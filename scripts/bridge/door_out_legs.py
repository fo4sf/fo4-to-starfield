"""Keep only the OUT legs of a staged door_rounds plan whose doors stand at least MIN_M from the Red Rocket arrival.

    python scripts/bridge/door_out_legs.py <staged rounds folder> <NEW folder> <min metres>

Each OUT leg starts with a coc into its interior, so none of them goes near Red Rocket (the v6 build crashed there on
2026-10-19). Every kept entry is rebuilt with door_rounds.plan_door from the door record stage saved in rounds.json
and must equal the staged plan entry and its expectation exactly (coc, travel, activation, ack, resolve; a
--border-off stage's console lines too, door_rounds.border_off), so a mismatched or edited stage is refused before
anything is written. The distance is computed from the same numbers
plan_door uses (the Red Rocket arrival's spawn_local and the door's exterior arrival_local), never from a label.
The new folder holds plan.json and rounds.json renumbered, so plan-terrain and door_rounds.py judge work on it.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import door_rounds as dr  # noqa: E402


def finite_xy(v, what):
    if not isinstance(v, (list, tuple)) or len(v) < 2 or not all(
            isinstance(c, (int, float)) and not isinstance(c, bool) and math.isfinite(c) for c in v[:2]):
        sys.exit(f"{what}: not a finite position: {v!r}")
    return [float(v[0]), float(v[1])]


def select(plan, rounds, min_m):
    """The (OUT plan entry, OUT expectation, distance) of every door at least min_m away; exits on any mismatch."""
    ci, pi = int(rounds["core_index"], 16), int(rounds["port_index"], 16)
    doors, tests = rounds["doors"], rounds["tests"]
    if len(plan) != 2 * len(doors) or len(tests) != 2 * len(doors):
        sys.exit(f"{len(plan)} plan entries and {len(tests)} expectations for {len(doors)} doors: not a door_rounds stage")
    spawn = None
    for k in range(len(doors)):
        fwd = plan[2 * k]
        if fwd.get("coc") != dr.SPAWN_COC:
            sys.exit(f"test {2 * k}: the IN leg does not start at {dr.SPAWN_COC}")
        s = finite_xy(fwd.get("spawn_local"), f"test {2 * k} spawn_local")
        if spawn is not None and s != spawn:
            sys.exit(f"test {2 * k}: spawn_local {s} differs from the other doors' {spawn}")
        spawn = s
    kept = []
    for k, r in enumerate(doors):
        _, ret, _, eret = dr.plan_door(k, r, spawn + [0.0], {}, 0.0, ci, pi)   # the OUT leg needs no spawn or zref
        if rounds.get("border_off"):                      # a --border-off stage: its console lines are part of the leg
            ret = dr.border_off(ret)
        want = dict(eret, test=2 * k + 1)
        if plan[2 * k + 1] != ret or tests[2 * k + 1] != want:
            sys.exit(f"test {2 * k + 1}: the staged OUT leg of door {k} ({r.get('cell_edid')}) does not match its "
                     f"door record (coc, travel, activation, ack or resolve changed)")
        if tests[2 * k].get("leg") != "in" or tests[2 * k].get("door") != k:
            sys.exit(f"test {2 * k}: not door {k}'s IN expectation")
        d = math.dist(spawn, finite_xy(r["exterior"]["arrival_local"], f"door {k} exterior arrival_local"))
        if d >= min_m:
            kept.append((ret, want, d))
    return kept


def main(argv=None):
    src, dst, min_m = (argv or sys.argv[1:])[:3]
    min_m = float(min_m)
    if not math.isfinite(min_m) or min_m < 0:
        sys.exit(f"min metres {min_m}: want a finite number, 0 or more")
    with open(os.path.join(src, "plan.json"), encoding="utf-8") as f:
        plan = json.load(f)
    with open(os.path.join(src, "rounds.json"), encoding="utf-8") as f:
        rounds = json.load(f)
    kept = select(plan, rounds, min_m)                    # every check before anything is written
    os.makedirs(dst)                                      # a NEW folder only
    dr.save_stage(dst, [p for p, _, _ in kept],
                  dict(rounds, legs="out", out_min_m=min_m, tests=[dict(e, test=i) for i, (_, e, _) in enumerate(kept)]))
    for i, (_, e, d) in enumerate(kept):
        print(i, e["cell_edid"], f"{d:.1f}", "m")
    print(len(kept), "OUT tests kept of", len(rounds["doors"]))


if __name__ == "__main__":
    main()
