"""Synthetic tests for status command environment diagnostics."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class StatusEnvTests(unittest.TestCase):
    def test_status_prints_git_and_python(self) -> None:
        """cmd_status includes short git rev and python version when run from the repo."""
        if sys.version_info < (3, 11):
            self.skipTest("tomllib requires Python 3.11+")
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            cfg.write_text(
                '[fo4]\ndata_dirs = []\n[starfield]\ndata_dir = ""\n'
                '[paths]\nwork_dir = ""\nstaging_dir = ""\n'
            )
            # Run as module so imports resolve
            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
            proc = subprocess.run(
                [sys.executable, "-m", "fo4sf", "--config", str(cfg), "status"],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = proc.stdout
            self.assertIn("fo4-to-starfield status", out)
            self.assertIn("git revision:", out)
            self.assertIn("python:", out)
            self.assertIn(sys.version.split()[0], out)


if __name__ == "__main__":
    unittest.main()
