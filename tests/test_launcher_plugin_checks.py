"""Master checks on built plugins (src/fo4sf/launcher/plugin_checks.py) on synthetic plugins; no game files."""
import importlib.util
import os
import struct
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf.launcher import plugin_checks  # noqa: E402


def plugin(masters=(), records=b""):
    subs = b"HEDR" + struct.pack("<H", 12) + struct.pack("<fII", 0.96, 0, 0x800)
    for m in masters:
        n = m.encode() + b"\0"
        subs += b"MAST" + struct.pack("<H", len(n)) + n + b"DATA" + struct.pack("<H", 8) + b"\0" * 8
    return b"TES4" + struct.pack("<IIIIHH", len(subs), 1, 0, 0, 0, 0) + subs + records


class PluginCheckTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.build = os.path.join(t.name, "build")
        self.data = os.path.join(t.name, "Starfield", "Data")
        os.makedirs(self.build)
        os.makedirs(self.data)
        for n in ("Starfield.esm", "Constellation.esm", "BlueprintShips-Starfield.esm"):
            self.write(self.data, n, plugin())

    def write(self, folder, name, data):
        with open(os.path.join(folder, name), "wb") as f:
            f.write(data)

    def test_ordered_masters_from_the_header_only(self):
        self.write(self.build, "Core.esm", plugin(["Starfield.esm", "Constellation.esm"], records=b"GRUP" + b"\0" * 20))
        self.assertEqual(plugin_checks.masters(os.path.join(self.build, "Core.esm")),
                         ["Starfield.esm", "Constellation.esm"])

    def test_clean_build_passes(self):
        self.write(self.build, "Core.esm", plugin(["Starfield.esm", "Constellation.esm"]))
        self.write(self.build, "Mission.esm", plugin(["Starfield.esm", "Core.esm"]))
        r = plugin_checks.check(self.build, self.data)
        self.assertEqual(r["problems"], [])
        self.assertEqual(r["plugins"]["Mission.esm"], ["Starfield.esm", "Core.esm"])

    def test_blueprint_master_is_refused_even_though_the_game_has_it(self):
        self.write(self.build, "Core.esm", plugin(["Starfield.esm", "BlueprintShips-Starfield.esm"]))
        r = plugin_checks.check(self.build, self.data)
        self.assertEqual(len(r["problems"]), 1)
        self.assertIn("BlueprintShips-Starfield.esm as a master", r["problems"][0])

    def test_unknown_and_self_masters(self):
        self.write(self.build, "Core.esm", plugin(["Starfield.esm", "Elsewhere.esm", "Core.esm"]))
        r = plugin_checks.check(self.build, self.data)
        self.assertTrue(any("Elsewhere.esm is neither" in p for p in r["problems"]))
        self.assertTrue(any("lists itself" in p for p in r["problems"]))
        self.assertEqual(len(plugin_checks.check(self.build, self.data, also=["Elsewhere.esm"])["problems"]), 1)

    def test_without_the_data_folder_only_starfield_esm_is_given(self):
        self.write(self.build, "Core.esm", plugin(["Starfield.esm", "Constellation.esm"]))
        r = plugin_checks.check(self.build)
        self.assertEqual(r["problems"], ["Core.esm: master Constellation.esm is neither a Starfield master nor in this build"])

    def test_not_a_plugin_and_truncated_header(self):
        self.write(self.build, "Bad.esm", b"nope")
        self.write(self.build, "Cut.esm", plugin(["Starfield.esm"])[:30])
        r = plugin_checks.check(self.build, self.data)
        self.assertEqual(len(r["problems"]), 2)

    def test_cli(self):
        spec = importlib.util.spec_from_file_location("launcher_cli", os.path.join(ROOT, "scripts", "launcher.py"))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        self.write(self.build, "Core.esm", plugin(["Starfield.esm"]))
        self.assertEqual(cli.main(["check-plugins", self.build, "--starfield-data", self.data]), 0)
        self.write(self.build, "Core.esm", plugin(["BlueprintShips-Starfield.esm"]))
        self.assertEqual(cli.main(["check-plugins", self.build, "--starfield-data", self.data]), 1)


if __name__ == "__main__":
    unittest.main()
