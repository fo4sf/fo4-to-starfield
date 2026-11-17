"""Unit tests for `fo4sf.core.title_fit_tables` (`GAP-J3-01`..`GAP-J3-04` and byte-identical `FO4` defaults)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fo4sf.core.title_fit_tables import (  # noqa: E402
    EXTENDED_50CAL_SUBTYPE_IDS,
    FNV_13_REPU_BANK,
    FO4_CORE_SLOTS_0_TO_7,
    FO4_STARFIELD_SUBTYPE_FORMIDS,
    NV_16_STATE_MATRIX,
    REPU_TIER_THRESHOLDS,
    TITLE_AMMO_CALIBRE_MAP,
    TITLE_START_FIT_DEFAULTS,
    evaluate_nv_16_state,
)


class TitleFitTablesTests(unittest.TestCase):
    def test_gap_j3_01_repu_matrix_thresholds_and_diagonals(self) -> None:
        self.assertEqual(REPU_TIER_THRESHOLDS, (15.0, 40.0, 75.0))
        self.assertEqual(len(NV_16_STATE_MATRIX), 4)
        for row in NV_16_STATE_MATRIX:
            self.assertEqual(len(row), 4)
        # Verify exact off-diagonal cells flagged in GAP-J3-01
        self.assertEqual(evaluate_nv_16_state(20.0, 20.0), (1, 1, "Mixed"))
        self.assertEqual(evaluate_nv_16_state(40.0, 40.0), (2, 2, "Unpredictable"))
        self.assertEqual(evaluate_nv_16_state(80.0, 0.0), (3, 0, "Idolized"))
        self.assertEqual(evaluate_nv_16_state(0.0, 80.0), (0, 3, "Vilified"))

    def test_gap_j3_02_fo4_slots_unchanged_and_fnv_13_repu_collision_free(self) -> None:
        # FO4 8 slots keep exact indices 0..7 and FormIDs 0x810..0x872
        self.assertEqual([slot for slot, _, _ in FO4_CORE_SLOTS_0_TO_7], list(range(8)))
        self.assertEqual(FO4_CORE_SLOTS_0_TO_7[0], (0, "Minutemen", 0x000810))
        self.assertEqual(FO4_CORE_SLOTS_0_TO_7[7], (7, "RaidersOutlaws", 0x000872))

        # All 13 New Vegas REPU records have unique slot indices 0..12 <= 15 and unique FormIDs
        fnv_slots = [slot for slot, _, _ in FNV_13_REPU_BANK]
        fnv_fids = [fid for _, _, fid in FNV_13_REPU_BANK]
        self.assertEqual(fnv_slots, list(range(13)))
        self.assertEqual(len(set(fnv_fids)), 13)

    def test_gap_j3_03_fo4_ammo_formids_byte_identical_and_50cal_distinct(self) -> None:
        self.assertEqual(FO4_STARFIELD_SUBTYPE_FORMIDS["FO4SF_Ammo777_AP"], 0x00082C)
        self.assertEqual(FO4_STARFIELD_SUBTYPE_FORMIDS["FO4SF_Laser_MaxCharge"], 0x000836)
        self.assertEqual(len(FO4_STARFIELD_SUBTYPE_FORMIDS), 11)
        self.assertNotEqual(EXTENDED_50CAL_SUBTYPE_IDS["JHP"], "FO4SF_Ammo777_JHP")
        for title in ("FO1", "FO2", "FO3", "FNV", "FO4", "FO76"):
            self.assertIn(title, TITLE_AMMO_CALIBRE_MAP)
            self.assertGreaterEqual(len(TITLE_AMMO_CALIBRE_MAP[title]), 6)

    def test_gap_j3_04_start_world_defaults_preserve_fo4_behavior(self) -> None:
        fo4 = TITLE_START_FIT_DEFAULTS["FO4"]
        self.assertEqual(fo4.start_key, "vault111")
        self.assertEqual(fo4.rads_rule_default, 0)
        self.assertFalse(fo4.pa_training_required)
        self.assertEqual(fo4.perk_cadence_default, 1)

        self.assertEqual(TITLE_START_FIT_DEFAULTS["FO1"].perk_cadence_default, 3)
        self.assertEqual(TITLE_START_FIT_DEFAULTS["FNV"].perk_cadence_default, 2)
        self.assertTrue(TITLE_START_FIT_DEFAULTS["FO3"].pa_training_required)


if __name__ == "__main__":
    unittest.main()
