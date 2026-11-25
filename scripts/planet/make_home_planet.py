"""Stage and verify our isolated home star system, home planet, our own weather/sky/Fallout-4-ground biome
(`FO4SFHome.esm`, `WB1`–`WB2`), and single host registration plugin (`FO4TerrainCore_Home.esm`, `WB3`),
plus `WL1`, `WB1`, and `WB2` swap-session comparison variants.

Usage:
  python scripts/planet/make_home_planet.py stage --data <Starfield Data> --out <stage dir>
      [--worlds Commonwealth] [--star-name "FO4SF Home"] [--planet-name "Earth"]
      [--body-name "fo4sf_home_earth"] [--temp 15.0]
      [--climate ours|ours_empty|ClimateUniqueNewAtlantis|DefaultClimate]
      [--sky ours|ATMO_Jemison|ATMO_Earth] [--ground-ltex ours|LDirtFootprints01]
      [--ground-source-dir <converted FO4 ground dir>]
      [--pattern PatternStyleFieldsHillsFieldsFlat|PatternStyleFieldsMixed|PatternStyleHillsRockyFieldsRocky]
      [--surface-tree none|ours_empty|EarthSurfaceTree] [--wb3-mode ours|passthrough]
      [--sun-preset SunPresetTypeG2|ours] [--orbital-meshes starfield|none] [--control-b7dc7f52]
      [--lever-keywords K1,K2] [--world-plugin-dir <extra dir>] [--map-markers <FO4SFMapMarkers.esm>]
  python scripts/planet/make_home_planet.py check --stage <stage dir> [--data <Starfield Data>]
  python scripts/planet/make_home_planet.py stage-wl1 --data <Starfield Data> --out <variants dir>
  python scripts/planet/make_home_planet.py stage-wb1 --data <Starfield Data> --out <variants dir>
  python scripts/planet/make_home_planet.py stage-wb2 --data <Starfield Data> --out <variants dir>

Refuses any output path inside a Git worktree or inside a game installation directory (`R4`).
Never modifies `FO4TerrainCore.esm`, `FO4SFMapMarkers.esm`, or any file in `<Starfield Data>`.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
if os.path.join(REPO, "src") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "src"))
if os.path.join(REPO, "scripts", "terrain") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "scripts", "terrain"))

from fo4_world_census import CensusPathError, refuse_unsafe_output_path  # noqa: E402
from fo4sf.planet import biom, esm, home_planet_spec as hspec, records, wb_records  # noqa: E402
import sf_location_census  # noqa: E402

PLAN_KIND = "home-world"
WL1_VARIANTS: Sequence[tuple[str, Sequence[str]]] = (
    ("00-baseline", ()),
    ("01-PCM_OverlayExclusionZone", ("PCM_OverlayExclusionZone",)),
    ("02-PCM_OverlayExclusionZone_HumanLocations", ("PCM_OverlayExclusionZone_HumanLocations",)),
    ("03-LocTypeNoPCMScanTreeContent", ("LocTypeNoPCMScanTreeContent",)),
    ("04-LocTypeNoPCMCreatureContent", ("LocTypeNoPCMCreatureContent",)),
    ("05-LocTypeSENotAllowed", ("LocTypeSENotAllowed",)),
    ("06-all5", hspec.LEVER_KEYWORD_EDIDS),
)
WB1_VARIANTS: Sequence[Tuple[str, str, str]] = (
    ("01-ours-clear-temperate", "ours", "ours"),
    ("02-starfield-control", "ClimateUniqueNewAtlantis", "ATMO_Jemison"),
)
WB2_VARIANTS: Sequence[Tuple[str, Dict[str, str]]] = (
    (
        "01-fo4-ground-flat-nosftr",
        {
            "ground_ltex": "ours",
            "pattern_style": wb_records.DEFAULT_TERRAIN_PATTERN_EDID,
            "surface_tree": "none",
            "sun_preset": "SunPresetTypeG2",
            "orbital_meshes": "starfield",
        },
    ),
    (
        "02-fo4-ground-flat-emptysftr",
        {
            "ground_ltex": "ours",
            "pattern_style": wb_records.DEFAULT_TERRAIN_PATTERN_EDID,
            "surface_tree": "ours_empty",
            "sun_preset": "SunPresetTypeG2",
            "orbital_meshes": "starfield",
        },
    ),
    (
        "03-fo4-ground-hills-control",
        {
            "ground_ltex": "ours",
            "pattern_style": wb_records.CONTROL_TERRAIN_PATTERN_EDID,
            "surface_tree": "EarthSurfaceTree",
            "sun_preset": "SunPresetTypeG2",
            "orbital_meshes": "starfield",
        },
    ),
    (
        "04-no-orbital-meshes-ours-sunp",
        {
            "ground_ltex": "ours",
            "pattern_style": wb_records.DEFAULT_TERRAIN_PATTERN_EDID,
            "surface_tree": "none",
            "sun_preset": "ours",
            "orbital_meshes": "none",
        },
    ),
)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def stage_files_inventory(stage_dir: str) -> Dict[str, str]:
    """Return `{rel_path: sha256}` of top-level `.esm` plugins and everything under `Data/`."""
    out: Dict[str, str] = {}
    for name in sorted(os.listdir(stage_dir)):
        if name.lower().endswith(".esm"):
            out[name] = sha256_file(os.path.join(stage_dir, name))
    data_sub = os.path.join(stage_dir, "Data")
    if os.path.isdir(data_sub):
        for root, dirs, files in os.walk(data_sub):
            dirs.sort()
            for fname in sorted(files):
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, stage_dir).replace(os.sep, "/")
                out[rel] = sha256_file(full)
    return out


def _new_partial_dir(final_dir: str) -> str:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = f"{final_dir}.partial-{stamp}-{os.getpid()}"
    cand, n = base, 1
    while os.path.exists(cand):
        cand = f"{base}-{n}"
        n += 1
    os.makedirs(cand)
    return cand


def _parse_csv_list(raw: str) -> List[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def stage_one(
    data_dir: str,
    out_dir: str,
    worlds: Sequence[str] = ("Commonwealth",),
    star_name: str = hspec.DEFAULT_STAR_NAME,
    planet_name: str = hspec.DEFAULT_PLANET_NAME,
    body_name: str = hspec.DEFAULT_BODY_NAME,
    temp_c: float = hspec.DEFAULT_TEMP_C,
    sky_atmo: str = hspec.DEFAULT_SKY_ATMO,
    lever_keywords: Sequence[str] = (),
    extra_world_dirs: Sequence[str] = (),
    map_markers_path: str = "",
    *,
    climate: str = hspec.DEFAULT_CLIMATE,
    ground_ltex: str = hspec.DEFAULT_GROUND_LTEX,
    ground_source_dir: str = "",
    pattern_style: str = hspec.DEFAULT_TERRAIN_PATTERN,
    surface_tree: str = hspec.DEFAULT_SURFACE_TREE,
    wb3_mode: str = hspec.DEFAULT_WB3_MODE,
    sun_preset: str = hspec.DEFAULT_SUN_PRESET,
    orbital_meshes: str = hspec.DEFAULT_ORBITAL_MESHES,
    port_plugin_path: str = "",
    require_port: bool = False,
    legacy_b7dc7f52: bool = False,
) -> Dict[str, Any]:
    final = os.path.abspath(out_dir)
    sf_path = os.path.join(os.path.abspath(data_dir), "Starfield.esm")
    if not os.path.isfile(sf_path):
        raise FileNotFoundError(f"Starfield.esm not found in {data_dir}")

    mm_abs = os.path.abspath(map_markers_path) if map_markers_path else ""
    if mm_abs and not os.path.isfile(mm_abs):
        raise FileNotFoundError(f"map-markers plugin not found: {map_markers_path}")

    port_abs = os.path.abspath(port_plugin_path) if port_plugin_path else ""
    if port_abs and not os.path.isfile(port_abs):
        raise FileNotFoundError(f"port plugin not found: {port_plugin_path}")

    ground_src_abs = os.path.abspath(ground_source_dir) if ground_source_dir else ""
    if ground_src_abs and not os.path.isdir(ground_src_abs):
        raise FileNotFoundError(f"ground-source-dir not found: {ground_source_dir}")

    search_dirs = [os.path.abspath(d) for d in extra_world_dirs if d] + [os.path.abspath(data_dir)]
    guard_inputs = [sf_path] + ([mm_abs] if mm_abs else []) + ([port_abs] if port_abs else []) + ([ground_src_abs] if ground_src_abs else []) + search_dirs
    refuse_unsafe_output_path(final, guard_inputs)
    if os.path.exists(final):
        raise FileExistsError(f"{final} already exists; stage into a new folder")

    sf_sha_before = sha256_file(sf_path)
    mm_sha_before = sha256_file(mm_abs) if mm_abs else None
    mm_name = os.path.basename(mm_abs) if mm_abs else None
    world_plugin_pins_before: Dict[str, str] = {}

    partial = _new_partial_dir(final)
    clean_body_name = body_name.strip()
    with esm.Plugin(sf_path) as sf:
        master_writer, master_report = hspec.build_home_master(
            sf,
            data_dir=data_dir,
            star_name=star_name,
            planet_name=planet_name,
            body_name=clean_body_name,
            temp_c=temp_c,
            sky_atmo=sky_atmo,
            lever_keywords=lever_keywords,
            climate=climate,
            ground_ltex=ground_ltex,
            pattern_style=pattern_style,
            surface_tree=surface_tree,
            sun_preset=sun_preset,
            orbital_meshes=orbital_meshes,
            wb3_mode=wb3_mode,
            legacy_b7dc7f52=legacy_b7dc7f52,
        )
        master_path = os.path.join(partial, hspec.HOME_MASTER)
        master_writer.write(master_path, compress=False)

        reg_writer, reg_report = hspec.build_home_registration(
            sf,
            master_path,
            world_plugin_dirs=search_dirs,
            world_keys=worlds,
            lever_keywords=lever_keywords,
            map_markers_path=mm_abs or None,
            wb3_mode=wb3_mode,
            port_plugin_path=port_abs or None,
            require_port=require_port,
        )
        reg_path = os.path.join(partial, hspec.HOME_REGISTRATION)
        reg_writer.write(reg_path, compress=False)

    port_ov = reg_report.get("port_interiors_override")
    port_used_abs = port_ov["path"] if port_ov else (port_abs or "")

    # Pin every referenced world plugin (e.g. FO4TerrainCore.esm, FO4Port.esm) and verify zero modification
    for mname in reg_report["masters"][2:]:
        if mm_name and mname.lower() == mm_name.lower():
            continue
        if port_used_abs and mname.lower() == os.path.basename(port_used_abs).lower():
            world_plugin_pins_before[mname] = sha256_file(port_used_abs)
            continue
        for sdir in search_dirs:
            cand = os.path.join(sdir, mname)
            if os.path.isfile(cand):
                world_plugin_pins_before[mname] = sha256_file(cand)
                break

    biome_fid = (1 << 24) | hspec.BIOME
    biome_map_report = biom.stage_uniform_biome_map(biome_fid, clean_body_name, hspec.HOME_MASTER, partial)

    ground_assets_report: Optional[Dict[str, Any]] = None
    if ground_ltex == "ours":
        ground_assets_report = wb_records.stage_home_ground_assets(
            partial,
            edid=wb_records.DEFAULT_GROUND_LTEX_EDID,
            ground_source_dir=ground_src_abs,
        )

    problems, check_summary = hspec.check_home_stage(
        sf_path,
        master_path,
        reg_path,
        data_dir=data_dir,
        expected_world_count=len(worlds),
        expected_levers=lever_keywords,
        map_markers_path=mm_abs or None,
        expected_climate=climate,
        expected_sky=sky_atmo,
        expected_ground_ltex=ground_ltex,
        expected_surface_tree=surface_tree,
        expected_wb3_mode=wb3_mode,
        port_plugin_path=port_used_abs or None,
    )
    if problems:
        raise records.PlanetError(f"home stage check failed: {problems}")

    if sha256_file(sf_path) != sf_sha_before:
        raise RuntimeError("Starfield.esm changed during stage")
    if mm_abs and sha256_file(mm_abs) != mm_sha_before:
        raise RuntimeError(f"{mm_name} changed during stage")
    for mname, old_sha in world_plugin_pins_before.items():
        if port_used_abs and mname.lower() == os.path.basename(port_used_abs).lower():
            if sha256_file(port_used_abs) != old_sha:
                raise RuntimeError(f"port plugin {mname} changed during stage")
            continue
        for sdir in search_dirs:
            cand = os.path.join(sdir, mname)
            if os.path.isfile(cand):
                if sha256_file(cand) != old_sha:
                    raise RuntimeError(f"world plugin {mname} changed during stage")
                break

    plugins = [hspec.HOME_MASTER, hspec.HOME_REGISTRATION]
    outputs = stage_files_inventory(partial)
    inputs_doc: Dict[str, Any] = {
        "Starfield.esm": {"sha256": sf_sha_before, "bytes": os.path.getsize(sf_path)},
        "world_plugins": world_plugin_pins_before,
    }
    if mm_abs and mm_name and mm_sha_before:
        inputs_doc["map_markers"] = {
            "plugin": mm_name,
            "sha256": mm_sha_before,
            "bytes": os.path.getsize(mm_abs),
        }
    biome_profile = (
        "our-weather-sky-fo4-ground"
        if (climate in ("ours", "ours_empty") and sky_atmo == "ours" and ground_ltex == "ours")
        else "no-life, Starfield-patterned"
    )
    plan: Dict[str, Any] = {
        "kind": PLAN_KIND,
        "version": 1,
        "plugins": plugins,
        "swaps_out": [hspec.MARS_REGISTRATION],
        "archive": "FO4SFHome - Main.ba2",
        "worlds": list(worlds),
        "lever_keywords": list(lever_keywords),
        "star_name": star_name,
        "planet_name": planet_name,
        "body_name": clean_body_name,
        "temp_c": float(temp_c),
        "climate": climate,
        "sky_atmo": sky_atmo,
        "ground_ltex": ground_ltex,
        "pattern_style": pattern_style,
        "surface_tree": surface_tree,
        "wb3_mode": wb3_mode,
        "wb3_status": "untested" if wb3_mode == "ours" else "passthrough",
        "sun_preset": sun_preset,
        "orbital_meshes": orbital_meshes,
        "biome_profile": biome_profile,
        "system_id": master_report["system_id"],
        "planet_id": master_report["planet_id"],
        "biome_formid": reg_report["biome_formid"],
        "surface_location_formid": reg_report["surface_parent_formid"],
        "biome_map": biome_map_report,
        "ground_assets": ground_assets_report,
        "port_interiors_override": (
            {k: v for k, v in port_ov.items() if k != "path"} if port_ov else None
        ),
        "map_markers_plugin": mm_name,
        "map_markers_sha256": mm_sha_before,
        "inputs": inputs_doc,
        "outputs": outputs,
    }
    write_json(os.path.join(partial, "field_sources.json"), master_report["field_sources"])
    write_json(
        os.path.join(partial, "offline_check.json"),
        {
            "problems": [],
            "summary": check_summary,
            "master": master_report,
            "registration": reg_report,
            "biome_map": biome_map_report,
            "ground_assets": ground_assets_report,
        },
    )
    write_json(os.path.join(partial, "plan.json"), plan)

    verify_extra_dirs = list(extra_world_dirs or ())
    if port_used_abs:
        port_dir = os.path.dirname(port_used_abs)
        if port_dir not in verify_extra_dirs:
            verify_extra_dirs.append(port_dir)
    verify_probs = verify_stage(
        partial,
        plan,
        data_dir,
        extra_world_dirs=verify_extra_dirs,
        port_plugin_path=port_used_abs or None,
    )
    if verify_probs:
        raise records.PlanetError(f"stage post-verification failed: {verify_probs}")

    os.replace(partial, final)
    return plan


def load_plan(stage_dir: str) -> Dict[str, Any]:
    plan_path = os.path.join(stage_dir, "plan.json")
    if not os.path.isfile(plan_path):
        raise ValueError(f"{plan_path} missing: not a home-world stage")
    with open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)
    if plan.get("kind") != PLAN_KIND or not plan.get("plugins") or not plan.get("outputs"):
        raise ValueError(f"{plan_path} is not a valid home-world plan")
    return plan


def verify_stage(
    stage_dir: str,
    plan: Dict[str, Any],
    data_dir: Optional[str] = None,
    *,
    extra_world_dirs: Sequence[str] = (),
    port_plugin_path: Optional[str] = None,
) -> List[str]:
    """Verify staged file hashes, `.biom` paths, `WB1`–`WB3` ground/weather/sky/override invariants, and `W2`–`WL2` checks."""
    problems: List[str] = []
    now = stage_files_inventory(stage_dir)
    for rel, expected_sha in plan["outputs"].items():
        if rel not in now:
            problems.append(f"{rel} missing from stage")
        elif now[rel] != expected_sha:
            problems.append(f"{rel} sha256 mismatch ({now[rel]} != {expected_sha})")
    extra = sorted(set(now) - set(plan["outputs"]))
    if extra:
        problems.append(f"unexpected files in stage: {extra}")
    if problems:
        return problems

    # Verify both .biom paths exist, carry TEST-STATION status, match PNDT ANAM, and name our BIOM FormID
    biom_body_name = plan.get("body_name") or plan["planet_name"]
    want_biom_paths = biom.stage_paths(biom_body_name, hspec.HOME_MASTER)
    want_biom_fid = f"{(1 << 24) | hspec.BIOME:08X}"
    path_status = ((plan.get("biome_map") or {}).get("path_status") or {})
    for rel in want_biom_paths:
        if path_status and path_status.get(rel) != "TEST-STATION":
            problems.append(f"{rel} path_status {path_status.get(rel)!r} != 'TEST-STATION'")
        full = os.path.join(stage_dir, *rel.split("/"))
        if not os.path.isfile(full):
            problems.append(f"biome map missing at {rel}")
            continue
        with open(full, "rb") as bf:
            parsed = biom.parse_biome_map(bf.read())
        if parsed["biomes"] != [want_biom_fid]:
            problems.append(f"{rel} header biomes {parsed['biomes']} != [{want_biom_fid}]")
        for fidx, face in enumerate(parsed["faces"]):
            if face["pixel_biomes"] != [want_biom_fid]:
                problems.append(f"{rel} face {fidx} pixel biomes {face['pixel_biomes']} != [{want_biom_fid}]")
            if face["resource_values"] != [0]:
                problems.append(f"{rel} face {fidx} has non-zero resource bytes {face['resource_values']}")

    # WB2: verify staged Fallout 4 ground .mat + .dds assets when ground_ltex == 'ours'
    if plan.get("ground_ltex") == "ours":
        ginfo = plan.get("ground_assets") or {}
        gfiles = ginfo.get("files") or []
        if len(gfiles) != 4:
            problems.append(f"WB2 ground_assets expected 4 files (.mat + 3 .dds), got {gfiles!r}")
        for rel in gfiles:
            full = os.path.join(stage_dir, *rel.split("/"))
            if not os.path.isfile(full):
                problems.append(f"WB2 ground asset missing: {rel}")
            elif rel.lower().endswith(".mat"):
                try:
                    with open(full, encoding="utf-8") as mf:
                        mdoc = json.load(mf)
                    if "Summary" not in mdoc:
                        problems.append(f"WB2 ground material {rel} missing Summary")
                except (OSError, ValueError) as exc:
                    problems.append(f"WB2 ground material {rel} invalid JSON: {exc}")

    master_path = os.path.join(stage_dir, hspec.HOME_MASTER)
    reg_path = os.path.join(stage_dir, hspec.HOME_REGISTRATION)
    for label, ppath in ((hspec.HOME_MASTER, master_path), (hspec.HOME_REGISTRATION, reg_path)):
        if os.path.isfile(ppath):
            with esm.Plugin(ppath) as plug:
                if any(m.lower() == "fo4wg1redrocket.esm" for m in plug.masters):
                    problems.append(f"{label} references forbidden FO4WG1RedRocket.esm")
                grp_order = list(plug.groups.keys())
                want_grp_order = [g for g in esm.GROUP_ORDER if g in plug.groups]
                if grp_order != want_grp_order:
                    problems.append(f"{label} top-group order {grp_order} != canonical {want_grp_order}")
                pndts = list(plug.records("PNDT", [b"PNDT"]))
                if pndts:
                    anam_b = records.body_get(pndts[0].subs, b"ANAM")
                    actual_anam = esm.zstring(anam_b) if anam_b else ""
                    if actual_anam != biom_body_name:
                        problems.append(f"{label} PNDT ANAM {actual_anam!r} != {biom_body_name!r}")
    problems.extend(hspec.check_no_duplicate_overrides([master_path, reg_path]))

    if data_dir:
        sf_path = os.path.join(data_dir, "Starfield.esm")
        if not os.path.isfile(sf_path):
            problems.append(f"Starfield.esm missing in {data_dir}")
            return problems
        sf_sha = sha256_file(sf_path)
        pinned_sf = ((plan.get("inputs") or {}).get("Starfield.esm") or {}).get("sha256")
        if pinned_sf and sf_sha != pinned_sf:
            problems.append(f"Starfield.esm changed since stage ({sf_sha} != {pinned_sf})")
        pinned_worlds = ((plan.get("inputs") or {}).get("world_plugins") or {})
        world_search = [os.path.abspath(d) for d in extra_world_dirs if d] + [os.path.abspath(data_dir)]
        for wname, wsha in pinned_worlds.items():
            for wdir in world_search:
                wp = os.path.join(wdir, wname)
                if os.path.isfile(wp):
                    if sha256_file(wp) != wsha:
                        problems.append(f"{wname} changed since stage ({sha256_file(wp)} != {wsha})")
                    break
        pinned_mm_sha = plan.get("map_markers_sha256")
        pinned_mm_name = plan.get("map_markers_plugin") or hspec.MAP_MARKERS_PLUGIN
        mm_check_path: Optional[str] = None
        if pinned_mm_sha:
            for mdir in [os.path.abspath(data_dir)] + [os.path.abspath(d) for d in extra_world_dirs if d]:
                cand_mm = os.path.join(mdir, pinned_mm_name)
                if os.path.isfile(cand_mm):
                    mm_check_path = cand_mm
                    actual_mm_sha = sha256_file(cand_mm)
                    if actual_mm_sha != pinned_mm_sha:
                        problems.append(f"{pinned_mm_name} changed since stage ({actual_mm_sha} != {pinned_mm_sha})")
                    break
        port_check_path: Optional[str] = os.path.abspath(port_plugin_path) if port_plugin_path else None
        if port_check_path and not os.path.isfile(port_check_path):
            problems.append(f"port plugin missing: {port_check_path}")
        if port_check_path is None and plan.get("port_interiors_override"):
            port_name = plan["port_interiors_override"].get("plugin") or hspec.PORT_PLUGIN
            for wdir in world_search:
                cand_port = os.path.join(wdir, port_name)
                if os.path.isfile(cand_port):
                    port_check_path = cand_port
                    break
            if port_check_path is None:
                problems.append(f"{port_name} missing in search dirs during port verification")
        chk_probs, _summary = hspec.check_home_stage(
            sf_path,
            master_path,
            reg_path,
            data_dir=data_dir,
            expected_world_count=len(plan.get("worlds", ["Commonwealth"])),
            expected_levers=plan.get("lever_keywords", ()),
            map_markers_path=mm_check_path,
            expected_climate=plan.get("climate"),
            expected_sky=plan.get("sky_atmo"),
            expected_ground_ltex=plan.get("ground_ltex"),
            expected_surface_tree=plan.get("surface_tree"),
            expected_wb3_mode=plan.get("wb3_mode"),
            port_plugin_path=port_check_path,
        )
        problems.extend(chk_probs)

    return problems


def _print_field_sources() -> None:
    for rtype, rows in (
        ("STDT", hspec.STAR_FIELD_SPEC),
        ("PNDT", hspec.PLANET_FIELD_SPEC),
        ("BIOM", hspec.BIOM_FIELD_SPEC),
        ("WTHR", wb_records.WTHR_FIELD_SPEC),
        ("CLMT", wb_records.CLMT_FIELD_SPEC),
        ("ATMO", wb_records.ATMO_FIELD_SPEC),
        ("LTEX", wb_records.LTEX_FIELD_SPEC),
    ):
        print(f"=== {rtype} Field Sources ===")
        for row in rows:
            print(f"  [{row['subrecord']}] {row['field']} = {row['value']}  <-- {row['source']}")
    print("=== WB3 Registration Overrides (untested) ===")
    for row in wb_records.WB3_OVERRIDE_SPEC:
        print(f"  [{row['record']} / {row['subrecord']}] {row['value']} ({row['status']})  <-- {row['why']}")


def _live_biom_and_pndt_refs(stage_dir: str, data_dir: Optional[str]) -> List[Dict[str, Any]]:
    master_path = os.path.join(stage_dir, hspec.HOME_MASTER)
    fallback_sf: Dict[int, Tuple[str, str]] = {}
    chk_json = os.path.join(stage_dir, "offline_check.json")
    if os.path.isfile(chk_json):
        with open(chk_json, encoding="utf-8") as f:
            chk_doc = json.load(f)
        for r in (chk_doc.get("summary") or {}).get("biom_and_pndt_references") or ():
            if (r.get("owner") or "").lower() == "starfield.esm":
                fid_int = int(r["form_id"], 16) & 0xFFFFFF
                fallback_sf[fid_int] = (r.get("record_type", "UNKNOWN"), r.get("edid", ""))

    sf_cand = os.path.join(data_dir, "Starfield.esm") if data_dir else ""
    with esm.Plugin(master_path) as hm:
        if sf_cand and os.path.isfile(sf_cand):
            with esm.Plugin(sf_cand) as sf:
                return wb_records.collect_biom_and_pndt_references(sf, hm, home_master_name=hspec.HOME_MASTER, fallback_sf_names=fallback_sf)
        return wb_records.collect_biom_and_pndt_references(None, hm, home_master_name=hspec.HOME_MASTER, fallback_sf_names=fallback_sf)


def cmd_stage(args: argparse.Namespace) -> int:
    worlds = _parse_csv_list(args.worlds)
    levers = _parse_csv_list(args.lever_keywords)
    extra_dirs = [args.world_plugin_dir] if args.world_plugin_dir else []
    if args.control_b7dc7f52:
        star_name = "FO4SF Home"
        body_name = "Earth"
        climate = "ClimateUniqueNewAtlantis"
        sky = "ATMO_Jemison"
        ground_ltex = "LDirtFootprints01"
        pattern_style = wb_records.CONTROL_TERRAIN_PATTERN_EDID
        surface_tree = "EarthSurfaceTree"
        wb3_mode = "passthrough"
        sun_preset = "SunPresetTypeG2"
        orbital_meshes = "starfield"
        legacy_b7dc7f52 = True
    else:
        star_name = args.star_name
        body_name = args.body_name
        climate = args.climate
        sky = args.sky
        ground_ltex = args.ground_ltex
        pattern_style = args.pattern
        surface_tree = args.surface_tree
        wb3_mode = args.wb3_mode
        sun_preset = args.sun_preset
        orbital_meshes = args.orbital_meshes
        legacy_b7dc7f52 = False

    plan = stage_one(
        data_dir=args.data,
        out_dir=args.out,
        worlds=worlds,
        star_name=star_name,
        planet_name=args.planet_name,
        body_name=body_name,
        temp_c=args.temp,
        sky_atmo=sky,
        lever_keywords=levers,
        extra_world_dirs=extra_dirs,
        map_markers_path=args.map_markers,
        climate=climate,
        ground_ltex=ground_ltex,
        ground_source_dir=args.ground_source_dir,
        pattern_style=pattern_style,
        surface_tree=surface_tree,
        wb3_mode=wb3_mode,
        sun_preset=sun_preset,
        orbital_meshes=orbital_meshes,
        port_plugin_path=getattr(args, "port", ""),
        require_port=bool(getattr(args, "require_port", False)),
        legacy_b7dc7f52=legacy_b7dc7f52,
    )
    print(
        f"staged {os.path.abspath(args.out)}: plugins={plan['plugins']}, "
        f"system_id={plan['system_id']}, planet_id={plan['planet_id']}, "
        f"body_name={plan['body_name']}, biome={plan['biome_formid']}, levers={plan['lever_keywords']}"
    )
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    plan = load_plan(args.stage)
    extra_dirs = [args.world_plugin_dir] if getattr(args, "world_plugin_dir", "") else []
    port_path = getattr(args, "port", "") or None
    problems = verify_stage(args.stage, plan, args.data or None, extra_world_dirs=extra_dirs, port_plugin_path=port_path)
    _print_field_sources()
    live_refs = _live_biom_and_pndt_refs(args.stage, args.data or None)
    print("=== BIOM & PNDT Form References ===")
    for r in live_refs:
        print(
            f"  [{r['record']} {r['subrecord']}] {r['field']} -> "
            f"{r['owner']}:{r['record_type']} {r['form_id']} ({r['edid']})"
        )
    print("=== Brings-Content Audit ===")
    by_field = {r["field"]: r for r in live_refs}
    clmt_r = by_field.get("climate")
    wthr_r = by_field.get("climate_weather")
    atmo_r = by_field.get("atmosphere")
    ltex_r = by_field.get("ground_ltex")
    sftr_r = by_field.get("surface_tree")
    ptst_r = by_field.get("terrain_pattern")
    for label, ref, staged_var in (
        ("climate (BIOM.ENAM + WRLD.CNAM)", clmt_r, "wb1-variants/01-ours-clear-temperate vs 02-starfield-control"),
        ("weather (CLMT.WLST)", wthr_r, "wb1-variants/01-ours-clear-temperate vs 02-starfield-control"),
        ("atmosphere (PNDT.INAM)", atmo_r, "wb1-variants/01-ours-clear-temperate vs 02-starfield-control"),
        ("land_texture (BIOM.LNAM[0..6])", ltex_r, "wb2-variants/01-fo4-ground-flat-nosftr"),
        ("surface_tree (PNDT.FNAM)", sftr_r, "wb2-variants/01-fo4-ground-flat-nosftr vs 02-fo4-ground-flat-emptysftr"),
    ):
        if ref is None:
            print(f"  {label}: empty (omitted) | variant: {staged_var}")
        elif ref["owner"].lower() != "starfield.esm":
            print(f"  {label}: empty (ours: {ref['owner']}:{ref['edid']} {ref['form_id']}) | variant: {staged_var}")
        else:
            print(f"  {label}: {ref['owner']}:{ref['record_type']} {ref['form_id']} ({ref['edid']}) | variant: {staged_var}")
    if ptst_r and ptst_r["owner"].lower() == "starfield.esm":
        print(
            f"  planet_pattern (BIOM.NNAM): {ptst_r['owner']}:{ptst_r['record_type']} {ptst_r['form_id']} ({ptst_r['edid']}) "
            "| reason: 46/46 PTST records hold only EDID (0 height fields; heights live in 258 SFPT->SFBK .btd banks "
            "with 392 B SFBK.FNAM seam tables unproven offline, and 0/431 BIOM omit NNAM); smallest 38.11 m span chosen "
            "| variant: wb2-variants/01-fo4-ground-flat-nosftr vs 03-fo4-ground-hills-control"
        )
    if plan.get("sun_preset", "SunPresetTypeG2") != "ours":
        print(
            "  sun_preset (STDT.PNAM): Starfield.esm:SUNP 0x00134249 (SunPresetTypeG2) "
            "| reason: 14 Nov G2 solar daylight disc/illuminance rule "
            "| variant: wb2-variants/04-no-orbital-meshes-ours-sunp (--sun-preset ours -> FO4SFHomeSunPreset 0x0100080D)"
        )
    else:
        print("  sun_preset (STDT.PNAM): empty (ours: FO4SFHome.esm:FO4SFHomeSunPreset 0x0100080D)")
    if plan.get("orbital_meshes", "starfield") != "none":
        print(
            "  orbital_meshes (PNDT.MODL, STDT.MODL): HoudiniPlanet.nif / HoudiniPlanet_star.nif "
            "| reason: untextured BSGalaxy unit spheres (0 PCCC/XMPM blobs; star map blocked in play) "
            "| variant: wb2-variants/04-no-orbital-meshes-ours-sunp (--orbital-meshes none)"
        )
    else:
        print("  orbital_meshes (PNDT.MODL, STDT.MODL): empty (omitted: --orbital-meshes none)")
    if plan.get("climate") in ("ours", "ours_empty"):
        bad_cw = [
            r
            for r in live_refs
            if r["owner"].lower() == "starfield.esm" and r["record_type"] in ("CLMT", "WTHR", "WTHS")
        ]
        if bad_cw:
            problems.append(f"WB1 check failed: Starfield climate/weather referenced: {bad_cw}")
    if plan.get("sky_atmo") == "ours":
        bad_atmo = [
            r
            for r in live_refs
            if r["owner"].lower() == "starfield.esm" and r["record_type"] == "ATMO"
        ]
        if bad_atmo:
            problems.append(f"WB1 check failed: Starfield atmosphere referenced: {bad_atmo}")

    chk_json = os.path.join(args.stage, "offline_check.json")
    if os.path.isfile(chk_json):
        with open(chk_json, encoding="utf-8") as f:
            chk = json.load(f)
        print("=== Stage Summary ===")
        print(json.dumps(chk.get("summary", {}), indent=2))
    for p in problems:
        print(f"FAIL  {p}", file=sys.stderr)
    print("check: " + ("ok" if not problems else f"{len(problems)} problem(s)"))
    return 0 if not problems else 1


def cmd_stage_wl1(args: argparse.Namespace) -> int:
    out_root = os.path.abspath(args.out)
    sf_path = os.path.join(os.path.abspath(args.data), "Starfield.esm")
    refuse_unsafe_output_path(out_root, [sf_path, os.path.abspath(args.data)])
    if os.path.exists(out_root):
        raise FileExistsError(f"{out_root} already exists; stage into a new folder")
    os.makedirs(out_root)

    worlds = _parse_csv_list(args.worlds)
    extra_dirs = [args.world_plugin_dir] if args.world_plugin_dir else []
    variant_reports: List[Dict[str, Any]] = []

    for slug, levers in WL1_VARIANTS:
        vdir = os.path.join(out_root, slug)
        plan = stage_one(
            data_dir=args.data,
            out_dir=vdir,
            worlds=worlds,
            body_name=getattr(args, "body_name", hspec.DEFAULT_BODY_NAME),
            lever_keywords=levers,
            extra_world_dirs=extra_dirs,
            map_markers_path=getattr(args, "map_markers", ""),
            ground_source_dir=getattr(args, "ground_source_dir", ""),
        )
        inspected = sf_location_census.inspect_host_plugins(
            sf_path,
            home_esm=os.path.join(vdir, hspec.HOME_MASTER),
            registration_esm=os.path.join(vdir, hspec.HOME_REGISTRATION),
        )
        census_out = os.path.join(vdir, "sf_location_census.json")
        sf_location_census.write_sf_census_json(census_out, inspected, [sf_path])

        want_flags = {k: (k in levers) for k in hspec.LEVER_KEYWORD_EDIDS}
        reg_locs = inspected["our_registration"]["locations"]
        home_surf = [loc for loc in inspected["our_home"]["locations"] if loc["local_id"] == f"0x{hspec.SURFACE_LOC:06X}"]
        if not reg_locs or len(home_surf) != 1:
            raise records.PlanetError(f"{slug}: missing registration or home surface location in census")
        for loc_row in reg_locs + home_surf:
            if loc_row["exclusion_levers_present"] != want_flags:
                raise records.PlanetError(
                    f"{slug}: {loc_row['edid']} levers {loc_row['exclusion_levers_present']} != {want_flags}"
                )

        variant_reports.append(
            {
                "variant": slug,
                "lever_keywords": list(levers),
                "registration_locations": [
                    {"edid": r["edid"], "parent": r["parent_lctn"], "levers": r["exclusion_levers_present"]}
                    for r in reg_locs
                ],
                "home_surface_location": {
                    "edid": home_surf[0]["edid"],
                    "levers": home_surf[0]["exclusion_levers_present"],
                },
                "outputs": plan["outputs"],
            }
        )

    summary_path = os.path.join(out_root, "wl1_summary.json")
    sf_location_census.write_sf_census_json(summary_path, {"variants": variant_reports}, [sf_path])
    print(f"staged {len(variant_reports)} WL1 variants under {out_root}")
    return 0


def cmd_stage_wb1(args: argparse.Namespace) -> int:
    out_root = os.path.abspath(args.out)
    sf_path = os.path.join(os.path.abspath(args.data), "Starfield.esm")
    refuse_unsafe_output_path(out_root, [sf_path, os.path.abspath(args.data)])
    if os.path.exists(out_root):
        raise FileExistsError(f"{out_root} already exists; stage into a new folder")
    os.makedirs(out_root)

    worlds = _parse_csv_list(args.worlds)
    extra_dirs = [args.world_plugin_dir] if args.world_plugin_dir else []
    rows: List[Dict[str, Any]] = []
    for slug, climate_opt, sky_opt in WB1_VARIANTS:
        vdir = os.path.join(out_root, slug)
        plan = stage_one(
            data_dir=args.data,
            out_dir=vdir,
            worlds=worlds,
            extra_world_dirs=extra_dirs,
            map_markers_path=args.map_markers,
            climate=climate_opt,
            sky_atmo=sky_opt,
            ground_source_dir=args.ground_source_dir,
        )
        rows.append(
            {
                "variant": slug,
                "climate": climate_opt,
                "sky_atmo": sky_opt,
                "owner_pick_status": "OWNER TEST (R8 — no variant is final)",
                "outputs": plan["outputs"],
            }
        )
    write_json(os.path.join(out_root, "wb1_summary.json"), {"variants": rows})
    print(f"staged {len(rows)} WB1 variants under {out_root}")
    return 0


def cmd_stage_wb2(args: argparse.Namespace) -> int:
    out_root = os.path.abspath(args.out)
    sf_path = os.path.join(os.path.abspath(args.data), "Starfield.esm")
    refuse_unsafe_output_path(out_root, [sf_path, os.path.abspath(args.data)])
    if os.path.exists(out_root):
        raise FileExistsError(f"{out_root} already exists; stage into a new folder")
    os.makedirs(out_root)

    worlds = _parse_csv_list(args.worlds)
    extra_dirs = [args.world_plugin_dir] if args.world_plugin_dir else []
    rows: List[Dict[str, Any]] = []
    for slug, opts in WB2_VARIANTS:
        vdir = os.path.join(out_root, slug)
        plan = stage_one(
            data_dir=args.data,
            out_dir=vdir,
            worlds=worlds,
            extra_world_dirs=extra_dirs,
            map_markers_path=args.map_markers,
            ground_ltex=opts["ground_ltex"],
            ground_source_dir=args.ground_source_dir,
            pattern_style=opts["pattern_style"],
            surface_tree=opts["surface_tree"],
            sun_preset=opts["sun_preset"],
            orbital_meshes=opts["orbital_meshes"],
        )
        rows.append(
            {
                "variant": slug,
                **opts,
                "owner_pick_status": "OWNER TEST (R8 — no variant is final)",
                "outputs": plan["outputs"],
            }
        )
    write_json(os.path.join(out_root, "wb2_summary.json"), {"variants": rows})
    print(f"staged {len(rows)} WB2 variants under {out_root}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Stage and check FO4SFHome.esm + FO4TerrainCore_Home.esm")
    sub = ap.add_subparsers(dest="cmd", required=True)

    st = sub.add_parser("stage", help="Stage FO4SFHome.esm, FO4TerrainCore_Home.esm, .biom maps, and FO4 outer-ring ground")
    st.add_argument("--data", required=True, help="Path to Starfield Data folder")
    st.add_argument("--out", required=True, help="Output stage directory (outside Git worktrees and game folders)")
    st.add_argument("--worlds", default="Commonwealth", help="Comma-separated world keys from world_registry.json")
    st.add_argument("--star-name", default=hspec.DEFAULT_STAR_NAME)
    st.add_argument("--planet-name", default=hspec.DEFAULT_PLANET_NAME)
    st.add_argument(
        "--body-name",
        default=hspec.DEFAULT_BODY_NAME,
        help="Internal PNDT ANAM body name and .biom stem (default: fo4sf_home_earth; control: Earth)",
    )
    st.add_argument("--temp", type=float, default=hspec.DEFAULT_TEMP_C)
    st.add_argument("--climate", choices=hspec.CLIMATE_CHOICES, default=hspec.DEFAULT_CLIMATE)
    st.add_argument("--sky", "--atmosphere", dest="sky", choices=hspec.SKY_ATMO_CHOICES, default=hspec.DEFAULT_SKY_ATMO)
    st.add_argument("--ground-ltex", choices=hspec.GROUND_LTEX_CHOICES, default=hspec.DEFAULT_GROUND_LTEX)
    st.add_argument("--ground-source-dir", default="", help="Optional directory of converted Fallout 4 ground PBR .dds maps")
    st.add_argument("--pattern", choices=hspec.TERRAIN_PATTERN_CHOICES, default=hspec.DEFAULT_TERRAIN_PATTERN)
    st.add_argument("--surface-tree", choices=hspec.SURFACE_TREE_CHOICES, default=hspec.DEFAULT_SURFACE_TREE)
    st.add_argument("--wb3-mode", choices=hspec.WB3_MODE_CHOICES, default=hspec.DEFAULT_WB3_MODE)
    st.add_argument("--sun-preset", choices=hspec.SUN_PRESET_CHOICES, default=hspec.DEFAULT_SUN_PRESET)
    st.add_argument("--orbital-meshes", choices=hspec.ORBITAL_MESHES_CHOICES, default=hspec.DEFAULT_ORBITAL_MESHES)
    st.add_argument(
        "--control-b7dc7f52",
        action="store_true",
        help="Reproduce the exact Round-1 b7dc7f52 control preset (R12)",
    )
    st.add_argument("--lever-keywords", default="", help="Comma-separated WL1 lever keyword EditorIDs")
    st.add_argument("--world-plugin-dir", default="", help="Optional extra folder searched for world ESMs before --data")
    st.add_argument(
        "--map-markers",
        default="",
        help="Optional FO4SFMapMarkers.esm path: merge core LCTN LCSR rows, add master, and pin sha256 in plan.json",
    )
    st.add_argument(
        "--port",
        default="",
        help="Optional FO4Port.esm path (defaults to searching --world-plugin-dir / --data for 0x00E18A re-parenting)",
    )
    st.add_argument(
        "--require-port",
        action="store_true",
        help="Fail stage if FO4Port.esm (0x00E18A FO4Port_InteriorsLocation) cannot be resolved and re-parented",
    )

    ck = sub.add_parser("check", help="Offline verification of a staged home-world folder")
    ck.add_argument("--stage", required=True, help="Path to staged home-world directory")
    ck.add_argument("--data", default="", help="Optional path to Starfield Data folder for live clash checks")
    ck.add_argument("--world-plugin-dir", default="", help="Optional extra folder searched for world ESMs before --data")
    ck.add_argument("--port", default="", help="Optional path to FO4Port.esm if not in --world-plugin-dir / --data")

    cn = sub.add_parser(
        "census",
        help="Offline winning-record census across an ordered plugin list proving zero MarsPlanetData/SSol_PMars_Surface refs",
    )
    cn.add_argument(
        "--plugins",
        required=True,
        help="Comma-separated list of .esm plugin paths in exact active load order",
    )
    cn.add_argument("--out", default="", help="Optional JSON report path (outside Git worktrees and game folders)")

    wl = sub.add_parser("stage-wl1", help="Stage 0-keyword baseline, 5 single-keyword variants, and all-5 variant")
    wl.add_argument("--data", required=True, help="Path to Starfield Data folder")
    wl.add_argument("--out", required=True, help="Output directory for WL1 variants")
    wl.add_argument("--worlds", default="Commonwealth")
    wl.add_argument("--body-name", default=hspec.DEFAULT_BODY_NAME)
    wl.add_argument("--world-plugin-dir", default="")
    wl.add_argument("--ground-source-dir", default="")
    wl.add_argument("--map-markers", default="", help="Optional FO4SFMapMarkers.esm path to merge LCSR rows and pin sha256")

    wb1p = sub.add_parser("stage-wb1", help="Stage WB1 weather & sky comparison variants (ours vs Starfield control)")
    wb1p.add_argument("--data", required=True, help="Path to Starfield Data folder")
    wb1p.add_argument("--out", required=True, help="Output directory for WB1 variants")
    wb1p.add_argument("--worlds", default="Commonwealth")
    wb1p.add_argument("--world-plugin-dir", default="")
    wb1p.add_argument("--ground-source-dir", default="")
    wb1p.add_argument("--map-markers", default="")

    wb2p = sub.add_parser("stage-wb2", help="Stage WB2 ground, pattern, and surface-tree comparison variants")
    wb2p.add_argument("--data", required=True, help="Path to Starfield Data folder")
    wb2p.add_argument("--out", required=True, help="Output directory for WB2 variants")
    wb2p.add_argument("--worlds", default="Commonwealth")
    wb2p.add_argument("--world-plugin-dir", default="")
    wb2p.add_argument("--ground-source-dir", default="")
    wb2p.add_argument("--map-markers", default="")

    args = ap.parse_args(argv)
    try:
        if args.cmd == "stage":
            return cmd_stage(args)
        if args.cmd == "check":
            return cmd_check(args)
        if args.cmd == "census":
            paths = _parse_csv_list(args.plugins)
            problems, summary = hspec.audit_zero_mars_references(paths)
            payload = {"problems": problems, "summary": summary}
            if args.out:
                out_abs = os.path.abspath(args.out)
                refuse_unsafe_output_path(out_abs, [os.path.abspath(p) for p in paths])
                write_json(out_abs, payload)
            print(json.dumps(payload, indent=2))
            return 0 if not problems else 1
        if args.cmd == "stage-wl1":
            return cmd_stage_wl1(args)
        if args.cmd == "stage-wb1":
            return cmd_stage_wb1(args)
        if args.cmd == "stage-wb2":
            return cmd_stage_wb2(args)
    except (CensusPathError, records.PlanetError, biom.BiomError, esm.EsmError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
