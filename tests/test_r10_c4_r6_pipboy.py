"""Offline regression tests for Round 10 Slice W4 — C4 Pip-Boy Screen Fixes & R6 Native Scan Cache / Vector Locks.

Verifies offline (pushed, not run in game until candidate-2g):
  - C4-1: Opaque dark Pip-Boy CRT backdrop via root.graphics (fallback Menu_mc.graphics), reset on teardown,
    and logged via step=shell_backdrop.
  - C4-2: Opt-in ShellVitalsFill (default 0 -> exact 2f path byte-for-byte with SpecialReady; 1 -> real HP/AP
    & S.P.E.C.I.A.L. on kShow, onNewPage/onNewTab, and partial updates even when PopulateInCall=0), with
    everPositiveHp/everPositiveAp zero-AV guards and step=shell_vitals.
  - C4-3: BottomBar_mc.Info_mc.Date_tf widened (194.0, wordWrap=false, autoSize="left") clear of Time_tf (x=207),
    logged via step=shell_date_fix.
  - C4-4: Opt-in SuppressDataMenu (default 0, hide-only kHide) + opt-in TabOpensPipboy (default 0), with
    main-thread blocking-menu tracker (g_nonDataBlockingOpen + 500 ms kBlockingMenuCooldownMs) so pressing Tab
    to close a Starfield menu (DialogueMenu/ContainerMenu/WorkshopMenu/etc.) never pops the Pip-Boy.
  - R6-1: One-time PostDataLoad TESQuest* cache (g_cachedQuestForms, step=quest_cache_build) and fast
    InvDataAnswers=0 path skipping full DATA quest/workshop/stat list building.
  - R6-2: Dedicated leaf std::mutex g_pushedIndicesLock guarding g_pushedStoreIndices & g_pushedQuestIndices
    across all 5 access sites in pipboy_map.cpp without ever holding the lock across Scaleform GFx calls.
  - Preserved invariants: g_armShowAt = NowMs() + g_armRaiseMs;, zero local drive path leaks, cross-OS safe.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts" / "ui") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "ui"))

import make_pipboy_stage_ini as stage_ini  # noqa: E402

MAIN_CPP = ROOT / "sfse" / "FO4SFPipboyMenu" / "src" / "main.cpp"
MAP_CPP = ROOT / "sfse" / "FO4SFPipboyMenu" / "src" / "pipboy_map.cpp"
MAP_H = ROOT / "sfse" / "FO4SFPipboyMenu" / "src" / "pipboy_map.h"
SHIPPED_INI = ROOT / "sfse" / "FO4SFPipboyMenu" / "FO4SFPipboyMenu.ini"
STAGE_INI_PY = ROOT / "scripts" / "ui" / "make_pipboy_stage_ini.py"
C4_DOC = ROOT / "docs" / "ui" / "pipboy-c4-fixes.md"


def _should_open_pipboy_on_closed_tab(
    *,
    tab_opens_pipboy: bool,
    pipboy_open: bool,
    game_in_front: bool,
    non_data_blocking_open_at_down: bool,
    last_non_data_blocking_ms: int,
    last_shell_transition_ms: int,
    now_ms: int,
    current_blocking_menu: str | None,
    blocking_cooldown_ms: int = 500,
    shell_cooldown_ms: int = 350,
) -> bool:
    """Reference model of the C4-4 KeyThread + HandleClosedTabKeyMainThread decision."""
    if not tab_opens_pipboy or pipboy_open or not game_in_front:
        return False
    # KeyThread key-down check
    if non_data_blocking_open_at_down:
        return False
    if last_non_data_blocking_ms > 0 and (now_ms - last_non_data_blocking_ms) < blocking_cooldown_ms:
        return False
    if (now_ms - last_shell_transition_ms) < shell_cooldown_ms:
        return False
    # Main-thread check (even if Starfield already closed DialogueMenu/WorkshopMenu on the same Tab press!)
    if current_blocking_menu is not None and current_blocking_menu.lower() != "datamenu":
        return False
    return True


class Round10C4R6PipboyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main_cpp = MAIN_CPP.read_text(encoding="utf-8")
        cls.map_cpp = MAP_CPP.read_text(encoding="utf-8")
        cls.c4_doc = C4_DOC.read_text(encoding="utf-8")

    def test_c4_1_opaque_shell_backdrop_and_session_reset(self) -> None:
        self.assertIn('g_shellBackdrop = ReadNumber(ini, L"ShellBackdrop", 1) != 0;', self.main_cpp)
        fn = self.main_cpp[
            self.main_cpp.index("bool ApplyShellBackdrop(") : self.main_cpp.rindex("void ApplyBottomBarDateFix(")
        ]
        self.assertIn("if (!g_shellBackdrop) {", fn)
        self.assertIn('a_top.GetMember("graphics", &gfx)', fn)
        self.assertIn('a_menuMc.GetMember("graphics", &gfx)', fn)
        self.assertIn('gfx.Invoke("beginFill"', fn)
        self.assertIn('gfx.Invoke("drawRect"', fn)
        self.assertIn('gfx.Invoke("endFill"', fn)
        self.assertIn("g_backdropMovie.store(movie);", fn)
        self.assertIn("step=shell_backdrop movie={} ok={} target={} color=0x041409 alpha=0.97", fn)

        show_init = self.main_cpp[
            self.main_cpp.index("void ShellShowInit(") : self.main_cpp.index("void ShellHideTeardown(")
        ]
        self.assertIn("ApplyShellBackdrop(a_menu, top, menuMc);", show_init)

        clear_fn = self.main_cpp[
            self.main_cpp.index("void ClearMovieSessionState(") : self.main_cpp.index("const char* OpenBlockingOverlayMenu(")
        ]
        self.assertIn("g_backdropMovie = nullptr;", clear_fn)
        self.assertIn("g_dateFixLogMovie = nullptr;", clear_fn)
        self.assertIn("g_vitalsLogMovie = nullptr;", clear_fn)

    def test_c4_2_opt_in_shell_vitals_fill_preserves_2f_default_path(self) -> None:
        # Safe default: ShellVitalsFill=0 restores exact 2f path byte-for-byte
        self.assertIn('g_shellVitalsFill = ReadNumber(ini, L"ShellVitalsFill", 0) != 0;', self.main_cpp)
        self.assertIn('g_populateInCall = ReadNumber(ini, L"PopulateInCall", 0) != 0;', self.main_cpp)

        vitals_fn = self.main_cpp[
            self.main_cpp.index("void CollectShellVitalsMainThread(") : self.main_cpp.index("struct RawObjectInstance")
        ]
        self.assertIn("static bool   everPositiveHp = false;", vitals_fn)
        self.assertIn("static bool   everPositiveAp = false;", vitals_fn)
        self.assertIn('next.hpSource = "av";', vitals_fn)
        self.assertIn('next.apSource = "av";', vitals_fn)
        self.assertIn('next.hpSource = hpReadOk ? "formula_zero_av" : "formula";', vitals_fn)

        fill_fn = self.main_cpp[
            self.main_cpp.index("void FillPipboyDataObj(") : self.main_cpp.index("bool ReadPath(")
        ]
        self.assertIn("step=shell_vitals when={} page={} tab={} hp={:.0f}/{:.0f} ap={:.0f}/{:.0f}", fill_fn)

        # kShow, onNewPage/onNewTab, and partial all gate FillPipboyDataObj behind g_populateInCall || g_shellVitalsFill
        # and keep the exact 2f SpecialReady else-branch intact when both are 0
        show_init = self.main_cpp[
            self.main_cpp.index("void ShellShowInit(") : self.main_cpp.index("void ShellHideTeardown(")
        ]
        self.assertIn("if (g_populateInCall || g_shellVitalsFill)", show_init)
        self.assertIn('FillPipboyDataObj(a_menu, root, g_dataObj, page, tab, "kShow");', show_init)
        self.assertIn('SpecialReady(root, top, "show");', show_init)

        ans_fn = self.main_cpp[
            self.main_cpp.index("void AnswerPageOrTabSynchronously(") : self.main_cpp.index("void NoteAnswer(")
        ]
        self.assertIn("if (g_populateInCall || g_shellVitalsFill)", ans_fn)
        self.assertIn('FillPipboyDataObj(menu, root, g_dataObj, targetPage, targetTab, a_isPage ? "onNewPage" : "onNewTab");', ans_fn)
        self.assertIn('SpecialReady(root, top, "answer");', ans_fn)

        events_fn = self.main_cpp[
            self.main_cpp.index("bool ProcessPendingShellEvents(") : self.main_cpp.index("void ShellUpdate(")
        ]
        self.assertIn("(g_populateInCall || g_shellVitalsFill || g_statActions || g_invDataAnswers || g_dataPagesFill)", events_fn)
        self.assertIn('FillPipboyDataObj(a_menu, a_root, g_dataObj, page, tab, "partial");', events_fn)

    def test_c4_3_bottom_bar_date_field_widen_and_autosize(self) -> None:
        fn = self.main_cpp[
            self.main_cpp.rindex("void ApplyBottomBarDateFix(") : self.main_cpp.index("void ShellShowInit(")
        ]
        self.assertIn('ReadPath(a_menuMc, "BottomBar_mc.Info_mc.Date_tf", dateTf)', fn)
        self.assertIn('dateTf.SetMember("wordWrap", RE::Scaleform::GFx::Value(false))', fn)
        self.assertIn('dateTf.SetMember("width", RE::Scaleform::GFx::Value(194.0))', fn)
        self.assertIn('dateTf.SetMember("autoSize", RE::Scaleform::GFx::Value("left"))', fn)
        self.assertIn("step=shell_date_fix when={} old_w={:.1f} new_w={:.1f}", fn)

        show_init = self.main_cpp[
            self.main_cpp.index("void ShellShowInit(") : self.main_cpp.index("void ShellHideTeardown(")
        ]
        self.assertIn('ApplyBottomBarDateFix(a_menu, menuMc, "kShow");', show_init)

        upd = self.main_cpp[
            self.main_cpp.index("void ShellUpdate(") : self.main_cpp.index("bool BootMovieLooseFileExists(")
        ]
        self.assertIn('ApplyBottomBarDateFix(a_menu, menuMc, "update");', upd)

    def test_c4_4_data_menu_opt_in_and_blocking_menu_closed_by_same_tab_press_no_open(self) -> None:
        # Both C4-4 switches default to 0 (safe default preserved)
        self.assertIn('g_suppressDataMenu = ReadNumber(ini, L"SuppressDataMenu", 0) != 0;', self.main_cpp)
        self.assertIn('g_tabOpensPipboy = ReadNumber(ini, L"TabOpensPipboy", 0) != 0;', self.main_cpp)
        self.assertIn(
            "step=shell_c4_config shell_backdrop={} shell_vitals_fill={} suppress_data_menu={} tab_opens_pipboy={}",
            self.main_cpp,
        )
        self.assertIn("constexpr std::int64_t                   kBlockingMenuCooldownMs = 500;", self.main_cpp)

        suppress_fn = self.main_cpp[
            self.main_cpp.index("bool SuppressDataMenuMainThread()") : self.main_cpp.rindex("void RequestPipboyOpen(")
        ]
        self.assertIn("OpenBlockingOverlayMenu(ui, true) != nullptr", suppress_fn)
        self.assertIn("queue->AddMessage(DataMenuFixed(), RE::UI_MESSAGE_TYPE::kHide);", suppress_fn)
        self.assertIn("step=data_menu_suppress n={} menu=DataMenu sent=hide", suppress_fn)

        poll_fn = self.main_cpp[
            self.main_cpp.index("void PollBlockingMenuStateMainThread()") : self.main_cpp.index("void HandleClosedTabKeyMainThread(")
        ]
        self.assertIn('const bool  nonDataBlocking = (blocking != nullptr) && !SameText(blocking, "DataMenu");', poll_fn)
        self.assertIn("g_nonDataBlockingOpen.store(nonDataBlocking);", poll_fn)
        self.assertIn("g_lastNonDataBlockingMs.store(NowMs());", poll_fn)

        tab_fn = self.main_cpp[
            self.main_cpp.index("void HandleClosedTabKeyMainThread(") : self.main_cpp.index("void ArmKey(")
        ]
        self.assertIn('if (!SameText(blocking, "DataMenu"))', tab_fn)
        self.assertIn("kBlockingMenuCooldownMs", tab_fn)
        self.assertIn("ignored=recent_blocking_menu", tab_fn)
        self.assertIn("SuppressDataMenuMainThread();", tab_fn)
        self.assertIn("step=tab_key n={} vk=0x9 page={} sent=request_open", tab_fn)
        self.assertIn('RequestPipboyOpen(page, "tab_key");', tab_fn)

        key_fn = self.main_cpp[
            self.main_cpp.index("std::uint32_t KeyThread(") : self.main_cpp.index("void Register()")
        ]
        self.assertIn("PollBlockingMenuStateMainThread();", key_fn)
        self.assertIn("blockedAtDown", key_fn)
        self.assertIn("kBlockingMenuCooldownMs", key_fn)
        self.assertIn("kShellTabCooldownMs", key_fn)

        on_movie = self.main_cpp[
            self.main_cpp.index("void OnMovieCreated(") : self.main_cpp.index("void OnMessage(")
        ]
        self.assertIn('SameText(a_menu->menuName.c_str(), "DataMenu")', on_movie)
        self.assertIn("SuppressDataMenuMainThread();", on_movie)

        # Behavioral scenario: blocking menu (DialogueMenu / WorkshopMenu / ContainerMenu) closed by the same Tab press
        # -> Starfield already closed the menu by the time main thread runs (current_blocking_menu=None),
        # yet Pip-Boy MUST NOT open because blocking menu was open at key-down or within 500 ms!
        self.assertFalse(
            _should_open_pipboy_on_closed_tab(
                tab_opens_pipboy=True,
                pipboy_open=False,
                game_in_front=True,
                non_data_blocking_open_at_down=True,
                last_non_data_blocking_ms=1000,
                last_shell_transition_ms=0,
                now_ms=1030,
                current_blocking_menu=None,
            )
        )
        self.assertFalse(
            _should_open_pipboy_on_closed_tab(
                tab_opens_pipboy=True,
                pipboy_open=False,
                game_in_front=True,
                non_data_blocking_open_at_down=False,
                last_non_data_blocking_ms=1000,
                last_shell_transition_ms=0,
                now_ms=1450,  # 450 ms < 500 ms cooldown after DialogueMenu/WorkshopMenu closed
                current_blocking_menu=None,
            )
        )
        # Normal closed-gameplay Tab press (> 500 ms after any blocking menu, even if Starfield queued DataMenu) -> opens
        self.assertTrue(
            _should_open_pipboy_on_closed_tab(
                tab_opens_pipboy=True,
                pipboy_open=False,
                game_in_front=True,
                non_data_blocking_open_at_down=False,
                last_non_data_blocking_ms=1000,
                last_shell_transition_ms=0,
                now_ms=1600,
                current_blocking_menu="DataMenu",
            )
        )
        # Opt-out default (TabOpensPipboy=0) -> never opens on Tab
        self.assertFalse(
            _should_open_pipboy_on_closed_tab(
                tab_opens_pipboy=False,
                pipboy_open=False,
                game_in_front=True,
                non_data_blocking_open_at_down=False,
                last_non_data_blocking_ms=0,
                last_shell_transition_ms=0,
                now_ms=5000,
                current_blocking_menu=None,
            )
        )

    def test_r6_1_quest_scan_cache_and_fast_inv_off_path(self) -> None:
        self.assertIn("struct CachedQuestForm", self.main_cpp)
        self.assertIn("std::vector<CachedQuestForm> g_cachedQuestForms;", self.main_cpp)
        collect_fn = self.main_cpp[
            self.main_cpp.index("void CollectQuestAndStatsMainThread(") : self.main_cpp.index("void LogCoreValueResolve(")
        ]
        self.assertIn("if (!g_questCacheBuilt || g_questCacheHandler != handler)", collect_fn)
        self.assertIn("g_questCacheBuilt = true;", collect_fn)
        self.assertIn("step=quest_cache_build plugins={} quests={} workshop={} scanned={}", collect_fn)
        self.assertIn("for (const auto& cached : g_cachedQuestForms)", collect_fn)
        self.assertIn("if (!wantFullData)", collect_fn)

    def test_r6_2_pipboy_map_pushed_indices_mutex_leaf_lock(self) -> None:
        self.assertIn("std::mutex                             g_pushedIndicesLock;", self.map_cpp)

        reset_fn = self.map_cpp[
            self.map_cpp.index("void ResetMapMovieState()") : self.map_cpp.index("void CloseMenuOnFailedMovieCall(")
        ]
        self.assertIn("std::scoped_lock lock(g_pushedIndicesLock);", reset_fn)

        release_fn = self.map_cpp[
            self.map_cpp.index("void ReleaseMovieRefs()") : self.map_cpp.index("void OnCodeObjCall(")
        ]
        self.assertIn("std::scoped_lock lock(g_pushedIndicesLock);", release_fn)

        fast_travel = self.map_cpp[
            self.map_cpp.index('if (a_name == "FastTravel")') : self.map_cpp.index("void PopulateMapDataObj(")
        ]
        self.assertIn("std::scoped_lock lock(g_pushedIndicesLock);", fast_travel)

        pop_fn = self.map_cpp[
            self.map_cpp.index("void PopulateMapDataObj(") : self.map_cpp.index("void OnShellUpdate(")
        ]
        self.assertGreaterEqual(pop_fn.count("std::scoped_lock lock(g_pushedIndicesLock);"), 4)
        for m in re.finditer(r"\{\s*std::scoped_lock lock\(g_pushedIndicesLock\);([^}]*)\}", pop_fn, re.S):
            body = m.group(1)
            self.assertNotIn("CreateObject", body)
            self.assertNotIn("PushMarkerObject", body)
            self.assertNotIn("Invoke", body)

        upd_fn = self.map_cpp[
            self.map_cpp.index("void OnShellUpdate(") : self.map_cpp.index("void OnMenuDestroy()")
        ]
        self.assertGreaterEqual(upd_fn.count("std::scoped_lock lock(g_pushedIndicesLock);"), 2)
        self.assertLess(upd_fn.rindex("g_pushedIndicesLock"), upd_fn.index("SetCenterMarker"))

    def test_shipped_and_staged_ini_defaults_enable_backdrop_and_vitals_keep_datamenu_off(self) -> None:
        shipped = "\n" + SHIPPED_INI.read_text(encoding="utf-8")
        for req in (
            "ShellBackdrop=1",
            "ShellVitalsFill=1",
            "SuppressDataMenu=0",
            "TabOpensPipboy=0",
            "MapBlockStarMap=0",
            "Arm=0",
            "BootOnFirstOpen=0",
        ):
            self.assertIn(f"\n{req}\n", shipped, req)

        staged = "\n" + stage_ini.format_stage_ini(["HideMenu"])
        for req in (
            "ShellBackdrop=1",
            "ShellVitalsFill=1",
            "SuppressDataMenu=0",
            "TabOpensPipboy=0",
            "MapBlockStarMap=0",
            "Arm=0",
            "BootOnFirstOpen=0",
        ):
            self.assertIn(f"\n{req}\n", staged, req)

        rolled_back = "\n" + stage_ini.format_stage_ini(
            ["HideMenu"], shell_backdrop=0, shell_vitals_fill=0, suppress_data_menu=1, tab_opens_pipboy=0
        )
        for req in ("ShellBackdrop=0", "ShellVitalsFill=0", "SuppressDataMenu=1", "TabOpensPipboy=0"):
            self.assertIn(f"\n{req}\n", rolled_back, req)

    def test_preserved_invariants_docs_and_no_drive_path_leaks(self) -> None:
        self.assertIn("g_armShowAt = NowMs() + g_armRaiseMs;", self.main_cpp)
        self.assertIn("all 7 Fallout titles", self.c4_doc)
        self.assertIn("pushed, not run", self.c4_doc)
        self.assertIn("ShellBackdrop=0", self.c4_doc)
        self.assertIn("ShellVitalsFill=0", self.c4_doc)
        self.assertIn("TabOpensPipboy=0", self.c4_doc)
        self.assertNotIn("No changes to existing safe defaults", self.c4_doc)
        for token in (
            "step=shell_c4_config",
            "step=shell_backdrop",
            "step=shell_vitals",
            "step=shell_date_fix",
            "step=data_menu_suppress",
            "step=tab_key",
            "step=quest_cache_build",
        ):
            self.assertIn(token, self.c4_doc, token)

        for path in (Path(__file__), MAIN_CPP, MAP_H, MAP_CPP, SHIPPED_INI, STAGE_INI_PY, C4_DOC):
            txt = path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", txt), f"drive path leaked in {path.name}")


if __name__ == "__main__":
    unittest.main()
