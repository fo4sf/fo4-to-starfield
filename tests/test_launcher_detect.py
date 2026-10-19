"""Launcher detect stage and disk measure (src/fo4sf/launcher/detect.py) on synthetic folders; no game files."""
import importlib.util
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf.launcher import detect, manifest  # noqa: E402

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
        write(os.path.join(self.sf, "sfse_loader.exe"), b"MZ")
        os.makedirs(os.path.join(self.sf, "Data"), exist_ok=True)
        self.table = {"schema": 1, "sources": []}
        detect.add_sources(self.table, {"fo4": manifest.fo4_inputs([self.fo4])}, "test install")

    def run_detect(self, **kw):
        kw.setdefault("sources", self.table)
        return detect.detect(fo4_data=[self.fo4], starfield=self.sf, **kw)

    def test_ready_when_everything_is_known(self):
        r = self.run_detect(out_dir=self.root, need_gb=0, floor_gb=0)
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

    def test_archive2_required_ck_and_sfse_optional(self):
        os.remove(os.path.join(self.sf, "Tools", "Archive2", "Archive2.exe"))
        os.remove(os.path.join(self.sf, "CreationKit.exe"))
        os.remove(os.path.join(self.sf, "sfse_loader.exe"))
        r = self.run_detect()
        self.assertTrue(any("Archive2" in x for x in r["refusals"]))
        self.assertEqual(len(r["refusals"]), 1)
        self.assertEqual(len(r["warnings"]), 2)
        r = self.run_detect(require_ck=True, require_sfse=True)
        self.assertEqual(len(r["refusals"]), 3)

    def test_disk_floor(self):
        r = self.run_detect(out_dir=os.path.join(self.root, "not", "yet"), need_gb=10 ** 9, floor_gb=40)
        self.assertFalse(r["ready"])
        self.assertTrue(any(x.startswith("Disk:") for x in r["refusals"]))

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
        man = os.path.join(self.root, "m.json")
        self.assertEqual(cli.main(["manifest", "--out", man, "--fo4-data", self.fo4]), 0)
        self.assertEqual(cli.main(["detect", "--fo4-data", self.fo4, "--starfield", self.sf, "--table", table]), 1)
        self.assertEqual(cli.main(["sources-add", "--manifest", man, "--label", "x", "--table", table]), 0)
        self.assertEqual(cli.main(["detect", "--fo4-data", self.fo4, "--starfield", self.sf, "--table", table]), 0)
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
