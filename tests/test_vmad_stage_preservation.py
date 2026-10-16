"""Door post-pass must leave its pinned inputs and existing behavior untouched."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import test_vmad_patch as fixture

vp = fixture.vp


class DoorStagePreservationTests(unittest.TestCase):
    def setUp(self):
        evidence = os.environ.get('FO4SF_DOOR_PATCH_EVIDENCE')
        if evidence:
            self.root = Path(evidence) / self._testMethodName
            self.root.mkdir(parents=True, exist_ok=False)
        else:
            temporary = tempfile.TemporaryDirectory(prefix='fo4sf-door-stage-')
            self.addCleanup(temporary.cleanup)
            self.root = Path(temporary.name)
        self.port, self.core, self.out = (self.root / n for n in ('port', 'core', 'out'))
        self.port.mkdir()
        (self.port / 'FO4Port.esm').write_bytes(fixture.tiny_plugin())
        (self.port / 'formids.json').write_text(json.dumps({'CELL:FO4Port_Test': 0x801}), encoding='utf-8')
        fixture.core_folder(str(self.core), [fixture.door_entry()])

    @staticmethod
    def snapshot(folder):
        return {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob('*') if p.is_file()}

    def cli(self, operation):
        p = subprocess.run([sys.executable, '-I', '-B', vp.__file__, operation,
                            '--port', str(self.port), '--core', str(self.core), '--out', str(self.out)],
                           capture_output=True, text=True)
        (self.root / (operation + '.log')).write_text(p.stdout + p.stderr, encoding='utf-8')
        return p

    def existing_script(self, vmad):
        plugin = vp.Plugin.read(str(self.port / 'FO4Port.esm'))
        plugin.set_vmad(fixture.OWN | 0x802, vmad)
        (self.port / 'FO4Port.esm').write_bytes(plugin.serialize())

    def test_port_and_check_preserve_all_source_files(self):
        for name in ('README.txt', 'doors.json', 'doors_check.json', 'keep.txt'):
            (self.port / name).write_bytes(('original ' + name).encode())
        before, core_before = self.snapshot(self.port), self.snapshot(self.core)
        p = self.cli('port')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(before, self.snapshot(self.port))
        self.assertFalse((self.out / 'doors_check.json').exists(), 'old acceptance report was carried into new stage')
        p = self.cli('check')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(before, self.snapshot(self.port))
        self.assertEqual(core_before, self.snapshot(self.core))
        for name in ('README.txt', 'doors.json', 'doors_check.json', 'FO4Port.esm', 'formids.json'):
            self.assertFalse((self.port / name).samefile(self.out / name), name)

    def test_generated_names_are_reserved_case_insensitively(self):
        names = ('rEaDmE.TxT', 'dOoRs.JsOn', 'dOoRs_ChEcK.JsOn')
        for name in names:
            (self.port / name).write_bytes(b'original mixed case')
        before = self.snapshot(self.port)
        p = self.cli('port')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(before, self.snapshot(self.port))
        self.assertNotIn('doors_check.json', {p.name.casefold() for p in self.out.iterdir()})
        self.assertEqual(sum(p.name.casefold() == 'readme.txt' for p in self.out.iterdir()), 1)

    def test_existing_behavior_refuses_before_output(self):
        self.existing_script(vp.encode([{'name': 'PreserveExistingBehavior', 'status': 0, 'properties': []}]))
        before = self.snapshot(self.port)
        p = self.cli('port')
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('existing VMAD', p.stderr)
        self.assertFalse(self.out.exists())
        self.assertEqual(before, self.snapshot(self.port))

    def test_matching_load_door_script_is_not_silently_replaced(self):
        self.existing_script(vp.load_door_vmad('FO4TerrainCore.esm', 0xA5E20))
        before = self.snapshot(self.port)
        p = self.cli('port')
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('existing VMAD', p.stderr)
        self.assertFalse(self.out.exists())
        self.assertEqual(before, self.snapshot(self.port))

    def test_late_existing_vmad_preflight_preserves_in_memory_plugin(self):
        plugin = vp.Plugin.read(str(self.port / 'FO4Port.esm'))
        plugin.set_vmad(fixture.OWN | 0x803, vp.encode([]))
        before = plugin.serialize()
        entries = [fixture.door_entry(), fixture.door_entry(src='000002:Synthetic.esm', dest_id=0x805, ref='000803')]
        edits = vp.port_edits('FO4TerrainCore.esm', entries, 'FO4Port.esm', 0x804)
        with self.assertRaisesRegex(ValueError, 'existing VMAD'):
            vp.patch_port(plugin, edits, 1)
        self.assertEqual(plugin.serialize(), before)

    def test_duplicate_marker_map_refuses_before_output(self):
        ids = {'CELL:FO4Port_Test': 0x801, 'MARK:FO4Port_Test:0EE661:Fallout4.esm': 0x800}
        (self.port / 'formids.json').write_text(json.dumps(ids), encoding='utf-8')
        before = self.snapshot(self.port)
        p = self.cli('port')
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('already has', p.stderr)
        self.assertFalse(self.out.exists())
        self.assertEqual(before, self.snapshot(self.port))

    def test_check_breaks_old_report_hardlink_without_changing_source(self):
        p = self.cli('port')
        self.assertEqual(p.returncode, 0, p.stderr)
        old = self.port / 'doors_check.json'
        old.write_bytes(b'old source acceptance evidence')
        os.link(old, self.out / 'doors_check.json')
        before = self.snapshot(self.port)
        p = self.cli('check')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(before, self.snapshot(self.port))
        self.assertFalse(old.samefile(self.out / 'doors_check.json'))

    def test_failed_report_replacement_keeps_source_and_previous_report(self):
        self.out.mkdir()
        source = self.port / 'doors_check.json'
        source.write_bytes(b'previous evidence')
        report = self.out / 'doors_check.json'
        os.link(source, report)
        with mock.patch.object(vp.os, 'replace', side_effect=OSError('injected replace failure')):
            with self.assertRaisesRegex(OSError, 'injected replace failure'):
                vp.write_output(str(report), b'new evidence')
        self.assertEqual(source.read_bytes(), b'previous evidence')
        self.assertEqual(report.read_bytes(), b'previous evidence')
        self.assertEqual([p.name for p in self.out.iterdir()], ['doors_check.json'])

    def test_nested_output_refuses_before_recursive_linking(self):
        # Bound the old regression at the copy boundary rather than let os.walk
        # recursively link its own newly-created output into the pinned input.
        for parent in (self.port, self.core):
            with self.subTest(parent=parent.name):
                before = self.snapshot(parent)
                output = parent / 'nested-output'
                with mock.patch.object(vp, 'link_folder', side_effect=AssertionError('recursive copy attempted')) as copy:
                    with self.assertRaisesRegex(ValueError, 'inside input'):
                        vp.main(['port', '--port', str(self.port), '--core', str(self.core), '--out', str(output)])
                    copy.assert_not_called()
                self.assertFalse(output.exists())
                self.assertEqual(before, self.snapshot(parent))


if __name__ == '__main__':
    unittest.main()
