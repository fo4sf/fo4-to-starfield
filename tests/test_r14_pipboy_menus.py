"""Offline regression tests for Round 14 Task 2 (`gemini/r14-pipboy-menus`) and DATA > QUESTS / WORKSHOPS wiring."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts" / "ui") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "ui"))

import make_pipboy_stage_ini as stage_ini  # noqa: E402

BLOCKING_H = ROOT / "sfse" / "common" / "blocking_menus.h"
R14_H = ROOT / "sfse" / "FO4SFPipboyMenu" / "src" / "pipboy_menus_r14.h"
MAIN_CPP = ROOT / "sfse" / "FO4SFPipboyMenu" / "src" / "main.cpp"
BUILD_PS1 = ROOT / "sfse" / "FO4SFPipboyMenu" / "build.ps1"
SHIPPED_INI = ROOT / "sfse" / "FO4SFPipboyMenu" / "FO4SFPipboyMenu.ini"
STAGE_INI_PY = ROOT / "scripts" / "ui" / "make_pipboy_stage_ini.py"
JOBS_DOC = ROOT / "docs" / "ui" / "pipboy-jobs-subtab-design.md"
CARD_DOC = ROOT / "docs" / "testing" / "pipboy-r14-menus-card.md"

CURATED_21_MODALS = (
    "ArmorCraftingMenu",
    "DrugsCraftingMenu",
    "FoodCraftingMenu",
    "IndustrialCraftingMenu",
    "WeaponsCraftingMenu",
    "DataSlateMenu",
    "PowersMenu",
    "AlmanacMenu",
    "MissionBoard",
    "WorkshopTargetMenu",
    "ShipCrewMenu",
    "ShipCrewAssignMenu",
    "TakeoffMenu",
    "ShipRefuelMenu",
    "WeaponGroupAssignmentMenu",
    "ResearchMenu",
    "PhotoGalleryMenu",
    "PlayBinkMenu",
    "TitleSequenceMenu",
    "CreditsMenu",
    "EndGameCreditsMenu",
)

FORBIDDEN_ALWAYS_OPEN = (
    "HUDMenu",
    "HUDMessagesMenu",
    "CursorMenu",
    "FaderMenu",
    "FullscreenMenu",
    "ScopeMenu",
    "SpaceshipHudMenu",
    "ContextMenu",
    "TestMenu",
)

DEFERRED_CENSUS_6 = (
    "MissionMenu",
    "MarketplaceMenu",
    "DocAcceptMenu",
    "BoundaryMenu",
    "FanfareMenu",
    "StreamingInstallMenu",
)

HIDE_MENUS_8 = (
    ("HidePowersMenu", "PowersMenu"),
    ("HideAlmanacMenu", "AlmanacMenu"),
    ("HideResearchMenu", "ResearchMenu"),
    ("HideShipCrewMenu", "ShipCrewMenu"),
    ("HideShipCrewAssignMenu", "ShipCrewAssignMenu"),
    ("HideTakeoffMenu", "TakeoffMenu"),
    ("HideShipRefuelMenu", "ShipRefuelMenu"),
    ("HideWeaponGroupAssignmentMenu", "WeaponGroupAssignmentMenu"),
)


def _extract_kblocking_entries(text: str) -> list[str]:
    m = re.search(r"kBlockingMenus\s*\{\s*\{(.*?)\}\s*\};", text, re.S)
    assert m is not None
    # Strip C++ single-line comments before extracting string literals
    body = re.sub(r"//[^\n]*", "", m.group(1))
    return re.findall(r'"([^"]+)"', body)


class Round14PipboyMenusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.blocking_h = BLOCKING_H.read_text(encoding="utf-8")
        cls.r14_h = R14_H.read_text(encoding="utf-8")
        cls.main_cpp = MAIN_CPP.read_text(encoding="utf-8")
        cls.build_ps1 = BUILD_PS1.read_text(encoding="utf-8")
        cls.shipped_ini = "\n" + SHIPPED_INI.read_text(encoding="utf-8")
        cls.jobs_doc = JOBS_DOC.read_text(encoding="utf-8")
        cls.card_doc = CARD_DOC.read_text(encoding="utf-8")

    def test_task2a_curated_blocking_list_only(self) -> None:
        entries = _extract_kblocking_entries(self.blocking_h)
        self.assertEqual(len(entries), 38 + 21)
        self.assertEqual(len(set(entries)), len(entries), "duplicate menu in kBlockingMenus")
        for m in CURATED_21_MODALS:
            self.assertIn(m, entries)
        for bad in FORBIDDEN_ALWAYS_OPEN:
            self.assertNotIn(bad, entries, f"always-open overlay {bad} must NEVER be added")
        for deferred in DEFERRED_CENSUS_6:
            self.assertNotIn(deferred, entries, f"census-only {deferred} must not be added yet")

    def test_task2b_hide_menus_and_ini_switches_default_off(self) -> None:
        self.assertIn("bool SuppressHiddenMenusMainThread()", self.main_cpp)
        self.assertIn("step=hide_menu n={} menu={} sent=hide", self.main_cpp)
        staged = "\n" + stage_ini.format_stage_ini(["HideMenu"])
        for ini_key, menu_name in HIDE_MENUS_8:
            self.assertIn(f'L"{ini_key}", "{menu_name}"', self.r14_h)
            self.assertIn(f"\n{ini_key}=0\n", self.shipped_ini)
            self.assertIn(f"\n{ini_key}=0\n", staged)
        self.assertIn("DataPagesFill=1", staged)
        self.assertIn("DataPagesFill=0", self.shipped_ini)
        self.assertIn("ShowJobsGroup=0", self.shipped_ini)
        self.assertIn("ShowJobsGroup=0", staged)
        self.assertIn("JobsJson=FO4SFPipboyJobs.json", self.shipped_ini)
        self.assertIn("JobsJson=FO4SFPipboyJobs.json", staged)
        self.assertIn(r"src\pipboy_menus_r14.h", self.build_ps1)

    def test_task2c_and_next_data_quests_workshops_and_jobs_step1(self) -> None:
        # Clean Rule 13 Sanctuary Hills entry in WORKSHOPS (available for Workshop or Mission plugin)
        self.assertIn('ws.name = "Sanctuary Hills";', self.main_cpp)
        self.assertNotIn("(Placeholder)", self.main_cpp)
        self.assertIn("g_questCacheWorkshopLoaded || g_questCacheMissionLoaded", self.main_cpp)
        # Quests & Workshops fill split from InvDataAnswers via g_dataPagesFill
        self.assertIn("const bool wantFullData = g_invDataAnswers || g_dataPagesFill;", self.main_cpp)
        # formID=0 JOBS group handling in CollectQuestAndStatsMainThread + onQuestSelection + SetQuestActive
        self.assertIn('jobsGroup.formId = 0;', self.main_cpp)
        self.assertIn('jobsGroup.name = "JOBS";', self.main_cpp)
        self.assertIn("qFid == 0 && g_showJobsGroup", self.main_cpp)
        self.assertIn("step=job_select jobs={}", self.main_cpp)
        self.assertIn("step=job_active id={} active={}", self.main_cpp)
        # Generic JSON reader supports all 6 job schema fields cleanly
        for field in ("id", "title", "giver", "target", "reward_text", "rewardText", "status"):
            self.assertIn(f'"{field}"', self.r14_h)

    def test_task2cd_docs_card_and_no_drive_letter_leaks(self) -> None:
        self.assertIn("Option A", self.jobs_doc)
        self.assertIn("Option B", self.jobs_doc)
        self.assertIn("formID == 0", self.jobs_doc)
        self.assertIn("inspectmenu.swf", self.card_doc)
        self.assertIn("VIDEO", self.card_doc)
        for deferred in DEFERRED_CENSUS_6:
            self.assertIn(deferred, self.card_doc)
        for ini_key, _ in HIDE_MENUS_8:
            self.assertIn(ini_key, self.card_doc)

        for path in (BLOCKING_H, R14_H, MAIN_CPP, SHIPPED_INI, STAGE_INI_PY, JOBS_DOC, CARD_DOC, Path(__file__)):
            txt = path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", txt), f"drive path leaked in {path.name}")


if __name__ == "__main__":
    unittest.main()
