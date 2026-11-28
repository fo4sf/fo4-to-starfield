"""BA2 archive reader for Fallout 4 (v1, v7, v8) and Starfield (v2, v3): general files (GNRL) and DX10 textures.

Binary header layout after the 24-byte `BTDX` common prefix (`<4sI4sIQ`: magic, version, kind, entry_count, name_offset):
  - v1, v7, v8: 0 extra header bytes (entry table begins at byte 24; payloads are uncompressed or zlib-compressed).
  - v2:         8 extra header bytes (entry table begins at byte 32; payloads are uncompressed or zlib-compressed).
  - v3:         12 extra header bytes (`<III`, uint32 compression method at +8; 0 = zlib/stored, 3 = LZ4).

    a = Ba2("Fallout4 - Textures1.ba2")
    a.names                    # file names as stored (backslashes)
    data = a.read(name)        # general file bytes, or a complete DDS (DX10 header) for a texture
Lookup is case-insensitive and slash-agnostic: a.find("textures/setdressing/x_d.dds").
Starfield v3 LZ4-compressed entries raise Ba2Error; v1/v2/v3(non-LZ4)/v7/v8 zlib and uncompressed entries are supported.
"""
import os
import struct
import zlib
from dataclasses import dataclass
from typing import Dict, List, Optional


HEADER_EXTRA_BYTES: Dict[int, int] = {
    1: 0,
    2: 8,
    3: 12,
    7: 0,
    8: 0,
}


class Ba2Error(ValueError):
    pass


@dataclass
class Entry:
    name: str
    kind: str                  # "GNRL" | "DX10"
    # GNRL
    offset: int = 0
    packed: int = 0
    unpacked: int = 0
    # DX10
    width: int = 0
    height: int = 0
    mips: int = 0
    dxgi: int = 0
    cubemap: bool = False
    chunks: Optional[list] = None      # (offset, packed, unpacked, start_mip, end_mip)


def _read_exact(f, size: int, path: str, what: str) -> bytes:
    buf = f.read(size)
    if len(buf) != size:
        raise Ba2Error(f"{path}: truncated BA2 while reading {what} (wanted {size} bytes, got {len(buf)})")
    return buf


def _decompress_zlib(raw: bytes, expected_unpacked: int, path: str, name: str) -> bytes:
    try:
        out = zlib.decompress(raw)
    except zlib.error as exc:
        raise Ba2Error(f"{path}: corrupt zlib stream in {name}: {exc}") from exc
    if expected_unpacked and len(out) != expected_unpacked:
        raise Ba2Error(f"{path}: unpacked length mismatch in {name} (got {len(out)}, expected {expected_unpacked})")
    return out


def _dds_header_dx10(width, height, mips, dxgi, cubemap):
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | (0x20000 if mips > 1 else 0)
    caps = 0x1000 | (0x8 | 0x400000 if mips > 1 else 0)
    caps2 = 0xFE00 | 0x200 if cubemap else 0
    h = b"DDS " + struct.pack("<7I", 124, flags, height, width, 0, 0, mips) + b"\0" * 44
    h += struct.pack("<II4sIIIII", 32, 0x4, b"DX10", 0, 0, 0, 0, 0)
    h += struct.pack("<5I", caps, caps2, 0, 0, 0)
    h += struct.pack("<5I", dxgi, 3, 4 if cubemap else 0, 6 if cubemap else 1, 0)
    return h


class Ba2:
    def __init__(self, path: str):
        self.path = path
        self._size = os.path.getsize(path)
        with open(path, "rb") as f:
            hdr = _read_exact(f, 24, path, "header")
            magic, version, kind, count, name_off = struct.unpack("<4sI4sIQ", hdr)
            if magic != b"BTDX":
                raise Ba2Error(f"{path}: not a BA2")
            self.version = version
            self.kind = kind.decode("ascii", "replace")
            if self.kind not in ("GNRL", "DX10"):
                raise Ba2Error(f"{path}: unsupported archive type {self.kind}")
            extra = HEADER_EXTRA_BYTES.get(version)
            if extra is None:
                raise Ba2Error(f"{path}: unsupported version {version}")
            extra_bytes = _read_exact(f, extra, path, f"v{version} extended header") if extra else b""
            self.compression = struct.unpack_from("<I", extra_bytes, 8)[0] if version == 3 else 0
            f.seek(24 + extra)
            raw = []
            for i in range(count):
                if self.kind == "GNRL":
                    rec = _read_exact(f, 36, path, f"GNRL entry {i}")
                    _h, _e, _d, _fl, off, pk, up, _al = struct.unpack("<I4sIIQIII", rec)
                    raw.append(("GNRL", off, pk, up))
                else:
                    rec = _read_exact(f, 24, path, f"DX10 entry {i}")
                    _h, _e, _d, _u, nch, _chsz, hgt, wid, mips, fmt, fl, _tile = struct.unpack("<I4sIBBHHHBBBB", rec)
                    chunks = [
                        struct.unpack("<QIIHHI", _read_exact(f, 24, path, f"DX10 entry {i} chunk {j}"))[:5]
                        for j in range(nch)
                    ]
                    raw.append(("DX10", wid, hgt, mips, fmt, bool(fl & 1), chunks))
            if count > 0 and (name_off < 24 + extra or name_off >= self._size):
                raise Ba2Error(f"{path}: invalid name table offset {name_off}")
            if count > 0:
                f.seek(name_off)
            names = []
            for i in range(count):
                n, = struct.unpack("<H", _read_exact(f, 2, path, f"name length {i}"))
                names.append(_read_exact(f, n, path, f"name {i}").decode("utf-8", "replace"))
        self.entries: List[Entry] = []
        for name, r in zip(names, raw):
            if r[0] == "GNRL":
                self.entries.append(Entry(name, "GNRL", offset=r[1], packed=r[2], unpacked=r[3]))
            else:
                self.entries.append(Entry(name, "DX10", width=r[1], height=r[2], mips=r[3], dxgi=r[4], cubemap=r[5], chunks=r[6]))
        self.names = names
        self._index = {self._norm(n): i for i, n in enumerate(names)}
        self._validate_entries()

    def _validate_entries(self) -> None:
        """Basic structural validation of entries to catch truncated or corrupt archives early."""
        if not self.entries:
            raise Ba2Error(f"{self.path}: archive contains no entries")
        for i, e in enumerate(self.entries):
            if not e.name:
                raise Ba2Error(f"{self.path}: entry {i} has empty name")
            if e.kind == "GNRL":
                if e.offset < 0 or e.unpacked < 0 or e.packed < 0:
                    raise Ba2Error(f"{self.path}: invalid offsets/sizes in GNRL entry {e.name}")
                payload = e.packed or e.unpacked
                if e.offset > self._size or e.offset + payload > self._size:
                    raise Ba2Error(f"{self.path}: GNRL entry {e.name} payload is outside the file")
            elif e.kind == "DX10":
                if e.width <= 0 or e.height <= 0 or e.mips <= 0:
                    raise Ba2Error(f"{self.path}: invalid dimensions in DX10 entry {e.name}")
                if not e.chunks:
                    raise Ba2Error(f"{self.path}: DX10 entry {e.name} has no chunks")
                for off, pk, up, _s, _e in e.chunks:
                    chunk = pk or up
                    if off > self._size or off + chunk > self._size:
                        raise Ba2Error(f"{self.path}: DX10 entry {e.name} chunk is outside the file")

    def summary(self) -> dict:
        """Return a short summary of the archive contents, including size totals and extension counts.

        Useful for conversion planning: total unpacked bytes to process, and which file types dominate.
        """
        gnrl = sum(1 for e in self.entries if e.kind == "GNRL")
        dx10 = sum(1 for e in self.entries if e.kind == "DX10")
        total_unpacked = 0
        total_packed = 0
        by_ext: dict[str, int] = {}
        for e in self.entries:
            if e.kind == "GNRL":
                u = e.unpacked
                p = e.packed or e.unpacked
            else:
                u = sum(c[2] for c in (e.chunks or []))
                p = sum((c[1] or c[2]) for c in (e.chunks or []))
            total_unpacked += u
            total_packed += p
            ext = e.name.rsplit(".", 1)[-1].lower() if "." in e.name else ""
            by_ext[ext] = by_ext.get(ext, 0) + 1
        return {
            "path": self.path,
            "version": self.version,
            "kind": self.kind,
            "entries": len(self.entries),
            "general": gnrl,
            "textures": dx10,
            "total_unpacked": total_unpacked,
            "total_packed": total_packed,
            "by_extension": dict(sorted(by_ext.items(), key=lambda x: -x[1])),
        }

    def size_estimates(self) -> dict:
        """Rough estimates of packed (on-disk) and unpacked (decompressed) total sizes.

        Useful for conversion planning: packed is what you download/store, unpacked is peak RAM/temp during extract.
        Counts only the payload sizes recorded in the index; does not read file data.
        """
        packed = 0
        unpacked = 0
        for e in self.entries:
            if e.kind == "GNRL":
                packed += e.packed or e.unpacked
                unpacked += e.unpacked
            elif e.kind == "DX10" and e.chunks:
                for _off, pk, up, _s, _e in e.chunks:
                    packed += pk or up
                    unpacked += up
        return {"packed_bytes": packed, "unpacked_bytes": unpacked, "entries": len(self.entries)}

    def largest_entries(self, n: int = 10) -> list:
        """Return the n largest entries by unpacked size, useful for conversion planning.

        Each item is a dict with name, kind, unpacked bytes, and packed bytes (0 if uncompressed).
        For DX10 textures the unpacked size is the sum of chunk unpacked sizes (excluding the DDS header).
        """
        def unpacked_of(e: Entry) -> int:
            if e.kind == "GNRL":
                return e.unpacked
            return sum(c[2] for c in (e.chunks or []))

        def packed_of(e: Entry) -> int:
            if e.kind == "GNRL":
                return e.packed or e.unpacked
            return sum((c[1] or c[2]) for c in (e.chunks or []))

        ranked = sorted(self.entries, key=unpacked_of, reverse=True)[:n]
        return [
            {
                "name": e.name,
                "kind": e.kind,
                "unpacked": unpacked_of(e),
                "packed": packed_of(e),
            }
            for e in ranked
        ]

    @staticmethod
    def _norm(n: str) -> str:
        return n.replace("/", "\\").lower().lstrip("\\")

    def find(self, name: str) -> Optional[int]:
        return self._index.get(self._norm(name))

    def read(self, name_or_index) -> bytes:
        i = name_or_index if isinstance(name_or_index, int) else self.find(name_or_index)
        if i is None:
            raise KeyError(name_or_index)
        e = self.entries[i]
        with open(self.path, "rb") as f:
            if e.kind == "GNRL":
                if e.packed and self.version == 3 and self.compression == 3:
                    raise Ba2Error("LZ4-compressed (v3) entries are not supported")
                f.seek(e.offset)
                raw = _read_exact(f, e.packed or e.unpacked, self.path, f"payload {e.name}")
                return _decompress_zlib(raw, e.unpacked, self.path, e.name) if e.packed else raw
            if self.version == 3 and self.compression == 3 and any(pk > 0 for _, pk, _, _, _ in (e.chunks or [])):
                raise Ba2Error("LZ4-compressed (v3) textures are not supported")
            out = [_dds_header_dx10(e.width, e.height, e.mips, e.dxgi, e.cubemap)]
            for off, pk, up, _s, _e in (e.chunks or []):
                f.seek(off)
                raw = _read_exact(f, pk or up, self.path, f"chunk {e.name}")
                out.append(_decompress_zlib(raw, up, self.path, e.name) if pk else raw)
            return b"".join(out)
