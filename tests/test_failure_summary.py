"""Failure summary reporting in convert_batch."""
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


class FailureSummaryTests(unittest.TestCase):
    def test_writes_failure_summary_with_percentages(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            collision = Path(tmp) / "collision.nif"
            collision.write_bytes(b"synthetic")
            names = [f"meshes/fail{i}.nif" for i in range(4)]
            src = SimpleNamespace(mesh_names=lambda pattern: names)
            converter = SimpleNamespace(stats={}, material_errors={})

            def convert(name):
                if name.endswith("0.nif"):
                    return {"ok": False, "reason": "missing texture: foo"}
                if name.endswith("1.nif"):
                    return {"ok": False, "reason": "missing texture: bar"}
                return {"ok": False, "reason": "too many tris"}
            converter.convert_nif = Mock(side_effect=convert)
            argv = ["convert_batch.py", "--fo4-data", "unused", "--staging", str(staging),
                    "--content-resources", "unused", "--texconv", "unused",
                    "--collision-template", str(collision), "--limit", "10"]
            with patch.object(sys, "argv", argv), \
                    patch.object(batch.pipeline, "Fo4Archives", return_value=src), \
                    patch.object(batch.pipeline, "Converter", return_value=converter), \
                    patch.object(batch.convert_static, "collision_template_from_nif", return_value=b"template"), \
                    patch("builtins.print"):
                batch.main()
            summary_path = staging / "failure-summary.json"
            self.assertTrue(summary_path.exists())
            summary = json.loads(summary_path.read_text())
            self.assertEqual(summary["total_failures"], 4)
            self.assertEqual(summary["unique_reasons"], 2)
            self.assertEqual(summary["top"][0]["reason"], "missing texture")
            self.assertEqual(summary["top"][0]["count"], 2)
            self.assertAlmostEqual(summary["top"][0]["percent"], 50.0)
