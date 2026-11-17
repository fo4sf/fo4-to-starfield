"""Unit tests for CF-8 Combat Core (src/fo4sf/combat/, scripts/combat/, dotnet/CombatCore/)."""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO / "src", REPO / "scripts" / "combat"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import make_combat_core  # noqa: E402
from fo4sf.combat import (  # noqa: E402
    AMMO_SUBTYPES,
    ARCHETYPE_ZONE_MULTS,
    CALIBRE_FAMILIES,
    RELOADING_BENCH_RECIPES,
    TITLE_COMBAT_TABLES,
    ZONES,
    compute_ballistic_dt_dr,
    compute_vats_ap_cost,
    compute_vats_hit_chance,
    compute_zone_hit,
    cycle_ammo_subtype,
    evaluate_cripple_state,
    parse_combat_log,
    resolve_limb_cure,
    resolve_vats_shot,
)


class FakeRunningSystem:
    def pids(self, exe_name: str):
        return [4242]


class CombatTablesAndFormulasTests(unittest.TestCase):
    def test_unified_zones_and_all_title_tables_present(self):
        self.assertEqual(len(ZONES), 8)
        for arch in ("human", "robot", "creature"):
            self.assertEqual(set(ARCHETYPE_ZONE_MULTS[arch].keys()), set(ZONES))
        for title in ("FO1", "FO2", "FOT", "FO3", "FNV", "FO4", "FO76", "FO4SF"):
            self.assertIn(title, TITLE_COMBAT_TABLES)

    def test_zone_multipliers_across_human_robot_and_creature(self):
        head = compute_zone_hit(24.0, "head", archetype="human")
        torso = compute_zone_hit(24.0, "torso", archetype="human")
        leg = compute_zone_hit(24.0, "left_leg", archetype="human")
        self.assertAlmostEqual(head["applied_damage"], 48.0)
        self.assertAlmostEqual(torso["applied_damage"], 24.0)
        self.assertAlmostEqual(leg["applied_damage"], 20.4)

        robot_chassis = compute_zone_hit(24.0, "torso", archetype="robot")
        robot_inhib = compute_zone_hit(24.0, "special_core", archetype="robot")
        self.assertLess(robot_chassis["applied_damage"], torso["applied_damage"])
        self.assertGreater(robot_inhib["applied_damage"], torso["applied_damage"])

        creature_belly = compute_zone_hit(24.0, "special_core", archetype="creature")
        self.assertAlmostEqual(creature_belly["zone_mult"], 1.85)

    def test_cripple_penalties_slow_walk_aim_sway_and_weapon_drop(self):
        healthy = evaluate_cripple_state({"left_leg": 100.0, "right_arm": 100.0})
        self.assertFalse(healthy["slow_walk"])
        self.assertEqual(healthy["speed_mult_delta"], 0.0)
        self.assertFalse(healthy["drop_weapon"])

        one_leg = evaluate_cripple_state({"left_leg": 0.0, "right_leg": 80.0})
        self.assertTrue(one_leg["slow_walk"])
        self.assertEqual(one_leg["speed_mult_delta"], -40.0)

        two_legs = evaluate_cripple_state({"left_leg": 0.0, "right_leg": 0.0})
        self.assertEqual(two_legs["speed_mult_delta"], -60.0)

        weapon_arm = evaluate_cripple_state({"right_arm": 0.0, "head": 0.0}, prev_right_arm_crippled=False)
        self.assertTrue(weapon_arm["drop_weapon"])
        self.assertEqual(weapon_arm["aim_sway_penalty"], 55.0)
        self.assertEqual(weapon_arm["perception_delta"], -4.0)

        already_crippled = evaluate_cripple_state({"right_arm": 0.0}, prev_right_arm_crippled=True)
        self.assertFalse(already_crippled["drop_weapon"])

    def test_stimpak_vs_hardcore_doctors_bag_cure(self):
        damaged = {"left_leg": 0.0, "right_arm": 15.0}
        cured_norm, hp_norm, _ = resolve_limb_cure(damaged, "stimpak", hardcore_enabled=False)
        self.assertTrue(cured_norm)
        self.assertEqual(hp_norm["left_leg"], 100.0)

        cured_hc_stim, hp_hc_stim, reason = resolve_limb_cure(damaged, "stimpak", hardcore_enabled=True)
        self.assertFalse(cured_hc_stim)
        self.assertEqual(hp_hc_stim["left_leg"], 0.0)
        self.assertIn("doctors_bag", reason)

        cured_hc_bag, hp_hc_bag, _ = resolve_limb_cure(damaged, "doctors_bag", hardcore_enabled=True)
        self.assertTrue(cured_hc_bag)
        self.assertEqual(hp_hc_bag["left_leg"], 100.0)
        self.assertEqual(hp_hc_bag["right_arm"], 100.0)

    def test_new_vegas_ammo_subtypes_against_soft_and_high_dt_targets(self):
        std, ap, jhp, plus_p = AMMO_SUBTYPES["standard_ballistic"]
        # Against unarmored target (DT=0, DR=0): JHP > +P > Standard > AP
        soft_std = compute_ballistic_dt_dr(24.0, target_dt=0.0, subtype=std)["final_damage"]
        soft_ap = compute_ballistic_dt_dr(24.0, target_dt=0.0, subtype=ap)["final_damage"]
        soft_jhp = compute_ballistic_dt_dr(24.0, target_dt=0.0, subtype=jhp)["final_damage"]
        soft_pp = compute_ballistic_dt_dr(24.0, target_dt=0.0, subtype=plus_p)["final_damage"]
        self.assertGreater(soft_jhp, soft_pp)
        self.assertGreater(soft_pp, soft_std)
        self.assertGreater(soft_std, soft_ap)

        # Against High-DT armored target (DT=18, DR=15%): AP penetrates 15 DT and strongly beats Standard & JHP
        arm_std = compute_ballistic_dt_dr(24.0, target_dt=18.0, target_dr_pct=15.0, subtype=std)["final_damage"]
        arm_ap = compute_ballistic_dt_dr(24.0, target_dt=18.0, target_dr_pct=15.0, subtype=ap)["final_damage"]
        arm_jhp = compute_ballistic_dt_dr(24.0, target_dt=18.0, target_dr_pct=15.0, subtype=jhp)["final_damage"]
        self.assertAlmostEqual(arm_std, 4.8)
        self.assertAlmostEqual(arm_ap, 16.38)
        self.assertAlmostEqual(arm_jhp, 7.92)
        self.assertGreater(arm_ap, arm_std * 3.0)
        self.assertGreater(arm_ap, arm_jhp * 2.0)

        # Shotgun Buckshot vs Slug against DT=18, DR=15%
        buck, slug, _, _ = AMMO_SUBTYPES["shotgun"]
        sg_buck = compute_ballistic_dt_dr(30.0, target_dt=18.0, target_dr_pct=15.0, subtype=buck)["final_damage"]
        sg_slug = compute_ballistic_dt_dr(30.0, target_dt=18.0, target_dr_pct=15.0, subtype=slug)["final_damage"]
        self.assertGreater(sg_slug, sg_buck * 2.5)

    def test_ammo_cycle_and_reloading_bench_recipes_hook_workshop_ires(self):
        self.assertEqual(cycle_ammo_subtype(0, "standard_ballistic").key, "ap")
        self.assertEqual(cycle_ammo_subtype(3, "standard_ballistic").key, "standard")
        self.assertEqual(cycle_ammo_subtype(0, "shotgun").key, "slug")
        self.assertEqual(len(CALIBRE_FAMILIES), 5)
        self.assertEqual(len(RELOADING_BENCH_RECIPES), 6)
        for rcpe in RELOADING_BENCH_RECIPES:
            self.assertEqual(rcpe["bench_keyword"], "WorkbenchIndustrialKeyword")
            self.assertGreaterEqual(len(rcpe["ires_costs"]), 2)

    def test_vats_ap_hit_chance_and_shot_resolution(self):
        self.assertEqual(compute_vats_ap_cost("rifle", "torso"), 28)
        self.assertEqual(compute_vats_ap_cost("rifle", "head"), 32)
        near_torso = compute_vats_hit_chance(5.0, weapon_skill=75.0, perception=8.0, zone="torso")
        far_head = compute_vats_hit_chance(25.0, weapon_skill=35.0, perception=4.0, zone="head", crippled_arms=1)
        self.assertEqual(near_torso, 95)
        self.assertGreater(near_torso, far_head)
        self.assertGreaterEqual(far_head, 5)

        no_ap = resolve_vats_shot(10.0, "rifle", "head", 8.0, 60.0, 7.0, roll_1_to_100=20, base_damage=24.0)
        self.assertFalse(no_ap["queued"])
        self.assertEqual(no_ap["reason"], "insufficient_ap")

        hit = resolve_vats_shot(100.0, "rifle", "head", 6.0, 70.0, 7.0, roll_1_to_100=25, base_damage=24.0)
        self.assertTrue(hit["queued"])
        self.assertTrue(hit["hit"])
        self.assertAlmostEqual(hit["applied_damage"], 48.0)
        self.assertAlmostEqual(hit["ap_after"], 68.0)

    def test_log_parser_recognizes_full_pc_card_session(self):
        sample = "\n".join([
            "[FO4SF_Combat] PASS step=zone_hit zone=head mult=2.0 applied=48.0 subtype=standard",
            "[FO4SF_Combat] PASS step=zone_hit zone=torso mult=1.0 applied=24.0 subtype=standard",
            "[FO4SF_Combat] PASS step=zone_hit zone=left_arm mult=0.85 applied=20.4 subtype=standard",
            "[FO4SF_Combat] PASS step=zone_hit zone=right_arm mult=0.85 applied=20.4 subtype=standard",
            "[FO4SF_Combat] PASS step=zone_hit zone=left_leg mult=0.85 applied=20.4 subtype=standard",
            "[FO4SF_Combat] PASS step=zone_hit zone=right_leg mult=0.85 applied=20.4 subtype=standard",
            "[FO4SF_Combat] PASS step=high_dt_hit subtype=standard target_dt=18.0 eff_dt=18.0 damage=4.8",
            "[FO4SF_Combat] PASS step=ammo_cycle calibre=cal_0 slot=1 subtype=ap",
            "[FO4SF_Combat] PASS step=high_dt_hit subtype=ap target_dt=18.0 eff_dt=3.0 damage=16.38",
            "[FO4SF_Combat] PASS step=limb_crippled zone=left_leg speed_delta=-40.0 sway=0.0",
            "[FO4SF_Combat] PASS step=limb_cure item=stimpak hardcore=1 cured=0",
            "[FO4SF_Combat] PASS step=limb_cure item=doctors_bag hardcore=1 cured=1",
            "[FO4SF_Combat] PASS step=vats_shot slow_time=1 zone=head ap_cost=32 chance=54 queued=1",
        ])
        rep = parse_combat_log(sample)
        self.assertTrue(rep.zones_pass)
        self.assertTrue(rep.ammo_dt_pass)
        self.assertTrue(rep.cripple_cure_pass)
        self.assertTrue(rep.vats_pass)
        self.assertTrue(rep.all_pass)


class CombatContractAndStagerTests(unittest.TestCase):
    def test_csharp_and_papyrus_properties_match_in_exact_order(self):
        cs = (REPO / "dotnet" / "CombatCore" / "Program.cs").read_text(encoding="utf-8")
        psc = (REPO / "scripts" / "combat" / "FO4SF_CombatQuest.psc").read_text(encoding="utf-8")

        m_block = re.search(r"PropNames\s*=\s*\{([^}]+)\}", cs, re.S)
        self.assertIsNotNone(m_block)
        cs_props = re.findall(r'"(\w+)"', m_block.group(1))
        psc_props = re.findall(r"^\w+\s+Property\s+(\w+)\s+Auto\s+Const\b", psc, re.M)
        self.assertEqual(cs_props, psc_props)
        self.assertEqual(len(cs_props), 43)

    def test_stage_refuses_when_starfield_is_running(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(make_combat_core.CombatStageRefused) as ctx:
                make_combat_core.stage_combat_core(
                    os.path.join(td, "stage"),
                    td,
                    system=FakeRunningSystem(),
                )
            self.assertIn("running", str(ctx.exception))

    @unittest.skipUnless(os.environ.get("FO4SF_DOTNET_TESTS") == "1", "set FO4SF_DOTNET_TESTS=1 to run dotnet selftest")
    def test_dotnet_combat_core_selftest(self):
        proj = REPO / "dotnet" / "CombatCore"
        with tempfile.TemporaryDirectory() as td:
            r = subprocess.run(["dotnet", "run", "--project", str(proj), "--", "selftest", td],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{r.stdout}\n{r.stderr}")
            self.assertIn("selftest: ok", r.stdout)


if __name__ == "__main__":
    unittest.main()
