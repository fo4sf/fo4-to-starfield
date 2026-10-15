"""Local helper cannot hide refusals or turn a summary into acceptance."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("evidence_brief", ROOT / "tools/ai-team/evidence_brief.py")
brief = importlib.util.module_from_spec(spec)
spec.loader.exec_module(brief)


class EvidenceBriefTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def source(self, text, name="run.log"):
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_groups_repeated_markers_but_retains_all_anchors_and_real_refusal(self):
        text = '\n'.join(['Script command "fo4sfr12345678" not found.',
                          'Script command "f04sfrabcdef90" not found.',
                          'Script command "ApplyHavokImpulse" not found.', 'PASS walked']) + '\n'
        sources = brief.capture([self.source(text)], self.root)
        packet = brief.packet(sources)
        self.assertEqual(len(packet["groups"]), 3)
        markers, refused, result = packet["groups"]
        self.assertEqual(markers["occurrences"], ["S1:L1", "S1:L2"])
        self.assertIn("not_freshness_proof", markers["kind"])
        self.assertEqual(refused["kind"], "command_refusal")
        self.assertEqual(result["examples"][0]["text"], "PASS walked")
        out = self.root / "bundle"
        brief.write_bundle(sources, packet, out)
        self.assertEqual((out / "S1.txt").read_bytes(), sources[0]["bytes"])
        self.assertEqual(hashlib.sha256((out / "S1.txt").read_bytes()).hexdigest(), packet["sources"][0]["sha256"])
        self.assertIn("not gameplay acceptance", (out / "brief.txt").read_text(encoding="utf-8"))

    def test_mixed_or_spoofed_marker_does_not_hide_other_errors(self):
        for text in ('Script command "fo4sfr12345678" not found. Script command "Real" not found.',
                     'ERROR Script command "fo4sfr12345678" not found.',
                     'Script command "fo4sfr12345678suffix" not found.'):
            with self.subTest(text=text):
                self.assertEqual(brief.kind(text), "mixed_marker_and_diagnostic")

    def test_duplicate_results_keep_distinct_line_anchors(self):
        packet = brief.packet(brief.capture([self.source('2026-10-15T00:10:01 FAIL STUCK\n2026-10-15T00:11:01 FAIL STUCK\n')], self.root))
        self.assertEqual(len(packet["groups"]), 1)
        self.assertEqual(packet["groups"][0]["occurrences"], ["S1:L1", "S1:L2"])

    def test_wrapped_commands_keep_names_in_brief_and_model_input(self):
        text = '\n'.join(['Script command "fo4sfr12345678"', 'not found.',
                          'Script command "fo4sfrabcdef90"', 'not found.',
                          'Script command "ApplyHavokImpulse"', 'not found.'])
        data = brief.packet(brief.capture([self.source(text)], self.root))
        self.assertEqual(len(data['groups']), 2)
        self.assertEqual(data['groups'][1]['kind'], 'command_refusal')
        self.assertIn('ApplyHavokImpulse', brief.render(data))
        self.assertIn('ApplyHavokImpulse', json.dumps(data['groups']))
        context = data['groups'][1]['examples'][0]['context'][0]
        self.assertEqual(context, {'anchor': 'S1:L5', 'text': 'Script command "ApplyHavokImpulse"'})

    def test_mixed_refusals_and_spoof_cannot_collapse_into_markers(self):
        text = '\n'.join(['Script command "fo4sfr12345678" not found.',
                          'Script command "fo4sfrabcdef90" not found.',
                          'Script command "fo4sfrdeadbeef" not found. ApplyHavokImpulse is not recognized.',
                          'Script command "fo4sfrdeadbeef" not found. mesh.nif does not exist.',
                          'fo4sfr0: navmesh resource not found.'])
        data = brief.packet(brief.capture([self.source(text)], self.root))
        self.assertEqual(len(data['groups']), 4)
        self.assertEqual(len(data['groups'][0]['occurrences']), 2)
        rendered = brief.render(data)
        for required in ('ApplyHavokImpulse', 'mesh.nif', 'navmesh resource'):
            self.assertIn(required, rendered)

    def test_selection_includes_unknown_commands_and_file_exceptions(self):
        data = brief.packet(brief.capture([self.source('Unknown command "RealCommand"\nFileNotFoundError: mesh.nif\n')], self.root))
        self.assertEqual([g['kind'] for g in data['groups']], ['command_refusal', 'missing_path_or_resource'])

    def test_missing_context_does_not_become_success(self):
        data = brief.packet(brief.capture([self.source('ordinary text')], self.root))
        self.assertEqual(data["groups"], [])
        self.assertIn("does not establish success", brief.render(data))
        self.assertTrue(data["sources"][0]["incomplete_final_line"])

    def test_outside_duplicate_binary_and_oversized_inputs_refuse(self):
        path = self.source('FAIL synthetic\n')
        for paths, root, limit in (([path], self.root / 'other', 100),
                                   ([path, path], self.root, 100), ([path], self.root, 3),
                                   ([], self.root, 100)):
            with self.subTest(paths=paths, root=root, limit=limit):
                with self.assertRaises(ValueError):
                    brief.capture(paths, root, limit)
        binary = self.source('FAIL\0binary', 'binary.txt')
        with self.assertRaises(ValueError):
            brief.capture([binary], self.root)
        wrong = self.source('FAIL', 'source.ps1')
        with self.assertRaises(ValueError):
            brief.capture([wrong], self.root)

    def test_bundle_never_overwrites_prior_evidence(self):
        sources = brief.capture([self.source('FAIL synthetic\n')], self.root)
        data, out = brief.packet(sources), self.root / 'packet'
        brief.write_bundle(sources, data, out)
        before = (out / 'packet.json').read_bytes()
        with self.assertRaises(FileExistsError):
            brief.write_bundle(sources, data, out)
        self.assertEqual((out / 'packet.json').read_bytes(), before)


class LocalSummaryTests(unittest.TestCase):
    @staticmethod
    def status():
        return {"mode": "running", "admission_if_new_job": "admit", "running": [], "queued": [],
                "limits": {"game_blocks_inference": True}, "snapshot": {"agents": {"processes": {}},
                "lmstudio": {"source": "measured (/api/v0/models)", "loaded": [{"id": "qwen3-14b", "state": "loaded"}]}}}

    def test_resource_pause_game_unknown_or_unloaded_model_blocks(self):
        variants = [None, {}, self.status(), self.status(), self.status(), self.status(), self.status(), self.status()]
        variants[2]['mode'] = 'paused'
        variants[3]['admission_if_new_job'] = 'queue'
        variants[4]['snapshot']['agents']['processes']['Starfield.exe'] = {}
        variants[5]['snapshot']['lmstudio']['loaded'] = []
        variants[6]['snapshot']['lmstudio']['source'] = 'measured (/v1/models; no load state)'
        variants[7]['snapshot']['simulated'] = True
        for status in variants:
            with self.subTest(status=status):
                with self.assertRaises(ValueError):
                    brief.ready(status, 'qwen3-14b')

    def test_readiness_requires_no_other_local_jobs_and_game_guard(self):
        for field, value in (('running', [{}]), ('queued', [{}]), ('limits', {'game_blocks_inference': False})):
            status = self.status()
            status[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                brief.ready(status, 'qwen3-14b')
        brief.ready(self.status(), 'qwen3-14b')

    def test_unknown_or_malformed_readiness_collections_fail_cleanly(self):
        missing_running = self.status()
        del missing_running['running']
        missing_queued = self.status()
        del missing_queued['queued']
        variants = [missing_running, missing_queued]
        for name, value in (('running', None), ('limits', None), ('snapshot', None)):
            status = self.status()
            status[name] = value
            variants.append(status)
        for value in (None, {}, {'processes': []}, {'processes': None}, {'processes': {1: {}}}):
            status = self.status()
            status['snapshot']['agents'] = value
            variants.append(status)
        status = self.status()
        status['snapshot']['lmstudio']['loaded'] = [None]
        variants.append(status)
        for status in variants:
            with self.subTest(status=status), self.assertRaises(ValueError):
                brief.ready(status, 'qwen3-14b')

    def test_summary_padding_is_removed_before_retention(self):
        result = brief.validate_summary({'items': [{'group_id': 'G001', 'summary': ' ' * 10000 + 'Refused' + ' ' * 10000}]}, [{'id': 'G001'}])
        self.assertEqual(result['items'][0]['summary'], 'Refused')

    def test_unknown_duplicate_omitted_or_bad_summary_rejects(self):
        groups = [{'id': 'G001'}, {'id': 'G002'}]
        valid = {'items': [{'group_id': 'G001', 'summary': 'Refused'}, {'group_id': 'G002', 'summary': 'Unread'}]}
        self.assertEqual(brief.validate_summary(valid, groups), valid)
        for bad in ({'items': valid['items'][:1]}, {'items': valid['items'] * 2},
                    {'items': [{'group_id': 'invented', 'summary': 'PASS'}]},
                    {'items': [{'group_id': 'G001', 'summary': 7}]},
                    {'items': [], 'acceptance': True}, [], {'items': 'PASS'}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                brief.validate_summary(bad, groups)

    def test_request_has_no_tools_or_remote_endpoint_and_retains_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = {'groups': [{'id': 'G001', 'kind': 'command_refusal', 'occurrences': ['S1:L1'],
                               'examples': [{'anchor': 'S1:L1', 'text': 'FAIL refused'}]}]}
            response = {'choices': [{'message': {'content': json.dumps({'items': [{'group_id': 'G001', 'summary': 'Refused; inspect source.'}]})}}],
                        'usage': {'prompt_tokens': 100, 'completion_tokens': 30}}
            seen = []
            def opener(request, timeout):
                seen.append((request, timeout))
                return io.BytesIO(json.dumps(response).encode())
            result = brief.summarize(data, tmp, self.status, opener)
            request, timeout = seen[0]
            self.assertEqual(request.full_url, 'http://127.0.0.1:1235/v1/chat/completions')
            payload = json.loads(request.data)
            self.assertNotIn('tools', payload)
            self.assertEqual(payload['model'], 'fo4-qa')
            self.assertEqual(timeout, 180)
            self.assertFalse(result['acceptance'])
            self.assertTrue(result['untrusted'])
            self.assertEqual(json.loads((Path(tmp) / 'local-response.json').read_bytes()), response)
            self.assertEqual(result['usage']['prompt_tokens'], 100)

    def test_blocked_state_makes_zero_inference_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = []
            with self.assertRaises(ValueError):
                brief.summarize({'groups': [{'id': 'G001'}]}, tmp, lambda: {}, lambda *a, **k: calls.append(a))
            self.assertEqual(calls, [])
            self.assertFalse((Path(tmp) / 'local-request.json').exists())


if __name__ == '__main__':
    unittest.main()
