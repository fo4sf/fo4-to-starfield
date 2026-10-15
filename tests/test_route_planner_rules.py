"""Route planner rules (scripts/game/routes.py): a "stair" model without a helper needs real treads, and double doors
made of two single-leaf references are twins. Synthetic data; no game, no archives."""
import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import routes  # noqa: E402


def quad(x0, x1, y0, y1, z, up=True):
    a, b, c, d = (x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)
    tris = [(0, 1, 2), (0, 2, 3)] if up else [(0, 2, 1), (0, 3, 2)]
    return [a, b, c, d], tris


def steps(n, rise=0.18, depth=0.3):
    bodies = []
    for k in range(n):
        pts, tris = quad(k * depth, (k + 1) * depth, 0.0, 1.2, k * rise)
        bodies.append((1, pts, tris))
    return bodies


class TreadLevelTests(unittest.TestCase):
    def test_five_steps_are_five_levels(self):
        with patch.object(routes, "collision_bodies", return_value=steps(5)):
            self.assertEqual(len(routes.tread_levels(object())), 5)

    def test_railing_has_no_treads(self):
        # a sloped rail top (tilted quad) and a post: nothing flat to stand on
        rail = [(1, [(0, 0, 0), (2, 0, 1.2), (2, 0.1, 1.2), (0, 0.1, 0)], [(0, 1, 2), (0, 2, 3)])]
        with patch.object(routes, "collision_bodies", return_value=rail):
            self.assertEqual(routes.tread_levels(object()), [])

    def test_helper_bodies_and_undersides_do_not_count(self):
        bodies = steps(3) + [(routes.STAIRHELPER, *quad(0, 1, 0, 1, 5.0))] + [(1, *quad(0, 1, 0, 1, 9.0, up=False))]
        with patch.object(routes, "collision_bodies", return_value=bodies):
            self.assertEqual(len(routes.tread_levels(object())), 3)

    def test_heights_within_four_centimetres_merge(self):
        bodies = [(1, *quad(0, 1, 0, 1, 0.0)), (1, *quad(0, 1, 0, 1, 0.03)), (1, *quad(0, 1, 0, 1, 0.5))]
        with patch.object(routes, "collision_bodies", return_value=bodies):
            self.assertEqual(len(routes.tread_levels(object())), 2)


class DoorTwinTests(unittest.TestCase):
    DOOR = {"origin_offset": [0, 0, 0], "anim_graph": "SimpleOpenClose01.agx"}     # as the manifest marks rigged doors
    ITEMS = {"meshes\\doors\\dbdoor.nif": {"door": DOOR}, "meshes\\doors\\single.nif": {"door": DOOR},
             "meshes\\wall.nif": {}}

    def test_two_doors_on_one_spot_are_twins_both_ways(self):
        refs = [{"formkey": "A", "model": "Doors\\DbDoor.nif", "pos": [2048.0, 5312.0, 768.0]},
                {"formkey": "B", "model": "Doors\\DbDoor.nif", "pos": [2048.0, 5312.0, 768.0]},
                {"formkey": "C", "model": "Doors\\Single.nif", "pos": [2048.0, 5400.0, 768.0]},   # 1.3 m away
                {"formkey": "W", "model": "Wall.nif", "pos": [2048.0, 5312.0, 768.0]}]            # not a door
        self.assertEqual(routes.door_twins(refs, self.ITEMS), {"A": "B", "B": "A"})

    def test_within_ten_centimetres_counts(self):
        refs = [{"formkey": "A", "model": "Doors\\DbDoor.nif", "pos": [0.0, 0.0, 0.0]},
                {"formkey": "B", "model": "Doors\\DbDoor.nif", "pos": [6.0, -6.0, 0.0]}]       # 0.086 m in FO4 units
        self.assertEqual(routes.door_twins(refs, self.ITEMS), {"A": "B", "B": "A"})
        refs[1]["pos"] = [8.0, 0.0, 0.0]                                                        # 0.114 m
        self.assertEqual(routes.door_twins(refs, self.ITEMS), {})


if __name__ == "__main__":
    unittest.main()
