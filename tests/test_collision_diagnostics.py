"""Offline unit tests for collision_diagnostics. No game data."""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf.collision_diagnostics import report_clamped_halves, has_non_finite
from fo4sf import sfcollision


def fake_template():
    b = bytearray(sfcollision.BLOB_SIZE)
    b[0:8] = b"\x00\x00\x18\x18TAG0"
    b[100:112] = b"hknpBoxShape"
    struct.pack_into("<3f", b, 528, 1.0, 0.0, 0.0)
    struct.pack_into("<3f", b, 544, 0.0, 1.0, 0.0)
    struct.pack_into("<3f", b, 560, 0.0, 0.0, 1.0)
    return bytes(b)


class TestCollisionDiagnostics(unittest.TestCase):
    def test_report_clamped_leaf(self):
        # 0.02 is below MIN_LEAF_HALF 0.05
        clamped = report_clamped_halves([(0.02, 0.5, 0.5)], leaf=True)
        self.assertEqual(len(clamped), 1)
        orig, after = clamped[0]
        self.assertEqual(orig, (0.02, 0.5, 0.5))
        self.assertEqual(after, (0.05, 0.5, 0.5))

    def test_no_clamp_when_above_floor(self):
        clamped = report_clamped_halves([(0.1, 0.1, 0.1)], leaf=True)
        self.assertEqual(clamped, [])

    def test_non_finite(self):
        self.assertTrue(has_non_finite([1.0, float("nan")]))
        self.assertTrue(has_non_finite([float("inf")]))
        self.assertFalse(has_non_finite([0.0, 1.0, -0.5]))

    def test_leaf_clamp_in_blob_avoids_0x3ca3d70a(self):
        """Synthetic leaf half-extent 0.02 is raised to 0.05; no written float is the crash pattern 0x3ca3d70a."""
        BAD = 0x3ca3d70a  # float 0.02 as little-endian uint32
        template = fake_template()
        # Apply leaf floor the same way convert_static does for door leaves
        half = tuple(max(sfcollision.MIN_LEAF_HALF, v) for v in (0.02, 0.4, 0.4))
        blob = sfcollision.box_blob(template, (0.0, 0.0, 0.0), half)
        # Scan every 4-byte word for the bad pattern
        for off in range(0, len(blob) - 3, 4):
            word = struct.unpack_from("<I", blob, off)[0]
            self.assertNotEqual(word, BAD, f"found 0.02 float at offset {off}")
        # And the recovered half is the floor
        _, recovered = sfcollision.read_box(blob)
        self.assertAlmostEqual(recovered[0], 0.05, places=5)
        self.assertAlmostEqual(recovered[1], 0.4, places=5)
        self.assertAlmostEqual(recovered[2], 0.4, places=5)


if __name__ == "__main__":
    unittest.main()
