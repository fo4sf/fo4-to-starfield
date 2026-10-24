"""Synthetic check that fo4sf status reports the running Python version against the project minimum."""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fo4sf.__main__ import MIN_PYTHON, cmd_status  # noqa: E402


class StatusPythonTests(unittest.TestCase):
    def test_status_reports_python_against_minimum(self):
        args = type("A", (), {"config": None, "manifest": None})()
        dummy_cfg = {"fo4": {"data_dirs": []}, "starfield": {}, "paths": {}}
        buf = io.StringIO()
        with patch("fo4sf.__main__.load_config", return_value=dummy_cfg), redirect_stdout(buf):
            rc = cmd_status(args)
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("Python:", out)
        major, minor = sys.version_info[:2]
        self.assertIn(f"{major}.{minor}", out)
        meets = "meets" if sys.version_info >= MIN_PYTHON else "below"
        self.assertIn(meets, out)


if __name__ == "__main__":
    unittest.main()
