"""Combined-core L4 settlement management (manage.py): synthetic REGION_1/REGION_2 packs only, placeholder names."""
import copy
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.combined import fixtures, manage, model, sim  # noqa: E402
from fo4sf.combined.model import GOODS, ROLES, SCHEMA_VERSION, Squad, WorldState  # noqa: E402

SEEDS = range(10)
DAYS = 60


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


def kinds(ws, kind):
    return [e for e in ws.events if e["kind"] == kind]


class AssignRoleTests(unittest.TestCase):
    def test_moves_settlers_and_logs_an_event(self):
        ws = world()
        roles = manage.assign_role(ws, "farm_a", "farmer", "guard", 2)
        self.assertEqual(roles["farmer"], 1)
        self.assertEqual(roles["guard"], 3)
        self.assertEqual(sum(roles.values()), ws.settlements["farm_a"].population)
        e = kinds(ws, "roles_changed")[0]
        self.assertEqual((e["place"], e["region"], e["from_role"], e["to_role"], e["n"]),
                         ("farm_a", "R1", "farmer", "guard", 2))

    def test_validation(self):
        ws = world()
        for args in (("ruins", "farmer", "guard", 1), ("farm_a", "pilot", "guard", 1),
                     ("farm_a", "farmer", "farmer", 1), ("farm_a", "farmer", "guard", 0),
                     ("farm_a", "farmer", "guard", 4), ("farm_a", "farmer", "guard", True)):
            with self.assertRaises(ValueError, msg=args):
                manage.assign_role(ws, *args)
        self.assertEqual(ws.settlements["farm_a"].roles["farmer"], 3)   # nothing moved on failure
        self.assertEqual(ws.events, [])


class AddBedsTests(unittest.TestCase):
    def test_adds_beds_up_to_the_cap(self):
        ws = world()
        self.assertEqual(manage.add_beds(ws, "farm_b", 5), 25)
        self.assertEqual(kinds(ws, "beds_added")[0]["beds"], 25)
        manage.add_beds(ws, "farm_b", manage.BEDS_MAX - 25)
        self.assertEqual(ws.settlements["farm_b"].beds, manage.BEDS_MAX)
        with self.assertRaises(ValueError):
            manage.add_beds(ws, "farm_b", 1)
        for bad in (0, -1, 2.5):
            with self.assertRaises(ValueError):
                manage.add_beds(ws, "farm_a", bad)
        with self.assertRaises(ValueError):
            manage.add_beds(ws, "raider_camp", 1)

    def test_more_beds_let_a_settlement_grow_past_the_old_cap(self):
        ws = quiet(world())
        s = ws.settlements["farm_a"]
        s.beds = s.population            # full
        s.morale, s.stock["food"], s.stock["water"] = 100, 500, 500
        before = s.population
        sim.run(ws, 10 * 24)
        self.assertEqual(s.population, before)
        manage.add_beds(ws, "farm_a", 3)
        sim.run(ws, 10 * 24)
        self.assertGreater(s.population, before)
        self.assertLessEqual(s.population, s.beds)


class PriorityTests(unittest.TestCase):
    def test_set_and_clear(self):
        ws = world()
        self.assertEqual(manage.set_priority(ws, "farm_a", "scrap"), "scrap")
        self.assertEqual(ws.settlements["farm_a"].priority, "scrap")
        self.assertIsNone(manage.set_priority(ws, "farm_a", None))
        self.assertEqual([(e["old"], e["new"]) for e in kinds(ws, "priority_set")],
                         [(None, "scrap"), ("scrap", None)])
        with self.assertRaises(ValueError):
            manage.set_priority(ws, "farm_a", "caps")
        with self.assertRaises(ValueError):
            manage.set_priority(ws, "ruins", "food")

    def test_sim_honours_the_priority(self):
        for good in GOODS:
            plain, focused = quiet(world()), quiet(world())
            manage.set_priority(focused, "market", good)
            for ws in (plain, focused):
                s = ws.settlements["market"]
                s.roles = {r: 0 for r in ROLES}
                s.roles.update({"farmer": 2, "scavenger": 1, "crafter": 1, "doctor": 1, "guard": 1})
                s.population = 6
                s.stock["scrap"] = 100
                s.stock["food"] = s.stock["water"] = 100
            sim.tick(plain)
            sim.tick(focused)
            role = sim.PRIORITY_ROLE[good]
            workers = plain.settlements["market"].roles[role]
            gain = focused.settlements["market"].stock[good] - plain.settlements["market"].stock[good]
            self.assertEqual(gain, sim.PRIORITY_BONUS_PER_WORKER * workers, good)
            for other in GOODS:
                if other != good:
                    self.assertEqual(focused.settlements["market"].stock[other],
                                     plain.settlements["market"].stock[other], (good, other))

    def test_ammo_priority_still_needs_scrap(self):
        ws = quiet(world())
        s = ws.settlements["market"]
        s.stock["scrap"], s.stock["ammo"] = 0, 0
        manage.set_priority(ws, "market", "ammo")
        sim.tick(ws)
        self.assertEqual(s.stock["ammo"], 0)

    def test_no_priority_replays_the_old_world(self):
        a, b = world(3), world(3)
        sim.run(a, DAYS * 24)
        sim.run(b, DAYS * 24)
        self.assertEqual(a.to_json(), b.to_json())
        self.assertTrue(all(s.priority is None for s in a.settlements.values()))


class SendSuppliesTests(unittest.TestCase):
    def test_caravan_leaves_now_and_arrives_later(self):
        ws = quiet(world())
        src, dst = ws.settlements["farm_a"], ws.settlements["farm_b"]
        food_before, dst_food = src.stock["food"], dst.stock["food"]
        qid = manage.send_supplies(ws, "farm_a", "farm_b", {"food": 10, "ammo": 4})
        q = ws.squads[qid]
        self.assertEqual((q.kind, q.faction, q.at, q.goal, q.cargo), ("caravan", "settlers", "farm_a", "farm_b",
                                                                      {"ammo": 4, "food": 10}))
        self.assertEqual(q.eta, 12)                       # farm_a -> market -> farm_b, two hops of 6
        self.assertEqual(src.stock["food"], food_before - 10)
        e = kinds(ws, "supplies_sent")[0]
        self.assertEqual((e["target"], e["cargo"], e["squad"]), ("farm_b", {"ammo": 4, "food": 10}, qid))
        sim.run(ws, 12)
        self.assertNotIn(qid, ws.squads)
        self.assertTrue(kinds(ws, "caravan_arrived") or kinds(ws, "caravan_raided"))
        if kinds(ws, "caravan_arrived"):
            # two ticks of farm_b's own production and eating sit on top of the 10 delivered
            self.assertGreaterEqual(dst.stock["ammo"], 4)

    def test_player_caravans_can_be_raided_like_any_other(self):
        from unittest import mock
        ws = quiet(world())
        qid = manage.send_supplies(ws, "farm_a", "market", {"food": 5})
        with mock.patch.object(sim, "RAID_CHANCE_CAP", 1.0), mock.patch.object(sim, "RAID_CHANCE_PER_STRENGTH", 1.0):
            sim.run(ws, 6)
        self.assertNotIn(qid, ws.squads)
        self.assertEqual(kinds(ws, "caravan_raided")[0]["raider"], "raiders")

    def test_validation(self):
        ws = world()
        cases = [
            ("ruins", "farm_a", {"food": 1}),                 # not a settlement
            ("farm_a", "farm_a", {"food": 1}),                # itself
            ("farm_a", "river_town", {"food": 1}),            # other holder
            ("farm_a", "farm_b", {}),                         # nothing to send
            ("farm_a", "farm_b", {"caps": 1}),                # unknown good
            ("farm_a", "farm_b", {"food": 0}),                # non-positive
            ("farm_a", "farm_b", {"food": 10_000}),           # more than stocked
            ("farm_a", "farm_b", [("food", 1)]),              # not a dict
        ]
        for args in cases:
            with self.assertRaises(ValueError, msg=args):
                manage.send_supplies(ws, *args)
        ws.places["farm_a"].holder = None
        with self.assertRaises(ValueError):
            manage.send_supplies(ws, "farm_a", "farm_b", {"food": 1})
        ws.places["farm_a"].holder = ws.places["river_town"].holder = "settlers"
        ws.routes = [r for r in ws.routes if {r.a, r.b} != {"gate_1", "gate_2"}]   # cut the only link
        with self.assertRaises(ValueError):
            manage.send_supplies(ws, "farm_a", "river_town", {"food": 1})
        self.assertEqual(ws.squads, {})
        self.assertEqual(ws.settlements["farm_a"].stock["food"], 20)   # a failed send moves nothing


class StatusTests(unittest.TestCase):
    def test_summary_fields(self):
        ws = world()
        st = manage.status(ws, "farm_a")
        self.assertEqual(st["holder"], "settlers")
        self.assertEqual(st["population"], 5)
        self.assertEqual(st["roles"], ws.settlements["farm_a"].roles)
        self.assertEqual(st["stock"], ws.settlements["farm_a"].stock)
        self.assertEqual(st["food_days"], 20 // (5 * manage.TICKS_PER_DAY))
        self.assertEqual(st["water_days"], 1)
        self.assertEqual((st["morale"], st["stage"], st["beds"], st["priority"]), (50, 0, 20, None))
        self.assertEqual(st["defence"], sim._defence(ws, "farm_a"))
        self.assertEqual(st["incoming_attacks"], [])
        self.assertEqual(st["threats"], [{"place": "raider_camp", "holder": "raiders", "hours": 12, "kind": "base"}])
        st["roles"]["farmer"] = 99                                   # copies, not the live dicts
        self.assertEqual(ws.settlements["farm_a"].roles["farmer"], 3)
        json.dumps(st)

    def test_threats_follow_hostility_and_distance(self):
        ws = world()
        self.assertEqual(manage.threats(ws, "farm_b", hours=6), [])   # ruins (6 hours) is empty
        self.assertEqual([t["place"] for t in manage.threats(ws, "farm_b")], ["raider_camp"])   # 12 via ruins
        ws.places["ruins"].holder = "raiders"
        self.assertEqual([t["place"] for t in manage.threats(ws, "farm_b")], ["ruins", "raider_camp"])
        ws.places["ruins"].holder = "order"                          # friendly to settlers
        self.assertEqual([t["place"] for t in manage.threats(ws, "farm_b")], ["raider_camp"])
        ws.places["farm_b"].holder = None
        self.assertEqual(manage.threats(ws, "farm_b"), [])
        ws.settlements["farm_b"].population = 0
        self.assertIsNone(manage.status(ws, "farm_b")["food_days"])

    def test_incoming_attacks_listed(self):
        ws = quiet(world())
        ws.squads["s9"] = Squad(id="s9", faction="raiders", size=4, at="raider_camp", goal="farm_a",
                                kind="attack", eta=12)
        self.assertEqual(manage.status(ws, "farm_a")["incoming_attacks"], ["s9"])
        with self.assertRaises(ValueError):
            manage.status(ws, "raider_camp")


def play(ws):
    """A fixed script of actions applied mid-run."""
    sim.run(ws, 10 * 24)
    manage.assign_role(ws, "market", "guard", "farmer", 1)
    manage.add_beds(ws, "farm_a", 4)
    manage.set_priority(ws, "farm_a", "food")
    manage.set_priority(ws, "river_town", "medicine")
    sim.player_traded(ws, "farm_a", {"food": 10})                   # ten days in, the larder may be bare
    if ws.places["farm_a"].holder == ws.places["market"].holder:    # or farm_a may have changed hands
        manage.send_supplies(ws, "farm_a", "market", {"food": 5})
    sim.run(ws, 20 * 24)


class DeterminismAndSaveTests(unittest.TestCase):
    def test_actions_keep_determinism(self):
        for seed in SEEDS:
            a, b = world(seed), world(seed)
            play(a)
            play(b)
            self.assertEqual(a.to_json(), b.to_json())

    def test_save_replay_with_actions_applied_mid_run(self):
        for seed in SEEDS:
            a = world(seed)
            play(a)
            saved = a.to_json()
            manage.set_priority(a, "market", "ammo")
            manage.add_beds(a, "market", 2)
            sim.run(a, 30 * 24)
            b = WorldState.from_json(saved)
            self.assertEqual(b.settlements["farm_a"].priority, "food")
            manage.set_priority(b, "market", "ammo")
            manage.add_beds(b, "market", 2)
            sim.run(b, 30 * 24)
            self.assertEqual(a.to_json(), b.to_json())

    def test_schema_2_save_without_priority_loads_with_default(self):
        d = json.loads(world().to_json())
        self.assertEqual(d["schema"], SCHEMA_VERSION)
        for s in d["settlements"].values():
            del s["priority"]
        ws = WorldState.from_json(json.dumps(d))
        self.assertTrue(all(s.priority is None for s in ws.settlements.values()))
        d["schema"] = 1
        del d["settings"], d["regional_reputation"]
        self.assertTrue(all(s.priority is None for s in WorldState.from_json(json.dumps(d)).settlements.values()))

    def test_invariants_hold_with_actions(self):
        for seed in SEEDS:
            ws = world(seed)
            play(ws)
            for sid, s in ws.settlements.items():
                self.assertTrue(0 <= s.population <= s.beds, (sid, s.population))
                self.assertEqual(sum(s.roles.values()), s.population, sid)
                self.assertTrue(all(v >= 0 for v in s.stock.values()), sid)
                self.assertTrue(s.priority is None or s.priority in GOODS, sid)


if __name__ == "__main__":
    unittest.main()
