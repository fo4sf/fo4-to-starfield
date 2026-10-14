"""make_cave_core64c.py (docs/slice/cave-routes.md): the plan entry the runner gets (both legs routed, facing, probes,
moved_m past the routes' reach), the facing from XTEL rotations, the hard-linked install tree. Synthetic data only."""
import json
import math
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "slice"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import make_cave_core64c as mk  # noqa: E402
import testqueue as tq  # noqa: E402

# the link as staged on exp2d (docs/slice/redrocket-door.md section 4), world frame / interior frame
SIDES = {"outside": {"door": [-994.94814, 1109.49007, 98.68436], "arrival": [-995.53029, 1104.14286, 99.77143],
                     "near": [-995.0564, 1108.4959, 98.3114], "ground": 99.7343},
         "inside": {"door": [-1.65907, 2.41581, 0.0], "arrival": [0.04926, -6.62199, -0.00623],
                    "near": [-2.1547, 1.0001, -0.0082], "floor": 0.2442}}
ROUTES = {"outside": {"route": [[-989.2571, 1146.5143, 105.2609], [-982.7571, 1127.5143, 105.0253],
                                [-995.2571, 1103.5143, 99.6857], [-995.03, 1106.98, 99.05]], "walk_ms": 28300},
          "inside": {"route": [[0.0493, -6.622, 0.2442], [-0.9507, -1.622, 0.6809], [-0.9507, -0.122, 0.5021]],
                     "walk_ms": 10300}}
SPAWN = [-989.2571, 1146.5143, 105.2609]


class CaveCore64cPlanTests(unittest.TestCase):
    def entry(self, probes=()):
        return mk.plan_entry(SIDES, ROUTES, SPAWN, -3.1081858, 2.7014012, list(probes))

    def test_facing_from_the_xtel_rotations(self):
        e = self.entry()
        self.assertAlmostEqual(e["outside"]["arrival_heading"], 181.914, places=3)   # facing south, out of the cave
        self.assertAlmostEqual(e["inside"]["arrival_heading"], 154.779, places=3)    # facing into the cave
        self.assertEqual(mk.deg(0.0), 0.0)
        self.assertAlmostEqual(mk.deg(-math.pi / 2), 270.0)

    def test_both_legs_walk_from_where_the_player_stands(self):
        e = self.entry()
        self.assertEqual(e["outside"]["start"], ROUTES["outside"]["route"][0])
        self.assertEqual(e["inside"]["start"], ROUTES["inside"]["route"][0])
        self.assertEqual(e["outside"]["start"], SPAWN)                      # the coc arrival: no teleport to a start
        self.assertEqual(e["travel"], "coc FO4Core_RedRocketSpawn")
        self.assertEqual(e["outside"]["ref"], "05000800")
        self.assertEqual(e["inside"]["cell_id"], "04002338")
        reach = max(math.dist(q, ROUTES["outside"]["route"][0]) for q in ROUTES["outside"]["route"])
        self.assertGreater(e["moved_m"], reach + 10)                        # a far read is the other side of the door
        self.assertEqual(e["route_walk_ms"], 28300 + 10000)

    def test_the_runner_accepts_it(self):
        probes = [{"ref": "05000802", "local": [-985.2571, 1138.5143, 105.0253], "what": "B"},
                  {"ref": "02000800", "local": [-989.2571, 1146.5143, 105.1429], "what": "A"}]
        t = tq.door_test(0, self.entry(probes))
        self.assertEqual(t["kind"], "door_trip")
        self.assertEqual(len(t["outside"]["route"]), 4)
        self.assertEqual(t["inside"]["arrival_heading"], 154.779)
        self.assertEqual([p["ref"] for p in t["probes"]], ["05000802", "02000800"])
        self.assertGreater(tq.step_timeout(t), 0)

    def test_probe_ids_follow_the_doors(self):
        self.assertEqual([p[0] for p in mk.PROBES], ["000802", "000803"])
        self.assertEqual([p[2] for p in mk.PROBES], [True, False])
        for _pid, _edid, _pers, pos, _what in mk.PROBES:                     # in the probe cell (100 m cells)
            self.assertEqual((math.floor(pos[0] / 100), math.floor(pos[1] / 100)), mk.PROBE_CELL)


class CaveCore64cLinkTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="cave64c_")
        self.addCleanup(shutil.rmtree, self.d, True)
        self.core = os.path.join(self.d, "core")
        os.makedirs(os.path.join(self.core, "Data", "meshes"))
        for rel, body in (("FO4TerrainCore.esm", b"TES4core"), (os.path.join("Data", "meshes", "a.nif"), b"x" * 10),
                          (os.path.join("Data", "b.dds"), b"y" * 3)):
            with open(os.path.join(self.core, rel), "wb") as f:
                f.write(body)

    def test_link_tree_makes_hard_links_and_keeps_them(self):
        out = os.path.join(self.d, "slice")
        os.makedirs(out)
        self.assertEqual(mk.link_tree(os.path.join(self.core, "Data"), os.path.join(out, "Data")), (2, 0))
        self.assertEqual(mk.link_tree(os.path.join(self.core, "Data"), os.path.join(out, "Data")), (0, 2))
        self.assertTrue(os.path.samefile(os.path.join(out, "Data", "meshes", "a.nif"),
                                         os.path.join(self.core, "Data", "meshes", "a.nif")))
        self.assertEqual(mk.link_file(os.path.join(self.core, "FO4TerrainCore.esm"),
                                      os.path.join(out, "FO4TerrainCore.esm")), "linked")
        # the manifest of the links equals the manifest of the originals (hard links share size and time)
        self.assertEqual(mk.data_manifest(out, ["FO4TerrainCore.esm"]),
                         mk.data_manifest(self.core, ["FO4TerrainCore.esm"]))
        self.assertEqual(sorted(mk.data_manifest(out)), ["Data/b.dds", "Data/meshes/a.nif"])

    def test_a_different_file_is_replaced_by_the_link(self):
        out = os.path.join(self.d, "slice")
        os.makedirs(out)
        with open(os.path.join(out, "FO4TerrainCore.esm"), "wb") as f:
            f.write(b"stale")
        self.assertEqual(mk.link_file(os.path.join(self.core, "FO4TerrainCore.esm"),
                                      os.path.join(out, "FO4TerrainCore.esm")), "linked")
        with open(os.path.join(out, "FO4TerrainCore.esm"), "rb") as f:
            self.assertEqual(f.read(), b"TES4core")


if __name__ == "__main__":
    unittest.main()
