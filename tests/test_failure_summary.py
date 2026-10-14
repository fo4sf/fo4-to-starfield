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
            self.assertEqual(summary["attempted"], 4)
            self.assertEqual(summary["successes"], 0)
            self.assertAlmostEqual(summary["success_percent"], 0.0)
            self.assertIn("generated_at", summary)
            self.assertEqual(summary["top"][0]["reason"], "missing texture")
            self.assertEqual(summary["top"][0]["count"], 2)
            self.assertAlmostEqual(summary["top"][0]["percent"], 50.0)

    def test_writes_zero_summary_when_no_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            collision = Path(tmp) / "collision.nif"
            collision.write_bytes(b"synthetic")
            names = [f"meshes/ok{i}.nif" for i in range(2)]
            src = SimpleNamespace(mesh_names=lambda pattern: names)
            converter = SimpleNamespace(stats={}, material_errors={})

            def convert(name):
                return {"ok": True, "out_name": "out", "shapes": 1, "fallback_materials": 0}
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
            self.assertEqual(summary["total_failures"], 0)
            self.assertEqual(summary["unique_reasons"], 0)
            self.assertEqual(summary["attempted"], 2)
            self.assertEqual(summary["successes"], 2)
            self.assertAlmostEqual(summary["success_percent"], 100.0)
            self.assertIn("generated_at", summary)
            self.assertEqual(summary["top"], [])

    def test_overwrites_stale_summary_on_successful_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            collision = Path(tmp) / "collision.nif"
            collision.write_bytes(b"synthetic")
            names = [f"meshes/m{i}.nif" for i in range(2)]
            src = SimpleNamespace(mesh_names=lambda pattern: names)

            # First run: all fail
            converter_fail = SimpleNamespace(stats={}, material_errors={})
            def convert_fail(name):
                return {"ok": False, "reason": "missing texture"}
            converter_fail.convert_nif = Mock(side_effect=convert_fail)
            argv = ["convert_batch.py", "--fo4-data", "unused", "--staging", str(staging),
                    "--content-resources", "unused", "--texconv", "unused",
                    "--collision-template", str(collision), "--limit", "10"]
            with patch.object(sys, "argv", argv), \
                    patch.object(batch.pipeline, "Fo4Archives", return_value=src), \
                    patch.object(batch.pipeline, "Converter", return_value=converter_fail), \
                    patch.object(batch.convert_static, "collision_template_from_nif", return_value=b"template"), \
                    patch("builtins.print"):
                batch.main()
            summary = json.loads((staging / "failure-summary.json").read_text())
            self.assertEqual(summary["total_failures"], 2)

            # Second run: all succeed — must overwrite with zeros
            converter_ok = SimpleNamespace(stats={}, material_errors={})
            def convert_ok(name):
                return {"ok": True, "out_name": "out", "shapes": 1, "fallback_materials": 0}
            converter_ok.convert_nif = Mock(side_effect=convert_ok)
            with patch.object(sys, "argv", argv), \
                    patch.object(batch.pipeline, "Fo4Archives", return_value=src), \
                    patch.object(batch.pipeline, "Converter", return_value=converter_ok), \
                    patch.object(batch.convert_static, "collision_template_from_nif", return_value=b"template"), \
                    patch("builtins.print"):
                batch.main()
            summary = json.loads((staging / "failure-summary.json").read_text())
            self.assertEqual(summary["total_failures"], 0)
            self.assertEqual(summary["unique_reasons"], 0)
            self.assertEqual(summary["successes"], 2)
            self.assertAlmostEqual(summary["success_percent"], 100.0)
            self.assertEqual(summary["top"], [])

