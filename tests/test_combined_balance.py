"""Combined-core tuning harness (balance.py): synthetic REGION_1/REGION_2 packs only, placeholder names, not facts."""
import copy
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.combined import balance, fixtures, jobs, model, seedpack, sim  # noqa: E402
from fo4sf.combined.model import WorldState  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_combined_seedpack import commonwealth_scale_draft  # noqa: E402

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

    def test_settlements_without_beds_do_not_crash(self):
        # Codex P2 on #431: validate_pack allows beds 0, and mean() of nothing raised StatisticsError.
        ws = world()
        for s in ws.settlements.values():
            s.beds, s.population = 0, 0
            s.roles = {r: 0 for r in s.roles}
        self.assertEqual(balance.metrics(ws)["mean_population_share"], 0.0)

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
        # scale-free rates and per-faction tables
        self.assertAlmostEqual(m["changes_per_30_days_per_place"], m["changes_per_30_days"] / len(ws.places))
        self.assertAlmostEqual(m["attacks_per_day_per_faction"], m["attacks_per_day"] / len(ws.factions))
        captures = [e for e in taken if e["place"] in ws.settlements]
        self.assertEqual(m["settlement_captures"], len(captures))
        self.assertAlmostEqual(m["settlement_captures_per_30_days"], len(captures))
        self.assertEqual(set(m["places_taken_by"]), set(ws.factions))
        self.assertEqual(sum(m["places_taken_by"].values()), len(taken))
        self.assertEqual(sum(m["places_lost_by"].values()), sum(1 for e in taken if e["previous"]))
        self.assertAlmostEqual(m["settlements_at_cap_share"],
                               sum(s.population >= s.beds for s in ws.settlements.values()) / 4)
        self.assertAlmostEqual(m["mean_population_share"],
                               sum(s.population / s.beds for s in ws.settlements.values()) / 4)

    def test_enemy_rates_count_every_faction_but_the_one_holding_most_settlements(self):
        ws = world()
        self.assertEqual(balance._settler_faction(ws), "settlers")              # 3 of 4 settlements
        ws.hour = 24 * 30
        for faction, previous, place in (("raiders", "settlers", "farm_a"), ("settlers", "raiders", "farm_a"),
                                         ("order", None, "ruins"), ("slavers", "traders", "river_town")):
            ws.events.append({"hour": 6, "kind": "place_taken", "place": place, "region": "R1", "faction": faction,
                              "previous": previous, "retaken": False})
        m = balance.metrics(ws)
        self.assertEqual(m["enemy_takes_per_30_days"], 3)                       # raiders, order, slavers
        self.assertEqual(m["enemy_losses_per_30_days"], 2)                      # raiders and traders lost one each
        self.assertEqual(m["settlement_captures"], 3)
        self.assertEqual(m["places_taken_by"], {"order": 1, "raiders": 1, "settlers": 1, "slavers": 1, "traders": 0})
        self.assertEqual(m["places_lost_by"], {"order": 0, "raiders": 1, "settlers": 1, "slavers": 0, "traders": 1})
        empty = WorldState(seed=1)
        self.assertIsNone(balance._settler_faction(empty))
        self.assertEqual(balance.metrics(empty)["places_taken_by"], {})

    def test_empty_hours_are_rebuilt_from_emptied_and_resettled_events(self):
        ws = world()
        ws.hour = 100
        for hour, kind, place in ((10, "settlement_emptied", "farm_a"), (30, "settlement_resettled", "farm_a"),
                                  (20, "settler_arrived", "market"),            # no open span: ignored
                                  (50, "settlement_emptied", "farm_b"),         # open until the end
                                  (80, "settlement_emptied", "farm_a"), (90, "settler_arrived", "farm_a"),
                                  (95, "settlement_emptied", "ruins")):         # not a settlement: ignored
            ws.events.append({"hour": hour, "kind": kind, "place": place, "region": "R1"})
        self.assertEqual(balance.empty_hours(ws), {"farm_a": 30, "farm_b": 50, "market": 0, "river_town": 0})
        m = balance.metrics(ws)
        self.assertAlmostEqual(m["empty_share"], 80 / 400)
        self.assertEqual((m["settlements_emptied"], m["resettlements"]), (4, 1))   # raw log counts
        self.assertEqual(balance.metrics(world())["empty_share"], 0.0)

    def test_empty_share_matches_a_population_trace(self):
        ws = world(9)
        hours = {sid: 0 for sid in ws.settlements}
        for _ in range(60 * 24 // sim.TICK_HOURS):
            sim.tick(ws)
            for sid, s in ws.settlements.items():
                hours[sid] += sim.TICK_HOURS * (s.population == 0)
        self.assertEqual(balance.empty_hours(ws), hours)

    def test_settlements_that_start_empty_count_from_hour_zero(self):
        # Codex review of #431: no `settlement_emptied` opens their span, so hour 0 does.
        ws = world()
        ws.hour = 100
        ws.settlements["farm_b"].population = 0                                  # empty all run, no events
        ws.events.append({"hour": 40, "kind": "settlement_resettled", "place": "farm_a", "region": "R1"})
        ws.events.append({"hour": 70, "kind": "settlement_emptied", "place": "farm_a", "region": "R1"})
        self.assertEqual(balance.empty_hours(ws), {"farm_a": 40 + 30, "farm_b": 100, "market": 0, "river_town": 0})
        trace = world(9)
        trace.settlements[sorted(trace.settlements)[0]].population = 0
        hours = {sid: 0 for sid in trace.settlements}
        for _ in range(60 * 24 // sim.TICK_HOURS):
            for sid, st in trace.settlements.items():
                hours[sid] += sim.TICK_HOURS * (st.population == 0)
            sim.tick(trace)
        self.assertEqual(balance.empty_hours(trace), hours)

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
                          ("sim.ATTACK_CHANCE_PER_AGGRESSION", None), ("sim.STAGE_POP", 3),
                          ("sim.REROLE_ON_SHORTAGE", 1.5), ("sim.UPKEEP_PER_PLACE", 0.5)):   # a fraction for an int
            with self.assertRaises(ValueError, msg=f"{name}={bad!r}"):
                with balance.overrides({name: bad}):
                    pass
        with balance.overrides({"sim.ATTACK_CHANCE_PER_AGGRESSION": 1, "sim.UPKEEP_PER_PLACE": 2}):   # int for a float
            self.assertEqual((sim.ATTACK_CHANCE_PER_AGGRESSION, sim.UPKEEP_PER_PLACE), (1, 2))
        self.assertEqual((sim.UPKEEP_PER_PLACE, sim.ATTACK_CHANCE_PER_AGGRESSION), before)

    def test_nonpositive_tick_hours_is_refused(self):
        # Codex review of #431: sim.run never reaches its end with a tick of 0 or less hours.
        before = sim.TICK_HOURS
        for bad in (0, -1, 0.0, 7, 5, 48):            # and a tick that skips midnights (Codex review of #431)
            with self.assertRaises(ValueError, msg=repr(bad)):
                with balance.overrides({"sim.TICK_HOURS": bad}):
                    pass
        self.assertEqual(sim.TICK_HOURS, before)
        for good in (1, 3, 8, 12, 24):
            with balance.overrides({"sim.TICK_HOURS": good}):
                self.assertEqual(sim.TICK_HOURS, good)

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
        self.assertAlmostEqual(agg["places_taken_by"]["raiders"], sum(m["places_taken_by"]["raiders"] for m in runs) / 3)
        self.assertEqual(balance.aggregate({}), {"seeds": 0})

    def test_overrides_change_the_numbers_and_are_restored(self):
        base = balance.sweep(PACKS, range(3), 20)
        still = balance.sweep(PACKS, range(3), 20, {"ATTACK_CHANCE_PER_AGGRESSION": 0.0})
        self.assertEqual(still["aggregate"]["attacks_per_day"], 0.0)
        self.assertEqual(still["aggregate"]["frozen_regions"], ["R1", "R2"])
        self.assertGreater(base["aggregate"]["attacks_per_day"], 0.0)
        self.assertEqual(sim.ATTACK_CHANCE_PER_AGGRESSION, 0.25)
        self.assertEqual(still["overrides"], {"ATTACK_CHANCE_PER_AGGRESSION": 0.0})

    def test_a_shared_constant_is_set_everywhere(self):
        # Codex review of #431: STRENGTH_CAP lives in model and is imported by sim and pack; one override sets all
        from fo4sf.combined import model, pack
        with balance.overrides({"sim.STRENGTH_CAP": 1}):
            self.assertEqual((model.STRENGTH_CAP, sim.STRENGTH_CAP, pack.STRENGTH_CAP), (1, 1, 1))
        self.assertEqual((model.STRENGTH_CAP, sim.STRENGTH_CAP, pack.STRENGTH_CAP), (60, 60, 60))

    def test_invariants_hold_across_the_baseline(self):
        agg = balance.sweep(PACKS, range(20), 90)["aggregate"]
        self.assertEqual(agg["story_lock_violations"], 0)
        self.assertEqual(agg["home_violations"], 0)
        self.assertEqual(agg["landless_share_max"], 0.0)
        self.assertEqual(balance.check(agg), [])      # the fixtures sit inside their own envelope
        self.assertGreater(agg["resettlements"], 0)   # places fall and are resettled (sim.RESETTLE_*)
        self.assertGreater(agg["settlements_emptied"], 0)
        self.assertLess(agg["empty_settlements"], 1.0)


class CommonwealthScaleSweepTests(unittest.TestCase):
    """The synthetic Commonwealth-scale pack (test_combined_seedpack.commonwealth_scale_draft) over 5 seeds x 90 days
    sits inside balance.SCALE_BOUNDS: settlements grow but do not all saturate, enemies take and lose places. The
    numbers are the "after" column of docs/combined-core.md "Commonwealth-scale baseline"."""

    @classmethod
    def setUpClass(cls):
        cls.pack, _ = seedpack.generate(commonwealth_scale_draft())
        cls.sweep = balance.sweep([cls.pack], range(5), 90)

    def test_inside_the_scale_envelope(self):
        agg = self.sweep["aggregate"]
        self.assertEqual(balance.check(agg, balance.SCALE_BOUNDS), [])
        self.assertEqual((agg["story_lock_violations"], agg["home_violations"]), (0, 0))
        self.assertLess(agg["settlements_at_cap_share"], 0.3)
        self.assertGreater(agg["mean_population_share"], 0.5)
        self.assertTrue(40 < agg["mean_morale"] < 95)
        self.assertEqual(agg["empty_settlements"], 0)

    def test_every_enemy_faction_takes_and_loses_ground(self):
        agg = self.sweep["aggregate"]
        for fid in ("creatures", "ghouls", "gunners", "raiders", "robots", "supermutants"):
            self.assertGreater(agg["places_taken_by"][fid], 0, fid)
            self.assertGreater(agg["places_lost_by"][fid], 0, fid)
        self.assertGreater(agg["settlement_captures"], 0)

    def test_first_prototype_rules_saturate_the_same_pack(self):
        old = {"sim.FARM_SLOTS_PER_BEDS": 0, "sim.LEAVE_ONLY_WHEN_SHORT": 0, "sim.MORALE_DRIFT": 0,
               "sim.ARRIVAL_SLOWDOWN_POP": 0}
        agg = balance.sweep([self.pack], range(2), 90, old)["aggregate"]
        self.assertGreater(agg["settlements_at_cap_share"], 0.9)
        self.assertGreater(agg["mean_morale"], 95)
        self.assertIn("settlements_at_cap_share", " ".join(balance.check(agg, balance.SCALE_BOUNDS)))


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
