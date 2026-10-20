"""convert_batch --limit progress ETA uses successful throughput, not attempt rate."""
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
spec = importlib.util.spec_from_file_location("convert_batch_eta", root / "scripts" / "convert_batch.py")
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


def _ok(name):
    return {"ok": True, "out_name": name[:-4], "shapes": 1, "fallback_materials": 0}


def _fail(_name):
    return {"ok": False, "reason": "injected failure"}


class BatchProgressEtaTests(unittest.TestCase):
    def _run(self, names, convert, limit, elapsed=100.0, cell=False):
        printed = []
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            collision = Path(tmp) / "collision.nif"
            collision.write_bytes(b"synthetic")
            src = SimpleNamespace(mesh_names=lambda pattern: list(names))
            converter = SimpleNamespace(stats={}, material_errors={}, texture_log={})
            converter.convert_nif = Mock(side_effect=convert)
            argv = ["convert_batch.py", "--fo4-data", "unused", "--staging", str(staging),
                    "--content-resources", "unused", "--texconv", "unused",
                    "--collision-template", str(collision), "--limit", str(limit)]
            if cell:
                cell_file = Path(tmp) / "cell.json"
                cell_file.write_text(json.dumps({"refs": [
                    {"model": name.removeprefix("meshes\\"), "type": "Static"}
                    for name in names]}), encoding="utf-8")
                argv.extend(["--cell-json", str(cell_file)])
            clock = {"n": 0}

            def fake_time():
                clock["n"] += 1
                return 0.0 if clock["n"] == 1 else elapsed

            with patch.object(sys, "argv", argv), \
                    patch.object(batch.pipeline, "Fo4Archives", return_value=src), \
                    patch.object(batch.pipeline, "Converter", return_value=converter), \
                    patch.object(batch.convert_static, "collision_template_from_nif", return_value=b"template"), \
                    patch.object(batch.time, "time", side_effect=fake_time), \
                    patch("builtins.print", side_effect=lambda *a, **k: printed.append(" ".join(str(x) for x in a))):
                batch.main()
            manifest = json.loads((staging / "manifest.json").read_text())
        progress = [line for line in printed if line.startswith("  progress:")]
        return progress, manifest, printed

    def test_mixed_failures_use_success_rate_not_attempt_rate(self):
        # Codex 5561634581: 10 attempts / 100s, 1 success, 9 failures, limit 20.
        # Attempt-rate ETA was ~3m; success-rate remaining 19 at 1/100s is ~32m.
        names = [f"meshes/setdressing/m{i:02d}.nif" for i in range(30)]

        def convert(name):
            return _ok(name) if name.endswith("m00.nif") else _fail(name)

        progress, manifest, _printed = self._run(names, convert, limit=20)
        self.assertTrue(progress)
        line = progress[0]
        self.assertIn("(5% of limit)", line)
        self.assertIn("~32m left", line)
        self.assertNotIn("~3m left", line)
        self.assertEqual(len(manifest["items"]), 1)
        self.assertEqual(len(manifest["failures"]), 29)

    def test_zero_successes_omits_eta(self):
        names = [f"meshes/setdressing/f{i:02d}.nif" for i in range(30)]
        progress, manifest, _printed = self._run(names, _fail, limit=20)
        self.assertTrue(progress)
        line = progress[0]
        self.assertIn("(0% of limit)", line)
        self.assertNotIn("left", line)
        self.assertEqual(manifest["items"], [])
        self.assertEqual(len(manifest["failures"]), 30)

    def test_exhausted_input_omits_eta(self):
        names = [f"meshes/setdressing/e{i:02d}.nif" for i in range(10)]

        def convert(name):
            return _ok(name) if name.endswith("e00.nif") else _fail(name)

        progress, manifest, _printed = self._run(names, convert, limit=20)
        self.assertEqual(len(progress), 1)
        line = progress[0]
        self.assertIn("(5% of limit)", line)
        self.assertNotIn("left", line)
        self.assertEqual(len(manifest["items"]), 1)
        self.assertEqual(len(manifest["failures"]), 9)

    def test_remaining_candidate_accounting_is_linear(self):
        names = [f"meshes/setdressing/f{i:05d}.nif" for i in range(2000)]
        original_compile = batch.re.compile
        searches = []

        def counted_compile(pattern, *args, **kwargs):
            actual = original_compile(pattern, *args, **kwargs)
            if pattern != r"(lod|_dmg|damaged|destr)":
                return actual

            def search(name):
                searches.append(name)
                return actual.search(name)

            return SimpleNamespace(search=search)

        with patch.object(batch.re, "compile", side_effect=counted_compile):
            progress, manifest, _printed = self._run(names, _fail, limit=20)
        self.assertEqual([row["nif"] for row in manifest["failures"]], names)
        self.assertEqual(manifest["items"], [])
        self.assertTrue(progress)
        self.assertTrue(all("left" not in line for line in progress))
        self.assertLessEqual(len(searches), 3 * len(names))

    def test_skipped_lod_candidates_cannot_supply_success_target(self):
        eligible = [f"meshes/setdressing/e{i:02d}.nif" for i in range(28)]
        skipped = [f"meshes/setdressing/lod{i:02d}.nif" for i in range(20)]
        names = eligible[:10] + skipped + eligible[10:]

        def convert(name):
            return _ok(name) if name == eligible[0] else _fail(name)

        progress, manifest, _printed = self._run(names, convert, limit=20)
        self.assertNotIn("left", progress[0])  # Only 18 eligible remain; target needs 19.
        self.assertEqual([row["source"] for row in manifest["items"]], eligible[:1])
        self.assertEqual([row["nif"] for row in manifest["failures"]], eligible[1:])

    def test_cell_mode_counts_lod_named_models_as_eligible(self):
        names = [f"meshes\\setdressing\\lod{i:02d}.nif" for i in range(30)]

        def convert(name):
            return _ok(name) if name == names[0] else _fail(name)

        progress, manifest, _printed = self._run(names, convert, limit=20, cell=True)
        self.assertIn("~32m left", progress[0])
        self.assertEqual([row["source"] for row in manifest["items"]], names[:1])
        self.assertEqual([row["nif"] for row in manifest["failures"]], names[1:])


if __name__ == "__main__":
    unittest.main()
