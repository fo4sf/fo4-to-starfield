"""Actual isolated CLI checks for the converted .mesh bounds diagnostic."""
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf import sfmesh


class MeshBoundsTests(unittest.TestCase):
    def run_mesh(self, data):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.mesh"
            path.write_bytes(data)
            result = subprocess.run(
                [sys.executable, "-I", str(ROOT / "scripts/oracles/mesh_aabb_helper.py"), str(path)],
                capture_output=True, text=True, cwd=folder,
            )
            self.assertEqual(path.read_bytes(), data)
            return result

    def test_decodes_packed_positions_and_reports_mesh_local_bounds(self):
        mesh = sfmesh.SfMesh(scale=7.0, positions=[(-32767, 0, 32767), (0, -32767, 0)])
        result = self.run_mesh(sfmesh.serialize(mesh))
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["min"], [-7.0, -7.0, 0.0])
        self.assertEqual(report["max"], [0.0, 0.0, 7.0])
        self.assertEqual(report["vertices"], 2)
        self.assertEqual(report["frame"], "mesh-local")
        self.assertEqual(report["units"], "metres")

    def test_single_origin_vertex_is_a_valid_zero_extent_box(self):
        result = self.run_mesh(sfmesh.serialize(sfmesh.SfMesh(positions=[(0, 0, 0)])))
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["min"], report["max"])
        self.assertEqual(report["min"], [0.0, 0.0, 0.0])

    def test_refuses_empty_mesh_without_success_report(self):
        result = self.run_mesh(sfmesh.serialize(sfmesh.SfMesh()))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("no vertices", result.stderr)

    def test_refuses_invalid_scale_without_success_report(self):
        for scale in [0.0, -1.0, math.nan, math.inf, -math.inf]:
            with self.subTest(scale=scale):
                result = self.run_mesh(sfmesh.serialize(sfmesh.SfMesh(scale=scale, positions=[(1, 2, 3)])))
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("finite positive", result.stderr)

    def test_refuses_truncated_or_nonmesh_bytes(self):
        for data in [b"", b"\x02\0\0\0", b"Gamebryo File Format"]:
            with self.subTest(data=data):
                result = self.run_mesh(data)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("mesh bounds:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_missing_path_has_clean_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run(
                [sys.executable, "-I", str(ROOT / "scripts/oracles/mesh_aabb_helper.py"),
                 str(Path(folder) / "absent.mesh")], capture_output=True, text=True,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("mesh bounds:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
