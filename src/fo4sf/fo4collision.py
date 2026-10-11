"""Decode the collision geometry stored in Fallout 4 NIFs (bhkPhysicsSystem -> Havok 2014 packfile, hknp shapes) into
plain triangles in NIF space (Havok metres x 70 = FO4 units are NOT applied: hknp stores metres... see UNIT below).

FO4 collision is authored for gameplay: stairs are ramps, walls are simplified, clutter and trim are left out. Using it as
the source for Starfield collision is far better than guessing from the render mesh.

Supported shapes: hknpCompressedMeshShape (the usual architecture / prop mesh collision) and hknpConvexPolytopeShape.
Layouts (hk_2014.1.0-r1, 64-bit) were decoded from vanilla files; offsets are relative to each object.
"""
import struct
from typing import List, Tuple

from . import hkpackfile

Vec = Tuple[float, float, float]

# hknpCompressedMeshShapeData
CMD_SECTIONS, CMD_PRIMITIVES, CMD_SHARED_INDEX, CMD_PACKED, CMD_SHARED = 80, 96, 112, 128, 144
CMD_DOMAIN = 32                                      # hkAabb of the whole mesh (min xyzw, max xyzw)
SECTION_SIZE = 96
# section: nodes hkArray(16), domain hkAabb(32), codecParms float[6] @48 (offset xyz, scale xyz),
# firstPackedVertex u32 @72, sharedVertices u32 @76 (start<<8 | count), primitives u32 @80 (start<<8 | count),
# dataRuns u32 @84, numPackedVertices u8 @88, numSharedIndices u8 @89, leafIndex u16 @90, page u8 @92, flags u8 @93

# Hull primitives (FO4 precombines, SCOL\CM*.NIF; docs/ai/research-log.md 2026-10-11). A section whose flags bit 0 is
# set can hold convex hulls next to triangles: primitive (a, b, b, b) with a >= numPackedVertices is a hull, not a
# triangle. a - numPackedVertices is a slot in the section's sharedVerticesIndex range holding a 3 x u16 record:
#   word 0  bits 0-7 = 0x52 (constant), count = (word0 >> 9) + ((word0 >> 8) & 1)   (bit 8 is set for a few hulls:
#           36, 44, 47 vertices; the split is not understood, the sum is right: hull ranges tile the shared array)
#   word 1  first shared vertex; the hull is the convex hull of sharedVertices[first : first + count]
#   word 2  unresolved (half-float-like 0.81..1.33, constant per source shape)
# b is the section tree leaf of the primitive (its data byte is 2 * primitive index). Hull primitives have one shape
# key each (section << 8 | primitive << 1), like a triangle. Verified on 286 hulls in 38 models (0 shared vertices
# unreferenced, 0 in two hulls, 0 shared between a hull and a triangle).
SECTION_HULLS = 1                                    # section flags bit: section holds hull primitives
HULL_TAG = 0x52                                      # low byte of a hull record's first word


def _hull_record(p: hkpackfile.Packfile, sidx_at: int, sh_start: int, slot: int, nsi: int, nshared: int):
    """(first shared vertex, count) of the hull record in a section's shared-index slot; raises on anything else."""
    if slot < 0 or slot + 3 > nsi:
        raise hkpackfile.PackfileError(f"hull record slot {slot} outside the section's {nsi} shared indices")
    w0, first, _unresolved = p.unpack("<3H", sidx_at + 2 * (sh_start + slot))
    if (w0 & 0xFF) != HULL_TAG:
        raise hkpackfile.PackfileError(f"hull record tag 0x{w0 & 0xFF:02x} (expected 0x{HULL_TAG:02x})")
    count = (w0 >> 9) + ((w0 >> 8) & 1)
    if count < 1 or first + count > nshared:
        raise hkpackfile.PackfileError(f"hull vertices {first}..{first + count} outside the {nshared} shared vertices")
    return first, count


def _classify(prim: bytes, npacked: int, nsi: int, flags: int) -> str:
    """"hull", "tri" (triangle or quad) or "none" (unused 0xDEAD slot / degenerate point) for a 4-byte primitive."""
    a, b, c, d = prim
    if (flags & SECTION_HULLS) and b == c == d and npacked <= a < npacked + nsi:
        return "hull"                                # includes (x, x, x, x): the leaf index can equal the slot
    if a == b == c == d or max(a, b, c, d) >= npacked + nsi:
        return "none"
    return "tri"


def _shared_vertices(p: hkpackfile.Packfile, data_obj: int) -> List[Vec]:
    """Shared vertices: 21 / 21 / 22 bits quantised over the whole domain."""
    shar_at, nshared = p.array(data_obj + CMD_SHARED)
    dmin = p.unpack("<3f", data_obj + CMD_DOMAIN)
    dmax = p.unpack("<3f", data_obj + CMD_DOMAIN + 16)
    bits = (0x1FFFFF, 0x1FFFFF, 0x3FFFFF)
    shared = []
    for k in range(nshared):
        v, = p.unpack("<Q", shar_at + 8 * k)
        q = (v & 0x1FFFFF, (v >> 21) & 0x1FFFFF, v >> 42)
        shared.append(tuple(dmin[a] + q[a] * (dmax[a] - dmin[a]) / bits[a] for a in range(3)))
    return shared


def _decode_mesh(p: hkpackfile.Packfile, data_obj: int):
    """(points, triangles, keys, hulls) of a compressed mesh. Triangles are point-index triples in key order with their
    shape keys (section << 8 | primitive << 1 | t, t = 1 for the second triangle of a quad; matches maxKeyValue /
    numPrimitiveKeys in FO4 and vanilla Starfield). hulls: [(section, primitive, slot, first, count, points)] for the
    hull primitives (see SECTION_HULLS), which have no triangle here."""
    sec_at, nsec = p.array(data_obj + CMD_SECTIONS)
    prim_at, _ = p.array(data_obj + CMD_PRIMITIVES)
    sidx_at, _ = p.array(data_obj + CMD_SHARED_INDEX)
    pack_at, _ = p.array(data_obj + CMD_PACKED)
    shared = _shared_vertices(p, data_obj)
    points: List[Vec] = []
    tris, keys, hulls = [], [], []
    for s in range(nsec):
        so = sec_at + SECTION_SIZE * s
        off = p.unpack("<3f", so + 48)
        scale = p.unpack("<3f", so + 60)
        first_packed, shared_d, prim_d = p.unpack("<3I", so + 72)
        npacked, nsi = p.unpack("<BB", so + 88)
        flags, = p.unpack("<B", so + 93)
        sh_start = shared_d >> 8
        local = []
        for k in range(npacked):
            v, = p.unpack("<I", pack_at + 4 * (first_packed + k))
            q = (v & 0x7FF, (v >> 11) & 0x7FF, v >> 22)          # 11 / 11 / 10 bits
            local.append(len(points))
            points.append(tuple(off[a] + q[a] * scale[a] for a in range(3)))
        cache = {}

        def vertex(i):
            if i < npacked:
                return local[i]
            if i not in cache:
                j, = p.unpack("<H", sidx_at + 2 * (sh_start + i - npacked))
                if j >= len(shared):
                    raise hkpackfile.PackfileError(f"shared vertex index {j} out of range ({len(shared)})")
                cache[i] = len(points)
                points.append(shared[j])
            return cache[i]
        pstart, pcount = prim_d >> 8, prim_d & 0xFF
        for k in range(pcount):
            prim = p.raw(prim_at + 4 * (pstart + k), 4)
            kind = _classify(prim, npacked, nsi, flags)
            if kind == "none":
                continue
            if kind == "hull":
                slot = prim[0] - npacked
                first, count = _hull_record(p, sidx_at, sh_start, slot, nsi, len(shared))
                hulls.append((s, k, slot, first, count, shared[first:first + count]))
                continue
            a, b, c, d = prim
            tris.append((vertex(a), vertex(b), vertex(c)))
            keys.append((s << 8) | (k << 1))
            if c != d:                                   # quad
                tris.append((vertex(a), vertex(c), vertex(d)))
                keys.append((s << 8) | (k << 1) | 1)
    return points, tris, keys, hulls


def hull_surface(pts):
    """(points, triangles) of the closed convex hull over a hull primitive's points: a flat set becomes a 1 cm slab; a
    set without volume (fewer than 3 distinct points, e.g. the two 2-point hulls in FO4) gives ([], [])."""
    from . import meshcollision as mc
    pts = mc.thicken_if_flat(list(pts))
    try:
        faces = mc.convex_hull_triangles(pts)
    except hkpackfile.PackfileError:
        return [], []
    return pts, faces


def _compressed_mesh(p: hkpackfile.Packfile, data_obj: int) -> Tuple[List[Vec], List[Tuple[int, int, int]]]:
    """Points and triangles of a compressed mesh. Hull primitives are returned as their triangulated hull surface, so
    consumers of the plain geometry (route planning, compounds) see the whole collision."""
    points, tris, _, hulls = _decode_mesh(p, data_obj)
    for *_, pts in hulls:
        hp, faces = hull_surface(pts)
        base = len(points)
        points += hp
        tris += [(base + a, base + b, base + c) for a, b, c in faces]
    return points, tris


def compressed_mesh_hulls(p: hkpackfile.Packfile, data_obj: int):
    """[(section, primitive, slot, first shared vertex, count, points)] per hull primitive of a compressed mesh (empty for
    ordinary meshes). Raises PackfileError on a malformed hull record."""
    return _decode_mesh(p, data_obj)[3]


# hknpPhysicsSystemData: bodyCinfos hkArray @64, 96 bytes each: shape pointer @0, position hkVector4 @48,
# orientation quaternion (x, y, z, w) @64
SYS_BODIES, BODY_SIZE, BODY_POS, BODY_ROT = 64, 96, 48, 64
CMS_DATA = 96                                        # hknpCompressedMeshShape -> hknpCompressedMeshShapeData pointer
# hknpConvexPolytopeShape: hkRelArray (u16 count, u16 offset from the field) vertices @48 (hkVector4),
# faces @68 (u16 first index, u8 count, u8 angle), indices @72 (u8)
CVX_VERTS, CVX_FACES, CVX_INDICES = 48, 68, 72


def _rel(p, field):
    n, off = p.unpack("<HH", field)
    return field + off, n


def _convex(p: hkpackfile.Packfile, obj: int):
    va, nv = _rel(p, obj + CVX_VERTS)
    fa, nf = _rel(p, obj + CVX_FACES)
    ia, _ = _rel(p, obj + CVX_INDICES)
    pts = [p.unpack("<3f", va + 16 * k) for k in range(nv)]
    tris = []
    for k in range(nf):
        first, cnt = p.unpack("<HB", fa + 4 * k)
        idx = list(p.raw(ia + first, cnt))
        tris += [(idx[0], idx[j], idx[j + 1]) for j in range(1, cnt - 1)]
    return pts, tris


def _rotate(q, v):
    x, y, z, w = q
    r = (1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y),
         2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x),
         2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y))
    return tuple(r[3 * i] * v[0] + r[3 * i + 1] * v[1] + r[3 * i + 2] * v[2] for i in range(3))


def decode_bodies(blob: bytes):
    """[(shape class, points, triangles)] per body of a FO4 bhkPhysicsSystem blob, in the space of the NIF node that owns
    the collision object (metres: FO4's Havok scale is 1/70 game unit, the same as our conversion), plus skipped classes.
    Bodies with a rotation are skipped for now (quaternion convention not verified against a reference)."""
    p = hkpackfile.Packfile(blob)
    classes = dict(p.objects())
    sysobj = next(o for o, c in classes.items() if c == "hknpPhysicsSystemData")
    bodies_at, nbodies = p.array(sysobj + SYS_BODIES)
    bodies, skipped = [], []
    for k in range(nbodies):
        b = bodies_at + BODY_SIZE * k
        shape = p.pointer(b)
        cls = classes.get(shape, "?")
        rot = p.unpack("<4f", b + BODY_ROT)
        if any(abs(x) > 1e-4 for x in rot[:3]):
            skipped.append(cls + " (rotated body)")
            continue
        if cls == "hknpCompressedMeshShape":
            pts, tr = _compressed_mesh(p, p.pointer(shape + CMS_DATA))
        elif cls == "hknpConvexPolytopeShape":
            pts, tr = _convex(p, shape)
        else:
            skipped.append(cls)
            continue
        pos = p.unpack("<3f", b + BODY_POS)
        bodies.append((cls, [tuple(c + t for c, t in zip(v, pos)) for v in pts], tr))
    return bodies, skipped


def decode(blob: bytes) -> Tuple[List[Vec], List[Tuple[int, int, int]], List[str]]:
    """Triangles of every body in a FO4 bhkPhysicsSystem blob merged into one list (see decode_bodies)."""
    p = hkpackfile.Packfile(blob)
    classes = dict(p.objects())
    sysobj = next(o for o, c in classes.items() if c == "hknpPhysicsSystemData")
    bodies_at, nbodies = p.array(sysobj + SYS_BODIES)
    points: List[Vec] = []
    tris = []
    skipped = []
    for k in range(nbodies):
        b = bodies_at + BODY_SIZE * k
        shape = p.pointer(b)
        cls = classes.get(shape, "?")
        if cls == "hknpCompressedMeshShape":
            pts, tr = _compressed_mesh(p, p.pointer(shape + CMS_DATA))
        elif cls == "hknpConvexPolytopeShape":
            pts, tr = _convex(p, shape)
        else:
            skipped.append(cls)
            continue
        pos = p.unpack("<3f", b + BODY_POS)
        rot = p.unpack("<4f", b + BODY_ROT)
        base = len(points)
        points += [tuple(r + t for r, t in zip(_rotate(rot, v), pos)) for v in pts]
        tris += [(a + base, b_ + base, c + base) for a, b_, c in tr]
    return points, tris, skipped


def compressed_mesh_keys(p: hkpackfile.Packfile, data_obj: int):
    """[(shape key, (min xyz, max xyz))] per triangle of a compressed mesh (hull primitives have no triangle key: they
    are converted as convex bodies). Key = section << 8 | primitive << 1 | t, t = 1 for the second triangle of a quad."""
    points, tris, keys, _ = _decode_mesh(p, data_obj)
    out = []
    for key, tri in zip(keys, tris):
        P = [points[i] for i in tri]
        lo = tuple(min(q[x] for q in P) for x in range(3))
        hi = tuple(max(q[x] for q in P) for x in range(3))
        out.append((key, (lo, hi)))
    return out
