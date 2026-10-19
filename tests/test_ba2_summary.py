"""Synthetic tests for Ba2.summary."""
import os
import tempfile
import unittest

from tests.ba2_fixture import general_archive
from fo4sf.ba2 import Ba2


class SummaryTests(unittest.TestCase):
    def test_counts_and_sizes(self):
        entries = {
            "small.txt": b"a" * 10,
            "medium.bin": b"b" * 100,
            "large.dat": b"c" * 1000,
        }
        data = general_archive(entries, compressed=True)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            s = a.summary()
            self.assertEqual(s["total_entries"], 3)
            self.assertEqual(s["gnrl_count"], 3)
            self.assertEqual(s["dx10_count"], 0)
            self.assertEqual(s["gnrl_unpacked"], 1110)
            self.assertEqual(s["total_unpacked"], 1110)
            self.assertGreater(s["total_packed"], 0)
            self.assertEqual(s["kind"], "GNRL")
            self.assertIn("path", s)

    def test_uncompressed(self):
        data = general_archive({"only.txt": b"x" * 50}, compressed=False)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "one.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            s = a.summary()
            self.assertEqual(s["total_unpacked"], 50)
            self.assertEqual(s["total_packed"], 50)  # uncompressed packed == unpacked


if __name__ == "__main__":
    unittest.main()
