"""Queued test runner (scripts/game/testqueue.py): judges never pass on missing observations, the run checkpoints after
every test and resumes, retries are limited, and the owner's controls stop it. Synthetic data; no game, no Windows calls."""
import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import testqueue as tq  # noqa: E402


def touch(d, name):
    open(os.path.join(d, name), "wb").close()
    return name


class JudgeTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def test_no_observations_is_inconclusive(self):
        for kind in ("fall", "movable", "travel", "stairs", "door"):
            self.assertEqual(tq.judge({"kind": kind}, None, self.d)[0], "INCONCLUSIVE")
            self.assertEqual(tq.judge({"kind": kind}, {"stopped": "input guard"}, self.d)[0], "INCONCLUSIVE")

    def test_fall(self):
        t = {"kind": "fall", "point": [1.0, 2.0, 3.0]}
        shot = touch(self.d, "fall.png")
        self.assertEqual(tq.judge(t, {"end_read": "1.0 2.0 3.1", "shot": shot}, self.d)[0], "PASS")
        self.assertEqual(tq.judge(t, {"end_read": "1.0 2.0 -20", "shot": shot}, self.d)[:2], ("FAIL", "FALL"))
        self.assertEqual(tq.judge(t, {"end_read": "1.0 2.0 1.5", "shot": shot}, self.d)[:2], ("INCONCLUSIVE", "LOWER"))
        self.assertEqual(tq.judge(t, {"end_read": "9.0 2.0 3.0", "shot": shot}, self.d)[:2], ("INCONCLUSIVE", "MOVED"))
        # a perfect landing without the screenshot is not a pass
        self.assertEqual(tq.judge(t, {"end_read": "1.0 2.0 3.0", "shot": "missing.png"}, self.d)[0], "INCONCLUSIVE")
        self.assertEqual(tq.judge(t, {"end_read": None, "shot": shot}, self.d)[0], "INCONCLUSIVE")

    def test_movable(self):
        t = {"kind": "movable"}
        b, a = touch(self.d, "before.png"), touch(self.d, "after.png")
        base = {"item_before": "5.0 5.0 1.0", "player_end": "5.3 5.0 1.0", "shot_before": b, "shot_after": a}
        self.assertEqual(tq.judge(t, dict(base, item_after="5.4 5.1 1.0"), self.d)[0], "PASS")
        self.assertEqual(tq.judge(t, dict(base, item_after="5.0 5.0 1.0"), self.d)[:2], ("FAIL", "NOTMOVED"))
        self.assertEqual(tq.judge(t, dict(base, item_after="5.0 5.0 -4.0"), self.d)[:2], ("FAIL", "ITEMFELL"))
        far = dict(base, item_after="5.0 5.0 1.0", player_end="9.0 9.0 1.0")
        self.assertEqual(tq.judge(t, far, self.d)[:2], ("INCONCLUSIVE", "MISSED"))
        self.assertEqual(tq.judge(t, dict(base, item_after=None), self.d)[0], "INCONCLUSIVE")

    def test_travel(self):
        t = {"kind": "travel", "start": [0.0, 0.0, 0.0], "arrival": [100.0, 50.0, 2.0], "dest_cell": "B"}
        s = touch(self.d, "arrival.png")
        ok = {"start_read": "0.2 0.1 0.0", "prompt": True, "end_read": "101.0 50.5 2.0", "shot": s, "load_s": 9}
        self.assertEqual(tq.judge(t, ok, self.d)[0], "PASS")
        self.assertEqual(tq.judge(t, dict(ok, prompt=False), self.d)[:2], ("FAIL", "NOPROMPT"))
        self.assertEqual(tq.judge(t, dict(ok, end_read="0.5 0.2 0.0"), self.d)[:2], ("FAIL", "NOTRAVEL"))
        self.assertEqual(tq.judge(t, dict(ok, start_read="30 30 0"), self.d)[0], "INCONCLUSIVE")
        self.assertEqual(tq.judge(t, dict(ok, shot=None), self.d)[0], "INCONCLUSIVE")

    def test_route_uses_route_eval(self):
        routes = {"routes": [{"kind": "stairs", "start": [0, 0, 0],
                              "expect": {"low": [0, 0, 0], "high": [0, 3, 2], "min_rise": 1.6}}]}
        rf = os.path.join(self.d, "routes.json")
        json.dump(routes, open(rf, "w"))
        t = {"kind": "stairs", "routes_file": rf, "route_index": 0}
        up = {"result": {"start_read": "0 0 0", "end_read": "0 2.5 1.9"}, "shots": ["r0.png"]}
        self.assertEqual(tq.judge(t, up, self.d)[0], "PASS")
        stuck = {"result": {"start_read": "0 0 0", "end_read": "0 0.5 0.1"}, "shots": ["r0.png"]}
        self.assertEqual(tq.judge(t, stuck, self.d)[:2], ("FAIL", "STUCK"))
        self.assertEqual(tq.judge(t, dict(up, shots=[]), self.d)[0], "INCONCLUSIVE")
        self.assertEqual(tq.judge(t, {"result": {"skipped": "start not reached"}, "shots": ["x"]}, self.d)[0], "INCONCLUSIVE")


class FakeControls:
    def __init__(self):
        self.stop, self.mode, self.idle, self.foreign, self.fg, self.pid = None, "running", 10 ** 6, False, "starfield.exe", 42
        self.last_sent_tick = None

    def stop_file(self):
        return self.stop

    def guardian_mode(self):
        return self.mode

    def idle_s(self):
        return self.idle

    def foreign_input(self):
        return self.foreign

    def mark_sent(self):
        pass

    def game_in_front(self):
        return bool(self.pid) and self.fg == "starfield.exe"

    def game_pid(self):
        return self.pid

    def owned_pid(self):
        return 42

    def refocus_game(self):
        return True


def make_queue(d, n=3, kind="fall"):
    tests = [{"id": f"{k:04d}_{kind}", "kind": kind, "cell": "C", "ref": f"pt{k}", "model": "m.nif",
              "point": [0.0, 0.0, 0.0], "heading": 0} for k in range(n)]
    json.dump({"build_id": "abcd1234", "commit": "0" * 40, "staging": d, "plugin_sha256": "x", "save": "fo4sf_test_abcd1234",
               "plugin_index": "02", "hours": [[0, 24]], "tests": tests}, open(os.path.join(d, "queue.json"), "w"))


def args(**kw):
    base = dict(max_tests=10 ** 6, max_hours=1.0, min_idle=900, max_attempts=2, max_relaunch=3, wait_for_idle=False,
                refocus=False, dry_run=False, starfield="")
    base.update(kw)
    return SimpleNamespace(**base)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        make_queue(self.d)
        self.ctl = FakeControls()

    def runner(self, step, **kw):
        r = tq.Runner(self.d, args(**kw), ctl=self.ctl, step=step)
        r.session, r.cell = True, "C"                     # game already set up in the test cell
        r._ps = lambda *a, **k: (0, "at the cell")        # coc after an unknown state: never a real PowerShell here
        return r

    def landing(self, z):
        def step(test, out):
            json.dump({"end_read": f"0 0 {z}", "shot": touch(out, "fall.png")}, open(os.path.join(out, "obs.json"), "w"))
            return 0
        return step

    def results(self):
        return [json.loads(x) for x in open(os.path.join(self.d, "results.jsonl"))]

    def test_checkpoint_after_every_test_and_resume(self):
        self.runner(self.landing(0.1), max_tests=2).run()
        st = json.load(open(os.path.join(self.d, "state.json")))
        self.assertEqual(len(st["done"]), 2)
        calls = []

        def step(test, out):
            calls.append(test["id"])
            return self.landing(0.1)(test, out)
        self.runner(step).run()
        self.assertEqual(calls, ["0002_fall"])           # only the test that was left
        self.assertEqual(len(json.load(open(os.path.join(self.d, "state.json")))["done"]), 3)
        self.assertTrue(os.path.exists(os.path.join(self.d, "report.md")))

    def test_inconclusive_is_retried_up_to_the_limit_and_fail_is_final(self):
        calls = {}

        def step(test, out):
            calls[test["id"]] = calls.get(test["id"], 0) + 1
            if test["id"] == "0000_fall":
                return 0                                  # writes nothing: inconclusive
            return self.landing(-20)(test, out)           # fell through: FAIL
        self.runner(step, max_attempts=2).run()
        self.assertEqual(calls, {"0000_fall": 2, "0001_fall": 1, "0002_fall": 1})
        done = json.load(open(os.path.join(self.d, "state.json")))["done"]
        self.assertEqual(done["0000_fall"]["verdict"], "INCONCLUSIVE")
        self.assertEqual(done["0001_fall"]["verdict"], "FAIL")
        rep = json.load(open(os.path.join(self.d, "report.json")))
        self.assertEqual(rep["ranked"][0]["class"], "FALL")
        self.assertEqual(rep["ranked"][0]["count"], 2)

    def test_stop_file_and_guardian_stop_before_any_input(self):
        for setup in (lambda: setattr(self.ctl, "stop", "STOP"), lambda: setattr(self.ctl, "mode", "paused")):
            self.ctl = FakeControls()
            setup()
            calls = []
            r = self.runner(lambda t, o: calls.append(t) or 0)
            self.assertEqual(r.run(), 3)
            self.assertEqual(calls, [])
            self.assertTrue(json.load(open(os.path.join(self.d, "state.json")))["status"].startswith("stopped"))

    def test_owner_input_or_other_window_stops_without_counting_an_attempt(self):
        self.ctl.fg = "chrome.exe"
        calls = []
        self.assertEqual(self.runner(lambda t, o: calls.append(t) or 0).run(), 3)
        self.assertEqual(calls, [])
        self.ctl.fg = "starfield.exe"
        n = [0]

        def step(test, out):
            n[0] += 1
            return 2                                      # input guard tripped mid-step
        self.assertEqual(self.runner(step).run(), 3)
        st = json.load(open(os.path.join(self.d, "state.json")))
        self.assertEqual(st["done"], {})
        self.assertEqual(st["attempts"]["0000_fall"], 0)

    def test_crash_is_recorded_and_not_a_pass(self):
        def step(test, out):
            self.ctl.pid = None                           # the game exited during the step
            return 0
        r = self.runner(step, max_tests=1)
        r.run()
        self.assertEqual(self.results()[0]["class"], "CRASH")
        self.assertEqual(json.load(open(os.path.join(self.d, "state.json")))["crashes"], 1)

    def test_someone_elses_game_is_never_touched(self):
        self.ctl.pid = 7                                  # not the pid cycle.ps1 recorded
        calls = []
        r = tq.Runner(self.d, args(), ctl=self.ctl, step=lambda t, o: calls.append(t) or 0)
        self.assertEqual(r.run(), 3)
        self.assertEqual(calls, [])

    def test_launch_waits_for_an_idle_pc(self):
        self.ctl.pid, self.ctl.idle = None, 30            # no game yet, owner active 30 s ago
        r = tq.Runner(self.d, args(min_idle=900), ctl=self.ctl, step=lambda t, o: 0)
        r._ps = lambda *a, **k: self.fail("must not launch while the owner is active")
        self.assertEqual(r.run(), 3)


class StepScriptTests(unittest.TestCase):
    def test_qstep_handles_every_planned_kind(self):
        # the supervised run 2026-10-11 found "unknown kind stairs": the planner's kinds must all reach a step
        src = open(os.path.join(ROOT, "scripts", "game", "qstep.ps1"), encoding="utf-8").read()
        for kind in tq.KINDS:
            self.assertTrue(f"'{kind}'" in src, kind)
        self.assertIn("$kind -in 'stairs', 'door'", src)
        self.assertIn("enabled|disabled", src)


class ProbePointTests(unittest.TestCase):
    def test_floor_pieces_by_file_name_not_folder(self):
        import subprocess
        d = tempfile.mkdtemp()
        kit = "Interiors\Building\Deco\Small_FloorCeilKit\\"
        refs = [{"type": "Static", "model": kit + name, "pos": [70.0 * k * 5, 0.0, 0.0]} for k, name in
                enumerate(["BldDecoSmCeilOnly03.nif", "BldDecoSmFlrOnly04.nif", "BldWlpSmFlrCeil01.nif",
                           "SubPlatformWall03.nif", "BldWoodPSmStairsHalfTiny03.nif"])]
        json.dump({"cell": "C", "refs": refs}, open(os.path.join(d, "c.json"), "w"))
        out = os.path.join(d, "pts.txt")
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "game", "probe_points.py"), os.path.join(d, "c.json"),
                        out, "10"], check=True, capture_output=True)
        names = sorted(line.split(" ", 3)[3] for line in open(out).read().splitlines())
        self.assertEqual(names, ["BldDecoSmFlrOnly04.nif", "BldWlpSmFlrCeil01.nif", "BldWoodPSmStairsHalfTiny03.nif"])


class RecoverTests(RunnerTests):
    def test_menu_over_the_hud_is_escaped_once_then_the_test_retried(self):
        calls = []

        def step(test, out):
            calls.append(test["kind"])
            if test["kind"] == "recover":
                json.dump({"hud_before": False, "escapes": 1, "hud_after": True}, open(os.path.join(out, "obs.json"), "w"))
                return 0
            if calls.count("fall") == 1:
                json.dump({"stopped": "console not opened safely (3)"}, open(os.path.join(out, "obs.json"), "w"))
                return 3
            return self.landing(0.1)(test, out)
        self.runner(step, max_tests=2).run()
        self.assertEqual(calls[:3], ["fall", "recover", "fall"])

    def test_menu_that_stays_stops_the_run(self):
        def step(test, out):
            if test["kind"] == "recover":
                json.dump({"hud_before": False, "escapes": 3, "hud_after": False}, open(os.path.join(out, "obs.json"), "w"))
                return 0
            json.dump({"stopped": "console not opened safely (3)"}, open(os.path.join(out, "obs.json"), "w"))
            return 3
        self.assertEqual(self.runner(step).run(), 3)
        self.assertEqual(json.load(open(os.path.join(self.d, "state.json")))["status"], "stopped: menu or overlay")

    def test_no_escape_after_owner_input(self):
        calls = []

        def step(test, out):
            calls.append(test["kind"])
            self.ctl.foreign = True                       # the owner touched the PC during the step
            json.dump({"stopped": "console not opened safely (3)"}, open(os.path.join(out, "obs.json"), "w"))
            return 3
        self.assertEqual(self.runner(step).run(), 3)
        self.assertNotIn("recover", calls)


class BreakerTests(unittest.TestCase):
    def test_a_kind_that_never_decides_is_switched_off(self):
        d = tempfile.mkdtemp()
        make_queue(d, n=12)
        calls = []
        r = tq.Runner(d, args(max_attempts=1), ctl=FakeControls(), step=lambda t, o: calls.append(t) or 0)
        r.session, r.cell, r._ps = True, "C", (lambda *a, **k: (0, ""))
        r.run()
        self.assertEqual(len(calls), tq.BREAKER)
        done = json.load(open(os.path.join(d, "state.json")))["done"]
        self.assertEqual(sum(v["class"] == "BREAKER" for v in done.values()), 12 - tq.BREAKER)

    def test_a_kind_with_a_verdict_keeps_running(self):
        d = tempfile.mkdtemp()
        make_queue(d, n=10)
        calls = []

        def step(t, o):
            calls.append(t)
            if len(calls) == 1:
                json.dump({"end_read": "0 0 0.1", "shot": touch(o, "fall.png")}, open(os.path.join(o, "obs.json"), "w"))
            return 0
        r = tq.Runner(d, args(max_attempts=1), ctl=FakeControls(), step=step)
        r.session, r.cell, r._ps = True, "C", (lambda *a, **k: (0, ""))
        r.run()
        self.assertEqual(len(calls), 10)


class PopupTests(RunnerTests):
    def test_focus_lost_without_input_is_taken_back(self):
        refocused = []
        self.ctl.refocus_game = lambda: refocused.append(1) or setattr(self.ctl, "fg", "starfield.exe") or True
        r = self.runner(self.landing(0.1), refocus=True)
        r.ctl.last_sent_tick = 1
        self.ctl.fg = "steamwebhelper.exe"
        self.assertEqual(r.run(), 0)
        self.assertEqual(refocused, [1])

    def test_focus_lost_after_owner_input_is_not_taken_back(self):
        self.ctl.refocus_game = lambda: self.fail("must not refocus after owner input")
        r = self.runner(self.landing(0.1), refocus=True)
        r.ctl.last_sent_tick = 1
        self.ctl.fg, self.ctl.foreign = "chrome.exe", True
        self.assertEqual(r.run(), 3)


class ParseGetposTests(unittest.TestCase):
    def parse(self, text):
        import subprocess
        p = os.path.join(tempfile.mkdtemp(), "ocr.txt")
        open(p, "w").write(text)
        return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "game", "parse_getpos.py"), p],
                              capture_output=True, text=True).stdout.strip()

    def test_ocr_quirks(self):
        self.assertEqual(self.parse("GetPos: X >> -10.07\nGetPos: Y >> 43.95\nGetPos: Z >> -10.95\n"),
                         "-10.07 43.95 -10.95")
        # seen 2026-10-11: ">>" dropped, "Po s" split, older lines above the latest reply
        self.assertEqual(self.parse("GetPos: z 1.00\nprid 0200BA55\nGet Po s: X > > 9.71\nGetPos: Y > > -66.58\n"
                                    "GetPos: z 7.95\n"), "9.71 -66.58 7.95")


class ControlTests(unittest.TestCase):
    def test_hours(self):
        ctl = FakeControls()
        h = __import__("time").localtime().tm_hour
        self.assertIsNone(tq.blocked_reason(ctl, {"hours": [[0, 24]]}))
        self.assertIn("hours", tq.blocked_reason(ctl, {"hours": [[(h + 1) % 24, (h + 1) % 24 + 1]]}))


if __name__ == "__main__":
    unittest.main()


class TerrainTests(unittest.TestCase):
    def test_terrain_judge(self):
        d = tempfile.mkdtemp()
        shot = touch(d, "spawn.png")
        t = {"kind": "terrain", "points": [{"label": "ground", "x": -60.0, "y": -60.0, "expect": 10.0},
                                           {"label": "padA", "x": 30.0, "y": 30.0, "expect": 35.0}]}
        ok = {"shot": shot, "points": [{"read": "-60.0 -60.0 10.1"}, {"read": "30.0 30.0 35.0"}]}
        self.assertEqual(tq.judge(t, ok, d)[0], "PASS")
        scaled = {"shot": shot, "points": [{"read": "-60.0 -60.0 80.0"}, {"read": "30.0 30.0 280.0"}]}
        self.assertEqual(tq.judge(t, scaled, d)[:2], ("FAIL", "HEIGHTS"))
        void = {"shot": shot, "points": [{"read": "-60.0 -60.0 -400.0"}, {"read": "30.0 30.0 -380.0"}]}
        self.assertEqual(tq.judge(t, void, d)[:2], ("FAIL", "NOTERRAIN"))
        self.assertEqual(tq.judge(t, {"shot": shot, "points": [{"read": None}, {"read": "30 30 35"}]}, d)[0],
                         "INCONCLUSIVE")
        self.assertEqual(tq.judge(t, dict(ok, shot=None), d)[0], "INCONCLUSIVE")

    def test_plan_terrain(self):
        d = tempfile.mkdtemp()
        open(os.path.join(d, "FO4Port.esm"), "wb").write(b"TES4")
        exp = {b: {"ground": 10.0, "padA_x20-40_y20-40": h, "padB_x60-80_y20-40": 22.5, "pitC_x20-40_y60-80": 5.0}
               for b, h in (("FO4TX_World01.btd", 35.0), ("FO4TX_Shared02.btd", 45.0), ("FO4TX_World03.btd", 55.0))}
        json.dump(exp, open(os.path.join(d, "expected.json"), "w"))
        out = os.path.join(d, "q")
        tq.main(["plan-terrain", "--staging", d, "--exp-dir", d, "--out", out])
        q = json.load(open(os.path.join(out, "queue.json")))
        self.assertEqual([t["world_coc"] for t in q["tests"]], ["FO4TX_W01Spawn", "FO4TX_W02Spawn", "FO4TX_W03Spawn"])
        self.assertEqual([t["points"][1]["expect"] for t in q["tests"]], [35.0, 45.0, 55.0])
        self.assertTrue(all(t["cell"] == "" for t in q["tests"]))

    def test_qstep_has_the_terrain_step(self):
        src = open(os.path.join(ROOT, "scripts", "game", "qstep.ps1"), encoding="utf-8").read()
        self.assertIn("'terrain' {", src)
        self.assertIn("'recover' {", src)


class ExpInstallTests(unittest.TestCase):
    def test_install_and_uninstall_leave_nothing_behind(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
        import exp_install
        root = tempfile.mkdtemp()
        game, exp, local = (os.path.join(root, x) for x in ("game", "exp", "local"))
        os.makedirs(os.path.join(game, "Data"))
        os.makedirs(os.path.join(exp, "Data", "Terrain"))
        os.makedirs(os.path.join(local, "Starfield"))
        open(os.path.join(exp, "Exp.esm"), "wb").write(b"TES4")
        open(os.path.join(exp, "Data", "Terrain", "W.btd"), "wb").write(b"BTDB")
        plugins = os.path.join(local, "Starfield", "Plugins.txt")
        original = b"\xef\xbb\xbf# comment\r\n*FO4Port.esm\r\n"
        open(plugins, "wb").write(original)
        old = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = local
        try:
            exp_install.main(["install", "--exp-dir", exp, "--starfield", game])
            self.assertTrue(os.path.exists(os.path.join(game, "Data", "Terrain", "W.btd")))
            self.assertEqual(open(plugins, "rb").read(), original + b"*Exp.esm\r\n")
            exp_install.main(["install", "--exp-dir", exp, "--starfield", game])   # same experiment again: no-op
            self.assertEqual(open(plugins, "rb").read(), original + b"*Exp.esm\r\n")
            other = os.path.join(root, "other")
            os.makedirs(other)
            open(os.path.join(other, "Other.esm"), "wb").write(b"TES4")
            with self.assertRaises(SystemExit):           # a different experiment refuses
                exp_install.main(["install", "--exp-dir", other, "--starfield", game])
            exp_install.main(["uninstall", "--starfield", game])
            self.assertEqual(open(plugins, "rb").read(), original)
            self.assertEqual(sorted(os.listdir(os.path.join(game, "Data"))), [])
        finally:
            if old is None:
                os.environ.pop("LOCALAPPDATA")
            else:
                os.environ["LOCALAPPDATA"] = old

    def test_never_overwrites_game_files(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
        import exp_install
        root = tempfile.mkdtemp()
        game, exp = os.path.join(root, "game"), os.path.join(root, "exp")
        os.makedirs(os.path.join(game, "Data"))
        os.makedirs(exp)
        open(os.path.join(exp, "Exp.esm"), "wb").write(b"new")
        open(os.path.join(game, "Data", "Exp.esm"), "wb").write(b"theirs")
        with self.assertRaises(SystemExit):
            exp_install.main(["install", "--exp-dir", exp, "--starfield", game])
        self.assertEqual(open(os.path.join(game, "Data", "Exp.esm"), "rb").read(), b"theirs")


class LaunchIdleTests(unittest.TestCase):
    def test_runner_input_does_not_count_as_owner_activity_for_a_relaunch(self):
        ctl = FakeControls()
        ctl.idle, ctl.last_sent_tick = 5, 123             # only the runner's own keys a moment ago
        self.assertIsNone(tq.blocked_reason(ctl, {"hours": [[0, 24]]}, launching=True, min_idle=900))
        ctl.foreign = True                                # the owner touched the PC after that
        self.assertIn("owner active", tq.blocked_reason(ctl, {"hours": [[0, 24]]}, launching=True, min_idle=900))
        ctl.foreign, ctl.last_sent_tick = False, None     # nothing known: needs real idle time
        self.assertIn("owner active", tq.blocked_reason(ctl, {"hours": [[0, 24]]}, launching=True, min_idle=900))


class PreLaunchTests(unittest.TestCase):
    def run_with(self, pre):
        d = tempfile.mkdtemp()
        make_queue(d, n=1)
        q = json.load(open(os.path.join(d, "queue.json")))
        q["pre_launch"] = pre
        json.dump(q, open(os.path.join(d, "queue.json"), "w"))
        ctl = FakeControls()
        ctl.pid = None                                    # no game yet: the runner has to launch
        launched = []
        r = tq.Runner(d, args(), ctl=ctl, step=lambda t, o: 0)
        r.pinned_ok = lambda: True
        r._ps = lambda script, *a, **k: launched.append(script) or (1, "launch refused in the test")
        r.run()
        return launched, open(os.path.join(d, "run.log")).read()

    def test_pre_launch_runs_right_before_the_launch(self):
        launched, log = self.run_with([sys.executable, "-c", "print('installed')"])
        self.assertIn("pre-launch exit 0: installed", log)
        self.assertEqual(launched[:1], ["cycle.ps1"])

    def test_failed_pre_launch_stops_without_launching(self):
        launched, log = self.run_with([sys.executable, "-c", "import sys; sys.exit(3)"])
        self.assertEqual(launched, [])
        self.assertIn("pre-launch exit 3", log)


class PlanJsonTests(unittest.TestCase):
    def test_experiment_with_its_own_plan(self):
        d = tempfile.mkdtemp()
        open(os.path.join(d, "FO4Port.esm"), "wb").write(b"TES4")
        plan = [{"coc": "FO4CW_RedRocketSpawn", "label": "Red Rocket patch", "drop_z": 140,
                 "points": [{"label": "v0", "x": -1000.0, "y": 300.0, "expect": 101.2}]}]
        json.dump(plan, open(os.path.join(d, "plan.json"), "w"))
        out = os.path.join(d, "q")
        tq.main(["plan-terrain", "--staging", d, "--exp-dir", d, "--out", out])
        t = json.load(open(os.path.join(out, "queue.json")))["tests"]
        self.assertEqual([x["world_coc"] for x in t], ["FO4CW_RedRocketSpawn"])
        self.assertEqual(t[0]["drop_z"], 140.0)
        self.assertEqual(t[0]["beyond"], {"x": -500.0, "y": 300.0})
        json.dump([{"coc": "bad name; quit", "points": []}], open(os.path.join(d, "plan.json"), "w"))
        with self.assertRaises(SystemExit):               # typed into the console: letters, digits, _ only
            tq.main(["plan-terrain", "--staging", d, "--exp-dir", d, "--out", out])
