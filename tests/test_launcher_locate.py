"""locate (src/fo4sf/launcher/locate.py): finding Steam games from synthetic libraryfolders.vdf and appmanifest files."""
import importlib.util
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf.launcher import locate  # noqa: E402


def write(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def manifest(appid, installdir):
    return f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"x"\n\t"installdir"\t\t"{installdir}"\n}}\n'


class LocateTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.steam = os.path.join(t.name, "Steam")
        self.lib2 = os.path.join(t.name, "SteamLibrary")
        lib2 = self.lib2.replace("\\", "\\\\")
        write(os.path.join(self.steam, "config", "libraryfolders.vdf"),
              '"libraryfolders"\n{\n\t// a comment\n\t"0"\n\t{\n\t\t"path"\t\t"' + self.steam.replace("\\", "\\\\")
              + '"\n\t\t"apps"\n\t\t{\n\t\t\t"377160"\t\t"123"\n\t\t}\n\t}\n\t"1"\n\t{\n\t\t"path"\t\t"' + lib2
              + '"\n\t}\n}\n')

    def test_parse_vdf_nested_escapes_and_comments(self):
        d = locate.parse_vdf('"a"\n{\n "b" "C:\\\\Games\\\\x" // note\n "c" { "d" "1" }\n}\n')
        self.assertEqual(d, {"a": {"b": "C:\\Games\\x", "c": {"d": "1"}}})
        for bad in ('"a" {', '}', '{ "a" "b" }'):
            with self.assertRaises(ValueError):
                locate.parse_vdf(bad)

    def test_games_in_two_libraries_and_depot_downloads(self):
        write(os.path.join(self.lib2, "steamapps", "appmanifest_1716740.acf"), manifest("1716740", "Starfield"))
        os.makedirs(os.path.join(self.lib2, "steamapps", "common", "Starfield"))
        write(os.path.join(self.steam, "steamapps", "appmanifest_377160.acf"), manifest("377160", "Fallout 4"))
        os.makedirs(os.path.join(self.steam, "steamapps", "common", "Fallout 4", "Data"))
        content = os.path.join(self.steam, "steamapps", "content", "app_377160")
        write(os.path.join(content, "depot_435880", "Data", "DLCworkshop01.esm"))
        write(os.path.join(content, "depot_377163", "Data", "Fallout4.esm"))
        write(os.path.join(content, "depot_435871", "DLCRobot.esm"))               # data files at the depot's root
        os.makedirs(os.path.join(content, "depot_99", "empty"))
        r = locate.locate(self.steam)
        self.assertEqual(r["libraries"], [os.path.normpath(self.steam), os.path.normpath(self.lib2)])
        self.assertEqual(r["starfield"], os.path.join(self.lib2, "steamapps", "common", "Starfield"))
        self.assertEqual(r["fallout4"], os.path.join(self.steam, "steamapps", "common", "Fallout 4"))
        self.assertEqual(r["fallout4_depots"], [os.path.join(content, "depot_377163", "Data"),
                                                os.path.join(content, "depot_435871"),
                                                os.path.join(content, "depot_435880", "Data")])   # by depot number
        self.assertEqual(locate.fo4_data_folders(r)[-1], os.path.join(r["fallout4"], "Data"))
        self.assertEqual(r["notes"], [])

    def test_manifest_without_its_folder_is_not_an_install(self):
        write(os.path.join(self.steam, "steamapps", "appmanifest_1716740.acf"), manifest("1716740", "Starfield"))
        r = locate.locate(self.steam, gog="")
        self.assertIsNone(r["starfield"])
        self.assertIn("Starfield not found in any Steam library", r["notes"])

    def test_a_game_still_downloading_is_not_an_install_yet(self):
        os.makedirs(os.path.join(self.steam, "steamapps", "common", "Fallout 4", "Data"))
        acf = os.path.join(self.steam, "steamapps", "appmanifest_377160.acf")
        for flags, found in (("1042", False), ("4", True), ("1028", True)):   # downloading; installed; updating
            write(acf, manifest("377160", "Fallout 4").replace('"name"', f'"StateFlags"\t\t"{flags}"\n\t"name"'))
            with self.subTest(flags=flags):
                self.assertEqual(locate.find_app(self.steam, "377160") is not None, found)
        r = locate.locate(self.steam, gog="")
        self.assertEqual(r["fallout4"], os.path.join(self.steam, "steamapps", "common", "Fallout 4"))
        # once installed, its Data comes after the depot downloads: detect uses the later copy of any archive
        self.assertEqual(locate.fo4_data_folders(r)[-1], os.path.join(r["fallout4"], "Data"))

    def test_old_libraryfolders_layout(self):
        old = os.path.join(self.steam, "steamapps", "libraryfolders.vdf")
        write(old, '"LibraryFolders"\n{\n\t"TimeNextStatsReport"\t"1"\n\t"1"\t"' + self.lib2.replace("\\", "\\\\")
              + '"\n}\n')
        os.remove(os.path.join(self.steam, "config", "libraryfolders.vdf"))
        self.assertEqual(locate.libraries(self.steam), [os.path.normpath(self.steam), os.path.normpath(self.lib2)])

    def test_a_library_listed_in_other_case_is_one_library(self):
        # the owner's libraryfolders.vdf lists Steam's own folder in lower case: on Windows that is the same folder,
        # and listing it twice listed every Fallout 4 depot twice (PC, 2026-10-22)
        write(os.path.join(self.steam, "config", "libraryfolders.vdf"),
              '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"' + self.steam.lower().replace("\\", "\\\\")
              + '"\n\t}\n\t"1"\n\t{\n\t\t"path"\t\t"' + self.lib2.replace("\\", "\\\\") + '"\n\t}\n}\n')
        with mock.patch("os.path.normcase", str.lower):                 # Windows' rule, on any test machine
            self.assertEqual(locate.libraries(self.steam), [os.path.normpath(self.steam), os.path.normpath(self.lib2)])

    def test_gog_fallout4_when_steam_has_none(self):
        gog = os.path.join(os.path.dirname(self.steam), "GOG Games", "Fallout 4 GOTY")
        os.makedirs(os.path.join(gog, "Data"))
        r = locate.locate(self.steam, gog=gog)
        self.assertEqual((r["fallout4"], r["fallout4_store"]), (gog, "gog"))
        self.assertEqual(locate.fo4_data_folders(r), [os.path.join(gog, "Data")])
        write(os.path.join(self.steam, "steamapps", "appmanifest_377160.acf"), manifest("377160", "Fallout 4"))
        os.makedirs(os.path.join(self.steam, "steamapps", "common", "Fallout 4"))
        self.assertEqual(locate.locate(self.steam, gog=gog)["fallout4_store"], "steam")       # Steam first (LA-5)

    def test_no_steam(self):
        r = locate.locate(os.path.join(self.steam, "missing"), gog="")
        self.assertIsNone(r["steam"])
        self.assertTrue(r["notes"])

    def test_cli(self):
        spec = importlib.util.spec_from_file_location("launcher_cli", os.path.join(ROOT, "scripts", "launcher.py"))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        self.assertEqual(cli.main(["find", "--steam", self.steam]), 1)
        write(os.path.join(self.steam, "steamapps", "appmanifest_1716740.acf"), manifest("1716740", "Starfield"))
        os.makedirs(os.path.join(self.steam, "steamapps", "common", "Starfield"))
        write(os.path.join(self.steam, "steamapps", "content", "app_377160", "depot_377163", "Data", "Fallout4.esm"))
        self.assertEqual(cli.main(["find", "--steam", self.steam]), 0)


if __name__ == "__main__":
    unittest.main()
