"""Combined-core L3 radiant work (jobs.py) on the synthetic REGION_1/REGION_2 packs: placeholder names, not game facts."""
import copy
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.combined import fixtures, jobs, model, news, reputation, sim  # noqa: E402
from fo4sf.combined.model import Squad, WorldState  # noqa: E402

SEEDS = range(8)
DAYS = 30


def world(seed=1):
    ws = WorldState(seed=seed)
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_1))
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_2))
    return ws


def quiet(ws):
    for f in ws.factions.values():
        f.aggression = 0
    return ws


def without_events(ws):
    """The state minus its log, so "the world changed" means more than one event appended."""
    d = json.loads(ws.to_json())
    del d["events"]
    return json.dumps(d, sort_keys=True)


def by_kind(found, kind):
    return [o for o in found if o.kind == kind]


def attack(ws, qid="s_t", faction="raiders", target="farm_a", size=5, hours=sim.TICK_HOURS * 2):
    ws.squads[qid] = Squad(id=qid, faction=faction, size=size, at="raider_camp", goal=target, kind="attack",
                           eta=ws.hour + hours)
    return qid


def caravan(ws, qid="c_t", at="farm_a", goal="market", cargo=None, hours=sim.TICK_HOURS):
    ws.squads[qid] = Squad(id=qid, faction="settlers", size=2, at=at, goal=goal, kind="caravan",
                           cargo=cargo or {"food": 12}, eta=ws.hour + hours)
    return qid


def lose(ws, place="farm_a", to="raiders", hour=0):
    ws.places[place].holder = to
    ws.events.append({"hour": hour, "kind": "place_taken", "place": place, "region": "R1", "faction": to,
                      "previous": "settlers", "retaken": False})


class OfferTests(unittest.TestCase):
    def test_no_holder_no_offers_and_unknown_place_raises(self):
        ws = world()
        self.assertEqual(jobs.offers(ws, "ruins"), [])
        with self.assertRaises(KeyError):
            jobs.offers(ws, "nowhere")

    def test_every_kind_appears_in_plain_runs(self):
        seen = set()
        for seed in SEEDS:
            ws = world(seed)
            for _ in range(DAYS * 24 // sim.TICK_HOURS):
                sim.tick(ws)
                for place in sorted(ws.places):
                    seen.update(o.kind for o in jobs.offers(ws, place, limit=50))
        self.assertEqual(seen, set(jobs.KINDS))

    def test_offer_shape_and_text(self):
        for seed in SEEDS:
            ws = world(seed)
            sim.run(ws, DAYS * 24)
            for place in sorted(ws.places):
                for o in jobs.offers(ws, place, limit=50):
                    self.assertIn(o.kind, jobs.KINDS)
                    self.assertEqual(o.giver, ws.places[place].holder)
                    self.assertEqual(o.place, place)
                    self.assertIn(o.target, ws.places)
                    self.assertTrue(1 <= o.reward_tier <= len(reputation.GAIN_TIERS), o)
                    self.assertEqual(o.offered_hour, ws.hour)
                    self.assertGreater(o.expires_hour, ws.hour)
                    self.assertTrue(o.id.startswith(o.kind + ":"), o.id)
                    self.assertTrue(o.text.endswith("."), o.text)
                    self.assertEqual(o.text[0], o.text[0].upper())
                    self.assertNotIn("{", o.text)
                    self.assertNotIn("_", o.text)                 # ids shown as names
                    self.assertIsNone(jobs.valid(ws, o), o)
                    self.assertEqual(jobs.Offer(**o.to_dict()), o)  # round-trips as plain data

    def test_limit_and_order(self):
        ws = quiet(world())
        attack(ws, "s_a", target="farm_a", hours=12)
        attack(ws, "s_b", target="farm_b", hours=24)
        caravan(ws, "c_a", at="market", goal="farm_a", hours=18)
        lose(ws, "story_vault", "raiders")      # story-locked: never offered
        found = jobs.offers(ws, "market", limit=50)
        self.assertEqual([o.expires_hour for o in found], sorted(o.expires_hour for o in found))
        self.assertEqual([o.id for o in found][:3], ["defend:s_a", "escort:c_a", "defend:s_b"])
        self.assertNotIn("retake:settlers:story_vault:0", [o.id for o in found])
        self.assertEqual(len(jobs.offers(ws, "market", limit=2)), 2)

    def test_display_names_reach_the_text(self):
        ws = quiet(world())
        attack(ws)
        o = by_kind(jobs.offers(ws, "farm_a", names={"settlers": "The Settlers", "farm_a": "Farm A"}), "defend")[0]
        self.assertIn("The Settlers", o.text)
        self.assertIn("Farm A", o.text)

    def test_same_state_same_offers(self):
        for seed in (2, 5):
            a, b = world(seed), world(seed)
            sim.run(a, 20 * 24)
            sim.run(b, 20 * 24)
            for place in sorted(a.places):
                self.assertEqual(jobs.offers(a, place, limit=50), jobs.offers(b, place, limit=50))
            c = WorldState.from_json(a.to_json())
            self.assertEqual(jobs.offers(a, "market", limit=50), jobs.offers(c, "market", limit=50))


class TierTests(unittest.TestCase):
    def test_reward_tier_is_a_tier_number_not_points(self):
        # Codex P2 on #431: a size-9 defend once stored the points (7) as the tier and paid 12 fame.
        unit = jobs.DEFEND_SIZE_PER_TIER
        self.assertEqual([reputation.tier_number(n * unit, unit) for n in range(7)], [1, 2, 3, 4, 5, 5, 5])
        self.assertEqual([reputation.tier_points(reputation.tier_number(n * unit, unit)) for n in range(5)],
                         [reputation.tier_for(n * unit, unit) for n in range(5)])


class DefendTests(unittest.TestCase):
    def test_offer_from_incoming_attack_and_garrison_on_complete(self):
        ws = quiet(world())
        qid = attack(ws, size=6)
        found = by_kind(jobs.offers(ws, "market"), "defend")       # market is settlers' too
        self.assertEqual([o.id for o in found], [f"defend:{qid}"])
        o = found[0]
        self.assertEqual((o.target, o.expires_hour, o.detail["attacker"]), ("farm_a", ws.squads[qid].eta, "raiders"))
        self.assertEqual(o.reward_tier, reputation.tier_number(6, jobs.DEFEND_SIZE_PER_TIER))
        base = sim._defence(ws, "farm_a")
        fame0 = ws.reputation["settlers"].fame
        changed = jobs.complete(ws, o)
        self.assertEqual(ws.squads[changed["garrison"]].kind, "garrison")
        self.assertEqual(sim._defence(ws, "farm_a"), base + sim.PLAYER_DEFENCE_BONUS)
        self.assertEqual(ws.reputation["settlers"].fame,
                         fame0 + sim.PLAYER_DEFENCE_FAME + reputation.tier_points(o.reward_tier))
        self.assertGreater(ws.reputation["raiders"].infamy, 0)
        self.assertEqual([e["job"] for e in ws.events if e["kind"] == "job_done"], ["defend"])
        self.assertEqual(by_kind(jobs.offers(ws, "market"), "defend"), [])   # a garrison stands: not offered twice
        with self.assertRaises(ValueError):
            jobs.complete(ws, o)

    def test_expires_when_the_attack_arrives(self):
        ws = quiet(world())
        attack(ws, hours=sim.TICK_HOURS)
        o = by_kind(jobs.offers(ws, "farm_a"), "defend")[0]
        sim.tick(ws)
        self.assertIsNotNone(jobs.valid(ws, o))
        with self.assertRaises(ValueError):
            jobs.complete(ws, o)

    def test_moot_when_the_giver_loses_the_place_first(self):
        ws = quiet(world())
        attack(ws)
        o = by_kind(jobs.offers(ws, "farm_a"), "defend")[0]
        ws.places["farm_a"].holder = "order"
        self.assertIn("no longer holds", jobs.valid(ws, o))


class EscortTests(unittest.TestCase):
    def test_offer_only_where_the_caravan_leaves_and_delivery_on_complete(self):
        ws = quiet(world())
        qid = caravan(ws, cargo={"food": 12, "water": 3})
        self.assertEqual(by_kind(jobs.offers(ws, "market"), "escort"), [])
        o = by_kind(jobs.offers(ws, "farm_a"), "escort")[0]
        self.assertEqual((o.id, o.target, o.detail["cargo"]), (f"escort:{qid}", "market", {"food": 12, "water": 3}))
        self.assertEqual(o.reward_tier, reputation.tier_number(15, jobs.ESCORT_GOODS_PER_TIER))
        food, water = ws.settlements["market"].stock["food"], ws.settlements["market"].stock["water"]
        changed = jobs.complete(ws, o)
        self.assertNotIn(qid, ws.squads)
        self.assertEqual(ws.settlements["market"].stock["food"], food + 12)
        self.assertEqual(ws.settlements["market"].stock["water"], water + 3)
        self.assertEqual(changed["cargo"], {"food": 12, "water": 3})
        arrived = [e for e in ws.events if e["kind"] == "caravan_arrived"]
        self.assertEqual(len(arrived), 1)
        self.assertTrue(arrived[0]["escorted"])
        self.assertIsNotNone(news.headline(arrived[0]))             # the news already writes about it
        with self.assertRaises(ValueError):
            jobs.complete(ws, o)

    def test_escorted_caravan_cannot_be_raided_later(self):
        ws = quiet(world())
        caravan(ws, hours=sim.TICK_HOURS)
        o = by_kind(jobs.offers(ws, "farm_a"), "escort")[0]
        jobs.complete(ws, o)
        sim.run(ws, 2 * 24)
        self.assertEqual([e for e in ws.events if e["kind"] == "caravan_raided"], [])

    def test_lapses_once_the_caravan_resolves(self):
        ws = quiet(world())
        caravan(ws, hours=sim.TICK_HOURS)
        o = by_kind(jobs.offers(ws, "farm_a"), "escort")[0]
        sim.tick(ws)
        with self.assertRaises(ValueError):
            jobs.complete(ws, o)


class RetakeTests(unittest.TestCase):
    def test_offer_from_place_taken_and_holder_restored_on_complete(self):
        ws = quiet(world())
        lose(ws, "farm_a", "raiders", hour=0)
        o = by_kind(jobs.offers(ws, "market"), "retake")[0]
        self.assertEqual((o.id, o.target, o.detail["holder"]), ("retake:settlers:farm_a:0", "farm_a", "raiders"))
        self.assertEqual(o.expires_hour, jobs.RETAKE_OFFER_HOURS)
        pop = ws.settlements["farm_a"].population
        fame0 = ws.reputation["settlers"].fame
        changed = jobs.complete(ws, o)
        self.assertEqual(ws.places["farm_a"].holder, "settlers")
        self.assertEqual(changed["previous"], "raiders")
        self.assertEqual(ws.settlements["farm_a"].population, pop)    # a clean retake, unlike a capture
        self.assertEqual(ws.reputation["settlers"].fame, fame0 + reputation.tier_points(jobs.RETAKE_TIER))
        taken = [e for e in ws.events if e["kind"] == "place_taken" and e.get("player")]
        self.assertEqual(len(taken), 1)
        self.assertEqual((taken[0]["hour"], taken[0]["retaken"], taken[0]["region"]), (ws.hour, True, "R1"))
        self.assertEqual(news.headline(taken[0]), "Settlers took back farm a from raiders.")
        self.assertIn("farm_a", sim._lost_places(ws, "raiders"))       # the raiders now want it back
        self.assertNotIn("farm_a", sim._lost_places(ws, "settlers"))
        with self.assertRaises(ValueError):
            jobs.complete(ws, o)

    def test_old_losses_homes_story_places_and_friends_are_not_offered(self):
        ws = quiet(world())
        lose(ws, "farm_a", "raiders", hour=0)
        ws.hour = jobs.RETAKE_OFFER_HOURS                             # the loss is a week old
        self.assertEqual(by_kind(jobs.offers(ws, "market"), "retake"), [])
        ws.hour = 0
        ws.places["farm_a"].holder = "order"                          # a friend holds it now
        self.assertEqual(by_kind(jobs.offers(ws, "market"), "retake"), [])
        ws.places["farm_a"].holder = "raiders"
        o = by_kind(jobs.offers(ws, "market"), "retake")[0]
        ws.places["farm_a"].story_lock = "s"
        self.assertIn("cannot change hands", jobs.valid(ws, o))

    def test_simulation_may_take_it_back_first(self):
        ws = quiet(world())
        lose(ws, "farm_a", "raiders", hour=0)
        o = by_kind(jobs.offers(ws, "market"), "retake")[0]
        ws.places["farm_a"].holder = "settlers"
        with self.assertRaises(ValueError):
            jobs.complete(ws, o)


class ResupplyTests(unittest.TestCase):
    def test_shortage_offer_and_trade_on_complete(self):
        ws = quiet(world())
        s = ws.settlements["farm_b"]
        s.stock["food"] = 1                                           # population 3: short below 6
        o = by_kind(jobs.offers(ws, "market"), "resupply")
        self.assertEqual([x.id for x in o], ["resupply:settlers:farm_b:food"])
        o = o[0]
        want = 3 * jobs.RESUPPLY_FILL_TICKS - 1
        self.assertEqual(o.detail, {"good": "food", "amount": want})
        self.assertEqual(o.expires_hour, ws.hour + jobs.RESUPPLY_OFFER_HOURS)
        fame0 = ws.reputation["settlers"].fame
        changed = jobs.complete(ws, o)
        self.assertEqual(changed["moved"], {"food": want})
        self.assertEqual(s.stock["food"], want + 1)
        self.assertEqual(ws.reputation["settlers"].fame,
                         fame0 + sim._rep_tier(want) + reputation.tier_points(o.reward_tier))
        self.assertEqual(by_kind(jobs.offers(ws, "market"), "resupply"), [])
        with self.assertRaises(ValueError):
            jobs.complete(ws, o)

    def test_a_completed_offer_cannot_be_handed_in_again(self):
        # Codex review of #431: the settlement short again before expiry must not let the same offer pay twice
        ws = quiet(world())
        s = ws.settlements["farm_b"]
        s.stock["food"] = 1
        o = by_kind(jobs.offers(ws, "market"), "resupply")[0]
        jobs.complete(ws, o)
        s.stock["food"] = 1                                           # the player took the goods straight back
        self.assertIn("already handed in", jobs.valid(ws, o))
        with self.assertRaises(ValueError):
            jobs.complete(ws, o)
        ws.hour += 1                                                  # a new shortage later is a new offer
        self.assertIsNone(jobs.valid(ws, by_kind(jobs.offers(ws, "market"), "resupply")[0]))

    def test_no_offer_for_an_empty_or_stocked_settlement(self):
        ws = quiet(world())
        self.assertEqual(by_kind(jobs.offers(ws, "market"), "resupply"), [])
        s = ws.settlements["farm_b"]
        s.population = 0
        s.roles = {r: 0 for r in s.roles}
        s.stock["water"] = 0
        self.assertEqual(by_kind(jobs.offers(ws, "market"), "resupply"), [])

    def test_offer_lapses_when_the_farm_recovers(self):
        ws = quiet(world())
        s = ws.settlements["farm_b"]
        s.stock["water"] = 0
        o = by_kind(jobs.offers(ws, "farm_b"), "resupply")[0]
        s.stock["water"] = 100
        self.assertIn("no longer short", jobs.valid(ws, o))


class ClearTests(unittest.TestCase):
    def test_hostile_neighbour_offer_and_empty_holder_on_complete(self):
        ws = quiet(world())
        ws.places["ruins"].holder = "raiders"                         # next to farm_b (settlers)
        found = by_kind(jobs.offers(ws, "market"), "clear")
        self.assertEqual([o.id for o in found], ["clear:settlers:ruins"])   # raider_camp is a home: never
        o = found[0]
        self.assertEqual(o.detail, {"holder": "raiders", "near": "farm_b"})
        self.assertEqual(o.expires_hour, ws.hour + jobs.CLEAR_OFFER_HOURS)
        fame0 = ws.reputation["settlers"].fame
        changed = jobs.complete(ws, o)
        self.assertIsNone(ws.places["ruins"].holder)
        self.assertEqual(changed["previous"], "raiders")
        self.assertEqual(ws.reputation["settlers"].fame, fame0 + reputation.tier_points(jobs.CLEAR_TIER))
        cleared = [e for e in ws.events if e["kind"] == "place_cleared"]
        self.assertEqual((cleared[0]["place"], cleared[0]["faction"], cleared[0]["previous"], cleared[0]["region"]),
                         ("ruins", "settlers", "raiders", "R1"))
        self.assertEqual(set(cleared[0]) >= {"hour", "kind", "place", "region"}, True)   # sim's event shape
        with self.assertRaises(ValueError):
            jobs.complete(ws, o)

    def test_cleared_place_counts_as_lost_and_can_be_asked_back(self):
        ws = quiet(world())
        ws.places["ruins"].holder = "raiders"
        o = by_kind(jobs.offers(ws, "farm_b"), "clear")[0]
        jobs.complete(ws, o)
        self.assertEqual(sim._lost_places(ws, "raiders"), {"ruins"})
        self.assertEqual(jobs._lost_hour(ws, "raiders", "ruins"), ws.hour)
        retake = by_kind(jobs.offers(ws, "raider_camp"), "retake")
        self.assertEqual([o.id for o in retake], [f"retake:raiders:ruins:{ws.hour}"])
        self.assertEqual(retake[0].detail, {"holder": None, "taken_hour": ws.hour})
        self.assertEqual(retake[0].expires_hour, ws.hour + jobs.RETAKE_OFFER_HOURS)
        self.assertNotIn("ruins", [o.target for o in jobs.offers(ws, "raider_camp", limit=50) if o.kind == "clear"])
        jobs.complete(ws, retake[0])
        self.assertEqual(ws.places["ruins"].holder, "raiders")
        self.assertEqual(sim._lost_places(ws, "raiders"), set())

    def test_lost_places_are_retake_not_clear(self):
        ws = quiet(world())
        lose(ws, "farm_a", "raiders")
        found = jobs.offers(ws, "market", limit=50)
        self.assertEqual([o.kind for o in found if o.target == "farm_a"], ["retake"])

    def test_cleared_place_can_be_moved_into_by_the_simulation(self):
        ws = world(3)
        ws.places["ruins"].holder = "raiders"
        o = by_kind(jobs.offers(ws, "farm_b"), "clear")[0]
        jobs.complete(ws, o)
        sim.run(ws, DAYS * 24)
        self.assertTrue(any(e["kind"] == "place_taken" and e["place"] == "ruins" for e in ws.events))


class OutcomeTests(unittest.TestCase):
    def test_every_completed_offer_changes_the_world_beyond_the_log(self):
        done = set()
        for seed in SEEDS:
            ws = world(seed)
            for _ in range(DAYS * 24 // sim.TICK_HOURS):
                sim.tick(ws)
                for place in sorted(ws.places):
                    for o in jobs.offers(ws, place, limit=50):
                        trial = WorldState.from_json(ws.to_json())
                        before = without_events(trial)
                        changed = jobs.complete(trial, o)
                        self.assertNotEqual(without_events(trial), before, o)
                        self.assertEqual(changed["fame"], reputation.tier_points(o.reward_tier))
                        self.assertIsNotNone(jobs.valid(trial, o), o)        # never twice
                        done.add(o.kind)
        self.assertEqual(done, set(jobs.KINDS))

    def test_completed_world_keeps_simulation_invariants(self):
        for seed in SEEDS:
            ws = world(seed)
            sim.run(ws, 10 * 24)
            for place in sorted(ws.places):
                for o in jobs.offers(ws, place, limit=50):
                    if jobs.valid(ws, o) is None:
                        jobs.complete(ws, o)
            start = copy.deepcopy(ws)
            sim.run(ws, 20 * 24)
            for pid, pl in ws.places.items():
                if pl.story_lock:
                    self.assertEqual(pl.holder, start.places[pid].holder)
            for fid, f in ws.factions.items():
                self.assertEqual(ws.places[f.home].holder, fid)
                self.assertTrue(0 <= f.strength <= sim.STRENGTH_CAP)
            for s in ws.settlements.values():
                self.assertTrue(all(v >= 0 for v in s.stock.values()))
                self.assertEqual(sum(s.roles.values()), s.population)

    def test_complete_and_fail_keep_determinism(self):
        runs = []
        for _ in range(2):
            ws = world(4)
            sim.run(ws, 10 * 24)
            found = jobs.offers(ws, "market", limit=50)
            if found:
                jobs.complete(ws, found[0])
            for o in found[1:]:
                jobs.fail(ws, o)
            sim.run(ws, 20 * 24)
            runs.append(ws.to_json())
        self.assertEqual(runs[0], runs[1])

    def test_offers_survive_a_save_and_complete_on_the_resumed_world(self):
        ws = quiet(world())
        attack(ws)
        o = jobs.offers(ws, "farm_a")[0]
        ws = WorldState.from_json(ws.to_json())
        again = jobs.Offer(**json.loads(json.dumps(o.to_dict())))
        self.assertEqual(again, o)
        jobs.complete(ws, again)
        self.assertTrue(sim._garrisons(ws, "farm_a"))

    def test_fail_costs_small_infamy_or_nothing(self):
        ws = quiet(world())
        attack(ws)
        lose(ws, "farm_b", "raiders")
        found = jobs.offers(ws, "farm_a", limit=50)
        defend, retake = by_kind(found, "defend")[0], by_kind(found, "retake")[0]
        self.assertEqual(jobs.fail(ws, retake), 0)
        self.assertEqual(ws.reputation["settlers"].infamy, 0)
        sim.run(ws, 24)                                               # failing an expired offer is allowed
        self.assertIsNotNone(jobs.valid(ws, defend))
        self.assertEqual(jobs.fail(ws, defend), jobs.FAIL_INFAMY["defend"])
        self.assertEqual(ws.reputation["settlers"].infamy, jobs.FAIL_INFAMY["defend"])
        self.assertEqual([e["job"] for e in ws.events if e["kind"] == "job_failed"], ["retake", "defend"])
        with self.assertRaises(ValueError):                          # once per offer (Codex review of #431)
            jobs.fail(ws, defend)
        self.assertEqual(ws.reputation["settlers"].infamy, jobs.FAIL_INFAMY["defend"])

    def test_a_completed_offer_cannot_also_fail(self):
        ws = quiet(world())
        ws.settlements["farm_b"].stock["food"] = 1
        o = by_kind(jobs.offers(ws, "market"), "resupply")[0]
        jobs.complete(ws, o)
        with self.assertRaises(ValueError):
            jobs.fail(ws, o)

    def test_bad_offers_are_refused(self):
        ws = quiet(world())
        bogus = jobs.Offer("x:1", "bribe", "settlers", "market", "market", 1, 0, 99, "No.")
        self.assertIn("unknown offer kind", jobs.valid(ws, bogus))
        gone = jobs.Offer("retake:ghosts:farm_a:0", "retake", "ghosts", "market", "farm_a", 1, 0, 99, "No.")
        self.assertIn("no longer exists", jobs.valid(ws, gone))
        with self.assertRaises(ValueError):
            jobs.complete(ws, gone)


if __name__ == "__main__":
    unittest.main()
