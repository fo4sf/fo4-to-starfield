"""Time of day and weather for queued game tests (scripts/game/sky_light.py, testqueue.py, runner_features.py): plan
fields are validated, only the whitelisted commands are typed, the light is read from the arrival camera before and
after the commands and from the probe shots, the judge says when the commands were not tested (the arrival was already
in daylight) and retries a night run, and a queue that needs these features is refused by a runner without them.
Synthetic data; no game. The step itself runs against the simulated game in tests/test_qstep_sandbox.py (opt-in)."""
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
import exp_install  # noqa: E402
import runner_features  # noqa: E402
import sky_light as sl  # noqa: E402
import testqueue as tq  # noqa: E402
from test_testqueue import FakeControls, args, jdump, jload, readf, touch, writef  # noqa: E402

SLT = ["SetLocalTime 12", "SetLocalTime 12 1", 'cgf "Game.SetLocalTime" 12']
METHODS = ["slt", "slt_galaxy", "cgf"]


class Bad(Exception):
    pass


def fail(msg):
    raise Bad(msg)


def png(path, sky, ground=40, h=720, w=64):
    im = np.full((h, w, 3), ground, np.uint8)
    im[:200] = sky
    Image.fromarray(im).save(path)
    return path


def light_obs(before, *afters, cmds=None, late=None, ocr=None):
    """obs.json "light": the arrival sky, then one try per reading (late: second-shot readings by try index)."""
    cmds = cmds or SLT[:len(afters)]
    tries = []
    for k, (c, a) in enumerate(zip(cmds, afters)):
        x = {"method": "weather" if c.startswith("fw") else METHODS[SLT.index(c)] if c in SLT else "slt", "cmd": c,
             "sky": a}
        if late and k in late:
            x["sky_late"] = late[k]
        if ocr and k in ocr:
            x["ocr"] = ocr[k]
        tries.append(x)
    return {"before": {"shot": "spawn.png", "sky": before}, "tries": tries}


def probes(*corners):
    return [{"label": f"p{k}", "read": "0 0 10.1", "corners": c} for k, c in enumerate(corners)]


class FieldTests(unittest.TestCase):
    def test_valid_fields(self):
        self.assertEqual(sl.light_fields({}, fail), {})
        self.assertEqual(sl.light_fields({"time_of_day": "12"}, fail), {"time_of_day": 12.0})
        got = sl.light_fields({"time_of_day": 6.254, "time_methods": ["cgf", "slt"], "weather": "0000015e",
                               "weather_lock": 1, "light_wait_ms": "2500", "need_daylight": True, "other": 1}, fail)
        self.assertEqual(got, {"time_of_day": 6.25, "time_methods": ["cgf", "slt"], "weather": "0000015E",
                               "weather_lock": True, "light_wait_ms": 2500, "need_daylight": True})
        self.assertEqual(sl.light_fields({"time_of_day": 23.994}, fail), {"time_of_day": 23.99})
        self.assertEqual(sl.light_fields({"time_of_day": 12, "time_repin": False}, fail),
                         {"time_of_day": 12.0, "time_repin": False})
        self.assertEqual(sl.light_fields({"time_of_day": 12, "time_repin": True}, fail), {"time_of_day": 12.0})

    def test_bad_fields_never_reach_the_console(self):
        for w in ({"time_of_day": 24}, {"time_of_day": -0.5}, {"time_of_day": "noon"}, {"time_of_day": float("nan")},
                  {"time_of_day": float("inf")}, {"time_of_day": 23.995}, {"time_of_day": 23.999},
                  {"time_of_day": True}, {"time_of_day": False},
                  {"time_of_day": 12, "time_methods": ["set gamehour to 12"]}, {"time_of_day": 12, "time_methods": []},
                  {"time_of_day": 12, "time_methods": ["slt", "slt"]}, {"time_of_day": 12, "time_methods": "slt"},
                  {"time_methods": ["slt"]}, {"time_repin": False}, {"time_of_day": 12, "time_repin": "no"},
                  {"weather": "15E"}, {"weather": "0000015E; tgm"}, {"weather_lock": True},
                  {"time_of_day": 12, "light_wait_ms": 60000}, {"time_of_day": 12, "light_wait_ms": "x"},
                  {"time_of_day": 12, "light_wait_ms": True}, {"need_daylight": True}):
            with self.assertRaises(Bad, msg=w):
                sl.light_fields(w, fail)

    def test_every_accepted_hour_is_typed_as_qstep_accepts_it(self):
        # qstep.ps1 refuses h >= 24 and the console whitelist allows 0..23.99: what light_fields lets through is typed
        # with at most two decimals and below 24
        import console_plan
        for h in (0, 0.004, 6.25, 12, 23.99, 23.994, "7.5"):
            t = sl.light_fields({"time_of_day": h}, fail)
            for c in sl.commands(t):
                self.assertTrue(console_plan.allowed(c), c)

    def test_commands_in_typing_order(self):
        self.assertEqual(sl.commands({}), [])
        self.assertEqual(sl.commands({"time_of_day": 12.0}), SLT)
        self.assertEqual(sl.commands({"time_of_day": 9.5, "time_methods": ["slt"], "weather": "0000015E",
                                      "weather_lock": True}), ["fw 0000015E 1", "SetLocalTime 9.5"])
        self.assertEqual(sl.commands({"time_of_day": 0.0, "time_methods": ["slt_galaxy"]}), ["SetLocalTime 0 1"])
        self.assertEqual(sl.commands({"time_of_day": 6.25, "time_methods": ["slt"]}), ["SetLocalTime 6.25"])

    def test_repin_only_for_terrain_time_of_day(self):
        self.assertTrue(sl.repins({"kind": "terrain", "time_of_day": 12.0}))
        self.assertFalse(sl.repins({"kind": "terrain", "time_of_day": 12.0, "time_repin": False}))
        self.assertFalse(sl.repins({"kind": "terrain", "weather": "0000015E"}))
        self.assertFalse(sl.repins({"kind": "npc_nav", "time_of_day": 12.0}))

    def test_qstep_has_the_same_table(self):
        src = readf(os.path.join(ROOT, "scripts", "game", "qstep.ps1"), encoding="utf-8")
        self.assertIn("""$table = @{ 'slt' = "SetLocalTime $h"; 'slt_galaxy' = "SetLocalTime $h 1"; """
                      """'cgf' = "cgf `"Game.SetLocalTime`" $h" }""", src)
        self.assertIn("@('slt', 'slt_galaxy', 'cgf')", src)
        self.assertEqual(sl.DEFAULT_LADDER, ("slt", "slt_galaxy", "cgf"))
        self.assertEqual(src.count("Apply-Light $lightCmds"), 3)          # terrain, npc_nav and door_trip
        self.assertEqual(src.count("$lightCmds = Light-Commands"), 3)     # validated before the travel
        self.assertIn("if ($t.time_of_day -is [bool])", src)
        self.assertIn("$hv = [Math]::Round([double]$t.time_of_day, 2)", src)
        # the only thing typed again before a probe is the ladder's own command that worked
        self.assertIn("$script:repin = $c.cmd", src)
        self.assertEqual(src.count("$script:repin = "), 2)                # the initial '' and the one assignment


class SkyTests(unittest.TestCase):
    @unittest.skipUnless(Image, "numpy / Pillow not installed")
    def test_measures_are_the_top_rows_and_the_top_corners(self):
        d = tempfile.mkdtemp()
        self.assertAlmostEqual(sl.brightness(png(os.path.join(d, "a.png"), 120, ground=10)), 120.0)
        self.assertAlmostEqual(sl.brightness(png(os.path.join(d, "b.png"), 8, ground=200)), 8.0)
        im = np.full((100, 80, 3), 200, np.uint8)
        im[:20, :20] = 30                                  # top fifth, left quarter
        im[:20, 60:] = 50                                  # top fifth, right quarter
        Image.fromarray(im).save(os.path.join(d, "c.png"))
        self.assertAlmostEqual(sl.measures(os.path.join(d, "c.png"))[1], 40.0)

    def test_classes_and_the_ladder_stop(self):
        self.assertEqual([sl.classify(v) for v in (None, 6.4, 30.0, 45.0, 60.0, 131.0)],
                         ["unread", "night", "night", "unclear", "daylight", "daylight"])
        self.assertEqual([sl.classify_corners(v) for v in (None, 37.0, 40.0, 42.0, 45.0, 47.5)],
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
        self.assertEqual(json.loads(r.stdout), {"sky": 110.0, "corners": 110.0, "class": "daylight",
                                                "corner_class": "daylight", "done": True})
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "game", "sky_light.py"), "measure",
                            os.path.join(d, "missing.png")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)["class"], "unread")


# The Mars arrivals of 2026-10-11 from the runner's save (C:\Modding\testqueue, read-only; docs/ai/test-queue.md):
# (spawn sky = arrival camera, probe-corner median or None without probes). Day site: longitude 1.2, night site -1.2.
DAY_SITE = [(115.4, 47.9), (105.8, 51.1), (130.7, 154.4), (114.3, 103.0), (96.4, 125.8), (119.2, 47.5), (7.3, 51.6),
            (131.0, 115.4), (103.0, 119.0), (107.4, 136.4), (118.6, 52.1), (49.9, 52.5), (131.6, 104.3)]
NIGHT_SITE = [(41.1, 22.6), (6.6, 32.9), (11.4, 7.7), (11.4, 27.8), (44.3, 30.3), (11.4, 21.8), (11.4, 31.1),
              (19.9, 34.5), (8.0, 6.8), (6.4, 34.5), (17.2, 37.0), (19.2, 34.5), (10.1, 6.7), (11.2, 34.8),
              (10.0, 36.0), (9.9, 36.1), (11.2, 31.7), (11.1, 33.7)]


class VerdictTests(unittest.TestCase):
    def test_not_asked(self):
        self.assertIsNone(sl.verdict({}, light_obs(12, 110)))

    def test_no_effect_is_night(self):
        v = sl.verdict({"time_of_day": 12}, light_obs(12.3, 13.0, 12.8, 12.9))
        self.assertEqual((v["light"], v["effect"], v["sky"], v["tested"], v["credited"]),
                         ("night", False, [12.3, 12.9], True, None))
        self.assertIn("sky 12.3 -> 12.9 after SetLocalTime 12; SetLocalTime 12 1; cgf", v["detail"])
        self.assertIn("no effect: night => night (asked for daylight)", v["detail"])

    def test_daylight_after_the_command_is_credited_to_it(self):
        v = sl.verdict({"time_of_day": 12}, light_obs(12.0, 110.0))
        self.assertEqual((v["light"], v["effect"], v["tested"], v["credited"], v["late"]),
                         ("daylight", True, True, "SetLocalTime 12", False))
        self.assertTrue(v["detail"].endswith("; daylight after SetLocalTime 12 => daylight"), v["detail"])

    def test_already_daylight_at_the_arrival_is_not_a_test_of_the_commands(self):
        # the verifier's case: every staged exp2t plan arrived where the sky already read daylight (110 -> 112)
        for before, after in ((110.0, 112.0), (115.0, 117.0), (105.8, 104.0)):
            v = sl.verdict({"time_of_day": 12}, light_obs(before, after))
            self.assertEqual((v["light"], v["tested"]), ("daylight", False))
            self.assertIn("already daylight at the arrival: the time commands were not tested", v["detail"])
            self.assertNotIn("after SetLocalTime 12 =>", v["detail"])

    def test_a_slow_change_is_credited_to_its_own_command(self):
        v = sl.verdict({"time_of_day": 12}, light_obs(12.0, 12.5, late={0: 109.0}))
        self.assertEqual((v["light"], v["credited"], v["late"], v["sky"]), ("daylight", "SetLocalTime 12", True,
                                                                            [12.0, 109.0]))
        self.assertIn("daylight after SetLocalTime 12 (on its second shot)", v["detail"])
        later = sl.verdict({"time_of_day": 12}, light_obs(12.0, 12.5, 110.0, late={0: 12.4}))
        self.assertEqual(later["credited"], "SetLocalTime 12 1")
        self.assertIn("(1 earlier command without a visible change, also on a second shot after another wait)",
                      later["detail"])

    def test_console_errors_are_reported(self):
        v = sl.verdict({"time_of_day": 12}, light_obs(12.0, 12.0, 12.0, 110.0, late={0: 12.0, 1: 12.0}, ocr={
            0: "SetLocalTime 12\nSetLocalTime only works on a planet.", 1: "SetLocalTime 12 1\nSetLocalTime only "
            "works on a planet.", 2: 'cgf "Game.SetLocalTime" 12'}))
        self.assertEqual(v["replies"], ["SetLocalTime 12: SetLocalTime only works on a planet",
                                        "SetLocalTime 12 1: SetLocalTime only works on a planet"])
        self.assertIn("(console: SetLocalTime 12: SetLocalTime only works on a planet;", v["detail"])
        self.assertEqual(v["credited"], 'cgf "Game.SetLocalTime" 12')

    def test_probes_decide_over_a_shaded_arrival_camera(self):
        # exp1d a1 (daylight site): the arrival fell into a pit (sky 7.3), its probes were in daylight
        v = sl.verdict({"kind": "terrain", "time_of_day": 12}, light_obs(7.3, 7.4, 7.2, 7.3), probes(51.6, 50.0, 53.0))
        self.assertEqual((v["light"], v["probes"]["class"], v["probes"]["corners"], v["credited"]),
                         ("daylight", "daylight", 51.6, None))
        self.assertIn("probes: 3 measured, corner median 51.6 -> daylight (the arrival camera read night: the probes "
                      "decide) => daylight", v["detail"])
        self.assertIn("whether the commands acted is unknown", v["detail"])
        # core64 0000 (night site): the arrival read 41.1 (unclear), its probes night
        v = sl.verdict({"time_of_day": 12}, light_obs(41.1, 41.0, 40.0, 41.5), probes(22.6, 20.0, 25.0))
        self.assertEqual(v["light"], "night")
        self.assertIn("=> night (asked for daylight)", v["detail"])

    def test_night_probes_are_named(self):
        v = sl.verdict({"time_of_day": 12}, light_obs(12.0, 110.0), probes(100, 104, 110, 12.0, 11.0))
        self.assertEqual((v["light"], v["probes"]["night"]), ("daylight", ["p3", "p4"]))
        self.assertIn("night at p3, p4", v["detail"])

    def test_the_reference_arrivals_all_read_right(self):
        # the arrival camera alone misreads 2 of 13 daylight arrivals (7.3, 49.9) and 2 of 18 night ones (41.1, 44.3);
        # with the probe shots every one of the 31 reads as its site
        for site, rows in (("daylight", DAY_SITE), ("night", NIGHT_SITE)):
            for sky, corners in rows:
                v = sl.verdict({"time_of_day": 12}, light_obs(sky, sky, sky, sky), probes(corners))
                self.assertEqual(v["light"], site, (sky, corners))
        cam = [sl.classify(s) for s, _ in DAY_SITE]
        self.assertEqual(cam.count("daylight"), 11)
        self.assertEqual(sorted(s for s, _ in NIGHT_SITE if sl.classify(s) != "night"), [41.1, 44.3])

    def test_unread(self):
        self.assertEqual(sl.verdict({"time_of_day": 12}, None)["light"], "unread")
        v = sl.verdict({"time_of_day": 12}, light_obs(12.0, None))
        self.assertEqual(v["light"], "unread")
        self.assertIn("no sky reading after the commands", v["detail"])
        nobefore = sl.verdict({"time_of_day": 12}, light_obs(None, 110.0))
        self.assertEqual((nobefore["light"], nobefore["effect"], nobefore["tested"]), ("daylight", None, None))

    def test_weather_only(self):
        v = sl.verdict({"weather": "0000015E"}, light_obs(12.0, 70.0, cmds=["fw 0000015E"]))
        self.assertEqual(v["light"], "daylight")
        self.assertIn("weather 0000015E: sky 12.0 -> 70.0 after fw 0000015E", v["detail"])


def terrain_obs(d, light, corners=None):
    pt = {"read": "0 0 10.1"}
    if corners is not None:
        pt["corners"] = corners
    return {"shot": touch(d, "spawn.png"), "points": [pt], "light": light}


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
        # the probe shots decide: a shaded arrival camera with daylight probes is daylight, and the other way round
        self.assertEqual(tq.judge(t, terrain_obs(d, light_obs(7.3, 7.3), corners=51.6), d)[:2], ("PASS", "PASS"))
        self.assertEqual(tq.judge(t, terrain_obs(d, light_obs(12, 110), corners=20.0), d)[:2], ("INCONCLUSIVE", "NIGHT"))
        wrong = dict(terrain_obs(d, light_obs(12, 13)), points=[{"read": "0 0 30.0"}])
        self.assertEqual(tq.judge(t, wrong, d)[:2], ("FAIL", "HEIGHTS"))     # a FAIL stays a FAIL at night
        # another arrival can read differently: neither NIGHT nor LIGHT is final
        self.assertNotIn("NIGHT", tq.FINAL_INCONCLUSIVE)
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
                        "time_methods": ["slt", "cgf"], "time_repin": False}, {"coc": "Other", "points": pts}])
        self.assertEqual((t[0]["time_of_day"], t[0]["need_daylight"], t[0]["time_methods"], t[0]["time_repin"]),
                         (12.0, True, ["slt", "cgf"], False))
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

    def test_step_timeout_counts_the_light_commands_and_the_probes(self):
        t = dict(TERRAIN)
        base = tq.step_timeout(t)
        self.assertEqual(base, 150 + 90 * 2)
        per_try = tq.LIGHT_TRY_S + 2 * 4
        self.assertEqual(tq.step_timeout(dict(t, time_of_day=12)),
                         base + 3 * per_try + 1 * (tq.LIGHT_PROBE_S + tq.REPIN_S))
        self.assertEqual(tq.step_timeout(dict(t, time_of_day=12, time_repin=False)),
                         base + 3 * per_try + 1 * tq.LIGHT_PROBE_S)
        self.assertEqual(tq.step_timeout(dict(t, time_of_day=12, time_methods=["slt"], weather="0000015E",
                                              light_wait_ms=1000)),
                         base + 2 * (tq.LIGHT_TRY_S + 2) + tq.LIGHT_PROBE_S + tq.REPIN_S)
        n = tq.npc_test(0, {"travel": "coc QASmoke", "npc": "0000CF96", "a": [0, 0, 0], "b": [10, 0, 0]})
        self.assertEqual(tq.step_timeout(dict(n, time_of_day=12)), tq.step_timeout(n) + 3 * per_try)


class RunnerFeatureTests(unittest.TestCase):
    """A queue planned with time of day or console lines must never run on a runner without them (the chain runs the
    integration worktree's runner): queue.json "needs", the runner's own check, and a pre_launch an older runner fails."""
    def setUp(self):
        self.d = tempfile.mkdtemp()
        writef(os.path.join(self.d, "FO4Port.esm"), b"TES4")
        self.out = os.path.join(self.d, "q")
        self.pts = [{"label": "p", "x": 1.0, "y": 2.0, "expect": 3.0}]

    def plan(self, entries, *extra):
        jdump(entries, os.path.join(self.d, "plan.json"))
        tq.main(["plan-terrain", "--staging", self.d, "--exp-dir", self.d, "--out", self.out, *extra])
        return jload(os.path.join(self.out, "queue.json"))

    def test_needs_and_pre_launch(self):
        q = self.plan([{"coc": "A", "points": self.pts, "time_of_day": 12,
                        "console_pre": ['GetINI "bBorderRegionsEnabled:General"']}], "--plugins", "Exp.esm,Exp_Mars.esm")
        self.assertEqual(q["needs"], ["console", "light"])
        pre = q["pre_launch"]
        # the runner's own exp_install.py (relative to the checkout testqueue.py runs it from), with --needs
        self.assertEqual(pre[1], os.path.join("scripts", "game", "exp_install.py"))
        self.assertEqual(pre[-2:], ["--needs", "console,light"])
        self.assertEqual(pre[pre.index("--exp-dir") + 1], os.path.abspath(self.d))
        plain = self.plan([{"coc": "A", "points": self.pts}], "--plugins", "Exp.esm")
        self.assertNotIn("needs", plain)
        self.assertNotIn("--needs", plain["pre_launch"])
        noplug = self.plan([{"coc": "A", "points": self.pts}], "--time-of-day", "12")
        self.assertEqual(noplug["pre_launch"][1:], [os.path.join("scripts", "game", "runner_features.py"), "check",
                                                   "light"])
        self.assertNotIn("pre_launch", self.plan([{"coc": "A", "points": self.pts}]))

    def test_the_pre_launch_paths_resolve_in_this_checkout(self):
        # testqueue.py runs pre_launch with cwd = its own checkout: both scripts must be there
        for rel in (("scripts", "game", "exp_install.py"), ("scripts", "game", "runner_features.py")):
            self.assertTrue(os.path.isfile(os.path.join(tq.REPO, *rel)), rel)
        r = subprocess.run([sys.executable, os.path.join("scripts", "game", "runner_features.py"), "check",
                            "console,light"], cwd=tq.REPO, capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "ok"))
        r = subprocess.run([sys.executable, os.path.join("scripts", "game", "runner_features.py"), "check",
                            "light,teleport2"], cwd=tq.REPO, capture_output=True, text=True)
        self.assertEqual(r.returncode, 5)
        self.assertIn("lacks teleport2", r.stdout)

    def test_exp_install_refuses_missing_features_before_installing(self):
        game = tempfile.mkdtemp()
        os.makedirs(os.path.join(game, "Data"))
        with self.assertRaises(SystemExit) as e:
            exp_install.main(["install", "--exp-dir", self.d, "--starfield", game, "--plugins", "FO4Port.esm",
                              "--needs", "light,teleport2"])
        self.assertEqual(e.exception.code, 5)
        self.assertEqual(os.listdir(os.path.join(game, "Data")), [])         # nothing installed

    def test_an_older_exp_install_refuses_the_option(self):
        # what a runner from before runner_features.py runs: argparse without --needs exits 2, so its ensure_game
        # stops ("pre-launch exit 2") before it launches the game
        import argparse
        old = argparse.ArgumentParser()
        old.add_argument("cmd")
        old.add_argument("--exp-dir")
        with self.assertRaises(SystemExit) as e, open(os.devnull, "w") as null:
            err, sys.stderr = sys.stderr, null
            try:
                old.parse_args(["install", "--exp-dir", "x", "--needs", "light"])
            finally:
                sys.stderr = err
        self.assertEqual(e.exception.code, 2)

    def test_runner_refuses_a_queue_it_cannot_run(self):
        d = tempfile.mkdtemp()
        test = dict(TERRAIN, id="0000_terrain_A", cell="", ref="A", model="m", time_of_day=12)
        jdump({"build_id": "abcd1234", "commit": "0" * 40, "staging": d, "plugin_sha256": "x", "save": "s",
               "plugin_index": "02", "hours": [[0, 24]], "needs": ["light", "teleport2"], "tests": [test]},
              os.path.join(d, "queue.json"))
        calls = []
        r = tq.Runner(d, args(), ctl=FakeControls(), step=lambda t, o: calls.append(t) or 0)
        r.session = True
        self.assertEqual(r.run(), 3)
        self.assertEqual(calls, [])
        self.assertIn("needs runner features ['teleport2']", readf(os.path.join(d, "run.log")))
        self.assertEqual(jload(os.path.join(d, "state.json"))["status"], "stopped: runner lacks teleport2")

    def test_planned_on_other_code_is_noted(self):
        self.assertIsNone(tq.planned_on_other_code(None))
        self.assertIsNone(tq.planned_on_other_code("not a commit"))
        head = subprocess.run(["git", "-C", tq.REPO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        if head:
            self.assertIsNone(tq.planned_on_other_code(head))
        self.assertIn("not found", tq.planned_on_other_code("1" * 40) or "")


class RunnerLightTests(unittest.TestCase):
    def test_night_is_recorded_reported_and_retried(self):
        d = tempfile.mkdtemp()
        test = dict(TERRAIN, id="0000_terrain_A", cell="", ref="A", model="exp2t", time_of_day=12, need_daylight=True)
        jdump({"build_id": "abcd1234", "commit": "0" * 40, "staging": d, "plugin_sha256": "x", "save": "s",
               "plugin_index": "02", "hours": [[0, 24]], "tests": [test]}, os.path.join(d, "queue.json"))
        calls = []

        def step(t, out):
            calls.append(t["id"])
            if len(calls) == 1:                           # a1: night (no effect), probes night too
                obs = terrain_obs(out, light_obs(12.3, 12.9, 13.1, 12.4), corners=20.0)
            else:                                         # a2: another arrival reads daylight
                obs = terrain_obs(out, light_obs(12.3, 110.0), corners=90.0)
            jdump(obs, os.path.join(out, "obs.json"))
            return 0
        r = tq.Runner(d, args(max_attempts=2), ctl=FakeControls(), step=step)
        r.session = True
        r.run()
        self.assertEqual(calls, ["0000_terrain_A"] * 2)                     # NIGHT is retried
        recs = [json.loads(x) for x in readf(os.path.join(d, "results.jsonl")).splitlines()]
        self.assertEqual([(x["verdict"], x["class"], x["light"]) for x in recs],
                         [("INCONCLUSIVE", "NIGHT", "night"), ("PASS", "PASS", "daylight")])
        self.assertEqual((recs[0]["sky"], recs[0]["light_tested"], recs[0]["light_credited"]), ([12.3, 12.4], True, None))
        self.assertEqual((recs[1]["light_credited"], recs[1]["light_probes"]["corners"]), ("SetLocalTime 12", 90.0))
        st = jload(os.path.join(d, "state.json"))
        self.assertEqual(st["breaker"]["terrain"]["inconclusive_run"], 0)  # NIGHT never trips the circuit breaker
        rep = readf(os.path.join(d, "report.md"), encoding="utf-8")
        self.assertIn("## Light", rep)
        self.assertIn("| 0000_terrain_A | daylight | 12.3 -> 110.0 | 90.0 (1) | yes | SetLocalTime 12 |", rep)
        self.assertEqual(jload(os.path.join(d, "report.json"))["light"][0]["light"], "daylight")

    def test_night_twice_ends_inconclusive(self):
        d = tempfile.mkdtemp()
        test = dict(TERRAIN, id="0000_terrain_A", cell="", ref="A", model="m", time_of_day=12, need_daylight=True)
        jdump({"build_id": "abcd1234", "commit": "0" * 40, "staging": d, "plugin_sha256": "x", "save": "s",
               "plugin_index": "02", "hours": [[0, 24]], "tests": [test]}, os.path.join(d, "queue.json"))

        def step(t, out):
            jdump(terrain_obs(out, light_obs(12.3, 12.9, 13.1, 12.4), corners=20.0), os.path.join(out, "obs.json"))
            return 0
        r = tq.Runner(d, args(max_attempts=2), ctl=FakeControls(), step=step)
        r.session = True
        r.run()
        self.assertEqual(jload(os.path.join(d, "state.json"))["done"]["0000_terrain_A"],
                         {"verdict": "INCONCLUSIVE", "class": "NIGHT", "attempts": 2})


if __name__ == "__main__":
    unittest.main()
