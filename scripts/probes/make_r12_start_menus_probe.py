#!/usr/bin/env python3
"""Stage, verify, install, inspect, and uninstall the Round 12 Task 5 (`r12-start-menus`) probe.

Assembles a standalone, self-contained staging folder outside Git and Starfield containing:
  - Rebuilt `FO4SFNewGame.esm`, loose `Data/Scripts/FO4SF_NewGame*.pex`, and `FO4SFNewGame - Main.ba2`
    (verified GNRL BA2 + vault activator assets)
  - Slot 2 `FO4SFPipboyMenu.dll` via `probe_common.reuse_tested_binary` (reused when hashes match,
    rebuilt cleanly otherwise)
  - Stage=2 `FO4SFPipboyMenu.ini` generated via `make_pipboy_stage_ini.py` preserving shipped
    `MapBlockStarMap=0`, `MapSurvival=0`, and `SetupShowUnavailable=0` (or caller setting)
  - `Data/SFSE/Plugins/FO4SFStartPlaces.json` & `FO4SFWarfareStarts.json` (validated strictly:
    only `fo4_vault111` claims available in Story until Task 6; Commonwealth Warfare starts
    verified against loaded plugins/exterior cells)
  - `P3` zero-`M/N/V` inspection batches `s5a.txt` (Corvega) and `s5b.txt` (Gunners Plaza)
  - `manifest.json` with SHA-256 checksums for atomic `probe_common.install_probe` / `uninstall_probe`

Never installs into `Starfield\\Data`, never launches game/Creation Kit, and refuses frozen folders.
"""
from __future__ import annotations

import argparse
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
UI_SCRIPTS_DIR = SCRIPTS_DIR / "ui"
NEWGAME_SCRIPTS_DIR = SCRIPTS_DIR / "newgame"
TESTING_SCRIPTS_DIR = SCRIPTS_DIR / "testing"
for _p in (SRC_DIR, PROBES_DIR, UI_SCRIPTS_DIR, NEWGAME_SCRIPTS_DIR, TESTING_SCRIPTS_DIR):
    s = str(_p)
    if s not in sys.path:
        sys.path.insert(0, s)

import make_newgame  # noqa: E402
import make_pipboy_stage_ini  # noqa: E402
import probe_common  # noqa: E402
import r12_card_validator  # noqa: E402
from fo4sf.core import start_places as sp  # noqa: E402
from fo4sf.core import warfare_starts as ws  # noqa: E402
from fo4sf.launcher import launch_choices as lc  # noqa: E402
from fo4sf.planet.esm import Plugin  # noqa: E402

PROBE_ID = "r12-start-menus"
MANIFEST_NAME = "manifest.json"
MIN_FREE_GB = probe_common.DEFAULT_MIN_FREE_GB
MAX_AXIS_M = probe_common.DEFAULT_MAX_HOP_AXIS_M

DEFAULT_STARFIELD_DIR: Optional[Path] = None
DEFAULT_BASELINE_DIR: Optional[Path] = None
DEFAULT_FO4_DATA_DIR: Optional[Path] = None
DEFAULT_PORT_ESM: Optional[Path] = None
DEFAULT_PORT_IDS: Optional[Path] = None
DEFAULT_TESTED_PIPBOY_DLL: Optional[Path] = None
DEFAULT_CARD_PATH = REPO_ROOT / "docs" / "testing" / "r12-start-menus-card.md"
DEFAULT_START_PLACES = REPO_ROOT / "src" / "fo4sf" / "core" / "start_places.json"
DEFAULT_WARFARE_STARTS = REPO_ROOT / "src" / "fo4sf" / "core" / "warfare_starts.json"
DEFAULT_MSVC_ENV_PS1: Optional[Path] = None

TESTED_SLOT2_PIPBOY_DLL_SHA256 = "c0e232b95fb6a31f1959d02bb529701b41d4e2f6e62dc268739a6e75534b8767"
PIPBOY_SOURCE_REL_PATHS: Tuple[str, ...] = (
    "xmake.lua",
    "FO4SFPipboyMenu.ini",
    "src/main.cpp",
    "src/pch.h",
    "src/pipboy_map.cpp",
    "src/pipboy_map.h",
    "src/setup_places.h",
    "src/world.cpp",
    "src/world.h",
)
TESTED_SLOT2_PIPBOY_SOURCE_HASHES: Dict[str, str] = {
    "xmake.lua": "00869296f54eeeadc4cdf4cf03cc580b87db27af953e5c8b29ef5b7ccbd9f472",
    "FO4SFPipboyMenu.ini": "aa1b5ad3eb8538a12020bc3dadae6748d962c9133ae53a5ad4ab4f0687598162",
    "main.cpp": "bbd76df8691fde6ac056a747466132565b8a05b954e237049cba29ec6438aa2d",
    "pch.h": "7a64a825b8a26917ccc69c73c15f82f943252a038d406fab916234277e09122c",
    "pipboy_map.cpp": "611ae4d939b6d55068889836b3fb636002a86d8fc85c0a30dd6c1ed85de56f1a",
    "pipboy_map.h": "1dcce102e16dfb75245908098a136dae3953e25b1cd95e9ed926d6f95cd4f2bb",
    "setup_places.h": "55d9301d61147c05793533d87c065b91ba4eaf1c38c8e5836db1a9af30a757fa",
    "world.cpp": "eba9623a09f135ebb6f53fd823fa492c458499d5138f48ad8515dc761ed43982",
    "world.h": "040ba4591a37553adb9b7c7344640f5d70200ed521f767efb8f89303fe7ebcce",
}

COMMONWEALTH_WARFARE_ANCHORS: Tuple[probe_common.AnchorPoint, ...] = (
    probe_common.AnchorPoint(
        name="sanctuary",
        x=-1153.83,
        y=1259.64,
        z=110.26,
        cell_type="exterior",
        cell="Sanctuary Hills (-12, 12)",
    ),
    probe_common.AnchorPoint(
        name="corvega",
        x=-561.05,
        y=505.93,
        z=51.99,
        cell_type="exterior",
        cell="Corvega Assembly Plant (-6, 5)",
    ),
    probe_common.AnchorPoint(
        name="gunners_plaza",
        x=-155.06,
        y=-1055.00,
        z=14.21,
        cell_type="exterior",
        cell="Gunners Plaza (-2, -11)",
    ),
)

COMMONWEALTH_WARFARE_HOPS: Tuple[probe_common.HopSpec, ...] = (
    probe_common.HopSpec(
        name="corvega_exterior_lot",
        from_anchor="corvega",
        x=-516.05,
        y=540.93,
        z=53.99,
        cell_type="exterior",
        cell="Corvega Assembly Plant (-6, 5)",
    ),
    probe_common.HopSpec(
        name="gunners_plaza_courtyard",
        from_anchor="gunners_plaza",
        x=-115.06,
        y=-1025.00,
        z=16.21,
        cell_type="exterior",
        cell="Gunners Plaza (-2, -11)",
    ),
)

P3_BATCHES: Tuple[Tuple[str, str], ...] = (
    (
        "s5a.txt",
        "; Corvega Assembly Plant exterior warfare check (0 M/N/V, <200m local)\n"
        "getpos x\n"
        "getpos y\n"
        "getpos z\n",
    ),
    (
        "s5b.txt",
        "; Gunners Plaza exterior warfare check (0 M/N/V, <200m local)\n"
        "getpos x\n"
        "getpos y\n"
        "getpos z\n",
    ),
)
P3_ACTIVATE_COMMANDS: Tuple[str, ...] = ("bat s5a", "bat s5b")

SWAP_ALLOWED_DATA_PREFIXES: Tuple[str, ...] = (
    "Data/FO4SFNewGame.esm",
    "Data/FO4SFNewGame - Main.ba2",
    "Data/Scripts/FO4SF_NewGame",
    "Data/SFSE/Plugins/FO4SFPipboyMenu.dll",
    "Data/SFSE/Plugins/FO4SFPipboyMenu.ini",
    "Data/SFSE/Plugins/FO4SFStartPlaces.json",
    "Data/SFSE/Plugins/FO4SFWarfareStarts.json",
)


def _copy_stage_file(src: Path, dst: Path) -> str:
    """Copy a staged file cleanly without hardlinks (`st_nlink == 1`), returning its SHA-256."""
    probe_common.copy_or_link_staged_file(src, dst, allow_hardlink=False)
    return probe_common.sha256_file(dst)


def _pipboy_src_paths() -> List[Path]:
    base = REPO_ROOT / "sfse" / "FO4SFPipboyMenu"
    return [base / rel for rel in PIPBOY_SOURCE_REL_PATHS]


def _rebuild_pipboy_dll_into(work_dir: Path, msvc_env_ps1: Optional[Path] = DEFAULT_MSVC_ENV_PS1) -> Path:
    """Invoke `sfse/FO4SFPipboyMenu/build.ps1 -Out <fresh>` as `reuse_tested_binary` fallback."""
    plugin_root = REPO_ROOT / "sfse" / "FO4SFPipboyMenu"
    build_ps1 = plugin_root / "build.ps1"
    if not build_ps1.is_file():
        raise FileNotFoundError(f"build.ps1 missing at {build_ps1}")
    out_dir = Path(tempfile.mkdtemp(prefix="r12_t5_pb_out_", dir=str(work_dir)))
    env_candidate = msvc_env_ps1
    if env_candidate is None and os.environ.get("FO4SF_MSVC_ENV"):
        env_candidate = Path(os.environ["FO4SF_MSVC_ENV"])
    if env_candidate is not None and env_candidate.is_file():
        ps_cmd = f". '{env_candidate}'; & '{build_ps1}' -Out '{out_dir}'"
    else:
        ps_cmd = f"& '{build_ps1}' -Out '{out_dir}'"
    proc = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
        cwd=str(plugin_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"FO4SFPipboyMenu build.ps1 failed ({proc.returncode}): {proc.stdout}\n{proc.stderr}")
    built = out_dir / "FO4SFPipboyMenu.dll"
    if not built.is_file():
        raise FileNotFoundError(f"Built FO4SFPipboyMenu.dll missing at {built}")
    return built


def _resolve_pipboy_dll(
    *,
    pipboy_dll_override: Optional[Path],
    tested_pipboy_dll: Optional[Path],
    dst_path: Path,
    work_dir: Path,
    build_json_dst: Optional[Path] = None,
    pipboy_build_json_override: Optional[Path] = None,
) -> probe_common.BinaryReuseResult:
    """Resolve `FO4SFPipboyMenu.dll`, honoring explicit override or `reuse_tested_binary`."""
    if pipboy_dll_override is not None:
        src = Path(pipboy_dll_override)
        if not src.is_file():
            raise FileNotFoundError(f"--pipboy-dll file missing: {src}")
        _copy_stage_file(src, dst_path)
        bjson = pipboy_build_json_override or (src.parent / "build.json")
        if build_json_dst is not None and bjson.is_file():
            _copy_stage_file(bjson, build_json_dst)
        src_hash = probe_common.hash_source_files(_pipboy_src_paths())
        return probe_common.BinaryReuseResult(
            path=dst_path,
            reused=(probe_common.sha256_file(dst_path) == TESTED_SLOT2_PIPBOY_DLL_SHA256),
            src_hash=src_hash,
            bin_sha256=probe_common.sha256_file(dst_path),
        )

    if tested_pipboy_dll is None:
        built = _rebuild_pipboy_dll_into(work_dir)
        _copy_stage_file(built, dst_path)
        bjson = pipboy_build_json_override or (built.parent / "build.json")
        if build_json_dst is not None and bjson.is_file():
            _copy_stage_file(bjson, build_json_dst)
        return probe_common.BinaryReuseResult(
            path=dst_path,
            reused=False,
            src_hash=probe_common.hash_source_files(_pipboy_src_paths()),
            bin_sha256=probe_common.sha256_file(dst_path),
        )

    res = probe_common.reuse_tested_binary(
        _pipboy_src_paths(),
        TESTED_SLOT2_PIPBOY_SOURCE_HASHES,
        tested_pipboy_dll,
        lambda: _rebuild_pipboy_dll_into(work_dir),
        dst_path=dst_path,
    )
    bjson = pipboy_build_json_override or (Path(res.path).parent / "build.json")
    if not bjson.is_file():
        bjson = Path(tested_pipboy_dll).parent / "build.json"
    if build_json_dst is not None and bjson.is_file():
        _copy_stage_file(bjson, build_json_dst)
    return res


def _generate_pipboy_ini(
    *,
    interface_dir: Path,
    out_ini: Path,
    show_unavailable_starts: int,
) -> None:
    """Build Stage=2 INI preserving `MapBlockStarMap=0` and `MapSurvival=0`."""
    if not interface_dir.is_dir():
        raise FileNotFoundError(f"Interface SWF folder missing: {interface_dir}")
    with tempfile.TemporaryDirectory(prefix="r12_t5_ini_") as td:
        tmp_stage = Path(td) / "pb_stage"
        iface_dst = tmp_stage / "Data" / "Interface"
        iface_dst.mkdir(parents=True, exist_ok=True)
        for swf_p in interface_dir.glob("*.swf"):
            shutil.copy2(swf_p, iface_dst / swf_p.name)
        comp_src = interface_dir / "Components"
        if comp_src.is_dir():
            shutil.copytree(comp_src, iface_dst / "Components", dirs_exist_ok=True)

        make_pipboy_stage_ini.generate_stage_ini(
            tmp_stage,
            out_ini=out_ini,
            movie="FO4SF_Fo4Shell",
            pause=1,
            populate_in_call=0,
            late_invalidate=0,
            shell_backdrop=1,
            shell_vitals_fill=1,
            suppress_data_menu=0,
            tab_opens_pipboy=0,
            arm=0,
            stat_actions=0,
            inv_data_answers=0,
            require_pickup=0,
            boot_on_first_open=0,
            special_menu=0,
            map_block_starmap=0,
            setup_show_unavailable=1 if int(show_unavailable_starts) else 0,
        )
        ini_text = out_ini.read_text(encoding="utf-8")
        make_pipboy_stage_ini.assert_no_kit_entries(ini_text)


def _scan_core_places(core_esm: Optional[Path], port_esm: Optional[Path]) -> Optional[Dict[str, Any]]:
    """Scan loaded TES4 core/port plugins for markers and exterior/interior cells when present."""
    markers: set[str] = set()
    interior_cells: set[str] = set()
    exterior_cells: set[Tuple[int, int]] = set()
    parsed: List[str] = []
    for p in (core_esm, port_esm):
        if p is not None and p.is_file():
            if lc._scan_single_tes4_places(str(p), markers, interior_cells, exterior_cells):
                parsed.append(p.name)
    if not parsed:
        return None
    return {
        "parsed_plugins": parsed,
        "markers": markers,
        "interior_cells": interior_cells,
        "exterior_cells": exterior_cells,
    }


def _validate_start_configs(
    *,
    start_places_path: Path,
    warfare_starts_path: Path,
    core_esm: Optional[Path],
    port_esm: Optional[Path],
) -> Tuple[Tuple[sp.StartPlaceRow, ...], Tuple[ws.WarfareStartRow, ...]]:
    """Enforce Task 5 strict Story (`fo4_vault111`-only) and Warfare exterior cell/anchor validity."""
    scan = _scan_core_places(core_esm, port_esm)
    known_ext = scan["exterior_cells"] if scan is not None else None
    all_rows = sp.load_start_places(
        str(start_places_path),
        available_only=False,
        known_exterior_cells=known_ext,
        allow_story_ids=sp.ALLOWED_STORY_START_IDS,
    )
    warfare_rows = ws.load_warfare_starts(
        str(warfare_starts_path),
        known_exterior_cells=known_ext,
    )
    avail_story = [r.id for r in all_rows if r.mode == "story" and r.available]
    if avail_story != ["fo4_vault111"]:
        raise probe_common.ProbeValidationError(
            f"Task 5 requires only 'fo4_vault111' available in Story (found {avail_story})"
        )
    avail_warfare = {r.id for r in all_rows if r.mode == "warfare" and r.available}
    for req_id in ("minutemen_sanctuary", "gunners_plaza", "raiders_corvega"):
        if req_id not in avail_warfare:
            raise probe_common.ProbeValidationError(
                f"Expected Commonwealth Warfare start {req_id!r} to be available (found {sorted(avail_warfare)})"
            )
    return all_rows, warfare_rows


def _build_newgame_stage(
    *,
    work_dir: Path,
    starfield_dir: Path,
    fo4_data: Path,
    port_esm: Path,
    port_ids: Path,
    core_esm: Path,
    cog_door_dir: Optional[Path],
    exit_lift_dir: Optional[Path],
    start_places_path: Path,
    warfare_starts_path: Path,
    start_choice_backdrop: str,
    show_unavailable_starts: int,
) -> Path:
    """Run `scripts/newgame/make_newgame.py stage` cleanly into an isolated temporary folder."""
    fo4_esm = fo4_data if fo4_data.is_file() else (fo4_data / "Fallout4.esm")
    for label, p in (
        ("FO4Port.esm", port_esm),
        ("formids.json", port_ids),
        ("FO4TerrainCore.esm", core_esm),
        ("Fallout4.esm", fo4_esm),
        ("Starfield.esm", starfield_dir / "Data" / "Starfield.esm"),
    ):
        if not p.is_file():
            raise FileNotFoundError(f"Missing required NewGame build input {label}: {p}")

    ng_out = work_dir / "newgame_stage"
    cmd: List[str] = [
        "stage",
        "--out",
        str(ng_out),
        "--fo4",
        str(fo4_esm),
        "--port",
        str(port_esm),
        "--port-ids",
        str(port_ids),
        "--core",
        str(core_esm),
        "--starfield",
        str(starfield_dir / "Data" / "Starfield.esm"),
        "--warfare-starts",
        str(warfare_starts_path),
        "--start-places",
        str(start_places_path),
        "--start-choice-backdrop",
        start_choice_backdrop,
        "--show-unavailable-starts",
        str(int(bool(show_unavailable_starts))),
    ]
    if cog_door_dir is not None and (cog_door_dir / "plan.json").is_file():
        cmd.extend(["--cog-door", str(cog_door_dir)])
    if exit_lift_dir is not None and (exit_lift_dir / "plan.json").is_file():
        cmd.extend(["--exit-lift", str(exit_lift_dir)])

    rc = make_newgame.main(cmd)
    if rc != 0:
        raise RuntimeError(f"make_newgame.py stage failed with exit code {rc}")
    return ng_out


def _scan_full_names_clean(esm_path: Path) -> List[str]:
    """Fail if any top-level FULL record string in `esm_path` begins with `FO4SF `."""
    errors: List[str] = []
    with Plugin(str(esm_path)) as plg:
        for grp in plg.groups:
            for start, end in plg.groups[grp]:
                for item in plg.walk(start, end):
                    if item[0] != "REC":
                        continue
                    rec = plg.record_at(item[1])
                    full_b = rec.get(b"FULL")
                    if full_b:
                        txt = full_b.rstrip(b"\x00").decode("utf-8", errors="replace")
                        if txt.startswith("FO4SF "):
                            errors.append(f"{esm_path.name}:{rec.edid or hex(rec.formid)} FULL has 'FO4SF ' prefix: {txt!r}")
    return errors


def _validate_ini_defaults(ini_path: Path) -> None:
    text = ini_path.read_text(encoding="utf-8")
    make_pipboy_stage_ini.assert_no_kit_entries(text)
    kv: Dict[str, str] = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(";") or s.startswith("[") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        kv[k.strip()] = v.strip()
    if kv.get("Stage") != "2":
        raise probe_common.ProbeValidationError(f"{ini_path}: expected Stage=2, got {kv.get('Stage')!r}")
    if kv.get("MapBlockStarMap") != "0":
        raise probe_common.ProbeValidationError(
            f"{ini_path}: must preserve shipped MapBlockStarMap=0 default, got {kv.get('MapBlockStarMap')!r}"
        )
    if kv.get("MapSurvival") != "0":
        raise probe_common.ProbeValidationError(
            f"{ini_path}: must preserve shipped MapSurvival=0 default, got {kv.get('MapSurvival')!r}"
        )


def _is_swap_allowed(target_rel: str) -> bool:
    return any(target_rel == pref or target_rel.startswith(pref) for pref in SWAP_ALLOWED_DATA_PREFIXES)


def _ensure_stage_clean_newgame_inputs(
    *,
    esm_path: Path,
    reference_esms: Sequence[Path],
) -> None:
    probe_common.scan_plugin_cleanliness(
        [esm_path],
        reference_esms=reference_esms,
        raise_on_error=True,
    )
    full_errs = _scan_full_names_clean(esm_path)
    if full_errs:
        raise probe_common.ProbeValidationError("; ".join(full_errs))


def stage_probe(
    *,
    out_dir: Path,
    starfield_dir: Optional[Path] = DEFAULT_STARFIELD_DIR,
    baseline_dir: Optional[Path] = DEFAULT_BASELINE_DIR,
    fo4_data: Optional[Path] = DEFAULT_FO4_DATA_DIR,
    port_esm: Optional[Path] = None,
    port_ids: Optional[Path] = None,
    core_esm: Optional[Path] = None,
    cog_door_dir: Optional[Path] = None,
    exit_lift_dir: Optional[Path] = None,
    newgame_stage_dir: Optional[Path] = None,
    pipboy_dll: Optional[Path] = None,
    tested_pipboy_dll: Optional[Path] = DEFAULT_TESTED_PIPBOY_DLL,
    pipboy_build_json: Optional[Path] = None,
    interface_dir: Optional[Path] = None,
    start_places_path: Path = DEFAULT_START_PLACES,
    warfare_starts_path: Path = DEFAULT_WARFARE_STARTS,
    start_choice_backdrop: str = "empty_cell",
    show_unavailable_starts: int = 0,
    clean: bool = False,
    min_free_gb: float = MIN_FREE_GB,
    system: Optional[Any] = None,
) -> Dict[str, Any]:
    """Build and verify the standalone Round 12/13 Start Before Load (`r12-start-menus`) staging folder."""
    probe_common.check_starfield_not_running(system)
    out_p = Path(out_dir)
    probe_common.check_out_dir_safe(out_p, clean=clean)
    probe_common.check_free_space_gb(out_p.parent if out_p.parent.exists() else out_p, min_gb=min_free_gb)

    sf_dir = Path(starfield_dir) if starfield_dir is not None else None
    base_dir = Path(baseline_dir) if baseline_dir is not None else None
    resolved_core = core_esm
    if resolved_core is None and base_dir is not None:
        cand = base_dir / "FO4TerrainCore.esm"
        resolved_core = cand if cand.is_file() else (base_dir / "clean-core-2g-fix2-player" / "FO4TerrainCore.esm")
    resolved_port = port_esm if port_esm is not None else DEFAULT_PORT_ESM
    if resolved_port is None and base_dir is not None and (base_dir / "FO4Port.esm").is_file():
        resolved_port = base_dir / "FO4Port.esm"
    if port_ids is not None:
        resolved_port_ids = port_ids
    elif DEFAULT_PORT_IDS is not None and DEFAULT_PORT_IDS.is_file():
        resolved_port_ids = DEFAULT_PORT_IDS
    elif base_dir is not None:
        cand_ids = base_dir / "formids.json"
        resolved_port_ids = cand_ids if cand_ids.is_file() else (base_dir / "clean-core-2g-fix2-player" / "formids.json")
    else:
        resolved_port_ids = None
    resolved_cog = cog_door_dir if cog_door_dir is not None else ((base_dir / "stages" / "01-cog-door") if base_dir is not None else None)
    resolved_lift = exit_lift_dir if exit_lift_dir is not None else ((base_dir / "stages" / "02-exit-lift") if base_dir is not None else None)
    if interface_dir is not None:
        resolved_iface = interface_dir
    elif base_dir is not None:
        cand_iface = base_dir / "Data" / "Interface"
        resolved_iface = cand_iface if cand_iface.is_dir() else (base_dir / "player" / "Data" / "Interface")
    else:
        raise ValueError("--interface-dir or --baseline-dir is required")

    if not start_places_path.is_file():
        raise FileNotFoundError(f"Missing start_places.json: {start_places_path}")
    if not warfare_starts_path.is_file():
        raise FileNotFoundError(f"Missing warfare_starts.json: {warfare_starts_path}")

    all_rows, _warfare_rows = _validate_start_configs(
        start_places_path=start_places_path,
        warfare_starts_path=warfare_starts_path,
        core_esm=resolved_core if resolved_core is not None and resolved_core.is_file() else None,
        port_esm=resolved_port if resolved_port is not None and resolved_port.is_file() else None,
    )

    out_p.mkdir(parents=True, exist_ok=True)
    data_out = out_p / "Data"
    scripts_out = data_out / "Scripts"
    sfse_out = data_out / "SFSE" / "Plugins"
    bat_out = out_p / "bat"
    for d in (data_out, scripts_out, sfse_out, bat_out):
        d.mkdir(parents=True, exist_ok=True)

    build_json_out = out_p / "build.json"

    with tempfile.TemporaryDirectory(prefix="r12_t5_work_") as td:
        work_dir = Path(td)

        # 1. Obtain rebuilt FO4SFNewGame.esm + Scripts/*.pex + vault activator assets
        if newgame_stage_dir is not None:
            ng_stage = Path(newgame_stage_dir)
        else:
            if sf_dir is None or fo4_data is None or resolved_port is None or resolved_port_ids is None or resolved_core is None:
                raise ValueError(
                    "Building FO4SFNewGame.esm requires --starfield, --fo4, --port, --port-ids, and --core "
                    "(or pass --newgame-stage)"
                )
            ng_stage = _build_newgame_stage(
                work_dir=work_dir,
                starfield_dir=sf_dir,
                fo4_data=Path(fo4_data),
                port_esm=resolved_port,
                port_ids=resolved_port_ids,
                core_esm=resolved_core,
                cog_door_dir=resolved_cog if resolved_cog is not None and resolved_cog.is_dir() else None,
                exit_lift_dir=resolved_lift if resolved_lift is not None and resolved_lift.is_dir() else None,
                start_places_path=start_places_path,
                warfare_starts_path=warfare_starts_path,
                start_choice_backdrop=start_choice_backdrop,
                show_unavailable_starts=show_unavailable_starts,
            )

        ng_esm_src = ng_stage / "FO4SFNewGame.esm"
        if not ng_esm_src.is_file():
            raise FileNotFoundError(f"FO4SFNewGame.esm missing in {ng_stage}")
        ng_esm_dst = data_out / "FO4SFNewGame.esm"
        ng_esm_sha = _copy_stage_file(ng_esm_src, ng_esm_dst)

        # Stage compiled scripts + activator assets (never overwrite FO4SFVaultGearDoor/ExitLift from baseline)
        ba2_sources: Dict[str, Path] = {}
        ng_data = ng_stage / "Data"
        if ng_data.is_dir():
            for src_file in sorted(ng_data.rglob("*")):
                if not src_file.is_file():
                    continue
                rel_data = src_file.relative_to(ng_data).as_posix()
                rel_low = rel_data.lower()
                is_newgame_pex = rel_low.startswith("scripts/fo4sf_newgame") and rel_low.endswith(".pex")
                is_newgame_asset = rel_low.startswith(("meshes/", "materials/", "geometries/"))
                if not (is_newgame_pex or is_newgame_asset):
                    continue
                dst_file = data_out / rel_data
                _copy_stage_file(src_file, dst_file)
                ba2_sources[rel_data] = dst_file

        if not any(k.lower().startswith("scripts/fo4sf_newgame") for k in ba2_sources):
            raise probe_common.ProbeValidationError(
                f"No Scripts/FO4SF_NewGame*.pex found in NewGame stage {ng_stage}"
            )

        ba2_path = data_out / "FO4SFNewGame - Main.ba2"
        probe_common.pack_gnrl_ba2(ba2_sources, ba2_path, compress=True)
        ba2_hashes = probe_common.verify_ba2_entry_hashes(ba2_path, source_files=ba2_sources)

        # 2. FO4SFPipboyMenu.dll + Stage=2 INI (preserving shipped MapBlockStarMap=0, MapSurvival=0)
        dll_res = _resolve_pipboy_dll(
            pipboy_dll_override=pipboy_dll,
            tested_pipboy_dll=tested_pipboy_dll,
            dst_path=sfse_out / "FO4SFPipboyMenu.dll",
            work_dir=work_dir,
            build_json_dst=build_json_out,
            pipboy_build_json_override=pipboy_build_json,
        )
        ini_dst = sfse_out / "FO4SFPipboyMenu.ini"
        _generate_pipboy_ini(
            interface_dir=resolved_iface,
            out_ini=ini_dst,
            show_unavailable_starts=show_unavailable_starts,
        )
        _validate_ini_defaults(ini_dst)

    # 3. Pre-launch JSON start configs for DLL & runtime lookup
    sp_dst = sfse_out / "FO4SFStartPlaces.json"
    ws_dst = sfse_out / "FO4SFWarfareStarts.json"
    sp_sha = _copy_stage_file(start_places_path, sp_dst)
    ws_sha = _copy_stage_file(warfare_starts_path, ws_dst)

    # 4. Write & validate P3 batches and <200m/axis hops
    batch_paths: List[Path] = []
    for fname, body in P3_BATCHES:
        bp = bat_out / fname
        bp.write_text(body, encoding="utf-8", newline="\n")
        batch_paths.append(bp)
    probe_common.validate_batches_and_hops(
        batch_files=batch_paths,
        activate_commands=P3_ACTIVATE_COMMANDS,
        anchors=COMMONWEALTH_WARFARE_ANCHORS,
        hops=COMMONWEALTH_WARFARE_HOPS,
        max_axis_m=MAX_AXIS_M,
        raise_on_error=True,
    )

    # 5. Plugin cleanliness check on FO4SFNewGame.esm
    ref_esms = [p for p in (resolved_core, resolved_port) if p is not None and p.is_file()]
    _ensure_stage_clean_newgame_inputs(esm_path=ng_esm_dst, reference_esms=ref_esms)

    # 6. Build manifest.json for atomic install_probe / uninstall_probe / verify_probe
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
                "src_rel": f"Data/{rel_data}",
                "target_rel": tgt_rel,
                "sha256": probe_common.sha256_file(p),
                "allow_swap": _is_swap_allowed(tgt_rel),
            }
        )
    for bp in sorted(batch_paths):
        file_entries.append(
            {
                "src_rel": f"bat/{bp.name}",
                "target_rel": bp.name,
                "sha256": probe_common.sha256_file(bp),
                "allow_swap": False,
            }
        )

    manifest: Dict[str, Any] = {
        "schema": "fo4sf.r12_start_menus_manifest.v1",
        "probe_id": PROBE_ID,
        "plugins_to_activate": ["FO4SFNewGame.esm"],
        "available_starts": [r.id for r in all_rows if r.available],
        "start_choice_backdrop": start_choice_backdrop,
        "show_unavailable_starts": int(bool(show_unavailable_starts)),
        "newgame_esm_sha256": ng_esm_sha,
        "newgame_ba2_sha256": probe_common.sha256_file(ba2_path),
        "newgame_ba2_entries": ba2_hashes,
        "pipboy_dll_sha256": dll_res.bin_sha256,
        "pipboy_dll_reused": bool(dll_res.reused),
        "pipboy_source_hash": dll_res.src_hash,
        "pipboy_build_json_sha256": probe_common.sha256_file(build_json_out) if build_json_out.is_file() else "",
        "pipboy_ini_sha256": probe_common.sha256_file(ini_dst),
        "start_places_sha256": sp_sha,
        "warfare_starts_sha256": ws_sha,
        "commonwealth_anchors": {
            anc.name: {"x": anc.x, "y": anc.y, "z": anc.z, "cell": anc.cell}
            for anc in COMMONWEALTH_WARFARE_ANCHORS
        },
        "files": file_entries,
    }
    (out_p / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def verify_probe(
    *,
    stage_dir: Path,
    core_esm: Optional[Path] = None,
    port_esm: Optional[Path] = None,
    card_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run all offline verification gates against an already-staged `r12-start-menus` folder."""
    st = Path(stage_dir)
    manifest_p = st / MANIFEST_NAME
    if not manifest_p.is_file():
        raise probe_common.ProbeValidationError(f"Missing probe manifest: {manifest_p}")
    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
    if manifest.get("probe_id") != PROBE_ID:
        raise probe_common.ProbeValidationError(
            f"Unexpected manifest probe_id: {manifest.get('probe_id')!r} != {PROBE_ID!r}"
        )

    files = manifest.get("files") or []
    if not files:
        raise probe_common.ProbeValidationError("Manifest contains 0 files")

    for entry in files:
        src_p = st / str(entry["src_rel"])
        if not src_p.is_file():
            raise probe_common.ProbeValidationError(f"Missing staged file: {entry['src_rel']}")
        if src_p.stat().st_nlink != 1:
            raise probe_common.ProbeValidationError(
                f"Hardlink forbidden in stage ({src_p.stat().st_nlink} links): {entry['src_rel']}"
            )
        actual_sha = probe_common.sha256_file(src_p)
        if actual_sha != entry["sha256"]:
            raise probe_common.ProbeValidationError(
                f"SHA-256 mismatch on {entry['src_rel']}: got {actual_sha}, expected {entry['sha256']}"
            )

    ba2_path = st / "Data" / "FO4SFNewGame - Main.ba2"
    expected_ba2 = manifest.get("newgame_ba2_entries") or {}
    ba2_actual = probe_common.verify_ba2_entry_hashes(ba2_path, expected_hashes=expected_ba2)

    ng_esm = st / "Data" / "FO4SFNewGame.esm"
    ref_esms = [p for p in (core_esm, port_esm) if p is not None and p.is_file()]
    _ensure_stage_clean_newgame_inputs(esm_path=ng_esm, reference_esms=ref_esms)

    _validate_ini_defaults(st / "Data" / "SFSE" / "Plugins" / "FO4SFPipboyMenu.ini")
    if any(str(p).strip().casefold() == "fo4sfrouteloot.esm" for p in manifest.get("plugins_to_activate", ())):
        raise probe_common.ProbeValidationError(
            "Manifest plugins_to_activate must NOT activate FO4SFRouteLoot.esm (direct Warfare [null+0x1F0] crash)."
        )

    all_rows, _ = _validate_start_configs(
        start_places_path=st / "Data" / "SFSE" / "Plugins" / "FO4SFStartPlaces.json",
        warfare_starts_path=st / "Data" / "SFSE" / "Plugins" / "FO4SFWarfareStarts.json",
        core_esm=core_esm if core_esm is not None and core_esm.is_file() else None,
        port_esm=port_esm if port_esm is not None and port_esm.is_file() else None,
    )

    batch_files = sorted((st / "bat").glob("*.txt"))
    probe_common.validate_batches_and_hops(
        batch_files=batch_files,
        activate_commands=P3_ACTIVATE_COMMANDS,
        anchors=COMMONWEALTH_WARFARE_ANCHORS,
        hops=COMMONWEALTH_WARFARE_HOPS,
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
        "ba2_entries": len(ba2_actual),
        "available_starts": [r.id for r in all_rows if r.available],
        "card_validated": card_validated,
    }


def _assert_no_active_routeloot(plugins_path: Path) -> None:
    if not plugins_path.is_file():
        return
    for raw in plugins_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("*") and line.lstrip("*").strip().casefold() == "fo4sfrouteloot.esm":
            raise probe_common.ProbeInstallError(
                f"Active FO4SFRouteLoot.esm in {plugins_path} conflicts with direct Warfare starts "
                "(Task 1 [null+0x1F0] lightingTemplate crash); deactivate FO4SFRouteLoot.esm before installing."
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
    plg_path = probe_common._resolve_plugins_txt(Path(starfield_dir), plugins_txt)
    _assert_no_active_routeloot(plg_path)
    return probe_common.install_probe(
        probe_id=PROBE_ID,
        stage_dir=stage_dir,
        starfield_dir=starfield_dir,
        plugins_txt=plugins_txt,
        plugins_to_activate=manifest["plugins_to_activate"],
        files=manifest["files"],
        baseline_2g_fix2_hashes=probe_common.CANDIDATE_2G_FIX4_HASHES,
        baseline_label="candidate-2g-fix4",
        version_tag=version_tag,
        card_path=card_path,
        min_free_gb=min_free_gb,
        allow_hardlink=allow_hardlink,
        system=system,
    )


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Stage, verify, install, inspect, and uninstall r12-start-menus probe")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp_cmd = sub.add_parser("stage", help="Stage r12-start-menus probe into an external directory")
    sp_cmd.add_argument("--out", required=True)
    sp_cmd.add_argument("--starfield", default="")
    sp_cmd.add_argument("--baseline-dir", default="")
    sp_cmd.add_argument("--fo4", default="")
    sp_cmd.add_argument("--port", default="")
    sp_cmd.add_argument("--port-ids", default="")
    sp_cmd.add_argument("--core", default="")
    sp_cmd.add_argument("--cog-door", default="")
    sp_cmd.add_argument("--exit-lift", default="")
    sp_cmd.add_argument("--newgame-stage", default="")
    sp_cmd.add_argument("--pipboy-dll", default="")
    sp_cmd.add_argument("--tested-pipboy-dll", default="")
    sp_cmd.add_argument("--pipboy-build-json", default="")
    sp_cmd.add_argument("--interface-dir", default="")
    sp_cmd.add_argument("--start-places", default=str(DEFAULT_START_PLACES))
    sp_cmd.add_argument("--warfare-starts", default=str(DEFAULT_WARFARE_STARTS))
    sp_cmd.add_argument(
        "--start-choice-backdrop",
        choices=("empty_cell", "title_card", "setup_menu", "none"),
        default="empty_cell",
    )
    sp_cmd.add_argument("--show-unavailable-starts", type=int, choices=(0, 1), default=0)
    sp_cmd.add_argument("--clean", action="store_true")
    sp_cmd.add_argument("--min-free-gb", type=float, default=MIN_FREE_GB)

    vp = sub.add_parser("verify", help="Verify staged r12-start-menus probe directory")
    vp.add_argument("--stage-dir", "--dir", dest="stage_dir", required=True)
    vp.add_argument("--core", default="")
    vp.add_argument("--port", default="")
    vp.add_argument("--card", default="")

    ip = sub.add_parser("install", help="Atomically install r12-start-menus probe into <STARFIELD_DIR>")
    ip.add_argument("--dir", required=True)
    ip.add_argument("--starfield", required=True)
    ip.add_argument("--plugins-txt", default="")
    ip.add_argument("--version-tag", default="")
    ip.add_argument("--card", default="")
    ip.add_argument("--min-free-gb", type=float, default=MIN_FREE_GB)

    up = sub.add_parser("uninstall", help="Atomically uninstall r12-start-menus probe from <STARFIELD_DIR>")
    up.add_argument("--starfield", required=True)
    up.add_argument("--force", action="store_true")

    stp = sub.add_parser("status", help="Inspect installed r12-start-menus probe status")
    stp.add_argument("--starfield", required=True)
    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "stage":
        man = stage_probe(
            out_dir=Path(args.out),
            starfield_dir=Path(args.starfield) if args.starfield else None,
            baseline_dir=Path(args.baseline_dir) if args.baseline_dir else None,
            fo4_data=Path(args.fo4) if args.fo4 else None,
            port_esm=Path(args.port) if args.port else None,
            port_ids=Path(args.port_ids) if args.port_ids else None,
            core_esm=Path(args.core) if args.core else None,
            cog_door_dir=Path(args.cog_door) if args.cog_door else None,
            exit_lift_dir=Path(args.exit_lift) if args.exit_lift else None,
            newgame_stage_dir=Path(args.newgame_stage) if args.newgame_stage else None,
            pipboy_dll=Path(args.pipboy_dll) if args.pipboy_dll else None,
            tested_pipboy_dll=Path(args.tested_pipboy_dll) if args.tested_pipboy_dll else None,
            pipboy_build_json=Path(args.pipboy_build_json) if args.pipboy_build_json else None,
            interface_dir=Path(args.interface_dir) if args.interface_dir else None,
            start_places_path=Path(args.start_places),
            warfare_starts_path=Path(args.warfare_starts),
            start_choice_backdrop=args.start_choice_backdrop,
            show_unavailable_starts=args.show_unavailable_starts,
            clean=args.clean,
            min_free_gb=args.min_free_gb,
        )
        print(
            f"staged {PROBE_ID} -> {args.out} "
            f"(files={len(man['files'])}, reused_dll={man['pipboy_dll_reused']}, "
            f"starts={','.join(man['available_starts'])})"
        )
        return 0
    if args.cmd == "verify":
        rep = verify_probe(
            stage_dir=Path(args.stage_dir),
            core_esm=Path(args.core) if args.core else None,
            port_esm=Path(args.port) if args.port else None,
            card_path=Path(args.card) if args.card else None,
        )
        print(json.dumps(rep, indent=2))
        return 0
    if args.cmd == "install":
        rcpt = install_probe_cmd(
            stage_dir=Path(args.dir),
            starfield_dir=Path(args.starfield),
            plugins_txt=Path(args.plugins_txt) if args.plugins_txt else None,
            version_tag=args.version_tag,
            card_path=Path(args.card) if args.card else None,
            min_free_gb=args.min_free_gb,
        )
        print(json.dumps({"probe_id": rcpt["probe_id"], "complete": rcpt["complete"], "files": len(rcpt["published_files"])}, indent=2))
        return 0
    if args.cmd == "uninstall":
        res = probe_common.uninstall_probe(probe_id=PROBE_ID, starfield_dir=Path(args.starfield), force=args.force)
        print(json.dumps(res, indent=2))
        return 0
    if args.cmd == "status":
        st = probe_common.probe_status(
            probe_id=PROBE_ID,
            starfield_dir=Path(args.starfield),
            baseline_2g_fix2_hashes=probe_common.CANDIDATE_2G_FIX4_HASHES,
        )
        print(json.dumps(st, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
