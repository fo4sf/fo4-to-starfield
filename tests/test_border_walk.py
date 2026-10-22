"""scripts/bridge/border_walk.py: straight border walks from the Red Rocket arrival and their report (synthetic)."""
import hashlib
import io
import json
import math
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "bridge"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import border_walk as bw  # noqa: E402
import testqueue  # noqa: E402

SPAWN = [-989.0, 1146.0, 12.0]


class RayTests(unittest.TestCase):
    def test_headings_are_compass_bearings(self):
        for deg, want in ((0, (0, 1)), (90, (1, 0)), (180, (0, -1)), (270, (-1, 0))):
            dx, dy = bw.heading_xy(deg)
            self.assertAlmostEqual(dx, want[0])
            self.assertAlmostEqual(dy, want[1])

    def test_a_ray_is_clipped_to_the_terrain(self):
        x, y, t = bw.ray_end(SPAWN, 0, 1200, (-3100, -3100, 3100, 1500))
        self.assertAlmostEqual(y, 1500)
        self.assertAlmostEqual(t, 354)
        self.assertAlmostEqual(x, SPAWN[0])
        x, y, t = bw.ray_end(SPAWN, 270, 1200, (-3100, -3100, 3100, 3100))
        self.assertAlmostEqual(t, 1200)

    def test_points_are_at_most_a_step_apart_and_end_on_the_end(self):
        pts = bw.ray_points(SPAWN, (SPAWN[0], SPAWN[1] + 100))
        self.assertEqual(len(pts), math.ceil(100 / bw.WP_STEP_M))
        self.assertAlmostEqual(pts[-1][1], SPAWN[1] + 100)
        gaps = [math.dist(a, b) for a, b in zip([tuple(SPAWN[:2])] + pts, pts)]
        self.assertTrue(all(g <= bw.WP_STEP_M + 1e-9 for g in gaps))

    def test_an_entry_is_a_valid_walk_test(self):
        with tempfile.TemporaryDirectory() as d:
            g = os.path.join(d, "ground_h000.json")
            with open(g, "w") as f:
                f.write("{}")
            sha = hashlib.sha256(open(g, "rb").read()).hexdigest()
            wps = [[SPAWN[0], SPAWN[1], SPAWN[2], 3.0, 1]] + [[SPAWN[0], SPAWN[1] + 12 * k, 10.0, 3.0, 0]
                                                              for k in range(1, 10)] + [[SPAWN[0], SPAWN[1] + 120, 10.0, 5.0, 1]]
            e = bw.walk_entry("border_h000", SPAWN, 0, wps, 120.0, "ground_h000.json", sha)
            t = testqueue.walk_test(0, e, d)
            self.assertEqual(t["travel"], f"coc {bw.SPAWN_COC}")
            self.assertEqual(t["offroute_m"], bw.OFFROUTE_M)
            self.assertTrue(t["fresh"])


class ImportTests(unittest.TestCase):
    def test_plan_uses_the_terrain_walk_route(self):
        # PC run 2026-10-22: scripts/game/walk_route.py shadowed the terrain one on sys.path
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("numpy not installed")
        wr = bw.terrain_walk_route()
        self.assertTrue(wr.__file__.replace("\\", "/").endswith("scripts/terrain/walk_route.py"))
        for name in ("tg", "core_world", "ground_file", "sha256"):
            self.assertTrue(hasattr(wr, name), name)


class ReportTests(unittest.TestCase):
    ARRIVAL = [-2189.0, -1554.0, 12.0]
    LEGS = [{"n": 1, "used": "-2189.0 -1540.0 12.0"}, {"n": 2, "used": "-2189.0 -1000.0 30.0"},
            {"n": 3, "used": "-2189.0 -908.0 31.0", "popup": "BOUNDARY REACHED", "shot": "walk_003.png"},
            {"n": 4, "used": "-2189.0 -950.0 31.0"}]

    def report(self, verdict):
        """(printed text, CSV rows, SVG text) of a one-ray queue whose attempt a1 saw the popup and was judged
        `verdict` (verdict, class) in results.jsonl (None: no row)."""
        tid = "0000_walk_border_h000"
        with tempfile.TemporaryDirectory() as d:
            plan, queue = os.path.join(d, "plan"), os.path.join(d, "queue")
            os.makedirs(plan)
            os.makedirs(os.path.join(queue, "tests", tid, "a1"))

            def dump(obj, *path):
                with open(os.path.join(*path), "w") as f:
                    json.dump(obj, f)
            dump({"spawn_local": SPAWN, "rays": [{"label": "border_h000"}]}, plan, "rays.json")
            dump({"tests": [{"id": tid, "kind": "walk", "ref": "border_h000"}]}, queue, "queue.json")
            obs = {"spawn_read": " ".join(map(str, self.ARRIVAL)), "legs": self.LEGS, "walk_stopped": "boundary"}
            dump(obs, queue, "tests", tid, "a1", "obs.json")
            stale = os.path.join(queue, "tests", tid, "a1_interrupted_20261022T120000")
            os.makedirs(stale)                              # Codex on #444: a renamed interrupted attempt never counts
            dump(dict(obs, legs=self.LEGS[:1], walk_stopped="stopped"), stale, "obs.json")
            if verdict:
                dump({"id": tid, "attempt": 1, "verdict": verdict[0], "class": verdict[1]}, queue, "results.jsonl")
            svg, out = os.path.join(d, "b.svg"), os.path.join(d, "b.csv")
            with redirect_stdout(io.StringIO()) as s:
                bw.main(["report", "--queue", queue, "--plan", plan, "--svg", svg, "--csv", out,
                         "--extra", "owner wall:-2606.46,-907.91"])
            with open(out) as f:
                rows = [r.split(",") for r in f.read().splitlines()]
            with open(svg) as f:
                return s.getvalue(), rows, f.read()

    def test_a_boundary_stop_reports_the_last_read_before_the_popup(self):
        text, rows, svg = self.report(("FAIL", "BOUNDARY"))
        self.assertEqual(len(rows), 2)
        row = rows[1]
        self.assertEqual(row[1], "boundary")
        self.assertEqual(float(row[3]), 646.0)             # distance from the arrival to the popup's read
        self.assertEqual(float(row[8]), round(-908.0 - (self.ARRIVAL[1] - SPAWN[1]), 1))   # local y
        self.assertIn("walk_003.png", row)
        self.assertEqual(row[-1], "FAIL BOUNDARY")
        self.assertIn("owner wall", svg)
        self.assertIn('stroke="#c0392b" stroke-width="3"', svg)                          # the red cross

    def test_a_popup_the_runner_did_not_judge_a_boundary_is_no_cross(self):
        # Codex on #444: an INCONCLUSIVE attempt's popup is evidence the runner rejected
        for verdict in (("INCONCLUSIVE", "INSTALL"), None):
            text, rows, svg = self.report(verdict)
            self.assertEqual(rows[1][1], "boundary_unconfirmed")
            self.assertEqual(rows[1][-1], " ".join(verdict) if verdict else "UNJUDGED")
            self.assertNotIn('stroke-width="3"', svg)

if __name__ == "__main__":
    unittest.main()
