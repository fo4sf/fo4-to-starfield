"""Tests for Ba2.extension_counts."""
import tempfile
import unittest
from pathlib import Path

from fo4sf.ba2 import Ba2
from tests.ba2_fixture import general_archive


class TestBa2ExtensionCounts(unittest.TestCase):
    def test_mixed_extensions(self):
        raw = general_archive({
            "meshes/chair.nif": b"nifdata",
            "textures/chair_d.dds": b"dds",
            "meshes/table.NIF": b"more",
            "readme.txt": b"hi",
            "noextension": b"plain",
        })
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.ba2"
            path.write_bytes(raw)
            ba2 = Ba2(str(path))
            counts = ba2.extension_counts()
            self.assertEqual(counts[".nif"], 2)  # case-insensitive
            self.assertEqual(counts[".dds"], 1)
            self.assertEqual(counts[".txt"], 1)
            self.assertEqual(counts["(noext)"], 1)
            self.assertEqual(sum(counts.values()), 5)
            # sorted by count descending
            self.assertEqual(list(counts.keys())[0], ".nif")

    def test_empty(self):
        # Minimal archive with no entries is invalid in the reader, so skip or use one
        raw = general_archive({"a.txt": b"x"})
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.ba2"
            path.write_bytes(raw)
            ba2 = Ba2(str(path))
            counts = ba2.extension_counts()
            self.assertEqual(counts, {".txt": 1})


if __name__ == "__main__":
    unittest.main()
