"""Offline test: thin door-leaf collision never writes the 0.02 (0x3ca3d70a) crash float.

Builds on the existing LeafBoxFloorTests. Converts a synthetic flat leaf and asserts the
written Havok blob contains no float equal to 0.02 and the half-extent is floored at 0.05.
"""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fo4sf import convert_static, nif, sfcollision  # noqa: E402
from test_collision import fake_template  # noqa: E402
from test_door_two_panels import door_nif, IDENTITY, quat_z  # noqa: E402


CRASH_FLOAT = struct.unpack("<f", struct.pack("<I", 0x3ca3d70a))[0]


def collision_targets(model):
    """Minimal extractor: find bhkPhysicsSystem blobs in the NIF (copied pattern)."""
    out = {}
    for i, block in enumerate(model.blocks):
        if model.type_of(i) == "bhkPhysicsSystem" and len(block) > 4:
            out[i] = block[4:]
    return out


class NoCrashFloatTest(unittest.TestCase):
    def test_thin_leaf_writes_no_0_02(self):
        f = door_nif([("Leaf", (0, 0, 0), IDENTITY, [(0, quat_z(0)), (1, quat_z(-90))], None)])
        count = len([s for s in nif.fo4_trishapes(f) if s.positions and s.triangles])
        files, _off, _bounds = convert_static.convert_door(
            nif.serialize(f), "fo4port/doors/thinleaf",
            ["Materials\\x.mat"] * count, collision_template=fake_template()
        )
        model = nif.parse(files["meshes/fo4port/doors/thinleaf.nif"])
        blobs = collision_targets(model)
        self.assertEqual(len(blobs), 1)
        blob = next(iter(blobs.values()))
        # no crash float anywhere in the blob
        words = struct.unpack(f"<{len(blob) // 4}I", blob)
        self.assertNotIn(0x3ca3d70a, words)
        # and the half is the floor
        _c, half = sfcollision.read_box(blob)
        self.assertAlmostEqual(half[0], 0.05, places=5)
        self.assertEqual(sfcollision.MIN_LEAF_HALF, 0.05)


if __name__ == "__main__":
    unittest.main()
