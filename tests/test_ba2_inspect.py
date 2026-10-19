"""Synthetic tests for the ba2_inspect CLI."""
import os
import subprocess
import sys
import tempfile
import unittest

from tests.ba2_fixture import general_archive


class Ba2InspectCLITests(unittest.TestCase):
    def _run(self, path, *extra):
        env = os.environ.copy()
        env["PYTHONPATH"] = os.path.join(os.path.dirname(__file__), "..", "src")
        cmd = [sys.executable, os.path.join(os.path.dirname(__file__), "..", "scripts", "ba2_inspect.py"), path, *extra]
        return subprocess.run(cmd, capture_output=True, text=True, env=env)

    def test_summary_and_largest(self):
        entries = {"tiny.txt": b"a", "big.dat": b"b" * 5000}
        data = general_archive(entries)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.ba2")
            with open(path, "wb") as f:
                f.write(data)
            r = self._run(path, "--largest", "1")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("entries: 2", r.stdout)
            self.assertIn("big.dat", r.stdout)
            self.assertIn("5000", r.stdout.replace(",", ""))  # size appears

    def test_json(self):
        data = general_archive({"x.txt": b"hello"})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "one.ba2")
            with open(path, "wb") as f:
                f.write(data)
            r = self._run(path, "--json")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('"summary"', r.stdout)
            self.assertIn('"largest"', r.stdout)

    def test_missing_file(self):
        r = self._run("/nonexistent/archive.ba2")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("error", r.stderr.lower())


if __name__ == "__main__":
    unittest.main()
