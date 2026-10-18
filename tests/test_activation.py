"""Synthetic tests for activation field extraction. No game data."""
import os
import struct
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf import activation  # noqa: E402


class ActivationParseTests(unittest.TestCase):
    def test_linked_and_activate(self):
        fields = [
            (b"XLKR", struct.pack("<II", 0x12345678, 0x00000ABC)),
            (b"XAPR", struct.pack("<If", 0x00000DEF, 1.5)),
            (b"XAPD", b"\x01"),
        ]
        result = activation.parse_activation(fields)
        self.assertEqual(result["linked_refs"], [(0x12345678, 0x00000ABC)])
        self.assertEqual(result["activate_parents"], [(0x00000DEF, 1.5)])
        self.assertEqual(result["xapd"], 1)
        self.assertIsNone(result["enable_parent"])
        self.assertEqual(result["scripts"], [])

    def test_enable_parent(self):
        fields = [(b"XESP", struct.pack("<II", 0x11111111, 0x00000001))]
        result = activation.parse_activation(fields)
        self.assertEqual(result["enable_parent"], (0x11111111, 1))


if __name__ == "__main__":
    unittest.main()
