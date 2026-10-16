"""door_trip (docs/slice/redrocket-door.md, docs/slice/door-frames.md): planning, the judge on synthetic observations,
the step timeout, the runner features, GetInCell parsing and the experiment plugin order (exp_install.py order).
Synthetic data only. Since the first live runs (2026-10-13) GetInCell never decides (the console refused the cell's
EditorID): which side of the door the player is on comes from the position frames."""
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
        self.assertEqual(runner_features.needs([t]), ["door_check", "door_frames", "door_trip"])
        old = {k: v for k, v in t.items() if k not in ("moved_m", "activate_m", "reads")}   # a test planned at bf7c853
        self.assertEqual(runner_features.needs([old]), ["door_trip"])
        b = {k: v for k, v in t.items() if k != "reads"}                                    # planned at 95552f8
        self.assertEqual(runner_features.needs([b]), ["door_check", "door_trip"])

    def test_what_is_typed_is_validated(self):
        bad = [{"travel": "coc FO4CW_RedRocketSpawn; tgm"}, {"travel": "player.moveto 02000800"},
               {"save": "fo4sf_test_1a2b3c4d"}, {"save": "slice door"}, {"save": "myplaythrough"},
               {"inside": dict(PLAN["inside"], cell="FO4Port RedRocket01")},
               {"inside": dict(PLAN["inside"], cell="")}, {"outside": dict(PLAN["outside"], door=[1, 2])},
               {"outside": dict(PLAN["outside"], extra=1)}, {"walk_ms": 10 ** 6}, {"unknown_key": 1},
               {"outside": dict(PLAN["outside"], start=[float("nan"), 0, 0])},
               {"outside": dict(PLAN["outside"], ref="0500080")}, {"outside": dict(PLAN["outside"], ref="05000800;tgm")},
               {"inside": dict(PLAN["inside"], ref="05000801")}, {"activate_m": 50}, {"moved_m": 1},
               {"inside": dict(PLAN["inside"], cell_id="FO4Port_RedRocket01")},
               {"outside": dict(PLAN["outside"], route=[[0, 0, 0]])},
               {"outside": dict(PLAN["outside"], route=[[0, 0, 0], [1, 2]])},
               {"outside": dict(PLAN["outside"], route=[[-989.0, 1147.0, 105.0], [-990.0, 1120.0, 100.0]])},  # ends 10 m short
               {"outside": dict(PLAN["outside"], arrival_heading="north")}, {"facing_tol": 0},
               {"probes": [{"ref": "0200080", "local": [0, 0, 0]}]}, {"probes": [{"ref": "02000800", "local": [0, 0]}]},
               {"probes": [{"ref": "02000800", "local": [0, 0, 0], "extra": 1}]}]
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
        self.assertTrue(q["tests"][0]["fresh"])
        pre = q["pre_launch"]
        self.assertEqual(pre[pre.index("--plugins") + 1], plugins)
        self.assertEqual(pre[pre.index("--needs") + 1], "door_check,door_frames,door_trip,plugin_order")
        self.assertIn("--pack", pre)
        self.assertGreater(tq.step_timeout(q["tests"][0]), 2000)
        self.assertEqual(q["needs"], ["door_check", "door_frames", "door_trip", "plugin_order"])

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
        self.assertIn("in: arrived 0.0 m from the interior arrival point (interior frame), GetInCell "
                      "FO4Port_RedRocket01 1 (a diagnostic, not judged), trigger walk", detail)
        self.assertIn("out: arrived 0.0 m from the merged exterior arrival point (merged exterior frame)", detail)
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
            # GetInCell is a diagnostic only: the position at this side's door decides
            (self.leg(good_obs(), "in", load_seen=False, arrival_read=at_door, trigger="", incell=1), ("FAIL", "NOLOAD")),
            # never within the door's range: the door was not tried
            (self.leg(good_obs(), "in", load_seen=False, arrival_read=far, trigger="", incell=0), ("INCONCLUSIVE", "NOREACH")),
            (self.leg(good_obs(), "in", load_seen=False, arrival_read=at_door, trigger="", incell=0, arrival_settled=False),
             ("INCONCLUSIVE", "UNREAD")),
            (self.leg(good_obs(), "in", load_seen=True, arrival_read=far), ("INCONCLUSIVE", "NOMOVE")),
            (self.leg(good_obs(), "in", arrival_read=None), ("INCONCLUSIVE", "UNREAD")),
            (self.leg(good_obs(), "in", shot=None), ("INCONCLUSIVE", "NOSHOT")),
            (self.leg(good_obs(), "in", incell=0), ("PASS", "PASS")),                     # GetInCell not judged
            # loaded into the interior frame (within frame_m of the interior door) but away from the arrival point
            (self.leg(good_obs(), "in", arrival_read=fmt([40, 40, 0]), incell=None), ("FAIL", "ELSEWHERE")),
            # loaded, but still in the merged exterior frame, 120 m from the door
            (self.leg(good_obs(), "in", arrival_read=fmt(plus(o["door"], [OFF[0] + 120, OFF[1], OFF[2]]))),
             ("FAIL", "WRONGCELL")),
            # in no known frame: inconclusive, whatever GetInCell said
            (self.leg(good_obs(), "in", arrival_read=fmt([-500, 300, 20]), incell=0), ("INCONCLUSIVE", "ELSEWHERE")),
            (self.leg(good_obs(), "in", arrival_read=fmt([-500, 300, 20]), incell=None), ("INCONCLUSIVE", "ELSEWHERE")),
            (self.leg(good_obs(), "in", arrival_settled=False), ("INCONCLUSIVE", "UNREAD")),
            (dict(good_obs(), legs=good_obs()["legs"][:1]), ("INCONCLUSIVE", "UNREAD")),
            (self.leg(good_obs(), "out", arrival_read=fmt(o["arrival"])), ("FAIL", "UNMERGED")),
            (self.leg(good_obs(), "out", arrival_read=fmt(plus(o["arrival"], [OFF[0] + 300, OFF[1] - 100, 0.3]))),
             ("FAIL", "REMERGED")),
            (self.leg(good_obs(), "out", arrival_read=fmt(plus(o["arrival"], [OFF[0], OFF[1], -40])),
                      arrival_settled=False), ("FAIL", "FELL")),
            (self.leg(good_obs(), "out", load_seen=False, arrival_read=fmt(i["near"]), incell=1), ("FAIL", "NOLOAD")),
            (self.leg(good_obs(), "out", load_seen=False, arrival_read=fmt(i["near"]), incell=0), ("FAIL", "NOLOAD")),
            (self.leg(good_obs(), "out", load_seen=False, arrival_read=fmt(i["start"]), incell=1),
             ("INCONCLUSIVE", "NOREACH")),
            (self.leg(good_obs(), "in", load_seen=False, load_by="position", arrival_read=fmt([30, 30, 0]), incell=0),
             ("FAIL", "ELSEWHERE")),
            # the out leg loaded, but the player is still in the interior frame (47 m from the interior start)
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
            # GetInCell after the load is a diagnostic only
            (dict(good_obs(), reload=dict(good_obs()["reload"], incell=1)), ("PASS", "PASS")),
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
        self.assertEqual(self.judge(a)[:2], ("INCONCLUSIVE", "NOREACH"))           # 10 m from the door: not tried
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
        self.assertIn("inside its 3 m range, after trigger none", detail)

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


class DoorFramesTests(unittest.TestCase):
    """door_frames (docs/slice/door-frames.md): routes, facing, probes, rejected reads."""
    ROUTE_OUT = [PLAN["spawn_local"], [-985.0, 1130.0, 105.0], [-995.26, 1107.01, 99.06]]
    ROUTE_IN = [PLAN["inside"]["arrival"], [-3.0, -2.0, 0.0], [-2.0, 0.8, 0.0]]
    # the steps qstep.ps1 Route-Walk records: a read on this side after every W hold, none for the hold that loaded
    STEPS_IN = [{"wp": 1, "ms": 2000, "state": "here", "read": fmt(plus([-986.5, 1138.5, 105.1]))},
                {"wp": 1, "ms": 1800, "state": "here", "read": fmt(plus([-985.1, 1130.4, 105.0]))},
                {"wp": 2, "ms": 2000, "state": "here", "read": fmt(plus([-989.4, 1120.6, 102.1]))},
                {"wp": 2, "ms": 2000, "state": "here", "read": fmt(plus([-993.6, 1111.2, 99.3]))},
                {"wp": 3, "ms": 500, "state": "loaded", "read": None}]
    STEPS_OUT = [{"wp": 1, "ms": 1200, "state": "here", "read": fmt([-2.8, -2.3, 0.0])},
                 {"wp": 2, "ms": 700, "state": "loaded", "read": None}]

    def plan(self, **kw):
        o = dict(PLAN["outside"], route=self.ROUTE_OUT, arrival_heading=181.92)
        i = dict(PLAN["inside"], route=self.ROUTE_IN, arrival_heading=154.78)
        d = dict(PLAN, outside=o, inside=i, moved_m=150.0)
        d.update(kw)
        return d

    def obs(self):
        obs = good_obs()
        obs["legs"][0].update(start_read=fmt(plus(PLAN["spawn_local"])), mode="route", teleports=0,
                              steps=[dict(s) for s in self.STEPS_IN], arrival_heading=154.6)
        obs["legs"][1].update(start_read=fmt(PLAN["inside"]["arrival"]), mode="route", teleports=0,
                              steps=[dict(s) for s in self.STEPS_OUT], arrival_heading=182.3)
        obs["reload"]["heading"] = 182.1
        return obs

    def judge(self, obs, **kw):
        t = tq.door_test(0, self.plan(**kw))
        return tq.judge_door(t, obs, lambda name: bool(name))

    def test_the_route_plan(self):
        t = tq.door_test(0, self.plan())
        self.assertEqual(len(t["outside"]["route"]), 3)
        self.assertEqual((t["outside"]["arrival_heading"], t["inside"]["arrival_heading"]), (181.92, 154.78))
        self.assertEqual(runner_features.needs([t]), ["door_check", "door_frames", "door_route", "door_trip"])
        self.assertEqual((t["route_hold_ms"], t["route_max_steps"], t["facing_tol"]), (2000, 40, 20.0))
        # the worst-case sum is capped: a hung routed trip must not hold the game for hours (live trips: 8-12 min)
        self.assertEqual(tq.door_timeout(t), tq.DOOR_TIMEOUT_CAP_S)
        self.assertGreaterEqual(tq.step_timeout(t), tq.step_timeout(tq.door_test(0, PLAN)))
        with self.assertRaises(SystemExit):                       # a route longer than moved_m allows
            tq.door_test(0, dict(self.plan(), moved_m=30.0))
        self.assertEqual(tq.door_test(0, dict(PLAN, outside=dict(PLAN["outside"], arrival_heading=-178.08)))
                         ["outside"]["arrival_heading"], 181.92)

    def test_a_walked_trip_with_the_right_facing_passes(self):
        v, cls, detail = self.judge(self.obs())
        self.assertEqual((v, cls), ("PASS", "PASS"), detail)
        self.assertIn("along the route (5 steps, 0 teleports)", detail)
        self.assertIn("out arrival heading 182.3, want 181.9", detail)
        self.assertIn("heading after the load (the saved one) heading 182.1", detail)

    def test_the_walk_must_show_in_the_record(self):
        # Codex's review of PR #107: a routed trip passed with mode route and no steps, and with one teleport and
        # trigger walk; the arrival, save and load positions alone cannot tell a walked route from a teleport
        o = PLAN["outside"]
        straight = [plus(p) for p in ([-990.5, 1137.5, 104.0], [-992.0, 1128.0, 102.0], [-993.5, 1118.5, 100.5],
                                      [-994.5, 1111.5, 99.0])]                   # misses waypoint 1 by 6.6 m
        cases = [({"steps": []}, "no route step read on this side"),
                 ({"teleports": 1}, "1 teleport(s) in a routed leg"),
                 ({"mode": None}, "mode straight, planned route"),
                 ({"mode": "straight", "teleports": 1}, "mode straight, planned route"),
                 ({"steps": [{"wp": 1, "ms": 2000, "state": "loaded", "read": None}]}, "no route step read on this side"),
                 ({"steps": [dict(self.STEPS_IN[0], read=None)] + self.STEPS_IN[1:]}, "1 step(s) not read on this side"),
                 ({"steps": [dict(self.STEPS_IN[0], read=fmt(plus([-985.1, 1030.4, 105.0])))] + self.STEPS_IN[1:]},
                  "step 1 read 116.9 m from the read before, beyond the 21 m its hold walks"),
                 ({"steps": [dict(s, read=fmt(p)) for s, p in zip(self.STEPS_IN, straight)] + [self.STEPS_IN[-1]]},
                  "waypoint 1 passed no closer than 6.6 m"),
                 ({"steps": self.STEPS_IN[:2] + [self.STEPS_IN[-1]]},
                  "the last read on this side was 24.0 m from the door, beyond the 9 m the last hold walks")]
        for bad, want in cases:
            obs = self.obs()
            obs["legs"][0].update(bad)
            v, cls, detail = self.judge(obs)
            self.assertEqual((v, cls), ("INCONCLUSIVE", "ROUTE"), (bad, detail))
            self.assertIn(f"in: arrived, but the walk is not shown: {want}", detail)
        obs = self.obs()
        obs["legs"][1].update(steps=[], teleports=1)
        v, cls, detail = self.judge(obs)
        self.assertEqual((v, cls), ("INCONCLUSIVE", "ROUTE"), detail)
        self.assertIn("out: arrived, but the walk is not shown: 1 teleport(s)", detail)
        # a route that loaded only after the near teleport stays NEARONLY, with or without steps
        for steps in ([], self.STEPS_IN):
            obs = self.obs()
            obs["legs"][0].update(trigger="near", near_m=1.0, teleports=1, steps=steps)
            v, cls, detail = self.judge(obs)
            self.assertEqual((v, cls), ("INCONCLUSIVE", "NEARONLY"), detail)
        # a position failure still comes first
        obs = self.obs()
        obs["legs"][0].update(steps=[], load_seen=False, trigger="", arrival_read=fmt(plus(o["near"])))
        self.assertEqual(self.judge(obs)[:2], ("FAIL", "NOLOAD"))
        # a straight trip (no route planned) whose record claims a route
        obs = good_obs()
        obs["legs"][0]["mode"] = "route"
        v, cls, detail = tq.judge_door(tq.door_test(0, PLAN), obs, lambda n: True)
        self.assertEqual((v, cls), ("INCONCLUSIVE", "ROUTE"), detail)
        self.assertIn("mode route, planned straight", detail)

    def test_the_route_start_is_where_the_player_stands(self):
        obs = self.obs()
        obs["legs"][0]["start_read"] = fmt(plus(PLAN["outside"]["start"]))   # 43 m from the coc arrival
        self.assertEqual(self.judge(obs)[:2], ("INCONCLUSIVE", "START"))

    def test_facing(self):
        obs = self.obs()
        obs["legs"][1]["arrival_heading"] = 6.0                # facing the cave instead of away from it
        v, cls, detail = self.judge(obs)
        self.assertEqual((v, cls), ("FAIL", "FACING"), detail)
        self.assertIn("out arrival heading 6.0, want 181.9 (175.9 degrees off", detail)
        obs = self.obs()
        obs["reload"]["heading"] = 0.0                         # the away teleport's heading came back, not the saved one
        self.assertEqual(self.judge(obs)[:2], ("FAIL", "FACING"))
        obs = self.obs()
        obs["legs"][0]["arrival_heading"] = None
        v, cls, detail = self.judge(obs)
        self.assertEqual((v, cls), ("INCONCLUSIVE", "NOFACING"), detail)
        obs = self.obs()                                       # wraps around north
        obs["legs"][0]["arrival_heading"] = 154.78 + 359.0 - 360.0
        self.assertEqual(self.judge(obs)[:2], ("PASS", "PASS"))
        # a position failure comes first; a FACING failure before NEARONLY
        obs = self.obs()
        obs["legs"][1]["arrival_read"] = fmt(PLAN["outside"]["arrival"])
        self.assertEqual(self.judge(obs)[:2], ("FAIL", "UNMERGED"))
        obs = self.obs()
        obs["legs"][1].update(trigger="near", arrival_heading=6.0)
        self.assertEqual(self.judge(obs)[:2], ("FAIL", "FACING"))
        # no heading planned: not judged
        self.assertEqual(tq.judge_door(tq.door_test(0, PLAN), good_obs(), lambda n: True)[:2], ("PASS", "PASS"))

    def test_probes_say_which_storage_merged(self):
        probes = [{"ref": "02000800", "local": [-989.2571, 1146.5143, 105.1429], "what": "anchor, persistent cell"},
                  {"ref": "05000802", "local": [-987.2571, 1146.5143, 105.1429], "what": "exterior cell, persistent"},
                  {"ref": "05000803", "local": [-985.2571, 1146.5143, 105.1429], "what": "exterior cell, temporary"}]
        obs = self.obs()
        obs["probe_reads"] = [{"ref": "02000800", "read": fmt(probes[0]["local"])},
                              {"ref": "05000802", "read": fmt(plus(probes[1]["local"]))},
                              {"ref": "05000803", "read": "fail"}]
        v, cls, detail = self.judge(obs, probes=probes)
        self.assertEqual((v, cls), ("PASS", "PASS"), detail)
        self.assertIn("probe 02000800 (anchor, persistent cell) read -989.26 1146.51 105.14: its unmerged local", detail)
        self.assertIn("probe 05000802 (exterior cell, persistent) read", detail)
        self.assertIn(": its merged position", detail)
        self.assertIn("probe 05000803 (exterior cell, temporary) not read", detail)
        # the notes come with a failing leg too (the probes are read before the walk)
        obs["legs"][0].update(load_seen=False, trigger="near", near_m=1.0, arrival_read=fmt(plus(PLAN["outside"]["near"])),
                              arrival_settled=True)
        v, cls, detail = self.judge(obs, probes=probes)
        self.assertEqual((v, cls), ("FAIL", "NOLOAD"), detail)
        self.assertIn("probe 02000800", detail)

    def test_rejected_reads_are_named(self):
        obs = self.obs()
        obs["legs"][0]["checks"] = [{"tag": "walk", "read": "99.74 -2195.27 99.41", "rejected": "axes swapped"},
                                    {"tag": "walk_confirm", "read": fmt(plus([-995.27, 1106.29, 99.40]))}]
        v, cls, detail = self.judge(obs)
        self.assertEqual((v, cls), ("PASS", "PASS"), detail)
        self.assertIn("1 read(s) rejected (axes swapped)", detail)

    def test_getincell_is_only_a_note(self):
        obs = self.obs()
        obs["legs"][0].update(incell=None, incell_error="not found for parameter Cell")
        v, cls, detail = self.judge(obs, inside=dict(self.plan()["inside"], cell_id="04002338"))
        self.assertEqual((v, cls), ("PASS", "PASS"), detail)
        self.assertIn("GetInCell 04002338 unread (not found for parameter Cell) (a diagnostic, not judged)", detail)


class InCellParseTests(unittest.TestCase):
    def test_the_refusal_of_the_first_live_run(self):
        # slice_door_1013 a1, in_cell_ocr.txt (2026-10-13): the console refused the cell's EditorID
        text = ("DOOR player. get pos y GetPos: Y -1593.51 player, get pos z GetPos: z 99.41 Clear Console player. "
                "Getl n Cell F04Port_RedRocket01 'F04Port Red RocketOl not found for pararneter Cell. Cornpiled script "
                "not saved! 'F 04 SL")
        r = parse_npc.parse(text, ["incell"])
        self.assertIsNone(r["incell"])
        self.assertEqual(r["incell_error"], "not found for parameter Cell")
        r = parse_npc.parse("ClearConsole player.GetInCell 04002338 Compiled script not saved!", ["incell"])
        self.assertEqual((r["incell"], r["incell_error"]), (None, "compiled script not saved"))
        self.assertIsNone(parse_npc.parse("ClearConsole player.GetInCell 04002338 GetInCell >> 1.00",
                                          ["incell"])["incell_error"])

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
