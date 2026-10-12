"""Recoverable installs with the cave runner's order/feature gate; synthetic plugins only."""
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts' / 'game'))
import exp_install as exp  # noqa: E402


def plugin(masters=()):
    subrecords = b''
    for master in masters:
        name = master.encode('utf-8') + b'\0'
        subrecords += b'MAST' + struct.pack('<H', len(name)) + name
    return b'TES4' + struct.pack('<IIIIHH', len(subrecords), 0, 0, 0, 0, 0) + subrecords


class SliceInstallTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.stage = self.root / 'staged'
        self.data = self.root / 'game' / 'Data'
        self.profile = self.root / 'profile'
        self.txt = self.profile / 'Starfield' / 'Plugins.txt'
        self.stage.mkdir()
        self.data.mkdir(parents=True)
        self.txt.parent.mkdir(parents=True)
        self.txt.write_bytes(b'\xef\xbb\xbf# owner\r\n*FO4Port.esm\r\n')
        (self.stage / 'Slice.esm').write_bytes(plugin(['Starfield.esm', 'FO4Port.esm']))
        (self.data / 'FO4Port.esm').write_bytes(plugin(['Starfield.esm']))
        self.args = SimpleNamespace(exp_dir=str(self.stage), starfield=str(self.data.parent),
                                    plugins='Slice.esm', pack=False)
        environment = patch.dict(os.environ, LOCALAPPDATA=str(self.profile))
        environment.start()
        self.addCleanup(environment.stop)

    def record(self):
        return json.loads((self.data / exp.RECORD).read_text())

    def cycle_appends_master(self):
        self.txt.write_bytes(b'\xef\xbb\xbf# owner\r\n*Slice.esm\r\n*FO4Port.esm\r\n')

    def test_plugin_only_pack_installs_relaunches_and_uninstalls_without_archive2(self):
        self.args.pack = True
        original = self.txt.read_bytes()
        with patch.object(exp, 'build_ba2', side_effect=AssertionError('no resources to pack')):
            exp.install(self.args)
            exp.install(self.args)
        self.assertTrue(self.record()['pack'])
        self.assertEqual(set(self.record()['files']), {'Slice.esm'})
        exp.uninstall(self.args)
        self.assertEqual(self.txt.read_bytes(), original)
        self.assertEqual([p.name for p in self.data.iterdir()], ['FO4Port.esm'])

    def test_order_includes_reactivated_and_already_active_plugins(self):
        for line in (b'Slice.esm', b'*Slice.esm'):
            with self.subTest(line=line):
                self.txt.write_bytes(b'# owner\r\n' + line + b'\r\n*FO4Port.esm\r\n')
                exp.install(self.args)
                self.assertEqual(exp.order(self.args), 0)
                self.assertEqual(self.txt.read_bytes(), b'# owner\r\n*FO4Port.esm\r\n*Slice.esm\r\n')
                exp.install(self.args)  # a reorder must remain a valid completed install
                exp.uninstall(self.args)
                self.assertEqual(self.txt.read_bytes(), b'# owner\r\n*FO4Port.esm\r\n' + line + b'\r\n')

    def test_disabled_master_refuses_to_rewrite(self):
        exp.install(self.args)
        original = b'*Slice.esm\r\nFO4Port.esm\r\n'
        self.txt.write_bytes(original)
        self.assertEqual(exp.order(self.args), 6)
        self.assertEqual(self.txt.read_bytes(), original)

    def test_order_preserves_edit_between_snapshot_and_replace(self):
        exp.install(self.args)
        self.cycle_appends_master()
        concurrent = self.txt.read_bytes() + b'*OwnerMod.esm\r\n'
        real_replace = exp.deployment.atomic_write_bytes

        def edit_then_write(*args, **kwargs):
            self.txt.write_bytes(concurrent)
            return real_replace(*args, **kwargs)

        with patch.object(exp.deployment, 'atomic_write_bytes', side_effect=edit_then_write):
            self.assertEqual(exp.order(self.args), 6)
        self.assertEqual(self.txt.read_bytes(), concurrent)
        self.assertFalse(list(self.txt.parent.glob('.fo4sfexp-plugins-*')))
        exp.uninstall(self.args)
        self.assertIn(b'*OwnerMod.esm', self.txt.read_bytes())

    def test_order_refuses_incomplete_or_cleanup_pending_install(self):
        exp.install(self.args)
        self.cycle_appends_master()
        original = self.txt.read_bytes()
        for field, value in (('complete', False), ('cleanup_pending', True)):
            rec = self.record()
            rec[field] = value
            (self.data / exp.RECORD).write_text(json.dumps(rec))
            self.assertEqual(exp.order(self.args), 6)
            self.assertEqual(self.txt.read_bytes(), original)
            rec[field] = not value
            (self.data / exp.RECORD).write_text(json.dumps(rec))

    def test_order_preserves_an_interrupted_master_deploys_recovery_snapshot(self):
        exp.install(self.args)
        self.cycle_appends_master()
        before = self.txt.read_bytes()
        master = self.data / exp.deployment.MANIFEST
        state = {'complete': False, 'plugins_txt': str(self.txt), 'plugins_original': None,
                 'plugins_activated': exp.base64.b64encode(before).decode('ascii')}
        master.write_text(json.dumps(state))
        self.assertEqual(exp.order(self.args), 6)
        self.assertEqual(self.txt.read_bytes(), before)
        self.assertEqual(json.loads(master.read_text()), state)
        exp.deployment.restore_plugins(state)
        self.assertFalse(self.txt.exists(), 'master recovery must still recognize the original activated bytes')

    def test_complete_master_deployment_allows_order(self):
        exp.install(self.args)
        self.cycle_appends_master()
        (self.data / exp.deployment.MANIFEST).write_text(json.dumps({'complete': True}))
        self.assertEqual(exp.order(self.args), 0)

    def test_install_cannot_invalidate_an_interrupted_master_snapshot(self):
        before = self.txt.read_bytes()
        master = self.data / exp.deployment.MANIFEST
        for state in ({'complete': False}, {'complete': True, 'cleanup_pending': True}, {}):
            with self.subTest(state=state):
                master.write_text(json.dumps(state))
                with self.assertRaisesRegex(SystemExit, 'incomplete FO4Port'):
                    exp.install(self.args)
                self.assertEqual(self.txt.read_bytes(), before)
                self.assertFalse((self.data / exp.RECORD).exists())
                self.assertFalse((self.data / 'Slice.esm').exists())
                self.assertEqual(json.loads(master.read_text()), state)

    def test_missing_changed_or_inactive_plugin_cannot_report_order_success(self):
        exp.install(self.args)
        self.cycle_appends_master()
        contents = (self.data / 'Slice.esm').read_bytes()
        (self.data / 'Slice.esm').unlink()
        self.assertEqual(exp.order(self.args), 6)
        (self.data / 'Slice.esm').write_bytes(plugin(['Different.esm']))
        self.assertEqual(exp.order(self.args), 6)
        (self.data / 'Slice.esm').write_bytes(contents)
        self.txt.write_bytes(b'Slice.esm\r\n*FO4Port.esm\r\n')
        self.assertEqual(exp.order(self.args), 6)

    def test_uninstall_after_order_preserves_foreign_lines_and_format(self):
        original = self.txt.read_bytes()
        exp.install(self.args)
        self.cycle_appends_master()
        self.txt.write_bytes(self.txt.read_bytes() + b'*OwnerMod.esm\r\n')
        self.assertEqual(exp.order(self.args), 0)
        self.assertEqual(exp.order(self.args), 0)
        exp.uninstall(self.args)
        self.assertEqual(self.txt.read_bytes(), original + b'*OwnerMod.esm\r\n')

    def test_cli_gate_runs_before_build_or_publication(self):
        base = ['install', '--exp-dir', str(self.stage), '--starfield', str(self.data.parent), '--pack']
        with self.assertRaises(SystemExit) as error:
            exp.main(base + ['--needs', 'a_future_feature'])
        self.assertEqual(error.exception.code, 5)
        self.assertFalse((self.data / exp.RECORD).exists())
        exp.main(base + ['--needs', 'door_trip,door_check,plugin_order'])
        with self.assertRaises(SystemExit) as result:
            exp.main(['order', '--starfield', str(self.data.parent)])
        self.assertEqual(result.exception.code, 0)

    def test_cycles_and_self_master_never_report_order_success(self):
        for dependencies in (['Slice.esm'], ['Loop.esm']):
            with self.subTest(dependencies=dependencies):
                (self.stage / 'Slice.esm').write_bytes(plugin(dependencies))
                if dependencies == ['Loop.esm']:
                    (self.stage / 'Loop.esm').write_bytes(plugin(['Slice.esm']))
                    self.args.plugins = 'Slice.esm,Loop.esm'
                exp.install(self.args)
                original = self.txt.read_bytes()
                self.assertEqual(exp.order(self.args), 6)
                self.assertEqual(self.txt.read_bytes(), original)
                exp.uninstall(self.args)

    def test_truncated_header_cannot_hide_missing_masters(self):
        valid = plugin(['Missing.esm'])
        (self.stage / 'Bad.esm').write_bytes(valid)
        self.assertEqual(exp.plugin_masters(self.stage / 'Bad.esm'), ['Missing.esm'])
        for malformed in (valid[:-1], valid[:25]):
            with self.subTest(size=len(malformed)):
                (self.stage / 'Bad.esm').write_bytes(malformed)
                with self.assertRaises(ValueError):
                    exp.plugin_masters(self.stage / 'Bad.esm')
