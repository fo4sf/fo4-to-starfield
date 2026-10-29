"""Raw Starfield plugin records: read, edit and write records without a schema.

Mutagen 0.55's Starfield schema lacks some star fields (SNAM, HNAM, WED0 of STDT: docs/planet/planet-probe.md), so
the planet master is written here, record by record: a cloned record keeps every subrecord it came with, byte for
byte, except the ones the caller replaces.

Layout (verified: SFBGS00D.esm, SFBGS003.esm and SFBGS008.esm of 1.16.244, and our Mutagen-written plugins; xEdit's
SF1 definitions agree):
  record    sig (4), data size u32, flags u32, form id u32, version control u32, form version u16, unknown u16;
            the data follows (24-byte header). Flag 0x00040000: the data is u32 decompressed size + a zlib stream.
  group     "GRUP", total size u32 (header included), label (4), group type i32, 8 more header bytes (0 in the top
            groups of both Bethesda's and Mutagen's plugins). Top groups (type 0) are labelled with a record type.
  subrecord sig (4), size u16, data. "XXXX" (size 4, u32 value) gives the size of the next subrecord, whose own u16
            size is then 0: needed above 65,535 bytes (a planet's HoudiniData PCCC can come close).
  TES4      HEDR (f32 version 0.96, u32 records + groups, u32 next object id), then MAST per master. Our Mutagen
            plugins that load in game write nothing else; header form version 576.
Form ids: the top byte is the index into the plugin's master list; the plugin's own records use len(masters).
"""
import mmap
import struct
import zlib

COMPRESSED = 0x00040000
ESM = 0x00000001
LOCALIZED = 0x00000080
PERSISTENT = 0x00000400
HEDR_VERSION = 0.96
HEADER_FORM_VERSION = 576           # the TES4 header of every Mutagen-written plugin of ours that loads in game
_REC = struct.Struct("<4sIIIIHH")   # sig, size, flags, form id, version control, form version, unknown
_GRP = struct.Struct("<4sI4siII")   # "GRUP", size, label, type, two u32
# top-group order of xEdit's SF1 definitions (AddGroupOrder), for the groups this package writes
GROUP_ORDER = ("GMST", "KYWD", "LCRT", "GLOB", "FACT", "STAT", "NPC_", "CLMT", "CELL", "WRLD", "QUST", "LCTN",
               "SFBK", "PNDT", "STDT")


class EsmError(ValueError):
    pass


# ------------------------------------------------------------------------------------------------ subrecords
def parse_subrecords(data):
    """[(sig bytes, data bytes)] of a record's (decompressed) data, XXXX sizes applied; raises EsmError on a
    truncated subrecord or a dangling XXXX."""
    out = []
    p, n, big = 0, len(data), None
    while p < n:
        if p + 6 > n:
            raise EsmError(f"truncated subrecord header at {p} of {n}")
        sig = bytes(data[p:p + 4])
        size = struct.unpack_from("<H", data, p + 4)[0]
        if sig == b"XXXX":
            if size != 4 or p + 10 > n:
                raise EsmError(f"bad XXXX at {p}")
            big = struct.unpack_from("<I", data, p + 6)[0]
            p += 10
            continue
        if big is not None:
            size, big = big, None
        if p + 6 + size > n:
            raise EsmError(f"subrecord {sig!r} at {p} runs past the record ({size} bytes, {n - p - 6} left)")
        out.append((sig, bytes(data[p + 6:p + 6 + size])))
        p += 6 + size
    if big is not None:
        raise EsmError("XXXX at the end of a record")
    return out


def pack_subrecords(subs):
    parts = []
    for sig, data in subs:
        if len(sig) != 4:
            raise EsmError(f"subrecord signature {sig!r} is not 4 bytes")
        if len(data) > 0xFFFF:
            parts.append(b"XXXX" + struct.pack("<HI", 4, len(data)) + sig + b"\0\0" + data)
        else:
            parts.append(sig + struct.pack("<H", len(data)) + data)
    return b"".join(parts)


def zstring(data):
    """A NUL-terminated string field (Windows-1252, as Bethesda's plugins)."""
    return bytes(data).split(b"\0", 1)[0].decode("cp1252", "replace")


def zbytes(text):
    return text.encode("cp1252") + b"\0"


# ------------------------------------------------------------------------------------------------ records
class Record:
    """One record: header fields and its subrecords (decompressed). Edit .subs, then to_bytes()."""

    __slots__ = ("sig", "flags", "formid", "vc", "version", "unknown", "subs", "offset")

    def __init__(self, sig, formid, subs=None, flags=0, vc=0, version=0x245, unknown=0, offset=None):
        self.sig = sig if isinstance(sig, bytes) else sig.encode("ascii")
        self.formid, self.flags, self.vc, self.version, self.unknown = formid, flags, vc, version, unknown
        self.subs = list(subs or [])
        self.offset = offset

    @classmethod
    def parse(cls, buf, off):
        """The record at buf[off:] (a record header, not a GRUP)."""
        if off + 24 > len(buf):
            raise EsmError(f"truncated record header at {off}")
        sig, size, flags, fid, vc, ver, unk = _REC.unpack_from(buf, off)
        if sig == b"GRUP":
            raise EsmError(f"a group, not a record, at {off}")
        end = off + 24 + size
        if end > len(buf):
            raise EsmError(f"record {sig!r} {fid:08X} at {off} runs past the file")
        data = bytes(buf[off + 24:end])
        if flags & COMPRESSED:
            if size < 4:
                raise EsmError(f"compressed record {fid:08X} without its size field")
            want = struct.unpack_from("<I", data, 0)[0]
            try:
                data = zlib.decompress(data[4:])
            except zlib.error as e:
                raise EsmError(f"record {sig!r} {fid:08X}: {e}") from None
            if len(data) != want:
                raise EsmError(f"record {fid:08X}: decompressed {len(data)} bytes, header says {want}")
        return cls(sig, fid, parse_subrecords(data), flags, vc, ver, unk, off)

    def copy(self, formid=None):
        return Record(self.sig, self.formid if formid is None else formid, list(self.subs), self.flags, self.vc,
                      self.version, self.unknown)

    # access
    def get(self, sig, default=None):
        sig = sig if isinstance(sig, bytes) else sig.encode("ascii")
        return next((d for s, d in self.subs if s == sig), default)

    def all(self, sig):
        sig = sig if isinstance(sig, bytes) else sig.encode("ascii")
        return [d for s, d in self.subs if s == sig]

    def index(self, sig, start=0):
        sig = sig if isinstance(sig, bytes) else sig.encode("ascii")
        for i in range(start, len(self.subs)):
            if self.subs[i][0] == sig:
                return i
        return -1

    @property
    def edid(self):
        d = self.get(b"EDID")
        return zstring(d) if d is not None else ""

    def data(self):
        return pack_subrecords(self.subs)

    def to_bytes(self, compress=None, level=6):
        """Header + data. compress None keeps the record's own compressed flag."""
        data = self.data()
        flags = self.flags
        if compress is None:
            compress = bool(flags & COMPRESSED)
        if compress:
            body = struct.pack("<I", len(data)) + zlib.compress(data, level)
            flags |= COMPRESSED
        else:
            body = data
            flags &= ~COMPRESSED
        return _REC.pack(self.sig, len(body), flags, self.formid, self.vc, self.version, self.unknown) + body

    def __repr__(self):
        return f"Record({self.sig.decode()} {self.formid:08X} {self.edid!r}, {len(self.subs)} subrecords)"


def group_bytes(label, payload, gtype=0):
    lab = label.encode("ascii") if isinstance(label, str) else label
    return _GRP.pack(b"GRUP", 24 + len(payload), lab, gtype, 0, 0) + payload


# ------------------------------------------------------------------------------------------------ reading
class Plugin:
    """A plugin file, memory-mapped: its header, masters and top groups. Records are parsed on demand, so a full
    Starfield.esm (1.46 GB) costs only the groups that are read."""

    def __init__(self, path):
        self.path = path
        self._f = open(path, "rb")
        try:
            self.buf = mmap.mmap(self._f.fileno(), 0, access=mmap.ACCESS_READ)
        except ValueError:                       # an empty file cannot be mapped
            self._f.close()
            raise EsmError(f"{path}: empty file") from None
        try:
            self._scan(path)
        except BaseException:
            self.close()
            raise

    def _scan(self, path):
        if len(self.buf) < 24 or self.buf[:4] != b"TES4":
            raise EsmError(f"{path}: not a TES4 plugin")
        self.header = Record.parse(self.buf, 0)
        self.masters = [zstring(d) for s, d in self.header.subs if s == b"MAST"]
        self.flags = self.header.flags
        self.groups = {}
        off = 24 + struct.unpack_from("<I", self.buf, 4)[0]
        while off < len(self.buf):
            if off + 24 > len(self.buf):
                raise EsmError(f"{path}: truncated group header at {off}")
            sig, size, label, gtype, _, _ = _GRP.unpack_from(self.buf, off)
            if sig != b"GRUP" or size < 24 or off + size > len(self.buf):
                raise EsmError(f"{path}: bad top group at {off}")
            self.groups.setdefault(label.decode("latin1"), []).append((off + 24, off + size))
            off += size

    def close(self):
        try:
            self.buf.close()
        except (AttributeError, ValueError, BufferError):
            pass
        self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @property
    def localized(self):
        return bool(self.flags & LOCALIZED)

    @property
    def self_index(self):
        return len(self.masters)

    def walk(self, start, end, depth=0, groups=None):
        """Yield ('GRUP', label bytes, type, start, end, depth) and ('REC', offset, sig, depth) items in file order.
        groups (a set of group types) restricts which subgroups are entered (their items are skipped)."""
        off = start
        while off < end:
            if off + 24 > end:
                raise EsmError(f"{self.path}: truncated item at {off}")
            sig = bytes(self.buf[off:off + 4])
            if sig == b"GRUP":
                _, size, label, gtype, _, _ = _GRP.unpack_from(self.buf, off)
                if size < 24 or off + size > end:
                    raise EsmError(f"{self.path}: bad group at {off}")
                yield ("GRUP", label, gtype, off + 24, off + size, depth)
                if groups is None or gtype in groups:
                    yield from self.walk(off + 24, off + size, depth + 1, groups)
                off += size
                continue
            size = struct.unpack_from("<I", self.buf, off + 4)[0]
            if off + 24 + size > end:
                raise EsmError(f"{self.path}: record at {off} runs past its group")
            yield ("REC", off, sig, depth)
            off += 24 + size

    def records(self, label, sigs=None):
        """Every record of a flat top group (STDT, PNDT, LCTN, KYWD, ...), parsed."""
        want = None if sigs is None else {s if isinstance(s, bytes) else s.encode("ascii") for s in sigs}
        for start, end in self.groups.get(label, []):
            for item in self.walk(start, end):
                if item[0] == "REC" and (want is None or item[2] in want):
                    yield Record.parse(self.buf, item[1])

    def record_at(self, off):
        return Record.parse(self.buf, off)


# ------------------------------------------------------------------------------------------------ writing
class PluginWriter:
    """A new plugin: masters, header flags and records, written in xEdit's top-group order."""

    def __init__(self, masters, flags=ESM, author=None, description=None):
        self.masters = list(masters)
        self.flags = flags
        self.author, self.description = author, description
        self.records = []

    @property
    def self_index(self):
        return len(self.masters)

    def own(self, local):
        """This plugin's form id for local id `local`."""
        return (self.self_index << 24) | (local & 0xFFFFFF)

    def add(self, rec):
        self.records.append(rec)
        return rec

    def to_bytes(self, compress=None):
        by_group = {}
        for r in self.records:
            by_group.setdefault(r.sig.decode("ascii"), []).append(r)
        order = [g for g in GROUP_ORDER if g in by_group] + sorted(g for g in by_group if g not in GROUP_ORDER)
        body = b"".join(group_bytes(g, b"".join(r.to_bytes(compress) for r in by_group[g])) for g in order)
        count = len(self.records) + len(order)
        own = [r.formid & 0xFFFFFF for r in self.records if r.formid >> 24 == self.self_index]
        next_id = max(own) + 1 if own else 0x800
        hsubs = [(b"HEDR", struct.pack("<fII", HEDR_VERSION, count, next_id))]
        if self.author:
            hsubs.append((b"CNAM", zbytes(self.author)))
        if self.description:
            hsubs.append((b"SNAM", zbytes(self.description)))
        hsubs += [(b"MAST", zbytes(m)) for m in self.masters]
        head = Record(b"TES4", 0, hsubs, self.flags, 0, HEADER_FORM_VERSION, 0)
        return head.to_bytes(compress=False) + body

    def write(self, path, compress=None):
        data = self.to_bytes(compress)
        with open(path, "wb") as f:
            f.write(data)
        return len(data)
