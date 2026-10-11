"""FO4 precombine hull primitives (SCOL\\CM*.NIF, fo4collision.SECTION_HULLS): record decode, shape keys, plain-geometry
surface, neutralisation in the Starfield mesh copy and the convex-body emission (synthetic data, no game files)."""
import os
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import fo4collision as fc, hkpackfile, meshcollision  # noqa: E402


class FakePack:
    """Just enough of hkpackfile.Packfile for a hand-built hknpCompressedMeshShapeData: a flat data section plus the
    pointer targets of its hkArray fields (hkArray: pointer @0, size i32 @8)."""

    def __init__(self, data: bytes, pointers: dict):
        self.data, self.pointers = bytes(data), pointers

    def raw(self, off, n):
        return self.data[off:off + n]

    def unpack(self, fmt, off):
        return struct.unpack_from(fmt, self.data, off)

    def pointer(self, off):
        return self.pointers.get(off)

    def array(self, off):
        size, = self.unpack("<i", off + 8)
        return self.pointer(off), size


DMIN, DMAX = (0.0, 0.0, 0.0), (8.0, 2.0, 2.0)
QUAD = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
TETRA = [(2.0, 0.0, 0.0), (3.0, 0.0, 0.0), (2.0, 1.0, 0.0), (2.0, 0.0, 1.0)]
PYRAMID = [(5.0, 0.0, 0.0), (6.0, 0.0, 0.0), (6.0, 1.0, 0.0), (5.0, 1.0, 0.0), (5.5, 0.5, 1.0)]
D, S, P, X, K, V = 0, 256, 352, 368, 384, 400          # data object, section, primitives, shared index, packed, shared


def _shared_word(v):
    bits = (0x1FFFFF, 0x1FFFFF, 0x3FFFFF)
    q = [round((v[a] - DMIN[a]) / (DMAX[a] - DMIN[a]) * bits[a]) for a in range(3)]
    return q[0] | (q[1] << 21) | (q[2] << 42)


def build_mesh(flags=fc.SECTION_HULLS, w0_tetra=0x0852, w0_pyramid=0x0952):
    """One section: a unit quad of 4 packed vertices (one quad primitive) and two hull primitives: a tetrahedron (record
    0x0852: count 4) and a square pyramid (record 0x0952: count (4) + bit 8 = 5, the form FO4 uses for a few hulls), the
    second one as (x, x, x, x) (leaf index equal to the slot, as in CM00163A1B). An unused 0xDEAD slot sits between."""
    b = bytearray(480)
    struct.pack_into("<3f", b, D + 32, *DMIN)
    struct.pack_into("<3f", b, D + 48, *DMAX)
    for off, n in ((80, 1), (96, 4), (112, 6), (128, 4), (144, 9), (160, 0)):
        struct.pack_into("<i", b, D + off + 8, n)
    struct.pack_into("<3f", b, S + 48, 0.0, 0.0, 0.0)                 # codec offset
    struct.pack_into("<3f", b, S + 60, 0.001, 0.001, 0.001)           # codec scale
    struct.pack_into("<4I", b, S + 72, 0, (0 << 8) | 4, (0 << 8) | 4, 0)
    b[S + 88], b[S + 89], b[S + 93] = 4, 6, flags
    prims = [(0, 1, 2, 3), (4, 1, 1, 1), (0xDE, 0xAD, 0xDE, 0xAD), (7, 7, 7, 7)]
    for j, q in enumerate(prims):
        b[P + 4 * j:P + 4 * j + 4] = bytes(q)
    struct.pack_into("<6H", b, X, w0_tetra, 0, 0x3C24, w0_pyramid, 4, 0x3C24)
    for j, v in enumerate(QUAD):
        struct.pack_into("<I", b, K + 4 * j, round(v[0] * 1000) | (round(v[1] * 1000) << 11) | (round(v[2] * 1000) << 22))
    for j, v in enumerate(TETRA + PYRAMID):
        struct.pack_into("<Q", b, V + 8 * j, _shared_word(v))
    return FakePack(b, {D + 80: S, D + 96: P, D + 112: X, D + 128: K, D + 144: V, D + 160: None, S: None})


def _close(a, b, tol=1e-4):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


class HullDecodeTests(unittest.TestCase):
    def test_hull_primitives_are_decoded_from_their_records(self):
        hulls = fc.compressed_mesh_hulls(build_mesh(), D)
        self.assertEqual([(s, j, slot, first, count) for s, j, slot, first, count, _ in hulls],
                         [(0, 1, 0, 0, 4), (0, 3, 3, 4, 5)])
        for (_, _, _, _, _, pts), want in zip(hulls, (TETRA, PYRAMID)):
            self.assertEqual(len(pts), len(want))
            for got, w in zip(pts, want):
                self.assertTrue(_close(got, w), (got, w))

    def test_shape_keys_cover_triangles_only(self):
        keys = fc.compressed_mesh_keys(build_mesh(), D)
        self.assertEqual([k for k, _ in keys], [0, 1])                 # the quad's two triangles; no key for a hull
        lo, hi = keys[0][1]
        self.assertTrue(_close(lo, (0.0, 0.0, 0.0)) and _close(hi, (1.0, 1.0, 0.0)))

    def test_plain_geometry_includes_closed_hull_surfaces(self):
        points, tris = fc._compressed_mesh(build_mesh(), D)
        self.assertEqual(len(tris), 2 + 4 + 6)                         # quad, tetrahedron, square pyramid
        for lo_x, hi_x, ntri in ((2.0, 3.0, 4), (5.0, 6.0, 6)):
            hull_tris = [t for t in tris[2:] if lo_x - 1e-4 <= points[t[0]][0] <= hi_x + 1e-4]
            self.assertEqual(len(hull_tris), ntri)
            for t in hull_tris:
                for i in t:
                    self.assertTrue(lo_x - 1e-4 <= points[i][0] <= hi_x + 1e-4)
            used = sorted({i for t in hull_tris for i in t})
            remap = {i: k for k, i in enumerate(used)}
            meshcollision._hull_links([[remap[i] for i in t] for t in hull_tris], len(used))   # closed surface

    def test_hull_primitives_need_the_section_flag(self):
        with self.assertRaisesRegex(hkpackfile.PackfileError, "shared vertex index"):
            fc.compressed_mesh_keys(build_mesh(flags=0), D)            # read as triangles, as before this decoder

    def test_malformed_hull_records_are_rejected(self):
        with self.assertRaisesRegex(hkpackfile.PackfileError, "hull record tag"):
            fc.compressed_mesh_hulls(build_mesh(w0_tetra=0x0853), D)
        with self.assertRaisesRegex(hkpackfile.PackfileError, "outside the 9 shared vertices"):
            fc.compressed_mesh_hulls(build_mesh(w0_pyramid=(6 << 9) | 0x52), D)   # 4 + 6 > 9

    def test_hull_surface_without_volume_is_empty_and_flat_sets_become_slabs(self):
        self.assertEqual(fc.hull_surface([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]), ([], []))
        pts, faces = fc.hull_surface(QUAD)
        self.assertEqual((len(pts), len(faces)), (8, 12))


class HullEmissionTests(unittest.TestCase):
    def test_neutralize_hulls_rewrites_primitives_records_and_reports_sections(self):
        p = build_mesh()
        fo4 = {name: (p.raw(p.pointer(D + off), meshcollision.ELEM_SIZE[name] * p.array(D + off)[1]), p.array(D + off)[1])
               for name, off in meshcollision.FO4_ARRAYS.items() if p.array(D + off)[1]}
        hulls = fc.compressed_mesh_hulls(p, D)
        touched = meshcollision._neutralize_hulls(fo4, hulls)
        self.assertEqual(touched, {0})
        prims = [tuple(fo4["primitives"][0][4 * j:4 * j + 4]) for j in range(4)]
        self.assertEqual(prims, [(0, 1, 2, 3), (4, 4, 4, 4), (0xDE, 0xAD, 0xDE, 0xAD), (7, 7, 7, 7)])
        sidx = struct.unpack("<6H", fo4["sharedVerticesIndex"][0])
        self.assertEqual(sidx, (0, 0, 0x3C24, 4, 4, 0x3C24))             # record word 0 -> the hull's first vertex
        self.assertEqual(meshcollision._neutralize_hulls(fo4, []), set())

    def test_emit_hull_bakes_the_part_transform_and_rebuilds_a_closed_hull(self):
        captured = {}

        def fake_write(w, t, verts, faces, face_raw, planes, radius):
            captured.update(verts=verts, faces=faces, radius=radius)
            return 7
        R = (0.0, -1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)              # +90 degrees about z
        with patch.object(meshcollision, "_write_convex_shape", fake_write):
            self.assertEqual(meshcollision._emit_hull(None, None, TETRA, R, (10.0, 0.0, 0.0)), 7)
            self.assertIsNone(meshcollision._emit_hull(None, None, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]))
        verts = captured["verts"]
        self.assertEqual(len(verts), 4)
        self.assertTrue(any(_close(v, (10.0, 2.0, 0.0)) for v in verts))   # (2, 0, 0) rotated then moved
        self.assertTrue(any(_close(v, (10.0, 3.0, 0.0)) for v in verts))   # (3, 0, 0)
        self.assertTrue(any(_close(v, (9.0, 2.0, 0.0)) for v in verts))    # (2, 1, 0)
        self.assertEqual(len(captured["faces"]), 4)
        meshcollision._hull_links(captured["faces"], 4)                     # closed
        self.assertEqual(captured["radius"], 0.0)

    def test_transplant_refuses_meshes_with_hull_primitives(self):
        p = build_mesh()
        with patch.object(hkpackfile, "Packfile", lambda blob: p), \
                patch.object(meshcollision, "_fo4_mesh_body", lambda pack: (D, (0.0, 0.0, 0.0))):
            with self.assertRaisesRegex(hkpackfile.PackfileError, "hull primitives"):
                meshcollision.transplant(b"", b"")


if __name__ == "__main__":
    unittest.main()
