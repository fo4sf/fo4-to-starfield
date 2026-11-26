"""Offline tests for Round 15 Wave A Item 4b: Vault 111 surface entrance lift cog (bidirectional shared lift pair)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts" / "newgame"))
sys.path.insert(0, str(ROOT / "scripts" / "planet"))
sys.path.insert(0, str(ROOT / "src"))

import stage_surface_lift_cog as sslc  # noqa: E402
from test_anim_console import FakeConv, FakeSrc  # noqa: E402

LIFT_PAIRS_PATH = ROOT / "src" / "fo4sf" / "core" / "lift_pairs.json"
SURFACE_COG_CS = ROOT / "dotnet" / "AnimConsoleProbe" / "SurfaceLiftCog.cs"
PAPYRUS_SPEC = ROOT / "scripts" / "newgame" / "lift_pair_papyrus_spec.txt"


def _valid_surface_cog_anim() -> dict:
    return {
        "skeleton": "fo4port\\interiors\\vault\\rooms\\vltelevator\\vltelevatorexterior_anim\\characterassets\\skeleton.rig",
        "animations": "fo4port\\interiors\\vault\\rooms\\vltelevator\\vltelevatorexterior_anim\\animations",
        "idles": "toggle",
        "moving_bodies": 29,
        "fo4_collision": {
            "carried": True,
            "box_fallback_bones": [],
            "carried_bodies": (
                [{"bone": "c_ExteriorLightR"}] * 1
                + [{"bone": "c_ExteriorLightL"}] * 1
                + [{"bone": "b_Platform"}] * 25
                + [{"bone": "b_Hatch Left"}] * 1
                + [{"bone": "b_Hatch Right"}] * 1
            ),
        },
        "clips": [
            {
                "name": "StateA_Play",
                "seconds": 18.6667,
                "frames": 560,
                "hold_of": None,
                "hold_frame": None,
                "motion": [{"bone": "b_Platform", "travel_m": [0.0, 0.0, -59.1425], "rotation_deg": 0.0}],
            },
            {
                "name": "StateB_Play",
                "seconds": 11.6667,
                "frames": 350,
                "hold_of": None,
                "hold_frame": None,
                "motion": [{"bone": "b_Platform", "travel_m": [0.0, 0.0, 25.9932], "rotation_deg": 0.0}],
            },
            {
                "name": "StateA_Idle",
                "seconds": 0.0,
                "frames": 0,
                "hold_of": "StateA_Play",
                "hold_frame": "first",
                "motion": [{"bone": "b_Platform", "travel_m": [0.0, 0.0, 0.0], "rotation_deg": 0.0}],
            },
            {
                "name": "StateB_Idle",
                "seconds": 0.0,
                "frames": 0,
                "hold_of": "StateA_Play",
                "hold_frame": "last",
                "motion": [{"bone": "b_Platform", "travel_m": [0.0, 0.0, 0.0], "rotation_deg": 0.0}],
            },
        ],
        "pose_boxes_m": {
            "rest": {
                "1": [[-3.0, -3.0, -59.5], [3.0, 3.0, 2.5]],
            },
            "end_of_clip": {},
        },
    }


class FakeSurfaceConv(FakeConv):
    def __init__(self, staging: str, anim_override: dict | None = None, extra_textures: tuple[str, ...] = ()):
        super().__init__(staging)
        self._anim_override = anim_override
        self._extra_textures = extra_textures

    def convert_anim_object(self, nif_name, states, foley=None, **extra):
        out_name = "fo4port/interiors/vault/rooms/vltelevator/vltelevatorexterior_anim"
        for rel in (
            f"meshes/{out_name}.nif",
            f"meshes/{out_name}/characterassets/skeleton.rig",
            f"meshes/{out_name}/animations/StateA_Play.af",
            f"meshes/{out_name}/animations/StateB_Play.af",
            f"meshes/{out_name}/animations/StateA_Idle.af",
            f"meshes/{out_name}/animations/StateB_Idle.af",
            "geometries/abc/def.mesh",
            "materials/fo4port/interiors/vault/vault111/v111elevplatform01.mat",
            "textures/fo4port/interiors/vault/vault111/v111elevplatform01_color.dds",
            *self._extra_textures,
        ):
            p = os.path.join(self.staging, *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(b"fake")
        return {
            "ok": True,
            "out_name": out_name,
            "anim": self._anim_override if self._anim_override is not None else _valid_surface_cog_anim(),
        }


class LiftPairsJsonTests(unittest.TestCase):
    def test_schema_fo4_vault111_exit_and_fo3_fnv_support(self):
        data = json.loads(LIFT_PAIRS_PATH.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["supported_games"], ["FO4", "FO3", "FNV"])
        pairs = data["pairs"]

        v111 = pairs["fo4.vault111_exit"]
        self.assertTrue(v111["available"])
        self.assertEqual(v111["game"], "FO4")
        self.assertEqual(v111["platform_radius_m"], 2.0)
        self.assertEqual(v111["interior"]["fo4_ref_id"], "0x0244EB")
        self.assertEqual(v111["interior"]["fo4_base_id"], "0x0244EF")

        surf = v111["surface"]
        self.assertEqual(surf["cog_plugin"], "FO4SFExitLift.esm")
        self.assertEqual(surf["core_plugin"], "FO4TerrainCore.esm")
        self.assertEqual(surf["core_static_base_id"], "0x0A2D4B")
        self.assertEqual(surf["core_static_base_edid"], "FO4Core_acti_19d22f_fallout4")
        self.assertEqual(surf["cog_name"], "Vault 111 Elevator")
        self.assertEqual(surf["states"], {"stage8": "StateA_Play", "stage4": "StateB_Play"})
        self.assertEqual(surf["descend_duration_s"], 18.6667)
        self.assertEqual(surf["descend_fade_at_s"], 7.533)
        self.assertEqual(len(surf["ref_local_pos_m"]), 3)
        for forbidden in ("cog_base_id", "cog_edid", "xy_offset_m", "z_offset_m", "rot_z_deg", "rot_z_rad"):
            self.assertNotIn(forbidden, surf)

        # FO3 & FNV schema entries exist and cleanly declare unavailable_reason
        for game, key in (("FO3", "fo3.vault101_exit"), ("FNV", "fnv.vault22_exit")):
            entry = pairs[key]
            self.assertEqual(entry["game"], game)
            self.assertFalse(entry["available"])
            reason = entry["unavailable_reason"].strip()
            self.assertTrue(reason and "\n" not in reason)
            for req in data["pair_schema"]["required_keys"]:
                self.assertIn(req, entry)


class SurfaceLiftCogCSharpTests(unittest.TestCase):
    def test_surface_lift_cog_cs_contract_and_build(self):
        src = SURFACE_COG_CS.read_text(encoding="utf-8")
        self.assertIn("BuildSurfaceCog", src)
        self.assertIn("CheckSurfaceCog", src)
        self.assertIn("0x0A2D4B", src)
        self.assertIn("FO4TerrainCore.esm", src)
        self.assertIn("FO4Core_acti_19d22f_fallout4", src)
        self.assertIn("ActivatorStateGraph01.agx", src)
        self.assertIn("ObjectBounds", src)
        self.assertIn("MarkerColor", src)
        self.assertIn("ActivationAngle", src)
        self.assertNotIn("0x802", src)
        self.assertNotIn("FO4SF_Vault111SurfaceCog", src)

        if not shutil.which("dotnet"):
            self.skipTest("dotnet SDK not installed")
        res = subprocess.run(
            ["dotnet", "build", str(ROOT / "dotnet" / "AnimConsoleProbe"), "-c", "Release"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 0, msg=res.stdout + "\n" + res.stderr)

        # Runtime Mutagen check: execute BuildSurfaceCog + CheckSurfaceCog overriding 0x0A2D4B
        bin_dir = ROOT / "dotnet" / "AnimConsoleProbe" / "bin" / "Release" / "net9.0"
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            (tdir / "Harness.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk">\n'
                '  <PropertyGroup>\n'
                '    <OutputType>Exe</OutputType>\n'
                '    <TargetFramework>net9.0</TargetFramework>\n'
                '    <ImplicitUsings>enable</ImplicitUsings>\n'
                '    <Nullable>enable</Nullable>\n'
                '  </PropertyGroup>\n'
                '  <ItemGroup>\n'
                '    <PackageReference Include="Mutagen.Bethesda.Starfield" Version="0.55.0-alpha.67" />\n'
                f'    <Reference Include="AnimConsoleProbe"><HintPath>{bin_dir / "AnimConsoleProbe.dll"}</HintPath></Reference>\n'
                '  </ItemGroup>\n'
                '</Project>\n',
                encoding="utf-8",
            )
            (tdir / "Program.cs").write_text(
                'using System.Drawing;\n'
                'using Mutagen.Bethesda.Plugins;\n'
                'using Mutagen.Bethesda.Plugins.Binary.Parameters;\n'
                'using Mutagen.Bethesda.Plugins.Records;\n'
                'using Mutagen.Bethesda.Starfield;\n'
                'using Noggog;\n'
                'var key = ModKey.FromFileName("FO4SFExitLift.esm");\n'
                'var sfKey = ModKey.FromFileName("Starfield.esm");\n'
                'var portKey = ModKey.FromFileName("FO4Port.esm");\n'
                'var coreKey = ModKey.FromFileName("FO4TerrainCore.esm");\n'
                'var core = new StarfieldMod(coreKey, StarfieldRelease.Starfield);\n'
                'core.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;\n'
                'core.Activators.Add(new Mutagen.Bethesda.Starfield.Activator(new FormKey(coreKey, 0x0A2D4B), StarfieldRelease.Starfield)\n'
                '{\n'
                '    EditorID = "FO4Core_acti_19d22f_fallout4",\n'
                '    Model = new Model { File = "fo4core\\\\vltelevatorexterior.nif" },\n'
                '});\n'
                'var interiorOv = new Mutagen.Bethesda.Starfield.Activator(new FormKey(portKey, 0x00E0E6), StarfieldRelease.Starfield)\n'
                '{\n'
                '    EditorID = "FO4Port_acti_0244ef_fallout4",\n'
                '    MarkerColor = Color.FromArgb(0, 0xCC, 0x4C, 0x33),\n'
                '    Flags = (Mutagen.Bethesda.Starfield.Activator.Flag)0,\n'
                '    ActivationAngle = 360,\n'
                '};\n'
                'var mod = new StarfieldMod(key, StarfieldRelease.Starfield);\n'
                'mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;\n'
                'var model = "fo4port\\\\interiors\\\\vault\\\\rooms\\\\vltelevator\\\\vltelevatorexterior_anim.nif";\n'
                'var rig = "fo4port\\\\interiors\\\\vault\\\\rooms\\\\vltelevator\\\\vltelevatorexterior_anim\\\\characterassets\\\\skeleton.rig";\n'
                'var anims = "fo4port\\\\interiors\\\\vault\\\\rooms\\\\vltelevator\\\\vltelevatorexterior_anim\\\\animations";\n'
                'var bMin = new P3Float(-3.0f, -3.0f, -59.5f);\n'
                'var bMax = new P3Float(3.0f, 3.0f, 2.5f);\n'
                'SurfaceLiftCog.BuildSurfaceCog(mod, core, interiorOv, model, rig, anims, bMin, bMax);\n'
                'if (mod.Worldspaces.Count != 0) throw new Exception("expected 0 WRLD");\n'
                'mod.ModHeader.MasterReferences.Add(new MasterReference { Master = sfKey });\n'
                'mod.ModHeader.MasterReferences.Add(new MasterReference { Master = portKey });\n'
                'mod.ModHeader.MasterReferences.Add(new MasterReference { Master = coreKey });\n'
                'var outPath = Path.Combine(AppContext.BaseDirectory, "FO4SFExitLift.esm");\n'
                'mod.BeginWrite.ToPath(outPath).WithLoadOrder(sfKey, portKey, coreKey)\n'
                '   .WithKnownMasters(new KeyedMasterStyle(sfKey, MasterStyle.Full), new KeyedMasterStyle(portKey, MasterStyle.Full), new KeyedMasterStyle(coreKey, MasterStyle.Full))\n'
                '   .WithMastersListContent(MastersListContentOption.NoCheck).Write();\n'
                'var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);\n'
                'styles.Set(new KeyedMasterStyle(sfKey, MasterStyle.Full));\n'
                'styles.Set(new KeyedMasterStyle(portKey, MasterStyle.Full));\n'
                'styles.Set(new KeyedMasterStyle(coreKey, MasterStyle.Full));\n'
                'using var readBack = StarfieldMod.CreateFromBinaryOverlay(outPath, StarfieldRelease.Starfield, new BinaryReadParameters { MasterFlagsLookup = styles });\n'
                'var probs = SurfaceLiftCog.CheckSurfaceCog(readBack, core, interiorOv, model, rig, anims, bMin, bMax);\n'
                'if (probs.Count != 0) throw new Exception("CheckSurfaceCog failed: " + string.Join("; ", probs));\n'
                'var badProbs = SurfaceLiftCog.CheckSurfaceCog(readBack, core, interiorOv, "wrong.nif", rig, anims, bMin, bMax);\n'
                'if (badProbs.Count == 0) throw new Exception("CheckSurfaceCog did not catch model mismatch");\n'
                'Console.WriteLine("SurfaceLiftCog runtime check OK");\n',
                encoding="utf-8",
            )
            run_res = subprocess.run(
                ["dotnet", "run", "--project", str(tdir)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run_res.returncode, 0, msg=run_res.stdout + "\n" + run_res.stderr)
            self.assertIn("SurfaceLiftCog runtime check OK", run_res.stdout)


class StageSurfaceLiftCogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.sf_data = self.tmp / "sf_data"
        self.sf_data.mkdir()
        (self.sf_data / "Starfield.esm").write_bytes(b"SF")
        (self.sf_data / "FO4Port.esm").write_bytes(b"PORT")
        self.fo4_data = self.tmp / "fo4_data"
        self.fo4_data.mkdir()

    def _args(self, out: Path):
        from types import SimpleNamespace

        return SimpleNamespace(
            out=str(out),
            pair="fo4.vault111_exit",
            lift_pairs=str(LIFT_PAIRS_PATH),
            starfield_data=str(self.sf_data),
            port_data=str(self.sf_data),
            fo4_data=str(self.fo4_data),
            door_anim_dll="CALUMI.Animation.dll",
            collision_template="tmpl.nif",
            texconv="texconv.exe",
            content_resources="ContentResources.zip",
            foley="",
        )

    def test_load_lift_pair_refuses_unavailable_or_unknown(self):
        pair = sslc.load_lift_pair("fo4.vault111_exit")
        self.assertEqual(pair["surface"]["core_static_base_id"], "0x0A2D4B")
        self.assertEqual(pair["surface"]["core_static_base_edid"], "FO4Core_acti_19d22f_fallout4")
        for bad in ("fo3.vault101_exit", "fnv.vault22_exit", "unknown.pair"):
            with self.assertRaises(SystemExit):
                sslc.load_lift_pair(bad)

    def test_validate_surface_cog_animation_accepts_and_rejects_drift(self):
        pair = sslc.load_lift_pair("fo4.vault111_exit")
        good = _valid_surface_cog_anim()
        sslc.validate_surface_cog_animation(good, pair)

        bad_idle = _valid_surface_cog_anim()
        bad_idle["idles"] = "hold"
        with self.assertRaises(SystemExit):
            sslc.validate_surface_cog_animation(bad_idle, pair)

        bad_fb = _valid_surface_cog_anim()
        bad_fb["fo4_collision"]["box_fallback_bones"] = ["b_Platform"]
        with self.assertRaises(SystemExit):
            sslc.validate_surface_cog_animation(bad_fb, pair)

        bad_rest = _valid_surface_cog_anim()
        bad_rest["clips"][2]["hold_frame"] = "last"
        with self.assertRaises(SystemExit):
            sslc.validate_surface_cog_animation(bad_rest, pair)

        bad_drop = _valid_surface_cog_anim()
        bad_drop["clips"][0]["motion"][0]["travel_m"] = [0.0, 0.0, -21.6]
        with self.assertRaises(SystemExit):
            sslc.validate_surface_cog_animation(bad_drop, pair)

    def test_stage_and_verify_round_trip_with_fake_converter(self):
        out = self.tmp / "surface-cog-stage"
        port_textures = {"textures/fo4port/interiors/vault/vault111/v111elevplatform01_color.dds"}
        rc = sslc.stage(
            self._args(out),
            converter=lambda _a, st: (FakeSrc(b"nif"), FakeSurfaceConv(st)),
            port_names_fn=lambda _d: port_textures,
        )
        self.assertEqual(rc, 0)
        self.assertTrue((out / "plan.json").is_file())
        self.assertTrue((out / "surface_cog_manifest.json").is_file())
        self.assertEqual([p.name for p in self.tmp.glob("*.partial-*")], [])

        plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["kind"], sslc.SURFACE_COG_KIND)
        self.assertEqual(plan["world_overrides"], 0)
        self.assertEqual(plan["core_static_base_id"], "0x0A2D4B")
        self.assertEqual(plan["bounds"], [[-3.0, -3.0, -59.5], [3.0, 3.0, 2.5]])
        self.assertNotIn("cog_base_id", plan)
        self.assertEqual(sslc.verify_stage(str(out), plan, str(self.sf_data)), [])

        # Missing texture in FO4Port*.ba2 must refuse
        out_missing_tex = self.tmp / "surface-cog-missing-tex"
        with self.assertRaisesRegex(SystemExit, "texture"):
            sslc.stage(
                self._args(out_missing_tex),
                converter=lambda _a, st: (FakeSrc(b"nif"), FakeSurfaceConv(st)),
                port_names_fn=lambda _d: set(),
            )
        self.assertFalse(out_missing_tex.exists())

        # Output inside git worktree must refuse
        with self.assertRaisesRegex(SystemExit, "forbidden"):
            sslc.stage(
                self._args(ROOT / "tests" / "forbidden-out"),
                converter=lambda _a, st: (FakeSrc(b"nif"), FakeSurfaceConv(st)),
                port_names_fn=lambda _d: port_textures,
            )

        # Tampering after stage is detected by verify_stage
        mat = out / "Data" / "materials" / "fo4port" / "interiors" / "vault" / "vault111" / "v111elevplatform01.mat"
        mat.write_bytes(b"tampered")
        problems = sslc.verify_stage(str(out), plan, str(self.sf_data))
        self.assertTrue(any("changed after stage" in p for p in problems))

    def test_verify_stage_accepts_separate_starfield_and_port_dirs(self):
        from types import SimpleNamespace

        sf_only = self.tmp / "sf_only"
        port_only = self.tmp / "port_only"
        sf_only.mkdir()
        port_only.mkdir()
        (sf_only / "Starfield.esm").write_bytes(b"SF-ONLY")
        (port_only / "FO4Port.esm").write_bytes(b"PORT-ONLY")

        out = self.tmp / "surface-cog-split-dirs"
        port_textures = {"textures/fo4port/interiors/vault/vault111/v111elevplatform01_color.dds"}
        args = SimpleNamespace(
            out=str(out),
            pair="fo4.vault111_exit",
            lift_pairs=str(LIFT_PAIRS_PATH),
            starfield_data=str(sf_only),
            port_data=str(port_only),
            fo4_data=str(self.fo4_data),
            door_anim_dll="CALUMI.Animation.dll",
            collision_template="tmpl.nif",
            texconv="texconv.exe",
            content_resources="ContentResources.zip",
            foley="",
        )
        rc = sslc.stage(
            args,
            converter=lambda _a, st: (FakeSrc(b"nif"), FakeSurfaceConv(st)),
            port_names_fn=lambda _d: port_textures,
        )
        self.assertEqual(rc, 0)
        plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
        self.assertEqual(sslc.verify_stage(str(out), plan, str(port_only), str(sf_only)), [])
        missing_sf = sslc.verify_stage(str(out), plan, str(port_only))
        self.assertTrue(any("missing Starfield.esm" in p for p in missing_sf), msg=missing_sf)


class PapyrusSpecContractTests(unittest.TestCase):
    def test_spec_defines_unified_functions_and_exact_log_lines(self):
        spec = PAPYRUS_SPEC.read_text(encoding="utf-8")
        for fn in (
            "EnsureSurfaceLiftCog(Actor player)",
            "StartPairedLiftRide(Actor player, bool descending)",
            "CheckPairedLiftRide(Actor player)",
            "RecoverPairedLiftOnLoad(Actor player)",
        ):
            self.assertIn(fn, spec)
        for line in (
            "lift_pair surface_cog ready ",
            "lift_pair transfer dir=",
            "lift_pair ride start dir=",
            "lift_pair ride arrived dir=",
            "lift_pair reload recovered ",
        ):
            self.assertIn(line, spec)
        for prop in ("ExitLiftPlugin", "SurfaceCogLocalX", "SurfaceCogLocalY", "SurfaceCogLocalZ", "CoreStaticSurfaceLiftBaseId"):
            self.assertIn(prop, spec)
        self.assertNotIn("SurfaceCogOffset", spec)
        self.assertNotIn("+ 94.0", spec)


class G4SingleElevatorVerificationTests(unittest.TestCase):
    def test_no_surface_cog_offset_or_plus_94_or_0x802_or_placeatme_cog(self):
        for rel in (
            "scripts/newgame/FO4SF_NewGameQuest.psc",
            "scripts/newgame/lift_pair_papyrus_spec.txt",
            "scripts/newgame/stage_surface_lift_cog.py",
            "scripts/newgame/make_anim_console.py",
            "dotnet/NewGame/Program.cs",
            "dotnet/AnimConsoleProbe/SurfaceLiftCog.cs",
            "src/fo4sf/core/lift_pairs.json",
            "src/fo4sf/core/cross_plugin_check.py",
        ):
            txt = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("SurfaceCogOffset", txt, f"{rel} still defines or references SurfaceCogOffset*")
            self.assertNotIn("+ 94.0", txt, f"{rel} still contains '+ 94.0'")
        psc = (ROOT / "scripts/newgame/FO4SF_NewGameQuest.psc").read_text(encoding="utf-8")
        self.assertNotIn("PlaceAtMe", psc[psc.index("Function EnsureSurfaceLiftCog"):psc.index("Function FailPairedLift")])
        self.assertNotIn("FO4SF_Vault111SurfaceCog", psc)
        self.assertNotIn("0x000802", ROOT.joinpath("src/fo4sf/core/lift_pairs.json").read_text(encoding="utf-8"))

    def test_cog_resolves_within_2m_matches_static_refr_within_005m_and_logs_hex_once_per_arrival(self):
        import math
        from types import SimpleNamespace
        from test_exit_arrival import translated_functions

        psc = (ROOT / "scripts/newgame/FO4SF_NewGameQuest.psc").read_text(encoding="utf-8")
        pair = json.loads(LIFT_PAIRS_PATH.read_text(encoding="utf-8"))["pairs"]["fo4.vault111_exit"]
        mx, my, _mz = pair["merge_offset_m"]
        rx, ry, rz = pair["surface"]["ref_local_pos_m"]
        ax, ay, az = pair["surface"]["arrival_local_pos_m"]
        static_merged = (rx + mx, ry + my, rz)

        class FakeCog:
            def __init__(self, fid, pos, rotz=27.811361):
                self.fid, self.pos, self.rotz = fid, pos, rotz
                self.loaded = True
                self.set_positions = []
                self.disables = []
            def Is3DLoaded(self): return self.loaded
            def GetFormID(self): return (self.fid - 0x100000000) if self.fid >= 0x80000000 else self.fid
            def GetPositionX(self): return self.pos[0]
            def GetPositionY(self): return self.pos[1]
            def GetPositionZ(self): return self.pos[2]
            def GetAngleZ(self): return self.rotz
            def SetPosition(self, *a): self.set_positions.append(a)
            def DisableNoWait(self, *a): self.disables.append(a)
            def PlayAnimation(self, *_a): return True
            def Reset(self): pass

        host_world = object()
        vault_cell = object()
        base_0a2d4b = object()
        cog1 = FakeCog(0xFF001234, static_merged)
        cog2 = FakeCog(0xFF005678, static_merged)
        active_cog = [cog1]
        find_calls = []
        place_calls = []
        traces = []

        def find_closest(form, fx, fy, fz, radius):
            find_calls.append((form, fx, fy, fz, radius))
            if form is base_0a2d4b and radius == 2.0:
                dx = active_cog[0].GetPositionX() - fx
                dy = active_cog[0].GetPositionY() - fy
                dz = active_cog[0].GetPositionZ() - fz
                if math.sqrt(dx * dx + dy * dy + dz * dz) <= radius:
                    return active_cog[0]
            return None

        player = SimpleNamespace(
            Is3DLoaded=lambda: True,
            IsInInterior=lambda: False,
            GetWorldSpace=lambda: host_world,
            GetParentCell=lambda: vault_cell,
            GetPositionX=lambda: ax + mx,
            GetPositionY=lambda: ay + my,
            GetPositionZ=lambda: az,
            PlaceAtMe=lambda *a: place_calls.append(a),
        )
        custom_events = []
        ns = {
            "ArrivalX": ax, "ArrivalY": ay, "ArrivalZ": az,
            "MergeOffsetX": mx, "MergeOffsetY": my,
            "ActiveLiftPairId": "fo4.vault111_exit",
            "LiftPairIds": ["fo4.vault111_exit"],
            "SurfaceCogLocalX": [rx], "SurfaceCogLocalY": [ry], "SurfaceCogLocalZ": [rz],
            "SurfaceCogPadRadius": [3.2],
            "CorePlugin": "FO4TerrainCore.esm", "SurfaceCoreStaticBaseIds": [0x0A2D4B],
            "VaultPlugin": "FO4Port.esm",
            "PlatformX": 0.0, "PlatformY": 0.0, "PlatformZ": 0.0, "PlatformRadius": 2.0,
            "LiftRise": 21.6, "LiftSeconds": 9.8667, "LiftFadeLead": 1.1, "LiftDoneMargin": 0.25,
            "LiftPlayEvent": "Play01", "LiftResetEvent": "Play02",
            "SurfaceLiftSeconds": [18.6667], "SurfaceLiftFadeAt": [7.533], "SurfaceLiftDoneMargin": [0.25],
            "SurfaceLiftPlayEvents": ["Play01"], "SurfaceLiftResetEvents": ["Play02"],
            "SurfaceLiftAscendSeconds": [11.6667], "SurfaceLiftAscendRise": [25.9932],
            "surfaceCogRefs": None, "surfaceCogActivationReg": None, "surfaceCogLogged": None,
            "liftPairActive": False, "liftPairDescending": False, "liftPairDone": False,
            "liftPairTransferred": False, "liftPairTransferPending": False, "liftPairFadeStarted": False,
            "liftPairActiveRef": None, "liftPairStartCell": None, "liftPairStartWorld": None,
            "liftPairStartedAt": 0.0, "liftPairStartX": 0.0, "liftPairStartY": 0.0, "liftPairStartZ": 0.0,
            "liftPairTransferRetries": 0,
            "asked": False, "returnAsked": False, "returnVaultAsked": False, "leftArrivalPad": False, "returnLiftArmed": False,
            "surfaceMovedAt": 0.0, "surfaceMoves": 0, "surfaceSets": 0, "exitFailures": 0,
            "ResolveHostWorld": lambda: host_world,
            "Game": SimpleNamespace(
                GetFormFromFile=lambda fid, plg: base_0a2d4b if (fid, plg) == (0x0A2D4B, "FO4TerrainCore.esm") else None,
                FindClosestReferenceOfType=find_closest,
                FadeOutGame=lambda *_: None,
            ),
            "Utility": SimpleNamespace(GetCurrentRealTime=lambda: 100.0),
            "RegisterForRemoteEvent": lambda *_: None,
            "UnregisterForRemoteEvent": lambda *_: None,
            "UnregisterForAnimationEvent": lambda *_: None,
            "SendCustomEvent": lambda ev, args: custom_events.append((ev, list(args))),
            "Trace": traces.append,
            "GetStage": lambda: 200,
        }
        code = translated_functions(
            psc,
            (
                "HexDigit", "HexFormId", "PairIndex", "EnsurePairCogStorage",
                "GetPairSurfaceCog", "SetPairSurfaceCog", "GetPairCogActivationReg", "SetPairCogActivationReg",
                "GetPairCogLogged", "SetPairCogLogged",
                "PairSurfaceCogLocalX", "PairSurfaceCogLocalY", "PairSurfaceCogLocalZ",
                "PairSurfaceCogPadRadius", "PairSurfaceLiftSeconds", "PairSurfaceLiftFadeAt",
                "PairSurfaceLiftDoneMargin", "PairSurfacePlayEvent", "PairSurfaceResetEvent",
                "PairSurfaceAscendSeconds", "PairSurfaceAscendRise", "PairCoreStaticCogBaseId",
                "EmitLiftPairArrived", "ResetSurfaceLiftCog", "EnsureSurfaceLiftCog",
                "FailPairedLift", "RecoverPairedLiftOnLoad", "CheckPairedLiftRide",
            ),
            "surfaceCogRefs, surfaceCogActivationReg, surfaceCogLogged, liftPairActive, liftPairDescending, liftPairDone, liftPairTransferred, liftPairTransferPending, liftPairFadeStarted, liftPairActiveRef, liftPairStartCell, liftPairStartWorld, liftPairTransferRetries, surfaceMovedAt, surfaceMoves, surfaceSets, asked, returnAsked, returnVaultAsked, leftArrivalPad, returnLiftArmed",
        )
        exec(compile(code, "PSC", "exec"), ns)

        resolved1 = ns["EnsureSurfaceLiftCog"](player)
        self.assertIs(resolved1, cog1)
        self.assertEqual(find_calls[-1][4], 2.0)
        self.assertEqual(place_calls, [])
        self.assertEqual(cog1.disables, [])
        self.assertEqual(cog1.set_positions, [])
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip((cog1.GetPositionX(), cog1.GetPositionY(), cog1.GetPositionZ()), static_merged)))
        self.assertLessEqual(dist, 0.05)

        # Repeated calls on the same arrival must log only once
        ns["EnsureSurfaceLiftCog"](player)
        ns["EnsureSurfaceLiftCog"](player)
        ready_lines = [t for t in traces if t.startswith("lift_pair surface_cog ready ")]
        self.assertEqual(len(ready_lines), 1)
        self.assertIn("ref=0xFF001234", ready_lines[0])
        self.assertIn("base=FO4TerrainCore.esm:0x000A2D4B", ready_lines[0])

        # Save/load replaces merged-overlay FF instance -> must re-resolve within 2 m and log once for new instance
        active_cog[0] = cog2
        ns["RecoverPairedLiftOnLoad"](player)
        ready_lines2 = [t for t in traces if t.startswith("lift_pair surface_cog ready ")]
        self.assertEqual(len(ready_lines2), 2)
        self.assertIn("ref=0xFF005678", ready_lines2[1])

        # Verify lift_pair transfer log format
        ns["liftPairActive"] = True
        ns["liftPairDescending"] = False
        ns["liftPairDone"] = True
        ns["liftPairStartedAt"] = 90.0
        ns["liftPairStartX"] = player.GetPositionX()
        ns["liftPairStartY"] = player.GetPositionY()
        ns["liftPairStartZ"] = -1.7
        ns["liftPairStartCell"] = player.GetParentCell()
        ns["liftPairActiveRef"] = SimpleNamespace(Is3DLoaded=lambda: True, GetParentCell=lambda: player.GetParentCell())
        ns["Surface"] = lambda *_: None
        player_up = SimpleNamespace(**{**player.__dict__, "GetPositionZ": lambda: 19.9, "IsInInterior": lambda: True})
        ns["CheckPairedLiftRide"](player_up)
        transfer_lines = [t for t in traces if t.startswith("lift_pair transfer ")]
        self.assertEqual(len(transfer_lines), 1)
        self.assertIn("dir=up z=19.9 drop=", transfer_lines[0])
        self.assertIn("elapsed=10.0", transfer_lines[0])

        # Verify EmitLiftPairArrived sends real CustomEvent LiftPairArrived with [pairId, dir, z]
        ns["EmitLiftPairArrived"]("fo4.vault111_exit", "down", -1.5)
        self.assertEqual(custom_events, [("LiftPairArrived", ["fo4.vault111_exit", "down", -1.5])])


if __name__ == "__main__":
    unittest.main()
