"""The terrain "activate" block: a runner feature, and its summary in the verdict detail (shown, never judged)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import runner_features  # noqa: E402
import testqueue  # noqa: E402

TEST = {"kind": "terrain", "activate": {"ref": "020A2AA5", "expect": ["First Aid Kit", "Credits", "Digipick"]}}


class ActivateStepTests(unittest.TestCase):
    def test_activate_is_a_runner_feature(self):
        self.assertIn("activate", runner_features.FEATURES)
        self.assertIn("activate", runner_features.needs([TEST]))
        self.assertNotIn("activate", runner_features.needs([{"kind": "terrain"}]))

    def test_summary_lists_the_words_read(self):
        obs = {"activate": {"ref": "020A2AA5", "shot": "activate.png", "ocr": "FIRST AID KIT\nCredits 25\nDigipick 1"}}
        self.assertEqual(testqueue.activate_summary(TEST, obs),
                         "[activate 020A2AA5: read ['First Aid Kit', 'Credits', 'Digipick'] of ['First Aid Kit', 'Credits', 'Digipick']]")
        obs["activate"]["ocr"] = "MARS\nHEALTH 2/75"
        self.assertEqual(testqueue.activate_summary(TEST, obs),
                         "[activate 020A2AA5: read [] of ['First Aid Kit', 'Credits', 'Digipick']]")

    def test_no_capture_and_no_block(self):
        self.assertEqual(testqueue.activate_summary(TEST, {"activate": {"ref": "020A2AA5", "shot": None}}),
                         "[activate 020A2AA5: no capture]")
        self.assertEqual(testqueue.activate_summary(TEST, {}), "")
        self.assertEqual(testqueue.activate_summary({"kind": "terrain"}, {"activate": {"shot": "x"}}), "")


if __name__ == "__main__":
    unittest.main()
