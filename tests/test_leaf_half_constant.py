"""Offline check that the door-leaf minimum half-extent stays at the post-crash value.

The Red Rocket crashes were traced to 0.02 written as a half-extent that the engine read as an index
(0x3ca3d70a). The constant is now 0.05; this test keeps it from silently returning to the old value.
See docs/spikes/red-rocket-crash-bisect.md and #458.
"""
import unittest

from src.fo4sf.sfcollision import MIN_LEAF_HALF, MIN_HALF


class LeafHalfConstantTest(unittest.TestCase):
    def test_leaf_half_is_post_crash_value(self):
        self.assertEqual(MIN_LEAF_HALF, 0.05)
        # the general minimum is smaller; leaves use the raised floor
        self.assertLess(MIN_HALF, MIN_LEAF_HALF)
        self.assertNotEqual(MIN_LEAF_HALF, 0.02)


if __name__ == "__main__":
    unittest.main()
