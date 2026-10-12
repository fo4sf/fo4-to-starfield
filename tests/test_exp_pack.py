"""exp_install.py --pack: the staged Data tree, textures included, goes into one General, stored '<plugin> - Main.ba2'
(the layout vanilla uses for terrain textures and overlay masks), built outside the staged folder, installed and
uninstalled like every other file. A fake Archive2 (recorded subprocess.run) builds the archive; nothing is executed."""
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


def read(p):
    with open(p, "rb") as f:
        return f.read()


def tree(d):
    return sorted(os.path.relpath(os.path.join(r, f), d) for r, _, fs in os.walk(d) for f in fs)


class PackTests(unittest.TestCase):
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
            # Archive2 <folders> -create=<out> -root=<root> -format=<fmt> -compression=<c>
            opts = dict(a[1:].split("=", 1) for a in cmd[2:])
            self.calls.append({"folders": cmd[1].split(","), "format": opts["format"], "root": opts["root"],
                               "compression": opts["compression"], "create": opts["create"]})
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

    def test_terrain_and_overlay_mask_go_into_one_general_stored_archive(self):
        write(os.path.join(self.exp, "Data", "Terrain", "W.btd"), b"BTDB")
        write(os.path.join(self.exp, "Data", "textures", "terrain", "overlaymasks", "w.dds"), b"DDS ")
        before = tree(self.exp)
        self.install()
        self.assertEqual(len(self.calls), 1)
        c = self.calls[0]
        self.assertEqual((c["folders"], c["format"], c["compression"]), (["Terrain", "textures"], "General", "None"))
        self.assertEqual(c["root"], os.path.join(self.exp, "Data"))
        self.assertFalse(os.path.normcase(c["create"]).startswith(os.path.normcase(self.exp)))   # built elsewhere
        self.assertFalse(os.path.exists(os.path.dirname(c["create"])))                          # and cleaned up
        self.assertEqual(tree(self.exp), before)                                                 # staged folder only read
        self.assertEqual(self.data(), ["Exp - Main.ba2", "Exp.esm", "Exp_Mars.esm", exp_install.RECORD])
        self.assertFalse(os.path.exists(os.path.join(self.game, "Data", "Terrain")))           # no loose files
        exp_install.main(["uninstall", "--starfield", self.game])
        self.assertEqual(self.data(), [])
        self.assertEqual(read(os.path.join(self.local, "Starfield", "Plugins.txt")), b"*FO4Port.esm\r\n")

    def test_an_existing_archive_is_never_overwritten(self):
        write(os.path.join(self.exp, "Data", "textures", "a.dds"), b"DDS ")
        write(os.path.join(self.game, "Data", "Exp - Main.ba2"), b"theirs")
        with self.assertRaises(SystemExit):
            self.install()
        self.assertEqual(read(os.path.join(self.game, "Data", "Exp - Main.ba2")), b"theirs")
        self.assertNotIn("Exp.esm", self.data())

    def test_archive2_failure_installs_nothing(self):
        write(os.path.join(self.exp, "Data", "textures", "a.dds"), b"DDS ")
        before = tree(self.exp)
        exp_install.subprocess.run = lambda *a, **k: SimpleNamespace(returncode=1, stdout="bad", stderr=None)
        with self.assertRaises(SystemExit):
            self.install()
        self.assertEqual(self.data(), [])
        self.assertEqual(tree(self.exp), before)

    def test_without_pack_the_loose_files_are_copied(self):
        write(os.path.join(self.exp, "Data", "Terrain", "W.btd"), b"BTDB")
        exp_install.main(["install", "--exp-dir", self.exp, "--starfield", self.game, "--plugins", "Exp.esm"])
        self.assertEqual(self.calls, [])
        self.assertEqual(read(os.path.join(self.game, "Data", "Terrain", "W.btd")), b"BTDB")
        exp_install.main(["uninstall", "--starfield", self.game])
        self.assertEqual(self.data(), [])


if __name__ == "__main__":
    unittest.main()
