"""scripts/bridge/door_probe.py (the scripted door's Step 0): the three targets checked in a plugin report, the four
plan.json tests through the runner's own planner, and the queue README's decision lines. Synthetic data; no game."""
import argparse
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "bridge"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import console_plan as cp  # noqa: E402
import door_probe as dp  # noqa: E402
import testqueue as tq  # noqa: E402
from test_testqueue import jdump, jload, writef  # noqa: E402

SPAWN = [-989.2571, 1146.5143, 105.2609]
ZREF = {"label": "zref_ground", "x": -985.2571, "y": 1138.5143, "expect": 105.0253}


def ref(local, persistent, cell, kind, pos, grid=None):
    return {"formid": f"01{local:06X}", "edid": None, "record_flags": "0x400" if persistent else "0x0",
            "persistent": persistent, "group": "persistent children" if persistent else "temporary children",
            "cell": cell, "cell_kind": kind, "cell_grid": grid, "base": "0100003B", "pos": pos}


def report(**over):
    refs = {"anchor": ref(0x800, True, "01001805", "persistent", [-989.2571, 1146.5143, 105.1429]),
            "stimpak": ref(0x0116FB, False, "01000DAF", "exterior", [-993.4615, 1151.8423, 105.3653], [-10, 11]),
            "far_door": ref(0x02D22C, False, "01000EEB", "exterior", [-469.8529, 636.7089, 42.356], [-5, 6])}
    refs.update(over)
    return {"worlds": {"FO4Core_Commonwealth": {"persistent_cell": {"formid": "01001805"}}},
            "refs": [r for r in refs.values() if r is not None]}


FORMIDS = {"items": {"066996:Fallout4.esm": {"base": "0A2B77", "ref": "0116FB"}}, "refs": {"0EE661:Fallout4.esm": "02D22C"}}


class TargetTests(unittest.TestCase):
    def test_the_three_targets(self):
        t = dp.check_targets(report(), FORMIDS)
        self.assertEqual({k: (v["local"], v["storage"]) for k, v in t.items()},
                         {"anchor": (2048, "persistent"), "stimpak": (71419, "temporary"), "far_door": (184876, "temporary")})
        d = dp.check_distances(t, SPAWN)
        self.assertLess(d["stimpak"], 10.0)
        self.assertAlmostEqual(d["far_door"], 727.8, places=1)

    def test_wrong_storage_slot_or_absence_stops(self):
        bad = [(report(anchor=ref(0x800, False, "01000DAF", "exterior", [0, 0, 0])), FORMIDS),       # anchor temporary
               (report(stimpak=ref(0x0116FB, True, "01001805", "persistent", [0, 0, 0])), FORMIDS),  # Stimpak persistent
               (report(far_door=None), FORMIDS),                                                     # missing
               (report(), {"items": {"066996:Fallout4.esm": {"ref": "0116FC"}}, "refs": FORMIDS["refs"]}),   # slot moved
               ({"worlds": {}, "refs": []}, FORMIDS)]
        for rep, fids in bad:
            with self.assertRaises(SystemExit):
                dp.check_targets(rep, fids)

    def test_distances_guard_the_loaded_and_unloaded_cases(self):
        t = dp.check_targets(report(), FORMIDS)
        near = dict(t, far_door=dict(t["far_door"], pos=[-900.0, 1100.0, 0.0]))
        with self.assertRaises(SystemExit):
            dp.check_distances(near, SPAWN)
        far = dict(t, stimpak=dict(t["stimpak"], pos=[-700.0, 1146.0, 0.0]))
        with self.assertRaises(SystemExit):
            dp.check_distances(far, SPAWN)


class PlanTests(unittest.TestCase):
    def test_four_tests_of_whitelisted_lines(self):
        plan = dp.plan_entries(SPAWN, ZREF)
        self.assertEqual([p["coc"] for p in plan], ["FO4Core_RedRocketSpawn"] + ["FO4Port_RedRocket01"] * 3)
        for p in plan:
            self.assertTrue(all(cp.allowed(c) for c in p["console_post"]), p["console_post"])
            self.assertTrue(p["console_post"][0].startswith('cgf "FO4SF_Probe.Ack" "door-probe-'))
        three = ['cgf "FO4SF_Probe.Resolve" "FO4TerrainCore.esm" 2048', 'cgf "FO4SF_Probe.Resolve" "FO4TerrainCore.esm" 71419',
                 'cgf "FO4SF_Probe.Resolve" "FO4TerrainCore.esm" 184876']
        self.assertEqual(plan[0]["console_post"][1:], three)
        self.assertEqual(plan[1]["console_post"][1:], three)
        self.assertEqual(plan[2]["console_post"][2], 'cgf "FO4SF_Probe.MoveTo" "FO4TerrainCore.esm" 2048 0.0 0.0 0.0')
        self.assertEqual(plan[3]["console_post"][2], 'cgf "FO4SF_Probe.MoveTo" "FO4TerrainCore.esm" 2048 -1200.0 -2700.0 0.0')
        for p in plan[2:]:
            self.assertEqual(p["console_post"][3:], ['cgf "FO4SF_Probe.Pos" 20', three[0], three[1]])
            self.assertNotIn("spawn_local", p)                    # an interior arrival: the points are absolute
        self.assertEqual(plan[0]["spawn_local"], SPAWN)
        self.assertEqual((plan[2]["points"][0]["x"], plan[2]["points"][0]["y"]), (ZREF["x"], ZREF["y"]))      # local
        self.assertEqual((plan[3]["points"][0]["x"], plan[3]["points"][0]["y"]), (-2185.2571, -1561.4857))   # merged
        self.assertEqual(plan[1]["points"][0]["label"], "cave_arrival")
        self.assertAlmostEqual(plan[1]["drop_z"], 1.7442)
        for p in plan:                                             # no 500 m default "beyond" teleport
            pt = p["points"][0]
            self.assertLess(abs(p["beyond"]["x"] - pt["x"]) + abs(p["beyond"]["y"] - pt["y"]), 15.0)

    def stage_dirs(self, d):
        staging, exp, br = (os.path.join(d, n) for n in ("staging", "exp", "bridge"))
        for p in (staging, os.path.join(br, "Data", "Scripts")):
            os.makedirs(p)
        writef(os.path.join(staging, "FO4Port.esm"), b"TES4")
        writef(os.path.join(br, "FO4SFBridge.esm"), b"TES4")
        for n in ("FO4SF_Bridge.pex", "FO4SF_Probe.pex"):
            writef(os.path.join(br, "Data", "Scripts", n), b"pex")
        os.makedirs(exp)
        jdump(dp.plan_entries(SPAWN, ZREF), os.path.join(exp, "plan.json"))
        return staging, exp, br

    def test_the_runner_plans_it_with_its_features(self):
        with tempfile.TemporaryDirectory() as d:
            staging, exp, br = self.stage_dirs(d)
            out = os.path.join(d, "queue")
            tq.main(["plan-terrain", "--staging", staging, "--exp-dir", exp, "--out", out, "--bridge", br,
                     "--plugins", "FO4TerrainCore.esm,FO4TerrainCore_Mars.esm", "--fresh"])
            q = jload(os.path.join(out, "queue.json"))
            self.assertEqual(q["needs"], ["bridge", "console", "probe_moveto"])
            self.assertIn("--needs", q["pre_launch"])
            self.assertEqual(sorted(k.replace("\\", "/") for k in q["bridge"]["sha256"]),
                             ["Data/Scripts/FO4SF_Bridge.pex", "Data/Scripts/FO4SF_Probe.pex", "FO4SFBridge.esm"])
            self.assertEqual([t["id"] for t in q["tests"]],
                             ["0000_terrain_FO4Core_RedRocketSpawn", "0001_terrain_FO4Port_RedRocket01",
                              "0002_terrain_FO4Port_RedRocket01", "0003_terrain_FO4Port_RedRocket01"])
            self.assertTrue(all(t["fresh"] and t["bridge_reads"] for t in q["tests"]))
            self.assertEqual(tq.step_timeout(q["tests"][3]) - tq.step_timeout(dict(q["tests"][3], console_post=[])),
                             6 * tq.CONSOLE_CMD_S + tq.MOVETO_S)
            # the queue README names every decisive line and the reference points
            info = {"core": "C:/core", "persistent_cell": "01001805", "targets": dp.check_targets(report(), FORMIDS)}
            dp.check_distances(info["targets"], SPAWN)
            text = dp.queue_readme(q, info)
            for s in ('"FO4SF resolve ... id=2048"', '"FO4SF resolve ... id=71419"', '"... id=184876"', "phase=after",
                      "phase=settled", "(-2189.257, -1553.486)", "(-989.257, 1146.514)", "(-3389.257, -4253.486)",
                      "33556480 = 02000800", "33625851 = 020116FB", "33739308 = 0202D22C", "67117880 = 04002338",
                      "33557935 = 02000DAF", "bridge_install.py uninstall", "probe_moveto", "FO4Port_Vault111Cryo",
                      "bridge_log.py events"):
                self.assertIn(s, text)
            self.assertTrue(text.endswith("\r\n"))


class StageTests(unittest.TestCase):
    def test_an_existing_folder_is_refused_before_anything_is_read(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(dp.persistent_refs, "walk") as walk:
                with self.assertRaises(SystemExit):
                    dp.stage(argparse.Namespace(core=os.path.join(d, "core"), out=d))
                walk.assert_not_called()

    def test_link_tree_links_and_never_copies(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "src")
            os.makedirs(os.path.join(src, "meshes"))
            writef(os.path.join(src, "meshes", "a.nif"), b"x")
            writef(os.path.join(src, "b.txt"), b"y")
            self.assertEqual(dp.link_tree(src, os.path.join(d, "dst")), 2)
            self.assertTrue(os.path.samefile(os.path.join(src, "meshes", "a.nif"), os.path.join(d, "dst", "meshes", "a.nif")))
            with mock.patch.object(dp.os, "link", side_effect=OSError("cross-volume")):
                with self.assertRaises(OSError):                     # a link that fails stops: never a copy instead
                    dp.link_tree(src, os.path.join(d, "dst2"))
            self.assertFalse(os.path.exists(os.path.join(d, "dst2", "b.txt")))


if __name__ == "__main__":
    unittest.main()
