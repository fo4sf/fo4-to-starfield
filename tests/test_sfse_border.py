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

    def test_the_value_offset_is_the_one_the_probe_found(self):
        # Card A on the PC (2026-10-24): the byte 16 before the name pointer followed SetINI 0 and 1 (border.md)
        ini = (PLUGIN / "FO4SFBorder.ini").read_text(encoding="utf-8")
        self.assertRegex(ini, r"(?m)^ValueOffset=-16$")
        self.assertIn("int g_value_offset = -16;", self.cpp)
        # GetPrivateProfileInt returns 0 for a negative ini value, so -16 must be read as text.
        self.assertIn('GetPrivateProfileStringW(L"FO4SFBorder", L"ValueOffset", L"-16",', self.cpp)
        self.assertNotIn('GetPrivateProfileIntW(L"FO4SFBorder", L"ValueOffset"', self.cpp)
        self.assertIn("parse_value_offset(narrow(offset_text), -16, kWatchBytes)", self.cpp)
        self.assertIn("inline int parse_value_offset", self.scan)

    def test_game_memory_is_read_only_through_read_process_memory(self):
        # the worker has no SEH (mingw): a page freed or reprotected after VirtualQuery must fail a read, not crash
        # the game (Grok on #522). Regions carry no live pointer, and no code dereferences the value byte.
        self.assertIn("ReadProcessMemory(GetCurrentProcess()", self.cpp)
        self.assertIn("base + at), nullptr, len, writable", self.cpp)
        for deref in ("*addr_", "*value", "reinterpret_cast<const std::uint8_t*>(ptr"):
            self.assertNotIn(deref, self.cpp)
        run = self.cpp[self.cpp.index("void Run() override"):self.cpp.index("void Destroy()")]
        self.assertLess(run.index("before > 1"), run.index("WriteProcessMemory"))   # checked again at write time

    def test_an_unfinished_line_is_carried_to_the_next_read(self):
        self.assertIn("fo4sfborder::complete_lines(t.carry, buf)", self.cpp)
        self.assertIn("std::string carry;", self.cpp)

    def test_no_sfse_header_or_binary_in_the_repo(self):
        tracked = subprocess.run(["git", "ls-files", "sfse/FO4SFBorder"], cwd=ROOT, capture_output=True,
                                 text=True, check=True).stdout.split()
        self.assertFalse([f for f in tracked if f.endswith(("PluginAPI.h", ".dll"))])
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("sfse/FO4SFBorder/PluginAPI.h", ignore)


if __name__ == "__main__":
    unittest.main()
