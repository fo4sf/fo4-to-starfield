"""Tests for manifest summary (synthetic data only)."""
import json
import tempfile
import unittest
from pathlib import Path

from fo4sf.manifest import ManifestError, load_manifest, summarize_manifest


class TestManifest(unittest.TestCase):
    def test_missing(self):
        with self.assertRaises(ManifestError):
            load_manifest("/no/such/manifest.json")

    def test_list_form(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "manifest.json"
            p.write_text(json.dumps([
                {"type": "STAT", "fidelity_tier": "T1"},
                {"type": "STAT", "fidelity_tier": "T2"},
                {"type": "MISC", "tier": "T1"},
            ]))
            items = load_manifest(p)
            self.assertEqual(len(items), 3)
            s = summarize_manifest(items)
            self.assertEqual(s["total"], 3)
            self.assertEqual(s["by_type"]["STAT"], 2)
            self.assertEqual(s["by_tier"]["T1"], 2)

    def test_items_form(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "m.json"
            p.write_text(json.dumps({"items": [{"record_type": "CELL"}]}))
            items = load_manifest(p)
            self.assertEqual(len(items), 1)
            s = summarize_manifest(items)
            self.assertEqual(s["by_type"]["CELL"], 1)

    def test_null_item_is_manifest_error_with_index(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "m.json"
            p.write_text(json.dumps([None]), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, r"item 0"):
                load_manifest(p)

    def test_null_item_in_items_form_is_manifest_error(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "m.json"
            p.write_text(json.dumps({"items": [{"type": "STAT"}, None]}), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, r"item 1"):
                load_manifest(p)


    def test_asset_mix_counts(self):
        items = [
            {"type": "STAT", "door": True, "shapes": 4},
            {"type": "STAT", "load_door": True, "shapes": 2},
            {"type": "MISC", "movable": True, "shapes": 1},
            {"type": "STAT"},
        ]
        s = summarize_manifest(items)
        self.assertEqual(s["doors"], 1)
        self.assertEqual(s["load_doors"], 1)
        self.assertEqual(s["movables"], 1)
        self.assertEqual(s["total_shapes"], 7)
        self.assertAlmostEqual(s["avg_shapes"], 1.8)


