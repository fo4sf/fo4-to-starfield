"""Existing garage relationship metadata participates in the persistent-ID audit; no game inputs."""
import copy
import json
import shutil
import struct
import unittest

import test_terrain_reference_identity as fixture
import test_terrain_stable_ids as stable
import test_terrain_identity_audit as audit_fixture


class GarageIdentityAuditTests(unittest.TestCase):
    setUpClass = classmethod(stable.TerrainStableIdentityTests.setUpClass.__func__)
    setUp = stable.TerrainStableIdentityTests.setUp
    run_writer = stable.TerrainStableIdentityTests.run_writer
    build = stable.TerrainStableIdentityTests.build
    audit = audit_fixture.TerrainIdentityAuditTests.audit
    snapshot = staticmethod(audit_fixture.TerrainIdentityAuditTests.snapshot)

    def objects_with_pair(self):
        objects = copy.deepcopy(self.objects)
        button, door = objects['refs'][:2]
        objects['activators'] = [dict(ref, reference_index=i, edid=f'SyntheticActi{i}',
                                     model='synthetic.nif', name=f'Part{i}')
                                 for i, ref in enumerate((button, door))]
        objects['refs'] = objects['refs'][2:]
        objects['garage_buttons'] = [{'button': button['src'], 'door': door['src']}]
        return objects

    def test_wired_pair_audits_and_preserves_ids_and_links_across_growth(self):
        objects = self.objects_with_pair()
        first, stage = self.build(objects, 'garage-identity-growth')
        self.audit(stage)
        original = fixture.records(stage / 'Synthetic.esm')
        changed = copy.deepcopy(objects)
        extra = dict(changed['activators'][0], src='000004:Other.esm', reference_index=3,
                     edid='NewGarageButton', name='New button')
        changed['activators'].reverse()
        changed['activators'].insert(0, extra)
        changed['garage_buttons'].insert(0, {'button': extra['src'],
                                            'door': objects['garage_buttons'][0]['door']})
        after, stage = self.build(changed, 'garage-identity-growth')
        self.audit(stage)
        for source, identity in first['activators'].items():
            self.assertEqual(after['activators'][source], identity)
        written = fixture.records(stage / 'Synthetic.esm')
        for source, identity in first['activators'].items():
            self.assertEqual(written[int(identity['ref'], 16)], original[int(identity['ref'], 16)])
        for pair, mapped in zip(changed['garage_buttons'], after['garage_buttons']):
            button_id = int(after['activators'][pair['button']]['ref'], 16)
            door_id = int(after['activators'][pair['door']]['ref'], 16)
            self.assertEqual(mapped, {'button': f'{button_id:06X}', 'door': f'{door_id:06X}'})
            fields = dict(fixture.subrecords(written[button_id][1]))
            self.assertEqual(struct.unpack('<II', fields[b'XLKR']), (0x0005D5E7, 0x01000000 | door_id))
            self.assertIn(b'VMAD', fields)

    def test_changed_source_pairs_refuse_without_touching_published_outputs(self):
        objects = self.objects_with_pair()
        ids, original = self.build(objects, 'garage-source-proof')
        pair = objects['garage_buttons'][0]
        mutations = {
            'swapped': ([{'button': pair['door'], 'door': pair['button']}], 'mapped id disagrees'),
            'ordinary-reference': ([dict(pair, door=objects['refs'][0]['src'])], 'not a promoted activator'),
            'wrong-owner': ([dict(pair, door='000002:Other.esm')], 'not a promoted activator'),
            'base-as-source': ([dict(pair, button=ids['activators'][pair['button']]['base'] + ':Synthetic.esm')],
                               'not a promoted activator'),
            'extra-pair': ([pair, pair], 'garage pair count'),
            'empty-source': ([], 'map/source key sets differ'),
        }
        for name, (pairs, reason) in mutations.items():
            with self.subTest(name=name):
                stage = self.root / ('garage-source-' + name)
                shutil.copytree(original, stage)
                changed = copy.deepcopy(objects)
                changed['garage_buttons'] = pairs
                (stage / 'objects.json').write_text(json.dumps(changed), encoding='utf-8')
                self.audit(stage, False, reason)

    def test_absent_empty_and_casefolded_source_pairs_keep_writer_semantics(self):
        objects = self.objects_with_pair()
        objects.pop('garage_buttons')
        _, stage = self.build(objects, 'garage-absent')
        self.audit(stage)
        objects['garage_buttons'] = []
        ids, stage = self.build(objects, 'garage-empty')
        self.assertNotIn('garage_buttons', ids)
        self.audit(stage)
        objects = self.objects_with_pair()
        _, stage = self.build(objects, 'garage-casefold')
        changed = copy.deepcopy(objects)
        changed['garage_buttons'][0] = {k: v.upper() for k, v in changed['garage_buttons'][0].items()}
        (stage / 'objects.json').write_text(json.dumps(changed), encoding='utf-8')
        self.audit(stage)


if __name__ == '__main__':
    unittest.main()
