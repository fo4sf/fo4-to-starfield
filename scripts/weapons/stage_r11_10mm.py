"""Stage Fallout 4's 10mm Pistol + 10mm Round (Round 11 Step 3a, A4.1 ALONE).

Assembles Fallout 4 WEAP 0x00004822 ('10mm') default ObjectTemplate[0] OMOD parts:
  - 0x091FC4 mod_10mm_Receiver_Standard -> meshes/weapons/10mmpistol/10mmpistol_1.nif
    (6 shapes: receiver, slide/bolt, hammer, trigger, mag release, bolt release;
     integral short barrel 0x100E27 & iron sights 0x148409 have Null OMOD models)
  - 0x0231AB mod_10mm_Grip_Standard     -> meshes/weapons/10mmpistol/10mmgrip_1.nif (C-Grip -> P-Grip)
  - 0x091FC2 mod_10mm_Mag_Standard      -> meshes/weapons/10mmpistol/10mmmag01_1.nif (C-Mag -> P-Mag)

Welds the 8 Fallout 4 BSTriShapes along BSConnectPoint::Parents into a single rigid Starfield
BS-173 weapon NIF (`meshes/fo4sf/weapons/10mm/fo4_10mmpistol.nif`) aligned to donor
Starfield.esm:0x24561C (`XM2311` / `M1919`) grip/trigger/muzzle coordinates, and converts
Fallout 4 AMMO 0x0001F276 (`10mmAmmo.nif` -> `meshes/fo4core/ammo/10mm/10mmammo.nif`) plus all
external `.mesh`, `.mat`, and BC1/BC5/BC4 `.dds` files.

Rigid-part & stand-in disclosure (mandatory R15):
  Welded moving parts (10mm pistol slide/bolt, hammer, trigger, mag release, and detachable
  magazine) are rigid and do not move; firing/reload animations and Wwise SNDR audio are
  Starfield XM2311 (0x24561C) stand-ins.

Scope lock: builds 10mm Pistol + 10mm Round ONLY (no Laser Musket, Pipe Gun, or Minigun).
Nothing from game archives is committed to Git; all assets stage into an external empty directory.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import os
import posixpath
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
for _p in (os.path.join(REPO, "src"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fo4sf import ba2 as ba2mod  # noqa: E402
from fo4sf import convert_material as cm  # noqa: E402
from fo4sf import convert_static, meshcollision, nif as nifmod, sfbodies, sfcollision, sfmesh, sfnif  # noqa: E402
from fo4sf.launcher.crashwatch import GAME_EXE, System  # noqa: E402
import stage_r11_weapons as sw  # noqa: E402

WEAP_10MM_MODL = r"fo4sf\weapons\10mm\fo4_10mmpistol.nif"
AMMO_10MM_MODL = r"fo4core\ammo\10mm\10mmammo.nif"

WEAP_10MM_REL = "meshes/fo4sf/weapons/10mm/fo4_10mmpistol.nif"
AMMO_10MM_REL = "meshes/fo4core/ammo/10mm/10mmammo.nif"

FO4_RECEIVER_NIF = "meshes/weapons/10mmpistol/10mmpistol_1.nif"
FO4_RECEIVER_FALLBACK_NIF = "meshes/weapons/10mmpistol/10mmpistol.nif"
FO4_GRIP_NIF = "meshes/weapons/10mmpistol/10mmgrip_1.nif"
FO4_GRIP_FALLBACK_NIF = "meshes/weapons/10mmpistol/10mmgrip.nif"
FO4_MAG_NIF = "meshes/weapons/10mmpistol/10mmmag01_1.nif"
FO4_MAG_FALLBACK_NIF = "meshes/weapons/10mmpistol/10mmmag01.nif"
FO4_AMMO_NIF = "meshes/ammo/10mm/10mmammo.nif"

# Donor Starfield NIFs (read-only at stage time; never committed):
SF_M1919_RECEIVER_NIF = "meshes/weapons/m1919/m1919_receiver_standard.nif"
SF_BOX_COLLISION_CANDIDATES = (
    "meshes/setdressing/outpost/switches/poweredlever01.nif",
    "meshes/setdressing/credtank/credtank_01.nif",
    "meshes/architecture/city/akila/aggriculture/ak_agggreenhouse_pod_floor_01.nif",
)

RIGID_PARTS_DISCLOSURE = (
    "Welded moving parts (10mm pistol slide/bolt, hammer, trigger, mag release, and detachable "
    "magazine) are rigid and do not move; firing/reload animations and Wwise SNDR audio are "
    "Starfield XM2311 (0x24561C) stand-ins."
)

FORBIDDEN_SF_WEAPON_TOKENS = (
    "weapons/m1919",
    "weapons\\m1919",
    "bullpupdummyreceiver",
    "weapons/beowulf",
    "weapons\\beowulf",
)

WEAPON_DYNAMIC_BSX = 0x4A  # HAVOK (0x2) | COMPLEX (0x8) | DYNAMIC (0x40), matching vanilla Beowulf/M1919


class Stage10mmError(ValueError):
    pass


@dataclass(frozen=True)
class ConnectPointParent:
    parent_node: str
    name: str
    quaternion: Tuple[float, float, float, float]  # (w, x, y, z)
    translation: Tuple[float, float, float]        # FO4 units
    scale: float


@dataclass(frozen=True)
class WeldedWeaponResult:
    nif_bytes: bytes
    meshes: Dict[Tuple[str, str], bytes]
    shape_names: List[str]
    materials: List[str]
    bounds_min_m: Tuple[float, float, float]
    bounds_max_m: Tuple[float, float, float]
    named_nodes_m: Dict[str, Tuple[float, float, float]]
    node_to_shapes: Dict[str, List[str]] = field(default_factory=dict)


def normalize_rel(path_str: str) -> str:
    return path_str.strip().replace("\\", "/").lstrip("/").lower()


def _is_subpath(candidate: str, root: str) -> bool:
    c = os.path.normcase(os.path.abspath(candidate))
    r = os.path.normcase(os.path.abspath(root))
    return c == r or c.startswith(r.rstrip("\\/") + os.sep)


def refuse_unsafe_staging_dir(staging: str, fo4_data: Optional[str] = None, sf_data: Optional[str] = None) -> None:
    if not staging or not staging.strip():
        raise Stage10mmError("staging directory must not be empty")
    if _is_subpath(staging, REPO):
        raise Stage10mmError(f"refused staging inside repository root: {staging}")
    for label, game_dir in (("fo4_data", fo4_data), ("sf_data", sf_data)):
        if game_dir and _is_subpath(staging, game_dir):
            raise Stage10mmError(f"refused staging inside {label}: {staging}")
    if os.path.isfile(staging):
        raise Stage10mmError(f"staging path is an existing file: {staging}")
    if os.path.isdir(staging) and os.listdir(staging):
        raise Stage10mmError(f"staging directory is not empty: {staging}")


def require_starfield_not_running() -> None:
    pids = System.pids(GAME_EXE)
    if pids:
        raise Stage10mmError(f"refused to read archives while {GAME_EXE} is running (pids={pids})")


def mat_mul(a: Sequence[float], b: Sequence[float]) -> Tuple[float, ...]:
    return tuple(
        sum(a[3 * i + k] * b[3 * k + j] for k in range(3))
        for i in range(3)
        for j in range(3)
    )


def mat_vec(r: Sequence[float], v: Sequence[float]) -> Tuple[float, float, float]:
    return (
        r[0] * v[0] + r[1] * v[1] + r[2] * v[2],
        r[3] * v[0] + r[4] * v[1] + r[5] * v[2],
        r[6] * v[0] + r[7] * v[1] + r[8] * v[2],
    )


def quat_to_mat(w: float, x: float, y: float, z: float) -> Tuple[float, ...]:
    """Convert FO4 BSConnectPoint quaternion (w, x, y, z) to row-major 3x3 rotation matrix.

    Verified on 10mmPistol_1.nif: WeaponMagazine has R_x(+26.52 deg) and P-Mag has
    q=(0.9733, +0.2293, 0.0001, 0.0) = R_x(-26.52 deg), so R_WeaponMagazine * quat_to_mat(q)
    equals identity [1, 1, 1] matching P-Grip's receiver orientation to 1e-3.
    """
    n = math.sqrt(w * w + x * x + y * y + z * z)
    if n <= 1e-12:
        return (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    w, x, y, z = w / n, x / n, y / n, z / n
    return (
        1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - w * z), 2.0 * (x * z + w * y),
        2.0 * (x * y + w * z), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - w * x),
        2.0 * (x * z - w * y), 2.0 * (y * z + w * x), 1.0 - 2.0 * (x * x + y * y),
    )


def parse_connect_point_parents(nf: nifmod.NifFile) -> Dict[str, ConnectPointParent]:
    """Parse BSConnectPoint::Parents entries keyed by connect-point name (e.g. 'P-Grip', 'P-Mag')."""
    out: Dict[str, ConnectPointParent] = {}
    for bi, blk in enumerate(nf.blocks):
        if nf.type_of(bi) != "BSConnectPoint::Parents":
            continue
        if len(blk) < 8:
            continue
        _, count = struct.unpack_from("<iI", blk, 0)
        p = 8
        for _ in range(count):
            lp, = struct.unpack_from("<I", blk, p); p += 4
            parent_nm = blk[p : p + lp].decode("latin-1"); p += lp
            lc, = struct.unpack_from("<I", blk, p); p += 4
            cp_nm = blk[p : p + lc].decode("latin-1"); p += lc
            qw, qx, qy, qz = struct.unpack_from("<4f", blk, p); p += 16
            tx, ty, tz, sc = struct.unpack_from("<4f", blk, p); p += 16
            out[cp_nm] = ConnectPointParent(
                parent_node=parent_nm,
                name=cp_nm,
                quaternion=(qw, qx, qy, qz),
                translation=(tx, ty, tz),
                scale=sc,
            )
    return out


def parse_named_node_world_transforms(
    nf: nifmod.NifFile,
) -> Dict[str, Tuple[Tuple[float, float, float], Tuple[float, ...], float]]:
    """Return {node_name: (world_tr_fo4, world_rot_3x3, world_scale)} across all NiNodes in `nf`."""
    world = nifmod.world_transforms(nf, placed=False)
    by_name: Dict[str, Tuple[Tuple[float, float, float], Tuple[float, ...], float]] = {}
    for bi, blk in enumerate(nf.blocks):
        if nf.type_of(bi) != "NiNode":
            continue
        ni, = struct.unpack_from("<i", blk, 0)
        if 0 <= ni < len(nf.strings):
            nm = nf.strings[ni].decode("latin-1")
            if nm and nm not in by_name:
                by_name[nm] = world(bi)
    return by_name


def connect_point_world_transform(
    node_worlds: Dict[str, Tuple[Tuple[float, float, float], Tuple[float, ...], float]],
    cp: ConnectPointParent,
) -> Tuple[Tuple[float, float, float], Tuple[float, ...], float]:
    """Compose parent NiNode world transform with connect-point local (translation, quaternion, scale)."""
    if cp.parent_node in node_worlds:
        ptr, prot, psc = node_worlds[cp.parent_node]
    elif "" in node_worlds:
        ptr, prot, psc = node_worlds[""]
    else:
        ptr, prot, psc = (0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0), 1.0
    crot = quat_to_mat(*cp.quaternion)
    mv = mat_vec(prot, cp.translation)
    wtr = (ptr[0] + psc * mv[0], ptr[1] + psc * mv[1], ptr[2] + psc * mv[2])
    wrot = mat_mul(prot, crot)
    wsc = psc * cp.scale
    return wtr, wrot, wsc


def transform_fo4_shape(
    sh: nifmod.Fo4Shape,
    parent_tr: Tuple[float, float, float],
    parent_rot: Tuple[float, ...],
    parent_scale: float,
) -> nifmod.Fo4Shape:
    mv = mat_vec(parent_rot, sh.translation)
    new_tr = (
        parent_tr[0] + parent_scale * mv[0],
        parent_tr[1] + parent_scale * mv[1],
        parent_tr[2] + parent_scale * mv[2],
    )
    new_rot = mat_mul(parent_rot, sh.rotation)
    new_scale = parent_scale * sh.scale
    return dataclasses.replace(sh, translation=new_tr, rotation=new_rot, scale=new_scale)


def _resolve_shape_material(
    fnf: nifmod.NifFile,
    sh: nifmod.Fo4Shape,
    conv: Optional[object],
    fallback_material: str,
) -> str:
    if conv is not None:
        mat = conv._shape_material(fnf, sh)
        if mat:
            return mat
        return conv.neutral
    return fallback_material


def build_welded_10mm_nif(
    receiver_nif_bytes: bytes,
    grip_nif_bytes: bytes,
    mag_nif_bytes: bytes,
    conv: Optional[object] = None,
    weapon_collision_blob: Optional[bytes] = None,
    default_material: str = convert_static.PLACEHOLDER_MATERIAL,
) -> WeldedWeaponResult:
    """Assemble FO4 10mm receiver + grip + magazine into hierarchical BS-173 fo4_10mmpistol.nif."""
    try:
        hres = sw.build_10mm_weapon(
            receiver_nif_bytes,
            grip_nif_bytes,
            mag_nif_bytes,
            conv=conv,
            weapon_collision_blob=weapon_collision_blob,
            default_material=default_material,
        )
    except sw.StageWeaponsError as exc:
        raise Stage10mmError(str(exc)) from exc
    if len(hres.shape_names) < 3:
        raise Stage10mmError(f"expected shapes from receiver + grip + mag, got {len(hres.shape_names)}")
    return WeldedWeaponResult(
        nif_bytes=hres.nif_bytes,
        meshes=hres.meshes,
        shape_names=hres.shape_names,
        materials=hres.materials,
        bounds_min_m=hres.bounds_min_m,
        bounds_max_m=hres.bounds_max_m,
        named_nodes_m=hres.named_nodes_m,
        node_to_shapes=hres.node_to_shapes,
    )


def read_sf_mesh_ba2(sf_data: str, rel_path: str) -> bytes:
    target = normalize_rel(rel_path)
    for name in sorted(os.listdir(sf_data)):
        low = name.lower()
        if not (low.startswith("starfield - meshes") and low.endswith(".ba2")):
            continue
        archive = ba2mod.Ba2(os.path.join(sf_data, name))
        idx = archive.find(target)
        if idx is not None:
            return archive.read(idx)
    raise FileNotFoundError(f"{rel_path} not found in Starfield mesh BA2s under {sf_data}")


def extract_first_physics_blob(sf_nif_bytes: bytes) -> bytes:
    nf = nifmod.parse(sf_nif_bytes)
    for i, blk in enumerate(nf.blocks):
        if nf.type_of(i) == "bhkPhysicsSystem":
            sz, = struct.unpack_from("<I", blk, 0)
            return blk[4 : 4 + sz]
    raise Stage10mmError("Starfield donor NIF contains no bhkPhysicsSystem")


def _extract_mat_texture_paths(mat_json_text: str) -> List[str]:
    """Extract every Data-relative `.dds` texture path referenced inside a Starfield `.mat` JSON file."""
    data = json.loads(mat_json_text)
    found: List[str] = []

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
        elif isinstance(obj, str) and obj.lower().endswith(".dds"):
            norm = normalize_rel(obj)
            if norm.startswith("data/"):
                norm = norm[5:]
            found.append(norm)

    walk(data)
    return sorted(set(found))


def verify_nif_asset_tree(
    staging_root: str,
    nif_rel_path: str,
    *,
    require_converted_materials: bool = True,
    require_collision: bool = True,
    require_weapon_nodes: bool = False,
) -> Dict[str, object]:
    """Verify a staged Starfield BS-173 NIF and confirm 0 missing `.mesh`, `.mat`, and `.dds` files."""
    nif_disk = os.path.join(staging_root, *normalize_rel(nif_rel_path).split("/"))
    if not os.path.isfile(nif_disk):
        raise Stage10mmError(f"missing staged NIF: {nif_rel_path}")
    with open(nif_disk, "rb") as nf_fh:
        raw = nf_fh.read()
    nf = nifmod.parse(raw)
    if nf.bs_version != 173:
        raise Stage10mmError(f"{nif_rel_path}: expected BS 173, got {nf.bs_version}")
    if not nf.blocks or nf.type_of(0) != "NiNode":
        raise Stage10mmError(f"{nif_rel_path}: block [0] is not NiNode")

    node_names: List[str] = []
    phys_bodies: List[dict] = []
    geom_count = 0
    missing_meshes: List[str] = []
    missing_mats: List[str] = []
    missing_dds: List[str] = []
    checked_mats: List[str] = []

    for bi, blk in enumerate(nf.blocks):
        tp = nf.type_of(bi)
        if tp == "NiNode":
            ni, = struct.unpack_from("<i", blk, 0)
            if 0 <= ni < len(nf.strings):
                node_names.append(nf.strings[ni].decode("latin-1"))
        elif tp == "bhkPhysicsSystem":
            sz, = struct.unpack_from("<I", blk, 0)
            phys_bodies.extend(sfbodies.blob_bodies(blk[4 : 4 + sz]))
        elif tp == "BSGeometry":
            geom_count += 1
            g = sfnif.parse_bsgeometry(blk)
            m0 = g.meshes[0]
            if m0 is None or not m0.path:
                raise Stage10mmError(f"{nif_rel_path}: BSGeometry [{bi}] lacks LOD0 .mesh path")
            mesh_rel = "geometries/" + normalize_rel(m0.path.decode("latin-1")) + ".mesh"
            if not os.path.isfile(os.path.join(staging_root, *mesh_rel.split("/"))):
                missing_meshes.append(mesh_rel)
            if not (0 <= g.shader < len(nf.blocks)) or nf.type_of(g.shader) != "BSLightingShaderProperty":
                raise Stage10mmError(f"{nif_rel_path}: BSGeometry [{bi}] lacks BSLightingShaderProperty")
            sh_idx, = struct.unpack_from("<i", nf.blocks[g.shader], 0)
            mat_raw = nf.strings[sh_idx].decode("latin-1")
            mat_rel = normalize_rel(mat_raw)
            if mat_rel.startswith("data/"):
                mat_rel = mat_rel[5:]
            if any(tok in mat_rel for tok in FORBIDDEN_SF_WEAPON_TOKENS):
                raise Stage10mmError(f"{nif_rel_path}: forbidden Starfield weapon material leak {mat_raw!r}")
            checked_mats.append(mat_rel)
            if require_converted_materials or not mat_rel.startswith("materials/common/"):
                mat_disk = os.path.join(staging_root, *mat_rel.split("/"))
                if not os.path.isfile(mat_disk):
                    missing_mats.append(mat_rel)
                else:
                    with open(mat_disk, encoding="utf-8") as mat_fh:
                        mat_txt = mat_fh.read()
                    for tex_rel in _extract_mat_texture_paths(mat_txt):
                        if not os.path.isfile(os.path.join(staging_root, *tex_rel.split("/"))):
                            missing_dds.append(tex_rel)

    if geom_count == 0:
        raise Stage10mmError(f"{nif_rel_path}: contains zero BSGeometry blocks")
    if require_collision and not phys_bodies:
        raise Stage10mmError(f"{nif_rel_path}: missing Havok bhkPhysicsSystem body")
    if require_weapon_nodes:
        for req_nm in ("WEAPON", "ProjectileNode", "TRIGGER", "Magazine", "MiscA06"):
            if req_nm not in node_names:
                raise Stage10mmError(f"{nif_rel_path}: missing required weapon node {req_nm!r}")
        hier = sw.inspect_weapon_nif_hierarchy(raw)
        if "WEAPON" in hier["node_to_shapes"]:
            raise Stage10mmError(f"{nif_rel_path}: BSGeometry flattened directly onto root WEAPON")
        for sh_nm, want_parent in (
            ("Pistol10mmBolt:0", "MiscA06"),
            ("Magazine:0", "Magazine"),
            ("10mmTrigger:0", "TRIGGER"),
        ):
            if sh_nm in hier["shape_to_parent_node"] and hier["shape_to_parent_node"][sh_nm] != want_parent:
                raise Stage10mmError(
                    f"{nif_rel_path}: shape {sh_nm!r} parent {hier['shape_to_parent_node'][sh_nm]!r} != {want_parent!r}"
                )
        node_to_shapes = hier["node_to_shapes"]
    else:
        node_to_shapes = {}
    if missing_meshes or missing_mats or missing_dds:
        raise Stage10mmError(
            f"{nif_rel_path} has missing staged references: "
            f"meshes={sorted(set(missing_meshes))}, mats={sorted(set(missing_mats))}, dds={sorted(set(missing_dds))}"
        )

    return {
        "nif": nif_rel_path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "bs_geometry_count": geom_count,
        "physics_bodies": [{"shape": b["shape"], "layer": b["layer"]} for b in phys_bodies],
        "node_names": node_names,
        "node_to_shapes": node_to_shapes,
        "materials": sorted(set(checked_mats)),
        "missing_meshes": [],
        "missing_mats": [],
        "missing_dds": [],
    }


def verify_staged_10mm(
    staging_root: str,
    *,
    require_converted_materials: bool = True,
    require_collision: bool = True,
) -> Dict[str, object]:
    weap_info = verify_nif_asset_tree(
        staging_root,
        WEAP_10MM_REL,
        require_converted_materials=require_converted_materials,
        require_collision=require_collision,
        require_weapon_nodes=True,
    )
    ammo_info = verify_nif_asset_tree(
        staging_root,
        AMMO_10MM_REL,
        require_converted_materials=require_converted_materials,
        require_collision=require_collision,
        require_weapon_nodes=False,
    )
    if weap_info["bs_geometry_count"] < 8:
        raise Stage10mmError(
            f"expected >= 8 welded BSGeometry blocks on {WEAP_10MM_REL}, got {weap_info['bs_geometry_count']}"
        )
    return {
        "weapon": weap_info,
        "ammo": ammo_info,
        "rigid_parts_disclosure": RIGID_PARTS_DISCLOSURE,
    }


def _discover_sf_tools(sf_data: str, content_resources: Optional[str], texconv: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    sf_root = os.path.dirname(os.path.abspath(sf_data.rstrip("\\/")))
    cr = content_resources or os.path.join(sf_root, "Tools", "ContentResources.zip")
    tc = texconv
    if not tc:
        cand = os.path.join(sf_root, "Tools", "AssetWatcher", "Plugins", "Starfield", "xtexconv.exe")
        if os.path.isfile(cand):
            tc = cand
    return (cr if cr and os.path.isfile(cr) else None), (tc if tc and os.path.isfile(tc) else None)


def _read_fo4_mesh_with_fallback(src: object, primary: str, fallback: Optional[str] = None) -> Tuple[str, bytes]:
    raw = src.mesh(primary.replace("/", "\\"))
    if raw is not None:
        return primary, raw
    if fallback:
        raw_fb = src.mesh(fallback.replace("/", "\\"))
        if raw_fb is not None:
            return fallback, raw_fb
    raise FileNotFoundError(f"Fallout 4 mesh not found in archives: {primary}")


def _run_texconv_cp437_safe(texconv_exe: str, src: str, out_dir: str, fmt: str, extra: Sequence[str] = ()) -> None:
    """UTF-8-mode safe texconv runner (DirectXTex prints CP437 0xE0 alpha in 'alpha:Opaque')."""
    from fo4sf import textures

    mips = () if "-m" in extra else ("-m", "0")
    r = subprocess.run(
        [texconv_exe, "-nologo", "-y", *mips, "-dx10", "-f", fmt, *extra, "-o", out_dir, src],
        capture_output=True,
    )
    out_txt = r.stdout.decode("cp437", errors="replace")
    err_txt = r.stderr.decode("cp437", errors="replace")
    if r.returncode != 0 or "FAILED" in out_txt:
        raise textures.DdsError(f"texconv failed for {src}: {out_txt.strip()[-300:]} {err_txt.strip()[-200:]}")


def stage_r11_10mm(
    fo4_data: str,
    sf_data: str,
    staging: str,
    content_resources: Optional[str] = None,
    texconv: Optional[str] = None,
) -> Dict[str, object]:
    """Convert and stage ONLY FO4_10mmPistol + FO4_Ammo10mm into `staging`."""
    from fo4sf import pipeline, textures

    require_starfield_not_running()
    refuse_unsafe_staging_dir(staging, fo4_data=fo4_data, sf_data=sf_data)

    cr_zip, tc_exe = _discover_sf_tools(sf_data, content_resources, texconv)
    if not cr_zip or not tc_exe:
        raise Stage10mmError(
            f"ContentResources.zip ({cr_zip}) and texconv/xtexconv.exe ({tc_exe}) are required for full staging"
        )

    parent = os.path.dirname(os.path.abspath(staging))
    os.makedirs(parent, exist_ok=True)
    partial = tempfile.mkdtemp(prefix=os.path.basename(os.path.abspath(staging)) + ".partial-", dir=parent)
    orig_texconv = textures.texconv
    textures.texconv = _run_texconv_cp437_safe
    try:
        src = pipeline.Fo4Archives(fo4_data)

        # Donor Starfield collision templates (read-only from Starfield - Meshes*.ba2):
        m1919_raw = read_sf_mesh_ba2(sf_data, SF_M1919_RECEIVER_NIF)
        weap_coll_blob = extract_first_physics_blob(m1919_raw)

        box_coll_blob: Optional[bytes] = None
        for cand in SF_BOX_COLLISION_CANDIDATES:
            try:
                b = convert_static.collision_template_from_nif(read_sf_mesh_ba2(sf_data, cand))
                box_coll_blob = b
                break
            except (FileNotFoundError, nifmod.NifError, ValueError):
                continue
        if box_coll_blob is None:
            raise Stage10mmError("could not locate vanilla box collision template in Starfield - Meshes*.ba2")

        dyn_coll_blob = meshcollision.check_dynamic_template(
            extract_first_physics_blob(read_sf_mesh_ba2(sf_data, meshcollision.DYNAMIC_TEMPLATE_NIF))
        )

        # 1. Build welded rigid 10mm Pistol under prefix='fo4sf'
        conv_weap = pipeline.Converter(
            src,
            partial,
            tc_exe,
            cr_zip,
            collision_template=box_coll_blob,
            dynamic_template=dyn_coll_blob,
            prefix="fo4sf",
        )
        rec_rel, rec_bytes = _read_fo4_mesh_with_fallback(src, FO4_RECEIVER_NIF, FO4_RECEIVER_FALLBACK_NIF)
        grip_rel, grip_bytes = _read_fo4_mesh_with_fallback(src, FO4_GRIP_NIF, FO4_GRIP_FALLBACK_NIF)
        mag_rel, mag_bytes = _read_fo4_mesh_with_fallback(src, FO4_MAG_NIF, FO4_MAG_FALLBACK_NIF)

        welded = build_welded_10mm_nif(
            rec_bytes,
            grip_bytes,
            mag_bytes,
            conv=conv_weap,
            weapon_collision_blob=weap_coll_blob,
        )
        weap_dst = os.path.join(partial, *WEAP_10MM_REL.split("/"))
        pipeline.write_staged(weap_dst, welded.nif_bytes)
        for (d_hex, f_hex), mbytes in welded.meshes.items():
            mdst = os.path.join(partial, "geometries", d_hex, f"{f_hex}.mesh")
            pipeline.write_staged(mdst, mbytes)

        # 2. Convert 10mmAmmo.nif under prefix='fo4core' -> meshes/fo4core/ammo/10mm/10mmammo.nif
        conv_ammo = pipeline.Converter(
            src,
            partial,
            tc_exe,
            cr_zip,
            collision_template=box_coll_blob,
            dynamic_template=dyn_coll_blob,
            prefix="fo4core",
        )
        ammo_res = conv_ammo.convert_nif(FO4_AMMO_NIF)
        if not ammo_res.get("ok"):
            raise Stage10mmError(f"failed to convert {FO4_AMMO_NIF}: {ammo_res}")

        # Remove neutral fallback files if 0 shapes used them so staging contains strictly 10mm assets:
        for unused_prefix, c_obj in (("fo4sf", conv_weap), ("fo4core", conv_ammo)):
            if c_obj.stats["materials_fallback"] == 0:
                n_mat = os.path.join(partial, "materials", unused_prefix, "_neutral.mat")
                if os.path.isfile(n_mat):
                    os.remove(n_mat)
                for kind in ("color", "normal", "rough"):
                    n_tex = os.path.join(partial, "textures", unused_prefix, f"_neutral_{kind}.dds")
                    if os.path.isfile(n_tex):
                        os.remove(n_tex)

        verification = verify_staged_10mm(partial, require_converted_materials=True, require_collision=True)
        manifest = {
            "round": "R11-Step-3a",
            "weapon_scope": "FO4_10mmPistol + FO4_Ammo10mm ONLY (Laser Musket, Pipe Gun, Minigun gated on Probe P4)",
            "fo4_sources": {
                "weap_form_id": "0x00004822",
                "ammo_form_id": "0x0001F276",
                "receiver_omod": {"form_id": "0x00091FC4", "nif": rec_rel},
                "grip_omod": {"form_id": "0x000231AB", "nif": grip_rel, "connect_point": "P-Grip"},
                "mag_omod": {"form_id": "0x00091FC2", "nif": mag_rel, "connect_point": "P-Mag"},
                "barrel_omod": {"form_id": "0x00100E27", "note": "integral short barrel (Null OMOD model)"},
                "sights_omod": {"form_id": "0x00148409", "note": "integral iron sights (Null OMOD model)"},
                "ammo_nif": FO4_AMMO_NIF,
            },
            "sf_donor": {
                "weap_form_id": "0x0024561C",
                "weap_edid": "XM2311",
                "ammo_form_id": "0x002B5598",
                "ammo_edid": "Ammo45Caliber",
                "collision_donor_nif": SF_M1919_RECEIVER_NIF,
            },
            "staged_models": {
                "weap_modl": WEAP_10MM_MODL,
                "weap_rel": WEAP_10MM_REL,
                "ammo_modl": AMMO_10MM_MODL,
                "ammo_rel": AMMO_10MM_REL,
            },
            "bounds_m": {
                "min": [round(x, 5) for x in welded.bounds_min_m],
                "max": [round(x, 5) for x in welded.bounds_max_m],
            },
            "named_nodes_m": {k: [round(x, 5) for x in v] for k, v in welded.named_nodes_m.items()},
            "welded_shapes": welded.shape_names,
            "rigid_parts_disclosure": RIGID_PARTS_DISCLOSURE,
            "verification": verification,
        }
        with open(os.path.join(partial, "r11_10mm_manifest.json"), "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, sort_keys=True)

        if os.path.isdir(staging):
            os.rmdir(staging)
        os.replace(partial, staging)
        partial = ""
        return manifest
    finally:
        textures.texconv = orig_texconv
        if partial and os.path.isdir(partial):
            shutil.rmtree(partial, ignore_errors=True)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Stage Fallout 4 10mm Pistol + 10mm Round (R11 Step 3a, A4.1 ALONE)")
    ap.add_argument("--fo4-data", required=True, help="Path to Fallout 4 Data directory")
    ap.add_argument("--sf-data", required=True, help="Path to Starfield Data directory")
    ap.add_argument("--staging", required=True, help="New or empty external output directory")
    ap.add_argument("--content-resources", default=None, help="Optional path to Starfield Tools/ContentResources.zip")
    ap.add_argument("--texconv", default=None, help="Optional path to texconv.exe / xtexconv.exe")
    args = ap.parse_args(argv)

    manifest = stage_r11_10mm(
        fo4_data=args.fo4_data,
        sf_data=args.sf_data,
        staging=args.staging,
        content_resources=args.content_resources,
        texconv=args.texconv,
    )
    print(f"staged {WEAP_10MM_REL} ({len(manifest['welded_shapes'])} shapes) + {AMMO_10MM_REL}")
    print(f"rigid_parts_disclosure: {RIGID_PARTS_DISCLOSURE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
