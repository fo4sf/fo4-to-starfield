"""Exercise manifest exit status and advisory batch reports through the CLI."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ENTRY = (
    f"import sys; sys.path.insert(0, {str(ROOT / 'src')!r}); "
    "from fo4sf.__main__ import main; raise SystemExit(main())"
)
SUMMARY = {
    "attempted": 10,
    "successes": 8,
    "success_percent": 80.0,
    "total_failures": 2,
    "top": [{"reason": "missing texture", "count": 2, "percent": 100.0}],
}


class StatusCliResultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.staging = self.base / "staging"
        self.work = self.base / "work"
        self.staging.mkdir()
        self.work.mkdir()
        self.config = self.base / "config.toml"
        self.config.write_text(
            "[paths]\n"
            f"staging_dir = {json.dumps(self.staging.as_posix())}\n"
            f"work_dir = {json.dumps(self.work.as_posix())}\n",
            encoding="utf-8",
        )

    def run_status(self, explicit=None):
        args = [sys.executable, "-I", "-B", "-c", ENTRY,
                "--config", str(self.config), "status"]
        if explicit is not None:
            args.extend(["--manifest", str(explicit)])
        return subprocess.run(args, capture_output=True, text=True, check=False,
                              cwd=self.base, timeout=30)

    def write_manifest(self, directory, valid=True):
        path = directory / "manifest.json"
        path.write_text(
            json.dumps([{"type": "static", "fidelity_tier": "T1"}]) if valid else "{",
            encoding="utf-8",
        )
        return path

    def write_summary(self, directory, data):
        (directory / "failure-summary.json").write_text(json.dumps(data), encoding="utf-8")

    def test_corrupt_manifest_result_matches_explicit_and_both_discovery_paths(self):
        for directory in (self.staging, self.work):
            manifest = self.write_manifest(directory, valid=False)
            for summary in (None, SUMMARY, {"top": [None]}):
                with self.subTest(directory=directory.name, summary=summary):
                    if summary is not None:
                        self.write_summary(directory, summary)
                    explicit = self.run_status(manifest)
                    discovered = self.run_status()
                    for result in (explicit, discovered):
                        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                        self.assertIn("manifest error:", result.stderr)
                        self.assertNotIn("Traceback", result.stderr)
            # Give the next iteration access to work_dir rather than staging_dir.
            manifest.unlink()

    def test_malformed_advisory_report_preserves_healthy_manifest_result(self):
        manifest = self.write_manifest(self.staging)
        cases = [None, [], "report", {"top": "bad"}, {"top": {}},
                 {"top": [None]}, {"top": [{"count": "two"}]},
                 {"top": [{"percent": "many"}]}, {"top": [{"reason": None}]},
                 {"top": [SUMMARY["top"][0], {"count": "bad"}]}]
        for data in cases:
            for explicit in (None, manifest):
                with self.subTest(data=data, explicit=explicit is not None):
                    self.write_summary(self.staging, data)
                    result = self.run_status(explicit)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("failure-summary error:", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertIn("(1 items)", result.stdout)
                    self.assertNotIn("Latest batch:", result.stdout)
                    self.assertNotIn("Top failure reasons:", result.stdout)

    def test_truncated_report_is_advisory(self):
        self.write_manifest(self.staging)
        (self.staging / "failure-summary.json").write_text("{", encoding="utf-8")
        result = self.run_status()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("failure-summary error:", result.stderr)
        self.assertNotIn("Latest batch:", result.stdout)

    def test_valid_report_preserves_format_and_limits_reasons(self):
        self.write_manifest(self.staging)
        data = dict(SUMMARY, top=SUMMARY["top"] + [
            {"reason": "second", "count": 0, "percent": 0.0},
            {"reason": "third", "count": 0, "percent": 0.0},
            {"reason": "fourth-not-displayed", "count": 0, "percent": 0.0},
        ])
        self.write_summary(self.staging, data)
        result = self.run_status()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("Latest batch: 8/10 succeeded (80.0%), 2 failures", result.stdout)
        self.assertIn("       2 (100.0%)  missing texture", result.stdout)
        self.assertIn("second", result.stdout)
        self.assertIn("third", result.stdout)
        self.assertNotIn("fourth-not-displayed", result.stdout)

    def test_staging_error_does_not_fall_through_to_healthy_work_manifest(self):
        self.write_manifest(self.staging, valid=False)
        self.write_manifest(self.work)
        result = self.run_status()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(str(self.staging / "manifest.json"), result.stderr)
        self.assertNotIn("(1 items)", result.stdout)

    def test_work_fallback_and_null_top_remain_supported(self):
        self.write_manifest(self.work)
        self.write_summary(self.work, dict(SUMMARY, top=None))
        result = self.run_status()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn(str(self.work / "manifest.json"), result.stdout)
        self.assertIn("Latest batch: 8/10 succeeded", result.stdout)
        self.assertNotIn("Top failure reasons:", result.stdout)

    def test_absent_manifest_is_informational_unless_explicit(self):
        discovered = self.run_status()
        self.assertEqual(discovered.returncode, 0, discovered.stderr)
        self.assertIn("Manifest: not found", discovered.stdout)
        explicit = self.run_status(self.staging / "manifest.json")
        self.assertEqual(explicit.returncode, 1)
        self.assertIn("manifest error:", explicit.stderr)


if __name__ == "__main__":
    unittest.main()
