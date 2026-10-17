"""Tests for config loading and status CLI."""
import os
import tempfile
import unittest
from pathlib import Path

from fo4sf.config import load_config, status_summary
from fo4sf.__main__ import main


class TestConfig(unittest.TestCase):
    def test_missing_config_returns_empty(self):
        self.assertEqual(load_config("/nonexistent.toml"), {})

    def test_status_summary_empty(self):
        s = status_summary({})
        self.assertIn("(not set)", s)

    def test_status_summary_with_values(self):
        cfg = {
            "fo4": {"data_dirs": ["/fo4"]},
            "starfield": {"data_dir": "/sf"},
            "paths": {"work_dir": "/work", "staging_dir": "/staging"},
        }
        s = status_summary(cfg)
        self.assertIn("/fo4", s)
        self.assertIn("/sf", s)
        self.assertIn("/work", s)
        self.assertIn("/staging", s)

    def test_cli_status_no_config(self):
        # Should not raise
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            rc = main(["status"])
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
