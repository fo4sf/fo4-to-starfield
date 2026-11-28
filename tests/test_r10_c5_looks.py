"""Round 10 Slice W3 (C5) unit tests: actor spacesuit stripping, FO4 outfit/face looks, SkinAttach rebind & HUD audit."""
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT / "scripts" / "actors") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "actors"))
if str(REPO_ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tests"))

from fo4sf import actor_rebind, nif as nifmod, sfmesh, sfnif  # noqa: E402
from fo4sf.planet.esm import Plugin  # noqa: E402
import stage_c5_actor_looks as stage_c5  # noqa: E402
from test_fo4skin import skinned_nif  # noqa: E402

DRIVE_LEAK_RE = re.compile(r"\b[A-Za-z]:[\\/]")


def _make_synthetic_sf_human_template_nif(bone_names=("C_Chest", "C_Hips", "C_Head", "L_Wrist_Twist1", "R_Wrist_Twist1", "L_Foot", "R_Foot")) -> bytes:
    """Build a minimal valid BS 173/175 Starfield HumanRace SkinAttach template NIF completely offline."""
    nf = sfnif.build_static_nif(
        b"Scene Root",
        [sfnif.StaticShape(
            name=b"TemplateGeom",
            mesh_path=b"0123456789abcdef0123\\fedcba9876543210fedc",
            indices_size=3,
            num_verts=3,
            material_path="materials\\fo4core\\armor\\raider04\\raider04.mat",
            sphere=(0.0, 0.0, 0.0, 1.0),
            box=(0.0, 0.0, 0.0, 0.5, 0.5, 0.5),
        )],
    )
    g = sfnif.parse_bsgeometry(nf.blocks[2])
    sa_name_idx = nf.string_index(b"SkinAttach")
    sa_idx = nf.add_block("SkinAttach", stage_c5.build_skin_attach(sa_name_idx, bone_names))

    ident_entry = struct.pack(
        "<4f9f3ff",
        0.0, 0.0, 0.0, 0.25,
        1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
        0.0, 0.0, 0.0,
        1.0,
    )
    bdata_idx = nf.add_block("BSSkin::BoneData", struct.pack("<I", len(bone_names)) + ident_entry * len(bone_names))
    binst_idx = nf.add_block(
        "BSSkin::Instance",
        actor_rebind.write_instance(0, bdata_idx, [-1] * len(bone_names), struct.pack("<I", 0)),
    )
    g.translation = (0.0, -0.0018, 1.63227)
    g.extra_refs = list(g.extra_refs) + [sa_idx]
    g.skin = binst_idx
    nf.blocks[2] = sfnif.build_bsgeometry(g)
    return nifmod.serialize(nf)


def _make_synthetic_fo4_skinned_nif() -> bytes:
    """Serialize the canonical BS 130 Fallout 4 skinned BSTriShape fixture from test_fo4skin."""
    return nifmod.serialize(skinned_nif())


class TestR10C5Looks(unittest.TestCase):
    def test_skin_attach_roundtrip_and_staged_bundle_verifier(self):
        tpl = _make_synthetic_sf_human_template_nif()
        fo4 = _make_synthetic_fo4_skinned_nif()
        preston_mat = "materials\\fo4port\\armor\\preston\\prestonbody1.mat"
        hat_mat = "materials\\fo4port\\armor\\preston\\prestonhat1.mat"
        raider_mat = stage_c5.EXISTING_FO4CORE_MATS["raider04"]

        res_body = stage_c5.rebind_human_skin_attach(
            tpl, [("synthetic_preston.nif", fo4, {})],
            unit_scale=stage_c5.FO4_TO_SF_HUMAN_SCALE, weights_per_vertex=4, default_material=preston_mat,
        )
        res_hat = stage_c5.rebind_human_skin_attach(
            _make_synthetic_sf_human_template_nif(bone_names=("C_Head",)),
            [("synthetic_hat.nif", fo4, {})],
            unit_scale=stage_c5.FO4_TO_SF_HUMAN_SCALE, weights_per_vertex=1, default_material=hat_mat,
        )
        res_raider = stage_c5.rebind_human_skin_attach(
            tpl, [("synthetic_raider.nif", fo4, {})],
            unit_scale=stage_c5.FO4_TO_SF_HUMAN_SCALE, weights_per_vertex=4, default_material=raider_mat,
        )

        out_nf = nifmod.parse(res_body.nif)
        geoms = [i for i in range(len(out_nf.blocks)) if out_nf.type_of(i) == "BSGeometry"]
        self.assertEqual(len(geoms), 1)
        g = sfnif.parse_bsgeometry(out_nf.blocks[geoms[0]])

        sa_refs = [e for e in g.extra_refs if out_nf.type_of(e) == "SkinAttach"]
        self.assertEqual(len(sa_refs), 1)
        _, sa_bones = stage_c5.parse_skin_attach(out_nf.blocks[sa_refs[0]])
        _, bdata_idx, inst_bones, _ = actor_rebind.read_instance(out_nf.blocks[g.skin])
        self.assertEqual(len(sa_bones), 7)
        self.assertEqual(inst_bones, [-1] * 7)
        self.assertEqual(len(out_nf.blocks[bdata_idx]), 4 + 68 * 7)

        mat_id_refs = [
            e for e in g.extra_refs
            if out_nf.type_of(e) == "NiIntegerExtraData" and actor_rebind._name(out_nf, e) == "MaterialID"
        ]
        self.assertEqual(len(mat_id_refs), 1)
        got_crc, = struct.unpack_from("<I", out_nf.blocks[mat_id_refs[0]], 4)
        self.assertEqual(got_crc, sfnif.material_id(preston_mat))
        self.assertEqual(len(out_nf.blocks[g.shader]), 12)

        mesh_bytes = next(iter(res_body.meshes.values()))
        sm = sfmesh.parse(mesh_bytes)
        self.assertEqual(sm.version, 2)
        self.assertEqual(sm.weights_per_vertex, 4)
        self.assertEqual(len(sm.positions), 3)
        self.assertEqual(len(sm.weights), 12)
        self.assertEqual(len(sm.colors), 0)
        self.assertTrue(sm.has_meshlet_section)
        self.assertEqual(len(sm.tail), 0)
        for v in range(3):
            row = sm.weights[v * 4:(v + 1) * 4]
            self.assertEqual(sum(w for _, w in row), 65535)
            for sl, _ in row:
                self.assertTrue(0 <= sl < len(sa_bones))

        # Test verify_staged_c5_assets positive + negative missing-mesh / missing-texture detection
        with tempfile.TemporaryDirectory(prefix="c5_stage_verify_") as tmp:
            root = Path(tmp)
            for rel, raw in (
                (stage_c5.PRESTON_OUTFIT_REL, res_body.nif),
                (stage_c5.PRESTON_HAT_REL, res_hat.nif),
                (stage_c5.RAIDER_OUTFIT_REL, res_raider.nif),
            ):
                dst = root / "meshes" / Path(*rel.split("/"))
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(raw)
            for res in (res_body, res_hat, res_raider):
                for (d, f), mraw in res.meshes.items():
                    mdst = root / "geometries" / d / f"{f}.mesh"
                    mdst.parent.mkdir(parents=True, exist_ok=True)
                    mdst.write_bytes(mraw)
            tex_rel = "textures/fo4port/armor/preston/prestonbody1_color.dds"
            tdst = root / Path(*tex_rel.split("/"))
            tdst.parent.mkdir(parents=True, exist_ok=True)
            tdst.write_bytes(b"DDS ")
            for mrel in (preston_mat, hat_mat):
                mp = root / Path(*mrel.replace("\\", "/").split("/"))
                mp.parent.mkdir(parents=True, exist_ok=True)
                mp.write_text(json.dumps({"Tex": tex_rel}), encoding="utf-8")

            summary = stage_c5.verify_staged_c5_assets(str(root), require_preston_mats=True)
            self.assertEqual(len(summary["nifs"]), 3)
            self.assertIn(tex_rel, summary["local_textures"])

            # Removing the referenced .dds texture must fail verify_staged_c5_assets
            tdst.unlink()
            with self.assertRaises(FileNotFoundError):
                stage_c5.verify_staged_c5_assets(str(root), require_preston_mats=True)

            # Removing a referenced .mesh must also fail verify_staged_c5_assets
            tdst.write_bytes(b"DDS ")
            any_mesh = next((root / "geometries").rglob("*.mesh"))
            any_mesh.unlink()
            with self.assertRaises(FileNotFoundError):
                stage_c5.verify_staged_c5_assets(str(root), require_preston_mats=True)

    def test_bone_mapping_covers_fo4_preston_and_raider_skeleton(self):
        naked_bones = [
            "C_Chest", "C_Neck_Twist", "C_Neck1", "L_Clavicle", "L_Deltoid", "L_Calf", "L_Foot", "L_CalfMass",
            "L_Thigh", "L_Thigh_Twist1", "L_Knee", "C_Hips", "L_Thigh_Twist", "R_Thigh_Twist", "L_Butt",
            "C_Spine", "C_Spine1", "C_Spine2", "R_Clavicle", "L_Biceps_Twist1", "L_Biceps", "R_Thigh_Twist1",
            "R_Butt", "L_Toe", "R_Thigh", "R_Deltoid", "R_Biceps_Twist1", "R_Biceps", "R_Foot", "R_Calf",
            "R_CalfMass", "R_Knee", "R_Toe", "L_Elbow", "L_Forearm", "L_Wrist_Twist", "L_Wrist_Twist1",
            "R_Elbow", "R_Forearm", "R_Wrist_Twist", "R_Wrist_Twist1",
        ]
        expected = {
            "HEAD": "C_Neck1",
            "Neck1_skin": "C_Neck1",
            "Chest_skin": "C_Chest",
            "Spine1_skin": "C_Spine1",
            "Spine2_skin": "C_Spine2",
            "Pelvis_skin": "C_Hips",
            "LArm_Collarbone_skin": "L_Clavicle",
            "LArm_UpperArm_skin": "L_Biceps",
            "LArm_UpperTwist1_skin": "L_Biceps_Twist1",
            "LArm_ForeArm1_skin": "L_Forearm",
            "LArm_Hand": "L_Wrist_Twist1",
            "RArm_Finger22": "R_Wrist_Twist1",
            "LLeg_Thigh_skin": "L_Thigh",
            "LLeg_Calf_skin": "L_Calf",
            "LLeg_Foot": "L_Foot",
            "RLeg_Toe1": "R_Toe",
            "CLOTH_Bone_Coat_A_003": "C_Hips",
            "CLOTH_Bone_Collar_1": "C_Neck1",
        }
        for fo4_b, want_sf in expected.items():
            got = stage_c5.fo4_human_bone_to_sf(fo4_b, naked_bones)
            self.assertEqual(got, want_sf, f"{fo4_b} mapped to {got}, expected {want_sf}")
            self.assertIn(got, naked_bones)

        self.assertEqual(stage_c5.fo4_human_bone_to_sf("HEAD", ["C_Head"]), "C_Head")
        self.assertEqual(stage_c5.fo4_human_bone_to_sf("Head_skin", ["C_Head"]), "C_Head")

    @unittest.skipUnless(shutil.which("dotnet"), "dotnet SDK required for Mutagen binary ESM verification")
    def test_c5_dotnet_build_and_standalone_binary_selftest(self):
        mission_proj = REPO_ROOT / "dotnet" / "Mission" / "Mission.csproj"
        build_res = subprocess.run(
            ["dotnet", "build", str(mission_proj), "-c", "Release", "-nologo"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(build_res.returncode, 0, f"Mission.csproj build failed:\n{build_res.stdout}\n{build_res.stderr}")
        self.assertIn("0 Warning(s)", build_res.stdout)

        with tempfile.TemporaryDirectory(prefix="c5_looks_selftest_") as tmp:
            tmp_path = Path(tmp)
            harness_dir = tmp_path / "harness"
            harness_dir.mkdir()
            (harness_dir / "Harness.csproj").write_text(
                f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net9.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
    <ProjectReference Include="{mission_proj}" />
  </ItemGroup>
</Project>
""",
                encoding="utf-8",
            )
            (harness_dir / "Program.cs").write_text(
                """FalloutActorLooks.RunStandaloneSelfTest(args[0]);
Console.WriteLine("C5_STANDALONE_SELFTEST_OK");
""",
                encoding="utf-8",
            )
            esm_dir = tmp_path / "esms"
            run_res = subprocess.run(
                ["dotnet", "run", "--project", str(harness_dir / "Harness.csproj"), "-c", "Release", "--", str(esm_dir)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run_res.returncode, 0, f"C5 standalone selftest failed:\n{run_res.stdout}\n{run_res.stderr}")
            self.assertIn("C5_STANDALONE_SELFTEST_OK", run_res.stdout)

            with Plugin(str(esm_dir / "buggy2f" / "FO4SFMission.esm")) as p_buggy:
                buggy_npcs = {r.formid: r for r in p_buggy.records("NPC_")}
                preston_2f = next(r for r in buggy_npcs.values() if r.edid == "FO4_PrestonGarvey")
                self.assertIsNone(preston_2f.get(b"SOFT"), "2f reproduction should lack SOFT subrecord")
                self.assertEqual(preston_2f.get(b"STON")[0], 4, "2f reproduction retained PapaKatz STON=4")
                self.assertFalse(any(r.edid == "FO4_LvlRaider" for r in buggy_npcs.values()))

            with Plugin(str(esm_dir / "FO4SFMission.esm")) as p_fixed:
                otfts = {r.formid & 0xFFFFFF: r for r in p_fixed.records("OTFT")}
                armos = {r.formid & 0xFFFFFF: r for r in p_fixed.records("ARMO")}
                armas = {r.formid & 0xFFFFFF: r for r in p_fixed.records("ARMA")}
                self.assertEqual(otfts[0x980].edid, "FO4_Outfit_PrestonMinuteman")
                self.assertEqual(otfts[0x988].edid, "FO4_Outfit_ConcordRaider")
                self.assertIn(0x981, armas)
                self.assertIn(0x984, armas)
                self.assertIn(0x989, armas)
                self.assertIn(0x983, armos)
                self.assertIn(0x985, armos)
                self.assertIn(0x98A, armos)

                npcs_by_edid = {r.edid: r for r in p_fixed.records("NPC_")}
                self.assertIn("FO4_PrestonGarvey", npcs_by_edid)
                self.assertIn("FO4_ConcordRaider", npcs_by_edid)
                self.assertNotIn("FO4_LvlRaider", npcs_by_edid, "A2.3: FO4SFMission.esm must not override shared FO4_LvlRaider globally")
                self.assertIn("FO4_Sturges", npcs_by_edid)

                # Non-C5 NPCs (FO4_Sturges) must remain untouched (no SOFT/DOFT injected)
                self.assertIsNone(npcs_by_edid["FO4_Sturges"].get(b"SOFT"))
                self.assertIsNone(npcs_by_edid["FO4_Sturges"].get(b"DOFT"))

                preston = npcs_by_edid["FO4_PrestonGarvey"]
                self.assertEqual(struct.unpack("<I", preston.get(b"DOFT"))[0] & 0xFFFFFF, 0x980)
                self.assertEqual(struct.unpack("<I", preston.get(b"SOFT"))[0] & 0xFFFFFF, 0x980)
                self.assertGreaterEqual(preston.get(b"STON")[0], 5)
                self.assertEqual((preston.get(b"HCOL") or b"").rstrip(b"\0"), b"Black")
                self.assertEqual((preston.get(b"FHCL") or b"").rstrip(b"\0"), b"Black")
                mwgt = struct.unpack("<3f", preston.get(b"MWGT"))
                self.assertAlmostEqual(mwgt[0], 0.3566, places=3)
                self.assertAlmostEqual(mwgt[1], 0.3468, places=3)
                self.assertAlmostEqual(mwgt[2], 0.2966, places=3)

                for ed in ("FO4_PrestonGarvey", "FO4_ConcordRaider"):
                    prps = npcs_by_edid[ed].get(b"PRPS") or b""
                    self.assertEqual(len(prps) % 12, 0)
                    entries = [struct.unpack_from("<IfI", prps, off) for off in range(0, len(prps), 12)]
                    self.assertTrue(
                        any((av & 0xFFFFFF) == 0x0B120E and abs(val - 1.0) < 1e-4 for av, val, _ in entries),
                        f"{ed} PRPS missing 0x0B120E == 1.0: {entries}",
                    )

                concord_raider = npcs_by_edid["FO4_ConcordRaider"]
                self.assertEqual(concord_raider.formid & 0xFFFFFF, 0x000986)
                self.assertEqual(struct.unpack("<I", concord_raider.get(b"DOFT"))[0] & 0xFFFFFF, 0x988)
                self.assertEqual(struct.unpack("<I", concord_raider.get(b"SOFT"))[0] & 0xFFFFFF, 0x988)

    def test_c5_doc_and_source_hygiene(self):
        self.assertFalse(
            (REPO_ROOT / "docs" / "design" / "c5-actor-and-hud-looks.md").exists(),
            "C5 report must live under docs/actors/c5-actor-and-hud-looks-report.md (not docs/design/)",
        )
        doc_path = REPO_ROOT / "docs" / "actors" / "c5-actor-and-hud-looks-report.md"
        owned = [
            REPO_ROOT / "dotnet" / "Mission" / "FalloutActorLooks.cs",
            REPO_ROOT / "scripts" / "actors" / "stage_c5_actor_looks.py",
            doc_path,
            REPO_ROOT / "tests" / "test_r10_c5_looks.py",
        ]
        for path in owned:
            self.assertTrue(path.is_file(), f"Missing owned file: {path}")
            raw = path.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM present in {path.name}")
            text = raw.decode("utf-8")
            if path.name != "test_r10_c5_looks.py":
                leaks = DRIVE_LEAK_RE.findall(text)
                self.assertEqual(leaks, [], f"Local drive-letter path leak in {path.name}: {leaks}")

        doc_lines = doc_path.read_text(encoding="utf-8").splitlines()
        self.assertTrue(
            doc_lines[0].startswith("Titles: Fallout 4") and "| Modes:" in doc_lines[0] and "| Track:" in doc_lines[0],
            f"Line 1 lacks canonical Titles/Modes/Track header: {doc_lines[0]!r}",
        )
        self.assertIn("prototype, offline", doc_lines[0])

        doc_text = "\n".join(doc_lines)
        for required_token in (
            "pushed, not run",
            "Starfield chargen approximation, because the FO4 FaceGen head is not converted",
            "0x001A76BD",
            "0x0016D5E5",
            "0x00194ABF",
            "0x000B120E",
            "0x003D094D",
            "0x0003F59A",
            "FO4_Outfit_PrestonMinuteman",
            "FO4_Outfit_ConcordRaider",
            "SkinAttach",
            "WatchFaceComponent_mc",
            "O2Txt_mc",
            "CO2Txt_mc",
            "Planet_tf",
            "## 5. Open Questions for the Owner",
        ):
            self.assertIn(required_token, doc_text, f"Missing required C5 audit token '{required_token}' in doc")

    def test_c3_raider_catalog_and_c5_bundle_verify_refusal(self):
        from fo4sf.core import cross_plugin_check

        sf_cat = cross_plugin_check.KNOWN_EXTERNAL_RECORDS["Starfield.esm"]
        self.assertEqual(sf_cat.get(0x26D96B), ("WEAP", "Coachman"))
        self.assertEqual(sf_cat.get(0x2B4AFB), ("AMMO", "AmmoShotshell"))

        mcb_txt = (REPO_ROOT / "scripts" / "core" / "make_core_bundle.py").read_text(encoding="utf-8")
        self.assertIn("mission_wants_c5", mcb_txt)
        self.assertIn('b"prestongarveyoutfit_m.nif"', mcb_txt)


if __name__ == "__main__":
    unittest.main()
