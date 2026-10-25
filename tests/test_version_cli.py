"""Test the --version flag on the fo4sf CLI."""
import unittest
from unittest.mock import patch
import io
import sys

from fo4sf import __version__
from fo4sf.__main__ import main


class TestVersionCLI(unittest.TestCase):
    def test_version_flag(self):
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            with self.assertRaises(SystemExit) as cm:
                main(["--version"])
            self.assertEqual(cm.exception.code, 0)
            out = fake_out.getvalue()
            self.assertIn(__version__, out)
            self.assertIn("fo4sf", out)


if __name__ == "__main__":
    unittest.main()
