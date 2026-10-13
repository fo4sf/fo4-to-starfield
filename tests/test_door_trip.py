"""door_trip (docs/slice/redrocket-door.md): planning, the judge on synthetic observations, the step timeout, the
runner features, GetInCell parsing and the experiment plugin order (exp_install.py order). Synthetic data only."""
import json
import os
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import exp_install  # noqa: E402
import parse_npc  # noqa: E402
import runner_features  # noqa: E402
import testqueue as tq  # noqa: E402

OFF = [-1200.0, -2699.8, 0.01]
PLAN = {"label": "rr_cave", "travel": "coc FO4CW_RedRocketSpawn", "spawn_local": [-989.0286, 1147.2, 105.2609],
        "outside": {"start": [-995.53, 1104.143, 99.771], "door": [-994.948, 1109.49, 98.684],
                    "arrival": [-995.53, 1104.143, 99.771], "near": [-995.03, 1108.5, 99.0], "ground": 99.6},
        "inside": {"cell": "FO4Port_RedRocket01", "start": [0.049, -6.622, -0.006], "door": [-1.659, 2.416, 0.0],
                   "arrival": [0.049, -6.622, -0.006], "near": [-1.47, 1.43, 0.0], "floor": 0.0},
        "save": "fo4sf_slice_rrdoor"}


def fmt(p):
    return " ".join(f"{v:.2f}" for v in p)


def plus(p, o=OFF):
    return [p[k] + o[k] for k in range(3)]


def good_obs():
    o, i = PLAN["outside"], PLAN["inside"]
    out_at = plus(o["arrival"])
    return {"offset": OFF, "spawn_read": fmt(plus(PLAN["spawn_local"])), "spawn_settled": True,
            "legs": [{"name": "in", "start_read": fmt(plus(o["start"])), "trigger": "walk", "walked_ms": 1000,
                      "load_seen": True, "load_s": 12, "arrival_read": fmt(i["arrival"]), "arrival_settled": True,
                      "incell": 1, "shot": "in_arrival.png"},
                     {"name": "out", "start_read": fmt(i["start"]), "trigger": "walk", "walked_ms": 2500,
                      "load_seen": True, "load_s": 20, "arrival_read": fmt(out_at), "arrival_settled": True,
                      "incell": 0, "shot": "out_arrival.png"}],
            "save": {"name": PLAN["save"], "found": True, "file": "fo4sf_slice_rrdoor.sfs", "size": 1234},
            "reload": {"load_seen": True, "hud_back": True, "load_s": 25, "read": fmt(out_at), "settled": True,
                       "incell": 0, "shot": "reload.png"}}


class DoorPlanTests(unittest.TestCase):
    def test_a_test_from_the_plan(self):
        t = tq.door_test(0, PLAN)
        self.assertEqual((t["id"], t["kind"], t["cell"]), ("0000_door_trip_rr_cave", "door_trip", ""))
        self.assertAlmostEqual(t["heading_out"], 6.2, places=1)     # north, slightly east, towards the cave mouth
        self.assertAlmostEqual(t["heading_in"], 349.3, places=1)
        self.assertEqual(t["inside"]["cell"], "FO4Port_RedRocket01")
        self.assertEqual(t["outside"]["ground"], 99.6)
        self.assertEqual((t["radius"], t["walk_ms"], t["walk_step_ms"]), (4.0, 8000, 500))
        self.assertEqual((t["moved_m"], t["activate_m"]), (30.0, 3.0))
        self.assertNotIn("ref", t["outside"])
        self.assertEqual(tq.door_test(0, dict(PLAN, outside=dict(PLAN["outside"], ref="05000800")))["outside"]["ref"],
                         "05000800")
        self.assertEqual(runner_features.needs([t]), ["door_check", "door_trip"])
        old = {k: v for k, v in t.items() if k not in ("moved_m", "activate_m")}      # a test planned at bf7c853
        self.assertEqual(runner_features.needs([old]), ["door_trip"])

    def test_what_is_typed_is_validated(self):
        bad = [{"travel": "coc FO4CW_RedRocketSpawn; tgm"}, {"travel": "player.moveto 02000800"},
               {"save": "fo4sf_test_1a2b3c4d"}, {"save": "slice door"}, {"save": "myplaythrough"},
               {"inside": dict(PLAN["inside"], cell="FO4Port RedRocket01")},
               {"inside": dict(PLAN["inside"], cell="")}, {"outside": dict(PLAN["outside"], door=[1, 2])},
               {"outside": dict(PLAN["outside"], extra=1)}, {"walk_ms": 10 ** 6}, {"unknown_key": 1},
               {"outside": dict(PLAN["outside"], start=[float("nan"), 0, 0])},
               {"outside": dict(PLAN["outside"], ref="0500080")}, {"outside": dict(PLAN["outside"], ref="05000800;tgm")},
               {"inside": dict(PLAN["inside"], ref="05000801")}, {"activate_m": 50}, {"moved_m": 1}]
        for b in bad:
            with self.assertRaises(SystemExit, msg=b):
                tq.door_test(0, dict(PLAN, **b))

    def test_plan_door_writes_the_queue_with_its_needs(self):
        d = tempfile.mkdtemp()
        staging, exp, out = (os.path.join(d, x) for x in ("staging", "exp", "queue"))
        os.makedirs(staging), os.makedirs(exp)
        put(os.path.join(staging, "FO4Port.esm"), b"TES4")
        with open(os.path.join(exp, "plan.json"), "w") as f:
            json.dump([PLAN], f)
        write_plugin(os.path.join(exp, "FO4TerrainExp2.esm"), ["Starfield.esm"])
        write_plugin(os.path.join(exp, "FO4TerrainExp2_Mars.esm"), ["Starfield.esm", "FO4TerrainExp2.esm"])
        write_plugin(os.path.join(exp, "FO4SliceRedRocket.esm"), ["Starfield.esm", "FO4TerrainExp2.esm", "FO4Port.esm"])
        plugins = "FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm,FO4SliceRedRocket.esm"
        tq.main(["plan-door", "--staging", staging, "--exp-dir", exp, "--out", out, "--plugins", plugins, "--fresh"])
        with open(os.path.join(out, "queue.json")) as f:
            q = json.load(f)
        self.assertEqual(q["needs"], ["door_check", "door_trip", "plugin_order"])
        self.assertTrue(q["tests"][0]["fresh"])
        pre = q["pre_launch"]
        self.assertEqual(pre[pre.index("--plugins") + 1], plugins)
        self.assertEqual(pre[pre.index("--needs") + 1], "door_check,door_trip,plugin_order")
        self.assertIn("--pack", pre)
        self.assertGreater(tq.step_timeout(q["tests"][0]), 2000)

    def test_plugin_order_is_needed_only_for_a_master_outside_the_install(self):
        d = tempfile.mkdtemp()
        write_plugin(os.path.join(d, "A.esm"), ["Starfield.esm"])
        write_plugin(os.path.join(d, "B.esm"), ["Starfield.esm", "A.esm", "SFBGS003.esm"])
        write_plugin(os.path.join(d, "C.esm"), ["Starfield.esm", "FO4Port.esm"])
        self.assertFalse(tq.plugin_order_needed(d, ["A.esm", "B.esm"]))
        self.assertTrue(tq.plugin_order_needed(d, ["B.esm", "A.esm"]))
        self.assertTrue(tq.plugin_order_needed(d, ["A.esm", "C.esm"]))
        self.assertFalse(tq.plugin_order_needed(d, ["missing.esm"]))


class DoorJudgeTests(unittest.TestCase):
    def judge(self, obs, plan=None):
        t = tq.door_test(0, dict(PLAN, **(plan or {})))
        return tq.judge_door(t, obs, lambda name: bool(name))

    def test_pass(self):
        v, cls, detail = self.judge(good_obs())
        self.assertEqual((v, cls), ("PASS", "PASS"), detail)
        self.assertIn("in: arrived 0.0 m from the interior arrival point (GetInCell FO4Port_RedRocket01 1), trigger walk", detail)
        self.assertIn("save fo4sf_slice_rrdoor written (1234 B); after the load 0.00 m from the saved spot", detail)

    def leg(self, obs, name, **kw):
        x = next(x for x in obs["legs"] if x["name"] == name)
        x.update(kw)
        return obs

    def test_each_way_to_fail_or_stay_open(self):
        o, i = PLAN["outside"], PLAN["inside"]
        far = fmt(plus(plus(o["start"]), [0, 0.5, 0]))           # still in front of the outside door, 4.9 m from it
        at_door = fmt(plus(o["near"]))                           # 1 m from the outside door (the last-try spot)
        cases = [
            (dict(good_obs(), offset=None), ("INCONCLUSIVE", "ANCHOR")),
            (self.leg(good_obs(), "in", start_read="fail"), ("INCONCLUSIVE", "START")),
            (self.leg(good_obs(), "in", start_read=fmt(plus(o["start"], [0, 8, 0]))), ("INCONCLUSIVE", "START")),
            (self.leg(good_obs(), "in", load_seen=False, arrival_read=at_door, trigger="", incell=0), ("FAIL", "NOLOAD")),
            (self.leg(good_obs(), "in", load_seen=False, arrival_read=at_door, trigger="", incell=None), ("FAIL", "NOLOAD")),
            # GetInCell says the far side while the position is at this side's door: never "the door does not work"
            (self.leg(good_obs(), "in", load_seen=False, arrival_read=at_door, trigger="", incell=1),
             ("INCONCLUSIVE", "CELLREAD")),
            # never within the door's range: the door was not tried
            (self.leg(good_obs(), "in", load_seen=False, arrival_read=far, trigger="", incell=0), ("INCONCLUSIVE", "NOREACH")),
            (self.leg(good_obs(), "in", load_seen=False, arrival_read=at_door, trigger="", incell=0, arrival_settled=False),
             ("INCONCLUSIVE", "UNREAD")),
            (self.leg(good_obs(), "in", load_seen=True, arrival_read=far), ("INCONCLUSIVE", "NOMOVE")),
            (self.leg(good_obs(), "in", arrival_read=None), ("INCONCLUSIVE", "UNREAD")),
            (self.leg(good_obs(), "in", shot=None), ("INCONCLUSIVE", "NOSHOT")),
            (self.leg(good_obs(), "in", incell=0), ("INCONCLUSIVE", "CELLREAD")),
            (self.leg(good_obs(), "in", arrival_read=fmt([40, 40, 0]), incell=1), ("FAIL", "ELSEWHERE")),
            (self.leg(good_obs(), "in", arrival_read=fmt([-500, 300, 20]), incell=0), ("FAIL", "WRONGCELL")),
            (self.leg(good_obs(), "in", arrival_read=fmt([-500, 300, 20]), incell=None), ("INCONCLUSIVE", "ELSEWHERE")),
            (self.leg(good_obs(), "in", arrival_settled=False), ("INCONCLUSIVE", "UNREAD")),
            (dict(good_obs(), legs=good_obs()["legs"][:1]), ("INCONCLUSIVE", "UNREAD")),
            (self.leg(good_obs(), "out", arrival_read=fmt(o["arrival"])), ("FAIL", "UNMERGED")),
            (self.leg(good_obs(), "out", arrival_read=fmt(plus(o["arrival"], [OFF[0] + 300, OFF[1] - 100, 0.3]))),
             ("FAIL", "REMERGED")),
            (self.leg(good_obs(), "out", arrival_read=fmt(plus(o["arrival"], [OFF[0], OFF[1], -40])),
                      arrival_settled=False), ("FAIL", "FELL")),
            (self.leg(good_obs(), "out", load_seen=False, arrival_read=fmt(i["near"]), incell=1), ("FAIL", "NOLOAD")),
            (self.leg(good_obs(), "out", load_seen=False, arrival_read=fmt(i["near"]), incell=0),
             ("INCONCLUSIVE", "CELLREAD")),
            (self.leg(good_obs(), "out", load_seen=False, arrival_read=fmt(i["start"]), incell=1),
             ("INCONCLUSIVE", "NOREACH")),
            (self.leg(good_obs(), "in", load_seen=False, load_by="position", arrival_read=fmt([30, 30, 0]), incell=0),
             ("FAIL", "WRONGCELL")),
            (self.leg(good_obs(), "out", arrival_read=fmt([30, 30, 0]), incell=1), ("FAIL", "WRONGCELL")),
            (dict(good_obs(), save={"found": False, "why": "no file"}), ("INCONCLUSIVE", "NOSAVE")),
            (dict(good_obs(), save=None), ("INCONCLUSIVE", "NOSAVE")),
            (dict(good_obs(), reload=dict(good_obs()["reload"], load_seen=False)), ("INCONCLUSIVE", "RELOAD_UNSEEN")),
            (dict(good_obs(), reload=dict(good_obs()["reload"], read="fail")), ("INCONCLUSIVE", "UNREAD")),
            (dict(good_obs(), reload=dict(good_obs()["reload"], read=fmt(plus(o["arrival"], [OFF[0], OFF[1] + 6, 0])))),
             ("FAIL", "RELOAD")),
            (dict(good_obs(), reload=dict(good_obs()["reload"], read=fmt(plus(o["arrival"], [OFF[0], OFF[1], -30])))),
             ("FAIL", "FELL")),
            (dict(good_obs(), reload=dict(good_obs()["reload"], settled=False)), ("INCONCLUSIVE", "UNREAD")),
            # GetInCell after the load contradicts the position on the terrain
            (dict(good_obs(), reload=dict(good_obs()["reload"], incell=1)), ("INCONCLUSIVE", "CELLREAD")),
        ]
        for obs, want in cases:
            v, cls, detail = self.judge(obs)
            self.assertEqual((v, cls), want, detail)

    def test_the_verifiers_cases_are_not_noload(self):
        # QA on PR #78 with the queue's own test and offset: (a) arrival 10 m below the outside near point, not settled,
        # GetInCell 1 (the door loaded, then the runner moved the player); (b) 5 m from the door, never within 3 m
        o = PLAN["outside"]
        a = self.leg(good_obs(), "in", load_seen=False, trigger="", arrival_settled=False, incell=1,
                     arrival_read=fmt(plus(o["near"], [OFF[0], OFF[1], OFF[2] - 10])))
        self.assertEqual(self.judge(a)[:2], ("INCONCLUSIVE", "CELLREAD"))
        door = plus(o["door"])
        b = self.leg(good_obs(), "in", load_seen=False, trigger="", incell=None, near_m=1.0,
                     arrival_read=fmt([door[0], door[1] - 5.0, door[2]]),
                     checks=[{"tag": "walk", "read": fmt([door[0], door[1] - 5.2, door[2]])}])
        v, cls, detail = self.judge(b)
        self.assertEqual((v, cls), ("INCONCLUSIVE", "NOREACH"), detail)
        self.assertIn("closest read 5.0 m", detail)
        # a walk read inside the range is reported, but NOLOAD needs the final stand there
        c = self.leg(good_obs(), "in", load_seen=False, trigger="", incell=0, arrival_read=fmt(plus(o["near"])),
                     checks=[{"tag": "walk", "read": fmt([door[0], door[1] - 2.0, door[2]])}])
        v, cls, detail = self.judge(c)
        self.assertEqual((v, cls), ("FAIL", "NOLOAD"), detail)
        self.assertIn("inside its 3 m range (GetInCell FO4Port_RedRocket01 0)", detail)

    def test_a_load_found_by_the_position_counts(self):
        obs = good_obs()
        for x in obs["legs"]:
            x.update(load_seen=False, load_by="position", load_s=None)
        v, cls, detail = self.judge(obs)
        self.assertEqual((v, cls), ("PASS", "PASS"), detail)
        self.assertIn("the load found by the position", detail)

    def test_the_load_after_moving_away(self):
        out_at = plus(PLAN["outside"]["arrival"])
        away = fmt(plus(PLAN["spawn_local"]))                    # the coc arrival, 43 m from the saved spot
        rl = good_obs()["reload"]
        cases = [(dict(rl, load_seen=False, away_read=away), ("PASS", "PASS")),        # back: the load happened
                 (dict(rl, load_seen=False), ("INCONCLUSIVE", "RELOAD_UNSEEN")),       # not moved, nothing seen
                 (dict(rl, load_seen=True, away_read=away, read=away), ("INCONCLUSIVE", "RELOAD_UNSEEN")),
                 (dict(rl, load_seen=False, away_read=away, read=away), ("INCONCLUSIVE", "RELOAD_UNSEEN")),
                 (dict(rl, load_seen=True, away_read=away, read=fmt([out_at[0], out_at[1] + 6, out_at[2]])),
                  ("FAIL", "RELOAD")),
                 (dict(rl, load_seen=False, away_read=away, read=None), ("INCONCLUSIVE", "RELOAD_UNSEEN")),
                 # gone from the away spot without a loading screen seen: the load moved the player, so it is judged
                 (dict(rl, load_seen=False, away_read=away, read=fmt([out_at[0], out_at[1] + 6, out_at[2]])),
                  ("FAIL", "RELOAD")),
                 (dict(rl, load_seen=False, away_read=away, read=fmt([out_at[0], out_at[1], out_at[2] - 40]),
                       settled=False), ("FAIL", "FELL"))]
        for r, want in cases:
            v, cls, detail = self.judge(dict(good_obs(), reload=r))
            self.assertEqual((v, cls), want, (r, detail))
        v, cls, detail = self.judge(dict(good_obs(), reload=cases[0][0]))
        self.assertIn("no loading screen seen, moved 43.9 m away before it", detail)

    def test_a_trip_loaded_only_from_the_last_try_is_nearonly(self):
        obs = self.leg(good_obs(), "out", trigger="near", near_m=1.5)
        v, cls, detail = self.judge(obs)
        self.assertEqual((v, cls), ("INCONCLUSIVE", "NEARONLY"), detail)
        self.assertIn("the out leg loaded only from the last-try teleport", detail)

    def test_the_door_getpos_diagnostic(self):
        o = PLAN["outside"]
        plan = {"outside": dict(o, ref="05000800")}
        for read, want in ((fmt(o["door"]), "its unmerged local position"), (fmt(plus(o["door"])), "its merged position"),
                           (fmt([0, 0, 0]), "another ref?"), ("fail", "not read")):
            v, cls, detail = self.judge(dict(good_obs(), door_read=read), plan=plan)
            self.assertEqual((v, cls), ("PASS", "PASS"), detail)
            self.assertIn(want, detail)
        nl = self.leg(dict(good_obs(), door_read=fmt(o["door"])), "in", load_seen=False, trigger="near", incell=0,
                      arrival_read=fmt(plus(o["near"])))
        v, cls, detail = self.judge(nl, plan=plan)
        self.assertEqual((v, cls), ("FAIL", "NOLOAD"), detail)
        self.assertIn("getpos of door 05000800 read", detail)
        self.assertNotIn("getpos", self.judge(good_obs())[2])          # no ref, no note

    def test_off_the_ground_after_the_load(self):
        # the saved spot itself is 1.5 m above the expected ground: same place after the load, but not on the terrain
        v, cls, detail = self.judge(good_obs(), plan={"outside": dict(PLAN["outside"], ground=98.2)})
        self.assertEqual((v, cls), ("FAIL", "OFFGROUND"), detail)
        v, cls, detail = self.judge(good_obs(), plan={"outside": dict(PLAN["outside"], ground=None)})
        self.assertEqual((v, cls), ("PASS", "PASS"), detail)            # no ground given: the position alone

    def test_judge_adds_the_expectation(self):
        t = tq.door_test(0, dict(PLAN, expect="PASS", basis="vanilla cave doors"))
        v, cls, detail = tq.judge(t, good_obs(), tempfile.mkdtemp())
        self.assertEqual(v, "INCONCLUSIVE")                             # the shots are not on disk here
        out = tempfile.mkdtemp()
        for n in ("in_arrival.png", "out_arrival.png", "reload.png"):
            open(os.path.join(out, n), "wb").close()
        v, cls, detail = tq.judge(t, good_obs(), out)
        self.assertEqual((v, cls), ("PASS", "PASS"), detail)
        self.assertTrue(detail.endswith("[expected PASS]"))


class InCellParseTests(unittest.TestCase):
    def test_getincell_replies(self):
        cases = [("Clear Console player.GetlnCell FO4Port_RedRocket01 GetlnCell > > 1.00", 1),
                 ("GetInCell >> 1.00 ClearConsole player.GetInCell FO4Port_RedRocket01 GetInCell >> 0.00", 0),
                 ("GetInCell >> 1.00 ClearConsole player.GetInCell FO4Port_RedRocket01", None),
                 ("ClearConsole player.GetInCell FO4Port_RedRocket01 GetInCeII 1.00", 1)]
        for text, want in cases:
            self.assertEqual(parse_npc.parse(text, ["incell"])["incell"], want, text)


def put(path, data):
    with open(path, "wb") as f:
        f.write(data)


def get(path):
    with open(path, "rb") as f:
        return f.read()


def write_plugin(path, masters, flags=1):
    sub = b""
    for m in masters:
        name = m.encode() + b"\0"
        sub += b"MAST" + struct.pack("<H", len(name)) + name + b"DATA" + struct.pack("<H", 8) + b"\0" * 8
    sub = b"HEDR" + struct.pack("<H", 12) + b"\0" * 12 + sub
    with open(path, "wb") as f:
        f.write(b"TES4" + struct.pack("<IIIIHH", len(sub), flags, 0, 0, 0, 0) + sub)


class PluginOrderTests(unittest.TestCase):
    def test_masters_from_the_header(self):
        d = tempfile.mkdtemp()
        write_plugin(os.path.join(d, "X.esm"), ["Starfield.esm", "FO4TerrainExp2.esm", "FO4Port.esm"])
        self.assertEqual(exp_install.plugin_masters(os.path.join(d, "X.esm")),
                         ["Starfield.esm", "FO4TerrainExp2.esm", "FO4Port.esm"])
        open(os.path.join(d, "bad.esm"), "wb").write(b"NOPE" + b"\0" * 30)
        with self.assertRaises(ValueError):
            exp_install.plugin_masters(os.path.join(d, "bad.esm"))

    def test_lines_move_after_their_masters(self):
        masters = {"FO4TerrainExp2.esm": ["Starfield.esm"],
                   "FO4TerrainExp2_Mars.esm": ["Starfield.esm", "FO4TerrainExp2.esm"],
                   "FO4SliceRedRocket.esm": ["Starfield.esm", "FO4TerrainExp2.esm", "FO4Port.esm"]}
        plugins = list(masters)
        # what Plugins.txt holds at launch: the experiment appended in pre_launch, FO4Port.esm by cycle's deploy
        lines = ["# header", "*FO4TerrainExp2.esm", "*FO4TerrainExp2_Mars.esm", "*FO4SliceRedRocket.esm", "*FO4Port.esm"]
        new, moved, missing = exp_install.order_lines(lines, plugins, masters)
        self.assertEqual(new, ["# header", "*FO4TerrainExp2.esm", "*FO4TerrainExp2_Mars.esm", "*FO4Port.esm",
                               "*FO4SliceRedRocket.esm"])
        self.assertEqual((moved, missing), (["FO4SliceRedRocket.esm"], []))
        again, moved, _ = exp_install.order_lines(new, plugins, masters)    # idempotent
        self.assertEqual((again, moved), (new, []))
        # without FO4Port.esm in Plugins.txt the plugin cannot load: named, nothing moved for it
        _, _, missing = exp_install.order_lines(lines[:-1], plugins, masters)
        self.assertEqual(missing, [("FO4SliceRedRocket.esm", "FO4Port.esm")])
        # an experiment without such a master (exp2d) is left exactly as it is
        two = ["*FO4TerrainExp2.esm", "*FO4TerrainExp2_Mars.esm", "*FO4Port.esm"]
        self.assertEqual(exp_install.order_lines(two, plugins[:2], masters)[0], two)

    def test_order_rewrites_plugins_txt_keeping_its_format(self):
        d = tempfile.mkdtemp()
        sf, appdata = os.path.join(d, "Starfield"), os.path.join(d, "appdata")
        os.makedirs(os.path.join(sf, "Data")), os.makedirs(os.path.join(appdata, "Starfield"))
        write_plugin(os.path.join(sf, "Data", "E.esm"), ["Starfield.esm"])
        write_plugin(os.path.join(sf, "Data", "S.esm"), ["Starfield.esm", "E.esm", "FO4Port.esm"])
        with open(os.path.join(sf, "Data", exp_install.RECORD), "w") as f:
            json.dump({"exp_dir": d, "files": {}, "dirs": [], "plugins_added": ["*E.esm", "*S.esm"]}, f)
        p = os.path.join(appdata, "Starfield", "Plugins.txt")
        put(p, b"\xef\xbb\xbf# keep\r\n*E.esm\r\n*S.esm\r\n*FO4Port.esm\r\n")
        a = mock.Mock(starfield=sf)
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": appdata}):
            self.assertEqual(exp_install.order(a), 0)
            self.assertEqual(get(p), b"\xef\xbb\xbf# keep\r\n*E.esm\r\n*FO4Port.esm\r\n*S.esm\r\n")
            self.assertEqual(exp_install.order(a), 0)                       # nothing more to move
            put(p, b"*E.esm\r\n*S.esm\r\n")
            self.assertEqual(exp_install.order(a), 6)                       # FO4Port.esm not active: refused
            self.assertEqual(get(p), b"*E.esm\r\n*S.esm\r\n")
            os.remove(os.path.join(sf, "Data", exp_install.RECORD))
            self.assertEqual(exp_install.order(a), 0)                       # nothing installed


class FeatureTests(unittest.TestCase):
    def test_features(self):
        self.assertIn("door_trip", runner_features.FEATURES)
        self.assertIn("plugin_order", runner_features.FEATURES)
        self.assertEqual(runner_features.missing(["door_check", "door_trip", "plugin_order"]), [])


if __name__ == "__main__":
    unittest.main()
