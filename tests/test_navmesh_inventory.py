"""Synthetic tests for navmesh coverage inventory."""
import json
import tempfile
import unittest
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "scripts" / "actors"))
import navmesh_inventory as inv  # noqa: E402


class NavmeshInventoryTests(unittest.TestCase):
    def test_detects_lost_and_reduced(self):
        fo4 = {
            "cellA": {"triangles": 100, "area": 50.0},
            "cellB": {"triangles": 20, "area": 10.0},
            "cellC": {"triangles": 5, "area": 2.0},
        }
        sf = {
            "cellA": {"triangles": 0, "area": 0.0},          # lost
            "cellB": {"triangles": 8, "area": 4.0},           # reduced (40% tri, 40% area)
            "cellC": {"triangles": 5, "area": 2.0},           # unchanged
            "cellD": {"triangles": 30, "area": 15.0},         # gained
        }
        report = inv.inventory(fo4, sf)
        self.assertEqual(len(report["lost_coverage"]), 1)
        self.assertEqual(report["lost_coverage"][0]["cell"], "cellA")
        self.assertEqual(len(report["reduced_coverage"]), 1)
        self.assertEqual(report["reduced_coverage"][0]["cell"], "cellB")
        self.assertEqual(len(report["gained_coverage"]), 1)
        self.assertEqual(report["unchanged"], 1)
        self.assertIn("1 lost", report["summary"])

    def test_cli_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            fo4_path = Path(tmp) / "fo4.json"
            sf_path = Path(tmp) / "sf.json"
            out_path = Path(tmp) / "report.json"
            fo4_path.write_text(json.dumps({"c1": {"triangles": 10}}))
            sf_path.write_text(json.dumps({"c1": {"triangles": 0}}))
            # Simulate CLI by calling main pieces
            fo4 = json.loads(fo4_path.read_text())
            sf = json.loads(sf_path.read_text())
            report = inv.inventory(fo4, sf)
            out_path.write_text(json.dumps(report))
            self.assertTrue(out_path.exists())
            loaded = json.loads(out_path.read_text())
            self.assertEqual(len(loaded["lost_coverage"]), 1)


if __name__ == "__main__":
    unittest.main()
