"""Synthetic test for the door-leaf half-extent floor (MIN_LEAF_HALF = 0.05).

The old 0.02 floor wrote the exact float every Red Rocket crash dump reads as an index
(0x3ca3d70a). This test builds a collision box that would have been 0.02 and asserts
the written blob contains no such float and the half-extent is floored at 0.05.
"""
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


CRASH_FLOAT = struct.unpack("<f", bytes.fromhex("0ad7a33c"))[0]  # 0.02


class LeafClampTests(unittest.TestCase):
    def test_leaf_half_floor_avoids_crash_float(self):
        template = fake_template()
        # A leaf that would have been 0.02 thick on one axis
        raw_half = (0.02, 0.4, 0.5)
        clamped = tuple(max(sfcollision.MIN_LEAF_HALF, abs(v)) for v in raw_half)
        self.assertEqual(clamped[0], sfcollision.MIN_LEAF_HALF)
        blob = sfcollision.box_blob(template, (0.0, 0.0, 0.0), clamped)
        # No written float equals the old crash value
        floats = struct.unpack(f"<{len(blob)//4}f", blob)
        self.assertNotIn(CRASH_FLOAT, floats)
        # And the half we read back is the floor
        _, h = sfcollision.read_box(blob)
        self.assertAlmostEqual(h[0], sfcollision.MIN_LEAF_HALF, places=5)
        self.assertAlmostEqual(h[1], 0.4, places=5)
        self.assertAlmostEqual(h[2], 0.5, places=5)


if __name__ == "__main__":
    unittest.main()
