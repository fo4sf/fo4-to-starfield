"""Synthetic captures and observations only; never launches a game."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image


spec = importlib.util.spec_from_file_location('evidence', Path(__file__).resolve().parents[1] /
                                           'scripts/testing/commonwealth_evidence.py')
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.phase = self.root / '01-smoke'
        self.folder = self.phase / 'tests' / 'fixture' / 'a1'
        self.folder.mkdir(parents=True)
        self.plan = {'id': 'fixture', 'spawn_local': [0, 0, 10], 'z_ref': 'ground',
                     'points': [{'label': 'ground', 'x': 0, 'y': 0, 'expect': 10},
                                {'label': 'roof', 'x': 10, 'y': 0, 'expect': 15},
                                {'label': 'roof_again', 'x': 10, 'y': 0, 'expect': 15}],
                     'beyond': {'x': 10, 'y': 0}}
        self.obs = {'offset_from': 'spawn', 'spawn_read': '100 -200 12', 'offset': [100, -200, 2],
                    'points': [{'label': 'ground', 'read': '100 -200 12', 'shot': 'pt0.png'},
                               {'label': 'roof', 'read': '110 -200 17', 'shot': 'pt1.png'},
                               {'label': 'roof_again', 'read': '110 -200 17', 'shot': 'pt2.png'}],
                    'beyond_read': '110 -200 17', 'beyond_shot': 'beyond.png'}
        for shot in ('pt0.png', 'pt1.png', 'pt2.png', 'beyond.png'):
            Image.new('RGB', (3, 3), (20, 30, 40)).save(self.folder / shot)
        self.queue = {'commit': 'fixture_commit', 'tests': [self.plan]}
        self.state = {'status': 'finished', 'done': {'fixture': {'verdict': 'PASS', 'class': 'PASS', 'attempts': 1}},
                      'attempts': {'fixture': 1}}
        self.result = {'id': 'fixture', 'attempt': 1, 'verdict': 'PASS', 'class': 'PASS'}
        self.save_fixture()

    def write(self, path, value):
        path.write_text(json.dumps(value), encoding='utf-8')

    def save_fixture(self):
        self.write(self.phase / 'queue.json', self.queue)
        sha = hashlib.sha256((self.phase / 'queue.json').read_bytes()).hexdigest()
        self.write(self.root / 'campaign.json', {'runner_commit': 'fixture_commit', 'phases': {
            '01-smoke': {'queue_sha256': sha, 'acceptance_gate': True, 'points': 3}}})
        self.write(self.phase / 'state.json', self.state)
        self.write(self.phase / 'results.jsonl', self.result)
        self.write(self.folder / 'obs.json', self.obs)

    def inspect(self):
        return evidence.inspect_phase(self.root, '01-smoke')

    def test_nonzero_offsets_and_independent_stationary_captures_match(self):
        report = self.inspect()
        self.assertEqual(report['status'], 'MATCH')
        self.assertEqual(report['height_matches'], 3)
        self.assertFalse(report['runtime_accepted'])
        self.assertFalse(report['launch_hold'])
        points = report['entries'][0]['points']
        self.assertEqual(len({p['capture']['file'] for p in points}), 3)
        self.assertEqual(len({p['capture']['sha256'] for p in points}), 1)

    def test_raw_local_final_teleport_cannot_hide_behind_matching_points(self):
        self.obs['beyond_read'] = '10 0 12'
        self.save_fixture()
        report = self.inspect()
        self.assertEqual(report['status'], 'MISMATCH')
        self.assertEqual(report['height_matches'], 3)
        self.assertTrue(report['launch_hold'])
        self.assertGreater(report['entries'][0]['post_probe']['xy_error_m'], 200)

    def test_height_mismatch_retained_even_with_reported_pass(self):
        self.obs['points'][1]['read'] = '110 -200 18.9'
        self.save_fixture()
        report = self.inspect()
        self.assertEqual(report['status'], 'MISMATCH')
        self.assertEqual(report['height_matches'], 2)

    def test_wrong_xy_is_inconclusive_despite_correct_height(self):
        self.obs['points'][1]['read'] = '150 -200 17'
        self.save_fixture()
        self.assertEqual(self.inspect()['status'], 'INCONCLUSIVE')

    def test_shifted_reference_invalidates_relative_heights(self):
        self.obs['points'][0]['read'] = '150 -200 12'
        self.save_fixture()
        report = self.inspect()
        self.assertEqual(report['status'], 'INCONCLUSIVE')
        self.assertEqual(report['height_matches'], 0)

    def test_missing_and_reordered_points_cannot_pass(self):
        original = copy.deepcopy(self.obs)
        for points in (original['points'][:2], list(reversed(original['points']))):
            with self.subTest(points=points):
                self.obs['points'] = points
                self.save_fixture()
                self.assertEqual(self.inspect()['status'], 'INCONCLUSIVE')

    def test_unreadable_nonfinite_and_missing_frame_cannot_pass(self):
        original = copy.deepcopy(self.obs)
        for value in ('fail console 3', '110 -200 nan', '110 -200 inf', None):
            with self.subTest(read=value):
                self.obs = copy.deepcopy(original)
                self.obs['points'][1]['read'] = value
                self.save_fixture()
                self.assertEqual(self.inspect()['status'], 'INCONCLUSIVE')
        self.obs = copy.deepcopy(original)
        self.obs.pop('offset')
        self.save_fixture()
        self.assertEqual(self.inspect()['status'], 'INCONCLUSIVE')

    def test_inconsistent_spawn_offset_cannot_pass(self):
        self.obs['offset'][0] = 90
        self.save_fixture()
        self.assertEqual(self.inspect()['status'], 'INCONCLUSIVE')

    def test_missing_corrupt_and_wrong_format_captures_cannot_pass(self):
        path = self.folder / 'pt1.png'
        for contents in (None, b'\x89PNG\r\n\x1a\n'):
            with self.subTest(contents=contents):
                if contents is None:
                    path.unlink()
                else:
                    path.write_bytes(contents)
                self.assertEqual(self.inspect()['status'], 'INCONCLUSIVE')
        Image.new('RGB', (3, 3)).save(path, format='JPEG')
        self.assertEqual(self.inspect()['status'], 'INCONCLUSIVE')

    def test_reusing_a_capture_path_and_path_escape_are_inconclusive(self):
        for shot in ('pt0.png', '../secret.png', '/secret.png'):
            with self.subTest(shot=shot):
                self.obs['points'][1]['shot'] = shot
                self.save_fixture()
                self.assertEqual(self.inspect()['status'], 'INCONCLUSIVE')

    def test_queue_mutation_is_refused_before_observations(self):
        self.write(self.phase / 'queue.json', dict(self.queue, commit='changed'))
        with self.assertRaisesRegex(ValueError, 'campaign pins'):
            self.inspect()

    def test_incomplete_or_breaker_skipped_attempt_cannot_pass(self):
        for state in ({'status': 'running'}, {'status': 'finished', 'done': {'fixture': {'attempts': 0}}}):
            with self.subTest(state=state):
                self.state = state
                self.save_fixture()
                self.assertEqual(self.inspect()['status'], 'INCONCLUSIVE')

    def test_reported_inconclusive_is_never_upgraded(self):
        self.state['done']['fixture'].update(verdict='INCONCLUSIVE', **{'class': 'UNREAD'})
        self.result.update(verdict='INCONCLUSIVE', **{'class': 'UNREAD'})
        self.save_fixture()
        self.assertEqual(self.inspect()['status'], 'INCONCLUSIVE')

    def test_terminal_disagreement_is_refused(self):
        self.result['verdict'] = 'FAIL'
        self.save_fixture()
        with self.assertRaisesRegex(ValueError, 'disagree'):
            self.inspect()

    def test_bad_plan_and_empty_campaign_cannot_pass(self):
        for value in (float('nan'), True, '15'):
            with self.subTest(value=value):
                self.plan['points'][1]['expect'] = value
                self.save_fixture()
                with self.assertRaisesRegex(ValueError, 'inventory'):
                    self.inspect()
        self.queue['tests'] = []
        self.save_fixture()
        with self.assertRaisesRegex(ValueError, 'inventory'):
            self.inspect()


if __name__ == '__main__':
    unittest.main()
