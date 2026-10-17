"""Queued in-game test runner: plan a batch of tests on ONE pinned build, run them unattended without any AI calls,
checkpoint after every test, resume later, and rank the problems found.

usage:
  python testqueue.py plan   --staging <build dir> --out <queue dir> [--cells A,B] [--kinds stairs,door,fall,movable,travel]
                             [--per-cell 12] [--per-kind N] [--plugin-index 02] [--impulse] [--routes-prefix routesfull_]
                             [--routes-dir <dir>]  (route files planned again outside the pinned build, e.g. a
                             routes.py fix: the build, its plugin hash and deploy stay those of --staging; the queue
                             keeps its own copy of the route files) [--refs A,B] (only these references, in this
                             order) [--first A,B] (these references first)
                             --impulse: a movable item the walk did not move is pushed with ApplyHavokImpulse
  python testqueue.py plan-movable --staging <build dir> --exp-dir <dir with plan.json> --out <queue dir> [--fresh]
                             movable_control: an item (vanilla, or a converted one of the build) placed in a vanilla
                             cell, walked over, then pushed with ApplyHavokImpulse (docs/ai/test-queue.md "Movable
                             items: walk, then impulse")
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
  python testqueue.py plan-door --staging <build dir> --exp-dir <dir with plan.json> --out <queue dir>
                             [--plugins a.esm,b.esm] [--fresh]
                             door_trip (docs/slice/redrocket-door.md): coc into a world, through a load door into an
                             interior and back out, save, load; every arrival observed (position, GetInCell, screenshot)
  python testqueue.py plan-walk --staging <build dir> --exp-dir <dir with plan.json and walk_ground.json> --out <queue dir>
                             --install-exp <experiment> --plugins a.esm,b.esm [--fresh]
                             walk (docs/terrain/walk-redrocket-sanctuary.md): the player walks continuously with real
                             input (W held, player.setangle z, never a setpos) from the coc arrival over planned waypoints
                             (scripts/terrain/walk_route.py); every leg read, its ground checked (walk_eval.py). The
                             experiment's staged inputs are pinned (queue.json experiment_identity) and checked before
                             a launch and, against the install record, when a result is recorded: a PASS or FAIL on
                             another install is INCONCLUSIVE INSTALL and stops the run
  python testqueue.py run   --queue <queue dir> [--max-tests N] [--max-hours 8] [--min-idle 900] [--wait-for-idle]
                             [--refocus] [--max-attempts 2] [--dry-run]
  python testqueue.py report --queue <queue dir>

Run exit status: 0 = all tests have terminal results (or a dry-run preview); 4 = budget pause with pending tests.
A required queue's chain keeps nonzero runs queued for resume. A completed queue may still contain FAIL/INCONCLUSIVE.
  python testqueue.py status --queue <queue dir>

Verdicts: PASS, FAIL (with a reason class) or INCONCLUSIVE. A missing observation (no position read, no screenshot,
start not reached) is INCONCLUSIVE, never PASS. INCONCLUSIVE tests are retried up to --max-attempts; FAIL is final.

The owner's PC-use controls are checked before every launch and every test, and the run stops (checkpointed, resumable)
when one trips:
  - STOP file: <queue>\\STOP, the chain folder's <queue>\\..\\STOP_ALL or %LOCALAPPDATA%\\fo4-ai-team\\state\\testqueue.STOP
    (create it to stop the runner; a walk step checks them between its actions and during a hold too);
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
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import console_plan  # noqa: E402
import exp_install  # noqa: E402
import route_eval  # noqa: E402
import runner_features  # noqa: E402
import sky_light  # noqa: E402
import bridge_log  # noqa: E402
import walk_eval  # noqa: E402

UNIT = 1.0 / 70.0
COMPANION_REF = "000057BE"   # Starfield.esm ACHR VascoREF: the test save's companion, disabled per session
KINDS = ("stairs", "door", "fall", "movable", "travel")         # planned from a build; "terrain" via plan-terrain
EXTRA_KINDS = ("terrain", "npc_nav", "door_trip", "walk", "movable_control")   # planned from an experiment's plan.json
# ranking weight per (kind, verdict reason class): falling out of the world and broken travel first
SEVERITY = {("fall", "FALL"): 5, ("travel", "NOTRAVEL"): 5, ("travel", "NOPROMPT"): 4, ("door", "BLOCKED"): 4,
            ("door", "NOPROMPT"): 3, ("stairs", "FALL"): 4, ("stairs", "STUCK"): 3, ("door", "FALL"): 5,
            ("movable", "NOTMOVED"): 2, ("movable", "ITEMFELL"): 3, ("any", "CRASH"): 5,
            ("terrain", "NOTERRAIN"): 5, ("terrain", "HEIGHTS"): 4,
            ("npc_nav", "FELL"): 5, ("npc_nav", "NONAV"): 4, ("npc_nav", "STALLED"): 3, ("npc_nav", "WANDER"): 3,
            ("npc_nav", "NOCOMBAT"): 3,
            ("door_trip", "NOLOAD"): 5, ("door_trip", "WRONGCELL"): 5, ("door_trip", "UNMERGED"): 5,
            ("door_trip", "REMERGED"): 4, ("door_trip", "ELSEWHERE"): 4, ("door_trip", "RELOAD"): 5,
            ("door_trip", "FELL"): 5, ("door_trip", "OFFGROUND"): 3,
            ("walk", "BOUNDARY"): 5, ("walk", "FELL"): 5, ("walk", "JUMP"): 5, ("walk", "HEIGHTS"): 4,
            ("walk", "STUCK"): 4, ("walk", "OFFROUTE"): 3,
            ("movable", "STUCK"): 3, ("movable_control", "STUCK"): 3, ("movable_control", "ITEMFELL"): 3,
            ("movable_control", "NOTMOVED"): 2}
PS = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]
BREAKER = 6          # inconclusive attempts in a row, with no PASS/FAIL yet, that switch a kind off for the run
# inconclusive for a reason a retry cannot change. NIGHT (need_daylight, the run did not read as daylight) is NOT
# final: arrivals of the same test differ between attempts (exp1d 2026-10-11: a1 fell into a pit, sky 7.3, a2 in the
# open, 131.0), so a retry can read differently; it does not count towards the circuit breaker either (the step works)
# ELEVATED (movable): the item lies on furniture the walk did not reach: more than ELEVATED_M above the player's feet and
# the walk never came within CONTACT_M of it (supervised_1011 0007, 2026-10-12: a cigarette pack 0.83 m up on a desk,
# the player stopped at the desk 0.67 m from it), or above the player's head. The same walk from the same stand point
# stops at the same furniture however often it is retried, and the step itself worked. An item the walk passed through
# (batch_full 0100: 0.26 m from the walk, 0.53 m above the highest feet read) is not ELEVATED: FAIL NOTMOVED
FINAL_INCONCLUSIVE = ("CONTROL", "PRECONDITION", "ELEVATED")
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
# combat_reads (docs/ai/test-queue.md "Combat engagement"): what every sample's confirmed session also types, after the
# position, to ask the combat manager instead of measuring a walk (in QASmoke on 2026-10-13 the hostile Spacer held its
# ground for 30 s and StartCombat froze the calm citizen: an approach is the wrong measure of combat). Condition
# functions of Starfield.exe 1.16.244 (help strings): GetCombatState "Test the state of this actor in the combat
# manager", GetCombatTarget "Gets the current actor's combat target (ref ID)", GetLineOfSight <ref>. qstep.ps1 has the
# same table; nothing else is ever typed for it. The reply formats are unverified (parse_npc.py).
NPC_COMBAT_READS = ("GetCombatState", "GetCombatTarget", "GetLineOfSight player")
NPC_COMBAT_METHODS = ("none", "combat_player")      # a hostile actor engages on its own; StartCombat player
PLAYER_REF = "00000014"                             # the player's ref id: GetCombatTarget's reply when engaged
# GenerateNavMesh's short name "gnm" sits next to its name and help text in Starfield.exe, but its command entry was
# not decoded (supported hypothesis, unlike PTR / PLR / PRID): staged plans do not use it yet.
NPC_PRE = ("gnm",)                  # probe commands allowed before the spawn (GenerateNavMesh: route R1, run N2)
# every key a plan.json test may carry (npc_test); any other key stops the planning, so a typo or a key of a newer
# runner is never dropped silently (a lost control_npc would turn every FAIL into INCONCLUSIVE CONTROL)
NPC_PLAN_KEYS = frozenset((
    "label", "travel", "npc", "method", "pre", "a", "b", "reads_s", "radius", "min_progress", "nomove", "spawn_tol",
    "target_tol", "fell_m", "drop", "settle_ms", "pre_wait_ms", "max_speed", "spawn_wait_ms", "handle_tol", "path_line",
    "control", "control_npc", "fresh", "anchor", "spawn_local", "requires", "expect", "basis",
    "precommand_m", "arrive_progress", "combat_reads")
    + sky_light.LIGHT_KEYS + console_plan.CONSOLE_KEYS)            # read by with_extras, after npc_test
# requires.verdict: the required test's verdict, or DECIDED for either PASS or FAIL (its run was judged at all: for an
# npc_nav test, the spawn was confirmed and the reads were taken)
REQUIRE_VERDICTS = ("PASS", "FAIL", "DECIDED")

# Movable items (docs/ai/test-queue.md "Movable items: walk, then impulse"). An item counts as moved at MOVE_M. Only the
# walk can pass a movable test: the test asks whether the player pushes the item. When the walk did not move it,
# ApplyHavokImpulse (a console script function of Starfield.exe 1.16.244: opcode 0x1251, four Floats, axis x y z and
# magnitude; scripts/recon_console.py) is typed on the confirmed selection in steps of a speed change dv (m/s):
# magnitude = mass x dv, the unit kg m/s a supported hypothesis (LC012NASAGravTrigger.psc scales its impulses by
# GetMass()). The ladder stops at the first step that moves the item. It tells a simulated body the walk did not push
# (still FAIL NOTMOVED when the walk reached it) from one nothing moves (FAIL STUCK); since its magnitudes scale with
# the mass, it cannot show whether the mass stops the player: movable_control's vanilla items and SetRigidBodyMass can.
# ELEVATED: the item more than ELEVATED_M above the player's feet (the highest of the reads before and after the walk)
# while the walk came no closer than CONTACT_M to it, or more than OVERHEAD_M above them. CONTACT_M and OVERHEAD_M are
# not measured from Starfield's character capsule (supported hypothesis: a radius of about 0.3-0.4 m plus the item's
# half-width, a height of about 1.8 m); CONTACT_M lies between the two readings it must separate: 0.26 m (batch_full
# 0100, walked through: FAIL NOTMOVED) and 0.67 m (supervised_1011 0007, stopped at the desk: ELEVATED)
MOVE_M, ELEVATED_M, CONTACT_M, OVERHEAD_M = 0.05, 0.5, 0.5, 1.8
IMPULSE_DV = (1.5, 6.0, 24.0)
SET_MASS_CMD = "SetRigidBodyMass"     # console script function, opcode 0x1156, one Float: "Sets the Havok mass for an object."
MASS_PROBE = 'cf "ObjectReference.GetMass"'     # Papyrus ObjectReference.GetMass() through the console's CallFunction
# movable_control: the player read at the spot, and the placed item, this close in height to the spot (the floor there)
SPOT_Z_M, SPAWN_Z_M = 0.4, 0.5
MASS_WAIT_MS = 1000     # movable_control: the console closed after SetRigidBodyMass before GetMass reads it (the game runs)


def _fmt(x, nd=3):
    """A number as the console gets it: up to nd decimals, no trailing zeros, never -0."""
    x = round(float(x), nd)
    if x == 0:
        return "0"
    return f"{x:.{nd}f}".rstrip("0").rstrip(".")


def impulse_axis(heading):
    """Unit axis of an impulse: back along the walk (towards the stand point, the path the player has just walked, so
    clear of obstacles) and 45 degrees up, so the item hops off the floor and lands away from where it lay."""
    h = math.radians(float(heading))
    s = 1 / math.sqrt(2)
    return [round(-math.sin(h) * s, 3), round(-math.cos(h) * s, 3), round(s, 3)]


def impulse_steps(mass, heading, dvs=IMPULSE_DV):
    """The impulse ladder of one item: [{dv, magnitude, cmd}], magnitude = mass x dv (kg m/s)."""
    ax = " ".join(_fmt(x) for x in impulse_axis(heading))
    out = []
    for dv in dvs:
        mag = round(float(mass) * float(dv), 2)
        if not 0 < mag < 1e6:
            sys.exit(f"impulse magnitude {mag} out of range (mass {mass} kg x dv {dv} m/s)")
        out.append({"dv": float(dv), "magnitude": mag, "cmd": f"ApplyHavokImpulse {ax} {_fmt(mag, 2)}"})
    return out


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
def plan_cell(cell, staging, kinds, per_cell, plugin_index, formids, items, all_refs, routes_prefix="routes_",
              impulse=False, routes_dir=None):
    """Tests for one exported cell, in the owner's priority order: stairs, falls, doors (both sides), movable, travel.
    impulse: a movable test whose walk does not move the item applies the impulse ladder to it (needs the item's base
    record in formids.json and its mass in the manifest; runner feature "impulse").
    Route files come from `routes_dir` when given (routes planned again for the same build), else from the staging."""
    name = cell["cell"]
    out = []
    routes_file = os.path.join(routes_dir or staging, f"{routes_prefix}{name}.json")   # routesfull_ = routes.py --max 400
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
            t = {"kind": "movable", "cell": name, "ref": r["formkey"], "model": r["model"],
                 "sf_ref": f"{plugin_index}{local:06X}", "item": [round(x, 3) for x in item],
                 "stand": [round(x, 3) for x in stand], "heading": heading_to(stand, item), "walk_ms": 900}
            it = items[key]
            base = formids.get(f"MSTT:{it.get('editor_id')}")
            mass = (it.get("movable") or {}).get("mass_kg")
            if impulse and base is not None and mass:
                # the impulse acts on the selection only after prid <ref> and GetIsID <base> read 1 in that session
                t.update(sf_base=f"{plugin_index}{base:06X}", mass_kg=float(mass),
                         impulses=impulse_steps(mass, t["heading"]), impulse_wait_ms=3000)
            out.append(t)
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


def order_by_refs(tests, refs="", first=""):
    """Tests restricted to the references listed in `refs` (comma-separated FormID prefixes such as 0EBED6, the order
    they are listed in) and/or with those listed in `first` moved to the front in that order, the rest after them in
    their planned order. A reference with several tests (door sides) keeps them together."""
    def keys(s):
        return [k.strip().upper() for k in s.split(",") if k.strip()]

    def rank(t, wanted):
        ref = str(t.get("ref", "")).split(":")[0].upper()
        return next((i for i, k in enumerate(wanted) if ref.startswith(k)), None)
    if keys(refs):
        tests = [t for t in tests if rank(t, keys(refs)) is not None]
        tests = sorted(tests, key=lambda t: rank(t, keys(refs)))
    if keys(first):
        front = sorted([t for t in tests if rank(t, keys(first)) is not None], key=lambda t: rank(t, keys(first)))
        tests = front + [t for t in tests if rank(t, keys(first)) is None]
    return tests


def plan(a):
    staging = os.path.abspath(a.staging)
    esm = os.path.join(staging, "FO4Port.esm")
    if not os.path.exists(esm):
        sys.exit(f"no FO4Port.esm in {staging}: build it first")
    kinds = [k.strip() for k in a.kinds.split(",") if k.strip()]
    bad = [k for k in kinds if k not in KINDS]
    if bad:
        sys.exit(f"unknown kinds {bad}; known: {KINDS}")
    routes_dir = os.path.abspath(a.routes_dir) if getattr(a, "routes_dir", "") else None
    if routes_dir and not glob.glob(os.path.join(routes_dir, f"{a.routes_prefix}*.json")):
        sys.exit(f"no {a.routes_prefix}*.json route files in {routes_dir}")
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
        tests += plan_cell(c, staging, kinds, a.per_cell, a.plugin_index, formids, items, all_refs, a.routes_prefix,
                           routes_dir=routes_dir, impulse=getattr(a, "impulse", False))
    if a.per_kind:                                        # small batches: the first N of each kind in each cell
        seen = {}
        keep = []
        for t in tests:
            k = (t["cell"], t["kind"])
            seen[k] = seen.get(k, 0) + 1
            if seen[k] <= a.per_kind:
                keep.append(t)
        tests = keep
    tests = order_by_refs(tests, getattr(a, "refs", ""), getattr(a, "first", ""))
    os.makedirs(a.out, exist_ok=True)
    routes_sha = {}
    if routes_dir:                     # the queue keeps its own copy: re-planning that folder cannot change this queue
        own = os.path.join(os.path.abspath(a.out), "routes")
        os.makedirs(own, exist_ok=True)
        copied = {}
        for t in tests:
            f = t.get("routes_file")
            if f and f not in copied:
                copied[f] = os.path.join(own, os.path.basename(f))
                shutil.copyfile(f, copied[f])
            if f:
                t["routes_file"] = copied[f]
    for f in sorted({t["routes_file"] for t in tests if t.get("routes_file") and os.path.exists(t["routes_file"])}):
        routes_sha[os.path.basename(f)] = sha256(f)
    for n, t in enumerate(tests):
        t["id"] = f"{n:04d}_{t['kind']}_{t['cell']}_{str(t['ref']).split(':')[0]}" + (f"_s{t['side']}" if t.get("side") else "")
    digest = sha256(esm)
    q = {"created": now(), "staging": staging, "plugin_sha256": digest, "build_id": digest[:8],
         "commit": subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
         "save": f"fo4sf_test_{digest[:8]}", "plugin_index": a.plugin_index, "hours": [[0, 24]], "tests": tests,
         **({"routes_dir": routes_dir} if routes_dir else {}), **({"routes_sha256": routes_sha} if routes_sha else {})}
    q.update(apply_bridge(tests, a))
    need = runner_features.needs(tests)
    if need:                                              # e.g. "impulse": an older runner refuses the queue
        q["needs"] = need
    os.makedirs(a.out, exist_ok=True)
    save_atomic(os.path.join(a.out, "queue.json"), q)
    counts = {}
    for t in tests:
        counts[t["kind"]] = counts.get(t["kind"], 0) + 1
    print(f"{len(tests)} tests in {len(cells)} cells on build {q['build_id']}: {counts}")


def activate_block(a):
    """The terrain "activate" block of a plan.json entry (docs/ai/test-queue.md "Activate"), validated at planning: ref
    and base are 8 hex digits (both are typed into the game), expect a list of non-empty strings; anything else stops
    the plan (Codex's review of #145: the planner must carry and check the block, not drop it)."""
    if not isinstance(a, dict):
        sys.exit("activate must be an object {ref, base, expect}")
    for k in ("ref", "base"):
        if not re.fullmatch(r"[0-9A-Fa-f]{8}", str(a.get(k, ""))):
            sys.exit(f"activate.{k} must be 8 hex digits: {a.get(k)!r}")
    expect = a.get("expect") or []
    if not isinstance(expect, list) or not all(isinstance(x, str) and x for x in expect):
        sys.exit("activate.expect must be a list of non-empty strings")
    return {"ref": str(a["ref"]).upper(), "base": str(a["base"]).upper(), "expect": list(expect)}


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
        if w.get("activate"):
            w = dict(w, activate=activate_block(w["activate"]))
        w = dict(w, points=terrain_points(w.get("points")))
        tests.append(with_extras({"id": f"{n:04d}_terrain_{w['coc']}", "kind": "terrain", "cell": "",
                                  "ref": w["coc"], "model": w.get("label", ""), "world_coc": w["coc"], "travel": travel,
                                  **{k: w[k] for k in ("spawn_local", "anchor", "drop_above_spawn", "settle_ms",
                                                       "z_ref", "hop_m", "hop_wait_ms", "activate",
                                                       "teleport_console") if w.get(k)},
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


def terrain_points(points):
    """plan.json's terrain "points": a non-empty list of {label, x, y, expect} with finite numbers, like the other
    planners' _vec / _num (#219: an empty list made the judge's checks vacuous, a NaN expect never failed)."""
    if not isinstance(points, list) or not points:
        sys.exit(f"bad points in plan.json (want a non-empty list of {{label, x, y, expect}}): {points!r}")
    out = []
    for p in points:
        if not isinstance(p, dict):
            sys.exit(f"bad point in plan.json: {p!r}")
        out.append(dict(p, label=str(p.get("label") or f"p{len(out)}"),
                        **{k: _num(p, k, None, -1e6, 1e6) for k in ("x", "y", "expect")}))
    return out


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
    if "combat_reads" in w:
        # the combat manager asked at every sample (NPC_COMBAT_READS) and the verdict ENGAGED / NOCOMBAT from its
        # replies, the walk as detail: a hostile actor (method none) or StartCombat player. Such a test is neither a
        # wander baseline nor a control (its PASS means "in combat with the player", not "stayed away"): it gates
        # nothing and is gated by nothing (control_gate). Needs runner feature npc_combat.
        if not isinstance(w["combat_reads"], bool):
            sys.exit(f"{label}: combat_reads must be true or false: {w['combat_reads']!r}")
        if w["combat_reads"]:
            if method not in NPC_COMBAT_METHODS:
                sys.exit(f"{label}: combat_reads goes with methods {NPC_COMBAT_METHODS}, not {method!r}")
            if t["control"] or w.get("control_npc"):
                sys.exit(f"{label}: a combat_reads test is judged by its own combat reads: no control, no control_npc")
            t["combat_reads"] = True
            t["baseline"] = False
    # the walk measured from t0 (N0b, docs/actors/npc-navigation.md 5.4): only when the plan sets them, so a queue
    # without them is judged exactly as before and needs no runner feature (runner_features "npc_t0")
    if "precommand_m" in w:
        # a commanded test whose actor came this far towards B between the spawn read and t0 is INCONCLUSIVE
        # PRECOMMAND (default: min_progress)
        t["precommand_m"] = _num(w, "precommand_m", 5.0, 0.1, 500)
    if "arrive_progress" in w:
        # an arrival within radius is a PASS only when the actor also came this far towards B after t0 (d0 - min d);
        # a baseline then FAILs WANDER on the largest approach between any two of its reads, the spawn read included
        t["arrive_progress"] = _num(w, "arrive_progress", 0.0, 0.0, 500)
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
    return with_extras(t, w, {})   # time of day, weather, console commands (before the travel, after the arrival)


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
          f"on build {q['build_id']}" + (f", needs runner features {', '.join(q['needs'])}" if q.get("needs") else ""))


# door_trip (docs/slice/redrocket-door.md): every key a plan.json test may carry; anything else stops the planning
DOOR_PLAN_KEYS = frozenset((
    "label", "travel", "spawn_local", "outside", "inside", "save", "radius", "start_tol", "reload_tol", "ground_tol",
    "walk_ms", "walk_step_ms", "settle_ms", "drop", "near_wait_ms", "load_wait_s", "moved_m", "activate_m", "fresh",
    "expect", "basis", "facing_tol", "frame_m", "probes", "route_hold_ms", "route_reach_m", "route_speed",
    "route_walk_ms", "route_max_steps", "route_final_steps")
    + sky_light.LIGHT_KEYS + console_plan.CONSOLE_KEYS)
DOOR_SIDE_KEYS = {"outside": frozenset(("start", "door", "arrival", "near", "ground", "ref", "route", "arrival_heading")),
                  "inside": frozenset(("cell", "cell_id", "start", "door", "arrival", "near", "floor", "route",
                                       "arrival_heading"))}
DOOR_ROUTE_MAX = 64                                             # waypoints per route (qstep.ps1 checks the same)
ROUTE_MAX_SPEED = 10.0      # m/s: two route reads farther apart than a W hold walks are a teleport or another frame
NAME = r"[A-Za-z0-9_]{1,64}"                                    # a cell EditorID or a save name: typed into the console


def door_test(n, w):
    """One door_trip test from a plan.json entry (docs/slice/redrocket-door.md). Positions: "outside" in the world's own
    frame (the runner adds the overlay's merge offset, measured from the settled arrival against spawn_local), "inside"
    in the interior cell's frame. Everything qstep.ps1 types comes from here and is validated (qstep checks it again):
    the coc travel, the interior cell's EditorID (player.GetInCell), the save name, finite numbers."""
    label = str(w.get("label") or f"door{n}")
    unknown = sorted(set(w) - DOOR_PLAN_KEYS)
    if unknown:
        sys.exit(f"{label}: unknown plan.json keys {unknown} (known: {sorted(DOOR_PLAN_KEYS)})")
    travel = str(w.get("travel") or "")
    if not re.fullmatch(r"coc [A-Za-z0-9_]+", travel):
        sys.exit(f"bad travel in plan.json (coc <cell editor id>): {travel!r}")
    sides = {}
    for side, keys in DOOR_SIDE_KEYS.items():
        s = w.get(side)
        if not isinstance(s, dict) or set(s) - keys:
            sys.exit(f"{label}: {side} must be an object with keys among {sorted(keys)}: {s!r}")
        out = {k: _vec(s.get(k), (3,), f"{side}.{k}") for k in ("start", "door", "arrival")}
        out["near"] = _vec(s["near"], (3,), f"{side}.near") if s.get("near") is not None else None
        for k in ("ground", "floor"):
            if k in keys and s.get(k) is not None:
                out[k] = _vec([s[k]], (1,), f"{side}.{k}")[0]
        if s.get("ref") is not None:                    # the door's runtime form id: prid + getpos (a diagnostic)
            if not re.fullmatch(r"[0-9A-Fa-f]{8}", str(s["ref"])):
                sys.exit(f"bad {side}.ref in plan.json (8 hex digits, the door's form id in the load order): {s['ref']!r}")
            out["ref"] = str(s["ref"]).upper()
        if s.get("route") is not None:                  # walked from where the player stands (docs/slice/door-frames.md)
            r = s["route"]
            if not isinstance(r, list) or not 2 <= len(r) <= DOOR_ROUTE_MAX:
                sys.exit(f"bad {side}.route in plan.json (2 to {DOOR_ROUTE_MAX} waypoints x, y, z): {r!r}")
            out["route"] = [_vec(q, (3,), f"{side}.route") for q in r]
        if s.get("arrival_heading") is not None:        # the facing the door gives on arrival (degrees, as getangle z)
            out["arrival_heading"] = round(_vec([s["arrival_heading"]], (1,), f"{side}.arrival_heading")[0] % 360, 3)
        if s.get("cell_id") is not None:                # player.GetInCell <form id>: a diagnostic only
            if not re.fullmatch(r"[0-9A-Fa-f]{8}", str(s["cell_id"])):
                sys.exit(f"bad {side}.cell_id in plan.json (8 hex digits, the cell's form id in the load order): {s['cell_id']!r}")
            out["cell_id"] = str(s["cell_id"]).upper()
        sides[side] = out
    cell = str(w["inside"].get("cell") or "")
    if not re.fullmatch(NAME, cell):
        sys.exit(f"bad inside.cell in plan.json (an interior cell's EditorID): {cell!r}")
    sides["inside"]["cell"] = cell
    save = str(w.get("save") or "")
    if not re.fullmatch(NAME, save) or not save.lower().startswith("fo4sf_"):
        sys.exit(f"bad save name in plan.json (fo4sf_<letters, digits, _>, not the runner's session save): {save!r}")
    if save.lower().startswith("fo4sf_test_"):
        sys.exit(f"save name {save!r} would overwrite a runner session save (fo4sf_test_<build>)")
    safe = re.sub(r"[^A-Za-z0-9_]", "_", label)[:40]
    o, i = sides["outside"], sides["inside"]
    t = {"id": f"{n:04d}_door_trip_{safe}", "kind": "door_trip", "cell": "", "ref": label, "model": label,
         "travel": travel, "spawn_local": _vec(w.get("spawn_local"), (2, 3), "spawn_local"),
         "outside": o, "inside": i, "save": save,
         # the walk towards each door: heading from the start to the door (degrees clockwise from north, as setangle z)
         "heading_out": heading_to(o["start"], o["door"]), "heading_in": heading_to(i["start"], i["door"]),
         "radius": _num(w, "radius", 4.0, 0.5, 50), "start_tol": _num(w, "start_tol", 3.0, 0.5, 50),
         "reload_tol": _num(w, "reload_tol", 1.0, 0.05, 50), "ground_tol": _num(w, "ground_tol", 1.0, 0.05, 50),
         "walk_ms": int(_num(w, "walk_ms", 8000, 0, 60000)), "walk_step_ms": int(_num(w, "walk_step_ms", 500, 100, 5000)),
         "settle_ms": int(_num(w, "settle_ms", 6000, 0, 30000)), "drop": _num(w, "drop", 0.5, 0, 50),
         "near_wait_ms": int(_num(w, "near_wait_ms", 6000, 0, 60000)),
         "load_wait_s": int(_num(w, "load_wait_s", 90, 10, 600)),
         # a read farther than moved_m from a leg's start is on the other side of the door (a load: the two frames
         # are about 2.7 km apart here); activate_m: the automatic door's range (Starfield.esm
         # fAutoDoorActivateDistance 3), within which standing without a load is a NOLOAD
         "moved_m": _num(w, "moved_m", 30.0, 5, 1000), "activate_m": _num(w, "activate_m", 3.0, 0.5, 10),
         # every read strict (readpos -Strict), a load never from one read, GetInCell never judged, the facing on
         # arrival judged when planned (runner feature door_frames: the first live run, 2026-10-13)
         "reads": "strict", "facing_tol": _num(w, "facing_tol", 20.0, 1, 90), "frame_m": _num(w, "frame_m", 150.0, 10, 1000)}
    if o.get("route") or i.get("route"):
        t.update({"route_hold_ms": int(_num(w, "route_hold_ms", 2000, 300, 10000)),
                  "route_reach_m": _num(w, "route_reach_m", 0.8, 0.2, 5),
                  "route_speed": _num(w, "route_speed", 4.6, 0.5, 20),
                  "route_walk_ms": int(_num(w, "route_walk_ms", 60000, 1000, 600000)),
                  "route_max_steps": int(_num(w, "route_max_steps", 40, 2, 400)),
                  "route_final_steps": int(_num(w, "route_final_steps", 6, 1, 40))})
        for side, s in (("outside", o), ("inside", i)):
            r = s.get("route")
            if r and math.dist(r[-1], s["door"]) > t["activate_m"] + 1.0:
                sys.exit(f"{label}: {side}.route ends {math.dist(r[-1], s['door']):.1f} m from the door (at most "
                         f"activate_m + 1 m: the final approach steers at the door from there)")
            if r and t["moved_m"] <= max(math.dist(q, r[0]) for q in r) + 10.0:
                sys.exit(f"{label}: moved_m {t['moved_m']} must exceed the {side} route's reach from its start + 10 m "
                         f"(a read beyond moved_m counts as the other side of the door)")
    probes = w.get("probes")
    if probes is not None:                              # merge probes: refs whose getpos is read after the arrival
        if not isinstance(probes, list) or len(probes) > 8:
            sys.exit(f"bad probes in plan.json (at most 8 objects with ref, local, what): {probes!r}")
        t["probes"] = []
        for q in probes:
            if not isinstance(q, dict) or set(q) - {"ref", "local", "what"} or \
                    not re.fullmatch(r"[0-9A-Fa-f]{8}", str(q.get("ref"))):
                sys.exit(f"bad probe in plan.json (ref: 8 hex digits, local: x y z, what): {q!r}")
            t["probes"].append({"ref": str(q["ref"]).upper(), "local": _vec(q.get("local"), (3,), "probe local"),
                                "what": str(q.get("what") or "")[:160]})
    if w.get("fresh"):
        t["fresh"] = True
    for k in ("expect", "basis"):
        if w.get(k):
            t[k] = str(w[k])
    return with_extras(t, w, {})


def plan_door(a):
    """door_trip tests from <exp-dir>/plan.json (a list, or {"tests": [...]}); see door_test."""
    staging = os.path.abspath(a.staging)
    esm = os.path.join(staging, "FO4Port.esm")
    if not os.path.exists(esm):
        sys.exit(f"no FO4Port.esm in {staging}: the runner pins and launches a build")
    src = load(os.path.join(a.exp_dir, "plan.json"))
    if isinstance(src, dict):
        src = src.get("tests")
    if not src or not isinstance(src, list) or not all(isinstance(w, dict) for w in src):
        sys.exit(f"no door_trip tests in {os.path.join(a.exp_dir, 'plan.json')} (a list of test objects)")
    cli = light_cli(a)
    tests = [with_extras(door_test(n, w), w, cli) for n, w in enumerate(src)]
    digest = sha256(esm)
    q = {"created": now(), "staging": staging, "plugin_sha256": digest, "build_id": digest[:8],
         "commit": subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
         "save": f"fo4sf_test_{digest[:8]}", "plugin_index": a.plugin_index, "hours": [[0, 24]],
         "launch_cell": a.launch_cell, "experiment": os.path.abspath(a.exp_dir),
         "tests": [dict(t, fresh=True) if a.fresh else t for t in (tests[:a.only] if a.only else tests)]}
    q.update(queue_extras(q["tests"], a, a.exp_dir))
    os.makedirs(a.out, exist_ok=True)
    save_atomic(os.path.join(a.out, "queue.json"), q)
    print(f"{len(q['tests'])} door_trip tests (experiment {a.exp_dir}) on build {q['build_id']}"
          + (f", needs runner features {', '.join(q['needs'])}" if q.get("needs") else ""))


# walk (docs/terrain/walk-redrocket-sanctuary.md): every key a plan.json test may carry; anything else stops the planning
WALK_PLAN_KEYS = frozenset((
    "label", "travel", "spawn_local", "setup", "start", "waypoints", "goal_radius", "ground", "ground_sha256",
    "bridge", "cells", "crossings", "length_m", "max_legs", "max_leg_m", "speed", "z_tol", "fell_m", "offroute_m",
    "stuck_m", "stuck_k", "shot_every", "drop", "settle_ms", "start_tol", "fresh", "expect", "basis")
    + sky_light.LIGHT_KEYS + console_plan.CONSOLE_KEYS)
SRC_KEY = r"[0-9A-Fa-f]{6}:[A-Za-z0-9_ .-]{1,64}"               # an FO4 reference key as objects.json writes it


def _int(w, key, default, lo, hi):
    v = _num(w, key, default, lo, hi)
    if v != int(v):
        sys.exit(f"{key} in plan.json must be a whole number: {v}")
    return int(v)


def walk_test(n, w, exp_dir):
    """One walk test from a plan.json entry (scripts/terrain/walk_route.py writes them). Positions are in the
    overlay's own frame (the runner adds the merge offset measured at the coc arrival). The judge's ground file
    (walk_ground.json next to plan.json) is pinned by its sha256, checked here and again when judging."""
    label = str(w.get("label") or f"walk{n}")
    unknown = sorted(set(w) - WALK_PLAN_KEYS)
    if unknown:
        sys.exit(f"{label}: unknown plan.json keys {unknown} (known: {sorted(WALK_PLAN_KEYS)})")
    travel = str(w.get("travel") or "")
    if not re.fullmatch(r"coc [A-Za-z0-9_]+", travel):
        sys.exit(f"bad travel in plan.json (coc <cell editor id>): {travel!r}")
    wps = w.get("waypoints")
    if not isinstance(wps, list) or not 2 <= len(wps) <= 400:
        sys.exit(f"{label}: waypoints must be a list of 2..400 [x, y, z, reach]")
    wps = [_vec(p, (4, 5), "waypoint") for p in wps]                # x, y, z, reach[, keep 0 / 1]
    if any(not 0.3 <= p[3] <= 20.0 for p in wps):
        sys.exit(f"{label}: every waypoint's reach must be within 0.3..20 m")
    if any(len(p) == 5 and p[4] not in (0.0, 1.0) for p in wps):
        sys.exit(f"{label}: a waypoint's keep flag is 0 or 1")
    ground = str(w.get("ground") or "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}\.json", ground):
        sys.exit(f"{label}: ground must be a .json file name next to plan.json: {ground!r}")
    gpath = os.path.abspath(os.path.join(exp_dir, ground))
    if not os.path.isfile(gpath):
        sys.exit(f"{label}: ground file {gpath} not found")
    gsha = str(w.get("ground_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", gsha) or sha256(gpath) != gsha:
        sys.exit(f"{label}: {gpath} does not match ground_sha256 (re-plan with scripts/terrain/walk_route.py)")
    safe = re.sub(r"[^A-Za-z0-9_]", "_", label)[:40]
    t = {"id": f"{n:04d}_walk_{safe}", "kind": "walk", "cell": "", "ref": label, "model": label, "travel": travel,
         "spawn_local": _vec(w.get("spawn_local"), (2, 3), "spawn_local"), "setup": bool(w.get("setup", False)),
         "start": _vec(w.get("start") or wps[0][:3], (3,), "start"), "waypoints": wps,
         "goal_radius": _num(w, "goal_radius", 3.0, 0.5, 20), "ground_path": gpath, "ground_sha256": gsha,
         "length_m": _num(w, "length_m", 0.0, 0.0, 100000), "max_legs": _int(w, "max_legs", 60, 1, 400),
         "max_leg_m": _num(w, "max_leg_m", 15.0, 3, 40), "speed": _num(w, "speed", 4.6, 1, 8),
         "z_tol": _num(w, "z_tol", 0.6, 0.1, 3), "fell_m": _num(w, "fell_m", 3.0, 0.5, 50),
         "offroute_m": _num(w, "offroute_m", 10.0, 2, 50), "stuck_m": _num(w, "stuck_m", 0.6, 0.1, 5),
         "stuck_k": _int(w, "stuck_k", 3, 1, 10), "shot_every": _int(w, "shot_every", 3, 1, 50),
         "drop": _num(w, "drop", 1.0, 0, 50), "settle_ms": _int(w, "settle_ms", 6000, 0, 30000),
         "start_tol": _num(w, "start_tol", 3.0, 0.5, 50)}
    if t["setup"] and t["start"] != wps[0][:3]:
        sys.exit(f"{label}: start must be the first waypoint (the setup teleport's target)")
    br = w.get("bridge")
    if br:
        if not isinstance(br, dict) or set(br) - {"src", "edid", "span", "min_reads"} or \
                not re.fullmatch(SRC_KEY, str(br.get("src") or "")):
            sys.exit(f"{label}: bad bridge (want {{\"src\": \"<FO4 ref key>\", \"edid\", \"span\": [s0, s1], "
                     f"\"min_reads\"}}): {br!r}")
        t["bridge"] = {"src": br["src"], "edid": str(br.get("edid") or ""),
                       "span": _vec(br.get("span"), (2,), "bridge span"),
                       "min_reads": _int(br, "min_reads", 2, 0, 50)}
    cross = w.get("crossings") or []
    if not isinstance(cross, list) or len(cross) > 100:
        sys.exit(f"{label}: crossings must be a list")
    t["crossings"] = []
    for c in cross:
        if not isinstance(c, dict):
            sys.exit(f"{label}: bad crossing {c!r}")
        a, b = _vec(c.get("from"), (2,), "crossing from"), _vec(c.get("to"), (2,), "crossing to")
        if any(v != int(v) for v in a + b) or sum(abs(a[k] - b[k]) for k in range(2)) != 1:
            sys.exit(f"{label}: a crossing joins two neighbouring cells: {c!r}")
        t["crossings"].append({"from": [int(v) for v in a], "to": [int(v) for v in b], "s": float(c.get("s", 0.0))})
    if w.get("fresh"):
        t["fresh"] = True
    for k in ("expect", "basis"):
        if w.get(k):
            t[k] = str(w[k])
    return with_extras(t, w, {})


def plan_walk(a):
    """walk tests from <exp-dir>/plan.json (a list, or {"tests": [...]}); see walk_test."""
    staging = os.path.abspath(a.staging)
    esm = os.path.join(staging, "FO4Port.esm")
    if not os.path.exists(esm):
        sys.exit(f"no FO4Port.esm in {staging}: the runner pins and launches a build")
    src = load(os.path.join(a.exp_dir, "plan.json"))
    if isinstance(src, dict):
        src = src.get("tests")
    if not src or not isinstance(src, list) or not all(isinstance(w, dict) for w in src):
        sys.exit(f"no walk tests in {os.path.join(a.exp_dir, 'plan.json')} (a list of test objects)")
    plugins = [p.strip() for p in a.plugins.split(",") if p.strip()]
    if not plugins:
        sys.exit("plan-walk needs --plugins (and --install-exp): a walk is judged on the terrain experiment it runs on, "
                 "pinned here and checked against the install record when a result is recorded")
    cli = light_cli(a)
    tests = [with_extras(walk_test(n, w, os.path.abspath(a.exp_dir)), w, cli) for n, w in enumerate(src)]
    digest = sha256(esm)
    world = os.path.abspath(a.install_exp or a.exp_dir)   # the terrain experiment the walk happens on
    try:
        pinned = experiment_identity(world, plugins)
    except OSError as e:
        sys.exit(f"cannot pin the experiment {world}: {e}")
    q = {"created": now(), "staging": staging, "plugin_sha256": digest, "build_id": digest[:8],
         "commit": subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
         "save": f"fo4sf_test_{digest[:8]}", "plugin_index": a.plugin_index, "hours": [[0, 24]],
         "launch_cell": a.launch_cell, "experiment": os.path.abspath(a.exp_dir), "experiment_identity": pinned,
         "tests": [dict(t, fresh=True) if a.fresh else t for t in (tests[:a.only] if a.only else tests)]}
    q.update(queue_extras(q["tests"], a, world))
    os.makedirs(a.out, exist_ok=True)
    save_atomic(os.path.join(a.out, "queue.json"), q)
    print(f"{len(q['tests'])} walk tests (route {a.exp_dir}) on build {q['build_id']}"
          + (f", installing {world}" if world else "")
          + (f", needs runner features {', '.join(q['needs'])}" if q.get("needs") else ""))


# movable_control (docs/ai/test-queue.md "Movable items: walk, then impulse"): every key a plan.json test may carry
MOVABLE_PLAN_KEYS = frozenset((
    "label", "model", "travel", "base", "base_edid", "mass_kg", "set_mass_kg", "mass_probe", "mass_wait_ms", "spot",
    "heading", "stand_m", "park_m", "walk_ms", "settle_ms", "spawn_wait_ms", "handle_tol", "drop", "impulse_dv",
    "impulse_wait_ms", "moved_m", "reach_m", "settle_m", "fresh", "expect", "basis") + console_plan.CONSOLE_KEYS)


def movable_test(n, w, formids=None, items=None, plugin_index="02"):
    """One movable_control test from a plan.json entry: an item placed with placeatme at `spot` in a vanilla cell (a
    vanilla Starfield base, or a converted one of the pinned build by its EditorID), the player 1.1 m before it walks over
    it along `heading`, then the impulse ladder when the walk did not move it. Everything qstep.ps1 types is built and
    validated here (the coc travel, 8-hex form ids, SetRigidBodyMass / ApplyHavokImpulse with finite numbers in range,
    the GetMass probe) and checked again by qstep."""
    label = str(w.get("label") or f"item{n}")
    unknown = sorted(set(w) - MOVABLE_PLAN_KEYS)
    if unknown:
        sys.exit(f"{label}: unknown plan.json keys {unknown} (known: {sorted(MOVABLE_PLAN_KEYS)})")
    travel = str(w.get("travel") or "")
    if not re.fullmatch(r"coc [A-Za-z0-9_]+", travel):
        sys.exit(f"bad travel in plan.json (coc <cell editor id>): {travel!r}")
    if bool(w.get("base")) == bool(w.get("base_edid")):
        sys.exit(f"{label}: give exactly one of base (8 hex digits, the form id in the load order) and base_edid "
                 f"(an EditorID of the pinned build's formids.json)")
    model = str(w.get("model") or label)
    if w.get("base"):
        base = str(w["base"])
        if not re.fullmatch(r"[0-9A-Fa-f]{8}", base):
            sys.exit(f"bad base form id in plan.json: {base!r}")
        mass = w.get("mass_kg")
    else:
        edid = str(w["base_edid"])
        local = next((v for k, v in (formids or {}).items() if k in (f"MSTT:{edid}", f"MISC:{edid}")), None)
        if local is None:
            sys.exit(f"{label}: {edid} is not a MoveableStatic of the pinned build (formids.json)")
        base = f"{plugin_index}{int(local):06X}"
        it = next((x for x in (items or {}).values() if x.get("editor_id") == edid), {})
        mass = w.get("mass_kg", (it.get("movable") or {}).get("mass_kg"))
        model = str(w.get("model") or it.get("source") or edid)
        if not it.get("movable"):
            sys.exit(f"{label}: {edid} is not a movable item of the pinned build's manifest")
    if mass is None:
        sys.exit(f"{label}: mass_kg needed (the body's mass; the impulse magnitudes scale with it)")
    mass = _num({"mass_kg": mass}, "mass_kg", 1.0, 0.01, 100000)
    spot = _vec(w.get("spot"), (3,), "spot")
    heading = _num(w, "heading", 0.0, 0.0, 360.0)
    stand_m, park_m = _num(w, "stand_m", 1.1, 0.5, 5.0), _num(w, "park_m", 3.0, 1.0, 20.0)
    if park_m <= stand_m:
        sys.exit(f"{label}: park_m ({park_m}) must be farther than stand_m ({stand_m})")
    h = math.radians(heading)
    park = [round(spot[0] - math.sin(h) * park_m, 3), round(spot[1] - math.cos(h) * park_m, 3), spot[2]]
    dvs = _vec(w.get("impulse_dv", list(IMPULSE_DV)), range(0, 5), "impulse_dv")
    if any(not 0.1 <= dv <= 100 for dv in dvs):
        sys.exit(f"{label}: impulse_dv steps must be within 0.1..100 m/s: {dvs}")
    safe = re.sub(r"[^A-Za-z0-9_]", "_", label)[:40]
    t = {"id": f"{n:04d}_movable_control_{safe}", "kind": "movable_control", "cell": "", "ref": label, "model": model,
         "travel": travel, "base": base.upper(), "mass_kg": mass, "spot": spot, "heading": heading, "park": park,
         "stand_m": stand_m, "walk_ms": int(_num(w, "walk_ms", 900, 100, 5000)),
         "settle_ms": int(_num(w, "settle_ms", 1500, 0, 30000)), "drop": _num(w, "drop", 0.3, 0, 5),
         # the console closed this long after placeatme (the item drops and settles; PickLastRef needs the game to have
         # run, N0_base 2026-10-11), and how close to the spot the ref PickLastRef names must lie
         "spawn_wait_ms": int(_num(w, "spawn_wait_ms", 3000, 500, 30000)),
         "handle_tol": _num(w, "handle_tol", 2.0, 0.3, 10),
         "impulse_wait_ms": int(_num(w, "impulse_wait_ms", 3000, 500, 30000)),
         "moved_m": _num(w, "moved_m", MOVE_M, 0.01, 1.0), "reach_m": _num(w, "reach_m", 0.6, 0.1, 3.0),
         "settle_m": _num(w, "settle_m", 0.1, 0.01, 1.0)}
    if w.get("set_mass_kg") is not None:
        # SetRigidBodyMass <kg> on the confirmed selection before the walk: does the same body move once it is as
        # light as a vanilla item of its size? Its effect is unverified, so the GetMass probe is typed with it and the
        # test is judged only when the probe reads the mass set (judge_movable_control: else INCONCLUSIVE MASS)
        if "mass_probe" in w and not w["mass_probe"]:
            sys.exit(f"{label}: set_mass_kg needs the GetMass probe (a test whose mass is not read back cannot be "
                     f"judged); drop mass_probe: false")
        sm = _num(w, "set_mass_kg", 1.0, 0.1, 1000)
        t["set_mass_kg"], t["set_mass_cmd"] = sm, f"{SET_MASS_CMD} {_fmt(sm, 2)}"
        t["mass_wait_ms"] = int(_num(w, "mass_wait_ms", MASS_WAIT_MS, 200, 10000))
    if w.get("mass_probe") or t.get("set_mass_cmd"):
        # before (and after SetRigidBodyMass, in a session of its own once the game has run) the walk; with set_mass_kg
        # the reading after the set decides whether the test can be judged, otherwise it is only shown
        t["probe_cmd"] = MASS_PROBE
    # the ladder's magnitudes are for the mass the body has during the test
    t["impulses"] = impulse_steps(t.get("set_mass_kg", mass), heading, dvs) if dvs else []
    if w.get("fresh"):
        t["fresh"] = True
    for k in ("expect", "basis"):
        if w.get(k):
            t[k] = str(w[k])
    # whitelisted console lines before the travel / after the arrival (console_plan.py; e.g. GetINI of the character
    # controller's settings), their replies OCR'd into obs.console and shown with the verdict
    return dict(t, **console_plan.console_fields(w, _plan_fail))


def plan_movable(a):
    """movable_control tests from <exp-dir>/plan.json (a list, or {"tests": [...]}); see movable_test. The pinned build
    (--staging) supplies FO4Port.esm, formids.json (base_edid) and the manifest (masses)."""
    staging = os.path.abspath(a.staging)
    esm = os.path.join(staging, "FO4Port.esm")
    if not os.path.exists(esm):
        sys.exit(f"no FO4Port.esm in {staging}: the runner pins and launches a build")
    src = load(os.path.join(a.exp_dir, "plan.json"))
    if isinstance(src, dict):
        src = src.get("tests")
    if not src or not isinstance(src, list) or not all(isinstance(w, dict) for w in src):
        sys.exit(f"no movable_control tests in {os.path.join(a.exp_dir, 'plan.json')} (a list of test objects)")
    formids = load(os.path.join(staging, "formids.json"), {})
    items = {it["source"].lower(): it for it in load(os.path.join(staging, "manifest.json"), {"items": []})["items"]}
    tests = [movable_test(n, w, formids, items, a.plugin_index) for n, w in enumerate(src)]
    labels = [t["ref"] for t in tests]
    if len(set(labels)) != len(labels):
        sys.exit(f"duplicate labels in plan.json: {sorted({x for x in labels if labels.count(x) > 1})}")
    digest = sha256(esm)
    q = {"created": now(), "staging": staging, "plugin_sha256": digest, "build_id": digest[:8],
         "commit": subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
         "save": f"fo4sf_test_{digest[:8]}", "plugin_index": a.plugin_index, "hours": [[0, 24]],
         "launch_cell": a.launch_cell, "experiment": os.path.abspath(a.exp_dir),
         "tests": [dict(t, fresh=True) if a.fresh else t for t in (tests[:a.only] if a.only else tests)]}
    q.update(queue_extras(q["tests"], SimpleNamespace(plugins=""), a.exp_dir))
    os.makedirs(a.out, exist_ok=True)
    save_atomic(os.path.join(a.out, "queue.json"), q)
    print(f"{len(q['tests'])} movable_control tests (experiment {a.exp_dir}) on build {q['build_id']}"
          + (f", needs runner features {', '.join(q['needs'])}" if q.get("needs") else ""))


# ------------------------------------------------------------------------------------------------------------ judging
def light_of(test, obs):
    """The light of a test that asked for a time of day or a weather (sky_light.verdict: the arrival camera before and
    after the commands, and for terrain the probe shots, whose corner median decides), else None."""
    obs = obs or {}
    probes = obs.get("points") if test.get("kind") == "terrain" else None
    return sky_light.verdict(test, obs.get("light"), probes if isinstance(probes, list) else None)


def seg_dist_xy(a, b, p):
    """Horizontal distance from point p to the segment a-b (x, y of 3-tuples)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = dx * dx + dy * dy
    t = 0.0 if n == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n))
    return math.hypot(a[0] + t * dx - p[0], a[1] + t * dy - p[1])


def activate_summary(test, obs):
    """"[activate ...]" for a terrain test with an "activate" block (qstep.ps1: the container menu opened from the console with
    prid <ref> + activate player, captured as activate.png and OCR'd): which of the expected words (the container's name, its
    items) the OCR read. Shown in the detail, never judged: the verdict stays the terrain verdict."""
    want = test.get("activate")
    if not want or not obs:
        return ""
    a = obs.get("activate") or {}
    if a.get("selected") is False:
        return (f"[activate {want.get('ref')}: selection not confirmed (GetIsID {want.get('base')} did not reply 1); "
                "nothing activated]")
    if not a.get("shot"):
        return f"[activate {want.get('ref')}: no capture]"
    text = (a.get("ocr") or "").lower()
    expect = [w for w in (want.get("expect") or []) if w]
    if expect:
        found = [w for w in expect if w.lower() in text]
        return f"[activate {want.get('ref')}: read {found} of {expect}]"
    return f"[activate {want.get('ref')}: {'text read' if text.strip() else 'nothing read'}]"


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
    act = activate_summary(test, obs)
    if act:
        detail = f"{detail} {act}"
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
        return judge_push(test, obs, shot_ok)
    if kind == "movable_control":
        return judge_movable_control(test, obs, shot_ok)
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
        planned = test.get("points")
        if not planned or not all(isinstance(p, dict) and all(
                isinstance(p.get(k), (int, float)) and not isinstance(p.get(k), bool) and math.isfinite(p[k])
                for k in ("x", "y", "expect")) for p in planned):
            # a queue planned before plan-terrain checked its points (#219): nothing to judge a height against
            return "INCONCLUSIVE", "PLAN", f"the test has no points or a non-numeric one: {planned!r:.120}"
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
        v, cls, detail = (judge_npc_combat if test.get("combat_reads") else judge_npc)(test, obs, shot_ok)
        return v, cls, detail + (f" [expected {test['expect']}]" if test.get("expect") else "")
    if kind == "door_trip":
        v, cls, detail = judge_door(test, obs, shot_ok)
        return v, cls, detail + (f" [expected {test['expect']}]" if test.get("expect") else "")
    if kind == "walk":
        v, cls, detail = walk_eval.judge(test, obs, shot_ok)
        return v, cls, detail + (f" [expected {test['expect']}]" if test.get("expect") else "")
    return "INCONCLUSIVE", "KIND", f"unknown kind {kind}"


CLEAR_ECHO = re.compile(r"C[Il1|]ear\s?Conso[Il1|]e", re.I)          # ClearConsole's echo, as parse_npc.py reads it
REFUSED = re.compile(r"not\s?found|unknown|invalid|missing|error|failed|cannot|can't", re.I)


def console_refused(ocr):
    """The refusal the console printed for this session's command (the text after the session's last ClearConsole echo),
    else None."""
    text = str(ocr or "")
    starts = [m.end() for m in CLEAR_ECHO.finditer(text)]
    m = REFUSED.search(text[starts[-1]:] if starts else text)
    return m.group(0) if m else None


def impulse_outcome(test, obs, start):
    """The impulse ladder after a walk that did not move the item, judged from `start` (the item's read after the
    walk): ("moved", step, distance, z drop, record) | ("stuck", steps) when every planned impulse was typed on a
    confirmed selection and read back without a move | ("incomplete", why) | None when no ladder is planned."""
    planned = test.get("impulses") or []
    if not planned:
        return None
    done = [r for r in (obs.get("impulses") or []) if isinstance(r, dict)]
    moved_m = test.get("moved_m", MOVE_M)
    for k, rec in enumerate(done):
        p = parse3(rec.get("read"))
        if p is not None and math.dist(start, p) >= moved_m:
            return "moved", k, math.dist(start, p), start[2] - p[2], rec
    if len(done) == len(planned) and all(r.get("applied") and parse3(r.get("read")) is not None for r in done):
        return "stuck", len(done)
    if not done:
        return "incomplete", "no impulse was applied"
    miss = [str(k + 1) for k, r in enumerate(done) if not r.get("applied")]
    unread = [str(k + 1) for k, r in enumerate(done) if r.get("applied") and parse3(r.get("read")) is None]
    why = []
    if miss:
        why.append(f"impulse {', '.join(miss)} not applied (selection not confirmed)")
    if unread:
        why.append(f"impulse {', '.join(unread)} not read back")
    if len(done) < len(planned):
        why.append(f"{len(done)} of {len(planned)} impulses run")
    return "incomplete", "; ".join(why)


def judge_push(test, obs, shot_ok):
    """movable (an item of the build, walked into) and movable_control (an item placed in a vanilla cell): the walk,
    then, when it did not move the item, the impulse ladder.
    - PASS (movable_control: PASS WALKED): the walk moved it MOVE_M. Only the walk passes a movable test.
    - FAIL ITEMFELL: it dropped through the floor (after the walk or an impulse). FAIL STUCK: every planned impulse was
      typed on a confirmed selection and none moved it (the body does not respond).
    - INCONCLUSIVE ELEVATED (movable): the walk did not reach it because it lies on furniture: more than ELEVATED_M
      above the player's feet (the highest of the reads before and after the walk) while the walk came no closer than
      CONTACT_M, or more than OVERHEAD_M above them (supervised_1011 0007). Final, not counted by the breaker.
    - The walk reached it (closest approach within reach_m) and did not move it: movable FAIL NOTMOVED, whatever the
      ladder showed (an impulse that moved it only adds "the body is simulated" to the detail: the player still cannot
      push it); movable_control PASS IMPULSE when an impulse moved it (the measurement of a control: the body is
      simulated, the walk did not push it), INCONCLUSIVE IMPULSE when the ladder did not finish, FAIL NOTMOVED without
      a ladder.
    - Otherwise INCONCLUSIVE MISSED, with what the ladder showed."""
    control = test["kind"] == "movable_control"
    b, a_ = parse3(obs.get("item_before")), parse3(obs.get("item_after"))
    pe = parse3(obs.get("player_end"))
    if b is None or a_ is None or pe is None or not (shot_ok(obs.get("shot_before")) and shot_ok(obs.get("shot_after"))):
        return "INCONCLUSIVE", "UNREAD", "item or player position not read, or a screenshot missing"
    moved = math.dist(b, a_)
    if a_[2] < b[2] - 1.0:
        return "FAIL", "ITEMFELL", f"item dropped {b[2] - a_[2]:.1f} m"
    reach = math.hypot(pe[0] - b[0], pe[1] - b[1])
    # the walk runs from player_start to player_end: its closest approach decides whether the player reached the
    # item (batch_full 2026-10-12: the player walked straight over a book, 0.01 m from it, and ended 3.2 m past
    # it; judged on the end point alone it was MISSED, and six of those switched the whole kind off)
    ps = parse3(obs.get("player_start"))
    how = f"player reached it ({reach:.2f} m)"
    if ps is not None:
        near = seg_dist_xy(ps, pe, b)
        if near < reach:
            reach, how = near, f"player passed {near:.2f} m from it (walked {math.hypot(pe[0] - ps[0], pe[1] - ps[1]):.1f} m)"
    if moved >= test.get("moved_m", MOVE_M):
        return "PASS", "WALKED" if control else "PASS", f"item moved {moved:.2f} m" + (f" ({how})" if control else "")
    walk = f"{how} but it moved {moved:.3f} m"
    imp = impulse_outcome(test, obs, a_)
    note = ""
    if imp and imp[0] == "moved":
        _, k, d, drop, rec = imp
        what = f"ApplyHavokImpulse {rec.get('magnitude')} (dv {rec.get('dv')} m/s, step {k + 1})"
        if drop > 1.0:
            return "FAIL", "ITEMFELL", f"{walk}; {what} dropped it {drop:.1f} m"
        note = f"; {what} then moved it {d:.2f} m: the body is simulated"
    elif imp and imp[0] == "stuck":
        top = max(r.get("dv", 0) for r in test["impulses"])
        return "FAIL", "STUCK", f"{walk}; {imp[1]} impulses up to dv {top} m/s did not move it either"
    elif imp:
        note = f"; the impulse ladder did not finish: {imp[1]}"
    # the player's feet: the highest read of the walk (a player who climbed onto the furniture reached its height)
    feet = max(ps[2], pe[2]) if ps is not None else pe[2]
    elev = b[2] - feet
    if not control and (elev > OVERHEAD_M or (elev > ELEVATED_M and reach > CONTACT_M)):
        where = "above the player's head" if elev > OVERHEAD_M else "on furniture"
        return "INCONCLUSIVE", "ELEVATED", (f"the item lies {elev:.2f} m above the player's feet ({where}) and the walk "
                                            f"came no closer than {reach:.2f} m: it did not reach it; it moved {moved:.3f} m{note}")
    if reach > test.get("reach_m", 1.0):
        return "INCONCLUSIVE", "MISSED", f"player came no closer than {reach:.2f} m to the item{note}"
    if not control:
        # the walk reached it and did not push it: the failure this test exists to find, whatever an impulse did
        return "FAIL", "NOTMOVED", f"{walk}{note}"
    if imp and imp[0] == "moved":
        return "PASS", "IMPULSE", f"{walk}{note}"
    if imp:                                               # the ladder was planned but did not finish
        return "INCONCLUSIVE", "IMPULSE", f"{walk}{note}"
    return "FAIL", "NOTMOVED", walk


MASS_ECHO = re.compile(r"G[e3]t\s?M[a@]ss", re.I)                    # the probe's echo (and a reply naming it)
MASS_NUM = re.compile(r"(?<![\w.])-?\d+(?:[.,]\d+)?(?![\w.])")
# cf "Actor.PathToReference" (N0_cf, 2026-10-11) replied "No script named Actor is attached to the object"
NO_SCRIPT = re.compile(r"no\s?script", re.I)


def mass_read(ocr):
    """(kg, "") read from a GetMass probe's console session, or (None, why): the one number printed after the probe's
    echo in the text after the session's last ClearConsole echo. The reply's format is unseen (docs/ai/test-queue.md):
    a refusal, no echo, no number or several different numbers read nothing."""
    text = str(ocr or "")
    starts = [m.end() for m in CLEAR_ECHO.finditer(text)]
    text = text[starts[-1]:] if starts else text
    bad = NO_SCRIPT.search(text) or REFUSED.search(text)
    if bad:
        return None, f"the console refused it ({bad.group(0)!r})"
    echo = MASS_ECHO.search(text)
    if not echo:
        return None, "its echo was not read"
    vals = sorted({round(float(x.replace(",", ".")), 2) for x in MASS_NUM.findall(text[echo.end():])})
    if len(vals) != 1:
        return None, ("no number after it" if not vals else f"several numbers after it ({', '.join(map(str, vals))})")
    return vals[0], ""


def mass_ok(read, want):
    """GetMass read the mass SetRigidBodyMass set: within 5 %, at least 0.25 kg."""
    return read is not None and abs(read - want) <= max(0.25, 0.05 * want)


def judge_movable_control(test, obs, shot_ok):
    """movable_control: the player at the spot (within 1 m, and SPOT_Z_M of its height: on the floor there), the item
    placed and its handle confirmed (PickLastRef's id, GetSelf, GetIsID <base> 1, within handle_tol of the spot and
    SPAWN_Z_M of its height), the player at the stand point on the same floor; with set_mass_kg, SetRigidBodyMass typed
    and not refused and GetMass read back as the mass set (else INCONCLUSIVE MASS: a mass that did not change would
    otherwise read as "thinness, not mass"); the item at rest before the walk (its spawn read and its read before the
    walk within settle_m); then judge_push."""
    sp = parse3(obs.get("player_spot"))
    spot = test["spot"]
    if sp is None or math.hypot(sp[0] - spot[0], sp[1] - spot[1]) > 1.0:
        return "INCONCLUSIVE", "START", f"the player was not read at the spot ({obs.get('player_spot')})"
    if abs(sp[2] - spot[2]) > SPOT_Z_M:
        return "INCONCLUSIVE", "START", (f"the player was read {sp[2] - spot[2]:+.2f} m from the spot's height: not on "
                                         f"the open floor planned there ({obs.get('player_spot')})")
    s = obs.get("spawn") or {}
    if not s.get("confirmed"):
        return "INCONCLUSIVE", "SPAWN", f"the placed item's handle was not confirmed: {s.get('why') or 'no spawn read'}"
    r0 = parse3(s.get("read"))
    if r0 is not None and abs(r0[2] - spot[2]) > SPAWN_Z_M:
        return "INCONCLUSIVE", "SPAWN", (f"the placed item was read {r0[2] - spot[2]:+.2f} m from the spot's height: not "
                                         f"on the floor there ({s.get('read')})")
    ps = parse3(obs.get("player_start"))
    if ps is not None and abs(ps[2] - spot[2]) > SPOT_Z_M:
        return "INCONCLUSIVE", "START", (f"the player was read {ps[2] - spot[2]:+.2f} m from the spot's height at the "
                                         f"stand point: the walk would not start on the spot's floor")
    mass_note = ""
    if test.get("set_mass_cmd"):
        m = obs.get("set_mass") or {}
        if not m.get("typed"):
            return "INCONCLUSIVE", "SETMASS", f"{test['set_mass_cmd']} not typed (selection not confirmed)"
        refused = console_refused(m.get("ocr"))
        if refused:
            return "INCONCLUSIVE", "SETMASS", f"the console refused {test['set_mass_cmd']} ({refused!r})"
        probe = obs.get("mass_probe") or {}
        before, _ = mass_read(probe.get("before"))
        if probe.get("after") is None:
            after, why = None, probe.get("after_note") or "its reply was not captured"
        else:
            after, why = mass_read(probe["after"])
        was = f" (before: {_fmt(before, 2)} kg)" if before is not None else ""
        if after is None:
            return "INCONCLUSIVE", "MASS", (f"GetMass was not read after {test['set_mass_cmd']}: {why}{was}; the mass "
                                            f"the walk met is unknown")
        if not mass_ok(after, test["set_mass_kg"]):
            return "INCONCLUSIVE", "MASS", (f"GetMass read {_fmt(after, 2)} kg after {test['set_mass_cmd']}{was}: the "
                                            f"mass set did not take")
        mass_note = f" [GetMass {_fmt(after, 2)} kg after {test['set_mass_cmd']}{was}]"
    b = parse3(obs.get("item_before"))
    if r0 is not None and b is not None and math.dist(r0, b) > test.get("settle_m", 0.1):
        return "INCONCLUSIVE", "SETTLE", (f"the item was still moving before the walk: {math.dist(r0, b):.2f} m between "
                                          f"its spawn read and its read before the walk")
    v, c, d = judge_push(test, obs, shot_ok)
    return v, c, d + mass_note


def _add(p, off):
    return [p[k] + off[k] for k in range(3)]


def _whole_cells(delta, radius, cell=100.0):
    """(dx, dy) when delta is a whole number of Starfield cells in x and y (within radius) and level in z, else None:
    an arrival the overlay merge put at another cell offset than the coc arrival's."""
    dx, dy = round(delta[0] / cell) * cell, round(delta[1] / cell) * cell
    if (dx or dy) and math.hypot(delta[0] - dx, delta[1] - dy) <= radius and abs(delta[2]) <= radius:
        return dx, dy
    return None


def _door_ref_note(test, obs, off):
    """The getpos of the outside door's reference (obs.door_read, read after the coc arrival): where the engine reports
    the persistent door. Our persistent XMarker anchors read their unmerged local position (exp1d / exp2b), a vanilla
    persistent ref in LC172World read the merged one; the door read its local position in the first live runs
    (2026-10-13), where a last try 1 m from its merged position did not load (docs/slice/door-frames.md)."""
    ref = test["outside"].get("ref")
    if not ref:
        return None
    rd = parse3(obs.get("door_read"))
    if rd is None:
        return f"getpos of door {ref}: not read"
    return f"getpos of door {ref} read {obs.get('door_read')}: {_merge_frame(rd, test['outside']['door'], off)}"


def _merge_frame(read, local, off):
    """Where a getpos read puts a ref placed at `local` in the overlay's own frame: merged (local + offset), its
    unmerged local position, or neither."""
    dm, dl = math.dist(read, _add(local, off)), math.dist(read, local)
    return ("its merged position" if dm <= 1.0 else "its unmerged local position (as our anchors read)" if dl <= 1.0
            else f"neither its merged ({dm:.1f} m) nor its local position ({dl:.1f} m): another ref?")


def _probe_notes(test, obs, off):
    """The merge probes (test.probes: refs at known local positions, each stored differently): merged or not."""
    reads = {str(x.get("ref", "")).upper(): x.get("read") for x in obs.get("probe_reads") or [] if isinstance(x, dict)}
    out = []
    for q in test.get("probes") or []:
        rd = parse3(reads.get(q["ref"]))
        where = "not read" if rd is None else f"read {reads.get(q['ref'])}: {_merge_frame(rd, q['local'], off)}"
        out.append(f"probe {q['ref']} ({q['what']}) {where}")
    return out


def _turn(a, b):
    """The smallest angle between two headings (degrees)."""
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _walk_evidence(test, x, route, door):
    """None when a leg's record shows the planned walk, else why not. A leg with a planned route must have walked it:
    mode route, no teleport (the near last try excepted: the trip is NEARONLY then), its steps read on this side, each
    within one W hold of the read before, past every intermediate waypoint (within radius) and up to the door. The
    arrival, save and load positions alone cannot tell a walked route from a teleport (Codex's review of PR #107,
    2026-10-14: PASS with mode route and no steps, or with a teleport and trigger walk)."""
    mode, want = x.get("mode") or "straight", "route" if route else "straight"
    if mode != want:
        return f"mode {mode}, planned {want}"
    if not route or x.get("trigger") == "near":
        return None
    if x.get("teleports") or 0:
        return f"{x['teleports']} teleport(s) in a routed leg"
    steps = [s for s in x.get("steps") or [] if isinstance(s, dict)]
    reads = [parse3(s.get("read")) for s in steps]
    if sum(r is None for r in reads[:-1]):                  # only the step that loaded (or ended the walk) has none
        return f"{sum(r is None for r in reads[:-1])} step(s) not read on this side"
    chain = [parse3(x.get("start_read"))] + [r for r in reads if r is not None]
    if len(chain) < 2:
        return "no route step read on this side"
    hold = float(test.get("route_hold_ms", 2000))
    reach = [max(float(s.get("ms") or hold), 300.0) / 1000.0 * ROUTE_MAX_SPEED + 1.0 for s in steps]
    for k in range(1, len(chain)):
        d = math.dist(chain[k - 1], chain[k])
        if d > reach[k - 1]:
            return f"step {k} read {d:.1f} m from the read before, beyond the {reach[k - 1]:.0f} m its hold walks"
    R = test.get("radius", 4.0)
    for n, wp in enumerate(route[1:-1], 1):
        off = min(seg_dist_xy(chain[k - 1], chain[k], wp) for k in range(1, len(chain)))
        if off > R:
            return f"waypoint {n} passed no closer than {off:.1f} m"
    end = (reach[len(chain) - 1] if len(chain) - 1 < len(steps) else 1.0) + test.get("activate_m", 3.0)
    d = math.dist(chain[-1], door)
    if d > end:
        return f"the last read on this side was {d:.1f} m from the door, beyond the {end:.0f} m the last hold walks"
    return None


def judge_door(test, obs, shot_ok):
    """door_trip (docs/slice/redrocket-door.md, docs/slice/door-frames.md). The legs must all be observed, in order: the
    coc arrival (settled, gives the overlay's merge offset O = arrival - spawn_local), "in" (from outside.start + O, or
    with outside.route from its first waypoint + O, the coc arrival itself, through the door to inside.arrival), "out"
    (from inside.start, or inside.route's first waypoint, the interior arrival, through the door to outside.arrival +
    O: the merged exterior frame), the save (its file written) and the load (the player back at the saved spot after
    being moved away, or a loading screen seen; settled, on outside.ground + O.z). A position not read, a start not
    reached or a screenshot missing is INCONCLUSIVE, never PASS; the first leg that fails decides.
    Which side of the door the player is on comes from the position alone: the interior frame (within frame_m of the
    interior door), the merged exterior frame (within frame_m of the outside door + O) or the unmerged one (of the
    outside door). player.GetInCell is never judged: with the cell's EditorID the console refuses it ("Item
    'FO4Port_RedRocket01' not found for parameter Cell.", first live run 2026-10-13); with inside.cell_id its reply is
    reported as a diagnostic. NOLOAD needs the player standing (settled) within activate_m of the door with no load.
    Facing: with <side>.arrival_heading the heading read at the arrival (getangle z, before anything turns the player)
    must be within facing_tol of it (the XTEL marker's rotation), and after the load the saved heading must come back:
    FAIL FACING, or INCONCLUSIVE NOFACING when not read; position failures come first. A leg that loaded only from the
    last-try teleport (trigger near) makes the whole trip INCONCLUSIVE NEARONLY: the door works, walking in is not
    shown. A leg that arrived without its record showing the planned walk (_walk_evidence: a routed leg's mode, no
    teleport, continuous step reads past every waypoint up to the door) is INCONCLUSIVE ROUTE."""
    if not obs.get("offset"):
        why = obs.get("offset_missing") or "the arrival was not read or never settled"
        return "INCONCLUSIVE", "ANCHOR", f"no merge offset ({why}): no door was tried"
    off = (list(obs["offset"]) + [0.0, 0.0, 0.0])[:3]
    o, i = test["outside"], test["inside"]
    R, ST = test.get("radius", 4.0), test.get("start_tol", 3.0)
    MOVED, ACT = test.get("moved_m", 30.0), test.get("activate_m", 3.0)
    FRAME, FTOL = test.get("frame_m", 150.0), test.get("facing_tol", 20.0)
    legs = {x.get("name"): x for x in obs.get("legs") or [] if isinstance(x, dict)}
    notes = [f"offset {off[0]:.1f}, {off[1]:.1f}, {off[2]:.2f}"]
    ref_note = _door_ref_note(test, obs, off)
    probe_notes = _probe_notes(test, obs, off)
    facing = []                                                  # (what, got, want)

    def frame(p):
        """The frame a position is in (interior / merged exterior / unmerged exterior), or None."""
        d = {"interior": math.dist(p, i["door"]), "merged exterior": math.dist(p, _add(o["door"], off)),
             "unmerged exterior": math.dist(p, o["door"])}
        name = min(d, key=d.get)
        if name == "unmerged exterior" and d["merged exterior"] <= FRAME:
            name = "merged exterior"                             # no merge offset: the two coincide
        return name if d[name] <= FRAME else None

    def cell_note(x):
        if x.get("incell") is None and not x.get("incell_error"):
            return ""
        return (f", GetInCell {i.get('cell_id') or i['cell']} {x.get('incell') if x.get('incell') is not None else 'unread'}"
                + (f" ({x['incell_error']})" if x.get("incell_error") else "") + " (a diagnostic, not judged)")

    def leg(name, start, door, arrival, unmerged=None, route=None):
        """None when the leg passed (notes appended), else (verdict, class, detail). unmerged: the arrival point in
        the world's own frame (out leg), to tell an arrival without the overlay's merge offset. route: the planned
        waypoints in the frame the leg's reads are in, whose walk the record must show (_walk_evidence)."""
        x = legs.get(name)
        if not x:
            return "INCONCLUSIVE", "UNREAD", f"{name}: the leg did not run"
        st = parse3(x.get("start_read"))
        if st is None or math.hypot(st[0] - start[0], st[1] - start[1]) > ST:
            got = "not read" if st is None else f"read {math.hypot(st[0] - start[0], st[1] - start[1]):.1f} m away"
            return "INCONCLUSIVE", "START", f"{name}: the start {'of the route' if x.get('mode') == 'route' else 'in front of the door'} was not reached ({got})"
        steps = [s for s in x.get("steps") or [] if isinstance(s, dict)]
        how = (f"trigger {x.get('trigger') or 'none'} after {x.get('walked_ms', 0)} ms of walking"
               + (f" along the route ({len(steps)} steps, {x.get('teleports', 0)} teleports)" if x.get("mode") == "route" else "")
               + (", prompt seen" if x.get("prompt") else "")
               + (", the load found by the position (two reads agree; no loading screen seen)" if x.get("load_by") == "position" else "")
               + (f", walk stopped: {x['walk_stopped']}" if x.get("walk_stopped") else "")
               + (f", last try skipped: {x['near_skipped']}" if x.get("near_skipped") else ""))
        rejected = [c for c in x.get("checks") or [] if isinstance(c, dict) and c.get("rejected")]
        if rejected:
            how += f", {len(rejected)} read(s) rejected ({', '.join(sorted({c['rejected'] for c in rejected}))})"
        end = parse3(x.get("arrival_read"))
        seen = bool(x.get("load_seen"))
        loaded = seen or x.get("load_by") == "position"
        inside = name == "in"
        if end is None:
            return "INCONCLUSIVE", "UNREAD", f"{name}: arrival not read ({how})"
        if not shot_ok(x.get("shot")):
            return "INCONCLUSIVE", "NOSHOT", f"{name}: no arrival screenshot"
        settled = bool(x.get("arrival_settled"))
        if math.dist(end, st) < MOVED:                           # the player is still on this side of the door
            dd = math.dist(end, door)
            if seen:
                return ("INCONCLUSIVE", "NOMOVE", f"{name}: the HUD went away (a load?) but the player stayed "
                        f"{dd:.1f} m from the door: a menu or popup, not a load ({how})")
            near_reads = [p for p in (parse3(c.get("read")) for c in x.get("checks") or [] if isinstance(c, dict)
                                      and not c.get("rejected"))
                          if p is not None and math.dist(p, st) < MOVED]
            closest = min([dd] + [math.dist(p, door) for p in near_reads])
            if dd > ACT:
                return ("INCONCLUSIVE", "NOREACH", f"{name}: no load, but the player ended {dd:.1f} m from the door, "
                        f"outside its {ACT:g} m range (closest read {closest:.1f} m): the door was not tried ({how})")
            if not settled:
                return "INCONCLUSIVE", "UNREAD", f"{name}: no load, {dd:.1f} m from the door but still moving ({how})"
            return "FAIL", "NOLOAD", (f"{name}: no load: the player stood {dd:.1f} m from the door, inside its "
                                      f"{ACT:g} m range, after {how}"
                                      + (f", teleported {x['near_m']} m from it as a last try" if x.get("near_m") else "")
                                      + cell_note(x) + (f"; {ref_note}" if ref_note and inside else ""))
        d = math.dist(end, arrival)
        if not settled and end[2] < arrival[2] - 3.0 and math.hypot(end[0] - arrival[0], end[1] - arrival[1]) <= R:
            return ("FAIL", "FELL", f"{name}: arrived over the arrival point but falling (z {end[2]:.1f}, "
                    f"{arrival[2] - end[2]:.1f} m below it, not settled): no floor or ground there; {how}")
        if d <= R:
            if not settled:
                return "INCONCLUSIVE", "UNREAD", f"{name}: arrived {d:.1f} m from the arrival point, still moving"
            why = _walk_evidence(test, x, route, door)
            if why:                                              # arrived, but the record does not show the walk
                return "INCONCLUSIVE", "ROUTE", f"{name}: arrived, but the walk is not shown: {why} ({how})"
            notes.append(f"{name}: arrived {d:.1f} m from the {'interior' if inside else 'merged exterior'} arrival "
                         f"point ({frame(end) or 'no known frame'} frame){cell_note(x)}, {how}, "
                         + (f"load {x['load_s']} s" if x.get("load_s") is not None else "load time not seen"))
            want = (i if inside else o).get("arrival_heading")
            if want is not None:
                facing.append((f"{name} arrival", x.get("arrival_heading"), want))
            return None
        if unmerged is not None:                                 # out: the arrival in the world's own frame
            dl = math.dist(end, unmerged)
            if dl <= R:
                return ("FAIL", "UNMERGED", f"{name}: arrived {dl:.1f} m from the arrival point's UNMERGED position "
                        f"(the overlay's own frame, offset not applied); {how}")
            wc = _whole_cells([end[k] - arrival[k] for k in range(3)], R)
            if wc:
                return ("FAIL", "REMERGED", f"{name}: arrived at the arrival point shifted by {wc[0]:+.0f}, {wc[1]:+.0f} m "
                        f"(whole cells): the overlay merged at another offset than at the coc arrival; {how}")
        fr = frame(end)
        far = "interior" if inside else "merged exterior"
        if loaded and fr == far:
            return ("FAIL", "ELSEWHERE", f"{name}: loaded into the {far} frame but {d:.1f} m from the arrival point; {how}")
        if loaded and fr is not None and fr != far:
            return ("FAIL", "WRONGCELL", f"{name}: loaded, but the position is in the {fr} frame, {d:.1f} m from the "
                    f"arrival point; {how}")
        return "INCONCLUSIVE", "ELSEWHERE", f"{name}: ended {d:.1f} m from the arrival point ({fr or 'no known'} frame; {how})"

    o_start = _add((o.get("route") or [o["start"]])[0], off)
    i_start = (i.get("route") or [i["start"]])[0]
    o_door, o_arr = _add(o["door"], off), _add(o["arrival"], off)
    r = leg("in", o_start, o_door, i["arrival"], route=[_add(p, off) for p in o["route"]] if o.get("route") else None)
    if r:
        return r[0], r[1], f"{r[2]}; {'; '.join(notes + probe_notes)}"
    r = leg("out", i_start, i["door"], o_arr, unmerged=o["arrival"], route=i.get("route"))
    if r:
        return r[0], r[1], f"{r[2]}; {'; '.join(notes + probe_notes)}"
    out_read = parse3(legs["out"].get("arrival_read"))
    ground = o.get("ground")
    if ground is not None:
        notes.append(f"out arrival z {out_read[2] - off[2]:.2f} (ground {ground:.2f})")
    if ref_note:
        notes.append(ref_note)
    notes += probe_notes
    sv = obs.get("save") or {}
    if not sv.get("found"):
        why = sv.get("why") or ("not checked" if not sv else "no file")
        return "INCONCLUSIVE", "NOSAVE", f"save {test['save']}: file not seen ({why}); {'; '.join(notes)}"
    rl = obs.get("reload") or {}
    rd = parse3(rl.get("read"))
    away = parse3(rl.get("away_read"))                      # where the player was moved to before the load
    moved_away = away is not None and math.dist(away, out_read) > 5.0
    if rd is None or not shot_ok(rl.get("shot")):
        if not rl.get("load_seen"):
            return ("INCONCLUSIVE", "RELOAD_UNSEEN", f"load {test['save']}: no loading screen seen and no position "
                    f"read after it; {'; '.join(notes)}")
        return "INCONCLUSIVE", "UNREAD", f"load: position not read or no screenshot; {'; '.join(notes)}"
    dr = math.dist(rd, out_read)
    tol = test.get("reload_tol", 1.0)
    if moved_away and math.dist(rd, away) <= tol:
        return ("INCONCLUSIVE", "RELOAD_UNSEEN", f"load {test['save']}: the player is still where it was moved before "
                f"the load ({math.dist(away, out_read):.1f} m from the saved spot): the load did not happen; "
                f"{'; '.join(notes)}")
    if not rl.get("load_seen") and not moved_away:          # moved away and gone from there: the load moved the player
        return ("INCONCLUSIVE", "RELOAD_UNSEEN", f"load {test['save']}: no loading screen seen and the player was not "
                f"moved away before it, so the read after it says nothing; {'; '.join(notes)}")
    z0 = (ground + off[2]) if ground is not None else out_read[2]
    if rd[2] < z0 - 3.0:
        return "FAIL", "FELL", f"after the load z {rd[2]:.2f}, {z0 - rd[2]:.1f} m below the ground; {'; '.join(notes)}"
    if dr > tol:
        return ("FAIL", "RELOAD", f"after the load {dr:.2f} m from where the save was made ({rl.get('read')} vs "
                f"{legs['out'].get('arrival_read')}); {'; '.join(notes)}")
    if not rl.get("settled"):
        return "INCONCLUSIVE", "UNREAD", f"after the load the position never settled; {'; '.join(notes)}"
    if ground is not None and abs(rd[2] - z0) > test.get("ground_tol", 1.0):
        return ("FAIL", "OFFGROUND", f"after the load z {rd[2] - off[2]:.2f} in the world's frame, ground {ground:.2f} "
                f"(off by {rd[2] - z0:+.2f} m); {'; '.join(notes)}")
    notes.append(f"save {test['save']} written ({sv.get('size')} B); after the load {dr:.2f} m from the saved spot"
                 + (f", z {rd[2] - z0:+.2f} m from the ground" if ground is not None else "")
                 + f"{cell_note(rl)}, load {rl.get('load_s')} s, "
                 + ("loading screen seen" if rl.get("load_seen") else "no loading screen seen")
                 + (f", moved {math.dist(away, out_read):.1f} m away before it" if moved_away else ""))
    if o.get("arrival_heading") is not None:                # the saved facing must come back with the load
        facing.append(("heading after the load (the saved one)", rl.get("heading"), legs["out"].get("arrival_heading")))
    bad, unread = [], []
    for what, got, want in facing:
        if got is None or want is None:
            unread.append(what)
            continue
        dt = _turn(float(got), float(want))
        (bad if dt > FTOL else notes).append(f"{what} heading {float(got):.1f}, want {float(want):.1f} "
                                             f"({dt:.1f} degrees off, tolerance {FTOL:g})")
    if bad:
        return "FAIL", "FACING", f"{'; '.join(bad)}; {'; '.join(notes)}"
    near = [n for n in ("in", "out") if legs[n].get("trigger") == "near"]
    if near:
        return ("INCONCLUSIVE", "NEARONLY", f"the door loads, but the {' and '.join(near)} leg"
                f"{'s' if len(near) > 1 else ''} loaded only from the last-try teleport 1 m from the door: walking in "
                f"is not shown; {'; '.join(notes)}")
    if unread:
        return ("INCONCLUSIVE", "NOFACING", f"facing not read: {', '.join(unread)} (position, save and load passed); "
                f"{'; '.join(notes)}")
    return "PASS", "PASS", "; ".join(notes)


def judge_npc(test, obs, shot_ok):
    """npc_nav (PR #61 3.4). The actor spawns at A, the player (the walk target) stands at B. Positions are in the
    worldspace's own frame plus the measured offset (anchor or spawn), like terrain points. The spawn counts only when
    qstep.ps1 confirmed the handle (PickLastRef's id, GetSelf naming no other ref, GetIsID 1, at the player at A); only
    reads whose selection the game confirmed (prid <id>, GetIsID 1 in the same console session) and that have a
    screenshot count. A baseline (method none, no command) is judged the other way round: PASS when the actor did NOT
    come to B. With the plan keys precommand_m / arrive_progress (N0b) the commanded walk is measured from t0 only:
    an approach before the command beyond precommand_m is INCONCLUSIVE PRECOMMAND, an arrival is a PASS only after
    arrive_progress metres from t0 (else INCONCLUSIVE SHORT), and a baseline FAILs WANDER on the largest approach
    between any two of its reads."""
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
    # from_t0 (plan key arrive_progress): the walk is measured from t0 only, and a baseline by the largest approach
    # between any two of its reads (spawn read and t0 included): wander may start before or after the command
    from_t0 = "arrive_progress" in test
    seq = ([dS] if ps is not None else []) + [d0] + [dist(p) for _, p in good]
    approach, far = 0.0, seq[0]
    for x in seq[1:]:
        approach, far = max(approach, far - x), max(far, x)
    stats = (f"spawn d {dS:.1f} m, d0 {d0:.1f} m, min d {dmin:.1f} m, end d {dend:.1f} m, moved {moved:.1f} m, path "
             f"{path:.1f} m, {len(good)}/{want} reads, last at {good[-1][0].get('t_game')} s ({test['method']})"
             + (f", largest approach {approach:.1f} m" if from_t0 else ""))
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
        prog = max(d0 - dend, dS - dend, early) if not from_t0 else max(d0 - dend, dS - dend, early, approach)
        came = min(dmin, d0) <= test["radius"] or prog >= test["min_progress"]
        if came:
            when = (f" ({early:.1f} m of it before the first read, between the spawn read and t0)"
                    if early >= test["min_progress"] or (d0 <= test["radius"] < dS) else "")
            return ("FAIL", "WANDER", f"came {prog:.1f} m towards B without a command{when}: a control PASS of this "
                    f"actor here says nothing about the command; {stats}")
        if len(good) < want:
            return "INCONCLUSIVE", "UNREAD", f"{len(good)} of {want} reads confirmed: {stats}"
        return "PASS", "PASS", f"stayed away from B without a command: {stats}"
    pre_lim = test.get("precommand_m", test["min_progress"])
    if early >= pre_lim or (d0 <= test["radius"] < dS):
        # it came for the player before the command was typed (between the spawn read and t0): whatever follows is
        # not the command's doing alone (a hostile actor, or a citizen that walks up to the player: N0_cf, N1c), so
        # neither a PASS nor a FAIL of the command
        return ("INCONCLUSIVE", "PRECOMMAND", f"came {early:.1f} m towards B before the command (spawn read to t0, "
                f"limit {pre_lim:g} m): the walk after it is not the command's alone; {stats}")
    if dist(good[0][1]) <= test["radius"]:
        # at B by the first read: no position on the way was seen, so a warp to the player is not ruled out
        return ("INCONCLUSIVE", "EARLY", f"already at B at the first read ({good[0][0].get('t_game')} s): the walk "
                f"itself was not observed (add an earlier read); {stats}")
    if dmin <= test["radius"] and d0 - dmin >= test.get("arrive_progress", 0.0):
        return "PASS", "PASS", (f"arrived within {test['radius']} m of B" + (
            f", {d0 - dmin:.1f} m closer than at t0" if from_t0 else "") + f": {stats}")
    if d0 - dend >= test["min_progress"]:
        return "PASS", "PASS", f"walked {d0 - dend:.1f} m towards B: {stats}"
    if dmin <= test["radius"]:
        # at the player, but it started too close at t0 for the walk after the command to be told from wandering:
        # neither a PASS (the command's part is too short) nor a FAIL (it did arrive)
        return ("INCONCLUSIVE", "SHORT", f"arrived within {test['radius']} m of B but only {d0 - dmin:.1f} m closer "
                f"than at t0 (needs {test['arrive_progress']:g} m): too short to tell from wandering; {stats}")
    if len(good) < want:
        return "INCONCLUSIVE", "UNREAD", f"{len(good)} of {want} reads confirmed: {stats}"
    if moved < test.get("nomove", 0.5):
        return "FAIL", "NONAV", f"spawned and commanded, never moved: {stats}"
    return "FAIL", "STALLED", f"moved but did not reach B: {stats}"


def combat_read(sample):
    """(state, target, los) of one sample as qstep.ps1 recorded them, each None unless it is a value: the state a small
    integer 0..9, the target an 8-hex form id, LOS 0 / 1. An unreadable reply is never a value (the formats are
    unverified in game: the raw OCR stays in the sample's combat_ocr). Nothing counts when the combat capture's own
    GetIsID (combat_isid) read 0: another ref answered."""
    if not isinstance(sample, dict) or sample.get("combat_isid") == 0:
        return None, None, None
    st, tg, los = sample.get("combat"), sample.get("target"), sample.get("los")
    st = int(st) if isinstance(st, (int, float)) and not isinstance(st, bool) and 0 <= st <= 9 and st == int(st) else None
    tg = tg.upper() if isinstance(tg, str) and re.fullmatch(r"[0-9A-Fa-f]{8}", tg) else None
    los = int(los) if isinstance(los, (int, float)) and not isinstance(los, bool) and los in (0, 1) else None
    return st, tg, los


def judge_npc_combat(test, obs, shot_ok):
    """npc_nav with combat_reads: the verdict comes from the combat manager, not from where the actor walked. PASS
    ENGAGED when any confirmed sample read a combat state >= 1 with the player (00000014) as the target; FAIL NOCOMBAT
    when every expected sample read state 0; INCONCLUSIVE COMBATREAD when the replies were not readable (the formats
    are a hypothesis until the first run), OTHERTARGET when it fought something else. The walk judge's preconditions
    (spawn confirmed, player at B, the command typed) hold here too, and its verdict is kept as detail only (a method
    none test's walk is read as a baseline's: stayed away / came towards B without a command)."""
    walk = judge_npc(dict(test, baseline=test.get("method") == "none"), obs, shot_ok)
    if walk[0] == "INCONCLUSIVE" and walk[1] in ("ANCHOR", "SPAWN", "HANDLE", "TARGET"):
        return walk
    if walk[0] == "INCONCLUSIVE" and walk[1] == "UNREAD" and not obs.get("samples"):
        return walk
    reads = [s for s in obs.get("samples") or []
             if isinstance(s, dict) and s.get("isid") == 1 and shot_ok(s.get("shot"))]
    want = len([x for x in test["reads_s"] if x > 0])
    walk_note = f"walk: {walk[0]} {walk[1]}, {walk[2]}"
    if not reads:
        return "INCONCLUSIVE", "UNREAD", f"no confirmed read after t0 (0 of {want}); {walk_note}"
    rows = [(s.get("t_game"),) + combat_read(s) for s in reads]
    seq = ", ".join(f"t {t} s: state {st if st is not None else '?'} target {tg or '?'} LOS {los if los is not None else '?'}"
                    for t, st, tg, los in rows)
    engaged = [(t, st, tg, los) for t, st, tg, los in rows if st is not None and st >= 1 and tg == PLAYER_REF]
    if engaged:
        t, st, tg, los = engaged[0]
        return "PASS", "ENGAGED", (f"in combat with the player from t {t} s (state {st}, target {tg}, LOS "
                                   f"{los if los is not None else '?'}), {len(engaged)} of {len(rows)} reads; {seq}; "
                                   f"{walk_note}")
    fighting = [(t, st, tg) for t, st, tg, _ in rows if st is not None and st >= 1]
    if fighting:
        t, st, tg = fighting[0]
        if tg is None:
            return ("INCONCLUSIVE", "COMBATREAD", f"combat state {st} at t {t} s but its target was not read (OCR "
                    f"{str(reads[0].get('combat_ocr'))[:80]!r}); {seq}; {walk_note}")
        return ("INCONCLUSIVE", "OTHERTARGET", f"in combat at t {t} s (state {st}) but with {tg}, not the player "
                f"{PLAYER_REF}; {seq}; {walk_note}")
    states = [st for _, st, _, _ in rows if st is not None]
    if len(states) == want and all(st == 0 for st in states):
        return "FAIL", "NOCOMBAT", f"never in combat ({want} of {want} reads state 0); {seq}; {walk_note}"
    missing = [s for s in reads if combat_read(s)[0] is None]
    ocr = str((missing or reads)[0].get("combat_ocr"))[:80]
    return ("INCONCLUSIVE", "COMBATREAD", f"combat state read in {len(states)} of {want} samples, none in combat; "
            f"the reply format is unverified (OCR {ocr!r}); {seq}; {walk_note}")


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
    in the control's own queue (method none: no command), a baseline there passed and none came to B (the actor did
    not come to B on its own, so the control's PASS was the command's doing; a baseline of the other queue, e.g. this
    queue's wander reference in another world, does not vouch for that control). Otherwise: INCONCLUSIVE CONTROL with
    the raw verdict kept in the detail; the runner
    keeps the raw verdict and the report applies the gate again (a control that passes later still counts). PASS
    needs no control (the walk was observed); it gets a note on whether the actor's own baseline credits the command
    (own_baseline_note). No control configured: unchanged. A test with "control_npc" is gated by
    that actor's control and baseline instead of its own (a converted actor judged against the vanilla one). A
    combat_reads test is judged by the combat manager's own replies: no gate, no note."""
    if test.get("combat_reads"):
        return verdict, cls, detail
    if test.get("kind") == "npc_nav" and not test.get("baseline") and verdict == "PASS":
        return verdict, cls, detail + own_baseline_note(qdir, q, test)
    if test.get("kind") != "npc_nav" or test.get("control") or test.get("baseline") or verdict != "FAIL":
        return verdict, cls, detail
    gate_npc = test.get("control_npc") or test.get("npc")
    sources = [qdir] + ([q["control_queue"]] if q.get("control_queue") else [])
    configured, ctrl, base = bool(q.get("control_queue")), [], {}
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
                ctrl.append((d, c["id"], done.get(c["id"])))
            elif c.get("baseline"):
                base.setdefault(d, []).append((c["id"], done.get(c["id"])))
    if not configured:
        return verdict, cls, detail
    raw = f"raw verdict {verdict} {cls}: {detail}"

    def why(group):
        if any(r and r.get("class") == "WANDER" for _, r in group):
            return "did not pass (the actor came to B without a command)"
        return "did not pass" if any(r for _, r in group) else "has no result"
    passed = [(d, i) for d, i, r in ctrl if r and r.get("verdict") == "PASS"]
    if not passed:
        return ("INCONCLUSIVE", "CONTROL",
                f"control ({test.get('method')}, {gate_npc}) {why([(i, r) for _d, i, r in ctrl])}; {raw}")
    # a control's PASS is the command's doing only when the baselines planned next to it (its own queue: the same
    # world, cell and pair) passed, none of them came to B on its own; a baseline of another queue (this queue's own
    # wander reference in another world) says nothing about that control
    refused = []
    for d, i in passed:
        group = base.get(d) or []
        if not group:
            return verdict, cls, detail + f" (control {i} passed)"
        bpass = [j for j, r in group if r and r.get("verdict") == "PASS"]
        if bpass and not any(r and r.get("class") == "WANDER" for _, r in group):
            return verdict, cls, detail + f" (control {i} and baseline {bpass[0]} passed)"
        refused.append(f"control {i} passed but the baseline ({gate_npc}, no command) {why(group)}")
    return "INCONCLUSIVE", "CONTROL", f"{'; '.join(refused)}; {raw}"


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
        for p in stop_files(self.queue_dir):
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


def stop_files(queue_dir):
    """The STOP files that stop a run: the queue's own, the chain folder's STOP_ALL (the queues of one chain share a
    parent folder; watchdog.ps1 honours the same file) and the state folder's testqueue.STOP."""
    return [os.path.join(queue_dir, "STOP"), os.path.join(os.path.dirname(os.path.abspath(queue_dir)), "STOP_ALL"),
            os.path.join(Controls.state_dir, "testqueue.STOP")]


def stop_controls(queue_dir):
    """What a walk step checks between its actions (qstep.ps1 'walk', walk_eval.stop_reason), passed in the step spec:
    the runner is blocked in the step while it runs, so the step itself has to honour the STOP files and the Resource
    Guardian's database (guardian_mode) and end with the input guard's exit code when one trips."""
    return {"files": stop_files(queue_dir), "guardian_db": os.path.join(Controls.state_dir, "guardian.db")}


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


def plugin_order_needed(exp_dir, plugins):
    """True when a staged plugin masters a plugin that neither the game loads on its own nor an earlier plugin of the
    same install provides (e.g. FO4Port.esm, which cycle.ps1's deploy activates after the experiment's plugins): such a
    queue needs a runner whose cycle.ps1 runs exp_install.py order (runner feature plugin_order)."""
    for k, p in enumerate(plugins):
        f = os.path.join(exp_dir, p)
        if not os.path.exists(f):
            continue
        earlier = {x.casefold() for x in plugins[:k]}
        if any(not exp_install.implicit(m) and m.casefold() not in earlier for m in exp_install.plugin_masters(f)):
            return True
    return False


BRIDGE_PLUGIN = "FO4SFBridge.esm"
BRIDGE_PEX = os.path.join("Data", "Scripts", "FO4SF_Bridge.pex")


def apply_bridge(tests, a):
    """plan-* --bridge <staged bridge dir> (docs/ai/test-queue.md "Bridge", 2026-10-14): every test reads the player's
    position from the bridge's log (qstep.ps1 Bridge-Read, runner feature "bridge"; the console only acts) and the
    queue records the staged bridge with the sha256 of its plugin and compiled script. The runner checks those hashes
    and installs the bridge before every launch (bridge_install.py). Returns the queue fields to add ({} without
    --bridge); marks the tests in place."""
    d = getattr(a, "bridge", "") or ""
    if not d:
        return {}
    d = os.path.abspath(d)
    files = {BRIDGE_PLUGIN: os.path.join(d, BRIDGE_PLUGIN), BRIDGE_PEX: os.path.join(d, BRIDGE_PEX)}
    for root, _, names in os.walk(os.path.join(d, "Data")):   # every packed file (FO4SF_Probe.pex and later ones too)
        for n in names:
            p = os.path.join(root, n)
            files[os.path.relpath(p, d)] = p
    missing = [k for k, p in files.items() if not os.path.exists(p)]
    if missing:
        sys.exit(f"--bridge {d}: missing {missing} (scripts/bridge/make_bridge.py stage)")
    for t in tests:
        t["bridge_reads"] = True                              # ("bridge" is taken: a walk plan's bridge deck)
    return {"bridge": {"dir": d, "plugin": BRIDGE_PLUGIN, "sha256": {k: sha256(p) for k, p in files.items()}}}


def bridge_mismatch(br):
    """Why the staged bridge is not the one the queue pinned (apply_bridge), else None: a missing file or a changed
    hash (a re-staged bridge after the plan is another bridge)."""
    for rel, want in (br.get("sha256") or {}).items():
        p = os.path.join(br["dir"], rel)
        if not os.path.exists(p):
            return f"pinned bridge file {p} is missing"
        if sha256(p) != want:
            return f"pinned bridge file {p} changed since the plan"
    return None


def queue_extras(tests, a, exp_dir):
    """queue.json "needs" (runner_features.needs) and "pre_launch": the RUNNER's own exp_install.py (a path relative to
    the checkout the runner runs from: testqueue.py starts it there) installs the experiment when --plugins is given, and
    with --needs it refuses when that runner lacks the features (an exp_install.py from before --needs refuses the
    option itself); without plugins, runner_features.py check does the same. With --bridge, "bridge" (apply_bridge)."""
    out = apply_bridge(tests, a)
    need = runner_features.needs(tests)
    if a.plugins and plugin_order_needed(exp_dir, [p.strip() for p in a.plugins.split(",") if p.strip()]):
        need = sorted(set(need) | {"plugin_order"})
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
NPC_COMBAT_S = NPC_SESSION_S   # combat_reads: one more capture per confirmed read (GetIsID again, the three lines, OCR)
LIGHT_TRY_S = 50        # one time-of-day / weather command: console open, typing, reply capture + OCR, close, two
                        # screenshots and their measures (the second only when the first did not read as asked)
LIGHT_WAIT_MS = 4000    # qstep.ps1's wait after such a command before the screenshot (plan field light_wait_ms)
LIGHT_PROBE_S = 4       # terrain with light: the measure of every probe shot
REPIN_S = 8             # terrain, time_repin: the time command typed again in every probe's teleport session
CONSOLE_CMD_S = 35      # one console_pre / console_post command: open, ~45 characters, capture, OCR, close
MOVETO_S = 100          # after a FO4SF_Probe.MoveTo line: qstep.ps1 waits up to 90 s for the HUD (a cell load), then 3 s
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
    console_pre / console_post: CONSOLE_CMD_S per command (console open, typing, capture, OCR, close), and MOVETO_S
    more for each FO4SF_Probe.MoveTo line (the HUD wait after it)."""
    light = len(sky_light.commands(test)) * (LIGHT_TRY_S + 2 * test.get("light_wait_ms", LIGHT_WAIT_MS) / 1000)
    light += CONSOLE_CMD_S * sum(len(test.get(k) or []) for k in console_plan.CONSOLE_KEYS)
    light += MOVETO_S * sum(1 for k in console_plan.CONSOLE_KEYS for c in test.get(k) or [] if console_plan.is_moveto(c))
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
        per_read = 2 * NPC_SESSION_S + 10 + (NPC_COMBAT_S if test.get("combat_reads") else 0)
        return int(fixed + n * per_read + max(reads) + light)
    if test.get("kind") == "door_trip":
        return door_timeout(test, light)
    if test.get("kind") == "walk":
        return walk_timeout(test, light)
    if test.get("kind") in ("movable", "movable_control"):
        return movable_timeout(test) + int(light)         # console_pre / console_post of movable_control
    return 300


def movable_timeout(test):
    """Worst case of a movable / movable_control step: every impulse is one confirmed selection (Select-Item: up to two
    sessions), the impulse line in its own capture, impulse_wait_ms with the console closed and a confirmed read (two
    sessions). movable_control adds the coc arrival read until it settles, the player to the spot and its read, the
    placeatme session with the player's move to the park point, spawn_wait_ms, the handle (plr; prid + GetSelf; GetIsID +
    getpos), the GetMass probe and SetRigidBodyMass (one selection and a capture each; after SetRigidBodyMass the console
    closed MASS_WAIT_MS, a second selection and the probe again), the player to the stand point and its read, the
    confirmed reads before and after the walk, and the removal (a selection, disable, markfordelete)."""
    per_imp = 4 * NPC_SESSION_S + test.get("impulse_wait_ms", 3000) / 1000 + 10
    imps = len(test.get("impulses") or [])
    if test.get("kind") == "movable":
        return int(300 + 2 * NPC_SESSION_S * bool(imps) + imps * per_imp)
    setm, probe = test.get("set_mass_cmd") is not None, test.get("probe_cmd") is not None
    mass = (((2 + setm + probe) * NPC_SESSION_S if setm or probe else 0)
            + ((3 * NPC_SESSION_S + test.get("mass_wait_ms", MASS_WAIT_MS) / 1000) if setm and probe else 0))
    fixed = (120 + 5 * NPC_READ_S + 12 + 10                     # coc, the HUD back, the arrival until it settles, shot
             + 2 * (30 + test.get("settle_ms", 1500) / 1000 + NPC_READ_S)   # the player to the spot and to the stand
             + NPC_SESSION_S + 15 + test.get("spawn_wait_ms", 3000) / 1000    # placeatme, the move to the park point
             + 3 * NPC_SESSION_S + 10                           # the handle: plr; prid + GetSelf; GetIsID + getpos
             + mass
             + 2 * (2 * NPC_SESSION_S) + 10                     # the item read before and after the walk, two shots
             + test.get("walk_ms", 900) / 1000 + 2 + NPC_READ_S  # the walk and the player's read after it
             + 3 * NPC_SESSION_S)                               # the removal
    return int(fixed + imps * per_imp + 60)


DOOR_CHECK_S = 8        # door_trip: one HUD check while walking (screenshot + hud_visible.py, PowerShell + Python start)
DOOR_READ_S = 25        # door_trip: one readpos.ps1 run after a walk step (console open, getpos x / y / z, OCR, 4 tries)
DOOR_TIMEOUT_CAP_S = 5400   # door_trip: cap of the computed worst case (live trips 8-12 min; routed about 50 min at real step costs)
DOOR_TURN_S = 15        # door_trip route: one player.setangle z console session (open, about 24 characters, close)


def door_timeout(test, light=0.0):
    """Worst case of one door_trip step (qstep.ps1 'door_trip'): the coc arrival read until it settles (5 reads) and
    the door's getpos, per leg the teleport to the start, its read, every walk step with its HUD check and one position
    read (a second HUD check when the read fails), E with a full check before and after it, the full check before the
    1 m teleport, that teleport with its HUD checks, the load (load_wait_s), the arrival read until it settles and
    GetInCell (one console session), then the save, the teleport away with its read and the load with its reads."""
    step_ms = max(test.get("walk_step_ms", 500), 1)
    settle = test.get("settle_ms", 6000) / 1000
    checks = math.ceil(test.get("walk_ms", 8000) / step_ms)
    full_check = 2 * DOOR_CHECK_S + NPC_READ_S             # HUD, Read-Pos (3 runs), HUD again
    leg = (30 + settle + NPC_READ_S + 5
           + checks * (step_ms / 1000 + 2 * DOOR_CHECK_S + DOOR_READ_S)
           + 2 * full_check + DOOR_CHECK_S + 15            # E: checked before and after it, its prompt shot
           + full_check                                    # before the last try
           + 30 + test.get("near_wait_ms", 6000) / 1000 + 4 * DOOR_CHECK_S
           + test.get("load_wait_s", 90) + 3 + 5 * NPC_READ_S + 12 + NPC_SESSION_S + 5)
    fixed = 120 + 5 * NPC_READ_S + 12 + 5 + NPC_READ_S     # coc, the HUD back (up to 90 s), settled, shot, door getpos
    fixed += len(test.get("probes") or []) * NPC_READ_S      # the merge probes' getpos
    save = 30 + 10
    reload = 30 + settle + NPC_READ_S + 30 + 120 + 3 + 5 * (NPC_READ_S + 10) + 12 + NPC_SESSION_S + 5
    legs = 0
    for side in ("outside", "inside"):
        if (test.get(side) or {}).get("route"):
            # a routed leg: no start teleport; per step a turn (one console session), the W hold, a HUD check and a
            # read, a reread when it fails, the confirmation reads of a far read; plus the final steps at the door
            steps = test.get("route_max_steps", 40)
            per = DOOR_TURN_S + test.get("route_hold_ms", 2000) / 1000 + 0.25 + 2 * DOOR_CHECK_S + DOOR_READ_S + NPC_READ_S
            legs += leg - 30 - settle - checks * (step_ms / 1000 + 2 * DOOR_CHECK_S + DOOR_READ_S) \
                + steps * per + 2 * NPC_READ_S + 5 * 10            # + the confirmation reads, the heading reads
        else:
            legs += leg + 5 * 10
    # the sum above is a worst case of worst cases (every read at its 3-run maximum, every route step used): 14,386 s
    # for the routed core64c trip, while live trips took 8-12 min (2026-10-13). A hung step must not hold the game for
    # hours, so the timeout is capped at DOOR_TIMEOUT_CAP_S.
    return int(min(fixed + legs + save + reload + light, DOOR_TIMEOUT_CAP_S + light))


WALK_LEG_S = 60        # walk: one leg, worst case (console open, ClearConsole + three getpos, OCR at up to 4 thresholds,
                       # the controller, setangle, the HUD shot and the popup OCR, up to two more read sessions when the
                       # first fails); the hold adds up to max_leg_m / walk_eval.V_LO seconds


def walk_timeout(test, light=0.0):
    """Worst case of one walk step (qstep.ps1 'walk'): the coc arrival until it settles, the setup teleport and its
    settled read (reverse test), max_legs legs, the end shot. The step itself stops walking 150 s before its budget
    (budget_s = this - 60)."""
    fixed = 120 + 5 * NPC_READ_S + 12 + 10
    setup = (30 + test.get("settle_ms", 6000) / 1000 + 5 * NPC_READ_S + 12 + 10) if test.get("setup") else 0
    hold = min(test.get("max_leg_m", 15.0) / walk_eval.V_LO, walk_eval.MAX_HOLD_MS / 1000)
    legs = test.get("max_legs", 60) * (WALK_LEG_S + hold)
    return int(fixed + setup + legs + 30 + light)


def installed_identity(starfield):
    """What exp_install.py says is installed (its record in the game's Data folder: the staged folder, the plugins and
    the sha256 of every installed file, the packed archive included, and of every staged input), pinned with every
    walk result and checked against the queue's experiment_identity; {"error": ...} when it cannot be read. Read only."""
    p = os.path.join(starfield or "", "Data", exp_install.RECORD)
    try:
        with open(p, encoding="utf-8") as f:
            r = json.load(f)
    except (OSError, ValueError) as e:
        return {"error": f"{type(e).__name__}: {e}"}
    return {"exp_dir": r.get("exp_dir"), "plugins": r.get("plugins"), "files": r.get("files"),
            "source_inputs": r.get("source_inputs"), "packing_policy": r.get("packing_policy"),
            "complete": r.get("complete")}


def experiment_identity(exp_dir, plugins):
    """What a walk queue pins of the experiment it runs on (plan-walk --install-exp / --plugins): the staged folder,
    the plugins in order and the sha256 of every staged input (exp_install.source_inventory: the plugins and the Data
    tree the packed archive is built and verified from). The runner compares the folder with it before a launch
    (Runner.experiment_mismatch) and the install record with it when a result is recorded (install_mismatch): a walk
    judged on another experiment than the planned one is no evidence about it."""
    return {"exp_dir": os.path.abspath(exp_dir), "plugins": list(plugins),
            "inputs": exp_install.source_inventory(exp_dir, plugins)}


def install_mismatch(q, inst):
    """Why the installed experiment (installed_identity) is not the one the queue pinned (experiment_identity), else
    None. A missing or incomplete record, another folder, other plugins or other staged inputs all count."""
    pin = q.get("experiment_identity")
    if not pin:
        return "no experiment pinned when the queue was planned (plan-walk --plugins)"
    if not inst or inst.get("error"):
        return f"no install record: {inst.get('error') if inst else 'nothing read'}"
    if inst.get("complete") is not True:
        return "the experiment install record is incomplete"
    if os.path.normcase(os.path.abspath(inst.get("exp_dir") or "")) != os.path.normcase(pin["exp_dir"]):
        return f"installed experiment {inst.get('exp_dir')!r} is not the pinned {pin['exp_dir']!r}"
    if [str(p).casefold() for p in inst.get("plugins") or []] != [p.casefold() for p in pin["plugins"]]:
        return f"installed plugins {inst.get('plugins')} are not the pinned {pin['plugins']}"
    got = inst.get("source_inputs") or {}
    if got != pin["inputs"]:
        diff = sorted(k for k in set(got) | set(pin["inputs"]) if got.get(k) != pin["inputs"].get(k))
        return f"installed experiment inputs differ from the pinned ones: {diff[:5]}{'...' if len(diff) > 5 else ''}"
    return None


def copy_attempt_logs(bridge_src, out_dir, log):
    """Copy this attempt's evidence logs next to its captures: the bridge's log as bridge.log, and the game's newest
    Papyrus log (Logs/Script/Papyrus.0.log, two folders up from the bridge log) as papyrus.log when it exists: a
    script error there is what stops the bridge mid-attempt (r05_medkit_1015: it stopped at a teleport and the
    session's Papyrus log had rotated away before anyone read it). The game rotates both on every load."""
    try:
        shutil.copy2(bridge_src, os.path.join(out_dir, "bridge.log"))
    except OSError as e:
        log(f"bridge log not copied: {e}")
    papyrus = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(bridge_src))), "Papyrus.0.log")
    if os.path.exists(papyrus):
        try:
            shutil.copy2(papyrus, os.path.join(out_dir, "papyrus.log"))
        except OSError as e:
            log(f"papyrus log not copied: {e}")


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
        extra = {"budget_s": timeout - 60} if test.get("kind") in ("npc_nav", "walk") else {}
        if test.get("kind") == "walk":                    # the owner's stop controls, checked between the walk's actions
            extra["stop"] = stop_controls(self.qdir)
        save_atomic(spec, dict(test, **extra))
        code, out = self._ps("qstep.ps1", ["-Spec", spec, "-Out", out_dir, "-PluginIndex", self.q["plugin_index"]],
                             timeout)
        with open(os.path.join(out_dir, "step.log"), "w", encoding="utf-8") as f:
            f.write(out)
        if self.q.get("bridge"):
            # the bridge's log is this attempt's evidence (positions, acknowledgements, probe replies); the game
            # rotates it on every load and the next launch starts a new one, so a copy goes into the attempt folder
            src = os.environ.get("FO4SF_BRIDGE_LOG") or bridge_log.default_log()
            copy_attempt_logs(src, out_dir, self.log)
        return code

    def pinned_ok(self):
        esm = os.path.join(self.q["staging"], "FO4Port.esm")
        return os.path.exists(esm) and sha256(esm) == self.q["plugin_sha256"]

    def experiment_mismatch(self):
        """Why the staged experiment a walk queue pinned (experiment_identity) is no longer what the plan saw, else
        None: checked before a launch (the launch installs it), as pinned_ok checks FO4Port.esm."""
        pin = self.q.get("experiment_identity")
        if not pin:
            return None
        try:
            now_ = experiment_identity(pin["exp_dir"], pin["plugins"])
        except OSError as e:
            return f"staged experiment {pin['exp_dir']} unreadable: {e}"
        if now_["inputs"] != pin["inputs"]:
            diff = sorted(k for k in set(now_["inputs"]) | set(pin["inputs"]) if now_["inputs"].get(k) != pin["inputs"].get(k))
            return f"staged experiment {pin['exp_dir']} changed since planning: {diff[:5]}{'...' if len(diff) > 5 else ''}"
        return None

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
            why = self.experiment_mismatch()
            if why:
                self.log(f"{why}: stopping")
                return "stop"
            br = self.q.get("bridge")
            if br:                                        # the observation bridge, installed before every launch
                why = bridge_mismatch(br)
                if why:
                    self.log(f"{why}: stopping")
                    return "stop"
                r = subprocess.run([sys.executable, os.path.join("scripts", "game", "bridge_install.py"), "install",
                                    "--dir", br["dir"], "--starfield", self.a.starfield],
                                   capture_output=True, text=True, cwd=REPO)
                self.log(f"bridge install exit {r.returncode}: {(r.stdout + r.stderr).strip()[-200:]}")
                if r.returncode != 0:
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
                # 7: an installed experiment plugin's master is not active (exp_install.py order): nothing launched
                return "stop" if code in (2, 3, 5, 6, 7) else "retry"
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
        # the save's companion follows the player and blocks doors and shots: off for this session (queue.json
        # "companion": "keep" leaves it)
        if self.q.get("companion", "off") != "keep":
            code = self.step({"kind": "companion_off", "ref": COMPANION_REF}, sd)
            obs = load(os.path.join(sd, "obs.json"), {})
            self.log(f"companion {COMPANION_REF}: {obs.get('companion')} (exit {code})")
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
            # an open breaker skips the test before any launch (core64 2026-10-11: a "fresh" test relaunched the game
            # only to be skipped)
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
            inst, inst_why = None, None
            if t["kind"] == "walk":
                # the install record as run (the plugins', the archive's and every staged input's sha256), checked
                # against the experiment the queue pinned: a PASS or FAIL on another install decides nothing
                inst = installed_identity(getattr(self.a, "starfield", ""))
                inst_why = install_mismatch(self.q, inst)
                if inst_why and verdict != "INCONCLUSIVE":
                    verdict, cls, detail = "INCONCLUSIVE", "INSTALL", f"{inst_why}; raw verdict {verdict} {cls}: {detail}"
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
            if inst is not None:
                rec["install"] = inst
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
            if inst_why:                                  # every walk of this run would be judged on the wrong install
                self.log(f"stopped: {inst_why}")
                self.checkpoint(f"stopped: {inst_why}")
                write_report(self.qdir)
                return 3
            if not final:
                pending.append(t)                         # retried at the end of the queue
        left = len([t for t in tests if t["id"] not in self.state["done"]])
        self.checkpoint("finished" if left == 0 else f"paused ({left} left)")
        self.log(f"run ends: {left} tests left")
        write_report(self.qdir)
        return 4 if left and not a.dry_run else 0


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
            # "PASS" for a plain pass; with its class when a kind has several (movable_control: PASS WALKED / IMPULSE)
            got = None if r is None else ("PASS" if (r["verdict"], r["class"]) == ("PASS", "PASS")
                                          else f"{r['verdict']} {r['class']}")
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
    p.add_argument("--impulse", action="store_true",
                   help="movable: when the walk does not move an item, push it with ApplyHavokImpulse (runner feature "
                        "impulse; docs/ai/test-queue.md \"Movable items: walk, then impulse\")")
    p.add_argument("--routes-dir", default="", help="take the route files from this folder instead of the staging "
                   "(routes planned again for the same pinned build by a newer routes.py); the queue copies them into "
                   "<queue>/routes and records their sha256")
    p.add_argument("--refs", default="", help="only the tests of these references (comma-separated FormID prefixes), "
                   "in this order")
    p.add_argument("--first", default="", help="these references first (comma-separated FormID prefixes, in order), "
                   "then the rest")
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
    pd = sub.add_parser("plan-door", help="door_trip tests (a load door there and back, save, load) from "
                                          "<exp-dir>\\plan.json (docs/slice/redrocket-door.md)")
    pd.add_argument("--staging", required=True)
    pd.add_argument("--exp-dir", required=True, help="folder with plan.json and the plugins to install")
    pd.add_argument("--out", required=True)
    pd.add_argument("--launch-cell", default="Vault111Cryo")
    pd.add_argument("--plugin-index", default="02")
    pd.add_argument("--starfield", default=r"D:\SteamLibrary\steamapps\common\Starfield")
    pd.add_argument("--plugins", default="", help="experiment plugins to activate before launch (exp_install.py)")
    pd.add_argument("--only", type=int, default=0, help="keep the first N tests")
    pd.add_argument("--fresh", action="store_true", help="relaunch the game before every test")
    pm = sub.add_parser("plan-movable", help="movable_control tests (an item placed in a vanilla cell, walked over, "
                                             "then pushed with ApplyHavokImpulse) from <exp-dir>\\plan.json")
    pm.add_argument("--staging", required=True, help="the pinned build (FO4Port.esm, formids.json, manifest.json)")
    pm.add_argument("--exp-dir", required=True, help="folder with plan.json")
    pm.add_argument("--out", required=True)
    pm.add_argument("--launch-cell", default="Vault111Cryo")
    pm.add_argument("--plugin-index", default="02")
    pm.add_argument("--only", type=int, default=0, help="keep the first N tests")
    pm.add_argument("--fresh", action="store_true", help="relaunch the game before every test")
    pw = sub.add_parser("plan-walk", help="walk tests (a continuous walk over planned waypoints) from <exp-dir>\\plan.json "
                                          "(docs/terrain/walk-redrocket-sanctuary.md)")
    pw.add_argument("--staging", required=True)
    pw.add_argument("--exp-dir", required=True, help="folder with plan.json and its walk_ground.json")
    pw.add_argument("--out", required=True)
    pw.add_argument("--launch-cell", default="Vault111Cryo")
    pw.add_argument("--plugin-index", default="02")
    pw.add_argument("--starfield", default=r"D:\SteamLibrary\steamapps\common\Starfield")
    pw.add_argument("--plugins", default="", help="experiment plugins to activate before launch (exp_install.py)")
    pw.add_argument("--install-exp", default="", help="experiment folder those plugins come from (default --exp-dir)")
    pw.add_argument("--only", type=int, default=0, help="keep the first N tests")
    pw.add_argument("--fresh", action="store_true", help="relaunch the game before every test")
    for sp in (p, pt, pn, pd, pw, pm):                    # the observation bridge for every kind (docs/ai/test-queue.md)
        sp.add_argument("--bridge", default="", help="staged bridge folder (make_bridge.py stage): positions from the "
                                                     "game's own log instead of console captures; runner feature bridge")
    for sp in (pt, pn, pd, pw):                           # time of day / weather for every test (docs/ai/test-queue.md)
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
    if a.cmd == "plan-door":
        return plan_door(a)
    if a.cmd == "plan-walk":
        return plan_walk(a)
    if a.cmd == "plan-movable":
        return plan_movable(a)
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
