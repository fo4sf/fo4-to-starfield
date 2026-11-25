"""Extract the bounded SanctuaryHillsWorld pre-war strip, build its BTD/objects, and emit pure pre-war weather/sky."""
from __future__ import annotations

import json
import math
import os
import struct
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from fo4sf import btd, exterior, fo4land, navmesh, overlay, overlay_grid as og, terrain_grid as tg
from fo4sf.planet import esm, home_planet_spec as hspec, records as precords, wb_records
from . import s1_spec


def _u32(data: bytes, offset: int = 0) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def strip_sf_tile(
    gx0: int = s1_spec.DEFAULT_STRIP_RECT[0],
    gx1: int = s1_spec.DEFAULT_STRIP_RECT[1],
    gy0: int = s1_spec.DEFAULT_STRIP_RECT[2],
    gy1: int = s1_spec.DEFAULT_STRIP_RECT[3],
) -> og.Tile:
    """Compute the single square Starfield `Tile` covering inclusive FO4 grid `[gx0..gx1] x [gy0..gy1]`."""
    cx0, cx1, cy0, cy1 = og.sf_cells_of_fo4_rect(gx0, gx1, gy0, gy1)
    n = max(cx1 - cx0 + 1, cy1 - cy0 + 1)
    return og.Tile(ix=0, iy=0, cx0=cx0, cy0=cy0, n=n)


def extract_strip_from_plugin(
    plugin: fo4land.Plugin,
    gx0: int = s1_spec.DEFAULT_STRIP_RECT[0],
    gx1: int = s1_spec.DEFAULT_STRIP_RECT[1],
    gy0: int = s1_spec.DEFAULT_STRIP_RECT[2],
    gy1: int = s1_spec.DEFAULT_STRIP_RECT[3],
    world_fid: int = s1_spec.SANCTUARY_WRLD_FID,
) -> Dict[str, Any]:
    """Read-only extract `LAND` VHGT grids, `NAVM`, `REFR`, `ACHR`, and base info from a bounded FO4 strip."""
    wanted = {(x, y) for x in range(gx0, gx1 + 1) for y in range(gy0, gy1 + 1)}
    buf = plugin.buf

    wrld_span = None
    for item in fo4land.iter_items(buf, *plugin.top_group(b"WRLD")):
        if item[0] == "GRUP" and _u32(item[3]) == world_fid:
            wrld_span = (item[1] + 24, item[2])
            break
    if wrld_span is None:
        raise ValueError(f"Worldspace 0x{world_fid:08X} not found in {plugin.path}")

    # Index relevant base records across top groups
    base_sigs = (
        b"STAT", b"SCOL", b"MSTT", b"ACTI", b"DOOR", b"FURN",
        b"TREE", b"FLOR", b"CONT", b"MISC", b"LIGH", b"TERM",
    )
    bases: Dict[int, Dict[str, Any]] = {}
    for g in fo4land.iter_items(buf, plugin.body, len(buf)):
        if g[0] == "GRUP" and g[3] in base_sigs:
            for r in fo4land.iter_items(buf, g[1] + 24, g[2]):
                if r[0] == "GRUP":
                    continue
                subs = list(fo4land.iter_subrecords(fo4land.record_data(buf, r[1])))
                ed = ""
                modl = ""
                for sg, d in subs:
                    if sg == b"EDID":
                        ed = fo4land.zstring(d)
                    elif sg == b"MODL":
                        modl = fo4land.zstring(d)
                bases[r[3]] = {"sig": r[0].decode("ascii"), "edid": ed, "model": modl}

    grids: Dict[Tuple[int, int], np.ndarray] = {}
    navms: List[Dict[str, Any]] = []
    refrs: List[Dict[str, Any]] = []
    achrs: List[Dict[str, Any]] = []
    cells_found: List[Tuple[int, int]] = []

    def _walk(start: int, end: int, cur_cell: Optional[Tuple[int, bool, Optional[int], Optional[int]]] = None, in_block: bool = False) -> None:
        for sub in fo4land.iter_items(buf, start, end):
            if sub[0] == "GRUP":
                _walk(sub[1] + 24, sub[2], cur_cell, in_block or sub[4] in (4, 5))
            elif sub[0] == b"CELL":
                subs = list(fo4land.iter_subrecords(fo4land.record_data(buf, sub[1])))
                xclc = next((d for sg, d in subs if sg == b"XCLC"), None)
                gx, gy = struct.unpack_from("<ii", xclc, 0) if xclc and len(xclc) >= 8 else (None, None)
                cur_cell = (sub[3], not in_block, gx, gy)
                if in_block and (gx, gy) in wanted:
                    cells_found.append((gx, gy))
            elif sub[0] == b"LAND":
                if cur_cell and not cur_cell[1] and (cur_cell[2], cur_cell[3]) in wanted:
                    subs = list(fo4land.iter_subrecords(fo4land.record_data(buf, sub[1])))
                    vhgt = next((d for sg, d in subs if sg == b"VHGT"), None)
                    if vhgt:
                        grids[(cur_cell[2], cur_cell[3])] = fo4land.decode_vhgt(vhgt)
            elif sub[0] == b"NAVM":
                if cur_cell and not cur_cell[1] and (cur_cell[2], cur_cell[3]) in wanted:
                    nvnm = next((d for sg, d in fo4land.iter_subrecords(fo4land.record_data(buf, sub[1])) if sg == b"NVNM"), None)
                    if nvnm:
                        navms.append({"fid": sub[3], "cell": (cur_cell[2], cur_cell[3]), "nvnm": nvnm})
            elif sub[0] in (b"REFR", b"ACHR"):
                if sub[2] & 0x20:
                    continue
                subs = list(fo4land.iter_subrecords(fo4land.record_data(buf, sub[1])))
                pr = fo4land.parse_ref(subs)
                ed = next((fo4land.zstring(d) for sg, d in subs if sg == b"EDID"), "")
                pos = pr["pos"]
                rgx = int(math.floor(pos[0] / tg.FO4_CELL_UNITS)) if pos else None
                rgy = int(math.floor(pos[1] / tg.FO4_CELL_UNITS)) if pos else None
                in_w = (cur_cell and not cur_cell[1] and (cur_cell[2], cur_cell[3]) in wanted) or (
                    cur_cell and cur_cell[1] and (rgx, rgy) in wanted
                )
                if in_w and pos is not None:
                    row = {
                        "fid": sub[3],
                        "sig": sub[0].decode("ascii"),
                        "edid": ed,
                        "base": pr["base"],
                        "pos": list(pos),
                        "rot": list(pr["rot"] or (0.0, 0.0, 0.0)),
                        "scale": float(pr.get("scale") or 1.0),
                        "persistent": bool(cur_cell[1]),
                        "cell": (cur_cell[2], cur_cell[3]) if not cur_cell[1] else (rgx, rgy),
                        "disabled": bool(sub[2] & 0x0800),
                        "open_by_default": any(sg == b"ONAM" for sg, _ in subs),
                    }
                    if sub[0] == b"REFR":
                        refrs.append(row)
                    else:
                        achrs.append(row)

    _walk(*wrld_span)
    return {
        "world_fid": world_fid,
        "rect": (gx0, gx1, gy0, gy1),
        "cells": sorted(set(cells_found)),
        "grids": grids,
        "navms": navms,
        "refrs": refrs,
        "achrs": achrs,
        "bases": bases,
    }


def _fill_missing_cells(
    grids: Dict[Tuple[int, int], np.ndarray],
    x0: int,
    x1: int,
    y0: int,
    y1: int,
    default_units: float = 0.0,
) -> Dict[Tuple[int, int], np.ndarray]:
    """Ensure every cell in `[x0..x1] x [y0..y1]` has a `(33, 33)` grid so edge resampling never fails."""
    out = dict(grids)
    if out:
        fallback_val = float(np.mean([float(np.mean(v)) for v in out.values()]))
    else:
        fallback_val = default_units
    fill = np.full((fo4land.GRID, fo4land.GRID), fallback_val, dtype=np.float64)
    for gx in range(x0, x1 + 1):
        for gy in range(y0, y1 + 1):
            if (gx, gy) not in out:
                out[(gx, gy)] = fill
    return out


def build_strip_btd_bytes(
    grids: Dict[Tuple[int, int], np.ndarray],
    tile: og.Tile,
    ltex_table: Sequence[int] = (0x001235C2,),
    quad_bytes: bytes = bytes([0] * 8),
) -> Tuple[bytes, float, float, np.ndarray]:
    """Resample FO4 strip `LAND` grids onto Starfield `tile` and serialize a valid Starfield `.btd`."""
    if len(quad_bytes) != 8:
        raise ValueError(f"quad_bytes must be 8 bytes, got {len(quad_bytes)}")
    bx0, bx1, by0, by1 = tile.bounds_m
    cx0, cx1, cy0, cy1 = tg.fo4_cells_covering(bx0, bx1, by0, by1)
    padded = _fill_missing_cells(grids, cx0 - 1, cx1 + 1, cy0 - 1, cy1 + 1)
    merged, _ = fo4land.merge_cells(padded, cx0 - 1, cy0 - 1, (cx1 - cx0) + 3, (cy1 - cy0) + 3)
    ox = (cx0 - 1) * tg.FO4_CELL_UNITS
    oy = (cy0 - 1) * tg.FO4_CELL_UNITS

    xs, ys = tile.sample_coords()
    xu = xs * tg.UNITS_PER_METRE
    yu = ys * tg.UNITS_PER_METRE
    heights_m = tg.resample_bilinear(merged, ox, oy, tg.FO4_VERTEX_UNITS, xu, yu) / tg.UNITS_PER_METRE

    lo = float(np.min(heights_m))
    hi = float(np.max(heights_m))
    hmin, hmax = og.height_range(lo, hi)
    raw = btd.quantize(heights_m, hmin, hmax)
    weights = np.zeros_like(raw)
    quad = np.tile(np.frombuffer(quad_bytes, np.uint8), (2 * tile.n, 2 * tile.n, 1))
    btd_bytes = btd.write(btd.Btd(6, hmin, hmax, list(ltex_table), raw, weights, quad))
    return btd_bytes, hmin, hmax, raw


_SIG_TO_TYPE = {
    "STAT": "Static",
    "SCOL": "StaticCollection",
    "MSTT": "MovableStatic",
    "ACTI": "Activator",
    "DOOR": "Door",
    "FURN": "Furniture",
    "CONT": "Container",
    "MISC": "MiscItem",
    "TERM": "Terminal",
    "FLOR": "Flora",
    "TREE": "Static",
    "LIGH": "Light",
}


def build_strip_objects(
    strip: Dict[str, Any],
    tile: og.Tile,
    world_edid: str = "FO4SF_PrewarSanctuaryWorld",
    asset_prefix: str = "fo4core",
    door_manifest: Optional[Dict[str, dict]] = None,
) -> Tuple[dict, List[dict]]:
    """Build `objects.json` (`bases`, `refs`) in `tile`'s local frame reusing `exterior.classify` & door rigs (`S1-14`)."""
    bases_meta = strip["bases"]
    selected_bases: Dict[str, dict] = {}
    placed_refs: List[dict] = []
    skipped: List[dict] = []
    norm_doors: Dict[str, dict] = {
        str(k).replace("\\", "/").lower(): dict(v)
        for k, v in (door_manifest or {}).items()
        if isinstance(v, dict)
    }

    ox, oy = tile.origin_m
    for r in strip["refrs"]:
        base_info = bases_meta.get(r["base"])
        if not base_info:
            skipped.append({"fid": f"0x{r['fid']:08X}", "reason": "missing_base"})
            continue
        tname = _SIG_TO_TYPE.get(base_info["sig"], base_info["sig"])
        pseudo_ref = {
            "formkey": f"{r['fid']:06X}:Fallout4.esm",
            "type": tname,
            "base_editor_id": base_info["edid"],
            "model": base_info["model"],
            "exterior_cell": list(r["cell"]),
        }
        action, code, detail = exterior.classify(pseudo_ref)
        if action != "convert":
            skipped.append({"fid": f"0x{r['fid']:08X}", "reason": code, "detail": detail})
            continue
        src_model = exterior.source_key(base_info["model"]).replace("\\", "/")
        sf_model = f"{asset_prefix}/" + src_model.removeprefix("meshes/")
        bed = base_info["edid"] or f"FO4PrewarBase_{r['base']:06X}"
        door_meta = norm_doors.get(src_model.lower()) or norm_doors.get(sf_model.lower())
        if bed not in selected_bases:
            bentry: Dict[str, Any] = {"edid": f"FO4Prewar_{bed}", "model": sf_model, "fo4_fid": f"0x{r['base']:08X}"}
            if door_meta:
                bentry["door"] = door_meta
            selected_bases[bed] = bentry

        px, py, pz = [c / tg.UNITS_PER_METRE for c in r["pos"]]
        lx, ly = px - ox, py - oy
        rot = [float(a) for a in r["rot"]]
        scale = float(r["scale"])
        if door_meta and "origin_offset" in door_meta:
            off = door_meta["origin_offset"]
            m = exterior.ref_matrix(rot)
            lx, ly, pz = (
                lx + scale * (m[0] * off[0] + m[1] * off[1] + m[2] * off[2]),
                ly + scale * (m[3] * off[0] + m[4] * off[1] + m[5] * off[2]),
                pz + scale * (m[6] * off[0] + m[7] * off[1] + m[8] * off[2]),
            )
        sc = tg.sf_cell_of(lx, ly)
        ref_row: Dict[str, Any] = {
            "src": f"{r['fid']:06X}:Fallout4.esm",
            "base": selected_bases[bed]["edid"],
            "cell": [int(sc[0]), int(sc[1])],
            "pos": [round(lx, 4), round(ly, 4), round(pz, 4)],
            "rot": [round(a, 6) for a in rot],
            "scale": round(scale, 4),
            "disabled": bool(r["disabled"]),
        }
        if door_meta and r.get("open_by_default"):
            ref_row["open_by_default"] = True
        placed_refs.append(ref_row)

    sorted_bases = sorted(selected_bases.values(), key=lambda x: x["edid"])
    base_idx_by_edid = {b["edid"]: idx for idx, b in enumerate(sorted_bases)}
    for ref in placed_refs:
        ref["base"] = base_idx_by_edid[ref["base"]]

    doc = {
        "world": world_edid,
        "bases": sorted_bases,
        "refs": placed_refs,
    }
    return doc, skipped


def build_strip_navmesh_doc(
    strip: Dict[str, Any],
    tile: og.Tile,
    *,
    world_edid: str = "FO4SF_PrewarSanctuaryWorld",
) -> Tuple[dict, Dict[str, Any]]:
    """Convert FO4 `SanctuaryHillsWorld` `NAVM`s via `src/fo4sf/navmesh.py` into `tile`'s local frame (`S1-04`)."""
    raw_navms = strip.get("navms") or []
    if not raw_navms:
        return {"version": 1, "world": world_edid, "navmeshes": []}, {"fo4_navms": 0, "sf_pieces": 0, "refused": []}

    ox, oy = tile.origin_m
    scale_xy = navmesh.UNITS_PER_METRE / tg.UNITS_PER_METRE
    shift_x = -ox * navmesh.UNITS_PER_METRE
    shift_y = -oy * navmesh.UNITS_PER_METRE

    shifted: List[Tuple[int, navmesh.Nvnm]] = []
    for row in raw_navms:
        nv = navmesh.parse(row["nvnm"], layout="fo4")
        nv.vertices[:, 0] = nv.vertices[:, 0] * scale_xy + shift_x
        nv.vertices[:, 1] = nv.vertices[:, 1] * scale_xy + shift_y
        nv.vertices[:, 2] = nv.vertices[:, 2] * scale_xy
        if len(nv.waypoints):
            nv.waypoints["pos"][:, 0] = nv.waypoints["pos"][:, 0] * scale_xy + shift_x
            nv.waypoints["pos"][:, 1] = nv.waypoints["pos"][:, 1] * scale_xy + shift_y
            nv.waypoints["pos"][:, 2] = nv.waypoints["pos"][:, 2] * scale_xy
        nv.grid_min = (
            nv.grid_min[0] * scale_xy + shift_x,
            nv.grid_min[1] * scale_xy + shift_y,
            nv.grid_min[2] * scale_xy,
        )
        nv.grid_max = (
            nv.grid_max[0] * scale_xy + shift_x,
            nv.grid_max[1] * scale_xy + shift_y,
            nv.grid_max[2] * scale_xy,
        )
        shifted.append((int(row["fid"]), nv))

    cmin, cmax = tg.cell_range(tile.n)
    tile_cells = {(cx, cy) for cx in range(cmin, cmax + 1) for cy in range(cmin, cmax + 1)}

    refused: List[dict] = []
    remaining = list(shifted)
    pieces: List[navmesh.Piece] = []
    report: Dict[str, Any] = {}
    while remaining:
        try:
            pieces, report = navmesh.convert(remaining)
            break
        except navmesh.NavmeshError as exc:
            msg = str(exc)
            # Drop single overflowing FO4 navmesh if encountered, mirrors navmesh_core64n_convert.py
            import re

            m = re.search(r"0x([0-9A-Fa-f]+)", msg)
            if not m:
                raise
            bad_fid = int(m.group(1), 16)
            refused.append({"fid": f"0x{bad_fid:08X}", "reason": msg})
            remaining = [(f, nv) for f, nv in remaining if f != bad_fid]

    in_tile = [p for p in pieces if p.cell in tile_cells]
    doc = navmesh.export(in_tile)
    doc["world"] = world_edid
    stats = {
        "fo4_navms": len(raw_navms),
        "sf_pieces": len(in_tile),
        "dropped_outside_tile": len(pieces) - len(in_tile),
        "refused": refused,
        "convert_report": report,
    }
    return doc, stats


def build_prewar_sky_plugin(
    out_path: str,
    weather_id: int = wb_records.HOME_WEATHER,
    climate_id: int = wb_records.HOME_CLIMATE,
    atmo_id: int = wb_records.HOME_ATMO,
    weather_edid: str = "FO4SFPrewarClearWeather",
    climate_edid: str = "FO4SFPrewarClimate",
    atmo_edid: str = "FO4SFPrewarAtmosphere",
) -> Tuple[str, Dict[str, Any]]:
    """Write a standalone pure pre-war weather/climate/atmo ESM with ZERO `Starfield.esm` references."""
    w = esm.PluginWriter([], esm.ESM)
    w.add(wb_records.build_home_weather(weather_id, edid=weather_edid))
    w.add(wb_records.build_home_climate(climate_id, weather_formid=weather_id, edid=climate_edid))
    w.add(wb_records.build_home_atmosphere(atmo_id, edid=atmo_edid))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    w.write(out_path, compress=False)
    verify_zero_starfield_sky_refs(out_path)
    return out_path, {
        "weather_id": f"0x{weather_id:06X}",
        "climate_id": f"0x{climate_id:06X}",
        "atmo_id": f"0x{atmo_id:06X}",
        "starfield_sky_refs": 0,
    }


def _rebuild_grup_replacing_wrld(buf: bytes, start: int, end: int, wrld_fn) -> bytes:
    """Recursively copy raw ESM bytes inside a top-level WRLD GRUP while transforming matching WRLD records."""
    from . import vault111_append as va

    parts: List[bytes] = []
    pos = start
    while pos < end:
        if buf[pos : pos + 4] == b"GRUP":
            gs = _u32(buf, pos + 4)
            lbl = bytes(buf[pos + 8 : pos + 12])
            gt, st, unk = struct.unpack_from("<III", buf, pos + 12)
            inner = _rebuild_grup_replacing_wrld(buf, pos + 24, pos + gs, wrld_fn)
            parts.append(b"GRUP" + struct.pack("<I", 24 + len(inner)) + lbl + struct.pack("<III", gt, st, unk) + inner)
            pos += gs
        else:
            rec, nxt = va._read_rec(buf, pos)  # noqa: SLF001
            parts.append(wrld_fn(rec).to_bytes() if rec.sig == b"WRLD" else bytes(buf[pos:nxt]))
            pos = nxt
    return b"".join(parts)


def bind_prewar_world_to_home(
    world_esm_path: str,
    *,
    climate_local_id: int = wb_records.HOME_CLIMATE,
    water_local_id: int = wb_records.HOME_WATER,
    world_edid: str = "FO4SF_PrewarSanctuaryWorld",
    emit_prewar_sky_pair: bool = True,
) -> Dict[str, Any]:
    """Bind `FO4SF_PrewarSanctuaryWorld` WRLD `CNAM` (pre-war `CLMT`/`WTHR`, `S1-11`) & `NAM3` (water), 0 Starfield sky."""
    from . import vault111_append as va

    with open(world_esm_path, "rb") as f:
        raw = f.read()
    tes4, grups = va.parse_top_grups(raw)
    masters = [esm.zstring(d) for s, d in va._iter_subrecords(tes4.raw_subrecords_bytes) if s == b"MAST"]  # noqa: SLF001
    if hspec.HOME_MASTER not in masters:
        raise ValueError(f"{world_esm_path} must depend on {hspec.HOME_MASTER}, got masters={masters}")
    home_idx = masters.index(hspec.HOME_MASTER)
    self_idx = len(masters)
    water_fid = (home_idx << 24) | water_local_id

    max_local = va.max_local_formid(raw)
    extra_grups: Dict[bytes, bytes] = {}
    prewar_weather_fid: Optional[int] = None
    if emit_prewar_sky_pair:
        # Allocate self-owned pre-war WTHR/CLMT cleanly above TerrainOverlays max_local (S1-11)
        next_local = max_local + 1
        prewar_weather_fid = (self_idx << 24) | next_local
        prewar_climate_fid = (self_idx << 24) | (next_local + 1)
        climate_fid = prewar_climate_fid
        w_rec = wb_records.build_home_weather(prewar_weather_fid, edid="FO4SF_PrewarClearWeather")
        c_rec = wb_records.build_home_climate(
            prewar_climate_fid, weather_formid=prewar_weather_fid, edid="FO4SF_PrewarSanctuaryClimate"
        )
        # Check if TerrainOverlays already created WTHR/CLMT groups (unused, replaced or inserted cleanly in GROUP_ORDER)
        extra_grups[b"WTHR"] = w_rec.to_bytes()
        extra_grups[b"CLMT"] = c_rec.to_bytes()
        next_hedr_id = next_local + 2
    else:
        climate_fid = (home_idx << 24) | climate_local_id
        next_hedr_id = max_local + 1

    updated = False

    def _patch_wrld(rec: va.RawRec) -> va.RawRec:
        nonlocal updated
        subs = list(va._iter_subrecords(rec.raw_subrecords_bytes))  # noqa: SLF001
        ed = next((esm.zstring(d) for s, d in subs if s == b"EDID"), "")
        if ed != world_edid:
            return rec
        updated = True
        kept: List[Tuple[bytes, bytes]] = []
        in_ov_comp = False
        for s, d in subs:
            if s == b"BFCB" and esm.zstring(d) == "BGSWorldSpaceOverlay_Component":
                in_ov_comp = True
                kept.append((s, d))
                continue
            if s == b"BFCE" and in_ov_comp:
                in_ov_comp = False
                kept.append((s, d))
                continue
            if in_ov_comp and s in (b"CNAM", b"NAM3", b"NAM2"):
                continue
            if s in (b"CNAM", b"NAM3", b"NAM2") and not in_ov_comp:
                continue
            if s == b"BNAM" and not in_ov_comp and len(d) == 4 and (_u32(d) >> 24) != home_idx:
                continue
            kept.append((s, d))
        insert_at = 1 if kept and kept[0][0] == b"EDID" else 0
        # Never insert CNAM/NAM3 inside any BFCB..BFCE component block (BGSWorldSpaceOverlay_Component contains SNAM/PNAM/BNAM).
        in_comp_ins = False
        while insert_at < len(kept):
            sig_ins = kept[insert_at][0]
            if sig_ins == b"BFCB":
                in_comp_ins = True
                insert_at += 1
            elif sig_ins == b"BFCE" and in_comp_ins:
                in_comp_ins = False
                insert_at += 1
            elif in_comp_ins or sig_ins in (b"FULL", b"CNAM", b"NAM3"):
                insert_at += 1
            else:
                break
        kept[insert_at:insert_at] = [
            (b"CNAM", struct.pack("<I", climate_fid)),
            (b"NAM3", struct.pack("<I", water_fid)),
        ]
        return va.RawRec(
            rec.sig,
            rec.flags & ~va.COMPRESSED_FLAG,
            rec.fid,
            rec.version,
            rec.vc,
            rec.unknown,
            va._pack_subrecords(kept),  # noqa: SLF001
        )

    existing_by_lbl: Dict[bytes, Tuple[int, int, int, bytes]] = {}
    for lbl, gt, st, unk, pl in grups:
        if lbl == b"WRLD":
            pl_out = _rebuild_grup_replacing_wrld(pl, 0, len(pl), _patch_wrld)
        else:
            pl_out = pl
        if lbl in extra_grups:
            pl_out = pl_out + extra_grups.pop(lbl)
        existing_by_lbl[lbl] = (gt, st, unk, pl_out)

    for lbl, rec_b in extra_grups.items():
        existing_by_lbl[lbl] = (0, 0, 0, rec_b)

    order_index = {g.encode("ascii"): i for i, g in enumerate(esm.GROUP_ORDER)}
    ordered_lbls = sorted(
        existing_by_lbl.keys(),
        key=lambda lbl: (order_index.get(lbl, len(order_index)), lbl),
    )
    out_grups = [
        b"GRUP" + struct.pack("<I", 24 + len(existing_by_lbl[lbl][3])) + lbl + struct.pack("<III", *existing_by_lbl[lbl][:3]) + existing_by_lbl[lbl][3]
        for lbl in ordered_lbls
    ]

    if not updated:
        raise ValueError(f"{world_esm_path} missing WRLD {world_edid}")
    body = b"".join(out_grups)
    n_total = va._count_recs_and_grups(tes4.to_bytes() + body)  # noqa: SLF001
    tes4_subs = []
    for s, d in va._iter_subrecords(tes4.raw_subrecords_bytes):  # noqa: SLF001
        if s == b"HEDR" and len(d) >= 12:
            ver, _cnt, _nxt = struct.unpack_from("<fII", d, 0)
            tes4_subs.append((s, struct.pack("<fII", ver, n_total, next_hedr_id)))
        else:
            tes4_subs.append((s, d))
    new_tes4 = va.RawRec(b"TES4", tes4.flags, 0, tes4.version, tes4.vc, tes4.unknown, va._pack_subrecords(tes4_subs))  # noqa: SLF001
    with open(world_esm_path, "wb") as f:
        f.write(new_tes4.to_bytes() + body)
    verify_zero_starfield_sky_refs(world_esm_path)
    return {
        "world": world_edid,
        "prewar_weather_fid": f"0x{prewar_weather_fid:08X}" if prewar_weather_fid else None,
        "prewar_climate_fid": f"0x{climate_fid:08X}",
        "home_climate_fid": f"0x{climate_fid:08X}",
        "home_water_fid": f"0x{water_fid:08X}",
    }


def _verify_pure_sky_records(plugin_path: str, p: esm.Plugin, allowed_wthr_fids: set[int]) -> None:
    for rec in p.records("WTHR", [b"WTHR"]):
        for sig, d in rec.subs:
            if sig in (b"LNAM", b"MNAM", b"NNAM", b"GNAM") and len(d) == 4:
                val = _u32(d)
                if val != 0:
                    raise ValueError(f"WTHR {rec.edid} subrecord {sig.decode()} non-zero external ref 0x{val:08X}")
            elif sig in (b"IMSP", b"HNAM") and len(d) == 32:
                vals = struct.unpack("<8I", d)
                if any(v != 0 for v in vals):
                    raise ValueError(f"WTHR {rec.edid} {sig.decode()} holds non-zero IMGS ref {vals}")
    for rec in p.records("CLMT", [b"CLMT"]):
        for sig, d in rec.subs:
            if sig == b"WLST" and len(d) >= 4:
                wfid = _u32(d, 0)
                if wfid not in allowed_wthr_fids:
                    raise ValueError(f"CLMT {rec.edid} WLST references invalid/external weather 0x{wfid:08X}")


def verify_zero_starfield_sky_refs(plugin_path: str) -> None:
    """Verify pure sky ESMs OR `FO4SFPrewar_Sanctuary.esm` carry zero Starfield sky/water/planet refs (`S1-11`)."""
    with esm.Plugin(plugin_path) as p:
        if "WRLD" in p.groups:
            if hspec.HOME_MASTER not in p.masters:
                raise ValueError(f"{plugin_path} WRLD must target {hspec.HOME_MASTER}, got masters={p.masters}")
            home_idx = p.masters.index(hspec.HOME_MASTER)
            self_idx = p.self_index
            for forbidden in ("PNDT", "ATMO", "WATR"):
                if list(p.records(forbidden, [forbidden.encode("ascii")])):
                    raise ValueError(f"{plugin_path} must not define {forbidden} overrides/records")
            own_wthr_fids = {r.formid for r in p.records("WTHR", [b"WTHR"]) if (r.formid >> 24) == self_idx}
            own_clmt_fids = {r.formid for r in p.records("CLMT", [b"CLMT"]) if (r.formid >> 24) == self_idx}
            for rec in p.records("WTHR", [b"WTHR"]):
                if (rec.formid >> 24) != self_idx:
                    raise ValueError(f"{plugin_path} must not override external WTHR 0x{rec.formid:08X}")
            for rec in p.records("CLMT", [b"CLMT"]):
                if (rec.formid >> 24) != self_idx:
                    raise ValueError(f"{plugin_path} must not override external CLMT 0x{rec.formid:08X}")
            _verify_pure_sky_records(plugin_path, p, own_wthr_fids)
            for loc in p.records("LCTN", [b"LCTN"]):
                pnam = loc.get(b"PNAM")
                if not pnam or len(pnam) < 4 or (_u32(pnam) >> 24) != home_idx:
                    got = _u32(pnam) if pnam and len(pnam) >= 4 else 0
                    raise ValueError(f"{plugin_path} LCTN {loc.edid} PNAM=0x{got:08X} must point to {hspec.HOME_MASTER}")
            for start, end in p.groups.get("WRLD", []):
                for item in p.walk(start, end, groups=set()):
                    if item[0] == "REC":
                        wrec = p.record_at(item[1])
                        cnam = nam3 = bnam = None
                        in_comp = False
                        comp_name = ""
                        for sub_sig, sub_data in wrec.subs:
                            if sub_sig == b"BFCB":
                                in_comp = True
                                comp_name = esm.zstring(sub_data)
                            elif sub_sig == b"BFCE":
                                in_comp = False
                                comp_name = ""
                            elif in_comp:
                                if comp_name == "BGSWorldSpaceOverlay_Component" and sub_sig == b"BNAM" and len(sub_data) >= 4:
                                    sfbk_fid = _u32(sub_data)
                                    if (sfbk_fid >> 24) != self_idx:
                                        raise ValueError(
                                            f"{plugin_path} WRLD {wrec.edid} SurfaceBlock BNAM=0x{sfbk_fid:08X} must resolve to self (master #{self_idx})"
                                        )
                            else:
                                if sub_sig == b"CNAM":
                                    cnam = sub_data
                                elif sub_sig == b"NAM3":
                                    nam3 = sub_data
                                elif sub_sig == b"BNAM":
                                    bnam = sub_data
                        cnam_val = _u32(cnam) if cnam and len(cnam) >= 4 else 0
                        if not cnam or len(cnam) < 4 or ((cnam_val >> 24) != home_idx and cnam_val not in own_clmt_fids):
                            raise ValueError(
                                f"{plugin_path} WRLD {wrec.edid} CNAM=0x{cnam_val:08X} must resolve to self CLMT or {hspec.HOME_MASTER}"
                            )
                        for tag, val_bytes in (("NAM3", nam3), ("BNAM", bnam)):
                            if not val_bytes or len(val_bytes) < 4 or (_u32(val_bytes) >> 24) != home_idx:
                                got = _u32(val_bytes) if val_bytes and len(val_bytes) >= 4 else 0
                                raise ValueError(
                                    f"{plugin_path} WRLD {wrec.edid} {tag}=0x{got:08X} must resolve to {hspec.HOME_MASTER} (master #{home_idx})"
                                )
            return

        if p.masters:
            raise ValueError(f"{plugin_path} must have 0 masters for pure sky records, got {p.masters}")
        allowed_locals: set[int] = set()
        for grp in ("WTHR", "CLMT", "ATMO"):
            for rec in p.records(grp, [grp.encode("ascii")]):
                allowed_locals.add(rec.formid & 0xFFFFFF)

        _verify_pure_sky_records(plugin_path, p, {w & 0xFFFFFF for w in allowed_locals})
        for grp in ("PNDT", "LCTN"):
            if list(p.records(grp, [grp.encode("ascii")])):
                raise ValueError(f"{plugin_path} must not contain Starfield {grp} records")


def coordinate_home_pndt_plugin(
    home_master_path: str,
    sanctuary_world_path: str,
    out_reg_path: str,
    *,
    terrain_core_home_path: Optional[str] = None,
    world_edid: str = "FO4SF_PrewarSanctuaryWorld",
    latitude_rad: float = 0.7409,
    longitude_rad: float = -1.2453,
) -> Dict[str, Any]:
    """Emit coordinated `FO4SFPrewar_Sanctuary_Home.esm` combining `#858` `FO4TerrainCore_Home.esm` + Sanctuary (`S1-07`).

    When `terrain_core_home_path` exists, reads its `PNDT 0x01000805` `CNAM` rows (`Commonwealth`, etc.), preserves them
    with their owning master plugin names (`FO4TerrainCore.esm:0x000803`), and appends `FO4SFPrewar_Sanctuary.esm:0x000803`.
    """
    with esm.Plugin(home_master_path) as hm:
        home_name = os.path.basename(home_master_path)
        pndts = [r for r in hm.records("PNDT", [b"PNDT"]) if r.formid == ((1 << 24) | precords.PLANET)]
        if len(pndts) != 1:
            raise precords.PlanetError(f"{home_master_path} missing PNDT {(1 << 24) | precords.PLANET:#010x}")
        home_planet = pndts[0]

    with esm.Plugin(sanctuary_world_path) as sp:
        sanc_name = os.path.basename(sanctuary_world_path)
        swrlds = [w for w in sp.records("WRLD", [b"WRLD"]) if w.edid == world_edid]
        if len(swrlds) != 1:
            raise precords.PlanetError(f"{sanctuary_world_path} missing WRLD {world_edid!r}")
        sanc_wrld_local = swrlds[0].formid & 0xFFFFFF

    masters: List[str] = ["Starfield.esm", home_name]
    combined_specs: List[Tuple[float, float, str, int]] = []

    if terrain_core_home_path and os.path.isfile(terrain_core_home_path):
        with esm.Plugin(terrain_core_home_path) as tp:
            tp_pndts = [r for r in tp.records("PNDT", [b"PNDT"]) if (r.formid & 0xFFFFFF) == precords.PLANET]
            if tp_pndts:
                for lat, lon, wid in precords.master_worldspaces(tp_pndts[0]):
                    midx = wid >> 24
                    local = wid & 0xFFFFFF
                    owner = tp.masters[midx] if midx < len(tp.masters) else os.path.basename(terrain_core_home_path)
                    if owner.lower() == sanc_name.lower() and local == sanc_wrld_local:
                        continue
                    if all(m.lower() != owner.lower() for m in masters):
                        masters.append(owner)
                    combined_specs.append((float(lat), float(lon), owner, local))

    if all(m.lower() != sanc_name.lower() for m in masters):
        masters.append(sanc_name)
    combined_specs.append((float(latitude_rad), float(longitude_rad), sanc_name, sanc_wrld_local))

    seen_worlds: set[Tuple[str, int]] = set()
    cnam_entries: List[Tuple[float, float, int]] = []
    report_worlds: List[dict] = []
    master_idx_by_low = {m.lower(): idx for idx, m in enumerate(masters)}
    for lat, lon, owner, local in combined_specs:
        key = (owner.lower(), local)
        if key in seen_worlds:
            continue
        seen_worlds.add(key)
        midx = master_idx_by_low[owner.lower()]
        fid = (midx << 24) | local
        cnam_entries.append((lat, lon, fid))
        report_worlds.append({"owner": owner, "local_id": f"0x{local:06X}", "lat_rad": lat, "lon_rad": lon})

    writer = esm.PluginWriter(masters, esm.ESM)
    home_idx = masters.index(home_name)
    writer.add(precords.registration_record(home_planet, (home_idx << 24) | precords.PLANET, cnam_entries))
    os.makedirs(os.path.dirname(os.path.abspath(out_reg_path)), exist_ok=True)
    writer.write(out_reg_path, compress=False)
    return {
        "plugin": os.path.basename(out_reg_path),
        "masters": masters,
        "combined_with_core_home": bool(terrain_core_home_path and os.path.isfile(terrain_core_home_path)),
        "worlds": report_worlds,
    }


def build_prewar_overlay_params(
    tile: og.Tile,
    hmin: float,
    hmax: float,
    raw_btd_heights: np.ndarray,
    plugin_name: str = s1_spec.PLUGIN_PREWAR_WORLD,
    world_edid: str = "FO4SF_PrewarSanctuaryWorld",
    objects_rel: str = "objects.json",
    host_system_id: int = hspec.DEFAULT_HOME_SYSTEM_ID,
    host_planet_id: int = hspec.DEFAULT_HOME_PLANET_ID,
    host_planet_edid: str = "FO4SF_EarthPlanetData",
    navmesh_rel: Optional[str] = None,
) -> dict:
    """Assemble `overlays_params.json` compatible with `dotnet/TerrainOverlays` targeting `FO4SFHome` (`FO4SF_EarthPlanetData`)."""
    sx_cw, sy_cw, sz_cw = s1_spec.SANCTUARY_KEY_COORDS_M["player_start"]
    lx, ly = tile.to_local(sx_cw, sy_cw)
    spawn = [round(lx, 4), round(ly, 4), round(sz_cw + 0.5, 4)]
    spawn_cell = list(tg.sf_cell_of(lx, ly))
    doc: Dict[str, Any] = {
        "plugin": plugin_name,
        "prefix": "FO4SFPrewar",
        "hmin": float(hmin),
        "hmax": float(hmax),
        "alignment": "absolute",
        "hnam": 0,
        "host": {
            "planet_plugin": hspec.HOME_MASTER,
            "planet_edid": host_planet_edid,
            "surface_location": f"{hspec.SURFACE_LOC:06X}:{hspec.HOME_MASTER}",
            "system_id": int(host_system_id),
            "planet_id": int(host_planet_id),
            "biome": f"{hspec.BIOME:06X}:{hspec.HOME_MASTER}",
            "lever_keywords": ["PCM_OverlayExclusionZone", "LocTypeNoPCMScanTreeContent"],
            "registration_plugin": "FO4SFPrewar_Sanctuary_Home.esm",
        },
        "objects": objects_rel,
        "overlays": [
            {
                "world": world_edid,
                "tag": "SanctuaryPrewar",
                "latitude": 0.7409,
                "longitude": -1.2453,
                "ix": tile.ix,
                "iy": tile.iy,
                "n": tile.n,
                "cell_min": tg.cell_range(tile.n)[0],
                "cell_max": tg.cell_range(tile.n)[1],
                "btd_path": f"Data\\TERRAIN\\{world_edid}.btd",
                "fnam": overlay.fnam_values(raw_btd_heights),
                "location": world_edid + "Location",
                "block": world_edid + "Block",
                "bounds_min_m": tg.grid_origin(tile.n),
                "bounds_max_m": tg.grid_origin(tile.n) + tile.n * tg.SF_CELL_M,
                "coc": world_edid + "Spawn",
                "spawn": spawn,
                "spawn_cell": spawn_cell,
                "anchor": {"edid": world_edid + "Anchor", "local": spawn, "form_id": 0x800},
            }
        ],
    }
    if navmesh_rel:
        doc["navmesh"] = navmesh_rel
    return doc


def write_strip_stage_inputs(
    fo4_esm_path: str,
    out_dir: str,
    *,
    gx0: int = s1_spec.DEFAULT_STRIP_RECT[0],
    gx1: int = s1_spec.DEFAULT_STRIP_RECT[1],
    gy0: int = s1_spec.DEFAULT_STRIP_RECT[2],
    gy1: int = s1_spec.DEFAULT_STRIP_RECT[3],
    ltex_table: Sequence[int] = (0x001235C2,),
    quad_bytes: bytes = bytes([0] * 8),
    world_edid: str = "FO4SF_PrewarSanctuaryWorld",
    emit_standalone_sky: bool = False,
    door_manifest: Optional[Dict[str, dict]] = None,
) -> Dict[str, Any]:
    """Materialize local strip `.btd`, mask `.dds`, `objects.json`, `navmesh.json` (`S1-04`), `overlays_params.json`, and pure sky ESM."""
    with fo4land.Plugin(fo4_esm_path) as plugin:
        strip = extract_strip_from_plugin(plugin, gx0=gx0, gx1=gx1, gy0=gy0, gy1=gy1)
    tile = strip_sf_tile(gx0, gx1, gy0, gy1)
    btd_bytes, hmin, hmax, raw_h = build_strip_btd_bytes(
        strip["grids"], tile, ltex_table=ltex_table, quad_bytes=quad_bytes
    )
    objects_doc, skipped = build_strip_objects(strip, tile, world_edid=world_edid, door_manifest=door_manifest)
    navmesh_doc, navmesh_stats = build_strip_navmesh_doc(strip, tile, world_edid=world_edid)
    has_navms = bool(navmesh_doc.get("navmeshes"))
    params_doc = build_prewar_overlay_params(
        tile,
        hmin,
        hmax,
        raw_h,
        world_edid=world_edid,
        navmesh_rel="navmesh.json" if has_navms else None,
    )

    btd_path = os.path.join(out_dir, "Data", "Terrain", f"{world_edid}.btd")
    os.makedirs(os.path.dirname(btd_path), exist_ok=True)
    with open(btd_path, "wb") as f:
        f.write(btd_bytes)

    mask_path = os.path.join(out_dir, "Data", "textures", "terrain", "overlaymasks", f"{world_edid.lower()}.dds")
    os.makedirs(os.path.dirname(mask_path), exist_ok=True)
    with open(mask_path, "wb") as f:
        f.write(overlay.dds_bc4(overlay.mask_array(tile.n, edges=("w", "e", "s", "n"))))

    obj_path = os.path.join(out_dir, "objects.json")
    with open(obj_path, "w", encoding="utf-8") as f:
        json.dump(objects_doc, f, indent=1)

    if has_navms:
        nav_path = os.path.join(out_dir, "navmesh.json")
        with open(nav_path, "w", encoding="utf-8") as f:
            json.dump(navmesh_doc, f, indent=None, separators=(",", ":"))

    prm_path = os.path.join(out_dir, "overlays_params.json")
    with open(prm_path, "w", encoding="utf-8") as f:
        json.dump(params_doc, f, indent=1)

    sky_path = None
    sky_rep = None
    if emit_standalone_sky:
        sky_path, sky_rep = build_prewar_sky_plugin(os.path.join(out_dir, "FO4SFPrewarSky.esm"))
    return {
        "rect": strip["rect"],
        "fo4_cells": len(strip["cells"]),
        "fo4_lands": len(strip["grids"]),
        "fo4_navms": len(strip["navms"]),
        "sf_navms": len(navmesh_doc.get("navmeshes", [])),
        "navmesh_stats": navmesh_stats,
        "fo4_refrs": len(strip["refrs"]),
        "fo4_achrs": len(strip["achrs"]),
        "sf_tile_n": tile.n,
        "placed_objects": len(objects_doc["refs"]),
        "distinct_bases": len(objects_doc["bases"]),
        "skipped_objects": len(skipped),
        "btd_bytes": len(btd_bytes),
        "hmin": hmin,
        "hmax": hmax,
        "sky_report": sky_rep,
        "sky_plugin": sky_path,
    }
