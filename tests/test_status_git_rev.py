"""Test that fo4sf status reports a short git revision when run from a checkout."""
import subprocess
import sys
import unittest
from pathlib import Path


class StatusGitRevTests(unittest.TestCase):
    def test_status_shows_git_rev(self):
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-m", "fo4sf", "status"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Config may fail on Python < 3.11; git line must still appear
        self.assertIn("git:", result.stdout, result.stderr)
        if "tomllib requires Python 3.11+" not in result.stderr:
            self.assertEqual(result.returncode, 0, result.stderr)
        # At least 7 hex chars
        lines = [ln.strip() for ln in result.stdout.splitlines() if "git:" in ln]
        self.assertTrue(lines)
        rev = lines[0].split(":", 1)[1].strip()
        self.assertTrue(len(rev) >= 7 and all(c in "0123456789abcdef" for c in rev.lower()))


if __name__ == "__main__":
    unittest.main()
