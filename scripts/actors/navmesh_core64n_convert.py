"""Run exp2d's navmesh.convert over the core64c FO4 cell window (docs/actors/navmesh-conversion.md).

    python scripts/actors/navmesh_core64n_convert.py ^
        --fo4 <Fallout4.esm> ^
        --out <staging>/terrain_core64n_work/navmesh ^
        --inventory-fo4 docs/actors/data/core64c-fo4-navmesh.json ^
        --export-dir <staging>/terrain_core64c_work/export ^
        --objects <staging>/terrain_core64c/objects.json ^
        --summary-out docs/actors/data/core64n-convert-report.json

Reads Commonwealth NAVM from Fallout4.esm in FO4 cells x,y -55..54 (the 11 core64c export bands),
cuts each at Starfield's 100 m lines, writes navmesh.json in the TerrainExp2 export shape, and a
per-cell comparison against the #163 inventory. Geometry stays in --out (not git). Offline only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "actors"))
from fo4sf import fo4land  # noqa: E402
from fo4sf import navmesh as nm  # noqa: E402
import navmesh_core64c_stats as stats  # noqa: E402
import navmesh_inventory as inv  # noqa: E402

OVERFLOW_RE = re.compile(r"piece \((\d+),")
CORE_CELL_MIN = stats.CORE_CELL_MIN
CORE_CELL_MAX = stats.CORE_CELL_MAX
FO4_WORLD = "Commonwealth"


def cell_key(cell):
    return stats.cell_key(cell[0], cell[1])


def list_export_bands(export_dir: Path):
    paths = sorted(p for p in export_dir.glob("band_*.json") if p.is_file())
    return [{"name": p.name, "size": int(p.stat().st_size)} for p in paths]


def door_sources_from_objects(objects: dict):
    """{Fallout 4 REFR FormID: source key} of converted rigged DOOR references (make_exp2d.door_sources)."""
    bases = objects["bases"]
    out = {}
    if isinstance(bases, dict):
        def is_door(ref):
            return "door" in bases[ref["base"]]
    else:
        def is_door(ref):
            return "door" in bases[int(ref["base"])]
    for ref in objects["refs"]:
        if is_door(ref):
            out[int(ref["src"].split(":")[0], 16)] = ref["src"]
    return out


def parse_overflow_fid(message: str):
    match = OVERFLOW_RE.search(message)
    return int(match.group(1)) if match else None


def empty_convert_report():
    return {
        "fo4_navmeshes": 0, "fo4_triangles": 0, "fo4_vertices": 0, "pieces": 0, "triangles": 0,
        "clipped_triangles": 0, "sliver_triangles_dropped": 0, "nonmanifold_edges": 0,
        "links": {"cell_line": 0, "fo4_portal": 0},
        "dropped": {"fo4_links_outside": 0, "fo4_links_ledge_type1_2": 0, "fo4_portal_no_overlap": 0,
                    "fo4_portal_subedge_missing": 0, "cover_entries": 0, "cover_flag_triangles": 0,
                    "water_flag_triangles": 0, "doors_not_converted": 0, "waypoints_not_found": 0,
                    "deleted_triangles": 0},
        "kept": {"doors": 0, "waypoints": 0},
    }


def convert_with_refusals(fo4, door_refs=None):
    """nm.convert, dropping FO4 navmeshes whose pieces exceed i16 indices and listing them."""
    remaining = list(fo4)
    refused = []
    while remaining:
        try:
            pieces, report = nm.convert(remaining, door_refs=door_refs)
            return pieces, report, refused
        except nm.NavmeshError as exc:
            fid = parse_overflow_fid(str(exc))
            if fid is None:
                raise
            refused.append({
                "id": f"{fid:08X}",
                "reason": "i16_index_overflow",
                "detail": str(exc),
            })
            remaining = [(f, mesh) for f, mesh in remaining if f != fid]
    return [], empty_convert_report(), refused


def load_fo4_navmeshes(fo4_path: Path, cells):
    parsed = []
    refused = []
    with fo4land.Plugin(str(fo4_path)) as plugin:
        raw = nm.world_navmeshes(plugin, FO4_WORLD, cells)
    for cell, fid, _flags, blob in raw:
        try:
            mesh = nm.parse(blob, layout="fo4")
        except nm.NavmeshError as exc:
            refused.append({
                "id": f"{fid:08X}",
                "cell": list(cell) if cell is not None else None,
                "reason": "parse",
                "detail": str(exc),
            })
            continue
        parsed.append((fid, mesh))
    return parsed, refused


def piece_area(pc):
    """Horizontal (XY) area in m², same measure as the #163 inventory."""
    if not pc.tris:
        return 0.0
    verts = np.asarray(pc.pos, np.float64).reshape(-1, 3)
    tri_v = np.asarray(pc.tris, np.int16)
    return float(stats.xy_area_m2(verts, tri_v).sum())


def cell_stats_from_pieces(pieces):
    """Per Starfield cell: NAVM count, triangles, XY area, link ends by kind."""
    out = {}
    for pc in pieces:
        rec = out.get(cell_key(pc.cell))
        if rec is None:
            rec = out[cell_key(pc.cell)] = {
                "navm": 0, "triangles": 0, "vertices": 0, "area": 0.0,
                "cell_line_links": 0, "fo4_portal_links": 0,
            }
        rec["navm"] += 1
        rec["triangles"] += len(pc.tris)
        rec["vertices"] += len(pc.pos)
        rec["area"] += piece_area(pc)
        for _typ, tgt, _tri, _edge in pc.links:
            kind = "cell_line_links" if pieces[tgt].src == pc.src else "fo4_portal_links"
            rec[kind] += 1
    return round_cell_stats(out)


def round_cell_stats(raw):
    out = {}
    for key in sorted(raw, key=lambda k: tuple(int(p) for p in k.split(","))):
        rec = raw[key]
        out[key] = {
            "navm": int(rec["navm"]),
            "triangles": int(rec["triangles"]),
            "vertices": int(rec["vertices"]),
            "area": round(float(rec["area"]), 6),
            "cell_line_links": int(rec["cell_line_links"]),
            "fo4_portal_links": int(rec["fo4_portal_links"]),
        }
    return out


def in_overlay(cell, cell_min=CORE_CELL_MIN, cell_max=CORE_CELL_MAX):
    return cell_min <= cell[0] <= cell_max and cell_min <= cell[1] <= cell_max


def overlay_stats(cell_stats, cell_min=CORE_CELL_MIN, cell_max=CORE_CELL_MAX):
    keep = {}
    for key, rec in cell_stats.items():
        x, y = (int(p) for p in key.split(","))
        if in_overlay((x, y), cell_min, cell_max):
            keep[key] = rec
    return keep


def compare_to_inventory(fo4_inventory, converted_overlay):
    """#163 FO4-binned triangles vs converted pieces in the same overlay cells."""
    sf_for_inv = {
        key: {"triangles": rec["triangles"], "area": rec["area"]}
        for key, rec in converted_overlay.items()
    }
    report = inv.inventory(fo4_inventory, sf_for_inv)
    rows = []
    cells = set(fo4_inventory) | set(converted_overlay)
    for key in sorted(cells, key=lambda k: tuple(int(p) for p in k.split(","))):
        fo4 = fo4_inventory.get(key) or {"triangles": 0, "area": 0.0}
        conv = converted_overlay.get(key) or {
            "navm": 0, "triangles": 0, "vertices": 0, "area": 0.0,
            "cell_line_links": 0, "fo4_portal_links": 0,
        }
        rows.append({
            "cell": key,
            "fo4_triangles": int(fo4.get("triangles") or 0),
            "fo4_area": float(fo4.get("area") or 0.0),
            "navm": int(conv.get("navm") or 0),
            "triangles": int(conv.get("triangles") or 0),
            "area": float(conv.get("area") or 0.0),
            "cell_line_links": int(conv.get("cell_line_links") or 0),
            "fo4_portal_links": int(conv.get("fo4_portal_links") or 0),
        })
    densest = sorted(rows, key=lambda r: (-r["triangles"], r["cell"]))[:10]
    return {
        "inventory": {
            "lost": len(report["lost_coverage"]),
            "reduced": len(report["reduced_coverage"]),
            "gained": len(report["gained_coverage"]),
            "unchanged": report["unchanged"],
            "unknown": len(report["unknown"]),
            "summary": report["summary"],
            "total_fo4_triangles": report["total_fo4_triangles"],
            "total_sf_triangles": report["total_sf_triangles"],
        },
        "densest_converted": densest,
        "named_cells": {
            key: next((r for r in rows if r["cell"] == key), None)
            for key in ("-10,11", "-11,11", "2,-4", "2,14", "14,6")
        },
    }


def write_json(path: Path, obj, indent=2):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"{path} already exists; will not overwrite")
    text = json.dumps(obj, indent=indent) + ("\n" if indent is not None else "")
    path.write_text(text, encoding="utf-8", newline="\n")


def write_export(path: Path, pieces):
    """TerrainExp2 navmesh.json (nm.export) written piece by piece so the full dict is not held."""
    if path.exists():
        raise FileExistsError(f"{path} already exists; will not overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write('{"version": 1, "navmeshes": [')
        for i, pc in enumerate(pieces):
            if i:
                handle.write(",")
            json.dump(nm.export([pc])["navmeshes"][0], handle, indent=None, separators=(",", ":"))
        handle.write("]}")


def refused_ids(rows):
    return sorted({row["id"] for row in rows})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fo4", type=Path, required=True, help="Fallout4.esm")
    ap.add_argument("--out", type=Path, required=True, help="staging folder for navmesh.json (not git)")
    ap.add_argument("--inventory-fo4", type=Path, help="docs/actors/data/core64c-fo4-navmesh.json")
    ap.add_argument("--export-dir", type=Path, help="core64c work/export (11 band_*.json)")
    ap.add_argument("--objects", type=Path, help="core64c objects.json for converted DOOR refs")
    ap.add_argument("--summary-out", type=Path, help="counts-only JSON for the report PR")
    ap.add_argument("--cell-min", type=int, default=CORE_CELL_MIN)
    ap.add_argument("--cell-max", type=int, default=CORE_CELL_MAX)
    ap.add_argument("--fo4-x0", type=int)
    ap.add_argument("--fo4-y0", type=int)
    ap.add_argument("--fo4-x1", type=int)
    ap.add_argument("--fo4-y1", type=int)
    args = ap.parse_args(argv)

    t0 = time.time()
    cell_min, cell_max = args.cell_min, args.cell_max
    if None not in (args.fo4_x0, args.fo4_y0, args.fo4_x1, args.fo4_y1):
        want = {(x, y) for x in range(args.fo4_x0, args.fo4_x1 + 1)
                for y in range(args.fo4_y0, args.fo4_y1 + 1)}
        fo4_lo, fo4_hi = args.fo4_x0, args.fo4_x1
        fo4_y0, fo4_y1 = args.fo4_y0, args.fo4_y1
    else:
        fo4_lo, fo4_hi = stats.overlay_fo4_cell_bounds(cell_min, cell_max)
        fo4_y0, fo4_y1 = fo4_lo, fo4_hi
        want = stats.overlay_fo4_cell_set(cell_min, cell_max)

    bands = list_export_bands(args.export_dir) if args.export_dir else []
    fo4_ident = stats.file_identity(args.fo4)
    print(f"FO4 {fo4_ident['name']} {fo4_ident['size']} B cells {fo4_lo}..{fo4_hi} x {fo4_y0}..{fo4_y1} "
          f"({len(want)} FO4 cells), {len(bands)} export bands", flush=True)

    door_refs = {}
    if args.objects is not None:
        objects = json.loads(args.objects.read_text(encoding="utf-8"))
        door_refs = door_sources_from_objects(objects)
        print(f"converted DOOR refs {len(door_refs)}", flush=True)

    loaded, parse_refused = load_fo4_navmeshes(args.fo4, want)
    print(f"parsed {len(loaded)} NAVM, parse refused {len(parse_refused)}", flush=True)
    pieces, report, overflow_refused = convert_with_refusals(loaded, door_refs=door_refs)
    refused = parse_refused + overflow_refused
    print(
        f"converted {report['fo4_navmeshes']} navmeshes ({report['fo4_triangles']:,} triangles) into "
        f"{report['pieces']} Starfield navmeshes ({report['triangles']:,} triangles), "
        f"links {report['links']}, refused {len(refused)}",
        flush=True,
    )

    all_stats = cell_stats_from_pieces(pieces)
    over_stats = overlay_stats(all_stats, cell_min, cell_max)
    outside = {k: v for k, v in all_stats.items() if k not in over_stats}

    inventory_cmp = None
    if args.inventory_fo4 is not None:
        fo4_inv = json.loads(args.inventory_fo4.read_text(encoding="utf-8"))
        inventory_cmp = compare_to_inventory(fo4_inv, over_stats)

    summary = {
        "overlay": {
            "starfield_cells": {"min": cell_min, "max": cell_max, "n": (cell_max - cell_min + 1) ** 2},
            "fo4_cells": {"x": [fo4_lo, fo4_hi], "y": [fo4_y0, fo4_y1], "n": len(want)},
            "starfield_cell_m": stats.SF_CELL_M,
            "units_per_metre": stats.UNITS_PER_METRE,
        },
        "fo4": {"file": fo4_ident, "parsed": len(loaded), "parse_refused": len(parse_refused)},
        "export_bands": bands,
        "doors": {"converted_refs": len(door_refs)},
        "convert": report,
        "refused": refused,
        "refused_ids": refused_ids(refused),
        "pieces": {
            "all": report["pieces"],
            "overlay_cells": len(over_stats),
            "overlay_navm": sum(r["navm"] for r in over_stats.values()),
            "overlay_triangles": sum(r["triangles"] for r in over_stats.values()),
            "overlay_area_m2": round(sum(r["area"] for r in over_stats.values()), 6),
            "outside_overlay_cells": len(outside),
            "outside_overlay_navm": sum(r["navm"] for r in outside.values()),
            "outside_overlay_triangles": sum(r["triangles"] for r in outside.values()),
        },
        "links": report["links"],
        "inventory_comparison": inventory_cmp,
        "seconds": round(time.time() - t0, 1),
    }

    args.out.mkdir(parents=True, exist_ok=True)
    write_export(args.out / "navmesh.json", pieces)
    write_json(args.out / "navmesh_report.json", report)
    write_json(args.out / "cell_stats.json", over_stats)
    write_json(args.out / "refused.json", refused)
    write_json(args.out / "summary.json", summary)
    if args.summary_out is not None:
        slim = dict(summary)
        slim["inventory_comparison"] = None if inventory_cmp is None else {
            **inventory_cmp,
            "densest_converted": inventory_cmp["densest_converted"][:10],
        }
        write_json(args.summary_out, slim)
    print(f"wrote {args.out} in {summary['seconds']} s; overlay NAVM "
          f"{summary['pieces']['overlay_navm']} triangles {summary['pieces']['overlay_triangles']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
