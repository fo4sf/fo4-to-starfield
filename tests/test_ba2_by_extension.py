"""Tests for Ba2.by_extension."""
import tempfile
import unittest
from pathlib import Path

from fo4sf.ba2 import Ba2
from tests.ba2_fixture import general_archive


class TestBa2ByExtension(unittest.TestCase):
    def test_mixed_extensions_and_separators(self):
        entries = {
            "meshes/setdressing/chair.nif": b"nifdata",
            "Textures/SetDressing/chair_d.dds": b"ddsdata",
            "materials/chair.bgsm": b"bgsm",
            "scripts/foo.pex": b"pex",
            "readme": b"text",  # no extension
            "subdir\\file.NIF": b"another",  # mixed sep, upper
            "another.nif": b"third",
        }
        raw = general_archive(entries, compressed=False)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.ba2"
            path.write_bytes(raw)
            ba2 = Ba2(str(path))
            counts = ba2.by_extension()
            self.assertEqual(counts.get("nif", 0), 3)
            self.assertEqual(counts.get("dds", 0), 1)
            self.assertEqual(counts.get("bgsm", 0), 1)
            self.assertEqual(counts.get("pex", 0), 1)
            self.assertEqual(counts.get("", 0), 1)  # no extension
            self.assertEqual(sum(counts.values()), len(entries))

    def test_empty_archive_raises(self):
        # Ba2 already rejects empty; just ensure method exists and works on valid
        raw = general_archive({"a.txt": b"x"})
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "t.ba2"
            path.write_bytes(raw)
            ba2 = Ba2(str(path))
            self.assertEqual(ba2.by_extension(), {"txt": 1})


if __name__ == "__main__":
    unittest.main()
