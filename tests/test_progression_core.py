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

from fo4sf.core.core_values import CORE_VALUES_PLUGIN, core_form_id  # noqa: E402
from fo4sf.progression import core_log, tables  # noqa: E402
from fo4sf.reputation import tables as rep_tables  # noqa: E402

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
    "FO4SFPROG rt=5.0 karma_repu karma=-800.0 karma_tier=Very_Evil faction_slot=0 rep_state=12 end=true",
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
            "Function Notification(string asMessage) native global\n"
        ),
        "Message.psc": (
            "Scriptname Message extends Form Native\n"
            "int Function Show(float afArg1 = 0.0, float afArg2 = 0.0, float afArg3 = 0.0, float afArg4 = 0.0, "
            "float afArg5 = 0.0, float afArg6 = 0.0, float afArg7 = 0.0, float afArg8 = 0.0, float afArg9 = 0.0) native\n"
        ),
        "Utility.psc": "Scriptname Utility Native\nfloat Function GetCurrentRealTime() native global\n",
        "Quest.psc": (
            "Scriptname Quest extends Form Native\n"
            "bool Function GetStageDone(int aiStage) native\n"
            "Event OnStageSet(int auiStageID, int auiItemID)\nEndEvent\n"
        ),
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
        self.assertFalse(hasattr(tables, "REPU_FACTIONS_TABLE"))
        self.assertFalse(hasattr(tables, "REPU_MATRIX"))
        self.assertFalse(hasattr(tables, "evaluate_faction_repu"))

        for row in (*tables.SPECIAL_TABLE, *tables.SKILLS_TABLE):
            self.assertEqual(row["plugin"], CORE_VALUES_PLUGIN)
            self.assertEqual(row["id"], core_form_id(row["edid"]))

        self.assertEqual(tables.SHARED_CORE_FORM_IDS["SpecialAVList"], 0x817)
        self.assertEqual(tables.SHARED_CORE_FORM_IDS["SkillAVList"], 0x82D)
        self.assertEqual(tables.SHARED_CORE_FORM_IDS["KarmaAV"], 0x830)
        self.assertEqual(tables.SHARED_CORE_FORM_IDS["KarmaGlobal"], 0x831)
        self.assertEqual(tables.SHARED_CORE_FORM_IDS["TestModeGlobal"], 0x860)

        keyed_ids = [
            (r["plugin"], r["id"])
            for r in (
                *tables.SPECIAL_TABLE,
                *tables.SKILLS_TABLE,
                *tables.BACKGROUNDS_TABLE,
                *tables.TRAITS_TABLE,
                *tables.PERKS_TABLE,
            )
        ]
        self.assertEqual(len(keyed_ids), len(set(keyed_ids)), "every (plugin, FormID) pair must be unique")

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

    def test_decoupled_karma_and_reputation_single_authority(self):
        self.assertEqual(tables.karma_tier(-850), "Very Evil")
        r_ally = rep_tables.evaluate_faction_reputation(85.0, 0.0)
        self.assertEqual(r_ally.code, 12)
        self.assertEqual(r_ally.title, "Idolized")
        self.assertEqual(r_ally.disposition, "Ally")
        self.assertLess(r_ally.buy_mult, 1.0)

        self.assertEqual(tables.karma_tier(900), "Very Good")
        r_enemy = rep_tables.evaluate_faction_reputation(0.0, 90.0)
        self.assertEqual(r_enemy.code, 3)
        self.assertEqual(r_enemy.title, "Vilified")
        self.assertEqual(r_enemy.disposition, "Enemy")
        self.assertEqual(rep_tables.evaluate_faction_reputation(80.0, 80.0).code, 15)


def _parse_progression_cs_messages(cs: str) -> list[tuple[int, str, list[str]]]:
    uint_consts = {
        m.group(1): int(m.group(2).rstrip("uU"), 0)
        for bm in re.finditer(r"\bconst\s+uint\s+([^;]+);", cs, re.S)
        for part in bm.group(1).split(",")
        if (m := re.match(r"\s*(\w+)\s*=\s*(0x[0-9A-Fa-f]+u?|\d+u?)", part.strip()))
    }
    str_consts = {
        m.group(1): m.group(2)
        for bm in re.finditer(r"\bconst\s+string\s+([^;]+);", cs, re.S)
        for part in bm.group(1).split(",")
        if (m := re.match(r'\s*(\w+)\s*=\s*"([^"]*)"', part.strip()))
    }
    cm_block = cs[cs.index("CreationMessages ="):cs.index("static readonly uint[] SpecialAllocationMsgIds")]
    rows = []
    for m in re.finditer(
        r'\(\s*(\w+|0x[0-9A-Fa-f]+)\s*,\s*(\w+|"[^"]+")\s*,.*?new\[\]\s*\{([^}]*)\}\s*\)',
        cm_block,
        re.S,
    ):
        raw_id, raw_edid, btns_raw = m.groups()
        fid = int(raw_id, 16) if raw_id.startswith("0x") else uint_consts[raw_id]
        edid = raw_edid.strip('"') if raw_edid.startswith('"') else str_consts[raw_edid]
        btns = re.findall(r'"([^"]+)"', btns_raw)
        rows.append((fid, edid, btns))
    return rows


class PluginParityAndStageTests(unittest.TestCase):
    def test_csharp_psc_and_python_tables_match_1_to_1(self):
        cs = (ROOT / "dotnet" / "ProgressionCore" / "Program.cs").read_text(encoding="utf-8")
        for row in (*tables.BACKGROUNDS_TABLE, *tables.TRAITS_TABLE, *tables.PERKS_TABLE):
            self.assertIn(f'(0x{row["id"]:X}, "{row["edid"]}"', cs)
        for row in (*tables.SPECIAL_TABLE, *tables.SKILLS_TABLE):
            self.assertNotIn(f'"{row["edid"]}"', cs)
        self.assertNotIn("FO4SF_Repu_", cs)
        self.assertNotIn("FO4SF_Fact_", cs)

        m_obj = re.search(r"ObjPropNames\s*=\s*\{([^}]*)\}", cs, re.S)
        m_val = re.search(r"ValuePropNames\s*=\s*\{([^}]*)\}", cs, re.S)
        self.assertIsNotNone(m_obj)
        self.assertIsNotNone(m_val)
        cs_props = re.findall(r'"(\w+)"', m_obj.group(1)) + re.findall(r'"(\w+)"', m_val.group(1))
        psc = (ROOT / "scripts" / "progression" / "FO4SF_ProgressionQuest.psc").read_text(encoding="utf-8")
        psc_props = [pm.group(1) for pm in re.finditer(r"^\s*[\w\[\]]+\s+Property\s+(\w+)\s+Auto\s+Const\b", psc, re.M)]
        self.assertEqual(cs_props, psc_props)
        self.assertEqual(len(cs_props), 31)
        self.assertIn("TestModeGlobal", cs_props)
        for msg_prop in (
            "SpecialPage1Msg",
            "SpecialPage2Msg",
            "SpecialDefaultMsg",
            "TagSkillsPage1Msg",
            "TagSkillsPage2Msg",
            "TagSkillsPage3Msg",
            "BackgroundPage1Msg",
            "BackgroundPage2Msg",
            "TraitsPage1Msg",
            "TraitsPage2Msg",
            "TraitsPage3Msg",
            "RespecRefusedMsg",
            "SpecialBoxNames",
            "SpecialBoxButtonCounts",
            "StandardSpread40",
            "StandardSpread28",
        ):
            self.assertIn(msg_prop, cs_props)
        self.assertNotIn("RepuGlobalsList", cs_props)
        self.assertNotIn("FactionList", cs_props)
        self.assertNotIn("SyncFactionRepu", psc)
        self.assertNotIn("RepuAxisTier", psc)
        self.assertNotIn("0x0001C21C", psc)
        self.assertIn("int Function ReadFactionRepState(int slotIndex)", psc)
        self.assertIn('Game.GetFormFromFile(0x000870 + slotIndex, "FO4SFReputation.esm") as GlobalVariable', psc)
        self.assertIn("bool Function ApplyCreationSheet(", psc)
        self.assertIn("bool Function OpenCreationSheetMenu()", psc)
        self.assertIn("if TestModeGlobal != None && TestModeGlobal.GetValue() != 0.0", psc)
        self.assertEqual(pi.RECORD, "FO4SFProgression.install.json")

    def test_interactive_creation_sheet_menus_and_single_respec_contract(self):
        cs = (ROOT / "dotnet" / "ProgressionCore" / "Program.cs").read_text(encoding="utf-8")
        psc = (ROOT / "scripts" / "progression" / "FO4SF_ProgressionQuest.psc").read_text(encoding="utf-8")
        self.assertIn("MaxMessageButtons = 7", cs)
        # B3: Every single MESG in CreationMessages must have <= 7 buttons, and Confirm is reachable on Page 1
        msg_rows = _parse_progression_cs_messages(cs)
        self.assertEqual(len(msg_rows), 12)
        btns_by_edid = {}
        for fid, edid, btns in msg_rows:
            self.assertGreaterEqual(len(btns), 1, edid)
            self.assertLessEqual(len(btns), 7, f"{edid} (0x{fid:X}) exceeds 7 buttons: {btns}")
            btns_by_edid[edid] = btns
        self.assertTrue(any("Confirm" in b for b in btns_by_edid["FO4SF_ProgSpecialPage1Msg"]))
        self.assertIn("Use the standard spread", btns_by_edid["FO4SF_ProgSpecialDefaultMsg"])
        for fid, edid in (
            ("0x870", "FO4SF_ProgSpecialPage1Msg"),
            ("0x871", "FO4SF_ProgTagSkillsPage1Msg"),
            ("0x872", "FO4SF_ProgTagSkillsPage2Msg"),
            ("0x873", "FO4SF_ProgBackgroundMsg"),
            ("0x874", "FO4SF_ProgBackgroundPage2Msg"),
            ("0x875", "FO4SF_ProgTraitsMsg"),
            ("0x876", "FO4SF_ProgTraitsPage2Msg"),
            ("0x877", "FO4SF_ProgRespecRefusedMsg"),
            ("0x878", "FO4SF_ProgSpecialPage2Msg"),
            ("0x879", "FO4SF_ProgTagSkillsPage3Msg"),
            ("0x87A", "FO4SF_ProgTraitsPage3Msg"),
            ("0x87B", "FO4SF_ProgSpecialDefaultMsg"),
        ):
            self.assertIn(fid, cs)
            self.assertIn(edid, cs)
        self.assertIn("Stages = { 10, 15, 20, 30, 40, 50 }", cs)
        self.assertIn('LogLine("creation_applied", "source=" + source', psc)
        self.assertIn('ApplyCreationSheet(player, bgIdx, traits[0], traits[1], stats[0], stats[1], stats[2], stats[3], stats[4], stats[5], stats[6], tags[0], tags[1], tags[2], "lift_menu")', psc)
        self.assertIn('respecOk = ApplyExitTraitRespec(player, traits[0], traits[1])', psc)
        self.assertIn('LogLine("respec_applied", "source=lift_menu', psc)
        self.assertIn('LogLine("respec_refused", "source=lift_menu reason=limit_1")', psc)
        self.assertIn("if unspent != 0", psc)
        self.assertIn("if CountSelectedTags(tags) == 3", psc)
        self.assertIn("string boxName = SpecialBoxNames[pageIdx]", psc)
        self.assertIn("int boxButtons = SpecialBoxButtonCounts[pageIdx]", psc)
        self.assertIn('"special box shown box=" + boxName + " buttons=" + boxButtons', psc)
        self.assertIn('"special box press=" + presses + " box=" + boxName + " button="', psc)
        self.assertIn("bool Function OpenSpecialAllocationOnly(string sourceTag)", psc)
        self.assertIn('"special set S=" + stats[0]', psc)
        self.assertIn('"special default sum=" + sum + " source=" + sourceTag', psc)
        self.assertIn("Function ApplyWarfareBackground(int bgIdx)", psc)
        with self.assertRaises(SystemExit):
            mp.refuse_forbidden_out_dir(str(ROOT / "bad_prog_stage"))

    def test_log_summary_and_precheck_fold_verify(self):
        s = core_log.summarize(SAMPLE_PASS_LOG)
        self.assertTrue(s["passed"], s["checks"])
        bad = [l.replace("rep_state=12", "rep_state=3") for l in SAMPLE_PASS_LOG]
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

    def test_a3_a12_special_menu_store_handoff_and_pool_cap(self):
        psc = (ROOT / "scripts" / "progression" / "FO4SF_ProgressionQuest.psc").read_text(encoding="utf-8")
        self.assertIn("bool Function ApplySpecialMenuCommit(Actor player)", psc)
        self.assertIn("ApplySpecialMenuCommit(player)", psc)
        for fid in range(0x000880, 0x000888):
            self.assertIn(f'Game.GetFormFromFile(0x{fid:06X}, "FO4SFCoreValues.esm") as GlobalVariable', psc)
        self.assertIn("reqGlob.SetValue(0.0)", psc)
        self.assertIn('return CommitSpecialAllocation(player, stats, "fo4_menu", false)', psc)
        self.assertIn('LogLine("special", "set S=" + stats[0] + " P=" + stats[1] + " E=" + stats[2] + " C=" + stats[3] + " I=" + stats[4] + " A=" + stats[5] + " L=" + stats[6] + " sum=" + sum + " source=" + sourceTag)', psc)

        # Simulate FO4SF_ProgressionQuest.ApplySpecialMenuCommit against shared store globals (0x000880..0x000887)
        def _sim_apply(pending_vals: list[int], commit_req: float, pool28: bool = False) -> tuple[bool, float, dict[int, int] | None, str]:
            if commit_req < 0.5:
                return False, commit_req, None, ""
            new_req = 0.0
            if any(v < 1 or v > 10 for v in pending_vals):
                return False, new_req, None, "reason=special_menu_stat_range source=fo4_menu"
            req_pool = 28 if pool28 else 40
            s = sum(pending_vals)
            if s != req_pool:
                return False, new_req, None, f"reason=pool_mismatch sum={s} required={req_pool} source=fo4_menu"
            alloc = dict(zip(("STR", "PER", "END", "CHA", "INT", "AGI", "LCK"), pending_vals))
            tables.validate_special_allocation(alloc, use_fo4_pool_28=pool28)
            skills = tables.compute_initial_skills(
                alloc,
                background_name="Vault Dweller",
                tag_skills=["Speech", "Guns", "Lockpick"],
                traits=[],
            )
            log = (
                f"FO4SFPROG rt=10.0 special set S={pending_vals[0]} P={pending_vals[1]} E={pending_vals[2]} "
                f"C={pending_vals[3]} I={pending_vals[4]} A={pending_vals[5]} L={pending_vals[6]} sum={s} source=fo4_menu end=true"
            )
            return True, new_req, skills, log

        # 40-pt pool apply clears commit_req, recomputes all 13 skills, and logs source=fo4_menu
        ok40, req_after, sk40, log40 = _sim_apply([6, 5, 5, 6, 7, 6, 5], 1.0, pool28=False)
        self.assertTrue(ok40)
        self.assertEqual(req_after, 0.0)
        self.assertEqual(len(sk40), 13)
        self.assertIn("special set S=6 P=5 E=5 C=6 I=7 A=6 L=5 sum=40 source=fo4_menu", log40)

        # Pool mismatch (sum=41 or sum=35 on 40-pt pool) is refused and still clears commit_req so it cannot loop
        ok_bad, req_bad_after, sk_bad, log_bad = _sim_apply([10, 6, 5, 6, 7, 4, 3], 1.0, pool28=False)
        self.assertFalse(ok_bad)
        self.assertEqual(req_bad_after, 0.0)
        self.assertIsNone(sk_bad)
        self.assertIn("reason=pool_mismatch sum=41 required=40 source=fo4_menu", log_bad)

        # 28-pt pool mode accepts exact 28-pt sum
        ok28, _, sk28, log28 = _sim_apply([4, 4, 4, 4, 4, 4, 4], 1.0, pool28=True)
        self.assertTrue(ok28)
        self.assertEqual(len(sk28), 13)
        self.assertIn("sum=28 source=fo4_menu", log28)

    @unittest.skipUnless(os.environ.get("FO4SF_DOTNET_TESTS") == "1", "set FO4SF_DOTNET_TESTS=1 to run ProgressionCore selftest")
    def test_dotnet_progression_core_selftest(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = subprocess.run(
                ["dotnet", "run", "-c", "Release", "--project", str(ROOT / "dotnet" / "ProgressionCore"), "--", "selftest", tmp],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(res.returncode, 0, res.stdout + "\n" + res.stderr)
            self.assertIn("selftest: ok", res.stdout)


class SpecialBoxAndStandardSpreadExecutionTests(unittest.TestCase):
    """B3: Translated-execution tests on FO4SF_ProgressionQuest.psc using the single translator in test_exit_arrival."""

    FUNCS = (
        "ActiveSpecialPool",
        "AdjustSpecialStat",
        "RunSpecialMenu",
        "CommitSpecialAllocation",
        "ApplyStandardSpread",
        "OfferStandardSpread",
        "OpenSpecialAllocationOnly",
        "OpenAttributeAllocation",
    )
    VARS = "specialAllocatedOnce, liftSpecialFailures"

    def setUp(self):
        from types import SimpleNamespace
        from tests.test_exit_arrival import translated_functions

        cs = (ROOT / "dotnet" / "ProgressionCore" / "Program.cs").read_text(encoding="utf-8")
        by_id = {fid: (edid, len(btns)) for fid, edid, btns in _parse_progression_cs_messages(cs)}
        # Populate SpecialBoxNames & SpecialBoxButtonCounts directly from the C# writer's record table!
        box_names = [by_id[0x870][0], by_id[0x878][0]]
        box_counts = [by_id[0x870][1], by_id[0x878][1]]

        self.avs = [f"AV_{i}" for i in range(7)]
        self.written_stats = {}
        self.prog_logs = []
        self.ng_logs = []
        self.recomputes = 0
        self.pool28 = 0.0
        self.page1_queue = []
        self.page2_queue = []
        self.default_queue = []

        self.player = SimpleNamespace(
            GetValue=lambda av: float(self.written_stats.get(av, 5.0)),
            SetValue=lambda av, val: self.written_stats.__setitem__(av, float(val)),
        )
        psc = (ROOT / "scripts" / "progression" / "FO4SF_ProgressionQuest.psc").read_text(encoding="utf-8")
        self.ns = dict(
            specialAllocatedOnce=False,
            liftSpecialFailures=0,
            Pool28Global=SimpleNamespace(GetValue=lambda: self.pool28),
            SpecialBoxNames=box_names,
            SpecialBoxButtonCounts=box_counts,
            StandardSpread40=[6, 5, 5, 6, 7, 6, 5],
            StandardSpread28=[4, 4, 4, 4, 4, 4, 4],
            SpecialPage1Msg=SimpleNamespace(Show=lambda *a: self.page1_queue.pop(0) if self.page1_queue else -1),
            SpecialPage2Msg=SimpleNamespace(Show=lambda *a: self.page2_queue.pop(0) if self.page2_queue else -1),
            SpecialDefaultMsg=SimpleNamespace(Show=lambda *a: self.default_queue.pop(0) if self.default_queue else 0),
            Game=SimpleNamespace(GetPlayer=lambda: self.player),
            Debug=SimpleNamespace(Notification=lambda *_: None),
            GetSpecialAV=lambda idx: self.avs[idx],
            RecomputeSkillsAndDerived=lambda p: setattr(self, "recomputes", self.recomputes + 1),
            LogLine=lambda step, body: self.prog_logs.append(f"{step} {body}"),
            LogNewGameLine=lambda body: self.ng_logs.append(str(body)),
        )
        exec(compile(translated_functions(psc, self.FUNCS, self.VARS), "<FO4SF_ProgressionQuest>", "exec"), self.ns)

    def test_b3_writer_table_box_names_button_counts_and_confirm_from_page_1(self):
        # Spend 5 points on Page 1 (+2 STR, Next -> Page 2 +2 INT, Back -> Page 1 +1 PER, Confirm on Page 1!)
        self.page1_queue = [0, 0, 4, 1, 5]  # +STR, +STR, Next, +PER, Confirm (button 5 on Page 1!)
        self.page2_queue = [1, 1, 5]        # +INT, +INT, Back
        ok = self.ns["OpenAttributeAllocation"]("lift")
        self.assertTrue(ok)
        self.assertEqual([int(self.written_stats[av]) for av in self.avs], [7, 6, 5, 5, 7, 5, 5])
        self.assertTrue(
            any("special box shown box=FO4SF_ProgSpecialPage1Msg buttons=7" in l for l in self.ng_logs),
            self.ng_logs,
        )
        self.assertTrue(
            any("special box shown box=FO4SF_ProgSpecialPage2Msg buttons=7" in l for l in self.ng_logs),
            self.ng_logs,
        )
        self.assertTrue(
            any("special box press=1 box=FO4SF_ProgSpecialPage1Msg button=0" in l for l in self.ng_logs),
            self.ng_logs,
        )
        self.assertIn("special set S=7 P=6 E=5 C=5 I=7 A=5 L=5 sum=40 source=lift", self.ng_logs)
        self.assertFalse(any("special default " in l for l in self.ng_logs))

    def test_b3_three_cancelled_lift_tries_offer_standard_spread_sum_40_and_28(self):
        # 40-point pool: 2 cancels return False; 3rd cancel offers SpecialDefaultMsg ("Use the standard spread" = 0)
        self.page1_queue = [6, 6, 6]  # Cancel 3 times
        self.default_queue = [0]
        self.assertFalse(self.ns["OpenAttributeAllocation"]("lift"))
        self.assertFalse(self.ns["OpenAttributeAllocation"]("lift"))
        self.assertEqual(self.written_stats, {})
        self.assertTrue(self.ns["OpenAttributeAllocation"]("lift"))
        self.assertEqual([int(self.written_stats[av]) for av in self.avs], [6, 5, 5, 6, 7, 6, 5])
        self.assertIn("special set S=6 P=5 E=5 C=6 I=7 A=6 L=5 sum=40 source=lift", self.ng_logs)
        self.assertIn("special default sum=40 source=lift", self.ng_logs)
        self.assertIn("special_default sum=40 source=lift", self.prog_logs)

        # 28-point pool: 3 cancels on lift apply 4/4/4/4/4/4/4 (= 28) through the same CommitSpecialAllocation write path
        self.setUp()
        self.pool28 = 1.0
        self.page1_queue = [-1, -1, -1]
        self.default_queue = [0]
        self.assertFalse(self.ns["OpenAttributeAllocation"]("lift"))
        self.assertFalse(self.ns["OpenAttributeAllocation"]("lift"))
        self.assertTrue(self.ns["OpenAttributeAllocation"]("lift"))
        self.assertEqual([int(self.written_stats[av]) for av in self.avs], [4, 4, 4, 4, 4, 4, 4])
        self.assertIn("special set S=4 P=4 E=4 C=4 I=4 A=4 L=4 sum=28 source=lift", self.ng_logs)
        self.assertIn("special default sum=28 source=lift", self.ng_logs)

    def test_b3_warfare_three_tries_then_standard_spread_logs_source_warfare(self):
        self.page1_queue = [6, 6, 6]
        self.default_queue = [0]
        alloc_ok = False
        for _ in range(3):
            alloc_ok = self.ns["OpenAttributeAllocation"]("warfare")
            self.assertFalse(alloc_ok)
        alloc_ok = self.ns["OfferStandardSpread"]("warfare", False)
        self.assertTrue(alloc_ok)
        self.assertEqual([int(self.written_stats[av]) for av in self.avs], [6, 5, 5, 6, 7, 6, 5])
        self.assertIn("special set S=6 P=5 E=5 C=6 I=7 A=6 L=5 sum=40 source=warfare", self.ng_logs)
        self.assertIn("special default sum=40 source=warfare", self.ng_logs)


if __name__ == "__main__":
    unittest.main()
