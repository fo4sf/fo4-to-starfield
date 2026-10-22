"""The cell coc.ps1 hops through when its first coc missed the target's COC marker (v6e stairs retest 2026-10-21: the
save stood inside the target already, at its load door's arrival, and the coc left the player there).

usage: coc_hop.py <staging>\\<Cell>.json
Prints the EditorID of the first other cell export next to it (sorted by file name) that has its own
COCMarkerHeading at least MIN_APART_M from the target's (in the cells' own coordinates), with the planner's filter
(testqueue.py plan): helper documents and merged.json are never cells. coc.ps1 checks the arrival by position only, so
a return coc the game ignored must leave the player far from the target's marker (Codex on #450). Prints nothing and
exits 1 when there is none."""
import glob
import json
import math
import os
import sys

UNIT = 70.0                                                # game units per metre (coc.ps1's pos / 70)
MIN_APART_M = 20.0                                         # 4x coc.ps1's 5 m arrival radius
SKIP = {"editorids.json", "formids.json", "lighting.json", "merged.json", "manifest.json"}


def marker_xy(doc):
    """The first COCMarkerHeading's x, y in metres, or None."""
    for r in doc.get("refs") or []:
        if isinstance(r, dict) and r.get("base_editor_id") == "COCMarkerHeading":
            pos = r.get("pos")
            if isinstance(pos, list) and len(pos) >= 2 and all(isinstance(v, (int, float)) for v in pos[:2]):
                return pos[0] / UNIT, pos[1] / UNIT
    return None


def hop_cell(cell_json):
    """EditorID of the hop cell for the export at cell_json, or None (also when the target has no readable marker)."""
    staging = os.path.dirname(os.path.abspath(cell_json))
    try:
        with open(cell_json, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    target, at = doc.get("cell") or os.path.splitext(os.path.basename(cell_json))[0], marker_xy(doc)
    if at is None:
        return None
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
        xy = marker_xy(c)
        if xy is not None and math.dist(xy, at) >= MIN_APART_M:
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
