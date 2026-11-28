"""Offline regression tests for Lane A A5 — Pip-Boy mission readiness.

Verifies all four A5 pillars offline:
  1. DATA / Quests: live objectives for every converted Fallout 4 mission
     (FO4SF_NewGame, FO4SF_Codsworth01, FO4SF_Min00, FO4SF_Sanctuary01) plus
     0x800..0x9FF extensible scan & silent background helper filtering.
  2. MAP: active quest objective markers pushed into WorldMapMarkers with
     exact Commonwealth coordinates, FO4SFPipboyQuestObjectives.tsv extensible
     override/A4 hooks, and ShowQuestOnMap -> RequestCenterQuest centering.
  3. INV: 13-plugin player-bundle item form types (WEAP/ARMO/ALCH/AMMO/MISC/IRES)
     and opt-in --a5-playable preset (preserving safe defaults when omitted).
  4. Arm raise: Arm=0 shipped default preserved, plus R10 non-blocking watchdog
     (step=arm_watchdog_open) and second-press skip-wait (step=arm_raise_skip_wait).
"""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "src"), str(ROOT / "scripts" / "ui")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import make_pipboy_stage_ini as stage_ini  # noqa: E402
import pipboy_mission_catalog as cat  # noqa: E402
from tests.test_pipboy_stage_ini import _build_shell_swf  # noqa: E402

MAIN_CPP = ROOT / "sfse" / "FO4SFPipboyMenu" / "src" / "main.cpp"
MAP_H = ROOT / "sfse" / "FO4SFPipboyMenu" / "src" / "pipboy_map.h"
MAP_CPP = ROOT / "sfse" / "FO4SFPipboyMenu" / "src" / "pipboy_map.cpp"
SHIPPED_INI = ROOT / "sfse" / "FO4SFPipboyMenu" / "FO4SFPipboyMenu.ini"


class A5PipboyMissionTests(unittest.TestCase):
    def test_canonical_mission_catalog_matches_cpp_seed_and_commonwealth_bounds(self) -> None:
        map_cpp = MAP_CPP.read_text(encoding="utf-8")
        seed_block = map_cpp[
            map_cpp.index("void SeedDefaultQuestObjectiveCatalog(") : map_cpp.index("void LoadQuestObjectiveCatalog(")
        ]

        tsv = cat.render_quest_objectives_tsv()
        parsed = cat.parse_quest_objectives_tsv(tsv)
        self.assertEqual(parsed, list(cat.CANONICAL_MISSION_OBJECTIVES))

        # Every converted Track-1 mission objective in Python matches the C++ built-in seed
        for row in parsed:
            self.assertIn(f'"{row.plugin}"', seed_block)
            self.assertIn(f"0x{row.quest_local_id:06X}u", seed_block)
            self.assertIn(f"{row.objective_num}u", seed_block)
            self.assertIn(f"{row.x_fo4:.2f}", seed_block)
            self.assertIn(f"{row.y_fo4:.2f}", seed_block)
            self.assertIn(f'"{row.location_label}"', seed_block)
            self.assertIn(f'"{row.fallback_text}"', seed_block)

        # Must cover Out of Time, Codsworth01, When Freedom Calls (10/85/86), Sanctuary01,
        # and A4 reserved FormIDs (0x000A20 The First Step, 0x000A50 Jewel of the Commonwealth)
        keys = {(r.plugin, r.quest_local_id, r.objective_num) for r in parsed}
        for req in (
            ("FO4SFNewGame.esm", 0x000800, 10),
            ("FO4SFMission.esm", 0x000816, 10),
            ("FO4SFMission.esm", 0x000800, 10),
            ("FO4SFMission.esm", 0x000800, 85),
            ("FO4SFMission.esm", 0x000800, 86),
            ("FO4SFMission.esm", 0x000817, 10),
            ("FO4SFMission.esm", 0x000A20, 10),
            ("FO4SFMission.esm", 0x000A20, 20),
            ("FO4SFMission.esm", 0x000A50, 10),
        ):
            self.assertIn(req, keys)
        for stale in (20, 30, 35):
            self.assertNotIn(("FO4SFMission.esm", 0x000800, stale), keys)

    def test_mission_catalog_extensible_for_a4_and_refuses_bad_paths_or_bounds(self) -> None:
        tenpines_x, tenpines_y = cat.A4_KNOWN_LANDMARK_COORDS["Tenpines Bluff"]
        dc_x, dc_y = cat.A4_KNOWN_LANDMARK_COORDS["Diamond City"]
        extended = list(cat.CANONICAL_MISSION_OBJECTIVES) + [
            cat.MissionObjectiveRow(
                plugin="FO4SFMission.esm",
                quest_local_id=0x000910,
                objective_num=10,
                x_fo4=tenpines_x,
                y_fo4=tenpines_y,
                location_label="Tenpines Bluff",
                fallback_text="Talk to the settlers at Tenpines Bluff",
            ),
            cat.MissionObjectiveRow(
                plugin="FO4SFMission.esm",
                quest_local_id=0x000920,
                objective_num=10,
                x_fo4=dc_x,
                y_fo4=dc_y,
                location_label="Diamond City",
                fallback_text="Go to Diamond City",
            ),
        ]
        with tempfile.TemporaryDirectory() as td:
            out_p = Path(td) / cat.QUEST_OBJECTIVES_TSV_NAME
            written = cat.write_quest_objectives_tsv(out_p, extended)
            self.assertTrue(written.is_file())
            reloaded = cat.parse_quest_objectives_tsv(written.read_text(encoding="utf-8"))
            self.assertEqual(reloaded, extended)

        # Out-of-bounds Commonwealth coordinates must be refused
        with self.assertRaises(cat.MissionCatalogError):
            cat.validate_row(
                cat.MissionObjectiveRow(
                    plugin="FO4SFMission.esm",
                    quest_local_id=0x000930,
                    objective_num=10,
                    x_fo4=999999.0,
                    y_fo4=0.0,
                    location_label="Nowhere",
                    fallback_text="Invalid",
                )
            )

        # Writing inside Git worktree must be refused (Rule R4)
        with self.assertRaises(cat.MissionCatalogError):
            cat.write_quest_objectives_tsv(ROOT / "FO4SFPipboyQuestObjectives.tsv")

    def test_quests_collection_scan_filtering_and_objective_marker_handoff(self) -> None:
        main_cpp = MAIN_CPP.read_text(encoding="utf-8")
        collect_fn = main_cpp[
            main_cpp.index("void CollectQuestAndStatsMainThread(") : main_cpp.index("void LogCoreValueResolve(")
        ]

        # Extensible 0x800..0xBFF quest scan window for current + A4 + A7 + Act II (0x000AD0..0x000B30) missions
        self.assertIn("for (std::uint32_t localId = 0x800; localId <= 0xBFF; ++localId)", collect_fn)
        # Silent background controller quests filtered when they lack display name and objectives
        self.assertIn("const bool hasDisplayName = !qName.empty();", collect_fn)
        self.assertIn('qName.find("Keeper") != std::string::npos', collect_fn)
        self.assertIn('qName.find("COMPreston") != std::string::npos', collect_fn)
        # Catalog fallback display text & active-first objective selection
        self.assertIn("PipboyMap::LookupQuestObjectiveCatalog(a_pluginName, a_localId, num, cat)", collect_fn)
        self.assertIn("PipboyMap::SetActiveQuestObjectives(std::move(activeQuestMarkers));", collect_fn)
        self.assertIn("step=quests_collect n={} active={} completed={} objectives={} quest_markers={}", collect_fn)

        # MAP gets synced quest objective markers even when InvDataAnswers=0
        vitals_fn = main_cpp[
            main_cpp.index("void CollectShellVitalsMainThread(") : main_cpp.index("struct RawObjectInstance")
        ]
        self.assertIn("else if (PipboyMap::Enabled())", vitals_fn)

    def test_map_quest_objective_markers_and_show_quest_on_map_centering(self) -> None:
        map_h = MAP_H.read_text(encoding="utf-8")
        map_cpp = MAP_CPP.read_text(encoding="utf-8")
        main_cpp = MAIN_CPP.read_text(encoding="utf-8")

        for sym in (
            "struct QuestObjectiveCatalogEntry",
            "struct QuestObjectiveMarker",
            "LookupQuestObjectiveCatalog(",
            "SetActiveQuestObjectives(",
            "RequestCenterQuest(",
        ):
            self.assertIn(sym, map_h)

        self.assertIn("kQuestTargetMarkerType = kPlayerSetMarkerType", map_cpp)
        self.assertIn("kQuestMarkerIdBase = 0xF00000u", map_cpp)
        self.assertIn('kQuestObjectivesStoreDefault = "FO4SFPipboyQuestObjectives.tsv"', map_cpp)
        self.assertIn('qEntry.SetMember("isQuestTarget", RE::Scaleform::GFx::Value(true))', map_cpp)
        self.assertIn('qEntry.SetMember("questFormID", RE::Scaleform::GFx::Value(qm.questFormId))', map_cpp)
        self.assertIn('qEntry.SetMember("objectiveIndex",', map_cpp)
        self.assertIn("step=map_quest_markers n={} first_quest={:08X} obj={} x={:.1f} y={:.1f}", map_cpp)
        self.assertIn("step=map_center idx={} quest={:08X} called={}", map_cpp)
        self.assertIn("LoadQuestObjectiveCatalog(a_dir / kQuestObjectivesStoreDefault);", map_cpp)

        # ShowQuestOnMap in main.cpp routes through RequestCenterQuest first
        show_map_block = main_cpp[
            main_cpp.index('if (_name == "ShowQuestOnMap"'):main_cpp.index('if (_name == "ToggleRadioStationActiveStatus")')
        ]
        self.assertIn("PipboyMap::RequestCenterQuest(", show_map_block)

    def test_inventory_page_form_types_and_a5_playable_stage_ini_preset(self) -> None:
        main_cpp = MAIN_CPP.read_text(encoding="utf-8")
        inv_filter = main_cpp[
            main_cpp.index("std::uint32_t InvFilterFlagForForm(") : main_cpp.index("std::string ReadObjectiveDisplayText(")
        ]
        # 13-plugin player bundle items: WEAP (0x30 pistol), ARMO (0x22 Pip-Boy/suit),
        # ALCH (0x36 Stimpak), AMMO (0x31 rounds), MISC (0x28), IRES (0x9F junk)
        for token in ("case 0x30:", "case 0x22:", "case 0x36:", "case 0x31:", "case 0x28:", "case 0x9F:"):
            self.assertIn(token, inv_filter)

        # Stage INI: default stays safe (InvDataAnswers=0, Arm=0), while --a5-playable turns on
        # PopulateInCall=1, StatActions=1, InvDataAnswers=1 and stages FO4SFPipboyQuestObjectives.tsv
        with tempfile.TemporaryDirectory() as td:
            stage = Path(td)
            iface = stage / "Data" / "Interface"
            iface.mkdir(parents=True)
            (iface / "FO4SF_Fo4Shell.swf").write_bytes(_build_shell_swf())

            res_default = stage_ini.generate_stage_ini(stage)
            ini_default = Path(str(res_default["ini_path"])).read_text(encoding="utf-8")
            self.assertIn("InvDataAnswers=0", ini_default)
            self.assertIn("Arm=1", ini_default)
            self.assertFalse((stage / "SFSE" / "Plugins" / cat.QUEST_OBJECTIVES_TSV_NAME).exists())

            res_a5 = stage_ini.generate_stage_ini(stage, a5_playable=True)
            ini_a5 = Path(str(res_a5["ini_path"])).read_text(encoding="utf-8")
            self.assertIn("PopulateInCall=1", ini_a5)
            self.assertIn("StatActions=1", ini_a5)
            self.assertIn("InvDataAnswers=1", ini_a5)
            self.assertIn("Arm=1", ini_a5)  # Arm=1 default (G12b)
            self.assertIn("MapBlockStarMap=0", ini_a5)
            tsv_path = Path(str(res_a5["quest_catalog_path"]))
            self.assertTrue(tsv_path.is_file())
            self.assertEqual(len(cat.parse_quest_objectives_tsv(tsv_path.read_text(encoding="utf-8"))), len(cat.CANONICAL_MISSION_OBJECTIVES))

    def test_arm_raise_is_opt_in_and_never_blocks_pipboy_open(self) -> None:
        shipped_ini = SHIPPED_INI.read_text(encoding="utf-8")
        main_cpp = MAIN_CPP.read_text(encoding="utf-8")

        self.assertIn("\nArm=1\n", shipped_ini)
        arm_key_fn = main_cpp[main_cpp.index("void ArmKey(") : main_cpp.index("void ArmTick(")]
        arm_tick_fn = main_cpp[main_cpp.index("void ArmTick(") : main_cpp.index("std::uint32_t KeyThread(")]
        arm_raise_fn = main_cpp[main_cpp.index("void ArmRaise(") : main_cpp.index("void ArmLower(")]

        # Refused/third-person/weapon-drawn raise opens immediately (showLeadMs = 0)
        self.assertIn('const auto showLeadMs = (outcome == "1") ? g_armRaiseMs : 0u;', arm_raise_fn)
        # Second press while raising skips remaining wait cleanly
        self.assertIn("step=arm_raise_skip_wait n={} t_ms={}", arm_key_fn)
        # Hard watchdog guarantees Arm=1 can never block opening the Pip-Boy
        self.assertIn("kArmWatchdogSlackMs", arm_tick_fn)
        self.assertIn("step=arm_watchdog_open n={} elapsed_ms={}", arm_tick_fn)

    def test_cpp_sfse_concurrency_arm_watchdog_and_map_invariants(self) -> None:
        """Verify all T3 C++ SFSE concurrency, Arm watchdog, and Map/Quest invariants."""
        main_cpp = MAIN_CPP.read_text(encoding="utf-8")
        map_cpp = MAP_CPP.read_text(encoding="utf-8")

        # 1. Arm watchdog premature fire & stale double-open fencing
        self.assertIn("std::atomic<std::uint32_t>               g_armPendingOpenN{ 0 };", main_cpp)
        arm_key_fn = main_cpp[main_cpp.index("void ArmKey(") : main_cpp.index("void ArmTick(")]
        self.assertLess(arm_key_fn.index("g_armPressAt = at;"), arm_key_fn.index("g_armDispatching = true;\n\t\t\t\tg_task->AddTask([n, at]() {"))
        self.assertIn("g_armPendingOpenN = n;", arm_key_fn)
        arm_raise_fn = main_cpp[main_cpp.index("void ArmRaise(") : main_cpp.index("void ArmLower(")]
        self.assertIn("if (g_armPendingOpenN.load() != a_n || g_armShown.load())", arm_raise_fn)
        self.assertLess(
            arm_raise_fn.index("g_armShowAt = NowMs() + g_armRaiseMs;"),
            arm_raise_fn.index("g_armWaitingRaiseGraph.store(true, std::memory_order_release);"),
        )
        arm_tick_fn = main_cpp[main_cpp.index("void ArmTick(") : main_cpp.index("std::uint32_t KeyThread(")]
        self.assertEqual(arm_tick_fn.count("g_armPendingOpenN.exchange(0)"), 2)
        self.assertIn("g_armWaitingRaiseGraph = false;", arm_tick_fn)
        arm_sink_fn = main_cpp[main_cpp.index("class ArmAnimGraphSink") : main_cpp.index("ArmAnimGraphSink g_armGraphSink;")]
        self.assertIn("g_armPendingOpenN.load() != 0 && g_armWaitingRaiseGraph.exchange(false)", arm_sink_fn)

        # 2. Thread-safety & lock fixes in main.cpp
        self.assertIn("std::atomic<std::uint32_t>               g_invSortMode{ 0 };", main_cpp)
        self.assertIn("std::atomic<const void*>                 g_activeShellMenu{ nullptr };", main_cpp)
        self.assertNotIn("const_cast<std::int32_t&>(extPage)", main_cpp)
        clear_fn = main_cpp[main_cpp.index("void ClearMovieSessionState(") : main_cpp.index("const char* OpenBlockingOverlayMenu(")]
        self.assertIn("g_activeShellMenu = nullptr;", clear_fn)
        load_fn = main_cpp[main_cpp.index("bool MenuLoadMovie(") : main_cpp.index("std::int64_t SincePress()")]
        self.assertIn("if (a_dispatcher) {", load_fn)
        sync_fn = main_cpp[main_cpp.index("void ArmSyncGraphSink()") : main_cpp.index("bool EventIsPath(")]
        self.assertIn("bool oldStillPresent = false;", sync_fn)
        self.assertIn("if (graphPtr == g_armWatchedGraph && curGen == g_armWatchedGen)", sync_fn)
        self.assertIn("thread_local std::vector<GfxWatchdogFrame> t_gfxWatchdogStack;", main_cpp)
        self.assertIn("std::mutex                               g_gfxWatchdogLock;", main_cpp)
        fill_inv_fn = main_cpp[main_cpp.index("void FillInvAndDataIntoDataObj(") : main_cpp.index("void FillPipboyDataObj(")]
        self.assertIn("quickkeysCopy = g_quickkeyFormIds;", fill_inv_fn)

        # 3. SetQuestActive & ShowQuestOnMap fixes in main.cpp
        set_quest_fn = main_cpp[
            main_cpp.index('if (_name == "SetQuestActive")') : main_cpp.index('if (_name == "ShowQuestOnMap"')
        ]
        self.assertIn("CollectShellVitalsMainThread(s_savedPage.load());", set_quest_fn)
        show_map_fn = main_cpp[
            main_cpp.index('if (_name == "ShowQuestOnMap"') : main_cpp.index('if (_name == "ToggleRadioStationActiveStatus")')
        ]
        self.assertIn("ExtractShellUInt32(a_params.args[0], targetU32);", show_map_fn)
        self.assertIn("CollectShellVitalsMainThread(3u);", show_map_fn)
        self.assertIn("PipboyMap::RequestCenterMarker(-1);", show_map_fn)
        fill_data_fn = main_cpp[main_cpp.index("void FillPipboyDataObj(") : main_cpp.index("bool ReadPath(")]
        self.assertIn('std::string_view(a_when) != "partial"', fill_data_fn)

        # 4. pipboy_map.cpp atomics, dirty-flag ownership, storeIdx<->arrIdx mapping & ResetMapMovieState
        self.assertIn("std::array<std::atomic<bool>, kMaxMapMenus> g_mapSlotInstalled{};", map_cpp)
        self.assertIn("std::vector<std::pair<std::uint32_t, std::int32_t>> g_pushedStoreIndices;", map_cpp)
        load_cat_fn = map_cpp[map_cpp.index("void LoadQuestObjectiveCatalog(") : map_cpp.index("const RE::BSFixedString& OurMenuFixed()")]
        self.assertIn("rows = g_questCatalog.size();", load_cat_fn)
        self.assertNotIn("g_questCatalog.size(), extraLoaded", load_cat_fn)
        reset_fn = map_cpp[map_cpp.index("void ResetMapMovieState()") : map_cpp.index("void CloseMenuOnFailedMovieCall(")]
        self.assertIn("g_pushedStoreIndices.clear();", reset_fn)
        self.assertIn("g_pushedQuestIndices.clear();", reset_fn)
        self.assertIn("g_requestedCenterMarkerId = -1;", reset_fn)
        self.assertIn("g_requestedCenterQuestFormId = 0;", reset_fn)
        pop_fn = map_cpp[map_cpp.index("void PopulateMapDataObj(") : map_cpp.index("void OnShellUpdate(")]
        self.assertNotIn("g_markersDirty = false;", pop_fn)
        self.assertIn("g_pushedStoreIndices.emplace_back(", pop_fn)
        shell_upd_fn = map_cpp[map_cpp.index("void OnShellUpdate(") : map_cpp.index("void OnMenuDestroy()")]
        self.assertIn("if (g_lastPlayerArrayIdx >= 0 && g_needCenter.exchange(false))", shell_upd_fn)
        self.assertNotIn("g_needCenter.exchange(false) && g_lastPlayerArrayIdx >= 0", shell_upd_fn)
        self.assertIn("for (const auto& [storeIdx, pushedArrIdx] : g_pushedStoreIndices)", shell_upd_fn)

    def test_cross_os_path_safety_no_drive_letters_in_new_files(self) -> None:
        for path in (Path(__file__), ROOT / "scripts" / "ui" / "pipboy_mission_catalog.py", MAIN_CPP, MAP_H, MAP_CPP):
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", text), f"drive path leaked in {path.name}")


if __name__ == "__main__":
    unittest.main()
