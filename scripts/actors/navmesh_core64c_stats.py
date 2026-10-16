"""Per-Starfield-cell navmesh stats for the core64c overlay (docs/terrain/core64c.md).

Reads Fallout4.esm Commonwealth NAVM and the staged Starfield plugins, bins triangles
into 100 m Starfield cells, and writes the JSON maps that navmesh_inventory.py compares.

    python scripts/actors/navmesh_core64c_stats.py \\
        --fo4 <Fallout4.esm> \\
        --sf C:\\Modding\\staging\\terrain_core64c\\FO4TerrainCore.esm \\
        --slice C:\\Modding\\staging\\slice_cave_core64c\\FO4SliceRedRocketCore.esm \\
        --fo4-out docs/actors/data/core64c-fo4-navmesh.json \\
        --sf-out docs/actors/data/core64c-sf-navmesh.json \\
        --meta-out docs/actors/data/core64c-navmesh-meta.json

No game assets are written: counts, areas in m^2, and file identity (basename, size, sha256).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf import fo4land  # noqa: E402
from fo4sf import navmesh as nm  # noqa: E402
from fo4sf.fo4land import (  # noqa: E402
    CELL_UNITS,
    UNITS_PER_METRE,
    iter_items,
    iter_subrecords,
    record_data,
    zstring,
)

SF_CELL_M = 100.0
CORE_CELL_MIN = -32
CORE_CELL_MAX = 31
FO4_WORLD = "Commonwealth"
SF_WORLD = "FO4Core_Commonwealth"


def overlay_fo4_cell_bounds(cell_min=CORE_CELL_MIN, cell_max=CORE_CELL_MAX):
    """Inclusive FO4 cell index range whose 4096-unit squares overlap the overlay metres."""
    m0 = cell_min * SF_CELL_M
    m1 = (cell_max + 1) * SF_CELL_M
    u0 = m0 * UNITS_PER_METRE
    u1 = m1 * UNITS_PER_METRE
    x0 = math.floor(u0 / CELL_UNITS)
    x1 = math.floor((u1 - 1e-9) / CELL_UNITS)
    return int(x0), int(x1)


def overlay_fo4_cell_set(cell_min=CORE_CELL_MIN, cell_max=CORE_CELL_MAX):
    x0, x1 = overlay_fo4_cell_bounds(cell_min, cell_max)
    return {(x, y) for x in range(x0, x1 + 1) for y in range(x0, x1 + 1)}


def cell_key(x, y):
    return f"{int(x)},{int(y)}"


def xy_area_m2(vertices_m, tri_v):
    """Horizontal (XY) area of each triangle in square metres."""
    pts = vertices_m[tri_v]
    ab = pts[:, 1, :2] - pts[:, 0, :2]
    ac = pts[:, 2, :2] - pts[:, 0, :2]
    cross = ab[:, 0] * ac[:, 1] - ab[:, 1] * ac[:, 0]
    return 0.5 * np.abs(cross)


def add_cell(stats, key, triangles, area, vertices=0):
    rec = stats.get(key)
    if rec is None:
        stats[key] = {"triangles": int(triangles), "area": float(area), "vertices": int(vertices)}
        return
    rec["triangles"] += int(triangles)
    rec["area"] += float(area)
    rec["vertices"] += int(vertices)


def merge_stats(dst, src):
    for key, rec in src.items():
        add_cell(dst, key, rec["triangles"], rec["area"], rec.get("vertices", 0))


def bin_triangles(vertices, tri_v, units_per_metre, cell_min=CORE_CELL_MIN, cell_max=CORE_CELL_MAX):
    """Bin triangles into overlay Starfield cells by XY centroid. vertices in file units."""
    if len(tri_v) == 0 or len(vertices) == 0:
        return {}, 0
    verts_m = np.asarray(vertices, dtype=np.float64) / float(units_per_metre)
    areas = xy_area_m2(verts_m, tri_v)
    centroids = verts_m[tri_v].mean(axis=1)
    cx = np.floor(centroids[:, 0] / SF_CELL_M).astype(np.int64)
    cy = np.floor(centroids[:, 1] / SF_CELL_M).astype(np.int64)
    inside = (cx >= cell_min) & (cx <= cell_max) & (cy >= cell_min) & (cy <= cell_max)
    out = {}
    n_in = int(inside.sum())
    if n_in:
        for x, y, area in zip(cx[inside].tolist(), cy[inside].tolist(), areas[inside].tolist()):
            add_cell(out, cell_key(x, y), 1, float(area), 0)
    return out, n_in


def file_identity(path: Path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"name": path.name, "size": int(path.stat().st_size), "sha256": digest.hexdigest()}


def count_plugin_records(path: Path):
    """Count every record signature, plus WRLD/CELL editor ids and NAVM count."""
    counts = Counter()
    worlds = []
    cells = []
    navm = 0
    with fo4land.Plugin(str(path)) as plugin:
        def walk(start, end):
            nonlocal navm
            for it in iter_items(plugin.buf, start, end):
                if it[0] == "GRUP":
                    walk(it[1] + 24, it[2])
                    continue
                typ, off, _flags, fid = it
                counts[typ.decode("ascii")] += 1
                if typ == b"NAVM":
                    navm += 1
                    continue
                if typ not in (b"WRLD", b"CELL"):
                    continue
                edid = ""
                for sig, data in iter_subrecords(record_data(plugin.buf, off)):
                    if sig == b"EDID":
                        edid = zstring(data)
                        break
                entry = {"formid": f"{fid:08X}", "edid": edid}
                if typ == b"WRLD":
                    worlds.append(entry)
                else:
                    cells.append(entry)

        walk(plugin.body, len(plugin.buf))
    return {
        "records": dict(sorted(counts.items())),
        "navm": navm,
        "worlds": worlds,
        "cells": cells,
    }


def collect_world_navmeshes(plugin_path, world_edid, cells, units_per_metre, layout=None):
    """Parse NAVM in one worldspace and bin triangles into overlay Starfield cells."""
    stats = {}
    parsed = 0
    triangles = 0
    in_overlay = 0
    errors = 0
    with fo4land.Plugin(str(plugin_path)) as plugin:
        try:
            raw = nm.world_navmeshes(plugin, world_edid, cells)
        except KeyError:
            return {
                "stats": stats,
                "world_missing": world_edid,
                "records": 0,
                "parsed": 0,
                "triangles": 0,
                "triangles_in_overlay": 0,
                "parse_errors": 0,
            }
    for _cell, _fid, _flags, blob in raw:
        try:
            mesh = nm.parse(blob, layout=layout)
        except nm.NavmeshError:
            errors += 1
            continue
        parsed += 1
        tri_v = mesh.triangles["v"]
        triangles += int(len(tri_v))
        part, n_in = bin_triangles(mesh.vertices, tri_v, units_per_metre)
        in_overlay += n_in
        if part:
            first = next(iter(part))
            part[first]["vertices"] += int(len(mesh.vertices))
            merge_stats(stats, part)
    return {
        "stats": stats,
        "records": len(raw),
        "parsed": parsed,
        "triangles": triangles,
        "triangles_in_overlay": in_overlay,
        "parse_errors": errors,
    }


def round_stats(stats):
    out = {}
    for key in sorted(stats, key=lambda k: tuple(int(p) for p in k.split(","))):
        rec = stats[key]
        out[key] = {
            "triangles": int(rec["triangles"]),
            "area": round(float(rec["area"]), 6),
            "vertices": int(rec.get("vertices", 0)),
        }
    return out


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"{path} already exists; will not overwrite")
    text = json.dumps(obj, indent=2) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fo4", type=Path, required=True, help="Fallout4.esm")
    ap.add_argument("--sf", type=Path, required=True, help="FO4TerrainCore.esm")
    ap.add_argument("--slice", type=Path, help="FO4SliceRedRocketCore.esm")
    ap.add_argument("--fo4-out", type=Path, required=True)
    ap.add_argument("--sf-out", type=Path, required=True)
    ap.add_argument("--meta-out", type=Path, required=True)
    ap.add_argument("--cell-min", type=int, default=CORE_CELL_MIN)
    ap.add_argument("--cell-max", type=int, default=CORE_CELL_MAX)
    args = ap.parse_args(argv)

    cell_min, cell_max = args.cell_min, args.cell_max
    fo4_lo, fo4_hi = overlay_fo4_cell_bounds(cell_min, cell_max)
    want = overlay_fo4_cell_set(cell_min, cell_max)

    sf_plugins = [("terrain", args.sf)]
    if args.slice is not None:
        sf_plugins.append(("slice", args.slice))

    plugin_info = {}
    sf_stats = {}
    sf_navm_total = 0
    for label, path in sf_plugins:
        info = count_plugin_records(path)
        ident = file_identity(path)
        world = collect_world_navmeshes(path, SF_WORLD, None, 1.0, layout="sf")
        merge_stats(sf_stats, world["stats"])
        sf_navm_total += info["navm"]
        cells = info["cells"]
        plugin_info[label] = {
            "file": ident,
            "records": info["records"],
            "navm": info["navm"],
            "worlds": info["worlds"],
            "cell_count": len(cells),
            "cells": cells if len(cells) <= 16 else [],
            "world_walk": {k: world[k] for k in world if k != "stats"},
        }

    print(
        f"FO4 overlay FO4-cells {fo4_lo}..{fo4_hi} ({len(want)} cells); reading {args.fo4.name} ...",
        flush=True,
    )
    fo4_ident = file_identity(args.fo4)
    fo4_world = collect_world_navmeshes(args.fo4, FO4_WORLD, want, UNITS_PER_METRE, layout="fo4")
    fo4_stats = round_stats(fo4_world["stats"])
    sf_stats = round_stats(sf_stats)

    meta = {
        "overlay": {
            "world": SF_WORLD,
            "starfield_cells": {"min": cell_min, "max": cell_max, "n": (cell_max - cell_min + 1) ** 2},
            "fo4_cells": {"min": fo4_lo, "max": fo4_hi, "n": (fo4_hi - fo4_lo + 1) ** 2},
            "units_per_metre": UNITS_PER_METRE,
            "starfield_cell_m": SF_CELL_M,
        },
        "fo4": {
            "file": fo4_ident,
            "world": FO4_WORLD,
            **{k: fo4_world[k] for k in fo4_world if k != "stats"},
            "overlay_cells_with_navmesh": len(fo4_stats),
            "overlay_triangles": sum(r["triangles"] for r in fo4_stats.values()),
            "overlay_area_m2": round(sum(r["area"] for r in fo4_stats.values()), 6),
        },
        "sf": {
            "navm_records": sf_navm_total,
            "overlay_cells_with_navmesh": len(sf_stats),
            "overlay_triangles": sum(r["triangles"] for r in sf_stats.values()),
            "overlay_area_m2": round(sum(r["area"] for r in sf_stats.values()), 6),
            "plugins": plugin_info,
        },
    }

    write_json(args.fo4_out, fo4_stats)
    write_json(args.sf_out, sf_stats)
    write_json(args.meta_out, meta)
    print(
        f"FO4 NAVM {fo4_world['records']} parsed {fo4_world['parsed']}; "
        f"overlay triangles {meta['fo4']['overlay_triangles']} in {len(fo4_stats)} SF cells; "
        f"SF NAVM records {sf_navm_total}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
