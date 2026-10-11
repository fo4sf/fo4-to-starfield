"""Synthetic-fixture tests for the Starfield .af / .rig readers: every input byte is built here, no game data."""
import math
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import af  # noqa: E402

S = math.sqrt(0.5)


def header(bones, frames, atlas_len, suffix=0, preamble=0, flags=0):
    h = struct.pack('<Q', 0) + struct.pack('<4f', 1, 0, 0, 0) + struct.pack('<3f', 0, 0, 0) + bytes([flags, 0, 0, 0])
    h += struct.pack('<6H', 5, bones, frames, atlas_len, suffix, preamble) + struct.pack('<3f', 0, 0, 0)
    assert len(h) == 64
    return h


def rot_prefix(cx=0, cy=0, cz=0, x8=(0, 0, 0), missing=3, run=0):
    out = bytes([(c & 0x7F) | (0x80 if f else 0) for c, f in zip((cx, cy, cz), x8)])
    return out + bytes([(missing << 6) | run])


def trans_prefix(cx, cy, cz, run):
    return struct.pack('<3hH', cx, cy, cz, run)


def block(pos, rot=None, trans=None, scalars=(), prios=(), wide_counters=False, wide_frames=False):
    """One bone block starting at absolute offset `pos`; every 2-byte field is 2-aligned like the reader expects.

    rot / trans = (frames, entries, prefixes); scalars / prios = [(frame, value)]."""
    cfmt = '<H' if wide_counters else '<B'
    kfmt = '<H' if wide_frames else '<B'
    rf, re_, rp = rot or ([], [], [])
    tf, te, tp = trans or ([], [], [])
    sf = [s[0] for s in scalars]
    pf = [p[0] for p in prios]
    out = b''

    def align2():
        nonlocal out
        if (pos + len(out)) % 2:
            out += b'\0'

    if wide_counters:
        align2()
    out += b''.join(struct.pack(cfmt, n) for n in (len(rf), len(rp), len(tf), len(tp), len(sf), len(pf)))
    if wide_frames and (rf or tf or sf or pf):
        align2()
    out += b''.join(struct.pack(kfmt, f) for f in rf + tf + sf + pf)
    out += b''.join(re_) + b''.join(rp) + b''.join(te)
    if tp:
        align2()
        out += b''.join(tp)
    if scalars:
        align2()
        out += b''.join(struct.pack('<h', s[1]) for s in scalars)
    out += bytes(p[1] for p in prios)
    return out


def door_file(flags=0, preamble=b'', suffix_ids=()):
    """3 bones, 5 frames. Bone 0 has no block. Bone 1 rotates from identity (key 0, prefix A) to 90 deg about -z
    (keys 2 and 4, prefix B with run 1). Bone 2 slides (-1.0, 1.5, 0) -> (-1.0, 1.5, 0.011) with two prefixes, plus
    one scalar key and one priority key. Each suffix id gets one extra block with a half turn about x at frame 3."""
    wide_c, wide_f = bool(flags & 2), bool(flags & 4)
    body = struct.pack('<%dI' % len(suffix_ids), *suffix_ids) + bytes([1, 2])

    def pos():
        return 64 + len(preamble) + len(body)

    body += block(pos(), rot=([0, 2, 4], [bytes(3)] * 3, [rot_prefix(missing=3, run=0), rot_prefix(0, 0, -64, missing=3, run=1)]),
                  wide_counters=wide_c, wide_frames=wide_f)
    body += block(pos(), trans=([0, 4], [bytes(3), bytes([0, 0, 44])], [trans_prefix(-32, 48, 0, 1), trans_prefix(-32, 48, 0, 1)]),
                  scalars=[(1, -5)], prios=[(0, 7)], wide_counters=wide_c, wide_frames=wide_f)
    for _ in suffix_ids:
        body += block(pos(), rot=([3], [bytes(3)], [rot_prefix(missing=0)]), wide_counters=wide_c, wide_frames=wide_f)
    return header(3, 5, 2, suffix=len(suffix_ids), preamble=len(preamble), flags=flags) + preamble + body


def rig_file(bones, low=0.03125, high=0.00025, map_slots=4):
    """bones: list of (name, parent, local_rot_wxyz, translation)."""
    map_off = 80 + 96 * len(bones)
    names_start = map_off + 2 * map_slots
    names, offs, cur = b'', [], names_start
    for name, _p, _q, _t in bones:
        offs.append(cur)
        enc = name.encode() + b'\0'
        names += enc
        cur += len(enc)
    size = names_start + len(names)
    out = struct.pack('<6I', 5, size, 80, 0, map_off, 0) + struct.pack('<3Q', 0, 0, 0)
    out += struct.pack('<ffHH', low, high, len(bones), len(bones)) + bytes(20)
    for (name, parent, q, t), off in zip(bones, offs):
        rec = struct.pack('<8f', *q, *q) + struct.pack('<3f', *t) + struct.pack('<I', 0xFFFFFFFF)
        rec += struct.pack('<Q', off) + struct.pack('<i', parent)
        out += rec + bytes(96 - len(rec))
    out += b'\xff\xff' * map_slots + names
    assert len(out) == size
    return out


def qdist_deg(a, b):
    return math.degrees(2 * math.acos(min(1.0, abs(sum(p * q for p, q in zip(a, b))))))


def rounded(v, places=3):
    return tuple(round(c, places) for c in v)


class RotationDecodeTests(unittest.TestCase):
    def test_identity_and_dropped_w(self):
        self.assertEqual(af.decode_rotation(rot_prefix(missing=3), bytes(3)), (1.0, 0.0, 0.0, 0.0))

    def test_coarse_step_gives_exact_90_degrees(self):
        q = af.decode_rotation(rot_prefix(0, 0, -64, missing=3), bytes(3))      # 7-bit -64 -> z = -sqrt(1/2)
        axis, angle = af.axis_angle(q)                                        # 90 deg about -z
        self.assertAlmostEqual(angle, 90.0, places=6)
        self.assertEqual(rounded(axis, 6), (0.0, 0.0, -1.0))
        self.assertAlmostEqual(q[0], S, places=6)

    def test_fine_step_and_x8_flag(self):
        q = af.decode_rotation(rot_prefix(63, 0, 0, x8=(1, 0, 0), missing=3), bytes([32, 0, 0]))
        self.assertAlmostEqual(q[1], 63 * S / 64 + 32 * 8 * S / 16384, places=9)
        self.assertAlmostEqual(af.axis_angle(q)[1], 90.0, places=3)
        q = af.decode_rotation(rot_prefix(0, 45, 0, missing=3), bytes([0, 65, 0]))
        self.assertAlmostEqual(af.axis_angle(q)[1], 60.0, places=1)
        q = af.decode_rotation(rot_prefix(0, 0, 0, missing=3), struct.pack('<3b', 0, 0, -3))
        self.assertAlmostEqual(q[3], -3 * S / 16384, places=12)

    def test_dropped_component_index(self):
        # missing = 1 (y): stored x, z, w all zero -> y = 1: a half turn about y
        self.assertEqual(af.decode_rotation(rot_prefix(missing=1), bytes(3)), (0.0, 0.0, 1.0, 0.0))
        self.assertEqual(af.decode_rotation(rot_prefix(missing=0), bytes(3)), (0.0, 1.0, 0.0, 0.0))
        self.assertEqual(af.decode_rotation(rot_prefix(missing=2), bytes(3)), (0.0, 0.0, 0.0, 1.0))

    def test_run_length_and_bad_sizes(self):
        self.assertEqual(af.rotation_run_length(rot_prefix(run=2)), 3)
        self.assertEqual(af.rotation_run_length(rot_prefix(missing=2, run=63)), 64)
        with self.assertRaises(af.AfError):
            af.decode_rotation(b'\0\0\0', b'\0\0\0')


class TranslationDecodeTests(unittest.TestCase):
    def test_coarse_and_fine_steps_from_rig_precision(self):
        p = trans_prefix(-32, 48, 0, 2)
        self.assertEqual(af.decode_translation(p, bytes(3)), (-1.0, 1.5, 0.0))
        v = af.decode_translation(p, bytes([0, 0, 44]), af.DEFAULT_PRECISION)
        self.assertAlmostEqual(v[2], 0.011, places=9)
        v = af.decode_translation(trans_prefix(2, 0, 0, 1), bytes([53, 0, 0]), af.SHIP_PRECISION)
        self.assertAlmostEqual(v[0], 0.606, places=9)
        self.assertEqual(af.translation_run_length(p), 2)
        with self.assertRaises(af.AfError):
            af.decode_translation(b'\0' * 7, bytes(3))


class ParseTests(unittest.TestCase):
    def check_door(self, anim):
        h = anim.header
        self.assertEqual((h.version, h.bone_count, h.frame_count, h.atlas_length), (5, 3, 5, 2))
        self.assertEqual(anim.atlas, [1, 2])
        self.assertEqual(anim.animated_bones, [1, 2])
        self.assertFalse(anim.bones[0].animated)
        rot = anim.bones[1].rotation
        self.assertEqual(rot.frames, [0, 2, 4])
        self.assertEqual(rot.values[0], (1.0, 0.0, 0.0, 0.0))
        axis, angle = af.axis_angle(rot.values[1])
        self.assertEqual((rounded(axis, 6), round(angle, 6)), ((0.0, 0.0, -1.0), 90.0))
        self.assertEqual(rot.values[1], rot.values[2])
        tr = anim.bones[2].translation
        self.assertEqual(tr.frames, [0, 4])
        self.assertEqual(tr.values[0], (-1.0, 1.5, 0.0))
        self.assertAlmostEqual(tr.values[1][2], 0.011, places=9)
        self.assertEqual((anim.bones[2].scalar.frames, anim.bones[2].scalar.values), ([1], [-5]))
        self.assertEqual((anim.bones[2].priority.frames, anim.bones[2].priority.values), ([0], [7]))

    def test_whole_file_consumed_exactly(self):
        data = door_file()
        anim = af.parse(data)
        self.check_door(anim)
        self.assertEqual(anim.consumed, len(data))
        self.assertEqual((anim.suffix_ids, anim.suffix_blocks, anim.preamble_raw), ([], [], b''))
        self.assertEqual(len(anim.bones[1].raw['rotation_prefixes']), 2)

    def test_wide_counters_and_frame_indices(self):
        for flags in (2, 4, 6):
            data = door_file(flags=flags)
            anim = af.parse(data)
            self.assertEqual((anim.header.wide_counters, anim.header.wide_frames), (bool(flags & 2), bool(flags & 4)))
            self.check_door(anim)
            self.assertEqual(anim.consumed, len(data))

    def test_preamble_is_skipped_by_header_size_and_decoded_best_effort(self):
        # one entry: u32 count, u16 n=1, (pad to 4), 2 pre floats, 5 main floats, 1 i16, 1 i8 -> 39 bytes, padded to 40
        pre = struct.pack('<IH', 1, 1) + b'\0\0' + struct.pack('<2f', 0.5, 0.25) + struct.pack('<5f', 1, 2, 3, 4, 5)
        pre += struct.pack('<hb', -7, 3) + b'\0'
        self.assertEqual(len(pre), 40)
        anim = af.parse(door_file(preamble=pre))
        self.check_door(anim)
        self.assertEqual(anim.header.preamble_size, 40)
        self.assertTrue(anim.preamble_parsed)
        self.assertEqual((anim.preamble[0].count, anim.preamble[0].footer1, anim.preamble[0].footer2), (1, [-7], [3]))
        self.assertEqual(anim.preamble[0].main, [1.0, 2.0, 3.0, 4.0, 5.0])
        # a blob of another shape is still skipped by the header size, just not decoded
        anim = af.parse(door_file(preamble=b'\x09' * 12))
        self.check_door(anim)
        self.assertFalse(anim.preamble_parsed)
        self.assertEqual((anim.preamble, anim.preamble_raw), ([], b'\x09' * 12))

    def test_suffix_ids_and_blocks(self):
        anim = af.parse(door_file(suffix_ids=(0xFFF1BB1A, 7)))
        self.check_door(anim)
        self.assertEqual(anim.suffix_ids, [0xFFF1BB1A, 7])
        self.assertEqual([b.bone for b in anim.suffix_blocks], [-1, -2])
        self.assertEqual(anim.suffix_blocks[0].rotation.frames, [3])
        self.assertEqual(anim.suffix_blocks[0].rotation.values[0], (0.0, 1.0, 0.0, 0.0))

    def test_errors(self):
        data = door_file()
        with self.assertRaisesRegex(af.AfError, 'parsed'):
            af.parse(data + b'\0')
        self.assertEqual(af.parse(data + b'\0', strict=False).consumed, len(data))
        with self.assertRaisesRegex(af.AfError, 'truncated'):
            af.parse(data[:-1])
        bad = bytearray(data)
        bad[0x2A] = 4                                   # header says 4 bones, atlas covers 3
        with self.assertRaisesRegex(af.AfError, 'atlas covers 3 bones'):
            af.parse(bytes(bad))
        bad = bytearray(data)
        bad[66 + 6 + 2] = 1                              # bone 1 key frames 0, 2, 4 -> 0, 2, 1
        with self.assertRaisesRegex(af.AfError, 'not ascending'):
            af.parse(bytes(bad))
        bad = bytearray(data)
        bad[66 + 6 + 3 + 9 + 4 + 3] = 0xC0               # prefix B run 1 -> 0: prefixes cover 2 keys, block has 3
        with self.assertRaisesRegex(af.AfError, 'rotation prefixes cover 2 keys'):
            af.parse(bytes(bad))
        with self.assertRaises(af.AfError):
            af.parse(data[:40])


class SampleAndPoseTests(unittest.TestCase):
    def setUp(self):
        self.anim = af.parse(door_file())
        self.rig = af.parse_rig(rig_file([
            ('Root', -1, (1, 0, 0, 0), (-4.0, -2.0, 0.0)),
            ('Hinge01_Point', 0, (1, 0, 0, 0), (-0.823, 1.698, 0.0)),
            ('Panel', 0, (S, 0, 0, S), (1.0, 2.0, 3.0)),
        ]))

    def test_sample_interpolates_and_holds(self):
        d0, d1, d2 = af.sample(self.anim, 0), af.sample(self.anim, 1), af.sample(self.anim, 9)
        self.assertEqual(d0[0], ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0)))        # bone without channels
        self.assertEqual(d0[1][1], (1.0, 0.0, 0.0, 0.0))
        self.assertEqual(d2[1][1], self.anim.bones[1].rotation.values[-1])         # held after the last key
        axis, angle = af.axis_angle(d1[1][1])                                      # halfway between keys 0 and 2
        self.assertEqual((rounded(axis, 4), round(angle, 4)), ((0.0, 0.0, -1.0), 45.0))
        self.assertAlmostEqual(af.sample(self.anim, 2)[2][0][2], 0.0055, places=9)  # translation lerp (0 -> 0.011)
        self.assertEqual(len(af.expand(self.anim)), 5)

    def test_pose_composes_bind_and_delta_in_parent_frame(self):
        pose = af.pose_at(self.anim, 4, self.rig)
        t, q = pose[1]
        self.assertEqual(rounded(t), (-0.823, 1.698, 0.0))
        axis, angle = af.axis_angle(q)
        self.assertEqual((rounded(axis, 6), round(angle, 6)), ((0.0, 0.0, -1.0), 90.0))
        t, q = pose[2]                                        # bind 90 deg about z, no rotation delta: unchanged
        self.assertEqual(rounded(t), (0.0, 3.5, 3.011))
        self.assertEqual(rounded(q, 6), rounded((S, 0, 0, S), 6))
        # composition order: delta 90 about z after a bind 90 about z = 180 about z (parent frame)
        t, q = af.compose(self.rig.bones[2], (1.0, 0.0, 0.0), (S, 0, 0, S))
        self.assertAlmostEqual(abs(q[3]), 1.0, places=6)
        self.assertEqual(rounded(t, 6), (2.0, 2.0, 3.0))
        t, q = af.compose(self.rig.bones[2], (1.0, 0.0, 0.0), (S, 0, 0, S), parent_frame=False)
        self.assertEqual(rounded(t, 6), (1.0, 3.0, 3.0))                      # delta rotated by the bind
        frames = af.expand(self.anim, self.rig)
        self.assertEqual(len(frames), 5)
        self.assertEqual((rounded(frames[0][1][0]), rounded(frames[0][1][1])), ((-0.823, 1.698, 0.0), (1.0, 0.0, 0.0, 0.0)))
        with self.assertRaises(af.AfError):
            af.pose_at(self.anim, 0, af.parse_rig(rig_file([('Root', -1, (1, 0, 0, 0), (0, 0, 0))])))

    def test_qmul(self):
        self.assertEqual(af.qmul(af.IDENTITY, (S, 0, 0, S)), (S, 0.0, 0.0, S))
        half = af.qmul((S, 0, 0, S), (S, 0, 0, S))
        self.assertAlmostEqual(abs(half[3]), 1.0, places=9)
        self.assertAlmostEqual(half[0], 0.0, places=9)


class RigTests(unittest.TestCase):
    def test_names_parents_precision_and_bone_map(self):
        rig = af.parse_rig(rig_file([('Root', -1, (1, 0, 0, 0), (0, 0, 0)), ('Door', 0, (0, 0, 1, 0), (0.5, 0, 2.29))],
                                    low=0.25, high=0.002, map_slots=3))
        self.assertEqual([(b.name, b.parent) for b in rig.bones], [('Root', -1), ('Door', 0)])
        self.assertEqual(rounded(rig.precision, 6), (0.25, 0.002))          # f32 in the file
        self.assertEqual(rig.bone_map, [0xFFFF] * 3)
        self.assertEqual(rig.animated_count, 2)
        self.assertEqual(rig.bones[1].rotation, (0.0, 0.0, 1.0, 0.0))
        self.assertEqual(rounded(rig.bones[1].translation), (0.5, 0.0, 2.29))
        self.assertEqual(rig.index('Door'), 1)
        with self.assertRaises(KeyError):
            rig.index('Hinge')

    def test_rig_errors(self):
        good = rig_file([('Root', -1, (1, 0, 0, 0), (0, 0, 0)), ('Door', 0, (1, 0, 0, 0), (0, 0, 0))])
        with self.assertRaisesRegex(af.AfError, 'file size'):
            af.parse_rig(good + b'\0')
        bad = bytearray(good)
        struct.pack_into('<ff', bad, 48, 0.00025, 0.03125)
        with self.assertRaisesRegex(af.AfError, 'precision'):
            af.parse_rig(bytes(bad))
        bad = bytearray(good)
        struct.pack_into('<i', bad, 80 + 96 + 56, 1)         # bone 1 is its own parent
        with self.assertRaisesRegex(af.AfError, 'parent'):
            af.parse_rig(bytes(bad))
        bad = bytearray(good)
        struct.pack_into('<Q', bad, 80 + 48, 10)              # name offset inside the bone table
        with self.assertRaisesRegex(af.AfError, 'name offset'):
            af.parse_rig(bytes(bad))
        with self.assertRaises(af.AfError):
            af.parse_rig(good[:60])


if __name__ == '__main__':
    unittest.main()
