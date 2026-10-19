"""Synthetic tests for Ba2.by_extension."""
import os
import tempfile
import unittest

from tests.ba2_fixture import general_archive
from fo4sf.ba2 import Ba2


class ByExtensionTests(unittest.TestCase):
    def test_counts_extensions(self):
        entries = {
            "mesh.nif": b"nifdata",
            "texture.dds": b"ddsdata",
            "another.nif": b"more",
            "noext": b"plain",
            "path\\to\\file.HKX": b"anim",
        }
        data = general_archive(entries)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            stats = a.by_extension()
            self.assertEqual(stats.get("nif"), 2)
            self.assertEqual(stats.get("dds"), 1)
            self.assertEqual(stats.get("hkx"), 1)
            self.assertEqual(stats.get(""), 1)
            self.assertEqual(sum(stats.values()), 5)



if __name__ == "__main__":
    unittest.main()
