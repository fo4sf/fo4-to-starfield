"""stage_r11_p1_museum.py: Round 11 Probe P1 standalone Museum of Freedom stager, verifier, and reversible installer.

Builds the standalone Probe P1 folder (outside Git worktrees and outside Starfield Data):
  <out-dir>/
    port/
      FO4Port.esm                    (lossless doors_anim_b00 + ConcordMuseum01 + PrewarVault111 + NAVM/NAVI)
      FO4Port - Main.ba2             (minimal +960 file delta merged into b00 Main)
      FO4Port - Textures.ba2         (minimal +220 texture delta merged into b00 Textures; 0 companion stub)
      r11_museum_extension_report.json
    exp/
      FO4SF_R11P1Museum.esm          (4 confirmed-arrival doors + basement terminal + ground raider + QUST)
      FO4SF_R11P1Museum - Main.ba2   (BTDX v2 GNRL archive with compiled FO4SF_ConfirmedLoadDoor.pex & FO4SF_R11P1Quest.pex)
      Data/Scripts/FO4SF_ConfirmedLoadDoor.pex
      Data/Scripts/FO4SF_R11P1Quest.pex
    xtel_extra/                      (OPTIONAL EXTRA ONLY - not the plan of record)
      FO4SF_R11P1XtelExtra.esm       (side-offset +4m east optional native XTEL door pair)
      README_OPTIONAL_XTEL.txt
    bat/                             (P3-clean .txt batch files: zero M/N/V in filenames or typed console commands)
      p1h1.txt, p1c.txt, p1r.txt, p1f.txt, p1b.txt, p1k.txt, p1p.txt, p1q.txt
    manifest.json                    (SHA-256 + byte sizes + FormID map + hop math + reversible install/rollback plan)

Also provides reversible `install`, `uninstall`, and `status` commands that safely back up and swap
existing `Data/FO4Port.*` alongside `candidate-2g-fix` (solving `exp_install.py`'s no-overwrite refusal
for existing `FO4Port.*`) and restore exact pre-probe SHA-256s + `Plugins.txt` on `uninstall`.

Usage:
  python scripts/probes/stage_r11_p1_museum.py stage \
      --base-dir <doors_anim_b00/port> --source-dir <interiors_b10/port> \
      --fo4-esm <Fallout4.esm> --starfield <Starfield game dir> \
      --out-dir <probe stage dir> [--min-free-gb 60]
  python scripts/probes/stage_r11_p1_museum.py verify --stage-dir <probe stage dir>
  python scripts/probes/stage_r11_p1_museum.py install --stage-dir <probe stage dir> --starfield <Starfield game dir>
  python scripts/probes/stage_r11_p1_museum.py uninstall --starfield <Starfield game dir>
  python scripts/probes/stage_r11_p1_museum.py status --starfield <Starfield game dir>
"""
from __future__ import annotations

import argparse
import hashlib
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
TERRAIN_DIR = REPO / "scripts" / "terrain"
for _p in (str(SRC_DIR), str(TERRAIN_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import build_fo4port_r11_museum as ext  # noqa: E402
import vmad_patch  # noqa: E402
from fo4sf.ba2 import Ba2  # noqa: E402

# ---------------------------------------------------------------------------
# Constants, FormIDs, and Coordinates
# ---------------------------------------------------------------------------
PROBE_PLUGIN = "FO4SF_R11P1Museum.esm"
PROBE_MAIN_BA2 = "FO4SF_R11P1Museum - Main.ba2"
XTEL_EXTRA_PLUGIN = "FO4SF_R11P1XtelExtra.esm"
INSTALL_RECEIPT = "FO4SF_R11P1.install.json"
PORT_FILES = ("FO4Port.esm", "FO4Port - Main.ba2", "FO4Port - Textures.ba2")
DEFAULT_MIN_FREE_GB = 60.0

# Master indices in FO4SF_R11P1Museum.esm:
#   0x00 Starfield.esm
#   0x01 FO4Port.esm
#   0x02 FO4TerrainCore.esm
#   0x03 FO4ActorRaider.esm
#   0x04 FO4SF_R11P1Museum.esm (local)
M_SF = 0x00
M_PORT = 0x01
M_CORE = 0x02
M_RAIDER = 0x03
M_LOCAL = 0x04

# Verified FormIDs in masters
PORT_MUSEUM_CELL = (M_PORT << 24) | 0x00E2F4
PORT_MUSEUM_CELL_LOCAL = 0x00E2F4
PORT_MUSEUM_LCTN = (M_PORT << 24) | 0x00E2EF
PORT_MUSEUM_ANCHOR_LOCAL = 0x00E2F5
PORT_MUSEUM_TERM_LOCAL = 0x00E35E                 # Persistent FO4Port_term_08110c_fallout4 in ConcordMuseum01
PORT_MUSEUM_TERM_REF = (M_PORT << 24) | 0x00E35E
PORT_MUSEUM_GATE_LOCAL = 0x00EDF0                 # Persistent FO4Port_switchdoorexsmlatch02 in ConcordMuseum01
PORT_MUSEUM_GATE_REF = (M_PORT << 24) | 0x00EDF0
PORT_MUSEUM_NAVM = (M_PORT << 24) | 0x00EFA8
PORT_PREWAR_CELL = (M_PORT << 24) | 0x00EDFB
CORE_ANCHOR_LOCAL = 0x0A775C                      # Concord persistent anchor in FO4TerrainCore.esm
CORE_FALLBACK_ANCHOR_LOCAL = 0x0A775B             # Vault 111 surface persistent anchor in FO4TerrainCore.esm
CORE_EXIT_PRIMARY_ANCHOR_LOCAL = 0x0A775B         # P1v2 cold-reload fix: Vault 111 surface anchor primary
CORE_EXIT_FALLBACK_ANCHOR_LOCAL = 0x0A775C        # Concord persistent anchor fallback
RAIDER_NPC_BASE = (M_RAIDER << 24) | 0xF04800     # FO4_LvlRaider in FO4ActorRaider.esm

# B1: Visible, collidable FO4Port NIF models + non-zero ObjectBounds for every placed ACTI (zero DecoratorMarker!)
FO4_FRONT_DOOR_MODL = b"fo4port\\setdressing\\doors\\paintedwooddoordoubleload01.nif\x00"
FO4_FRONT_DOOR_OBND = (-1.43, -0.16, 0.0, 1.42, 0.16, 2.40)
FO4_ROOF_DOOR_MODL = b"fo4port\\interiors\\building\\woodp\\doors\\bldwoodpdoorload01.nif\x00"
FO4_ROOF_DOOR_OBND = (-0.07, -0.73, 0.0, 0.14, 0.70, 2.40)
FO4_BASEMENT_TERM_MODL = b"fo4port\\furniture\\terminals\\terminalwall01.nif\x00"
FO4_BASEMENT_TERM_OBND = (-0.27, -0.76, 1.24, 0.31, 0.0, 1.94)
FO4_TRIGGER_CONSOLE_MODL = b"fo4port\\furniture\\terminals\\terminalconsoleon.nif\x00"
FO4_TRIGGER_CONSOLE_OBND = (-0.29, -0.50, 0.0, 0.29, 0.23, 1.40)
DISALLOWED_MARKER_MODEL_TOKENS = ("decoratormarker", "xmarker", "marker", "editor")

SF_CAVE_DOOR_BASE = 0x0024F9CE                    # AutoloadDoor_Cave:Starfield.esm (optional XTEL extra only)
SF_CASLESS_SHELL = 0x002B4AFB                     # Caseless Shotgun Shell ammo for FO4_LvlRaider
SF_DEFAULT_FOLLOW_PKG = 0x00021E76                # defaultFollowPlayerPKG:Starfield.esm (ground raider 3F pursue)
SF_COMBAT_PKG_A = 0x00042240
SF_COMBAT_PKG_B = 0x00089605
SF_PROVEN_LTMP = ext.PROVEN_INTERIOR_LTMP         # 0x0006BCF8 KreetBase01LGTtemplate (proven on Vault111Cryo)
SF_PROVEN_XCIM = 0x00122393
SF_PROVEN_XEMP = b"Data\\Textures\\Cubemaps\\Cell_HiTechHallCube.dds\x00"
QUST_DNAM_START_GAME_ENABLED = 0x00000009         # Bit 0 StartGameEnabled | Bit 3 AllowRepeatedStages

# Local FormIDs in FO4SF_R11P1Museum.esm (prefix 0x04)
FID_ACTI_FRONT_IN = (M_LOCAL << 24) | 0x000800
FID_ACTI_FRONT_OUT = (M_LOCAL << 24) | 0x000801
FID_ACTI_ROOF_OUT = (M_LOCAL << 24) | 0x000802
FID_ACTI_ROOF_IN = (M_LOCAL << 24) | 0x000803
FID_ACTI_BASEMENT_TERM = (M_LOCAL << 24) | 0x000804
FID_ACTI_RAIDER_TRIGGER = (M_LOCAL << 24) | 0x000805
FID_CELL_HOLDING = (M_LOCAL << 24) | 0x00080F     # Probe-owned holding interior CELL (ZERO WRLD/PNDT overrides!)

FID_REF_EXT_FRONT_IN = (M_LOCAL << 24) | 0x000810
FID_REF_INT_FRONT_OUT = (M_LOCAL << 24) | 0x000811
FID_REF_INT_ROOF_OUT = (M_LOCAL << 24) | 0x000812
FID_REF_EXT_ROOF_IN = (M_LOCAL << 24) | 0x000813
FID_REF_INT_BASEMENT_TERM = (M_LOCAL << 24) | 0x000814
FID_ACHR_GROUND_RAIDER = (M_LOCAL << 24) | 0x000815
FID_REF_INT_RAIDER_TRIGGER = (M_LOCAL << 24) | 0x000816
FID_QUST_P1 = (M_LOCAL << 24) | 0x000820
FID_QUST_LOADDOOR = (M_LOCAL << 24) | 0x000821
QUST_P1_LOCAL_ID = 0x000820
DEFAULT_QUEST_LOAD_PREFIX = 0x11  # 00 Starfield, 01 BlueprintShips, 02..10 15 active full ESMs, 11 FO4SF_R11P1Museum

# Implicit full masters Starfield loads automatically ahead of Plugins.txt (light/medium flags 0x300 excluded dynamically)
IMPLICIT_FULL_MASTERS = (
    "Starfield.esm",
    "BlueprintShips-Starfield.esm",
    "Constellation.esm",
    "OldMars.esm",
    "ShatteredSpace.esm",
)

# Overlay world merge offset (FO4Core_Commonwealth measured & pinned across FO4SFMission / FO4SFNewGame)
MERGE_OFFSET_X = -1200.0
MERGE_OFFSET_Y = -2700.0

# Verified Concord exterior merged coordinates (metres)
CONCORD_ANCHOR_MERGED = (-2061.23, -1657.46, 86.93)  # FO4TerrainCore.esm:0x0A775C + MergeOffset
SANCTUARY_BENCH_MERGED = (-2329.25, -1420.19, 112.09)
HOP_MID_MERGED = (-2170.0, -1560.0, 102.0)

EXT_FRONT_DOOR_MERGED = (-2010.69, -1698.04, 89.26)
EXT_FRONT_ARRIVAL_MERGED = (-2012.50, -1697.94, 88.24)
EXT_FRONT_HEADING_DEG = 270.0  # facing west away from Museum facade onto Concord street

EXT_ROOF_DOOR_MERGED = (-1991.27, -1722.57, 97.42)
EXT_ROOF_ARRIVAL_MERGED = (-1990.58, -1724.19, 97.56)  # F9: Fallout 4 0002C1C6 XTEL roof bulkhead (1.77 m from ExtRoofIn)
EXT_ROOF_HEADING_DEG = 335.0   # facing NNW toward ExtRoofInDoor

# Verified walkable interior coordinates on Museum NAVM 0x0100EFA8 (metres)
INT_FRONT_ACTI_POS = (9.02, 0.0, -0.914)        # flush in 0x0100EDEC front doorframe (disabled), rotZ=90 deg
INT_FRONT_ARRIVAL_POS = (7.73, 0.91, -0.90)     # NAVM tri 87 centroid
INT_FRONT_HEADING_DEG = 270.0                   # facing west into Museum lobby

INT_ROOF_ACTI_POS = (-21.943, 9.02, 9.143)      # flush in 0x0100EDF5 roof doorframe (disabled), rotZ=90 deg
INT_ROOF_ARRIVAL_POS = (-21.90, 8.68, 9.15)     # FO4 00029AD8 XTEL roof arrival inside 3F stairwell hallway
INT_ROOF_HEADING_DEG = 90.0                     # facing east back into 3F corridor

INT_BASEMENT_TERM_POS = (-14.092, -1.750, -3.566) # beside basement gate 0x0100EDF0 (-13.714, -0.457, -3.657), rotZ=90 deg
INT_BASEMENT_STAND_POS = (-14.38, -0.10, -3.32) # NAVM tri 1011 centroid

INT_GROUND_RAIDER_POS = (-3.00, 0.00, 0.15)     # NAVM tri 147 (main atrium floor; InitiallyDisabled)
INT_3F_VANTAGE_POS = (-4.00, 7.50, 9.15)        # NAVM tri 817 (3F overlooking atrium; 195-hop path)
INT_3F_RAIDER_TRIGGER_POS = (-4.00, 6.20, 9.15) # Floor-seated console in front of p1k 3F camera (-4.00, 7.50, 9.15)

# Optional XTEL extra side-offset (+4.0 m east of main front door so it never overlaps P1 confirmed door)
XTEL_EXT_OFFSET_MERGED = (-2006.57, -1697.94, 89.26)
XTEL_INT_OFFSET_POS = (8.75, 3.50, -0.90)

# Rule P3: ZERO M, N, or V in ANY batch filename or ANY typed console command, and ZERO stripped FO4SF_ EDIDs in bat!
P3_FORBIDDEN_RE = re.compile(r"[mnvMNV]")
STRIPPED_MOD_EDID_RE = re.compile(r"\bFO4SF_[A-Za-z0-9_]+\b")
MAX_EXTERIOR_HOP_AXIS_M = 200.0
QUST_VMAD_TAIL = b"\x03\x00\x00\x00\x00\x00\x00"


class ProbeError(ValueError):
    """Raised when P1 staging, coordinate/P3 validation, or install/uninstall guards fail."""


# ---------------------------------------------------------------------------
# Pure-Python ESM & BA2 builders for FO4SF_R11P1Museum.esm and optional XTEL
# ---------------------------------------------------------------------------
def _rec(sig: bytes, fid: int, subs: Sequence[Tuple[bytes, bytes]], flags: int = 0, version: int = 576) -> ext.RawRecord:
    return ext.RawRecord(sig, flags, fid, 0, version, 0, ext.pack_subrecords(subs))


def is_invalid_or_marker_model(modl_str: str) -> bool:
    norm = modl_str.replace("/", "\\").strip()
    if not norm:
        return True
    norm_low = norm.lower()
    stem_low = Path(norm).stem.lower()
    return any(tok in norm_low or tok in stem_low for tok in DISALLOWED_MARKER_MODEL_TOKENS)


def has_nonzero_obnd(obnd_bytes: bytes) -> bool:
    if len(obnd_bytes) != 24:
        return False
    x0, y0, z0, x1, y1, z1 = struct.unpack("<6f", obnd_bytes)
    return (x1 - x0) > 1e-3 and (y1 - y0) > 1e-3 and (z1 - z0) > 1e-3


def _make_acti(
    fid: int,
    edid: str,
    full_name: str,
    prompt: str = "Open",
    modl: bytes = FO4_FRONT_DOOR_MODL,
    obnd: Tuple[float, float, float, float, float, float] = FO4_FRONT_DOOR_OBND,
) -> ext.RawRecord:
    modl_str = modl.rstrip(b"\x00").decode("utf-8", errors="replace")
    if is_invalid_or_marker_model(modl_str):
        raise ProbeError(f"B1: ACTI 0x{fid:08X} ({edid}) uses invalid/marker MODL: {modl_str!r}")
    obnd_raw = struct.pack("<6f", *obnd)
    if not has_nonzero_obnd(obnd_raw):
        raise ProbeError(f"B1: ACTI 0x{fid:08X} ({edid}) has zero/degenerate OBND: {obnd}")
    return _rec(
        b"ACTI",
        fid,
        [
            (b"EDID", edid.encode("ascii") + b"\x00"),
            (b"OBND", obnd_raw),
            (b"ODTY", struct.pack("<I", 0)),
            (b"FULL", full_name.encode("utf-8") + b"\x00"),
            (b"MODL", modl),
            (b"PNAM", struct.pack("<I", 0x00334CCC)),
            (b"ATTX", prompt.encode("utf-8") + b"\x00"),
            (b"FNAM", struct.pack("<H", 0)),
            (b"JNAM", struct.pack("<H", 0x0168)),
        ],
    )


def _door_vmad(
    target_plugin: str,
    target_form_id: int,
    direction: str,
    door_tag: str,
    dest_x: float,
    dest_y: float,
    dest_z: float,
    dest_heading: float,
    merge_x: float,
    merge_y: float,
    require_core_cell: bool,
    fallback_plugin: str = "",
    fallback_form_id: int = 0,
    controller_form_id: int = FID_QUST_LOADDOOR,
) -> bytes:
    props = [
        {"name": "LoadDoorController", "type": vmad_patch.T_OBJECT, "status": 1, "value": {"form": controller_form_id, "alias": -1}},
        {"name": "TargetPlugin", "type": vmad_patch.T_STRING, "status": 1, "value": target_plugin},
        {"name": "TargetFormId", "type": vmad_patch.T_INT, "status": 1, "value": target_form_id},
        {"name": "FallbackTargetPlugin", "type": vmad_patch.T_STRING, "status": 1, "value": fallback_plugin},
        {"name": "FallbackTargetFormId", "type": vmad_patch.T_INT, "status": 1, "value": fallback_form_id},
        {"name": "Direction", "type": vmad_patch.T_STRING, "status": 1, "value": direction},
        {"name": "DoorTag", "type": vmad_patch.T_STRING, "status": 1, "value": door_tag},
        {"name": "UseDestinationPosition", "type": vmad_patch.T_BOOL, "status": 1, "value": True},
        {"name": "DestinationX", "type": vmad_patch.T_FLOAT, "status": 1, "value": dest_x},
        {"name": "DestinationY", "type": vmad_patch.T_FLOAT, "status": 1, "value": dest_y},
        {"name": "DestinationZ", "type": vmad_patch.T_FLOAT, "status": 1, "value": dest_z},
        {"name": "DestinationHeading", "type": vmad_patch.T_FLOAT, "status": 1, "value": dest_heading},
        {"name": "MergeOffsetX", "type": vmad_patch.T_FLOAT, "status": 1, "value": merge_x},
        {"name": "MergeOffsetY", "type": vmad_patch.T_FLOAT, "status": 1, "value": merge_y},
        {"name": "RequireCoreCell", "type": vmad_patch.T_BOOL, "status": 1, "value": require_core_cell},
        {"name": "MaxRetries", "type": vmad_patch.T_INT, "status": 1, "value": 3},
        {"name": "EnableLog", "type": vmad_patch.T_BOOL, "status": 1, "value": True},
        {"name": "LogName", "type": vmad_patch.T_STRING, "status": 1, "value": "fo4sf_loaddoor"},
    ]
    return vmad_patch.encode([{"name": "FO4SF_ConfirmedLoadDoor", "status": 0, "properties": props}])


def _make_persistent_refr(
    fid: int,
    edid: str,
    base_fid: int,
    pos: Tuple[float, float, float],
    rot: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    vmad: Optional[bytes] = None,
    xtel: Optional[bytes] = None,
) -> ext.RawRecord:
    subs: List[Tuple[bytes, bytes]] = [(b"EDID", edid.encode("ascii") + b"\x00")]
    if vmad is not None:
        subs.append((b"VMAD", vmad))
    subs.append((b"NAME", struct.pack("<I", base_fid)))
    if xtel is not None:
        subs.append((b"XTEL", xtel))
    subs.append((b"DATA", struct.pack("<6f", pos[0], pos[1], pos[2], rot[0], rot[1], rot[2])))
    return _rec(b"REFR", fid, subs, flags=0x400)


def _make_persistent_achr(
    fid: int,
    edid: str,
    npc_fid: int,
    pos: Tuple[float, float, float],
    rot: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    initially_disabled: bool = True,
) -> ext.RawRecord:
    subs = [
        (b"EDID", edid.encode("ascii") + b"\x00"),
        (b"NAME", struct.pack("<I", npc_fid)),
        (b"DATA", struct.pack("<6f", pos[0], pos[1], pos[2], rot[0], rot[1], rot[2])),
    ]
    flags = 0x400 | (0x800 if initially_disabled else 0)
    return _rec(b"ACHR", fid, subs, flags=flags)


def _make_p1_quest() -> ext.RawRecord:
    props = [
        {
            "name": "GateActivator",
            "type": vmad_patch.T_OBJECT,
            "status": 1,
            "value": {"form": FID_REF_INT_BASEMENT_TERM, "alias": -1},
        },
        {"name": "PortPlugin", "type": vmad_patch.T_STRING, "status": 1, "value": "FO4Port.esm"},
        {"name": "BasementGateLocalId", "type": vmad_patch.T_INT, "status": 1, "value": PORT_MUSEUM_GATE_LOCAL},
        {"name": "BasementTerminalLocalId", "type": vmad_patch.T_INT, "status": 1, "value": PORT_MUSEUM_TERM_LOCAL},
        {"name": "MuseumCellLocalId", "type": vmad_patch.T_INT, "status": 1, "value": PORT_MUSEUM_CELL_LOCAL},
        {
            "name": "ExtFrontInDoor",
            "type": vmad_patch.T_OBJECT,
            "status": 1,
            "value": {"form": FID_REF_EXT_FRONT_IN, "alias": -1},
        },
        {
            "name": "ExtRoofInDoor",
            "type": vmad_patch.T_OBJECT,
            "status": 1,
            "value": {"form": FID_REF_EXT_ROOF_IN, "alias": -1},
        },
        {
            "name": "RaiderTrigger",
            "type": vmad_patch.T_OBJECT,
            "status": 1,
            "value": {"form": FID_REF_INT_RAIDER_TRIGGER, "alias": -1},
        },
        {
            "name": "GroundRaider",
            "type": vmad_patch.T_OBJECT,
            "status": 1,
            "value": {"form": FID_ACHR_GROUND_RAIDER, "alias": -1},
        },
        {
            "name": "HideSpacesuitAV",
            "type": vmad_patch.T_OBJECT,
            "status": 1,
            "value": {"form": 0x000B120E, "alias": -1},
        },
        {"name": "EnableLog", "type": vmad_patch.T_BOOL, "status": 1, "value": True},
        {"name": "LogName", "type": vmad_patch.T_STRING, "status": 1, "value": "fo4sf_r11p1"},
    ]
    q_vmad = vmad_patch.encode([{"name": "FO4SF_R11P1Quest", "status": 0, "properties": props}]) + QUST_VMAD_TAIL

    subs: List[Tuple[bytes, bytes]] = [
        (b"EDID", b"FO4SF_R11P1Quest\x00"),
        (b"VMAD", q_vmad),
        (b"FULL", b"R11 P1 Museum Probe\x00"),
        # DNAM: flags=0x00000009 (Bit 0 StartGameEnabled | Bit 3 AllowRepeatedStages), priority=50, unk=0
        (b"DNAM", struct.pack("<III", QUST_DNAM_START_GAME_ENABLED, 50, 0)),
        (b"QTYP", struct.pack("<I", 0x00047600)),
        # Stages 10 (open basement gate), 20 (start ground-floor raider NAVM combat), 30 (snapshot)
        (b"INDX", struct.pack("<I", 10)),
        (b"QSDT", b"\x00"),
        (b"INDX", struct.pack("<I", 20)),
        (b"QSDT", b"\x00"),
        (b"INDX", struct.pack("<I", 30)),
        (b"QSDT", b"\x00"),
        # ReferenceAlias for GroundRaider giving ammo (60 Caseless Shotgun Shells) + hostile combat AI packages
        (b"ANAM", struct.pack("<I", 1)),
        (b"ALST", struct.pack("<I", 0)),
        (b"ALID", b"GroundRaider\x00"),
        (b"FNAM", struct.pack("<I", 0x00000292)),
        (b"ALFR", struct.pack("<I", FID_ACHR_GROUND_RAIDER)),
        (b"COCT", struct.pack("<I", 1)),
        (b"CNTO", struct.pack("<II", SF_CASLESS_SHELL, 60)),
        (b"ALPC", struct.pack("<I", SF_DEFAULT_FOLLOW_PKG)),
        (b"ALPC", struct.pack("<I", SF_COMBAT_PKG_A)),
        (b"ALPC", struct.pack("<I", SF_COMBAT_PKG_B)),
        (b"ALED", b""),
    ]
    return _rec(b"QUST", FID_QUST_P1, subs, flags=0, version=581)


def _make_load_door_quest() -> ext.RawRecord:
    q_vmad = vmad_patch.encode([{"name": "FO4SF_LoadDoorQuest", "status": 0, "properties": []}]) + QUST_VMAD_TAIL
    subs: List[Tuple[bytes, bytes]] = [
        (b"EDID", b"FO4SF_P1_LoadDoor\x00"),
        (b"VMAD", q_vmad),
        (b"DNAM", struct.pack("<III", QUST_DNAM_START_GAME_ENABLED, 55, 0)),
        (b"QTYP", struct.pack("<I", 0x00047600)),
        (b"INDX", struct.pack("<I", 10)),
        (b"QSDT", b"\x00"),
    ]
    return _rec(b"QUST", FID_QUST_LOADDOOR, subs, flags=0, version=581)


def _assemble_esm(masters: Sequence[str], top_grups: Sequence[ext.TopGrup], next_object_id: int) -> bytes:
    tes4_subs: List[Tuple[bytes, bytes]] = [(b"HEDR", struct.pack("<fII", 0.96, 0, next_object_id))]
    for m in masters:
        tes4_subs.append((b"MAST", m.encode("ascii") + b"\x00"))
        tes4_subs.append((b"DATA", struct.pack("<Q", 0)))
    tes4 = _rec(b"TES4", 0, tes4_subs, flags=1)
    body = b"".join(g.to_bytes() for g in top_grups)
    nrec = ext.count_records_and_grups(tes4.to_bytes() + body)
    fixed_tes4 = ext.update_tes4_hedr(tes4, nrec, next_object_id)
    return fixed_tes4.to_bytes() + body


def _make_full_museum_cell_record(port_esm: Optional[Path] = None) -> ext.RawRecord:
    """Return full CELL 0x0100E2F4 record (preserving EDID, DATA, LTMP=0x0006BCF8, XLCN, XCIM, XEMP)."""
    if port_esm is not None and port_esm.is_file():
        for rec in ext.walk_all_records(port_esm.read_bytes()):
            if rec.sig == b"CELL" and rec.fid == PORT_MUSEUM_CELL:
                return rec
    return _rec(
        b"CELL",
        PORT_MUSEUM_CELL,
        [
            (b"EDID", b"FO4Port_ConcordMuseum01\x00"),
            (b"DATA", struct.pack("<I", 1)),
            (b"LTMP", struct.pack("<I", SF_PROVEN_LTMP)),
            (b"XLCN", struct.pack("<I", PORT_MUSEUM_LCTN)),
            (b"XCIM", struct.pack("<I", SF_PROVEN_XCIM)),
            (b"XEMP", SF_PROVEN_XEMP),
        ],
    )


def _make_holding_cell_record(fid: int, edid: str) -> ext.RawRecord:
    return _rec(
        b"CELL",
        fid,
        [
            (b"EDID", edid.encode("ascii") + b"\x00"),
            (b"DATA", struct.pack("<I", 1)),
            (b"LTMP", struct.pack("<I", SF_PROVEN_LTMP)),
            (b"XCIM", struct.pack("<I", SF_PROVEN_XCIM)),
            (b"XEMP", SF_PROVEN_XEMP),
        ],
    )


def build_p1_museum_esm(port_esm: Optional[Path] = None) -> bytes:
    """Build FO4SF_R11P1Museum.esm with ZERO WRLD/PNDT overrides (holding cell + ConcordMuseum01 + QUST)."""
    actis = [
        _make_acti(FID_ACTI_FRONT_IN, "FO4SF_P1_MuseumFrontIn", "Museum of Freedom (Enter)", "Enter", FO4_FRONT_DOOR_MODL, FO4_FRONT_DOOR_OBND),
        _make_acti(FID_ACTI_FRONT_OUT, "FO4SF_P1_MuseumFrontOut", "Commonwealth (Exit)", "Exit", FO4_FRONT_DOOR_MODL, FO4_FRONT_DOOR_OBND),
        _make_acti(FID_ACTI_ROOF_OUT, "FO4SF_P1_MuseumRoofOut", "Museum Roof (Exit)", "Exit", FO4_ROOF_DOOR_MODL, FO4_ROOF_DOOR_OBND),
        _make_acti(FID_ACTI_ROOF_IN, "FO4SF_P1_MuseumRoofIn", "Museum of Freedom 3F (Enter)", "Enter", FO4_ROOF_DOOR_MODL, FO4_ROOF_DOOR_OBND),
        _make_acti(FID_ACTI_BASEMENT_TERM, "FO4SF_P1_BasementTerminal", "Security Terminal (Unlock Gate)", "Unlock", FO4_BASEMENT_TERM_MODL, FO4_BASEMENT_TERM_OBND),
        _make_acti(FID_ACTI_RAIDER_TRIGGER, "FO4SF_P1_RaiderNavTrigger", "Raider Climb Probe (Start)", "Start", FO4_TRIGGER_CONSOLE_MODL, FO4_TRIGGER_CONSOLE_OBND),
    ]

    ext_front_arr_local = (
        EXT_FRONT_ARRIVAL_MERGED[0] - MERGE_OFFSET_X,
        EXT_FRONT_ARRIVAL_MERGED[1] - MERGE_OFFSET_Y,
        EXT_FRONT_ARRIVAL_MERGED[2],
    )
    ext_roof_arr_local = (
        EXT_ROOF_ARRIVAL_MERGED[0] - MERGE_OFFSET_X,
        EXT_ROOF_ARRIVAL_MERGED[1] - MERGE_OFFSET_Y,
        EXT_ROOF_ARRIVAL_MERGED[2],
    )

    # Authored in probe-owned holding interior CELL 0x0400080F (ZERO WRLD/PNDT overrides!) and relocated
    # dynamically onto MarsPlanetWorld by FO4SF_R11P1Quest whenever the player is outdoors near Concord.
    ref_ext_front_in = _make_persistent_refr(
        FID_REF_EXT_FRONT_IN,
        "FO4SF_P1_ExtFrontInRef",
        FID_ACTI_FRONT_IN,
        (0.0, 0.0, 0.0),
        vmad=_door_vmad(
            target_plugin="FO4Port.esm",
            target_form_id=PORT_MUSEUM_ANCHOR_LOCAL,
            direction="in",
            door_tag="p1_front_in",
            dest_x=INT_FRONT_ARRIVAL_POS[0],
            dest_y=INT_FRONT_ARRIVAL_POS[1],
            dest_z=INT_FRONT_ARRIVAL_POS[2],
            dest_heading=INT_FRONT_HEADING_DEG,
            merge_x=0.0,
            merge_y=0.0,
            require_core_cell=False,
        ),
    )
    ref_ext_roof_in = _make_persistent_refr(
        FID_REF_EXT_ROOF_IN,
        "FO4SF_P1_ExtRoofInRef",
        FID_ACTI_ROOF_IN,
        (4.0, 0.0, 0.0),
        vmad=_door_vmad(
            target_plugin="FO4Port.esm",
            target_form_id=PORT_MUSEUM_ANCHOR_LOCAL,
            direction="in",
            door_tag="p1_roof_in",
            dest_x=INT_ROOF_ARRIVAL_POS[0],
            dest_y=INT_ROOF_ARRIVAL_POS[1],
            dest_z=INT_ROOF_ARRIVAL_POS[2],
            dest_heading=INT_ROOF_HEADING_DEG,
            merge_x=0.0,
            merge_y=0.0,
            require_core_cell=False,
        ),
    )

    # Interior persistent placements in FO4Port_ConcordMuseum01 (0x0100E2F4)
    half_pi = 1.5707963
    ref_int_front_out = _make_persistent_refr(
        FID_REF_INT_FRONT_OUT,
        "FO4SF_P1_IntFrontOutRef",
        FID_ACTI_FRONT_OUT,
        INT_FRONT_ACTI_POS,
        rot=(0.0, 0.0, half_pi),
        vmad=_door_vmad(
            target_plugin="FO4TerrainCore.esm",
            target_form_id=CORE_EXIT_PRIMARY_ANCHOR_LOCAL,
            direction="out",
            door_tag="p1_front_out",
            dest_x=ext_front_arr_local[0],
            dest_y=ext_front_arr_local[1],
            dest_z=ext_front_arr_local[2],
            dest_heading=EXT_FRONT_HEADING_DEG,
            merge_x=MERGE_OFFSET_X,
            merge_y=MERGE_OFFSET_Y,
            require_core_cell=True,
            fallback_plugin="FO4TerrainCore.esm",
            fallback_form_id=CORE_EXIT_FALLBACK_ANCHOR_LOCAL,
        ),
    )
    ref_int_roof_out = _make_persistent_refr(
        FID_REF_INT_ROOF_OUT,
        "FO4SF_P1_IntRoofOutRef",
        FID_ACTI_ROOF_OUT,
        INT_ROOF_ACTI_POS,
        rot=(0.0, 0.0, half_pi),
        vmad=_door_vmad(
            target_plugin="FO4TerrainCore.esm",
            target_form_id=CORE_EXIT_PRIMARY_ANCHOR_LOCAL,
            direction="out",
            door_tag="p1_roof_out",
            dest_x=ext_roof_arr_local[0],
            dest_y=ext_roof_arr_local[1],
            dest_z=ext_roof_arr_local[2],
            dest_heading=EXT_ROOF_HEADING_DEG,
            merge_x=MERGE_OFFSET_X,
            merge_y=MERGE_OFFSET_Y,
            require_core_cell=True,
            fallback_plugin="FO4TerrainCore.esm",
            fallback_form_id=CORE_EXIT_FALLBACK_ANCHOR_LOCAL,
        ),
    )
    ref_int_basement_term = _make_persistent_refr(
        FID_REF_INT_BASEMENT_TERM,
        "FO4SF_P1_BasementTermRef",
        FID_ACTI_BASEMENT_TERM,
        INT_BASEMENT_TERM_POS,
        rot=(0.0, 0.0, half_pi),
    )
    ref_int_raider_trigger = _make_persistent_refr(
        FID_REF_INT_RAIDER_TRIGGER,
        "FO4SF_P1_RaiderNavTriggerRef",
        FID_ACTI_RAIDER_TRIGGER,
        INT_3F_RAIDER_TRIGGER_POS,
    )
    achr_raider = _make_persistent_achr(
        FID_ACHR_GROUND_RAIDER,
        "FO4SF_P1_GroundRaiderRef",
        RAIDER_NPC_BASE,
        INT_GROUND_RAIDER_POS,
        initially_disabled=True,
    )

    # Full CELL 0x0100E2F4 copy (never a 2-subrecord stub!) + probe-owned holding CELL 0x0400080F (ZERO WRLD GRUP!)
    int_cell_rec = _make_full_museum_cell_record(port_esm)
    holding_cell_rec = _make_holding_cell_record(FID_CELL_HOLDING, "FO4SF_P1_HoldingCell")
    cell_payload = ext.wrap_cell_entry(
        int_cell_rec,
        [ref_int_front_out, ref_int_roof_out, ref_int_basement_term, ref_int_raider_trigger, achr_raider],
        [],
    ) + ext.wrap_cell_entry(
        holding_cell_rec,
        [ref_ext_front_in, ref_ext_roof_in],
        [],
    )

    quest_rec = _make_p1_quest()
    load_door_quest_rec = _make_load_door_quest()

    grups = [
        ext.TopGrup(b"ACTI", 0, 0, 0, b"".join(a.to_bytes() for a in actis)),
        ext.TopGrup(b"CELL", 0, 0, 0, cell_payload),
        ext.TopGrup(b"QUST", 0, 0, 0, quest_rec.to_bytes() + load_door_quest_rec.to_bytes()),
    ]
    return _assemble_esm(
        masters=["Starfield.esm", "FO4Port.esm", "FO4TerrainCore.esm", "FO4ActorRaider.esm"],
        top_grups=grups,
        next_object_id=0x000822,
    )


def build_optional_xtel_extra_esm(port_esm: Optional[Path] = None) -> bytes:
    """Removed in P1v2 (F4): holding-cell extra XTEL lobby door was a trap into an empty holding cell."""
    raise ProbeError("FO4SF_R11P1XtelExtra.esm was removed (P1v2 F4: empty holding-cell XTEL trap)")


def bs_crc32(data: bytes) -> int:
    """Bethesda BTDX BA2 CRC32 (poly=0xEDB88320, init=0x00000000, final_xor=0x00000000)."""
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc >> 1) ^ 0xEDB88320) if (crc & 1) else (crc >> 1)
    return crc & 0xFFFFFFFF


def verify_ba2_bs_crc32_headers(ba2_path: Path) -> int:
    """Verify every GNRL or DX10 entry header in a BTDX v2 BA2 carries exact Bethesda bs_crc32 hashes."""
    with ba2_path.open("rb") as f:
        hdr = f.read(32)
        if len(hdr) != 32:
            raise ProbeError(f"{ba2_path.name}: truncated BTDX v2 header")
        magic, ver, kind_b, count, name_off, _e1, _e2 = struct.unpack("<4sI4sIQII", hdr)
        if magic != b"BTDX" or ver != 2:
            raise ProbeError(f"{ba2_path.name}: expected BTDX v2, got {magic!r} v={ver}")
        kind = kind_b.decode("ascii")
        meta = []
        if kind == "GNRL":
            for _ in range(count):
                nh, ext_b, dh, _fl, _off, _pk, _up, _al = struct.unpack("<I4sIIQIII", f.read(36))
                meta.append((nh, ext_b, dh))
        elif kind == "DX10":
            for _ in range(count):
                nh, ext_b, dh, _unk, nch, _chsz, _h, _w, _m, _fmt, _c, _t = struct.unpack(
                    "<I4sIBBHHHBBBB", f.read(24)
                )
                f.seek(24 * nch, os.SEEK_CUR)
                meta.append((nh, ext_b, dh))
        else:
            raise ProbeError(f"{ba2_path.name}: unsupported BA2 kind {kind!r}")

        f.seek(name_off)
        for i, (nh, ext_b, dh) in enumerate(meta):
            slen = struct.unpack("<H", f.read(2))[0]
            raw_name = f.read(slen).decode("utf-8", "replace")
            norm = raw_name.replace("/", "\\").lstrip("\\")
            dir_part = os.path.dirname(norm).lower().encode("ascii")
            stem_part = Path(norm).stem.lower().encode("ascii")
            want_ext = Path(norm).suffix.lstrip(".").lower().encode("ascii")[:4].ljust(4, b"\x00")
            want_nh = bs_crc32(stem_part)
            want_dh = bs_crc32(dir_part)
            if (nh, ext_b, dh) != (want_nh, want_ext, want_dh):
                raise ProbeError(
                    f"{ba2_path.name} entry {i} ({raw_name}): BTDX hash mismatch "
                    f"got=(0x{nh:08X}, {ext_b!r}, 0x{dh:08X}) "
                    f"want=(0x{want_nh:08X}, {want_ext!r}, 0x{want_dh:08X})"
                )
    return count


def pack_gnrl_ba2_v2(
    files: Sequence[Tuple[str, bytes]],
    out_path: Path,
    starfield_dir: Optional[Path] = None,
) -> dict:
    """Write a Starfield BTDX v2 GNRL archive (Archive2.exe preferred when present, exact bs_crc32 fallback) & verify."""
    if not files:
        raise ProbeError("cannot pack empty BA2 archive")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    archive2 = (starfield_dir / "Tools" / "Archive2" / "Archive2.exe") if starfield_dir else None
    used_archive2 = False
    if archive2 is not None and archive2.is_file():
        with tempfile.TemporaryDirectory(prefix="fo4sf_r11p1_a2_") as td:
            root = Path(td)
            src_paths = []
            for rel_name, raw in files:
                norm = rel_name.replace("/", "\\").lstrip("\\")
                dst = root / norm
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(raw)
                src_paths.append(str(dst))
            if out_path.exists():
                out_path.unlink()
            cmd = [
                str(archive2),
                ",".join(src_paths),
                f"-create={out_path}",
                f"-root={root}",
                "-format=General",
                "-compression=None",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and out_path.is_file():
                used_archive2 = True

    if not used_archive2:
        table_size = 36 * len(files)
        cur = 32 + table_size
        entries = []
        payloads = []
        for rel_name, raw in files:
            norm = rel_name.replace("/", "\\").lstrip("\\")
            ext_b = Path(norm).suffix.lstrip(".").lower().encode("ascii")[:4].ljust(4, b"\x00")
            dir_part = os.path.dirname(norm).lower().encode("ascii")
            stem_part = Path(norm).stem.lower().encode("ascii")
            entries.append(
                (
                    bs_crc32(stem_part),
                    ext_b,
                    bs_crc32(dir_part),
                    0x00100100,
                    cur,
                    0,
                    len(raw),
                    ext.BA2_ALIGN,
                )
            )
            payloads.append(raw)
            cur += len(raw)
        name_off = cur
        with out_path.open("wb") as f:
            f.write(struct.pack("<4sI4sIQII", b"BTDX", 2, b"GNRL", len(files), name_off, 1, 0))
            for e in entries:
                f.write(struct.pack("<I4sIIQIII", *e))
            for p in payloads:
                f.write(p)
            for rel_name, _ in files:
                nb = rel_name.replace("/", "\\").lstrip("\\").encode("utf-8")
                f.write(struct.pack("<H", len(nb)) + nb)

    checked = Ba2(str(out_path))
    if len(checked.entries) != len(files):
        raise ProbeError(f"{out_path.name}: entry count mismatch")
    for rel_name, raw in files:
        if checked.read(rel_name) != raw:
            raise ProbeError(f"{out_path.name}: round-trip payload mismatch for {rel_name}")
    verify_ba2_bs_crc32_headers(out_path)
    return {
        "file": out_path.name,
        "entries": len(files),
        "size_bytes": out_path.stat().st_size,
        "sha256": ext.sha256_file(out_path),
        "packer": "Archive2.exe" if used_archive2 else "python-bs-crc32",
    }


# ---------------------------------------------------------------------------
# P3-Clean Batch File Generator, Full-Master Load Index & Hop-Math Validator
# ---------------------------------------------------------------------------
def _tes4_flags(esm_path: Path) -> Optional[int]:
    """Read the 4-byte TES4 record flags from a plugin on disk, or None if unreadable."""
    try:
        with esm_path.open("rb") as f:
            hdr = f.read(12)
        if len(hdr) < 12 or hdr[:4] != b"TES4":
            return None
        return struct.unpack_from("<I", hdr, 8)[0]
    except OSError:
        return None


def compute_full_master_load_index(
    data_dir: Path,
    plugins_txt_lines: Sequence[str],
    target_plugin: str = PROBE_PLUGIN,
) -> int:
    """Compute the 1-byte full-master load index (0x00..0xFC) of target_plugin in Starfield.

    Counts full-master plugins ((TES4.flags & 0x300) == 0; excludes FE light & FD medium masters)
    ahead of target_plugin: implicit full masters present in Data/, followed by active `*...` lines
    in Plugins.txt ahead of target_plugin.
    """
    seen: set[str] = set()
    slot = 0

    for name in IMPLICIT_FULL_MASTERS:
        p = data_dir / name
        if p.is_file():
            fl = _tes4_flags(p)
            if fl is not None and (fl & 0x300) == 0:
                seen.add(name.casefold())
                slot += 1

    target_low = target_plugin.casefold()
    for raw_line in plugins_txt_lines:
        ln = raw_line.strip()
        if not ln or ln.startswith("#") or not ln.startswith("*"):
            continue
        pname = ln[1:].strip()
        plow = pname.casefold()
        if plow == target_low:
            break
        if plow in seen:
            continue
        p = data_dir / pname
        if p.is_file():
            fl = _tes4_flags(p)
            if fl is not None and (fl & 0x300) == 0:
                seen.add(plow)
                slot += 1
    return slot


def build_p3_batch_scripts(quest_load_prefix: int = DEFAULT_QUEST_LOAD_PREFIX) -> Dict[str, str]:
    """Return {filename: content} for all P1 batch scripts (zero M/N/V in filenames/commands, hex FormID only)."""
    qhex = f"{((quest_load_prefix & 0xFF) << 24) | QUST_P1_LOCAL_ID:08X}"
    batches = {
        "p1h1.txt": (
            "; R11 P1 exterior mid-hop from Sanctuary workbench (-2329.25,-1420.19) toward Concord (<160 m/axis)\n"
            f"player.setpos x {HOP_MID_MERGED[0]:.2f}\n"
            f"player.setpos y {HOP_MID_MERGED[1]:.2f}\n"
            f"player.setpos z {HOP_MID_MERGED[2]:.2f}\n"
            "player.setangle z 135\n"
        ),
        "p1c.txt": (
            "; R11 P1 exterior Museum front door approach (<160 m/axis from p1h1, <51 m/axis from 0x0A775C)\n"
            f"player.setpos x {EXT_FRONT_ARRIVAL_MERGED[0]:.2f}\n"
            f"player.setpos y {EXT_FRONT_ARRIVAL_MERGED[1]:.2f}\n"
            f"player.setpos z {EXT_FRONT_ARRIVAL_MERGED[2] + 0.40:.2f}\n"
            "player.setangle z 90\n"
        ),
        "p1r.txt": (
            "; R11 P1 exterior Museum 3F roof approach (<27 m/axis from p1c, facing NNW at roof bulkhead door)\n"
            f"player.setpos x {EXT_ROOF_ARRIVAL_MERGED[0]:.2f}\n"
            f"player.setpos y {EXT_ROOF_ARRIVAL_MERGED[1]:.2f}\n"
            f"player.setpos z {EXT_ROOF_ARRIVAL_MERGED[2] + 0.26:.2f}\n"
            f"player.setangle z {EXT_ROOF_HEADING_DEG:.0f}\n"
        ),
        "p1f.txt": (
            "; R11 P1 enter Museum of Freedom interior (0x0100E2F4, NAVM tri 87)\n"
            "coc FO4Port_ConcordMuseum01\n"
            f"player.setpos x {INT_FRONT_ARRIVAL_POS[0]:.2f}\n"
            f"player.setpos y {INT_FRONT_ARRIVAL_POS[1]:.2f}\n"
            f"player.setpos z {INT_FRONT_ARRIVAL_POS[2]:.2f}\n"
            f"player.setangle z {INT_FRONT_HEADING_DEG:.0f}\n"
        ),
        "p1b.txt": (
            "; R11 P1 INTERIOR-ONLY (FO4Port_ConcordMuseum01): enter via `bat p1f` first!\n"
            "; Stage 10 enforces IsPlayerInMuseum() guard before positioning at basement gate (-14.38, -0.10, -3.32)\n"
            f"SetStage {qhex} 10\n"
        ),
        "p1k.txt": (
            "; R11 P1 INTERIOR-ONLY (FO4Port_ConcordMuseum01): enter via `bat p1f` first!\n"
            "; Stage 20 enforces IsPlayerInMuseum() guard before positioning at 3F vantage (-4.00, 7.50, 9.15)\n"
            f"SetStage {qhex} 20\n"
        ),
        "p1p.txt": (
            "; R11 P1 Pre-War Vault 111 interior check (0x0100EDFB)\n"
            "coc FO4Port_PrewarVault111\n"
        ),
        "p1q.txt": (
            "; R11 P1 status snapshot (logs cell/interior/world/pos/gate/raider to fo4sf_r11p1.0.log)\n"
            f"SetStage {qhex} 30\n"
        ),
    }
    validate_p3_batches_and_hops(batches)
    return batches


def validate_p3_batches_and_hops(batches: Dict[str, str]) -> dict:
    """Enforce P3 (zero M/N/V in filenames & typed commands, zero stripped FO4SF_ EDIDs in bat) and <200 m/axis hops."""
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
        raise ProbeError(f"P3 violation (M/N/V in batch filename or typed command): {bad_names}")
    if stripped_edids:
        raise ProbeError(f"P3 violation (stripped FO4SF_ mod EditorID inside batch file): {stripped_edids}")

    # Verify every exterior hop is strictly < 200 m on every axis!
    hops = [
        ("sanctuary_to_p1h1", SANCTUARY_BENCH_MERGED, HOP_MID_MERGED),
        ("p1h1_to_p1c", HOP_MID_MERGED, EXT_FRONT_ARRIVAL_MERGED),
        ("anchor_0A775C_to_p1c", CONCORD_ANCHOR_MERGED, EXT_FRONT_ARRIVAL_MERGED),
        ("anchor_0A775C_to_front_door", CONCORD_ANCHOR_MERGED, EXT_FRONT_DOOR_MERGED),
        ("p1c_to_p1r", EXT_FRONT_ARRIVAL_MERGED, EXT_ROOF_ARRIVAL_MERGED),
    ]
    hop_report = []
    for label, a, b in hops:
        dx, dy, dz = abs(b[0] - a[0]), abs(b[1] - a[1]), abs(b[2] - a[2])
        if max(dx, dy, dz) >= MAX_EXTERIOR_HOP_AXIS_M:
            raise ProbeError(
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
    return {"typed_commands": typed_commands, "p3_zero_mnv": True, "exterior_hops": hop_report}


# ---------------------------------------------------------------------------
# Papyrus Compilation Helper (uses Starfield Tools PapyrusCompiler + ContentResources)
# ---------------------------------------------------------------------------
def compile_papyrus_scripts(starfield_dir: Path, sources: Sequence[Path], out_dir: Path) -> Dict[str, Path]:
    compiler = starfield_dir / "Tools" / "Papyrus Compiler" / "PapyrusCompiler.exe"
    content_zip = starfield_dir / "Tools" / "ContentResources.zip"
    if not compiler.is_file() or not content_zip.is_file():
        raise ProbeError(f"Starfield Papyrus compiler or ContentResources.zip missing under {starfield_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fo4sf_r11p1_psc_") as td:
        base_dir = Path(td) / "base"
        base_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(content_zip) as zf:
            for info in zf.infolist():
                name = info.filename.replace("\\", "/")
                if (
                    name.startswith("Scripts/Source/")
                    and "/" not in name[len("Scripts/Source/") :]
                    and name.endswith((".psc", ".flg"))
                ):
                    (base_dir / name[len("Scripts/Source/") :]).write_bytes(zf.read(info))
        flg = base_dir / "Starfield_Papyrus_Flags.flg"
        doors_dir = REPO / "scripts" / "doors"
        compiled: Dict[str, Path] = {}
        for src in sources:
            cmd = [
                str(compiler),
                str(src),
                f"-f={flg}",
                f"-i={src.parent};{doors_dir};{base_dir}",
                f"-o={out_dir}",
                "-op",
            ]
            res = subprocess.run(cmd, cwd=str(out_dir), capture_output=True, text=True)
            if res.returncode != 0:
                raise ProbeError(f"Papyrus compilation failed for {src.name}:\n{res.stdout}\n{res.stderr}")
            pex = out_dir / (src.stem + ".pex")
            if not pex.is_file():
                raise ProbeError(f"expected compiled PEX missing: {pex}")
            compiled[src.stem] = pex
        return compiled


# ---------------------------------------------------------------------------
# Stage, Verify, Install, Uninstall, Status
# ---------------------------------------------------------------------------
def stage_probe_p1(
    base_dir: Path,
    source_dir: Path,
    fo4_esm: Path,
    out_dir: Path,
    starfield_dir: Optional[Path] = None,
    prebuilt_pex: Optional[Dict[str, bytes]] = None,
    min_free_gb: float = DEFAULT_MIN_FREE_GB,
    skip_port_ba2: bool = False,
    reuse_port_ba2_dir: Optional[Path] = None,
    clean: bool = False,
    allow_custom_base: bool = False,
) -> dict:
    """Build and verify the complete standalone Probe P1 staging directory."""
    ext.check_out_dir_safe(out_dir, allow_clean=clean)
    if "candidate-" in str(out_dir).lower():
        raise ProbeError(f"refusing to write probe into any candidate folder: {out_dir}")
    free_before = ext.check_free_space_gb(out_dir, min_free_gb)

    port_dir = out_dir / "port"
    exp_dir = out_dir / "exp"
    bat_dir = out_dir / "bat"
    for d in (port_dir, exp_dir, bat_dir):
        d.mkdir(parents=True, exist_ok=True)

    # 1. Build lossless FO4Port.esm + Museum NAVM + minimal Main/Textures BA2 deltas into port/
    base_bytes = (base_dir / "FO4Port.esm").read_bytes()
    source_bytes = (source_dir / "FO4Port.esm").read_bytes()
    nvnm_raw, fo4_doors_m = ext.read_fo4_interior_navm_and_doors(fo4_esm)
    out_port_bytes, port_report = ext.extend_fo4port_esm(
        base_esm_bytes=base_bytes,
        source_esm_bytes=source_bytes,
        target_cells=ext.DEFAULT_CELLS,
        start_id=ext.DEFAULT_START_ID,
        museum_navm_input=(nvnm_raw, ext.FO4_MUSEUM_NAVM_FID, fo4_doors_m),
        expected_base_sha256=None if allow_custom_base else ext.BASE_B00_SHA256,
    )
    port_esm_out = port_dir / "FO4Port.esm"
    port_esm_out.write_bytes(out_port_bytes)

    if not skip_port_ba2:
        reused_ba2 = False
        if (
            reuse_port_ba2_dir is not None
            and (reuse_port_ba2_dir / "FO4Port - Main.ba2").is_file()
            and (reuse_port_ba2_dir / "FO4Port - Textures.ba2").is_file()
        ):
            # F12: ALWAYS copy (never hardlink) so frozen baseline directories stay isolated.
            for bname in ("FO4Port - Main.ba2", "FO4Port - Textures.ba2"):
                dst_b = port_dir / bname
                if dst_b.exists():
                    dst_b.unlink()
                shutil.copy2(reuse_port_ba2_dir / bname, dst_b)
            main_p = port_dir / "FO4Port - Main.ba2"
            tex_p = port_dir / "FO4Port - Textures.ba2"
            m_cnt = verify_ba2_bs_crc32_headers(main_p)
            t_cnt = verify_ba2_bs_crc32_headers(tex_p)
            port_report["ba2"] = {
                "skipped": False,
                "reused_copied_from": str(reuse_port_ba2_dir),
                "main_archive": {
                    "archive": "FO4Port - Main.ba2",
                    "kind": "GNRL",
                    "total_entries": m_cnt,
                    "out_size_bytes": main_p.stat().st_size,
                    "out_sha256": ext.sha256_file(main_p),
                },
                "textures_archive": {
                    "archive": "FO4Port - Textures.ba2",
                    "kind": "DX10",
                    "total_entries": t_cnt,
                    "out_size_bytes": tex_p.stat().st_size,
                    "out_sha256": ext.sha256_file(tex_p),
                },
                "companion_plugins_added": 0,
            }
            reused_ba2 = True

        if not reused_ba2:
            src_tex_candidates = [
                source_dir / "FO4Port - Textures.ba2",
                source_dir / "FO4PortTextures2 - Textures.ba2",
            ]
            delta_plan = ext.trace_cell_asset_delta(
                source_esm_bytes=source_bytes,
                target_cells=ext.DEFAULT_CELLS,
                base_main_ba2=base_dir / "FO4Port - Main.ba2",
                base_tex_ba2=base_dir / "FO4Port - Textures.ba2",
                src_main_ba2=source_dir / "FO4Port - Main.ba2",
                src_tex_ba2s=src_tex_candidates,
            )
            main_res = ext.merge_ba2_v2_lossless(
                base_ba2=base_dir / "FO4Port - Main.ba2",
                delta_sources=[(source_dir / "FO4Port - Main.ba2", delta_plan["delta_main"])],
                out_ba2=port_dir / "FO4Port - Main.ba2",
            )
            tex_sources = [(Path(p), names) for p, names in delta_plan["delta_tex_by_src"].items() if names]
            tex_res = ext.merge_ba2_v2_lossless(
                base_ba2=base_dir / "FO4Port - Textures.ba2",
                delta_sources=tex_sources,
                out_ba2=port_dir / "FO4Port - Textures.ba2",
            )
            port_report["ba2"] = {
                "skipped": False,
                "main_archive": main_res,
                "textures_archive": tex_res,
                "companion_plugins_added": 0,
            }
    else:
        port_report["ba2"] = {"skipped": True}

    (port_dir / "r11_museum_extension_report.json").write_text(
        json.dumps(port_report, indent=2) + "\n", encoding="utf-8"
    )

    # 2. Build FO4SF_R11P1Museum.esm (copying full CELL 0x0100E2F4 subrecords, ZERO WRLD/PNDT!)
    p1_esm_bytes = build_p1_museum_esm(port_esm=port_esm_out)
    (exp_dir / PROBE_PLUGIN).write_bytes(p1_esm_bytes)

    scripts_out = exp_dir / "Data" / "Scripts"
    scripts_out.mkdir(parents=True, exist_ok=True)
    if prebuilt_pex is not None:
        pex_items = []
        for stem, raw in sorted(prebuilt_pex.items()):
            p = scripts_out / f"{stem}.pex"
            p.write_bytes(raw)
            pex_items.append((f"Scripts\\{stem}.pex", raw))
    else:
        if starfield_dir is None:
            raise ProbeError("either --starfield (for PapyrusCompiler.exe) or prebuilt_pex is required")
        psc_list = [
            REPO / "scripts" / "doors" / "FO4SF_LoadDoorQuest.psc",
            REPO / "scripts" / "doors" / "FO4SF_ConfirmedLoadDoor.psc",
            REPO / "scripts" / "probes" / "FO4SF_R11P1Quest.psc",
        ]
        compiled = compile_papyrus_scripts(starfield_dir, psc_list, scripts_out)
        pex_items = [(f"Scripts\\{stem}.pex", p.read_bytes()) for stem, p in sorted(compiled.items())]

    probe_ba2_info = pack_gnrl_ba2_v2(pex_items, exp_dir / PROBE_MAIN_BA2, starfield_dir=starfield_dir)

    # 3. Write P3-clean .txt batch files (F4: holding-cell XTEL trap removed)
    batches = build_p3_batch_scripts()
    p3_report = validate_p3_batches_and_hops(batches)
    for fname, content in sorted(batches.items()):
        (bat_dir / fname).write_text(content, encoding="utf-8")

    # 4. Hash every staged file into manifest.json
    file_hashes: Dict[str, dict] = {}
    for p in sorted(out_dir.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            rel = p.relative_to(out_dir).as_posix()
            file_hashes[rel] = {
                "size_bytes": p.stat().st_size,
                "sha256": ext.sha256_file(p),
            }

    free_after = ext.check_free_space_gb(out_dir, min_free_gb)
    manifest = {
        "probe": "r11-p1-museum",
        "version": 2,
        "status": "OFFLINE ONLY - UNPROVEN IN GAME",
        "disk_free_gb_before": free_before,
        "disk_free_gb_after": free_after,
        "port_extension": {
            "base_sha256": port_report["base_sha256"],
            "out_sha256": port_report["out_sha256"],
            "verification": port_report["verification"],
            "cells": port_report["cells"],
            "notable_museum_refs": port_report.get("notable_museum_refs", {}),
            "museum_navm": port_report["museum_navm"],
            "ba2": port_report["ba2"],
        },
        "probe_plugin": {
            "esm": PROBE_PLUGIN,
            "main_ba2": probe_ba2_info,
            "formids": {
                "FO4SF_P1_ExtFrontInRef": f"0x{FID_REF_EXT_FRONT_IN:08X}",
                "FO4SF_P1_IntFrontOutRef": f"0x{FID_REF_INT_FRONT_OUT:08X}",
                "FO4SF_P1_IntRoofOutRef": f"0x{FID_REF_INT_ROOF_OUT:08X}",
                "FO4SF_P1_ExtRoofInRef": f"0x{FID_REF_EXT_ROOF_IN:08X}",
                "FO4SF_P1_BasementTermRef": f"0x{FID_REF_INT_BASEMENT_TERM:08X}",
                "FO4SF_P1_RaiderNavTriggerRef": f"0x{FID_REF_INT_RAIDER_TRIGGER:08X}",
                "FO4SF_P1_GroundRaiderRef": f"0x{FID_ACHR_GROUND_RAIDER:08X}",
                "FO4SF_R11P1Quest": f"0x{FID_QUST_P1:08X}",
                "FO4SF_LoadDoorQuest": f"0x{FID_QUST_LOADDOOR:08X}",
                "FO4Port_ConcordMuseum01": f"0x{PORT_MUSEUM_CELL:08X}",
                "FO4Port_MuseumAnchor": f"0x{PORT_MUSEUM_ANCHOR_LOCAL:06X}",
                "FO4Port_MuseumBasementTerminal": f"0x{PORT_MUSEUM_TERM_REF:08X}",
                "FO4Port_MuseumBasementGate": f"0x{PORT_MUSEUM_GATE_REF:08X}",
                "FO4Port_MuseumNavm": f"0x{PORT_MUSEUM_NAVM:08X}",
                "FO4Port_PrewarVault111": f"0x{PORT_PREWAR_CELL:08X}",
                "FO4TerrainCore_Anchor": f"0x{CORE_ANCHOR_LOCAL:06X}",
            },
        },
        "xtel_extra_removed": "P1v2 F4: removed empty-holding-cell XTEL trap",
        "p3_batches": p3_report,
        "files": file_hashes,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_probe_stage(stage_dir: Path) -> dict:
    """Read-only SHA-256, P3, ESM structure, XLOC/XLKR, and BA2 verification of a staged Probe P1 directory."""
    mpath = stage_dir / "manifest.json"
    if not mpath.is_file():
        raise ProbeError(f"manifest.json missing in {stage_dir}")
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    files = manifest.get("files", {})
    if not files:
        raise ProbeError("manifest.json has no files")
    if (stage_dir / "xtel_extra").exists():
        raise ProbeError("F4 violation: xtel_extra trap directory must not exist in staged output")

    for rel, meta in files.items():
        p = stage_dir / rel
        if not p.is_file():
            raise ProbeError(f"missing staged file: {rel}")
        if p.stat().st_size != meta["size_bytes"]:
            raise ProbeError(f"size mismatch for {rel}: got {p.stat().st_size}, want {meta['size_bytes']}")
        got = ext.sha256_file(p)
        if got != meta["sha256"]:
            raise ProbeError(f"sha256 mismatch for {rel}: got {got}, want {meta['sha256']}")

    # Verify P1 ESM carries ZERO WRLD/PNDT overrides, full CELL LTMP=0x0006BCF8, and DNAM=0x09
    p1_recs = ext.walk_all_records((stage_dir / "exp" / PROBE_PLUGIN).read_bytes())
    bad_world = [r.sig.decode("ascii") for r in p1_recs if r.sig in (b"WRLD", b"PNDT")]
    if bad_world:
        raise ProbeError(f"{PROBE_PLUGIN} must carry 0 WRLD/PNDT overrides (found {bad_world})")
    p1_cell = next((r for r in p1_recs if r.sig == b"CELL" and r.fid == PORT_MUSEUM_CELL), None)
    if p1_cell is None:
        raise ProbeError(f"{PROBE_PLUGIN} missing CELL 0x{PORT_MUSEUM_CELL:08X}")
    p1_cell_ltmp = next(
        (struct.unpack("<I", sp)[0] for ss, sp in ext.iter_subrecords(p1_cell.decompressed_body()) if ss == b"LTMP"),
        None,
    )
    if p1_cell_ltmp != SF_PROVEN_LTMP:
        raise ProbeError(f"{PROBE_PLUGIN} CELL 0x{PORT_MUSEUM_CELL:08X} LTMP={p1_cell_ltmp}, want 0x{SF_PROVEN_LTMP:08X}")
    p1_qust = next((r for r in p1_recs if r.sig == b"QUST" and r.fid == FID_QUST_P1), None)
    if p1_qust is None:
        raise ProbeError(f"{PROBE_PLUGIN} missing QUST 0x{FID_QUST_P1:08X}")
    q_dnam_flags = next(
        (struct.unpack_from("<I", sp, 0)[0] for ss, sp in ext.iter_subrecords(p1_qust.decompressed_body()) if ss == b"DNAM"),
        0,
    )
    if q_dnam_flags != QUST_DNAM_START_GAME_ENABLED:
        raise ProbeError(f"{PROBE_PLUGIN} QUST DNAM flags=0x{q_dnam_flags:08X}, want 0x{QUST_DNAM_START_GAME_ENABLED:08X}")
    ld_qust = next((r for r in p1_recs if r.sig == b"QUST" and r.fid == FID_QUST_LOADDOOR), None)
    if ld_qust is None:
        raise ProbeError(f"{PROBE_PLUGIN} missing FO4SF_LoadDoorQuest QUST 0x{FID_QUST_LOADDOOR:08X}")
    ld_flags = next(
        (struct.unpack_from("<I", sp, 0)[0] for ss, sp in ext.iter_subrecords(ld_qust.decompressed_body()) if ss == b"DNAM"),
        0,
    )
    if ld_flags != QUST_DNAM_START_GAME_ENABLED:
        raise ProbeError(f"{PROBE_PLUGIN} FO4SF_LoadDoor QUST DNAM flags=0x{ld_flags:08X}, want 0x{QUST_DNAM_START_GAME_ENABLED:08X}")

    # B1 + F9 + cold reload: Every placed ACTI must carry a real non-empty non-marker NIF MODL + non-zero OBND;
    # "out" doors must bind LoadDoorController (0x04000821), target 0x0A775B primary / 0x0A775C fallback, and F9 roof arrival.
    p1_actis = {r.fid: r for r in p1_recs if r.sig == b"ACTI"}
    placed_acti_nifs: Set[str] = set()
    for r in p1_recs:
        if r.sig != b"REFR":
            continue
        subs = dict(ext.iter_subrecords(r.decompressed_body()))
        name_raw = subs.get(b"NAME")
        if not name_raw or len(name_raw) != 4:
            continue
        base_fid = struct.unpack("<I", name_raw)[0]
        if base_fid not in p1_actis:
            continue
        acti = p1_actis[base_fid]
        a_subs = dict(ext.iter_subrecords(acti.decompressed_body()))
        modl_raw = a_subs.get(b"MODL", b"")
        modl_str = modl_raw.rstrip(b"\x00").decode("utf-8", errors="replace")
        if is_invalid_or_marker_model(modl_str):
            raise ProbeError(f"B1: placed ACTI 0x{base_fid:08X} used by REFR 0x{r.fid:08X} has invalid/marker MODL {modl_str!r}")
        if not has_nonzero_obnd(a_subs.get(b"OBND", b"")):
            raise ProbeError(f"B1: placed ACTI 0x{base_fid:08X} used by REFR 0x{r.fid:08X} has zero OBND")
        placed_acti_nifs.add(modl_str.replace("/", "\\").lstrip("\\").lower())
        if b"VMAD" in subs and r.fid in (FID_REF_EXT_FRONT_IN, FID_REF_INT_FRONT_OUT, FID_REF_INT_ROOF_OUT, FID_REF_EXT_ROOF_IN):
            dec = vmad_patch.decode(subs[b"VMAD"])
            pmap = {p["name"]: p["value"] for p in dec["scripts"][0]["properties"]}
            ctrl = pmap.get("LoadDoorController")
            if not isinstance(ctrl, dict) or ctrl.get("form") != FID_QUST_LOADDOOR:
                raise ProbeError(f"door 0x{r.fid:08X} missing LoadDoorController -> 0x{FID_QUST_LOADDOOR:08X}")
            if r.fid in (FID_REF_INT_FRONT_OUT, FID_REF_INT_ROOF_OUT):
                if pmap.get("TargetFormId") != CORE_EXIT_PRIMARY_ANCHOR_LOCAL or pmap.get("FallbackTargetFormId") != CORE_EXIT_FALLBACK_ANCHOR_LOCAL:
                    raise ProbeError(
                        f"out door 0x{r.fid:08X} anchor mismatch: got ({pmap.get('TargetFormId')}, {pmap.get('FallbackTargetFormId')})"
                    )
            if r.fid == FID_REF_INT_ROOF_OUT:
                gx = pmap.get("DestinationX", 0.0) + MERGE_OFFSET_X
                gy = pmap.get("DestinationY", 0.0) + MERGE_OFFSET_Y
                gz = pmap.get("DestinationZ", 0.0)
                if (
                    abs(gx - EXT_ROOF_ARRIVAL_MERGED[0]) > 0.05
                    or abs(gy - EXT_ROOF_ARRIVAL_MERGED[1]) > 0.05
                    or abs(gz - EXT_ROOF_ARRIVAL_MERGED[2]) > 0.05
                ):
                    raise ProbeError(
                        f"F9 mismatch on p1_roof_out: got merged ({gx:.2f}, {gy:.2f}, {gz:.2f}), want {EXT_ROOF_ARRIVAL_MERGED}"
                    )

    # Verify FO4Port.esm basement gate (Novice XLOC) and terminal (persistent + XLOC + XLKR -> gate)
    port_esm_path = stage_dir / "port" / "FO4Port.esm"
    port_recs = {r.fid: r for r in ext.walk_all_records(port_esm_path.read_bytes()) if r.sig != b"TES4"}
    gate_rec = next(
        (
            r
            for r in port_recs.values()
            if r.sig == b"REFR"
            and (r.flags & ext.PERSISTENT_FLAG)
            and ext.refr_name(r) in port_recs
            and ext.get_edid(port_recs[ext.refr_name(r)]) == ext.MUSEUM_BASEMENT_GATE_BASE_EDID
        ),
        None,
    )
    if gate_rec is None:
        raise ProbeError("FO4Port.esm missing persistent basement gate REFR")
    gate_xloc = next((sp for ss, sp in ext.iter_subrecords(gate_rec.decompressed_body()) if ss == b"XLOC"), None)
    if gate_xloc is None or len(gate_xloc) < 12 or gate_xloc[0] != ext.LOCK_LEVEL_NOVICE:
        raise ProbeError(f"FO4Port.esm basement gate 0x{gate_rec.fid:08X} missing Novice level-25 XLOC")

    # Verify basement terminal when present (live b10+ builds): persistent + Novice XLOC + XLKR -> gate
    term_rec = next(
        (
            r
            for r in port_recs.values()
            if r.sig == b"REFR"
            and ext.refr_name(r) in port_recs
            and ext.get_edid(port_recs[ext.refr_name(r)]) == ext.MUSEUM_BASEMENT_TERM_BASE_EDID
        ),
        None,
    )
    if term_rec is not None:
        if not (term_rec.flags & ext.PERSISTENT_FLAG):
            raise ProbeError(f"FO4Port.esm basement terminal 0x{term_rec.fid:08X} must be persistent")
        term_xloc = next((sp for ss, sp in ext.iter_subrecords(term_rec.decompressed_body()) if ss == b"XLOC"), None)
        if term_xloc is None or len(term_xloc) < 12 or term_xloc[0] != ext.LOCK_LEVEL_NOVICE:
            raise ProbeError(f"FO4Port.esm basement terminal 0x{term_rec.fid:08X} missing Novice level-25 XLOC")
        term_xlkrs = [
            struct.unpack_from("<II", sp, 0)[1]
            for ss, sp in ext.iter_subrecords(term_rec.decompressed_body())
            if ss == b"XLKR" and len(sp) >= 8
        ]
        if gate_rec.fid not in term_xlkrs:
            raise ProbeError(f"FO4Port.esm basement terminal 0x{term_rec.fid:08X} missing XLKR to 0x{gate_rec.fid:08X}")

    # L3: Verify FO4Port.esm NAVI 0x00000FF1 preserves base NVMIs + carries every Museum NAVM NVMI
    port_verif = manifest.get("port_extension", {}).get("verification", {})
    if port_verif.get("navm_count", 0) > 0:
        navi_rec = port_recs.get(ext.NAVI_FID)
        if navi_rec is None or navi_rec.sig != b"NAVI":
            raise ProbeError(f"L3: FO4Port.esm missing NAVI 0x{ext.NAVI_FID:08X}")
        navi_navm_fids = {
            ext.navm.parse_nvmi(sp).navmesh
            for ss, sp in ext.iter_subrecords(navi_rec.decompressed_body())
            if ss == b"NVMI"
        }
        museum_navms = [fid for fid, r in port_recs.items() if r.sig == b"NAVM" and (fid & 0x00FFFFFF) >= ext.DEFAULT_START_ID]
        missing_nvmis = [fid for fid in museum_navms if fid not in navi_navm_fids]
        if missing_nvmis:
            raise ProbeError(f"L3: FO4Port.esm NAVI missing Museum NVMIs: {[hex(x) for x in missing_nvmis]}")
        if port_verif.get("added_nvmi_count") != len(museum_navms):
            raise ProbeError(
                f"L3: FO4Port.esm added_nvmi_count={port_verif.get('added_nvmi_count')} != {len(museum_navms)}"
            )

    p1_ba2_path = stage_dir / "exp" / PROBE_MAIN_BA2
    p1_ba2 = Ba2(str(p1_ba2_path))
    verified_ba2_headers = verify_ba2_bs_crc32_headers(p1_ba2_path)
    p1_ba2_names = {e.name.replace("/", "\\").lower() for e in p1_ba2.entries}
    for req_pex in ("scripts\\fo4sf_loaddoorquest.pex", "scripts\\fo4sf_confirmedloaddoor.pex", "scripts\\fo4sf_r11p1quest.pex"):
        if req_pex not in p1_ba2_names:
            raise ProbeError(f"{PROBE_MAIN_BA2} missing compiled script {req_pex}")

    port_main_ba2_path = stage_dir / "port" / "FO4Port - Main.ba2"
    port_tex_ba2_path = stage_dir / "port" / "FO4Port - Textures.ba2"
    for port_ba2_name in ("FO4Port - Main.ba2", "FO4Port - Textures.ba2"):
        pba2 = stage_dir / "port" / port_ba2_name
        if pba2.is_file():
            verified_ba2_headers += verify_ba2_bs_crc32_headers(pba2)

    port_ba2_info = manifest.get("port_extension", {}).get("ba2", {})
    if not port_ba2_info.get("skipped", True):
        if not port_main_ba2_path.is_file() or not port_tex_ba2_path.is_file():
            raise ProbeError("port BA2 archives missing when port_extension.ba2.skipped is False")
        from fo4sf import nif as fo4_nif, sfnif as sf_nif

        main_ba2 = Ba2(str(port_main_ba2_path))
        tex_ba2 = Ba2(str(port_tex_ba2_path))
        main_map = {e.name.replace("/", "\\").lstrip("\\").lower(): e.name for e in main_ba2.entries}
        tex_map = {e.name.replace("/", "\\").lstrip("\\").lower(): e.name for e in tex_ba2.entries}
        for rel_nif in sorted(placed_acti_nifs):
            nif_key = rel_nif if rel_nif.startswith("meshes\\") else f"meshes\\{rel_nif}"
            if nif_key not in main_map:
                raise ProbeError(f"B1: placed ACTI NIF {nif_key} missing from FO4Port - Main.ba2")
            parsed = fo4_nif.parse(main_ba2.read(main_map[nif_key]))
            has_bhk = any(parsed.type_of(i) == "bhkNPCollisionObject" for i in range(len(parsed.blocks)))
            if not has_bhk:
                raise ProbeError(f"B1: placed ACTI NIF {nif_key} lacks bhkNPCollisionObject")
            for i, blk in enumerate(parsed.blocks):
                if parsed.type_of(i) == "BSGeometry":
                    for mesh in sf_nif.parse_bsgeometry(blk).meshes:
                        if mesh is not None:
                            mpath = "geometries\\" + mesh.path.decode("latin-1").replace("/", "\\").lstrip("\\").lower() + ".mesh"
                            if mpath not in main_map:
                                raise ProbeError(f"B1: mesh {mpath} referenced by {nif_key} missing from FO4Port - Main.ba2")
            for s in parsed.strings:
                sp = s.decode("latin-1").replace("/", "\\").lstrip("\\").lower()
                if sp.startswith("materials\\fo4") and sp.endswith(".mat"):
                    if sp not in main_map:
                        raise ProbeError(f"B1: material {sp} referenced by {nif_key} missing from FO4Port - Main.ba2")
                    mat_obj = json.loads(main_ba2.read(main_map[sp]).decode("utf-8-sig"))
                    stack = [mat_obj]
                    while stack:
                        cur = stack.pop()
                        if isinstance(cur, dict):
                            stack.extend(cur.values())
                        elif isinstance(cur, list):
                            stack.extend(cur)
                        elif isinstance(cur, str):
                            tp = cur.replace("/", "\\").lstrip("\\").lower()
                            if tp.startswith("data\\"):
                                tp = tp[5:]
                            if tp.startswith("textures\\fo4") and tp.endswith(".dds") and tp not in tex_map:
                                raise ProbeError(f"B1: texture {tp} referenced by {sp} missing from FO4Port - Textures.ba2")

    # Re-validate all batch files against P3 + hop math
    bat_dir = stage_dir / "bat"
    batches = {p.name: p.read_text(encoding="utf-8") for p in sorted(bat_dir.glob("*.txt"))}
    p3 = validate_p3_batches_and_hops(batches)

    return {
        "verified_files": len(files),
        "p1_esm_records": len(p1_recs),
        "wrld_pndt_overrides": 0,
        "museum_cell_ltmp": f"0x{p1_cell_ltmp:08X}",
        "basement_gate_fid": f"0x{gate_rec.fid:08X}",
        "basement_gate_lock_level": int(gate_xloc[0]),
        "quest_dnam_flags": f"0x{q_dnam_flags:08X}",
        "p1_main_ba2_entries": len(p1_ba2.entries),
        "verified_ba2_bs_crc32_entries": verified_ba2_headers,
        "p3_zero_mnv": p3["p3_zero_mnv"],
        "batch_files": sorted(batches),
    }


def _default_plugins_txt() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / "Starfield" / "Plugins.txt"


def _check_starfield_not_running() -> None:
    if sys.platform != "win32":
        return
    res = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq Starfield.exe", "/NH"],
        capture_output=True,
        text=True,
    )
    if "Starfield.exe" in res.stdout:
        raise ProbeError("Starfield.exe is running; refusing to modify Data or Plugins.txt")


def _same_volume_link_or_copy(src: Path, dst: Path) -> None:
    """Hard-link read-only .ba2 archives to save GiB, but ALWAYS copy2 .esm plugins to prevent shared-inode clobber."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        raise ProbeError(f"refusing to overwrite existing destination file: {dst}")
    if src.suffix.lower() == ".ba2":
        try:
            os.link(src, dst)
            return
        except OSError:
            pass
    shutil.copy2(src, dst)


def install_probe_p1(
    stage_dir: Path,
    starfield_dir: Path,
    plugins_txt: Optional[Path] = None,
    include_xtel_extra: bool = False,
    min_free_gb: float = DEFAULT_MIN_FREE_GB,
    allow_custom_base: bool = False,
) -> dict:
    """Reversibly swap FO4Port.* (with SHA-pinned backup) and install FO4SF_R11P1Museum + P3 batch files."""
    if include_xtel_extra:
        raise ProbeError("FO4SF_R11P1XtelExtra.esm was removed (P1v2 F4: empty holding-cell XTEL trap)")
    _check_starfield_not_running()
    verify_probe_stage(stage_dir)
    ext.check_free_space_gb(starfield_dir, min_free_gb)

    data_dir = starfield_dir / "Data"
    if not data_dir.is_dir():
        raise ProbeError(f"Starfield Data directory not found: {data_dir}")
    receipt_path = data_dir / INSTALL_RECEIPT
    if receipt_path.exists():
        raise ProbeError(f"Probe P1 is already installed ({receipt_path}); run uninstall first")

    # F1: Verify live base FO4Port.esm matches pinned doors_anim_b00 SHA-256 before moving/swapping anything.
    live_port_esm = data_dir / "FO4Port.esm"
    if not allow_custom_base and live_port_esm.is_file():
        live_sha = ext.sha256_file(live_port_esm)
        if live_sha.lower() != ext.BASE_B00_SHA256.lower():
            raise ProbeError(
                f"live FO4Port.esm sha256 mismatch: got {live_sha}, want {ext.BASE_B00_SHA256} "
                "(pass --allow-custom-base only if intentional)"
            )

    ptxt = plugins_txt or _default_plugins_txt()
    ptxt_existed = ptxt.is_file()
    orig_ptxt_raw = ptxt.read_text(encoding="utf-8-sig") if ptxt_existed else ""
    orig_lines = orig_ptxt_raw.splitlines() if ptxt_existed else []

    # F2: Pre-compute Plugins.txt changes & verify NO root batch file collisions BEFORE touching Data or Plugins.txt!
    exp_pairs = [
        (stage_dir / "exp" / PROBE_PLUGIN, data_dir / PROBE_PLUGIN),
        (stage_dir / "exp" / PROBE_MAIN_BA2, data_dir / PROBE_MAIN_BA2),
    ]
    for _src, dst in exp_pairs:
        if dst.exists():
            raise ProbeError(f"refusing to overwrite existing destination file: {dst}")

    added_plugins = [PROBE_PLUGIN]
    existing_low = {ln.strip().lstrip("*").casefold() for ln in orig_lines if ln.strip()}
    new_lines = list(orig_lines)
    appended_lines = []
    for pname in added_plugins:
        if pname.casefold() not in existing_low:
            line = f"*{pname}"
            new_lines.append(line)
            appended_lines.append(line)

    quest_slot = compute_full_master_load_index(data_dir, new_lines, PROBE_PLUGIN)
    stamped_batches = build_p3_batch_scripts(quest_load_prefix=quest_slot)
    for fname in sorted(stamped_batches):
        bdst = starfield_dir / fname
        if bdst.exists():
            raise ProbeError(f"refusing to overwrite existing batch file: {bdst}")

    backup_dir = stage_dir / "backup_pre_p1"
    if backup_dir.exists() and any(backup_dir.iterdir()):
        raise ProbeError(f"non-empty backup directory exists: {backup_dir}; inspect or uninstall first")
    backup_dir.mkdir(parents=True, exist_ok=True)

    swapped_port: Dict[str, dict] = {}
    added_data_files: List[dict] = []
    added_root_bats: List[dict] = []

    # Record planned swap metadata into backup_dir before moving any live files.
    planned_receipt = {
        "status": "installing",
        "probe": "r11-p1-museum",
        "stage_dir": str(stage_dir),
        "backup_dir": str(backup_dir),
        "plugins_txt": str(ptxt),
        "planned_port_files": [f for f in PORT_FILES if (stage_dir / "port" / f).is_file()],
        "planned_added_plugins": added_plugins,
        "planned_batches": sorted(stamped_batches),
    }
    (backup_dir / "planned_install.json").write_text(json.dumps(planned_receipt, indent=2) + "\n", encoding="utf-8")

    try:
        # 1. Back up and swap FO4Port.* (atomic move to backup_dir + copy/link staged port files)
        for fname in PORT_FILES:
            staged_src = stage_dir / "port" / fname
            if not staged_src.is_file():
                continue
            live_dst = data_dir / fname
            had_prev = live_dst.is_file()
            prev_sha = ext.sha256_file(live_dst) if had_prev else None
            if had_prev:
                shutil.move(str(live_dst), str(backup_dir / fname))
            _same_volume_link_or_copy(staged_src, live_dst)
            swapped_port[fname] = {
                "had_previous": had_prev,
                "previous_sha256": prev_sha,
                "installed_sha256": ext.sha256_file(live_dst),
            }

        # 2. Install FO4SF_R11P1Museum.esm + Main.ba2
        for src, dst in exp_pairs:
            _same_volume_link_or_copy(src, dst)
            added_data_files.append({"name": dst.name, "sha256": ext.sha256_file(dst)})

        # 3. Write updated Plugins.txt + stamped P3 batch files into Starfield root
        ptxt.parent.mkdir(parents=True, exist_ok=True)
        ptxt.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")

        for fname, content in sorted(stamped_batches.items()):
            bdst = starfield_dir / fname
            bdst.write_text(content, encoding="utf-8")
            added_root_bats.append({"name": bdst.name, "sha256": ext.sha256_file(bdst)})

        receipt = {
            "probe": "r11-p1-museum",
            "stage_dir": str(stage_dir),
            "backup_dir": str(backup_dir),
            "plugins_txt": str(ptxt),
            "quest_load_prefix_hex": f"0x{quest_slot:02X}",
            "quest_runtime_formid": f"{(quest_slot << 24) | QUST_P1_LOCAL_ID:08X}",
            "swapped_port": swapped_port,
            "added_data_files": added_data_files,
            "added_root_bats": added_root_bats,
            "appended_plugins_lines": appended_lines,
        }
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        planned_file = backup_dir / "planned_install.json"
        if planned_file.exists():
            planned_file.unlink()
        return receipt
    except Exception:
        # F2: Atomic rollback of Plugins.txt, batch files, added ESM/BA2s, and backed-up FO4Port.*
        if ptxt_existed:
            ptxt.write_text(orig_ptxt_raw, encoding="utf-8")
        elif ptxt.exists():
            ptxt.unlink()
        for item in added_root_bats:
            p = starfield_dir / item["name"]
            if p.exists():
                p.unlink()
        for item in added_data_files:
            p = data_dir / item["name"]
            if p.exists():
                p.unlink()
        for fname, info in swapped_port.items():
            live_dst = data_dir / fname
            if live_dst.exists():
                live_dst.unlink()
            if info["had_previous"] and (backup_dir / fname).exists():
                shutil.move(str(backup_dir / fname), str(live_dst))
        planned_file = backup_dir / "planned_install.json"
        if planned_file.exists():
            planned_file.unlink()
        raise


def uninstall_probe_p1(starfield_dir: Path, plugins_txt: Optional[Path] = None) -> dict:
    """Reversibly remove Probe P1 and restore exact pre-probe FO4Port.* and Plugins.txt."""
    _check_starfield_not_running()
    data_dir = starfield_dir / "Data"
    receipt_path = data_dir / INSTALL_RECEIPT
    if not receipt_path.is_file():
        raise ProbeError(f"Probe P1 is not installed ({receipt_path} not found)")

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    backup_dir = Path(receipt["backup_dir"])
    ptxt = plugins_txt or Path(receipt["plugins_txt"])

    # 1. Remove added root batch files (only if SHA matches installed receipt)
    for item in receipt["added_root_bats"]:
        p = starfield_dir / item["name"]
        if p.is_file():
            if ext.sha256_file(p) != item["sha256"]:
                raise ProbeError(f"refusing to delete modified batch file: {p}")
            p.unlink()

    # 2. Remove added Data files (only if SHA matches installed receipt)
    for item in receipt["added_data_files"]:
        p = data_dir / item["name"]
        if p.is_file():
            if ext.sha256_file(p) != item["sha256"]:
                raise ProbeError(f"refusing to delete modified probe file: {p}")
            p.unlink()

    # 3. Restore backed-up FO4Port.* and verify pre-probe SHA-256
    restored = {}
    for fname, info in receipt["swapped_port"].items():
        live_dst = data_dir / fname
        if live_dst.is_file():
            if ext.sha256_file(live_dst) != info["installed_sha256"]:
                raise ProbeError(f"refusing to replace externally modified {live_dst}")
            live_dst.unlink()
        if info["had_previous"]:
            bfile = backup_dir / fname
            if not bfile.is_file():
                raise ProbeError(f"missing backup file for rollback: {bfile}")
            shutil.move(str(bfile), str(live_dst))
            got_sha = ext.sha256_file(live_dst)
            if got_sha != info["previous_sha256"]:
                raise ProbeError(f"restored {fname} SHA mismatch: got {got_sha}, want {info['previous_sha256']}")
            restored[fname] = got_sha

    # 4. Restore Plugins.txt by removing only lines added by this install
    if ptxt.is_file():
        drop = {ln.strip().casefold() for ln in receipt.get("appended_plugins_lines", [])}
        kept = [ln for ln in ptxt.read_text(encoding="utf-8-sig").splitlines() if ln.strip().casefold() not in drop]
        ptxt.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")

    receipt_path.unlink()
    if backup_dir.is_dir() and not any(backup_dir.iterdir()):
        backup_dir.rmdir()
    return {"uninstalled": True, "restored_port_sha256": restored}


def status_probe_p1(starfield_dir: Path) -> dict:
    receipt_path = starfield_dir / "Data" / INSTALL_RECEIPT
    if not receipt_path.is_file():
        return {"installed": False}
    return {"installed": True, "receipt": json.loads(receipt_path.read_text(encoding="utf-8"))}


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Round 11 Probe P1 Museum stager, verifier, and reversible installer")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s_stage = sub.add_parser("stage")
    s_stage.add_argument("--base-dir", required=True)
    s_stage.add_argument("--source-dir", required=True)
    s_stage.add_argument("--fo4-esm", required=True)
    s_stage.add_argument("--starfield", required=True)
    s_stage.add_argument("--out-dir", required=True)
    s_stage.add_argument("--min-free-gb", type=float, default=DEFAULT_MIN_FREE_GB)
    s_stage.add_argument("--skip-port-ba2", action="store_true")
    s_stage.add_argument("--reuse-port-ba2-dir", default="", help="Optional existing port/ dir to copy unchanged FO4Port *.ba2")
    s_stage.add_argument("--clean", action="store_true", help="Allow overwriting/clearing a non-empty --out-dir")
    s_stage.add_argument("--allow-custom-base", action="store_true", help="Skip strict doors_anim_b00 SHA-256 check")

    s_ver = sub.add_parser("verify")
    s_ver.add_argument("--stage-dir", required=True)

    s_inst = sub.add_parser("install")
    s_inst.add_argument("--stage-dir", required=True)
    s_inst.add_argument("--starfield", required=True)
    s_inst.add_argument("--plugins-txt", default="")
    s_inst.add_argument("--include-xtel-extra", action="store_true")
    s_inst.add_argument("--min-free-gb", type=float, default=DEFAULT_MIN_FREE_GB)
    s_inst.add_argument("--allow-custom-base", action="store_true")

    s_un = sub.add_parser("uninstall")
    s_un.add_argument("--starfield", required=True)
    s_un.add_argument("--plugins-txt", default="")

    s_st = sub.add_parser("status")
    s_st.add_argument("--starfield", required=True)

    args = ap.parse_args(argv)
    if args.cmd == "stage":
        rep = stage_probe_p1(
            base_dir=Path(args.base_dir),
            source_dir=Path(args.source_dir),
            fo4_esm=Path(args.fo4_esm),
            out_dir=Path(args.out_dir),
            starfield_dir=Path(args.starfield),
            min_free_gb=args.min_free_gb,
            skip_port_ba2=args.skip_port_ba2,
            reuse_port_ba2_dir=Path(args.reuse_port_ba2_dir) if args.reuse_port_ba2_dir else None,
            clean=args.clean,
            allow_custom_base=args.allow_custom_base,
        )
        print(json.dumps(rep, indent=2))
    elif args.cmd == "verify":
        print(json.dumps(verify_probe_stage(Path(args.stage_dir)), indent=2))
    elif args.cmd == "install":
        print(
            json.dumps(
                install_probe_p1(
                    stage_dir=Path(args.stage_dir),
                    starfield_dir=Path(args.starfield),
                    plugins_txt=Path(args.plugins_txt) if args.plugins_txt else None,
                    include_xtel_extra=args.include_xtel_extra,
                    min_free_gb=args.min_free_gb,
                    allow_custom_base=args.allow_custom_base,
                ),
                indent=2,
            )
        )
    elif args.cmd == "uninstall":
        print(
            json.dumps(
                uninstall_probe_p1(
                    starfield_dir=Path(args.starfield),
                    plugins_txt=Path(args.plugins_txt) if args.plugins_txt else None,
                ),
                indent=2,
            )
        )
    elif args.cmd == "status":
        print(json.dumps(status_probe_p1(Path(args.starfield)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
