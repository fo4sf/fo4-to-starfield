"""Tests for the summary helpers added to Ba2 and NifFile."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from fo4sf.ba2 import Ba2, Ba2Error
from fo4sf.nif import NifFile, parse as parse_nif

# Reuse the fixture helpers
from tests.ba2_fixture import general_archive


class TestBa2Summary(unittest.TestCase):
    def test_summary_counts(self):
        data = general_archive({
            "meshes/test.nif": b"NIFDATA",
            "textures/test.dds": b"DDS" * 10,
        })
        with tempfile.NamedTemporaryFile(suffix=".ba2", delete=False) as f:
            f.write(data)
            path = f.name
        try:
            ba2 = Ba2(path)
            s = ba2.summary()
            self.assertEqual(s["entries"], 2)
            self.assertEqual(s["general"], 2)
            self.assertEqual(s["textures"], 0)
            self.assertEqual(s["version"], 2)
            self.assertEqual(s["kind"], "GNRL")
        finally:
            os.unlink(path)

    def test_validate_rejects_empty(self):
        # An empty archive should fail validation
        data = general_archive({})
        with tempfile.NamedTemporaryFile(suffix=".ba2", delete=False) as f:
            f.write(data)
            path = f.name
        try:
            with self.assertRaises(Ba2Error):
                Ba2(path)
        finally:
            os.unlink(path)


class TestNifSummary(unittest.TestCase):
    def test_summary_on_empty_like(self):
        # Minimal valid-looking NIF bytes are hard; just confirm method exists and runs on a constructed object
        n = NifFile()
        n.blocks = [b"a", b"b"]
        n.block_types = ["NiNode", "BSTriShape"]
        n.block_type_index = [0, 1]
        n.strings = [b"test"]
        n.footer = b"END"
        s = n.summary()
        self.assertEqual(s["blocks"], 2)
        self.assertEqual(s["strings"], 1)
        self.assertEqual(s["footer_bytes"], 3)
        self.assertIn("NiNode", s["type_counts"])


if __name__ == "__main__":
    unittest.main()
