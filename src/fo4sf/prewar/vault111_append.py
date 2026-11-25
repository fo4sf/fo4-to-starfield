"""Parameterized lossless PrewarVault111 (0x000CA260) append-generator for FO4Port.esm (Slot 2 after Museum IDs)."""
from __future__ import annotations

import hashlib
import math
import struct
import zlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

import numpy as np

from fo4sf import fo4land, navmesh as navm
from . import s1_spec

COMPRESSED_FLAG = 0x00040000
PERSISTENT_FLAG = 0x00000400
DELETED_FLAG = 0x00000020
UNITS_PER_METRE = 70.0
PROVEN_INTERIOR_LTMP = 0x0006BCF8

# Essential persistent interactive / structural refs from Fallout4.esm CELL 0x000CA260 for S1
KEY_PREWAR_V111_PERSISTENT_FIDS: Tuple[int, ...] = (
    0x000CA2AF,  # PrewarVaultIntAutoloadDoor
    0x000CA2AD,  # VltElevator (interior shaft)
    0x000CA2AC,  # Vault111GearDoorREF001
    0x001EBAC8,  # NPCHandOutVaultSuit
    0x000CA2A8,  # MQ101PlayerCryopodREF
    0x000CA28D,  # MQ101PlayerSpousePodREF
    0x000CA5C0,  # MQ101CryoTerminalWall
    0x000CA2B0,  # MQ101SpouseElevatorMarker02
    0x000CEA9C,  # MQ101VaultTecEscortToCryoMarker
    0x000CEA9F,  # MQ101SpouseToCryopodMarker
    0x0007585E,  # MQ101VaultTecEscortToCryoMarker02
)


class PrewarPortError(ValueError):
    """Raised when lossless FO4Port.esm append invariants fail."""


@dataclass
class RawRec:
    sig: bytes
    flags: int
    fid: int
    version: int
    vc: int
    unknown: int
    body: bytes  # compressed if (flags & COMPRESSED_FLAG) else raw subrecords

    @property
    def raw_subrecords_bytes(self) -> bytes:
        if self.flags & COMPRESSED_FLAG:
            return zlib.decompress(self.body[4:])
        return self.body

    def to_bytes(self) -> bytes:
        hdr = struct.pack(
            "<4sIIIIHH",
            self.sig,
            len(self.body),
            self.flags,
            self.fid,
            self.vc,
            self.version,
            self.unknown,
        )
        return hdr + self.body


def _read_rec(buf: bytes, off: int) -> Tuple[RawRec, int]:
    sig, size, flags, fid, vc, ver, unk = struct.unpack_from("<4sIIIIHH", buf, off)
    body = bytes(buf[off + 24 : off + 24 + size])
    return RawRec(sig, flags, fid, ver, vc, unk, body), off + 24 + size


def _iter_subrecords(raw_bytes: bytes):
    p = 0
    big: Optional[int] = None
    n = len(raw_bytes)
    while p + 6 <= n:
        sig = raw_bytes[p : p + 4]
        sz = struct.unpack_from("<H", raw_bytes, p + 4)[0]
        p += 6
        if big is not None:
            sz = big
            big = None
        if sig == b"XXXX":
            big = struct.unpack_from("<I", raw_bytes, p)[0]
            p += sz
            continue
        yield sig, bytes(raw_bytes[p : p + sz])
        p += sz


def _pack_subrecords(subs: Sequence[Tuple[bytes, bytes]]) -> bytes:
    parts: List[bytes] = []
    for sig, payload in subs:
        if len(payload) > 0xFFFF:
            parts.append(b"XXXX" + struct.pack("<HI", 4, len(payload)))
            parts.append(sig + struct.pack("<H", 0) + payload)
        else:
            parts.append(sig + struct.pack("<H", len(payload)) + payload)
    return b"".join(parts)


def _get_edid(rec: RawRec) -> str:
    for sig, d in _iter_subrecords(rec.raw_subrecords_bytes):
        if sig == b"EDID":
            return fo4land.zstring(d)
    return ""


def _rewrite_edid_subs(raw_bytes: bytes, new_edid: str) -> bytes:
    subs = [(s, d) for s, d in _iter_subrecords(raw_bytes) if s != b"EDID"]
    subs.insert(0, (b"EDID", new_edid.encode("cp1252") + b"\0"))
    return _pack_subrecords(subs)


def parse_top_grups(buf: bytes) -> Tuple[RawRec, List[Tuple[bytes, int, int, int, bytes]]]:
    """Parse `TES4` header and top-level `GRUP` chunks `(label4, gtype, stamp, unk, payload)`."""
    if buf[:4] != b"TES4":
        raise PrewarPortError(f"Expected TES4 header, got {buf[:4]!r}")
    tes4, pos = _read_rec(buf, 0)
    grups = []
    n = len(buf)
    while pos + 24 <= n:
        sig = buf[pos : pos + 4]
        if sig != b"GRUP":
            raise PrewarPortError(f"Expected top-level GRUP at 0x{pos:X}, got {sig!r}")
        gsize = struct.unpack_from("<I", buf, pos + 4)[0]
        label = bytes(buf[pos + 8 : pos + 12])
        gtype, stamp, unk = struct.unpack_from("<III", buf, pos + 12)
        payload = bytes(buf[pos + 24 : pos + gsize])
        grups.append((label, gtype, stamp, unk, payload))
        pos += gsize
    return tes4, grups


def walk_records(buf: bytes) -> List[RawRec]:
    """Walk every record in an ESM file in appearance order (skipping GRUP headers)."""
    out: List[RawRec] = []
    def _w(s: int, e: int) -> None:
        p = s
        while p + 24 <= e:
            if buf[p : p + 4] == b"GRUP":
                gs = struct.unpack_from("<I", buf, p + 4)[0]
                _w(p + 24, p + gs)
                p += gs
            else:
                rec, nxt = _read_rec(buf, p)
                out.append(rec)
                p = nxt
    _w(0, len(buf))
    return out


def _count_recs_and_grups(buf: bytes) -> int:
    total = 0
    pos = 24 + struct.unpack_from("<I", buf, 4)[0]
    def _c(s: int, e: int) -> int:
        cnt = 0
        p = s
        while p + 24 <= e:
            cnt += 1
            if buf[p : p + 4] == b"GRUP":
                gs = struct.unpack_from("<I", buf, p + 4)[0]
                cnt += _c(p + 24, p + gs)
                p += gs
            else:
                rs = struct.unpack_from("<I", buf, p + 4)[0]
                p += 24 + rs
        return cnt
    total += _c(pos, len(buf))
    return total


def max_local_formid(esm_bytes: bytes) -> int:
    """Return max local 24-bit FormID across all non-TES4 records belonging to the plugin's own master prefix."""
    tes4, _ = parse_top_grups(esm_bytes)
    masters = sum(1 for s, _ in _iter_subrecords(tes4.raw_subrecords_bytes) if s == b"MAST")
    mx = 0
    for rec in walk_records(esm_bytes):
        if rec.sig != b"TES4" and (rec.fid >> 24) == masters:
            mx = max(mx, rec.fid & 0x00FFFFFF)
    return mx


def extract_prewar_v111_source(fo4_esm_path: str) -> dict:
    """Read-only inspect Fallout4.esm CELL 0x000CA260 for its 2 NAVMs, persistent refs, and LIGH placements."""
    navms: List[Tuple[int, bytes]] = []
    door_pos: Dict[int, Tuple[float, float, float]] = {}
    pers_refs: List[dict] = []
    ligh_fids: Set[int] = set()
    ligh_refs: List[dict] = []

    with fo4land.Plugin(fo4_esm_path) as p:
        buf = p.buf
        for g in fo4land.iter_items(buf, *p.top_group(b"CELL")):
            if g[0] != "GRUP":
                continue
            for blk in fo4land.iter_items(buf, g[1] + 24, g[2]):
                if blk[0] != "GRUP":
                    continue
                for c in fo4land.iter_items(buf, blk[1] + 24, blk[2]):
                    if c[0] == "GRUP" and struct.unpack_from("<I", c[3])[0] == s1_spec.PREWAR_VAULT111_CELL_FID:
                        for sg in fo4land.iter_items(buf, c[1] + 24, c[2]):
                            if sg[0] != "GRUP":
                                continue
                            is_pers = sg[4] == 8
                            for rec in fo4land.iter_items(buf, sg[1] + 24, sg[2]):
                                if rec[0] == "GRUP" or (rec[2] & DELETED_FLAG):
                                    continue
                                subs = list(fo4land.iter_subrecords(fo4land.record_data(buf, rec[1])))
                                if rec[0] == b"NAVM":
                                    nv = next((d for s, d in subs if s == b"NVNM"), None)
                                    if nv:
                                        navms.append((rec[3], nv))
                                elif rec[0] == b"REFR":
                                    pr = fo4land.parse_ref(subs)
                                    ed = next((fo4land.zstring(d) for s, d in subs if s == b"EDID"), "")
                                    if pr["pos"]:
                                        pos_m = tuple(v / UNITS_PER_METRE for v in pr["pos"])
                                        rot_r = tuple(pr["rot"] or (0.0, 0.0, 0.0))
                                        door_pos[rec[3]] = pos_m
                                        if is_pers and (rec[3] in KEY_PREWAR_V111_PERSISTENT_FIDS or ed):
                                            pers_refs.append({
                                                "fo4_fid": rec[3],
                                                "edid": ed,
                                                "base": pr["base"],
                                                "pos_m": pos_m,
                                                "rot_rad": rot_r,
                                            })
                                        # Track any light refs via subrecords XRDS/XLIG/LNAM/NAME
                                        if any(s in (b"XRDS", b"XLIG") for s, _ in subs):
                                            ligh_fids.add(pr["base"])
                                            ligh_refs.append({
                                                "fo4_fid": rec[3],
                                                "base": pr["base"],
                                                "pos_m": pos_m,
                                                "rot_rad": rot_r,
                                            })
    return {
        "navms": navms,
        "door_pos": door_pos,
        "pers_refs": pers_refs,
        "ligh_fids": sorted(ligh_fids),
        "ligh_refs": ligh_refs,
    }


def _find_cell_block_in_payload(
    cell_payload: bytes,
    target_cell_edid: str,
) -> Optional[Tuple[RawRec, List[RawRec], List[RawRec]]]:
    """Locate `target_cell_edid` inside a top-level `CELL` GRUP payload and return `(cell_rec, pers, temp)`."""
    p = 0
    n = len(cell_payload)
    def _scan_group(s: int, e: int):
        q = s
        while q + 24 <= e:
            if cell_payload[q : q + 4] == b"GRUP":
                gs = struct.unpack_from("<I", cell_payload, q + 4)[0]
                res = _scan_group(q + 24, q + gs)
                if res is not None:
                    return res
                q += gs
            else:
                rec, nxt = _read_rec(cell_payload, q)
                if rec.sig == b"CELL":
                    subs = list(_iter_subrecords(rec.raw_subrecords_bytes))
                    ed = next((fo4land.zstring(d) for sg, d in subs if sg == b"EDID"), "")
                    pers, temp = [], []
                    # Immediately following GRUP type 6 holds persistent/temporary sub-GRUPs
                    if nxt + 24 <= e and cell_payload[nxt : nxt + 4] == b"GRUP":
                        cgs = struct.unpack_from("<I", cell_payload, nxt + 4)[0]
                        cgt = struct.unpack_from("<I", cell_payload, nxt + 12)[0]
                        if cgt == 6:
                            sp = nxt + 24
                            ce = nxt + cgs
                            while sp + 24 <= ce:
                                if cell_payload[sp : sp + 4] == b"GRUP":
                                    sgs = struct.unpack_from("<I", cell_payload, sp + 4)[0]
                                    sgt = struct.unpack_from("<I", cell_payload, sp + 12)[0]
                                    inner = sp + 24
                                    while inner + 24 <= sp + sgs:
                                        cr, cn = _read_rec(cell_payload, inner)
                                        if sgt == 8:
                                            pers.append(cr)
                                        elif sgt == 9:
                                            temp.append(cr)
                                        inner = cn
                                    sp += sgs
                                else:
                                    sp += 24 + struct.unpack_from("<I", cell_payload, sp + 4)[0]
                            nxt = ce
                    if ed == target_cell_edid:
                        return rec, pers, temp
                q = nxt
        return None
    return _scan_group(p, n)


def _wrap_grup(label: bytes, gtype: int, payload: bytes) -> bytes:
    return b"GRUP" + struct.pack("<I", 24 + len(payload)) + label + struct.pack("<III", gtype, 0, 0) + payload


def _wrap_cell(cell_rec: RawRec, pers: Sequence[RawRec], temp: Sequence[RawRec]) -> bytes:
    """Wrap one interior CELL + child groups inside `InteriorCellBlock (2)` and `InteriorCellSubBlock (3)` GRUPs."""
    local_id = cell_rec.fid & 0x00FFFFFF
    block = local_id % 10
    subblock = (local_id // 10) % 10
    sub_blocks = b""
    if pers:
        sub_blocks += _wrap_grup(struct.pack("<I", cell_rec.fid), 8, b"".join(r.to_bytes() for r in pers))
    if temp:
        sub_blocks += _wrap_grup(struct.pack("<I", cell_rec.fid), 9, b"".join(r.to_bytes() for r in temp))
    cell_body = cell_rec.to_bytes()
    if sub_blocks:
        cell_body += _wrap_grup(struct.pack("<I", cell_rec.fid), 6, sub_blocks)
    sub_grp = _wrap_grup(struct.pack("<i", subblock), 3, cell_body)
    return _wrap_grup(struct.pack("<i", block), 2, sub_grp)


def _build_static_marker_base_if_missing(fid: int, edid: str) -> RawRec:
    raw = _pack_subrecords([
        (b"EDID", edid.encode("cp1252") + b"\0"),
        (b"OBND", struct.pack("<6f", -0.25, -0.25, -0.25, 0.25, 0.25, 0.25)),
        (b"MODL", b"Markers\\MarkerX.nif\0"),
    ])
    return RawRec(b"STAT", 0, fid, 581, 0, 0, raw)


def _build_refr(fid: int, edid: str, base_fid: int, pos_m: Tuple[float, float, float], rot_rad: Tuple[float, float, float], persistent: bool) -> RawRec:
    subs: List[Tuple[bytes, bytes]] = []
    if edid:
        subs.append((b"EDID", edid.encode("cp1252") + b"\0"))
    subs.append((b"NAME", struct.pack("<I", base_fid)))
    subs.append((b"DATA", struct.pack("<6f", pos_m[0], pos_m[1], pos_m[2], rot_rad[0], rot_rad[1], rot_rad[2])))
    flags = PERSISTENT_FLAG if persistent else 0
    return RawRec(b"REFR", flags, fid, 581, 0, 0, _pack_subrecords(subs))


def _convert_interior_navm_to_sf(
    fo4_nvnm_raw: bytes,
    fo4_navm_fid: int,
    new_navm_fid: int,
    new_cell_fid: int,
) -> Tuple[navm.Nvnm, navm.Nvmi, RawRec]:
    fo4 = navm.parse(fo4_nvnm_raw, layout="fo4")
    sf_verts = (fo4.vertices / UNITS_PER_METRE).astype(np.float32).astype(np.float64)
    sf_tris = fo4.triangles.copy()
    heights = sf_tris["height"].astype(np.float64)
    fmask = heights < navm.NO_CEILING
    heights[fmask] = heights[fmask] / UNITS_PER_METRE
    sf_tris["height"] = np.where(fmask, heights.astype(np.float32), np.float32(navm.FLT_MAX))
    sf_tris["cover"] = 0

    link_remap: Dict[int, int] = {}
    kept_links = []
    for idx, row in enumerate(fo4.links):
        if int(row["navmesh"]) == fo4_navm_fid:
            link_remap[idx] = len(kept_links)
            kept_links.append((int(row["type"]), new_navm_fid, int(row["tri"]), int(row["edge"])))
    sf_links = np.zeros(len(kept_links), navm.LINK_DTYPE)
    for i, item in enumerate(kept_links):
        sf_links[i] = item

    vertex_extra = np.zeros(len(sf_verts), np.int32)
    for ti in range(len(sf_tris)):
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
        sf_tris["flags"][ti] = fl & ~navm.F_DOOR

    sf_doors = np.zeros(0, navm.DOOR_DTYPE)
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
        cover_map=np.zeros(0, dtype=navm.COVERMAP_DTYPE),
        waypoints=sf_wps,
        grid_divisor=div,
        grid_size=gsize,
        grid_min=gmin,
        grid_max=gmax,
        grid_lists=glists,
    )
    mean_loc = tuple(float(v) for v in sf_verts.mean(axis=0)) if len(sf_verts) else (0.0, 0.0, 0.0)
    sf_nvmi = navm.Nvmi(
        navmesh=new_navm_fid,
        flags=0,
        location=mean_loc,
        unknown_f=0.0,
        merged=[],
        preferred=[],
        doors=[],
        traversals=[],
        outline=None,
        world=0,
        grid=None,
        cell=new_cell_fid,
        border=0,
    )
    nv_raw = _pack_subrecords([(b"NVNM", navm.write_sf(sf_nvnm)), (b"MNAM", b"")])
    nv_rec = RawRec(b"NAVM", 0, new_navm_fid, 581, 0, 0, nv_raw)
    return sf_nvnm, sf_nvmi, nv_rec


def _append_into_existing_cell_payload(
    cell_payload: bytes,
    target_cell_fid: int,
    extra_pers: Sequence[RawRec],
    extra_temp: Sequence[RawRec],
) -> bytes:
    """Re-pack top-level `CELL` GRUP payload, appending `extra_pers`/`extra_temp` into `target_cell_fid` in-place."""
    extra_pers_bytes = b"".join(r.to_bytes() for r in extra_pers)
    extra_temp_bytes = b"".join(r.to_bytes() for r in extra_temp)
    spliced = False

    def _splice_cell_children(child_grup_bytes: bytes) -> bytes:
        inner_pl = child_grup_bytes[24:]
        gt, st, unk = struct.unpack_from("<III", child_grup_bytes, 12)
        assert gt == 6
        parts: List[bytes] = []
        pos = 0
        saw_8 = False
        saw_9 = False
        while pos + 24 <= len(inner_pl):
            if inner_pl[pos : pos + 4] == b"GRUP":
                sgs = struct.unpack_from("<I", inner_pl, pos + 4)[0]
                slbl = inner_pl[pos + 8 : pos + 12]
                sgt, sst, sunk = struct.unpack_from("<III", inner_pl, pos + 12)
                sub_pl = inner_pl[pos + 24 : pos + sgs]
                if sgt == 8:
                    saw_8 = True
                    sub_pl = sub_pl + extra_pers_bytes
                elif sgt == 9:
                    saw_9 = True
                    sub_pl = sub_pl + extra_temp_bytes
                parts.append(b"GRUP" + struct.pack("<I", 24 + len(sub_pl)) + slbl + struct.pack("<III", sgt, sst, sunk) + sub_pl)
                pos += sgs
            else:
                r, nxt = _read_rec(inner_pl, pos)
                parts.append(r.to_bytes())
                pos = nxt
        if extra_pers_bytes and not saw_8:
            parts.insert(0, _wrap_grup(struct.pack("<I", target_cell_fid), 8, extra_pers_bytes))
        if extra_temp_bytes and not saw_9:
            parts.append(_wrap_grup(struct.pack("<I", target_cell_fid), 9, extra_temp_bytes))
        joined = b"".join(parts)
        return b"GRUP" + struct.pack("<I", 24 + len(joined)) + struct.pack("<I", target_cell_fid) + struct.pack("<III", gt, st, unk) + joined

    def _walk(s: int, e: int) -> bytes:
        nonlocal spliced
        out: List[bytes] = []
        q = s
        while q + 24 <= e:
            if cell_payload[q : q + 4] == b"GRUP":
                gs = struct.unpack_from("<I", cell_payload, q + 4)[0]
                lbl = cell_payload[q + 8 : q + 12]
                gt, st, unk = struct.unpack_from("<III", cell_payload, q + 12)
                inner = _walk(q + 24, q + gs)
                out.append(b"GRUP" + struct.pack("<I", 24 + len(inner)) + lbl + struct.pack("<III", gt, st, unk) + inner)
                q += gs
            else:
                rec, nxt = _read_rec(cell_payload, q)
                out.append(cell_payload[q:nxt])
                if rec.sig == b"CELL" and rec.fid == target_cell_fid:
                    spliced = True
                    if nxt + 24 <= e and cell_payload[nxt : nxt + 4] == b"GRUP" and struct.unpack_from("<I", cell_payload, nxt + 12)[0] == 6:
                        cgs = struct.unpack_from("<I", cell_payload, nxt + 4)[0]
                        out.append(_splice_cell_children(cell_payload[nxt : nxt + cgs]))
                        nxt += cgs
                    elif extra_pers_bytes or extra_temp_bytes:
                        sub_grps = b""
                        if extra_pers_bytes:
                            sub_grps += _wrap_grup(struct.pack("<I", target_cell_fid), 8, extra_pers_bytes)
                        if extra_temp_bytes:
                            sub_grps += _wrap_grup(struct.pack("<I", target_cell_fid), 9, extra_temp_bytes)
                        out.append(_wrap_grup(struct.pack("<I", target_cell_fid), 6, sub_grps))
                q = nxt
        return b"".join(out)

    result = _walk(0, len(cell_payload))
    if not spliced:
        raise PrewarPortError(f"Failed to splice into target cell 0x{target_cell_fid:08X}")
    return result


def append_prewar_vault111_lossless(
    base_esm_bytes: bytes,
    *,
    start_id: Optional[int] = None,
    min_start_id: int = s1_spec.MIN_PREWAR_PORT_START_ID,
    fo4_navms: Sequence[Tuple[int, bytes]] = (),
    extra_persistent_specs: Sequence[dict] = (),
    source_shell_edid: str = "FO4Port_PrewarVault111",
    new_cell_edid: Optional[str] = None,
) -> Tuple[bytes, dict]:
    """Losslessly append ONLY `extra_persistent_specs` + converted `NAVM`s (>= `start_id`) onto existing Slot 1
    `source_shell_edid` (`FO4Port_PrewarVault111`, `S1-08`) without cloning the shell cell or mutating Slot 1 records."""
    tes4, grups = parse_top_grups(base_esm_bytes)
    masters = sum(1 for s, _ in _iter_subrecords(tes4.raw_subrecords_bytes) if s == b"MAST")
    max_id = max_local_formid(base_esm_bytes)
    alloc_start = start_id if start_id is not None else max(max_id + 1, min_start_id)
    if alloc_start <= max_id:
        raise PrewarPortError(f"start_id 0x{alloc_start:06X} must exceed base max local ID 0x{max_id:06X}")
    if alloc_start < min_start_id:
        raise PrewarPortError(f"start_id 0x{alloc_start:06X} violates Slot 2 floor 0x{min_start_id:06X}")

    next_local = alloc_start

    def _alloc() -> int:
        nonlocal next_local
        fid = (masters << 24) | next_local
        next_local += 1
        return fid

    cell_payload = next((pl for lbl, _gt, _st, _un, pl in grups if lbl == b"CELL"), None)
    if cell_payload is None:
        raise PrewarPortError("base FO4Port.esm has no top-level CELL GRUP")
    found_shell = _find_cell_block_in_payload(cell_payload, source_shell_edid)
    if found_shell is None:
        raise PrewarPortError(f"source shell cell {source_shell_edid!r} not found in base FO4Port.esm")
    shell_cell, shell_pers, shell_temp = found_shell

    # S1-08: Reuse Slot 1's FO4Port_PrewarVault111 in-place (zero clone of 0x0100EFAB).
    target_cell_edid = new_cell_edid or source_shell_edid
    target_cell_fid = shell_cell.fid
    seen_edids: Set[str] = {
        ed for ed in (_get_edid(rec) for rec in walk_records(base_esm_bytes)) if ed
    }

    def _s1_edid(raw_name: str, fallback: str) -> str:
        base_name = raw_name if raw_name else fallback
        if not base_name.startswith(f"{target_cell_edid}_"):
            base_name = f"{target_cell_edid}_{base_name}"
        cand = base_name
        suffix = 1
        while cand in seen_edids:
            cand = f"{base_name}_{suffix}"
            suffix += 1
        seen_edids.add(cand)
        return cand

    # 1. Allocate persistent marker base + refs appended into existing cell's GRUP 8
    extra_pers: List[RawRec] = []
    extra_temp: List[RawRec] = []
    appended_stats: List[RawRec] = []
    extra_ref_map: Dict[str, str] = {}
    if extra_persistent_specs:
        marker_base_fid = _alloc()
        marker_base_edid = _s1_edid("MarkerBase", "MarkerBase")
        appended_stats.append(_build_static_marker_base_if_missing(marker_base_fid, marker_base_edid))
        for idx, spec in enumerate(extra_persistent_specs):
            rfid = _alloc()
            raw_ed = spec.get("edid") or f"Pers_{idx:02d}"
            red = _s1_edid(raw_ed, f"Pers_{idx:02d}")
            extra_pers.append(_build_refr(rfid, red, marker_base_fid, tuple(spec["pos_m"]), tuple(spec.get("rot_rad", (0.0, 0.0, 0.0))), persistent=True))
            extra_ref_map[red] = f"0x{rfid:08X}"

    # 2. Convert FO4 interior NAVMs targeting the existing shell CELL and append into GRUP 9 + NAVI
    nvmis: List[navm.Nvmi] = []
    navm_fids: List[str] = []
    for fo4_nfid, fo4_nvnm in fo4_navms:
        sf_nfid = _alloc()
        _snv, snvmi, nv_rec = _convert_interior_navm_to_sf(fo4_nvnm, fo4_nfid, sf_nfid, target_cell_fid)
        extra_temp.append(nv_rec)
        nvmis.append(snvmi)
        navm_fids.append(f"0x{sf_nfid:08X}")

    stat_chunk = b"".join(r.to_bytes() for r in appended_stats)

    # Assemble output GRUPs cleanly while keeping ALL Slot 1 records (including FO4Port_PrewarVault111 shell) byte-identical!
    out_grups: List[bytes] = []
    has_navi = False
    for lbl, gt, st, unk, pl in grups:
        if lbl == b"CELL":
            pl_out = _append_into_existing_cell_payload(pl, target_cell_fid, extra_pers, extra_temp)
        elif lbl == b"STAT" and stat_chunk:
            pl_out = pl + stat_chunk
        elif lbl == b"NAVI":
            has_navi = True
            if nvmis:
                # Preserve existing NVER/NVMI, insert new NVMI BEFORE trailing NVPP (match build_fo4port_r11_museum.py)
                navi_rec, _ = _read_rec(pl, 0)
                existing_subs = list(_iter_subrecords(navi_rec.raw_subrecords_bytes))
                head_subs = [(s, d) for s, d in existing_subs if s != b"NVPP"]
                tail_subs = [(s, d) for s, d in existing_subs if s == b"NVPP"]
                if not tail_subs:
                    tail_subs = [(b"NVPP", b"\x00" * 8)]
                merged_subs = head_subs + [(b"NVMI", navm.write_nvmi(nv)) for nv in nvmis] + tail_subs
                new_navi = RawRec(
                    b"NAVI",
                    navi_rec.flags & ~COMPRESSED_FLAG,
                    navi_rec.fid,
                    navi_rec.version,
                    0,
                    navi_rec.unknown,
                    _pack_subrecords(merged_subs),
                )
                pl_out = new_navi.to_bytes()
            else:
                pl_out = pl
        else:
            pl_out = pl
        out_grups.append(b"GRUP" + struct.pack("<I", 24 + len(pl_out)) + lbl + struct.pack("<III", gt, st, unk) + pl_out)

    if stat_chunk and not any(lbl == b"STAT" for lbl, *_ in grups):
        out_grups.append(_wrap_grup(b"STAT", 0, stat_chunk))
    if nvmis and not has_navi:
        navi_subs = [(b"NVER", struct.pack("<I", 12))] + [(b"NVMI", navm.write_nvmi(nv)) for nv in nvmis]
        navi_rec = RawRec(b"NAVI", 0, 0x000FF1, 581, 0, 0, _pack_subrecords(navi_subs))
        out_grups.append(_wrap_grup(b"NAVI", 0, navi_rec.to_bytes()))

    body = b"".join(out_grups)
    provisional = tes4.to_bytes() + body
    n_total = _count_recs_and_grups(provisional)

    tes4_subs = []
    for s, d in _iter_subrecords(tes4.raw_subrecords_bytes):
        if s == b"HEDR" and len(d) >= 12:
            ver, _cnt, _nxt = struct.unpack_from("<fII", d, 0)
            tes4_subs.append((s, struct.pack("<fII", ver, n_total, next_local)))
        else:
            tes4_subs.append((s, d))
    new_tes4 = RawRec(b"TES4", tes4.flags, 0, tes4.version, 0, tes4.unknown, _pack_subrecords(tes4_subs))
    out_bytes = new_tes4.to_bytes() + body

    verify_lossless_append(base_esm_bytes, out_bytes, alloc_start, allow_navi_update=bool(nvmis))
    existing_temp_refrs = sum(1 for r in shell_temp if r.sig == b"REFR")
    return out_bytes, {
        "base_max_local_id": f"0x{max_id:06X}",
        "start_id": f"0x{alloc_start:06X}",
        "next_object_id": f"0x{next_local:06X}",
        "new_cell_fid": f"0x{target_cell_fid:08X}",
        "new_cell_edid": target_cell_edid,
        "reused_slot1_cell": True,
        "existing_persistent_count": len(shell_pers),
        "existing_temp_refr_count": existing_temp_refrs,
        "appended_persistent_count": len(extra_pers),
        "appended_navm_count": len(navm_fids),
        "persistent_count": len(shell_pers) + len(extra_pers),
        "temporary_count": len(shell_temp) + len(extra_temp),
        "split_summary": f"{existing_temp_refrs} temp REFR + {len(navm_fids)} NAVM",
        "navm_fids": navm_fids,
        "extra_persistent_refs": extra_ref_map,
        "base_sha256": hashlib.sha256(base_esm_bytes).hexdigest(),
        "out_sha256": hashlib.sha256(out_bytes).hexdigest(),
    }


def verify_lossless_append(
    base_esm_bytes: bytes,
    out_esm_bytes: bytes,
    start_id: int,
    *,
    allow_navi_update: bool = False,
) -> dict:
    """Strictly verify all base records (< start_id) remain byte-identical (optionally allowing NAVI NVMI growth)."""
    base_tes4, _ = parse_top_grups(base_esm_bytes)
    out_tes4, _ = parse_top_grups(out_esm_bytes)
    masters = sum(1 for s, _ in _iter_subrecords(base_tes4.raw_subrecords_bytes) if s == b"MAST")
    if sum(1 for s, _ in _iter_subrecords(out_tes4.raw_subrecords_bytes) if s == b"MAST") != masters:
        raise PrewarPortError("TES4 master count changed")

    base_map = {r.fid: r for r in walk_records(base_esm_bytes) if r.sig != b"TES4"}
    out_recs = [r for r in walk_records(out_esm_bytes) if r.sig != b"TES4"]
    out_map: Dict[int, RawRec] = {}
    for r in out_recs:
        if r.fid in out_map:
            raise PrewarPortError(f"Duplicate FormID in extended ESM: 0x{r.fid:08X}")
        out_map[r.fid] = r

    for fid, brec in base_map.items():
        orec = out_map.get(fid)
        if orec is None:
            raise PrewarPortError(f"Missing base FormID 0x{fid:08X}")
        if orec.sig != brec.sig:
            raise PrewarPortError(f"Changed signature on 0x{fid:08X}: {brec.sig} -> {orec.sig}")
        if brec.sig == b"NAVI" and allow_navi_update:
            b_subs = list(_iter_subrecords(brec.raw_subrecords_bytes))
            o_subs = list(_iter_subrecords(orec.raw_subrecords_bytes))
            b_nvmi = [d for s, d in b_subs if s == b"NVMI"]
            o_nvmi = [d for s, d in o_subs if s == b"NVMI"]
            if o_nvmi[: len(b_nvmi)] != b_nvmi:
                raise PrewarPortError("NAVI lost or altered existing NVMI entries")
            if b_subs and b_subs[-1][0] == b"NVPP":
                if not o_subs or o_subs[-1] != b_subs[-1]:
                    raise PrewarPortError("NAVI trailing NVPP must remain preserved after new NVMI entries")
            continue
        if orec.to_bytes() != brec.to_bytes():
            raise PrewarPortError(f"Mutated base record 0x{fid:08X} ({brec.sig})")

    new_recs = [r for fid, r in out_map.items() if fid not in base_map]
    for r in new_recs:
        if (r.fid >> 24) != masters and r.sig != b"NAVI":
            raise PrewarPortError(f"Unexpected master prefix on net-new record 0x{r.fid:08X}")
        if r.sig != b"NAVI" and (r.fid & 0x00FFFFFF) < start_id:
            raise PrewarPortError(f"Low local allocation 0x{r.fid & 0xFFFFFF:06X} < 0x{start_id:06X}")

    return {"preserved_records": len(base_map), "appended_records": len(new_recs)}
