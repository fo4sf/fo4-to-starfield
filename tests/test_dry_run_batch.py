"""Synthetic tests for convert_batch.py --dry-run (no game files)."""
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "scripts", "convert_batch.py")


class DryRunTests(unittest.TestCase):
    def test_dry_run_appears_in_help(self):
        out = subprocess.check_output([sys.executable, SCRIPT, "--help"], text=True, stderr=subprocess.STDOUT)
        self.assertIn("--dry-run", out)
        self.assertIn("list the models that would be converted", out)

    def test_dry_run_exits_early_without_required_args_when_names_empty(self):
        # --dry-run still needs the required args to parse, but we can check it fails cleanly on missing required
        # before any conversion work. A full mock is left for a follow-up; this guards the flag.
        r = subprocess.run([sys.executable, SCRIPT, "--dry-run"], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("required", r.stderr.lower() + r.stdout.lower())


if __name__ == "__main__":
    unittest.main()
