"""Offline inventory of navmesh coverage loss between Fallout 4 source and converted Starfield cells.

usage: python scripts/actors/navmesh_inventory.py --fo4-stats <json> --sf-stats <json> [--out <report.json>]

Reads two JSON maps of cell_id -> {"triangles": N, "area": F, "vertices": N} (or similar) and reports
cells that lost coverage (zero or significantly reduced triangles/area in SF) and why (missing, reduced, etc.).

No game data; synthetic-fixture friendly. Deterministic.
"""
import argparse
import json
import math
import os
import sys
from pathlib import Path


def _finite_nonneg(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if isinstance(value, float) and not math.isfinite(value):
        return False
    return value >= 0


def _integral_count(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if isinstance(value, float):
        return math.isfinite(value) and value.is_integer() and value >= 0
    return value >= 0


def _ratio(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if not math.isfinite(value):
        return False
    return 0 < float(value) <= 1


def _measure(record):
    if not isinstance(record, dict):
        return None
    if "triangles" not in record or "area" not in record:
        return None
    triangles = record["triangles"]
    area = record["area"]
    if not _integral_count(triangles) or not _finite_nonneg(area):
        return None
    verts = record.get("vertices")
    if verts is not None and not _integral_count(verts):
        return None
    return int(triangles), float(area), (int(verts) if verts is not None else None)


def inventory(fo4: dict, sf: dict, area_tol: float = 0.5, tri_tol: float = 0.5) -> dict:
    """Return inventory of losses. Keys are cell identifiers (str)."""
    if not _ratio(area_tol) or not _ratio(tri_tol):
        raise ValueError("area_tol and tri_tol must be finite ratios in (0, 1]")
    if not isinstance(fo4, dict) or not isinstance(sf, dict):
        raise ValueError("fo4 and sf stats must be objects")
    lost = []
    reduced = []
    gained = []
    unchanged = []
    unknown = []
    all_cells = set(fo4) | set(sf)
    for cell in sorted(all_cells):
        in_fo4 = cell in fo4
        in_sf = cell in sf
        fo4_m = _measure(fo4[cell]) if in_fo4 else None
        sf_m = _measure(sf[cell]) if in_sf else None
        if in_fo4 and fo4_m is None:
            unknown.append({"cell": cell, "reason": "invalid fo4 measurement"})
            continue
        if in_sf and sf_m is None:
            unknown.append({"cell": cell, "reason": "invalid sf measurement"})
            continue
        if in_fo4 and not in_sf:
            fo4_tri, _fo4_area, _fo4_verts = fo4_m
            if fo4_tri > 0:
                lost.append({"cell": cell, "fo4_triangles": fo4_tri, "reason": "missing in SF"})
            else:
                unchanged.append(cell)
            continue
        if in_sf and not in_fo4:
            sf_tri, _sf_area, _sf_verts = sf_m
            if sf_tri > 0:
                gained.append({"cell": cell, "sf_triangles": sf_tri, "reason": "new in SF"})
            else:
                unchanged.append(cell)
            continue
        fo4_tri, fo4_area, fo4_verts = fo4_m
        sf_tri, sf_area, sf_verts = sf_m
        if fo4_tri > 0 and sf_tri == 0:
            lost.append({"cell": cell, "fo4_triangles": fo4_tri, "reason": "missing in SF"})
        elif fo4_tri > 0 and (sf_tri < fo4_tri * tri_tol or sf_area < fo4_area * area_tol):
            reduced.append({
                "cell": cell,
                "fo4_triangles": fo4_tri, "sf_triangles": sf_tri,
                "fo4_area": fo4_area, "sf_area": sf_area,
                "reason": "reduced coverage",
            })
        elif sf_tri > fo4_tri and fo4_tri == 0:
            gained.append({"cell": cell, "sf_triangles": sf_tri, "reason": "new in SF"})
        else:
            unchanged.append(cell)
    fo4_tris = sum(_measure(fo4[c])[0] for c in fo4 if _measure(fo4[c]))
    sf_tris = sum(_measure(sf[c])[0] for c in sf if _measure(sf[c]))
    fo4_vert_vals = [m[2] for c in fo4 if (m := _measure(fo4[c])) and m[2] is not None]
    sf_vert_vals = [m[2] for c in sf if (m := _measure(sf[c])) and m[2] is not None]
    verts_comparable = bool(fo4_vert_vals) and bool(sf_vert_vals)
    if verts_comparable:
        fo4_verts = sum(fo4_vert_vals)
        sf_verts = sum(sf_vert_vals)
        vert_pct = round(100.0 * sf_verts / fo4_verts, 1) if fo4_verts else 100.0
        vert_summary = f"; verts {fo4_verts} -> {sf_verts}"
    else:
        fo4_verts = 0
        sf_verts = 0
        vert_pct = None
        vert_summary = ""
    lost_tris = sum(item["fo4_triangles"] for item in lost)
    # Area-flagged cells can have more SF triangles than FO4; a loss count must not go negative.
    reduced_tris = sum(
        max(0, item["fo4_triangles"] - item.get("sf_triangles", 0))
        for item in reduced
        if "fo4_triangles" in item
    )
    retention_pct = round(100.0 * sf_tris / fo4_tris, 1) if fo4_tris else 100.0
    report = {
        "total_fo4_cells": len(fo4),
        "total_sf_cells": len(sf),
        "total_fo4_triangles": fo4_tris,
        "total_sf_triangles": sf_tris,
        "triangle_retention_percent": retention_pct,
        "total_fo4_vertices": fo4_verts,
        "total_sf_vertices": sf_verts,
        "lost_triangles": lost_tris,
        "reduced_triangles_approx": reduced_tris,
        "lost_coverage": lost,
        "reduced_coverage": reduced,
        "gained_coverage": gained,
        "example_lost": [item["cell"] for item in lost[:3]],
        "example_reduced": [item["cell"] for item in reduced[:3]],
        "unknown": unknown,
        "unchanged": len(unchanged),
        "summary": (
            f"{len(lost)} lost ({lost_tris} tris), {len(reduced)} reduced ({reduced_tris} tris approx), {len(gained)} gained, "
            f"{len(unknown)} unknown; FO4 tris {fo4_tris} -> SF {sf_tris} ({retention_pct}% retained)"
            + vert_summary
        ),
    }
    if vert_pct is not None:
        report["vertex_retention_percent"] = vert_pct
    return report


def _same_file(left: Path, right: Path) -> bool:
    try:
        left_r = left.resolve()
        right_r = right.resolve()
    except OSError:
        return False
    if left_r == right_r:
        return True
    try:
        left_stat = left.stat()
        right_stat = right.stat()
    except OSError:
        return False
    return left_stat.st_dev == right_stat.st_dev and left_stat.st_ino == right_stat.st_ino and left_stat.st_ino != 0


def _unlink_if_owned(path: Path, dev, ino) -> None:
    """Remove path only if it is still the inode we exclusively created."""
    if not ino:
        return
    try:
        now = path.stat()
    except OSError:
        return
    if now.st_dev == dev and now.st_ino == ino:
        try:
            path.unlink()
        except OSError:
            return


def _write_exclusive(path: Path, text: str) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = os.open(path, flags)
    owned = os.fstat(fd)
    handle = None
    try:
        handle = os.fdopen(fd, "w", encoding="utf-8", newline="\n")
        fd = None
        handle.write(text)
        handle.flush()
    except Exception:
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
            handle = None
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
            fd = None
        _unlink_if_owned(path, owned.st_dev, owned.st_ino)
        raise
    finally:
        if handle is not None:
            handle.close()
        if fd is not None:
            os.close(fd)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fo4-stats", required=True, type=Path)
    ap.add_argument("--sf-stats", required=True, type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--area-tol", type=float, default=0.5)
    ap.add_argument("--tri-tol", type=float, default=0.5)
    a = ap.parse_args()
    if a.out is not None:
        if _same_file(a.out, a.fo4_stats) or _same_file(a.out, a.sf_stats):
            print("error: --out must not overwrite --fo4-stats or --sf-stats", file=sys.stderr)
            return 2
        if a.out.exists():
            print("error: --out already exists; will not overwrite", file=sys.stderr)
            return 2
    try:
        fo4 = json.loads(a.fo4_stats.read_text(encoding="utf-8"))
        sf = json.loads(a.sf_stats.read_text(encoding="utf-8"))
        report = inventory(fo4, sf, a.area_tol, a.tri_tol)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(report, indent=2)
    if a.out:
        try:
            _write_exclusive(a.out, text)
        except OSError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"wrote {a.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
