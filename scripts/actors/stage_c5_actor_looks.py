"""Stage Fallout 4 HumanRace outfits for Preston Garvey and Concord Raiders (Round 10 C5).

    python scripts/actors/stage_c5_actor_looks.py --fo4-data "<FO4 Data>" --sf-data "<Starfield Data>"
        --staging "<new empty dir>" [--content-resources "<ContentResources.zip>"] [--texconv "<texconv.exe>"]

Rebinds Fallout 4 skinned clothing/armor NIFs onto vanilla Starfield HumanRace (0x00347D) SkinAttach templates:
  1. Preston Garvey body + gloves:
     - FO4 sources: meshes/armor/preston_garvey/prestongarveyoutfit.nif + prestongarveygloves.nif
     - SF template: meshes/actors/human/mesh/naked_body/naked_m.nif (41 SkinAttach bones)
     - Output NIF:  meshes/fo4port/armor/preston_garvey/prestongarveyoutfit_m.nif
  2. Preston Garvey Minuteman hat:
     - FO4 source:  meshes/armor/preston_garvey/prestongarveyhat.nif
     - SF template: meshes/clothes/outfit_first_mercenary_01/outfit_first_mercenary_01_hat_m.nif (SkinAttach ['C_Head'])
     - Output NIF:  meshes/fo4port/armor/preston_garvey/prestongarveyhat_m.nif
  3. Concord Raider body + harness + hands:
     - FO4 sources: meshes/armor/raiderunderarmor/raiderunderarmorm.nif + meshes/armor/raider04/raider04m.nif
                    + meshes/actors/character/characterassets/malehands.nif
     - SF template: meshes/actors/human/mesh/naked_body/naked_m.nif (41 SkinAttach bones)
     - Materials:   reuses already-converted Starfield .mat/.dds in FO4ActorRaider - Main.ba2:
                    materials/fo4core/armor/raiderunderarmor/raiderunderarmorm.mat
                    materials/fo4core/armor/raider04/raider04.mat
                    materials/fo4core/actors/character/basehumanmale/basehumanskin.mat
                    materials/fo4core/actors/character/basehumanmale/basehumanmaleskinhands.mat
     - Output NIF:  meshes/fo4core/armor/raider04/concord_raider_m.nif

Offline-provable vs in-game (R15):
  - Proven offline: NIF block graph, SkinAttach bone table, BSSkin::Instance (-1 bone refs) + BSSkin::BoneData spheres,
    BSMeshData v2 4-weight/1-weight normalized skin weights, meshlets/cull_data, MaterialID CRC32, plain shader blocks,
    and world-space vertex bounds matching HumanRace Naked_M / Hat_M within millimetres.
  - Unproven until run in game: Starfield HumanRace runtime deformation, cloth/coat skirt rig follow, and lighting.
"""
import argparse
from dataclasses import dataclass, field, replace
import glob
import json
import os
import posixpath
import struct
import sys
import tempfile
from typing import Callable, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from fo4sf import actor_rebind, ba2, convert_static, fo4skin, nif as nifmod, sfmesh, sfnif  # noqa: E402

SF_BODY_TEMPLATE = "meshes/actors/human/mesh/naked_body/naked_m.nif"
SF_HAT_TEMPLATE = "meshes/clothes/outfit_first_mercenary_01/outfit_first_mercenary_01_hat_m.nif"

PRESTON_OUTFIT_SOURCES = (
    "meshes/armor/preston_garvey/prestongarveyoutfit.nif",
    "meshes/armor/preston_garvey/prestongarveygloves.nif",
)
PRESTON_HAT_SOURCES = (
    "meshes/armor/preston_garvey/prestongarveyhat.nif",
)
RAIDER_OUTFIT_SOURCES = (
    "meshes/armor/raiderunderarmor/raiderunderarmorm.nif",
    "meshes/armor/raider04/raider04m.nif",
    "meshes/actors/character/characterassets/malehands.nif",
)

PRESTON_OUTFIT_REL = "fo4port/armor/preston_garvey/prestongarveyoutfit_m.nif"
PRESTON_HAT_REL = "fo4port/armor/preston_garvey/prestongarveyhat_m.nif"
RAIDER_OUTFIT_REL = "fo4core/armor/raider04/concord_raider_m.nif"

# Already-converted Fallout 4 human/raider Starfield .mat paths shipped in FO4ActorRaider - Main.ba2
EXISTING_FO4CORE_MATS = {
    "raiderunderarmorm": "materials\\fo4core\\armor\\raiderunderarmor\\raiderunderarmorm.mat",
    "raider04": "materials\\fo4core\\armor\\raider04\\raider04.mat",
    "malebody": "materials\\fo4core\\actors\\character\\basehumanmale\\basehumanskin.mat",
    "malehands": "materials\\fo4core\\actors\\character\\basehumanmale\\basehumanmaleskinhands.mat",
}

# FO4 posed human head stands at Z = 120.84 FO4 units; SF HumanRace Naked_M head origin is Z = +1.63227 m.
FO4_TO_SF_HUMAN_SCALE = 1.63227 / 120.84


@dataclass
class HumanRebindResult:
    nif: bytes
    meshes: Dict[Tuple[str, str], bytes]
    report: dict = field(default_factory=dict)


def parse_skin_attach(blk: bytes) -> Tuple[int, List[str]]:
    """Decode Starfield SkinAttach block: (name_str_idx, [bone_name, ...])."""
    if len(blk) < 8:
        raise nifmod.NifError(f"SkinAttach block too short ({len(blk)} B)")
    name_idx, count = struct.unpack_from("<iI", blk, 0)
    pos = 8
    names: List[str] = []
    for _ in range(count):
        if pos + 4 > len(blk):
            raise nifmod.NifError("SkinAttach truncated at string length")
        slen, = struct.unpack_from("<I", blk, pos)
        pos += 4
        if pos + slen > len(blk):
            raise nifmod.NifError("SkinAttach truncated inside bone name")
        names.append(blk[pos:pos + slen].decode("latin-1"))
        pos += slen
    if pos != len(blk):
        raise nifmod.NifError(f"SkinAttach trailing {len(blk) - pos} bytes")
    return name_idx, names


def build_skin_attach(name_idx: int, names: Sequence[str]) -> bytes:
    parts = [struct.pack("<iI", name_idx, len(names))]
    for nm in names:
        raw = nm.encode("latin-1")
        parts.append(struct.pack("<I", len(raw)) + raw)
    return b"".join(parts)


def invert_rigid(xf: Tuple[tuple, tuple, float]) -> Tuple[tuple, tuple, float]:
    """Invert (t, R_row_major_9, s) where v' = s * R * v + t -> v = (1/s) * R^T * (v' - t)."""
    t, r, s = xf
    inv_s = 1.0 / s if s else 1.0
    rt = (
        r[0], r[3], r[6],
        r[1], r[4], r[7],
        r[2], r[5], r[8],
    )
    tx = -inv_s * (rt[0] * t[0] + rt[1] * t[1] + rt[2] * t[2])
    ty = -inv_s * (rt[3] * t[0] + rt[4] * t[1] + rt[5] * t[2])
    tz = -inv_s * (rt[6] * t[0] + rt[7] * t[1] + rt[8] * t[2])
    return (tx, ty, tz), rt, inv_s


def fo4_human_bone_to_sf(fo4_bone: Optional[str], available: Sequence[str]) -> str:
    """Map a Fallout 4 human/cloth bone name onto the closest Starfield HumanRace SkinAttach bone."""
    avail = set(available)

    def pick(*candidates: str) -> str:
        for c in candidates:
            if c in avail:
                return c
        return available[0]

    if not fo4_bone:
        return pick("C_Chest", "C_Hips", "C_Head")
    b = fo4_bone.strip()
    bl = b.lower()

    if "head" in bl:
        return pick("C_Head", "C_Neck1", "C_Chest")
    if "neck" in bl or "collar_" in bl:
        return pick("C_Neck1", "C_Neck_Twist", "C_Chest")

    # Left / Right arm & hand chains
    for prefix, side in (("larm_", "L"), ("l_", "L"), ("lbreast", "L"), ("lbutt", "L"), ("lleg_", "L"),
                         ("rarm_", "R"), ("r_", "R"), ("rbreast", "R"), ("rbutt", "R"), ("rleg_", "R")):
        if bl.startswith(prefix):
            if "collarbone" in bl or "clavicle" in bl:
                return pick(f"{side}_Clavicle", "C_Chest")
            if "shoulder" in bl:
                return pick(f"{side}_Deltoid", f"{side}_Biceps", f"{side}_Clavicle")
            if "upperarm" in bl or "uppertwist" in bl or "upperfat" in bl:
                if "twist" in bl:
                    return pick(f"{side}_Biceps_Twist1", f"{side}_Biceps_Twist", f"{side}_Biceps")
                return pick(f"{side}_Biceps", f"{side}_Deltoid")
            if "forearm3" in bl or "hand" in bl or "finger" in bl or "thumb" in bl:
                return pick(f"{side}_Wrist", f"{side}_Wrist_Twist1", f"{side}_Wrist_Twist", f"{side}_Forearm")
            if "forearm1" in bl:
                return pick(f"{side}_Forearm", f"{side}_Elbow", f"{side}_Biceps")
            if "forearm" in bl:
                return pick(f"{side}_Wrist_Twist", f"{side}_Forearm")
            if "breast" in bl or "ribhelper" in bl:
                return pick("C_Chest", "C_Spine2")
            if "butt" in bl:
                return pick(f"{side}_Butt", "C_Hips")
            if "thigh" in bl:
                if "low" in bl:
                    return pick(f"{side}_Thigh_Twist1", f"{side}_Thigh_Twist", f"{side}_Thigh")
                return pick(f"{side}_Thigh", f"{side}_Thigh_Twist", "C_Hips")
            if "calf" in bl:
                return pick(f"{side}_Calf", f"{side}_Knee", f"{side}_Thigh")
            if "foot" in bl:
                return pick(f"{side}_Foot", f"{side}_Calf")
            if "toe" in bl:
                return pick(f"{side}_Toe", f"{side}_Foot")

    # Cloth skirt / duster coat tails & bags follow thighs / hips smoothly
    if bl.startswith("cloth_"):
        if any(k in bl for k in ("_002", "_003")):
            # Coat lower tails: split by left/right or center hips
            return pick("C_Hips", "C_Spine")
        if "collar" in bl:
            return pick("C_Neck1", "C_Chest")
        return pick("C_Hips", "C_Spine1", "C_Chest")

    if "chest" in bl:
        return pick("C_Chest", "C_Spine2")
    if "spine2" in bl:
        return pick("C_Spine2", "C_Chest")
    if "spine1" in bl:
        return pick("C_Spine1", "C_Spine")
    if "spine" in bl:
        return pick("C_Spine", "C_Hips")
    if "pelvis" in bl or "com" == bl:
        return pick("C_Hips", "C_Spine")

    return pick("C_Chest", "C_Hips", "C_Head")


def _vertex_slot_weights(
    src: nifmod.NifFile,
    shape,
    slot_lookup: Dict[str, int],
    bone_mapper: Callable[[Optional[str]], str],
    wpv: int,
) -> List[Tuple[int, int]]:
    """Convert FO4 per-vertex skin weights into `wpv` normalized (slot, u16_weight) pairs summing to 65535."""
    skin = fo4skin.read_skin(src, shape.block) if shape.skinned else None
    default_slot = slot_lookup[bone_mapper(None)]
    out: List[Tuple[int, int]] = []
    if skin is None:
        for _ in range(len(shape.positions)):
            out.append((default_slot, actor_rebind.FULL_WEIGHT))
            for _ in range(wpv - 1):
                out.append((0, 0))
        return out

    for w_row, ix_row in zip(skin.weights, skin.indices):
        merged: Dict[int, float] = {}
        for w, bone_ix in zip(w_row, ix_row):
            if w <= 0.0 or bone_ix >= len(skin.bone_names):
                continue
            fo4_nm = skin.bone_names[bone_ix].decode("latin-1")
            sf_nm = bone_mapper(fo4_nm)
            sl = slot_lookup[sf_nm]
            merged[sl] = merged.get(sl, 0.0) + float(w)
        if not merged:
            merged[default_slot] = 1.0
        ranked = sorted(merged.items(), key=lambda kv: (-kv[1], kv[0]))[:wpv]
        total = sum(v for _, v in ranked) or 1.0
        quant: List[List[int]] = [[sl, int(round((v / total) * actor_rebind.FULL_WEIGHT))] for sl, v in ranked]
        # Ensure exact sum == 65535 on the dominant slot
        diff = actor_rebind.FULL_WEIGHT - sum(q[1] for q in quant)
        quant[0][1] = max(0, min(actor_rebind.FULL_WEIGHT, quant[0][1] + diff))
        for sl, qw in quant:
            out.append((sl, qw))
        for _ in range(wpv - len(quant)):
            out.append((0, 0))
    return out


def rebind_human_skin_attach(
    template_nif: bytes,
    fo4_sources: Sequence[Tuple[str, bytes, Dict[str, str]]],
    unit_scale: float = FO4_TO_SF_HUMAN_SCALE,
    weights_per_vertex: int = 4,
    default_material: str = convert_static.PLACEHOLDER_MATERIAL,
    skip_shapes: Sequence[str] = (),
) -> HumanRebindResult:
    """Rebind one or more Fallout 4 skinned NIFs onto a Starfield HumanRace SkinAttach template NIF."""
    t = nifmod.parse(template_nif)
    geoms = [i for i in range(len(t.blocks)) if t.type_of(i) == "BSGeometry"]
    parsed = {i: sfnif.parse_bsgeometry(t.blocks[i]) for i in geoms}
    tgt = next((i for i in geoms if parsed[i].skin >= 0), None)
    if tgt is None:
        raise nifmod.NifError("template has no skinned BSGeometry")
    g0 = parsed[tgt]
    sa_ref = next((e for e in g0.extra_refs if t.type_of(e) == "SkinAttach"), None)
    if sa_ref is None:
        raise nifmod.NifError("template BSGeometry has no SkinAttach extra data")
    _, slot_names = parse_skin_attach(t.blocks[sa_ref])
    root, data, bones, tail = actor_rebind.read_instance(t.blocks[g0.skin])
    if len(bones) != len(slot_names):
        raise nifmod.NifError(f"SkinAttach count {len(slot_names)} != BSSkin::Instance count {len(bones)}")
    slot_lookup = {nm: idx for idx, nm in enumerate(slot_names)}

    parents = {i: actor_rebind._raw_children(t, i) for i in range(len(t.blocks)) if t.type_of(i).endswith("Node")}
    parent = next((p for p, ch in parents.items() if tgt in ch), None)
    if parent is None:
        raise nifmod.NifError(f"template BSGeometry {tgt} has no parent node")

    wt_fn = nifmod.world_transforms(t)
    inv_world_to_mesh = invert_rigid(wt_fn(tgt))

    def bone_mapper(nm: Optional[str]) -> str:
        return fo4_human_bone_to_sf(nm, slot_names)

    groups: Dict[str, List[Tuple[object, List[Tuple[int, int]]]]] = {}
    bound_counts: Dict[str, int] = {}
    pose_reports: Dict[str, dict] = {}

    for src_label, fo4_bytes, mat_map in fo4_sources:
        src = nifmod.parse(fo4_bytes)
        shapes = [s for s in nifmod.fo4_trishapes(src, placed=True) if s.name.decode("latin-1") not in skip_shapes]
        p_rep: dict = {}
        posed = convert_static.pose_skinned_shapes(src, shapes, p_rep)
        pose_reports[src_label] = p_rep
        for raw_s, posed_s in zip(shapes, posed):
            sname = raw_s.name.decode("latin-1")
            mat = mat_map.get(sname, default_material)
            # Transform posed FO4 root coordinates (scaled to SF human height) into template .mesh local space
            local_pts = [
                fo4skin.apply(
                    inv_world_to_mesh,
                    (x * unit_scale, y * unit_scale, z * unit_scale),
                )
                for x, y, z in posed_s.positions
            ]
            # Transform normals/tangents by inv_world_to_mesh rotation if non-identity
            _, inv_r, _ = inv_world_to_mesh
            is_ident_r = (
                abs(inv_r[0] - 1.0) < 1e-4 and abs(inv_r[4] - 1.0) < 1e-4 and abs(inv_r[8] - 1.0) < 1e-4
            )
            local_nrm = posed_s.normals
            local_tan = posed_s.tangents
            if not is_ident_r:
                if local_nrm:
                    local_nrm = [fo4skin.apply(((0.0, 0.0, 0.0), inv_r, 1.0), n) for n in local_nrm]
                if local_tan:
                    local_tan = [
                        (*fo4skin.apply(((0.0, 0.0, 0.0), inv_r, 1.0), (tx, ty, tz)), tw)
                        for tx, ty, tz, tw in local_tan
                    ]
            # Strip vertex colors so HumanRace .mesh matches vanilla (col=0)
            adj_shape = replace(
                posed_s,
                positions=local_pts,
                normals=local_nrm,
                tangents=local_tan,
                colors=[],
            )
            vweights = _vertex_slot_weights(src, raw_s, slot_lookup, bone_mapper, weights_per_vertex)
            for hb in actor_rebind.heaviest_bones(src, raw_s):
                target_bn = bone_mapper(hb)
                key = f"{hb}->{target_bn}"
                bound_counts[key] = bound_counts.get(key, 0) + 1
            groups.setdefault(mat, []).append((adj_shape, vweights))

    if not groups:
        raise nifmod.NifError("no FO4 shapes remained after filtering")

    meshes: Dict[Tuple[str, str], bytes] = {}
    new_children = [c for c in parents[parent] if c not in geoms]
    for node, ch in parents.items():
        if node != parent and any(c in geoms for c in ch):
            actor_rebind._set_children(t, node, [c for c in ch if c not in geoms])

    bone_data0 = t.blocks[data]
    report = {
        "template_bones": slot_names,
        "weights_per_vertex": weights_per_vertex,
        "groups": {},
        "bound": bound_counts,
        "pose": pose_reports,
    }

    for k, (mat, items) in enumerate(groups.items()):
        member_shapes = [it[0] for it in items]
        merged = actor_rebind._merge(member_shapes)
        all_weights: List[Tuple[int, int]] = []
        for _, vw in items:
            all_weights.extend(vw)
        # unit_scale=1.0 because positions were already scaled & transformed into template .mesh local space
        m = convert_static.shape_to_mesh(merged, unit_scale=1.0)
        m.weights_per_vertex = weights_per_vertex
        m.weights = all_weights
        mesh_bytes = sfmesh.serialize(m)
        d, f = convert_static.mesh_file_path(mesh_bytes)
        meshes[(d, f)] = mesh_bytes

        pts = [sfmesh.decode_position(p, m.scale) for p in m.positions]
        sphere, box = sfnif.bounds_from_points(pts)
        # Update per-bone bounding spheres using vertices weighted to each slot
        slot_pts: Dict[int, List[Tuple[float, float, float]]] = {}
        for v_idx, pt in enumerate(pts):
            base = v_idx * weights_per_vertex
            for j in range(weights_per_vertex):
                sl, qw = all_weights[base + j]
                if qw > 0:
                    slot_pts.setdefault(sl, []).append(pt)
        spheres = {}
        for sl, spts in slot_pts.items():
            xf = actor_rebind._skin_to_bone(bone_data0, sl)
            sph = actor_rebind._sphere([fo4skin.apply(xf, p) for p in spts])
            if sph:
                spheres[sl] = sph

        flags = g0.meshes[0].flags if g0.meshes[0] else 0x40
        g = replace(
            g0,
            name_idx=t.string_index(f"FO4Human_{k}".encode("latin-1")),
            sphere=sphere,
            box=box,
            meshes=[sfnif.MeshRef(3 * len(m.triangles), len(m.positions), flags, f"{d}\\{f}".encode("latin-1")),
                    None, None, None],
        )
        if k == 0:
            gi, si, bi, di = tgt, g0.shader, g0.skin, data
        else:
            gi = t.add_block("BSGeometry", t.blocks[tgt])
            si = t.add_block("BSLightingShaderProperty", t.blocks[g0.shader])
            bi = t.add_block("BSSkin::Instance", t.blocks[g0.skin])
            di = t.add_block("BSSkin::BoneData", bone_data0)
            g = replace(g, extra_refs=[t.add_block(t.type_of(e), t.blocks[e]) for e in g0.extra_refs])
            new_children.append(gi)
        g = replace(g, shader=si, skin=bi)
        for e in g.extra_refs:
            if t.type_of(e) == "NiIntegerExtraData" and actor_rebind._name(t, e) == "MaterialID":
                t.blocks[e] = t.blocks[e][:4] + struct.pack("<I", sfnif.material_id(mat))
        # Plain shader block (proven crash-free on Codsworth)
        t.blocks[si] = struct.pack("<iIi", t.string_index(mat.encode("latin-1")), 0, -1)
        t.blocks[bi] = actor_rebind.write_instance(root, di, bones, tail)
        t.blocks[di] = actor_rebind._bone_data_with_spheres(bone_data0, spheres)
        t.blocks[gi] = sfnif.build_bsgeometry(g)

        world_pts = [fo4skin.apply(wt_fn(tgt), pt) for pt in pts]
        wxs = [p[0] for p in world_pts]
        wys = [p[1] for p in world_pts]
        wzs = [p[2] for p in world_pts]
        report["groups"][mat] = {
            "shapes": [s.name.decode("latin-1") for s in member_shapes],
            "verts": len(m.positions),
            "tris": len(m.triangles),
            "mesh": f"{d}\\{f}",
            "world_bounds_m": {
                "x": [round(min(wxs), 4), round(max(wxs), 4)],
                "y": [round(min(wys), 4), round(max(wys), 4)],
                "z": [round(min(wzs), 4), round(max(wzs), 4)],
            },
        }

    new_children.insert(0, tgt)
    actor_rebind._set_children(t, parent, new_children)
    return HumanRebindResult(nifmod.serialize(t), meshes, report)


def read_sf_mesh_ba2(sf_data: str, rel_path: str) -> bytes:
    norm = rel_path.lower().replace("\\", "/")
    if not norm.startswith("meshes/"):
        norm = "meshes/" + norm
    for path in sorted(glob.glob(os.path.join(sf_data, "Starfield - Meshes*.ba2")), reverse=True):
        a = ba2.Ba2(path)
        i = a.find(norm)
        if i is not None:
            return a.read(i)
    raise FileNotFoundError(f"{norm} not found in Starfield - Meshes*.ba2 under {sf_data}")


def _resolve_raider_shape_materials(fo4_nif_bytes: bytes, src_rel: str) -> Dict[str, str]:
    fnf = nifmod.parse(fo4_nif_bytes)
    out: Dict[str, str] = {}
    sl = src_rel.lower()
    for s in nifmod.fo4_trishapes(fnf, placed=True):
        nm = s.name.decode("latin-1")
        nl = nm.lower()
        if "hand" in sl or "hand" in nl:
            out[nm] = EXISTING_FO4CORE_MATS["malehands"]
        elif "basemalebody" in nl or "body" in nl and "raider04" not in nl and "underarmor" not in nl:
            out[nm] = EXISTING_FO4CORE_MATS["malebody"]
        elif "underarmor" in sl or "underarmor" in nl:
            out[nm] = EXISTING_FO4CORE_MATS["raiderunderarmorm"]
        else:
            out[nm] = EXISTING_FO4CORE_MATS["raider04"]
    return out


def _resolve_preston_shape_materials(
    fo4_nif_bytes: bytes,
    conv: Optional[object],
) -> Dict[str, str]:
    fnf = nifmod.parse(fo4_nif_bytes)
    out: Dict[str, str] = {}
    for s in nifmod.fo4_trishapes(fo4_nif_bytes if isinstance(fo4_nif_bytes, nifmod.NifFile) else fnf, placed=True):
        nm = s.name.decode("latin-1")
        if "basemalebody" in nm.lower():
            out[nm] = EXISTING_FO4CORE_MATS["malebody"]
        elif conv is not None:
            mat = conv._shape_material(fnf, s)
            out[nm] = mat if mat else conv.neutral
        else:
            out[nm] = convert_static.PLACEHOLDER_MATERIAL
    return out


def stage_c5_looks(
    fo4_data: str,
    sf_data: str,
    staging: str,
    content_resources: Optional[str] = None,
    texconv: Optional[str] = None,
) -> dict:
    from fo4sf import pipeline

    if os.path.exists(staging) and os.listdir(staging):
        raise SystemExit(f"{staging} is not empty: pass a new or empty staging folder")
    parent = os.path.dirname(os.path.abspath(staging))
    os.makedirs(parent, exist_ok=True)
    partial = tempfile.mkdtemp(prefix=os.path.basename(os.path.abspath(staging)) + ".partial-", dir=parent)

    src = pipeline.Fo4Archives(fo4_data)
    conv = None
    if content_resources and texconv and os.path.isfile(content_resources) and os.path.isfile(texconv):
        conv = pipeline.Converter(src, partial, texconv, content_resources)

    sf_body_tpl = read_sf_mesh_ba2(sf_data, SF_BODY_TEMPLATE)
    sf_hat_tpl = read_sf_mesh_ba2(sf_data, SF_HAT_TEMPLATE)

    preston_body_inputs = []
    for rel in PRESTON_OUTFIT_SOURCES:
        raw = src.mesh(rel.replace("/", "\\"))
        if raw is None:
            raise FileNotFoundError(f"{rel} not found in {fo4_data}")
        preston_body_inputs.append((rel, raw, _resolve_preston_shape_materials(raw, conv)))

    preston_hat_inputs = []
    for rel in PRESTON_HAT_SOURCES:
        raw = src.mesh(rel.replace("/", "\\"))
        if raw is None:
            raise FileNotFoundError(f"{rel} not found in {fo4_data}")
        preston_hat_inputs.append((rel, raw, _resolve_preston_shape_materials(raw, conv)))

    raider_body_inputs = []
    for rel in RAIDER_OUTFIT_SOURCES:
        raw = src.mesh(rel.replace("/", "\\"))
        if raw is None:
            raise FileNotFoundError(f"{rel} not found in {fo4_data}")
        raider_body_inputs.append((rel, raw, _resolve_raider_shape_materials(raw, rel)))

    default_mat = conv.neutral if conv is not None else convert_static.PLACEHOLDER_MATERIAL
    preston_body_res = rebind_human_skin_attach(
        sf_body_tpl, preston_body_inputs, unit_scale=FO4_TO_SF_HUMAN_SCALE, weights_per_vertex=4, default_material=default_mat
    )
    preston_hat_res = rebind_human_skin_attach(
        sf_hat_tpl, preston_hat_inputs, unit_scale=FO4_TO_SF_HUMAN_SCALE, weights_per_vertex=1, default_material=default_mat
    )
    raider_body_res = rebind_human_skin_attach(
        sf_body_tpl,
        raider_body_inputs,
        unit_scale=FO4_TO_SF_HUMAN_SCALE,
        weights_per_vertex=4,
        default_material=EXISTING_FO4CORE_MATS["raider04"],
        skip_shapes=("BaseMaleBodyRaider:0",),
    )

    files: Dict[str, bytes] = {
        posixpath.join("meshes", PRESTON_OUTFIT_REL): preston_body_res.nif,
        posixpath.join("meshes", PRESTON_HAT_REL): preston_hat_res.nif,
        posixpath.join("meshes", RAIDER_OUTFIT_REL): raider_body_res.nif,
    }
    for res in (preston_body_res, preston_hat_res, raider_body_res):
        for d, f in res.meshes:
            files[posixpath.join("geometries", d, f"{f}.mesh")] = res.meshes[(d, f)]

    for rel, data in files.items():
        dst = os.path.join(partial, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as fh:
            fh.write(data)

    manifest = {
        "preston_outfit_model": PRESTON_OUTFIT_REL,
        "preston_hat_model": PRESTON_HAT_REL,
        "raider_outfit_model": RAIDER_OUTFIT_REL,
        "materials_converted_with_texconv": conv is not None,
        "existing_fo4core_materials": EXISTING_FO4CORE_MATS,
        "preston_outfit": preston_body_res.report,
        "preston_hat": preston_hat_res.report,
        "raider_outfit": raider_body_res.report,
        "written_nif_and_mesh_files": sorted(files),
    }
    with open(os.path.join(partial, "c5_actor_looks_report.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)

    if os.path.exists(staging):
        os.rmdir(staging)
    os.replace(partial, staging)
    verify_staged_c5_assets(staging, require_preston_mats=conv is not None)
    return manifest


def verify_staged_c5_assets(root_dir: str, require_preston_mats: bool = True) -> dict:
    """Verify that a staged directory (or bundle Data root) contains all 3 C5 NIFs, every referenced external
    geometries/<dir>/<file>.mesh, and every local fo4port .mat + .dds texture referenced by Preston's outfit/hat."""
    checked_nifs: List[str] = []
    checked_meshes: List[str] = []
    checked_mats: List[str] = []
    checked_textures: List[str] = []
    fo4core_mats = {v.lower().replace("/", "\\") for v in EXISTING_FO4CORE_MATS.values()}

    for nif_rel in (PRESTON_OUTFIT_REL, PRESTON_HAT_REL, RAIDER_OUTFIT_REL):
        nif_disk = os.path.join(root_dir, "meshes", *nif_rel.split("/"))
        if not os.path.isfile(nif_disk):
            raise FileNotFoundError(f"Missing staged C5 NIF: {nif_disk}")
        checked_nifs.append(posixpath.join("meshes", nif_rel))
        with open(nif_disk, "rb") as fh:
            nf = nifmod.parse(fh.read())
        for i in range(len(nf.blocks)):
            if nf.type_of(i) != "BSGeometry":
                continue
            g = sfnif.parse_bsgeometry(nf.blocks[i])
            if g.meshes[0] is None:
                raise ValueError(f"{nif_rel} BSGeometry[{i}] lacks LOD0 MeshRef")
            m_rel = g.meshes[0].path.decode("latin-1").replace("\\", "/")
            m_disk = os.path.join(root_dir, "geometries", *m_rel.split("/")) + ".mesh"
            if not os.path.isfile(m_disk):
                raise FileNotFoundError(f"{nif_rel} references missing external mesh: {m_disk}")
            with open(m_disk, "rb") as mfh:
                sm = sfmesh.parse(mfh.read())
            if sm.weights_per_vertex < 1 or len(sm.tail) != 0:
                raise ValueError(f"Invalid BSMeshData in {m_disk}: wpv={sm.weights_per_vertex}, tail={len(sm.tail)}")
            checked_meshes.append(posixpath.join("geometries", f"{m_rel}.mesh"))

            if g.shader >= 0:
                sidx, = struct.unpack_from("<i", nf.blocks[g.shader], 0)
                mat_rel_bs = nf.strings[sidx].decode("latin-1").replace("/", "\\")
                if mat_rel_bs.lower() in fo4core_mats:
                    continue
                if mat_rel_bs == convert_static.PLACEHOLDER_MATERIAL and not require_preston_mats:
                    continue
                mat_rel = mat_rel_bs.replace("\\", "/")
                mat_disk = os.path.join(root_dir, *mat_rel.split("/"))
                if not os.path.isfile(mat_disk):
                    raise FileNotFoundError(f"{nif_rel} references missing material: {mat_disk}")
                checked_mats.append(mat_rel)
                with open(mat_disk, encoding="utf-8") as mat_fh:
                    mat_json = json.load(mat_fh)
                # Verify any local textures/fo4port/*.dds referenced inside the .mat exist on disk
                mat_text = json.dumps(mat_json)
                for tok in set(mat_text.replace("\\\\", "/").replace("\\", "/").split('"')):
                    tok_norm = tok[5:] if tok.lower().startswith("data/") else tok
                    tl = tok_norm.lower()
                    if tl.startswith("textures/fo4port/") and tl.endswith(".dds"):
                        tex_disk = os.path.join(root_dir, *tok_norm.split("/"))
                        if not os.path.isfile(tex_disk):
                            raise FileNotFoundError(f"{mat_rel} references missing texture: {tex_disk}")
                        checked_textures.append(tok_norm)

    return {
        "nifs": sorted(set(checked_nifs)),
        "meshes": sorted(set(checked_meshes)),
        "local_mats": sorted(set(checked_mats)),
        "local_textures": sorted(set(checked_textures)),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--verify-only", default=None, help="Verify an already-staged directory or bundle Data root and exit")
    p.add_argument("--fo4-data", default=None)
    p.add_argument("--sf-data", default=None)
    p.add_argument("--staging", default=None)
    p.add_argument("--content-resources", default=None)
    p.add_argument("--texconv", default=None)
    a = p.parse_args(argv)
    if a.verify_only:
        res = verify_staged_c5_assets(a.verify_only, require_preston_mats=True)
        print(json.dumps(res, indent=2))
        return 0
    if not (a.fo4_data and a.sf_data and a.staging):
        p.error("--fo4-data, --sf-data, and --staging are required unless --verify-only is passed")
    manifest = stage_c5_looks(a.fo4_data, a.sf_data, a.staging, a.content_resources, a.texconv)
    print(json.dumps({
        "preston_outfit_model": manifest["preston_outfit_model"],
        "preston_hat_model": manifest["preston_hat_model"],
        "raider_outfit_model": manifest["raider_outfit_model"],
        "materials_converted_with_texconv": manifest["materials_converted_with_texconv"],
        "preston_groups": manifest["preston_outfit"]["groups"],
        "preston_hat_groups": manifest["preston_hat"]["groups"],
        "raider_groups": manifest["raider_outfit"]["groups"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
