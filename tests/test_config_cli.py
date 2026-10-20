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


    def test_status_reports_path_existence(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            work = td_path / "work"
            work.mkdir()
            missing = td_path / "missing_dir"
            cfg = td_path / "config.toml"
            cfg.write_text(
                f"""
[fo4]
data_dirs = ["{missing.as_posix()}"]

[starfield]
data_dir = "{work.as_posix()}"

[paths]
work_dir = "{work.as_posix()}"
staging_dir = "{missing.as_posix()}"

[tools]
nifskope = "{missing.as_posix()}/tool.exe"
"""
            )
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["--config", str(cfg), "status"])
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("not found", out)
            self.assertIn("exists (dir)", out)
            self.assertIn("nifskope:", out)
            self.assertIn(str(work), out)


