"""Separate source CELL-grid facts from LAND evidence and terrain uncertainty."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_placement_world_identity import plugin

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/oracles/placement_frame.py"


class PlacementCellPresenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.core = Path(self.temp.name) / "core.esp"
        self.mission = Path(self.temp.name) / "mission.esp"
        plugin(self.core, ["Starfield.esm"], 0x01000803, land=False, refs=False)
        plugin(self.mission, ["core.esp"], 0x803)

    def run_cli(self, text=False):
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [self.core, self.mission]}
        command = [sys.executable, "-I", "-B", str(SCRIPT), "--core", str(self.core),
                   "--plugin", str(self.mission), "--world-edid", "TestWorld"]
        if not text:
            command += ["--json"]
        result = subprocess.run(command, cwd=self.core.parent, capture_output=True, text=True, timeout=30)
        self.assertEqual(before, {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [self.core, self.mission]})
        self.assertNotIn("Traceback", result.stderr)
        return result

    def test_empty_exterior_cell_is_present_but_terrain_unknown(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(result.stdout)
        row = report["refs"][0]
        self.assertTrue(row["core_cell_record_present"])
        self.assertFalse(row["core_local_land_data_present"])
        self.assertIsNone(row["core_has_coverage"])
        self.assertEqual(row["reason"], "coverage_unknown")
        self.assertEqual(report["core_exterior_cell_grids"], 1)
        self.assertEqual(report["core_coverage_cells"], 0)
        self.assertIn("this core plugin", report["cell_record_basis"])

    def test_missing_core_cell_record_is_distinct_from_unknown_terrain(self):
        plugin(self.mission, ["core.esp"], 0x803, position=(150., 1., 0.), parent=(1, 0))
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        row = json.loads(result.stdout)["refs"][0]
        self.assertFalse(row["core_cell_record_present"])
        self.assertFalse(row["core_local_land_data_present"])
        self.assertIsNone(row["core_has_coverage"])
        self.assertIn("core_cell_record_missing", row["reasons"])
        self.assertIn("coverage_unknown", row["reasons"])
        self.assertNotIn("no_coverage", result.stdout)

    def test_local_land_evidence_and_cell_presence_are_reported_separately(self):
        plugin(self.core, ["Starfield.esm"], 0x01000803, land=True, refs=False)
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        row = json.loads(result.stdout)["refs"][0]
        self.assertTrue(row["core_cell_record_present"])
        self.assertTrue(row["core_local_land_data_present"])
        self.assertTrue(row["core_has_coverage"])

    def test_global_persistent_cell_does_not_count_as_exterior_grid(self):
        plugin(self.core, ["Starfield.esm"], 0x01000803, land=True, refs=False, persistent=True)
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertEqual(report["core_exterior_cell_grids"], 0)
        self.assertFalse(report["refs"][0]["core_cell_record_present"])
        self.assertFalse(report["refs"][0]["core_local_land_data_present"])

    def test_negative_grid_coordinates_use_the_existing_sf_cell_mapping(self):
        plugin(self.core, ["Starfield.esm"], 0x01000803, land=True, refs=False, parent=(-1, 0))
        plugin(self.mission, ["core.esp"], 0x803, position=(-1., 1., 0.), parent=(-1, 0))
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        row = json.loads(result.stdout)["refs"][0]
        self.assertEqual(row["computed_cell"], [-1, 0])
        self.assertTrue(row["core_cell_record_present"])

    def test_wrong_world_and_missing_position_have_unknown_presence(self):
        for masters, fid, pos in [(["Other.esm"], 0x01000803, (1., 1., 0.)),
                                  (["core.esp"], 0x803, None)]:
            with self.subTest(masters=masters, pos=pos):
                plugin(self.mission, masters, fid, position=pos)
                result = self.run_cli()
                self.assertEqual(result.returncode, 1)
                row = json.loads(result.stdout)["refs"][0]
                self.assertIsNone(row["core_cell_record_present"])
                self.assertIsNone(row["core_local_land_data_present"])

    def test_text_output_distinguishes_cell_from_land_data(self):
        result = self.run_cli(text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("core_cell_record_present=True", result.stdout)
        self.assertIn("core_local_land_data_present=False", result.stdout)


if __name__ == "__main__":
    unittest.main()
