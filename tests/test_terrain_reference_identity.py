"""Run the actual terrain writer on a three-record synthetic master, never a game."""
import copy
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]


def records(path):
    data = path.read_bytes()
    out = {}

    def walk(start, end, owner=None):
        pos = start
        while pos < end:
            sig, size = data[pos:pos + 4], struct.unpack_from('<I', data, pos + 4)[0]
            if sig == b'GRUP':
                label, kind = struct.unpack_from('<II', data, pos + 8)
                walk(pos + 24, pos + size, label & 0xFFFFFF if kind in (6, 8, 9) else owner)
                pos += size
            else:
                flags, form = struct.unpack_from('<II', data, pos + 8)
                payload = data[pos + 24:pos + 24 + size]
                if flags & 0x40000:
                    payload = zlib.decompress(payload[4:])
                if form:
                    if form & 0xFFFFFF in out:
                        raise AssertionError('duplicate serialized identity')
                    out[form & 0xFFFFFF] = (sig, payload, owner, flags)
                pos += 24 + size
        if pos != end:
            raise AssertionError('bad synthetic record framing')
    walk(0, len(data))
    return out


def without_base(record):
    payload = record[1]
    kept, pos = [], 0
    while pos < len(payload):
        sig, size = payload[pos:pos + 4], struct.unpack_from('<H', payload, pos + 4)[0]
        if sig != b'NAME':
            kept.append(payload[pos:pos + 6 + size])
        pos += 6 + size
    return kept, record[2], record[3]


class TerrainReferenceIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which('dotnet')
        if not cls.dotnet:
            raise unittest.SkipTest('.NET 9 SDK/runtime needed for actual writer test')
        sdks = subprocess.run([cls.dotnet, '--list-sdks'], capture_output=True, text=True, check=True)
        if not any(line.startswith('9.') for line in sdks.stdout.splitlines()):
            raise unittest.SkipTest('.NET 9 SDK/runtime needed for actual writer test')
        build = subprocess.run([cls.dotnet, 'build', str(ROOT / 'dotnet/TerrainIdentityFixture'),
                                '-c', 'Release', '--nologo'], capture_output=True, text=True)
        if build.returncode:
            raise AssertionError(build.stdout + build.stderr)
        evidence = os.environ.get('FO4SF_IDENTITY_EVIDENCE_DIR')
        if evidence:
            cls.root = Path(evidence).resolve()
            cls.root.mkdir(parents=True, exist_ok=False)
        else:
            temporary = tempfile.TemporaryDirectory(prefix='fo4sf-identity-')
            cls.addClassCleanup(temporary.cleanup)
            cls.root = Path(temporary.name)
        (cls.root / 'build.log').write_text(build.stdout + build.stderr, encoding='utf-8')
        cls.master = cls.root / 'master/Starfield.esm'
        fixture = ROOT / 'dotnet/TerrainIdentityFixture/bin/Release/net9.0/TerrainIdentityFixture.dll'
        subprocess.run([cls.dotnet, str(fixture), str(cls.master)], capture_output=True, check=True)
        cls.writer = Path(os.environ.get('FO4SF_TERRAIN_WRITER', ROOT / 'dotnet/TerrainOverlays/bin/Release/net9.0/TerrainOverlays.dll'))
        cls.params = {'plugin': 'Synthetic.esm', 'hmin': 0, 'hmax': 1, 'alignment': 'absolute', 'hnam': 0,
                      'objects': 'objects.json', 'overlays': [{'world': 'SyntheticWorld', 'block': 'SyntheticBlock',
                      'location': 'SyntheticLocation', 'tag': 'Synthetic', 'n': 2, 'cell_min': 0, 'cell_max': 1,
                      'btd_path': 'Terrain/Synthetic.btd', 'fnam': [0] * 4, 'bounds_min_m': 0, 'bounds_max_m': 200,
                      'spawn': [1, 1, 2], 'spawn_cell': [0, 0], 'coc': 'SyntheticSpawn',
                      'anchor': {'form_id': 0x800, 'edid': 'SyntheticAnchor', 'local': [1, 1, 2]}}]}
        cls.objects = {'world': 'SyntheticWorld', 'bases': [{'edid': 'SyntheticBase', 'model': 'synthetic.nif'}],
                       'refs': [{'src': f'{i + 1:06X}:Synthetic.esm', 'base': 0, 'cell': cell,
                                 'pos': pos, 'rot': [0, 0, i / 10], 'scale': 1 + i / 10, 'disabled': False}
                                for i, (cell, pos) in enumerate(zip(([0, 0], [0, 1], [1, 1]), ([1, 2, 3], [4, 101, 6], [101, 102, 9])))]}

    def run_writer(self, objects, name):
        stage = self.root / name
        stage.mkdir(exist_ok=True)
        suffix = len(list(stage.glob('run-*.log')))
        (stage / 'overlays_params.json').write_text(json.dumps(self.params), encoding='utf-8')
        (stage / 'objects.json').write_text(json.dumps(objects), encoding='utf-8')
        (stage / f'objects-run-{suffix}.json').write_text(json.dumps(objects), encoding='utf-8')
        proc = subprocess.run([self.dotnet, str(self.writer), str(self.master), str(stage)], capture_output=True, text=True)
        # Distinct names preserve successive negative observations in the same stage.
        (stage / f'run-{suffix}.log').write_text(proc.stdout + proc.stderr, encoding='utf-8')
        return proc, stage

    def promote(self, indices):
        obj = copy.deepcopy(self.objects)
        obj['containers'] = [dict(obj['refs'][i], reference_index=i, edid=f'SyntheticContainer{i}',
                                 model='synthetic.nif', name=f'Synthetic {i}',
                                 items=[{'form': 'Starfield.esm:00000F', 'count': 25}]) for i in indices]
        obj['refs'] = [r for i, r in enumerate(obj['refs']) if i not in indices]
        return obj

    def assert_preserved(self, indices, name):
        before, baseline = self.run_writer(self.objects, f'{name}-before')
        after, candidate = self.run_writer(self.promote(indices), f'{name}-after')
        self.assertEqual(before.returncode, 0, before.stderr)
        self.assertEqual(after.returncode, 0, after.stderr)
        old = json.loads((baseline / 'formids.json').read_text())
        new = json.loads((candidate / 'formids.json').read_text())
        combined = dict(new['refs'], **{src: v['ref'] for src, v in new['containers'].items()})
        self.assertEqual(combined, old['refs'])
        self.assertEqual(new['bases'], old['bases'])
        old_records, new_records = records(baseline / 'Synthetic.esm'), records(candidate / 'Synthetic.esm')
        for src, identity in old['refs'].items():
            key = int(identity, 16)
            self.assertEqual(new_records[key][0], b'REFR')
            if src in new['containers']:
                self.assertEqual(without_base(new_records[key]), without_base(old_records[key]))
            else:
                self.assertEqual(new_records[key], old_records[key])
        for info in new['containers'].values():
            self.assertGreater(int(info['base'], 16), max(old_records))
            self.assertEqual(new_records[int(info['base'], 16)][0], b'CONT')

    def test_middle_promotion_preserves_all_serialized_source_references(self):
        self.assert_preserved([1], 'middle')

    def test_first_and_last_promotions_preserve_all_slots(self):
        self.assert_preserved([0], 'first')
        self.assert_preserved([2], 'last')
        self.assert_preserved([2, 0], 'multiple-reversed')

    def test_ambiguous_identity_inputs_do_not_replace_existing_plugin_or_map(self):
        good = self.promote([1])
        proc, stage = self.run_writer(good, 'refusals')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        pinned = {n: (stage / n).read_bytes() for n in ('Synthetic.esm', 'formids.json')}
        invalid = []
        missing = copy.deepcopy(good)
        del missing['containers'][0]['reference_index']
        invalid.append(missing)
        for index in (-1, 3):
            bad = copy.deepcopy(good)
            bad['containers'][0]['reference_index'] = index
            invalid.append(bad)
        duplicate = self.promote([0, 2])
        duplicate['containers'][1]['reference_index'] = 0
        invalid.append(duplicate)
        alias = copy.deepcopy(good)
        alias['refs'][0]['src'] = alias['containers'][0]['src'].lower()
        invalid.append(alias)
        for objects in invalid:
            proc, _ = self.run_writer(objects, 'refusals')
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual({n: (stage / n).read_bytes() for n in pinned}, pinned)
