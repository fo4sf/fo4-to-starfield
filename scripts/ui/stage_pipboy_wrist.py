"""Stage Fallout 4 Pip-Boy 3000 wrist models onto Starfield's non-occluded spacesuit-watch slot (Round 15 Wave A Item 1).

Usage:
  python scripts/ui/stage_pipboy_wrist.py --fo4-data "<Fallout 4/Data>" --sf-data "<Starfield/Data>"
      --staging "<new empty dir>" [--content-resources "<ContentResources.zip>"] [--texconv "<texconv.exe>"]
  python scripts/ui/stage_pipboy_wrist.py --verify-only "<staged dir>"

Splits Fallout 4's 1st-person (pipboy.nif) and 3rd-person (pipboylowplayer.nif) Pip-Boy into two separate ARMA-ready
model families anchored to Starfield's spacesuit ChronoWatch template (spacesuit_suitzero_chronowatch_{m,f}.nif):
  - Housing NIFs: meshes/fo4port/pipboy/pipboy_wrist_housing_{m,f,1st}.nif  (Screen* & TapREF excluded)
  - Screen NIFs:  meshes/fo4port/pipboy/pipboy_wrist_screen_{m,f,1st}.nif   (Screen:0 only -> pipboy_screen_2d.mat)

All outputs bind rigidly (100% weight) to L_Wrist_Twist2 (slot 3) in the 4-bone SkinAttach table
['L_Forearm', 'L_Wrist_Twist', 'L_Wrist_Twist1', 'L_Wrist_Twist2'], so equipping clothes/spacesuits in slots 3/8/35
never occludes the wrist Pip-Boy and 3D RTT later swaps only the screen material/NIF seam without rebuilding housing.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field, replace
import glob
import json
import math
import os
import posixpath
import shutil
import struct
import sys
import tempfile
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
if os.path.join(REPO, "src") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "src"))

from fo4sf import actor_rebind, ba2, convert_material as cm, convert_static, fo4skin, nif as nifmod, pipeline, sfmesh, sfnif, textures  # noqa: E402

SF_WATCH_TEMPLATE_M = "meshes/clothes/spacesuit_suitzero/spacesuit_suitzero_chronowatch_m.nif"
SF_WATCH_TEMPLATE_F = "meshes/clothes/spacesuit_suitzero/spacesuit_suitzero_chronowatch_f.nif"

FO4_PIPBOY_1ST_SOURCE = "meshes/pipboy/characterassets/pipboy.nif"
FO4_PIPBOY_3RD_SOURCE = "meshes/pipboy/characterassets/pipboylowplayer.nif"

HOUSING_NIF_M = "meshes/fo4port/pipboy/pipboy_wrist_housing_m.nif"
HOUSING_NIF_F = "meshes/fo4port/pipboy/pipboy_wrist_housing_f.nif"
HOUSING_NIF_1ST = "meshes/fo4port/pipboy/pipboy_wrist_housing_1st.nif"

SCREEN_NIF_M = "meshes/fo4port/pipboy/pipboy_wrist_screen_m.nif"
SCREEN_NIF_F = "meshes/fo4port/pipboy/pipboy_wrist_screen_f.nif"
SCREEN_NIF_1ST = "meshes/fo4port/pipboy/pipboy_wrist_screen_1st.nif"

ALL_WRIST_NIFS = (
    HOUSING_NIF_M,
    HOUSING_NIF_F,
    HOUSING_NIF_1ST,
    SCREEN_NIF_M,
    SCREEN_NIF_F,
    SCREEN_NIF_1ST,
)

HOUSING_NIFS = (HOUSING_NIF_M, HOUSING_NIF_F, HOUSING_NIF_1ST)
SCREEN_NIFS = (SCREEN_NIF_M, SCREEN_NIF_F, SCREEN_NIF_1ST)

SCREEN_MAT_REL = "materials/fo4port/pipboy/pipboy_screen_2d.mat"
SCREEN_MAT_GAME = "materials\\fo4port\\pipboy\\pipboy_screen_2d.mat"
SCREEN_TEX_PREFIX = "textures/fo4port/pipboy/pipboy_screen_2d"
SCREEN_BGSM_PATH = "Materials\\AnimObjects\\PipBoy\\PipBoyScreen.BGSM"

EXPECTED_SKIN_ATTACH = ("L_Forearm", "L_Wrist_Twist", "L_Wrist_Twist1", "L_Wrist_Twist2")
WRIST_DOMINANT_BONE = "L_Wrist_Twist2"
WRIST_DOMINANT_SLOT = 3
WEIGHTS_PER_VERTEX = 4

# Measured FO4 inner cuff center (PipboyBody_mesh:8 + PipboyBack_mesh:8 in FO4 units)
FO4_CUFF_CENTER = (5.810, 0.014, -0.106)
# Canonical FO4 -> Starfield HumanRace scale (matches stage_c5_actor_looks.py)
FO4_TO_SF_HUMAN_SCALE = 1.63227 / 120.84
FO4_TO_SF_WRIST_SCALE_M = FO4_TO_SF_HUMAN_SCALE
FO4_TO_SF_WRIST_SCALE_F = FO4_TO_SF_HUMAN_SCALE * 0.94

# Target wrist-cuff centerline in Starfield L_Wrist_Twist2 bone-local space (metres),
# aligned with spacesuit_suitzero_chronowatch_{m,f}.nif cuff bounds.
WRIST_CENTER_BONE_M = (-0.050, 0.005, 0.002)
WRIST_CENTER_BONE_F = (-0.054, 0.005, 0.002)

# Pure Ry(180 deg) rotation (det = +1): maps FO4 (-X hand / +U, +Y pinky / V=0 top, -Z screen normal)
# onto Starfield L_Wrist_Twist2 (+X hand, +Y pinky, +Z dorsal wrist outward normal).
RY_180 = (-1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, -1.0)

TEXCONV_CANDIDATES = (
    r"C:\Modding\tools\xedit\Edit Scripts\Texconvx64.exe",
    r"C:\Modding\tools\xedit\Edit Scripts\Texconv.exe",
    r"C:\Modding\3.7.5.3\Tools\texconv.exe",
    r"C:\Modding\3.7.5.3\cli\Tools\texconv.exe",
)


@dataclass
class WristBuildResult:
    nif: bytes
    meshes: Dict[Tuple[str, str], bytes]
    report: dict = field(default_factory=dict)


def parse_skin_attach(blk: bytes) -> Tuple[int, List[str]]:
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


def _mul_mat3(a: Sequence[float], b: Sequence[float]) -> Tuple[float, ...]:
    return tuple(
        sum(a[3 * r + k] * b[3 * k + c] for k in range(3))
        for r in range(3)
        for c in range(3)
    )


def _rot_vec(r: Sequence[float], v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    x = r[0] * v[0] + r[1] * v[1] + r[2] * v[2]
    y = r[3] * v[0] + r[4] * v[1] + r[5] * v[2]
    z = r[6] * v[0] + r[7] * v[1] + r[8] * v[2]
    ln = math.sqrt(x * x + y * y + z * z) or 1.0
    return (x / ln, y / ln, z / ln)


def is_screen_shape(name: str) -> bool:
    return name.strip().lower().startswith("screen")


def is_primary_screen_shape(name: str) -> bool:
    return name.strip().lower() == "screen:0"


def is_housing_shape(name: str) -> bool:
    low = name.strip().lower()
    return not low.startswith("screen") and not low.startswith("tapref")


def transform_fo4_to_wrist_bone(
    pt_fo4_root: Tuple[float, float, float],
    cuff_center_fo4: Tuple[float, float, float] = FO4_CUFF_CENTER,
    cuff_center_bone: Tuple[float, float, float] = WRIST_CENTER_BONE_M,
    unit_scale: float = FO4_TO_SF_WRIST_SCALE_M,
) -> Tuple[float, float, float]:
    """Map a point from FO4 NIF-root space into Starfield L_Wrist_Twist2 bone-local space."""
    dx = pt_fo4_root[0] - cuff_center_fo4[0]
    dy = pt_fo4_root[1] - cuff_center_fo4[1]
    dz = pt_fo4_root[2] - cuff_center_fo4[2]
    # Ry(180 deg) = diag(-1, +1, -1)
    rx = -dx * unit_scale + cuff_center_bone[0]
    ry = dy * unit_scale + cuff_center_bone[1]
    rz = -dz * unit_scale + cuff_center_bone[2]
    return (rx, ry, rz)


def rebind_pipboy_to_wrist(
    template_nif: bytes,
    fo4_nif: bytes,
    shape_predicate: Callable[[str], bool],
    material_for_shape: Callable[[nifmod.NifFile, object], Optional[str]],
    cuff_center_bone: Tuple[float, float, float] = WRIST_CENTER_BONE_M,
    unit_scale: float = FO4_TO_SF_WRIST_SCALE_M,
    cuff_center_fo4: Tuple[float, float, float] = FO4_CUFF_CENTER,
    group_prefix: str = "FO4Wrist",
) -> WristBuildResult:
    """Rebind selected FO4 Pip-Boy shapes onto Starfield's 4-bone ChronoWatch wrist template."""
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
    if tuple(slot_names) != EXPECTED_SKIN_ATTACH:
        raise nifmod.NifError(f"unexpected ChronoWatch SkinAttach bones: {slot_names}")
    root, data, bones, tail = actor_rebind.read_instance(t.blocks[g0.skin])
    if len(bones) != len(slot_names):
        raise nifmod.NifError(f"SkinAttach count {len(slot_names)} != BSSkin::Instance count {len(bones)}")

    parents = {i: actor_rebind._raw_children(t, i) for i in range(len(t.blocks)) if t.type_of(i).endswith("Node")}
    parent = next((p for p, ch in parents.items() if tgt in ch), None)
    if parent is None:
        raise nifmod.NifError(f"template BSGeometry {tgt} has no parent node")

    bone_data0 = t.blocks[data]
    skin_to_bone3 = actor_rebind._skin_to_bone(bone_data0, WRIST_DOMINANT_SLOT)
    bone3_to_mesh = invert_rigid(skin_to_bone3)
    _, bone3_to_mesh_rot, _ = bone3_to_mesh
    fo4_root_to_mesh_rot = _mul_mat3(bone3_to_mesh_rot, RY_180)

    src = nifmod.parse(fo4_nif)
    all_shapes = [s for s in nifmod.fo4_trishapes(src, placed=True) if s.positions and s.triangles]
    selected = [s for s in all_shapes if shape_predicate(s.name.decode("latin-1", "replace"))]
    if not selected:
        raise nifmod.NifError("no FO4 Pip-Boy shapes matched shape_predicate")

    groups: Dict[str, List[object]] = {}
    for s in selected:
        mat = material_for_shape(src, s)
        if not mat:
            continue
        r = s.rotation
        tr = s.translation
        sc = s.scale

        root_pts = [
            (
                sc * (r[0] * x + r[1] * y + r[2] * z) + tr[0],
                sc * (r[3] * x + r[4] * y + r[5] * z) + tr[1],
                sc * (r[6] * x + r[7] * y + r[8] * z) + tr[2],
            )
            for x, y, z in s.positions
        ]
        bone_pts = [
            transform_fo4_to_wrist_bone(pt, cuff_center_fo4, cuff_center_bone, unit_scale)
            for pt in root_pts
        ]
        mesh_pts = [fo4skin.apply(bone3_to_mesh, bp) for bp in bone_pts]

        shape_to_mesh_rot = _mul_mat3(fo4_root_to_mesh_rot, r)
        mesh_nrm = [_rot_vec(shape_to_mesh_rot, n) for n in s.normals] if s.normals else []
        if s.tangents and s.normals and s.uvs:
            signs = convert_static.tangent_signs(s.positions, s.uvs, s.normals, s.tangents, s.triangles)
            mesh_tan = []
            for tan, sig in zip(s.tangents, signs):
                rtan = _rot_vec(shape_to_mesh_rot, tan)
                mesh_tan.append((*rtan, float(sig)))
        else:
            mesh_tan = []

        adj_shape = replace(
            s,
            positions=mesh_pts,
            normals=mesh_nrm,
            tangents=mesh_tan,
            colors=[],
            translation=(0.0, 0.0, 0.0),
            rotation=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
            scale=1.0,
            skinned=False,
        )
        groups.setdefault(mat, []).append(adj_shape)

    if not groups:
        raise nifmod.NifError("no FO4 Pip-Boy shapes remained after material filtering")

    meshes: Dict[Tuple[str, str], bytes] = {}
    new_children = [c for c in parents[parent] if c not in geoms]
    for node, ch in parents.items():
        if node != parent and any(c in geoms for c in ch):
            actor_rebind._set_children(t, node, [c for c in ch if c not in geoms])

    all_bone_pts: List[Tuple[float, float, float]] = []
    all_mesh_pts: List[Tuple[float, float, float]] = []
    group_reports: Dict[str, dict] = {}

    for k, (mat, member_shapes) in enumerate(groups.items()):
        merged = actor_rebind._merge(member_shapes)
        m = convert_static.shape_to_mesh(merged, unit_scale=1.0)
        m.weights_per_vertex = WEIGHTS_PER_VERTEX
        vcount = len(m.positions)
        weights: List[Tuple[int, int]] = []
        for _ in range(vcount):
            weights.append((WRIST_DOMINANT_SLOT, actor_rebind.FULL_WEIGHT))
            for _ in range(WEIGHTS_PER_VERTEX - 1):
                weights.append((0, 0))
        m.weights = weights

        mesh_bytes = sfmesh.serialize(m)
        d, f = convert_static.mesh_file_path(mesh_bytes)
        meshes[(d, f)] = mesh_bytes

        pts = [sfmesh.decode_position(p, m.scale) for p in m.positions]
        bpts = [fo4skin.apply(skin_to_bone3, p) for p in pts]
        all_mesh_pts.extend(pts)
        all_bone_pts.extend(bpts)
        sphere, box = sfnif.bounds_from_points(pts)
        bone3_sphere = actor_rebind._sphere(bpts)
        spheres = {sl: bone3_sphere for sl in range(len(slot_names)) if bone3_sphere is not None}

        flags = g0.meshes[0].flags if g0.meshes[0] else 0x40
        g = replace(
            g0,
            name_idx=t.string_index(f"{group_prefix}_{k}".encode("latin-1")),
            sphere=sphere,
            box=box,
            meshes=[
                sfnif.MeshRef(3 * len(m.triangles), len(m.positions), flags, f"{d}\\{f}".encode("latin-1")),
                None,
                None,
                None,
            ],
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
        t.blocks[si] = struct.pack("<iIi", t.string_index(mat.encode("latin-1")), 0, -1)
        t.blocks[bi] = actor_rebind.write_instance(root, di, bones, tail)
        t.blocks[di] = actor_rebind._bone_data_with_spheres(bone_data0, spheres)
        t.blocks[gi] = sfnif.build_bsgeometry(g)

        group_reports[mat] = {
            "shapes": [ms.name.decode("latin-1", "replace") for ms in member_shapes],
            "verts": len(m.positions),
            "tris": len(m.triangles),
            "mesh": f"{d}\\{f}",
            "bone_bounds_m": _bounds_dict(bpts),
            "mesh_bounds_m": _bounds_dict(pts),
        }

    new_children.insert(0, tgt)
    actor_rebind._set_children(t, parent, new_children)
    report = {
        "skin_attach_bones": list(slot_names),
        "dominant_bone": WRIST_DOMINANT_BONE,
        "dominant_slot": WRIST_DOMINANT_SLOT,
        "weights_per_vertex": WEIGHTS_PER_VERTEX,
        "total_verts": len(all_bone_pts),
        "bone_bounds_m": _bounds_dict(all_bone_pts) if all_bone_pts else None,
        "mesh_bounds_m": _bounds_dict(all_mesh_pts) if all_mesh_pts else None,
        "groups": group_reports,
    }
    return WristBuildResult(nifmod.serialize(t), meshes, report)


def _bounds_dict(pts: Sequence[Tuple[float, float, float]]) -> dict:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    zs = [p[2] for p in pts]
    return {
        "x": [round(min(xs), 4), round(max(xs), 4)],
        "y": [round(min(ys), 4), round(max(ys), 4)],
        "z": [round(min(zs), 4), round(max(zs), 4)],
    }


def read_sf_mesh_ba2(sf_data: str, rel_path: str) -> bytes:
    norm = rel_path.lower().replace("\\", "/")
    if not norm.startswith("meshes/"):
        norm = "meshes/" + norm
    for path in sorted(glob.glob(os.path.join(sf_data, "Starfield - Meshes*.ba2")), reverse=True):
        arc = ba2.Ba2(path)
        idx = arc.find(norm)
        if idx is not None:
            return arc.read(idx)
    raise FileNotFoundError(f"{norm} not found in Starfield - Meshes*.ba2 under {sf_data}")


def find_texconv(explicit: Optional[str] = None) -> str:
    if explicit:
        if os.path.isfile(explicit):
            return explicit
        raise FileNotFoundError(f"--texconv not found: {explicit}")
    for cand in TEXCONV_CANDIDATES:
        if os.path.isfile(cand):
            return cand
    found = shutil.which("texconv") or shutil.which("texconv.exe") or shutil.which("Texconvx64.exe")
    if found:
        return found
    raise FileNotFoundError("texconv.exe not found; pass --texconv <path>")


def find_content_resources(sf_data: str, explicit: Optional[str] = None) -> str:
    if explicit:
        if os.path.isfile(explicit):
            return explicit
        raise FileNotFoundError(f"--content-resources not found: {explicit}")
    sf_root = os.path.dirname(os.path.abspath(sf_data))
    cand = os.path.join(sf_root, "Tools", "ContentResources.zip")
    if os.path.isfile(cand):
        return cand
    raise FileNotFoundError(f"ContentResources.zip not found under {sf_root}\\Tools; pass --content-resources")


def stage_screen_material_2d(
    src: pipeline.Fo4Archives,
    staging_root: str,
    texconv_exe: str,
    template_mat: dict,
) -> str:
    """Convert PipBoyScreen.BGSM into swappable materials/fo4port/pipboy/pipboy_screen_2d.mat + DDS files."""
    import numpy as np

    raw_bgsm = src.material(SCREEN_BGSM_PATH)
    if raw_bgsm is not None:
        bgsm = cm.parse_bgsm(raw_bgsm)
        diffuse = bgsm.diffuse or "AnimObjects/PipBoy/PipBoyScreen_d.dds"
        normal = bgsm.normal or "Shared/FlatFlat_n.dds"
    else:
        diffuse = "AnimObjects/PipBoy/PipBoyScreen_d.dds"
        normal = "Shared/FlatFlat_n.dds"

    d_bytes = src.texture(diffuse)
    n_bytes = src.texture(normal)
    if d_bytes is None:
        raise FileNotFoundError(f"missing FO4 screen diffuse texture: {diffuse}")

    out_paths: Dict[str, str] = {}
    with tempfile.TemporaryDirectory() as tmp:
        d_in = os.path.join(tmp, "d.dds")
        with open(d_in, "wb") as fh:
            fh.write(d_bytes)
        textures.texconv(texconv_exe, d_in, tmp, "BC1_UNORM_SRGB", ("-srgbi",))

        if n_bytes is not None:
            nr, ng = pipeline._plane_pair(n_bytes, tmp, texconv_exe)
        else:
            nr = np.full((4, 4), 128, dtype=np.uint8)
            ng = np.full((4, 4), 128, dtype=np.uint8)
        n_in = os.path.join(tmp, "n_in.dds")
        textures.write_rg8_snorm(n_in, nr, ng)
        textures.texconv(texconv_exe, n_in, tmp, "BC5_SNORM")

        r_in = os.path.join(tmp, "r_in.dds")
        textures.write_r8(r_in, np.full((4, 4), 190, dtype=np.uint8))
        textures.texconv(texconv_exe, r_in, tmp, "BC4_UNORM")

        for kind, fn in (("color", "d.dds"), ("normal", "n_in.dds"), ("rough", "r_in.dds")):
            dst = os.path.join(staging_root, *f"{SCREEN_TEX_PREFIX}_{kind}.dds".split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(os.path.join(tmp, fn), "rb") as fh:
                pipeline.write_staged(dst, fh.read())
            out_paths[kind] = cm.game_path(f"{SCREEN_TEX_PREFIX}_{kind}.dds")

    mat = cm.build_mat(
        template_mat,
        "FO4Port_PipboyScreen2D",
        out_paths["color"],
        out_paths["normal"],
        out_paths["rough"],
        metalness=0.0,
    )
    mat_disk = os.path.join(staging_root, *SCREEN_MAT_REL.split("/"))
    os.makedirs(os.path.dirname(mat_disk), exist_ok=True)
    pipeline.write_staged(mat_disk, cm.dump_mat(mat).encode("utf-8"))
    return SCREEN_MAT_GAME


def stage_pipboy_wrist(
    fo4_data: str,
    sf_data: str,
    staging: str,
    content_resources: Optional[str] = None,
    texconv: Optional[str] = None,
) -> dict:
    """Stage split Pip-Boy housing + screen wrist NIFs, meshes, materials, and textures into `staging`."""
    pipeline.refuse_unsafe_output_dir(staging, "--staging")

    if os.path.exists(staging) and os.listdir(staging):
        raise SystemExit(f"{staging} is not empty: pass a new or empty staging folder")

    texconv_exe = find_texconv(texconv)
    cr_zip = find_content_resources(sf_data, content_resources)

    parent = os.path.dirname(os.path.abspath(staging))
    os.makedirs(parent, exist_ok=True)
    partial = tempfile.mkdtemp(prefix=os.path.basename(os.path.abspath(staging)) + ".partial-", dir=parent)

    try:
        src = pipeline.Fo4Archives(fo4_data)
        conv = pipeline.Converter(src, partial, texconv_exe, cr_zip, prefix="fo4port")

        sf_tpl_m = read_sf_mesh_ba2(sf_data, SF_WATCH_TEMPLATE_M)
        sf_tpl_f = read_sf_mesh_ba2(sf_data, SF_WATCH_TEMPLATE_F)
        fo4_1st = src.mesh(FO4_PIPBOY_1ST_SOURCE)
        fo4_3rd = src.mesh(FO4_PIPBOY_3RD_SOURCE)
        if fo4_1st is None:
            raise FileNotFoundError(f"{FO4_PIPBOY_1ST_SOURCE} not found in {fo4_data}")
        if fo4_3rd is None:
            raise FileNotFoundError(f"{FO4_PIPBOY_3RD_SOURCE} not found in {fo4_data}")

        screen_mat_game = stage_screen_material_2d(src, partial, texconv_exe, conv.template_mat)

        def housing_mat(nf_src: nifmod.NifFile, shape) -> Optional[str]:
            return conv._shape_material(nf_src, shape)

        def screen_mat(_nf_src: nifmod.NifFile, _shape) -> Optional[str]:
            return screen_mat_game

        builds = {
            HOUSING_NIF_M: rebind_pipboy_to_wrist(
                sf_tpl_m, fo4_3rd, is_housing_shape, housing_mat,
                cuff_center_bone=WRIST_CENTER_BONE_M, unit_scale=FO4_TO_SF_WRIST_SCALE_M,
                group_prefix="FO4WristHousingM",
            ),
            HOUSING_NIF_F: rebind_pipboy_to_wrist(
                sf_tpl_f, fo4_3rd, is_housing_shape, housing_mat,
                cuff_center_bone=WRIST_CENTER_BONE_F, unit_scale=FO4_TO_SF_WRIST_SCALE_F,
                group_prefix="FO4WristHousingF",
            ),
            HOUSING_NIF_1ST: rebind_pipboy_to_wrist(
                sf_tpl_m, fo4_1st, is_housing_shape, housing_mat,
                cuff_center_bone=WRIST_CENTER_BONE_M, unit_scale=FO4_TO_SF_WRIST_SCALE_M,
                group_prefix="FO4WristHousing1st",
            ),
            SCREEN_NIF_M: rebind_pipboy_to_wrist(
                sf_tpl_m, fo4_3rd, is_primary_screen_shape, screen_mat,
                cuff_center_bone=WRIST_CENTER_BONE_M, unit_scale=FO4_TO_SF_WRIST_SCALE_M,
                group_prefix="FO4WristScreenM",
            ),
            SCREEN_NIF_F: rebind_pipboy_to_wrist(
                sf_tpl_f, fo4_3rd, is_primary_screen_shape, screen_mat,
                cuff_center_bone=WRIST_CENTER_BONE_F, unit_scale=FO4_TO_SF_WRIST_SCALE_F,
                group_prefix="FO4WristScreenF",
            ),
            SCREEN_NIF_1ST: rebind_pipboy_to_wrist(
                sf_tpl_m, fo4_1st, is_primary_screen_shape, screen_mat,
                cuff_center_bone=WRIST_CENTER_BONE_M, unit_scale=FO4_TO_SF_WRIST_SCALE_M,
                group_prefix="FO4WristScreen1st",
            ),
        }

        written_files: Dict[str, bytes] = {}
        for nif_rel, res in builds.items():
            written_files[nif_rel] = res.nif
            for d, f in res.meshes:
                written_files[posixpath.join("geometries", d, f"{f}.mesh")] = res.meshes[(d, f)]

        for rel, data in written_files.items():
            dst = os.path.join(partial, *rel.split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            pipeline.write_staged(dst, data)

        manifest = {
            "screen_material": SCREEN_MAT_REL,
            "skin_attach_bones": list(EXPECTED_SKIN_ATTACH),
            "dominant_bone": WRIST_DOMINANT_BONE,
            "converter_stats": conv.stats,
            "material_errors": conv.material_errors,
            "nifs": {rel: res.report for rel, res in builds.items()},
            "written_nif_and_mesh_files": sorted(written_files),
        }
        report_path = os.path.join(partial, "pipboy_wrist_report.json")
        pipeline.write_staged(report_path, json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"))

        if os.path.exists(staging):
            os.rmdir(staging)
        os.replace(partial, staging)
    except Exception:
        shutil.rmtree(partial, ignore_errors=True)
        raise

    verified = verify_staged_pipboy_wrist(staging)
    manifest["verified"] = verified
    return manifest


def verify_staged_pipboy_wrist(root_dir: str) -> dict:
    """Verify all 6 wrist NIFs, external .mesh weights/bboxes, SkinAttach 4-bone layout, materials, and DDS files."""
    if not os.path.isdir(root_dir):
        raise FileNotFoundError(f"staged directory not found: {root_dir}")

    screen_mat_disk = os.path.join(root_dir, *SCREEN_MAT_REL.split("/"))
    if not os.path.isfile(screen_mat_disk):
        raise FileNotFoundError(f"missing swappable screen material: {screen_mat_disk}")

    checked_nifs: List[str] = []
    checked_meshes: List[str] = []
    checked_mats: List[str] = []
    checked_textures: List[str] = []
    nif_summaries: Dict[str, dict] = {}

    for nif_rel in ALL_WRIST_NIFS:
        is_screen_nif = nif_rel in SCREEN_NIFS
        nif_disk = os.path.join(root_dir, *nif_rel.split("/"))
        if not os.path.isfile(nif_disk):
            raise FileNotFoundError(f"missing wrist NIF: {nif_disk}")
        checked_nifs.append(nif_rel)
        with open(nif_disk, "rb") as fh:
            nf = nifmod.parse(fh.read())
        if nf.bs_version not in (173, 175):
            raise ValueError(f"{nif_rel}: expected bs_version 173 or 175, got {nf.bs_version}")

        geom_indices = [i for i in range(len(nf.blocks)) if nf.type_of(i) == "BSGeometry"]
        if not geom_indices:
            raise ValueError(f"{nif_rel}: zero BSGeometry blocks")
        if is_screen_nif and len(geom_indices) != 1:
            raise ValueError(f"{nif_rel}: screen NIF must have exactly 1 BSGeometry, found {len(geom_indices)}")

        nif_bone_pts: List[Tuple[float, float, float]] = []
        nif_mesh_pts: List[Tuple[float, float, float]] = []
        nif_mats: List[str] = []
        nif_bones_count = 0

        for gi in geom_indices:
            g = sfnif.parse_bsgeometry(nf.blocks[gi])
            gname = nf.strings[g.name_idx].decode("latin-1", "replace") if 0 <= g.name_idx < len(nf.strings) else ""
            if not is_screen_nif and "screen" in gname.lower():
                raise ValueError(f"{nif_rel}: housing NIF contains screen BSGeometry {gname!r}")

            sa_ref = next((e for e in g.extra_refs if nf.type_of(e) == "SkinAttach"), None)
            if sa_ref is None:
                raise ValueError(f"{nif_rel} BSGeometry[{gi}] missing SkinAttach")
            _, s_bones = parse_skin_attach(nf.blocks[sa_ref])
            if tuple(s_bones) != EXPECTED_SKIN_ATTACH:
                raise ValueError(f"{nif_rel} BSGeometry[{gi}] SkinAttach {s_bones} != {list(EXPECTED_SKIN_ATTACH)}")
            nif_bones_count = len(s_bones)

            if g.skin < 0 or nf.type_of(g.skin) != "BSSkin::Instance":
                raise ValueError(f"{nif_rel} BSGeometry[{gi}] missing BSSkin::Instance")
            _root, bdata_ref, inst_bones, _tail = actor_rebind.read_instance(nf.blocks[g.skin])
            if len(inst_bones) != len(EXPECTED_SKIN_ATTACH) or any(b != -1 for b in inst_bones):
                raise ValueError(f"{nif_rel} BSGeometry[{gi}] BSSkin::Instance bones {inst_bones} != [-1,-1,-1,-1]")
            if bdata_ref < 0 or nf.type_of(bdata_ref) != "BSSkin::BoneData":
                raise ValueError(f"{nif_rel} BSGeometry[{gi}] missing BSSkin::BoneData")
            bd_count, = struct.unpack_from("<I", nf.blocks[bdata_ref], 0)
            if bd_count != len(EXPECTED_SKIN_ATTACH):
                raise ValueError(f"{nif_rel} BSSkin::BoneData count {bd_count} != {len(EXPECTED_SKIN_ATTACH)}")
            skin_to_bone3 = actor_rebind._skin_to_bone(nf.blocks[bdata_ref], WRIST_DOMINANT_SLOT)

            if g.meshes[0] is None:
                raise ValueError(f"{nif_rel} BSGeometry[{gi}] missing LOD0 MeshRef")
            m_rel = g.meshes[0].path.decode("latin-1").replace("\\", "/")
            m_disk = os.path.join(root_dir, "geometries", *m_rel.split("/")) + ".mesh"
            if not os.path.isfile(m_disk):
                raise FileNotFoundError(f"{nif_rel} references missing external mesh: {m_disk}")
            with open(m_disk, "rb") as mfh:
                sm = sfmesh.parse(mfh.read())
            if sm.weights_per_vertex != WEIGHTS_PER_VERTEX or len(sm.tail) != 0:
                raise ValueError(f"{m_disk}: invalid wpv={sm.weights_per_vertex} tail={len(sm.tail)}")
            if len(sm.positions) != g.meshes[0].num_verts or len(sm.triangles) * 3 != g.meshes[0].indices_size:
                raise ValueError(f"{nif_rel} BSGeometry[{gi}] mesh header count mismatch")
            # Verify dominant L_Wrist_Twist2 weight on every vertex
            for vi in range(len(sm.positions)):
                row = [sm.weights[vi * sm.weights_per_vertex + j] for j in range(sm.weights_per_vertex)]
                dom_slot, dom_w = max(row, key=lambda pair: pair[1])
                if dom_slot != WRIST_DOMINANT_SLOT or dom_w == 0:
                    raise ValueError(f"{m_disk}: vertex {vi} dominant slot {dom_slot} != {WRIST_DOMINANT_SLOT}")
            checked_meshes.append(posixpath.join("geometries", f"{m_rel}.mesh"))

            pts = [sfmesh.decode_position(p, sm.scale) for p in sm.positions]
            nif_mesh_pts.extend(pts)
            nif_bone_pts.extend(fo4skin.apply(skin_to_bone3, p) for p in pts)

            if g.shader < 0 or nf.type_of(g.shader) != "BSLightingShaderProperty":
                raise ValueError(f"{nif_rel} BSGeometry[{gi}] missing BSLightingShaderProperty")
            sidx, = struct.unpack_from("<i", nf.blocks[g.shader], 0)
            mat_bs = nf.strings[sidx].decode("latin-1").replace("/", "\\")
            mat_rel = mat_bs.replace("\\", "/")
            if is_screen_nif and mat_rel.lower() != SCREEN_MAT_REL:
                raise ValueError(f"{nif_rel}: screen NIF must bind {SCREEN_MAT_REL}, got {mat_rel}")
            if not is_screen_nif and mat_rel.lower() == SCREEN_MAT_REL:
                raise ValueError(f"{nif_rel}: housing NIF must not bind {SCREEN_MAT_REL}")

            mat_id_ref = next(
                (e for e in g.extra_refs if nf.type_of(e) == "NiIntegerExtraData" and actor_rebind._name(nf, e) == "MaterialID"),
                None,
            )
            if mat_id_ref is None:
                raise ValueError(f"{nif_rel} BSGeometry[{gi}] missing MaterialID NiIntegerExtraData")
            _, got_crc = struct.unpack_from("<iI", nf.blocks[mat_id_ref], 0)
            want_crc = sfnif.material_id(mat_bs)
            if got_crc != want_crc:
                raise ValueError(f"{nif_rel} BSGeometry[{gi}] MaterialID 0x{got_crc:08X} != 0x{want_crc:08X}")

            mat_disk = os.path.join(root_dir, *mat_rel.split("/"))
            if not os.path.isfile(mat_disk):
                raise FileNotFoundError(f"{nif_rel} references missing material: {mat_disk}")
            checked_mats.append(mat_rel)
            nif_mats.append(mat_rel)

            with open(mat_disk, encoding="utf-8") as mat_fh:
                mat_json = json.load(mat_fh)
            mat_text = json.dumps(mat_json)
            for tok in set(mat_text.replace("\\\\", "/").replace("\\", "/").split('"')):
                tok_norm = tok[5:] if tok.lower().startswith("data/") else tok
                tl = tok_norm.lower()
                if tl.startswith("textures/fo4port/") and tl.endswith(".dds"):
                    tex_disk = os.path.join(root_dir, *tok_norm.split("/"))
                    if not os.path.isfile(tex_disk) or os.path.getsize(tex_disk) == 0:
                        raise FileNotFoundError(f"{mat_rel} references missing/empty texture: {tex_disk}")
                    checked_textures.append(tok_norm)

        nif_summaries[nif_rel] = {
            "geometries": len(geom_indices),
            "skin_attach_bones": nif_bones_count,
            "verts": len(nif_bone_pts),
            "bone_bounds_m": _bounds_dict(nif_bone_pts),
            "mesh_bounds_m": _bounds_dict(nif_mesh_pts),
            "materials": nif_mats,
        }

    return {
        "nifs": sorted(set(checked_nifs)),
        "meshes": sorted(set(checked_meshes)),
        "local_mats": sorted(set(checked_mats)),
        "local_textures": sorted(set(checked_textures)),
        "summaries": nif_summaries,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--verify-only", default=None, help="Verify an already-staged wrist directory and exit")
    ap.add_argument("--fo4-data", default=None, help="Fallout 4 Data directory")
    ap.add_argument("--sf-data", default=None, help="Starfield Data directory")
    ap.add_argument("--staging", default=None, help="Empty target staging directory (outside Git/game)")
    ap.add_argument("--content-resources", default=None, help="Starfield Tools/ContentResources.zip")
    ap.add_argument("--texconv", default=None, help="Path to texconv.exe / Texconvx64.exe")
    args = ap.parse_args(argv)

    if args.verify_only:
        res = verify_staged_pipboy_wrist(args.verify_only)
        print(json.dumps(res, indent=2))
        return 0

    if not (args.fo4_data and args.sf_data and args.staging):
        ap.error("--fo4-data, --sf-data, and --staging are required unless --verify-only is passed")

    manifest = stage_pipboy_wrist(
        args.fo4_data,
        args.sf_data,
        args.staging,
        content_resources=args.content_resources,
        texconv=args.texconv,
    )
    print(json.dumps({
        "screen_material": manifest["screen_material"],
        "skin_attach_bones": manifest["skin_attach_bones"],
        "dominant_bone": manifest["dominant_bone"],
        "converter_stats": manifest["converter_stats"],
        "summaries": manifest["verified"]["summaries"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
