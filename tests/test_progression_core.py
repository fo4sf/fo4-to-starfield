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

from fo4sf.progression import core_log, tables  # noqa: E402


SAMPLE_PASS_LOG = [
    "FO4SFPROG rt=1.0 init pool28=0 cadence=2 respec_used=0 end=true",
    "FO4SFPROG rt=2.0 creation bg=Vault_Dweller traits=2 special_sum=40 skills_count=13 speech=50 science=49 medicine=49 carry=210.0 end=true",
    "FO4SFPROG rt=3.0 respec first_ok=True second_refused=True active_traits=1 end=true",
    "FO4SFPROG rt=4.0 cadence cad2_lvl2=True cad2_lvl3=False cad2_lvl4=True cad1_lvl3=True end=true",
    "FO4SFPROG rt=5.0 karma_repu karma=-800.0 karma_tier=Very_Evil faction=Minutemen fame=85.0 infamy=0.0 repu_title=Idolized disposition=Ally end=true",
    "FO4SFPROG rt=6.0 summary ok=true stages=10,20,30,40,50 end=true",
]


class DataTablesAndMathTests(unittest.TestCase):
    def test_table_counts_and_unique_formids(self):
        self.assertEqual(len(tables.SPECIAL_TABLE), 7)
        self.assertEqual(len(tables.SKILLS_TABLE), 13)
        self.assertEqual(len(tables.BACKGROUNDS_TABLE), 9)
        self.assertEqual(len(tables.TRAITS_TABLE), 9)
        self.assertEqual(len(tables.PERKS_TABLE), 8)
        self.assertEqual(len(tables.REPU_FACTIONS_TABLE), 6)

        ids = (
            [r["id"] for r in tables.SPECIAL_TABLE]
            + [r["id"] for r in tables.SKILLS_TABLE]
            + [r["id"] for r in tables.BACKGROUNDS_TABLE]
            + [r["id"] for r in tables.TRAITS_TABLE]
            + [r["id"] for r in tables.PERKS_TABLE]
            + [r["fame_id"] for r in tables.REPU_FACTIONS_TABLE]
            + [r["infamy_id"] for r in tables.REPU_FACTIONS_TABLE]
        )
        self.assertEqual(len(ids), len(set(ids)), "every table FormID must be unique")

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
        # LCK=5 -> ceil(2.5) = 3. Speech gov CHA=6 -> base 2 + 12 + 3 = 17.
        # Vault Dweller (+10 Speech/Science/Medicine) + Tag Speech (+15) + Good Natured (+5 Speech, -5 Guns) = 47!
        skills = tables.compute_initial_skills(
            alloc40,
            background_name="Vault Dweller",
            tag_skills=["Speech", "Guns", "Lockpick"],
            traits=["Good Natured", "Small Frame"],
        )
        self.assertEqual(len(skills), 13)
        self.assertEqual(skills["Speech"], 47)
        # Small Frame raises AGI 6->7: Guns base = 2 + 14 + 3 = 19 + 15 (Tag) - 5 (Good Natured) = 29
        self.assertEqual(skills["Guns"], 29)

        with self.assertRaises(tables.ProgressionError):
            tables.compute_initial_skills(
                alloc40,
                background_name="Vault Dweller",
                tag_skills=["Speech", "Guns", "Lockpick"],
                traits=["Good Natured", "Small Frame", "Skilled"],  # > 2 traits refused
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

    def test_decoupled_karma_and_repu_16_state_matrix(self):
        # Very Evil Karma (-850) + High Fame (85) / Zero Infamy (0) -> still Idolized & Ally!
        self.assertEqual(tables.karma_tier(-850), "Very Evil")
        r_ally = tables.evaluate_faction_repu(85.0, 0.0)
        self.assertEqual(r_ally["title"], "Idolized")
        self.assertEqual(r_ally["disposition"], "Ally")
        self.assertLess(r_ally["vendor_price_mult"], 1.0)

        # Very Good Karma (+900) + Zero Fame (0) / High Infamy (90) -> Vilified & Enemy!
        self.assertEqual(tables.karma_tier(900), "Very Good")
        r_enemy = tables.evaluate_faction_repu(0.0, 90.0)
        self.assertEqual(r_enemy["title"], "Vilified")
        self.assertEqual(r_enemy["disposition"], "Enemy")

        # High Fame + High Infamy -> Wild Child!
        self.assertEqual(tables.evaluate_faction_repu(80.0, 80.0)["title"], "Wild Child")


class ProgressionLogTests(unittest.TestCase):
    def test_pass_and_fail_logs(self):
        s = core_log.summarize(SAMPLE_PASS_LOG)
        self.assertTrue(s["passed"], s["checks"])
        bad = [l.replace("disposition=Ally", "disposition=Enemy") for l in SAMPLE_PASS_LOG]
        self.assertFalse(core_log.summarize(bad)["passed"])


if __name__ == "__main__":
    unittest.main()
