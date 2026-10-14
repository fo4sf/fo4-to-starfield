"""walk (docs/terrain/walk-redrocket-sanctuary.md): planning a walk queue (testqueue.py plan-walk), the controller
qstep.ps1 asks every leg (walk_eval.py steer) and the judge on synthetic observations. Synthetic data only."""
import contextlib
import io
import json
import math
import os
import sqlite3
import struct
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import exp_install  # noqa: E402
import runner_features  # noqa: E402
import testqueue as tq  # noqa: E402
import walk_eval as we  # noqa: E402
import test_testqueue as tt  # noqa: E402  (FakeControls, args: the runner without Windows or a game)

OFF = [-1200.0, -2700.0, 0.0]
WPS = [(-995.0, 1190.0), (-1005.0, 1190.0), (-1015.0, 1190.0), (-1015.0, 1198.0), (-1015.0, 1206.0),
       (-1015.0, 1214.0)]
DECK = (-1017.0, 1195.0, -1013.0, 1209.0, 85.0)          # a deck 5 m over the slope
BRIDGE = {"src": "01F970:Fallout4.esm", "edid": "FO4Core_northbridge"}


def slope_z(x):
    return 100.0 + 0.02 * x


def on_deck(x, y):
    return DECK[0] <= x <= DECK[2] and DECK[1] <= y <= DECK[3]


def ground_z(x, y):
    return DECK[4] if on_deck(x, y) else slope_z(x)


def write_ground(d, deck=DECK):
    x0, y0, step = -1035.0, 1170.0, 0.78125
    rows = [[round(slope_z(x0 + c * step), 4) for c in range(80)] for _r in range(80)]
    sx0, sy0, ss = -1035.0, 1170.0, 0.5
    nodes = {}
    for i in range(int(math.ceil((deck[0] - sx0) / ss)), int(math.floor((deck[2] - sx0) / ss)) + 1):
        for j in range(int(math.ceil((deck[1] - sy0) / ss)), int(math.floor((deck[3] - sy0) / ss)) + 1):
            nodes[f"{i},{j}"] = [[deck[4], 0]]
    data = {"version": 1, "frame": "test", "terrain": {"x0": x0, "y0": y0, "step": step, "rows": rows},
            "surfaces": {"x0": sx0, "y0": sy0, "step": ss, "nx": 140, "ny": 140, "nodes": nodes}, "owners": [BRIDGE],
            "corridor_m": 12.0, "path": [list(p) for p in WPS]}
    p = os.path.join(d, "walk_ground.json")
    with open(p, "w") as f:
        json.dump(data, f)
    return tq.sha256(p)


def entry(d, **extra):
    gsha = write_ground(d)
    wps = [[x, y, ground_z(x, y), 3.0 if k == len(WPS) - 1 else 2.5] for k, (x, y) in enumerate(WPS)]
    e = {"label": "walk_test", "travel": "coc FO4Core_RedRocketSpawn", "spawn_local": [-995.0, 1190.0, slope_z(-995.0)],
         "setup": False, "start": wps[0][:3], "waypoints": wps, "goal_radius": 3.0, "ground": "walk_ground.json",
         "ground_sha256": gsha, "bridge": dict(BRIDGE, span=[25.0, 39.0], min_reads=2),
         "crossings": [{"s": 5.0, "from": [-10, 11], "to": [-11, 11], "axis": "x", "at": -1000.0},
                       {"s": 30.0, "from": [-11, 11], "to": [-11, 12], "axis": "y", "at": 1200.0}],
         "length_m": 44.0, "max_legs": 20, "speed": 3.0, "shot_every": 2}
    e.update(extra)
    return e


def test_of(**extra):
    d = tempfile.mkdtemp(prefix="walk_eval_")
    return tq.walk_test(0, entry(d, **extra), d), d


def fmt(p):
    return " ".join(f"{v:.2f}" for v in p)


def game(x, y, z):
    return [x + OFF[0], y + OFF[1], z + OFF[2]]


def legs_at(points, hold=3400):
    """Legs reading the player at each local (x, y[, z]) point, W held hold ms after each but the last."""
    out = []
    for n, p in enumerate(points):
        z = p[2] if len(p) > 2 else ground_z(p[0], p[1])
        r = fmt(game(p[0], p[1], z))
        last = n == len(points) - 1
        leg = {"n": n, "read": r, "used": r, "action": "done" if last else "aim",
               "cmds": ["ClearConsole", "player.getpos x", "player.getpos y", "player.getpos z"]
               + ([] if last else ["player.setangle z 270"]), "hud": True}
        if not last:
            leg["hold_ms"] = hold
        if n % 2 == 0:
            leg["shot"] = f"walk_{n:03d}.png"
        out.append(leg)
    return out


def good_obs(points=WPS, stopped="goal", **extra):
    o = {"offset": OFF, "spawn_read": fmt(game(-995.0, 1190.0, slope_z(-995.0))), "spawn_settled": True,
         "shot": "arrival.png", "legs": legs_at(points), "walk_stopped": stopped}
    o.update(extra)
    return o


def shot_ok(name):
    return bool(name)


def tes4(path, body=b""):
    """A minimal plugin (a TES4 header without masters, as exp_install.plugin_masters reads it) with distinct bytes."""
    with open(path, "wb") as f:
        f.write(b"TES4" + struct.pack("<I", 0) + b"\0" * 16 + body)


PLUGINS = ["FO4TerrainCore.esm", "FO4TerrainCore_Mars.esm"]


def planned_queue(d, *flags, **extra):
    """plan-walk for real: a fake build in <d>/staging, the route in <d>/walk, the experiment it runs on in <d>/core
    (two plugins and a Data file: what the runner installs and pins); returns (queue dir, core dir)."""
    staging, exp, core, out = (os.path.join(d, x) for x in ("staging", "walk", "core", "queue"))
    for p in (staging, exp, os.path.join(core, "Data", "Terrain")):
        os.makedirs(p)
    with open(os.path.join(staging, "FO4Port.esm"), "wb") as f:
        f.write(b"TES4")
    for k, p in enumerate(PLUGINS):
        tes4(os.path.join(core, p), bytes([k]))
    with open(os.path.join(core, "Data", "Terrain", "W.btd"), "wb") as f:
        f.write(b"BTDB")
    with open(os.path.join(exp, "plan.json"), "w") as f:
        json.dump([entry(exp, **extra)], f)
    tq.main(["plan-walk", "--staging", staging, "--exp-dir", exp, "--out", out, "--plugins", ",".join(PLUGINS),
             "--install-exp", core] + list(flags))
    return out, core


def install_record(starfield, core, **changes):
    """The install record exp_install.py would leave for the planned experiment in <starfield>/Data."""
    rec = {"exp_dir": core, "plugins": PLUGINS, "complete": True, "pack": True,
           "source_inputs": exp_install.source_inventory(core, PLUGINS),
           "files": dict({p: exp_install.digest(os.path.join(core, p)) for p in PLUGINS},
                         **{"FO4TerrainCore - Main.ba2": "cd" * 32}),
           "packing_policy": "general-stored-verified-v2", "plugins_txt": "x"}
    rec.update(changes)
    os.makedirs(os.path.join(starfield, "Data"), exist_ok=True)
    with open(os.path.join(starfield, "Data", exp_install.RECORD), "w") as f:
        json.dump(rec, f)


class WalkPlanTests(unittest.TestCase):
    def test_a_test_from_the_plan(self):
        t, d = test_of()
        self.assertEqual((t["id"], t["kind"], t["cell"]), ("0000_walk_walk_test", "walk", ""))
        self.assertEqual(t["ground_path"], os.path.join(d, "walk_ground.json"))
        self.assertEqual(len(t["waypoints"]), 6)
        self.assertEqual(t["crossings"][1], {"from": [-11, 11], "to": [-11, 12], "s": 30.0})
        self.assertEqual(t["bridge"]["min_reads"], 2)
        self.assertEqual((t["z_tol"], t["fell_m"], t["stuck_k"]), (0.6, 3.0, 3))

    def test_the_plan_is_checked(self):
        d = tempfile.mkdtemp()
        for bad in ({"label": "x", "teleport": True}, {"travel": "player.moveto 02000800"},
                    {"waypoints": [[1, 2, 3, 2.5]]}, {"waypoints": [[1, 2, 3, 50.0]] * 3},
                    {"ground": "..\\walk_ground.json"}, {"ground_sha256": "0" * 64},
                    {"setup": True, "start": [0.0, 0.0, 0.0]},
                    {"crossings": [{"from": [-10, 11], "to": [-12, 11]}]},
                    {"bridge": {"src": "nope", "span": [1, 2]}}):
            with self.assertRaises(SystemExit, msg=bad):
                tq.walk_test(0, entry(d, **bad), d)

    def test_plan_walk_writes_the_queue_with_its_needs(self):
        d = tempfile.mkdtemp()
        out, core = planned_queue(d, "--fresh", time_of_day=12, fresh=True)
        with open(os.path.join(out, "queue.json")) as f:
            q = json.load(f)
        self.assertEqual(q["needs"], ["light", "walk"])
        t = q["tests"][0]
        self.assertTrue(t["fresh"])
        self.assertEqual(t["time_of_day"], 12.0)
        pre = q["pre_launch"]
        self.assertEqual(pre[pre.index("--exp-dir") + 1], os.path.abspath(core))      # core64c is what is installed
        self.assertEqual(pre[pre.index("--needs") + 1], "light,walk")
        self.assertEqual(q["experiment"], os.path.abspath(os.path.join(d, "walk")))
        self.assertGreater(tq.step_timeout(t), 20 * 60)
        self.assertEqual(runner_features.needs([t]), ["light", "walk"])
        self.assertEqual(runner_features.missing(["walk"]), [])
        # the experiment the walk runs on is pinned by its staged inputs (Codex on PR #103: FO4Port alone was)
        pin = q["experiment_identity"]
        self.assertEqual((pin["exp_dir"], pin["plugins"]), (os.path.abspath(core), PLUGINS))
        self.assertEqual(sorted(pin["inputs"]), ["Data/Terrain/W.btd", "plugin/FO4TerrainCore.esm",
                                                 "plugin/FO4TerrainCore_Mars.esm"])
        self.assertEqual(pin["inputs"]["Data/Terrain/W.btd"], tq.sha256(os.path.join(core, "Data", "Terrain", "W.btd")))

    def test_plan_walk_needs_the_experiment(self):
        d = tempfile.mkdtemp()
        staging, exp = os.path.join(d, "staging"), os.path.join(d, "walk")
        os.makedirs(staging)
        os.makedirs(exp)
        with open(os.path.join(staging, "FO4Port.esm"), "wb") as f:
            f.write(b"TES4")
        with open(os.path.join(exp, "plan.json"), "w") as f:
            json.dump([entry(exp)], f)
        with self.assertRaises(SystemExit):                            # no --plugins: nothing to pin
            tq.main(["plan-walk", "--staging", staging, "--exp-dir", exp, "--out", os.path.join(d, "q")])
        with self.assertRaises(SystemExit):                            # a plugin that is not staged
            tq.main(["plan-walk", "--staging", staging, "--exp-dir", exp, "--out", os.path.join(d, "q"),
                     "--plugins", "FO4TerrainCore.esm", "--install-exp", os.path.join(d, "core")])
        self.assertFalse(os.path.exists(os.path.join(d, "q", "queue.json")))

    def test_the_install_record_is_pinned_with_a_result(self):
        d = tempfile.mkdtemp()
        self.assertIn("error", tq.installed_identity(d))
        os.makedirs(os.path.join(d, "Data"))
        rec = {"exp_dir": "C:\\Modding\\staging\\terrain_core64c", "plugins": ["FO4TerrainCore.esm"], "complete": True,
               "files": {"FO4TerrainCore.esm": "ab" * 32, "FO4TerrainCore - Main.ba2": "cd" * 32},
               "source_inputs": {"plugin/FO4TerrainCore.esm": "ab" * 32, "Data/Terrain/W.btd": "ef" * 32},
               "packing_policy": "general-stored-verified-v2", "plugins_txt": "x"}
        with open(os.path.join(d, "Data", "FO4SFExp.install.json"), "w") as f:
            json.dump(rec, f)
        got = tq.installed_identity(d)
        self.assertEqual((got["files"], got["source_inputs"]), (rec["files"], rec["source_inputs"]))
        self.assertNotIn("plugins_txt", got)

    def test_a_changed_experiment_stops_before_the_launch(self):
        d = tempfile.mkdtemp()
        out, core = planned_queue(d)
        ctl = tt.FakeControls()
        ctl.pid = None                                                 # no game yet: the runner would launch
        r = tq.Runner(out, tt.args(), ctl=ctl, step=lambda t, o: 0)
        r._ps = lambda *a, **k: self.fail("must not launch on a changed experiment")
        self.assertIsNone(r.experiment_mismatch())
        with open(os.path.join(core, "Data", "Terrain", "W.btd"), "ab") as f:
            f.write(b"!")                                              # the staged terrain changed since planning
        self.assertIn("Data/Terrain/W.btd", r.experiment_mismatch())
        self.assertEqual(r.run(), 3)
        with open(os.path.join(out, "run.log"), encoding="utf-8") as f:
            self.assertIn("changed since planning", f.read())
        os.remove(os.path.join(core, PLUGINS[1]))                      # a plugin gone: unreadable, stops too
        self.assertIn("unreadable", r.experiment_mismatch())

    def walk_run(self, d, starfield, record=None):
        """One run of the planned walk with a step that writes a passing observation: (exit, last result, status);
        record(core) writes the install record between the planning and the run."""
        out, core = planned_queue(d)
        if record:
            record(core)

        def step(test, out_dir):
            obs = good_obs()
            for name in ["arrival.png"] + [x["shot"] for x in obs["legs"] if x.get("shot")]:
                open(os.path.join(out_dir, name), "wb").close()
            with open(os.path.join(out_dir, "obs.json"), "w") as f:
                json.dump(obs, f)
            return 0
        r = tq.Runner(out, tt.args(starfield=starfield), ctl=tt.FakeControls(), step=step)
        r.session, r.cell = True, "C"
        code = r.run()
        with open(os.path.join(out, "results.jsonl"), encoding="utf-8") as f:
            rows = [json.loads(x) for x in f]
        return code, rows[-1], r.state["status"], core

    def test_a_walk_result_needs_the_pinned_install_record(self):
        # Codex on PR #103: a mocked runner wrote PASS with a missing install receipt
        d = tempfile.mkdtemp()
        sf = os.path.join(d, "starfield")
        code, rec, status, core = self.walk_run(d, sf)
        self.assertEqual((code, rec["verdict"], rec["class"]), (3, "INCONCLUSIVE", "INSTALL"), rec["detail"])
        self.assertIn("no install record", rec["detail"])
        self.assertIn("raw verdict PASS PASS", rec["detail"])
        self.assertTrue(status.startswith("stopped: no install record"), status)
        self.assertIn("error", rec["install"])
        for change, why in (({"complete": False}, "incomplete"), ({"plugins": PLUGINS[:1]}, "installed plugins"),
                            ({"exp_dir": os.path.join(d, "other")}, "is not the pinned"),
                            ({"source_inputs": {"plugin/FO4TerrainCore.esm": "00" * 32}}, "inputs differ")):
            d2 = tempfile.mkdtemp()
            sf2 = os.path.join(d2, "starfield")
            code, rec, status, _ = self.walk_run(d2, sf2, lambda core: install_record(sf2, core, **change))
            self.assertEqual((code, rec["class"]), (3, "INSTALL"), change)
            self.assertIn(why, rec["detail"])
            self.assertEqual(rec["install"]["complete"], change.get("complete", True))
        d3 = tempfile.mkdtemp()                                        # the pinned experiment installed: PASS
        sf3 = os.path.join(d3, "starfield")
        code, rec, status, _ = self.walk_run(d3, sf3, lambda core: install_record(sf3, core))
        self.assertEqual((code, rec["verdict"], status), (0, "PASS", "finished"), rec["detail"])
        self.assertEqual(rec["install"]["files"]["FO4TerrainCore - Main.ba2"], "cd" * 32)


class StopControlTests(unittest.TestCase):
    """Codex on PR #103: the runner is blocked in a walk step, so the step honours the owner's stop controls itself."""
    def test_the_stop_controls_reach_the_step_spec(self):
        d = tempfile.mkdtemp()
        qdir = os.path.join(d, "chain", "walk_q")
        os.makedirs(qdir)
        ctl = tq.stop_controls(qdir)
        self.assertEqual(ctl["files"][:2], [os.path.join(qdir, "STOP"), os.path.join(d, "chain", "STOP_ALL")])
        self.assertTrue(ctl["files"][2].endswith("testqueue.STOP"))
        self.assertTrue(ctl["guardian_db"].endswith("guardian.db"))
        t, _ = test_of()
        with open(os.path.join(qdir, "queue.json"), "w") as f:
            json.dump({"build_id": "x", "commit": "0" * 40, "staging": d, "plugin_sha256": "x", "plugin_index": "02",
                       "hours": [[0, 24]], "tests": [t]}, f)
        r = tq.Runner(qdir, SimpleNamespace(starfield=""))
        r._ps = lambda *a, **k: (0, "")
        out = os.path.join(qdir, "tests", t["id"], "a1")
        os.makedirs(out)
        r._step(t, out)
        with open(os.path.join(out, "spec.json")) as f:
            spec = json.load(f)
        self.assertEqual(spec["stop"], ctl)
        self.assertGreater(spec["budget_s"], 0)
        # the chain folder's STOP_ALL (watchdog.ps1's file) stops the runner between tests too
        old = tq.Controls.state_dir
        tq.Controls.state_dir = os.path.join(d, "state")
        try:
            c = tq.Controls(qdir)
            self.assertIsNone(c.stop_file())
            open(os.path.join(d, "chain", "STOP_ALL"), "w").close()
            self.assertEqual(c.stop_file(), os.path.join(d, "chain", "STOP_ALL"))
        finally:
            tq.Controls.state_dir = old

    def test_stop_reason(self):
        d = tempfile.mkdtemp()
        stop, db = os.path.join(d, "STOP"), os.path.join(d, "guardian.db")
        t = {"stop": {"files": [os.path.join(d, "nope"), stop], "guardian_db": db}}
        self.assertIsNone(we.stop_reason(t))
        self.assertIsNone(we.stop_reason({}))
        open(stop, "w").close()
        self.assertEqual(we.stop_reason(t), f"STOP file {stop}")
        os.remove(stop)
        c = sqlite3.connect(db)
        c.execute("CREATE TABLE control (key TEXT PRIMARY KEY, value TEXT)")
        c.execute("INSERT INTO control VALUES ('mode', 'running')")
        c.commit()
        self.assertIsNone(we.stop_reason(t))
        c.execute("UPDATE control SET value = 'paused' WHERE key = 'mode'")
        c.commit()
        c.close()
        self.assertEqual(we.stop_reason(t), "Resource Guardian mode paused")
        with open(db, "wb") as f:
            f.write(b"not a database")
        self.assertEqual(we.stop_reason(t), "Resource Guardian mode unreadable")     # fail closed, as the runner

    def test_steer_stops_on_a_stop_control_without_touching_its_state(self):
        t, d = test_of()
        stop = os.path.join(d, "STOP")
        t["stop"] = {"files": [stop], "guardian_db": ""}
        spec, state = os.path.join(d, "spec.json"), os.path.join(d, "walk_state.json")
        with open(spec, "w") as f:
            json.dump(t, f)
        read = "--read=" + fmt(game(-995.0, 1190.0, slope_z(-995.0)))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            we.main(["init", "--spec", spec, "--state", state, "--offset", " ".join(str(v) for v in OFF)])
            open(stop, "w").close()
            we.main(["steer", "--spec", spec, "--state", state, read])
        init, stopped = [json.loads(x) for x in out.getvalue().splitlines()]
        self.assertEqual(init["action"], "init")
        self.assertEqual(stopped, {"action": "stop", "reason": "stopped", "stopped": f"STOP file {stop}"})
        with open(state) as f:
            self.assertEqual(json.load(f)["legs"], 0)
        os.remove(stop)
        with contextlib.redirect_stdout(out):
            we.main(["steer", "--spec", spec, "--state", state, read])
        self.assertEqual(json.loads(out.getvalue().splitlines()[-1])["action"], "aim")

    def test_the_step_and_the_hold_carry_the_checks(self):
        # the sandbox (opt-in QstepWalkSandboxTests) proves it end to end; here: the real scripts carry the checks
        game_dir = os.path.join(ROOT, "scripts", "game")
        with open(os.path.join(game_dir, "input.ps1"), encoding="utf-8") as f:
            holdg = f.read().split("'holdg' {")[1].split("'move'")[0]
        self.assertIn("FO4SF_STOP_FILES", holdg)
        self.assertIn("exit 5", holdg)
        with open(os.path.join(game_dir, "qstep.ps1"), encoding="utf-8") as f:
            step = f.read()
        self.assertIn("$env:FO4SF_STOP_FILES = ", step)
        self.assertEqual(step.count("Walk-Stop; if ($why) { Stop-Walk $why $L }"), 2)   # before the leg, before the hold
        self.assertIn("if ($LASTEXITCODE -eq 5)", step)


class SteerTests(unittest.TestCase):
    def setUp(self):
        self.t, _ = test_of()
        self.st = we.init_state(self.t, OFF)

    def at(self, x, y, z=None, reread=False):
        z = ground_z(x, y) if z is None else z
        return we.steer(self.st, self.t, fmt(game(x, y, z)), reread)

    def test_waypoint_by_waypoint_to_the_goal(self):
        d = self.at(-995.0, 1190.0)
        self.assertEqual((d["action"], d["wp"], d["heading"]), ("aim", 1, 270.0))
        self.assertEqual(d["hold_ms"], int(10.0 / 3.0 * 1000))
        d = self.at(-1004.0, 1190.3)                              # within 2.5 m of wp 1: the next one
        self.assertEqual((d["action"], d["wp"]), ("aim", 2))
        d = self.at(-1017.8, 1190.5)                              # past wp 2 along the route (2.8 m beyond it)
        self.assertEqual(d["wp"], 3)
        self.assertGreater(d["heading"], 15.0)                    # back towards (-1015, 1198)
        for p in ((-1015.0, 1198.0), (-1015.0, 1206.0)):
            self.at(*p)
        d = self.at(-1015.2, 1212.5)
        self.assertEqual((d["action"], d["reason"]), ("done", "goal"))

    def test_waypoints_not_kept_are_walked_past_in_one_leg(self):
        wps = [list(w) + [1] for w in self.t["waypoints"]]
        wps[1][4] = 0                                             # (-1005, 1190): on the line to (-1015, 1190)
        t = dict(self.t, waypoints=wps, max_leg_m=25.0)
        st = we.init_state(t, OFF)
        d = we.steer(st, t, fmt(game(-995.0, 1190.0, slope_z(-995.0))))
        self.assertEqual((d["wp"], d["target"]), (1, 2))
        self.assertEqual(d["hold_ms"], int(20.0 / 3.0 * 1000))
        d = we.steer(st, t, fmt(game(-1014.0, 1190.2, slope_z(-1014.0))))
        self.assertEqual((d["wp"], d["target"]), (3, 3))         # both behind; wp 3 is kept (a corner)
        t = dict(self.t, waypoints=[list(w) + [1] for w in self.t["waypoints"]], max_leg_m=25.0)
        st = we.init_state(t, OFF)
        self.assertEqual(we.steer(st, t, fmt(game(-995.0, 1190.0, slope_z(-995.0))))["target"], 1)
        wps = [list(w) + [0] for w in self.t["waypoints"]]
        wps[0][:2] = [-995.0, 1190.0]
        t = dict(self.t, waypoints=wps, max_leg_m=40.0)
        st = we.init_state(t, OFF)
        d = we.steer(st, t, fmt(game(-995.0, 1190.0, slope_z(-995.0))))
        self.assertEqual(d["target"], 2)                          # (-1015, 1198) is off the line: not past it

    def test_no_movement_steps_aside_then_stops_stuck(self):
        self.at(-995.0, 1190.0)
        d = self.at(-995.0, 1190.0)
        self.assertTrue(d["detour"])
        self.assertEqual((d["heading"], d["hold_ms"]), (320.0, we.DETOUR_MS))
        d = self.at(-995.0, 1190.0)
        self.assertEqual(d["heading"], 220.0)
        d = self.at(-995.05, 1190.0)
        self.assertEqual((d["action"], d["reason"]), ("stop", "stuck"))

    def test_an_implausible_read_is_read_again(self):
        self.at(-995.0, 1190.0)
        d = we.steer(self.st, self.t, fmt([2205.0, -1510.0, 80.0]))           # the OCR dropped the minus sign
        self.assertEqual(d["action"], "reread")
        d = self.at(-1004.0, 1190.0, reread=True)
        self.assertEqual(d["action"], "aim")
        self.assertEqual(self.st["misreads"], 1)

    def test_a_jump_two_reads_agree_on_stops_the_walk(self):
        self.at(-995.0, 1190.0)
        far = fmt(game(8000.0, 1190.0, 80.0))
        self.assertEqual(we.steer(self.st, self.t, far)["action"], "reread")
        d = we.steer(self.st, self.t, far, True)
        self.assertEqual((d["action"], d["reason"], d["confirmed"]), ("stop", "jump", True))
        st = we.init_state(self.t, OFF)
        we.steer(st, self.t, fmt(game(-995.0, 1190.0, slope_z(-995.0))))
        we.steer(st, self.t, far)
        d = we.steer(st, self.t, fmt(game(-3000.0, 1190.0, 80.0)), True)
        self.assertEqual((d["reason"], d["confirmed"]), ("jump_unconfirmed", False))

    def test_off_the_route_below_it_unread_and_out_of_legs(self):
        self.assertEqual(self.at(-1003.0, 1205.0)["reason"], "offroute")             # 12 m from the route
        st = we.init_state(self.t, OFF)
        self.assertEqual(we.steer(st, self.t, fmt(game(-1000.0, 1190.0, 40.0)))["reason"], "fell")
        self.assertEqual(we.steer(st, self.t, None)["reason"], "unread")
        t = dict(self.t, max_legs=1)
        st = we.init_state(t, OFF)
        we.steer(st, t, fmt(game(-995.0, 1190.0, 80.1)))
        self.assertEqual(we.steer(st, t, fmt(game(-999.0, 1190.0, 80.0)))["reason"], "legs")

    def test_a_long_slow_leg_holds_at_most_8_s(self):
        t = dict(self.t, max_leg_m=40.0, speed=1.0, waypoints=[[-995.0, 1190.0, 80.1, 2.5], [-1035.0, 1190.0, 79.3, 3.0]])
        st = we.init_state(t, OFF)
        self.assertEqual(we.steer(st, t, fmt(game(-995.0, 1190.0, 80.1)))["hold_ms"], we.MAX_HOLD_MS)


class JudgeTests(unittest.TestCase):
    def judge(self, obs, **extra):
        t, _ = test_of(**extra)
        return we.judge(t, obs, shot_ok)

    def test_a_walk_over_the_bridge_and_two_borders_passes(self):
        v = self.judge(good_obs())
        self.assertEqual(v[:2], ("PASS", "PASS"), v[2])
        self.assertIn("2 reads on the FO4Core_northbridge deck", v[2])
        self.assertIn("cells (-22,-16) -> (-23,-16) -> (-23,-15)", v[2])
        self.assertIn("walked 44.0 m", v[2])

    def test_through_testqueue(self):
        t, _ = test_of()
        d = tempfile.mkdtemp()
        obs = good_obs()
        for name in ["arrival.png"] + [x["shot"] for x in obs["legs"] if x.get("shot")]:
            open(os.path.join(d, name), "wb").close()
        self.assertEqual(tq.judge(t, obs, d)[:2], ("PASS", "PASS"))
        os.remove(os.path.join(d, "walk_002.png"))
        self.assertEqual(tq.judge(t, obs, d)[:2], ("INCONCLUSIVE", "NOSHOT"))

    def test_a_boundary_popup_fails(self):
        obs = good_obs()
        obs["legs"][2]["popup"] = "BOUNDARY REACHED Open the map to explore another region"
        self.assertEqual(self.judge(obs)[:2], ("FAIL", "BOUNDARY"))

    def test_through_the_terrain_and_off_the_deck_are_falls(self):
        pts = [WPS[0], WPS[1], (-1010.0, 1190.0, slope_z(-1010.0) - 40.0)]
        v = self.judge(good_obs(pts, stopped="fell"))
        self.assertEqual(v[:2], ("FAIL", "FELL"), v[2])
        self.assertIn("below the terrain", v[2])
        pts = WPS[:4] + [(-1015.0, 1203.0, slope_z(-1015.0))]                  # under the deck, on the slope
        v = self.judge(good_obs(pts, stopped="stuck"))
        self.assertEqual(v[:2], ("FAIL", "FELL"), v[2])
        self.assertIn("off the planned surface", v[2])

    def test_ground_lower_than_planned_is_heights(self):
        pts = WPS[:2] + [(-1015.0, 1190.0, slope_z(-1015.0) - 1.2)] + WPS[3:]
        self.assertEqual(self.judge(good_obs(pts))[:2], ("FAIL", "HEIGHTS"))

    def test_a_confirmed_jump_fails_an_unconfirmed_one_is_a_read(self):
        obs = good_obs(WPS[:2] + [(-900.0, 1190.0)])
        obs["legs"][-1]["confirmed"] = True
        self.assertEqual(self.judge(obs)[:2], ("FAIL", "JUMP"))
        obs = good_obs(WPS[:2] + [WPS[5]])                      # 26 m after a 0.1 s hold: no walk does that
        obs["legs"][1]["hold_ms"] = 100
        self.assertEqual(self.judge(obs)[:2], ("INCONCLUSIVE", "READ"))

    def test_off_the_route_and_stuck(self):
        self.assertEqual(self.judge(good_obs(WPS[:2] + [(-1003.0, 1205.0)], stopped="offroute"))[:2],
                         ("FAIL", "OFFROUTE"))
        self.assertEqual(self.judge(good_obs(WPS[:3], stopped="stuck"))[:2], ("FAIL", "STUCK"))

    def test_what_keeps_a_walk_from_a_pass(self):
        obs = good_obs()
        obs["legs"][3]["used"] = None
        self.assertEqual(self.judge(obs)[:2], ("INCONCLUSIVE", "UNREAD"))
        pts = WPS[:2] + [(-1015.0, 1190.0, slope_z(-1015.0) + 2.0)] + WPS[3:]
        self.assertEqual(self.judge(good_obs(pts))[:2], ("INCONCLUSIVE", "OFFGROUND"))
        self.assertEqual(self.judge(good_obs(WPS[:4], stopped="legs"))[:2], ("INCONCLUSIVE", "NOTREACHED"))
        obs = good_obs()
        obs["legs"][1]["cmds"].append("player.setpos x -2205")
        self.assertEqual(self.judge(obs)[:2], ("INCONCLUSIVE", "TYPED"))
        obs = good_obs()
        obs["legs"][2]["hud"], obs["legs"][2]["hud_gap_s"] = False, 6
        self.assertEqual(self.judge(obs)[:2], ("INCONCLUSIVE", "HUDGAP"))
        self.assertEqual(self.judge({"legs": []})[:2], ("INCONCLUSIVE", "ANCHOR"))

    def test_borders_and_the_deck_must_be_seen(self):
        pts = [WPS[0], WPS[1], WPS[2], (-1015.0, 1203.0), WPS[5]]
        v = self.judge(good_obs(pts))
        self.assertEqual(v[:2], ("INCONCLUSIVE", "BRIDGE"), v[2])           # one read on the deck
        pts = [(-997.0, 1190.0), (-1015.0, 1206.0), WPS[5]]
        v = self.judge(good_obs(pts))
        self.assertEqual(v[:2], ("INCONCLUSIVE", "CROSSING"), v[2])         # x = -1000 and y = 1200 in one leg

    def test_the_setup_landing_and_the_ground_file(self):
        obs = good_obs(WPS[::-1])
        t, d = test_of(setup=True, start=[WPS[0][0], WPS[0][1], ground_z(*WPS[0])])
        obs["setup"] = {"read": fmt(game(-995.0, 1215.0, 80.0)), "settled": True}
        self.assertEqual(we.judge(t, obs, shot_ok)[:2], ("INCONCLUSIVE", "START"))
        t, d = test_of()
        with open(os.path.join(d, "walk_ground.json"), "a") as f:
            f.write(" ")
        self.assertEqual(we.judge(t, good_obs(), shot_ok)[:2], ("INCONCLUSIVE", "GROUND"))


if __name__ == "__main__":
    unittest.main()
