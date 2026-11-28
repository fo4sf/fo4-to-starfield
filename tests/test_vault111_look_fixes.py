"""Offline regressions for Vault 111 restricted-area floor decal fixes and PluginSpike XESP/dedup switches.

Tests:
1. parse_ni_alpha decodes FO4 NiAlphaProperty blend/test bits + threshold safely.
2. Inline BSLightingShaderProperty shapes with SLSF1_DECAL / SLSF1_DYNAMIC_DECAL or NiAlphaProperty blend
   route through texture_set_material(decal=True), not opaque MetalIronCast01.
3. Inline NiAlphaProperty alpha-test shapes (without decal/blend) route through alpha_test=True cutouts.
4. shape_normal_offset_m lifts planar (dz < 0.01) decal shapes by DECAL_NORMAL_OFFSET_M along vertex normals
   in convert_static.shape_to_mesh while leaving non-decals / non-planar shapes at 0.0.
5. Built PluginSpike.dll (via Ensure/dotnet build) honors opt-in DEDUP_EXACT_REFS=1 and RESOLVE_ENABLE_PARENTS=1
   in lighting.json while keeping default output unchanged when those keys are omitted.
"""
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import typing
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fo4sf import convert_static, nif, pipeline, sfmesh  # noqa: E402


def _make_inline_shape(flags1: int, textures, flags2: int = 0x1,
                       colors=(), ni_alpha_flags: int = None, ni_alpha_thresh: int = 128):
    n = nif.NifFile()
    shader = (
        struct.pack("<IiI", 1, -1, 0)
        + struct.pack("<iII", -1, flags1, flags2)
        + struct.pack("<4f", 0.0, 0.0, 1.0, 1.0)
        + struct.pack("<i", 1)
    )
    n.add_block("BSLightingShaderProperty", shader)
    texset = struct.pack("<I", len(textures)) + b"".join(struct.pack("<I", len(t)) + t for t in textures)
    n.add_block("BSShaderTextureSet", texset)
    alpha_ref = -1
    if ni_alpha_flags is not None:
        alpha_blk = struct.pack("<iI i HB", -1, 0, -1, ni_alpha_flags, ni_alpha_thresh)
        alpha_ref = n.add_block("NiAlphaProperty", alpha_blk)
    shape = SimpleNamespace(
        shader_ref=0,
        alpha_ref=alpha_ref,
        colors=list(colors),
        positions=[(0.0, 0.0, 0.0), (14.0, 0.0, 0.0), (0.0, 14.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        tangents=[(1.0, 0.0, 0.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        triangles=[(0, 1, 2)],
        scale=1.0,
        rotation=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
        translation=(0.0, 0.0, 0.0),
    )
    return n, shape


def _mock_converter():
    c = pipeline.Converter.__new__(pipeline.Converter)
    c.neutral = "materials\\fo4port\\_neutral.mat"
    c.texture_set_material = Mock(return_value="materials\\fo4port\\texdecals\\x.mat")
    c.material = Mock(return_value="materials\\fo4port\\x.mat")
    c._is_blended = Mock(return_value=False)
    c._materials = {}
    c.stats = {"materials_ok": 0, "materials_fallback": 0}
    c.material_errors = {}
    return c


class InlineDecalAndOffsetTests(unittest.TestCase):
    def test_parse_ni_alpha_reads_blend_test_and_threshold(self):
        hints = typing.get_type_hints(pipeline.parse_ni_alpha)
        self.assertIn("return", hints)
        n, s = _make_inline_shape(0x8C400201, [b"a.dds", b"n.dds"], ni_alpha_flags=0x10ED, ni_alpha_thresh=128)
        self.assertEqual(pipeline.parse_ni_alpha(n, s.alpha_ref), (True, False, 128))
        n2, s2 = _make_inline_shape(0x80400281, [b"a.dds", b"n.dds"], ni_alpha_flags=0x12EC, ni_alpha_thresh=128)
        self.assertEqual(pipeline.parse_ni_alpha(n2, s2.alpha_ref), (False, True, 128))
        self.assertEqual(pipeline.parse_ni_alpha(n2, -1), (False, False, 128))

    def test_inline_stripe_restricted_routes_to_decal_material(self):
        c = _mock_converter()
        tex = [b"textures\\interiors\\vault\\vault111\\V111GreebsAlpha01_d.dds",
               b"textures\\interiors\\vault\\vault111\\V111GreebsAlpha01_n.dds"] + [b""] * 8
        # Matches V111FloorStripeRestricted.nif (flags1=0x8C400201, NiAlpha=0x10ED)
        src, s = _make_inline_shape(0x8C400201, tex, flags2=0x21, ni_alpha_flags=0x10ED, ni_alpha_thresh=128)
        mat = c._shape_material(src, s)
        self.assertEqual(mat, "materials\\fo4port\\texdecals\\x.mat")
        c.texture_set_material.assert_called_once()
        kw = c.texture_set_material.call_args.kwargs
        self.assertTrue(kw.get("decal"))

    def test_inline_decal_respects_zero_and_faded_vertex_alpha(self):
        c = _mock_converter()
        tex = [b"textures\\a_d.dds", b"textures\\a_n.dds"] + [b""] * 8
        src0, s0 = _make_inline_shape(pipeline.SLSF1_DECAL, tex, flags2=0x21, colors=[(255, 255, 255, 0)])
        self.assertIsNone(c._shape_material(src0, s0))
        c.texture_set_material.assert_not_called()

        src_fade, s_fade = _make_inline_shape(pipeline.SLSF1_DYNAMIC_DECAL, tex, flags2=0x21, colors=[(255, 255, 255, 48)])
        c._shape_material(src_fade, s_fade)
        kw = c.texture_set_material.call_args.kwargs
        self.assertTrue(kw.get("decal"))
        self.assertAlmostEqual(kw.get("opacity_scale"), 48 / 255)

    def test_inline_alpha_test_only_routes_as_cutout_not_decal(self):
        c = _mock_converter()
        c.texture_set_material.return_value = "materials\\fo4port\\texcutouts\\x.mat"
        tex = [b"textures\\a_d.dds", b"textures\\a_n.dds"] + [b""] * 8
        src, s = _make_inline_shape(0x80400201, tex, ni_alpha_flags=0x12EC, ni_alpha_thresh=128)
        mat = c._shape_material(src, s)
        self.assertEqual(mat, "materials\\fo4port\\texcutouts\\x.mat")
        kw = c.texture_set_material.call_args.kwargs
        self.assertFalse(kw.get("decal", False))
        self.assertTrue(kw.get("alpha_test"))
        self.assertEqual(kw.get("alpha_ref"), 128)

    def test_texture_set_material_separates_decal_and_opaque_cache_keys(self):
        c = pipeline.Converter.__new__(pipeline.Converter)
        c._materials = {}
        c.stats = {"materials_ok": 0, "materials_fallback": 0}
        c.material_errors = {}
        c._convert_texture_set = Mock(side_effect=lambda stem, *a, **kw: f"materials\\fo4port\\{stem}.mat")
        m_opaque = c.texture_set_material("textures\\a\\x_d.dds", "textures\\a\\x_n.dds", "")
        m_decal = c.texture_set_material("textures\\a\\x_d.dds", "textures\\a\\x_n.dds", "", decal=True)
        m_cutout = c.texture_set_material("textures\\a\\x_d.dds", "textures\\a\\x_n.dds", "", alpha_test=True, alpha_ref=96)
        self.assertIn("texsets/", m_opaque)
        self.assertIn("texdecals/", m_decal)
        self.assertIn("texcutouts/", m_cutout)
        self.assertEqual(len({m_opaque, m_decal, m_cutout}), 3)

    def test_planar_decal_gets_normal_offset_in_shape_to_mesh(self):
        _n, flat_shape = _make_inline_shape(0x8C400201, [b"a.dds", b"n.dds"])
        off = pipeline.shape_normal_offset_m(flat_shape, "materials\\fo4port\\decals\\x.mat")
        self.assertAlmostEqual(off, pipeline.DECAL_NORMAL_OFFSET_M)
        self.assertEqual(pipeline.shape_normal_offset_m(flat_shape, "materials\\fo4port\\texsets\\x.mat"), 0.0)
        mesh = convert_static.shape_to_mesh(flat_shape, normal_offset_m=off)
        pts = [sfmesh.decode_position(p, mesh.scale) for p in mesh.positions]
        for p in pts:
            self.assertAlmostEqual(p[2], pipeline.DECAL_NORMAL_OFFSET_M, places=4)


def _walk_top_refr_count_and_disabled(esm_bytes: bytes):
    """Lightweight parser returning total REFR count and list of (fid, flags) in cell records."""
    hsize = struct.unpack_from("<I", esm_bytes, 4)[0]
    from fo4sf import fo4land
    refrs = []

    def walk(s, e):
        for item in fo4land.iter_items(esm_bytes, s, e):
            if item[0] == "GRUP":
                walk(item[1] + 24, item[2])
            elif item[0] == b"REFR":
                _, _off, flags, fid = item
                refrs.append((fid, flags))

    walk(24 + hsize, len(esm_bytes))
    return refrs


class PluginSpikeVault111FlagsTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("dotnet"), "dotnet SDK required")
    def test_dedup_exact_refs_and_resolve_enable_parents(self):
        rel_dir = ROOT / "dotnet" / "PluginSpike" / "bin" / "Release"
        candidates = sorted(rel_dir.glob("net*/PluginSpike.dll"))
        if not candidates:
            cp = subprocess.run(
                ["dotnet", "build", str(ROOT / "dotnet" / "PluginSpike" / "PluginSpike.csproj"), "-c", "Release"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            candidates = sorted(rel_dir.glob("net*/PluginSpike.dll"))
        self.assertTrue(candidates, "PluginSpike.dll missing after dotnet build")
        dll = candidates[-1]

        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            sf_data = t / "sf_data"
            sf_data.mkdir()
            env = dict(os.environ, STARFIELD_DATA=str(sf_data))
            man = t / "manifest.json"
            man.write_text(json.dumps({
                "items": [
                    {"editor_id": "FO4Port_V111Hall01", "model": "fo4port\\v111hall01.nif", "source": "meshes\\Interiors\\V111Hall01.nif"},
                    {"editor_id": "FO4Port_Marker", "model": "fo4port\\marker.nif", "source": "meshes\\Markers\\Marker.nif"},
                ],
                "failures": [],
            }), encoding="utf-8")
            cell = t / "Vault111Cryo.json"
            cell.write_text(json.dumps({
                "schema_version": 3,
                "cell": "Vault111Cryo",
                "refs": [
                    # Enable marker: initially disabled (0x800)
                    {"formkey": "000010:Fallout4.esm", "type": "Static", "base_editor_id": "EnableMarker",
                     "model": "Markers\\Marker.nif", "pos": [0.0, 0.0, 0.0], "rot": [0.0, 0.0, 0.0], "scale": 1.0, "disabled": 2048},
                    # Two exact duplicate V111Hall01 refs at same transform
                    {"formkey": "000020:Fallout4.esm", "type": "Static", "base_editor_id": "V111Hall01",
                     "model": "Interiors\\V111Hall01.nif", "pos": [70.0, 70.0, 0.0], "rot": [0.0, 0.0, 0.0], "scale": 1.0, "disabled": 0},
                    {"formkey": "000021:Fallout4.esm", "type": "Static", "base_editor_id": "V111Hall01",
                     "model": "Interiors\\V111Hall01.nif", "pos": [70.0, 70.0, 0.0], "rot": [0.0, 0.0, 0.0], "scale": 1.0, "disabled": 0},
                    # Pre-War light tied to disabled marker with opposite=0 -> disabled (skipped before merge!)
                    {"formkey": "000030:Fallout4.esm", "type": "Light", "base_editor_id": "PreWarLight",
                     "model": "", "pos": [0.0, 0.0, 0.0], "rot": [0.0, 0.0, 0.0], "scale": 1.0, "disabled": 0,
                     "enable_parent": {"reference": "000010:Fallout4.esm", "flags": 0}},
                    # Post-War light tied to disabled marker with opposite=1 -> enabled!
                    {"formkey": "000031:Fallout4.esm", "type": "Light", "base_editor_id": "PostWarLight",
                     "model": "", "pos": [0.0, 0.0, 0.0], "rot": [0.0, 0.0, 0.0], "scale": 1.0, "disabled": 0,
                     "enable_parent": {"reference": "000010:Fallout4.esm", "flags": 1}},
                    # Static tied to disabled marker with opposite=0 -> marked 0x800 initially disabled
                    {"formkey": "000040:Fallout4.esm", "type": "Static", "base_editor_id": "PreWarProp",
                     "model": "Interiors\\V111Hall01.nif", "pos": [700.0, 0.0, 0.0], "rot": [0.0, 0.0, 0.0], "scale": 1.0, "disabled": 0,
                     "enable_parent": {"reference": "000010:Fallout4.esm", "flags": 0}},
                    # Disabled alternate at same transform as 000020 -> preserved (never collapsed by DEDUP_EXACT_REFS)
                    {"formkey": "000060:Fallout4.esm", "type": "Static", "base_editor_id": "V111Hall01",
                     "model": "Interiors\\V111Hall01.nif", "pos": [70.0, 70.0, 0.0], "rot": [0.0, 0.0, 0.0], "scale": 1.0, "disabled": 2048},
                    # Cyclic enable_parent pair -> terminates cleanly without infinite recursion
                    {"formkey": "000050:Fallout4.esm", "type": "Static", "base_editor_id": "V111Hall01",
                     "model": "Interiors\\V111Hall01.nif", "pos": [1400.0, 0.0, 0.0], "rot": [0.0, 0.0, 0.0], "scale": 1.0, "disabled": 0,
                     "enable_parent": {"reference": "000051:Fallout4.esm", "flags": 0}},
                    {"formkey": "000051:Fallout4.esm", "type": "Static", "base_editor_id": "V111Hall01",
                     "model": "Interiors\\V111Hall01.nif", "pos": [2100.0, 0.0, 0.0], "rot": [0.0, 0.0, 0.0], "scale": 1.0, "disabled": 0,
                     "enable_parent": {"reference": "000050:Fallout4.esm", "flags": 0}},
                    # Co-located COCMarkerHeading pair -> both kept even when DEDUP_EXACT_REFS=1
                    {"formkey": "000070:Fallout4.esm", "type": "Static", "base_editor_id": "COCMarkerHeading",
                     "model": "", "pos": [0.0, 0.0, 0.0], "rot": [0.0, 0.0, 0.0], "scale": 1.0, "disabled": 0},
                    {"formkey": "000071:Fallout4.esm", "type": "Static", "base_editor_id": "COCMarkerHeading",
                     "model": "", "pos": [0.0, 0.0, 0.0], "rot": [0.0, 0.0, 0.0], "scale": 1.0, "disabled": 0},
                ],
            }), encoding="utf-8")

            # Run 1: flags OFF (legacy default) -> 10 REFRs (1 marker disabled + 2 halls + 1 merged light + 1 prop + 1 disabled alt + 2 cyclic + 2 COC)
            out_default = t / "out_default"
            out_default.mkdir()
            cp1 = subprocess.run(["dotnet", str(dll), str(out_default), str(man), str(cell)],
                                 capture_output=True, text=True, check=False, env=env)
            self.assertEqual(cp1.returncode, 0, cp1.stdout + cp1.stderr)
            r_def = _walk_top_refr_count_and_disabled((out_default / "FO4Port.esm").read_bytes())
            self.assertEqual(len(r_def), 10)
            self.assertEqual(sum(1 for _, fl in r_def if fl & 0x800), 2)

            # Run 2: flags ON -> duplicate hall 000021 skipped, PreWarLight skipped, PreWarProp gets 0x800,
            # disabled alt 000060 kept, cyclic pair kept without hanging, both COC markers kept -> 9 REFRs
            out_opt = t / "out_opt"
            out_opt.mkdir()
            (out_opt / "lighting.json").write_text(json.dumps({
                "Vault111Cryo": {"DEDUP_EXACT_REFS": "1", "RESOLVE_ENABLE_PARENTS": "1"}
            }), encoding="utf-8")
            cp2 = subprocess.run(["dotnet", str(dll), str(out_opt), str(man), str(cell)],
                                 capture_output=True, text=True, check=False, env=env)
            self.assertEqual(cp2.returncode, 0, cp2.stdout + cp2.stderr)
            self.assertIn("1 lights", cp2.stdout)
            r_opt = _walk_top_refr_count_and_disabled((out_opt / "FO4Port.esm").read_bytes())
            self.assertEqual(len(r_opt), 9)
            self.assertEqual(sum(1 for _, fl in r_opt if fl & 0x800), 3)


if __name__ == "__main__":
    unittest.main()
