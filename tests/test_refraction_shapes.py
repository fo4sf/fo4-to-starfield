"""FO4 refraction shapes (heat shimmer, water streams) are skipped, not drawn with their distortion normal map as colour.

Synthetic NIF blocks only: a BSLightingShaderProperty without a .bgsm (FO4 layout: shader type, name, extra data list,
controller, flags1, flags2, UV offset, UV scale, texture set ref) and its BSShaderTextureSet.
"""
import struct
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fo4sf import nif, pipeline  # noqa: E402

HEAT_SHIMMER_FLAGS1 = 0x80408000     # VltGearDoor01 m_HeatShimmer:0 (ZBuffer test, own emit, refraction)
SURFACE_FLAGS1 = 0x80400281          # V111RadScanner01:0 (specular, env map, cast shadows, own emit, ZBuffer test)


def lighting_shape(flags1, textures, name=b"", n_extra=0):
    """A NIF holding one lighting shader property (block 0) and its texture set (block 1); returns (nif, shape)."""
    n = nif.NifFile()
    name_idx = n.string_index(name) if name else -1
    shader = struct.pack("<Ii I", 1, name_idx, n_extra) + struct.pack(f"<{n_extra}i", *range(5, 5 + n_extra))
    shader += struct.pack("<iII", -1, flags1, 0x1) + struct.pack("<4f", 0, 0, 1, 1) + struct.pack("<i", 1)
    n.add_block("BSLightingShaderProperty", shader)
    texset = struct.pack("<I", len(textures)) + b"".join(struct.pack("<I", len(t)) + t for t in textures)
    n.add_block("BSShaderTextureSet", texset)
    return n, SimpleNamespace(shader_ref=0)


def converter():
    c = pipeline.Converter.__new__(pipeline.Converter)    # no archives, texconv or templates
    c.neutral = "materials\\fo4port\\_neutral.mat"
    c.texture_set_material = Mock(return_value="materials\\fo4port\\texsets\\x.mat")
    c.material = Mock(return_value="materials\\fo4port\\x.mat")
    c._is_blended = Mock(return_value=False)
    return c


SMOKE = [b"textures\\Effects\\SmokeVapor01Tile_n.dds", b"textures\\Effects\\SmokeVapor01Tile_n.dds"] + [b""] * 8
SURFACE = [b"textures\\a\\x_d.dds", b"textures\\a\\x_n.dds", b"", b"", b"", b"", b"", b"textures\\a\\x_s.dds", b"", b""]
PALETTE = [b"textures\\a\\x_d.dds", b"textures\\a\\x_n.dds", b"", b"textures\\a\\x_p.dds",
           b"", b"", b"", b"textures\\a\\x_s.dds", b"", b""]


class RefractionShapeTests(unittest.TestCase):
    def test_refraction_shape_is_skipped_without_converting_its_normal_map(self):
        c = converter()
        src, shape = lighting_shape(HEAT_SHIMMER_FLAGS1, SMOKE)
        self.assertIsNone(c._shape_material(src, shape))
        c.texture_set_material.assert_not_called()

    def test_flag_is_found_after_extra_data_refs(self):
        c = converter()
        src, shape = lighting_shape(HEAT_SHIMMER_FLAGS1, SMOKE, n_extra=2)
        self.assertIsNone(c._shape_material(src, shape))
        c.texture_set_material.assert_not_called()

    def test_texture_set_surface_without_the_flag_still_converts(self):
        c = converter()
        src, shape = lighting_shape(SURFACE_FLAGS1, SURFACE, n_extra=1)
        self.assertEqual(c._shape_material(src, shape), "materials\\fo4port\\texsets\\x.mat")
        c.texture_set_material.assert_called_once_with("textures\\a\\x_d.dds", "textures\\a\\x_n.dds", "textures\\a\\x_s.dds")

    def test_same_textures_without_the_flag_are_not_skipped(self):
        # the flag decides, not the texture names: an unflagged shape keeps its (odd) texture set as before
        c = converter()
        src, shape = lighting_shape(HEAT_SHIMMER_FLAGS1 & ~pipeline.SLSF1_REFRACTION, SMOKE)
        self.assertEqual(c._shape_material(src, shape), "materials\\fo4port\\texsets\\x.mat")

    def test_greyscale_flag_passes_slot_3_as_palette(self):
        c = converter()
        src, shape = lighting_shape(SURFACE_FLAGS1 | pipeline.SLSF1_GREYSCALE_TO_PALETTE_COLOR, PALETTE)
        self.assertEqual(c._shape_material(src, shape), "materials\\fo4port\\texsets\\x.mat")
        c.texture_set_material.assert_called_once_with(
            "textures\\a\\x_d.dds", "textures\\a\\x_n.dds", "textures\\a\\x_s.dds",
            greyscale="textures\\a\\x_p.dds")

    def test_slot_3_without_the_flag_is_not_a_palette(self):
        # slot 3 is also height; only GreyscaleToPalette_Color (0x10) bakes it
        c = converter()
        src, shape = lighting_shape(SURFACE_FLAGS1, PALETTE)
        self.assertEqual(c._shape_material(src, shape), "materials\\fo4port\\texsets\\x.mat")
        c.texture_set_material.assert_called_once_with(
            "textures\\a\\x_d.dds", "textures\\a\\x_n.dds", "textures\\a\\x_s.dds")

    def test_bgsm_shape_is_left_to_its_material_file(self):
        # with a .bgsm the material file, not the NIF block, sets the shader in FO4; no FO4 .bgsm sets refraction
        c = converter()
        src, shape = lighting_shape(HEAT_SHIMMER_FLAGS1, SURFACE, name=b"Materials\\A\\X.BGSM")
        self.assertEqual(c._shape_material(src, shape), "materials\\fo4port\\x.mat")
        c.material.assert_called_once_with("Materials\\A\\X.BGSM")


if __name__ == "__main__":
    unittest.main()
