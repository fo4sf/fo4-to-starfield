"""Queued in-game test runner: plan a batch of tests on ONE pinned build, run them unattended without any AI calls,
checkpoint after every test, resume later, and rank the problems found.

usage:
  python testqueue.py plan   --staging <build dir> --out <queue dir> [--cells A,B] [--kinds stairs,door,fall,movable,travel]
                             [--per-cell 12] [--per-kind N] [--plugin-index 02]
  python testqueue.py plan-terrain --staging <build dir> --exp-dir <experiment> --out <queue dir> [--plugins a.esm,b.esm]
  python testqueue.py plan-npc --staging <build dir> --exp-dir <dir with plan.json> --out <queue dir>
                             [--install-exp <experiment> --plugins a.esm,b.esm] [--control-queue <N0 queue dir>]
                             [--fresh]
  plan-terrain and plan-npc also take [--time-of-day <local hour>] [--time-methods slt,slt_galaxy,cgf]
                             [--weather <form id>] [--need-daylight] for every test (plan.json fields of the same names
                             per test; docs/ai/test-queue.md "Time of day and weather"); plan.json may also carry
                             console_pre / console_post: whitelisted console lines (console_plan.py) typed before the
                             travel / after the arrival. queue.json "needs" lists the runner features such a queue
                             uses (runner_features.py): a runner without them refuses it, also an older one (the
                             queue's pre_launch runs the runner's own exp_install.py with --needs)
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
import console_plan  # noqa: E402
import route_eval  # noqa: E402
import runner_features  # noqa: E402
import sky_light  # noqa: E402

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
# inconclusive for a reason a retry cannot change. NIGHT (need_daylight, the run did not read as daylight) is NOT
# final: arrivals of the same test differ between attempts (exp1d 2026-10-11: a1 fell into a pit, sky 7.3, a2 in the
# open, 131.0), so a retry can read differently; it does not count towards the circuit breaker either (the step works)
FINAL_INCONCLUSIVE = ("CONTROL", "PRECONDITION")
NO_BREAKER = ("CRASH", "NOCELL", "NIGHT")

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


def _plan_fail(msg):
    sys.exit(f"{msg} (plan.json or the plan command line)")


def light_cli(a):
    """Time-of-day / weather fields given on the plan-terrain / plan-npc command line: for every test, winning over the
    same fields of plan.json (validated together with them, per test, in with_light)."""
    raw = {}
    if getattr(a, "time_of_day", None) is not None:
        raw["time_of_day"] = a.time_of_day
    if getattr(a, "time_methods", ""):
        raw["time_methods"] = [m.strip() for m in a.time_methods.split(",") if m.strip()]
    if getattr(a, "weather", ""):
        raw["weather"] = a.weather
    if getattr(a, "need_daylight", False):
        raw["need_daylight"] = True
    return raw


def with_light(t, w, cli):
    """A planned test plus the light fields of its plan.json entry `w` and of the command line, validated (only what
    sky_light.light_fields returns ever reaches the console)."""
    merged = {k: w[k] for k in sky_light.LIGHT_KEYS if isinstance(w, dict) and k in w}
    merged.update(cli)
    return dict(t, **sky_light.light_fields(merged, _plan_fail))


def with_extras(t, w, cli):
    """with_light plus the whitelisted console_pre / console_post commands of the plan.json entry (console_plan.py)."""
    return dict(with_light(t, w, cli), **console_plan.console_fields(w, _plan_fail))


# ----------------------------------------------------------------------------------------------------------- planning
def plan_cell(cell, staging, kinds, per_cell, plugin_index, formids, items, all_refs, routes_prefix="routes_"):
    """Tests for one exported cell, in the owner's priority order: stairs, falls, doors (both sides), movable, travel."""
    name = cell["cell"]
    out = []
    routes_file = os.path.join(staging, f"{routes_prefix}{name}.json")   # e.g. routesfull_ = routes.py --max 400
    routes = load(routes_file, {}).get("routes", [])
    if "stairs" in kinds:
        for k, r in enumerate(routes):
            if r["kind"] == "stairs":
                out.append({"kind": "stairs", "cell": name, "ref": r["ref"], "model": r["model"],
                            "routes_file": routes_file, "route_index": k})
    if "fall" in kinds:
        # the point count is part of the name: a bigger batch must not reuse a smaller batch's picks
        pts_file = os.path.join(staging, f"probe_{name}.txt" if per_cell == 10 else f"probe_{name}_{per_cell}.txt")
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
        tests += plan_cell(c, staging, kinds, a.per_cell, a.plugin_index, formids, items, all_refs, a.routes_prefix)
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
    cli = light_cli(a)
    # later experiments ship their own plan.json: [{"coc": "<cell editor id>", "label": "...", "drop_z": 80,
    #   "points": [{"label", "x", "y", "expect"}], "beyond": {"x", "y"} (optional)}]  (metres, world coordinates)
    # plus the optional time-of-day / weather fields (sky_light.LIGHT_KEYS)
    own = load(os.path.join(a.exp_dir, "plan.json"))
    for n, w in enumerate(own or []):
        if not str(w.get("coc", "")).replace("_", "").isalnum():
            sys.exit(f"bad coc name in plan.json: {w.get('coc')!r}")
        travel = w.get("travel") or ""
        # cow did not move the player in Starfield (control run 2026-10-11: still in the interior); moveto to a
        # reference inside the target worldspace does
        if travel and not re.fullmatch(r"(coc|cow) [A-Za-z0-9_]+( -?\d+ -?\d+)?|player\.moveto [0-9A-Fa-f]{8}", travel):
            sys.exit(f"bad travel command in plan.json: {travel!r}")
        tests.append(with_extras({"id": f"{n:04d}_terrain_{w['coc']}", "kind": "terrain", "cell": "",
                                  "ref": w["coc"], "model": w.get("label", ""), "world_coc": w["coc"], "travel": travel,
                                  **{k: w[k] for k in ("spawn_local", "anchor", "drop_above_spawn", "settle_ms",
                                                       "z_ref", "hop_m", "hop_wait_ms") if w.get(k)},
                                  "drop_z": float(w.get("drop_z", 80.0)),
                                  "points": w["points"], "beyond": w.get("beyond") or {"x": w["points"][0]["x"] + 500.0,
                                                                                       "y": w["points"][0]["y"]}},
                                 w, cli))
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
        tests.append(with_light({"id": f"{n:04d}_terrain_{coc}", "kind": "terrain", "cell": "", "ref": coc,
                                 "model": btd, "world_coc": coc, "btd_lookup": how, "drop_z": 80.0, "points": pts,
                                 "beyond": {"x": 300.0, "y": 0.0}}, {}, cli))
    digest = sha256(esm)
    q = {"created": now(), "staging": staging, "plugin_sha256": digest, "build_id": digest[:8],
         "commit": subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
         "save": f"fo4sf_test_{digest[:8]}", "plugin_index": a.plugin_index, "hours": [[0, 24]],
         "launch_cell": a.launch_cell, "experiment": os.path.abspath(a.exp_dir),
         "tests": [dict(t, fresh=True) if a.fresh else t for t in (tests[:a.only] if a.only else tests)]}
    # installed by the runner right before it launches the game; needs: the runner features its tests use
    q.update(queue_extras(q["tests"], a, a.exp_dir))
    os.makedirs(a.out, exist_ok=True)
    save_atomic(os.path.join(a.out, "queue.json"), q)
    print(f"{len(q['tests'])} terrain tests (experiment {a.exp_dir}) on build {q['build_id']}"
          + (f", needs runner features {', '.join(q['needs'])}" if q.get("needs") else ""))


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
        r = w["requires"]
        ok = isinstance(r, dict) and isinstance(r.get("queue"), str) and bool(r["queue"]) and \
            bool(re.fullmatch(r"[A-Za-z0-9_]+", str(r.get("test") or ""))) and r.get("verdict", "PASS") in ("PASS", "FAIL")
        if not ok:
            sys.exit(f"bad requires in plan.json (want {{\"queue\": \"<queue dir>\", \"test\": \"<test id>\"}}): {r!r}")
        t["requires"] = {"queue": os.path.abspath(r["queue"]), "test": r["test"], "verdict": r.get("verdict", "PASS")}
    for k in ("expect", "basis"):
        if w.get(k):
            t[k] = str(w[k])
    return with_extras(t, w, {})   # time of day, weather, console commands (before the travel, after the arrival)


def precondition(test):
    """None when the test may run, else why not: a test with "requires" runs only when that test of another queue has
    the required verdict (N1 walks on terrain exp2b only once exp2b's terrain test passed: its heights are ours)."""
    r = test.get("requires")
    if not r:
        return None
    done = (load(os.path.join(r["queue"], "state.json"), {}) or {}).get("done", {})
    got = done.get(r["test"])
    if got and got.get("verdict") == r["verdict"]:
        return None
    have = f"{got.get('verdict')} {got.get('class')}" if got else "no result"
    return f"needs {r['test']} in {r['queue']} to be {r['verdict']}, it is {have}: not run"


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
    cli = light_cli(a)
    tests = [with_extras(npc_test(n, w), w, cli) for n, w in enumerate(src)]
    digest = sha256(esm)
    q = {"created": now(), "staging": staging, "plugin_sha256": digest, "build_id": digest[:8],
         "commit": subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
         "save": f"fo4sf_test_{digest[:8]}", "plugin_index": a.plugin_index, "hours": [[0, 24]],
         "launch_cell": a.launch_cell, "experiment": os.path.abspath(a.exp_dir),
         "tests": [dict(t, fresh=True) if getattr(a, "fresh", False) else t for t in (tests[:a.only] if a.only else tests)]}
    if a.control_queue:
        q["control_queue"] = os.path.abspath(a.control_queue)
    world = os.path.abspath(a.install_exp or a.exp_dir) if a.plugins else ""
    q.update(queue_extras(q["tests"], a, world))           # e.g. the terrain experiment whose world N1 walks on
    for t in q["tests"]:
        # a required test must have measured the very world this queue installs (same staged folder, packed by the
        # same exp_install.py at install time), or its PASS says nothing about this run
        r = t.get("requires")
        if not r:
            continue
        rq = load(os.path.join(r["queue"], "queue.json"))
        if not rq or r["test"] not in {x.get("id") for x in rq.get("tests", [])}:
            sys.exit(f"{t['id']}: requires {r['test']} in {r['queue']}, which is not planned there")
        if os.path.normcase(rq.get("experiment") or "") != os.path.normcase(world):
            sys.exit(f"{t['id']}: {r['queue']} tested {rq.get('experiment')!r}, but this queue installs {world!r} "
                     f"(--install-exp)")
    os.makedirs(a.out, exist_ok=True)
    save_atomic(os.path.join(a.out, "queue.json"), q)
    print(f"{len(q['tests'])} npc_nav tests ({sum(t['control'] for t in q['tests'])} control) from {a.exp_dir} "
          f"on build {q['build_id']}" + (f", needs runner features {', '.join(q['needs'])}" if q.get("needs") else ""))


# ------------------------------------------------------------------------------------------------------------ judging
def light_of(test, obs):
    """The light of a test that asked for a time of day or a weather (sky_light.verdict: the arrival camera before and
    after the commands, and for terrain the probe shots, whose corner median decides), else None."""
    obs = obs or {}
    probes = obs.get("points") if test.get("kind") == "terrain" else None
    return sky_light.verdict(test, obs.get("light"), probes if isinstance(probes, list) else None)


def judge(test, obs, out_dir):
    """(verdict, reason class, detail) from raw observations. Missing observations are INCONCLUSIVE.
    A test that asked for a time of day or a weather gets its light appended to the detail ("[light: ...]", e.g.
    "no effect: night" when the commands left a dark sky as it was, "already daylight at the arrival: the time commands
    were not tested"). With need_daylight, a PASS whose run did not read as daylight (terrain: the probe shots' corner
    median, else the arrival camera after the commands) becomes INCONCLUSIVE NIGHT, or INCONCLUSIVE LIGHT when nothing
    was read; both are retried (another arrival can read differently). A FAIL stays a FAIL."""
    v, cls, detail = judge_kind(test, obs, out_dir)
    con, _ = console_plan.summary(test, obs)              # console_pre / console_post replies: shown, never judged
    if con and obs:
        detail = f"{detail} {con}"
    lt = light_of(test, obs)
    if lt is None or not obs or obs.get("stopped"):
        return v, cls, detail
    detail = f"{detail} [light: {lt['detail']}]"
    if test.get("need_daylight") and v == "PASS" and lt["light"] != "daylight":
        return "INCONCLUSIVE", "LIGHT" if lt["light"] == "unread" else "NIGHT", f"not in daylight: {detail}"
    return v, cls, detail


def judge_kind(test, obs, out_dir):
    """judge() for one kind, without the light reading."""
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
    dmin = min(dist(p) for _, p in good)
    moved = max(math.hypot(p[0] - p0[0], p[1] - p0[1]) for _, p in good)
    path, last = 0.0, p0
    for _, p in good:
        path, last = path + math.hypot(p[0] - last[0], p[1] - last[1]), p
    stats = (f"d0 {d0:.1f} m, min d {dmin:.1f} m, end d {dend:.1f} m, moved {moved:.1f} m, path {path:.1f} m, "
             f"{len(good)}/{want} reads, last at {good[-1][0].get('t_game')} s ({test['method']})")
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
        came = dmin <= test["radius"] or d0 - dend >= test["min_progress"]
        if came:
            return ("FAIL", "WANDER", f"came {d0 - dend:.1f} m towards B without a command: a control PASS of this actor "
                    f"here says nothing about the command; {stats}")
        if len(good) < want:
            return "INCONCLUSIVE", "UNREAD", f"{len(good)} of {want} reads confirmed: {stats}"
        return "PASS", "PASS", f"stayed away from B without a command: {stats}"
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


def control_gate(qdir, q, test, verdict, cls, detail):
    """A FAIL of a non-control npc_nav test only means something when the control (same method, same actor, in a vanilla
    navmeshed cell: N0) passed, in this queue or in q['control_queue'], and, when a baseline of that actor is planned
    there (method none: no command), the baseline passed too (the actor did not come to B on its own, so the control's
    PASS was the command's doing). Otherwise: INCONCLUSIVE CONTROL with the raw verdict kept in the detail; the runner
    keeps the raw verdict and the report applies the gate again (a control that passes later still counts). PASS
    needs no control (the walk was observed). No control configured: unchanged."""
    if test.get("kind") != "npc_nav" or test.get("control") or test.get("baseline") or verdict != "FAIL":
        return verdict, cls, detail
    sources = [qdir] + ([q["control_queue"]] if q.get("control_queue") else [])
    configured, ctrl, base = bool(q.get("control_queue")), [], []
    for d in sources:
        qq = load(os.path.join(d, "queue.json"), {}) or {}
        done = (load(os.path.join(d, "state.json"), {}) or {}).get("done", {})
        for c in qq.get("tests", []):
            if c.get("kind") != "npc_nav":
                continue
            configured = configured or bool(c.get("control"))
            if c.get("npc") != test.get("npc"):
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
        return "INCONCLUSIVE", "CONTROL", f"control ({test.get('method')}, {test.get('npc')}) {why(ctrl)}; {raw}"
    if base:
        bpass = [i for i, r in base if r and r.get("verdict") == "PASS"]
        if not bpass:
            return ("INCONCLUSIVE", "CONTROL",
                    f"control {passed[0]} passed but the baseline ({test.get('npc')}, no command) {why(base)}; {raw}")
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


def planned_on_other_code(commit):
    """A warning when the queue was planned at a commit this runner's checkout does not contain (planned from another
    worktree or branch: its plan may use behaviour this runner's qstep.ps1 does not have), else None."""
    if not commit or not re.fullmatch(r"[0-9a-f]{7,40}", str(commit)):
        return None
    try:
        r = subprocess.run(["git", "-C", REPO, "merge-base", "--is-ancestor", commit, "HEAD"], capture_output=True,
                           text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode == 1:
        return (f"note: this queue was planned at commit {commit[:8]}, which this runner's checkout does not contain: "
                f"its tests run with this checkout's qstep.ps1")
    if r.returncode != 0:
        return f"note: planning commit {commit[:8]} not found in this runner's checkout"
    return None


def queue_extras(tests, a, exp_dir):
    """queue.json "needs" (runner_features.needs) and "pre_launch": the RUNNER's own exp_install.py (a path relative to
    the checkout the runner runs from: testqueue.py starts it there) installs the experiment when --plugins is given, and
    with --needs it refuses when that runner lacks the features (an exp_install.py from before --needs refuses the
    option itself); without plugins, runner_features.py check does the same."""
    out = {}
    need = runner_features.needs(tests)
    if need:
        out["needs"] = need
    if a.plugins:
        out["pre_launch"] = [sys.executable, os.path.join("scripts", "game", "exp_install.py"), "install", "--exp-dir",
                             os.path.abspath(exp_dir), "--starfield", a.starfield, "--plugins", a.plugins, "--pack"] \
            + (["--needs", ",".join(need)] if need else [])
    elif need:
        out["pre_launch"] = [sys.executable, os.path.join("scripts", "game", "runner_features.py"), "check",
                             ",".join(need)]
    return out


# -------------------------------------------------------------------------------------------------------------- runner
# npc_nav step costs, worst case (typing about 0.24 s a character, +0.08 s shifted, a PowerShell start per Send)
NPC_SESSION_S = 45      # one console session: open, ClearConsole + ~60 characters, waits, OCR at up to 4 thresholds
NPC_READ_S = 75         # Read-Pos: up to 3 readpos.ps1 runs
NPC_REMOVE_S = 300      # kept for the removal (qstep.ps1 $reserve): Select-Npc (2), PickLastRef again (3), disable (1)
LIGHT_TRY_S = 50        # one time-of-day / weather command: console open, typing, reply capture + OCR, close, two
                        # screenshots and their measures (the second only when the first did not read as asked)
LIGHT_WAIT_MS = 4000    # qstep.ps1's wait after such a command before the screenshot (plan field light_wait_ms)
LIGHT_PROBE_S = 4       # terrain with light: the measure of every probe shot
REPIN_S = 8             # terrain, time_repin: the time command typed again in every probe's teleport session
CONSOLE_CMD_S = 35      # one console_pre / console_post command: open, ~45 characters, capture, OCR, close
HOP_S = 40              # one intermediate terrain hop: console open, five setpos / setangle lines, close


def terrain_hops(test):
    """Intermediate hops qstep.ps1 makes for hop_m (the same count: ceil(distance / hop_m) - 1 between points)."""
    hop = test.get("hop_m")
    pts = test.get("points") or []
    if not hop or len(pts) < 2:
        return 0
    n = 0
    for p, q in zip(pts, pts[1:]):
        n += max(0, math.ceil(math.hypot(q["x"] - p["x"], q["y"] - p["y"]) / float(hop)) - 1)
    return n


def step_timeout(test):
    """Seconds one qstep.ps1 may take before the runner kills it. Every confirmed npc_nav read is one console session
    (ClearConsole, prid <id>, GetIsID, getpos x/y/z, OCR), two when the first is not read (Select-Npc). The spawn is
    four sessions (placeatme; plr; prid + GetSelf; GetIsID + getpos) around spawn_wait_ms of game time.
    Time of day / weather: one console session per command qstep.ps1 may type (open, up to ~35 characters, reply
    capture and OCR, close), twice light_wait_ms, two screenshots and their measures: LIGHT_TRY_S each, worst case (the
    ladder stops early); terrain also measures every probe shot (LIGHT_PROBE_S) and types the time command again before
    every probe (REPIN_S, time_repin).
    console_pre / console_post: CONSOLE_CMD_S per command (console open, typing, capture, OCR, close)."""
    light = len(sky_light.commands(test)) * (LIGHT_TRY_S + 2 * test.get("light_wait_ms", LIGHT_WAIT_MS) / 1000)
    light += CONSOLE_CMD_S * sum(len(test.get(k) or []) for k in console_plan.CONSOLE_KEYS)
    if test.get("kind") == "terrain":
        # a terrain drop takes about a minute per point (teleport, fall, OCR read): 300 s cut experiment 1 off; a
        # settle_ms above the step's default 4.5 s adds to every point (core64 2026-10-11: 10-12 s settle, 103-114 s a
        # point); every intermediate hop of hop_m is one more teleport plus hop_wait_ms
        pts = test.get("points", [])
        settle = max(0.0, test.get("settle_ms", 4500) - 4500) / 1000
        per_pt = (LIGHT_PROBE_S if sky_light.commands(test) else 0) + (REPIN_S if sky_light.repins(test) else 0)
        return int(150 + (90 + settle) * (len(pts) + 1) + light + per_pt * len(pts) + terrain_hops(test) * HOP_S
                   + terrain_hops(test) * test.get("hop_wait_ms", 6000) / 1000)
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
        return int(fixed + n * (2 * NPC_SESSION_S + 10) + max(reads) + light)
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
        miss = runner_features.missing(self.q.get("needs") or runner_features.needs(tests))
        if miss:
            self.log(f"stopped: this queue needs runner features {miss} that this checkout ({REPO}) lacks: update it "
                     f"(merge the branch the queue was planned from) and run the queue again")
            self.checkpoint(f"stopped: runner lacks {', '.join(miss)}")
            return 3
        note = planned_on_other_code(self.q.get("commit"))
        if note:
            self.log(note)
        self.checkpoint("running")
        ran = 0
        for t in pending:
            if ran >= a.max_tests or time.time() > self.deadline:
                self.log("test or time budget used up")
                break
            pre = precondition(t)
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
            lt = None                                     # the sky reading, for tests that asked for a time of day
            con = []                                      # console_pre / console_post replies (parsed OCR)
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
                    obs = load(os.path.join(out_dir, "obs.json"))
                    raw = judge(t, obs, out_dir)
                    lt = light_of(t, obs)
                    con = console_plan.summary(t, obs)[1]
                    verdict, cls, detail = control_gate(self.qdir, self.q, t, *raw)
                    if not t["cell"]:
                        self.cell = None                  # the test travelled (terrain experiment world)
                    if cls in ("STOPPED", "NOOBS", "NORESULT"):
                        self.cell = None                  # unknown game state: re-verify the cell next time
            rec = {"id": t["id"], "kind": t["kind"], "cell": t["cell"], "ref": t["ref"], "model": t.get("model", ""),
                   "attempt": n, "verdict": verdict, "class": cls, "detail": detail, "exit": code, "dir": out_dir, "t": now()}
            if t.get("expect"):
                rec["expect"] = t["expect"]
            if lt:                                        # daylight / night / unclear / unread, sky before -> after
                rec["light"], rec["sky"], rec["light_detail"] = lt["light"], lt["sky"], lt["detail"]
                rec["light_tested"], rec["light_credited"] = lt["tested"], lt["credited"]
                if lt["probes"]:
                    rec["light_probes"] = lt["probes"]
            if con:
                rec["console"] = con
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
            if verdict == "INCONCLUSIVE" and cls not in NO_BREAKER + FINAL_INCONCLUSIVE:
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
    # time of day / weather asked for: was the run in daylight? (night with "no effect": the commands changed nothing)
    light = [{"id": r["id"], "light": r["light"], "sky": r.get("sky"), "tested": r.get("light_tested"),
              "credited": r.get("light_credited"), "probes": r.get("light_probes"), "detail": r.get("light_detail", "")}
             for r in final.values() if r.get("light")]
    rep = {"build_id": q["build_id"], "commit": q["commit"], "tests": len(q["tests"]), "results": len(final),
           "pending": pending, "tally": tally, "ranked": ranked}
    console = [dict(c, id=r["id"]) for r in final.values() for c in r.get("console") or []]
    if expectations:
        rep["expectations"] = expectations
    if light:
        rep["light"] = light
    if console:
        rep["console"] = console
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
    if light:
        lines += ["", "## Light (time of day / weather asked for; sky = the arrival camera's top 200 rows, probes = "
                  "the median of the probe shots' top corners, 0..255; the probes decide when there are some)", "",
                  "| test | light | sky before -> after | probes | commands tested | worked | detail |",
                  "|---|---|---|---|---|---|---|"]
        for x in light:
            b, a_ = (list(x["sky"] or []) + [None, None])[:2]
            sky = " -> ".join("-" if v is None else f"{v:.1f}" for v in (b, a_))
            pr = x.get("probes") or {}
            probes = f"{pr['corners']:.1f} ({pr['n']})" if pr.get("corners") is not None else "-"
            tested = {True: "yes", False: "no (already as asked)"}.get(x.get("tested"), "unknown")
            lines.append(f"| {x['id']} | {x['light']} | {sky} | {probes} | {tested} | {x.get('credited') or '-'} | "
                         f"{x['detail']} |")
    if console:
        lines += ["", "## Console replies (console_pre before the travel, console_post after the arrival; OCR, best "
                  "effort: the capture is console_<k>.png in the attempt folder)", "",
                  "| test | phase | command | reply | note |", "|---|---|---|---|---|"]
        for c in console:
            got = c["value"] if c.get("status") == "value" else c.get("status")
            lines.append(f"| {c['id']} | {c['phase']} | `{c['cmd']}` | {got} | {c.get('note') or ''} |")
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
    p.add_argument("--routes-prefix", default="routes_", help="route files <staging>/<prefix><cell>.json (routes.py output)")
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
    for sp in (pt, pn):                                   # time of day / weather for every test (docs/ai/test-queue.md)
        sp.add_argument("--time-of-day", type=float, default=None,
                        help="local hour set after the arrival, before the screenshots (12 = noon on any planet)")
        sp.add_argument("--time-methods", default="",
                        help=f"ladder of time commands among {','.join(sky_light.TIME_METHODS)} "
                             f"(default {','.join(sky_light.DEFAULT_LADDER)}: stops once the sky reads right)")
        sp.add_argument("--weather", default="", help="weather form id forced after the arrival (fw <id>)")
        sp.add_argument("--need-daylight", action="store_true",
                        help="a PASS whose run did not read as daylight is INCONCLUSIVE NIGHT (retried)")
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
