"""Stairs route planning with the offline walk (scripts/game/routes.py + fo4sf.walksim) on synthetic collision: the
reference rotation order, buried feet under floor slabs, lanes around walls, starts closer to the foot, walks that
end at a drop, trivial rises, doors and movable objects. No game data."""
import importlib.util
import math
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fo4sf import meshcollision, walksim  # noqa: E402
from test_walksim import box, floor, ramp  # noqa: E402

spec = importlib.util.spec_from_file_location("routes_lanes", ROOT / "scripts" / "game" / "routes.py")
routes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routes)


def scene(*parts):
    tris, owners = [], []
    for name, ts in parts:
        tris += ts
        owners += [name] * len(ts)
    return walksim.Scene(tris, owners)


def ground_of(*parts):
    """routes.neighbour_ground's ground(x, y, below) over the walkable (upward) faces of `parts`."""
    tris = [t for _, ts in parts for t in ts]
    up = []
    for a, b, c in tris:
        u = [b[i] - a[i] for i in range(3)]
        v = [c[i] - a[i] for i in range(3)]
        if u[0] * v[1] - u[1] * v[0] > 0:
            up.append((a, b, c))
    return lambda x, y, below: routes.surface_z(up, x, y, below)


def apply(m, v):
    return tuple(sum(m[3 * i + k] * v[k] for k in range(3)) for i in range(3))


class RotationTests(unittest.TestCase):
    def test_pure_z_rotation_is_clockwise(self):
        m = routes.ref_matrix((0.0, 0.0, math.radians(90)))
        for got, want in zip(apply(m, (1, 0, 0)), (0, -1, 0)):
            self.assertAlmostEqual(got, want)

    def test_tilted_reference_turns_about_z_first(self):
        # R = Rx(-x) Ry(-y) Rz(-z): +x turned 90 degrees about Z goes to -y, then 90 about X takes -y to +z. The old
        # X-first order (Rz Ry Rx) would leave it at -y (the X turn first does nothing to +x).
        m = routes.ref_matrix((math.radians(90), 0.0, math.radians(90)))
        for got, want in zip(apply(m, (1, 0, 0)), (0, 0, 1)):
            self.assertAlmostEqual(got, want, places=6)


class EmergeTests(unittest.TestCase):
    LO, HI = (0.0, 0.0, 0.0), (0.0, 3.66, 3.66)            # a 45-degree 3.66 m flight (BldDecoSmStairs03)

    def test_a_slab_below_player_height_buries_the_foot(self):
        # the library gallery: a floor 1.69 m over the foot, ending where the flight comes through it
        g = ground_of(("slab", floor(-2, 2, -3, 1.9, 1.69)))
        t, z = routes.emerge(self.LO, self.HI, g)
        self.assertAlmostEqual(t, 1.69 / 3.66, delta=0.06)
        self.assertAlmostEqual(z, 1.69)

    def test_a_floor_at_the_foot_keeps_it(self):
        g = ground_of(("floor", floor(-2, 2, -3, 0.2, 0.0)), ("high", floor(-2, 2, -3, 0.2, 2.5)))
        self.assertEqual(routes.emerge(self.LO, self.HI, g)[0], 0.0)

    def test_a_flight_hanging_in_the_void_starts_where_its_floor_covers_it(self):
        # nothing under the flight; the floor it ends on reaches back over its lower half (BldDecoSmStairs01 0EF6A4)
        g = ground_of(("upper", floor(-2, 2, 1.0, 6, 3.66)))
        t, z = routes.emerge(self.LO, self.HI, g)
        self.assertGreater(t, 0.9)


class LaneTests(unittest.TestCase):
    """check_lane / plan_stairs on a 3.66 m wide, 2 m high flight rising along +y (27 degrees, a helper ramp)."""
    LO, HI = (0.0, 0.0, 0.0), (0.0, 4.0, 2.0)
    PLACED = [(-1.83, 0.0, 0.0), (1.83, 0.0, 0.0), (-1.83, 4.0, 2.0), (1.83, 4.0, 2.0)]

    def flight(self, *extra, beyond=True):
        parts = [("lower", floor(-3, 3, -4, 0, 0.0)), ("stair", ramp(-1.83, 1.83, 0, 4, 0.0, 2.0))]
        if beyond:
            parts.append(("upper", floor(-3, 3, 4, 8, 2.0)))
        return parts + list(extra)

    def plan(self, parts):
        with patch.object(routes, "neighbour_ground", return_value=ground_of(*parts)), \
                patch.object(routes, "walk_scene", return_value=scene(*parts)):
            return routes.plan_stairs({"refs": []}, None, self.PLACED, None, {}, {})

    def test_a_clear_flight_is_planned_on_its_centre_line(self):
        found, why = self.plan(self.flight())
        self.assertIsNone(why)
        self.assertEqual(found["lane"], 0.0)
        self.assertEqual(found["start"], [0.0, -0.8, 0.3])
        self.assertEqual(found["heading"], 0.0)
        self.assertEqual(found["expect"]["min_rise"], 1.6)
        self.assertEqual(found["walk_ms"], int(1000 * (0.8 + 4.0 + routes.OVERSHOOT) / routes.RUN_SPEED))
        self.assertNotIn("tight", found)

    def test_a_wall_along_the_centre_line_moves_the_lane(self):
        # the library's wall plug and closed double door standing on the middle of BldDecoSmStairs03 0EBECE
        found, why = self.plan(self.flight(("wall", box(-0.1, 0.1, -1.0, 6.0, 0.0, 4.0))))
        self.assertIsNotNone(found, why)
        self.assertGreaterEqual(abs(found["lane"]), 0.1 + walksim.PLAYER_RADIUS + routes.CLEARANCES[0])

    def test_a_slot_narrower_than_the_player_is_skipped(self):
        # walls 0.6 m apart across the whole flight width: no lane at all
        parts = self.flight(("left", box(-3, -0.3, -4, 8, 0, 4)), ("right", box(0.3, 3, -4, 8, 0, 4)))
        found, why = self.plan(parts)
        self.assertIsNone(found)
        self.assertIn("start blocked", why)

    def test_debris_across_every_lane_skips_the_flight(self):
        found, why = self.plan(self.flight(("chunk", box(-3, 3, 1.5, 1.9, 0.0, 3.0))))
        self.assertIsNone(found)
        self.assertTrue(why.startswith("stopped by chunk"), why)

    def test_a_top_that_ends_at_a_drop_shortens_the_walk(self):
        # the upper floor starts 0.9 m after the top: walking 0.6 m past it would leave the player over the gap
        parts = self.flight(("far", floor(-3, 3, 4.9, 8, 2.0)), beyond=False)
        found, why = self.plan(parts)
        if found is not None:
            walked = found["walk_ms"] / 1000 * routes.RUN_SPEED
            self.assertLessEqual(walked + routes.EDGE_MARGIN, 0.8 + 4.0 + 0.25)
        else:
            self.assertIn("drop", why)

    def test_a_tight_flight_is_marked(self):
        # walls 0.38 m from the centre line on both sides: only the bare capsule fits (ShackStairs01)
        parts = self.flight(("left", box(-3, -0.38, -4, 8, 0, 4)), ("right", box(0.38, 3, -4, 8, 0, 4)))
        found, why = self.plan(parts)
        self.assertIsNotNone(found, why)
        self.assertTrue(found.get("tight"))
        self.assertEqual(found["lane"], 0.0)

    def test_a_rail_end_at_the_start_moves_the_start_closer(self):
        # a rail across the lane 0.8 m before the foot (Cambridge HitFloorEdge02Stairs01 16D87C)
        found, why = self.plan(self.flight(("rail", box(-3, 3, -1.0, -0.75, 0.6, 1.0))))
        self.assertIsNotNone(found, why)
        self.assertGreater(found["start"][1], -0.8)

    def test_a_flight_rising_less_than_min_rise_is_no_stairs_test(self):
        low = [(-1.83, 0.0, 0.0), (1.83, 0.0, 0.0), (-1.83, 0.6, 0.15), (1.83, 0.6, 0.15)]
        parts = [("floor", floor(-3, 3, -4, 6, 0.0)), ("step", ramp(-1.83, 1.83, 0, 0.6, 0.0, 0.15))]
        with patch.object(routes, "neighbour_ground", return_value=ground_of(*parts)), \
                patch.object(routes, "walk_scene", return_value=scene(*parts)):
            found, why = routes.plan_stairs({"refs": []}, None, low, None, {}, {})
        self.assertIsNone(found)
        self.assertTrue(why.startswith("rises 0.15 m"), why)

    def test_a_foot_under_a_slab_starts_on_the_slab(self):
        # the 45-degree library flight under the gallery slab: the start moves up onto the slab
        placed = [(-1.83, 0.0, 0.0), (1.83, 0.0, 0.0), (-1.83, 3.66, 3.66), (1.83, 3.66, 3.66)]
        parts = [("slab", floor(-3, 3, -4, 1.9, 1.69)), ("stair", ramp(-1.83, 1.83, 0, 3.66, 0.0, 3.66)),
                 ("upper", floor(-3, 3, 3.66, 8, 3.66))]
        with patch.object(routes, "neighbour_ground", return_value=ground_of(("slab", parts[0][1]), parts[2])), \
                patch.object(routes, "walk_scene", return_value=scene(*parts)):
            found, why = routes.plan_stairs({"refs": []}, None, placed, None, {}, {})
        self.assertIsNotNone(found, why)
        self.assertAlmostEqual(found["start"][2], 1.69 + 0.3, places=2)
        self.assertAlmostEqual(found["expect"]["low"][2], 1.69, delta=0.1)
        self.assertGreater(found["buried_fraction"], 0.4)


class SceneTests(unittest.TestCase):
    def test_open_doors_and_movable_objects_move_aside(self):
        self.assertTrue(routes.moves_aside({"type": "Door", "open_by_default": True}, {"door": {}}))
        self.assertFalse(routes.moves_aside({"type": "Door", "open_by_default": False}, {"door": {}}))
        self.assertTrue(routes.moves_aside({"type": "MovableStatic"}, {"movable": {"mass_kg": 3}}))
        self.assertFalse(routes.moves_aside({"type": "Static"}, {}))

    def test_a_model_whose_collision_lies_far_from_its_origin_is_found(self):
        # VltGearDoorStairs01's collision is 16-22 m from its origin
        far = {"walk": [], "solid": [((20.0, -1, 0), (22.0, -1, 0), (22.0, 1, 1.0))], "reach": 22.1}
        cell = {"refs": [{"formkey": "A", "model": "Far.nif", "pos": [0, 0, 0], "rot": [0, 0, 0], "scale": 1}]}
        with patch.object(routes, "model_collision", return_value=far):
            got = routes.placed_triangles(cell, (21.0, 0.0), 2.0, None, {"meshes\\far.nif": {}}, {}, "solid")
        self.assertEqual(len(got), 1)

    def test_steep_helpers_are_flattened_as_the_converter_does(self):
        # a 46-degree helper slab (V111HallStairs01 / BldWoodPSmStairsHalfTiny03) becomes 40 degrees in the build
        pts = [(-1, 0, 0), (1, 0, 0), (1, 1.85, 1.93), (-1, 1.85, 1.93),
               (-1, 0, -0.1), (1, 0, -0.1), (1, 1.85, 1.83), (-1, 1.85, 1.83)]
        tris = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6)]
        with patch.object(routes, "collision_bodies", return_value=[(routes.STAIRHELPER, pts, tris)]):
            solid = routes.solid_triangles(None)
        verts = {v for t in solid for v in t}
        lo, hi = routes.ends(list(verts))
        slope = math.degrees(math.atan2(hi[2] - lo[2], math.hypot(hi[0] - lo[0], hi[1] - lo[1])))
        self.assertLessEqual(slope, meshcollision.STAIR_HELPER_MAX_SLOPE + 1.0)
        self.assertAlmostEqual(max(v[2] for v in verts), 1.93)


if __name__ == "__main__":
    unittest.main()
