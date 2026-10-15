"""bridge_install.py: the bridge's own deployment record, Plugins.txt line and uninstall (a temp game folder, a temp
LOCALAPPDATA, the archive builder replaced by a stub; no game, no Archive2)."""
import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "game"))
import bridge_install  # noqa: E402
import exp_install  # noqa: E402


def write(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


class BridgeInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.game = os.path.join(root, "game")
        self.data = os.path.join(self.game, "Data")
        os.makedirs(self.data)
        self.staged = os.path.join(root, "bridge_t0")
        write(os.path.join(self.staged, bridge_install.PLUGIN), b"TES4-bridge-plugin")
        write(os.path.join(self.staged, bridge_install.PEX), b"pex")
        self.local = os.path.join(root, "local")
        os.makedirs(os.path.join(self.local, "Starfield"))
        self.plugins = os.path.join(self.local, "Starfield", "Plugins.txt")
        write(self.plugins, b"# header\r\n*FO4Port.esm\r\n")
        self.old_local = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = self.local
        self.old_build = exp_install.build_ba2

        def stub_build(a, root_dir, out):
            self.assertTrue(os.path.isdir(os.path.join(root_dir, "Scripts")))
            write(out, b"BTDX-stub")
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

    def record(self):
        with open(os.path.join(self.data, bridge_install.RECORD), encoding="utf-8") as f:
            return json.load(f)

    def test_install_records_files_and_activates_the_plugin_last(self):
        bridge_install.install(self.a)
        self.assertTrue(os.path.exists(os.path.join(self.data, bridge_install.PLUGIN)))
        self.assertTrue(os.path.exists(os.path.join(self.data, bridge_install.ARCHIVE)))
        rec = self.record()
        self.assertTrue(rec["complete"])
        self.assertEqual(sorted(rec["files"]), sorted([bridge_install.PLUGIN, bridge_install.ARCHIVE]))
        self.assertEqual(self.lines(), ["# header", "*FO4Port.esm", "*FO4SFBridge.esm"])

    def test_second_install_is_a_no_op_and_reactivates_after_a_rewrite(self):
        bridge_install.install(self.a)
        bridge_install.install(self.a)                        # same staged bridge: nothing changes
        self.assertEqual(self.lines().count("*FO4SFBridge.esm"), 1)
        write(self.plugins, b"*FO4Port.esm\r\n")              # a deploy rewrote Plugins.txt without our line
        bridge_install.install(self.a)
        self.assertEqual(self.lines(), ["*FO4Port.esm", "*FO4SFBridge.esm"])
        self.assertTrue(self.record()["complete"])

    def test_a_different_bridge_is_refused_until_uninstalled(self):
        bridge_install.install(self.a)
        write(os.path.join(self.staged, bridge_install.PEX), b"pex-v2")
        with self.assertRaises(SystemExit):
            bridge_install.install(self.a)
        bridge_install.uninstall(self.a)
        bridge_install.install(self.a)
        self.assertEqual(self.record()["source_sha256"][bridge_install.PEX], exp_install.digest(
            os.path.join(self.staged, bridge_install.PEX)))

    def test_uninstall_removes_only_what_it_added(self):
        write(self.plugins, b"*FO4Port.esm\r\nFO4SFBridge.esm\r\n")   # an inactive line from before: put back after
        bridge_install.install(self.a)
        self.assertEqual(self.lines(), ["*FO4Port.esm", "*FO4SFBridge.esm"])
        bridge_install.uninstall(self.a)
        self.assertEqual(self.lines(), ["*FO4Port.esm", "FO4SFBridge.esm"])
        self.assertFalse(os.path.exists(os.path.join(self.data, bridge_install.PLUGIN)))
        self.assertFalse(os.path.exists(os.path.join(self.data, bridge_install.ARCHIVE)))
        self.assertFalse(os.path.exists(os.path.join(self.data, bridge_install.RECORD)))

    def test_a_changed_installed_file_is_preserved_and_the_record_kept(self):
        bridge_install.install(self.a)
        write(os.path.join(self.data, bridge_install.PLUGIN), b"someone edited this")
        with self.assertRaises(SystemExit):
            bridge_install.uninstall(self.a)
        self.assertTrue(os.path.exists(os.path.join(self.data, bridge_install.PLUGIN)))
        self.assertFalse(os.path.exists(os.path.join(self.data, bridge_install.ARCHIVE)))
        self.assertTrue(self.record().get("cleanup_pending"))

    def test_existing_game_files_are_never_overwritten(self):
        write(os.path.join(self.data, bridge_install.ARCHIVE), b"not ours")
        with self.assertRaises(SystemExit):
            bridge_install.install(self.a)
        self.assertFalse(os.path.exists(os.path.join(self.data, bridge_install.RECORD)))


if __name__ == "__main__":
    unittest.main()


class OrderTests(BridgeInstallTests):
    """bridge_install.py order: the bridge's line goes last right before launch (cave_core64c_1015 a1: it sat first and
    shifted every experiment's load index)."""
    def test_order_moves_the_bridge_last_and_is_idempotent(self):
        bridge_install.install(self.a)
        write(self.plugins, b"*FO4SFBridge.esm\r\n*FO4TerrainCore.esm\r\n*FO4Port.esm\r\n*FO4SliceRedRocketCore.esm\r\n")
        bridge_install.order(self.a)
        self.assertEqual(self.lines(), ["*FO4TerrainCore.esm", "*FO4Port.esm", "*FO4SliceRedRocketCore.esm", "*FO4SFBridge.esm"])
        bridge_install.order(self.a)                                   # already last: no change
        self.assertEqual(self.lines(), ["*FO4TerrainCore.esm", "*FO4Port.esm", "*FO4SliceRedRocketCore.esm", "*FO4SFBridge.esm"])

    def test_order_reactivates_a_missing_line(self):
        bridge_install.install(self.a)
        write(self.plugins, b"*FO4Port.esm\r\n")
        bridge_install.order(self.a)
        self.assertEqual(self.lines(), ["*FO4Port.esm", "*FO4SFBridge.esm"])

    def test_order_without_an_install_does_nothing(self):
        write(self.plugins, b"*FO4SFBridge.esm\r\n*FO4Port.esm\r\n")
        bridge_install.order(self.a)
        self.assertEqual(self.lines(), ["*FO4SFBridge.esm", "*FO4Port.esm"])
