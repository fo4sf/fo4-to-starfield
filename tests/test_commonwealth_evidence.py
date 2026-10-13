"""Synthetic captures and observations only; never launches a game."""
import copy
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
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
        self.queue = {'commit': 'a' * 40, 'tests': [self.plan]}
        self.state = {'status': 'finished', 'done': {'fixture': {'verdict': 'PASS', 'class': 'PASS', 'attempts': 1}},
                      'attempts': {'fixture': 1}}
        self.result = {'id': 'fixture', 'attempt': 1, 'verdict': 'PASS', 'class': 'PASS'}
        self.save_fixture()

    def write(self, path, value):
        path.write_text(json.dumps(value), encoding='utf-8')

    def save_fixture(self):
        self.write(self.phase / 'queue.json', self.queue)
        sha = hashlib.sha256((self.phase / 'queue.json').read_bytes()).hexdigest()
        self.write(self.root / 'campaign.json', {'runner_commit': 'a' * 40, 'phases': {
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

    def test_hardlinked_capture_alias_is_not_an_independent_invocation(self):
        path = self.folder / 'pt1.png'
        path.unlink()
        os.link(self.folder / 'pt0.png', path)
        self.assertEqual(self.inspect()['status'], 'INCONCLUSIVE')

    @unittest.skipUnless(os.name == 'nt', 'Windows filename aliases')
    def test_windows_case_and_trailing_dot_aliases_cannot_pass(self):
        for name in ('PT0.png', 'pt0.png.'):
            with self.subTest(name=name):
                self.obs['points'][1]['shot'] = name
                self.save_fixture()
                self.assertEqual(self.inspect()['status'], 'INCONCLUSIVE')
        self.obs['points'][1]['shot'] = 'pt1.png'
        self.obs['beyond_shot'] = 'PT0.png'
        self.save_fixture()
        self.assertEqual(self.inspect()['status'], 'INCONCLUSIVE')

    def test_newer_terminal_failure_cannot_be_ignored(self):
        with (self.phase / 'results.jsonl').open('a') as stream:
            stream.write('\n' + json.dumps(dict(self.result, attempt=2, verdict='FAIL', **{'class': 'HEIGHTS'})))
        self.assertEqual(self.inspect()['status'], 'INCONCLUSIVE')

    def test_boolean_attempt_fields_are_rejected(self):
        self.result['attempt'] = True
        self.save_fixture()
        with self.assertRaisesRegex(ValueError, 'attempt'):
            self.inspect()
        self.result['attempt'] = 1
        self.state['attempts']['fixture'] = True
        self.save_fixture()
        self.assertEqual(self.inspect()['status'], 'INCONCLUSIVE')

    def test_missing_commit_is_refused_even_when_queue_digest_matches(self):
        for commit in (None, '', 'not-a-commit'):
            with self.subTest(commit=commit):
                self.queue['commit'] = commit
                self.save_fixture()
                manifest = json.loads((self.root / 'campaign.json').read_text())
                manifest['runner_commit'] = commit
                self.write(self.root / 'campaign.json', manifest)
                with self.assertRaisesRegex(ValueError, 'campaign pins'):
                    self.inspect()

    def test_invalid_png_checksum_is_inconclusive(self):
        path = self.folder / 'pt1.png'
        data = bytearray(path.read_bytes())
        data[60] ^= 1
        path.write_bytes(data)
        self.assertEqual(self.inspect()['status'], 'INCONCLUSIVE')

    def test_malformed_object_shapes_cannot_crash_into_a_pass(self):
        self.write(self.folder / 'obs.json', [])
        self.assertEqual(self.inspect()['status'], 'INCONCLUSIVE')
        self.save_fixture()
        self.write(self.phase / 'results.jsonl', [])
        with self.assertRaisesRegex(ValueError, 'attempt'):
            self.inspect()
        self.state['done']['fixture'] = []
        self.save_fixture()
        with self.assertRaisesRegex(ValueError, 'done entry'):
            self.inspect()

    def test_cli_returns_inconclusive_json_for_unusable_evidence(self):
        path = self.folder / 'pt1.png'
        data = bytearray(path.read_bytes())
        data[60] ^= 1
        path.write_bytes(data)
        for malformed_obs in (False, True):
            with self.subTest(malformed_obs=malformed_obs):
                if malformed_obs:
                    self.write(self.folder / 'obs.json', [])
                output = io.StringIO()
                with redirect_stdout(output):
                    code = evidence.main(['--campaign', str(self.root), '--phase', '01-smoke'])
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(output.getvalue())['status'], 'INCONCLUSIVE')

    def test_cross_entry_capture_replay_cannot_pass(self):
        plan2 = copy.deepcopy(self.plan)
        plan2['id'] = 'fixture2'
        self.queue['tests'].append(plan2)
        self.state['done']['fixture2'] = copy.deepcopy(self.state['done']['fixture'])
        self.state['attempts']['fixture2'] = 1
        self.save_fixture()
        manifest = json.loads((self.root / 'campaign.json').read_text())
        manifest['phases']['01-smoke']['points'] = 6
        self.write(self.root / 'campaign.json', manifest)
        other = self.phase / 'tests' / 'fixture2' / 'a1'
        other.mkdir(parents=True)
        self.write(other / 'obs.json', self.obs)
        for name in ('pt0.png', 'pt1.png', 'pt2.png', 'beyond.png'):
            os.link(self.folder / name, other / name)
        with (self.phase / 'results.jsonl').open('a') as stream:
            stream.write('\n' + json.dumps(dict(self.result, id='fixture2')))
        report = self.inspect()
        self.assertEqual(report['status'], 'INCONCLUSIVE')
        self.assertEqual(report['height_matches'], 0)
        self.assertTrue(report['launch_hold'])

    def add_second_entry(self, replay=None):
        """Independent files may have identical pixels; replay shares one inode."""
        plan = copy.deepcopy(self.plan)
        plan['id'] = 'fixture2'
        self.queue['tests'].append(plan)
        self.state['done']['fixture2'] = copy.deepcopy(self.state['done']['fixture'])
        self.state['attempts']['fixture2'] = 1
        self.save_fixture()
        manifest = json.loads((self.root / 'campaign.json').read_text())
        manifest['phases']['01-smoke']['points'] = 6
        self.write(self.root / 'campaign.json', manifest)
        other = self.phase / 'tests' / 'fixture2' / 'a1'
        other.mkdir(parents=True)
        self.write(other / 'obs.json', self.obs)
        for name in ('pt0.png', 'pt1.png', 'pt2.png', 'beyond.png'):
            if name == replay:
                os.link(self.folder / name, other / name)
            else:
                (other / name).write_bytes((self.folder / name).read_bytes())
        with (self.phase / 'results.jsonl').open('a') as stream:
            stream.write('\n' + json.dumps(dict(self.result, id='fixture2')))

    def test_replayed_reference_invalidates_both_entries_relative_heights(self):
        self.add_second_entry(replay='pt0.png')
        report = self.inspect()
        self.assertEqual(report['status'], 'INCONCLUSIVE')
        self.assertEqual(report['height_matches'], 0)
        for entry in report['entries']:
            self.assertTrue(all(p['status'] == 'INCONCLUSIVE' for p in entry['points']))
            self.assertIn('CAPTURE_REUSE', [i['class'] for i in entry['issues']])
            self.assertIn('REFERENCE', [i['class'] for i in entry['issues']])

    def test_post_probe_replaying_reference_invalidates_relative_heights(self):
        self.obs['beyond_shot'] = 'pt0.png'
        self.save_fixture()
        report = self.inspect()
        self.assertEqual(report['status'], 'INCONCLUSIVE')
        self.assertEqual(report['height_matches'], 0)
        self.assertTrue(report['launch_hold'])
        self.assertIn('REFERENCE', [i['class'] for i in report['entries'][0]['issues']])

    def test_replayed_reference_demotes_dependent_height_mismatch_issues(self):
        self.obs['points'][1]['read'] = '110 -200 18.9'
        self.add_second_entry(replay='pt0.png')
        report = self.inspect()
        self.assertEqual(report['status'], 'INCONCLUSIVE')
        self.assertEqual(report['height_matches'], 0)
        for entry in report['entries']:
            self.assertFalse(any(i['class'] == 'HEIGHTS' and i['status'] == 'MISMATCH'
                                 for i in entry['issues']))
            self.assertTrue(any(i.get('invalidated_class') == 'HEIGHTS' and
                                i['status'] == 'INCONCLUSIVE' for i in entry['issues']))
            self.assertIn('CAPTURE_REUSE', [i['class'] for i in entry['issues']])

    def test_shifted_reference_demotes_dependent_height_mismatch_issues(self):
        self.obs['points'][0]['read'] = '150 -200 12'
        self.obs['points'][1]['read'] = '110 -200 18.9'
        self.save_fixture()
        report = self.inspect()
        self.assertEqual(report['status'], 'INCONCLUSIVE')
        self.assertEqual(report['height_matches'], 0)
        self.assertFalse(any(i['status'] == 'MISMATCH' for i in report['entries'][0]['issues']))

    def test_nonreference_replay_keeps_other_independent_heights(self):
        self.add_second_entry(replay='pt1.png')
        report = self.inspect()
        self.assertEqual(report['status'], 'INCONCLUSIVE')
        self.assertEqual(report['height_matches'], 4)
        for entry in report['entries']:
            self.assertEqual([p['status'] for p in entry['points']],
                             ['MATCH', 'INCONCLUSIVE', 'MATCH'])
            self.assertNotIn('REFERENCE', [i['class'] for i in entry['issues']])

    def test_independent_identical_captures_across_entries_remain_usable(self):
        self.add_second_entry()
        report = self.inspect()
        self.assertEqual(report['status'], 'MATCH')
        self.assertEqual(report['height_matches'], 6)
        self.assertFalse(report['launch_hold'])

    def test_overflowing_inputs_and_calculations_produce_inconclusive_json(self):
        for plan_x, expect in ((1e308, 15), (10, 10**400)):
            with self.subTest(plan_x=plan_x):
                self.plan['points'][1].update(x=plan_x, expect=expect)
                self.obs['points'][1]['read'] = '-1e308 -200 17'
                self.save_fixture()
                output = io.StringIO()
                with redirect_stdout(output):
                    code = evidence.main(['--campaign', str(self.root), '--phase', '01-smoke'])
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(output.getvalue())['status'], 'INCONCLUSIVE')


if __name__ == '__main__':
    unittest.main()
