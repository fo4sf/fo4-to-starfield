"""End-to-end run of qstep.ps1's npc_nav step against a simulated console (tests/qstep_sandbox), judged by testqueue.
Opt-in (each scenario starts ~60 PowerShell processes, about 25 s): set FO4SF_QSTEP_SANDBOX=1 on Windows.

Safety: the real qstep.ps1, parse_npc.py and parse_getpos.py are copied into a temporary folder next to the sandbox
fakes, so every helper the step calls (input.ps1, console_open.ps1, readpos.ps1, shot*.ps1, ocr.ps1) is a fake that
never sends input; nothing in scripts/game is run except the copied step itself."""
import json
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
        for f in ("qstep.ps1", "parse_npc.py", "parse_getpos.py", "sky_light.py"):
            shutil.copy(os.path.join(GAME, f), step_dir)
        state = os.path.join(d, "state.json")
        with open(state, "w") as f:
            json.dump(dict(WORLD, **(world or {})), f)
        t = test or tq.npc_test(0, dict(N0, **(plan or {})))
        spec, out = os.path.join(d, "spec.json"), os.path.join(d, "out")
        with open(spec, "w") as f:
            json.dump(t, f)
        env = dict(os.environ, FAKE_STATE=state, FO4SF_PYTHON=sys.executable, FO4SF_NO_FOCUS_STEAL="1", LEGACY="1")
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


if __name__ == "__main__":
    unittest.main()
