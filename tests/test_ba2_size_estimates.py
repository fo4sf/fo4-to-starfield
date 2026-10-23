"""Tests for Ba2.size_estimates and summary sizes."""
import os
import tempfile
import unittest
from pathlib import Path

from fo4sf.ba2 import Ba2
from tests.ba2_fixture import general_archive


class TestBa2SizeEstimates(unittest.TestCase):
    def test_empty_like_minimal(self):
        # One small uncompressed entry
        data = b"hello"
        raw = general_archive({"test.txt": data}, compressed=False)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.ba2"
            path.write_bytes(raw)
            ba2 = Ba2(str(path))
            est = ba2.size_estimates()
            self.assertEqual(est["entries"], 1)
            self.assertEqual(est["packed_bytes"], len(data))
            self.assertEqual(est["unpacked_bytes"], len(data))
            # summary includes the sizes
            sm = ba2.summary()
            self.assertEqual(sm["packed_bytes"], len(data))
            self.assertEqual(sm["unpacked_bytes"], len(data))

    def test_compressed(self):
        data = b"a" * 1000  # compressible
        raw = general_archive({"test.txt": data}, compressed=True)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.ba2"
            path.write_bytes(raw)
            ba2 = Ba2(str(path))
            est = ba2.size_estimates()
            self.assertEqual(est["entries"], 1)
            self.assertLess(est["packed_bytes"], est["unpacked_bytes"])
            self.assertEqual(est["unpacked_bytes"], len(data))
            sm = ba2.summary()
            self.assertLess(sm["packed_bytes"], sm["unpacked_bytes"])
            self.assertEqual(sm["unpacked_bytes"], len(data))


if __name__ == "__main__":
    unittest.main()
