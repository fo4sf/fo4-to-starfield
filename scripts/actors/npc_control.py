"""NPC navigation control N0b (docs/actors/npc-navigation.md, "N0 result and the N0b design"): the npc_nav plan.json
of the vanilla control from navmesh_points.py's analysis of QASmoke, and N1 / N2 plans derived from earlier ones so
they are judged by the same rule and gated by N0b.

usage:
  python scripts/actors/npc_control.py n0b --points <qasmoke_points.json> --out <staging dir>
  python scripts/actors/npc_control.py derive --plan <old plan.json> --out <staging dir> [--points <points.json>]
         [--methods ptr_player,combat_player] [--map-queue <old queue dir>=<new queue dir>]...
  python scripts/actors/npc_control.py check --plan <plan.json>

The rule (RULE, the same keys testqueue.py already reads, so the integration-1012 runner plans and judges it as is):
  PASS = the actor came within radius 3 m of the player (who stands at B; not already at the first read), or ended
  min_progress 12 m closer to the player than at t0. A baseline (no command) is judged the other way round with the
  same numbers: FAIL WANDER when it comes 12 m closer or within 3 m on its own.
  Why 12 m: in N0 (2026-10-12) actors that no command moved came 5.4 m (N0_base), 6.8 / 7.0 m (N0_ptr, N0_cf, whose
  command failed) and 9.0 m (N0_ptr_lvl) closer to B, and the old pair let an actor gain 8.5 m by going where they went
  (navmesh_points.py drift progress). 12 m is 3 m above the largest of them and twice the N0b pair's drift bound (6 m).
  The reads add one at 1 s, so an actor that runs to the player is seen on the way (else INCONCLUSIVE EARLY).

`derive` keeps every test of an old plan whose method is "none" or in --methods (the methods N0b controls), drops the
others (their FAIL could never count: no N0b control), sets RULE, moves QASmoke tests to the N0b pair (--points),
renames requires queues (--map-queue), and for the first actor and point pair with a commanded test adds a twin for each
missing method and a baseline when there is none (an N1 world gets its own wander reference). Labels stay, so the
same-queue requires keep working. Every written test is checked with testqueue.npc_test (the runner's plan validation).
"""
import argparse
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "scripts", "game"))
import testqueue  # noqa: E402

CITIZEN = "002B211C"      # EncCitizen01Template: N0's actor. AIDT 00 00 32 03 00 01 00: Unaggressive, Cowardly
SPACER = "00270255"       # EncSpacer01Template: N2b's reference. AIDT 00 03 32 03 00 01 01: Unaggressive, Brave;
#                           SpacerFaction (Enemy to PlayerFaction) and 6 reaction-radius RDSA entries
RULE = {"radius": 3.0, "min_progress": 12.0, "reads_s": [0, 1, 3, 8, 15, 30]}
METHODS = ("ptr_player", "combat_player")         # the commands N0b controls (the others failed in N0)
QASMOKE = {"travel": "coc QASmoke", "drop": 0.5, "settle_ms": 1500}       # N0's travel, drop and settle
HOSTILE = {"handle_tol": 3.0}                     # N2b's: a hostile actor may step away while the handle is read
N0_EVIDENCE = ("N0 (npc_nav_n0, 2026-10-12): every actor stayed in x -11..0, y -6..2, never closer than 10.8 m to "
               "B (5, 10); N0_base came 5.4 m closer without a command")
PY = r"C:\Modding\venv-render\Scripts\python.exe"     # the chain's Python (docs/ai/test-queue.md, codex-runbook.md)


def _pair(points):
    with open(points, encoding="utf-8") as f:
        res = json.load(f)
    ch = res.get("chosen")
    if not ch:
        sys.exit(f"{points}: no chosen pair (navmesh_points.py analyze found none)")
    return res, [round(x, 3) + 0.0 for x in ch["a"]], [round(x, 3) + 0.0 for x in ch["b"]], ch


def n0b_tests(a, b, ch):
    """The N0b plan: the calm citizen and the hostile Spacer, each with a baseline, StartCombat and PathToRef."""
    where = (f"A {a[:2]} -> B {b[:2]}, {ch['distance']} m, one navmesh, straight path clear by "
             f"{ch['segment_clearance']} m, drift progress {ch['drift_progress']} m (verified offline, "
             f"navmesh_points.py)")

    def t(label, npc, method, control, expect, basis, **kw):
        return {"label": label, "npc": npc, "method": method, **QASMOKE, "a": a, "b": b, **RULE,
                "control": control, "expect": expect, "basis": basis, **kw}
    return [
        t("N0b_base", CITIZEN, "none", False, "PASS",
          f"supported hypothesis: {N0_EVIDENCE}; here B is {ch['b_from_trace']} m from every N0 read and "
          f"{ch['b_from_arrival']} m from the arrival marker, so the citizen does not come 12 m closer or within 3 m "
          f"on its own ({where})"),
        t("N0b_ptr", CITIZEN, "ptr_player", True, "FAIL STALLED",
          "supported hypothesis: N0_ptr (6.8 m) and N0_ptr_lvl (9.0 m) stayed inside N0_base's wander and ended "
          "where it went (N0_ptr 0.3 m from the arrival marker): PathToRef typed on the console did not walk the "
          f"citizen to the player. A PASS here (12 m or within 3 m) would show it does ({where})"),
        t("N0b_combat", CITIZEN, "combat_player", True, "FAIL STALLED",
          "supported hypothesis: EncCitizen01Template is Cowardly (AIDT confidence 0, verified in Starfield.esm), and "
          "a cowardly actor in combat flees (Bethesda AI semantics, not measured in Starfield): it moves, away from "
          "the player. PASS = StartCombat brings even a cowardly citizen to the player"),
        t("N0b_spacer_base", SPACER, "none", False, "FAIL WANDER",
          "supported hypothesis: SpacerFaction is Enemy to PlayerFaction and the Spacer has 6 reaction radii "
          "(verified); spawned at the player's feet it starts combat and comes for the player without a command "
          "(N2b_spacer_base asks the same on the old pair). PASS = it stays away: Unaggressive (verified) wins",
          **HOSTILE),
        t("N0b_spacer_combat", SPACER, "combat_player", True, "PASS",
          "supported hypothesis: StartCombat on a Brave (AIDT confidence 3, verified) Spacer brings it at least 12 m "
          "closer; it may stop at weapon range. Credited to the command only when N0b_spacer_base stayed away",
          **HOSTILE),
        t("N0b_spacer_ptr", SPACER, "ptr_player", True, "PASS",
          "supported hypothesis: the hostile Spacer comes for the player whatever is typed; credited to PathToRef "
          "only when N0b_spacer_base stayed away (unresolved)", **HOSTILE),
    ]


def first_group(tests):
    """(npc, travel, a, b) of the first commanded test, or None."""
    for w in tests:
        if w.get("method", "ptr_player") != "none":
            return (str(w["npc"]).upper(), w["travel"], tuple(w["a"]), tuple(w["b"]))
    return None


def _key(w):
    return (str(w["npc"]).upper(), w["travel"], tuple(w["a"]), tuple(w["b"]))


def _twin_label(label, method, taken):
    stem = method.split("_")[0]                       # ptr / combat / cf / follow
    for old in ("ptr_player", "ptr"):
        if old in label:
            new = label.replace(old, method if old == "ptr_player" else stem, 1)
            break
    else:
        new = f"{label}_{stem}"
    while new in taken:
        new += "_b"
    return new


def derive(tests, methods=METHODS, pair=None, map_queue=None, control_queue_name="npc_nav_n0b"):
    """(new tests, notes). tests: an old plan.json list."""
    map_queue = {os.path.normcase(os.path.abspath(k)): v for k, v in (map_queue or {}).items()}
    keep, notes, moved, mapped = [], [], [], []
    for w in tests:
        m = w.get("method", "ptr_player")
        if m != "none" and m not in methods:
            notes.append(f"dropped {w.get('label')} ({m}: no N0b control for it, its FAIL could never count)")
            continue
        w = copy.deepcopy(w)
        w.update(copy.deepcopy(RULE))
        if pair and w.get("travel") == QASMOKE["travel"]:
            w["a"], w["b"] = list(pair[0]), list(pair[1])
            moved.append(w.get("label"))
        r = w.get("requires")
        if r and r.get("queue"):
            new = map_queue.get(os.path.normcase(os.path.abspath(r["queue"])))
            if new:
                w["requires"] = dict(r, queue=new)
                mapped.append(f"{w.get('label')} -> {new}")
        w["basis"] = (w.get("basis", "") + f" [re-planned with the N0b rule: within {RULE['radius']:g} m of the player"
                      f" or {RULE['min_progress']:g} m closer; FAILs gated by {control_queue_name}]").strip()
        keep.append(w)
    if moved:
        notes.append(f"moved to the N0b pair A {list(pair[0])} -> B {list(pair[1])}: {', '.join(moved)}")
    if mapped:
        notes.append(f"requires now names the new queue: {'; '.join(mapped)}")
    grp = first_group(keep)
    if grp:
        members = [w for w in keep if _key(w) == grp]
        cmd = [w for w in members if w.get("method", "ptr_player") != "none"]
        taken = {w.get("label") for w in keep}
        src = cmd[0]
        at = keep.index(src) + 1
        for m in methods:
            if any(w.get("method") == m for w in cmd):
                continue
            tw = copy.deepcopy(src)
            tw["method"] = m
            tw["label"] = _twin_label(src["label"], m, taken)
            taken.add(tw["label"])
            tw["expect"] = f"unresolved (as N0b's {m} control for {src.get('control_npc') or src['npc']})"
            tw["basis"] = (f"{m} twin of {src['label']} (derived): the same actor, world and points; counts only where "
                           f"N0b's {m} control and baseline passed ({control_queue_name})")
            keep.insert(at, tw)
            at += 1
            notes.append(f"added {tw['label']} ({m} twin of {src['label']})")
        if not any(w.get("method") == "none" for w in members):
            base = copy.deepcopy(src)
            base["method"] = "none"
            base["control"] = False
            base.pop("control_npc", None)
            base["label"] = _twin_label(src["label"], "base", taken).replace("_base_player", "_base")
            if base["label"] in taken or "base" not in base["label"]:
                base["label"] = src["label"].split("_")[0] + "_base"
            base["expect"] = "PASS"
            base["basis"] = ("derived baseline (no command): the actor's own movement in this world, the reference "
                             "that credits or voids this queue's commanded PASSes")
            keep.insert(0, base)
            notes.append(f"added {base['label']} (baseline of {src['npc']} in this world)")
    labels = [w.get("label") for w in keep]
    if len(set(labels)) != len(labels):
        sys.exit(f"duplicate labels after deriving: {labels}")
    return keep, notes


def check(tests):
    """Every test through the runner's own validation (testqueue.npc_test exits on an unknown key or a bad value)."""
    return [testqueue.npc_test(n, w) for n, w in enumerate(tests)]


def _load(p):
    with open(p, encoding="utf-8-sig") as f:
        src = json.load(f)
    return src.get("tests") if isinstance(src, dict) else src


def _write(out, tests, readme):
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(tests, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(readme)


def n0b_readme(res, a, b, ch, out):
    old = res.get("old_pair") or {}
    return f"""NPC navigation N0b: the vanilla control that tells a commanded walk from wandering (Claude, branch
claude/npc-control-n0b; docs/actors/npc-navigation.md "N0 result and the N0b design"). Runner kind npc_nav.

Why: N0 (npc_nav_n0) could not tell a walk from wandering. Every actor, commanded or not, stayed in x -11..0, y -6..2
and never came closer than 10.8 m to B (5, 10); N0_base wandered 5.4 m towards B (FAIL WANDER), N0_ptr / N0_ptr_lvl
"passed" with 6.8 / 9.0 m, inside that wander; cf "Actor.PathToReference" failed ("No script named Actor is attached
to the object"); SetPlayerTeammate + EvaluatePackage stood still 30 s. Offline (navmesh_points.py, Starfield.esm):
QASmoke's navmesh 002BE3AA is one flat component (14 triangles, 554.7 m2) and the old straight path was clear
by {old.get('segment_clearance')} m, so the navmesh did not stop the walk; an actor gained up to
{old.get('drift_progress')} m on the old pair just by going to the middle of the room or the arrival marker, where
N0's actors went.

New pair (navmesh_points.py, chosen by rule, deterministic): A {a} -> B {b}, {ch['distance']} m along the north side,
one navmesh, straight path = navmesh path = free path ({ch['free_path_ratio']} x), clear by {ch['segment_clearance']} m,
ends {ch['a_clearance']} / {ch['b_clearance']} m from walls and the open navmesh edge; A {ch['a_from_arrival']} m and
B {ch['b_from_arrival']} m from the arrival marker (COCMarkerHeading 002BE3AF at -3.4, -1.1), B {ch['b_from_trace']} m
from every N0 read; going to the arrival marker gains {ch['attractor_progress']} m, to the worst place N0's actors went
(or the navmesh centre) {ch['drift_progress']} m. No furniture or idle marker on the navmesh.

Rule (existing keys, so the integration-1012 runner plans and judges it as is): PASS = within
{RULE['radius']:g} m of the player at B (not at the first read) or {RULE['min_progress']:g} m closer than at t0; a
baseline FAILs WANDER on the same numbers. Reads at {RULE['reads_s']} s of game time (a 1 s read added). The
spawn-read approach rule (PR #75) stays: a commanded actor that came 12 m closer before the command is INCONCLUSIVE
PRECOMMAND.
Tests (actor, method, expected; basis in plan.json):
  N0b_base           002B211C citizen   none            PASS (stays away)
  N0b_ptr            002B211C citizen   PathToRef       FAIL STALLED (N0: PTR did nothing; a PASS proves it works)
  N0b_combat         002B211C citizen   StartCombat     FAIL STALLED (Cowardly: flees)
  N0b_spacer_base    00270255 Spacer    none            FAIL WANDER (hostile: comes on its own)
  N0b_spacer_combat  00270255 Spacer    StartCombat     PASS
  N0b_spacer_ptr     00270255 Spacer    PathToRef       PASS (credited only if N0b_spacer_base stayed away)
Controls: N0b_ptr, N0b_combat (gate N1 / N2a FAILs of the citizen), N0b_spacer_* (for a Spacer gate later).

Reading the results:
  N0b_base PASS + N0b_ptr or N0b_combat PASS: that command walks the citizen; N1 / N2a FAILs with it now count.
  N0b_base PASS, both commanded FAIL: no console command walks the calm citizen; look at end d vs d0 (a flight from
    StartCombat shows as end d > d0). N1 / N2a can then only be judged through the Spacer (hostility) or a PASS.
  N0b_base FAIL WANDER: the citizen still came 12 m on its own here: the pair or the rule is wrong, nothing is gated.
  N0b_spacer_base FAIL WANDER: hostility brings the Spacer to the player on this navmesh: a navigation reference
    without any command (its commanded PASSes are then not credited to the command).
  Mind the save's companion (the robot in N0's shots, also in the baseline): it may fight the Spacer.

Plan (from a checkout at claude/integration-1012 or later; nothing to install):
  {PY} scripts\\game\\testqueue.py plan-npc ^
         --staging C:\\Modding\\staging\\integ_1011 --exp-dir {out} --out C:\\Modding\\testqueue\\npc_nav_n0b --fresh
Chain line: npc_nav_n0b (before any N1 / N2 queue planned with --control-queue C:\\Modding\\testqueue\\npc_nav_n0b).
Files: plan.json (runner input, scripts/actors/npc_control.py n0b), qasmoke_points.json (navmesh_points.py analyze:
navmesh, components, objects, old and new pair, candidates), qasmoke_topdown.png (navmesh, obstacles, N0's reads,
old and new pair).
"""


def plan_command(out, old_queue, new_queue, control_queue):
    """The plan-npc command for a derived plan, with the staging, install and plugins of the old queue it replaces
    (read from its queue.json, never written) and the control queue switched to N0b when the old one had one."""
    with open(os.path.join(old_queue, "queue.json"), encoding="utf-8-sig") as f:
        q = json.load(f)
    cmd = [PY, r"scripts\game\testqueue.py", "plan-npc", "--staging", q["staging"], "--exp-dir", out,
           "--out", new_queue]
    pre = q.get("pre_launch") or []
    for opt, key in (("--exp-dir", "--install-exp"), ("--plugins", "--plugins")):
        if opt in pre and pre.index(opt) + 1 < len(pre):
            cmd += [key, pre[pre.index(opt) + 1]]
    if q.get("control_queue"):
        cmd += ["--control-queue", control_queue]
    if all(t.get("fresh") for t in q.get("tests", [])):
        cmd.append("--fresh")
    return " ".join(cmd)


def derive_readme(src_plan, out, notes, tests, command=""):
    return f"""Derived npc_nav plan (scripts/actors/npc_control.py derive, branch claude/npc-control-n0b): {src_plan}
re-planned with the N0b rule and gated by npc_nav_n0b (docs/actors/npc-navigation.md "N0 result and the N0b design").
Rule: PASS within {RULE['radius']:g} m of the player or {RULE['min_progress']:g} m closer (baselines: FAIL WANDER on
the same numbers); reads at {RULE['reads_s']} s. Everything else (world, points outside QASmoke, drop, settle, anchor,
requires) as in the source plan, whose README says what the world is.
Changes:
""" + "".join(f"  - {n}\n" for n in notes) + "Tests: " + ", ".join(
        f"{w['label']} ({w.get('method', 'ptr_player')})" for w in tests) + "\n" + (
        f"Plan (from a checkout at claude/integration-1012 or later, after npc_nav_n0b is planned):\n  {command}\n"
        if command else "Plan with the source plan's command, --exp-dir this folder, a new --out queue folder and "
                        "--control-queue C:\\Modding\\testqueue\\npc_nav_n0b.\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("n0b")
    p.add_argument("--points", required=True)
    p.add_argument("--out", required=True)
    d = sub.add_parser("derive")
    d.add_argument("--plan", required=True)
    d.add_argument("--out", required=True)
    d.add_argument("--points", default="")
    d.add_argument("--methods", default=",".join(METHODS))
    d.add_argument("--map-queue", action="append", default=[], help="<old queue dir>=<new queue dir> for requires")
    d.add_argument("--from-queue", default="", help="the old queue this plan replaces (read only): its staging, "
                   "install and plugins go into the plan command the README gives")
    d.add_argument("--queue-out", default="", help="the new queue folder for that command")
    d.add_argument("--control-queue", default=r"C:\Modding\testqueue\npc_nav_n0b")
    c = sub.add_parser("check")
    c.add_argument("--plan", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "check":
        tests = check(_load(a.plan))
        print(f"{a.plan}: {len(tests)} tests pass the runner's plan validation")
        return 0
    if a.cmd == "n0b":
        res, pa, pb, ch = _pair(a.points)
        tests = n0b_tests(pa, pb, ch)
        check(tests)
        _write(a.out, tests, n0b_readme(res, pa, pb, ch, os.path.abspath(a.out)))
        print(f"{len(tests)} N0b tests -> {os.path.join(a.out, 'plan.json')} (A {pa}, B {pb}, {ch['distance']} m)")
        return 0
    methods = tuple(m for m in a.methods.split(",") if m)
    bad = [m for m in methods if m not in testqueue.NPC_METHODS or m == "none"]
    if bad:
        sys.exit(f"--methods: {bad} are not commanded npc_nav methods ({sorted(testqueue.NPC_METHODS)})")
    mq = {}
    for x in a.map_queue:
        if "=" not in x:
            sys.exit(f"--map-queue wants <old>=<new>: {x!r}")
        k, v = x.split("=", 1)
        mq[k] = os.path.abspath(v)
    pair = None
    if a.points:
        _res, pa, pb, _ch = _pair(a.points)
        pair = (pa, pb)
    tests, notes = derive(_load(a.plan), methods, pair, mq,
                          os.path.basename(os.path.normpath(a.control_queue)))
    check(tests)
    command = ""
    if a.from_queue:
        if not a.queue_out:
            sys.exit("--from-queue needs --queue-out (the new queue folder)")
        command = plan_command(os.path.abspath(a.out), a.from_queue, a.queue_out, a.control_queue)
    _write(a.out, tests, derive_readme(os.path.abspath(a.plan), os.path.abspath(a.out), notes, tests, command))
    for n in notes:
        print("  " + n)
    print(f"{len(tests)} tests -> {os.path.join(a.out, 'plan.json')}")
    if command:
        print(command)
    return 0


if __name__ == "__main__":
    sys.exit(main())
