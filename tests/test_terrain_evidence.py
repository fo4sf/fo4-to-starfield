import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "terrain_evidence", Path(__file__).resolve().parents[1] / "scripts" / "game" / "terrain_evidence.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)

PIN = "a" * 64
OTHER = "b" * 64


def bundle(**over):
    evidence = {
        "pinned": {"plan_sha256": PIN, "plugin_sha256": PIN, "archive_sha256": PIN},
        "identity": {"plan_sha256": PIN, "plugin_sha256": PIN, "archive_sha256": PIN},
        "ground": "plugin",
        "point": {"label": "origin", "x": 10.0, "y": -4.0, "expect": 105.14},
        "offset": [0.0, 0.0, 0.0],
        "require_offset": True,
        "frames": ["10.02 -4.01 105.13", "10.01 -3.99 105.14"],
    }
    evidence.update(over)
    return evidence


class TerrainEvidenceTests(unittest.TestCase):
    def test_two_settled_frames_on_the_pinned_plugin_pass(self):
        self.assertEqual(oracle.judge(bundle())[0], "PASS")

    def test_missing_identity_procedural_ground_and_one_frame_do_not_pass(self):
        self.assertEqual(oracle.judge(bundle(identity={}))[0], "UNREAD")
        self.assertEqual(oracle.judge(bundle(ground="procedural"))[0], "UNREAD")
        self.assertEqual(oracle.judge(bundle(ground=None))[0], "UNREAD")
        self.assertEqual(oracle.judge(bundle(frames=["10  -4  105.14"]))[0], "UNREAD")
        moved = dict(bundle())
        moved["identity"] = dict(moved["identity"], archive_sha256=OTHER)
        self.assertEqual(oracle.judge(moved)[0], "UNREAD")
        self.assertEqual(oracle.judge(bundle(offset=None))[0], "UNREAD")

    def test_a_far_landing_and_a_falling_z_are_not_a_height_pass(self):
        # 142 m from the point: the reading never happened, so it is not FAIL and not PASS.
        far = ["152 -4 105.14", "152.1 -4 105.14"]
        self.assertEqual(oracle.judge(bundle(frames=far))[0], "UNREAD")
        falling = ["10 -4 140.0", "10 -4 120.0"]
        self.assertEqual(oracle.judge(bundle(frames=falling))[0], "UNREAD")

    def test_settled_wrong_height_fails(self):
        wrong = ["10 -4 90.0", "10.01 -4 90.02"]
        self.assertEqual(oracle.judge(bundle(frames=wrong))[0], "FAIL")

    def test_overlay_offset_is_applied_before_the_height_check(self):
        # The player is read in the merged world; expected height stays in the plan frame.
        shifted = bundle(offset=[3000.0, -3500.0, 0.01],
                         frames=["3010.0 -3504.0 105.15", "3010.02 -3504.01 105.14"])
        self.assertEqual(oracle.judge(shifted)[0], "PASS")

    def test_a_present_bad_offset_is_not_zero(self):
        # QA on #69: require_offset false used to turn a bad offset into 0,0,0 and PASS.
        self.assertEqual(oracle.judge(bundle(require_offset=False, offset="bad"))[0], "UNREAD")
        self.assertEqual(oracle.judge(bundle(require_offset=False, offset=None))[0], "UNREAD")
        self.assertEqual(oracle.judge(bundle(require_offset=False, offset=[float("nan"), 0, 0]))[0], "UNREAD")
        omitted = bundle(require_offset=False)
        del omitted["offset"]
        self.assertEqual(oracle.judge(omitted)[0], "PASS")

    def test_nonfinite_tolerances_cannot_pass(self):
        wrong = ["10 -4 90.0", "10.01 -4 90.02"]
        self.assertEqual(oracle.judge(bundle(frames=wrong))[0], "FAIL")
        self.assertEqual(oracle.judge(bundle(frames=wrong), tol_m=float("nan"))[0], "UNREAD")
        far = ["152 -4 105.14", "152.1 -4 105.14"]
        self.assertEqual(oracle.judge(bundle(frames=far), reach_m=float("nan"))[0], "UNREAD")
        drift = ["10 -4 105.14", "10 -4 125.14"]
        self.assertEqual(oracle.judge(bundle(frames=drift), settle_m=float("nan"))[0], "UNREAD")
        self.assertEqual(oracle.judge(bundle(), tol_m=-0.1)[0], "UNREAD")
        self.assertEqual(oracle.judge(bundle(), reach_m=True)[0], "UNREAD")

    def test_identical_stationary_captures_are_allowed(self):
        # Independent readings of a settled player may be identical. Coordinates alone
        # do not prove reuse; provenance belongs to capture ids or timestamps.
        same = ["10 -4 105.14", "10 -4 105.14"]
        self.assertEqual(oracle.judge(bundle(frames=same))[0], "PASS")
        nudged = ["10 -4 105.14", "10.0000001 -4 105.14"]
        self.assertEqual(oracle.judge(bundle(frames=nudged))[0], "PASS")

    def test_reused_capture_identifier_is_unread(self):
        # When identifiers are present, a duplicate id is reuse, not an independent sample.
        frames = [
            {"pos": "10 -4 105.14", "id": "cap-1"},
            {"pos": "10.01 -4 105.14", "id": "cap-1"},
        ]
        self.assertEqual(oracle.judge(bundle(frames=frames))[0], "UNREAD")
        distinct = [
            {"pos": "10 -4 105.14", "id": "cap-1"},
            {"pos": "10.01 -4 105.14", "id": "cap-2"},
        ]
        self.assertEqual(oracle.judge(bundle(frames=distinct))[0], "PASS")

    def test_reused_capture_timestamp_is_unread(self):
        # Timestamps, when recorded, must also be unique for independent samples.
        frames = [
            {"pos": "10 -4 105.14", "time": 1.0},
            {"pos": "10.01 -4 105.14", "time": 1.0},
        ]
        self.assertEqual(oracle.judge(bundle(frames=frames))[0], "UNREAD")
        distinct = [
            {"pos": "10 -4 105.14", "timestamp": 1.0},
            {"pos": "10.01 -4 105.14", "timestamp": 2.0},
        ]
        self.assertEqual(oracle.judge(bundle(frames=distinct))[0], "PASS")
        # Mixed with id still works.
        mixed = [
            {"pos": "10 -4 105.14", "id": "a", "t": 10},
            {"pos": "10.01 -4 105.14", "id": "b", "t": 11},
        ]
        self.assertEqual(oracle.judge(bundle(frames=mixed))[0], "PASS")

    def test_recorded_bytes_must_hash_to_the_pin(self):
        import hashlib
        raw = b"plan-v1"
        digest = hashlib.sha256(raw).hexdigest()
        pinned = {"plan_sha256": digest, "plugin_sha256": digest, "archive_sha256": digest}
        good = {"plan": raw, "plugin": raw, "archive": raw}
        self.assertEqual(oracle.judge(bundle(pinned=pinned, identity=dict(pinned), bodies=good))[0], "PASS")
        bad = {"plan": b"other", "plugin": raw, "archive": raw}
        self.assertEqual(oracle.judge(bundle(pinned=pinned, identity=dict(pinned), bodies=bad))[0], "UNREAD")

    def test_a_probe_passes_only_when_every_planned_point_does(self):
        shared = bundle()
        evidence = {
            "pinned": shared["pinned"], "identity": shared["identity"], "ground": "plugin",
            "offset": [0.0, 0.0, 0.0], "require_offset": True,
            "points": [
                {"label": "origin", "x": 10.0, "y": -4.0, "expect": 105.14},
                {"label": "flat", "x": 12.0, "y": -4.0, "expect": 105.03},
            ],
            "reads": {
                "origin": ["10.02 -4.01 105.13", "10.01 -3.99 105.14"],
                "flat": ["12.01 -4.00 105.03", "12.00 -4.02 105.03"],
            },
        }
        self.assertEqual(oracle.judge_probe(evidence)[0], "PASS")
        dropped = dict(evidence, reads={"origin": evidence["reads"]["origin"]})
        self.assertEqual(oracle.judge_probe(dropped)[0], "UNREAD")
        wrong = dict(evidence, reads=dict(evidence["reads"], flat=["12 -4 90", "12.01 -4 90"]))
        self.assertEqual(oracle.judge_probe(wrong)[0], "FAIL")

    def test_zero_valued_provenance_is_preserved(self):
        # Zero is a valid value; key presence must not drop it.
        frames = [
            {"pos": "10 -4 105.14", "id": 0},
            {"pos": "10.01 -4 105.14", "id": 0},
        ]
        self.assertEqual(oracle.judge(bundle(frames=frames))[0], "UNREAD")
        frames_ts = [
            {"pos": "10 -4 105.14", "time": 0.0},
            {"pos": "10.01 -4 105.14", "time": 0.0},
        ]
        self.assertEqual(oracle.judge(bundle(frames=frames_ts))[0], "UNREAD")
        # Distinct zeros would not, but same zero is reuse.
        distinct = [
            {"pos": "10 -4 105.14", "id": 0},
            {"pos": "10.01 -4 105.14", "id": 1},
        ]
        self.assertEqual(oracle.judge(bundle(frames=distinct))[0], "PASS")

    def test_malformed_provenance_is_unread(self):
        # Non-scalar metadata must not crash; it is unreadable.
        frames = [
            {"pos": "10 -4 105.14", "id": ["a"]},
            {"pos": "10.01 -4 105.14", "id": "b"},
        ]
        self.assertEqual(oracle.judge(bundle(frames=frames))[0], "UNREAD")
        frames_ts = [
            {"pos": "10 -4 105.14", "timestamp": {"sec": 1}},
            {"pos": "10.01 -4 105.14", "timestamp": 2},
        ]
        self.assertEqual(oracle.judge(bundle(frames=frames_ts))[0], "UNREAD")

    def test_identifier_reuse_across_planned_points_is_unread(self):
        # The same capture IDs cannot count for two different planned points.
        evidence = {
            "pinned": {"plan_sha256": PIN, "plugin_sha256": PIN, "archive_sha256": PIN},
            "identity": {"plan_sha256": PIN, "plugin_sha256": PIN, "archive_sha256": PIN},
            "ground": "plugin",
            "points": [
                {"label": "one", "x": 10.0, "y": -4.0, "expect": 105.14},
                {"label": "two", "x": 11.0, "y": -4.0, "expect": 105.14},
            ],
            "reads": {
                "one": [
                    {"pos": "10 -4 105.14", "id": "a"},
                    {"pos": "10.01 -4 105.14", "id": "b"},
                ],
                "two": [
                    {"pos": "11 -4 105.14", "id": "a"},
                    {"pos": "11.01 -4 105.14", "id": "b"},
                ],
            },
        }
        verdict, _ = oracle.judge_probe(evidence)
        self.assertEqual(verdict, "UNREAD")
        # Independent IDs still pass.
        evidence["reads"]["two"] = [
            {"pos": "11 -4 105.14", "id": "c"},
            {"pos": "11.01 -4 105.14", "id": "d"},
        ]
        verdict, _ = oracle.judge_probe(evidence)
        self.assertEqual(verdict, "PASS")

    def test_null_primary_does_not_hide_alias(self):
        # QA on #69: id:None used to drop capture, and time:None used to drop timestamp.
        reused_id = [
            {"pos": "10 -4 105.14", "id": None, "capture": "reused"},
            {"pos": "10.01 -4 105.14", "id": None, "capture": "reused"},
        ]
        self.assertEqual(oracle.judge(bundle(frames=reused_id))[0], "UNREAD")
        reused_time = [
            {"pos": "10 -4 105.14", "time": None, "timestamp": 0},
            {"pos": "10.01 -4 105.14", "time": None, "timestamp": 0},
        ]
        self.assertEqual(oracle.judge(bundle(frames=reused_time))[0], "UNREAD")
        malformed_alias = [
            {"pos": "10 -4 105.14", "id": None, "capture": ["bad"]},
            {"pos": "10.01 -4 105.14", "id": "ok"},
        ]
        self.assertEqual(oracle.judge(bundle(frames=malformed_alias))[0], "UNREAD")
        distinct = [
            {"pos": "10 -4 105.14", "id": None, "capture": "a"},
            {"pos": "10.01 -4 105.14", "id": None, "capture": "b"},
        ]
        self.assertEqual(oracle.judge(bundle(frames=distinct))[0], "PASS")
        zero_then_one = [
            {"pos": "10 -4 105.14", "time": None, "timestamp": 0},
            {"pos": "10.01 -4 105.14", "time": None, "timestamp": 1},
        ]
        self.assertEqual(oracle.judge(bundle(frames=zero_then_one))[0], "PASS")
        conflict = [
            {"pos": "10 -4 105.14", "id": "a", "capture": "b"},
            {"pos": "10.01 -4 105.14", "id": "c"},
        ]
        self.assertEqual(oracle.judge(bundle(frames=conflict))[0], "UNREAD")
        # A null with no later alias is still "not recorded", so identical positions may pass.
        absent = [
            {"pos": "10 -4 105.14", "id": None},
            {"pos": "10.01 -4 105.14", "id": None},
        ]
        self.assertEqual(oracle.judge(bundle(frames=absent))[0], "PASS")

    def test_duplicate_and_malformed_plan_labels_are_unread(self):
        shared = bundle()
        base = {
            "pinned": shared["pinned"], "identity": shared["identity"], "ground": "plugin",
            "reads": {"one": ["10 -4 105.14", "10 -4 105.14"]},
        }
        duplicated = dict(base, points=[
            {"label": "one", "x": 10.0, "y": -4.0, "expect": 105.14},
            {"label": "one", "x": 11.0, "y": -4.0, "expect": 105.14},
        ])
        self.assertEqual(oracle.judge_probe(duplicated)[0], "UNREAD")
        listed = dict(base, points=[
            {"label": ["one"], "x": 10.0, "y": -4.0, "expect": 105.14},
        ])
        verdict, why = oracle.judge_probe(listed)
        self.assertEqual(verdict, "UNREAD")
        self.assertIn("label", why)
        empty = dict(base, points=[
            {"label": "", "x": 10.0, "y": -4.0, "expect": 105.14},
        ])
        self.assertEqual(oracle.judge_probe(empty)[0], "UNREAD")

    def test_position_aliases_follow_the_same_rules_as_id_and_time(self):
        # QA on #69: pos/xyz/position used the first truthy value and ignored the rest.
        disagree = [
            {"pos": "10 -4 105.14", "position": "900 900 9"},
            {"pos": "10.01 -4 105.14", "position": "900 900 9"},
        ]
        self.assertEqual(oracle.judge(bundle(frames=disagree))[0], "UNREAD")
        empty_primary = [
            {"pos": "", "xyz": "10 -4 105.14"},
            {"pos": "", "xyz": "10.01 -4 105.14"},
        ]
        self.assertEqual(oracle.judge(bundle(frames=empty_primary))[0], "UNREAD")
        fallthrough = [
            {"pos": None, "xyz": "10 -4 105.14"},
            {"pos": None, "position": "10.01 -4 105.14"},
        ]
        self.assertEqual(oracle.judge(bundle(frames=fallthrough))[0], "PASS")

    def test_overflowing_numbers_are_unread(self):
        huge = 10 ** 400
        frames = [[huge, -4, 105.14], [10.01, -4, 105.14]]
        self.assertEqual(oracle.judge(bundle(frames=frames))[0], "UNREAD")
        point = {"x": huge, "y": -4, "expect": 105.14}
        self.assertEqual(oracle.judge(bundle(point=point))[0], "UNREAD")
        self.assertEqual(oracle.judge(bundle(), reach_m=huge)[0], "UNREAD")

    def test_timestamps_must_be_strictly_increasing(self):
        # Numeric timestamps, when recorded, must increase so out-of-order samples cannot pass.
        decreasing = [
            {"pos": "10 -4 105.14", "time": 2.0},
            {"pos": "10.01 -4 105.14", "time": 1.0},
        ]
        self.assertEqual(oracle.judge(bundle(frames=decreasing))[0], "UNREAD")
        equal = [
            {"pos": "10 -4 105.14", "timestamp": 5},
            {"pos": "10.01 -4 105.14", "timestamp": 5},
        ]
        self.assertEqual(oracle.judge(bundle(frames=equal))[0], "UNREAD")
        increasing = [
            {"pos": "10 -4 105.14", "t": 1},
            {"pos": "10.01 -4 105.14", "t": 2},
        ]
        self.assertEqual(oracle.judge(bundle(frames=increasing))[0], "PASS")
        # Non-numeric timestamps keep uniqueness only (order is not defined).
        strings = [
            {"pos": "10 -4 105.14", "time": "later"},
            {"pos": "10.01 -4 105.14", "time": "earlier"},
        ]
        self.assertEqual(oracle.judge(bundle(frames=strings))[0], "PASS")
