"""exp_install.py --pack: the staged Data tree goes into the plugin's own archives, textures into a DDS-format
'<plugin> - Textures.ba2' (as deploy_starfield.py does for FO4Port), the rest into a General '<plugin> - Main.ba2';
installed and uninstalled like every other file. A fake Archive2 (recorded subprocess.run) builds the archives."""
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import exp_install  # noqa: E402


def write(p, data=b"x"):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


class TexturePackTests(unittest.TestCase):
    def setUp(self):
        root = tempfile.mkdtemp()
        self.game, self.exp, self.local = (os.path.join(root, x) for x in ("game", "exp", "local"))
        os.makedirs(os.path.join(self.game, "Data"))
        write(os.path.join(self.game, "Tools", "Archive2", "Archive2.exe"), b"MZ fake")   # never executed
        write(os.path.join(self.exp, "Exp.esm"), b"TES4")
        write(os.path.join(self.exp, "Exp_Mars.esm"), b"TES4")
        write(os.path.join(self.local, "Starfield", "Plugins.txt"), b"*FO4Port.esm\r\n")
        self.calls = []

        def fake_run(cmd, cwd=None, capture_output=False, text=False, **kw):
            # Archive2 <folders> -create=<out> -root=<root> -format=<fmt> -compression=Default
            opts = dict(a[1:].split("=", 1) for a in cmd[2:])
            self.calls.append({"folders": cmd[1].split(","), "format": opts["format"], "root": opts["root"],
                               "out": os.path.basename(opts["create"]).replace(".tmp.ba2", "")})   # built under a temp name
            write(opts["create"], b"BTDX" + b"\0" * 20)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        self.old = (exp_install.subprocess.run, os.environ.get("LOCALAPPDATA"))
        exp_install.subprocess.run = fake_run
        os.environ["LOCALAPPDATA"] = self.local

    def tearDown(self):
        exp_install.subprocess.run = self.old[0]
        if self.old[1] is None:
            os.environ.pop("LOCALAPPDATA")
        else:
            os.environ["LOCALAPPDATA"] = self.old[1]

    def install(self):
        exp_install.main(["install", "--exp-dir", self.exp, "--starfield", self.game,
                          "--plugins", "Exp.esm,Exp_Mars.esm", "--pack"])

    def data(self):
        return sorted(os.listdir(os.path.join(self.game, "Data")))

    def test_textures_go_into_a_dds_archive_and_the_rest_into_main(self):
        write(os.path.join(self.exp, "Data", "Terrain", "W.btd"), b"BTDB")
        write(os.path.join(self.exp, "Data", "textures", "terrain", "overlaymasks", "w.dds"), b"DDS ")
        self.install()
        by_fmt = {c["format"]: c for c in self.calls}
        self.assertEqual(sorted(by_fmt), ["DDS", "General"])
        self.assertEqual((by_fmt["General"]["folders"], by_fmt["General"]["out"]), (["Terrain"], "Exp - Main.ba2"))
        self.assertEqual((by_fmt["DDS"]["folders"], by_fmt["DDS"]["out"]), (["textures"], "Exp - Textures.ba2"))
        self.assertTrue(all(c["root"] == os.path.join(self.exp, "Data") for c in self.calls))
        self.assertEqual(self.data(), ["Exp - Main.ba2", "Exp - Textures.ba2", "Exp.esm", "Exp_Mars.esm",
                                       exp_install.RECORD])
        self.assertFalse(os.path.exists(os.path.join(self.game, "Data", "Terrain")))   # no loose files
        exp_install.main(["uninstall", "--starfield", self.game])
        self.assertEqual(self.data(), [])
        with open(os.path.join(self.local, "Starfield", "Plugins.txt"), "rb") as f:
            self.assertEqual(f.read(), b"*FO4Port.esm\r\n")

    def test_textures_only_builds_no_main_archive(self):
        write(os.path.join(self.exp, "Data", "Textures", "a.DDS"), b"DDS ")              # any case
        self.install()
        self.assertEqual([(c["format"], c["folders"]) for c in self.calls], [("DDS", ["Textures"])])
        self.assertIn("Exp - Textures.ba2", self.data())
        self.assertNotIn("Exp - Main.ba2", self.data())

    def test_a_non_dds_file_in_textures_is_refused_before_anything_is_built(self):
        write(os.path.join(self.exp, "Data", "Terrain", "W.btd"), b"BTDB")
        write(os.path.join(self.exp, "Data", "textures", "notes.txt"), b"x")
        with self.assertRaises(SystemExit):
            self.install()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.data(), [])

    def test_an_existing_texture_archive_is_never_overwritten(self):
        write(os.path.join(self.exp, "Data", "textures", "a.dds"), b"DDS ")
        write(os.path.join(self.game, "Data", "Exp - Textures.ba2"), b"theirs")
        with self.assertRaises(SystemExit):
            self.install()
        with open(os.path.join(self.game, "Data", "Exp - Textures.ba2"), "rb") as f:
            self.assertEqual(f.read(), b"theirs")
        self.assertNotIn("Exp.esm", self.data())

    def test_archive2_failure_installs_nothing(self):
        write(os.path.join(self.exp, "Data", "textures", "a.dds"), b"DDS ")
        exp_install.subprocess.run = lambda *a, **k: SimpleNamespace(returncode=1, stdout="bad", stderr="")
        with self.assertRaises(SystemExit):
            self.install()
        self.assertEqual(self.data(), [])


if __name__ == "__main__":
    unittest.main()
