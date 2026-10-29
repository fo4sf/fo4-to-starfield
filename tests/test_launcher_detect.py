"""Launcher detect stage and disk measure (src/fo4sf/launcher/detect.py) on synthetic folders; no game files."""
import importlib.util
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf.launcher import detect, manifest, runtimes  # noqa: E402

DLC = ("DLCRobot.esm", "DLCworkshop01.esm", "DLCCoast.esm", "DLCworkshop02.esm", "DLCworkshop03.esm",
       "DLCNukaWorld.esm")


def write(path, data=b"x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


class DetectTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = t.name
        self.fo4 = os.path.join(self.root, "fo4", "Data")
        write(os.path.join(self.fo4, "Fallout4.esm"), b"TES4 base")
        for n in DLC:
            write(os.path.join(self.fo4, n), b"TES4 " + n.encode())
        self.sf = os.path.join(self.root, "Starfield")
        write(os.path.join(self.sf, "Starfield.exe"), b"MZ")
        write(os.path.join(self.sf, "Tools", "Archive2", "Archive2.exe"), b"MZ")
        write(os.path.join(self.sf, "CreationKit.exe"), b"MZ")
        write(os.path.join(self.sf, "sfse_loader.exe"), b"MZ loader")
        write(os.path.join(self.sf, "sfse_test.dll"), b"MZ sfse dll")      # synthetic; the real name is measured
        os.makedirs(os.path.join(self.sf, "Data"), exist_ok=True)
        self.table = {"schema": 1, "sources": []}
        detect.add_sources(self.table, {"fo4": manifest.fo4_inputs([self.fo4])}, "test install")
        self.runtimes = {"schema": 1, "runtimes": []}
        runtimes.add_runtime(self.runtimes, {"game": manifest.game_pins(self.sf)}, "test runtime")
        self.my_games = os.path.join(self.root, "Documents", "My Games", "Starfield")
        os.makedirs(self.my_games)

    def run_detect(self, **kw):
        kw.setdefault("sources", self.table)
        kw.setdefault("runtimes", self.runtimes)
        return detect.detect(fo4_data=[self.fo4], starfield=self.sf, **kw)

    def test_ready_when_everything_is_known(self):
        r = self.run_detect(out_dir=self.root, need_gb=0, floor_gb=0, my_games=self.my_games)
        self.assertTrue(r["ready"], r["refusals"])
        self.assertEqual(r["fo4"]["masters"]["Fallout4.esm"]["version"], "test install")
        self.assertEqual(r["warnings"], [])

    def test_unknown_version_is_refused_unless_allowed(self):
        write(os.path.join(self.fo4, "Fallout4.esm"), b"TES4 other build")
        r = self.run_detect()
        self.assertFalse(r["ready"])
        self.assertTrue(any("not a known version" in x for x in r["refusals"]))
        self.assertTrue(self.run_detect(allow_unknown=True)["ready"])

    def test_missing_dlc_named(self):
        os.remove(os.path.join(self.fo4, "DLCNukaWorld.esm"))
        r = self.run_detect()
        self.assertFalse(r["ready"])
        self.assertIn("DLC missing: DLCNukaWorld.esm (Nuka-World)", r["refusals"])
        self.assertTrue(self.run_detect(allow_missing_dlc=True)["ready"])

    def test_archive2_and_sfse_required_ck_optional(self):
        os.remove(os.path.join(self.sf, "Tools", "Archive2", "Archive2.exe"))
        os.remove(os.path.join(self.sf, "CreationKit.exe"))
        os.remove(os.path.join(self.sf, "sfse_loader.exe"))
        r = self.run_detect(my_games=self.my_games)
        self.assertTrue(any("Archive2" in x for x in r["refusals"]))
        self.assertIn("Starfield: SFSE not installed (required)", r["refusals"])    # NG-1
        self.assertEqual(len(r["refusals"]), 2)
        self.assertEqual(len(r["warnings"]), 1)
        r = self.run_detect(require_ck=True, my_games=self.my_games)
        self.assertEqual(len(r["refusals"]), 3)
        r = self.run_detect(require_sfse=False, my_games=self.my_games)
        self.assertEqual(len(r["refusals"]), 1)

    def test_unlisted_runtime_is_refused_unless_allowed(self):
        write(os.path.join(self.sf, "Starfield.exe"), b"MZ a later patch")      # LA-15
        r = self.run_detect(my_games=self.my_games)
        self.assertFalse(r["ready"])
        self.assertTrue(any("not listed as a good runtime" in x and "only when launched" in x for x in r["refusals"]))
        self.assertIsNone(r["game"]["runtime"])
        r = self.run_detect(my_games=self.my_games, allow_unknown_runtime=True)
        self.assertTrue(r["ready"], r["refusals"])
        self.assertTrue(any("not listed as a good runtime" in w for w in r["warnings"]))

    def test_listed_runtime_needs_its_own_sfse_build(self):
        r = self.run_detect(my_games=self.my_games)
        self.assertEqual(r["game"]["runtime"], "test runtime")
        write(os.path.join(self.sf, "sfse_test.dll"), b"MZ another sfse build")
        r = self.run_detect(my_games=self.my_games)
        self.assertIn("Starfield: SFSE: sfse_test.dll is not the SFSE build listed for this runtime", r["refusals"])
        os.remove(os.path.join(self.sf, "sfse_test.dll"))
        r = self.run_detect(my_games=self.my_games)
        self.assertTrue(any("sfse_test.dll missing" in x for x in r["refusals"]))
        write(os.path.join(self.sf, "sfse_test.dll"), b"MZ sfse dll")
        write(os.path.join(self.sf, "sfse_loader.exe"), b"MZ other loader")
        r = self.run_detect(my_games=self.my_games)
        self.assertIn("Starfield: SFSE: sfse_loader.exe is not the SFSE build listed for this runtime", r["refusals"])
        write(os.path.join(self.sf, "sfse_loader.exe"), b"MZ loader")
        write(os.path.join(self.sf, "sfse_old.dll"), b"MZ an older sfse build")
        r = self.run_detect(my_games=self.my_games)
        self.assertFalse(r["ready"])
        self.assertTrue(any("sfse_old.dll is not part of the SFSE build listed" in x for x in r["refusals"]))

    def test_game_pass_folder_is_refused(self):
        xbox = os.path.join(self.root, "XboxGames", "Starfield", "Content")
        for rel in ("Starfield.exe", "sfse_loader.exe", "sfse_test.dll", os.path.join("Tools", "Archive2", "Archive2.exe")):
            with open(os.path.join(self.sf, rel), "rb") as f:
                write(os.path.join(xbox, rel), f.read())
        os.makedirs(os.path.join(xbox, "Data"))
        r = detect.detect(fo4_data=[self.fo4], starfield=xbox, sources=self.table, runtimes=self.runtimes,
                          my_games=self.my_games)
        self.assertFalse(r["ready"])
        self.assertTrue(any("Game Pass" in x and "Steam" in x for x in r["refusals"]))

    def test_runtimes_add_needs_a_hashed_exe_and_sfse(self):
        self.assertEqual(runtimes.add_runtime(self.runtimes, {"game": manifest.game_pins(self.sf)}, "again"), 0)
        os.remove(os.path.join(self.sf, "sfse_test.dll"))
        with self.assertRaises(ValueError):
            runtimes.add_runtime({"schema": 1, "runtimes": []}, {"game": manifest.game_pins(self.sf)}, "x")
        with self.assertRaises(ValueError):
            runtimes.add_runtime({"schema": 1, "runtimes": []}, {"game": {}}, "x")

    def test_exe_version_names_a_runtime_without_a_label(self):
        import struct
        fixed = struct.pack("<13I", 0xFEEF04BD, 0x10000, (9 << 16) | 8, (7 << 16) | 6, (9 << 16) | 8,
                            (7 << 16) | 6, 0x3F, 0, 0x40004, 1, 0, 0, 0)
        exe = b"MZ" + b"\0" * 64 + "VS_VERSION_INFO".encode("utf-16-le") + b"\0\0\0\0" + fixed + b"\0" * 32
        write(os.path.join(self.sf, "Starfield.exe"), exe)          # synthetic; the real version is read on the PC
        game = manifest.game_pins(self.sf)
        self.assertEqual(game["exe_version"], {"file": "9.8.7.6", "product": "9.8.7.6"})
        table = {"schema": 1, "runtimes": []}
        self.assertEqual(runtimes.add_runtime(table, {"game": game}), 1)
        self.assertEqual((table["runtimes"][0]["label"], table["runtimes"][0]["exe_version"]),
                         ("Steam, Starfield.exe 9.8.7.6", "9.8.7.6"))
        write(os.path.join(self.sf, "Starfield.exe"), b"MZ no version resource")
        game = manifest.game_pins(self.sf)
        self.assertIsNone(game["exe_version"])
        with self.assertRaises(ValueError):
            runtimes.add_runtime({"schema": 1, "runtimes": []}, {"game": game})
        self.assertEqual(runtimes.add_runtime({"schema": 1, "runtimes": []}, {"game": game}, "labelled"), 1)

    def test_shipped_runtime_table_is_well_formed(self):
        t = runtimes.load_runtimes()
        for r in t["runtimes"]:
            self.assertRegex(r["exe_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(r["sfse"]["loader_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(r["sfse"]["dlls"] and r["label"])

    def test_disk_floor(self):
        r = self.run_detect(out_dir=os.path.join(self.root, "not", "yet"), need_gb=10 ** 9, floor_gb=40)
        self.assertFalse(r["ready"])
        self.assertTrue(any(x.startswith("Disk:") for x in r["refusals"]))

    def test_work_folder_rules(self):
        bad = {"D:\\": "drive root", "C:/Program Files/FO4SF": "protected", "C:\\Users\\aaron\\Documents\\out":
               "Users folder", "E:\\OneDrive - Home\\build": "OneDrive", "D:\\OneDrive\\x": "OneDrive"}
        for path, why in bad.items():
            with self.subTest(path=path):
                self.assertTrue(any(why in p for p in detect.work_folder_problems(path)), path)
        for path in ("D:\\Modding\\FO4SF", "C:\\Modding\\scratch", self.root):
            self.assertEqual(detect.work_folder_problems(path), [], path)
        r = self.run_detect(out_dir="C:\\Users\\aaron\\Desktop\\fo4sf", need_gb=0, floor_gb=0, my_games=self.my_games)
        self.assertTrue(any(x.startswith("Work folder:") for x in r["refusals"]))

    def test_test_file_in_any_ini_is_refused(self):
        mg = os.path.join(self.root, "My Games", "Starfield")
        write(os.path.join(mg, "StarfieldCustom.ini"), b"[General]\nsTestFile1=Foo.esm\nsTestFile2=\n")
        write(os.path.join(self.sf, "Starfield.ini"), b"[General]\n; sTestFile3=commented\n")
        r = self.run_detect(my_games=mg)
        self.assertFalse(r["ready"])
        self.assertEqual(len(r["refusals"]), 1)
        self.assertIn("sTestFile1=Foo.esm", r["refusals"][0])
        self.assertIn("line 2", r["refusals"][0])

    def test_test_file_in_a_language_ini_is_refused(self):
        mg = os.path.join(self.root, "My Games", "Starfield")
        os.makedirs(mg, exist_ok=True)
        write(os.path.join(self.sf, "Starfield_de.ini"), b"[General]\nsTestFile1=Lang.esm\n")
        write(os.path.join(self.sf, "Starfield_backup.ini"), b"[General]\nsTestFile1=Old.esm\n")  # not the game's
        r = self.run_detect(my_games=mg)
        self.assertFalse(r["ready"])
        self.assertEqual(len(r["refusals"]), 1)
        self.assertIn("sTestFile1=Lang.esm in " + os.path.join(self.sf, "Starfield_de.ini"), r["refusals"][0])

    def test_loose_files_in_my_games_are_reported(self):
        mg = os.path.join(self.root, "My Games", "Starfield")
        write(os.path.join(mg, "Data", "meshes", "x.nif"))
        r = self.run_detect(my_games=mg)
        self.assertTrue(r["ready"], r["refusals"])
        self.assertEqual(r["my_games"]["loose_files"], 1)
        self.assertEqual(r["my_games"]["loose_sample"], ["meshes/x.nif"])
        self.assertTrue(any("loose files" in w for w in r["warnings"]))
        self.assertTrue(any("not found" in w for w in self.run_detect(my_games=mg + "x")["warnings"]))

    def test_archive_versions_and_duplicates_reported(self):
        write(os.path.join(self.fo4, "Fallout4 - Meshes.ba2"), b"BTDX\x01\x00\x00\x00GNRL")
        other = os.path.join(self.root, "depot2", "Data")
        write(os.path.join(other, "Fallout4 - Meshes.ba2"), b"BTDX\x08\x00\x00\x00GNRL")
        r = detect.detect(fo4_data=[self.fo4, other], starfield=self.sf, sources=self.table, runtimes=self.runtimes)
        self.assertTrue(r["ready"], r["refusals"])
        self.assertEqual(r["fo4"]["ba2_versions"], {"8": 1})
        self.assertEqual(len(r["fo4"]["archive_duplicates"]["Fallout4 - Meshes.ba2"]), 2)
        self.assertTrue(any("v8 x1" in w for w in r["warnings"]))
        self.assertTrue(any("found 2 times" in w for w in r["warnings"]))
        r = self.run_detect(my_games=self.my_games)
        self.assertEqual(r["fo4"]["ba2_versions"], {"1": 1})
        self.assertEqual(r["warnings"], [])

    def test_one_data_folder_named_twice_is_read_once(self):
        write(os.path.join(self.fo4, "Fallout4 - Meshes.ba2"), b"BTDX\x01\x00\x00\x00GNRL")
        twice = [self.fo4, self.fo4 + os.sep, self.fo4.upper()]          # the owner's list named each depot twice
        with mock.patch("os.path.normcase", str.upper):                   # Windows ignores case, on any machine
            with mock.patch.object(detect.mf, "fo4_inputs", wraps=detect.mf.fo4_inputs) as read:
                r = detect.detect(fo4_data=twice, starfield=self.sf, sources=self.table, runtimes=self.runtimes)
        self.assertEqual(read.call_args[0][0], [self.fo4])
        self.assertEqual(r["fo4"]["archive_duplicates"], {})
        self.assertFalse(any("times" in w for w in r["warnings"]), r["warnings"])

    def test_no_fallout4(self):
        r = detect.detect(fo4_data=[self.root], starfield=self.sf, sources=self.table)
        self.assertFalse(r["ready"])
        self.assertTrue(r["refusals"][0].startswith("Fallout 4:"))

    def test_sources_add_skips_duplicates(self):
        n = detect.add_sources(self.table, {"fo4": manifest.fo4_inputs([self.fo4])}, "again")
        self.assertEqual(n, 0)
        self.assertEqual(len(self.table["sources"]), 7)

    def test_shipped_table_loads_with_well_formed_entries(self):
        t = detect.load_sources(os.path.join(ROOT, "scripts", "launcher_recipes", "known_sources.json"))
        self.assertIn("Fallout4.esm", {s["file"] for s in t["sources"]})
        for s in t["sources"]:
            self.assertRegex(s["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(s["label"])

    def test_cli(self):
        spec = importlib.util.spec_from_file_location("launcher_cli", os.path.join(ROOT, "scripts", "launcher.py"))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        table = os.path.join(self.root, "sources.json")
        rts = os.path.join(self.root, "runtimes.json")
        man = os.path.join(self.root, "m.json")
        det = ["detect", "--fo4-data", self.fo4, "--starfield", self.sf, "--table", table, "--runtimes", rts]
        self.assertEqual(cli.main(["manifest", "--out", man, "--fo4-data", self.fo4, "--starfield", self.sf]), 0)
        self.assertEqual(cli.main(det), 1)
        self.assertEqual(cli.main(["sources-add", "--manifest", man, "--label", "x", "--table", table]), 0)
        self.assertEqual(cli.main(det), 1)                                  # the runtime is not listed yet
        self.assertEqual(cli.main(det + ["--allow-unknown-runtime"]), 0)
        self.assertEqual(cli.main(["runtimes-add", "--manifest", man, "--label", "y", "--table", rts]), 0)
        self.assertEqual(cli.main(det), 0)
        self.assertEqual(cli.main(["measure", self.fo4]), 0)


class MeasureTests(unittest.TestCase):
    def test_hard_links_counted_once_and_outside_links_shared(self):
        with tempfile.TemporaryDirectory() as t:
            work, out = os.path.join(t, "work"), os.path.join(t, "out")
            write(os.path.join(work, "big.bin"), b"a" * 1000)
            write(os.path.join(out, "own.bin"), b"b" * 100)
            os.makedirs(os.path.join(out, "Data"))
            os.link(os.path.join(work, "big.bin"), os.path.join(out, "Data", "big.bin"))
            os.link(os.path.join(out, "own.bin"), os.path.join(out, "Data", "own_again.bin"))
            m = detect.measure(out)
            self.assertEqual(m["files"], 3)
            self.assertEqual(m["bytes_listed"], 1200)
            self.assertEqual(m["bytes_unique"], 1100)
            self.assertEqual(m["bytes_shared"], 1000)          # big.bin is also held by work/
            self.assertEqual(m["frees_if_deleted"], 100)


if __name__ == "__main__":
    unittest.main()
