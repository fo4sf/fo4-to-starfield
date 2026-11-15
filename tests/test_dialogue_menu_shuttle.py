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
        self.assertIn("onChoiceListUpdate", src)
        self.assertIn("selectSlot", src)
        self.assertIn("Subscribe", src)
        self.assertIn("sendSelect(ON_SELECT", src)
        self.assertIn("i >= MAP_ROWS", src)
        self.assertIn("getChildByName", src)
        self.assertIn(".text = value", src)
        self.assertIn("getDefinitionByName", src)
        self.assertIn("new TextField", src)
        self.assertIn("addChild", src)
        self.assertIn("MouseEvent.CLICK", src)
        self.assertNotIn("BSUIDataManager.Subscribe", src)
        self.assertNotIn("BSUIDataManager.Dispatch", src)
        self.assertIn("return null;", src)
        card = os.path.join(ROOT, "docs", "dialogue", "concord-talk-pc-card.md")
        with open(card, encoding="utf-8") as f:
            card_src = f.read()
        self.assertIn("-target-player=32.0", card_src)
        self.assertNotIn("-target-player=11.1", card_src)
        self.assertIn(
            "https://fpdownload.macromedia.com/get/flashplayer/updaters/32/playerglobal32_0.swc",
            card_src,
        )
        self.assertIn("frameworks/libs/player/32.0/playerglobal.swc", card_src)
        self.assertIn("PLAYERGLOBAL_HOME", card_src)
        self.assertIn("ensureHostRoots", src)
        self.assertIn("public dynamic class DialogueMenuFour", src)
        self.assertIn("this.name = HOST_ROOT", src)
        self.assertIn("Timeline-placed document root may refuse a name write", src)
        self.assertIn("this.Menu_mc = this", src)
        self.assertIn("this[n] = mc", src)
        self.assertNotIn("this.Menu_mc = root", src)
        self.assertNotIn("root.addChild(mc)", src)
        self.assertIn("public var Menu_mc", src)
        self.assertIn("public var DialogueList_mc", src)
        self.assertIn("Menu_mc", src)
        self.assertIn("DialogueList_mc", src)
        self.assertIn("any vanilla talk", card_src)
        self.assertIn("control then kit", card_src)
        self.assertIn("kit not installed", card_src)
        self.assertIn("Do not install 48a3eb3d or 69ee810a", card_src)
        self.assertIn("Keep the game's `DialogueMenu` movie", card_src)
        self.assertIn("Do not REPLACE `Interface/DialogueMenu.swf`", card_src)
        self.assertIn("Overlay load", card_src)
        self.assertIn("PARTIAL: four slots on any vanilla talk", card_src)
        self.assertNotIn("public function fillSlot(name:String, text:String):void {}", src)
        self.assertNotIn("public function sendSelect(eventName:String, payload:Object):void {}", src)

    def test_bind_slots_maps_four_choice_texts(self):
        data = {
            "aChoices": [
                {"sChoiceText": "ONE", "uEntryID": 10},
                {"sChoiceText": "TWO", "uEntryID": 20},
                {"sChoiceText": "THREE", "uEntryID": 30},
                {"sChoiceText": "FOUR", "uEntryID": 40},
                {"sChoiceText": "FIVE", "uEntryID": 50},
            ]
        }
        slots = shuttle.bind_slots(data)
        self.assertEqual([s["slot"] for s in slots], ["N", "E", "S", "W"])
        self.assertEqual([s["text"] for s in slots], ["ONE", "TWO", "THREE", "FOUR"])
        self.assertEqual([s["uEntryID"] for s in slots], [10, 20, 30, 40])

    def test_bind_slots_nested_data_and_short_list(self):
        slots = shuttle.bind_slots({"data": {"aChoices": [{"sChoiceText": "ONE", "uEntryID": 1}]}})
        self.assertEqual(slots[0]["text"], "ONE")
        self.assertEqual(slots[1]["text"], "")
        self.assertIsNone(slots[1]["uEntryID"])

    def test_bind_slots_outer_aChoices_wins_when_both_present(self):
        data = {
            "aChoices": [{"sChoiceText": "OUTER", "uEntryID": 1}],
            "data": {"aChoices": [{"sChoiceText": "INNER", "uEntryID": 2}]},
        }
        self.assertEqual(shuttle.bind_slots(data)[0]["text"], "OUTER")

    def test_select_payload_uses_uentryid_not_index(self):
        payload = shuttle.select_payload({"sChoiceText": "TWO", "uEntryID": 99})
        self.assertEqual(payload, {"DialogueMenu_OnDialogueSelect": {"selectedIndex": 99}})
        self.assertEqual(shuttle.select_payload({"uEntryID": 0})["DialogueMenu_OnDialogueSelect"]["selectedIndex"], 0)
        with self.assertRaisesRegex(shuttle.ShuttleError, "uEntryID"):
            shuttle.select_payload({"sChoiceText": "TWO"})
        with self.assertRaisesRegex(shuttle.ShuttleError, "uEntryID"):
            shuttle.select_payload({"sChoiceText": "TWO", "uEntryID": None})


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
