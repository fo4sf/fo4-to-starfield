"""Read-only BSA v104 (0x68) archive reader for Fallout 3 and Fallout: New Vegas, matching the API shape of
`src/fo4sf/ba2.py`.

    a = Bsa("Fallout - Meshes.bsa")
    a.names                              # file paths as stored (backslashes)
    data = a.read("meshes/x/y.nif")      # case-insensitive, slash-agnostic lookup
    a.extract_all(out_dir, names=[...])  # path-traversal-guarded extraction
"""
import argparse
import os
import struct
import sys
import zlib
from dataclasses import dataclass
from typing import Iterable, List, Optional

BSA_MAGIC = b"BSA\x00"
BSA_VERSION_104 = 104  # 0x68 (Fallout 3, Fallout: New Vegas, TES5)

FLAG_INCLUDE_DIRECTORY_NAMES = 0x0001
FLAG_INCLUDE_FILE_NAMES = 0x0002
FLAG_COMPRESSED_BY_DEFAULT = 0x0004
FLAG_EMBED_FILE_NAMES = 0x0100

FILE_SIZE_MASK = 0x3FFFFFFF
FILE_COMPRESS_TOGGLE = 1 << 30


class BsaError(ValueError):
    pass


@dataclass
class BsaEntry:
    name: str
    offset: int
    size: int
    compressed: bool
    folder_hash: int = 0
    file_hash: int = 0


def _read_exact(f, size: int, path: str, what: str) -> bytes:
    buf = f.read(size)
    if len(buf) != size:
        raise BsaError(f"{path}: truncated BSA while reading {what} (wanted {size} bytes, got {len(buf)})")
    return buf


class Bsa:
    def __init__(self, path: str):
        self.path = path
        self._size = os.path.getsize(path)
        with open(path, "rb") as f:
            hdr = _read_exact(f, 36, path, "header")
            (
                magic,
                version,
                folder_offset,
                archive_flags,
                folder_count,
                file_count,
                total_folder_name_len,
                total_file_name_len,
                file_flags,
            ) = struct.unpack("<4s8I", hdr)

            if magic != BSA_MAGIC:
                raise BsaError(f"{path}: not a BSA archive (magic={magic!r})")
            if version != BSA_VERSION_104:
                raise BsaError(f"{path}: unsupported BSA version {version} (expected {BSA_VERSION_104})")
            if folder_offset != 36:
                raise BsaError(f"{path}: unexpected folder table offset {folder_offset} (expected 36)")
            if file_count == 0 or folder_count == 0:
                raise BsaError(f"{path}: archive contains no entries")
            if not (archive_flags & FLAG_INCLUDE_DIRECTORY_NAMES) or not (archive_flags & FLAG_INCLUDE_FILE_NAMES):
                raise BsaError(
                    f"{path}: BSA lacks directory or file name tables (archive_flags=0x{archive_flags:04X})"
                )

            self.version = version
            self.archive_flags = archive_flags
            self.file_flags = file_flags
            self._embed_names = bool(archive_flags & FLAG_EMBED_FILE_NAMES)
            default_compressed = bool(archive_flags & FLAG_COMPRESSED_BY_DEFAULT)

            # 1. Folder records: folder_count * 16 bytes (<QII: name_hash, count, offset_plus_total_file_name_len)
            folders = []
            for i in range(folder_count):
                rec = _read_exact(f, 16, path, f"folder record {i}")
                f_hash, f_cnt, f_off = struct.unpack("<QII", rec)
                block_off = f_off - total_file_name_len
                if block_off < 36 + folder_count * 16 or block_off >= self._size:
                    raise BsaError(f"{path}: invalid folder block offset {block_off} for folder {i}")
                folders.append((f_hash, f_cnt, block_off))

            # 2. File record blocks: bzstring folder name + f_cnt * 16-byte file records
            raw_files = []
            for i, (f_hash, f_cnt, block_off) in enumerate(folders):
                f.seek(block_off)
                dir_len = _read_exact(f, 1, path, f"folder {i} name length")[0]
                dir_raw = _read_exact(f, dir_len, path, f"folder {i} name")
                dir_name = dir_raw.rstrip(b"\x00").decode("latin-1").replace("/", "\\").strip("\\")
                for j in range(f_cnt):
                    frec = _read_exact(f, 16, path, f"folder {i} file record {j}")
                    e_hash, raw_size, data_off = struct.unpack("<QII", frec)
                    size = raw_size & FILE_SIZE_MASK
                    toggled = bool(raw_size & FILE_COMPRESS_TOGGLE)
                    is_comp = default_compressed ^ toggled
                    raw_files.append((dir_name, f_hash, e_hash, data_off, size, is_comp))

            if len(raw_files) != file_count:
                raise BsaError(
                    f"{path}: folder file counts sum to {len(raw_files)}, header declares {file_count}"
                )

            # 3. File name block immediately follows the last file record block
            name_block = _read_exact(f, total_file_name_len, path, "file name table")
            parts = name_block.split(b"\x00")
            if parts and parts[-1] == b"":
                parts = parts[:-1]
            if len(parts) != file_count:
                raise BsaError(
                    f"{path}: file name table holds {len(parts)} names, header declares {file_count}"
                )
            file_names = [p.decode("latin-1") for p in parts]

        self.entries: List[BsaEntry] = []
        self.names: List[str] = []
        for base_name, (dir_name, f_hash, e_hash, data_off, size, is_comp) in zip(file_names, raw_files):
            clean_base = base_name.replace("/", "\\").lstrip("\\")
            full_name = f"{dir_name}\\{clean_base}" if dir_name else clean_base
            entry = BsaEntry(
                name=full_name,
                offset=data_off,
                size=size,
                compressed=is_comp,
                folder_hash=f_hash,
                file_hash=e_hash,
            )
            self.entries.append(entry)
            self.names.append(full_name)

        self._index = {self._norm(n): i for i, n in enumerate(self.names)}
        self._validate_entries()

    def _validate_entries(self) -> None:
        for i, e in enumerate(self.entries):
            if not e.name:
                raise BsaError(f"{self.path}: entry {i} has empty name")
            if e.offset < 36 or e.size < 0 or e.offset + e.size > self._size:
                raise BsaError(f"{self.path}: entry {e.name} payload [{e.offset}, +{e.size}] is outside the file")

    @staticmethod
    def _norm(name: str) -> str:
        return name.replace("/", "\\").lower().lstrip("\\")

    def summary(self) -> dict:
        comp = sum(1 for e in self.entries if e.compressed)
        return {
            "path": self.path,
            "version": self.version,
            "archive_flags": self.archive_flags,
            "entries": len(self.entries),
            "compressed": comp,
            "uncompressed": len(self.entries) - comp,
            "packed_bytes": sum(e.size for e in self.entries),
        }

    def find(self, name: str) -> Optional[int]:
        return self._index.get(self._norm(name))

    def read(self, name_or_index) -> bytes:
        if isinstance(name_or_index, int):
            if name_or_index < 0 or name_or_index >= len(self.entries):
                raise IndexError(name_or_index)
            idx = name_or_index
        else:
            found = self.find(name_or_index)
            if found is None:
                raise KeyError(name_or_index)
            idx = found

        e = self.entries[idx]
        with open(self.path, "rb") as f:
            f.seek(e.offset)
            blob = _read_exact(f, e.size, self.path, f"payload {e.name}")

        pos = 0
        if self._embed_names:
            if len(blob) < 1:
                raise BsaError(f"{self.path}: missing embedded filename length in {e.name}")
            emb_len = blob[0]
            pos = 1 + emb_len
            if pos > len(blob):
                raise BsaError(f"{self.path}: embedded filename length {emb_len} exceeds payload in {e.name}")

        if not e.compressed:
            return blob[pos:]

        if pos + 4 > len(blob):
            raise BsaError(f"{self.path}: compressed entry {e.name} lacks 4-byte unpacked size")
        unpacked_size = struct.unpack_from("<I", blob, pos)[0]
        stream = blob[pos + 4 :]
        if unpacked_size == 0 and len(stream) == 0:
            return b""
        try:
            out = zlib.decompress(stream)
        except zlib.error as exc:
            raise BsaError(f"{self.path}: corrupt zlib stream in {e.name}: {exc}") from exc
        if len(out) != unpacked_size:
            raise BsaError(
                f"{self.path}: unpacked length mismatch in {e.name} (got {len(out)}, expected {unpacked_size})"
            )
        return out

    @staticmethod
    def _safe_rel_parts(entry_name: str, archive_path: str) -> List[str]:
        norm = entry_name.replace("/", "\\")
        if norm.startswith("\\") or ":" in norm:
            raise BsaError(f"{archive_path}: unsafe entry path {entry_name!r}")
        parts = [p for p in norm.split("\\") if p]
        if not parts or any(p in (".", "..") for p in parts):
            raise BsaError(f"{archive_path}: unsafe traversal segment in {entry_name!r}")
        return parts

    def extract_all(self, out_dir: str, names: Optional[Iterable[str]] = None) -> List[str]:
        out_abs = os.path.abspath(out_dir)
        os.makedirs(out_abs, exist_ok=True)

        if names is None:
            indices = list(range(len(self.entries)))
        else:
            indices = []
            for want in names:
                idx = self.find(want)
                if idx is None:
                    raise KeyError(want)
                indices.append(idx)

        written: List[str] = []
        for idx in indices:
            e = self.entries[idx]
            parts = self._safe_rel_parts(e.name, self.path)
            dst = os.path.abspath(os.path.join(out_abs, *parts))
            if os.path.commonpath([out_abs, dst]) != out_abs:
                raise BsaError(f"{self.path}: entry {e.name!r} escapes target directory")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            data = self.read(idx)
            with open(dst, "wb") as fp:
                fp.write(data)
            written.append(dst)
        return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Read-only BSA v104 listing and extraction utility.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ls = sub.add_parser("list", help="List entries in a BSA v104 archive.")
    ls.add_argument("archive")
    ls.add_argument("--limit", type=int, default=0, help="Maximum entry names to print (0 = all).")

    ex = sub.add_parser("extract", help="Extract all or selected entries from a BSA v104 archive.")
    ex.add_argument("archive")
    ex.add_argument("--out", required=True, help="Destination directory.")
    ex.add_argument("--names", nargs="*", default=None, help="Optional subset of entry paths to extract.")

    a = ap.parse_args(argv)
    bsa = Bsa(a.archive)
    if a.cmd == "list":
        shown = bsa.names[: a.limit] if a.limit > 0 else bsa.names
        for n in shown:
            print(n)
        s = bsa.summary()
        print(
            f"summary: version={s['version']} flags=0x{s['archive_flags']:04X} "
            f"entries={s['entries']} compressed={s['compressed']} packed_bytes={s['packed_bytes']}"
        )
        return 0
    written = bsa.extract_all(a.out, names=a.names)
    print(f"extracted {len(written)} file(s) to {os.path.abspath(a.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
