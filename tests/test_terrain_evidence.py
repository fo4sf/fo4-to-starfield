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

    def test_one_sample_repeated_is_not_settled(self):
        same = ["10 -4 105.14", "10 -4 105.14"]
        self.assertEqual(oracle.judge(bundle(frames=same))[0], "UNREAD")
        nudged = ["10 -4 105.14", "10.0000001 -4 105.14"]
        self.assertEqual(oracle.judge(bundle(frames=nudged))[0], "UNREAD")

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
