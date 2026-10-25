"""Offline test: door-leaf collision half-extents floor at 0.05 and never write the old 0.02 crash float.

Issue #458 task 1. Offline / simulated only.
"""
import struct
import unittest

from fo4sf.sfcollision import MIN_LEAF_HALF, box_blob, CollisionError


class LeafClampTests(unittest.TestCase):
    def test_floor_is_005(self):
        self.assertEqual(MIN_LEAF_HALF, 0.05)

    def test_thin_box_floors_and_has_no_old_pattern(self):
        # Minimal valid template: 6168 bytes starting with the tag, identity rotation, plain box.
        # We only need enough for check_template and the pack sites used by LINEAR.
        template = bytearray(6168)
        template[0:8] = b"\x00\x00\x18\x18TAG0"
        # Identity rotation at the offsets check_template reads
        struct.pack_into("<3f", template, 528, 1.0, 0.0, 0.0)
        struct.pack_into("<3f", template, 544, 0.0, 1.0, 0.0)
        struct.pack_into("<3f", template, 560, 0.0, 0.0, 1.0)
        # Marker so the shape check passes
        template[100:112] = b"hknpBoxShape"

        thin = (0.01, 1.0, 1.0)  # one axis below the floor
        blob = box_blob(bytes(template), (0, 0, 0), thin)

        # The written half-extents must be at least the floor
        # LINEAR packs the feature vector; the old crash value must not appear
        self.assertNotIn(b"\x0a\xd7\xa3\x3c", blob)  # little-endian 0x3ca3d70a
        # Spot-check that a floored value is present (0.05 as float32)
        expected = struct.pack("<f", 0.05)
        self.assertIn(expected, blob)


if __name__ == "__main__":
    unittest.main()
