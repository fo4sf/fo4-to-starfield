"""Tests for BA2 size estimate helper."""
import unittest
import tempfile
from pathlib import Path

from fo4sf.ba2 import Ba2
from tests.ba2_fixture import general_archive


class TestBa2Estimate(unittest.TestCase):
    def test_total_unpacked_estimate_minimal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "min.ba2"
            data = general_archive({"dummy.txt": b"x"})
            path.write_bytes(data)
            ba2 = Ba2(str(path))
            self.assertEqual(ba2.total_unpacked_estimate(), 1)

    def test_total_unpacked_estimate_simple(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "simple.ba2"
            entries = {"meshes/test.nif": b"hello world" * 10}
            data = general_archive(entries)
            path.write_bytes(data)
            ba2 = Ba2(str(path))
            est = ba2.total_unpacked_estimate()
            self.assertGreater(est, 0)
            self.assertEqual(est, len(entries["meshes/test.nif"]))


if __name__ == "__main__":
    unittest.main()
