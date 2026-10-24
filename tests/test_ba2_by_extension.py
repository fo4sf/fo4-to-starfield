"""Tests for Ba2.by_extension and the ba2-summary CLI."""
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from fo4sf.ba2 import Ba2
from fo4sf.__main__ import cmd_ba2_summary
from tests.ba2_fixture import general_archive


class TestBa2ByExtension(unittest.TestCase):
    def test_counts_extensions(self):
        files = {
            "meshes/foo.nif": b"nifdata",
            "meshes/bar.nif": b"more",
            "textures/a.dds": b"tex",
            "textures/b.DDS": b"tex2",
            "scripts/noext": b"script",
            "misc/file.txt": b"text",
        }
        raw = general_archive(files, compressed=False)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.ba2"
            path.write_bytes(raw)
            ba2 = Ba2(str(path))
            counts = ba2.by_extension()
            self.assertEqual(counts.get("nif"), 2)
            self.assertEqual(counts.get("dds"), 2)
            self.assertEqual(counts.get("txt"), 1)
            self.assertEqual(counts.get("(none)"), 1)
            self.assertEqual(sum(counts.values()), 6)

    def test_cli_summary(self):
        files = {"a.nif": b"x", "b.dds": b"y"}
        raw = general_archive(files, compressed=False)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.ba2"
            path.write_bytes(raw)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cmd_ba2_summary(type("A", (), {"archive": str(path), "largest": 0})())
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("entries: 2", out)
            self.assertIn(".nif: 1", out)
            self.assertIn(".dds: 1", out)


if __name__ == "__main__":
    unittest.main()
