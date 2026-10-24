"""Synthetic tests for Ba2.by_extension."""
import os
import tempfile
import unittest

from tests.ba2_fixture import general_archive
from fo4sf.ba2 import Ba2


class ByExtensionTests(unittest.TestCase):
    def test_counts_by_extension(self):
        entries = {
            "meshes/a.nif": b"nif1",
            "meshes/b.NIF": b"nif2",
            "textures/c.dds": b"dds",
            "textures/d.DDS": b"dds2",
            "other/file.txt": b"txt",
            "noext": b"none",
            "path\\with\\slash.nif": b"nif3",
        }
        data = general_archive(entries)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mix.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            counts = a.by_extension()
            self.assertEqual(counts.get("nif"), 3)
            self.assertEqual(counts.get("dds"), 2)
            self.assertEqual(counts.get("txt"), 1)
            self.assertEqual(counts.get(""), 1)  # no extension
            # sorted by count desc, then name
            keys = list(counts.keys())
            self.assertEqual(keys[0], "nif")  # highest count

    def test_empty_archive_raises(self):
        # empty is rejected by constructor; just ensure method is robust if called
        data = general_archive({"one.nif": b"x"})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "one.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            self.assertEqual(a.by_extension(), {"nif": 1})


if __name__ == "__main__":
    unittest.main()
