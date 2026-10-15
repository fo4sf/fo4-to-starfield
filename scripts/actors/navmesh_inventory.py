"""Offline inventory of navmesh coverage loss between Fallout 4 source and converted Starfield cells.

usage: python scripts/actors/navmesh_inventory.py --fo4-stats <json> --sf-stats <json> [--out <report.json>]

Reads two JSON maps of cell_id -> {"triangles": N, "area": F, "vertices": N} (or similar) and reports
cells that lost coverage (zero or significantly reduced triangles/area in SF) and why (missing, reduced, etc.).

No game data; synthetic-fixture friendly. Deterministic.
"""
import argparse
import json
import sys
from pathlib import Path


def inventory(fo4: dict, sf: dict, area_tol: float = 0.5, tri_tol: float = 0.5) -> dict:
    """Return inventory of losses. Keys are cell identifiers (str)."""
    lost = []
    reduced = []
    gained = []
    unchanged = []
    all_cells = set(fo4) | set(sf)
    for cell in sorted(all_cells):
        f = fo4.get(cell, {})
        s = sf.get(cell, {})
        f_tri = f.get("triangles", 0)
        s_tri = s.get("triangles", 0)
        f_area = f.get("area", 0.0)
        s_area = s.get("area", 0.0)
        if f_tri > 0 and s_tri == 0:
            lost.append({"cell": cell, "fo4_triangles": f_tri, "reason": "missing in SF"})
        elif f_tri > 0 and (s_tri < f_tri * tri_tol or s_area < f_area * area_tol):
            reduced.append({
                "cell": cell,
                "fo4_triangles": f_tri, "sf_triangles": s_tri,
                "fo4_area": f_area, "sf_area": s_area,
                "reason": "reduced coverage"
            })
        elif s_tri > f_tri and f_tri == 0:
            gained.append({"cell": cell, "sf_triangles": s_tri, "reason": "new in SF"})
        else:
            unchanged.append(cell)
    return {
        "total_fo4_cells": len(fo4),
        "total_sf_cells": len(sf),
        "lost_coverage": lost,
        "reduced_coverage": reduced,
        "gained_coverage": gained,
        "unchanged": len(unchanged),
        "summary": f"{len(lost)} lost, {len(reduced)} reduced, {len(gained)} gained"
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fo4-stats", required=True, type=Path)
    ap.add_argument("--sf-stats", required=True, type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--area-tol", type=float, default=0.5)
    ap.add_argument("--tri-tol", type=float, default=0.5)
    a = ap.parse_args()
    fo4 = json.loads(a.fo4_stats.read_text())
    sf = json.loads(a.sf_stats.read_text())
    report = inventory(fo4, sf, a.area_tol, a.tri_tol)
    text = json.dumps(report, indent=2)
    if a.out:
        a.out.write_text(text)
        print(f"wrote {a.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
