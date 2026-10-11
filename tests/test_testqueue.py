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
