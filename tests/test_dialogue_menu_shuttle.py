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
    def test_payload_uses_pc_pass_names(self):
        payload = shuttle.check(shuttle.shuttle_bind())
        self.assertFalse(payload["payload_unread"])
        self.assertEqual(
            payload["payload_fields"],
            ["DialogueListData", "aChoices", "sChoiceText", "uEntryID", "selectedIndex"],
        )
        self.assertEqual(payload["list_provider"], "DialogueListData")
        self.assertEqual(payload["choices"], "aChoices")
        self.assertEqual(payload["choice_text"], "sChoiceText")
        self.assertEqual(payload["entry_id"], "uEntryID")
        self.assertEqual(payload["select_event"], "DialogueMenu_OnDialogueSelect")
        self.assertEqual(payload["select_key"], "selectedIndex")
        self.assertTrue(payload["no_row_index_field"])
        self.assertFalse(payload["compiled_movie"])
        self.assertTrue(payload["abc_required"])
        self.assertEqual(payload["map_rows"], 4)
        self.assertEqual(payload["keep_shuttle"], list(host.KEEP_SHUTTLE))
        self.assertEqual(payload["host_list"], "DialogueList_mc")
        self.assertEqual(payload["providers"][0], "DialogueListData")
        self.assertTrue(payload["fo4_slots_are_not_the_bind"])

    def test_refuses_invented_payload_fields(self):
        payload = shuttle.shuttle_bind()
        payload["payload_fields"] = ["entryList"]
        with self.assertRaisesRegex(shuttle.ShuttleError, "payload fields"):
            shuttle.check(payload)

    def test_refuses_marking_unread_after_pass(self):
        payload = shuttle.shuttle_bind()
        payload["payload_unread"] = True
        with self.assertRaisesRegex(shuttle.ShuttleError, "FAL-879"):
            shuttle.check(payload)

    def test_refuses_claiming_compiled_movie(self):
        payload = shuttle.shuttle_bind()
        payload["compiled_movie"] = True
        with self.assertRaisesRegex(shuttle.ShuttleError, "compiled"):
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

    def test_as3_source_names_pc_fields_not_fo4_clips(self):
        path = os.path.join(ROOT, "scripts", "ui", "DialogueMenuFour.as")
        with open(path, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("BSUIDataManager", src)
        self.assertIn("UIDataShuttleConnector", src)
        self.assertIn("DialogueListData", src)
        self.assertIn("aChoices", src)
        self.assertIn("sChoiceText", src)
        self.assertIn("uEntryID", src)
        self.assertIn("DialogueMenu_OnDialogueSelect", src)
        self.assertIn("selectedIndex", src)
        self.assertNotIn("UNREAD", src)
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
