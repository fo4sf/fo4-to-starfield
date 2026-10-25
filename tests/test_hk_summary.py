"""Synthetic tests for the hk-summary CLI (offline diagnostic for Havok packfiles)."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fo4sf.__main__ import main


class TestHkSummary(unittest.TestCase):
    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            missing = str(Path(d) / "nope.hkx")
            with patch("sys.stdout", new_callable=io.StringIO) as out, \
                 patch("sys.stderr", new_callable=io.StringIO):
                rc = main(["hk-summary", missing])
            self.assertEqual(rc, 1)
            self.assertIn("ERROR", out.getvalue())
            self.assertIn("not a file", out.getvalue())

    def test_bad_magic_json(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.hkx"
            bad.write_bytes(b"NOTAHKXX" + b"\0" * 32)
            with patch("sys.stdout", new_callable=io.StringIO) as out:
                rc = main(["hk-summary", "--json", str(bad)])
            self.assertEqual(rc, 1)
            data = json.loads(out.getvalue())
            self.assertEqual(len(data), 1)
            self.assertIn("error", data[0])
            self.assertIn("not a Havok packfile", data[0]["error"])


if __name__ == "__main__":
    unittest.main()
