"""Attempt-mode dispatch never calls or rewrites the live controller's judge."""
import contextlib
import importlib.util
import io
import json
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


if __name__ == '__main__':
    unittest.main()
