"""Stairs route planning with the offline walk (scripts/game/routes.py + fo4sf.walksim) on synthetic collision: the
reference rotation order, buried feet under floor slabs, lanes around walls, starts closer to the foot, walks that
end at a drop, trivial rises, doors and movable objects, converted helper crossings and their probes. No game data."""
import importlib.util
import json
import math
import os
import sys
import tempfile
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


def library_helper():
    """[(FO4 triangle, converted triangle)] of a 45-degree, 0.1 m thick helper slab rising 3.66 m along +y from y 0 (the
    library's BldDecoSmStairs03 / StairsBlock03), the converted one flattened as the converter does."""
    pts = [(-1.83, 0, 0), (1.83, 0, 0), (1.83, 3.66, 3.66), (-1.83, 3.66, 3.66),
           (-1.83, 0.1, -0.1), (1.83, 0.1, -0.1), (1.83, 3.76, 3.56), (-1.83, 3.76, 3.56)]
    tris = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6)]
    with patch.object(routes, "collision_bodies", return_value=[(routes.STAIRHELPER, pts, tris)]):
        return routes.helper_pairs(None)


class HelperCrossingTests(unittest.TestCase):
    """QA on PR #111: batch_full 0002 / 0003 stopped where the flattened helper comes up through the gallery slab, 0.43 m
    from where FO4's does; the planner now marks routes that cross such a place and plans a probe past it."""
    SLAB = 1.69

    def test_a_route_over_a_slab_meets_the_flattened_crossing_first(self):
        pairs = library_helper()
        c = routes.helper_crossing(pairs, (0.0, 0.89, self.SLAB + 0.3), 0.0, 4.0, self.SLAB)
        self.assertIsNotNone(c)
        self.assertAlmostEqual(c["fo4_at"][1], 1.69, delta=0.03)        # FO4's 45-degree face: y = z
        flat_y = 3.66 - (3.66 - self.SLAB) / math.tan(math.radians(c["slope"]))
        self.assertAlmostEqual(c["at"][1], flat_y, delta=0.03)
        self.assertGreater(c["moved"], 0.3)                               # the walk meets the converted one first
        self.assertAlmostEqual(c["at"][2], self.SLAB)
        self.assertGreater(c["depth"], 1.6)
        self.assertLess(c["slope"], meshcollision.STAIR_HELPER_MAX_SLOPE + 1.0)

    def test_a_gentle_helper_and_a_toe_on_the_floor_are_not_marked(self):
        gentle = [(t, t) for t in ramp(-1.83, 1.83, 0, 4.0, 0.0, 2.0)]   # 27 degrees: the converter leaves it
        self.assertIsNone(routes.helper_crossing(gentle, (0.0, -0.5, 1.3), 0.0, 4.0, 1.0))
        on_floor = [(t, t) for t in ramp(-1.83, 1.83, 0, 4.0, 0.0, 2.0)]
        self.assertIsNone(routes.helper_crossing(on_floor, (0.0, -0.8, 0.3), 0.0, 4.0, 0.0))
        self.assertIsNone(routes.helper_crossing([], (0.0, 0.0, 0.3), 0.0, 4.0, 0.0))

    def test_plan_marks_the_crossing_and_plans_a_probe_past_it(self):
        pairs = library_helper()
        parts = [("slab", floor(-3, 3, -4, 2.2, self.SLAB)), ("stair", [b for _, b in pairs]),
                 ("upper", floor(-3, 3, 3.66, 8, 3.66))]
        with patch.object(routes, "neighbour_ground", return_value=ground_of(parts[0], parts[2])), \
                patch.object(routes, "walk_scene", return_value=scene(*parts)):
            found, why = routes.plan_stairs({"refs": []}, None, sorted({v for a, _ in pairs for v in a}), None, {}, {},
                                            pairs)
        self.assertIsNotNone(found, why)
        self.assertIn("helper_crossing", found)
        c = found["helper_crossing"]
        runup, probe = found["_probes"]
        self.assertEqual(probe.get("probe"), "past_crossing", probe)
        self.assertEqual(runup.get("probe"), "runup", runup)
        self.assertAlmostEqual(c["at"][1] - runup["start"][1], routes.PROBE_RUNUP, delta=0.02)
        self.assertAlmostEqual(runup["start"][2], self.SLAB + 0.3, delta=0.02)
        self.assertEqual(runup["expect"], found["expect"])
        self.assertGreater(runup["walk_ms"], found["walk_ms"])
        self.assertAlmostEqual(probe["start"][1] - c["at"][1], routes.PROBE_PAST, delta=0.02)
        top = routes.surface_z([b for _, b in pairs if routes._faces_up(b)], 0.0, probe["start"][1], 1e9)
        self.assertAlmostEqual(probe["start"][2], top + 0.3, delta=0.02)
        self.assertEqual(probe["expect"]["high"], found["expect"]["high"])
        self.assertEqual(found["heading"], 0.0)


class MovableTests(unittest.TestCase):
    """QA on PR #111: the walk leaves movable objects out, so lanes that meet one are listed and taken last."""
    LO, HI = (0.0, 0.0, 0.0), (0.0, 4.0, 2.0)
    PLACED = [(-1.83, 0.0, 0.0), (1.83, 0.0, 0.0), (-1.83, 4.0, 2.0), (1.83, 4.0, 2.0)]

    def plan(self, boxes):
        parts = [("lower", floor(-3, 3, -4, 0, 0.0)), ("stair", ramp(-1.83, 1.83, 0, 4, 0.0, 2.0)),
                 ("upper", floor(-3, 3, 4, 8, 2.0))]
        refs = [{"formkey": f"00000{k}:Fallout4.esm", "model": "Clutter\\Box.nif", "pos": [x * 70, y * 70, 0],
                 "rot": [0, 0, 0], "scale": 1} for k, (x, y) in enumerate(boxes)]
        corners = [(-0.15, -0.15, 0.0), (0.15, 0.15, 0.3)]
        with patch.object(routes, "neighbour_ground", return_value=ground_of(*parts)), \
                patch.object(routes, "walk_scene", return_value=scene(*parts)), \
                patch.object(routes, "_all_collision_points", return_value=corners):
            return routes.plan_stairs({"refs": refs}, None, self.PLACED, None,
                                      {"meshes\\clutter\\box.nif": {"movable": {"mass_kg": 10}}}, {})

    def test_a_box_on_the_centre_line_moves_the_lane_and_is_listed_when_near(self):
        found, why = self.plan([(0.0, -0.3)])
        self.assertIsNotNone(found, why)
        self.assertNotEqual(found["lane"], 0.0)
        for d in found.get("movable_near", {}).values():
            self.assertGreaterEqual(d, routes.MOVABLE_TOUCH)

    def test_boxes_on_every_lane_keep_the_first_lane_and_list_them(self):
        found, why = self.plan([(x / 4.0, -0.3) for x in range(-8, 9)])
        self.assertIsNotNone(found, why)
        self.assertEqual(found["lane"], 0.0)
        self.assertLess(min(found["movable_near"].values()), routes.MOVABLE_TOUCH)

    def test_no_movable_nothing_listed(self):
        found, why = self.plan([])
        self.assertEqual(found["lane"], 0.0)
        self.assertNotIn("movable_near", found)


class RouteFileTests(unittest.TestCase):
    def test_route_entries_carry_emerges_crossing_and_probes(self):
        # QA on PR #111: the page said route files gain "emerges"; main() never wrote it
        pairs = library_helper()
        found = {"start": [0.0, 0.89, 1.99], "heading": 0.0, "walk_ms": 900, "lane": 0.0, "buried_fraction": 0.46,
                 "emerges": 0.46, "expect": {"low": [0, 1.69, 1.69], "high": [0, 3.66, 3.66], "min_rise": 1.58},
                 "sim_end": [0.0, 4.26, 3.66], "helper_crossing": {"at": [0, 1.31, 1.69]},
                 "_probes": [{"probe": "runup", "skipped": "no floor for the run-up"},
                             {"probe": "past_crossing", "start": [0, 1.91, 2.3], "heading": 0.0, "walk_ms": 630,
                              "expect": {}, "sim_end": [0, 4.6, 3.66]}]}
        cell = {"cell": "CellA", "refs": [{"formkey": "000001:Fallout4.esm", "model": "Stairs03.nif", "pos": [0, 0, 0],
                                            "rot": [0, 0, 0], "scale": 1}]}
        d = tempfile.mkdtemp()
        paths = {k: os.path.join(d, k) for k in ("cell.json", "manifest.json", "out.json", "probes.json")}
        with open(paths["cell.json"], "w") as f:
            json.dump(cell, f)
        with open(paths["manifest.json"], "w") as f:
            json.dump({"items": [{"source": "meshes\\stairs03.nif"}]}, f)
        with patch.object(routes.pipeline, "Fo4Archives"), patch.object(routes.nif, "parse"), \
                patch.object(routes, "ramp_points", return_value=([(0, 0, 0), (0, 3.66, 3.66)], "stairhelper")), \
                patch.object(routes, "model_collision", return_value={"helper": [], "walk": [], "solid": []}), \
                patch.object(routes, "plan_stairs", return_value=(dict(found), None)):
            routes.main(["--fo4-data", d, "--cell-json", paths["cell.json"], "--manifest", paths["manifest.json"],
                         "--out", paths["out.json"], "--probes-out", paths["probes.json"]])
        with open(paths["out.json"]) as f:
            route = json.load(f)["routes"][0]
        self.assertEqual(route["emerges"], 0.46)
        self.assertEqual(route["helper_crossing"], found["helper_crossing"])
        self.assertNotIn("_probes", route)
        with open(paths["probes.json"]) as f:
            pf = json.load(f)
        probes = pf["routes"]
        self.assertEqual([p["probe"] for p in probes], ["through_crossing", "past_crossing"])
        self.assertEqual(pf["probes_skipped"], [{"ref": "000001:Fallout4.esm", "model": "Stairs03.nif", "probe": "runup",
                                                 "skipped": "no floor for the run-up"}])
        self.assertEqual(probes[0]["start"], route["start"])
        self.assertEqual(probes[1]["start"], [0, 1.91, 2.3])
        self.assertEqual(probes[1]["ref"], route["ref"])
        self.assertTrue(pairs)


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
