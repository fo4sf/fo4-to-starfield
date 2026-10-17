"""--max-tris is applied and large meshes are skipped."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
spec = importlib.util.spec_from_file_location("convert_batch", root / "scripts" / "convert_batch.py")
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


class MaxTrisTests(unittest.TestCase):
    def test_max_tris_skips_large_mesh(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            collision = Path(tmp) / "collision.nif"
            collision.write_bytes(b"synthetic")
            name = "meshes/big.nif"
            src = SimpleNamespace(mesh_names=lambda pattern: [name])
            converter = SimpleNamespace(stats={}, material_errors={})

            def convert(n):
                return {"ok": False, "reason": "ValueError: too many triangles (25000 > 20000)"}
            converter.convert_nif = Mock(side_effect=convert)

            argv = ["convert_batch.py", "--fo4-data", "unused", "--staging", str(staging),
                    "--content-resources", "unused", "--texconv", "unused",
                    "--collision-template", str(collision), "--max-tris", "20000", "--limit", "5"]
            with patch.object(sys, "argv", argv), \
                 patch.object(batch.pipeline, "Fo4Archives", return_value=src), \
                 patch.object(batch.pipeline, "Converter", return_value=converter), \
                 patch.object(batch.convert_static, "collision_template_from_nif", return_value=b"t"), \
                 patch("builtins.print"):
                batch.main()
            summary = json.loads((staging / "failure-summary.json").read_text())
            self.assertEqual(summary.get("skipped", 0), 1)
            self.assertEqual(summary.get("total_failures", 0), 0)


if __name__ == "__main__":
    unittest.main()
