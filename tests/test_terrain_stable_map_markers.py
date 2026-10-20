"""Actual writer: map identities remain stable alongside persistent door destinations."""
import copy
import json
import subprocess
import unittest

import test_terrain_reference_identity as fixture
import test_terrain_stable_ids as stable
import test_terrain_stable_doors as doors
import test_terrain_identity_audit as audit_fixture


class TerrainStableMapMarkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.TerrainReferenceIdentityTests.setUpClass.__func__(cls)
        tool = fixture.ROOT / 'dotnet/TerrainIdentityFixture/bin/Release/net9.0/TerrainIdentityFixture.dll'
        subprocess.run([cls.dotnet, str(tool), str(cls.master), 'map-marker'], capture_output=True, check=True)

    setUp = stable.TerrainStableIdentityTests.setUp
    run_writer = stable.TerrainStableIdentityTests.run_writer
    build = stable.TerrainStableIdentityTests.build
    promote = fixture.TerrainReferenceIdentityTests.promote
    with_doors = doors.TerrainStableDoorTests.with_doors
    snapshot = staticmethod(audit_fixture.TerrainIdentityAuditTests.snapshot)
    audit = audit_fixture.TerrainIdentityAuditTests.audit

    @staticmethod
    def marker(tag, pos=(20, 30, 4)):
        return {'tag': tag, 'name': tag or 'Red Rocket', 'pos': list(pos), 'cell': [0, 0]}

    def test_default_marker_has_a_named_reservation_and_audits(self):
        ids, stage = self.build(self.with_doors(self.promote([1])), 'default-marker')
        key = json.dumps(['map-marker', 'syntheticworld', 'redrocket'], separators=(',', ':'))
        ledger = json.loads((stage / 'terrain-stable-ids.json').read_text())['reservations']
        self.assertEqual(ledger[key], int(ids['map_marker_refs']['SyntheticWorld']['RedRocket'], 16))
        self.audit(stage)

    def test_marker_reorder_growth_removal_and_reintroduction_preserve_doors(self):
        overlay = self.params['overlays'][0]
        original = [self.marker('RedRocket'), self.marker('Sanctuary')]
        overlay['map_markers'] = copy.deepcopy(original)
        obj = self.with_doors(self.promote([1]))
        first, stage = self.build(obj, 'marker-growth')
        for markers in [list(reversed(original)), [self.marker('Concord'), *original],
                        [original[1]], [], original]:
            overlay['map_markers'] = copy.deepcopy(markers)
            ids, _ = self.build(obj, 'marker-growth')
            for kind in ('bases', 'refs', 'containers', 'doors'):
                self.assertEqual(first[kind], ids[kind])
            for marker in markers:
                tag = marker['tag']
                if tag in first['map_marker_refs']['SyntheticWorld']:
                    self.assertEqual(first['map_marker_refs']['SyntheticWorld'][tag],
                                     ids['map_marker_refs']['SyntheticWorld'][tag])
            if markers:
                self.assertEqual(ids['map_markers']['SyntheticWorld'],
                                 ids['map_marker_refs']['SyntheticWorld'][markers[0]['tag']])
            self.audit(stage)
        keys = json.loads((stage / 'terrain-stable-ids.json').read_text())['reservations']
        self.assertIn('["map-marker","syntheticworld","concord"]', keys)

    def test_legacy_bootstrap_is_byte_identical(self):
        self.params['persistent_ids'] = False
        self.params['overlays'][0]['map_markers'] = [self.marker('RedRocket'), self.marker('Sanctuary')]
        obj = self.with_doors(self.promote([1]))
        first, stage = self.build(obj, 'marker-bootstrap')
        before = {n: (stage / n).read_bytes() for n in ('Synthetic.esm', 'formids.json')}
        self.params['persistent_ids'] = True
        second, _ = self.build(obj, 'marker-bootstrap', bootstrap=True)
        self.assertEqual(first, second)
        self.assertEqual(before, {n: (stage / n).read_bytes() for n in before})
        self.audit(stage)

    def test_default_and_explicit_redrocket_share_identity(self):
        first, stage = self.build(self.objects, 'marker-default-to-explicit')
        self.params['overlays'][0]['map_markers'] = [self.marker('RedRocket')]
        second, _ = self.build(self.objects, 'marker-default-to-explicit')
        self.assertEqual(first, second)
        self.audit(stage)

    def test_duplicate_canonical_tags_refuse_without_replacing_outputs(self):
        _, stage = self.build(self.objects, 'duplicate-markers')
        names = ('Synthetic.esm', 'formids.json', 'terrain-stable-ids.json')
        before = {n: (stage / n).read_bytes() for n in names}
        for tags in [('Sanctuary', 'sanctuary'), ('', 'RedRocket'), (' ',)]:
            with self.subTest(tags=tags):
                self.params['overlays'][0]['map_markers'] = [self.marker(t) for t in tags]
                proc, _ = self.run_writer(self.objects, 'duplicate-markers')
                self.assertNotEqual(proc.returncode, 0)
                self.assertEqual(before, {n: (stage / n).read_bytes() for n in names})

    def test_audit_rejects_changed_tag_or_first_marker_without_rebuild(self):
        overlay = self.params['overlays'][0]
        original = [self.marker('RedRocket'), self.marker('Sanctuary')]
        overlay['map_markers'] = copy.deepcopy(original)
        _, stage = self.build(self.objects, 'marker-audit-source')
        for markers in [[self.marker('Unknown'), original[1]], list(reversed(original))]:
            overlay['map_markers'] = markers
            (stage / 'overlays_params.json').write_text(json.dumps(self.params))
            self.audit(stage, success=False)

    def test_same_tag_in_different_worlds_uses_distinct_ids(self):
        other = copy.deepcopy(self.params['overlays'][0])
        other.update(world='OtherWorld', block='OtherBlock', location='OtherLocation',
                     coc='OtherSpawn', tag='Other')
        other['anchor'].update(form_id=0x900, edid='OtherAnchor')
        self.params['overlays'].append(other)
        first, stage = self.build(self.objects, 'marker-worlds')
        self.assertNotEqual(first['map_markers']['SyntheticWorld'], first['map_markers']['OtherWorld'])
        self.audit(stage)

    def test_new_template_adds_map_ids_without_moving_existing_door_ids(self):
        tool = fixture.ROOT / 'dotnet/TerrainIdentityFixture/bin/Release/net9.0/TerrainIdentityFixture.dll'
        plain_master = self.root / 'without-marker/Starfield.esm'
        subprocess.run([self.dotnet, str(tool), str(plain_master)], capture_output=True, check=True)
        marker_master = self.master
        self.master = plain_master
        obj = self.with_doors(self.promote([1]))
        first, stage = self.build(obj, 'marker-template-introduction')
        self.assertNotIn('map_markers', first)
        self.audit(stage)
        old_keys = json.loads((stage / 'terrain-stable-ids.json').read_text())['reservations']
        self.master = marker_master
        second, _ = self.build(obj, 'marker-template-introduction')
        for kind, ids in first.items():
            self.assertEqual(ids, second[kind])
        new_keys = json.loads((stage / 'terrain-stable-ids.json').read_text())['reservations']
        self.assertTrue(old_keys.items() <= new_keys.items())
        self.assertEqual(len(new_keys), len(old_keys) + 1)
        self.audit(stage)
