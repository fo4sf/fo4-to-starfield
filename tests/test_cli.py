"""Tests for the fo4sf CLI entry point."""
import os
import sys
import unittest
from io import StringIO
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.__main__ import main  # noqa: E402
from fo4sf import __version__  # noqa: E402


class TestCLI(unittest.TestCase):
    def test_version_command(self):
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            code = main(["version"])
        self.assertEqual(code, 0)
        output = mock_out.getvalue()
        self.assertIn(f"fo4sf {__version__}", output)
        self.assertIn("Python", output)


if __name__ == "__main__":
    unittest.main()
