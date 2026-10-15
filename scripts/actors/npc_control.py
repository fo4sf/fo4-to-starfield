"""NPC navigation control N0b (docs/actors/npc-navigation.md, "N0 result and the N0b design"): the npc_nav plan.json
of the vanilla control from navmesh_points.py's analysis of QASmoke, the wander evidence of earlier runs, and N1 / N2
plans derived from earlier ones so they are judged by the same rule and gated by N0b.

usage:
  python scripts/actors/npc_control.py n0b --points <qasmoke_points.json> --out <staging dir> [--wander <queue dir>]...
  python scripts/actors/npc_control.py wander --queue <npc_nav queue dir>... [--out <wander.json>]
  python scripts/actors/npc_control.py derive --plan <old plan.json> --out <staging dir> [--points <points.json>]
         [--methods ptr_player,combat_player] [--twins combat_player] [--control-plan <N0b plan.json>]
         [--map-queue <old queue dir>=<new queue dir>]... [--from-queue <old queue> --queue-out <new queue>]
  python scripts/actors/npc_control.py ready --plan <derived plan.json> --control-queue <N0b queue dir>
  python scripts/actors/npc_control.py check --plan <plan.json>

The rule (rule_for; precommand_m and arrive_progress need a runner with feature npc_t0, runner_features.py): the
  commanded walk is measured from t0, the read in the session that types the command. For a pair D m long, P = D - 6 m
  (radius 3 m, pre-command allowance 3 m; rounded down to 0.5 m): PASS = it came within radius 3 m of the player (who
  stands at B; not already at the first read) after coming arrive_progress P closer than at t0, or it ended
  min_progress P closer than at t0. An actor that came precommand_m 3 m towards the player between the spawn read and
  t0 is INCONCLUSIVE PRECOMMAND (beyond it even a walk all the way could not show P); one that arrives with less than
  P after t0 is INCONCLUSIVE SHORT. A baseline (no command) FAILs WANDER when it comes within 3 m, or P closer between
  ANY two of its reads (spawn read and t0 included): wander may start before or after the moment a command is typed.
  Why from t0: with the integration-1012 judge an arrival counted whatever the actor had wandered before the command,
  and its pre-command guard is min_progress itself, so 11.5 m of approach before the command and 3.5 m after it
  passed (verifier of PR #77). Why P = D - 6 on a 24 m pair (P = 18 m): the wander table (`wander`, below) of
  npc_nav_n0 / n1a / n1c: the largest uncommanded approach towards the player is 9.5 m (N1c_ptr_player, before its
  command), after t0 9.0 m (N0_ptr_lvl); the largest distance from t0 in any direction 14.1 m (N1c_cross_ptr), the
  worst case had it pointed at the player; going to a fixed place N0's actors went 11.7 m (navmesh_points.py drift).
  The N0b pair's margins: 8.6 / 9.0 / 3.9 / 6.3 m. The two citizen baselines are the in-run check.

`wander` reads obs.json of earlier npc_nav queues (read only) and lists per run how far the actor came towards the
player and how far it moved, before and after t0 (none of N0's or N1's commands was shown to walk an actor, so every
run counts as wander).

`derive` keeps every test of an old plan whose method is "none" or in --methods (the methods N0b controls), drops the
others (their FAIL could never count: no N0b control), moves QASmoke tests to the N0b pair (--points), sets the rule
of each test's own pair (rule_for: an N1 pair of 19.1 m gets P = 13 m, thinner than N0b's),
drops a test that repeats one of the control plan (--control-plan: same actor, method, travel and points), renames
requires queues (--map-queue), adds a twin of the first commanded test for each method in --twins (none by default:
the citizen is Cowardly, a combat twin waits for N0b_combat), and a baseline of that actor and pair when there is none
(the actor's own movement in that world). Every written test is checked with testqueue.npc_test.

`ready` says whether a derived plan is worth a run: for every commanded test, N0b's control of the same actor
(control_npc) and method must have PASSed and the baselines in N0b's queue must have passed with none WANDER (the gate
testqueue.control_gate applies). Exit 0: plan and queue it; 4: not yet or never (its FAILs would be INCONCLUSIVE
CONTROL).
"""
import argparse
import copy
import glob
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "scripts", "game"))
import testqueue  # noqa: E402

CITIZEN = "002B211C"      # EncCitizen01Template: N0's actor. AIDT 00 00 32 03 00 01 00: Unaggressive, Cowardly
SPACER = "00270255"       # EncSpacer01Template: N2b's reference. AIDT 00 03 32 03 00 01 01: Unaggressive, Brave;
#                           SpacerFaction (Enemy to PlayerFaction) and 6 reaction-radius RDSA entries
RADIUS = 3.0                      # within this of the player (who stands at B) is "arrived"
PRECOMMAND = 3.0                  # the approach allowed between the spawn read and t0 (N0_cf 4.4 m, N1c 9.5 / 3.4 m)
READS = [0, 1, 3, 8, 15, 30]      # a 1 s read: an actor that runs to the player is seen on the way (else EARLY)
P_MIN = 10.0                      # a pair too short for P >= 10 m cannot tell a walk from wander at all
# the wander table of npc_nav_n0 / n1a / n1c (2026-10-12, `wander`): the largest approach towards the player between
# two reads (N1c_ptr_player, before its command) and the largest move from t0 in any direction (N1c_cross_ptr)
WANDER_TOWARDS, WANDER_ANY = 9.45, 14.06
METHODS = ("ptr_player", "combat_player")         # the commands N0b controls (the others failed in N0)
QASMOKE = {"travel": "coc QASmoke", "drop": 0.5, "settle_ms": 1500}       # N0's travel, drop and settle
HOSTILE = {"handle_tol": 3.0}                     # N2b's: a hostile actor may step away while the handle is read
N0_EVIDENCE = ("N0 (npc_nav_n0, 2026-10-12): every actor stayed in x -11..0, y -6..2, never closer than 10.8 m to "
               "B (5, 10); N0_base came 5.4 m closer without a command")
WANDER_EVIDENCE = ("wander table (README, npc_nav_n0 / n1a / n1c obs.json): the largest uncommanded approach towards "
                   "the player 9.5 m (N1c_ptr_player, before its command), after t0 9.0 m (N0_ptr_lvl); the largest "
                   "distance from t0 in any direction 14.1 m (N1c_cross_ptr)")
PY = r"C:\Modding\venv-render\Scripts\python.exe"     # the chain's Python (docs/ai/test-queue.md, codex-runbook.md)
N0B_QUEUE = r"C:\Modding\testqueue\npc_nav_n0b"


def rule_for(a, b):
    """The N0b rule for a pair a -> b: P = its length less RADIUS and PRECOMMAND, rounded down to 0.5 m."""
    d = math.dist(a[:2], b[:2])
    p = math.floor((d - RADIUS - PRECOMMAND) * 2) / 2
    if p < P_MIN:
        sys.exit(f"pair {list(a[:2])} -> {list(b[:2])} is {d:.1f} m: P {p:g} m < {P_MIN:g} m, too short for the "
                 f"N0b rule")
    return {"radius": RADIUS, "min_progress": p, "arrive_progress": p, "precommand_m": PRECOMMAND,
            "reads_s": list(READS)}


def _pair(points):
    with open(points, encoding="utf-8") as f:
        res = json.load(f)
    ch = res.get("chosen")
    if not ch:
        sys.exit(f"{points}: no chosen pair (navmesh_points.py analyze found none)")
    return res, [round(x, 3) + 0.0 for x in ch["a"]], [round(x, 3) + 0.0 for x in ch["b"]], ch


# ------------------------------------------------------------------------------------------------------------- wander
def wander_rows(queues):
    """One row per confirmed run of the npc_nav queues (obs.json, read only): early = how much closer to the player the
    actor came between the spawn read and t0; pre_moved = how far it moved then; approach_t0 = d0 - min d after t0;
    approach_any = the largest approach between any two reads (spawn read and t0 included); moved_t0 = the largest
    distance from t0; spread = the largest distance between two reads from t0 on. Horizontal metres, to the player's
    read at B (the same frame as the actor's reads)."""
    rows = []
    for q in queues:
        qq = testqueue.load(os.path.join(q, "queue.json"), {}) or {}
        for t in qq.get("tests", []):
            if t.get("kind") != "npc_nav":
                continue
            for o in sorted(glob.glob(os.path.join(q, "tests", t["id"], "a*", "obs.json"))):
                obs = testqueue.load(o, {}) or {}
                sp = obs.get("spawn") or {}
                if sp.get("isid") != 1 or sp.get("confirmed") is False:
                    continue
                ps, p0 = testqueue.parse3(sp.get("read")), testqueue.parse3((obs.get("t0") or {}).get("read"))
                pb = testqueue.parse3(obs.get("player_b"))
                reads = [testqueue.parse3(s.get("read")) for s in obs.get("samples") or []
                         if isinstance(s, dict) and s.get("isid") == 1]
                reads = [p for p in reads if p is not None]
                if ps is None or p0 is None or pb is None or not reads:
                    continue

                def d(p):
                    return math.hypot(p[0] - pb[0], p[1] - pb[1])

                def gap(p, r):
                    return math.hypot(p[0] - r[0], p[1] - r[1])
                seq = [ps, p0] + reads
                after = [p0] + reads
                rows.append({
                    "run": f"{os.path.basename(os.path.normpath(q))}/{t.get('ref')}/"
                           f"{os.path.basename(os.path.dirname(o))}",
                    "npc": t.get("npc"), "method": t.get("method"), "reads": len(reads),
                    "early": round(d(ps) - d(p0), 2), "pre_moved": round(gap(ps, p0), 2),
                    "approach_t0": round(d(p0) - min(d(p) for p in reads), 2),
                    "approach_any": round(max(max(d(seq[i]) - d(seq[j]) for i in range(len(seq))
                                                  for j in range(i + 1, len(seq))), 0.0), 2),
                    "moved_t0": round(max(gap(p, p0) for p in reads), 2),
                    "spread": round(max(gap(after[i], after[j]) for i in range(len(after))
                                        for j in range(i + 1, len(after))), 2)})
    return rows


WANDER_KEYS = ("early", "pre_moved", "approach_t0", "approach_any", "moved_t0", "spread")


def wander_summary(rows):
    """{key: [largest value, run]} over the rows."""
    out = {}
    for k in WANDER_KEYS:
        if rows:
            r = max(rows, key=lambda x: (x[k], x["run"]))
            out[k] = [r[k], r["run"]]
    return out


def wander_table(rows, p=None):
    s = wander_summary(rows)
    lines = ["run | npc | method | early | pre_moved | approach_t0 | approach_any | moved_t0 | spread"]
    for r in rows:
        lines.append(" | ".join(str(r[k]) for k in ("run", "npc", "method") + WANDER_KEYS))
    if s:
        lines.append("largest: " + "; ".join(f"{k} {v[0]} m ({v[1]})" for k, v in s.items()))
    if s and p:
        lines.append(f"margin to {p:g} m: approach_any {p - s['approach_any'][0]:.1f} m, approach_t0 "
                     f"{p - s['approach_t0'][0]:.1f} m, moved_t0 {p - s['moved_t0'][0]:.1f} m (the worst case: all "
                     f"of it towards the player), spread {p - s['spread'][0]:.1f} m")
    return "\n".join(lines)


# --------------------------------------------------------------------------------------------------------------- N0b
def n0b_tests(a, b, ch):
    """The N0b plan: the calm citizen (two baselines, PathToRef, StartCombat) and the hostile Spacer's baseline."""
    rule = rule_for(a, b)
    p = rule["min_progress"]
    clear = ch.get("segment_clearance_exact", ch["segment_clearance"])
    where = (f"A {a[:2]} -> B {b[:2]}, {ch['distance']} m, one navmesh, straight path clear by {clear} m, going to a "
             f"fixed place N0's actors went gains {ch['drift_progress']} m (verified offline, navmesh_points.py)")
    said = (f"PASS = within {RADIUS:g} m after coming {p:g} m closer than at t0, or {p:g} m closer at the end; a "
            f"baseline FAILs WANDER on {p:g} m between any two reads")

    def t(label, npc, method, control, expect, basis, **kw):
        return {"label": label, "npc": npc, "method": method, **QASMOKE, "a": a, "b": b, **rule,
                "control": control, "expect": expect, "basis": basis, **kw}
    base = (f"supported hypothesis: {N0_EVIDENCE}; {WANDER_EVIDENCE}: no run on record came {p:g} m towards the "
            f"player between any two reads ({said}; {where})")
    return [
        t("N0b_base", CITIZEN, "none", False, "PASS", base),
        t("N0b_base2", CITIZEN, "none", False, "PASS",
          base + ". A second baseline in its own launch: the approach to the player is not every run's (N1c's "
          "citizen walked 9.5 m up to the player before one command, 3.4 m and none before the other two); a WANDER of "
          "either voids the citizen's controls (testqueue.control_gate)"),
        t("N0b_ptr", CITIZEN, "ptr_player", True, "FAIL STALLED",
          "supported hypothesis: PathToRef typed on the console has not walked the citizen to the player anywhere: "
          "N0_ptr (6.8 m) and N0_ptr_lvl (9.0 m) stayed inside N0_base's wander, and in N1c (npc_nav_n1c, "
          "2026-10-12) the citizen went from 10.0 to 16.9 m (N1c_ptr_player) and from 15.2 to 15.8 m (N1c_cross_ptr) "
          f"from the player after it. A PASS here ({p:g} m from t0) would show it does ({where})"),
        t("N0b_combat", CITIZEN, "combat_player", True, "FAIL STALLED",
          "supported hypothesis: EncCitizen01Template is Cowardly (AIDT confidence 0, verified in Starfield.esm), and "
          "a cowardly actor in combat flees (Bethesda AI semantics, not measured in Starfield): it moves, away from "
          "the player. PASS = StartCombat brings even a cowardly citizen to the player (then derive --twins "
          "combat_player)"),
        t("N0b_spacer_base", SPACER, "none", False, "FAIL WANDER",
          "supported hypothesis: SpacerFaction is Enemy to PlayerFaction and the Spacer has 6 reaction radii "
          "(verified); spawned at the player's feet it starts combat and comes for the player without a command: a "
          "navigation reference that needs no console command. PASS = it stays away: Unaggressive (verified) wins",
          **HOSTILE),
    ]


def first_group(tests):
    """(npc, travel, a, b) of the first commanded test, or None."""
    for w in tests:
        if w.get("method", "ptr_player") != "none":
            return (str(w["npc"]).upper(), w["travel"], tuple(w["a"]), tuple(w["b"]))
    return None


def _key(w):
    return (str(w["npc"]).upper(), w["travel"], tuple(w["a"]), tuple(w["b"]))


def _same(w, c):
    return _key(w) == _key(c) and w.get("method", "ptr_player") == c.get("method", "ptr_player")


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


def derive(tests, methods=METHODS, pair=None, map_queue=None, control_queue_name="npc_nav_n0b", twins=(),
           control_tests=()):
    """(new tests, notes). tests: an old plan.json list; control_tests: the control plan's tests (repeats dropped)."""
    map_queue = {os.path.normcase(os.path.abspath(k)): v for k, v in (map_queue or {}).items()}
    keep, notes, moved, mapped = [], [], [], []
    for w in tests:
        m = w.get("method", "ptr_player")
        if m != "none" and m not in methods:
            notes.append(f"dropped {w.get('label')} ({m}: no N0b control for it, its FAIL could never count)")
            continue
        w = copy.deepcopy(w)
        to_pair = bool(pair) and w.get("travel") == QASMOKE["travel"]
        if to_pair:
            w["a"], w["b"] = list(pair[0]), list(pair[1])
        rule = rule_for(w["a"], w["b"])
        w.update(rule)
        twin = next((c for c in control_tests if _same(w, c)), None)
        if twin is not None:
            notes.append(f"dropped {w.get('label')}: the same actor, method, cell and points as {twin['label']} in "
                         f"{control_queue_name}, whose result it would repeat")
            continue
        if to_pair:
            moved.append(w.get("label"))
        r = w.get("requires")
        if r and r.get("queue"):
            new = map_queue.get(os.path.normcase(os.path.abspath(r["queue"])))
            if new:
                w["requires"] = dict(r, queue=new)
                mapped.append(f"{w.get('label')} -> {new}")
        dist = math.dist(w["a"][:2], w["b"][:2])
        w["basis"] = (w.get("basis", "") + f" [re-planned with the N0b rule for this {dist:.1f} m "
                      f"pair: within {RADIUS:g} m after {rule['arrive_progress']:g} m from t0, or "
                      f"{rule['min_progress']:g} m closer; FAILs gated by {control_queue_name}]").strip()
        if m != "none" and not w.get("control"):
            gate = str(w.get("control_npc") or w["npc"]).upper()
            w["basis"] += (f" [conditional: queue this plan only once `npc_control.py ready` reports "
                           f"{control_queue_name}'s {m} control of {gate} and the baselines next to it passed; the "
                           f"expected verdict is for that case. N0b expects its citizen controls to FAIL STALLED: "
                           f"then this plan is not run, its FAIL would be INCONCLUSIVE CONTROL]")
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
        for m in twins:
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
            base["basis"] = ("derived baseline (no command): the actor's own movement in this world and pair. A WANDER "
                             "here takes the credit from this queue's commanded PASSes (any baseline of the actor in "
                             f"this queue or {control_queue_name} that came voids it); it does not open or close the "
                             f"FAIL gate, which takes {control_queue_name}'s control and the baselines in its queue")
            keep.insert(0, base)
            notes.append(f"added {base['label']} (baseline of {src['npc']} in this world)")
    labels = [w.get("label") for w in keep]
    if len(set(labels)) != len(labels):
        sys.exit(f"duplicate labels after deriving: {labels}")
    return keep, notes


def check(tests):
    """Every test through the runner's own validation (testqueue.npc_test exits on an unknown key or a bad value)."""
    return [testqueue.npc_test(n, w) for n, w in enumerate(tests)]


def ready(tests, control_queue):
    """(open, lines): for every commanded non-control test, whether control_queue holds a PASS of the control with the
    same actor (control_npc) and method and, when baselines of that actor are planned there, a baseline PASS and no
    WANDER (testqueue.control_gate's rule for a control of another queue)."""
    q = testqueue.load(os.path.join(control_queue, "queue.json"), {}) or {}
    done = (testqueue.load(os.path.join(control_queue, "state.json"), {}) or {}).get("done", {})
    lines, ok = [], True
    for w in tests:
        m = w.get("method", "ptr_player")
        if m == "none" or w.get("control"):
            continue
        gate = str(w.get("control_npc") or w["npc"]).upper()

        def res(c):
            r = done.get(c["id"]) or {}
            return f"{c.get('ref')} " + (f"{r.get('verdict')} {r.get('class')}" if r else "no result")
        ctrl = [c for c in q.get("tests", []) if c.get("kind") == "npc_nav" and c.get("control")
                and c.get("npc") == gate and c.get("method") == m]
        base = [c for c in q.get("tests", []) if c.get("kind") == "npc_nav" and c.get("baseline")
                and c.get("npc") == gate]
        cpass = [c for c in ctrl if (done.get(c["id"]) or {}).get("verdict") == "PASS"]
        bpass = [c for c in base if (done.get(c["id"]) or {}).get("verdict") == "PASS"]
        came = [c for c in base if (done.get(c["id"]) or {}).get("class") == "WANDER"]
        good = bool(cpass) and (not base or (bool(bpass) and not came))
        ok = ok and good
        lines.append(f"{w.get('label')} ({m}, gated by {gate}): {'open' if good else 'closed'}: controls "
                     f"{', '.join(res(c) for c in ctrl) or 'none planned'}; baselines "
                     f"{', '.join(res(c) for c in base) or 'none planned'}")
    if not lines:
        lines.append("no commanded test: nothing to gate")
    return ok, lines


def _load(p):
    with open(p, encoding="utf-8-sig") as f:
        src = json.load(f)
    return src.get("tests") if isinstance(src, dict) else src


def _write(out, tests, readme, extra=None):
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(tests, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(readme)
    for name, obj in (extra or {}).items():
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=1)


def n0b_readme(res, a, b, ch, out, rows=()):
    old = res.get("old_pair") or {}
    rule = rule_for(a, b)
    p = rule["min_progress"]
    table = wander_table(list(rows), p) if rows else "(no --wander queue given)"
    big = wander_summary(list(rows))
    toward = big.get("approach_any", [WANDER_TOWARDS])[0]
    anyway = big.get("moved_t0", [WANDER_ANY])[0]
    rev = (res.get("chosen_reversed") or {}).get("b_from_trace")
    return f"""NPC navigation N0b: the vanilla control that tells a commanded walk from wandering (Claude, branch
claude/npc-control-n0b; docs/actors/npc-navigation.md "N0 result and the N0b design"). Runner kind npc_nav.

Why: N0 (npc_nav_n0) could not tell a walk from wandering. Every actor, commanded or not, stayed in x -11..0, y -6..2
and never came closer than 10.8 m to B (5, 10); N0_base wandered 5.4 m towards B (FAIL WANDER), N0_ptr / N0_ptr_lvl
"passed" with 6.8 / 9.0 m, inside that wander; cf "Actor.PathToReference" failed ("No script named Actor is attached
to the object"); SetPlayerTeammate + EvaluatePackage stood still 30 s. Offline (navmesh_points.py, Starfield.esm):
QASmoke's navmesh 002BE3AA is one flat component (14 triangles, 554.7 m2) and the old straight path was clear by
{old.get('segment_clearance_exact', old.get('segment_clearance'))} m, so the navmesh did not stop the walk.

Pair (navmesh_points.py, chosen by rule, deterministic): A {a} -> B {b}, {ch['distance']} m, from the south-east
corner through the middle of the room to the north-west corner; one navmesh, straight path = navmesh path = free path
({ch['free_path_ratio']} x), clear by {ch.get('segment_clearance_exact')} m (exact; {ch['segment_clearance']} m on the
0.1 m grid), ends {ch.get('a_clearance_exact')} / {ch.get('b_clearance_exact')} m from walls, pillars and the open
navmesh edge; A {ch['a_from_arrival']} m and B {ch['b_from_arrival']} m from the arrival marker (COCMarkerHeading
002BE3AF at -3.4, -1.1), B {ch['b_from_trace']} m from every N0 read. Direction matters: reversed, B would be {rev} m
from an N0 read. Going to a fixed place N0's actors went (the arrival marker, the navmesh centre, an N0 read) gains
at most {ch['drift_progress']} m (to {ch.get('drift_to')}): that is one model only (fixed attractors). Wander that
moves with the actor is in the table below. The pair is 24 m (the first N0b plan had 18 m) because the table holds a
14.1 m move from t0, more than the 12 m an 18 m pair allows.

Rule (plan keys precommand_m / arrive_progress: the runner needs feature npc_t0, i.e. this branch; an integration-1012
runner refuses the queue before launching the game): the walk is measured from t0, the read in the command's session.
  PASS = within {RADIUS:g} m of the player at B (not at the first read) after coming {p:g} m closer than at t0, or
         ended {p:g} m closer than at t0;
  INCONCLUSIVE PRECOMMAND = came {PRECOMMAND:g} m towards the player between the spawn read and t0 (P = {p:g} m is
         the pair less {RADIUS:g} m and {PRECOMMAND:g} m: beyond that a walk all the way could not show P);
  INCONCLUSIVE SHORT = arrived, but less than {p:g} m closer than at t0;
  baseline FAIL WANDER = within {RADIUS:g} m, or {p:g} m closer between ANY two of its reads (spawn read and t0
         included).
Reads at {rule['reads_s']} s of game time (a 1 s read added).

Wander evidence (npc_control.py wander; every run counts: no command was shown to walk an actor). early = towards
the player between the spawn read and t0; approach_t0 = d0 - min d; approach_any = between any two reads;
moved_t0 / spread = distance from t0 / between two reads, in any direction (the worst case if it all pointed at the
player). Metres.
{table}
The approach to the player before the command (N0_cf 4.4 m, N1c_ptr_player 9.5 m, N1c_follow_player 3.4 m) is why
precommand_m is {PRECOMMAND:g} m. Margins to {p:g} m: {p - toward:.1f} m over the largest approach towards the player,
{p - anyway:.1f} m over the largest move from t0 in any direction, {p - ch['drift_progress']:.1f} m over the fixed-place
drift. The two citizen baselines are the in-run check: the gate takes a WANDER of either as voiding the citizen's
controls.

Tests (actor, method, expected; basis in plan.json):
  N0b_base, N0b_base2  002B211C citizen   none            PASS (stays away; two launches)
  N0b_ptr              002B211C citizen   PathToRef       FAIL STALLED (N0, N1c: PTR did nothing; a PASS: it works)
  N0b_combat           002B211C citizen   StartCombat     FAIL STALLED (Cowardly: flees)
  N0b_spacer_base      00270255 Spacer    none            FAIL WANDER (hostile: comes on its own)
Controls: N0b_ptr, N0b_combat (they gate N1 / N2a FAILs of the citizen, with N0b_base and N0b_base2).
Not planned: commanded Spacer tests. Spawned at the player's feet, a hostile Spacer comes for the player in the few
seconds before the command, so they would read INCONCLUSIVE PRECOMMAND and be retried; N0b_spacer_base answers the
hostility question without a command. N2b's Spacer baseline is this test (npc_nav_n2b_b no longer repeats it).

Reading the results:
  N0b_base and N0b_base2 PASS + N0b_ptr or N0b_combat PASS: that command walks the citizen; derived N1 / N2a plans
    with it are worth a run (`npc_control.py ready` exits 0).
  Both baselines PASS, both commanded FAIL (expected): no console command walks the calm citizen; the derived
    citizen plans are not run (their FAILs would be INCONCLUSIVE CONTROL). Look at end d vs d0 (a flight from
    StartCombat shows as end d > d0).
  A baseline FAIL WANDER: the citizen came {p:g} m on its own here: nothing is gated open; read its detail.
  PRECOMMAND / SHORT: the citizen walked up to the player before the command; the runner retries it.
  N0b_spacer_base FAIL WANDER: hostility brings the Spacer to the player on this navmesh: a navigation reference that
    needs no command. Mind the save's companion (the robot in N0's shots, also in the baseline): it may fight it.

Plan (from a checkout with this branch, claude/npc-control-n0b, merged; nothing to install):
  {PY} scripts\\game\\testqueue.py plan-npc ^
         --staging C:\\Modding\\staging\\integ_1011 --exp-dir {out} --out {N0B_QUEUE} --fresh
Chain line: npc_nav_n0b, run by a runner with feature npc_t0 (scripts/game/runner_features.py).
Files: plan.json (runner input, scripts/actors/npc_control.py n0b), wander.json (the table above),
qasmoke_points.json (navmesh_points.py analyze: navmesh, components, objects, old and new pair, candidates),
qasmoke_topdown.png (navmesh, obstacles, N0's reads, old and new pair).
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


def derive_readme(src_plan, out, notes, tests, command="", control_queue=N0B_QUEUE):
    commanded = [w for w in tests if w.get("method", "ptr_player") != "none" and not w.get("control")]
    req = sorted({w["requires"]["queue"] for w in tests if (w.get("requires") or {}).get("queue")})
    before = []
    if commanded:
        before.append(f"{control_queue} has results and\n    {PY} scripts\\actors\\npc_control.py ready --plan "
                      f"{os.path.join(out, 'plan.json')} --control-queue {control_queue}\n    exits 0 (N0b's "
                      f"controls of these methods and its baselines passed; N0b expects its citizen controls to "
                      f"FAIL, then this plan is not run)")
    for r in req:
        before.append(f"{r} is planned: plan-npc refuses a requires naming a queue where that test is not planned")
    pairs = {}
    for w in tests:
        pairs.setdefault((tuple(w["a"][:2]), tuple(w["b"][:2]), w["min_progress"]), []).append(w["label"])
    rules = "".join(f"  {', '.join(v)}: {math.dist(k[0], k[1]):.1f} m pair, P = {k[2]:g} m: margin "
                    f"{k[2] - WANDER_TOWARDS:.1f} m over the largest approach towards the player on record, "
                    f"{k[2] - WANDER_ANY:.1f} m over the largest move from t0 in any direction\n"
                    for k, v in pairs.items())
    return f"""Derived npc_nav plan (scripts/actors/npc_control.py derive, branch claude/npc-control-n0b): {src_plan}
re-planned with the N0b rule and gated by npc_nav_n0b (docs/actors/npc-navigation.md "N0 result and the N0b design").
Rule (runner feature npc_t0), P = the pair less {RADIUS:g} m and {PRECOMMAND:g} m: PASS within {RADIUS:g} m of the
player after coming P closer than at t0, or ended P closer; INCONCLUSIVE PRECOMMAND after {PRECOMMAND:g} m towards the
player before the command, SHORT when it arrives with less than P; baselines FAIL WANDER within {RADIUS:g} m or P
closer between any two reads; reads at {READS} s.
""" + rules + f"""(wander table: npc_nav_n0b's README; a negative margin means a move on record, had it pointed at the
player, would pass: this plan's own baseline is then the only check on a PASS.) Everything else (world, points
outside QASmoke, drop, settle, anchor, requires) as in the source plan, whose README says what the world is.
Gates (testqueue.py of this branch): a FAIL here counts only when {os.path.basename(control_queue)}'s control of the
same actor (control_npc) and method passed and the baselines in that queue passed with none WANDER; a baseline of
this queue does not open or close that gate. A commanded PASS here is credited to the command only when no baseline
of the actor (this queue or {os.path.basename(control_queue)}) came to the player on its own.
Changes:
""" + "".join(f"  - {n}\n" for n in notes) + "Tests: " + ", ".join(
        f"{w['label']} ({w.get('method', 'ptr_player')})" for w in tests) + "\n" + (
        "Before planning:\n" + "".join(f"  - {b}\n" for b in before) if before else "") + (
        f"Plan (from a checkout with claude/npc-control-n0b merged):\n  {command}\n"
        if command else "Plan with the source plan's command, --exp-dir this folder, a new --out queue folder and "
                        f"--control-queue {control_queue}.\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("n0b")
    p.add_argument("--points", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--wander", action="append", default=[], help="npc_nav queue dir read for the wander table")
    w = sub.add_parser("wander")
    w.add_argument("--queue", action="append", required=True)
    w.add_argument("--out", default="")
    d = sub.add_parser("derive")
    d.add_argument("--plan", required=True)
    d.add_argument("--out", required=True)
    d.add_argument("--points", default="")
    d.add_argument("--methods", default=",".join(METHODS))
    d.add_argument("--twins", default="", help="methods to add as twins of the first commanded test (default none)")
    d.add_argument("--control-plan", default="", help="the control queue's plan.json: tests repeating one are dropped")
    d.add_argument("--map-queue", action="append", default=[], help="<old queue dir>=<new queue dir> for requires")
    d.add_argument("--from-queue", default="", help="the old queue this plan replaces (read only): its staging, "
                   "install and plugins go into the plan command the README gives")
    d.add_argument("--queue-out", default="", help="the new queue folder for that command")
    d.add_argument("--control-queue", default=N0B_QUEUE)
    r = sub.add_parser("ready")
    r.add_argument("--plan", required=True)
    r.add_argument("--control-queue", default=N0B_QUEUE)
    c = sub.add_parser("check")
    c.add_argument("--plan", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "check":
        tests = check(_load(a.plan))
        print(f"{a.plan}: {len(tests)} tests pass the runner's plan validation")
        return 0
    if a.cmd == "ready":
        ok, lines = ready(_load(a.plan), a.control_queue)
        for x in lines:
            print("  " + x)
        print("ready: plan and queue it" if ok else "not ready: its FAILs would be INCONCLUSIVE CONTROL")
        return 0 if ok else 4
    if a.cmd == "wander":
        rows = wander_rows(a.queue)
        print(wander_table(rows))
        if a.out:
            with open(a.out, "w", encoding="utf-8") as f:
                json.dump({"rows": rows, "largest": wander_summary(rows)}, f, indent=1)
        return 0
    if a.cmd == "n0b":
        res, pa, pb, ch = _pair(a.points)
        tests = n0b_tests(pa, pb, ch)
        check(tests)
        rows = wander_rows(a.wander)
        _write(a.out, tests, n0b_readme(res, pa, pb, ch, os.path.abspath(a.out), rows),
               {"wander.json": {"queues": [os.path.basename(os.path.normpath(q)) for q in a.wander], "rows": rows,
                                "largest": wander_summary(rows)}} if a.wander else None)
        print(f"{len(tests)} N0b tests -> {os.path.join(a.out, 'plan.json')} (A {pa}, B {pb}, {ch['distance']} m)")
        return 0
    methods = tuple(m for m in a.methods.split(",") if m)
    twins = tuple(m for m in a.twins.split(",") if m)
    bad = [m for m in methods + twins if m not in testqueue.NPC_METHODS or m == "none"]
    if bad:
        sys.exit(f"--methods / --twins: {bad} are not commanded npc_nav methods ({sorted(testqueue.NPC_METHODS)})")
    if set(twins) - set(methods):
        sys.exit(f"--twins {sorted(set(twins) - set(methods))} not in --methods {list(methods)}")
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
    ctrl = _load(a.control_plan) if a.control_plan else []
    tests, notes = derive(_load(a.plan), methods, pair, mq, os.path.basename(os.path.normpath(a.control_queue)),
                          twins, ctrl)
    check(tests)
    command = ""
    if a.from_queue:
        if not a.queue_out:
            sys.exit("--from-queue needs --queue-out (the new queue folder)")
        command = plan_command(os.path.abspath(a.out), a.from_queue, a.queue_out, a.control_queue)
    _write(a.out, tests, derive_readme(os.path.abspath(a.plan), os.path.abspath(a.out), notes, tests, command,
                                       a.control_queue))
    for n in notes:
        print("  " + n)
    print(f"{len(tests)} tests -> {os.path.join(a.out, 'plan.json')}")
    if command:
        print(command)
    return 0


if __name__ == "__main__":
    sys.exit(main())
