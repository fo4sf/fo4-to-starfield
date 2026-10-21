"""Ground under the door-exit arrivals a door rounds judge failed (docs/spikes/door-exit-heights.md).

    python scripts/terrain/arrival_ground.py <core staging dir> <door_rounds_judge.json> [--all] [--json <out.json>]

For each WRONG_PLACE row (every judged row with --all), the expected marker and the place the player was read, both
taken back into the core's local frame (world minus the build's merge offset, vmad_patch.merge_offset), with the core
BTD's bilinear ground height under each (make_core64c.Terrain). Reading the pair:
  got z close to the ground under got: the player stood on terrain there.
  marker z well above the ground under it: the marker floats, or sits on something that is not terrain.
  marker z well below the ground under it: the marker is underground and the player was lifted.
Terrain only: objects (buildings, rocks) are not read, so standing on one shows as "got above ground". Read-only.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_core64c  # noqa: E402
import vmad_patch  # noqa: E402

NEAR_M = 0.5        # "on the ground": within this of the BTD height (the BTD step is 0.78 m; heights are bilinear)


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def core_terrain(core):
    """The core build's Terrain, from the one overlay in overlays_params.json that names a btd_file."""
    prm = load(os.path.join(core, "overlays_params.json"))
    ovs = [o for o in prm.get("overlays") or [] if o.get("btd_file")]
    if len(ovs) != 1:
        raise ValueError(f"{core}: overlays_params.json has {len(ovs)} overlay(s) with a btd_file, want 1")
    return make_core64c.Terrain(os.path.join(core, *ovs[0]["btd_file"].split("/")))


def rows(judge, everything=False):
    """The judged rows to read: WRONG_PLACE fails (all rows with an expected and a read position with everything)."""
    out = []
    for r in judge if isinstance(judge, list) else judge.get("results") or judge.get("tests") or []:
        if not isinstance(r, dict) or not isinstance(r.get("pos"), list) or not isinstance((r.get("got") or {}).get("pos"), list):
            continue
        if everything or str(r.get("why", "")).startswith("WRONG_PLACE"):
            out.append(r)
    return out


def classify(z, ground):
    d = z - ground
    return "on ground" if abs(d) <= NEAR_M else (f"{d:.1f} m above ground" if d > 0 else f"{-d:.1f} m below ground")


def read(terrain, offset, judged):
    out = []
    for r in judged:
        mark = [r["pos"][i] - offset[i] for i in range(3)]
        got = [float(r["got"]["pos"][i]) - offset[i] for i in range(3)]
        gm, gg = (float(v) for v in terrain.bilinear([mark[0], got[0]], [mark[1], got[1]]))
        out.append({"id": r.get("id"), "src": r.get("src"), "cell_edid": r.get("cell_edid"), "why": r.get("why"),
                    "marker_local": [round(v, 3) for v in mark], "ground_at_marker": round(gm, 3),
                    "marker": classify(mark[2], gm),
                    "got_local": [round(v, 3) for v in got], "ground_at_got": round(gg, 3), "got": classify(got[2], gg)})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("core")
    ap.add_argument("judge")
    ap.add_argument("--all", action="store_true", help="every judged row with positions, not only WRONG_PLACE")
    ap.add_argument("--json", default="")
    a = ap.parse_args(argv)
    try:
        offset = vmad_patch.merge_offset(a.core)
        found = read(core_terrain(a.core), offset, rows(load(a.judge), a.all))
    except (OSError, ValueError, KeyError) as e:
        sys.exit(str(e))
    for f in found:
        print(f"{f['id']}  {f['cell_edid']}  ({f['why']})")
        print(f"  marker {f['marker_local']}  ground {f['ground_at_marker']}  -> {f['marker']}")
        print(f"  got    {f['got_local']}  ground {f['ground_at_got']}  -> {f['got']}")
    if a.json:
        with open(a.json, "x", encoding="utf-8") as f:
            json.dump({"merge_offset": list(offset), "rows": found}, f, indent=1)
    print(f"{len(found)} row(s); merge offset {offset}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
