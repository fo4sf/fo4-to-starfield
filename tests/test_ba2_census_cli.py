"""Synthetic test for the ba2_census CLI."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.ba2_fixture import general_archive


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "ba2_census.py"


class Ba2CensusCliTests(unittest.TestCase):
    def run_cli(self, path, *args):
        return subprocess.run([sys.executable, "-I", "-B", str(SCRIPT), str(path), *args],
                              capture_output=True, text=True, check=False, timeout=30,
                              cwd=path.parent)

    def test_negative_top_is_usage_error_before_opening_archive(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "valid.ba2"
            data = general_archive({"one.txt": b"one", "two.txt": b"twotwo", "three.bin": b"three"})
            path.write_bytes(data)
            for candidate in [path, Path(d) / "absent.ba2"]:
                for top in ["-1", "-10"]:
                    with self.subTest(candidate=candidate.name, top=top):
                        result = self.run_cli(candidate, "--top", top)
                        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                        self.assertEqual(result.stdout, "")
                        self.assertIn("--top", result.stderr)
                        self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(path.read_bytes(), data)

    def test_malformed_metadata_has_clean_error_without_partial_json(self):
        data = general_archive({"a.txt": b"data"})
        invalid_kind = data[:8] + b"\xff\xff\xff\xff" + data[12:]
        for bad in [b"", b"BTDX", data[:23], data[:40], data[:-1-len("a.txt")], invalid_kind]:
            with self.subTest(length=len(bad)), tempfile.TemporaryDirectory() as d:
                path = Path(d) / "malformed.ba2"
                path.write_bytes(bad)
                result = self.run_cli(path)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertIn("error:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(path.read_bytes(), bad)

    def test_zero_and_large_top_keep_valid_raw_and_compressed_reports(self):
        for compressed in [False, True]:
            with self.subTest(compressed=compressed), tempfile.TemporaryDirectory() as d:
                path = Path(d) / "valid.ba2"
                data = general_archive({"a.txt": b"a", "b.bin": b"bb"}, compressed=compressed)
                path.write_bytes(data)
                for top, count in [("0", 0), ("100", 2)]:
                    result = self.run_cli(path, "--top", top)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    report = json.loads(result.stdout)
                    self.assertEqual(len(report["largest"]), count)
                    self.assertEqual(report["summary"]["entries"], 2)
                    self.assertNotIn("path", report["summary"])
                self.assertEqual(path.read_bytes(), data)

    def test_missing_archive_is_clean_failure(self):
        with tempfile.TemporaryDirectory() as d:
            result = self.run_cli(Path(d) / "missing.ba2")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("error:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_prints_summary_and_largest(self):
        entries = {
            "small.txt": b"a" * 10,
            "big.dat": b"b" * 500,
        }
        data = general_archive(entries, compressed=True)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "census.ba2"
            path.write_bytes(data)
            env = os.environ.copy()
            env["PYTHONPATH"] = str(REPO / "src")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(path), "--top", "1"],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["summary"]["entries"], 2)
            self.assertEqual(report["summary"]["general"], 2)
            self.assertEqual(len(report["largest"]), 1)
            self.assertEqual(report["largest"][0]["name"], "big.dat")
            self.assertEqual(report["largest"][0]["unpacked"], 500)
            self.assertNotIn("path", report["summary"])


if __name__ == "__main__":
    unittest.main()
