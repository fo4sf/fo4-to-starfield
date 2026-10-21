"""Combined-core tuning harness (balance.py): synthetic REGION_1/REGION_2 packs only, placeholder names, not facts."""
import copy
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.combined import balance, fixtures, jobs, model, sim  # noqa: E402
from fo4sf.combined.model import WorldState  # noqa: E402

PACKS = [fixtures.REGION_1, fixtures.REGION_2]


def world(seed=1):
    ws = WorldState(seed=seed)
    for pack in PACKS:
        model.load_pack(ws, copy.deepcopy(pack))
    return ws


def ran(seed=1, days=30):
    ws = world(seed)
    sim.run(ws, days * 24)
    return ws


class MetricsTests(unittest.TestCase):
    def test_fresh_world_is_all_zero_rates(self):
        m = balance.metrics(world())
        self.assertEqual((m["days"], m["places_changed_hands"], m["changes_per_30_days"], m["attacks_per_day"]),
                         (0, 0, 0.0, 0.0))
        self.assertEqual(m["caravans_raided_share"], 0.0)
        self.assertEqual(m["frozen_regions"], ["R1", "R2"])
        self.assertEqual(m["frozen_region_count"], 2)
        self.assertEqual(m["story_lock_violations"], 0)
        self.assertEqual(m["home_violations"], 0)

    def test_counts_match_the_event_log(self):
        ws = ran(4, 30)
        m = balance.metrics(ws)
        taken = [e for e in ws.events if e["kind"] == "place_taken"]
        self.assertEqual(m["places_changed_hands"], len(taken))
        self.assertEqual(m["days"], 30)
        self.assertAlmostEqual(m["changes_per_30_days"], len(taken))
        attacks = sum(e["kind"] == "attack_launched" for e in ws.events)
        self.assertAlmostEqual(m["attacks_per_day"], attacks / 30)
        self.assertEqual(m["empty_settlements"], sum(s.population == 0 for s in ws.settlements.values()))
        self.assertAlmostEqual(m["mean_morale"], sum(s.morale for s in ws.settlements.values()) / len(ws.settlements))
        self.assertEqual(set(m["landless_share"]), set(ws.factions))
        self.assertEqual(set(m["home_only_share"]), set(ws.factions))
        for v in list(m["landless_share"].values()) + list(m["home_only_share"].values()):
            self.assertTrue(0.0 <= v <= 1.0, v)
        self.assertEqual(sorted(m["frozen_regions"]), m["frozen_regions"])
        self.assertEqual(m["frozen_region_count"], len(m["frozen_regions"]))

    def test_raided_share_is_raided_over_finished_caravans(self):
        ws = world()
        for kind in ("caravan_raided", "caravan_arrived", "caravan_arrived", "caravan_lost"):
            ws.events.append({"hour": 6, "kind": kind, "place": "market", "region": "R1"})
        ws.hour = 24
        self.assertAlmostEqual(balance.metrics(ws)["caravans_raided_share"], 0.25)

    def test_holder_timeline_is_rebuilt_from_events(self):
        ws = world()
        ws.hour = 100
        ws.places["ruins"].holder = "raiders"
        ws.events.append({"hour": 25, "kind": "place_taken", "place": "ruins", "region": "R1",
                          "faction": "order", "previous": None, "retaken": False})
        ws.events.append({"hour": 75, "kind": "place_taken", "place": "ruins", "region": "R1",
                          "faction": "raiders", "previous": "order", "retaken": False})
        timeline = balance._holder_timeline(ws)
        self.assertEqual([(h, t["ruins"]) for h, t in timeline], [(0, None), (25, "order"), (75, "raiders")])
        # order held only its home outside hours 25..75: home-only for 50 of 100 hours
        self.assertAlmostEqual(balance.home_only_share(ws)["order"], 0.5)
        self.assertEqual(balance.landless_share(ws)["order"], 0.0)
        self.assertEqual(balance.metrics(ws)["frozen_regions"], ["R2"])

    def test_cleared_place_is_a_change_of_hands_in_the_timeline(self):
        ws = world()
        for f in ws.factions.values():
            f.aggression = 0
        ws.places["ruins"].holder = "raiders"
        ws.events.append({"hour": 0, "kind": "place_taken", "place": "ruins", "region": "R1",
                          "faction": "raiders", "previous": None, "retaken": False})
        sim.run(ws, 24)                                       # hour 24, nothing moves
        offer = [o for o in jobs.offers(ws, "farm_b") if o.kind == "clear"][0]
        jobs.complete(ws, offer)                              # holder None, place_cleared at hour 24
        ws.hour = 96
        timeline = balance._holder_timeline(ws)
        self.assertEqual([(h, t["ruins"]) for h, t in timeline], [(0, None), (0, "raiders"), (24, None)])
        self.assertIn("ruins", sim._lost_places(ws, "raiders"))
        # raiders held more than their home for 24 of 96 hours
        self.assertAlmostEqual(balance.home_only_share(ws)["raiders"], 0.75)
        m = balance.metrics(ws)
        self.assertEqual(m["places_changed_hands"], 2)
        self.assertEqual(m["frozen_regions"], ["R2"])
        self.assertEqual(m["story_lock_violations"], 0)

    def test_violations_are_counted_not_hidden(self):
        ws = world()
        ws.hour = 24
        ws.events.append({"hour": 6, "kind": "place_taken", "place": "story_vault", "region": "R1",
                          "faction": "raiders", "previous": "settlers", "retaken": False})
        ws.places["story_vault"].holder = "raiders"
        ws.places["order_fort"].holder = "raiders"
        m = balance.metrics(ws)
        self.assertEqual(m["story_lock_violations"], 1)
        self.assertEqual(m["home_violations"], 1)

    def test_landless_share_counts_a_faction_with_nothing(self):
        ws = world()
        ws.hour = 100
        ws.places["order_fort"].holder = "raiders"    # not something the sim allows; the metric still sees it
        ws.events.append({"hour": 50, "kind": "place_taken", "place": "order_fort", "region": "R1",
                          "faction": "raiders", "previous": "order", "retaken": False})
        self.assertAlmostEqual(balance.landless_share(ws)["order"], 0.5)

    def test_resumed_save_measures_like_an_unbroken_run(self):
        a = ran(6, 40)
        b = world(6)
        sim.run(b, 20 * 24)
        b = WorldState.from_json(b.to_json())
        sim.run(b, 20 * 24)
        self.assertEqual(balance.metrics(a), balance.metrics(b))


class OverrideTests(unittest.TestCase):
    def test_restores_constants_even_on_error(self):
        before = (sim.UPKEEP_PER_PLACE, sim.RETAKE_WEIGHT)
        with self.assertRaises(RuntimeError):
            with balance.overrides({"sim.UPKEEP_PER_PLACE": 9, "RETAKE_WEIGHT": 1}):
                self.assertEqual((sim.UPKEEP_PER_PLACE, sim.RETAKE_WEIGHT), (9, 1))
                raise RuntimeError("boom")
        self.assertEqual((sim.UPKEEP_PER_PLACE, sim.RETAKE_WEIGHT), before)

    def test_bare_name_resolves_to_the_one_module_that_has_it(self):
        self.assertEqual(balance._resolve("ATTACK_CHANCE_PER_AGGRESSION"), (sim, "ATTACK_CHANCE_PER_AGGRESSION"))
        self.assertEqual(balance._resolve("sim.RAID_CHANCE_CAP"), (sim, "RAID_CHANCE_CAP"))

    def test_rejects_unknown_ambiguous_and_lowercase(self):
        for bad in ("NO_SUCH_CONSTANT", "news.HEADLINE_LIMIT", "sim.tick", "HOURS_PER_DAY"):
            with self.assertRaises(ValueError, msg=bad):
                with balance.overrides({bad: 1}):
                    pass
        self.assertEqual(sim.ATTACK_CHANCE_PER_AGGRESSION, 0.25)   # nothing leaked

    def test_present_is_not_overridable_because_a_sweep_never_runs_it(self):
        self.assertEqual(set(balance.OVERRIDABLE), {"sim"})
        for name in ("present.RADIUS_HOURS", "MAX_LIVE_ACTORS"):
            with self.assertRaises(ValueError, msg=name):
                balance._resolve(name)

    def test_value_of_the_wrong_kind_is_refused_before_the_sweep(self):
        before = (sim.UPKEEP_PER_PLACE, sim.ATTACK_CHANCE_PER_AGGRESSION)
        for name, bad in (("sim.UPKEEP_PER_PLACE", "abc"), ("sim.UPKEEP_PER_PLACE", ""), ("sim.UPKEEP_PER_PLACE", True),
                          ("sim.ATTACK_CHANCE_PER_AGGRESSION", None), ("sim.STAGE_POP", 3)):
            with self.assertRaises(ValueError, msg=f"{name}={bad!r}"):
                with balance.overrides({name: bad}):
                    pass
        with balance.overrides({"sim.ATTACK_CHANCE_PER_AGGRESSION": 1, "sim.UPKEEP_PER_PLACE": 0.5}):   # numbers mix
            self.assertEqual((sim.ATTACK_CHANCE_PER_AGGRESSION, sim.UPKEEP_PER_PLACE), (1, 0.5))
        self.assertEqual((sim.UPKEEP_PER_PLACE, sim.ATTACK_CHANCE_PER_AGGRESSION), before)

    def test_bad_name_after_a_good_one_still_restores(self):
        before = sim.UPKEEP_PER_PLACE
        with self.assertRaises(ValueError):
            with balance.overrides({"sim.UPKEEP_PER_PLACE": 7, "sim.ZZZ_NOPE": 1}):
                pass
        self.assertEqual(sim.UPKEEP_PER_PLACE, before)


class SweepTests(unittest.TestCase):
    def test_deterministic_and_one_entry_per_seed(self):
        a = balance.sweep(PACKS, range(4), 20)
        b = balance.sweep(PACKS, [3, 1, 0, 2, 2], 20)
        self.assertEqual(a, b)
        self.assertEqual(sorted(a["seeds"]), [0, 1, 2, 3])
        self.assertEqual(a["aggregate"]["seeds"], 4)
        self.assertEqual(a["days"], 20)
        self.assertEqual(a["overrides"], {})

    def test_does_not_mutate_the_packs(self):
        packs = copy.deepcopy(PACKS)
        balance.sweep(packs, range(2), 10)
        self.assertEqual(packs, PACKS)

    def test_aggregate_is_the_mean_and_intersection(self):
        r = balance.sweep(PACKS, range(3), 20)
        runs = [r["seeds"][s] for s in sorted(r["seeds"])]
        agg = r["aggregate"]
        self.assertAlmostEqual(agg["changes_per_30_days"], sum(m["changes_per_30_days"] for m in runs) / 3)
        self.assertAlmostEqual(agg["home_only_share"]["raiders"],
                               sum(m["home_only_share"]["raiders"] for m in runs) / 3)
        self.assertEqual(set(agg["frozen_regions"]), set.intersection(*(set(m["frozen_regions"]) for m in runs)))
        self.assertEqual(balance.aggregate({}), {"seeds": 0})

    def test_overrides_change_the_numbers_and_are_restored(self):
        base = balance.sweep(PACKS, range(3), 20)
        still = balance.sweep(PACKS, range(3), 20, {"ATTACK_CHANCE_PER_AGGRESSION": 0.0})
        self.assertEqual(still["aggregate"]["attacks_per_day"], 0.0)
        self.assertEqual(still["aggregate"]["frozen_regions"], ["R1", "R2"])
        self.assertGreater(base["aggregate"]["attacks_per_day"], 0.0)
        self.assertEqual(sim.ATTACK_CHANCE_PER_AGGRESSION, 0.25)
        self.assertEqual(still["overrides"], {"ATTACK_CHANCE_PER_AGGRESSION": 0.0})

    def test_invariants_hold_across_the_baseline(self):
        agg = balance.sweep(PACKS, range(20), 90)["aggregate"]
        self.assertEqual(agg["story_lock_violations"], 0)
        self.assertEqual(agg["home_violations"], 0)
        self.assertEqual(agg["landless_share_max"], 0.0)
        self.assertEqual(balance.check(agg), [])      # the fixtures sit inside their own envelope


class CheckTests(unittest.TestCase):
    def test_reports_each_broken_side(self):
        agg = {"a": 5, "b": 0.5, "c": 3}
        bounds = {"a": (None, 4), "b": (1, None), "c": (0, 10)}
        self.assertEqual(balance.check(agg, bounds), ["a: 5 above 4", "b: 0.5 below 1"])
        self.assertEqual(balance.check(agg, {"c": (3, 3)}), [])

    def test_missing_or_non_numeric_metric_is_a_broken_bound(self):
        self.assertEqual(balance.check({"x": [1]}, {"x": (0, 1), "y": (0, 1)}),
                         ["x: not an aggregate number ([1])", "y: not an aggregate number (None)"])

    def test_default_bounds_pin_the_invariants_to_zero(self):
        self.assertEqual(balance.DEFAULT_BOUNDS["story_lock_violations"], (0, 0))
        self.assertEqual(balance.DEFAULT_BOUNDS["home_violations"], (0, 0))
        agg = balance.sweep(PACKS, range(2), 10)["aggregate"]
        agg["story_lock_violations"] = 1
        self.assertIn("story_lock_violations: 1 above 0", balance.check(agg))


if __name__ == "__main__":
    unittest.main()
