#!/usr/bin/env python3
"""Stage, verify, install, inspect, and uninstall the Round 12 `w-home` host-swap & Pip-Boy StarMap probe.

Self-contained external probe builder reusing `probe_common.py`, `make_home_planet.py`, `home_world_install.py`,
`make_core_values.py`, `make_pipboy_stage_ini.py`, and `pipboy_map_store.py`. Never modifies frozen folders, Git
worktrees, `FO4TerrainCore.esm`, or `FO4Port.esm`, and never launches `Starfield.exe`.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import zipfile

HERE = Path(__file__).resolve().parent
SCRIPTS_DIR = HERE.parent
REPO_ROOT = SCRIPTS_DIR.parent
SRC_DIR = REPO_ROOT / "src"
for _p in (
    str(HERE),
    str(SCRIPTS_DIR),
    str(SCRIPTS_DIR / "core"),
    str(SCRIPTS_DIR / "planet"),
    str(SCRIPTS_DIR / "ui"),
    str(SRC_DIR),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import deploy_starfield  # noqa: E402
from fo4sf.planet import esm, home_planet_spec as hspec  # noqa: E402
import home_world_install  # noqa: E402
import make_core_values  # noqa: E402
import make_home_planet  # noqa: E402
import make_pipboy_stage_ini  # noqa: E402
import pipboy_map_store  # noqa: E402
import probe_common  # noqa: E402

PROBE_ID = "w-home"
MANIFEST_NAME = "probe_manifest.json"
CENSUS_NAME = "location_census.json"
MIN_FREE_GB = 60.0
MAX_HOP_AXIS_M = 180.0
BASE_PORT_ESM_SHA256 = "07756819ecf7ab9a88af6421478c7c05f13eb6dbef062a1a61b98ec63e7bbe60"

WHOME_LEVER_KEYWORDS: Tuple[str, ...] = hspec.LEVER_KEYWORD_EDIDS

VAULT111_ANCHOR = probe_common.AnchorPoint(
    name="Vault111",
    x=-2475.31,
    y=-1394.72,
    z=129.71,
    cell_type="exterior",
)
NORTH_STOPS: Tuple[Tuple[str, str, float, float, float, float], ...] = (
    ("w1", "SanctuaryHills", -2353.83, -1440.36, 112.76, 135.0),
    ("w2", "RedRocket", -2189.26, -1553.49, 109.64, 135.0),
    ("w3", "Concord", -2061.23, -1657.46, 89.43, 135.0),
    ("w4", "MuseumOfFreedom", -2014.45, -1694.40, 89.89, 90.0),
)
# F2: Collision/BTD-verified Diamond City chain (ground_z + 2.5 m, every hop < 180 m/axis;
# k3 clears rooftop mesh at -1791.85; k7 sits off 26.35 m roof; k8 stands 5.15 m SW of DmndGateREF).
DIAMOND_STOPS: Tuple[Tuple[str, str, float, float, float, float], ...] = (
    ("k1", "DC_Step1", -1940.25, -1874.09, 70.57, 158.0),
    ("k2", "DC_Step2", -1866.05, -2053.77, 64.78, 158.0),
    ("k3", "DC_Step3", -1788.85, -2233.46, 66.05, 158.0),
    ("k4", "DC_Step4", -1717.65, -2413.14, 40.83, 158.0),
    ("k5", "DC_Step5", -1643.46, -2592.83, 21.26, 158.0),
    ("k6", "DC_Step6", -1569.26, -2772.52, 15.87, 158.0),
    ("k7", "DC_Step7", -1495.06, -2952.20, 12.60, 158.0),
    ("k8", "DiamondCity", -1420.86, -3131.89, 21.93, 61.0),
)
# F5: 64-cell-edge chain west along y=-1394.72 from Vault111 to the west grid edge (sf_x=-4400.00).
WEST_EDGE_STOPS: Tuple[Tuple[str, str, float, float, float, float], ...] = (
    ("ea", "WestEdge_Step1", -2650.31, -1394.72, 118.78, 270.0),
    ("eb", "WestEdge_Step2", -2825.31, -1394.72, 119.00, 270.0),
    ("ec", "WestEdge_Step3", -3000.31, -1394.72, 139.39, 270.0),
    ("ed", "WestEdge_Step4", -3175.31, -1394.72, 147.15, 270.0),
    ("ee", "WestEdge_Step5", -3350.31, -1394.72, 162.13, 270.0),
    ("ef", "WestEdge_Step6", -3525.31, -1394.72, 173.47, 270.0),
    ("eg", "WestEdge_Step7", -3700.31, -1394.72, 182.52, 270.0),
    ("eh", "WestEdge_Step8", -3875.31, -1394.72, 198.56, 270.0),
    ("ei", "WestEdge_Step9", -4050.31, -1394.72, 226.89, 270.0),
    ("ej", "WestEdge_Step10", -4225.31, -1394.72, 256.93, 270.0),
    ("we1", "WestEdge_Inside", -4350.00, -1394.72, 312.90, 270.0),
    ("we2", "WestEdge_Outside", -4460.00, -1394.72, 312.90, 270.0),
)


def _format_hop_batch(bat_stem: str, comment: str, x: float, y: float, z: float, az: float) -> str:
    return "\n".join(
        [
            f"; {bat_stem}.txt: {comment}",
            f"player.setpos x {x:.2f}",
            f"player.setpos y {y:.2f}",
            f"player.setpos z {z:.2f}",
            f"player.setangle z {az:.0f}",
            "",
        ]
    )


def _build_batch_plan() -> Tuple[List[probe_common.AnchorPoint], List[probe_common.HopSpec], List[Tuple[str, str]]]:
    """Return P3-compliant anchors, `<180m/axis` hops, and `(filename, contents)` batch scripts."""
    anchors: List[probe_common.AnchorPoint] = [VAULT111_ANCHOR]
    hops: List[probe_common.HopSpec] = []
    batches: List[Tuple[str, str]] = []

    prev_name = VAULT111_ANCHOR.name
    for bat_stem, label, x, y, z, az in NORTH_STOPS:
        hops.append(probe_common.HopSpec(name=label, from_anchor=prev_name, x=x, y=y, z=z, cell_type="exterior"))
        anchors.append(probe_common.AnchorPoint(name=label, x=x, y=y, z=z, cell_type="exterior"))
        batches.append((f"{bat_stem}.txt", _format_hop_batch(bat_stem, f"{prev_name} -> {label} (<180m/axis exterior hop)", x, y, z, az)))
        prev_name = label

    for bat_stem, label, x, y, z, az in DIAMOND_STOPS:
        hops.append(probe_common.HopSpec(name=label, from_anchor=prev_name, x=x, y=y, z=z, cell_type="exterior"))
        anchors.append(probe_common.AnchorPoint(name=label, x=x, y=y, z=z, cell_type="exterior"))
        batches.append((f"{bat_stem}.txt", _format_hop_batch(bat_stem, f"{prev_name} -> {label} (ground_z+2.5m <180m/axis Diamond City hop)", x, y, z, az)))
        prev_name = label

    prev_west = VAULT111_ANCHOR.name
    for bat_stem, label, x, y, z, az in WEST_EDGE_STOPS:
        hops.append(probe_common.HopSpec(name=label, from_anchor=prev_west, x=x, y=y, z=z, cell_type="exterior"))
        anchors.append(probe_common.AnchorPoint(name=label, x=x, y=y, z=z, cell_type="exterior"))
        batches.append((f"{bat_stem}.txt", _format_hop_batch(bat_stem, f"{prev_west} -> {label} (64-cell west edge probe <180m/axis)", x, y, z, az)))
        prev_west = label

    batches.append(
        (
            "ktg.txt",
            "; ktg.txt: toggle god mode safely for exterior walk/hop probe checks (bat ktg)\ntgm\n",
        )
    )
    batches.append(
        (
            "r1.txt",
            "; r1.txt: trigger blocked GalaxyStarMapMenu safely on MapBlockStarMap=1 probe\nShowMenu GalaxyStarMapMenu\n",
        )
    )
    return anchors, hops, batches


def _compile_travel_pex(starfield_dir: Path, out_scripts_dir: Path) -> Path:
    compiler = starfield_dir / "Tools" / "Papyrus Compiler" / "PapyrusCompiler.exe"
    cr_zip = starfield_dir / "Tools" / "ContentResources.zip"
    if not compiler.is_file():
        raise FileNotFoundError(f"PapyrusCompiler.exe not found: {compiler}")
    if not cr_zip.is_file():
        raise FileNotFoundError(f"ContentResources.zip not found: {cr_zip}")

    psc_dir = REPO_ROOT / "scripts" / "mapmarkers"
    psc_file = psc_dir / "FO4SF_PipboyTravel.psc"
    if not psc_file.is_file():
        raise FileNotFoundError(f"Missing {psc_file}")

    out_scripts_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fo4sf_whome_cr_") as td:
        cr_root = Path(td)
        with zipfile.ZipFile(cr_zip, "r") as zf:
            for member in zf.namelist():
                low = member.lower()
                if low.endswith(".psc") or low.endswith(".flg"):
                    zf.extract(member, cr_root)
        src_base = cr_root / "Scripts" / "Source"
        flg = src_base / "Starfield_Papyrus_Flags.flg"
        if not flg.is_file():
            for p in cr_root.rglob("Starfield_Papyrus_Flags.flg"):
                flg = p
                break
        if not flg.is_file():
            raise FileNotFoundError("Starfield_Papyrus_Flags.flg missing in ContentResources.zip")

        inc_parts = [str(src_base)]
        if (src_base / "Base").is_dir():
            inc_parts.insert(0, str(src_base / "Base"))
        inc_parts.append(str(psc_dir))
        cmd = [
            str(compiler),
            "FO4SF_PipboyTravel.psc",
            f"-f={flg}",
            f"-i={';'.join(inc_parts)}",
            f"-o={out_scripts_dir}",
        ]
        proc = subprocess.run(cmd, cwd=str(psc_dir), capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"PapyrusCompiler.exe failed ({proc.returncode}): {proc.stdout}\n{proc.stderr}")

    pex = out_scripts_dir / "FO4SF_PipboyTravel.pex"
    if not pex.is_file():
        raise RuntimeError(f"Compiled FO4SF_PipboyTravel.pex missing at {pex}")
    return pex


def _copy_stage_file(src: Path, dst: Path) -> str:
    """Copy a file into stage without hardlinks (`st_nlink == 1`), returning its SHA-256."""
    probe_common.copy_or_link_staged_file(src, dst, allow_hardlink=False)
    return probe_common.sha256_file(dst)


def _pack_plugin_scripts_ba2(scripts_map: Mapping[str, Path], ba2_path: Path) -> Optional[Path]:
    """Pack `{Scripts/<name>.pex: Path}` into `<Plugin> - Main.ba2` and verify hashes."""
    if not scripts_map:
        return None
    probe_common.pack_gnrl_ba2(dict(sorted(scripts_map.items())), ba2_path, compress=True)
    probe_common.verify_ba2_entry_hashes(ba2_path, source_files=dict(scripts_map))
    return ba2_path


def _pack_home_ba2s(
    home_stage_dir: Path,
    travel_pex: Path,
    data_out: Path,
    mission_pex_paths: Sequence[Path] = (),
    newgame_pex_paths: Sequence[Path] = (),
) -> List[Path]:
    """Pack Home (`Main`/`Textures`), Travel, and optional 1i Mission/NewGame script BA2 archives."""
    data_out.mkdir(parents=True, exist_ok=True)
    home_data = home_stage_dir / "Data"
    gnrl_entries: List[Tuple[str, Path]] = []
    dx10_entries: List[Tuple[str, Path]] = []

    if home_data.is_dir():
        for p in sorted(home_data.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(home_data).as_posix()
            if rel.lower().startswith("textures/") and rel.lower().endswith(".dds"):
                dx10_entries.append((rel, p))
            else:
                gnrl_entries.append((rel, p))

    created: List[Path] = []
    if gnrl_entries:
        main_ba2 = data_out / "FO4SFHome - Main.ba2"
        probe_common.pack_gnrl_ba2(gnrl_entries, main_ba2, compress=True)
        probe_common.verify_ba2_entry_hashes(main_ba2, source_files=dict(gnrl_entries))
        created.append(main_ba2)

    if dx10_entries:
        tex_ba2 = data_out / "FO4SFHome - Textures.ba2"
        probe_common.pack_dx10_ba2(dx10_entries, tex_ba2, compress=True)
        probe_common.verify_ba2_entry_hashes(tex_ba2, source_files=dict(dx10_entries))
        created.append(tex_ba2)

    for archive_name, pex_list in (
        ("FO4SFPipboyTravel - Main.ba2", [travel_pex]),
        ("FO4SFMission - Main.ba2", list(mission_pex_paths)),
        ("FO4SFNewGame - Main.ba2", list(newgame_pex_paths)),
    ):
        entries = {f"Scripts/{p.name}": p for p in pex_list if p is not None and p.is_file()}
        packed = _pack_plugin_scripts_ba2(entries, data_out / archive_name)
        if packed is not None:
            created.append(packed)
    return created


def _build_ini_for_stage(baseline_dir: Path, out_ini: Path) -> None:
    """Generate a Stage=2 INI preserving the Fallout 4 shell/page kit with `MapBlockStarMap=1`, `MapSurvival=0`."""
    with tempfile.TemporaryDirectory(prefix="fo4sf_whome_ini_") as td:
        tmp_stage = Path(td) / "pb_stage"
        iface_dst = tmp_stage / "Data" / "Interface"
        iface_dst.mkdir(parents=True, exist_ok=True)
        src_iface = baseline_dir / "Data" / "Interface"
        if not src_iface.is_dir():
            raise FileNotFoundError(f"Baseline Interface SWFs missing at {src_iface}")
        for swf in src_iface.glob("*.swf"):
            shutil.copy2(swf, iface_dst / swf.name)
        src_comp = src_iface / "Components"
        if src_comp.is_dir():
            shutil.copytree(src_comp, iface_dst / "Components", dirs_exist_ok=True)

        # Preserve shipped Stage=2 Fallout 4 shell with StarMap block enabled in this test probe only (`MapSurvival=0`).
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
            map_block_starmap=1,
        )
        make_pipboy_stage_ini.assert_no_kit_entries(out_ini.read_text(encoding="utf-8"))


def _stage_script_dir(src_dir: Optional[Path], scripts_out: Path) -> List[Path]:
    """Copy `.pex` scripts from `src_dir` into `scripts_out` and return their staged paths."""
    if src_dir is None:
        return []
    if not src_dir.is_dir():
        raise FileNotFoundError(f"Missing scripts directory: {src_dir}")
    copied: List[Path] = []
    for src_pex in sorted(src_dir.glob("*.pex")):
        dst_pex = scripts_out / src_pex.name
        _copy_stage_file(src_pex, dst_pex)
        copied.append(dst_pex)
    if not copied:
        raise FileNotFoundError(f"No .pex files found in scripts directory: {src_dir}")
    return copied


def stage_probe(
    *,
    starfield_dir: Path,
    out_dir: Path,
    baseline_dir: Path,
    port_esm: Path,
    map_markers_esm: Path,
    pipboy_dll: Path,
    pipboy_build_json: Optional[Path] = None,
    mission_esm: Optional[Path] = None,
    newgame_esm: Optional[Path] = None,
    mission_scripts_dir: Optional[Path] = None,
    newgame_scripts_dir: Optional[Path] = None,
    core_esm: Optional[Path] = None,
    ground_source_dir: Optional[Path] = None,
    travel_pex_override: Optional[Path] = None,
    core_values_override: Optional[Path] = None,
    clean: bool = False,
    min_free_gb: float = MIN_FREE_GB,
) -> Dict[str, Any]:
    """Build and verify the self-contained `w-home` probe staging folder."""
    probe_common.check_starfield_not_running()
    probe_common.check_free_space_gb(out_dir.parent if out_dir.parent.exists() else out_dir, min_gb=min_free_gb)
    probe_common.check_out_dir_safe(out_dir, clean=clean)

    sf_data = starfield_dir / "Data"
    sf_esm = sf_data / "Starfield.esm"
    if not sf_esm.is_file():
        raise FileNotFoundError(f"Starfield.esm missing at {sf_esm}")

    core_src = core_esm or (baseline_dir / "FO4TerrainCore.esm")
    mission_src = mission_esm or (baseline_dir / "FO4SFMission.esm")
    newgame_src = newgame_esm or (baseline_dir / "FO4SFNewGame.esm")
    for label, p in (
        ("FO4TerrainCore.esm", core_src),
        ("FO4Port.esm", port_esm),
        ("FO4SFMapMarkers.esm", map_markers_esm),
        ("FO4SFMission.esm", mission_src),
        ("FO4SFNewGame.esm", newgame_src),
        ("FO4SFPipboyMenu.dll", pipboy_dll),
    ):
        if not p.is_file():
            raise FileNotFoundError(f"Missing required input {label}: {p}")

    ground_dir = ground_source_dir
    if ground_dir is None:
        cand_ground = baseline_dir / "Data" / "textures" / "fo4core" / "landscape" / "ground"
        if cand_ground.is_dir():
            ground_dir = cand_ground

    # Stage inside clean sub-staging before copying/verifying target files
    out_dir.mkdir(parents=True, exist_ok=True)
    data_out = out_dir / "Data"
    sfse_out = data_out / "SFSE" / "Plugins"
    scripts_out = data_out / "Scripts"
    bat_out = out_dir / "bat"
    for d in (data_out, sfse_out, scripts_out, bat_out):
        d.mkdir(parents=True, exist_ok=True)

    # 1. CoreValues (--commonwealth-weather 0 equivalent: 0 Mars CLMT/ATMO overrides)
    weather_flags = home_world_install.core_values_weather_flags(
        str(REPO_ROOT / "dotnet" / "CoreValues" / "Program.cs")
    )
    if core_values_override is not None:
        _copy_stage_file(core_values_override, data_out / "FO4SFCoreValues.esm")
    else:
        with tempfile.TemporaryDirectory(prefix="fo4sf_whome_cv_") as td:
            rc_cv = make_core_values.main(["stage", "--sf-data", str(sf_data), "--out", td, *weather_flags])
            if rc_cv != 0:
                raise RuntimeError(f"make_core_values stage failed ({rc_cv})")
            _copy_stage_file(Path(td) / "Data" / "FO4SFCoreValues.esm", data_out / "FO4SFCoreValues.esm")

    # 2. Home world ESMs + .biom + ground (.mat + .dds), overriding 0x01000802 & FO4Port 0x0100E18A
    home_stage = out_dir / "_home_stage"
    make_home_planet.stage_one(
        data_dir=str(sf_data),
        out_dir=str(home_stage),
        worlds=("Commonwealth",),
        star_name=hspec.DEFAULT_STAR_NAME,
        planet_name="Earth",
        body_name=hspec.DEFAULT_BODY_NAME,
        lever_keywords=WHOME_LEVER_KEYWORDS,
        extra_world_dirs=[str(core_src.parent)],
        map_markers_path=str(map_markers_esm),
        ground_ltex="ours",
        ground_source_dir=str(ground_dir) if ground_dir else "",
        port_plugin_path=str(port_esm),
        require_port=True,
    )
    _copy_stage_file(home_stage / "FO4SFHome.esm", data_out / "FO4SFHome.esm")
    _copy_stage_file(home_stage / "FO4TerrainCore_Home.esm", data_out / "FO4TerrainCore_Home.esm")
    _copy_stage_file(port_esm, data_out / "FO4Port.esm")
    _copy_stage_file(map_markers_esm, data_out / "FO4SFMapMarkers.esm")
    _copy_stage_file(mission_src, data_out / "FO4SFMission.esm")
    _copy_stage_file(newgame_src, data_out / "FO4SFNewGame.esm")

    # 3. Copy loose Data/ files generated by home_stage (PlanetData, materials, textures)
    home_data_dir = home_stage / "Data"
    for p in sorted(home_data_dir.rglob("*")):
        if p.is_file():
            rel = p.relative_to(home_data_dir)
            _copy_stage_file(p, data_out / rel)

    # 4. Pip-Boy DLL + optional build.json (F15), INI (Stage=2, MapBlockStarMap=1, MapSurvival=0), MapMarkers TSV, Travel ESM+PEX
    _copy_stage_file(pipboy_dll, sfse_out / "FO4SFPipboyMenu.dll")
    build_json_src = pipboy_build_json
    if build_json_src is None:
        for cand_name in ("build.json", "FO4SFPipboyMenu.build.json"):
            cand_p = pipboy_dll.parent / cand_name
            if cand_p.is_file():
                build_json_src = cand_p
                break
    pipboy_build_json_sha256: Optional[str] = None
    if build_json_src is not None:
        if not build_json_src.is_file():
            raise FileNotFoundError(f"Missing FO4SFPipboyMenu build.json: {build_json_src}")
        pipboy_build_json_sha256 = _copy_stage_file(build_json_src, sfse_out / "FO4SFPipboyMenu.build.json")
    _build_ini_for_stage(baseline_dir, sfse_out / "FO4SFPipboyMenu.ini")

    store_rows = pipboy_map_store.build_store_rows(
        str(core_src),
        markers_esm=str(map_markers_esm),
        include_diamond_city=True,
    )
    tsv_path = sfse_out / "FO4SFPipboyMapMarkers.tsv"
    pipboy_map_store.write_store_tsv(str(tsv_path), store_rows)
    pipboy_map_store.main(["stage-travel-esm", "--store", str(tsv_path), "--out", str(data_out / "FO4SFPipboyTravel.esm")])

    if travel_pex_override is not None:
        pex_path = scripts_out / "FO4SF_PipboyTravel.pex"
        _copy_stage_file(travel_pex_override, pex_path)
    else:
        pex_path = _compile_travel_pex(starfield_dir, scripts_out)

    mission_pex_paths = _stage_script_dir(mission_scripts_dir, scripts_out)
    newgame_pex_paths = _stage_script_dir(newgame_scripts_dir, scripts_out)

    # 5. Pack GNRL & DX10 BA2s
    _pack_home_ba2s(
        home_stage,
        pex_path,
        data_out,
        mission_pex_paths=mission_pex_paths,
        newgame_pex_paths=newgame_pex_paths,
    )
    shutil.rmtree(home_stage, ignore_errors=True)

    # 6. Write & validate P3 batches + <180m/axis hops
    anchors, hops, batches = _build_batch_plan()
    batch_paths: List[Path] = []
    for fname, body in batches:
        bp = bat_out / fname
        bp.write_text(body, encoding="utf-8", newline="\n")
        batch_paths.append(bp)
    probe_common.validate_batches_and_hops(
        batch_files=batch_paths,
        anchors=anchors,
        hops=hops,
        max_axis_m=MAX_HOP_AXIS_M,
        raise_on_error=True,
    )

    # 7. Cleanliness & zero-Mars winning location census across full load order.
    # (FO4SFMapMarkers.esm is audited below via check_load_order_overrides with pinned_map_markers_sha256.)
    non_host_esms = [
        data_out / "FO4Port.esm",
        data_out / "FO4SFCoreValues.esm",
        data_out / "FO4SFMission.esm",
        data_out / "FO4SFNewGame.esm",
        data_out / "FO4SFPipboyTravel.esm",
    ]
    probe_common.scan_plugin_cleanliness(
        non_host_esms,
        reference_esms=[core_src, port_esm],
        raise_on_error=True,
    )

    full_order: List[str] = []
    raider_src = baseline_dir / "FO4ActorRaider.esm"
    if raider_src.is_file():
        full_order.append(str(raider_src))
    full_order.extend([str(core_src), str(data_out / "FO4Port.esm"), str(data_out / "FO4SFMapMarkers.esm")])
    full_order.append(str(data_out / "FO4SFCoreValues.esm"))
    for opt_name in (
        "FO4SFVaultGearDoor.esm",
        "FO4SFExitLift.esm",
        "FO4SFWorkshop.esm",
        "FO4SFPowerArmor.esm",
        "FO4SFFortHagen.esm",
        "FO4SFPipboyProbe.esm",
    ):
        opt_p = baseline_dir / opt_name
        if opt_p.is_file():
            full_order.append(str(opt_p))
    full_order.extend(
        [
            str(data_out / "FO4SFMission.esm"),
            str(data_out / "FO4SFNewGame.esm"),
            str(data_out / "FO4SFHome.esm"),
            str(data_out / "FO4TerrainCore_Home.esm"),
            str(data_out / "FO4SFPipboyTravel.esm"),
        ]
    )
    census_probs, census_summary = hspec.audit_zero_mars_references(full_order)
    if census_probs:
        raise probe_common.ProbeValidationError(f"w-home zero-Mars audit failed: {census_probs}")
    ov_probs = hspec.check_load_order_overrides(
        full_order,
        allow_map_markers_pair=True,
        pinned_map_markers_sha256=probe_common.sha256_file(data_out / "FO4SFMapMarkers.esm"),
    )
    if ov_probs:
        raise probe_common.ProbeValidationError(f"w-home load-order override audit failed: {ov_probs}")

    census_payload = {"problems": census_probs, "override_problems": ov_probs, "summary": census_summary}
    (out_dir / CENSUS_NAME).write_text(json.dumps(census_payload, indent=2) + "\n", encoding="utf-8", newline="\n")

    # 8. Build probe_manifest.json for atomic install_probe / uninstall_probe
    swap_targets = {
        "Data/FO4Port.esm",
        "Data/FO4SFMapMarkers.esm",
        "Data/FO4SFCoreValues.esm",
        "Data/FO4SFMission.esm",
        "Data/FO4SFNewGame.esm",
        "Data/FO4SFPipboyTravel.esm",
        "Data/FO4SFMission - Main.ba2",
        "Data/FO4SFNewGame - Main.ba2",
        "Data/FO4SFPipboyTravel - Main.ba2",
        "Data/Scripts/FO4SF_PipboyTravel.pex",
        *(f"Data/Scripts/{p.name}" for p in mission_pex_paths),
        *(f"Data/Scripts/{p.name}" for p in newgame_pex_paths),
        "Data/SFSE/Plugins/FO4SFPipboyMenu.dll",
        "Data/SFSE/Plugins/FO4SFPipboyMenu.build.json",
        "Data/SFSE/Plugins/FO4SFPipboyMenu.ini",
        "Data/SFSE/Plugins/FO4SFPipboyMapMarkers.tsv",
    }
    file_entries: List[Dict[str, Any]] = []
    for p in sorted(data_out.rglob("*")):
        if not p.is_file():
            continue
        rel_data = p.relative_to(data_out).as_posix()
        tgt_rel = f"Data/{rel_data}"
        src_rel = f"Data/{rel_data}"
        file_entries.append(
            {
                "src_rel": src_rel,
                "target_rel": tgt_rel,
                "sha256": probe_common.sha256_file(p),
                "allow_swap": tgt_rel in swap_targets,
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

    plugins_to_activate = [
        "FO4Port.esm",
        "FO4SFMapMarkers.esm",
        "FO4SFCoreValues.esm",
        "FO4SFMission.esm",
        "FO4SFNewGame.esm",
        "FO4SFHome.esm",
        "FO4TerrainCore_Home.esm",
        "FO4SFPipboyTravel.esm",
    ]
    manifest = {
        "schema": "fo4sf.w_home_manifest.v1",
        "probe_id": PROBE_ID,
        "core_values_weather_flags": weather_flags,
        "plugins_to_activate": plugins_to_activate,
        "plugins_to_untick": [home_world_install.MARS_PLUGIN],
        "marker_rows": len(store_rows),
        "pipboy_dll_sha256": probe_common.sha256_file(sfse_out / "FO4SFPipboyMenu.dll"),
        "pipboy_build_json_sha256": pipboy_build_json_sha256,
        "census": census_summary,
        "files": file_entries,
    }
    (out_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def _sync_untick_mars_receipt(
    starfield_dir: Path,
    plugins_txt_path: Optional[Path],
    untick_names: Iterable[str],
) -> None:
    """After `probe_common.install_probe`, untick `FO4TerrainCore_Mars.esm` in `Plugins.txt` and sync planned bytes."""
    plg_path = (
        plugins_txt_path
        if plugins_txt_path is not None
        else Path(home_world_install.exp_install.plugins_txt())
    )
    cur_raw = plg_path.read_bytes()
    lines, bom, nl = home_world_install.exp_install.plugin_lines(cur_raw)
    updated_lines = list(lines)
    unticked_records: List[Dict[str, str]] = []
    for name in untick_names:
        updated_lines, did = home_world_install._untick_plugin_lines(updated_lines, name)
        for item in did:
            unticked_records.append({"active": item["original"].strip(), "original": item["unticked"]})
    if updated_lines == lines:
        return

    new_bytes = deploy_starfield.render_lines(updated_lines, cur_raw)
    deploy_starfield.atomic_write_bytes(str(plg_path), new_bytes, ".fo4sf-whome-", expected_current=cur_raw)

    rcpt_p = starfield_dir / "Data" / f".fo4sf_probe_{PROBE_ID}.json"
    receipt = json.loads(rcpt_p.read_text(encoding="utf-8"))
    receipt["plugins_planned_b64"] = base64.b64encode(new_bytes).decode("ascii")
    # Preserve `plugins_original_b64` so uninstall_probe restores `*FO4TerrainCore_Mars.esm` cleanly.
    tmp_p = rcpt_p.with_suffix(".tmp")
    tmp_p.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp_p, rcpt_p)


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
    manifest = json.loads((stage_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    receipt = probe_common.install_probe(
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
    try:
        _sync_untick_mars_receipt(starfield_dir, plugins_txt, manifest.get("plugins_to_untick", ()))
        plg_path = plugins_txt if plugins_txt is not None else Path(home_world_install.exp_install.plugins_txt())
        cur_lines, _, _ = home_world_install.exp_install.plugin_lines(plg_path.read_bytes())
        dual_err = home_world_install.check_no_dual_host_active(cur_lines)
        if dual_err:
            raise probe_common.ProbeInstallError(dual_err)
        load_errs = home_world_install.validate_active_load_order(
            cur_lines,
            data_dir=str(starfield_dir / "Data"),
            pinned_map_markers_sha256=probe_common.sha256_file(stage_dir / "Data" / "FO4SFMapMarkers.esm"),
        )
        if load_errs:
            raise probe_common.ProbeInstallError("; ".join(load_errs))
    except Exception:
        probe_common.uninstall_probe(probe_id=PROBE_ID, starfield_dir=starfield_dir, force=True, system=system)
        raise
    return receipt


def _verify_staged_ba2s(stage_dir: Path) -> List[str]:
    """Verify every staged BA2 archive matches the corresponding loose staged Data files."""
    data_dir = stage_dir / "Data"
    scripts_dir = data_dir / "Scripts"
    verified: List[str] = []

    home_gnrl: Dict[str, Path] = {}
    home_dx10: Dict[str, Path] = {}
    for p in sorted(data_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(data_dir).as_posix()
        low = rel.lower()
        if low.startswith("planetdata/") or low.startswith("materials/"):
            home_gnrl[rel] = p
        elif low.startswith("textures/") and low.endswith(".dds"):
            home_dx10[rel] = p

    for ba2_name, entries in (
        ("FO4SFHome - Main.ba2", home_gnrl),
        ("FO4SFHome - Textures.ba2", home_dx10),
    ):
        ba2_p = data_dir / ba2_name
        if ba2_p.is_file():
            probe_common.verify_ba2_entry_hashes(ba2_p, source_files=entries)
            verified.append(ba2_name)

    if scripts_dir.is_dir():
        all_pex = {f"Scripts/{p.name}": p for p in sorted(scripts_dir.glob("*.pex"))}
        travel_entries = {k: v for k, v in all_pex.items() if k.endswith("/FO4SF_PipboyTravel.pex")}
        ng_entries = {k: v for k, v in all_pex.items() if "/FO4SF_NewGame" in k}
        mission_entries = {k: v for k, v in all_pex.items() if k not in travel_entries and k not in ng_entries}
        for ba2_name, entries in (
            ("FO4SFPipboyTravel - Main.ba2", travel_entries),
            ("FO4SFMission - Main.ba2", mission_entries),
            ("FO4SFNewGame - Main.ba2", ng_entries),
        ):
            ba2_p = data_dir / ba2_name
            if ba2_p.is_file():
                probe_common.verify_ba2_entry_hashes(ba2_p, source_files=entries)
                verified.append(ba2_name)
    return verified


def verify_staged_probe(
    stage_dir: Path,
    *,
    require_base_port: bool = False,
    starfield_dir: Optional[Path] = None,
    core_esm: Optional[Path] = None,
    baseline_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Verify an already-staged `w-home` folder offline (`manifest`, `nlink==1`, INI, F14, P3/hops, BA2, census)."""
    man_path = stage_dir / MANIFEST_NAME
    if not man_path.is_file():
        raise FileNotFoundError(f"Missing {MANIFEST_NAME} in {stage_dir}")
    manifest = json.loads(man_path.read_text(encoding="utf-8"))

    if manifest.get("core_values_weather_flags") != ["--commonwealth-weather", "0"]:
        raise probe_common.ProbeValidationError(
            f"core_values_weather_flags={manifest.get('core_values_weather_flags')!r}, expected ['--commonwealth-weather', '0']"
        )
    if manifest.get("plugins_to_untick") != [home_world_install.MARS_PLUGIN]:
        raise probe_common.ProbeValidationError(
            f"plugins_to_untick={manifest.get('plugins_to_untick')!r} != {[home_world_install.MARS_PLUGIN]!r}"
        )

    files = manifest.get("files") or []
    if not files:
        raise probe_common.ProbeValidationError(f"{MANIFEST_NAME} contains zero file entries")
    for entry in files:
        src_p = stage_dir / entry["src_rel"]
        if src_p.is_symlink():
            raise probe_common.ProbeValidationError(f"Symlink forbidden in stage: {src_p}")
        if not src_p.is_file():
            raise probe_common.ProbeValidationError(f"Missing staged file: {src_p}")
        if os.stat(src_p).st_nlink != 1:
            raise probe_common.ProbeValidationError(f"Hardlink forbidden in stage (st_nlink != 1): {src_p}")
        act_sha = probe_common.sha256_file(src_p)
        if act_sha != entry["sha256"]:
            raise probe_common.ProbeValidationError(f"SHA-256 mismatch on {entry['src_rel']}: {act_sha} != {entry['sha256']}")

    data_dir = stage_dir / "Data"
    ini_path = data_dir / "SFSE" / "Plugins" / "FO4SFPipboyMenu.ini"
    ini_text = ini_path.read_text(encoding="utf-8")
    for req in ("Stage=2", "Map=1", "MapBlockStarMap=1", "MapSurvival=0"):
        if req not in ini_text:
            raise probe_common.ProbeValidationError(f"{ini_path.name} missing required setting {req!r}")
    make_pipboy_stage_ini.assert_no_kit_entries(ini_text)

    with esm.Plugin(str(data_dir / "FO4SFHome.esm")) as hm:
        pndt_recs = list(hm.records("PNDT", [b"PNDT"]))
        if len(pndt_recs) != 1 or pndt_recs[0].edid != "FO4SF_EarthPlanetData":
            edids = [r.edid for r in pndt_recs]
            raise probe_common.ProbeValidationError(f"FO4SFHome.esm PNDT EDID={edids!r}, expected ['FO4SF_EarthPlanetData']")
        stdt_recs = list(hm.records("STDT", [b"STDT"]))
        if len(stdt_recs) != 1 or esm.zstring(stdt_recs[0].get(b"FULL") or b"") != "Sol":
            raise probe_common.ProbeValidationError("FO4SFHome.esm STDT FULL must be 'Sol' (F14)")
        sys_locs = [r for r in hm.records("LCTN", [b"LCTN"]) if (r.formid & 0xFFFFFF) == hspec.SYSTEM_LOC]
        if len(sys_locs) != 1 or esm.zstring(sys_locs[0].get(b"FULL") or b"") != "Sol":
            raise probe_common.ProbeValidationError("FO4SFHome.esm system LCTN FULL must be 'Sol' (F14)")

    if require_base_port:
        port_sha = probe_common.sha256_file(data_dir / "FO4Port.esm")
        if port_sha != BASE_PORT_ESM_SHA256:
            raise probe_common.ProbeValidationError(
                f"Data/FO4Port.esm sha256={port_sha} != base candidate-2g-fix4 {BASE_PORT_ESM_SHA256}"
            )

    verified_ba2s = _verify_staged_ba2s(stage_dir)

    anchors, hops, expected_batches = _build_batch_plan()
    expected_bat_names = sorted(name for name, _ in expected_batches)
    actual_bat_paths = sorted((stage_dir / "bat").glob("*.txt"))
    actual_bat_names = [p.name for p in actual_bat_paths]
    if actual_bat_names != expected_bat_names:
        raise probe_common.ProbeValidationError(f"Staged bat/*.txt {actual_bat_names} != expected {expected_bat_names}")
    probe_common.validate_batches_and_hops(
        batch_files=actual_bat_paths,
        anchors=anchors,
        hops=hops,
        max_axis_m=MAX_HOP_AXIS_M,
        raise_on_error=True,
    )

    census_path = stage_dir / CENSUS_NAME
    census_doc = json.loads(census_path.read_text(encoding="utf-8"))
    summary = census_doc.get("summary") or {}
    if census_doc.get("problems") or census_doc.get("override_problems"):
        raise probe_common.ProbeValidationError(f"{CENSUS_NAME} reports problems: {census_doc}")
    if summary.get("mars_planet_data_winning_refs") != 0 or summary.get("mars_surface_lctn_winning_refs") != 0:
        raise probe_common.ProbeValidationError(f"Zero-Mars check failed in {CENSUS_NAME}: {summary}")

    if starfield_dir is not None:
        base_dir = baseline_dir if baseline_dir is not None else (starfield_dir / "Data")
        core_src = core_esm if core_esm is not None else (base_dir / "FO4TerrainCore.esm")
        if not core_src.is_file():
            raise FileNotFoundError(f"Missing FO4TerrainCore.esm for live verify: {core_src}")
        non_host_esms = [
            data_dir / "FO4Port.esm",
            data_dir / "FO4SFCoreValues.esm",
            data_dir / "FO4SFMission.esm",
            data_dir / "FO4SFNewGame.esm",
            data_dir / "FO4SFPipboyTravel.esm",
        ]
        probe_common.scan_plugin_cleanliness(non_host_esms, reference_esms=[core_src, data_dir / "FO4Port.esm"], raise_on_error=True)
        full_order: List[str] = []
        raider_src = base_dir / "FO4ActorRaider.esm"
        if raider_src.is_file():
            full_order.append(str(raider_src))
        full_order.extend([str(core_src), str(data_dir / "FO4Port.esm"), str(data_dir / "FO4SFMapMarkers.esm"), str(data_dir / "FO4SFCoreValues.esm")])
        for opt_name in ("FO4SFVaultGearDoor.esm", "FO4SFExitLift.esm", "FO4SFWorkshop.esm", "FO4SFPowerArmor.esm", "FO4SFFortHagen.esm", "FO4SFPipboyProbe.esm"):
            opt_p = base_dir / opt_name
            if opt_p.is_file():
                full_order.append(str(opt_p))
        full_order.extend([str(data_dir / "FO4SFMission.esm"), str(data_dir / "FO4SFNewGame.esm"), str(data_dir / "FO4SFHome.esm"), str(data_dir / "FO4TerrainCore_Home.esm"), str(data_dir / "FO4SFPipboyTravel.esm")])
        c_probs, _ = hspec.audit_zero_mars_references(full_order)
        if c_probs:
            raise probe_common.ProbeValidationError(f"w-home zero-Mars verify failed: {c_probs}")
        ov_probs = hspec.check_load_order_overrides(
            full_order,
            allow_map_markers_pair=True,
            pinned_map_markers_sha256=probe_common.sha256_file(data_dir / "FO4SFMapMarkers.esm"),
        )
        if ov_probs:
            raise probe_common.ProbeValidationError(f"w-home override verify failed: {ov_probs}")

    return {
        "verified": True,
        "manifest_sha256": probe_common.sha256_file(man_path),
        "file_count": len(files),
        "ba2_verified": verified_ba2s,
        "batches": actual_bat_names,
        "base_port_verified": require_base_port,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Stage, verify, install, and uninstall w-home probe")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("stage", help="Stage w-home probe into an external directory")
    sp.add_argument("--starfield", required=True)
    sp.add_argument("--out", required=True)
    sp.add_argument("--baseline-dir", required=True)
    sp.add_argument("--port", required=True)
    sp.add_argument("--map-markers", required=True)
    sp.add_argument("--pipboy-dll", required=True)
    sp.add_argument("--pipboy-build-json", default="")
    sp.add_argument("--mission", default="")
    sp.add_argument("--newgame", default="")
    sp.add_argument("--mission-scripts-dir", default="")
    sp.add_argument("--newgame-scripts-dir", default="")
    sp.add_argument("--core", default="")
    sp.add_argument("--ground-source-dir", default="")
    sp.add_argument("--travel-pex", default="")
    sp.add_argument("--core-values", default="")
    sp.add_argument("--clean", action="store_true")
    sp.add_argument("--min-free-gb", type=float, default=MIN_FREE_GB)

    vp = sub.add_parser("verify", help="Verify a staged w-home probe folder offline")
    vp.add_argument("--dir", required=True)
    vp.add_argument("--require-base-port", action="store_true")
    vp.add_argument("--starfield", default="")
    vp.add_argument("--core", default="")
    vp.add_argument("--baseline-dir", default="")

    ip = sub.add_parser("install", help="Atomically install w-home probe into <STARFIELD_DIR>")
    ip.add_argument("--dir", required=True)
    ip.add_argument("--starfield", required=True)
    ip.add_argument("--plugins-txt", default="")
    ip.add_argument("--version-tag", default="")
    ip.add_argument("--card", default="")
    ip.add_argument("--min-free-gb", type=float, default=MIN_FREE_GB)

    up = sub.add_parser("uninstall", help="Atomically uninstall w-home probe from <STARFIELD_DIR>")
    up.add_argument("--starfield", required=True)
    up.add_argument("--force", action="store_true")

    stp = sub.add_parser("status", help="Inspect installed w-home probe status")
    stp.add_argument("--starfield", required=True)

    args = ap.parse_args(argv)
    if args.cmd == "stage":
        man = stage_probe(
            starfield_dir=Path(args.starfield),
            out_dir=Path(args.out),
            baseline_dir=Path(args.baseline_dir),
            port_esm=Path(args.port),
            map_markers_esm=Path(args.map_markers),
            pipboy_dll=Path(args.pipboy_dll),
            pipboy_build_json=Path(args.pipboy_build_json) if args.pipboy_build_json else None,
            mission_esm=Path(args.mission) if args.mission else None,
            newgame_esm=Path(args.newgame) if args.newgame else None,
            mission_scripts_dir=Path(args.mission_scripts_dir) if args.mission_scripts_dir else None,
            newgame_scripts_dir=Path(args.newgame_scripts_dir) if args.newgame_scripts_dir else None,
            core_esm=Path(args.core) if args.core else None,
            ground_source_dir=Path(args.ground_source_dir) if args.ground_source_dir else None,
            travel_pex_override=Path(args.travel_pex) if args.travel_pex else None,
            core_values_override=Path(args.core_values) if args.core_values else None,
            clean=args.clean,
            min_free_gb=args.min_free_gb,
        )
        print(
            f"staged w-home -> {args.out} (files={len(man['files'])}, "
            f"markers={man['marker_rows']}, mars_pndt={man['census']['mars_planet_data_winning_refs']}, "
            f"mars_surf={man['census']['mars_surface_lctn_winning_refs']})"
        )
        return 0
    if args.cmd == "verify":
        res = verify_staged_probe(
            Path(args.dir),
            require_base_port=bool(args.require_base_port),
            starfield_dir=Path(args.starfield) if args.starfield else None,
            core_esm=Path(args.core) if args.core else None,
            baseline_dir=Path(args.baseline_dir) if args.baseline_dir else None,
        )
        print(json.dumps(res, indent=2))
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
        res = probe_common.probe_status(probe_id=PROBE_ID, starfield_dir=Path(args.starfield))
        print(json.dumps(res, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
