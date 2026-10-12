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
FEATURES = ("light", "console", "npc_t0")


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
