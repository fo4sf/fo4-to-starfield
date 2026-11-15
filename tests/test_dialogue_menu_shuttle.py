"""scripts/dialogue/dialogue_menu_shuttle.py: shuttle bind contract. No game files."""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "dialogue"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ui"))
import dialogue_menu_host as host  # noqa: E402
import dialogue_menu_shuttle as shuttle  # noqa: E402
import make_dialogue_wheel_swf as wheel  # noqa: E402


class ShuttleBindTest(unittest.TestCase):
    def test_payload_marks_fields_unread(self):
        payload = shuttle.check(shuttle.shuttle_bind())
        self.assertTrue(payload["payload_unread"])
        self.assertEqual(payload["payload_fields"], [])
        self.assertTrue(payload["abc_required"])
        self.assertEqual(payload["map_rows"], 4)
        self.assertEqual(payload["keep_shuttle"], list(host.KEEP_SHUTTLE))
        self.assertEqual(payload["host_list"], "DialogueList_mc")
        self.assertTrue(payload["fo4_slots_are_not_the_bind"])

    def test_refuses_invented_payload_fields(self):
        payload = shuttle.shuttle_bind()
        payload["payload_fields"] = ["entryList"]
        payload["payload_unread"] = False
        with self.assertRaisesRegex(shuttle.ShuttleError, "UNREAD"):
            shuttle.check(payload)

    def test_refuses_dropping_abc_required(self):
        payload = shuttle.shuttle_bind()
        payload["abc_required"] = False
        with self.assertRaisesRegex(shuttle.ShuttleError, "DoABC"):
            shuttle.check(payload)

    def test_current_wheel_has_no_doabc(self):
        data = wheel.movie_bytes()
        self.assertFalse(shuttle.has_doabc(data))
        self.assertIn("DoABC", shuttle.refuse_install_reason(data))

    def test_as3_source_names_shuttle_not_fo4_clips(self):
        path = os.path.join(ROOT, "scripts", "ui", "DialogueMenuFour.as")
        with open(path, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("BSUIDataManager", src)
        self.assertIn("UIDataShuttleConnector", src)
        self.assertIn("DialogueList_mc", src)
        self.assertIn("DialogueMenu_OnDialogueSelect", src)
        self.assertIn("UNREAD", src)
        self.assertNotIn("Question", src)
        self.assertNotIn("BGSCodeObj", src)


class WheelBytesNoAbc(unittest.TestCase):
    def test_refuse_via_temp_file(self):
        with tempfile.NamedTemporaryFile(suffix=".swf", delete=False) as f:
            path = f.name
            f.write(wheel.movie_bytes())
        try:
            reason = shuttle.refuse_install_reason(path)
        finally:
            os.unlink(path)
        self.assertIsNotNone(reason)
        self.assertIn("killed", reason)


if __name__ == "__main__":
    unittest.main()
