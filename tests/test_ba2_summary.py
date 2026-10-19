"""Synthetic tests for Ba2.summary."""
import os
import tempfile
import unittest

from tests.ba2_fixture import general_archive
from fo4sf.ba2 import Ba2


class SummaryTests(unittest.TestCase):
    def test_totals_and_extensions(self):
        entries = {
            "small.txt": b"a" * 10,
            "medium.bin": b"b" * 100,
            "large.dat": b"c" * 1000,
            "notes.txt": b"d" * 50,
        }
        data = general_archive(entries, compressed=True)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            s = a.summary()
            self.assertEqual(s["entries"], 4)
            self.assertEqual(s["general"], 4)
            self.assertEqual(s["textures"], 0)
            self.assertEqual(s["total_unpacked"], 10 + 100 + 1000 + 50)
            self.assertGreater(s["total_packed"], 0)
            self.assertLess(s["total_packed"], s["total_unpacked"])
            self.assertEqual(s["extensions"], {"txt": 2, "bin": 1, "dat": 1})

    def test_empty_archive_rejected(self):
        # Fixture always has entries; empty is rejected by validator
        data = general_archive({})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "empty.ba2")
            with open(path, "wb") as f:
                f.write(data)
            with self.assertRaises(Exception):
                Ba2(path)


if __name__ == "__main__":
    unittest.main()
