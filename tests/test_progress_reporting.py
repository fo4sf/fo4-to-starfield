"""Live progress in convert_batch includes skipped LOD/dmg names on one emit path."""
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


def _run(names, limit, convert=None):
    printed = []
    converter = SimpleNamespace(stats={}, material_errors={})
    converter.convert_nif = Mock(side_effect=convert or (
        lambda name: {"ok": True, "out_name": name[:-4], "shapes": 1, "fallback_materials": 0}))
    src = SimpleNamespace(mesh_names=lambda pattern: names)
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / "staging"
        collision = Path(tmp) / "collision.nif"
        collision.write_bytes(b"synthetic")
        argv = ["convert_batch.py", "--fo4-data", "unused", "--staging", str(staging),
                "--content-resources", "unused", "--texconv", "unused",
                "--collision-template", str(collision), "--limit", str(limit)]
        with patch.object(sys, "argv", argv), \
                patch.object(batch.pipeline, "Fo4Archives", return_value=src), \
                patch.object(batch.pipeline, "Converter", return_value=converter), \
                patch.object(batch.convert_static, "collision_template_from_nif", return_value=b"template"), \
                patch("builtins.print", side_effect=lambda *a, **k: printed.append(" ".join(str(x) for x in a))):
            batch.main()
        summary = json.loads((staging / "failure-summary.json").read_text())
        manifest = json.loads((staging / "manifest.json").read_text())
    progress = [p for p in printed if "progress:" in p]
    return progress, summary, manifest, converter.convert_nif


class ProgressReportingTests(unittest.TestCase):
    def test_skip_only_batch_emits_progress_without_converting(self):
        names = [f"meshes/setdressing/prop_lod_{i}.nif" for i in range(10)]
        progress, summary, manifest, convert_nif = _run(names, limit=20)
        self.assertEqual(len(progress), 1)
        self.assertIn("0 attempted", progress[0])
        self.assertIn("10 skipped", progress[0])
        self.assertEqual(summary["skipped"], 10)
        self.assertEqual(summary["successes"], 0)
        self.assertEqual(manifest["items"], [])
        convert_nif.assert_not_called()

    def test_mixed_batch_counts_skips_on_the_same_progress_line(self):
        names = ([f"meshes/setdressing/prop_lod_{i}.nif" for i in range(5)]
                 + [f"meshes/setdressing/chair_{i}.nif" for i in range(5)])
        progress, summary, manifest, convert_nif = _run(names, limit=20)
        self.assertEqual(len(progress), 1)
        self.assertIn("5 attempted", progress[0])
        self.assertIn("5 skipped", progress[0])
        self.assertIn("5 ok", progress[0])
        self.assertEqual(summary["skipped"], 5)
        self.assertEqual(summary["successes"], 5)
        self.assertEqual(len(manifest["items"]), 5)
        self.assertEqual(convert_nif.call_count, 5)

    def test_limit_stops_conversions_after_skips_without_dropping_skip_progress(self):
        names = ([f"meshes/setdressing/prop_lod_{i}.nif" for i in range(10)]
                 + [f"meshes/setdressing/chair_{i}.nif" for i in range(10)])
        progress, summary, manifest, convert_nif = _run(names, limit=5)
        self.assertEqual(progress[0].count("10 skipped"), 1)
        self.assertIn("0 attempted", progress[0])
        self.assertEqual(summary["skipped"], 10)
        self.assertEqual(summary["successes"], 5)
        self.assertEqual(len(manifest["items"]), 5)
        self.assertEqual(convert_nif.call_count, 5)
        converted = {i["source"] for i in manifest["items"]}
        self.assertTrue(all("chair_" in n for n in converted))
        self.assertNotIn("meshes/setdressing/chair_5.nif", converted)
