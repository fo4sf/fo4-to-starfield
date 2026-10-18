"""Synthetic tests for Ba2 size estimate helpers."""
import os
import tempfile
import unittest

from tests.ba2_fixture import general_archive
from fo4sf.ba2 import Ba2


class SizeEstimateTests(unittest.TestCase):
    def test_total_and_estimates(self):
        entries = {
            "a.txt": b"a" * 50,
            "b.bin": b"b" * 150,
        }
        data = general_archive(entries, compressed=True)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sizes.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            self.assertEqual(a.total_unpacked_estimate(), 200)
            est = a.size_estimates()
            self.assertEqual(est["total_unpacked"], 200)
            self.assertEqual(est["general_unpacked"], 200)
            self.assertEqual(est["texture_unpacked"], 0)
            self.assertEqual(est["entry_count"], 2)
            self.assertEqual(est["average_unpacked"], 100)
            self.assertGreater(est["total_packed"], 0)


if __name__ == "__main__":
    unittest.main()
