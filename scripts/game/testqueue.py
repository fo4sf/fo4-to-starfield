"""Queued in-game test runner: plan a batch of tests on ONE pinned build, run them unattended without any AI calls,
checkpoint after every test, resume later, and rank the problems found.

usage:
  python testqueue.py plan   --staging <build dir> --out <queue dir> [--cells A,B] [--kinds stairs,door,fall,movable,travel]
                             [--per-cell 12] [--per-kind N] [--plugin-index 02]
  python testqueue.py plan-terrain --staging <build dir> --exp-dir <experiment> --out <queue dir> [--plugins a.esm,b.esm]
  python testqueue.py plan-npc --staging <build dir> --exp-dir <dir with plan.json> --out <queue dir>
                             [--install-exp <experiment> --plugins a.esm,b.esm] [--control-queue <N0 queue dir>]
                             [--fresh]
  python testqueue.py run   --queue <queue dir> [--max-tests N] [--max-hours 8] [--min-idle 900] [--wait-for-idle]
                             [--refocus] [--max-attempts 2] [--dry-run]
  python testqueue.py report --queue <queue dir>
  python testqueue.py status --queue <queue dir>

Verdicts: PASS, FAIL (with a reason class) or INCONCLUSIVE. A missing observation (no position read, no screenshot,
start not reached) is INCONCLUSIVE, never PASS. INCONCLUSIVE tests are retried up to --max-attempts; FAIL is final.

The owner's PC-use controls are checked before every launch and every test, and the run stops (checkpointed, resumable)
when one trips:
  - STOP file: <queue>\\STOP or %LOCALAPPDATA%\\fo4-ai-team\\state\\testqueue.STOP (create it to stop the runner);
  - Resource Guardian switch (tools/ai-team guardian.py pause|stop): mode paused or stopped;
  - owner activity: keyboard/mouse input that the runner did not send, or another window in front of the game. With
    --wait-for-idle the runner waits until the PC has been idle --min-idle seconds instead of stopping; with --refocus it
    then brings ITS OWN game window back to the front once (never another app);
  - allowed hours (queue.json "hours", default all day); --max-hours and --max-tests.
A game is only launched when the PC has been idle --min-idle seconds, and only by cycle.ps1 (the runner never touches a
Starfield the owner started). Every key press still goes through input.ps1's foreground guard, with
FO4SF_NO_FOCUS_STEAL=1 so a step can never pull the game in front of the owner's window.
"""
import argparse
import ctypes
import glob
import hashlib
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import route_eval  # noqa: E402

UNIT = 1.0 / 70.0
KINDS = ("stairs", "door", "fall", "movable", "travel")         # planned from a build; "terrain" via plan-terrain
EXTRA_KINDS = ("terrain", "npc_nav")                            # planned from an experiment's plan.json
# ranking weight per (kind, verdict reason class): falling out of the world and broken travel first
SEVERITY = {("fall", "FALL"): 5, ("travel", "NOTRAVEL"): 5, ("travel", "NOPROMPT"): 4, ("door", "BLOCKED"): 4,
            ("door", "NOPROMPT"): 3, ("stairs", "FALL"): 4, ("stairs", "STUCK"): 3, ("door", "FALL"): 5,
            ("movable", "NOTMOVED"): 2, ("movable", "ITEMFELL"): 3, ("any", "CRASH"): 5,
            ("terrain", "NOTERRAIN"): 5, ("terrain", "HEIGHTS"): 4,
            ("npc_nav", "FELL"): 5, ("npc_nav", "NONAV"): 4, ("npc_nav", "STALLED"): 3, ("npc_nav", "WANDER"): 3}
PS = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]
BREAKER = 6          # inconclusive attempts in a row, with no PASS/FAIL yet, that switch a kind off for the run
FINAL_INCONCLUSIVE = ("CONTROL", "PRECONDITION")   # inconclusive for a reason a retry cannot change

# npc_nav (PR #61 docs/actors/npc-navigation.md 3.4): what qstep.ps1 types on the verified console selection to make the
# actor walk to the player, who stands at B. qstep.ps1 has the same table; nothing else is ever typed for a method.
# PathToRef (PTR, one optional TESObjectREFR, "Force actor to path to reference.") is a console command in Starfield.exe
# 1.16.244 (command table decoded, docs/ai/test-queue.md); cf + Actor.PathToReference is the research doc's first idea.
# "none" types nothing: the baseline (does the actor come to the player without a command, e.g. its default package?).
NPC_METHODS = {"none": [],
               "ptr_player": ["PathToRef player"],
               "cf_pathto_player": ['cf "Actor.PathToReference" player 1.0'],
               "follow_player": ["SetPlayerTeammate 1", "EvaluatePackage"],
               "combat_player": ["StartCombat player"]}
# GenerateNavMesh's short name "gnm" sits next to its name and help text in Starfield.exe, but its command entry was
# not decoded (supported hypothesis, unlike PTR / PLR / PRID): staged plans do not use it yet.
NPC_PRE = ("gnm",)                  # probe commands allowed before the spawn (GenerateNavMesh: route R1, run N2)
# every key a plan.json test may carry (npc_test); any other key stops the planning, so a typo or a key of a newer
# runner is never dropped silently (a lost control_npc would turn every FAIL into INCONCLUSIVE CONTROL)
NPC_PLAN_KEYS = frozenset((
    "label", "travel", "npc", "method", "pre", "a", "b", "reads_s", "radius", "min_progress", "nomove", "spawn_tol",
    "target_tol", "fell_m", "drop", "settle_ms", "pre_wait_ms", "max_speed", "spawn_wait_ms", "handle_tol", "path_line",
    "control", "control_npc", "fresh", "anchor", "spawn_local", "requires", "expect", "basis"))
# requires.verdict: the required test's verdict, or DECIDED for either PASS or FAIL (its run was judged at all: for an
# npc_nav test, the spawn was confirmed and the reads were taken)
REQUIRE_VERDICTS = ("PASS", "FAIL", "DECIDED")


# ---------------------------------------------------------------------------------------------------------- utilities
def load(p, default=None):
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def save_atomic(p, obj):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, p)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def parse3(s):
    return route_eval.parse(s) if isinstance(s, str) else None


def heading_to(src, dst):
    return round(math.degrees(math.atan2(dst[0] - src[0], dst[1] - src[1])) % 360, 1)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ----------------------------------------------------------------------------------------------------------- planning
def plan_cell(cell, staging, kinds, per_cell, plugin_index, formids, items, all_refs):
    """Tests for one exported cell, in the owner's priority order: stairs, falls, doors (both sides), movable, travel."""
    name = cell["cell"]
    out = []
    routes_file = os.path.join(staging, f"routes_{name}.json")
    routes = load(routes_file, {}).get("routes", [])
    if "stairs" in kinds:
        for k, r in enumerate(routes):
            if r["kind"] == "stairs":
                out.append({"kind": "stairs", "cell": name, "ref": r["ref"], "model": r["model"],
                            "routes_file": routes_file, "route_index": k})
    if "fall" in kinds:
        pts_file = os.path.join(staging, f"probe_{name}.txt")
        if not os.path.exists(pts_file):
            subprocess.run([sys.executable, os.path.join(HERE, "probe_points.py"), os.path.join(staging, name + ".json"),
                            pts_file, str(per_cell)], check=False, capture_output=True)
        for n, line in enumerate(open(pts_file).read().splitlines() if os.path.exists(pts_file) else []):
            p = line.split(" ", 3)
            if len(p) >= 3:
                out.append({"kind": "fall", "cell": name, "ref": f"pt{n}", "model": p[3] if len(p) > 3 else "",
                            "point": [float(p[0]), float(p[1]), float(p[2])], "heading": 0})
    if "door" in kinds:
        for k, r in enumerate(routes):
            if r["kind"] == "door":
                out.append({"kind": "door", "cell": name, "ref": r["ref"], "model": r["model"], "side": r.get("side"),
                            "routes_file": routes_file, "route_index": k})
    coc = next((r for r in cell["refs"] if r.get("base_editor_id") == "COCMarkerHeading"), None)
    if "movable" in kinds:
        movable_models = {k for k, it in items.items() if it.get("movable")}
        n = 0
        for r in cell["refs"]:
            key = "meshes\\" + (r.get("model") or "").lstrip("\\").lower()
            local = formids.get(f"REFR:FO4Port_{name}:{r['formkey']}")
            if key not in movable_models or local is None or r.get("disabled") or n >= per_cell:
                continue
            item = [x * UNIT for x in r["pos"]]
            towards = [x * UNIT for x in coc["pos"]] if coc else [item[0], item[1] - 1.0, item[2]]
            d = math.hypot(towards[0] - item[0], towards[1] - item[1]) or 1.0
            stand = [item[0] + (towards[0] - item[0]) / d * 1.1, item[1] + (towards[1] - item[1]) / d * 1.1, item[2] + 0.1]
            out.append({"kind": "movable", "cell": name, "ref": r["formkey"], "model": r["model"],
                        "sf_ref": f"{plugin_index}{local:06X}", "item": [round(x, 3) for x in item],
                        "stand": [round(x, 3) for x in stand], "heading": heading_to(stand, item), "walk_ms": 900})
            n += 1
    if "travel" in kinds:
        for r in cell["refs"]:
            t = r.get("teleport_destination")
            if not t or t["door"] not in all_refs:
                continue                                  # leads outside the build: nothing to arrive at
            dest_cell, dest = all_refs[t["door"]]
            back = dest.get("teleport_destination")
            if not back or back.get("door") != r["formkey"]:
                continue                                  # one-way link: no arrival point on this side to start from
            start = [x * UNIT for x in back["pos"]]       # the reverse link's arrival point stands in front of this door
            out.append({"kind": "travel", "cell": name, "ref": r["formkey"], "model": r["model"], "dest_cell": dest_cell,
                        "start": [round(x, 3) for x in start], "heading": heading_to(start, [x * UNIT for x in r["pos"]]),
                        "arrival": [round(x * UNIT, 3) for x in t["pos"]]})
    return out


def plan(a):
    staging = os.path.abspath(a.staging)
    esm = os.path.join(staging, "FO4Port.esm")
    if not os.path.exists(esm):
        sys.exit(f"no FO4Port.esm in {staging}: build it first")
    kinds = [k.strip() for k in a.kinds.split(",") if k.strip()]
    bad = [k for k in kinds if k not in KINDS]
    if bad:
        sys.exit(f"unknown kinds {bad}; known: {KINDS}")
    formids = load(os.path.join(staging, "formids.json"), {})
    items = {it["source"].lower(): it for it in load(os.path.join(staging, "manifest.json"), {"items": []})["items"]}
    skip = {"editorids.json", "formids.json", "lighting.json", "merged.json", "manifest.json"}
    cells = []
    for p in sorted(glob.glob(os.path.join(staging, "*.json"))):
        b = os.path.basename(p)
        if b in skip or b.startswith("routes_") or b.startswith("build"):
            continue
        c = load(p)
        if isinstance(c, dict) and "refs" in c and c.get("cell") and c["cell"] != "merged":
            cells.append(c)
    all_refs = {r["formkey"]: (c["cell"], r) for c in cells for r in c["refs"]}   # travel may lead to an unplanned cell
    if a.cells:
        want = {c.strip() for c in a.cells.split(",")}
        cells = [c for c in cells if c["cell"] in want]
    tests = []
    for c in cells:
        tests += plan_cell(c, staging, kinds, a.per_cell, a.plugin_index, formids, items, all_refs)
    if a.per_kind:                                        # small batches: the first N of each kind in each cell
        seen = {}
        keep = []
        for t in tests:
            k = (t["cell"], t["kind"])
            seen[k] = seen.get(k, 0) + 1
            if seen[k] <= a.per_kind:
                keep.append(t)
        tests = keep
    for n, t in enumerate(tests):
        t["id"] = f"{n:04d}_{t['kind']}_{t['cell']}_{str(t['ref']).split(':')[0]}" + (f"_s{t['side']}" if t.get("side") else "")
    digest = sha256(esm)
    q = {"created": now(), "staging": staging, "plugin_sha256": digest, "build_id": digest[:8],
         "commit": subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
         "save": f"fo4sf_test_{digest[:8]}", "plugin_index": a.plugin_index, "hours": [[0, 24]], "tests": tests}
    os.makedirs(a.out, exist_ok=True)
    save_atomic(os.path.join(a.out, "queue.json"), q)
    counts = {}
    for t in tests:
        counts[t["kind"]] = counts.get(t["kind"], 0) + 1
    print(f"{len(tests)} tests in {len(cells)} cells on build {q['build_id']}: {counts}")


def plan_terrain(a):
    """Terrain experiment 1 (docs/terrain/architecture.md on PR #57): three test worldspaces, each with its own BTD
    (flat ground at 10 m and pads at known heights); which height the player lands on shows whether the plugin's
    worldspace loads its BTD at all, through the record or by name, and at what height scale."""
    staging = os.path.abspath(a.staging)
    esm = os.path.join(staging, "FO4Port.esm")
    tests = []
    # later experiments ship their own plan.json: [{"coc": "<cell editor id>", "label": "...", "drop_z": 80,
    #   "points": [{"label", "x", "y", "expect"}], "beyond": {"x", "y"} (optional)}]  (metres, world coordinates)
    own = load(os.path.join(a.exp_dir, "plan.json"))
    for n, w in enumerate(own or []):
        if not str(w.get("coc", "")).replace("_", "").isalnum():
            sys.exit(f"bad coc name in plan.json: {w.get('coc')!r}")
        travel = w.get("travel") or ""
        # cow did not move the player in Starfield (control run 2026-10-11: still in the interior); moveto to a
        # reference inside the target worldspace does
        if travel and not re.fullmatch(r"(coc|cow) [A-Za-z0-9_]+( -?\d+ -?\d+)?|player\.moveto [0-9A-Fa-f]{8}", travel):
            sys.exit(f"bad travel command in plan.json: {travel!r}")
        tests.append({"id": f"{n:04d}_terrain_{w['coc']}", "kind": "terrain", "cell": "", "ref": w["coc"],
                      "model": w.get("label", ""), "world_coc": w["coc"], "travel": travel,
                      **{k: w[k] for k in ("spawn_local", "anchor", "drop_above_spawn", "settle_ms", "z_ref") if w.get(k)},
                      "drop_z": float(w.get("drop_z", 80.0)),
                      "points": w["points"], "beyond": w.get("beyond") or {"x": w["points"][0]["x"] + 500.0,
                                                                           "y": w["points"][0]["y"]}})
    exp = load(os.path.join(a.exp_dir, "expected.json")) if not own else {}
    worlds = [] if own else [("FO4TX_W01Spawn", "FO4TX_World01.btd", "record and name"),
                             ("FO4TX_W02Spawn", "FO4TX_Shared02.btd", "record path only"),
                             ("FO4TX_W03Spawn", "FO4TX_World03.btd", "name only")]
    for n, (coc, btd, how) in enumerate(worlds):
        e = exp[btd]
        pts = [{"label": "ground", "x": -60.0, "y": -60.0, "expect": e["ground"]},
               {"label": "padA", "x": 30.0, "y": 30.0, "expect": e["padA_x20-40_y20-40"]},
               {"label": "padB", "x": 70.0, "y": 30.0, "expect": e["padB_x60-80_y20-40"]},
               {"label": "pitC", "x": 30.0, "y": 70.0, "expect": e["pitC_x20-40_y60-80"]}]
        if n == 0:                                        # pad edge: 1 m inside / outside pad A
            pts += [{"label": "padA_edge_in", "x": 39.0, "y": 30.0, "expect": e["padA_x20-40_y20-40"]},
                    {"label": "padA_edge_out", "x": 41.0, "y": 30.0, "expect": e["ground"]}]
        tests.append({"id": f"{n:04d}_terrain_{coc}", "kind": "terrain", "cell": "", "ref": coc, "model": btd,
                      "world_coc": coc, "btd_lookup": how, "drop_z": 80.0, "points": pts,
                      "beyond": {"x": 300.0, "y": 0.0}})
    digest = sha256(esm)
    q = {"created": now(), "staging": staging, "plugin_sha256": digest, "build_id": digest[:8],
         "commit": subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
         "save": f"fo4sf_test_{digest[:8]}", "plugin_index": a.plugin_index, "hours": [[0, 24]],
         "launch_cell": a.launch_cell, "experiment": os.path.abspath(a.exp_dir),
         "tests": [dict(t, fresh=True) if a.fresh else t for t in (tests[:a.only] if a.only else tests)]}
    if a.plugins:                                         # installed by the runner right before it launches the game
        q["pre_launch"] = [sys.executable, os.path.join(HERE, "exp_install.py"), "install", "--exp-dir",
                           os.path.abspath(a.exp_dir), "--starfield", a.starfield, "--plugins", a.plugins, "--pack"]
    os.makedirs(a.out, exist_ok=True)
    save_atomic(os.path.join(a.out, "queue.json"), q)
    print(f"{len(q['tests'])} terrain tests (experiment {a.exp_dir}) on build {q['build_id']}")


def _vec(v, sizes, what):
    if not isinstance(v, (list, tuple)):
        sys.exit(f"bad {what} in plan.json (want a list of numbers): {v!r}")
    try:
        out = [float(x) for x in v]
    except (TypeError, ValueError):
        sys.exit(f"bad {what} in plan.json: {v!r}")
    if len(out) not in sizes or not all(math.isfinite(x) and abs(x) < 1e6 for x in out):
        sys.exit(f"bad {what} in plan.json: {v!r}")
    return out


def _num(w, key, default, lo, hi):
    try:
        v = float(w.get(key, default))
    except (TypeError, ValueError):
        sys.exit(f"bad {key} in plan.json: {w.get(key)!r}")
    if not (math.isfinite(v) and lo <= v <= hi):
        sys.exit(f"{key} in plan.json must be within {lo}..{hi}: {v}")
    return v


def npc_test(n, w):
    """One npc_nav test from a plan.json entry. Everything qstep.ps1 types into the console comes from here and is
    validated (cell editor id, hex form ids, whitelisted methods and probes, finite numbers); qstep checks it again."""
    label = str(w.get("label") or f"npc{n}")
    unknown = sorted(set(w) - NPC_PLAN_KEYS)
    if unknown:
        sys.exit(f"{label}: unknown plan.json keys {unknown} (known: {sorted(NPC_PLAN_KEYS)})")
    travel = str(w.get("travel") or "")
    if not re.fullmatch(r"coc [A-Za-z0-9_]+", travel):     # coc <cell editor id> is the travel that works (2026-10-11)
        sys.exit(f"bad travel in plan.json (coc <cell editor id>): {travel!r}")
    npc = str(w.get("npc") or "")
    if not re.fullmatch(r"[0-9A-Fa-f]{8}", npc):
        sys.exit(f"bad npc form id in plan.json: {npc!r}")
    method = str(w.get("method") or "ptr_player")
    if method not in NPC_METHODS:
        sys.exit(f"unknown method {method!r}; known: {sorted(NPC_METHODS)}")
    pre = w.get("pre") or []
    if not isinstance(pre, list) or any(c not in NPC_PRE for c in pre):
        sys.exit(f"pre must be a list of commands among {NPC_PRE}: {pre!r}")
    a, b = _vec(w.get("a"), (3,), "a"), _vec(w.get("b"), (3,), "b")
    reads = sorted(set(_vec(w.get("reads_s", [0, 3, 8, 15, 30]), range(1, 13), "reads_s")))
    if reads[0] < 0 or reads[-1] > 300 or reads[-1] <= 0:
        sys.exit(f"reads_s must be 1..12 times within 0..300 s, the last > 0: {reads}")
    safe = re.sub(r"[^A-Za-z0-9_]", "_", label)[:40]
    t = {"id": f"{n:04d}_npc_nav_{safe}", "kind": "npc_nav", "cell": "", "ref": label, "model": label,
         "travel": travel, "npc": npc.upper(), "method": method, "pre": pre, "a": a, "b": b,
         "heading_a": heading_to(a, b), "heading_b": heading_to(b, a), "reads_s": reads,
         "radius": _num(w, "radius", 2.5, 0.1, 50), "min_progress": _num(w, "min_progress", 5.0, 0.1, 500),
         "nomove": _num(w, "nomove", 0.5, 0.05, 10), "spawn_tol": _num(w, "spawn_tol", 3.0, 0.5, 20),
         "target_tol": _num(w, "target_tol", 3.0, 0.5, 20), "fell_m": _num(w, "fell_m", 3.0, 0.5, 100),
         "drop": _num(w, "drop", 0.5, 0, 200), "settle_ms": int(_num(w, "settle_ms", 1500, 0, 30000)),
         "pre_wait_ms": int(_num(w, "pre_wait_ms", 5000, 0, 60000)), "max_speed": _num(w, "max_speed", 8.0, 1, 50),
         # the console closed this long after placeatme before the handle is read (the game runs: N0_base 2026-10-11
         # read PickLastRef with the console still open and the selection stayed on a static), and how close to the
         # player at A the ref PickLastRef names must stand (placeatme puts it at the player's feet)
         "spawn_wait_ms": int(_num(w, "spawn_wait_ms", 2000, 0, 30000)), "handle_tol": _num(w, "handle_tol", 2.0, 0.5, 10),
         "path_line": bool(w.get("path_line", False)), "control": bool(w.get("control", False)),
         "baseline": method == "none"}
    if w.get("fresh"):
        # relaunch the runner's game before this test (as plan-terrain --fresh): a merged planet world arrives
        # erratically on a repeated coc (2026-10-11), so every test of one starts from a new launch
        t["fresh"] = True
    if t["baseline"] and t["control"]:
        sys.exit(f"{label}: a baseline (method none) gates the controls and cannot be one itself")
    if w.get("control_npc"):
        # the actor whose control (same method) and baseline gate this test's FAIL, when it differs from the test's own
        # actor: a converted actor in the vanilla control cell is judged against the vanilla actor's control there
        cn = str(w["control_npc"])
        if not re.fullmatch(r"[0-9A-Fa-f]{8}", cn):
            sys.exit(f"bad control_npc form id in plan.json: {cn!r}")
        if t["control"] or t["baseline"]:
            sys.exit(f"{label}: control_npc gates a test's FAIL; a control or a baseline is never gated")
        t["control_npc"] = cn.upper()
    if w.get("anchor"):
        if not isinstance(w["anchor"], dict):
            sys.exit(f"bad anchor in plan.json (want {{\"ref\": \"<8 hex>\", \"local\": [x, y, z]}}): {w['anchor']!r}")
        ref = str(w["anchor"].get("ref") or "")
        if not re.fullmatch(r"[0-9A-Fa-f]{8}", ref):
            sys.exit(f"bad anchor ref in plan.json: {ref!r}")
        t["anchor"] = {"ref": ref.upper(), "local": _vec(w["anchor"].get("local"), (3,), "anchor local")}
    if w.get("spawn_local"):
        t["spawn_local"] = _vec(w["spawn_local"], (2, 3), "spawn_local")
    if w.get("requires"):
        # {"queue": "<queue dir>", "test": "<test id or label>", "verdict": "PASS" | "FAIL" | "DECIDED"}; without
        # "queue" the test is in this queue (plan_npc fills in the queue dir and the id)
        r = w["requires"]
        ok = isinstance(r, dict) and (("queue" not in r) or (isinstance(r["queue"], str) and bool(r["queue"]))) and \
            not (set(r) - {"queue", "test", "verdict"}) and \
            bool(re.fullmatch(r"[A-Za-z0-9_]+", str(r.get("test") or ""))) and r.get("verdict", "PASS") in REQUIRE_VERDICTS
        if not ok:
            sys.exit(f"bad requires in plan.json (want {{\"queue\": \"<queue dir>\" (none: this queue), \"test\": "
                     f"\"<test id or label>\", \"verdict\": one of {REQUIRE_VERDICTS}}}): {r!r}")
        t["requires"] = {"queue": os.path.abspath(r["queue"]) if r.get("queue") else "", "test": r["test"],
                         "verdict": r.get("verdict", "PASS")}
    for k in ("expect", "basis"):
        if w.get(k):
            t[k] = str(w[k])
    return t


def precondition(test):
    """None when the test may run, else why not: a test with "requires" runs only when that test of another queue has
    the required verdict (N1 walks on terrain exp2b only once exp2b's terrain test passed: its heights are ours)."""
    r = test.get("requires")
    if not r:
        return None
    done = (load(os.path.join(r["queue"], "state.json"), {}) or {}).get("done", {})
    got = done.get(r["test"])
    want = ("PASS", "FAIL") if r["verdict"] == "DECIDED" else (r["verdict"],)
    if got and got.get("verdict") in want:
        return None
    have = f"{got.get('verdict')} {got.get('class')}" if got else "no result"
    return f"needs {r['test']} in {r['queue']} to be {' or '.join(want)}, it is {have}: not run"


def installed_world(q):
    """The staged folder a queue installs before launching (its pre_launch exp_install --exp-dir), else the experiment
    folder it was planned from."""
    pre = q.get("pre_launch") or []
    if "--exp-dir" in pre and pre.index("--exp-dir") + 1 < len(pre):
        return pre[pre.index("--exp-dir") + 1]
    return q.get("experiment") or ""


def plan_npc(a):
    """NPC navigation runs (PR #61 3.3): N0 the control in a vanilla navmeshed cell, N1 the same actor and commands in
    a test worldspace. plan.json: a list of tests (or {"tests": [...]}), see npc_test and docs/ai/test-queue.md."""
    staging = os.path.abspath(a.staging)
    esm = os.path.join(staging, "FO4Port.esm")
    if not os.path.exists(esm):
        sys.exit(f"no FO4Port.esm in {staging}: the runner pins and launches a build")
    src = load(os.path.join(a.exp_dir, "plan.json"))
    if isinstance(src, dict):
        src = src.get("tests")
    if not src:
        sys.exit(f"no tests in {os.path.join(a.exp_dir, 'plan.json')}")
    if not isinstance(src, list) or not all(isinstance(w, dict) for w in src):
        sys.exit("plan.json must be a list of test objects (or {\"tests\": [...]})")
    # baselines (method none) first, then controls: the others are judged against them
    src = sorted(src, key=lambda w: (w.get("method") != "none", not w.get("control")))
    tests = [npc_test(n, w) for n, w in enumerate(src)]
    digest = sha256(esm)
    q = {"created": now(), "staging": staging, "plugin_sha256": digest, "build_id": digest[:8],
         "commit": subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
         "save": f"fo4sf_test_{digest[:8]}", "plugin_index": a.plugin_index, "hours": [[0, 24]],
         "launch_cell": a.launch_cell, "experiment": os.path.abspath(a.exp_dir),
         "tests": [dict(t, fresh=True) if getattr(a, "fresh", False) else t for t in (tests[:a.only] if a.only else tests)]}
    if a.control_queue:
        q["control_queue"] = os.path.abspath(a.control_queue)
    world = os.path.abspath(a.install_exp or a.exp_dir) if a.plugins else ""
    if a.plugins:                                         # e.g. the terrain experiment whose world N1 walks on
        q["pre_launch"] = [sys.executable, os.path.join(HERE, "exp_install.py"), "install", "--exp-dir",
                           world, "--starfield", a.starfield, "--plugins", a.plugins, "--pack"]
    out = os.path.abspath(a.out)
    for t in q["tests"]:
        r = t.get("requires")
        if not r:
            continue
        if not r["queue"]:
            # a test of this queue (by id or label), run before it: N2's tests wait for N2a_base's spawn
            req = [x for x in q["tests"] if r["test"] in (x["id"], x["ref"])]
            if len(req) != 1 or req[0]["id"] == t["id"]:
                sys.exit(f"{t['id']}: requires {r['test']}, which is not exactly one other test of this queue")
            if (req[0].get("requires") or {}).get("queue") in ("", out):
                sys.exit(f"{t['id']}: requires {r['test']}, which itself waits for a test of this queue (one level only)")
            t["requires"] = dict(r, queue=out, test=req[0]["id"])
            continue
        # a test of another queue must have measured the very world this queue installs (same staged folder, packed
        # by the same exp_install.py at install time), or its PASS says nothing about this run
        rq = load(os.path.join(r["queue"], "queue.json"))
        ids = [x.get("id") for x in (rq or {}).get("tests", []) if r["test"] in (x.get("id"), x.get("ref"))]
        if len(ids) != 1:
            sys.exit(f"{t['id']}: requires {r['test']} in {r['queue']}, which is not planned there")
        t["requires"] = dict(r, test=ids[0])
        if os.path.normcase(installed_world(rq)) != os.path.normcase(world):
            sys.exit(f"{t['id']}: {r['queue']} tested {installed_world(rq)!r}, but this queue installs {world!r} "
                     f"(--install-exp)")
    os.makedirs(a.out, exist_ok=True)
    save_atomic(os.path.join(a.out, "queue.json"), q)
    print(f"{len(q['tests'])} npc_nav tests ({sum(t['control'] for t in q['tests'])} control) from {a.exp_dir} "
          f"on build {q['build_id']}")


# ------------------------------------------------------------------------------------------------------------ judging
def judge(test, obs, out_dir):
    """(verdict, reason class, detail) from raw observations. Missing observations are INCONCLUSIVE."""
    if not obs:
        return "INCONCLUSIVE", "NOOBS", "no observations written"
    if obs.get("stopped"):
        return "INCONCLUSIVE", "STOPPED", obs["stopped"]

    def shot_ok(name):
        return bool(name) and os.path.exists(os.path.join(out_dir, name))

    kind = test["kind"]
    if kind in ("stairs", "door"):
        res = obs.get("result")
        if not res:
            return "INCONCLUSIVE", "NORESULT", "route_run wrote no result"
        if not obs.get("shots"):
            return "INCONCLUSIVE", "NOSHOT", "no screenshot"
        route = load(test["routes_file"])["routes"][test["route_index"]]
        if res.get("skipped"):
            return "INCONCLUSIVE", "UNREAD", res["skipped"]
        v, why = route_eval.judge(route, res)
        if v == "PASS":
            return "PASS", "PASS", why
        if v in ("UNREAD", "UNOPENED"):
            return "INCONCLUSIVE", v, why
        return "FAIL", v, why
    if kind == "fall":
        end = parse3(obs.get("end_read"))
        if end is None or not shot_ok(obs.get("shot")):
            return "INCONCLUSIVE", "UNREAD", "no position read or no screenshot"
        x, y, z = test["point"]
        dxy, dz = math.hypot(end[0] - x, end[1] - y), end[2] - z
        if dxy > 1.0:
            return "INCONCLUSIVE", "MOVED", f"ended {dxy:.1f} m away"
        if dz < -3:
            return "FAIL", "FALL", f"dropped {-dz:.1f} m below the floor"
        if dz < -0.6:
            return "INCONCLUSIVE", "LOWER", f"landed {-dz:.1f} m below (lower floor or a hole)"
        if dz > 1.2:
            return "INCONCLUSIVE", "HELD", f"stopped {dz:.1f} m above"
        return "PASS", "PASS", f"landed {dz:+.2f} m"
    if kind == "movable":
        b, a_ = parse3(obs.get("item_before")), parse3(obs.get("item_after"))
        pe = parse3(obs.get("player_end"))
        if b is None or a_ is None or pe is None or not (shot_ok(obs.get("shot_before")) and shot_ok(obs.get("shot_after"))):
            return "INCONCLUSIVE", "UNREAD", "item or player position not read, or a screenshot missing"
        moved = math.dist(b, a_)
        if a_[2] < b[2] - 1.0:
            return "FAIL", "ITEMFELL", f"item dropped {b[2] - a_[2]:.1f} m"
        if moved >= 0.05:
            return "PASS", "PASS", f"item moved {moved:.2f} m"
        reach = math.hypot(pe[0] - b[0], pe[1] - b[1])
        if reach <= 1.0:
            return "FAIL", "NOTMOVED", f"player reached it ({reach:.2f} m) but it moved {moved:.3f} m"
        return "INCONCLUSIVE", "MISSED", f"player ended {reach:.2f} m from the item"
    if kind == "travel":
        st = parse3(obs.get("start_read"))
        if st is None or math.hypot(st[0] - test["start"][0], st[1] - test["start"][1]) > 3:
            return "INCONCLUSIVE", "UNREAD", "start not reached or not read"
        if not obs.get("prompt"):
            return "FAIL", "NOPROMPT", "no activation prompt at the load door"
        end = parse3(obs.get("end_read"))
        if end is None or not shot_ok(obs.get("shot")):
            return "INCONCLUSIVE", "UNREAD", "arrival not read or no screenshot"
        d = math.dist(end, test["arrival"])
        if d <= 4.0:
            return "PASS", "PASS", f"arrived {d:.1f} m from the arrival point in {test['dest_cell']}, load {obs.get('load_s')} s"
        if math.dist(end, st) <= 3.0:
            return "FAIL", "NOTRAVEL", "pressed E at the door but stayed in place"
        return "INCONCLUSIVE", "ELSEWHERE", f"ended {d:.1f} m from the arrival point"
    if kind == "terrain":
        # heights measured by dropping the player onto known terrain pads (terrain experiment 1, PR #57)
        pts = obs.get("points") or []
        reads = [(p, parse3(o.get("read")) if isinstance(o, dict) else None) for p, o in zip(test["points"], pts)]
        if len(reads) < len(test["points"]) or any(r is None for _, r in reads) or not shot_ok(obs.get("shot")):
            got = "; ".join(f"{p['label']} {r[2]:.2f} (want {p['expect']})" for p, r in reads if r is not None)
            return "INCONCLUSIVE", "UNREAD", f"{len([r for _, r in reads if r])} of {len(test['points'])} heights read"                 + (f": {got}" if got else "")
        parts, worst, fell = [], 0.0, False
        off = list(obs.get("offset") or [0.0, 0.0]) + [0.0]
        ox, oy, oz = off[0], off[1], off[2]                 # overlay merge offset (anchor or spawn), z included
        zref = test.get("z_ref")
        if zref:                                            # Z offset from a reference probe (e.g. "ground"): only
            for p, r in reads:                              # height differences between points are compared
                if p["label"] == zref:
                    oz = r[2] - p["expect"]
        for p, r in reads:
            parts.append(f"{p['label']} {r[2] - oz:.2f} (want {p['expect']})")
            off = math.hypot(r[0] - p["x"] - ox, r[1] - p["y"] - oy)
            if off > 2.0:
                return "INCONCLUSIVE", "MOVED", f"{p['label']}: ended {off:.1f} m away"
            worst = max(worst, abs(r[2] - oz - p["expect"]))
            fell = fell or r[2] - oz < p["expect"] - 50     # falling through reads hundreds of metres below
        detail = "; ".join(parts) + (f" (offset {ox:.1f}, {oy:.1f}, {oz:.2f} from {obs.get('offset_from')})"
                                     if obs.get("offset") else "")
        if fell:
            return "FAIL", "NOTERRAIN", "fell through where terrain should be: " + detail
        if worst > 0.5:
            return "FAIL", "HEIGHTS", f"off by up to {worst:.2f} m: " + detail
        return "PASS", "PASS", detail
    if kind == "npc_nav":
        v, cls, detail = judge_npc(test, obs, shot_ok)
        return v, cls, detail + (f" [expected {test['expect']}]" if test.get("expect") else "")
    return "INCONCLUSIVE", "KIND", f"unknown kind {kind}"


def judge_npc(test, obs, shot_ok):
    """npc_nav (PR #61 3.4). The actor spawns at A, the player (the walk target) stands at B. Positions are in the
    worldspace's own frame plus the measured offset (anchor or spawn), like terrain points. The spawn counts only when
    qstep.ps1 confirmed the handle (PickLastRef's id, GetSelf naming no other ref, GetIsID 1, at the player at A); only
    reads whose selection the game confirmed (prid <id>, GetIsID 1 in the same console session) and that have a
    screenshot count. A baseline (method none, no command) is judged the other way round: PASS when the actor did NOT
    come to B."""
    if (test.get("anchor") or test.get("spawn_local")) and not obs.get("offset"):
        why = obs.get("offset_missing") or "anchor / arrival read failed"
        return "INCONCLUSIVE", "ANCHOR", f"frame offset not measured ({why}): nothing spawned"
    off = (list(obs.get("offset") or []) + [0.0, 0.0, 0.0])[:3]
    A = [test["a"][k] + off[k] for k in range(3)]
    B = [test["b"][k] + off[k] for k in range(3)]
    sp = obs.get("spawn") or {}
    if sp.get("isid") != 1 or sp.get("confirmed") is False:
        why = sp.get("why") or f"GetIsID {sp.get('isid')}"
        return "INCONCLUSIVE", "SPAWN", (f"spawned actor not confirmed ({why}; PickLastRef {sp.get('ref')}, GetSelf "
                                         f"{sp.get('self')}, OCR {str(sp.get('ocr'))[:80]!r})")
    ps = parse3(sp.get("read"))
    p0 = parse3((obs.get("t0") or {}).get("read")) or ps
    if p0 is None:
        return "INCONCLUSIVE", "UNREAD", "actor position not read before the command"
    ds = math.hypot((ps or p0)[0] - A[0], (ps or p0)[1] - A[1])
    if ds > test.get("spawn_tol", 3.0):
        return "INCONCLUSIVE", "SPAWN", f"actor stood {ds:.1f} m from A before the command"
    if not obs.get("command_sent"):
        return "INCONCLUSIVE", "HANDLE", "the actor's console handle was lost before the walk command"
    tb = parse3(obs.get("player_b"))
    if tb is None or math.hypot(tb[0] - B[0], tb[1] - B[1]) > test.get("target_tol", 3.0):
        return "INCONCLUSIVE", "TARGET", f"the player (the walk target) was not read at B: {obs.get('player_b')!r}"
    good = []
    for s in obs.get("samples") or []:
        p = parse3(s.get("read")) if isinstance(s, dict) else None
        if p is not None and s.get("isid") == 1 and shot_ok(s.get("shot")):
            good.append((s, p))
    want = len([x for x in test["reads_s"] if x > 0])
    if not good:
        return "INCONCLUSIVE", "UNREAD", f"no confirmed position read after the command (0 of {want})"

    def dist(p):
        return math.hypot(p[0] - tb[0], p[1] - tb[1])
    d0, dend = dist(p0), dist(good[-1][1])
    # the spawn read: the actor at the player's feet at A, before the player went to B. t0 comes later (the player
    # teleported to B, settled settle_ms, and two console sessions read it), so an actor that came for the player on
    # its own (a hostile one) may have closed most of the gap by t0: the approach is also measured from here
    dS = dist(ps) if ps is not None else d0
    early = dS - d0                                     # towards B between the spawn read and t0
    dmin = min(dist(p) for _, p in good)
    moved = max(math.hypot(p[0] - p0[0], p[1] - p0[1]) for _, p in good)
    path, last = 0.0, p0
    for _, p in good:
        path, last = path + math.hypot(p[0] - last[0], p[1] - last[1]), p
    stats = (f"spawn d {dS:.1f} m, d0 {d0:.1f} m, min d {dmin:.1f} m, end d {dend:.1f} m, moved {moved:.1f} m, path "
             f"{path:.1f} m, {len(good)}/{want} reads, last at {good[-1][0].get('t_game')} s ({test['method']})")
    zfloor = min(p0[2], tb[2]) - test.get("fell_m", 3.0)
    low = min(p[2] for _, p in good)
    if low < zfloor:
        return "FAIL", "FELL", f"actor dropped to z {low:.1f} (start {p0[2]:.1f}): world, not navigation; {stats}"
    # faster than max_speed between two reads, with 2 s of slack on the game clock: a warp (teammate catch-up, a
    # script moveto), not a walk. The slack makes this a check for gross jumps only; an arrival already at the first
    # read is not taken as a walk either (below).
    vmax, prev_t, prev_p = test.get("max_speed", 8.0), 0.0, p0
    for smp, p in good:
        t = smp.get("t_game")
        if not isinstance(t, (int, float)):
            continue
        seg = math.hypot(p[0] - prev_p[0], p[1] - prev_p[1])
        if seg > vmax * (max(t - prev_t, 0.0) + 2.0):
            return ("INCONCLUSIVE", "WARP", f"{seg:.1f} m between t {prev_t:g} and {t:g} s, faster than {vmax:g} m/s: "
                    f"not a walk; {stats}")
        prev_t, prev_p = t, p
    if test.get("baseline"):
        prog = max(d0 - dend, dS - dend, early)
        came = min(dmin, d0) <= test["radius"] or prog >= test["min_progress"]
        if came:
            when = (f" ({early:.1f} m of it before the first read, between the spawn read and t0)"
                    if early >= test["min_progress"] or (d0 <= test["radius"] < dS) else "")
            return ("FAIL", "WANDER", f"came {prog:.1f} m towards B without a command{when}: a control PASS of this "
                    f"actor here says nothing about the command; {stats}")
        if len(good) < want:
            return "INCONCLUSIVE", "UNREAD", f"{len(good)} of {want} reads confirmed: {stats}"
        return "PASS", "PASS", f"stayed away from B without a command: {stats}"
    if early >= test["min_progress"] or (d0 <= test["radius"] < dS):
        # it came for the player before the command was typed (between the spawn read and t0): whatever follows is
        # not the command's doing alone (a hostile actor), so neither a PASS nor a FAIL of the command
        return ("INCONCLUSIVE", "PRECOMMAND", f"came {early:.1f} m towards B before the command (spawn read to t0): "
                f"the walk after it is not the command's alone; {stats}")
    if dist(good[0][1]) <= test["radius"]:
        # at B by the first read: no position on the way was seen, so a warp to the player is not ruled out
        return ("INCONCLUSIVE", "EARLY", f"already at B at the first read ({good[0][0].get('t_game')} s): the walk "
                f"itself was not observed (add an earlier read); {stats}")
    if dmin <= test["radius"]:
        return "PASS", "PASS", f"arrived within {test['radius']} m of B: {stats}"
    if d0 - dend >= test["min_progress"]:
        return "PASS", "PASS", f"walked {d0 - dend:.1f} m towards B: {stats}"
    if len(good) < want:
        return "INCONCLUSIVE", "UNREAD", f"{len(good)} of {want} reads confirmed: {stats}"
    if moved < test.get("nomove", 0.5):
        return "FAIL", "NONAV", f"spawned and commanded, never moved: {stats}"
    return "FAIL", "STALLED", f"moved but did not reach B: {stats}"


def own_baseline_note(qdir, q, test):
    """Whether a commanded walk that passed can be credited to the command: the same actor's baseline (no command) in
    this queue or the control queue stayed away (yes) or came to B on its own (no). PASS stays PASS either way (the walk
    was observed); the note says what it shows. No baseline of the actor: no note."""
    came, stayed = [], []
    for d in [qdir] + ([q["control_queue"]] if q.get("control_queue") else []):
        qq = load(os.path.join(d, "queue.json"), {}) or {}
        done = (load(os.path.join(d, "state.json"), {}) or {}).get("done", {})
        for c in qq.get("tests", []):
            if c.get("kind") == "npc_nav" and c.get("baseline") and c.get("npc") == test.get("npc"):
                r = done.get(c["id"]) or {}
                if r.get("class") == "WANDER":
                    came.append(c["id"])
                elif r.get("verdict") == "PASS":
                    stayed.append(c["id"])
    if came:                                            # any baseline that came voids the credit
        return f" (not credited to the command: baseline {came[0]} came to B without one)"
    if stayed:
        return f" (baseline {stayed[0]} stayed away without a command: the command moved it)"
    return ""


def control_gate(qdir, q, test, verdict, cls, detail):
    """A FAIL of a non-control npc_nav test only means something when the control (same method, same actor, in a vanilla
    navmeshed cell: N0) passed, in this queue or in q['control_queue'], and, when a baseline of that actor is planned
    there (method none: no command), the baseline passed too (the actor did not come to B on its own, so the control's
    PASS was the command's doing). Otherwise: INCONCLUSIVE CONTROL with the raw verdict kept in the detail; the runner
    keeps the raw verdict and the report applies the gate again (a control that passes later still counts). PASS
    needs no control (the walk was observed); it gets a note on whether the actor's own baseline credits the command
    (own_baseline_note). No control configured: unchanged. A test with "control_npc" is gated by
    that actor's control and baseline instead of its own (a converted actor judged against the vanilla one)."""
    if test.get("kind") == "npc_nav" and not test.get("baseline") and verdict == "PASS":
        return verdict, cls, detail + own_baseline_note(qdir, q, test)
    if test.get("kind") != "npc_nav" or test.get("control") or test.get("baseline") or verdict != "FAIL":
        return verdict, cls, detail
    gate_npc = test.get("control_npc") or test.get("npc")
    sources = [qdir] + ([q["control_queue"]] if q.get("control_queue") else [])
    configured, ctrl, base = bool(q.get("control_queue")), [], []
    for d in sources:
        qq = load(os.path.join(d, "queue.json"), {}) or {}
        done = (load(os.path.join(d, "state.json"), {}) or {}).get("done", {})
        for c in qq.get("tests", []):
            if c.get("kind") != "npc_nav":
                continue
            configured = configured or bool(c.get("control"))
            if c.get("npc") != gate_npc:
                continue
            if c.get("control") and c.get("method") == test.get("method"):
                ctrl.append((c["id"], done.get(c["id"])))
            elif c.get("baseline"):
                base.append((c["id"], done.get(c["id"])))
    if not configured:
        return verdict, cls, detail
    raw = f"raw verdict {verdict} {cls}: {detail}"

    def why(group):
        if any(r and r.get("class") == "WANDER" for _, r in group):
            return "did not pass (the actor came to B without a command)"
        return "did not pass" if any(r for _, r in group) else "has no result"
    passed = [i for i, r in ctrl if r and r.get("verdict") == "PASS"]
    if not passed:
        return "INCONCLUSIVE", "CONTROL", f"control ({test.get('method')}, {gate_npc}) {why(ctrl)}; {raw}"
    if base:
        bpass = [i for i, r in base if r and r.get("verdict") == "PASS"]
        if not bpass:
            return ("INCONCLUSIVE", "CONTROL",
                    f"control {passed[0]} passed but the baseline ({gate_npc}, no command) {why(base)}; {raw}")
        return verdict, cls, detail + f" (control {passed[0]} and baseline {bpass[0]} passed)"
    return verdict, cls, detail + f" (control {passed[0]} passed)"


# ----------------------------------------------------------------------------------------------------------- controls
class Controls:
    """The owner's PC-use controls and the game process (Windows). Replaced by a fake in the unit tests."""
    state_dir = os.environ.get("FO4_AI_TEAM_STATE") or os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
                                                                      "fo4-ai-team", "state")

    def __init__(self, queue_dir):
        self.queue_dir = queue_dir
        # shared by the queues of one chain (same parent folder): input sent by the previous queue is not the owner's
        self.tick_file = os.path.join(os.path.dirname(os.path.abspath(queue_dir)), "last_sent_tick.txt")
        self.last_sent_tick = None
        try:
            self.last_sent_tick = int(open(self.tick_file).read().strip())
        except (OSError, ValueError):
            pass

    def stop_file(self):
        for p in (os.path.join(self.queue_dir, "STOP"), os.path.join(self.state_dir, "testqueue.STOP")):
            if os.path.exists(p):
                return p
        return None

    def guardian_mode(self):
        db = os.path.join(self.state_dir, "guardian.db")
        if not os.path.exists(db):
            return "running"
        try:
            c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
            r = c.execute("SELECT value FROM control WHERE key='mode'").fetchone()
            c.close()
            return r[0] if r else "running"
        except sqlite3.Error:
            return "unreadable"                          # fail closed: treated as a stop

    @staticmethod
    def _last_input_tick():
        class LII(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint32)]
        li = LII(ctypes.sizeof(LII), 0)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li))
        return li.dwTime

    @staticmethod
    def _tick():
        return ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF

    def idle_s(self):
        return ((self._tick() - self._last_input_tick()) & 0xFFFFFFFF) / 1000.0

    def mark_sent(self):
        """Call right after a subprocess that sent input returned: later input is the owner's."""
        self.last_sent_tick = self._tick()
        try:
            with open(self.tick_file, "w") as f:
                f.write(str(self.last_sent_tick))
        except OSError:
            pass

    def foreign_input(self):
        if self.last_sent_tick is None:
            return False
        d = (self._last_input_tick() - self.last_sent_tick) & 0xFFFFFFFF
        d = d - (1 << 32) if d >= 1 << 31 else d                 # signed: input before our last step is negative
        return d > 500

    @staticmethod
    def foreground_pid():
        u = ctypes.windll.user32
        pid = ctypes.c_uint32()
        u.GetWindowThreadProcessId(u.GetForegroundWindow(), ctypes.byref(pid))
        return pid.value

    def game_in_front(self):
        """The runner's game owns the foreground window (compared by process id, not by name)."""
        gp = self.game_pid()
        return bool(gp) and self.foreground_pid() == gp

    @staticmethod
    def game_pid():
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Starfield.exe", "/FO", "CSV", "/NH"], capture_output=True, text=True)
        for line in r.stdout.splitlines():
            parts = [p.strip('"') for p in line.split('","')]
            if parts and parts[0].lower() == "starfield.exe":
                return int(parts[1])
        return None

    @staticmethod
    def owned_pid():
        p = os.path.join(HERE, "cycle_pid.txt")
        try:
            return int(open(p).read().strip())
        except (OSError, ValueError):
            return None

    def close_game(self):
        """Close the runner's OWN game (cycle.ps1's pid) so the next test starts from a fresh launch."""
        gp = self.game_pid()
        if not gp or gp != self.owned_pid():
            return False
        subprocess.run(PS[:-1] + ["-Command", f"$g = Get-Process -Id {gp} -ErrorAction SilentlyContinue; if ($g) {{ "
                                  "$g.CloseMainWindow() | Out-Null; Start-Sleep 10; $g.Refresh(); "
                                  f"if (-not $g.HasExited) {{ Stop-Process -Id {gp} -Force -Confirm:$false }} }}"],
                       capture_output=True)
        time.sleep(5)
        return True

    @staticmethod
    def refocus_game():
        """Bring the runner's own game window to the front (only used after --min-idle of owner inactivity)."""
        r = subprocess.run(PS + [os.path.join(HERE, "refocus.ps1")], capture_output=True, text=True)
        return r.returncode == 0


def blocked_reason(ctl, q, launching=False, min_idle=900):
    p = ctl.stop_file()
    if p:
        return f"STOP file {p}"
    mode = ctl.guardian_mode()
    if mode != "running":
        return f"Resource Guardian mode {mode}"
    h = time.localtime().tm_hour
    if not any(lo <= h < hi for lo, hi in q.get("hours", [[0, 24]])):
        return f"outside the allowed hours {q.get('hours')}"
    # the PC counts as idle when nobody gave input since the runner's own last input (relaunch after a crash, the
    # next queue of a chain); otherwise it needs min_idle seconds without any input
    if launching and ctl.idle_s() < min_idle and (ctl.last_sent_tick is None or ctl.foreign_input()):
        return f"owner active (idle {ctl.idle_s():.0f} s < {min_idle} s): not launching the game"
    if ctl.foreign_input():
        return "owner input detected (keyboard/mouse the runner did not send)"
    return None


# -------------------------------------------------------------------------------------------------------------- runner
# npc_nav step costs, worst case (typing about 0.24 s a character, +0.08 s shifted, a PowerShell start per Send)
NPC_SESSION_S = 45      # one console session: open, ClearConsole + ~60 characters, waits, OCR at up to 4 thresholds
NPC_READ_S = 75         # Read-Pos: up to 3 readpos.ps1 runs
NPC_REMOVE_S = 300      # kept for the removal (qstep.ps1 $reserve): Select-Npc (2), PickLastRef again (3), disable (1)


def step_timeout(test):
    """Seconds one qstep.ps1 may take before the runner kills it. Every confirmed npc_nav read is one console session
    (ClearConsole, prid <id>, GetIsID, getpos x/y/z, OCR), two when the first is not read (Select-Npc). The spawn is
    four sessions (placeatme; plr; prid + GetSelf; GetIsID + getpos) around spawn_wait_ms of game time."""
    if test.get("kind") == "terrain":
        # a terrain drop takes about a minute per point (teleport, fall, OCR read): 300 s cut experiment 1 off
        return 150 + 90 * (len(test.get("points", [])) + 1)
    if test.get("kind") == "npc_nav":
        reads = test.get("reads_s") or [0]
        n = len([x for x in reads if x > 0])
        pre = len(test.get("pre") or []) * (test.get("pre_wait_ms", 0) / 1000 + 30)
        fixed = (120                                      # coc, the HUD back (up to 90 s), 3 s
                 + 5 * NPC_READ_S + 12 + NPC_READ_S        # the arrival until it settles (5 reads), the anchor
                 + 2 * (30 + test.get("settle_ms", 0) / 1000 + NPC_READ_S)   # the player to A and to B
                 + pre + 4 * NPC_SESSION_S + 10            # probes, the spawn: placeatme, plr, GetSelf, GetIsID + getpos
                 + test.get("spawn_wait_ms", 2000) / 1000
                 + 3 * NPC_SESSION_S + NPC_REMOVE_S)       # t = 0 (Select-Npc) and the command; the removal
        return int(fixed + n * (2 * NPC_SESSION_S + 10) + max(reads))
    return 300


class Runner:
    def __init__(self, qdir, a, ctl=None, step=None):
        self.qdir, self.a = qdir, a
        self.q = load(os.path.join(qdir, "queue.json"))
        self.state_p = os.path.join(qdir, "state.json")
        self.state = load(self.state_p, {"done": {}, "attempts": {}, "relaunches": 0, "crashes": 0, "status": "new"})
        self.ctl = ctl or Controls(qdir)
        self.step = step or self._step
        self.cell = None                                  # cell the player is verified to be in
        self.session = False                              # game set up by this run (save loaded, god mode)
        self.log_p = os.path.join(qdir, "run.log")

    def log(self, msg):
        line = f"{now()} {msg}"
        print(line, flush=True)
        with open(self.log_p, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def checkpoint(self, status=None):
        if status:
            self.state["status"] = status
        self.state["updated"] = now()
        save_atomic(self.state_p, self.state)

    def _ps(self, script, args, timeout, steal=False):
        # steal=True only for cycle.ps1's launch, which runs after --min-idle of owner inactivity: the new game window
        # has to come to the front once. Every other step refuses to take the foreground (input.ps1 exits 2 instead).
        env = dict(os.environ, FO4SF_NO_FOCUS_STEAL="0" if steal else "1", LEGACY="1")
        env.setdefault("FO4SF_PYTHON", sys.executable)
        try:
            r = subprocess.run(PS + [os.path.join(HERE, script)] + args, capture_output=True, text=True, timeout=timeout, env=env)
            code, out = r.returncode, (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            code, out = 124, "timeout"
        self.ctl.mark_sent()
        return code, out

    def _step(self, test, out_dir):
        spec = os.path.join(out_dir, "spec.json")
        timeout = step_timeout(test)
        # npc_nav: the step stops sampling in time to remove its actor before this timeout would kill it
        save_atomic(spec, dict(test, budget_s=timeout - 60) if test.get("kind") == "npc_nav" else test)
        code, out = self._ps("qstep.ps1", ["-Spec", spec, "-Out", out_dir, "-PluginIndex", self.q["plugin_index"]],
                             timeout)
        with open(os.path.join(out_dir, "step.log"), "w", encoding="utf-8") as f:
            f.write(out)
        return code

    def pinned_ok(self):
        esm = os.path.join(self.q["staging"], "FO4Port.esm")
        return os.path.exists(esm) and sha256(esm) == self.q["plugin_sha256"]

    def ensure_game(self, cell):
        """True when the player is verified in `cell` of the runner's own game; launches or travels when needed."""
        gp = self.ctl.game_pid()
        if gp and gp != self.ctl.owned_pid():
            self.log("a Starfield the runner did not start is running (the owner's session): stopping")
            return "stop"
        # a test with no cell (terrain experiment) travels on its own: launch into the queue's launch cell, no coc
        launch = cell or self.q.get("launch_cell") or "Vault111Cryo"
        cell_json = os.path.join(self.q["staging"], launch + ".json")
        if not gp:
            fresh = getattr(self, "fresh_launch", False)
            self.fresh_launch = False
            if not fresh and self.state["relaunches"] >= self.a.max_relaunch:
                self.log(f"game not running and {self.state['relaunches']} relaunches used: stopping")
                return "stop"
            why = blocked_reason(self.ctl, self.q, launching=True, min_idle=self.a.min_idle)
            if why:
                return why
            if not self.pinned_ok():
                self.log("staging FO4Port.esm no longer matches the pinned build: stopping")
                return "stop"
            pre = self.q.get("pre_launch")
            if pre:                                       # e.g. install a staged experiment only when the game starts
                r = subprocess.run(pre, capture_output=True, text=True, cwd=REPO)
                self.log(f"pre-launch exit {r.returncode}: {(r.stdout + r.stderr).strip()[-200:]}")
                if r.returncode != 0:
                    return "stop"
            if fresh:
                self.state["fresh_launches"] = self.state.get("fresh_launches", 0) + 1
            else:
                self.state["relaunches"] += 1              # crash or first launch: bounded by --max-relaunch
            self.checkpoint()
            self.log(f"launching the pinned build {self.q['build_id']} into {launch}")
            code, out = self._ps("cycle.ps1", ["-Staging", self.q["staging"], "-Starfield", self.a.starfield,
                                               "-Cell", f"FO4Port_{launch}", "-CellJson", cell_json,
                                               "-Shot", os.path.join(self.qdir, "cycle.png")], 900, steal=True)
            self.log(f"cycle exit {code}: {out.strip().splitlines()[-1] if out.strip() else ''}")
            if code != 0:
                return "stop" if code in (2, 3, 5, 6) else "retry"
            self.session, self.cell = False, launch
        if not self.session:
            self.setup_session(launch)
        if cell and self.cell != cell:
            code, out = self._ps("coc.ps1", ["-Cell", cell, "-CellJson", cell_json], 180)
            self.log(f"coc {cell}: exit {code} {out.strip().splitlines()[-1] if out.strip() else ''}")
            if code == 2:
                return "owner"
            if code != 0:
                self.cell = None
                return "nocell"
            self.cell = cell
        return None

    def setup_session(self, cell):
        """Dedicated test save (created once per pinned build), then god mode, so falls never kill the player."""
        saves = os.path.join(os.path.expanduser("~"), "OneDrive", "Documents", "My Games", "Starfield", "Saves")
        if not os.path.isdir(saves):
            saves = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Saves")
        name = self.q["save"]
        sd = os.path.join(self.qdir, "_session")
        os.makedirs(sd, exist_ok=True)
        if glob.glob(os.path.join(saves, f"*{name}*")):
            code = self.step({"kind": "load", "name": name}, sd)
            self.log(f"loaded the dedicated save {name}: exit {code}")
            self.cell = None                              # the save's cell; coc follows
        else:
            code = self.step({"kind": "save", "name": name}, sd)
            found = glob.glob(os.path.join(saves, f"*{name}*"))
            self.log(f"created the dedicated save {name}: exit {code}, file {'found' if found else 'NOT found'}")
            self.state["save_file"] = bool(found)
        code = self.step({"kind": "godmode"}, sd)
        obs = load(os.path.join(sd, "obs.json"), {})
        self.log(f"god mode: {obs.get('god')} (reply {obs.get('reply', '')[:60]!r})")
        self.session = True

    def recover(self):
        """The console could not be opened (menu, overlay or popup over the HUD). Only when nobody touched the PC since
        the runner's last input: up to three Escapes, each followed by a HUD check (qstep kind recover). True: HUD back."""
        if self.ctl.foreign_input() or not self.ctl.game_in_front():
            return False
        d = os.path.join(self.qdir, "_session", "recover")
        os.makedirs(d, exist_ok=True)
        code = self.step({"kind": "recover"}, d)
        obs = load(os.path.join(d, "obs.json"), {})
        self.log(f"recover: exit {code}, HUD before {obs.get('hud_before')}, escapes {obs.get('escapes')}, after {obs.get('hud_after')}")
        self.cell = None
        return code == 0 and obs.get("hud_after") is True

    def wait_or_stop(self, why):
        """Owner present: stop, or with --wait-for-idle wait until the PC is idle again (STOP/Guardian still end it)."""
        if not self.a.wait_for_idle or not why.startswith("owner"):
            return False
        self.log(f"{why}: waiting for {self.a.min_idle} s of inactivity")
        self.checkpoint("waiting for idle")
        refocus_fails = 0
        while True:
            time.sleep(30)
            hard = blocked_reason(self.ctl, self.q)
            if hard and not hard.startswith("owner"):
                self.log(f"{hard}: stopping while waiting")
                return False
            if time.time() > self.deadline:
                return False
            if self.ctl.idle_s() >= self.a.min_idle:
                self.ctl.last_sent_tick = None
                if self.ctl.game_pid() and not self.ctl.game_in_front():
                    if not self.a.refocus:
                        self.log("idle again but the game is not in front and --refocus is off: stopping")
                        return False
                    if not self.ctl.refocus_game():
                        refocus_fails += 1
                        self.log(f"idle, but the game could not be brought to the front ({refocus_fails})")
                        if refocus_fails >= 3:
                            return False
                        continue
                self.log("idle again: continuing")
                return True

    def run(self):
        a = self.a
        self.deadline = time.time() + a.max_hours * 3600
        tests = self.q["tests"]
        pending = [t for t in tests if t["id"] not in self.state["done"]]
        self.log(f"run: {len(pending)} of {len(tests)} tests pending on build {self.q['build_id']} (commit {self.q['commit'][:8]})")
        self.checkpoint("running")
        ran = 0
        waits, max_waits = {}, len(tests) * max(a.max_attempts, 1) + 1
        self.qdir_abs = os.path.abspath(self.qdir)
        for i, t in enumerate(pending):
            if ran >= a.max_tests or time.time() > self.deadline:
                self.log("test or time budget used up")
                break
            pre = precondition(t)
            r = t.get("requires") or {}
            same = bool(r) and os.path.normcase(os.path.abspath(r["queue"])) == os.path.normcase(self.qdir_abs)
            if pre and same and any(x["id"] == r["test"] for x in pending[i + 1:]) and waits.get(t["id"], 0) < max_waits:
                # the required test is in this queue and still to be run or retried in this run: wait for it (bounded,
                # although plan-npc refuses a chain of same-queue requires)
                waits[t["id"]] = waits.get(t["id"], 0) + 1
                self.log(f"{t['id']}: waits for {r['test']} (no final result yet)")
                pending.append(t)
                continue
            if pre and a.dry_run:                         # nothing ran, so nothing is final: say what it waits for
                self.log(f"dry run: {t['id']} would run only once {r['test']} is {r['verdict']}" if same
                         else f"dry run: {t['id']} would not run: {pre}")
                continue
            if pre:                                       # checked before the game is launched for it: final
                rec = {"id": t["id"], "kind": t["kind"], "cell": t["cell"], "ref": t["ref"], "model": t.get("model", ""),
                       "attempt": 0, "verdict": "INCONCLUSIVE", "class": "PRECONDITION", "detail": pre, "exit": None,
                       "dir": "", "t": now()}
                if t.get("expect"):
                    rec["expect"] = t["expect"]
                with open(os.path.join(self.qdir, "results.jsonl"), "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec) + "\n")
                self.state["done"][t["id"]] = {"verdict": "INCONCLUSIVE", "class": "PRECONDITION", "attempts": 0}
                self.checkpoint()
                self.log(f"{t['id']}: INCONCLUSIVE PRECONDITION {pre}")
                continue
            while True:
                why = blocked_reason(self.ctl, self.q)
                if not why and self.ctl.game_pid() and not self.ctl.game_in_front():
                    # no keyboard/mouse input since the runner's last step: a popup took the focus (the Steam
                    # overlay hint did, 2026-10-11), not the owner, so take the game back at once
                    popup = self.ctl.last_sent_tick is not None and not self.ctl.foreign_input()
                    if popup and self.a.refocus and self.ctl.refocus_game():
                        self.log("focus lost without owner input (popup): game brought back to the front")
                        self.ctl.mark_sent()
                        continue
                    why = "owner switched to another window"
                if not why:
                    break
                if not self.wait_or_stop(why):
                    self.log(f"stopped: {why}")
                    self.checkpoint(f"stopped: {why}")
                    return 3
            if a.dry_run:
                self.log(f"dry run: would run {t['id']}")
                ran += 1
                continue
            if t.get("fresh") and getattr(self, "game_used", False) and self.ctl.game_pid():
                # every arrival after the first in an already merged planet world was erratic (2026-10-11 terrain
                # retries fell through): a "fresh" test starts from a new launch
                self.log("fresh test: closing the runner's game for a new launch")
                self.ctl.close_game()
                self.session, self.cell, self.game_used = False, None, False
                self.fresh_launch = True                  # an intended relaunch: not counted against --max-relaunch
            g = self.ensure_game(t["cell"])
            if g in ("stop",) or (g and g.startswith(("owner", "STOP", "Resource", "outside"))):
                if g != "stop" and self.wait_or_stop(g):
                    g = self.ensure_game(t["cell"])
                if g:
                    self.log(f"stopped: {g}")
                    self.checkpoint(f"stopped: {g}")
                    return 3
            br = self.state.setdefault("breaker", {})
            if br.get(t["kind"], {}).get("open"):
                rec = {"id": t["id"], "kind": t["kind"], "cell": t["cell"], "ref": t["ref"], "model": t.get("model", ""),
                       "attempt": 0, "verdict": "INCONCLUSIVE", "class": "BREAKER",
                       "detail": f"not run: the first {BREAKER} {t['kind']} tests were all inconclusive", "exit": None,
                       "dir": "", "t": now()}
                with open(os.path.join(self.qdir, "results.jsonl"), "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec) + "\n")
                self.state["done"][t["id"]] = {"verdict": "INCONCLUSIVE", "class": "BREAKER", "attempts": 0}
                self.checkpoint()
                continue
            n = self.state["attempts"].get(t["id"], 0) + 1
            self.state["attempts"][t["id"]] = n
            out_dir = os.path.join(self.qdir, "tests", t["id"], f"a{n}")
            os.makedirs(out_dir, exist_ok=True)
            if g in ("nocell", "retry"):
                verdict, cls, detail, code = "INCONCLUSIVE", "NOCELL", f"cell {t['cell']} not reached ({g})", None
                if g == "nocell" and not self.recover():
                    self.log("stopped: the game is not in a playable state (menu or overlay)")
                    self.checkpoint("stopped: menu or overlay")
                    return 3
            else:
                pid_before = self.ctl.game_pid()
                code = self.step(t, out_dir)
                self.game_used = True
                if code == 2:                             # the owner took the foreground mid-step: not an attempt
                    self.state["attempts"][t["id"]] = n - 1
                    self.cell = None
                    if self.wait_or_stop("owner switched windows during a step"):
                        pending.append(t)                 # run it again later in this run
                        continue
                    self.log("stopped: owner took over during a step")
                    self.checkpoint("stopped: owner took over during a step")
                    return 3
                if code == 3 and not self.recover():      # a menu or overlay hides the HUD and Escape did not clear it
                    self.state["attempts"][t["id"]] = n - 1
                    self.log("stopped: the game is not in a playable state (menu or overlay)")
                    self.checkpoint("stopped: menu or overlay")
                    return 3
                if pid_before and not self.ctl.game_pid():
                    self.state["crashes"] += 1
                    self.session, self.cell = False, None
                    verdict, cls, detail = "INCONCLUSIVE", "CRASH", "the game exited during this test"
                else:
                    raw = judge(t, load(os.path.join(out_dir, "obs.json")), out_dir)
                    verdict, cls, detail = control_gate(self.qdir, self.q, t, *raw)
                    if not t["cell"]:
                        self.cell = None                  # the test travelled (terrain experiment world)
                    if cls in ("STOPPED", "NOOBS", "NORESULT"):
                        self.cell = None                  # unknown game state: re-verify the cell next time
            rec = {"id": t["id"], "kind": t["kind"], "cell": t["cell"], "ref": t["ref"], "model": t.get("model", ""),
                   "attempt": n, "verdict": verdict, "class": cls, "detail": detail, "exit": code, "dir": out_dir, "t": now()}
            if t.get("expect"):
                rec["expect"] = t["expect"]
            if cls == "CONTROL":
                rec["raw"] = list(raw)                    # the report gates it again (write_report)
            with open(os.path.join(self.qdir, "results.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            final = verdict != "INCONCLUSIVE" or n >= a.max_attempts or cls in FINAL_INCONCLUSIVE
            if final:
                self.state["done"][t["id"]] = {"verdict": verdict, "class": cls, "attempts": n}
                if cls == "CONTROL":
                    self.state["done"][t["id"]]["raw"] = list(raw)
            k = br.setdefault(t["kind"], {"inconclusive_run": 0, "decided": 0, "open": False})
            if verdict == "INCONCLUSIVE" and cls not in ("CRASH", "NOCELL") + FINAL_INCONCLUSIVE:
                k["inconclusive_run"] += 1
            elif verdict != "INCONCLUSIVE":
                k["inconclusive_run"], k["decided"] = 0, k["decided"] + 1
            if k["decided"] == 0 and k["inconclusive_run"] >= BREAKER:
                k["open"] = True                          # this kind's step is broken here: stop spending hours on it
                self.log(f"circuit breaker: {BREAKER} {t['kind']} tests in a row inconclusive, none decided: "
                         f"the rest of this kind is skipped")
            self.checkpoint()
            ran += 1
            self.log(f"{t['id']}: {verdict} {cls} {detail}")
            if not final:
                pending.append(t)                         # retried at the end of the queue
        left = len([t for t in tests if t["id"] not in self.state["done"]])
        self.checkpoint("finished" if left == 0 else f"paused ({left} left)")
        self.log(f"run ends: {left} tests left")
        write_report(self.qdir)
        return 0


# -------------------------------------------------------------------------------------------------------------- report
def write_report(qdir):
    q = load(os.path.join(qdir, "queue.json"))
    rows = []
    if os.path.exists(os.path.join(qdir, "results.jsonl")):
        with open(os.path.join(qdir, "results.jsonl"), encoding="utf-8") as f:
            rows = [json.loads(x) for x in f]
    final = {}
    for r in rows:                                        # last attempt per test counts
        final[r["id"]] = r
    # npc_nav control gate again, on the raw verdict: a control that passed after this test ran (retried at the end
    # of its queue, or its queue ran later) now counts
    by_id = {t["id"]: t for t in q["tests"]}
    for k, r in list(final.items()):
        if r.get("class") == "CONTROL" and r.get("raw") and k in by_id:
            v, c, d = control_gate(qdir, q, by_id[k], *r["raw"])
            if c != "CONTROL":
                final[k] = dict(r, verdict=v, detail=d + " (gated again at report time)", **{"class": c})
    tally = {}
    for r in final.values():
        tally.setdefault(r["kind"], {}).setdefault(r["verdict"], 0)
        tally[r["kind"]][r["verdict"]] += 1
    groups = {}
    for r in final.values():
        if r["verdict"] == "PASS":
            continue
        key = (r["kind"], r["class"], os.path.basename((r.get("model") or "").replace("\\", "/")))
        g = groups.setdefault(key, {"kind": r["kind"], "class": r["class"], "model": key[2], "verdict": r["verdict"],
                                    "count": 0, "cells": set(), "examples": []})
        g["count"] += 1
        g["cells"].add(r["cell"])
        if len(g["examples"]) < 3:
            g["examples"].append({"id": r["id"], "detail": r["detail"], "dir": r["dir"]})
    for g in groups.values():
        w = SEVERITY.get((g["kind"], g["class"]), SEVERITY.get(("any", g["class"]), 1 if g["verdict"] == "INCONCLUSIVE" else 2))
        g["score"] = w * g["count"] if g["verdict"] == "FAIL" else 0.5 * g["count"]
        g["cells"] = sorted(g["cells"])
    ranked = sorted(groups.values(), key=lambda g: (-(g["verdict"] == "FAIL"), -g["score"], -g["count"]))
    pending = len(q["tests"]) - len(load(os.path.join(qdir, "state.json"), {"done": {}})["done"])
    # hypotheses written down before the run (npc_nav plan.json "expect"): what came out
    expectations = []
    for t in q["tests"]:
        if t.get("expect"):
            r = final.get(t["id"])
            got = None if r is None else ("PASS" if r["verdict"] == "PASS" else f"{r['verdict']} {r['class']}")
            expectations.append({"id": t["id"], "expect": t["expect"], "result": got, "basis": t.get("basis", "")})
    rep = {"build_id": q["build_id"], "commit": q["commit"], "tests": len(q["tests"]), "results": len(final),
           "pending": pending, "tally": tally, "ranked": ranked}
    if expectations:
        rep["expectations"] = expectations
    save_atomic(os.path.join(qdir, "report.json"), rep)
    lines = [f"# Test queue report: build {q['build_id']} (commit {q['commit'][:8]})", "",
             f"{len(final)} of {len(q['tests'])} tests have a result, {pending} pending. Generated {now()}.", "",
             "| kind | PASS | FAIL | INCONCLUSIVE |", "|---|---|---|---|"]
    for k in KINDS + EXTRA_KINDS:
        if k in tally:
            lines.append(f"| {k} | {tally[k].get('PASS', 0)} | {tally[k].get('FAIL', 0)} | {tally[k].get('INCONCLUSIVE', 0)} |")
    lines += ["", "## Ranked problems (FAIL first, by severity x count)", "",
              "| # | verdict | kind | class | model | count | cells | example |", "|---|---|---|---|---|---|---|---|"]
    for n, g in enumerate(ranked, 1):
        ex = g["examples"][0]
        lines.append(f"| {n} | {g['verdict']} | {g['kind']} | {g['class']} | {g['model']} | {g['count']} | "
                     f"{', '.join(g['cells'])} | {ex['id']}: {ex['detail']} |")
    if expectations:
        lines += ["", "## Expectations written before the run", "",
                  "| test | expected | result | as expected | basis |", "|---|---|---|---|---|"]
        for e in expectations:
            same = "" if e["result"] is None else ("yes" if e["result"] == e["expect"] else "no")
            lines.append(f"| {e['id']} | {e['expect']} | {e['result'] or 'pending'} | {same} | {e['basis']} |")
    with open(os.path.join(qdir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return rep


# ---------------------------------------------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--staging", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--cells", default="")
    p.add_argument("--kinds", default=",".join(KINDS))
    p.add_argument("--per-cell", type=int, default=12)
    p.add_argument("--plugin-index", default="02")
    p.add_argument("--per-kind", type=int, default=0, help="keep the first N tests of each kind per cell (0 = all)")
    pt = sub.add_parser("plan-terrain")
    pt.add_argument("--staging", required=True)
    pt.add_argument("--exp-dir", required=True)
    pt.add_argument("--out", required=True)
    pt.add_argument("--launch-cell", default="Vault111Cryo")
    pt.add_argument("--plugin-index", default="02")
    pt.add_argument("--starfield", default=r"D:\SteamLibrary\steamapps\common\Starfield")
    pt.add_argument("--plugins", default="", help="experiment plugins to activate before launch (exp_install.py)")
    pt.add_argument("--only", type=int, default=0, help="keep the first N worlds")
    pt.add_argument("--fresh", action="store_true", help="relaunch the game before every test (clean arrivals)")
    pn = sub.add_parser("plan-npc", help="NPC navigation tests (npc_nav) from <exp-dir>\\plan.json")
    pn.add_argument("--staging", required=True)
    pn.add_argument("--exp-dir", required=True, help="folder with plan.json")
    pn.add_argument("--out", required=True)
    pn.add_argument("--launch-cell", default="Vault111Cryo")
    pn.add_argument("--plugin-index", default="02")
    pn.add_argument("--starfield", default=r"D:\SteamLibrary\steamapps\common\Starfield")
    pn.add_argument("--plugins", default="", help="experiment plugins to activate before launch (exp_install.py)")
    pn.add_argument("--install-exp", default="", help="experiment folder those plugins come from (default --exp-dir)")
    pn.add_argument("--control-queue", default="", help="queue whose control tests gate this queue's FAIL verdicts")
    pn.add_argument("--only", type=int, default=0, help="keep the first N tests")
    pn.add_argument("--fresh", action="store_true", help="relaunch the game before every test (a test's own "
                                                         "\"fresh\": true in plan.json does the same for that test)")
    r = sub.add_parser("run")
    r.add_argument("--queue", required=True)
    r.add_argument("--starfield", default=r"D:\SteamLibrary\steamapps\common\Starfield")
    r.add_argument("--max-tests", type=int, default=10 ** 6)
    r.add_argument("--max-hours", type=float, default=8.0)
    r.add_argument("--min-idle", type=int, default=900)
    r.add_argument("--max-attempts", type=int, default=2)
    r.add_argument("--max-relaunch", type=int, default=3)
    r.add_argument("--wait-for-idle", action="store_true")
    r.add_argument("--refocus", action="store_true")
    r.add_argument("--dry-run", action="store_true")
    for name in ("report", "status"):
        s = sub.add_parser(name)
        s.add_argument("--queue", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "plan":
        return plan(a)
    if a.cmd == "plan-terrain":
        return plan_terrain(a)
    if a.cmd == "plan-npc":
        return plan_npc(a)
    if a.cmd == "run":
        return Runner(a.queue, a).run()
    if a.cmd == "report":
        rep = write_report(a.queue)
        print(open(os.path.join(a.queue, "report.md"), encoding="utf-8").read())
        return 0 if rep else 1
    st = load(os.path.join(a.queue, "state.json"), {})
    q = load(os.path.join(a.queue, "queue.json"), {"tests": []})
    print(f"status {st.get('status')}, {len(st.get('done', {}))} of {len(q['tests'])} done, updated {st.get('updated')}, "
          f"relaunches {st.get('relaunches')}, crashes {st.get('crashes')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
