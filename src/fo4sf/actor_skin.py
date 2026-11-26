"""Put a Fallout 4 skinned actor mesh on its OWN skeleton in Starfield form (multi-weight skin, full bone tree).

    skel = actor_skin.read_hka_skeleton(hkx_bytes).scaled(1 / 70)        # FO4 skeleton.hkx, metres
    res = actor_skin.build_actor_mesh_nif(skel, parts, template_nif=sf_mesh_nif)
    res.nif, res.meshes                     # NIF bytes; {(dir, name): .mesh bytes} for Data/geometries/<dir>/<name>.mesh
    skeleton_nif = actor_skin.build_skeleton_nif(skel, sf_skeleton_nif, b"HandyFO4_mrRigRoot", bound)
    actor_skin.verify_actor_mesh_nif(res.nif, res.meshes, skel)          # offline proof, see below

How a vanilla Starfield actor mesh carries its skeleton (measured 2026-11-23 on MiniBotA minibota_mesh.nif and
minibota_base.nif, ModelA modela_civilian_01.nif, their skeleton.nif and skeleton_ref.nif; BS 173):
  * mesh NIF: root NiNode (BSXFlags 0x1004A) -> "COM_Twin" NiNode (identity, NiStringExtraData ParentBoneName = "COM")
    -> every rig bone below COM, with its local bind transform (metres) and NiStringExtraData sgoKeep = "sgoKeepBone";
    the BSGeometry shapes are children of the root, not of a bone. Bone nodes carry flags 0x0400000E.
  * per shape: BSGeometry (identity transform, Meshes[0] -> geometries .mesh), NiIntegerExtraData "MaterialID",
    SkinAttach named "SkinBMP" with one EMPTY name per bone, BSSkin::Instance (root = block 0, bone refs = the bone
    NiNodes in the same file), BSSkin::BoneData, BSLightingShaderProperty.
  * BSSkin::BoneData slot k = inverse(world bind of bone k in actor Root space): the .mesh positions are in Root (ground)
    space. Checked: MiniBot C_Chassis world z 0.5057 (COM) -> t = (0, 0, -0.5057); C_Hatch (0, 0.1641, 0.7407) ->
    t = (0, -0.1641, -0.7407); ModelA R_Hip (0.1253, -0.039, 1.0873) -> t = (-0.1253, 0.039, -1.0873). (minibota_base.nif
    stores its .mesh Y-up and folds that 90-degree turn into BoneData; the rule is skin space -> bone space.)
    The bounding sphere of slot k is in that bone's space.
  * .mesh skin weights: weights_per_vertex = the largest influence count the shape needs (vanilla 1 or 2), per vertex
    sorted heaviest first, zero-padded with (0, 0), every vertex summing to exactly 65535. No vertex colours.
  * skeleton.nif holds only the rig root (BSBound "BBX" + BSXFlags 0x4A), Root, COM (+ a bhkPhysicsSystem), the
    CharacterController (its bhkPhysicsSystem is the movement body) and a few helper nodes, even for ModelA whose
    skeleton_ref.nif / rig have ~95 bones; skeleton_ref.nif adds the full bone tree. So the full bone list lives in the
    .rig and in each mesh NIF, not in skeleton.nif.

Havok side: read_hka_skeleton decodes hkaSkeleton (hk_2014.1.0-r1, 64-bit): +16 name, +24 parentIndices (int16),
+40 bones (16 bytes: name ptr, lockTranslation), +56 referencePose (hkQsTransform: translation vec4, rotation quat
xyzw, scale vec4). Standalone .hkx files put a 16-byte predicate array before the section headers (header int16 at
0x3E); if the shared hkpackfile reader in this checkout does not handle that yet, _PaddedPackfile does.

Proven offline only (verify_actor_mesh_nif): block graph, bone counts, weights per vertex and their sums, node tree ==
BoneData inverse, bind-pose positions. NOT proven until run in game: deformation with a matching .rig, LOD, and the
copied character-controller body size. Bone names: no vanilla actor rig uses '|' or '-', so starfield_bone_names
gives the Fallout 4 names a letters / digits / '_' form; rest_rotation_corrections + rebase_skeleton give chosen bones
(the Handy COM) an identity rest rotation without moving anything (see "rig edits"). Vanilla actor meshes use up to 8
weights per vertex (sample of 400 actor NIFs: 1 to 8) and up to 112 skin bones per shape.
"""
import math
import re
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from . import convert_static, fo4skin, hkpackfile, nif as nifmod, sfmesh, sfnif

Transform = Tuple[tuple, tuple, float]
IDENT_R = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
FULL_WEIGHT = 65535
MAX_WEIGHTS = 4
BONE_FLAGS = 0x0400000E          # vanilla bone NiNodes (ModelA, MiniBot)
ROOT_FLAGS = 0x2000000E          # vanilla mesh root / COM_Twin (MiniBot)
MESH_BSX = 0x1004A               # vanilla actor mesh NIFs
SKELETON_BSX = 0x4A              # vanilla skeleton.nif / skeleton_ref.nif


# ---- Havok skeleton ----------------------------------------------------------------------------------------------

class _PaddedPackfile(hkpackfile.Packfile):
    """hkpackfile.Packfile with the section headers read after the predicate array (0x40 + int16 at 0x3E). Local
    workaround for standalone .hkx files while the shared reader assumed 0x40."""

    def __init__(self, data: bytes):            # noqa: D401 - same fields as the parent
        if data[:8] != hkpackfile.MAGIC:
            raise hkpackfile.PackfileError("not a Havok packfile")
        if data[16] != 8:
            raise hkpackfile.PackfileError("only 64-bit packfiles are supported")
        self.data = data
        self.version = data[40:56].split(b"\0")[0].decode("latin-1")
        pad, = struct.unpack_from("<h", data, 0x3E)
        hdr = 0x40 + max(0, pad)
        nsec, = struct.unpack_from("<i", data, 20)
        self.sections = []
        spans = []
        for i in range(nsec):
            h = hdr + 64 * i
            tag = data[h:h + 20].split(b"\0")[0].decode("latin-1")
            start, loc, glo, vir, exp, _imp, end = struct.unpack_from("<7i", data, h + 20)
            s = hkpackfile.Section(tag, start, end)
            for p in range(start + loc, start + glo - 7, 8):
                a, b = struct.unpack_from("<ii", data, p)
                if a != -1:
                    s.local[a] = b
            for p in range(start + glo, start + vir - 11, 12):
                a, sec, b = struct.unpack_from("<iii", data, p)
                if a != -1:
                    s.glob[a] = (sec, b)
            spans.append((start + vir, start + exp))
            self.sections.append(s)
        for s, (v0, v1) in zip(self.sections, spans):
            for p in range(v0, v1 - 11, 12):
                a, sec, b = struct.unpack_from("<iii", data, p)
                if a != -1:
                    at = self.sections[sec].start + b
                    s.virtual.append((a, data[at:data.index(b"\0", at)].decode("latin-1")))
        try:
            self.data_section = next(s for s in self.sections if s.tag == "__data__")
        except StopIteration:
            raise hkpackfile.PackfileError("no __data__ section") from None


def load_packfile(data: bytes) -> hkpackfile.Packfile:
    """The shared reader when it finds the data section and classes, else the padded-header workaround."""
    try:
        pf = hkpackfile.Packfile(data)
        if pf.objects():
            return pf
    except (hkpackfile.PackfileError, StopIteration, struct.error, ValueError, IndexError):
        pass
    return _PaddedPackfile(data)


def quat_to_matrix(q) -> tuple:
    """Row-major 3x3 of unit quaternion (x, y, z, w), for v' = R v (Havok and nif.py agree on this convention)."""
    x, y, z, w = q
    n = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    x, y, z, w = x / n, y / n, z / n, w / n
    return (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w),
            2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w),
            2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y))


def matrix_to_quat(r) -> tuple:
    """(x, y, z, w) of an orthonormal row-major 3x3 (w >= 0)."""
    m00, m01, m02, m10, m11, m12, m20, m21, m22 = r
    tr = m00 + m11 + m22
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        q = ((m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s, 0.25 * s)
    elif m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2
        q = (0.25 * s, (m01 + m10) / s, (m02 + m20) / s, (m21 - m12) / s)
    elif m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2
        q = ((m01 + m10) / s, 0.25 * s, (m12 + m21) / s, (m02 - m20) / s)
    else:
        s = math.sqrt(1.0 + m22 - m00 - m11) * 2
        q = ((m02 + m20) / s, (m12 + m21) / s, 0.25 * s, (m10 - m01) / s)
    return tuple(-c for c in q) if q[3] < 0 else q


@dataclass
class Skeleton:
    names: List[str]
    parents: List[int]
    local: List[Transform]                    # parent-relative bind (t, R row-major, s)
    lock_translation: List[bool] = field(default_factory=list)
    name: str = ""

    def index(self, name: str) -> int:
        low = name.lower()
        for i, n in enumerate(self.names):
            if n.lower() == low:
                return i
        raise KeyError(name)

    def world(self) -> List[Transform]:
        out: List[Optional[Transform]] = [None] * len(self.names)
        for i in range(len(self.names)):          # hkaSkeleton lists parents before children; checked in read
            p = self.parents[i]
            out[i] = self.local[i] if p < 0 else nifmod._compose(out[p], self.local[i])
        return out

    def children(self, i: int) -> List[int]:
        return [k for k, p in enumerate(self.parents) if p == i]

    def descendants(self, i: int) -> List[int]:
        """Bones below i, depth first (pre-order), not including i."""
        out = []
        for c in self.children(i):
            out.append(c)
            out.extend(self.descendants(c))
        return out

    def scaled(self, k: float) -> "Skeleton":
        return Skeleton(list(self.names), list(self.parents),
                        [(tuple(c * k for c in t), r, s) for t, r, s in self.local],
                        list(self.lock_translation), self.name)

    def to_json(self) -> dict:
        world = self.world()
        return {"name": self.name, "bones": [
            {"index": i, "name": n, "parent": self.parents[i],
             "parent_name": self.names[self.parents[i]] if self.parents[i] >= 0 else None,
             "translation": [round(c, 7) for c in self.local[i][0]],
             "rotation_xyzw": [round(c, 7) for c in matrix_to_quat(self.local[i][1])],
             "scale": self.local[i][2],
             "world_translation": [round(c, 7) for c in world[i][0]],
             "world_rotation_xyzw": [round(c, 7) for c in matrix_to_quat(world[i][1])]}
            for i, n in enumerate(self.names)]}


def read_hka_skeleton(hkx: bytes, which: int = 0) -> Skeleton:
    """The `which`-th hkaSkeleton of a 64-bit hk_2014 packfile (FO4 skeleton.hkx), in the file's units."""
    pf = load_packfile(hkx)
    objs = pf.objects("hkaSkeleton")
    if not objs:
        raise hkpackfile.PackfileError("no hkaSkeleton in packfile")
    sk = objs[which][0]

    def cstr(ptr_at: int) -> str:
        tgt = pf.pointer(ptr_at)
        if tgt is None:
            return ""
        s = pf.data_section.start + tgt
        return pf.data[s:pf.data.index(b"\0", s)].decode("latin-1")

    par_off, npar = pf.array(sk + 24)
    bone_off, nb = pf.array(sk + 40)
    pose_off, npose = pf.array(sk + 56)
    if not (npar == nb == npose) or nb <= 0 or None in (par_off, bone_off, pose_off):
        raise hkpackfile.PackfileError(f"hkaSkeleton arrays disagree: parents {npar}, bones {nb}, pose {npose}")
    parents = list(pf.unpack(f"<{nb}h", par_off))
    names, locks, local = [], [], []
    for i in range(nb):
        if not -1 <= parents[i] < i:
            raise hkpackfile.PackfileError(f"bone {i}: parent {parents[i]} does not precede it")
        names.append(cstr(bone_off + 16 * i))
        locks.append(bool(pf.raw(bone_off + 16 * i + 8, 1)[0]))
        t = pf.unpack("<3f", pose_off + 48 * i)
        q = pf.unpack("<4f", pose_off + 48 * i + 16)
        sc = pf.unpack("<3f", pose_off + 48 * i + 32)
        if max(abs(c - 1.0) for c in sc) > 1e-4:
            raise hkpackfile.PackfileError(f"bone {names[-1]}: non-unit reference scale {sc}")
        local.append((t, quat_to_matrix(q), 1.0))
    return Skeleton(names, parents, local, locks, cstr(sk + 16))


# ---- name mapping evidence ---------------------------------------------------------------------------------------

def rotation_angle_deg(a, b) -> float:
    tr = sum(a[3 * i + k] * b[3 * i + k] for i in range(3) for k in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (tr - 1.0) / 2.0))))


def pose_evidence(mapping: Dict[str, Optional[str]], mesh_world: Dict[str, Transform], skel: Skeleton) -> dict:
    """Per mesh bone: the mapped skeleton bone and how far the mesh NIF's node stands from that bone's reference pose
    (distance in the skeleton's units, angle in degrees), plus the nearest skeleton bone by position for comparison."""
    world = skel.world()
    out = {}
    for mb, sb in sorted(mapping.items()):
        mw = mesh_world.get(mb)
        if mw is None:
            continue
        near = min(range(len(skel.names)), key=lambda i: math.dist(world[i][0], mw[0]))
        row = {"skeleton_bone": sb, "nearest_by_position": skel.names[near],
               "nearest_distance": round(math.dist(world[near][0], mw[0]), 4)}
        if sb is not None:
            w = world[skel.index(sb)]
            row["distance"] = round(math.dist(w[0], mw[0]), 4)
            row["angle_deg"] = round(rotation_angle_deg(w[1], mw[1]), 2)
            row["offset"] = [round(a - b, 4) for a, b in zip(mw[0], w[0])]
        out[mb] = row
    return out


# ---- weights -----------------------------------------------------------------------------------------------------

def quantize_weights(influences: Sequence[Tuple[int, float]], max_n: int = MAX_WEIGHTS,
                     fallback: int = 0) -> List[Tuple[int, int]]:
    """(slot, u16) pairs: duplicate slots merged, non-positive dropped, heaviest first (ties by slot), at most max_n,
    summing to exactly 65535 with no zero entries. A vertex with no positive weight gets [(fallback, 65535)]."""
    merged: Dict[int, float] = {}
    for slot, w in influences:
        if w > 0.0 and math.isfinite(w):
            merged[slot] = merged.get(slot, 0.0) + float(w)
    ranked = sorted(merged.items(), key=lambda kv: (-kv[1], kv[0]))[:max_n]
    if not ranked:
        return [(fallback, FULL_WEIGHT)]
    while True:
        total = sum(w for _, w in ranked)
        q = [[s, int(round(w / total * FULL_WEIGHT))] for s, w in ranked]
        if all(v > 0 for _, v in q[1:]) or len(ranked) == 1:
            break
        ranked = ranked[:-1]                  # a weight below 1/65535 after renormalising: drop it and retry
    q[0][1] += FULL_WEIGHT - sum(v for _, v in q)
    q.sort(key=lambda sv: (-sv[1], sv[0]))
    return [(s, v) for s, v in q]


# ---- NIF building ------------------------------------------------------------------------------------------------

def _node_bytes(name_idx: int, extras: Sequence[int], xf: Transform, children: Sequence[int],
                flags: int = BONE_FLAGS, collision: int = -1) -> bytes:
    t, r, s = xf
    return (struct.pack("<iI", name_idx, len(extras)) + struct.pack(f"<{len(extras)}i", *extras)
            + struct.pack("<iI", -1, flags) + struct.pack("<3f", *t) + struct.pack("<9f", *r) + struct.pack("<f", s)
            + struct.pack("<iI", collision, len(children)) + struct.pack(f"<{len(children)}i", *children))


def _string_extra(f: nifmod.NifFile, name: bytes, value: bytes) -> int:
    return f.add_block("NiStringExtraData", struct.pack("<ii", f.string_index(name), f.string_index(value)))


def _new_nif(template: Optional[bytes]) -> nifmod.NifFile:
    """An empty BS 173 NIF whose header fields copy the template's (vanilla Starfield actor file), else sfnif's."""
    if template:
        t = nifmod.parse(template)
        return nifmod.NifFile(endian=t.endian, user_version=t.user_version, bs_version=t.bs_version, author=t.author,
                              unknown_int=t.unknown_int, export_script=t.export_script, sf_data=t.sf_data)
    return nifmod.NifFile(endian=1, user_version=12, bs_version=173, author=b"\x00", unknown_int=0,
                          export_script=b"\x00", sf_data=b"\x7a\x00")


@dataclass
class SkinPart:
    """One shape to write: a posed FO4 shape (identity transform, FO4 units, Root space) and per vertex its
    influences as (skeleton bone name, weight)."""
    name: str
    shape: nifmod.Fo4Shape
    influences: List[List[Tuple[str, float]]]
    material: str


@dataclass
class ActorMeshResult:
    nif: bytes
    meshes: Dict[Tuple[str, str], bytes]
    report: dict = field(default_factory=dict)


def build_actor_mesh_nif(skel: Skeleton, parts: Sequence[SkinPart], unit_scale: float = convert_static.UNIT_SCALE,
                         template_nif: Optional[bytes] = None, root_name: bytes = b"ExportScene",
                         com: str = "COM", max_weights: int = MAX_WEIGHTS, exclude: Sequence[str] = ()) -> ActorMeshResult:
    """Starfield actor mesh NIF laid out like vanilla minibota_mesh.nif / modela_*.nif. `skel` is in metres; shape
    positions are multiplied by unit_scale. Every bone below `com` becomes a NiNode under COM_Twin, except the
    unweighted leaf bones named in `exclude` (vanilla minibota_mesh.nif has no DirectAt node although the rig and
    skeleton_ref.nif have one); each part becomes one BSGeometry skinned to the skeleton bones its vertices use (sorted
    by skeleton index), with up to max_weights influences per vertex."""
    world = skel.world()
    com_i = skel.index(com)
    skip = {skel.index(n) for n in exclude}
    for b in skip:
        if skel.children(b):
            raise ValueError(f"excluded bone {skel.names[b]} has children")
    below = [b for b in skel.descendants(com_i) if b not in skip]
    f = _new_nif(template_nif)
    root = f.add_block("NiNode", b"")
    bsx = f.add_block("BSXFlags", struct.pack("<iI", f.string_index(b"BSX"), MESH_BSX))
    twin = f.add_block("NiNode", b"")
    pbn = _string_extra(f, b"ParentBoneName", skel.names[com_i].encode("latin-1"))
    block_of: Dict[int, int] = {}
    for b in below:
        block_of[b] = f.add_block("NiNode", b"")
        _string_extra(f, b"sgoKeep", b"sgoKeepBone")
    for b in below:
        kids = [block_of[c] for c in skel.children(b) if c in block_of]
        f.blocks[block_of[b]] = _node_bytes(f.string_index(skel.names[b].encode("latin-1")), [block_of[b] + 1],
                                            skel.local[b], kids)
    f.blocks[twin] = _node_bytes(f.string_index(b"COM_Twin"), [pbn], ((0.0, 0.0, 0.0), IDENT_R, 1.0),
                                 [block_of[c] for c in skel.children(com_i) if c in block_of], flags=ROOT_FLAGS)
    s_matid, s_skin = f.string_index(b"MaterialID"), f.string_index(b"SkinBMP")
    meshes: Dict[Tuple[str, str], bytes] = {}
    root_kids = [twin]
    report = {"bones_in_nif": len(below) + 1, "com": skel.names[com_i], "parts": {}}
    for part in parts:
        if len(part.influences) != len(part.shape.positions):
            raise ValueError(f"{part.name}: {len(part.influences)} influence rows for {len(part.shape.positions)} vertices")
        used = sorted({skel.index(n) for row in part.influences for n, w in row if w > 0.0})
        if not used:
            raise ValueError(f"{part.name}: no weighted bone")
        for b in used:
            if b not in block_of:
                raise ValueError(f"{part.name}: bone {skel.names[b]} is not below {com}")
        slot = {b: k for k, b in enumerate(used)}
        rows = [quantize_weights([(slot[skel.index(n)], w) for n, w in row], max_weights) for row in part.influences]
        wpv = max(len(r) for r in rows)
        m = convert_static.shape_to_mesh(part.shape, unit_scale=unit_scale)
        m.colors = []
        m.weights_per_vertex = wpv
        m.weights = [pair for r in rows for pair in (r + [(0, 0)] * (wpv - len(r)))]
        mesh_bytes = sfmesh.serialize(m)
        d, fn = convert_static.mesh_file_path(mesh_bytes)
        meshes[(d, fn)] = mesh_bytes
        pts = [sfmesh.decode_position(p, m.scale) for p in m.positions]
        sphere, box = sfnif.bounds_from_points(pts)
        skin_to_bone = [fo4skin.invert(world[b]) for b in used]
        spheres = []
        for k, b in enumerate(used):
            bp = [fo4skin.apply(skin_to_bone[k], pts[v]) for v, r in enumerate(rows) if any(s == k for s, _ in r)]
            (cx, cy, cz, rad), _ = sfnif.bounds_from_points(bp)
            spheres.append((cx, cy, cz, rad))
        g = f.add_block("BSGeometry", b"")
        mat = f.add_block("NiIntegerExtraData", struct.pack("<iI", s_matid, sfnif.material_id(part.material)))
        att = f.add_block("SkinAttach", struct.pack("<iI", s_skin, len(used)) + b"".join(struct.pack("<I", 0) for _ in used))
        inst = f.add_block("BSSkin::Instance", b"")
        data = f.add_block("BSSkin::BoneData", struct.pack("<I", len(used)) + b"".join(
            struct.pack("<4f", *sp) + struct.pack("<9f", *xf[1]) + struct.pack("<3f", *xf[0]) + struct.pack("<f", xf[2])
            for sp, xf in zip(spheres, skin_to_bone)))
        f.blocks[inst] = struct.pack("<iiI", root, data, len(used)) + struct.pack(f"<{len(used)}i", *[block_of[b] for b in used]) \
            + struct.pack("<I", 0)
        shader = f.add_block("BSLightingShaderProperty", struct.pack("<iIi", f.string_index(part.material.encode("latin-1")), 0, -1))
        f.blocks[g] = sfnif.build_bsgeometry(sfnif.BSGeometry(
            name_idx=f.string_index(part.name.encode("latin-1")), extra_refs=[mat, att], sphere=sphere, box=box,
            skin=inst, shader=shader,
            meshes=[sfnif.MeshRef(3 * len(m.triangles), len(m.positions), 0x40, f"{d}\\{fn}".encode("latin-1")),
                    None, None, None]))
        root_kids.append(g)
        hist: Dict[int, int] = {}
        for r in rows:
            hist[len(r)] = hist.get(len(r), 0) + 1
        report["parts"][part.name] = {"verts": len(m.positions), "tris": len(m.triangles), "material": part.material,
                                      "mesh": f"{d}\\{fn}", "weights_per_vertex": wpv, "bones": [skel.names[b] for b in used],
                                      "influence_histogram": {str(k): v for k, v in sorted(hist.items())},
                                      "box": [round(c, 4) for c in box]}
    f.blocks[root] = _node_bytes(f.string_index(root_name), [bsx], ((0.0, 0.0, 0.0), IDENT_R, 1.0), root_kids,
                                 flags=ROOT_FLAGS)
    f.footer = struct.pack("<II", 1, root)
    return ActorMeshResult(nifmod.serialize(f), meshes, report)


def _template_collisions(template: bytes) -> Dict[str, Tuple[bytes, int, int, bytes]]:
    """{node name: (collision object block, its flags, its trailing u32, physics block bytes)} for every node of a
    vanilla skeleton.nif that owns a bhkNPCollisionObject -> bhkPhysicsSystem."""
    t = nifmod.parse(template)
    out = {}
    for i in range(len(t.blocks)):
        if t.type_of(i) != "bhkNPCollisionObject":
            continue
        target, flags, data, tail = struct.unpack_from("<iHiI", t.blocks[i], 0)
        if not (0 <= data < len(t.blocks)) or t.type_of(data) != "bhkPhysicsSystem":
            continue
        out[fo4skin._block_name(t, target).decode("latin-1")] = (t.blocks[i], flags, tail, t.blocks[data])
    return out


def build_skeleton_nif(skel: Skeleton, template_skeleton: bytes, root_name: bytes, bound: Tuple[tuple, tuple],
                       full_tree: bool = False, com: str = "COM",
                       helpers: Sequence[str] = ("CharacterController", "CharacterBumper"),
                       com_collision: bool = True) -> bytes:
    """skeleton.nif (full_tree=False: Root, COM and the skeleton's other direct children of Root) or skeleton_ref.nif
    (full_tree=True: every bone) for skeleton `skel` (metres), laid out like vanilla: rig root with BSBound "BBX"
    (centre, half extents) + BSXFlags 0x4A, NiStringExtraData sgoKeep on every bone, helper nodes (character
    controller, bumper) as children of the rig root. Physics bodies are copied byte for byte from the template's
    skeleton.nif for COM (com_collision) and the helper nodes it has: they were authored for the template's body,
    not this one."""
    coll = _template_collisions(template_skeleton)
    tmpl = nifmod.parse(template_skeleton)
    tmpl_xf = {}
    for i in range(len(tmpl.blocks)):
        if tmpl.type_of(i) == "NiNode":
            tmpl_xf[fo4skin._block_name(tmpl, i).decode("latin-1")] = nifmod._av_transform(tmpl.blocks[i])
    f = _new_nif(template_skeleton)
    root = f.add_block("NiNode", b"")
    bbx = f.add_block("BSBound", struct.pack("<i3f3f", f.string_index(b"BBX"), *bound[0], *bound[1]))
    bsx = f.add_block("BSXFlags", struct.pack("<iI", f.string_index(b"BSX"), SKELETON_BSX))
    com_i = skel.index(com)
    roots = [i for i, p in enumerate(skel.parents) if p < 0]
    keep = set(range(len(skel.names))) if full_tree else set(roots) | {com_i} | {
        c for r in roots for c in skel.children(r)}
    block_of: Dict[int, int] = {}
    pending: Dict[int, Tuple[int, int]] = {}

    def add_collision(node: int, name: str) -> int:
        blk, flags, tail, phys = coll[name]
        c = f.add_block("bhkNPCollisionObject", b"")
        p = f.add_block("bhkPhysicsSystem", phys)
        f.blocks[c] = struct.pack("<iHiI", node, flags, p, tail)
        return c

    order = [i for i in range(len(skel.names)) if i in keep]
    for b in order:
        block_of[b] = f.add_block("NiNode", b"")
        extra = _string_extra(f, b"sgoKeep", b"sgoKeep")
        c = add_collision(block_of[b], skel.names[b]) if (b == com_i and com_collision and skel.names[b] in coll) else -1
        pending[b] = (extra, c)
    for b in order:
        kids = [block_of[c] for c in skel.children(b) if c in keep]
        extra, c = pending[b]
        f.blocks[block_of[b]] = _node_bytes(f.string_index(skel.names[b].encode("latin-1")), [extra], skel.local[b], kids,
                                            collision=c)
    root_kids = [block_of[r] for r in roots]
    for h in helpers:
        if h not in tmpl_xf or h in skel.names:
            continue
        n = f.add_block("NiNode", b"")
        c = add_collision(n, h) if h in coll else -1
        f.blocks[n] = _node_bytes(f.string_index(h.encode("latin-1")), [], tmpl_xf[h], [], collision=c)
        root_kids.append(n)
    f.blocks[root] = _node_bytes(f.string_index(root_name), [bbx, bsx], ((0.0, 0.0, 0.0), IDENT_R, 1.0), root_kids,
                                 flags=ROOT_FLAGS)
    f.footer = struct.pack("<II", 1, root)
    return nifmod.serialize(f)


def bound_from_points(points) -> Tuple[tuple, tuple]:
    """BSBound (centre, half extents) like vanilla skeleton.nif: box centre, x and y half extents both the larger one."""
    lo = [min(p[a] for p in points) for a in range(3)]
    hi = [max(p[a] for p in points) for a in range(3)]
    c = tuple((lo[a] + hi[a]) / 2 for a in range(3))
    e = [(hi[a] - lo[a]) / 2 for a in range(3)]
    r = max(e[0], e[1])
    return c, (r, r, e[2])


# ---- rig edits: rest-rotation rebase, Starfield-safe bone names, extra bones ------------------------------------
# Measured (robot-anim review, 23 Nov 2026): no vanilla Starfield rig of 386 turns COM or Pelvis by more than 30 degrees,
# and of 8,568 vanilla rig bones '|' and '-' occur only in ship rigs, never in an actor rig. Fallout 4's Handy skeleton
# turns COM -90 degrees about Y and uses '|' / '-' in 80 of its 112 names; these helpers remove both without moving
# anything in world space.

SAFE_BONE_NAME = re.compile(r"^[A-Za-z0-9_]+$")


def _mat_mul(a, b) -> tuple:
    return tuple(sum(a[3 * i + k] * b[3 * k + j] for k in range(3)) for i in range(3) for j in range(3))


def _mat_t(a) -> tuple:
    return (a[0], a[3], a[6], a[1], a[4], a[7], a[2], a[5], a[8])


def _mat_vec(a, v) -> tuple:
    return tuple(a[3 * i] * v[0] + a[3 * i + 1] * v[1] + a[3 * i + 2] * v[2] for i in range(3))


def starfield_bone_name(name: str) -> str:
    """`name` with every character other than a letter, a digit or '_' replaced by '_' (Arm1|0 -> Arm1_0,
    C-Head -> C_Head)."""
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


def starfield_bone_names(names: Sequence[str]) -> Dict[str, str]:
    """{old name: new name} for every name; raises ValueError when two names become the same (case ignored, as
    Skeleton.index ignores it)."""
    out: Dict[str, str] = {}
    seen: Dict[str, str] = {}
    for n in names:
        new = starfield_bone_name(n)
        if not new or not SAFE_BONE_NAME.match(new):
            raise ValueError(f"bone name {n!r} has no safe form")
        if new.lower() in seen and seen[new.lower()] != n:
            raise ValueError(f"bone names {seen[new.lower()]!r} and {n!r} both become {new!r}")
        seen[new.lower()] = n
        out[n] = new
    return out


def rest_rotation_corrections(skel: Skeleton, zero: Sequence[str]) -> List[tuple]:
    """Per bone, the constant rotation C_j (row-major 3x3) rebase_skeleton folds into it so that every bone named in
    `zero` gets an identity parent-local rest rotation: C_j = R_j^T C_parent for those, C_j = identity for every other
    bone. Folding keeps every bone's world POSITION, in the rest pose and in any pose, and turns bone j's world
    rotation into W_j C_j (so a named bone's rest world rotation becomes its parent's)."""
    want = {skel.index(n) for n in zero}
    out: List[tuple] = []
    for i in range(len(skel.names)):
        p = skel.parents[i]
        cp = out[p] if p >= 0 else IDENT_R
        out.append(_mat_mul(_mat_t(skel.local[i][1]), cp) if i in want else IDENT_R)
    return out


def rebase_skeleton(skel: Skeleton, corrections: Sequence[tuple]) -> Skeleton:
    """The skeleton with each bone's frame turned by corrections[j]: local t' = C_p^T t, R' = C_p^T R C_j. Any pose
    (t, R per bone) maps the same way, so world positions are unchanged (see rest_rotation_corrections)."""
    if len(corrections) != len(skel.names):
        raise ValueError(f"{len(corrections)} corrections for {len(skel.names)} bones")
    local = []
    for i, (t, r, s) in enumerate(skel.local):
        p = skel.parents[i]
        cpt = _mat_t(corrections[p]) if p >= 0 else IDENT_R
        local.append((_mat_vec(cpt, t), _mat_mul(_mat_mul(cpt, r), corrections[i]), s))
    return Skeleton(list(skel.names), list(skel.parents), local, list(skel.lock_translation), skel.name)


def rename_skeleton(skel: Skeleton, mapping: Dict[str, str]) -> Skeleton:
    names = [mapping.get(n, n) for n in skel.names]
    if len({n.lower() for n in names}) != len(names):
        raise ValueError("renaming makes two bone names equal")
    return Skeleton(names, list(skel.parents), list(skel.local), list(skel.lock_translation), skel.name)


def add_bone(skel: Skeleton, name: str, parent: str, local: Transform) -> Skeleton:
    """The skeleton with one more bone, appended last (every existing index is kept), under `parent`."""
    if name.lower() in {n.lower() for n in skel.names}:
        raise ValueError(f"bone {name} already exists")
    return Skeleton(list(skel.names) + [name], list(skel.parents) + [skel.index(parent)], list(skel.local) + [local],
                    list(skel.lock_translation) + ([False] if skel.lock_translation else []), skel.name)


# ---- verification ------------------------------------------------------------------------------------------------

def _node_name(n: nifmod.NifFile, i: int) -> str:
    return fo4skin._block_name(n, i).decode("latin-1")


def verify_actor_mesh_nif(nif_bytes: bytes, meshes: Dict[Tuple[str, str], bytes], skel: Skeleton,
                          expected_positions: Optional[Dict[str, List[tuple]]] = None,
                          expected_influences: Optional[Dict[str, List[List[Tuple[str, float]]]]] = None,
                          tol_m: float = 1e-3, exclude: Sequence[str] = ()) -> dict:
    """Re-read a NIF from build_actor_mesh_nif and check it offline. Returns a report; report["ok"] is False and
    report["errors"] lists every failed check. Checks: block graph; SkinAttach / Instance / BoneData counts agree;
    every skin bone is a NiNode of this file named like a skeleton bone; node tree (COM_Twin placed at the skeleton's
    COM) equals inverse(BoneData) within 1e-4; every vertex has 1..4 weights summing to 65535 on valid slots;
    bind-pose linear blend of the stored positions lands on expected_positions (metres) within tol_m; the stored
    weights reproduce expected_influences (bone name -> weight) within 1/2048 (FO4 half-float precision)."""
    n = nifmod.parse(nif_bytes)
    errors: List[str] = []
    world_skel = skel.world()
    rep = {"shapes": {}, "errors": errors}
    twin = [i for i in range(len(n.blocks)) if n.type_of(i) == "NiNode" and _node_name(n, i) == "COM_Twin"]
    if len(twin) != 1:
        errors.append(f"{len(twin)} COM_Twin nodes")
        rep["ok"] = False
        return rep
    pbn = [e for e in struct.unpack_from(f"<{struct.unpack_from('<I', n.blocks[twin[0]], 4)[0]}i", n.blocks[twin[0]], 8)]
    parent_bone = None
    for e in pbn:
        if n.type_of(e) == "NiStringExtraData" and _node_name(n, e) == "ParentBoneName":
            v, = struct.unpack_from("<i", n.blocks[e], 4)
            parent_bone = n.strings[v].decode("latin-1")
    if parent_bone is None:
        errors.append("COM_Twin has no ParentBoneName")
        parent_bone = "COM"
    base = world_skel[skel.index(parent_bone)]
    local_world = nifmod.world_transforms(n)
    node_world = lambda i: nifmod._compose(base, nifmod._compose(fo4skin.invert(local_world(twin[0])), local_world(i)))  # noqa: E731
    bone_nodes = {_node_name(n, i): i for i in nifmod.descendants(n, twin[0]) if n.type_of(i) == "NiNode" and i != twin[0]}
    missing = [skel.names[b] for b in skel.descendants(skel.index(parent_bone))
               if skel.names[b] not in bone_nodes and skel.names[b] not in exclude]
    extra = [nm for nm in bone_nodes if nm not in skel.names]
    if missing:
        errors.append(f"skeleton bones missing from the NIF: {missing}")
    if extra:
        errors.append(f"NIF bones not in the skeleton: {extra}")
    node_err = 0.0
    for nm, i in bone_nodes.items():
        if nm in skel.names:
            w = node_world(i)
            ref = world_skel[skel.index(nm)]
            node_err = max(node_err, math.dist(w[0], ref[0]), max(abs(a - b) for a, b in zip(w[1], ref[1])))
    rep["bone_nodes"] = len(bone_nodes)
    rep["node_vs_skeleton_max_error"] = node_err
    if node_err > 1e-4:
        errors.append(f"bone nodes differ from the skeleton bind by {node_err}")
    by_path = {f"{d}\\{fn}": b for (d, fn), b in meshes.items()}
    for g in [i for i in range(len(n.blocks)) if n.type_of(i) == "BSGeometry"]:
        geo = sfnif.parse_bsgeometry(n.blocks[g])
        name = n.strings[geo.name_idx].decode("latin-1")
        sr = {"errors": 0}
        att = [e for e in geo.extra_refs if n.type_of(e) == "SkinAttach"]
        root_i, data_i, bones = struct.unpack_from("<iiI", n.blocks[geo.skin], 0)[0], \
            struct.unpack_from("<iiI", n.blocks[geo.skin], 0)[1], \
            list(struct.unpack_from(f"<{struct.unpack_from('<iiI', n.blocks[geo.skin], 0)[2]}i", n.blocks[geo.skin], 12))
        bounds, s2b = fo4skin.read_bone_data(n.blocks[data_i])
        att_count = struct.unpack_from("<I", n.blocks[att[0]], 4)[0] if att else -1
        if not (att_count == len(bones) == len(s2b)):
            errors.append(f"{name}: SkinAttach {att_count}, Instance {len(bones)}, BoneData {len(s2b)}")
        bone_names = []
        bind_err = 0.0
        for k, b in enumerate(bones):
            if not (0 <= b < len(n.blocks)) or n.type_of(b) != "NiNode":
                errors.append(f"{name}: slot {k} -> block {b} is not a NiNode")
                bone_names.append("?")
                continue
            nm = _node_name(n, b)
            bone_names.append(nm)
            if nm not in skel.names:
                errors.append(f"{name}: slot {k} bone {nm} is not a skeleton bone")
                continue
            bw = node_world(b)
            ident = nifmod._compose(bw, s2b[k])
            bind_err = max(bind_err, math.dist(ident[0], (0, 0, 0)), max(abs(a - b_) for a, b_ in zip(ident[1], IDENT_R)))
        if bind_err > 1e-4:
            errors.append(f"{name}: node world * BoneData is not identity (max {bind_err})")
        raw = by_path.get(geo.meshes[0].path.decode("latin-1"))
        if raw is None:
            errors.append(f"{name}: .mesh {geo.meshes[0].path!r} not among the written meshes")
            continue
        m = sfmesh.parse(raw)
        wpv = m.weights_per_vertex
        nv = len(m.positions)
        if not 1 <= wpv <= MAX_WEIGHTS or len(m.weights) != wpv * nv:
            errors.append(f"{name}: weights_per_vertex {wpv}, {len(m.weights)} weights for {nv} vertices")
            continue
        pts = [sfmesh.decode_position(p, m.scale) for p in m.positions]
        mats = [nifmod._compose(node_world(b), s2b[k]) for k, b in enumerate(bones)]
        bad_sum = bad_slot = 0
        hist: Dict[int, int] = {}
        max_pos_err = max_w_err = 0.0
        for v in range(nv):
            ws = m.weights[v * wpv:(v + 1) * wpv]
            nz = [(s, w) for s, w in ws if w]
            hist[len(nz)] = hist.get(len(nz), 0) + 1
            if sum(w for _, w in ws) != FULL_WEIGHT:
                bad_sum += 1
            if any(s >= len(bones) for s, _ in nz):
                bad_slot += 1
                continue
            p = [0.0, 0.0, 0.0]
            for s, w in nz:
                q = fo4skin.apply(mats[s], pts[v])
                for a in range(3):
                    p[a] += w / FULL_WEIGHT * q[a]
            if expected_positions is not None:
                max_pos_err = max(max_pos_err, math.dist(p, expected_positions[name][v]))
            if expected_influences is not None:
                want: Dict[str, float] = {}
                for bn, w in expected_influences[name][v]:
                    if w > 0:
                        want[bn] = want.get(bn, 0.0) + w
                tot = sum(want.values()) or 1.0
                got = {bone_names[s]: w / FULL_WEIGHT for s, w in nz}
                for bn in set(want) | set(got):
                    max_w_err = max(max_w_err, abs(got.get(bn, 0.0) - want.get(bn, 0.0) / tot))
        if bad_sum:
            errors.append(f"{name}: {bad_sum} vertices whose weights do not sum to 65535")
        if bad_slot:
            errors.append(f"{name}: {bad_slot} vertices use a slot past the bone list")
        sr.update({"verts": nv, "tris": len(m.triangles), "weights_per_vertex": wpv, "bones": len(bones),
                   "bone_names": bone_names, "influence_histogram": {str(k): v for k, v in sorted(hist.items())},
                   "bind_identity_max_error": bind_err, "vertices_weight_sum_not_one": bad_sum})
        if expected_positions is not None:
            sr["bind_pose_max_error_mm"] = round(max_pos_err * 1000.0, 4)
            if max_pos_err > tol_m:
                errors.append(f"{name}: bind pose off by {max_pos_err * 1000:.3f} mm")
        if expected_influences is not None:
            sr["weight_max_error"] = round(max_w_err, 6)
            if max_w_err > 1.0 / 2048 + 1.0 / FULL_WEIGHT * 4:
                errors.append(f"{name}: weights differ from FO4 by {max_w_err}")
        rep["shapes"][name] = sr
    rep["ok"] = not errors
    return rep


def verify_skeleton_nif(nif_bytes: bytes, skel: Skeleton, full_tree: bool) -> dict:
    """Bones present (all of them for skeleton_ref, else at least Root and COM), world transforms equal the skeleton's
    bind, and the rig root carries BSBound + BSXFlags."""
    n = nifmod.parse(nif_bytes)
    world = nifmod.world_transforms(n)
    sw = skel.world()
    nodes = {_node_name(n, i): i for i in range(len(n.blocks)) if n.type_of(i) == "NiNode"}
    want = skel.names if full_tree else [nm for nm in skel.names if nm in nodes]
    errors = [f"missing bone {nm}" for nm in (skel.names if full_tree else ["Root", "COM"]) if nm not in nodes]
    err = 0.0
    for nm in want:
        if nm in nodes:
            w, r = world(nodes[nm]), sw[skel.index(nm)]
            err = max(err, math.dist(w[0], r[0]), max(abs(a - b) for a, b in zip(w[1], r[1])))
    if err > 1e-4:
        errors.append(f"bone world transforms differ from the skeleton by {err}")
    types = {n.type_of(i) for i in range(len(n.blocks))}
    for t in ("BSBound", "BSXFlags"):
        if t not in types:
            errors.append(f"no {t}")
    return {"ok": not errors, "errors": errors, "nodes": len(nodes), "bones_checked": len([x for x in want if x in nodes]),
            "max_error": err, "collision_objects": sum(1 for i in range(len(n.blocks)) if n.type_of(i) == "bhkNPCollisionObject")}


# ---- Mr. Handy name mapping ----------------------------------------------------------------------------------------

HANDY_SIDE = {"M": 0, "R": 1, "L": 2}    # mrhandy.nif prefix -> skeleton.hkx instance (|0 front +Y, |1 +X, |2 -X)
HANDY_SINGLE = {"Pelvis": "Pelvis", "Ring": "Ring", "Chest": "Chest", "HEAD": "Neck"}


def handy_mesh_bone_to_hkx(name: str) -> Optional[str]:
    """FO4 mrhandy.nif skin bone name -> Fallout 4 Handy skeleton.hkx bone name, or None.

    Evidence (convert_handy.py report, mapping_evidence): the hkx has three copies of each arm and eye arm, suffixed
    |0 (front, +Y), |1 (+X) and |2 (-X); FO4's own part meshes (Parts\\ArmsTypeA1.nif, ModTorsoHandyEye.nif) skin to
    these names. mrhandy.nif names them MArm_/RArm_/LArm_ and MEyeArm/REyeArm/LEyeArm; its nodes stand on the matching
    hkx bone with the same orientation (eye arms <= 0.6 FO4 units, arms translated 1.333 units toward the body).
    HEAD stands where C-Head and its child Neck are (same transform); Neck is the bone, C-Head the part attach point.
    """
    if name in HANDY_SINGLE:
        return HANDY_SINGLE[name]
    m = re.fullmatch(r"([LMR])EyeArm(\d|_Flap|Palm|Palm_Lens|Palm_Iris|Palm_IrisSC)", name)
    if m:
        return f"EyeArm{m.group(2)}|{HANDY_SIDE[m.group(1)]}"
    m = re.fullmatch(r"([LMR])Arm_(\d)", name)
    if m:
        return f"Arm{m.group(2)}|{HANDY_SIDE[m.group(1)]}"
    m = re.fullmatch(r"([LMR])Arm_Hub(\d)", name)
    if m:
        return f"ArmHub{m.group(2)}|{HANDY_SIDE[m.group(1)]}"
    m = re.fullmatch(r"([LMR])Arm_Palm", name)
    if m:
        return f"ArmPalm|{HANDY_SIDE[m.group(1)]}"
    m = re.fullmatch(r"([LMR])Arm_Palm_Bone(\d)", name)
    if m:
        return f"ArmPalmBone{m.group(2)}|{HANDY_SIDE[m.group(1)]}"
    return None
