"""Offline check that fo4sf --version prints an identification line."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestCLIVersion(unittest.TestCase):
    def test_version_flag(self):
        result = subprocess.run(
            [sys.executable, "-m", "fo4sf", "--version"],
            cwd=ROOT,
            env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("fo4sf ", result.stdout)
        self.assertTrue(result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
