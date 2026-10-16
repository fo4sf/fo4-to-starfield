"""Actual synthetic writer: saved door destinations coexist with new promoted records and lights."""
import copy
import json
import unittest

import test_terrain_reference_identity as fixture
import test_terrain_stable_ids as stable
import test_terrain_doors_writer as doors
import test_terrain_lights_writer as lights


class TerrainStableMixedTests(unittest.TestCase):
    setUpClass = classmethod(fixture.ActivatorTerminalWriterTests.setUpClass.__func__)
    run_writer = stable.TerrainStableIdentityTests.run_writer
    build = stable.TerrainStableIdentityTests.build
    promote_all = fixture.ActivatorTerminalWriterTests.promote_all
    with_doors = doors.TerrainDoorsWriterTests.with_doors
    with_lights = lights.TerrainLightsWriterTests.with_lights
    BODY = fixture.ActivatorTerminalWriterTests.BODY

    def setUp(self):
        stable.TerrainStableIdentityTests.setUp(self)
        self.objects = copy.deepcopy(self.seven)

    def mixed(self):
        obj = self.with_lights(self.with_doors(self.promote_all(), (7,)))
        # Two distinct menus ensure that a terminal/menu permutation actually changes allocation order.
        obj['terminals'][1]['edid'] += '_second'
        obj['terminals'][1]['menu_edid'] += '_second'
        return obj

    @staticmethod
    def reorder(obj):
        obj = copy.deepcopy(obj)
        for kind in ('containers', 'items', 'activators', 'terminals', 'doors', 'lights', 'light_bases'):
            obj[kind].reverse()
        return obj

    def test_legacy_mixed_build_keeps_existing_light_ids_and_passes_raw_checks(self):
        self.params['persistent_ids'] = False
        obj = self.mixed()
        no_door = copy.deepcopy(obj)
        no_door['refs'] = [copy.deepcopy(self.seven['refs'][7])]
        no_door.pop('doors')
        old, before = self.build(no_door, 'legacy-before-doors')
        ids, stage = self.build(obj, 'legacy-mixed')
        for kind in ('bases', 'containers', 'items', 'activators', 'terminals', 'lights'):
            self.assertEqual(ids[kind], old[kind])
        door = next(iter(ids['doors'].values()))
        self.assertEqual(door['ref'], old['refs'][obj['doors'][0]['src']])
        original, written = fixture.records(before / 'Synthetic.esm'), fixture.records(stage / 'Synthetic.esm')
        for key, record in original.items():
            if key != int(door['ref'], 16):
                self.assertEqual(written[key], record)
        self.assertGreater(int(door['base'], 16), max(original))
        self.assertGreater(int(door['arrival'], 16), int(door['base'], 16))

        mk = doors.mk
        plugin = doors.overlay_records.walk_plugin(str(stage / 'Synthetic.esm'))
        recs, own = plugin['records'], len(plugin['masters']) << 24
        mk.check_reference_slots(obj, ids)
        mk.check_door_identities(obj, ids)
        mk.check_light_identities(obj, ids)
        first, last = mk.lights_after(recs, len(plugin['masters']), ids)
        self.assertGreater(first, last)
        self.assertEqual(mk.light_record_problems(recs, own, obj, ids), [])
        exp = {'objects': {'exported': len(self.seven['refs']) + len(obj['lights']), 'skipped': {}}}
        checks = mk.promotion_checks(recs, own, obj, ids, exp)
        self.assertTrue(all(ok for _what, ok in checks), checks)
        self.assertTrue(any('3 ACTI' in what for what, _ok in checks), checks)
        # Missing ordinary ACTI, missing marker and damaged VMAD cannot become accepted mixed builds.
        for removed in (int(next(iter(ids['activators'].values()))['base'], 16), int(door['arrival'], 16)):
            bad = [r for r in recs if r['fid'] != own | removed]
            self.assertTrue(any(not ok for _what, ok in mk.promotion_checks(bad, own, obj, ids, exp)))
        bad = copy.deepcopy(recs)
        for r in bad:
            if r['fid'] == own | int(door['ref'], 16):
                r['fields'] = [f for f in r['fields'] if f[0] != b'VMAD']
        self.assertTrue(any(not ok for _what, ok in mk.promotion_checks(bad, own, obj, ids, exp)))
        for key, check in (('doors', mk.check_door_identities), ('lights', mk.check_light_identities)):
            bad_ids = copy.deepcopy(ids)
            next(iter(bad_ids[key].values()))['base'] = door['ref']
            with self.assertRaises(ValueError):
                check(obj, bad_ids)

    def test_persistent_mixed_reorder_keeps_every_identity(self):
        obj = self.mixed()
        first, stage = self.build(obj, 'mixed-reorder')
        second, _ = self.build(self.reorder(obj), 'mixed-reorder')
        self.assertEqual(first, second)
        reservations = json.loads((stage / 'terrain-stable-ids.json').read_text())['reservations']
        self.assertEqual(len(reservations), len(set(reservations.values())))

    def test_new_promotions_and_lights_do_not_move_existing_door_destinations(self):
        obj = self.mixed()
        first, stage = self.build(obj, 'mixed-growth')
        changed = self.reorder(obj)
        for i, kind in enumerate(('activators', 'terminals', 'doors'), 8):
            extra = copy.deepcopy(changed[kind][0])
            extra.update(src=f'{i + 1:06X}:Synthetic.esm', reference_index=i, edid=extra['edid'] + '_new')
            if kind == 'terminals':
                extra['menu_edid'] += '_new'
            changed[kind].insert(0, extra)
        extra = copy.deepcopy(changed['lights'][0])
        extra.update(src='00A004:Other.esm', edid=extra['edid'] + '_new')
        light_base = copy.deepcopy(next(b for b in changed['light_bases'] if b['edid'] == changed['lights'][0]['edid']))
        light_base['edid'] = extra['edid']
        changed['lights'].insert(0, extra)
        changed['light_bases'].insert(0, light_base)
        second, _ = self.build(changed, 'mixed-growth')
        for kind in ('bases', 'refs', 'containers', 'items', 'activators', 'terminals', 'doors', 'lights'):
            for src, identity in first[kind].items():
                self.assertEqual(second[kind][src], identity, (kind, src))
        reserved = json.loads((stage / 'terrain-stable-ids.json').read_text())['reservations']
        restored, _ = self.build(obj, 'mixed-growth')
        self.assertEqual(first, restored)
        self.assertEqual(reserved, json.loads((stage / 'terrain-stable-ids.json').read_text())['reservations'])
        reintroduced, _ = self.build(changed, 'mixed-growth')
        self.assertEqual(second, reintroduced)

    def test_mixed_bootstrap_requires_identical_plugin_and_map_then_preserves_reordering(self):
        self.params['persistent_ids'] = False
        obj = self.mixed()
        first, stage = self.build(obj, 'mixed-bootstrap')
        old = {name: (stage / name).read_bytes() for name in ('Synthetic.esm', 'formids.json')}
        self.params['persistent_ids'] = True
        second, _ = self.build(obj, 'mixed-bootstrap', bootstrap=True)
        self.assertEqual(first, second)
        self.assertEqual(old, {name: (stage / name).read_bytes() for name in old})
        third, _ = self.build(self.reorder(obj), 'mixed-bootstrap')
        self.assertEqual(first, third)

    def test_light_identity_uses_source_plugin_and_refuses_invalid_source_without_publication(self):
        obj = self.mixed()
        obj['lights'][0]['src'] = '00A001:One.esm'
        obj['lights'][1]['src'] = '00A001:Two.esm'
        first, stage = self.build(obj, 'light-source-owners')
        self.assertNotEqual(first['lights']['00A001:One.esm']['ref'], first['lights']['00A001:Two.esm']['ref'])
        second, _ = self.build(self.reorder(obj), 'light-source-owners')
        self.assertEqual(first, second)
        names = ('Synthetic.esm', 'formids.json', 'terrain-stable-ids.json')
        before = {name: (stage / name).read_bytes() for name in names}
        obj['lights'][0]['src'] = 'not-a-source-key'
        proc, _ = self.run_writer(obj, 'light-source-owners')
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(before, {name: (stage / name).read_bytes() for name in names})


if __name__ == '__main__':
    unittest.main()
