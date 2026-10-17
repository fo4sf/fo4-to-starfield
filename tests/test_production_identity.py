"""Exercise converter cache behavior without game assets or texture tools."""
import struct
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fo4sf.pipeline import Converter


def _bgsm(greyscale="", palette_color=0, palette_scale=1.0):
    head = bytearray(b"BGSM" + struct.pack("<II4f", 2, 3, 0.0, 0.0, 1.0, 1.0) + b"\x00" * 35)
    head[62] = palette_color
    def s(t):
        b = t.encode() + b"\0"
        return struct.pack("<I", len(b)) + b
    return bytes(head) + s("a/b_d.dds") + s("a/b_n.dds") + s("a/b_s.dds") + s(greyscale) + s("env/c.dds") + s("") \
        + b"\x00" * 40 + struct.pack("<fB", palette_scale, 0)


class ProductionCacheTests(unittest.TestCase):
    def setUp(self):
        self.converter = Converter.__new__(Converter)
        self.converter._materials = {}
        self.converter.stats = {"materials_ok": 0, "materials_fallback": 0}
        self.converter.material_errors = {}
        self.converter._convert_texture_set = Mock(side_effect=lambda stem, *args, **kwargs: stem + ".mat")

    def test_each_texture_changes_material_identity(self):
        c = self.converter
        original = c.texture_set_material("textures/a.dds", "textures/n.dds", "textures/s.dds")
        for inputs in [("textures/b.dds", "textures/n.dds", "textures/s.dds"),
                       ("textures/a.dds", "textures/n2.dds", "textures/s.dds"),
                       ("textures/a.dds", "textures/n.dds", "textures/s2.dds")]:
            self.assertNotEqual(original, c.texture_set_material(*inputs))
        self.assertEqual(c._convert_texture_set.call_count, 4)

    def test_slashes_and_case_share_one_conversion(self):
        c = self.converter
        first = c.texture_set_material("Textures/A.dds", "Textures/N.dds", "Textures/S.dds")
        self.assertEqual(first, c.texture_set_material("textures\\a.dds", "textures\\n.dds", "textures\\s.dds"))
        c._convert_texture_set.assert_called_once()

    def test_greyscale_palette_changes_material_identity(self):
        c = self.converter
        plain = c.texture_set_material("textures/a.dds", "textures/n.dds", "textures/s.dds")
        paletted = c.texture_set_material("textures/a.dds", "textures/n.dds", "textures/s.dds",
                                          greyscale="textures/p.dds")
        self.assertNotEqual(plain, paletted)
        again = c.texture_set_material("textures/a.dds", "textures/n.dds", "textures/s.dds",
                                       greyscale="textures/p.dds")
        self.assertEqual(paletted, again)
        self.assertEqual(c._convert_texture_set.call_count, 2)
        self.assertEqual(c._convert_texture_set.call_args.kwargs.get("greyscale"), "textures/p.dds")

    def test_failure_is_cached_and_different_texture_can_succeed(self):
        c = self.converter
        c._convert_texture_set.side_effect = [FileNotFoundError("missing normal"), "good.mat"]
        inputs = ("a.dds", "missing.dds", "s.dds")
        self.assertIsNone(c.texture_set_material(*inputs))
        self.assertIsNone(c.texture_set_material(*inputs))
        self.assertEqual(c.texture_set_material("a.dds", "present.dds", "s.dds"), "good.mat")
        self.assertEqual(c._convert_texture_set.call_count, 2)
        self.assertEqual(c.stats, {"materials_ok": 1, "materials_fallback": 1})
        self.assertEqual(len(c.material_errors), 1)

    def test_bgsm_greyscale_string_is_passed_to_texture_set(self):
        c = self.converter
        c.src = Mock()
        c.src.material = Mock(return_value=_bgsm(greyscale="a/b_p.dds", palette_color=1, palette_scale=0.12))
        self.assertEqual(c._convert_material("materials/x.bgsm"), "x.mat")
        self.assertEqual(c._convert_texture_set.call_args.kwargs.get("greyscale"), "a/b_p.dds")
        self.assertAlmostEqual(c._convert_texture_set.call_args.kwargs.get("palette_scale"), 0.12, places=5)

    def test_bgsm_without_greyscale_omits_the_palette(self):
        c = self.converter
        c.src = Mock()
        c.src.material = Mock(return_value=_bgsm())
        c._convert_material("materials/x.bgsm")
        self.assertIsNone(c._convert_texture_set.call_args.kwargs.get("greyscale"))

    def test_bgsm_greyscale_string_without_flag_is_not_a_palette(self):
        c = self.converter
        c.src = Mock()
        c.src.material = Mock(return_value=_bgsm(greyscale="Shared/Cubemaps/mipblur.dds", palette_color=0))
        c._convert_material("materials/concreteroadhw01.bgsm")
        self.assertIsNone(c._convert_texture_set.call_args.kwargs.get("greyscale"))

    def test_missing_palette_texture_is_a_failure(self):
        c = Converter.__new__(Converter)
        c.src = Mock()
        c.src.texture = Mock(side_effect=lambda p: None if "p.dds" in p.replace("\\", "/") else b"DDS")
        with self.assertRaises(FileNotFoundError) as err:
            c._convert_texture_set("x", "d.dds", "n.dds", "s.dds", greyscale="p.dds")
        self.assertIn("palette", str(err.exception).lower())
