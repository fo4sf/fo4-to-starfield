"""Scripted door bases/return markers survive changing exports in the real synthetic writer."""
import copy
import json
import unittest

import test_terrain_reference_identity as fixture
import test_terrain_stable_ids as stable
import test_terrain_doors_writer as doors


def selected_doors(self, objects, indices=(2,)):
    obj = copy.deepcopy(objects)
    selected = {self.objects['refs'][i]['src']: i for i in indices}
    refs = {r['src']: r for r in obj['refs']}
    obj['doors'] = [doors.TerrainDoorsWriterTests.door(refs[src], i, 0xDEFF + n,
                      arrival=tuple(refs[src]['pos']))
                    for n, (src, i) in enumerate(selected.items())]
    obj['refs'] = [r for r in obj['refs'] if r['src'] not in selected]
    return obj


class TerrainStableDoorTests(unittest.TestCase):
    setUpClass = classmethod(fixture.TerrainReferenceIdentityTests.setUpClass.__func__)
    setUp = stable.TerrainStableIdentityTests.setUp
    run_writer = stable.TerrainStableIdentityTests.run_writer
    build = stable.TerrainStableIdentityTests.build
    promote = fixture.TerrainReferenceIdentityTests.promote
    with_doors = selected_doors

    def pair(self):
        obj = self.with_doors(self.promote([1]), (2, 0))
        obj['doors'][1]['edid'] += '_second'
        return obj

    def test_legacy_reorder_demonstrates_why_migration_is_explicit(self):
        self.params['persistent_ids'] = False
        obj = self.pair()
        first, _ = self.build(obj, 'legacy-door-order')
        obj['doors'].reverse()
        second, _ = self.build(obj, 'legacy-door-order')
        for src in first['doors']:
            self.assertEqual(first['doors'][src]['ref'], second['doors'][src]['ref'])
            self.assertNotEqual(first['doors'][src]['base'], second['doors'][src]['base'])
            self.assertNotEqual(first['doors'][src]['arrival'], second['doors'][src]['arrival'])

    def test_door_reorder_preserves_all_ids_and_reopens_ledger(self):
        obj = self.pair()
        first, stage = self.build(obj, 'persistent-door-order')
        obj['doors'].reverse()
        second, _ = self.build(obj, 'persistent-door-order')
        self.assertEqual(first, second)
        keys = [json.loads(k) for k in json.loads((stage / 'terrain-stable-ids.json').read_text())['reservations']]
        for d in obj['doors']:
            self.assertIn(['door-base', d['edid'].lower()], keys)
            self.assertIn(['door-arrival', d['src'].lower()], keys)

    def test_insert_remove_reintroduce_preserves_door_destinations_and_tombstones(self):
        obj = self.pair()
        first, stage = self.build(obj, 'persistent-door-growth')
        added = copy.deepcopy(obj)
        new_door = copy.deepcopy(added['doors'][0])
        new_door.update(src='000004:Synthetic.esm', edid='NewDoorBase', reference_index=3)
        new_door['destination']['id'] = 0xDF10  # each return endpoint belongs to one exterior door
        added['doors'].insert(0, new_door)
        second, _ = self.build(added, 'persistent-door-growth')
        for src, ids in first['doors'].items():
            self.assertEqual(ids, second['doors'][src])
        for key in ('bases', 'refs', 'containers'):
            self.assertEqual(first[key], second[key])
        reservations = json.loads((stage / 'terrain-stable-ids.json').read_text())['reservations']
        removed, _ = self.build(obj, 'persistent-door-growth')
        self.assertEqual(first, removed)
        self.assertEqual(reservations, json.loads((stage / 'terrain-stable-ids.json').read_text())['reservations'])
        restored, _ = self.build(added, 'persistent-door-growth')
        self.assertEqual(second, restored)
        self.assertEqual(len(reservations.values()), len(set(reservations.values())))

    def test_legacy_door_bootstrap_is_byte_identical_then_reorder_is_stable(self):
        self.params['persistent_ids'] = False
        obj = self.pair()
        first, stage = self.build(obj, 'door-bootstrap')
        original = {n: (stage / n).read_bytes() for n in ('Synthetic.esm', 'formids.json')}
        self.params['persistent_ids'] = True
        second, _ = self.build(obj, 'door-bootstrap', bootstrap=True)
        self.assertEqual(first, second)
        self.assertEqual(original, {n: (stage / n).read_bytes() for n in original})
        obj['doors'].reverse()
        third, _ = self.build(obj, 'door-bootstrap')
        self.assertEqual(first, third)

    def test_arrival_identity_uses_the_whole_source_plugin_key(self):
        obj = self.pair()
        obj['doors'][0]['src'] = '000003:One.esm'
        obj['doors'][1]['src'] = '000003:Two.esm'
        first, _ = self.build(obj, 'door-source-owners')
        a, b = (first['doors'][k]['arrival'] for k in ('000003:One.esm', '000003:Two.esm'))
        self.assertNotEqual(a, b)
        obj['doors'].reverse()
        second, _ = self.build(obj, 'door-source-owners')
        self.assertEqual(first, second)


if __name__ == '__main__':
    unittest.main()
