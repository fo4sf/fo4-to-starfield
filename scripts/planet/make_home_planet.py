"""Stage and verify our isolated home star system, home planet, `"no-life, Starfield-patterned"` biome
(`FO4SFHome.esm`, until `WB1`–`WB3` replace the remaining Starfield climate/sky/pattern/ground references),
and single host registration plugin (`FO4TerrainCore_Home.esm`), plus `WL1` location-lever variants.

Usage:
  python scripts/planet/make_home_planet.py stage --data <Starfield Data> --out <stage dir>
      [--worlds Commonwealth] [--star-name "FO4SF Home"] [--planet-name "Earth"]
      [--temp 15.0] [--sky ATMO_Jemison|ATMO_Earth] [--lever-keywords K1,K2]
      [--world-plugin-dir <extra dir>] [--map-markers <FO4SFMapMarkers.esm>]
  python scripts/planet/make_home_planet.py check --stage <stage dir> [--data <Starfield Data>]
  python scripts/planet/make_home_planet.py stage-wl1 --data <Starfield Data> --out <variants dir>

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
from typing import Any, Dict, List, Optional, Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
if os.path.join(REPO, "src") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "src"))
if os.path.join(REPO, "scripts", "terrain") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "scripts", "terrain"))

from fo4_world_census import CensusPathError, refuse_unsafe_output_path  # noqa: E402
from fo4sf.planet import biom, esm, home_planet_spec as hspec, records  # noqa: E402
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
    temp_c: float = hspec.DEFAULT_TEMP_C,
    sky_atmo: str = hspec.DEFAULT_SKY_ATMO,
    lever_keywords: Sequence[str] = (),
    extra_world_dirs: Sequence[str] = (),
    map_markers_path: str = "",
) -> Dict[str, Any]:
    final = os.path.abspath(out_dir)
    sf_path = os.path.join(os.path.abspath(data_dir), "Starfield.esm")
    if not os.path.isfile(sf_path):
        raise FileNotFoundError(f"Starfield.esm not found in {data_dir}")

    mm_abs = os.path.abspath(map_markers_path) if map_markers_path else ""
    if mm_abs and not os.path.isfile(mm_abs):
        raise FileNotFoundError(f"map-markers plugin not found: {map_markers_path}")

    search_dirs = [os.path.abspath(d) for d in extra_world_dirs if d] + [os.path.abspath(data_dir)]
    guard_inputs = [sf_path] + ([mm_abs] if mm_abs else []) + search_dirs
    refuse_unsafe_output_path(final, guard_inputs)
    if os.path.exists(final):
        raise FileExistsError(f"{final} already exists; stage into a new folder")

    sf_sha_before = sha256_file(sf_path)
    mm_sha_before = sha256_file(mm_abs) if mm_abs else None
    mm_name = os.path.basename(mm_abs) if mm_abs else None
    world_plugin_pins_before: Dict[str, str] = {}

    partial = _new_partial_dir(final)
    with esm.Plugin(sf_path) as sf:
        master_writer, master_report = hspec.build_home_master(
            sf,
            data_dir=data_dir,
            star_name=star_name,
            planet_name=planet_name,
            temp_c=temp_c,
            sky_atmo=sky_atmo,
            lever_keywords=lever_keywords,
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
        )
        reg_path = os.path.join(partial, hspec.HOME_REGISTRATION)
        reg_writer.write(reg_path, compress=False)

    # Pin every referenced world plugin (e.g. FO4TerrainCore.esm) and verify zero modification
    for mname in reg_report["masters"][2:]:
        if mm_name and mname.lower() == mm_name.lower():
            continue
        for sdir in search_dirs:
            cand = os.path.join(sdir, mname)
            if os.path.isfile(cand):
                world_plugin_pins_before[mname] = sha256_file(cand)
                break

    biome_fid = (1 << 24) | hspec.BIOME
    biome_map_report = biom.stage_uniform_biome_map(biome_fid, planet_name, hspec.HOME_MASTER, partial)

    problems, check_summary = hspec.check_home_stage(
        sf_path,
        master_path,
        reg_path,
        data_dir=data_dir,
        expected_world_count=len(worlds),
        expected_levers=lever_keywords,
        map_markers_path=mm_abs or None,
    )
    if problems:
        raise records.PlanetError(f"home stage check failed: {problems}")

    if sha256_file(sf_path) != sf_sha_before:
        raise RuntimeError("Starfield.esm changed during stage")
    if mm_abs and sha256_file(mm_abs) != mm_sha_before:
        raise RuntimeError(f"{mm_name} changed during stage")
    for mname, old_sha in world_plugin_pins_before.items():
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
        "temp_c": float(temp_c),
        "sky_atmo": sky_atmo,
        "biome_profile": "no-life, Starfield-patterned",
        "system_id": master_report["system_id"],
        "planet_id": master_report["planet_id"],
        "biome_formid": reg_report["biome_formid"],
        "surface_location_formid": reg_report["surface_parent_formid"],
        "biome_map": biome_map_report,
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
        },
    )
    write_json(os.path.join(partial, "plan.json"), plan)

    verify_probs = verify_stage(partial, plan, data_dir)
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


def verify_stage(stage_dir: str, plan: Dict[str, Any], data_dir: Optional[str] = None) -> List[str]:
    """Verify staged file hashes, `.biom` paths and binary validity, and `W2`/`W3`/`W4`/`WL1`/`WL2` checks."""
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

    # Verify both .biom paths exist and name our BIOM FormID
    want_biom_paths = biom.stage_paths(plan["planet_name"], hspec.HOME_MASTER)
    want_biom_fid = f"{(1 << 24) | hspec.BIOME:08X}"
    for rel in want_biom_paths:
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

    master_path = os.path.join(stage_dir, hspec.HOME_MASTER)
    reg_path = os.path.join(stage_dir, hspec.HOME_REGISTRATION)
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
        for wname, wsha in pinned_worlds.items():
            wp = os.path.join(data_dir, wname)
            if os.path.isfile(wp) and sha256_file(wp) != wsha:
                problems.append(f"{wname} changed since stage ({sha256_file(wp)} != {wsha})")
        pinned_mm_sha = plan.get("map_markers_sha256")
        pinned_mm_name = plan.get("map_markers_plugin") or hspec.MAP_MARKERS_PLUGIN
        mm_check_path: Optional[str] = None
        if pinned_mm_sha:
            cand_mm = os.path.join(data_dir, pinned_mm_name)
            if os.path.isfile(cand_mm):
                mm_check_path = cand_mm
                actual_mm_sha = sha256_file(cand_mm)
                if actual_mm_sha != pinned_mm_sha:
                    problems.append(f"{pinned_mm_name} changed since stage ({actual_mm_sha} != {pinned_mm_sha})")
        chk_probs, _summary = hspec.check_home_stage(
            sf_path,
            master_path,
            reg_path,
            data_dir=data_dir,
            expected_world_count=len(plan.get("worlds", ["Commonwealth"])),
            expected_levers=plan.get("lever_keywords", ()),
            map_markers_path=mm_check_path,
        )
        problems.extend(chk_probs)

    return problems


def _print_field_sources() -> None:
    for rtype, rows in (
        ("STDT", hspec.STAR_FIELD_SPEC),
        ("PNDT", hspec.PLANET_FIELD_SPEC),
        ("BIOM", hspec.BIOM_FIELD_SPEC),
    ):
        print(f"=== {rtype} Field Sources ===")
        for row in rows:
            print(f"  [{row['subrecord']}] {row['field']} = {row['value']}  <-- {row['source']}")


def cmd_stage(args: argparse.Namespace) -> int:
    worlds = _parse_csv_list(args.worlds)
    levers = _parse_csv_list(args.lever_keywords)
    extra_dirs = [args.world_plugin_dir] if args.world_plugin_dir else []
    plan = stage_one(
        data_dir=args.data,
        out_dir=args.out,
        worlds=worlds,
        star_name=args.star_name,
        planet_name=args.planet_name,
        temp_c=args.temp,
        sky_atmo=args.sky,
        lever_keywords=levers,
        extra_world_dirs=extra_dirs,
        map_markers_path=args.map_markers,
    )
    print(
        f"staged {os.path.abspath(args.out)}: plugins={plan['plugins']}, "
        f"system_id={plan['system_id']}, planet_id={plan['planet_id']}, "
        f"biome={plan['biome_formid']}, levers={plan['lever_keywords']}"
    )
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    plan = load_plan(args.stage)
    problems = verify_stage(args.stage, plan, args.data or None)
    _print_field_sources()
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
            lever_keywords=levers,
            extra_world_dirs=extra_dirs,
            map_markers_path=getattr(args, "map_markers", ""),
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


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Stage and check FO4SFHome.esm + FO4TerrainCore_Home.esm")
    sub = ap.add_subparsers(dest="cmd", required=True)

    st = sub.add_parser("stage", help="Stage FO4SFHome.esm, FO4TerrainCore_Home.esm, and .biom maps")
    st.add_argument("--data", required=True, help="Path to Starfield Data folder")
    st.add_argument("--out", required=True, help="Output stage directory (outside Git worktrees and game folders)")
    st.add_argument("--worlds", default="Commonwealth", help="Comma-separated world keys from world_registry.json")
    st.add_argument("--star-name", default=hspec.DEFAULT_STAR_NAME)
    st.add_argument("--planet-name", default=hspec.DEFAULT_PLANET_NAME)
    st.add_argument("--temp", type=float, default=hspec.DEFAULT_TEMP_C)
    st.add_argument("--sky", choices=hspec.SKY_ATMO_CHOICES, default=hspec.DEFAULT_SKY_ATMO)
    st.add_argument("--lever-keywords", default="", help="Comma-separated WL1 lever keyword EditorIDs")
    st.add_argument("--world-plugin-dir", default="", help="Optional extra folder searched for world ESMs before --data")
    st.add_argument(
        "--map-markers",
        default="",
        help="Optional FO4SFMapMarkers.esm path: merge core LCTN LCSR rows, add master, and pin sha256 in plan.json",
    )

    ck = sub.add_parser("check", help="Offline verification of a staged home-world folder")
    ck.add_argument("--stage", required=True, help="Path to staged home-world directory")
    ck.add_argument("--data", default="", help="Optional path to Starfield Data folder for live clash checks")

    wl = sub.add_parser("stage-wl1", help="Stage 0-keyword baseline, 5 single-keyword variants, and all-5 variant")
    wl.add_argument("--data", required=True, help="Path to Starfield Data folder")
    wl.add_argument("--out", required=True, help="Output directory for WL1 variants")
    wl.add_argument("--worlds", default="Commonwealth")
    wl.add_argument("--world-plugin-dir", default="")
    wl.add_argument("--map-markers", default="", help="Optional FO4SFMapMarkers.esm path to merge LCSR rows and pin sha256")

    args = ap.parse_args(argv)
    try:
        if args.cmd == "stage":
            return cmd_stage(args)
        if args.cmd == "check":
            return cmd_check(args)
        if args.cmd == "stage-wl1":
            return cmd_stage_wl1(args)
    except (CensusPathError, records.PlanetError, biom.BiomError, esm.EsmError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
