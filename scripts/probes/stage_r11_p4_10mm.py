"""stage_r11_p4_10mm.py: Round 11 Probe P4 (Part 1 — 10mm Pistol ALONE) stager, verifier, and reversible installer.

Builds the standalone Probe P4 folder (outside Git worktrees, outside Starfield Data, and outside any candidate-* folder):
  <out-dir>/
    core/
      FO4SFCoreValues.esm              (--fo4-10mm 1: 0x000898 FO4_Ammo10mm + 0x000899 FO4_10mmPistol ONLY)
      FO4SFNewGame.esm                 (--fo4-10mm 1: 0x0820 FO4_10mmPistol + 0x0821 48x FO4_Ammo10mm + auto-equip)
    assets/
      meshes/fo4sf/weapons/10mm/fo4_10mmpistol.nif
      meshes/fo4core/ammo/10mm/10mmammo.nif
      geometries/...                   (10 .mesh v2 files)
      materials/...                    (4 .mat files)
      textures/...                     (13 BC1/BC5/BC4 .dds files)
      r11_10mm_manifest.json
    exp/
      FO4SF_R11P4Pistol.esm            (in-world 10mm Target Practice trigger + InitiallyDisabled 0xC00 TargetDummy + QUST)
      FO4SF_R11P4Pistol - Main.ba2     (BTDX v2 GNRL: FO4SF_NewGameQuest.pex, FO4SF_R11P4Quest.pex, .nif, .mesh, .mat)
      FO4SF_R11P4Pistol - Textures.ba2 (BTDX v2 DX10: 13 converted .dds textures)
      Data/Scripts/FO4SF_NewGameQuest.pex
      Data/Scripts/FO4SF_R11P4Quest.pex
    bat/                               (P3-clean .txt batch files: 0 M/N/V in filenames/commands, 0 FO4SF_ stripped EDIDs)
      p4o.txt, p4d.txt, p4g.txt, p4t.txt, p4h1.txt, p4e.txt, p4s.txt
    manifest.json                      (SHA-256 + byte sizes + rigid-parts disclosure + reversible install/rollback commands)

Safety rules enforced:
  - Starfield.exe process count == 0 before any archive read or Data/Plugins.txt change.
  - Free space >= 60.0 GiB before and after staging and before install.
  - Never writes into any Git worktree, game Data folder (during stage), or candidate-* folder.
  - Never hardlinks .esm, .pex, or .txt files (shutil.copy2 only; os.link allowed strictly for .ba2 archives).
  - Zero M/N/V in batch filenames or typed console commands, and zero stripped FO4SF_ EditorIDs inside bat/*.txt.
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
WEAPONS_DIR = REPO / "scripts" / "weapons"

for _p in (str(SRC_DIR), str(WEAPONS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import stage_r11_10mm as s10  # noqa: E402
from fo4sf.ba2 import Ba2  # noqa: E402
from fo4sf.core import cross_plugin_check as cpc  # noqa: E402
from fo4sf.launcher.crashwatch import GAME_EXE, System  # noqa: E402
from fo4sf.planet.esm import Plugin  # noqa: E402

PROBE_NAME = "r11-p4-10mm"
PROBE_STEM = "FO4SF_R11P4Pistol"
PROBE_PLUGIN = f"{PROBE_STEM}.esm"
PROBE_MAIN_BA2 = f"{PROBE_STEM} - Main.ba2"
PROBE_TEX_BA2 = f"{PROBE_STEM} - Textures.ba2"
INSTALL_RECEIPT = "FO4SF_R11P4.install.json"
SWAPPED_CORE_ESMS = ("FO4SFCoreValues.esm", "FO4SFNewGame.esm")
DEFAULT_MIN_FREE_GB = 60.0
BA2_ALIGN = 0xBAADF00D

# Implicit full-master plugins loaded by Starfield before Plugins.txt entries:
IMPLICIT_FULL_MASTERS = (
    "Starfield.esm",
    "Constellation.esm",
    "OldMars.esm",
    "BlueprintShips-Starfield.esm",
    "ShatteredSpace.esm",
)

# Master indices in FO4SF_R11P4Pistol.esm:
#   0x00 Starfield.esm
#   0x01 FO4Port.esm
#   0x02 FO4SFCoreValues.esm
#   0x03 FO4ActorRaider.esm
#   0x04 FO4SF_R11P4Pistol.esm (local)
M_SF = 0x00
M_PORT = 0x01
M_CV = 0x02
M_RAIDER = 0x03
M_LOCAL = 0x04

PORT_V111_CELL = (M_PORT << 24) | 0x0011F3          # FO4Port_Vault111Cryo (InteriorCellBlock=5, SubBlock=9)
PORT_V111_BLOCK = 5
PORT_V111_SUBBLOCK = 9
PORT_ARMORY_CAGE_DOOR = (M_PORT << 24) | 0x001539   # FO4Port_SwitchDoorExSmLatch01 at (-54.92, 29.71)

CV_AMMO_10MM = (M_CV << 24) | 0x000898              # FO4_Ammo10mm ("10mm Round")
CV_WEAP_10MM = (M_CV << 24) | 0x000899              # FO4_10mmPistol ("10mm Pistol")
RAIDER_CALM_NPC = (M_RAIDER << 24) | 0xF04801       # FO4_LvlRaider_Calm

SF_DONOR_XM2311 = 0x0024561C                        # XM2311
SF_DONOR_AMMO45 = 0x002B5598                        # Ammo45Caliber
SF_AV_HEALTH = 0x000002D4                           # Health
SF_AV_HIDE_SUIT = 0x000B120E                        # ActorShouldForceHideSpacesuit_AV
SF_ACTI_MODL = b"Effects\\sfbgs006\\SFBGS006_SBShipDecoratorMarker.nif\x00"

FID_ACTI_TRIGGER = (M_LOCAL << 24) | 0x000800
FID_REF_TRIGGER = (M_LOCAL << 24) | 0x000810
FID_ACHR_DUMMY = (M_LOCAL << 24) | 0x000811
QUST_P4_LOCAL_ID = 0x000820
FID_QUST_P4 = (M_LOCAL << 24) | QUST_P4_LOCAL_ID
DEFAULT_QUEST_LOAD_PREFIX = 0x11

# Verified Vault 111 Overseer office & Commonwealth exterior coordinates (metres):
OVERSEER_DESK_STANCE = (-55.40, 29.80, 0.15)        # 1.65 m east of desk (-57.03, 30.01, 1.29), facing 278 deg
OVERSEER_DESK_YAW_DEG = 278.0
OVERSEER_TRIGGER_POS = (-55.40, 31.10, 1.35)        # beside Overseer pistol desk
OVERSEER_TARGET_STANCE = (-53.20, 29.80, 0.15)      # east of armory cage doorway (-54.92, 29.71) for clear 4.4 m sightline
OVERSEER_DUMMY_POS = (-48.80, 30.00, 0.15)          # open Overseer office floor (east of 0x01001528 skeleton at -49.99)

SANCTUARY_BENCH_MERGED = (-2329.25, -1420.19, 112.09)
EXT_HOP_MID_MERGED = (-2400.00, -1413.00, 120.00)
V111_HILLTOP_MERGED = (-2467.78, -1406.93, 127.85)

P3_FORBIDDEN_RE = re.compile(r"[mnvMNV]")
STRIPPED_MOD_EDID_RE = re.compile(r"\bFO4SF_[A-Za-z0-9_]+", re.I)
MAX_EXTERIOR_HOP_AXIS_M = 200.0
QUST_VMAD_TAIL = b"\x03\x00\x00\x00\x00\x00\x00"


class ProbeP4Error(ValueError):
    """Raised when P4 staging, verification, P3/hop checks, or reversible install/uninstall guards fail."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_starfield_not_running() -> None:
    pids = System.pids(GAME_EXE)
    if pids:
        raise ProbeP4Error(f"refused while {GAME_EXE} is running (pids={pids})")


def check_free_space_gb(target_path: Path, min_free_gb: float = DEFAULT_MIN_FREE_GB) -> float:
    probe = target_path
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    usage = shutil.disk_usage(probe)
    free_gb = round(usage.free / (1024 ** 3), 2)
    if free_gb < min_free_gb:
        raise ProbeP4Error(f"free disk space {free_gb:.2f} GiB < {min_free_gb:.2f} GiB floor on {probe}")
    return free_gb


def check_out_dir_safe(out_dir: Path, fo4_data: Optional[Path] = None, sf_dir: Optional[Path] = None) -> None:
    resolved = out_dir.resolve()
    norm = os.path.normcase(str(resolved))
    if "candidate-" in norm:
        raise ProbeP4Error(f"refusing to write probe into any candidate-* directory: {out_dir}")
    repo_norm = os.path.normcase(str(REPO.resolve()))
    if norm == repo_norm or norm.startswith(repo_norm + os.sep):
        raise ProbeP4Error(f"refusing to write probe inside Git repository: {out_dir}")
    for label, gdir in (("fo4_data", fo4_data), ("starfield_dir", sf_dir)):
        if gdir is not None:
            gnorm = os.path.normcase(str(gdir.resolve()))
            if norm == gnorm or norm.startswith(gnorm + os.sep):
                raise ProbeP4Error(f"refusing to write probe inside {label}: {out_dir}")
    if out_dir.is_file():
        raise ProbeP4Error(f"out_dir is an existing file: {out_dir}")


# ---------------------------------------------------------------------------
# Pure-Python ESM, VMAD v6 & BA2 builders for FO4SF_R11P4Pistol
# ---------------------------------------------------------------------------
VMAD_T_OBJECT, VMAD_T_STRING, VMAD_T_INT, VMAD_T_FLOAT, VMAD_T_BOOL = 1, 2, 3, 4, 5


def _vmad_wstr(s: str) -> bytes:
    raw = str(s).encode("cp1252")
    if len(raw) > 0xFFFF:
        raise ProbeP4Error("VMAD string too long")
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
            else:
                raise ProbeP4Error(f"unsupported VMAD property type {t}")
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


def _extract_port_cell_record_bytes(port_esm: Optional[Path], cell_fid: int = PORT_V111_CELL) -> bytes:
    """Copy exact CELL 0x010011F3 header+subrecords from FO4Port.esm so interior lighting/fog stay untouched."""
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


def build_p4_pistol_esm(port_esm: Optional[Path] = None) -> bytes:
    """Build FO4SF_R11P4Pistol.esm with persistent trigger ACTI/REFR, InitiallyDisabled (0xC00) TargetDummy, and QUST."""
    acti_trigger = _rec_bytes(
        b"ACTI",
        FID_ACTI_TRIGGER,
        [
            (b"EDID", b"FO4SF_P4_TargetTriggerActi\x00"),
            (b"OBND", struct.pack("<6f", -0.35, -0.35, -0.35, 0.35, 0.35, 0.35)),
            (b"ODTY", struct.pack("<I", 0)),
            (b"FULL", b"10mm Target Practice\x00"),
            (b"MODL", SF_ACTI_MODL),
            (b"PNAM", struct.pack("<I", 0x0033CC4C)),
            (b"ATTX", b"Spawn\x00"),
            (b"FNAM", struct.pack("<H", 0)),
            (b"JNAM", struct.pack("<H", 0x0168)),
        ],
    )

    ref_trigger = _rec_bytes(
        b"REFR",
        FID_REF_TRIGGER,
        [
            (b"EDID", b"FO4SF_P4_TargetTriggerRef\x00"),
            (b"NAME", struct.pack("<I", FID_ACTI_TRIGGER)),
            (
                b"DATA",
                struct.pack(
                    "<6f",
                    OVERSEER_TRIGGER_POS[0],
                    OVERSEER_TRIGGER_POS[1],
                    OVERSEER_TRIGGER_POS[2],
                    0.0,
                    0.0,
                    0.0,
                ),
            ),
        ],
        flags=0x400,  # Persistent
    )

    # Mandatory #559 Rule 3: TargetDummy starts Persistent | InitiallyDisabled (0x400 | 0x800 = 0xC00)!
    achr_dummy = _rec_bytes(
        b"ACHR",
        FID_ACHR_DUMMY,
        [
            (b"EDID", b"FO4SF_P4_TargetDummyRef\x00"),
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
        flags=0x400 | 0x800,
    )

    cell_rec = _extract_port_cell_record_bytes(port_esm, PORT_V111_CELL)
    cell_lbl = struct.pack("<I", PORT_V111_CELL)
    pers_grup = _grup_bytes(cell_lbl, 8, ref_trigger + achr_dummy)
    cell_children = _grup_bytes(cell_lbl, 6, pers_grup)
    subblock_grup = _grup_bytes(struct.pack("<i", PORT_V111_SUBBLOCK), 3, cell_rec + cell_children)
    block_grup = _grup_bytes(struct.pack("<i", PORT_V111_BLOCK), 2, subblock_grup)

    props = [
        {"name": "TargetTrigger", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": FID_REF_TRIGGER, "alias": -1}},
        {"name": "PortPlugin", "type": VMAD_T_STRING, "status": 1, "value": "FO4Port.esm"},
        {"name": "ArmoryCageDoorLocalId", "type": VMAD_T_INT, "status": 1, "value": PORT_ARMORY_CAGE_DOOR & 0x00FFFFFF},
        {"name": "TargetDummy", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": FID_ACHR_DUMMY, "alias": -1}},
        {"name": "Pistol10mm", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": CV_WEAP_10MM, "alias": -1}},
        {"name": "Ammo10mm", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": CV_AMMO_10MM, "alias": -1}},
        {"name": "DonorXm2311", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": SF_DONOR_XM2311, "alias": -1}},
        {"name": "DonorAmmo45", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": SF_DONOR_AMMO45, "alias": -1}},
        {"name": "HealthAV", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": SF_AV_HEALTH, "alias": -1}},
        {"name": "HideSuitAV", "type": VMAD_T_OBJECT, "status": 1, "value": {"form": SF_AV_HIDE_SUIT, "alias": -1}},
        {"name": "EnableLog", "type": VMAD_T_BOOL, "status": 1, "value": True},
        {"name": "LogName", "type": VMAD_T_STRING, "status": 1, "value": "fo4sf_r11p4"},
    ]
    q_vmad = _encode_vmad_v6([{"name": "FO4SF_R11P4Quest", "status": 0, "properties": props}]) + QUST_VMAD_TAIL
    quest_rec = _rec_bytes(
        b"QUST",
        FID_QUST_P4,
        [
            (b"EDID", b"FO4SF_R11P4Quest\x00"),
            (b"VMAD", q_vmad),
            (b"FULL", b"R11 P4 10mm Pistol Probe\x00"),
            (b"DNAM", struct.pack("<III", 0x00000009, 50, 0)),
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
        raise ProbeP4Error(f"{ba2_path.name}: truncated BTDX header")
    magic, version, kind, count, name_off = struct.unpack_from("<4sI4sIQ", raw, 0)
    extra = {1: 0, 2: 8, 3: 12, 7: 8, 8: 12}.get(version)
    if magic != b"BTDX" or kind not in (b"GNRL", b"DX10") or extra is None:
        raise ProbeP4Error(f"{ba2_path.name}: unsupported BTDX header ({magic!r}, v={version}, kind={kind!r})")

    npos = name_off
    names: List[str] = []
    for _ in range(count):
        if npos + 2 > len(raw):
            raise ProbeP4Error(f"{ba2_path.name}: truncated name table")
        nlen, = struct.unpack_from("<H", raw, npos)
        npos += 2
        if npos + nlen > len(raw):
            raise ProbeP4Error(f"{ba2_path.name}: name entry overflows file")
        names.append(raw[npos : npos + nlen].decode("utf-8"))
        npos += nlen

    epos = 24 + extra
    for idx, rel_name in enumerate(names):
        want_h, want_ext, want_d = _ba2_entry_keys(rel_name)
        if kind == b"GNRL":
            if epos + 36 > name_off:
                raise ProbeP4Error(f"{ba2_path.name}: GNRL entry {idx} overflows table")
            got_h, got_ext, got_d, _fl, _off, pk_len, _unpk, _align = struct.unpack_from("<I4sIIQIII", raw, epos)
            epos += 36
            if require_uncompressed_gnrl and pk_len != 0:
                raise ProbeP4Error(f"{ba2_path.name}: GNRL entry {rel_name!r} must be stored uncompressed (pk_len={pk_len})")
        else:
            if epos + 24 > name_off:
                raise ProbeP4Error(f"{ba2_path.name}: DX10 entry {idx} overflows table")
            got_h, got_ext, got_d, _unk, n_chunks, chunk_hdr_sz = struct.unpack_from("<I4sIBBH", raw, epos)
            epos += 24 + n_chunks * chunk_hdr_sz
            if epos > name_off:
                raise ProbeP4Error(f"{ba2_path.name}: DX10 chunks for {idx} overflow table")
        if (got_h, got_ext, got_d) != (want_h, want_ext, want_d):
            raise ProbeP4Error(
                f"{ba2_path.name}: entry[{idx}] {rel_name!r} hash mismatch "
                f"got=(0x{got_h:08X}, {got_ext!r}, 0x{got_d:08X}) "
                f"want=(0x{want_h:08X}, {want_ext!r}, 0x{want_d:08X})"
            )
    return count


def _pack_gnrl_ba2_v2_python(ordered: Sequence[Tuple[str, bytes]], out_path: Path) -> None:
    """Pure-Python uncompressed Starfield BTDX v2 GNRL writer using exact Bethesda bs_crc32."""
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
    """Write an uncompressed Starfield BTDX General archive (preferring Archive2.exe) and verify bs_crc32 + payloads."""
    if not files:
        raise ProbeP4Error("cannot pack empty GNRL BA2 archive")
    ordered = sorted(files, key=lambda kv: kv[0].replace("/", "\\").lower())
    archive2 = starfield_dir / "Tools" / "Archive2" / "Archive2.exe" if starfield_dir is not None else None
    used_archive2 = False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if archive2 is not None and archive2.is_file():
        with tempfile.TemporaryDirectory(prefix=".p4-gnrl-ba2-", dir=str(out_path.parent)) as tdir:
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
        raise ProbeP4Error(f"{out_path.name}: entry count mismatch")
    for rel_name, raw in ordered:
        if checked.read(rel_name) != raw:
            raise ProbeP4Error(f"{out_path.name}: round-trip payload mismatch for {rel_name}")
    return {
        "file": out_path.name,
        "entries": len(ordered),
        "used_archive2": used_archive2,
        "size_bytes": out_path.stat().st_size,
        "sha256": sha256_file(out_path),
    }


def _read_dx10_dds_header(data: bytes) -> dict:
    if len(data) < 148 or data[:4] != b"DDS " or data[84:88] != b"DX10":
        raise ProbeP4Error("DX10 DDS header required for Starfield DX10 BA2")
    height, width = struct.unpack_from("<II", data, 12)
    mips, = struct.unpack_from("<I", data, 28)
    dxgi, = struct.unpack_from("<I", data, 128)
    return {"width": width, "height": height, "mips": max(mips, 1), "dxgi": dxgi, "data_offset": 148}


def _pack_dx10_ba2_v2_python(dds_files: Sequence[Tuple[str, bytes]], out_path: Path) -> None:
    """Pure-Python Starfield BTDX v2 DX10 archive writer using exact Bethesda bs_crc32 (for Linux CI)."""
    ordered = sorted(dds_files, key=lambda kv: kv[0].replace("/", "\\").lower())
    # Each entry has 24B header + 1 chunk (24B) = 48B
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
    """Pack textures into `<PluginStem> - Textures.ba2` via CK Archive2.exe when present, else pure-Python DX10 v2."""
    if not dds_files:
        raise ProbeP4Error("cannot pack empty Textures BA2 archive")
    archive2 = starfield_dir / "Tools" / "Archive2" / "Archive2.exe" if starfield_dir is not None else None
    used_archive2 = False
    if archive2 is not None and archive2.is_file() and (assets_root / "textures").is_dir():
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".p4-tex-ba2-", dir=str(out_path.parent)) as tdir:
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
        raise ProbeP4Error(f"{out_path.name}: expected DX10 BA2 with {len(dds_files)} entries, got {len(checked.entries)}")
    for rel_name, _ in dds_files:
        if checked.find(rel_name) is None:
            raise ProbeP4Error(f"{out_path.name}: missing packed texture {rel_name}")
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
def _tes4_flags(esm_path: Path) -> Optional[int]:
    try:
        with esm_path.open("rb") as fh:
            hdr = fh.read(24)
        if len(hdr) < 24 or hdr[:4] != b"TES4":
            return None
        return struct.unpack_from("<I", hdr, 8)[0]
    except OSError:
        return None


def compute_full_master_load_index(
    data_dir: Path,
    plugins_txt_lines: Sequence[str],
    target_plugin: str = PROBE_PLUGIN,
) -> int:
    """Compute 1-byte full-master load index (0x00..0xFC) of target_plugin, skipping FE/FD light/medium masters."""
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
    """Return {filename: content} for Probe P4 batch scripts (zero M/N/V in filenames/commands, zero FO4SF_ EDIDs)."""
    qhex = f"{((quest_load_prefix & 0xFF) << 24) | QUST_P4_LOCAL_ID:08X}"
    batches = {
        "p4d.txt": (
            "; R11 P4 interior hop inside Vault 111 to Overseer pistol desk (-57.03, 30.01, 1.29) keeping active quest stage\n"
            f"player.setpos x {OVERSEER_DESK_STANCE[0]:.2f}\n"
            f"player.setpos y {OVERSEER_DESK_STANCE[1]:.2f}\n"
            f"player.setpos z {OVERSEER_DESK_STANCE[2]:.2f}\n"
            f"player.setangle z {OVERSEER_DESK_YAW_DEG:.0f}\n"
        ),
        "p4o.txt": (
            "; R11 P4 direct load into Vault 111 Overseer office facing 10mm Pistol & 48x 10mm Round on desk\n"
            "coc FO4Port_Vault111Cryo\n"
            f"player.setpos x {OVERSEER_DESK_STANCE[0]:.2f}\n"
            f"player.setpos y {OVERSEER_DESK_STANCE[1]:.2f}\n"
            f"player.setpos z {OVERSEER_DESK_STANCE[2]:.2f}\n"
            f"player.setangle z {OVERSEER_DESK_YAW_DEG:.0f}\n"
        ),
        "p4g.txt": (
            "; R11 P4 fallback grant + auto-equip 10mm Pistol & 48x 10mm Round (for non-NewGame existing saves)\n"
            f"SetStage {qhex} 10\n"
        ),
        "p4t.txt": (
            "; R11 P4 step east of armory cage doorway and spawn 30-HP practice target 4.4 m ahead (or press E on trigger)\n"
            f"player.setpos x {OVERSEER_TARGET_STANCE[0]:.2f}\n"
            f"player.setpos y {OVERSEER_TARGET_STANCE[1]:.2f}\n"
            f"player.setpos z {OVERSEER_TARGET_STANCE[2]:.2f}\n"
            "player.setangle z 90\n"
            f"SetStage {qhex} 20\n"
        ),
        "p4h1.txt": (
            "; R11 P4 exterior mid-hop from Sanctuary (-2329.25, -1420.19) toward Vault 111 hilltop (<75 m/axis)\n"
            f"player.setpos x {EXT_HOP_MID_MERGED[0]:.2f}\n"
            f"player.setpos y {EXT_HOP_MID_MERGED[1]:.2f}\n"
            f"player.setpos z {EXT_HOP_MID_MERGED[2]:.2f}\n"
            "player.setangle z 275\n"
        ),
        "p4e.txt": (
            "; R11 P4 exterior Vault 111 hilltop clearing (<70 m/axis from p4h1) for daylight 1stP/3rdP/ADS/muzzle check\n"
            f"player.setpos x {V111_HILLTOP_MERGED[0]:.2f}\n"
            f"player.setpos y {V111_HILLTOP_MERGED[1]:.2f}\n"
            f"player.setpos z {V111_HILLTOP_MERGED[2]:.2f}\n"
            "player.setangle z 90\n"
        ),
        "p4s.txt": (
            "; R11 P4 write full scorecard summary line to r11p4 user log\n"
            f"SetStage {qhex} 30\n"
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
        raise ProbeP4Error(f"P3 violation (M/N/V in batch filename or typed command): {bad_names}")
    if stripped_edids:
        raise ProbeP4Error(f"P3 violation (stripped FO4SF_ mod EditorID inside batch file): {stripped_edids}")

    hops = [
        ("sanctuary_to_p4h1", SANCTUARY_BENCH_MERGED, EXT_HOP_MID_MERGED),
        ("p4h1_to_p4e_hilltop", EXT_HOP_MID_MERGED, V111_HILLTOP_MERGED),
    ]
    hop_report = []
    for label, a, b in hops:
        dx, dy, dz = abs(b[0] - a[0]), abs(b[1] - a[1]), abs(b[2] - a[2])
        if max(dx, dy, dz) >= MAX_EXTERIOR_HOP_AXIS_M:
            raise ProbeP4Error(
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
        raise ProbeP4Error(f"missing PapyrusCompiler.exe or ContentResources.zip under {starfield_dir / 'Tools'}")
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="p4_papyrus_") as tdir:
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
                raise ProbeP4Error(f"Papyrus compile failed for {src.name}:\n{r.stdout}\n{r.stderr}")
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
        ["dotnet", "run", "--project", str(cv_proj), "-c", "Release", "--", "build", str(sf_esm), str(core_out_dir), "--fo4-10mm", "1"],
        ["dotnet", "run", "--project", str(cv_proj), "-c", "Release", "--", "check", str(core_out_dir / "FO4SFCoreValues.esm"), str(sf_esm), "--fo4-10mm", "1"],
    ):
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if r.returncode != 0:
            raise ProbeP4Error(f"CoreValues failed ({cmd}):\n{r.stdout}\n{r.stderr}")

    with tempfile.TemporaryDirectory(prefix="p4_ng_pts_") as tdir:
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
                raise ProbeP4Error(f"NewGame failed ({cmd}):\n{r.stdout}\n{r.stderr}")


# ---------------------------------------------------------------------------
# Stage, Verify, Install, Uninstall, Status
# ---------------------------------------------------------------------------
def stage_probe_p4(
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
    """Build and verify the standalone Probe P4 (`r11-p4-10mm`) staging directory."""
    check_starfield_not_running()
    check_out_dir_safe(out_dir, fo4_data=fo4_data, sf_dir=starfield_dir)
    if out_dir.is_dir() and any(out_dir.iterdir()):
        raise ProbeP4Error(f"out_dir is not empty: {out_dir}")
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

    # 1. Stage FO4SFCoreValues.esm (--fo4-10mm 1) & FO4SFNewGame.esm (--fo4-10mm 1) into core/
    if prebuilt_core_esms is not None:
        for ename in SWAPPED_CORE_ESMS:
            if ename not in prebuilt_core_esms:
                raise ProbeP4Error(f"prebuilt_core_esms missing {ename}")
            (core_dir / ename).write_bytes(prebuilt_core_esms[ename])
    else:
        if fo4_data is None or sf_data is None or port_ids is None or eff_port_esm is None or eff_terrain_esm is None:
            raise ProbeP4Error("fo4_data, starfield_dir, port_ids, FO4Port.esm, and FO4TerrainCore.esm are required")
        _build_core_and_newgame_esms(
            sf_esm=sf_data / "Starfield.esm",
            fo4_esm=fo4_data / "Fallout4.esm",
            port_esm=eff_port_esm,
            port_ids=port_ids,
            terrain_core_esm=eff_terrain_esm,
            core_out_dir=core_dir,
        )

    # 2. Stage welded 10mm Pistol + 10mm Round NIF/mesh/mat/dds assets into assets/
    if prebuilt_assets_dir is not None:
        shutil.copytree(prebuilt_assets_dir, assets_dir)
        s10.verify_staged_10mm(str(assets_dir), require_converted_materials=True, require_collision=False)
    else:
        if fo4_data is None or sf_data is None:
            raise ProbeP4Error("fo4_data and starfield_dir are required to stage 10mm assets")
        s10.stage_r11_10mm(str(fo4_data), str(sf_data), str(assets_dir))

    # 3. Build FO4SF_R11P4Pistol.esm + compile FO4SF_NewGameQuest.pex & FO4SF_R11P4Quest.pex
    p4_esm_bytes = build_p4_pistol_esm(port_esm=eff_port_esm)
    (exp_dir / PROBE_PLUGIN).write_bytes(p4_esm_bytes)

    scripts_out = exp_dir / "Data" / "Scripts"
    scripts_out.mkdir(parents=True, exist_ok=True)
    if prebuilt_pex is not None:
        pex_items: List[Tuple[str, bytes]] = []
        for stem, raw in sorted(prebuilt_pex.items()):
            (scripts_out / f"{stem}.pex").write_bytes(raw)
            pex_items.append((f"Scripts\\{stem}.pex", raw))
    else:
        if starfield_dir is None:
            raise ProbeP4Error("either --starfield (for PapyrusCompiler.exe) or prebuilt_pex is required")
        psc_list = [
            REPO / "scripts" / "newgame" / "FO4SF_NewGameQuest.psc",
            REPO / "scripts" / "probes" / "FO4SF_R11P4Quest.psc",
        ]
        compiled = compile_papyrus_scripts(starfield_dir, psc_list, scripts_out)
        pex_items = [(f"Scripts\\{stem}.pex", p.read_bytes()) for stem, p in sorted(compiled.items())]

    # 4. Pack FO4SF_R11P4Pistol - Main.ba2 (GNRL: .pex + .nif + .mesh + .mat) & - Textures.ba2 (DX10: .dds)
    gnrl_items: List[Tuple[str, bytes]] = list(pex_items)
    dds_items: List[Tuple[str, bytes]] = []
    for ap in sorted(assets_dir.rglob("*")):
        if not ap.is_file() or ap.name == "r11_10mm_manifest.json":
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

    # 6. Cross-check staged .esm trio [FO4SFCoreValues.esm, FO4SFNewGame.esm, FO4SF_R11P4Pistol.esm]
    if prebuilt_core_esms is None:
        catalog, dups = cpc.build_writer_catalog(str(REPO))
        if dups:
            raise ProbeP4Error(f"writer catalog duplicates: {dups}")
        psc_props = cpc.collect_psc_props_by_script(str(REPO))
        # Register known Starfield.esm records referenced by FO4SF_R11P4Quest:
        catalog["Starfield.esm"].setdefault(SF_DONOR_AMMO45, ("AMMO", "Ammo45Caliber"))
        catalog["Starfield.esm"].setdefault(SF_AV_HIDE_SUIT, ("AVIF", "ActorShouldForceHideSpacesuit_AV"))
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
            raise ProbeP4Error(f"cross_plugin_check errors on staged P4 .esm set: {errs}")

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
        "weapon_scope": "FO4_10mmPistol (0x000899) + FO4_Ammo10mm (0x000898) ALONE (Laser Musket, Pipe Gun, Minigun gated on P4)",
        "rigid_parts_disclosure": s10.RIGID_PARTS_DISCLOSURE,
        "disk_free_gb_before": free_before,
        "disk_free_gb_after": free_after,
        "swapped_core_esms": list(SWAPPED_CORE_ESMS),
        "probe_plugin": {
            "esm": PROBE_PLUGIN,
            "main_ba2": main_ba2_info,
            "textures_ba2": tex_ba2_info,
            "formids": {
                "FO4_Ammo10mm": "FO4SFCoreValues.esm:0x000898",
                "FO4_10mmPistol": "FO4SFCoreValues.esm:0x000899",
                "FO4SF_Vault111PistolRef": "FO4SFNewGame.esm:0x000820",
                "FO4SF_Vault111AmmoRef": "FO4SFNewGame.esm:0x000821",
                "ArmoryCageDoor": "FO4Port.esm:0x001539",
                "FO4SF_P4_TargetTriggerActi": f"0x{FID_ACTI_TRIGGER:08X}",
                "FO4SF_P4_TargetTriggerRef": f"0x{FID_REF_TRIGGER:08X}",
                "FO4SF_P4_TargetDummyRef": f"0x{FID_ACHR_DUMMY:08X} (flags=0xC00 Persistent|InitiallyDisabled)",
                "FO4SF_R11P4Quest": f"0x{FID_QUST_P4:08X}",
            },
        },
        "commands": {
            "install": "python scripts/probes/stage_r11_p4_10mm.py install --stage-dir <probe-dir> --starfield <Starfield-dir>",
            "uninstall": "python scripts/probes/stage_r11_p4_10mm.py uninstall --starfield <Starfield-dir>",
            "verify": "python scripts/probes/stage_r11_p4_10mm.py verify --stage-dir <probe-dir>",
        },
        "p3_batches": p3_report,
        "files": file_hashes,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    verify_probe_p4(out_dir)
    return manifest


def verify_probe_p4(stage_dir: Path) -> dict:
    """Read-only SHA-256, ESM record/flag, BA2, and P3/hop verification of a staged Probe P4 directory."""
    mpath = stage_dir / "manifest.json"
    if not mpath.is_file():
        raise ProbeP4Error(f"manifest.json missing in {stage_dir}")
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    files = manifest.get("files", {})
    if not files:
        raise ProbeP4Error("manifest.json has no files")

    for rel, meta in files.items():
        p = stage_dir / rel
        if not p.is_file():
            raise ProbeP4Error(f"missing staged file: {rel}")
        if p.stat().st_size != meta["size_bytes"]:
            raise ProbeP4Error(f"size mismatch for {rel}: got {p.stat().st_size}, want {meta['size_bytes']}")
        got = sha256_file(p)
        if got != meta["sha256"]:
            raise ProbeP4Error(f"sha256 mismatch for {rel}: got {got}, want {meta['sha256']}")

    # Verify FO4SF_R11P4Pistol.esm structure & TargetDummy InitiallyDisabled (0xC00) flag
    with Plugin(str(stage_dir / "exp" / PROBE_PLUGIN)) as plg:
        dummy_flags = None
        for grp, spans in plg.groups.items():
            for start, end in spans:
                for item in plg.walk(start, end):
                    if item[0] != "REC":
                        continue
                    rec = plg.record_at(item[1])
                    if rec.sig == b"ACHR" and (rec.formid & 0xFFFFFF) == 0x000811:
                        dummy_flags = rec.flags
        if dummy_flags is None or (dummy_flags & 0xC00) != 0xC00:
            raise ProbeP4Error(
                f"FO4SF_P4_TargetDummyRef (0x000811) must have flags 0xC00 (Persistent|InitiallyDisabled), got {dummy_flags}"
            )

    verify_ba2_entry_hashes(stage_dir / "exp" / PROBE_MAIN_BA2, require_uncompressed_gnrl=True)
    verify_ba2_entry_hashes(stage_dir / "exp" / PROBE_TEX_BA2)
    main_ba2 = Ba2(str(stage_dir / "exp" / PROBE_MAIN_BA2))
    tex_ba2 = Ba2(str(stage_dir / "exp" / PROBE_TEX_BA2))
    s10.verify_staged_10mm(str(stage_dir / "assets"), require_converted_materials=True, require_collision=False)

    bat_dir = stage_dir / "bat"
    batches = {p.name: p.read_text(encoding="utf-8") for p in sorted(bat_dir.glob("*.txt"))}
    p3 = validate_p3_batches_and_hops(batches)

    return {
        "verified_files": len(files),
        "main_ba2_entries": len(main_ba2.entries),
        "textures_ba2_entries": len(tex_ba2.entries),
        "p3_zero_mnv": p3["p3_zero_mnv"],
        "p3_zero_stripped_fo4sf_edids": p3["p3_zero_stripped_fo4sf_edids"],
        "batch_files": sorted(batches),
    }


def _default_plugins_txt() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / "Starfield" / "Plugins.txt"


def _copy_or_link_ba2_only(src: Path, dst: Path) -> None:
    """Mandatory #559 Rule 2: NEVER hardlink .esm/.pex/.txt; os.link allowed strictly for .ba2 archives."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        raise ProbeP4Error(f"refusing to overwrite existing destination file: {dst}")
    if src.suffix.lower() == ".ba2":
        try:
            os.link(src, dst)
            return
        except OSError:
            pass
    shutil.copy2(src, dst)


def install_probe_p4(
    stage_dir: Path,
    starfield_dir: Path,
    plugins_txt: Optional[Path] = None,
    min_free_gb: float = DEFAULT_MIN_FREE_GB,
) -> dict:
    """Reversibly back up & swap FO4SFCoreValues.esm + FO4SFNewGame.esm and install FO4SF_R11P4Pistol + P3 batches."""
    check_starfield_not_running()
    verify_probe_p4(stage_dir)
    check_free_space_gb(starfield_dir, min_free_gb)

    data_dir = starfield_dir / "Data"
    if not data_dir.is_dir():
        raise ProbeP4Error(f"Starfield Data directory not found: {data_dir}")
    receipt_path = data_dir / INSTALL_RECEIPT
    if receipt_path.exists():
        raise ProbeP4Error(f"Probe P4 is already installed ({receipt_path}); run uninstall first")

    ptxt = plugins_txt or _default_plugins_txt()
    orig_lines = ptxt.read_text(encoding="utf-8-sig").splitlines() if ptxt.is_file() else []

    backup_dir = stage_dir / "backup_pre_p4"
    if backup_dir.exists() and any(backup_dir.iterdir()):
        raise ProbeP4Error(f"non-empty backup directory exists: {backup_dir}; inspect or uninstall first")
    backup_dir.mkdir(parents=True, exist_ok=True)

    swapped_esms: Dict[str, dict] = {}
    added_data_files: List[dict] = []
    added_root_bats: List[dict] = []

    try:
        # 1. Back up & copy (NEVER hardlink!) FO4SFCoreValues.esm & FO4SFNewGame.esm
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

        # 2. Install FO4SF_R11P4Pistol.esm (shutil.copy2) + Main.ba2 & Textures.ba2 (link or copy)
        for fname in (PROBE_PLUGIN, PROBE_MAIN_BA2, PROBE_TEX_BA2):
            src = stage_dir / "exp" / fname
            dst = data_dir / fname
            _copy_or_link_ba2_only(src, dst)
            added_data_files.append({"name": dst.name, "sha256": sha256_file(dst)})

        # 3. Append *FO4SF_R11P4Pistol.esm to Plugins.txt & compute exact full-master load slot <XX>
        existing_low = {ln.strip().lstrip("*").casefold() for ln in orig_lines if ln.strip()}
        new_lines = list(orig_lines)
        appended_lines: List[str] = []
        if PROBE_PLUGIN.casefold() not in existing_low:
            line = f"*{PROBE_PLUGIN}"
            new_lines.append(line)
            appended_lines.append(line)

        slot_idx = compute_full_master_load_index(data_dir, new_lines, target_plugin=PROBE_PLUGIN)
        stamped_batches = build_p3_batch_scripts(quest_load_prefix=slot_idx)

        # 4. Write stamped P3 batch files into Starfield game root (shutil.copy2 / write_text, never linked)
        for fname, content in sorted(stamped_batches.items()):
            bdst = starfield_dir / fname
            if bdst.exists():
                raise ProbeP4Error(f"refusing to overwrite existing batch file: {bdst}")
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


def uninstall_probe_p4(starfield_dir: Path, plugins_txt: Optional[Path] = None) -> dict:
    """Reversibly remove Probe P4 and restore exact pre-probe FO4SFCoreValues.esm, FO4SFNewGame.esm, and Plugins.txt."""
    check_starfield_not_running()
    data_dir = starfield_dir / "Data"
    receipt_path = data_dir / INSTALL_RECEIPT
    if not receipt_path.is_file():
        raise ProbeP4Error(f"Probe P4 is not installed ({receipt_path} not found)")

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    backup_dir = Path(receipt["backup_dir"])
    ptxt = plugins_txt or Path(receipt["plugins_txt"])

    for item in receipt["added_root_bats"]:
        p = starfield_dir / item["name"]
        if p.is_file():
            if sha256_file(p) != item["sha256"]:
                raise ProbeP4Error(f"refusing to delete modified batch file: {p}")
            p.unlink()

    for item in receipt["added_data_files"]:
        p = data_dir / item["name"]
        if p.is_file():
            if sha256_file(p) != item["sha256"]:
                raise ProbeP4Error(f"refusing to delete modified probe file: {p}")
            p.unlink()

    restored: Dict[str, Optional[str]] = {}
    for ename, info in receipt["swapped_esms"].items():
        live_dst = data_dir / ename
        if live_dst.is_file():
            if sha256_file(live_dst) != info["installed_sha256"]:
                raise ProbeP4Error(f"refusing to replace externally modified {live_dst}")
            live_dst.unlink()
        if info["had_previous"]:
            bfile = backup_dir / ename
            if not bfile.is_file():
                raise ProbeP4Error(f"missing backup file for rollback: {bfile}")
            shutil.move(str(bfile), str(live_dst))
            got_sha = sha256_file(live_dst)
            if got_sha != info["previous_sha256"]:
                raise ProbeP4Error(f"restored {ename} SHA-256 {got_sha} != {info['previous_sha256']}")
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


def status_probe_p4(starfield_dir: Path) -> dict:
    receipt_path = starfield_dir / "Data" / INSTALL_RECEIPT
    if not receipt_path.is_file():
        return {"installed": False}
    data = json.loads(receipt_path.read_text(encoding="utf-8"))
    return {"installed": True, "receipt": data}


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Round 11 Probe P4 (10mm Pistol ALONE) stager, verifier & installer")
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
        m = stage_probe_p4(
            out_dir=args.out_dir,
            fo4_data=args.fo4_data,
            starfield_dir=args.starfield,
            port_ids=args.port_ids,
            port_esm=args.port_esm,
            terrain_core_esm=args.terrain_core_esm,
            min_free_gb=args.min_free_gb,
        )
        print(f"staged {PROBE_NAME} -> {args.out_dir} ({len(m['files'])} files, free={m['disk_free_gb_after']} GiB)")
        print(f"rigid_parts_disclosure: {m['rigid_parts_disclosure']}")
        return 0
    if args.cmd == "verify":
        res = verify_probe_p4(args.stage_dir)
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0
    if args.cmd == "install":
        res = install_probe_p4(args.stage_dir, args.starfield, plugins_txt=args.plugins_txt, min_free_gb=args.min_free_gb)
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0
    if args.cmd == "uninstall":
        res = uninstall_probe_p4(args.starfield, plugins_txt=args.plugins_txt)
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0
    if args.cmd == "status":
        res = status_probe_p4(args.starfield)
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
