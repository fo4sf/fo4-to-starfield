"""Synthetic tests for Ba2.by_extension."""
import os
import tempfile
import unittest

from fo4sf.ba2 import Ba2
from tests.ba2_fixture import general_archive


class ByExtensionTests(unittest.TestCase):
    def test_general_extensions(self):
        data = {
            "meshes/foo.nif": b"nifdata",
            "textures/bar.dds": b"ddsdata",
            "scripts/baz.psc": b"psc",
            "noext": b"raw",
        }
        blob = general_archive(data)
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(blob)
            path = f.name
        try:
            a = Ba2(path)
            stats = a.by_extension()
            self.assertEqual(stats[".nif"]["count"], 1)
            self.assertEqual(stats[".nif"]["unpacked"], 7)
            self.assertEqual(stats[".dds"]["count"], 1)
            self.assertEqual(stats[".psc"]["count"], 1)
            self.assertEqual(stats["(none)"]["count"], 1)
            self.assertEqual(stats["(none)"]["unpacked"], 3)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
