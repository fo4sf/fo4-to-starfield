"""Tests for the oracles listing CLI (synthetic; no game assets)."""
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from fo4sf.__main__ import main


class TestOraclesCli(unittest.TestCase):
    def test_oracles_lists_scripts(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["oracles"])
        out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("offline oracles", out)
        self.assertIn("collision_bounds.py", out)
        self.assertIn("oracles", out)
        # At least a few real oracles should appear
        self.assertGreater(out.count(".py"), 5)

    def test_oracles_outside_repo(self):
        with patch("fo4sf.__main__._repo_root", return_value=None):
            rc = main(["oracles"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
