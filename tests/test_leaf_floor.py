"""Offline reproduction of the 0.02 door-leaf clamp (issue #458 task 1).

A thin synthetic door leaf has a collision half-extent floored at 0.05 on main.
The written blob must contain no IEEE-754 little-endian 0.02 (0x3ca3d70a), the value
every Red Rocket crash dump read as an index. The test fails on the parent of #455.
"""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fo4sf import convert_static, nif, sfcollision  # noqa: E402
from test_collision import fake_template  # noqa: E402
from test_door_two_panels import door_nif, IDENTITY, quat_z, collision_targets  # noqa: E402

CRASH_FLOAT = struct.unpack("<f", bytes.fromhex("0ad7a33c"))[0]  # 0.02
CRASH_BYTES = bytes.fromhex("0ad7a33c")  # little-endian 0x3ca3d70a


class LeafFloorReproTests(unittest.TestCase):
    def test_thin_leaf_floors_to_0_05_and_contains_no_crash_float(self):
        # 2 FO4 units deep (~0.029 m) leaf: half-extent would be ~0.014 without the floor.
        f = door_nif([("Leaf", (0, 0, 0), IDENTITY, [(0, quat_z(0)), (1, quat_z(-90))], None)])
        count = len([s for s in nif.fo4_trishapes(f) if s.positions and s.triangles])
        files, _offset, _bounds = convert_static.convert_door(
            nif.serialize(f), "fo4port/doors/thinleaf",
            ["Materials\\x.mat"] * count, collision_template=fake_template(),
        )
        (blob,) = collision_targets(nif.parse(files["meshes/fo4port/doors/thinleaf.nif"])).values()
        centre, half = sfcollision.read_box(blob)
        # Floor is 0.05 on every axis that would otherwise be thinner.
        self.assertGreaterEqual(min(half), 0.05)
        self.assertAlmostEqual(half[0], 0.05, places=6)
        self.assertEqual(sfcollision.MIN_LEAF_HALF, 0.05)
        # No written float equals the old 0.02 crash value.
        self.assertNotIn(CRASH_BYTES, blob)
        # Also check unpacked floats for good measure.
        for i in range(0, len(blob) - 3, 4):
            val = struct.unpack_from("<f", blob, i)[0]
            self.assertNotAlmostEqual(val, CRASH_FLOAT, places=6)


if __name__ == "__main__":
    unittest.main()
