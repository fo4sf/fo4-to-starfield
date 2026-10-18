"""Full source identities for native CONT/MISC promotions, synthetic inputs only."""
import unittest
from unittest.mock import patch

from test_make_core64c import mk


class PromotedSourceIdentityTests(unittest.TestCase):
    def test_distinct_base_plugins_never_share_either_record_class(self):
        pairs = [('A-B.esm', 'AB.esm'), ('AB.esm', 'AB.esp'), ('A_B.esm', 'A.B.esm'),
                 ('Ma\u00dfe.esm', 'Masse.esm')]
        for helper in (mk.container_edid, mk.item_edid):
            for a, b in pairs:
                with self.subTest(helper=helper.__name__, plugins=(a, b)):
                    self.assertNotEqual(helper('000123:' + a, 'unused'), helper('000123:' + b, 'unused'))

    def test_unshared_reference_keys_retain_plugin_identity(self):
        for helper in (mk.container_edid, mk.item_edid):
            for a, b in [('Fallout4.esm', 'Other.esm'), ('A-B.esm', 'AB.esm'), ('AB.esm', 'AB.esp')]:
                with self.subTest(helper=helper.__name__, plugins=(a, b)):
                    self.assertNotEqual(helper(None, '000123:' + a), helper(None, '000123:' + b))

    def test_legacy_fallout_and_ascii_case_sharing_are_preserved(self):
        for kind, helper in [('cont', mk.container_edid), ('misc', mk.item_edid)]:
            self.assertEqual(helper('04B6E9:Fallout4.esm', 'x'), 'FO4Core_' + kind + '_04b6e9_fallout4')
            self.assertEqual(helper(None, '19EE52:Fallout4.esm'), 'FO4Core_' + kind + '_19ee52')
            self.assertEqual(helper('04B6E9:A-B.esm', 'x'), helper('04b6e9:a-b.ESM', 'y'))
        self.assertNotEqual(mk.container_edid('000123:A.esm', 'x'), mk.item_edid('000123:A.esm', 'x'))

    @staticmethod
    def fixture(source_bases):
        bases = [{'model': 'synthetic.nif'}]
        placed = [dict(src=f'{i:06X}:Fallout4.esm', base=0, cell=[0, 0], pos=[i, 0, 0],
                       rot=[0, 0, 0], scale=1.0) for i in (1, 2)]
        cluster = {'items': [dict(src=p['src'], base=b, name='Item', value=7, weight=0.25)
                             for p, b in zip(placed, source_bases)]}
        return bases, placed, cluster

    def test_item_collision_is_refused_even_when_metadata_matches(self):
        args = self.fixture(['000123:A.esm', '000123:B.esm'])
        with patch.object(mk, 'item_edid', return_value='ForcedCollision'):
            with self.assertRaisesRegex(ValueError, 'distinct source identities'):
                mk.cluster_items(*args)

    def test_item_same_source_case_variants_share_and_keep_slots(self):
        args = self.fixture(['000123:A-B.esm', '000123:a-b.ESM'])
        keep, items = mk.cluster_items(*args)
        self.assertEqual(keep, [])
        self.assertEqual(len({i['edid'] for i in items}), 1)
        self.assertEqual([i['reference_index'] for i in items], [0, 1])
        self.assertEqual([i['pos'] for i in items], [[1, 0, 0], [2, 0, 0]])


if __name__ == '__main__':
    unittest.main()
