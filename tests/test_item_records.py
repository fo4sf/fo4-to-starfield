"""Independent serialized MISC audit controls; no converted/game files."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_container_records as fixtures

cr = fixtures.cr


class ItemRecordTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ContainerRecordTests()
        self.fixture.setUp()
        f = self.fixture
        f.objects['items'] = f.objects.pop('containers')
        item = f.objects['items'][0]
        item.pop('items')
        item.update(value=7, weight=.25)
        f.ids['items'] = f.ids.pop('containers')
        f.base_fields = [(s, d) for s, d in f.base_fields if s != 'CNTO'] + [('DATA', struct.pack('<if', 7, .25))]

    def blob(self, **kw):
        return self.fixture.blob(**kw).replace(b'CONT', b'MISC')

    def audit(self, blob=None):
        f = self.fixture
        return cr.audit(self.blob() if blob is None else blob, f.objects, f.ids,
                        plugin_name='Fixture.esm', baseline=f.baseline, kind='items')

    def test_valid_item_and_float32_weight(self):
        report = self.audit()
        self.assertTrue(report['offline_passed'], report)
        self.assertEqual((report['audit_kind'], report['items_checked'], report['item_base_records']), ('items', 1, 1))
        self.assertFalse(report['runtime_accepted'])
        self.fixture.objects['items'][0]['weight'] = .1
        fields = [(s, struct.pack('<if', 7, .1) if s == 'DATA' else d) for s, d in self.fixture.base_fields]
        self.assertTrue(self.audit(self.blob(base=fields))['offline_passed'])

    def test_malformed_or_wrong_item_data_refuses(self):
        good = self.fixture.base_fields
        cases = [struct.pack('<if', v, w) for v, w in [(8,.25),(-1,.25),(7,.5),(7,-.25),
                   (7,float('nan')),(7,float('inf')),(7,-float('inf'))]] + [b'', b'1234567', b'123456789']
        for payload in cases:
            with self.subTest(payload=payload.hex()):
                fields = [(s, payload if s == 'DATA' else d) for s, d in good]
                self.assertFalse(self.audit(self.blob(base=fields))['offline_passed'])
        self.assertFalse(self.audit(self.blob(base=good+[('DATA',struct.pack('<if',7,.25))]))['offline_passed'])

    def test_nonfinite_placement_and_deleted_item_refuse(self):
        for component in (0,3):
            vals = [10,20,1,0,0,.5]; vals[component] = float('nan')
            fields = [(s, struct.pack('<6f', *vals) if s == 'DATA' else d) for s,d in self.fixture.ref_fields]
            self.assertFalse(self.audit(self.blob(ref=fields))['offline_passed'])
        fields = [(s, struct.pack('<f',float('nan')) if s == 'XSCL' else d) for s,d in self.fixture.ref_fields]
        self.assertFalse(self.audit(self.blob(ref=fields))['offline_passed'])
        self.assertFalse(self.audit(self.blob(flags=0x20))['offline_passed'])

    def test_invalid_expected_item_values_refuse(self):
        item = self.fixture.objects['items'][0]
        for field, value in [('value',True),('value',-1),('value',2**31),('weight',float('nan')),
                             ('weight',float('inf')),('weight',-1),('weight',4e38)]:
            with self.subTest(field=field,value=value):
                previous = item[field]; item[field] = value
                self.assertFalse(self.audit()['offline_passed'])
                item[field] = previous

    def test_mixed_reference_and_base_aliases_refuse(self):
        self.fixture.ids['containers'] = {'other': {'base':'000806','ref':'000804'}}
        self.assertFalse(self.audit()['offline_passed'])
        self.fixture.ids['containers']['other'] = {'base':'000803','ref':'000806'}
        self.assertFalse(self.audit()['offline_passed'])

    def test_container_mode_detects_item_reference_alias(self):
        f = fixtures.ContainerRecordTests(); f.setUp()
        f.ids['items'] = {'other': {'base':'000806','ref':'000804'}}
        report = cr.audit(f.blob(), f.objects, f.ids, plugin_name='Fixture.esm', baseline=f.baseline)
        self.assertFalse(report['offline_passed'], report)

    def test_item_base_migration_is_checked_against_baseline(self):
        f = self.fixture
        del f.baseline['refs'][f.src]
        f.baseline['items'] = deepcopy(f.ids['items'])
        self.assertTrue(self.audit()['offline_passed'])
        f.baseline['items'][f.src]['base'] = '000809'
        self.assertFalse(self.audit()['offline_passed'])

    def test_cli_selects_items_and_pins_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'Fixture.esm').write_bytes(self.blob())
            (root/'objects.json').write_text(json.dumps(self.fixture.objects))
            (root/'ids.json').write_text(json.dumps(self.fixture.ids))
            args = ['audit','--kind','items','--plugin',str(root/'Fixture.esm'),
                    '--objects',str(root/'objects.json'),'--ids',str(root/'ids.json'),'--out',str(root/'report.json')]
            with patch.object(sys,'argv',args):
                self.assertEqual(cr.main(),0)
                self.assertEqual(cr.main(),2)
            report=json.loads((root/'report.json').read_text())
            self.assertEqual(report['audit_kind'],'items')
            self.assertEqual(len(report['input_sha256']),3)


if __name__ == '__main__':
    unittest.main()
