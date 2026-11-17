"""Unit tests for Phase B 2d (CF-9 Power Armor Core + #806 FNV Salvaged NCR worn ARMO).

Covers:
  1. C# <-> Papyrus FormID parity, zero-property Quest contract, and Papyrus reserved-type-name lint.
  2. precheck, fake-compiler stage, verify, fold --hardlink (verifying core README.txt is never mutated via hardlink),
     and tamper refusals on rogue ESMs or altered PEX files.
  3. Ride-along installer isolation (FO4SFPowerArmor.install.json leaves FO4SFExp.install.json and
     FO4SFPowerArmorProbe.install.json untouched).
  4. core_log.py parsing, multi-run splitting, save/reload (`reload_sync`) continuity, Papyrus error capture,
     and PASS / PARTIAL / INCONCLUSIVE verdicts across climb-in, drain, reload, exit restore, and salvaged NCR.
  5. Public-surface cleanliness check across all PowerArmorCore source, script, and doc files.
  6. Opt-in C# Mutagen self-test (`FO4SF_DOTNET_TESTS=1`) exercising clean build, `--override-dfob` build,
     6-limb BPTD check, dual-race ARMA skin/piece check, and negative tamper rejections.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "powerarmor"))
sys.path.insert(0, str(ROOT / "scripts" / "game"))
sys.path.insert(0, str(ROOT / "src"))

import make_power_armor_core as mpac  # noqa: E402
import power_armor_core_install as paci  # noqa: E402
from fo4sf.powerarmor import core_log  # noqa: E402

PSC_PATH = ROOT / "scripts" / "powerarmor" / "FO4SF_PowerArmorCoreQuest.psc"
CS_PATH = ROOT / "dotnet" / "PowerArmorCore" / "Program.cs"
DOC_PATH = ROOT / "docs" / "powerarmor" / "power-armor-core.md"
PSC_TEXT = PSC_PATH.read_text(encoding="utf-8")
CS_TEXT = CS_PATH.read_text(encoding="utf-8")


def parse_cs_uint_consts(text):
    out = {}
    for m in re.finditer(r"const uint ([^;]+);", text):
        for name, val in re.findall(r"(\w+)\s*=\s*(0x[0-9A-Fa-f]+)", m.group(1)):
            out[name] = int(val, 16)
    return out


def make_fake_content_resources(zip_path, omit=()):
    """Write a minimal synthetic ContentResources.zip declaring the Starfield script hierarchy."""
    omit_set = set(omit)
    files = {
        "Scripts/Source/Starfield_Papyrus_Flags.flg": "Flags {}\n",
        "Scripts/Source/ScriptObject.psc": "\n".join(
            ln for key, ln in [
                ("ScriptObject.StartTimer", "Function StartTimer(float afInterval, int aiTimerID = 0) native"),
                ("ScriptObject.RegisterForRemoteEvent", "bool Function RegisterForRemoteEvent(ScriptObject akSrc, string asEvent) native"),
            ] if key not in omit_set
        ) + "\nScriptname ScriptObject Native\n",
        "Scripts/Source/Form.psc": "Scriptname Form extends ScriptObject Native\nint Function GetFormID() native\n",
        "Scripts/Source/Quest.psc": "Scriptname Quest extends Form Native\nbool Function GetStageDone(int aiStage)\nEndFunction\n",
        "Scripts/Source/ObjectReference.psc": (
            "Scriptname ObjectReference extends Form Native\n"
            + "\n".join(
                f"Function {fn}() native"
                for fn in mpac.REQUIRED["ObjectReference"]
                if f"ObjectReference.{fn}" not in omit_set
            )
            + "\n"
        ),
        "Scripts/Source/Actor.psc": (
            "Scriptname Actor extends ObjectReference Native\n"
            + "\n".join(
                (f"Event {fn}()\nEndEvent" if fn.startswith("On") else f"Function {fn}() native")
                for fn in mpac.REQUIRED["Actor"]
                if f"Actor.{fn}" not in omit_set
            )
            + "\n"
        ),
        "Scripts/Source/Game.psc": "Scriptname Game Native\nActor Function GetPlayer() global native\nForm Function GetFormFromFile(int aiId, string asFile) global native\nbool Function IsPluginInstalled(string asFile) global native\n",
        "Scripts/Source/Debug.psc": "Scriptname Debug Native\nbool Function OpenUserLog(string s) global native\nbool Function TraceUser(string s, string m) global native\nFunction Notification(string m) global native\n",
        "Scripts/Source/Utility.psc": "Scriptname Utility Native\nfloat Function GetCurrentRealTime() global native\n",
        "Scripts/Source/Math.psc": "Scriptname Math Native\nfloat Function Sqrt(float v) global native\n",
    }
    with zipfile.ZipFile(zip_path, "w") as z:
        for arc, body in files.items():
            z.writestr(arc, body)


def make_fake_compiler(td_path):
    """Create a cross-platform fake Papyrus compiler producing deterministic .pex bytes."""
    py_script = Path(td_path) / "fake_papyrus.py"
    py_script.write_text(
        "import os, sys\n"
        "psc = sys.argv[1]\n"
        "out = [a[3:] for a in sys.argv[2:] if a.startswith('-o=')][0]\n"
        "os.makedirs(out, exist_ok=True)\n"
        "stem = os.path.splitext(os.path.basename(psc))[0]\n"
        "with open(psc, 'rb') as f: data = f.read()\n"
        "with open(os.path.join(out, stem + '.pex'), 'wb') as o: o.write(b'FAKAPEX:' + data[:64])\n"
        "print('Compilation succeeded.')\n",
        encoding="utf-8",
    )
    if os.name == "nt":
        wrapper = Path(td_path) / "fake_compiler.cmd"
        wrapper.write_text(f'@"{sys.executable}" "{py_script}" %*\r\n', encoding="utf-8")
    else:
        wrapper = Path(td_path) / "fake_compiler.sh"
        wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{py_script}" "$@"\n', encoding="utf-8")
        wrapper.chmod(0o755)
    return str(wrapper)


class PowerArmorCoreScriptAndContractTests(unittest.TestCase):
    def test_psc_and_csharp_formids_match_exactly(self):
        cs_ids = parse_cs_uint_consts(CS_TEXT)
        shared = (
            "CellId",
            "FrameFurnId",
            "RaceId",
            "BodyPartDataId",
            "SkinId",
            "QuestId",
            "ArmorKeywordId",
            "SalvagedKeywordId",
            "FrameFurnKeywordId",
            "FusionCoreId",
            "InPaAvId",
            "FusionChargeAvId",
            "CondHeadId",
            "CondTorsoId",
            "CondLeftArmId",
            "CondRightArmId",
            "CondLeftLegId",
            "CondRightLegId",
            "FrameArmorId",
            "PaTorsoId",
            "PaHelmetId",
            "PaPackId",
            "SalvagedBodyId",
            "SalvagedHelmId",
            "SalvagedAgiEnchId",
            "SalvagedAgiMgefId",
            "ArrivalRefId",
            "CocRefId",
            "FrameFurnRefId",
            "ExitChairRefId",
        )
        for name in shared:
            m = re.search(rf"^int {name}\s*=\s*(0x[0-9A-Fa-f]+)", PSC_TEXT, re.M)
            self.assertIsNotNone(m, f"missing {name} in {PSC_PATH.name}")
            self.assertEqual(int(m.group(1), 16), cs_ids[name], f"FormID mismatch for {name}")

    def test_psc_has_zero_properties_and_zero_reserved_type_variable_names(self):
        self.assertTrue(PSC_TEXT.startswith("Scriptname FO4SF_PowerArmorCoreQuest extends Quest"))
        self.assertNotIn(" Property ", PSC_TEXT)
        self.assertIsNone(re.search(r"^\s*\w+(\[\])?\s+\w+\s+Auto\b", PSC_TEXT, re.M | re.I))

        reserved_types = {
            "race", "cell", "form", "actor", "quest", "furniture", "keyword", "spell",
            "game", "debug", "utility", "math", "objectreference", "scriptobject",
            "actorvalue", "int", "float", "string", "bool",
        }
        decls = re.findall(r"^\s*(?:[A-Za-z:]+(?:\[\])?)\s+(\w+)\s*(?:=|$)", PSC_TEXT, re.M)
        params = [
            p
            for sig in re.findall(r"(?:Function|Event)\s+[\w.]+\(([^)]*)\)", PSC_TEXT)
            for p in re.findall(r"\s(\w+)\s*(?:,|$)", " " + sig)
        ]
        bad = [n for n in decls + params if n.lower() in reserved_types]
        self.assertEqual(bad, [], f"Papyrus reserved type names used as identifiers: {bad}")

    def test_psc_implements_outfit_capture_drain_reload_and_salvaged_ncr(self):
        self.assertIn('RegisterForRemoteEvent(p, "OnItemUnequipped")', PSC_TEXT)
        self.assertIn('RegisterForRemoteEvent(p, "OnPlayerLoadGame")', PSC_TEXT)
        self.assertIn("Event Actor.OnPlayerLoadGame(Actor akSender)", PSC_TEXT)
        self.assertIn("Event Actor.OnItemUnequipped(Actor akSender, Form akBaseObject, ObjectReference akReference)", PSC_TEXT)
        self.assertIn("Event Actor.OnItemEquipped(Actor akSender, Form akBaseObject, ObjectReference akReference)", PSC_TEXT)
        self.assertIn("reload_sync", PSC_TEXT)
        self.assertIn("core_reload", PSC_TEXT)
        self.assertIn("core_depleted", PSC_TEXT)
        self.assertIn("salvaged_equip", PSC_TEXT)

    def test_pc_card_names_and_deletes_throwaway_save_and_public_surface_is_clean(self):
        doc_text = DOC_PATH.read_text(encoding="utf-8")
        self.assertGreaterEqual(doc_text.count("FO4SF_Throwaway_PowerArmor_DeleteMe"), 3)
        self.assertIn("Delete the throwaway save", doc_text)

        local_path_patterns = (
            r"\b[A-Za-z]:[\\/][A-Za-z0-9_.-]+",
            r"/(?:home|Users)/[A-Za-z0-9_.-]+",
        )
        checked_files = [
            CS_PATH,
            PSC_PATH,
            DOC_PATH,
            ROOT / "scripts" / "powerarmor" / "make_power_armor_core.py",
            ROOT / "scripts" / "powerarmor" / "power_armor_core_install.py",
            ROOT / "src" / "fo4sf" / "powerarmor" / "core_log.py",
        ]
        for fpath in checked_files:
            txt = fpath.read_text(encoding="utf-8")
            for pat in local_path_patterns:
                self.assertIsNone(
                    re.search(pat, txt),
                    f"machine-specific path pattern {pat!r} found in {fpath.name}",
                )


class StageFoldVerifyAndInstallTests(unittest.TestCase):
    def _make_synthetic_stage(self, root_dir):
        sf_path = os.path.join(root_dir, "Starfield.esm")
        with open(sf_path, "wb") as f:
            f.write(b"TES4-SYNTH-STARFIELD")
        cr_zip = os.path.join(root_dir, "ContentResources.zip")
        make_fake_content_resources(cr_zip)
        comp = make_fake_compiler(root_dir)
        stage_dir = os.path.join(root_dir, "stage-v1")

        def fake_dotnet_run(cmd, **kwargs):
            if "build" in cmd:
                out_idx = cmd.index("build") + 2
                out_d = cmd[out_idx]
                os.makedirs(out_d, exist_ok=True)
                with open(os.path.join(out_d, mpac.PLUGIN), "wb") as ef:
                    ef.write(b"TES4-FO4SFPOWERARMOR-SYNTH")
                return subprocess.CompletedProcess(cmd, 0, stdout="wrote synthetic FO4SFPowerArmor.esm\n", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="check ok\n", stderr="")

        from unittest import mock
        with mock.patch.object(mpac, "run", side_effect=fake_dotnet_run):
            rc = mpac.main([
                "stage",
                "--out", stage_dir,
                "--starfield", sf_path,
                "--compiler", comp,
                "--content-resources", cr_zip,
            ])
        self.assertEqual(rc, 0)
        return sf_path, cr_zip, stage_dir

    def test_precheck_passes_and_detects_missing_declarations(self):
        with tempfile.TemporaryDirectory() as td:
            good_zip = os.path.join(td, "good.zip")
            make_fake_content_resources(good_zip)
            out_json = os.path.join(td, "precheck.json")
            self.assertEqual(mpac.main(["precheck", "--content-resources", good_zip, "--out", out_json]), 0)
            rep = json.loads(Path(out_json).read_text(encoding="utf-8"))
            self.assertEqual(rep["missing"], [])

            bad_zip = os.path.join(td, "bad.zip")
            make_fake_content_resources(bad_zip, omit=("Actor.OnPlayerLoadGame",))
            self.assertEqual(mpac.main(["precheck", "--content-resources", bad_zip]), 1)

    def test_stage_verify_fold_hardlink_readme_safety_and_tamper_refusal(self):
        with tempfile.TemporaryDirectory() as td:
            sf_path, _, stage_dir = self._make_synthetic_stage(td)
            self.assertEqual(mpac.main(["verify", "--dir", stage_dir, "--starfield", sf_path]), 0)

            # Rogue ESM in stage must fail verify
            rogue = os.path.join(stage_dir, "Rogue.esm")
            Path(rogue).write_bytes(b"rogue")
            self.assertEqual(mpac.main(["verify", "--dir", stage_dir]), 1)
            os.remove(rogue)
            self.assertEqual(mpac.main(["verify", "--dir", stage_dir]), 0)

            # Build synthetic clean-core directory and verify --hardlink never mutates clean-core/README.txt
            core_dir = os.path.join(td, "clean-core")
            os.makedirs(os.path.join(core_dir, "Data", "Scripts"))
            Path(core_dir, "FO4TerrainCore.esm").write_bytes(b"CORE1")
            Path(core_dir, "FO4TerrainCore_Mars.esm").write_bytes(b"CORE2")
            core_readme_orig = (
                "Clean core set\n"
                "  scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> "
                "--plugins FO4TerrainCore.esm,FO4TerrainCore_Mars.esm --pack\n"
            )
            Path(core_dir, "README.txt").write_text(core_readme_orig, encoding="utf-8")

            folded_dir = os.path.join(td, "folded-v1")
            self.assertEqual(
                mpac.main(["fold", "--core-dir", core_dir, "--stage", stage_dir, "--out", folded_dir, "--hardlink", "--starfield", sf_path]),
                0,
            )
            self.assertEqual(Path(core_dir, "README.txt").read_text(encoding="utf-8"), core_readme_orig)
            folded_readme = Path(folded_dir, "README.txt").read_text(encoding="utf-8")
            self.assertIn("FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFPowerArmor.esm", folded_readme)
            self.assertEqual(mpac.main(["verify", "--dir", folded_dir, "--starfield", sf_path]), 0)

            # Re-folding into a prior folded set succeeds with --clean-prior
            folded_v2 = os.path.join(td, "folded-v2")
            self.assertEqual(
                mpac.main(["fold", "--core-dir", folded_dir, "--stage", stage_dir, "--out", folded_v2, "--hardlink", "--clean-prior"]),
                0,
            )
            self.assertEqual(mpac.main(["verify", "--dir", folded_v2, "--starfield", sf_path]), 0)

            # Tampering with folded PEX fails verify
            pex_target = Path(folded_v2, "Data", "Scripts", "FO4SF_PowerArmorCoreQuest.pex")
            os.unlink(pex_target)
            pex_target.write_bytes(b"TAMPERED-PEX")
            self.assertEqual(mpac.main(["verify", "--dir", folded_v2]), 1)

    def test_ride_along_installer_uses_isolated_record_name(self):
        self.assertEqual(paci.RECORD, "FO4SFPowerArmor.install.json")
        with tempfile.TemporaryDirectory() as td:
            sf_path, _, stage_dir = self._make_synthetic_stage(td)
            game_dir = os.path.join(td, "StarfieldGame")
            os.makedirs(os.path.join(game_dir, "Data"))
            shutil.copy2(sf_path, os.path.join(game_dir, "Data", "Starfield.esm"))
            exp_rec = Path(game_dir, "Data", "FO4SFExp.install.json")
            probe_rec = Path(game_dir, "Data", "FO4SFPowerArmorProbe.install.json")
            exp_rec.write_text('{"sentinel": "core"}', encoding="utf-8")
            probe_rec.write_text('{"sentinel": "probe"}', encoding="utf-8")

            seen = {}

            def fake_exp_main(argv):
                seen["record"] = paci.exp_install.RECORD
                seen["argv"] = argv
                return 0

            from unittest import mock
            with mock.patch.object(paci.exp_install, "main", side_effect=fake_exp_main):
                rc = paci.main(["install", "--dir", stage_dir, "--starfield", game_dir])
            self.assertEqual(rc, 0)
            self.assertEqual(seen["record"], "FO4SFPowerArmor.install.json")
            self.assertIn("--pack", seen["argv"])
            self.assertEqual(exp_rec.read_text(encoding="utf-8"), '{"sentinel": "core"}')
            self.assertEqual(probe_rec.read_text(encoding="utf-8"), '{"sentinel": "probe"}')


class CoreLogParserTests(unittest.TestCase):
    def test_full_session_with_save_quit_reload_reaches_pass_verdict(self):
        lines = [
            "[11/16/2026 - 05:00:01PM] FO4SFPACORE rt=10.0 init version=1 quest=150996997 installed=true parace=150996994 bptd=150996995 framefurn=150997026 core=150997001 salvaged=150997018 end=true",
            "FO4SFPACORE rt=14.0 captured_worn item=95565 count=1 end=true",
            "FO4SFPACORE rt=14.1 captured_worn item=95567 count=2 end=true",
            "FO4SFPACORE rt=14.2 climb_in cycle=0 trigger=onsit_frame race=150996994 orig_race=13437 equipped_pa=4 charge=100.0 limbs_min=100.0 inpa=1.0 end=true",
            "FO4SFPACORE rt=15.7 outfit_saved saved_worn=2 equipped_pa=4 end=true",
            "FO4SFPACORE rt=22.0 drain source=move charge=84.5 remaining_cores=1 slow_walk=false end=true",
            # Save -> Quit -> Reload: no OnInit, OnPlayerLoadGame emits reload_sync
            "FO4SFPACORE rt=4.2 reload_sync inpa=true pa_av=1.0 equipped_pa=4 charge=84.5 saved_worn=2 salvaged_worn=false limbs_min=100.0 race=150996994 end=true",
            "FO4SFPACORE rt=12.0 core_reload reason=move charge=100.0 remaining_cores=0 end=true",
            "FO4SFPACORE rt=29.0 core_depleted reason=move charge=0.0 remaining_cores=0 slow_walk=true end=true",
            "FO4SFPACORE rt=35.0 core_reload reason=pickup_reload charge=100.0 remaining_cores=0 end=true",
            "FO4SFPACORE rt=41.0 exit_complete cycle=0 trigger=onsit_exitchair restored_worn=2 equipped_pa=0 inpa=0.0 race=13437 frame_standing=true charge_kept=92.0 end=true",
            "FO4SFPACORE rt=48.0 salvaged_equip item=150997018 inpa=false pa_av=0.0 agi=4.0 charge=92.0 end=true",
            "FO4SFPACORE rt=49.0 truncated_line_without_end_marker",
        ]
        s = core_log.summarize(lines, papyrus=["[11/16/2026] unrelated line"])
        self.assertEqual(s["runs"], 1)
        self.assertEqual(s["cut"], 1)
        self.assertTrue(s["climb_in"]["ok"])
        self.assertTrue(s["fusion_core"]["ok"])
        self.assertTrue(s["reload_sync"]["ok"])
        self.assertTrue(s["exit_restore"]["ok"])
        self.assertTrue(s["salvaged_ncr"]["ok"])
        self.assertTrue(s["verdict"].startswith("PASS:"))
        rep = "\n".join(core_log.report(s))
        self.assertIn("quest form id 09000805", rep)

    def test_papyrus_error_blocks_pass_verdict(self):
        lines = [
            "FO4SFPACORE rt=1.0 init version=1 quest=150996997 installed=true end=true",
            "FO4SFPACORE rt=2.0 climb_in cycle=0 trigger=stage10 race=150996994 orig_race=13437 equipped_pa=4 charge=100.0 limbs_min=100.0 inpa=1.0 end=true",
            "FO4SFPACORE rt=3.0 drain source=move charge=90.0 remaining_cores=0 slow_walk=false end=true",
            "FO4SFPACORE rt=4.0 reload_sync inpa=true pa_av=1.0 equipped_pa=4 charge=90.0 saved_worn=1 limbs_min=100.0 end=true",
            "FO4SFPACORE rt=5.0 exit_complete cycle=0 trigger=stage30 restored_worn=1 equipped_pa=0 inpa=0.0 race=13437 frame_standing=true end=true",
            "FO4SFPACORE rt=6.0 salvaged_equip item=150997018 inpa=false pa_av=0.0 agi=4.0 end=true",
        ]
        s = core_log.summarize(lines, papyrus=["[ts] error: FO4SF_PowerArmorCoreQuest something failed"])
        self.assertEqual(len(s["papyrus"]), 1)
        self.assertTrue(s["verdict"].startswith("PARTIAL"))


@unittest.skipUnless(
    shutil.which("dotnet") and os.environ.get("FO4SF_DOTNET_TESTS"),
    "set FO4SF_DOTNET_TESTS=1 with dotnet installed to run C# Mutagen self-tests",
)
class PowerArmorCoreDotnetTests(unittest.TestCase):
    def test_dotnet_power_armor_core_selftest(self):
        with tempfile.TemporaryDirectory() as td:
            proj = str(ROOT / "dotnet" / "PowerArmorCore")
            r = subprocess.run(
                ["dotnet", "run", "-c", "Release", "--project", proj, "--", "selftest", td],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("selftest pass", r.stdout)


if __name__ == "__main__":
    unittest.main()
