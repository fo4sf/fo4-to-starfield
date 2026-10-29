"""fo4sf.core.loadset: what Starfield will load, read from a made-up game folder, My Games folder and Plugins.txt
(the built-in plugins, Starfield.ccc, sTestFile, plugin copies in My Games\\Starfield\\Data, and the plugins that
override Starfield's start records). Synthetic plugins written with fo4sf.planet.esm; no game files."""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.core import loadset as ls  # noqa: E402
from fo4sf.planet import esm  # noqa: E402


def plugin(path, masters=("Starfield.esm",), records=(), flags=esm.ESM):
    """A plugin with records [(sig, form id)]."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    w = esm.PluginWriter(list(masters), flags)
    for sig, fid in records:
        w.add(esm.Record(sig, fid, [(b"EDID", esm.zbytes("X"))]))
    w.write(path)
    return path


def write(path, text, mode="w"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as f:
        f.write(text)
    return path


class NameTests(unittest.TestCase):
    def test_built_in_and_ours(self):
        for n in ("Starfield.esm", "constellation.esm", "SFBGS003.esm", "SFBGS050.esm", "BlueprintShips-Starfield.esm",
                  "ShatteredSpace.esm", "OldMars.esm"):
            self.assertTrue(ls.built_in(n), n)
        for n in ("FO4Port.esm", "SomeMod.esp", "SFBGS003.txt", "Starfield.ini"):
            self.assertFalse(ls.built_in(n), n)
        self.assertTrue(ls.ours("FO4SFNewGame.esm") and ls.ours("fo4terraincore.esm") and ls.ours("FO4Port.esm"))
        self.assertFalse(ls.ours("SomeMod.esm") or ls.ours("FO4SF.toggle.json"))

    def test_plugins_txt_lines(self):
        with tempfile.TemporaryDirectory() as d:
            p = write(os.path.join(d, "Plugins.txt"), b"\xef\xbb\xbf# c\r\n*A.esm\r\n B.esm\r\n  * C.esm \r\n", "wb")
            lines = ls.read_lines(p)
            self.assertEqual(lines, ["# c", "*A.esm", " B.esm", "  * C.esm "])
            self.assertEqual(ls.active_plugins(lines), ["A.esm", "C.esm"])
            self.assertEqual(ls.read_lines(os.path.join(d, "none.txt")), [])
        self.assertEqual(ls.plugins_txt_path({"LOCALAPPDATA": ""}), None)
        self.assertEqual(ls.plugins_txt_path({"LOCALAPPDATA": "relative"}), None)
        root = os.path.abspath(os.sep)
        self.assertEqual(ls.plugins_txt_path({"LOCALAPPDATA": root}), os.path.join(root, "Starfield", "Plugins.txt"))


class FolderTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = tmp.name
        self.game = os.path.join(self.d, "game")
        self.data = os.path.join(self.game, "Data")
        self.home = os.path.join(self.d, "home")
        self.mg = os.path.join(self.home, "Documents", "My Games", "Starfield")
        os.makedirs(self.data)
        os.makedirs(self.mg)

    def test_my_games_dirs(self):
        self.assertEqual(ls.my_games_dirs(home=self.home), [self.mg])
        od = os.path.join(self.home, "OneDrive", "Documents", "My Games", "Starfield")
        os.makedirs(od)
        self.assertEqual(ls.my_games_dirs(home=self.home), [od, self.mg])           # OneDrive's first
        self.assertEqual(ls.my_games_dirs(self.mg), [self.mg])
        self.assertEqual(ls.my_games_dirs(os.path.join(self.d, "none")), [])

    def test_builtin_plugins(self):
        plugin(os.path.join(self.data, "Starfield.esm"), masters=())
        plugin(os.path.join(self.data, "SFBGS003.esm"))
        plugin(os.path.join(self.data, "FO4Port.esm"))
        write(os.path.join(self.data, "Starfield - Textures01.ba2"), "BTDX")
        got = ls.builtin_plugins(self.data)
        self.assertEqual(sorted(got), ["SFBGS003.esm", "Starfield.esm"])
        self.assertEqual(got["Starfield.esm"], {"size": os.path.getsize(os.path.join(self.data, "Starfield.esm"))})
        self.assertEqual(ls.builtin_plugins(self.data, digest=True)["SFBGS003.esm"]["sha256"],
                         ls.sha256(os.path.join(self.data, "SFBGS003.esm")))
        self.assertIsNone(ls.builtin_plugins(os.path.join(self.d, "none")))

    def test_ccc_test_files_and_shadows(self):
        self.assertEqual((ls.ccc_files(self.game, [self.mg]), ls.test_files(self.game, [self.mg]),
                          ls.shadow_plugins(self.data, [self.mg])), ([], [], []))
        write(os.path.join(self.game, "Starfield.ccc"), "SFBGS003.esm\n\n# note\nBlueprintShips-SFBGS003.esm\n")
        write(os.path.join(self.mg, "Starfield.ccc"), "Mod.esm\n")
        self.assertEqual(ls.ccc_files(self.game, [self.mg]),                          # My Games first
                         [(os.path.join(self.mg, "Starfield.ccc"), ["Mod.esm"]),
                          (os.path.join(self.game, "Starfield.ccc"), ["SFBGS003.esm", "BlueprintShips-SFBGS003.esm"])])
        write(os.path.join(self.mg, "StarfieldCustom.ini"), "[General]\nsTestFile1=\nsTestFile2=Mod.esm\n")
        self.assertEqual(ls.test_files(self.game, [self.mg]),                         # an empty one sets nothing
                         [(os.path.join(self.mg, "StarfieldCustom.ini"), 3, "sTestFile2", "Mod.esm")])
        plugin(os.path.join(self.data, "FO4Port.esm"))
        plugin(os.path.join(self.mg, "Data", "fo4port.esm"))
        plugin(os.path.join(self.mg, "Data", "Lonely.esm"))                         # no twin in Data: never loaded
        write(os.path.join(self.mg, "Data", "Textures", "x.dds"), "DDS ")
        self.assertEqual(ls.shadow_plugins(self.data, [self.mg]),
                         [(os.path.join(self.mg, "Data", "fo4port.esm"), "fo4port.esm")])

    def test_start_overrides(self):
        d = self.data
        plugins = [
            ("Alt.esm", plugin(os.path.join(d, "Alt.esm"), records=[(b"DFOB", 0x0000562D)])),
            ("Glob.esm", plugin(os.path.join(d, "Glob.esm"), records=[(b"GLOB", 0x000A7D31), (b"GLOB", 0x000A7D32)])),
            ("Own.esm", plugin(os.path.join(d, "Own.esm"), records=[(b"QUST", 0x01003448)])),        # its own 003448
            # a small plugin keeps its own records as FE in the file, and overrides of Starfield.esm as 00 (verified)
            ("Small.esm", plugin(os.path.join(d, "Small.esm"), masters=("Starfield.esm", "SFBGS003.esm"),
                                 records=[(b"QUST", 0x00003448), (b"QUST", 0xFE000800)], flags=esm.ESM | 0x100)),
            ("Second.esm", plugin(os.path.join(d, "Second.esm"), masters=("SFBGS003.esm", "Starfield.esm"),
                                  records=[(b"DFOB", 0x0100562D), (b"DFOB", 0x0000562D)])),   # 01 is Starfield.esm
            ("Gone.esm", os.path.join(d, "Gone.esm")),
            ("Bad.esm", write(os.path.join(d, "Bad.esm"), "not a plugin")),
        ]
        hits, bad = ls.start_overrides(plugins)
        self.assertEqual(hits, [("Alt.esm", "StartupQuest_DO", "00562D"), ("Glob.esm", "MQ101Debug", "0A7D31"),
                                ("Small.esm", "MQ101", "003448"), ("Second.esm", "StartupQuest_DO", "00562D")])
        self.assertEqual([n for n, _ in bad], ["Bad.esm"])


class ProbeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = tmp.name
        self.game = os.path.join(self.d, "game")
        self.data = os.path.join(self.game, "Data")
        self.mg = os.path.join(self.d, "mg")
        self.pt = os.path.join(self.d, "local", "Starfield", "Plugins.txt")
        os.makedirs(self.data)
        os.makedirs(self.mg)

    def test_loading_and_start_overrides(self):
        p = ls.LoadProbe(self.game, [self.mg], None)
        self.assertIsNone(p.plugins_txt_lines())
        self.assertIsNone(p.start_overrides())                                       # Plugins.txt not locatable
        plugin(os.path.join(self.data, "SFBGS003.esm"), records=[(b"QUST", 0x00003448)])
        plugin(os.path.join(self.data, "Mod.esm"), records=[(b"DFOB", 0x0000562D)])
        plugin(os.path.join(self.data, "Ccc.esm"), records=[(b"GLOB", 0x000A7D31)])
        plugin(os.path.join(self.data, "FO4Port.esm"))
        staged = plugin(os.path.join(self.d, "FO4Port.esm"), records=[(b"QUST", 0x00003448)])
        write(self.pt, "*SFBGS003.esm\n*Mod.esm\nInactive.esm\n*FO4Port.esm\n")
        write(os.path.join(self.mg, "Starfield.ccc"), "Ccc.esm\nSFBGS003.esm\n")
        p = ls.LoadProbe(self.game, [self.mg], self.pt, [("FO4Port.esm", staged), ("FO4SFExp.esm", "missing.esm")])
        self.assertEqual(p.loading(), [("Ccc.esm", os.path.join(self.data, "Ccc.esm")),
                                       ("Mod.esm", os.path.join(self.data, "Mod.esm")),
                                       ("FO4Port.esm", staged),                     # the staged file replaces Data's
                                       ("FO4SFExp.esm", "missing.esm")])
        self.assertEqual(p.start_overrides(), ([("Ccc.esm", "MQ101Debug", "0A7D31"), ("Mod.esm", "StartupQuest_DO", "00562D"),
                                                ("FO4Port.esm", "MQ101", "003448")], []))
        self.assertTrue(p.my_games_known())
        self.assertFalse(ls.LoadProbe(self.game).my_games_known())

    def test_papyrus_ini_texts(self):
        write(os.path.join(self.game, "Starfield.ini"), "[Papyrus]\nbEnableLogging=0\n")
        write(os.path.join(self.mg, "StarfieldCustom.ini"), "[Papyrus]\nbEnableLogging=1\n")
        write(os.path.join(self.mg, "StarfieldPrefs.ini"), "[Papyrus]\nbEnableLogging=0\n")   # not a [Papyrus] source
        self.assertEqual(ls.LoadProbe(self.game, [self.mg]).ini_texts(),
                         ["[Papyrus]\nbEnableLogging=0\n", "[Papyrus]\nbEnableLogging=1\n"])


if __name__ == "__main__":
    unittest.main()
