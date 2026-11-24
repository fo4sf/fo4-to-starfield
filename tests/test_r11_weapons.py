"""Offline cross-OS tests for Round 11 Part 3 Step 4 (Hierarchical FO4 Weapons & CoreValues P5).

Covers:
  1. Hierarchical NiNode -> BSGeometry assembly for all 4 weapons (10mm Pistol, Baton with +Z
     melee frame & telescoping segments, 4-part short Laser Musket, and Minigun with rotating
     6-barrel cluster & ammo drum) + scene-graph world-vertex invariant (W_node * v_local == v_world).
  2. Shader/overlay filtering: skips BatonMergedBlood:0 (BloodWeapon.BGSM), Laser Musket
     BSEffectShaderProperty glow/beam shells, and Minigun BaseRefractionMesh:0 (SLSF1_REFRACTION).
  3. Asset-tree verifier & negative tamper checks (flattened root BSGeometry, wrong moving-part
     parent, blood shell leak, donor material leaks for M1919/RescueAxe/Orion/Microgun, and
     missing .mesh/.mat/.dds files).
  4. Safety guards refusing repo, candidate-*, game-install/Data dirs, non-empty dirs, and
     running Starfield.exe.
  5. Binary FO4SFCoreValues.esm verification across all 9 weapon/ammo records (0x000898..0x0008A0),
     raw DAMA dtEnergy (30 / 18) with AttackDamage == 0 on Laser Muskets, NonPlayable flags on
     companion records (0x00089C / 0x00089E), [Starfield.esm] sole master, and --fo4-p5-weapons 0
     rollback.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[1]
SRC_DIR = REPO_ROOT / "src"
WEAPONS_DIR = REPO_ROOT / "scripts" / "weapons"

for _p in (str(REPO_ROOT), str(SRC_DIR), str(WEAPONS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import stage_r11_weapons as sw  # noqa: E402
from fo4sf import nif, sfmesh, sfnif  # noqa: E402
from fo4sf.core import cross_plugin_check as cpc  # noqa: E402

STAGE_WEAPONS_PY = WEAPONS_DIR / "stage_r11_weapons.py"
COREVALUES_CS = REPO_ROOT / "dotnet" / "CoreValues" / "Program.cs"

DRIVE_PATH_RX = re.compile(r"\b[A-Za-z]:[\\/]")
IDENT_ROT = sw.IDENT_ROT
QUAD_TRIS = [(0, 1, 2), (0, 2, 3)]


def _av_fields(
    name_idx: int,
    trans: tuple[float, float, float],
    rot: tuple[float, ...] = IDENT_ROT,
    scale: float = 1.0,
    extra_refs: tuple[int, ...] = (),
) -> bytes:
    return (
        struct.pack("<iI", name_idx, len(extra_refs))
        + (struct.pack(f"<{len(extra_refs)}i", *extra_refs) if extra_refs else b"")
        + struct.pack("<iI", -1, 0xE)
        + struct.pack("<3f", *trans)
        + struct.pack("<9f", *rot)
        + struct.pack("<fi", scale, -1)
    )


def _fo4_lighting_shader_block(mat_name_idx: int, sf1: int = 0, sf2: int = 0) -> bytes:
    # NiObjectNET (s_type=0, name_idx, nextra=0, controller=-1) + sf1, sf2 + uv_offset/scale + texset=-1
    return struct.pack("<IiIiiII4fi", 0, mat_name_idx, 0, -1, 0, sf1, sf2, 0.0, 0.0, 1.0, 1.0, -1)


def _fo4_effect_shader_block(name_idx: int) -> bytes:
    return struct.pack("<iIi", name_idx, 0, -1) + b"\x00" * 32


def _fo4_trishape_block(
    name_idx: int,
    pts: list[tuple[float, float, float]],
    tris: list[tuple[int, int, int]] = QUAD_TRIS,
    trans: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rot: tuple[float, ...] = IDENT_ROT,
    shader_ref: int = -1,
) -> bytes:
    vsize = 16 + 4 + 4 + 4
    desc = ((0x1 | 0x2 | 0x8 | 0x10 | 0x400) << 44) | (vsize // 4) | (4 << 8) | (5 << 16) | (6 << 20)
    verts = b"".join(
        struct.pack("<3ff", *p, 0.0)
        + struct.pack("<2e", 0.1 * idx, 0.2 * idx)
        + bytes([128, 128, 255, 128])
        + bytes([255, 128, 128, 128])
        for idx, p in enumerate(pts)
    )
    head = (
        _av_fields(name_idx, trans, rot, 1.0)
        + struct.pack("<4f", 0.0, 0.0, 0.0, 10.0)
        + struct.pack("<iii", -1, shader_ref, -1)
        + struct.pack("<Q", desc)
        + struct.pack("<IHI", len(tris), len(pts), vsize * len(pts) + 6 * len(tris))
    )
    return head + verts + b"".join(struct.pack("<HHH", *t) for t in tris)


def _connect_points_parents_block(
    name_idx: int,
    entries: list[tuple[bytes, bytes, tuple[float, float, float, float], tuple[float, float, float], float]],
) -> bytes:
    buf = bytearray(struct.pack("<iI", name_idx, len(entries)))
    for parent_b, cp_b, quat, tr, sc in entries:
        buf += struct.pack("<I", len(parent_b)) + parent_b
        buf += struct.pack("<I", len(cp_b)) + cp_b
        buf += struct.pack("<4f", *quat)
        buf += struct.pack("<4f", *tr, sc)
    return bytes(buf)


def _new_fo4_nif() -> nif.NifFile:
    return nif.NifFile(
        bs_version=130,
        author=b"t\x00",
        process_script=b"\x00",
        export_script=b"\x00",
        max_filepath=b"\x00",
    )


def _build_synthetic_baton_nif(include_blood_overlay: bool = True) -> bytes:
    """Synthetic FO4 baton.nif with 90-deg Y root rot, telescoping WeaponExtra1/2, and optional blood shell."""
    fn = _new_fo4_nif()
    # FO4 baton.nif root & BatonLowHandle have 90-deg Y rotation: (0,0,1, 0,1,0, -1,0,0)
    rot_y90 = (0.0, 0.0, 1.0, 0.0, 1.0, 0.0, -1.0, 0.0, 0.0)
    s_weap = fn.string_index(b"WEAPON")
    s_e1 = fn.string_index(b"WeaponExtra1")
    s_ext1 = fn.string_index(b"BatonLowExt01")
    s_e2 = fn.string_index(b"WeaponExtra2")
    s_ext2 = fn.string_index(b"BatonLowExt02")
    s_hdl = fn.string_index(b"BatonLowHandle")
    s_sh_e1 = fn.string_index(b"BatonLowExt01:0")
    s_sh_e2 = fn.string_index(b"BatonLowExt02:0")
    s_sh_hdl = fn.string_index(b"BatonLowHandle:0")
    s_mat = fn.string_index(b"Materials\\Weapons\\Baton\\Baton.BGSM")
    s_blood_nm = fn.string_index(b"BatonMergedBlood:0")
    s_blood_mat = fn.string_index(b"Materials\\Blood\\BloodWeapon.BGSM")

    hdl_kids = [8, 9] if include_blood_overlay else [8]
    # [0] WEAPON -> [1, 3, 5]
    fn.add_block("NiNode", _av_fields(s_weap, (0.0, 0.0, 0.0), rot_y90) + struct.pack("<I3i", 3, 1, 3, 5))
    # [1] WeaponExtra1 -> [2] BatonLowExt01 -> [6] BatonLowExt01:0
    fn.add_block("NiNode", _av_fields(s_e1, (0.0, 9.878, 0.0), IDENT_ROT) + struct.pack("<Ii", 1, 2))
    fn.add_block("NiNode", _av_fields(s_ext1, (0.0, 0.0, 0.0), IDENT_ROT) + struct.pack("<Ii", 1, 6))
    # [3] WeaponExtra2 -> [4] BatonLowExt02 -> [7] BatonLowExt02:0
    fn.add_block("NiNode", _av_fields(s_e2, (0.0, 22.8426, 0.0), IDENT_ROT) + struct.pack("<Ii", 1, 4))
    fn.add_block("NiNode", _av_fields(s_ext2, (0.0, 0.0, 0.0), IDENT_ROT) + struct.pack("<Ii", 1, 7))
    # [5] BatonLowHandle -> hdl_kids
    fn.add_block(
        "NiNode",
        _av_fields(s_hdl, (0.0, 0.0, 0.0), IDENT_ROT) + struct.pack(f"<I{len(hdl_kids)}i", len(hdl_kids), *hdl_kids),
    )
    # [6..8] opaque shapes + [10] Baton.BGSM shader
    shader_idx = 11 if include_blood_overlay else 9
    fn.add_block(
        "BSTriShape",
        _fo4_trishape_block(
            s_sh_e1,
            [(-0.75, 0.2, -0.75), (0.75, 0.2, -0.75), (0.75, 13.1, 0.75), (-0.75, 13.1, 0.75)],
            shader_ref=shader_idx,
        ),
    )
    fn.add_block(
        "BSTriShape",
        _fo4_trishape_block(
            s_sh_e2,
            [(-0.85, -0.4, -0.85), (0.85, -0.4, -0.85), (0.85, 13.45, 0.85), (-0.85, 13.45, 0.85)],
            shader_ref=shader_idx,
        ),
    )
    fn.add_block(
        "BSTriShape",
        _fo4_trishape_block(
            s_sh_hdl,
            [(-1.34, -7.126, -1.34), (1.34, -7.126, -1.34), (1.34, 10.37, 1.34), (-1.34, 10.37, 1.34)],
            shader_ref=shader_idx,
        ),
    )
    if include_blood_overlay:
        # [9] BatonMergedBlood:0 -> [10] BloodWeapon.BGSM, [11] Baton.BGSM
        fn.add_block(
            "BSTriShape",
            _fo4_trishape_block(
                s_blood_nm,
                [(-1.2, 8.0, -1.2), (1.2, 8.0, -1.2), (1.2, 36.3, 1.2), (-1.2, 36.3, 1.2)],
                shader_ref=10,
            ),
        )
        fn.add_block("BSLightingShaderProperty", _fo4_lighting_shader_block(s_blood_mat))
    fn.add_block("BSLightingShaderProperty", _fo4_lighting_shader_block(s_mat))
    fn.footer = struct.pack("<II", 1, 0)
    return nif.serialize(fn)


def _build_synthetic_lasermusket_nifs() -> tuple[bytes, bytes, bytes, bytes]:
    """Synthetic 4-part OBTS[0] Laser Musket with crank/trigger/rotor/magnets + BSEffectShaderProperty FX."""
    rec = _new_fo4_nif()
    s_weap = rec.string_index(b"WEAPON")
    s_cpa = rec.string_index(b"CPA")
    s_r = rec.string_index(b"LaserMusketReceiver")
    s_mag = rec.string_index(b"WeaponMagazine")
    s_trg = rec.string_index(b"WeaponTrigger")
    s_e1 = rec.string_index(b"WeaponExtra1")
    s_e2 = rec.string_index(b"WeaponExtra2")
    s_e3 = rec.string_index(b"WeaponExtra3")
    s_sc_d = rec.string_index(b"ScopeCameraDelta")
    s_sc_p = rec.string_index(b"ScopePOS")
    s_mat = rec.string_index(b"Materials\\Weapons\\LaserMusket\\LaserMusket.BGSM")
    s_fx = rec.string_index(b"Materials\\Weapons\\LaserMusket\\LaserMusketGlow.BGEM")

    # Blocks:
    #   [0] WEAPON (extra=[1], kids=[2])
    #   [1] BSConnectPoint::Parents (P-Grip, P-Barrel, P-Scope)
    #   [2] LaserMusketReceiver -> [3..9, 10 (LaserMusketFront:0), 16 (LaserMusketGlassCylinder:0 FX)]
    #   [3] WeaponMagazine -> [11 (LaserMusketCrank:0)]
    #   [4] WeaponTrigger  -> [12 (LaserMusketTrigger:0)]
    #   [5] WeaponExtra1   -> [13 (LaserMusketMagnet1:0)]
    #   [6] WeaponExtra2   -> [14 (LaserMusketRotor:0)]
    #   [7] WeaponExtra3   -> [15 (LaserMusketMagnet2:0)]
    #   [8] ScopeCameraDelta -> [9] ScopePOS
    #   [17] BSLightingShaderProperty, [18] BSEffectShaderProperty
    rec.add_block("NiNode", _av_fields(s_weap, (0.0, 0.0, 0.0), extra_refs=(1,)) + struct.pack("<Ii", 1, 2))
    rec.add_block(
        "BSConnectPoint::Parents",
        _connect_points_parents_block(
            s_cpa,
            [
                (b"LaserMusketReceiver", b"P-Grip", (1.0, 0.0, 0.0, 0.0), (0.0, -2.4581, -0.3723), 1.0),
                (b"LaserMusketReceiver", b"P-Barrel", (1.0, 0.0, 0.0, 0.0), (0.0, 21.5106, 6.3335), 1.0),
                (b"LaserMusketReceiver", b"P-Scope", (1.0, 0.0, 0.0, 0.0), (0.0, 19.6179, 9.9705), 1.0),
            ],
        ),
    )
    rec_kids = [3, 4, 5, 6, 7, 8, 10, 16]
    rec.add_block("NiNode", _av_fields(s_r, (0.0, 0.0, 0.0)) + struct.pack(f"<I{len(rec_kids)}i", len(rec_kids), *rec_kids))
    rec.add_block("NiNode", _av_fields(s_mag, (-5.1917, 2.6104, 5.5454)) + struct.pack("<Ii", 1, 11))
    rec.add_block("NiNode", _av_fields(s_trg, (-0.0121, 4.2790, -1.0906)) + struct.pack("<Ii", 1, 12))
    rec.add_block("NiNode", _av_fields(s_e1, (-0.0305, 5.6251, 5.5782)) + struct.pack("<Ii", 1, 13))
    rec.add_block("NiNode", _av_fields(s_e2, (-0.0321, 9.3519, 5.5740)) + struct.pack("<Ii", 1, 14))
    rec.add_block("NiNode", _av_fields(s_e3, (-0.0305, 10.7649, 5.5782)) + struct.pack("<Ii", 1, 15))
    rec.add_block("NiNode", _av_fields(s_sc_d, (0.0542, -9.4187, 11.7098)) + struct.pack("<Ii", 1, 9))
    rec.add_block("NiNode", _av_fields(s_sc_p, (-0.0542, 4.6111, 0.1573)) + struct.pack("<I", 0))

    for nm_b, y0 in (
        (b"LaserMusketFront:0", 0.0),
        (b"LaserMusketCrank:0", -4.0),
        (b"LaserMusketTrigger:0", 3.0),
        (b"LaserMusketMagnet1:0", 5.0),
        (b"LaserMusketRotor:0", 8.0),
        (b"LaserMusketMagnet2:0", 10.0),
    ):
        sid = rec.string_index(nm_b)
        rec.add_block(
            "BSTriShape",
            _fo4_trishape_block(
                sid,
                [(-2.0, y0, -2.0), (2.0, y0, -2.0), (2.0, y0 + 4.0, 4.0), (-2.0, y0 + 4.0, 4.0)],
                shader_ref=17,
            ),
        )
    # [16] BSEffectShaderProperty glass cylinder -> must be skipped!
    rec.add_block(
        "BSTriShape",
        _fo4_trishape_block(
            rec.string_index(b"LaserMusketGlassCylinder:0"),
            [(-3.5, 12.0, 2.0), (3.5, 12.0, 2.0), (3.5, 20.0, 9.0), (-3.5, 20.0, 9.0)],
            shader_ref=18,
        ),
    )
    rec.add_block("BSLightingShaderProperty", _fo4_lighting_shader_block(s_mat))
    rec.add_block("BSEffectShaderProperty", _fo4_effect_shader_block(s_fx))
    rec.footer = struct.pack("<II", 1, 0)

    # Stock/Grip NIF (maresleg)
    grp = _new_fo4_nif()
    grp.add_block("NiNode", _av_fields(grp.string_index(b"LaserMusketMaresLeg"), (0.0, 0.0, 0.0)) + struct.pack("<Ii", 1, 1))
    grp.add_block(
        "BSTriShape",
        _fo4_trishape_block(
            grp.string_index(b"LaserMusketMaresLeg:1"),
            [(-1.2, -7.0, -3.8), (1.2, -7.0, -3.8), (1.2, 6.3, 4.1), (-1.2, 6.3, 4.1)],
            shader_ref=2,
        ),
    )
    grp.add_block("BSLightingShaderProperty", _fo4_lighting_shader_block(grp.string_index(b"Materials\\Weapons\\LaserMusket\\Stock.BGSM")))
    grp.footer = struct.pack("<II", 1, 0)

    # Compact Barrel NIF with nested LaserMusketBarrelExtension2Lens + P-Muzzle + FrontGlowMesh:0 (FX -> skip!)
    bar = _new_fo4_nif()
    bar.add_block(
        "NiNode",
        _av_fields(bar.string_index(b"LaserRifleBarrelMusket004"), (0.0, 0.0, 0.0), extra_refs=(1,)) + struct.pack("<I2i", 2, 2, 3),
    )
    bar.add_block(
        "BSConnectPoint::Parents",
        _connect_points_parents_block(
            bar.string_index(b"CPA"),
            [(b"LaserMusketBarrelExtension2Lens", b"P-Muzzle", (1.0, 0.0, 0.0, 0.0), (0.0, 21.2275, 2.8422), 1.0)],
        ),
    )
    bar.add_block(
        "NiNode",
        _av_fields(bar.string_index(b"LaserMusketBarrelExtension2Lens"), (0.0, 22.7469, -3.6842)) + struct.pack("<I2i", 2, 4, 5),
    )
    bar.add_block(
        "BSTriShape",
        _fo4_trishape_block(
            bar.string_index(b"LaserRifleBarrelMusket004:0"),
            [(-1.0, 0.0, -2.0), (1.0, 0.0, -2.0), (1.0, 22.0, 2.0), (-1.0, 22.0, 2.0)],
            shader_ref=6,
        ),
    )
    bar.add_block(
        "BSTriShape",
        _fo4_trishape_block(
            bar.string_index(b"LaserMusketBarrelExtension2Lens:0"),
            [(-2.5, 0.0, -2.5), (2.5, 0.0, -2.5), (2.5, 21.2, 1.5), (-2.5, 21.2, 1.5)],
            shader_ref=6,
        ),
    )
    bar.add_block(
        "BSTriShape",
        _fo4_trishape_block(
            bar.string_index(b"FrontGlowMesh:0"),
            [(-8.0, 0.0, -5.0), (8.0, 0.0, -5.0), (8.0, 25.0, 7.0), (-8.0, 25.0, 7.0)],
            shader_ref=7,
        ),
    )
    bar.add_block("BSLightingShaderProperty", _fo4_lighting_shader_block(bar.string_index(b"Materials\\Weapons\\LaserMusket\\Barrel.BGSM")))
    bar.add_block("BSEffectShaderProperty", _fo4_effect_shader_block(bar.string_index(b"GlowFX")))
    bar.footer = struct.pack("<II", 1, 0)

    # Iron Sights NIF
    sgt = _new_fo4_nif()
    sgt.add_block("NiNode", _av_fields(sgt.string_index(b"LaserMusketIronSight"), (0.0, 0.0, 0.0)) + struct.pack("<Ii", 1, 1))
    sgt.add_block(
        "BSTriShape",
        _fo4_trishape_block(
            sgt.string_index(b"LaserMusketIronSight:0"),
            [(-1.0, -0.5, 0.0), (1.0, -0.5, 0.0), (1.0, 0.2, 3.6), (-1.0, 0.2, 3.6)],
            shader_ref=2,
        ),
    )
    sgt.add_block("BSLightingShaderProperty", _fo4_lighting_shader_block(sgt.string_index(b"Materials\\Weapons\\LaserMusket\\Sight.BGSM")))
    sgt.footer = struct.pack("<II", 1, 0)

    return nif.serialize(rec), nif.serialize(grp), nif.serialize(bar), nif.serialize(sgt)


def _build_synthetic_minigun_nifs() -> tuple[bytes, bytes]:
    """Synthetic Minigun receiver + 6-barrel cluster with SLSF1_REFRACTION heat-haze billboard."""
    rec = _new_fo4_nif()
    rec.add_block("NiNode", _av_fields(rec.string_index(b"WEAPON"), (0.0, 0.0, 0.0), extra_refs=(1,)) + struct.pack("<I3i", 3, 2, 3, 5))
    rec.add_block(
        "BSConnectPoint::Parents",
        _connect_points_parents_block(
            rec.string_index(b"CPA"),
            [(b"WeaponBolt", b"P-Barrel", (1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 1.0)],
        ),
    )
    # [2] Minigun001 -> [6 (Minigun001:0), 7 (AmmoBelt:0)]
    rec.add_block("NiNode", _av_fields(rec.string_index(b"Minigun001"), (-6.8736, 18.5639, -14.0634)) + struct.pack("<I2i", 2, 6, 7))
    # [3] WeaponMagazine -> [4] Minigun_AmmoDrum -> [8 (Minigun_AmmoDrum:0)]
    rec.add_block("NiNode", _av_fields(rec.string_index(b"WeaponMagazine"), (-8.5868, 4.0082, -23.1810)) + struct.pack("<Ii", 1, 4))
    rec.add_block("NiNode", _av_fields(rec.string_index(b"Minigun_AmmoDrum"), (0.0, 11.2317, 0.0)) + struct.pack("<Ii", 1, 8))
    # [5] WeaponBolt
    rec.add_block("NiNode", _av_fields(rec.string_index(b"WeaponBolt"), (-8.5868, 35.4299, -1.0234)) + struct.pack("<I", 0))
    for nm_b, y0 in ((b"Minigun001:0", -8.0), (b"AmmoBelt:0", 4.0), (b"Minigun_AmmoDrum:0", -5.0)):
        rec.add_block(
            "BSTriShape",
            _fo4_trishape_block(
                rec.string_index(nm_b),
                [(-6.0, y0, -6.0), (6.0, y0, -6.0), (6.0, y0 + 18.0, 8.0), (-6.0, y0 + 18.0, 8.0)],
                shader_ref=9,
            ),
        )
    rec.add_block("BSLightingShaderProperty", _fo4_lighting_shader_block(rec.string_index(b"Materials\\Weapons\\Minigun\\Minigun.BGSM")))
    rec.footer = struct.pack("<II", 1, 0)

    # Barrel NIF: BarrelRoot -> [Minigun_Barrel -> Minigun_Barrel:0, BaseRefractionMesh -> BaseRefractionMesh:0]
    bar = _new_fo4_nif()
    bar.add_block("NiNode", _av_fields(bar.string_index(b"BarrelRoot"), (0.0, 0.0, 0.0)) + struct.pack("<I2i", 2, 1, 2))
    bar.add_block("NiNode", _av_fields(bar.string_index(b"Minigun_Barrel"), (0.0, 0.0, 0.0)) + struct.pack("<Ii", 1, 3))
    bar.add_block("NiNode", _av_fields(bar.string_index(b"BaseRefractionMesh"), (0.0434, 47.4404, 0.9418)) + struct.pack("<Ii", 1, 4))
    bar.add_block(
        "BSTriShape",
        _fo4_trishape_block(
            bar.string_index(b"Minigun_Barrel:0"),
            [(-5.9, 0.0, -5.9), (5.9, 0.0, -5.9), (5.9, 49.25, 5.9), (-5.9, 49.25, 5.9)],
            shader_ref=5,
        ),
    )
    bar.add_block(
        "BSTriShape",
        _fo4_trishape_block(
            bar.string_index(b"BaseRefractionMesh:0"),
            [(-20.0, 38.0, -34.0), (20.0, 38.0, -34.0), (20.0, 48.0, 14.0), (-20.0, 48.0, 14.0)],
            shader_ref=6,
        ),
    )
    bar.add_block("BSLightingShaderProperty", _fo4_lighting_shader_block(bar.string_index(b"Materials\\Weapons\\Minigun\\Barrel.BGSM")))
    bar.add_block(
        "BSLightingShaderProperty",
        _fo4_lighting_shader_block(bar.string_index(b"Materials\\Effects\\Refraction.BGSM"), sf1=sw.SLSF1_REFRACTION),
    )
    bar.footer = struct.pack("<II", 1, 0)
    return nif.serialize(rec), nif.serialize(bar)


def _reconstruct_world_bounds_from_nif(
    nif_bytes: bytes,
    meshes: dict[tuple[str, str], bytes],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Independently walk BS-173 NiNode transforms * decoded .mesh local vertices -> world AABB."""
    info = sw.inspect_weapon_nif_hierarchy(nif_bytes)
    mesh_by_rel = {f"{d}/{f}".lower(): mb for (d, f), mb in meshes.items()}
    pts_world: list[tuple[float, float, float]] = []
    for _bi, ginfo in info["geometries"].items():
        gnm = str(ginfo["name"])
        p_nm = info["shape_to_parent_node"][gnm]
        w_tr, w_rot = info["node_world_m"][p_nm]
        m_bytes = mesh_by_rel[str(ginfo["mesh_rel"]).lower()]
        parsed_m = sfmesh.parse(m_bytes)
        for qpos in parsed_m.positions:
            lp = sfmesh.decode_position(qpos, parsed_m.scale)
            rv = sw.mat_vec(w_rot, lp)
            pts_world.append((rv[0] + w_tr[0], rv[1] + w_tr[1], rv[2] + w_tr[2]))
    bmin = tuple(min(p[k] for p in pts_world) for k in range(3))
    bmax = tuple(max(p[k] for p in pts_world) for k in range(3))
    return bmin, bmax


def _write_synthetic_mat_and_dds(staging_root: Path, mat_rel: str, tex_prefix: str) -> None:
    dds_rels = [f"textures/{tex_prefix}_{suffix}.dds" for suffix in ("color", "normal", "rough")]
    for dr in dds_rels:
        dp = staging_root / dr
        dp.parent.mkdir(parents=True, exist_ok=True)
        dp.write_bytes(b"DDS " + b"\x00" * 144)
    # Match real convert_material.game_path ("Data\\Textures\\...") inside .mat JSON!
    data_prefixed = ["Data\\" + dr.replace("/", "\\") for dr in dds_rels]
    mp = staging_root / mat_rel
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps({"Objects": [{"Textures": data_prefixed}]}, indent=2), encoding="utf-8")


def _stage_synthetic_ammo_nif(staging_root: Path, ammo_rel: str, mat_rel: str, tex_prefix: str) -> None:
    ammo_m = sfmesh.SfMesh(version=2)
    ammo_m.scale, ammo_m.positions = sfmesh.encode_positions(
        [(-0.03, -0.02, 0.0), (0.03, -0.02, 0.0), (0.03, 0.02, 0.04), (-0.03, 0.02, 0.04)]
    )
    ammo_m.triangles = list(QUAD_TRIS)
    sfmesh.build_meshlets(ammo_m)
    mb = sfmesh.serialize(ammo_m)
    dh, fh = sw.convert_static.mesh_file_path(mb)
    (staging_root / "geometries" / dh).mkdir(parents=True, exist_ok=True)
    (staging_root / "geometries" / dh / f"{fh}.mesh").write_bytes(mb)
    pts_dec = [sfmesh.decode_position(p, ammo_m.scale) for p in ammo_m.positions]
    sph, bx = sfnif.bounds_from_points(pts_dec)
    anf = sfnif.build_static_nif(
        b"AmmoRoot",
        [
            sfnif.StaticShape(
                name=b"Ammo:0",
                mesh_path=f"{dh}\\{fh}".encode("ascii"),
                indices_size=6,
                num_verts=4,
                material_path=mat_rel,
                sphere=sph,
                box=bx,
            )
        ],
    )
    ap = staging_root / ammo_rel
    ap.parent.mkdir(parents=True, exist_ok=True)
    ap.write_bytes(nif.serialize(anf))
    _write_synthetic_mat_and_dds(staging_root, mat_rel, tex_prefix)


def _walk_esm_records(esm_bytes: bytes) -> list[tuple[bytes, int, int, list[tuple[bytes, bytes]]]]:
    """Pure-stdlib Starfield .esm walker returning (rec_type, flags, form_id, [(sub_type, sub_payload)])."""
    out: list[tuple[bytes, int, int, list[tuple[bytes, bytes]]]] = []

    def walk(buf: bytes, start: int, end: int) -> None:
        pos = start
        while pos + 24 <= end:
            rt = buf[pos : pos + 4]
            if rt == b"GRUP":
                gsz, = struct.unpack_from("<I", buf, pos + 4)
                if gsz < 24 or pos + gsz > end:
                    break
                walk(buf, pos + 24, pos + gsz)
                pos += gsz
                continue
            dsz, flags, fid = struct.unpack_from("<III", buf, pos + 4)
            body = buf[pos + 24 : pos + 24 + dsz]
            if flags & 0x00040000 and len(body) >= 4:
                body = zlib.decompress(body[4:])
            subs: list[tuple[bytes, bytes]] = []
            sp = 0
            xxxx_len: int | None = None
            while sp + 6 <= len(body):
                st = body[sp : sp + 4]
                slen, = struct.unpack_from("<H", body, sp + 4)
                sp += 6
                if st == b"XXXX" and slen == 4:
                    xxxx_len, = struct.unpack_from("<I", body, sp)
                    sp += 4
                    continue
                if xxxx_len is not None:
                    slen = xxxx_len
                    xxxx_len = None
                subs.append((st, body[sp : sp + slen]))
                sp += slen
            out.append((rt, flags, fid, subs))
            pos += 24 + dsz

    walk(esm_bytes, 0, len(esm_bytes))
    return out


def _build_synthetic_fo4_10mm_part_nifs() -> tuple[bytes, bytes, bytes]:
    """Synthetic FO4 10mm Pistol receiver, grip, and magazine NIFs matching real F1 hierarchy."""
    rec = _new_fo4_nif()
    s_weap = rec.string_index(b"WEAPON")
    s_cpa = rec.string_index(b"CPA")
    s_r = rec.string_index(b"Pistol10mmReceiver")
    s_bolt = rec.string_index(b"WeaponBolt")
    s_mag = rec.string_index(b"WeaponMagazine")
    s_trg = rec.string_index(b"WeaponTrigger")
    s_e2 = rec.string_index(b"WeaponExtra2")
    s_mat = rec.string_index(b"Materials\\Weapons\\10mmPistol\\10mmPistol.BGSM")
    rec.add_block("NiNode", _av_fields(s_weap, (0.0, 0.0, 0.0), extra_refs=(1,)) + struct.pack("<I5i", 5, 2, 3, 4, 5, 6))
    rec.add_block(
        "BSConnectPoint::Parents",
        _connect_points_parents_block(
            s_cpa,
            [
                (b"Pistol10mmReceiver", b"P-Grip", (1.0, 0.0, 0.0, 0.0), (0.0, -1.5, -2.0), 1.0),
                (b"WeaponMagazine", b"P-Mag", (1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 1.0),
                (b"Pistol10mmReceiver", b"P-ProjectileNode", (1.0, 0.0, 0.0, 0.0), (-0.0343, 18.5135, 4.8686), 1.0),
            ],
        ),
    )
    rec.add_block("NiNode", _av_fields(s_r, (0.0, 0.0, 0.0)) + struct.pack("<I2i", 2, 7, 10))
    rec.add_block("NiNode", _av_fields(s_bolt, (-0.104, 6.95, 0.301)) + struct.pack("<Ii", 1, 8))
    rec.add_block("NiNode", _av_fields(s_mag, (0.0, 2.0, -3.5)) + struct.pack("<I", 0))
    rec.add_block("NiNode", _av_fields(s_trg, (0.238, 4.676, 1.162)) + struct.pack("<I", 0))
    rec.add_block("NiNode", _av_fields(s_e2, (0.0, -1.0, 2.5)) + struct.pack("<Ii", 1, 9))
    for nm_b, y0 in (
        (b"Pistol10mmReceiver:0", 0.0),
        (b"Pistol10mmBolt:0", 1.0),
        (b"Pistol10mmHammer:0", -0.5),
        (b"10mmTrigger:0", 4.0),
    ):
        rec.add_block(
            "BSTriShape",
            _fo4_trishape_block(
                rec.string_index(nm_b),
                [(-1.0, y0, -1.0), (1.0, y0, -1.0), (1.0, y0 + 5.0, 2.0), (-1.0, y0 + 5.0, 2.0)],
                shader_ref=11,
            ),
        )
    rec.add_block("BSLightingShaderProperty", _fo4_lighting_shader_block(s_mat))
    rec.footer = struct.pack("<II", 1, 0)

    grp = _new_fo4_nif()
    grp.add_block("NiNode", _av_fields(grp.string_index(b"Pistol10mmGrip"), (0.0, 0.0, 0.0)) + struct.pack("<Ii", 1, 1))
    grp.add_block(
        "BSTriShape",
        _fo4_trishape_block(grp.string_index(b"10mmGrip:0"), [(-1.0, -2.0, -4.0), (1.0, -2.0, -4.0), (1.0, 1.0, 0.0), (-1.0, 1.0, 0.0)], shader_ref=2),
    )
    grp.add_block("BSLightingShaderProperty", _fo4_lighting_shader_block(grp.string_index(b"Materials\\Weapons\\10mmPistol\\Grip.BGSM")))
    grp.footer = struct.pack("<II", 1, 0)

    mag = _new_fo4_nif()
    mag.add_block("NiNode", _av_fields(mag.string_index(b"10mmMag"), (0.0, 0.0, 0.0)) + struct.pack("<Ii", 1, 1))
    mag.add_block(
        "BSTriShape",
        _fo4_trishape_block(mag.string_index(b"Magazine:0"), [(-0.8, -1.0, -5.0), (0.8, -1.0, -5.0), (0.8, 1.0, 0.0), (-0.8, 1.0, 0.0)], shader_ref=2),
    )
    mag.add_block("BSLightingShaderProperty", _fo4_lighting_shader_block(mag.string_index(b"Materials\\Weapons\\10mmPistol\\Mag.BGSM")))
    mag.footer = struct.pack("<II", 1, 0)
    return nif.serialize(rec), nif.serialize(grp), nif.serialize(mag)


class R11Step4WeaponsTests(unittest.TestCase):
    def test_all_four_weapons_moving_part_hierarchies_and_world_vertex_invariant(self) -> None:
        # 1. 10mm Pistol (F1: WeaponBolt->MiscA06, WeaponMagazine->Magazine, WeaponTrigger->TRIGGER, zero empty duplicates)
        p10_rec, p10_grip, p10_mag = _build_synthetic_fo4_10mm_part_nifs()
        r10 = sw.build_10mm_weapon(
            p10_rec, p10_grip, p10_mag, default_material="materials/fo4sf/weapons/10mm/10mm.mat"
        )
        h10 = sw.inspect_weapon_nif_hierarchy(r10.nif_bytes)
        self.assertTrue(h10["all_nodes_have_sgo_keep"])
        self.assertNotIn("WEAPON", h10["node_to_shapes"])
        self.assertEqual(h10["shape_to_parent_node"]["Pistol10mmBolt:0"], "MiscA06")
        self.assertEqual(h10["shape_to_parent_node"]["Magazine:0"], "Magazine")
        self.assertEqual(h10["shape_to_parent_node"]["10mmTrigger:0"], "TRIGGER")
        self.assertEqual(h10["shape_to_parent_node"]["Pistol10mmHammer:0"], "WeaponExtra2")
        for forbidden in ("WeaponBolt", "WeaponMagazine", "WeaponTrigger", "Bolt"):
            self.assertNotIn(forbidden, h10["node_names"])
        self.assertEqual(r10.fo4_part_map["MiscA06"], "WeaponBolt")
        self.assertEqual(r10.fo4_part_map["Magazine"], "WeaponMagazine")
        self.assertEqual(r10.fo4_part_map["TRIGGER"], "WeaponTrigger")
        bmin10, bmax10 = _reconstruct_world_bounds_from_nif(r10.nif_bytes, r10.meshes)
        for g, w in zip(bmin10 + bmax10, r10.bounds_min_m + r10.bounds_max_m):
            self.assertAlmostEqual(g, w, delta=2e-4)

        # 2. Baton (R_MELEE +Y -> +Z, telescoping WeaponExtra1/2, blood shell skipped, zero empty TRIGGER)
        det_melee = (
            sw.R_MELEE_FO4_Y_TO_SF_Z[0] * (sw.R_MELEE_FO4_Y_TO_SF_Z[4] * sw.R_MELEE_FO4_Y_TO_SF_Z[8] - sw.R_MELEE_FO4_Y_TO_SF_Z[5] * sw.R_MELEE_FO4_Y_TO_SF_Z[7])
            - sw.R_MELEE_FO4_Y_TO_SF_Z[1] * (sw.R_MELEE_FO4_Y_TO_SF_Z[3] * sw.R_MELEE_FO4_Y_TO_SF_Z[8] - sw.R_MELEE_FO4_Y_TO_SF_Z[5] * sw.R_MELEE_FO4_Y_TO_SF_Z[6])
            + sw.R_MELEE_FO4_Y_TO_SF_Z[2] * (sw.R_MELEE_FO4_Y_TO_SF_Z[3] * sw.R_MELEE_FO4_Y_TO_SF_Z[7] - sw.R_MELEE_FO4_Y_TO_SF_Z[4] * sw.R_MELEE_FO4_Y_TO_SF_Z[6])
        )
        self.assertAlmostEqual(det_melee, 1.0, places=6)
        baton_b = _build_synthetic_baton_nif(include_blood_overlay=True)
        r_bat = sw.build_baton_weapon(baton_b, default_material="materials/fo4sf/weapons/baton/baton.mat")
        self.assertEqual(sorted(r_bat.shape_names), ["BatonLowExt01:0", "BatonLowExt02:0", "BatonLowHandle:0"])
        self.assertTrue(any("BatonMergedBlood:0" in s for s in r_bat.skipped_shapes), r_bat.skipped_shapes)
        h_bat = sw.inspect_weapon_nif_hierarchy(r_bat.nif_bytes)
        self.assertTrue(h_bat["all_nodes_have_sgo_keep"])
        self.assertNotIn("TRIGGER", h_bat["node_names"])
        self.assertEqual(h_bat["shape_to_parent_node"]["BatonLowExt01:0"], "BatonLowExt01")
        self.assertEqual(h_bat["node_parents"]["BatonLowExt01"], "WeaponExtra1")
        self.assertEqual(h_bat["shape_to_parent_node"]["BatonLowExt02:0"], "BatonLowExt02")
        self.assertEqual(h_bat["node_parents"]["BatonLowExt02"], "WeaponExtra2")
        self.assertEqual(h_bat["shape_to_parent_node"]["BatonLowHandle:0"], "BatonLowHandle")
        bmin_b, bmax_b = _reconstruct_world_bounds_from_nif(r_bat.nif_bytes, r_bat.meshes)
        self.assertAlmostEqual(bmin_b[2], -7.126 / 70.0, delta=5e-4)
        self.assertAlmostEqual(bmax_b[2], (22.8426 + 13.45) / 70.0, delta=5e-4)
        self.assertLess(abs(bmax_b[1]), 0.03)
        self.assertAlmostEqual(r_bat.named_nodes_m["WeaponExtra1"][2], 9.878 / 70.0, places=4)
        self.assertAlmostEqual(r_bat.named_nodes_m["WeaponExtra2"][2], 22.8426 / 70.0, places=4)
        self.assertAlmostEqual(r_bat.named_nodes_m["ProjectileNode"][2], 36.295 / 70.0, places=4)

        # 3. Laser Musket (F1: WeaponTrigger->TRIGGER, crank stays WeaponMagazine, zero empty Magazine/Bolt; F3: P-ProjectileNode)
        lm_rec, lm_grp, lm_bar, lm_sgt = _build_synthetic_lasermusket_nifs()
        r_lm = sw.build_laser_musket_weapon(
            lm_rec, lm_grp, lm_bar, lm_sgt, default_material="materials/fo4sf/weapons/lasermusket/lm.mat"
        )
        self.assertEqual(len(r_lm.shape_names), 10)
        self.assertTrue(any("LaserMusketGlassCylinder:0" in s for s in r_lm.skipped_shapes))
        self.assertTrue(any("FrontGlowMesh:0" in s for s in r_lm.skipped_shapes))
        h_lm = sw.inspect_weapon_nif_hierarchy(r_lm.nif_bytes)
        self.assertTrue(h_lm["all_nodes_have_sgo_keep"])
        self.assertEqual(h_lm["shape_to_parent_node"]["LaserMusketCrank:0"], "WeaponMagazine")
        self.assertEqual(h_lm["shape_to_parent_node"]["LaserMusketTrigger:0"], "TRIGGER")
        self.assertEqual(h_lm["shape_to_parent_node"]["LaserMusketRotor:0"], "WeaponExtra2")
        for forbidden in ("WeaponTrigger", "Magazine", "Bolt"):
            self.assertNotIn(forbidden, h_lm["node_names"])
        self.assertEqual(r_lm.fo4_part_map["TRIGGER"], "WeaponTrigger")
        self.assertEqual(r_lm.fo4_part_map["WeaponMagazine"], "WeaponMagazine")
        self.assertEqual(
            h_lm["shape_to_parent_node"]["LaserMusketBarrelExtension2Lens:0"],
            "LaserMusketBarrelExtension2Lens",
        )
        self.assertEqual(h_lm["node_parents"]["LaserMusketBarrelExtension2Lens"], "LaserRifleBarrelMusket004")
        self.assertAlmostEqual(r_lm.named_nodes_m["ProjectileNode"][1], (21.5106 + 22.7469 + 21.2275) / 70.0, places=4)
        self.assertAlmostEqual(r_lm.named_nodes_m["Scope"][2], (11.7098 + 0.1573) / 70.0, places=4)
        bmin_lm, bmax_lm = _reconstruct_world_bounds_from_nif(r_lm.nif_bytes, r_lm.meshes)
        for g, w in zip(bmin_lm + bmax_lm, r_lm.bounds_min_m + r_lm.bounds_max_m):
            self.assertAlmostEqual(g, w, delta=2e-4)

        # 4. Minigun (F1: MiscA01 -> BarrelRoot -> Minigun_Barrel, Magazine -> Minigun_AmmoDrum, zero empty duplicates)
        mg_rec, mg_bar = _build_synthetic_minigun_nifs()
        r_mg = sw.build_minigun_weapon(
            mg_rec, mg_bar, default_material="materials/fo4sf/weapons/minigun/mg.mat"
        )
        self.assertEqual(
            sorted(r_mg.shape_names),
            ["AmmoBelt:0", "Minigun001:0", "Minigun_AmmoDrum:0", "Minigun_Barrel:0"],
        )
        self.assertTrue(any("BaseRefractionMesh:0" in s for s in r_mg.skipped_shapes))
        h_mg = sw.inspect_weapon_nif_hierarchy(r_mg.nif_bytes)
        self.assertTrue(h_mg["all_nodes_have_sgo_keep"])
        self.assertEqual(h_mg["shape_to_parent_node"]["Minigun_Barrel:0"], "Minigun_Barrel")
        self.assertEqual(h_mg["node_parents"]["Minigun_Barrel"], "BarrelRoot")
        self.assertEqual(h_mg["node_parents"]["BarrelRoot"], "MiscA01")
        self.assertEqual(h_mg["shape_to_parent_node"]["Minigun_AmmoDrum:0"], "Minigun_AmmoDrum")
        self.assertEqual(h_mg["node_parents"]["Minigun_AmmoDrum"], "Magazine")
        for forbidden in ("WeaponBolt", "WeaponMagazine", "Bolt", "TRIGGER"):
            self.assertNotIn(forbidden, h_mg["node_names"])
        self.assertEqual(r_mg.fo4_part_map["MiscA01"], "WeaponBolt")
        self.assertEqual(r_mg.fo4_part_map["Magazine"], "WeaponMagazine")
        bmin_mg, bmax_mg = _reconstruct_world_bounds_from_nif(r_mg.nif_bytes, r_mg.meshes)
        for g, w in zip(bmin_mg + bmax_mg, r_mg.bounds_min_m + r_mg.bounds_max_m):
            self.assertAlmostEqual(g, w, delta=2e-4)

    def test_f3_musket_p_projectilenode_and_f6_controllers_and_shader_offset(self) -> None:
        # F3: Barrel with BOTH P-ProjectileNode (~0.935m, 0.079m) and P-Muzzle must prefer P-ProjectileNode
        lm_rec, lm_grp, _, lm_sgt = _build_synthetic_lasermusket_nifs()
        bar = _new_fo4_nif()
        bar.add_block("NiNode", _av_fields(bar.string_index(b"LaserRifleBarrelMusket004"), (0.0, 0.0, 0.0), extra_refs=(1,)) + struct.pack("<I2i", 2, 2, 3))
        bar.add_block(
            "BSConnectPoint::Parents",
            _connect_points_parents_block(
                bar.string_index(b"CPA"),
                [
                    (b"LaserMusketBarrelExtension2Lens", b"P-ProjectileNode", (1.0, 0.0, 0.0, 0.0), (0.0, 21.1925, 2.8422), 1.0),
                    (b"LaserRifleBarrelMusket004", b"P-Muzzle", (1.0, 0.0, 0.0, 0.0), (0.0, 12.0, 0.0), 1.0),
                ],
            ),
        )
        bar.add_block("NiNode", _av_fields(bar.string_index(b"LaserMusketBarrelExtension2Lens"), (0.0, 22.7469, -3.6842)) + struct.pack("<Ii", 1, 3))
        bar.add_block("BSTriShape", _fo4_trishape_block(bar.string_index(b"LaserMusketBarrelExtension2Lens:0"), [(-1, 0, -1), (1, 0, -1), (1, 20, 1), (-1, 20, 1)], shader_ref=4))
        bar.add_block("BSLightingShaderProperty", _fo4_lighting_shader_block(bar.string_index(b"Materials\\Weapons\\LaserMusket\\Barrel.BGSM")))
        bar.footer = struct.pack("<II", 1, 0)
        r_lm = sw.build_laser_musket_weapon(lm_rec, lm_grp, nif.serialize(bar), lm_sgt, default_material="materials/fo4sf/weapons/lasermusket/lm.mat")
        # 21.5106 + 22.7469 + 21.1925 = 65.45 FO4 = 0.935 m; 6.3335 - 3.6842 + 2.8422 = 5.4915 FO4 = 0.07845 m
        self.assertAlmostEqual(r_lm.named_nodes_m["ProjectileNode"][1], 0.935, delta=1e-3)
        self.assertAlmostEqual(r_lm.named_nodes_m["ProjectileNode"][2], 0.0785, delta=1e-3)

        # F6: Synthetic NiControllerManager + NiControllerSequence must appear in controllers sidecar payload
        nf_ctrl = _new_fo4_nif()
        nf_ctrl.add_block("NiNode", _av_fields(nf_ctrl.string_index(b"MinigunBarrel"), (0.0, 0.0, 0.0)) + struct.pack("<I", 0))
        nf_ctrl.add_block("NiControllerManager", struct.pack("<iI", nf_ctrl.string_index(b"CM"), 0))
        nf_ctrl.add_block("NiControllerSequence", struct.pack("<iI", nf_ctrl.string_index(b"x_partA"), 0))
        nf_ctrl.add_block("NiControllerSequence", struct.pack("<iI", nf_ctrl.string_index(b"MusketFireWeapon"), 0))
        nf_ctrl.footer = struct.pack("<II", 1, 0)
        parsed_c = sw.extract_nif_controllers(nif.parse(nif.serialize(nf_ctrl)), "meshes/weapons/minigun/minigunbarrel.nif")
        self.assertEqual(parsed_c["controller_block_count"], 3)
        self.assertEqual([s["name"] for s in parsed_c["sequences"]], ["x_partA", "MusketFireWeapon"])

        # BSLightingShaderProperty <IiI fix: high string index must NOT be misparsed as SLSF1_REFRACTION
        nf_g = _new_fo4_nif()
        for k in range(25):
            nf_g.string_index(f"pad_{k}".encode("ascii"))
        s_gauss_mat = nf_g.string_index(b"Materials\\Weapons\\GaussRifle\\GaussRifle.BGSM")
        nf_g.add_block("NiNode", _av_fields(nf_g.string_index(b"GaussRifleReceiver"), (0.0, 0.0, 0.0)) + struct.pack("<Ii", 1, 1))
        nf_g.add_block("BSTriShape", _fo4_trishape_block(nf_g.string_index(b"GaussRifleReceiver:0"), [(-1, 0, -1), (1, 0, -1), (1, 10, 1), (-1, 10, 1)], shader_ref=2))
        nf_g.add_block("BSLightingShaderProperty", _fo4_lighting_shader_block(s_gauss_mat, sf1=0x80400281))
        nf_g.footer = struct.pack("<II", 1, 0)
        parsed_g = nif.parse(nif.serialize(nf_g))
        g_shapes = nif.fo4_trishapes(parsed_g, placed=False)
        self.assertIsNone(sw.should_skip_fo4_weapon_shape(parsed_g, g_shapes[0]))

    def test_verify_staged_weapons_and_negative_tamper_checks(self) -> None:
        p10_rec, p10_grip, p10_mag = _build_synthetic_fo4_10mm_part_nifs()
        bat_b = _build_synthetic_baton_nif(include_blood_overlay=True)
        lm_rec, lm_grp, lm_bar, lm_sgt = _build_synthetic_lasermusket_nifs()
        mg_rec, mg_bar = _build_synthetic_minigun_nifs()

        built = {
            "10mm": sw.build_10mm_weapon(p10_rec, p10_grip, p10_mag, default_material="materials/fo4sf/weapons/10mm/p10.mat"),
            "baton": sw.build_baton_weapon(bat_b, default_material="materials/fo4sf/weapons/baton/bat.mat"),
            "lasermusket": sw.build_laser_musket_weapon(lm_rec, lm_grp, lm_bar, lm_sgt, default_material="materials/fo4sf/weapons/lasermusket/lm.mat"),
            "minigun": sw.build_minigun_weapon(mg_rec, mg_bar, default_material="materials/fo4sf/weapons/minigun/mg.mat"),
        }

        with tempfile.TemporaryDirectory() as td, mock.patch.object(sw, "require_starfield_not_running", return_value=None):
            stg = Path(td)
            for wkey, wres in built.items():
                wp = stg / sw.WEAPON_NIF_RELS[wkey]
                wp.parent.mkdir(parents=True, exist_ok=True)
                wp.write_bytes(wres.nif_bytes)
                for (dh, fh), mb in wres.meshes.items():
                    mp = stg / "geometries" / dh / f"{fh}.mesh"
                    mp.parent.mkdir(parents=True, exist_ok=True)
                    mp.write_bytes(mb)
                _write_synthetic_mat_and_dds(stg, wres.materials[0], f"fo4sf/weapons/{wkey}/{wkey}")

            for akey in sw.P5_AMMO_KEYS:
                arel = sw.AMMO_NIF_RELS[akey]
                _stage_synthetic_ammo_nif(
                    stg, arel, f"materials/fo4core/ammo/{akey}/{akey}.mat", f"fo4core/ammo/{akey}/{akey}"
                )

            rep = sw.verify_staged_weapons(str(stg), require_converted_materials=True, require_collision=False)
            self.assertEqual(sorted(rep["weapons"].keys()), ["10mm", "baton", "lasermusket", "minigun"])
            self.assertEqual(sorted(rep["ammo"].keys()), ["10mm", "5mm", "fusioncell"])
            self.assertIn("stand-ins", rep["standin_disclosure"])

            # Negative 1: Flattened BSGeometry directly on root WEAPON must fail!
            mg_path = stg / sw.WEAPON_NIF_RELS["minigun"]
            saved_mg = mg_path.read_bytes()
            first_dh, first_fh = next(iter(built["minigun"].meshes.keys()))
            flat_nf = sfnif.build_static_nif(
                b"WEAPON",
                [
                    sfnif.StaticShape(
                        name=b"Minigun_Barrel:0",
                        mesh_path=f"{first_dh}\\{first_fh}".encode("ascii"),
                        indices_size=6,
                        num_verts=4,
                        material_path="materials/fo4sf/weapons/minigun/mg.mat",
                        sphere=(0.0, 0.0, 0.0, 0.5),
                        box=(0.0, 0.0, 0.0, 0.2, 0.2, 0.2),
                    )
                ],
            )
            mg_path.write_bytes(nif.serialize(flat_nf))
            with self.assertRaises(sw.StageWeaponsError):
                sw.verify_staged_weapons(str(stg), require_converted_materials=True, require_collision=False)
            mg_path.write_bytes(saved_mg)

            # Negative 2: Wrong moving-part parent (Minigun_Barrel:0 moved onto Minigun001) must fail!
            wrong_parent_mg = sw.build_hierarchical_weapon_nif(
                "minigun",
                mg_rec,
                [sw.AttachedOmodPart(mg_bar, "P-Barrel", graft_part_root=True)],
                default_material="materials/fo4sf/weapons/minigun/mg.mat",
                shape_parent_overrides={"Minigun_Barrel:0": "Minigun001"},
                extra_sgo_nodes_fo4={"ProjectileNode": (0.0, 80.0, 0.0)},
            )
            mg_path.write_bytes(wrong_parent_mg.nif_bytes)
            for (dh, fh), mb in wrong_parent_mg.meshes.items():
                mp = stg / "geometries" / dh / f"{fh}.mesh"
                mp.parent.mkdir(parents=True, exist_ok=True)
                mp.write_bytes(mb)
            with self.assertRaises(sw.StageWeaponsError):
                sw.verify_staged_weapons(str(stg), require_converted_materials=True, require_collision=False)
            mg_path.write_bytes(saved_mg)

            # Negative 3: Starfield donor material leaks across RescueAxe, Orion, and Microgun must all fail!
            bat_path = stg / sw.WEAPON_NIF_RELS["baton"]
            saved_bat = bat_path.read_bytes()
            for leaked_mat in (
                r"Materials\Weapons\RescueAxe\RescueAxe.mat",
                r"Materials\Weapons\OrionRifle\Orion_Barrel.mat",
                r"Materials\Weapons\MicroGun\MicroGun_Barrel.mat",
                r"Materials\Test\Test_Herb_Default_1.mat",
            ):
                bad_bat = sw.build_baton_weapon(bat_b, default_material=leaked_mat)
                bat_path.write_bytes(bad_bat.nif_bytes)
                with self.assertRaises(sw.StageWeaponsError):
                    sw.verify_staged_weapons(str(stg), require_converted_materials=False, require_collision=False)
            bat_path.write_bytes(saved_bat)

            # Negative 4: Missing .dds referenced via Data\Textures\... must fail!
            victim_dds = stg / "textures" / "fo4sf" / "weapons" / "lasermusket" / "lasermusket_normal.dds"
            victim_dds.unlink()
            with self.assertRaises(sw.StageWeaponsError):
                sw.verify_staged_weapons(str(stg), require_converted_materials=True, require_collision=False)
            victim_dds.write_bytes(b"DDS " + b"\x00" * 144)

    def test_safety_guards_refuse_repo_candidate_game_and_running_starfield(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fake_fo4 = os.path.join(td, "Fallout 4", "Data")
            fake_sf_root = os.path.join(td, "Starfield")
            fake_sf_data = os.path.join(fake_sf_root, "Data")
            os.makedirs(fake_fo4)
            os.makedirs(fake_sf_data)
            Path(fake_sf_root, "Starfield.exe").write_bytes(b"MZ")

            with self.assertRaises(sw.StageWeaponsError):
                sw.refuse_unsafe_staging_dir(str(REPO_ROOT / "bad_stage"))
            with self.assertRaises(sw.StageWeaponsError):
                sw.refuse_unsafe_staging_dir(os.path.join(td, "candidate-2g-fix2", "assets"))
            with self.assertRaises(sw.StageWeaponsError):
                sw.refuse_unsafe_staging_dir(os.path.join(fake_fo4, "sub"), fo4_data=fake_fo4)
            with self.assertRaises(sw.StageWeaponsError):
                sw.refuse_unsafe_staging_dir(os.path.join(fake_sf_root, "sub"), sf_data=fake_sf_data)

            clean_dir = os.path.join(td, "r11-s4-clean-stage")
            sw.refuse_unsafe_staging_dir(clean_dir, fo4_data=fake_fo4, sf_data=fake_sf_data)

        with mock.patch.object(sw.System, "pids", return_value=[42196]):
            with self.assertRaises(sw.StageWeaponsError):
                sw.require_starfield_not_running()

    @unittest.skipUnless(shutil.which("dotnet") is not None, "dotnet SDK required for binary CoreValues P5 verification")
    def test_dotnet_corevalues_p5_binary_records_dama_energy_and_nonplayable_flags(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            cv_proj = REPO_ROOT / "dotnet" / "CoreValues" / "CoreValues.csproj"
            r = subprocess.run(
                ["dotnet", "run", "--project", str(cv_proj), "-c", "Release", "--", "selftest", str(tmp / "st")],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(r.returncode, 0, r.stdout + "\n" + r.stderr)
            self.assertIn("CoreValues selftest: ok", r.stdout)

            p5_esm = tmp / "st" / "p5_weapons_on" / "FO4SFCoreValues.esm"
            rep = cpc.inspect_esm_binary(str(p5_esm))
            self.assertEqual(list(rep.masters), ["Starfield.esm"])

            raw_records = {
                fid: (rt, flags, subs)
                for rt, flags, fid, subs in _walk_esm_records(p5_esm.read_bytes())
                if rt in (b"WEAP", b"AMMO")
            }
            self.assertEqual(
                sorted(raw_records.keys()),
                [0x01000898, 0x01000899, 0x0100089A, 0x0100089B, 0x0100089C, 0x0100089D, 0x0100089E, 0x0100089F, 0x010008A0],
            )

            def sub_map(local_fid: int) -> dict[bytes, bytes]:
                return {st: payload for st, payload in raw_records[0x01000000 | local_fid][2]}

            def cstr(b: bytes) -> str:
                return b.rstrip(b"\x00").decode("utf-8")

            # Verify exact FULL, ONAM (short name), MODL, NonPlayable flags, and DAMA energy damage
            expected_meta = {
                0x000898: ("AMMO", "FO4_Ammo10mm", "10mm Round", "10mm", r"fo4core\ammo\10mm\10mmammo.nif", False),
                0x000899: ("WEAP", "FO4_10mmPistol", "10mm Pistol", None, r"fo4sf\weapons\10mm\fo4_10mmpistol.nif", False),
                0x00089A: ("WEAP", "FO4_Baton", "Baton", None, r"fo4sf\weapons\baton\fo4_baton.nif", False),
                0x00089B: ("AMMO", "FO4_AmmoFusionCell", "Fusion Cell", "Cell", r"fo4core\ammo\laserammo\microfusioncell.nif", False),
                0x00089C: ("AMMO", "FO4_CompanionAmmoFusionCell", "Companion Fusion Cell", "Cell", r"fo4core\ammo\laserammo\microfusioncell.nif", True),
                0x00089D: ("WEAP", "FO4_LaserMusket", "Laser Musket", None, r"fo4sf\weapons\lasermusket\fo4_lasermusket.nif", False),
                0x00089E: ("WEAP", "FO4_CompPrestonLaserMusket", "Preston's Laser Musket", None, r"fo4sf\weapons\lasermusket\fo4_lasermusket.nif", True),
                0x00089F: ("AMMO", "FO4_Ammo5mm", "5mm Round", "5mm", r"fo4core\ammo\5mm\5mmammo.nif", False),
                0x0008A0: ("WEAP", "FO4_Minigun", "Minigun", None, r"fo4sf\weapons\minigun\fo4_minigun.nif", False),
            }
            for fid, (want_rt, want_edid, want_full, want_short, want_modl, want_nonplayable) in expected_meta.items():
                rt, rec_flags, _ = raw_records[0x01000000 | fid]
                smap = sub_map(fid)
                self.assertEqual(rt.decode("ascii"), want_rt)
                self.assertEqual(cstr(smap[b"EDID"]), want_edid)
                self.assertEqual(cstr(smap[b"FULL"]), want_full)
                if want_short is not None:
                    self.assertEqual(cstr(smap[b"ONAM"]), want_short)
                self.assertEqual(cstr(smap[b"MODL"]).replace("/", "\\").lower(), want_modl.lower())
                if want_rt == "AMMO":
                    dn_flags, = struct.unpack_from("<I", smap[b"DNAM"], 8) if len(smap.get(b"DNAM", b"")) >= 12 else (0,)
                    is_np = bool((rec_flags & 0x4) or (dn_flags & 0x2))
                    self.assertEqual(is_np, want_nonplayable, f"AMMO 0x{fid:X} NonPlayable mismatch")
                else:
                    is_np = bool(rec_flags & 0x4)
                    self.assertEqual(is_np, want_nonplayable, f"WEAP 0x{fid:X} NonPlayable mismatch")

            # Verify Laser Musket (30 dtEnergy) and Preston's Laser Musket (18 dtEnergy) carry DAMA 0x00060A81 and 0 phys AttackDamage
            for fid, want_energy in ((0x00089D, 30), (0x00089E, 18)):
                smap = sub_map(fid)
                self.assertIn(b"DAMA", smap)
                dama = smap[b"DAMA"]
                self.assertGreaterEqual(len(dama), 8)
                dt_fid, dt_val = struct.unpack_from("<IH", dama, 0)
                self.assertEqual(dt_fid, 0x00060A81)  # Starfield.esm dtEnergy
                self.assertEqual(dt_val, want_energy)
                if b"WDMG" in smap and len(smap[b"WDMG"]) >= 4:
                    phys_dmg, = struct.unpack_from("<f", smap[b"WDMG"], 0)
                    self.assertAlmostEqual(phys_dmg, 0.0, places=5)

            # Verify full Arsenal binary ESM (0x851 Stimpak, F5 stats, WEAP.WVIS[12:16], EXPL.ENAM[84:88], Rows 5-20, Goo/Ash)
            ars_esm = tmp / "st" / "arsenal_on" / "FO4SFCoreValues.esm"
            ars_recs = {
                fid: (rt, flags, dict(subs))
                for rt, flags, fid, subs in _walk_esm_records(ars_esm.read_bytes())
            }
            stimpak_subs = ars_recs[0x01000851][2]
            self.assertEqual(cstr(stimpak_subs[b"MODL"]).replace("/", "\\").lower(), r"fo4core\props\stimpack01.nif")
            stimpak_wt, = struct.unpack_from("<f", stimpak_subs[b"DATA"], 0)
            stimpak_val, = struct.unpack_from("<I", stimpak_subs[b"ENIT"], 0)
            self.assertAlmostEqual(stimpak_wt, 0.1, places=5)
            self.assertEqual(stimpak_val, 48)

            expected_wvis = {
                0x000899: 0x0000D02C, 0x00089A: 0x00055DC3, 0x00089D: 0x001C1162, 0x00089E: 0x001C1162,
                0x0008A0: 0x0000D02C, 0x0008A2: 0x0000D02C, 0x0008A3: 0x0000D02C, 0x0008C5: 0x00252B4C,
                0x0008C6: 0x0015CCFD, 0x0008C7: 0x0015CCFD, 0x0008C8: 0x0000D02C, 0x0008C9: 0x0000D02C,
                0x0008CA: 0x00239D0F, 0x0008CB: 0x001D7FEC, 0x0008CC: 0x0000D02C, 0x0008CD: 0x0000D02C,
                0x0008CE: 0x001F5DA1, 0x0008CF: 0x001F5DA1, 0x0008D0: 0x0005C498, 0x0008D1: 0x0015CCFD,
                0x0008D2: 0x0015CCFD, 0x0008D3: 0x00115BE5, 0x0008D4: 0x00164E05, 0x0008D5: 0x00164E03,
                0x0008D6: 0x0034BE5D,
            }
            for lid, want_ipds in expected_wvis.items():
                rt, _, smap = ars_recs[0x01000000 | lid]
                self.assertEqual(rt, b"WEAP")
                wvis = smap.get(b"WVIS", b"")
                self.assertGreaterEqual(len(wvis), 16, f"WEAP 0x{lid:X} WVIS too short")
                got_ipds, = struct.unpack_from("<I", wvis, 12)
                self.assertEqual(got_ipds, want_ipds, f"WEAP 0x{lid:X} WVIS mismatch")
                full_str = cstr(smap[b"FULL"])
                self.assertNotIn("starfield", full_str.lower())
                self.assertFalse(full_str.startswith("FO4SF"))

            for expl_lid, want_ipds in ((0x0008B9, 0x003A5907), (0x0008BA, 0x003A5907), (0x0008BB, 0x0015CCFD), (0x0008BC, 0x0015CCFD)):
                enam = ars_recs[0x01000000 | expl_lid][2][b"ENAM"]
                self.assertGreaterEqual(len(enam), 88)
                self.assertEqual(struct.unpack_from("<I", enam, 84)[0], want_ipds)

            self.assertEqual(cstr(ars_recs[0x010008C1][2][b"EDID"]), "FO4_GooPile01")
            self.assertEqual(cstr(ars_recs[0x010008C3][2][b"EDID"]), "FO4_CritPlasma")
            self.assertEqual(cstr(ars_recs[0x010008C4][2][b"EDID"]), "FO4_CritLaser")
            crit_plasma_mgef = ars_recs[0x010008C2][2]
            self.assertIn(b"AttachAshPile", crit_plasma_mgef[b"VMAD"])
            self.assertIn(struct.pack("<I", 0x010008C1), crit_plasma_mgef[b"VMAD"])

    def test_step_4_hygiene_and_standin_disclosure(self) -> None:
        for path in (STAGE_WEAPONS_PY, HERE, COREVALUES_CS):
            raw = path.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM in {path.name}")
            txt = raw.decode("utf-8")
            self.assertIsNone(DRIVE_PATH_RX.search(txt), f"Drive-letter path leak in {path.name}")
        self.assertIn("stand-ins", sw.STANDIN_DISCLOSURE)
        self.assertIn("claude/robot-anim", sw.STANDIN_DISCLOSURE)

    @unittest.skipUnless(
        bool(os.environ.get("FO4SF_FO4_DATA")) and bool(os.environ.get("FO4SF_STARFIELD_DATA")),
        "Set FO4SF_FO4_DATA and FO4SF_STARFIELD_DATA to run real-archive Step 4 weapons test",
    )
    def test_optional_real_archive_all_weapons_staging_when_idle(self) -> None:
        if sw.System.pids(sw.GAME_EXE):
            self.skipTest(f"{sw.GAME_EXE} is currently running; skipping real-archive read")
        fo4_data = os.environ["FO4SF_FO4_DATA"]
        sf_data = os.environ["FO4SF_STARFIELD_DATA"]
        with tempfile.TemporaryDirectory() as td:
            stg = os.path.join(td, "stage_r11_weapons")
            manifest = sw.stage_r11_weapons(fo4_data, sf_data, stg)
            self.assertEqual(manifest["weapons"]["10mm"]["shape_count"], 8)
            self.assertGreaterEqual(manifest["weapons"]["baton"]["shape_count"], 1)
            self.assertEqual(manifest["weapons"]["lasermusket"]["shape_count"], 19)
            self.assertEqual(manifest["weapons"]["minigun"]["shape_count"], 6)
            self.assertEqual(len(manifest["weapons"]), 23)


if __name__ == "__main__":
    unittest.main()
