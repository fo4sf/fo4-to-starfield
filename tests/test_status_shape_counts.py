"""Reject malformed optional shape counts through both API and actual CLI."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf.manifest import ManifestError, summarize_manifest

ENTRY = f"import sys; sys.path.insert(0, {str(ROOT / 'src')!r}); from fo4sf.__main__ import main; raise SystemExit(main())"
INVALID = ["many", "2", -1, 1.75, True, [], {}, 10 ** 400]


class StatusShapeCountsTests(unittest.TestCase):
    def test_valid_counts_and_legacy_missing_null_fields(self):
        report = summarize_manifest([{"shapes": 4}, {"shapes": 0}, {}, {"shapes": None}])
        self.assertEqual(report["total_shapes"], 4)
        self.assertEqual(report["avg_shapes"], 1.0)

    def test_api_refuses_instead_of_coercing_bad_counts(self):
        for bad in INVALID:
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ManifestError, "shape"):
                    summarize_manifest([{"type": "STAT", "shapes": bad}])

    def test_actual_cli_bad_counts_are_clean_errors_explicit_and_discovered(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            config = base / "settings.toml"
            config.write_text(f'[paths]\nstaging_dir = {json.dumps(base.as_posix())}\n', encoding="utf-8")
            manifest = base / "manifest.json"
            for bad in INVALID:
                manifest.write_text(json.dumps([{"type": "STAT", "shapes": bad}]), encoding="utf-8")
                for explicit in [False, True]:
                    with self.subTest(bad=bad, explicit=explicit):
                        command = [sys.executable, "-I", "-B", "-c", ENTRY,
                                   "--config", str(config), "status"]
                        if explicit:
                            command += ["--manifest", str(manifest)]
                        original = manifest.read_bytes()
                        result = subprocess.run(command, cwd=base, capture_output=True, text=True)
                        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                        self.assertIn("manifest error:", result.stderr)
                        self.assertNotIn("Traceback", result.stderr)
                        self.assertNotIn("Asset mix:", result.stdout)
                        self.assertNotIn("(1 items)", result.stdout)
                        self.assertEqual(manifest.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
