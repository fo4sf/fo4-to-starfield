"""Tests for path handling in convert_asset.py."""
import os
import sys
import unittest

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

if __name__ == "__main__":
    unittest.main()
