"""What this checkout's queue runner can do (testqueue.py run + qstep.ps1), so a queue planned for features an older
runner lacks is refused instead of run without them.

usage: python scripts/game/runner_features.py check <feature,feature>    exit 0 when this checkout has them all, else 5

Why: the unattended chain runs `testqueue.py run` from the integration worktree. An older runner there ignores test
fields it does not know (time_of_day, console_pre, ...) and would run such a queue at night, without the console lines
and without a word (verifier of PR #73, 2026-10-12). So plan-terrain / plan-npc write the features a queue needs into
queue.json "needs", the runner refuses a queue whose needs it lacks, and the queue's pre_launch command runs the
RUNNER's own copy of exp_install.py (a path relative to the runner's checkout) with --needs: a runner from before this
file has an exp_install.py that refuses the unknown option, so even it stops before launching the game.
"""
import sys

# light:   time_of_day / weather (sky_light.py): the time ladder with OCR'd replies and second shots, the probe shots'
#          light, the time command typed again before every terrain probe
# console: console_pre / console_post (console_plan.py)
# npc_t0:  npc_nav precommand_m / arrive_progress (N0b): the walk judged from t0 only, baselines by their largest
#          approach, and the control gate pairing a control with the baselines of its own queue. An older runner would
#          judge such a queue by min_progress alone (a 12 m pre-command guard, an arrival credited with the wander
#          before the command: verifier of PR #77, 2026-10-12)
# door_trip:    the door_trip kind (plan-door; docs/slice/redrocket-door.md): through a load door and back, save, load.
#               An older qstep.ps1 ends such a step with "unknown kind" (exit 4) after the game was launched for it
# plugin_order: cycle.ps1 runs exp_install.py order after deploying FO4Port.esm, so an experiment plugin that masters
#               FO4Port.esm loads after it; an older runner would launch with that plugin before its master
# door_check:   door_trip with moved_m / activate_m (QA on PR #78, 2026-10-12): a position read after every walk step
#               and before E or the last-try teleport, the player moved away before the reload, NOLOAD only from a stand
#               within the door's range. The first door_trip runner could teleport after a load its HUD checks missed
#               and call a stand 5 m from the door "the door does not work"
# door_frames:  door_trip with reads "strict" (docs/slice/door-frames.md; the first live runs, 2026-10-13): labelled
#               position reads of the read's own session only (readpos -Strict), a load never taken from one read
#               (two far reads that agree; axes that look swapped rejected), GetInCell never judged (the console
#               refused the cell's EditorID), which side of the door from the position frames, the facing on arrival
#               (getangle z) and after the load, merge probes. An older runner took "99.74 -2195.27 99.41" for a load
# door_route:   door_trip legs that walk a planned route from where the player stands (outside.route / inside.route):
#               no teleport to a start; an older qstep.ps1 would teleport to outside.start instead
# walk:         the walk kind (plan-walk; docs/terrain/walk-redrocket-sanctuary.md): a continuous walk with real input
#               over planned waypoints, steered by walk_eval.py, W held by input.ps1's guarded holdg. An older qstep.ps1
#               ends such a step with "unknown kind" (exit 4) after the game was launched for it
FEATURES = ("light", "console", "npc_t0", "door_trip", "plugin_order", "door_check", "door_frames", "door_route", "walk")


def needs(tests):
    """The features the planned tests use, sorted."""
    out = set()
    for t in tests:
        if t.get("time_of_day") is not None or t.get("weather"):
            out.add("light")
        if t.get("console_pre") or t.get("console_post"):
            out.add("console")
        if "precommand_m" in t or "arrive_progress" in t:
            out.add("npc_t0")
        if t.get("kind") == "door_trip":
            out.add("door_trip")
            if "moved_m" in t or "activate_m" in t:
                out.add("door_check")
            if t.get("reads") == "strict":
                out.add("door_frames")
            if (t.get("outside") or {}).get("route") or (t.get("inside") or {}).get("route"):
                out.add("door_route")
        if t.get("kind") == "walk":
            out.add("walk")
    return sorted(out)


def missing(need):
    return [f for f in need or [] if f not in FEATURES]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] != "check":
        print(__doc__.strip().splitlines()[2])
        return 2
    miss = missing([x.strip() for x in argv[1].split(",") if x.strip()])
    if miss:
        print(f"this runner lacks {', '.join(miss)} (it has {', '.join(FEATURES)}): update its checkout first")
        return 5
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
