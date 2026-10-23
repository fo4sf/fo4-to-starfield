"""Combined-core engine adapter (adapter.py): record plan and game view over synthetic packs; placeholder names only."""
import copy
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.combined import adapter, fixtures, model, reputation, sim  # noqa: E402
from fo4sf.combined.model import WorldState  # noqa: E402


def world(seed=1, both=True):
    ws = WorldState(seed=seed)
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_1))
    if both:
        model.load_pack(ws, copy.deepcopy(fixtures.REGION_2))
    return ws


class EditorIdTests(unittest.TestCase):
    def test_prefix_and_valid_characters(self):
        self.assertEqual(adapter.editor_id("Place", "farm_a"), "FOCC_Place_farm_a")
        self.assertEqual(adapter.editor_id("Place", "farm-a.b c"), "FOCC_Place_farm_a_b_c")
        for eid in (adapter.editor_id("Rep", "x"), adapter.editor_id("StoryMode")):
            self.assertRegex(eid, adapter.EDITOR_ID_RE)

    def test_limits(self):
        with self.assertRaisesRegex(ValueError, "longer"):
            adapter.editor_id("Place", "x" * adapter.EDITOR_ID_MAX)
        with self.assertRaisesRegex(ValueError, "non-empty"):
            adapter.editor_id("")
        adapter.editor_id("Place", "x" * (adapter.EDITOR_ID_MAX - len("FOCC_Place_")))   # exactly at the limit


class PlanTests(unittest.TestCase):
    def test_slots_cover_places_factions_and_settings(self):
        ws = world()
        plan = adapter.record_plan(ws)
        by_purpose = {}
        for s in plan.slots:
            by_purpose.setdefault(s.purpose, []).append(s)
        self.assertEqual(sorted(s.subject for s in by_purpose["holder"]), sorted(ws.places))
        self.assertEqual(sorted(s.subject for s in by_purpose["reputation"]), sorted(ws.factions))
        self.assertEqual(tuple(sorted(s.subject for s in by_purpose["setting"])), tuple(sorted(adapter.SETTINGS_GLOBALS)))
        self.assertTrue(all(s.kind == "keyword" and s.probe == "P2" for s in by_purpose["holder"]))
        self.assertTrue(all(s.kind == "global" and s.probe is None
                            for s in by_purpose["reputation"] + by_purpose["setting"]))
        self.assertEqual([s.id for s in plan.slots], sorted(s.id for s in plan.slots))
        self.assertEqual(len({s.id for s in plan.slots}), len(plan.slots))
        for s in plan.slots:
            self.assertTrue(s.id.startswith(adapter.PREFIX))
            self.assertRegex(s.id, adapter.EDITOR_ID_RE)
            self.assertLessEqual(len(s.id), adapter.EDITOR_ID_MAX)

    def test_holder_codes_from_sorted_faction_ids(self):
        ws = world()
        codes = adapter.record_plan(ws).holder_codes
        self.assertEqual(list(codes), sorted(ws.factions))
        self.assertEqual(sorted(codes.values()), list(range(1, len(ws.factions) + 1)))
        self.assertNotIn(adapter.EMPTY_HOLDER, codes.values())
        # the first region alone keeps the same relative order: codes depend only on the faction set
        self.assertEqual(adapter.holder_codes(world(both=False)), {f: n for n, f in
                         enumerate(sorted(world(both=False).factions), start=1)})

    def test_plan_is_deterministic_and_serializable(self):
        a, b = adapter.record_plan(world()), adapter.record_plan(world())
        self.assertEqual(a, b)
        self.assertEqual(a.to_dict()["prefix"], "FOCC_")
        self.assertIsInstance(a.to_dict()["slots"][0], dict)

    def test_colliding_ids_are_refused(self):
        ws = world(both=False)
        ws.places["farm-a"] = copy.deepcopy(ws.places["farm_a"])
        with self.assertRaisesRegex(ValueError, "collides"):
            adapter.record_plan(ws)

    def test_custom_prefix(self):
        plan = adapter.record_plan(world(both=False), prefix="X_")
        self.assertTrue(all(s.id.startswith("X_") for s in plan.slots))


class ViewTests(unittest.TestCase):
    def test_view_reports_holders_tiers_and_settings(self):
        ws = world()
        plan = adapter.record_plan(ws)
        view = adapter.game_view(ws, plan)
        self.assertEqual(set(view), {s.id for s in plan.slots})
        self.assertTrue(all(isinstance(v, int) for v in view.values()))
        self.assertEqual(view["FOCC_Place_ruins"], adapter.EMPTY_HOLDER)              # nobody holds the ruins
        self.assertEqual(view["FOCC_Place_market"], plan.holder_codes["settlers"])
        self.assertEqual(view["FOCC_Rep_raiders"], 0)                                 # neutral at start
        self.assertEqual(view["FOCC_Survival"], 0)
        self.assertEqual(view["FOCC_RaidPressure"], 1)                                # "normal"
        self.assertEqual(view["FOCC_StoryMode"], 0)
        self.assertEqual(view["FOCC_StoryActive"], 0)

    def test_settings_map_to_indices(self):
        ws = world(both=False)
        ws.settings.survival, ws.settings.raid_pressure, ws.settings.story_mode = "full", "high", True
        ws.settings.start_story("main_story_1")
        view = adapter.game_view(ws)
        self.assertEqual((view["FOCC_Survival"], view["FOCC_RaidPressure"]), (2, 2))
        self.assertEqual((view["FOCC_StoryMode"], view["FOCC_StoryActive"]), (1, 1))
        ws.settings.story_mode = False
        self.assertEqual(adapter.game_view(ws)["FOCC_StoryActive"], 0)    # a story outside story mode shields nothing

    def test_reputation_tier_encodes_the_grid_cell(self):
        ws = world(both=False)
        rep = ws.reputation["settlers"]
        rep.fame, rep.infamy = reputation.LEVEL_THRESHOLDS[2], reputation.LEVEL_THRESHOLDS[1]
        self.assertEqual(adapter.reputation_tier(ws, "settlers"), 2 * reputation.LEVELS + 1)
        self.assertEqual(adapter.game_view(ws)["FOCC_Rep_settlers"], 2 * reputation.LEVELS + 1)
        rep.fame, rep.infamy = 10 ** 6, 10 ** 6
        self.assertEqual(adapter.reputation_tier(ws, "settlers"), reputation.LEVELS ** 2 - 1)

    def test_view_follows_the_simulation(self):
        ws = world(seed=3)
        plan = adapter.record_plan(ws)
        before = adapter.game_view(ws, plan)
        sim.run(ws, 90 * 24)
        after = adapter.game_view(ws, plan)
        self.assertEqual(set(before), set(after))
        for pid, pl in ws.places.items():
            want = adapter.EMPTY_HOLDER if pl.holder is None else plan.holder_codes[pl.holder]
            self.assertEqual(after[f"FOCC_Place_{pid}"], want)
        self.assertEqual(adapter.game_view(ws, plan), after)         # reading twice changes nothing


class ChangesTests(unittest.TestCase):
    def test_minimal_writes(self):
        old = {"FOCC_Place_a": 1, "FOCC_Place_b": 0, "FOCC_Rep_x": 0}
        new = {"FOCC_Place_a": 1, "FOCC_Place_b": 2, "FOCC_Rep_x": 5, "FOCC_StoryMode": 0}
        self.assertEqual(adapter.changes(old, new),
                         [("FOCC_Place_b", 2), ("FOCC_Rep_x", 5), ("FOCC_StoryMode", 0)])
        self.assertEqual(adapter.changes(new, new), [])
        self.assertEqual(adapter.changes(None, {"b": 1, "a": 0}), [("a", 0), ("b", 1)])
        self.assertEqual(adapter.changes({"gone": 1}, {}), [])        # a slot leaving the plan is not a write

    def test_changes_track_a_capture(self):
        ws = world(seed=5)
        plan = adapter.record_plan(ws)
        before = adapter.game_view(ws, plan)
        ws.places["ruins"].holder = "raiders"
        writes = adapter.changes(before, adapter.game_view(ws, plan))
        self.assertEqual(writes, [("FOCC_Place_ruins", plan.holder_codes["raiders"])])


if __name__ == "__main__":
    unittest.main()
