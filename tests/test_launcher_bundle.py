"""Support bundle (src/fo4sf/launcher/bundle.py) from synthetic driver state, records and INIs; nothing is sent."""
import importlib.util
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf.launcher import bundle  # noqa: E402

HOME = "C:\\Users\\username"


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class BundleTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = t.name
        self.state = os.path.join(self.root, ".launcher")
        write(os.path.join(self.state, "state.json"), '{"w": "C:\\\\Users\\\\username\\\\work"}')
        for n in ("stage.1.log", "stage.2.log", "select.1.log", "notes.txt"):
            write(os.path.join(self.state, "logs", n), f"{n} at C:/Users/username/Desktop by Username\n")
        self.sf = os.path.join(self.root, "Starfield")
        write(os.path.join(self.sf, "Data", "FO4SFExp.install.json"), '{"exp_dir": "D:\\\\Modding\\\\x"}')
        write(os.path.join(self.sf, "Data", "Starfield.esm"), "TES4 not text we take")
        write(os.path.join(self.sf, "StarfieldPrefs.ini"), "[Display]\n")
        self.pt = os.path.join(self.root, "local", "Starfield", "Plugins.txt")
        write(self.pt, "*FO4Port.esm\n")
        self.mg = os.path.join(self.root, "My Games", "Starfield")
        write(os.path.join(self.mg, "StarfieldCustom.ini"), "[General]\nsTestFile1=x.esm\n")

    def make(self, **kw):
        out = os.path.join(self.root, "support.zip")
        kw.setdefault("state_dirs", [self.state])
        bundle.make(out, starfield=self.sf, plugins_txt=self.pt, my_games=self.mg, home=HOME, user="username", **kw)
        return bundle.manifest_of(out)

    def test_contents_and_newest_log_per_step(self):
        z = self.make()
        self.assertEqual(sorted(z), ["BUNDLE.txt", "Plugins.txt", "driver/logs/select.1.log", "driver/logs/stage.2.log",
                                     "driver/state.json", "my-games/StarfieldCustom.ini", "starfield/Data/FO4SFExp.install.json",
                                     "starfield/StarfieldPrefs.ini"])
        self.assertNotIn("Starfield.esm", "".join(z))                       # no game data
        self.assertIn("starfield/Data/FO4Port.deploy.json", z["BUNDLE.txt"])  # looked for, not found
        self.assertIn("sTestFile1=x.esm", z["my-games/StarfieldCustom.ini"])

    def test_user_name_and_home_are_taken_out(self):
        z = self.make()
        for name, text in z.items():
            self.assertNotRegex(text.casefold(), "username", name)
        self.assertIn("%USERPROFILE%\\\\work", z["driver/state.json"])          # JSON's doubled slashes too
        self.assertIn("%USERPROFILE%/Desktop by <user>", z["driver/logs/stage.2.log"])

    def test_long_log_keeps_its_tail_and_says_so(self):
        write(os.path.join(self.state, "logs", "stage.3.log"), "x" * 100 + "END")
        out = os.path.join(self.root, "small.zip")
        items, missing = bundle.collect(state_dirs=[self.state])
        bundle.write(out, items, missing, home=HOME, user="username", cap=10)
        z = bundle.manifest_of(out)
        self.assertTrue(z["driver/logs/stage.3.log"].endswith("xxxxxxxEND"))
        self.assertIn("only the last 10 of 103 bytes", z["driver/logs/stage.3.log"])
        self.assertIn("(last 10 of 103 bytes)", z["BUNDLE.txt"])

    def test_never_overwrites(self):
        self.make()
        with self.assertRaises(FileExistsError):
            self.make()

    def test_short_user_names_are_not_replaced_in_ordinary_words(self):
        self.assertEqual(bundle.clean("al is in the hall", home="", user="al"), "al is in the hall")

    def test_cli(self):
        spec = importlib.util.spec_from_file_location("launcher_cli", os.path.join(ROOT, "scripts", "launcher.py"))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        out = os.path.join(self.root, "cli.zip")
        argv = ["bundle", "--out", out, "--state-dir", self.state, "--starfield", self.sf, "--plugins-txt", self.pt]
        self.assertEqual(cli.main(argv), 0)
        self.assertIn("Plugins.txt", bundle.manifest_of(out))
        self.assertIn("launcher code: ", bundle.manifest_of(out)["BUNDLE.txt"])   # which version made the report
        self.assertEqual(cli.main(argv), 2)                                 # exists: refused, not overwritten


if __name__ == "__main__":
    unittest.main()
