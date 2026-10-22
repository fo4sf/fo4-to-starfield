"""Combined-core play settings (modes.py) and how sim reads them: synthetic fixtures only, placeholder names."""
import copy
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.combined import fixtures, model, modes, sim  # noqa: E402
from fo4sf.combined.model import SCHEMA_VERSION, WorldState  # noqa: E402
from fo4sf.combined.modes import Settings  # noqa: E402

SEEDS = range(20)
DAYS = 90


def world(seed=1, **settings):
    ws = WorldState(seed=seed)
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_1))
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_2))
    for k, v in settings.items():
        setattr(ws.settings, k, v)
    ws.settings.validate()
    return ws


def attacks(ws):
    return [e for e in ws.events if e["kind"] == "attack_launched"]


def total_attacks(**settings):
    n = 0
    for seed in SEEDS:
        ws = world(seed, **settings)
        sim.run(ws, DAYS * 24)
        n += len(attacks(ws))
    return n


class SettingsTests(unittest.TestCase):
    def test_defaults_are_off_normal_and_no_story_mode(self):
        s = Settings()
        self.assertEqual((s.survival, s.raid_pressure, s.story_mode, s.active_stories), ("off", "normal", False, []))
        self.assertFalse(s.survival_preset().enabled)
        self.assertEqual(s.raid_multiplier(), 1.0)

    def test_presets_are_complete_and_validated(self):
        self.assertEqual(sorted(modes.SURVIVAL_PRESETS), sorted(modes.SURVIVAL_PRESET_NAMES))
        self.assertEqual(sorted(modes.RAID_PRESSURE_MULTIPLIER), sorted(modes.RAID_PRESSURE_NAMES))
        self.assertLess(modes.RAID_PRESSURE_MULTIPLIER["low"], modes.RAID_PRESSURE_MULTIPLIER["normal"])
        self.assertLess(modes.RAID_PRESSURE_MULTIPLIER["normal"], modes.RAID_PRESSURE_MULTIPLIER["high"])
        for name in modes.SURVIVAL_PRESET_NAMES:
            p = modes.SURVIVAL_PRESETS[name]
            self.assertEqual(p.enabled, name != "off")
            self.assertTrue(p.food_per_day >= 0 and p.water_per_day >= 0)
        with self.assertRaisesRegex(ValueError, "survival"):
            Settings(survival="hardcore").validate()
        with self.assertRaisesRegex(ValueError, "raid pressure"):
            Settings(raid_pressure="extreme").validate()
        with self.assertRaises(ValueError):
            Settings(story_mode="yes").validate()
        with self.assertRaises(ValueError):
            Settings(active_stories=[3]).validate()

    def test_story_set_semantics(self):
        s = Settings(story_mode=True)
        s.start_story("b")
        s.start_story("a")
        s.start_story("a")
        self.assertEqual(s.active_stories, ["a", "b"])
        self.assertTrue(s.story_active("a"))
        self.assertFalse(s.story_active("c"))
        self.assertFalse(s.story_active(None))
        s.finish_story("a")
        self.assertEqual(s.active_stories, ["b"])
        s.story_mode = False
        self.assertFalse(s.story_active("b"))          # off: nothing is active, whatever the list says

    def test_dict_round_trip_and_defaults_for_missing_keys(self):
        s = Settings(survival="light", raid_pressure="high", story_mode=True, active_stories=["z", "y"])
        back = Settings.from_dict(json.loads(json.dumps(s.to_dict())))
        self.assertEqual(back.active_stories, ["y", "z"])
        self.assertEqual((back.survival, back.raid_pressure, back.story_mode), ("light", "high", True))
        self.assertEqual(Settings.from_dict(None), Settings())
        self.assertEqual(Settings.from_dict({"survival": "full"}), Settings(survival="full"))


class SaveTests(unittest.TestCase):
    def test_settings_ride_in_world_json(self):
        ws = world(3, survival="full", raid_pressure="low", story_mode=True, active_stories=["main_story_1"])
        d = json.loads(ws.to_json())
        self.assertEqual(d["schema"], SCHEMA_VERSION)
        self.assertEqual(d["settings"]["raid_pressure"], "low")
        back = WorldState.from_json(ws.to_json())
        self.assertEqual(back.settings, ws.settings)
        self.assertEqual(back, ws)

    def test_version_1_save_still_loads_with_defaults(self):
        ws = world(3)
        d = json.loads(ws.to_json())
        d["schema"] = 1
        del d["settings"]
        del d["regional_reputation"]
        back = WorldState.from_json(json.dumps(d))
        self.assertEqual(back.settings, Settings())
        self.assertEqual(back.regional_reputation, {})
        self.assertEqual(back.places, ws.places)
        self.assertEqual(back.factions, ws.factions)
        self.assertEqual(json.loads(back.to_json())["schema"], SCHEMA_VERSION)   # re-saved as the current schema

    def test_unknown_schema_still_rejected(self):
        d = json.loads(world(3).to_json())
        d["schema"] = SCHEMA_VERSION + 1
        with self.assertRaises(ValueError):
            WorldState.from_json(json.dumps(d))
        d["schema"] = 0
        with self.assertRaises(ValueError):
            WorldState.from_json(json.dumps(d))

    def test_bad_settings_in_a_save_fail_loudly(self):
        d = json.loads(world(3).to_json())
        d["settings"]["raid_pressure"] = "nope"
        with self.assertRaises(ValueError):
            WorldState.from_json(json.dumps(d))

    def test_active_stories_must_be_a_list_not_a_string(self):
        d = json.loads(world(3).to_json())
        d["settings"]["active_stories"] = "abc"
        with self.assertRaises(ValueError):
            WorldState.from_json(json.dumps(d))
        with self.assertRaises(ValueError):
            Settings(active_stories="abc").validate()
        with self.assertRaises(ValueError):
            Settings(active_stories=["a", 1]).validate()


class RaidPressureTests(unittest.TestCase):
    def test_low_launches_fewer_attacks_than_normal_than_high_over_20_seeds(self):
        low, normal, high = (total_attacks(raid_pressure=p) for p in ("low", "normal", "high"))
        self.assertGreater(low, 0)
        self.assertLess(low, normal)
        self.assertLess(normal, high)

    def test_normal_replays_the_unscaled_world(self):
        a, b = world(5), world(5, raid_pressure="normal")
        sim.run(a, DAYS * 24)
        sim.run(b, DAYS * 24)
        self.assertEqual(a.to_json(), b.to_json())

    def test_caravan_raid_chance_scales_with_pressure(self):
        # the roll is rng.random() < chance; a draw just under the low chance only intercepts under high pressure
        q = model.Squad(id="c1", faction="settlers", size=2, at="farm_a", goal="market", kind="caravan",
                        cargo={"food": 5}, eta=6)
        seen = {}
        for pressure in ("low", "high"):
            ws = world(1, raid_pressure=pressure)
            ws.factions["raiders"].strength = 10            # 0.10 base chance, under the cap even doubled
            rng = mock.Mock()
            rng.random.return_value = 0.15
            seen[pressure] = sim._raider(ws, q, rng)
        self.assertIsNone(seen["low"])
        self.assertEqual(seen["high"], "raiders")

    def test_pressure_keeps_determinism_and_invariants(self):
        for pressure in ("low", "high"):
            a, b = world(2, raid_pressure=pressure), world(2, raid_pressure=pressure)
            sim.run(a, DAYS * 24)
            sim.run(b, DAYS * 24)
            self.assertEqual(a.to_json(), b.to_json())
            for fid, f in a.factions.items():
                self.assertEqual(a.places[f.home].holder, fid)
                self.assertTrue(0 <= f.strength <= sim.STRENGTH_CAP)


class SettingsShapeTests(unittest.TestCase):
    def test_only_a_missing_block_defaults(self):
        # Codex review of #431: a present non-object is a broken save, not a version-1 one
        self.assertEqual(Settings.from_dict(None).to_dict(), Settings().to_dict())
        for bad in ([], "", 0, ["survival"]):
            with self.assertRaises(ValueError):
                Settings.from_dict(bad)


class StoryModeTests(unittest.TestCase):
    """REGION_1's story_vault is locked to main_story_1 (placeholder names). With the shield widened to 12 route-hours
    it covers farm_a, farm_b and ruins, which the unshielded world attacks in every seed set."""

    def shielded_targets(self, **settings):
        hit = set()
        with mock.patch.object(sim, "STORY_SHIELD_HOURS", 12):
            area = sim._story_shielded(world(1, story_mode=True, active_stories=["main_story_1"]))
            for seed in SEEDS:
                ws = world(seed, **settings)
                sim.run(ws, DAYS * 24)
                hit |= {e["target"] for e in attacks(ws)}
        return area, hit

    def test_shield_area_is_route_distance_from_active_story_places(self):
        ws = world(1)
        self.assertEqual(sim._story_shielded(ws), set())                       # story mode off
        ws.settings.story_mode = True
        self.assertEqual(sim._story_shielded(ws), set())                       # on, but no story active
        ws.settings.start_story("main_story_1")
        self.assertEqual(sim._story_shielded(ws), {"story_vault", "market", "raider_camp"})
        with mock.patch.object(sim, "STORY_SHIELD_HOURS", 12):
            self.assertEqual(sim._story_shielded(ws),
                             {"story_vault", "market", "raider_camp", "farm_a", "farm_b", "ruins"})
        ws.settings.finish_story("main_story_1")
        self.assertEqual(sim._story_shielded(ws), set())

    def test_story_mode_protects_the_area_and_the_sandbox_still_moves_elsewhere(self):
        area, protected = self.shielded_targets(story_mode=True, active_stories=["main_story_1"])
        _, open_world = self.shielded_targets()
        self.assertTrue(open_world & area, open_world)                         # off: the area is attacked
        self.assertEqual(protected & area, set(), protected)                   # on: never
        self.assertTrue(protected - area, protected)                           # but the rest of the world goes on

    def test_an_attack_already_on_its_way_is_called_off(self):
        # Codex review of #431: a story that starts after dispatch still shields the target on arrival
        ws = world(1, story_mode=True)
        holder = ws.places["market"].holder
        attacker = next(f for f in sorted(ws.factions) if f != holder)
        ws.squads["q_test"] = model.Squad(id="q_test", faction=attacker, size=50, at="raider_camp", goal="market",
                                          kind="attack", eta=ws.hour + 1)
        ws.settings.start_story("main_story_1")
        sim.run(ws, 2)
        self.assertEqual(ws.places["market"].holder, holder)
        self.assertNotIn("q_test", ws.squads)
        self.assertEqual([e["faction"] for e in ws.events if e["kind"] == "attack_called_off"], [attacker])

    def test_story_mode_without_an_active_story_changes_nothing(self):
        a, b = world(4), world(4, story_mode=True)
        sim.run(a, DAYS * 24)
        sim.run(b, DAYS * 24)
        self.assertEqual(a.events, b.events)

    def test_story_mode_survives_a_save(self):
        ws = world(4, story_mode=True, active_stories=["main_story_1"])
        sim.run(ws, 30 * 24)
        back = WorldState.from_json(ws.to_json())
        sim.run(ws, 30 * 24)
        sim.run(back, 30 * 24)
        self.assertEqual(ws.to_json(), back.to_json())


if __name__ == "__main__":
    unittest.main()
