"""bridge_install.py: the bridge's own deployment record, Plugins.txt line and uninstall (a temp game folder, a temp
LOCALAPPDATA, the archive builder replaced by a stub; no game, no Archive2)."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ba2_fixture import archive_from_tree, general_archive

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

    def test_legacy_untracked_partial_file_keeps_its_recovery_record(self):
        write(os.path.join(self.data, bridge_install.PLUGIN), b"partial old copy")
        record = {"dir": self.staged, "plugin": bridge_install.PLUGIN,
                  "source_sha256": {}, "files": {}, "complete": False}
        bridge_install.deployment.write_manifest(os.path.join(self.data, bridge_install.RECORD), record)
        with self.assertRaises(SystemExit):
            bridge_install.uninstall(self.a)
        self.assertTrue(self.record()['cleanup_pending'])
        self.assertEqual(Path(self.data, bridge_install.PLUGIN).read_bytes(), b"partial old copy")

    def test_unconfirmed_partial_publication_retains_intent_and_journal(self):
        def partial(src, dst, expected_sha256=None):
            write(dst, b"partial synthetic copy")
            raise OSError("copy interrupted")
        with patch.object(bridge_install.deployment, 'copy_new_artifact', side_effect=partial):
            with self.assertRaisesRegex(OSError, 'copy interrupted'):
                bridge_install.install(self.a)
        record = self.record()
        self.assertFalse(record['complete'])
        self.assertTrue(record['cleanup_pending'])
        self.assertIn(bridge_install.PLUGIN, record['files'])
        self.assertEqual(Path(self.data, bridge_install.PLUGIN).read_bytes(), b"partial synthetic copy")
        self.assertEqual(self.lines(), ['# header', '*FO4Port.esm'])

    def test_second_copy_failure_rolls_back_confirmed_first_publication(self):
        real = bridge_install.deployment.copy_new_artifact
        def fail_archive(src, dst, expected_sha256=None):
            if os.path.basename(dst) == bridge_install.ARCHIVE:
                raise OSError('archive copy interrupted')
            return real(src, dst, expected_sha256)
        original = Path(self.plugins).read_bytes()
        with patch.object(bridge_install.deployment, 'copy_new_artifact', side_effect=fail_archive):
            with self.assertRaisesRegex(OSError, 'archive copy interrupted'):
                bridge_install.install(self.a)
        self.assertEqual(os.listdir(self.data), [])
        self.assertEqual(Path(self.plugins).read_bytes(), original)

    def test_target_created_at_publication_is_preserved(self):
        real_link = bridge_install.deployment.os.link
        def race(src, dst):
            write(dst, b'foreign concurrent file')
            return real_link(src, dst)
        with patch.object(bridge_install.deployment.os, 'link', side_effect=race):
            with self.assertRaises(FileExistsError):
                bridge_install.install(self.a)
        self.assertEqual(Path(self.data, bridge_install.PLUGIN).read_bytes(), b'foreign concurrent file')
        self.assertFalse(Path(self.data, bridge_install.RECORD).exists())
        self.assertEqual(self.lines(), ['# header', '*FO4Port.esm'])

    def test_corrupted_temporary_copy_is_not_published(self):
        def corrupt(src, dst):
            write(dst, b'corrupt copy')
        with patch.object(bridge_install.deployment.shutil, 'copyfile', side_effect=corrupt):
            with self.assertRaisesRegex(OSError, 'copy differs'):
                bridge_install.install(self.a)
        self.assertEqual(os.listdir(self.data), [])

    def test_source_drift_during_packing_refuses_before_publication(self):
        real_build = exp_install.build_ba2
        def drift(*args):
            archive = real_build(*args)
            write(os.path.join(self.staged, bridge_install.PEX), b'changed during packing')
            return archive
        with patch.object(exp_install, 'build_ba2', side_effect=drift):
            with self.assertRaisesRegex(OSError, 'source changed'):
                bridge_install.install(self.a)
        self.assertEqual(os.listdir(self.data), [])

    def test_wrong_archive_payload_refuses_before_publication(self):
        def wrong(a, root, out):
            write(out, general_archive({'Scripts/FO4SF_Bridge.pex': b'wrong script'}))
            return out
        with patch.object(exp_install, 'build_ba2', side_effect=wrong):
            with self.assertRaisesRegex(ValueError, 'differs from pinned input'):
                bridge_install.install(self.a)
        self.assertEqual(os.listdir(self.data), [])

    def test_activation_then_failure_restores_exact_original_bytes(self):
        original = b'\xef\xbb\xbf# owner\r\nFO4SFBridge.esm\r\n*FO4Port.esm\r\n'
        write(self.plugins, original)
        real_write = exp_install.write_plugins
        def activate_then_fail(*args):
            real_write(*args)
            raise OSError('activation interrupted')
        with patch.object(exp_install, 'write_plugins', side_effect=activate_then_fail):
            with self.assertRaisesRegex(OSError, 'activation interrupted'):
                bridge_install.install(self.a)
        self.assertEqual(Path(self.plugins).read_bytes(), original)
        self.assertEqual(os.listdir(self.data), [])

    def test_complete_receipt_missing_one_file_cannot_authorize_relaunch(self):
        bridge_install.install(self.a)
        record = self.record()
        record['files'].pop(bridge_install.ARCHIVE)
        bridge_install.deployment.write_manifest(os.path.join(self.data, bridge_install.RECORD), record)
        with self.assertRaises(SystemExit):
            bridge_install.install(self.a)
        with self.assertRaises(SystemExit):
            bridge_install.uninstall(self.a)
        self.assertTrue(self.record()['cleanup_pending'])
        self.assertTrue(Path(self.data, bridge_install.ARCHIVE).exists())

    def test_legacy_complete_ownership_survives_interrupted_reactivation(self):
        bridge_install.install(self.a)
        record = self.record()
        record.pop('schema')
        record.pop('published_files')
        bridge_install.deployment.write_manifest(os.path.join(self.data, bridge_install.RECORD), record)
        write(self.plugins, b'*FO4Port.esm\r\n')
        original = Path(self.plugins).read_bytes()
        real_write = exp_install.write_plugins
        def activate_then_fail(*args):
            real_write(*args)
            raise OSError('reactivation interrupted')
        with patch.object(exp_install, 'write_plugins', side_effect=activate_then_fail):
            with self.assertRaisesRegex(OSError, 'reactivation interrupted'):
                bridge_install.install(self.a)
        self.assertFalse(self.record()['complete'])
        bridge_install.uninstall(self.a)
        self.assertEqual(os.listdir(self.data), [])
        self.assertEqual(Path(self.plugins).read_bytes(), original)

    def test_incomplete_recovery_refuses_a_different_current_profile(self):
        bridge_install.install(self.a)
        record = self.record()
        record['complete'] = False
        bridge_install.deployment.write_manifest(os.path.join(self.data, bridge_install.RECORD), record)
        first_profile = Path(self.plugins).read_bytes()
        other = Path(self.tmp.name) / 'other-profile' / 'Plugins.txt'
        write(other, b'# different profile\n')
        with patch.object(exp_install, 'plugins_txt', return_value=str(other)):
            with self.assertRaisesRegex(ValueError, 'current user path'):
                bridge_install.uninstall(self.a)
        self.assertEqual(Path(self.plugins).read_bytes(), first_profile)
        self.assertEqual(other.read_bytes(), b'# different profile\n')
        self.assertTrue(Path(self.data, bridge_install.PLUGIN).exists())
        self.assertTrue(Path(self.data, bridge_install.RECORD).exists())

    def test_uninstall_retry_does_not_duplicate_restored_inactive_lines(self):
        original = b'# header\r\n*FO4Port.esm\r\nFO4SFBridge.esm\r\n'
        write(self.plugins, original)
        bridge_install.install(self.a)
        real_write = exp_install.write_plugins
        def restored_then_interrupted(*args):
            real_write(*args)
            raise OSError('deactivation interrupted')
        with patch.object(exp_install, 'write_plugins', side_effect=restored_then_interrupted):
            with self.assertRaises(SystemExit):
                bridge_install.uninstall(self.a)
        self.assertTrue(self.record()['cleanup_pending'])
        bridge_install.uninstall(self.a)
        self.assertEqual(Path(self.plugins).read_bytes(), original)
        self.assertEqual(self.lines().count('FO4SFBridge.esm'), 1)
        self.assertEqual(os.listdir(self.data), [])


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
