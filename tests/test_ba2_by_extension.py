"""Tests for Ba2.by_extension."""
import tempfile
import unittest
from pathlib import Path

from fo4sf.ba2 import Ba2
from tests.ba2_fixture import general_archive


class TestBa2ByExtension(unittest.TestCase):
    def test_mixed_extensions(self):
        entries = {
            "meshes/chair.nif": b"nifdata",
            "textures/chair_d.dds": b"ddsdata",
            "materials/chair.bgsm": b"bgsm",
            "readme.txt": b"txt",
            "noext": b"none",
            "dir.with.dots/file": b"nodot",
            "another/path\\with\\back.nif": b"back",
        }
        raw = general_archive(entries, compressed=False)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.ba2"
            path.write_bytes(raw)
            ba2 = Ba2(str(path))
            counts = ba2.by_extension()
            self.assertEqual(counts.get("nif"), 2)
            self.assertEqual(counts.get("dds"), 1)
            self.assertEqual(counts.get("bgsm"), 1)
            self.assertEqual(counts.get("txt"), 1)
            self.assertEqual(counts.get(""), 2)  # noext and dir.with.dots/file
            self.assertEqual(sum(counts.values()), len(entries))


if __name__ == "__main__":
    unittest.main()
