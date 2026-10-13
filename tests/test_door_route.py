"""door_route.py (docs/slice/cave-core64c.md): walking routes to a load door on synthetic worlds: walls with a gap,
steps, ledges, the FO4-navmesh oracle and the pulled waypoints."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "slice"))
import door_route as dr  # noqa: E402


def world(boxes=(), floors=(), pits=()):
    """support / blocked_r of a flat floor at z 0 (x, y in -20..20) with
    boxes  [(x0, y0, x1, y1)]: walls 3 m high (a capsule of radius r closer than r to one is blocked),
    floors [(x0, y0, x1, y1, z)]: raised platforms (their top is a floor; their sides block a capsule whose feet are
           more than 0.3 m below the top),
    pits   [(x0, y0, x1, y1)]: no floor at all."""
    def support(x, y, below):
        if not (-20 <= x <= 20 and -20 <= y <= 20) or any(a <= x <= c and b <= y <= d for a, b, c, d in pits):
            return None
        best = (0.0, "floor")
        for a, b, c, d, z in floors:
            if a <= x <= c and b <= y <= d and z <= below and z > best[0]:
                best = (z, "platform")
        return best if best[0] <= below else None

    def near(x, y, r, a, b, c, d):
        dx, dy = max(a - x, 0, x - c), max(b - y, 0, y - d)
        return math.hypot(dx, dy) < r

    def blocked_r(r):
        def blocked(x, y, z):
            out = ["wall" for a, b, c, d in boxes if near(x, y, r, a, b, c, d)]
            out += ["platform side" for a, b, c, d, zz in floors if zz > z + 0.3 and near(x, y, r, a, b, c, d)]
            return out
        return blocked
    return support, blocked_r


BOUNDS = (-20, -20, 20, 20)


class WalkTests(unittest.TestCase):
    def test_a_straight_walk_on_the_floor(self):
        support, br = world()
        ok, pts, why = dr.walk(support, br(0.35), (0, 0), (0, 2), 0.0)
        self.assertTrue(ok, why)
        self.assertEqual(len(pts), 8)                       # every 0.25 m, the start excluded
        self.assertEqual(pts[-1], (0.0, 2.0, 0.0))

    def test_a_wall_stops_it(self):
        support, br = world(boxes=[(-1, 1, 1, 1.2)])
        ok, _pts, why = dr.walk(support, br(0.35), (0, 0), (0, 2), 0.0)
        self.assertFalse(ok)
        self.assertIn("wall", why)

    def test_a_step_too_high_is_not_climbed_a_low_one_is(self):
        support, br = world(floors=[(-1, 1, 1, 3, 0.5)])
        self.assertFalse(dr.walk(support, br(0.35), (0, 0), (0, 2), 0.0)[0])
        support, br = world(floors=[(-1, 1, 1, 3, 0.25)])
        ok, pts, why = dr.walk(support, br(0.35), (0, 0), (0, 2), 0.0)
        self.assertTrue(ok, why)
        self.assertEqual(pts[-1][2], 0.25)

    def test_a_ledge_higher_than_max_drop_is_refused(self):
        support, _br = world(floors=[(-5, -5, 5, 0.5, 1.5)])
        clear = lambda *_: []                               # noqa: E731  (the floor alone: no capsule)
        ok, _pts, why = dr.walk(support, clear, (0, 0), (0, 2), 1.5)
        self.assertFalse(ok)
        self.assertIn("a drop of 1.50 m", why)
        self.assertTrue(dr.walk(support, clear, (0, 0), (0, 2), 1.5, max_drop=2.0)[0])

    def test_no_floor(self):
        support, br = world(pits=[(-1, 1, 1, 1.5)])
        ok, _pts, why = dr.walk(support, br(0.35), (0, 0), (0, 2), 0.0)
        self.assertFalse(ok)
        self.assertIn("no floor", why)


class PlanTests(unittest.TestCase):
    def test_around_a_wall_through_its_gap(self):
        # a wall across y = 0 from x -20 to 20 except a 2 m gap at x 8..10; start south, door north
        support, br = world(boxes=[(-20, -0.1, 8, 0.1), (10, -0.1, 20, 0.1)])
        res = dr.plan(support, br, (0, -6, 0.0), (0, 6, 0.0), BOUNDS, goal_m=2.7, radii=(0.6, 0.35))
        wps = res["waypoints"]
        self.assertIsNotNone(wps, res["tried"])
        self.assertEqual(res["radius"], 0.6)
        self.assertEqual(wps[0], [0, -6, 0.0])
        self.assertLessEqual(math.dist(wps[-1], (0, 6, 0)), 2.7)
        self.assertTrue(any(8 <= p[0] <= 10 and abs(p[1]) <= 1.5 for p in res["nodes"]))   # through the gap
        self.assertLessEqual(len(wps), 5)                                  # pulled taut: a few straight legs
        self.assertTrue(all(ok for _k, ok, _w in dr.replay(support, br(0.6), wps)))
        self.assertEqual(dr.contacts(support, br(0.35), wps), [])
        self.assertAlmostEqual(res["length"], sum(lg["length"] for lg in res["legs"]), places=2)
        self.assertEqual([lg["heading"] for lg in res["legs"]][0], dr.heading(wps[0], wps[1]))

    def test_a_narrow_gap_needs_a_smaller_radius(self):
        support, br = world(boxes=[(-20, -0.1, 8.6, 0.1), (9.4, -0.1, 20, 0.1)])      # 0.8 m gap
        res = dr.plan(support, br, (0, -6, 0.0), (0, 6, 0.0), BOUNDS, radii=(0.6, 0.35))
        self.assertEqual(res["tried"], [(0.6, False), (0.35, True)])
        self.assertEqual(res["radius"], 0.35)

    def test_no_way_at_all(self):
        support, br = world(boxes=[(-20, -0.1, 20, 0.1)])
        res = dr.plan(support, br, (0, -6, 0.0), (0, 6, 0.0), BOUNDS, radii=(0.35,))
        self.assertIsNone(res["waypoints"])
        self.assertEqual(res["tried"], [(0.35, False)])

    def test_up_a_ramp_not_up_a_wall(self):
        # a 1.2 m terrace across the way, reachable by a ramp at x 10..12 (0.2 m per 0.5 m)
        floors = [(-20, 2, 20, 20, 1.2)] + [(10, 2 - 0.5 * (k + 1), 12, 2 - 0.5 * k, 1.2 - 0.2 * (k + 1))
                                            for k in range(6)]
        support, br = world(floors=floors)
        res = dr.plan(support, br, (0, -6, 0.0), (0, 8, 1.2), BOUNDS, radii=(0.35,))
        self.assertIsNotNone(res["waypoints"], res["tried"])
        self.assertTrue(any(9.5 <= p[0] <= 12.5 for p in res["nodes"]))
        self.assertAlmostEqual(res["waypoints"][-1][2], 1.2)

    def test_leaving_a_start_whose_capsule_touches_something(self):
        # four thin posts 0.42 m diagonally from the start: the capsule (0.35 m) of every first sample touches one
        support, br = world(boxes=[(x - 0.02, y - 0.02, x + 0.02, y + 0.02) for x in (-0.3, 0.3) for y in (-6.3, -5.7)])
        self.assertIsNone(dr.plan(support, br, (0, -6, 0.0), (0, 6, 0.0), BOUNDS, radii=(0.35,))["waypoints"])
        res = dr.plan(support, br, (0, -6, 0.0), (0, 6, 0.0), BOUNDS, radii=(0.35,), start_free=0.6)
        self.assertIsNotNone(res["waypoints"])

    def test_a_route_to_a_point_in_front_of_the_door_then_the_walk_at_it(self):
        # the outside leg: the route ends at the XTEL point in front of the door, the runner walks the rest straight
        support, br = world(boxes=[(-20, -0.1, 8, 0.1), (10, -0.1, 20, 0.1)])
        res = dr.plan(support, br, (0, -6, 0.0), (0, 6, 0.0), BOUNDS, goal_m=0.75, radii=(0.35,), target=(0, 2, 0.0))
        self.assertLessEqual(math.dist(res["waypoints"][-1], (0, 2, 0)), 0.75)
        self.assertAlmostEqual(res["end_to_door_m"], math.dist(res["waypoints"][-1], (0, 6, 0)), places=3)
        fw = dr.toward(support, br(0.35), res["waypoints"][-1], (0, 6, 0.0), reach=2.7)
        self.assertTrue(fw["reaches"], fw)
        self.assertLessEqual(fw["to_door_m"], 2.7)
        # a post right in front of the door stops the walk at it before the range: not reached, and why
        support, br = world(boxes=[(-1, 3.4, 1, 3.6)])
        fw = dr.toward(support, br(0.35), (0, 2, 0.0), (0, 6, 0.0), reach=2.7)
        self.assertFalse(fw["reaches"])
        self.assertIn("wall", fw["why"])
        self.assertGreater(fw["to_door_m"], 2.7)

    def test_pull_makes_one_straight_leg_on_an_open_floor(self):
        support, br = world()
        res = dr.plan(support, br, (0.3, -6, 0.0), (4.1, 6, 0.0), BOUNDS, radii=(0.35,))
        self.assertEqual(len(res["waypoints"]), 2)


class NavCoverTests(unittest.TestCase):
    def square(self, x0, y0, x1, y1, z=0.0):
        return [[(x0, y0, z), (x1, y0, z), (x1, y1, z)], [(x0, y0, z), (x1, y1, z), (x0, y1, z)]]

    def test_covered_and_margin(self):
        nav = dr.NavCover(self.square(0, 0, 4, 4) + self.square(4, 0, 8, 1), ztol=1.0)
        self.assertTrue(nav.covered(2, 2, 0.5))
        self.assertFalse(nav.covered(2, 2, 1.5))                          # beyond ztol: another level
        self.assertFalse(nav.covered(6, 2, 0.0))
        self.assertEqual(nav.blocked_at(0.0)(6, 0.5, 0.0), [])
        self.assertEqual(nav.blocked_at(0.6)(6, 0.5, 0.0), ["off the FO4 navmesh"])   # a 1 m strip: no 0.6 m margin
        self.assertEqual(nav.blocked_at(0.4)(6, 0.5, 0.0), [])

    def test_a_route_stays_on_the_navmesh(self):
        # an L of navmesh: south strip then east-west strip; the straight line leaves it, the route does not
        tris = self.square(-1, -8, 1, 1) + self.square(-1, 1, 9, 3) + self.square(7, 3, 9, 9)
        nav = dr.NavCover(tris)
        support, _br = world()
        res = dr.plan(support, nav.blocked_at, (0, -6, 0.0), (8, 8, 0.0), BOUNDS, goal_m=1.0, radii=(0.4, 0.0))
        self.assertIsNotNone(res["waypoints"], res["tried"])
        self.assertEqual(dr.contacts(support, nav.blocked_at(0.0), res["waypoints"]), [])
        both = dr.both(nav.blocked_at(0.0), lambda x, y, z: ["x"] if x > 100 else [])
        self.assertEqual(both(0, 0, 0), [])
        self.assertEqual(both(5, -5, 0), ["off the FO4 navmesh"])


class HelperTests(unittest.TestCase):
    def test_heading(self):
        self.assertEqual(dr.heading((0, 0), (0, 1)), 0.0)
        self.assertEqual(dr.heading((0, 0), (1, 0)), 90.0)
        self.assertEqual(dr.heading((0, 0), (0, -1)), 180.0)
        self.assertEqual(dr.heading((0, 0), (-1, 0)), 270.0)

    def test_lateral_shifts_left_of_the_walk(self):
        out = dr.lateral([[0, 0, 0], [0, 10, 0]], 0.5)
        self.assertEqual(out[0], [0, 0, 0])
        self.assertAlmostEqual(out[1][0], -0.5)                           # walking north, left is west
        self.assertAlmostEqual(out[1][1], 10)

    def test_walk_budget(self):
        self.assertEqual(dr.walk_ms(46.0), 24000)                           # 46 m / 4.6 m/s * 1.6 + 8 s


if __name__ == "__main__":
    unittest.main()
