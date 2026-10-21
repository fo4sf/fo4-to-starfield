"""The cell coc.ps1 hops through when its first coc missed the target's COC marker (v6e stairs retest 2026-10-21: the
save stood inside the target already, at its load door's arrival, and the coc left the player there).

usage: coc_hop.py <staging>\\<Cell>.json
Prints the EditorID of the first other cell export next to it (sorted by file name) that has its own
COCMarkerHeading, with the planner's filter (testqueue.py plan): helper documents and merged.json are never cells.
Prints nothing and exits 1 when there is none."""
import glob
import json
import os
import sys

SKIP = {"editorids.json", "formids.json", "lighting.json", "merged.json", "manifest.json"}


def hop_cell(cell_json):
    """EditorID of the hop cell for the export at cell_json, or None."""
    staging = os.path.dirname(os.path.abspath(cell_json))
    try:
        with open(cell_json, encoding="utf-8") as f:
            target = json.load(f).get("cell")
    except (OSError, ValueError, AttributeError):
        target = None
    target = target or os.path.splitext(os.path.basename(cell_json))[0]
    for p in sorted(glob.glob(os.path.join(staging, "*.json"))):
        b = os.path.basename(p)
        if b in SKIP or b.startswith("routes_") or b.startswith("build"):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                c = json.load(f)
        except (OSError, ValueError):
            continue
        if not (isinstance(c, dict) and isinstance(c.get("refs"), list) and c.get("cell")):
            continue
        if c["cell"] in ("merged", target):
            continue
        if any(isinstance(r, dict) and r.get("base_editor_id") == "COCMarkerHeading" for r in c["refs"]):
            return c["cell"]
    return None


def main(argv):
    if len(argv) != 1:
        sys.exit(__doc__)
    cell = hop_cell(argv[0])
    if not cell:
        return 1
    print(cell)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
