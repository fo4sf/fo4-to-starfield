"""Mixed-map identity controls; unselected record contents remain unaudited."""
from copy import deepcopy
import unittest

import test_container_records as containers
import test_item_records as items

cr = containers.cr


class PromotedMapAuditTests(unittest.TestCase):
    categories = ('activators', 'terminals', 'workshops', 'benches', 'doors')

    def fixture(self, kind):
        if kind == 'items':
            item = items.ItemRecordTests()
            item.setUp()
            return item.fixture, item.blob()
        container = containers.ContainerRecordTests()
        container.setUp()
        return container, container.blob()

    def audit(self, f, blob, kind):
        return cr.audit(blob, f.objects, f.ids, plugin_name='Fixture.esm', baseline=f.baseline, kind=kind)

    def test_other_class_reference_alias_is_rejected(self):
        for kind in ('containers', 'items'):
            for category in self.categories:
                with self.subTest(kind=kind, category=category):
                    f, blob = self.fixture(kind)
                    f.ids[category] = {'other': {'base': '000900', 'ref': '000804'}}
                    self.assertFalse(self.audit(f, blob, kind)['offline_passed'])

    def test_other_class_source_duplicate_is_rejected(self):
        for kind in ('containers', 'items'):
            for category in self.categories:
                with self.subTest(kind=kind, category=category):
                    f, blob = self.fixture(kind)
                    f.ids[category] = {f.src: {'base': '000900', 'ref': '000901'}}
                    self.assertFalse(self.audit(f, blob, kind)['offline_passed'])

    def test_other_owned_base_cannot_alias_selected_base(self):
        for kind in ('containers', 'items'):
            for category in ('activators', 'terminals', 'workshops', 'doors'):
                with self.subTest(kind=kind, category=category):
                    f, blob = self.fixture(kind)
                    f.ids[category] = {'other': {'base': '000803', 'ref': '000901'}}
                    self.assertFalse(self.audit(f, blob, kind)['offline_passed'])

    def test_baseline_other_class_reference_must_remain_stable(self):
        for kind in ('containers', 'items'):
            for category in self.categories:
                with self.subTest(kind=kind, category=category):
                    f, blob = self.fixture(kind)
                    f.baseline[category] = {'other': {'base': '000900', 'ref': '000901'}}
                    f.ids[category] = deepcopy(f.baseline[category])
                    self.assertTrue(self.audit(f, blob, kind)['offline_passed'])
                    f.ids[category]['other']['ref'] = '000902'
                    self.assertFalse(self.audit(f, blob, kind)['offline_passed'])

    def test_valid_vanilla_bench_key_does_not_become_local_base(self):
        for kind in ('containers', 'items'):
            with self.subTest(kind=kind):
                f, blob = self.fixture(kind)
                f.ids['benches'] = {'other': {'base': '2B6A63:Starfield.esm', 'ref': '000901', 'kind': 'weapon'}}
                f.baseline['benches'] = deepcopy(f.ids['benches'])
                report = self.audit(f, blob, kind)
                self.assertTrue(report['offline_passed'], report)
                self.assertFalse(report['runtime_accepted'])

    def test_other_owned_baseline_base_must_remain_stable(self):
        for kind in ('containers', 'items'):
            for category in ('activators', 'terminals', 'workshops', 'doors'):
                with self.subTest(kind=kind, category=category):
                    f, blob = self.fixture(kind)
                    f.baseline[category] = {'other': {'base': '000900', 'ref': '000901'}}
                    f.ids[category] = deepcopy(f.baseline[category])
                    self.assertTrue(self.audit(f, blob, kind)['offline_passed'])
                    f.ids[category]['other']['base'] = '000902'
                    self.assertFalse(self.audit(f, blob, kind)['offline_passed'])

    def test_malformed_other_reference_refuses(self):
        for category in self.categories:
            with self.subTest(category=category):
                f, blob = self.fixture('containers')
                f.ids[category] = {'other': {'base': '000900', 'ref': 'not-a-form-id'}}
                report = self.audit(f, blob, 'containers')
                self.assertFalse(report['offline_passed'])
                self.assertTrue(report['errors'])
