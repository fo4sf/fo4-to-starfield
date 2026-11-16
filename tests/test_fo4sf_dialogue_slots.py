"""scripts/ui/Fo4sfDialogueSlots.as: overlay bind on the unnamed container, not sealed DialogueMenu."""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AS = os.path.join(ROOT, "scripts", "ui", "Fo4sfDialogueSlots.as")


class Fo4sfDialogueSlotsSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(AS, encoding="utf-8") as f:
            cls.src = f.read()

    def test_binds_host_shuttle_not_dialogue_menu_document(self):
        self.assertIn("class Fo4sfDialogueSlots", self.src)
        self.assertNotIn("class DialogueMenu", self.src)
        self.assertNotIn("this.name = HOST_ROOT", self.src)
        self.assertNotIn("this.Menu_mc = this", self.src)
        self.assertIn("BSUIDataManager", self.src)
        self.assertIn("DialogueListData", self.src)
        self.assertIn("sChoiceText", self.src)
        self.assertIn("uEntryID", self.src)
        self.assertIn("DialogueMenu_OnDialogueSelect", self.src)
        self.assertIn("selectedIndex", self.src)
        self.assertIn("fo4sfOptN", self.src)
        self.assertIn("getChildByName", self.src)
        self.assertIn("getDefinitionByName", self.src)

    def test_not_a_compiled_movie(self):
        self.assertTrue(self.src.lstrip().startswith("//"))
        self.assertNotIn("CWS", self.src)


if __name__ == "__main__":
    unittest.main()
