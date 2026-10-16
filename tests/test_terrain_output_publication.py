"""Real helper/writer failures on synthetic artifacts; never game installations."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import stage_outputs
import test_terrain_reference_identity as identity


class TerrainOutputPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_type = type('PublicationFixture', (identity.TerrainReferenceIdentityTests,), {})
        cls.fixture_type.setUpClass()
        cls.addClassCleanup(cls.fixture_type.doClassCleanups)
        cls.root = cls.fixture_type.root
        cls.fixture = ROOT / 'dotnet/TerrainIdentityFixture/bin/Release/net9.0/TerrainIdentityFixture.dll'

    def setUp(self):
        self.case = self.fixture_type(methodName='test_middle_promotion_preserves_all_serialized_source_references')

    def publisher(self, mode):
        path = self.root / self._testMethodName
        path.mkdir()
        originals = {n: ('old:' + n).encode() for n in ('Synthetic.esm', 'formids.json', 'Registration.esm')}
        for name, data in originals.items():
            (path / name).write_bytes(data)
        proc = subprocess.run([self.fixture_type.dotnet, str(self.fixture), '--publish-fixture', str(path), mode],
                              capture_output=True, text=True)
        (path / 'process.log').write_text(proc.stdout + proc.stderr, encoding='utf-8')
        return proc, path, originals

    def test_three_outputs_publish_together_and_retain_previous_bytes(self):
        proc, path, old = self.publisher('normal')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for name, value in old.items():
            self.assertEqual((path / name).read_bytes(), ('new:' + name).encode())
            self.assertEqual(next(path.glob(f'.fo4sf-output-*/old/{name}')).read_bytes(), value)
        self.assertFalse((path / stage_outputs.PENDING).exists())
        stage_outputs.require_ready_stage(path)

    def test_fault_after_first_publication_restores_all_three_outputs(self):
        proc, path, old = self.publisher('fail')
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual({n: (path / n).read_bytes() for n in old}, old)
        self.assertFalse((path / stage_outputs.PENDING).exists())
        self.assertTrue(list(path.glob('.fo4sf-output-*/rolled-back.jsonl')))
        stage_outputs.require_ready_stage(path)

    def test_concurrent_owner_file_is_preserved_with_recovery_block(self):
        proc, path, old = self.publisher('owner')
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual((path / 'formids.json').read_bytes(), b'owner-created file')
        self.assertEqual((path / 'Synthetic.esm').read_bytes(), old['Synthetic.esm'])
        self.assertEqual((path / 'Registration.esm').read_bytes(), old['Registration.esm'])
        journal = [json.loads(line) for line in (path / stage_outputs.PENDING).read_text().splitlines()]
        self.assertEqual(journal[-1]['phase'], 'recovery-required')
        recovery = path / journal[-1]['recovery_directory']
        self.assertEqual((recovery / 'old/formids.json').read_bytes(), old['formids.json'])
        self.assertEqual((recovery / 'new/formids.json').read_bytes(), b'new:formids.json')
        with self.assertRaisesRegex(ValueError, 'publication is pending'):
            stage_outputs.require_ready_stage(path)

    def test_abrupt_exit_retains_durable_recovery_state(self):
        proc, path, old = self.publisher('crash')
        self.assertEqual(proc.returncode, 17)
        journal = [json.loads(line) for line in (path / stage_outputs.PENDING).read_text().splitlines()]
        recovery = path / journal[-1]['recovery_directory']
        for name, value in old.items():
            self.assertEqual((recovery / 'old' / name).read_bytes(), value)
        self.assertEqual((path / 'Synthetic.esm').read_bytes(), b'new:Synthetic.esm')
        with self.assertRaisesRegex(ValueError, 'publication is pending'):
            stage_outputs.require_ready_stage(path)
        again = subprocess.run([self.fixture_type.dotnet, str(self.fixture), '--publish-fixture', str(path), 'normal'],
                               capture_output=True, text=True)
        self.assertNotEqual(again.returncode, 0)
        self.assertEqual((path / 'Synthetic.esm').read_bytes(), b'new:Synthetic.esm')

    @unittest.skipUnless(os.name == 'nt', 'native Windows sharing-denial regression')
    def test_locked_real_plugin_does_not_replace_its_map(self):
        from fo4sf.checkpoints import _open_archive_windows
        proc, path = self.case.run_writer(self.fixture_type.objects, 'real-locked')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        old = {n: (path / n).read_bytes() for n in ('Synthetic.esm', 'formids.json')}
        with _open_archive_windows(path / 'Synthetic.esm'):
            proc, _ = self.case.run_writer(self.case.promote([1]), 'real-locked')
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual({n: (path / n).read_bytes() for n in old}, old)
        stage_outputs.require_ready_stage(path)

    def test_optional_mars_preparation_failure_preserves_real_existing_pair(self):
        proc, path = self.case.run_writer(self.fixture_type.objects, 'real-mars-failure')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        old = {n: (path / n).read_bytes() for n in ('Synthetic.esm', 'formids.json')}
        self.case.params = copy.deepcopy(self.fixture_type.params)
        self.case.params['mars'] = {'plugin': 'MissingPlanet.esm'}  # synthetic master deliberately has no planet
        proc, _ = self.case.run_writer(self.case.promote([1]), 'real-mars-failure')
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual({n: (path / n).read_bytes() for n in old}, old)
        self.assertFalse((path / 'MissingPlanet.esm').exists())
        stage_outputs.require_ready_stage(path)

    def test_real_mars_registration_publishes_with_plugin_and_map(self):
        master = self.root / 'mars-master/Starfield.esm'
        generated = subprocess.run([self.fixture_type.dotnet, str(self.fixture), '--master-with-mars', str(master)],
                                   capture_output=True, text=True)
        (self.root / 'mars-master.log').write_text(generated.stdout + generated.stderr, encoding='utf-8')
        self.assertEqual(generated.returncode, 0, generated.stderr)
        self.case.master = master
        self.case.params = copy.deepcopy(self.fixture_type.params)
        self.case.params['mars'] = {'plugin': 'Synthetic_Mars.esm'}
        self.case.params['overlays'][0].update(latitude=0.1, longitude=0.2)
        proc, path = self.case.run_writer(self.fixture_type.objects, 'real-mars-success')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(json.loads((path / 'formids.json').read_text())['refs'])
        self.assertTrue(any(r[0] == b'WRLD' for r in identity.records(path / 'Synthetic.esm').values()))
        self.assertTrue(any(r[0] == b'PNDT' for r in identity.records(path / 'Synthetic_Mars.esm').values()))
        stage_outputs.require_ready_stage(path)
