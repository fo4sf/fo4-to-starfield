"""Ground under the door-exit arrivals a door rounds judge failed (docs/spikes/door-exit-heights.md).

    python scripts/terrain/arrival_ground.py <core staging dir> <door_rounds_judge.json> [--all] [--json <out.json>]

For each exterior ("out" leg) WRONG_PLACE row (every judged "out" row with --all), the expected marker and the place
the player was read, both taken back into the core's local frame (world minus the build's merge offset,
vmad_patch.merge_offset), with the core BTD's ground height under each (make_core64c.Terrain). The engine's rule inside
a BTD quad is unknown, so the height is given under all three of tg.point_interp's rules; a point is only called on,
above or below the ground when all three agree, and "unresolved" otherwise. "in" rows are skipped: their positions are
interior-cell coordinates, not the core's. Reading the pair:
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
from fo4sf import terrain_grid as tg  # noqa: E402  (make_core64c puts src on the path)

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
    """The judged exterior rows to read: "out" WRONG_PLACE fails (every "out" row with both positions with everything)."""
    out = []
    for r in judge if isinstance(judge, list) else judge.get("results") or judge.get("tests") or []:
        if not isinstance(r, dict) or r.get("leg") != "out" or not isinstance(r.get("pos"), list) \
                or not isinstance((r.get("got") or {}).get("pos"), list):
            continue
        if everything or str(r.get("why", "")).startswith("WRONG_PLACE"):
            out.append(r)
    return out


def ground(terrain, x, y):
    """The BTD height at (x, y) under each of tg.point_interp's rules, or None outside the BTD (heights there are clamped
    edge values, not ground)."""
    last = terrain.origin + (terrain.raw.shape[0] - 1) * tg.SF_STEP_M
    if not (terrain.origin <= x <= last and terrain.origin <= y <= last):
        return None
    win, ox, oy = terrain.window(x, y, x, y)
    return {k: round(v, 3) for k, v in tg.point_interp(win, ox, oy, tg.SF_STEP_M, x, y).items()}


def classify(z, heights):
    if heights is None:
        return "outside the BTD"
    d = [z - h for h in heights.values()]
    lo, hi = min(d), max(d)
    if all(abs(v) <= NEAR_M for v in d):
        return "on ground"
    if lo > NEAR_M:
        return f"{lo:.1f} m above ground" if hi - lo < 0.05 else f"{lo:.1f} to {hi:.1f} m above ground"
    if hi < -NEAR_M:
        return f"{-hi:.1f} m below ground" if hi - lo < 0.05 else f"{-hi:.1f} to {-lo:.1f} m below ground"
    return f"unresolved: {lo:+.1f} to {hi:+.1f} m from the ground under the three rules"


def read(terrain, offset, judged):
    out = []
    for r in judged:
        mark = [r["pos"][i] - offset[i] for i in range(3)]
        got = [float(r["got"]["pos"][i]) - offset[i] for i in range(3)]
        gm, gg = ground(terrain, mark[0], mark[1]), ground(terrain, got[0], got[1])
        out.append({"id": r.get("id"), "src": r.get("src"), "cell_edid": r.get("cell_edid"), "why": r.get("why"),
                    "marker_local": [round(v, 3) for v in mark], "ground_at_marker": gm,
                    "marker": classify(mark[2], gm),
                    "got_local": [round(v, 3) for v in got], "ground_at_got": gg, "got": classify(got[2], gg)})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("core")
    ap.add_argument("judge")
    ap.add_argument("--all", action="store_true", help="every judged out row with positions, not only WRONG_PLACE")
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
