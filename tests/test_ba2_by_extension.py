"""Tests for Ba2.by_extension()."""
import tempfile
import unittest
from pathlib import Path

from fo4sf.ba2 import Ba2
from tests.ba2_fixture import general_archive


class TestBa2ByExtension(unittest.TestCase):
    def test_basic_counts(self):
        entries = {
            "textures/setdressing/x_d.dds": b"dds",
            "meshes/foo.nif": b"nif",
            "meshes/bar.NIF": b"nif2",
            "materials/foo.bgsm": b"mat",
            "noext": b"plain",
            "dir.with.dot/file.bgsm": b"mat2",
            "UPPER.DDS": b"dds2",
        }
        raw = general_archive(entries)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.ba2"
            path.write_bytes(raw)
            ba2 = Ba2(str(path))
            counts = ba2.by_extension()
            self.assertEqual(counts.get(".dds"), 2)
            self.assertEqual(counts.get(".nif"), 2)
            self.assertEqual(counts.get(".bgsm"), 2)
            self.assertEqual(counts.get(""), 1)
            self.assertEqual(sum(counts.values()), 7)

    def test_mixed_separators(self):
        entries = {
            r"textures\setdressing\x_d.dds": b"a",
            "meshes/foo.nif": b"b",
        }
        raw = general_archive(entries)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.ba2"
            path.write_bytes(raw)
            ba2 = Ba2(str(path))
            counts = ba2.by_extension()
            self.assertEqual(counts[".dds"], 1)
            self.assertEqual(counts[".nif"], 1)


if __name__ == "__main__":
    unittest.main()
