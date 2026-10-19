"""Synthetic tests for Ba2.summary size totals."""
import os
import tempfile
import unittest

from tests.ba2_fixture import general_archive
from fo4sf.ba2 import Ba2


class SummarySizesTests(unittest.TestCase):
    def test_totals_uncompressed(self):
        entries = {
            "a.txt": b"a" * 10,
            "b.bin": b"b" * 100,
        }
        data = general_archive(entries, compressed=False)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            s = a.summary()
            self.assertEqual(s["entries"], 2)
            self.assertEqual(s["general"], 2)
            self.assertEqual(s["textures"], 0)
            self.assertEqual(s["general_unpacked"], 110)
            self.assertEqual(s["general_packed"], 110)
            self.assertEqual(s["total_unpacked"], 110)
            self.assertEqual(s["total_packed"], 110)

    def test_totals_compressed(self):
        entries = {"large.dat": b"c" * 1000}
        data = general_archive(entries, compressed=True)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "comp.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            s = a.summary()
            self.assertEqual(s["general_unpacked"], 1000)
            self.assertGreater(s["general_packed"], 0)
            self.assertLess(s["general_packed"], 1000)
            self.assertEqual(s["total_unpacked"], 1000)
            self.assertEqual(s["total_packed"], s["general_packed"])


if __name__ == "__main__":
    unittest.main()
