"""Offline placement-frame oracle for plugins that add refs to a core worldspace.

Reports every REFR/ACHR placed into the shared worldspace: position, exterior cell
computed from that position, whether the core plugin has LAND in that cell, and
optional distance to a named anchor. Flags any ref that lands outside core cells
or whose computed cell disagrees with its parent CELL's XCLC.

Exits 1 when any flag is raised.

Usage:
  python scripts/oracles/placement_frame.py --plugin mission.esp --core core.esp \\
      --world-edid TestWorld [--anchor Good]
"""
import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fo4sf.fo4land import Plugin, cell_of  # noqa: E402


def collect_refs(plugin_path, world_edid):
    """Return list of ref dicts with parent_xy attached, and set of cells that have LAND."""
    with Plugin(plugin_path) as p:
        data = p.read_world(world_edid, cells=None, refs=True)
        cells_with_land = set()
        sources = list(data["cells"].values())
        if data.get("persistent_cell"):
            sources.append(data["persistent_cell"])
        for cell in sources:
            if not cell:
                continue
            xy = (cell["x"], cell["y"]) if cell.get("x") is not None else None
            if xy and (cell.get("vhgt") is not None or cell.get("land_fid")):
                cells_with_land.add(xy)
        refs = []
        for cell in sources:
            if not cell:
                continue
            parent = (cell["x"], cell["y"]) if cell.get("x") is not None else None
            for bucket in ("refs", "persistent_refs"):
                for r in cell.get(bucket, []):
                    rr = dict(r)
                    rr["parent_xy"] = parent
                    rr["parent_fid"] = cell["fid"]
                    # EDID is not extracted by parse_ref; leave None unless we extend later
                    refs.append(rr)
        return cells_with_land, refs, data["world_fid"]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plugin", required=True)
    ap.add_argument("--core", required=True)
    ap.add_argument("--world-edid", required=True, help="EDID of the shared worldspace")
    ap.add_argument("--anchor", help="EDID of an anchor ref (distance reported if found)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        core_cells, _, core_fid = collect_refs(args.core, args.world_edid)
        _, plugin_refs, _ = collect_refs(args.plugin, args.world_edid)
    except Exception as exc:
        print(f"failed to read plugins: {exc}", file=sys.stderr)
        return 2

    anchor_pos = None
    if args.anchor:
        # Without EDID on refs we match by a comment or skip; for now note limitation
        print(f"note: anchor matching by EDID requires parse_ref extension; skipping distance", file=sys.stderr)

    flags = []
    report = []
    for r in plugin_refs:
        pos = r.get("pos")
        if not pos or len(pos) < 2:
            continue
        computed = cell_of(pos[0], pos[1])
        parent = r.get("parent_xy")
        has_land = computed in core_cells
        disagree = parent is not None and tuple(parent) != computed
        flag = (not has_land) or disagree
        entry = {
            "fid": f"{r.get('fid', 0):08X}",
            "type": r.get("type"),
            "pos": [round(float(v), 2) for v in pos],
            "computed_cell": list(computed),
            "parent_cell": list(parent) if parent else None,
            "core_has_land": has_land,
            "flag": flag,
        }
        if anchor_pos:
            dx = pos[0] - anchor_pos[0]
            dy = pos[1] - anchor_pos[1]
            entry["dist_to_anchor"] = round(math.hypot(dx, dy), 1)
        report.append(entry)
        if flag:
            flags.append(entry)

    out = {"world_fid": f"{core_fid:08X}", "core_land_cells": len(core_cells),
           "refs": report, "flagged": len(flags)}
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"world {out['world_fid']}  core LAND cells: {out['core_land_cells']}")
        print(f"refs: {len(report)}  flagged: {len(flags)}")
        for e in report:
            mark = "FLAG" if e["flag"] else "ok  "
            print(f"  {mark} {e['fid']} {e['type']} pos={e['pos']} "
                  f"cell={e['computed_cell']} parent={e['parent_cell']} land={e['core_has_land']}")
    return 1 if flags else 0


if __name__ == "__main__":
    sys.exit(main())
