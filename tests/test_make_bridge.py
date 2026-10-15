"""make_bridge.py: the StarfieldCustom.ini [Papyrus] edit (pure text; the stage command needs the game's tools)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "bridge"))
import make_bridge  # noqa: E402


class IniTests(unittest.TestCase):
    def test_empty_file_gets_the_section(self):
        new, changed = make_bridge.ensure_ini("")
        self.assertTrue(changed)
        self.assertEqual(new, "[Papyrus]\nbEnableLogging=1\nbEnableTrace=1\nbLoadDebugInformation=1\n")

    def test_other_sections_kept_and_section_appended(self):
        old = "[General]\nsLanguage=ENGLISH\n\n[Display]\nfGamma=1.0\n"
        new, changed = make_bridge.ensure_ini(old)
        self.assertTrue(changed)
        self.assertTrue(new.startswith(old))
        self.assertIn("\n[Papyrus]\nbEnableLogging=1\n", new)

    def test_existing_section_updated_in_place(self):
        old = "[Papyrus]\nbEnableLogging=0\nbEnableProfiling=0\n[Display]\nfGamma=1.0\n"
        new, changed = make_bridge.ensure_ini(old)
        self.assertTrue(changed)
        self.assertEqual(new, "[Papyrus]\nbEnableLogging=1\nbEnableProfiling=0\nbEnableTrace=1\nbLoadDebugInformation=1\n"
                              "[Display]\nfGamma=1.0\n")

    def test_already_set_is_unchanged(self):
        old = "[Papyrus]\nbEnableLogging=1\nbEnableTrace=1\nbLoadDebugInformation=1\n"
        new, changed = make_bridge.ensure_ini(old)
        self.assertFalse(changed)
        self.assertEqual(new, old)

    def test_case_insensitive_keys_and_section(self):
        old = "[papyrus]\nBENABLELOGGING = 1\nbenabletrace=0\n"
        new, changed = make_bridge.ensure_ini(old)
        self.assertTrue(changed)
        self.assertEqual(new, "[papyrus]\nBENABLELOGGING = 1\nbEnableTrace=1\nbLoadDebugInformation=1\n")


if __name__ == "__main__":
    unittest.main()
