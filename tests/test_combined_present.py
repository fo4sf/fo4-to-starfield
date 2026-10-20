"""Combined-core L3 planner (present.py) on the synthetic REGION_1/REGION_2 packs: placeholder names, not game facts."""
import copy
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.combined import fixtures, model, present, sim  # noqa: E402
from fo4sf.combined.model import ROLES, Squad, WorldState  # noqa: E402
from fo4sf.combined.present import Slot  # noqa: E402

SEEDS = range(8)
DAYS = 12


def world(seed=1, both=True):
    ws = WorldState(seed=seed)
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_1))
    if both:
        model.load_pack(ws, copy.deepcopy(fixtures.REGION_2))
    return ws


def quiet(ws):
    for f in ws.factions.values():
        f.aggression = 0
    return ws


def ran(seed, days=DAYS):
    ws = world(seed)
    sim.run(ws, days * 24)
    return ws


class PlanShapeTests(unittest.TestCase):
    def test_radius_is_route_distance_and_centre_is_first(self):
        ws = world(1)
        p = present.plan(ws, "market", radius_hours=6)
        self.assertEqual(p.places, ["market", "farm_a", "farm_b", "story_vault"])
        self.assertEqual(present.plan(ws, "market", radius_hours=0).places, ["market"])
        wide = present.plan(ws, "market", radius_hours=12).places
        self.assertEqual(wide[0], "market")
        self.assertIn("raider_camp", wide)                     # via story_vault, 12 hours
        self.assertIn("gate_1", wide)
        self.assertNotIn("gate_2", wide)                       # 60 hours away
        self.assertEqual(p.centre, "market")
        self.assertEqual(p.hour, ws.hour)

    def test_unknown_place_is_an_error(self):
        with self.assertRaises(KeyError):
            present.plan(world(1), "nowhere")

    def test_every_slot_is_in_radius_and_well_formed(self):
        for seed in SEEDS:
            ws = ran(seed)
            for centre in sorted(ws.places):
                p = present.plan(ws, centre, max_actors=10_000)
                dist = sim._distances(ws, centre)
                self.assertEqual(p.dropped, [])
                for s in p.slots:
                    self.assertIn(s.kind, ("garrison", "settler", "squad", "caravan"))
                    self.assertGreater(s.count, 0, s)
                    self.assertIn(s.place, p.places, s)
                    self.assertEqual(s.distance, dist[s.place], s)
                    if s.kind == "settler":
                        self.assertIn(s.role, ROLES)
                    if s.kind in ("garrison", "settler"):
                        self.assertEqual(s.faction, ws.places[s.place].holder)
                self.assertEqual(len({s.id for s in p.slots}), len(p.slots), "ids unique")

    def test_garrison_follows_holder_defence_and_strength_and_is_capped(self):
        ws = world(1)
        ws.places["ruins"].holder = None
        self.assertEqual(present.garrison_size(ws, "ruins"), 0)
        ws.places["ruins"].holder = "order"
        ws.places["ruins"].defence = 0
        ws.factions["order"].strength = 4
        expect = present.GARRISON_BASE + 4 // 2
        self.assertEqual(present.garrison_size(ws, "ruins"), expect)
        ws.places["ruins"].defence = 2
        self.assertEqual(present.garrison_size(ws, "ruins"), expect + 2 * present.GARRISON_PER_DEFENCE)
        ws.factions["order"].strength = model.STRENGTH_CAP
        ws.places["ruins"].defence = 50
        self.assertEqual(present.garrison_size(ws, "ruins"), present.GARRISON_MAX)
        slots = [s for s in present.plan(ws, "ruins").slots if s.kind == "garrison" and s.place == "ruins"]
        self.assertEqual([s.count for s in slots], [present.GARRISON_MAX])

    def test_settlers_by_role_match_roles_up_to_the_cap(self):
        ws = world(1)
        s = ws.settlements["market"]
        s.roles = {r: 0 for r in ROLES}
        s.roles["farmer"] = present.SETTLERS_PER_ROLE_MAX + 5
        s.roles["doctor"] = 1
        s.population = sum(s.roles.values())
        got = {x.role: x.count for x in present.plan(ws, "market").slots
               if x.kind == "settler" and x.place == "market"}
        self.assertEqual(got, {"farmer": present.SETTLERS_PER_ROLE_MAX, "doctor": 1})

    def test_empty_place_has_no_slots_of_its_own(self):
        ws = quiet(world(1))
        ws.squads.clear()
        p = present.plan(ws, "ruins", radius_hours=0)
        self.assertEqual(p.slots, [])
        self.assertEqual(p.actors(), 0)


class SquadSlotTests(unittest.TestCase):
    def squad(self, ws, **kw):
        q = Squad(**{"id": "s1", "faction": "raiders", "size": 5, "at": "raider_camp", "goal": "farm_a",
                     "kind": "attack", "eta": ws.hour + 12, **kw})
        ws.squads[q.id] = q
        return q

    def test_squad_appears_when_either_end_is_in_radius(self):
        ws = quiet(world(1))
        self.squad(ws)                                        # raider_camp -> farm_a, 12 hours, just left
        ids = lambda centre: [s.id for s in present.plan(ws, centre, radius_hours=0).slots  # noqa: E731
                              if s.kind == "squad"]
        self.assertEqual(ids("farm_a"), ["squad:s1"])          # goal in radius
        self.assertEqual(ids("raider_camp"), ["squad:s1"])     # origin in radius
        self.assertEqual(ids("market"), [])                    # neither

    def test_squad_sits_at_its_nearer_end_as_time_passes(self):
        ws = quiet(world(1))
        self.squad(ws)
        slot = lambda: [s for s in present.plan(ws, "farm_a", radius_hours=12).slots  # noqa: E731
                        if s.kind == "squad"][0]
        self.assertEqual(slot().place, "raider_camp")          # just departed
        ws.hour += 6                                           # half way: rounds toward the goal
        ws.squads["s1"].eta = ws.hour + 6
        self.assertEqual(slot().place, "farm_a")

    def test_squad_shown_at_in_range_end_when_nearer_end_is_outside(self):
        ws = quiet(world(1))
        self.squad(ws)                                        # near raider_camp, 12h from market; farm_a is 6h
        s = [x for x in present.plan(ws, "market", radius_hours=6, max_actors=10_000).slots
             if x.kind == "squad"][0]
        self.assertEqual(s.place, "farm_a")
        self.assertEqual(s.distance, 6)

    def test_squad_actor_count_is_capped_and_kind_kept(self):
        ws = quiet(world(1))
        self.squad(ws, size=50)
        s = [x for x in present.plan(ws, "farm_a").slots if x.kind == "squad"][0]
        self.assertEqual(s.count, present.SQUAD_ACTORS_MAX)
        self.assertEqual(s.role, "attack")
        self.assertEqual(s.faction, "raiders")

    def test_caravans_and_player_garrisons_get_slots(self):
        ws = quiet(world(1))
        ws.squads.clear()
        self.squad(ws, id="c1", faction="settlers", size=2, at="farm_a", goal="market", kind="caravan",
                   cargo={"food": 5}, eta=ws.hour + 6)
        gid = sim.player_defended(ws, "market")
        p = present.plan(ws, "market", radius_hours=6, max_actors=10_000)
        by_id = {s.id: s for s in p.slots}
        self.assertEqual(by_id["caravan:c1"].kind, "caravan")
        self.assertEqual(by_id["caravan:c1"].count, present.CARAVAN_ACTORS)
        g = by_id[f"squad:{gid}"]
        self.assertEqual((g.faction, g.role, g.place), ("player", "garrison", "market"))

    def test_running_worlds_have_squad_slots_somewhere(self):
        found = 0
        for seed in SEEDS:
            ws = ran(seed, 30)
            for q in ws.squads.values():
                p = present.plan(ws, q.at, radius_hours=0, max_actors=10_000)
                key = "caravan" if q.kind == "caravan" else "squad"
                self.assertIn(f"{key}:{q.id}", [s.id for s in p.slots])
                found += 1
        self.assertGreater(found, 0)


class BudgetTests(unittest.TestCase):
    def test_budget_is_enforced_and_drops_are_reported(self):
        ws = ran(2)
        full = present.plan(ws, "market", radius_hours=12, max_actors=10_000)
        self.assertGreater(full.actors(), 12)
        p = present.plan(ws, "market", radius_hours=12, max_actors=12)
        self.assertLessEqual(p.actors(), 12)
        self.assertEqual(sorted(s.id for s in p.slots + p.dropped), sorted(s.id for s in full.slots))
        self.assertTrue(p.dropped)
        self.assertEqual(p.slots, sorted(p.slots, key=Slot.rank))
        self.assertEqual(p.dropped, sorted(p.dropped, key=Slot.rank))

    def test_default_budget_is_the_module_constant(self):
        ws = ran(2)
        with mock.patch.object(present, "MAX_LIVE_ACTORS", 5):
            p = present.plan(ws, "market", radius_hours=12, max_actors=present.MAX_LIVE_ACTORS)
            self.assertLessEqual(p.actors(), 5)

    def test_priority_nearest_then_attackers_garrisons_settlers(self):
        ws = quiet(world(1))
        ws.squads.clear()
        ws.squads["s1"] = Squad(id="s1", faction="raiders", size=4, at="farm_a", goal="market",
                                kind="attack", eta=ws.hour + 6)
        ws.squads["c1"] = Squad(id="c1", faction="settlers", size=2, at="farm_a", goal="market",
                                kind="caravan", cargo={"food": 1}, eta=ws.hour + 6)
        p = present.plan(ws, "farm_a", radius_hours=6, max_actors=10_000)
        at_farm = [s for s in p.slots if s.distance == 0]
        kinds = [s.role if s.kind == "squad" else s.kind for s in at_farm]
        self.assertEqual(kinds[0], "attack")
        self.assertEqual(kinds[1], "garrison")
        self.assertTrue(all(k == "settler" for k in kinds[2:-1]))
        self.assertEqual(kinds[-1], "caravan")
        self.assertTrue(all(s.distance <= t.distance for s, t in zip(p.slots, p.slots[1:])))
        far = [s for s in p.slots if s.distance > 0]
        self.assertTrue(far)


class StabilityTests(unittest.TestCase):
    def test_plan_does_not_mutate_the_world(self):
        for seed in SEEDS:
            ws = ran(seed)
            before = ws.to_json()
            for centre in sorted(ws.places):
                present.plan(ws, centre, radius_hours=12)
            present.diff(present.plan(ws, "market"), present.plan(ws, "ruins"))
            self.assertEqual(ws.to_json(), before)

    def test_same_state_same_plan(self):
        for seed in SEEDS:
            a, b = ran(seed), WorldState.from_json(ran(seed).to_json())
            for centre in sorted(a.places):
                self.assertEqual(present.plan(a, centre).to_dict(), present.plan(b, centre).to_dict())

    def test_ids_survive_a_replan_and_a_save(self):
        ws = ran(3)
        p = present.plan(ws, "market", radius_hours=12)
        again = present.plan(WorldState.from_json(ws.to_json()), "market", radius_hours=12)
        self.assertEqual([s.id for s in p.slots], [s.id for s in again.slots])
        self.assertTrue(all(":" in s.id and not s.id.split(":")[-1].isdigit() or s.kind in ("squad", "caravan")
                            for s in p.slots))
        for s in p.slots:
            if s.kind in ("squad", "caravan"):
                self.assertIn(s.id.split(":")[1], ws.squads)   # the save's own squad id, not a counter


class DiffTests(unittest.TestCase):
    def test_no_old_plan_spawns_everything(self):
        p = present.plan(world(1), "market")
        d = present.diff(None, p)
        self.assertEqual((len(d.spawn), d.keep, d.dissolve), (len(p.slots), [], []))
        self.assertEqual([s.id for s in d.spawn], sorted(s.id for s in p.slots))

    def test_same_plan_keeps_everything(self):
        ws = ran(1)
        p = present.plan(ws, "market")
        spawn, keep, dissolve = present.diff(p, present.plan(ws, "market"))
        self.assertEqual((spawn, dissolve), ([], []))
        self.assertEqual(len(keep), len(p.slots))

    def test_moving_the_player_only_changes_the_difference(self):
        ws = ran(4)
        a = present.plan(ws, "market", radius_hours=6, max_actors=10_000)
        b = present.plan(ws, "farm_a", radius_hours=6, max_actors=10_000)
        d = present.diff(a, b)
        ids_a, ids_b = {s.id for s in a.slots}, {s.id for s in b.slots}
        self.assertEqual({s.id for s in d.keep}, ids_a & ids_b)
        self.assertEqual({s.id for s in d.spawn}, ids_b - ids_a)
        self.assertEqual({s.id for s in d.dissolve}, ids_a - ids_b)
        self.assertEqual(sorted(s.id for s in d.spawn) + sorted(s.id for s in d.keep),
                         sorted(s.id for s in d.spawn + d.keep))
        self.assertEqual(len(d.keep) + len(d.spawn), len(b.slots))
        self.assertEqual(len(d.keep) + len(d.dissolve), len(a.slots))

    def test_changed_count_respawns_the_slot(self):
        ws = quiet(world(1))
        a = present.plan(ws, "market")
        ws.settlements["market"].roles["farmer"] += 1
        ws.settlements["market"].population += 1
        b = present.plan(ws, "market")
        d = present.diff(a, b)
        self.assertEqual([s.id for s in d.spawn], ["settler:market:farmer"])
        self.assertEqual([s.id for s in d.dissolve], ["settler:market:farmer"])
        self.assertEqual(d.spawn[0].count, d.dissolve[0].count + 1)

    def test_time_passing_changes_only_what_moved(self):
        ws = ran(5)
        a = present.plan(ws, "market", radius_hours=12)
        sim.run(ws, 24)
        b = present.plan(ws, "market", radius_hours=12)
        d = present.diff(a, b)
        unchanged = {s.id for s in a.slots} & {s.id for s in b.slots}
        for s in d.keep:
            self.assertIn(s.id, unchanged)
        self.assertEqual(len(d.spawn) + len(d.keep), len(b.slots))


if __name__ == "__main__":
    unittest.main()
