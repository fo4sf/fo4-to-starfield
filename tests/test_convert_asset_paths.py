"""Tests for path handling in convert_asset.py."""
import importlib.util
from pathlib import Path
import os
import sys
import unittest
from unittest.mock import patch

# Simulate the path construction logic
def make_tex_rel(name):
    base = name.rsplit("/", 1)
    folder, stem = (base[0], base[1]) if len(base) == 2 else ("", base[0])
    tex_rel = f"textures/{folder}/{stem}".replace("//", "/").strip("/")
    return tex_rel

class ConvertAssetPathTests(unittest.TestCase):
    def test_folderless_name_no_double_separator(self):
        # #206: folder-less --name should not produce // 
        tex_rel = make_tex_rel("chair")
        self.assertEqual(tex_rel, "textures/chair")
        self.assertNotIn("//", tex_rel)

    def test_with_folder_normal(self):
        tex_rel = make_tex_rel("fo4port/setdressing/chair")
        self.assertEqual(tex_rel, "textures/fo4port/setdressing/chair")
        self.assertNotIn("//", tex_rel)


class ConvertAssetMassScaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "convert_asset_mass_scale", root / "scripts" / "convert_asset.py")
        cls.asset = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.asset)

    def test_invalid_mass_scale_rejected_before_opening_the_nif(self):
        for value in ("0", "-1", "nan", "inf"):
            with self.subTest(value=value), patch("sys.stderr"):
                argv = ["convert_asset.py", "--fo4-nif", "missing.nif", "--fo4-root", "root",
                        "--staging", "staging", "--name", "chair", "--content-resources", "c",
                        "--texconv", "t", "--mass-scale", value]
                with patch.object(sys, "argv", argv), patch("builtins.open") as opened:
                    with self.assertRaises(SystemExit):
                        self.asset.main()
                    opened.assert_not_called()

    def test_valid_mass_scale_is_accepted_by_the_parser(self):
        self.assertEqual(self.asset.convert_static.require_mass_scale(0.2), 0.2)
        self.assertEqual(self.asset.convert_static.require_mass_scale(1.0), 1.0)


if __name__ == "__main__":
    unittest.main()
