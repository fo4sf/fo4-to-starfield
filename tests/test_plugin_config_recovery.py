"""Final-operation configuration races: temporary files and synthetic bytes only."""
import base64
import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'deploy_config_recovery', Path(__file__).resolve().parents[1] / 'scripts' / 'deploy_starfield.py')
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class PluginConfigRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.plugins = self.root / 'Plugins.txt'
        self.original = b'*Other.esm\r\n'
        self.activated = self.original + b'*FO4Port.esm\r\n'
        self.edited = self.original + b'*OwnerAdded.esm\r\n'

    def final_boundary_edit(self):
        """Inject once at either the legacy replace/unlink or the new capture/link."""
        real_replace, real_remove, real_link = os.replace, os.remove, os.link
        fired = False

        def edit():
            nonlocal fired
            if not fired:
                self.plugins.write_bytes(self.edited)
                fired = True

        def replace(source, target, *args, **kwargs):
            if Path(source) == self.plugins or Path(target) == self.plugins:
                edit()
            return real_replace(source, target, *args, **kwargs)

        def remove(path, *args, **kwargs):
            if Path(path) == self.plugins:
                edit()
            return real_remove(path, *args, **kwargs)

        def link(source, target, *args, **kwargs):
            if Path(target) == self.plugins:
                edit()
            return real_link(source, target, *args, **kwargs)

        return (patch.object(deploy.os, 'replace', side_effect=replace),
                patch.object(deploy.os, 'remove', side_effect=remove),
                patch.object(deploy.os, 'link', side_effect=link))

    def test_final_write_boundary_edit_is_preserved(self):
        self.plugins.write_bytes(self.original)
        replace, remove, link = self.final_boundary_edit()
        with replace, remove, link:
            with self.assertRaises(OSError):
                deploy.atomic_write_bytes(str(self.plugins), self.activated, '.plugins-',
                                          expected_current=self.original)
        self.assertEqual(self.plugins.read_bytes(), self.edited)

    def test_safely_restored_conflict_preserves_the_integration_exception_contract(self):
        self.plugins.write_bytes(self.edited)
        with self.assertRaises(deploy.ConcurrentUpdateError):
            deploy.atomic_write_bytes(str(self.plugins), self.activated, '.plugins-', self.original)
        self.assertEqual(self.plugins.read_bytes(), self.edited)
        record = json.loads((self.recovery() / 'transaction.json').read_text())
        self.assertEqual(record['restoration'], 'captured file restored without replacement')

    def test_failed_conflict_restoration_is_not_a_safe_typed_refusal(self):
        self.plugins.write_bytes(self.original)
        replace, remove, _ = self.final_boundary_edit()
        real_link = os.link

        def refuse_restoration(source, target, **kwargs):
            if Path(target) == self.plugins:
                raise OSError('cannot restore captured owner file')
            return real_link(source, target, **kwargs)

        with replace, remove, patch.object(deploy.os, 'link', side_effect=refuse_restoration):
            with self.assertRaises(OSError) as caught:
                deploy.atomic_write_bytes(str(self.plugins), self.activated, '.plugins-', self.original)
        self.assertNotIsInstance(caught.exception, deploy.ConcurrentUpdateError)
        self.assertFalse(self.plugins.exists())
        self.assertEqual((self.recovery() / 'before.txt').read_bytes(), self.edited)

    def test_missing_file_creation_never_replaces_a_new_owner_file(self):
        replace, remove, link = self.final_boundary_edit()
        with replace, remove, link:
            with self.assertRaises(OSError):
                deploy.atomic_write_bytes(str(self.plugins), self.activated, '.plugins-', expected_current=None)
        self.assertEqual(self.plugins.read_bytes(), self.edited)

    def test_interrupted_restore_unlink_boundary_edit_is_preserved(self):
        self.plugins.write_bytes(self.activated)
        state = {'plugins_txt': str(self.plugins), 'plugins_original': None,
                 'plugins_activated': base64.b64encode(self.activated).decode('ascii')}
        replace, remove, link = self.final_boundary_edit()
        with replace, remove, link:
            with self.assertRaises(OSError):
                deploy.restore_plugins(state)
        self.assertEqual(self.plugins.read_bytes(), self.edited)

    def test_normal_uninstall_preserves_final_boundary_edit_and_manifest(self):
        data = self.root / 'Data'
        data.mkdir()
        self.plugins.write_bytes(b'*FO4Port.esm\r\n')
        manifest = data / deploy.MANIFEST
        deploy.write_manifest(str(manifest), {'files': [], 'plugins_txt': str(self.plugins),
            'plugins_added': ['*FO4Port.esm'], 'plugins_replaced': [],
            'plugins_original': None, 'complete': True})
        replace, remove, link = self.final_boundary_edit()
        with replace, remove, link, patch.object(deploy, 'plugins_txt_path', return_value=str(self.plugins)):
            with self.assertRaisesRegex(SystemExit, 'uninstall incomplete'):
                deploy.uninstall(SimpleNamespace(starfield=str(self.root), dry_run=False))
        self.assertEqual(self.plugins.read_bytes(), self.edited)
        self.assertTrue(manifest.exists())
        self.assertEqual(json.loads(manifest.read_text())['plugins_added'], ['*FO4Port.esm'])

    def recovery(self):
        directories = list(self.root.glob('.fo4port-config-*'))
        self.assertEqual(len(directories), 1)
        return directories[0]

    def test_success_retains_previous_and_intended_configuration(self):
        self.plugins.write_bytes(self.original)
        deploy.atomic_write_bytes(str(self.plugins), self.activated, '.plugins-', self.original)
        recovery = self.recovery()
        self.assertEqual(self.plugins.read_bytes(), self.activated)
        self.assertEqual((recovery / 'before.txt').read_bytes(), self.original)
        self.assertEqual((recovery / 'intended.txt').read_bytes(), self.activated)
        record = json.loads((recovery / 'transaction.json').read_text())
        self.assertTrue(record['complete'])
        self.assertEqual(record['status'], 'published')

    def test_removal_retains_the_activated_file_and_journal(self):
        self.plugins.write_bytes(self.activated)
        deploy.update_plugins_config(str(self.plugins), None, self.activated)
        recovery = self.recovery()
        self.assertFalse(self.plugins.exists())
        self.assertEqual((recovery / 'before.txt').read_bytes(), self.activated)
        record = json.loads((recovery / 'transaction.json').read_text())
        self.assertTrue(record['complete'])
        self.assertEqual(record['status'], 'removed')

    def test_missing_file_is_created_without_overwriting(self):
        deploy.atomic_write_bytes(str(self.plugins), self.activated, '.plugins-', None)
        self.assertEqual(self.plugins.read_bytes(), self.activated)
        self.assertFalse((self.recovery() / 'before.txt').exists())

    def test_unsupported_links_refuse_before_moving_the_configuration(self):
        self.plugins.write_bytes(self.original)
        with patch.object(deploy.os, 'link', side_effect=OSError('links unavailable')):
            with self.assertRaisesRegex(OSError, 'links unavailable'):
                deploy.atomic_write_bytes(str(self.plugins), self.activated, '.plugins-', self.original)
        self.assertEqual(self.plugins.read_bytes(), self.original)
        self.assertFalse((self.recovery() / 'before.txt').exists())

    def test_capture_failure_keeps_the_original_file(self):
        self.plugins.write_bytes(self.original)
        real_replace = os.replace

        def refuse_capture(source, target):
            if Path(source) == self.plugins:
                raise PermissionError('owner holds configuration open')
            return real_replace(source, target)

        with patch.object(deploy.os, 'replace', side_effect=refuse_capture):
            with self.assertRaisesRegex(OSError, 'owner holds configuration open'):
                deploy.atomic_write_bytes(str(self.plugins), self.activated, '.plugins-', self.original)
        self.assertEqual(self.plugins.read_bytes(), self.original)
        self.assertFalse((self.recovery() / 'before.txt').exists())

    def test_publish_failure_restores_without_replacement(self):
        self.plugins.write_bytes(self.original)
        real_link = os.link

        def refuse_publish(source, target, **kwargs):
            if Path(target) == self.plugins and Path(source).name == 'intended.txt':
                raise OSError('publication unavailable')
            return real_link(source, target, **kwargs)

        with patch.object(deploy.os, 'link', side_effect=refuse_publish):
            with self.assertRaisesRegex(OSError, 'publication unavailable'):
                deploy.atomic_write_bytes(str(self.plugins), self.activated, '.plugins-', self.original)
        self.assertEqual(self.plugins.read_bytes(), self.original)
        self.assertEqual((self.recovery() / 'before.txt').read_bytes(), self.original)

    def test_new_owner_file_after_capture_is_not_overwritten_by_restore(self):
        self.plugins.write_bytes(self.original)
        real_link = os.link

        def owner_creates_new_file(source, target, **kwargs):
            if Path(target) == self.plugins and Path(source).name == 'intended.txt':
                self.plugins.write_bytes(self.edited)
            return real_link(source, target, **kwargs)

        with patch.object(deploy.os, 'link', side_effect=owner_creates_new_file):
            with self.assertRaises(OSError):
                deploy.atomic_write_bytes(str(self.plugins), self.activated, '.plugins-', self.original)
        self.assertEqual(self.plugins.read_bytes(), self.edited)
        self.assertEqual((self.recovery() / 'before.txt').read_bytes(), self.original)

    def test_late_writer_to_captured_file_is_retained_after_publication(self):
        self.plugins.write_bytes(self.original)
        real_link = os.link

        def late_captured_write(source, target, **kwargs):
            if Path(target) == self.plugins and Path(source).name == 'intended.txt':
                # Models an editor that retained its old handle after capture/validation.
                (Path(source).parent / 'before.txt').write_bytes(self.edited)
            return real_link(source, target, **kwargs)

        with patch.object(deploy.os, 'link', side_effect=late_captured_write):
            deploy.atomic_write_bytes(str(self.plugins), self.activated, '.plugins-', self.original)
        self.assertEqual(self.plugins.read_bytes(), self.activated)
        self.assertEqual((self.recovery() / 'before.txt').read_bytes(), self.edited)

    def test_interrupt_after_capture_restores_and_retains_journal(self):
        self.plugins.write_bytes(self.original)
        real_replace = os.replace

        def interrupt_after_capture(source, target):
            result = real_replace(source, target)
            if Path(source) == self.plugins:
                raise KeyboardInterrupt('interrupted after capture')
            return result

        with patch.object(deploy.os, 'replace', side_effect=interrupt_after_capture):
            with self.assertRaisesRegex(KeyboardInterrupt, 'interrupted after capture'):
                deploy.atomic_write_bytes(str(self.plugins), self.activated, '.plugins-', self.original)
        self.assertEqual(self.plugins.read_bytes(), self.original)
        recovery = self.recovery()
        self.assertEqual((recovery / 'before.txt').read_bytes(), self.original)
        self.assertFalse(json.loads((recovery / 'transaction.json').read_text())['complete'])

    def test_finished_journal_failure_keeps_both_versions(self):
        self.plugins.write_bytes(self.original)
        real_atomic = deploy.atomic_write_bytes

        def fail_finished_journal(path, content, prefix, expected_current=deploy._UNSET):
            if Path(path).name == 'transaction.json' and json.loads(content)['complete']:
                raise OSError('finished journal unavailable')
            return real_atomic(path, content, prefix, expected_current)

        with patch.object(deploy, 'atomic_write_bytes', side_effect=fail_finished_journal):
            with self.assertRaisesRegex(OSError, 'finished journal unavailable'):
                real_atomic(str(self.plugins), self.activated, '.plugins-', self.original)
        self.assertEqual(self.plugins.read_bytes(), self.activated)
        recovery = self.recovery()
        self.assertEqual((recovery / 'before.txt').read_bytes(), self.original)
        self.assertEqual((recovery / 'intended.txt').read_bytes(), self.activated)

    def test_unconditional_atomic_write_remains_a_single_replace(self):
        self.plugins.write_bytes(self.original)
        deploy.atomic_write_bytes(str(self.plugins), self.activated, '.plugins-')
        self.assertEqual(self.plugins.read_bytes(), self.activated)
        self.assertEqual({p.name for p in self.root.iterdir()}, {'Plugins.txt'})

    def test_owner_file_created_during_removal_preserves_both_files(self):
        self.plugins.write_bytes(self.activated)
        real_replace = os.replace

        def create_after_capture(source, target):
            result = real_replace(source, target)
            if Path(source) == self.plugins:
                self.plugins.write_bytes(self.edited)
            return result

        with patch.object(deploy.os, 'replace', side_effect=create_after_capture):
            with self.assertRaises(OSError):
                deploy.update_plugins_config(str(self.plugins), None, self.activated)
        self.assertEqual(self.plugins.read_bytes(), self.edited)
        self.assertEqual((self.recovery() / 'before.txt').read_bytes(), self.activated)

    def test_failed_restore_retains_captured_bytes_for_manual_recovery(self):
        self.plugins.write_bytes(self.original)
        real_link = os.link

        def fail_target_links(source, target, **kwargs):
            if Path(target) == self.plugins:
                raise PermissionError('target path unavailable')
            return real_link(source, target, **kwargs)

        with patch.object(deploy.os, 'link', side_effect=fail_target_links):
            with self.assertRaisesRegex(OSError, 'restoration unavailable'):
                deploy.atomic_write_bytes(str(self.plugins), self.activated, '.plugins-', self.original)
        recovery = self.recovery()
        self.assertFalse(self.plugins.exists())
        self.assertEqual((recovery / 'before.txt').read_bytes(), self.original)
        self.assertEqual((recovery / 'intended.txt').read_bytes(), self.activated)
        self.assertFalse(json.loads((recovery / 'transaction.json').read_text())['complete'])

    def test_prepared_journal_failure_never_moves_the_configuration(self):
        self.plugins.write_bytes(self.original)
        real_atomic = deploy.atomic_write_bytes

        def fail_journals(path, content, prefix, expected_current=deploy._UNSET):
            if Path(path).name == 'transaction.json':
                raise OSError('journal unavailable')
            return real_atomic(path, content, prefix, expected_current)

        with patch.object(deploy, 'atomic_write_bytes', side_effect=fail_journals):
            with self.assertRaisesRegex(OSError, 'journal unavailable'):
                real_atomic(str(self.plugins), self.activated, '.plugins-', self.original)
        self.assertEqual(self.plugins.read_bytes(), self.original)
        self.assertFalse((self.recovery() / 'before.txt').exists())

    def crash_after_operation(self, operation):
        self.plugins.write_bytes(self.original)
        # Only this fresh helper process exits; every input/output is inside the fixture directory.
        program = '''
import importlib.util, os, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('crash_fixture', sys.argv[1])
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)
target = Path(sys.argv[2])
operation = sys.argv[3]
replace, link = os.replace, os.link
def capture(source, destination):
    result = replace(source, destination)
    if operation == 'capture' and Path(source) == target:
        os._exit(43)
    return result
def publish(source, destination, **kwargs):
    result = link(source, destination, **kwargs)
    if operation == 'publish' and Path(destination) == target:
        os._exit(43)
    return result
deploy.os.replace = capture
deploy.os.link = publish
deploy.atomic_write_bytes(str(target), b'*Other.esm\\r\\n*FO4Port.esm\\r\\n', '.plugins-', b'*Other.esm\\r\\n')
'''
        result = subprocess.run([sys.executable, '-I', '-B', '-c', program, deploy.__file__,
                                 str(self.plugins), operation], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 43, result.stderr)
        recovery = self.recovery()
        self.assertEqual((recovery / 'before.txt').read_bytes(), self.original)
        self.assertEqual((recovery / 'intended.txt').read_bytes(), self.activated)
        record = json.loads((recovery / 'transaction.json').read_text())
        self.assertFalse(record['complete'])
        self.assertEqual(record['status'], 'prepared')

    def test_process_exit_after_capture_retains_recoverable_intent_and_original(self):
        self.crash_after_operation('capture')
        self.assertFalse(self.plugins.exists())

    def test_process_exit_after_publication_retains_current_and_previous_bytes(self):
        self.crash_after_operation('publish')
        self.assertEqual(self.plugins.read_bytes(), self.activated)

    def test_recovery_cannot_forget_a_crash_capture_when_original_file_was_absent(self):
        self.crash_after_operation('capture')
        state = {'plugins_txt': str(self.plugins), 'plugins_original': None,
                 'plugins_activated': base64.b64encode(self.original).decode('ascii')}
        with self.assertRaisesRegex(OSError, 'recovery remains unresolved'):
            deploy.restore_plugins(state)
        self.assertEqual((self.recovery() / 'before.txt').read_bytes(), self.original)
        self.assertFalse(self.plugins.exists())

    def test_prepared_publication_refuses_a_retry_even_when_current_bytes_match(self):
        self.crash_after_operation('publish')
        with self.assertRaisesRegex(OSError, 'recovery remains unresolved'):
            deploy.atomic_write_bytes(str(self.plugins), self.edited, '.plugins-', self.activated)
        self.assertEqual(self.plugins.read_bytes(), self.activated)
        self.assertEqual((self.recovery() / 'before.txt').read_bytes(), self.original)

    def test_unreadable_captured_journal_refuses_recovery(self):
        self.crash_after_operation('capture')
        recovery = self.recovery()
        (recovery / 'transaction.json').write_text('{broken journal')
        with self.assertRaisesRegex(OSError, 'recovery journal unreadable'):
            deploy.atomic_write_bytes(str(self.plugins), self.activated, '.plugins-', None)
        self.assertEqual((recovery / 'before.txt').read_bytes(), self.original)
        self.assertFalse(self.plugins.exists())

    def test_corrupt_journal_with_only_intended_file_blocks_a_retry(self):
        self.plugins.write_bytes(self.activated)
        recovery = self.root / '.fo4port-config-fixture'
        recovery.mkdir()
        (recovery / 'intended.txt').write_bytes(self.activated)
        (recovery / 'transaction.json').write_text('{corrupt publication journal')
        with self.assertRaisesRegex(OSError, 'recovery journal unreadable'):
            deploy.atomic_write_bytes(str(self.plugins), self.edited, '.plugins-', self.activated)
        self.assertEqual(self.plugins.read_bytes(), self.activated)

    def test_unresolved_config_keeps_uninstall_ownership_after_process_exit(self):
        self.crash_after_operation('capture')
        data = self.root / 'Data'
        data.mkdir()
        manifest = data / deploy.MANIFEST
        state = {'files': [], 'plugins_txt': str(self.plugins), 'plugins_original': None,
                 'plugins_added': ['*FO4Port.esm'], 'plugins_replaced': [], 'complete': False,
                 'plugins_activated': base64.b64encode(self.original).decode('ascii'),
                 'plugins_restore_pending': True}
        deploy.write_manifest(str(manifest), state)
        with patch.object(deploy, 'plugins_txt_path', return_value=str(self.plugins)):
            with self.assertRaisesRegex(SystemExit, 'uninstall incomplete'):
                deploy.uninstall(SimpleNamespace(starfield=str(self.root), dry_run=False))
        self.assertTrue(json.loads(manifest.read_text())['plugins_restore_pending'])
        self.assertEqual((self.recovery() / 'before.txt').read_bytes(), self.original)

    def test_directory_configuration_is_refused_without_moving_it(self):
        self.plugins.mkdir()
        sentinel = self.plugins / 'owner.txt'
        sentinel.write_bytes(self.edited)
        with self.assertRaisesRegex(OSError, 'ordinary file'):
            deploy.atomic_write_bytes(str(self.plugins), self.activated, '.plugins-', self.original)
        self.assertEqual(sentinel.read_bytes(), self.edited)
        self.assertFalse(list(self.root.glob('.fo4port-config-*')))

    @unittest.skipUnless(os.name == 'nt', 'Windows reparse-point metadata')
    def test_windows_reparse_configuration_is_refused_before_capture(self):
        self.plugins.write_bytes(self.original)
        metadata = SimpleNamespace(st_mode=stat.S_IFREG,
                                   st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
        with patch.object(deploy.os, 'lstat', return_value=metadata):
            with self.assertRaisesRegex(OSError, 'ordinary file'):
                deploy.atomic_write_bytes(str(self.plugins), self.activated, '.plugins-', self.original)
        self.assertEqual(self.plugins.read_bytes(), self.original)
        self.assertFalse(list(self.root.glob('.fo4port-config-*')))
