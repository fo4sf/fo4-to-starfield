"""Synthetic uninstall interruption receipts; no game or owner settings."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_deployment import deploy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'game'))
import exp_install


class CleanupJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / 'Data'
        self.data.mkdir()
        self.plugin = self.data / deploy.PLUGIN
        self.archive = self.data / deploy.ARCHIVE
        self.plugin.write_bytes(b'TES4 synthetic plugin')
        self.archive.write_bytes(b'BTDX synthetic archive')
        self.plugins = self.root / 'Plugins.txt'
        self.plugins.write_bytes(b'*Owner.esm\n*FO4Port.esm\n')
        self.receipt = self.data / deploy.MANIFEST
        self.state = dict(complete=True, files=[deploy.PLUGIN, deploy.ARCHIVE],
                          published_files=[deploy.PLUGIN, deploy.ARCHIVE],
                          artifacts={p.name: deploy.artifact_identity(p) for p in (self.plugin, self.archive)},
                          plugins_txt=str(self.plugins), plugins_added=['*FO4Port.esm'],
                          plugins_replaced=[], plugins_restore_pending=True)
        deploy.write_manifest(str(self.receipt), self.state)
        self.args = SimpleNamespace(starfield=str(self.root), dry_run=False)

    def uninstall(self):
        with patch.object(deploy, 'plugins_txt_path', return_value=str(self.plugins)), contextlib.redirect_stdout(io.StringIO()):
            deploy.uninstall(self.args)

    def test_partial_uninstall_is_blocked_by_existing_experiment_gate(self):
        self.archive.write_bytes(b'changed owner archive')
        with self.assertRaisesRegex(SystemExit, 'uninstall incomplete'):
            self.uninstall()
        self.assertFalse(self.plugin.exists())
        receipt = json.loads(self.receipt.read_text())
        self.assertTrue(receipt.get('cleanup_pending'))
        self.assertTrue(receipt['complete'])  # install provenance still controls config restoration
        with self.assertRaisesRegex(ValueError, 'incomplete FO4Port deployment'):
            exp_install.require_complete_master(str(self.data))
        self.assertEqual(self.plugins.read_bytes(), b'*Owner.esm\n')
        self.archive.write_bytes(b'BTDX synthetic archive')
        self.uninstall()
        self.assertFalse(self.receipt.exists())
        self.assertFalse(self.archive.exists())

    def test_process_interruption_after_first_removal_keeps_pending_receipt(self):
        original_remove = deploy.os.remove

        def interrupted(path):
            if Path(path) == self.archive:
                raise KeyboardInterrupt('synthetic process interruption')
            original_remove(path)

        with patch.object(deploy.os, 'remove', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.uninstall()
        self.assertFalse(self.plugin.exists())
        self.assertTrue(json.loads(self.receipt.read_text()).get('cleanup_pending'))
        with self.assertRaisesRegex(ValueError, 'incomplete FO4Port deployment'):
            exp_install.require_complete_master(str(self.data))
        self.uninstall()
        self.assertFalse(self.receipt.exists())
        self.assertEqual(self.plugins.read_bytes(), b'*Owner.esm\n')

    def test_journal_write_failure_prevents_any_cleanup(self):
        before = {p: p.read_bytes() for p in (self.plugin, self.archive, self.plugins, self.receipt)}
        with patch.object(deploy, 'write_manifest', side_effect=OSError('journal unavailable')):
            with self.assertRaisesRegex(OSError, 'journal unavailable'):
                self.uninstall()
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_dry_run_does_not_mark_or_mutate(self):
        before = {p: p.read_bytes() for p in (self.plugin, self.archive, self.plugins, self.receipt)}
        self.args.dry_run = True
        self.uninstall()
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_healthy_complete_install_keeps_restore_ownership_until_uninstall(self):
        exp_install.require_complete_master(str(self.data))
        self.uninstall()
        self.assertFalse(self.receipt.exists())
        self.assertEqual(self.plugins.read_bytes(), b'*Owner.esm\n')


if __name__ == '__main__':
    unittest.main()
