"""Synthetic tests for SfMesh.summary and the mesh-summary CLI."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fo4sf.sfmesh import SfMesh, serialize, parse


class MeshSummaryTests(unittest.TestCase):
    def _tiny_mesh(self) -> SfMesh:
        m = SfMesh(version=2, scale=1.0, weights_per_vertex=0)
        m.triangles = [(0, 1, 2)]
        m.positions = [(0, 0, 0), (1000, 0, 0), (0, 1000, 0)]
        m.uv1 = [(0, 0), (32767, 0), (0, 32767)]
        m.normals = [0, 0, 0]
        m.tangents = [0, 0, 0]
        m.has_meshlet_section = True
        m.meshlets = [(3, 0, 1, 0)]
        m.cull_data = [b"\0" * 24]
        return m

    def test_summary_fields(self):
        m = self._tiny_mesh()
        s = m.summary()
        self.assertEqual(s["version"], 2)
        self.assertEqual(s["vertices"], 3)
        self.assertEqual(s["triangles"], 1)
        self.assertFalse(s["skinned"])
        self.assertEqual(s["meshlets"], 1)
        self.assertTrue(s["has_meshlet_section"])
        self.assertTrue(s["has_uv1"])
        self.assertFalse(s["has_uv2"])
        self.assertEqual(s["tail_bytes"], 0)

    def test_roundtrip_summary(self):
        m = self._tiny_mesh()
        data = serialize(m)
        parsed = parse(data)
        self.assertEqual(parsed.summary()["vertices"], 3)
        self.assertEqual(parsed.summary()["triangles"], 1)

    def test_cli_text_and_json(self):
        m = self._tiny_mesh()
        data = serialize(m)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "tiny.mesh"
            path.write_bytes(data)
            # text
            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
            r = subprocess.run(
                [sys.executable, "-m", "fo4sf", "mesh-summary", str(path)],
                capture_output=True, text=True, env=env, cwd=Path(__file__).resolve().parents[1],
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("vertices: 3", r.stdout)
            self.assertIn("triangles: 1", r.stdout)
            # json
            r2 = subprocess.run(
                [sys.executable, "-m", "fo4sf", "mesh-summary", "--json", str(path)],
                capture_output=True, text=True, env=env, cwd=Path(__file__).resolve().parents[1],
            )
            self.assertEqual(r2.returncode, 0, r2.stderr)
            parsed = json.loads(r2.stdout)
            self.assertEqual(len(parsed), 1)
            self.assertEqual(parsed[0]["vertices"], 3)
            self.assertEqual(parsed[0]["path"], str(path))


if __name__ == "__main__":
    unittest.main()
