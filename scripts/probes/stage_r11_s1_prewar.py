"""Stage, verify, install, inspect, and uninstall the Round 13 S1 Pre-War probe (`r13-s1-prewar`).

Stacks cleanly on:
  - Task 1 Slot 1 `FO4Port.esm` -> Slot 2 lossless in-place append into `FO4Port_PrewarVault111` (`0x0100EDFB`, `427 temp REFR + 2 NAVM`) + Slot 1 BA2s
  - Task 4 `FO4SFHome.esm` + coordinated `PNDT 0x805` `FO4SFPrewar_Sanctuary_Home.esm` (`allow_prewar_home_pair=True`)
  - SanctuaryHillsWorld (`0x000A7FF4`) bounded pre-war strip (`4x4` SF tile, `.btd`, `59` NAVMs/`NAVI`, rigged `DOOR`s, self-owned `WTHR`/`CLMT`)
  - `#854` Mr. Handy Codsworth + local `WwiseConsole` `.fuz -> .wem` voices via `make_mission` helpers + 6 real `SCEN`s + 5 stand-in beats
  - Slot 3 `FO4SF_NewGameQuest.psc` + `FO4SFNewGame.esm` (`--prewar`, `--cog-door`, `--exit-lift`, `FadeHold=False`, backdrop `1`, preserving `fo4_vault111`)
  - `#860` rebuilt merged `FO4SFPipboyMenu.dll` + Stage=2 safe INI (`MapBlockStarMap=0`, `MapSurvival=0`)

Never launches Starfield/Creation Kit, never writes to Starfield\\Data during `stage`, never commits binary assets to Git,
and refuses frozen candidate/probe directories. All CLI external paths must be passed explicitly (`Task 8`: zero hardcoded drive paths).
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
SCRIPTS_DIR = REPO_ROOT / "scripts"
PROBES_DIR = SCRIPTS_DIR / "probes"
PREWAR_SCRIPTS_DIR = SCRIPTS_DIR / "prewar"
TERRAIN_SCRIPTS_DIR = SCRIPTS_DIR / "terrain"
UI_SCRIPTS_DIR = SCRIPTS_DIR / "ui"
NEWGAME_SCRIPTS_DIR = SCRIPTS_DIR / "newgame"
TESTING_SCRIPTS_DIR = SCRIPTS_DIR / "testing"
for _p in (SRC_DIR, PROBES_DIR, PREWAR_SCRIPTS_DIR, TERRAIN_SCRIPTS_DIR, UI_SCRIPTS_DIR, NEWGAME_SCRIPTS_DIR, TESTING_SCRIPTS_DIR):
    s = str(_p)
    if s not in sys.path:
        sys.path.insert(0, s)

import build_fo4port_r11_museum  # noqa: E402
import build_prewar_quest  # noqa: E402
import build_prewar_strip  # noqa: E402
import make_newgame  # noqa: E402
import make_pipboy_stage_ini  # noqa: E402
import make_r12_start_menus_probe  # noqa: E402
import probe_common  # noqa: E402
import r12_card_validator  # noqa: E402
from fo4sf import ba2 as ba2_mod, convert_static, exterior, fo4land, meshcollision, pipeline, sfcollision, sfnif  # noqa: E402
from fo4sf.core import start_places as sp  # noqa: E402
from fo4sf.core import warfare_starts as ws  # noqa: E402
from fo4sf.planet import census, esm, home_planet_spec as hspec  # noqa: E402
from fo4sf.prewar import mq101_census, s1_spec, sanctuary_strip, vault111_append  # noqa: E402

PROBE_ID = "r13-s1-prewar"
MANIFEST_NAME = "manifest.json"
MIN_FREE_GB = probe_common.DEFAULT_MIN_FREE_GB
MAX_AXIS_M = probe_common.DEFAULT_MAX_HOP_AXIS_M

# Task 8: Zero hardcoded external D:\ / C:\ defaults; external inputs must be passed explicitly on CLI.
DEFAULT_STARFIELD_DIR: Optional[Path] = None
DEFAULT_FO4_DATA_DIR: Optional[Path] = None
DEFAULT_BASELINE_DIR: Optional[Path] = None
DEFAULT_DOORS_ANIM_DIR: Optional[Path] = None
DEFAULT_INTERIORS_B10_DIR: Optional[Path] = None
DEFAULT_P1_PORT_DIR: Optional[Path] = None
DEFAULT_WHOME_DATA_DIR: Optional[Path] = None
DEFAULT_HANDY_STAGE_DIR: Optional[Path] = None
DEFAULT_TESTED_PIPBOY_DLL: Optional[Path] = None
DEFAULT_TEXCONV_EXE: Optional[Path] = None
DEFAULT_XWM_EXE: Optional[Path] = None
DEFAULT_WWISE_EXE: Optional[Path] = None
DEFAULT_PORT_IDS: Optional[Path] = None
DEFAULT_BASE_START_PLACES = REPO_ROOT / "src" / "fo4sf" / "core" / "start_places.json"
DEFAULT_WARFARE_STARTS = REPO_ROOT / "src" / "fo4sf" / "core" / "warfare_starts.json"
DEFAULT_CARD_PATH = REPO_ROOT / "docs" / "testing" / "round11-s1-prewar-card.md"

HERO_VERTIBIRD_MODEL = r"fo4core\vehicles\vertibird\vertibird01.nif"
HERO_EXT_LIFT_MODEL = r"fo4core\interiors\vault\rooms\vltelevator\vltelevatorexterior.nif"

PLUGINS_TO_ACTIVATE: Tuple[str, ...] = (
    "FO4Port.esm",
    "FO4TerrainCore.esm",
    "FO4TerrainCore_Mars.esm",
    "FO4SFCoreValues.esm",
    "FO4SFVaultGearDoor.esm",
    "FO4SFExitLift.esm",
    "FO4SFMission.esm",
    "FO4SFHome.esm",
    "FO4SFPrewar_Sanctuary.esm",
    "FO4SFPrewar_Sanctuary_Home.esm",
    "FO4SFPrewar.esm",
    "FO4SFNewGame.esm",
)

SWAP_ALLOWED_DATA_PREFIXES: Tuple[str, ...] = (
    "Data/FO4Port.esm",
    "Data/FO4Port - Main.ba2",
    "Data/FO4Port - Textures.ba2",
    "Data/FO4SFVaultGearDoor.esm",
    "Data/FO4SFExitLift.esm",
    "Data/FO4SFNewGame.esm",
    "Data/FO4SFNewGame - Main.ba2",
    "Data/Scripts/FO4SF_NewGame",
    "Data/SFSE/Plugins/",
)

S1_TILE = sanctuary_strip.strip_sf_tile()


def _sanc_local(key: str) -> Tuple[float, float, float]:
    px, py, pz = s1_spec.SANCTUARY_KEY_COORDS_M[key]
    lx, ly = S1_TILE.to_local(px, py)
    return round(lx, 2), round(ly, 2), round(pz, 2)


_ANC_HOUSE = _sanc_local("player_start")
_ANC_V111 = s1_spec.PREWAR_V111_KEY_COORDS_M["int_elevator_base"]
_HOP_BRIDGE = _sanc_local("west_bridge")
_HOP_GATE = _sanc_local("military_gate_checker")
_HOP_LIFT = _sanc_local("ext_elevator_center")
_HOP_POD = s1_spec.PREWAR_V111_KEY_COORDS_M["player_cryopod"]

S1_ANCHORS: Tuple[probe_common.AnchorPoint, ...] = (
    probe_common.AnchorPoint(
        name="sanctuary_house",
        x=_ANC_HOUSE[0],
        y=_ANC_HOUSE[1],
        z=_ANC_HOUSE[2],
        cell_type="exterior",
        cell="FO4SF_PrewarSanctuaryWorld",
    ),
    probe_common.AnchorPoint(
        name="prewar_vault111_entry",
        x=_ANC_V111[0],
        y=_ANC_V111[1],
        z=_ANC_V111[2],
        cell_type="interior",
        cell="FO4Port_PrewarVault111",
    ),
)

S1_HOPS: Tuple[probe_common.HopSpec, ...] = (
    probe_common.HopSpec(
        name="sanctuary_west_bridge",
        from_anchor="sanctuary_house",
        x=_HOP_BRIDGE[0],
        y=_HOP_BRIDGE[1],
        z=_HOP_BRIDGE[2],
        cell_type="exterior",
        cell="FO4SF_PrewarSanctuaryWorld",
    ),
    probe_common.HopSpec(
        name="military_gate_checker",
        from_anchor="sanctuary_house",
        x=_HOP_GATE[0],
        y=_HOP_GATE[1],
        z=_HOP_GATE[2],
        cell_type="exterior",
        cell="FO4SF_PrewarSanctuaryWorld",
    ),
    probe_common.HopSpec(
        name="ext_vault_elevator",
        from_anchor="sanctuary_house",
        x=_HOP_LIFT[0],
        y=_HOP_LIFT[1],
        z=_HOP_LIFT[2],
        cell_type="exterior",
        cell="FO4SF_PrewarSanctuaryWorld",
    ),
    probe_common.HopSpec(
        name="prewar_vault_player_pod",
        from_anchor="prewar_vault111_entry",
        x=_HOP_POD[0],
        y=_HOP_POD[1],
        z=_HOP_POD[2],
        cell_type="interior",
        cell="FO4Port_PrewarVault111",
    ),
)

P3_BATCHES: Tuple[Tuple[str, str], ...] = (
    (
        "s1a.txt",
        "; S1 Pre-War House arrival pos check (0 M/N/V)\n"
        "getpos x\n"
        "getpos y\n"
        "getpos z\n",
    ),
    (
        "s1b.txt",
        f"; S1 Pre-War West Bridge hop from House (<200m/axis, 0 M/N/V)\n"
        f"player.setpos x {_HOP_BRIDGE[0]:.2f}\n"
        f"player.setpos y {_HOP_BRIDGE[1]:.2f}\n"
        f"player.setpos z {_HOP_BRIDGE[2]:.2f}\n"
        "getpos x\ngetpos y\ngetpos z\n",
    ),
    (
        "s1c.txt",
        f"; S1 Pre-War Military Gate hop from House (<200m/axis, 0 M/N/V)\n"
        f"player.setpos x {_HOP_GATE[0]:.2f}\n"
        f"player.setpos y {_HOP_GATE[1]:.2f}\n"
        f"player.setpos z {_HOP_GATE[2]:.2f}\n"
        "getpos x\ngetpos y\ngetpos z\n",
    ),
    (
        "s1d.txt",
        f"; S1 Pre-War ExtVaultElevator pad hop from House (<200m/axis, 0 M/N/V)\n"
        f"player.setpos x {_HOP_LIFT[0]:.2f}\n"
        f"player.setpos y {_HOP_LIFT[1]:.2f}\n"
        f"player.setpos z {_HOP_LIFT[2]:.2f}\n"
        "getpos x\ngetpos y\ngetpos z\n",
    ),
    (
        "s1e.txt",
        f"; S1 FO4Port_PrewarVault111 interior pod hop (<200m/axis, 0 M/N/V)\n"
        f"player.setpos x {_HOP_POD[0]:.2f}\n"
        f"player.setpos y {_HOP_POD[1]:.2f}\n"
        f"player.setpos z {_HOP_POD[2]:.2f}\n"
        "getpos x\ngetpos y\ngetpos z\n",
    ),
)
P3_ACTIVATE_COMMANDS: Tuple[str, ...] = ("bat s1a", "bat s1b", "bat s1c", "bat s1d", "bat s1e")


def _copy_stage_file(src: Path, dst: Path) -> str:
    probe_common.copy_or_link_staged_file(src, dst, allow_hardlink=False)
    return probe_common.sha256_file(dst)


def _is_swap_allowed(target_rel: str) -> bool:
    return any(target_rel == pref or target_rel.startswith(pref) for pref in SWAP_ALLOWED_DATA_PREFIXES)


def build_s1_start_places_doc(base_start_places_path: Path) -> Dict[str, Any]:
    """Return a `start_places.json` copy enabling `fo4_prewar_sanctuary` while keeping `fo4_vault111` (Skip Pre-War)."""
    raw = json.loads(base_start_places_path.read_text(encoding="utf-8"))
    rows = copy.deepcopy(raw.get("places") or [])
    filtered = [r for r in rows if not (isinstance(r, dict) and r.get("id") == "fo4_prewar_sanctuary")]

    for row in filtered:
        if isinstance(row, dict) and row.get("id") == "fo4_vault111":
            row["name"] = "Vault 111 (Skip Pre-War)"

    prewar_row: Dict[str, Any] = {
        "id": "fo4_prewar_sanctuary",
        "mode": "story",
        "story_id": "fo4_commonwealth",
        "story_label": "Fallout 4: Commonwealth",
        "faction_slot": -1,
        "faction_label": "",
        "name": "Sanctuary Hills (Pre-War)",
        "space": "FO4SF_PrewarSanctuaryWorld",
        "is_interior": False,
        "plugin": "FO4SFPrewar.esm",
        "required_plugins": ["FO4SFPrewar_Sanctuary.esm", "FO4SFPrewar.esm"],
        "marker_edid": "FO4SF_PrewarHouseSpawnMarker",
        "anchor_edid": "FO4SF_PrewarHouseSpawnMarker",
        "pos": list(_ANC_HOUSE),
        "cell": [0, -1],
        "quests": ["FO4SF_PrewarQuest", "FO4SF_NewGame"],
        "quest_mask": 1,
        "warfare_key": "",
        "min_difficulty": 0,
        "max_difficulty": 3,
        "available": True,
        "unavailable_reason": "",
    }
    doc = {"schema_version": int(raw.get("schema_version", 1)), "places": [prewar_row, *filtered]}
    s1_spec.validate_start_places_preserves_skip_prewar(doc)
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as tf:
        json.dump(doc, tf, indent=2)
        tmp_path = tf.name
    try:
        sp.load_start_places(tmp_path, allow_story_ids=("fo4_prewar_sanctuary", "fo4_vault111"))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    return doc


def _pack_textures_ba2(
    dds_entries: Mapping[str, Path],
    out_ba2: Path,
    *,
    archive2_exe: Optional[Path] = None,
    fast_ba2: bool = False,
    scratch_parent: Path,
) -> Dict[str, str]:
    """Pack textures into DX10 BA2 using Archive2 (-format=DDS) when available, else probe_common.pack_dx10_ba2."""
    if not dds_entries:
        raise probe_common.ProbeValidationError(f"No .dds files to pack into {out_ba2.name}")
    if archive2_exe is not None and archive2_exe.is_file() and not fast_ba2:
        tex_stage = Path(tempfile.mkdtemp(prefix="r11_s1_a2tex_", dir=str(scratch_parent)))
        try:
            for norm_rel, src_p in dds_entries.items():
                dst_p = tex_stage / norm_rel
                dst_p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_p, dst_p)
            out_ba2.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="r11_s1_a2tmp_", dir=str(scratch_parent)) as tmp_out:
                fresh = Path(tmp_out) / out_ba2.name
                proc = subprocess.run(
                    [
                        str(archive2_exe),
                        "textures",
                        f"-create={fresh}",
                        f"-root={tex_stage}",
                        "-format=DDS",
                        "-compression=Default",
                    ],
                    cwd=str(tex_stage),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if proc.returncode == 0 and fresh.is_file() and fresh.stat().st_size >= 16:
                    os.replace(fresh, out_ba2)
                    return probe_common.verify_ba2_entry_hashes(out_ba2, source_files=dds_entries)
        finally:
            shutil.rmtree(tex_stage, ignore_errors=True)

    probe_common.pack_dx10_ba2(dds_entries, out_ba2, compress=False)
    return probe_common.verify_ba2_entry_hashes(out_ba2, source_files=dds_entries)


def _stage_slot2_port(
    *,
    work_dir: Path,
    data_out: Path,
    fo4_esm: Path,
    doors_anim_dir: Optional[Path],
    interiors_b10_dir: Optional[Path],
    p1_port_dir: Optional[Path],
    slot1_port_esm: Optional[Path],
    skip_port_ba2: bool,
) -> Dict[str, Any]:
    """Build or load Slot 1 FO4Port.esm and losslessly append Slot 2 into FO4Port_PrewarVault111 (`S1-08`)."""
    if slot1_port_esm is not None:
        if not slot1_port_esm.is_file():
            raise FileNotFoundError(f"Missing --slot1-port-esm: {slot1_port_esm}")
        s1_bytes = slot1_port_esm.read_bytes()
    else:
        if doors_anim_dir is None or interiors_b10_dir is None:
            raise ValueError("Missing --slot1-port-esm (or explicit --doors-anim-dir and --interiors-b10-dir)")
        for req in (doors_anim_dir / "FO4Port.esm", interiors_b10_dir / "FO4Port.esm", fo4_esm):
            if not req.is_file():
                raise FileNotFoundError(f"Missing Slot 1 FO4Port input: {req}")
        s1_dir = work_dir / "slot1_port"
        rc = build_fo4port_r11_museum.main(
            [
                "--base-dir",
                str(doors_anim_dir),
                "--source-dir",
                str(interiors_b10_dir),
                "--fo4-esm",
                str(fo4_esm),
                "--out-dir",
                str(s1_dir),
                "--esm-only",
                "--clean",
            ]
        )
        if rc != 0:
            raise RuntimeError(f"build_fo4port_r11_museum.py failed ({rc})")
        s1_bytes = (s1_dir / "FO4Port.esm").read_bytes()

    slot1_ref_dir = work_dir / "slot1_ref"
    slot1_ref_dir.mkdir(parents=True, exist_ok=True)
    slot1_work_esm = slot1_ref_dir / "FO4Port.esm"
    slot1_work_esm.write_bytes(s1_bytes)

    navms: Sequence[Tuple[int, bytes]] = ()
    if fo4_esm.is_file():
        v111_src = vault111_append.extract_prewar_v111_source(str(fo4_esm))
        navms = v111_src.get("navms") or ()

    s2_bytes, append_rep = vault111_append.append_prewar_vault111_lossless(
        s1_bytes,
        min_start_id=s1_spec.MIN_PREWAR_PORT_START_ID,
        fo4_navms=navms,
        new_cell_edid="FO4Port_PrewarVault111",
    )
    start_id_int = int(append_rep["start_id"], 16) if isinstance(append_rep["start_id"], str) else int(append_rep["start_id"])
    verify_rep = vault111_append.verify_lossless_append(
        s1_bytes,
        s2_bytes,
        start_id_int,
        allow_navi_update=bool(navms),
    )

    out_port_esm = data_out / "FO4Port.esm"
    out_port_esm.parent.mkdir(parents=True, exist_ok=True)
    out_port_esm.write_bytes(s2_bytes)

    ba2_info: Dict[str, Any] = {}
    if not skip_port_ba2:
        if p1_port_dir is None:
            raise ValueError("Missing --p1-port-dir (required unless --skip-port-ba2 is passed)")
        for ba2_name in ("FO4Port - Main.ba2", "FO4Port - Textures.ba2"):
            src_ba2 = p1_port_dir / ba2_name
            if not src_ba2.is_file():
                raise FileNotFoundError(f"Missing Slot 1 archive: {src_ba2}")
            dst_ba2 = data_out / ba2_name
            ba2_info[ba2_name] = _copy_stage_file(src_ba2, dst_ba2)

    return {
        "slot1_sha256": probe_common.sha256_bytes(s1_bytes),
        "slot2_sha256": probe_common.sha256_bytes(s2_bytes),
        "slot2_bytes": len(s2_bytes),
        "slot1_work_esm": slot1_work_esm,
        "append_report": {k: v for k, v in append_rep.items() if k != "out_sha256"},
        "verify_report": verify_rep,
        "ba2_sha256": ba2_info,
    }


def _stage_home_host(*, whome_data_dir: Optional[Path], data_out: Path) -> Dict[str, Any]:
    """Copy Task 4 FO4SFHome host ESM, archives, and dual Earth biome maps; detect optional FO4TerrainCore_Home.esm."""
    if whome_data_dir is None:
        raise ValueError("Missing --whome-data-dir")
    required_files = (
        hspec.HOME_MASTER,
        "FO4SFHome - Main.ba2",
        "FO4SFHome - Textures.ba2",
        f"PlanetData/BiomeMaps/{hspec.DEFAULT_BODY_NAME}.biom",
        f"PlanetData/BiomeMaps/fo4sfhome.esm/{hspec.DEFAULT_BODY_NAME}.biom",
    )
    copied: Dict[str, str] = {}
    for rel in required_files:
        src = whome_data_dir / Path(rel)
        if not src.is_file():
            raise FileNotFoundError(f"Missing FO4SFHome asset in {whome_data_dir}: {rel}")
        dst = data_out / Path(rel)
        copied[rel] = _copy_stage_file(src, dst)
    home_reg = whome_data_dir / hspec.HOME_REGISTRATION
    return {
        "files": copied,
        "home_reg_src": home_reg if home_reg.is_file() else None,
    }


def _rig_sanctuary_doors(
    *,
    fo4_data: Path,
    starfield_dir: Path,
    texconv_exe: Path,
    content_res: Path,
    conv_work: Path,
) -> Tuple[Dict[str, dict], Dict[str, Path]]:
    """Rig Sanctuary strip FO4 DOOR meshes (`S1-14`) into `door_manifest` and preconverted `.nif` entries."""
    fo4_esm_path = fo4_data / "Fallout4.esm"
    strip = sanctuary_strip.extract_strip_from_plugin(fo4land.Plugin(str(fo4_esm_path)))
    door_models: Dict[str, str] = {}
    for b in strip["bases"].values():
        if b.get("sig") != "DOOR":
            continue
        raw_m = str(b.get("model") or "").strip()
        if not raw_m or "autoload" in raw_m.lower():
            continue
        src_key = exterior.source_key(raw_m).replace("\\", "/").lower()
        sf_rel = "fo4core/" + src_key.removeprefix("meshes/")
        door_models.setdefault(src_key, f"meshes/{sf_rel}")

    sf_m01 = ba2_mod.Ba2(str(starfield_dir / "Data" / "Starfield - Meshes01.ba2"))
    ct = convert_static.collision_template_from_nif(
        sf_m01.read(sf_m01.find("meshes/architecture/city/akila/unique/crates/ak_crate_wall_latch02.nif"))
    )
    uc = meshcollision.template_from_nif(sf_m01.read(sf_m01.find(meshcollision.TEMPLATE_NIF)))
    door_donor = sfcollision.physics_blob_from_nif(sf_m01.read(sf_m01.find(sfnif.DOOR_TEMPLATE["nif"])))

    src = pipeline.Fo4Archives(str(fo4_data))
    conv = pipeline.Converter(
        src,
        str(conv_work),
        str(texconv_exe),
        str(content_res),
        collision_template=ct,
        sf_mesh_template=uc,
        prefix="fo4prewar",
        spec_mask_roughness=True,
        rig_doors=True,
        door_physics_donor=door_donor,
    )

    door_manifest: Dict[str, dict] = {}
    door_nifs: Dict[str, Path] = {}
    for src_key, sf_mesh_rel in sorted(door_models.items()):
        res = conv.convert_nif(src_key.replace("/", "\\"))
        if not res.get("ok"):
            continue
        produced_nif = conv_work / "meshes" / f"{res['out_name']}.nif"
        if not produced_nif.is_file():
            continue
        door_nifs[sf_mesh_rel.lower()] = produced_nif
        if isinstance(res.get("door"), dict):
            door_manifest[src_key] = res["door"]
    return door_manifest, door_nifs


def _convert_strip_delta_assets(
    *,
    objects_json_path: Path,
    fo4_data: Path,
    starfield_dir: Path,
    baseline_data_dir: Optional[Path],
    texconv_exe: Path,
    content_res: Path,
    conv_work: Path,
    preconverted_door_nifs: Optional[Mapping[str, Path]] = None,
) -> Tuple[Dict[str, Path], Dict[str, Path], Dict[str, Any]]:
    """Convert missing Sanctuary strip NIFs with prefix='fo4prewar' and remap .nif output to meshes/fo4core/..."""
    objs = json.loads(objects_json_path.read_text(encoding="utf-8"))
    bases = objs.get("bases") or []
    pre_doors = {k.lower(): v for k, v in (preconverted_door_nifs or {}).items()}

    delta_models: List[str] = []
    seen_models: set[str] = set()
    existing_in_baseline = 0
    for b in bases:
        model = str(b.get("model", "")).replace("\\", "/").lstrip("/")
        if not model:
            continue
        low = model.lower()
        if low in seen_models:
            continue
        seen_models.add(low)
        if f"meshes/{low}" in pre_doors:
            continue
        cand_base = (baseline_data_dir / "meshes" / model) if baseline_data_dir is not None else None
        if cand_base is not None and cand_base.is_file():
            existing_in_baseline += 1
        else:
            delta_models.append(model)

    for hero_rel in (HERO_VERTIBIRD_MODEL, HERO_EXT_LIFT_MODEL):
        hero_norm = hero_rel.replace("\\", "/").lstrip("/")
        cand_hero = (baseline_data_dir / "meshes" / hero_norm) if baseline_data_dir is not None else None
        if hero_norm.lower() not in seen_models and not (cand_hero is not None and cand_hero.is_file()):
            seen_models.add(hero_norm.lower())
            delta_models.append(hero_norm)

    sf_m01 = ba2_mod.Ba2(str(starfield_dir / "Data" / "Starfield - Meshes01.ba2"))
    ct_bytes = sf_m01.read(sf_m01.find("meshes/architecture/city/akila/unique/crates/ak_crate_wall_latch02.nif"))
    ct = convert_static.collision_template_from_nif(ct_bytes)
    uc_bytes = sf_m01.read(sf_m01.find(meshcollision.TEMPLATE_NIF))
    uc = meshcollision.template_from_nif(uc_bytes)

    src = pipeline.Fo4Archives(str(fo4_data))
    conv = pipeline.Converter(
        src,
        str(conv_work),
        str(texconv_exe),
        str(content_res),
        collision_template=ct,
        sf_mesh_template=uc,
        prefix="fo4prewar",
        spec_mask_roughness=True,
    )

    ok_count = 0
    effect_skipped: List[str] = []
    failed: List[Dict[str, str]] = []
    nif_entries: Dict[str, Path] = dict(pre_doors)

    for model in sorted(delta_models):
        fo4_rel = "meshes/" + (model[len("fo4core/") :] if model.lower().startswith("fo4core/") else model)
        fo4_bs = fo4_rel.replace("/", "\\")
        res = conv.convert_nif(fo4_bs)
        if res.get("ok"):
            ok_count += 1
            produced_nif = conv_work / "meshes" / f"{res['out_name']}.nif"
            if not produced_nif.is_file():
                raise FileNotFoundError(f"Expected converted NIF missing: {produced_nif}")
            nif_entries[f"meshes/{model.lower()}"] = produced_nif
        else:
            reason = str(res.get("reason", ""))
            if "only effect-shader shapes" in reason or "no static BSTriShape geometry" in reason:
                effect_skipped.append(f"{model}: {reason}")
            else:
                failed.append({"model": model, "reason": reason})

    if failed:
        raise RuntimeError(f"Sanctuary delta NIF conversion errors ({len(failed)}): {failed[:5]}")

    main_entries: Dict[str, Path] = dict(nif_entries)
    tex_entries: Dict[str, Path] = {}
    for dir_name in ("geometries", "materials"):
        root_sub = conv_work / dir_name
        if root_sub.is_dir():
            for p in sorted(root_sub.rglob("*")):
                if p.is_file():
                    rel = p.relative_to(conv_work).as_posix().lower()
                    main_entries[rel] = p
    tex_root = conv_work / "textures"
    if tex_root.is_dir():
        for p in sorted(tex_root.rglob("*")):
            if p.is_file():
                rel = p.relative_to(conv_work).as_posix().lower()
                tex_entries[rel] = p

    summary = {
        "total_distinct_bases": len(bases),
        "reused_from_baseline": existing_in_baseline,
        "rigged_door_nifs": len(pre_doors),
        "delta_requested": len(delta_models),
        "delta_converted_ok": ok_count,
        "effect_or_empty_skipped": effect_skipped,
        "converter_stats": conv.stats,
        "main_entries_count": len(main_entries),
        "tex_entries_count": len(tex_entries),
    }
    return main_entries, tex_entries, summary


def _count_records_in_groups(plg: esm.Plugin, target_sig: bytes, search_groups: Sequence[str]) -> int:
    """Count records matching `target_sig` across top-level and nested child GRUPs (e.g., NAVM under WRLD, SCEN under QUST)."""
    total = 0
    seen_groups = set()
    for gname in search_groups:
        if gname in seen_groups:
            continue
        seen_groups.add(gname)
        for s, e in plg.groups.get(gname, ()):
            for item in plg.walk(s, e):
                if item[0] == "REC" and plg.record_at(item[1]).sig == target_sig:
                    total += 1
    return total


def _stage_sanctuary_world(
    *,
    work_dir: Path,
    data_out: Path,
    fo4_data: Path,
    starfield_dir: Path,
    baseline_dir: Optional[Path],
    strip_dir_override: Optional[Path],
    home_reg_path: Optional[Path],
    texconv_exe: Optional[Path],
    content_res: Path,
    archive2_exe: Optional[Path],
    skip_strip_assets: bool,
    fast_ba2: bool,
) -> Dict[str, Any]:
    """Build FO4SFPrewar_Sanctuary.esm (NAVM/DOOR/WTHR/CLMT) + coordinated FO4SFPrewar_Sanctuary_Home.esm + BA2s."""
    door_manifest: Dict[str, dict] = {}
    pre_door_nifs: Dict[str, Path] = {}
    conv_work = work_dir / "sanctuary_conv"

    if strip_dir_override is not None:
        strip_src = Path(strip_dir_override)
    else:
        strip_src = work_dir / "sanctuary_strip"
        if not skip_strip_assets:
            if texconv_exe is None:
                raise ValueError("Missing --texconv (required unless --skip-strip-assets or --strip-dir is passed)")
            conv_work.mkdir(parents=True, exist_ok=True)
            door_manifest, pre_door_nifs = _rig_sanctuary_doors(
                fo4_data=fo4_data,
                starfield_dir=starfield_dir,
                texconv_exe=texconv_exe,
                content_res=content_res,
                conv_work=conv_work,
            )

        strip_args = [
            "--fo4-esm",
            str(fo4_data / "Fallout4.esm"),
            "--out-dir",
            str(strip_src),
            "--starfield-esm",
            str(starfield_dir / "Data" / "Starfield.esm"),
            "--host-esm-dir",
            str(data_out),
            "--run-overlays",
            "--report-json",
            str(strip_src / "strip_report.json"),
        ]
        if door_manifest:
            dm_path = work_dir / "door_manifest.json"
            dm_path.write_text(json.dumps(door_manifest, indent=2) + "\n", encoding="utf-8")
            strip_args.extend(["--door-manifest", str(dm_path)])
        if home_reg_path is not None and home_reg_path.is_file():
            strip_args.extend(["--combine-home-reg", str(home_reg_path)])
        rc = build_prewar_strip.main(strip_args)
        if rc != 0:
            raise RuntimeError(f"build_prewar_strip.py failed ({rc})")

    sanc_esm_src = strip_src / s1_spec.PLUGIN_PREWAR_WORLD
    reg_esm_src = strip_src / hspec.PREWAR_HOME_REGISTRATION
    btd_src = strip_src / "Data" / "Terrain" / "FO4SF_PrewarSanctuaryWorld.btd"
    mask_src = strip_src / "Data" / "textures" / "terrain" / "overlaymasks" / "fo4sf_prewarsanctuaryworld.dds"
    for req in (sanc_esm_src, reg_esm_src, btd_src, mask_src):
        if not req.is_file():
            raise FileNotFoundError(f"Missing Sanctuary strip output: {req}")

    sanctuary_strip.verify_zero_starfield_sky_refs(str(sanc_esm_src))
    sanc_sha = _copy_stage_file(sanc_esm_src, data_out / s1_spec.PLUGIN_PREWAR_WORLD)
    reg_sha = _copy_stage_file(reg_esm_src, data_out / hspec.PREWAR_HOME_REGISTRATION)
    btd_sha = _copy_stage_file(btd_src, data_out / "Terrain" / "FO4SF_PrewarSanctuaryWorld.btd")

    with esm.Plugin(str(data_out / s1_spec.PLUGIN_PREWAR_WORLD)) as sp_plg:
        navm_count = _count_records_in_groups(sp_plg, b"NAVM", ("WRLD", "NAVM"))
        door_count = sum(1 for _ in sp_plg.records("DOOR", [b"DOOR"]))
        wthr_count = sum(1 for _ in sp_plg.records("WTHR", [b"WTHR"]))
        clmt_count = sum(1 for _ in sp_plg.records("CLMT", [b"CLMT"]))

    main_entries: Dict[str, Path] = {}
    tex_entries: Dict[str, Path] = {"textures/terrain/overlaymasks/fo4sf_prewarsanctuaryworld.dds": mask_src}
    conv_summary: Dict[str, Any] = {"skipped": bool(skip_strip_assets)}

    if not skip_strip_assets:
        if texconv_exe is None:
            raise ValueError("Missing --texconv (required unless --skip-strip-assets is passed)")
        conv_work.mkdir(parents=True, exist_ok=True)
        base_data = (
            (baseline_dir / "player" / "Data")
            if (baseline_dir is not None and (baseline_dir / "player" / "Data").is_dir())
            else ((baseline_dir / "Data") if baseline_dir is not None else None)
        )
        main_entries, delta_tex, conv_summary = _convert_strip_delta_assets(
            objects_json_path=strip_src / "objects.json",
            fo4_data=fo4_data,
            starfield_dir=starfield_dir,
            baseline_data_dir=base_data,
            texconv_exe=texconv_exe,
            content_res=content_res,
            conv_work=conv_work,
            preconverted_door_nifs=pre_door_nifs,
        )
        tex_entries.update(delta_tex)
    else:
        dummy_mat = work_dir / "dummy_sanctuary.mat"
        dummy_mat.write_text('{"Version": 1, "Comment": "synthetic unit test strip placeholder"}\n', encoding="utf-8")
        main_entries["materials/fo4prewar/_synthetic_placeholder.mat"] = dummy_mat

    main_ba2 = data_out / "FO4SFPrewar_Sanctuary - Main.ba2"
    probe_common.pack_gnrl_ba2(main_entries, main_ba2, compress=True)
    main_hashes = probe_common.verify_ba2_entry_hashes(main_ba2, source_files=main_entries)

    tex_ba2 = data_out / "FO4SFPrewar_Sanctuary - Textures.ba2"
    tex_hashes = _pack_textures_ba2(
        tex_entries,
        tex_ba2,
        archive2_exe=archive2_exe,
        fast_ba2=fast_ba2,
        scratch_parent=work_dir,
    )

    return {
        "sanctuary_esm_sha256": sanc_sha,
        "sanctuary_home_reg_sha256": reg_sha,
        "btd_sha256": btd_sha,
        "btd_bytes": (data_out / "Terrain" / "FO4SF_PrewarSanctuaryWorld.btd").stat().st_size,
        "navm_count": navm_count,
        "door_count": door_count,
        "wthr_count": wthr_count,
        "clmt_count": clmt_count,
        "combined_home_reg": bool(home_reg_path is not None and home_reg_path.is_file()),
        "sanctuary_main_ba2_sha256": probe_common.sha256_file(main_ba2),
        "sanctuary_main_ba2_entries": main_hashes,
        "sanctuary_textures_ba2_sha256": probe_common.sha256_file(tex_ba2),
        "sanctuary_textures_ba2_entries": tex_hashes,
        "conversion_summary": conv_summary,
    }


def _inspect_newgame_vmad_scalars(ng_esm_path: Path) -> Dict[str, Any]:
    """Read `FO4SF_NewGameQuest` scalar VMAD properties (`LiftId`, `LiftBaseId`, `CogDoorId`, `FadeHold`, `StartChoiceBackdrop`)."""
    scalars: Dict[str, Any] = {}
    with esm.Plugin(str(ng_esm_path)) as plg:
        for rec in plg.records("QUST", [b"QUST"]):
            if (rec.formid & 0xFFFFFF) != 0x800:
                continue
            vmad = rec.get(b"VMAD")
            if not vmad or len(vmad) < 6:
                break
            _ver, obj_fmt, sc_cnt = struct.unpack_from("<HHH", vmad, 0)
            p = 6

            def _skip_elem(t: int) -> Any:
                nonlocal p
                if t == 1:
                    p += 8
                    return None
                if t == 2:
                    sl = struct.unpack_from("<H", vmad, p)[0]
                    val = vmad[p + 2 : p + 2 + sl].decode("cp1252", "replace")
                    p += 2 + sl
                    return val
                if t == 3:
                    val = struct.unpack_from("<i", vmad, p)[0]
                    p += 4
                    return val
                if t == 4:
                    val = struct.unpack_from("<f", vmad, p)[0]
                    p += 4
                    return val
                if t == 5:
                    val = bool(vmad[p])
                    p += 1
                    return val
                raise ValueError(f"Unsupported VMAD scalar type {t}")

            for _ in range(sc_cnt):
                sl = struct.unpack_from("<H", vmad, p)[0]
                p += 2 + sl + 1
                pr_cnt = struct.unpack_from("<H", vmad, p)[0]
                p += 2
                for _ in range(pr_cnt):
                    pl = struct.unpack_from("<H", vmad, p)[0]
                    pname = vmad[p + 2 : p + 2 + pl].decode("cp1252", "replace")
                    p += 2 + pl
                    pt, _st = struct.unpack_from("<BB", vmad, p)
                    p += 2
                    if 1 <= pt <= 5:
                        val = _skip_elem(pt)
                        if pt in (2, 3, 4, 5):
                            scalars[pname] = val
                    elif 11 <= pt <= 15:
                        arr_len = struct.unpack_from("<I", vmad, p)[0]
                        p += 4
                        for _ in range(arr_len):
                            _skip_elem(pt - 10)
            break
    return scalars


def _stage_prewar_quest_and_voices(
    *,
    work_dir: Path,
    data_out: Path,
    fo4_data: Path,
    starfield_esm: Path,
    handy_stage_dir: Optional[Path],
    xwm_exe: Optional[Path],
    wwise_exe: Optional[Path],
    papyrus_compiler: Path,
    content_res: Path,
    prewar_dir_override: Optional[Path],
    skip_voices: bool,
) -> Dict[str, Any]:
    """Convert wired S1 .fuz -> .wem via `make_mission` helpers (`S1-01`/`S1-16`), build FO4SFPrewar.esm + Main BA2."""
    if prewar_dir_override is not None:
        pq_work = Path(prewar_dir_override)
        voice_summary: Dict[str, Any] = {"skipped": True, "wired_wem_count": 0}
    else:
        if handy_stage_dir is None:
            raise ValueError("Missing --handy-stage-dir (required unless --prewar-dir is passed)")
        pq_work = work_dir / "prewar_quest"
        pq_work.mkdir(parents=True, exist_ok=True)
        fo4_esm = fo4_data / "Fallout4.esm"
        fo4_voices = fo4_data / "Fallout4 - Voices.ba2"
        voices_json_path: Optional[Path] = None

        voice_summary = {"skipped": bool(skip_voices), "wired_wem_count": 0}
        if not skip_voices:
            if xwm_exe is None or wwise_exe is None:
                raise ValueError("Missing --xwmaencode / --wwise-console (required unless --skip-voices is passed)")
            for req in (fo4_esm, fo4_voices, xwm_exe, wwise_exe):
                if not req.is_file():
                    raise FileNotFoundError(f"Missing MQ101 voice conversion input: {req}")
            wired_stems = list(
                dict.fromkeys(
                    mq101_census.curated_prewar_scene_stems()
                    + mq101_census.kellogg_scene_stems(str(fo4_esm), str(fo4_voices))
                )
            )
            vscratch = work_dir / "voice_scratch"
            durations: Dict[str, float] = {}
            stem_to_wem = mq101_census.convert_stems_via_wwise(
                str(fo4_voices),
                wired_stems,
                str(xwm_exe),
                str(wwise_exe),
                str(vscratch),
                durations_out=durations,
            )
            voice_out_dir = pq_work / "Data" / "sound" / "voice" / "fo4sfprewar.esm"
            payload, wired_copied = mq101_census.build_local_prewar_scenes_payload(
                str(fo4_esm),
                durations,
                str(voice_out_dir),
                stem_to_wem,
            )
            voices_json_path = work_dir / "voices_local.json"
            voices_json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            voice_summary = {
                "skipped": False,
                "wired_stem_count": len(wired_stems),
                "converted_wem_count": len(stem_to_wem),
                "wired_wem_count": len(wired_copied),
                "scene_counts": {k: len(v) for k, v in payload.items()},
                "pool_wem_count": 0,
            }

        q_cmd = [
            "--starfield-esm",
            str(starfield_esm),
            "--out-dir",
            str(pq_work),
            "--sanctuary-esm",
            str(data_out / s1_spec.PLUGIN_PREWAR_WORLD),
            "--port-esm",
            str(data_out / "FO4Port.esm"),
            "--codsworth-handy",
            str(handy_stage_dir),
            "--vertibird-model",
            HERO_VERTIBIRD_MODEL,
            "--ext-lift-model",
            HERO_EXT_LIFT_MODEL,
            "--compile-scripts",
            "--papyrus-compiler",
            str(papyrus_compiler),
            "--content-resources",
            str(content_res),
            "--report-json",
            str(pq_work / "prewar_build_report.json"),
        ]
        if voices_json_path is not None:
            q_cmd.extend(["--voices-json", str(voices_json_path)])
        rc = build_prewar_quest.main(q_cmd)
        if rc != 0:
            raise RuntimeError(f"build_prewar_quest.py failed ({rc})")

    prewar_esm_src = pq_work / s1_spec.PLUGIN_PREWAR
    if not prewar_esm_src.is_file():
        raise FileNotFoundError(f"Missing {s1_spec.PLUGIN_PREWAR} in {pq_work}")
    prewar_sha = _copy_stage_file(prewar_esm_src, data_out / s1_spec.PLUGIN_PREWAR)

    pq_data = pq_work / "Data"
    main_entries: Dict[str, Path] = {}
    tex_entries: Dict[str, Path] = {}
    if pq_data.is_dir():
        for src_p in sorted(pq_data.rglob("*")):
            if not src_p.is_file():
                continue
            rel = src_p.relative_to(pq_data).as_posix()
            rel_low = rel.lower()
            if rel_low.startswith("textures/") and rel_low.endswith(".dds"):
                tex_entries[rel_low] = src_p
            else:
                main_entries[rel] = src_p
                if rel_low.startswith("scripts/fo4sf_prewar") and rel_low.endswith(".pex"):
                    _copy_stage_file(src_p, data_out / Path(rel))

    if not any(k.lower().startswith("scripts/fo4sf_prewarquest.pex") for k in main_entries):
        raise probe_common.ProbeValidationError("Missing Scripts/FO4SF_PrewarQuest.pex in FO4SFPrewar stage")
    if not any(k.lower().startswith("scripts/fo4sf_prewarstandins.pex") for k in main_entries):
        raise probe_common.ProbeValidationError("Missing Scripts/FO4SF_PrewarStandIns.pex in FO4SFPrewar stage")

    prewar_main_ba2 = data_out / "FO4SFPrewar - Main.ba2"
    probe_common.pack_gnrl_ba2(main_entries, prewar_main_ba2, compress=True)
    main_hashes = probe_common.verify_ba2_entry_hashes(prewar_main_ba2, source_files=main_entries)

    tex_hashes: Dict[str, str] = {}
    if tex_entries:
        prewar_tex_ba2 = data_out / "FO4SFPrewar - Textures.ba2"
        probe_common.pack_dx10_ba2(tex_entries, prewar_tex_ba2, compress=False)
        tex_hashes = probe_common.verify_ba2_entry_hashes(prewar_tex_ba2, source_files=tex_entries)

    return {
        "prewar_esm_sha256": prewar_sha,
        "prewar_main_ba2_sha256": probe_common.sha256_file(prewar_main_ba2),
        "prewar_main_ba2_bytes": prewar_main_ba2.stat().st_size,
        "prewar_main_ba2_entries": main_hashes,
        "prewar_textures_ba2_entries": tex_hashes,
        "voice_summary": voice_summary,
    }


def _stage_newgame_and_ui(
    *,
    work_dir: Path,
    data_out: Path,
    starfield_dir: Path,
    baseline_dir: Optional[Path],
    fo4_data: Path,
    port_ids: Optional[Path],
    core_esm: Optional[Path],
    port_esm_for_newgame: Optional[Path],
    cog_door_dir: Optional[Path],
    exit_lift_dir: Optional[Path],
    newgame_stage_override: Optional[Path],
    pipboy_dll_override: Optional[Path],
    tested_pipboy_dll: Optional[Path],
    interface_dir: Optional[Path],
    base_start_places_path: Path,
    warfare_starts_path: Path,
) -> Dict[str, Any]:
    """Write S1 FO4SFStartPlaces.json, stage FO4SFNewGame (--cog-door/--exit-lift, FadeHold=False, backdrop 1), pack Main BA2, and reuse #860 DLL + INI."""
    sfse_out = data_out / "SFSE" / "Plugins"
    sfse_out.mkdir(parents=True, exist_ok=True)
    sp_dst = sfse_out / "FO4SFStartPlaces.json"
    ws_dst = sfse_out / "FO4SFWarfareStarts.json"

    s1_sp_doc = build_s1_start_places_doc(base_start_places_path)
    sp_dst.write_text(json.dumps(s1_sp_doc, indent=2) + "\n", encoding="utf-8", newline="\n")
    sp_sha = probe_common.sha256_file(sp_dst)
    ws_sha = _copy_stage_file(warfare_starts_path, ws_dst)

    if newgame_stage_override is not None:
        ng_stage = Path(newgame_stage_override)
    else:
        if port_ids is None or core_esm is None:
            raise ValueError("Building FO4SFNewGame.esm requires --port-ids and --core (or --baseline-dir / --newgame-stage)")
        ng_stage = work_dir / "newgame_stage"
        fo4_esm = fo4_data if fo4_data.is_file() else (fo4_data / "Fallout4.esm")
        ng_port = port_esm_for_newgame if port_esm_for_newgame is not None else (data_out / "FO4Port.esm")
        ng_cmd: List[str] = [
            "stage",
            "--out",
            str(ng_stage),
            "--fo4",
            str(fo4_esm),
            "--port",
            str(ng_port),
            "--port-ids",
            str(port_ids),
            "--core",
            str(core_esm),
            "--starfield",
            str(starfield_dir / "Data" / "Starfield.esm"),
            "--warfare-starts",
            str(ws_dst),
            "--start-places",
            str(sp_dst),
            "--prewar",
            str(data_out / s1_spec.PLUGIN_PREWAR),
            "--no-fade-hold",
            "--start-choice-backdrop",
            "empty_cell",
            "--show-unavailable-starts",
            "0",
        ]
        if cog_door_dir is not None and (cog_door_dir / "plan.json").is_file():
            ng_cmd.extend(["--cog-door", str(cog_door_dir)])
        if exit_lift_dir is not None and (exit_lift_dir / "plan.json").is_file():
            ng_cmd.extend(["--exit-lift", str(exit_lift_dir)])
        rc = make_newgame.main(ng_cmd)
        if rc != 0:
            raise RuntimeError(f"make_newgame.py stage failed ({rc})")

    ng_esm_src = ng_stage / "FO4SFNewGame.esm"
    if not ng_esm_src.is_file():
        raise FileNotFoundError(f"Missing FO4SFNewGame.esm in {ng_stage}")
    ng_esm_sha = _copy_stage_file(ng_esm_src, data_out / "FO4SFNewGame.esm")
    for extra_plugin in ("FO4SFVaultGearDoor.esm", "FO4SFExitLift.esm"):
        cand_ep = ng_stage / extra_plugin
        if cand_ep.is_file():
            _copy_stage_file(cand_ep, data_out / extra_plugin)

    ba2_sources: Dict[str, Path] = {}
    ng_data = ng_stage / "Data"
    if ng_data.is_dir():
        for src_p in sorted(ng_data.rglob("*")):
            if not src_p.is_file():
                continue
            rel = src_p.relative_to(ng_data).as_posix()
            rel_low = rel.lower()
            if (rel_low.startswith("scripts/fo4sf_newgame") and rel_low.endswith(".pex")) or rel_low.startswith(
                ("meshes/", "materials/", "geometries/")
            ):
                dst_p = data_out / Path(rel)
                _copy_stage_file(src_p, dst_p)
                ba2_sources[rel] = dst_p

    if not any(k.lower().startswith("scripts/fo4sf_newgame") for k in ba2_sources):
        raise probe_common.ProbeValidationError(f"Missing Scripts/FO4SF_NewGame*.pex in {ng_stage}")

    ng_ba2 = data_out / "FO4SFNewGame - Main.ba2"
    probe_common.pack_gnrl_ba2(ba2_sources, ng_ba2, compress=True)
    ng_ba2_hashes = probe_common.verify_ba2_entry_hashes(ng_ba2, source_files=ba2_sources)

    dll_res = make_r12_start_menus_probe._resolve_pipboy_dll(  # noqa: SLF001
        pipboy_dll_override=pipboy_dll_override,
        tested_pipboy_dll=tested_pipboy_dll,
        dst_path=sfse_out / "FO4SFPipboyMenu.dll",
        work_dir=work_dir,
    )
    if interface_dir is not None:
        resolved_iface = interface_dir
    elif baseline_dir is not None:
        cand_i = baseline_dir / "player" / "Data" / "Interface"
        resolved_iface = cand_i if cand_i.is_dir() else (baseline_dir / "Data" / "Interface")
    else:
        raise ValueError("Missing --interface-dir (required unless --baseline-dir is passed)")
    ini_dst = sfse_out / "FO4SFPipboyMenu.ini"
    make_r12_start_menus_probe._generate_pipboy_ini(  # noqa: SLF001
        interface_dir=resolved_iface,
        out_ini=ini_dst,
        show_unavailable_starts=0,
    )
    make_r12_start_menus_probe._validate_ini_defaults(ini_dst)  # noqa: SLF001
    vmad_scalars = _inspect_newgame_vmad_scalars(data_out / "FO4SFNewGame.esm")

    return {
        "newgame_esm_sha256": ng_esm_sha,
        "newgame_ba2_sha256": probe_common.sha256_file(ng_ba2),
        "newgame_ba2_entries": ng_ba2_hashes,
        "pipboy_dll_sha256": dll_res.bin_sha256,
        "pipboy_dll_reused": bool(dll_res.reused),
        "pipboy_source_hash": dll_res.src_hash,
        "pipboy_ini_sha256": probe_common.sha256_file(ini_dst),
        "start_places_sha256": sp_sha,
        "warfare_starts_sha256": ws_sha,
        "available_starts": [r["id"] for r in s1_sp_doc["places"] if r.get("available")],
        "cog_door_enabled": bool(cog_door_dir is not None and (cog_door_dir / "plan.json").is_file()),
        "exit_lift_enabled": bool(exit_lift_dir is not None and (exit_lift_dir / "plan.json").is_file()),
        "newgame_vmad_scalars": vmad_scalars,
    }


def stage_probe(
    *,
    out_dir: Path,
    starfield_dir: Optional[Path] = DEFAULT_STARFIELD_DIR,
    fo4_data: Optional[Path] = DEFAULT_FO4_DATA_DIR,
    baseline_dir: Optional[Path] = DEFAULT_BASELINE_DIR,
    doors_anim_dir: Optional[Path] = DEFAULT_DOORS_ANIM_DIR,
    interiors_b10_dir: Optional[Path] = DEFAULT_INTERIORS_B10_DIR,
    p1_port_dir: Optional[Path] = DEFAULT_P1_PORT_DIR,
    whome_data_dir: Optional[Path] = DEFAULT_WHOME_DATA_DIR,
    handy_stage_dir: Optional[Path] = DEFAULT_HANDY_STAGE_DIR,
    port_ids: Optional[Path] = None,
    core_esm: Optional[Path] = None,
    cog_door_dir: Optional[Path] = None,
    exit_lift_dir: Optional[Path] = None,
    interface_dir: Optional[Path] = None,
    pipboy_dll: Optional[Path] = None,
    tested_pipboy_dll: Optional[Path] = DEFAULT_TESTED_PIPBOY_DLL,
    base_start_places_path: Path = DEFAULT_BASE_START_PLACES,
    warfare_starts_path: Path = DEFAULT_WARFARE_STARTS,
    texconv_exe: Optional[Path] = DEFAULT_TEXCONV_EXE,
    xwm_exe: Optional[Path] = DEFAULT_XWM_EXE,
    wwise_exe: Optional[Path] = DEFAULT_WWISE_EXE,
    slot1_port_esm: Optional[Path] = None,
    combine_home_reg: Optional[Path] = None,
    strip_dir: Optional[Path] = None,
    prewar_dir: Optional[Path] = None,
    newgame_stage_dir: Optional[Path] = None,
    skip_port_ba2: bool = False,
    skip_strip_assets: bool = False,
    skip_voices: bool = False,
    fast_ba2: bool = False,
    clean: bool = False,
    min_free_gb: float = MIN_FREE_GB,
    system: Optional[Any] = None,
) -> Dict[str, Any]:
    """Build and offline-verify the complete Round 13 `r13-s1-prewar` staging folder."""
    if starfield_dir is None:
        raise ValueError("Missing required --starfield")
    if fo4_data is None:
        raise ValueError("Missing required --fo4")
    probe_common.check_starfield_not_running(system)
    out_p = Path(out_dir)
    probe_common.check_out_dir_safe(out_p, clean=clean)
    probe_common.check_free_space_gb(out_p.parent if out_p.parent.exists() else out_p, min_gb=min_free_gb)

    sf_dir = Path(starfield_dir)
    base_dir = Path(baseline_dir) if baseline_dir is not None else None

    def _pick_existing(*cands: Optional[Path]) -> Optional[Path]:
        for c in cands:
            if c is not None and c.exists():
                return c
        return None

    resolved_core = core_esm or _pick_existing(
        (base_dir / "player" / "FO4TerrainCore.esm") if base_dir else None,
        (base_dir / "FO4TerrainCore.esm") if base_dir else None,
        (base_dir / "clean-core-2g-fix2-player" / "FO4TerrainCore.esm") if base_dir else None,
    )
    resolved_port_ids = port_ids or _pick_existing(
        DEFAULT_PORT_IDS,
        (base_dir / "player" / "formids.json") if base_dir else None,
        (base_dir / "formids.json") if base_dir else None,
        (base_dir / "clean-core-2g-fix2-player" / "formids.json") if base_dir else None,
    )
    resolved_cog = cog_door_dir or (_pick_existing(base_dir / "stages" / "01-cog-door") if base_dir else None)
    resolved_lift = exit_lift_dir or (_pick_existing(base_dir / "stages" / "02-exit-lift") if base_dir else None)
    resolved_slot1_port = slot1_port_esm or (_pick_existing(base_dir / "port" / "FO4Port.esm") if base_dir else None)
    resolved_p1_port = p1_port_dir or (_pick_existing(base_dir / "port") if base_dir else None)

    starfield_esm = sf_dir / "Data" / "Starfield.esm"
    content_res = sf_dir / "Tools" / "ContentResources.zip"
    papyrus_compiler = sf_dir / "Tools" / "Papyrus Compiler" / "PapyrusCompiler.exe"
    archive2_exe = sf_dir / "Tools" / "Archive2" / "Archive2.exe"

    data_out = out_p / "Data"
    bat_out = out_p / "bat"
    for d in (data_out, data_out / "Scripts", data_out / "SFSE" / "Plugins", bat_out):
        d.mkdir(parents=True, exist_ok=True)

    work_parent = out_p.parent if out_p.parent.exists() else out_p
    with tempfile.TemporaryDirectory(prefix="r13_s1_work_", dir=str(work_parent)) as td:
        work_dir = Path(td)

        port_rep = _stage_slot2_port(
            work_dir=work_dir,
            data_out=data_out,
            fo4_esm=Path(fo4_data) / "Fallout4.esm",
            doors_anim_dir=Path(doors_anim_dir) if doors_anim_dir is not None else None,
            interiors_b10_dir=Path(interiors_b10_dir) if interiors_b10_dir is not None else None,
            p1_port_dir=Path(resolved_p1_port) if resolved_p1_port is not None else None,
            slot1_port_esm=resolved_slot1_port,
            skip_port_ba2=skip_port_ba2,
        )
        slot1_work_esm = port_rep.pop("slot1_work_esm")

        home_stage = _stage_home_host(
            whome_data_dir=Path(whome_data_dir) if whome_data_dir is not None else None,
            data_out=data_out,
        )
        home_rep = home_stage["files"]
        resolved_home_reg = combine_home_reg or home_stage.get("home_reg_src")

        sanc_rep = _stage_sanctuary_world(
            work_dir=work_dir,
            data_out=data_out,
            fo4_data=Path(fo4_data),
            starfield_dir=sf_dir,
            baseline_dir=base_dir,
            strip_dir_override=strip_dir,
            home_reg_path=resolved_home_reg,
            texconv_exe=Path(texconv_exe) if texconv_exe is not None else None,
            content_res=content_res,
            archive2_exe=archive2_exe,
            skip_strip_assets=skip_strip_assets,
            fast_ba2=fast_ba2,
        )
        prewar_rep = _stage_prewar_quest_and_voices(
            work_dir=work_dir,
            data_out=data_out,
            fo4_data=Path(fo4_data),
            starfield_esm=starfield_esm,
            handy_stage_dir=Path(handy_stage_dir) if handy_stage_dir is not None else None,
            xwm_exe=Path(xwm_exe) if xwm_exe is not None else None,
            wwise_exe=Path(wwise_exe) if wwise_exe is not None else None,
            papyrus_compiler=papyrus_compiler,
            content_res=content_res,
            prewar_dir_override=prewar_dir,
            skip_voices=skip_voices,
        )
        ng_rep = _stage_newgame_and_ui(
            work_dir=work_dir,
            data_out=data_out,
            starfield_dir=sf_dir,
            baseline_dir=base_dir,
            fo4_data=Path(fo4_data),
            port_ids=resolved_port_ids,
            core_esm=resolved_core,
            port_esm_for_newgame=slot1_work_esm,
            cog_door_dir=resolved_cog if resolved_cog is not None and resolved_cog.is_dir() else None,
            exit_lift_dir=resolved_lift if resolved_lift is not None and resolved_lift.is_dir() else None,
            newgame_stage_override=newgame_stage_dir,
            pipboy_dll_override=pipboy_dll,
            tested_pipboy_dll=Path(tested_pipboy_dll) if tested_pipboy_dll is not None else None,
            interface_dir=interface_dir,
            base_start_places_path=Path(base_start_places_path),
            warfare_starts_path=Path(warfare_starts_path),
        )

    batch_paths: List[Path] = []
    for fname, body in P3_BATCHES:
        bp = bat_out / fname
        bp.write_text(body, encoding="utf-8", newline="\n")
        batch_paths.append(bp)

    probe_common.validate_batches_and_hops(
        batch_files=batch_paths,
        activate_commands=P3_ACTIVATE_COMMANDS,
        anchors=S1_ANCHORS,
        hops=S1_HOPS,
        max_axis_m=MAX_AXIS_M,
        raise_on_error=True,
    )

    ref_esms = [
        p
        for p in (
            resolved_core if resolved_core is not None and resolved_core.is_file() else None,
            data_out / "FO4Port.esm",
            data_out / hspec.HOME_MASTER,
            data_out / s1_spec.PLUGIN_PREWAR_WORLD,
        )
        if p is not None and p.is_file()
    ]
    probe_common.scan_plugin_cleanliness(
        [data_out / s1_spec.PLUGIN_PREWAR, data_out / "FO4SFNewGame.esm"],
        reference_esms=ref_esms,
        raise_on_error=True,
    )
    make_r12_start_menus_probe._ensure_stage_clean_newgame_inputs(  # noqa: SLF001
        esm_path=data_out / "FO4SFNewGame.esm",
        reference_esms=ref_esms,
    )

    file_entries: List[Dict[str, Any]] = []
    for p in sorted(data_out.rglob("*")):
        if not p.is_file():
            continue
        if p.stat().st_nlink != 1:
            raise probe_common.ProbeValidationError(f"Refusing staged hardlink (st_nlink={p.stat().st_nlink}): {p}")
        rel_data = p.relative_to(data_out).as_posix()
        tgt_rel = f"Data/{rel_data}"
        file_entries.append(
            {
                "src_rel": tgt_rel,
                "target_rel": tgt_rel,
                "sha256": probe_common.sha256_file(p),
                "bytes": p.stat().st_size,
                "allow_swap": _is_swap_allowed(tgt_rel),
            }
        )
    for bp in sorted(batch_paths):
        file_entries.append(
            {
                "src_rel": f"bat/{bp.name}",
                "target_rel": bp.name,
                "sha256": probe_common.sha256_file(bp),
                "bytes": bp.stat().st_size,
                "allow_swap": False,
            }
        )

    manifest: Dict[str, Any] = {
        "schema": "fo4sf.r13_s1_prewar_manifest.v1",
        "probe_id": PROBE_ID,
        "plugins_to_activate": list(PLUGINS_TO_ACTIVATE),
        "available_starts": ng_rep["available_starts"],
        "port_slot2": port_rep,
        "home_host": home_rep,
        "sanctuary_world": sanc_rep,
        "prewar_quest": prewar_rep,
        "newgame_and_ui": ng_rep,
        "s1_anchors": {anc.name: {"x": anc.x, "y": anc.y, "z": anc.z, "cell": anc.cell} for anc in S1_ANCHORS},
        "files": file_entries,
    }
    (out_p / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def _scan_esm_player_full_names(esm_path: Path, *, min_local_fid: int = 0) -> List[str]:
    """Fail if any player-facing FULL subrecord starts with `'FO4SF '` or contains `'(Stand-In)'`."""
    errors: List[str] = []
    with esm.Plugin(str(esm_path)) as plg:
        for grp in plg.groups:
            for start, end in plg.groups[grp]:
                for item in plg.walk(start, end):
                    if item[0] != "REC":
                        continue
                    rec = plg.record_at(item[1])
                    if (rec.formid & 0xFFFFFF) < min_local_fid:
                        continue
                    full_b = rec.get(b"FULL")
                    if full_b:
                        txt = full_b.rstrip(b"\x00").decode("utf-8", errors="replace")
                        if txt.startswith("FO4SF ") or "(stand-in)" in txt.lower():
                            errors.append(f"{esm_path.name}:{rec.edid or hex(rec.formid)} FULL banned text: {txt!r}")
    return errors


def _verify_s1_fix_gates(data_out: Path, manifest: Mapping[str, Any]) -> Dict[str, Any]:
    """Verify S1-01..S1-16 invariants directly against staged ESMs and BA2 manifests."""
    errors: List[str] = []
    for pname in (
        s1_spec.PLUGIN_PREWAR,
        s1_spec.PLUGIN_PREWAR_WORLD,
        hspec.PREWAR_HOME_REGISTRATION,
        "FO4SFNewGame.esm",
        "FO4SFVaultGearDoor.esm",
        "FO4SFExitLift.esm",
    ):
        pp = data_out / pname
        if pp.is_file():
            errors.extend(_scan_esm_player_full_names(pp))
    port_p = data_out / "FO4Port.esm"
    if port_p.is_file():
        errors.extend(_scan_esm_player_full_names(port_p, min_local_fid=s1_spec.MIN_PREWAR_PORT_START_ID))
        with esm.Plugin(str(port_p)) as plg:
            cells = [c.edid for c in plg.records("CELL", [b"CELL"]) if c.edid and "prewarvault111" in c.edid.lower()]
            if cells != ["FO4Port_PrewarVault111"]:
                errors.append(f"S1-08: expected single reused ['FO4Port_PrewarVault111'], got {cells}")

    sanc_p = data_out / s1_spec.PLUGIN_PREWAR_WORLD
    sanc_rep = manifest.get("sanctuary_world") or {}
    if sanc_p.is_file():
        with esm.Plugin(str(sanc_p)) as plg:
            navms = _count_records_in_groups(plg, b"NAVM", ("WRLD", "NAVM"))
            navis = sum(1 for _ in plg.records("NAVI", [b"NAVI"]))
            doors = sum(1 for _ in plg.records("DOOR", [b"DOOR"]))
            sanc_ov_map = {w.edid: census.overlay_of(w) for w in census.worlds(plg)}
        if not (sanc_rep.get("conversion_summary") or {}).get("skipped"):
            if navms == 0 or navis == 0:
                errors.append(f"S1-04: FO4SFPrewar_Sanctuary.esm missing navmeshes/NAVI (NAVM={navms}, NAVI={navis})")
            if doors == 0:
                errors.append("S1-14: FO4SFPrewar_Sanctuary.esm has 0 rigged DOOR records")
    else:
        navms = navis = doors = 0
        sanc_ov_map = {}

    pw_p = data_out / s1_spec.PLUGIN_PREWAR
    pq_rep = manifest.get("prewar_quest") or {}
    if pw_p.is_file():
        with esm.Plugin(str(pw_p)) as plg:
            scen_cnt = _count_records_in_groups(plg, b"SCEN", ("QUST", "SCEN"))
            pw_ov_map = {w.edid: census.overlay_of(w) for w in census.worlds(plg)}
        for we, ov in pw_ov_map.items():
            master_ov = sanc_ov_map.get(we)
            if ov is None or ov[0] == 0 or ov[1] == 0:
                errors.append(f"S1-06: FO4SFPrewar.esm WRLD {we} dropped SNAM/PNAM overlay ({ov})")
            elif master_ov is not None and (ov[0], ov[1]) != (master_ov[0], master_ov[1]):
                errors.append(f"S1-06: FO4SFPrewar.esm WRLD {we} overlay {ov[:2]} != master {master_ov[:2]}")
        vs = pq_rep.get("voice_summary") or {}
        if not vs.get("skipped"):
            if scen_cnt < 6:
                errors.append(f"S1-01: expected >= 6 SCEN in FO4SFPrewar.esm, got {scen_cnt}")
            ba2_keys = sorted((pq_rep.get("prewar_main_ba2_entries") or {}).keys())
            wem_keys = [k for k in ba2_keys if k.lower().endswith(".wem")]
            if any("mq101_pool" in k.lower() for k in wem_keys):
                errors.append("S1-01: unreached mq101_pool .wem files leaked into FO4SFPrewar - Main.ba2")
            want_wems = int(vs.get("wired_wem_count") or 0)
            if want_wems == 0 or len(wem_keys) != want_wems:
                errors.append(f"S1-01/S1-16: wired BA2 .wem count {len(wem_keys)} != expected {want_wems}")

    ng_p = data_out / "FO4SFNewGame.esm"
    ng_rep = manifest.get("newgame_and_ui") or {}
    if ng_p.is_file() and (ng_rep.get("cog_door_enabled") or ng_rep.get("exit_lift_enabled")):
        vm = _inspect_newgame_vmad_scalars(ng_p)
        if ng_rep.get("cog_door_enabled") and int(vm.get("CogDoorId") or 0) <= 0:
            errors.append(f"S1-03: CogDoorId must be non-zero in FO4SFNewGame.esm, got {vm.get('CogDoorId')}")
        if ng_rep.get("exit_lift_enabled") and (int(vm.get("LiftId") or 0) <= 0 or int(vm.get("LiftBaseId") or 0) <= 0):
            errors.append(f"S1-03: LiftId/LiftBaseId must be non-zero, got LiftId={vm.get('LiftId')}, LiftBaseId={vm.get('LiftBaseId')}")
        if vm.get("FadeHold") is True:
            errors.append("S1-03: FO4SFNewGame FadeHold must be False")
        if vm.get("StartChoiceBackdrop") not in (None, 1):
            errors.append(f"S1-03: FO4SFNewGame StartChoiceBackdrop expected 1, got {vm.get('StartChoiceBackdrop')}")

    reg_p = data_out / hspec.PREWAR_HOME_REGISTRATION
    if reg_p.is_file() and sanc_rep.get("combined_home_reg"):
        with esm.Plugin(str(reg_p)) as plg:
            pndts = list(plg.records("PNDT", [b"PNDT"]))
            if not pndts:
                errors.append(f"S1-07: {reg_p.name} missing PNDT")
            else:
                rows = hspec.canonical_pndt_cnam_rows(plg, reg_p.name, pndts[0])
                if len(rows) < 2:
                    errors.append(f"S1-07: combined {reg_p.name} expected >= 2 world rows, got {len(rows)}")

    if errors:
        raise probe_common.ProbeValidationError("; ".join(errors))
    return {"navms": navms, "navis": navis, "doors": doors}


def verify_probe(
    *,
    stage_dir: Path,
    core_esm: Optional[Path] = None,
    card_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run all offline verification gates against an already-staged `r13-s1-prewar` folder."""
    st = Path(stage_dir)
    manifest_p = st / MANIFEST_NAME
    if not manifest_p.is_file():
        raise probe_common.ProbeValidationError(f"Missing probe manifest: {manifest_p}")
    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
    if manifest.get("probe_id") != PROBE_ID:
        raise probe_common.ProbeValidationError(f"Unexpected probe_id: {manifest.get('probe_id')!r} != {PROBE_ID!r}")

    files = manifest.get("files") or []
    if not files:
        raise probe_common.ProbeValidationError("Manifest contains 0 files")
    for entry in files:
        src_p = st / str(entry["src_rel"])
        if not src_p.is_file():
            raise probe_common.ProbeValidationError(f"Missing staged file: {entry['src_rel']}")
        if src_p.stat().st_nlink != 1:
            raise probe_common.ProbeValidationError(f"Hardlink forbidden in stage: {entry['src_rel']}")
        if probe_common.sha256_file(src_p) != entry["sha256"]:
            raise probe_common.ProbeValidationError(f"SHA-256 mismatch on {entry['src_rel']}")

    data_out = st / "Data"
    sanc_rep = manifest.get("sanctuary_world") or {}
    probe_common.verify_ba2_entry_hashes(
        data_out / "FO4SFPrewar_Sanctuary - Main.ba2",
        expected_hashes=sanc_rep.get("sanctuary_main_ba2_entries") or {},
    )
    probe_common.verify_ba2_entry_hashes(
        data_out / "FO4SFPrewar_Sanctuary - Textures.ba2",
        expected_hashes=sanc_rep.get("sanctuary_textures_ba2_entries") or {},
    )
    pq_rep = manifest.get("prewar_quest") or {}
    probe_common.verify_ba2_entry_hashes(
        data_out / "FO4SFPrewar - Main.ba2",
        expected_hashes=pq_rep.get("prewar_main_ba2_entries") or {},
    )
    ng_rep = manifest.get("newgame_and_ui") or {}
    probe_common.verify_ba2_entry_hashes(
        data_out / "FO4SFNewGame - Main.ba2",
        expected_hashes=ng_rep.get("newgame_ba2_entries") or {},
    )

    sanctuary_strip.verify_zero_starfield_sky_refs(str(data_out / s1_spec.PLUGIN_PREWAR_WORLD))
    sp_path = data_out / "SFSE" / "Plugins" / "FO4SFStartPlaces.json"
    ws_path = data_out / "SFSE" / "Plugins" / "FO4SFWarfareStarts.json"
    sp_doc = json.loads(sp_path.read_text(encoding="utf-8"))
    s1_spec.validate_start_places_preserves_skip_prewar(sp_doc)
    known_ext = None
    if core_esm is not None and core_esm.is_file():
        scan = make_r12_start_menus_probe._scan_core_places(core_esm, data_out / "FO4Port.esm")  # noqa: SLF001
        ext_set = set(scan["exterior_cells"]) if scan is not None else set()
        sanc_esm = data_out / s1_spec.PLUGIN_PREWAR_WORLD
        if sanc_esm.is_file():
            sanc_marks: set[str] = set()
            sanc_ints: set[str] = set()
            lc_mod_cells: set[Tuple[int, int]] = set()
            from fo4sf.launcher import launch_choices as _lc  # noqa: PLC0415

            _lc._scan_single_tes4_places(str(sanc_esm), sanc_marks, sanc_ints, lc_mod_cells)  # noqa: SLF001
            ext_set |= lc_mod_cells
        if ext_set:
            known_ext = ext_set
    sp.load_start_places(
        str(sp_path),
        available_only=False,
        known_exterior_cells=known_ext,
        allow_story_ids=("fo4_prewar_sanctuary", "fo4_vault111"),
    )
    ws.load_warfare_starts(
        str(ws_path),
        known_exterior_cells=known_ext,
    )
    make_r12_start_menus_probe._validate_ini_defaults(data_out / "SFSE" / "Plugins" / "FO4SFPipboyMenu.ini")  # noqa: SLF001

    ref_esms = [
        p
        for p in (
            core_esm if core_esm is not None and core_esm.is_file() else None,
            data_out / "FO4Port.esm",
            data_out / hspec.HOME_MASTER,
            data_out / s1_spec.PLUGIN_PREWAR_WORLD,
        )
        if p is not None and p.is_file()
    ]
    probe_common.scan_plugin_cleanliness(
        [data_out / s1_spec.PLUGIN_PREWAR, data_out / "FO4SFNewGame.esm"],
        reference_esms=ref_esms,
        raise_on_error=True,
    )
    probe_common.validate_batches_and_hops(
        batch_files=sorted((st / "bat").glob("*.txt")),
        activate_commands=P3_ACTIVATE_COMMANDS,
        anchors=S1_ANCHORS,
        hops=S1_HOPS,
        max_axis_m=MAX_AXIS_M,
        raise_on_error=True,
    )
    gate_stats = _verify_s1_fix_gates(data_out, manifest)

    card_validated = False
    if card_path is not None:
        errs = r12_card_validator.validate_r12_card_file(Path(card_path))
        if errs:
            raise probe_common.ProbeValidationError("; ".join(errs))
        card_validated = True

    return {
        "verified": True,
        "probe_id": PROBE_ID,
        "files_verified": len(files),
        "available_starts": manifest.get("available_starts") or [],
        "card_validated": card_validated,
        "s1_gates": gate_stats,
    }


def _assert_clean_plugins_txt(
    plugins_path: Path,
    *,
    stage_data_dir: Optional[Path] = None,
    starfield_data_dir: Optional[Path] = None,
) -> None:
    if not plugins_path.is_file():
        return
    active: List[str] = []
    for raw in plugins_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or not line.startswith("*"):
            continue
        pname = line.lstrip("*").strip()
        plow = pname.casefold()
        active.append(pname)
        if plow == "fo4sfrouteloot.esm":
            raise probe_common.ProbeInstallError(f"Active FO4SFRouteLoot.esm in {plugins_path} conflicts with direct Warfare starts")

    if any(p.casefold() == hspec.HOME_REGISTRATION.lower() for p in active):
        sanc_reg = (stage_data_dir / hspec.PREWAR_HOME_REGISTRATION) if stage_data_dir else None
        if sanc_reg is None or not sanc_reg.is_file():
            raise probe_common.ProbeInstallError(
                f"Active {hspec.HOME_REGISTRATION} conflicts with PNDT 0x805 unless paired with combined {hspec.PREWAR_HOME_REGISTRATION}"
            )
        home_reg_p = None
        for d in (starfield_data_dir, stage_data_dir):
            if d is not None and (d / hspec.HOME_REGISTRATION).is_file():
                home_reg_p = d / hspec.HOME_REGISTRATION
                break
        if home_reg_p is None:
            try:
                with esm.Plugin(str(sanc_reg)) as sp:
                    pndts = list(sp.records("PNDT", [b"PNDT"]))
                    rows = hspec.canonical_pndt_cnam_rows(sp, sanc_reg.name, pndts[0]) if pndts else []
            except Exception as exc:
                raise probe_common.ProbeInstallError(
                    f"Active {hspec.HOME_REGISTRATION} in {plugins_path} conflicts with unreadable {sanc_reg.name}: {exc}"
                ) from exc
            if len(rows) < 2:
                raise probe_common.ProbeInstallError(
                    f"Active {hspec.HOME_REGISTRATION} in {plugins_path} overrides EarthPlanetData PNDT 0x805 "
                    f"and staged {hspec.PREWAR_HOME_REGISTRATION} is not combined ({len(rows)} world(s))"
                )
        else:
            check_paths: List[str] = []
            for p in active:
                if p.casefold() == hspec.HOME_REGISTRATION.lower():
                    check_paths.append(str(home_reg_p))
                elif p.casefold() == hspec.HOME_MASTER.lower() and stage_data_dir and (stage_data_dir / hspec.HOME_MASTER).is_file():
                    check_paths.append(str(stage_data_dir / hspec.HOME_MASTER))
                elif p.casefold() == s1_spec.PLUGIN_PREWAR_WORLD.lower() and stage_data_dir and (stage_data_dir / s1_spec.PLUGIN_PREWAR_WORLD).is_file():
                    check_paths.append(str(stage_data_dir / s1_spec.PLUGIN_PREWAR_WORLD))
            if not any(p.casefold() == hspec.PREWAR_HOME_REGISTRATION.lower() for p in active):
                check_paths.append(str(sanc_reg))
            else:
                idx_hr = next(i for i, p in enumerate(active) if p.casefold() == hspec.HOME_REGISTRATION.lower())
                idx_pw = next(i for i, p in enumerate(active) if p.casefold() == hspec.PREWAR_HOME_REGISTRATION.lower())
                if idx_pw < idx_hr:
                    raise probe_common.ProbeInstallError(
                        f"{hspec.PREWAR_HOME_REGISTRATION} must load after {hspec.HOME_REGISTRATION} in {plugins_path}"
                    )
                check_paths.append(str(sanc_reg))
            probs = hspec.check_load_order_overrides(check_paths, allow_prewar_home_pair=True)
            if probs:
                raise probe_common.ProbeInstallError("; ".join(probs))


def install_probe_cmd(
    *,
    stage_dir: Path,
    starfield_dir: Path,
    plugins_txt: Optional[Path] = None,
    version_tag: str = "",
    card_path: Optional[Path] = None,
    allow_hardlink: bool = True,
    min_free_gb: float = MIN_FREE_GB,
    system: Optional[Any] = None,
) -> Dict[str, Any]:
    manifest = json.loads((Path(stage_dir) / MANIFEST_NAME).read_text(encoding="utf-8"))
    plg_path = probe_common._resolve_plugins_txt(Path(starfield_dir), plugins_txt)  # noqa: SLF001
    _assert_clean_plugins_txt(
        plg_path,
        stage_data_dir=Path(stage_dir) / "Data",
        starfield_data_dir=Path(starfield_dir) / "Data",
    )
    return probe_common.install_probe(
        probe_id=PROBE_ID,
        stage_dir=stage_dir,
        starfield_dir=starfield_dir,
        plugins_txt=plugins_txt,
        plugins_to_activate=manifest["plugins_to_activate"],
        files=manifest["files"],
        version_tag=version_tag,
        card_path=card_path,
        min_free_gb=min_free_gb,
        allow_hardlink=allow_hardlink,
        system=system,
    )


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Stage, verify, install, inspect, and uninstall r13-s1-prewar probe")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp_cmd = sub.add_parser("stage", help="Stage r13-s1-prewar probe into an external directory")
    sp_cmd.add_argument("--out", required=True)
    sp_cmd.add_argument("--starfield", required=True)
    sp_cmd.add_argument("--fo4", required=True)
    sp_cmd.add_argument("--baseline-dir", default="")
    sp_cmd.add_argument("--doors-anim-dir", default="")
    sp_cmd.add_argument("--interiors-b10-dir", default="")
    sp_cmd.add_argument("--p1-port-dir", default="")
    sp_cmd.add_argument("--whome-data-dir", required=True)
    sp_cmd.add_argument("--handy-stage-dir", default="")
    sp_cmd.add_argument("--port-ids", default="")
    sp_cmd.add_argument("--core", default="")
    sp_cmd.add_argument("--cog-door", default="")
    sp_cmd.add_argument("--exit-lift", default="")
    sp_cmd.add_argument("--interface-dir", default="")
    sp_cmd.add_argument("--pipboy-dll", default="")
    sp_cmd.add_argument("--tested-pipboy-dll", default="")
    sp_cmd.add_argument("--base-start-places", default=str(DEFAULT_BASE_START_PLACES))
    sp_cmd.add_argument("--warfare-starts", default=str(DEFAULT_WARFARE_STARTS))
    sp_cmd.add_argument("--texconv", default="")
    sp_cmd.add_argument("--xwmaencode", default="")
    sp_cmd.add_argument("--wwise-console", default="")
    sp_cmd.add_argument("--slot1-port-esm", default="")
    sp_cmd.add_argument("--combine-home-reg", default="")
    sp_cmd.add_argument("--strip-dir", default="")
    sp_cmd.add_argument("--prewar-dir", default="")
    sp_cmd.add_argument("--newgame-stage", default="")
    sp_cmd.add_argument("--skip-port-ba2", action="store_true")
    sp_cmd.add_argument("--skip-strip-assets", action="store_true")
    sp_cmd.add_argument("--skip-voices", action="store_true")
    sp_cmd.add_argument("--fast-ba2", action="store_true")
    sp_cmd.add_argument("--clean", action="store_true")
    sp_cmd.add_argument("--min-free-gb", type=float, default=MIN_FREE_GB)

    vr = sub.add_parser("verify", help="Verify an already-staged r13-s1-prewar folder")
    vr.add_argument("--stage-dir", required=True)
    vr.add_argument("--core", default="")
    vr.add_argument("--card", default="")

    ins = sub.add_parser("install", help="Atomically install r13-s1-prewar into Starfield (game closed)")
    ins.add_argument("--dir", required=True)
    ins.add_argument("--starfield", required=True)
    ins.add_argument("--plugins-txt", default="")
    ins.add_argument("--version-tag", default="")
    ins.add_argument("--card", default="")
    ins.add_argument("--no-hardlink", action="store_true")
    ins.add_argument("--min-free-gb", type=float, default=MIN_FREE_GB)

    st = sub.add_parser("status", help="Inspect installation status of r13-s1-prewar")
    st.add_argument("--starfield", required=True)

    un = sub.add_parser("uninstall", help="Atomically roll back r13-s1-prewar from Starfield (game closed)")
    un.add_argument("--starfield", required=True)
    un.add_argument("--min-free-gb", type=float, default=MIN_FREE_GB)
    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = build_parser()
    args = ap.parse_args(list(argv) if argv is not None else None)
    if args.cmd == "stage":
        man = stage_probe(
            out_dir=Path(args.out),
            starfield_dir=Path(args.starfield),
            fo4_data=Path(args.fo4),
            baseline_dir=Path(args.baseline_dir) if args.baseline_dir else None,
            doors_anim_dir=Path(args.doors_anim_dir) if args.doors_anim_dir else None,
            interiors_b10_dir=Path(args.interiors_b10_dir) if args.interiors_b10_dir else None,
            p1_port_dir=Path(args.p1_port_dir) if args.p1_port_dir else None,
            whome_data_dir=Path(args.whome_data_dir),
            handy_stage_dir=Path(args.handy_stage_dir) if args.handy_stage_dir else None,
            port_ids=Path(args.port_ids) if args.port_ids else None,
            core_esm=Path(args.core) if args.core else None,
            cog_door_dir=Path(args.cog_door) if args.cog_door else None,
            exit_lift_dir=Path(args.exit_lift) if args.exit_lift else None,
            interface_dir=Path(args.interface_dir) if args.interface_dir else None,
            pipboy_dll=Path(args.pipboy_dll) if args.pipboy_dll else None,
            tested_pipboy_dll=Path(args.tested_pipboy_dll) if args.tested_pipboy_dll else None,
            base_start_places_path=Path(args.base_start_places),
            warfare_starts_path=Path(args.warfare_starts),
            texconv_exe=Path(args.texconv) if args.texconv else None,
            xwm_exe=Path(args.xwmaencode) if args.xwmaencode else None,
            wwise_exe=Path(args.wwise_console) if args.wwise_console else None,
            slot1_port_esm=Path(args.slot1_port_esm) if args.slot1_port_esm else None,
            combine_home_reg=Path(args.combine_home_reg) if args.combine_home_reg else None,
            strip_dir=Path(args.strip_dir) if args.strip_dir else None,
            prewar_dir=Path(args.prewar_dir) if args.prewar_dir else None,
            newgame_stage_dir=Path(args.newgame_stage) if args.newgame_stage else None,
            skip_port_ba2=bool(args.skip_port_ba2),
            skip_strip_assets=bool(args.skip_strip_assets),
            skip_voices=bool(args.skip_voices),
            fast_ba2=bool(args.fast_ba2),
            clean=bool(args.clean),
            min_free_gb=float(args.min_free_gb),
        )
        print(
            f"staged {PROBE_ID} into {args.out}: files={len(man['files'])} "
            f"starts={man['available_starts']} plugins={man['plugins_to_activate']}"
        )
        return 0
    if args.cmd == "verify":
        rep = verify_probe(
            stage_dir=Path(args.stage_dir),
            core_esm=Path(args.core) if args.core else None,
            card_path=Path(args.card) if args.card else None,
        )
        print(json.dumps(rep, indent=2))
        return 0
    if args.cmd == "install":
        rep = install_probe_cmd(
            stage_dir=Path(args.dir),
            starfield_dir=Path(args.starfield),
            plugins_txt=Path(args.plugins_txt) if args.plugins_txt else None,
            version_tag=str(args.version_tag),
            card_path=Path(args.card) if args.card else None,
            allow_hardlink=not bool(args.no_hardlink),
            min_free_gb=float(args.min_free_gb),
        )
        print(json.dumps(rep, indent=2))
        return 0
    if args.cmd == "status":
        rep = probe_common.probe_status(probe_id=PROBE_ID, starfield_dir=Path(args.starfield))
        print(json.dumps(rep, indent=2))
        return 0
    if args.cmd == "uninstall":
        rep = probe_common.uninstall_probe(
            probe_id=PROBE_ID,
            starfield_dir=Path(args.starfield),
        )
        print(json.dumps(rep, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
