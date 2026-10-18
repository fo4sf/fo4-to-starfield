"""Actual synthetic writer: main's FLOR promotion joins persistent identity publication."""
import copy
import json
import unittest

import test_terrain_reference_identity as fixture
import test_terrain_stable_ids as stable
import test_terrain_identity_audit as audit_fixture


class TerrainStableFloraTests(unittest.TestCase):
    setUpClass = classmethod(fixture.TerrainReferenceIdentityTests.setUpClass.__func__)
    setUp = stable.TerrainStableIdentityTests.setUp
    run_writer = stable.TerrainStableIdentityTests.run_writer
    build = stable.TerrainStableIdentityTests.build
    snapshot = staticmethod(audit_fixture.TerrainIdentityAuditTests.snapshot)
    audit = audit_fixture.TerrainIdentityAuditTests.audit

    def plants(self, shared=False):
        obj = copy.deepcopy(self.objects)
        obj['flora'] = [dict(obj['refs'][i], reference_index=i,
                             edid='SharedPlant' if shared else f'SyntheticPlant{i}',
                             model='synthetic_plant.nif', name='Synthetic plant',
                             ingredient='00260DF2:Starfield.esm') for i in (0, 2)]
        obj['refs'] = [obj['refs'][1]]
        return obj

    def test_reorder_growth_and_reintroduction_keep_flora_and_reference_ids(self):
        obj = self.plants()
        first, stage = self.build(obj, 'stable-flora-reorder')
        changed = copy.deepcopy(obj)
        changed['flora'].reverse()
        reordered, _ = self.build(changed, 'stable-flora-reorder')
        self.assertEqual(first, reordered)
        changed['refs'].append(dict(changed['refs'][0], src='000004:Synthetic.esm'))
        grown, _ = self.build(changed, 'stable-flora-reorder')
        self.assertEqual(first['flora'], grown['flora'])
        self.assertEqual(first['refs']['000002:Synthetic.esm'], grown['refs']['000002:Synthetic.esm'])
        reserved = json.loads((stage / 'terrain-stable-ids.json').read_text())['reservations']
        removed = changed['flora'].pop()
        changed['refs'].append(dict(removed, base=0))
        fewer, _ = self.build(changed, 'stable-flora-reorder')
        self.assertEqual(fewer['refs'][removed['src']], first['flora'][removed['src']]['ref'])
        self.audit(stage)
        restored, _ = self.build(obj, 'stable-flora-reorder')
        self.assertEqual(first, restored)
        self.assertEqual(reserved, json.loads((stage / 'terrain-stable-ids.json').read_text())['reservations'])
        self.audit(stage)

    def test_legacy_bootstrap_preserves_plugin_and_map_bytes(self):
        obj = self.plants()
        self.params['persistent_ids'] = False
        first, stage = self.build(obj, 'stable-flora-bootstrap')
        original = {name: (stage / name).read_bytes() for name in ('Synthetic.esm', 'formids.json')}
        self.params['persistent_ids'] = True
        proc, _ = self.run_writer(obj, 'stable-flora-bootstrap')
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(original, {name: (stage / name).read_bytes() for name in original})
        restored, _ = self.build(obj, 'stable-flora-bootstrap', bootstrap=True)
        self.assertEqual(first, restored)
        self.assertEqual(original, {name: (stage / name).read_bytes() for name in original})
        self.audit(stage)

    def test_shared_flora_base_has_one_reservation_and_distinct_placements(self):
        ids, stage = self.build(self.plants(shared=True), 'stable-flora-shared')
        flora = list(ids['flora'].values())
        self.assertEqual(len({v['base'] for v in flora}), 1)
        self.assertEqual(len({v['ref'] for v in flora}), 2)
        keys = [json.loads(k) for k in json.loads((stage / 'terrain-stable-ids.json').read_text())['reservations']]
        self.assertEqual([k for k in keys if k[0] == 'flora'], [['flora', 'sharedplant']])
        self.audit(stage)

    def test_invalid_ingredient_preserves_published_outputs_and_ledger(self):
        obj = self.plants()
        _, stage = self.build(obj, 'stable-flora-refusal')
        original = {name: (stage / name).read_bytes()
                    for name in ('Synthetic.esm', 'formids.json', 'terrain-stable-ids.json')}
        wrong = copy.deepcopy(obj)
        wrong['flora'][0]['ingredient'] = '000010:Starfield.esm'  # STAT, not a harvestable ingredient
        proc, _ = self.run_writer(wrong, 'stable-flora-refusal')
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('MISC or LVLI', proc.stdout + proc.stderr)
        self.assertEqual(original, {name: (stage / name).read_bytes() for name in original})
        self.build(obj, 'stable-flora-refusal')
        self.audit(stage)

    def test_audit_rejects_a_different_declared_flora_base_without_repair(self):
        obj = self.plants()
        _, stage = self.build(obj, 'stable-flora-audit-binding')
        self.audit(stage)
        original = (stage / 'objects.json').read_bytes()
        changed = copy.deepcopy(obj)
        # This is a valid shared-base declaration, but not the published generation's binding.
        changed['flora'][0]['edid'] = changed['flora'][1]['edid']
        (stage / 'objects.json').write_text(json.dumps(changed))
        self.audit(stage, success=False)
        (stage / 'objects.json').write_bytes(original)
        self.audit(stage)


if __name__ == '__main__':
    unittest.main()
