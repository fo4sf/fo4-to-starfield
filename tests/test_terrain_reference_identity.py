"""Run the actual terrain writer on a small synthetic master (dotnet/TerrainIdentityFixture), never a game."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
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


def subrecords(payload):
    pos = 0
    while pos < len(payload):
        sig, size = payload[pos:pos + 4], struct.unpack_from('<H', payload, pos + 4)[0]
        yield sig, payload[pos + 6:pos + 6 + size]
        pos += 6 + size


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

    def promote(self, indices, items=()):
        obj = copy.deepcopy(self.objects)
        obj['containers'] = [dict(obj['refs'][i], reference_index=i, edid=f'SyntheticContainer{i}',
                                 model='synthetic.nif', name=f'Synthetic {i}',
                                 items=[{'form': 'Starfield.esm:00000F', 'count': 25}]) for i in indices]
        if items:
            # loose items of one FO4 base: one shared MISC edid (make_core64c.cluster_items)
            obj['items'] = [dict(obj['refs'][i], reference_index=i, edid='SyntheticMisc', model='synthetic.nif',
                                 name='Synthetic item', value=7, weight=0.25) for i in items]
        obj['refs'] = [r for i, r in enumerate(obj['refs']) if i not in indices and i not in items]
        return obj

    def assert_preserved(self, indices, name, items=()):
        before, baseline = self.run_writer(self.objects, f'{name}-before')
        after, candidate = self.run_writer(self.promote(indices, items), f'{name}-after')
        self.assertEqual(before.returncode, 0, before.stderr)
        self.assertEqual(after.returncode, 0, after.stderr)
        old = json.loads((baseline / 'formids.json').read_text())
        new = json.loads((candidate / 'formids.json').read_text())
        self.assertNotIn('items', old)                 # a build without items keeps its formids.json shape
        promoted = dict(new['containers'], **new.get('items', {}))
        combined = dict(new['refs'], **{src: v['ref'] for src, v in promoted.items()})
        self.assertEqual(combined, old['refs'])
        self.assertEqual(new['bases'], old['bases'])
        old_records, new_records = records(baseline / 'Synthetic.esm'), records(candidate / 'Synthetic.esm')
        for src, identity in old['refs'].items():
            key = int(identity, 16)
            self.assertEqual(new_records[key][0], b'REFR')
            if src in promoted:
                self.assertEqual(without_base(new_records[key]), without_base(old_records[key]))
                name = next(d for sig, d in subrecords(new_records[key][1]) if sig == b'NAME')
                self.assertEqual(struct.unpack_from('<I', name)[0] & 0xFFFFFF, int(promoted[src]['base'], 16))
            else:
                self.assertEqual(new_records[key], old_records[key])
        for info in new['containers'].values():
            self.assertGreater(int(info['base'], 16), max(old_records))
            self.assertEqual(new_records[int(info['base'], 16)][0], b'CONT')
        last_cont = max([max(old_records)] + [int(c['base'], 16) for c in new['containers'].values()])
        for info in new.get('items', {}).values():
            self.assertGreater(int(info['base'], 16), last_cont)                     # MISC after every CONT
            self.assertEqual(new_records[int(info['base'], 16)][0], b'MISC')
        if items:
            self.assertEqual(len({info['base'] for info in new['items'].values()}), 1)   # one MISC per edid
            base = new_records[int(next(iter(new['items'].values()))['base'], 16)]
            fields = dict(subrecords(base[1]))
            self.assertEqual(fields[b'EDID'], b'SyntheticMisc' + bytes(1))
            self.assertEqual(fields[b'MODL'], b'synthetic.nif' + bytes(1))
            self.assertEqual(fields[b'FULL'], b'Synthetic item' + bytes(1))
            self.assertEqual(struct.unpack('<if', fields[b'DATA'][:8]), (7, 0.25))
        return new_records

    def test_items_and_containers_mixed_preserve_all_slots(self):
        recs = self.assert_preserved([1], 'mixed-items', items=(2, 0))
        self.assertEqual(sum(1 for r in recs.values() if r[0] == b'MISC'), 1)
        self.assert_preserved([], 'items-only', items=(1,))

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
        clash = self.promote([1], items=(0,))
        clash['items'][0]['reference_index'] = 1                     # an item in the container's slot
        invalid.append(clash)
        disagree = self.promote([], items=(0, 2))
        disagree['items'][1]['value'] = 8                            # one MISC edid, two values
        invalid.append(disagree)
        for objects in invalid:
            proc, _ = self.run_writer(objects, 'refusals')
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual({n: (stage / n).read_bytes() for n in pinned}, pinned)


sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts' / 'terrain'))
_spec = importlib.util.spec_from_file_location('make_core64c', ROOT / 'scripts' / 'terrain' / 'make_core64c.py')
mk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mk)


class ActivatorTerminalWriterTests(unittest.TestCase):
    """Activators and terminals (commonwealth-build-plan.md section 3) through the actual writer: FO4 Activator ->
    ACTI, FO4 Terminal -> TERM + its own TMLM menu, in the one slot plan with containers and items; the raw records
    are read back, and make_core64c's own check (promotion_checks) runs on the written plugin."""
    BODY = 'FO4 terminal (text not ported yet)'

    run_writer = TerrainReferenceIdentityTests.run_writer

    @classmethod
    def setUpClass(cls):
        TerrainReferenceIdentityTests.setUpClass.__func__(cls)          # the same .NET checks, master and writer
        cells = ([0, 0], [0, 1], [1, 1], [1, 0], [0, 0], [1, 1], [0, 1], [1, 0])
        poss = ([1, 2, 3], [4, 101, 6], [101, 102, 9], [102, 5, 7], [7, 8, 9], [150, 160, 2], [30, 140, 4], [120, 9, 1])
        cls.seven = {'world': 'SyntheticWorld', 'bases': [{'edid': 'SyntheticBase', 'model': 'synthetic.nif'},
                                                          {'edid': 'SyntheticTerminalBase', 'model': 'terminal.nif'}],
                     'refs': [{'src': f'{i + 1:06X}:Synthetic.esm', 'base': 1 if i in (5, 6) else 0, 'cell': c,
                               'pos': p, 'rot': [0, 0, i / 10], 'scale': 1 + i / 10, 'disabled': False}
                              for i, (c, p) in enumerate(zip(cells, poss))]}

    def promote_all(self, **change):
        """0 container, 1 item, 2 + 4 one named activator base, 3 an activator without a name, 5 + 6 one terminal base;
        7 stays an ordinary reference."""
        obj = copy.deepcopy(self.seven)
        r = obj['refs']
        obj['containers'] = [dict(r[0], reference_index=0, edid='SyntheticContainer', model='synthetic.nif', name='Box',
                                  items=[{'form': 'Starfield.esm:00000F', 'count': 25}])]
        obj['items'] = [dict(r[1], reference_index=1, edid='SyntheticMisc', model='synthetic.nif', name='Can', value=7,
                             weight=0.25)]
        obj['activators'] = [dict(r[i], reference_index=i, edid=edid, model='synthetic.nif', name=name)
                             for i, edid, name in ((2, 'FO4Core_acti_000100_synthetic', 'Bell'),
                                                   (3, 'FO4Core_acti_000101_synthetic', None),
                                                   (4, 'FO4Core_acti_000100_synthetic', 'Bell'))]
        obj['terminals'] = [dict(r[i], reference_index=i, edid='FO4Core_term_000102_synthetic',
                                 menu_edid='FO4Core_tmlm_000102_synthetic', model='terminal.nif', name='Terminal',
                                 body=self.BODY) for i in (5, 6)]
        for k in ('containers', 'items', 'activators', 'terminals'):
            for e in obj[k]:
                e.pop('base')
                e.pop('disabled')
        obj['refs'] = [r[7]]
        for k, v in change.items():
            v(obj) if callable(v) else obj.__setitem__(k, v)
        return obj

    def test_activators_and_terminals_keep_slots_and_write_native_records(self):
        before, baseline = self.run_writer(self.seven, 'acti-term-before')
        after, candidate = self.run_writer(self.promote_all(), 'acti-term-after')
        self.assertEqual(before.returncode, 0, before.stderr)
        self.assertEqual(after.returncode, 0, after.stderr)
        old = json.loads((baseline / 'formids.json').read_text())
        new = json.loads((candidate / 'formids.json').read_text())
        for k in ('items', 'activators', 'terminals'):
            self.assertNotIn(k, old)                   # a build without a class keeps its formids.json shape
        promoted = {src: v for k in ('containers', 'items', 'activators', 'terminals') for src, v in new[k].items()}
        self.assertEqual(len(promoted), 7)
        combined = dict(new['refs'], **{src: v['ref'] for src, v in promoted.items()})
        self.assertEqual(combined, old['refs'])                                         # every source keeps its REFR id
        self.assertEqual(new['bases'], old['bases'])
        old_records, new_records = records(baseline / 'Synthetic.esm'), records(candidate / 'Synthetic.esm')
        for src, identity in old['refs'].items():
            key = int(identity, 16)
            if src not in promoted:
                self.assertEqual(new_records[key], old_records[key])                    # the ordinary one: unchanged
                continue
            self.assertEqual(without_base(new_records[key]), without_base(old_records[key]))
            name = next(d for sig, d in subrecords(new_records[key][1]) if sig == b'NAME')
            self.assertEqual(struct.unpack_from('<I', name)[0] & 0xFFFFFF, int(promoted[src]['base'], 16))
        # allocation: CONT, MISC, the two ACTI, then TERM followed by its TMLM, all after the last reserved REFR
        cont = int(next(iter(new['containers'].values()))['base'], 16)
        misc = int(next(iter(new['items'].values()))['base'], 16)
        acti = sorted({int(v['base'], 16) for v in new['activators'].values()})
        term = {int(v['base'], 16) for v in new['terminals'].values()}
        menu = {int(v['menu'], 16) for v in new['terminals'].values()}
        self.assertEqual((len(acti), len(term), len(menu)), (2, 1, 1))
        term, menu = term.pop(), menu.pop()
        self.assertEqual([cont, misc] + acti + [term, menu], list(range(max(old_records) + 1, max(old_records) + 7)))
        sigs = {k: new_records[k][0] for k in [cont, misc] + acti + [term, menu]}
        self.assertEqual(list(sigs.values()), [b'CONT', b'MISC', b'ACTI', b'ACTI', b'TERM', b'TMLM'])
        named = dict(subrecords(new_records[int(new['activators']['000003:Synthetic.esm']['base'], 16)][1]))
        quiet = dict(subrecords(new_records[int(new['activators']['000004:Synthetic.esm']['base'], 16)][1]))
        self.assertEqual((named[b'EDID'], named[b'MODL'], named[b'FULL']),
                         (b'FO4Core_acti_000100_synthetic\0', b'synthetic.nif\0', b'Bell\0'))
        self.assertNotIn(b'FULL', quiet)                                   # no name in FO4: no FULL here either
        self.assertEqual(quiet[b'EDID'], b'FO4Core_acti_000101_synthetic\0')
        t = dict(subrecords(new_records[term][1]))
        self.assertEqual((t[b'EDID'], t[b'MODL'], t[b'FULL'], t[b'NAM1']),
                         (b'FO4Core_term_000102_synthetic\0', b'terminal.nif\0', b'Terminal\0', b'\x02'))
        self.assertEqual(struct.unpack('<I', t[b'DNAM'])[0], 0x01000000 | menu)   # file-local: own records are 01
        m = list(subrecords(new_records[menu][1]))
        md = dict(m)
        self.assertEqual((md[b'EDID'], md[b'FULL'], md[b'TMVT'], md[b'SNAM']),
                         (b'FO4Core_tmlm_000102_synthetic\0', b'Terminal\0', struct.pack('<I', 1), struct.pack('<I', 0)))
        self.assertEqual([d for s, d in m if s == b'BTXT'], [self.BODY.encode() + b'\0'])
        self.assertEqual(md.get(b'TPLT'), b'\x00')
        self.assertEqual(md.get(b'BSIZ', struct.pack('<I', 1)), struct.pack('<I', 1))
        self.assertEqual(md.get(b'ISIZ', struct.pack('<I', 0)), struct.pack('<I', 0))
        (candidate / 'record-layout.json').write_text(json.dumps(
            {k: [[s.decode(), d.hex()] for s, d in subrecords(new_records[v][1])]
             for k, v in (('ACTI', acti[0]), ('ACTI_unnamed', acti[1]), ('TERM', term), ('TMLM', menu))}, indent=1))
        # make_core64c's check on the written plugin: counts and every binding hold
        objects = self.promote_all()
        walked = mk.overlay_records.walk_plugin(str(candidate / 'Synthetic.esm'))
        own = len(walked['masters']) << 24
        exp = {'objects': {'exported': 8, 'skipped': {}}}
        mk.check_reference_slots(objects, new)
        res = mk.promotion_checks(walked['records'], own, objects, new, exp)
        self.assertTrue(all(ok for _w, ok in res), res)
        self.assertEqual([w.split(' (')[0] for w, _ok in res][2:],
                         ['1 CONT = 1 distinct containers edids', '1 MISC = 1 distinct items edids',
                          '2 ACTI = 2 distinct activators edids', '1 TERM = 1 distinct terminals edids',
                          '1 TMLM = 1 distinct terminals menu edids',
                          'every promoted REFR names its CONT / MISC / ACTI / TERM'])
        # the same check catches a wrong body or a renamed activator in the cluster it is given
        wrong = self.promote_all(x=lambda o: o['terminals'][1].update(body='other'))
        self.assertFalse(mk.promotion_checks(walked['records'], own, wrong, new, exp)[-1][1])
        wrong = self.promote_all(x=lambda o: o['activators'][1].update(name='Quiet'))
        self.assertFalse(mk.promotion_checks(walked['records'], own, wrong, new, exp)[-1][1])

    # the furniture block every vanilla TERM carries (review of #241), as the template terminal of the master has it
    FURNITURE = (b'BFCB', b'ANAM', b'BNAM', b'CNAM', b'KSIZ', b'KWDA', b'PNAM', b'FNAM', b'JNAM', b'MNAM', b'GNAM',
                 b'WBDT', b'FTMP', b'XMRK', b'SNAM')

    def test_terminal_carries_the_template_furniture_block_and_activator_the_vanilla_fields(self):
        proc, stage = self.run_writer(self.promote_all(), 'acti-term-furniture')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        ids = json.loads((stage / 'formids.json').read_text())
        written = records(stage / 'Synthetic.esm')
        template = list(subrecords(records(self.master)[0x0155A2][1]))
        term = list(subrecords(written[int(next(iter(ids['terminals'].values()))['base'], 16)][1]))
        for sig in self.FURNITURE:
            want = [d for s, d in template if s == sig]
            self.assertTrue(want, sig)                                     # the synthetic template has every field
            self.assertEqual([d for s, d in term if s == sig], want, sig)
        t = dict(term)
        self.assertNotIn(b'VMAD', t)                                       # the template's script stays behind
        self.assertEqual(t[b'OBND'], bytes(24))                            # as every promoted base: no bounds yet
        self.assertEqual((t[b'EDID'], t[b'MODL'], t[b'FULL']),
                         (b'FO4Core_term_000102_synthetic\0', b'terminal.nif\0', b'Terminal\0'))
        self.assertEqual(struct.unpack('<I', t[b'MNAM'])[0], 0x40000001)  # HasModel + InteractionPoint0
        for src in ('000003:Synthetic.esm', '000004:Synthetic.esm'):     # named and unnamed ACTI
            a = dict(subrecords(written[int(ids['activators'][src]['base'], 16)][1]))
            self.assertEqual((a.get(b'PNAM'), a.get(b'FNAM'), a.get(b'JNAM')),
                             (bytes.fromhex('cc4c3300'), b'\0\0', struct.pack('<H', 360)), src)

    def test_bad_activator_or_terminal_inputs_leave_the_plugin_and_map(self):
        good = self.promote_all()
        proc, stage = self.run_writer(good, 'acti-term-refusals')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        pinned = {n: (stage / n).read_bytes() for n in ('Synthetic.esm', 'formids.json')}
        invalid = [
            self.promote_all(x=lambda o: o['terminals'][0].update(body='two\nlines')),
            self.promote_all(x=lambda o: o['terminals'][1].update(body='')),
            self.promote_all(x=lambda o: o['terminals'][1].update(name='Other')),            # one TERM edid, two names
            self.promote_all(x=lambda o: o['activators'][2].update(name='Gong')),           # one ACTI edid, two names
            self.promote_all(x=lambda o: o['activators'][2].update(model='other.nif')),     # one ACTI edid, two models
            self.promote_all(x=lambda o: o['terminals'][1].update(edid='FO4Core_term_000103_synthetic')),   # menu shared
            self.promote_all(x=lambda o: o['terminals'][0].update(reference_index=0)),      # the container's slot
        ]
        for objects in invalid:
            proc, _ = self.run_writer(objects, 'acti-term-refusals')
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual({n: (stage / n).read_bytes() for n in pinned}, pinned)
