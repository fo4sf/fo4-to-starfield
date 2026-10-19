"""Doors keep their persistent destinations alongside native workshops and vanilla crafting benches."""
import copy
import json
import unittest
import test_terrain_stable_doors as stable_doors

import test_terrain_reference_identity as fixture
import test_terrain_stable_ids as stable
import test_terrain_stable_doors as stable_doors
import test_terrain_identity_audit as audit_fixture
import test_terrain_doors_writer as door_fixture
import test_terrain_lights_writer as light_fixture


class TerrainStableStationTests(unittest.TestCase):
    setUpClass = classmethod(fixture.StationWriterTests.setUpClass.__func__)
    run_writer = stable.TerrainStableIdentityTests.run_writer
    build = stable.TerrainStableIdentityTests.build
    promote_all = fixture.StationWriterTests.promote_all
    with_doors = stable_doors.selected_doors
    with_lights = light_fixture.TerrainLightsWriterTests.with_lights
    BODY = fixture.StationWriterTests.BODY
    snapshot = staticmethod(audit_fixture.TerrainIdentityAuditTests.snapshot)
    audit = audit_fixture.TerrainIdentityAuditTests.audit

    def setUp(self):
        stable.TerrainStableIdentityTests.setUp(self)
        self.objects = copy.deepcopy(self.ten)

    def mixed(self):
        obj = self.with_lights(self.with_doors(self.promote_all(), (9,)))
        obj['workshops'][1]['edid'] += '_second'
        return obj

    @staticmethod
    def reorder(obj):
        obj = copy.deepcopy(obj)
        for k in ('workshops', 'benches', 'lights', 'light_bases'):
            obj[k].reverse()
        return obj

    def test_legacy_mixed_stations_keep_light_ids_and_native_bench_links(self):
        self.params['persistent_ids'] = False
        obj = self.mixed()
        plain = copy.deepcopy(obj)
        plain['refs'] = [self.ten['refs'][9]]
        plain.pop('doors')
        before, old_stage = self.build(plain, 'stations-legacy-before')
        ids, stage = self.build(obj, 'stations-legacy-mixed')
        for key in ('bases', 'containers', 'items', 'activators', 'terminals', 'workshops', 'benches', 'lights'):
            self.assertEqual(before[key], ids[key])
        records = fixture.records(stage / 'Synthetic.esm')
        old_records = fixture.records(old_stage / 'Synthetic.esm')
        door_id = int(next(iter(ids['doors'].values()))['ref'], 16)
        for key, rec in old_records.items():
            if key != door_id:
                self.assertEqual(rec, records[key])
        self.assertFalse(any(r[0] == b'FURN' for r in records.values()))
        mk = door_fixture.mk
        mk.check_reference_slots(obj, ids)
        mk.check_door_identities(obj, ids)
        mk.check_light_identities(obj, ids)
        plugin = door_fixture.mk.overlay_records.walk_plugin(str(stage / 'Synthetic.esm'))
        checks = mk.promotion_checks(plugin['records'], len(plugin['masters']) << 24, obj, ids,
                                    {'objects': {'exported': 13, 'skipped': {}}})
        self.assertTrue(all(ok for _what, ok in checks), checks)
        self.assertTrue(any('4 ACTI' in what for what, _ok in checks), checks)

    def test_station_reorder_and_growth_preserve_all_existing_door_ids(self):
        obj = self.mixed()
        first, stage = self.build(obj, 'stations-persistent')
        changed = self.reorder(obj)
        second, _ = self.build(changed, 'stations-persistent')
        self.assertEqual(first, second)
        self.audit(stage)
        changed['workshops'].insert(0, dict(changed['workshops'][0], src='00000B:Other.esm', reference_index=10,
                                            edid='NewWorkshop'))
        third, _ = self.build(changed, 'stations-persistent')
        for key in ('bases', 'containers', 'items', 'activators', 'terminals', 'workshops', 'benches', 'lights', 'doors'):
            for src, value in first[key].items():
                self.assertEqual(value, third[key][src])
        self.audit(stage)
        reserved = json.loads((stage / 'terrain-stable-ids.json').read_text())['reservations']
        removed, _ = self.build(obj, 'stations-persistent')
        self.assertEqual(first, removed)
        self.assertEqual(reserved, json.loads((stage / 'terrain-stable-ids.json').read_text())['reservations'])
        self.audit(stage)
        restored, _ = self.build(changed, 'stations-persistent')
        self.assertEqual(third, restored)

    def test_legacy_station_bootstrap_keeps_bytes_and_native_bases(self):
        self.params['persistent_ids'] = False
        obj = self.mixed()
        # The writer accepts padded hex and case-insensitive master names; the audit must agree.
        obj['benches'][0]['vanilla'] = '002b6a63:starfield.esm'
        first, stage = self.build(obj, 'stations-bootstrap')
        old = {n: (stage / n).read_bytes() for n in ('Synthetic.esm', 'formids.json')}
        self.params['persistent_ids'] = True
        second, _ = self.build(obj, 'stations-bootstrap', bootstrap=True)
        self.assertEqual(first, second)
        self.assertEqual(old, {n: (stage / n).read_bytes() for n in old})
        self.audit(stage)
        keys = [json.loads(k) for k in json.loads((stage / 'terrain-stable-ids.json').read_text())['reservations']]
        for b in obj['benches']:
            self.assertIn(['reference', b['src'].lower()], keys)
            self.assertEqual(first['benches'][b['src']]['base'], b['vanilla'])
        self.assertFalse(any(k[0].startswith('bench') for k in keys))

    def test_bench_audit_rejects_wrong_source_kind_or_master(self):
        _, stage = self.build(self.mixed(), 'stations-audit')
        self.audit(stage)
        path = stage / 'objects.json'
        original = path.read_bytes()
        for field, wrong in (('kind', 'cooking'), ('kind', 'unknown'),
                             ('vanilla', '2B6A63:Other.esm'), ('vanilla', '2B6A62:Starfield.esm')):
            obj = json.loads(original)
            obj['benches'][0][field] = wrong
            path.write_text(json.dumps(obj))
            self.audit(stage, False, 'bench')
        path.write_bytes(original)
