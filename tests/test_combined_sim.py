"""Combined-core L2 simulation: synthetic REGION_1/REGION_2 packs only, no game data (placeholder names, not facts)."""
import copy
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.combined import fixtures, model, sim  # noqa: E402
from fo4sf.combined.model import ROLES, Squad, WorldState  # noqa: E402

SEEDS = range(20)
DAYS = 90


def world(seed=1, both=True):
    ws = WorldState(seed=seed)
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_1))
    if both:
        model.load_pack(ws, copy.deepcopy(fixtures.REGION_2))
    return ws


def quiet(ws):
    """No faction launches attacks; keeps a test's world still."""
    for f in ws.factions.values():
        f.aggression = 0
    return ws


def kinds(ws, kind):
    return [e for e in ws.events if e["kind"] == kind]


class DeterminismTests(unittest.TestCase):
    def test_same_seed_same_world(self):
        for seed in SEEDS:
            a, b = world(seed), world(seed)
            sim.run(a, DAYS * 24)
            sim.run(b, DAYS * 24)
            self.assertEqual(a.to_json(), b.to_json())

    def test_seeds_differ(self):
        a, b = world(1), world(2)
        sim.run(a, DAYS * 24)
        sim.run(b, DAYS * 24)
        self.assertNotEqual(a.events, b.events)

    def test_save_mid_run_and_resume_replays_exactly(self):
        for seed in (3, 7, 11):
            a = world(seed)
            sim.run(a, 45 * 24)
            saved = a.to_json()
            sim.run(a, 45 * 24)
            b = WorldState.from_json(saved)
            sim.run(b, 45 * 24)
            self.assertEqual(a.to_json(), b.to_json())
            self.assertEqual(a.hour, DAYS * 24)


class InvariantTests(unittest.TestCase):
    def check(self, ws, start):
        for pid, pl in ws.places.items():
            if pl.story_lock:
                self.assertEqual(pl.holder, start.places[pid].holder, pid)
        for fid, f in ws.factions.items():
            self.assertEqual(ws.places[f.home].holder, fid, f"{fid} lost its home")
            self.assertTrue(0 <= f.strength <= sim.STRENGTH_CAP, (fid, f.strength))
        for sid, s in ws.settlements.items():
            self.assertTrue(0 <= s.population <= s.beds, (sid, s.population))
            self.assertTrue(0 <= s.morale <= 100, (sid, s.morale))
            self.assertTrue(0 <= s.stage <= 4, (sid, s.stage))
            self.assertEqual(set(s.roles), set(ROLES))
            self.assertEqual(sum(s.roles.values()), s.population, (sid, s.roles))
            self.assertTrue(all(v >= 0 for v in s.roles.values()), (sid, s.roles))
            self.assertTrue(all(v >= 0 for v in s.stock.values()), (sid, s.stock))
        for q in ws.squads.values():
            self.assertGreater(q.size, 0, q)
            self.assertIn(q.at, ws.places)
            self.assertIn(q.goal, ws.places)

    def test_invariants_hold_every_tick_for_20_seeds_x_90_days(self):
        for seed in SEEDS:
            ws = world(seed)
            start = copy.deepcopy(ws)
            for _ in range(DAYS * 24 // sim.TICK_HOURS):
                sim.tick(ws)
                self.check(ws, start)

    def test_one_region_runs_alone_and_a_second_plugs_in(self):
        one = world(5, both=False)
        sim.run(one, DAYS * 24)
        self.assertTrue(all(e["region"] == "R1" for e in one.events))
        two = world(5)
        sim.run(two, DAYS * 24)
        self.assertEqual({e["region"] for e in two.events} & {"R1", "R2"}, {"R1", "R2"})

    def test_world_keeps_moving(self):
        ws = world(0)
        sim.run(ws, DAYS * 24)
        for kind in ("attack_launched", "caravan_arrived", "settler_arrived", "place_taken"):
            self.assertTrue(kinds(ws, kind), kind)


class UpkeepTests(unittest.TestCase):
    def test_strength_never_leaves_range(self):
        for seed in SEEDS:
            ws = world(seed)
            for _ in range(DAYS * 24 // sim.TICK_HOURS):
                sim.tick(ws)
                for f in ws.factions.values():
                    self.assertTrue(0 <= f.strength <= sim.STRENGTH_CAP, (seed, f))

    def test_upkeep_is_a_sink_and_never_goes_below_zero(self):
        ws = quiet(world(1))
        ws.factions["order"].strength = 1          # holds one place, pays 1 a day
        with mock.patch.object(sim, "STRENGTH_INCOME_PER_PLACE", 0):
            sim.run(ws, 24)
            self.assertEqual(ws.factions["order"].strength, 0)
            sim.run(ws, 24)
            self.assertEqual(ws.factions["order"].strength, 0)
        for f in ws.factions.values():
            self.assertGreaterEqual(f.strength, 0)

    def test_more_territory_costs_more(self):
        ws = quiet(world(1))
        for pid in ("ruins", "gate_1"):
            ws.places[pid].holder = "order"
        held = [p for p, pl in ws.places.items() if pl.holder == "order"]
        before = ws.factions["order"].strength = 20
        with mock.patch.object(sim, "STRENGTH_INCOME_PER_PLACE", 0):
            sim.run(ws, 24)
        self.assertEqual(ws.factions["order"].strength, before - sim.UPKEEP_PER_PLACE * len(held))


class TerritoryTests(unittest.TestCase):
    def test_retake_happens_in_some_seed_and_is_preferred(self):
        retakes = 0
        for seed in SEEDS:
            ws = world(seed)
            sim.run(ws, DAYS * 24)
            for e in kinds(ws, "place_taken"):
                if e["retaken"]:
                    retakes += 1
                    earlier = [x for x in kinds(ws, "place_taken") if x["place"] == e["place"]
                               and x["hour"] < e["hour"] and x["previous"] == e["faction"]]
                    self.assertTrue(earlier, e)
        self.assertGreater(retakes, 0)

    def test_lost_places_read_from_events(self):
        ws = world(1)
        ws.events.append({"hour": 0, "kind": "place_taken", "place": "farm_a", "region": "R1",
                          "faction": "raiders", "previous": "settlers", "retaken": False})
        ws.places["farm_a"].holder = "raiders"
        self.assertEqual(sim._lost_places(ws, "settlers"), {"farm_a"})
        ws.places["farm_a"].holder = "settlers"
        self.assertEqual(sim._lost_places(ws, "settlers"), set())

    def test_capture_hurts_the_settlement(self):
        ws = quiet(world(1))
        s = ws.settlements["farm_a"]
        s.morale = 90
        ws.places["farm_a"].defence = 0
        s.roles = {r: 0 for r in ROLES}
        s.roles["farmer"] = s.population = 4
        s.stock["ammo"] = 0
        ws.factions["settlers"].strength = 0
        ws.squads["s1"] = Squad(id="s1", faction="raiders", size=500, at="raider_camp", goal="farm_a",
                                kind="attack", eta=sim.TICK_HOURS)
        sim.tick(ws)
        self.assertEqual(ws.places["farm_a"].holder, "raiders")
        self.assertEqual(s.population, 2)
        self.assertEqual(sum(s.roles.values()), 2)
        self.assertLessEqual(s.morale, 32)      # capped at 30, then the same tick's settlement step may add 2


class RaidTests(unittest.TestCase):
    def test_raiding_happens_in_some_seed_and_loses_cargo(self):
        raids = 0
        for seed in SEEDS:
            ws = world(seed)
            sim.run(ws, DAYS * 24)
            for e in kinds(ws, "caravan_raided"):
                raids += 1
                self.assertTrue(sim._hostile(ws, e["raider"], e["faction"]), e)
                self.assertTrue(e["cargo"])
        self.assertGreater(raids, 0)

    def test_raider_must_hold_a_place_next_to_the_route(self):
        ws = world(1)
        q = Squad(id="c1", faction="settlers", size=2, at="farm_a", goal="market", kind="caravan",
                  cargo={"food": 5}, eta=6)
        always = mock.patch.object(sim, "RAID_CHANCE_CAP", 1.0)
        rich = mock.patch.object(sim, "RAID_CHANCE_PER_STRENGTH", 1.0)
        with always, rich:
            self.assertEqual(sim._raider(ws, q, sim._rng(ws)), "raiders")   # raider_camp touches farm_a
            ws.places["raider_camp"].holder = "order"                        # order is friendly
            self.assertIsNone(sim._raider(ws, q, sim._rng(ws)))
            far = Squad(id="c2", faction="traders", size=2, at="gate_2", goal="river_town",
                        kind="caravan", cargo={"food": 5}, eta=6)
            self.assertEqual(sim._raider(ws, far, sim._rng(ws)), "slavers")  # slaver_pit touches river_town


class PlayerHookTests(unittest.TestCase):
    def test_player_helped_is_fame_plus_enemy_infamy(self):
        ws = world(1)
        sim.player_helped(ws, "settlers", 10)
        self.assertEqual(ws.reputation["settlers"].fame, 10)
        self.assertEqual(ws.reputation["raiders"].infamy, 5)
        self.assertEqual(ws.reputation["order"].infamy, 0)

    def test_player_defended_adds_defence_once(self):
        ws = quiet(world(1))
        base = sim._defence(ws, "farm_a")
        gid = sim.player_defended(ws, "farm_a")
        self.assertEqual(ws.squads[gid].kind, "garrison")
        self.assertEqual(sim._defence(ws, "farm_a"), base + sim.PLAYER_DEFENCE_BONUS)
        self.assertEqual(ws.reputation["settlers"].fame, sim.PLAYER_DEFENCE_FAME)
        self.assertTrue(kinds(ws, "player_defended"))
        ws.squads["s1"] = Squad(id="s1", faction="raiders", size=5, at="raider_camp", goal="farm_a",
                                kind="attack", eta=sim.TICK_HOURS)
        sim.tick(ws)
        self.assertNotIn(gid, ws.squads)                      # spent on that attack
        self.assertEqual(sim._defence(ws, "farm_a") <= base + 5, True)
        self.assertTrue(kinds(ws, "attack_failed") or kinds(ws, "place_taken"))

    def test_player_defence_expires_and_survives_a_save(self):
        ws = quiet(world(1))
        gid = sim.player_defended(ws, "farm_a")
        ws = WorldState.from_json(ws.to_json())
        self.assertIn(gid, ws.squads)
        sim.run(ws, sim.PLAYER_DEFENCE_HOURS)
        self.assertNotIn(gid, ws.squads)

    def test_player_traded_moves_goods_and_earns_tiered_fame(self):
        ws = world(1)
        s = ws.settlements["farm_b"]
        food, scrap = s.stock["food"], s.stock["scrap"]
        moved = sim.player_traded(ws, "farm_b", {"food": 20, "scrap": -100})
        self.assertEqual(moved, {"food": 20, "scrap": -scrap})
        self.assertEqual(s.stock["food"], food + 20)
        self.assertEqual(s.stock["scrap"], 0)
        self.assertEqual(ws.reputation["settlers"].fame, sim._rep_tier(20))
        self.assertEqual(sim._rep_tier(20), sim.REP_TIERS[2])
        sim.player_traded(ws, "farm_b", {"food": -1})         # taking earns nothing
        self.assertEqual(ws.reputation["settlers"].fame, sim.REP_TIERS[2])
        with self.assertRaises(ValueError):
            sim.player_traded(ws, "farm_b", {"caps": 1})

    def test_hooks_keep_determinism(self):
        runs = []
        for _ in range(2):
            ws = world(4)
            sim.run(ws, 10 * 24)
            sim.player_defended(ws, "market")
            sim.player_traded(ws, "market", {"food": 30})
            sim.run(ws, 30 * 24)
            runs.append(ws.to_json())
        self.assertEqual(runs[0], runs[1])


class NewsTests(unittest.TestCase):
    def test_news_travels_along_routes(self):
        ws = world(1)
        sim.run(ws, 24)
        here = sim.news_for(ws, "market")
        self.assertTrue(here)
        self.assertTrue(all(e["hour"] <= ws.hour for e in here))
        far = [e for e in sim.news_for(ws, "slaver_pit") if e["region"] == "R1"]
        self.assertEqual(far, [])                              # 60 route hours away, 24 hours in


if __name__ == "__main__":
    unittest.main()
