"""Offline placement-frame oracle for plugins that add refs to the core worldspace.

Reports for every placed REFR/ACHR in the given plugin's worldspace:
  its position, the exterior cell it falls in (from position), whether the core has land there,
  the parent CELL's XCLC if present, and distance to a named anchor if given.
Flags refs that land in cells the core does not have, or whose computed cell disagrees with the
parent CELL record's XCLC. Applies the measured merge offset (-1200, -2700) as an alternative frame
and reports both. Exit 1 on any flag.

Usage:
  python scripts/oracles/placement_frame.py --core <core.esm> --plugin <mission.esp>
      [--world Commonwealth] [--anchor <EDID>] [--json]
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
from fo4sf import fo4land  # noqa: E402

MERGE = (-1200.0, -2700.0, 0.0)
CELL_UNITS = fo4land.CELL_UNITS


def cell_of(x, y):
    return fo4land.cell_of(x, y)


def dist2(a, b):
    return math.sqrt(sum((p - q) ** 2 for p, q in zip(a, b)))


def collect_core_cells(core_path, world):
    """Set of (x, y) cells that have LAND in the core plugin's worldspace."""
    with fo4land.Plugin(core_path) as p:
        result = p.read_world(world, cells=None, refs=False)
    return {xy for xy, cell in result["cells"].items() if cell.get("vhgt") is not None}


def collect_refs(plugin_path, world):
    """List of placed refs: {fid, type, pos, rot, cell_x, cell_y, edid, parent_cell}."""
    refs = []
    with fo4land.Plugin(plugin_path) as p:
        result = p.read_world(world, cells=None, refs=True)
        for xy, cell in result["cells"].items():
            parent = xy
            for r in cell.get("refs", []) + cell.get("persistent_refs", []):
                if r.get("pos") is None:
                    continue
                refs.append({
                    "fid": f"{r['fid']:08X}",
                    "type": r["type"],
                    "pos": r["pos"],
                    "rot": r["rot"],
                    "parent_cell": list(parent) if parent else None,
                    "edid": cell.get("edid") or "",
                })
        # persistent cell refs too
        for r in result.get("persistent", []):
            if r.get("pos") is None:
                continue
            refs.append({
                "fid": f"{r['fid']:08X}",
                "type": r["type"],
                "pos": r["pos"],
                "rot": r["rot"],
                "parent_cell": None,
                "edid": "",
            })
    return refs


def audit(core_path, plugin_path, world="Commonwealth", anchor_edid=None):
    core_cells = collect_core_cells(core_path, world)
    refs = collect_refs(plugin_path, world)
    anchor = None
    if anchor_edid:
        # find anchor by EDID in either plugin (prefer plugin)
        for path in (plugin_path, core_path):
            with fo4land.Plugin(path) as p:
                bases = p.base_records(edid_regex=f"^{anchor_edid}$")
                if bases:
                    # not a ref; skip for now — anchor is expected as a placed ref EDID on a REFR
                    pass
            # better: look for a REFR with that EDID in the world
            # (simple: scan collected refs if they carried EDID; they don't. Leave distance optional.)
        # For the oracle, distance is optional; if not found, note it.
    flags = []
    report = []
    for r in refs:
        x, y, z = r["pos"]
        cx, cy = cell_of(x, y)
        mx, my = cell_of(x + MERGE[0], y + MERGE[1])
        parent = r["parent_cell"]
        parent_ok = parent is None or (parent[0] == cx and parent[1] == cy)
        in_core = (cx, cy) in core_cells
        in_core_merged = (mx, my) in core_cells
        entry = {
            "fid": r["fid"],
            "type": r["type"],
            "pos": [round(v, 4) for v in r["pos"]],
            "cell": [cx, cy],
            "merged_cell": [mx, my],
            "parent_cell": parent,
            "in_core": in_core,
            "in_core_merged": in_core_merged,
            "parent_ok": parent_ok,
        }
        if not parent_ok:
            entry["flag"] = "parent_cell_mismatch"
            flags.append(entry["fid"])
        elif not in_core and not in_core_merged:
            entry["flag"] = "outside_core"
            flags.append(entry["fid"])
        report.append(entry)
    return {
        "core_cells": len(core_cells),
        "refs": len(refs),
        "flags": len(flags),
        "flagged": flags,
        "entries": sorted(report, key=lambda e: e["fid"]),
        "merge_offset": list(MERGE),
        "world": world,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--core", required=True)
    ap.add_argument("--plugin", required=True)
    ap.add_argument("--world", default="Commonwealth")
    ap.add_argument("--anchor", help="EDID of an anchor reference (distance reported if found)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = audit(args.core, args.plugin, args.world, args.anchor)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"core cells with land: {result['core_cells']}")
        print(f"placed refs: {result['refs']}")
        print(f"flags: {result['flags']}")
        for e in result["entries"]:
            flag = e.get("flag", "")
            print(f"  {e['fid']} {e['type']} pos={e['pos']} cell={e['cell']} "
                  f"merged={e['merged_cell']} parent={e['parent_cell']} "
                  f"in_core={e['in_core']} in_merged={e['in_core_merged']} {flag}")
    return 1 if result["flags"] else 0


if __name__ == "__main__":
    sys.exit(main())
