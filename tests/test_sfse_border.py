"""FO4SFBorder (sfse/FO4SFBorder): the scan and signal rules, compiled and run here, and the contract between the
plugin and FO4SF_MapMarkers' border lines (docs/terrain/border.md, "Per-world switch")."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "sfse" / "FO4SFBorder"
SCRIPT = ROOT / "scripts" / "mapmarkers" / "FO4SF_MapMarkers.psc"


class ScanTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++"), "g++ not installed")
    def test_scan_and_signal_rules(self):
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / "scan_test"
            subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I", str(PLUGIN),
                            str(ROOT / "tests" / "sfse_border_scan_test.cpp"), "-o", str(exe)], check=True)
            out = subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout
        self.assertIn("all passed", out)


class ContractTests(unittest.TestCase):
    cpp = (PLUGIN / "FO4SFBorder.cpp").read_text(encoding="utf-8")
    scan = (PLUGIN / "scan.h").read_text(encoding="utf-8")
    psc = SCRIPT.read_text(encoding="utf-8")

    def test_the_script_writes_the_tokens_the_plugin_reads(self):
        for token in ("border=off", "border=on"):
            self.assertIn(f'"{token}"', self.scan)
            self.assertIn(f'Trace("{token} ', self.psc)
        # the plugin tails the log the script opens
        self.assertIn('string LogName = "fo4sf_map"', self.psc)
        self.assertIn("fo4sf_map.0.log", self.cpp)

    def test_the_signal_is_written_on_change_and_again_each_session(self):
        border = self.psc[self.psc.index("Function Border"):self.psc.index("Function Trace")]
        self.assertIn("if want != border", border)
        self.assertIn("rt < lastRealTime", border)                   # a new session clears the state
        self.assertLess(border.index("rt < lastRealTime"), border.index("IsInInterior"))
        self.assertIn("border = -1", border)
        # indoors keeps the last state (the return comes before any write)
        self.assertLess(border.index("IsInInterior"), border.index("want = 1"))
        place = self.psc[self.psc.index("Function Place"):self.psc.index("Function Border")]
        self.assertLess(place.index("Border(player)"), place.index("IsInInterior"))

    def test_our_world_is_the_cores_cells_and_their_runtime_world(self):
        border = self.psc[self.psc.index("Function Border"):self.psc.index("Function Trace")]
        self.assertIn("Markers[0].GetFormID() / 16777216", border)
        self.assertIn("c.GetFormID() / 16777216 == core", border)
        self.assertIn("ourWorld = w", border)
        self.assertIn("w == ourWorld", border)

    def test_the_plugin_has_a_kill_switch_and_refuses_unsure_writes(self):
        self.assertIn('L"Mode"', self.cpp)
        self.assertRegex(self.cpp, r'GetPrivateProfileIntW\(L"FO4SFBorder", L"Mode", 0,')    # off unless set
        ini = (PLUGIN / "FO4SFBorder.ini").read_text(encoding="utf-8")
        self.assertRegex(ini, r"(?m)^Mode=0$")
        self.assertIn("kStructureIndependence_1_14_70_Layout", self.cpp)

    def test_no_sfse_header_or_binary_in_the_repo(self):
        tracked = subprocess.run(["git", "ls-files", "sfse/FO4SFBorder"], cwd=ROOT, capture_output=True,
                                 text=True, check=True).stdout.split()
        self.assertFalse([f for f in tracked if f.endswith(("PluginAPI.h", ".dll"))])
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("sfse/FO4SFBorder/PluginAPI.h", ignore)


if __name__ == "__main__":
    unittest.main()
