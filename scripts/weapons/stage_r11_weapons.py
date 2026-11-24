"""Stage Fallout 4 P5 + Rows 5-20 arsenal weapons, ammo, projectiles, core items & F1-F6 controller sidecars.

Builds and verifies all Round 11 Step 4 / Probe P5 + Round 12 Probe P6 Fallout 4 weapons,
13 ammo models, core item NIFs (Stimpak, Caps, Bobby Pin, Plasma Goo), and 2+ explosive
projectile NIFs under `<staging>/`:
  - P5 (0x000898..0x0008A0): 10mm, Baton, Laser Musket (+Preston), Minigun, .10mm/FusionCell/5mm
  - Row 5 (0x0008A1..0x0008A3): Pipe Pistol, Pipe Rifle, .38 Round
  - Core items (0x000851, 0x0008A4, 0x0008A5): Stimpak, Bottlecap, Bobby Pin + Plasma GooPile01
  - Rows 6-20 (0x0008B0..0x0008FF): Frag Grenade/Mine, Pipe Revolver, Hunting Rifle, Combat
    Shotgun, Double-Barrel, SMG, Assault Rifle, Laser Pistol/Rifle, Baseball Bat, Missile
    Launcher, Fat Man, Flamer, Plasma Pistol/Rifle, Gauss Rifle + .308/.45/Shells/5.56/Plasma/2mmEC/Missile/MiniNuke/Fuel.

P5 Fixes applied (F1, F3, F6):
  - F1: Moving geometry sits directly on Starfield donor-tracked NiNode names (TRIGGER, Magazine,
    Bolt, MiscA..MiscB) with empty duplicate helpers removed (10mm WeaponBolt->MiscA06,
    WeaponMagazine->Magazine, WeaponTrigger->TRIGGER; Minigun WeaponBolt->MiscA01,
    WeaponMagazine->Magazine; Laser Musket WeaponTrigger->TRIGGER, crank stays WeaponMagazine).
    Every weapon manifest exports `fo4_part_map` mapping Starfield NiNode -> FO4 source NiNode.
  - F3: Laser Musket ProjectileNode resolves P-ProjectileNode from LaserMusketBarrelExtension2Lens.
  - F6: Each weapon writes `<stem>_controllers.json` alongside its NIF recording every FO4
    controller/sequence/interpolator/FX block from the source NIFs.

Nothing from game archives is committed to Git; all assets stage into an external empty directory.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
if os.path.join(REPO, "src") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "src"))

from fo4sf import ba2 as ba2mod  # noqa: E402
from fo4sf import convert_static, meshcollision, nif as nifmod, sfbodies, sfmesh, sfnif  # noqa: E402
from fo4sf.launcher.crashwatch import GAME_EXE, System  # noqa: E402

WEAP_10MM_MODL = r"fo4sf\weapons\10mm\fo4_10mmpistol.nif"
WEAP_BATON_MODL = r"fo4sf\weapons\baton\fo4_baton.nif"
WEAP_LASER_MUSKET_MODL = r"fo4sf\weapons\lasermusket\fo4_lasermusket.nif"
WEAP_MINIGUN_MODL = r"fo4sf\weapons\minigun\fo4_minigun.nif"

AMMO_10MM_MODL = r"fo4core\ammo\10mm\10mmammo.nif"
AMMO_FUSION_CELL_MODL = r"fo4core\ammo\laserammo\microfusioncell.nif"
AMMO_5MM_MODL = r"fo4core\ammo\5mm\5mmammo.nif"

WEAPON_NIF_RELS: Dict[str, str] = {
    "10mm": "meshes/fo4sf/weapons/10mm/fo4_10mmpistol.nif",
    "baton": "meshes/fo4sf/weapons/baton/fo4_baton.nif",
    "lasermusket": "meshes/fo4sf/weapons/lasermusket/fo4_lasermusket.nif",
    "minigun": "meshes/fo4sf/weapons/minigun/fo4_minigun.nif",
    "pipepistol": "meshes/fo4sf/weapons/pipegun/fo4_pipepistol.nif",
    "piperifle": "meshes/fo4sf/weapons/pipegun/fo4_piperifle.nif",
    "fraggrenade": "meshes/fo4sf/weapons/fraggrenade/fo4_fraggrenade.nif",
    "fragmine": "meshes/fo4sf/weapons/fragmine/fo4_fragmine.nif",
    "piperevolver": "meshes/fo4sf/weapons/piperevolver/fo4_piperevolver.nif",
    "huntingrifle": "meshes/fo4sf/weapons/huntingrifle/fo4_huntingrifle.nif",
    "combatshotgun": "meshes/fo4sf/weapons/combatshotgun/fo4_combatshotgun.nif",
    "doublebarrel": "meshes/fo4sf/weapons/doublebarrel/fo4_doublebarrel.nif",
    "submachinegun": "meshes/fo4sf/weapons/submachinegun/fo4_submachinegun.nif",
    "assaultrifle": "meshes/fo4sf/weapons/assaultrifle/fo4_assaultrifle.nif",
    "laserpistol": "meshes/fo4sf/weapons/lasergun/fo4_laserpistol.nif",
    "laserrifle": "meshes/fo4sf/weapons/lasergun/fo4_laserrifle.nif",
    "baseballbat": "meshes/fo4sf/weapons/baseballbat/fo4_baseballbat.nif",
    "missilelauncher": "meshes/fo4sf/weapons/missilelauncher/fo4_missilelauncher.nif",
    "fatman": "meshes/fo4sf/weapons/fatman/fo4_fatman.nif",
    "flamer": "meshes/fo4sf/weapons/flamer/fo4_flamer.nif",
    "plasmapistol": "meshes/fo4sf/weapons/plasmagun/fo4_plasmapistol.nif",
    "plasmarifle": "meshes/fo4sf/weapons/plasmagun/fo4_plasmarifle.nif",
    "gaussrifle": "meshes/fo4sf/weapons/gaussrifle/fo4_gaussrifle.nif",
}

P5_WEAPON_KEYS: Tuple[str, ...] = ("10mm", "baton", "lasermusket", "minigun")
P5_AMMO_KEYS: Tuple[str, ...] = ("10mm", "fusioncell", "5mm")

AMMO_NIF_RELS: Dict[str, str] = {
    "10mm": "meshes/fo4core/ammo/10mm/10mmammo.nif",
    "fusioncell": "meshes/fo4core/ammo/laserammo/microfusioncell.nif",
    "5mm": "meshes/fo4core/ammo/5mm/5mmammo.nif",
    "38cal": "meshes/fo4core/ammo/38/38ammo.nif",
    "45cal": "meshes/fo4core/ammo/45cal/45ammo.nif",
    "308cal": "meshes/fo4core/ammo/308/308ammo.nif",
    "shotgunshell": "meshes/fo4core/ammo/shotgunshell/shotgunshellammo.nif",
    "556": "meshes/fo4core/ammo/556/556ammo.nif",
    "missile": "meshes/fo4core/ammo/missile/missile.nif",
    "mininuke": "meshes/fo4core/ammo/fatman/ammofatman.nif",
    "flamerfuel": "meshes/fo4core/ammo/flamer/flamerfuel.nif",
    "plasmacartridge": "meshes/fo4core/ammo/plasma/plasmacellmagazine.nif",
    "2mmec": "meshes/fo4core/ammo/gaussrifleammo/gaussrifleammo.nif",
}

FO4_AMMO_SOURCES: Dict[str, str] = {
    "10mm": "meshes/ammo/10mm/10mmammo.nif",
    "fusioncell": "meshes/ammo/laserammo/microfusioncell.nif",
    "5mm": "meshes/ammo/5mm/5mmammo.nif",
    "38cal": "meshes/ammo/38/38ammo.nif",
    "45cal": "meshes/ammo/45cal/45ammo.nif",
    "308cal": "meshes/ammo/308/308ammo.nif",
    "shotgunshell": "meshes/ammo/shotgunshell/shotgunshellammo.nif",
    "556": "meshes/ammo/556/556ammo.nif",
    "missile": "meshes/ammo/missile/missile.nif",
    "mininuke": "meshes/ammo/fatman/ammofatman.nif",
    "flamerfuel": "meshes/ammo/flamer/flamerfuel.nif",
    "plasmacartridge": "meshes/ammo/plasma/plasmacellmagazine.nif",
    "2mmec": "meshes/ammo/gaussrifleammo/gaussrifleammo.nif",
}

CORE_ITEM_NIF_RELS: Dict[str, str] = {
    "stimpak": "meshes/fo4core/props/stimpack01.nif",
    "caps": "meshes/fo4core/props/bottlecapsingle.nif",
    "bobbypin": "meshes/fo4core/props/bobbypin.nif",
    "goopile": "meshes/fo4core/effects/ashpileplasmagoo.nif",
}

FO4_CORE_ITEM_SOURCES: Dict[str, str] = {
    "stimpak": "meshes/props/stimpack01.nif",
    "caps": "meshes/props/bottlecapsingle.nif",
    "bobbypin": "meshes/props/bobbypin.nif",
    "goopile": "meshes/effects/ashpileplasmagoo.nif",
}

PROJ_NIF_RELS: Dict[str, str] = {
    "fraggrenade_proj": "meshes/fo4sf/weapons/grenade/grenadefragprojectile.nif",
    "fragmine_proj": "meshes/fo4sf/weapons/mine/fragmineprojectile.nif",
}

FO4_PROJ_SOURCES: Dict[str, str] = {
    "fraggrenade_proj": "meshes/weapons/grenade/grenadefragprojectile.nif",
    "fragmine_proj": "meshes/weapons/mine/fragmineprojectile.nif",
}

SF_DONOR_COLLISION_NIFS: Dict[str, Tuple[str, ...]] = {
    "10mm": ("meshes/weapons/m1919/m1919_receiver_standard.nif",),
    "baton": ("meshes/weapons/rescueaxe/rescueaxe.nif",),
    "lasermusket": (
        "meshes/weapons/orionrifle/orionrifle_receiver.nif",
        "meshes/weapons/orionrifle/orionrifle.nif",
    ),
    "minigun": (
        "meshes/weapons/microgun/microgun.nif",
        "meshes/weapons/microgun/microgun_receiver.nif",
    ),
    "pipepistol": ("meshes/weapons/stingerpistol/stinger.nif",),
    "piperifle": ("meshes/weapons/beowulf/beowulf.nif",),
    "fraggrenade": ("meshes/weapons/fraggrenade/grenadefrag.nif",),
    "fragmine": ("meshes/weapons/fragmine/fragmine.nif",),
    "piperevolver": ("meshes/weapons/razorback/razorback.nif",),
    "huntingrifle": ("meshes/weapons/lawgiver/lawgiver1.nif",),
    "combatshotgun": ("meshes/weapons/pacifiershotgun/pacifiershotgun.nif", "meshes/weapons/breach/breach.nif"),
    "doublebarrel": ("meshes/weapons/coachmanshotgun/coachmanshotgun.nif",),
    "submachinegun": ("meshes/weapons/maelstrom/maelstrom.nif",),
    "assaultrifle": ("meshes/weapons/ar99/ar99.nif", "meshes/weapons/beowulf/beowulf.nif"),
    "laserpistol": ("meshes/weapons/solstice/solstice.nif",),
    "laserrifle": ("meshes/weapons/laserrifle/pirate_laserrifle_rev1.nif",),
    "baseballbat": ("meshes/weapons/rescueaxe/rescueaxe.nif",),
    "missilelauncher": ("meshes/weapons/bridger/bridger.nif",),
    "fatman": ("meshes/weapons/bridger/bridger.nif",),
    "flamer": ("meshes/weapons/arcwelder/arcwelder.nif",),
    "plasmapistol": ("meshes/weapons/novalight/novalight.nif",),
    "plasmarifle": ("meshes/weapons/inflictorrifle/inflictorrifle_receiver.nif",),
    "gaussrifle": ("meshes/weapons/magsniper/magsniper_receiver.nif",),
}

SF_BOX_COLLISION_CANDIDATES: Tuple[str, ...] = (
    "meshes/setdressing/outpost/switches/poweredlever01.nif",
    "meshes/setdressing/credtank/credtank_01.nif",
    "meshes/architecture/city/akila/aggriculture/ak_agggreenhouse_pod_floor_01.nif",
)

FORBIDDEN_SF_DONOR_MATERIAL_TOKENS: Tuple[str, ...] = (
    "weapons/m1919",
    "weapons\\m1919",
    "bullpupdummyreceiver",
    "weapons/beowulf",
    "weapons\\beowulf",
    "weapons/rescueaxe",
    "weapons\\rescueaxe",
    "weapons/orion",
    "weapons\\orion",
    "weapons/microgun",
    "weapons\\microgun",
    "weapons/stinger",
    "weapons\\stinger",
    "weapons/razorback",
    "weapons\\razorback",
    "weapons/lawgiver",
    "weapons\\lawgiver",
    "weapons/pacifier",
    "weapons\\pacifier",
    "weapons/breach",
    "weapons\\breach",
    "weapons/coachman",
    "weapons\\coachman",
    "weapons/maelstrom",
    "weapons\\maelstrom",
    "weapons/ar99",
    "weapons\\ar99",
    "weapons/solstice",
    "weapons\\solstice",
    "weapons/laserrifle",
    "weapons\\laserrifle",
    "weapons/bridger",
    "weapons\\bridger",
    "weapons/arcwelder",
    "weapons\\arcwelder",
    "weapons/novalight",
    "weapons\\novalight",
    "weapons/inflictor",
    "weapons\\inflictor",
    "weapons/magsniper",
    "weapons\\magsniper",
    "awp_master_shareable",
    "test_herb_default",
    "ammo_crates",
)

STANDIN_DISCLOSURE = (
    "All Fallout 4 weapons preserve sgoKeep moving-part NiNode hierarchies mapped onto "
    "Starfield donor-tracked receiver names (TRIGGER, Magazine, Bolt, MiscA/MiscB) with FO4 "
    "source names saved in fo4_part_map and FO4 NIF controller blocks saved in per-weapon "
    "*_controllers.json sidecars for future converted .rig/.af hookup on claude/robot-anim. "
    "Firing/reload/melee/throw animations, heavy-grip ArcWelder Flamer handling, and Wwise SNDR "
    "audio remain Starfield donor stand-ins; donor Havok collision hulls replace unported FO4 bhk shapes."
)

WEAPON_DYNAMIC_BSX = 0x4A  # HAVOK (0x2) | COMPLEX (0x8) | DYNAMIC (0x40)
SLSF1_REFRACTION = 1 << 15

IDENT_ROT: Tuple[float, ...] = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
# Right-handed SO(3) rotation (det = +1) mapping FO4 1H melee +Y shaft -> Starfield 1H melee +Z shaft
# (verified across RescueAxe, CombatKnife, Cutlass, BarrowKnife, Wakizashi):
#   x' = -x, y' = z, z' = y  =>  det = (-1)*(0 - 1) = +1.
R_MELEE_FO4_Y_TO_SF_Z: Tuple[float, ...] = (
    -1.0, 0.0, 0.0,
    0.0, 0.0, 1.0,
    0.0, 1.0, 0.0,
)


class StageWeaponsError(ValueError):
    pass


@dataclass(frozen=True)
class ConnectPointParent:
    parent_node: str
    name: str
    quaternion: Tuple[float, float, float, float]
    translation: Tuple[float, float, float]
    scale: float


@dataclass(frozen=True)
class AttachedOmodPart:
    nif_bytes: bytes
    connect_point: str
    graft_part_root: bool = True
    override_parent_node: Optional[str] = None
    parent_part_index: Optional[int] = None
    shape_offset_overrides_fo4: Optional[Dict[str, Tuple[float, float, float]]] = None


@dataclass(frozen=True)
class HierarchicalWeaponResult:
    weapon_key: str
    nif_bytes: bytes
    meshes: Dict[Tuple[str, str], bytes]
    shape_names: List[str]
    skipped_shapes: List[str]
    materials: List[str]
    bounds_min_m: Tuple[float, float, float]
    bounds_max_m: Tuple[float, float, float]
    named_nodes_m: Dict[str, Tuple[float, float, float]]
    node_to_shapes: Dict[str, List[str]]
    node_parents: Dict[str, str]
    fo4_part_map: Dict[str, str] = field(default_factory=dict)
    controllers: Dict[str, Any] = field(default_factory=dict)


@dataclass
class _SceneNodeSpec:
    name: str
    parent_name: str
    world_tr_fo4: Tuple[float, float, float]
    world_rot: Tuple[float, ...]
    children_nodes: List[str] = field(default_factory=list)
    shapes: List[sfnif.StaticShape] = field(default_factory=list)


def normalize_rel(path_str: str) -> str:
    return path_str.strip().replace("\\", "/").lstrip("/").lower()


def _is_subpath(candidate: str, root: str) -> bool:
    c = os.path.normcase(os.path.abspath(candidate))
    r = os.path.normcase(os.path.abspath(root))
    return c == r or c.startswith(r.rstrip("\\/") + os.sep)


def refuse_unsafe_staging_dir(
    staging: str,
    fo4_data: Optional[str] = None,
    sf_data: Optional[str] = None,
) -> None:
    if not staging or not staging.strip():
        raise StageWeaponsError("staging directory must not be empty")
    if _is_subpath(staging, REPO):
        raise StageWeaponsError(f"refused staging inside repository root: {staging}")
    norm_parts = [p.lower() for p in os.path.abspath(staging).replace("\\", "/").split("/") if p]
    for p in norm_parts:
        if p.startswith("candidate-"):
            raise StageWeaponsError(f"refused staging inside frozen candidate folder: {staging}")
    for label, game_dir in (("fo4_data", fo4_data), ("sf_data", sf_data)):
        if game_dir:
            if _is_subpath(staging, game_dir):
                raise StageWeaponsError(f"refused staging inside {label}: {staging}")
            game_root = os.path.dirname(os.path.abspath(game_dir.rstrip("\\/")))
            if os.path.isfile(os.path.join(game_root, "Starfield.exe")) and _is_subpath(staging, game_root):
                raise StageWeaponsError(f"refused staging inside Starfield install root: {staging}")
    if os.path.isfile(staging):
        raise StageWeaponsError(f"staging path is an existing file: {staging}")
    if os.path.isdir(staging) and os.listdir(staging):
        raise StageWeaponsError(f"staging directory is not empty: {staging}")


def require_starfield_not_running() -> None:
    pids = System.pids(GAME_EXE)
    if pids:
        raise StageWeaponsError(f"refused to read archives while {GAME_EXE} is running (pids={pids})")


def mat_mul(a: Sequence[float], b: Sequence[float]) -> Tuple[float, ...]:
    return tuple(
        sum(a[3 * i + k] * b[3 * k + j] for k in range(3))
        for i in range(3)
        for j in range(3)
    )


def mat_transpose(r: Sequence[float]) -> Tuple[float, ...]:
    return (
        r[0], r[3], r[6],
        r[1], r[4], r[7],
        r[2], r[5], r[8],
    )


def mat_vec(r: Sequence[float], v: Sequence[float]) -> Tuple[float, float, float]:
    return (
        r[0] * v[0] + r[1] * v[1] + r[2] * v[2],
        r[3] * v[0] + r[4] * v[1] + r[5] * v[2],
        r[6] * v[0] + r[7] * v[1] + r[8] * v[2],
    )


def quat_to_mat(w: float, x: float, y: float, z: float) -> Tuple[float, ...]:
    n = math.sqrt(w * w + x * x + y * y + z * z)
    if n <= 1e-12:
        return IDENT_ROT
    w, x, y, z = w / n, x / n, y / n, z / n
    return (
        1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - w * z), 2.0 * (x * z + w * y),
        2.0 * (x * y + w * z), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - w * x),
        2.0 * (x * z - w * y), 2.0 * (y * z + w * x), 1.0 - 2.0 * (x * x + y * y),
    )


def parse_connect_point_parents(nf: nifmod.NifFile) -> Dict[str, ConnectPointParent]:
    out: Dict[str, ConnectPointParent] = {}
    for bi, blk in enumerate(nf.blocks):
        if nf.type_of(bi) != "BSConnectPoint::Parents" or len(blk) < 8:
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
    world = nifmod.world_transforms(nf, placed=False)
    by_name: Dict[str, Tuple[Tuple[float, float, float], Tuple[float, ...], float]] = {}
    for bi, blk in enumerate(nf.blocks):
        if not nf.type_of(bi).endswith("Node") or nf.type_of(bi) == "BSFaceGenNiNode":
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
    if cp.parent_node in node_worlds:
        ptr, prot, psc = node_worlds[cp.parent_node]
    elif "WEAPON" in node_worlds:
        ptr, prot, psc = node_worlds["WEAPON"]
    else:
        ptr, prot, psc = (0.0, 0.0, 0.0), IDENT_ROT, 1.0
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


def shape_in_node_frame(
    sh_world: nifmod.Fo4Shape,
    node_world_tr_fo4: Tuple[float, float, float],
    node_world_rot: Tuple[float, ...],
) -> nifmod.Fo4Shape:
    """Express a world-space Fo4Shape in the local coordinate frame of `node_world`.

    Guarantees `node_world_rot * p_local_m + node_world_tr_m == p_world_m` and
    `node_world_rot * n_local == n_world` when BSGeometry sits at identity under `NiNode(node)`.
    """
    r_inv = mat_transpose(node_world_rot)
    diff = (
        sh_world.translation[0] - node_world_tr_fo4[0],
        sh_world.translation[1] - node_world_tr_fo4[1],
        sh_world.translation[2] - node_world_tr_fo4[2],
    )
    t_rel = mat_vec(r_inv, diff)
    r_rel = mat_mul(r_inv, sh_world.rotation)
    return dataclasses.replace(sh_world, translation=t_rel, rotation=r_rel, scale=sh_world.scale)


def should_skip_fo4_weapon_shape(fnf: nifmod.NifFile, sh: nifmod.Fo4Shape) -> Optional[str]:
    """Return skip reason if `sh` is an unconvertible FX/blood/refraction overlay, else None."""
    if not sh.positions or not sh.triangles:
        return "empty_geometry"
    sh_nm = sh.name.decode("latin-1")
    low_nm = sh_nm.lower()
    if "mergedblood" in low_nm:
        return "dynamic_blood_overlay"
    if "refractionmesh" in low_nm:
        return "refraction_billboard"
    if 0 <= sh.shader_ref < len(fnf.blocks):
        sh_tp = fnf.type_of(sh.shader_ref)
        if sh_tp != "BSLightingShaderProperty":
            return f"unsupported_shader:{sh_tp}"
        sblk = fnf.blocks[sh.shader_ref]
        if len(sblk) >= 12:
            _st, s_ni, n_extra = struct.unpack_from("<IiI", sblk, 0)
            if 0 <= s_ni < len(fnf.strings):
                mat_str = fnf.strings[s_ni].decode("latin-1").lower().replace("\\", "/")
                if "bloodweapon.bgsm" in mat_str or "/blood/" in mat_str:
                    return "blood_bgsm_overlay"
            fl_off = 12 + 4 * n_extra + 4
            if fl_off + 8 <= len(sblk):
                sf1, _sf2 = struct.unpack_from("<II", sblk, fl_off)
                if sf1 & SLSF1_REFRACTION:
                    return "slsf1_refraction"
    return None


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


def _block_parent_map(nf: nifmod.NifFile) -> Dict[int, int]:
    parents: Dict[int, int] = {}
    for bi in range(len(nf.blocks)):
        tp = nf.type_of(bi)
        if tp.endswith("Node") and tp != "BSFaceGenNiNode":
            for ch in nifmod.node_children(nf, bi):
                parents.setdefault(ch, bi)
    return parents


def _block_name(nf: nifmod.NifFile, bi: int) -> str:
    if not (0 <= bi < len(nf.blocks)):
        return ""
    ni, = struct.unpack_from("<i", nf.blocks[bi], 0)
    if 0 <= ni < len(nf.strings):
        return nf.strings[ni].decode("latin-1")
    return ""


CTRL_BLOCK_KEYWORDS = (
    "Controller",
    "Sequence",
    "Interpolator",
    "Billboard",
    "Particle",
)


def extract_nif_controllers(fnf: nifmod.NifFile, source_label: str) -> Dict[str, Any]:
    """Extract Fallout 4 controller/sequence/FX block inventory (F6 sidecar) from a parsed NifFile."""
    sequences: List[Dict[str, Any]] = []
    blocks: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}

    for bi, blk in enumerate(fnf.blocks):
        tp = fnf.type_of(bi)
        if not any(kw in tp for kw in CTRL_BLOCK_KEYWORDS):
            continue
        counts[tp] = counts.get(tp, 0) + 1
        entry: Dict[str, Any] = {
            "block_index": bi,
            "type": tp,
            "byte_len": len(blk),
            "sha256": hashlib.sha256(blk).hexdigest()[:16],
        }
        if tp == "NiControllerSequence" and len(blk) >= 4:
            sidx = struct.unpack_from("<i", blk, 0)[0]
            seq_name = (
                fnf.strings[sidx].decode("latin-1", "replace")
                if 0 <= sidx < len(fnf.strings)
                else ""
            )
            entry["sequence_name"] = seq_name
            sequences.append({"block_index": bi, "name": seq_name, "byte_len": len(blk)})
        elif len(blk) >= 4 and tp in ("NiTransformController", "NiTransformInterpolator", "NiBillboardNode", "BSLagBoneController"):
            sidx = struct.unpack_from("<i", blk, 0)[0]
            if 0 <= sidx < len(fnf.strings):
                entry["name"] = fnf.strings[sidx].decode("latin-1", "replace")
        blocks.append(entry)

    return {
        "source": source_label,
        "controller_block_count": len(blocks),
        "type_counts": counts,
        "sequences": sequences,
        "blocks": blocks,
    }


def _find_cp_source_in_part(fnf: nifmod.NifFile, cp_name: str) -> Tuple[Dict[str, ConnectPointParent], Dict[str, Tuple[Tuple[float, float, float], Tuple[float, ...], float]]]:
    return parse_connect_point_parents(fnf), parse_named_node_world_transforms(fnf)


def build_hierarchical_weapon_nif(
    weapon_key: str,
    receiver_nif_bytes: bytes,
    attached_parts: Sequence[AttachedOmodPart] = (),
    *,
    conv: Optional[object] = None,
    weapon_collision_blob: Optional[bytes] = None,
    default_material: str = convert_static.PLACEHOLDER_MATERIAL,
    root_frame_rot: Tuple[float, ...] = IDENT_ROT,
    shape_parent_overrides: Optional[Dict[str, str]] = None,
    extra_sgo_nodes_fo4: Optional[Dict[str, Tuple[float, float, float]]] = None,
    preserve_named_pivots: Sequence[str] = (),
    node_rename_map: Optional[Mapping[str, str]] = None,
    source_labels: Sequence[str] = (),
) -> HierarchicalWeaponResult:
    """Assemble a multi-part Fallout 4 weapon into a hierarchical BS-173 Starfield weapon NIF."""
    rec_nf = nifmod.parse(receiver_nif_bytes)
    rec_cps = parse_connect_point_parents(rec_nf)
    rec_node_worlds = parse_named_node_world_transforms(rec_nf)
    scale_m = convert_static.UNIT_SCALE
    renames = dict(node_rename_map or {})
    parent_overrides = {
        sh_nm: renames.get(p_nm, p_nm)
        for sh_nm, p_nm in (shape_parent_overrides or {}).items()
    }
    preserve_eff = {renames.get(p, p) for p in preserve_named_pivots} | set(preserve_named_pivots)
    fo4_part_map: Dict[str, str] = {}
    for sf_nm, fo4_nm in ((v, k) for k, v in renames.items()):
        fo4_part_map.setdefault(sf_nm, fo4_nm)

    ctrl_sources: List[Dict[str, Any]] = [
        extract_nif_controllers(rec_nf, source_labels[0] if source_labels else f"{weapon_key}_receiver")
    ]

    nodes: Dict[str, _SceneNodeSpec] = {
        "WEAPON": _SceneNodeSpec(
            name="WEAPON",
            parent_name="",
            world_tr_fo4=(0.0, 0.0, 0.0),
            world_rot=IDENT_ROT,
        )
    }

    def register_node(
        nm: str,
        parent_nm: str,
        w_tr_fo4: Tuple[float, float, float],
        w_rot: Tuple[float, ...],
    ) -> str:
        eff_nm = nm if nm else "WEAPON"
        if eff_nm == "WEAPON":
            return "WEAPON"
        if eff_nm not in nodes:
            p_nm = parent_nm if parent_nm and parent_nm != eff_nm else "WEAPON"
            if p_nm not in nodes:
                p_nm = "WEAPON"
            nodes[eff_nm] = _SceneNodeSpec(
                name=eff_nm,
                parent_name=p_nm,
                world_tr_fo4=mat_vec(root_frame_rot, w_tr_fo4),
                world_rot=mat_mul(root_frame_rot, w_rot),
            )
            if eff_nm not in nodes[p_nm].children_nodes:
                nodes[p_nm].children_nodes.append(eff_nm)
        return eff_nm

    def ingest_nif_nodes(
        fnf: nifmod.NifFile,
        mount_tr_fo4: Tuple[float, float, float],
        mount_rot: Tuple[float, ...],
        mount_scale: float,
        mount_parent_name: str,
        graft_root: bool,
    ) -> Tuple[Dict[int, str], Dict[int, int]]:
        world_fn = nifmod.world_transforms(fnf, placed=False)
        pmap = _block_parent_map(fnf)
        blk_to_scene_name: Dict[int, str] = {}

        # Traverse BFS from root blocks so parents register before children
        roots = nifmod.footer_roots(fnf)
        queue = list(roots)
        visited: Set[int] = set()
        while queue:
            bi = queue.pop(0)
            if bi in visited or not (0 <= bi < len(fnf.blocks)):
                continue
            visited.add(bi)
            tp = fnf.type_of(bi)
            if not tp.endswith("Node") or tp in ("BSFaceGenNiNode", "NiBillboardNode", "BSValueNode"):
                continue
            raw_nm = _block_name(fnf, bi)
            is_root = bi in roots
            l_tr, l_rot, _l_sc = world_fn(bi)
            mv = mat_vec(mount_rot, l_tr)
            w_tr = (
                mount_tr_fo4[0] + mount_scale * mv[0],
                mount_tr_fo4[1] + mount_scale * mv[1],
                mount_tr_fo4[2] + mount_scale * mv[2],
            )
            w_rot = mat_mul(mount_rot, l_rot)

            if is_root and (raw_nm in ("", "WEAPON", "Root") or not graft_root):
                scene_nm = mount_parent_name
            else:
                parent_bi = pmap.get(bi)
                parent_scene = blk_to_scene_name.get(parent_bi, mount_parent_name) if parent_bi is not None else mount_parent_name
                cand_nm = raw_nm or f"{weapon_key}_node_{bi}"
                mapped_nm = renames.get(cand_nm, cand_nm)
                if raw_nm and (mapped_nm != cand_nm or raw_nm.startswith("Weapon") or raw_nm in preserve_named_pivots or raw_nm in ("BarrelRoot", "Minigun_Barrel", "Minigun_AmmoDrum", "Minigun001")):
                    fo4_part_map[mapped_nm] = raw_nm
                cand_nm = mapped_nm
                if cand_nm in nodes and is_root:
                    scene_nm = cand_nm
                else:
                    if cand_nm in nodes and nodes[cand_nm].parent_name != parent_scene:
                        # If target node was explicitly reserved by node_rename_map from earlier sibling part, reuse it when grafting or attach children under it cleanly
                        if cand_nm not in renames.values():
                            cand_nm = f"{cand_nm}_{bi}"
                    scene_nm = register_node(cand_nm, parent_scene, w_tr, w_rot)
            blk_to_scene_name[bi] = scene_nm
            for ch in nifmod.node_children(fnf, bi):
                queue.append(ch)
        return blk_to_scene_name, pmap

    rec_blk_map, rec_pmap = ingest_nif_nodes(rec_nf, (0.0, 0.0, 0.0), IDENT_ROT, 1.0, "WEAPON", graft_root=True)

    # Collect kept Fo4Shapes with their owning scene node name
    kept_shapes: List[Tuple[nifmod.NifFile, nifmod.Fo4Shape, str]] = []
    skipped_shapes: List[str] = []

    for sh in nifmod.fo4_trishapes(rec_nf, placed=False):
        reason = should_skip_fo4_weapon_shape(rec_nf, sh)
        sh_nm = sh.name.decode("latin-1")
        if reason is not None:
            skipped_shapes.append(f"{sh_nm} ({reason})")
            continue
        sh_world = transform_fo4_shape(sh, (0.0, 0.0, 0.0), root_frame_rot, 1.0)
        parent_bi = rec_pmap.get(sh.block, 0)
        owner_nm = rec_blk_map.get(parent_bi, "WEAPON")
        if sh_nm in parent_overrides and parent_overrides[sh_nm] in nodes:
            owner_nm = parent_overrides[sh_nm]
        kept_shapes.append((rec_nf, sh_world, owner_nm))

    # Track mounted part contexts for multi-hop connect-point attachments (e.g. Flamer barrel -> nozzle)
    part_contexts: List[
        Tuple[
            Dict[str, ConnectPointParent],
            Dict[str, Tuple[Tuple[float, float, float], Tuple[float, ...], float]],
            Tuple[float, float, float],
            Tuple[float, ...],
            float,
            str,
        ]
    ] = []

    for idx, part in enumerate(attached_parts):
        if part.parent_part_index is not None:
            if not (0 <= part.parent_part_index < len(part_contexts)):
                raise StageWeaponsError(f"{weapon_key}: invalid parent_part_index {part.parent_part_index}")
            src_cps, src_nw, base_wtr, base_wrot, base_wsc, base_root_nm = part_contexts[part.parent_part_index]
        else:
            src_cps, src_nw, base_wtr, base_wrot, base_wsc, base_root_nm = (
                rec_cps,
                rec_node_worlds,
                (0.0, 0.0, 0.0),
                IDENT_ROT,
                1.0,
                "WEAPON",
            )

        if part.connect_point not in src_cps:
            raise StageWeaponsError(
                f"{weapon_key}: parent NIF missing required connect point {part.connect_point!r}"
            )
        cp = src_cps[part.connect_point]
        loc_wtr, loc_wrot, loc_wsc = connect_point_world_transform(src_nw, cp)
        mv = mat_vec(base_wrot, loc_wtr)
        cp_wtr = (
            base_wtr[0] + base_wsc * mv[0],
            base_wtr[1] + base_wsc * mv[1],
            base_wtr[2] + base_wsc * mv[2],
        )
        cp_wrot = mat_mul(base_wrot, loc_wrot)
        cp_wsc = base_wsc * loc_wsc

        raw_cp_par = renames.get(cp.parent_node, cp.parent_node) if cp.parent_node else ""
        if part.override_parent_node:
            mount_parent = renames.get(part.override_parent_node, part.override_parent_node)
        elif raw_cp_par and raw_cp_par in nodes:
            mount_parent = raw_cp_par
        else:
            mount_parent = base_root_nm if base_root_nm in nodes else "WEAPON"

        part_nf = nifmod.parse(part.nif_bytes)
        p_lbl = source_labels[idx + 1] if idx + 1 < len(source_labels) else f"{weapon_key}_part_{idx}"
        ctrl_sources.append(extract_nif_controllers(part_nf, p_lbl))

        p_blk_map, p_pmap = ingest_nif_nodes(
            part_nf,
            cp_wtr,
            cp_wrot,
            cp_wsc,
            mount_parent,
            graft_root=part.graft_part_root,
        )
        p_roots = nifmod.footer_roots(part_nf)
        part_root_nm = p_blk_map.get(p_roots[0], mount_parent) if p_roots else mount_parent
        part_contexts.append(
            (
                parse_connect_point_parents(part_nf),
                parse_named_node_world_transforms(part_nf),
                cp_wtr,
                cp_wrot,
                cp_wsc,
                part_root_nm,
            )
        )

        for sh in nifmod.fo4_trishapes(part_nf, placed=False):
            reason = should_skip_fo4_weapon_shape(part_nf, sh)
            sh_nm = sh.name.decode("latin-1")
            if reason is not None:
                skipped_shapes.append(f"{sh_nm} ({reason})")
                continue
            if part.shape_offset_overrides_fo4 and sh_nm in part.shape_offset_overrides_fo4:
                sh = dataclasses.replace(sh, translation=part.shape_offset_overrides_fo4[sh_nm])
            sh_mounted = transform_fo4_shape(sh, cp_wtr, cp_wrot, cp_wsc)
            sh_world = transform_fo4_shape(sh_mounted, (0.0, 0.0, 0.0), root_frame_rot, 1.0)
            parent_bi = p_pmap.get(sh.block, 0)
            owner_nm = p_blk_map.get(parent_bi, mount_parent)
            if sh_nm in parent_overrides and parent_overrides[sh_nm] in nodes:
                owner_nm = parent_overrides[sh_nm]
            kept_shapes.append((part_nf, sh_world, owner_nm))

    if not kept_shapes:
        raise StageWeaponsError(f"{weapon_key}: zero convertible BSGeometry shapes after filtering")

    # Add non-duplicate extra Starfield donor attachment nodes (ProjectileNode, Scope, CasingNonEmbedded)
    if extra_sgo_nodes_fo4:
        for enm, etr_fo4 in extra_sgo_nodes_fo4.items():
            if enm in nodes:
                if not nodes[enm].shapes and not nodes[enm].children_nodes:
                    nodes[enm].world_tr_fo4 = mat_vec(root_frame_rot, etr_fo4)
            else:
                register_node(enm, "WEAPON", etr_fo4, IDENT_ROT)

    # Convert each Fo4Shape in its owning NiNode's local frame
    meshes: Dict[Tuple[str, str], bytes] = {}
    shape_names: List[str] = []
    materials: List[str] = []
    all_world_pts_m: List[Tuple[float, float, float]] = []

    for src_nf, sh_world, owner_nm in kept_shapes:
        owner = nodes[owner_nm]
        sh_local = shape_in_node_frame(sh_world, owner.world_tr_fo4, owner.world_rot)
        mat_path = _resolve_shape_material(src_nf, sh_local, conv, default_material)
        sf_m = convert_static.shape_to_mesh(sh_local, unit_scale=scale_m)
        mesh_bytes = sfmesh.serialize(sf_m)
        d_hex, f_hex = convert_static.mesh_file_path(mesh_bytes)
        meshes[(d_hex, f_hex)] = mesh_bytes

        local_pts_m = [sfmesh.decode_position(p, sf_m.scale) for p in sf_m.positions]
        sphere, box = sfnif.bounds_from_points(local_pts_m)
        w_tr_m = tuple(c * scale_m for c in owner.world_tr_fo4)
        for lp in local_pts_m:
            rv = mat_vec(owner.world_rot, lp)
            all_world_pts_m.append((rv[0] + w_tr_m[0], rv[1] + w_tr_m[1], rv[2] + w_tr_m[2]))

        owner.shapes.append(
            sfnif.StaticShape(
                name=sh_world.name,
                mesh_path=f"{d_hex}\\{f_hex}".encode("ascii"),
                indices_size=len(sf_m.triangles) * 3,
                num_verts=len(sf_m.positions),
                material_path=mat_path,
                sphere=sphere,
                box=box,
            )
        )
        shape_names.append(sh_world.name.decode("latin-1"))
        materials.append(mat_path)

    # Prune empty non-essential helper nodes (e.g. ProceduralGeometry, Lightning01, WeaponMagazineChild*)
    keep_names: Set[str] = {"WEAPON"} | preserve_eff | set((extra_sgo_nodes_fo4 or {}).keys())

    def mark_live(nm: str) -> bool:
        spec = nodes[nm]
        kept_kids = [k for k in spec.children_nodes if mark_live(k)]
        spec.children_nodes = kept_kids
        return bool(spec.shapes or spec.children_nodes or nm in keep_names or nm.startswith("Weapon") or nm == "ProjectileNode")

    mark_live("WEAPON")
    live_order: List[str] = []

    def collect_dfs(nm: str) -> None:
        live_order.append(nm)
        for ch in nodes[nm].children_nodes:
            collect_dfs(ch)

    collect_dfs("WEAPON")

    if weapon_collision_blob is not None:
        bodies = sfbodies.blob_bodies(weapon_collision_blob)
        if not bodies:
            raise StageWeaponsError(f"{weapon_key}: weapon_collision_blob contains zero Havok bodies")

    # Serialize BS-173 hierarchical weapon NIF
    nf_out = nifmod.NifFile(
        endian=1,
        user_version=12,
        bs_version=173,
        author=b"\x00",
        unknown_int=0,
        export_script=b"\x00",
        sf_data=b"\x7a\x00",
    )
    s_sgokeep = nf_out.string_index(b"sgoKeep")
    s_bsx = nf_out.string_index(b"BSX")
    s_matid = nf_out.string_index(b"MaterialID")

    has_coll = weapon_collision_blob is not None
    # Plan exact block indices ahead of serialization:
    #   [0] WEAPON NiNode, [1] sgoKeep, [2] BSXFlags, ([3] bhkNPCollisionObject, [4] bhkPhysicsSystem)
    #   For each non-root live node: [node_blk] NiNode, [node_blk+1] sgoKeep
    #   For each StaticShape on any node: [g_blk] BSGeometry, [g_blk+1] MaterialID, [g_blk+2] BSLightingShaderProperty
    next_blk = 5 if has_coll else 3
    node_blk_idx: Dict[str, int] = {"WEAPON": 0}
    for nm in live_order[1:]:
        node_blk_idx[nm] = next_blk
        next_blk += 2

    shape_blk_indices: Dict[str, List[int]] = {}
    for nm in live_order:
        s_idxs: List[int] = []
        for _ in nodes[nm].shapes:
            s_idxs.append(next_blk)
            next_blk += 3
        shape_blk_indices[nm] = s_idxs

    # Emit [0] WEAPON + root extras + optional collision
    root_children = [node_blk_idx[ch] for ch in nodes["WEAPON"].children_nodes] + shape_blk_indices["WEAPON"]
    coll_ref = 3 if has_coll else -1
    bsx_val = WEAPON_DYNAMIC_BSX if has_coll else 0x8
    s_weapon = nf_out.string_index(b"WEAPON")
    nf_out.add_block(
        "NiNode",
        struct.pack("<iI2iiI", s_weapon, 2, 1, 2, -1, 0xE)
        + struct.pack("<3f9ff", 0.0, 0.0, 0.0, *IDENT_ROT, 1.0)
        + struct.pack("<iI", coll_ref, len(root_children))
        + (struct.pack(f"<{len(root_children)}i", *root_children) if root_children else b""),
    )
    nf_out.add_block("NiStringExtraData", struct.pack("<ii", s_sgokeep, s_sgokeep))
    nf_out.add_block("BSXFlags", struct.pack("<iI", s_bsx, bsx_val))
    if has_coll:
        nf_out.add_block("bhkNPCollisionObject", struct.pack("<iHiI", 0, 0x80, 4, 0))
        nf_out.add_block("bhkPhysicsSystem", struct.pack("<I", len(weapon_collision_blob)) + weapon_collision_blob)

    # Emit non-root NiNodes with parent-relative local transforms
    for nm in live_order[1:]:
        spec = nodes[nm]
        parent_spec = nodes[spec.parent_name]
        p_rinv = mat_transpose(parent_spec.world_rot)
        diff_m = tuple((spec.world_tr_fo4[k] - parent_spec.world_tr_fo4[k]) * scale_m for k in range(3))
        local_tr_m = mat_vec(p_rinv, diff_m)
        local_rot = mat_mul(p_rinv, spec.world_rot)

        blk_i = node_blk_idx[nm]
        extra_i = blk_i + 1
        child_refs = [node_blk_idx[ch] for ch in spec.children_nodes] + shape_blk_indices[nm]
        s_nm = nf_out.string_index(nm.encode("latin-1"))
        nf_out.add_block(
            "NiNode",
            struct.pack("<iIiiI", s_nm, 1, extra_i, -1, 0xE)
            + struct.pack("<3f9ff", *local_tr_m, *local_rot, 1.0)
            + struct.pack("<iI", -1, len(child_refs))
            + (struct.pack(f"<{len(child_refs)}i", *child_refs) if child_refs else b""),
        )
        nf_out.add_block("NiStringExtraData", struct.pack("<ii", s_sgokeep, s_sgokeep))

    # Emit BSGeometry + MaterialID + BSLightingShaderProperty triples
    for nm in live_order:
        for s_obj, base_blk in zip(nodes[nm].shapes, shape_blk_indices[nm]):
            g = sfnif.BSGeometry(
                name_idx=nf_out.string_index(s_obj.name),
                extra_refs=[base_blk + 1],
                flags=0xE,
                sphere=s_obj.sphere,
                box=s_obj.box,
                shader=base_blk + 2,
                meshes=[sfnif.MeshRef(s_obj.indices_size, s_obj.num_verts, 0x40, s_obj.mesh_path), None, None, None],
            )
            nf_out.add_block("BSGeometry", sfnif.build_bsgeometry(g))
            nf_out.add_block("NiIntegerExtraData", struct.pack("<iI", s_matid, sfnif.material_id(s_obj.material_path)))
            nf_out.add_block(
                "BSLightingShaderProperty",
                struct.pack("<iIi", nf_out.string_index(s_obj.material_path.encode("latin-1")), 0, -1),
            )

    nf_out.footer = struct.pack("<II", 1, 0)
    nif_bytes = nifmod.serialize(nf_out)

    bounds_min_m = tuple(min(p[k] for p in all_world_pts_m) for k in range(3))
    bounds_max_m = tuple(max(p[k] for p in all_world_pts_m) for k in range(3))
    named_nodes_m = {
        nm: tuple(nodes[nm].world_tr_fo4[k] * scale_m for k in range(3))
        for nm in live_order
    }
    node_to_shapes = {
        nm: [s_obj.name.decode("latin-1") for s_obj in nodes[nm].shapes]
        for nm in live_order
        if nodes[nm].shapes
    }
    node_parents = {nm: nodes[nm].parent_name for nm in live_order[1:]}

    if not fo4_part_map:
        fo4_part_map["WEAPON"] = weapon_key
    controllers_payload: Dict[str, Any] = {
        "weapon_key": weapon_key,
        "total_controller_blocks": sum(s["controller_block_count"] for s in ctrl_sources),
        "sources": ctrl_sources,
    }

    return HierarchicalWeaponResult(
        weapon_key=weapon_key,
        nif_bytes=nif_bytes,
        meshes=meshes,
        shape_names=shape_names,
        skipped_shapes=skipped_shapes,
        materials=materials,
        bounds_min_m=bounds_min_m,
        bounds_max_m=bounds_max_m,
        named_nodes_m=named_nodes_m,
        node_to_shapes=node_to_shapes,
        node_parents=node_parents,
        fo4_part_map=fo4_part_map,
        controllers=controllers_payload,
    )


def build_10mm_weapon(
    receiver_nif_bytes: bytes,
    grip_nif_bytes: bytes,
    mag_nif_bytes: bytes,
    *,
    conv: Optional[object] = None,
    weapon_collision_blob: Optional[bytes] = None,
    default_material: str = convert_static.PLACEHOLDER_MATERIAL,
    source_labels: Sequence[str] = (
        "meshes/weapons/10mmpistol/10mmpistol.nif",
        "meshes/weapons/10mmpistol/10mmgrip.nif",
        "meshes/weapons/10mmpistol/10mmmag01.nif",
    ),
) -> HierarchicalWeaponResult:
    """Assemble FO4 10mm Pistol (0x000899) with F1 donor-tracked names (MiscA06, Magazine, TRIGGER)."""
    rec_nf = nifmod.parse(receiver_nif_bytes)
    cps = parse_connect_point_parents(rec_nf)
    nw = parse_named_node_world_transforms(rec_nf)
    missing = [nm for nm in ("P-Grip", "P-Mag") if nm not in cps]
    if missing:
        raise StageWeaponsError(f"10mm receiver NIF missing required BSConnectPoint::Parents: {missing}")

    if "ProjectileNode" in nw:
        proj_fo4 = nw["ProjectileNode"][0]
    elif "P-ProjectileNode" in cps:
        proj_fo4 = connect_point_world_transform(nw, cps["P-ProjectileNode"])[0]
    else:
        proj_fo4 = (-0.0343, 18.5135, 4.8686)
    casing_fo4 = connect_point_world_transform(nw, cps["P-Casing"])[0] if "P-Casing" in cps else (-0.0124, 2.4238, 7.8119)

    return build_hierarchical_weapon_nif(
        "10mm",
        receiver_nif_bytes,
        [
            AttachedOmodPart(grip_nif_bytes, "P-Grip", graft_part_root=False),
            AttachedOmodPart(mag_nif_bytes, "P-Mag", graft_part_root=False, override_parent_node="WeaponMagazine"),
        ],
        conv=conv,
        weapon_collision_blob=weapon_collision_blob,
        default_material=default_material,
        shape_parent_overrides={"10mmTrigger:0": "WeaponTrigger"},
        extra_sgo_nodes_fo4={
            "ProjectileNode": proj_fo4,
            "CasingNonEmbedded": casing_fo4,
        },
        preserve_named_pivots=("WeaponBolt", "WeaponMagazine", "WeaponTrigger", "WeaponExtra1", "WeaponExtra2", "WeaponExtra3"),
        node_rename_map={
            "WeaponBolt": "MiscA06",
            "WeaponMagazine": "Magazine",
            "WeaponTrigger": "TRIGGER",
        },
        source_labels=source_labels,
    )


def build_baton_weapon(
    baton_nif_bytes: bytes,
    *,
    conv: Optional[object] = None,
    weapon_collision_blob: Optional[bytes] = None,
    default_material: str = convert_static.PLACEHOLDER_MATERIAL,
    source_labels: Sequence[str] = ("meshes/weapons/baton/baton.nif",),
) -> HierarchicalWeaponResult:
    """Assemble FO4 Baton (0x00089A) aligned to Starfield +Z 1H melee shaft, skipping blood overlay shells."""
    return build_hierarchical_weapon_nif(
        "baton",
        baton_nif_bytes,
        (),
        conv=conv,
        weapon_collision_blob=weapon_collision_blob,
        default_material=default_material,
        root_frame_rot=R_MELEE_FO4_Y_TO_SF_Z,
        extra_sgo_nodes_fo4={
            # In FO4 Baton coordinates (+Y shaft), tip is y=+36.295 (-> +0.5185 m along Starfield +Z after R_MELEE)
            "ProjectileNode": (0.0, 36.295, 0.0),
        },
        preserve_named_pivots=("WeaponExtra1", "WeaponExtra2", "BatonLowHandle", "BatonLowExt01", "BatonLowExt02"),
        source_labels=source_labels,
    )


def build_laser_musket_weapon(
    receiver_nif_bytes: bytes,
    grip_stock_nif_bytes: bytes,
    barrel_nif_bytes: bytes,
    sights_nif_bytes: bytes,
    *,
    conv: Optional[object] = None,
    weapon_collision_blob: Optional[bytes] = None,
    default_material: str = convert_static.PLACEHOLDER_MATERIAL,
    source_labels: Sequence[str] = (
        "meshes/weapons/lasermusket/lasermusket.nif",
        "meshes/weapons/lasermusket/lasermusketmareslegstock.nif",
        "meshes/weapons/lasermusket/lasermusketcompact.nif",
        "meshes/weapons/lasermusket/lasermusketironssights.nif",
    ),
) -> HierarchicalWeaponResult:
    """Assemble FO4 short Laser Musket (0x00089D / Preston 0x00089E) with F1 (TRIGGER, crank=WeaponMagazine) & F3 muzzle."""
    rec_nf = nifmod.parse(receiver_nif_bytes)
    rec_cps = parse_connect_point_parents(rec_nf)
    rec_nw = parse_named_node_world_transforms(rec_nf)
    for req_cp in ("P-Grip", "P-Barrel", "P-Scope"):
        if req_cp not in rec_cps:
            raise StageWeaponsError(f"lasermusket receiver NIF missing connect point {req_cp!r}")

    barrel_wtr, barrel_wrot, barrel_wsc = connect_point_world_transform(rec_nw, rec_cps["P-Barrel"])
    bar_nf = nifmod.parse(barrel_nif_bytes)
    bar_cps = parse_connect_point_parents(bar_nf)
    bar_nw = parse_named_node_world_transforms(bar_nf)
    proj_fo4: Optional[Tuple[float, float, float]] = None
    for cp_key in ("P-ProjectileNode", "P-Muzzle"):
        if cp_key in bar_cps:
            b_muz_local, _, _ = connect_point_world_transform(bar_nw, bar_cps[cp_key])
            mv = mat_vec(barrel_wrot, b_muz_local)
            proj_fo4 = (
                barrel_wtr[0] + barrel_wsc * mv[0],
                barrel_wtr[1] + barrel_wsc * mv[1],
                barrel_wtr[2] + barrel_wsc * mv[2],
            )
            break
    if proj_fo4 is None:
        if "ProjectileNode" in rec_nw:
            proj_fo4 = rec_nw["ProjectileNode"][0]
        else:
            proj_fo4 = (0.0, 65.485, 5.492)

    scope_fo4 = rec_nw.get("ScopePOS", ((0.0, -4.8076, 11.8671), IDENT_ROT, 1.0))[0]

    return build_hierarchical_weapon_nif(
        "lasermusket",
        receiver_nif_bytes,
        [
            AttachedOmodPart(grip_stock_nif_bytes, "P-Grip", graft_part_root=True),
            AttachedOmodPart(barrel_nif_bytes, "P-Barrel", graft_part_root=True),
            AttachedOmodPart(sights_nif_bytes, "P-Scope", graft_part_root=True),
        ],
        conv=conv,
        weapon_collision_blob=weapon_collision_blob,
        default_material=default_material,
        extra_sgo_nodes_fo4={
            "ProjectileNode": proj_fo4,
            "Scope": scope_fo4,
        },
        preserve_named_pivots=("WeaponMagazine", "WeaponTrigger", "WeaponExtra1", "WeaponExtra2", "WeaponExtra3"),
        node_rename_map={
            "WeaponTrigger": "TRIGGER",
        },
        source_labels=source_labels,
    )


def build_minigun_weapon(
    receiver_nif_bytes: bytes,
    barrel_nif_bytes: bytes,
    *,
    conv: Optional[object] = None,
    weapon_collision_blob: Optional[bytes] = None,
    default_material: str = convert_static.PLACEHOLDER_MATERIAL,
    source_labels: Sequence[str] = (
        "meshes/weapons/minigun/minigun.nif",
        "meshes/weapons/minigun/minigunbarrel.nif",
    ),
) -> HierarchicalWeaponResult:
    """Assemble FO4 Minigun (0x0008A0) OBTS[0] with F1 (WeaponBolt->MiscA01, WeaponMagazine->Magazine)."""
    rec_nf = nifmod.parse(receiver_nif_bytes)
    rec_cps = parse_connect_point_parents(rec_nf)
    rec_nw = parse_named_node_world_transforms(rec_nf)
    if "P-Barrel" not in rec_cps:
        raise StageWeaponsError("minigun receiver NIF missing connect point 'P-Barrel'")

    bar_wtr, bar_wrot, bar_wsc = connect_point_world_transform(rec_nw, rec_cps["P-Barrel"])
    bar_nf = nifmod.parse(barrel_nif_bytes)
    bar_cps = parse_connect_point_parents(bar_nf)
    bar_nw = parse_named_node_world_transforms(bar_nf)
    if "P-Muzzle" in bar_cps:
        b_muz, _, _ = connect_point_world_transform(bar_nw, bar_cps["P-Muzzle"])
        mv = mat_vec(bar_wrot, b_muz)
        proj_fo4 = (bar_wtr[0] + bar_wsc * mv[0], bar_wtr[1] + bar_wsc * mv[1], bar_wtr[2] + bar_wsc * mv[2])
    else:
        # Standard 6-barrel tip sits +45.82 FO4 units ahead of WeaponBolt
        proj_fo4 = (bar_wtr[0] + 0.0217, bar_wtr[1] + 45.821, bar_wtr[2] - 0.0157)

    return build_hierarchical_weapon_nif(
        "minigun",
        receiver_nif_bytes,
        [AttachedOmodPart(barrel_nif_bytes, "P-Barrel", graft_part_root=True)],
        conv=conv,
        weapon_collision_blob=weapon_collision_blob,
        default_material=default_material,
        extra_sgo_nodes_fo4={
            "ProjectileNode": proj_fo4,
        },
        preserve_named_pivots=("WeaponBolt", "WeaponMagazine", "Minigun_AmmoDrum", "Minigun_Barrel", "Minigun001"),
        node_rename_map={
            "WeaponBolt": "MiscA01",
            "WeaponMagazine": "Magazine",
        },
        source_labels=source_labels,
    )


@dataclass(frozen=True)
class WeaponBuildPartSpec:
    connect_point: str
    fo4_nif: str
    graft_part_root: bool = True
    override_parent_node: Optional[str] = None
    parent_part_index: Optional[int] = None
    fallback_nif: Optional[str] = None
    relocate_shapes_to_front_sight: Optional[Tuple[int, Sequence[str]]] = None  # (barrel_part_idx, shape_names)


@dataclass(frozen=True)
class WeaponBuildSpec:
    weapon_key: str
    receiver_nif: str
    parts: Tuple[WeaponBuildPartSpec, ...]
    node_rename_map: Dict[str, str]
    preserve_named_pivots: Tuple[str, ...]
    muzzle_part_index: Optional[int] = 0
    muzzle_cps: Tuple[str, ...] = ("P-ProjectileNode", "P-Muzzle")
    fallback_muzzle_fo4: Tuple[float, float, float] = (0.0, 20.0, 3.0)
    root_frame_rot: Tuple[float, ...] = IDENT_ROT
    shape_parent_overrides: Optional[Dict[str, str]] = None


ARSENAL_WEAPON_SPECS: Dict[str, WeaponBuildSpec] = {
    "pipepistol": WeaponBuildSpec(
        weapon_key="pipepistol",
        receiver_nif="meshes/weapons/handmade/recievers/piperiflesa.nif",
        parts=(
            WeaponBuildPartSpec("P-Grip", "meshes/weapons/handmade/grips/handmadepistolgrip.nif", graft_part_root=False),
            WeaponBuildPartSpec("P-Mag", "meshes/weapons/handmade/magazines/45straightmagshort.nif", graft_part_root=False, override_parent_node="WeaponExtra3"),
            WeaponBuildPartSpec("P-Scope", "meshes/weapons/handmade/scopes/piperifleironsights.nif", graft_part_root=True),
        ),
        node_rename_map={"WeaponBolt": "MiscB", "WeaponExtra3": "Magazine", "WeaponTrigger": "TRIGGER"},
        preserve_named_pivots=("WeaponBolt", "WeaponExtra3", "WeaponTrigger", "WeaponExtra1", "WeaponExtra2"),
        muzzle_part_index=None,
        muzzle_cps=("P-ProjectileNode", "P-Muzzle", "P-Barrel"),
        fallback_muzzle_fo4=(0.01, 26.38, 1.02),
    ),
    "piperifle": WeaponBuildSpec(
        weapon_key="piperifle",
        receiver_nif="meshes/weapons/handmade/recievers/piperiflesa.nif",
        parts=(
            WeaponBuildPartSpec("P-Barrel", "meshes/weapons/handmade/barrels/longbarrel.nif", graft_part_root=True),
            WeaponBuildPartSpec("P-Grip", "meshes/weapons/handmade/grips/pipestock.nif", graft_part_root=False),
            WeaponBuildPartSpec("P-Mag", "meshes/weapons/handmade/magazines/45straightmagshort.nif", graft_part_root=False, override_parent_node="WeaponExtra3"),
            WeaponBuildPartSpec("P-Scope", "meshes/weapons/handmade/scopes/piperifleironsights.nif", graft_part_root=True),
        ),
        node_rename_map={"WeaponBolt": "MiscA", "WeaponExtra3": "Magazine", "WeaponTrigger": "TRIGGER"},
        preserve_named_pivots=("WeaponBolt", "WeaponExtra3", "WeaponTrigger", "WeaponExtra1", "WeaponExtra2"),
        muzzle_part_index=0,
        fallback_muzzle_fo4=(0.0, 38.28, 1.01),
    ),
    "fraggrenade": WeaponBuildSpec(
        weapon_key="fraggrenade",
        receiver_nif="meshes/weapons/grenade/grenadefrag.nif",
        parts=(),
        node_rename_map={},
        preserve_named_pivots=("GrenadeFrag",),
        muzzle_part_index=None,
        fallback_muzzle_fo4=(0.0, 0.0, 0.0),
    ),
    "fragmine": WeaponBuildSpec(
        weapon_key="fragmine",
        receiver_nif="meshes/weapons/mine/fragmine.nif",
        parts=(),
        node_rename_map={},
        preserve_named_pivots=("TestMine",),
        muzzle_part_index=None,
        fallback_muzzle_fo4=(0.0, 0.0, 0.0),
    ),
    "piperevolver": WeaponBuildSpec(
        weapon_key="piperevolver",
        receiver_nif="meshes/weapons/handmade/recievers/revolverreceiver.nif",
        parts=(
            WeaponBuildPartSpec("P-Grip", "meshes/weapons/handmade/grips/handmadepistolgrip.nif", graft_part_root=False),
            WeaponBuildPartSpec("P-Scope", "meshes/weapons/handmade/scopes/piperevolverironsights.nif", graft_part_root=True),
        ),
        node_rename_map={"WeaponBolt": "Bolt", "WeaponMagazine": "Magazine", "WeaponTrigger": "TRIGGER"},
        preserve_named_pivots=("WeaponBolt", "WeaponMagazine", "WeaponTrigger", "WeaponExtra1", "WeaponMagazineChild1", "WeaponMagazineChild2", "WeaponMagazineChild3"),
        muzzle_part_index=None,
        muzzle_cps=("P-Barrel",),
        fallback_muzzle_fo4=(0.0, 17.84, 3.49),
    ),
    "huntingrifle": WeaponBuildSpec(
        weapon_key="huntingrifle",
        receiver_nif="meshes/weapons/huntingrifle/huntingriflereceiver.nif",
        parts=(
            WeaponBuildPartSpec("P-Grip", "meshes/weapons/huntingrifle/huntingriflestockshort.nif", graft_part_root=True),
            WeaponBuildPartSpec("P-Mag", "meshes/ammo/308/308smallmag.nif", graft_part_root=False, override_parent_node="WeaponMagazine", fallback_nif="meshes/weapons/huntingrifle/308smallmag.nif"),
            WeaponBuildPartSpec("P-Scope", "meshes/weapons/huntingrifle/huntingrifleironsights.nif", graft_part_root=True, relocate_shapes_to_front_sight=(0, ("FrontSight:0",))),
        ),
        node_rename_map={"WeaponBolt": "MiscA", "WeaponMagazine": "Magazine", "WeaponTrigger": "TRIGGER"},
        preserve_named_pivots=("WeaponBolt", "WeaponMagazine", "WeaponTrigger"),
        muzzle_part_index=0,
        fallback_muzzle_fo4=(0.0, 30.625, 3.601),
    ),
    "combatshotgun": WeaponBuildSpec(
        weapon_key="combatshotgun",
        receiver_nif="meshes/weapons/combatshotgun/combatshotgun.nif",
        parts=(
            WeaponBuildPartSpec("P-Barrel", "meshes/weapons/combatshotgun/combatshotgunbarrelshort.nif", graft_part_root=True),
            WeaponBuildPartSpec("P-Grip", "meshes/weapons/combatshotgun/stockshort.nif", graft_part_root=False),
            WeaponBuildPartSpec("P-Mag", "meshes/weapons/combatshotgun/combatshotgunsmallmag.nif", graft_part_root=False, override_parent_node="WeaponMagazine"),
            WeaponBuildPartSpec("P-Scope", "meshes/weapons/combatshotgun/combatriflesightsiron.nif", graft_part_root=True, relocate_shapes_to_front_sight=(0, ("FrontSight001:0", "FrontSight001:1"))),
        ),
        node_rename_map={"WeaponBolt": "Bolt", "WeaponMagazine": "Magazine", "WeaponTrigger": "TRIGGER"},
        preserve_named_pivots=("WeaponBolt", "WeaponMagazine", "WeaponTrigger"),
        muzzle_part_index=0,
        fallback_muzzle_fo4=(0.0, 40.324, 2.783),
    ),
    "doublebarrel": WeaponBuildSpec(
        weapon_key="doublebarrel",
        receiver_nif="meshes/weapons/shotgun/shotgun.nif",
        parts=(
            WeaponBuildPartSpec("P-Barrel", "meshes/weapons/shotgun/shotgunbarrelmedium.nif", graft_part_root=True),
            WeaponBuildPartSpec("P-Grip", "meshes/weapons/shotgun/shotgunstockshort.nif", graft_part_root=False),
        ),
        node_rename_map={"WeaponMagazine": "MiscA", "WeaponTrigger": "TRIGGER"},
        preserve_named_pivots=("WeaponMagazine", "WeaponTrigger", "WeaponExtra1", "WeaponMagazineChild1", "WeaponMagazineChild2"),
        muzzle_part_index=0,
        fallback_muzzle_fo4=(-0.06, 28.42, 2.81),
    ),
    "submachinegun": WeaponBuildSpec(
        weapon_key="submachinegun",
        receiver_nif="meshes/weapons/combatshotgun/tgunreceiver.nif",
        parts=(
            WeaponBuildPartSpec("P-Barrel", "meshes/weapons/combatshotgun/barrelstandard.nif", graft_part_root=True),
            WeaponBuildPartSpec("P-Grip", "meshes/weapons/combatshotgun/tgungripshort.nif", graft_part_root=False),
            WeaponBuildPartSpec("P-Mag", "meshes/weapons/combatshotgun/tgundrummagsmall.nif", graft_part_root=False, override_parent_node="WeaponMagazine"),
            WeaponBuildPartSpec("P-Scope", "meshes/weapons/combatshotgun/tgunsights.nif", graft_part_root=True),
        ),
        node_rename_map={"WeaponBolt": "Bolt", "WeaponMagazine": "Magazine", "WeaponTrigger": "TRIGGER"},
        preserve_named_pivots=("WeaponBolt", "WeaponMagazine", "WeaponTrigger"),
        muzzle_part_index=0,
        fallback_muzzle_fo4=(0.0, 44.50, 2.80),
    ),
    "assaultrifle": WeaponBuildSpec(
        weapon_key="assaultrifle",
        receiver_nif="meshes/weapons/machinegun/machinegunreceiver.nif",
        parts=(
            WeaponBuildPartSpec("P-Barrel", "meshes/weapons/machinegun/mgbarrelshort.nif", graft_part_root=True),
            WeaponBuildPartSpec("P-Grip", "meshes/weapons/machinegun/mgstockcollapsed.nif", graft_part_root=False),
            WeaponBuildPartSpec("P-Mag", "meshes/weapons/machinegun/mgmagstraight.nif", graft_part_root=False, override_parent_node="WeaponMagazine"),
            WeaponBuildPartSpec("P-Scope", "meshes/weapons/machinegun/mgsight.nif", graft_part_root=True),
        ),
        node_rename_map={"WeaponBolt": "Bolt", "WeaponMagazine": "Magazine", "WeaponTrigger": "TRIGGER"},
        preserve_named_pivots=("WeaponBolt", "WeaponMagazine", "WeaponTrigger", "WeaponExtra1"),
        muzzle_part_index=0,
        fallback_muzzle_fo4=(0.01, 42.38, 4.34),
    ),
    "laserpistol": WeaponBuildSpec(
        weapon_key="laserpistol",
        receiver_nif="meshes/weapons/laserweapons/laserreceiver.nif",
        parts=(
            WeaponBuildPartSpec("P-Barrel", "meshes/weapons/laserweapons/laserpistolbarrel.nif", graft_part_root=True),
            WeaponBuildPartSpec("P-Grip", "meshes/weapons/laserweapons/laserpistolgrip.nif", graft_part_root=False),
            WeaponBuildPartSpec("P-Scope", "meshes/weapons/laserweapons/laserironsights.nif", graft_part_root=True),
        ),
        node_rename_map={"WeaponBolt": "MiscA", "WeaponMagazine": "Magazine", "WeaponTrigger": "TRIGGER"},
        preserve_named_pivots=("WeaponBolt", "WeaponMagazine", "WeaponTrigger", "WeaponExtra1", "WeaponOptics1"),
        muzzle_part_index=0,
        fallback_muzzle_fo4=(-0.018, 26.64, 2.24),
        shape_parent_overrides={"LaserRifleRetainer:0": "LaserRifleReceiver"},
    ),
    "laserrifle": WeaponBuildSpec(
        weapon_key="laserrifle",
        receiver_nif="meshes/weapons/laserweapons/laserreceiver.nif",
        parts=(
            WeaponBuildPartSpec("P-Barrel", "meshes/weapons/laserweapons/laserriflebarrel.nif", graft_part_root=True),
            WeaponBuildPartSpec("P-Grip", "meshes/weapons/laserweapons/laserriflegrip.nif", graft_part_root=False),
            WeaponBuildPartSpec("P-Scope", "meshes/weapons/laserweapons/laserironsights.nif", graft_part_root=True),
        ),
        node_rename_map={"WeaponBolt": "MiscB", "WeaponMagazine": "Magazine", "WeaponTrigger": "TRIGGER"},
        preserve_named_pivots=("WeaponBolt", "WeaponMagazine", "WeaponTrigger", "WeaponExtra1", "WeaponOptics1"),
        muzzle_part_index=0,
        fallback_muzzle_fo4=(-0.018, 34.29, 2.12),
        shape_parent_overrides={"LaserRifleRetainer:0": "LaserRifleReceiver"},
    ),
    "baseballbat": WeaponBuildSpec(
        weapon_key="baseballbat",
        receiver_nif="meshes/weapons/baseballbat/baseballbat.nif",
        parts=(
            WeaponBuildPartSpec("p-Material", "meshes/weapons/baseballbat/mod_grip_leather.nif", graft_part_root=True),
        ),
        node_rename_map={},
        preserve_named_pivots=("BaseballBat",),
        muzzle_part_index=None,
        fallback_muzzle_fo4=(0.0, 47.4, 0.0),
        root_frame_rot=R_MELEE_FO4_Y_TO_SF_Z,
    ),
    "missilelauncher": WeaponBuildSpec(
        weapon_key="missilelauncher",
        receiver_nif="meshes/weapons/missilelauncher/missilelauncher.nif",
        parts=(
            WeaponBuildPartSpec("P-Barrel", "meshes/weapons/missilelauncher/missilelauncherbarrel.nif", graft_part_root=True),
        ),
        node_rename_map={"WeaponMagazine": "Magazine", "WeaponTrigger": "TRIGGER"},
        preserve_named_pivots=("WeaponMagazine", "WeaponTrigger", "WeaponExtra2"),
        muzzle_part_index=0,
        fallback_muzzle_fo4=(0.0, 38.21, 10.99),
    ),
    "fatman": WeaponBuildSpec(
        weapon_key="fatman",
        receiver_nif="meshes/weapons/fatman/fatman.nif",
        parts=(
            WeaponBuildPartSpec("P-Barrel", "meshes/weapons/fatman/mininukestandardbarrel.nif", graft_part_root=True),
        ),
        node_rename_map={"WeaponBolt": "Bolt", "WeaponMagazine": "Magazine", "WeaponTrigger": "TRIGGER"},
        preserve_named_pivots=("WeaponBolt", "WeaponMagazine", "WeaponTrigger"),
        muzzle_part_index=None,
        fallback_muzzle_fo4=(0.0, 35.0, 20.0),
    ),
    "flamer": WeaponBuildSpec(
        weapon_key="flamer",
        receiver_nif="meshes/weapons/flamer/flamer.nif",
        parts=(
            WeaponBuildPartSpec("P-Receiver", "meshes/weapons/flamer/flamerfueltank.nif", graft_part_root=True),
            WeaponBuildPartSpec("P-Barrel", "meshes/weapons/flamer/flamerbarrelshort.nif", graft_part_root=True),
            WeaponBuildPartSpec("P-Muzzle", "meshes/weapons/flamer/standardnozzle.nif", graft_part_root=True, parent_part_index=1),
            WeaponBuildPartSpec("P-Mag", "meshes/weapons/flamer/flamerpropellenttank.nif", graft_part_root=False, override_parent_node="WeaponExtra3"),
        ),
        node_rename_map={"WeaponExtra3": "Magazine"},
        preserve_named_pivots=("WeaponExtra3", "WeaponExtra1", "WeaponExtra2", "WeaponOptics2"),
        muzzle_part_index=2,
        fallback_muzzle_fo4=(-0.042, 71.77, -1.856),
    ),
    "plasmapistol": WeaponBuildSpec(
        weapon_key="plasmapistol",
        receiver_nif="meshes/weapons/plasma/plasmareceiver.nif",
        parts=(
            WeaponBuildPartSpec("P-Grip", "meshes/weapons/plasma/pistolgrip.nif", graft_part_root=False),
            WeaponBuildPartSpec("P-Mag", "meshes/weapons/plasma/plasmacell.nif", graft_part_root=False, override_parent_node="WeaponMagazine"),
        ),
        node_rename_map={"WeaponMagazine": "Magazine", "WeaponTrigger": "TRIGGER"},
        preserve_named_pivots=("WeaponMagazine", "WeaponTrigger", "WeaponExtra1", "WeaponExtra2", "WeaponExtra3", "WeaponOptics1", "WeaponOptics2"),
        muzzle_part_index=None,
        muzzle_cps=("P-Barrel",),
        fallback_muzzle_fo4=(-0.03, 24.11, 5.86),
    ),
    "plasmarifle": WeaponBuildSpec(
        weapon_key="plasmarifle",
        receiver_nif="meshes/weapons/plasma/plasmareceiver.nif",
        parts=(
            WeaponBuildPartSpec("P-Grip", "meshes/weapons/plasma/riflestock01.nif", graft_part_root=False),
            WeaponBuildPartSpec("P-Mag", "meshes/weapons/plasma/plasmacell.nif", graft_part_root=False, override_parent_node="WeaponMagazine"),
        ),
        node_rename_map={"WeaponMagazine": "Magazine", "WeaponTrigger": "TRIGGER"},
        preserve_named_pivots=("WeaponMagazine", "WeaponTrigger", "WeaponExtra1", "WeaponExtra2", "WeaponExtra3", "WeaponOptics1", "WeaponOptics2"),
        muzzle_part_index=None,
        muzzle_cps=("P-Barrel",),
        fallback_muzzle_fo4=(-0.03, 24.11, 5.86),
    ),
    "gaussrifle": WeaponBuildSpec(
        weapon_key="gaussrifle",
        receiver_nif="meshes/weapons/gaussrifle/gaussrifle.nif",
        parts=(
            WeaponBuildPartSpec("P-Mag", "meshes/weapons/gaussrifle/gaussriflemagsmall.nif", graft_part_root=False, override_parent_node="WeaponMagazine"),
            WeaponBuildPartSpec("P-Grip", "meshes/weapons/gaussrifle/gaussriflewoodengrip.nif", graft_part_root=False),
            WeaponBuildPartSpec("P-Scope", "meshes/weapons/gaussrifle/gaussrifleironsights.nif", graft_part_root=True),
        ),
        node_rename_map={"WeaponBolt": "MiscA", "WeaponMagazine": "Magazine", "WeaponTrigger": "TRIGGER"},
        preserve_named_pivots=("WeaponBolt", "WeaponMagazine", "WeaponTrigger"),
        muzzle_part_index=None,
        muzzle_cps=("P-Muzzle",),
        fallback_muzzle_fo4=(0.0, 53.74, 6.98),
    ),
}


def build_arsenal_weapon_from_spec(
    spec: WeaponBuildSpec,
    receiver_nif_bytes: bytes,
    part_nif_bytes: Sequence[bytes],
    *,
    conv: Optional[object] = None,
    weapon_collision_blob: Optional[bytes] = None,
    default_material: str = convert_static.PLACEHOLDER_MATERIAL,
    source_labels: Sequence[str] = (),
) -> HierarchicalWeaponResult:
    """Assemble any Row 5-20 Fallout 4 weapon from a `WeaponBuildSpec` table entry."""
    if len(part_nif_bytes) != len(spec.parts):
        raise StageWeaponsError(f"{spec.weapon_key}: expected {len(spec.parts)} parts, got {len(part_nif_bytes)}")

    rec_nf = nifmod.parse(receiver_nif_bytes)
    rec_cps = parse_connect_point_parents(rec_nf)
    rec_nw = parse_named_node_world_transforms(rec_nf)

    part_nifs = [nifmod.parse(b) for b in part_nif_bytes]
    part_cps_list = [parse_connect_point_parents(pnf) for pnf in part_nifs]
    part_nw_list = [parse_named_node_world_transforms(pnf) for pnf in part_nifs]

    # Compute cumulative part world transforms for muzzle & front-sight alignment
    part_xforms: List[Tuple[Tuple[float, float, float], Tuple[float, ...], float]] = []
    for pspec in spec.parts:
        if pspec.parent_part_index is not None:
            scps = part_cps_list[pspec.parent_part_index]
            snw = part_nw_list[pspec.parent_part_index]
            bwtr, bwrot, bwsc = part_xforms[pspec.parent_part_index]
        else:
            scps, snw, bwtr, bwrot, bwsc = rec_cps, rec_nw, (0.0, 0.0, 0.0), IDENT_ROT, 1.0
        if pspec.connect_point not in scps:
            raise StageWeaponsError(f"{spec.weapon_key}: missing connect point {pspec.connect_point!r}")
        ltr, lrot, lsc = connect_point_world_transform(snw, scps[pspec.connect_point])
        mv = mat_vec(bwrot, ltr)
        part_xforms.append(
            (
                (bwtr[0] + bwsc * mv[0], bwtr[1] + bwsc * mv[1], bwtr[2] + bwsc * mv[2]),
                mat_mul(bwrot, lrot),
                bwsc * lsc,
            )
        )

    attached: List[AttachedOmodPart] = []
    for idx, (pspec, pbytes) in enumerate(zip(spec.parts, part_nif_bytes)):
        offset_overrides: Optional[Dict[str, Tuple[float, float, float]]] = None
        if pspec.relocate_shapes_to_front_sight is not None:
            bar_idx, fs_names = pspec.relocate_shapes_to_front_sight
            bar_cps = part_cps_list[bar_idx]
            if "P-FrontSight" in bar_cps:
                bwtr, bwrot, bwsc = part_xforms[bar_idx]
                fs_loc, _, _ = connect_point_world_transform(part_nw_list[bar_idx], bar_cps["P-FrontSight"])
                fmv = mat_vec(bwrot, fs_loc)
                fs_world = (bwtr[0] + bwsc * fmv[0], bwtr[1] + bwsc * fmv[1], bwtr[2] + bwsc * fmv[2])
                swtr, swrot, swsc = part_xforms[idx]
                delta_w = (fs_world[0] - swtr[0], fs_world[1] - swtr[1], fs_world[2] - swtr[2])
                inv_s = mat_transpose(swrot)
                d_loc = mat_vec(inv_s, delta_w)
                rel_tr = (d_loc[0] / swsc, d_loc[1] / swsc, d_loc[2] / swsc)
                offset_overrides = {nm: rel_tr for nm in fs_names}

        attached.append(
            AttachedOmodPart(
                pbytes,
                pspec.connect_point,
                graft_part_root=pspec.graft_part_root,
                override_parent_node=pspec.override_parent_node,
                parent_part_index=pspec.parent_part_index,
                shape_offset_overrides_fo4=offset_overrides,
            )
        )

    proj_fo4: Optional[Tuple[float, float, float]] = None
    if spec.muzzle_part_index is not None:
        mcps = part_cps_list[spec.muzzle_part_index]
        mnw = part_nw_list[spec.muzzle_part_index]
        mwtr, mwrot, mwsc = part_xforms[spec.muzzle_part_index]
        for cp_key in spec.muzzle_cps:
            if cp_key in mcps:
                lm, _, _ = connect_point_world_transform(mnw, mcps[cp_key])
                mv = mat_vec(mwrot, lm)
                proj_fo4 = (mwtr[0] + mwsc * mv[0], mwtr[1] + mwsc * mv[1], mwtr[2] + mwsc * mv[2])
                break
    else:
        for cp_key in spec.muzzle_cps:
            if cp_key in rec_cps:
                proj_fo4 = connect_point_world_transform(rec_nw, rec_cps[cp_key])[0]
                break
    if proj_fo4 is None:
        proj_fo4 = spec.fallback_muzzle_fo4

    return build_hierarchical_weapon_nif(
        spec.weapon_key,
        receiver_nif_bytes,
        attached,
        conv=conv,
        weapon_collision_blob=weapon_collision_blob,
        default_material=default_material,
        root_frame_rot=spec.root_frame_rot,
        shape_parent_overrides=spec.shape_parent_overrides,
        extra_sgo_nodes_fo4={"ProjectileNode": proj_fo4},
        preserve_named_pivots=spec.preserve_named_pivots,
        node_rename_map=spec.node_rename_map,
        source_labels=source_labels or (spec.receiver_nif, *(p.fo4_nif for p in spec.parts)),
    )


def build_pipe_pistol_weapon(
    receiver_nif_bytes: bytes,
    grip_nif_bytes: bytes,
    mag_nif_bytes: bytes,
    sights_nif_bytes: bytes,
    *,
    conv: Optional[object] = None,
    weapon_collision_blob: Optional[bytes] = None,
    default_material: str = convert_static.PLACEHOLDER_MATERIAL,
) -> HierarchicalWeaponResult:
    """Assemble Row 5 FO4 Pipe Pistol (0x0008A2) for Task 1/Task 2 consumers."""
    return build_arsenal_weapon_from_spec(
        ARSENAL_WEAPON_SPECS["pipepistol"],
        receiver_nif_bytes,
        [grip_nif_bytes, mag_nif_bytes, sights_nif_bytes],
        conv=conv,
        weapon_collision_blob=weapon_collision_blob,
        default_material=default_material,
    )


def build_pipe_rifle_weapon(
    receiver_nif_bytes: bytes,
    barrel_nif_bytes: bytes,
    stock_nif_bytes: bytes,
    mag_nif_bytes: bytes,
    sights_nif_bytes: bytes,
    *,
    conv: Optional[object] = None,
    weapon_collision_blob: Optional[bytes] = None,
    default_material: str = convert_static.PLACEHOLDER_MATERIAL,
) -> HierarchicalWeaponResult:
    """Assemble Row 5 FO4 Pipe Rifle (0x0008A3) for Task 1/Task 2 consumers."""
    return build_arsenal_weapon_from_spec(
        ARSENAL_WEAPON_SPECS["piperifle"],
        receiver_nif_bytes,
        [barrel_nif_bytes, stock_nif_bytes, mag_nif_bytes, sights_nif_bytes],
        conv=conv,
        weapon_collision_blob=weapon_collision_blob,
        default_material=default_material,
    )


def build_flamer_weapon(
    receiver_nif_bytes: bytes,
    tank_nif_bytes: bytes,
    barrel_nif_bytes: bytes,
    nozzle_nif_bytes: bytes,
    propellent_nif_bytes: bytes,
    *,
    conv: Optional[object] = None,
    weapon_collision_blob: Optional[bytes] = None,
    default_material: str = convert_static.PLACEHOLDER_MATERIAL,
) -> HierarchicalWeaponResult:
    """Assemble Row 19 FO4 Flamer (with chained barrel->nozzle CP and ArcWelder heavy-grip stand-in)."""
    return build_arsenal_weapon_from_spec(
        ARSENAL_WEAPON_SPECS["flamer"],
        receiver_nif_bytes,
        [tank_nif_bytes, barrel_nif_bytes, nozzle_nif_bytes, propellent_nif_bytes],
        conv=conv,
        weapon_collision_blob=weapon_collision_blob,
        default_material=default_material,
    )


def inspect_weapon_nif_hierarchy(nif_bytes: bytes) -> Dict[str, object]:
    """Parse a Starfield BS-173 NIF and return its exact parent-child NiNode -> BSGeometry hierarchy."""
    nf = nifmod.parse(nif_bytes)
    if nf.bs_version != 173:
        raise StageWeaponsError(f"expected BS 173 NIF, got {nf.bs_version}")
    if not nf.blocks or nf.type_of(0) != "NiNode":
        raise StageWeaponsError("block [0] is not NiNode")

    world_fn = nifmod.world_transforms(nf, placed=False)
    node_names: Dict[int, str] = {}
    node_sgo: Dict[int, bool] = {}
    node_kids: Dict[int, List[int]] = {}
    geom_info: Dict[int, Dict[str, object]] = {}
    phys_bodies: List[dict] = []

    for bi, blk in enumerate(nf.blocks):
        tp = nf.type_of(bi)
        if tp == "NiNode":
            nm = _block_name(nf, bi)
            node_names[bi] = nm
            node_kids[bi] = nifmod.node_children(nf, bi)
            _, nextra = struct.unpack_from("<iI", blk, 0)
            extras = struct.unpack_from(f"<{nextra}i", blk, 8) if nextra else ()
            has_sgo = False
            for ex in extras:
                if 0 <= ex < len(nf.blocks) and nf.type_of(ex) == "NiStringExtraData":
                    ek, ev = struct.unpack_from("<ii", nf.blocks[ex], 0)
                    if 0 <= ek < len(nf.strings) and 0 <= ev < len(nf.strings):
                        if nf.strings[ek] == b"sgoKeep" and nf.strings[ev] == b"sgoKeep":
                            has_sgo = True
            node_sgo[bi] = has_sgo
        elif tp == "bhkPhysicsSystem":
            sz, = struct.unpack_from("<I", blk, 0)
            phys_bodies.extend(sfbodies.blob_bodies(blk[4 : 4 + sz]))
        elif tp == "BSGeometry":
            g = sfnif.parse_bsgeometry(blk)
            nm = nf.strings[g.name_idx].decode("latin-1") if 0 <= g.name_idx < len(nf.strings) else f"geom_{bi}"
            m0 = g.meshes[0]
            mesh_rel = normalize_rel(m0.path.decode("latin-1")) if (m0 and m0.path) else ""
            mat_raw = ""
            if 0 <= g.shader < len(nf.blocks) and nf.type_of(g.shader) == "BSLightingShaderProperty":
                si, = struct.unpack_from("<i", nf.blocks[g.shader], 0)
                if 0 <= si < len(nf.strings):
                    mat_raw = nf.strings[si].decode("latin-1")
            geom_info[bi] = {"name": nm, "mesh_rel": mesh_rel, "material": mat_raw, "shader_block": g.shader}

    node_to_shapes: Dict[str, List[str]] = {}
    shape_to_parent_node: Dict[str, str] = {}
    shape_to_parent_block: Dict[str, int] = {}
    node_parents: Dict[str, str] = {}
    node_world_m: Dict[str, Tuple[Tuple[float, float, float], Tuple[float, ...]]] = {}

    for bi, nm in node_names.items():
        w_tr, w_rot, _ = world_fn(bi)
        key = nm or f"node_{bi}"
        node_world_m[key] = (tuple(w_tr), tuple(w_rot))
        shapes_here: List[str] = []
        for ch in node_kids[bi]:
            if ch in node_names:
                ch_key = node_names[ch] or f"node_{ch}"
                node_parents[ch_key] = key
            elif ch in geom_info:
                gnm = str(geom_info[ch]["name"])
                shapes_here.append(gnm)
                shape_to_parent_node[gnm] = key
                shape_to_parent_block[gnm] = bi
        if shapes_here:
            node_to_shapes.setdefault(key, []).extend(shapes_here)

    return {
        "root_name": node_names.get(0, ""),
        "node_names": [nm for nm in node_names.values() if nm],
        "all_nodes_have_sgo_keep": all(node_sgo.values()),
        "node_parents": node_parents,
        "node_to_shapes": node_to_shapes,
        "shape_to_parent_node": shape_to_parent_node,
        "shape_to_parent_block": shape_to_parent_block,
        "node_world_m": node_world_m,
        "geometries": geom_info,
        "shape_count": len(geom_info),
        "physics_bodies": [{"shape": b["shape"], "layer": b["layer"]} for b in phys_bodies],
    }


def _extract_mat_texture_paths(mat_json_text: str) -> List[str]:
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
            if not norm.startswith("textures/"):
                norm = "textures/" + norm
            found.append(norm)

    walk(data)
    return sorted(set(found))


REQUIRED_MOVING_SHAPE_PARENTS: Dict[str, Dict[str, str]] = {
    "10mm": {
        "Pistol10mmBolt:0": "MiscA06",
        "Magazine:0": "Magazine",
        "10mmTrigger:0": "TRIGGER",
        "Pistol10mmHammer:0": "WeaponExtra2",
    },
    "lasermusket": {
        "LaserMusketCrank:0": "WeaponMagazine",
        "LaserMusketTrigger:0": "TRIGGER",
        "LaserMusketRotor:0": "WeaponExtra2",
    },
    "minigun": {
        "Minigun_Barrel:0": "Minigun_Barrel",
        "Minigun_AmmoDrum:0": "Minigun_AmmoDrum",
    },
    "pipepistol": {
        "PipeRifleBolt:0": "MiscB",
        "PipeRifleTrigger:0": "TRIGGER",
        "PipeRifle45Mag001:0": "Magazine",
    },
    "piperifle": {
        "PipeRifleBolt:0": "MiscA",
        "PipeRifleTrigger:0": "TRIGGER",
        "PipeRifle45Mag001:0": "Magazine",
    },
    "piperevolver": {
        "RevolverCatch:1": "Bolt",
        "RevolverCylinderPivot:1": "Magazine",
        "RevolverTrigger:1": "TRIGGER",
    },
    "huntingrifle": {
        "HuntingRifleBolt:0": "MiscA",
        "308MagSmall:0": "Magazine",
        "HuntingRifleTrigger:0": "TRIGGER",
    },
    "combatshotgun": {
        "CombatShotgunBolt:0": "Bolt",
        "CombatShotgunSmallMag:0": "Magazine",
    },
    "doublebarrel": {
        "ShotgunStock:0": "MiscA",
        "ShotgunTrigger:0": "TRIGGER",
    },
    "submachinegun": {
        "TGunBolt:0": "Bolt",
        "TGunTrigger:0": "TRIGGER",
        "TGunDrumMagSmall:0": "Magazine",
    },
    "assaultrifle": {
        "MachineGunMagStraight:3": "Magazine",
        "MachineGunCarryHandle:0": "WeaponExtra1",
    },
    "laserpistol": {
        "LaserRifleBolt:0": "MiscA",
        "LaserRifleMicrofusionCell:0": "Magazine",
    },
    "laserrifle": {
        "LaserRifleBolt:0": "MiscB",
        "LaserRifleMicrofusionCell:0": "Magazine",
    },
    "missilelauncher": {
        "MissileLauncherTrigger:0": "TRIGGER",
    },
    "fatman": {
        "FatManBolt:0": "Bolt",
        "FatManSled:0": "Magazine",
        "FatManTrigger:0": "TRIGGER",
    },
    "flamer": {
        "FlamerSideTank:1": "Magazine",
    },
    "plasmapistol": {
        "PlasmaValve6:0": "TRIGGER",
        "PlasmaCellMagazineNew:0": "Magazine",
    },
    "plasmarifle": {
        "PlasmaValve6:0": "TRIGGER",
        "PlasmaCellMagazineNew:0": "Magazine",
    },
    "gaussrifle": {
        "GaussRifleBolt:0": "MiscA",
        "GaussRifleMagazine:0": "Magazine",
        "GaussRifleTrigger:0": "TRIGGER",
    },
}

REQUIRED_NODE_PARENTS: Dict[str, Dict[str, str]] = {
    "minigun": {
        "BarrelRoot": "MiscA01",
        "Minigun_Barrel": "BarrelRoot",
        "Minigun_AmmoDrum": "Magazine",
    },
    "doublebarrel": {
        "Shotgun_Barrel_Medium": "MiscA",
    },
}

FORBIDDEN_EMPTY_HELPER_NODES: Dict[str, Tuple[str, ...]] = {
    "10mm": ("WeaponBolt", "WeaponMagazine", "WeaponTrigger", "Bolt"),
    "lasermusket": ("WeaponTrigger", "Magazine", "Bolt"),
    "minigun": ("WeaponBolt", "WeaponMagazine", "Bolt", "TRIGGER"),
    "baton": ("TRIGGER", "Magazine", "Bolt"),
}


def verify_nif_asset_tree(
    staging_root: str,
    nif_rel_path: str,
    *,
    weapon_key: Optional[str] = None,
    require_converted_materials: bool = True,
    require_collision: bool = True,
) -> Dict[str, object]:
    """Verify a staged Starfield BS-173 weapon, ammo, core-item, or projectile NIF and assets."""
    nif_disk = os.path.join(staging_root, *normalize_rel(nif_rel_path).split("/"))
    if not os.path.isfile(nif_disk):
        raise StageWeaponsError(f"missing staged NIF: {nif_rel_path}")
    with open(nif_disk, "rb") as fh:
        raw = fh.read()

    info = inspect_weapon_nif_hierarchy(raw)
    if info["shape_count"] == 0:
        raise StageWeaponsError(f"{nif_rel_path}: contains zero BSGeometry blocks")
    if require_collision and not info["physics_bodies"]:
        raise StageWeaponsError(f"{nif_rel_path}: missing Havok bhkPhysicsSystem body")

    if weapon_key is not None:
        if info["root_name"] != "WEAPON":
            raise StageWeaponsError(f"{nif_rel_path}: expected root NiNode 'WEAPON', got {info['root_name']!r}")
        if not info["all_nodes_have_sgo_keep"]:
            raise StageWeaponsError(f"{nif_rel_path}: one or more weapon NiNodes lack NiStringExtraData sgoKeep")
        if "ProjectileNode" not in info["node_names"]:
            raise StageWeaponsError(f"{nif_rel_path}: missing required ProjectileNode")
        # Enforce non-flattened hierarchy: zero BSGeometry directly on root WEAPON!
        if "WEAPON" in info["node_to_shapes"]:
            raise StageWeaponsError(
                f"{nif_rel_path}: moving/part BSGeometry flattened directly onto root WEAPON: "
                f"{info['node_to_shapes']['WEAPON']}"
            )
        for sh_nm, want_parent in REQUIRED_MOVING_SHAPE_PARENTS.get(weapon_key, {}).items():
            got_parent = info["shape_to_parent_node"].get(sh_nm)
            if got_parent != want_parent:
                raise StageWeaponsError(
                    f"{nif_rel_path}: shape {sh_nm!r} parent {got_parent!r} != expected moving-part NiNode {want_parent!r}"
                )
        for ch_nm, want_parent in REQUIRED_NODE_PARENTS.get(weapon_key, {}).items():
            got_parent = info["node_parents"].get(ch_nm)
            if got_parent != want_parent:
                raise StageWeaponsError(
                    f"{nif_rel_path}: node {ch_nm!r} parent {got_parent!r} != expected {want_parent!r}"
                )
        for forb in FORBIDDEN_EMPTY_HELPER_NODES.get(weapon_key, ()):
            if forb in info["node_names"] and not info["node_to_shapes"].get(forb):
                # Allow parent nodes like ShotgunBarrelMedium only if they hold children; forbidden nodes must not exist
                raise StageWeaponsError(
                    f"{nif_rel_path}: forbidden empty duplicate helper NiNode {forb!r} present"
                )
        if weapon_key in ("baton", "baseballbat"):
            for sh_nm in info["shape_to_parent_node"]:
                if "blood" in sh_nm.lower():
                    raise StageWeaponsError(f"{nif_rel_path}: unskipped blood overlay shape {sh_nm!r}")

    missing_meshes: List[str] = []
    missing_mats: List[str] = []
    missing_dds: List[str] = []
    checked_mats: List[str] = []

    for bi, ginfo in info["geometries"].items():
        mrel = str(ginfo["mesh_rel"])
        if not mrel:
            raise StageWeaponsError(f"{nif_rel_path}: BSGeometry [{bi}] lacks LOD0 .mesh path")
        mesh_rel = f"geometries/{mrel}.mesh"
        if not os.path.isfile(os.path.join(staging_root, *mesh_rel.split("/"))):
            missing_meshes.append(mesh_rel)

        mat_raw = str(ginfo["material"])
        if not mat_raw:
            raise StageWeaponsError(f"{nif_rel_path}: BSGeometry [{bi}] lacks BSLightingShaderProperty material")
        mat_rel = normalize_rel(mat_raw)
        if mat_rel.startswith("data/"):
            mat_rel = mat_rel[5:]
        if not mat_rel.startswith("materials/"):
            mat_rel = "materials/" + mat_rel
        for tok in FORBIDDEN_SF_DONOR_MATERIAL_TOKENS:
            if "/" in tok or "\\" in tok:
                norm_tok = tok.replace("\\", "/")
                if f"/{norm_tok}/" in mat_rel or f"/{norm_tok}." in mat_rel:
                    raise StageWeaponsError(f"{nif_rel_path}: forbidden Starfield donor material leak {mat_raw!r}")
            elif tok in mat_rel:
                raise StageWeaponsError(f"{nif_rel_path}: forbidden Starfield donor material leak {mat_raw!r}")
        checked_mats.append(mat_rel)
        if require_converted_materials or not mat_rel.startswith("materials/common/"):
            mat_disk = os.path.join(staging_root, *mat_rel.split("/"))
            if not os.path.isfile(mat_disk):
                missing_mats.append(mat_rel)
            else:
                with open(mat_disk, encoding="utf-8") as mfh:
                    mat_txt = mfh.read()
                for tex_rel in _extract_mat_texture_paths(mat_txt):
                    if not os.path.isfile(os.path.join(staging_root, *tex_rel.split("/"))):
                        missing_dds.append(tex_rel)

    if missing_meshes or missing_mats or missing_dds:
        raise StageWeaponsError(
            f"{nif_rel_path} has missing staged references: "
            f"meshes={sorted(set(missing_meshes))}, mats={sorted(set(missing_mats))}, dds={sorted(set(missing_dds))}"
        )

    return {
        "nif": nif_rel_path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "bs_geometry_count": info["shape_count"],
        "physics_bodies": info["physics_bodies"],
        "node_names": info["node_names"],
        "node_parents": info["node_parents"],
        "node_to_shapes": info["node_to_shapes"],
        "materials": sorted(set(checked_mats)),
        "missing_meshes": [],
        "missing_mats": [],
        "missing_dds": [],
    }


def verify_staged_weapons(
    staging_root: str,
    *,
    require_converted_materials: bool = True,
    require_collision: bool = True,
    require_all_arsenal: Optional[bool] = None,
) -> Dict[str, object]:
    """Verify staged weapon, ammo, core-item, and projectile NIFs under `staging_root`."""
    if require_all_arsenal is None:
        require_all_arsenal = os.path.isfile(
            os.path.join(staging_root, *WEAPON_NIF_RELS["pipepistol"].split("/"))
        )

    weapon_keys = list(WEAPON_NIF_RELS.keys()) if require_all_arsenal else list(P5_WEAPON_KEYS)
    ammo_keys = list(AMMO_NIF_RELS.keys()) if require_all_arsenal else list(P5_AMMO_KEYS)

    weapons_rep: Dict[str, object] = {}
    for wkey in weapon_keys:
        wrel = WEAPON_NIF_RELS[wkey]
        weapons_rep[wkey] = verify_nif_asset_tree(
            staging_root,
            wrel,
            weapon_key=wkey,
            require_converted_materials=require_converted_materials,
            require_collision=require_collision,
        )
    ammo_rep: Dict[str, object] = {}
    for akey in ammo_keys:
        arel = AMMO_NIF_RELS[akey]
        ammo_rep[akey] = verify_nif_asset_tree(
            staging_root,
            arel,
            weapon_key=None,
            require_converted_materials=require_converted_materials,
            require_collision=require_collision,
        )

    core_rep: Dict[str, object] = {}
    proj_rep: Dict[str, object] = {}
    if require_all_arsenal:
        for ckey, crel in CORE_ITEM_NIF_RELS.items():
            core_rep[ckey] = verify_nif_asset_tree(
                staging_root,
                crel,
                weapon_key=None,
                require_converted_materials=require_converted_materials,
                require_collision=require_collision,
            )
        for pkey, prel in PROJ_NIF_RELS.items():
            proj_rep[pkey] = verify_nif_asset_tree(
                staging_root,
                prel,
                weapon_key=None,
                require_converted_materials=require_converted_materials,
                require_collision=require_collision,
            )

    return {
        "weapons": weapons_rep,
        "ammo": ammo_rep,
        "core_items": core_rep,
        "projectiles": proj_rep,
        "standin_disclosure": STANDIN_DISCLOSURE,
    }


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
    raise StageWeaponsError("Starfield donor NIF contains no bhkPhysicsSystem")


def _read_donor_weapon_collision(sf_data: str, weapon_key: str) -> Tuple[str, bytes]:
    for cand in SF_DONOR_COLLISION_NIFS[weapon_key]:
        try:
            raw = read_sf_mesh_ba2(sf_data, cand)
            blob = extract_first_physics_blob(raw)
            if not sfbodies.blob_bodies(blob):
                continue
            return cand, blob
        except (FileNotFoundError, StageWeaponsError, nifmod.NifError, sfbodies.BodyError):
            continue
    raise StageWeaponsError(f"could not locate Starfield donor collision NIF for {weapon_key}")


def _discover_sf_tools(
    sf_data: str,
    content_resources: Optional[str],
    texconv: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
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


def stage_r11_weapons(
    fo4_data: str,
    sf_data: str,
    staging: str,
    content_resources: Optional[str] = None,
    texconv: Optional[str] = None,
    scope: str = "all",
) -> Dict[str, object]:
    """Convert and stage FO4 P5 (+ Rows 5-20 arsenal when scope='all') weapons, ammo, core items, and controller sidecars."""
    from fo4sf import pipeline, textures

    require_starfield_not_running()
    refuse_unsafe_staging_dir(staging, fo4_data=fo4_data, sf_data=sf_data)

    cr_zip, tc_exe = _discover_sf_tools(sf_data, content_resources, texconv)
    if not cr_zip or not tc_exe:
        raise StageWeaponsError(
            f"ContentResources.zip ({cr_zip}) and texconv/xtexconv.exe ({tc_exe}) are required for staging"
        )

    parent = os.path.dirname(os.path.abspath(staging))
    os.makedirs(parent, exist_ok=True)
    partial = tempfile.mkdtemp(prefix=os.path.basename(os.path.abspath(staging)) + ".partial-", dir=parent)
    orig_texconv = textures.texconv
    textures.texconv = _run_texconv_cp437_safe
    try:
        src = pipeline.Fo4Archives(fo4_data)

        box_coll_blob: Optional[bytes] = None
        for cand in SF_BOX_COLLISION_CANDIDATES:
            try:
                box_coll_blob = convert_static.collision_template_from_nif(read_sf_mesh_ba2(sf_data, cand))
                break
            except (FileNotFoundError, nifmod.NifError, ValueError):
                continue
        if box_coll_blob is None:
            raise StageWeaponsError("could not locate vanilla box collision template in Starfield - Meshes*.ba2")

        dyn_coll_blob = meshcollision.check_dynamic_template(
            extract_first_physics_blob(read_sf_mesh_ba2(sf_data, meshcollision.DYNAMIC_TEMPLATE_NIF))
        )

        conv_weap = pipeline.Converter(
            src,
            partial,
            tc_exe,
            cr_zip,
            collision_template=box_coll_blob,
            dynamic_template=dyn_coll_blob,
            prefix="fo4sf",
        )

        wkeys = list(P5_WEAPON_KEYS) if scope == "p5" else list(WEAPON_NIF_RELS.keys())
        akeys = list(P5_AMMO_KEYS) if scope == "p5" else list(AMMO_NIF_RELS.keys())

        donor_colls: Dict[str, Tuple[str, bytes]] = {
            wkey: _read_donor_weapon_collision(sf_data, wkey)
            for wkey in wkeys
        }

        built_weapons: Dict[str, HierarchicalWeaponResult] = {}

        # P5 Core Weapons (0x000899..0x0008A0) with F1/F3/F6 fixes
        p10_rec_rel, p10_rec = _read_fo4_mesh_with_fallback(
            src, "meshes/weapons/10mmpistol/10mmpistol_1.nif", "meshes/weapons/10mmpistol/10mmpistol.nif"
        )
        p10_grp_rel, p10_grip = _read_fo4_mesh_with_fallback(
            src, "meshes/weapons/10mmpistol/10mmgrip_1.nif", "meshes/weapons/10mmpistol/10mmgrip.nif"
        )
        p10_mag_rel, p10_mag = _read_fo4_mesh_with_fallback(
            src, "meshes/weapons/10mmpistol/10mmmag01_1.nif", "meshes/weapons/10mmpistol/10mmmag01.nif"
        )
        built_weapons["10mm"] = build_10mm_weapon(
            p10_rec,
            p10_grip,
            p10_mag,
            conv=conv_weap,
            weapon_collision_blob=donor_colls["10mm"][1],
            source_labels=(p10_rec_rel, p10_grp_rel, p10_mag_rel),
        )

        baton_src_rel, baton_bytes = _read_fo4_mesh_with_fallback(
            src, "meshes/weapons/baton/baton.nif", "meshes/weapons/baton/baton_1.nif"
        )
        built_weapons["baton"] = build_baton_weapon(
            baton_bytes,
            conv=conv_weap,
            weapon_collision_blob=donor_colls["baton"][1],
            source_labels=(baton_src_rel,),
        )

        lm_r_rel, lm_rec = _read_fo4_mesh_with_fallback(src, "meshes/weapons/lasermusket/lasermusket.nif")
        lm_g_rel, lm_grip = _read_fo4_mesh_with_fallback(src, "meshes/weapons/lasermusket/lasermusketmareslegstock.nif")
        lm_b_rel, lm_bar = _read_fo4_mesh_with_fallback(src, "meshes/weapons/lasermusket/lasermusketcompact.nif")
        lm_s_rel, lm_sights = _read_fo4_mesh_with_fallback(src, "meshes/weapons/lasermusket/lasermusketironssights.nif")
        built_weapons["lasermusket"] = build_laser_musket_weapon(
            lm_rec,
            lm_grip,
            lm_bar,
            lm_sights,
            conv=conv_weap,
            weapon_collision_blob=donor_colls["lasermusket"][1],
            source_labels=(lm_r_rel, lm_g_rel, lm_b_rel, lm_s_rel),
        )

        mg_r_rel, mg_rec = _read_fo4_mesh_with_fallback(
            src, "meshes/weapons/minigun/minigun_1.nif", "meshes/weapons/minigun/minigun.nif"
        )
        mg_b_rel, mg_bar = _read_fo4_mesh_with_fallback(
            src, "meshes/weapons/minigun/minigunbarrel_1.nif", "meshes/weapons/minigun/minigunbarrel.nif"
        )
        built_weapons["minigun"] = build_minigun_weapon(
            mg_rec,
            mg_bar,
            conv=conv_weap,
            weapon_collision_blob=donor_colls["minigun"][1],
            source_labels=(mg_r_rel, mg_b_rel),
        )

        # Rows 5-20 Arsenal Weapons
        if scope != "p5":
            for wkey, wspec in ARSENAL_WEAPON_SPECS.items():
                r_rel, r_bytes = _read_fo4_mesh_with_fallback(src, wspec.receiver_nif)
                part_bytes_list: List[bytes] = []
                part_labels: List[str] = [r_rel]
                for pspec in wspec.parts:
                    p_rel, p_bytes = _read_fo4_mesh_with_fallback(src, pspec.fo4_nif, pspec.fallback_nif)
                    part_bytes_list.append(p_bytes)
                    part_labels.append(p_rel)
                built_weapons[wkey] = build_arsenal_weapon_from_spec(
                    wspec,
                    r_bytes,
                    part_bytes_list,
                    conv=conv_weap,
                    weapon_collision_blob=donor_colls[wkey][1],
                    source_labels=part_labels,
                )

        controllers_rels: Dict[str, str] = {}
        for wkey, wres in built_weapons.items():
            wdst = os.path.join(partial, *WEAPON_NIF_RELS[wkey].split("/"))
            pipeline.write_staged(wdst, wres.nif_bytes)
            for (d_hex, f_hex), mbytes in wres.meshes.items():
                mdst = os.path.join(partial, "geometries", d_hex, f"{f_hex}.mesh")
                pipeline.write_staged(mdst, mbytes)
            # F6: write per-weapon controller sidecar next to weapon NIF
            ctrl_rel = os.path.splitext(WEAPON_NIF_RELS[wkey])[0] + "_controllers.json"
            controllers_rels[wkey] = ctrl_rel
            cdst = os.path.join(partial, *ctrl_rel.split("/"))
            os.makedirs(os.path.dirname(cdst), exist_ok=True)
            with open(cdst, "w", encoding="utf-8") as cfh:
                json.dump(wres.controllers, cfh, indent=2)
                cfh.write("\n")

        # Convert Fallout 4 ammo, core items, and explosive projectiles
        conv_ammo = pipeline.Converter(
            src,
            partial,
            tc_exe,
            cr_zip,
            collision_template=box_coll_blob,
            dynamic_template=dyn_coll_blob,
            prefix="fo4core",
        )
        for akey in akeys:
            fo4_ammo_nif = FO4_AMMO_SOURCES[akey]
            ares = conv_ammo.convert_nif(fo4_ammo_nif)
            if not ares.get("ok"):
                raise StageWeaponsError(f"failed to convert {akey} ammo NIF ({fo4_ammo_nif}): {ares}")

        if scope != "p5":
            for ckey, fo4_core_nif in FO4_CORE_ITEM_SOURCES.items():
                cres = conv_ammo.convert_nif(fo4_core_nif)
                if not cres.get("ok"):
                    raise StageWeaponsError(f"failed to convert core item {ckey} NIF ({fo4_core_nif}): {cres}")
            for pkey, fo4_proj_nif in FO4_PROJ_SOURCES.items():
                pres = conv_weap.convert_nif(fo4_proj_nif)
                if not pres.get("ok"):
                    raise StageWeaponsError(f"failed to convert projectile {pkey} NIF ({fo4_proj_nif}): {pres}")

        for unused_prefix, c_obj in (("fo4sf", conv_weap), ("fo4core", conv_ammo)):
            if c_obj.stats["materials_fallback"] == 0:
                n_mat = os.path.join(partial, "materials", unused_prefix, "_neutral.mat")
                if os.path.isfile(n_mat):
                    os.remove(n_mat)
                for kind in ("color", "normal", "rough"):
                    n_tex = os.path.join(partial, "textures", unused_prefix, f"_neutral_{kind}.dds")
                    if os.path.isfile(n_tex):
                        os.remove(n_tex)

        verification = verify_staged_weapons(
            partial,
            require_converted_materials=True,
            require_collision=True,
            require_all_arsenal=(scope != "p5"),
        )
        manifest = {
            "round": "R12P6-Arsenal" if scope != "p5" else "R11P3-Step-4",
            "scope": scope,
            "status": "OFFLINE ONLY - UNPROVEN IN GAME",
            "baton_fo4_source": baton_src_rel,
            "standin_disclosure": STANDIN_DISCLOSURE,
            "sf_donors": {
                wkey: {"collision_nif": donor_colls[wkey][0]}
                for wkey in wkeys
            },
            "weapons": {
                wkey: {
                    "nif_rel": WEAPON_NIF_RELS[wkey],
                    "controllers_rel": controllers_rels[wkey],
                    "controller_block_count": wres.controllers.get("total_controller_blocks", 0),
                    "controller_sequences": [
                        seq["name"]
                        for src_info in wres.controllers.get("sources", [])
                        for seq in src_info.get("sequences", [])
                    ],
                    "fo4_part_map": wres.fo4_part_map,
                    "shape_count": len(wres.shape_names),
                    "skipped_shapes": wres.skipped_shapes,
                    "bounds_min_m": [round(x, 5) for x in wres.bounds_min_m],
                    "bounds_max_m": [round(x, 5) for x in wres.bounds_max_m],
                    "named_nodes_m": {k: [round(c, 5) for c in v] for k, v in wres.named_nodes_m.items()},
                    "node_parents": wres.node_parents,
                    "node_to_shapes": wres.node_to_shapes,
                }
                for wkey, wres in built_weapons.items()
            },
            "verification": verification,
        }
        # Preserve detailed donor citations on P5 records inside manifest
        manifest["sf_donors"]["10mm"].update({"weap": "Starfield.esm:0x24561C (XM2311)", "ammo": "Starfield.esm:0x2B5598 (Ammo45Caliber)"})
        manifest["sf_donors"]["baton"].update({"weap": "Starfield.esm:0x04F760 (RescueAxe)"})
        manifest["sf_donors"]["lasermusket"].update({"weap": "Starfield.esm:0x2773C8 (Orion)", "ammo": "Starfield.esm:0x00E8EC (AmmoLaser)"})
        manifest["sf_donors"]["minigun"].update({"weap": "Starfield.esm:0x0546CD (Microgun)", "ammo": "Starfield.esm:0x04AD3E (Ammo777mm)"})

        with open(os.path.join(partial, "r11_weapons_manifest.json"), "w", encoding="utf-8") as mfh:
            json.dump(manifest, mfh, indent=2)
            mfh.write("\n")

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
    ap = argparse.ArgumentParser(description="Stage or verify Fallout 4 Step 4 / Probe P5 + Rows 5-20 arsenal.")
    sub = ap.add_subparsers(dest="cmd")

    p_stage = sub.add_parser("stage", help="Convert and stage FO4 weapons, ammo, core items & controller sidecars")
    p_stage.add_argument("--fo4-data", required=True, help="Path to Fallout 4 Data directory")
    p_stage.add_argument("--sf-data", required=True, help="Path to Starfield Data directory")
    p_stage.add_argument("--out", "--staging", dest="out_dir", required=True, help="Empty external output directory")
    p_stage.add_argument("--content-resources", default=None, help="Optional path to ContentResources.zip")
    p_stage.add_argument("--texconv", default=None, help="Optional path to xtexconv.exe / texconv.exe")
    p_stage.add_argument("--scope", choices=("all", "p5"), default="all", help="Weapon/ammo scope to stage (default: all)")

    p_ver = sub.add_parser("verify", help="Verify an existing staged weapon/ammo directory")
    p_ver.add_argument("--stage-dir", "--out", dest="stage_dir", required=True, help="Staged assets directory")
    p_ver.add_argument("--all-arsenal", action="store_true", default=None, help="Require all Rows 5-20 assets")

    args = ap.parse_args(argv)
    if args.cmd == "stage":
        manifest = stage_r11_weapons(
            args.fo4_data,
            args.sf_data,
            args.out_dir,
            content_resources=args.content_resources,
            texconv=args.texconv,
            scope=args.scope,
        )
        counts = {k: v["shape_count"] for k, v in manifest["weapons"].items()}
        print(f"staged FO4 arsenal ({args.scope}) -> {args.out_dir} (weapons={len(counts)}, shapes={counts})")
        return 0
    if args.cmd == "verify":
        rep = verify_staged_weapons(args.stage_dir, require_all_arsenal=args.all_arsenal)
        print(f"verified staged weapons ({len(rep['weapons'])}) + ammo ({len(rep['ammo'])}): {sorted(rep['weapons'].keys())}")
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
