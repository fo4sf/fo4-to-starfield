"""Reproduce the 0.02 door-leaf clamp offline.

A synthetic two-leaf door has a thin axis of ~0.014 m half-extent.
After conversion the written NIF must contain the 0.05 floor and must not contain the bit pattern of 0.02.
The test fails on the parent of the #455 fix (ff6f27e2) and passes on main.
Offline only; no game data.
"""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fo4sf import convert_static, nif, sfcollision  # noqa: E402
from test_door_two_panels import door_nif, two_leaves, donor  # noqa: E402
from test_collision import fake_template  # noqa: E402

# Bit pattern of IEEE-754 float 0.02 (little-endian)
PATTERN_002 = struct.pack("<f", 0.02)
PATTERN_005 = struct.pack("<f", 0.05)


class LeafFloorReproTests(unittest.TestCase):
    def test_thin_leaf_gets_005_floor_never_002(self):
        src = door_nif(two_leaves())
        template = fake_template()
        donor_blob = donor()
        files, _pivot, _bounds = convert_static.convert_door(
            nif.serialize(src),
            "test_leaf",
            ["mat", "mat", "mat"],
            unit_scale=1.0 / 70.0,
            collision_template=template,
            leaf_physics_donor=donor_blob,
        )
        nif_bytes = files["meshes/test_leaf.nif"]
        self.assertNotIn(
            PATTERN_002,
            nif_bytes,
            "float 0.02 bit pattern must not appear; the leaf half-extent floor must be 0.05",
        )
        self.assertIn(
            PATTERN_005,
            nif_bytes,
            "the 0.05 floor must be written as the thin-axis half-extent",
        )
        # Also confirm the constant matches what the converter uses
        self.assertEqual(sfcollision.MIN_LEAF_HALF, 0.05)


if __name__ == "__main__":
    unittest.main()
