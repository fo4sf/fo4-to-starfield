"""Unit and 25-seed completability tests for X9 world-state radiant missions (cross-OS safe)."""
from __future__ import annotations

import os
import posixpath
import re
import sys
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
SCRIPTS_ALIFE_DIR = os.path.join(REPO_ROOT, "scripts", "alife")
for _p in (SRC_DIR, SCRIPTS_ALIFE_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fo4sf.alife import radiant_missions, schema  # noqa: E402
import demo_radiant_missions  # noqa: E402


class RadiantMissionsVerificationTest(unittest.TestCase):
    def test_25_seeds_commonwealth_all_completable_and_diverse(self) -> None:
        cfg = schema.load_preset("fo4sf_commonwealth")
        summary = radiant_missions.run_multi_seed_verification(cfg, num_seeds=25, ticks=600, max_per_seed=4)
        self.assertTrue(summary["all_completable"], summary["failures"])
        self.assertEqual(summary["failures"], [])
        self.assertGreaterEqual(summary["total_missions_generated"], 75)
        # Every one of the 5 request types should appear naturally across 25 Commonwealth war seeds
        for rtype in radiant_missions.REQUEST_TYPES:
            self.assertGreater(summary["by_request_type"][rtype], 0, f"request type {rtype} never generated")
        self.assertGreaterEqual(summary["unique_target_nodes"], 6)
        # Never routes offers onto Pip-Boy STAT or INV
        for tab in summary["by_secondary_device_tab"]:
            self.assertIn(tab, ("bounties", "settlements", "warfare", "faction_comms"))

    def test_20_seeds_vanilla_new_atlantis_all_completable(self) -> None:
        cfg = schema.load_preset("vanilla_new_atlantis")
        summary = radiant_missions.run_multi_seed_verification(cfg, num_seeds=20, ticks=500, max_per_seed=3)
        self.assertTrue(summary["all_completable"], summary["failures"])
        self.assertGreaterEqual(summary["total_missions_generated"], 40)

    def test_rejects_fewer_than_20_seeds_in_benchmark(self) -> None:
        cfg = schema.load_preset("fo4sf_commonwealth")
        with self.assertRaises(ValueError):
            radiant_missions.run_multi_seed_verification(cfg, num_seeds=19, ticks=100)

    def test_quality_guard_blocks_duplicate_target_in_batch_and_recent_pair(self) -> None:
        cfg = schema.load_preset("fo4sf_commonwealth")
        snap = radiant_missions.snapshot_from_simulation(cfg, ticks=600, seed=7)
        guard = radiant_missions.QualityGuard(cooldown_window=6)
        batch_1 = radiant_missions.generate_missions_from_world_state(snap, max_missions=4, seed=7, quality_guard=guard)
        self.assertEqual(len({m.target_node_index for m in batch_1}), len(batch_1))
        first_pair = (batch_1[0].request_type, batch_1[0].target_node_index)
        self.assertFalse(guard.allows(first_pair[0], first_pair[1], set()))

    def test_completeness_validator_catches_nonsense_combinations(self) -> None:
        cfg = schema.load_preset("fo4sf_commonwealth")
        snap = radiant_missions.snapshot_from_simulation(cfg, ticks=600, seed=3)
        valid = radiant_missions.generate_missions_from_world_state(snap, max_missions=1, seed=3)[0]
        ok, probs = radiant_missions.verify_mission_completable(valid, snap)
        self.assertTrue(ok, probs)

        # 1. Self-loop (giver == target)
        bad_loop = radiant_missions.RadiantMission(**{
            **valid.__dict__,
            "target_node_index": valid.giver_node_index,
        })
        ok, probs = radiant_missions.verify_mission_completable(bad_loop, snap)
        self.assertFalse(ok)
        self.assertTrue(any("self-loop" in p for p in probs))

        # 2. Friendly-fire kill contract (non-hostile target faction)
        bad_ff = radiant_missions.RadiantMission(**{
            **valid.__dict__,
            "request_type": "kill_named_threat",
            "target_faction_index": valid.giver_faction_index,
        })
        ok, probs = radiant_missions.verify_mission_completable(bad_ff, snap)
        self.assertFalse(ok)
        self.assertTrue(any("hostile target faction" in p for p in probs))

        # 3. Escort into hostile-occupied node
        hostile_node = next(
            i for i, o in enumerate(snap.node_owners)
            if o >= 0 and snap.hostile[valid.giver_faction_index][o]
        )
        route = tuple(snap.graph.route(valid.giver_node_index, hostile_node) or ())
        bad_escort = radiant_missions.RadiantMission(**{
            **valid.__dict__,
            "request_type": "escort_or_deliver",
            "target_node_index": hostile_node,
            "route_nodes": route,
        })
        ok, probs = radiant_missions.verify_mission_completable(bad_escort, snap)
        self.assertFalse(ok)
        self.assertTrue(any("occupied by a hostile" in p for p in probs))

        # 4. Wrong UI surface (attempting to place job board on Pip-Boy STAT)
        bad_ui = radiant_missions.RadiantMission(**{
            **valid.__dict__,
            "secondary_device_tab": "stat",
        })
        ok, probs = radiant_missions.verify_mission_completable(bad_ui, snap)
        self.assertFalse(ok)

    def test_w7_dead_giver_and_ally_preclear_and_expiration_never_dead_end(self) -> None:
        cfg = schema.load_preset("fo4sf_commonwealth")
        snap = radiant_missions.snapshot_from_simulation(cfg, ticks=600, seed=11)
        batch = radiant_missions.generate_missions_from_world_state(snap, max_missions=3, seed=11)
        m = batch[0]

        # Normal completion with living giver
        u1, r1 = radiant_missions.resolve_mission_outcome(m, objective_done=True, giver_alive=True)
        self.assertEqual(u1.state, "completed")
        self.assertTrue(r1["terminal"])
        self.assertGreater(r1["reward_caps"], 0)

        # W7 Open Mode: primary giver died -> deputy role succession completes cleanly
        u2, r2 = radiant_missions.resolve_mission_outcome(m, objective_done=True, giver_alive=False, deputy_alive=True)
        self.assertEqual(u2.state, "completed_via_deputy")
        self.assertTrue(r2["terminal"])
        self.assertIn("deputy:", r2["turnin_channel"])

        # W7 Open Mode: entire settlement wiped out -> secondary device faction_comms dropbox completes cleanly
        u3, r3 = radiant_missions.resolve_mission_outcome(m, objective_done=True, giver_alive=False, deputy_alive=False)
        self.assertEqual(u3.state, "completed_via_comms")
        self.assertTrue(r3["terminal"])
        self.assertEqual(r3["turnin_channel"], "device:faction_comms")

        # Friendly A-Life squad cleared target while player was walking there -> graceful partial payout
        u4, r4 = radiant_missions.resolve_mission_outcome(m, objective_done=False, cleared_by_alife_ally=True)
        self.assertEqual(u4.state, "resolved_by_alife_ally")
        self.assertTrue(r4["terminal"])
        self.assertEqual(r4["reward_caps"], max(25, m.reward_caps // 2))

        # Deadline expired -> failed_with_consequence frees slot cleanly
        u5, r5 = radiant_missions.resolve_mission_outcome(m, objective_done=False, elapsed_s=m.deadline_s + 10.0)
        self.assertEqual(u5.state, "expired_with_consequence")
        self.assertTrue(r5["terminal"])

        # Escort charge killed -> failed_with_consequence frees slot cleanly
        escort_m = radiant_missions.RadiantMission(**{**m.__dict__, "request_type": "escort_or_deliver"})
        u6, r6 = radiant_missions.resolve_mission_outcome(escort_m, objective_done=False, escort_alive=False)
        self.assertEqual(u6.state, "failed_with_consequence")
        self.assertEqual(r6["reason"], "escort_charge_died")

    def test_active_cap_and_papyrus_array_save_reload_roundtrip(self) -> None:
        cfg = schema.load_preset("fo4sf_commonwealth")
        snap = radiant_missions.snapshot_from_simulation(cfg, ticks=600, seed=5)
        batch = radiant_missions.generate_missions_from_world_state(snap, max_missions=4, seed=5)
        board = radiant_missions.MissionBoardState(max_active=3)
        for m in batch[:3]:
            board.accept(m)
        with self.assertRaises(ValueError):
            board.accept(batch[3])

        arrays = board.to_papyrus_arrays()
        for vals in arrays.values():
            self.assertLessEqual(len(vals), radiant_missions.PAPYRUS_ARRAY_LIMIT)

        restored = radiant_missions.MissionBoardState.from_papyrus_arrays(arrays, snap)
        self.assertEqual(len(restored.active_missions()), 3)
        for orig, rest in zip(board.active_missions(), restored.active_missions()):
            self.assertEqual(orig.mission_id, rest.mission_id)
            self.assertEqual(orig.request_type, rest.request_type)
            self.assertEqual(orig.giver_node_index, rest.giver_node_index)
            self.assertEqual(orig.target_node_index, rest.target_node_index)
            self.assertEqual(orig.reward_caps, rest.reward_caps)

        # Resolving one slot frees capacity for the 4th mission
        receipt = restored.resolve_slot(0, objective_done=True, giver_alive=False, deputy_alive=True)
        self.assertTrue(receipt["terminal"])
        self.assertEqual(len(restored.active_missions()), 2)
        slot = restored.accept(batch[3])
        self.assertEqual(slot, 0)

    def test_cross_os_path_basename_and_cli_scrubbing_under_posix_and_windows(self) -> None:
        win_drive = "D" + ":"
        c_drive = "C" + ":"
        cases = [
            (win_drive + "\\Games\\Configs\\fo4sf_commonwealth.json", "fo4sf_commonwealth.json"),
            ("/opt/alife/configs/fo4sf_commonwealth.json", "fo4sf_commonwealth.json"),
            (win_drive + "\\Games/Mixed\\Subdir/custom_world.json\\", "custom_world.json"),
            ("\\\\server\\share\\configs\\warfare.json", "warfare.json"),
            (win_drive + "\\", ""),
            (c_drive + "warfare.json", "warfare.json"),
            ("\\\\server\\share\\", ""),
        ]
        with mock.patch("os.path.basename", side_effect=posixpath.basename):
            for raw, expected in cases:
                self.assertEqual(radiant_missions.cross_os_basename(raw), expected)

        cfg = schema.load_preset("fo4sf_commonwealth")
        summary = radiant_missions.run_multi_seed_verification(cfg, num_seeds=20, ticks=300, max_per_seed=2)
        report = demo_radiant_missions.format_report(summary, win_drive + "\\Private\\Configs\\fo4sf_commonwealth.json")
        self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", report))
        self.assertIn("fo4sf_commonwealth.json", report)
        root_report = demo_radiant_missions.format_report(summary, win_drive + "\\")
        self.assertIsNone(re.search(r"\b[A-Za-z]:", root_report))
        self.assertIn("<config>", root_report)

    def test_design_doc_hygiene_and_required_banners(self) -> None:
        doc_path = os.path.join(REPO_ROOT, "docs", "quests", "radiant-missions.md")
        if not os.path.exists(doc_path):
            return
        with open(doc_path, encoding="utf-8") as f:
            text = f.read()
        first_line = text.splitlines()[0]
        self.assertIn("Titles:", first_line)
        self.assertIn("Modes:", first_line)
        self.assertIn("Track:", first_line)
        self.assertIn("prototype, offline", first_line)
        self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", text))
        self.assertIn("## Questions for the Owner", text)


if __name__ == "__main__":
    unittest.main()
