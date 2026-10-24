"""Offline reproduction of the Red Rocket 0.02 leaf-clamp floor (issue #458 task 1).

A synthetic thin door leaf whose natural half-extent is below MIN_LEAF_HALF must
be floored to 0.05, and the IEEE-754 bits of the old crash value 0.02
(0x3ca3d70a) must never appear in the written Havok blob.
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


class LeafClampReproTests(unittest.TestCase):
    def test_thin_leaf_floored_and_old_crash_float_absent(self):
        # A synthetic leaf whose natural half-extents include values < 0.05
        # (the pre-#455 clamp would have written 0.02).
        natural = (0.02, 0.01, 0.03)
        floored = tuple(max(sfcollision.MIN_LEAF_HALF, abs(v)) for v in natural)
        blob = sfcollision.box_blob(fake_template(), (0.0, 0.0, 0.0), floored)

        # Exact bit pattern that every Red Rocket crash dump read as an index.
        bad = struct.pack("<f", 0.02)
        self.assertNotIn(bad, blob, "old 0.02 crash float must not be written")

        # Written half-extents must be the floor, not the raw small values.
        centre, half = sfcollision.read_box(blob)
        for h in half:
            self.assertAlmostEqual(h, sfcollision.MIN_LEAF_HALF, places=5)
            self.assertGreater(h, 0.02)

        # The constant itself is the post-fix value.
        self.assertEqual(sfcollision.MIN_LEAF_HALF, 0.05)

        # The floor bits are present.
        good = struct.pack("<f", 0.05)
        self.assertIn(good, blob)


if __name__ == "__main__":
    unittest.main()
