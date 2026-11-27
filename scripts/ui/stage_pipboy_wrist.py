"""Stage Fallout 4 Pip-Boy 3000 wrist models onto Starfield's non-occluded spacesuit-watch slot (Round 15 Wave A / Round 16 I2).

Usage:
  python scripts/ui/stage_pipboy_wrist.py --fo4-data "<Fallout 4/Data>" --sf-data "<Starfield/Data>"
      --staging "<new empty dir>" [--content-resources "<ContentResources.zip>"] [--texconv "<texconv.exe>"]
      [--fo4-shell "<FO4SF_Fo4Shell.swf>"]
  python scripts/ui/stage_pipboy_wrist.py --verify-only "<staged dir>"

Builds Fallout 4's 1st-person (pipboy.nif) and 3rd-person (pipboylowplayer.nif) Pip-Boy NIFs anchored to
Starfield's spacesuit ChronoWatch template (spacesuit_suitzero_chronowatch_{m,f}.nif):
  - Combined wrist NIFs: meshes/fo4port/pipboy/pipboy_wrist_housing_{m,f,1st,1st_f}.nif (housing + PipboyScreen)
  - Screen-only NIFs:   meshes/fo4port/pipboy/pipboy_wrist_screen_{m,f,1st,1st_f}.nif  (PipboyScreen only)

Every variant names its screen geometry `PipboyScreen` bound to `materials/fo4port/pipboy/pipboy_screen_2d.mat`
(emissive green FO4 status screen rendered from FO4SF_Fo4Shell into `textures/fo4port/pipboy/pipboy_screen_idle_*.dds`).
All outputs bind rigidly (100% weight) to L_Wrist_Twist2 (slot 3) in the 4-bone SkinAttach table
['L_Forearm', 'L_Wrist_Twist', 'L_Wrist_Twist1', 'L_Wrist_Twist2'].
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

WRIST_SOURCES_JSON = os.path.join(REPO, "src", "fo4sf", "core", "pipboy_wrist_sources.json")


def load_wrist_sources(game: Optional[str] = None, json_path: str = WRIST_SOURCES_JSON) -> dict:
    """Load per-game Pip-Boy source NIFs, cuff centre, and screen/housing shape predicates."""
    with open(json_path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    key = game or cfg.get("default_game", "fo4")
    games = cfg.get("games", {})
    if key not in games:
        raise KeyError(f"game {key!r} not defined in {json_path}")
    entry = dict(games[key])
    entry["game"] = key
    return entry


HOUSING_NIF_M = "meshes/fo4port/pipboy/pipboy_wrist_housing_m.nif"
HOUSING_NIF_F = "meshes/fo4port/pipboy/pipboy_wrist_housing_f.nif"
HOUSING_NIF_1ST = "meshes/fo4port/pipboy/pipboy_wrist_housing_1st.nif"
HOUSING_NIF_1ST_F = "meshes/fo4port/pipboy/pipboy_wrist_housing_1st_f.nif"

SCREEN_NIF_M = "meshes/fo4port/pipboy/pipboy_wrist_screen_m.nif"
SCREEN_NIF_F = "meshes/fo4port/pipboy/pipboy_wrist_screen_f.nif"
SCREEN_NIF_1ST = "meshes/fo4port/pipboy/pipboy_wrist_screen_1st.nif"
SCREEN_NIF_1ST_F = "meshes/fo4port/pipboy/pipboy_wrist_screen_1st_f.nif"

ALL_WRIST_NIFS = (
    HOUSING_NIF_M,
    HOUSING_NIF_F,
    HOUSING_NIF_1ST,
    HOUSING_NIF_1ST_F,
    SCREEN_NIF_M,
    SCREEN_NIF_F,
    SCREEN_NIF_1ST,
    SCREEN_NIF_1ST_F,
)

HOUSING_NIFS = (HOUSING_NIF_M, HOUSING_NIF_F, HOUSING_NIF_1ST, HOUSING_NIF_1ST_F)
SCREEN_NIFS = (SCREEN_NIF_M, SCREEN_NIF_F, SCREEN_NIF_1ST, SCREEN_NIF_1ST_F)

SCREEN_MAT_REL = "materials/fo4port/pipboy/pipboy_screen_2d.mat"
SCREEN_MAT_GAME = "materials\\fo4port\\pipboy\\pipboy_screen_2d.mat"
SCREEN_GEOM_NAME = "PipboyScreen"
SCREEN_TEX_PREFIX = "textures/fo4port/pipboy/pipboy_screen_idle"
SCREEN_BGSM_PATH = "Materials\\AnimObjects\\PipBoy\\PipBoyScreen.BGSM"
SCREEN_SWF_SHELL_REL = "Interface\\PipboyMenu.swf"
SCREEN_SWF_STATS_REL = "Interface\\Pipboy_StatsPage.swf"
SCREEN_SWF_COND_BODY_REL = "Interface\\Components\\ConditionClips\\Condition_Body_0.swf"
SCREEN_SWF_COND_HEAD_REL = "Interface\\Components\\ConditionClips\\Condition_Head.swf"

EXPECTED_SKIN_ATTACH = ("L_Forearm", "L_Wrist_Twist", "L_Wrist_Twist1", "L_Wrist_Twist2")
WRIST_DOMINANT_BONE = "L_Wrist_Twist2"
WRIST_DOMINANT_SLOT = 3
WEIGHTS_PER_VERTEX = 4

_DEFAULT_SOURCES = load_wrist_sources()
FO4_CUFF_CENTER = tuple(float(v) for v in _DEFAULT_SOURCES["cuff_center"])
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


def make_shape_predicates(sources: dict) -> Tuple[Callable[[str], bool], Callable[[str], bool], Callable[[str], bool]]:
    screen_prefixes = tuple(str(p).lower() for p in sources.get("screen_shape_prefixes", []))
    primary_names = frozenset(str(p).lower() for p in sources.get("primary_screen_shapes", []))
    excluded_prefixes = tuple(str(p).lower() for p in sources.get("housing_excluded_prefixes", []))

    def _is_screen(name: str) -> bool:
        low = name.strip().lower()
        return any(low.startswith(p) for p in screen_prefixes)

    def _is_primary_screen(name: str) -> bool:
        return name.strip().lower() in primary_names

    def _is_housing(name: str) -> bool:
        low = name.strip().lower()
        return not any(low.startswith(p) for p in excluded_prefixes)

    return _is_screen, _is_primary_screen, _is_housing


def is_screen_shape(name: str, sources: dict = _DEFAULT_SOURCES) -> bool:
    low = name.strip().lower()
    return any(low.startswith(str(p).lower()) for p in sources.get("screen_shape_prefixes", ()))


def is_primary_screen_shape(name: str, sources: dict = _DEFAULT_SOURCES) -> bool:
    primary_names = {str(p).lower() for p in sources.get("primary_screen_shapes", ())}
    return name.strip().lower() in primary_names


def is_housing_shape(name: str, sources: dict = _DEFAULT_SOURCES) -> bool:
    low = name.strip().lower()
    return not any(low.startswith(str(p).lower()) for p in sources.get("housing_excluded_prefixes", ()))


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
        is_screen_group = mat.replace("/", "\\").lower() == SCREEN_MAT_GAME.lower()
        geom_name = SCREEN_GEOM_NAME if is_screen_group else f"{group_prefix}_{k}"
        g = replace(
            g0,
            name_idx=t.string_index(geom_name.encode("latin-1")),
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


# Minimal 5x7 crisp pixel bitmap font for rendering FO4 Pip-Boy green status screen text
_FONT_5X7: Dict[str, Tuple[str, ...]] = {
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    ":": ("00000", "00100", "00100", "00000", "00100", "00100", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "00100", "00100"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "[": ("01110", "01000", "01000", "01000", "01000", "01000", "01110"),
    "]": ("01110", "00010", "00010", "00010", "00010", "00010", "01110"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01110"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
}


class _SwfBits:
    """Bit-level reader for SWF RECT/MATRIX/SHAPE records."""

    def __init__(self, data: bytes, byte_pos: int = 0) -> None:
        self.data = data
        self.bitpos = byte_pos * 8

    def align(self) -> None:
        rem = self.bitpos & 7
        if rem:
            self.bitpos += 8 - rem

    def read_bits(self, n: int) -> int:
        val = 0
        for _ in range(n):
            byte_i = self.bitpos >> 3
            if byte_i >= len(self.data):
                return val << (n - _) if n else val
            bit = (self.data[byte_i] >> (7 - (self.bitpos & 7))) & 1
            val = (val << 1) | bit
            self.bitpos += 1
        return val

    def read_sbits(self, n: int) -> int:
        if n <= 0:
            return 0
        v = self.read_bits(n)
        if v & (1 << (n - 1)):
            v -= 1 << n
        return v

    def read_rect(self) -> Tuple[int, int, int, int]:
        self.align()
        nb = self.read_bits(5)
        return tuple(self.read_sbits(nb) for _ in range(4))  # type: ignore[return-value]


def _decompress_swf_body(swf_bytes: bytes) -> Tuple[Tuple[float, float], bytes]:
    """Return ((stage_w, stage_h), decompressed_body) for FWS/CWS/GFX/CFX."""
    import zlib

    if len(swf_bytes) < 12 or swf_bytes[:3] not in (b"FWS", b"CWS", b"GFX", b"CFX"):
        raise ValueError("not a valid SWF/GFX container")
    body = zlib.decompress(swf_bytes[8:]) if swf_bytes[:3] in (b"CWS", b"CFX") else swf_bytes[8:]
    br = _SwfBits(body, 0)
    xmin, xmax, ymin, ymax = br.read_rect()
    pos = ((br.bitpos + 7) // 8) + 4
    return ((xmax - xmin) / 20.0, (ymax - ymin) / 20.0), body[pos:]


def _iter_swf_tags(tag_bytes: bytes) -> Iterable[Tuple[int, bytes]]:
    pos = 0
    while pos + 2 <= len(tag_bytes):
        head, = struct.unpack_from("<H", tag_bytes, pos)
        code, size, pos = head >> 6, head & 0x3F, pos + 2
        if size == 0x3F:
            if pos + 4 > len(tag_bytes):
                break
            size, pos = struct.unpack_from("<I", tag_bytes, pos)[0], pos + 4
        if pos + size > len(tag_bytes):
            break
        yield code, tag_bytes[pos:pos + size]
        pos += size
        if code == 0:
            break


def extract_swf_screen_metadata(shell_swf: Optional[bytes], stats_swf: Optional[bytes] = None) -> dict:
    """Read FO4SF_Fo4Shell / PipboyMenu.swf & Pipboy_StatsPage.swf stage + DefineEditText placeholders."""
    import re

    info: dict = {
        "stage": (876.0, 700.0),
        "tabs": ["STAT", "INV", "DATA", "MAP", "RADIO"],
        "subtabs": ["STATUS", "SPECIAL", "PERKS"],
        "hp": "HP  80/80",
        "level": "LEVEL 1",
        "ap": "AP  90/90",
        "weight": "370/175",
        "caps": "110",
        "shell_strings": [],
        "stats_strings": [],
    }
    for key, raw in (("shell_strings", shell_swf), ("stats_strings", stats_swf)):
        if not raw:
            continue
        stage, tag_bytes = _decompress_swf_body(raw)
        if key == "shell_strings":
            info["stage"] = stage
        found: List[str] = []
        for code, tag in _iter_swf_tags(tag_bytes):
            if code == 37:
                for m in re.findall(rb"[A-Za-z0-9/$ .:/()+-]{2,}", tag):
                    txt = m.decode("latin-1", "ignore").strip()
                    if txt and not txt.startswith("$MAIN_Font") and not txt.startswith("$Controller"):
                        found.append(txt)
        info[key] = found
        if key == "shell_strings":
            joined = " ".join(found)
            for lbl_key, needle in (("hp", "HP "), ("level", "LEVEL"), ("ap", "AP ")):
                for s in found:
                    if s.startswith(needle):
                        info[lbl_key] = s.upper()
                        break
            if "$STAT" in joined:
                info["tabs"] = ["STAT", "INV", "DATA", "MAP", "RADIO"]
    return info


def _extract_condition_shape_bounds(cond_swf: Optional[bytes]) -> List[Tuple[float, float, float, float]]:
    """Extract normalized [0..1] shape bounding boxes from a ConditionClips SWF when available."""
    if not cond_swf:
        return []
    (sw, sh), tag_bytes = _decompress_swf_body(cond_swf)
    sw = sw or 100.0
    sh = sh or 100.0
    boxes: List[Tuple[float, float, float, float]] = []
    for code, tag in _iter_swf_tags(tag_bytes):
        if code in (2, 22, 32, 83) and len(tag) >= 6:
            br = _SwfBits(tag, 2)
            x0, x1, y0, y1 = br.read_rect()
            boxes.append((x0 / 20.0 / sw, y0 / 20.0 / sh, x1 / 20.0 / sw, y1 / 20.0 / sh))
    return boxes


def _draw_text(canvas, x: int, y: int, text: str, color: Tuple[int, int, int], scale: int = 2) -> None:
    h, w, _ = canvas.shape
    cx = x
    for ch in text.upper():
        glyph = _FONT_5X7.get(ch, _FONT_5X7[" "])
        for row_i, row in enumerate(glyph):
            py0 = y + row_i * scale
            if py0 >= h or py0 + scale <= 0:
                continue
            for col_i, bit in enumerate(row):
                if bit == "1":
                    px0 = cx + col_i * scale
                    if px0 >= w or px0 + scale <= 0:
                        continue
                    canvas[max(0, py0):min(h, py0 + scale), max(0, px0):min(w, px0 + scale), :3] = color
        cx += 6 * scale


def _fill_rect(canvas, x0: int, y0: int, x1: int, y1: int, color: Tuple[int, int, int]) -> None:
    h, w, _ = canvas.shape
    xa, xb = max(0, min(x0, x1)), min(w, max(x0, x1))
    ya, yb = max(0, min(y0, y1)), min(h, max(y0, y1))
    if xa < xb and ya < yb:
        canvas[ya:yb, xa:xb, :3] = color


def _stroke_rect(canvas, x0: int, y0: int, x1: int, y1: int, color: Tuple[int, int, int], t: int = 2) -> None:
    _fill_rect(canvas, x0, y0, x1, y0 + t, color)
    _fill_rect(canvas, x0, y1 - t, x1, y1, color)
    _fill_rect(canvas, x0, y0, x0 + t, y1, color)
    _fill_rect(canvas, x1 - t, y0, x1, y1, color)


def render_fo4_status_screen_rgba(
    shell_swf: Optional[bytes] = None,
    stats_swf: Optional[bytes] = None,
    cond_body_swf: Optional[bytes] = None,
    cond_head_swf: Optional[bytes] = None,
    size: int = 512,
):
    """Render Fallout 4's green STAT/STATUS Pip-Boy screen into (color_rgba, emissive_rgba) uint8 arrays."""
    import numpy as np

    meta = extract_swf_screen_metadata(shell_swf, stats_swf)
    _ = _extract_condition_shape_bounds(cond_body_swf)
    _ = _extract_condition_shape_bounds(cond_head_swf)

    # Phosphor green palette matching Fallout 4's Pip-Boy CRT (#18FF62 foreground on #031107 glass)
    bg_color = (4, 16, 7)
    bg_emit = (2, 10, 4)
    fg_bright = (28, 255, 98)
    fg_mid = (18, 175, 68)
    fg_dim = (10, 92, 36)

    color = np.zeros((size, size, 4), dtype=np.uint8)
    color[:, :, :3] = bg_color
    color[:, :, 3] = 255

    emissive = np.zeros((size, size, 4), dtype=np.uint8)
    emissive[:, :, :3] = bg_emit
    emissive[:, :, 3] = 255

    s = size / 512.0
    def px(v: float) -> int:
        return int(round(v * s))

    for target, fg_hi, fg_m, fg_lo in (
        (color, fg_bright, fg_mid, fg_dim),
        (emissive, fg_bright, fg_mid, fg_dim),
    ):
        # Outer CRT frame & top/bottom rule lines (from PipboyMenu.swf 876x700 header/footer)
        _stroke_rect(target, px(16), px(14), px(496), px(498), fg_lo, max(1, px(2)))
        _fill_rect(target, px(24), px(52), px(488), px(55), fg_hi)
        _fill_rect(target, px(24), px(452), px(488), px(455), fg_hi)

        # Top tabs: STAT selected (bracketed), INV, DATA, MAP, RADIO
        tab_xs = [42, 136, 222, 316, 396]
        for idx, (tab_name, tx) in enumerate(zip(meta["tabs"][:5], tab_xs)):
            if idx == 0:
                _stroke_rect(target, px(tx - 10), px(22), px(tx + 58), px(54), fg_hi, max(1, px(2)))
                _fill_rect(target, px(tx - 8), px(52), px(tx + 56), px(56), bg_color if target is color else bg_emit)
                _draw_text(target, px(tx), px(30), tab_name, fg_hi, max(1, px(2)))
            else:
                _draw_text(target, px(tx), px(30), tab_name, fg_m, max(1, px(2)))

        # Sub-tabs: STATUS (selected), SPECIAL, PERKS
        _draw_text(target, px(54), px(66), meta["subtabs"][0], fg_hi, max(1, px(2)))
        _fill_rect(target, px(52), px(84), px(124), px(86), fg_hi)
        _draw_text(target, px(168), px(66), meta["subtabs"][1], fg_lo, max(1, px(2)))
        _draw_text(target, px(294), px(66), meta["subtabs"][2], fg_lo, max(1, px(2)))

        # Vault Boy status figure in center (head, torso, arms, legs)
        cx = 256
        # Head circle/box
        _fill_rect(target, px(cx - 18), px(144), px(cx + 18), px(182), fg_hi)
        _fill_rect(target, px(cx - 12), px(152), px(cx + 12), px(176), bg_color if target is color else bg_emit)
        # Hair crest & eyes/smile
        _fill_rect(target, px(cx - 16), px(140), px(cx + 12), px(149), fg_hi)
        _fill_rect(target, px(cx - 7), px(160), px(cx - 3), px(164), fg_hi)
        _fill_rect(target, px(cx + 3), px(160), px(cx + 7), px(164), fg_hi)
        _fill_rect(target, px(cx - 7), px(169), px(cx + 7), px(172), fg_hi)
        # Torso & Vault suit stripe
        _fill_rect(target, px(cx - 24), px(186), px(cx + 24), px(256), fg_hi)
        _fill_rect(target, px(cx - 5), px(190), px(cx + 5), px(252), fg_m)
        # Left & right arms
        _fill_rect(target, px(cx - 52), px(190), px(cx - 26), px(208), fg_hi)
        _fill_rect(target, px(cx - 52), px(208), px(cx - 36), px(244), fg_hi)
        _fill_rect(target, px(cx + 26), px(190), px(cx + 52), px(208), fg_hi)
        _fill_rect(target, px(cx + 36), px(208), px(cx + 52), px(244), fg_hi)
        # Legs
        _fill_rect(target, px(cx - 22), px(258), px(cx - 4), px(316), fg_hi)
        _fill_rect(target, px(cx + 4), px(258), px(cx + 22), px(316), fg_hi)
        _fill_rect(target, px(cx - 28), px(312), px(cx - 4), px(324), fg_hi)
        _fill_rect(target, px(cx + 4), px(312), px(cx + 28), px(324), fg_hi)

        # Six full limb condition bars around Vault Boy (Head, Torso, LArm, RArm, LLeg, RLeg)
        limb_bars = [
            (226, 114, 286, 124),  # Head
            (226, 338, 286, 348),  # Torso
            (116, 198, 174, 208),  # Left arm
            (338, 198, 396, 208),  # Right arm
            (116, 286, 174, 296),  # Left leg
            (338, 286, 396, 296),  # Right leg
        ]
        for bx0, by0, bx1, by1 in limb_bars:
            _stroke_rect(target, px(bx0), px(by0), px(bx1), px(by1), fg_hi, max(1, px(1)))
            _fill_rect(target, px(bx0 + 2), px(by0 + 2), px(bx1 - 2), px(by1 - 2), fg_hi)

        # DMG & DR boxes + Stimpak / RadAway footer strip (Pipboy_StatsPage.swf widgets)
        _fill_rect(target, px(120), px(368), px(196), px(398), fg_lo)
        _stroke_rect(target, px(120), px(368), px(196), px(398), fg_hi, max(1, px(1)))
        _draw_text(target, px(128), px(376), "DMG 18", fg_hi, max(1, px(2)))

        _fill_rect(target, px(316), px(368), px(392), px(398), fg_lo)
        _stroke_rect(target, px(316), px(368), px(392), px(398), fg_hi, max(1, px(1)))
        _draw_text(target, px(326), px(376), "DR  0", fg_hi, max(1, px(2)))

        _fill_rect(target, px(36), px(412), px(476), px(442), fg_lo)
        _draw_text(target, px(50), px(420), "STIMPAK (0)", fg_hi, max(1, px(2)))
        _draw_text(target, px(262), px(420), "RADAWAY (0)", fg_hi, max(1, px(2)))

        # Bottom bar: HP, LEVEL + XP bar, AP (from PipboyMenu.swf BottomBar)
        _fill_rect(target, px(24), px(462), px(152), px(488), fg_lo)
        _draw_text(target, px(32), px(469), meta["hp"][:10], fg_hi, max(1, px(2)))

        _fill_rect(target, px(164), px(462), px(344), px(488), fg_lo)
        _draw_text(target, px(172), px(469), meta["level"][:8], fg_hi, max(1, px(2)))
        _stroke_rect(target, px(264), px(468), px(336), px(482), fg_hi, max(1, px(1)))
        _fill_rect(target, px(267), px(471), px(294), px(479), fg_hi)

        _fill_rect(target, px(356), px(462), px(488), px(488), fg_lo)
        _draw_text(target, px(364), px(469), meta["ap"][:10], fg_hi, max(1, px(2)))

    # Apply subtle CRT scanline modulation on odd rows so the phosphor glass feels physical
    color[1::2, :, :3] = (color[1::2, :, :3].astype(np.uint16) * 82 // 100).astype(np.uint8)
    emissive[1::2, :, :3] = (emissive[1::2, :, :3].astype(np.uint16) * 82 // 100).astype(np.uint8)
    return color, emissive


def _read_fo4_interface_swfs(fo4_data: str, fo4_shell_path: Optional[str] = None) -> Tuple[Optional[bytes], Optional[bytes], Optional[bytes], Optional[bytes]]:
    shell_swf: Optional[bytes] = None
    stats_swf: Optional[bytes] = None
    cond_body_swf: Optional[bytes] = None
    cond_head_swf: Optional[bytes] = None

    if fo4_shell_path and os.path.isfile(fo4_shell_path):
        with open(fo4_shell_path, "rb") as fh:
            shell_swf = fh.read()

    iface_ba2 = os.path.join(fo4_data, "Fallout4 - Interface.ba2")
    if os.path.isfile(iface_ba2):
        arc = ba2.Ba2(iface_ba2)
        if shell_swf is None:
            idx = arc.find(SCREEN_SWF_SHELL_REL)
            if idx is not None:
                shell_swf = arc.read(idx)
        for rel, target in (
            (SCREEN_SWF_STATS_REL, "stats"),
            (SCREEN_SWF_COND_BODY_REL, "body"),
            (SCREEN_SWF_COND_HEAD_REL, "head"),
        ):
            idx = arc.find(rel)
            if idx is not None:
                blob = arc.read(idx)
                if target == "stats":
                    stats_swf = blob
                elif target == "body":
                    cond_body_swf = blob
                else:
                    cond_head_swf = blob
    return shell_swf, stats_swf, cond_body_swf, cond_head_swf


def stage_screen_material_2d(
    src: pipeline.Fo4Archives,
    staging_root: str,
    texconv_exe: str,
    template_mat: dict,
    fo4_data: Optional[str] = None,
    fo4_shell_path: Optional[str] = None,
) -> str:
    """Render green FO4 status screen from FO4SF_Fo4Shell into emissive screen .mat + idle DDS files."""
    import numpy as np

    raw_bgsm = src.material(SCREEN_BGSM_PATH)
    if raw_bgsm is not None:
        bgsm = cm.parse_bgsm(raw_bgsm)
        normal = bgsm.normal or "Shared/FlatFlat_n.dds"
    else:
        normal = "Shared/FlatFlat_n.dds"

    n_bytes = src.texture(normal)
    shell_swf, stats_swf, cond_body_swf, cond_head_swf = (
        _read_fo4_interface_swfs(fo4_data, fo4_shell_path)
        if fo4_data
        else (None, None, None, None)
    )
    color_rgba, emissive_rgba = render_fo4_status_screen_rgba(
        shell_swf=shell_swf,
        stats_swf=stats_swf,
        cond_body_swf=cond_body_swf,
        cond_head_swf=cond_head_swf,
    )

    out_paths: Dict[str, str] = {}
    with tempfile.TemporaryDirectory() as tmp:
        c_in = os.path.join(tmp, "color.dds")
        textures.write_dds_dx10(
            c_in,
            color_rgba.shape[1],
            color_rgba.shape[0],
            textures.DXGI_R8G8B8A8_UNORM,
            np.ascontiguousarray(color_rgba, dtype=np.uint8).tobytes(),
            4,
        )
        textures.texconv(texconv_exe, c_in, tmp, "BC1_UNORM_SRGB", ("-srgbi",))

        e_in = os.path.join(tmp, "emissive.dds")
        textures.write_dds_dx10(
            e_in,
            emissive_rgba.shape[1],
            emissive_rgba.shape[0],
            textures.DXGI_R8G8B8A8_UNORM,
            np.ascontiguousarray(emissive_rgba, dtype=np.uint8).tobytes(),
            4,
        )
        textures.texconv(texconv_exe, e_in, tmp, "BC1_UNORM_SRGB", ("-srgbi",))

        if n_bytes is not None:
            nr, ng = pipeline._plane_pair(n_bytes, tmp, texconv_exe)
        else:
            nr = np.full((4, 4), 128, dtype=np.uint8)
            ng = np.full((4, 4), 128, dtype=np.uint8)
        n_in = os.path.join(tmp, "n_in.dds")
        textures.write_rg8_snorm(n_in, nr, ng)
        textures.texconv(texconv_exe, n_in, tmp, "BC5_SNORM")

        r_in = os.path.join(tmp, "r_in.dds")
        textures.write_r8(r_in, np.full((4, 4), 55, dtype=np.uint8))
        textures.texconv(texconv_exe, r_in, tmp, "BC4_UNORM")

        for kind, fn in (("color", "color.dds"), ("emissive", "emissive.dds"), ("normal", "n_in.dds"), ("rough", "r_in.dds")):
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
        emissive=out_paths["emissive"],
        emissive_tint=(1.0, 1.0, 1.0, 1.0),
        luminous_emittance=120.0,
        exposure_offset=0.0,
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
    game: Optional[str] = None,
    sources_json: str = WRIST_SOURCES_JSON,
    fo4_shell: Optional[str] = None,
) -> dict:
    """Stage combined wrist NIFs (housing + PipboyScreen), screen-only NIFs, meshes, emissive screen mat, and DDS files."""
    pipeline.refuse_unsafe_output_dir(staging, "--staging")

    if os.path.exists(staging) and os.listdir(staging):
        raise SystemExit(f"{staging} is not empty: pass a new or empty staging folder")

    sources = load_wrist_sources(game=game, json_path=sources_json)
    if not sources.get("enabled", False):
        raise SystemExit(f"wrist source table entry {sources['game']!r} is disabled / unconfigured")
    cuff_center = tuple(float(v) for v in sources["cuff_center"])
    _is_screen, pred_primary_screen, pred_housing = make_shape_predicates(sources)

    def pred_housing_with_screen(name: str) -> bool:
        return pred_housing(name) or pred_primary_screen(name)

    texconv_exe = find_texconv(texconv)
    cr_zip = find_content_resources(sf_data, content_resources)

    parent = os.path.dirname(os.path.abspath(staging))
    os.makedirs(parent, exist_ok=True)
    partial = tempfile.mkdtemp(prefix=os.path.basename(os.path.abspath(staging)) + ".partial-", dir=parent)

    try:
        src = pipeline.Fo4Archives(fo4_data)
        conv = pipeline.Converter(src, partial, texconv_exe, cr_zip, prefix="fo4port")

        sf_tpl_m = read_sf_mesh_ba2(sf_data, sources["sf_watch_template_m"])
        sf_tpl_f = read_sf_mesh_ba2(sf_data, sources["sf_watch_template_f"])
        tpl_1st_m_rel = sources.get("sf_watch_template_1st_m") or sources["sf_watch_template_m"]
        tpl_1st_f_rel = sources.get("sf_watch_template_1st_f") or sources["sf_watch_template_f"]
        sf_tpl_1st_m = sf_tpl_m if tpl_1st_m_rel == sources["sf_watch_template_m"] else read_sf_mesh_ba2(sf_data, tpl_1st_m_rel)
        sf_tpl_1st_f = sf_tpl_f if tpl_1st_f_rel == sources["sf_watch_template_f"] else read_sf_mesh_ba2(sf_data, tpl_1st_f_rel)
        fo4_1st_rel = sources["source_1st"]
        fo4_3rd_rel = sources["source_3rd"]
        fo4_1st = src.mesh(fo4_1st_rel)
        fo4_3rd = src.mesh(fo4_3rd_rel)
        if fo4_1st is None:
            raise FileNotFoundError(f"{fo4_1st_rel} not found in {fo4_data}")
        if fo4_3rd is None:
            raise FileNotFoundError(f"{fo4_3rd_rel} not found in {fo4_data}")

        screen_mat_game = stage_screen_material_2d(
            src,
            partial,
            texconv_exe,
            conv.template_mat,
            fo4_data=fo4_data,
            fo4_shell_path=fo4_shell,
        )

        def housing_and_screen_mat(nf_src: nifmod.NifFile, shape) -> Optional[str]:
            sname = shape.name.decode("latin-1", "replace")
            if pred_primary_screen(sname):
                return screen_mat_game
            return conv._shape_material(nf_src, shape)

        def screen_mat(_nf_src: nifmod.NifFile, _shape) -> Optional[str]:
            return screen_mat_game

        builds = {
            HOUSING_NIF_M: rebind_pipboy_to_wrist(
                sf_tpl_m, fo4_3rd, pred_housing_with_screen, housing_and_screen_mat,
                cuff_center_bone=WRIST_CENTER_BONE_M, unit_scale=FO4_TO_SF_WRIST_SCALE_M,
                cuff_center_fo4=cuff_center, group_prefix="FO4WristHousingM",
            ),
            HOUSING_NIF_F: rebind_pipboy_to_wrist(
                sf_tpl_f, fo4_3rd, pred_housing_with_screen, housing_and_screen_mat,
                cuff_center_bone=WRIST_CENTER_BONE_F, unit_scale=FO4_TO_SF_WRIST_SCALE_F,
                cuff_center_fo4=cuff_center, group_prefix="FO4WristHousingF",
            ),
            HOUSING_NIF_1ST: rebind_pipboy_to_wrist(
                sf_tpl_1st_m, fo4_1st, pred_housing_with_screen, housing_and_screen_mat,
                cuff_center_bone=WRIST_CENTER_BONE_M, unit_scale=FO4_TO_SF_WRIST_SCALE_M,
                cuff_center_fo4=cuff_center, group_prefix="FO4WristHousing1st",
            ),
            HOUSING_NIF_1ST_F: rebind_pipboy_to_wrist(
                sf_tpl_1st_f, fo4_1st, pred_housing_with_screen, housing_and_screen_mat,
                cuff_center_bone=WRIST_CENTER_BONE_F, unit_scale=FO4_TO_SF_WRIST_SCALE_F,
                cuff_center_fo4=cuff_center, group_prefix="FO4WristHousing1stF",
            ),
            SCREEN_NIF_M: rebind_pipboy_to_wrist(
                sf_tpl_m, fo4_3rd, pred_primary_screen, screen_mat,
                cuff_center_bone=WRIST_CENTER_BONE_M, unit_scale=FO4_TO_SF_WRIST_SCALE_M,
                cuff_center_fo4=cuff_center, group_prefix="FO4WristScreenM",
            ),
            SCREEN_NIF_F: rebind_pipboy_to_wrist(
                sf_tpl_f, fo4_3rd, pred_primary_screen, screen_mat,
                cuff_center_bone=WRIST_CENTER_BONE_F, unit_scale=FO4_TO_SF_WRIST_SCALE_F,
                cuff_center_fo4=cuff_center, group_prefix="FO4WristScreenF",
            ),
            SCREEN_NIF_1ST: rebind_pipboy_to_wrist(
                sf_tpl_1st_m, fo4_1st, pred_primary_screen, screen_mat,
                cuff_center_bone=WRIST_CENTER_BONE_M, unit_scale=FO4_TO_SF_WRIST_SCALE_M,
                cuff_center_fo4=cuff_center, group_prefix="FO4WristScreen1st",
            ),
            SCREEN_NIF_1ST_F: rebind_pipboy_to_wrist(
                sf_tpl_1st_f, fo4_1st, pred_primary_screen, screen_mat,
                cuff_center_bone=WRIST_CENTER_BONE_F, unit_scale=FO4_TO_SF_WRIST_SCALE_F,
                cuff_center_fo4=cuff_center, group_prefix="FO4WristScreen1stF",
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
            "screen_geometry_name": SCREEN_GEOM_NAME,
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
    """Verify all 8 wrist NIFs, PipboyScreen geometry & emissive .mat, external .mesh weights/bboxes, and DDS files."""
    if not os.path.isdir(root_dir):
        raise FileNotFoundError(f"staged directory not found: {root_dir}")

    screen_mat_disk = os.path.join(root_dir, *SCREEN_MAT_REL.split("/"))
    if not os.path.isfile(screen_mat_disk):
        raise FileNotFoundError(f"missing swappable screen material: {screen_mat_disk}")
    with open(screen_mat_disk, encoding="utf-8") as sm_fh:
        screen_mat_json = json.load(sm_fh)
    sm_textures = ((screen_mat_json.get("Summary") or {}).get("Layer1") or {}).get("Textures") or {}
    emissive_entry = sm_textures.get("Emissive") or {}
    if not emissive_entry.get("File"):
        raise ValueError(f"{SCREEN_MAT_REL}: Summary.Layer1.Textures.Emissive.File is missing")
    has_emissive_comp = any(
        c.get("Type") == "BSMaterial::EmissiveSettingsComponent"
        for o in screen_mat_json.get("Objects", [])
        for c in o.get("Components", [])
    )
    has_emissive_slot7 = any(
        c.get("Type") == "BSMaterial::MRTextureFile" and c.get("Index") == cm.EMISSIVE_SLOT
        for o in screen_mat_json.get("Objects", [])
        for c in o.get("Components", [])
    )
    if not (has_emissive_comp and has_emissive_slot7):
        raise ValueError(f"{SCREEN_MAT_REL}: missing EmissiveSettingsComponent or slot 7 MRTextureFile")

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
        nif_geoms: List[str] = []
        nif_bones_count = 0
        pipboy_screen_count = 0

        for gi in geom_indices:
            g = sfnif.parse_bsgeometry(nf.blocks[gi])
            gname = nf.strings[g.name_idx].decode("latin-1", "replace") if 0 <= g.name_idx < len(nf.strings) else ""
            nif_geoms.append(gname)

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
            is_screen_mat = mat_rel.lower() == SCREEN_MAT_REL
            if gname == SCREEN_GEOM_NAME:
                if not is_screen_mat:
                    raise ValueError(f"{nif_rel}: {SCREEN_GEOM_NAME} must bind {SCREEN_MAT_REL}, got {mat_rel}")
                pipboy_screen_count += 1
            else:
                if "screen" in gname.lower():
                    raise ValueError(f"{nif_rel}: non-{SCREEN_GEOM_NAME} geometry {gname!r} uses 'screen' in name")
                if is_screen_mat:
                    raise ValueError(f"{nif_rel}: non-{SCREEN_GEOM_NAME} geometry {gname!r} must not bind {SCREEN_MAT_REL}")

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

        if pipboy_screen_count != 1:
            raise ValueError(
                f"{nif_rel}: expected exactly 1 {SCREEN_GEOM_NAME!r} BSGeometry bound to {SCREEN_MAT_REL}, found {pipboy_screen_count}"
            )

        nif_summaries[nif_rel] = {
            "geometries": len(geom_indices),
            "geometry_names": nif_geoms,
            "skin_attach_bones": nif_bones_count,
            "verts": len(nif_bone_pts),
            "bone_bounds_m": _bounds_dict(nif_bone_pts),
            "mesh_bounds_m": _bounds_dict(nif_mesh_pts),
            "materials": nif_mats,
        }

    for nif_m, nif_f in ((HOUSING_NIF_1ST, HOUSING_NIF_1ST_F), (SCREEN_NIF_1ST, SCREEN_NIF_1ST_F)):
        with open(os.path.join(root_dir, *nif_m.split("/")), "rb") as fm, open(os.path.join(root_dir, *nif_f.split("/")), "rb") as ff:
            if fm.read() == ff.read():
                raise ValueError(f"female 1st-person wrist NIF {nif_f} must differ from male {nif_m}")

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
    ap.add_argument("--game", default=None, help="Game entry in src/fo4sf/core/pipboy_wrist_sources.json (default fo4)")
    ap.add_argument("--fo4-shell", default=None, help="Optional FO4SF_Fo4Shell.swf path (defaults to Fallout4 - Interface.ba2 PipboyMenu.swf)")
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
        game=args.game,
        fo4_shell=args.fo4_shell,
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
