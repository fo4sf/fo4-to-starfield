"""Tests for config loading and CLI (synthetic; no real game paths)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fo4sf.config import ConfigError, load_config
from fo4sf.__main__ import main

try:
    import tomllib
except ImportError:
    tomllib = None


@unittest.skipUnless(tomllib, "tomllib requires Python 3.11+")
class TestConfig(unittest.TestCase):
    def test_missing_file(self):
        with self.assertRaises(ConfigError):
            load_config("/nonexistent/config.toml")

    def test_load_example_structure(self):
        # Write a minimal synthetic config
        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / "config.toml"
            cfg_path.write_text(
                """
[fo4]
data_dirs = ["/tmp/fo4"]
version = "1.10.163"

[starfield]
data_dir = "/tmp/sf"
version = "1.16.244"

[paths]
work_dir = "/tmp/work"
staging_dir = "/tmp/staging"
"""
            )
            cfg = load_config(cfg_path)
            self.assertEqual(len(cfg["fo4"]["data_dirs"]), 1)
            self.assertTrue(str(cfg["paths"]["work_dir"]).endswith("work"))


@unittest.skipUnless(tomllib, "tomllib requires Python 3.11+")
class TestCLI(unittest.TestCase):
    def test_status_missing_config(self):
        with tempfile.TemporaryDirectory() as td:
            os.chdir(td)
            rc = main(["status"])
            self.assertEqual(rc, 1)

    def test_status_ok(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            cfg.write_text('[paths]\nwork_dir = "/tmp/w"\n')
            with patch("sys.stdout") as mock_out:
                rc = main(["--config", str(cfg), "status"])
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
