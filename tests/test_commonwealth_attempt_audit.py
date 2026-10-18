"""Attempt-mode dispatch never calls or rewrites the live controller's judge."""
import contextlib
import importlib.util
import io
import json
import subprocess
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).parents[1] / 'scripts' / 'testing'
sys.path.insert(0, str(HERE))
import commonwealth_evidence as audit


class AttemptAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.spec = {'id': 'fixture', 'kind': 'walk'}
        self.obs = {'kind': 'walk'}
        self.write()
        self.module = types.ModuleType('continuous_evidence')
        self.module.inspect_walk = lambda *args: {'issues': [], 'rows': []}
        self.module.inspect_door_trip = lambda *args: {'issues': [], 'rows': []}

    def write(self):
        for name, value in [('spec.json', self.spec), ('obs.json', self.obs)]:
            (self.folder / name).write_text(json.dumps(value), encoding='utf-8')

    def test_walk_attempt_is_dispatched_with_source_identities(self):
        before = {p.name: p.read_bytes() for p in self.folder.iterdir()}
        with patch.dict(sys.modules, continuous_evidence=self.module):
            result = audit.inspect_attempt(self.folder)
        self.assertEqual(result['status'], 'MATCH')
        self.assertFalse(result['runtime_accepted'])
        self.assertEqual(result['spec']['file'], 'spec.json')
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.folder.iterdir()})

    def test_door_attempt_keeps_missing_evidence_inconclusive(self):
        self.spec['kind'] = self.obs['kind'] = 'door_trip'
        self.write()
        self.module.inspect_door_trip = lambda *args: {'issues': [{'status': 'INCONCLUSIVE', 'class': 'ROUTE'}]}
        with patch.dict(sys.modules, continuous_evidence=self.module):
            result = audit.inspect_attempt(self.folder)
        self.assertEqual(result['status'], 'INCONCLUSIVE')

    def test_mismatch_and_incomplete_remain_inconclusive(self):
        self.module.inspect_walk = lambda *args: {'issues': [{'status': 'MISMATCH', 'class': 'XYZ'},
                                                           {'status': 'INCONCLUSIVE', 'class': 'CAPTURE'}]}
        with patch.dict(sys.modules, continuous_evidence=self.module):
            self.assertEqual(audit.inspect_attempt(self.folder)['status'], 'INCONCLUSIVE')

    def test_different_observation_kind_is_refused(self):
        self.obs['kind'] = 'door_trip'
        self.write()
        with self.assertRaisesRegex(ValueError, 'kind differs'):
            audit.inspect_attempt(self.folder)

    def test_unsupported_kind_is_refused(self):
        self.spec['kind'] = self.obs['kind'] = 'unknown'
        self.write()
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            audit.inspect_attempt(self.folder)

    def test_invalid_handler_issues_cannot_become_match(self):
        self.module.inspect_walk = lambda *args: {'issues': [{'status': 'PASS'}]}
        with patch.dict(sys.modules, continuous_evidence=self.module), self.assertRaises(ValueError):
            audit.inspect_attempt(self.folder)

    def test_cli_reports_same_incomplete_exit_protocol(self):
        self.module.inspect_walk = lambda *args: {'issues': [{'status': 'INCONCLUSIVE', 'class': 'PIN'}]}
        output = io.StringIO()
        with patch.dict(sys.modules, continuous_evidence=self.module), contextlib.redirect_stdout(output):
            code = audit.main(['--attempt', str(self.folder)])
        self.assertEqual(code, 2)
        self.assertFalse(json.loads(output.getvalue())['runtime_accepted'])


class IsolatedAttemptCliTests(unittest.TestCase):
    def test_isolated_cli_loads_trusted_sibling_and_keeps_selection_gate(self):
        from test_continuous_evidence import DoorEvidenceTests, WalkEvidenceTests
        for kind, fixture_type, wrong_selection in (
                ('walk', WalkEvidenceTests, False),
                ('door_trip', DoorEvidenceTests, False),
                ('door_trip', DoorEvidenceTests, True)):
            with self.subTest(kind=kind, wrong_selection=wrong_selection):
                fixture = fixture_type()
                fixture.setUp()
                try:
                    if wrong_selection:
                        fixture.rewrite_ocr(fixture.obs['probe_reads'][0], lambda text:
                            text.replace('GetSelf >> (01000001)', 'GetSelf >> (01000002)'))
                    fixture.obs['kind'] = kind
                    fixture.write('spec.json', fixture.test)
                    fixture.write('obs.json', fixture.obs)
                    # A result-directory module must never supply the auditor.
                    fixture.write('continuous_evidence.py', "raise RuntimeError('untrusted module loaded')")
                    before = {p.name: p.read_bytes() for p in fixture.root.iterdir()}
                    run = subprocess.run([sys.executable, '-I', '-B',
                        str(HERE / 'commonwealth_evidence.py'), '--attempt', str(fixture.root)],
                        cwd=fixture.root, capture_output=True, text=True, timeout=30)
                    self.assertTrue(run.stdout.strip(), run.stderr)
                    report = json.loads(run.stdout)
                    self.assertFalse(report['runtime_accepted'])
                    self.assertFalse(report['entry']['acceptance_gate'])
                    if wrong_selection:
                        self.assertNotEqual(run.returncode, 0)
                        self.assertNotEqual(report['status'], 'MATCH')
                        row = next(r for r in report['entry']['rows'] if r['label'] == 'merge_probe.0')
                        self.assertFalse(row['selection_verified'])
                        self.assertIsNone(row['observed'])
                        self.assertNotIn('merged_residual_m', row)
                    else:
                        self.assertEqual(run.returncode, 0, run.stderr)
                        self.assertEqual(report['status'], 'MATCH')
                    self.assertEqual(before, {p.name: p.read_bytes() for p in fixture.root.iterdir()})
                finally:
                    fixture.doCleanups()


if __name__ == '__main__':
    unittest.main()
