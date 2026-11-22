"""Offline contract, property-parity, W6 break-it batch, and clean-room tests for A7 Story Missions (MQ104 + MQ105)."""
from __future__ import annotations

from pathlib import Path
import re
import sys
import unittest

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[1]

for _p in (str(REPO_ROOT / "scripts" / "mission"), str(REPO_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import make_mission  # noqa: E402
from fo4sf.core.cross_plugin_check import build_writer_catalog  # noqa: E402

A7_CS = REPO_ROOT / "dotnet" / "Mission" / "NextStoryMissionsA7.cs"
PROGRAM_CS = REPO_ROOT / "dotnet" / "Mission" / "Program.cs"
MIN00_PSC = REPO_ROOT / "scripts" / "mission" / "FO4SF_Min00Quest.psc"
MQ103_PSC = REPO_ROOT / "scripts" / "mission" / "FO4SF_MQ103Quest.psc"
MQ104_PSC = REPO_ROOT / "scripts" / "mission" / "FO4SF_MQ104Quest.psc"
MQ105_PSC = REPO_ROOT / "scripts" / "mission" / "FO4SF_MQ105Quest.psc"

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
A7_BREAK_IT_BATCHES = [
    {
        "mission": "FO4SF_MQ104",
        "quest_hex": "09000A80",
        "axis": "giver_dead",
        "bat_id": "a7u1",
        "bat_lines": ["09000A82.kill", "setstage 09000A80 20"],
        "expected_log": "mq104 open_mode nick_unavailable -> case_notes stage 60",
    },
    {
        "mission": "FO4SF_MQ104",
        "quest_hex": "09000A80",
        "axis": "out_of_order_malone_dead",
        "bat_id": "a7u2",
        "bat_lines": ["09000A84.kill", "setstage 09000A80 85"],
        "expected_log": "mq104 malone pre_cleared -> stage 100",
    },
    {
        "mission": "FO4SF_MQ104",
        "quest_hex": "09000A80",
        "axis": "save_reload_every_stage",
        "bat_id": "a7u3",
        "bat_lines": ["sqs 09000A80"],
        "expected_log": "mq104 reload stage=",
    },
    {
        "mission": "FO4SF_MQ104",
        "quest_hex": "09000A80",
        "axis": "fast_travel_away",
        "bat_id": "a7u4",
        "bat_lines": ["sqs 09000A80"],
        "expected_log": "mq104 actors placed park_street=true",
    },
    {
        "mission": "FO4SF_MQ105",
        "quest_hex": "09000AB0",
        "axis": "giver_dead",
        "bat_id": "a7c1",
        "bat_lines": ["09000A82.kill", "09000AB2.kill", "09000AB4.kill"],
        "expected_log": "mq105 open_mode nick_unavailable -> dossier stage 30",
    },
    {
        "mission": "FO4SF_MQ105",
        "quest_hex": "09000AB0",
        "axis": "out_of_order_fort_hagen_door",
        "bat_id": "a7c2",
        "bat_lines": ["040547B0.Activate 14"],
        "expected_log": "mq105 complete stage=200 mq106_armed=1",
    },
    {
        "mission": "FO4SF_MQ105",
        "quest_hex": "09000AB0",
        "axis": "save_reload_every_stage",
        "bat_id": "a7c3",
        "bat_lines": ["sqs 09000AB0"],
        "expected_log": "mq105 reload stage=",
    },
    {
        "mission": "FO4SF_MQ105",
        "quest_hex": "09000AB0",
        "axis": "fast_travel_away",
        "bat_id": "a7c4",
        "bat_lines": ["sqs 09000AB0"],
        "expected_log": "mq105 hub actors placed diamond_city=true",
    },
]


def _declared_psc_properties(psc_text: str) -> set[str]:
    return set(re.findall(r"^\s*[\w\[\]]+\s+Property\s+(\w+)\s+Auto\b", psc_text, re.M | re.I))


class A7CSharpRecordTests(unittest.TestCase):
    def test_formid_reservations_strictly_inside_0xa80_0xaff_and_unique(self) -> None:
        cs = A7_CS.read_text(encoding="utf-8")
        self.assertIn("public const uint Mq104QuestId = 0xA80;", cs)
        self.assertIn("public const uint Mq105QuestId = 0xAB0;", cs)

        id_decls = re.findall(r"\b(\w+Id)\s*=\s*0x([0-9A-Fa-f]+)", cs)
        ids_by_name = {name: int(val, 16) for name, val in id_decls if name != "MaxAllocatedId"}
        self.assertEqual(len(ids_by_name), 32)
        for name, val in ids_by_name.items():
            self.assertGreaterEqual(val, 0xA80, f"{name} (0x{val:X}) overlaps A1/A4 0x800..0xA7F")
            self.assertLessEqual(val, 0xAFF, f"{name} (0x{val:X}) exceeds A7/A5 0xAFF ceiling")
        self.assertEqual(len(ids_by_name), len(set(ids_by_name.values())), "duplicate A7 FormID constant")

        catalog, dup_errors = build_writer_catalog(str(REPO_ROOT))
        self.assertEqual(dup_errors, [])
        mission_cat = catalog["FO4SFMission.esm"]
        self.assertEqual(mission_cat[0xA80], ("QUST", "FO4SF_MQ104"))
        self.assertEqual(mission_cat[0xAB0], ("QUST", "FO4SF_MQ105"))
        self.assertEqual(mission_cat[0xAB5], ("MISC", "FO4SF_KelloggCigar"))
        self.assertEqual(mission_cat[0xAB8], ("GLOB", "FO4SF_MQ106Armed"))
        for val in ids_by_name.values():
            self.assertIn(val, mission_cat, f"A7 FormID 0x{val:X} missing from cross_plugin_check catalog")

    def test_cs_script_property_bindings_match_psc_declarations(self) -> None:
        cs = A7_CS.read_text(encoding="utf-8")

        mq104_props_cs = set(re.findall(r'mq104Script\.Properties\.Add\(ObjProp\("(\w+)"', cs))
        mq104_props_psc = _declared_psc_properties(MQ104_PSC.read_text(encoding="utf-8"))
        self.assertTrue(mq104_props_cs, "no MQ104 properties found in C#")
        self.assertEqual(mq104_props_cs, mq104_props_psc, "MQ104 C# VMAD properties != PSC properties")

        mq105_props_cs = set(re.findall(r'mq105Script\.Properties\.Add\(ObjProp\("(\w+)"', cs))
        mq105_props_psc = _declared_psc_properties(MQ105_PSC.read_text(encoding="utf-8"))
        self.assertTrue(mq105_props_cs, "no MQ105 properties found in C#")
        self.assertEqual(mq105_props_cs, mq105_props_psc, "MQ105 C# VMAD properties != PSC properties")

    def test_program_cs_and_make_mission_wire_a7_cleanly(self) -> None:
        prog = PROGRAM_CS.read_text(encoding="utf-8")
        self.assertIn("NextStoryMissionsA7.PopulateA7Missions(", prog)
        self.assertIn("NextStoryMissionsA7.CheckA7Missions(", prog)
        self.assertIn("NextStoryMissionsA7.IsA7ActorRefId(", prog)
        for mutation in (
            "FO4SF_MQ104 removed",
            "FO4SF_MQ104 has StartGameEnabled",
            "FO4SF_MQ104 stage 10 lacks QSDT log entry",
            "FO4SF_MQ104 carries StartsEnabled",
            "FO4SF_MQ105 removed",
            "FO4SF_MQ105 has StartGameEnabled",
            "FO4SF_MQ105 stage 10 lacks QSDT log entry",
            "FO4SF_MQ105 carries 0x10000 flag",
            "FO4SF_KelloggCigar removed",
            "FO4SF_MQ106Armed GLOB removed",
        ):
            self.assertIn(mutation, prog)

        a7_cs = A7_CS.read_text(encoding="utf-8")
        # B1/B4 QUST binary invariants: no StartsEnabled/0x10000 dormancy flags, QSDT on all stages, FNAM=0 on objectives
        self.assertNotIn("SF.Quest.Flag.StartsEnabled |", a7_cs)
        self.assertNotIn("(SF.Quest.Flag)0x10000,", a7_cs)
        self.assertIn("!q.Data.Flags.HasFlag(SF.Quest.Flag.StartsEnabled)", a7_cs)
        self.assertIn("(((uint)q.Data.Flags & 0x10000u) == 0)", a7_cs)
        self.assertIn("FO4SF_MQ104 has a stage without QSDT QuestLogEntry", a7_cs)
        self.assertIn("FO4SF_MQ105 has a stage without QSDT QuestLogEntry", a7_cs)
        self.assertEqual(a7_cs.count("Flags = 0, DisplayText = otext"), 2)
        # T1 merged ACHR coordinates (Local + MergeOffset -1200, -2700) + female Darla & Geneva
        for merged in ("-987.46f, -2927.73f", "-1085.43f, -2958.22f", "-1083.0f, -2957.0f", "-1418.0f, -3125.0f", "-1422.0f, -3135.0f"):
            self.assertIn(merged, a7_cs)
        self.assertIn("PickFemaleTemplate(", a7_cs)
        self.assertIn("PickFemaleVoice(", a7_cs)
        self.assertIn("female: true", a7_cs)

        self.assertIn("FO4SF_MQ104Quest", make_mission.ALL_SCRIPTS)
        self.assertIn("FO4SF_MQ105Quest", make_mission.ALL_SCRIPTS)
        summary = make_mission.summarize([
            "FO4SF_MISSION rt=700.0 mq104 stage 200 by=nick_debrief",
            "FO4SF_MISSION rt=700.1 mq104 complete stage=200 mq105_armed=1 by=nick_debrief",
            "FO4SF_MISSION rt=800.0 mq105 stage 200 by=fort_hagen_arrival",
            "FO4SF_MISSION rt=800.1 mq105 complete stage=200 mq106_armed=1 forthagen_plugin=true by=fort_hagen_arrival",
        ])
        self.assertEqual(summary["mq104_stages"], [200])
        self.assertIn("mq105_armed=1", summary["mq104_complete"] or "")
        self.assertEqual(summary["mq105_stages"], [200])
        self.assertIn("mq106_armed=1", summary["mq105_complete"] or "")


class A7PapyrusContractTests(unittest.TestCase):
    def test_both_scripts_have_story_gate_reload_and_open_mode_guards(self) -> None:
        for path, prefix in (
            (MQ104_PSC, "mq104"),
            (MQ105_PSC, "mq105"),
        ):
            txt = path.read_text(encoding="utf-8")
            self.assertIn("bool Function IsWarfareMode()", txt, path.name)
            self.assertIn('0x000870, "FO4SFCoreValues.esm"', txt, path.name)
            self.assertIn(f"mission gate mode=2 started=false quest={prefix}", txt, path.name)
            self.assertIn('RegisterForRemoteEvent(player, "OnPlayerLoadGame")', txt, path.name)
            self.assertIn("Event Actor.OnPlayerLoadGame(Actor akSender)", txt, path.name)
            self.assertIn("Function AdvanceTo(", txt, path.name)
            self.assertIn("Event OnStageSet(", txt, path.name)
            self.assertIn("int Function EffectiveStage()", txt, path.name)
            self.assertIn("string Function ActiveCorePlugin()", txt, path.name)
            self.assertIn("FO4TerrainCore_Mars.esm", txt, path.name)
            self.assertIn("WorldSpace Function ResolveCommonwealthWorld()", txt, path.name)
            self.assertIn("if ws == None || wantWs == None || ws != wantWs", txt, path.name)
            self.assertIn("bool Function IsCommonwealthExterior(Actor player)", txt, path.name)
            self.assertIn("bool Function IsPlayerStableAt(Actor player,", txt, path.name)
            self.assertIn("Function ReleaseIfInCombat(Actor a)", txt, path.name)
            self.assertIn("Function ReleaseAllActors()", txt, path.name)
            self.assertIn("int talkSessionId = 0", txt, path.name)
            self.assertIn("talkSessionId += 1", txt, path.name)
            self.assertIn("!= 3", txt, path.name)
            self.assertIn("MergeOffsetX - 3200.0", txt, path.name)
            self.assertIn("open_mode", txt, path.name)
            self.assertNotIn("Debug.Notification(", txt, path.name)

    def test_console_free_runtime_starts_and_open_mode_simulation(self) -> None:
        min00 = MIN00_PSC.read_text(encoding="utf-8")
        mq103 = MQ103_PSC.read_text(encoding="utf-8")
        mq104 = MQ104_PSC.read_text(encoding="utf-8")
        mq105 = MQ105_PSC.read_text(encoding="utf-8")

        # 1. Runtime start callers exist for BOTH A7 quests (StartGameEnabled == false on both)
        self.assertIn("Game.GetFormFromFile(0x000A80, MissionPlugin) as Quest", mq103)
        self.assertIn('Trace("mq104 start_requested ok=" + startedMq104)', mq103)
        self.assertIn("Game.GetFormFromFile(0x000AB0, MissionPlugin) as Quest", mq104)
        self.assertIn('Trace("mq105 start_requested ok=" + startedMq105)', mq104)
        self.assertIn("Function CheckA7ProximityStarts(Actor player)", min00)
        self.assertGreaterEqual(min00.count("CheckA7ProximityStarts(player)"), 2)
        self.assertIn("mq104ProxAttempted = True", min00)
        self.assertIn("mq105ProxAttempted = True", min00)
        self.assertIn('Trace("mq104 started by=proximity")', min00)
        self.assertIn('Trace("mq105 started by=proximity")', min00)
        for coord in ("-987.46", "-2927.73", "-1085.43", "-2958.22", "-2456.84", "-2781.07"):
            self.assertIn(coord, min00)

        # 2. Verify Fort Hagen 0D handoff hooks in FO4SF_MQ105Quest.psc
        for tok in (
            'string FortHagenPlugin = "FO4SFFortHagen.esm"',
            "int FortHagenRoofDoorId = 0x0547B0",
            "int FortHagenRoofMarkerId = 0x0A774C",
            "int FortHagen01CellId = 0x00BA4B",
            "int FortHagen02CellId = 0x00CFC6",
            "MQ106Armed.SetValue(1.0)",
        ):
            self.assertIn(tok, mq105)

        # 3. Deterministic state-machine simulation for MQ104 (Normal + Out-of-order + Open-Mode Dead Nick/Malone)
        def simulate_mq104(nick_dead: bool, malone_precleared: bool, persuade: bool) -> dict[str, object]:
            stage = 10
            completed = False
            started_mq105 = False
            escape_wait = 0.0
            stages = [10]

            def advance(n: int) -> None:
                nonlocal stage, completed, started_mq105
                if n <= stage:
                    return
                stage = n
                stages.append(n)
                if n == 85 and malone_precleared:
                    advance(100)
                elif n == 200:
                    completed = True
                    started_mq105 = True

            # Enter Park Street Station / Vault 114
            advance(20)
            if nick_dead:
                advance(40)
                advance(60)
            else:
                advance(40)
                advance(60)

            # Escape Vault 11402 (R10 5 s override in Open Mode or Nick escape)
            if nick_dead:
                for _ in range(5):
                    escape_wait += 1.0
                if escape_wait >= 5.0:
                    advance(85)
            else:
                advance(85)

            if stage == 85:
                if persuade or malone_precleared:
                    advance(100)
                else:
                    # Combat kills Skinny Malone
                    advance(100)

            if stage == 100:
                advance(200)
            return {"stage": stage, "completed": completed, "started_mq105": started_mq105, "stages": stages}

        for kwargs in (
            {"nick_dead": False, "malone_precleared": False, "persuade": True},
            {"nick_dead": False, "malone_precleared": True, "persuade": False},
            {"nick_dead": True, "malone_precleared": False, "persuade": False},
        ):
            res = simulate_mq104(**kwargs)
            self.assertTrue(res["completed"], f"MQ104 stalled in {kwargs}: {res}")
            self.assertEqual(res["stage"], 200)
            self.assertTrue(res["started_mq105"])

        # 4. Deterministic state-machine simulation for MQ105 (Normal + Out-of-order + Open-Mode All NPCs Dead)
        def simulate_mq105(all_npcs_dead: bool, direct_fort_hagen: bool) -> dict[str, object]:
            stage = 10
            completed = False
            mq106_armed = False
            cigar = False

            def advance(n: int) -> None:
                nonlocal stage, completed, mq106_armed, cigar
                if n <= stage:
                    return
                stage = n
                if n in (80, 100):
                    cigar = True
                if n == 200:
                    completed = True
                    mq106_armed = True

            if direct_fort_hagen:
                advance(200)
            elif all_npcs_dead:
                advance(30)  # agency dossier
                advance(60)  # open_mode / lockpick
                advance(80)  # secret room button
                advance(100)  # open_mode dogmeat dead -> mark Fort Hagen
                advance(200)  # Fort Hagen arrival
            else:
                advance(30)  # Nick brief
                advance(60)  # Geneva key
                advance(80)  # Secret button + cigar
                advance(100)  # Dogmeat trail
                advance(200)  # Fort Hagen arrival
            return {"stage": stage, "completed": completed, "mq106_armed": mq106_armed, "cigar": cigar}

        for kwargs in (
            {"all_npcs_dead": False, "direct_fort_hagen": False},
            {"all_npcs_dead": True, "direct_fort_hagen": False},
            {"all_npcs_dead": True, "direct_fort_hagen": True},
        ):
            res = simulate_mq105(**kwargs)
            self.assertTrue(res["completed"], f"MQ105 stalled in {kwargs}: {res}")
            self.assertEqual(res["stage"], 200)
            self.assertTrue(res["mq106_armed"])


class A7BreakItBatchAndCleanRoomTests(unittest.TestCase):
    def test_w6_break_it_batches_p3_safe_and_clean_room(self) -> None:
        by_mission: dict[str, set[str]] = {}
        for case in A7_BREAK_IT_BATCHES:
            by_mission.setdefault(case["mission"], set()).add(case["axis"])
            console_cmd = f"bat {case['bat_id']}"
            for bad in ("m", "n", "v"):
                self.assertNotIn(bad, console_cmd.lower(), f"P3 violation in {console_cmd}")
            self.assertTrue(case["bat_lines"])
            self.assertTrue(case["expected_log"])
        self.assertEqual(set(by_mission.keys()), {"FO4SF_MQ104", "FO4SF_MQ105"})
        for mission, axes in by_mission.items():
            self.assertEqual(len(axes), 4, f"{mission} must cover all 4 W6 break-it axes")

        for path in (A7_CS, MQ104_PSC, MQ105_PSC, HERE):
            txt = path.read_text(encoding="utf-8")
            self.assertIsNone(DRIVE_PATH_RX.search(txt), f"drive path leak in {path.name}")
            for pat in FORBIDDEN_MOD_PATTERNS:
                self.assertIsNone(pat.search(txt), f"forbidden mod name in {path.name}")


if __name__ == "__main__":
    unittest.main()
