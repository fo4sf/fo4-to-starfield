"""Queued in-game test runner: plan a batch of tests on ONE pinned build, run them unattended without any AI calls,
checkpoint after every test, resume later, and rank the problems found.

usage:
  python testqueue.py plan   --staging <build dir> --out <queue dir> [--cells A,B] [--kinds stairs,door,fall,movable,travel]
                             [--per-cell 12] [--plugin-index 02]
  python testqueue.py run    --queue <queue dir> [--max-tests N] [--max-hours 8] [--min-idle 900] [--wait-for-idle]
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
import sqlite3
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import route_eval  # noqa: E402

UNIT = 1.0 / 70.0
KINDS = ("stairs", "door", "fall", "movable", "travel")
# ranking weight per (kind, verdict reason class): falling out of the world and broken travel first
SEVERITY = {("fall", "FALL"): 5, ("travel", "NOTRAVEL"): 5, ("travel", "NOPROMPT"): 4, ("door", "BLOCKED"): 4,
            ("door", "NOPROMPT"): 3, ("stairs", "FALL"): 4, ("stairs", "STUCK"): 3, ("door", "FALL"): 5,
            ("movable", "NOTMOVED"): 2, ("movable", "ITEMFELL"): 3, ("any", "CRASH"): 5}
PS = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]


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
    if a.cells:
        want = {c.strip() for c in a.cells.split(",")}
        cells = [c for c in cells if c["cell"] in want]
    all_refs = {r["formkey"]: (c["cell"], r) for c in cells for r in c["refs"]}
    tests = []
    for c in cells:
        tests += plan_cell(c, staging, kinds, a.per_cell, a.plugin_index, formids, items, all_refs)
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
    return "INCONCLUSIVE", "KIND", f"unknown kind {kind}"


# ----------------------------------------------------------------------------------------------------------- controls
class Controls:
    """The owner's PC-use controls and the game process (Windows). Replaced by a fake in the unit tests."""
    state_dir = os.environ.get("FO4_AI_TEAM_STATE") or os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
                                                                      "fo4-ai-team", "state")

    def __init__(self, queue_dir):
        self.queue_dir = queue_dir
        self.last_sent_tick = None

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

    def foreign_input(self):
        if self.last_sent_tick is None:
            return False
        d = (self._last_input_tick() - self.last_sent_tick) & 0xFFFFFFFF
        d = d - (1 << 32) if d >= 1 << 31 else d                 # signed: input before our last step is negative
        return d > 500

    @staticmethod
    def foreground_exe():
        u, k = ctypes.windll.user32, ctypes.windll.kernel32
        pid = ctypes.c_uint32()
        u.GetWindowThreadProcessId(u.GetForegroundWindow(), ctypes.byref(pid))
        h = k.OpenProcess(0x1000, False, pid.value)
        if not h:
            return ""
        buf, n = ctypes.create_unicode_buffer(1024), ctypes.c_uint32(1024)
        ok = k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
        k.CloseHandle(h)
        return os.path.basename(buf.value).lower() if ok else ""

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

    @staticmethod
    def refocus_game():
        """Bring the runner's own game window to the front (only used after --min-idle of owner inactivity)."""
        r = subprocess.run(PS[:-1] + ["-Command", "$p = Get-Process Starfield -ErrorAction SilentlyContinue | Select-Object -First 1; "
                           "if ($p) { Add-Type -MemberDefinition '[DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(System.IntPtr h);' "
                           "-Name W -Namespace F; [F.W]::SetForegroundWindow($p.MainWindowHandle) | Out-Null }"], capture_output=True)
        time.sleep(1.0)
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
    if launching and ctl.idle_s() < min_idle:
        return f"owner active (idle {ctl.idle_s():.0f} s < {min_idle} s): not launching the game"
    if ctl.foreign_input():
        return "owner input detected (keyboard/mouse the runner did not send)"
    return None


# -------------------------------------------------------------------------------------------------------------- runner
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
        save_atomic(spec, test)
        code, out = self._ps("qstep.ps1", ["-Spec", spec, "-Out", out_dir, "-PluginIndex", self.q["plugin_index"]], 300)
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
        cell_json = os.path.join(self.q["staging"], cell + ".json")
        if not gp:
            if self.state["relaunches"] >= self.a.max_relaunch:
                self.log(f"game not running and {self.state['relaunches']} relaunches used: stopping")
                return "stop"
            why = blocked_reason(self.ctl, self.q, launching=True, min_idle=self.a.min_idle)
            if why:
                return why
            if not self.pinned_ok():
                self.log("staging FO4Port.esm no longer matches the pinned build: stopping")
                return "stop"
            self.state["relaunches"] += 1
            self.checkpoint()
            self.log(f"launching the pinned build {self.q['build_id']} into {cell}")
            code, out = self._ps("cycle.ps1", ["-Staging", self.q["staging"], "-Starfield", self.a.starfield,
                                               "-Cell", f"FO4Port_{cell}", "-CellJson", cell_json,
                                               "-Shot", os.path.join(self.qdir, "cycle.png")], 900, steal=True)
            self.log(f"cycle exit {code}: {out.strip().splitlines()[-1] if out.strip() else ''}")
            if code != 0:
                return "stop" if code in (2, 3, 5, 6) else "retry"
            self.session, self.cell = False, cell
        if not self.session:
            self.setup_session(cell)
        if self.cell != cell:
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

    def wait_or_stop(self, why):
        """Owner present: stop, or with --wait-for-idle wait until the PC is idle again (STOP/Guardian still end it)."""
        if not self.a.wait_for_idle or not why.startswith("owner"):
            return False
        self.log(f"{why}: waiting for {self.a.min_idle} s of inactivity")
        self.checkpoint("waiting for idle")
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
                if self.ctl.game_pid() and self.ctl.foreground_exe() != "starfield.exe":
                    if not self.a.refocus:
                        self.log("idle again but the game is not in front and --refocus is off: stopping")
                        return False
                    self.ctl.refocus_game()
                    self.ctl.mark_sent()
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
        for t in pending:
            if ran >= a.max_tests or time.time() > self.deadline:
                self.log("test or time budget used up")
                break
            while True:
                why = blocked_reason(self.ctl, self.q)
                if not why and self.ctl.game_pid() and self.ctl.foreground_exe() != "starfield.exe":
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
            if g in ("nocell", "retry"):
                verdict, cls, detail, code = "INCONCLUSIVE", "NOCELL", f"cell {t['cell']} not reached ({g})", None
            else:
                pid_before = self.ctl.game_pid()
                code = self.step(t, out_dir)
                if code == 2:                             # the owner took the foreground mid-step: not an attempt
                    self.state["attempts"][t["id"]] = n - 1
                    self.cell = None
                    if self.wait_or_stop("owner switched windows during a step"):
                        pending.append(t)                 # run it again later in this run
                        continue
                    self.log("stopped: owner took over during a step")
                    self.checkpoint("stopped: owner took over during a step")
                    return 3
                if pid_before and not self.ctl.game_pid():
                    self.state["crashes"] += 1
                    self.session, self.cell = False, None
                    verdict, cls, detail = "INCONCLUSIVE", "CRASH", "the game exited during this test"
                else:
                    verdict, cls, detail = judge(t, load(os.path.join(out_dir, "obs.json")), out_dir)
                    if cls in ("STOPPED", "NOOBS", "NORESULT"):
                        self.cell = None                  # unknown game state: re-verify the cell next time
            rec = {"id": t["id"], "kind": t["kind"], "cell": t["cell"], "ref": t["ref"], "model": t.get("model", ""),
                   "attempt": n, "verdict": verdict, "class": cls, "detail": detail, "exit": code, "dir": out_dir, "t": now()}
            with open(os.path.join(self.qdir, "results.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            if verdict != "INCONCLUSIVE" or n >= a.max_attempts:
                self.state["done"][t["id"]] = {"verdict": verdict, "class": cls, "attempts": n}
            self.checkpoint()
            ran += 1
            self.log(f"{t['id']}: {verdict} {cls} {detail}")
            if verdict == "INCONCLUSIVE" and n < a.max_attempts:
                pending.append(t)                         # retried at the end of the queue
        left = len([t for t in tests if t["id"] not in self.state["done"]])
        self.checkpoint("finished" if left == 0 else f"paused ({left} left)")
        self.log(f"run ends: {left} tests left")
        write_report(self.qdir)
        return 0


# -------------------------------------------------------------------------------------------------------------- report
def write_report(qdir):
    q = load(os.path.join(qdir, "queue.json"))
    rows = [json.loads(x) for x in open(os.path.join(qdir, "results.jsonl"), encoding="utf-8")] \
        if os.path.exists(os.path.join(qdir, "results.jsonl")) else []
    final = {}
    for r in rows:                                        # last attempt per test counts
        final[r["id"]] = r
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
    rep = {"build_id": q["build_id"], "commit": q["commit"], "tests": len(q["tests"]), "results": len(final),
           "pending": pending, "tally": tally, "ranked": ranked}
    save_atomic(os.path.join(qdir, "report.json"), rep)
    lines = [f"# Test queue report: build {q['build_id']} (commit {q['commit'][:8]})", "",
             f"{len(final)} of {len(q['tests'])} tests have a result, {pending} pending. Generated {now()}.", "",
             "| kind | PASS | FAIL | INCONCLUSIVE |", "|---|---|---|---|"]
    for k in KINDS:
        if k in tally:
            lines.append(f"| {k} | {tally[k].get('PASS', 0)} | {tally[k].get('FAIL', 0)} | {tally[k].get('INCONCLUSIVE', 0)} |")
    lines += ["", "## Ranked problems (FAIL first, by severity x count)", "",
              "| # | verdict | kind | class | model | count | cells | example |", "|---|---|---|---|---|---|---|---|"]
    for n, g in enumerate(ranked, 1):
        ex = g["examples"][0]
        lines.append(f"| {n} | {g['verdict']} | {g['kind']} | {g['class']} | {g['model']} | {g['count']} | "
                     f"{', '.join(g['cells'])} | {ex['id']}: {ex['detail']} |")
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
