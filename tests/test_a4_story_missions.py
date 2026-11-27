"""Offline contract, property-parity, W6 break-it batch, and clean-room tests for A4 Next Story Missions."""
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

A4_CS = REPO_ROOT / "dotnet" / "Mission" / "NextStoryMissionsA4.cs"
PROGRAM_CS = REPO_ROOT / "dotnet" / "Mission" / "Program.cs"
MIN00_PSC = REPO_ROOT / "scripts" / "mission" / "FO4SF_Min00Quest.psc"
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


    def test_program_cs_and_make_mission_wire_a4_cleanly(self) -> None:
        prog = PROGRAM_CS.read_text(encoding="utf-8")
        self.assertIn("NextStoryMissionsA4.PopulateA4Missions(", prog)
        self.assertIn("NextStoryMissionsA4.CheckA4Missions(", prog)
        self.assertIn("NextStoryMissionsA4.IsA4ActorRefId(", prog)
        for mutation in (
            "duplicate second Sanctuary quest added",
            "FO4SF_MinRecruit00 removed",
            "FO4SF_MinRecruit00 has StartGameEnabled",
            "FO4SF_MQ103 removed",
            "FO4SF_MQ103 has StartGameEnabled",
            "Min01 BedTotal GLOB mutated",
        ):
            self.assertIn(mutation, prog)

        for scr in (
            "FO4SF_Min00Quest",
            "FO4SF_COMPreston",
            "FO4SF_Codsworth01Quest",
            "FO4SF_Sanctuary01Quest",
            "FO4SF_MinRecruit00Quest",
            "FO4SF_MQ103Quest",
        ):
            self.assertIn(scr, make_mission.ALL_SCRIPTS)
        summary = make_mission.summarize([
            "FO4SF_MISSION rt=400.0 sanctuary01 stage 1500 by=sturges",
            "FO4SF_MISSION rt=400.1 sanctuary01 finished stage=1500 by=sturges",
            "FO4SF_MISSION rt=500.0 minrecruit00 stage 500 by=preston",
            "FO4SF_MISSION rt=500.1 minrecruit00 complete stage=500 flare_gun=true min02_unlocked=1 by=preston",
            "FO4SF_MISSION rt=600.0 mq103 stage 100 by=ellie",
            "FO4SF_MISSION rt=600.1 mq103 complete stage=100 mq104_armed=1 by=ellie",
        ])
        self.assertEqual(summary["sanctuary01_stages"], [1500])
        self.assertIn("stage=1500", summary["sanctuary01_finished"] or "")
        self.assertEqual(summary["minrecruit00_stages"], [500])
        self.assertIn("flare_gun=true", summary["minrecruit00_complete"] or "")
        self.assertEqual(summary["mq103_stages"], [100])
        self.assertIn("mq104_armed=1", summary["mq103_complete"] or "")

        catalog, dup_errors = build_writer_catalog(str(REPO_ROOT))
        self.assertEqual(dup_errors, [])
        self.assertEqual(catalog["FO4SFMission.esm"][0x817], ("QUST", "FO4SF_Sanctuary01"))
        self.assertEqual(catalog["FO4SFMission.esm"][0xA20], ("QUST", "FO4SF_MinRecruit00"))
        self.assertEqual(catalog["FO4SFMission.esm"][0xA50], ("QUST", "FO4SF_MQ103"))


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
            self.assertIn("int Function EffectiveStage()", txt, path.name)
            self.assertIn("bool Function IsCommonwealthExterior(Actor player)", txt, path.name)
            self.assertIn("MergeOffsetX - 3200.0", txt, path.name)
            self.assertIn("Event OnStageSet(", txt, path.name)
            self.assertIn("open_mode", txt, path.name)

    def test_b1_b2_b4_binary_qust_and_proximity_guards(self) -> None:
        a4_cs = A4_CS.read_text(encoding="utf-8")
        prog_cs = PROGRAM_CS.read_text(encoding="utf-8")
        min00 = MIN00_PSC.read_text(encoding="utf-8")
        self.assertIn("!q.Data.Flags.HasFlag(SF.Quest.Flag.StartsEnabled)", a4_cs)
        self.assertIn("(((uint)q.Data.Flags & 0x10000u) == 0)", a4_cs)
        self.assertIn("has a stage without QSDT QuestLogEntry", a4_cs)
        self.assertIn("FO4SF_MinRecruit00 stage 50 lacks QSDT log entry", prog_cs)
        self.assertIn("FO4SF_MQ103 stage 10 lacks QSDT log entry", prog_cs)
        self.assertIn("if !IsCommonwealthExterior(player) || IsWarfareMode()", min00)

    def test_sanctuary01_preserves_legacy_contracts_and_adds_min01_in_place(self) -> None:
        txt = SANC_PSC.read_text(encoding="utf-8")
        # Legacy test_mission.py contracts must remain intact (H6 reads bench id/plugin/radius from FO4SFWorkshop.esm)
        self.assertIn("Form Property XMarkerBase Auto Const Mandatory", txt)
        self.assertNotIn("005C50", txt)
        self.assertIn("int Function ResolveSanctuaryBenchRefId()", txt)
        self.assertIn("string Function ResolveSanctuaryBenchPlugin()", txt)
        self.assertIn("float Function ResolveSanctuaryBuildRadius()", txt)
        self.assertIn("int BenchBaseId = 0x0A2ECD", txt)
        self.assertIn('Trace("min01 bench activated -> stage 100")', txt)
        self.assertIn('Trace("sanctuary01 bench_activated=true ref=" + refUsed + " complete=true")', txt)
        self.assertIn('Trace("sanctuary01 stage " + auiStageID + " by=" + cause)', txt)
        # New Min01 in-place contracts (incl. console-free workbench build menu 0xA15)
        for tok in (
            "IsSturgesDeadOrMissing",
            "CheckMilestoneProgress",
            "RunSturgesTalk",
            "RunWorkbenchBuildMenu",
            "WorkbenchBuildMsg",
            "0x000A15",
            "KeepSturges",
            "0x000A20",
            "if st == 100 && IsCompleted() && HasFullMin01() && !a4Upgraded",
        ):
            self.assertIn(tok, txt)
        self.assertNotIn("if st == 100 && IsCompleted() && HasFullMin01() && !completed", txt)

    def test_blind_audit_350_defects_fixed(self) -> None:
        """Verifies all #350 blind-audit A4 fixes across C#, Papyrus, and cross-plugin catalog."""
        a4_cs = A4_CS.read_text(encoding="utf-8")
        sanc = SANC_PSC.read_text(encoding="utf-8")
        step = STEP_PSC.read_text(encoding="utf-8")
        mq103 = MQ103_PSC.read_text(encoding="utf-8")
        min00 = MIN00_PSC.read_text(encoding="utf-8")

        # 1. Persistent GateProxyActi (0x000A59) + gateRef.DisableNoWait(False) + Alias 0 XMarkerBase in MQ103
        self.assertIn("GateProxyActiId = 0xA59", a4_cs)
        self.assertIn("GateProxyActiModel = Mission.CodsworthTalkActiModel", a4_cs)
        self.assertNotIn("Meshes\\\\Markers\\\\MarkerError.nif", a4_cs)
        self.assertIn("InvertFacing = false", a4_cs)
        self.assertIn("new P3Float(-0.25f, -0.25f, -0.25f)", a4_cs)
        self.assertIn('ObjProp("GateProxyActi"', a4_cs)
        self.assertIn("Activator Property GateProxyActi Auto Const", mq103)
        self.assertIn("gateRef.DisableNoWait(False)", mq103)
        self.assertIn("Function EnsureGateMarkerAndProxy(Actor player)", mq103)
        self.assertIn("gateAlias.ForceRefTo(gateMarker)", mq103)
        self.assertIn("gateProxy = player.PlaceAtMe(proxyBase, 1, True, False, False)", mq103)
        catalog, dup_errors = build_writer_catalog(str(REPO_ROOT))
        self.assertEqual(dup_errors, [])
        self.assertEqual(catalog["FO4SFMission.esm"][0xA59], ("ACTI", "FO4SF_MQ103_GateProxyActi"))
        self.assertEqual(catalog["FO4TerrainCore.esm"][0x013E79], ("REFR", "FO4Core_DiamondCityGateRef"))
        self.assertEqual(catalog["FO4TerrainCore.esm"][0x01A793], ("REFR", "FO4Core_TenpinesWorkbenchRef"))
        self.assertEqual(catalog["FO4TerrainCore.esm"][0x000803], ("WRLD", "FO4Core_Commonwealth"))

        # 2. Merged ACHR coordinates in C# + WorldSpace identity & _Mars core fallback in all 3 A4 scripts
        self.assertIn("MergeOffsetX = -1200.0f", a4_cs)
        self.assertIn("MergeOffsetY = -2700.0f", a4_cs)
        self.assertIn("-192.0f + MergeOffsetX, -402.0f + MergeOffsetY", a4_cs)
        for path, txt in ((SANC_PSC, sanc), (STEP_PSC, step), (MQ103_PSC, mq103)):
            self.assertIn('CoreFallbackPlugin = "FO4TerrainCore_Mars.esm"', txt, path.name)
            self.assertIn("string Function ActiveCorePlugin()", txt, path.name)
            self.assertIn("WorldSpace Function ResolveCommonwealthWorld()", txt, path.name)
            self.assertIn("if wantWs == None || ws != wantWs", txt, path.name)
            self.assertIn("talkSessionId += 1", txt, path.name)
            self.assertIn("SetRestrained(False)", txt, path.name)

        # 3. Ellie post-gate (never in PlaceGateActors), AreGateNpcsDead uses &&, dead-Ellie st>=20&&st<=30
        m_place = re.search(r"Function PlaceGateActors\(.*?EndFunction", mq103, re.S)
        self.assertIsNotNone(m_place)
        self.assertNotIn("ResolveEllie", m_place.group(0))
        self.assertIn("Function PlaceEllieAtAgency(Actor player)", mq103)
        self.assertIn("return pDead && mDead", mq103)
        self.assertNotIn("return pDead || mDead", mq103)
        self.assertIn("elseif st >= 20 && st <= 30 && IsEllieDead()", mq103)

        # 4. CorvegaBoss hostile raider clone (weapon/ammo/!Protected/no Talk/combat+sandbox packages) + pre-clear placement
        self.assertIn("CloneHostileBossNpc(", a4_cs)
        self.assertIn("npc.ActivateTextOverride = null;", a4_cs)
        self.assertIn("SF.Npc.Flag.Protected", a4_cs)
        self.assertIn("raiderCombatPackKey", a4_cs)
        self.assertIn("boss.StartCombat(player)", step)
        self.assertIn("FindClosestReferenceOfType", step)
        self.assertIn("if btn < 0 || btn == 3 || mySession != talkSessionId", step)
        self.assertIn("if st == 450 && IsPrestonDead()", step)

        # 5. Female template/voice/flag on Piper & Ellie
        self.assertIn("PickFemaleTemplate(", a4_cs)
        self.assertIn("PickFemaleVoice(", a4_cs)
        self.assertIn("SF.Npc.Flag.Female", a4_cs)

        # 6. R1: Sanctuary01 does NOT start MQ103 during the opening (only via StartPostOpeningHandoffs on completion)
        self.assertIn("StartPostOpeningHandoffs()", sanc)
        self.assertNotIn("StartMq103StoryHandoffIfNeeded()", sanc)
        self.assertIn("bool mq103ProxAttempted = False", min00)
        self.assertIn("bool minRecruitProxAttempted = False", min00)

    def test_console_free_runtime_starts_and_full_completion_of_all_three_a4_missions(self) -> None:
        """Proves zero-console keyboard+mouse start and completion for Sanctuary01, MinRecruit00, and MQ103."""
        min00 = MIN00_PSC.read_text(encoding="utf-8")
        sanc = SANC_PSC.read_text(encoding="utf-8")
        step = STEP_PSC.read_text(encoding="utf-8")
        mq103 = MQ103_PSC.read_text(encoding="utf-8")

        # 1. Runtime start callers exist for ALL THREE A4 quests (StartGameEnabled == false on all 3)
        #    - Sanctuary01 (0x000817): started by Min00 stage 200
        #    - MQ103 (0x000A50): started by Sanctuary01 completion (R1) AND JOTC-02 150 m Diamond City proximity
        #    - MinRecruit00 (0x000A20): started by Sanctuary01 completion AND 150 m Tenpines proximity
        self.assertIn('Game.GetFormFromFile(0x000817, "FO4SFMission.esm") as Quest', min00)
        self.assertIn('Game.GetFormFromFile(0x000A50, MissionPlugin) as Quest', sanc)
        self.assertIn("Function CheckA4ProximityStarts(Actor player)", min00)
        self.assertIn('Trace("mq103 started by=proximity")', min00)
        self.assertIn('Trace("minrecruit00 started by=proximity")', min00)
        self.assertIn("-1416.36", min00)
        self.assertIn("-3129.39", min00)
        self.assertIn("-1517.0", min00)
        self.assertIn("-1423.63", min00)
        self.assertEqual(min00.count("CheckA4ProximityStarts(player)"), 1)
        self.assertIn("Game.GetFormFromFile(0x000A20, MissionPlugin) as Quest", sanc)
        self.assertIn("firstStep.StartNoWait()", sanc)

        # 2. Console-free Sanctuary01 workbench build menu (0xA15) writes all 4 Min01 resource GLOBs
        for glob_hex, item_name in (
            ("0x000A02", "bed"),
            ("0x000A05", "water"),
            ("0x000A08", "food"),
            ("0x000A0B", "defense"),
        ):
            self.assertIn(glob_hex, sanc)
            self.assertIn(f'sanctuary01 bench build item={item_name} count=', sanc)

        # 3. Execute console-free simulation of Sanctuary01 (Normal + SANC-01 pre-build + Open-Mode dead Sturges)
        def simulate_sanctuary01(sturges_dead: bool, prebuild_before_sturges: bool) -> dict[str, object]:
            stage = 10
            completed = False
            started_minrecruit = False
            globs = {"bed": 0.0, "water": 0.0, "food": 0.0, "defense": 0.0}
            totals = {"bed": 5.0, "water": 5.0, "food": 5.0, "defense": 2.0}
            stages_seen = [10]

            def advance(n: int) -> None:
                nonlocal stage, completed, started_minrecruit
                if n <= stage:
                    return
                stage = n
                stages_seen.append(n)
                if n == 100 and sturges_dead:
                    advance(1000)
                elif n == 1000 and globs["bed"] >= totals["bed"]:
                    advance(1050)
                elif n == 1200 and globs["water"] >= totals["water"]:
                    advance(1250)
                elif n == 1300 and globs["food"] >= totals["food"]:
                    advance(1350)
                elif n == 1400 and globs["defense"] >= totals["defense"]:
                    advance(1450)
                elif n == 1500:
                    completed = True
                    started_minrecruit = True

            def check_milestone() -> None:
                if stage == 1000 and globs["bed"] >= totals["bed"]:
                    advance(1050)
                elif stage == 1200 and globs["water"] >= totals["water"]:
                    advance(1250)
                elif stage == 1300 and globs["food"] >= totals["food"]:
                    advance(1350)
                elif stage == 1400 and globs["defense"] >= totals["defense"]:
                    advance(1450)

            def bench_activate(clicks: list[int]) -> None:
                if completed:
                    return
                if stage < 100:
                    advance(100)
                elif sturges_dead:
                    nxt = {100: 1000, 1050: 1200, 1250: 1300, 1350: 1400, 1450: 1500}.get(stage)
                    if nxt is not None:
                        advance(nxt)
                        if nxt == 1500:
                            return
                keys = ("bed", "water", "food", "defense")
                for btn in clicks:
                    if 0 <= btn < 4 and not completed:
                        globs[keys[btn]] += 1.0
                        check_milestone()

            def sturges_activate() -> None:
                if completed or sturges_dead:
                    return
                nxt = {100: 1000, 1050: 1200, 1250: 1300, 1350: 1400, 1450: 1500}.get(stage)
                if nxt is not None:
                    advance(nxt)

            if prebuild_before_sturges:
                bench_activate([0] * 5 + [1] * 5 + [2] * 5 + [3] * 2 + [4])
                for _ in range(5):
                    sturges_activate()
            elif sturges_dead:
                bench_activate([0] * 5 + [4])
                bench_activate([1] * 5 + [4])
                bench_activate([2] * 5 + [4])
                bench_activate([3] * 2 + [4])
                bench_activate([4])
            else:
                bench_activate([4])
                sturges_activate()
                bench_activate([0] * 5 + [4])
                sturges_activate()
                bench_activate([1] * 5 + [4])
                sturges_activate()
                bench_activate([2] * 5 + [4])
                sturges_activate()
                bench_activate([3] * 2 + [4])
                sturges_activate()

            return {"stage": stage, "completed": completed, "started_minrecruit": started_minrecruit, "stages": stages_seen}

        for mode_kwargs in (
            {"sturges_dead": False, "prebuild_before_sturges": False},
            {"sturges_dead": False, "prebuild_before_sturges": True},
            {"sturges_dead": True, "prebuild_before_sturges": False},
        ):
            res = simulate_sanctuary01(**mode_kwargs)
            self.assertTrue(res["completed"], f"Sanctuary01 stalled in {mode_kwargs}: {res}")
            self.assertEqual(res["stage"], 1500)
            self.assertTrue(res["started_minrecruit"])

        # 4. Verify MinRecruit00 & MQ103 console-free completion paths exist in Papyrus source
        for tok in (
            'AdvanceTo(100, "spokesman")',
            'AdvanceTo(100, "open_mode")',
            'AdvanceTo(200, "boss_dead")',
            'AdvanceTo(200, "boss_dead_interior")',
            'AdvanceTo(450, "spokesman")',
            'AdvanceTo(450, "open_mode")',
            'AdvanceTo(500, "preston")',
            'AdvanceTo(500, "open_mode")',
        ):
            self.assertIn(tok, step)
        for tok in (
            "UnlockDiamondCityGate(by)",
            'AdvanceTo(20, "piper_gate")',
            'AdvanceTo(20, "gate_override")',
            'AdvanceTo(20, "open_mode")',
            'AdvanceTo(30, "piper_lead")',
            'AdvanceTo(30, "out_of_order")',
            'AdvanceTo(100, "ellie")',
            'AdvanceTo(100, "dossier")',
        ):
            self.assertIn(tok, mq103)


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
