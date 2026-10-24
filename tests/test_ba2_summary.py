"""Tests for Ba2.by_extension and the ba2-summary CLI."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fo4sf.ba2 import Ba2
from tests.ba2_fixture import general_archive


class TestBa2ByExtension(unittest.TestCase):
    def test_mixed_separators_and_dirs(self):
        files = {
            "meshes\\actors\\raider.nif": b"nif",
            "meshes/actors/raider.nif": b"dup",  # same after norm? but different names in archive
            "textures\\setdressing\\x_d.dds": b"dds",
            "materials\\setdressing\\x.bgsm": b"bgsm",
            "noext": b"none",
            "dir.with.dot\\file.txt": b"txt",
        }
        raw = general_archive(files, compressed=False)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.ba2"
            path.write_bytes(raw)
            ba2 = Ba2(str(path))
            by = ba2.by_extension()
            self.assertEqual(by.get("nif", 0), 2)
            self.assertEqual(by.get("dds", 0), 1)
            self.assertEqual(by.get("bgsm", 0), 1)
            self.assertEqual(by.get("txt", 0), 1)
            self.assertEqual(by.get("", 0), 1)


class TestBa2SummaryCLI(unittest.TestCase):
    def test_cli_runs(self):
        files = {"meshes\\test.nif": b"x" * 100, "textures\\test.dds": b"y" * 50}
        raw = general_archive(files, compressed=False)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.ba2"
            path.write_bytes(raw)
            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
            r = subprocess.run(
                [sys.executable, "-m", "fo4sf", "ba2-summary", str(path), "--largest", "2"],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("entries", r.stdout)
            self.assertIn(".nif=", r.stdout)
            self.assertIn("largest:", r.stdout)


if __name__ == "__main__":
    unittest.main()
