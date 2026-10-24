"""Tests for Ba2.by_extension."""
import tempfile
import unittest
from pathlib import Path

from fo4sf.ba2 import Ba2
from tests.ba2_fixture import general_archive


class TestBa2ByExtension(unittest.TestCase):
    def test_mixed_extensions(self):
        files = {
            "meshes/foo.nif": b"nifdata",
            "textures/bar.dds": b"ddsdata",
            "meshes/baz.nif": b"more",
            "readme.txt": b"text",
            "noext": b"plain",
        }
        raw = general_archive(files, compressed=False)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.ba2"
            path.write_bytes(raw)
            ba2 = Ba2(str(path))
            counts = ba2.by_extension()
            self.assertEqual(counts.get("nif"), 2)
            self.assertEqual(counts.get("dds"), 1)
            self.assertEqual(counts.get("txt"), 1)
            self.assertEqual(counts.get("(none)"), 1)
            self.assertEqual(sum(counts.values()), 5)

    def test_empty(self):
        # Minimal archive with one entry that has no extension
        raw = general_archive({"file": b"x"}, compressed=False)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.ba2"
            path.write_bytes(raw)
            ba2 = Ba2(str(path))
            counts = ba2.by_extension()
            self.assertEqual(counts, {"(none)": 1})


if __name__ == "__main__":
    unittest.main()
