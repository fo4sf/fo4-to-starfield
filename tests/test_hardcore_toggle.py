"""Unit tests for the CF-8 Hardcore & Survival GPOF toggle (FO4SFHardcore.esm)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from fo4sf.survival import hardcore_log  # noqa: E402

spec_mh = importlib.util.spec_from_file_location("make_hardcore", ROOT / "scripts" / "survival" / "make_hardcore.py")
mh = importlib.util.module_from_spec(spec_mh)
spec_mh.loader.exec_module(mh)

spec_hi = importlib.util.spec_from_file_location("hardcore_install", ROOT / "scripts" / "survival" / "hardcore_install.py")
hi = importlib.util.module_from_spec(spec_hi)
spec_hi.loader.exec_module(hi)


SAMPLE_PASS_LOG = [
    "FO4SFHC rt=10.0 sync reason=init hardcore=0 h=0.0 hs=0 t=0.0 ts=0 s=0.0 ss=0 ammo_burden=0.0 carry_mod=0.0 end_mod=0.0 str_mod=0.0 agi_mod=0.0 int_mod=0.0 ft_blocked=0 sq_env_running=False end=true",
    "FO4SFHC rt=12.0 sync reason=stage10_on hardcore=1 h=450.0 hs=2 t=650.0 ts=3 s=250.0 ss=1 ammo_burden=5.0 carry_mod=-5.0 end_mod=-5.0 str_mod=0.0 agi_mod=-1.0 int_mod=-1.0 ft_blocked=1 sq_env_running=False end=true",
    "FO4SFHC rt=12.1 stimpak source=stage10_hot mode=hot heal_tick=10.0 ticks_remaining=5 hp_before=60.0 hp_now=70.0 end=true",
    "FO4SFHC rt=12.2 stage id=10 ok=true hardcore=1 sq_env_running=False end=true",
    "FO4SFHC rt=14.0 sync reason=stage20_relief hardcore=1 h=200.0 hs=1 t=400.0 ts=2 s=0.0 ss=0 ammo_burden=5.0 carry_mod=-5.0 end_mod=-3.0 str_mod=0.0 agi_mod=0.0 int_mod=0.0 ft_blocked=1 sq_env_running=False end=true",
    "FO4SFHC rt=14.1 stage id=20 ok=true h=200.0 t=400.0 s=0.0 end=true",
    "FO4SFHC rt=16.0 sync reason=stage30_off hardcore=0 h=200.0 hs=0 t=400.0 ts=0 s=0.0 ss=0 ammo_burden=0.0 carry_mod=0.0 end_mod=0.0 str_mod=0.0 agi_mod=0.0 int_mod=0.0 ft_blocked=0 sq_env_running=False end=true",
    "FO4SFHC rt=16.1 stage id=30 ok=true hardcore=0 ammo_burden=0.0 carry_mod=0.0 end_mod=0.0 sq_env_running=False end=true",
    "FO4SFHC rt=18.0 stimpak source=stage40_instant mode=instant heal_instant=60.0 ticks_remaining=0 hp_before=60.0 hp_now=100.0 end=true",
    "FO4SFHC rt=18.1 stage id=40 ok=true hardcore=0 end=true",
    "FO4SFHC rt=20.0 sync reason=stage50_reset hardcore=0 h=0.0 hs=0 t=0.0 ts=0 s=0.0 ss=0 ammo_burden=0.0 carry_mod=0.0 end_mod=0.0 str_mod=0.0 agi_mod=0.0 int_mod=0.0 ft_blocked=0 sq_env_running=False end=true",
    "FO4SFHC rt=20.05 stage id=50 ok=true hardcore=0 end=true",
    "FO4SFHC rt=20.1 summary ok=true stages=10,20,30,40,50 sq_env_running=False end=true",
]


def _build_synthetic_sources_zip(zip_path: Path) -> None:
    psc_map = {
        "Form.psc": "Scriptname Form extends ScriptObject Native\n",
        "ScriptObject.psc": (
            "Scriptname ScriptObject Native\n"
            "Function StartTimer(float afInterval, int aiTimerID = 0) native\n"
            "Function CancelTimer(int aiTimerID = 0) native\n"
            "Function RegisterForRemoteEvent(ScriptObject akEventSource, string asEventName) native\n"
            "Function AddInventoryEventFilter(Form akFilter) native\n"
            "Function RemoveAllInventoryEventFilters() native\n"
            "Function RegisterForGameplayOptionChangedEvent() native\n"
            "Event OnGameplayOptionChanged(GameplayOption[] aChangedOptions)\nEndEvent\n"
            "Function RegisterForPlayerSleep() native\n"
            "Event OnPlayerSleepStart(float afStart, float afEnd, ObjectReference akBed)\nEndEvent\n"
            "Event OnPlayerSleepStop(bool abInterrupted, ObjectReference akBed)\nEndEvent\n"
        ),
        "ObjectReference.psc": (
            "Scriptname ObjectReference extends Form Native\n"
            "Function ModValue(ActorValue akAV, float afAmount) native\n"
            "Function DamageValue(ActorValue akAV, float afDamage) native\n"
            "Function RestoreValue(ActorValue akAV, float afAmount) native\n"
            "float Function GetValue(ActorValue akAV) native\n"
            "Function SetValue(ActorValue akAV, float afValue) native\n"
            "Function AddItem(Form akItemToAdd, int aiCount = 1, bool abSilent = false) native\n"
            "Function RemoveItem(Form akItemToRemove, int aiCount = 1, bool abSilent = false, ObjectReference akOtherContainer = None) native\n"
            "int Function GetItemCount(Form akItem) native\n"
            "Event OnItemAdded(Form akBaseItem, int aiItemCount, ObjectReference akItemReference, ObjectReference akSourceContainer, int aiTransferReason)\nEndEvent\n"
            "Event OnItemRemoved(Form akBaseItem, int aiItemCount, ObjectReference akItemReference, ObjectReference akDestContainer, int aiTransferReason)\nEndEvent\n"
        ),
        "Actor.psc": (
            "Scriptname Actor extends ObjectReference Native\n"
            "Event OnItemEquipped(Form akBaseObject, ObjectReference akReference)\nEndEvent\n"
            "Event OnPlayerLoadGame()\nEndEvent\n"
        ),
        "GlobalVariable.psc": (
            "Scriptname GlobalVariable extends Form Native\n"
            "float Function GetValue() native\n"
            "Function SetValue(float afNewValue) native\n"
        ),
        "GameplayOption.psc": (
            "Scriptname GameplayOption extends Form Native\n"
            "float Function GetValue() native\n"
            "Function NotifyGameplayOptionUpdateFinished() native global\n"
        ),
        "FormList.psc": (
            "Scriptname FormList extends Form Native\n"
            "int Function GetSize() native\n"
            "Form Function GetAt(int aiIndex) native\n"
        ),
        "Game.psc": (
            "Scriptname Game Native\n"
            "Actor Function GetPlayer() native global\n"
            "Form Function GetFormFromFile(int aiFormID, string asFilename) native global\n"
        ),
        "Debug.psc": (
            "Scriptname Debug Native\n"
            "bool Function OpenUserLog(string asLogName) native global\n"
            "bool Function TraceUser(string asUserLog, string asTextToPrint, int aiSeverity = 0) native global\n"
        ),
        "Utility.psc": (
            "Scriptname Utility Native\n"
            "float Function GetCurrentRealTime() native global\n"
            "float Function GetCurrentGameTime() native global\n"
        ),
        "Quest.psc": (
            "Scriptname Quest extends Form Native\n"
            "bool Function GetStageDone(int aiStage) native\n"
            "bool Function IsRunning() native\n"
        ),
    }
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("Scripts/Source/Starfield_Papyrus_Flags.flg", "")
        for name, body in psc_map.items():
            z.writestr(f"Scripts/Source/{name}", body)


class PropertyParityTests(unittest.TestCase):
    def test_csharp_and_psc_property_order_match_exactly(self):
        cs = (ROOT / "dotnet" / "HardcoreToggle" / "Program.cs").read_text(encoding="utf-8")
        m = re.search(r"PropNames\s*=\s*\{([^}]*)\}", cs, re.S)
        self.assertIsNotNone(m)
        cs_props = re.findall(r'"(\w+)"', m.group(1))

        psc = (ROOT / "scripts" / "survival" / "FO4SF_HardcoreQuest.psc").read_text(encoding="utf-8")
        psc_props = [
            pm.group(1)
            for pm in re.finditer(r"^\s*\w+\s+Property\s+(\w+)\s+Auto\s+Const\b", psc, re.M)
        ]
        self.assertEqual(cs_props, psc_props)
        self.assertEqual(len(cs_props), 23)


class HardcoreLogTests(unittest.TestCase):
    def test_pass_log_summary(self):
        s = hardcore_log.summarize(SAMPLE_PASS_LOG)
        self.assertTrue(s["passed"], s["checks"])
        self.assertIn("verdict: PASS", "\n".join(hardcore_log.report(s)))

    def test_sq_env_conflict_fails_verdict(self):
        bad = [l.replace("sq_env_running=False", "sq_env_running=True") for l in SAMPLE_PASS_LOG]
        s = hardcore_log.summarize(bad)
        self.assertFalse(s["passed"])
        self.assertFalse(s["checks"]["sq_env_never_conflicted"])

    def test_unreverted_carry_mod_fails_verdict(self):
        bad = [l.replace("reason=stage30_off hardcore=0 h=200.0 hs=0 t=400.0 ts=0 s=0.0 ss=0 ammo_burden=0.0 carry_mod=0.0",
                         "reason=stage30_off hardcore=0 h=200.0 hs=0 t=400.0 ts=0 s=0.0 ss=0 ammo_burden=5.0 carry_mod=-5.0")
               for l in SAMPLE_PASS_LOG]
        s = hardcore_log.summarize(bad)
        self.assertFalse(s["passed"])
        self.assertFalse(s["checks"]["stage30_off_reverted_cleanly"])

    def test_instant_stimpak_during_hardcore_fails_verdict(self):
        bad = [l for l in SAMPLE_PASS_LOG if "mode=hot" not in l]
        s = hardcore_log.summarize(bad)
        self.assertFalse(s["passed"])
        self.assertFalse(s["checks"]["stimpak_hot_when_on"])


class StageFoldVerifyTests(unittest.TestCase):
    def test_precheck_and_fold_and_verify_synthetic(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            cr = t / "ContentResources.zip"
            _build_synthetic_sources_zip(cr)
            self.assertEqual(mh.main(["precheck", "--content-resources", str(cr)]), 0)

            # Build synthetic stage directory to test fold + verify + identical/conflicting pex handling
            sf = t / "Starfield.esm"
            sf.write_bytes(b"TES4synthetic_starfield")
            sf_sha = hashlib.sha256(sf.read_bytes()).hexdigest()

            stage_dir = t / "stage"
            (stage_dir / "Data" / "Scripts").mkdir(parents=True)
            esm_bytes = b"TES4synthetic_hardcore_esm"
            pex_bytes = b"PEXsynthetic_hardcore_pex"
            (stage_dir / "FO4SFHardcore.esm").write_bytes(esm_bytes)
            (stage_dir / "Data" / "Scripts" / "FO4SF_HardcoreQuest.pex").write_bytes(pex_bytes)
            (stage_dir / "README.txt").write_text("Hardcore stage readme\n", encoding="utf-8")
            outputs = mh.stage_files(str(stage_dir))
            plan = {
                "kind": "hardcore-toggle",
                "version": 1,
                "plugin": "FO4SFHardcore.esm",
                "plugin_sha256": outputs["FO4SFHardcore.esm"],
                "plugins": ["FO4SFHardcore.esm"],
                "scripts": {"FO4SF_HardcoreQuest": outputs["Data/Scripts/FO4SF_HardcoreQuest.pex"]},
                "outputs": outputs,
                "inputs": {"Starfield.esm": {"sha256": sf_sha}},
            }
            (stage_dir / "plan.json").write_text(json.dumps(plan), encoding="utf-8")

            core_dir = t / "clean-core"
            (core_dir / "Data" / "Scripts").mkdir(parents=True)
            (core_dir / "FO4TerrainCore.esm").write_bytes(b"TES4core")
            (core_dir / "README.txt").write_text(
                "Core\nscripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> --plugins FO4TerrainCore.esm --pack\n",
                encoding="utf-8",
            )

            folded = t / "folded"
            self.assertEqual(
                mh.main(["fold", "--stage", str(stage_dir), "--core-dir", str(core_dir), "--out", str(folded), "--starfield", str(sf), "--hardlink"]),
                0,
            )
            self.assertEqual(
                mh.main(["verify", "--exp-dir", str(folded), "--plan", str(stage_dir / "plan.json"), "--starfield", str(sf)]),
                0,
            )
            self.assertIn("FO4TerrainCore.esm,FO4SFHardcore.esm", (folded / "README.txt").read_text(encoding="utf-8"))

            # Identical .pex already in core is accepted; different .pex is refused
            (core_dir / "Data" / "Scripts" / "FO4SF_HardcoreQuest.pex").write_bytes(pex_bytes)
            folded_same = t / "folded_same"
            self.assertEqual(
                mh.main(["fold", "--stage", str(stage_dir), "--core-dir", str(core_dir), "--out", str(folded_same)]),
                0,
            )

            (core_dir / "Data" / "Scripts" / "FO4SF_HardcoreQuest.pex").write_bytes(b"DIFFERENT_PEX")
            with self.assertRaises(SystemExit):
                mh.main(["fold", "--stage", str(stage_dir), "--core-dir", str(core_dir), "--out", str(t / "folded_bad")])

    def test_ride_along_installer_record_name(self):
        self.assertEqual(hi.RECORD, "FO4SFHardcore.install.json")

    @unittest.skipUnless(os.environ.get("FO4SF_DOTNET_TESTS") == "1", "set FO4SF_DOTNET_TESTS=1 to run dotnet HardcoreToggle selftest")
    def test_dotnet_hardcore_toggle_selftest(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = subprocess.run(
                ["dotnet", "run", "-c", "Release", "--project", str(ROOT / "dotnet" / "HardcoreToggle"), "--", "selftest", tmp],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(res.returncode, 0, res.stdout + "\n" + res.stderr)
            self.assertIn("selftest: ok", res.stdout)


if __name__ == "__main__":
    unittest.main()
