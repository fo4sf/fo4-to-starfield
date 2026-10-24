"""Synthetic tests for Ba2.diagnostics()."""
import tempfile
import unittest
from pathlib import Path

from tests.ba2_fixture import general_archive
from src.fo4sf.ba2 import Ba2


class Ba2DiagnosticsTests(unittest.TestCase):
    def test_clean_archive(self):
        data = general_archive([("a.txt", b"hello"), ("b.nif", b"world")])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "clean.ba2"
            p.write_bytes(data)
            diag = Ba2(str(p)).diagnostics()
            self.assertEqual(diag["issues"], [])
            self.assertEqual(diag["zero_size_entries"], 0)
            self.assertFalse(diag["unsupported_compression"])

    def test_zero_size_and_duplicate(self):
        data = general_archive([("a.txt", b""), ("A.txt", b"dup"), ("large.bin", b"x" * 100)])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "issues.ba2"
            p.write_bytes(data)
            diag = Ba2(str(p)).diagnostics()
            self.assertGreater(diag["zero_size_entries"], 0)
            self.assertTrue(any("zero-size" in i for i in diag["issues"]))
            self.assertTrue(any("duplicate" in i for i in diag["issues"]))


if __name__ == "__main__":
    unittest.main()
