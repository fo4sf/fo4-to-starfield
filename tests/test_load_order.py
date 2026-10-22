"""load_order (scripts/game/load_order.py): the one target order for our plugins, on synthetic files only."""
import os
import struct
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import load_order  # noqa: E402

# the order the game wrote on the owner's PC, 2026-10-22, 25 s after a start (Install thread)
GAME = ["FO4TerrainCore.esm", "FO4TerrainCore_Mars.esm", "FO4ActorRaider.esm", "FO4SFMission.esm", "FO4Port.esm",
        "FO4SFMapMarkers.esm", "FO4SFBridge.esm"]
MASTERS = {"FO4TerrainCore_Mars.esm": ["FO4TerrainCore.esm"], "FO4SFMapMarkers.esm": ["FO4TerrainCore.esm"],
           "FO4SFMission.esm": ["Starfield.esm"]}


def plugin(path, masters=()):
    sub = b"".join(b"MAST" + struct.pack("<H", len(m) + 1) + m.encode() + b"\0" for m in masters)
    with open(path, "wb") as f:
        f.write(b"TES4" + struct.pack("<I", len(sub)) + b"\0" * 16 + sub)


class LoadOrderTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.game = os.path.join(t.name, "Starfield")
        self.data = os.path.join(self.game, "Data")
        os.makedirs(self.data)
        for p in GAME:
            plugin(os.path.join(self.data, p), MASTERS.get(p, ()))
        self.txt = os.path.join(t.name, "Plugins.txt")
        self.said = []

    def write(self, lines, bom=b"\xef\xbb\xbf", nl="\r\n"):
        with open(self.txt, "wb") as f:
            f.write(bom + (nl.join(lines) + nl).encode())

    def run_(self, cmd):
        return load_order.run(cmd, self.game, plugins_txt=self.txt, say=self.said.append)

    def read(self):
        with open(self.txt, "rb") as f:
            return f.read()

    def test_the_order_the_game_wrote_is_the_target(self):
        self.write(["# This file is used by the game", "*Other.esm"] + ["*" + p for p in GAME])
        before = self.read()
        self.assertEqual(self.run_("check"), 0)
        self.assertEqual(self.run_("fix"), 0)
        self.assertEqual(self.read(), before)                         # nothing written
        self.assertEqual([n for n in os.listdir(os.path.dirname(self.txt)) if ".bak-" in n], [])

    def test_the_morning_order_is_put_right_and_only_our_lines_move(self):
        # 2026-10-22 05:50 local: FO4Port first, as the map markers install recorded it
        morning = ["*FO4Port.esm", "*FO4TerrainCore.esm", "*Other.esm", "*FO4TerrainCore_Mars.esm", "*FO4ActorRaider.esm",
                   "*FO4SFMission.esm", "*FO4SFMapMarkers.esm", "FO4SFBridge.esm"]
        self.write(morning)
        old = self.read()
        self.assertEqual(self.run_("check"), 9)
        self.assertEqual(self.read(), old)                            # check never writes
        self.assertTrue(any("FO4Port.esm: line 1 -> 6" in s for s in self.said), self.said)
        self.assertEqual(self.run_("fix"), 0)
        self.assertEqual(self.read(), b"\xef\xbb\xbf" + "\r\n".join(
            ["*Other.esm", "*FO4TerrainCore.esm", "*FO4TerrainCore_Mars.esm", "*FO4ActorRaider.esm", "*FO4SFMission.esm",
             "*FO4Port.esm", "*FO4SFMapMarkers.esm", "FO4SFBridge.esm"]).encode() + b"\r\n")   # the bridge stays unticked
        bak = [n for n in os.listdir(os.path.dirname(self.txt)) if ".bak-" in n]
        with open(os.path.join(os.path.dirname(self.txt), bak[0]), "rb") as f:
            self.assertEqual(f.read(), old)
        self.assertEqual(self.run_("check"), 0)

    def test_a_second_fix_in_the_same_second_keeps_the_first_copy(self):
        from unittest import mock
        import datetime
        fixed = datetime.datetime(2026, 10, 22, 19, 40, 0)
        with mock.patch.object(load_order.datetime, "datetime", mock.Mock(now=mock.Mock(return_value=fixed))):
            self.write(["*FO4Port.esm"] + ["*" + p for p in GAME if p != "FO4Port.esm"])
            first = self.read()
            self.assertEqual(self.run_("fix"), 0)
            self.write(["*FO4SFBridge.esm"] + ["*" + p for p in GAME if p != "FO4SFBridge.esm"])
            self.assertEqual(self.run_("fix"), 0)
        folder = os.path.dirname(self.txt)
        baks = sorted(n for n in os.listdir(folder) if ".bak-" in n)
        self.assertEqual(len(baks), 2)
        with open(os.path.join(folder, baks[0]), "rb") as f:
            self.assertEqual(f.read(), first)

    def test_a_plugin_loads_after_its_master_whatever_its_group(self):
        plugin(os.path.join(self.data, "FO4SFMission.esm"), ["FO4Port.esm"])
        self.write(["*" + p for p in GAME])
        self.assertEqual(self.run_("fix"), 0)
        lines = self.read().decode("utf-8-sig").split()
        self.assertLess(lines.index("*FO4Port.esm"), lines.index("*FO4SFMission.esm"))

    def test_a_patch_for_our_plugins_still_loads_after_them(self):
        # Codex on #487: a plugin that is not ours but masters one of ours, or such a patch, must stay after it
        plugin(os.path.join(self.data, "PortPatch.esm"), ["FO4Port.esm"])
        plugin(os.path.join(self.data, "PatchOfPatch.esp"), ["PortPatch.esm"])
        plugin(os.path.join(self.data, "Other.esm"))
        self.write(["*FO4Port.esm", "*PortPatch.esm", "*Other.esm", "*PatchOfPatch.esp"]
                   + ["*" + p for p in GAME if p != "FO4Port.esm"])
        self.assertEqual(self.run_("fix"), 0)
        self.assertEqual(self.read().decode("utf-8-sig").split(),
                         ["*Other.esm", "*FO4TerrainCore.esm", "*FO4TerrainCore_Mars.esm", "*FO4ActorRaider.esm",
                          "*FO4SFMission.esm", "*FO4Port.esm", "*PortPatch.esm", "*PatchOfPatch.esp",
                          "*FO4SFMapMarkers.esm", "*FO4SFBridge.esm"])       # each patch right after its master
        self.assertEqual(self.run_("check"), 0)

    def test_a_chain_from_ours_through_a_patch_back_to_ours_keeps_its_masters_first(self):
        # Codex's QA on #487: Port <- PortPatch <- Mission was rewritten Mission, Port, PortPatch and then accepted
        plugin(os.path.join(self.data, "PortPatch.esm"), ["FO4Port.esm"])
        plugin(os.path.join(self.data, "FO4SFMission.esm"), ["PortPatch.esm"])
        self.write(["*FO4TerrainCore.esm", "*FO4Port.esm", "*PortPatch.esm", "*FO4SFMission.esm"])
        self.assertEqual(self.run_("check"), 0)                              # already valid and in the target
        self.write(["*FO4SFMission.esm", "*PortPatch.esm", "*FO4Port.esm", "*FO4TerrainCore.esm"])
        self.assertEqual(self.run_("fix"), 0)
        self.assertEqual(self.read().decode("utf-8-sig").split(),
                         ["*FO4TerrainCore.esm", "*FO4Port.esm", "*PortPatch.esm", "*FO4SFMission.esm"])

    def test_a_cycle_across_ours_and_a_patch_and_a_patch_missing_its_master_are_refused(self):
        plugin(os.path.join(self.data, "PortPatch.esm"), ["FO4SFMission.esm"])
        plugin(os.path.join(self.data, "FO4SFMission.esm"), ["PortPatch.esm"])
        self.write(["*FO4SFMission.esm", "*PortPatch.esm"])
        old = self.read()
        self.assertEqual(self.run_("fix"), 6)
        self.assertIn("cycle", self.said[-1])
        self.assertEqual(self.read(), old)
        plugin(os.path.join(self.data, "Lone.esm"), ["Absent.esm"])
        self.write(["*" + p for p in GAME] + ["*Lone.esm"])
        old = self.read()
        self.assertEqual(self.run_("check"), 6)
        self.assertIn("Lone.esm needs master Absent.esm", self.said[-1])
        self.assertEqual(self.run_("fix"), 6)
        self.assertEqual(self.read(), old)

    def test_what_cannot_be_judged_is_refused_and_left_alone(self):
        cases = [
            (["*" + p for p in GAME if p != "FO4TerrainCore.esm"], "needs master FO4TerrainCore.esm"),
            (["*" + p for p in GAME] + ["*FO4SFNew.esm"], "active but not in"),
            (["*" + p for p in GAME] + ["*FO4Port.esm"], "more than once"),
        ]
        for lines, text in cases:
            with self.subTest(text=text):
                self.write(lines)
                old, self.said = self.read(), []
                self.assertEqual(self.run_("fix"), 6)
                self.assertIn(text, self.said[-1])
                self.assertEqual(self.read(), old)
        plugin(os.path.join(self.data, "FO4Port.esm"), ["FO4SFMission.esm"])
        plugin(os.path.join(self.data, "FO4SFMission.esm"), ["FO4Port.esm"])
        self.write(["*" + p for p in GAME])
        self.assertEqual(self.run_("check"), 6)
        self.assertIn("cycle", self.said[-1])

    def test_no_plugins_file_is_nothing_to_order(self):
        self.assertEqual(self.run_("fix"), 0)
        self.assertFalse(os.path.exists(self.txt))


if __name__ == "__main__":
    unittest.main()
