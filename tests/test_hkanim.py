"""hkanim: Fallout 4 Havok skeleton / binding / spline-compressed animation reader.

Synthetic cases build tiny hk_2014 packfiles in memory (both header layouts: section headers at 0x40 and 0x50) with a
hand-encoded spline stream; the real-file case runs only when the Fallout 4 archives are installed."""
import math
import os
import struct
import unittest

from fo4sf import hkanim, hkpackfile

FO4_ANIMS = r"D:\SteamLibrary\steamapps\common\Fallout 4\Data\Fallout4 - Animations.ba2"
SQH = math.sqrt(0.5)


# -- encoders used only by the tests (independent of the decoder) ------------------------------------------------------
def enc_threecomp40(q):
    idx = max(range(4), key=lambda i: abs(q[i]))
    three = [q[i] for i in range(4) if i != idx]
    v = 0
    for k, c in enumerate(three):
        v |= int(round(c / (SQH / 2047.0) + 2047)) << (12 * k)
    v |= idx << 36
    v |= (1 if q[idx] < 0 else 0) << 38
    return v.to_bytes(5, "little")


def enc_threecomp48(q):
    idx = max(range(4), key=lambda i: abs(q[i]))
    three = [int(round(c / (SQH / 16383.0) + 16383)) for c in (q[i] for i in range(4) if i != idx)]
    x, y, z = three
    x |= (idx & 1) << 15
    y |= ((idx >> 1) & 1) << 15
    z |= (1 if q[idx] < 0 else 0) << 15
    return struct.pack("<3H", x, y, z)


def norm(q):
    n = math.sqrt(sum(c * c for c in q))
    return tuple(c / n for c in q)


class Stream:
    def __init__(self):
        self.b = bytearray()

    def align(self, a):
        while len(self.b) % a:
            self.b.append(0)

    def add(self, fmt, *v):
        self.b += struct.pack(fmt, *v)


class PackBuilder:
    """Minimal hk_2014 64-bit packfile writer: one data section with local and virtual fixups."""

    def __init__(self):
        self.data = bytearray()
        self.local = []
        self.virtual = []

    def alloc(self, n, align=16):
        while len(self.data) % align:
            self.data.append(0)
        off = len(self.data)
        self.data += bytes(n)
        return off

    def blob(self, b, align=16):
        off = self.alloc(len(b), align)
        self.data[off:off + len(b)] = b
        return off

    def put(self, off, fmt, *v):
        struct.pack_into(fmt, self.data, off, *v)

    def ptr(self, at, target):
        self.local.append((at, target))

    def array(self, at, payload: bytes, n):
        if n:
            self.ptr(at, self.blob(payload))
        self.put(at + 8, "<iI", n, n | 0x80000000)

    def string(self, at, s):
        self.ptr(at, self.blob(s.encode("latin-1") + b"\0", 1))

    def obj(self, cls, size):
        o = self.alloc(size)
        self.virtual.append((o, cls))
        return o

    def build(self, pad=16) -> bytes:
        names = sorted({c for _, c in self.virtual})
        cn = bytearray()
        name_off = {}
        for c in names:
            cn += struct.pack("<I", 0) + b"\x09"
            name_off[c] = len(cn)
            cn += c.encode() + b"\0"
        while len(cn) % 16:
            cn.append(0xFF)

        def pad16(b):
            while len(b) % 16:
                b.append(0xFF)
            return b

        data = bytearray(self.data)
        while len(data) % 16:
            data.append(0)
        loc = len(data)
        data += b"".join(struct.pack("<ii", a, b) for a, b in self.local)
        pad16(data)
        glo = len(data)
        vir = len(data)
        data += b"".join(struct.pack("<iii", o, 0, name_off[c]) for o, c in self.virtual)
        pad16(data)
        end = len(data)
        nsec = 3
        hdr_end = 64 + pad
        cn_start = hdr_end + 64 * nsec
        ty_start = cn_start + len(cn)
        da_start = ty_start
        head = bytearray(b"\x57\xe0\xe0\x57\x10\xc0\xc0\x10")
        head += struct.pack("<ii", 0, 11) + bytes((8, 1, 0, 1)) + struct.pack("<iiiii", nsec, 2, 0, 0, 0)
        head += b"hk_2014.1.0-r1\0\xff" + struct.pack("<ihh", 0, 21 if pad else -1, pad)
        head += b"\xff" * pad

        def sec(tag, start, l, g, v, e):
            return tag.encode().ljust(20, b"\0") + struct.pack("<7i", start, l, g, v, e, e, e) + b"\xff" * 16

        head += sec("__classnames__", cn_start, len(cn), len(cn), len(cn), len(cn))
        head += sec("__types__", ty_start, 0, 0, 0, 0)
        head += sec("__data__", da_start, loc, glo, vir, end)
        return bytes(head + cn + data)


def build_clip(pad=16, ref_t=(1.0, 2.0, 3.0)):
    """Skeleton (2 bones), binding, and a 3-frame spline animation with 2 tracks:
      track 0: static translation, static THREECOMP40 rotation, identity scale
      track 1: x spline (16-bit, degree 1) + y static translation, THREECOMP48 degree-1 rotation spline"""
    pb = PackBuilder()
    q_static = norm((0.1, -0.2, 0.3, 0.9))
    q_a = norm((0.0, 0.0, 0.0, 1.0))
    q_b = norm((0.0, 0.0, math.sin(math.radians(30)), math.cos(math.radians(30))))
    # skeleton
    s = pb.obj("hkaSkeleton", 136)
    pb.string(s + 16, "Root")
    pb.array(s + 24, struct.pack("<2h", -1, 0), 2)
    bones = pb.alloc(32)
    pb.string(bones, "Root")
    pb.string(bones + 16, "Arm1|0")
    pb.ptr(s + 40, bones)
    pb.put(s + 48, "<iI", 2, 2 | 0x80000000)
    pose = b"".join(struct.pack("<12f", *ref_t, 0, *q, *(1.0, 1.0, 1.0), 0)
                    for q in (q_static, (0.0, 0.0, 0.0, 1.0)))         # bone 0 holds track 0's still pose
    pb.array(s + 56, pose, 2)
    # spline stream (one block)
    st = Stream()
    st.add("<4B", 1 << 2, 0x07, 0x0F, 0x00)                    # track 0: pos static xyz, rot static 3C40, scale id
    st.add("<4B", 0x01 | (2 << 2), 0x12, 0xF0, 0x00)           # track 1: pos 16-bit, rot 3C48 spline
    st.add("<3f", *ref_t)                                      # track 0 translation
    st.align(4)
    st.b += enc_threecomp40(q_static)                          # THREECOMP40 aligns to 1
    st.align(4)
    st.align(4)                                                # scale identity
    st.add("<HB", 2, 1)                                        # track 1 translation: 3 control points, degree 1
    st.b += bytes((0, 0, 1, 2, 2))
    st.align(4)
    st.add("<2f", -1.0, 3.0)                                   # x min, max
    st.add("<f", 7.5)                                          # y static
    for qv in (0, 32768, 65535):
        st.add("<H", qv)
    st.align(4)
    st.add("<HB", 1, 1)                                        # rotation: 2 control points, degree 1
    st.b += bytes((0, 0, 2, 2))
    st.align(2)
    st.b += enc_threecomp48(q_a) + enc_threecomp48(q_b)
    st.align(4)
    st.align(4)                                                # scale identity
    float_off = len(st.b)
    st.align(16)
    a = pb.obj("hkaSplineCompressedAnimation", 176)
    pb.put(a + 16, "<ifii", 3, 2 / 30.0, 2, 0)
    pb.put(a + 56, "<iiii", 3, 1, 256, 8)
    pb.put(a + 72, "<fff", 255 / 30.0, 30.0 / 255, 1 / 30.0)
    pb.array(a + 88, struct.pack("<I", 0), 1)
    pb.array(a + 104, struct.pack("<I", float_off), 1)
    pb.array(a + 152, bytes(st.b), len(st.b))
    b = pb.obj("hkaAnimationBinding", 88)
    pb.string(b + 16, "Root")
    pb.ptr(b + 24, a)
    pb.array(b + 32, struct.pack("<2h", 0, 1), 2)
    pb.put(b + 80, "<b", 0)
    return pb.build(pad), dict(q_static=q_static, q_a=q_a, q_b=q_b)


class HeaderTests(unittest.TestCase):
    def test_section_headers_found_from_header_both_layouts(self):
        for pad, at in ((0, 0x40), (16, 0x50)):
            blob, _ = build_clip(pad)
            self.assertEqual(hkpackfile.Packfile.section_header_offset(blob), at)
            p = hkpackfile.Packfile(blob)
            self.assertEqual([s.tag for s in p.sections], ["__classnames__", "__types__", "__data__"])
            self.assertEqual(sorted(c for _, c in p.objects()),
                             ["hkaAnimationBinding", "hkaSkeleton", "hkaSplineCompressedAnimation"])

    def test_wrong_padding_is_refused_not_guessed(self):
        blob, _ = build_clip(16)
        bad = bytearray(blob)
        struct.pack_into("<h", bad, 62, 32)            # claims 32 bytes: no section header there
        with self.assertRaises(hkpackfile.PackfileError):
            hkpackfile.Packfile(bytes(bad))


class QuantTests(unittest.TestCase):
    def test_threecomp40_and_48_round_trip(self):
        for q in [norm(v) for v in ((0.1, 0.2, 0.3, 0.9), (-0.7, 0.1, 0.1, 0.7), (0.0, -0.9, 0.3, -0.1),
                                    (0.5, 0.5, -0.5, -0.5), (0.0, 0.0, 0.0, 1.0))]:
            for fmt, enc, tol in ((1, enc_threecomp40, 6e-4), (2, enc_threecomp48, 8e-5)):
                hkanim.QUAT_CHECKS.clear()
                d = hkanim.unpack_quaternion(fmt, enc(q))
                self.assertAlmostEqual(sum(c * c for c in d), 1.0, places=9)
                self.assertLess(max(abs(a - b) for a, b in zip(d, q)), tol, (fmt, q, d))
                self.assertEqual(hkanim.QUAT_CHECKS["dropped_not_largest"], 0)

    def test_unmeasured_formats_raise(self):
        with self.assertRaises(hkanim.HkAnimError):
            hkanim.unpack_quaternion(0, bytes(4))


class SplineTests(unittest.TestCase):
    def test_degree1_interpolates_control_points(self):
        knots = (0, 0, 1, 2, 2)
        cps = [(0.0,), (10.0,), (4.0,)]
        self.assertEqual([hkanim.evaluate(u, 1, knots, cps)[0] for u in (0, 1, 2)], [0.0, 10.0, 4.0])
        self.assertAlmostEqual(hkanim.evaluate(0.5, 1, knots, cps)[0], 5.0)

    def test_degree3_clamped_end_points_and_partition_of_unity(self):
        knots = (0, 0, 0, 0, 3, 7, 7, 7, 7)
        cps = [(1.0,), (5.0,), (-2.0,), (8.0,), (3.0,)]
        self.assertAlmostEqual(hkanim.evaluate(0, 3, knots, cps)[0], 1.0)
        self.assertAlmostEqual(hkanim.evaluate(7, 3, knots, cps)[0], 3.0)
        for u in (0.5, 2.9, 3.0, 5.5, 6.99):
            span = hkanim.find_span(4, 3, u, knots)
            self.assertAlmostEqual(sum(hkanim.basis(span, u, 3, knots)), 1.0)
        same = [(2.5,)] * 5
        self.assertAlmostEqual(hkanim.evaluate(4.2, 3, knots, same)[0], 2.5)


class DecodeTests(unittest.TestCase):
    def test_synthetic_clip_decodes(self):
        for pad in (0, 16):
            blob, q = build_clip(pad)
            h = hkanim.load(blob)
            sk, b, a = h.skeletons[0], h.bindings[0], h.animations[0]
            self.assertEqual(sk.bones, ["Root", "Arm1|0"])
            self.assertEqual(sk.parents, [-1, 0])
            self.assertEqual(sk.reference_pose[0][0], (1.0, 2.0, 3.0))
            self.assertEqual(b.transform_track_to_bone, [0, 1])
            self.assertEqual(b.blend_hint_name, "NORMAL")
            self.assertEqual(b.original_skeleton_name, "Root")
            self.assertEqual((a.num_frames, a.num_transform_tracks), (3, 2))
            # track 0: static everywhere
            for f in range(3):
                t, r, s = a.tracks[0][f]
                self.assertEqual(t, (1.0, 2.0, 3.0))
                self.assertLess(hkanim.quat_angle(r, q["q_static"]), 2e-3)
                self.assertEqual(s, (1.0, 1.0, 1.0))
            # track 1: x follows the 16-bit control points exactly at the knots, y static, z default 0
            xs = [a.tracks[1][f][0][0] for f in range(3)]
            want = [-1.0 + 4.0 * v / 65535.0 for v in (0, 32768, 65535)]
            for got, exp in zip(xs, want):
                self.assertAlmostEqual(got, exp, places=5)
            self.assertTrue(all(a.tracks[1][f][0][1:] == (7.5, 0.0) for f in range(3)))
            # rotation: degree-1 spline between identity and 60 deg about z (half-angle 30); frame 1 is the
            # normalized midpoint, 30 deg
            self.assertLess(hkanim.quat_angle(a.tracks[1][0][1], q["q_a"]), 1e-3)
            self.assertLess(hkanim.quat_angle(a.tracks[1][2][1], q["q_b"]), 1e-3)
            self.assertAlmostEqual(math.degrees(hkanim.quat_angle(a.tracks[1][1][1], q["q_a"])), 30.0, places=1)
            st = a.stats
            self.assertEqual(st["blocks"][0]["read_end"], st["blocks"][0]["float_block_offset"])
            self.assertEqual(st["forms"]["rotation_THREECOMP48_spline"], 1)
            self.assertEqual(st["forms"]["rotation_THREECOMP40_static"], 1)
            self.assertEqual(st["forms"]["translation_BITS16_spline"], 1)
            rep = hkanim.clip_report(a, b, sk)
            self.assertTrue(rep["frames_match"] and rep["finite"])
            self.assertEqual(rep["still_tracks"], 1)
            self.assertEqual(rep["still_within_0.01u_0.1deg"], 1)
            js = hkanim.to_json(a, b, sk)
            self.assertEqual(js["tracks"][1]["bone"], "Arm1|0")
            self.assertEqual(len(js["tracks"][1]["frames"][0]), 10)

    def test_misparsed_stream_is_detected(self):
        blob, _ = build_clip(16)
        p = hkpackfile.Packfile(blob)
        a = next(o for o, c in p.objects() if c == "hkaSplineCompressedAnimation")
        at, _n = p.array(a + 104)
        bad = bytearray(blob)
        off = p.data_section.start + at
        struct.pack_into("<I", bad, off, struct.unpack_from("<I", bad, off)[0] + 4)
        with self.assertRaises(hkanim.HkAnimError):
            hkanim.load(bytes(bad))

    def test_model_space_composes_parent_rotation(self):
        q90z = (0.0, 0.0, math.sin(math.pi / 4), math.cos(math.pi / 4))
        ms = hkanim.model_space([-1, 0], [((0, 0, 10), q90z, (1, 1, 1)), ((1, 0, 0), (0, 0, 0, 1), (1, 1, 1))])
        for got, exp in zip(ms[1][0], (0.0, 1.0, 10.0)):
            self.assertAlmostEqual(got, exp)


@unittest.skipUnless(os.path.exists(FO4_ANIMS), "Fallout 4 archives not installed")
class RealFilesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fo4sf.ba2 import Ba2
        cls.arc = Ba2(FO4_ANIMS)

    def test_handy_skeleton_and_two_block_idle(self):
        raw = self.arc.read("meshes\\actors\\robot\\characterassets\\skeleton.hkx")
        self.assertEqual(hkpackfile.Packfile.section_header_offset(raw), 0x50)
        sk = hkanim.load(raw).skeletons[0]
        self.assertEqual(len(sk.bones), 112)
        self.assertEqual(sk.bones[:3], ["Root", "COM", "Pelvis"])
        h = hkanim.load(self.arc.read("meshes\\actors\\robot\\animations\\idle.hkx"))
        a, b = h.animations[0], h.bindings[0]
        self.assertEqual((a.num_frames, a.num_transform_tracks, a.stats["num_blocks"]), (311, 111, 2))
        rep = hkanim.clip_report(a, b, sk)
        self.assertTrue(rep["frames_match"] and rep["finite"])
        self.assertEqual(rep["packed_quat_dropped_not_largest"], 0)
        self.assertLess(rep["block_boundary_max_translation_diff"], 1e-3)
        self.assertLess(rep["block_boundary_max_rotation_diff_deg"], 0.1)
        self.assertLess(rep["max_blend_norm_dev"], 0.01)
        pelvis = b.transform_track_to_bone.index(sk.index("Pelvis"))
        self.assertEqual(a.tracks[pelvis][0][0], (0.0, 0.0, 0.0))

    def test_additive_clip_still_tracks_are_identity(self):
        sk = hkanim.load(self.arc.read("meshes\\actors\\robot\\characterassets\\skeleton.hkx")).skeletons[0]
        h = hkanim.load(self.arc.read("meshes\\actors\\robot\\animations\\rotateringcw_add.hkx"))
        rep = hkanim.clip_report(h.animations[0], h.bindings[0], sk)
        self.assertEqual(rep["blend_hint"], "ADDITIVE")
        self.assertEqual(rep["still_off_reference"], [])

    def test_deathclaw_clip_decodes(self):
        h = hkanim.load(self.arc.read("meshes\\actors\\deathclaw\\animations\\deathclaw_walkforward.hkx"))
        rep = hkanim.clip_report(h.animations[0], h.bindings[0], None)
        self.assertTrue(rep["frames_match"] and rep["finite"])


if __name__ == "__main__":
    unittest.main()
