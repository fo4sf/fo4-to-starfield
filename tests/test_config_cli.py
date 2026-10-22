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
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as td:
            os.chdir(td)
            try:
                rc = main(["status"])
                self.assertEqual(rc, 1)
            finally:
                os.chdir(old)
        self.assertEqual(os.getcwd(), old)

    def test_status_ok(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            cfg.write_text('[paths]\nwork_dir = "/tmp/w"\n')
            with patch("sys.stdout") as mock_out:
                rc = main(["--config", str(cfg), "status"])
            self.assertEqual(rc, 0)

    def test_status_reports_directory_existence(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("fo4a", "sf", "work"):
                (root / name).mkdir()
            cfg = root / "config.toml"
            cfg.write_text(
                "[fo4]\n"
                f'data_dirs = ["{(root / "fo4a").as_posix()}", "{(root / "fo4b").as_posix()}"]\n'
                "[starfield]\n"
                f'data_dir = "{(root / "sf").as_posix()}"\n'
                "[paths]\n"
                f'work_dir = "{(root / "work").as_posix()}"\n'
                f'staging_dir = "{(root / "staging").as_posix()}"\n'
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["--config", str(cfg), "status"])
            text = out.getvalue()
        self.assertEqual(rc, 0)
        lines = {line.strip() for line in text.splitlines()}
        self.assertIn("Fallout 4 data dirs: 2 configured", lines)
        self.assertTrue(any(l.startswith("[0]") and "fo4a" in l and l.endswith("(exists)") for l in lines), text)
        self.assertTrue(any(l.startswith("[1]") and "fo4b" in l and l.endswith("(MISSING)") for l in lines), text)
        self.assertTrue(any(l.startswith("Starfield data dir:") and l.endswith("(exists)") for l in lines), text)
        self.assertTrue(any(l.startswith("work_dir:") and l.endswith("(exists)") for l in lines), text)
        self.assertTrue(any(l.startswith("staging_dir:") and l.endswith("(MISSING or not created)") for l in lines), text)

    def test_status_reports_unset_directories(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            cfg.write_text("[fo4]\ndata_dirs = []\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["--config", str(cfg), "status"])
        self.assertEqual(rc, 0)
        lines = {line.strip() for line in out.getvalue().splitlines()}
        self.assertIn("Fallout 4 data dirs: 0 configured", lines)
        self.assertIn("Starfield data dir: missing", lines)
        self.assertIn("work_dir: missing", lines)
        self.assertIn("staging_dir: missing", lines)

    def test_status_explicit_missing_manifest_is_nonzero(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            cfg.write_text('[paths]\nwork_dir = "/tmp/w"\n')
            missing = Path(td) / "no-manifest.json"
            with patch("sys.stdout"), patch("sys.stderr"):
                rc = main(["--config", str(cfg), "status", "--manifest", str(missing)])
            self.assertEqual(rc, 1)

    def test_status_explicit_invalid_manifest_is_nonzero(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            cfg.write_text('[paths]\nwork_dir = "/tmp/w"\n')
            bad = Path(td) / "manifest.json"
            bad.write_text("{", encoding="utf-8")
            with patch("sys.stdout"), patch("sys.stderr"):
                rc = main(["--config", str(cfg), "status", "--manifest", str(bad)])
            self.assertEqual(rc, 1)

    def test_status_auto_missing_manifest_is_zero(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            work = Path(td) / "work"
            work.mkdir()
            cfg.write_text(f'[paths]\nwork_dir = "{work.as_posix()}"\n')
            with patch("sys.stdout"):
                rc = main(["--config", str(cfg), "status"])
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
