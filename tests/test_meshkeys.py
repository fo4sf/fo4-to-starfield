"""Starfield's compressed-mesh decoder rules on converted FO4 collision (synthetic data, no game files):
primitive slots the decoder cannot type become neighbour copies, the SIMD tree gets one leaf per primitive (even keys),
the FO4 special-primitive section flag is cleared, the tree's flat-convex byte is the vanilla value, and the decoder
simulation (fo4sf.meshcheck) that guards converted builds flags each violation and nothing on a vanilla-shaped mesh."""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import fo4collision as fc, hkpackfile, meshcheck, meshcollision as mc  # noqa: E402

DEAD = (0xDE, 0xAD, 0xDE, 0xAD)                       # FO4's padding of an unused primitive slot


def prims(*quads):
    return b"".join(bytes(q) for q in quads)


def slots(raw):
    return [tuple(raw[4 * i:4 * i + 4]) for i in range(len(raw) // 4)]


class SanitiseTests(unittest.TestCase):
    def test_slots_the_decoder_cannot_type_become_copies_of_the_nearest_valid_neighbour(self):
        raw = prims((0, 1, 2, 3), DEAD, (4, 5, 6, 6), (7, 7, 7, 7), (8, 9, 9, 9), (1, 2, 30, 3))
        out, fixes = mc.sanitise_primitives(raw, [(0, 6, 12)])           # one section, 12 vertex slots
        self.assertEqual(len(out), len(raw))
        got = slots(out)
        self.assertEqual(got[0], (0, 1, 2, 3))                           # valid slots untouched
        self.assertEqual(got[2], (4, 5, 6, 6))
        self.assertEqual(got[1], (0, 1, 2, 3))                           # DEAD: the slot before it
        self.assertEqual(got[3], (4, 5, 6, 6))                           # all-equal point
        self.assertEqual(got[4], (4, 5, 6, 6))                           # FO4 special (a, b, b, b): 3 and 5 invalid, 2 valid
        self.assertEqual(got[5], (4, 5, 6, 6))                           # index 30 outside the 12 vertex slots
        for q in got:
            self.assertNotEqual(q[1], q[3])
            self.assertLess(max(q), 12)
        self.assertEqual([(s, j) for s, j, _, _ in fixes], [(0, 1), (0, 3), (0, 4), (0, 5)])
        self.assertEqual(fixes[0][2:], (DEAD, (0, 1, 2, 3)))

    def test_copies_come_from_the_same_section(self):
        raw = prims((0, 1, 2, 3), DEAD, (4, 5, 6, 7))
        out, _ = mc.sanitise_primitives(raw, [(0, 2, 8), (2, 1, 8)])
        self.assertEqual(slots(out)[1], (0, 1, 2, 3))
        out, _ = mc.sanitise_primitives(prims((4, 5, 6, 7), DEAD, (0, 1, 2, 3)), [(0, 1, 8), (1, 2, 8)])
        self.assertEqual(slots(out)[1], (0, 1, 2, 3))                    # not slot 0 of the other section

    def test_section_without_a_valid_primitive_gets_the_zero_area_triangle(self):
        out, fixes = mc.sanitise_primitives(prims(DEAD, (3, 3, 3, 3)), [(0, 2, 4)])
        self.assertEqual(slots(out), [mc.FALLBACK_PRIMITIVE, mc.FALLBACK_PRIMITIVE])
        self.assertEqual(len(fixes), 2)
        with self.assertRaises(hkpackfile.PackfileError):
            mc.sanitise_primitives(prims(DEAD), [(0, 1, 1)])

    def test_special_primitives_of_a_known_type_are_still_replaced(self):
        # Starfield's decoder accepts types 3 and 4, but FO4 never writes them and our copies carry none
        out, fixes = mc.sanitise_primitives(prims((0, 1, 2, 3), (5, 7, 3, 7)), [(0, 2, 8)])
        self.assertEqual(slots(out)[1], (0, 1, 2, 3))

    def test_vanilla_shaped_array_is_byte_identical(self):
        raw = prims((0, 1, 2, 3), (3, 2, 1, 1), (4, 5, 6, 7), (7, 6, 5, 5))
        out, fixes = mc.sanitise_primitives(raw, [(0, 2, 8), (2, 2, 8)])
        self.assertEqual(out, raw)
        self.assertEqual(fixes, [])


def fo4_section(first, count, packed, shared, flags):
    s = bytearray(96)
    struct.pack_into("<I", s, 80, (first << 8) | count)
    s[88], s[89], s[93] = packed, shared, flags
    return bytes(s)


class MeshFixesTests(unittest.TestCase):
    def test_fo4_sections_read_primitive_range_and_vertex_slots(self):
        raw = fo4_section(0, 2, 5, 3, 0) + fo4_section(2, 1, 4, 0, 1)
        self.assertEqual(mc.fo4_sections(raw, 2), [(0, 2, 8), (2, 1, 4)])

    def test_flagged_section_is_sanitised_cleared_and_noted(self):
        fo4 = {"sections": (fo4_section(0, 2, 8, 0, 1) + fo4_section(2, 1, 8, 0, 0), 2),
               "primitives": (prims((0, 1, 2, 3), (5, 7, 7, 7), (1, 2, 3, 3)), 3)}
        notes = []
        out, flagged = mc._mesh_fixes(fo4, notes)
        self.assertEqual(flagged, [0])
        self.assertEqual(slots(out), [(0, 1, 2, 3), (0, 1, 2, 3), (1, 2, 3, 3)])
        self.assertEqual(len(notes), 2)
        self.assertIn("section 0: 1 of 2 primitive slots", notes[0])
        self.assertIn("(5, 7, 7, 7) -> (0, 1, 2, 3)", notes[0])
        self.assertIn("section 0: FO4 special-primitive flag cleared (flags 0x1)", notes[1])
        s = mc._convert_section(fo4_section(0, 2, 8, 0, 1))
        s[95] &= ~mc.SECTION_SPECIAL_FLAG                                # what _emit_mesh does for a flagged section
        self.assertEqual(s[95], 0)

    def test_vanilla_shaped_mesh_needs_nothing(self):
        raw = prims((0, 1, 2, 3), (3, 2, 1, 1))
        fo4 = {"sections": (fo4_section(0, 2, 8, 0, 0), 1), "primitives": (raw, 2)}
        notes = []
        out, flagged = mc._mesh_fixes(fo4, notes)
        self.assertEqual((out, flagged, notes), (raw, [], []))


class MeshData:
    """hkpackfile.Packfile stand-in holding one FO4 compressed mesh: domain 0..8 m, sections with packed vertices
    (11/11/10-bit quantised, codec offset 0, scale 1) and shared vertices (21/21/22-bit over the domain)."""
    DATA, SECTIONS, PRIMS, SIDX, PACKED, SHARED = 0, 1000, 2000, 3000, 4000, 5000

    def __init__(self, sections, primitives, shared_index=(), packed=(), shared=()):
        self.mem = bytearray(6000)
        struct.pack_into("<8f", self.mem, self.DATA + fc.CMD_DOMAIN, 0, 0, 0, 0, 8, 8, 8, 0)
        self.counts = {self.SECTIONS: len(sections), self.PRIMS: len(primitives), self.SIDX: len(shared_index),
                       self.PACKED: len(packed), self.SHARED: len(shared)}
        for k, (first_packed, first_shared, first_prim, nprim, npacked, nsidx) in enumerate(sections):
            so = self.SECTIONS + 96 * k
            struct.pack_into("<6f", self.mem, so + 48, 0, 0, 0, 1, 1, 1)
            struct.pack_into("<3I", self.mem, so + 72, first_packed, first_shared << 8, (first_prim << 8) | nprim)
            self.mem[so + 88], self.mem[so + 89] = npacked, nsidx
        self.mem[self.PRIMS:self.PRIMS + 4 * len(primitives)] = prims(*primitives)
        for i, j in enumerate(shared_index):
            struct.pack_into("<H", self.mem, self.SIDX + 2 * i, j)
        for i, (x, y, z) in enumerate(packed):
            struct.pack_into("<I", self.mem, self.PACKED + 4 * i, x | (y << 11) | (z << 22))
        for i, (x, y, z) in enumerate(shared):                            # metres over the 8 m domain
            q = (round(x / 8 * 0x1FFFFF), round(y / 8 * 0x1FFFFF), round(z / 8 * 0x3FFFFF))
            struct.pack_into("<Q", self.mem, self.SHARED + 8 * i, q[0] | (q[1] << 21) | (q[2] << 42))

    def array(self, off):
        base = {fc.CMD_SECTIONS: self.SECTIONS, fc.CMD_PRIMITIVES: self.PRIMS, fc.CMD_SHARED_INDEX: self.SIDX,
                fc.CMD_PACKED: self.PACKED, fc.CMD_SHARED: self.SHARED}[off - self.DATA]
        return base, self.counts[base]

    def unpack(self, fmt, off):
        return struct.unpack_from(fmt, self.mem, off)

    def raw(self, off, n):
        return bytes(self.mem[off:off + n])


class PrimitiveKeyTests(unittest.TestCase):
    def setUp(self):
        # section 0: 4 packed vertices (unit square), a quad, a triangle and a DEAD slot; section 1: 1 packed vertex
        # and 2 shared ones (2, 0, 0) and (0, 2, 0), one triangle
        self.p = MeshData(sections=[(0, 0, 0, 3, 4, 0), (4, 0, 3, 1, 1, 2)],
                          primitives=[(0, 1, 2, 3), (0, 1, 2, 2), DEAD, (0, 1, 2, 2)],
                          shared_index=[0, 1], packed=[(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 0)],
                          shared=[(2, 0, 0), (0, 2, 0)])

    def test_one_even_key_per_valid_primitive_with_the_whole_primitive_box(self):
        keys = fc.compressed_mesh_primitive_keys(self.p, MeshData.DATA)
        self.assertEqual([k for k, _ in keys], [0, 2, 256])                 # DEAD slot: no key; section 1 << 8
        self.assertEqual(keys[0][1], ((0.0, 0.0, 0.0), (1.0, 1.0, 0.0)))     # quad: all four vertices
        self.assertEqual(keys[1][1], ((0.0, 0.0, 0.0), (1.0, 1.0, 0.0)))
        lo, hi = keys[2][1]
        self.assertEqual(lo, (0.0, 0.0, 0.0))
        self.assertAlmostEqual(hi[0], 2.0, places=4)                          # shared vertex (2, 0, 0)
        self.assertAlmostEqual(hi[1], 2.0, places=4)
        self.assertEqual(hi[2], 0.0)
        per_triangle = [k for k, _ in fc.compressed_mesh_keys(self.p, MeshData.DATA)]
        self.assertEqual(per_triangle, [0, 1, 2, 256])                       # the old leaves: quad -> keys 0 and 1

    def test_sanitised_array_gives_the_copied_slot_its_own_key(self):
        secs = [(0, 3, 4), (3, 1, 3)]
        fixed, _ = mc.sanitise_primitives(self.p.raw(MeshData.PRIMS, 16), secs)
        keys = fc.compressed_mesh_primitive_keys(self.p, MeshData.DATA, fixed)
        self.assertEqual([k for k, _ in keys], [0, 2, 4, 256])

    def test_simd_tree_round_trips_through_the_checker_walker(self):
        keys = fc.compressed_mesh_primitive_keys(self.p, MeshData.DATA)
        raw = mc.build_simd_tree(keys)
        found, problems = meshcheck.walk_simd_tree(raw)
        self.assertEqual((sorted(found), problems), ([0, 2, 256], []))


def section_tree(n_leaves):
    """Aabb4BytesCodec nodes of a left-leaning tree over leaves 0..n-1: inner hiData = (left leaves << 1) | 1,
    leaf hiData = primitive << 1 (what FO4 and vanilla Starfield store)."""
    out = bytearray()

    def build(first, count):
        if count == 1:
            out.extend(bytes([0, 0, 0, first << 1]))
            return
        out.extend(bytes([0, 0, 0, (1 << 1) | 1]))                      # left: one leaf, right at +2
        build(first, 1)
        build(first + 1, count - 1)
    build(0, n_leaves)
    return bytes(out)


def vanilla_record(**over):
    """A vanilla-shaped mesh record: one section of 8 packed vertices, a quad, a triangle and a quad, one data run,
    a SIMD tree with one even key per primitive."""
    primitives = [(0, 1, 2, 3), (4, 5, 6, 6), (1, 2, 5, 4)]
    rec = {"numPrimitiveKeys": 5, "bitsPerKey": 3, "maxKeyValue": 5, "flat": 0xFF, "has_simd": 1,
           "n_shared_index": 0, "primitives": primitives, "runs": [(0, 0, 3)],
           "sections": [{"first_packed": 0, "first_shared": 0, "first_prim": 0, "first_run": 0, "npacked": 8,
                         "nprim": 3, "nrun": 1, "page": 0, "leafIndex": 0, "layerData": 0, "flags": 0,
                         "nodes": section_tree(3)}],
           "simd_nodes": mc.build_simd_tree([(k, ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))) for k in (0, 2, 4)])}
    rec.update(over)
    return rec


def kinds(rec):
    return sorted({v.kind for v in meshcheck.check(rec)})


class CheckerTests(unittest.TestCase):
    def test_vanilla_shaped_mesh_has_no_violations(self):
        self.assertEqual(meshcheck.check(vanilla_record()), [])

    def test_section_tree_codec(self):
        leaves, seen, problems = meshcheck.walk_section_tree(section_tree(5))
        self.assertEqual((sorted(leaves), len(seen), problems), ([0, 1, 2, 3, 4], 9, []))
        # vault_cart_01's first nodes (FO4 and vanilla alike): hiData 0x0d = inner, right child at +12
        cart = bytes.fromhex("0000000d11000d0b00000707000003050000020300e000340e0000320000e236")
        leaves, seen, problems = meshcheck.walk_section_tree(cart)
        self.assertIn(26, leaves)                                           # 0x34 >> 1
        self.assertTrue(any("out of range" in p for p in problems))        # the cut tree runs past its 8 nodes

    def test_section_slots_use_the_next_sections_shared_start(self):
        secs = [{"first_shared": 0, "npacked": 4}, {"first_shared": 6, "npacked": 2}, {"first_shared": 2, "npacked": 1}]
        self.assertEqual(meshcheck.section_slots(secs, 10), [6, 6, 5])

    def test_flat_convex_flags_and_simd_presence(self):
        self.assertEqual(kinds(vanilla_record(flat=0)), ["flat_convex"])
        rec = vanilla_record()
        rec["sections"][0]["flags"] = 1
        self.assertEqual(kinds(rec), ["section_flags"])
        self.assertEqual(kinds(vanilla_record(has_simd=0)), ["has_simd"])

    def test_primitive_rules(self):
        rec = vanilla_record(primitives=[(0, 1, 2, 3), DEAD, (1, 2, 5, 4)])
        v = meshcheck.check(rec)
        self.assertEqual([x.kind for x in v], ["prim_type"])
        self.assertEqual((v[0].section, v[0].index), (0, 1))
        self.assertIn("special primitive of type 222", v[0].detail)
        rec = vanilla_record(primitives=[(0, 1, 2, 3), (5, 7, 3, 7), (1, 2, 5, 4)])
        self.assertEqual(kinds(rec), [])                                    # special type 3: the decoder knows it
        rec = vanilla_record(primitives=[(0, 1, 2, 3), (4, 5, 9, 9), (1, 2, 5, 4)])
        self.assertEqual(kinds(rec), ["prim_index"])                        # 9 of 8 vertex slots

    def test_tree_and_run_rules(self):
        rec = vanilla_record()
        rec["sections"][0]["nodes"] = section_tree(4)                       # a leaf names primitive 3 of 3
        self.assertEqual(kinds(rec), ["tree"])
        rec = vanilla_record(runs=[(0, 0, 2)])
        self.assertEqual(kinds(rec), ["runs"])
        rec = vanilla_record(runs=[(0, 0, 2), (1, 2, 1)])
        rec["sections"][0]["nrun"] = 2
        self.assertEqual(kinds(rec), [])

    def test_simd_key_rules(self):
        box = ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
        tree = lambda *keys: mc.build_simd_tree([(k, box) for k in keys])
        v = meshcheck.check(vanilla_record(simd_nodes=tree(0, 2, 4, 5)))     # the old per-triangle leaf of quad 2
        self.assertEqual([x.kind for x in v], ["key_odd", "key_dup"])
        self.assertIn("past the end of 3 primitives", v[0].detail)
        v = meshcheck.check(vanilla_record(simd_nodes=tree(0, 1, 2, 4)))
        self.assertEqual([x.kind for x in v], ["key_odd", "key_dup"])
        self.assertIn("is primitive 1", v[0].detail)
        self.assertEqual(kinds(vanilla_record(simd_nodes=tree(0, 2, 6))), ["key_missing", "key_prim"])
        self.assertEqual(kinds(vanilla_record(simd_nodes=tree(0, 2, 4, 256))), ["key_section"])
        self.assertEqual(kinds(vanilla_record(simd_nodes=tree(0, 2))), ["key_missing"])

    def test_cli_reports_and_exits_nonzero_only_on_violations(self):
        import io
        import tempfile
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as d:
            out = io.StringIO()
            with redirect_stdout(out):
                rc = meshcheck.main([d])                                     # an empty folder: nothing to report
            self.assertEqual(rc, 0)
            self.assertIn("0 NIFs, 0 compressed meshes, 0 models with violations, 0 violations", out.getvalue())


if __name__ == "__main__":
    unittest.main()
