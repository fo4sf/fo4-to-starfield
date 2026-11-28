"""stage_r11_p5_weapons.py: Round 11 Probe P5 (Baton, 10mm Pistol, Laser Musket & Minigun) stager, verifier & installer.

Builds the standalone Probe P5 folder (outside Git worktrees, outside Starfield Data, and outside any candidate-* folder):
  <out-dir>/
    core/
      FO4SFCoreValues.esm               (--fo4-10mm 1 --fo4-p5-weapons 1: 0x000898..0x0008A0)
      FO4SFNewGame.esm                  (--fo4-10mm 1: 0x0820 FO4_10mmPistol + 0x0821 48x FO4_Ammo10mm on armory shelf)
    assets/
      meshes/fo4sf/weapons/baton/fo4_baton.nif
      meshes/fo4sf/weapons/10mm/fo4_10mmpistol.nif
      meshes/fo4sf/weapons/lasermusket/fo4_lasermusket.nif
      meshes/fo4sf/weapons/minigun/fo4_minigun.nif
      meshes/fo4core/ammo/10mm/10mmammo.nif
      meshes/fo4core/ammo/laserammo/microfusioncell.nif
      meshes/fo4core/ammo/5mm/5mmammo.nif
      geometries/...                    (external .mesh v2 files)
      materials/...                     (.mat files)
      textures/...                      (BC1/BC5/BC4/DX10 .dds files)
    exp/
      FO4SF_R11P5Weapons.esm            (FO4 Vault 111 Batons 0x0019891C & 0x000AE470, range Laser Musket + 3x24 Cells,
                                         Minigun + 500x 5mm, E-trigger, InitiallyDisabled unarmed TargetDummy, StartGameEnabled QUST)
      FO4SF_R11P5Weapons - Main.ba2     (BTDX v2 GNRL: .pex + .nif + .mesh + .mat, bs_crc32 verified)
      FO4SF_R11P5Weapons - Textures.ba2 (BTDX v2 DX10: .dds textures, bs_crc32 verified)
      Data/Scripts/FO4SF_NewGameQuest.pex
      Data/Scripts/FO4SF_R11P5Quest.pex
    bat/                                (P3-clean .txt batch files: 0 M/N/V in filenames/typed commands, 0 stripped FO4SF_ EDIDs)
      p5b1.txt, p5b2.txt, p5d.txt, p5o.txt, p5r.txt, p5t.txt, p5g.txt, p5h1.txt, p5e.txt, p5s.txt, p5q.txt
    manifest.json                       (SHA-256 + byte sizes + moving-part NiNode trees + stand-in disclosures)

P4 notes resolved cleanly in P5:
  - Zero non-persistent cross-plugin VMAD properties (ArmoryCageDoor 0x001539 resolved via Game.GetFormFromFile).
  - QUST DNAM = 0x00000009 (StartGameEnabled | AllowRepeatedStages) so fo4sf_r11p5.0.log logs from game start.
  - TargetDummy is stripped unarmed (RemoveAllItems), restrained, and resettable via E-activator or bat p5t.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SRC_DIR = REPO / "src"
WEAPONS_DIR = REPO / "scripts" / "weapons"

for _p in (str(SRC_DIR), str(WEAPONS_DIR), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import probe_common as pc  # noqa: E402
from fo4sf import nif as nifmod  # noqa: E402
from fo4sf.ba2 import Ba2  # noqa: E402
from fo4sf.core import cross_plugin_check as cpc  # noqa: E402
from fo4sf.launcher.crashwatch import GAME_EXE, System  # noqa: E402
from fo4sf.planet.esm import Plugin, parse_subrecords  # noqa: E402

PROBE_NAME = "r11-p5-weapons"
PROBE_STEM = "FO4SF_R11P5Weapons"
PROBE_PLUGIN = f"{PROBE_STEM}.esm"
PROBE_MAIN_BA2 = f"{PROBE_STEM} - Main.ba2"
PROBE_TEX_BA2 = f"{PROBE_STEM} - Textures.ba2"
INSTALL_RECEIPT = "FO4SF_R11P5.install.json"
SWAPPED_CORE_ESMS = ("FO4SFCoreValues.esm", "FO4SFNewGame.esm")
DEFAULT_MIN_FREE_GB = 60.0
BA2_ALIGN = 0xBAADF00D

IMPLICIT_FULL_MASTERS = pc.IMPLICIT_FULL_MASTERS

# Master indices in FO4SF_R11P5Weapons.esm:
#   0x00 Starfield.esm
#   0x01 FO4Port.esm
#   0x02 FO4SFCoreValues.esm
#   0x03 FO4ActorRaider.esm
#   0x04 FO4SF_R11P5Weapons.esm (local)
M_SF = 0x00
M_PORT = 0x01
M_CV = 0x02
M_RAIDER = 0x03
M_LOCAL = 0x04

PORT_V111_CELL = (M_PORT << 24) | 0x0011F3          # FO4Port_Vault111Cryo (block=5, subblock=9)
PORT_V111_BLOCK = 5
PORT_V111_SUBBLOCK = 9
PORT_ARMORY_CAGE_DOOR_LOCAL = 0x001539              # FO4Port_SwitchDoorExSmLatch01 (runtime GetFormFromFile ONLY!)

# Pinned FO4SFCoreValues.esm FormID contract (Step 4 Part A & Part B):
CV_AMMO_10MM = (M_CV << 24) | 0x000898              # FO4_Ammo10mm ("10mm Round")
CV_WEAP_10MM = (M_CV << 24) | 0x000899              # FO4_10mmPistol ("10mm Pistol")
CV_WEAP_BATON = (M_CV << 24) | 0x00089A             # FO4_Baton ("Baton")
CV_AMMO_FUSION_CELL = (M_CV << 24) | 0x00089B       # FO4_AmmoFusionCell ("Fusion Cell")
CV_AMMO_COMP_FUSION_CELL = (M_CV << 24) | 0x00089C  # FO4_CompanionAmmoFusionCell (non-playable)
CV_WEAP_LASER_MUSKET = (M_CV << 24) | 0x00089D      # FO4_LaserMusket ("Laser Musket")
CV_WEAP_COMP_PRESTON_LM = (M_CV << 24) | 0x00089E   # FO4_CompPrestonLaserMusket (non-playable)
CV_AMMO_5MM = (M_CV << 24) | 0x00089F               # FO4_Ammo5mm ("5mm Round")
CV_WEAP_MINIGUN = (M_CV << 24) | 0x0008A0           # FO4_Minigun ("Minigun")

RAIDER_CALM_NPC = (M_RAIDER << 24) | 0xF04801       # FO4_LvlRaider_Calm

# Starfield donor WEAP & AMMO FormIDs (checked for 0 inventory leak; animations/audio are stand-ins):
SF_DONOR_RESCUE_AXE = 0x0004F760                    # RescueAxe (1H hafted bludgeon/chop donor for Baton)
SF_DONOR_XM2311 = 0x0024561C                        # XM2311 (10mm Pistol donor)
SF_DONOR_ORION = 0x002773C8                         # Orion (Laser Musket donor)
SF_DONOR_MICROGUN = 0x000546CD                      # Microgun (Minigun donor)
SF_DONOR_AMMO45 = 0x002B5598                        # Ammo45Caliber
SF_DONOR_AMMO_LASER = 0x0000E8EC                    # AmmoLaser
SF_DONOR_AMMO_777 = 0x0004AD3E                      # Ammo777mm

SF_AV_HEALTH = 0x000002D4                           # Health
SF_AV_HIDE_SUIT = 0x000B120E                        # ActorShouldForceHideSpacesuit_AV
SF_ACTI_MODL = b"Effects\\sfbgs006\\SFBGS006_SBShipDecoratorMarker.nif\x00"

# Probe-local FormIDs in FO4SF_R11P5Weapons.esm:
FID_ACTI_TRIGGER = (M_LOCAL << 24) | 0x000800
FID_REF_TRIGGER = (M_LOCAL << 24) | 0x000810
FID_ACHR_DUMMY = (M_LOCAL << 24) | 0x000811
FID_REF_BATON_CRYO = (M_LOCAL << 24) | 0x000812     # FO4 0x0019891C Vault111Cryo table Baton
FID_REF_BATON_CRATE = (M_LOCAL << 24) | 0x000813    # FO4 0x000AE470 Vault111Cryo crate Baton
FID_REF_LASER_MUSKET = (M_LOCAL << 24) | 0x000814   # Range Laser Musket
FID_REF_FUSION_CELL_1 = (M_LOCAL << 24) | 0x000815  # Range Fusion Cell box #1 (x24)
FID_REF_FUSION_CELL_2 = (M_LOCAL << 24) | 0x000816  # Range Fusion Cell box #2 (x24)
FID_REF_FUSION_CELL_3 = (M_LOCAL << 24) | 0x000817  # Range Fusion Cell box #3 (x24)
FID_REF_MINIGUN = (M_LOCAL << 24) | 0x000818        # Range Minigun
FID_REF_AMMO_5MM = (M_LOCAL << 24) | 0x000819       # Range 5mm Round box (x500)
QUST_P5_LOCAL_ID = 0x000820
FID_QUST_P5 = (M_LOCAL << 24) | QUST_P5_LOCAL_ID
DEFAULT_QUEST_LOAD_PREFIX = 0x11

# QUST DNAM flags: StartGameEnabled (0x1) | AllowRepeatedStages (0x8) = 0x00000009 (fixes P4 Note 2!)
QUST_START_GAME_ENABLED_FLAGS = 0x00000009
REFR_PERSISTENT = 0x00000400
REFR_INITIALLY_DISABLED = 0x00000800
REFR_DONT_HAVOK_SETTLE = 0x20000000

# Verified Fallout4.esm -> FO4Port_Vault111Cryo (/ 70.0 m) placements & stances:
#   0x0019891C: FO4 (-165.56, 2000.52, -70.86) -> SF (-2.3651, 28.5789, -1.0123), rests on FO4Port_Vault_Table_01 (-1.829 floor)
#   0x000AE470: FO4 (-1272.29, 952.57, -85.74) -> SF (-18.1756, 13.6082, -1.2248), rests on FO4Port_Vault_Crate_03 (-1.829 floor)
#   0x0005F762: FO4 (-3992.36, 2100.42, 89.95) -> SF (-57.0338, 30.0060, 1.2850), shelf in FO4SFNewGame.esm:0x000820
BATON_CRYO_POS = (-2.3651, 28.5789, -1.0123)
BATON_CRYO_ROT = (-math.pi / 2.0, -0.0028, 4.4740)  # rx=-pi/2 lays +Z melee shaft flat on FO4Port_Vault_Table_01
BATON_CRYO_STANCE = (-2.37, 27.55, -1.83)
BATON_CRYO_STANCE_YAW = 0.0

BATON_CRATE_POS = (-18.1756, 13.6082, -1.2248)
BATON_CRATE_ROT = (-math.pi / 2.0, 0.0029, 5.3340)  # rx=-pi/2 lays +Z melee shaft flat on FO4Port_Vault_Crate_03
BATON_CRATE_STANCE = (-17.55, 13.65, -1.83)
BATON_CRATE_STANCE_YAW = 270.0

OVERSEER_DESK_STANCE = (-55.40, 29.80, 0.15)        # facing armory cage shelf 0x0A000820/0821
OVERSEER_DESK_YAW_DEG = 278.0
OVERSEER_TRIGGER_POS = (-55.40, 31.10, 1.35)
OVERSEER_TARGET_STANCE = (-53.20, 29.80, 0.15)      # open Overseer office range (4.4 m sightline east to TargetDummy)
OVERSEER_DUMMY_POS = (-48.80, 30.00, 0.15)

# Unobstructed open-floor placements south of OVERSEER_TARGET_STANCE (2.2+ m clear of north wall y=31.086):
RANGE_LASER_MUSKET_POS = (-53.30, 28.80, 0.12)
RANGE_FUSION_CELL_POSITIONS = (
    (-53.00, 28.60, 0.08),
    (-52.75, 28.60, 0.08),
    (-52.50, 28.60, 0.08),
)
RANGE_MINIGUN_POS = (-52.10, 28.85, 0.18)
RANGE_AMMO_5MM_POS = (-51.60, 28.70, 0.10)

SANCTUARY_BENCH_MERGED = (-2329.25, -1420.19, 112.09)
EXT_HOP_MID_MERGED = (-2400.00, -1413.00, 120.00)
V111_HILLTOP_MERGED = (-2467.78, -1406.93, 127.85)

WEAPON_NIF_RELS = {
    "10mm": "meshes/fo4sf/weapons/10mm/fo4_10mmpistol.nif",
    "baton": "meshes/fo4sf/weapons/baton/fo4_baton.nif",
    "lasermusket": "meshes/fo4sf/weapons/lasermusket/fo4_lasermusket.nif",
    "minigun": "meshes/fo4sf/weapons/minigun/fo4_minigun.nif",
}
AMMO_NIF_RELS = {
    "10mm": "meshes/fo4core/ammo/10mm/10mmammo.nif",
    "fusioncell": "meshes/fo4core/ammo/laserammo/microfusioncell.nif",
    "5mm": "meshes/fo4core/ammo/5mm/5mmammo.nif",
}

FORBIDDEN_SF_WEAPON_TOKENS = (
    "weapons/m1919",
    "weapons\\m1919",
    "weapons/rescueaxe",
    "weapons\\rescueaxe",
    "weapons/orion",
    "weapons\\orion",
    "weapons/microgun",
    "weapons\\microgun",
    "bullpupdummyreceiver",
)

STANDIN_DISCLOSURE = (
    "All four Fallout 4 weapon NIFs preserve named FO4 moving-part NiNode subtrees for Claude's "
    "future .rig/.af animation route. Animations and Wwise SNDR audio remain Starfield donor "
    "stand-ins: RescueAxe (0x04F760, Baton), XM2311 (0x24561C, 10mm Pistol), Orion (0x2773C8, "
    "Laser Musket), and Microgun (0x0546CD, Minigun)."
)

P3_FORBIDDEN_RE = re.compile(r"[mnvMNV]")
STRIPPED_MOD_EDID_RE = re.compile(r"\bFO4SF_[A-Za-z0-9_]+", re.I)
MAX_EXTERIOR_HOP_AXIS_M = 200.0
QUST_VMAD_TAIL = b"\x03\x00\x00\x00\x00\x00\x00"


class ProbeP5Error(ValueError):
    """Raised when P5 staging, verification, P3/hop checks, or reversible install/uninstall guards fail."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_starfield_not_running() -> None:
    pids = System.pids(GAME_EXE)
    if pids:
        raise ProbeP5Error(f"refused while {GAME_EXE} is running (pids={pids})")


def check_free_space_gb(target_path: Path, min_free_gb: float = DEFAULT_MIN_FREE_GB) -> float:
    probe = target_path
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    usage = shutil.disk_usage(probe)
    free_gb = round(usage.free / (1024 ** 3), 2)
    if free_gb < min_free_gb:
        raise ProbeP5Error(f"free disk space {free_gb:.2f} GiB < {min_free_gb:.2f} GiB floor on {probe}")
    return free_gb


def check_out_dir_safe(out_dir: Path, fo4_data: Optional[Path] = None, sf_dir: Optional[Path] = None) -> None:
    resolved = out_dir.resolve()
    norm = os.path.normcase(str(resolved))
    if "candidate-" in norm:
        raise ProbeP5Error(f"refusing to write probe into any candidate-* directory: {out_dir}")
    repo_norm = os.path.normcase(str(REPO.resolve()))
    if norm == repo_norm or norm.startswith(repo_norm + os.sep):
        raise ProbeP5Error(f"refusing to write probe inside Git repository: {out_dir}")
    for label, gdir in (("fo4_data", fo4_data), ("starfield_dir", sf_dir)):
        if gdir is not None:
            gnorm = os.path.normcase(str(gdir.resolve()))
            if norm == gnorm or norm.startswith(gnorm + os.sep):
                raise ProbeP5Error(f"refusing to write probe inside {label}: {out_dir}")
    if out_dir.is_file():
        raise ProbeP5Error(f"out_dir is an existing file: {out_dir}")


# ---------------------------------------------------------------------------
# Pure-Python ESM, VMAD v6 & BA2 helpers (shared via probe_common)
# ---------------------------------------------------------------------------
VMAD_T_OBJECT = pc.VMAD_T_OBJECT
VMAD_T_STRING = pc.VMAD_T_STRING
VMAD_T_INT = pc.VMAD_T_INT
VMAD_T_FLOAT = pc.VMAD_T_FLOAT
VMAD_T_BOOL = pc.VMAD_T_BOOL
_vmad_wstr = pc.vmad_wstr
_encode_vmad_v6 = pc.encode_vmad_v6
_decode_vmad_v6_prop_names = pc.decode_vmad_v6_prop_names
_pack_subs = pc.pack_subs
_rec_bytes = pc.rec_bytes
_grup_bytes = pc.grup_bytes
_count_records_and_grups = pc.count_records_and_grups
_extract_port_cell_record_bytes = pc.extract_cell_record_bytes
_refr_item = pc.refr_item


def build_p5_weapons_esm(port_esm: Optional[Path] = None) -> bytes:
    """Build FO4SF_R11P5Weapons.esm with FO4 Vault 111 Batons, range Laser Musket/Minigun/ammo, target, and StartGameEnabled QUST."""
    acti_trigger = _rec_bytes(
        b"ACTI",
        FID_ACTI_TRIGGER,
        [
            (b"EDID", b"FO4SF_P5_TargetTriggerActi\x00"),
            (b"OBND", struct.pack("<6f", -0.35, -0.35, -0.35, 0.35, 0.35, 0.35)),
            (b"ODTY", struct.pack("<I", 0)),
            (b"FULL", b"P5 Weapons Target\x00"),
            (b"MODL", SF_ACTI_MODL),
            (b"PNAM", struct.pack("<I", 0x0033CC4C)),
            (b"ATTX", b"Spawn / Reset\x00"),
            (b"FNAM", struct.pack("<H", 0)),
            (b"JNAM", struct.pack("<H", 0x0168)),
        ],
    )

    ref_trigger = _refr_item(
        FID_REF_TRIGGER,
        "FO4SF_P5_TargetTriggerRef",
        FID_ACTI_TRIGGER,
        OVERSEER_TRIGGER_POS,
        flags=REFR_PERSISTENT,
    )

    # TargetDummy starts Persistent | InitiallyDisabled (0xC00), stripped unarmed on spawn.
    achr_dummy = _rec_bytes(
        b"ACHR",
        FID_ACHR_DUMMY,
        [
            (b"EDID", b"FO4SF_P5_TargetDummyRef\x00"),
            (b"NAME", struct.pack("<I", RAIDER_CALM_NPC)),
            (
                b"DATA",
                struct.pack(
                    "<6f",
                    OVERSEER_DUMMY_POS[0],
                    OVERSEER_DUMMY_POS[1],
                    OVERSEER_DUMMY_POS[2],
                    0.0,
                    0.0,
                    math.radians(270.0),
                ),
            ),
        ],
        flags=REFR_PERSISTENT | REFR_INITIALLY_DISABLED,
    )

    # Exact FO4 Vault111Cryo Baton placements + range Laser Musket (x1 + 3x24 Fusion Cell) & Minigun (x1 + 1x500 5mm):
    ref_baton_cryo = _refr_item(
        FID_REF_BATON_CRYO,
        "FO4SF_P5_BatonCryoRef",
        CV_WEAP_BATON,
        BATON_CRYO_POS,
        rot=BATON_CRYO_ROT,
    )
    ref_baton_crate = _refr_item(
        FID_REF_BATON_CRATE,
        "FO4SF_P5_BatonCrateRef",
        CV_WEAP_BATON,
        BATON_CRATE_POS,
        rot=BATON_CRATE_ROT,
    )
    ref_laser_musket = _refr_item(
        FID_REF_LASER_MUSKET,
        "FO4SF_P5_LaserMusketRef",
        CV_WEAP_LASER_MUSKET,
        RANGE_LASER_MUSKET_POS,
        rot=(0.0, 0.0, math.pi / 2.0),
    )
    ref_cell_boxes = b"".join(
        _refr_item(
            fid,
            f"FO4SF_P5_FusionCellBox{idx}Ref",
            CV_AMMO_FUSION_CELL,
            pos,
            count=24,
        )
        for idx, (fid, pos) in enumerate(
            zip((FID_REF_FUSION_CELL_1, FID_REF_FUSION_CELL_2, FID_REF_FUSION_CELL_3), RANGE_FUSION_CELL_POSITIONS),
            start=1,
        )
    )
    ref_minigun = _refr_item(
        FID_REF_MINIGUN,
        "FO4SF_P5_MinigunRef",
        CV_WEAP_MINIGUN,
        RANGE_MINIGUN_POS,
        rot=(0.0, 0.0, math.pi / 2.0),
    )
    ref_ammo_5mm = _refr_item(
        FID_REF_AMMO_5MM,
        "FO4SF_P5_Ammo5mmBoxRef",
        CV_AMMO_5MM,
        RANGE_AMMO_5MM_POS,
        count=500,
    )

    cell_rec = _extract_port_cell_record_bytes(port_esm, PORT_V111_CELL)
    cell_lbl = struct.pack("<I", PORT_V111_CELL)
    pers_payload = (
        ref_trigger
        + achr_dummy
        + ref_baton_cryo
        + ref_baton_crate
        + ref_laser_musket
        + ref_cell_boxes
        + ref_minigun
        + ref_ammo_5mm
    )
    pers_grup = _grup_bytes(cell_lbl, 8, pers_payload)
    cell_children = _grup_bytes(cell_lbl, 6, pers_grup)
    subblock_grup = _grup_bytes(struct.pack("<i", PORT_V111_SUBBLOCK), 3, cell_rec + cell_children)
    block_grup = _grup_bytes(struct.pack("<i", PORT_V111_BLOCK), 2, subblock_grup)

    # Zero non-persistent cross-plugin VMAD ObjectReference properties: ArmoryCageDoor uses int+string GetFormFromFile!
    props = [
        {"name": "TargetTrigger", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": FID_REF_TRIGGER, "alias": -1}},
        {"name": "ArmoryCageDoorLocalId", "type": VMAD_T_INT, "status": 1, "value": PORT_ARMORY_CAGE_DOOR_LOCAL},
        {"name": "PortPlugin", "type": VMAD_T_STRING, "status": 1, "value": "FO4Port.esm"},
        {"name": "TargetDummy", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": FID_ACHR_DUMMY, "alias": -1}},
        {"name": "BatonWeap", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": CV_WEAP_BATON, "alias": -1}},
        {"name": "Pistol10mm", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": CV_WEAP_10MM, "alias": -1}},
        {"name": "LaserMusketWeap", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": CV_WEAP_LASER_MUSKET, "alias": -1}},
        {"name": "MinigunWeap", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": CV_WEAP_MINIGUN, "alias": -1}},
        {"name": "Ammo10mm", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": CV_AMMO_10MM, "alias": -1}},
        {"name": "AmmoFusionCell", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": CV_AMMO_FUSION_CELL, "alias": -1}},
        {"name": "Ammo5mm", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": CV_AMMO_5MM, "alias": -1}},
        {"name": "DonorRescueAxe", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": SF_DONOR_RESCUE_AXE, "alias": -1}},
        {"name": "DonorXm2311", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": SF_DONOR_XM2311, "alias": -1}},
        {"name": "DonorOrion", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": SF_DONOR_ORION, "alias": -1}},
        {"name": "DonorMicrogun", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": SF_DONOR_MICROGUN, "alias": -1}},
        {"name": "DonorAmmo45", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": SF_DONOR_AMMO45, "alias": -1}},
        {"name": "DonorAmmoLaser", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": SF_DONOR_AMMO_LASER, "alias": -1}},
        {"name": "DonorAmmo777", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": SF_DONOR_AMMO_777, "alias": -1}},
        {"name": "HealthAV", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": SF_AV_HEALTH, "alias": -1}},
        {"name": "HideSuitAV", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": SF_AV_HIDE_SUIT, "alias": -1}},
        {"name": "EnableLog", "type": VMAD_T_BOOL, "status": 1, "value": True},
        {"name": "LogName", "type": VMAD_T_STRING, "status": 1, "value": "fo4sf_r11p5"},
    ]
    q_vmad = _encode_vmad_v6([{"name": "FO4SF_R11P5Quest", "status": 0, "properties": props}]) + QUST_VMAD_TAIL
    quest_rec = _rec_bytes(
        b"QUST",
        FID_QUST_P5,
        [
            (b"EDID", b"FO4SF_R11P5Quest\x00"),
            (b"VMAD", q_vmad),
            (b"FULL", b"R11 P5 Weapons Probe\x00"),
            (b"DNAM", struct.pack("<III", QUST_START_GAME_ENABLED_FLAGS, 50, 0)),
            (b"QTYP", struct.pack("<I", 0x00047600)),
            (b"INDX", struct.pack("<I", 10)),
            (b"QSDT", b"\x00"),
            (b"INDX", struct.pack("<I", 20)),
            (b"QSDT", b"\x00"),
            (b"INDX", struct.pack("<I", 30)),
            (b"QSDT", b"\x00"),
        ],
        flags=0,
        version=581,
    )

    body = (
        _grup_bytes(b"ACTI", 0, acti_trigger)
        + _grup_bytes(b"CELL", 0, block_grup)
        + _grup_bytes(b"QUST", 0, quest_rec)
    )
    masters = ("Starfield.esm", "FO4Port.esm", "FO4SFCoreValues.esm", "FO4ActorRaider.esm")
    next_obj_id = 0x000821
    n_records_grups = _count_records_and_grups(body)
    tes4_subs: List[Tuple[bytes, bytes]] = [(b"HEDR", struct.pack("<fII", 0.96, n_records_grups, next_obj_id))]
    for m in masters:
        tes4_subs.append((b"MAST", m.encode("ascii") + b"\x00"))
        tes4_subs.append((b"DATA", struct.pack("<Q", 0)))
    tes4 = _rec_bytes(b"TES4", 0, tes4_subs, flags=1, version=576)
    return tes4 + body


# ---------------------------------------------------------------------------
# BS-173 Weapon/Ammo NIF Hierarchy & Asset Tree Verification
# ---------------------------------------------------------------------------
def _parse_ninode_children(block: bytes) -> Tuple[int, List[int]]:
    """Extract (name_idx, child_block_indices) from a BS-173 NiNode block."""
    # NiObjectNET: name(i32), num_extra(u32), extra[num_extra](i32), controller(i32)
    if len(block) < 12:
        return -1, []
    name_idx, num_extra = struct.unpack_from("<iI", block, 0)
    pos = 8 + 4 * num_extra + 4  # + controller(i32)
    # NiAVObject: flags(u32), translation(3f), rotation(9f), scale(f), collision(i32) -> 4+12+36+4+4 = 60B
    pos += 60
    if pos + 4 > len(block):
        return name_idx, []
    num_children, = struct.unpack_from("<I", block, pos)
    pos += 4
    if pos + 4 * num_children > len(block):
        return name_idx, []
    children = [c for c in struct.unpack_from(f"<{num_children}i", block, pos) if c >= 0]
    return name_idx, children


def _as_str(v: object) -> str:
    return v.decode("utf-8", "replace") if isinstance(v, (bytes, bytearray)) else str(v)


def inspect_nif_hierarchy(nif_bytes: bytes) -> dict:
    """Inspect BS-173 NIF block graph: returns node->BSGeometry mapping, mesh paths, and material paths."""
    nf = nifmod.parse(nif_bytes)
    strings = [_as_str(s) for s in nf.strings]
    block_types = [_as_str(nf.block_types[ti]) for ti in nf.block_type_index]

    def _str_at(idx: int) -> str:
        return strings[idx] if 0 <= idx < len(strings) else ""

    node_children: Dict[int, List[int]] = {}
    node_names: Dict[int, str] = {}
    geom_names: Dict[int, str] = {}
    mesh_paths: List[str] = []
    mat_paths: List[str] = []

    for idx, (btype, bdata) in enumerate(zip(block_types, nf.blocks)):
        if btype == "NiNode":
            n_idx, ch = _parse_ninode_children(bdata)
            node_names[idx] = _str_at(n_idx)
            node_children[idx] = ch
        elif btype == "BSGeometry":
            n_idx, = struct.unpack_from("<i", bdata, 0)
            geom_names[idx] = _str_at(n_idx)
        elif btype == "BSLightingShaderProperty":
            n_idx, = struct.unpack_from("<i", bdata, 0)
            mname = _str_at(n_idx)
            if mname:
                mat_paths.append(mname.replace("\\", "/").lstrip("/"))

    # Collect external .mesh references from BSGeometry blocks (UTF-8 / ASCII hex\hex strings inside block or string table)
    mesh_re = re.compile(rb"([0-9a-fA-F]{20}[\\/][0-9a-fA-F]{20})")
    for idx, (btype, bdata) in enumerate(zip(block_types, nf.blocks)):
        if btype == "BSGeometry":
            for m in mesh_re.findall(bdata):
                rel = m.decode("ascii").replace("\\", "/").lower()
                if rel not in mesh_paths:
                    mesh_paths.append(rel)

    node_to_shapes: Dict[str, List[str]] = {}
    for nidx, ch in node_children.items():
        shapes = [geom_names[c] for c in ch if c in geom_names]
        if shapes:
            node_to_shapes[node_names.get(nidx, f"node_{nidx}")] = shapes

    return {
        "root_name": node_names.get(0, ""),
        "named_nodes": sorted(n for n in node_names.values() if n),
        "node_to_shapes": node_to_shapes,
        "shape_count": len(geom_names),
        "mesh_paths": mesh_paths,
        "material_paths": sorted(set(mat_paths)),
    }


def verify_p5_assets_tree(assets_dir: Path) -> dict:
    """Verify all 4 weapon NIFs + 3 ammo NIFs and their referenced .mesh/.mat/.dds files exist cleanly."""
    if not assets_dir.is_dir():
        raise ProbeP5Error(f"assets directory missing: {assets_dir}")

    summary: Dict[str, dict] = {"weapons": {}, "ammo": {}}
    seen_dds: set[str] = set()

    def _check_one(bucket: str, key: str, rel_nif: str) -> None:
        np = assets_dir / Path(*rel_nif.split("/"))
        if not np.is_file():
            raise ProbeP5Error(f"missing {bucket} NIF ({key}): {rel_nif}")
        raw = np.read_bytes()
        low_raw = raw.lower()
        for bad_tok in FORBIDDEN_SF_WEAPON_TOKENS:
            if bad_tok.encode("ascii") in low_raw:
                raise ProbeP5Error(f"forbidden Starfield donor token {bad_tok!r} in {rel_nif}")
        info = inspect_nif_hierarchy(raw)
        if info["shape_count"] < 1:
            raise ProbeP5Error(f"{rel_nif} has 0 BSGeometry shapes")
        for mp in info["mesh_paths"]:
            mfile = assets_dir / "geometries" / Path(*mp.split("/"))
            if not mfile.with_suffix(".mesh").is_file():
                raise ProbeP5Error(f"{rel_nif} references missing external mesh: geometries/{mp}.mesh")
        for mat_rel in info["material_paths"]:
            mat_norm = mat_rel if mat_rel.lower().startswith("materials/") else f"materials/{mat_rel}"
            mpath = assets_dir / Path(*mat_norm.split("/"))
            if not mpath.is_file():
                raise ProbeP5Error(f"{rel_nif} references missing material: {mat_norm}")
            try:
                mjson = json.loads(mpath.read_text(encoding="utf-8"))
            except ValueError as exc:
                raise ProbeP5Error(f"invalid JSON material {mat_norm}: {exc}") from exc
            # Collect any textures listed in material JSON (supports both list/dict Starfield .mat schemas)
            tex_refs: List[str] = []

            def _walk_tex(obj: object) -> None:
                if isinstance(obj, str):
                    low = obj.replace("\\", "/").lstrip("/").lower()
                    if low.endswith(".dds"):
                        if low.startswith("data/"):
                            low = low[5:]
                        tex_refs.append(low if low.startswith("textures/") else f"textures/{low}")
                elif isinstance(obj, dict):
                    for v in obj.values():
                        _walk_tex(v)
                elif isinstance(obj, list):
                    for v in obj:
                        _walk_tex(v)

            _walk_tex(mjson)
            for tr in tex_refs:
                tp = assets_dir / Path(*tr.split("/"))
                if not tp.is_file():
                    raise ProbeP5Error(f"{mat_norm} references missing texture: {tr}")
                seen_dds.add(tr)
        summary[bucket][key] = info

    for k, rel in WEAPON_NIF_RELS.items():
        _check_one("weapons", k, rel)
    for k, rel in AMMO_NIF_RELS.items():
        _check_one("ammo", k, rel)

    summary["verified_dds_count"] = len(seen_dds)
    return summary


# ---------------------------------------------------------------------------
# BA2 Packing & Bethesda bs_crc32 Verification
# ---------------------------------------------------------------------------
def bs_crc32(data: bytes) -> int:
    """Bethesda BSResource::Archive2 CRC32 (poly=0xEDB88320, init=0x00000000, final_xor=0x00000000)."""
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc >> 1) ^ 0xEDB88320) if (crc & 1) else (crc >> 1)
    return crc & 0xFFFFFFFF


def _ba2_entry_keys(rel_name: str) -> Tuple[int, bytes, int]:
    norm = rel_name.replace("/", "\\").lstrip("\\")
    stem_b = Path(norm).stem.lower().encode("ascii")
    ext_b = Path(norm).suffix.lstrip(".").lower().encode("ascii")[:4].ljust(4, b"\x00")
    dir_b = os.path.dirname(norm).replace("/", "\\").lower().encode("ascii")
    return bs_crc32(stem_b), ext_b, bs_crc32(dir_b)


def verify_ba2_entry_hashes(ba2_path: Path, require_uncompressed_gnrl: bool = True) -> int:
    """Validate raw binary GNRL (36B) or DX10 (24B+chunks) entry table hashes against Bethesda bs_crc32."""
    raw = ba2_path.read_bytes()
    if len(raw) < 24:
        raise ProbeP5Error(f"{ba2_path.name}: truncated BTDX header")
    magic, version, kind, count, name_off = struct.unpack_from("<4sI4sIQ", raw, 0)
    extra = {1: 0, 2: 8, 3: 12, 7: 8, 8: 12}.get(version)
    if magic != b"BTDX" or kind not in (b"GNRL", b"DX10") or extra is None:
        raise ProbeP5Error(f"{ba2_path.name}: unsupported BTDX header ({magic!r}, v={version}, kind={kind!r})")

    npos = name_off
    names: List[str] = []
    for _ in range(count):
        if npos + 2 > len(raw):
            raise ProbeP5Error(f"{ba2_path.name}: truncated name table")
        nlen, = struct.unpack_from("<H", raw, npos)
        npos += 2
        if npos + nlen > len(raw):
            raise ProbeP5Error(f"{ba2_path.name}: name entry overflows file")
        names.append(raw[npos : npos + nlen].decode("utf-8"))
        npos += nlen

    epos = 24 + extra
    for idx, rel_name in enumerate(names):
        want_h, want_ext, want_d = _ba2_entry_keys(rel_name)
        if kind == b"GNRL":
            if epos + 36 > name_off:
                raise ProbeP5Error(f"{ba2_path.name}: GNRL entry {idx} overflows table")
            got_h, got_ext, got_d, _fl, _off, pk_len, _unpk, _align = struct.unpack_from("<I4sIIQIII", raw, epos)
            epos += 36
            if require_uncompressed_gnrl and pk_len != 0:
                raise ProbeP5Error(f"{ba2_path.name}: GNRL entry {rel_name!r} must be stored uncompressed (pk_len={pk_len})")
        else:
            if epos + 24 > name_off:
                raise ProbeP5Error(f"{ba2_path.name}: DX10 entry {idx} overflows table")
            got_h, got_ext, got_d, _unk, n_chunks, chunk_hdr_sz = struct.unpack_from("<I4sIBBH", raw, epos)
            epos += 24 + n_chunks * chunk_hdr_sz
            if epos > name_off:
                raise ProbeP5Error(f"{ba2_path.name}: DX10 chunks for {idx} overflow table")
        if (got_h, got_ext, got_d) != (want_h, want_ext, want_d):
            raise ProbeP5Error(
                f"{ba2_path.name}: entry[{idx}] {rel_name!r} hash mismatch "
                f"got=(0x{got_h:08X}, {got_ext!r}, 0x{got_d:08X}) "
                f"want=(0x{want_h:08X}, {want_ext!r}, 0x{want_d:08X})"
            )
    return count


def _pack_gnrl_ba2_v2_python(ordered: Sequence[Tuple[str, bytes]], out_path: Path) -> None:
    cur = 32 + 36 * len(ordered)
    entries = []
    payloads = []
    for rel_name, raw in ordered:
        name_h, ext_b, dir_h = _ba2_entry_keys(rel_name)
        entries.append((name_h, ext_b, dir_h, 0x00100100, cur, 0, len(raw), BA2_ALIGN))
        payloads.append(raw)
        cur += len(raw)
    name_off = cur
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as fh:
        fh.write(struct.pack("<4sI4sIQII", b"BTDX", 2, b"GNRL", len(ordered), name_off, 1, 0))
        for e in entries:
            fh.write(struct.pack("<I4sIIQIII", *e))
        for p in payloads:
            fh.write(p)
        for rel_name, _ in ordered:
            nb = rel_name.replace("/", "\\").lstrip("\\").encode("utf-8")
            fh.write(struct.pack("<H", len(nb)) + nb)


def pack_gnrl_ba2_v2(
    files: Sequence[Tuple[str, bytes]],
    out_path: Path,
    starfield_dir: Optional[Path] = None,
) -> dict:
    if not files:
        raise ProbeP5Error("cannot pack empty GNRL BA2 archive")
    ordered = sorted(files, key=lambda kv: kv[0].replace("/", "\\").lower())
    archive2 = starfield_dir / "Tools" / "Archive2" / "Archive2.exe" if starfield_dir is not None else None
    used_archive2 = False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if archive2 is not None and archive2.is_file():
        with tempfile.TemporaryDirectory(prefix=".p5-gnrl-ba2-", dir=str(out_path.parent)) as tdir:
            stage_root = Path(tdir) / "root"
            top_folders: List[str] = []
            for rel_name, raw in ordered:
                norm = rel_name.replace("/", "\\").lstrip("\\")
                top = norm.split("\\", 1)[0]
                if top not in top_folders:
                    top_folders.append(top)
                dst = stage_root / Path(*norm.split("\\"))
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(raw)
            fresh = Path(tdir) / out_path.name
            r = subprocess.run(
                [
                    str(archive2),
                    ",".join(top_folders),
                    f"-create={fresh}",
                    f"-root={stage_root}",
                    "-format=General",
                    "-compression=None",
                ],
                cwd=str(stage_root),
                capture_output=True,
                text=True,
                check=False,
            )
            if r.returncode == 0 and fresh.is_file() and fresh.read_bytes()[:4] == b"BTDX":
                os.replace(fresh, out_path)
                used_archive2 = True
    if not used_archive2:
        _pack_gnrl_ba2_v2_python(ordered, out_path)

    verify_ba2_entry_hashes(out_path, require_uncompressed_gnrl=True)
    checked = Ba2(str(out_path))
    if len(checked.entries) != len(ordered):
        raise ProbeP5Error(f"{out_path.name}: entry count mismatch")
    for rel_name, raw in ordered:
        if checked.read(rel_name) != raw:
            raise ProbeP5Error(f"{out_path.name}: round-trip payload mismatch for {rel_name}")
    return {
        "file": out_path.name,
        "entries": len(ordered),
        "used_archive2": used_archive2,
        "size_bytes": out_path.stat().st_size,
        "sha256": sha256_file(out_path),
    }


def _read_dx10_dds_header(data: bytes) -> dict:
    if len(data) < 148 or data[:4] != b"DDS " or data[84:88] != b"DX10":
        raise ProbeP5Error("DX10 DDS header required for Starfield DX10 BA2")
    height, width = struct.unpack_from("<II", data, 12)
    mips, = struct.unpack_from("<I", data, 28)
    dxgi, = struct.unpack_from("<I", data, 128)
    return {"width": width, "height": height, "mips": max(mips, 1), "dxgi": dxgi, "data_offset": 148}


def _pack_dx10_ba2_v2_python(dds_files: Sequence[Tuple[str, bytes]], out_path: Path) -> None:
    ordered = sorted(dds_files, key=lambda kv: kv[0].replace("/", "\\").lower())
    cur = 32 + 48 * len(ordered)
    entry_blobs = []
    payloads = []
    for rel_name, raw in ordered:
        hdr = _read_dx10_dds_header(raw)
        pix = raw[hdr["data_offset"] :]
        packed = zlib.compress(pix, level=6)
        if len(packed) < len(pix):
            use_bytes = packed
            pk_len = len(packed)
        else:
            use_bytes = pix
            pk_len = 0
        name_h, _ext_b, dir_h = _ba2_entry_keys(rel_name)
        mips = hdr["mips"]
        e_hdr = struct.pack(
            "<I4sIBBHHHBBBB",
            name_h,
            b"dds\x00",
            dir_h,
            0,
            1,
            24,
            hdr["height"],
            hdr["width"],
            mips,
            hdr["dxgi"],
            0,
            8,
        )
        c_hdr = struct.pack("<QIIHHI", cur, pk_len, len(pix), 0, max(0, mips - 1), BA2_ALIGN)
        entry_blobs.append(e_hdr + c_hdr)
        payloads.append(use_bytes)
        cur += len(use_bytes)
    name_off = cur
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as fh:
        fh.write(struct.pack("<4sI4sIQII", b"BTDX", 2, b"DX10", len(ordered), name_off, 1, 0))
        for eb in entry_blobs:
            fh.write(eb)
        for p in payloads:
            fh.write(p)
        for rel_name, _ in ordered:
            nb = rel_name.replace("/", "\\").lstrip("\\").encode("utf-8")
            fh.write(struct.pack("<H", len(nb)) + nb)


def pack_textures_ba2(
    assets_root: Path,
    dds_files: Sequence[Tuple[str, bytes]],
    out_path: Path,
    starfield_dir: Optional[Path] = None,
) -> dict:
    if not dds_files:
        raise ProbeP5Error("cannot pack empty Textures BA2 archive")
    archive2 = starfield_dir / "Tools" / "Archive2" / "Archive2.exe" if starfield_dir is not None else None
    used_archive2 = False
    if archive2 is not None and archive2.is_file() and (assets_root / "textures").is_dir():
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".p5-tex-ba2-", dir=str(out_path.parent)) as tdir:
            fresh = Path(tdir) / out_path.name
            r = subprocess.run(
                [
                    str(archive2),
                    "textures",
                    f"-create={fresh}",
                    f"-root={assets_root}",
                    "-format=DDS",
                    "-compression=Default",
                ],
                cwd=str(assets_root),
                capture_output=True,
                text=True,
                check=False,
            )
            if r.returncode == 0 and fresh.is_file() and fresh.read_bytes()[:4] == b"BTDX":
                os.replace(fresh, out_path)
                used_archive2 = True
    if not used_archive2:
        _pack_dx10_ba2_v2_python(dds_files, out_path)

    verify_ba2_entry_hashes(out_path)
    checked = Ba2(str(out_path))
    if checked.kind != "DX10" or len(checked.entries) != len(dds_files):
        raise ProbeP5Error(f"{out_path.name}: expected DX10 BA2 with {len(dds_files)} entries, got {len(checked.entries)}")
    for rel_name, _ in dds_files:
        if checked.find(rel_name) is None:
            raise ProbeP5Error(f"{out_path.name}: missing packed texture {rel_name}")
    return {
        "file": out_path.name,
        "entries": len(dds_files),
        "used_archive2": used_archive2,
        "size_bytes": out_path.stat().st_size,
        "sha256": sha256_file(out_path),
    }


# ---------------------------------------------------------------------------
# Load-Order Slot Computation & P3-Clean Batch Scripts
# ---------------------------------------------------------------------------
_tes4_flags = pc._tes4_flags


def compute_full_master_load_index(
    data_dir: Path,
    plugins_txt_lines: Sequence[str],
    target_plugin: str = PROBE_PLUGIN,
) -> int:
    return pc.compute_full_master_load_index(data_dir, plugins_txt_lines, target_plugin=target_plugin)


def build_p3_batch_scripts(quest_load_prefix: int = DEFAULT_QUEST_LOAD_PREFIX) -> Dict[str, str]:
    """Return {filename: content} for Probe P5 batch scripts (zero M/N/V in filenames/typed commands, zero FO4SF_ EDIDs)."""
    qhex = f"{((quest_load_prefix & 0xFF) << 24) | QUST_P5_LOCAL_ID:08X}"
    batches = {
        "p5b1.txt": (
            "; R11 P5 interior hop inside Vault 111 to FO4 Baton #1 (0x0019891C) on cryo table (-2.37, 28.58, -1.01)\n"
            f"player.setpos x {BATON_CRYO_STANCE[0]:.2f}\n"
            f"player.setpos y {BATON_CRYO_STANCE[1]:.2f}\n"
            f"player.setpos z {BATON_CRYO_STANCE[2]:.2f}\n"
            f"player.setangle z {BATON_CRYO_STANCE_YAW:.0f}\n"
        ),
        "p5b2.txt": (
            "; R11 P5 interior hop inside Vault 111 to FO4 Baton #2 (0x000AE470) on crate (-18.18, 13.61, -1.22)\n"
            f"player.setpos x {BATON_CRATE_STANCE[0]:.2f}\n"
            f"player.setpos y {BATON_CRATE_STANCE[1]:.2f}\n"
            f"player.setpos z {BATON_CRATE_STANCE[2]:.2f}\n"
            f"player.setangle z {BATON_CRATE_STANCE_YAW:.0f}\n"
        ),
        "p5d.txt": (
            "; R11 P5 interior hop inside Vault 111 to armory cage shelf (10mm Pistol 0x0820 + 48x Ammo 0x0821)\n"
            f"player.setpos x {OVERSEER_DESK_STANCE[0]:.2f}\n"
            f"player.setpos y {OVERSEER_DESK_STANCE[1]:.2f}\n"
            f"player.setpos z {OVERSEER_DESK_STANCE[2]:.2f}\n"
            f"player.setangle z {OVERSEER_DESK_YAW_DEG:.0f}\n"
        ),
        "p5o.txt": (
            "; R11 P5 direct coc into Vault 111 armory cage shelf (10mm Pistol + 48x 10mm Round)\n"
            "coc FO4Port_Vault111Cryo\n"
            f"player.setpos x {OVERSEER_DESK_STANCE[0]:.2f}\n"
            f"player.setpos y {OVERSEER_DESK_STANCE[1]:.2f}\n"
            f"player.setpos z {OVERSEER_DESK_STANCE[2]:.2f}\n"
            f"player.setangle z {OVERSEER_DESK_YAW_DEG:.0f}\n"
        ),
        "p5r.txt": (
            "; R11 P5 stand at range pickup bay facing Laser Musket (+3x24 Cells) and Minigun (+500x 5mm) to south\n"
            f"player.setpos x {OVERSEER_TARGET_STANCE[0]:.2f}\n"
            f"player.setpos y {OVERSEER_TARGET_STANCE[1]:.2f}\n"
            f"player.setpos z {OVERSEER_TARGET_STANCE[2]:.2f}\n"
            "player.setangle z 180\n"
        ),
        "p5t.txt": (
            "; R11 P5 face east on firing line and spawn/reset unarmed 30-HP practice target 4.4 m ahead\n"
            f"player.setpos x {OVERSEER_TARGET_STANCE[0]:.2f}\n"
            f"player.setpos y {OVERSEER_TARGET_STANCE[1]:.2f}\n"
            f"player.setpos z {OVERSEER_TARGET_STANCE[2]:.2f}\n"
            "player.setangle z 90\n"
            f"SetStage {qhex} 20\n"
        ),
        "p5g.txt": (
            "; R11 P5 fallback grant all 4 weapons + ammo (for existing non-NewGame saves)\n"
            f"SetStage {qhex} 10\n"
        ),
        "p5h1.txt": (
            "; R11 P5 exterior mid-hop from Sanctuary (-2329.25, -1420.19) toward Vault 111 hilltop (<75 m/axis)\n"
            f"player.setpos x {EXT_HOP_MID_MERGED[0]:.2f}\n"
            f"player.setpos y {EXT_HOP_MID_MERGED[1]:.2f}\n"
            f"player.setpos z {EXT_HOP_MID_MERGED[2]:.2f}\n"
            "player.setangle z 275\n"
        ),
        "p5e.txt": (
            "; R11 P5 exterior Vault 111 hilltop clearing (<70 m/axis from p5h1) for daylight 1stP/3rdP/ADS stills\n"
            f"player.setpos x {V111_HILLTOP_MERGED[0]:.2f}\n"
            f"player.setpos y {V111_HILLTOP_MERGED[1]:.2f}\n"
            f"player.setpos z {V111_HILLTOP_MERGED[2]:.2f}\n"
            "player.setangle z 90\n"
        ),
        "p5s.txt": (
            "; R11 P5 write full scorecard summary line to r11p5 user log\n"
            f"SetStage {qhex} 30\n"
        ),
        "p5q.txt": (
            "; R11 P5 quick quest stage status query\n"
            f"getstage {qhex}\n"
            f"sqs {qhex}\n"
        ),
    }
    validate_p3_batches_and_hops(batches)
    return batches


def validate_p3_batches_and_hops(batches: Dict[str, str]) -> dict:
    """Enforce P3 (0 M/N/V in filenames & typed commands, 0 stripped FO4SF_ EDIDs in bat) and <200 m/axis exterior hops."""
    bad_names = []
    stripped_edids = []
    typed_commands = []
    for fname, content in sorted(batches.items()):
        stem = Path(fname).stem
        cmd = f"bat {stem}"
        typed_commands.append(cmd)
        if P3_FORBIDDEN_RE.search(fname) or P3_FORBIDDEN_RE.search(cmd):
            bad_names.append((fname, cmd))
        hits = STRIPPED_MOD_EDID_RE.findall(content)
        if hits:
            stripped_edids.append((fname, hits))
    if bad_names:
        raise ProbeP5Error(f"P3 violation (M/N/V in batch filename or typed command): {bad_names}")
    if stripped_edids:
        raise ProbeP5Error(f"P3 violation (stripped FO4SF_ mod EditorID inside batch file): {stripped_edids}")

    hops = [
        ("sanctuary_to_p5h1", SANCTUARY_BENCH_MERGED, EXT_HOP_MID_MERGED),
        ("p5h1_to_p5e_hilltop", EXT_HOP_MID_MERGED, V111_HILLTOP_MERGED),
    ]
    hop_report = []
    for label, a, b in hops:
        dx, dy, dz = abs(b[0] - a[0]), abs(b[1] - a[1]), abs(b[2] - a[2])
        if max(dx, dy, dz) >= MAX_EXTERIOR_HOP_AXIS_M:
            raise ProbeP5Error(
                f"exterior hop {label} exceeds {MAX_EXTERIOR_HOP_AXIS_M} m/axis: dx={dx:.2f}, dy={dy:.2f}, dz={dz:.2f}"
            )
        hop_report.append(
            {
                "hop": label,
                "dx_m": round(dx, 2),
                "dy_m": round(dy, 2),
                "dz_m": round(dz, 2),
                "max_axis_m": round(max(dx, dy, dz), 2),
                "under_200m_per_axis": True,
            }
        )
    return {
        "typed_commands": typed_commands,
        "p3_zero_mnv": True,
        "p3_zero_stripped_fo4sf_edids": True,
        "exterior_hops": hop_report,
    }


def compile_papyrus_scripts(starfield_dir: Path, sources: Sequence[Path], out_dir: Path) -> Dict[str, Path]:
    compiler = starfield_dir / "Tools" / "Papyrus Compiler" / "PapyrusCompiler.exe"
    content_zip = starfield_dir / "Tools" / "ContentResources.zip"
    if not compiler.is_file() or not content_zip.is_file():
        raise ProbeP5Error(f"missing PapyrusCompiler.exe or ContentResources.zip under {starfield_dir / 'Tools'}")
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="p5_papyrus_") as tdir:
        base_src = Path(tdir) / "Source"
        base_src.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(content_zip) as zf:
            for member in zf.namelist():
                parts = member.split("/")
                if len(parts) == 3 and parts[:2] == ["Scripts", "Source"] and (
                    parts[2].lower().endswith(".psc") or parts[2] == "Starfield_Papyrus_Flags.flg"
                ):
                    (base_src / parts[2]).write_bytes(zf.read(member))
        compiled: Dict[str, Path] = {}
        inc_dirs = [str(REPO / "scripts" / "newgame"), str(REPO / "scripts" / "probes"), str(base_src)]
        inc_arg = ";".join(inc_dirs)
        for src in sources:
            r = subprocess.run(
                [
                    str(compiler),
                    src.name,
                    "-f=Starfield_Papyrus_Flags.flg",
                    f"-i={inc_arg}",
                    f"-o={out_dir}",
                ],
                cwd=str(src.parent),
                capture_output=True,
                text=True,
                check=False,
            )
            pex = out_dir / f"{src.stem}.pex"
            if r.returncode != 0 or "Compilation succeeded" not in r.stdout or not pex.is_file():
                raise ProbeP5Error(f"Papyrus compile failed for {src.name}:\n{r.stdout}\n{r.stderr}")
            compiled[src.stem] = pex
        return compiled


def _build_core_and_newgame_esms(
    sf_esm: Path,
    fo4_esm: Path,
    port_esm: Path,
    port_ids: Path,
    terrain_core_esm: Path,
    core_out_dir: Path,
) -> None:
    core_out_dir.mkdir(parents=True, exist_ok=True)
    cv_proj = REPO / "dotnet" / "CoreValues" / "CoreValues.csproj"
    ng_proj = REPO / "dotnet" / "NewGame" / "NewGame.csproj"

    for cmd in (
        [
            "dotnet", "run", "--project", str(cv_proj), "-c", "Release", "--",
            "build", str(sf_esm), str(core_out_dir), "--fo4-10mm", "1", "--fo4-p5-weapons", "1",
        ],
        [
            "dotnet", "run", "--project", str(cv_proj), "-c", "Release", "--",
            "check", str(core_out_dir / "FO4SFCoreValues.esm"), str(sf_esm), "--fo4-10mm", "1", "--fo4-p5-weapons", "1",
        ],
    ):
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if r.returncode != 0:
            raise ProbeP5Error(f"CoreValues failed ({cmd}):\n{r.stdout}\n{r.stderr}")

    with tempfile.TemporaryDirectory(prefix="p5_ng_pts_") as tdir:
        pts_json = Path(tdir) / "points.json"
        for cmd in (
            ["dotnet", "run", "--project", str(ng_proj), "-c", "Release", "--", "points", str(fo4_esm), str(pts_json)],
            [
                "dotnet", "run", "--project", str(ng_proj), "-c", "Release", "--",
                "write", str(sf_esm), str(port_esm), str(port_ids), str(terrain_core_esm), str(pts_json), str(core_out_dir),
                "--fo4-10mm", "1",
            ],
            [
                "dotnet", "run", "--project", str(ng_proj), "-c", "Release", "--",
                "check", str(core_out_dir / "FO4SFNewGame.esm"), str(sf_esm), str(port_esm), str(port_ids), str(terrain_core_esm), str(pts_json),
                "--fo4-10mm", "1",
            ],
        ):
            r = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if r.returncode != 0:
                raise ProbeP5Error(f"NewGame failed ({cmd}):\n{r.stdout}\n{r.stderr}")


def _stage_p5_weapon_assets(fo4_data: Path, sf_data: Path, assets_dir: Path) -> None:
    """Delegate live multi-weapon asset staging to scripts/weapons/stage_r11_weapons.py (Step 4 Part A)."""
    builder = WEAPONS_DIR / "stage_r11_weapons.py"
    if not builder.is_file():
        raise ProbeP5Error(
            f"missing Step 4 Part A weapon stager ({builder}); merge r11p3-s4-weapons or pass prebuilt_assets_dir"
        )
    mod = importlib.import_module("stage_r11_weapons")
    if hasattr(mod, "stage_r11_weapons"):
        mod.stage_r11_weapons(str(fo4_data), str(sf_data), str(assets_dir))
        return
    r = subprocess.run(
        [sys.executable, "-I", str(builder), "stage", "--fo4-data", str(fo4_data), "--sf-data", str(sf_data), "--out", str(assets_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        raise ProbeP5Error(f"stage_r11_weapons.py failed:\n{r.stdout}\n{r.stderr}")


# ---------------------------------------------------------------------------
# Stage, Verify, Install, Uninstall, Status
# ---------------------------------------------------------------------------
def stage_probe_p5(
    out_dir: Path,
    fo4_data: Optional[Path] = None,
    starfield_dir: Optional[Path] = None,
    port_ids: Optional[Path] = None,
    port_esm: Optional[Path] = None,
    terrain_core_esm: Optional[Path] = None,
    prebuilt_core_esms: Optional[Dict[str, bytes]] = None,
    prebuilt_assets_dir: Optional[Path] = None,
    prebuilt_pex: Optional[Dict[str, bytes]] = None,
    min_free_gb: float = DEFAULT_MIN_FREE_GB,
) -> dict:
    """Build and verify the standalone Probe P5 (`r11-p5-weapons`) staging directory."""
    check_starfield_not_running()
    check_out_dir_safe(out_dir, fo4_data=fo4_data, sf_dir=starfield_dir)
    if out_dir.is_dir() and any(out_dir.iterdir()):
        raise ProbeP5Error(f"out_dir is not empty: {out_dir}")
    free_before = check_free_space_gb(out_dir, min_free_gb)

    core_dir = out_dir / "core"
    assets_dir = out_dir / "assets"
    exp_dir = out_dir / "exp"
    bat_dir = out_dir / "bat"
    for d in (core_dir, exp_dir, bat_dir):
        d.mkdir(parents=True, exist_ok=True)

    sf_data = starfield_dir / "Data" if starfield_dir is not None else None
    eff_port_esm = port_esm or (sf_data / "FO4Port.esm" if sf_data is not None else None)
    eff_terrain_esm = terrain_core_esm or (sf_data / "FO4TerrainCore.esm" if sf_data is not None else None)

    # 1. Stage FO4SFCoreValues.esm (--fo4-10mm 1 --fo4-p5-weapons 1) & FO4SFNewGame.esm (--fo4-10mm 1)
    if prebuilt_core_esms is not None:
        for ename in SWAPPED_CORE_ESMS:
            if ename not in prebuilt_core_esms:
                raise ProbeP5Error(f"prebuilt_core_esms missing {ename}")
            (core_dir / ename).write_bytes(prebuilt_core_esms[ename])
    else:
        if fo4_data is None or sf_data is None or port_ids is None or eff_port_esm is None or eff_terrain_esm is None:
            raise ProbeP5Error("fo4_data, starfield_dir, port_ids, FO4Port.esm, and FO4TerrainCore.esm are required")
        _build_core_and_newgame_esms(
            sf_esm=sf_data / "Starfield.esm",
            fo4_esm=fo4_data / "Fallout4.esm",
            port_esm=eff_port_esm,
            port_ids=port_ids,
            terrain_core_esm=eff_terrain_esm,
            core_out_dir=core_dir,
        )

    # 2. Stage hierarchical weapon & ammo NIF/mesh/mat/dds assets into assets/
    if prebuilt_assets_dir is not None:
        shutil.copytree(prebuilt_assets_dir, assets_dir)
    else:
        if fo4_data is None or sf_data is None:
            raise ProbeP5Error("fo4_data and starfield_dir are required to stage P5 weapon assets")
        _stage_p5_weapon_assets(fo4_data, sf_data, assets_dir)

    assets_summary = verify_p5_assets_tree(assets_dir)

    # 3. Build FO4SF_R11P5Weapons.esm + compile FO4SF_NewGameQuest.pex & FO4SF_R11P5Quest.pex
    p5_esm_bytes = build_p5_weapons_esm(port_esm=eff_port_esm)
    (exp_dir / PROBE_PLUGIN).write_bytes(p5_esm_bytes)

    scripts_out = exp_dir / "Data" / "Scripts"
    scripts_out.mkdir(parents=True, exist_ok=True)
    if prebuilt_pex is not None:
        pex_items: List[Tuple[str, bytes]] = []
        for stem, raw in sorted(prebuilt_pex.items()):
            (scripts_out / f"{stem}.pex").write_bytes(raw)
            pex_items.append((f"Scripts\\{stem}.pex", raw))
    else:
        if starfield_dir is None:
            raise ProbeP5Error("either --starfield (for PapyrusCompiler.exe) or prebuilt_pex is required")
        psc_list = [
            REPO / "scripts" / "newgame" / "FO4SF_NewGameQuest.psc",
            REPO / "scripts" / "probes" / "FO4SF_R11P5Quest.psc",
        ]
        compiled = compile_papyrus_scripts(starfield_dir, psc_list, scripts_out)
        pex_items = [(f"Scripts\\{stem}.pex", p.read_bytes()) for stem, p in sorted(compiled.items())]

    # 4. Pack FO4SF_R11P5Weapons - Main.ba2 (GNRL) & - Textures.ba2 (DX10)
    gnrl_items: List[Tuple[str, bytes]] = list(pex_items)
    dds_items: List[Tuple[str, bytes]] = []
    for ap in sorted(assets_dir.rglob("*")):
        if not ap.is_file() or ap.name.endswith("_manifest.json") or ap.name == "manifest.json":
            continue
        rel_win = str(ap.relative_to(assets_dir)).replace("/", "\\")
        if rel_win.lower().startswith("textures\\") and rel_win.lower().endswith(".dds"):
            dds_items.append((rel_win, ap.read_bytes()))
        else:
            gnrl_items.append((rel_win, ap.read_bytes()))

    main_ba2_info = pack_gnrl_ba2_v2(gnrl_items, exp_dir / PROBE_MAIN_BA2, starfield_dir=starfield_dir)
    tex_ba2_info = pack_textures_ba2(assets_dir, dds_items, exp_dir / PROBE_TEX_BA2, starfield_dir=starfield_dir)

    # 5. Write P3-clean .txt batch files
    batches = build_p3_batch_scripts()
    p3_report = validate_p3_batches_and_hops(batches)
    for fname, content in sorted(batches.items()):
        (bat_dir / fname).write_text(content, encoding="utf-8")

    # 6. Cross-check staged .esm trio when live CoreValues/NewGame built
    if prebuilt_core_esms is None:
        catalog, dups = cpc.build_writer_catalog(str(REPO))
        if dups:
            raise ProbeP5Error(f"writer catalog duplicates: {dups}")
        psc_props = cpc.collect_psc_props_by_script(str(REPO))
        for sf_fid, sf_pair in (
            (SF_DONOR_RESCUE_AXE, ("WEAP", "RescueAxe")),
            (SF_DONOR_XM2311, ("WEAP", "XM2311")),
            (SF_DONOR_ORION, ("WEAP", "Orion")),
            (SF_DONOR_MICROGUN, ("WEAP", "Microgun")),
            (SF_DONOR_AMMO45, ("AMMO", "Ammo45Caliber")),
            (SF_DONOR_AMMO_LASER, ("AMMO", "AmmoLaser")),
            (SF_DONOR_AMMO_777, ("AMMO", "Ammo777mm")),
            (SF_AV_HIDE_SUIT, ("AVIF", "ActorShouldForceHideSpacesuit_AV")),
        ):
            catalog["Starfield.esm"].setdefault(sf_fid, sf_pair)
        errs = cpc.validate_staged_esms(
            [
                str(core_dir / "FO4SFCoreValues.esm"),
                str(core_dir / "FO4SFNewGame.esm"),
                str(exp_dir / PROBE_PLUGIN),
            ],
            catalog,
            psc_props,
        )
        if errs:
            raise ProbeP5Error(f"cross_plugin_check errors on staged P5 .esm set: {errs}")

    # 7. Hash every staged file into manifest.json
    file_hashes: Dict[str, dict] = {}
    for p in sorted(out_dir.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            rel = p.relative_to(out_dir).as_posix()
            file_hashes[rel] = {
                "size_bytes": p.stat().st_size,
                "sha256": sha256_file(p),
            }

    free_after = check_free_space_gb(out_dir, min_free_gb)
    manifest = {
        "probe": PROBE_NAME,
        "version": 1,
        "status": "OFFLINE ONLY - UNPROVEN IN GAME",
        "weapon_scope": "FO4_Baton (0x089A), FO4_10mmPistol (0x0899), FO4_LaserMusket (0x089D), FO4_Minigun (0x08A0) + FO4 ammo",
        "standin_disclosure": STANDIN_DISCLOSURE,
        "disk_free_gb_before": free_before,
        "disk_free_gb_after": free_after,
        "swapped_core_esms": list(SWAPPED_CORE_ESMS),
        "weapon_hierarchies": assets_summary["weapons"],
        "probe_plugin": {
            "esm": PROBE_PLUGIN,
            "main_ba2": main_ba2_info,
            "textures_ba2": tex_ba2_info,
            "quest_dnam_flags_hex": f"0x{QUST_START_GAME_ENABLED_FLAGS:08X}",
            "formids": {
                "FO4_Ammo10mm": "FO4SFCoreValues.esm:0x000898",
                "FO4_10mmPistol": "FO4SFCoreValues.esm:0x000899",
                "FO4_Baton": "FO4SFCoreValues.esm:0x00089A",
                "FO4_AmmoFusionCell": "FO4SFCoreValues.esm:0x00089B",
                "FO4_CompanionAmmoFusionCell": "FO4SFCoreValues.esm:0x00089C",
                "FO4_LaserMusket": "FO4SFCoreValues.esm:0x00089D",
                "FO4_CompPrestonLaserMusket": "FO4SFCoreValues.esm:0x00089E",
                "FO4_Ammo5mm": "FO4SFCoreValues.esm:0x00089F",
                "FO4_Minigun": "FO4SFCoreValues.esm:0x0008A0",
                "FO4SF_P5_TargetTriggerRef": f"0x{FID_REF_TRIGGER:08X}",
                "FO4SF_P5_TargetDummyRef": f"0x{FID_ACHR_DUMMY:08X} (flags=0xC00 Persistent|InitiallyDisabled)",
                "FO4SF_P5_BatonCryoRef": f"0x{FID_REF_BATON_CRYO:08X} (FO4 0x0019891C)",
                "FO4SF_P5_BatonCrateRef": f"0x{FID_REF_BATON_CRATE:08X} (FO4 0x000AE470)",
                "FO4SF_P5_LaserMusketRef": f"0x{FID_REF_LASER_MUSKET:08X}",
                "FO4SF_P5_FusionCellBoxes": [
                    f"0x{FID_REF_FUSION_CELL_1:08X}",
                    f"0x{FID_REF_FUSION_CELL_2:08X}",
                    f"0x{FID_REF_FUSION_CELL_3:08X}",
                ],
                "FO4SF_P5_MinigunRef": f"0x{FID_REF_MINIGUN:08X}",
                "FO4SF_P5_Ammo5mmBoxRef": f"0x{FID_REF_AMMO_5MM:08X}",
                "FO4SF_R11P5Quest": f"0x{FID_QUST_P5:08X}",
                "ArmoryCageDoor_RuntimeLookup": "FO4Port.esm:0x001539 (Game.GetFormFromFile, 0 VMAD ObjectRef)",
            },
        },
        "commands": {
            "install": "python scripts/probes/stage_r11_p5_weapons.py install --stage-dir <probe-dir> --starfield <Starfield-dir>",
            "uninstall": "python scripts/probes/stage_r11_p5_weapons.py uninstall --starfield <Starfield-dir>",
            "verify": "python scripts/probes/stage_r11_p5_weapons.py verify --stage-dir <probe-dir>",
        },
        "p3_batches": p3_report,
        "files": file_hashes,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    verify_probe_p5(out_dir)
    return manifest


def verify_probe_p5(stage_dir: Path) -> dict:
    """Read-only SHA-256, ESM record/flag/VMAD/DNAM, NIF hierarchy, BA2 bs_crc32, and P3/hop verification."""
    mpath = stage_dir / "manifest.json"
    if not mpath.is_file():
        raise ProbeP5Error(f"manifest.json missing in {stage_dir}")
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    files = manifest.get("files", {})
    if not files:
        raise ProbeP5Error("manifest.json has no files")

    for rel, meta in files.items():
        p = stage_dir / rel
        if not p.is_file():
            raise ProbeP5Error(f"missing staged file: {rel}")
        if p.stat().st_size != meta["size_bytes"]:
            raise ProbeP5Error(f"size mismatch for {rel}: got {p.stat().st_size}, want {meta['size_bytes']}")
        got = sha256_file(p)
        if got != meta["sha256"]:
            raise ProbeP5Error(f"sha256 mismatch for {rel}: got {got}, want {meta['sha256']}")

    # Inspect FO4SF_R11P5Weapons.esm: TargetDummy 0xC00, QUST DNAM=0x00000009, 0 ArmoryCageDoor VMAD ObjectRef, all placements
    found_refrs: Dict[int, dict] = {}
    dummy_flags = None
    qust_dnam = None
    qust_props: Dict[str, int] = {}
    with Plugin(str(stage_dir / "exp" / PROBE_PLUGIN)) as plg:
        for spans in plg.groups.values():
            for start, end in spans:
                for item in plg.walk(start, end):
                    if item[0] != "REC":
                        continue
                    rec = plg.record_at(item[1])
                    lid = rec.formid & 0xFFFFFF
                    if rec.sig == b"ACHR" and lid == 0x000811:
                        dummy_flags = rec.flags
                    elif rec.sig == b"REFR":
                        nr = rec.get(b"NAME")
                        xr = rec.get(b"XCNT")
                        found_refrs[lid] = {
                            "flags": rec.flags,
                            "base": struct.unpack_from("<I", nr, 0)[0] if nr and len(nr) >= 4 else 0,
                            "xcnt": struct.unpack_from("<i", xr, 0)[0] if xr and len(xr) >= 4 else None,
                        }
                    elif rec.sig == b"QUST" and lid == QUST_P5_LOCAL_ID:
                        dr = rec.get(b"DNAM")
                        if dr and len(dr) >= 4:
                            qust_dnam = struct.unpack_from("<I", dr, 0)[0]
                        vr = rec.get(b"VMAD")
                        if vr:
                            qust_props = _decode_vmad_v6_prop_names(vr)

    if dummy_flags is None or (dummy_flags & 0xC00) != 0xC00:
        raise ProbeP5Error(f"FO4SF_P5_TargetDummyRef (0x000811) must have flags 0xC00, got {dummy_flags}")
    if qust_dnam != QUST_START_GAME_ENABLED_FLAGS:
        raise ProbeP5Error(
            f"FO4SF_R11P5Quest DNAM must be 0x{QUST_START_GAME_ENABLED_FLAGS:08X} (StartGameEnabled|AllowRepeatedStages), got {qust_dnam}"
        )
    if "ArmoryCageDoor" in qust_props:
        raise ProbeP5Error("FO4SF_R11P5Quest VMAD must NOT bind ArmoryCageDoor ObjectReference directly (use GetFormFromFile)")
    if qust_props.get("ArmoryCageDoorLocalId") != VMAD_T_INT or qust_props.get("PortPlugin") != VMAD_T_STRING:
        raise ProbeP5Error("FO4SF_R11P5Quest VMAD missing ArmoryCageDoorLocalId (int) / PortPlugin (string)")

    expected_refrs = {
        0x000812: (CV_WEAP_BATON, None),
        0x000813: (CV_WEAP_BATON, None),
        0x000814: (CV_WEAP_LASER_MUSKET, None),
        0x000815: (CV_AMMO_FUSION_CELL, 24),
        0x000816: (CV_AMMO_FUSION_CELL, 24),
        0x000817: (CV_AMMO_FUSION_CELL, 24),
        0x000818: (CV_WEAP_MINIGUN, None),
        0x000819: (CV_AMMO_5MM, 500),
    }
    for lid, (want_base, want_xcnt) in expected_refrs.items():
        got = found_refrs.get(lid)
        if not got or got["base"] != want_base or got["xcnt"] != want_xcnt:
            raise ProbeP5Error(f"REFR 0x{lid:06X} mismatch: got={got}, want=(base=0x{want_base:08X}, xcnt={want_xcnt})")

    verify_ba2_entry_hashes(stage_dir / "exp" / PROBE_MAIN_BA2, require_uncompressed_gnrl=True)
    verify_ba2_entry_hashes(stage_dir / "exp" / PROBE_TEX_BA2)
    main_ba2 = Ba2(str(stage_dir / "exp" / PROBE_MAIN_BA2))
    tex_ba2 = Ba2(str(stage_dir / "exp" / PROBE_TEX_BA2))
    assets_summary = verify_p5_assets_tree(stage_dir / "assets")

    for rel_nif in list(WEAPON_NIF_RELS.values()) + list(AMMO_NIF_RELS.values()):
        if main_ba2.find(rel_nif) is None:
            raise ProbeP5Error(f"{PROBE_MAIN_BA2} missing packed NIF: {rel_nif}")

    bat_dir = stage_dir / "bat"
    batches = {p.name: p.read_text(encoding="utf-8") for p in sorted(bat_dir.glob("*.txt"))}
    p3 = validate_p3_batches_and_hops(batches)

    return {
        "verified_files": len(files),
        "main_ba2_entries": len(main_ba2.entries),
        "textures_ba2_entries": len(tex_ba2.entries),
        "verified_weapons": sorted(assets_summary["weapons"]),
        "verified_ammo": sorted(assets_summary["ammo"]),
        "qust_dnam_hex": f"0x{qust_dnam:08X}",
        "p3_zero_mnv": p3["p3_zero_mnv"],
        "p3_zero_stripped_fo4sf_edids": p3["p3_zero_stripped_fo4sf_edids"],
        "batch_files": sorted(batches),
    }


def _default_plugins_txt() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / "Starfield" / "Plugins.txt"


def _copy_or_link_ba2_only(src: Path, dst: Path) -> None:
    """NEVER hardlink .esm/.pex/.txt; os.link allowed strictly for .ba2 archives."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        raise ProbeP5Error(f"refusing to overwrite existing destination file: {dst}")
    if src.suffix.lower() == ".ba2":
        try:
            os.link(src, dst)
            return
        except OSError:
            pass
    shutil.copy2(src, dst)


def install_probe_p5(
    stage_dir: Path,
    starfield_dir: Path,
    plugins_txt: Optional[Path] = None,
    min_free_gb: float = DEFAULT_MIN_FREE_GB,
) -> dict:
    """Reversibly back up & swap FO4SFCoreValues.esm + FO4SFNewGame.esm and install FO4SF_R11P5Weapons + P3 batches."""
    check_starfield_not_running()
    verify_probe_p5(stage_dir)
    check_free_space_gb(starfield_dir, min_free_gb)

    data_dir = starfield_dir / "Data"
    if not data_dir.is_dir():
        raise ProbeP5Error(f"Starfield Data directory not found: {data_dir}")
    receipt_path = data_dir / INSTALL_RECEIPT
    if receipt_path.exists():
        raise ProbeP5Error(f"Probe P5 is already installed ({receipt_path}); run uninstall first")

    ptxt = plugins_txt or _default_plugins_txt()
    orig_lines = ptxt.read_text(encoding="utf-8-sig").splitlines() if ptxt.is_file() else []

    backup_dir = stage_dir / "backup_pre_p5"
    if backup_dir.exists() and any(backup_dir.iterdir()):
        raise ProbeP5Error(f"non-empty backup directory exists: {backup_dir}; inspect or uninstall first")
    backup_dir.mkdir(parents=True, exist_ok=True)

    swapped_esms: Dict[str, dict] = {}
    added_data_files: List[dict] = []
    added_root_bats: List[dict] = []

    try:
        for ename in SWAPPED_CORE_ESMS:
            staged_src = stage_dir / "core" / ename
            live_dst = data_dir / ename
            had_prev = live_dst.is_file()
            prev_sha = sha256_file(live_dst) if had_prev else None
            if had_prev:
                shutil.move(str(live_dst), str(backup_dir / ename))
            shutil.copy2(staged_src, live_dst)
            swapped_esms[ename] = {
                "had_previous": had_prev,
                "previous_sha256": prev_sha,
                "installed_sha256": sha256_file(live_dst),
            }

        for fname in (PROBE_PLUGIN, PROBE_MAIN_BA2, PROBE_TEX_BA2):
            src = stage_dir / "exp" / fname
            dst = data_dir / fname
            _copy_or_link_ba2_only(src, dst)
            added_data_files.append({"name": dst.name, "sha256": sha256_file(dst)})

        existing_low = {ln.strip().lstrip("*").casefold() for ln in orig_lines if ln.strip()}
        new_lines = list(orig_lines)
        appended_lines: List[str] = []
        if PROBE_PLUGIN.casefold() not in existing_low:
            line = f"*{PROBE_PLUGIN}"
            new_lines.append(line)
            appended_lines.append(line)

        stamped_batches = build_p3_batch_scripts()
        slot_hex = pc.stamp_batch_formid_prefix(
            stamped_batches,
            data_dir,
            new_lines,
            PROBE_PLUGIN,
            local_ids=(QUST_P5_LOCAL_ID,),
        )
        slot_idx = int(slot_hex, 16)

        for fname, content in sorted(stamped_batches.items()):
            bdst = starfield_dir / fname
            if bdst.exists():
                raise ProbeP5Error(f"refusing to overwrite existing batch file: {bdst}")
            bdst.write_text(content, encoding="utf-8")
            added_root_bats.append({"name": bdst.name, "sha256": sha256_file(bdst)})

        ptxt.parent.mkdir(parents=True, exist_ok=True)
        ptxt.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")

        receipt = {
            "probe": PROBE_NAME,
            "stage_dir": str(stage_dir),
            "backup_dir": str(backup_dir),
            "plugins_txt": str(ptxt),
            "quest_full_master_slot_hex": f"0x{slot_idx:02X}",
            "swapped_esms": swapped_esms,
            "added_data_files": added_data_files,
            "added_root_bats": added_root_bats,
            "appended_plugins_lines": appended_lines,
        }
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        return receipt
    except Exception:
        for item in added_root_bats:
            p = starfield_dir / item["name"]
            if p.exists():
                p.unlink()
        for item in added_data_files:
            p = data_dir / item["name"]
            if p.exists():
                p.unlink()
        for ename, info in swapped_esms.items():
            live_dst = data_dir / ename
            if live_dst.exists():
                live_dst.unlink()
            if info["had_previous"] and (backup_dir / ename).exists():
                shutil.move(str(backup_dir / ename), str(live_dst))
        raise


def uninstall_probe_p5(starfield_dir: Path, plugins_txt: Optional[Path] = None) -> dict:
    """Reversibly remove Probe P5 and restore exact pre-probe FO4SFCoreValues.esm, FO4SFNewGame.esm, and Plugins.txt."""
    check_starfield_not_running()
    data_dir = starfield_dir / "Data"
    receipt_path = data_dir / INSTALL_RECEIPT
    if not receipt_path.is_file():
        raise ProbeP5Error(f"Probe P5 is not installed ({receipt_path} not found)")

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    backup_dir = Path(receipt["backup_dir"])
    ptxt = plugins_txt or Path(receipt["plugins_txt"])

    for item in receipt["added_root_bats"]:
        p = starfield_dir / item["name"]
        if p.is_file():
            if sha256_file(p) != item["sha256"]:
                raise ProbeP5Error(f"refusing to delete modified batch file: {p}")
            p.unlink()

    for item in receipt["added_data_files"]:
        p = data_dir / item["name"]
        if p.is_file():
            if sha256_file(p) != item["sha256"]:
                raise ProbeP5Error(f"refusing to delete modified probe file: {p}")
            p.unlink()

    restored: Dict[str, Optional[str]] = {}
    for ename, info in receipt["swapped_esms"].items():
        live_dst = data_dir / ename
        if live_dst.is_file():
            if sha256_file(live_dst) != info["installed_sha256"]:
                raise ProbeP5Error(f"refusing to replace externally modified {live_dst}")
            live_dst.unlink()
        if info["had_previous"]:
            bfile = backup_dir / ename
            if not bfile.is_file():
                raise ProbeP5Error(f"missing backup file for rollback: {bfile}")
            shutil.move(str(bfile), str(live_dst))
            got_sha = sha256_file(live_dst)
            if got_sha != info["previous_sha256"]:
                raise ProbeP5Error(f"restored {ename} SHA-256 {got_sha} != {info['previous_sha256']}")
            restored[ename] = got_sha
        else:
            restored[ename] = None

    if ptxt.is_file() and receipt.get("appended_plugins_lines"):
        drop = {ln.strip().casefold() for ln in receipt["appended_plugins_lines"]}
        kept = [ln for ln in ptxt.read_text(encoding="utf-8-sig").splitlines() if ln.strip().casefold() not in drop]
        ptxt.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")

    if backup_dir.is_dir() and not any(backup_dir.iterdir()):
        backup_dir.rmdir()
    receipt_path.unlink()
    return {"uninstalled": PROBE_NAME, "restored_esms": restored}


def status_probe_p5(starfield_dir: Path) -> dict:
    receipt_path = starfield_dir / "Data" / INSTALL_RECEIPT
    if not receipt_path.is_file():
        return {"installed": False}
    data = json.loads(receipt_path.read_text(encoding="utf-8"))
    return {"installed": True, "receipt": data}


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Round 11 Probe P5 (Baton, 10mm, Laser Musket & Minigun) stager & installer")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s_st = sub.add_parser("stage")
    s_st.add_argument("--fo4-data", required=True, type=Path)
    s_st.add_argument("--starfield", required=True, type=Path)
    s_st.add_argument("--port-ids", required=True, type=Path)
    s_st.add_argument("--out-dir", required=True, type=Path)
    s_st.add_argument("--port-esm", default=None, type=Path)
    s_st.add_argument("--terrain-core-esm", default=None, type=Path)
    s_st.add_argument("--min-free-gb", default=DEFAULT_MIN_FREE_GB, type=float)

    s_vf = sub.add_parser("verify")
    s_vf.add_argument("--stage-dir", required=True, type=Path)

    s_in = sub.add_parser("install")
    s_in.add_argument("--stage-dir", required=True, type=Path)
    s_in.add_argument("--starfield", required=True, type=Path)
    s_in.add_argument("--plugins-txt", default=None, type=Path)
    s_in.add_argument("--min-free-gb", default=DEFAULT_MIN_FREE_GB, type=float)

    s_un = sub.add_parser("uninstall")
    s_un.add_argument("--starfield", required=True, type=Path)
    s_un.add_argument("--plugins-txt", default=None, type=Path)

    s_stat = sub.add_parser("status")
    s_stat.add_argument("--starfield", required=True, type=Path)

    args = ap.parse_args(argv)
    if args.cmd == "stage":
        m = stage_probe_p5(
            out_dir=args.out_dir,
            fo4_data=args.fo4_data,
            starfield_dir=args.starfield,
            port_ids=args.port_ids,
            port_esm=args.port_esm,
            terrain_core_esm=args.terrain_core_esm,
            min_free_gb=args.min_free_gb,
        )
        print(f"staged {PROBE_NAME} -> {args.out_dir} ({len(m['files'])} files, free={m['disk_free_gb_after']} GiB)")
        print(f"standin_disclosure: {m['standin_disclosure']}")
        return 0
    if args.cmd == "verify":
        res = verify_probe_p5(args.stage_dir)
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0
    if args.cmd == "install":
        res = install_probe_p5(args.stage_dir, args.starfield, plugins_txt=args.plugins_txt, min_free_gb=args.min_free_gb)
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0
    if args.cmd == "uninstall":
        res = uninstall_probe_p5(args.starfield, plugins_txt=args.plugins_txt)
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0
    if args.cmd == "status":
        res = status_probe_p5(args.starfield)
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
