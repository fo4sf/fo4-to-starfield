"""start_read.py: the read-only report over Starfield's Papyrus sources for the new-game framework questions.
A fake ContentResources.zip; no game."""
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "newgame"))
import start_read as sr  # noqa: E402

MQ00 = "Scriptname Fragments:Quests:QF_MQ00_00005790 extends Quest\nFunction Fragment_Stage_0010_Item_00()\n" \
       "  if MQ101Debug.GetValue() == 0\n    MQ101Debug.SetValue(10)\n  endif\nEndFunction\n"


class StartReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.zip = os.path.join(self.tmp.name, "ContentResources.zip")
        with zipfile.ZipFile(self.zip, "w") as z:
            z.writestr("Scripts/Source/Fragments/Quests/QF_MQ00_00005790.psc", MQ00)
            z.writestr("Scripts/Source/Fragments/Quests/QF_MQ101_00003448.psc", "Function Fragment_Stage_9000()\n"
                       "  Game.SetInChargen(false, false, false)\nEndFunction\n")
            z.writestr("Scripts/Source/Other.psc", "a\nb\nShip s = PlayerShip.GetShipRef()\nc\n")
            z.writestr("Scripts/Source/Unrelated.psc", "nothing here\n")
            z.writestr("Scripts/Source/Notes.txt", "MQ101Debug in a non-psc file is skipped\n")

    def test_whole_files_and_hits(self):
        r = sr.read(self.zip)
        self.assertEqual(r["files"], 4)
        self.assertEqual(sorted(os.path.basename(n) for n in r["whole"]),
                         ["QF_MQ00_00005790.psc", "QF_MQ101_00003448.psc"])
        self.assertEqual([(os.path.basename(n), no) for n, no, _ in r["hits"]["MQ101Debug"]],
                         [("QF_MQ00_00005790.psc", 3), ("QF_MQ00_00005790.psc", 4)])
        self.assertEqual(len(r["hits"]["SetInChargen"]), 1)
        name, no, ctx = r["hits"]["GetShipRef"][0]
        self.assertEqual(no, 3)
        self.assertEqual(ctx.splitlines(), ["a", "b", "Ship s = PlayerShip.GetShipRef()", "c"])

    def test_main_writes_only_the_report(self):
        out = os.path.join(self.tmp.name, "rep", "report.txt")
        before = os.path.getmtime(self.zip)
        self.assertEqual(sr.main(["--zip", self.zip, "--out", out]), 0)
        text = open(out, encoding="utf-8").read()
        self.assertIn("===== WHOLE Scripts/Source/Fragments/Quests/QF_MQ00_00005790.psc", text)
        self.assertIn("MQ101Debug.SetValue(10)", text)
        self.assertIn("===== TERM OnPlayerLoadGame: 0 line(s)", text)
        self.assertEqual(os.path.getmtime(self.zip), before)

    def test_missing_zip_refused(self):
        with self.assertRaises(SystemExit):
            sr.main(["--zip", os.path.join(self.tmp.name, "none.zip"), "--out", os.path.join(self.tmp.name, "r.txt")])


if __name__ == "__main__":
    unittest.main()
