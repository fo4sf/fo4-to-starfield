"""map_markers_install.py: the map markers plugin's own deployment record, its master gate, its Plugins.txt line and
order, and that it leaves the bridge's module alone (a temp game folder, a temp LOCALAPPDATA, the archive builder
replaced by a stub; no game, no Archive2)."""
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ba2_fixture import archive_from_tree

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "game"))
import bridge_install  # noqa: E402
import exp_install  # noqa: E402
import map_markers_install as mm  # noqa: E402


def write(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


def plugin(*masters):
    """A synthetic TES4 header with MAST/DATA pairs (the shape exp_install.plugin_masters reads)."""
    body = b""
    for m in masters:
        name = m.encode() + b"\0"
        body += b"MAST" + struct.pack("<H", len(name)) + name + b"DATA" + struct.pack("<H", 8) + b"\0" * 8
    return b"TES4" + struct.pack("<IIIIHH", len(body), 1, 0, 0, 0, 0) + body


class MapMarkersInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.game = os.path.join(root, "game")
        self.data = os.path.join(self.game, "Data")
        os.makedirs(self.data)
        write(os.path.join(self.data, "FO4TerrainCore.esm"), plugin())     # the installed core the markers master
        self.staged = os.path.join(root, "mapmarkers_v6e")
        write(os.path.join(self.staged, mm.PLUGIN), plugin("FO4TerrainCore.esm"))
        write(os.path.join(self.staged, mm.PEX), b"pex")
        self.local = os.path.join(root, "local")
        self.plugins = os.path.join(self.local, "Starfield", "Plugins.txt")
        write(self.plugins, b"# header\r\n*FO4Port.esm\r\n*FO4TerrainCore.esm\r\n*FO4SFBridge.esm\r\n")
        self.old_local = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = self.local
        self.old_build = exp_install.build_ba2

        def stub_build(a, root_dir, out):
            self.assertTrue(os.path.isfile(os.path.join(root_dir, "Scripts", "FO4SF_MapMarkers.pex")))
            write(out, archive_from_tree(Path(root_dir)))
            return out
        exp_install.build_ba2 = stub_build
        self.a = SimpleNamespace(dir=self.staged, starfield=self.game)

    def tearDown(self):
        exp_install.build_ba2 = self.old_build
        if self.old_local is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = self.old_local
        self.tmp.cleanup()

    def lines(self):
        with open(self.plugins, encoding="utf-8-sig") as f:
            return f.read().splitlines()

    def run_cmd(self, *args):
        mm.main([*args, "--starfield", self.game] + (["--dir", self.staged] if args[0] == "install" else []))

    def test_install_writes_its_own_files_record_and_line(self):
        self.run_cmd("install")
        for name in (mm.PLUGIN, mm.ARCHIVE, mm.RECORD):
            self.assertTrue(os.path.exists(os.path.join(self.data, name)), name)
        self.assertFalse(os.path.exists(os.path.join(self.data, bridge_install.RECORD)))
        with open(os.path.join(self.data, mm.RECORD), encoding="utf-8") as f:
            rec = json.load(f)
        self.assertTrue(rec["complete"])
        self.assertEqual(sorted(rec["files"]), sorted([mm.PLUGIN, mm.ARCHIVE]))
        self.assertEqual(self.lines(), ["# header", "*FO4Port.esm", "*FO4TerrainCore.esm", "*FO4SFBridge.esm",
                                        "*FO4SFMapMarkers.esm"])

    def test_install_refuses_without_an_active_core(self):
        write(self.plugins, b"*FO4Port.esm\r\nFO4TerrainCore.esm\r\n")      # the core's line is inactive
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("install")
        self.assertIn("FO4TerrainCore.esm is not active", str(cm.exception))
        self.assertEqual(os.listdir(self.data), ["FO4TerrainCore.esm"])
        self.assertEqual(self.lines(), ["*FO4Port.esm", "FO4TerrainCore.esm"])

    def test_install_refuses_an_active_core_line_without_its_file(self):
        os.remove(os.path.join(self.data, "FO4TerrainCore.esm"))          # the line is active, the file is gone
        before = Path(self.plugins).read_bytes()
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("install")
        self.assertIn("FO4TerrainCore.esm is not a readable plugin in Data", str(cm.exception))
        self.assertEqual(os.listdir(self.data), [])
        self.assertEqual(Path(self.plugins).read_bytes(), before)

    def test_install_refuses_while_the_main_build_recovers(self):
        write(os.path.join(self.data, exp_install.deployment.MANIFEST), json.dumps({"complete": False}).encode())
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("install")
        self.assertIn("incomplete FO4Port deployment", str(cm.exception))
        self.assertFalse(os.path.exists(os.path.join(self.data, mm.RECORD)))

    def test_order_refuses_to_reactivate_while_the_core_is_held(self):
        self.run_cmd("install")
        write(self.plugins, b"*FO4Port.esm\r\nFO4TerrainCore.esm\r\nFO4SFMapMarkers.esm\r\n")   # both held off
        before = Path(self.plugins).read_bytes()
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("order")
        self.assertIn("FO4TerrainCore.esm is not active", str(cm.exception))
        self.assertEqual(Path(self.plugins).read_bytes(), before)

    def test_order_refuses_when_the_core_file_is_gone(self):
        self.run_cmd("install")
        write(self.plugins, b"*FO4TerrainCore.esm\r\n*FO4SFMapMarkers.esm\r\n*FO4Port.esm\r\n")
        os.remove(os.path.join(self.data, "FO4TerrainCore.esm"))
        before = Path(self.plugins).read_bytes()
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("order")
        self.assertIn("not a readable plugin in Data", str(cm.exception))
        self.assertEqual(Path(self.plugins).read_bytes(), before)

    def test_order_reactivates_when_the_core_is_active(self):
        self.run_cmd("install")
        write(self.plugins, b"*FO4TerrainCore.esm\r\n*FO4Port.esm\r\n")     # a deploy dropped the markers line
        self.run_cmd("order")
        self.assertEqual(self.lines(), ["*FO4TerrainCore.esm", "*FO4Port.esm", "*FO4SFMapMarkers.esm"])

    def test_order_puts_it_last_then_the_bridge_goes_after_it(self):
        self.run_cmd("install")
        write(self.plugins, b"*FO4TerrainCore.esm\r\n*FO4SFMapMarkers.esm\r\n*FO4Port.esm\r\n")  # a deploy appended FO4Port
        self.run_cmd("order")
        self.assertEqual(self.lines(), ["*FO4TerrainCore.esm", "*FO4Port.esm", "*FO4SFMapMarkers.esm"])

    def test_uninstall_removes_only_what_it_added(self):
        self.run_cmd("install")
        self.run_cmd("uninstall")
        self.assertEqual(os.listdir(self.data), ["FO4TerrainCore.esm"])
        self.assertEqual(self.lines(), ["# header", "*FO4Port.esm", "*FO4TerrainCore.esm", "*FO4SFBridge.esm"])

    def test_a_different_build_is_refused_until_uninstalled(self):
        self.run_cmd("install")
        write(os.path.join(self.staged, mm.PEX), b"pex-v2")
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("install")
        self.assertIn("another map markers plugin is installed", str(cm.exception))

    def test_the_bridge_module_keeps_its_own_names(self):
        self.assertEqual((bridge_install.PLUGIN, bridge_install.RECORD, bridge_install.KIT),
                         ("FO4SFBridge.esm", "FO4SFBridge.install.json", "bridge"))
        self.assertIsNot(mm.kit, bridge_install)


class CycleOrderTests(unittest.TestCase):
    def test_cycle_orders_the_markers_before_the_bridge(self):
        text = Path(__file__).resolve().parent.parent.joinpath("scripts", "game", "cycle.ps1").read_text(encoding="utf-8")
        markers = text.index("map_markers_install.py\" order")
        self.assertLess(text.index("FO4SFExp.install.json"), markers)
        self.assertLess(markers, text.index("bridge_install.py\" order"))
        block = text[markers:text.index("bridge_install.py\" order")]
        self.assertIn("$mmCode = $LASTEXITCODE", block)                   # a refused order stops the launch
        self.assertIn("exit 7", block)


if __name__ == "__main__":
    unittest.main()
