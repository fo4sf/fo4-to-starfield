"""Put a Fallout 4 actor's skinned mesh on a Starfield actor's existing skeleton (template rebind).

    res = actor_rebind.rebind(template_nif, fo4_nif, bone_for, materials={"Torso": "materials\\...\\body.mat"})
    res.nif, res.meshes   # NIF bytes; {(dir, name): .mesh bytes} for Data/geometries/<dir>/<name>.mesh

The template is a vanilla Starfield skinned NIF the target race already draws (first use: Codsworth on the garden mini
bot, Meshes\\Actors\\MiniBotA\\Mesh\\minibota_base\\minibota_mesh.nif; ROADMAP B2). Everything in it is kept (nodes,
ragdoll, skin bone list and the skin-to-bone transforms of BSSkin::BoneData), except that its visible geometry is
replaced: the FO4 shapes are posed as the FO4 NIF's nodes stand (convert_static.pose_skinned_shapes), scaled to metres,
grouped by material, and every vertex is bound rigidly (one weight, 65535) to the template bone that bone_for() names
for the vertex's heaviest FO4 bone. Because the template's skin-to-bone transforms are kept, the mesh stands at its FO4
position in the bind pose and follows the template's bones when the race animates.

Layouts used (verified on the PC, 2026-10-18, scripts/actors/codsworth_dump.py output for minibota_mesh.nif, bs173):
BSGeometry as sfnif.parse_bsgeometry; BSSkin::Instance i32 root, i32 bone data, u32 N, N x i32 bone nodes, then a tail
kept as is; BSSkin::BoneData u32 N then N x 68 bytes (fo4skin.BONE_ENTRY: sphere, rotation, translation, scale); the
mini bot mesh has one weight per vertex. NiNode children follow NiAVObject + collision ref (nif.node_children).
Unresolved until seen in game: whether the race's animations look right on a body of a different shape, and LOD.
"""
import struct
from dataclasses import dataclass, field, replace
from typing import Callable, Dict, List, Optional, Tuple

from . import convert_static, fo4skin, nif as nifmod, sfmesh, sfnif

FULL_WEIGHT = 65535


@dataclass
class RebindResult:
    nif: bytes
    meshes: Dict[Tuple[str, str], bytes]
    report: dict = field(default_factory=dict)


def _name(n, i) -> str:
    k, = struct.unpack_from("<i", n.blocks[i], 0)
    return n.strings[k].decode("latin-1") if 0 <= k < len(n.strings) else ""


def _children_offset(blk: bytes) -> int:
    _, nextra = struct.unpack_from("<iI", blk, 0)
    return 8 + 4 * nextra + 8 + 52 + 4


def _set_children(n, node: int, children: List[int]) -> None:
    blk = n.blocks[node]
    p = _children_offset(blk)
    count, = struct.unpack_from("<I", blk, p)
    n.blocks[node] = (blk[:p] + struct.pack("<I", len(children)) + struct.pack(f"<{len(children)}i", *children)
                      + blk[p + 4 + 4 * count:])


def _raw_children(n, node: int) -> List[int]:
    blk = n.blocks[node]
    p = _children_offset(blk)
    count, = struct.unpack_from("<I", blk, p)
    return list(struct.unpack_from(f"<{count}i", blk, p + 4))


def read_instance(blk: bytes):
    root, data, count = struct.unpack_from("<iiI", blk, 0)
    if 12 + 4 * count > len(blk):
        raise nifmod.NifError(f"BSSkin::Instance: {count} bones run past {len(blk)} bytes")
    return root, data, list(struct.unpack_from(f"<{count}i", blk, 12)), blk[12 + 4 * count:]


def write_instance(root, data, bones, tail) -> bytes:
    return struct.pack("<iiI", root, data, len(bones)) + struct.pack(f"<{len(bones)}i", *bones) + tail


def _bone_data_with_spheres(blk: bytes, spheres: Dict[int, tuple]) -> bytes:
    count, = struct.unpack_from("<I", blk, 0)
    if 4 + fo4skin.BONE_ENTRY * count != len(blk):
        raise nifmod.NifError(f"BSSkin::BoneData: size {len(blk)} != 4 + 68 * {count}")
    out = bytearray(blk)
    for slot, sphere in spheres.items():
        struct.pack_into("<4f", out, 4 + fo4skin.BONE_ENTRY * slot, *sphere)
    return bytes(out)


def _skin_to_bone(blk: bytes, slot: int):
    o = 4 + fo4skin.BONE_ENTRY * slot
    rot = struct.unpack_from("<9f", blk, o + 16)
    tr = struct.unpack_from("<3f", blk, o + 52)
    scale, = struct.unpack_from("<f", blk, o + 64)
    return tr, rot, scale


def _sphere(points):
    if not points:
        return None
    (cx, cy, cz, r), _ = sfnif.bounds_from_points(points)
    return cx, cy, cz, r


def heaviest_bones(src, shape) -> List[Optional[str]]:
    """Per vertex: the name of the FO4 bone with the largest weight (None for every vertex of an unskinned shape)."""
    skin = fo4skin.read_skin(src, shape.block) if shape.skinned else None
    if skin is None:
        return [None] * len(shape.positions)
    return [skin.bone_names[ix[max(range(len(w)), key=lambda j: w[j])]].decode("latin-1")
            for w, ix in zip(skin.weights, skin.indices)]


def _merge(shapes):
    """One Fo4Shape from several posed shapes (identity transforms), filling missing vertex colours with white."""
    first = shapes[0]
    pos, uvs, nrm, tan, col, tris = [], [], [], [], [], []
    has = {k: all(getattr(s, k) for s in shapes) for k in ("uvs", "normals", "tangents")}
    any_col = any(s.colors for s in shapes)
    for s in shapes:
        base = len(pos)
        pos += s.positions
        if has["uvs"]:
            uvs += s.uvs
        if has["normals"]:
            nrm += s.normals
        if has["tangents"]:
            tan += s.tangents
        if any_col:
            col += s.colors or [(255, 255, 255, 255)] * len(s.positions)
        tris += [(a + base, b + base, c + base) for a, b, c in s.triangles]
    return replace(first, positions=pos, uvs=uvs, normals=nrm, tangents=tan, colors=col, triangles=tris,
                   translation=(0.0, 0.0, 0.0), rotation=(1, 0, 0, 0, 1, 0, 0, 0, 1), scale=1.0, skinned=False)


def rebind(template_nif: bytes, fo4_nif: bytes, bone_for: Callable[[Optional[str]], str],
           materials: Optional[Dict[str, str]] = None, target: Optional[str] = None,
           unit_scale: float = convert_static.UNIT_SCALE, default_material: str = convert_static.PLACEHOLDER_MATERIAL,
           skip_shapes=(), plain_shader: bool = False) -> RebindResult:
    """See the module docstring. bone_for(fo4 bone name or None) returns a bone name of the template's skin instance;
    materials maps FO4 shape names to .mat paths; target names the template BSGeometry to replace (default: the first
    skinned one); other template geometries are detached so only the FO4 actor shows. plain_shader writes each shader
    property as the static converter does (the .mat name, no extra data, no controller) instead of the template's own
    block with its name swapped. For the Red Rocket crash bisect; the hypothesis under test, not yet confirmed in game,
    is that the loader reads the template block's later bytes as a link."""
    materials = materials or {}
    t = nifmod.parse(template_nif)
    geoms = [i for i in range(len(t.blocks)) if t.type_of(i) == "BSGeometry"]
    parsed = {i: sfnif.parse_bsgeometry(t.blocks[i]) for i in geoms}
    tgt = next((i for i in geoms if (_name(t, i) == target if target else parsed[i].skin >= 0)), None)
    if tgt is None:
        raise nifmod.NifError(f"template has no {'BSGeometry ' + target if target else 'skinned BSGeometry'}")
    g0 = parsed[tgt]
    parents = {i: _raw_children(t, i) for i in range(len(t.blocks)) if t.type_of(i).endswith("Node")}
    parent = next((p for p, ch in parents.items() if tgt in ch), None)
    if parent is None:
        raise nifmod.NifError(f"template BSGeometry {tgt} has no parent node")
    root, data, bones, tail = read_instance(t.blocks[g0.skin])
    slot_names = [_name(t, b) for b in bones]
    report = {"template_geometry": _name(t, tgt), "template_bones": slot_names, "groups": {}, "bound": {}}

    src = nifmod.parse(fo4_nif)
    shapes = [s for s in nifmod.fo4_trishapes(src, placed=True) if s.name.decode("latin-1") not in skip_shapes]
    heavy = {s.block: heaviest_bones(src, s) for s in shapes}
    posed = convert_static.pose_skinned_shapes(src, shapes, report.setdefault("pose", {}))
    groups: Dict[str, list] = {}
    for s in posed:
        groups.setdefault(materials.get(s.name.decode("latin-1"), default_material), []).append(s)

    meshes: Dict[Tuple[str, str], bytes] = {}
    new_children = [c for c in parents[parent] if c not in geoms]          # detach every template geometry
    report["detached"] = sorted({_name(t, c) for ch in parents.values() for c in ch if c in geoms and c != tgt})
    for node, ch in parents.items():                                       # wherever it hangs, not only beside tgt
        if node != parent and any(c in geoms for c in ch):
            _set_children(t, node, [c for c in ch if c not in geoms])
    bone_data0 = t.blocks[data]
    for k, (mat, members) in enumerate(groups.items()):
        merged = _merge(members)
        slots = []
        for s in members:
            for b in heavy[s.block]:
                name = bone_for(b)
                if name not in slot_names:
                    raise nifmod.NifError(f"bone_for({b!r}) = {name!r} is not a template bone {slot_names}")
                slots.append(slot_names.index(name))
                report["bound"][f"{b}->{name}"] = report["bound"].get(f"{b}->{name}", 0) + 1
        m = convert_static.shape_to_mesh(merged, unit_scale)
        m.weights_per_vertex = 1
        m.weights = [(sl, FULL_WEIGHT) for sl in slots]
        mesh_bytes = sfmesh.serialize(m)
        d, f = convert_static.mesh_file_path(mesh_bytes)
        meshes[(d, f)] = mesh_bytes
        pts = [sfmesh.decode_position(p, m.scale) for p in m.positions]
        sphere, box = sfnif.bounds_from_points(pts)
        spheres = {}
        for sl in set(slots):
            xf = _skin_to_bone(bone_data0, sl)
            spheres[sl] = _sphere([fo4skin.apply(xf, p) for p, s2 in zip(pts, slots) if s2 == sl])
        flags = g0.meshes[0].flags if g0.meshes[0] else 0x40
        g = replace(g0, name_idx=t.string_index(f"FO4_{k}".encode()), sphere=sphere, box=box,
                    meshes=[sfnif.MeshRef(3 * len(m.triangles), len(m.positions), flags, f"{d}\\{f}".encode()),
                            None, None, None])
        if k == 0:
            gi, si, bi, di = tgt, g0.shader, g0.skin, data
        else:                                                               # copies of the template's blocks
            gi = t.add_block("BSGeometry", t.blocks[tgt])
            si = t.add_block("BSLightingShaderProperty", t.blocks[g0.shader])
            bi = t.add_block("BSSkin::Instance", t.blocks[g0.skin])
            di = t.add_block("BSSkin::BoneData", bone_data0)
            g = replace(g, extra_refs=[t.add_block(t.type_of(e), t.blocks[e]) for e in g0.extra_refs])
            new_children.append(gi)
        g = replace(g, shader=si, skin=bi)
        for e in g.extra_refs:                                               # MaterialID follows the new .mat
            if t.type_of(e) == "NiIntegerExtraData" and _name(t, e) == "MaterialID":
                t.blocks[e] = t.blocks[e][:4] + struct.pack("<I", sfnif.material_id(mat))
        if plain_shader:
            t.blocks[si] = struct.pack("<iIi", t.string_index(mat.encode("latin-1")), 0, -1)
        else:
            shader = bytearray(t.blocks[si])
            struct.pack_into("<i", shader, 0, t.string_index(mat.encode("latin-1")))
            t.blocks[si] = bytes(shader)
        t.blocks[bi] = write_instance(root, di, bones, tail)
        t.blocks[di] = _bone_data_with_spheres(bone_data0, {s: v for s, v in spheres.items() if v})
        t.blocks[gi] = sfnif.build_bsgeometry(g)
        report["groups"][mat] = {"shapes": [s.name.decode("latin-1") for s in members], "verts": len(m.positions),
                                 "tris": len(m.triangles), "mesh": f"{d}\\{f}", "box": [round(v, 3) for v in box]}
    new_children.insert(0, tgt)
    _set_children(t, parent, new_children)
    return RebindResult(nifmod.serialize(t), meshes, report)
