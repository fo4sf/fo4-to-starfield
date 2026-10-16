"""Actual synthetic writer controls for durable terrain reservations; no game assets."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).parent))
import test_terrain_reference_identity as fixture


class TerrainStableIdentityTests(fixture.TerrainReferenceIdentityTests):
    def setUp(self):
        self.params = copy.deepcopy(type(self).params)
        self.params['persistent_ids'] = True

    def run_writer(self, objects, name, bootstrap=False):
        stage = self.root / name
        stage.mkdir(exist_ok=True)
        suffix = len(list(stage.glob('run-*.log')))
        (stage / 'overlays_params.json').write_text(json.dumps(self.params))
        (stage / 'objects.json').write_text(json.dumps(objects))
        (stage / f'objects-run-{suffix}.json').write_text(json.dumps(objects))
        command = [self.dotnet, str(self.writer), str(self.master), str(stage)]
        if bootstrap:
            command.append('--bootstrap-identities')
        proc = subprocess.run(command, capture_output=True, text=True)
        (stage / f'run-{suffix}.log').write_text(proc.stdout + proc.stderr)
        return proc, stage

    def build(self, objects, name, bootstrap=False):
        proc, stage = self.run_writer(objects, name, bootstrap)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return json.loads((stage / 'formids.json').read_text()), stage

    def test_reorder_insert_remove_reintroduce_keep_ids_and_tombstones(self):
        before, stage = self.build(self.objects, 'stable-permutations')
        changed = copy.deepcopy(self.objects)
        changed['refs'].reverse()
        changed['refs'].insert(0, dict(changed['refs'][0], src='000004:Synthetic.esm'))
        after, _ = self.build(changed, 'stable-permutations')
        self.assertEqual(before['refs'], {k: after['refs'][k] for k in before['refs']})
        self.assertGreater(int(after['refs']['000004:Synthetic.esm'], 16), max(int(v, 16) for v in before['refs'].values()))
        reserved = json.loads((stage / 'terrain-stable-ids.json').read_bytes())['reservations']
        removed = copy.deepcopy(changed)
        removed['refs'] = [removed['refs'][0]]
        self.build(removed, 'stable-permutations')
        self.assertEqual(json.loads((stage / 'terrain-stable-ids.json').read_bytes())['reservations'], reserved)
        restored, _ = self.build(changed, 'stable-permutations')
        self.assertEqual(after, restored)

    def test_base_reorder_and_later_promotion_preserve_existing_bases(self):
        objects = copy.deepcopy(self.objects)
        objects['bases'].append({'edid': 'SecondBase', 'model': 'second.nif'})
        objects['refs'][1]['base'] = 1
        before, _ = self.build(objects, 'stable-bases')
        objects['bases'].reverse()
        for r in objects['refs']:
            r['base'] = 1 - r['base']
        after, _ = self.build(objects, 'stable-bases')
        self.assertEqual(before, after)
        one, _ = self.build(self.promote([1]), 'stable-promotions')
        two, _ = self.build(self.promote([0, 1]), 'stable-promotions')
        self.assertEqual(one['containers']['000002:Synthetic.esm'], two['containers']['000002:Synthetic.esm'])

    def test_bootstrap_requires_identical_old_outputs(self):
        self.params['persistent_ids'] = False
        before, stage = self.build(self.objects, 'bootstrap-good')
        original = {name: (stage / name).read_bytes() for name in ('Synthetic.esm', 'formids.json')}
        self.params['persistent_ids'] = True
        proc, _ = self.run_writer(self.objects, 'bootstrap-good')
        self.assertNotEqual(proc.returncode, 0)
        after, _ = self.build(self.objects, 'bootstrap-good', bootstrap=True)
        self.assertEqual(before, after)
        self.assertEqual(original, {name: (stage / name).read_bytes() for name in original})
        self.assertTrue((stage / 'terrain-stable-ids.json').is_file())
        self.params['persistent_ids'] = False
        _, other = self.build(self.objects, 'bootstrap-wrong')
        original = {name: (other / name).read_bytes() for name in ('Synthetic.esm', 'formids.json')}
        self.params['persistent_ids'] = True
        changed = copy.deepcopy(self.objects)
        changed['refs'].reverse()
        proc, _ = self.run_writer(changed, 'bootstrap-wrong', bootstrap=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse((other / 'terrain-stable-ids.json').exists())
        self.assertEqual(original, {name: (other / name).read_bytes() for name in original})

    def test_corrupt_missing_map_and_disabled_mode_refuse(self):
        _, stage = self.build(self.objects, 'map-refusals')
        path = stage / 'terrain-stable-ids.json'
        original = {n: (stage / n).read_bytes() for n in ('Synthetic.esm', 'formids.json')}
        good = path.read_bytes()
        data = json.loads(good)
        keys = list(data['reservations'])
        data['reservations'][keys[1]] = data['reservations'][keys[0]]
        truncated = json.loads(good)
        del truncated['reservations'][keys[-1]]
        for content in (json.dumps(data).encode(), json.dumps(truncated).encode(), b'{}'):
            path.write_bytes(content)
            proc, _ = self.run_writer(self.objects, 'map-refusals')
            self.assertNotEqual(proc.returncode, 0)
        path.unlink()  # synthetic fixture only
        proc, _ = self.run_writer(self.objects, 'map-refusals')
        self.assertNotEqual(proc.returncode, 0)
        path.write_bytes(good)
        self.params['persistent_ids'] = False
        proc, _ = self.run_writer(self.objects, 'map-refusals')
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(original, {name: (stage / name).read_bytes() for name in original})

    def test_grid_growth_preserves_existing_terrain_and_reference_ids(self):
        before, stage = self.build(self.objects, 'grid-growth')
        old = json.loads((stage / 'terrain-stable-ids.json').read_text())['reservations']
        overlay = self.params['overlays'][0]
        overlay.update(n=3, cell_max=2, fnam=[0] * 9, bounds_max_m=300)
        after, _ = self.build(self.objects, 'grid-growth')
        new = json.loads((stage / 'terrain-stable-ids.json').read_text())['reservations']
        self.assertEqual(before, after)
        self.assertEqual(old, {k: new[k] for k in old})
        self.assertEqual(len(new) - len(old), 5)

    def test_navmesh_reorder_and_promotion_preserve_navm_bytes(self):
        stage = self.root / 'stable-navmesh'
        stage.mkdir()
        self.params['navmesh'] = 'navmesh.json'
        meshes = []
        for i in range(2):
            meshes.append({'src': f'{0x100+i:06X}:Synthetic.esm', 'cell': [0, i],
                'vertices': [[1, 2+i*100, 3, 0], [2, 2+i*100, 3, 0], [1, 3+i*100, 3, 0]],
                'triangles': [[0, 1, 2, -1, -1, -1, 0.0, 0, 0, 0]],
                'links': [[0, 1-i, 0, 0]], 'doors': [], 'waypoints': [],
                'grid': {'divisor': 1, 'size': [1, 1], 'min': [1, 2+i*100, 3],
                         'max': [2, 3+i*100, 3], 'raw': [1, 0]},
                'nvmi': {'location': [1, 2+i*100, 3], 'border': 0}})
        def write_nav():
            (stage / 'navmesh.json').write_text(json.dumps({'world': 'SyntheticWorld', 'navmeshes': meshes}))
        write_nav()
        before, _ = self.build(self.objects, 'stable-navmesh')
        old_records = fixture.records(stage / 'Synthetic.esm')
        nav_ids = set(before['navmeshes'])
        meshes.reverse()
        for e in meshes:
            e['links'][0][1] = 1 - e['links'][0][1]
        write_nav()
        after, _ = self.build(self.promote([0]), 'stable-navmesh')
        new_records = fixture.records(stage / 'Synthetic.esm')
        self.assertEqual(after['navmeshes'], list(reversed(before['navmeshes'])))
        for nav in nav_ids:
            self.assertEqual(old_records[int(nav, 16)], new_records[int(nav, 16)])
        self.assertGreater(int(after['containers']['000001:Synthetic.esm']['base'], 16),
                           max(int(n, 16) for n in nav_ids))
        # An ambiguous source+cell identity is refused, never indexed by array position.
        meshes[1]['src'], meshes[1]['cell'] = meshes[0]['src'], meshes[0]['cell']
        write_nav()
        saved = (stage / 'Synthetic.esm').read_bytes()
        proc, _ = self.run_writer(self.promote([0]), 'stable-navmesh')
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(saved, (stage / 'Synthetic.esm').read_bytes())

    def stable_fixture(self, stage, mode):
        stage.mkdir(exist_ok=True)
        dll = fixture.ROOT / 'dotnet/TerrainIdentityFixture/bin/Release/net9.0/TerrainIdentityFixture.dll'
        result = subprocess.run([self.dotnet, str(dll), '--stable-fixture', str(stage), mode],
                                capture_output=True, text=True)
        count = len(list(stage.glob('fixture-*.log')))
        (stage / f'fixture-{count}-{mode}.log').write_text(result.stdout + result.stderr)
        return result

    def test_publication_failure_retains_reservations_for_retry(self):
        stage = self.root / 'stable-publication-fault'
        self.assertEqual(self.stable_fixture(stage, 'seed').returncode, 0)
        old = {n: (stage / n).read_bytes() for n in ('Synthetic.esm', 'formids.json')}
        failed = self.stable_fixture(stage, 'fail')
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn('synthetic publication failure', failed.stderr)
        self.assertEqual(old, {n: (stage / n).read_bytes() for n in old})
        ledger = (stage / 'terrain-stable-ids.json').read_bytes()
        self.assertEqual(sorted(json.loads(ledger)['reservations'].values()), [0x800, 0x801])
        self.assertEqual(self.stable_fixture(stage, 'retry').returncode, 0)
        self.assertEqual(json.loads(ledger)['reservations'],
                         json.loads((stage / 'terrain-stable-ids.json').read_bytes())['reservations'])

    def test_crash_keeps_ledger_and_recovery_marker_blocks_retry(self):
        stage = self.root / 'stable-crash'
        self.assertEqual(self.stable_fixture(stage, 'seed').returncode, 0)
        old = {n: (stage / n).read_bytes() for n in ('Synthetic.esm', 'formids.json')}
        self.assertEqual(self.stable_fixture(stage, 'crash').returncode, 17)
        self.assertEqual(old, {n: (stage / n).read_bytes() for n in old})
        ledger = (stage / 'terrain-stable-ids.json').read_bytes()
        self.assertEqual(len(json.loads(ledger)['reservations']), 2)
        self.assertTrue((stage / 'FO4SF.terrain-output.pending.jsonl').is_file())
        self.assertNotEqual(self.stable_fixture(stage, 'retry').returncode, 0)
        self.assertEqual(ledger, (stage / 'terrain-stable-ids.json').read_bytes())

    def test_external_ledger_edit_is_preserved(self):
        stage = self.root / 'stable-owner-edit'
        self.assertEqual(self.stable_fixture(stage, 'seed').returncode, 0)
        old = (stage / 'Synthetic.esm').read_bytes()
        changed = self.stable_fixture(stage, 'mutate')
        self.assertNotEqual(changed.returncode, 0)
        self.assertIn('ledger changed during build', changed.stderr)
        self.assertEqual((stage / 'terrain-stable-ids.json').read_text(), 'external owner bytes')
        self.assertEqual((stage / 'Synthetic.esm').read_bytes(), old)

    def test_full_source_plugin_identity_survives_case_and_order_changes(self):
        obj = copy.deepcopy(self.objects)
        for ref, source in zip(obj['refs'], ('000001:A-B.esm', '000001:AB.esm', '000001:A.B.esp')):
            ref['src'] = source
        old, _ = self.build(obj, 'full-source-identities')
        obj['refs'].reverse()
        for ref in obj['refs']:
            ref['src'] = ref['src'].upper()
        new, _ = self.build(obj, 'full-source-identities')
        self.assertEqual({k.lower(): v for k, v in old['refs'].items()}, {k.lower(): v for k, v in new['refs'].items()})
        self.assertEqual(len(set(new['refs'].values())), 3)

    def test_valid_foreign_ledger_cannot_reassign_published_sources(self):
        _, stage = self.build(self.objects, 'generation-a')
        changed = copy.deepcopy(self.objects)
        changed['refs'].reverse()
        _, other = self.build(changed, 'generation-b')
        original = {n: (stage / n).read_bytes() for n in ('Synthetic.esm', 'formids.json')}
        (stage / 'terrain-stable-ids.json').write_bytes((other / 'terrain-stable-ids.json').read_bytes())
        proc, _ = self.run_writer(self.objects, 'generation-a')
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('published output generation', proc.stderr)
        self.assertEqual(original, {n: (stage / n).read_bytes() for n in original})

    def test_exhausted_ids_do_not_publish_wrapped_records(self):
        stage = self.root / 'stable-exhausted'
        result = self.stable_fixture(stage, 'exhaust')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('range exhausted', result.stderr)
        self.assertFalse((stage / 'Synthetic.esm').exists())
        self.assertFalse((stage / 'terrain-stable-ids.json').exists())

    def test_second_writer_cannot_change_ledger_under_publication_lease(self):
        stage = self.root / 'stable-two-writers'
        self.assertEqual(self.stable_fixture(stage, 'seed').returncode, 0)
        ledger = (stage / 'terrain-stable-ids.json').read_bytes()
        dll = fixture.ROOT / 'dotnet/TerrainIdentityFixture/bin/Release/net9.0/TerrainIdentityFixture.dll'
        owner = subprocess.Popen([self.dotnet, str(dll), '--stable-fixture', str(stage), 'hold'],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 10
            while not (stage / 'fixture-lease-ready').exists() and owner.poll() is None and time.monotonic() < deadline:
                time.sleep(.05)
            self.assertIsNone(owner.poll())
            self.assertTrue((stage / 'fixture-lease-ready').is_file())
            self.assertNotEqual(self.stable_fixture(stage, 'retry').returncode, 0)
            self.assertEqual(ledger, (stage / 'terrain-stable-ids.json').read_bytes())
        finally:
            try:
                out, err = owner.communicate('\n', timeout=10)
            except subprocess.TimeoutExpired:
                owner.kill()  # Only this synthetic helper process, never a game.
                out, err = owner.communicate()
            (stage / 'lease-owner.log').write_text(out + err)
        self.assertEqual(owner.returncode, 0)
