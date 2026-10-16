"""The terrain "activate" block: a runner feature, and its summary in the verdict detail (shown, never judged)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import runner_features  # noqa: E402
import testqueue  # noqa: E402

import json
import tempfile

TEST = {"kind": "terrain", "activate": {"ref": "020A2AA5", "base": "020A2AA4", "expect": ["First Aid Kit", "Credits", "Digipick"]}}
PLAN = {"coc": "FO4Core_RedRocketSpawn", "travel": "coc FO4Core_RedRocketSpawn", "label": "r05", "spawn_local": [-989.26, 1146.51, 105.26],
        "settle_ms": 8000, "z_ref": "kit_south", "drop_z": 40.0, "points": [{"label": "kit_south", "x": -993.1, "y": 1148.6, "expect": 105.26}],
        "activate": TEST["activate"], "teleport_console": True}


class ActivateStepTests(unittest.TestCase):
    def test_activate_is_a_runner_feature(self):
        self.assertIn("activate", runner_features.FEATURES)
        self.assertIn("activate", runner_features.needs([TEST]))
        self.assertNotIn("activate", runner_features.needs([{"kind": "terrain"}]))

    def test_plan_terrain_carries_the_block(self):
        import inspect
        body = inspect.getsource(testqueue.plan_terrain)
        self.assertIn('"activate"', body)
        self.assertIn('"teleport_console"', body)

    def test_summary_lists_the_words_read(self):
        obs = {"activate": {"ref": "020A2AA5", "shot": "activate.png", "ocr": "FIRST AID KIT\nCredits 25\nDigipick 1"}}
        self.assertEqual(testqueue.activate_summary(TEST, obs),
                         "[activate 020A2AA5: read ['First Aid Kit', 'Credits', 'Digipick'] of ['First Aid Kit', 'Credits', 'Digipick']]")
        obs["activate"]["ocr"] = "MARS\nHEALTH 2/75"
        self.assertEqual(testqueue.activate_summary(TEST, obs),
                         "[activate 020A2AA5: read [] of ['First Aid Kit', 'Credits', 'Digipick']]")

    def test_unproven_selection_activates_nothing(self):
        obs = {"activate": {"ref": "020A2AA5", "base": "020A2AA4", "selected": False, "sel_ocr": "prid 020A2AA5\nItem not found"}}
        self.assertEqual(testqueue.activate_summary(TEST, obs),
                         "[activate 020A2AA5: selection not confirmed (GetIsID 020A2AA4 did not reply 1); nothing activated]")

    def test_planner_carries_and_validates_the_block(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "exp")); os.makedirs(os.path.join(d, "staging"))
            open(os.path.join(d, "staging", "FO4Port.esm"), "wb").write(b"TES4")
            open(os.path.join(d, "exp", "plan.json"), "w").write(json.dumps([PLAN]))
            args = type("A", (), dict(staging=os.path.join(d, "staging"), exp_dir=os.path.join(d, "exp"), out=os.path.join(d, "q"),
                                      plugin_index="02", launch_cell="Vault111Cryo", only=0, plugins="", starfield="", fresh=True))()
            testqueue.plan_terrain(args)
            q = json.load(open(os.path.join(d, "q", "queue.json")))
            self.assertEqual(q["tests"][0]["activate"], TEST["activate"])
            self.assertIs(q["tests"][0]["teleport_console"], True)
            self.assertIn("activate", q["needs"])
            bad = dict(PLAN, activate={"ref": "020A2AA5", "expect": ["x"]})          # no base: nothing to prove the selection with
            open(os.path.join(d, "exp", "plan.json"), "w").write(json.dumps([bad]))
            with self.assertRaises(SystemExit):
                testqueue.plan_terrain(args)

    def test_no_capture_and_no_block(self):
        self.assertEqual(testqueue.activate_summary(TEST, {"activate": {"ref": "020A2AA5", "shot": None}}),
                         "[activate 020A2AA5: no capture]")
        self.assertEqual(testqueue.activate_summary(TEST, {}), "")
        self.assertEqual(testqueue.activate_summary({"kind": "terrain"}, {"activate": {"shot": "x"}}), "")


if __name__ == "__main__":
    unittest.main()
