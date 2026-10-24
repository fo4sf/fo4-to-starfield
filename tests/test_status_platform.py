"""Offline tests for fo4sf status enhancements (platform, deps, git)."""
import os
import subprocess
import sys
import unittest
from pathlib import Path


class StatusEnvTest(unittest.TestCase):
    def test_status_prints_python_and_deps(self):
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-m", "fo4sf", "status"],
            cwd=repo,
            env={**os.environ, "PYTHONPATH": str(repo / "src")},
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        out = result.stdout
        self.assertIn("Python:", out)
        self.assertIn("numpy:", out)
        self.assertIn("PIL:", out)


if __name__ == "__main__":
    unittest.main()
