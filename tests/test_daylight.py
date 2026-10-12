"""Time of day and weather for queued game tests (scripts/game/sky_light.py, testqueue.py): plan fields are validated,
only the whitelisted commands are typed, the sky brightness is the mean of the top rows, and the judge marks a run night
when the commands left a dark sky as it was. Synthetic data; no game. The step itself runs against the simulated game in
tests/test_qstep_sandbox.py (opt-in)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

try:                                   # the sky measure needs numpy + Pillow (the runner's venv); the rest does not
    import numpy as np
    from PIL import Image
except ImportError:
    np = Image = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sky_light as sl  # noqa: E402
import testqueue as tq  # noqa: E402
from test_testqueue import FakeControls, args, jdump, jload, readf, touch, writef  # noqa: E402


class Bad(Exception):
    pass


def fail(msg):
    raise Bad(msg)


def png(path, sky, ground=40, h=720, w=64):
    im = np.full((h, w, 3), ground, np.uint8)
    im[:200] = sky
    Image.fromarray(im).save(path)
    return path


def light_obs(before, *afters, cmds=None):
    cmds = cmds or ["SetLocalTime 12", "SetLocalTime 12 1", 'cgf "Game.SetLocalTime" 12'][:len(afters)]
    return {"before": {"shot": "spawn.png", "sky": before},
            "tries": [{"cmd": c, "sky": a} for c, a in zip(cmds, afters)]}


class FieldTests(unittest.TestCase):
    def test_valid_fields(self):
        self.assertEqual(sl.light_fields({}, fail), {})
        self.assertEqual(sl.light_fields({"time_of_day": "12"}, fail), {"time_of_day": 12.0})
        got = sl.light_fields({"time_of_day": 6.254, "time_methods": ["cgf", "slt"], "weather": "0000015e",
                               "weather_lock": 1, "light_wait_ms": "2500", "need_daylight": True, "other": 1}, fail)
        self.assertEqual(got, {"time_of_day": 6.25, "time_methods": ["cgf", "slt"], "weather": "0000015E",
                               "weather_lock": True, "light_wait_ms": 2500, "need_daylight": True})

    def test_bad_fields_never_reach_the_console(self):
        for w in ({"time_of_day": 24}, {"time_of_day": -0.5}, {"time_of_day": "noon"}, {"time_of_day": float("nan")},
                  {"time_of_day": 12, "time_methods": ["set gamehour to 12"]}, {"time_of_day": 12, "time_methods": []},
                  {"time_of_day": 12, "time_methods": ["slt", "slt"]}, {"time_of_day": 12, "time_methods": "slt"},
                  {"time_methods": ["slt"]}, {"weather": "15E"}, {"weather": "0000015E; tgm"}, {"weather_lock": True},
                  {"time_of_day": 12, "light_wait_ms": 60000}, {"time_of_day": 12, "light_wait_ms": "x"},
                  {"need_daylight": True}):
            with self.assertRaises(Bad, msg=w):
                sl.light_fields(w, fail)

    def test_commands_in_typing_order(self):
        self.assertEqual(sl.commands({}), [])
        self.assertEqual(sl.commands({"time_of_day": 12.0}),
                         ["SetLocalTime 12", "SetLocalTime 12 1", 'cgf "Game.SetLocalTime" 12'])
        self.assertEqual(sl.commands({"time_of_day": 9.5, "time_methods": ["slt"], "weather": "0000015E",
                                      "weather_lock": True}), ["fw 0000015E 1", "SetLocalTime 9.5"])
        self.assertEqual(sl.commands({"time_of_day": 0.0, "time_methods": ["slt_galaxy"]}), ["SetLocalTime 0 1"])
        self.assertEqual(sl.commands({"time_of_day": 6.25, "time_methods": ["slt"]}), ["SetLocalTime 6.25"])

    def test_qstep_has_the_same_table(self):
        src = readf(os.path.join(ROOT, "scripts", "game", "qstep.ps1"), encoding="utf-8")
        self.assertIn("""$table = @{ 'slt' = "SetLocalTime $h"; 'slt_galaxy' = "SetLocalTime $h 1"; """
                      """'cgf' = "cgf `"Game.SetLocalTime`" $h" }""", src)
        self.assertIn("@('slt', 'slt_galaxy', 'cgf')", src)
        self.assertEqual(sl.DEFAULT_LADDER, ("slt", "slt_galaxy", "cgf"))
        self.assertEqual(src.count("Apply-Light $lightCmds"), 2)          # terrain and npc_nav
        self.assertEqual(src.count("$lightCmds = Light-Commands"), 2)     # validated before the travel


class SkyTests(unittest.TestCase):
    @unittest.skipUnless(Image, "numpy / Pillow not installed")
    def test_brightness_is_the_mean_of_the_top_rows(self):
        d = tempfile.mkdtemp()
        self.assertAlmostEqual(sl.brightness(png(os.path.join(d, "a.png"), 120, ground=10)), 120.0)
        self.assertAlmostEqual(sl.brightness(png(os.path.join(d, "b.png"), 8, ground=200)), 8.0)

    def test_classes_and_the_ladder_stop(self):
        self.assertEqual([sl.classify(v) for v in (None, 6.4, 30.0, 45.0, 60.0, 131.0)],
                         ["unread", "night", "night", "unclear", "daylight", "daylight"])
        self.assertEqual([sl.expected(h) for h in (None, 0, 4.9, 6, 7, 12, 17, 18, 19.5)],
                         [None, "night", "night", None, "daylight", "daylight", "daylight", None, "night"])
        self.assertTrue(sl.done(12, 110, 12))
        self.assertFalse(sl.done(12, 14, 12))             # asked for noon, still dark: try the next command
        self.assertFalse(sl.done(12, 45, 12))             # unclear is not daylight
        self.assertTrue(sl.done(110, 12, 23))
        self.assertTrue(sl.done(12, 40, 18))              # twilight: any clear change
        self.assertFalse(sl.done(12, 20, 18))
        self.assertFalse(sl.done(None, 40, 18))
        self.assertFalse(sl.done(12, None, 12))

    @unittest.skipUnless(Image, "numpy / Pillow not installed")
    def test_measure_prints_one_json_line(self):
        d = tempfile.mkdtemp()
        p = png(os.path.join(d, "sky.png"), 110)
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "game", "sky_light.py"), "measure", p,
                            "--before", "12", "--hour", "12"], capture_output=True, text=True)
        self.assertEqual(json.loads(r.stdout), {"sky": 110.0, "class": "daylight", "done": True})
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "game", "sky_light.py"), "measure",
                            os.path.join(d, "missing.png")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)["class"], "unread")


class VerdictTests(unittest.TestCase):
    def test_not_asked(self):
        self.assertIsNone(sl.verdict({}, light_obs(12, 110)))

    def test_no_effect_is_night(self):
        v = sl.verdict({"time_of_day": 12}, light_obs(12.3, 13.0, 12.8, 12.9))
        self.assertEqual((v["light"], v["effect"], v["sky"]), ("night", False, [12.3, 12.9]))
        self.assertIn("sky 12.3 -> 12.9 after SetLocalTime 12; SetLocalTime 12 1; cgf", v["detail"])
        self.assertIn("no effect: night (asked for daylight)", v["detail"])

    def test_daylight(self):
        v = sl.verdict({"time_of_day": 12}, light_obs(12.0, 110.0))
        self.assertEqual((v["light"], v["effect"]), ("daylight", True))
        self.assertTrue(v["detail"].endswith("; daylight"), v["detail"])
        already = sl.verdict({"time_of_day": 12}, light_obs(115.0, 117.0))
        self.assertEqual((already["light"], already["effect"]), ("daylight", False))
        self.assertNotIn("no effect", already["detail"])

    def test_unread(self):
        self.assertEqual(sl.verdict({"time_of_day": 12}, None)["light"], "unread")
        v = sl.verdict({"time_of_day": 12}, light_obs(12.0, None))
        self.assertEqual(v["light"], "unread")
        self.assertIn("no sky reading after the commands", v["detail"])
        nobefore = sl.verdict({"time_of_day": 12}, light_obs(None, 110.0))
        self.assertEqual((nobefore["light"], nobefore["effect"]), ("daylight", None))

    def test_weather_only(self):
        v = sl.verdict({"weather": "0000015E"}, light_obs(12.0, 70.0, cmds=["fw 0000015E"]))
        self.assertEqual(v["light"], "daylight")
        self.assertIn("weather 0000015E: sky 12.0 -> 70.0 after fw 0000015E", v["detail"])


def terrain_obs(d, light):
    return {"shot": touch(d, "spawn.png"), "points": [{"read": "0 0 10.1"}], "light": light}


TERRAIN = {"kind": "terrain", "points": [{"label": "ground", "x": 0.0, "y": 0.0, "expect": 10.0}]}


class JudgeTests(unittest.TestCase):
    def test_light_goes_into_the_detail(self):
        d = tempfile.mkdtemp()
        v = tq.judge(dict(TERRAIN, time_of_day=12), terrain_obs(d, light_obs(12, 13, 12, 12)), d)
        self.assertEqual(v[:2], ("PASS", "PASS"))
        self.assertIn("[light: local hour 12: sky 12.0 -> 12.0", v[2])
        self.assertIn("no effect: night", v[2])
        plain = tq.judge(TERRAIN, terrain_obs(d, None), d)
        self.assertNotIn("light", plain[2])

    def test_need_daylight(self):
        d = tempfile.mkdtemp()
        t = dict(TERRAIN, time_of_day=12, need_daylight=True)
        self.assertEqual(tq.judge(t, terrain_obs(d, light_obs(12, 13)), d)[:2], ("INCONCLUSIVE", "NIGHT"))
        self.assertEqual(tq.judge(t, terrain_obs(d, light_obs(12, 45)), d)[:2], ("INCONCLUSIVE", "NIGHT"))
        self.assertEqual(tq.judge(t, terrain_obs(d, None), d)[:2], ("INCONCLUSIVE", "LIGHT"))
        self.assertEqual(tq.judge(t, terrain_obs(d, light_obs(12, 110)), d)[:2], ("PASS", "PASS"))
        wrong = dict(terrain_obs(d, light_obs(12, 13)), points=[{"read": "0 0 30.0"}])
        self.assertEqual(tq.judge(t, wrong, d)[:2], ("FAIL", "HEIGHTS"))     # a FAIL stays a FAIL at night
        self.assertIn("NIGHT", tq.FINAL_INCONCLUSIVE)
        self.assertNotIn("LIGHT", tq.FINAL_INCONCLUSIVE)

    def test_npc_nav_gets_the_light_too(self):
        t = tq.npc_test(0, {"travel": "coc QASmoke", "npc": "0000CF96", "a": [0, 0, 0], "b": [10, 0, 0],
                            "time_of_day": 12})
        self.assertEqual(t["time_of_day"], 12.0)
        v = tq.judge(t, {"light": light_obs(12, 110)}, tempfile.mkdtemp())
        self.assertIn("[light: local hour 12", v[2])


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        writef(os.path.join(self.d, "FO4Port.esm"), b"TES4")
        self.out = os.path.join(self.d, "q")

    def plan(self, entries, *extra):
        jdump(entries, os.path.join(self.d, "plan.json"))
        tq.main(["plan-terrain", "--staging", self.d, "--exp-dir", self.d, "--out", self.out, "--fresh", *extra])
        return jload(os.path.join(self.out, "queue.json"))["tests"]

    def test_plan_terrain_keeps_the_light_fields(self):
        pts = [{"label": "p", "x": 1.0, "y": 2.0, "expect": 3.0}]
        t = self.plan([{"coc": "FO4CW_RedRocketSpawn", "points": pts, "time_of_day": 12, "need_daylight": True,
                        "time_methods": ["slt", "cgf"]}, {"coc": "Other", "points": pts}])
        self.assertEqual((t[0]["time_of_day"], t[0]["need_daylight"], t[0]["time_methods"]), (12.0, True, ["slt", "cgf"]))
        self.assertNotIn("time_of_day", t[1])
        self.assertTrue(all(x["fresh"] for x in t))

    def test_command_line_wins_for_every_test(self):
        pts = [{"label": "p", "x": 1.0, "y": 2.0, "expect": 3.0}]
        t = self.plan([{"coc": "A", "points": pts, "time_of_day": 20}, {"coc": "B", "points": pts}],
                      "--time-of-day", "12", "--need-daylight", "--weather", "0000015e")
        self.assertEqual([(x["time_of_day"], x["weather"], x.get("need_daylight")) for x in t],
                         [(12.0, "0000015E", True), (12.0, "0000015E", True)])

    def test_bad_plan_stops_planning(self):
        pts = [{"label": "p", "x": 1.0, "y": 2.0, "expect": 3.0}]
        with self.assertRaises(SystemExit):
            self.plan([{"coc": "A", "points": pts, "time_of_day": 25}])
        with self.assertRaises(SystemExit):
            self.plan([{"coc": "A", "points": pts}], "--time-methods", "slt,gamehour", "--time-of-day", "12")

    def test_step_timeout_counts_the_light_commands(self):
        t = dict(TERRAIN)
        base = tq.step_timeout(t)
        self.assertEqual(base, 150 + 90 * 2)
        self.assertEqual(tq.step_timeout(dict(t, time_of_day=12)), base + 3 * (tq.LIGHT_TRY_S + 4))
        self.assertEqual(tq.step_timeout(dict(t, time_of_day=12, time_methods=["slt"], weather="0000015E",
                                              light_wait_ms=1000)), base + 2 * (tq.LIGHT_TRY_S + 1))
        n = tq.npc_test(0, {"travel": "coc QASmoke", "npc": "0000CF96", "a": [0, 0, 0], "b": [10, 0, 0]})
        self.assertEqual(tq.step_timeout(dict(n, time_of_day=12)), tq.step_timeout(n) + 3 * (tq.LIGHT_TRY_S + 4))


class RunnerLightTests(unittest.TestCase):
    def test_night_is_recorded_reported_and_not_retried(self):
        d = tempfile.mkdtemp()
        test = dict(TERRAIN, id="0000_terrain_A", cell="", ref="A", model="exp2t", time_of_day=12, need_daylight=True)
        jdump({"build_id": "abcd1234", "commit": "0" * 40, "staging": d, "plugin_sha256": "x", "save": "s",
               "plugin_index": "02", "hours": [[0, 24]], "tests": [test]}, os.path.join(d, "queue.json"))
        calls = []

        def step(t, out):
            calls.append(t["id"])
            jdump(terrain_obs(out, light_obs(12.3, 12.9, 13.1, 12.4)), os.path.join(out, "obs.json"))
            return 0
        r = tq.Runner(d, args(max_attempts=2), ctl=FakeControls(), step=step)
        r.session = True
        r.run()
        self.assertEqual(calls, ["0000_terrain_A"])                          # NIGHT is final: no retry
        rec = [json.loads(x) for x in readf(os.path.join(d, "results.jsonl")).splitlines()][0]
        self.assertEqual((rec["verdict"], rec["class"], rec["light"], rec["sky"]), ("INCONCLUSIVE", "NIGHT", "night",
                                                                                     [12.3, 12.4]))
        rep = readf(os.path.join(d, "report.md"), encoding="utf-8")
        self.assertIn("## Light", rep)
        self.assertIn("| 0000_terrain_A | night | 12.3 -> 12.4 |", rep)
        self.assertEqual(jload(os.path.join(d, "report.json"))["light"][0]["light"], "night")


if __name__ == "__main__":
    unittest.main()
