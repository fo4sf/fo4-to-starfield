"""Synthetic runtime-planning fixtures; no game files or live input."""
import copy
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock


spec = importlib.util.spec_from_file_location("campaign", Path(__file__).resolve().parents[1] /
                                           "scripts/testing/commonwealth_campaign.py")
campaign = importlib.util.module_from_spec(spec)
spec.loader.exec_module(campaign)


def test_entry(index, labels):
    entry = {"id": f"{index}_terrain", "kind": "terrain", "world_coc": "FO4Core_RedRocketSpawn",
            "model": "synthetic", "spawn_local": [0, 0, 10], "z_ref": "ground", "fresh": True,
            "drop_z": 180.0, "settle_ms": 10000, "hop_m": 200, "hop_wait_ms": 7000,
            "points": [{"label": label, "x": i * 10, "y": i * 10, "expect": 10 + i}
                       for i, label in enumerate(labels)], "beyond": {"x": 1000, "y": 0}}
    for i, p in enumerate(entry["points"]):
        if p["label"].endswith("_again"):
            p.update({k: entry["points"][i - 1][k] for k in ("x", "y", "expect")})
    return entry


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.exp, self.staging, self.runner = [root / n for n in ("exterior", "interior", "runner")]
        for p in (self.exp / "Data", self.staging, self.runner / "scripts/game", root / "source"):
            p.mkdir(parents=True)
        for name in campaign.PLUGINS:
            (self.exp / name).write_bytes(b"synthetic plugin")
        (self.exp / "Data/fixture.mesh").write_bytes(b"abcd")
        for name in ("FO4Port.esm", "FO4Port - Main.ba2", "FO4Port - Textures.ba2"):
            (self.staging / name).write_bytes(b"synthetic interior")
        for name in ("formids.json", "manifest.json"):
            campaign.write(self.staging / name, {"synthetic": True})
        (self.runner / "scripts/game/testqueue.py").write_text("# synthetic runner\n")
        self.entries = [test_entry(0, ["ground", "wp_01", "w_200m", "farther"]),
                        test_entry(1, ["ground", "wp_01", "sanctuary_house_roof", "sanctuary_house_roof_again",
                                       "redrocket_roof", "redrocket_roof_again", "concord_museum_roof",
                                       "concord_museum_roof_again"]),
                        test_entry(2, ["ground", "obstructed"])]
        self.source = {"experiment": str(self.exp), "staging": str(self.staging), "tests": self.entries,
                       "plugin_sha256": campaign.digest(self.staging / "FO4Port.esm"), "build_id": "fixture",
                       "commit": "source_commit", "needs": ["light"], "hours": [[0, 24]],
                       "pre_launch": ["fixture-install", "--needs", "light"]}
        self.queue = root / "source/queue.json"
        self.out = root / "prepared"
        campaign.write(self.queue, self.source)
        for name in campaign.METADATA:
            campaign.write(self.exp / name, {"synthetic": True})
        plan = [dict(t, coc=t["world_coc"]) for t in self.entries]
        campaign.write(self.exp / "plan.json", plan)
        campaign.write(self.exp / "expected.json", {"objects": {"placed": 3}})
        campaign.write(self.exp / "objects.json", {"bases": [{"collision": "guessed-boxes"}],
                                                 "refs": [{"cell": c, "base": 0} for c in
                                                          [[-1, 0], [0, 0], [16, 0]]]})
        campaign.write(self.exp / "offline_check.json", {"pass": True, "checks": [["synthetic", True]],
                                                       "cells": {"with_refs": 3}})
        self.refresh_manifest()
        patch = mock.patch.object(campaign.subprocess, "run", return_value=SimpleNamespace(stdout="runner_commit\n"))
        patch.start()
        self.addCleanup(patch.stop)

    def refresh_manifest(self):
        files = [self.exp / n for n in campaign.PLUGINS] + campaign.tree_files(self.exp / "Data")
        campaign.write(self.exp / "data_manifest.json",
                       {"pass": True, "files": {p.relative_to(self.exp).as_posix(): campaign.stat_id(p) for p in files}})

    def prepare(self):
        return campaign.prepare(self.queue, self.runner, self.out)

    def test_prepare_preserves_provenance_payload_and_existing_source(self):
        original = self.queue.read_bytes()
        m = self.prepare()
        self.assertFalse(m["runtime_accepted"])
        self.assertEqual(m["runner_commit"], "runner_commit")
        self.assertEqual(m["source_queue_commit"], "source_commit")
        self.assertEqual(m["coverage"]["placed_refs"], 3)
        self.assertEqual(len(m["regional_selection"]["regions"]), 3)
        for name, selected, _purpose, gate in campaign.PHASES:
            q = campaign.load(self.out / name / "queue.json")
            self.assertEqual({k: v for k, v in q.items() if k != "tests"},
                             {k: v for k, v in self.source.items() if k != "tests"})
            self.assertEqual(m["phases"][name]["acceptance_gate"], gate)
            for t, (index, count) in zip(q["tests"], selected):
                expected = copy.deepcopy(self.entries[index])
                expected["points"] = expected["points"][:count] if count else expected["points"]
                expected["id"] = f"{name}_{expected['id']}"
                p = expected["points"][-1]
                expected["beyond"] = {"x": p["x"], "y": p["y"]}
                self.assertEqual(t, expected)
                campaign.validate_route(t)
        self.assertEqual(self.queue.read_bytes(), original)
        self.assertEqual(campaign.verify(self.out), m)

    def test_original_unjudged_final_jump_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "move over 200m"):
            campaign.validate_route(self.entries[0])

    def test_automatic_hops_and_initial_jump_cannot_hide_unsafe_setup(self):
        t = copy.deepcopy(self.entries[0])
        t["beyond"] = {"x": 30, "y": 30}
        t["points"][1].update(x=150, y=150)
        with self.assertRaisesRegex(ValueError, "automatic hop"):
            campaign.validate_route(t)
        t = copy.deepcopy(self.entries[0])
        t["beyond"] = {"x": 30, "y": 30}
        t["spawn_local"] = [1000, 0, 10]
        with self.assertRaisesRegex(ValueError, "move over 200m"):
            campaign.validate_route(t)

    def test_nonfinite_points_and_duplicate_labels_refused(self):
        for update in ({"expect": float("nan")}, {"label": "ground"}):
            t = copy.deepcopy(self.entries[0])
            t["points"][1].update(update)
            with self.assertRaisesRegex(ValueError, "finite"):
                campaign.validate_route(t)

    def test_failed_or_stale_exterior_check_refused_before_writing(self):
        campaign.write(self.exp / "offline_check.json", {"pass": True, "checks": [["synthetic", False]]})
        with self.assertRaisesRegex(ValueError, "check is missing or failed"):
            self.prepare()
        self.assertFalse(self.out.exists())
        campaign.write(self.exp / "offline_check.json", {"pass": True, "checks": [["synthetic", True]]})
        (self.exp / "Data/fixture.mesh").write_bytes(b"longer")
        with self.assertRaisesRegex(ValueError, "not the tree"):
            self.prepare()

    def test_changed_same_size_restored_mtime_data_or_archive_detected(self):
        self.prepare()
        for path in (self.exp / "Data/fixture.mesh", self.staging / "FO4Port - Textures.ba2"):
            original, st = path.read_bytes(), path.stat()
            path.write_bytes(b"z" * len(original))
            os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
            with self.assertRaisesRegex(ValueError, "contents changed"):
                campaign.verify(self.out)
            path.write_bytes(original)
            os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
        campaign.verify(self.out)

    def test_changed_phase_cannot_be_reauthorized_by_editing_hash(self):
        self.prepare()
        name = campaign.PHASES[0][0]
        p = self.out / name / "queue.json"
        q = campaign.load(p)
        q["tests"][0]["points"][0]["expect"] += 1
        campaign.write(p, q)
        m = campaign.load(self.out / "campaign.json")
        m["phases"][name]["queue_sha256"] = campaign.digest(p)
        campaign.write(self.out / "campaign.json", m)
        with self.assertRaisesRegex(ValueError, "phase queue changed"):
            campaign.verify(self.out)

    def test_data_inventory_addition_and_removal_refused(self):
        self.prepare()
        p = self.exp / "Data/extra.mesh"
        p.write_bytes(b"synthetic")
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            campaign.verify(self.out)
        p.unlink()
        (self.exp / "Data/fixture.mesh").unlink()
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            campaign.verify(self.out)

    def test_existing_output_and_source_build_mismatch_refused(self):
        self.prepare()
        before = (self.out / "campaign.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.prepare()
        self.assertEqual(before, (self.out / "campaign.json").read_bytes())
        self.out = self.out.parent / "second"
        (self.staging / "FO4Port.esm").write_bytes(b"different")
        with self.assertRaisesRegex(ValueError, "build pin"):
            self.prepare()
        self.assertFalse(self.out.exists())

    def test_output_inside_inputs_and_stale_plan_refused(self):
        self.out = self.exp / "prepared"
        with self.assertRaisesRegex(ValueError, "separate"):
            self.prepare()
        self.out = self.exp.parent / "prepared"
        plan = campaign.load(self.exp / "plan.json")
        plan[0]["points"][0]["expect"] += 1
        campaign.write(self.exp / "plan.json", plan)
        with self.assertRaisesRegex(ValueError, "differs from the staged"):
            self.prepare()

    def test_unsafe_manifest_paths_refused(self):
        for name in ("../escape", "/absolute", "C:/absolute", "Data\\windows"):
            with self.assertRaises(ValueError):
                campaign.relative_file(self.exp, name)

    def test_region_candidates_preserve_negative_cells_and_risk_counts(self):
        objects = {"bases": [{"collision": "fo4-native"}, {"collision": "rigged-door-box"}],
                   "refs": [{"cell": c, "base": b} for c, b in
                            [([-1, 0], 1), ([-1, 0], 1), ([-16, 1], 0), ([0, 0], 0)]]}
        r = campaign.regional_targets(objects, {"objects": {"placed": 4}}, {"cells": {"with_refs": 3}})
        self.assertEqual([x["region"] for x in r["regions"]], [[-1, 0], [0, 0]])
        self.assertEqual(r["densest_cells"][0], {"cell": [-1, 0], "refs": 2})
        candidates = r["regions"][0]["candidates"]
        risk = next(c for c in candidates if c["cell"] == [-1, 0])
        self.assertEqual(risk["risk_refs"], 2)
        self.assertIn("collision-risk", risk["reasons"])
        self.assertTrue(r["status"].startswith("blocked"))
        with self.assertRaisesRegex(ValueError, "differs"):
            campaign.regional_targets(objects, {"objects": {"placed": 5}}, {"cells": {"with_refs": 3}})

    def test_runner_revision_and_regional_claim_edits_refused(self):
        self.prepare()
        with mock.patch.object(campaign.subprocess, "run", return_value=SimpleNamespace(stdout="new_commit\n")):
            with self.assertRaisesRegex(ValueError, "runner revision changed"):
                campaign.verify(self.out)
        m = campaign.load(self.out / "campaign.json")
        m["regional_selection"]["populated_cells"] += 1
        campaign.write(self.out / "campaign.json", m)
        with self.assertRaisesRegex(ValueError, "regional selection changed"):
            campaign.verify(self.out)

    def test_parsed_plan_mutated_before_snapshot_is_refused(self):
        real_load = campaign.load_pinned

        def mutate_plan(path):
            parsed = real_load(path)
            if path == self.exp / "plan.json":
                changed = copy.deepcopy(parsed[0])
                changed[0]["points"][0]["expect"] = 999
                campaign.write(path, changed)
            return parsed

        with mock.patch.object(campaign, "load_pinned", side_effect=mutate_plan):
            with self.assertRaisesRegex(ValueError, "parsed metadata changed"):
                self.prepare()
        self.assertFalse(self.out.exists())

    def test_reordered_smoke_and_unobserved_wide_scope_are_refused(self):
        q = copy.deepcopy(self.source)
        pts = q["tests"][1]["points"]
        pts[2:6] = pts[4:6] + pts[2:4]
        with self.assertRaisesRegex(ValueError, "smoke prefix"):
            campaign.phase_queues(q)
        q = copy.deepcopy(self.source)
        q["tests"][0]["points"][-1]["x"] = 1000
        with self.assertRaisesRegex(ValueError, "510m"):
            campaign.phase_queues(q)

    def test_informational_gate_cannot_be_changed_to_acceptance(self):
        self.prepare()
        m = campaign.load(self.out / "campaign.json")
        m["phases"]["03-informational"]["acceptance_gate"] = True
        campaign.write(self.out / "campaign.json", m)
        with self.assertRaisesRegex(ValueError, "purpose/gate/estimate changed"):
            campaign.verify(self.out)


if __name__ == "__main__":
    unittest.main()
