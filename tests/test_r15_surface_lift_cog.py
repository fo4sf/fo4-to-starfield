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
        self.assertEqual(surf["cog_base_id"], "0x000802")
        self.assertEqual(surf["cog_edid"], "FO4SF_Vault111SurfaceCog")
        self.assertEqual(surf["cog_name"], "Vault 111 Elevator")
        self.assertEqual(surf["states"], {"stage8": "StateA_Play", "stage4": "StateB_Play"})
        self.assertEqual(surf["descend_duration_s"], 18.6667)
        self.assertEqual(surf["descend_fade_at_s"], 7.533)
        self.assertAlmostEqual(surf["rot_z_deg"], 27.811361, places=4)

        # Offset arithmetic consistency: ref_local_pos_m == arrival_local_pos_m + offset
        ax, ay, az = surf["arrival_local_pos_m"]
        ox, oy = surf["xy_offset_m"]
        oz = surf["z_offset_m"]
        rx, ry, rz = surf["ref_local_pos_m"]
        self.assertAlmostEqual(ax + ox, rx, places=4)
        self.assertAlmostEqual(ay + oy, ry, places=4)
        self.assertAlmostEqual(az + oz, rz, places=4)

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
        self.assertIn("0x802", src)
        self.assertIn("FO4SF_Vault111SurfaceCog", src)
        self.assertIn("Vault 111 Elevator", src)
        self.assertIn("ActivatorStateGraph01.agx", src)
        self.assertIn("mod.Worldspaces.Count", src)

        if not shutil.which("dotnet"):
            self.skipTest("dotnet SDK not installed")
        res = subprocess.run(
            ["dotnet", "build", str(ROOT / "dotnet" / "AnimConsoleProbe"), "-c", "Release"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 0, msg=res.stdout + "\n" + res.stderr)

        # Runtime Mutagen check: execute BuildSurfaceCog + CheckSurfaceCog against a real StarfieldMod
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
                'using Mutagen.Bethesda.Plugins;\n'
                'using Mutagen.Bethesda.Plugins.Binary.Parameters;\n'
                'using Mutagen.Bethesda.Plugins.Records;\n'
                'using Mutagen.Bethesda.Starfield;\n'
                'using Noggog;\n'
                'var key = ModKey.FromFileName("FO4SFExitLift.esm");\n'
                'var sfKey = ModKey.FromFileName("Starfield.esm");\n'
                'var portKey = ModKey.FromFileName("FO4Port.esm");\n'
                'var mod = new StarfieldMod(key, StarfieldRelease.Starfield);\n'
                'mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;\n'
                'var model = "fo4port\\\\interiors\\\\vault\\\\rooms\\\\vltelevator\\\\vltelevatorexterior_anim.nif";\n'
                'var rig = "fo4port\\\\interiors\\\\vault\\\\rooms\\\\vltelevator\\\\vltelevatorexterior_anim\\\\characterassets\\\\skeleton.rig";\n'
                'var anims = "fo4port\\\\interiors\\\\vault\\\\rooms\\\\vltelevator\\\\vltelevatorexterior_anim\\\\animations";\n'
                'SurfaceLiftCog.BuildSurfaceCog(mod, model, rig, anims);\n'
                'if (mod.Worldspaces.Count != 0) throw new Exception("expected 0 WRLD");\n'
                'if (mod.ModHeader.Stats.NextFormID < 0x803) throw new Exception("NextFormID not bumped");\n'
                'mod.ModHeader.MasterReferences.Add(new MasterReference { Master = sfKey });\n'
                'mod.ModHeader.MasterReferences.Add(new MasterReference { Master = portKey });\n'
                'var outPath = Path.Combine(AppContext.BaseDirectory, "FO4SFExitLift.esm");\n'
                'mod.BeginWrite.ToPath(outPath).WithLoadOrder(sfKey, portKey)\n'
                '   .WithKnownMasters(new KeyedMasterStyle(sfKey, MasterStyle.Full), new KeyedMasterStyle(portKey, MasterStyle.Full))\n'
                '   .WithMastersListContent(MastersListContentOption.NoCheck).Write();\n'
                'var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);\n'
                'styles.Set(new KeyedMasterStyle(sfKey, MasterStyle.Full));\n'
                'styles.Set(new KeyedMasterStyle(portKey, MasterStyle.Full));\n'
                'using var readBack = StarfieldMod.CreateFromBinaryOverlay(outPath, StarfieldRelease.Starfield, new BinaryReadParameters { MasterFlagsLookup = styles });\n'
                'var probs = SurfaceLiftCog.CheckSurfaceCog(readBack, model, rig, anims);\n'
                'if (probs.Count != 0) throw new Exception("CheckSurfaceCog failed: " + string.Join("; ", probs));\n'
                'var badProbs = SurfaceLiftCog.CheckSurfaceCog(readBack, "wrong.nif", rig, anims);\n'
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
        self.assertEqual(pair["surface"]["cog_edid"], "FO4SF_Vault111SurfaceCog")
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
        self.assertEqual(plan["cog_base_id"], "0x000802")
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
            "lift_pair ride start dir=",
            "lift_pair ride arrived dir=",
            "lift_pair reload recovered ",
        ):
            self.assertIn(line, spec)
        for prop in ("ExitLiftPlugin", "SurfaceCogBaseId", "SurfaceCogOffsetX", "SurfaceCogOffsetY", "SurfaceCogOffsetZ", "SurfaceCogRotZ"):
            self.assertIn(prop, spec)


if __name__ == "__main__":
    unittest.main()
