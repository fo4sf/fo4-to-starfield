"""Stage, verify, install, inspect, and uninstall the standalone Round 11 S1 Pre-War probe (`r11-s1-prewar`).

Stacks cleanly on:
  - Task 1 Slot 1 `FO4Port.esm` (`build_fo4port_r11_museum.py`, `8163ca9a...`, `next_object_id: 0x00EFAB`)
    -> Slot 2 lossless append of `FO4Port_PrewarVault111S1` (`>= 0x00EFAB`) + Slot 1 BA2s
  - Task 4 `FO4SFHome.esm` (`EarthPlanetData`, clear temperate climate/atmosphere/weather, zero Mars/Starfield refs)
  - SanctuaryHillsWorld (`0x000A7FF4`) bounded pre-war strip (`4x4` SF tile, `.btd`, delta converted NIFs/MATs/DDSs)
  - `#854` Mr. Handy Codsworth (`D:\\FO4SF-Owner-Tests\\robot-anim\\E2`) + local MQ101 `.fuz -> .wem` voices + 5 stand-in beats
  - Task 5 Slot 3 `FO4SF_NewGameQuest.psc` + `FO4SFNewGame.esm` (`--prewar`, preserving `fo4_vault111` Skip Pre-War)
  - Reused Slot 2 `FO4SFPipboyMenu.dll` (`c63c3e6a...`) + Stage=2 safe INI (`MapBlockStarMap=0`, `MapSurvival=0`)

Never launches Starfield/Creation Kit, never writes to Starfield\\Data during `stage`, never commits binary assets to Git,
and refuses frozen candidate/probe directories.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
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
from fo4sf import ba2 as ba2_mod, convert_static, meshcollision, pipeline  # noqa: E402
from fo4sf.core import start_places as sp  # noqa: E402
from fo4sf.core import warfare_starts as ws  # noqa: E402
from fo4sf.planet import home_planet_spec as hspec  # noqa: E402
from fo4sf.prewar import mq101_census, s1_spec, sanctuary_strip, vault111_append  # noqa: E402

PROBE_ID = "r11-s1-prewar"
MANIFEST_NAME = "manifest.json"
MIN_FREE_GB = probe_common.DEFAULT_MIN_FREE_GB
MAX_AXIS_M = probe_common.DEFAULT_MAX_HOP_AXIS_M

DEFAULT_STARFIELD_DIR = Path(r"D:\SteamLibrary\steamapps\common\Starfield")
DEFAULT_FO4_DATA_DIR = Path(r"D:\SteamLibrary\steamapps\common\Fallout 4\Data")
DEFAULT_BASELINE_DIR = Path(r"D:\FO4SF-Owner-Tests\gemini-core\candidate-2g-fix2")
DEFAULT_DOORS_ANIM_DIR = Path(r"D:\Modding\staging\doors_anim_b00\port")
DEFAULT_INTERIORS_B10_DIR = Path(r"D:\Modding\staging\interiors_b10\port")
DEFAULT_P1_PORT_DIR = Path(r"D:\FO4SF-Owner-Tests\gemini-probes\r11-p1-museum-v2\port")
DEFAULT_WHOME_DATA_DIR = Path(r"D:\FO4SF-Owner-Tests\gemini-probes\w-home\Data")
DEFAULT_HANDY_STAGE_DIR = Path(r"D:\FO4SF-Owner-Tests\robot-anim\E2")
DEFAULT_TESTED_PIPBOY_DLL = Path(r"D:\FO4SF-Owner-Tests\gemini-probes\r12-start-menus\Data\SFSE\Plugins\FO4SFPipboyMenu.dll")
DEFAULT_TEXCONV_EXE = Path(r"C:\Modding\tools\xedit\Edit Scripts\Texconvx64.exe")
DEFAULT_XWM_EXE = Path(r"D:\SteamLibrary\steamapps\common\Fallout 4\Tools\Audio\xwmaencode.exe")
DEFAULT_WWISE_EXE = Path(r"D:\Wwise_2026.1.3.9276\Authoring\x64\Release\bin\WwiseConsole.exe")
DEFAULT_PORT_IDS = Path(r"D:\FO4SF-Owner-Tests\gemini-core\candidate-2c\port_formids.json")
DEFAULT_BASE_START_PLACES = REPO_ROOT / "src" / "fo4sf" / "core" / "start_places.json"
DEFAULT_WARFARE_STARTS = REPO_ROOT / "src" / "fo4sf" / "core" / "warfare_starts.json"
DEFAULT_CARD_PATH = REPO_ROOT / "docs" / "testing" / "round11-s1-prewar-card.md"

HERO_VERTIBIRD_MODEL = r"fo4core\vehicles\vertibird\vertibird01.nif"
HERO_EXT_LIFT_MODEL = r"fo4core\interiors\vault\rooms\vltelevator\vltelevatorexterior.nif"

PLUGINS_TO_ACTIVATE: Tuple[str, ...] = (
    "FO4Port.esm",
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
_ANC_V111 = s1_spec.PREWAR_V111_KEY_COORDS_M["int_elevator_spawn"]
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
        cell="FO4Port_PrewarVault111S1",
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
        cell="FO4Port_PrewarVault111S1",
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
        f"; S1 PrewarVault111S1 interior pod hop (<200m/axis, 0 M/N/V)\n"
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
    doors_anim_dir: Path,
    interiors_b10_dir: Path,
    p1_port_dir: Path,
    slot1_port_esm: Optional[Path],
    skip_port_ba2: bool,
) -> Dict[str, Any]:
    """Build Task 1 Slot 1 FO4Port.esm (or reuse supplied Slot 1), losslessly append Slot 2 PrewarVault111S1."""
    if slot1_port_esm is not None:
        s1_bytes = slot1_port_esm.read_bytes()
    else:
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

    navms: Sequence[Tuple[int, bytes]] = ()
    if fo4_esm.is_file():
        v111_src = vault111_append.extract_prewar_v111_source(str(fo4_esm))
        navms = v111_src.get("navms") or ()

    s2_bytes, append_rep = vault111_append.append_prewar_vault111_lossless(
        s1_bytes,
        min_start_id=s1_spec.MIN_PREWAR_PORT_START_ID,
        fo4_navms=navms,
        new_cell_edid="FO4Port_PrewarVault111S1",
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
        "append_report": {k: v for k, v in append_rep.items() if k != "out_sha256"},
        "verify_report": verify_rep,
        "ba2_sha256": ba2_info,
    }


def _stage_home_host(*, whome_data_dir: Path, data_out: Path) -> Dict[str, str]:
    """Copy Task 4 FO4SFHome host ESM, archives, and dual Earth biome maps (never FO4TerrainCore_Home.esm)."""
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
    return copied


def _convert_strip_delta_assets(
    *,
    objects_json_path: Path,
    fo4_data: Path,
    starfield_dir: Path,
    baseline_data_dir: Path,
    texconv_exe: Path,
    content_res: Path,
    conv_work: Path,
) -> Tuple[Dict[str, Path], Dict[str, Path], Dict[str, Any]]:
    """Convert missing Sanctuary strip NIFs with prefix='fo4prewar' and remap .nif output to meshes/fo4core/..."""
    objs = json.loads(objects_json_path.read_text(encoding="utf-8"))
    bases = objs.get("bases") or []

    delta_models: List[str] = []
    seen_models: set[str] = set()
    existing_in_2g = 0
    for b in bases:
        model = str(b.get("model", "")).replace("\\", "/").lstrip("/")
        if not model:
            continue
        low = model.lower()
        if low in seen_models:
            continue
        seen_models.add(low)
        cand_2g = baseline_data_dir / "meshes" / model
        if cand_2g.is_file():
            existing_in_2g += 1
        else:
            delta_models.append(model)

    for hero_rel in (HERO_VERTIBIRD_MODEL, HERO_EXT_LIFT_MODEL):
        hero_norm = hero_rel.replace("\\", "/").lstrip("/")
        if hero_norm.lower() not in seen_models and not (baseline_data_dir / "meshes" / hero_norm).is_file():
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
    nif_entries: Dict[str, Path] = {}

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
        "reused_from_baseline": existing_in_2g,
        "delta_requested": len(delta_models),
        "delta_converted_ok": ok_count,
        "effect_or_empty_skipped": effect_skipped,
        "converter_stats": conv.stats,
        "main_entries_count": len(main_entries),
        "tex_entries_count": len(tex_entries),
    }
    return main_entries, tex_entries, summary


def _stage_sanctuary_world(
    *,
    work_dir: Path,
    data_out: Path,
    fo4_data: Path,
    starfield_dir: Path,
    baseline_dir: Path,
    strip_dir_override: Optional[Path],
    texconv_exe: Path,
    content_res: Path,
    archive2_exe: Path,
    skip_strip_assets: bool,
    fast_ba2: bool,
) -> Dict[str, Any]:
    """Build FO4SFPrewar_Sanctuary.esm + FO4SFPrewar_Sanctuary_Home.esm + .btd + Sanctuary BA2s."""
    if strip_dir_override is not None:
        strip_src = Path(strip_dir_override)
    else:
        strip_src = work_dir / "sanctuary_strip"
        rc = build_prewar_strip.main(
            [
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
        )
        if rc != 0:
            raise RuntimeError(f"build_prewar_strip.py failed ({rc})")

    sanc_esm_src = strip_src / s1_spec.PLUGIN_PREWAR_WORLD
    reg_esm_src = strip_src / "FO4SFPrewar_Sanctuary_Home.esm"
    btd_src = strip_src / "Data" / "Terrain" / "FO4SF_PrewarSanctuaryWorld.btd"
    mask_src = strip_src / "Data" / "textures" / "terrain" / "overlaymasks" / "fo4sf_prewarsanctuaryworld.dds"
    for req in (sanc_esm_src, reg_esm_src, btd_src, mask_src):
        if not req.is_file():
            raise FileNotFoundError(f"Missing Sanctuary strip output: {req}")

    sanctuary_strip.verify_zero_starfield_sky_refs(str(sanc_esm_src))
    sanc_sha = _copy_stage_file(sanc_esm_src, data_out / s1_spec.PLUGIN_PREWAR_WORLD)
    reg_sha = _copy_stage_file(reg_esm_src, data_out / "FO4SFPrewar_Sanctuary_Home.esm")
    btd_sha = _copy_stage_file(btd_src, data_out / "Terrain" / "FO4SF_PrewarSanctuaryWorld.btd")

    main_entries: Dict[str, Path] = {}
    tex_entries: Dict[str, Path] = {"textures/terrain/overlaymasks/fo4sf_prewarsanctuaryworld.dds": mask_src}
    conv_summary: Dict[str, Any] = {"skipped": bool(skip_strip_assets)}

    if not skip_strip_assets:
        conv_work = work_dir / "sanctuary_conv"
        conv_work.mkdir(parents=True, exist_ok=True)
        main_entries, delta_tex, conv_summary = _convert_strip_delta_assets(
            objects_json_path=strip_src / "objects.json",
            fo4_data=fo4_data,
            starfield_dir=starfield_dir,
            baseline_data_dir=baseline_dir / "player" / "Data",
            texconv_exe=texconv_exe,
            content_res=content_res,
            conv_work=conv_work,
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
        "sanctuary_main_ba2_sha256": probe_common.sha256_file(main_ba2),
        "sanctuary_main_ba2_entries": main_hashes,
        "sanctuary_textures_ba2_sha256": probe_common.sha256_file(tex_ba2),
        "sanctuary_textures_ba2_entries": tex_hashes,
        "conversion_summary": conv_summary,
    }


def _stage_prewar_quest_and_voices(
    *,
    work_dir: Path,
    data_out: Path,
    fo4_data: Path,
    starfield_esm: Path,
    handy_stage_dir: Path,
    xwm_exe: Path,
    wwise_exe: Path,
    papyrus_compiler: Path,
    content_res: Path,
    prewar_dir_override: Optional[Path],
    skip_voices: bool,
) -> Dict[str, Any]:
    """Convert MQ101 .fuz -> .wem locally, build FO4SFPrewar.esm + Handy + S1 scripts, and pack Main BA2."""
    if prewar_dir_override is not None:
        pq_work = Path(prewar_dir_override)
        voice_summary: Dict[str, Any] = {"skipped": True, "converted_wem_count": 0}
    else:
        pq_work = work_dir / "prewar_quest"
        pq_work.mkdir(parents=True, exist_ok=True)
        fo4_esm = fo4_data / "Fallout4.esm"
        fo4_voices = fo4_data / "Fallout4 - Voices.ba2"
        voices_json_path: Optional[Path] = None

        voice_summary = {"skipped": bool(skip_voices), "converted_wem_count": 0}
        if not skip_voices:
            for req in (fo4_esm, fo4_voices, xwm_exe, wwise_exe):
                if not req.is_file():
                    raise FileNotFoundError(f"Missing MQ101 voice conversion input: {req}")
            vplan = mq101_census.build_prewar_voice_plan(str(fo4_esm), str(fo4_voices))
            ext_stems = [row["stem"] for row in vplan["extractable_stems"]]
            vscratch = work_dir / "voice_scratch"
            durations: Dict[str, float] = {}
            stem_to_wem = mq101_census.convert_stems_via_wwise(
                str(fo4_voices),
                ext_stems,
                str(xwm_exe),
                str(wwise_exe),
                str(vscratch),
                durations_out=durations,
            )
            voice_out_dir = pq_work / "Data" / "sound" / "voice" / "fo4sfprewar.esm"
            kellogg_rows, kellogg_copied = mq101_census.build_local_kellogg_voices_payload(
                str(fo4_esm),
                durations,
                str(voice_out_dir),
                stem_to_wem,
            )
            pool_dir = voice_out_dir / "mq101_pool"
            pool_copied = 0
            for stem, wem_src in sorted(stem_to_wem.items()):
                dst = pool_dir / Path(f"{stem}.wem")
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(wem_src, dst)
                pool_copied += 1

            voices_json_path = work_dir / "voices_local.json"
            voices_json_path.write_text(
                json.dumps({"kellogg_scene": kellogg_rows}, indent=2) + "\n",
                encoding="utf-8",
            )
            voice_summary = {
                "skipped": False,
                "scene_count": vplan["scene_count"],
                "raw_stem_count": vplan["stem_count"],
                "extractable_stem_count": vplan["extractable_stem_count"],
                "converted_wem_count": len(stem_to_wem),
                "kellogg_scene_wem_count": len(kellogg_copied),
                "pool_wem_count": pool_copied,
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
        "prewar_main_ba2_entries": main_hashes,
        "prewar_textures_ba2_entries": tex_hashes,
        "voice_summary": voice_summary,
    }


def _stage_newgame_and_ui(
    *,
    work_dir: Path,
    data_out: Path,
    starfield_dir: Path,
    baseline_dir: Path,
    fo4_data: Path,
    port_ids: Path,
    core_esm: Path,
    cog_door_dir: Optional[Path],
    exit_lift_dir: Optional[Path],
    newgame_stage_override: Optional[Path],
    pipboy_dll_override: Optional[Path],
    tested_pipboy_dll: Path,
    interface_dir: Optional[Path],
    base_start_places_path: Path,
    warfare_starts_path: Path,
) -> Dict[str, Any]:
    """Write S1 FO4SFStartPlaces.json, stage FO4SFNewGame (--prewar), pack Main BA2, and reuse Slot 2 DLL + INI."""
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
        ng_stage = work_dir / "newgame_stage"
        fo4_esm = fo4_data if fo4_data.is_file() else (fo4_data / "Fallout4.esm")
        ng_cmd: List[str] = [
            "stage",
            "--out",
            str(ng_stage),
            "--fo4",
            str(fo4_esm),
            "--port",
            str(data_out / "FO4Port.esm"),
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
    resolved_iface = interface_dir or (baseline_dir / "player" / "Data" / "Interface")
    ini_dst = sfse_out / "FO4SFPipboyMenu.ini"
    make_r12_start_menus_probe._generate_pipboy_ini(  # noqa: SLF001
        interface_dir=resolved_iface,
        out_ini=ini_dst,
        show_unavailable_starts=0,
    )
    make_r12_start_menus_probe._validate_ini_defaults(ini_dst)  # noqa: SLF001

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
    }


def stage_probe(
    *,
    out_dir: Path,
    starfield_dir: Path = DEFAULT_STARFIELD_DIR,
    fo4_data: Path = DEFAULT_FO4_DATA_DIR,
    baseline_dir: Path = DEFAULT_BASELINE_DIR,
    doors_anim_dir: Path = DEFAULT_DOORS_ANIM_DIR,
    interiors_b10_dir: Path = DEFAULT_INTERIORS_B10_DIR,
    p1_port_dir: Path = DEFAULT_P1_PORT_DIR,
    whome_data_dir: Path = DEFAULT_WHOME_DATA_DIR,
    handy_stage_dir: Path = DEFAULT_HANDY_STAGE_DIR,
    port_ids: Optional[Path] = None,
    core_esm: Optional[Path] = None,
    cog_door_dir: Optional[Path] = None,
    exit_lift_dir: Optional[Path] = None,
    interface_dir: Optional[Path] = None,
    pipboy_dll: Optional[Path] = None,
    tested_pipboy_dll: Path = DEFAULT_TESTED_PIPBOY_DLL,
    base_start_places_path: Path = DEFAULT_BASE_START_PLACES,
    warfare_starts_path: Path = DEFAULT_WARFARE_STARTS,
    texconv_exe: Path = DEFAULT_TEXCONV_EXE,
    xwm_exe: Path = DEFAULT_XWM_EXE,
    wwise_exe: Path = DEFAULT_WWISE_EXE,
    slot1_port_esm: Optional[Path] = None,
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
    """Build and offline-verify the complete Round 11 `r11-s1-prewar` staging folder."""
    probe_common.check_starfield_not_running(system)
    out_p = Path(out_dir)
    probe_common.check_out_dir_safe(out_p, clean=clean)
    probe_common.check_free_space_gb(out_p.parent if out_p.parent.exists() else out_p, min_gb=min_free_gb)

    sf_dir = Path(starfield_dir)
    base_dir = Path(baseline_dir)
    resolved_core = core_esm or (base_dir / "clean-core-2g-fix2-player" / "FO4TerrainCore.esm")
    resolved_port_ids = port_ids or (
        DEFAULT_PORT_IDS if base_dir == DEFAULT_BASELINE_DIR and DEFAULT_PORT_IDS.is_file()
        else base_dir / "clean-core-2g-fix2-player" / "formids.json"
    )
    resolved_cog = cog_door_dir
    resolved_lift = exit_lift_dir
    starfield_esm = sf_dir / "Data" / "Starfield.esm"
    content_res = sf_dir / "Tools" / "ContentResources.zip"
    papyrus_compiler = sf_dir / "Tools" / "Papyrus Compiler" / "PapyrusCompiler.exe"
    archive2_exe = sf_dir / "Tools" / "Archive2" / "Archive2.exe"

    data_out = out_p / "Data"
    bat_out = out_p / "bat"
    for d in (data_out, data_out / "Scripts", data_out / "SFSE" / "Plugins", bat_out):
        d.mkdir(parents=True, exist_ok=True)

    work_parent = out_p.parent if out_p.parent.exists() else out_p
    with tempfile.TemporaryDirectory(prefix="r11_s1_work_", dir=str(work_parent)) as td:
        work_dir = Path(td)

        port_rep = _stage_slot2_port(
            work_dir=work_dir,
            data_out=data_out,
            fo4_esm=Path(fo4_data) / "Fallout4.esm",
            doors_anim_dir=Path(doors_anim_dir),
            interiors_b10_dir=Path(interiors_b10_dir),
            p1_port_dir=Path(p1_port_dir),
            slot1_port_esm=slot1_port_esm,
            skip_port_ba2=skip_port_ba2,
        )
        home_rep = _stage_home_host(whome_data_dir=Path(whome_data_dir), data_out=data_out)
        sanc_rep = _stage_sanctuary_world(
            work_dir=work_dir,
            data_out=data_out,
            fo4_data=Path(fo4_data),
            starfield_dir=sf_dir,
            baseline_dir=base_dir,
            strip_dir_override=strip_dir,
            texconv_exe=Path(texconv_exe),
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
            handy_stage_dir=Path(handy_stage_dir),
            xwm_exe=Path(xwm_exe),
            wwise_exe=Path(wwise_exe),
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
            cog_door_dir=resolved_cog if resolved_cog is not None and resolved_cog.is_dir() else None,
            exit_lift_dir=resolved_lift if resolved_lift is not None and resolved_lift.is_dir() else None,
            newgame_stage_override=newgame_stage_dir,
            pipboy_dll_override=pipboy_dll,
            tested_pipboy_dll=Path(tested_pipboy_dll),
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
            resolved_core if resolved_core.is_file() else None,
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
        "schema": "fo4sf.r11_s1_prewar_manifest.v1",
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


def verify_probe(
    *,
    stage_dir: Path,
    core_esm: Optional[Path] = None,
    card_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run all offline verification gates against an already-staged `r11-s1-prewar` folder."""
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
    }


def _assert_clean_plugins_txt(plugins_path: Path) -> None:
    if not plugins_path.is_file():
        return
    for raw in plugins_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or not line.startswith("*"):
            continue
        name = line.lstrip("*").strip().casefold()
        if name == "fo4sfrouteloot.esm":
            raise probe_common.ProbeInstallError(f"Active FO4SFRouteLoot.esm in {plugins_path} conflicts with direct Warfare starts")
        if name == "fo4terraincore_home.esm":
            raise probe_common.ProbeInstallError(
                f"Active FO4TerrainCore_Home.esm in {plugins_path} overrides EarthPlanetData PNDT 0x805 "
                "and would shadow FO4SFPrewar_Sanctuary_Home.esm"
            )


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
    _assert_clean_plugins_txt(plg_path)
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
    ap = argparse.ArgumentParser(description="Stage, verify, install, inspect, and uninstall r11-s1-prewar probe")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp_cmd = sub.add_parser("stage", help="Stage r11-s1-prewar probe into an external directory")
    sp_cmd.add_argument("--out", required=True)
    sp_cmd.add_argument("--starfield", default=str(DEFAULT_STARFIELD_DIR))
    sp_cmd.add_argument("--fo4", default=str(DEFAULT_FO4_DATA_DIR))
    sp_cmd.add_argument("--baseline-dir", default=str(DEFAULT_BASELINE_DIR))
    sp_cmd.add_argument("--doors-anim-dir", default=str(DEFAULT_DOORS_ANIM_DIR))
    sp_cmd.add_argument("--interiors-b10-dir", default=str(DEFAULT_INTERIORS_B10_DIR))
    sp_cmd.add_argument("--p1-port-dir", default=str(DEFAULT_P1_PORT_DIR))
    sp_cmd.add_argument("--whome-data-dir", default=str(DEFAULT_WHOME_DATA_DIR))
    sp_cmd.add_argument("--handy-stage-dir", default=str(DEFAULT_HANDY_STAGE_DIR))
    sp_cmd.add_argument("--port-ids", default="")
    sp_cmd.add_argument("--core", default="")
    sp_cmd.add_argument("--cog-door", default="")
    sp_cmd.add_argument("--exit-lift", default="")
    sp_cmd.add_argument("--interface-dir", default="")
    sp_cmd.add_argument("--pipboy-dll", default="")
    sp_cmd.add_argument("--tested-pipboy-dll", default=str(DEFAULT_TESTED_PIPBOY_DLL))
    sp_cmd.add_argument("--base-start-places", default=str(DEFAULT_BASE_START_PLACES))
    sp_cmd.add_argument("--warfare-starts", default=str(DEFAULT_WARFARE_STARTS))
    sp_cmd.add_argument("--texconv", default=str(DEFAULT_TEXCONV_EXE))
    sp_cmd.add_argument("--xwmaencode", default=str(DEFAULT_XWM_EXE))
    sp_cmd.add_argument("--wwise-console", default=str(DEFAULT_WWISE_EXE))
    sp_cmd.add_argument("--slot1-port-esm", default="")
    sp_cmd.add_argument("--strip-dir", default="")
    sp_cmd.add_argument("--prewar-dir", default="")
    sp_cmd.add_argument("--newgame-stage", default="")
    sp_cmd.add_argument("--skip-port-ba2", action="store_true")
    sp_cmd.add_argument("--skip-strip-assets", action="store_true")
    sp_cmd.add_argument("--skip-voices", action="store_true")
    sp_cmd.add_argument("--fast-ba2", action="store_true")
    sp_cmd.add_argument("--clean", action="store_true")
    sp_cmd.add_argument("--min-free-gb", type=float, default=MIN_FREE_GB)

    vr = sub.add_parser("verify", help="Verify an already-staged r11-s1-prewar folder")
    vr.add_argument("--stage-dir", required=True)
    vr.add_argument("--core", default="")
    vr.add_argument("--card", default="")

    ins = sub.add_parser("install", help="Atomically install r11-s1-prewar into Starfield (game closed)")
    ins.add_argument("--dir", required=True)
    ins.add_argument("--starfield", default=str(DEFAULT_STARFIELD_DIR))
    ins.add_argument("--plugins-txt", default="")
    ins.add_argument("--version-tag", default="")
    ins.add_argument("--card", default="")
    ins.add_argument("--no-hardlink", action="store_true")
    ins.add_argument("--min-free-gb", type=float, default=MIN_FREE_GB)

    st = sub.add_parser("status", help="Inspect installation status of r11-s1-prewar")
    st.add_argument("--starfield", default=str(DEFAULT_STARFIELD_DIR))

    un = sub.add_parser("uninstall", help="Atomically roll back r11-s1-prewar from Starfield (game closed)")
    un.add_argument("--starfield", default=str(DEFAULT_STARFIELD_DIR))
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
            baseline_dir=Path(args.baseline_dir),
            doors_anim_dir=Path(args.doors_anim_dir),
            interiors_b10_dir=Path(args.interiors_b10_dir),
            p1_port_dir=Path(args.p1_port_dir),
            whome_data_dir=Path(args.whome_data_dir),
            handy_stage_dir=Path(args.handy_stage_dir),
            port_ids=Path(args.port_ids) if args.port_ids else None,
            core_esm=Path(args.core) if args.core else None,
            cog_door_dir=Path(args.cog_door) if args.cog_door else None,
            exit_lift_dir=Path(args.exit_lift) if args.exit_lift else None,
            interface_dir=Path(args.interface_dir) if args.interface_dir else None,
            pipboy_dll=Path(args.pipboy_dll) if args.pipboy_dll else None,
            tested_pipboy_dll=Path(args.tested_pipboy_dll),
            base_start_places_path=Path(args.base_start_places),
            warfare_starts_path=Path(args.warfare_starts),
            texconv_exe=Path(args.texconv),
            xwm_exe=Path(args.xwmaencode),
            wwise_exe=Path(args.wwise_console),
            slot1_port_esm=Path(args.slot1_port_esm) if args.slot1_port_esm else None,
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
            f"staged r11-s1-prewar into {args.out}: files={len(man['files'])} "
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
