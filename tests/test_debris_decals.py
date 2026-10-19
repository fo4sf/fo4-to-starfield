"""Alpha-tested FO4 decal materials and vertex-alpha-faded decals become Starfield decals, not opaque cutouts.

BldFloorConcDebris02Alpha.bgsm (DebrisPileLargeConc01-06 shape Decals:10) is decal + alpha test, ref 6, no blend, and its
shape fades it with vertex alpha 0..48 (PC probe, 18 Oct). Drawn as an opaque cutout, its black transparent texels
showed as black patches on library, Cambridge Polymer and Fort Hagen floors. Synthetic bytes only.
"""
import struct
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fo4sf import convert_material as cm, nif, pipeline  # noqa: E402


def bgsm(blend=0, ref=128, test=0, decal=0):
    """v2 BGSM: header bytes 28..62 as in the probe's dump (alpha 1.0, blend src 6 dst 7), then nine texture strings."""
    head = b"BGSM" + struct.pack("<II4ff", 2, 3, 0, 0, 1, 1, 1.0)
    head += bytes([blend]) + struct.pack("<II", 6, 7) + bytes([ref, test, 1, 1, 0, 0, decal, 0])
    head += bytes(63 - len(head))
    strings = [b"Interiors\\Building\\X_d.dds", b"Interiors\\Building\\X_n.dds"] + [b""] * 7
    return head + b"".join(struct.pack("<I", len(s) + 1) + s + b"\0" for s in strings) + bytes(40)


class Src:
    def __init__(self, raw):
        self.raw = raw

    def material(self, name):
        return self.raw


def converter(raw):
    c = pipeline.Converter.__new__(pipeline.Converter)
    c.src, c._blend_cache, c._materials = Src(raw), {}, {}
    c.stats = {"materials_ok": 0, "materials_fallback": 0}
    c.material_errors = {}
    c.neutral = "materials\\fo4port\\_neutral.mat"
    return c


def bgsm_shape(name=b"materials\\Interiors\\Building\\X.BGSM", flags2=0x21, colors=()):
    n = nif.NifFile()
    shader = struct.pack("<IiI", 1, n.string_index(name), 0) + struct.pack("<iII", -1, 0x80400000, flags2)
    n.add_block("BSLightingShaderProperty", shader + bytes(40))
    return n, SimpleNamespace(shader_ref=0, colors=list(colors))


class BgsmOffsetsTests(unittest.TestCase):
    def test_probe_header_reads_as_decal_alpha_test_ref_6(self):
        b = cm.parse_bgsm(bgsm(ref=6, test=1, decal=1))
        self.assertEqual((b.alpha_blend, b.alpha_test, b.alpha_ref, b.decal), (False, True, 6, True))


class OverlayRoutingTests(unittest.TestCase):
    def test_alpha_tested_decal_is_an_overlay(self):
        self.assertTrue(converter(bgsm(ref=6, test=1, decal=1))._is_blended("materials\\a.bgsm"))

    def test_blended_material_is_still_an_overlay(self):
        self.assertTrue(converter(bgsm(blend=1))._is_blended("materials\\a.bgsm"))

    def test_plain_cutout_and_plain_decal_stay_surfaces(self):
        self.assertFalse(converter(bgsm(test=1))._is_blended("materials\\a.bgsm"))      # foliage cards, fences
        self.assertFalse(converter(bgsm(decal=1))._is_blended("materials\\b.bgsm"))     # opaque, depth-biased only


class VertexAlphaTests(unittest.TestCase):
    def test_peak_vertex_alpha_becomes_the_opacity_factor(self):
        src, s = bgsm_shape(colors=[(255, 255, 255, 0), (255, 255, 255, 48)])
        self.assertAlmostEqual(pipeline.vertex_alpha_scale(src.blocks[0], s), 48 / 255)

    def test_full_alpha_no_colours_or_no_flag_give_none(self):
        for flags2, colors in ((0x21, [(0, 0, 0, 255)]), (0x21, []), (0x01, [(0, 0, 0, 48)])):
            src, s = bgsm_shape(flags2=flags2, colors=colors)
            self.assertIsNone(pipeline.vertex_alpha_scale(src.blocks[0], s))

    def test_faded_decal_shape_gets_its_own_scaled_decal_material(self):
        c = converter(bgsm(ref=6, test=1, decal=1))
        c._convert_texture_set = Mock(return_value="materials\\fo4port\\vadecals\\a48\\x.mat")
        src, s = bgsm_shape(colors=[(255, 255, 255, 0), (255, 255, 255, 48)])
        self.assertEqual(c._shape_material(src, s), "materials\\fo4port\\vadecals\\a48\\x.mat")
        args, kw = c._convert_texture_set.call_args
        self.assertEqual(args[0], "vadecals/a48/interiors/building/x")
        self.assertTrue(kw["decal"])
        self.assertAlmostEqual(kw["opacity_scale"], 48 / 255)

    def test_scaled_output_never_shares_a_name_with_an_unscaled_source(self):
        # Codex P2: X.bgsm scaled and a literal X_a48.bgsm unscaled once both wrote decals/.../x_a48
        stems = []
        for bgsm_name, colors in ((b"materials\\Interiors\\Building\\X.BGSM", [(0, 0, 0, 48)]),
                                  (b"materials\\Interiors\\Building\\X_a48.BGSM", [(0, 0, 0, 255)])):
            c = converter(bgsm(blend=1))
            c._convert_texture_set = Mock(return_value="m.mat")
            src, s = bgsm_shape(name=bgsm_name, colors=colors)
            c._shape_material(src, s)
            stems.append(c._convert_texture_set.call_args[0][0])
        self.assertEqual(len(set(stems)), 2, stems)

    def test_fully_transparent_shape_is_skipped(self):
        # Codex P2: peak vertex alpha 0 must not become a 16/255 overlay
        src, s = bgsm_shape(colors=[(255, 255, 255, 0)] * 3)
        self.assertEqual(pipeline.vertex_alpha_scale(src.blocks[0], s), 0.0)
        c = converter(bgsm(ref=6, test=1, decal=1))
        c._convert_texture_set = Mock(return_value="m.mat")
        self.assertIsNone(c._shape_material(src, s))
        c._convert_texture_set.assert_not_called()

    def test_unfaded_decal_keeps_the_shared_material(self):
        c = converter(bgsm(blend=1))
        c._convert_texture_set = Mock(return_value="materials\\fo4port\\decals\\x.mat")
        src, s = bgsm_shape(colors=[(255, 255, 255, 255)])
        c._shape_material(src, s)
        args, kw = c._convert_texture_set.call_args
        self.assertEqual(args[0], "decals/interiors/building/x")
        self.assertNotIn("opacity_scale", kw)


if __name__ == "__main__":
    unittest.main()
