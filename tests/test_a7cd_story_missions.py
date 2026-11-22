"""Offline regression & W6 state-machine tests for Lane A Push 6 Act II missions:
FO4SF_MQ106 (Reunions, 0x000AD0), FO4SF_MQ203 (Dangerous Minds, 0x000AF0),
FO4SF_MQ204 (The Glowing Sea, 0x000B10), and FO4SF_MQ206 (The Molecular Level, 0x000B30).
"""
from __future__ import annotations

import re
import sys
import unittest
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "src"), str(ROOT / "scripts" / "mission"), str(ROOT / "scripts" / "ui")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import make_mission  # noqa: E402
import pipboy_mission_catalog as pmc  # noqa: E402
from fo4sf.core import cross_plugin_check as cpc  # noqa: E402

CS_A7CD = ROOT / "dotnet" / "Mission" / "NextStoryMissionsA7cd.cs"
CS_A7 = ROOT / "dotnet" / "Mission" / "NextStoryMissionsA7.cs"
CS_PROGRAM = ROOT / "dotnet" / "Mission" / "Program.cs"
PSC_MQ105 = ROOT / "scripts" / "mission" / "FO4SF_MQ105Quest.psc"
PSC_MQ106 = ROOT / "scripts" / "mission" / "FO4SF_MQ106Quest.psc"
PSC_MQ203 = ROOT / "scripts" / "mission" / "FO4SF_MQ203Quest.psc"
PSC_MQ204 = ROOT / "scripts" / "mission" / "FO4SF_MQ204Quest.psc"
PSC_MQ206 = ROOT / "scripts" / "mission" / "FO4SF_MQ206Quest.psc"
PSC_MIN00 = ROOT / "scripts" / "mission" / "FO4SF_Min00Quest.psc"
MAIN_CPP = ROOT / "sfse" / "FO4SFPipboyMenu" / "src" / "main.cpp"
MAP_CPP = ROOT / "sfse" / "FO4SFPipboyMenu" / "src" / "pipboy_map.cpp"

DRIVE_PATH_RX = re.compile(r"\b[A-Za-z]:[\\/]")
FORBIDDEN_MOD_PATTERNS = (
    re.compile(r"\b" + ("UF" + "O4P") + r"\b", re.I),
    re.compile(r"\b" + ("Unofficial" + r"\s+" + "Fallout") + r"\b", re.I),
    re.compile(r"\b" + ("Yuki" + "chigai" + "|" + "Y" + "UP") + r"\b", re.I),
    re.compile(r"\b" + ("GAM" + "MA") + r"\b", re.I),
    re.compile(r"\b" + ("Buff" + "out") + r"\b", re.I),
)


def _extract_cs_uint_consts(text: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for block in re.finditer(r"\bpublic\s+const\s+uint\s+([^;]+);", text, re.S):
        for part in block.group(1).split(","):
            m = re.match(r"\s*(\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)", part.strip())
            if m:
                out[m.group(1)] = int(m.group(2), 0)
    return out


def _extract_script_props_cs(text: str, script_var: str) -> set[str]:
    return set(re.findall(rf'{script_var}\.Properties\.Add\(ObjProp\("([A-Za-z_]\w*)"', text))


def _extract_script_props_psc(text: str) -> set[str]:
    clean = re.sub(r"\{[^}]*\}", "", text)
    return set(re.findall(r"^\s*[A-Za-z_]\w*(?:\[\])?\s+Property\s+([A-Za-z_]\w*)\b", clean, re.M))


def _simulate_graph(stages, start, finals, edges, open_mode=False):
    adj = {s: [] for s in stages}
    for src, dst, npc_gated in edges:
        if open_mode and npc_gated:
            continue
        adj.setdefault(src, []).append(dst)
    seen = {start}
    q = deque([start])
    while q:
        cur = q.popleft()
        for nxt in adj.get(cur, ()):
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    unreachable = sorted(s for s in stages if s not in seen)
    stuck = []
    for s in stages:
        if s in finals:
            continue
        sub_seen = {s}
        sq = deque([s])
        ok = False
        while sq:
            cur = sq.popleft()
            if cur in finals:
                ok = True
                break
            for nxt in adj.get(cur, ()):
                if nxt not in sub_seen:
                    sub_seen.add(nxt)
                    sq.append(nxt)
        if not ok:
            stuck.append(s)
    return unreachable, stuck


ACT2_STATE_GRAPHS = {
    "FO4SF_MQ106": {
        "stages": (10, 50, 75, 100, 125, 150, 200, 500),
        "start": 10,
        "finals": {500},
        "edges": (
            (10, 50, True),    # Dogmeat reaches Fort Hagen
            (10, 50, False),   # REUN-01 direct walk to Fort Hagen
            (50, 75, False),   # Enter FortHagen01 via 0D door
            (75, 100, False),  # Enter FortHagen02 Command Center
            (100, 125, True),  # Confront Kellogg
            (100, 125, False), # REUN-03 pre-attack Kellogg
            (125, 150, False), # Defeat Kellogg / recover CyberBrain + Password
            (150, 200, False), # REUN-04 exterior roof load -> PrydwenArrived=1
            (200, 500, True),  # Debrief with Nick
            (200, 500, False), # REUN-05 Open-Mode dossier or direct Memory Den arrival
        ),
    },
    "FO4SF_MQ203": {
        "stages": (5, 10, 100, 110, 120, 300),
        "start": 5,
        "finals": {300},
        "edges": (
            (5, 10, False),    # Arrive Memory Den with CyberBrain
            (10, 100, True),   # Talk to Doctor Amari
            (10, 100, False),  # MIND-01 Open-Mode LoungerProxyActi self-scan when Amari dead
            (100, 110, False), # Enter Memory Lounger -> MoveTo MQ203KelloggsBrain
            (110, 120, True),  # Memory walk + Virgil file
            (110, 120, False), # MIND-02 bridge skip / autonomous scan
            (120, 300, True),  # Doctor Amari debrief
            (120, 300, False), # MIND-05 LabTerminal or direct Glowing Sea arrival
        ),
    },
    "FO4SF_MQ204": {
        "stages": (10, 15, 20, 50, 200),
        "start": 10,
        "finals": {200},
        "edges": (
            (10, 15, False),   # Enter Glowing Sea
            (15, 20, True),    # Speak with Mother Isolde at Crater
            (15, 20, False),   # Open-Mode dead-Isolde VirgilNote or direct Rocky Cave arrival
            (20, 50, True),    # Speak with Virgil inside Rocky Cave
            (20, 50, False),   # Open-Mode dead-Virgil LabTerminalProxyActi
            (50, 200, False),  # Arm MQ206
        ),
    },
    "FO4SF_MQ206": {
        "stages": (10, 20, 65, 100, 200, 300, 350, 600, 700, 1000, 1200),
        "start": 10,
        "finals": {1200},
        "edges": (
            (10, 20, False),    # Defeat Courser Z2-47 -> CourserChip
            (20, 100, True),    # Tinker Tom decodes chip
            (20, 65, False),    # Stage 65 Open-Mode Tinker Tom dead
            (65, 100, False),   # ScannerProxyActi self-decode -> Holotape
            (100, 200, True),   # Virgil grants SignalInterceptorPlans
            (100, 200, False),  # Open-Mode dead-Virgil plans fallback
            (200, 300, True),   # Choose Minutemen / Railroad / BoS ally
            (200, 300, False),  # Solo Open-Mode Self-Build
            (300, 350, False),  # Build 4 Signal Interceptor modules
            (350, 600, False),  # Unified +27 power grid
            (600, 700, False),  # ReadyToTeleport=1
            (700, 1000, False), # ConsoleProxyActi relay fire
            (1000, 1200, False),# Arrive FO4Port_InstituteConcourse -> MQ207Armed=1
        ),
    },
}

W6_BREAK_IT_BATCHES = (
    ("act2_reun_ooo", "MQ106", "out_of_order", "coc fort_hagen_roof; player.moveto 0x0547B0"),
    ("act2_reun_dead", "MQ106", "giver_dead", "kill nick; use TerminalProxyActi; walk to Memory Den"),
    ("act2_reun_reload", "MQ106", "save_reload", "save/reload at stages 50, 100, 150, 200"),
    ("act2_reun_away", "MQ106", "fast_travel_away", "travel to Sanctuary mid-Fort Hagen and return"),
    ("act2_mind_ooo", "MQ203", "out_of_order", "enter Memory Den directly with CyberBrain"),
    ("act2_mind_dead", "MQ203", "giver_dead", "kill DoctorAmari; use LoungerProxyActi autonomous scan"),
    ("act2_mind_reload", "MQ203", "save_reload", "save/reload at stages 10, 100, 110, 120"),
    ("act2_mind_away", "MQ203", "fast_travel_away", "travel to Diamond City before lounger and return"),
    ("act2_glow_ooo", "MQ204", "out_of_order", "walk straight to Rocky Cave skipping Crater of Atom"),
    ("act2_glow_dead", "MQ204", "giver_dead", "kill MotherIsolde + Virgil; read VirgilNote + LabTerminalProxyActi"),
    ("act2_glow_reload", "MQ204", "save_reload", "save/reload inside Glowing Sea Track 1 vs Track 2 rads"),
    ("act2_glow_away", "MQ204", "fast_travel_away", "fast-travel out of SW zone; verify GlowingSeaRadsActive=0"),
    ("act2_mol_ooo", "MQ206", "out_of_order", "defeat Courser Z2-47 before MQ204 handoff"),
    ("act2_mol_dead", "MQ206", "giver_dead", "kill TinkerTom + Virgil + all faction leads; Stage 65 + Solo workbench"),
    ("act2_mol_reload", "MQ206", "save_reload", "save/reload between modules 1..4 and +27 power gate"),
    ("act2_mol_away", "MQ206", "fast_travel_away", "switch faction ally before Stage 1000 relay fire"),
)


class A7cdStoryMissionsTests(unittest.TestCase):
    def test_formid_disjointness_uniqueness_and_pipboy_window(self) -> None:
        a7_consts = _extract_cs_uint_consts(CS_A7.read_text(encoding="utf-8"))
        a7cd_consts = _extract_cs_uint_consts(CS_A7CD.read_text(encoding="utf-8"))

        a7_max = a7_consts["MaxAllocatedId"]
        a7cd_max = a7cd_consts["MaxAllocatedId"]
        a7cd_ids = {k: v for k, v in a7cd_consts.items() if k != "MaxAllocatedId"}

        self.assertGreaterEqual(len(a7cd_ids), 55)
        self.assertEqual(len(set(a7cd_ids.values())), len(a7cd_ids), "Duplicate FormID in NextStoryMissionsA7cd.cs")
        for name, fid in a7cd_ids.items():
            self.assertGreaterEqual(fid, a7_max, f"{name} 0x{fid:X} overlaps A7 (< 0x{a7_max:X})")
            self.assertLess(fid, a7cd_max, f"{name} 0x{fid:X} >= MaxAllocatedId 0x{a7cd_max:X}")
            self.assertLessEqual(fid, 0x000BFF, f"{name} 0x{fid:X} exceeds extended Pip-Boy scan ceiling 0xBFF")

        self.assertEqual(a7cd_consts["Mq106QuestId"], 0x000AD0)
        self.assertEqual(a7cd_consts["Mq203QuestId"], 0x000AF0)
        self.assertEqual(a7cd_consts["Mq204QuestId"], 0x000B10)
        self.assertEqual(a7cd_consts["Mq206QuestId"], 0x000B30)

    def test_cs_to_psc_vmad_property_parity_for_all_four_act2_quests(self) -> None:
        cs_text = CS_A7CD.read_text(encoding="utf-8")
        pairs = (
            ("mq106Script", PSC_MQ106),
            ("mq203Script", PSC_MQ203),
            ("mq204Script", PSC_MQ204),
            ("mq206Script", PSC_MQ206),
        )
        for var_name, psc_path in pairs:
            cs_props = _extract_script_props_cs(cs_text, var_name)
            psc_props = _extract_script_props_psc(psc_path.read_text(encoding="utf-8"))
            self.assertTrue(cs_props, f"{var_name} has no CS properties")
            self.assertEqual(cs_props, psc_props, f"VMAD mismatch for {psc_path.name}")

    def test_t1_and_b1_b2_b4_invariants_across_all_four_scripts_and_cs(self) -> None:
        cs_text = CS_A7CD.read_text(encoding="utf-8")
        # B1/B4 quest flags & proxy model hygiene
        self.assertIn("AllowRepeatedStages | SF.Quest.Flag.DisplaysInHud | SF.Quest.Flag.RunOnce", cs_text)
        self.assertIn("ProxyActiModel = Mission.CodsworthTalkActiModel", cs_text)
        self.assertNotIn('AssetLink<StarfieldModelAssetType>("Meshes\\\\', cs_text)
        # Hostile bosses & female NPCs
        self.assertIn('CloneHostileBossNpc(mod, modKey, KelloggNpcId, "FO4_Kellogg"', cs_text)
        self.assertIn('CloneHostileBossNpc(mod, modKey, CourserZ247NpcId, "FO4_CourserZ247"', cs_text)
        for fem_id in ("DoctorAmariNpcId", "MotherIsoldeNpcId", "DesdemonaNpcId", "ProctorIngramNpcId"):
            self.assertRegex(cs_text, re.compile(rf"{fem_id}[^;]*female:\s*true", re.S), f"{fem_id} must set female: true")

        for psc_path in (PSC_MQ106, PSC_MQ203, PSC_MQ204, PSC_MQ206):
            text = psc_path.read_text(encoding="utf-8")
            for required_token in (
                "ActiveCorePlugin()",
                "ResolveCommonwealthWorld()",
                "IsCommonwealthExterior(",
                "IsPlayerStableAt(",
                "EffectiveStage()",
                "OnPlayerLoadGame",
                "talkSessionId",
                "SetRestrained(False)",
                "IsWarfareMode()",
            ):
                self.assertIn(required_token, text, f"{psc_path.name} missing T1 invariant {required_token}")
            self.assertNotIn("Debug.Notification(", text, f"{psc_path.name} must not call ungated Debug.Notification")

        # MQ204 Track 1 vs Track 2 rads + Virgil PA Targeting HUD guard
        mq204_text = PSC_MQ204.read_text(encoding="utf-8")
        self.assertIn('Game.IsPluginInstalled(RadsPlugin)', mq204_text)
        self.assertIn("0x000800", mq204_text)
        self.assertIn("0x000804", mq204_text)
        self.assertIn("IgnoreFriendlyHits(True)", mq204_text)
        self.assertIn("StopCombat()", mq204_text)

        # Console-free chaining across Act I -> Act II & binary-verified persistent (0x400) interior arrival/return markers
        self.assertIn("0x000AD0", PSC_MQ105.read_text(encoding="utf-8"))
        mq106_text = PSC_MQ106.read_text(encoding="utf-8")
        self.assertIn("0x000AF0", mq106_text)
        self.assertIn("TryBindFortHagenRoofDoor()", mq106_text)

        mq203_text = PSC_MQ203.read_text(encoding="utf-8")
        self.assertIn("0x000B10", mq203_text)
        self.assertIn("0x00F2D3", mq203_text)
        self.assertIn("0x00F23D", mq203_text)
        self.assertIn("ReturnPlayerFromKelloggBrain(", mq203_text)
        self.assertNotIn("0x00F23F", mq203_text)

        self.assertIn("0x000B30", mq204_text)

        mq206_text = PSC_MQ206.read_text(encoding="utf-8")
        self.assertIn("0x03D252", mq206_text)
        self.assertIn("0x03D52E", mq206_text)
        self.assertIn("TryBindSanctuaryBench(", mq206_text)
        self.assertIn("FindClosestReferenceOfType(", mq206_text)
        self.assertNotIn("0x03D253", mq206_text)

        min00_text = PSC_MIN00.read_text(encoding="utf-8")
        self.assertIn("CheckA7cdProximityStarts(player)", min00_text)
        for flag in ("mq106ProxAttempted", "mq203ProxAttempted", "mq204ProxAttempted", "mq206ProxAttempted"):
            self.assertIn(flag, min00_text)

    def test_program_wiring_make_mission_and_cross_plugin_catalog(self) -> None:
        prog_text = CS_PROGRAM.read_text(encoding="utf-8")
        self.assertIn("NextStoryMissionsA7cd.PopulateA7cdMissions(", prog_text)
        self.assertIn("NextStoryMissionsA7cd.CheckA7cdMissions(", prog_text)
        self.assertIn("NextStoryMissionsA7cd.IsA7cdActorRefId(", prog_text)
        self.assertIn("NextStoryMissionsA7cd.MaxAllocatedId", prog_text)

        self.assertEqual(len(make_mission.ALL_SCRIPTS), 12)
        for scr in ("FO4SF_MQ106Quest", "FO4SF_MQ203Quest", "FO4SF_MQ204Quest", "FO4SF_MQ206Quest"):
            self.assertIn(scr, make_mission.ALL_SCRIPTS)

        sample_log = [
            "FO4SF_MISSION rt=1.0 mq106 stage 10 by=Trigger",
            "FO4SF_MISSION rt=2.0 mq106 complete stage=500 mq203_armed=1 mq203_started=True prydwen=1 by=talk",
            "FO4SF_MISSION rt=3.0 mq203 stage 5 by=Trigger",
            "FO4SF_MISSION rt=4.0 mq203 complete stage=300 memories=1 mq204_armed=1 mq204_started=True by=talk",
            "FO4SF_MISSION rt=5.0 mq204 stage 15 by=Trigger",
            "FO4SF_MISSION rt=6.0 mq204 complete stage=200 mq206_armed=1 mq206_started=True rads_plugin=False by=talk",
            "FO4SF_MISSION rt=7.0 mq206 stage 10 by=Trigger",
            "FO4SF_MISSION rt=8.0 mq206 complete stage=1200 faction=1 mq207_armed=1 institute_cell=0x03D252 by=relay",
        ]
        summary = make_mission.summarize(sample_log)
        self.assertEqual(summary["mq106_stages"], [10])
        self.assertIn("mq203_armed=1", summary["mq106_complete"])
        self.assertEqual(summary["mq203_stages"], [5])
        self.assertIn("mq204_armed=1", summary["mq203_complete"])
        self.assertEqual(summary["mq204_stages"], [15])
        self.assertIn("mq206_armed=1", summary["mq204_complete"])
        self.assertEqual(summary["mq206_stages"], [10])
        self.assertIn("mq207_armed=1", summary["mq206_complete"])

        catalog, dup_errors = cpc.build_writer_catalog(str(ROOT))
        self.assertEqual(dup_errors, [])
        mission_cat = catalog["FO4SFMission.esm"]
        a7cd_consts = _extract_cs_uint_consts(CS_A7CD.read_text(encoding="utf-8"))
        for name, fid in a7cd_consts.items():
            if name == "MaxAllocatedId":
                continue
            self.assertIn(fid, mission_cat, f"FO4SFMission.esm:0x{fid:04X} ({name}) missing from cross_plugin_check.py")

    def test_pipboy_catalog_and_scan_ceiling_cover_act2(self) -> None:
        self.assertIn("for (std::uint32_t localId = 0x800; localId <= 0xBFF; ++localId)", MAIN_CPP.read_text(encoding="utf-8"))
        map_text = MAP_CPP.read_text(encoding="utf-8")
        keys = {(r.plugin, r.quest_local_id, r.objective_num) for r in pmc.CANONICAL_MISSION_OBJECTIVES}
        for qid, oid in (
            (0x000A80, 10),
            (0x000AB0, 10),
            (0x000AB0, 80),
            (0x000AD0, 10),
            (0x000AD0, 100),
            (0x000AD0, 200),
            (0x000AF0, 10),
            (0x000AF0, 120),
            (0x000B10, 15),
            (0x000B10, 20),
            (0x000B30, 10),
            (0x000B30, 20),
            (0x000B30, 30),
            (0x000B30, 50),
            (0x000B30, 100),
            (0x000B30, 150),
        ):
            self.assertIn(("FO4SFMission.esm", qid, oid), keys)
            self.assertIn(f"0x{qid:06X}u, {oid}u", map_text)

    def test_w6_normal_and_open_mode_simulations_and_negative_mutations(self) -> None:
        for qname, spec in ACT2_STATE_GRAPHS.items():
            unr_n, stk_n = _simulate_graph(spec["stages"], spec["start"], spec["finals"], spec["edges"], open_mode=False)
            self.assertEqual((unr_n, stk_n), ([], []), f"{qname} Normal mode failed")
            unr_o, stk_o = _simulate_graph(spec["stages"], spec["start"], spec["finals"], spec["edges"], open_mode=True)
            self.assertEqual((unr_o, stk_o), ([], []), f"{qname} Open-Mode failed")

        # Negative mutation: removing MQ206 Stage 65 self-decode edge breaks Open-Mode while Normal still passes
        mq206 = ACT2_STATE_GRAPHS["FO4SF_MQ206"]
        mut_edges = [e for e in mq206["edges"] if not (e[0] == 20 and e[1] == 65)]
        unr_n, stk_n = _simulate_graph(mq206["stages"], mq206["start"], mq206["finals"], mut_edges, open_mode=False)
        self.assertEqual(stk_n, [])
        unr_o, stk_o = _simulate_graph(mq206["stages"], mq206["start"], mq206["finals"], mut_edges, open_mode=True)
        self.assertIn(20, stk_o)

    def test_w6_break_it_batches_p3_safe_and_hygiene(self) -> None:
        self.assertEqual(len(W6_BREAK_IT_BATCHES), 16)
        self.assertEqual(len({b[0] for b in W6_BREAK_IT_BATCHES}), 16)
        for bid, _q, _axis, cmd in W6_BREAK_IT_BATCHES:
            self.assertNotRegex(cmd, r"\b[MNV]\b", f"Batch {bid} violates P3")

        for path in (CS_A7CD, PSC_MQ106, PSC_MQ203, PSC_MQ204, PSC_MQ206):
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(DRIVE_PATH_RX.search(text), f"Drive leak in {path.name}")
            for pat in FORBIDDEN_MOD_PATTERNS:
                self.assertIsNone(pat.search(text), f"Forbidden mod name in {path.name}")


if __name__ == "__main__":
    unittest.main()
