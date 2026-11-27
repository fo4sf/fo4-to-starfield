"""build_fo4port_r11_museum.py: Lossless FO4Port.esm extension for Round 11 Step 3b+3c.

Appends FO4Port_ConcordMuseum01 and FO4Port_PrewarVault111 (plus their net-new transitive base records,
converted Starfield v17 interior NAVM + NAVI override 0x00000FF1 for ConcordMuseum01, and minimal
asset/texture BA2 v2 deltas) onto the proven doors_anim_b00 FO4Port baseline while guaranteeing:
  - 0 missing FormIDs from the baseline FO4Port.esm
  - 0 record type changes on any baseline FormID
  - 0 byte changes on any non-TES4 baseline record (100% byte-identical preservation)
  - All appended local FormIDs strictly >= --start-id (default 0x00E200, strictly above 0x00E199)
  - Minimal delta merged directly into FO4Port - Main.ba2 and FO4Port - Textures.ba2
    (0 companion FO4PortTextures2.esm stub, +0 extra plugins, strictly below 4 GiB BA2 ceiling)

Usage:
  python scripts/terrain/build_fo4port_r11_museum.py \
      --base-dir <doors_anim_b00/port> \
      --source-dir <interiors_b10/port> \
      --fo4-esm <Fallout4.esm> \
      --out-dir <staging output dir> \
      [--cells FO4Port_ConcordMuseum01,FO4Port_PrewarVault111] \
      [--start-id 0x00E200] [--min-free-gb 60] [--esm-only]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import struct
import sys
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SRC_DIR = REPO / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fo4sf import navmesh as navm  # noqa: E402
from fo4sf.ba2 import Ba2, Ba2Error  # noqa: E402

DEFAULT_CELLS = ("FO4Port_ConcordMuseum01", "FO4Port_PrewarVault111")
DEFAULT_START_ID = 0x00E200
DEFAULT_MIN_FREE_GB = 60.0
BASE_B00_SHA256 = "07756819ecf7ab9a88af6421478c7c05f13eb6dbef062a1a61b98ec63e7bbe60"
FO4_MUSEUM_CELL_FID = 0x00017DF7
FO4_MUSEUM_NAVM_FID = 0x00197BB0
NAVI_FID = 0x00000FF1
# Lighting template proven on FO4Port_Vault111Cryo (KreetBase01LGTtemplate: warm ambient + 6-axis DALC,
# replacing ShipInteriorLT 0x00006658 which had black ambient + zero DALC and caused blown-out lobby lighting).
PROVEN_INTERIOR_LTMP = 0x0006BCF8
LEGACY_DARK_LTMP = 0x00006658
MUSEUM_BASEMENT_GATE_BASE_EDID = "FO4Port_switchdoorexsmlatch02_N84C71750"
MUSEUM_BASEMENT_TERM_BASE_EDID = "FO4Port_term_08110c_fallout4"
MUSEUM_FRONT_DOOR_BASE_EDID = "FO4Port_paintedwooddoordoubleload01"
MUSEUM_ROOF_DOOR_BASE_EDID = "FO4Port_bldwoodpdoorload01"
MUSEUM_MEDKIT_CONT_BASE_EDID = "FO4Port_cont_04b6ea_fallout4"
PRESTON_DOOR_BASE_EDID = "FO4Port_BldWoodPDoor02"
PRESTON_EXIT_DOOR_BASE_EDID = "FO4Port_BldWoodPDoor01"
STARFIELD_XLOC_FLAG_LOCKED = 1
LOCK_LEVEL_NOVICE = 25
LOCK_LEVEL_INACCESSIBLE = 255
PERSISTENT_FLAG = 0x00000400
UNITS_PER_METRE = 70.0
ARCHIVE_LIMIT = 4095 * (2 ** 20)  # 4,293,918,720 B (< 4 GiB uint32 ceiling)
BA2_ALIGN = 0xBAADF00D
COMPRESSED_FLAG = 0x00040000
TOP_GRUP_ORDER = (
    b"ACTI",
    b"CONT",
    b"DOOR",
    b"MISC",
    b"STAT",
    b"MSTT",
    b"FURN",
    b"TERM",
    b"CELL",
    b"LCTN",
    b"TMLM",
    b"NAVI",
)
# Subrecords that carry FormIDs for our appended record types.
FORMID_SUBRECORDS: Dict[bytes, Set[bytes]] = {
    b"CELL": {b"XLCN"},
    b"REFR": {b"NAME", b"XESP", b"XLKR", b"XLOC", b"XTEL"},
    b"LCTN": {b"PNAM"},
    b"TERM": {b"DNAM"},
    b"CONT": {b"CNTO"},
}
# FO4 ConcordMuseum01 door REFRs referenced by FO4 NAVM 0x00197BB0 (metres = FO4 units / 70).
FO4_MUSEUM_NAVM_DOOR_FALLBACKS: Dict[int, Tuple[float, float, float]] = {
    0x00077D22: (640.0 / 70.0, 0.0 / 70.0, -64.0 / 70.0),
    0x0001B94A: (883.5 / 70.0, -1.0 / 70.0, 640.0 / 70.0),
    0x0002C1C6: (-1536.0 / 70.0, 640.0 / 70.0, 640.0 / 70.0),
}
ASCII_PATH_RE = re.compile(rb"[A-Za-z0-9_\\/\-\.]{5,180}")


class ExtensionError(ValueError):
    """Raised when lossless invariants or archive limits are violated."""


@dataclass
class RawRecord:
    sig: bytes
    flags: int
    fid: int
    revision: int
    version: int
    unknown: int
    raw_body: bytes  # exact on-disk payload (compressed if COMPRESSED_FLAG set)

    def to_bytes(self) -> bytes:
        hdr = struct.pack(
            "<4sIIIIHH",
            self.sig,
            len(self.raw_body),
            self.flags,
            self.fid,
            self.revision,
            self.version,
            self.unknown,
        )
        return hdr + self.raw_body

    def decompressed_body(self) -> bytes:
        if self.flags & COMPRESSED_FLAG:
            if len(self.raw_body) < 4:
                raise ExtensionError(f"compressed record {self.sig!r} 0x{self.fid:08X} truncated")
            return zlib.decompress(self.raw_body[4:])
        return self.raw_body


@dataclass
class ParsedCell:
    cell_rec: RawRecord
    edid: str
    persistent: List[RawRecord]
    temporary: List[RawRecord]


@dataclass
class TopGrup:
    label: bytes
    gtype: int
    stamp: int
    unknown: int
    payload: bytes  # raw bytes after the 24-byte GRUP header

    def to_bytes(self) -> bytes:
        total = 24 + len(self.payload)
        hdr = struct.pack("<4sI4sIII", b"GRUP", total, self.label, self.gtype, self.stamp, self.unknown)
        return hdr + self.payload


# ---------------------------------------------------------------------------
# Low-level ESM subrecord & record helpers
# ---------------------------------------------------------------------------
def iter_subrecords(body: bytes) -> Iterable[Tuple[bytes, bytes]]:
    pos = 0
    n = len(body)
    xxxx: Optional[int] = None
    while pos + 6 <= n:
        sig = body[pos : pos + 4]
        sz = struct.unpack_from("<H", body, pos + 4)[0]
        pos += 6
        if sig == b"XXXX":
            if sz != 4 or pos + 4 > n:
                raise ExtensionError("malformed XXXX subrecord")
            xxxx = struct.unpack_from("<I", body, pos)[0]
            pos += 4
            continue
        if xxxx is not None:
            sz = xxxx
            xxxx = None
        if pos + sz > n:
            raise ExtensionError(f"truncated subrecord {sig!r}: need {sz} B at {pos}/{n}")
        yield sig, body[pos : pos + sz]
        pos += sz
    if pos != n:
        raise ExtensionError(f"trailing {n - pos} bytes in record body")


def pack_subrecord(sig: bytes, payload: bytes) -> bytes:
    if len(payload) > 0xFFFF:
        return (
            b"XXXX"
            + struct.pack("<HI", 4, len(payload))
            + sig
            + struct.pack("<H", 0)
            + payload
        )
    return sig + struct.pack("<H", len(payload)) + payload


def pack_subrecords(subs: Sequence[Tuple[bytes, bytes]]) -> bytes:
    return b"".join(pack_subrecord(sig, payload) for sig, payload in subs)


def get_edid(rec: RawRecord) -> str:
    for sig, payload in iter_subrecords(rec.decompressed_body()):
        if sig == b"EDID":
            return payload.rstrip(b"\x00").decode("utf-8", "replace")
    return ""


def parse_top_level(data: bytes) -> Tuple[RawRecord, List[TopGrup]]:
    """Split an ESM into its TES4 record and ordered list of raw top-level GRUPs."""
    if len(data) < 24 or data[:4] != b"TES4":
        raise ExtensionError("input file does not start with TES4")
    tsize, flags, fid, rev, ver, unk = struct.unpack_from("<IIIIHH", data, 4)
    tes4 = RawRecord(b"TES4", flags, fid, rev, ver, unk, data[24 : 24 + tsize])
    pos = 24 + tsize
    grups: List[TopGrup] = []
    n = len(data)
    while pos < n:
        if pos + 24 > n or data[pos : pos + 4] != b"GRUP":
            raise ExtensionError(f"expected top-level GRUP at offset {pos}, got {data[pos:pos+4]!r}")
        gsize = struct.unpack_from("<I", data, pos + 4)[0]
        if gsize < 24 or pos + gsize > n:
            raise ExtensionError(f"invalid top-level GRUP size {gsize} at offset {pos}")
        label = data[pos + 8 : pos + 12]
        gtype, stamp, gunk = struct.unpack_from("<III", data, pos + 12)
        grups.append(TopGrup(label, gtype, stamp, gunk, data[pos + 24 : pos + gsize]))
        pos += gsize
    return tes4, grups


def walk_all_records(data: bytes) -> List[RawRecord]:
    """Walk every record in an ESM (including TES4 and nested CELL/WRLD children)."""
    out: List[RawRecord] = []
    n = len(data)

    def _walk(start: int, end: int) -> None:
        pos = start
        while pos < end:
            sig = data[pos : pos + 4]
            if sig == b"GRUP":
                gsize = struct.unpack_from("<I", data, pos + 4)[0]
                if gsize < 24 or pos + gsize > end:
                    raise ExtensionError(f"invalid nested GRUP at {pos}")
                _walk(pos + 24, pos + gsize)
                pos += gsize
            else:
                rsize, flags, fid, rev, ver, unk = struct.unpack_from("<IIIIHH", data, pos + 4)
                if pos + 24 + rsize > end:
                    raise ExtensionError(f"truncated record {sig!r} 0x{fid:08X} at {pos}")
                out.append(RawRecord(sig, flags, fid, rev, ver, unk, data[pos + 24 : pos + 24 + rsize]))
                pos += 24 + rsize

    _walk(0, n)
    return out


def parse_source_esm(data: bytes) -> Tuple[Dict[int, RawRecord], Dict[str, ParsedCell]]:
    """Parse source ESM into {fid: RawRecord} and {cell_edid: ParsedCell}."""
    by_fid: Dict[int, RawRecord] = {}
    cell_recs: Dict[int, RawRecord] = {}
    cell_children: Dict[int, Dict[int, List[RawRecord]]] = defaultdict(lambda: {8: [], 9: []})

    def _walk(start: int, end: int, cur_cell: Optional[int] = None, cur_gtype: Optional[int] = None) -> None:
        pos = start
        while pos < end:
            sig = data[pos : pos + 4]
            if sig == b"GRUP":
                gsize = struct.unpack_from("<I", data, pos + 4)[0]
                label = data[pos + 8 : pos + 12]
                gtype = struct.unpack_from("<I", data, pos + 12)[0]
                next_cell = struct.unpack("<I", label)[0] if gtype == 6 else cur_cell
                _walk(pos + 24, pos + gsize, next_cell, gtype)
                pos += gsize
            else:
                rsize, flags, fid, rev, ver, unk = struct.unpack_from("<IIIIHH", data, pos + 4)
                rec = RawRecord(sig, flags, fid, rev, ver, unk, data[pos + 24 : pos + 24 + rsize])
                if sig != b"TES4":
                    by_fid[fid] = rec
                if sig == b"CELL":
                    cell_recs[fid] = rec
                elif cur_cell is not None and cur_gtype in (8, 9):
                    cell_children[cur_cell][cur_gtype].append(rec)
                pos += 24 + rsize

    _walk(0, len(data))

    cells_by_edid: Dict[str, ParsedCell] = {}
    for cfid, crec in cell_recs.items():
        edid = get_edid(crec)
        if edid:
            cells_by_edid[edid] = ParsedCell(
                cell_rec=crec,
                edid=edid,
                persistent=list(cell_children[cfid][8]),
                temporary=list(cell_children[cfid][9]),
            )
    return by_fid, cells_by_edid


def get_master_count(tes4: RawRecord) -> int:
    return sum(1 for sig, _ in iter_subrecords(tes4.decompressed_body()) if sig == b"MAST")


def update_tes4_hedr(tes4: RawRecord, total_non_tes4_and_grups: int, next_object_id: int) -> RawRecord:
    """Return a copy of TES4 with updated HEDR (num_records, next_object_id); all other subrecords untouched."""
    subs: List[Tuple[bytes, bytes]] = []
    updated = False
    for sig, payload in iter_subrecords(tes4.decompressed_body()):
        if sig == b"HEDR" and len(payload) == 12:
            ver_f, _nrec, _next_id = struct.unpack("<fII", payload)
            subs.append((b"HEDR", struct.pack("<fII", ver_f, total_non_tes4_and_grups, next_object_id)))
            updated = True
        else:
            subs.append((sig, payload))
    if not updated:
        raise ExtensionError("TES4 missing 12-byte HEDR subrecord")
    new_body = pack_subrecords(subs)
    if tes4.flags & COMPRESSED_FLAG:
        raw_body = struct.pack("<I", len(new_body)) + zlib.compress(new_body)
    else:
        raw_body = new_body
    return RawRecord(b"TES4", tes4.flags, tes4.fid, tes4.revision, tes4.version, tes4.unknown, raw_body)


def count_records_and_grups(data: bytes) -> int:
    """Count all non-TES4 records + GRUP headers (TES4 HEDR num_records convention)."""
    count = 0
    n = len(data)
    tsize = struct.unpack_from("<I", data, 4)[0]

    def _walk(start: int, end: int) -> None:
        nonlocal count
        pos = start
        while pos < end:
            sig = data[pos : pos + 4]
            if sig == b"GRUP":
                gsize = struct.unpack_from("<I", data, pos + 4)[0]
                count += 1
                _walk(pos + 24, pos + gsize)
                pos += gsize
            else:
                rsize = struct.unpack_from("<I", data, pos + 4)[0]
                count += 1
                pos += 24 + rsize

    _walk(24 + tsize, n)
    return count


def _remap_fid_in_payload(
    sig: bytes,
    payload: bytes,
    fid_map: Dict[int, int],
    local_prefix: int,
    rec: RawRecord,
) -> bytes:
    offsets: Tuple[int, ...]
    if sig == b"XLKR" and len(payload) >= 8:
        offsets = (0, 4)
    elif sig == b"XLOC" and len(payload) >= 8:
        offsets = (4,)
    elif len(payload) >= 4:
        offsets = (0,)
    else:
        return payload

    buf = bytearray(payload)
    for off in offsets:
        val = struct.unpack_from("<I", buf, off)[0]
        if (val >> 24) == local_prefix:
            if val not in fid_map:
                raise ExtensionError(
                    f"unmapped local FormID 0x{val:08X} in {rec.sig.decode()} 0x{rec.fid:08X}.{sig.decode()}"
                )
            struct.pack_into("<I", buf, off, fid_map[val])
    return bytes(buf)


def remap_record_subrecords(
    rec: RawRecord,
    fid_map: Dict[int, int],
    local_prefix: int,
    new_fid: int,
    override_ltmp: Optional[int] = None,
    extra_flags: int = 0,
) -> RawRecord:
    """Clone rec with new_fid, remapped local FormID references, optional CELL LTMP fix, and optional flags."""
    ref_subs = FORMID_SUBRECORDS.get(rec.sig, set())
    subs: List[Tuple[bytes, bytes]] = []
    saw_ltmp = False
    for sig, payload in iter_subrecords(rec.decompressed_body()):
        if sig in ref_subs and len(payload) >= 4:
            payload = _remap_fid_in_payload(sig, payload, fid_map, local_prefix, rec)
        elif rec.sig == b"CELL" and sig == b"LTMP" and override_ltmp is not None and len(payload) == 4:
            payload = struct.pack("<I", override_ltmp)
            saw_ltmp = True
        subs.append((sig, payload))
    if rec.sig == b"CELL" and override_ltmp is not None and not saw_ltmp:
        subs.append((b"LTMP", struct.pack("<I", override_ltmp)))
    new_body = pack_subrecords(subs)
    new_flags = rec.flags | extra_flags
    if new_flags & COMPRESSED_FLAG:
        raw_body = struct.pack("<I", len(new_body)) + zlib.compress(new_body)
    else:
        raw_body = new_body
    return RawRecord(rec.sig, new_flags, new_fid, rec.revision, rec.version, rec.unknown, raw_body)


def extract_local_refs(rec: RawRecord, local_prefix: int) -> List[int]:
    """Return local FormIDs referenced by rec's known FormID-bearing subrecords."""
    out: List[int] = []
    ref_subs = FORMID_SUBRECORDS.get(rec.sig, set())
    for sig, payload in iter_subrecords(rec.decompressed_body()):
        if sig not in ref_subs or len(payload) < 4:
            continue
        offsets: Tuple[int, ...]
        if sig == b"XLKR" and len(payload) >= 8:
            offsets = (0, 4)
        elif sig == b"XLOC" and len(payload) >= 8:
            offsets = (4,)
        else:
            offsets = (0,)
        for off in offsets:
            val = struct.unpack_from("<I", payload, off)[0]
            if (val >> 24) == local_prefix:
                out.append(val)
    return out


def pack_xloc(
    level: int,
    key_fid: int = 0,
    flags: int = STARFIELD_XLOC_FLAG_LOCKED,
) -> bytes:
    """Pack a 16-byte Starfield REFR.XLOC lock subrecord."""
    return struct.pack("<B3sIB7s", level & 0xFF, b"\x00\x00\x00", key_fid, flags & 0xFF, b"\x00" * 7)


def pack_xlkr(target_ref_fid: int, keyword_fid: int = 0) -> bytes:
    """Pack an 8-byte Starfield REFR.XLKR linked-reference subrecord."""
    return struct.pack("<II", keyword_fid, target_ref_fid)


def with_refr_lock_and_link(
    rec: RawRecord,
    *,
    lock_level: Optional[int] = None,
    lock_flags: int = STARFIELD_XLOC_FLAG_LOCKED,
    linked_ref_fid: Optional[int] = None,
    persistent: bool = False,
) -> RawRecord:
    """Return rec updated with optional persistence, Starfield XLOC lock, and XLKR link right before DATA."""
    subs: List[Tuple[bytes, bytes]] = []
    inserted = False
    extra_subs: List[Tuple[bytes, bytes]] = []
    if linked_ref_fid is not None:
        extra_subs.append((b"XLKR", pack_xlkr(linked_ref_fid)))
    if lock_level is not None:
        extra_subs.append((b"XLOC", pack_xloc(lock_level, flags=lock_flags)))

    for sig, payload in iter_subrecords(rec.decompressed_body()):
        if (lock_level is not None and sig == b"XLOC") or (linked_ref_fid is not None and sig == b"XLKR"):
            continue
        if sig == b"DATA" and not inserted and extra_subs:
            subs.extend(extra_subs)
            inserted = True
        subs.append((sig, payload))
    if not inserted and extra_subs:
        subs.extend(extra_subs)

    new_body = pack_subrecords(subs)
    new_flags = rec.flags | (PERSISTENT_FLAG if persistent else 0)
    if new_flags & COMPRESSED_FLAG:
        raw_body = struct.pack("<I", len(new_body)) + zlib.compress(new_body)
    else:
        raw_body = new_body
    return RawRecord(rec.sig, new_flags, rec.fid, rec.revision, rec.version, rec.unknown, raw_body)


def make_museum_door_refr(
    fid: int,
    edid: str,
    base_fid: int,
    pos_m: Tuple[float, float, float],
    rot_rad: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    lock_level: Optional[int] = None,
    persistent: bool = True,
) -> RawRecord:
    """Create a synthetic persistent Starfield DOOR REFR inside FO4Port_ConcordMuseum01."""
    subs: List[Tuple[bytes, bytes]] = [
        (b"EDID", edid.encode("ascii") + b"\x00"),
        (b"NAME", struct.pack("<I", base_fid)),
    ]
    if lock_level is not None:
        subs.append((b"XLOC", pack_xloc(lock_level)))
    subs.append((b"DATA", struct.pack("<6f", *pos_m, *rot_rad)))
    flags = PERSISTENT_FLAG if persistent else 0
    return RawRecord(b"REFR", flags, fid, 0, 576, 0, pack_subrecords(subs))


def refr_pos(rec: RawRecord) -> Optional[Tuple[float, float, float]]:
    for sig, payload in iter_subrecords(rec.decompressed_body()):
        if sig == b"DATA" and len(payload) >= 24:
            x, y, z = struct.unpack_from("<3f", payload, 0)
            return (float(x), float(y), float(z))
    return None


def refr_name(rec: RawRecord) -> Optional[int]:
    for sig, payload in iter_subrecords(rec.decompressed_body()):
        if sig == b"NAME" and len(payload) == 4:
            return struct.unpack("<I", payload)[0]
    return None


# ---------------------------------------------------------------------------
# Interior FO4 NAVM -> Starfield v17 NAVM + NAVI conversion
# ---------------------------------------------------------------------------
def read_fo4_interior_navm_and_doors(
    fo4_esm: Path,
    fo4_cell_fid: int = FO4_MUSEUM_CELL_FID,
    fo4_navm_fid: int = FO4_MUSEUM_NAVM_FID,
) -> Tuple[bytes, Dict[int, Tuple[float, float, float]]]:
    """Read FO4 interior NAVM raw NVNM subrecord and door REFR positions (in metres) from Fallout4.esm."""
    data = fo4_esm.read_bytes()
    tsize = struct.unpack_from("<I", data, 4)[0]
    pos = 24 + tsize
    n = len(data)
    nvnm_raw: Optional[bytes] = None
    door_positions_m: Dict[int, Tuple[float, float, float]] = {}

    while pos < n:
        sig = data[pos : pos + 4]
        if sig == b"GRUP":
            gsize = struct.unpack_from("<I", data, pos + 4)[0]
            label = data[pos + 8 : pos + 12]
            if label == b"CELL":
                def _find(s: int, e: int, in_cell: bool = False) -> None:
                    nonlocal nvnm_raw
                    p = s
                    while p < e:
                        rsig = data[p : p + 4]
                        if rsig == b"GRUP":
                            gs = struct.unpack_from("<I", data, p + 4)[0]
                            gt = struct.unpack_from("<I", data, p + 12)[0]
                            gl = struct.unpack_from("<I", data, p + 8)[0]
                            _find(p + 24, p + gs, in_cell or (gt == 6 and gl == fo4_cell_fid))
                            p += gs
                        else:
                            rs, fl, fid = struct.unpack_from("<III", data, p + 4)
                            if in_cell:
                                body = data[p + 24 : p + 24 + rs]
                                ub = zlib.decompress(body[4:]) if (fl & COMPRESSED_FLAG) else body
                                if rsig == b"NAVM" and fid == fo4_navm_fid:
                                    for ss, sp in iter_subrecords(ub):
                                        if ss == b"NVNM":
                                            nvnm_raw = sp
                                            break
                                elif rsig == b"REFR":
                                    for ss, sp in iter_subrecords(ub):
                                        if ss == b"DATA" and len(sp) >= 24:
                                            x, y, z = struct.unpack_from("<3f", sp, 0)
                                            door_positions_m[fid] = (
                                                x / UNITS_PER_METRE,
                                                y / UNITS_PER_METRE,
                                                z / UNITS_PER_METRE,
                                            )
                                            break
                            p += 24 + rs

                _find(pos + 24, pos + gsize)
                break
            pos += gsize
        else:
            rsize = struct.unpack_from("<I", data, pos + 4)[0]
            pos += 24 + rsize

    if nvnm_raw is None:
        raise ExtensionError(f"FO4 NAVM 0x{fo4_navm_fid:08X} not found in CELL 0x{fo4_cell_fid:08X} of {fo4_esm}")
    return nvnm_raw, door_positions_m


def convert_interior_fo4_navm(
    fo4_nvnm_raw: bytes,
    fo4_navm_fid: int,
    new_navm_fid: int,
    new_cell_fid: int,
    fo4_door_positions_m: Dict[int, Tuple[float, float, float]],
    sf_door_refs: Sequence[Tuple[int, Tuple[float, float, float]]],
    door_match_tol_m: float = 0.25,
) -> Tuple[navm.Nvnm, navm.Nvmi, dict]:
    """Convert a Fallout 4 v15 interior NVNM into Starfield v17 NVNM + NVMI and run full validation."""
    fo4 = navm.parse(fo4_nvnm_raw, layout="fo4")
    if fo4.world != 0:
        raise ExtensionError(f"expected interior FO4 NAVM (world=0), got world=0x{fo4.world:08X}")

    sf_verts = (fo4.vertices / UNITS_PER_METRE).astype(np.float32).astype(np.float64)
    nt = len(fo4.triangles)
    sf_tris = fo4.triangles.copy()

    # Scale triangle ceiling heights from FO4 units to metres, keeping FLT_MAX intact.
    heights = sf_tris["height"].astype(np.float64)
    finite_mask = heights < navm.NO_CEILING
    heights[finite_mask] = heights[finite_mask] / UNITS_PER_METRE
    sf_tris["height"] = np.where(finite_mask, heights.astype(np.float32), np.float32(navm.FLT_MAX))
    # Clear FO4 cover bits since Starfield cover entries are 12 B (omitted cleanly as in make_exp2d).
    sf_tris["cover"] = 0

    # Keep only internal/self-links (remap target navmesh ID to new_navm_fid); strip any external links cleanly.
    link_remap: Dict[int, int] = {}
    kept_links = []
    for idx, row in enumerate(fo4.links):
        if int(row["navmesh"]) == fo4_navm_fid:
            link_remap[idx] = len(kept_links)
            kept_links.append((int(row["type"]), new_navm_fid, int(row["tri"]), int(row["edge"])))
    sf_links = np.zeros(len(kept_links), navm.LINK_DTYPE)
    for i, item in enumerate(kept_links):
        sf_links[i] = item

    # Update triangle edges/flags and compute Starfield open-boundary vertex_extra flags.
    vertex_extra = np.zeros(len(sf_verts), np.int32)
    for ti in range(nt):
        fl = int(sf_tris["flags"][ti])
        vv = sf_tris["v"][ti]
        for k in range(3):
            bit = navm.EDGE_LINK_BITS[k]
            e = int(sf_tris["e"][ti][k])
            if fl & bit:
                if e in link_remap:
                    sf_tris["e"][ti][k] = link_remap[e]
                else:
                    fl &= ~bit
                    sf_tris["e"][ti][k] = -1
                    vertex_extra[int(vv[k])] = 1
                    vertex_extra[int(vv[(k + 1) % 3])] = 1
            elif e == -1:
                vertex_extra[int(vv[k])] = 1
                vertex_extra[int(vv[(k + 1) % 3])] = 1
        sf_tris["flags"][ti] = fl

    # Match FO4 door triangles to remapped Starfield DOOR REFRs by 3D proximity.
    matched_doors: List[Tuple[int, int, int]] = []
    door_match_report: List[dict] = []
    for row in fo4.doors:
        tri_idx = int(row["tri"])
        extra = int(row["extra"])
        fo4_door_fid = int(row["door"])
        target_pos = fo4_door_positions_m.get(fo4_door_fid) or FO4_MUSEUM_NAVM_DOOR_FALLBACKS.get(fo4_door_fid)
        best: Optional[Tuple[float, int, Tuple[float, float, float]]] = None
        if target_pos is not None:
            for sf_rfid, sf_pos in sf_door_refs:
                d = math.dist(target_pos, sf_pos)
                if best is None or d < best[0]:
                    best = (d, sf_rfid, sf_pos)
        if best is not None and best[0] <= door_match_tol_m:
            matched_doors.append((tri_idx, extra, best[1]))
            door_match_report.append(
                {
                    "tri": tri_idx,
                    "fo4_door_fid": f"0x{fo4_door_fid:08X}",
                    "sf_door_fid": f"0x{best[1]:08X}",
                    "distance_m": round(best[0], 5),
                    "pos_m": [round(c, 3) for c in best[2]],
                }
            )
        else:
            # Unmatched door triangle: clear F_DOOR flag cleanly so validate() stays error-free.
            sf_tris["flags"][tri_idx] &= ~navm.F_DOOR

    sf_doors = np.zeros(len(matched_doors), navm.DOOR_DTYPE)
    for i, item in enumerate(matched_doors):
        sf_doors[i] = item

    # Scale waypoints from FO4 units to metres.
    sf_wps = fo4.waypoints.copy()
    if len(sf_wps):
        sf_wps["pos"] = (sf_wps["pos"].astype(np.float64) / UNITS_PER_METRE).astype(np.float32)

    div, gsize, gmin, gmax, glists = navm.build_grid(sf_verts, sf_tris)
    sf_nvnm = navm.Nvnm(
        version=navm.SF_VERSION,
        magic=navm.MAGIC,
        world=0,
        grid=None,
        cell=new_cell_fid,
        vertices=sf_verts,
        vertex_extra=vertex_extra,
        triangles=sf_tris,
        links=sf_links,
        doors=sf_doors,
        cover=[],
        cover_map=np.zeros(0, navm.COVERMAP_DTYPE),
        waypoints=sf_wps,
        grid_divisor=div,
        grid_size=gsize,
        grid_min=gmin,
        grid_max=gmax,
        grid_lists=glists,
        trailer=navm.SF_TRAILER,
    )

    # Build matching interior NVMI entry (world=0, grid=None, cell=new_cell_fid, border=0).
    loc = tuple(float(x) for x in sf_verts.astype(np.float32).mean(0, dtype=np.float32))
    merged = [new_navm_fid] if len(sf_links) else []
    nvmi_doors = [(int(d["extra"]), int(d["door"])) for d in sf_doors]
    sf_nvmi = navm.Nvmi(
        navmesh=new_navm_fid,
        flags=0,
        location=loc,
        unknown_f=0.0,
        merged=merged,
        preferred=[],
        doors=nvmi_doors,
        traversals=[],
        outline=None,
        world=0,
        grid=None,
        cell=new_cell_fid,
        border=0,
    )

    # Round-trip parse & validate both NVNM and NVMI!
    # Interior FO4 navmeshes contain paired drop-down ledge links (type 1/2, dz up to ~3.0 m, gap up to ~3.5 m);
    # enforce strict 0.5 m tolerance for flat portals (type 0) and 4.0 m for drop-down ledge links (type 1/2).
    nvnm_bytes = navm.write_sf(sf_nvnm)
    nvmi_bytes = navm.write_nvmi(sf_nvmi)
    rt_nvnm = navm.parse(nvnm_bytes, layout="sf")
    rt_nvmi = navm.parse_nvmi(nvmi_bytes)
    has_ledge_links = any(int(row["type"]) in (1, 2) for row in rt_nvnm.links)
    val = navm.validate(
        {new_navm_fid: rt_nvnm},
        {new_navm_fid: rt_nvmi},
        world=0,
        portal_tol=4.0 if has_ledge_links else 0.5,
    )
    if val["errors"]:
        raise ExtensionError(f"converted interior NAVM failed validation: {val['errors'][:5]}")

    # Verify walkability across all matched doors via triangle_path (e.g. Front -> 2F Balcony -> 3F Roof).
    door_paths: List[dict] = []
    if len(matched_doors) >= 2:
        for i in range(len(matched_doors)):
            for j in range(i + 1, len(matched_doors)):
                t_a, _, fid_a = matched_doors[i]
                t_b, _, fid_b = matched_doors[j]
                path = navm.triangle_path({new_navm_fid: rt_nvnm}, (new_navm_fid, t_a), (new_navm_fid, t_b))
                door_paths.append(
                    {
                        "from_door": f"0x{fid_a:08X}",
                        "from_tri": t_a,
                        "to_door": f"0x{fid_b:08X}",
                        "to_tri": t_b,
                        "reachable": path is not None,
                        "hops": len(path) if path is not None else -1,
                    }
                )

    info = {
        "fo4_navm_fid": f"0x{fo4_navm_fid:08X}",
        "sf_navm_fid": f"0x{new_navm_fid:08X}",
        "sf_cell_fid": f"0x{new_cell_fid:08X}",
        "vertices": len(rt_nvnm.vertices),
        "triangles": len(rt_nvnm.triangles),
        "links": len(rt_nvnm.links),
        "links_symmetric": val["links_symmetric"],
        "internal_edges": val["internal_edges"],
        "open_edges": val["open_edges"],
        "doors": door_match_report,
        "waypoints": len(rt_nvnm.waypoints),
        "grid_divisor": rt_nvnm.grid_divisor,
        "nvnm_bytes": len(nvnm_bytes),
        "nvmi_bytes": len(nvmi_bytes),
        "validation_errors": len(val["errors"]),
        "door_paths": door_paths,
        "bounds_min_m": [round(float(x), 3) for x in rt_nvnm.grid_min],
        "bounds_max_m": [round(float(x), 3) for x in rt_nvnm.grid_max],
    }
    return rt_nvnm, rt_nvmi, info


def build_navm_record(navm_fid: int, nvnm: navm.Nvnm, version: int = 581) -> RawRecord:
    body = pack_subrecords([(b"NVNM", navm.write_sf(nvnm)), (b"MNAM", b"")])
    return RawRecord(b"NAVM", 0, navm_fid, 0, version, 0, body)


def build_navi_record(nvmis: Sequence[navm.Nvmi], version: int = 581) -> RawRecord:
    subs: List[Tuple[bytes, bytes]] = [(b"NVER", struct.pack("<I", navm.SF_VERSION))]
    for item in nvmis:
        subs.append((b"NVMI", navm.write_nvmi(item)))
    subs.append((b"NVPP", b"\x00" * 8))
    body = pack_subrecords(subs)
    return RawRecord(b"NAVI", 0, NAVI_FID, 0, version, 0, body)


def parse_flat_grup_records(payload: bytes) -> List[RawRecord]:
    """Parse sequential RawRecords from a non-hierarchical top-level GRUP payload."""
    out: List[RawRecord] = []
    pos, n = 0, len(payload)
    while pos < n:
        if pos + 24 > n:
            raise ExtensionError(f"truncated record header inside GRUP payload at {pos}")
        sig = payload[pos : pos + 4]
        if sig == b"GRUP":
            raise ExtensionError(f"unexpected nested GRUP inside flat GRUP payload at {pos}")
        rsize, flags, fid, rev, ver, unk = struct.unpack_from("<IIIIHH", payload, pos + 4)
        if pos + 24 + rsize > n:
            raise ExtensionError(f"truncated record {sig!r} 0x{fid:08X} in GRUP payload at {pos}")
        out.append(RawRecord(sig, flags, fid, rev, ver, unk, payload[pos + 24 : pos + 24 + rsize]))
        pos += 24 + rsize
    return out


def merge_navi_record(base_navi: RawRecord, extra_nvmis: Sequence[navm.Nvmi]) -> Tuple[RawRecord, int]:
    """Losslessly merge extra NVMI entries into an existing NAVI 0x00000FF1 record.

    Preserves every base NVER, NVMI, NVPP, and NVSI subrecord byte-for-byte in order,
    inserting new NVMI entries directly before NVPP/NVSI.
    """
    base_subs = iter_subrecords(base_navi.decompressed_body())
    existing_navm_fids: Set[int] = set()
    prefix_subs: List[Tuple[bytes, bytes]] = []
    suffix_subs: List[Tuple[bytes, bytes]] = []
    in_suffix = False
    for ss, sp in base_subs:
        if not in_suffix and ss in (b"NVPP", b"NVSI"):
            in_suffix = True
        if in_suffix:
            suffix_subs.append((ss, sp))
        else:
            if ss == b"NVMI":
                existing_navm_fids.add(navm.parse_nvmi(sp).navmesh)
            prefix_subs.append((ss, sp))

    added_subs: List[Tuple[bytes, bytes]] = []
    for item in extra_nvmis:
        if item.navmesh in existing_navm_fids:
            raise ExtensionError(
                f"Museum NAVM 0x{item.navmesh:08X} already exists in base NAVI 0x{base_navi.fid:08X}"
            )
        added_subs.append((b"NVMI", navm.write_nvmi(item)))

    merged_body = pack_subrecords(prefix_subs + added_subs + suffix_subs)
    merged_rec = RawRecord(
        base_navi.sig,
        base_navi.flags & ~COMPRESSED_FLAG,
        base_navi.fid,
        base_navi.revision,
        base_navi.version,
        base_navi.unknown,
        merged_body,
    )
    return merged_rec, len(added_subs)


def wrap_grup(label: bytes, gtype: int, payload: bytes) -> bytes:
    return struct.pack("<4sI4sIII", b"GRUP", 24 + len(payload), label, gtype, 0, 0) + payload


def wrap_cell_entry(
    cell_rec: RawRecord,
    persistent: Sequence[RawRecord],
    temporary: Sequence[RawRecord],
) -> bytes:
    """Wrap one interior CELL and its persistent(8)/temporary(9) children in block(2)/subblock(3) GRUPs."""
    local_id = cell_rec.fid & 0x00FFFFFF
    block = local_id % 10
    subblock = (local_id // 10) % 10
    children_chunks: List[bytes] = []
    if persistent:
        p_payload = b"".join(r.to_bytes() for r in persistent)
        children_chunks.append(wrap_grup(struct.pack("<I", cell_rec.fid), 8, p_payload))
    if temporary:
        t_payload = b"".join(r.to_bytes() for r in temporary)
        children_chunks.append(wrap_grup(struct.pack("<I", cell_rec.fid), 9, t_payload))
    cell_block = cell_rec.to_bytes()
    if children_chunks:
        cell_block += wrap_grup(struct.pack("<I", cell_rec.fid), 6, b"".join(children_chunks))
    sub_grup = wrap_grup(struct.pack("<i", subblock), 3, cell_block)
    return wrap_grup(struct.pack("<i", block), 2, sub_grup)


# ---------------------------------------------------------------------------
# Lossless ESM Extension Core & Strict Self-Verifier
# ---------------------------------------------------------------------------
def extend_fo4port_esm(
    base_esm_bytes: bytes,
    source_esm_bytes: bytes,
    target_cells: Sequence[str] = DEFAULT_CELLS,
    start_id: int = DEFAULT_START_ID,
    museum_navm_input: Optional[Tuple[bytes, int, Dict[int, Tuple[float, float, float]]]] = None,
    museum_cell_edid: str = "FO4Port_ConcordMuseum01",
    expected_base_sha256: Optional[str] = None,
) -> Tuple[bytes, dict]:
    """Losslessly append target_cells + net-new transitive records + optional Museum NAVM onto base_esm_bytes."""
    base_sha256 = hashlib.sha256(base_esm_bytes).hexdigest()
    if expected_base_sha256 is not None and base_sha256.lower() != expected_base_sha256.lower():
        raise ExtensionError(
            f"base FO4Port.esm sha256 mismatch: got {base_sha256}, want {expected_base_sha256}"
        )
    tes4, top_grups = parse_top_level(base_esm_bytes)
    local_prefix = get_master_count(tes4)

    base_records = [r for r in walk_all_records(base_esm_bytes) if r.sig != b"TES4"]
    base_by_fid: Dict[int, RawRecord] = {}
    base_by_sig_edid: Dict[Tuple[bytes, str], int] = {}
    max_base_local = 0
    for rec in base_records:
        base_by_fid[rec.fid] = rec
        if (rec.fid >> 24) == local_prefix:
            max_base_local = max(max_base_local, rec.fid & 0x00FFFFFF)
        edid = get_edid(rec)
        if edid:
            base_by_sig_edid[(rec.sig, edid)] = rec.fid

    if start_id <= max_base_local:
        raise ExtensionError(
            f"start_id 0x{start_id:06X} must be strictly greater than base max local ID 0x{max_base_local:06X}"
        )

    src_by_fid, src_cells = parse_source_esm(source_esm_bytes)
    missing_cells = [c for c in target_cells if c not in src_cells]
    if missing_cells:
        raise ExtensionError(f"target cells not found in source ESM: {missing_cells}")
    already_present = [c for c in target_cells if (b"CELL", c) in base_by_sig_edid]
    if already_present:
        raise ExtensionError(f"target cells already exist in base ESM: {already_present}")

    # Collect transitive closure of local FormIDs referenced by target cells + their REFRs.
    needed_src_fids: Set[int] = set()
    queue: List[int] = []
    for cname in target_cells:
        pc = src_cells[cname]
        for ref_fid in extract_local_refs(pc.cell_rec, local_prefix):
            if ref_fid not in needed_src_fids:
                needed_src_fids.add(ref_fid)
                queue.append(ref_fid)
        for refr in pc.persistent + pc.temporary:
            for ref_fid in extract_local_refs(refr, local_prefix):
                if ref_fid not in needed_src_fids:
                    needed_src_fids.add(ref_fid)
                    queue.append(ref_fid)

    while queue:
        cur = queue.pop()
        rec = src_by_fid.get(cur)
        if rec is None:
            raise ExtensionError(f"dangling source local FormID 0x{cur:08X}")
        for dep in extract_local_refs(rec, local_prefix):
            if dep not in needed_src_fids:
                needed_src_fids.add(dep)
                queue.append(dep)

    # Map reused records to existing base FormIDs; sort net-new records deterministically.
    fid_map: Dict[int, int] = {}
    reused_records: List[dict] = []
    net_new_src_fids: List[int] = []
    for sfid in sorted(needed_src_fids):
        rec = src_by_fid[sfid]
        edid = get_edid(rec)
        existing = base_by_sig_edid.get((rec.sig, edid)) if edid else None
        if existing is not None:
            fid_map[sfid] = existing
            reused_records.append(
                {
                    "sig": rec.sig.decode("ascii"),
                    "edid": edid,
                    "source_fid": f"0x{sfid:08X}",
                    "reused_base_fid": f"0x{existing:08X}",
                    "body_differs_preserved_base": (
                        rec.decompressed_body() != base_by_fid[existing].decompressed_body()
                    ),
                }
            )
        else:
            net_new_src_fids.append(sfid)

    next_local = start_id

    def alloc_fid() -> int:
        nonlocal next_local
        fid = (local_prefix << 24) | next_local
        next_local += 1
        return fid

    # Deterministic allocation order for net-new base records: grouped by TOP_GRUP_ORDER then (edid, src_fid).
    sig_rank = {sig: i for i, sig in enumerate(TOP_GRUP_ORDER)}
    net_new_src_fids.sort(
        key=lambda f: (sig_rank.get(src_by_fid[f].sig, 999), src_by_fid[f].sig, get_edid(src_by_fid[f]), f)
    )
    for sfid in net_new_src_fids:
        fid_map[sfid] = alloc_fid()

    # Allocate FormIDs for each target CELL and its persistent + temporary REFRs.
    cell_alloc_info: Dict[str, dict] = {}
    for cname in target_cells:
        pc = src_cells[cname]
        new_cfid = alloc_fid()
        fid_map[pc.cell_rec.fid] = new_cfid
        pers_new: List[Tuple[int, int]] = []
        temp_new: List[Tuple[int, int]] = []
        for refr in pc.persistent:
            nfid = alloc_fid()
            fid_map[refr.fid] = nfid
            pers_new.append((refr.fid, nfid))
        for refr in pc.temporary:
            nfid = alloc_fid()
            fid_map[refr.fid] = nfid
            temp_new.append((refr.fid, nfid))
        cell_alloc_info[cname] = {
            "source_cell_fid": f"0x{pc.cell_rec.fid:08X}",
            "new_cell_fid": f"0x{new_cfid:08X}",
            "new_cell_fid_int": new_cfid,
            "persistent_count": len(pers_new),
            "persistent_fids": [f"0x{nf:08X}" for _, nf in pers_new],
            "temporary_count": len(temp_new),
        }

    # Build remapped net-new base records grouped by top-level signature.
    appended_by_sig: Dict[bytes, List[RawRecord]] = defaultdict(list)
    new_record_table: List[dict] = []
    for sfid in net_new_src_fids:
        src_rec = src_by_fid[sfid]
        nfid = fid_map[sfid]
        remapped = remap_record_subrecords(src_rec, fid_map, local_prefix, nfid)
        appended_by_sig[remapped.sig].append(remapped)
        new_record_table.append(
            {
                "sig": remapped.sig.decode("ascii"),
                "edid": get_edid(remapped),
                "source_fid": f"0x{sfid:08X}",
                "new_fid": f"0x{nfid:08X}",
            }
        )

    # Build remapped target CELLs, their REFRs, and optional Museum NAVM + NAVI.
    appended_cell_bytes: List[bytes] = []
    nvmis_to_emit: List[navm.Nvmi] = []
    navm_report: Optional[dict] = None
    notable_museum_refs: Dict[str, dict] = {}

    for cname in target_cells:
        pc = src_cells[cname]
        new_cfid = fid_map[pc.cell_rec.fid]
        new_cell_rec = remap_record_subrecords(
            pc.cell_rec,
            fid_map,
            local_prefix,
            new_cfid,
            override_ltmp=PROVEN_INTERIOR_LTMP,
        )
        new_pers = [remap_record_subrecords(r, fid_map, local_prefix, fid_map[r.fid]) for r in pc.persistent]
        new_temp = [remap_record_subrecords(r, fid_map, local_prefix, fid_map[r.fid]) for r in pc.temporary]

        # Promote museum gate/terminal/doors/medkit to persistent, add Starfield XLOC + XLKR, & track NAVM doors.
        if cname == museum_cell_edid:
            sf_door_refs: List[Tuple[int, Tuple[float, float, float]]] = []
            # Resolve base sig/edid across base + net-new records
            all_base_info: Dict[int, Tuple[bytes, str]] = {
                fid: (r.sig, get_edid(r)) for fid, r in base_by_fid.items()
            }
            for sig_recs in appended_by_sig.values():
                for r in sig_recs:
                    all_base_info[r.fid] = (r.sig, get_edid(r))

            base_fid_by_edid: Dict[str, int] = {
                edid: fid for fid, (_sig, edid) in all_base_info.items() if edid
            }

            # Locate the basement security gate REFR FID first so the basement terminal XLKR can link to it.
            gate_fid: Optional[int] = None
            for refr in new_pers + new_temp:
                nfid = refr_name(refr)
                _bsig, bedid = all_base_info.get(nfid, (b"", "")) if nfid is not None else (b"", "")
                if bedid == MUSEUM_BASEMENT_GATE_BASE_EDID:
                    gate_fid = refr.fid
                    break

            promoted_gate_fids: List[str] = []
            promoted_persistent_fids: List[str] = []
            synthesized_doors: Dict[str, str] = {}
            kept_temp: List[RawRecord] = []
            updated_pers: List[RawRecord] = []

            def _transform_museum_refr(refr: RawRecord) -> Tuple[RawRecord, bool, bool]:
                """Return (updated_refr, should_promote_to_pers, is_gate)."""
                nfid = refr_name(refr)
                _bsig, bedid = all_base_info.get(nfid, (b"", "")) if nfid is not None else (b"", "")
                pos = refr_pos(refr)
                if bedid == MUSEUM_BASEMENT_GATE_BASE_EDID:
                    return (
                        with_refr_lock_and_link(
                            refr,
                            lock_level=LOCK_LEVEL_NOVICE,
                            persistent=True,
                        ),
                        True,
                        True,
                    )
                if bedid == MUSEUM_BASEMENT_TERM_BASE_EDID:
                    return (
                        with_refr_lock_and_link(
                            refr,
                            lock_level=LOCK_LEVEL_NOVICE,
                            linked_ref_fid=gate_fid,
                            persistent=True,
                        ),
                        True,
                        False,
                    )
                if bedid == MUSEUM_FRONT_DOOR_BASE_EDID:
                    return (
                        with_refr_lock_and_link(refr, persistent=True),
                        True,
                        False,
                    )
                if bedid == MUSEUM_ROOF_DOOR_BASE_EDID:
                    is_balcony = (
                        pos is not None
                        and abs(pos[0] - 12.621) < 0.25
                        and abs(pos[1] - (-0.014)) < 0.25
                        and abs(pos[2] - 9.143) < 0.25
                    )
                    return (
                        with_refr_lock_and_link(
                            refr,
                            lock_level=LOCK_LEVEL_INACCESSIBLE if is_balcony else None,
                            persistent=True,
                        ),
                        True,
                        False,
                    )
                if bedid == MUSEUM_MEDKIT_CONT_BASE_EDID:
                    return (
                        with_refr_lock_and_link(refr, persistent=True),
                        True,
                        False,
                    )
                return (refr, False, False)

            for refr in new_pers:
                upd, _p, is_gate = _transform_museum_refr(refr)
                updated_pers.append(upd)
                if is_gate:
                    promoted_gate_fids.append(f"0x{upd.fid:08X}")
            new_pers = updated_pers

            for refr in new_temp:
                upd, promote, is_gate = _transform_museum_refr(refr)
                if promote:
                    new_pers.append(upd)
                    fstr = f"0x{upd.fid:08X}"
                    promoted_persistent_fids.append(fstr)
                    if is_gate:
                        promoted_gate_fids.append(fstr)
                else:
                    kept_temp.append(upd)
            new_temp = kept_temp

            for refr in new_pers + new_temp:
                nfid = refr_name(refr)
                pos = refr_pos(refr)
                if nfid is None or pos is None:
                    continue
                bsig, bedid = all_base_info.get(nfid, (b"", ""))
                if bsig == b"DOOR":
                    sf_door_refs.append((refr.fid, pos))
                    if bedid in (
                        MUSEUM_FRONT_DOOR_BASE_EDID,
                        MUSEUM_ROOF_DOOR_BASE_EDID,
                        MUSEUM_BASEMENT_GATE_BASE_EDID,
                    ):
                        key = f"{bedid}@{round(pos[0],2)},{round(pos[1],2)},{round(pos[2],2)}"
                        notable_museum_refs[key] = {
                            "new_refr_fid": f"0x{refr.fid:08X}",
                            "base_fid": f"0x{nfid:08X}",
                            "base_edid": bedid,
                            "persistent": bool(refr.flags & PERSISTENT_FLAG),
                            "pos_m": [round(c, 3) for c in pos],
                        }
                elif bedid in (MUSEUM_BASEMENT_TERM_BASE_EDID, MUSEUM_MEDKIT_CONT_BASE_EDID):
                    key = f"{bedid}@{round(pos[0],2)},{round(pos[1],2)},{round(pos[2],2)}"
                    notable_museum_refs[key] = {
                        "new_refr_fid": f"0x{refr.fid:08X}",
                        "base_fid": f"0x{nfid:08X}",
                        "base_edid": bedid,
                        "persistent": bool(refr.flags & PERSISTENT_FLAG),
                        "pos_m": [round(c, 3) for c in pos],
                    }

            if museum_navm_input is not None:
                fo4_nvnm_raw, fo4_navm_fid, fo4_door_pos = museum_navm_input
                new_navm_fid = alloc_fid()
                sf_nvnm, sf_nvmi, navm_report = convert_interior_fo4_navm(
                    fo4_nvnm_raw=fo4_nvnm_raw,
                    fo4_navm_fid=fo4_navm_fid,
                    new_navm_fid=new_navm_fid,
                    new_cell_fid=new_cfid,
                    fo4_door_positions_m=fo4_door_pos,
                    sf_door_refs=sf_door_refs,
                )
                navm_rec = build_navm_record(new_navm_fid, sf_nvnm)
                # Place NAVM first in temporary children GRUP(9), matching Starfield.esm interior convention.
                new_temp = [navm_rec] + new_temp
                nvmis_to_emit.append(sf_nvmi)
                cell_alloc_info[cname]["navm_fid"] = f"0x{new_navm_fid:08X}"

            # Append persistent 3F quest doors omitted by interiors_b10 AFTER NAVM allocation so existing IDs stay pinned.
            for syn_edid, base_edid, pos_m, rot_rad in (
                ("FO4Port_PrestonDoorREF", PRESTON_DOOR_BASE_EDID, (384.0 / 70.0, -512.0 / 70.0, 640.0 / 70.0), (0.0, 0.0, 0.0)),
                ("FO4Port_PrestonExitDoor", PRESTON_EXIT_DOOR_BASE_EDID, (521.193 / 70.0, 374.80676 / 70.0, 640.0 / 70.0), (0.0, 0.0, 4.712389)),
            ):
                b_fid = base_fid_by_edid.get(base_edid)
                if b_fid is None:
                    continue
                syn_fid = alloc_fid()
                syn_rec = make_museum_door_refr(
                    syn_fid,
                    syn_edid,
                    b_fid,
                    pos_m=pos_m,
                    rot_rad=rot_rad,
                    lock_level=LOCK_LEVEL_INACCESSIBLE,
                    persistent=True,
                )
                new_pers.append(syn_rec)
                synthesized_doors[syn_edid] = f"0x{syn_fid:08X}"
                notable_museum_refs[syn_edid] = {
                    "new_refr_fid": f"0x{syn_fid:08X}",
                    "base_fid": f"0x{b_fid:08X}",
                    "base_edid": base_edid,
                    "persistent": True,
                    "lock_level": LOCK_LEVEL_INACCESSIBLE,
                    "pos_m": [round(c, 3) for c in pos_m],
                }

            cell_alloc_info[cname]["persistent_count"] = len(new_pers)
            cell_alloc_info[cname]["persistent_fids"] = [f"0x{r.fid:08X}" for r in new_pers]
            cell_alloc_info[cname]["temporary_count"] = len(new_temp)
            cell_alloc_info[cname]["ltmp"] = f"0x{PROVEN_INTERIOR_LTMP:08X}"
            if promoted_gate_fids:
                cell_alloc_info[cname]["promoted_persistent_gate_fids"] = promoted_gate_fids
            if promoted_persistent_fids:
                cell_alloc_info[cname]["promoted_persistent_fids"] = promoted_persistent_fids
            if synthesized_doors:
                cell_alloc_info[cname]["synthesized_doors"] = synthesized_doors
        else:
            cell_alloc_info[cname]["ltmp"] = f"0x{PROVEN_INTERIOR_LTMP:08X}"

        appended_cell_bytes.append(wrap_cell_entry(new_cell_rec, new_pers, new_temp))

    # Assemble output top-level GRUPs: preserve every existing GRUP payload verbatim at its prefix,
    # and losslessly merge Museum NVMIs into existing NAVI 0x00000FF1 when NAVI already exists in base!
    out_grups: List[TopGrup] = []
    seen_labels: Set[bytes] = set()
    for tg in top_grups:
        seen_labels.add(tg.label)
        base_payload = tg.payload
        extra_payload = b""
        if tg.label == b"NAVI" and nvmis_to_emit:
            navi_recs = parse_flat_grup_records(tg.payload)
            out_navi_recs: List[RawRecord] = []
            merged_existing_navi = False
            for nrec in navi_recs:
                if nrec.fid == NAVI_FID and nrec.sig == b"NAVI" and not merged_existing_navi:
                    merged_rec, _ = merge_navi_record(nrec, nvmis_to_emit)
                    out_navi_recs.append(merged_rec)
                    merged_existing_navi = True
                else:
                    out_navi_recs.append(nrec)
            if not merged_existing_navi:
                out_navi_recs.append(build_navi_record(nvmis_to_emit))
            base_payload = b"".join(r.to_bytes() for r in out_navi_recs)
        elif tg.label == b"CELL":
            extra_payload = b"".join(appended_cell_bytes)
        elif tg.label in appended_by_sig:
            extra_payload = b"".join(r.to_bytes() for r in appended_by_sig[tg.label])
        out_grups.append(TopGrup(tg.label, tg.gtype, tg.stamp, tg.unknown, base_payload + extra_payload))

    # Append any top-level GRUPs not present in base (e.g. NAVI or any net-new sig).
    for sig in TOP_GRUP_ORDER:
        if sig in seen_labels:
            continue
        if sig == b"CELL" and appended_cell_bytes:
            out_grups.append(TopGrup(b"CELL", 0, 0, 0, b"".join(appended_cell_bytes)))
        elif sig == b"NAVI" and nvmis_to_emit:
            navi_rec = build_navi_record(nvmis_to_emit)
            out_grups.append(TopGrup(b"NAVI", 0, 0, 0, navi_rec.to_bytes()))
        elif sig in appended_by_sig:
            out_grups.append(TopGrup(sig, 0, 0, 0, b"".join(r.to_bytes() for r in appended_by_sig[sig])))

    # Assemble provisional ESM to compute exact HEDR record+GRUP count, then finalize TES4.
    body_bytes = b"".join(g.to_bytes() for g in out_grups)
    provisional = tes4.to_bytes() + body_bytes
    nrec_total = count_records_and_grups(provisional)
    new_tes4 = update_tes4_hedr(tes4, nrec_total, next_local)
    out_bytes = new_tes4.to_bytes() + body_bytes

    # Strict lossless self-verification!
    verify_report = verify_lossless_extension(
        base_esm_bytes=base_esm_bytes,
        out_esm_bytes=out_bytes,
        start_id=start_id,
        expected_new_cells=target_cells,
    )

    for info in cell_alloc_info.values():
        info.pop("new_cell_fid_int", None)

    report = {
        "local_prefix": local_prefix,
        "start_id": f"0x{start_id:06X}",
        "base_max_local_id": f"0x{max_base_local:06X}",
        "next_object_id": f"0x{next_local:06X}",
        "base_size_bytes": len(base_esm_bytes),
        "out_size_bytes": len(out_bytes),
        "base_sha256": hashlib.sha256(base_esm_bytes).hexdigest(),
        "out_sha256": hashlib.sha256(out_bytes).hexdigest(),
        "reused_base_records": len(reused_records),
        "reused_diff_preserved_base": [r for r in reused_records if r["body_differs_preserved_base"]],
        "net_new_base_records": len(new_record_table),
        "net_new_sig_counts": dict(Counter(r["sig"] for r in new_record_table)),
        "cells": cell_alloc_info,
        "notable_museum_refs": notable_museum_refs,
        "museum_navm": navm_report,
        "verification": verify_report,
        "new_base_records_non_stat": [r for r in new_record_table if r["sig"] != "STAT"],
    }
    return out_bytes, report


def verify_lossless_extension(
    base_esm_bytes: bytes,
    out_esm_bytes: bytes,
    start_id: int = DEFAULT_START_ID,
    expected_new_cells: Sequence[str] = (),
) -> dict:
    """Strictly verify out_esm_bytes is a 100% byte-lossless extension of base_esm_bytes.

    Raises ExtensionError on ANY missing base ID, type change, header/body byte change,
    low FormID allocation (< start_id), dangling local reference, or invalid NAVM/NAVI.
    """
    base_tes4, _ = parse_top_level(base_esm_bytes)
    out_tes4, _ = parse_top_level(out_esm_bytes)
    local_prefix = get_master_count(base_tes4)
    if get_master_count(out_tes4) != local_prefix:
        raise ExtensionError("TES4 master count changed during extension")

    base_recs = [r for r in walk_all_records(base_esm_bytes) if r.sig != b"TES4"]
    out_recs = [r for r in walk_all_records(out_esm_bytes) if r.sig != b"TES4"]

    base_map: Dict[int, RawRecord] = {r.fid: r for r in base_recs}
    out_map: Dict[int, RawRecord] = {}
    dup_fids: List[int] = []
    for r in out_recs:
        if r.fid in out_map:
            dup_fids.append(r.fid)
        out_map[r.fid] = r
    if dup_fids:
        raise ExtensionError(f"duplicate FormIDs in output ESM: {[hex(x) for x in dup_fids[:10]]}")

    missing_ids: List[int] = []
    type_changes: List[Tuple[int, bytes, bytes]] = []
    body_changes: List[int] = []
    base_nvmi_raws: List[bytes] = []
    navi_merged = False

    def _verify_merged_navi(brec: RawRecord, orec: RawRecord) -> Tuple[bool, List[bytes]]:
        b_subs = iter_subrecords(brec.decompressed_body())
        o_subs = iter_subrecords(orec.decompressed_body())
        b_pre: List[Tuple[bytes, bytes]] = []
        b_suf: List[Tuple[bytes, bytes]] = []
        in_suf = False
        b_nvmi_list: List[bytes] = []
        for ss, sp in b_subs:
            if not in_suf and ss in (b"NVPP", b"NVSI"):
                in_suf = True
            if in_suf:
                b_suf.append((ss, sp))
            else:
                if ss == b"NVMI":
                    b_nvmi_list.append(sp)
                b_pre.append((ss, sp))
        o_pre: List[Tuple[bytes, bytes]] = []
        o_suf: List[Tuple[bytes, bytes]] = []
        in_suf = False
        for ss, sp in o_subs:
            if not in_suf and ss in (b"NVPP", b"NVSI"):
                in_suf = True
            if in_suf:
                o_suf.append((ss, sp))
            else:
                o_pre.append((ss, sp))
        if o_suf != b_suf:
            return False, b_nvmi_list
        if len(o_pre) < len(b_pre) or o_pre[: len(b_pre)] != b_pre:
            return False, b_nvmi_list
        extra = o_pre[len(b_pre) :]
        if any(ss != b"NVMI" for ss, _ in extra):
            return False, b_nvmi_list
        return True, b_nvmi_list

    for fid, brec in base_map.items():
        orec = out_map.get(fid)
        if orec is None:
            missing_ids.append(fid)
        elif orec.sig != brec.sig:
            type_changes.append((fid, brec.sig, orec.sig))
        elif orec.to_bytes() != brec.to_bytes():
            if fid == NAVI_FID and brec.sig == b"NAVI":
                ok_navi, b_nvmis = _verify_merged_navi(brec, orec)
                if ok_navi:
                    base_nvmi_raws = b_nvmis
                    navi_merged = True
                    continue
            body_changes.append(fid)
        elif fid == NAVI_FID and brec.sig == b"NAVI":
            base_nvmi_raws = [sp for ss, sp in iter_subrecords(brec.decompressed_body()) if ss == b"NVMI"]

    if missing_ids or type_changes or body_changes:
        raise ExtensionError(
            f"lossless invariant violated: missing={len(missing_ids)} "
            f"type_changes={len(type_changes)} body_changes={len(body_changes)}"
        )

    # Check every net-new record allocates local FormID >= start_id (except NAVI override 0x00000FF1).
    net_new_recs = [r for fid, r in out_map.items() if fid not in base_map]
    bad_alloc: List[int] = []
    dangling_refs: List[Tuple[int, int]] = []
    navms: Dict[int, navm.Nvnm] = {}
    nvmis: Dict[int, navm.Nvmi] = {}
    out_nvmi_count = 0
    found_cells: Set[str] = set()

    navi_out = out_map.get(NAVI_FID)
    if navi_out is not None and navi_out.sig == b"NAVI":
        for ss, sp in iter_subrecords(navi_out.decompressed_body()):
            if ss == b"NVMI":
                out_nvmi_count += 1
                e = navm.parse_nvmi(sp)
                nvmis[e.navmesh] = e

    for rec in net_new_recs:
        if rec.sig == b"NAVI" and rec.fid == NAVI_FID:
            continue
        if (rec.fid >> 24) != local_prefix or (rec.fid & 0x00FFFFFF) < start_id:
            bad_alloc.append(rec.fid)
        if rec.sig == b"CELL":
            found_cells.add(get_edid(rec))
        elif rec.sig == b"NAVM":
            for ss, sp in iter_subrecords(rec.decompressed_body()):
                if ss == b"NVNM":
                    navms[rec.fid] = navm.parse(sp, layout="sf")
        for ref in extract_local_refs(rec, local_prefix):
            if ref not in out_map:
                dangling_refs.append((rec.fid, ref))

    if bad_alloc:
        raise ExtensionError(f"net-new FormIDs below start_id 0x{start_id:06X}: {[hex(x) for x in bad_alloc[:10]]}")
    if dangling_refs:
        raise ExtensionError(f"dangling local FormID refs: {[(hex(a), hex(b)) for a, b in dangling_refs[:10]]}")
    missing_cells = [c for c in expected_new_cells if c not in found_cells]
    if missing_cells:
        raise ExtensionError(f"expected appended cells missing from output ESM: {missing_cells}")

    added_nvmi_count = out_nvmi_count - len(base_nvmi_raws)
    if navms:
        missing_museum_nvmis = [nfid for nfid in navms if nfid not in nvmis]
        if missing_museum_nvmis:
            raise ExtensionError(
                f"Museum NAVMs missing NVMI entries in output NAVI: {[hex(x) for x in missing_museum_nvmis]}"
            )
        if added_nvmi_count != len(navms):
            raise ExtensionError(
                f"NVMI count mismatch: base={len(base_nvmi_raws)} + museum={len(navms)} != out={out_nvmi_count}"
            )

    navm_errors = 0
    validate_nvmis = {k: v for k, v in nvmis.items() if k in navms} if navms else None
    if navms:
        has_ledge = any(int(row["type"]) in (1, 2) for m in navms.values() for row in m.links)
        val = navm.validate(navms, validate_nvmis, world=0, portal_tol=4.0 if has_ledge else 0.5)
        navm_errors = len(val["errors"])
        if navm_errors:
            raise ExtensionError(f"output ESM NAVM/NAVI validation failed: {val['errors'][:5]}")

    return {
        "base_non_tes4_records": len(base_map),
        "out_non_tes4_records": len(out_map),
        "net_new_records": len(net_new_recs),
        "missing_base_ids": 0,
        "type_changes": 0,
        "body_changes": 0,
        "dangling_local_refs": 0,
        "navm_count": len(navms),
        "nvmi_count": out_nvmi_count,
        "base_nvmi_count": len(base_nvmi_raws),
        "added_nvmi_count": added_nvmi_count,
        "out_nvmi_count": out_nvmi_count,
        "navi_merged": navi_merged,
        "navm_validation_errors": navm_errors,
        "all_new_local_ids_ge_start_id": True,
    }


# ---------------------------------------------------------------------------
# Minimal Asset & Texture Dependency Tracer + Lossless BA2 v2 Merger
# ---------------------------------------------------------------------------
def _norm_asset(path: str) -> str:
    return path.replace("/", "\\").lower().lstrip("\\")


def trace_cell_asset_delta(
    source_esm_bytes: bytes,
    target_cells: Sequence[str],
    base_main_ba2: Path,
    base_tex_ba2: Path,
    src_main_ba2: Path,
    src_tex_ba2s: Sequence[Path],
) -> dict:
    """Compute the exact minimal Main + Textures asset delta needed by target_cells."""
    src_by_fid, src_cells = parse_source_esm(source_esm_bytes)
    tes4, _ = parse_top_level(source_esm_bytes)
    local_prefix = get_master_count(tes4)

    # Collect all local base forms referenced by target cells (transitive).
    needed_fids: Set[int] = set()
    q: List[int] = []
    for cname in target_cells:
        pc = src_cells[cname]
        for r in [pc.cell_rec] + pc.persistent + pc.temporary:
            for dep in extract_local_refs(r, local_prefix):
                if dep not in needed_fids:
                    needed_fids.add(dep)
                    q.append(dep)
    while q:
        cur = q.pop()
        rec = src_by_fid.get(cur)
        if rec is None:
            continue
        for dep in extract_local_refs(rec, local_prefix):
            if dep not in needed_fids:
                needed_fids.add(dep)
                q.append(dep)

    b00_main = Ba2(str(base_main_ba2))
    b00_tex = Ba2(str(base_tex_ba2))
    b10_main = Ba2(str(src_main_ba2))
    b10_tex_list = [Ba2(str(p)) for p in src_tex_ba2s if p.exists()]

    b10_main_norm = {_norm_asset(n): i for i, n in enumerate(b10_main.names)}
    b10_geo_by_stem = {
        nn[len("geometries\\") : -len(".mesh")]: nn
        for nn in b10_main_norm
        if nn.startswith("geometries\\") and nn.endswith(".mesh")
    }

    # Seed from MODL/MOD2/MOD3/MOD4 + animation graph BNAM/CNAM/ANAM strings.
    seed_main: Set[str] = set()
    for fid in needed_fids:
        rec = src_by_fid.get(fid)
        if rec is None:
            continue
        for ss, sp in iter_subrecords(rec.decompressed_body()):
            if ss in (b"MODL", b"MOD2", b"MOD3", b"MOD4"):
                m = _norm_asset(sp.rstrip(b"\x00").decode("utf-8", "replace"))
                if m and not m.startswith("meshes\\"):
                    m = "meshes\\" + m
                if m:
                    seed_main.add(m)
            elif ss in (b"BNAM", b"CNAM", b"ANAM") and len(sp) > 4:
                s = _norm_asset(sp.rstrip(b"\x00").decode("utf-8", "replace"))
                if "\\" in s:
                    seed_main.add(s)

    expanded_seeds: Set[str] = set()
    for p in seed_main:
        if p in b10_main_norm:
            expanded_seeds.add(p)
        elif ("meshes\\" + p) in b10_main_norm:
            expanded_seeds.add("meshes\\" + p)
        else:
            for pref in (p.rstrip("\\") + "\\", "meshes\\" + p.rstrip("\\") + "\\"):
                for nn in b10_main_norm:
                    if nn.startswith(pref):
                        expanded_seeds.add(nn)

    # BFS through NIF -> .mesh / .mat / .af / .afx / .rig and MAT JSON -> .dds / parent .mat.
    main_needed: Set[str] = set()
    tex_needed: Set[str] = set()
    queue = list(expanded_seeds)
    visited: Set[str] = set()
    while queue:
        cur = queue.pop()
        if cur in visited:
            continue
        visited.add(cur)
        idx = b10_main_norm.get(cur)
        if idx is None:
            continue
        main_needed.add(cur)
        if cur.endswith((".mesh", ".af", ".afx", ".rig")):
            continue
        raw = b10_main.read(idx)
        for m in ASCII_PATH_RE.findall(raw):
            s = _norm_asset(m.decode("latin1").replace("\\\\", "\\"))
            if s.startswith("data\\"):
                s = s[5:]
            if s.endswith(".dds"):
                t = s if s.startswith("textures\\") else ("textures\\" + s)
                tex_needed.add(t)
                continue
            cands = [s]
            if s.endswith(".mat") and not s.startswith("materials\\"):
                cands.append("materials\\" + s)
            if s.endswith(".nif") and not s.startswith("meshes\\"):
                cands.append("meshes\\" + s)
            if s.endswith(".mesh") and not s.startswith("geometries\\"):
                cands.append("geometries\\" + s)
            if s in b10_geo_by_stem:
                cands.append(b10_geo_by_stem[s])
            for c in cands:
                if c in b10_main_norm and c not in visited:
                    queue.append(c)

    b00_main_set = {_norm_asset(n) for n in b00_main.names}
    b00_tex_set = {_norm_asset(n) for n in b00_tex.names}

    delta_main = sorted(main_needed - b00_main_set)
    delta_tex_all = sorted(tex_needed - b00_tex_set)

    # Assign each delta texture to the first source texture BA2 that contains it.
    delta_tex_by_src: Dict[Path, List[str]] = defaultdict(list)
    vanilla_or_missing_tex: List[str] = []
    for t in delta_tex_all:
        found = False
        for src_path, ba2_obj in zip(src_tex_ba2s, b10_tex_list):
            if ba2_obj.find(t) is not None:
                delta_tex_by_src[src_path].append(t)
                found = True
                break
        if not found:
            vanilla_or_missing_tex.append(t)

    return {
        "main_traced_count": len(main_needed),
        "main_reused_count": len(main_needed & b00_main_set),
        "delta_main": delta_main,
        "tex_traced_count": len(tex_needed),
        "tex_reused_count": len(tex_needed & b00_tex_set),
        "delta_tex_by_src": {str(k): v for k, v in delta_tex_by_src.items()},
        "delta_tex_total": sum(len(v) for v in delta_tex_by_src.values()),
        "vanilla_or_missing_tex": vanilla_or_missing_tex,
    }


def _read_ba2_v2_raw_table(path: Path) -> Tuple[str, bytes, List[dict]]:
    """Read raw Starfield BTDX v2 header, entry metadata, and exact stored names for lossless merging."""
    with path.open("rb") as f:
        hdr = f.read(32)
        if len(hdr) != 32:
            raise ExtensionError(f"{path}: truncated BA2 v2 header")
        magic, version, kind_b, count, name_off, ext1, ext2 = struct.unpack("<4sI4sIQII", hdr)
        if magic != b"BTDX" or version != 2:
            raise ExtensionError(f"{path}: expected BTDX v2, got magic={magic!r} v={version}")
        kind = kind_b.decode("ascii")
        extra_hdr = struct.pack("<II", ext1, ext2)

        raw_entries: List[dict] = []
        if kind == "GNRL":
            for _ in range(count):
                rec = f.read(36)
                nh, ext, dh, fl, off, pk, up, al = struct.unpack("<I4sIIQIII", rec)
                raw_entries.append(
                    {
                        "name_hash": nh,
                        "ext": ext,
                        "dir_hash": dh,
                        "flags": fl,
                        "offset": off,
                        "packed": pk,
                        "unpacked": up,
                        "align": al,
                    }
                )
        elif kind == "DX10":
            for _ in range(count):
                rec = f.read(24)
                nh, ext, dh, unk, nch, chsz, hgt, wid, mips, fmt, is_cube, tile = struct.unpack(
                    "<I4sIBBHHHBBBB", rec
                )
                chunks = []
                for _ in range(nch):
                    c = f.read(24)
                    off, pk, up, smip, emip, al = struct.unpack("<QIIHHI", c)
                    chunks.append(
                        {
                            "offset": off,
                            "packed": pk,
                            "unpacked": up,
                            "start_mip": smip,
                            "end_mip": emip,
                            "align": al,
                        }
                    )
                raw_entries.append(
                    {
                        "name_hash": nh,
                        "ext": ext,
                        "dir_hash": dh,
                        "unk": unk,
                        "chunk_hdr_size": chsz,
                        "height": hgt,
                        "width": wid,
                        "mips": mips,
                        "format": fmt,
                        "is_cubemap": is_cube,
                        "tile_mode": tile,
                        "chunks": chunks,
                    }
                )
        else:
            raise ExtensionError(f"{path}: unsupported BA2 kind {kind!r}")

        f.seek(name_off)
        for item in raw_entries:
            slen = struct.unpack("<H", f.read(2))[0]
            item["name"] = f.read(slen).decode("utf-8", "replace")

    return kind, extra_hdr, raw_entries


def merge_ba2_v2_lossless(
    base_ba2: Path,
    delta_sources: Sequence[Tuple[Path, Sequence[str]]],
    out_ba2: Path,
    max_size_bytes: int = ARCHIVE_LIMIT,
) -> dict:
    """Merge base BTDX v2 BA2 with selected delta entries from delta_sources without recompression.

    Copies every existing base entry and every selected delta entry's compressed payload verbatim,
    rewriting only file offsets and the name table, and verifies the resulting archive with fo4sf.ba2.Ba2.
    """
    kind, extra_hdr, base_entries = _read_ba2_v2_raw_table(base_ba2)
    seen_norm: Set[str] = {_norm_asset(e["name"]) for e in base_entries}

    # Plan ordered list of (source_path, entry_dict)
    plan: List[Tuple[Path, dict]] = [(base_ba2, e) for e in base_entries]
    added_count = 0
    added_payload_bytes = 0

    for src_path, wanted_names in delta_sources:
        if not wanted_names:
            continue
        skind, _, src_entries = _read_ba2_v2_raw_table(src_path)
        if skind != kind:
            raise ExtensionError(f"BA2 kind mismatch: base={kind}, delta={skind} ({src_path})")
        by_norm = {_norm_asset(e["name"]): e for e in src_entries}
        for w in wanted_names:
            wn = _norm_asset(w)
            if wn in seen_norm:
                continue
            entry = by_norm.get(wn)
            if entry is None:
                raise ExtensionError(f"delta asset {w!r} not found in {src_path}")
            seen_norm.add(wn)
            plan.append((src_path, entry))
            added_count += 1
            if kind == "GNRL":
                added_payload_bytes += entry["packed"] or entry["unpacked"]
            else:
                added_payload_bytes += sum((c["packed"] or c["unpacked"]) for c in entry["chunks"])

    # Compute exact output layout: 32 B header + entry table + payloads + name table.
    if kind == "GNRL":
        table_size = 36 * len(plan)
    else:
        table_size = sum(24 + 24 * len(e["chunks"]) for _, e in plan)

    payload_offset = 32 + table_size
    new_entries_meta: List[Tuple[Path, dict, object]] = []
    cur_off = payload_offset
    for src_path, entry in plan:
        if kind == "GNRL":
            sz = entry["packed"] or entry["unpacked"]
            new_entries_meta.append((src_path, entry, cur_off))
            cur_off += sz
        else:
            c_offs = []
            for c in entry["chunks"]:
                sz = c["packed"] or c["unpacked"]
                c_offs.append(cur_off)
                cur_off += sz
            new_entries_meta.append((src_path, entry, c_offs))

    name_table_off = cur_off
    encoded_names = [e["name"].encode("utf-8") for _, e in plan]
    total_size = name_table_off + sum(2 + len(b) for b in encoded_names)
    if total_size > max_size_bytes:
        raise ExtensionError(
            f"merged BA2 {out_ba2.name} would be {total_size:,} B, exceeding limit {max_size_bytes:,} B"
        )

    out_ba2.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_ba2.with_suffix(out_ba2.suffix + ".tmp")

    # Open each distinct source BA2 once for streaming copy.
    src_handles = {}
    try:
        for sp, _ in plan:
            if sp not in src_handles:
                src_handles[sp] = sp.open("rb")

        with tmp_path.open("wb") as out:
            # 1. Header
            out.write(
                struct.pack("<4sI4sIQ", b"BTDX", 2, kind.encode("ascii"), len(plan), name_table_off)
                + extra_hdr
            )
            # 2. Entry table
            if kind == "GNRL":
                for _sp, e, new_off in new_entries_meta:
                    out.write(
                        struct.pack(
                            "<I4sIIQIII",
                            e["name_hash"],
                            e["ext"],
                            e["dir_hash"],
                            e["flags"],
                            new_off,
                            e["packed"],
                            e["unpacked"],
                            e["align"],
                        )
                    )
            else:
                for _sp, e, c_offs in new_entries_meta:
                    out.write(
                        struct.pack(
                            "<I4sIBBHHHBBBB",
                            e["name_hash"],
                            e["ext"],
                            e["dir_hash"],
                            e["unk"],
                            len(e["chunks"]),
                            e["chunk_hdr_size"],
                            e["height"],
                            e["width"],
                            e["mips"],
                            e["format"],
                            e["is_cubemap"],
                            e["tile_mode"],
                        )
                    )
                    for c, new_off in zip(e["chunks"], c_offs):
                        out.write(
                            struct.pack(
                                "<QIIHHI",
                                new_off,
                                c["packed"],
                                c["unpacked"],
                                c["start_mip"],
                                c["end_mip"],
                                c["align"],
                            )
                        )
            # 3. Stream raw compressed/uncompressed payloads verbatim
            for sp, e, _offs in new_entries_meta:
                fh = src_handles[sp]
                if kind == "GNRL":
                    sz = e["packed"] or e["unpacked"]
                    fh.seek(e["offset"])
                    _copy_exact(fh, out, sz)
                else:
                    for c in e["chunks"]:
                        sz = c["packed"] or c["unpacked"]
                        fh.seek(c["offset"])
                        _copy_exact(fh, out, sz)
            # 4. Name table
            for nb in encoded_names:
                out.write(struct.pack("<H", len(nb)))
                out.write(nb)
    finally:
        for fh in src_handles.values():
            fh.close()

    os.replace(tmp_path, out_ba2)

    # Validate merged archive with fo4sf.ba2.Ba2!
    checked = Ba2(str(out_ba2))
    if len(checked.entries) != len(plan):
        raise ExtensionError(f"{out_ba2.name}: expected {len(plan)} entries, Ba2 read {len(checked.entries)}")

    return {
        "archive": out_ba2.name,
        "kind": kind,
        "base_entries": len(base_entries),
        "added_entries": added_count,
        "total_entries": len(plan),
        "base_size_bytes": base_ba2.stat().st_size,
        "added_payload_bytes": added_payload_bytes,
        "out_size_bytes": out_ba2.stat().st_size,
        "out_sha256": sha256_file(out_ba2),
    }


def _copy_exact(src, dst, remaining: int, buf_size: int = 1 << 20) -> None:
    while remaining > 0:
        chunk = src.read(min(remaining, buf_size))
        if not chunk:
            raise ExtensionError("unexpected EOF while streaming BA2 payload")
        dst.write(chunk)
        remaining -= len(chunk)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_free_space_gb(target_dir: Path, min_free_gb: float) -> float:
    probe = target_dir
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    usage = shutil.disk_usage(probe)
    free_gb = usage.free / (1024 ** 3)
    if free_gb < min_free_gb:
        raise ExtensionError(
            f"insufficient disk space at {probe}: {free_gb:.2f} GiB free < required floor {min_free_gb:.2f} GiB"
        )
    return round(free_gb, 3)


def check_out_dir_safe(out_dir: Path, allow_clean: bool = False) -> None:
    """Refuse writing staged game output inside a Git repository, game Data folder, or non-empty dir unless clean."""
    resolved = out_dir.resolve()
    parts_low = [p.lower() for p in resolved.parts]
    if "starfield" in parts_low and "data" in parts_low:
        raise ExtensionError(f"refusing to write directly into a Starfield Data directory: {resolved}")
    cur = resolved
    while True:
        if (cur / ".git").exists():
            raise ExtensionError(f"refusing to write derived game staging output inside a Git worktree: {resolved}")
        if cur.parent == cur:
            break
        cur = cur.parent
    if resolved.exists() and resolved.is_dir() and any(resolved.iterdir()):
        if not allow_clean:
            raise ExtensionError(
                f"refusing to write into non-empty output directory without --clean: {resolved}"
            )
        shutil.rmtree(resolved)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Lossless FO4Port.esm Museum + PrewarVault111 extender (R11 Step 3b+3c)")
    ap.add_argument("--base-dir", required=True, help="Baseline doors_anim_b00 port folder (FO4Port.esm + BA2s)")
    ap.add_argument("--source-dir", required=True, help="Source interiors_b10 port folder (FO4Port.esm + BA2s)")
    ap.add_argument("--fo4-esm", default="", help="Fallout4.esm path for ConcordMuseum01 NAVM conversion")
    ap.add_argument("--out-dir", required=True, help="External staging output folder (outside repo & game Data)")
    ap.add_argument("--cells", default=",".join(DEFAULT_CELLS), help="Comma-separated source cell EditorIDs to append")
    ap.add_argument("--start-id", default=f"0x{DEFAULT_START_ID:06X}", help="First local FormID for new records")
    ap.add_argument("--min-free-gb", type=float, default=DEFAULT_MIN_FREE_GB, help="Required free GiB floor")
    ap.add_argument("--esm-only", action="store_true", help="Write & verify FO4Port.esm only (skip BA2 merge)")
    ap.add_argument("--clean", action="store_true", help="Allow overwriting/clearing a non-empty --out-dir")
    ap.add_argument("--allow-custom-base", action="store_true", help="Skip strict doors_anim_b00 SHA-256 check")
    args = ap.parse_args(argv)

    base_dir = Path(args.base_dir)
    source_dir = Path(args.source_dir)
    out_dir = Path(args.out_dir)
    start_id = int(args.start_id, 0)
    cells = [c.strip() for c in args.cells.split(",") if c.strip()]

    check_out_dir_safe(out_dir, allow_clean=args.clean)
    free_before = check_free_space_gb(out_dir, args.min_free_gb)

    base_esm = base_dir / "FO4Port.esm"
    source_esm = source_dir / "FO4Port.esm"
    base_bytes = base_esm.read_bytes()
    source_bytes = source_esm.read_bytes()

    museum_navm_input = None
    if args.fo4_esm:
        nvnm_raw, fo4_doors_m = read_fo4_interior_navm_and_doors(Path(args.fo4_esm))
        museum_navm_input = (nvnm_raw, FO4_MUSEUM_NAVM_FID, fo4_doors_m)

    out_bytes, report = extend_fo4port_esm(
        base_esm_bytes=base_bytes,
        source_esm_bytes=source_bytes,
        target_cells=cells,
        start_id=start_id,
        museum_navm_input=museum_navm_input,
        expected_base_sha256=None if args.allow_custom_base else BASE_B00_SHA256,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    out_esm = out_dir / "FO4Port.esm"
    out_esm.write_bytes(out_bytes)

    ba2_report: dict = {"skipped": bool(args.esm_only)}
    if not args.esm_only:
        src_tex_candidates = [
            source_dir / "FO4Port - Textures.ba2",
            source_dir / "FO4PortTextures2 - Textures.ba2",
        ]
        delta_plan = trace_cell_asset_delta(
            source_esm_bytes=source_bytes,
            target_cells=cells,
            base_main_ba2=base_dir / "FO4Port - Main.ba2",
            base_tex_ba2=base_dir / "FO4Port - Textures.ba2",
            src_main_ba2=source_dir / "FO4Port - Main.ba2",
            src_tex_ba2s=src_tex_candidates,
        )
        main_res = merge_ba2_v2_lossless(
            base_ba2=base_dir / "FO4Port - Main.ba2",
            delta_sources=[(source_dir / "FO4Port - Main.ba2", delta_plan["delta_main"])],
            out_ba2=out_dir / "FO4Port - Main.ba2",
        )
        tex_sources = [
            (Path(p), names) for p, names in delta_plan["delta_tex_by_src"].items() if names
        ]
        tex_res = merge_ba2_v2_lossless(
            base_ba2=base_dir / "FO4Port - Textures.ba2",
            delta_sources=tex_sources,
            out_ba2=out_dir / "FO4Port - Textures.ba2",
        )
        ba2_report = {
            "skipped": False,
            "main_traced_count": delta_plan["main_traced_count"],
            "main_reused_count": delta_plan["main_reused_count"],
            "tex_traced_count": delta_plan["tex_traced_count"],
            "tex_reused_count": delta_plan["tex_reused_count"],
            "delta_tex_by_source_counts": {
                Path(k).name: len(v) for k, v in delta_plan["delta_tex_by_src"].items()
            },
            "vanilla_or_missing_tex": delta_plan["vanilla_or_missing_tex"],
            "main_archive": main_res,
            "textures_archive": tex_res,
            "companion_plugins_added": 0,
        }

    free_after = check_free_space_gb(out_dir, args.min_free_gb)
    report["ba2"] = ba2_report
    report["disk_free_gb_before"] = free_before
    report["disk_free_gb_after"] = free_after

    report_path = out_dir / "r11_museum_extension_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
