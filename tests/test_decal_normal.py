"""Synthetic test for decal flat normal generation (issue #204)."""
import os
import sys
import unittest
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

try:
    import numpy as np
    from fo4sf import textures
except ImportError:
    np = None


class DecalNormalTests(unittest.TestCase):
    @unittest.skipIf(np is None, "numpy required")
    def test_unorm_128_is_flat_signed_zero(self):
        """The pipeline must pass unorm 128 (not zeros) so write_rg8_snorm emits (0, 0)."""
        r = np.full((4, 4), 128, dtype=np.uint8)
        g = np.full((4, 4), 128, dtype=np.uint8)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "n.dds")
            textures.write_rg8_snorm(path, r, g)
            data = open(path, "rb").read()
            h = textures.read_dds_header(data)
            px = np.frombuffer(data[h["data_offset"]:h["data_offset"] + h["width"] * h["height"] * 2], np.int8)
            self.assertTrue(np.all(px == 0), "flat normal must be signed zero")

    @unittest.skipIf(np is None, "numpy required")
    def test_zeros_are_not_flat(self):
        """Document that the previous bug produced (-127, -127)."""
        r = np.zeros((4, 4), dtype=np.int8)
        g = np.zeros((4, 4), dtype=np.int8)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "n.dds")
            textures.write_rg8_snorm(path, r, g)
            data = open(path, "rb").read()
            h = textures.read_dds_header(data)
            px = np.frombuffer(data[h["data_offset"]:h["data_offset"] + h["width"] * h["height"] * 2], np.int8)
            self.assertTrue(np.any(px != 0))


if __name__ == "__main__":
    unittest.main()
