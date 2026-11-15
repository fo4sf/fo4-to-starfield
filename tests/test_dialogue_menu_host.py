"""scripts/dialogue/dialogue_menu_host.py: PC PARTIAL names (FAL-865). No game files."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "dialogue"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ui"))
import dialogue_menu_host as host  # noqa: E402
import make_dialogue_wheel_swf as wheel  # noqa: E402


class HostNamesTest(unittest.TestCase):
    def test_payload_kills_no_as3_named_clips(self):
        payload = host.check(host.host_names())
        self.assertFalse(payload["host_fills_by_name"])
        self.assertFalse(payload["standin_matches_host"])
        self.assertFalse(payload["standin_matches_fo4"])
        self.assertTrue(payload["kill_no_as3_named_clips"])
        self.assertEqual(payload["quest_scenes"], 8)
        self.assertEqual(payload["host_list"], "DialogueList_mc")
        self.assertEqual(payload["fo4_slots"], ["Question", "Neutral", "Negative", "Positive"])

    def test_standin_slots_are_not_host_or_fo4(self):
        self.assertEqual(list(wheel.SLOT_NAMES), list(host.STANDIN_SLOTS))
        self.assertFalse(set(host.STANDIN_SLOTS) & set(host.HOST_CHILDREN))
        self.assertFalse(set(host.STANDIN_SLOTS) & set(host.FO4_SLOTS))

    def test_refuses_claiming_host_fills_by_name(self):
        payload = host.host_names()
        payload["host_fills_by_name"] = True
        with self.assertRaisesRegex(host.HostMenuError, "shuttle"):
            host.check(payload)

    def test_refuses_mixing_fo4_slot_names_into_standin(self):
        payload = host.host_names()
        payload["standin_slots"] = list(host.FO4_SLOTS)
        with self.assertRaisesRegex(host.HostMenuError, "Fallout 4"):
            host.check(payload)


if __name__ == "__main__":
    unittest.main()
