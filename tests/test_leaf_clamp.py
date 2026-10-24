"""Test that door-leaf collision half-extents are floored at 0.05, never writing the old 0.02 crash value."""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import sfcollision  # noqa: E402


def fake_template():
    b = bytearray(sfcollision.BLOB_SIZE)
    b[0:8] = b"\x00\x00\x18\x18TAG0"
    b[100:112] = b"hknpBoxShape"
    struct.pack_into("<3f", b, 528, 1.0, 0.0, 0.0)
    struct.pack_into("<3f", b, 544, 0.0, 1.0, 0.0)
    struct.pack_into("<3f", b, 560, 0.0, 0.0, 1.0)
    return bytes(b)


CRASH_FLOAT = 0.02
CRASH_BITS = 0x3CA3D70A


class LeafClampTests(unittest.TestCase):
    def test_leaf_half_floor_not_crash_value(self):
        """A thin leaf (half-extent 0.01 on one axis) is written with floor 0.05, never 0.02."""
        tmpl = fake_template()
        # Simulate the door-leaf call site in convert_static
        thin_half = (0.01, 0.5, 0.8)
        floored = tuple(max(sfcollision.MIN_LEAF_HALF, abs(v)) for v in thin_half)
        blob = sfcollision.box_blob(tmpl, (0.0, 0.0, 0.0), floored)
        _, written_half = sfcollision.read_box(blob)
        self.assertAlmostEqual(written_half[0], sfcollision.MIN_LEAF_HALF, places=6)
        self.assertGreater(written_half[0], CRASH_FLOAT)
        # No float word in the blob equals the crash bit pattern
        for off in range(0, len(blob) - 3, 4):
            bits, = struct.unpack_from("<I", blob, off)
            self.assertNotEqual(bits, CRASH_BITS, f"crash float 0.02 written at offset {off}")


if __name__ == "__main__":
    unittest.main()
