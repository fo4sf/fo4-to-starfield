"""Actual writer/audit lease controls and normal-check orchestration; no game installation."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_terrain_stable_stations as stations
import test_terrain_doors_writer as doors
import terrain_identity_session as session
from stage_outputs import LEASE, PENDING, require_ready_stage

core = doors.mk


class TerrainIdentitySessionTests(unittest.TestCase):
    setUpClass = classmethod(stations.TerrainStableStationTests.setUpClass.__func__)
    setUp = stations.TerrainStableStationTests.setUp
    run_writer = stations.TerrainStableStationTests.run_writer
    build = stations.TerrainStableStationTests.build
    mixed = stations.TerrainStableStationTests.mixed
    promote_all = stations.TerrainStableStationTests.promote_all
    with_doors = stations.TerrainStableStationTests.with_doors
    with_lights = stations.TerrainStableStationTests.with_lights
    BODY = stations.TerrainStableStationTests.BODY

    def prepare(self, name, growth=False):
        obj = self.mixed()
        ids, stage = self.build(obj, name)
        if growth:
            obj['workshops'].insert(0, dict(obj['workshops'][0], src='00000B:Other.esm', reference_index=10,
                                            edid='NewWorkshop'))
            obj['lights'].reverse()
            ids, stage = self.build(obj, name)
        (stage / 'plan.json').write_text('[]')
        (stage / 'expected.json').write_text('{}')
        return obj, ids, stage

    def held(self, stage):
        return session.persistent_verification(stage, command=[self.dotnet, str(self.writer)], timeout=10)

    @staticmethod
    def snapshot(stage):
        return {str(p.relative_to(stage)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in stage.rglob('*') if p.is_file() and p.name != LEASE}

    def records(self, stage):
        plugin = doors.overlay_records.walk_plugin(str(stage / 'Synthetic.esm'))
        return plugin['records'], len(plugin['masters']) << 24

    def test_retained_reservations_replace_order_checks_while_writer_is_excluded(self):
        obj, ids, stage = self.prepare('held-growth', growth=True)
        with self.assertRaises(ValueError):
            core.check_reference_slots(obj, ids)
        before = self.snapshot(stage)
        with self.held(stage) as audit:
            with self.assertRaises(OSError):
                require_ready_stage(stage)
            self.assertTrue(all(ok for _, ok in core.declared_identity_checks(stage, obj, ids, audit)))
            receipt = core.identity_inputs(stage, ready=audit.require_held)
            self.assertIn('terrain-stable-ids.json', receipt['files'])
            recs, own = self.records(stage)
            checks = core.promotion_checks(recs, own, obj, ids, {'objects': {'exported': 14, 'skipped': {}}})
            self.assertTrue(all(ok for _, ok in checks), checks)
            self.assertEqual(core.light_record_problems(recs, own, obj, ids), [])
            writer = subprocess.run([self.dotnet, str(self.writer), str(self.master), str(stage)],
                                    capture_output=True, text=True)
            (self.root / 'blocked-writer.log').write_text(writer.stdout + writer.stderr)
            self.assertNotEqual(writer.returncode, 0)
            self.assertEqual(before, self.snapshot(stage))
        self.assertEqual(before, self.snapshot(stage))
        self.assertFalse((stage / LEASE).exists())
        self.assertEqual(audit.proc.returncode, 0)

    def test_input_change_during_raw_reads_fails_final_verification(self):
        _, _, stage = self.prepare('changed-input')
        original = (stage / 'objects.json').read_bytes()
        (self.root / 'changed-input-original.json').write_bytes(original)
        with self.assertRaisesRegex(RuntimeError, 'audit input changed') as failure:
            with self.held(stage):
                (stage / 'objects.json').write_bytes(original + b' ')
        (self.root / 'changed-input.log').write_text(str(failure.exception))
        self.assertEqual((stage / 'objects.json').read_bytes(), original + b' ')
        self.assertFalse((stage / LEASE).exists())

    def test_map_marker_identities_and_door_returns_share_the_held_generation(self):
        original_master = self.master.read_bytes()
        self.addCleanup(self.master.write_bytes, original_master)
        fixture = self.writer.parents[4] / 'TerrainIdentityFixture/bin/Release/net9.0/TerrainIdentityFixture.dll'
        made = subprocess.run([self.dotnet, str(fixture), str(self.master), 'map-marker'],
                              capture_output=True, text=True)
        self.assertEqual(made.returncode, 0, made.stdout + made.stderr)
        self.params['overlays'][0]['map_markers'] = [
            {'tag': 'RedRocket', 'name': 'Red Rocket', 'pos': [1, 1, 2], 'cell': [0, 0]},
            {'tag': 'Sanctuary', 'name': 'Sanctuary', 'pos': [101, 102, 3], 'cell': [1, 1]},
        ]
        obj, ids, stage = self.prepare('held-map-marker-doors')
        tags = ids['map_marker_refs']['SyntheticWorld']
        self.assertEqual(set(tags), {'RedRocket', 'Sanctuary'})
        arrivals = {int(d['arrival'], 16) for d in ids['doors'].values()}
        self.assertTrue(arrivals.isdisjoint(int(value, 16) for value in tags.values()))
        before = self.snapshot(stage)
        with self.held(stage) as audit:
            self.assertTrue(all(ok for _, ok in core.declared_identity_checks(stage, obj, ids, audit)))
            recs, own = self.records(stage)
            self.assertEqual(core.map_marker_problems(recs, len(doors.overlay_records.walk_plugin(
                str(stage / 'Synthetic.esm'))['masters']), self.params['overlays'][0], ids), [])
            blocked = subprocess.run([self.dotnet, str(self.writer), str(self.master), str(stage)],
                                     capture_output=True, text=True)
            (self.root / 'map-marker-blocked-writer.log').write_text(blocked.stdout + blocked.stderr)
            self.assertNotEqual(blocked.returncode, 0)
            self.assertEqual(before, self.snapshot(stage))
        self.assertEqual(audit.proc.returncode, 0)
        self.assertEqual(before, self.snapshot(stage))

    def _raw_result(self, stage, obj, ids, audit, damaged=False):
        audit.require_held(stage)
        recs, own = self.records(stage)
        if damaged:
            ref = own | int(next(iter(ids['doors'].values()))['ref'], 16)
            recs = copy.deepcopy(recs)
            for rec in recs:
                if rec['fid'] == ref:
                    rec['fields'] = [field for field in rec['fields'] if field[0] != b'VMAD']
        checks = core.declared_identity_checks(stage, obj, ids, audit)
        checks += core.promotion_checks(recs, own, obj, ids, {'objects': {'exported': 13, 'skipped': {}}})
        rep = {'checks': checks, 'pass': all(ok for _, ok in checks),
               'identity_inputs': core.identity_inputs(stage, ready=audit.require_held)}
        return rep, core.data_manifest(stage, ['Synthetic.esm']), time.time()

    def test_normal_check_publishes_only_after_release_and_keeps_raw_failure(self):
        obj, ids, stage = self.prepare('raw-failure')
        publish = core.publish_check_report

        def publish_after_release(*args):
            require_ready_stage(stage)
            return publish(*args)

        with patch.object(core, 'persistent_verification', side_effect=self.held), \
             patch.object(core, 'check_stage', side_effect=lambda _a, audit: self._raw_result(stage, obj, ids, audit, True)), \
             patch.object(core, 'publish_check_report', side_effect=publish_after_release), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            result = core.cmd_check(SimpleNamespace(out=str(stage)))
        (self.root / 'raw-failure.log').write_text(output.getvalue())
        self.assertEqual(result, 1)
        for name in (core.MANIFEST, 'offline_check.json'):
            self.assertIs(json.loads((stage / name).read_text())['pass'], False)

    def test_audit_finish_failure_preserves_prior_reports(self):
        obj, ids, stage = self.prepare('prior-reports')
        reports = {core.MANIFEST: b'prior manifest', 'offline_check.json': b'prior report'}
        for name, data in reports.items():
            (stage / name).write_bytes(data)

        def changed(_a, audit):
            result = self._raw_result(stage, obj, ids, audit)
            with (stage / 'objects.json').open('ab') as stream:
                stream.write(b' ')
            return result

        with patch.object(core, 'persistent_verification', side_effect=self.held), \
             patch.object(core, 'check_stage', side_effect=changed), \
             self.assertRaisesRegex(RuntimeError, 'audit input changed'):
            core.cmd_check(SimpleNamespace(out=str(stage)))
        self.assertEqual(reports, {name: (stage / name).read_bytes() for name in reports})

    def test_abandoned_raw_check_cancels_owned_reader_without_publication(self):
        _, _, stage = self.prepare('cancelled')
        before = self.snapshot(stage)
        with self.assertRaisesRegex(ValueError, 'raw check failed'):
            with self.held(stage) as audit:
                raise ValueError('raw check failed')
        self.assertIsNotNone(audit.proc.poll())
        self.assertNotEqual(audit.proc.returncode, 0)
        self.assertFalse((stage / LEASE).exists())
        self.assertEqual(before, self.snapshot(stage))

    def test_reader_exit_after_ready_cannot_publish_a_passing_report(self):
        obj, ids, stage = self.prepare('reader-exited')
        old = b'prior checked generation'
        (stage / core.MANIFEST).write_bytes(old)
        (stage / 'offline_check.json').write_bytes(old)

        def exited(_a, audit):
            result = self._raw_result(stage, obj, ids, audit)
            self.assertTrue(result[0]['pass'])
            audit.proc.kill()  # Deliberately crash only the audit process this test created.
            audit.proc.wait(timeout=5)
            return result

        with patch.object(core, 'persistent_verification', side_effect=self.held), \
             patch.object(core, 'check_stage', side_effect=exited), \
             self.assertRaisesRegex(RuntimeError, 'no longer owns'):
            core.cmd_check(SimpleNamespace(out=str(stage)))
        self.assertEqual((stage / core.MANIFEST).read_bytes(), old)
        self.assertEqual((stage / 'offline_check.json').read_bytes(), old)

    def test_existing_controls_and_corrupt_bundle_never_reach_reader(self):
        _, _, original = self.prepare('refusal-original')
        for i, case in enumerate(('pending', 'pending-directory', 'lease', 'lease-directory', 'corrupt-map')):
            with self.subTest(case=case):
                stage = self.root / f'refusal-{i}'
                shutil.copytree(original, stage)
                if case == 'corrupt-map':
                    with (stage / 'formids.json').open('ab') as stream:
                        stream.write(b' ')
                else:
                    control = stage / (PENDING if case.startswith('pending') else LEASE)
                    control.mkdir() if case.endswith('directory') else control.write_bytes(b'preserve owner control')
                before = self.snapshot(stage)
                with self.assertRaises((OSError, RuntimeError)):
                    with self.held(stage):
                        self.fail('unproven stage reached raw reader')
                self.assertEqual(before, self.snapshot(stage))
                if case != 'corrupt-map':
                    self.assertTrue(control.exists())
                    if not control.is_dir():
                        self.assertEqual(control.read_bytes(), b'preserve owner control')

    def test_invalid_protocol_and_timeout_end_only_the_owned_process(self):
        _, _, stage = self.prepare('bad-protocol')
        before = self.snapshot(stage)
        popen = subprocess.Popen
        for script, timeout, error in (('print("{}")', 10, RuntimeError),
                                       ('import time; time.sleep(60)', 0.05, TimeoutError)):
            made = []
            def start(*args, **kwargs):
                proc = popen(*args, **kwargs)
                made.append(proc)
                return proc
            with patch.object(session.subprocess, 'Popen', side_effect=start), self.assertRaises(error):
                session.HeldIdentityAudit(stage, command=[sys.executable, '-I', '-B', '-c', script], timeout=timeout)
            self.assertEqual(len(made), 1)
            self.assertIsNotNone(made[0].poll())
            self.assertEqual(before, self.snapshot(stage))

    def test_legacy_mode_uses_original_order_checks_without_audit_process(self):
        self.params['persistent_ids'] = False
        obj, ids, stage = self.prepare('legacy')
        with session.persistent_verification(stage, command=['must-not-launch']) as audit:
            self.assertIsNone(audit)
            self.assertTrue(all(ok for _, ok in core.declared_identity_checks(stage, obj, ids, audit)))
