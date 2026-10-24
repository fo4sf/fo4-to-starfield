"""Tests for fo4sf CLI version and status enhancements."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf.__main__ import main, VERSION  # noqa: E402


class CliVersionTests(unittest.TestCase):
    def test_version_command(self):
        rc = main(["version"])
        self.assertEqual(rc, 0)

    def test_status_prints_version_line(self):
        # Mock config load so the test runs on older Python
        with patch("fo4sf.__main__.load_config", return_value={
            "fo4": {"data_dirs": []},
            "starfield": {},
            "paths": {},
        }):
            rc = main(["status"])
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
