"""Offline contract, property-parity, W6 break-it batch, and clean-room tests for A4 Next Story Missions."""
from __future__ import annotations

from pathlib import Path
import re
import unittest

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[1]

A4_CS = REPO_ROOT / "dotnet" / "Mission" / "NextStoryMissionsA4.cs"
PROGRAM_CS = REPO_ROOT / "dotnet" / "Mission" / "Program.cs"
SANC_PSC = REPO_ROOT / "scripts" / "mission" / "FO4SF_Sanctuary01Quest.psc"
STEP_PSC = REPO_ROOT / "scripts" / "mission" / "FO4SF_MinRecruit00Quest.psc"
MQ103_PSC = REPO_ROOT / "scripts" / "mission" / "FO4SF_MQ103Quest.psc"

DRIVE_PATH_RX = re.compile(r"\b[A-Za-z]:[\\/]")
FORBIDDEN_MOD_PATTERNS = [
    re.compile(r"\b" + ("UF" + "O4P") + r"\b", re.I),
    re.compile(r"\b" + ("Unofficial" + r"\s+" + "Fallout") + r"\b", re.I),
    re.compile(r"\b" + ("Yuki" + "chigai" + "|" + "Y" + "UP") + r"\b", re.I),
    re.compile(r"\b" + ("GAM" + "MA") + r"\b", re.I),
    re.compile(r"\b" + ("Buff" + "out") + r"\b", re.I),
    re.compile(r"\b" + ("Role" + "players" + r"'?\s+" + "Alternate") + r"\b", re.I),
]

# Deterministic W6 4-axis break-it batch cases (P3-safe bat IDs: zero M/N/V in interactive console!)
A4_BREAK_IT_BATCHES = [
    {
        "mission": "FO4SF_Sanctuary01",
        "quest_hex": "09000817",
        "axis": "giver_dead",
        "bat_id": "a4s1",
        "bat_lines": ["09000A01.kill", "04005C50.Activate 14"],
        "expected_log": "sanctuary01 open_mode sturges_unavailable -> stage 1000",
    },
    {
        "mission": "FO4SF_Sanctuary01",
        "quest_hex": "09000817",
        "axis": "out_of_order_prebuilt",
        "bat_id": "a4s2",
        "bat_lines": ["set 09000A02 to 5", "set 09000A05 to 5", "set 09000A08 to 5", "set 09000A0B to 2"],
        "expected_log": "sanctuary01 stage 1050 by=beds",
    },
    {
        "mission": "FO4SF_Sanctuary01",
        "quest_hex": "09000817",
        "axis": "save_reload_every_stage",
        "bat_id": "a4s3",
        "bat_lines": ["sqs 09000817"],
        "expected_log": "sanctuary01 reload stage=",
    },
    {
        "mission": "FO4SF_Sanctuary01",
        "quest_hex": "09000817",
        "axis": "fast_travel_away",
        "bat_id": "a4s4",
        "bat_lines": ["sqs 09000817"],
        "expected_log": "sanctuary01 keeper sturges placed held=true",
    },
    {
        "mission": "FO4SF_MinRecruit00",
        "quest_hex": "09000A20",
        "axis": "giver_dead",
        "bat_id": "a4r1",
        "bat_lines": ["09000A22.kill", "0401A793.Activate 14"],
        "expected_log": "minrecruit00 stage 100 by=open_mode",
    },
    {
        "mission": "FO4SF_MinRecruit00",
        "quest_hex": "09000A20",
        "axis": "out_of_order_pre_cleared",
        "bat_id": "a4r2",
        "bat_lines": ["09000A24.kill", "setstage 09000A20 100"],
        "expected_log": "minrecruit00 corvega pre_cleared -> stage 200",
    },
    {
        "mission": "FO4SF_MinRecruit00",
        "quest_hex": "09000A20",
        "axis": "save_reload_every_stage",
        "bat_id": "a4r3",
        "bat_lines": ["sqs 09000A20"],
        "expected_log": "minrecruit00 reload stage=",
    },
    {
        "mission": "FO4SF_MinRecruit00",
        "quest_hex": "09000A20",
        "axis": "fast_travel_away",
        "bat_id": "a4r4",
        "bat_lines": ["sqs 09000A20"],
        "expected_log": "minrecruit00 corvega boss leashed",
    },
    {
        "mission": "FO4SF_MQ103",
        "quest_hex": "09000A50",
        "axis": "giver_dead",
        "bat_id": "a4q1",
        "bat_lines": ["09000A52.kill", "09000A54.kill", "04013E79.Activate 14"],
        "expected_log": "mq103 gate unlocked by=gate_override",
    },
    {
        "mission": "FO4SF_MQ103",
        "quest_hex": "09000A50",
        "axis": "out_of_order_direct_ellie",
        "bat_id": "a4q2",
        "bat_lines": ["09000A56.Activate 14"],
        "expected_log": "mq103 stage 30 by=out_of_order",
    },
    {
        "mission": "FO4SF_MQ103",
        "quest_hex": "09000A50",
        "axis": "save_reload_every_stage",
        "bat_id": "a4q3",
        "bat_lines": ["sqs 09000A50"],
        "expected_log": "mq103 reload stage=",
    },
    {
        "mission": "FO4SF_MQ103",
        "quest_hex": "09000A50",
        "axis": "fast_travel_away",
        "bat_id": "a4q4",
        "bat_lines": ["sqs 09000A50"],
        "expected_log": "mq103 gate actors placed",
    },
]


def _declared_psc_properties(psc_text: str) -> set[str]:
    return set(re.findall(r"^\s*[\w\[\]]+\s+Property\s+(\w+)\s+Auto\b", psc_text, re.M | re.I))


class A4CSharpRecordTests(unittest.TestCase):
    def test_formid_reservations_disjoint_and_sanctuary_in_place(self) -> None:
        cs = A4_CS.read_text(encoding="utf-8")
        self.assertIn("public const uint SanctuaryQuestId = 0x817;", cs)
        self.assertIn("public const uint MinRecruit00QuestId = 0xA20;", cs)
        self.assertIn("public const uint Mq103QuestId = 0xA50;", cs)

        # Extract all uint hex ID constants in NextStoryMissionsA4.cs (excluding MaxAllocatedId and SanctuaryQuestId)
        id_decls = re.findall(r"\b(\w+Id)\s*=\s*0x([0-9A-Fa-f]+)", cs)
        ids_by_name = {name: int(val, 16) for name, val in id_decls if name != "MaxAllocatedId"}
        self.assertEqual(ids_by_name["SanctuaryQuestId"], 0x817)

        new_ids = {k: v for k, v in ids_by_name.items() if k != "SanctuaryQuestId"}
        self.assertGreaterEqual(len(new_ids), 35)
        # All new A4 IDs must live strictly inside 0xA00..0xA7F (zero collision with Program.cs 0x800..0x9FF)
        for name, val in new_ids.items():
            self.assertGreaterEqual(val, 0xA00, f"{name} (0x{val:X}) overlaps 0x800..0x9FF")
            self.assertLessEqual(val, 0xA7F, f"{name} (0x{val:X}) exceeds 0xA7F reservation")
        # All new A4 IDs must be unique
        self.assertEqual(len(new_ids), len(set(new_ids.values())), "duplicate A4 FormID constant")

        # Verify exact FO4 Min01 totals (5, 5, 5, 2)
        self.assertIn("DefaultBedTotal = 5.0f", cs)
        self.assertIn("DefaultWaterTotal = 5.0f", cs)
        self.assertIn("DefaultFoodTotal = 5.0f", cs)
        self.assertIn("DefaultSafetyTotal = 2.0f", cs)

    def test_cs_script_property_bindings_match_psc_declarations(self) -> None:
        cs = A4_CS.read_text(encoding="utf-8")

        sanc_props_cs = set(re.findall(r'SetProp\(sEntry,\s*"(\w+)"', cs))
        sanc_props_psc = _declared_psc_properties(SANC_PSC.read_text(encoding="utf-8"))
        self.assertTrue(sanc_props_cs, "no Sanctuary properties found in C#")
        self.assertTrue(sanc_props_cs.issubset(sanc_props_psc), f"missing in Sanctuary PSC: {sanc_props_cs - sanc_props_psc}")

        mr_props_cs = set(re.findall(r'mrScript\.Properties\.Add\(ObjProp\("(\w+)"', cs))
        mr_props_psc = _declared_psc_properties(STEP_PSC.read_text(encoding="utf-8"))
        self.assertTrue(mr_props_cs, "no MinRecruit00 properties found in C#")
        self.assertTrue(mr_props_cs.issubset(mr_props_psc), f"missing in MinRecruit00 PSC: {mr_props_cs - mr_props_psc}")

        mq_props_cs = set(re.findall(r'mqScript\.Properties\.Add\(ObjProp\("(\w+)"', cs))
        mq_props_psc = _declared_psc_properties(MQ103_PSC.read_text(encoding="utf-8"))
        self.assertTrue(mq_props_cs, "no MQ103 properties found in C#")
        self.assertTrue(mq_props_cs.issubset(mq_props_psc), f"missing in MQ103 PSC: {mq_props_cs - mq_props_psc}")


class A4PapyrusContractTests(unittest.TestCase):
    def test_all_three_scripts_have_mission_gate_reload_and_open_mode_guards(self) -> None:
        for path, prefix in (
            (SANC_PSC, "sanctuary01"),
            (STEP_PSC, "minrecruit00"),
            (MQ103_PSC, "mq103"),
        ):
            txt = path.read_text(encoding="utf-8")
            self.assertIn("bool Function IsWarfareMode()", txt, path.name)
            self.assertIn('0x000870, "FO4SFCoreValues.esm"', txt, path.name)
            self.assertIn(f'mission gate mode=2 started=false quest={prefix}', txt, path.name)
            self.assertIn('RegisterForRemoteEvent(player, "OnPlayerLoadGame")', txt, path.name)
            self.assertIn("Event Actor.OnPlayerLoadGame(Actor akSender)", txt, path.name)
            self.assertIn("Function AdvanceTo(", txt, path.name)
            self.assertIn("Event OnStageSet(", txt, path.name)
            self.assertIn("open_mode", txt, path.name)

    def test_sanctuary01_preserves_legacy_contracts_and_adds_min01_in_place(self) -> None:
        txt = SANC_PSC.read_text(encoding="utf-8")
        # Legacy test_mission.py contracts must remain intact
        self.assertIn("Form Property XMarkerBase Auto Const Mandatory", txt)
        self.assertIn("int BenchRefId = 0x005C50", txt)
        self.assertIn("int BenchBaseId = 0x0A2ECD", txt)
        self.assertIn('Trace("min01 bench activated -> stage 100")', txt)
        self.assertIn('Trace("sanctuary01 bench_activated=true ref=" + refUsed + " complete=true")', txt)
        self.assertIn('Trace("sanctuary01 stage " + auiStageID + " by=" + cause)', txt)
        # New Min01 in-place contracts
        for tok in ("IsSturgesDeadOrMissing", "CheckMilestoneProgress", "RunSturgesTalk", "KeepSturges", "0x000A20"):
            self.assertIn(tok, txt)


class A4BreakItBatchAndCleanRoomTests(unittest.TestCase):
    def test_break_it_batches_cover_all_missions_and_axes_p3_safe(self) -> None:
        by_mission: dict[str, set[str]] = {}
        for case in A4_BREAK_IT_BATCHES:
            by_mission.setdefault(case["mission"], set()).add(case["axis"])
            # P3 rule: interactive console command `bat <bat_id>` must have zero M, N, or V
            console_cmd = f"bat {case['bat_id']}"
            for bad in ("m", "n", "v"):
                self.assertNotIn(bad, console_cmd.lower(), f"P3 violation in {console_cmd}")
            self.assertTrue(case["bat_lines"])
            self.assertTrue(case["expected_log"])
        self.assertEqual(set(by_mission.keys()), {"FO4SF_Sanctuary01", "FO4SF_MinRecruit00", "FO4SF_MQ103"})
        for m, axes in by_mission.items():
            self.assertEqual(len(axes), 4, f"{m} must cover all 4 W6 break-it axes")

    def test_zero_drive_path_leaks_and_zero_forbidden_mod_names(self) -> None:
        for path in (A4_CS, SANC_PSC, STEP_PSC, MQ103_PSC, HERE):
            txt = path.read_text(encoding="utf-8")
            self.assertIsNone(DRIVE_PATH_RX.search(txt), f"drive path leak in {path.name}")
            for pat in FORBIDDEN_MOD_PATTERNS:
                self.assertIsNone(pat.search(txt), f"forbidden mod name in {path.name}")


if __name__ == "__main__":
    unittest.main()
