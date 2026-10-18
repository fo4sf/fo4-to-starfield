"""Offline player walk (src/fo4sf/walksim.py) on synthetic collision: floors, ramps, walls, one-sided slabs, starts
that overlap something, and edges of drops. No game data."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import walksim  # noqa: E402


def quad(a, b, c, d):
    """Two triangles a-b-c, a-c-d (front face by the winding a -> b -> c)."""
    return [(a, b, c), (a, c, d)]


def floor(x0, x1, y0, y1, z):
    """Upward-facing floor rectangle."""
    return quad((x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z))


def box(x0, x1, y0, y1, z0, z1):
    """Closed box, faces wound to face outwards (as FO4 convex hulls and solid meshes are)."""
    p = lambda i, j, k: ((x0, x1)[i], (y0, y1)[j], (z0, z1)[k])
    return (quad(p(0, 0, 1), p(1, 0, 1), p(1, 1, 1), p(0, 1, 1))        # top, +z
            + quad(p(0, 0, 0), p(0, 1, 0), p(1, 1, 0), p(1, 0, 0))      # bottom, -z
            + quad(p(0, 0, 0), p(1, 0, 0), p(1, 0, 1), p(0, 0, 1))      # -y
            + quad(p(0, 1, 0), p(0, 1, 1), p(1, 1, 1), p(1, 1, 0))      # +y
            + quad(p(0, 0, 0), p(0, 0, 1), p(0, 1, 1), p(0, 1, 0))      # -x
            + quad(p(1, 0, 0), p(1, 1, 0), p(1, 1, 1), p(1, 0, 1)))     # +x


def ramp(x0, x1, y0, y1, z0, z1):
    """Upward-facing ramp rising along +y from z0 at y0 to z1 at y1 (a stair helper's top face)."""
    return quad((x0, y0, z0), (x1, y0, z0), (x1, y1, z1), (x0, y1, z1))


def scene(*parts):
    tris, owners = [], []
    for name, ts in parts:
        tris += ts
        owners += [name] * len(ts)
    return walksim.Scene(tris, owners)


class WalkTests(unittest.TestCase):
    def test_a_ramp_is_climbed(self):
        # 2 m up over 4 m (27 degrees, BldDecoSmStairs01's helper), floors at both ends
        s = scene(("lower", floor(-2, 2, -3, 0, 0.0)), ("ramp", ramp(-2, 2, 0, 4, 0.0, 2.0)),
                  ("upper", floor(-2, 2, 4, 8, 2.0)))
        w = walksim.walk(s, (0, -1, 0.3), 0.0, 6.0)
        self.assertTrue(w["ok_start"])
        self.assertIsNone(w["stopped_by"])
        self.assertAlmostEqual(w["end"][2], 2.0, places=3)
        self.assertGreater(w["end"][1], 4.5)
        self.assertIsNone(w["overhang_at"])

    def test_a_wall_across_the_lane_stops_the_walk(self):
        s = scene(("floor", floor(-3, 3, -3, 6, 0.0)), ("wall", box(-3, 3, 2.0, 2.2, 0.0, 3.0)))
        w = walksim.walk(s, (0, 0, 0.3), 0.0, 5.0)
        self.assertEqual(w["stopped_by"], "wall")
        self.assertAlmostEqual(w["end"][1], 2.0 - walksim.PLAYER_RADIUS, delta=0.11)

    def test_an_angled_wall_is_slid_along(self):
        # a wall at 45 degrees to the heading: collide and slide
        wall = quad((-0.5, 1.5, 0.0), (3.5, 5.5, 0.0), (3.5, 5.5, 3.0), (-0.5, 1.5, 3.0))
        s = scene(("floor", floor(-3, 6, -3, 8, 0.0)), ("wall", wall))
        w = walksim.walk(s, (1.0, 0, 0.3), 0.0, 4.0)
        self.assertGreater(w["walked"], 3.0)
        self.assertGreater(w["end"][0], 1.5)            # pushed sideways along the wall

    def test_a_start_wedged_between_a_wall_and_a_rail_is_blocked(self):
        # the library landing: wall face 0.26 m to one side, rail 0.23 m to the other (a 0.49 m slot)
        s = scene(("floor", floor(-3, 3, -3, 6, 0.0)), ("wall", box(-1.0, -0.26, -3, 3, 0.0, 1.8)),
                  ("rail", box(0.23, 0.46, -1, 1, 0.0, 0.9)))
        w = walksim.walk(s, (0, 0, 0.3), 0.0, 3.0)
        self.assertFalse(w["ok_start"])
        self.assertIsNone(w["end"] and w["stopped_by"])
        self.assertEqual(w["start_by"], ["rail", "wall"])
        self.assertEqual(w["walked"], 0.0)

    def test_a_start_overlapping_one_wall_is_pushed_out(self):
        # the wall face 0.12 m from the teleport point: pushed 0.23 m away, then the walk goes on
        s = scene(("floor", floor(-3, 3, -3, 6, 0.0)), ("wall", box(0.12, 1.0, -3, 6, 0.0, 3.0)))
        w = walksim.walk(s, (0, 0, 0.3), 0.0, 3.0)
        self.assertTrue(w["ok_start"])
        self.assertEqual(w["start_by"], ["wall"])
        self.assertAlmostEqual(w["nudge"], 0.25, delta=0.001)
        self.assertLess(w["start"][0], 0.12 - walksim.PLAYER_RADIUS + 1e-9)
        self.assertGreater(w["walked"], 2.9)

    def test_no_push_when_the_planner_asks_for_a_free_start(self):
        s = scene(("floor", floor(-3, 3, -3, 6, 0.0)), ("wall", box(0.12, 1.0, -3, 6, 0.0, 3.0)))
        w = walksim.walk(s, (0, 0, 0.3), 0.0, 3.0, nudge=0.0)
        self.assertFalse(w["ok_start"])

    def test_clearance_widens_the_capsule(self):
        # a lane 0.38 m from a wall face fits the 0.35 m capsule, not one with 0.1 m clearance
        s = scene(("floor", floor(-3, 3, -3, 6, 0.0)), ("wall", box(0.38, 1.0, -3, 6, 0.0, 3.0)))
        self.assertTrue(walksim.walk(s, (0, 0, 0.3), 0.0, 3.0, nudge=0.0)["ok_start"])
        self.assertFalse(walksim.walk(s, (0, 0, 0.3), 0.0, 3.0, nudge=0.0, clearance=0.1)["ok_start"])

    def test_a_one_sided_slab_lifts_the_player_through(self):
        # a stair rising under a floor slab 1.7 m above its foot (the library's gallery): the player starts under
        # the slab, which it does not touch from below, and is lifted onto it once its centre passes the plane
        s = scene(("ramp", ramp(-2, 2, 0, 4, 0.0, 2.0)), ("under", floor(-2, 2, -3, 0, 0.0)),
                  ("slab", floor(-2, 2, -3, 2.0, 1.7)), ("upper", floor(-2, 2, 4, 8, 2.0)))
        w = walksim.walk(s, (0, -1, 0.3), 0.0, 6.0)
        self.assertTrue(w["ok_start"])
        self.assertAlmostEqual(w["start"][2], 0.0, places=3)        # not lifted at the start
        self.assertGreater(w["lift"], walksim.STEP_UP)

    def test_a_ceiling_is_not_a_floor(self):
        # a downward-facing ceiling tile just under the teleport point is not stood on: the player drops to the floor
        ceiling = [tuple(reversed(t)) for t in floor(-2, 2, -1, 1, 1.9)]
        s = scene(("floor", floor(-3, 3, -3, 6, 0.0)), ("ceiling", ceiling))
        w = walksim.walk(s, (0, 0, 2.0), 0.0, 3.0)
        self.assertTrue(w["ok_start"])
        self.assertAlmostEqual(w["start"][2], 0.0, places=6)
        self.assertEqual(w["lift"], 0.0)

    def test_a_low_ceiling_stops_the_player(self):
        # seen from below, a ceiling 1.2 m up is solid: a 1.8 m player does not fit under it
        ceiling = [tuple(reversed(t)) for t in floor(-2, 2, 1.0, 3.0, 1.2)]
        s = scene(("floor", floor(-3, 3, -3, 6, 0.0)), ("ceiling", ceiling))
        w = walksim.walk(s, (0, 0, 0.3), 0.0, 3.0)
        self.assertEqual(w["stopped_by"], "ceiling")

    def test_the_edge_of_a_hole_is_found(self):
        # a stair top that ends at a 0.9 m gap (BldDecoSmStairs03 0EBECE): the centre passes over the edge
        s = scene(("lower", floor(-2, 2, -3, 0, 0.0)), ("ramp", ramp(-2, 2, 0, 3, 0.0, 2.0)),
                  ("beyond", floor(-2, 2, 3.9, 6, 2.0)))
        w = walksim.walk(s, (0, -1, 0.3), 0.0, 4.4)
        self.assertIsNotNone(w["overhang_at"])
        self.assertAlmostEqual(w["overhang_at"], 4.1, delta=0.15)
        short = walksim.walk(s, (0, -1, 0.3), 0.0, 3.9)
        self.assertIsNone(short["overhang_at"])

    def test_a_seam_between_two_floor_tiles_is_no_edge(self):
        s = scene(("a", floor(-2, 2, -3, 1.0, 0.0)), ("b", floor(-2, 2, 1.04, 6, 0.0)))
        w = walksim.walk(s, (0, -1, 0.3), 0.0, 5.0)
        self.assertIsNone(w["overhang_at"])

    def test_nothing_under_the_start_is_void(self):
        s = scene(("floor", floor(5, 6, 5, 6, 0.0)))
        w = walksim.walk(s, (0, 0, 0.3), 0.0, 3.0)
        self.assertTrue(w["void"])
        self.assertFalse(w["ok_start"])

    def test_push_direction_from_opposite_sides_is_none(self):
        s = scene(("left", box(-1.0, -0.2, -1, 1, 0, 2)), ("right", box(0.2, 1.0, -1, 1, 0, 2)))
        hits = s.blockers(0, 0, 0.0)
        self.assertIsNone(walksim.push_direction(s, hits, (0, 0, 0)))
        one = scene(("right", box(0.2, 1.0, -1, 1, 0, 2)))
        d = walksim.push_direction(one, one.blockers(0, 0, 0.0), (0, 0, 0))
        self.assertAlmostEqual(d[0], -1.0)
        self.assertAlmostEqual(d[1], 0.0)

    def test_a_start_inside_a_thin_wall_is_blocked(self):
        # a capsule centred inside a 0.2 m wall sees only its back faces; the start is still not free
        s = scene(("floor", floor(-3, 3, -3, 6, 0.0)), ("wall", box(-0.1, 0.1, -1, 6, 0.0, 3.0)))
        self.assertEqual(s.blockers(0, 2, 0.0), [])
        self.assertEqual(s.enclosing(0, 2, 0.0), ["wall"])
        w = walksim.walk(s, (0, 2, 0.3), 0.0, 2.0)
        self.assertFalse(w["ok_start"])
        self.assertEqual(w["start_by"], ["wall"])

    def test_a_start_inside_a_big_box_is_blocked(self):
        s = scene(("floor", floor(-9, 9, -9, 9, 0.0)), ("crate", box(-2, 2, -2, 2, 0.0, 3.0)))
        self.assertEqual(s.enclosing(0, 0, 0.0), ["crate"])
        self.assertEqual(s.enclosing(3, 0, 0.0), [])             # beside it: the ray towards it meets its front
        self.assertFalse(walksim.walk(s, (0, 0, 0.3), 0.0, 1.0)["ok_start"])

    def test_a_wall_met_from_behind_pushes_out_on_the_capsule_side(self):
        s = scene(("floor", floor(-3, 3, -3, 6, 0.0)), ("wall", box(-1.0, 0.1, -3, 6, 0.0, 3.0)))
        hits = s.blockers(0.3, 0, 0.0)
        d = walksim.push_direction(s, hits, (0.3, 0, 0.0))
        self.assertGreater(d[0], 0.99)


if __name__ == "__main__":
    unittest.main()
