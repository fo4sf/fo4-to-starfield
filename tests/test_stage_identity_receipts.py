"""The actual verify-data CLI must reject changed door identity inputs, even at the same size/time."""
import hashlib
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/terrain'))
import make_core64c as core


class StageIdentityReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        evidence = os.environ.get('FO4SF_VERIFY_EVIDENCE_DIR')
        if evidence:
            cls.root = Path(evidence)
            cls.root.mkdir()
        else:
            cls.temp = tempfile.TemporaryDirectory()
            cls.addClassCleanup(cls.temp.cleanup)
            cls.root = Path(cls.temp.name)

    def fixture(self, name):
        stage = self.root / name
        stage.mkdir()
        (stage / 'Data').mkdir()
        (stage / 'Data/synthetic.txt').write_bytes(b'synthetic payload')
        for name in ('Synthetic.esm', 'SyntheticMars.esm'):
            (stage / name).write_bytes(b'synthetic plugin bytes; this test makes no raw-record claim')
        params = {'plugin': 'Synthetic.esm', 'mars': {'plugin': 'SyntheticMars.esm'}, 'overlays': [{}],
                  'objects': 'objects.json', 'navmesh': 'navmesh.json', 'persistent_ids': True, 'revision': 1}
        self.inputs = {
            'overlays_params.json': params, 'formids.json': {'door': '000801'},
            'objects.json': {'refs': [{'src': '000001:Synthetic.esm'}]},
            'terrain-stable-ids.json': {'generation': 1}, 'navmesh.json': {'sources': [1]},
            'plan.json': [{'step': 1}], 'expected.json': {'reference': 1}}
        for name, data in self.inputs.items():
            (stage / name).write_text(json.dumps(data), encoding='utf-8')
        # Fixture specifies the receipt contract independently of the new producer helper.
        receipt = {'schema': 1, 'files': {name: {'bytes': len((stage / name).read_bytes()),
                    'sha256': hashlib.sha256((stage / name).read_bytes()).hexdigest()} for name in self.inputs}}
        report = {'checked': 'synthetic', 'pass': True, 'identity_inputs': receipt,
                  'files': core.data_manifest(str(stage), ['Synthetic.esm', 'SyntheticMars.esm'])}
        (stage / core.MANIFEST).write_text(json.dumps(report), encoding='utf-8')
        return stage

    @staticmethod
    def snapshot(stage):
        return {str(p.relative_to(stage)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in stage.rglob('*') if p.is_file()}

    def verify(self, stage, success):
        before = self.snapshot(stage)
        proc = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'scripts/terrain/make_core64c.py'),
                               'verify-data', '--out', str(stage)], capture_output=True, text=True)
        (self.root / (stage.name + '.log')).write_text(proc.stdout + proc.stderr, encoding='utf-8')
        self.assertEqual(before, self.snapshot(stage), 'verification must not rewrite evidence or recovery controls')
        self.assertEqual(proc.returncode == 0, success, proc.stdout + proc.stderr)
        return proc

    def test_unchanged_complete_receipt_passes(self):
        self.verify(self.fixture('unchanged'), True)

    def test_each_same_size_same_time_identity_change_is_rejected(self):
        original = self.fixture('original')
        for i, name in enumerate(self.inputs):
            with self.subTest(name=name):
                stage = self.root / f'changed-{i}'
                shutil.copytree(original, stage)
                path = stage / name
                st = path.stat()
                old = path.read_bytes()
                new = old.replace(b'1', b'2', 1)
                self.assertNotEqual(old, new)
                path.write_bytes(new)
                os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
                self.assertEqual(path.stat().st_size, st.st_size)
                self.assertEqual(path.stat().st_mtime_ns, st.st_mtime_ns)
                self.verify(stage, False)

    def test_legacy_receipt_requires_a_fresh_check(self):
        stage = self.fixture('legacy-receipt')
        path = stage / core.MANIFEST
        report = json.loads(path.read_text())
        report.pop('identity_inputs')
        path.write_text(json.dumps(report))
        self.verify(stage, False)

    def test_missing_map_or_ledger_cannot_pass(self):
        for i, name in enumerate(('formids.json', 'terrain-stable-ids.json')):
            with self.subTest(name=name):
                stage = self.fixture(f'missing-{i}')
                (stage / name).rename(self.root / (f'missing-{i}-preserved.json'))
                self.verify(stage, False)

    def test_unknown_or_incomplete_identity_receipt_refuses(self):
        for i in range(2):
            with self.subTest(case=i):
                stage = self.fixture(f'bad-receipt-{i}')
                path = stage / core.MANIFEST
                report = json.loads(path.read_text())
                if i == 0:
                    report['identity_inputs']['schema'] = 99
                else:
                    report['identity_inputs']['files'].pop('formids.json')
                path.write_text(json.dumps(report))
                self.verify(stage, False)

    def test_control_files_and_directories_are_preserved(self):
        for i, name in enumerate(('FO4SF.terrain-output.pending.jsonl', 'FO4SF.terrain-output.lock')):
            for directory in (False, True):
                with self.subTest(name=name, directory=directory):
                    stage = self.fixture(f'control-{i}-{directory}')
                    control = stage / name
                    if directory:
                        control.mkdir()
                    else:
                        control.write_bytes(b'unresolved owner control')
                    self.verify(stage, False)
                    self.assertTrue(control.exists())

    def test_false_result_is_not_reinterpreted_as_success(self):
        stage = self.fixture('invalid-pass')
        path = stage / core.MANIFEST
        report = json.loads(path.read_text())
        report['pass'] = 'false'
        path.write_text(json.dumps(report))
        self.verify(stage, False)

    def test_producer_pins_bytes_and_ignores_metadata_only_identity_changes(self):
        stage = self.fixture('producer')
        receipt = json.loads((stage / core.MANIFEST).read_text())['identity_inputs']
        self.assertEqual(core.identity_inputs(stage), receipt)
        path = stage / 'objects.json'
        st = path.stat()
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000_000))
        self.assertEqual(core.identity_inputs(stage), receipt)
        self.verify(stage, True)

    def test_legacy_allocation_can_get_a_new_content_receipt_without_a_ledger(self):
        stage = self.fixture('legacy-allocation')
        params_path = stage / 'overlays_params.json'
        params = json.loads(params_path.read_text())
        params.pop('persistent_ids')
        params_path.write_text(json.dumps(params))
        (stage / 'terrain-stable-ids.json').rename(self.root / 'unused-ledger-preserved.json')
        report_path = stage / core.MANIFEST
        report = json.loads(report_path.read_text())
        files = report['identity_inputs']['files']
        files.pop('terrain-stable-ids.json')
        data = params_path.read_bytes()
        files['overlays_params.json'] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        report_path.write_text(json.dumps(report))
        self.assertEqual(core.identity_inputs(stage), report['identity_inputs'])
        self.verify(stage, True)

    def test_ambiguous_or_external_inputs_refuse_before_a_receipt(self):
        original = self.fixture('bad-input-original')
        cases = [('objects', '../outside.json'), ('objects', 'C:\\outside.json'),
                 ('objects', 'sub/../objects.json'), ('persistent_ids', 'true'), ('persistent_ids', False)]
        for i, (field, value) in enumerate(cases):
            with self.subTest(field=field, value=value):
                stage = self.root / f'bad-input-{i}'
                shutil.copytree(original, stage)
                path = stage / 'overlays_params.json'
                params = json.loads(path.read_text())
                params[field] = value
                path.write_text(json.dumps(params))
                before = self.snapshot(stage)
                with self.assertRaises((ValueError, OSError)):
                    core.identity_inputs(stage)
                self.assertEqual(before, self.snapshot(stage))
        path = original / 'overlays_params.json'
        path.write_text('{"objects":"outside.json",' + path.read_text()[1:])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            core.identity_inputs(original)

    def test_input_changed_during_asset_inspection_cannot_be_reported_unchanged(self):
        stage = self.fixture('during-verification')
        original_manifest = core.data_manifest

        def change_input(*args, **kwargs):
            path = stage / 'formids.json'
            st = path.stat()
            path.write_bytes(path.read_bytes().replace(b'1', b'2', 1))
            os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
            return original_manifest(*args, **kwargs)

        before_report = (stage / core.MANIFEST).read_bytes()
        stdout = io.StringIO()
        with patch.object(core, 'data_manifest', side_effect=change_input), contextlib.redirect_stdout(stdout):
            result = core.cmd_verify_data(SimpleNamespace(out=str(stage)))
        (self.root / 'during-verification.log').write_text(stdout.getvalue())
        self.assertEqual(result, 1)
        self.assertEqual(before_report, (stage / core.MANIFEST).read_bytes())
