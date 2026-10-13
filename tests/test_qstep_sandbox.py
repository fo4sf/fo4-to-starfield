"""End-to-end run of qstep.ps1's npc_nav step against a simulated console (tests/qstep_sandbox), judged by testqueue.
Opt-in (each scenario starts ~60 PowerShell processes, about 25 s): set FO4SF_QSTEP_SANDBOX=1 on Windows.

Safety: the real qstep.ps1, parse_npc.py and parse_getpos.py are copied into a temporary folder next to the sandbox
fakes, so every helper the step calls (input.ps1, console_open.ps1, readpos.ps1, shot*.ps1, ocr.ps1) is a fake that
never sends input; nothing in scripts/game is run except the copied step itself."""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "scripts", "game")
SANDBOX = os.path.join(ROOT, "tests", "qstep_sandbox")
sys.path.insert(0, GAME)
import testqueue as tq  # noqa: E402
import walk_eval  # noqa: E402

ENABLED = os.name == "nt" and os.environ.get("FO4SF_QSTEP_SANDBOX") == "1"
N0 = {"label": "N0_ptr", "travel": "coc QASmoke", "npc": "0000CF96", "a": [-8, -4, 0], "b": [5, 10, 0],
      "drop": 0.5, "settle_ms": 0, "method": "ptr_player", "reads_s": [0, 2, 4, 7], "control": True}
WORLD = {"player": [0, 0, 0], "arrival": [0, 0, 0], "actors": {}, "log": [], "speed": 4.0, "sel": None}
N1 = {"travel": "coc FO4CW_RedRocketSpawn", "a": [-987.43, 1128.23, 105.03], "b": [-976.46, 1144.69, 105.03],
      "anchor": {"ref": "02000800", "local": [-989.03, 1147.2, 105.14]}, "spawn_local": [-989.03, 1147.2, 105.14]}
MARS = {"anchor_id": "02000800", "anchor_pos": [2010.97, -2352.8, 85.14], "arrival": [2010.97, -2352.8, 85.14]}


class SandboxStep:
    """Runs the copied qstep.ps1 against the simulated game (mixed into the opt-in test classes below)."""
    def run_step(self, plan=None, world=None, test=None, code=0):
        d = tempfile.mkdtemp(prefix="qstep_npc_")
        step_dir = os.path.join(d, "game")
        shutil.copytree(SANDBOX, step_dir)
        for f in ("qstep.ps1", "parse_npc.py", "parse_getpos.py", "sky_light.py", "walk_eval.py"):
            shutil.copy(os.path.join(GAME, f), step_dir)
        state = os.path.join(d, "state.json")
        with open(state, "w") as f:
            json.dump(dict(WORLD, **(world or {})), f)
        t = test or tq.npc_test(0, dict(N0, **(plan or {})))
        spec, out = os.path.join(d, "spec.json"), os.path.join(d, "out")
        with open(spec, "w") as f:
            json.dump(t, f)
        saves = os.path.join(d, "saves")
        os.makedirs(saves)
        env = dict(os.environ, FAKE_STATE=state, FO4SF_PYTHON=sys.executable, FO4SF_NO_FOCUS_STEAL="1", LEGACY="1",
                   FO4SF_SAVES_DIR=saves)
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                            os.path.join(step_dir, "qstep.ps1"), "-Spec", spec, "-Out", out],
                           capture_output=True, text=True, env=env, timeout=600)
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        if code:                                              # a refused spec: what (if anything) reached the console
            with open(state) as f:
                self.typed = json.load(f).get("typed", [])
            return r.stdout, None, None
        with open(os.path.join(out, "obs.json"), encoding="utf-8-sig") as f:
            obs = json.load(f)
        with open(state) as f:
            st = json.load(f)
        left = [k for k, a in st["actors"].items() if not (a.get("disabled") and a.get("deleted"))]
        self.typed = st.get("typed", [])
        self.state = st
        # a selection that stayed on the floor static must never get disable (N0_base's spawn session had one)
        self.assertEqual([k for k, v in st.get("statics", {}).items() if v.get("disabled") or v.get("deleted")], [])
        return tq.judge(t, obs, out), obs, left

    def check(self, want, plan=None, world=None, removed=True):
        v, obs, left = self.run_step(plan, world)
        self.assertEqual(v[:2], want, v[2])
        if removed:
            self.assertEqual(left, [], obs.get("cleanup"))
        return obs


@unittest.skipUnless(ENABLED, "opt-in: FO4SF_QSTEP_SANDBOX=1 on Windows")
class QstepNpcSandboxTests(SandboxStep, unittest.TestCase):
    def test_walk_is_a_pass_and_the_actor_is_removed(self):
        obs = self.check(("PASS", "PASS"))
        self.assertEqual(obs["cleanup"]["via"], "prid")       # by PickLastRef's id
        self.assertEqual(obs["command"], "PathToRef player")
        sp = obs["spawn"]
        self.assertEqual((sp["ref"], sp["self"], sp["isid"], sp["confirmed"]), ("FF000800", "FF000800", 1, True))
        self.assertTrue(all(s["via"] == "prid" for s in obs["samples"]))

    def test_no_walk_is_nonav(self):
        self.check(("FAIL", "NONAV"), world={"speed": 0.0})

    def test_the_spawn_session_of_2026_10_11(self):
        # what N0_base met in game: ClearConsole leaves the older lines, the console selects the floor static under
        # the crosshair, the game prints GetInFaction lines after placeatme, the actor is not ready while the console
        # is open, OCR reads l for I (all fake defaults). The old step typed placeatme, plr, GetIsID, GetSelf in one
        # session and read GetIsID 0 / GetSelf (0024a824); the handle is now read after the console was closed
        obs = self.check(("PASS", "PASS"), plan={"method": "none", "control": False})
        sp = obs["spawn"]
        self.assertTrue(sp["confirmed"], sp["why"])
        self.assertIn("GetlnFaction", sp["place_ocr"])
        self.assertIn("PickLastRef", sp["plr_ocr"])
        self.assertLessEqual(sp["dist_a"], 2.0)
        self.assertEqual(obs["cleanup"]["via"], "prid")
        at = self.typed.index("player.placeatme 0000CF96 1")
        self.assertEqual(self.typed[at + 1:at + 3], ["ClearConsole", "plr"])    # a new session: the console was closed

    def test_plr_that_never_selects_is_taken_by_id(self):
        # the worst reading of the N0_base spawn: PickLastRef names the ref but never selects it; prid <id> does
        obs = self.check(("PASS", "PASS"), world={"plr_selects": False})
        self.assertTrue(all(s["via"] == "prid" for s in obs["samples"]))

    def test_a_selection_that_stays_on_the_static_is_never_used(self):
        # neither plr nor prid select anything: the console keeps the floor static. GetSelf names it: no walk, no
        # disable; the actor is left in the (never saved) session and the note says so
        v, obs, left = self.run_step(world={"plr_selects": False, "prid_fails": True})
        self.assertEqual(v[:2], ("INCONCLUSIVE", "SPAWN"), v[2])
        self.assertIn("GetSelf named 0024A824", obs["spawn"]["why"])
        self.assertNotIn("samples", obs)
        self.assertFalse(obs["cleanup"]["removed"])
        self.assertEqual(obs["cleanup"]["by_plr"]["self"], "0024A824")
        self.assertEqual(left, ["FF000800"])
        self.assertNotIn("disable", self.typed)

    def test_unconfirmed_spawn_is_removed_by_its_id(self):
        # GetIsID does not match (a templated actor?): not confirmed, nothing commanded, removed as the ref PickLastRef
        # named at the spawn, at the player's feet, which GetSelf names
        obs = self.check(("INCONCLUSIVE", "SPAWN"), world={"isid_ok": False})
        self.assertEqual(obs["cleanup"]["via"], "plr")
        self.assertIn("GetIsID 0000CF96 read 0", obs["spawn"]["why"])
        self.assertNotIn("samples", obs)                      # nothing commanded on an unconfirmed handle

    def test_world_frame_from_the_anchor(self):
        obs = self.check(("PASS", "PASS"), plan=N1, world=MARS)
        self.assertEqual(obs["offset_from"], "anchor")

    def test_failed_spawn_types_nothing_on_the_selection(self):
        obs = self.check(("INCONCLUSIVE", "SPAWN"), world={"spawn_fails": True}, removed=False)
        self.assertFalse(obs["cleanup"]["removed"])

    def test_cf_is_typed_with_its_quotes(self):
        # Windows PowerShell 5.1 dropped the quotes of a native argument: the console got cf Actor.PathToReference
        cf = 'cf "Actor.PathToReference" player 1.0'
        obs = self.check(("PASS", "PASS"), plan={"method": "cf_pathto_player"},
                         world={"accepts": cf.lower()})
        self.assertEqual(obs["command"], cf)
        self.assertIn(cf, self.typed)
        self.assertNotIn("cf Actor.PathToReference player 1.0", self.typed)

    def test_column_ocr_layout(self):
        # real console OCR lists labels first, then values, and loses a lone "y" argument (2026-10-11)
        obs = self.check(("PASS", "PASS"), world={"layout": "column"})
        self.assertEqual(obs["cleanup"]["via"], "prid")
        self.assertEqual(obs["spawn"]["how"], "order")
        self.assertEqual(obs["spawn"]["self"], "FF000800")
        self.assertTrue(all(s["isid"] == 1 for s in obs["samples"]))

    def test_anchor_reading_its_local_position_falls_back_to_the_arrival(self):
        # exp2b 2026-10-11: prid 02000800 + getpos gave -989.03 1147.20 105.14, the anchor's unmerged local position
        world = dict(MARS, anchor_pos=[-989.03, 1147.2, 105.14])
        obs = self.check(("PASS", "PASS"), plan=N1, world=world)
        self.assertTrue(obs["anchor_unmerged"])
        self.assertEqual(obs["offset_from"], "spawn")
        self.assertEqual([round(v, 2) for v in obs["offset"]], [3000.0, -3500.0, -20.0])

    def test_offset_waits_for_the_arrival_to_land(self):
        # exp1d read the arrival mid-fall: the Z offset comes from a read that no longer moves
        world = dict(MARS, anchor_pos=[-989.03, 1147.2, 105.14], fall={"height": 150.0, "speed": 12.0})
        obs = self.check(("PASS", "PASS"), plan=N1, world=world)
        self.assertTrue(obs["spawn_settled"])
        self.assertGreater(len(obs["spawn_reads"]), 2)
        self.assertAlmostEqual(obs["offset"][2], -20.0, places=1)

    def test_an_arrival_that_never_lands_spawns_nothing(self):
        world = dict(MARS, anchor_pos=[-989.03, 1147.2, 105.14], fall={"height": 100000.0, "speed": 5.0})
        v, obs, left = self.run_step(N1, world)
        self.assertEqual(v[:2], ("INCONCLUSIVE", "ANCHOR"), v[2])
        self.assertIn("still moving", obs["offset_missing"])
        self.assertNotIn("spawn", obs)
        self.assertEqual(left, [])

    def test_baseline_types_no_command(self):
        obs = self.check(("PASS", "PASS"), plan={"method": "none", "control": False})
        self.assertEqual(obs["command"], "")
        self.assertFalse([c for c in self.typed if c.lower().startswith(("pathtoref", "cf ", "setplayerteammate"))])


@unittest.skipUnless(ENABLED, "opt-in: FO4SF_QSTEP_SANDBOX=1 on Windows")
class QstepLightSandboxTests(SandboxStep, unittest.TestCase):
    """Time of day / weather (sky_light.py) in the real step: the simulated game arrives at night (local time 22, sky
    12) and its screenshots carry the simulated sky's brightness in their top rows."""
    def test_setlocaltime_makes_daylight_before_the_spawn(self):
        obs = self.check(("PASS", "PASS"), plan={"time_of_day": 12})
        light = obs["light"]
        self.assertEqual(light["before"], {"shot": "arrival.png", "sky": 12.0})
        self.assertEqual([(x["cmd"], x["sky"], x["done"]) for x in light["tries"]], [("SetLocalTime 12", 110.0, True)])
        at = self.typed.index("SetLocalTime 12")
        self.assertLess(self.typed.index("coc QASmoke"), at)
        self.assertLess(at, self.typed.index("player.placeatme 0000CF96 1"))

    def test_the_ladder_goes_on_until_the_sky_reads_as_asked(self):
        v, obs, _ = self.run_step(plan={"time_of_day": 12}, world={"time_works": ["cgf"]})
        self.assertEqual(v[:2], ("PASS", "PASS"), v[2])
        self.assertEqual([(x["method"], x["done"]) for x in obs["light"]["tries"]],
                         [("slt", False), ("slt_galaxy", False), ("cgf", True)])
        self.assertIn('cgf "Game.SetLocalTime" 12', self.typed)        # typed with its quotes
        self.assertIn("SetLocalTime 12 1", self.typed)
        self.assertIn("after SetLocalTime 12; SetLocalTime 12 1; cgf", v[2])

    def test_no_effect_is_marked_night(self):
        v, obs, _ = self.run_step(plan={"time_of_day": 12, "need_daylight": True}, world={"time_works": []})
        self.assertEqual(v[:2], ("INCONCLUSIVE", "NIGHT"), v[2])
        self.assertIn("sky 12.0 -> 12.0", v[2])
        self.assertIn("no effect: night", v[2])
        self.assertEqual(len(obs["light"]["tries"]), 3)

    def test_weather_first_then_the_time(self):
        v, obs, _ = self.run_step(plan={"weather": "0000015e", "weather_lock": True, "time_of_day": 9.5,
                                        "time_methods": ["slt"]}, world={"weather_sky": {"0000015E": 70}})
        self.assertEqual([x["cmd"] for x in obs["light"]["tries"]], ["fw 0000015E 1", "SetLocalTime 9.5"])
        self.assertLess(self.typed.index("fw 0000015E 1"), self.typed.index("SetLocalTime 9.5"))
        self.assertEqual(obs["light"]["tries"][0]["sky"], 70.0)
        self.assertIn("; daylight", v[2])

    def test_terrain_sets_the_time_after_the_arrival_before_the_probes(self):
        t = tq.with_light({"id": "0000_terrain_QASmoke", "kind": "terrain", "cell": "", "ref": "QASmoke", "model": "",
                           "world_coc": "QASmoke", "travel": "", "drop_z": 5.0, "settle_ms": 1,
                           "points": [{"label": "p0", "x": 1.0, "y": 1.0, "expect": 5.0}], "beyond": {"x": 3.0, "y": 1.0}},
                          {"time_of_day": 12, "need_daylight": True}, {})
        v, obs, _ = self.run_step(test=t)
        self.assertEqual(obs["light"]["before"]["shot"], "spawn.png")
        self.assertEqual(obs["light"]["tries"][0]["sky"], 110.0)
        at = self.typed.index("SetLocalTime 12")
        self.assertLess(self.typed.index("coc QASmoke"), at)
        self.assertLess(at, min(k for k, c in enumerate(self.typed) if c.startswith("player.setpos")))
        self.assertEqual(v[0], "PASS", v[2])                  # the simulated player stays at the drop height 5 = expect
        self.assertIn("[light: local hour 12: sky 12.0 -> 110.0 after SetLocalTime 12; daylight after SetLocalTime 12; "
                      "probes: 1 measured, corner median 110.0 -> daylight => daylight]", v[2])
        self.assertEqual((obs["points"][0]["corners"], obs["points"][0]["repin"]), (110.0, True))

    def terrain(self, n=3, **light):
        pts = [{"label": f"p{k}", "x": 1.0 + k, "y": 1.0, "expect": 5.0} for k in range(n)]
        return tq.with_light({"id": "0000_terrain_QASmoke", "kind": "terrain", "cell": "", "ref": "QASmoke",
                              "model": "", "world_coc": "QASmoke", "travel": "", "drop_z": 8.0, "settle_ms": 1,
                              "points": pts, "beyond": {"x": 9.0, "y": 1.0}}, dict({"time_of_day": 12}, **light), {})

    def test_an_arrival_already_in_daylight_does_not_test_the_commands(self):
        # every staged exp2t plan of the first version of this branch arrived where the sky already read daylight
        v, obs, _ = self.run_step(test=self.terrain(n=1), world={"local_time": 12.0, "land_z": 5.0})
        self.assertEqual(v[0], "PASS", v[2])
        self.assertEqual(obs["light"]["before"]["sky"], 110.0)
        self.assertEqual([x["cmd"] for x in obs["light"]["tries"]], ["SetLocalTime 12"])
        self.assertIn("sky 110.0 -> 110.0 after SetLocalTime 12; already daylight at the arrival: the time commands "
                      "were not tested", v[2])
        self.assertEqual(tq.light_of(self.terrain(n=1), obs)["tested"], False)

    def test_a_refused_command_is_read_from_the_console(self):
        v, obs, _ = self.run_step(test=self.terrain(n=1), world={"slt_error": True, "time_works": ["cgf"],
                                                                 "land_z": 5.0})
        self.assertEqual(v[0], "PASS", v[2])
        tries = obs["light"]["tries"]
        self.assertEqual([(x["method"], x["done"]) for x in tries], [("slt", False), ("slt_galaxy", False),
                                                                     ("cgf", True)])
        self.assertIn("SetLocalTime only works on a planet.", tries[0]["ocr"])
        self.assertTrue(all(x["console"] for x in tries))
        self.assertIn("(console: SetLocalTime 12: SetLocalTime only works on a planet; SetLocalTime 12 1: SetLocalTime "
                      "only works on a planet)", v[2])
        self.assertIn('daylight after cgf "Game.SetLocalTime" 12', v[2])
        self.assertEqual(obs["light"]["repin"], 'cgf "Game.SetLocalTime" 12')   # cgf is what is typed again
        self.assertEqual(self.typed.count('cgf "Game.SetLocalTime" 12'), 2)    # the ladder and the one probe

    def test_a_slow_sky_is_credited_to_the_command_that_changed_it(self):
        v, obs, _ = self.run_step(test=self.terrain(n=1), world={"time_lag_shots": 1, "land_z": 5.0})
        self.assertEqual(v[0], "PASS", v[2])
        (x,) = obs["light"]["tries"]                                            # the ladder stopped at slt
        self.assertEqual((x["sky"], x["sky_late"], x["done"]), (12.0, 110.0, True))
        self.assertNotIn("SetLocalTime 12 1", self.typed)
        self.assertIn("daylight after SetLocalTime 12 (on its second shot)", v[2])

    def test_the_time_is_set_again_before_every_probe(self):
        # game time runs between console sessions (drift_per_open 3 h): without the repin the third probe is at night
        v, obs, _ = self.run_step(test=self.terrain(), world={"drift_per_open": 3.0, "land_z": 5.0})
        self.assertEqual(v[0], "PASS", v[2])
        self.assertEqual([p["corners"] for p in obs["points"]], [110.0, 110.0, 110.0])
        sets = [k for k, c in enumerate(self.typed) if c.startswith("player.setpos x")]
        for k in sets[:3]:                                                      # the probes; not the beyond drop
            self.assertEqual(self.typed[k - 1], "SetLocalTime 12")
        v, obs, _ = self.run_step(test=self.terrain(time_repin=False), world={"drift_per_open": 3.0, "land_z": 5.0})
        self.assertEqual([p["corners"] for p in obs["points"]], [110.0, 110.0, 12.0])
        self.assertEqual(self.typed.count("SetLocalTime 12"), 1)
        self.assertIn("night at p2", v[2])
        self.assertIn("=> daylight", v[2])                                      # the median: two of three


BORDER = ['GetINI "bBorderRegionsEnabled:General"', 'GetINI "fPlayableAreaX:General"',
          'GetINI "uPlayableSpaceOverlayCellBuffer:Planet"', 'SetINI "bBorderRegionsEnabled:General" 0',
          'GetINI "bBorderRegionsEnabled:General"']


@unittest.skipUnless(ENABLED, "opt-in: FO4SF_QSTEP_SANDBOX=1 on Windows")
class QstepConsoleSandboxTests(SandboxStep, unittest.TestCase):
    """console_pre / console_post (console_plan.py) in the real step, against the simulated INI settings; its OCR reads
    l for I ("GetlNl", "lNlSetting", "EnabIed") and "> >" for ">>"."""
    def terrain(self, **extra):
        return tq.with_extras({"id": "0000_terrain_QASmoke", "kind": "terrain", "cell": "", "ref": "QASmoke",
                               "model": "", "world_coc": "QASmoke", "travel": "", "drop_z": 5.0, "settle_ms": 1,
                               "points": [{"label": "p0", "x": 1.0, "y": 1.0, "expect": 5.0}],
                               "beyond": {"x": 3.0, "y": 1.0}}, extra, {})

    def test_border_commands_before_the_travel_and_a_read_after_the_arrival(self):
        t = self.terrain(console_pre=BORDER, console_post=['GetINI "bBorderRegionsEnabled:General"'], time_of_day=12)
        v, obs, _ = self.run_step(test=t)
        coc = self.typed.index("coc QASmoke")
        self.assertEqual(self.typed[:coc], BORDER)                    # after the save, before the travel, in order
        post = self.typed.index('GetINI "bBorderRegionsEnabled:General"', coc)
        self.assertLess(self.typed.index("SetLocalTime 12"), post)
        self.assertLess(post, min(k for k, c in enumerate(self.typed) if c.startswith("player.setpos")))
        self.assertEqual([(c["phase"], c["cmd"]) for c in obs["console"]],
                         [("pre", c) for c in BORDER] + [("post", 'GetINI "bBorderRegionsEnabled:General"')])
        self.assertTrue(all(c["shot"] for c in obs["console"]))
        self.assertEqual(v[0], "PASS", v[2])
        self.assertIn("[console pre: GetINI bBorderRegionsEnabled:General = 1; GetINI fPlayableAreaX:General = "
                      "3200.0000; GetINI uPlayableSpaceOverlayCellBuffer:Planet = 2; SetINI "
                      "bBorderRegionsEnabled:General 0 (no reply); GetINI bBorderRegionsEnabled:General = 0] "
                      "[console post: GetINI bBorderRegionsEnabled:General = 0]", v[2])

    def test_npc_nav_types_its_console_commands_too(self):
        v, obs, _ = self.run_step(plan={"console_pre": ['GetINI "bNoSuch:General"', 'SetINI "bNoSuch:General" 1'],
                                        "console_post": ['GetINI "fPlayableAreaX:General"']})
        self.assertEqual(v[:2], ("PASS", "PASS"), v[2])
        coc = self.typed.index("coc QASmoke")
        self.assertEqual(self.typed[:coc], ['GetINI "bNoSuch:General"', 'SetINI "bNoSuch:General" 1'])
        self.assertLess(self.typed.index('GetINI "fPlayableAreaX:General"'),
                        self.typed.index("player.placeatme 0000CF96 1"))
        self.assertIn("[console pre: GetINI bNoSuch:General (not found: INISetting >> NOT FOUND); SetINI bNoSuch:General "
                      '1 (error: INI setting "bNoSuch:General" does not exist)]', v[2])

    def test_a_command_off_the_whitelist_types_nothing(self):
        for bad in (["qqq"], ["player.additem 0000000F 100"], ['GetINI "bBorderRegionsEnabled:General"', "tgm"],
                    ['SetINI "bBorderRegionsEnabled:General" 0|key:enter|type:tgm']):
            out, _, _ = self.run_step(test=dict(self.terrain(), console_pre=bad), code=4)
            self.assertIn("bad console_pre", out)
            self.assertEqual(self.typed, [], bad)
        out, _, _ = self.run_step(test=dict(self.terrain(), console_post=["coc Elsewhere"]), code=4)
        self.assertEqual(self.typed, [])


# door_trip (docs/slice/redrocket-door.md): the Red Rocket cave link as staged, in the world's own frame / the interior
# frame; the simulated overlay is merged at OFF (exp2d's measured offset, rounded)
OFF = [-1200.0, -2700.0, 0.0]
DOOR = {"label": "rr_cave", "travel": "coc FO4CW_RedRocketSpawn", "spawn_local": [-989.0286, 1147.2, 105.2609],
        "outside": {"start": [-995.53, 1104.143, 99.771], "door": [-994.948, 1109.49, 98.684],
                    "arrival": [-995.53, 1104.143, 99.771], "near": [-995.03, 1108.5, 99.0], "ground": 99.6},
        "inside": {"cell": "FO4Port_RedRocket01", "start": [0.049, -6.622, -0.006], "door": [-1.659, 2.416, 0.0],
                   "arrival": [0.049, -6.622, -0.006], "near": [-1.47, 1.43, 0.0], "floor": 0.0},
        "save": "fo4sf_slice_rrdoor", "settle_ms": 0, "walk_ms": 4000, "walk_step_ms": 500, "near_wait_ms": 3000}


def plus(p, o=OFF):
    return [p[k] + o[k] for k in range(3)]


def ps(x):
    """A coordinate as qstep.ps1 types it into player.setpos (F: '0.###')."""
    return f"{round(x, 3):.3f}".rstrip("0").rstrip(".")


def door_world(unmerged=False, works=True, **extra):
    """The simulated world: the coc arrival merged at OFF, an automatic door outside (in the coc cell) and one inside."""
    o, i = DOOR["outside"], DOOR["inside"]
    w = {"arrival": plus(DOOR["spawn_local"]), "player": [0, 0, 0],
         "doors": [{"name": "ext", "cell": "FO4CW_RedRocketSpawn", "pos": plus(o["door"]), "auto": True, "works": works,
                    "dest_cell": i["cell"], "dest_pos": i["arrival"]},
                   {"name": "int", "cell": i["cell"], "pos": i["door"], "auto": True, "works": True,
                    "dest_cell": "FO4CW_RedRocketSpawn", "dest_pos": o["arrival"] if unmerged else plus(o["arrival"])}]}
    w.update(extra)
    return w


@unittest.skipUnless(ENABLED, "opt-in: FO4SF_QSTEP_SANDBOX=1 on Windows")
class QstepDoorSandboxTests(SandboxStep, unittest.TestCase):
    """door_trip in the real step against simulated load doors (automatic doors that load within 3 m, a loading screen
    that hides the HUD, GetInCell, save files in a temporary Saves folder)."""
    def trip(self, world, plan=None, code=0):
        return self.run_step(test=tq.door_test(0, dict(DOOR, **(plan or {}))), world=world, code=code)

    def test_through_the_door_and_back_then_save_and_load(self):
        v, obs, _ = self.trip(door_world())
        self.assertEqual(v[:2], ("PASS", "PASS"), v[2])
        self.assertEqual(self.state["loads"], ["ext", "int"])
        self.assertEqual([(x["name"], x["trigger"], x["incell"]) for x in obs["legs"]], [("in", "walk", 1), ("out", "walk", 0)])
        self.assertEqual([round(c, 1) for c in obs["offset"]], [-1200.0, -2700.0, 0.0])
        self.assertTrue(obs["save"]["found"])
        self.assertEqual(obs["save"]["file"], "fo4sf_slice_rrdoor.sfs")
        self.assertTrue(obs["reload"]["load_seen"])
        self.assertEqual(obs["reload"]["incell"], 0)
        self.assertLess(self.typed.index("save fo4sf_slice_rrdoor"), self.typed.index("load fo4sf_slice_rrdoor"))
        self.assertIn("player.GetInCell FO4Port_RedRocket01", self.typed)
        self.assertIn("out: arrived 0.0 m from the merged exterior arrival point (GetInCell FO4Port_RedRocket01 0)", v[2])
        # every walk step was followed by a position read; the load was seen by the HUD check
        self.assertEqual([x["load_by"] for x in obs["legs"]], ["hud", "hud"])
        self.assertTrue(all(c["tag"] == "walk" for x in obs["legs"] for c in x["checks"]))
        # before the load the player was moved back to the coc arrival, about 44 m from the saved spot
        away = [float(v) for v in obs["reload"]["away_read"].split()]
        self.assertAlmostEqual(away[1], plus(DOOR["spawn_local"])[1], delta=0.1)
        back = len(self.typed) - 1 - self.typed[::-1].index(f"player.setpos y {ps(plus(DOOR['spawn_local'])[1])}")
        self.assertLess(self.typed.index("save fo4sf_slice_rrdoor"), back)
        self.assertLess(back, self.typed.index("load fo4sf_slice_rrdoor"))
        self.assertIn("loading screen seen", v[2])

    def test_a_load_no_hud_check_saw_is_found_by_the_position(self):
        # QA on PR #78: with an instant loading screen the HUD checks never see the load; the old step walked on in the
        # new cell and teleported to the other side's last-try spot there (6 loads instead of 2, the void inside)
        v, obs, _ = self.trip(door_world(load_secs=0))
        self.assertEqual(v[:2], ("PASS", "PASS"), v[2])
        self.assertEqual(self.state["loads"], ["ext", "int"])
        self.assertEqual([(x["trigger"], x["load_by"], x["load_seen"]) for x in obs["legs"]],
                         [("walk", "position", False), ("walk", "position", False)])
        self.assertNotIn("near_m", obs["legs"][0])                     # no last-try teleport after the load
        near_x = f"player.setpos x {ps(plus(DOOR['outside']['near'])[0])}"
        self.assertNotIn(near_x, self.typed)
        self.assertFalse(obs["reload"]["load_seen"])                  # the reload is shown by the position alone
        self.assertIn("no loading screen seen, moved", v[2])

    def test_no_reach_without_a_last_try(self):
        plan = {"outside": dict(DOOR["outside"], near=None), "inside": dict(DOOR["inside"], near=None)}
        v, obs, _ = self.trip(door_world(walk_blocked=True), plan=plan)
        self.assertEqual(v[:2], ("INCONCLUSIVE", "NOREACH"), v[2])
        leg = obs["legs"][0]
        self.assertEqual(leg["walk_stopped"], "no progress in two steps")
        self.assertEqual(len(leg["checks"]), 2)                         # stopped after two steps without progress

    def test_the_door_getpos_is_read_after_the_arrival(self):
        o = DOOR["outside"]
        w = door_world()
        w["doors"][0].update(ref="05000800", ref_pos=o["door"])          # reads its unmerged local position
        v, obs, _ = self.trip(w, plan={"outside": dict(o, ref="05000800")})
        self.assertEqual(v[:2], ("PASS", "PASS"), v[2])
        self.assertEqual(obs["door_read"], "-994.95 1109.49 98.68")        # the fake readpos -Ref (prid + getpos)
        self.assertIn("getpos of door 05000800 read -994.95 1109.49 98.68: its unmerged local position", v[2])

    def test_a_return_without_the_merge_offset_is_unmerged(self):
        v, obs, _ = self.trip(door_world(unmerged=True))
        self.assertEqual(v[:2], ("FAIL", "UNMERGED"), v[2])
        self.assertNotIn("save fo4sf_slice_rrdoor", self.typed)       # the step stops at the leg that failed

    def test_a_door_that_does_nothing_is_noload(self):
        v, obs, _ = self.trip(door_world(works=False))
        self.assertEqual(v[:2], ("FAIL", "NOLOAD"), v[2])
        leg = obs["legs"][0]
        self.assertEqual((leg["load_seen"], leg["trigger"]), (False, ""))
        self.assertAlmostEqual(leg["near_m"], 1.0, delta=0.05)
        self.assertEqual(len(leg["checks"]), 8)                         # 4 s in 500 ms steps, each read
        self.assertEqual(leg["incell"], 0)
        self.assertEqual(len(obs["legs"]), 1)
        self.assertNotIn("save fo4sf_slice_rrdoor", self.typed)

    def test_a_blocked_walk_loads_from_the_near_point(self):
        # the door works when stood at, but the walk never reached it: not the walk-in the slice asks for
        v, obs, _ = self.trip(door_world(walk_blocked=True))
        self.assertEqual(v[:2], ("INCONCLUSIVE", "NEARONLY"), v[2])
        self.assertEqual([x["trigger"] for x in obs["legs"]], ["near", "near"])
        self.assertEqual([x["walk_stopped"] for x in obs["legs"]], ["no progress in two steps"] * 2)

    def test_a_load_that_puts_the_player_elsewhere_is_reload(self):
        v, obs, _ = self.trip(door_world(reload_shift=[0.0, 7.5, 0.0]))
        self.assertEqual(v[:2], ("FAIL", "RELOAD"), v[2])

    def test_no_save_file_is_inconclusive_and_nothing_is_loaded(self):
        v, obs, _ = self.trip(door_world(save_fails=True))
        self.assertEqual(v[:2], ("INCONCLUSIVE", "NOSAVE"), v[2])
        self.assertNotIn("load fo4sf_slice_rrdoor", self.typed)

    def test_a_bad_spec_types_nothing(self):
        for bad in ({"save": "fo4sf_test_1234"}, {"inside": dict(DOOR["inside"], cell="FO4Port RedRocket01")},
                    {"travel": "player.moveto 02000800"}):
            t = dict(tq.door_test(0, DOOR), **bad)
            out, _, _ = self.run_step(test=t, world=door_world(), code=4)
            self.assertEqual(self.typed, [], bad)


# walk (docs/terrain/walk-redrocket-sanctuary.md): a 44 m route in the overlay's own frame over a gentle slope, across
# the local cell borders x = -1000 and y = 1200 and a raised "bridge" deck, in a world merged at OFF (core64c's offset)
WALK_WPS = [(-995.0, 1190.0), (-1005.0, 1190.0), (-1015.0, 1190.0), (-1015.0, 1198.0), (-1015.0, 1206.0),
            (-1015.0, 1214.0)]
DECK = (-1017.0, 1195.0, -1013.0, 1209.0, 81.2)          # local box and the deck's z (about 1.5 m over the slope)
BRIDGE = {"src": "01F970:Fallout4.esm", "edid": "FO4Core_northbridge"}


def slope_z(x):
    return 100.0 + 0.02 * x                               # local frame


def on_deck(x, y):
    return DECK[0] <= x <= DECK[2] and DECK[1] <= y <= DECK[3]


def walk_ground(d):
    """A walk_ground.json for the sandbox route: the slope as the BTD window, the deck as an object surface."""
    x0, y0, step = -1035.0, 1170.0, 0.78125
    rows = [[round(slope_z(x0 + c * step), 4) for c in range(80)] for _r in range(80)]
    sx0, sy0, ss = -1035.0, 1170.0, 0.5
    nodes = {}
    for i in range(int(math.ceil((DECK[0] - sx0) / ss)), int(math.floor((DECK[2] - sx0) / ss)) + 1):
        for j in range(int(math.ceil((DECK[1] - sy0) / ss)), int(math.floor((DECK[3] - sy0) / ss)) + 1):
            nodes[f"{i},{j}"] = [[DECK[4], 0]]
    data = {"version": 1, "frame": "sandbox", "terrain": {"x0": x0, "y0": y0, "step": step, "rows": rows},
            "surfaces": {"x0": sx0, "y0": sy0, "step": ss, "nx": 140, "ny": 140, "nodes": nodes}, "owners": [BRIDGE],
            "corridor_m": 12.0, "path": [list(p) for p in WALK_WPS]}
    p = os.path.join(d, "walk_ground.json")
    with open(p, "w") as f:
        json.dump(data, f)
    return tq.sha256(p)


def walk_entry(d, reverse=False, **extra):
    """A plan.json entry as scripts/terrain/walk_route.py writes it, for the sandbox route (reverse: from the goal back
    to the start after a setup teleport)."""
    gsha = walk_ground(d)
    wps = [[x, y, DECK[4] if on_deck(x, y) else slope_z(x), 3.0 if k == len(WALK_WPS) - 1 else 2.5]
           for k, (x, y) in enumerate(WALK_WPS)]
    cross = [{"s": 5.0, "from": [-10, 11], "to": [-11, 11], "axis": "x", "at": -1000.0},
             {"s": 30.0, "from": [-11, 11], "to": [-11, 12], "axis": "y", "at": 1200.0}]
    span = [25.0, 39.0]
    if reverse:
        wps = [w[:3] + [2.5] for w in wps[::-1]]
        wps[-1][3] = 3.0
        cross = [{"s": 44.0 - c["s"], "from": c["to"], "to": c["from"], "axis": c["axis"], "at": c["at"]}
                 for c in cross[::-1]]
        span = [44.0 - span[1], 44.0 - span[0]]
    e = {"label": "sandbox_walk_back" if reverse else "sandbox_walk", "travel": "coc FO4Core_RedRocketSpawn",
         "spawn_local": [-995.0, 1190.0, slope_z(-995.0)], "setup": reverse, "start": wps[0][:3], "waypoints": wps,
         "goal_radius": 3.0, "ground": "walk_ground.json", "ground_sha256": gsha,
         "bridge": dict(BRIDGE, span=span, min_reads=2), "crossings": cross, "length_m": 44.0, "max_legs": 20,
         "speed": 3.0, "shot_every": 2, "settle_ms": 0, "drop": 1.0}
    e.update(extra)
    return e


def game(p):
    return [p[0] + OFF[0], p[1] + OFF[1], p[2] + OFF[2]]


def box(b):
    """A local (x0, y0, x1, y1[, ...]) box in the game's frame."""
    return [b[0] + OFF[0], b[1] + OFF[1], b[2] + OFF[0], b[3] + OFF[1]] + list(b[4:])


def walk_world(**extra):
    g = {"z0": 100.0 - 0.02 * OFF[0], "sx": 0.02, "sy": 0.0, "decks": [box(DECK)]}
    g.update(extra.pop("ground", {}))
    w = {"arrival": game([-995.0, 1190.0, slope_z(-995.0)]), "player": [0, 0, 0], "walk_speed": 3.0, "ground": g}
    w.update(extra)
    return w


@unittest.skipUnless(ENABLED, "opt-in: FO4SF_QSTEP_SANDBOX=1 on Windows")
class QstepWalkSandboxTests(SandboxStep, unittest.TestCase):
    """walk in the real step against a simulated ground: the player walks only with W and setangle; holes, walls and a
    boundary box on the route; an OCR misread."""
    def walk(self, world=None, reverse=False, code=0, **extra):
        d = tempfile.mkdtemp(prefix="walk_plan_")
        t = tq.walk_test(0, walk_entry(d, reverse, **extra), d)
        return self.run_step(test=t, world=walk_world(**(world or {})), code=code)

    def walk_cmds(self):
        """Every console line typed after the walk's first ClearConsole."""
        return self.typed[self.typed.index("ClearConsole"):]

    def test_the_walk_passes_with_real_input_only(self):
        v, obs, _ = self.walk(world={"heading_bias": 6.0})
        self.assertEqual(v[:2], ("PASS", "PASS"), v[2])
        self.assertEqual(obs["walk_stopped"], "goal")
        self.assertTrue(all(walk_eval.WALK_CMD.fullmatch(c) for c in self.walk_cmds()), self.walk_cmds())
        self.assertFalse([c for c in self.typed if "setpos" in c or "moveto" in c])     # no teleport at all
        self.assertIn("2 reads on the FO4Core_northbridge deck", v[2])
        self.assertIn("cells (-22,-16) -> (-23,-16) -> (-23,-15)", v[2])
        self.assertTrue(self.state["holds"])
        self.assertTrue(all(x["shot"] for x in obs["legs"][::2] if x["action"] == "aim"))

    def test_a_straight_run_walks_past_a_waypoint_it_need_not_read(self):
        wps = walk_entry(tempfile.mkdtemp())["waypoints"]
        wps = [w + [0 if k == 1 else 1] for k, w in enumerate(wps)]
        v, obs, _ = self.walk(waypoints=wps, max_leg_m=25.0)
        self.assertEqual(v[:2], ("PASS", "PASS"), v[2])
        self.assertEqual(obs["legs"][0]["hold_ms"], int(20.0 / 3.0 * 1000))   # (-995, 1190) straight to (-1015, 1190)
        self.assertEqual(len(obs["legs"]), 5)

    def test_the_reverse_walk_starts_after_one_setup_teleport(self):
        v, obs, _ = self.walk(reverse=True)
        self.assertEqual(v[:2], ("PASS", "PASS"), v[2])
        self.assertTrue(obs["setup"]["settled"])
        first = self.typed.index("ClearConsole")
        self.assertTrue(all("setpos" not in c for c in self.typed[first:]))
        self.assertEqual(sum(1 for c in self.typed[:first] if c.startswith("player.setpos x")), 1)
        self.assertIn("setup teleport landed", v[2])

    def test_a_hole_in_the_ground_is_a_fall(self):
        v, obs, _ = self.walk(world={"ground": {"holes": [box((-1011.0, 1187.0, -1009.0, 1193.0))]}})
        self.assertEqual(v[:2], ("FAIL", "FELL"), v[2])
        self.assertEqual(obs["walk_stopped"], "fell")

    def test_a_boundary_popup_stops_the_walk(self):
        v, obs, _ = self.walk(world={"ground": {"boundary": [box((-1012.0, 1185.0, -1010.0, 1195.0))],
                                                "boundary_shift": [9000.0, 0.0, 0.0]}})
        self.assertEqual(v[:2], ("FAIL", "BOUNDARY"), v[2])
        self.assertEqual(obs["walk_stopped"], "boundary")
        self.assertIn("BOUNDARY REACHED", obs["legs"][-1]["popup"])
        self.assertTrue(obs["legs"][-1]["shot"])

    def test_a_wall_across_the_route_is_stuck(self):
        v, obs, _ = self.walk(world={"ground": {"walls": [box((-1025.0, 1193.0, -1005.0, 1194.0))]}})
        self.assertEqual(v[:2], ("FAIL", "STUCK"), v[2])
        self.assertTrue(any(x.get("detour") for x in obs["legs"]))

    def test_a_misread_is_read_again_and_the_walk_goes_on(self):
        v, obs, _ = self.walk(world={"getpos_misread": [3]})
        self.assertEqual(v[:2], ("PASS", "PASS"), v[2])
        again = [x for x in obs["legs"] if x.get("reread")]
        self.assertEqual(len(again), 1)
        self.assertNotEqual(again[0]["read"], again[0]["used"])

    def test_a_bad_spec_types_nothing(self):
        for bad in ({"travel": "player.moveto 02000800"}, {"waypoints": [[1.0, 2.0, 3.0]]}):
            d = tempfile.mkdtemp(prefix="walk_plan_")
            t = dict(tq.walk_test(0, walk_entry(d), d), **bad)
            self.run_step(test=t, world=walk_world(), code=4)
            self.assertEqual(self.typed, [], bad)


if __name__ == "__main__":
    unittest.main()
