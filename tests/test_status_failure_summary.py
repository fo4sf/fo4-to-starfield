"""Tests that fo4sf status reports failure-summary.json when present."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fo4sf.__main__ import cmd_status


class StatusFailureSummaryTests(unittest.TestCase):
    def test_prints_summary_when_present(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            manifest = base / "manifest.json"
            manifest.write_text(json.dumps([{"type": "static", "fidelity_tier": "T1"}]))
            summary = {
                "attempted": 10,
                "successes": 8,
                "success_percent": 80.0,
                "total_failures": 2,
                "unique_reasons": 1,
                "top": [
                    {"reason": "missing texture", "count": 2, "percent": 100.0},
                ],
            }
            (base / "failure-summary.json").write_text(json.dumps(summary))

            # Fake config that points at our temp dir
            class FakeCfg:
                def get(self, key, default=None):
                    if key == "paths":
                        return {"staging_dir": str(base)}
                    return {}

            with patch("fo4sf.__main__.load_config", return_value=FakeCfg()):
                # Capture stdout
                from io import StringIO
                import sys
                old = sys.stdout
                sys.stdout = buf = StringIO()
                try:
                    rc = cmd_status(type("A", (), {"config": None, "manifest": None})())
                finally:
                    sys.stdout = old
                out = buf.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("Latest batch: 8/10 succeeded (80.0%), 2 failures", out)
            self.assertIn("Unique failure reasons: 1", out)
            self.assertIn("missing texture", out)


if __name__ == "__main__":
    unittest.main()
