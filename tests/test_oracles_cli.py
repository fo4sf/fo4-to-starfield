"""Synthetic tests for the fo4sf oracles CLI subcommand."""
import os
import sys
import unittest
from io import StringIO
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import __main__ as cli  # noqa: E402


class OraclesCliTests(unittest.TestCase):
    def test_oracles_lists_scripts(self):
        buf = StringIO()
        with patch("sys.stdout", buf):
            rc = cli.main(["oracles"])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("Offline oracles", out)
        self.assertIn("collision_bounds", out)
        self.assertIn("oracle script(s)", out)

    def test_oracles_requires_checkout(self):
        with patch.object(cli, "_repo_root", return_value=None):
            buf = StringIO()
            with patch("sys.stderr", buf):
                rc = cli.main(["oracles"])
            self.assertEqual(rc, 1)
            self.assertIn("not running from a checkout", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
