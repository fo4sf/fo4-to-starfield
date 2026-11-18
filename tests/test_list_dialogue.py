"""Unit tests for CF-7 Silent-Player List Dialogue & Deterministic NV-Style Checks (1d)."""
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

from fo4sf.dialogue import list_checks, list_log  # noqa: E402

spec_mld = importlib.util.spec_from_file_location("make_list_dialogue", ROOT / "scripts" / "dialogue" / "make_list_dialogue.py")
mld = importlib.util.module_from_spec(spec_mld)
spec_mld.loader.exec_module(mld)

spec_ldi = importlib.util.spec_from_file_location("list_dialogue_install", ROOT / "scripts" / "dialogue" / "list_dialogue_install.py")
ldi = importlib.util.module_from_spec(spec_ldi)
spec_ldi.loader.exec_module(ldi)


PR792_OWNED_FILES = {
    "docs/dialogue/concord-four-option.md",
    "docs/dialogue/concord-talk-pc-card.md",
    "scripts/dialogue/concord_info_set.py",
    "scripts/dialogue/concord_talk_install.py",
    "scripts/dialogue/dialogue_menu_host.py",
    "scripts/dialogue/dialogue_menu_overlay.py",
    "scripts/dialogue/dialogue_menu_shuttle.py",
    "scripts/dialogue/make_concord_talk.py",
    "scripts/ui/DialogueMenuFour.as",
    "scripts/ui/Fo4sfDialogueSlots.as",
    "scripts/ui/make_dialogue_wheel_swf.py",
    "tests/test_concord_info_set.py",
    "tests/test_concord_talk_install.py",
    "tests/test_dialogue_menu_host.py",
    "tests/test_dialogue_menu_overlay.py",
    "tests/test_dialogue_menu_shuttle.py",
    "tests/test_dialogue_wheel_swf.py",
    "tests/test_fo4sf_dialogue_slots.py",
}

SAMPLE_PASS_LOG = [
    "FO4SFLIST rt=1.0 init speaker_present=True arrival_present=True end=true",
    "FO4SFLIST rt=2.0 eval phase=baseline_low speech=25.0 speech50=fail science=25.0 science40=fail strength=5.0 strength7=fail bg_vaultdweller=locked trait_goodnatured=locked end=true",
    "FO4SFLIST rt=3.0 choice_stage stage=21 tag=Speech_50 outcome=fail end=true",
    "FO4SFLIST rt=4.0 eval phase=qualified_high speech=55.0 speech50=pass science=45.0 science40=pass strength=8.0 strength7=pass bg_vaultdweller=pass trait_goodnatured=pass end=true",
    "FO4SFLIST rt=5.0 choice_stage stage=20 tag=Speech_50 outcome=pass end=true",
    "FO4SFLIST rt=5.5 choice_stage stage=40 tag=Vault_Dweller outcome=pass end=true",
    "FO4SFLIST rt=6.0 choice_stage stage=50 tag=Good_Natured outcome=pass end=true",
    "FO4SFLIST rt=7.0 eval phase=reset speech=25.0 speech50=fail science=25.0 science40=fail strength=5.0 strength7=fail bg_vaultdweller=locked trait_goodnatured=locked end=true",
    "FO4SFLIST rt=7.1 summary ok=true host_menu=DialogueMenu replaced_swf=false end=true",
]


def _build_synthetic_sources_zip(zip_path: Path) -> None:
    psc_map = {
        "Form.psc": "Scriptname Form extends ScriptObject Native\n",
        "ScriptObject.psc": (
            "Scriptname ScriptObject Native\n"
            "Function StartTimer(float afInterval, int aiTimerID = 0) native\n"
            "Function RegisterForRemoteEvent(ScriptObject akEventSource, string asEventName) native\n"
        ),
        "ObjectReference.psc": (
            "Scriptname ObjectReference extends Form Native\n"
            "float Function GetValue(ActorValue akAV) native\n"
            "Function SetValue(ActorValue akAV, float afValue) native\n"
            "Function ModValue(ActorValue akAV, float afAmount) native\n"
        ),
        "Actor.psc": (
            "Scriptname Actor extends ObjectReference Native\n"
            "Function AddPerk(Perk akPerk, bool abNotify = false) native\n"
            "Function RemovePerk(Perk akPerk) native\n"
            "bool Function HasPerk(Perk akPerk) native\n"
            "Event OnPlayerLoadGame()\nEndEvent\n"
        ),
        "Perk.psc": "Scriptname Perk extends Form Native\n",
        "ActorValue.psc": "Scriptname ActorValue extends Form Native\n",
        "GlobalVariable.psc": "Scriptname GlobalVariable extends Form Native\nfloat Function GetValue() native\n",
        "Game.psc": "Scriptname Game Native\nActor Function GetPlayer() native global\n",
        "Debug.psc": (
            "Scriptname Debug Native\n"
            "bool Function OpenUserLog(string asLogName) native global\n"
            "bool Function TraceUser(string asUserLog, string asTextToPrint, int aiSeverity = 0) native global\n"
        ),
        "Utility.psc": "Scriptname Utility Native\nfloat Function GetCurrentRealTime() native global\n",
        "Quest.psc": "Scriptname Quest extends Form Native\nbool Function GetStageDone(int aiStage) native\n",
    }
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("Scripts/Source/Starfield_Papyrus_Flags.flg", "")
        for name, body in psc_map.items():
            z.writestr(f"Scripts/Source/{name}", body)


class PrefixTagsAndDeterministicChecksTests(unittest.TestCase):
    def test_format_and_parse_all_four_tag_families(self):
        self.assertEqual(list_checks.format_prefix_tag("skill", "Speech", 50), "[Speech 50]")
        self.assertEqual(list_checks.format_prefix_tag("special", "Strength", 7), "[Strength 7]")
        self.assertEqual(list_checks.format_prefix_tag("background", "Vault Dweller"), "[Vault Dweller]")
        self.assertEqual(list_checks.format_prefix_tag("trait", "Good Natured"), "[Good Natured]")

        p1 = list_checks.parse_prefix_tag("[Speech 50] Present clearance.", {"Vault Dweller"}, {"Good Natured"})
        self.assertEqual(p1, {"kind": "skill", "label": "Speech", "threshold": 50, "body": "Present clearance."})
        p2 = list_checks.parse_prefix_tag("[Strength 7] Force latch.", {"Vault Dweller"}, {"Good Natured"})
        self.assertEqual(p2, {"kind": "special", "label": "Strength", "threshold": 7, "body": "Force latch."})
        p3 = list_checks.parse_prefix_tag("[Vault Dweller] Cite seal.", {"Vault Dweller"}, {"Good Natured"})
        self.assertEqual(p3["kind"], "background")
        p4 = list_checks.parse_prefix_tag("[Good Natured] Share meds.", {"Vault Dweller"}, {"Good Natured"})
        self.assertEqual(p4["kind"], "trait")

        with self.assertRaises(list_checks.ListDialogueError):
            list_checks.format_prefix_tag("skill", "NotASkill", 50)
        with self.assertRaises(list_checks.ListDialogueError):
            list_checks.format_prefix_tag("background", "Vault Dweller", 10)

    def test_deterministic_nv_shuttle_filtering(self):
        opts = [
            {"entry_id": 1, "kind": "skill", "label": "Speech", "threshold": 50, "variant": "pass", "text": "Pass line"},
            {"entry_id": 2, "kind": "skill", "label": "Speech", "threshold": 50, "variant": "fail", "text": "Fail line"},
            {"entry_id": 3, "kind": "special", "label": "Strength", "threshold": 7, "variant": "pass", "text": "Force"},
            {"entry_id": 4, "kind": "background", "label": "Vault Dweller", "variant": "only", "text": "BG line"},
            {"entry_id": 5, "kind": "trait", "label": "Good Natured", "variant": "only", "text": "Trait line"},
            {"entry_id": 6, "kind": "plain", "label": "", "variant": "only", "text": "Goodbye"},
        ]
        low = list_checks.build_shuttle_choices(opts, skills={"Speech": 49}, special={"Strength": 6})
        low_rows = low["DialogueListData"]["aChoices"]
        self.assertEqual([r["uEntryID"] for r in low_rows], [2, 6])
        self.assertEqual(low_rows[0]["sChoiceText"], "[Speech 50] Fail line")
        self.assertFalse(low_rows[0]["checkPassed"])

        high = list_checks.build_shuttle_choices(
            opts,
            skills={"Speech": 50},
            special={"Strength": 7},
            backgrounds={"Vault Dweller"},
            traits={"Good Natured"},
        )
        high_rows = high["DialogueListData"]["aChoices"]
        self.assertEqual([r["uEntryID"] for r in high_rows], [1, 3, 4, 5, 6])
        self.assertTrue(all(r["checkPassed"] for r in high_rows))

    def test_coexistence_mode_router_and_host_movie_refusal(self):
        self.assertEqual(
            list_checks.select_dialogue_mode(["ONE", "TWO", "THREE", "FOUR"], is_fo4_wheel_scene=True),
            "wheel_4",
        )
        self.assertEqual(
            list_checks.select_dialogue_mode(["[Speech 50] ONE", "TWO", "THREE", "FOUR"], is_fo4_wheel_scene=True),
            "list_host",
        )
        self.assertEqual(
            list_checks.select_dialogue_mode(["A", "B", "C", "D", "E"], is_fo4_wheel_scene=True),
            "list_host",
        )
        with self.assertRaises(list_checks.ListDialogueError):
            list_checks.validate_no_host_movie_override(["Data/Interface/DialogueMenu.swf"])

    def test_known_bug_ledger_validator(self):
        valid = list_checks.validate_bug_ledger([
            {
                "bug_id": "DLG-SUBJECT-VS-PLAYER-CTDA",
                "summary": "Skill condition evaluated NPC subject instead of player reference.",
                "disposition": "fixed",
                "reproduction": "Run stage 10 then stage 15 and observe Speech 50 branch switch.",
            }
        ])
        self.assertEqual(len(valid), 1)
        with self.assertRaises(list_checks.ListDialogueError):
            list_checks.validate_bug_ledger([
                {
                    "bug_id": "BAD-MOD-REF",
                    "summary": "Copied fix from PatchMod.esp",
                    "disposition": "studied_clean_room",
                    "reproduction": "Open dialogue",
                }
            ])


class NonCollisionAndPropertyParityTests(unittest.TestCase):
    def test_csharp_and_psc_property_order_match(self):
        cs = (ROOT / "dotnet" / "ListDialogue" / "Program.cs").read_text(encoding="utf-8")
        m = re.search(r"PropNames\s*=\s*\{([^}]*)\}", cs, re.S)
        self.assertIsNotNone(m)
        cs_props = re.findall(r'"(\w+)"', m.group(1))

        psc = (ROOT / "scripts" / "dialogue" / "FO4SF_ListDialogueQuest.psc").read_text(encoding="utf-8")
        psc_props = [pm.group(1) for pm in re.finditer(r"^\s*\w+\s+Property\s+(\w+)\s+Auto\s+Const\b", psc, re.M)]
        self.assertEqual(cs_props, psc_props)
        self.assertEqual(len(cs_props), 9)
        self.assertIn("TestModeGlobal", psc_props)
        self.assertIn("TestModeGlobal == None || TestModeGlobal.GetValue() == 0.0", psc)

    def test_shared_core_values_and_progression_masters_contract(self):
        self.assertEqual(
            list_checks.PLUGIN_MASTERS,
            ("Starfield.esm", "FO4SFCoreValues.esm", "FO4SFProgression.esm"),
        )
        self.assertEqual(list_checks.SHARED_CORE_FORM_IDS, {
            "SpeechAV": 0x00082A,
            "ScienceAV": 0x000828,
            "StrengthAV": 0x000810,
            "IntelligenceAV": 0x000814,
            "TestModeGlobal": 0x000860,
        })
        self.assertEqual(list_checks.PROGRESSION_PERK_FORM_IDS, {
            "FO4SF_BG_VaultDweller": 0x000820,
            "FO4SF_Trait_GoodNatured": 0x000836,
        })

    def test_zero_overlap_with_pr792_files_and_separate_install_record(self):
        self.assertEqual(ldi.RECORD, "FO4SFListDialogue.install.json")
        our_files = {
            "dotnet/ListDialogue/ListDialogue.csproj",
            "dotnet/ListDialogue/Program.cs",
            "src/fo4sf/dialogue/__init__.py",
            "src/fo4sf/dialogue/list_checks.py",
            "src/fo4sf/dialogue/list_log.py",
            "scripts/dialogue/FO4SF_ListDialogueQuest.psc",
            "scripts/dialogue/make_list_dialogue.py",
            "scripts/dialogue/list_dialogue_install.py",
            "docs/dialogue/list-skill-checks.md",
            "tests/test_list_dialogue.py",
        }
        self.assertEqual(our_files & PR792_OWNED_FILES, set())


class LogAndStageVerifyTests(unittest.TestCase):
    def test_log_summary_pass_and_fail(self):
        s = list_log.summarize(SAMPLE_PASS_LOG)
        self.assertTrue(s["passed"], s["checks"])
        self.assertEqual(s["choice_stages"], [21, 20, 40, 50])
        bad = [l.replace("speech50=pass", "speech50=fail") for l in SAMPLE_PASS_LOG]
        self.assertFalse(list_log.summarize(bad)["passed"])

    def test_precheck_fold_and_verify_refuses_host_movie(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            cr = t / "ContentResources.zip"
            _build_synthetic_sources_zip(cr)
            self.assertEqual(mld.main(["precheck", "--content-resources", str(cr)]), 0)

            sf = t / "Starfield.esm"
            sf.write_bytes(b"TES4synth_sf")
            sf_sha = hashlib.sha256(sf.read_bytes()).hexdigest()

            stage_dir = t / "stage"
            (stage_dir / "Data" / "Scripts").mkdir(parents=True)
            (stage_dir / "FO4SFListDialogue.esm").write_bytes(b"TES4list_esm")
            (stage_dir / "Data" / "Scripts" / "FO4SF_ListDialogueQuest.pex").write_bytes(b"PEXlist")
            (stage_dir / "README.txt").write_text("List dialogue stage\n", encoding="utf-8")
            outputs = mld.stage_files(str(stage_dir))
            plan = {
                "kind": "list-dialogue",
                "version": 1,
                "plugin": "FO4SFListDialogue.esm",
                "plugin_sha256": outputs["FO4SFListDialogue.esm"],
                "plugins": ["FO4SFListDialogue.esm"],
                "scripts": {"FO4SF_ListDialogueQuest": outputs["Data/Scripts/FO4SF_ListDialogueQuest.pex"]},
                "outputs": outputs,
                "inputs": {"Starfield.esm": {"sha256": sf_sha}},
                "replaces_host_movie": False,
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
                mld.main(["fold", "--stage", str(stage_dir), "--core-dir", str(core_dir), "--out", str(folded), "--starfield", str(sf)]),
                0,
            )
            self.assertEqual(
                mld.main(["verify", "--exp-dir", str(folded), "--plan", str(stage_dir / "plan.json"), "--starfield", str(sf)]),
                0,
            )
            self.assertEqual(
                mld.main(["verify", "--exp-dir", str(folded), "--plan", str(stage_dir / "plan.json"), "--no-test-cell"]),
                1,
            )

            # Injecting forbidden Interface/DialogueMenu.swf must fail verify!
            (folded / "Data" / "Interface").mkdir(parents=True)
            (folded / "Data" / "Interface" / "DialogueMenu.swf").write_bytes(b"FWS")
            self.assertEqual(
                mld.main(["verify", "--exp-dir", str(folded), "--plan", str(stage_dir / "plan.json"), "--starfield", str(sf)]),
                1,
            )

    @unittest.skipUnless(os.environ.get("FO4SF_DOTNET_TESTS") == "1", "set FO4SF_DOTNET_TESTS=1 to run ListDialogue selftest")
    def test_dotnet_list_dialogue_selftest(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = subprocess.run(
                ["dotnet", "run", "-c", "Release", "--project", str(ROOT / "dotnet" / "ListDialogue"), "--", "selftest", tmp],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(res.returncode, 0, res.stdout + "\n" + res.stderr)
            self.assertIn("selftest: ok", res.stdout)


if __name__ == "__main__":
    unittest.main()
