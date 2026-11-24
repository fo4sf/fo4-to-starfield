"""stage_r11_p6_arsenal.py: Round 11 Probe P6 (Full Arsenal Rows 1-20, Impacts & Ash/Goo) stager & installer.

Builds the standalone Probe P6 folder (outside Git worktrees, outside Starfield Data, and outside frozen dirs):
  <out-dir>/
    core/
      FO4SFCoreValues.esm               (--fo4-10mm 1 --fo4-p5-weapons 1 --fo4-arsenal 1: 0x0851, 0x0898..0x08D6)
    assets/
      meshes/fo4sf/weapons/...          (all 23 weapon NIFs + F6 controller sidecar JSONs)
      meshes/fo4core/...                (all 13 ammo NIFs, Stimpak/Caps/BobbyPin/GooPile01, Missile/MiniNuke proj)
      geometries/...                    (external .mesh v2 files)
      materials/...                     (.mat files)
      textures/...                      (BC1/BC5/BC4/DX10 .dds files)
    exp/
      FO4SF_R11P6Arsenal.esm            (Vault111Cryo 3-table weapon/ammo showcase beside P5 range w/ F4 bounds check,
                                         Flesh Dummy, Vanilla SF Robot metal target, NoDisintegrate Dummy, Stone & Wood,
                                         StartGameEnabled QUST 0x000830)
      FO4SF_R11P6Arsenal - Main.ba2     (BTDX v2 GNRL via probe_common.pack_gnrl_ba2)
      FO4SF_R11P6Arsenal - Textures.ba2 (BTDX v2 DX10 via probe_common.pack_dx10_ba2)
      Data/Scripts/FO4SF_R11P6Quest.pex
    bat/                                (P3-clean .txt batches: 0 M/N/V, 0 stripped FO4SF_ EDIDs, <200 m/axis hops)
      p6r.txt, p6t.txt, p6a.txt, p6g.txt, p6c.txt, p6h1.txt, p6e.txt, p6s.txt, p6q.txt
    manifest.json                       (SHA-256s, overridden candidate files, floor-clearance bounds, BA2 verification)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SRC_DIR = REPO / "src"
WEAPONS_DIR = REPO / "scripts" / "weapons"

for _p in (str(SRC_DIR), str(WEAPONS_DIR), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import probe_common as pc  # noqa: E402
import stage_r11_weapons as sw  # noqa: E402
from fo4sf import nif as nifmod, sfmesh  # noqa: E402
from fo4sf.ba2 import Ba2  # noqa: E402
from fo4sf.core import cross_plugin_check as cpc  # noqa: E402
from fo4sf.planet.esm import Plugin, parse_subrecords  # noqa: E402

PROBE_ID = "r11-p6-arsenal"
PROBE_STEM = "FO4SF_R11P6Arsenal"
PROBE_PLUGIN = f"{PROBE_STEM}.esm"
PROBE_MAIN_BA2 = f"{PROBE_STEM} - Main.ba2"
PROBE_TEX_BA2 = f"{PROBE_STEM} - Textures.ba2"

# Master indices in FO4SF_R11P6Arsenal.esm:
#   0x00 Starfield.esm
#   0x01 FO4Port.esm
#   0x02 FO4SFCoreValues.esm
#   0x03 FO4ActorRaider.esm
#   0x04 FO4SF_R11P6Arsenal.esm (local)
M_SF = 0x00
M_PORT = 0x01
M_CV = 0x02
M_RAIDER = 0x03
M_LOCAL = 0x04

PORT_V111_CELL = (M_PORT << 24) | 0x0011F3
PORT_V111_BLOCK = 5
PORT_V111_SUBBLOCK = 9
PORT_VAULT_TABLE_01 = (M_PORT << 24) | 0x0011A0  # bounds X[-1.064..1.065] Y[-0.537..0.558] Z[0.000..0.825]
VAULT_TABLE_TOP_Z = 0.825
VAULT_FLOOR_Z = 0.000

RAIDER_CALM_NPC = (M_RAIDER << 24) | 0xF04801
SF_ROBOT_MINIBOT_GARDEN = 0x0004297C  # OutpostRobotMiniBotA_Garden (MiniBotARace -> MaterialActorMetal 0x00022955)
SF_STONE_STAT = 0x000012E5            # RockPittedA (height ~0.94m, Z in [-0.470, +0.473])
SF_WOOD_STAT = 0x0013E8CA             # AK_Crate_WoodenSmall (height ~1.00m, Z in [-0.0002, +0.999])
SF_AV_HEALTH = 0x000002D4
SF_AV_HIDE_SUIT = 0x000B120E
SF_KW_NO_DISINTEGRATE = 0x0022DB8F
SF_ACTI_MODL = b"Effects\\sfbgs006\\SFBGS006_SBShipDecoratorMarker.nif\x00"

QUST_P6_LOCAL_ID = 0x000830
FID_ACTI_TRIGGER = (M_LOCAL << 24) | 0x000800
FID_NPC_NODISINT = (M_LOCAL << 24) | 0x000802
FID_REF_TRIGGER = (M_LOCAL << 24) | 0x000810
FID_ACHR_FLESH = (M_LOCAL << 24) | 0x000811
FID_ACHR_ROBOT = (M_LOCAL << 24) | 0x000812
FID_ACHR_NODISINT = (M_LOCAL << 24) | 0x000813
FID_REF_STONE = (M_LOCAL << 24) | 0x000814
FID_REF_WOOD = (M_LOCAL << 24) | 0x000815
FID_REF_TABLE_1 = (M_LOCAL << 24) | 0x000816
FID_REF_TABLE_2 = (M_LOCAL << 24) | 0x000817
FID_REF_TABLE_3 = (M_LOCAL << 24) | 0x000818
FID_QUST_P6 = (M_LOCAL << 24) | QUST_P6_LOCAL_ID

QUST_START_GAME_ENABLED_FLAGS = 0x00000009
REFR_PERSISTENT = 0x00000400
REFR_INITIALLY_DISABLED = 0x00000800
REFR_DONT_HAVOK_SETTLE = 0x20000000
DEFAULT_QUEST_LOAD_PREFIX = 0x11

OVERSEER_P6_STANCE = (-52.40, 29.85, 0.05)
OVERSEER_P6_RACKS_STANCE = (-51.10, 24.10, 0.05)
OVERSEER_TRIGGER_POS = (-53.50, 30.85, 1.25)

# Three FO4Port_Vault_Table_01 tables cleanly placed on Vault111Cryo z=0.00 floor:
#   Table 1 right beside P5/P6 firing line; Tables 2 & 3 in open South Overseer bay (yaw=0).
TABLE_PLACEMENTS: Tuple[Tuple[int, str, Tuple[float, float, float], Tuple[float, float, float]], ...] = (
    (FID_REF_TABLE_1, "FO4SF_P6_RackTable1Ref", (-53.70, 28.35, 0.00), (0.0, 0.0, math.pi / 2.0)),
    (FID_REF_TABLE_2, "FO4SF_P6_RackTable2Ref", (-52.60, 22.80, 0.00), (0.0, 0.0, 0.0)),
    (FID_REF_TABLE_3, "FO4SF_P6_RackTable3Ref", (-49.60, 22.80, 0.00), (0.0, 0.0, 0.0)),
)

# Targets lined cleanly at east end of Overseer range (z=0.00 floor, clear 4m sightline from OVERSEER_P6_STANCE):
TARGET_SPECS: Tuple[Tuple[str, int, str, int, Tuple[float, float, float], Tuple[float, float, float], int, Tuple[float, float]], ...] = (
    ("ACHR", FID_ACHR_FLESH,    "FO4SF_P6_FleshDummyRef",    RAIDER_CALM_NPC,         (-48.40, 30.40, 0.00), (0.0, 0.0, math.radians(270.0)), REFR_PERSISTENT | REFR_INITIALLY_DISABLED, (0.0, 1.80)),
    ("ACHR", FID_ACHR_ROBOT,    "FO4SF_P6_RobotDummyRef",    SF_ROBOT_MINIBOT_GARDEN, (-48.40, 29.40, 0.00), (0.0, 0.0, math.radians(270.0)), REFR_PERSISTENT | REFR_INITIALLY_DISABLED, (0.0, 1.10)),
    ("ACHR", FID_ACHR_NODISINT, "FO4SF_P6_NoDisintDummyRef", FID_NPC_NODISINT,        (-47.80, 29.95, 0.00), (0.0, 0.0, math.radians(270.0)), REFR_PERSISTENT | REFR_INITIALLY_DISABLED, (0.0, 1.80)),
    ("REFR", FID_REF_STONE,     "FO4SF_P6_StoneTargetRef",   SF_STONE_STAT,           (-47.10, 30.50, 0.48), (0.0, 0.0, 0.0),                 REFR_PERSISTENT | REFR_DONT_HAVOK_SETTLE, (-0.470, 0.473)),
    ("REFR", FID_REF_WOOD,      "FO4SF_P6_WoodTargetRef",    SF_WOOD_STAT,            (-47.10, 28.90, 0.01), (0.0, 0.0, 0.0),                 REFR_PERSISTENT | REFR_DONT_HAVOK_SETTLE, (-0.0002, 0.999)),
)

SANCTUARY_BENCH_ANCHOR = pc.AnchorPoint("sanctuary_bench", -2329.25, -1420.19, 112.09, "exterior")
EXT_HOP_MID = (-2400.00, -1413.00, 120.00)
V111_HILLTOP = (-2467.78, -1406.93, 127.85)
P6H1_ANCHOR = pc.AnchorPoint("p6h1", *EXT_HOP_MID, "exterior")

# 23 Playable Weapons in FO4SFCoreValues.esm (0x0899..0x08A3 + 0x08C6..0x08D6; excludes CompPrestonLM & UnarmedHuman):
@dataclass(frozen=True)
class RackItemSpec:
    local_ref_id: int
    ref_edid: str
    cv_form_id: int
    asset_key: str
    nif_rel: str
    rack_table: int      # 1, 2, or 3
    xy: Tuple[float, float]
    rot: Tuple[float, float, float]
    count: Optional[int] = None
    tag: str = ""


WEAP_RACK_SPECS: Tuple[RackItemSpec, ...] = (
    # Table 1 (-53.70, 28.35, rot_z=pi/2): P5 + Row 5 beside range (Minigun F4 elevated above table_top=0.825 & floor=0.00!)
    RackItemSpec(0x000819, "FO4SF_P6_Weap_10mmRef",           0x000899, "10mm",            sw.WEAPON_NIF_RELS["10mm"],            1, (-53.95, 27.60), (0.0, 0.0, 0.0),            tag="10mm"),
    RackItemSpec(0x00081A, "FO4SF_P6_Weap_BatonRef",          0x00089A, "baton",           sw.WEAPON_NIF_RELS["baton"],           1, (-53.95, 27.95), (-math.pi/2, 0.0, 0.0),     tag="baton"),
    RackItemSpec(0x00081B, "FO4SF_P6_Weap_PipePistolRef",     0x0008A2, "pipepistol",      sw.WEAPON_NIF_RELS["pipepistol"],      1, (-53.95, 28.30), (0.0, 0.0, 0.0),            tag="pipepistol"),
    RackItemSpec(0x00081C, "FO4SF_P6_Weap_PipeRifleRef",      0x0008A3, "piperifle",       sw.WEAPON_NIF_RELS["piperifle"],       1, (-53.95, 28.65), (0.0, 0.0, math.pi / 2.0),  tag="piperifle"),
    RackItemSpec(0x00081D, "FO4SF_P6_Weap_LaserMusketRef",    0x00089D, "lasermusket",     sw.WEAPON_NIF_RELS["lasermusket"],     1, (-53.65, 28.75), (0.0, 0.0, math.pi / 2.0),  tag="lasermusket"),
    RackItemSpec(0x00081E, "FO4SF_P6_Weap_MinigunRef",        0x0008A0, "minigun",         sw.WEAPON_NIF_RELS["minigun"],         1, (-53.70, 29.05), (0.0, 0.0, math.pi / 2.0),  tag="minigun"),
    # Table 2 (-52.60, 22.80, rot_z=0): Rows 7-14 Ballistics & Melee
    RackItemSpec(0x00081F, "FO4SF_P6_Weap_FragGrenadeRef",    0x0008C6, "fraggrenade",     sw.WEAPON_NIF_RELS["fraggrenade"],     2, (-53.40, 23.05), (0.0, 0.0, 0.0), count=5,   tag="fraggrenade"),
    RackItemSpec(0x000820, "FO4SF_P6_Weap_FragMineRef",       0x0008C7, "fragmine",        sw.WEAPON_NIF_RELS["fragmine"],        2, (-53.15, 23.05), (0.0, 0.0, 0.0), count=5,   tag="fragmine"),
    RackItemSpec(0x000821, "FO4SF_P6_Weap_PipeRevolverRef",   0x0008C8, "piperevolver",    sw.WEAPON_NIF_RELS["piperevolver"],    2, (-52.85, 23.05), (0.0, 0.0, 0.0),            tag="piperevolver"),
    RackItemSpec(0x000822, "FO4SF_P6_Weap_HuntingRifleRef",   0x0008C9, "huntingrifle",    sw.WEAPON_NIF_RELS["huntingrifle"],    2, (-52.50, 23.05), (0.0, 0.0, 0.0),            tag="huntingrifle"),
    RackItemSpec(0x000823, "FO4SF_P6_Weap_CombatShotgunRef",  0x0008CA, "combatshotgun",   sw.WEAPON_NIF_RELS["combatshotgun"],   2, (-52.15, 23.05), (0.0, 0.0, 0.0),            tag="combatshotgun"),
    RackItemSpec(0x000824, "FO4SF_P6_Weap_DoubleBarrelRef",   0x0008CB, "doublebarrel",    sw.WEAPON_NIF_RELS["doublebarrel"],    2, (-51.80, 23.05), (0.0, 0.0, 0.0),            tag="doublebarrel"),
    RackItemSpec(0x000825, "FO4SF_P6_Weap_SubmachineGunRef",  0x0008CC, "submachinegun",   sw.WEAPON_NIF_RELS["submachinegun"],   2, (-53.20, 22.55), (0.0, 0.0, 0.0),            tag="submachinegun"),
    RackItemSpec(0x000826, "FO4SF_P6_Weap_AssaultRifleRef",   0x0008CD, "assaultrifle",    sw.WEAPON_NIF_RELS["assaultrifle"],    2, (-52.60, 22.55), (0.0, 0.0, 0.0),            tag="assaultrifle"),
    RackItemSpec(0x000827, "FO4SF_P6_Weap_BaseballBatRef",    0x0008D0, "baseballbat",     sw.WEAPON_NIF_RELS["baseballbat"],     2, (-52.00, 22.55), (-math.pi/2, 0.0, 0.0),     tag="baseballbat"),
    # Table 3 (-49.60, 22.80, rot_z=0): Rows 15, 17-20 Energy & Heavy Weapons
    RackItemSpec(0x000828, "FO4SF_P6_Weap_LaserPistolRef",    0x0008CE, "laserpistol",     sw.WEAPON_NIF_RELS["laserpistol"],     3, (-50.40, 23.05), (0.0, 0.0, 0.0),            tag="laserpistol"),
    RackItemSpec(0x000829, "FO4SF_P6_Weap_LaserRifleRef",     0x0008CF, "laserrifle",      sw.WEAPON_NIF_RELS["laserrifle"],      3, (-50.05, 23.05), (0.0, 0.0, 0.0),            tag="laserrifle"),
    RackItemSpec(0x00082A, "FO4SF_P6_Weap_PlasmaPistolRef",   0x0008D4, "plasmapistol",    sw.WEAPON_NIF_RELS["plasmapistol"],    3, (-49.70, 23.05), (0.0, 0.0, 0.0),            tag="plasmapistol"),
    RackItemSpec(0x00082B, "FO4SF_P6_Weap_PlasmaRifleRef",    0x0008D5, "plasmarifle",     sw.WEAPON_NIF_RELS["plasmarifle"],     3, (-49.35, 23.05), (0.0, 0.0, 0.0),            tag="plasmarifle"),
    RackItemSpec(0x00082C, "FO4SF_P6_Weap_GaussRifleRef",     0x0008D6, "gaussrifle",      sw.WEAPON_NIF_RELS["gaussrifle"],      3, (-48.95, 23.05), (0.0, 0.0, 0.0),            tag="gaussrifle"),
    RackItemSpec(0x00082D, "FO4SF_P6_Weap_MissileLaunchRef",  0x0008D1, "missilelauncher", sw.WEAPON_NIF_RELS["missilelauncher"], 3, (-50.25, 22.55), (0.0, 0.0, 0.0),            tag="missilelauncher"),
    RackItemSpec(0x00082E, "FO4SF_P6_Weap_FatManRef",         0x0008D2, "fatman",          sw.WEAPON_NIF_RELS["fatman"],          3, (-49.60, 22.55), (0.0, 0.0, 0.0),            tag="fatman"),
    RackItemSpec(0x00082F, "FO4SF_P6_Weap_FlamerRef",         0x0008D3, "flamer",          sw.WEAPON_NIF_RELS["flamer"],          3, (-48.95, 22.55), (0.0, 0.0, 0.0),            tag="flamer"),
)

AMMO_RACK_SPECS: Tuple[RackItemSpec, ...] = (
    RackItemSpec(0x000831, "FO4SF_P6_Ammo_10mmRef",           0x000898, "10mm",            sw.AMMO_NIF_RELS["10mm"],            1, (-53.40, 27.60), (0.0, 0.0, 0.0), count=48,   tag="10mm"),
    RackItemSpec(0x000832, "FO4SF_P6_Ammo_38CalRef",          0x0008A1, "38cal",           sw.AMMO_NIF_RELS["38cal"],           1, (-53.40, 27.90), (0.0, 0.0, 0.0), count=48,   tag="38cal"),
    RackItemSpec(0x000833, "FO4SF_P6_Ammo_FusionCellRef",     0x00089B, "fusioncell",      sw.AMMO_NIF_RELS["fusioncell"],      1, (-53.40, 28.20), (0.0, 0.0, 0.0), count=72,   tag="fusioncell"),
    RackItemSpec(0x000834, "FO4SF_P6_Ammo_5mmRef",            0x00089F, "5mm",             sw.AMMO_NIF_RELS["5mm"],             1, (-53.40, 28.50), (0.0, 0.0, 0.0), count=500,  tag="5mm"),
    RackItemSpec(0x000835, "FO4SF_P6_Ammo_308CalRef",         0x0008B0, "308cal",          sw.AMMO_NIF_RELS["308cal"],          2, (-53.40, 22.40), (0.0, 0.0, 0.0), count=30,   tag="308cal"),
    RackItemSpec(0x000836, "FO4SF_P6_Ammo_45CalRef",          0x0008B1, "45cal",           sw.AMMO_NIF_RELS["45cal"],           2, (-53.00, 22.40), (0.0, 0.0, 0.0), count=48,   tag="45cal"),
    RackItemSpec(0x000837, "FO4SF_P6_Ammo_ShotgunShellRef",   0x0008B2, "shotgunshell",    sw.AMMO_NIF_RELS["shotgunshell"],    2, (-52.40, 22.40), (0.0, 0.0, 0.0), count=32,   tag="shotgunshell"),
    RackItemSpec(0x000838, "FO4SF_P6_Ammo_556Ref",            0x0008B3, "556",             sw.AMMO_NIF_RELS["556"],             2, (-51.80, 22.40), (0.0, 0.0, 0.0), count=60,   tag="556"),
    RackItemSpec(0x000839, "FO4SF_P6_Ammo_MissileRef",        0x0008B4, "missile",         sw.AMMO_NIF_RELS["missile"],         3, (-50.40, 22.40), (0.0, 0.0, 0.0), count=6,    tag="missile"),
    RackItemSpec(0x00083A, "FO4SF_P6_Ammo_MiniNukeRef",       0x0008B5, "mininuke",        sw.AMMO_NIF_RELS["mininuke"],        3, (-50.00, 22.40), (0.0, 0.0, 0.0), count=3,    tag="mininuke"),
    RackItemSpec(0x00083B, "FO4SF_P6_Ammo_FlamerFuelRef",     0x0008B6, "flamerfuel",      sw.AMMO_NIF_RELS["flamerfuel"],      3, (-49.60, 22.40), (0.0, 0.0, 0.0), count=200,  tag="flamerfuel"),
    RackItemSpec(0x00083C, "FO4SF_P6_Ammo_PlasmaCartRef",     0x0008B7, "plasmacartridge", sw.AMMO_NIF_RELS["plasmacartridge"], 3, (-49.20, 22.40), (0.0, 0.0, 0.0), count=60,   tag="plasmacartridge"),
    RackItemSpec(0x00083D, "FO4SF_P6_Ammo_2mmEcRef",          0x0008B8, "2mmec",           sw.AMMO_NIF_RELS["2mmec"],           3, (-48.80, 22.40), (0.0, 0.0, 0.0), count=30,   tag="2mmec"),
)

PROP_RACK_SPECS: Tuple[RackItemSpec, ...] = (
    RackItemSpec(0x00083E, "FO4SF_P6_StimpakRef",  0x000851, "stimpak",  sw.CORE_ITEM_NIF_RELS["stimpak"],  1, (-53.40, 28.80), (0.0, 0.0, 0.0), count=3,  tag="stimpak"),
    RackItemSpec(0x00083F, "FO4SF_P6_CapsRef",     0x0008A4, "caps",     sw.CORE_ITEM_NIF_RELS["caps"],     1, (-53.40, 29.00), (0.0, 0.0, 0.0), count=25, tag="caps"),
    RackItemSpec(0x000840, "FO4SF_P6_BobbyPinRef", 0x0008A5, "bobbypin", sw.CORE_ITEM_NIF_RELS["bobbypin"], 1, (-53.40, 29.18), (0.0, 0.0, 0.0), count=5,  tag="bobbypin"),
)

STANDIN_DISCLOSURE = sw.STANDIN_DISCLOSURE


class ProbeP6Error(ValueError):
    """Raised when P6 staging, verification, floor-bounds, or install guards fail."""


# ---------------------------------------------------------------------------
# Pure-Python ESM / VMAD v6 & Bounds-Above-Floor Helpers (F4)
# ---------------------------------------------------------------------------
VMAD_T_OBJECT, VMAD_T_STRING, VMAD_T_INT, VMAD_T_FLOAT, VMAD_T_BOOL = 1, 2, 3, 4, 5
VMAD_T_OBJECT_ARR, VMAD_T_STRING_ARR, VMAD_T_INT_ARR = 11, 12, 13
QUST_VMAD_TAIL = b"\x03\x00\x00\x00\x00\x00\x00"


def _vmad_wstr(s: str) -> bytes:
    raw = str(s).encode("cp1252")
    if len(raw) > 0xFFFF:
        raise ProbeP6Error("VMAD string too long")
    return struct.pack("<H", len(raw)) + raw


def _encode_vmad_v6(scripts: Sequence[dict]) -> bytes:
    out = bytearray(struct.pack("<hHH", 6, 2, len(scripts)))
    for sc in scripts:
        props = sc.get("properties") or []
        out += _vmad_wstr(sc["name"]) + struct.pack("<BH", int(sc.get("status", 0)), len(props))
        for p in props:
            t = int(p["type"])
            out += _vmad_wstr(p["name"]) + struct.pack("<BB", t, int(p.get("status", 1)))
            v = p["value"]
            if t == VMAD_T_OBJECT:
                out += struct.pack("<HhI", 0, int(v.get("alias", -1)), int(v["form"]))
            elif t == VMAD_T_STRING:
                out += _vmad_wstr(v)
            elif t == VMAD_T_INT:
                out += struct.pack("<i", int(v))
            elif t == VMAD_T_FLOAT:
                out += struct.pack("<f", float(v))
            elif t == VMAD_T_BOOL:
                out += struct.pack("<B", 1 if v else 0)
            elif t == VMAD_T_OBJECT_ARR:
                out += struct.pack("<I", len(v))
                for elem in v:
                    out += struct.pack("<HhI", 0, int(elem.get("alias", -1)), int(elem["form"]))
            elif t == VMAD_T_STRING_ARR:
                out += struct.pack("<I", len(v))
                for s_item in v:
                    out += _vmad_wstr(s_item)
            elif t == VMAD_T_INT_ARR:
                out += struct.pack("<I", len(v))
                for i_item in v:
                    out += struct.pack("<i", int(i_item))
            else:
                raise ProbeP6Error(f"unsupported VMAD property type {t}")
    return bytes(out)


def _pack_subs(subs: Sequence[Tuple[bytes, bytes]]) -> bytes:
    out = bytearray()
    for sig, data in subs:
        if len(data) > 0xFFFF:
            out += b"XXXX" + struct.pack("<HI", 4, len(data)) + sig + struct.pack("<H", 0) + data
        else:
            out += sig + struct.pack("<H", len(data)) + data
    return bytes(out)


def _rec_bytes(sig: bytes, fid: int, subs: Sequence[Tuple[bytes, bytes]], flags: int = 0, version: int = 576) -> bytes:
    payload = _pack_subs(subs)
    return sig + struct.pack("<IIIIHH", len(payload), flags, fid, 0, version, 0) + payload


def _grup_bytes(label_4b: bytes, gtype: int, payload: bytes) -> bytes:
    return b"GRUP" + struct.pack("<I4sIII", 24 + len(payload), label_4b, gtype, 0, 0) + payload


def _count_records_and_grups(stream: bytes, start: int = 0, end: Optional[int] = None) -> int:
    stop = len(stream) if end is None else end
    pos = start
    count = 0
    while pos < stop:
        sig = stream[pos : pos + 4]
        sz, = struct.unpack_from("<I", stream, pos + 4)
        count += 1
        if sig == b"GRUP":
            count += _count_records_and_grups(stream, pos + 24, pos + sz)
            pos += sz
        else:
            pos += 24 + sz
    return count


def _rot_xyz_z_minmax(bmin: Tuple[float, float, float], bmax: Tuple[float, float, float], rot: Tuple[float, float, float]) -> Tuple[float, float]:
    """Return exact rotated local (min_z, max_z) over all 8 AABB corners (Euler X -> Y -> Z)."""
    rx, ry, rz = rot
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    # Only the Z component of Rz * Ry * Rx applied to (x, y, z):
    # Wait: Rz only mixes X,Y; Z comes solely from Ry * Rx: z' = -sin(ry)*x + cos(ry)*sin(rx)*y + cos(ry)*cos(rx)*z.
    # For safety across Euler conventions, check R = Rz * Ry * Rx AND Rx * Ry * Rz and take conservative min/max!
    zs: List[float] = []
    for px in (bmin[0], bmax[0]):
        for py in (bmin[1], bmax[1]):
            for pz in (bmin[2], bmax[2]):
                # Rz * Ry * Rx:
                y1, z1 = cx * py - sx * pz, sx * py + cx * pz
                zs.append(-sy * px + cy * z1)
                # Rx * Ry * Rz:
                x2, y2 = cz * px - sz * py, sz * px + cz * py
                x3, z3 = cy * x2 + sy * pz, -sy * x2 + cy * pz
                zs.append(sx * y2 + cx * z3)
    return min(zs), max(zs)


def compute_asset_local_bounds(assets_dir: Path) -> Dict[str, Tuple[Tuple[float, float, float], Tuple[float, float, float]]]:
    """Compute local (min_xyz, max_xyz) bounds for every staged weapon/ammo/core NIF from r11_weapons_manifest + mesh files."""
    bounds: Dict[str, Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = {}
    mpath = assets_dir / "r11_weapons_manifest.json"
    manifest: dict = {}
    if mpath.is_file():
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
        for key, info in manifest.get("weapons", {}).items():
            bmin = info.get("bounds_min_m")
            bmax = info.get("bounds_max_m")
            if bmin and bmax and len(bmin) == 3 and len(bmax) == 3:
                bounds[key] = ((float(bmin[0]), float(bmin[1]), float(bmin[2])), (float(bmax[0]), float(bmax[1]), float(bmax[2])))

    # Fill ammo + core items (and fallback weapons if synthetic manifest omitted bounds) directly from NIF + .mesh
    for group_key, spec_map in (
        ("weapons", sw.WEAPON_NIF_RELS),
        ("ammo", sw.AMMO_NIF_RELS),
        ("core", sw.CORE_ITEM_NIF_RELS),
    ):
        for k, nif_rel in spec_map.items():
            if k in bounds:
                continue
            np = assets_dir / Path(*nif_rel.split("/"))
            if not np.is_file():
                continue
            info = sw.inspect_weapon_nif_hierarchy(np.read_bytes())
            pts: List[Tuple[float, float, float]] = []
            for ginfo in info.get("geometries", {}).values():
                mrel = str(ginfo.get("mesh_rel") or "")
                mp = assets_dir / "geometries" / Path(*mrel.split("/"))
                mp = mp.with_suffix(".mesh")
                if mp.is_file():
                    m = sfmesh.parse(mp.read_bytes())
                    pts.extend(sfmesh.decode_position(pt, m.scale) for pt in m.positions)
            if pts:
                bounds[k] = (
                    (min(p[0] for p in pts), min(p[1] for p in pts), min(p[2] for p in pts)),
                    (max(p[0] for p in pts), max(p[1] for p in pts), max(p[2] for p in pts)),
                )
    return bounds


def _extract_port_cell_record_bytes(port_esm: Optional[Path], cell_fid: int = PORT_V111_CELL) -> bytes:
    if port_esm is not None and port_esm.is_file():
        raw = port_esm.read_bytes()
        pos = 0
        while pos < len(raw):
            sig = raw[pos : pos + 4]
            sz, = struct.unpack_from("<I", raw, pos + 4)
            if sig == b"GRUP":
                pos += 24
            else:
                fid, = struct.unpack_from("<I", raw, pos + 12)
                if sig == b"CELL" and fid == cell_fid:
                    return raw[pos : pos + 24 + sz]
                pos += 24 + sz
    return _rec_bytes(
        b"CELL",
        cell_fid,
        [(b"EDID", b"FO4Port_Vault111Cryo\x00"), (b"DATA", struct.pack("<H", 1))],
        flags=0,
        version=576,
    )


def _refr_item(
    fid: int,
    edid: str,
    base_fid: int,
    pos: Tuple[float, float, float],
    rot: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    count: Optional[int] = None,
    flags: int = REFR_PERSISTENT | REFR_DONT_HAVOK_SETTLE,
) -> bytes:
    subs: List[Tuple[bytes, bytes]] = [
        (b"EDID", edid.encode("ascii") + b"\x00"),
        (b"NAME", struct.pack("<I", base_fid)),
    ]
    if count is not None:
        subs.append((b"XCNT", struct.pack("<i", int(count))))
    subs.append((b"DATA", struct.pack("<6f", pos[0], pos[1], pos[2], rot[0], rot[1], rot[2])))
    return _rec_bytes(b"REFR", fid, subs, flags=flags)


def _build_nodisint_npc(raider_esm: Optional[Path]) -> bytes:
    """Create FO4SF_P6_NoDisintTargetNpc (0x04000802) carrying Starfield.esm NoDisintegrate (0x0022DB8F)."""
    kw_subs = [
        (b"KSIZ", struct.pack("<I", 1)),
        (b"KWDA", struct.pack("<I", SF_KW_NO_DISINTEGRATE)),
    ]
    if raider_esm is not None and raider_esm.is_file():
        with Plugin(str(raider_esm)) as rp:
            for r in rp.records("NPC_"):
                if (r.formid & 0xFFFFFF) == 0xF04801:
                    new_subs: List[Tuple[bytes, bytes]] = []
                    inserted_kw = False
                    for t, d in r.subs:
                        if t == b"EDID":
                            new_subs.append((b"EDID", b"FO4SF_P6_NoDisintTargetNpc\x00"))
                        elif t == b"FULL":
                            new_subs.append((b"FULL", b"Raider Target (NoDisintegrate)\x00"))
                        elif t in (b"KSIZ", b"KWDA"):
                            continue
                        elif t == b"TPTA" and len(d) >= 60:
                            # Keep traits/stats template slots 0..1 while clearing template keywords/inventory overrides
                            arr = bytearray(d)
                            for idx in range(2, len(arr) // 4):
                                struct.pack_into("<I", arr, idx * 4, 0)
                            new_subs.append((t, bytes(arr)))
                        elif t == b"STOP":
                            new_subs.extend(kw_subs)
                            inserted_kw = True
                            new_subs.append((t, d))
                        else:
                            new_subs.append((t, d))
                    if not inserted_kw:
                        new_subs.extend(kw_subs)
                    return _rec_bytes(b"NPC_", FID_NPC_NODISINT, new_subs, flags=r.flags)
    # Minimal standalone NPC_ fallback for isolated synthetic tests
    subs: List[Tuple[bytes, bytes]] = [
        (b"EDID", b"FO4SF_P6_NoDisintTargetNpc\x00"),
        (b"OBND", struct.pack("<6f", -0.35, -0.35, 0.0, 0.35, 0.35, 1.80)),
        (b"RNAM", struct.pack("<I", 0x0000347D)),
        (b"FULL", b"Raider Target (NoDisintegrate)\x00"),
        *kw_subs,
        (b"STOP", b""),
    ]
    return _rec_bytes(b"NPC_", FID_NPC_NODISINT, subs, flags=0)


def build_p6_arsenal_esm(
    assets_dir: Path,
    port_esm: Optional[Path] = None,
    raider_esm: Optional[Path] = None,
) -> Tuple[bytes, List[dict]]:
    """Build FO4SF_R11P6Arsenal.esm with F4-verified Vault111Cryo tables, 23 weapons, 13 ammos, 3 props, and 5 targets."""
    local_bounds = compute_asset_local_bounds(assets_dir)
    placement_audit: List[dict] = []

    acti_trigger = _rec_bytes(
        b"ACTI",
        FID_ACTI_TRIGGER,
        [
            (b"EDID", b"FO4SF_P6_TargetTriggerActi\x00"),
            (b"OBND", struct.pack("<6f", -0.35, -0.35, -0.35, 0.35, 0.35, 0.35)),
            (b"ODTY", struct.pack("<I", 0)),
            (b"FULL", b"P6 Arsenal Range Trigger\x00"),
            (b"MODL", SF_ACTI_MODL),
            (b"PNAM", struct.pack("<I", 0x0033CC4C)),
            (b"ATTX", b"Spawn / Reset Targets\x00"),
            (b"FNAM", struct.pack("<H", 0)),
            (b"JNAM", struct.pack("<H", 0x0168)),
        ],
    )
    npc_nodisint = _build_nodisint_npc(raider_esm)

    persistent_recs: List[bytes] = [
        _refr_item(FID_REF_TRIGGER, "FO4SF_P6_TargetTriggerRef", FID_ACTI_TRIGGER, OVERSEER_TRIGGER_POS, flags=REFR_PERSISTENT)
    ]
    placement_audit.append({
        "local_id": f"0x{FID_REF_TRIGGER & 0xFFFFFF:06X}",
        "edid": "FO4SF_P6_TargetTriggerRef",
        "kind": "trigger",
        "z": OVERSEER_TRIGGER_POS[2],
        "support_top_z": VAULT_FLOOR_Z,
        "world_min_z": round(OVERSEER_TRIGGER_POS[2] - 0.35, 4),
    })

    for fid, edid, pos, rot in TABLE_PLACEMENTS:
        persistent_recs.append(_refr_item(fid, edid, PORT_VAULT_TABLE_01, pos, rot=rot, flags=REFR_PERSISTENT | REFR_DONT_HAVOK_SETTLE))
        placement_audit.append({
            "local_id": f"0x{fid & 0xFFFFFF:06X}",
            "edid": edid,
            "kind": "table",
            "z": pos[2],
            "support_top_z": VAULT_FLOOR_Z,
            "world_min_z": round(pos[2], 4),
        })

    for sig_s, fid, edid, base_fid, pos, rot, flags, (z_lo, z_hi) in TARGET_SPECS:
        subs = [
            (b"EDID", edid.encode("ascii") + b"\x00"),
            (b"NAME", struct.pack("<I", base_fid)),
            (b"DATA", struct.pack("<6f", *pos, *rot)),
        ]
        persistent_recs.append(_rec_bytes(sig_s.encode("ascii"), fid, subs, flags=flags))
        placement_audit.append({
            "local_id": f"0x{fid & 0xFFFFFF:06X}",
            "edid": edid,
            "kind": f"target_{sig_s.lower()}",
            "z": pos[2],
            "support_top_z": VAULT_FLOOR_Z,
            "world_min_z": round(pos[2] + z_lo, 4),
        })

    def _place_rack_item(item: RackItemSpec, base_fid: int, kind: str) -> None:
        bmin, bmax = local_bounds.get(item.asset_key, ((-0.12, -0.12, -0.05), (0.12, 0.12, 0.15)))
        rot_min_z, rot_max_z = _rot_xyz_z_minmax(bmin, bmax, item.rot)
        z_place = round(VAULT_TABLE_TOP_Z - rot_min_z + 0.005, 4)
        world_min_z = round(z_place + rot_min_z, 4)
        fid = (M_LOCAL << 24) | item.local_ref_id
        persistent_recs.append(
            _refr_item(
                fid,
                item.ref_edid,
                base_fid,
                (item.xy[0], item.xy[1], z_place),
                rot=item.rot,
                count=item.count,
                flags=REFR_PERSISTENT | REFR_DONT_HAVOK_SETTLE,
            )
        )
        placement_audit.append({
            "local_id": f"0x{item.local_ref_id:06X}",
            "edid": item.ref_edid,
            "kind": kind,
            "asset_key": item.asset_key,
            "rack_table": item.rack_table,
            "z": z_place,
            "support_top_z": VAULT_TABLE_TOP_Z,
            "world_min_z": world_min_z,
            "world_max_z": round(z_place + rot_max_z, 4),
        })

    for item in WEAP_RACK_SPECS:
        _place_rack_item(item, (M_CV << 24) | item.cv_form_id, "weapon")
    for item in AMMO_RACK_SPECS:
        _place_rack_item(item, (M_CV << 24) | item.cv_form_id, "ammo")
    for item in PROP_RACK_SPECS:
        _place_rack_item(item, (M_CV << 24) | item.cv_form_id, "prop")

    cell_rec = _extract_port_cell_record_bytes(port_esm, cell_fid=PORT_V111_CELL)
    cell_children = _grup_bytes(struct.pack("<I", PORT_V111_CELL), 6, _grup_bytes(struct.pack("<I", PORT_V111_CELL), 8, b"".join(persistent_recs)))
    subblock_grup = _grup_bytes(struct.pack("<I", PORT_V111_SUBBLOCK), 3, cell_rec + cell_children)
    block_grup = _grup_bytes(struct.pack("<I", PORT_V111_BLOCK), 2, subblock_grup)

    props = [
        {"name": "TargetTrigger",   "type": VMAD_T_OBJECT,     "status": 1, "value": {"form": FID_REF_TRIGGER, "alias": -1}},
        {"name": "FleshDummy",      "type": VMAD_T_OBJECT,     "status": 1, "value": {"form": FID_ACHR_FLESH, "alias": -1}},
        {"name": "RobotDummy",      "type": VMAD_T_OBJECT,     "status": 1, "value": {"form": FID_ACHR_ROBOT, "alias": -1}},
        {"name": "NoDisintDummy",   "type": VMAD_T_OBJECT,     "status": 1, "value": {"form": FID_ACHR_NODISINT, "alias": -1}},
        {"name": "StoneTarget",     "type": VMAD_T_OBJECT,     "status": 1, "value": {"form": FID_REF_STONE, "alias": -1}},
        {"name": "WoodTarget",      "type": VMAD_T_OBJECT,     "status": 1, "value": {"form": FID_REF_WOOD, "alias": -1}},
        {"name": "ShowcaseWeapons", "type": VMAD_T_OBJECT_ARR, "status": 1, "value": [{"form": (M_CV << 24) | x.cv_form_id, "alias": -1} for x in WEAP_RACK_SPECS]},
        {"name": "WeaponTags",      "type": VMAD_T_STRING_ARR, "status": 1, "value": [x.tag for x in WEAP_RACK_SPECS]},
        {"name": "ShowcaseAmmos",   "type": VMAD_T_OBJECT_ARR, "status": 1, "value": [{"form": (M_CV << 24) | x.cv_form_id, "alias": -1} for x in AMMO_RACK_SPECS]},
        {"name": "AmmoTags",        "type": VMAD_T_STRING_ARR, "status": 1, "value": [x.tag for x in AMMO_RACK_SPECS]},
        {"name": "GrantAmmoCounts", "type": VMAD_T_INT_ARR,    "status": 1, "value": [int(x.count or 50) for x in AMMO_RACK_SPECS]},
        {"name": "CapsMisc",        "type": VMAD_T_OBJECT,     "status": 1, "value": {"form": (M_CV << 24) | 0x0008A4, "alias": -1}},
        {"name": "BobbyPinMisc",    "type": VMAD_T_OBJECT,     "status": 1, "value": {"form": (M_CV << 24) | 0x0008A5, "alias": -1}},
        {"name": "StimpakAlch",     "type": VMAD_T_OBJECT,     "status": 1, "value": {"form": (M_CV << 24) | 0x000851, "alias": -1}},
        {"name": "NoDisintegrateKw","type": VMAD_T_OBJECT,     "status": 1, "value": {"form": SF_KW_NO_DISINTEGRATE, "alias": -1}},
        {"name": "HealthAV",        "type": VMAD_T_OBJECT,     "status": 1, "value": {"form": SF_AV_HEALTH, "alias": -1}},
        {"name": "HideSuitAV",      "type": VMAD_T_OBJECT,     "status": 1, "value": {"form": SF_AV_HIDE_SUIT, "alias": -1}},
        {"name": "ArmoryCageDoorLocalId", "type": VMAD_T_INT,  "status": 1, "value": 0x001539},
        {"name": "PortPlugin",      "type": VMAD_T_STRING,     "status": 1, "value": "FO4Port.esm"},
        {"name": "EnableLog",       "type": VMAD_T_BOOL,       "status": 1, "value": True},
        {"name": "LogName",         "type": VMAD_T_STRING,     "status": 1, "value": "fo4sf_r11p6"},
    ]
    q_vmad = _encode_vmad_v6([{"name": "FO4SF_R11P6Quest", "status": 0, "properties": props}]) + QUST_VMAD_TAIL
    quest_rec = _rec_bytes(
        b"QUST",
        FID_QUST_P6,
        [
            (b"EDID", b"FO4SF_R11P6Quest\x00"),
            (b"VMAD", q_vmad),
            (b"FULL", b"R11 P6 Arsenal Probe\x00"),
            (b"DNAM", struct.pack("<III", QUST_START_GAME_ENABLED_FLAGS, 50, 0)),
            (b"QTYP", struct.pack("<I", 0x00047600)),
            (b"INDX", struct.pack("<I", 10)), (b"QSDT", b"\x00"),
            (b"INDX", struct.pack("<I", 15)), (b"QSDT", b"\x00"),
            (b"INDX", struct.pack("<I", 20)), (b"QSDT", b"\x00"),
            (b"INDX", struct.pack("<I", 30)), (b"QSDT", b"\x00"),
        ],
        flags=0,
        version=581,
    )

    body = (
        _grup_bytes(b"ACTI", 0, acti_trigger)
        + _grup_bytes(b"NPC_", 0, npc_nodisint)
        + _grup_bytes(b"CELL", 0, block_grup)
        + _grup_bytes(b"QUST", 0, quest_rec)
    )
    masters = ("Starfield.esm", "FO4Port.esm", "FO4SFCoreValues.esm", "FO4ActorRaider.esm")
    next_obj_id = 0x000841
    tes4_subs: List[Tuple[bytes, bytes]] = [(b"HEDR", struct.pack("<fII", 0.96, _count_records_and_grups(body), next_obj_id))]
    for m in masters:
        tes4_subs.append((b"MAST", m.encode("ascii") + b"\x00"))
        tes4_subs.append((b"DATA", struct.pack("<Q", 0)))
    tes4 = _rec_bytes(b"TES4", 0, tes4_subs, flags=1, version=576)
    return tes4 + body, placement_audit


def verify_placed_refs_above_floor(placement_audit: Sequence[Mapping[str, object]], floor_z: float = VAULT_FLOOR_Z) -> None:
    """Enforce F4 invariant: every placed ref has world_min_z >= floor_z - 0.002 and racked items rest above table_top_z."""
    for entry in placement_audit:
        wmin = float(entry["world_min_z"])
        sup = float(entry.get("support_top_z", floor_z))
        if wmin < floor_z - 0.002:
            raise ProbeP6Error(f"F4 violation: {entry['edid']} ({entry['local_id']}) world_min_z={wmin} < floor_z={floor_z}")
        if entry["kind"] in ("weapon", "ammo", "prop") and wmin < sup - 0.002:
            raise ProbeP6Error(f"F4 rack violation: {entry['edid']} ({entry['local_id']}) world_min_z={wmin} < table_top={sup}")


# ---------------------------------------------------------------------------
# P3 Batch Scripts & Hop Validation
# ---------------------------------------------------------------------------
def build_p3_batch_scripts(quest_load_prefix: int = DEFAULT_QUEST_LOAD_PREFIX) -> Dict[str, str]:
    qhex = f"{quest_load_prefix:02X}{QUST_P6_LOCAL_ID:06X}"
    batches = {
        "p6r.txt": (
            "; R11 P6 enter Vault 111 P6 firing line beside Rack 1 facing 5 targets east\n"
            "coc FO4Port_Vault111Cryo\n"
            f"player.setpos x {OVERSEER_P6_STANCE[0]:.2f}\n"
            f"player.setpos y {OVERSEER_P6_STANCE[1]:.2f}\n"
            f"player.setpos z {OVERSEER_P6_STANCE[2]:.2f}\n"
            "player.setangle z 90\n"
        ),
        "p6t.txt": (
            "; R11 P6 face east on firing line and spawn/reset Flesh, SF Robot, NoDisint, Stone, Wood targets\n"
            f"player.setpos x {OVERSEER_P6_STANCE[0]:.2f}\n"
            f"player.setpos y {OVERSEER_P6_STANCE[1]:.2f}\n"
            f"player.setpos z {OVERSEER_P6_STANCE[2]:.2f}\n"
            "player.setangle z 90\n"
            f"SetStage {qhex} 20\n"
        ),
        "p6a.txt": (
            "; R11 P6 interior hop to South Overseer weapon racks 2 and 3 showcase tables\n"
            f"player.setpos x {OVERSEER_P6_RACKS_STANCE[0]:.2f}\n"
            f"player.setpos y {OVERSEER_P6_RACKS_STANCE[1]:.2f}\n"
            f"player.setpos z {OVERSEER_P6_RACKS_STANCE[2]:.2f}\n"
            "player.setangle z 180\n"
        ),
        "p6g.txt": (
            "; R11 P6 grant all 23 playable FO4 weapons + 13 ammos + Stimpak/Caps/BobbyPin\n"
            f"SetStage {qhex} 10\n"
        ),
        "p6c.txt": (
            "; R11 P6 cycle-equip next FO4 weapon across all 23 arsenal rows\n"
            f"SetStage {qhex} 15\n"
        ),
        "p6h1.txt": (
            "; R11 P6 exterior mid-hop from Sanctuary (<80 m/axis) toward Vault 111 hilltop\n"
            f"player.setpos x {EXT_HOP_MID[0]:.2f}\n"
            f"player.setpos y {EXT_HOP_MID[1]:.2f}\n"
            f"player.setpos z {EXT_HOP_MID[2]:.2f}\n"
            "player.setangle z 275\n"
        ),
        "p6e.txt": (
            "; R11 P6 exterior Vault 111 hilltop clearing (<70 m/axis from p6h1)\n"
            f"player.setpos x {V111_HILLTOP[0]:.2f}\n"
            f"player.setpos y {V111_HILLTOP[1]:.2f}\n"
            f"player.setpos z {V111_HILLTOP[2]:.2f}\n"
            "player.setangle z 90\n"
        ),
        "p6s.txt": (
            "; R11 P6 write scorecard summary line to fo4sf_r11p6 user log\n"
            f"SetStage {qhex} 30\n"
        ),
        "p6q.txt": (
            "; R11 P6 query quest stage status\n"
            f"getstage {qhex}\n"
            f"sqs {qhex}\n"
        ),
    }
    return batches


def _p6_anchors_and_hops() -> Tuple[List[pc.AnchorPoint], List[pc.HopSpec]]:
    anchors = [
        SANCTUARY_BENCH_ANCHOR,
        P6H1_ANCHOR,
        pc.AnchorPoint("p6_firing", *OVERSEER_P6_STANCE, "interior", "FO4Port_Vault111Cryo"),
    ]
    hops = [
        pc.HopSpec("sanctuary_to_p6h1", "sanctuary_bench", *EXT_HOP_MID, "exterior"),
        pc.HopSpec("p6h1_to_p6e_hilltop", "p6h1", *V111_HILLTOP, "exterior"),
        pc.HopSpec("p6_firing_to_racks", "p6_firing", *OVERSEER_P6_RACKS_STANCE, "interior", "FO4Port_Vault111Cryo"),
    ]
    return anchors, hops


def validate_p6_batches(bat_dir: Path) -> List[str]:
    batch_files = sorted(bat_dir.glob("*.txt"))
    activate_cmds = [f"bat {p.stem}" for p in batch_files]
    anchors, hops = _p6_anchors_and_hops()
    return pc.validate_batches_and_hops(
        batch_files=batch_files,
        activate_commands=activate_cmds,
        anchors=anchors,
        hops=hops,
        interior_mode=False,
        raise_on_error=True,
    )


def compile_papyrus(starfield_dir: Path, psc_path: Path, out_dir: Path) -> Path:
    compiler = starfield_dir / "Tools" / "Papyrus Compiler" / "PapyrusCompiler.exe"
    content_zip = starfield_dir / "Tools" / "ContentResources.zip"
    if not compiler.is_file() or not content_zip.is_file():
        raise ProbeP6Error(f"missing PapyrusCompiler.exe or ContentResources.zip under {starfield_dir / 'Tools'}")
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="p6_papyrus_") as tdir:
        base_src = Path(tdir) / "Source"
        base_src.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(content_zip) as zf:
            for member in zf.namelist():
                parts = member.split("/")
                if len(parts) == 3 and parts[:2] == ["Scripts", "Source"] and (
                    parts[2].lower().endswith(".psc") or parts[2] == "Starfield_Papyrus_Flags.flg"
                ):
                    (base_src / parts[2]).write_bytes(zf.read(member))
        r = subprocess.run(
            [
                str(compiler),
                psc_path.name,
                "-f=Starfield_Papyrus_Flags.flg",
                f"-i={base_src};{psc_path.parent}",
                f"-o={out_dir}",
            ],
            cwd=str(psc_path.parent),
            capture_output=True,
            text=True,
            check=False,
        )
        pex = out_dir / f"{psc_path.stem}.pex"
        if r.returncode != 0 or "Compilation succeeded" not in r.stdout or not pex.is_file():
            raise ProbeP6Error(f"Papyrus compile failed for {psc_path.name}:\n{r.stdout}\n{r.stderr}")
        return pex


def _build_core_values(sf_esm: Path, out_dir: Path) -> Path:
    proj = REPO / "dotnet" / "CoreValues" / "CoreValues.csproj"
    r = subprocess.run(
        [
            "dotnet", "run", "--project", str(proj), "-c", "Release", "--",
            "build", str(sf_esm), str(out_dir),
            "--test-mode", "0", "--commonwealth-weather", "1",
            "--fo4-10mm", "1", "--fo4-p5-weapons", "1", "--fo4-arsenal", "1",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    cv_esm = out_dir / "FO4SFCoreValues.esm"
    if r.returncode != 0 or not cv_esm.is_file():
        raise ProbeP6Error(f"CoreValues build failed:\n{r.stdout}\n{r.stderr}")
    chk = subprocess.run(
        [
            "dotnet", "run", "--project", str(proj), "-c", "Release", "--no-build", "--",
            "check", str(cv_esm), str(sf_esm),
            "--test-mode", "0", "--commonwealth-weather", "1",
            "--fo4-10mm", "1", "--fo4-p5-weapons", "1", "--fo4-arsenal", "1",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    if chk.returncode != 0:
        raise ProbeP6Error(f"CoreValues check failed:\n{chk.stdout}\n{chk.stderr}")
    return cv_esm


# ---------------------------------------------------------------------------
# Stage, Verify, Install, Uninstall, Status
# ---------------------------------------------------------------------------
def stage_probe_p6(
    out_dir: Path,
    fo4_data: Optional[Path] = None,
    starfield_dir: Optional[Path] = None,
    port_esm: Optional[Path] = None,
    raider_esm: Optional[Path] = None,
    prebuilt_core_values: Optional[Path] = None,
    prebuilt_assets_dir: Optional[Path] = None,
    prebuilt_pex: Optional[Dict[str, bytes]] = None,
    ship_pipboy_dll: bool = False,
    tested_pipboy_dll: Optional[Path] = None,
    clean: bool = False,
    min_free_gb: float = pc.DEFAULT_MIN_FREE_GB,
) -> dict:
    """Build and verify standalone Probe P6 (`r11-p6-arsenal`) using probe_common helpers."""
    pc.check_starfield_not_running()
    pc.check_free_space_gb(out_dir, min_gb=min_free_gb)

    # Preserve prebuilt sources outside out_dir before clean=True wipes out_dir
    tmp_hold: Optional[tempfile.TemporaryDirectory] = None
    try:
        eff_cv_src = prebuilt_core_values
        eff_assets_src = prebuilt_assets_dir
        out_abs = out_dir.resolve()
        if clean and ((eff_cv_src and out_abs in eff_cv_src.resolve().parents) or (eff_assets_src and out_abs in eff_assets_src.resolve().parents)):
            tmp_hold = tempfile.TemporaryDirectory(prefix="p6_hold_")
            hold_p = Path(tmp_hold.name)
            if eff_cv_src and eff_cv_src.is_file():
                dst = hold_p / "FO4SFCoreValues.esm"
                shutil.copy2(eff_cv_src, dst)
                eff_cv_src = dst
            if eff_assets_src and eff_assets_src.is_dir():
                dst_a = hold_p / "assets"
                shutil.copytree(eff_assets_src, dst_a)
                eff_assets_src = dst_a

        pc.check_out_dir_safe(out_dir, clean=clean)
        free_before = pc.check_free_space_gb(out_dir, min_gb=min_free_gb)

        core_dir = out_dir / "core"
        assets_dir = out_dir / "assets"
        exp_dir = out_dir / "exp"
        bat_dir = out_dir / "bat"
        for d in (core_dir, exp_dir, bat_dir):
            d.mkdir(parents=True, exist_ok=True)

        sf_data = starfield_dir / "Data" if starfield_dir is not None else None
        eff_port_esm = port_esm or (sf_data / "FO4Port.esm" if sf_data is not None else None)
        eff_raider_esm = raider_esm or (sf_data / "FO4ActorRaider.esm" if sf_data is not None else None)

        # 1. CoreValues ESM
        cv_dst = core_dir / "FO4SFCoreValues.esm"
        if eff_cv_src is not None:
            pc.copy_or_link_staged_file(eff_cv_src, cv_dst, allow_hardlink=False)
        else:
            if sf_data is None:
                raise ProbeP6Error("either --starfield or --prebuilt-core-values is required")
            _build_core_values(sf_data / "Starfield.esm", core_dir)

        # 2. Weapons + ammo + props + projectiles assets
        if eff_assets_src is not None:
            shutil.copytree(eff_assets_src, assets_dir)
        else:
            if fo4_data is None or sf_data is None:
                raise ProbeP6Error("either --fo4-data + --starfield or --prebuilt-assets-dir is required")
            sw.stage_r11_weapons(str(fo4_data), str(sf_data), str(assets_dir), scope="all")

        sw.verify_staged_weapons(str(assets_dir), require_converted_materials=True, require_collision=True, require_all_arsenal=True)

        # 3. Optional tested FO4SFPipboyMenu.dll reuse (never rebuilt from changed source without verification)
        overridden_files = ["Data/FO4SFCoreValues.esm"]
        pipboy_reuse_info: Optional[dict] = None
        if ship_pipboy_dll:
            src_dir = REPO / "sfse" / "FO4SFPipboyMenu"
            src_files = sorted(
                p for p in src_dir.rglob("*")
                if p.is_file() and p.name.casefold() in {k.casefold() for k in pc.TESTED_PIPBOY_SOURCE_HASHES}
            )
            if tested_pipboy_dll is None:
                raise ProbeP6Error("--tested-pipboy-dll is required when --ship-pipboy-dll is set")
            fallback_bin = tested_pipboy_dll

            def _reuse_verified_7d5ba49c() -> Path:
                if not fallback_bin.is_file() or not pc.sha256_file(fallback_bin).startswith(pc.TESTED_PIPBOY_DLL_SHA256_PREFIX):
                    raise ProbeP6Error(f"Refusing unverified FO4SFPipboyMenu.dll (expected {pc.TESTED_PIPBOY_DLL_SHA256_PREFIX}...)")
                return fallback_bin

            dll_dst = exp_dir / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll"
            res = pc.reuse_tested_binary(
                src_files=src_files,
                tested_src_hash=pc.TESTED_PIPBOY_SOURCE_HASHES,
                tested_bin_path=fallback_bin,
                fallback_build_fn=_reuse_verified_7d5ba49c,
                dst_path=dll_dst,
            )
            if not res.bin_sha256.startswith(pc.TESTED_PIPBOY_DLL_SHA256_PREFIX):
                raise ProbeP6Error(f"Shipped FO4SFPipboyMenu.dll SHA-256 mismatch: {res.bin_sha256}")
            pipboy_reuse_info = {"shipped": True, "reused": res.reused, "src_hash": res.src_hash, "sha256": res.bin_sha256}
            overridden_files.append("SFSE/Plugins/FO4SFPipboyMenu.dll")
        else:
            pipboy_reuse_info = {"shipped": False, "note": "Preserves installed candidate FO4SFPipboyMenu.dll untouched (7d5ba49c required on candidate-2g-fix)"}

        # 4. Build FO4SF_R11P6Arsenal.esm & compile FO4SF_R11P6Quest.pex
        p6_esm_bytes, placement_audit = build_p6_arsenal_esm(assets_dir, port_esm=eff_port_esm, raider_esm=eff_raider_esm)
        verify_placed_refs_above_floor(placement_audit, floor_z=VAULT_FLOOR_Z)
        (exp_dir / PROBE_PLUGIN).write_bytes(p6_esm_bytes)

        scripts_out = exp_dir / "Data" / "Scripts"
        scripts_out.mkdir(parents=True, exist_ok=True)
        if prebuilt_pex is not None:
            pex_items = []
            for stem, raw in sorted(prebuilt_pex.items()):
                (scripts_out / f"{stem}.pex").write_bytes(raw)
                pex_items.append((f"Scripts\\{stem}.pex", raw))
        else:
            if starfield_dir is None:
                raise ProbeP6Error("either --starfield or prebuilt_pex is required")
            pex_p = compile_papyrus(starfield_dir, HERE / "FO4SF_R11P6Quest.psc", scripts_out)
            pex_items = [(f"Scripts\\{pex_p.stem}.pex", pex_p.read_bytes())]

        # 5. Pack BA2s via probe_common
        gnrl_map: Dict[str, Union[bytes, Path]] = {name: raw for name, raw in pex_items}
        dx10_map: Dict[str, Path] = {}
        for ap in sorted(assets_dir.rglob("*")):
            if not ap.is_file() or ap.name.endswith("_manifest.json") or ap.name == "manifest.json":
                continue
            rel = ap.relative_to(assets_dir).as_posix().lower()
            if rel.startswith("textures/") and rel.endswith(".dds"):
                dx10_map[rel] = ap
            else:
                gnrl_map[rel] = ap

        main_ba2_p = pc.pack_gnrl_ba2(gnrl_map, exp_dir / PROBE_MAIN_BA2)
        tex_ba2_p = pc.pack_dx10_ba2(dx10_map, exp_dir / PROBE_TEX_BA2)
        pc.verify_ba2_entry_hashes(main_ba2_p)
        pc.verify_ba2_entry_hashes(tex_ba2_p, source_files=dx10_map)

        # 6. Write & validate P3 batches + hops via probe_common
        batches = build_p3_batch_scripts()
        for fname, txt in sorted(batches.items()):
            (bat_dir / fname).write_text(txt, encoding="utf-8", newline="\n")
        validate_p6_batches(bat_dir)

        # 7. Binary ESM cleanliness + cross_plugin_check validation
        pc.scan_plugin_cleanliness(
            [cv_dst, exp_dir / PROBE_PLUGIN],
            reference_esms=[p for p in (eff_port_esm, eff_raider_esm) if p and p.is_file()],
        )
        catalog, dups = cpc.build_writer_catalog(str(REPO))
        if dups:
            raise ProbeP6Error(f"writer catalog duplicates: {dups}")
        psc_props = cpc.collect_psc_props_by_script(str(REPO))
        errs = cpc.validate_staged_esms([str(cv_dst), str(exp_dir / PROBE_PLUGIN)], catalog, psc_props)
        if errs:
            raise ProbeP6Error(f"cross_plugin_check errors on P6 .esm set: {errs}")

        # 8. Install plan + full SHA-256 manifest
        install_files: List[dict] = [
            {"src_rel": "core/FO4SFCoreValues.esm", "target_rel": "Data/FO4SFCoreValues.esm", "allow_swap": True, "sha256": pc.sha256_file(cv_dst)},
            {"src_rel": f"exp/{PROBE_PLUGIN}", "target_rel": f"Data/{PROBE_PLUGIN}", "sha256": pc.sha256_file(exp_dir / PROBE_PLUGIN)},
            {"src_rel": f"exp/{PROBE_MAIN_BA2}", "target_rel": f"Data/{PROBE_MAIN_BA2}", "sha256": pc.sha256_file(main_ba2_p)},
            {"src_rel": f"exp/{PROBE_TEX_BA2}", "target_rel": f"Data/{PROBE_TEX_BA2}", "sha256": pc.sha256_file(tex_ba2_p)},
        ]
        if ship_pipboy_dll:
            dll_p = exp_dir / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll"
            install_files.append({"src_rel": "exp/SFSE/Plugins/FO4SFPipboyMenu.dll", "target_rel": "SFSE/Plugins/FO4SFPipboyMenu.dll", "allow_swap": True, "sha256": pc.sha256_file(dll_p)})
        for fname in sorted(batches):
            bp = bat_dir / fname
            install_files.append({"src_rel": f"bat/{fname}", "target_rel": fname, "sha256": pc.sha256_file(bp)})

        file_hashes = {
            p.relative_to(out_dir).as_posix(): {"size_bytes": p.stat().st_size, "sha256": pc.sha256_file(p)}
            for p in sorted(out_dir.rglob("*"))
            if p.is_file() and p.name != "manifest.json"
        }
        manifest = {
            "probe": PROBE_ID,
            "version": 1,
            "status": "OFFLINE VERIFIED / UNPROVEN IN GAME",
            "standin_disclosure": STANDIN_DISCLOSURE,
            "overridden_candidate_files": overridden_files,
            "pipboy_dll": pipboy_reuse_info,
            "disk_free_gb_before": round(free_before, 2),
            "disk_free_gb_after": round(pc.check_free_space_gb(out_dir, min_gb=min_free_gb), 2),
            "placement_floor_audit": placement_audit,
            "install_files": install_files,
            "files": file_hashes,
        }
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        verify_probe_p6(out_dir)
        return manifest
    finally:
        if tmp_hold is not None:
            tmp_hold.cleanup()


def verify_probe_p6(stage_dir: Path) -> dict:
    """Read-only verification of manifest hashes, BA2 entry hashes, P3/hops, ESM cleanliness, and F4 floor bounds."""
    mpath = stage_dir / "manifest.json"
    if not mpath.is_file():
        raise ProbeP6Error(f"manifest.json missing in {stage_dir}")
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    files = manifest.get("files", {})
    if not files:
        raise ProbeP6Error("manifest.json has no files")
    for rel, meta in files.items():
        p = stage_dir / rel
        if not p.is_file():
            raise ProbeP6Error(f"missing staged file: {rel}")
        if p.stat().st_size != meta["size_bytes"] or pc.sha256_file(p) != meta["sha256"]:
            raise ProbeP6Error(f"hash/size mismatch for {rel}")
        if p.suffix.lower() in pc.COPY_ONLY_EXTENSIONS and os.lstat(p).st_nlink != 1:
            raise ProbeP6Error(f"expected st_nlink==1 on {rel}")

    verify_placed_refs_above_floor(manifest.get("placement_floor_audit", []), floor_z=VAULT_FLOOR_Z)
    pc.verify_ba2_entry_hashes(stage_dir / "exp" / PROBE_MAIN_BA2)
    pc.verify_ba2_entry_hashes(stage_dir / "exp" / PROBE_TEX_BA2)
    sw.verify_staged_weapons(str(stage_dir / "assets"), require_converted_materials=True, require_collision=True, require_all_arsenal=True)
    pc.scan_plugin_cleanliness([stage_dir / "core" / "FO4SFCoreValues.esm", stage_dir / "exp" / PROBE_PLUGIN])
    validate_p6_batches(stage_dir / "bat")

    main_ba2 = Ba2(str(stage_dir / "exp" / PROBE_MAIN_BA2))
    tex_ba2 = Ba2(str(stage_dir / "exp" / PROBE_TEX_BA2))
    return {
        "verified": True,
        "verified_files": len(files),
        "main_ba2_entries": len(main_ba2.entries),
        "textures_ba2_entries": len(tex_ba2.entries),
        "placed_refs_checked": len(manifest.get("placement_floor_audit", [])),
        "overridden_candidate_files": manifest.get("overridden_candidate_files", []),
    }


def _compute_full_master_load_index(data_dir: Path, plugins_txt: Optional[Path], target_plugin: str) -> int:
    """Resolve runtime full-master slot index (skipping Light FE/Small FD plugins) for `<XX>000830` batches."""
    implicit = ("Starfield.esm", "Constellation.esm", "OldMars.esm", "BlueprintShips-Starfield.esm", "ShatteredSpace.esm")
    lines: List[str] = list(implicit)
    if plugins_txt is not None and plugins_txt.is_file():
        for raw in plugins_txt.read_text(encoding="utf-8-sig").splitlines():
            s = raw.strip().lstrip("*")
            if s and not s.startswith("#") and s not in lines:
                lines.append(s)
    if target_plugin not in lines:
        lines.append(target_plugin)
    slot = 0
    for name in lines:
        if name.casefold() == target_plugin.casefold():
            return slot
        p = data_dir / name
        if p.is_file():
            try:
                with p.open("rb") as fh:
                    hdr = fh.read(24)
                if len(hdr) >= 12 and hdr[:4] == b"TES4":
                    flags, = struct.unpack_from("<I", hdr, 8)
                    if flags & 0x0300:  # Light (0x200) or Small/Medium (0x100)
                        continue
            except OSError:
                pass
        slot += 1
    return slot


def install_probe_p6(
    stage_dir: Path,
    starfield_dir: Path,
    plugins_txt: Optional[Path] = None,
    version_tag: str = "",
    card_path: Optional[Path] = None,
    min_free_gb: float = pc.DEFAULT_MIN_FREE_GB,
) -> dict:
    verify_probe_p6(stage_dir)
    manifest = json.loads((stage_dir / "manifest.json").read_text(encoding="utf-8"))
    plg_txt = pc._resolve_plugins_txt(starfield_dir, plugins_txt)
    slot_idx = _compute_full_master_load_index(starfield_dir / "Data", plg_txt, PROBE_PLUGIN)
    stamped_batches = build_p3_batch_scripts(quest_load_prefix=slot_idx)
    install_specs = [dict(x) for x in manifest["install_files"] if not str(x.get("target_rel", "")).endswith(".txt")]
    with tempfile.TemporaryDirectory(prefix="p6_bat_") as td:
        bat_tmp = Path(td)
        for fname, txt in sorted(stamped_batches.items()):
            bp = bat_tmp / fname
            bp.write_text(txt, encoding="utf-8", newline="\n")
            install_specs.append({"src_rel": str(bp), "target_rel": fname, "sha256": pc.sha256_file(bp)})
        return pc.install_probe(
            probe_id=PROBE_ID,
            stage_dir=stage_dir,
            starfield_dir=starfield_dir,
            plugins_txt=plugins_txt,
            plugins_to_activate=[PROBE_PLUGIN],
            files=install_specs,
            expected_base_hashes={"Data/FO4Port.esm": pc.BASE_FO4PORT_SHA256_PREFIX},
            baseline_2g_fix2_hashes=pc.CANDIDATE_2G_FIX2_HASHES,
            version_tag=version_tag,
            card_path=card_path,
            min_free_gb=min_free_gb,
        )


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Round 11 Probe P6 (Full Arsenal) stager & installer")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s_st = sub.add_parser("stage")
    s_st.add_argument("--fo4-data", default=None, type=Path)
    s_st.add_argument("--starfield", default=None, type=Path)
    s_st.add_argument("--port-esm", default=None, type=Path)
    s_st.add_argument("--raider-esm", default=None, type=Path)
    s_st.add_argument("--prebuilt-core-values", default=None, type=Path)
    s_st.add_argument("--prebuilt-assets-dir", default=None, type=Path)
    s_st.add_argument("--out-dir", required=True, type=Path)
    s_st.add_argument("--ship-pipboy-dll", action="store_true")
    s_st.add_argument("--tested-pipboy-dll", default=None, type=Path)
    s_st.add_argument("--clean", action="store_true")
    s_st.add_argument("--min-free-gb", default=pc.DEFAULT_MIN_FREE_GB, type=float)

    s_vf = sub.add_parser("verify")
    s_vf.add_argument("--stage-dir", required=True, type=Path)

    s_in = sub.add_parser("install")
    s_in.add_argument("--stage-dir", required=True, type=Path)
    s_in.add_argument("--starfield", required=True, type=Path)
    s_in.add_argument("--plugins-txt", default=None, type=Path)
    s_in.add_argument("--version-tag", default="")
    s_in.add_argument("--card-path", default=None, type=Path)
    s_in.add_argument("--min-free-gb", default=pc.DEFAULT_MIN_FREE_GB, type=float)

    s_un = sub.add_parser("uninstall")
    s_un.add_argument("--starfield", required=True, type=Path)
    s_un.add_argument("--force", action="store_true")

    s_stat = sub.add_parser("status")
    s_stat.add_argument("--starfield", required=True, type=Path)

    args = ap.parse_args(argv)
    if args.cmd == "stage":
        m = stage_probe_p6(
            out_dir=args.out_dir,
            fo4_data=args.fo4_data,
            starfield_dir=args.starfield,
            port_esm=args.port_esm,
            raider_esm=args.raider_esm,
            prebuilt_core_values=args.prebuilt_core_values,
            prebuilt_assets_dir=args.prebuilt_assets_dir,
            ship_pipboy_dll=args.ship_pipboy_dll,
            tested_pipboy_dll=args.tested_pipboy_dll,
            clean=args.clean,
            min_free_gb=args.min_free_gb,
        )
        print(f"staged {PROBE_ID} -> {args.out_dir} ({len(m['files'])} files, free={m['disk_free_gb_after']} GiB)")
        return 0
    if args.cmd == "verify":
        print(json.dumps(verify_probe_p6(args.stage_dir), indent=2, sort_keys=True))
        return 0
    if args.cmd == "install":
        print(json.dumps(install_probe_p6(args.stage_dir, args.starfield, args.plugins_txt, args.version_tag, args.card_path, args.min_free_gb), indent=2, sort_keys=True))
        return 0
    if args.cmd == "uninstall":
        print(json.dumps(pc.uninstall_probe(probe_id=PROBE_ID, starfield_dir=args.starfield, force=args.force), indent=2, sort_keys=True))
        return 0
    if args.cmd == "status":
        print(json.dumps(pc.probe_status(probe_id=PROBE_ID, starfield_dir=args.starfield), indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
