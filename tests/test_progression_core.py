"""Unit tests for CF-6 Player Creation & Progression Core (2e)."""
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

from fo4sf.progression import core_log, tables  # noqa: E402

spec_mp = importlib.util.spec_from_file_location("make_progression", ROOT / "scripts" / "progression" / "make_progression.py")
mp = importlib.util.module_from_spec(spec_mp)
spec_mp.loader.exec_module(mp)

spec_pi = importlib.util.spec_from_file_location("progression_install", ROOT / "scripts" / "progression" / "progression_install.py")
pi = importlib.util.module_from_spec(spec_pi)
spec_pi.loader.exec_module(pi)


SAMPLE_PASS_LOG = [
    "FO4SFPROG rt=1.0 init pool28=0 cadence=2 respec_used=0 end=true",
    "FO4SFPROG rt=2.0 creation ok=True bg=Vault_Dweller traits=2 special_sum=40 skills_count=13 speech=47 science=34 medicine=34 carry_mod=45.0 end=true",
    "FO4SFPROG rt=3.0 respec first_ok=True second_refused=True active_traits=1 end=true",
    "FO4SFPROG rt=4.0 cadence cad2_lvl2=True cad2_lvl3=False cad2_lvl4=True cad1_lvl3=True end=true",
    "FO4SFPROG rt=5.0 karma_repu karma=-800.0 karma_tier=Very_Evil faction=Minutemen fame=85.0 infamy=0.0 repu_title=Idolized disposition=Ally end=true",
    "FO4SFPROG rt=6.0 summary ok=true stages=10,20,30,40,50 end=true",
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
            "int Function GetLevel() native\n"
            "Function AddPerk(Perk akPerk, bool abNotify = false) native\n"
            "Function RemovePerk(Perk akPerk) native\n"
            "bool Function HasPerk(Perk akPerk) native\n"
            "Event OnPlayerLoadGame()\nEndEvent\n"
        ),
        "Faction.psc": (
            "Scriptname Faction extends Form Native\n"
            "Function SetAlly(Faction akOther, bool abSelfIsFriend = false, bool abOtherIsFriend = false) native\n"
            "Function SetEnemy(Faction akOther, bool abSelfIsNeutral = false, bool abOtherIsNeutral = false) native\n"
        ),
        "FormList.psc": (
            "Scriptname FormList extends Form Native\n"
            "int Function GetSize() native\n"
            "Form Function GetAt(int aiIndex) native\n"
        ),
        "GlobalVariable.psc": (
            "Scriptname GlobalVariable extends Form Native\n"
            "float Function GetValue() native\n"
            "Function SetValue(float afVal) native\n"
        ),
        "Game.psc": (
            "Scriptname Game Native\n"
            "Actor Function GetPlayer() native global\n"
            "Form Function GetFormFromFile(int aiFormID, string asFile) native global\n"
        ),
        "Debug.psc": (
            "Scriptname Debug Native\n"
            "bool Function OpenUserLog(string asLogName) native global\n"
            "bool Function TraceUser(string asUserLog, string asText, int aiSev = 0) native global\n"
        ),
        "Utility.psc": "Scriptname Utility Native\nfloat Function GetCurrentRealTime() native global\n",
        "Quest.psc": "Scriptname Quest extends Form Native\nbool Function GetStageDone(int aiStage) native\n",
    }
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("Scripts/Source/Starfield_Papyrus_Flags.flg", "")
        for name, body in psc_map.items():
            z.writestr(f"Scripts/Source/{name}", body)


class DataTablesAndMathTests(unittest.TestCase):
    def test_table_counts_and_unique_formids(self):
        self.assertEqual(len(tables.SPECIAL_TABLE), 7)
        self.assertEqual(len(tables.SKILLS_TABLE), 13)
        self.assertEqual(len(tables.BACKGROUNDS_TABLE), 9)
        self.assertEqual(len(tables.TRAITS_TABLE), 9)
        self.assertEqual(len(tables.PERKS_TABLE), 8)
        self.assertEqual(len(tables.REPU_FACTIONS_TABLE), 6)

        ids = (
            [r["id"] for r in tables.SPECIAL_TABLE]
            + [r["id"] for r in tables.SKILLS_TABLE]
            + [r["id"] for r in tables.BACKGROUNDS_TABLE]
            + [r["id"] for r in tables.TRAITS_TABLE]
            + [r["id"] for r in tables.PERKS_TABLE]
            + [r["fame_id"] for r in tables.REPU_FACTIONS_TABLE]
            + [r["infamy_id"] for r in tables.REPU_FACTIONS_TABLE]
        )
        self.assertEqual(len(ids), len(set(ids)), "every table FormID must be unique")

    def test_special_40_pool_default_and_28_glob_option(self):
        alloc40 = {"STR": 6, "PER": 6, "END": 6, "CHA": 6, "INT": 6, "AGI": 5, "LCK": 5}
        self.assertEqual(sum(tables.validate_special_allocation(alloc40).values()), 40)
        with self.assertRaises(tables.ProgressionError):
            tables.validate_special_allocation(alloc40, use_fo4_pool_28=True)

        alloc28 = {"STR": 4, "PER": 4, "END": 4, "CHA": 4, "INT": 4, "AGI": 4, "LCK": 4}
        self.assertEqual(sum(tables.validate_special_allocation(alloc28, use_fo4_pool_28=True).values()), 28)
        with self.assertRaises(tables.ProgressionError):
            tables.validate_special_allocation(alloc28, use_fo4_pool_28=False)

    def test_nv_13_skill_formula_background_tags_and_traits(self):
        alloc40 = {"STR": 6, "PER": 5, "END": 5, "CHA": 6, "INT": 7, "AGI": 6, "LCK": 5}
        skills = tables.compute_initial_skills(
            alloc40,
            background_name="Vault Dweller",
            tag_skills=["Speech", "Guns", "Lockpick"],
            traits=["Good Natured", "Small Frame"],
        )
        self.assertEqual(len(skills), 13)
        self.assertEqual(skills["Speech"], 47)
        self.assertEqual(skills["Guns"], 29)

        with self.assertRaises(tables.ProgressionError):
            tables.compute_initial_skills(
                alloc40,
                background_name="Vault Dweller",
                tag_skills=["Speech", "Guns", "Lockpick"],
                traits=["Good Natured", "Small Frame", "Skilled"],
            )

    def test_exit_trait_respec_allowed_once_then_locked(self):
        updated, used = tables.apply_exit_trait_respec(["Small Frame", "Kamikaze"], ["Trigger Discipline"], respec_used=False)
        self.assertEqual(updated, ["Trigger Discipline"])
        self.assertTrue(used)
        with self.assertRaises(tables.ProgressionError):
            tables.apply_exit_trait_respec(updated, [], respec_used=used)

    def test_glob_driven_perk_cadence_has_no_fixed_assumption(self):
        self.assertEqual([tables.grants_perk_at_level(lv, 2) for lv in (1, 2, 3, 4, 5, 6)], [False, True, False, True, False, True])
        self.assertEqual([tables.grants_perk_at_level(lv, 1) for lv in (1, 2, 3, 4)], [False, True, True, True])
        self.assertEqual([tables.grants_perk_at_level(lv, 3) for lv in (1, 2, 3, 4, 5, 6)], [False, False, True, False, False, True])

    def test_decoupled_karma_and_repu_16_state_matrix(self):
        self.assertEqual(tables.karma_tier(-850), "Very Evil")
        r_ally = tables.evaluate_faction_repu(85.0, 0.0)
        self.assertEqual(r_ally["title"], "Idolized")
        self.assertEqual(r_ally["disposition"], "Ally")
        self.assertLess(r_ally["vendor_price_mult"], 1.0)

        self.assertEqual(tables.karma_tier(900), "Very Good")
        r_enemy = tables.evaluate_faction_repu(0.0, 90.0)
        self.assertEqual(r_enemy["title"], "Vilified")
        self.assertEqual(r_enemy["disposition"], "Enemy")
        self.assertEqual(tables.evaluate_faction_repu(80.0, 80.0)["title"], "Wild Child")


class PluginParityAndStageTests(unittest.TestCase):
    def test_csharp_psc_and_python_tables_match_1_to_1(self):
        cs = (ROOT / "dotnet" / "ProgressionCore" / "Program.cs").read_text(encoding="utf-8")
        for row in (*tables.SPECIAL_TABLE, *tables.SKILLS_TABLE, *tables.BACKGROUNDS_TABLE, *tables.TRAITS_TABLE, *tables.PERKS_TABLE):
            self.assertIn(f'(0x{row["id"]:X}, "{row["edid"]}"', cs)

        m = re.search(r"PropNames\s*=\s*\{([^}]*)\}", cs, re.S)
        self.assertIsNotNone(m)
        cs_props = re.findall(r'"(\w+)"', m.group(1))
        psc = (ROOT / "scripts" / "progression" / "FO4SF_ProgressionQuest.psc").read_text(encoding="utf-8")
        psc_props = [pm.group(1) for pm in re.finditer(r"^\s*\w+\s+Property\s+(\w+)\s+Auto\s+Const\b", psc, re.M)]
        self.assertEqual(cs_props, psc_props)
        self.assertEqual(len(cs_props), 16)
        self.assertEqual(pi.RECORD, "FO4SFProgression.install.json")

    def test_log_summary_and_precheck_fold_verify(self):
        s = core_log.summarize(SAMPLE_PASS_LOG)
        self.assertTrue(s["passed"], s["checks"])
        bad = [l.replace("disposition=Ally", "disposition=Enemy") for l in SAMPLE_PASS_LOG]
        self.assertFalse(core_log.summarize(bad)["passed"])

        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            cr = t / "ContentResources.zip"
            _build_synthetic_sources_zip(cr)
            self.assertEqual(mp.main(["precheck", "--content-resources", str(cr)]), 0)

            sf = t / "Starfield.esm"
            sf.write_bytes(b"TES4synth_sf")
            sf_sha = hashlib.sha256(sf.read_bytes()).hexdigest()

            stage_dir = t / "stage"
            (stage_dir / "Data" / "Scripts").mkdir(parents=True)
            (stage_dir / "FO4SFProgression.esm").write_bytes(b"TES4prog_esm")
            (stage_dir / "Data" / "Scripts" / "FO4SF_ProgressionQuest.pex").write_bytes(b"PEXprog")
            (stage_dir / "README.txt").write_text("Progression stage\n", encoding="utf-8")
            outputs = mp.stage_files(str(stage_dir))
            plan = {
                "kind": "progression-core",
                "version": 1,
                "plugin": "FO4SFProgression.esm",
                "plugin_sha256": outputs["FO4SFProgression.esm"],
                "plugins": ["FO4SFProgression.esm"],
                "scripts": {"FO4SF_ProgressionQuest": outputs["Data/Scripts/FO4SF_ProgressionQuest.pex"]},
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
                mp.main(["fold", "--stage", str(stage_dir), "--core-dir", str(core_dir), "--out", str(folded), "--starfield", str(sf)]),
                0,
            )
            self.assertEqual(
                mp.main(["verify", "--exp-dir", str(folded), "--plan", str(stage_dir / "plan.json"), "--starfield", str(sf)]),
                0,
            )

    @unittest.skipUnless(os.environ.get("FO4SF_DOTNET_TESTS") == "1", "set FO4SF_DOTNET_TESTS=1 to run ProgressionCore selftest")
    def test_dotnet_progression_core_selftest(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = subprocess.run(
                ["dotnet", "run", "-c", "Release", "--project", str(ROOT / "dotnet" / "ProgressionCore"), "--", "selftest", tmp],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(res.returncode, 0, res.stdout + "\n" + res.stderr)
            self.assertIn("selftest: ok", res.stdout)


if __name__ == "__main__":
    unittest.main()
