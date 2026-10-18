"""Stair route planning (scripts/game/routes.py) on synthetic collision: what counts as a ramp, and models placed as the
game places them (no scene-root transform)."""
import importlib.util
import math
import os
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fo4sf import fo4collision, nif  # noqa: E402
from test_root_transform import rooted_nif  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "routes_planner", Path(__file__).resolve().parents[1] / "scripts" / "game" / "routes.py")
routes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routes)


def ramp(rise, run, width=1.0, x0=0.0):
    """Two triangles of a straight ramp from (x0, 0, 0) up to (x0, run, rise)."""
    pts = [(x0, 0, 0), (x0 + width, 0, 0), (x0 + width, run, rise), (x0, run, rise)]
    return pts, [(0, 1, 2), (0, 2, 3)]


def bevels():
    """A stairwell railing frame: small 30-degree bevels at the post ends, low and high edges of each bevel stacked
    over the same spot, and the posts 0.9 m tall (PryPlatformInCornerStairs01 in miniature)."""
    pts, tris = [], []
    for cx, cy in ((-1.8, -1.6), (-1.6, -1.75), (1.6, -1.75), (-1.8, 1.9)):
        for z in (0.0, 0.85):                                   # bevel at the foot and at the top of each post
            k = len(pts)
            pts += [(cx, cy, z), (cx + 0.05, cy, z), (cx + 0.05, cy + 0.087, z + 0.05), (cx, cy + 0.087, z + 0.05)]
            tris += [(k, k + 1, k + 2), (k, k + 2, k + 3)]
    return pts, tris


class RampTests(unittest.TestCase):
    def plan(self, *bodies):
        with patch.object(routes, "collision_bodies", return_value=list(bodies)):
            return routes.ramp_points(None)

    def test_a_sloped_ramp_is_a_ramp(self):
        pts, tris = ramp(1.9, 3.0)                              # 32 degrees, like PryCatwalkStairs01
        found, how = self.plan((1, pts, tris))
        self.assertEqual(how, "sloped-collision")
        # ends() averages triangle corners, so a shared corner weighs twice: within a degree of the true slope
        self.assertAlmostEqual(routes.ramp_slope(found), math.degrees(math.atan2(1.9, 3.0)), delta=1.0)

    def test_a_steep_stair_helper_is_still_a_ramp(self):
        pts, tris = ramp(1.93, 1.84)                            # 46 degrees: V111HallStairs01's helper
        found, how = self.plan((routes.STAIRHELPER, pts, tris))
        self.assertEqual(how, "stairhelper")
        self.assertEqual(len(found), 4)

    def test_railing_bevels_are_not_a_ramp(self):
        pts, tris = bevels()
        self.assertGreater(routes.ramp_slope([pts[i] for t in tris for i in t]), 80)
        self.assertEqual(self.plan((1, pts, tris)), ([], routes.NOT_A_RAMP))

    def test_no_sloped_collision_is_no_ramp(self):
        flat = [(0, 0, 0), (1, 0, 0), (1, 1, 0)]
        self.assertEqual(self.plan((1, flat, [(0, 1, 2)])), ([], None))


class FakePackfile:
    """One FO4 body (layer 1) whose convex shape the test supplies."""
    def __init__(self, raw):
        pass

    def objects(self):
        return [(0, "hknpPhysicsSystemData"), (1000, "hknpConvexPolytopeShape")]

    def array(self, offset):
        return 100, 1

    def pointer(self, offset):
        return 1000

    def unpack(self, fmt, offset):
        return (1,)


class PlacedCollisionTests(unittest.TestCase):
    def test_collision_is_placed_without_the_scene_root(self):
        # root turned 180 degrees, collision on a child node 1 m along +y (PryCatwalkStairsEnt02's layout)
        f = nif.parse(rooted_nif(child_t=(0, 70, 0), collision=True))
        shape = ([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])
        with patch.object(routes.hkpackfile, "Packfile", FakePackfile), \
                patch.object(routes.fo4collision, "_convex", return_value=shape):
            bodies = list(routes.collision_bodies(f))
        self.assertEqual(len(bodies), 1)
        layer, pts, tris = bodies[0]
        self.assertEqual(layer, 1)
        for got, want in zip(pts, [(0, 1, 0), (1, 1, 0), (0, 2, 0)]):   # with the root applied: (0,-1), (-1,-1), (0,-2)
            for a, b in zip(got, want):
                self.assertAlmostEqual(a, b, places=6)


if __name__ == "__main__":
    unittest.main()
