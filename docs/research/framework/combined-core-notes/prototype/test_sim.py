"""Run: python3 -m unittest discover -s <this folder> (stdlib only)."""
import copy
import unittest

from scenario import REGION_1, REGION_2
from sim import news_for, player_helped, run
from worldstate import WorldState, load_pack


def world(seed=7, packs=(REGION_1,)):
    ws = WorldState(seed=seed)
    for p in packs:
        load_pack(ws, copy.deepcopy(p))
    return ws


class SimTests(unittest.TestCase):
    def test_deterministic(self):
        a, b = world(), world()
        run(a, 24 * 30)
        run(b, 24 * 30)
        self.assertEqual(a.to_json(), b.to_json())

    def test_resume_from_save_replays_exactly(self):
        straight = world()
        run(straight, 24 * 20)
        part = world()
        run(part, 24 * 7)
        resumed = WorldState.from_json(part.to_json())
        run(resumed, 24 * 13)
        self.assertEqual(straight.to_json(), resumed.to_json())

    def test_story_and_home_places_never_change_hands(self):
        for seed in range(20):
            ws = world(seed)
            run(ws, 24 * 60)
            self.assertEqual(ws.places["story_vault"].holder, "settlers")
            for f in ws.factions.values():
                self.assertEqual(ws.places[f.home].holder, f.id)

    def test_world_actually_changes(self):
        taken = 0
        for seed in range(20):
            ws = world(seed)
            run(ws, 24 * 60)
            taken += sum(e["kind"] == "place_taken" for e in ws.events)
        self.assertGreater(taken, 0)

    def test_values_stay_in_range(self):
        ws = world()
        run(ws, 24 * 90)
        for f in ws.factions.values():
            self.assertGreaterEqual(f.strength, 0)
        for s in ws.settlements.values():
            self.assertGreaterEqual(s.population, 0)
            self.assertTrue(0 <= s.morale <= 100)
            self.assertEqual(sum(s.roles.values()), s.population)
            self.assertTrue(all(v >= 0 for v in s.stock.values()))

    def test_one_region_runs_alone_and_a_second_plugs_in(self):
        ws = world(packs=(REGION_1, REGION_2))
        run(ws, 24 * 30)
        self.assertIn("river_town", ws.settlements)

    def test_packs_only_add(self):
        ws = world()
        with self.assertRaises(ValueError):
            load_pack(ws, copy.deepcopy(REGION_1))

    def test_news_travels_at_route_speed(self):
        ws = world(packs=(REGION_1, REGION_2))
        ws.hour = 100
        ws.events.append({"hour": 100, "kind": "test", "place": "market", "region": "R1"})
        self.assertTrue(news_for(ws, "market"))
        self.assertFalse(news_for(ws, "river_town", since=100))
        ws.hour = 100 + 12 + 48 + 6
        self.assertTrue(news_for(ws, "river_town", since=100))

    def test_reputation_spills_to_enemies(self):
        ws = world()
        player_helped(ws, "settlers", 10)
        self.assertEqual(ws.reputation["settlers"].fame, 10)
        self.assertEqual(ws.reputation["raiders"].infamy, 5)
        self.assertEqual(ws.reputation["order"].infamy, 0)


if __name__ == "__main__":
    unittest.main()
