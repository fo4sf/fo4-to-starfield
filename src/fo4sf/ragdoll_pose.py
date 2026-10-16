"""Pose a Fallout 4 ragdoll NIF with a placed reference's XRGD ragdoll data (docs/ai/research-log.md, 2026-10-11
"XRGD ragdoll pose decoded").

XRGD holds one 28-byte entry per body of the NIF's physics system, in body-index order (the `body` field of the
bhkNPCollisionObject that attaches a body to its node; static bodies included):
    4 bytes of uninitialised memory (kept as bone_id + unused for a loss-free round trip; ESM-wide the u8 is 0 in 71%
    of the entries and the other 3 bytes often hold ASCII fragments of file paths: not a bone id, ignored),
    position xyz (float, game units), rotation xyz (float, radians).
An entry REPLACES the local transform of its body's node, i.e. the transform relative to the parent node (relative to
the reference for a body on the NIF root). Its rotation is a Gamebryo Euler triple: R = Rx(-x) * Ry(-y) * Rz(-z) with
the usual counter-clockwise matrices, in the NIF's own convention (row-major, v' = R v, like NiAVObject rotations).
Nodes without a body keep their NIF transform.

pose_bones returns world transforms in the NIF / reference space: the reference's own position, rotation and scale
(REFR DATA / XSCL) are applied by the caller.
"""
import math
import struct
from typing import Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple, Union

from . import hkpackfile, nif as nifmod

ENTRY = struct.Struct("<B3s3f3f")              # 28 bytes
SYS_BODIES = 64                                # hknpPhysicsSystemData bodyCinfos hkArray (fo4collision.SYS_BODIES)
SCALE_TOLERANCE = 1e-4

Row = Tuple[float, float, float]


class RagdollPoseError(ValueError):
    pass


class RagdollEntry(NamedTuple):
    bone_id: int                               # first byte of the entry: garbage in the ESM, never used for matching
    unused: bytes
    position: Row                              # game units, in the parent node's frame
    rotation: Row                              # radians, Gamebryo Euler XYZ (see euler_matrix)


class BoneTransform(NamedTuple):
    rotation: Tuple[Row, Row, Row]             # rows; v_reference = scale * rotation @ v_node + translation
    translation: Row                           # game units
    scale: float = 1.0                         # always 1 for a bone node (checked); other nodes keep their NIF scale


def parse_xrgd(raw: bytes) -> List[RagdollEntry]:
    """Entries of a raw XRGD subrecord."""
    if len(raw) % ENTRY.size:
        raise RagdollPoseError(f"XRGD size {len(raw)} is not a multiple of {ENTRY.size}")
    out = []
    for k in range(len(raw) // ENTRY.size):
        bone, unused, *v = ENTRY.unpack_from(raw, ENTRY.size * k)
        out.append(RagdollEntry(bone, unused, tuple(v[:3]), tuple(v[3:])))
    return out


def entries_from_export(items: Sequence[Mapping]) -> List[RagdollEntry]:
    """Entries of a cell-export `ragdoll` list (Fo4Export: index, bone_id, unused hex, pos, rot), in index order."""
    items = sorted(items, key=lambda e: e.get("index", 0))
    if [e.get("index", k) for k, e in enumerate(items)] != list(range(len(items))):
        raise RagdollPoseError("ragdoll export indices are not 0..n-1")
    return [RagdollEntry(int(e.get("bone_id", 0)), bytes.fromhex(e.get("unused") or ""), tuple(map(float, e["pos"])),
                         tuple(map(float, e["rot"]))) for e in items]


def euler_matrix(rotation) -> Tuple[float, ...]:
    """Row-major 3x3 (v' = R v) of an XRGD rotation (x, y, z) in radians: R = Rx(-x) Ry(-y) Rz(-z), i.e. Gamebryo's
    clockwise axis rotations multiplied X * Y * Z (NiMatrix3::FromEulerAnglesXYZ)."""
    x, y, z = rotation
    cx, sx, cy, sy, cz, sz = math.cos(x), math.sin(x), math.cos(y), math.sin(y), math.cos(z), math.sin(z)
    rx = (1.0, 0.0, 0.0, 0.0, cx, sx, 0.0, -sx, cx)
    ry = (cy, 0.0, -sy, 0.0, 1.0, 0.0, sy, 0.0, cy)
    rz = (cz, sz, 0.0, -sz, cz, 0.0, 0.0, 0.0, 1.0)
    return nifmod._matmul(rx, nifmod._matmul(ry, rz))


def ragdoll_nodes(n: nifmod.NifFile) -> Tuple[int, Dict[int, int]]:
    """(bhkPhysicsSystem block, {body index: node block}) from the NIF's bhkNPCollisionObjects (one system only)."""
    system, nodes = None, {}
    for i in range(len(n.blocks)):
        if n.type_of(i) != "bhkNPCollisionObject":
            continue
        blk = n.blocks[i]
        if len(blk) < 14:
            raise RagdollPoseError(f"collision object {i} is truncated")
        target, _flags, data, body = struct.unpack_from("<iHiI", blk, 0)
        if not (0 <= data < len(n.blocks)) or n.type_of(data) != "bhkPhysicsSystem":
            raise RagdollPoseError(f"collision object {i} has no bhkPhysicsSystem")
        if system not in (None, data):
            raise RagdollPoseError("collision objects use more than one physics system")
        if not (0 <= target < len(n.blocks)) or not n.type_of(target).endswith("Node"):
            raise RagdollPoseError(f"collision object {i} targets no node")
        if body in nodes:
            raise RagdollPoseError(f"body {body} is attached to two nodes")
        system = data
        nodes[body] = target
    if system is None:
        raise RagdollPoseError("NIF has no collision bodies")
    return system, nodes


def system_body_count(n: nifmod.NifFile, system: int) -> Optional[int]:
    """Number of body cinfos in the system's Havok packfile, or None when the packfile can't be read."""
    blk = n.blocks[system]
    try:
        size, = struct.unpack_from("<I", blk, 0)
        p = hkpackfile.Packfile(blk[4:4 + size])
        roots = [o for o, c in p.objects() if c == "hknpPhysicsSystemData"]
        return p.array(roots[0] + SYS_BODIES)[1] if len(roots) == 1 else None
    except (hkpackfile.PackfileError, struct.error, IndexError, ValueError, StopIteration):
        return None


def _entries(ragdoll_entries) -> List[RagdollEntry]:
    if isinstance(ragdoll_entries, (bytes, bytearray, memoryview)):
        return parse_xrgd(bytes(ragdoll_entries))
    items = list(ragdoll_entries)
    if items and all(isinstance(e, Mapping) for e in items):
        return entries_from_export(items)
    out = [e if isinstance(e, RagdollEntry) else RagdollEntry(0, b"", tuple(e[0]), tuple(e[1])) for e in items]
    for k, e in enumerate(out):
        if len(e.position) != 3 or len(e.rotation) != 3:
            raise RagdollPoseError(f"entry {k} needs 3 position and 3 rotation values")
    return out


def _posed_entries(n: nifmod.NifFile, ragdoll_entries) -> Tuple[Dict[int, RagdollEntry], set]:
    """({bone node block: its entry}, bone node blocks) after the checks pose_bones documents."""
    entries = _entries(ragdoll_entries)
    system, body_node = ragdoll_nodes(n)
    expected = system_body_count(n, system)
    if expected is None:
        expected = max(body_node) + 1
    if len(entries) != expected:
        raise RagdollPoseError(f"{len(entries)} ragdoll entries for {expected} bodies")
    for k, e in enumerate(entries):
        if not all(math.isfinite(v) for v in tuple(e.position) + tuple(e.rotation)):
            raise RagdollPoseError(f"entry {k} is not finite")
    posed = {node: entries[body] for body, node in body_node.items() if body < len(entries)}
    if len(posed) != len(body_node):
        raise RagdollPoseError("a collision object refers to a body past the ragdoll entries")
    return posed, set(body_node.values())


def local_overrides(fo4_nif: Union[bytes, nifmod.NifFile], ragdoll_entries) -> Dict[int, Tuple[Row, tuple, float]]:
    """{bone node block: (translation, row-major rotation 9-tuple, scale)}: the local (parent-relative) transforms the
    XRGD entries give the ragdoll's bone nodes, in nif.world_transforms' form (its local_overrides argument), so shapes,
    skins and collision bodies can be composed in the placed pose. Scale is the node's own (entries carry none); a
    scaled bone node is refused as in pose_bones. Same checks and errors as pose_bones."""
    n = fo4_nif if isinstance(fo4_nif, nifmod.NifFile) else nifmod.parse(fo4_nif)
    posed, _ = _posed_entries(n, ragdoll_entries)
    out = {}
    for node, e in sorted(posed.items()):
        _, _, s = nifmod._av_transform(n.blocks[node])
        if abs(s - 1.0) > SCALE_TOLERANCE:
            raise RagdollPoseError(f"bone node {node} has scale {s:g}; ragdoll bones must be unscaled")
        out[node] = (tuple(float(v) for v in e.position), euler_matrix(e.rotation), s)
    return out


def pose_bones(fo4_nif_bytes: Union[bytes, nifmod.NifFile], ragdoll_entries, all_nodes: bool = False
               ) -> Dict[int, BoneTransform]:
    """{node block index: BoneTransform} of the ragdoll bone nodes (the nodes that own a physics body; every NiNode when
    all_nodes) after applying the XRGD entries, in NIF / reference space (game units).
    ragdoll_entries: raw XRGD bytes, RagdollEntry items, cell-export dicts or (position, rotation) pairs.
    Raises RagdollPoseError when the entries don't fit the NIF (count != number of bodies, as with stale XRGD written
    for another version of the model), contain non-finite numbers, or a bone node ends up scaled."""
    n = fo4_nif_bytes if isinstance(fo4_nif_bytes, nifmod.NifFile) else nifmod.parse(fo4_nif_bytes)
    posed, bones = _posed_entries(n, ragdoll_entries)
    parent = {}
    for i in range(len(n.blocks)):
        if n.type_of(i).endswith("Node") and n.type_of(i) != "BSFaceGenNiNode":
            for c in nifmod.node_children(n, i):
                parent.setdefault(c, i)
    cache = {}

    def world(i, depth=0):
        if i in cache:
            return cache[i]
        if depth > 256:
            raise RagdollPoseError("node tree has a cycle")
        t, r, s = nifmod._av_transform(n.blocks[i])
        if i in posed:
            t, r = tuple(posed[i].position), euler_matrix(posed[i].rotation)
        local = (tuple(t), tuple(r), s)
        cache[i] = local if i not in parent else nifmod._compose(world(parent[i], depth + 1), local)
        return cache[i]

    wanted = sorted(bones) if not all_nodes else [i for i in range(len(n.blocks)) if n.type_of(i).endswith("Node")]
    out = {}
    for i in wanted:
        t, r, s = world(i)
        if i in bones and abs(s - 1.0) > SCALE_TOLERANCE:
            raise RagdollPoseError(f"bone node {i} has world scale {s:g}; ragdoll bones must be unscaled")
        out[i] = BoneTransform((tuple(r[0:3]), tuple(r[3:6]), tuple(r[6:9])), tuple(t), s)
    return out
