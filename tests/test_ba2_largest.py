"""Synthetic tests for Ba2.largest_entries and the ba2-largest CLI."""
import os
import subprocess
import sys
import tempfile
import unittest

from tests.ba2_fixture import general_archive
from fo4sf.ba2 import Ba2


class LargestEntriesTests(unittest.TestCase):
    def test_orders_by_unpacked_size(self):
        entries = {
            "small.txt": b"a" * 10,
            "medium.bin": b"b" * 100,
            "large.dat": b"c" * 1000,
        }
        data = general_archive(entries, compressed=True)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            top = a.largest_entries(2)
            self.assertEqual(len(top), 2)
            self.assertEqual(top[0]["name"], "large.dat")
            self.assertEqual(top[0]["unpacked"], 1000)
            self.assertGreater(top[0]["packed"], 0)  # compressed
            self.assertEqual(top[1]["name"], "medium.bin")
            self.assertEqual(top[1]["unpacked"], 100)

    def test_empty_and_n_limit(self):
        data = general_archive({"only.txt": b"x"})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "one.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            self.assertEqual(len(a.largest_entries(5)), 1)
            self.assertEqual(a.largest_entries(0), [])

    def test_cli_ba2_largest(self):
        data = general_archive({"a.txt": b"x" * 50, "b.bin": b"y" * 500}, compressed=False)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "cli.ba2")
            with open(path, "wb") as f:
                f.write(data)
            env = os.environ.copy()
            env["PYTHONPATH"] = os.path.join(os.path.dirname(__file__), "..", "src")
            r = subprocess.run(
                [sys.executable, "-m", "fo4sf", "ba2-largest", path, "--n", "1"],
                capture_output=True, text=True, env=env,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("b.bin", r.stdout)
            self.assertIn("500", r.stdout)
            self.assertNotIn("a.txt", r.stdout)


if __name__ == "__main__":
    unittest.main()
