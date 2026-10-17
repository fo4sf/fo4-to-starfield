"""Decoder simulation for Starfield compressed-mesh collision (hknpCompressedMeshShape in a bhkPhysicsSystem tagfile).

Walks every compressed mesh of a converted NIF the way Starfield's hknp decoder does and reports every violation of the
invariants that hold for all 837 compressed meshes of a 1,500-NIF random sample of "Starfield - Meshes01.ba2"
(2026-10-16, scripts/oracles/collision_mesh_keys.py over the vanilla archive: 0 violations). Evidence for the decoder's
rules: the crash dump of 2026-10-16 (hknpCompressedMeshShapeInternals.cpp:939 "Unknown primitive type in compressed
mesh"; the closest-points query of vault_cart_01's mesh searched the data runs for primitive 40 of 40 and dereferenced
NULL) and Starfield.exe's primitive dispatch (indices[1] == indices[3] -> special primitive whose type is indices[2],
3 or 4, anything else asserts).

Rules (violation kinds):
  has_simd       hasSimdTree is set (every vanilla mesh carries a SIMD tree; queries traverse it)
  flat_convex    hkcdStaticMeshTree::Base.primitiveStoresIsFlatConvex (tree + 60) is 0xFF (vanilla: 837 of 837)
  section_flags  Section.flags has bit 0 clear (vanilla: always 0; FO4 sets it on sections with special primitives)
  prim_type      a primitive with indices[1] == indices[3] is a special primitive of type indices[2] in {3, 4}: FO4's
                 unused-slot padding DE AD DE AD, all-equal points and FO4's own specials (a, b, b, b) all assert
  prim_index     every index of a triangle / quad is < the section's vertex slots (packed + its shared indices)
  tree           the section's Aabb4BytesCodec tree: every node reached once, every leaf < numPrimitives, every
                 primitive has exactly one leaf (leaf when hiData bit 0 is clear, primitive = hiData >> 1;
                 inner: left child = node + 1, right child = node + (hiData & 0xFE))
  runs           the section's primitive data runs cover primitive 0 .. numPrimitives - 1 exactly
  key_section    a SIMD-tree leaf key (section << 8 | primitive << 1 | triangle) names an existing section
  key_prim       ... and an existing primitive of that section
  key_odd        no SIMD leaf key has bit 0 set: the decoder takes key K as the primitive's first triangle and K + 1
                 as the second triangle of a quad, so an odd K crosses into the next primitive slot, and past the end
                 of the section for its last primitive (vault_cart_01: keys 0..79 for 40 primitives, 79 + 1 -> 40)
  key_dup        no primitive has two SIMD leaf keys
  key_missing    every primitive has a SIMD leaf key (vanilla: one leaf per primitive, triangle bit 0)
  simd           the SIMD tree is well formed: node 0 is the sentinel, node 1 the root, children in range, each
                 node reached once
"""
import os
import struct
import sys
from typing import Dict, List, NamedTuple, Optional

from . import hktagfile

FLAT_CONVEX = 0xFF                                     # vanilla value of primitiveStoresIsFlatConvex
SPECIAL_TYPES = (3, 4)                                 # the special primitive types Starfield's decoder accepts
SECTION_SHIFT = 8                                      # key = section << 8 | primitive << 1 | triangle
SIMD_NODE = 128


class Violation(NamedTuple):
    kind: str
    section: int                                       # -1: whole mesh
    index: int                                         # primitive / key / node, -1 when not applicable
    detail: str


def section_slots(sections: List[dict], n_shared_index: int) -> List[int]:
    """Vertex slots per section: packed vertices + the shared indices between its firstSharedVertexIndex and the next
    section's (the array end for the last one). The Starfield section stores no shared count."""
    out = []
    for s in sections:
        later = [t["first_shared"] for t in sections if t["first_shared"] > s["first_shared"]]
        out.append(s["npacked"] + (min(later) if later else n_shared_index) - s["first_shared"])
    return out


def walk_section_tree(nodes: bytes):
    """(leaf primitive indices in traversal order, nodes reached, problems) of an Aabb4BytesCodec tree."""
    n = len(nodes) // 4
    leaves, seen, problems = [], set(), []

    def visit(i, depth):
        if depth > 64 or i >= n or i in seen:
            problems.append(f"node {i} {'revisited' if i in seen else 'out of range'}")
            return
        seen.add(i)
        hi = nodes[4 * i + 3]
        if hi & 1 == 0:
            leaves.append(hi >> 1)
            return
        visit(i + 1, depth + 1)
        visit(i + (hi & 0xFE), depth + 1)
    if n:
        visit(0, 0)
    return leaves, seen, problems


def walk_simd_tree(raw: bytes):
    """(leaf keys, problems) of an hkcdSimdTree (128-byte nodes: 24 floats, data u32[4], isLeaf): node 1 is the root;
    a lane is active when its box is not inverted; leaf lanes with data 0xffffffff are unused."""
    n = len(raw) // SIMD_NODE
    keys, seen, problems = [], set(), []
    if n < 2:
        return keys, [f"{n} nodes (sentinel + root expected)"]

    def visit(i, depth):
        if depth > 64 or i >= n or i in seen:
            problems.append(f"node {i} {'revisited' if i in seen else 'out of range'}")
            return
        seen.add(i)
        at = SIMD_NODE * i
        lx = struct.unpack_from("<4f", raw, at)
        hx = struct.unpack_from("<4f", raw, at + 16)
        data = struct.unpack_from("<4I", raw, at + 96)
        leaf = raw[at + 112]
        for lane in range(4):
            if lx[lane] > hx[lane]:
                continue
            if leaf:
                if data[lane] != 0xFFFFFFFF:
                    keys.append(data[lane])
            else:
                visit(data[lane], depth + 1)
    visit(1, 0)
    return keys, problems


def mesh_records(blob: bytes) -> List[dict]:
    """One plain record per hknpCompressedMeshShapeData of a Starfield physics blob (what check() reads)."""
    tf = hktagfile.Tagfile(blob)
    b, D = tf.blob, tf.data_start
    names = {t.index: tf.type_name(t.index) for t in tf.types[1:]}
    ptr: Dict[int, int] = {}
    for _, offs in tf.patches:
        for o in offs:
            ptr[D + o] = struct.unpack_from("<Q", b, D + o)[0]

    def field(T, name):
        return next(f for f in tf.all_fields(T) if f.name == name)

    def item(abs_off):
        k = ptr.get(abs_off)
        return tf.items[k] if k else None

    def array(abs_off, elem):
        it = item(abs_off)
        return (b[D + it.offset:D + it.offset + elem * it.count], it.count) if it else (b"", 0)
    out = []
    for it in tf.items[1:]:
        if names.get(it.type) != "hknpCompressedMeshShapeData":
            continue
        T = it.type
        a = D + it.offset
        tree_f = field(T, "meshTree")
        TT = tree_f.type
        ta = a + tree_f.offset
        rec = {"numPrimitiveKeys": struct.unpack_from("<i", b, ta + 48)[0],
               "bitsPerKey": struct.unpack_from("<i", b, ta + 52)[0],
               "maxKeyValue": struct.unpack_from("<I", b, ta + 56)[0], "flat": b[ta + 60]}
        prim_raw, nprim = array(ta + field(TT, "primitives").offset, 4)
        rec["primitives"] = [tuple(prim_raw[4 * i:4 * i + 4]) for i in range(nprim)]
        run_raw, nrun = array(ta + field(TT, "primitiveDataRuns").offset, 4)
        rec["runs"] = [struct.unpack_from("<HBB", run_raw, 4 * i) for i in range(nrun)]
        rec["n_shared_index"] = array(ta + field(TT, "sharedVerticesIndex").offset, 2)[1]
        si = item(ta + field(TT, "sections").offset)
        secs = []
        for k in range(si.count if si else 0):
            so = D + si.offset + 96 * k
            fp, fs, fpr, fr = struct.unpack_from("<4I", b, so + 72)
            s = {"first_packed": fp, "first_shared": fs, "first_prim": fpr, "first_run": fr, "npacked": b[so + 88],
                 "nprim": b[so + 89], "nrun": b[so + 90], "page": b[so + 91],
                 "leafIndex": struct.unpack_from("<H", b, so + 92)[0], "layerData": b[so + 94], "flags": b[so + 95]}
            s["nodes"] = array(so + field(si.type, "nodes").offset, 4)[0]
            secs.append(s)
        rec["sections"] = secs
        simd = field(T, "simdTree")
        rec["has_simd"] = b[a + field(T, "hasSimdTree").offset]
        rec["simd_nodes"] = array(a + simd.offset + field(simd.type, "nodes").offset, SIMD_NODE)[0]
        out.append(rec)
    return out


def check(rec: dict) -> List[Violation]:
    """Every violation of the vanilla invariants in one mesh record (see the module docstring)."""
    v: List[Violation] = []
    secs, prims, runs = rec["sections"], rec["primitives"], rec["runs"]
    if not rec.get("has_simd", 1):
        v.append(Violation("has_simd", -1, -1, "hasSimdTree is 0"))
    if rec["flat"] != FLAT_CONVEX:
        v.append(Violation("flat_convex", -1, -1, f"primitiveStoresIsFlatConvex {rec['flat']:#x} (vanilla 0xff)"))
    slots = section_slots(secs, rec["n_shared_index"])
    quads: Dict[int, List[bool]] = {}
    for k, s in enumerate(secs):
        if s["flags"] & 1:
            v.append(Violation("section_flags", k, -1, f"flags {s['flags']:#x}"))
        isq = []
        for j in range(s["nprim"]):
            g = s["first_prim"] + j
            if g >= len(prims):
                v.append(Violation("prim_index", k, j, f"primitive {g} past the array ({len(prims)})"))
                isq.append(False)
                continue
            a, b_, c, d = prims[g]
            if b_ == d:
                if c not in SPECIAL_TYPES:
                    v.append(Violation("prim_type", k, j, f"indices {prims[g]}: special primitive of type {c}"))
                isq.append(False)
                continue
            if max(a, b_, c, d) >= slots[k]:
                v.append(Violation("prim_index", k, j, f"indices {prims[g]} but {slots[k]} vertex slots"))
            isq.append(c != d)
        quads[k] = isq
        leaves, seen, problems = walk_section_tree(s["nodes"])
        for pr in problems:
            v.append(Violation("tree", k, -1, pr))
        if len(seen) != len(s["nodes"]) // 4:
            v.append(Violation("tree", k, -1, f"{len(seen)} of {len(s['nodes']) // 4} nodes reached"))
        for leaf in leaves:
            if leaf >= s["nprim"]:
                v.append(Violation("tree", k, leaf, f"leaf names primitive {leaf} of {s['nprim']}"))
        if sorted(x for x in leaves if x < s["nprim"]) != list(range(s["nprim"])):
            v.append(Violation("tree", k, -1, "leaves do not name every primitive once"))
        covered = []
        for r in range(s["first_run"], s["first_run"] + s["nrun"]):
            if r >= len(runs):
                v.append(Violation("runs", k, r, f"data run {r} past the array ({len(runs)})"))
                continue
            _, idx, cnt = runs[r]
            covered += range(idx, idx + cnt)
        if covered != list(range(s["nprim"])):
            v.append(Violation("runs", k, -1, f"data runs cover {covered[:8]}{'...' if len(covered) > 8 else ''} "
                                            f"for {s['nprim']} primitives"))
    keys, problems = walk_simd_tree(rec["simd_nodes"])
    for pr in problems:
        v.append(Violation("simd", -1, -1, pr))
    seen_prim = set()
    for key in keys:
        k, j, t = key >> SECTION_SHIFT, (key & 0xFF) >> 1, key & 1
        if k >= len(secs):
            v.append(Violation("key_section", k, key, f"key {key} names section {k} of {len(secs)}"))
            continue
        if j >= secs[k]["nprim"]:
            v.append(Violation("key_prim", k, key, f"key {key} names primitive {j} of {secs[k]['nprim']}"))
            continue
        if t:
            nxt = j + 1
            where = (f"past the end of {secs[k]['nprim']} primitives" if nxt >= secs[k]["nprim"]
                     else f"primitive {nxt}")
            v.append(Violation("key_odd", k, key, f"key {key} (primitive {j}, triangle 1): the decoder's second "
                                                  f"triangle {key + 1} is {where}"))
        if (k, j) in seen_prim:
            v.append(Violation("key_dup", k, key, f"primitive {j} has another key"))
        seen_prim.add((k, j))
    for k, s in enumerate(secs):
        for j in range(s["nprim"]):
            if (k, j) not in seen_prim:
                v.append(Violation("key_missing", k, j, "primitive has no SIMD leaf key"))
    return v


def physics_blobs(nif_bytes: bytes):
    """[(block index, bhkPhysicsSystem payload)] of a Starfield NIF."""
    from . import nif as nifmod
    f = nifmod.parse(nif_bytes)
    out = []
    for i in range(len(f.blocks)):
        if f.type_of(i) == "bhkPhysicsSystem":
            n, = struct.unpack_from("<I", f.blocks[i], 0)
            out.append((i, f.blocks[i][4:4 + n]))
    return out


def check_nif(nif_bytes: bytes):
    """[(block, mesh index, [Violation])] for every compressed mesh of a NIF, and the number of meshes seen."""
    out, meshes = [], 0
    for bi, blob in physics_blobs(nif_bytes):
        for m, rec in enumerate(mesh_records(blob)):
            meshes += 1
            vs = check(rec)
            if vs:
                out.append((bi, m, vs))
    return out, meshes


def iter_nifs(path: str, pattern: Optional[str] = None):
    """(name, bytes) of every NIF in a loose file, a folder (recursive) or a BA2 archive."""
    from . import ba2
    low = path.lower()
    if low.endswith(".ba2"):
        arc = ba2.Ba2(path)
        for name in arc.names:
            if name.lower().endswith(".nif") and (not pattern or pattern.lower() in name.lower()):
                yield name, arc.read(name)
    elif os.path.isdir(path):
        for root, _dirs, files in os.walk(path):
            for fn in sorted(files):
                rel = os.path.relpath(os.path.join(root, fn), path)
                if fn.lower().endswith(".nif") and (not pattern or pattern.lower() in rel.lower()):
                    with open(os.path.join(root, fn), "rb") as f:
                        yield rel, f.read()
    else:
        with open(path, "rb") as f:
            yield os.path.basename(path), f.read()


def main(argv=None) -> int:
    import argparse
    import collections
    import json
    ap = argparse.ArgumentParser(description="Starfield compressed-mesh decoder simulation (see fo4sf.meshcheck)")
    ap.add_argument("paths", nargs="+", help="NIF files, folders of NIFs or BA2 archives")
    ap.add_argument("--filter", default="", help="only NIFs whose path contains this text")
    ap.add_argument("--json", default="", help="write per-model violations here")
    ap.add_argument("--quiet", action="store_true", help="only the summary")
    ap.add_argument("--limit", type=int, default=0, help="stop after this many NIFs")
    a = ap.parse_args(argv)
    kinds, per_model, n_nif, n_mesh, errors = collections.Counter(), {}, 0, 0, 0
    for path in a.paths:
        for name, data in iter_nifs(path, a.filter or None):
            if a.limit and n_nif >= a.limit:
                break
            n_nif += 1
            try:
                found, meshes = check_nif(data)
            except Exception as e:                         # noqa: BLE001  (a reader failure is reported, not fatal)
                errors += 1
                print(f"ERROR {name}: {type(e).__name__}: {e}")
                continue
            n_mesh += meshes
            if found:
                per_model[name] = [{"block": bi, "mesh": m, "violations": [v._asdict() for v in vs]}
                                   for bi, m, vs in found]
                for _, _, vs in found:
                    for v in vs:
                        kinds[v.kind] += 1
                if not a.quiet:
                    for bi, m, vs in found:
                        by = collections.Counter(v.kind for v in vs)
                        first = "; ".join(f"{v.kind} s{v.section} i{v.index}: {v.detail}" for v in vs[:3])
                        print(f"{name} block {bi}: {dict(by)}  e.g. {first}")
    total = sum(kinds.values())
    print(f"{n_nif} NIFs, {n_mesh} compressed meshes, {len(per_model)} models with violations, {total} violations"
          f"{f', {errors} read errors' if errors else ''}: {dict(sorted(kinds.items()))}")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"nifs": n_nif, "meshes": n_mesh, "kinds": dict(kinds), "models": per_model}, f, indent=1)
    return 1 if total or errors else 0


if __name__ == "__main__":
    sys.exit(main())
