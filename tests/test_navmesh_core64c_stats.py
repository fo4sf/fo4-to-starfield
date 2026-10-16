"""Synthetic tests for core64c navmesh stats binning. No game data."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "actors"))
import navmesh_core64c_stats as stats  # noqa: E402
import navmesh_inventory as inv  # noqa: E402


class Core64cStatsTests(unittest.TestCase):
    def test_overlay_fo4_cell_bounds_match_core64c_doc(self):
        lo, hi = stats.overlay_fo4_cell_bounds(-32, 31)
        self.assertEqual((lo, hi), (-55, 54))
        cells = stats.overlay_fo4_cell_set(-32, 31)
        self.assertEqual(len(cells), 110 * 110)
        self.assertIn((-55, -55), cells)
        self.assertIn((54, 54), cells)
        self.assertNotIn((-56, 0), cells)
        self.assertNotIn((55, 0), cells)

    def test_xy_area_of_unit_right_triangle(self):
        verts = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        tri = np.array([[0, 1, 2]], dtype=np.int16)
        area = stats.xy_area_m2(verts, tri)
        self.assertEqual(len(area), 1)
        self.assertAlmostEqual(float(area[0]), 0.5, places=6)

    def test_fo4_units_bin_into_red_rocket_starfield_cell(self):
        # FO4 cell (-17, 19) origin in metres: (-17*4096)/70, (19*4096)/70 ~= (-994.7, 1111.5)
        # that Starfield cell is (-10, 11). A 70 x 70 unit right triangle is 0.5 m^2.
        origin_u = np.array([-17 * 4096.0, 19 * 4096.0, 0.0])
        verts = np.vstack([origin_u, origin_u + [70.0, 0.0, 0.0], origin_u + [0.0, 70.0, 0.0]])
        tri = np.array([[0, 1, 2]], dtype=np.int16)
        part, n_in = stats.bin_triangles(verts, tri, stats.UNITS_PER_METRE)
        self.assertEqual(n_in, 1)
        self.assertEqual(list(part), ["-10,11"])
        self.assertEqual(part["-10,11"]["triangles"], 1)
        self.assertAlmostEqual(part["-10,11"]["area"], 0.5, places=6)

    def test_triangle_outside_overlay_is_dropped(self):
        verts = np.array([[1_000_000.0, 1_000_000.0, 0.0], [1_000_070.0, 1_000_000.0, 0.0], [1_000_000.0, 1_000_070.0, 0.0]])
        tri = np.array([[0, 1, 2]], dtype=np.int16)
        part, n_in = stats.bin_triangles(verts, tri, stats.UNITS_PER_METRE)
        self.assertEqual(n_in, 0)
        self.assertEqual(part, {})

    def test_empty_sf_inventory_marks_every_fo4_cell_lost(self):
        fo4 = {
            "0,0": {"triangles": 10, "area": 4.0},
            "-10,11": {"triangles": 2354, "area": 900.0},
            "1,1": {"triangles": 3, "area": 1.0},
        }
        report = inv.inventory(fo4, {})
        lost = [row["cell"] for row in report["lost_coverage"]]
        self.assertEqual(lost, ["-10,11", "0,0", "1,1"])
        self.assertEqual(report["unchanged"], 0)
        self.assertEqual(report["reduced_coverage"], [])
        worst = sorted(report["lost_coverage"], key=lambda r: -r["fo4_triangles"])[:3]
        self.assertEqual([w["cell"] for w in worst], ["-10,11", "0,0", "1,1"])

    def test_write_json_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "fo4.json"
            existing.write_text("{}", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                stats.write_json(existing, {"0,0": {"triangles": 1, "area": 1.0}})
            self.assertEqual(existing.read_text(encoding="utf-8"), "{}")

    def test_committed_core64c_stats_are_total_loss(self):
        data = ROOT / "docs" / "actors" / "data"
        fo4 = json.loads((data / "core64c-fo4-navmesh.json").read_text(encoding="utf-8"))
        sf = json.loads((data / "core64c-sf-navmesh.json").read_text(encoding="utf-8"))
        meta = json.loads((data / "core64c-navmesh-meta.json").read_text(encoding="utf-8"))
        self.assertEqual(sf, {})
        self.assertEqual(meta["sf"]["navm_records"], 0)
        self.assertEqual(meta["fo4"]["parsed"], 7047)
        self.assertEqual(len(fo4), 1069)
        report = inv.inventory(fo4, sf)
        self.assertEqual(len(report["lost_coverage"]), 1069)
        self.assertEqual(report["unchanged"], 0)
        self.assertEqual(report["total_fo4_triangles"], 3439338)
        worst = sorted(report["lost_coverage"], key=lambda row: -row["fo4_triangles"])[:3]
        self.assertEqual([row["cell"] for row in worst], ["2,-4", "2,14", "14,6"])
        self.assertEqual([row["fo4_triangles"] for row in worst], [9252, 7881, 7509])


if __name__ == "__main__":
    unittest.main()
