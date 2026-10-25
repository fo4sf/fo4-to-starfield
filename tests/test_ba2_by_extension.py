"""Tests for Ba2.by_extension()."""
import unittest
from pathlib import Path
import tempfile
import struct

from fo4sf.ba2 import Ba2, Ba2Error


class TestBa2ByExtension(unittest.TestCase):
    def test_by_extension_counts(self):
        # Minimal synthetic uncompressed general BA2 with a few files
        # Header: magic, version=1, type=GNRL, file_count=3, name_table_offset
        # Then file entries, then names.
        # For simplicity we use the real reader path; a tiny valid archive is hard without the full writer,
        # so we test the method logic via a mock-like subclass if needed.
        # Direct unit of the method:
        class Dummy:
            entries = [
                type("E", (), {"name": r"textures\foo.DDS"})(),
                type("E", (), {"name": r"meshes\bar.NIF"})(),
                type("E", (), {"name": r"meshes\bar.nif"})(),
                type("E", (), {"name": "noext"})(),
            ]
        # Bind the method
        counts = Ba2.by_extension(Dummy())
        self.assertEqual(counts.get("dds"), 1)
        self.assertEqual(counts.get("nif"), 2)
        self.assertEqual(counts.get(""), 1)

    def test_empty(self):
        class Dummy:
            entries = []
        self.assertEqual(Ba2.by_extension(Dummy()), {})


if __name__ == "__main__":
    unittest.main()
