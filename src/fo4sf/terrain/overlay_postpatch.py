"""Raw record post-patcher and offline verifier for staged Starfield overlay plugins (`WD2`, `WD3`, `WG1`).

Operates on staging folders produced by `scripts/terrain/make_cw_overlays.py` + `dotnet/TerrainOverlays` without
modifying `dotnet/TerrainOverlays/*` or the default dry Commonwealth path:
  - Sets coastal/world sea-water fields on `WRLD` (`DNAM`, `NAM2`, `NAM3`, `NAM4`), `SFBK` (`WHGT`), and exterior
    `CELL` records (`DATA |= 0x02` `HasWater`, `XCLW = +FLT_MAX` inherit `WRLD` water height).
  - Updates `WRLD` / `LCTN` / default `MapMarker` `FULL` names to neutral world-specific labels.
  - Appends custom `LTEX` records (for `WG1` ground-texture prototypes) to a top-level `LTEX` group.
  - Registers peer overlay worldspaces (`Commonwealth`, `FarHarbor`, etc.) in the staged `*_Mars.esm` `PNDT` `CNAM`
    table so multi-world pairwise separation (`>= 2,000` planet cells) is verified in one `PNDT` record.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import struct
import sys
import tempfile
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import zlib

import numpy as np

from fo4sf import btd, fo4land, overlay_grid as og, terrain_grid as tg
from fo4sf.terrain.path_guard import refuse_unsafe_output_path

COMPRESSED_FLAG = 0x00040000
CELL_HAS_WATER = 0x00000002
XCLW_INHERIT_BYTES = b"\xff\xff\x7f\x7f"  # +FLT_MAX (+3.4028235e+38): inherit WRLD DNAM water height
WATER_CLEAR_FID = 0x00000018
DEFAULT_MATT_DIRT_FID = 0x00012F3E


def encode_subrecord(sig: bytes, payload: bytes) -> bytes:
    """Encode a Creation Engine subrecord, inserting an `XXXX` 32-bit length prefix if `len(payload) > 0xFFFF`."""
    sig_b = bytes(sig)
    data_b = bytes(payload)
    if len(sig_b) != 4:
        raise ValueError(f"Subrecord signature must be 4 bytes, got {sig_b!r}")
    if len(data_b) <= 0xFFFF:
        return sig_b + struct.pack("<H", len(data_b)) + data_b
    return b"XXXX\x04\x00" + struct.pack("<I", len(data_b)) + sig_b + b"\x00\x00" + data_b


def _zstr(text: str) -> bytes:
    return text.encode("cp1252") + b"\x00"


def _atomic_write_bytes(path: str, data: bytes) -> None:
    """Write `data` to a sibling temp file and atomically `os.replace` onto `path`."""
    abs_p = os.path.abspath(path)
    parent = os.path.dirname(abs_p)
    if parent:
        os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".fo4sf-opp-", dir=parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp_path, abs_p)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _atomic_write_json(path: str, payload: Any, *, indent: int = 2) -> None:
    raw = (json.dumps(payload, indent=indent) + "\n").encode("utf-8")
    _atomic_write_bytes(path, raw)


class RawRecord:
    __slots__ = ("header", "data")

    def __init__(self, header: bytes, data: bytes) -> None:
        self.header = bytes(header)
        self.data = bytes(data)

    @property
    def sig(self) -> bytes:
        return self.header[:4]

    @property
    def flags(self) -> int:
        return int(struct.unpack_from("<I", self.header, 8)[0])

    @property
    def fid(self) -> int:
        return int(struct.unpack_from("<I", self.header, 12)[0])

    def fields(self) -> List[Tuple[bytes, bytes]]:
        raw = self.data
        if self.flags & COMPRESSED_FLAG:
            raw = zlib.decompress(raw[4:])
        return list(fo4land.iter_subrecords(raw))

    def with_fields(self, fields: Sequence[Tuple[bytes, bytes]], *, keep_compressed: Optional[bool] = None) -> "RawRecord":
        uncompressed = b"".join(encode_subrecord(s, d) for s, d in fields)
        compress = bool(self.flags & COMPRESSED_FLAG) if keep_compressed is None else bool(keep_compressed)
        flags = (self.flags | COMPRESSED_FLAG) if compress else (self.flags & ~COMPRESSED_FLAG)
        if compress:
            payload = struct.pack("<I", len(uncompressed)) + zlib.compress(uncompressed)
        else:
            payload = uncompressed
        new_hdr = self.header[:4] + struct.pack("<II", len(payload), flags) + self.header[12:]
        return RawRecord(new_hdr, payload)

    def serialize(self) -> bytes:
        return self.header + self.data


class RawGroup:
    __slots__ = ("label", "gtype", "tail", "children")

    def __init__(self, label: bytes, gtype: int, tail: bytes, children: List[Any]) -> None:
        self.label = bytes(label)
        self.gtype = int(gtype)
        self.tail = bytes(tail)
        self.children = list(children)

    def serialize(self) -> bytes:
        body = b"".join(c.serialize() for c in self.children)
        return b"GRUP" + struct.pack("<I", 24 + len(body)) + self.label + struct.pack("<I", self.gtype) + self.tail + body


def _parse_tree(buf: bytes, start: int, end: int) -> List[Any]:
    out: List[Any] = []
    off = start
    while off < end:
        if off + 24 > end:
            raise ValueError(f"Truncated ESM item at byte {off}")
        if buf[off : off + 4] == b"GRUP":
            size, label, gtype = struct.unpack_from("<I4sI", buf, off + 4)
            if size < 24 or off + size > end:
                raise ValueError(f"Invalid GRUP size {size} at byte {off}")
            out.append(RawGroup(label, gtype, buf[off + 16 : off + 24], _parse_tree(buf, off + 24, off + size)))
            off += size
        else:
            size = struct.unpack_from("<I", buf, off + 4)[0]
            if off + 24 + size > end:
                raise ValueError(f"Invalid record size {size} at byte {off}")
            out.append(RawRecord(buf[off : off + 24], buf[off + 24 : off + 24 + size]))
            off += 24 + size
    return out


class RawPlugin:
    def __init__(self, buf: bytes) -> None:
        raw = bytes(buf)
        if raw[:4] != b"TES4":
            raise ValueError("Not a TES4 plugin")
        hsize = struct.unpack_from("<I", raw, 4)[0]
        self.tes4 = RawRecord(raw[:24], raw[24 : 24 + hsize])
        self.items = _parse_tree(raw, 24 + hsize, len(raw))

    @classmethod
    def read(cls, path: str) -> "RawPlugin":
        with open(path, "rb") as f:
            return cls(f.read())

    def serialize(self) -> bytes:
        return self.tes4.serialize() + b"".join(it.serialize() for it in self.items)

    def hedr(self) -> Tuple[float, int, int]:
        d = next(d for s, d in self.tes4.fields() if s == b"HEDR")
        ver, count, next_id = struct.unpack_from("<fII", d)
        return float(ver), int(count), int(next_id)

    def set_hedr(self, count: int, next_id: int) -> None:
        ver, _, _ = self.hedr()
        fields = [
            (s, struct.pack("<fII", ver, int(count), int(next_id)) if s == b"HEDR" else d)
            for s, d in self.tes4.fields()
        ]
        self.tes4 = self.tes4.with_fields(fields)

    def masters(self) -> List[str]:
        return [fo4land.zstring(d) for s, d in self.tes4.fields() if s == b"MAST"]

    def add_master(self, master_name: str) -> int:
        cur = self.masters()
        low = [m.lower() for m in cur]
        if master_name.lower() in low:
            return low.index(master_name.lower())
        fields = list(self.tes4.fields())
        insert_at = len(fields)
        for idx, (s, _) in enumerate(fields):
            if s in (b"MAST", b"DATA"):
                insert_at = idx + 1
        fields.insert(insert_at, (b"MAST", _zstr(master_name)))
        fields.insert(insert_at + 1, (b"DATA", struct.pack("<Q", 0)))
        self.tes4 = self.tes4.with_fields(fields)
        return len(cur)


def _patch_wrld_water(
    rec: RawRecord,
    *,
    water_height_m: Optional[float],
    water_fid: int,
    default_land_m: float,
    world_display_name: Optional[str],
) -> RawRecord:
    fields = rec.fields()
    out: List[Tuple[bytes, bytes]] = []
    saw_nam2 = False
    saw_nam3 = False
    saw_nam4 = False
    saw_dnam = False
    for s, d in fields:
        if s == b"FULL" and world_display_name is not None:
            out.append((b"FULL", _zstr(world_display_name)))
            continue
        if water_height_m is not None:
            if s == b"NAM2":
                out.append((b"NAM2", struct.pack("<I", water_fid)))
                saw_nam2 = True
                continue
            if s == b"NAM3":
                if not saw_nam2:
                    out.append((b"NAM2", struct.pack("<I", water_fid)))
                    saw_nam2 = True
                out.append((b"NAM3", struct.pack("<I", WATER_CLEAR_FID)))
                saw_nam3 = True
                continue
            if s == b"NAM4":
                out.append((b"NAM4", struct.pack("<f", 0.0)))
                saw_nam4 = True
                continue
            if s == b"DNAM":
                if not saw_nam2:
                    out.append((b"NAM2", struct.pack("<I", water_fid)))
                    saw_nam2 = True
                if not saw_nam3:
                    out.append((b"NAM3", struct.pack("<I", WATER_CLEAR_FID)))
                    saw_nam3 = True
                if not saw_nam4:
                    out.append((b"NAM4", struct.pack("<f", 0.0)))
                    saw_nam4 = True
                out.append((b"DNAM", struct.pack("<2f", float(default_land_m), float(water_height_m))))
                saw_dnam = True
                continue
        out.append((s, d))
    if water_height_m is not None and not saw_dnam:
        if not saw_nam2:
            out.append((b"NAM2", struct.pack("<I", water_fid)))
        if not saw_nam3:
            out.append((b"NAM3", struct.pack("<I", WATER_CLEAR_FID)))
        if not saw_nam4:
            out.append((b"NAM4", struct.pack("<f", 0.0)))
        out.append((b"DNAM", struct.pack("<2f", float(default_land_m), float(water_height_m))))
    return rec.with_fields(out)


def _patch_sfbk_water(rec: RawRecord, water_height_m: float) -> RawRecord:
    fields = rec.fields()
    whgt_bytes = struct.pack("<f", float(water_height_m))
    if any(s == b"WHGT" for s, _ in fields):
        out = [(s, whgt_bytes if s == b"WHGT" else d) for s, d in fields]
    else:
        out = list(fields) + [(b"WHGT", whgt_bytes)]
    return rec.with_fields(out)


def _patch_exterior_cell_water(rec: RawRecord) -> RawRecord:
    fields = rec.fields()
    if not any(s == b"XCLC" for s, _ in fields):
        return rec
    out: List[Tuple[bytes, bytes]] = []
    saw_data = False
    saw_xclw = False
    for s, d in fields:
        if s == b"DATA":
            val = struct.unpack_from("<I", d)[0] if len(d) >= 4 else int(d[0])
            out.append((b"DATA", struct.pack("<I", val | CELL_HAS_WATER)))
            saw_data = True
        elif s == b"XCLC":
            if not saw_data:
                out.append((b"DATA", struct.pack("<I", CELL_HAS_WATER)))
                saw_data = True
            out.append((s, d))
        elif s == b"XCLW":
            out.append((b"XCLW", XCLW_INHERIT_BYTES))
            saw_xclw = True
        else:
            out.append((s, d))
    if not saw_xclw:
        out.append((b"XCLW", XCLW_INHERIT_BYTES))
    return rec.with_fields(out)


def _make_ltex_record(
    full_fid: int,
    edid: str,
    bnam: str,
    mnam_fid: int = DEFAULT_MATT_DIRT_FID,
    version: int = 581,
) -> RawRecord:
    subs = [
        (b"EDID", _zstr(edid)),
        (b"BNAM", _zstr(bnam)),
        (b"MNAM", struct.pack("<I", int(mnam_fid))),
        (b"HNAM", b"\x1e\x1e"),
        (b"QNAM", b"\x00\x00\x00\x00"),
    ]
    payload = b"".join(encode_subrecord(s, d) for s, d in subs)
    hdr = struct.pack("<4sIIIIHH", b"LTEX", len(payload), 0, int(full_fid), 0, int(version), 0)
    return RawRecord(hdr, payload)


def patch_overlay_plugin(
    plugin_path: str,
    *,
    water_height_m: Optional[float] = None,
    water_fid: int = WATER_CLEAR_FID,
    default_land_m: float = -2048.0,
    world_display_name: Optional[str] = None,
    map_marker_name: Optional[str] = None,
    ltex_records: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Patch water records, display labels, and optional `LTEX` records into a staged overlay `.esm`."""
    refuse_unsafe_output_path(plugin_path)
    plug = RawPlugin.read(plugin_path)
    own_hi = len(plug.masters()) << 24

    patched_counts = {"wrld": 0, "sfbk": 0, "exterior_cells": 0, "lctn": 0, "map_markers": 0, "ltex_added": 0}

    def transform_items(items: List[Any]) -> List[Any]:
        res: List[Any] = []
        for it in items:
            if isinstance(it, RawGroup):
                it.children = transform_items(it.children)
                res.append(it)
                continue
            r: RawRecord = it
            if r.sig == b"WRLD" and (water_height_m is not None or world_display_name is not None):
                r = _patch_wrld_water(
                    r,
                    water_height_m=water_height_m,
                    water_fid=water_fid,
                    default_land_m=default_land_m,
                    world_display_name=world_display_name,
                )
                patched_counts["wrld"] += 1
            elif r.sig == b"SFBK" and water_height_m is not None:
                r = _patch_sfbk_water(r, water_height_m)
                patched_counts["sfbk"] += 1
            elif r.sig == b"CELL" and water_height_m is not None:
                r2 = _patch_exterior_cell_water(r)
                if r2 is not r:
                    patched_counts["exterior_cells"] += 1
                r = r2
            elif r.sig == b"LCTN" and world_display_name is not None:
                fields = [(s, _zstr(world_display_name) if s == b"FULL" else d) for s, d in r.fields()]
                r = r.with_fields(fields)
                patched_counts["lctn"] += 1
            elif r.sig == b"REFR" and map_marker_name is not None:
                flds = r.fields()
                if any(s == b"XMRK" for s, _ in flds):
                    flds = [(s, _zstr(map_marker_name) if s == b"FULL" else d) for s, d in flds]
                    r = r.with_fields(flds)
                    patched_counts["map_markers"] += 1
            res.append(r)
        return res

    plug.items = transform_items(plug.items)

    if ltex_records:
        _, rec_count, next_id = plug.hedr()
        ltex_group: Optional[RawGroup] = None
        for it in plug.items:
            if isinstance(it, RawGroup) and it.gtype == 0 and it.label == b"LTEX":
                ltex_group = it
                break
        created_group = False
        if ltex_group is None:
            ltex_group = RawGroup(b"LTEX", 0, b"\x00" * 8, [])
            plug.items.insert(0, ltex_group)
            created_group = True
        max_local = next_id
        for spec in ltex_records:
            local_id = int(spec["fid_local"])
            full_fid = own_hi | (local_id & 0xFFFFFF)
            ltex_group.children.append(
                _make_ltex_record(
                    full_fid=full_fid,
                    edid=str(spec["edid"]),
                    bnam=str(spec["bnam"]),
                    mnam_fid=int(spec.get("mnam", DEFAULT_MATT_DIRT_FID)),
                )
            )
            patched_counts["ltex_added"] += 1
            if (local_id & 0xFFFFFF) + 1 > max_local:
                max_local = (local_id & 0xFFFFFF) + 1
        plug.set_hedr(rec_count + (1 if created_group else 0) + len(ltex_records), max_local)

    data = plug.serialize()
    _atomic_write_bytes(plugin_path, data)
    return patched_counts


def patch_mars_plugin_extra_worlds(
    mars_plugin_path: str,
    overlays_params_path: str,
    extra_worlds: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Append external worldspace `PNDT` `CNAM` entries (`Commonwealth`, sibling DLC worlds) to `<mars_plugin>`."""
    refuse_unsafe_output_path(mars_plugin_path)
    refuse_unsafe_output_path(overlays_params_path)
    if not extra_worlds:
        return {"added_entries": 0}

    plug = RawPlugin.read(mars_plugin_path)
    resolved_entries: List[Tuple[float, float, int, Dict[str, Any]]] = []
    for ew in extra_worlds:
        p_name = str(ew["plugin"])
        m_idx = plug.add_master(p_name)
        local_fid = int(ew["wrld_local_fid"]) & 0xFFFFFF
        lat = float(ew["latitude"])
        lon = float(ew["longitude"])
        full_fid = (m_idx << 24) | local_fid
        resolved_entries.append((lat, lon, full_fid, dict(ew)))

    patched_pndt = 0

    def walk_patch(items: List[Any]) -> List[Any]:
        nonlocal patched_pndt
        out: List[Any] = []
        for it in items:
            if isinstance(it, RawGroup):
                it.children = walk_patch(it.children)
                out.append(it)
            elif isinstance(it, RawRecord) and it.sig == b"PNDT":
                fields = it.fields()
                in_body = False
                new_fields: List[Tuple[bytes, bytes]] = []
                updated = False
                for s, d in fields:
                    if s == b"BDST":
                        in_body = True
                    elif s == b"BDED":
                        in_body = False
                    if s == b"CNAM" and not in_body and not updated and len(d) % 20 == 0:
                        existing = [struct.unpack_from("<ddI", d, k) for k in range(0, len(d), 20)]
                        existing_fids = {e[2] for e in existing}
                        buf = bytearray(d)
                        for lat, lon, ffid, _ in resolved_entries:
                            if ffid not in existing_fids:
                                buf.extend(struct.pack("<ddI", lat, lon, ffid))
                                existing_fids.add(ffid)
                        new_fields.append((b"CNAM", bytes(buf)))
                        updated = True
                    else:
                        new_fields.append((s, d))
                out.append(it.with_fields(new_fields))
                patched_pndt += 1
            else:
                out.append(it)
        return out

    plug.items = walk_patch(plug.items)
    if patched_pndt != 1:
        raise ValueError(f"Expected 1 PNDT record in {mars_plugin_path}, found {patched_pndt}")
    _atomic_write_bytes(mars_plugin_path, plug.serialize())

    with open(overlays_params_path, encoding="utf-8") as f:
        prm = json.load(f)
    if prm.get("mars"):
        prm["mars"]["extra_worlds"] = [dict(ew) for ew in extra_worlds]
        _atomic_write_json(overlays_params_path, prm, indent=1)
    return {"added_entries": len(resolved_entries), "masters": plug.masters()}


def _latlon_distance_cells(a: Tuple[float, float], b: Tuple[float, float], radius_km: float = og.MARS_RADIUS_KM) -> float:
    k = og.cells_per_radian(radius_km)
    dlon = (b[1] - a[1] + math.pi) % (2.0 * math.pi) - math.pi
    return math.hypot((b[0] - a[0]) * k, dlon * k * math.cos((a[0] + b[0]) * 0.5))


def verify_dlc_terrain_stage(
    stage_dir: str,
    fo4_paths: Sequence[str],
    fo4_world: str,
    *,
    n_probes: int = 8,
    min_gap_cells: int = 2000,
) -> Dict[str, Any]:
    """Offline acceptance verification for a staged DLC terrain-only world (`WD2` / `WD3`)."""
    refuse_unsafe_output_path(stage_dir)
    prm_path = os.path.join(stage_dir, "overlays_params.json")
    with open(prm_path, encoding="utf-8") as f:
        prm = json.load(f)

    if len(prm["overlays"]) != 1:
        raise ValueError(f"Expected single-tile DLC world, got {len(prm['overlays'])} overlays")
    ov = prm["overlays"][0]
    plugin_path = os.path.join(stage_dir, prm["plugin"])
    plug = RawPlugin.read(plugin_path)

    wrlds: List[RawRecord] = []
    sfbks: List[RawRecord] = []
    lctns: List[RawRecord] = []
    ext_cells: List[RawRecord] = []
    top_cells: List[RawRecord] = []
    refrs: List[RawRecord] = []

    def collect(items: Iterable[Any]) -> None:
        for it in items:
            if isinstance(it, RawGroup):
                collect(it.children)
            elif isinstance(it, RawRecord):
                if it.sig == b"WRLD":
                    wrlds.append(it)
                elif it.sig == b"SFBK":
                    sfbks.append(it)
                elif it.sig == b"LCTN":
                    lctns.append(it)
                elif it.sig == b"CELL":
                    if any(s == b"XCLC" for s, _ in it.fields()):
                        ext_cells.append(it)
                    else:
                        top_cells.append(it)
                elif it.sig == b"REFR":
                    refrs.append(it)

    collect(plug.items)
    n = int(ov["n"])
    if len(wrlds) != 1:
        raise AssertionError(f"Expected 1 WRLD, found {len(wrlds)}")
    if len(ext_cells) != n * n:
        raise AssertionError(f"Expected {n * n} exterior CELLs, found {len(ext_cells)}")
    if len(top_cells) != 1:
        raise AssertionError(f"Expected 1 persistent top CELL, found {len(top_cells)}")

    want_wh = prm.get("water_height_m")
    water_cells_ok = 0
    if want_wh is not None:
        for c in ext_cells:
            fmap = dict(c.fields())
            d_flag = struct.unpack_from("<I", fmap[b"DATA"])[0] if b"DATA" in fmap and len(fmap[b"DATA"]) >= 4 else 0
            if (d_flag & CELL_HAS_WATER) and fmap.get(b"XCLW") == XCLW_INHERIT_BYTES:
                water_cells_ok += 1
        if water_cells_ok != n * n:
            raise AssertionError(f"Only {water_cells_ok}/{n * n} exterior cells carry HasWater + XCLW inherit")

    # Decode BTD and compare >= 5 spread-out real FO4 LAND cell centres directly against FO4 VHGT
    btd_path = os.path.join(stage_dir, *ov["btd_file"].split("/"))
    with open(btd_path, "rb") as f:
        b = btd.read(f.read())
    tile = og.Tile(ov["ix"], ov["iy"], ov["cells_cw"]["x"][0], ov["cells_cw"]["y"][0], n)

    world_data = fo4land.read_world_load_order(fo4_paths, fo4_world, refs=False)
    vhgt_cells = sorted(xy for xy, c in world_data["cells"].items() if c["vhgt"])
    # Filter to FO4 cells well inside the tile bounds
    bx0, bx1, by0, by1 = tile.bounds_m
    fo4_cell_m = tg.FO4_CELL_UNITS / tg.UNITS_PER_METRE
    eligible_cells = []
    for cx, cy in vhgt_cells:
        # Centre vertex (16, 16) of FO4 cell (cx, cy)
        x_cw = (cx * 32 + 16) * (fo4_cell_m / 32.0)
        y_cw = (cy * 32 + 16) * (fo4_cell_m / 32.0)
        if bx0 + 150.0 <= x_cw <= bx1 - 150.0 and by0 + 150.0 <= y_cw <= by1 - 150.0:
            eligible_cells.append((cx, cy))
    if len(eligible_cells) < max(5, n_probes):
        eligible_cells = vhgt_cells
    idxs = np.linspace(0, len(eligible_cells) - 1, max(5, n_probes), dtype=int)
    picked = [eligible_cells[int(i)] for i in idxs]

    probes: List[Dict[str, Any]] = []
    for cx, cy in picked:
        grid_u = fo4land.decode_vhgt(world_data["cells"][(cx, cy)]["vhgt"])
        fo4_m = float(grid_u[16, 16]) / tg.UNITS_PER_METRE
        x_cw = (cx * 32 + 16) * (fo4_cell_m / 32.0)
        y_cw = (cy * 32 + 16) * (fo4_cell_m / 32.0)
        lx, ly = tile.to_local(x_cw, y_cw)
        # Bilinear sample on BTD [ncy*128, ncx*128] lattice
        origin_m = tg.grid_origin(n)
        col_f = (lx - origin_m) * (128.0 / tg.SF_CELL_M)
        row_f = (ly - origin_m) * (128.0 / tg.SF_CELL_M)
        r0 = max(0, min(b.heights_raw.shape[0] - 2, int(math.floor(row_f))))
        c0 = max(0, min(b.heights_raw.shape[1] - 2, int(math.floor(col_f))))
        fr = row_f - r0
        fc = col_f - c0
        h00 = b.hmin + float(b.heights_raw[r0, c0]) / 65535.0 * (b.hmax - b.hmin)
        h01 = b.hmin + float(b.heights_raw[r0, c0 + 1]) / 65535.0 * (b.hmax - b.hmin)
        h10 = b.hmin + float(b.heights_raw[r0 + 1, c0]) / 65535.0 * (b.hmax - b.hmin)
        h11 = b.hmin + float(b.heights_raw[r0 + 1, c0 + 1]) / 65535.0 * (b.hmax - b.hmin)
        btd_m = (1.0 - fr) * ((1.0 - fc) * h00 + fc * h01) + fr * ((1.0 - fc) * h10 + fc * h11)
        err_m = abs(btd_m - fo4_m)
        probes.append(
            {
                "fo4_cell": [cx, cy],
                "local_xy_m": [round(lx, 3), round(ly, 3)],
                "fo4_height_m": round(fo4_m, 4),
                "btd_height_m": round(btd_m, 4),
                "abs_error_m": round(err_m, 5),
            }
        )

    max_err_m = max(p["abs_error_m"] for p in probes)
    if max_err_m >= 1.0:
        raise AssertionError(f"Probe height error {max_err_m:.4f} m >= 1.0 m")

    # Planet separation check on Mars plugin
    nearest_cells: Optional[float] = None
    nearest_fid: Optional[str] = None
    mars_entries_count = 0
    if prm.get("mars"):
        mars_path = os.path.join(stage_dir, prm["mars"]["plugin"])
        mplug = RawPlugin.read(mars_path)
        own_m_idx = mplug.masters().index(prm["plugin"])
        own_wrld_ffid = (own_m_idx << 24) | (wrlds[0].fid & 0xFFFFFF)
        pndt_rec = next(
            it
            for g in mplug.items
            if isinstance(g, RawGroup)
            for it in g.children
            if isinstance(it, RawRecord) and it.sig == b"PNDT"
        )
        in_body = False
        cnam_bytes = b""
        for s, d in pndt_rec.fields():
            if s == b"BDST":
                in_body = True
            elif s == b"BDED":
                in_body = False
            elif s == b"CNAM" and not in_body and len(d) % 20 == 0:
                cnam_bytes = d
                break
        ents = [struct.unpack_from("<ddI", cnam_bytes, k) for k in range(0, len(cnam_bytes), 20)]
        mars_entries_count = len(ents)
        mine = next(e for e in ents if e[2] == own_wrld_ffid)
        others = [e for e in ents if e[2] != own_wrld_ffid]
        radius_km = float(prm["mars"].get("radius_km", og.MARS_RADIUS_KM))
        near = min(others, key=lambda e: _latlon_distance_cells((mine[0], mine[1]), (e[0], e[1]), radius_km))
        nearest_cells = round(_latlon_distance_cells((mine[0], mine[1]), (near[0], near[1]), radius_km), 1)
        nearest_fid = f"{near[2]:08X}"
        if nearest_cells < min_gap_cells:
            raise AssertionError(f"Nearest world {nearest_fid} is {nearest_cells} cells away (< {min_gap_cells})")

    report = {
        "plugin": prm["plugin"],
        "world": ov["world"],
        "fo4_world": fo4_world,
        "tile_cells": n,
        "wrld_count": len(wrlds),
        "exterior_cell_count": len(ext_cells),
        "persistent_cell_count": len(top_cells),
        "sfbk_count": len(sfbks),
        "lctn_count": len(lctns),
        "refr_count": len(refrs),
        "water_height_m": want_wh,
        "water_exterior_cells_verified": water_cells_ok,
        "btd_height_range_m": [round(b.hmin, 3), round(b.hmax, 3)],
        "probe_count": len(probes),
        "max_probe_abs_error_m": round(max_err_m, 5),
        "probes": probes,
        "planet_target_cell": ov["planet_target_cell"],
        "planet_lat_lon_rad": [round(ov["latitude"], 9), round(ov["longitude"], 9)],
        "mars_pndt_total_entries": mars_entries_count,
        "nearest_other_world_fid": nearest_fid,
        "nearest_other_world_distance_cells": nearest_cells,
    }
    out_json = os.path.join(stage_dir, "dlc_terrain_verification.json")
    refuse_unsafe_output_path(out_json)
    _atomic_write_json(out_json, report, indent=2)
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Post-patch and verify staged DLC terrain overlay worlds.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_patch = sub.add_parser("postpatch", help="Apply water/display/Mars multi-world patches to a staged overlay dir")
    p_patch.add_argument("--stage-dir", required=True)
    p_patch.add_argument("--water-height-m", type=float, default=None)
    p_patch.add_argument("--water-fid", type=lambda s: int(s, 0), default=WATER_CLEAR_FID)
    p_patch.add_argument("--world-display-name", default=None)
    p_patch.add_argument("--map-marker-name", default=None)
    p_patch.add_argument("--extra-world", action="append", default=[], help="plugin:wrld_local_hex:lat:lon:label")

    p_ver = sub.add_parser("verify", help="Verify staged DLC terrain world against FO4 LAND and Mars separation")
    p_ver.add_argument("--stage-dir", required=True)
    p_ver.add_argument("--fo4", required=True)
    p_ver.add_argument("--fo4-world", required=True)
    p_ver.add_argument("--fo4-masters", nargs="*", default=[])
    p_ver.add_argument("--probes", type=int, default=8)
    p_ver.add_argument("--min-gap-cells", type=int, default=2000)

    args = ap.parse_args(argv)
    if args.cmd == "postpatch":
        prm_path = os.path.join(args.stage_dir, "overlays_params.json")
        with open(prm_path, encoding="utf-8") as f:
            prm = json.load(f)
        wh = args.water_height_m if args.water_height_m is not None else prm.get("water_height_m")
        plugin_path = os.path.join(args.stage_dir, prm["plugin"])
        p_res = patch_overlay_plugin(
            plugin_path,
            water_height_m=wh,
            water_fid=args.water_fid,
            world_display_name=args.world_display_name,
            map_marker_name=args.map_marker_name,
        )
        m_res = {}
        if args.extra_world and prm.get("mars"):
            ews = []
            for spec in args.extra_world:
                plg, fid_s, lat_s, lon_s, lbl = spec.split(":", 4)
                ews.append(
                    {
                        "plugin": plg,
                        "wrld_local_fid": int(fid_s, 16),
                        "latitude": float(lat_s),
                        "longitude": float(lon_s),
                        "label": lbl,
                    }
                )
            mars_path = os.path.join(args.stage_dir, prm["mars"]["plugin"])
            m_res = patch_mars_plugin_extra_worlds(mars_path, prm_path, ews)
        print(json.dumps({"overlay_patch": p_res, "mars_patch": m_res}, indent=2))
        return 0

    if args.cmd == "verify":
        rep = verify_dlc_terrain_stage(
            args.stage_dir,
            [*args.fo4_masters, args.fo4],
            args.fo4_world,
            n_probes=args.probes,
            min_gap_cells=args.min_gap_cells,
        )
        print(json.dumps(rep, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
