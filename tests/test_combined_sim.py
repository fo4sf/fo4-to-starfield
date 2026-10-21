"""Combined-core L2 simulation: synthetic REGION_1/REGION_2 packs only, no game data (placeholder names, not facts)."""
import copy
import json
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


def settle(ws, sid, roles, stock=0, morale=50, holder="settlers"):
    """Shape settlement `sid`: roles {role: n}, every stock at `stock`, the place held by `holder`."""
    s = ws.settlements[sid]
    s.roles = {r: roles.get(r, 0) for r in ROLES}
    s.population = sum(s.roles.values())
    s.stock = {g: stock for g in s.stock}
    s.morale = morale
    ws.places[sid].holder = holder
    return s


class ShortageTests(unittest.TestCase):
    """REROLE_ON_SHORTAGE: a settlement short of food or water puts a settler to farming instead of starving."""

    def test_short_tick_turns_the_biggest_other_role_into_a_farmer(self):
        ws = quiet(world(1))
        s = settle(ws, "farm_a", {"guard": 2, "trader": 1})
        sim.tick(ws)
        self.assertEqual((s.roles["farmer"], s.roles["guard"], s.roles["trader"]), (1, 1, 1))   # one per tick
        self.assertEqual(s.population, 3)
        ev = kinds(ws, "roles_changed")
        self.assertEqual([(e["place"], e["from_role"], e["to_role"], e["n"]) for e in ev],
                         [("farm_a", "guard", "farmer", 1)])
        self.assertEqual(s.morale, 45)                       # the shortage still hurts
        sim.tick(ws)                                         # 3 food and water for 3 mouths: fed, no second move
        self.assertEqual(s.roles["farmer"], 1)
        self.assertEqual(len(kinds(ws, "roles_changed")), 1)

    def test_no_move_when_farmers_already_meet_the_food_rule_or_nobody_else_is_left(self):
        ws = quiet(world(1))
        s = settle(ws, "farm_a", {"farmer": 2, "guard": 1})  # 3 * 2 >= 3 + 2
        sim.tick(ws)
        self.assertEqual(s.roles["farmer"], 2)
        s = settle(ws, "farm_b", {"farmer": 1}, stock=0)
        s.population = 1
        sim.tick(ws)
        self.assertEqual(s.roles, {**{r: 0 for r in ROLES}, "farmer": 1})
        self.assertEqual(kinds(ws, "roles_changed"), [])

    def test_zero_disables_the_rule(self):
        ws = quiet(world(1))
        s = settle(ws, "farm_a", {"guard": 2, "trader": 1})
        with mock.patch.object(sim, "REROLE_ON_SHORTAGE", 0):
            sim.run(ws, 48)
        self.assertEqual(s.roles["farmer"], 0)
        self.assertEqual(kinds(ws, "roles_changed"), [])
        self.assertLess(s.population, 3)                     # the old death spiral

    def test_captured_farm_feeds_itself_again_instead_of_emptying(self):
        """The baseline's commonest story (seed 9, farm_a): capture takes the three farmers, the guard and trader
        starve and leave, the place is dead by day 6. Now a survivor farms and the place keeps people."""
        ws = quiet(world(1))
        s = settle(ws, "farm_a", {"farmer": 3, "guard": 1, "trader": 1}, stock=20, morale=56)
        ws.places["farm_a"].defence = 0
        ws.factions["settlers"].strength = 0
        ws.squads["s1"] = Squad(id="s1", faction="raiders", size=500, at="raider_camp", goal="farm_a",
                                kind="attack", eta=sim.TICK_HOURS)
        sim.run(ws, 20 * 24)
        self.assertEqual(ws.places["farm_a"].holder, "raiders")
        self.assertGreaterEqual(s.population, 2)
        self.assertGreaterEqual(s.roles["farmer"], 1)
        self.assertEqual(kinds(ws, "settlement_emptied"), [])


class ResettlementTests(unittest.TestCase):
    """An empty settlement a faction holds draws a wanderer once a day when it is safe and fed (RESETTLE_*)."""

    def empty(self, ws, sid="farm_a", holder="raiders"):
        return settle(ws, sid, {}, stock=0, morale=0, holder=holder)

    def test_wanderer_arrives_as_a_farmer_with_a_kit_on_the_day_tick(self):
        ws = quiet(world(1))
        s = self.empty(ws)
        sim.run(ws, 18)                                      # hours 6, 12, 18: not a day boundary
        self.assertEqual(s.population, 0)
        sim.tick(ws)                                         # hour 24
        self.assertEqual((s.population, s.roles["farmer"]), (1, 1))
        self.assertEqual((s.stock["food"], s.stock["water"]), (sim.RESETTLE_KIT, sim.RESETTLE_KIT))
        self.assertEqual(s.morale, sim.RESETTLE_MORALE)
        ev = kinds(ws, "settlement_resettled")
        self.assertEqual([(e["hour"], e["place"], e["faction"]) for e in ev], [(24, "farm_a", "raiders")])
        sim.run(ws, 20 * 24)                                 # and then it grows like any fed settlement
        self.assertGreater(s.population, 1)
        self.assertTrue(kinds(ws, "settler_arrived"))

    def test_no_wanderer_without_a_holder_or_beds(self):
        ws = quiet(world(1))
        s = self.empty(ws, holder=None)
        sim.run(ws, 10 * 24)
        self.assertEqual(s.population, 0)
        s = self.empty(ws, holder="raiders")
        s.beds = 0
        sim.run(ws, 10 * 24)
        self.assertEqual(s.population, 0)
        self.assertEqual(kinds(ws, "settlement_resettled"), [])

    def test_an_unheld_empty_settlement_never_gains_a_normal_arrival(self):
        # Codex P1 on #431: morale drift lifted an empty place to 70 and the normal arrival branch skipped every
        # resettlement guard.
        ws = quiet(world(1))
        s = self.empty(ws, holder=None)
        s.stock["food"] = s.stock["water"] = 50
        s.morale = 90
        sim.run(ws, 20 * 24)
        self.assertEqual(s.population, 0)
        self.assertEqual([e for e in kinds(ws, "settler_arrived") if e["place"] == "farm_a"], [])

    def test_recent_fighting_or_an_attack_on_the_way_blocks_it(self):
        ws = quiet(world(1))
        s = self.empty(ws)
        ws.events.append({"hour": 0, "kind": "place_taken", "place": "farm_a", "region": "R1",
                          "faction": "raiders", "previous": "settlers", "retaken": False})
        sim.run(ws, sim.RESETTLE_SAFE_HOURS)                 # the fight is still within the window at its end
        self.assertEqual(s.population, 0)
        sim.run(ws, 24)                                      # hour 72: 72 - 48 = 24 > 0, safe
        self.assertEqual(s.population, 1)
        s = self.empty(ws, "farm_b")
        ws.squads["s9"] = Squad(id="s9", faction="order", size=3, at="ruins", goal="farm_b", kind="attack",
                                eta=ws.hour + 500)
        sim.run(ws, 5 * 24)
        self.assertEqual(s.population, 0)
        del ws.squads["s9"]
        sim.run(ws, 24)
        self.assertEqual(s.population, 1)

    def test_safe_check_reads_squads_and_the_log(self):
        ws = quiet(world(1))
        self.assertTrue(sim._resettle_safe(ws, "farm_a"))
        ws.events.append({"hour": 0, "kind": "attack_failed", "place": "farm_a", "region": "R1",
                          "faction": "raiders", "defender": "settlers"})
        self.assertFalse(sim._resettle_safe(ws, "farm_a"))
        ws.hour = sim.RESETTLE_SAFE_HOURS + 1
        self.assertTrue(sim._resettle_safe(ws, "farm_a"))
        self.assertTrue(sim._resettle_safe(ws, "farm_b"))
        ws.squads["s9"] = Squad(id="s9", faction="order", size=3, at="ruins", goal="farm_b", kind="attack", eta=999)
        self.assertFalse(sim._resettle_safe(ws, "farm_b"))

    def test_emptied_event_on_the_last_leaver_and_on_a_capture(self):
        ws = quiet(world(1))
        s = settle(ws, "farm_a", {"guard": 1}, stock=0, morale=12)
        with mock.patch.object(sim, "REROLE_ON_SHORTAGE", 0):
            sim.tick(ws)                                     # short: morale 7, the guard leaves
        self.assertEqual(s.population, 0)
        self.assertEqual([(e["place"], e["holder"]) for e in kinds(ws, "settlement_emptied")],
                         [("farm_a", "settlers")])
        s = settle(ws, "farm_b", {"guard": 1}, stock=0, morale=90)
        ws.places["farm_b"].defence = 0
        ws.factions["settlers"].strength = 0
        ws.squads["s1"] = Squad(id="s1", faction="raiders", size=500, at="ruins", goal="farm_b",
                                kind="attack", eta=ws.hour + sim.TICK_HOURS)
        sim.tick(ws)
        self.assertEqual(ws.places["farm_b"].holder, "raiders")
        self.assertEqual(s.population, 0)
        self.assertEqual([e["holder"] for e in kinds(ws, "settlement_emptied") if e["place"] == "farm_b"],
                         ["raiders"])

    def test_settlements_still_fall_and_come_back_across_seeds(self):
        emptied = resettled = ended_empty = 0
        for seed in SEEDS:
            ws = world(seed)
            sim.run(ws, DAYS * 24)
            emptied += len(kinds(ws, "settlement_emptied"))
            resettled += len(kinds(ws, "settlement_resettled"))
            ended_empty += sum(s.population == 0 for s in ws.settlements.values())
        self.assertGreater(emptied, 0)                       # a settlement can fall
        self.assertGreater(resettled, 0)                     # and be resettled
        self.assertLessEqual(ended_empty, len(SEEDS))        # rarely still empty at the end (baseline: 32 of 80)

    def test_save_made_under_the_old_rules_replays_under_the_new_ones(self):
        old = {"REROLE_ON_SHORTAGE": 0, "RESETTLE_SAFE_HOURS": 10 ** 9}
        for seed in (3, 9):
            ws = world(seed)
            with mock.patch.multiple(sim, **old):
                sim.run(ws, 45 * 24)
            d = json.loads(ws.to_json())                     # schema 2; strip the events a save from before
            d["events"] = [e for e in d["events"]            # the change never had
                           if e["kind"] not in ("settlement_emptied", "settlement_resettled")]
            self.assertTrue(len(d["events"]) < len(ws.events))
            ws = WorldState.from_json(json.dumps(d))
            sim.run(ws, 45 * 24)
            for sid, s in ws.settlements.items():
                self.assertEqual(sum(s.roles.values()), s.population, sid)
                self.assertTrue(0 <= s.population <= s.beds, sid)
            self.assertTrue(kinds(ws, "settlement_resettled") or kinds(ws, "settler_arrived"))


class GrowthBrakeTests(unittest.TestCase):
    """The Commonwealth-scale rules (sim.FARM_SLOTS_PER_BEDS, LEAVE_ONLY_WHEN_SHORT, MORALE_DRIFT, ARRIVAL_SLOWDOWN_POP,
    SETTLEMENT_TARGET_WEIGHT): a settlement alone no longer pins at its beds with morale 100."""

    def lone(self, beds=20):
        pack = {"places": [{"id": "lone", "region": "R", "kind": "settlement", "holder": "settlers", "defence": 2}],
                "settlements": [{"place": "lone", "population": 5, "beds": beds,
                                 "roles": {"farmer": 3, "guard": 1, "trader": 1, "crafter": 0, "scavenger": 0,
                                           "doctor": 0},
                                 "stock": {"food": 20, "water": 20, "scrap": 0, "ammo": 10, "medicine": 0}}],
                "factions": [{"id": "settlers", "strength": 8, "home": "lone", "aggression": 0}], "routes": []}
        ws = WorldState(seed=1)
        model.load_pack(ws, pack)
        return ws, ws.settlements["lone"]

    def test_farm_slots_cap_production_and_the_farmer_rule(self):
        ws, s = self.lone()
        self.assertEqual(sim._farm_slots(s), 5)                                 # 20 beds // 4
        s.roles["farmer"], s.population = 8, 8
        for r in ("guard", "trader"):
            s.roles[r] = 0
        sim.tick(ws)
        self.assertEqual(s.stock["food"], 20 + 3 * 5 - 8)                      # five farm, eight eat
        self.assertFalse(sim._wants_farmer(s))                                  # no land left
        sim._add_settler(s)
        self.assertEqual(s.roles["farmer"], 8)                                  # the newcomer took another role
        self.assertEqual(sim._reroles_to_farming(s, 3), {})
        with mock.patch.object(sim, "FARM_SLOTS_PER_BEDS", 0):
            self.assertIsNone(sim._farm_slots(s))
            ws2, s2 = self.lone()
            s2.roles["farmer"], s2.population = 8, 8
            s2.roles["guard"] = s2.roles["trader"] = 0
            sim.tick(ws2)
            self.assertEqual(s2.stock["food"], 20 + 24 - 8)                     # off: every farmer produces

    def test_lone_settlement_grows_but_stops_at_its_food_not_its_beds(self):
        ws, s = self.lone()
        sim.run(ws, 90 * 24)
        self.assertGreater(s.population, 5)                                     # still grows
        self.assertLess(s.population, s.beds)                                   # but not to the beds
        self.assertLessEqual(s.population, 3 * sim._farm_slots(s) + 1)         # the food edge (15 of 20 beds)
        self.assertLess(s.morale, 100)
        self.assertEqual(sum(1 for e in ws.events if e["kind"] == "settlement_emptied"), 0)   # no boom and bust
        old = {"FARM_SLOTS_PER_BEDS": 0, "LEAVE_ONLY_WHEN_SHORT": 0, "MORALE_DRIFT": 0, "ARRIVAL_SLOWDOWN_POP": 0}
        ws2, s2 = self.lone()
        with mock.patch.multiple(sim, **old):
            sim.run(ws2, 30 * 24)
        self.assertEqual((s2.population, s2.morale), (20, 100))                # the first prototype's saturation

    def test_leave_only_when_short(self):
        ws, s = self.lone()
        s.morale, s.stock["food"], s.stock["water"] = 8, 100, 100
        sim.tick(ws)                                                            # fed (morale 8 + 2 = 10): nobody leaves
        self.assertEqual((s.population, s.morale), (5, 10))
        s.stock["food"] = s.stock["water"] = 0
        s.roles["farmer"], s.roles["guard"] = 0, 4                              # short this tick
        s.morale = 10
        sim.tick(ws)
        self.assertEqual(s.population, 4)
        ws2, s2 = self.lone()
        s2.morale, s2.stock["food"], s2.stock["water"] = 8, 100, 100
        with mock.patch.object(sim, "LEAVE_ONLY_WHEN_SHORT", 0):
            sim.tick(ws2)
        self.assertEqual(s2.population, 4)                                      # off: the old every-tick rule

    def test_morale_drifts_up_when_fed_without_surplus(self):
        ws, s = self.lone()
        s.roles["farmer"], s.population = 5, 15                                # 15 made, 15 eaten: no surplus
        s.roles["guard"], s.roles["trader"] = 5, 5
        s.stock["food"] = s.stock["water"] = 15
        s.morale = 40
        sim.tick(ws)
        self.assertEqual(s.morale, 41)
        s.stock["food"] = s.stock["water"] = 200                                # surplus: the old +2
        sim.tick(ws)
        self.assertEqual(s.morale, 43)
        with mock.patch.object(sim, "MORALE_DRIFT", 0):
            s.stock["food"] = s.stock["water"] = 15
            sim.tick(ws)
            self.assertEqual(s.morale, 43)

    def test_arrival_slowdown_schedule(self):
        ws, s = self.lone()
        for pop, days in ((2, 1), (3, 2), (5, 2), (6, 3), (9, 4), (14, 5)):
            s.population = pop
            due = [day for day in range(60) if (setattr(ws, "hour", day * 24) or sim._arrival_due(ws, s))]
            self.assertEqual(due[:3], [0, days, 2 * days], pop)
        with mock.patch.object(sim, "ARRIVAL_SLOWDOWN_POP", 0):
            ws.hour = 24 * 7
            self.assertTrue(sim._arrival_due(ws, s))

    def test_settlement_target_weight_is_a_knob_on_target_choice(self):
        counts = {}
        for weight in (1, 5):
            n = 0
            for seed in range(12):
                ws = world(seed)
                with mock.patch.object(sim, "SETTLEMENT_TARGET_WEIGHT", weight):
                    sim.run(ws, 30 * 24)
                n += sum(1 for e in ws.events if e["kind"] == "attack_launched" and e["target"] in ws.settlements)
            counts[weight] = n
        self.assertGreater(counts[5], counts[1])

    def test_new_rules_keep_the_fixture_tests_alive_and_resumable(self):
        a = world(5)
        sim.run(a, 60 * 24)
        b = world(5)
        sim.run(b, 31 * 24)
        b = WorldState.from_json(b.to_json())
        sim.run(b, 29 * 24)
        self.assertEqual(a.to_json(), b.to_json())
        for kind in ("settler_arrived", "caravan_arrived", "place_taken"):
            self.assertTrue(kinds(a, kind), kind)


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
