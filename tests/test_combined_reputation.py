"""Combined-core reputation (reputation.py): synthetic fixtures only; faction names are placeholders, not game facts."""
import copy
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.combined import fixtures, model, reputation, sim  # noqa: E402
from fo4sf.combined.model import Reputation, WorldState  # noqa: E402

T = reputation.LEVEL_THRESHOLDS


def world(seed=1):
    ws = WorldState(seed=seed)
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_1))
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_2))
    return ws


class GridTests(unittest.TestCase):
    def test_gain_tiers_are_the_cited_new_vegas_values(self):
        self.assertEqual(reputation.GAIN_TIERS, (1, 2, 4, 7, 12))
        self.assertEqual([reputation.tier_points(t) for t in (0, 1, 2, 3, 4, 5, 9)], [1, 1, 2, 4, 7, 12, 12])
        self.assertEqual([reputation.tier_for(a, 10) for a in (-5, 0, 9, 10, 20, 30, 40, 400)],
                         [1, 1, 1, 2, 4, 7, 12, 12])
        self.assertIs(sim.REP_TIERS, reputation.GAIN_TIERS)
        self.assertEqual(sim._rep_tier(20), 4)

    def test_levels_follow_the_thresholds(self):
        self.assertEqual(len(T), 4)
        self.assertEqual(T[0], 0)
        self.assertEqual(reputation.level(0), 0)
        self.assertEqual(reputation.level(-3), 0)
        for lvl, t in enumerate(T):
            self.assertEqual(reputation.level(t), lvl)
            if lvl:
                self.assertEqual(reputation.level(t - 1), lvl - 1)
        self.assertEqual(reputation.level(10 ** 6), 3)

    def test_named_states_on_the_two_pure_axes(self):
        self.assertEqual(reputation.state(Reputation()), "Neutral")
        self.assertEqual([reputation.state(Reputation(fame=t)) for t in T],
                         ["Neutral", "Accepted", "Liked", "Idolized"])
        self.assertEqual([reputation.state(Reputation(infamy=t)) for t in T],
                         ["Neutral", "Shunned", "Hated", "Vilified"])

    def test_mixed_cells_are_distinct_placeholders(self):
        names = {reputation.state(Reputation(fame=T[f], infamy=T[i])) for f in range(1, 4) for i in range(1, 4)}
        self.assertEqual(len(names), 9)
        self.assertTrue(all(n.startswith("mixed_") for n in names))
        self.assertFalse(names & set(reputation.FAME_STATES) | names & set(reputation.INFAMY_STATES))
        # the two cited mixed names are recorded but not placed in a cell (the note gives no cells)
        self.assertEqual(reputation.MIXED_NAMES_FROM_NOTE, ("Smiling Troublemaker", "Dark Hero"))
        self.assertFalse(names & set(reputation.MIXED_NAMES_FROM_NOTE))


class EffectsTests(unittest.TestCase):
    def effects(self, fame=0, infamy=0):
        ws = world()
        ws.reputation["settlers"] = Reputation(fame=fame, infamy=infamy)
        return reputation.effects(ws, "settlers")

    def test_neutral_has_no_effects(self):
        e = self.effects()
        self.assertEqual((e.state, e.price_multiplier, e.refuses_service, e.hostile_on_sight),
                         ("Neutral", 1.0, False, False))

    def test_fame_lowers_prices_and_infamy_raises_them(self):
        prices = [self.effects(fame=t).price_multiplier for t in T]
        self.assertEqual(prices, sorted(prices, reverse=True))
        self.assertLess(prices[-1], 1.0)
        marks = [self.effects(infamy=t).price_multiplier for t in T]
        self.assertEqual(marks, sorted(marks))
        self.assertGreater(marks[-1], 1.0)

    def test_service_and_hostility_tiers(self):
        self.assertFalse(self.effects(infamy=T[1]).refuses_service)
        self.assertTrue(self.effects(infamy=T[2]).refuses_service)
        self.assertFalse(self.effects(infamy=T[2]).hostile_on_sight)
        vilified = self.effects(infamy=T[3])
        self.assertEqual(vilified.state, "Vilified")
        self.assertTrue(vilified.refuses_service and vilified.hostile_on_sight)
        # a mixed standing with enough fame is still served
        self.assertFalse(self.effects(fame=T[2], infamy=T[2]).refuses_service)
        self.assertTrue(self.effects(fame=T[3], infamy=T[3]).hostile_on_sight)


class GainTests(unittest.TestCase):
    def test_add_clamps_at_zero(self):
        ws = world()
        reputation.add(ws, "order", fame=3, infamy=-7)
        self.assertEqual(ws.reputation["order"], Reputation(fame=3, infamy=0))
        reputation.add(ws, "order", fame=-10)
        self.assertEqual(ws.reputation["order"].fame, 0)

    def test_helped_routes_fame_and_enemy_infamy(self):
        ws = world()
        reputation.helped(ws, "settlers", 10)
        self.assertEqual(ws.reputation["settlers"].fame, 10)
        self.assertEqual(ws.reputation["raiders"].infamy, 10 // reputation.ENEMY_INFAMY_DIVISOR)
        self.assertEqual(ws.reputation["slavers"].infamy, 0)     # slavers hate settlers, not the other way round
        self.assertEqual(ws.reputation["order"].infamy, 0)

    def test_sim_player_hooks_go_through_reputation(self):
        ws = world()
        sim.player_helped(ws, "settlers", 10)
        self.assertEqual(ws.reputation["settlers"].fame, 10)
        self.assertEqual(ws.reputation["raiders"].infamy, 5)
        sim.player_traded(ws, "farm_b", {"food": 20})
        self.assertEqual(ws.reputation["settlers"].fame, 10 + reputation.tier_for(20, sim.TRADE_GOODS_PER_TIER))
        sim.player_defended(ws, "farm_a")
        self.assertEqual(ws.reputation["settlers"].fame, 14 + sim.PLAYER_DEFENCE_FAME)


class RegionalTests(unittest.TestCase):
    def test_default_world_has_no_regional_layer_and_falls_back(self):
        ws = world()
        self.assertEqual(ws.regional_reputation, {})
        ws.reputation["settlers"].fame = 12
        self.assertIs(reputation.standing(ws, "settlers"), ws.reputation["settlers"])
        self.assertIs(reputation.standing(ws, "settlers", "R2"), ws.reputation["settlers"])
        self.assertEqual(reputation.effects(ws, "settlers", "R2").state, "Accepted")

    def test_open_region_copies_then_overrides(self):
        ws = world()
        ws.reputation["settlers"].fame = 12
        layer = reputation.open_region(ws, "R2", "settlers")
        self.assertEqual(layer, Reputation(fame=12, infamy=0))
        self.assertIsNot(layer, ws.reputation["settlers"])
        self.assertIs(reputation.open_region(ws, "R2", "settlers"), layer)   # idempotent
        layer.infamy = 30
        self.assertEqual(reputation.state(reputation.standing(ws, "settlers", "R2")), "mixed_fame1_infamy2")
        self.assertEqual(reputation.state(reputation.standing(ws, "settlers", "R1")), "Accepted")
        self.assertEqual(reputation.state(reputation.standing(ws, "settlers")), "Accepted")
        self.assertTrue(reputation.effects(ws, "settlers", "R2").refuses_service)
        self.assertFalse(reputation.effects(ws, "settlers").refuses_service)

    def test_gains_carry_across_regions(self):
        ws = world()
        reputation.open_region(ws, "R2", "settlers")
        reputation.open_region(ws, "R2", "raiders")
        sim.player_helped(ws, "settlers", 10)
        self.assertEqual(ws.reputation["settlers"].fame, 10)
        self.assertEqual(ws.regional_reputation["R2"]["settlers"].fame, 10)
        self.assertEqual(ws.regional_reputation["R2"]["raiders"].infamy, 5)

    def test_regional_layer_round_trips_and_is_sorted(self):
        ws = world()
        reputation.open_region(ws, "R2", "settlers").fame = 7
        text = ws.to_json()
        self.assertEqual(json.loads(text)["regional_reputation"], {"R2": {"settlers": {"fame": 7, "infamy": 0}}})
        back = WorldState.from_json(text)
        self.assertEqual(back, ws)
        self.assertEqual(back.to_json(), text)


class DeterminismTests(unittest.TestCase):
    def test_reputation_calls_keep_replay(self):
        runs = []
        for _ in range(2):
            ws = world(4)
            reputation.open_region(ws, "R2", "settlers")
            sim.run(ws, 10 * 24)
            sim.player_helped(ws, "settlers", 25)
            reputation.add(ws, "raiders", infamy=60)
            sim.run(ws, 30 * 24)
            runs.append(ws.to_json())
        self.assertEqual(runs[0], runs[1])
        ws = WorldState.from_json(runs[0])
        self.assertEqual(reputation.effects(ws, "raiders").hostile_on_sight, True)
        self.assertEqual(reputation.effects(ws, "settlers", "R2").state, "Liked")


if __name__ == "__main__":
    unittest.main()
