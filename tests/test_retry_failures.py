"""--retry-failures: merge into the prior stage; actual main() regressions."""
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

A, B, C = "meshes/ok.nif", "meshes/fail1.nif", "meshes/fail2.nif"


def convert_ok(name):
    return {"ok": True, "out_name": Path(name).stem, "shapes": 1, "fallback_materials": 0}


def run_main(staging, collision, names, convert, extra=()):
    src = SimpleNamespace(mesh_names=lambda pattern: list(names))
    converter = SimpleNamespace(stats={}, material_errors={}, convert_nif=Mock(side_effect=convert))
    argv = ["convert_batch.py", "--fo4-data", "unused", "--staging", str(staging),
            "--content-resources", "unused", "--texconv", "unused",
            "--collision-template", str(collision), *extra]
    with patch.object(sys, "argv", argv), \
            patch.object(batch.pipeline, "Fo4Archives", return_value=src), \
            patch.object(batch.pipeline, "Converter", return_value=converter), \
            patch.object(batch.convert_static, "collision_template_from_nif", return_value=b"template"), \
            patch("builtins.print"):
        batch.main()
    return converter.convert_nif


class RetryFailuresTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.staging = Path(self.tmp.name) / "staging"
        self.collision = Path(self.tmp.name) / "collision.nif"
        self.collision.write_bytes(b"synthetic")

    def tearDown(self):
        self.tmp.cleanup()

    def _initial_abc(self):
        def convert(name):
            if name == A:
                return convert_ok(name)
            return {"ok": False, "reason": "boom:" + name}
        run_main(self.staging, self.collision, [A, B, C], convert, extra=["--limit", "10"])
        man = json.loads((self.staging / "manifest.json").read_text())
        self.assertEqual([it["source"] for it in man["items"]], [A])
        self.assertEqual([f["nif"] for f in man["failures"]], [B, C])

    def test_retry_merges_successes_into_prior_manifest(self):
        self._initial_abc()
        prior_a = json.loads((self.staging / "manifest.json").read_text())["items"][0]
        run_main(self.staging, self.collision, [A, B, C], convert_ok,
                 extra=["--retry-failures", "--limit", "10"])
        man = json.loads((self.staging / "manifest.json").read_text())
        sources = [it["source"] for it in man["items"]]
        self.assertEqual(sources, [A, B, C])
        self.assertEqual(man["items"][0]["form_index"], prior_a["form_index"])
        self.assertEqual(man["failures"], [])
        summary = json.loads((self.staging / "failure-summary.json").read_text())
        self.assertEqual(summary["failed_nifs"], [])
        state = json.loads((self.staging / "build-state.json").read_text())
        self.assertTrue(state["complete"])

    def test_limited_retry_keeps_unattempted_failures(self):
        self._initial_abc()
        convert = Mock(side_effect=convert_ok)
        run_main(self.staging, self.collision, [A, B, C], convert,
                 extra=["--retry-failures", "--limit", "1"])
        called = [c.args[0] for c in convert.call_args_list]
        self.assertEqual(called, [B])
        man = json.loads((self.staging / "manifest.json").read_text())
        self.assertEqual([it["source"] for it in man["items"]], [A, B])
        self.assertEqual([f["nif"] for f in man["failures"]], [C])
        summary = json.loads((self.staging / "failure-summary.json").read_text())
        self.assertEqual(summary["failed_nifs"], [C])
        state = json.loads((self.staging / "build-state.json").read_text())
        self.assertFalse(state["complete"])
        convert2 = Mock(side_effect=convert_ok)
        run_main(self.staging, self.collision, [A, B, C], convert2,
                 extra=["--retry-failures", "--limit", "1"])
        self.assertEqual([c.args[0] for c in convert2.call_args_list], [C])
        man = json.loads((self.staging / "manifest.json").read_text())
        self.assertEqual([it["source"] for it in man["items"]], [A, B, C])
        self.assertEqual(json.loads((self.staging / "failure-summary.json").read_text())["failed_nifs"], [])

    def test_legacy_summary_without_failed_nifs_refuses(self):
        self._initial_abc()
        summary_path = self.staging / "failure-summary.json"
        legacy = {"total_failures": 2, "reasons": {"boom": 2}, "examples": {"boom": [B, C]}}
        summary_path.write_text(json.dumps(legacy), encoding="utf-8")
        before_summary = summary_path.read_bytes()
        before_manifest = (self.staging / "manifest.json").read_bytes()
        with self.assertRaises(SystemExit) as caught:
            run_main(self.staging, self.collision, [A, B, C], convert_ok,
                     extra=["--retry-failures", "--limit", "10"])
        self.assertIn("failed_nifs", str(caught.exception))
        self.assertEqual(summary_path.read_bytes(), before_summary)
        self.assertEqual((self.staging / "manifest.json").read_bytes(), before_manifest)


if __name__ == "__main__":
    unittest.main()
