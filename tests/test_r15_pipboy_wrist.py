"""Offline tests for Round 15 Wave A Item 1: Pip-Boy on the wrist (split housing/screen + ARMA/GLOB + C++ seam)."""
from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "scripts", "ui"))

import stage_pipboy_wrist as spw  # noqa: E402
from fo4sf import actor_rebind, nif as nifmod, sfmesh, sfnif  # noqa: E402


def _make_synthetic_sf_chronowatch_template() -> bytes:
    """Build a minimal BS-173 Starfield ChronoWatch NIF with 4-bone SkinAttach."""
    f = nifmod.NifFile(
        endian=1,
        user_version=12,
        bs_version=173,
        author=b"\x00",
        unknown_int=0,
        export_script=b"\x00",
        sf_data=b"\x7a\x00",
    )
    ident = struct.pack("<3f9ff", 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1.0)
    f.add_block(
        "NiNode",
        struct.pack("<iIiiI", f.string_index(b"Root"), 1, 1, -1, 0xE)
        + ident
        + struct.pack("<iI", -1, 1)
        + struct.pack("<i", 2),
    )
    f.add_block("BSXFlags", struct.pack("<iI", f.string_index(b"BSX"), 0))
    g = sfnif.BSGeometry(
        name_idx=f.string_index(b"ChronoWatch_Template:0"),
        extra_refs=[3, 4],
        skin=5,
        shader=7,
        meshes=[sfnif.MeshRef(3, 3, 0x40, b"0" * 20 + b"\\" + b"1" * 20), None, None, None],
    )
    f.add_block("BSGeometry", sfnif.build_bsgeometry(g))
    f.add_block("NiIntegerExtraData", struct.pack("<iI", f.string_index(b"MaterialID"), 0))

    sa_parts = [struct.pack("<iI", f.string_index(b"SkinAttach"), len(spw.EXPECTED_SKIN_ATTACH))]
    for bn in spw.EXPECTED_SKIN_ATTACH:
        raw = bn.encode("latin-1")
        sa_parts.append(struct.pack("<I", len(raw)) + raw)
    f.add_block("SkinAttach", b"".join(sa_parts))

    f.add_block("BSSkin::Instance", actor_rebind.write_instance(0, 6, [-1, -1, -1, -1], b"\x00\x00\x00\x00"))
    # 4 bone entries: identity rotation, translations along forearm, slot 3 offset at (-0.75, -0.18, 0.12)
    bd_parts = [struct.pack("<I", 4)]
    for i in range(4):
        sph = struct.pack("<4f", 0.0, 0.0, 0.0, 0.05)
        rot = struct.pack("<9f", 1, 0, 0, 0, 1, 0, 0, 0, 1)
        tr = struct.pack("<3f", -0.50 - 0.08 * i, -0.18, 0.12)
        sc = struct.pack("<f", 1.0)
        bd_parts.append(sph + rot + tr + sc)
    f.add_block("BSSkin::BoneData", b"".join(bd_parts))
    f.add_block("BSLightingShaderProperty", struct.pack("<iIi", f.string_index(b"Materials\\Items\\ChronoWatch.mat"), 0, -1))
    f.footer = struct.pack("<II", 1, 0)
    return nifmod.serialize(f)


def _make_synthetic_fo4_pipboy_nif() -> bytes:
    """Build a minimal BS-130 FO4 NIF with housing shapes, TapREF helper, and Screen* shapes."""
    f = nifmod.NifFile(
        endian=1,
        user_version=12,
        bs_version=130,
        author=b"\x00",
        unknown_int=0,
        export_script=b"\x00",
        sf_data=b"",
    )
    ident_xform = struct.pack("<3f9ff", 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1.0)

    def add_trishape(name: bytes, pts, uvs, shader_name: bytes, is_effect: bool = False) -> int:
        idx = len(f.blocks)
        n_idx = f.string_index(name)
        v_count = len(pts)
        t_count = 1
        # FO4 BSTriShape vertex desc (u64): vertex(0x1), uv(0x2), normals(0x8), tangents(0x10)
        # Layout: 24 bytes/vert or simple float3/half2/normal/tangent. Use nif.fo4_trishapes minimal layout:
        # Actually vertex_desc: flag 0x4 (no normals? let's include pos+uv+norm+tan = 20 B/vert -> flags=0x0040_0000_0000_0000 | ... )
        # Let's match nif.py's BSTriShape decoder directly!
        sh_idx = idx + 1
        # BSTriShape header: name(4), n_extra(4), ctrl(4), flags(4), tr(12), rot(36), scale(4),
        # collision(4), sphere(16), skin(4), shader(4), alpha(4), vertex_desc(8), ntri(4), nvert(2), dsize(4)
        # FullPrecision (attrs 0x41B = Vertex|UV|Normal|Tangent|FullPrecision):
        # 16 B pos+bitanX + 4 B uv + 4 B norm + 4 B tan = 28 B/vert (size_units = 7)
        attrs = 0x400 | 0x001 | 0x002 | 0x008 | 0x010
        vdesc = 7 | (attrs << 44)
        vdata = bytearray()
        for (px, py, pz), (u, v) in zip(pts, uvs):
            vdata.extend(struct.pack("<4f2e4B4B", px, py, pz, 0.0, u, v, 127, 127, 0, 0, 255, 127, 127, 0))
        tdata = struct.pack("<3H", 0, 1, 2)
        data_size = len(vdata) + len(tdata)
        blk = (
            struct.pack("<iIiI", n_idx, 0, -1, 0xE)
            + ident_xform
            + struct.pack("<i4f", -1, 0.0, 0.0, 0.0, 5.0)
            + struct.pack("<3i", -1, sh_idx, -1)
            + struct.pack("<QIHI", vdesc, t_count, v_count, data_size)
            + bytes(vdata)
            + tdata
        )
        f.add_block("BSTriShape", blk)
        if is_effect:
            f.add_block("BSEffectShaderProperty", struct.pack("<IiI", 0, f.string_index(shader_name), 0))
        else:
            f.add_block("BSLightingShaderProperty", struct.pack("<IiI", 0, f.string_index(shader_name), 0))
        return idx

    # Root NiNode at 0, children populated after shapes added
    f.add_block("NiNode", b"")
    c_body = add_trishape(
        b"PipboyBody_mesh:0",
        [(4.0, -3.0, -2.0), (8.0, -3.0, -2.0), (6.0, 3.0, 2.0)],
        [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)],
        b"Materials\\AnimObjects\\PipBoy\\PipBoy01.BGSM",
    )
    c_tap = add_trishape(
        b"TapREF_mesh:0",
        [(5.0, 4.0, 0.0), (6.0, 4.0, 0.0), (5.5, 5.0, 0.0)],
        [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)],
        b"",
    )
    c_scr = add_trishape(
        b"Screen:0",
        [(9.0, 4.0, -4.7), (3.0, 4.0, -4.7), (9.0, 0.0, -4.7)],
        [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        b"Materials\\AnimObjects\\PipBoy\\PipBoyScreen.BGSM",
    )
    c_glow = add_trishape(
        b"ScreenGlowEffect01:0",
        [(9.0, 4.0, -5.0), (3.0, 4.0, -5.0), (9.0, 0.0, -5.0)],
        [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        b"",
        is_effect=True,
    )
    children = [c_body, c_tap, c_scr, c_glow]
    f.blocks[0] = (
        struct.pack("<iIiI", f.string_index(b"PipboyRoot"), 0, -1, 0xE)
        + ident_xform
        + struct.pack("<iI", -1, len(children))
        + struct.pack(f"<{len(children)}i", *children)
    )
    f.footer = struct.pack("<II", 1, 0)
    return nifmod.serialize(f)


class TestR15PipboyWrist(unittest.TestCase):
    def test_split_housing_and_screen_and_verify_only(self) -> None:
        tpl_bytes = _make_synthetic_sf_chronowatch_template()
        fo4_bytes = _make_synthetic_fo4_pipboy_nif()

        housing_mat_rel = "materials/fo4port/animobjects/pipboy/pipboy01.mat"
        housing_mat_game = "materials\\fo4port\\animobjects\\pipboy\\pipboy01.mat"
        housing_tex_rel = "textures/fo4port/animobjects/pipboy/pipboy01_color.dds"

        housing_res = spw.rebind_pipboy_to_wrist(
            tpl_bytes,
            fo4_bytes,
            spw.is_housing_shape,
            lambda _nf, _s: housing_mat_game,
            cuff_center_bone=spw.WRIST_CENTER_BONE_M,
            unit_scale=spw.FO4_TO_SF_WRIST_SCALE_M,
            group_prefix="FO4WristHousingM",
        )
        screen_res = spw.rebind_pipboy_to_wrist(
            tpl_bytes,
            fo4_bytes,
            spw.is_primary_screen_shape,
            lambda _nf, _s: spw.SCREEN_MAT_GAME,
            cuff_center_bone=spw.WRIST_CENTER_BONE_M,
            unit_scale=spw.FO4_TO_SF_WRIST_SCALE_M,
            group_prefix="FO4WristScreenM",
        )

        # Housing excludes Screen* and TapREF*
        self.assertEqual(list(housing_res.report["groups"].keys()), [housing_mat_game])
        self.assertEqual(housing_res.report["groups"][housing_mat_game]["shapes"], ["PipboyBody_mesh:0"])
        self.assertEqual(housing_res.report["dominant_bone"], "L_Wrist_Twist2")
        self.assertEqual(housing_res.report["dominant_slot"], 3)

        # Screen has ONLY Screen:0 bound to pipboy_screen_2d.mat
        self.assertEqual(list(screen_res.report["groups"].keys()), [spw.SCREEN_MAT_GAME])
        self.assertEqual(screen_res.report["groups"][spw.SCREEN_MAT_GAME]["shapes"], ["Screen:0"])

        # Verify Screen:0 orientation: FO4 -Z (-4.7 < -0.106) rotated by Ry(180) -> +Z (> +0.002)
        scr_bounds = screen_res.report["bone_bounds_m"]
        self.assertGreater(scr_bounds["z"][0], 0.05)

        # Stage into temp dir outside Git and run verify_staged_pipboy_wrist positive + negative checks
        with tempfile.TemporaryDirectory() as tmp:
            for nif_rel in spw.HOUSING_NIFS:
                p = os.path.join(tmp, *nif_rel.split("/"))
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "wb") as fh:
                    fh.write(housing_res.nif)
            for nif_rel in spw.SCREEN_NIFS:
                p = os.path.join(tmp, *nif_rel.split("/"))
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "wb") as fh:
                    fh.write(screen_res.nif)
            for res in (housing_res, screen_res):
                for (d, f), mb in res.meshes.items():
                    mp = os.path.join(tmp, "geometries", d, f"{f}.mesh")
                    os.makedirs(os.path.dirname(mp), exist_ok=True)
                    with open(mp, "wb") as fh:
                        fh.write(mb)

            for mat_rel, tex_rel in (
                (housing_mat_rel, housing_tex_rel),
                (spw.SCREEN_MAT_REL, f"{spw.SCREEN_TEX_PREFIX}_color.dds"),
            ):
                tp = os.path.join(tmp, *tex_rel.split("/"))
                os.makedirs(os.path.dirname(tp), exist_ok=True)
                with open(tp, "wb") as fh:
                    fh.write(b"DDS_PLACEHOLDER")
                mp = os.path.join(tmp, *mat_rel.split("/"))
                os.makedirs(os.path.dirname(mp), exist_ok=True)
                with open(mp, "w", encoding="utf-8") as fh:
                    json.dump({"Albedo": f"Data\\{tex_rel.replace('/', chr(92))}"}, fh)

            verified = spw.verify_staged_pipboy_wrist(tmp)
            self.assertEqual(len(verified["nifs"]), 6)
            self.assertIn(spw.SCREEN_MAT_REL, verified["local_mats"])

            # Negative: missing screen texture must fail
            os.remove(os.path.join(tmp, *f"{spw.SCREEN_TEX_PREFIX}_color.dds".split("/")))
            with self.assertRaises(FileNotFoundError):
                spw.verify_staged_pipboy_wrist(tmp)

    def test_refuses_staging_inside_git_worktree(self) -> None:
        inside_git = os.path.join(REPO, "tmp_bad_stage")
        with self.assertRaises(ValueError):
            spw.stage_pipboy_wrist(REPO, REPO, inside_git)

    def test_csharp_pipboy_wrist_builder_with_mutagen(self) -> None:
        builder_cs = os.path.join(REPO, "dotnet", "NewGame", "PipboyWristBuilder.cs")
        csproj_src = os.path.join(REPO, "dotnet", "NewGame", "NewGame.csproj")
        self.assertTrue(os.path.isfile(builder_cs))
        with tempfile.TemporaryDirectory() as tmp:
            # Copy csproj to restore packages, write minimal harness calling PipboyWristBuilder
            shutil.copy2(builder_cs, os.path.join(tmp, "PipboyWristBuilder.cs"))
            with open(csproj_src, encoding="utf-8") as fh:
                csproj = fh.read()
            with open(os.path.join(tmp, "WristHarness.csproj"), "w", encoding="utf-8") as fh:
                fh.write(csproj)

            harness_cs = r"""
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Starfield;
using SF = Mutagen.Bethesda.Starfield;

var sfKey = ModKey.FromFileName("Starfield.esm");
var rel = SF.StarfieldRelease.Starfield;
var sf = new SF.StarfieldMod(sfKey, rel);
sf.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
sf.Races.Add(new SF.Race(new FormKey(sfKey, PipboyWristBuilder.HumanRaceId), rel) { EditorID = "HumanRace" });

var chronoArmo = new SF.Armor(new FormKey(sfKey, 0x0D4893), rel)
{
    EditorID = "Clothes_Chronomark_Mq101_NOTPLAYABLE",
    FirstPersonFlags = SF.FirstPersonFlag.Chronomark,
};
chronoArmo.MajorRecordFlagsRaw |= 0x4;
sf.Armors.Add(chronoArmo);

var watchAa = new SF.ArmorAddon(new FormKey(sfKey, PipboyWristBuilder.WatchTemplateArmaId), rel)
{
    EditorID = "AA_Spacesuit_Mark1_ChronoWatch",
    FirstPersonFlags = SF.FirstPersonFlag.SSChronoMark,
};
watchAa.Race.SetTo(new FormKey(sfKey, PipboyWristBuilder.HumanRaceId));
sf.ArmorAddons.Add(watchAa);

var ngKey = ModKey.FromFileName("FO4SFNewGame.esm");
var ng = new SF.StarfieldMod(ngKey, rel);
ng.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
var wrist = (SF.Armor)chronoArmo.Duplicate(new FormKey(ngKey, 0x80D));
wrist.EditorID = "FO4SF_PipboyWrist";
wrist.Name = "Pip-Boy 3000";
ng.Armors.Add(wrist);

var (housingAa, screenAa, sourceGlob) = PipboyWristBuilder.BuildWristRecords(ng, sf, wrist, sfKey);

var problems = new List<string>();
PipboyWristBuilder.ValidateWristRecords(ng, wrist, (ok, msg) => { if (!ok) problems.Add(msg); });
if (problems.Count > 0)
{
    Console.Error.WriteLine(string.Join("\n", problems));
    return 1;
}

Console.WriteLine($"OK housing={housingAa.FormKey} screen={screenAa.FormKey} glob={sourceGlob.FormKey} slot=0x{(ulong)(wrist.FirstPersonFlags ?? 0):X16}");

// Negative control: mutating wrist FirstPersonFlags back to occluded Chronomark must fail validation
wrist.FirstPersonFlags = SF.FirstPersonFlag.Chronomark;
var negProblems = new List<string>();
PipboyWristBuilder.ValidateWristRecords(ng, wrist, (ok, msg) => { if (!ok) negProblems.Add(msg); });
if (negProblems.Count == 0)
{
    Console.Error.WriteLine("negative control failed: occluded slot passed validation");
    return 2;
}

return 0;
"""
            with open(os.path.join(tmp, "Program.cs"), "w", encoding="utf-8") as fh:
                fh.write(harness_cs)

            r = subprocess.run(
                ["dotnet", "run", "--project", os.path.join(tmp, "WristHarness.csproj")],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, msg=f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}")
            self.assertIn("slot=0x0040000000000000", r.stdout)

    def test_cpp_pipboy_screen_source_header(self) -> None:
        hdr = os.path.join(REPO, "sfse", "FO4SFPipboyMenu", "src", "pipboy_screen_source.h")
        self.assertTrue(os.path.isfile(hdr))
        with open(hdr, encoding="utf-8") as fh:
            text = fh.read()
        for sym in (
            "enum class ScreenSourceMode",
            "k2DIMenu",
            "k3DRTT",
            "ParseScreenSourceIni",
            "ResolvePipboyScreenSource",
            "OpenPipboyScreenViaSource",
            "0x825",
        ):
            self.assertIn(sym, text)

        gpp = shutil.which("g++")
        cl = shutil.which("cl")
        if not (gpp or cl):
            return

        with tempfile.TemporaryDirectory() as tmp:
            cpp = os.path.join(tmp, "test_seam.cpp")
            exe = os.path.join(tmp, "test_seam.exe")
            with open(cpp, "w", encoding="utf-8") as fh:
                fh.write(
                    '#include <cassert>\n'
                    '#include "pipboy_screen_source.h"\n'
                    'int main() {\n'
                    '  using namespace fo4sf::pipboy;\n'
                    '  assert(ParseScreenSourceIni("") == ScreenSourceMode::k2DIMenu);\n'
                    '  assert(ParseScreenSourceIni("2d_imenu") == ScreenSourceMode::k2DIMenu);\n'
                    '  assert(ParseScreenSourceIni(" 3D_RTT ") == ScreenSourceMode::k3DRTT);\n'
                    '  assert(!ParseScreenSourceIni("invalid_mode").has_value());\n'
                    '  assert(ResolvePipboyScreenSource(ScreenSourceMode::k2DIMenu, 0.0f) == ScreenSourceMode::k2DIMenu);\n'
                    '  assert(ResolvePipboyScreenSource(ScreenSourceMode::k2DIMenu, 1.0f) == ScreenSourceMode::k3DRTT);\n'
                    '  assert(ResolvePipboyScreenSource(ScreenSourceMode::k3DRTT, 0.0f) == ScreenSourceMode::k3DRTT);\n'
                    '  auto r2d = OpenPipboyScreenViaSource(ScreenSourceMode::k2DIMenu, [](){ return true; }, [](){ return false; });\n'
                    '  assert(r2d.opened && !r2d.fellBackTo2D && r2d.mode == ScreenSourceMode::k2DIMenu);\n'
                    '  auto r3d_fb = OpenPipboyScreenViaSource(ScreenSourceMode::k3DRTT, [](){ return true; }, [](){ return false; });\n'
                    '  assert(r3d_fb.opened && r3d_fb.fellBackTo2D && r3d_fb.mode == ScreenSourceMode::k2DIMenu);\n'
                    '  auto r3d_ok = OpenPipboyScreenViaSource(ScreenSourceMode::k3DRTT, [](){ return false; }, [](){ return true; });\n'
                    '  assert(r3d_ok.opened && !r3d_ok.fellBackTo2D && r3d_ok.mode == ScreenSourceMode::k3DRTT);\n'
                    '  return 0;\n'
                    '}\n'
                )
            inc = os.path.dirname(hdr)
            if gpp:
                r = subprocess.run([gpp, "-std=c++20", f"-I{inc}", cpp, "-o", exe], capture_output=True, text=True)
            else:
                r = subprocess.run([cl, "/std:c++20", "/EHsc", f"/I{inc}", cpp, f"/Fe:{exe}"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, msg=f"compile failed:\n{r.stdout}\n{r.stderr}")
            run_r = subprocess.run([exe], capture_output=True, text=True)
            self.assertEqual(run_r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
