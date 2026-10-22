"""Reading back converted Starfield collision (src/fo4sf/sfbodies.py) from synthetic tagfiles and NIFs (no game data)."""
import math
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import meshcheck, meshcollision, nif, sfbodies, sfcollision, sfnif  # noqa: E402


def _v(x):
    """Havok varint (1 or 2 bytes, enough for these fixtures)."""
    assert 0 <= x < 0x4000
    return bytes([x]) if x < 0x80 else bytes([0x80 | (x >> 8), x & 0xFF])


def _sec(tag, payload, leaf=True):
    return struct.pack(">I", ((1 if leaf else 0) << 30) | (len(payload) + 8)) + tag + payload


class TagWriter:
    """Minimal TAG0 writer: named types with sizes and fields, items and pointer patches (what hktagfile reads)."""

    def __init__(self):
        self.types = []          # (name, size, [(field, offset, type name)], parent type name or None)
        self.items = []          # (type name, payload, count)
        self.ptrs = []           # (item, offset, target item)

    def type(self, name, size, fields=(), parent=None):
        self.types.append((name, size, list(fields), parent))

    def item(self, tname, payload, count=1):
        self.items.append((tname, bytearray(payload), count))
        return len(self.items)

    def ptr(self, item, offset, target):
        self.ptrs.append((item, offset, target))

    def build(self):
        names = [t[0] for t in self.types]
        tidx = {n: i + 1 for i, n in enumerate(names)}
        fields = sorted({f for t in self.types for f, _, _ in t[2]})
        fidx = {f: i for i, f in enumerate(fields)}
        tst = b"".join(n.encode() + b"\0" for n in names)
        fst = b"".join(f.encode() + b"\0" for f in fields)
        tna = _v(len(names) + 1) + b"".join(_v(i) + _v(0) for i in range(len(names)))
        tbdy = b""
        for name, size, fl, parent in self.types:
            opt = 0x8 | (0x20 if fl else 0)
            tbdy += _v(tidx[name]) + _v(tidx[parent] if parent else 0) + _v(opt) + _v(size) + _v(4)
            if fl:
                tbdy += _v(len(fl)) + b"".join(_v(fidx[f]) + _v(0) + _v(o) + _v(tidx[t]) for f, o, t in fl)
        data, offsets = bytearray(), []
        for _, payload, _ in self.items:
            data += b"\0" * (-len(data) % 16)
            offsets.append(len(data))
            data += payload
        data += b"\0" * (-len(data) % 16)
        pt = []
        for item, off, target in self.ptrs:
            at = offsets[item - 1] + off
            struct.pack_into("<Q", data, at, target)
            pt.append(at)
        item_tab = bytes(12) + b"".join(struct.pack("<III", tidx[t], o, c) for (t, _, c), o in zip(self.items, offsets))
        ptch = struct.pack("<II", 1, len(pt)) + struct.pack(f"<{len(pt)}I", *pt) if pt else b""
        types = (_sec(b"TST1", tst) + _sec(b"TNA1", tna) + _sec(b"FST1", fst) + _sec(b"TBDY", tbdy))
        body = (_sec(b"SDKV", b"20190200") + _sec(b"DATA", bytes(data)) + _sec(b"TYPE", types, leaf=False)
                + _sec(b"INDX", _sec(b"ITEM", item_tab) + _sec(b"PTCH", ptch), leaf=False))
        return _sec(b"TAG0", body, leaf=False)


BODY = "hknpPhysicsSystemData::bodyCinfoWithAttachment"
PSD = "hknpPhysicsSystemData"


def body_types(w, shape_type):
    """The body types, and the physics system as item 1 (the tagfile root, as meshcollision writes it)."""
    w.type("ptr", 8)
    w.type("float3", 12)
    w.type("u8", 1)
    w.type("face", 4)
    w.type(BODY, 64, [("shape", 0, "ptr"), ("position", 16, "float3"), ("orientation", 32, "float3"),
                      ("collisionFilterInfo", 48, "u8")])
    w.type(PSD, 16, [("bodyCinfos", 0, "ptr")])
    assert w.item(PSD, bytes(16)) == 1


def add_bodies(w, bodies, layer=1):
    """One body cinfo array [(shape item, position, quaternion)], which the system's bodyCinfos lists."""
    b = bytearray(64 * len(bodies))
    for k, (_, pos, quat) in enumerate(bodies):
        struct.pack_into("<3f", b, 64 * k + 16, *pos)
        struct.pack_into("<4f", b, 64 * k + 32, *quat)
        struct.pack_into("<I", b, 64 * k + 48, layer)
    i = w.item(BODY, b, len(bodies))
    for k, (shape_item, _, _) in enumerate(bodies):
        w.ptr(i, 64 * k, shape_item)
    w.ptr(1, 0, i)
    return i


def add_body(w, shape_item, pos=(0, 0, 0), quat=(0, 0, 0, 1), layer=1):
    return add_bodies(w, [(shape_item, pos, quat)], layer)


def convex_blob(verts, faces, radius=0.0, pos=(0, 0, 0), quat=(0, 0, 0, 1), kind="hknpConvexShape"):
    w = TagWriter()
    body_types(w, kind)
    add_body(w, add_convex(w, verts, faces, radius, kind), pos, quat)
    return w.build()


def add_convex(w, verts, faces, radius=0.0, kind="hknpConvexShape"):
    """A hull shape item (and its types, once per writer): float3 vertices, faces into u8 indices."""
    for name, fields in (("hull", [("vertices", 0, "ptr"), ("faces", 16, "ptr"), ("indices", 32, "ptr")]),
                         (kind, [("convexRadius", 8, "float3"), ("hull", 16, "hull")])):
        if not any(t[0] == name for t in w.types):
            w.type(name, 48 if name == "hull" else 80, fields)
    shape = bytearray(80)
    struct.pack_into("<f", shape, 8, radius)
    s = w.item(kind, shape)
    vi = w.item("float3", b"".join(struct.pack("<3f", *v) for v in verts), len(verts))
    fr, idx = b"", b""
    for f in faces:
        fr += struct.pack("<HBB", len(idx), len(f), 0)
        idx += bytes(f)
    fi = w.item("face", fr, len(faces))
    ii = w.item("u8", idx, len(idx))
    w.ptr(s, 16, vi)
    w.ptr(s, 32, fi)
    w.ptr(s, 48, ii)
    return s


def cube(lo, hi):
    v = [(x, y, z) for z in (lo[2], hi[2]) for y in (lo[1], hi[1]) for x in (lo[0], hi[0])]
    faces = [[0, 2, 3, 1], [4, 5, 7, 6], [0, 1, 5, 4], [2, 6, 7, 3], [0, 4, 6, 2], [1, 3, 7, 5]]
    return v, faces


def _section_tree(n):
    """An Aabb4BytesCodec tree naming primitives 0 .. n - 1 once: inner nodes (hiData 3: left child next, right child
    two on) chaining leaves (hiData primitive << 1)."""
    return b"".join(bytes([0, 0, 0, 3, 0, 0, 0, 2 * j]) for j in range(n - 1)) + bytes([0, 0, 0, 2 * (n - 1)])


def mesh_blob(packed, prims, n_shared_idx=0, section_off=(0, 0, 0), scale=(0.01, 0.01, 0.01), has_simd=1, keys=None):
    """One compressed-mesh body: one section of packed vertices (quantised 11/11/10 bits) and primitives, laid out as
    meshcheck's vanilla rules want (flat-convex tree, a section tree and one data run over every primitive, a SIMD tree
    with one even key per primitive unless keys says otherwise)."""
    w = TagWriter()
    body_types(w, "hknpCompressedMeshShape")
    w.type("tree", 160, [("sections", 64, "ptr"), ("primitives", 80, "ptr"), ("sharedVerticesIndex", 96, "ptr"),
                         ("packedVertices", 112, "ptr"), ("sharedVertices", 128, "ptr"),
                         ("primitiveDataRuns", 144, "ptr")])
    w.type("simd", 16, [("nodes", 0, "ptr")])
    w.type("hknpCompressedMeshShapeData", 192, [("meshTree", 0, "tree"), ("simdTree", 160, "simd"),
                                                ("hasSimdTree", 176, "u8")])
    w.type("hknpCompressedMeshShape", 32, [("data", 8, "ptr")])
    w.type("section", 96, [("nodes", 0, "ptr")])
    w.type("u32", 4)
    w.type("u16", 2)
    w.type("simdnode", 128)
    s = w.item("hknpCompressedMeshShape", bytes(32))
    data = bytearray(192)
    data[60], data[176] = meshcheck.FLAT_CONVEX, has_simd                   # meshTree.primitiveStoresIsFlatConvex
    d = w.item("hknpCompressedMeshShapeData", data)
    w.ptr(s, 8, d)
    sec = bytearray(96)
    struct.pack_into("<3f", sec, 48, *section_off)
    struct.pack_into("<3f", sec, 60, *scale)
    struct.pack_into("<4I", sec, 72, 0, 0, 0, 0)
    sec[88], sec[89], sec[90] = len(packed), len(prims), 1
    si = w.item("section", sec, 1)
    nodes = _section_tree(len(prims))
    w.ptr(si, 0, w.item("u32", nodes, len(nodes) // 4))
    pk = b"".join(struct.pack("<I", q[0] | (q[1] << 11) | (q[2] << 22)) for q in packed)
    pi = w.item("u32", pk, len(packed))
    pr = w.item("u32", b"".join(bytes(p) for p in prims), len(prims))
    sh = w.item("u16", bytes(2 * n_shared_idx), n_shared_idx) if n_shared_idx else None
    w.ptr(d, 64, si)
    w.ptr(d, 112, pi)
    w.ptr(d, 80, pr)
    w.ptr(d, 144, w.item("u32", struct.pack("<HBB", 0, 0, len(prims)), 1))
    if sh:
        w.ptr(d, 96, sh)
    simd = meshcollision.build_simd_tree([(k, ((0, 0, 0), (1, 1, 1))) for k in
                                          (range(0, 2 * len(prims), 2) if keys is None else keys)])
    w.ptr(d, 160, w.item("simdnode", simd, len(simd) // 128))
    add_body(w, s)
    return w.build()


def compound_blob(radius, scale):
    """A dynamic compound (meshcollision._emit_dynamic_compound's layout) of one instance: the unit cube hull with this
    convex radius, scaled by `scale`."""
    v, f = cube((0, 0, 0), (1, 1, 1))
    w = TagWriter()
    body_types(w, "hknpCompoundShape")
    w.type("hull", 48, [("vertices", 0, "ptr"), ("faces", 16, "ptr"), ("indices", 32, "ptr")])
    w.type("hknpConvexShape", 80, [("convexRadius", 8, "float3"), ("hull", 16, "hull")])
    w.type("freelist", 16, [("elements", 0, "ptr")])
    w.type("hknpCompoundShape", 32, [("instances", 16, "freelist")])
    w.type("instance", 64, [("rotation", 0, "float3"), ("translation", 16, "float3"), ("scale", 32, "float3"),
                            ("shape", 48, "ptr")])
    shape = bytearray(80)
    struct.pack_into("<f", shape, 8, radius)
    child = w.item("hknpConvexShape", shape)
    vi = w.item("float3", b"".join(struct.pack("<3f", *p) for p in v), len(v))
    fr, idx = b"", b""
    for face in f:
        fr += struct.pack("<HBB", len(idx), len(face), 0)
        idx += bytes(face)
    fi, ii = w.item("face", fr, len(f)), w.item("u8", idx, len(idx))
    for off, target in ((16, vi), (32, fi), (48, ii)):
        w.ptr(child, off, target)
    cs = w.item("hknpCompoundShape", bytearray(32))
    inst = bytearray(64)
    struct.pack_into("<4f3f4x3f", inst, 0, 0, 0, 0, 1, 0, 0, 0, *scale)
    ins = w.item("instance", inst, 1)
    w.ptr(ins, 48, child)
    w.ptr(cs, 16, ins)
    add_body(w, cs)
    return w.build()


class SfBodiesTests(unittest.TestCase):
    def test_convex_cube_triangles_and_radius(self):
        v, f = cube((0, 0, 0), (2, 1, 0.5))
        bodies = sfbodies.blob_bodies(convex_blob(v, f))
        self.assertEqual(len(bodies), 1)
        tris = bodies[0]["triangles"]
        self.assertEqual(len(tris), 12)
        self.assertEqual(bodies[0]["layer"], 1)
        zs = [p[2] for t in tris for p in t]
        self.assertAlmostEqual(max(zs), 0.5, places=6)
        # a convex radius pushes every face out along its normal: the top rises by the radius
        tris = sfbodies.blob_bodies(convex_blob(v, f, radius=0.05))[0]["triangles"]
        self.assertAlmostEqual(max(p[2] for t in tris for p in t), 0.55, places=5)
        self.assertAlmostEqual(min(p[0] for t in tris for p in t), -0.05, places=5)

    def test_body_position_and_rotation_are_applied(self):
        v, f = cube((0, 0, 0), (1, 1, 1))
        q = (0, 0, math.sin(math.pi / 4), math.cos(math.pi / 4))       # 90 degrees about +z (counter-clockwise)
        tris = sfbodies.blob_bodies(convex_blob(v, f, pos=(10, 0, 0), quat=q))[0]["triangles"]
        pts = {tuple(round(c, 5) for c in p) for t in tris for p in t}
        self.assertIn((10.0, 1.0, 0.0), pts)                        # (1, 0, 0) -> (0, 1, 0), then + (10, 0, 0)
        self.assertIn((9.0, 0.0, 1.0), pts)                         # (0, 1, 1) -> (-1, 0, 1)

    def test_sphere_is_an_octahedron_of_its_radius(self):
        w = convex_blob([(1, 2, 3)], [], radius=0.5, kind="hknpSphereShape")
        tris = sfbodies.blob_bodies(w)[0]["triangles"]
        self.assertEqual(len(tris), 8)
        self.assertAlmostEqual(max(p[2] for t in tris for p in t), 3.5)

    def test_compressed_mesh_quad_and_unused_slot(self):
        packed = [(0, 0, 0), (100, 0, 0), (100, 100, 0), (0, 100, 0)]
        prims = [(0, 1, 2, 3), (0x2D, 0x2D, 0x2D, 0x2D), (1, 1, 1, 1)]   # quad, unused 0xDEAD-style slot, point
        tris = sfbodies.blob_bodies(mesh_blob(packed, prims, section_off=(5, 0, 2)))[0]["triangles"]
        self.assertEqual(len(tris), 2)
        pts = {tuple(round(c, 5) for c in p) for t in tris for p in t}
        self.assertEqual(pts, {(5.0, 0.0, 2.0), (6.0, 0.0, 2.0), (6.0, 1.0, 2.0), (5.0, 1.0, 2.0)})

    def test_compressed_mesh_out_of_range_section_is_an_error(self):
        blob = bytearray(mesh_blob([(0, 0, 0)] * 3, [(0, 1, 2, 2)]))
        # claim 9 packed vertices in a section whose array holds 3
        at = blob.find(struct.pack("<3f", 0.01, 0.01, 0.01)) + 28
        blob[at] = 9
        with self.assertRaises(sfbodies.BodyError):
            sfbodies.blob_bodies(bytes(blob))

    def test_compound_instances_are_moved_and_free_slots_skipped(self):
        """A movable item's dynamic compound (meshcollision._emit_dynamic_compound): v6's core stage stopped on 62 of
        them ("unsupported shape hknpCompoundShape", PC 2026-10-18)."""
        v, f = cube((0, 0, 0), (1, 1, 1))
        w = TagWriter()
        body_types(w, "hknpCompoundShape")
        w.type("hull", 48, [("vertices", 0, "ptr"), ("faces", 16, "ptr"), ("indices", 32, "ptr")])
        w.type("hknpConvexShape", 80, [("convexRadius", 8, "float3"), ("hull", 16, "hull")])
        w.type("freelist", 16, [("elements", 0, "ptr")])
        w.type("hknpCompoundShape", 32, [("instances", 16, "freelist")])
        w.type("instance", 64, [("rotation", 0, "float3"), ("translation", 16, "float3"), ("scale", 32, "float3"),
                                ("shape", 48, "ptr")])
        child = w.item("hknpConvexShape", bytearray(80))
        vi = w.item("float3", b"".join(struct.pack("<3f", *p) for p in v), len(v))
        fr, idx = b"", b""
        for face in f:
            fr += struct.pack("<HBB", len(idx), len(face), 0)
            idx += bytes(face)
        fi, ii = w.item("face", fr, len(f)), w.item("u8", idx, len(idx))
        for off, target in ((16, vi), (32, fi), (48, ii)):
            w.ptr(child, off, target)
        cs = w.item("hknpCompoundShape", bytearray(32))
        inst = bytearray(128)
        h = math.sqrt(0.5)
        struct.pack_into("<4f3f4x3f", inst, 0, 0, 0, h, h, 10, 0, 0, 2, 2, 2)      # 90 degrees about z, x2, +10 x
        struct.pack_into("<4f", inst, 64, 0, 0, 0, 1)                             # second slot free (no shape)
        ins = w.item("instance", inst, 2)
        w.ptr(ins, 48, child)
        w.ptr(cs, 16, ins)
        add_body(w, cs)
        bodies = sfbodies.blob_bodies(w.build())
        self.assertEqual(bodies[0]["shape"], "hknpCompoundShape")
        pts = {tuple(round(c, 4) for c in p) for t in bodies[0]["triangles"] for p in t}
        self.assertEqual(min(p[0] for p in pts), 8.0)                            # x' = 10 - 2y
        self.assertEqual(max(p[1] for p in pts), 2.0)                            # y' = 2x
        self.assertEqual(max(p[2] for p in pts), 2.0)
        self.assertEqual(len(bodies[0]["triangles"]), 12)

    def test_unsupported_shape_raises(self):
        v, f = cube((0, 0, 0), (1, 1, 1))
        with self.assertRaises(sfbodies.BodyError):
            sfbodies.blob_bodies(convex_blob(v, f, kind="hknpCapsuleThing"))

    def test_body_orientation_must_be_a_unit_quaternion(self):
        v, f = cube((0, 0, 0), (1, 1, 1))
        for quat in ((0, 0, 0, 0), (0, 0, 0, 2), (0, 0, 0.5, 0.5)):
            with self.assertRaises(sfbodies.BodyError, msg=quat):
                sfbodies.blob_bodies(convex_blob(v, f, quat=quat))
        self.assertEqual(len(sfbodies.blob_bodies(convex_blob(v, f, quat=(0, 0, 0.6, 0.8)))), 1)

    def test_pieces_bound_a_turned_convex_radius_exactly(self):
        # The triangles push faces out by the radius (and an unused vertex is an octahedron): turned 45 degrees about z
        # they reach 0.35 m past the core on x / y, not the 0.5 m the ball does. The pieces carry the radius instead.
        v, f = cube((0, 0, 0), (1, 1, 1))
        blob = convex_blob(v + [(10, 0, 0)], f, radius=0.5)
        c = 0.5 ** 0.5
        n = sfnif.build_static_nif(b"Test", [], child_collision_blobs=[(blob, (0, 0, 0), (c, -c, 0, c, c, 0, 0, 0, 1))])
        body = sfbodies.nif_bodies(nif.serialize(n))[0]
        (pts, radius), = body["pieces"]
        self.assertEqual(radius, 0.5)
        self.assertAlmostEqual(max(p[0] for p in pts) + radius, 10 * c + 0.5, places=5)
        self.assertAlmostEqual(max(p[1] for p in pts) + radius, 10 * c + 0.5, places=5)
        self.assertAlmostEqual(min(p[0] for p in pts) - radius, -c - 0.5, places=5)    # corner (0, 1, z) turned
        tri_pts = [p for t in body["triangles"] for p in t]
        self.assertLess(max(p[0] for p in tri_pts), 10 * c + 0.5 - 0.1)               # the surfaces fall short

    def test_compound_cannot_scale_a_convex_radius(self):
        # Whether Havok scales the radius with the instance is not known: such a body is an error, not a guess.
        for scale, ok in (((1, 1, 1), True), ((-1, 1, 1), True), ((2, 2, 2), False), ((1, 1, 0.5), False)):
            if ok:
                (pts, radius), = sfbodies.blob_bodies(compound_blob(0.1, scale))[0]["pieces"]
                self.assertEqual(round(radius, 6), 0.1)
            else:
                with self.assertRaises(sfbodies.BodyError, msg=scale):
                    sfbodies.blob_bodies(compound_blob(0.1, scale))
        (pts, radius), = sfbodies.blob_bodies(compound_blob(0.0, (2, 2, 2)))[0]["pieces"]   # no radius: any scale
        self.assertEqual((radius, max(p[1] for p in pts)), (0.0, 2.0))

    def test_nif_node_transform_places_each_body(self):
        v, f = cube((0, 0, 0), (1, 1, 1))
        blob = convex_blob(v, f)
        rot = (0, -1, 0, 1, 0, 0, 0, 0, 1)                           # +x -> +y (row-major)
        n = sfnif.build_static_nif(b"Test", [], child_collision_blobs=[blob, (blob, (0, 0, 3), rot)])
        bodies = sfbodies.nif_bodies(nif.serialize(n))
        self.assertEqual(len(bodies), 2)
        first = {tuple(round(c, 5) for c in p) for t in bodies[0]["triangles"] for p in t}
        second = {tuple(round(c, 5) for c in p) for t in bodies[1]["triangles"] for p in t}
        self.assertIn((1.0, 1.0, 1.0), first)
        self.assertIn((0.0, 1.0, 3.0), second)                       # (1, 0, 0) rotated to (0, 1, 0), lifted 3
        self.assertIn((-1.0, 1.0, 4.0), second)
        st = sfbodies.triangle_stats(bodies)
        self.assertEqual(st["bodies"], 2)
        self.assertEqual(st["max"][2], 4.0)

    def test_bodies_are_the_ones_the_root_system_lists(self):
        # Every body cinfo item was read, never the system's bodyCinfos: a system listing no body read as an orphan body
        # on the mesh, and one listing a body 8 m off behind a type of the same name read as the orphan instead.
        v, f = cube((-0.4, -0.4, 0), (0.4, 0.4, 1))
        self.assertEqual(len(sfbodies.blob_bodies(convex_blob(v, f))), 1)                    # control

        def orphan(more=None):
            w = TagWriter()
            body_types(w, "hknpConvexShape")
            body = bytearray(64)
            struct.pack_into("<4f", body, 32, 0, 0, 0, 1)
            w.ptr(w.item(BODY, body), 0, add_convex(w, v, f))                                 # listed by nothing
            if more:
                more(w)
            return w.build()
        alt = BODY[:-1] + "X"                          # renamed to BODY after the build: two types, one name

        def listed_far(w):
            w.type(alt, 64, next(t[2] for t in w.types if t[0] == BODY))
            body = bytearray(64)
            struct.pack_into("<3f4x4f", body, 16, 8, 0, 0, 0, 0, 0, 1)
            i = w.item(alt, body)
            w.ptr(i, 0, add_convex(w, v, f))
            w.ptr(1, 0, i)
        cases = {"no bodyCinfos": orphan(),
                 "listed body behind a same-named type": orphan(listed_far).replace(alt.encode() + b"\0",
                                                                                    BODY.encode() + b"\0"),
                 "two systems": orphan(lambda w: (w.ptr(1, 0, 2), w.item(PSD, bytes(16))))}
        for name, blob in cases.items():
            with self.assertRaises(sfbodies.BodyError, msg=name):
                sfbodies.blob_bodies(blob)

    def test_template_corners_are_read_only_for_a_body_of_an_accepted_template(self):
        # Any hknpBoxShape in a 6,168-byte blob was read from the box template's corners at 592: a box in a blob
        # check_template rejects, or a compound's child box, read as whatever sat there, not as its own hull 8 m off.
        def blob(shape, rows):
            def build(pad):
                w = TagWriter()
                body_types(w, "hknpBoxShape")
                w.type("filler", 800)
                w.type("p" * pad, 4)                   # each character is one byte of the type strings
                w.item("filler", bytes(800))           # right after the system: blob offsets 48 .. 848
                add_body(w, shape(w))
                return bytearray(w.build())
            b = build(1 + sfcollision.BLOB_SIZE - len(build(1)))
            for off, coef in sfcollision.LINEAR.items():          # a box on the mesh, where the template keeps it
                struct.pack_into("<f", b, off, sum(c * x for c, x in zip(coef, (0, 0, 0.5, 0.4, 0.4, 0.5))))
            for k in range(3 if rows else 0):
                struct.pack_into("<3f", b, 528 + 16 * k, *(float(a == k) for a in range(3)))
            return bytes(b)

        def box(lo, hi):
            return lambda w: add_convex(w, *cube(lo, hi), kind="hknpBoxShape")

        def compound(w):
            child = box((7.6, -0.4, 0), (8.4, 0.4, 1))(w)
            w.type("freelist", 16, [("elements", 0, "ptr")])
            w.type("hknpCompoundShape", 32, [("instances", 16, "freelist")])
            w.type("instance", 64, [("rotation", 0, "float3"), ("translation", 16, "float3"),
                                    ("scale", 32, "float3"), ("shape", 48, "ptr")])
            inst = bytearray(64)
            struct.pack_into("<4f3f4x3f", inst, 0, 0, 0, 0, 1, 0, 0, 0, 1, 1, 1)
            i, cs = w.item("instance", inst), w.item("hknpCompoundShape", bytes(32))
            w.ptr(i, 48, child)
            w.ptr(cs, 16, i)
            return cs

        def xs(b):
            pts = [p for t in sfbodies.blob_bodies(b)[0]["triangles"] for p in t]
            return round(min(p[0] for p in pts), 4), round(max(p[0] for p in pts), 4)
        self.assertEqual(xs(blob(box((-0.4, -0.4, 0), (0.4, 0.4, 1)), True)), (-0.4, 0.4))   # control: the template
        self.assertEqual(xs(blob(box((7.6, -0.4, 0), (8.4, 0.4, 1)), False)), (7.6, 8.4))    # rejected: no identity
        self.assertEqual(xs(blob(compound, True)), (7.6, 8.4))

    def test_negative_or_nonfinite_convex_radius_is_an_error(self):
        # Its sign was never checked: a sphere of radius -0.5 read as one of +0.5, and a cube grown by -1 turned inside
        # out into a larger box.
        v, f = cube((-0.4, -0.4, 0), (0.4, 0.4, 1))
        for radius in (0.05, -0.0):                                                          # control
            self.assertEqual(len(sfbodies.blob_bodies(convex_blob(v, f, radius=radius))), 1)
        bad = [convex_blob([(0, 0, 0.5)], [], radius=-0.5, kind="hknpSphereShape")]
        bad += [convex_blob(v, f, radius=r) for r in (-1.0, float("nan"), float("inf"))]
        for blob in bad:
            with self.assertRaises(sfbodies.BodyError):
                sfbodies.blob_bodies(blob)

    def test_hull_vertex_on_no_face_is_part_of_the_body(self):
        # Only faces were triangulated, but Havok's convex shape is the hull of every vertex: one 20 m out on no face
        # never reached the bounds.
        v, f = cube((-0.4, -0.4, 0), (0.4, 0.4, 1))

        def max_x(blob):
            return max(p[0] for t in sfbodies.blob_bodies(blob)[0]["triangles"] for p in t)
        self.assertAlmostEqual(max_x(convex_blob(v, f)), 0.4, places=6)                     # control
        self.assertAlmostEqual(max_x(convex_blob(v + [(20, 0, 0.5)], f)), 20.0, places=5)
        self.assertAlmostEqual(max_x(convex_blob(v + [(20, 0, 0.5)], f, radius=0.05)), 20.05, places=5)

    def test_box_triangles_cover_the_box(self):
        tris = sfbodies.box_triangles((0, 0, 1), (1, 2, 1))
        self.assertEqual(len(tris), 12)
        pts = {p for t in tris for p in t}
        self.assertEqual(len(pts), 8)
        self.assertEqual(max(p[2] for p in pts), 2)


if __name__ == "__main__":
    unittest.main()
