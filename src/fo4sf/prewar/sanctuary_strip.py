"""Extract the bounded SanctuaryHillsWorld pre-war strip, build its BTD/objects, and emit pure pre-war weather/sky."""
from __future__ import annotations

import json
import math
import os
import struct
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from fo4sf import btd, exterior, fo4land, navmesh, overlay, overlay_grid as og, terrain_grid as tg
from fo4sf.planet import esm, home_planet_spec as hspec, wb_records
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
) -> Tuple[dict, List[dict]]:
    """Build `objects.json` (`bases`, `refs`) in `tile`'s local frame reusing `exterior.classify`."""
    bases_meta = strip["bases"]
    selected_bases: Dict[str, dict] = {}
    placed_refs: List[dict] = []
    skipped: List[dict] = []

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
        if bed not in selected_bases:
            selected_bases[bed] = {"edid": f"FO4Prewar_{bed}", "model": sf_model, "fo4_fid": f"0x{r['base']:08X}"}

        px, py, pz = [c / tg.UNITS_PER_METRE for c in r["pos"]]
        lx, ly = px - ox, py - oy
        sc = tg.sf_cell_of(lx, ly)
        placed_refs.append({
            "src": f"{r['fid']:06X}:Fallout4.esm",
            "base": selected_bases[bed]["edid"],
            "cell": [int(sc[0]), int(sc[1])],
            "pos": [round(lx, 4), round(ly, 4), round(pz, 4)],
            "rot": [round(float(a), 6) for a in r["rot"]],
            "scale": round(float(r["scale"]), 4),
            "disabled": bool(r["disabled"]),
        })

    doc = {
        "world": world_edid,
        "bases": sorted(selected_bases.values(), key=lambda x: x["edid"]),
        "refs": placed_refs,
    }
    return doc, skipped


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


def verify_zero_starfield_sky_refs(plugin_path: str) -> None:
    """Strictly verify a pre-war sky/world plugin carries zero Starfield PNDT/LCTN/CLMT/WTHR/ATMO references."""
    with esm.Plugin(plugin_path) as p:
        if p.masters:
            raise ValueError(f"{plugin_path} must have 0 masters for pure sky records, got {p.masters}")
        allowed_locals: set[int] = set()
        for grp in ("WTHR", "CLMT", "ATMO"):
            for rec in p.records(grp, [grp.encode("ascii")]):
                allowed_locals.add(rec.formid & 0xFFFFFF)

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
                    if (wfid >> 24) != 0 or (wfid & 0xFFFFFF) not in allowed_locals:
                        raise ValueError(f"CLMT {rec.edid} WLST references external weather 0x{wfid:08X}")
        for grp in ("PNDT", "LCTN"):
            if list(p.records(grp, [grp.encode("ascii")])):
                raise ValueError(f"{plugin_path} must not contain Starfield {grp} records")


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
) -> dict:
    """Assemble `overlays_params.json` compatible with `dotnet/TerrainOverlays` targeting `FO4SFHome` (`EarthPlanetData`)."""
    sx_cw, sy_cw, sz_cw = s1_spec.SANCTUARY_KEY_COORDS_M["player_start"]
    lx, ly = tile.to_local(sx_cw, sy_cw)
    spawn = [round(lx, 4), round(ly, 4), round(sz_cw + 0.5, 4)]
    spawn_cell = list(tg.sf_cell_of(lx, ly))
    return {
        "plugin": plugin_name,
        "prefix": "FO4SFPrewar",
        "hmin": float(hmin),
        "hmax": float(hmax),
        "alignment": "absolute",
        "hnam": 0,
        "mars": None,
        "host": {
            "planet_plugin": hspec.HOME_MASTER,
            "planet_edid": "EarthPlanetData",
            "surface_location": f"0x{0x01000000 | hspec.SURFACE_LOC:08X}:{hspec.HOME_MASTER}",
            "system_id": int(host_system_id),
            "planet_id": int(host_planet_id),
            "biome": f"0x{0x01000000 | hspec.BIOME:08X}:{hspec.HOME_MASTER}",
        },
        "objects": objects_rel,
        "overlays": [
            {
                "world": world_edid,
                "tag": "SanctuaryPrewar",
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
) -> Dict[str, Any]:
    """Materialize local strip `.btd`, mask `.dds`, `objects.json`, `overlays_params.json`, and pure sky ESM."""
    with fo4land.Plugin(fo4_esm_path) as plugin:
        strip = extract_strip_from_plugin(plugin, gx0=gx0, gx1=gx1, gy0=gy0, gy1=gy1)
    tile = strip_sf_tile(gx0, gx1, gy0, gy1)
    btd_bytes, hmin, hmax, raw_h = build_strip_btd_bytes(
        strip["grids"], tile, ltex_table=ltex_table, quad_bytes=quad_bytes
    )
    objects_doc, skipped = build_strip_objects(strip, tile, world_edid=world_edid)
    params_doc = build_prewar_overlay_params(tile, hmin, hmax, raw_h, world_edid=world_edid)

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

    prm_path = os.path.join(out_dir, "overlays_params.json")
    with open(prm_path, "w", encoding="utf-8") as f:
        json.dump(params_doc, f, indent=1)

    sky_path, sky_rep = build_prewar_sky_plugin(os.path.join(out_dir, "FO4SFPrewarSky.esm"))
    return {
        "rect": strip["rect"],
        "fo4_cells": len(strip["cells"]),
        "fo4_lands": len(strip["grids"]),
        "fo4_navms": len(strip["navms"]),
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
