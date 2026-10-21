"""Synthetic tests for scripts/terrain/arrival_objects.py: what the core placed and skipped around door-exit arrivals.
No game data: objects.json, skipped.json and the arrival_ground rows are invented."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "terrain"))
import arrival_objects  # noqa: E402

OBJECTS = {"world": "W", "edid_prefix": "FO4Core_",
           "bases": [{"model": "fo4port/roof01", "collision": "none"}, {"model": "fo4port/rock01", "collision": "fo4-native"},
                     {"model": "fo4port/door01", "collision": "none"}],
           "refs": [{"src": "000A01:Fallout4.esm", "base": 0, "pos": [100.0, 200.0, 94.0]},          # 0 m from the marker
                    {"src": "000A02:Fallout4.esm", "base": 1, "pos": [110.0, 200.0, 75.0], "scale": 2.0},  # 10 m
                    {"src": "000A03:Fallout4.esm", "base": 1, "pos": [160.0, 200.0, 75.0]}],              # 60 m: far
           "doors": [{"src": "000D01:Fallout4.esm", "edid": "FO4Core_door", "model": "fo4port/door01",
                      "pos": [100.0, 205.0, 95.0], "disabled": 1}]}
GROUND = {"rows": [{"id": "0013_t", "cell_edid": "FortHagen02", "marker": "14.1 m above ground", "got": "1.9 m above ground",
                    "marker_local": [100.0, 200.0, 95.0], "got_local": [100.0, 200.0, 82.9]}]}


class ArrivalObjects(unittest.TestCase):
    def test_lists_nearby_placed_refs_nearest_first_with_collision_and_heights(self):
        found = arrival_objects.read(OBJECTS, {}, GROUND["rows"], 20.0)
        placed = found[0]["placed"]
        self.assertEqual([e["src"] for e in placed], ["000A01:Fallout4.esm", "000D01:Fallout4.esm", "000A02:Fallout4.esm"])
        roof, door, rock = placed
        self.assertEqual((roof["collision"], roof["dz_marker"], roof["dz_got"]), ("none", -1.0, 11.1))
        self.assertEqual((door["class"], door["collision"], door["disabled"]), ("doors", "none", True))   # promoted: matched by model
        self.assertEqual((rock["dist"], rock["scale"]), (10.0, 2.0))

    def test_skipped_refs_come_from_the_fo4_cells_touching_the_radius(self):
        # FO4 cells are 58.5 m: 20 m around x 100 reaches cells 1 and 2 (the edge is at 117 m), around y 200 only cell 3
        skipped = {"refs": [{"formkey": "000B01:Fallout4.esm", "type": "STAT", "model": "a.nif", "exterior_cell": [1, 3],
                             "reason": "not_converted", "detail": "x"},
                            {"formkey": "000B02:Fallout4.esm", "type": "STAT", "model": "b.nif", "exterior_cell": [5, 3],
                             "reason": "not_converted", "detail": "x"},
                            {"formkey": "000B03:Fallout4.esm", "type": "STAT", "model": "c.nif", "exterior_cell": None,
                             "reason": "outside_terrain", "detail": "x"}]}
        self.assertEqual(arrival_objects.cells_touching({"m": (100.0, 200.0, 0.0)}, 20.0), {(1, 3), (2, 3)})
        found = arrival_objects.read(OBJECTS, skipped, GROUND["rows"], 20.0)
        self.assertEqual([s["formkey"] for s in found[0]["skipped"]], ["000B01:Fallout4.esm"])
        self.assertEqual(arrival_objects.cells_touching({"m": (60.0, 200.0, 0.0)}, 5.0), {(0, 3), (1, 3)})

    def test_main_reads_a_core_folder_and_writes_json_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "objects.json"), "w") as f:
                json.dump(OBJECTS, f)
            ground = os.path.join(tmp, "ground.json")
            with open(ground, "w") as f:
                json.dump(GROUND, f)
            out = os.path.join(tmp, "out.json")
            with contextlib.redirect_stdout(io.StringIO()) as text:
                self.assertEqual(arrival_objects.main([tmp, ground, "--json", out]), 0)
            self.assertIn("3 placed within 20.0 m, 0 skipped", text.getvalue())
            with open(out) as f:
                self.assertEqual(len(json.load(f)["rows"][0]["placed"]), 3)
            with self.assertRaises(FileExistsError), contextlib.redirect_stdout(io.StringIO()):
                arrival_objects.main([tmp, ground, "--json", out])


if __name__ == "__main__":
    unittest.main()
