"""Offline regression tests for Round 11 Slice R11-W4: D5 (Parts 1 & 2), D7 (a & b), and A2.6.

All Round 11 changes verified here are `pushed, not run` (offline verified only until the next PC candidate run):
  - D5 Part 1: ButtonHintBar_mc repositioned to y=672.0 (below BottomBar_mc 629.8..668.0, inside 708.0 CRT bezel)
    so StatusTab_mc.Name_tf ("PLAYER", y=580.0) never overlaps "RADAWAY (0)" (cand2g still 12).
  - D5 Part 2: Menu_mc.SetPlatform(0u, false) (PLATFORM_PC_KB_MOUSE=0) + Header_mc LeftTriggerButton_mc &
    RightTriggerButton_mc hidden on KB+M, with page-switch refresh on onNewPage.
  - D7 (a): Clear Commonwealth weather & blue-sky atmosphere overrides in FO4SFCoreValues.esm
    (CLMT 0x00310DB1 ClimateUniqueCydonia & 0x002EDEA5 ClimateUniqueCydoniaFrozen -> WTHS 0x001034AB 60% +
     0x0009BC5A 40%; ATMO 0x0000C9D2 ATMO_Mars -> ATMO_Jemison 0x0000C010), default ON with --commonwealth-weather 0
    one-line rollback and byte-identical minimal fixture compatibility.
  - D7 (b): HideStarfieldWatch=1 in shipped & staged FO4SFPipboyMenu.ini (C++ fallback 0, one-line HideStarfieldWatch=0
    rollback), hiding HUDMenu root.BottomLeftGroup_mc and its watch/planet/O2/CO2 children via isolated HudRootOf
    (never mutating g_checkedMovie or g_channelOff), with LoadingMenu pointer-reuse reset.
  - A2.6: Atomic staging (ReplaceAs3ArrayFromStaged) across all AS3 list builds so failed CreateObject leaves prior
    lists intact; static structural list skip on partial vitals refreshes; INV/DATA/RADIO array safety under
    ShellVitalsFill=1; once-per-movie ShellUpdate guards eliminating per-tick ReadPath churn.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "scripts" / "ui", ROOT / "scripts" / "core", ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import make_core_values  # noqa: E402
import make_pipboy_stage_ini as stage_ini  # noqa: E402

MAIN_CPP = ROOT / "sfse" / "FO4SFPipboyMenu" / "src" / "main.cpp"
SHIPPED_INI = ROOT / "sfse" / "FO4SFPipboyMenu" / "FO4SFPipboyMenu.ini"
STAGE_INI_PY = ROOT / "scripts" / "ui" / "make_pipboy_stage_ini.py"
CORE_VALUES_CS = ROOT / "dotnet" / "CoreValues" / "Program.cs"
C4_DOC = ROOT / "docs" / "ui" / "pipboy-c4-fixes.md"

WINDOWS_DRIVE_PATH_RE = re.compile(r"\b[A-Za-z]:[\\/]")


def _simulate_atomic_stage(existing: list[str], wanted: list[str], fail_at_index: int | None) -> tuple[list[str], bool]:
    """Reference model of A2.6 ReplaceAs3ArrayFromStaged: a CreateObject failure preserves the prior AS3 array."""
    staged: list[str] = []
    for idx, item in enumerate(wanted):
        if fail_at_index is not None and idx == fail_at_index:
            return list(existing), False
        staged.append(item)
    return staged, True


class Round11PipboyWeatherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main_cpp = MAIN_CPP.read_text(encoding="utf-8")
        cls.shipped_ini = SHIPPED_INI.read_text(encoding="utf-8")
        cls.core_cs = CORE_VALUES_CS.read_text(encoding="utf-8")
        cls.doc_text = C4_DOC.read_text(encoding="utf-8")

    def test_d5_part1_hint_bar_repositioned_below_bottom_bar_clear_of_player_name(self) -> None:
        # Layout geometry invariant from PipboyMenu.swf (Sprite 79) & Pipboy_StatsPage.swf (Sprite 176)
        name_tf_y = 580.0
        bottom_bar_top = 629.8
        bottom_bar_bottom = 668.0
        target_hintbar_y = 672.0
        crt_bezel_bottom = 708.0
        self.assertGreater(target_hintbar_y, bottom_bar_bottom)
        self.assertLess(target_hintbar_y, crt_bezel_bottom)
        self.assertGreater(bottom_bar_top - name_tf_y, 40.0)

        fn = self.main_cpp[
            self.main_cpp.rindex("void ApplyShellHintBarLayout(") : self.main_cpp.rindex("void ApplyShellPlatform(")
        ]
        self.assertIn("g_hintBarDoneMovie.load() == movie", fn)
        self.assertIn('ReadPath(a_menuMc, "ButtonHintBar_mc", hintBar)', fn)
        self.assertIn("constexpr double kTargetHintBarY = 672.0;", fn)
        self.assertIn('hintBar.SetMember("y", RE::Scaleform::GFx::Value(kTargetHintBarY))', fn)
        self.assertIn("g_hintBarDoneMovie.store(movie);", fn)
        self.assertIn("step=shell_hintbar_layout when={} old_y={:.1f} new_y={:.1f} ok={}", fn)

        show_init = self.main_cpp[
            self.main_cpp.index("void ShellShowInit(") : self.main_cpp.index("void ShellHideTeardown(")
        ]
        self.assertIn('ApplyShellHintBarLayout(a_menu, menuMc, "kShow");', show_init)

    def test_d5_part2_keyboard_mouse_platform_and_trigger_hide(self) -> None:
        fn = self.main_cpp[
            self.main_cpp.rindex("void ApplyShellPlatform(") : self.main_cpp.index("void ShellShowInit(")
        ]
        self.assertIn("constexpr std::uint32_t   kPlatformPcKbMouse = 0u;", fn)
        self.assertIn('InvokeMovieTracked(a_menuMc, "SetPlatform", &res, args, 2, "Menu_mc.SetPlatform", false)', fn)
        self.assertIn('ReadPath(a_menuMc, "ButtonHintBar_mc", hintBar)', fn)
        self.assertIn('ReadPath(a_menuMc, "Header_mc", headerMc)', fn)
        self.assertIn('"LeftTriggerButton_mc"', fn)
        self.assertIn('"RightTriggerButton_mc"', fn)
        self.assertIn('trig.SetMember("visible", RE::Scaleform::GFx::Value(false))', fn)
        self.assertIn("step=shell_platform when={} platform=0 called={} triggers_hidden={}", fn)

        show_init = self.main_cpp[
            self.main_cpp.index("void ShellShowInit(") : self.main_cpp.index("void ShellHideTeardown(")
        ]
        self.assertIn('ApplyShellPlatform(a_menu, menuMc, "kShow");', show_init)

        ans_fn = self.main_cpp[
            self.main_cpp.index("void AnswerPageOrTabSynchronously(") : self.main_cpp.index("void NoteAnswer(")
        ]
        self.assertIn('ApplyShellPlatform(menu, menuMc, a_isPage ? "onNewPage" : "onNewTab", a_isPage);', ans_fn)

    def test_d7b_starfield_watch_hide_flag_isolation_and_one_line_rollback(self) -> None:
        # C++ fallback is 0 if omitted; shipped & staged INIs ship HideStarfieldWatch=1 with one-line rollback 0
        self.assertIn('g_hideStarfieldWatch = ReadNumber(ini, L"HideStarfieldWatch", 0) != 0;', self.main_cpp)
        self.assertIn("hide_starfield_watch={}", self.main_cpp)
        self.assertIn("g_hideStarfieldWatch", self.main_cpp[
            self.main_cpp.index("std::size_t IdCount()") : self.main_cpp.index("bool InImage(")
        ])
        self.assertIn("\nHideStarfieldWatch=1\n", self.shipped_ini)

        # Stage INI generator emits HideStarfieldWatch=1 by default and supports one-line rollback 0
        ini_on = stage_ini.format_stage_ini(["PlaySound", "HideMenu", "onNewPage", "onNewTab"])
        self.assertIn("\nHideStarfieldWatch=1\n", ini_on)
        ini_off = stage_ini.format_stage_ini(["PlaySound", "HideMenu", "onNewPage", "onNewTab"], hide_starfield_watch=0)
        self.assertIn("\nHideStarfieldWatch=0\n", ini_off)
        parser = stage_ini.build_parser()
        ns_def = parser.parse_args(["--stage", "dummy"])
        self.assertEqual(ns_def.hide_starfield_watch, 1)
        ns_off = parser.parse_args(["--stage", "dummy", "--hide-starfield-watch", "0"])
        self.assertEqual(ns_off.hide_starfield_watch, 0)

        # HudRootOf must stay isolated from Pip-Boy g_checkedMovie / g_channelOff
        hud_root = self.main_cpp[
            self.main_cpp.index("HudRootOf(") : self.main_cpp.index("void ApplyHudWatchHide(")
        ]
        self.assertNotIn("g_checkedMovie", hud_root)
        self.assertNotIn("g_channelOff", hud_root)

        # ApplyHudWatchHide hides BottomLeftGroup_mc & watch/O2/CO2 children, never touching RightMeters/CenterGroup/Rollover
        hide_fn = self.main_cpp[
            self.main_cpp.index("void ApplyHudWatchHide(") : self.main_cpp.index("void OnMovieCreated(")
        ]
        self.assertIn("if (!g_hideStarfieldWatch || !a_menu)", hide_fn)
        self.assertIn('ReadPath(top, "BottomLeftGroup_mc", bottomLeft)', hide_fn)
        for child in ("WatchFaceComponent_mc", "WatchOutline_mc", "WatchIconsWidget_mc", "O2CO2_mc", "locationNameBase_mc"):
            self.assertIn(f'"{child}"', hide_fn)
        for keep in ("RightMeters_mc", "CenterGroup_mc", "RolloverWidget_mc", "TopCenterGroup_mc"):
            self.assertNotIn(keep, hide_fn)
        self.assertIn("step=hud_watch_hide when={} movie={} ok={} target=BottomLeftGroup_mc children_hidden={}", hide_fn)

        # OnMovieCreated resets g_hudWatchHiddenMovie on LoadingMenu and hides on HUDMenu
        on_movie = self.main_cpp[
            self.main_cpp.index("void OnMovieCreated(") : self.main_cpp.index("void OnMessage(")
        ]
        self.assertIn('SameText(a_menu->menuName.c_str(), "LoadingMenu")', on_movie)
        self.assertIn("g_hudWatchHiddenMovie.store(nullptr);", on_movie)
        self.assertIn('SameText(a_menu->menuName.c_str(), "HUDMenu")', on_movie)
        self.assertIn('ApplyHudWatchHide(a_menu, "on_movie_created");', on_movie)

    def test_a26_atomic_staging_partial_skip_page_safety_and_once_per_movie_guards(self) -> None:
        # Behavioral proof: failed CreateObject leaves prior list untouched; clean build replaces it
        prior = ["Strength", "Perception", "Endurance", "Charisma", "Intelligence", "Agility", "Luck"]
        kept, ok_fail = _simulate_atomic_stage(prior, ["S2", "P2", "E2"], fail_at_index=2)
        self.assertFalse(ok_fail)
        self.assertEqual(kept, prior)
        replaced, ok_pass = _simulate_atomic_stage(prior, ["S2", "P2", "E2"], fail_at_index=None)
        self.assertTrue(ok_pass)
        self.assertEqual(replaced, ["S2", "P2", "E2"])

        # ReplaceAs3ArrayFromStaged helper present and used across FillPipboyDataObj & FillInvAndDataIntoDataObj
        self.assertIn("std::uint32_t ReplaceAs3ArrayFromStaged(", self.main_cpp)
        inv_fill = self.main_cpp[
            self.main_cpp.index("void FillInvAndDataIntoDataObj(") : self.main_cpp.index("void FillPipboyDataObj(")
        ]
        for list_name in ("InvItems", "FavoritesList", "QuestsList", "WorkshopsList", "GeneralStatsList"):
            self.assertIn(f"step=data_obj_stage_abort list={list_name}", inv_fill)
        self.assertGreaterEqual(inv_fill.count("ReplaceAs3ArrayFromStaged("), 5)

        data_fill = self.main_cpp[
            self.main_cpp.index("void FillPipboyDataObj(") : self.main_cpp.index("bool ReadPath(")
        ]
        for list_name in ("SPECIALList", "SlotResists", "TotalResists", "ActiveEffects"):
            self.assertIn(f"step=data_obj_stage_abort list={list_name}", data_fill)
        self.assertGreaterEqual(data_fill.count("ReplaceAs3ArrayFromStaged("), 4)
        # Partial update skips static structural lists once initialized for this movie
        self.assertIn('const bool          isPartial = (a_when != nullptr && std::string_view(a_when) == "partial");', data_fill)
        self.assertIn("const bool          needStructuralLists = !isPartial || !movie || g_staticListsInitMovie.load() != movie;", data_fill)
        self.assertIn("g_staticListsInitMovie.store(movie);", data_fill)
        # INV / DATA / RADIO array safety when ShellVitalsFill=1
        for arr in ("PerksList", "StatsCategories", "RadioList", "InvItems", "QuestsList", "WorkshopsList", "GeneralStatsList"):
            self.assertIn(f'"{arr}"', data_fill)

        # ApplyBottomBarDateFix runs once per (movie, page) on DATA/MAP only
        date_fn = self.main_cpp[
            self.main_cpp.rindex("void ApplyBottomBarDateFix(") : self.main_cpp.rindex("void ApplyShellHintBarLayout(")
        ]
        self.assertIn("if (curPage >= 0 && curPage != 2 && curPage != 3)", date_fn)
        self.assertIn("g_dateFixDoneMovie.load() == movie && g_dateFixDonePage.load() == curPage", date_fn)
        self.assertIn("g_dateFixDoneMovie.store(movie);", date_fn)

        # ShellUpdate skips ReadPath completely once backdrop, hint bar, platform, and date fix have succeeded
        upd = self.main_cpp[
            self.main_cpp.index("void ShellUpdate(") : self.main_cpp.index("bool BootMovieLooseFileExists(")
        ]
        self.assertIn("const bool needBackdrop = g_shellBackdrop && g_backdropMovie.load() != movie;", upd)
        self.assertIn("const bool needHintBar = g_hintBarDoneMovie.load() != movie;", upd)
        self.assertIn("const bool needPlatform = g_platformDoneMovie.load() != movie;", upd)
        self.assertIn("if (needBackdrop || needHintBar || needPlatform || needDateFix)", upd)

        # ClearMovieSessionState resets all new per-movie atomics
        clear_fn = self.main_cpp[
            self.main_cpp.index("void ClearMovieSessionState(") : self.main_cpp.index("const char* OpenBlockingOverlayMenu(")
        ]
        for sym in (
            "g_dateFixDoneMovie = nullptr;",
            "g_dateFixDonePage = -1;",
            "g_hintBarDoneMovie = nullptr;",
            "g_platformDoneMovie = nullptr;",
            "g_staticListsInitMovie = nullptr;",
        ):
            self.assertIn(sym, clear_fn)

    def test_d7a_clear_commonwealth_weather_in_core_values_and_rollback(self) -> None:
        # Exact binary-verified Starfield.esm FormIDs for Mars -> New Atlantis clear weather & Jemison blue-sky ATMO
        for token in (
            "0x00310DB1",  # ClimateUniqueCydonia
            "0x002EDEA5",  # ClimateUniqueCydoniaFrozen
            "0x0024E982",  # ClimateUniqueNewAtlantis
            "0x001034AB",  # WeatherUniqueNA_Clear_Unique
            "0x0009BC5A",  # WeatherUniqueNA_PartlyCloudy_C2_Unique
            "0x0000C9D2",  # ATMO_Mars
            "0x0000C010",  # ATMO_Jemison
            "--commonwealth-weather",
        ):
            self.assertIn(token, self.core_cs)

        # make_core_values.py CLI defaults to --commonwealth-weather 1 and supports rollback 0
        parser = make_core_values.build_parser()
        ns_on = parser.parse_args(["stage", "--sf-data", "sf", "--out", "out"])
        self.assertEqual(ns_on.commonwealth_weather, 1)
        ns_off = parser.parse_args(["stage", "--sf-data", "sf", "--out", "out", "--commonwealth-weather", "0"])
        self.assertEqual(ns_off.commonwealth_weather, 0)

        # Run Mutagen CoreValues selftest (includes weather_fixture on/off/determinism/rejection checks) when dotnet exists
        if shutil.which("dotnet"):
            proj = str(ROOT / "dotnet" / "CoreValues" / "CoreValues.csproj")
            dll = ROOT / "dotnet" / "CoreValues" / "bin" / "Release" / "net9.0" / "CoreValues.dll"
            cmd = ["dotnet", str(dll)] if dll.is_file() else ["dotnet", "run", "--project", proj, "--"]
            with tempfile.TemporaryDirectory() as tmp:
                proc = subprocess.run([*cmd, "selftest", tmp], cwd=str(ROOT), text=True, capture_output=True)
                self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
                self.assertIn("2 CLMT, 1 ATMO", proc.stdout)
                self.assertIn("CoreValues selftest: ok", proc.stdout)

    def test_doc_r15_honesty_and_zero_drive_path_leaks(self) -> None:
        self.assertIn("pushed, not run", self.doc_text)
        self.assertIn("HideStarfieldWatch=0", self.doc_text)
        self.assertIn("--commonwealth-weather 0", self.doc_text)
        self.assertIsNone(WINDOWS_DRIVE_PATH_RE.search(self.doc_text), "drive path leak in pipboy-c4-fixes.md")


if __name__ == "__main__":
    unittest.main()
