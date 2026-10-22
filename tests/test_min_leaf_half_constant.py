"""Guard that the door-leaf half-extent floor remains 0.05.

0.02 (IEEE 0x3ca3d70a) was the value that appeared as an index in every Red Rocket crash dump.
Offline constant check only.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import sfcollision  # noqa: E402


class MinLeafHalfConstantTests(unittest.TestCase):
    def test_floor_is_005_not_002(self):
        self.assertEqual(sfcollision.MIN_LEAF_HALF, 0.05)
        # 0.02's bit pattern must not be the constant
        import struct
        self.assertNotEqual(struct.pack("<f", sfcollision.MIN_LEAF_HALF), struct.pack("<f", 0.02))


if __name__ == "__main__":
    unittest.main()
