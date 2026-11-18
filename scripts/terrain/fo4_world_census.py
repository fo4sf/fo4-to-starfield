"""Read-only Fallout 4 worldspace, location, map-marker, and world-to-world door census.

Walks Fallout 4 and DLC `.esm` plugins in load order using `src/fo4sf/fo4land.py` (memory-mapped raw reader, no Mutagen)
and reports:
  - Per-worldspace land cell `(x, y)` bounds, land cell counts (`VHGT` and raw `LAND`), reference cell `(x, y)` bounds,
    dry-land bounds, height range in metres, placed/persistent reference counts, map marker (`XMRK`) counts, `LCTN`
    location counts, `ECZN` encounter-zone counts, and `REGN` region counts (both merged in load order and per plugin).
  - Full `LCTN` metadata rows (`form_key`, `form_id`, `edid`, `defining_plugin`, `parent_lctn`, `world_key`) with zero
    display strings (`FULL` / `DESC` are never read or emitted).
  - World-to-world `DOOR` `XTEL` load-door pairs across the load order.

Refuses any output path inside a Git repository/worktree, inside a game installation directory, or aliasing an input.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import struct
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
if os.path.join(REPO, "src") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "src"))

from fo4sf import fo4land as fl  # noqa: E402

DEFAULT_FO4_PLUGINS: Tuple[str, ...] = (
    "Fallout4.esm",
    "DLCRobot.esm",
    "DLCworkshop01.esm",
    "DLCCoast.esm",
    "DLCworkshop02.esm",
    "DLCworkshop03.esm",
    "DLCNukaWorld.esm",
)

DELETED = 0x00000020
CELL_INTERIOR = 0x0001
GROUP_WORLD = 1
GROUP_INT_BLOCK = 2
GROUP_INT_SUB = 3
GROUP_EXT_BLOCK = 4
GROUP_EXT_SUB = 5
GROUP_CELL = 6
GROUP_PERSISTENT = 8
GROUP_TEMPORARY = 9

GAME_INSTALL_MARKERS = frozenset(
    {
        "starfield.exe",
        "fallout4.exe",
        "fallout4launcher.exe",
        "starfield.ccc",
        "fallout4.ccc",
        "creationkit.exe",
    }
)
GAME_DATA_ESMS = frozenset({"starfield.esm", "fallout4.esm"})
SAFE_WORLD_RAW_SIGS = (
    b"DNAM",
    b"MNAM",
    b"NAM0",
    b"NAM9",
    b"ONAM",
    b"DATA",
    b"PNAM",
    b"WNAM",
    b"CNAM",
    b"XLCN",
)


class CensusPathError(ValueError):
    """Raised when an output path lies inside a Git worktree, game directory, or aliases an input."""


def _ancestor_dirs(path: str) -> List[str]:
    cur = os.path.abspath(path)
    if not os.path.isdir(cur):
        cur = os.path.dirname(cur)
    out: List[str] = []
    while True:
        out.append(cur)
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return out


def _is_within(child: str, root: str) -> bool:
    c_norm = os.path.normcase(os.path.abspath(child))
    r_norm = os.path.normcase(os.path.abspath(root))
    try:
        return os.path.commonpath([c_norm, r_norm]) == r_norm
    except ValueError:
        return False


def refuse_unsafe_output_path(out_path: str, input_paths: Sequence[str] = ()) -> None:
    """Refuse writing inside any Git repository/worktree, game installation directory, or input file alias."""
    if not out_path or not out_path.strip():
        raise CensusPathError("refused: empty output path")

    base_targets = [
        os.path.abspath(out_path),
        os.path.realpath(os.path.abspath(out_path)),
    ]
    candidates = base_targets + [
        os.path.abspath(out_path + ".tmp"),
        os.path.realpath(os.path.abspath(out_path + ".tmp")),
    ]

    for btarget in base_targets:
        t_norm = os.path.normcase(os.path.normpath(btarget))
        for src in input_paths:
            if not src:
                continue
            src_abs = os.path.abspath(src)
            src_real = os.path.realpath(src_abs)
            for s_cand in (src_abs, src_real):
                s_norm = os.path.normcase(os.path.normpath(s_cand))
                if t_norm == s_norm:
                    raise CensusPathError(f"refused: output path aliases input plugin {os.path.basename(src)}")
                try:
                    common = os.path.normcase(os.path.normpath(os.path.commonpath([t_norm, s_norm])))
                except ValueError:
                    continue
                if common == t_norm:
                    raise CensusPathError(f"refused: output path is a parent/ancestor of input {os.path.basename(src)}")
                if common == s_norm:
                    raise CensusPathError(f"refused: output path lies inside input {os.path.basename(src)}")

    for target in candidates:
        for src in input_paths:
            if not src:
                continue
            src_abs = os.path.abspath(src)
            src_real = os.path.realpath(src_abs)
            if os.path.normcase(target) in (os.path.normcase(src_abs), os.path.normcase(src_real)):
                raise CensusPathError(f"refused: output path aliases input plugin {os.path.basename(src)}")
            if os.path.exists(target) and os.path.exists(src_abs) and os.path.samefile(target, src_abs):
                raise CensusPathError(f"refused: output path is same file as input plugin {os.path.basename(src)}")

        parts_lower = [p.lower() for p in target.replace("\\", "/").split("/") if p]
        for idx in range(len(parts_lower) - 1):
            if parts_lower[idx] == "steamapps" and parts_lower[idx + 1] == "common":
                raise CensusPathError("refused: output path is inside a Steam game installation directory")

        for anc in _ancestor_dirs(target):
            if os.path.exists(os.path.join(anc, ".git")):
                raise CensusPathError("refused: output path is inside a Git worktree or repository")
            try:
                entries_lower = {e.lower() for e in os.listdir(anc)}
            except OSError:
                entries_lower = set()
            if entries_lower & GAME_INSTALL_MARKERS:
                raise CensusPathError("refused: output path is inside a game installation directory")
            if os.path.basename(anc).lower() == "data" and (entries_lower & GAME_DATA_ESMS):
                raise CensusPathError("refused: output path is inside a game Data directory")

        for src in input_paths:
            src_dir = os.path.dirname(os.path.realpath(os.path.abspath(src)))
            if os.path.basename(src_dir).lower() == "data":
                game_root = os.path.dirname(src_dir)
                if _is_within(target, game_root):
                    raise CensusPathError("refused: output path is inside the input plugin's game directory")
            else:
                try:
                    src_entries = {e.lower() for e in os.listdir(src_dir)}
                except OSError:
                    src_entries = set()
                if (src_entries & GAME_INSTALL_MARKERS) and _is_within(target, src_dir):
                    raise CensusPathError("refused: output path is inside a game installation directory")


def _u32(data: bytes, offset: int = 0) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _bbox(coords: Iterable[Tuple[int, int]]) -> Optional[List[int]]:
    pts = list(coords)
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return [min(xs), max(xs), min(ys), max(ys)]


def _form_key(plugin_name: str, masters: Sequence[str], fid: int) -> Tuple[str, int, str]:
    idx = (fid >> 24) & 0xFF
    local = fid & 0xFFFFFF
    owner = masters[idx] if idx < len(masters) else plugin_name
    return owner, local, f"{owner}:{local:06X}"


def _hex_id(local_fid: int) -> str:
    return f"0x{local_fid & 0xFFFFFF:06X}"


def _decode_world_struct_fields(raw_map: Dict[bytes, bytes]) -> Dict[str, Any]:
    decoded: Dict[str, Any] = {}
    if b"DNAM" in raw_map and len(raw_map[b"DNAM"]) >= 8:
        land_h, water_h = struct.unpack_from("<ff", raw_map[b"DNAM"], 0)
        decoded["dnam_land_units"] = round(float(land_h), 3)
        decoded["dnam_water_units"] = round(float(water_h), 3)
        decoded["dnam_land_m"] = round(float(land_h) / fl.UNITS_PER_METRE, 3)
        decoded["dnam_water_m"] = round(float(water_h) / fl.UNITS_PER_METRE, 3)
    if b"MNAM" in raw_map and len(raw_map[b"MNAM"]) >= 16:
        uw, uh, nwx, nwy, sex, sey = struct.unpack_from("<IIhhhh", raw_map[b"MNAM"], 0)
        decoded["mnam"] = {
            "usable_width": uw,
            "usable_height": uh,
            "nw_cell": [nwx, nwy],
            "se_cell": [sex, sey],
        }
    if b"ONAM" in raw_map and len(raw_map[b"ONAM"]) >= 16:
        vals = struct.unpack_from("<4f", raw_map[b"ONAM"], 0)
        decoded["onam"] = [round(float(v), 6) for v in vals]
    return decoded


def run_fo4_census(plugin_paths: Sequence[str]) -> Dict[str, Any]:
    """Walk `plugin_paths` in load order and return a redacted, JSON-serializable census dictionary."""
    if not plugin_paths:
        raise ValueError("at least one Fallout 4 plugin path is required")

    plugin_names = [os.path.basename(p) for p in plugin_paths]
    lower_names = [n.lower() for n in plugin_names]
    if "fallout4.esm" in lower_names and lower_names[0] != "fallout4.esm":
        raise ValueError("Fallout4.esm must come first in load order")

    # Merged load-order state
    worlds: Dict[str, Dict[str, Any]] = {}
    locations: Dict[str, Dict[str, Any]] = {}
    eczn: Dict[str, Dict[str, Any]] = {}
    regn: Dict[str, Dict[str, Any]] = {}
    door_bases: set[str] = set()

    # Cell & reference tracking for overrides and deletions
    ext_cells: Dict[str, Dict[str, Any]] = {}   # cell_key -> {world_key, xy, xlcn}
    int_cells: Dict[str, Dict[str, Any]] = {}   # cell_key -> {xlcn}
    land_by_key: Dict[str, Dict[str, Any]] = {} # land_key -> {world_key, xy, has_vhgt, is_dry, zmin_m, zmax_m}
    refs_by_key: Dict[str, Dict[str, Any]] = {} # ref_key -> {place_kind, place_id, xy, persistent, is_marker, xtel, base_key, plugin}
    marker_lctns: set[str] = set()

    per_plugin_reports: List[Dict[str, Any]] = []

    for path in plugin_paths:
        pname = os.path.basename(path)
        p_counts: Dict[str, int] = {"WRLD": 0, "LCTN": 0, "ECZN": 0, "REGN": 0}
        p_new_counts: Dict[str, int] = {"WRLD": 0, "LCTN": 0, "ECZN": 0, "REGN": 0}
        p_interior_markers = 0
        p_worlds_touched: Dict[str, Dict[str, Any]] = {}

        def _touch_world(wkey: str) -> Dict[str, Any]:
            if wkey not in p_worlds_touched:
                p_worlds_touched[wkey] = {
                    "cells": set(),
                    "land_records": 0,
                    "land_xy": set(),
                    "dry_xy": set(),
                    "ref_xy": set(),
                    "placed_refs": 0,
                    "persistent_refs": 0,
                    "map_markers": 0,
                    "zmin_m": None,
                    "zmax_m": None,
                }
            return p_worlds_touched[wkey]

        with fl.Plugin(path) as plug:
            buf = plug.buf
            hdr_subs = list(fl.iter_subrecords(fl.record_data(buf, 0)))
            masters = [fl.zstring(d) for s, d in hdr_subs if s == b"MAST"]

            def fk(fid: int) -> Tuple[str, int, str]:
                return _form_key(pname, masters, fid)

            def walk_cell_children(
                start: int,
                end: int,
                place_kind: str,
                place_id: str,
                cell_xy: Optional[Tuple[int, int]],
                is_persistent_cell: bool,
                persistent_group: bool,
            ) -> None:
                for item in fl.iter_items(buf, start, end):
                    if item[0] == "GRUP":
                        _g, goff, gend, _glab, gtype = item
                        walk_cell_children(
                            goff + 24,
                            gend,
                            place_kind,
                            place_id,
                            cell_xy,
                            is_persistent_cell,
                            persistent_group or (gtype == GROUP_PERSISTENT),
                        )
                        continue
                    typ, roff, rflags, rfid = item
                    _owner, _local, rkey = fk(rfid)
                    if typ == b"LAND" and place_kind == "world":
                        if rflags & DELETED:
                            land_by_key.pop(rkey, None)
                            continue
                        tw = _touch_world(place_id)
                        tw["land_records"] += 1
                        has_vhgt = False
                        is_dry = False
                        zmin_m: Optional[float] = None
                        zmax_m: Optional[float] = None
                        for s, d in fl.iter_subrecords(fl.record_data(buf, roff)):
                            if s == b"VHGT" and len(d) >= fl.VHGT_MIN_SIZE:
                                has_vhgt = True
                                grid_m = fl.decode_vhgt(d) / fl.UNITS_PER_METRE
                                lo = round(float(grid_m.min()), 2)
                                hi = round(float(grid_m.max()), 2)
                                zmin_m = lo if zmin_m is None else min(zmin_m, lo)
                                zmax_m = hi if zmax_m is None else max(zmax_m, hi)
                                if float(grid_m.max()) > 0.5:
                                    is_dry = True
                        if cell_xy is not None:
                            if has_vhgt:
                                tw["land_xy"].add(cell_xy)
                            if is_dry:
                                tw["dry_xy"].add(cell_xy)
                        if zmin_m is not None:
                            tw["zmin_m"] = zmin_m if tw["zmin_m"] is None else min(tw["zmin_m"], zmin_m)
                        if zmax_m is not None:
                            tw["zmax_m"] = zmax_m if tw["zmax_m"] is None else max(tw["zmax_m"], zmax_m)
                        land_by_key[rkey] = {
                            "world_key": place_id,
                            "xy": cell_xy,
                            "has_vhgt": has_vhgt,
                            "is_dry": is_dry,
                            "zmin_m": zmin_m,
                            "zmax_m": zmax_m,
                        }
                    elif typ in (b"REFR", b"ACHR"):
                        if rflags & DELETED:
                            refs_by_key.pop(rkey, None)
                            continue
                        base_key: Optional[str] = None
                        xtel_key: Optional[str] = None
                        xlcn_key: Optional[str] = None
                        is_marker = False
                        for s, d in fl.iter_subrecords(fl.record_data(buf, roff)):
                            if s == b"NAME" and len(d) >= 4:
                                base_key = fk(_u32(d))[2]
                            elif s == b"XTEL" and len(d) >= 4 and _u32(d) != 0:
                                xtel_key = fk(_u32(d))[2]
                            elif s == b"XMRK" and typ == b"REFR":
                                is_marker = True
                            elif s == b"XLCN" and len(d) >= 4 and _u32(d) != 0:
                                xlcn_key = fk(_u32(d))[2]
                        is_pers = is_persistent_cell or persistent_group
                        if place_kind == "world":
                            tw = _touch_world(place_id)
                            tw["placed_refs"] += 1
                            if is_pers:
                                tw["persistent_refs"] += 1
                            elif cell_xy is not None:
                                tw["ref_xy"].add(cell_xy)
                            if is_marker:
                                tw["map_markers"] += 1
                                if xlcn_key:
                                    marker_lctns.add(xlcn_key)
                        elif is_marker:
                            nonlocal p_interior_markers
                            p_interior_markers += 1
                            if xlcn_key:
                                marker_lctns.add(xlcn_key)
                        refs_by_key[rkey] = {
                            "place_kind": place_kind,
                            "place_id": place_id,
                            "xy": None if is_persistent_cell else cell_xy,
                            "persistent": is_pers,
                            "is_marker": is_marker,
                            "xtel": xtel_key,
                            "base_key": base_key,
                            "plugin": pname,
                        }

            def walk_cells(start: int, end: int, world_key: Optional[str], in_ext_block: bool) -> None:
                cur_cell_key: Optional[str] = None
                cur_cell_xy: Optional[Tuple[int, int]] = None
                cur_is_pers_cell = False
                for item in fl.iter_items(buf, start, end):
                    if item[0] == "GRUP":
                        _g, goff, gend, glab, gtype = item
                        if gtype in (GROUP_INT_BLOCK, GROUP_INT_SUB):
                            walk_cells(goff + 24, gend, world_key, False)
                        elif gtype in (GROUP_EXT_BLOCK, GROUP_EXT_SUB):
                            walk_cells(goff + 24, gend, world_key, True)
                        elif gtype == GROUP_CELL and cur_cell_key is not None and fk(_u32(glab))[2] == cur_cell_key:
                            walk_cell_children(
                                goff + 24,
                                gend,
                                "world" if world_key is not None else "interior",
                                world_key if world_key is not None else cur_cell_key,
                                cur_cell_xy,
                                cur_is_pers_cell,
                                False,
                            )
                        continue
                    typ, coff, cflags, cfid = item
                    if typ != b"CELL":
                        cur_cell_key = None
                        continue
                    _cowner, _clocal, ckey = fk(cfid)
                    if cflags & DELETED:
                        ext_cells.pop(ckey, None)
                        int_cells.pop(ckey, None)
                        cur_cell_key = None
                        continue
                    csubs = list(fl.iter_subrecords(fl.record_data(buf, coff)))
                    xy: Optional[Tuple[int, int]] = None
                    xlcn_key: Optional[str] = None
                    data_flags = 0
                    for s, d in csubs:
                        if s == b"XCLC" and len(d) >= 8:
                            xy = struct.unpack_from("<ii", d, 0)
                        elif s == b"XLCN" and len(d) >= 4 and _u32(d) != 0:
                            xlcn_key = fk(_u32(d))[2]
                        elif s == b"DATA" and len(d) >= 2:
                            data_flags = struct.unpack_from("<H", d, 0)[0]
                    cur_cell_key = ckey
                    if world_key is not None:
                        tw = _touch_world(world_key)
                        if not in_ext_block or xy is None:
                            cur_is_pers_cell = True
                            cur_cell_xy = None
                        else:
                            cur_is_pers_cell = False
                            cur_cell_xy = xy
                            tw["cells"].add(xy)
                            ext_cells[ckey] = {"world_key": world_key, "xy": xy, "xlcn": xlcn_key}
                    else:
                        cur_is_pers_cell = False
                        cur_cell_xy = None
                        if data_flags & CELL_INTERIOR:
                            int_cells[ckey] = {"xlcn": xlcn_key}

            for item in fl.iter_items(buf, plug.body, len(buf)):
                if item[0] != "GRUP":
                    continue
                _g, goff, gend, glab, _gtype = item
                label = bytes(glab)
                if label == b"CELL":
                    walk_cells(goff + 24, gend, None, False)
                elif label == b"WRLD":
                    cur_world_key: Optional[str] = None
                    for witem in fl.iter_items(buf, goff + 24, gend):
                        if witem[0] == "GRUP":
                            _wg, woff, wend, wlab, wgtype = witem
                            if wgtype == GROUP_WORLD:
                                target_wkey = fk(_u32(wlab))[2]
                                walk_cells(woff + 24, wend, target_wkey, False)
                            continue
                        wtyp, wroff, wrflags, wrfid = witem
                        if wtyp != b"WRLD":
                            continue
                        wowner, wlocal, wkey = fk(wrfid)
                        if wrflags & DELETED:
                            worlds.pop(wkey, None)
                            cur_world_key = None
                            continue
                        p_counts["WRLD"] += 1
                        if wowner == pname:
                            p_new_counts["WRLD"] += 1
                        cur_world_key = wkey
                        _touch_world(wkey)
                        wsubs = list(fl.iter_subrecords(fl.record_data(buf, wroff)))
                        edid = next((fl.zstring(d) for s, d in wsubs if s == b"EDID"), "")
                        raw_map = {s: bytes(d) for s, d in wsubs if s in SAFE_WORLD_RAW_SIGS}
                        parent_key = fk(_u32(raw_map[b"WNAM"]))[2] if b"WNAM" in raw_map and len(raw_map[b"WNAM"]) >= 4 and _u32(raw_map[b"WNAM"]) else None
                        xlcn_key = fk(_u32(raw_map[b"XLCN"]))[2] if b"XLCN" in raw_map and len(raw_map[b"XLCN"]) >= 4 and _u32(raw_map[b"XLCN"]) else None
                        cnam_key = fk(_u32(raw_map[b"CNAM"]))[2] if b"CNAM" in raw_map and len(raw_map[b"CNAM"]) >= 4 and _u32(raw_map[b"CNAM"]) else None
                        entry = worlds.get(wkey)
                        if entry is None:
                            entry = {
                                "form_key": wkey,
                                "defining_plugin": wowner,
                                "form_id": _hex_id(wlocal),
                                "edid": edid,
                                "plugins": [],
                                "parent_world": parent_key,
                                "location": xlcn_key,
                                "climate": cnam_key,
                                "raw_subrecords": {},
                            }
                            worlds[wkey] = entry
                        if pname not in entry["plugins"]:
                            entry["plugins"].append(pname)
                        if edid:
                            entry["edid"] = edid
                        if parent_key is not None:
                            entry["parent_world"] = parent_key
                        if xlcn_key is not None:
                            entry["location"] = xlcn_key
                        if cnam_key is not None:
                            entry["climate"] = cnam_key
                        for rs, rd in raw_map.items():
                            entry["raw_subrecords"][rs.decode("ascii")] = rd.hex()[:96]
                        entry["decoded_fields"] = _decode_world_struct_fields(
                            {k.encode("ascii"): bytes.fromhex(v) for k, v in entry["raw_subrecords"].items()}
                        )
                elif label in (b"LCTN", b"ECZN", b"REGN", b"DOOR"):
                    for rec in fl.iter_items(buf, goff + 24, gend):
                        if rec[0] == "GRUP":
                            continue
                        rtyp, roff, rflags, rfid = rec
                        rowner, rlocal, rkey = fk(rfid)
                        if rtyp == b"DOOR":
                            if rflags & DELETED:
                                door_bases.discard(rkey)
                            else:
                                door_bases.add(rkey)
                            continue
                        tname = rtyp.decode("ascii")
                        if rflags & DELETED:
                            if rtyp == b"LCTN":
                                locations.pop(rkey, None)
                            elif rtyp == b"ECZN":
                                eczn.pop(rkey, None)
                            elif rtyp == b"REGN":
                                regn.pop(rkey, None)
                            continue
                        if tname in p_counts:
                            p_counts[tname] += 1
                            if rowner == pname:
                                p_new_counts[tname] += 1
                        rsubs = list(fl.iter_subrecords(fl.record_data(buf, roff)))
                        edid = next((fl.zstring(d) for s, d in rsubs if s == b"EDID"), "")
                        if rtyp == b"LCTN":
                            pnam_key: Optional[str] = None
                            nam1_key: Optional[str] = None
                            for s, d in rsubs:
                                if s == b"PNAM" and len(d) >= 4 and _u32(d) != 0:
                                    pnam_key = fk(_u32(d))[2]
                                elif s == b"NAM1" and len(d) >= 4 and _u32(d) != 0:
                                    nam1_key = fk(_u32(d))[2]
                            prev_loc = locations.get(rkey)
                            plugins_seen = list(prev_loc["plugins"]) if prev_loc else []
                            if pname not in plugins_seen:
                                plugins_seen.append(pname)
                            locations[rkey] = {
                                "form_key": rkey,
                                "defining_plugin": rowner,
                                "form_id": _hex_id(rlocal),
                                "edid": edid or (prev_loc["edid"] if prev_loc else ""),
                                "plugins": plugins_seen,
                                "parent_lctn": pnam_key,
                                "world_marker_ref": nam1_key,
                            }
                        elif rtyp == b"ECZN":
                            loc_key: Optional[str] = None
                            for s, d in rsubs:
                                if s == b"DATA" and len(d) >= 8 and _u32(d, 4) != 0:
                                    loc_key = fk(_u32(d, 4))[2]
                            eczn[rkey] = {
                                "form_key": rkey,
                                "defining_plugin": rowner,
                                "form_id": _hex_id(rlocal),
                                "edid": edid,
                                "location": loc_key,
                            }
                        elif rtyp == b"REGN":
                            wnam_key: Optional[str] = None
                            for s, d in rsubs:
                                if s == b"WNAM" and len(d) >= 4 and _u32(d) != 0:
                                    wnam_key = fk(_u32(d))[2]
                            regn[rkey] = {
                                "form_key": rkey,
                                "defining_plugin": rowner,
                                "form_id": _hex_id(rlocal),
                                "edid": edid,
                                "world_key": wnam_key,
                            }

        # Summarize per-plugin touched worlds
        touched_summary: Dict[str, Any] = {}
        for wkey, tw in sorted(p_worlds_touched.items()):
            w_edid = worlds.get(wkey, {}).get("edid", wkey)
            touched_summary[w_edid or wkey] = {
                "world_form_key": wkey,
                "is_override": wkey.split(":", 1)[0] != pname,
                "cells": len(tw["cells"]),
                "cell_bbox": _bbox(tw["cells"]),
                "land_records": tw["land_records"],
                "land_cells": len(tw["land_xy"]),
                "land_bbox": _bbox(tw["land_xy"]),
                "dry_cells": len(tw["dry_xy"]),
                "dry_bbox": _bbox(tw["dry_xy"]),
                "ref_cells": len(tw["ref_xy"]),
                "ref_bbox": _bbox(tw["ref_xy"]),
                "placed_refs": tw["placed_refs"],
                "persistent_refs": tw["persistent_refs"],
                "map_markers": tw["map_markers"],
                "zmin_m": tw["zmin_m"],
                "zmax_m": tw["zmax_m"],
            }

        per_plugin_reports.append(
            {
                "plugin": pname,
                "masters": masters,
                "counts": p_counts,
                "new_counts": p_new_counts,
                "interior_map_markers": p_interior_markers,
                "map_markers_total_in_plugin": sum(tw["map_markers"] for tw in p_worlds_touched.values()) + p_interior_markers,
                "worlds_touched": touched_summary,
            }
        )

    # Interior BFS from worldspace load doors -> assign interior CELLs (and their XLCNs) to entry worldspace
    int_adj: Dict[str, set[str]] = collections.defaultdict(set)
    int_entry_worlds: Dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    for ref in refs_by_key.values():
        xtel = ref["xtel"]
        if not xtel or xtel not in refs_by_key:
            continue
        dst = refs_by_key[xtel]
        if ref["place_kind"] == "world" and dst["place_kind"] == "interior":
            int_entry_worlds[dst["place_id"]][ref["place_id"]] += 1
        elif ref["place_kind"] == "interior" and dst["place_kind"] == "world":
            int_entry_worlds[ref["place_id"]][dst["place_id"]] += 1
        elif ref["place_kind"] == "interior" and dst["place_kind"] == "interior":
            int_adj[ref["place_id"]].add(dst["place_id"])
            int_adj[dst["place_id"]].add(ref["place_id"])

    int_cell_world: Dict[str, str] = {}
    bfs_q: collections.deque[str] = collections.deque()
    for icell, wc in sorted(int_entry_worlds.items()):
        # Prefer child worlds (e.g. DiamondCity) when tied or dominant
        best_w = sorted(wc.items(), key=lambda kv: (-kv[1], worlds.get(kv[0], {}).get("parent_world") is None, kv[0]))[0][0]
        int_cell_world[icell] = best_w
        bfs_q.append(icell)
    while bfs_q:
        cur_ic = bfs_q.popleft()
        cur_w = int_cell_world[cur_ic]
        for nxt_ic in sorted(int_adj.get(cur_ic, ())):
            if nxt_ic not in int_cell_world:
                int_cell_world[nxt_ic] = cur_w
                bfs_q.append(nxt_ic)

    lctn_int_worlds: Dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    for ic_key, ic_info in int_cells.items():
        xl = ic_info.get("xlcn")
        if xl and ic_key in int_cell_world:
            lctn_int_worlds[xl][int_cell_world[ic_key]] += 1

    # Primary worldspace per plugin for holding/virtual/teleport-only locations (e.g. Institute -> Commonwealth)
    plugin_primary_world: Dict[str, str] = {}
    for wkey, w in worlds.items():
        dp = w["defining_plugin"]
        if dp not in plugin_primary_world:
            plugin_primary_world[dp] = wkey
        elif w["edid"] in ("Commonwealth", "DLC03FarHarbor", "NukaWorld"):
            plugin_primary_world[dp] = wkey
    if "Fallout4.esm:00003C" in worlds:
        for dlc_cw in ("DLCRobot.esm", "DLCworkshop01.esm", "DLCworkshop02.esm", "DLCworkshop03.esm"):
            plugin_primary_world.setdefault(dlc_cw, "Fallout4.esm:00003C")

    # Resolve LCTN -> worldspace assignment
    # 1. Direct WRLD.XLCN roots (prefer child worlds over parent worlds when walking up PNAM)
    xlcn_to_worlds: Dict[str, List[str]] = collections.defaultdict(list)
    for wkey, w in worlds.items():
        if w["location"]:
            xlcn_to_worlds[w["location"]].append(wkey)

    # Exterior cell XLCN hints
    lctn_ext_worlds: Dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    for c in ext_cells.values():
        if c["xlcn"]:
            lctn_ext_worlds[c["xlcn"]][c["world_key"]] += 1

    def resolve_lctn_world(lkey: str) -> Tuple[Optional[str], str]:
        seen: set[str] = set()
        cur: Optional[str] = lkey
        while cur and cur in locations and cur not in seen:
            seen.add(cur)
            if cur in xlcn_to_worlds:
                candidates = xlcn_to_worlds[cur]
                child_first = sorted(candidates, key=lambda wk: (worlds[wk]["parent_world"] is None, wk))
                return child_first[0], "wrld_xlcn_chain"
            loc_obj = locations[cur]
            nam1 = loc_obj.get("world_marker_ref")
            if nam1 and nam1 in refs_by_key and refs_by_key[nam1]["place_kind"] == "world":
                return refs_by_key[nam1]["place_id"], "world_marker_ref"
            if cur in lctn_ext_worlds and lctn_ext_worlds[cur]:
                return lctn_ext_worlds[cur].most_common(1)[0][0], "exterior_cell_xlcn"
            if cur in lctn_int_worlds and lctn_int_worlds[cur]:
                return lctn_int_worlds[cur].most_common(1)[0][0], "interior_door_bfs"
            cur = loc_obj.get("parent_lctn")
        dp = locations[lkey]["defining_plugin"]
        fallback_w = plugin_primary_world.get(dp)
        if fallback_w:
            return fallback_w, "plugin_primary_world"
        return None, "unassigned"

    locations_by_world: Dict[str, int] = collections.Counter()
    location_rows: List[Dict[str, Any]] = []
    for lkey, loc in locations.items():
        wkey, resolution = resolve_lctn_world(lkey)
        wedid = worlds[wkey]["edid"] if wkey and wkey in worlds else None
        if wkey:
            locations_by_world[wkey] += 1
        nam1 = loc.get("world_marker_ref")
        has_marker = (lkey in marker_lctns) or bool(
            nam1 and nam1 in refs_by_key and refs_by_key[nam1].get("is_marker")
        )
        location_rows.append(
            {
                "form_key": loc["form_key"],
                "defining_plugin": loc["defining_plugin"],
                "form_id": loc["form_id"],
                "edid": loc["edid"],
                "parent_lctn": loc["parent_lctn"],
                "world_form_key": wkey,
                "world_edid": wedid,
                "world_resolution": resolution,
                "has_marker": has_marker,
            }
        )
    location_rows.sort(key=lambda r: (lower_names.index(r["defining_plugin"].lower()) if r["defining_plugin"].lower() in lower_names else 999, int(r["form_id"], 16)))

    # Encounter zones and regions per worldspace
    eczn_by_world: Dict[str, int] = collections.Counter()
    lctn_to_wkey = {r["form_key"]: r["world_form_key"] for r in location_rows}
    for z in eczn.values():
        wk = lctn_to_wkey.get(z["location"]) if z["location"] else None
        if wk:
            eczn_by_world[wk] += 1

    regn_by_world: Dict[str, int] = collections.Counter()
    for rg in regn.values():
        if rg["world_key"]:
            regn_by_world[rg["world_key"]] += 1

    # Aggregate merged worldspace metrics
    w_cells: Dict[str, set[Tuple[int, int]]] = collections.defaultdict(set)
    for c in ext_cells.values():
        w_cells[c["world_key"]].add(c["xy"])

    w_land_records: Dict[str, int] = collections.Counter()
    w_land_xy: Dict[str, set[Tuple[int, int]]] = collections.defaultdict(set)
    w_dry_xy: Dict[str, set[Tuple[int, int]]] = collections.defaultdict(set)
    w_zmin: Dict[str, float] = {}
    w_zmax: Dict[str, float] = {}
    for ld in land_by_key.values():
        wk = ld["world_key"]
        w_land_records[wk] += 1
        if ld["xy"] is not None:
            if ld["has_vhgt"]:
                w_land_xy[wk].add(ld["xy"])
            if ld["is_dry"]:
                w_dry_xy[wk].add(ld["xy"])
        if ld["zmin_m"] is not None:
            w_zmin[wk] = ld["zmin_m"] if wk not in w_zmin else min(w_zmin[wk], ld["zmin_m"])
        if ld["zmax_m"] is not None:
            w_zmax[wk] = ld["zmax_m"] if wk not in w_zmax else max(w_zmax[wk], ld["zmax_m"])

    w_ref_xy: Dict[str, set[Tuple[int, int]]] = collections.defaultdict(set)
    w_placed: Dict[str, int] = collections.Counter()
    w_pers: Dict[str, int] = collections.Counter()
    w_markers: Dict[str, int] = collections.Counter()
    interior_markers_merged = 0

    # World-to-world XTEL load-door pairs
    door_pair_counts: Dict[Tuple[str, str], int] = collections.Counter()
    door_pair_details: Dict[Tuple[str, str], List[Dict[str, str]]] = collections.defaultdict(list)
    world_to_interior_doors: Dict[str, int] = collections.Counter()

    for rkey, ref in refs_by_key.items():
        if ref["place_kind"] == "world":
            wk = ref["place_id"]
            w_placed[wk] += 1
            if ref["persistent"]:
                w_pers[wk] += 1
            elif ref["xy"] is not None:
                w_ref_xy[wk].add(ref["xy"])
            if ref["is_marker"]:
                w_markers[wk] += 1
        elif ref["is_marker"]:
            interior_markers_merged += 1

        xtel = ref["xtel"]
        if xtel and ref["place_kind"] == "world":
            src_wkey = ref["place_id"]
            src_wedid = worlds.get(src_wkey, {}).get("edid", src_wkey)
            dst_ref = refs_by_key.get(xtel)
            if dst_ref is not None:
                if dst_ref["place_kind"] == "world" and dst_ref["place_id"] != src_wkey:
                    dst_wkey = dst_ref["place_id"]
                    dst_wedid = worlds.get(dst_wkey, {}).get("edid", dst_wkey)
                    pair = (src_wedid, dst_wedid)
                    door_pair_counts[pair] += 1
                    door_pair_details[pair].append(
                        {
                            "src_door": rkey,
                            "dst_door": xtel,
                            "plugin": ref["plugin"],
                            "is_door_base": str(ref["base_key"] in door_bases).lower(),
                        }
                    )
                elif dst_ref["place_kind"] == "interior":
                    world_to_interior_doors[src_wedid] += 1

    world_rows: Dict[str, Any] = {}
    for wkey, w in sorted(
        worlds.items(),
        key=lambda kv: (
            lower_names.index(kv[1]["defining_plugin"].lower()) if kv[1]["defining_plugin"].lower() in lower_names else 999,
            int(kv[1]["form_id"], 16),
        ),
    ):
        edid_key = w["edid"] or wkey
        parent_edid = worlds[w["parent_world"]]["edid"] if w["parent_world"] in worlds else None
        loc_edid = locations[w["location"]]["edid"] if w["location"] in locations else None
        world_rows[edid_key] = {
            "form_key": w["form_key"],
            "defining_plugin": w["defining_plugin"],
            "form_id": w["form_id"],
            "edid": w["edid"],
            "plugins": w["plugins"],
            "parent_world": w["parent_world"],
            "parent_world_edid": parent_edid,
            "location": w["location"],
            "location_edid": loc_edid,
            "climate": w["climate"],
            "cells": len(w_cells[wkey]),
            "cell_bbox": _bbox(w_cells[wkey]),
            "land_records": w_land_records[wkey],
            "land_cells": len(w_land_xy[wkey]),
            "land_bbox": _bbox(w_land_xy[wkey]),
            "dry_cells": len(w_dry_xy[wkey]),
            "dry_bbox": _bbox(w_dry_xy[wkey]),
            "zmin_m": w_zmin.get(wkey),
            "zmax_m": w_zmax.get(wkey),
            "ref_cells": len(w_ref_xy[wkey]),
            "ref_bbox": _bbox(w_ref_xy[wkey]),
            "placed_refs": w_placed[wkey],
            "persistent_refs": w_pers[wkey],
            "map_markers": w_markers[wkey],
            "lctn_count": locations_by_world[wkey],
            "eczn_count": eczn_by_world[wkey],
            "regn_count": regn_by_world[wkey],
            "interior_load_doors": world_to_interior_doors[edid_key],
            "decoded_fields": w.get("decoded_fields", {}),
            "raw_subrecords": w["raw_subrecords"],
        }

    door_pairs_out = [
        {
            "from_world": src_w,
            "to_world": dst_w,
            "count": cnt,
            "doors": door_pair_details[(src_w, dst_w)],
        }
        for (src_w, dst_w), cnt in sorted(door_pair_counts.items())
    ]

    unassigned_lctns = sum(1 for r in location_rows if r["world_form_key"] is None)

    return {
        "schema_version": 1,
        "tool": "scripts/terrain/fo4_world_census.py",
        "plugins_in_load_order": plugin_names,
        "totals": {
            "worlds": len(world_rows),
            "lctn": len(locations),
            "lctn_unassigned_world": unassigned_lctns,
            "eczn": len(eczn),
            "regn": len(regn),
            "map_markers_worldspace": sum(w_markers.values()),
            "map_markers_interior": interior_markers_merged,
            "map_markers": sum(w_markers.values()) + interior_markers_merged,
            "map_markers_per_plugin_sum": sum(p["map_markers_total_in_plugin"] for p in per_plugin_reports),
            "world_to_world_doors": sum(door_pair_counts.values()),
        },
        "per_plugin": per_plugin_reports,
        "worlds": world_rows,
        "world_door_pairs": door_pairs_out,
        "locations": location_rows,
    }


def write_census_json(out_path: str, payload: Dict[str, Any], input_paths: Sequence[str] = ()) -> None:
    refuse_unsafe_output_path(out_path, input_paths)
    parent = os.path.dirname(os.path.abspath(out_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp_path = out_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    os.replace(tmp_path, out_path)


def resolve_plugin_list(plugins: Sequence[str], data_dir: str = "") -> List[str]:
    if plugins:
        return list(plugins)
    if data_dir:
        return [os.path.join(data_dir, name) for name in DEFAULT_FO4_PLUGINS]
    raise ValueError("provide plugin paths or --data-dir")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Read-only Fallout 4 worldspace, location, marker, and load-door census")
    ap.add_argument("--out", required=True, help="Output JSON path (outside Git worktrees and game folders)")
    ap.add_argument("--data-dir", default="", help="Fallout 4 Data directory (expands canonical 7-plugin load order)")
    ap.add_argument("plugins", nargs="*", help="Explicit plugin paths in load order (Fallout4.esm first)")
    args = ap.parse_args(argv)

    try:
        plugin_paths = resolve_plugin_list(args.plugins, args.data_dir)
        refuse_unsafe_output_path(args.out, plugin_paths)
        report = run_fo4_census(plugin_paths)
        write_census_json(args.out, report, plugin_paths)
    except (CensusPathError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps({"totals": report["totals"], "world_door_pairs": [
        {"from": p["from_world"], "to": p["to_world"], "count": p["count"]} for p in report["world_door_pairs"]
    ]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
