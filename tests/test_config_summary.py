"""Synthetic tests for the config-summary CLI command."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fo4sf.__main__ import main


class TestConfigSummary(unittest.TestCase):
    def test_missing_config(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("sys.stderr") as mock_err:
                rc = main(["--config", str(Path(td) / "nope.toml"), "config-summary"])
            self.assertEqual(rc, 1)

    def test_valid_config_prints_keys(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            cfg.write_text("""
[fo4]
data_dirs = ["/tmp/fo4"]

[starfield]
data_dir = "/tmp/sf"

[paths]
work_dir = "/tmp/work"
""")
            # Capture stdout
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["--config", str(cfg), "config-summary"])
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("[fo4] keys:", out)
            self.assertIn("data_dirs", out)
            self.assertIn("[paths] keys:", out)
            # Should not print full path values
            self.assertNotIn("/tmp/fo4", out)


if __name__ == "__main__":
    unittest.main()
