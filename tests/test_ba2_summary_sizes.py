"""Synthetic tests for Ba2.summary size totals."""
import os
import tempfile
import unittest

from tests.ba2_fixture import general_archive
from fo4sf.ba2 import Ba2


class SummarySizeTests(unittest.TestCase):
    def test_summary_includes_size_totals(self):
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
            self.assertEqual(s["total_unpacked"], 10 + 100 + 1000)
            self.assertGreater(s["total_packed"], 0)
            self.assertEqual(s["gnrl_unpacked"], s["total_unpacked"])
            self.assertIn("path", s)
            self.assertEqual(s["kind"], "GNRL")


if __name__ == "__main__":
    unittest.main()
