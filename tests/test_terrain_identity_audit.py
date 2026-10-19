"""Persistent ID audit on actual synthetic writer outputs; never reads a game installation."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import unittest

import test_terrain_stable_mixed as mixed_fixture


class TerrainIdentityAuditTests(unittest.TestCase):
    setUpClass = classmethod(mixed_fixture.TerrainStableMixedTests.setUpClass.__func__)
    setUp = mixed_fixture.TerrainStableMixedTests.setUp
    run_writer = mixed_fixture.TerrainStableMixedTests.run_writer
    build = mixed_fixture.TerrainStableMixedTests.build
    mixed = mixed_fixture.TerrainStableMixedTests.mixed
    reorder = staticmethod(mixed_fixture.TerrainStableMixedTests.reorder)
    promote_all = mixed_fixture.TerrainStableMixedTests.promote_all
    with_doors = mixed_fixture.TerrainStableMixedTests.with_doors
    with_lights = mixed_fixture.TerrainStableMixedTests.with_lights
    BODY = mixed_fixture.TerrainStableMixedTests.BODY

    @staticmethod
    def snapshot(stage):
        return {str(p.relative_to(stage)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in stage.rglob('*') if p.is_file()}

    def audit(self, stage, success=True, reason=None):
        before = self.snapshot(stage)
        proc = subprocess.run([self.dotnet, str(self.writer), '--check-identities', str(stage)], capture_output=True, text=True)
        self.assertEqual(before, self.snapshot(stage), 'audit must not change artifacts or clear existing controls')
        index = len(list(self.root.glob('audit-*.log')))
        (self.root / f'audit-{index}.log').write_text(proc.stdout + proc.stderr, encoding='utf-8')
        if success:
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            report = json.loads(proc.stdout)
            self.assertGreater(report['checked_ids'], 0)
            self.assertFalse(report['artifacts_changed'])
            self.assertFalse(report['native_acceptance'])
            return report
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        if reason:
            self.assertIn(reason, proc.stderr)

    def test_explicit_empty_doors_matches_current_writer_and_retains_reservations(self):
        obj = self.mixed()
        first, stage = self.build(obj, 'audit-empty-doors')
        empty = copy.deepcopy(obj)
        empty['refs'].extend(dict(d, base=0) for d in empty['doors'])
        empty['doors'] = []
        second, _ = self.build(empty, 'audit-empty-doors')
        self.assertEqual(second['doors'], {})
        self.audit(stage)
        restored, _ = self.build(obj, 'audit-empty-doors')
        self.assertEqual(first, restored)
        self.audit(stage)

    def test_reordered_mixed_sources_use_saved_ids_not_allocation_order(self):
        obj = self.mixed()
        first, stage = self.build(obj, 'audit-reorder')
        second, _ = self.build(self.reorder(obj), 'audit-reorder')
        self.assertEqual(first, second)
        report = self.audit(stage)
        self.assertEqual(report['output_count'], 2)

    def test_large_reference_section_keeps_exact_source_lookup_after_reorder(self):
        obj = copy.deepcopy(self.objects)
        template = obj['refs'][0]
        obj['refs'] = [dict(template, src=f'{0x100000 + i:06X}:Synthetic.esm',
                            cell=[0, 0], pos=[1 + i % 20, 2 + i % 30, 3]) for i in range(8192)]
        _, stage = self.build(obj, 'audit-many-refs')
        first = self.audit(stage)
        self.assertGreaterEqual(first['checked_ids'], 8192)
        obj['refs'].reverse()
        (stage / 'objects.json').write_text(json.dumps(obj), encoding='utf-8')
        self.assertEqual(self.audit(stage), first)

    def test_source_key_case_mismatch_is_not_hidden_by_indexing(self):
        obj = self.mixed()
        _, stage = self.build(obj, 'audit-key-case')
        obj['doors'][0]['src'] = obj['doors'][0]['src'].lower()
        (stage / 'objects.json').write_text(json.dumps(obj), encoding='utf-8')
        self.audit(stage, False, 'map/source key sets differ')

    def test_removed_light_reservations_remain_valid_tombstones(self):
        obj = self.mixed()
        added = copy.deepcopy(obj)
        added['lights'].append(dict(added['lights'][0], src='00A099:Other.esm'))
        _, stage = self.build(added, 'audit-tombstones')
        self.build(obj, 'audit-tombstones')
        ledger = json.loads((stage / 'terrain-stable-ids.json').read_text())
        self.assertIn(['light-reference', '00a099:other.esm'], [json.loads(k) for k in ledger['reservations']])
        self.audit(stage)

    def test_altered_outputs_or_ledger_refuse_without_repair(self):
        _, original = self.build(self.mixed(), 'audit-corruption')
        for name in ('Synthetic.esm', 'formids.json', 'terrain-stable-ids.json'):
            with self.subTest(name=name):
                stage = self.root / ('corrupt-' + name)
                shutil.copytree(original, stage)
                path = stage / name
                if name.endswith('.esm'):
                    path.write_bytes(path.read_bytes() + b'corrupted')
                else:
                    obj = json.loads(path.read_text())
                    if name == 'formids.json':
                        next(iter(obj['doors'].values()))['arrival'] = 'ABCDEF'
                    else:
                        obj['checksum'] = '0' * 64
                    path.write_text(json.dumps(obj))
                self.audit(stage, False, 'checksum mismatch' if name == 'terrain-stable-ids.json' else 'published output generation')

    def test_changed_source_menu_is_rejected_even_with_unchanged_valid_outputs(self):
        _, stage = self.build(self.mixed(), 'audit-source')
        path = stage / 'objects.json'
        obj = json.loads(path.read_text())
        obj['terminals'][0]['menu_edid'] = obj['terminals'][1]['menu_edid']
        path.write_text(json.dumps(obj))
        self.audit(stage, False, 'mapped id disagrees')

    def test_missing_outputs_ledger_and_existing_recovery_controls_are_preserved(self):
        _, original = self.build(self.mixed(), 'audit-controls')
        cases = ('missing-ledger', 'missing-map', 'pending-file', 'pending-directory', 'lock-file', 'lock-directory', 'disabled')
        for case in cases:
            with self.subTest(case=case):
                stage = self.root / case
                shutil.copytree(original, stage)
                if case.startswith('missing-'):
                    # Keep the removed synthetic input beside the case instead of discarding it.
                    name = 'terrain-stable-ids.json' if case == 'missing-ledger' else 'formids.json'
                    (stage / name).rename(self.root / (case + '-preserved.json'))
                elif case == 'disabled':
                    p = stage / 'overlays_params.json'
                    prm = json.loads(p.read_text())
                    prm['persistent_ids'] = False
                    p.write_text(json.dumps(prm))
                else:
                    name = 'FO4SF.terrain-output.pending.jsonl' if case.startswith('pending') else 'FO4SF.terrain-output.lock'
                    path = stage / name
                    path.mkdir() if case.endswith('directory') else path.write_text('preserve this control')
                self.audit(stage, False)
                if case.endswith('directory'):
                    self.assertTrue(path.is_dir())

    def test_duplicate_json_and_escaped_identity_spelling(self):
        obj = self.mixed()
        obj['lights'][0]['src'] = '00A001:Ü+Name.esm'
        obj['activators'][0]['edid'] = obj['activators'][2]['edid'] = 'É<&>Bell'
        _, stage = self.build(obj, 'audit-unicode')
        self.audit(stage)
        path = stage / 'objects.json'
        text = path.read_text()
        path.write_text('{"world":"SyntheticWorld",' + text[1:])
        self.audit(stage, False, 'duplicate JSON property')

    def test_terrain_only_output_and_missing_mars_companion(self):
        self.params.pop('objects')
        proc, stage = self.run_writer(self.mixed(), 'audit-terrain-only')
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.audit(stage)['output_count'], 1)
        # A newly declared companion cannot be accepted against the one-output generation.
        path = stage / 'overlays_params.json'
        prm = json.loads(path.read_text())
        prm['mars'] = {'plugin': 'SyntheticMars.esm'}
        path.write_text(json.dumps(prm))
        self.audit(stage, False, 'incomplete')

    def test_navmesh_only_output_uses_source_and_cell_keys(self):
        self.params.pop('objects')
        self.params['navmesh'] = 'navmesh.json'
        stage = self.root / 'audit-navmesh'
        stage.mkdir()
        meshes = [{'src': f'{0x100 + i:06X}:Synthetic.esm', 'cell': [0, i],
                   'vertices': [[1, 2 + i*100, 3, 0], [2, 2 + i*100, 3, 0], [1, 3 + i*100, 3, 0]],
                   'triangles': [[0, 1, 2, -1, -1, -1, 0.0, 0, 0, 0]], 'links': [], 'doors': [], 'waypoints': [],
                   'grid': {'divisor': 1, 'size': [1, 1], 'min': [1, 2 + i*100, 3],
                            'max': [2, 3 + i*100, 3], 'raw': [1, 0]},
                   'nvmi': {'location': [1, 2 + i*100, 3], 'border': 0}} for i in range(2)]
        nav = stage / 'navmesh.json'
        nav.write_text(json.dumps({'world': 'SyntheticWorld', 'navmeshes': meshes}))
        first, _ = self.build(self.mixed(), 'audit-navmesh')
        meshes.reverse()
        nav.write_text(json.dumps({'world': 'SyntheticWorld', 'navmeshes': meshes}))
        second, _ = self.build(self.mixed(), 'audit-navmesh')
        self.assertEqual(first['navmeshes'], list(reversed(second['navmeshes'])))
        self.audit(stage)
        meshes[0]['cell'] = [1, 0]
        nav.write_text(json.dumps({'world': 'SyntheticWorld', 'navmeshes': meshes}))
        self.audit(stage, False, 'no reservation')

    def test_mars_companion_is_included_in_generation_verification(self):
        self.master = self.root / 'mars-master/Starfield.esm'
        fixture = Path(__file__).resolve().parents[1] / 'dotnet/TerrainIdentityFixture/bin/Release/net9.0/TerrainIdentityFixture.dll'
        proc = subprocess.run([self.dotnet, str(fixture), '--master-with-mars', str(self.master)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.params['mars'] = {'plugin': 'Synthetic_Mars.esm'}
        self.params['overlays'][0].update(latitude=0.1, longitude=0.2)
        _, stage = self.build(self.mixed(), 'audit-mars')
        self.assertEqual(self.audit(stage)['output_count'], 3)
        path = stage / 'Synthetic_Mars.esm'
        path.write_bytes(path.read_bytes() + b'corrupted companion')
        self.audit(stage, False, 'published output generation')


if __name__ == '__main__':
    unittest.main()
