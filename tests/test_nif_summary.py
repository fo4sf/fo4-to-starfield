"""Tests for NifFile.summary diagnostic helper.

Offline only. Verifies the summary counts blocks, types and strings correctly
on a minimal synthetic NIF.
"""
import unittest

from fo4sf.nif import NifFile


class TestNifSummary(unittest.TestCase):
    def test_empty_summary(self):
        nif = NifFile()
        s = nif.summary()
        self.assertEqual(s["blocks"], 0)
        self.assertEqual(s["block_types"], 0)
        self.assertEqual(s["strings"], 0)
        self.assertEqual(s["type_counts"], {})
        self.assertEqual(s["footer_bytes"], 0)

    def test_with_blocks_and_strings(self):
        nif = NifFile(bs_version=130)
        nif.add_block("NiNode", b"node-data")
        nif.add_block("BSTriShape", b"shape-data")
        nif.add_block("NiNode", b"another-node")
        nif.string_index(b"Hello")
        nif.string_index(b"World")
        nif.footer = b"footer"
        s = nif.summary()
        self.assertEqual(s["bs_version"], 130)
        self.assertEqual(s["blocks"], 3)
        self.assertEqual(s["block_types"], 2)
        self.assertEqual(s["strings"], 2)
        self.assertEqual(s["type_counts"]["NiNode"], 2)
        self.assertEqual(s["type_counts"]["BSTriShape"], 1)
        self.assertEqual(s["footer_bytes"], 6)


if __name__ == "__main__":
    unittest.main()
