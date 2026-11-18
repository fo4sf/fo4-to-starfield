"""Stage, verify, and census FO4SFRouteLoot.esm (Phase 2 Track C 2i).

Stages Vault 111 armory loot (semi-auto ballistic pistol + >= 48 matching rounds +
2 FO4SF_Stimpaks) and Sanctuary -> Red Rocket -> Concord (<= 600 m) route container
loot overrides into an isolated stage folder outside Git.

usage:
  python scripts/loot/make_route_loot.py stage --out <stage_dir>
      --starfield <Starfield.esm> --core <FO4TerrainCore.esm> --port <FO4Port.esm>
      [--json <route_loot_ids.json>]

  python scripts/loot/make_route_loot.py verify --exp-dir <stage_dir>
      --plan <stage_dir/plan.json> [--starfield <Starfield.esm>]
      [--core <FO4TerrainCore.esm>] [--port <FO4Port.esm>]

  python scripts/loot/make_route_loot.py census --plugin <FO4SFRouteLoot.esm>
      --starfield <Starfield.esm> --core <FO4TerrainCore.esm> --port <FO4Port.esm>
      [--out <census.json>] [--json <route_loot_ids.json>]
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import struct
import subprocess
import sys
import zlib
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
if os.path.join(REPO, "src") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "src"))

from fo4sf.loot.tables import (  # noqa: E402
    ROUTE_LOOT_IDS_JSON,
    ROUTE_LOOT_MASTERS,
    ROUTE_LOOT_PLUGIN,
    load_route_loot_spec,
)

PROJECT_DIR = os.path.join(REPO, "dotnet", "RouteLoot")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save_json_atomic(path: str, data: object) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = f"{path}.tmp-{os.getpid()}"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def new_partial_dir(final_dir: str) -> str:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
    base = f"{final_dir}.partial-{stamp}-{os.getpid()}"
    cand, idx = base, 1
    while os.path.exists(cand):
        cand = f"{base}-{idx}"
        idx += 1
    os.makedirs(cand)
    return cand


def build_routeloot_dll() -> str:
    r = subprocess.run(
        ["dotnet", "build", PROJECT_DIR, "-c", "Release", "--nologo", "-v", "q"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        sys.exit(f"dotnet build RouteLoot failed ({r.returncode}):\n{r.stdout}{r.stderr}")
    return os.path.join(PROJECT_DIR, "bin", "Release", "net9.0", "RouteLoot.dll")


def run_cmd(cmd: List[str]) -> subprocess.CompletedProcess[str]:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"command failed ({r.returncode}): {' '.join(cmd)}\n{r.stdout}{r.stderr}")
    return r


def read_tes4_header_info(esm_path: str) -> Tuple[int, List[str]]:
    with open(esm_path, "rb") as f:
        hdr = f.read(24)
        if len(hdr) < 24 or hdr[:4] != b"TES4":
            raise ValueError(f"{esm_path}: not a TES4 ESM file")
        hsize, hflags = struct.unpack_from("<II", hdr, 4)
        payload = f.read(hsize)
    if hflags & 0x00040000:
        payload = zlib.decompress(payload[4:])
    masters: List[str] = []
    pos, end = 0, len(payload)
    large_sz: Optional[int] = None
    while pos + 6 <= end:
        sig = payload[pos : pos + 4]
        sz = struct.unpack_from("<H", payload, pos + 4)[0]
        pos += 6
        if sig == b"XXXX" and sz == 4 and pos + 4 <= end:
            large_sz = struct.unpack_from("<I", payload, pos)[0]
            pos += 4
            continue
        if large_sz is not None:
            sz, large_sz = large_sz, None
        sdata = payload[pos : pos + sz]
        pos += sz
        if sig == b"MAST" and sdata:
            masters.append(sdata.rstrip(b"\x00").decode("utf-8", errors="replace"))
    return hflags, masters


def verify_census_doc(census: Dict[str, object], min_ammo: int = 48, min_stimpaks: int = 2) -> List[str]:
    problems: List[str] = []
    non_credit = int(census.get("route_containers_with_non_credit_items", 0))  # type: ignore[arg-type]
    within = int(census.get("route_containers_within_600m", 0))  # type: ignore[arg-type]
    core_cont_ov = int(census.get("overridden_core_cont_bases", 0))  # type: ignore[arg-type]
    outside_mod = int(census.get("outside_corridor_containers_modified", 0))  # type: ignore[arg-type]
    if core_cont_ov != 0:
        problems.append(f"B10 violation: overridden_core_cont_bases={core_cont_ov} (expected 0)")
    if outside_mod != 0:
        problems.append(f"B10 violation: outside_corridor_containers_modified={outside_mod} (expected 0)")
    if within <= 0:
        problems.append(f"route_containers_within_600m={within} (expected > 0)")
    if non_credit <= 0:
        problems.append(f"route_containers_with_non_credit_items={non_credit} (expected > 0)")
    v111 = census.get("vault111")
    if not isinstance(v111, dict):
        problems.append("census missing vault111 block")
        return problems
    if int(v111.get("armory_case_pistols", 0)) < 1:
        problems.append(f"Vault 111 armory_case_pistols={v111.get('armory_case_pistols')} (expected >= 1)")
    if int(v111.get("armory_case_ammo_rounds", 0)) < min_ammo:
        problems.append(
            f"Vault 111 armory_case_ammo_rounds={v111.get('armory_case_ammo_rounds')} (expected >= {min_ammo})"
        )
    if int(v111.get("armory_case_stimpaks", 0)) < min_stimpaks:
        problems.append(
            f"Vault 111 armory_case_stimpaks={v111.get('armory_case_stimpaks')} (expected >= {min_stimpaks})"
        )
    if int(v111.get("total_pistols", 0)) < 1 or int(v111.get("total_ammo_rounds", 0)) < min_ammo:
        problems.append("Vault 111 total pistol/ammo counts below required minimums")
    return problems


def cmd_stage(args: argparse.Namespace) -> int:
    final_dir = os.path.abspath(args.out)
    if os.path.exists(final_dir):
        sys.exit(f"{final_dir} exists: stage into a new folder (existing stages are never overwritten)")

    json_path = os.path.abspath(args.json) if args.json else ROUTE_LOOT_IDS_JSON
    for flag, path in (
        ("--starfield", args.starfield),
        ("--core", args.core),
        ("--port", args.port),
        ("--json", json_path),
    ):
        if not path or not os.path.isfile(path):
            sys.exit(f"missing {flag}: {path!r}")

    spec = load_route_loot_spec(json_path)
    before_pins = {
        "Starfield.esm": sha256_file(args.starfield),
        "FO4TerrainCore.esm": sha256_file(args.core),
        "FO4Port.esm": sha256_file(args.port),
        "route_loot_ids.json": sha256_file(json_path),
    }

    dll = build_routeloot_dll()
    out = new_partial_dir(final_dir)
    plugin_path = os.path.join(out, ROUTE_LOOT_PLUGIN)
    census_path = os.path.join(out, "census.json")

    b_res = run_cmd(["dotnet", dll, "build", args.starfield, args.core, args.port, out, "--json", json_path])
    c_res = run_cmd(["dotnet", dll, "check", plugin_path, args.starfield, args.core, args.port, "--json", json_path])
    n_res = run_cmd(
        [
            "dotnet",
            dll,
            "census",
            plugin_path,
            args.starfield,
            args.core,
            args.port,
            "--out",
            census_path,
            "--json",
            json_path,
        ]
    )

    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(b_res.stdout + c_res.stdout + n_res.stdout)

    with open(census_path, encoding="utf-8") as f:
        census = json.load(f)

    problems = verify_census_doc(census, spec.vault_min_ammo_rounds, spec.vault_min_stimpaks)
    hflags, masters = read_tes4_header_info(plugin_path)
    if not (hflags & 0x01):
        problems.append("TES4 Master flag (0x01) missing")
    if tuple(masters) != ROUTE_LOOT_MASTERS:
        problems.append(f"TES4 masters {masters} != {list(ROUTE_LOOT_MASTERS)}")
    if problems:
        sys.exit(f"stage verification failed ({'; '.join(problems)}); attempt kept in {out}")

    after_pins = {
        "Starfield.esm": sha256_file(args.starfield),
        "FO4TerrainCore.esm": sha256_file(args.core),
        "FO4Port.esm": sha256_file(args.port),
        "route_loot_ids.json": sha256_file(json_path),
    }
    drift = [k for k in before_pins if before_pins[k] != after_pins[k]]
    if drift:
        sys.exit(f"input file(s) changed during stage ({', '.join(drift)}); attempt kept in {out}")

    plan = {
        "schema_version": 1,
        "kind": "route-loot",
        "plugin": ROUTE_LOOT_PLUGIN,
        "plugin_sha256": sha256_file(plugin_path),
        "plugin_bytes": os.path.getsize(plugin_path),
        "masters": list(ROUTE_LOOT_MASTERS),
        "census_file": "census.json",
        "census_sha256": sha256_file(census_path),
        "checked_against_sha256": {
            "Starfield.esm": before_pins["Starfield.esm"],
            "FO4TerrainCore.esm": before_pins["FO4TerrainCore.esm"],
            "FO4Port.esm": before_pins["FO4Port.esm"],
        },
        "table_sha256": before_pins["route_loot_ids.json"],
        "corridor_radius_m": spec.corridor_radius_m,
        "corridor_polyline_m": [list(pt) for pt in spec.corridor_polyline_m],
        "route_summary": {
            "total_exterior_containers": census["total_exterior_containers"],
            "route_containers_within_600m": census["route_containers_within_600m"],
            "route_containers_modified": census.get("route_containers_modified", 0),
            "route_containers_with_non_credit_items": census["route_containers_with_non_credit_items"],
            "route_containers_by_category": census["route_containers_by_category"],
            "outside_corridor_containers": census.get("outside_corridor_containers", 0),
            "outside_corridor_containers_modified": census.get("outside_corridor_containers_modified", 0),
            "overridden_core_cont_bases": census["overridden_core_cont_bases"],
            "own_route_cont_bases": census.get("own_route_cont_bases", 0),
            "overridden_route_container_refs": census.get("overridden_route_container_refs", 0),
        },
        "vault111": census["vault111"],
    }
    save_json_atomic(os.path.join(out, "plan.json"), plan)

    readme = (
        f"Route & Vault 111 Loot stage ({datetime.date.today().isoformat()}). NOT installed, NOT deployed.\n"
        f"Plugin: {ROUTE_LOOT_PLUGIN} ({plan['plugin_bytes']:,} bytes, sha256 {plan['plugin_sha256']}).\n"
        f"Masters: {', '.join(ROUTE_LOOT_MASTERS)}.\n"
        f"Corridor (<= {spec.corridor_radius_m:g} m): "
        f"{census['route_containers_with_non_credit_items']}/{census['route_containers_within_600m']} "
        f"containers hold non-credit items ({census.get('overridden_route_container_refs', 0)} corridor REFR overrides, "
        f"0 core CONT base overrides, {census.get('outside_corridor_containers_modified', 0)} outside containers modified).\n"
        f"Vault 111 (0x{spec.vault_cell_id:06X}): pistol 0x{spec.vault_pistol_id:06X} + "
        f"{census['vault111']['armory_case_ammo_rounds']} case rounds (0x{spec.vault_ammo_id:06X}) + "
        f"{census['vault111']['armory_case_stimpaks']} stimpaks (0x{spec.vault_stimpak_id:06X}).\n"
    )
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(readme)

    os.replace(out, final_dir)
    print(b_res.stdout.strip())
    print(c_res.stdout.strip())
    print(n_res.stdout.strip())
    print(f"staged {final_dir}: {ROUTE_LOOT_PLUGIN}, census.json, plan.json, README.txt")
    return 0


def verify_stage_dir(
    exp_dir: str,
    plan_path: str,
    starfield_esm: Optional[str] = None,
    core_esm: Optional[str] = None,
    port_esm: Optional[str] = None,
) -> List[str]:
    problems: List[str] = []
    if not os.path.isfile(plan_path):
        return [f"missing plan.json: {plan_path}"]
    with open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)
    if plan.get("kind") != "route-loot" or plan.get("plugin") != ROUTE_LOOT_PLUGIN:
        return [f"{plan_path}: not a route-loot plan"]

    plugin_path = os.path.join(exp_dir, plan["plugin"])
    if not os.path.isfile(plugin_path):
        problems.append(f"missing plugin: {plugin_path}")
    else:
        actual_sha = sha256_file(plugin_path)
        if actual_sha != plan.get("plugin_sha256"):
            problems.append(f"plugin sha256 {actual_sha} != expected {plan.get('plugin_sha256')}")
        hflags, masters = read_tes4_header_info(plugin_path)
        if not (hflags & 0x01):
            problems.append("plugin TES4 header lacks Master flag (0x01)")
        if tuple(masters) != ROUTE_LOOT_MASTERS:
            problems.append(f"plugin TES4 masters {masters} != {list(ROUTE_LOOT_MASTERS)}")

    census_path = os.path.join(exp_dir, plan.get("census_file", "census.json"))
    if not os.path.isfile(census_path):
        problems.append(f"missing census.json: {census_path}")
    else:
        c_sha = sha256_file(census_path)
        if c_sha != plan.get("census_sha256"):
            problems.append(f"census sha256 {c_sha} != expected {plan.get('census_sha256')}")
        with open(census_path, encoding="utf-8") as f:
            census = json.load(f)
        problems.extend(verify_census_doc(census))

    pinned = plan.get("checked_against_sha256") or {}
    for label, arg_path in (
        ("Starfield.esm", starfield_esm),
        ("FO4TerrainCore.esm", core_esm),
        ("FO4Port.esm", port_esm),
    ):
        if arg_path:
            if not os.path.isfile(arg_path):
                problems.append(f"missing {label}: {arg_path}")
            elif label in pinned and sha256_file(arg_path) != pinned[label]:
                problems.append(f"{label} sha256 mismatch against plan.json")

    return problems


def cmd_verify(args: argparse.Namespace) -> int:
    problems = verify_stage_dir(args.exp_dir, args.plan, args.starfield, args.core, args.port)
    for p in problems:
        print("FAIL  " + p)
    print("verify: ok" if not problems else f"verify: {len(problems)} problem(s)")
    return 0 if not problems else 1


def cmd_census(args: argparse.Namespace) -> int:
    json_path = os.path.abspath(args.json) if args.json else ROUTE_LOOT_IDS_JSON
    dll = build_routeloot_dll()
    cmd = ["dotnet", dll, "census", args.plugin, args.starfield, args.core, args.port, "--json", json_path]
    if args.out:
        cmd.extend(["--out", args.out])
    res = run_cmd(cmd)
    sys.stdout.write(res.stdout)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Stage and verify FO4SFRouteLoot.esm (2i)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp_st = sub.add_parser("stage", help="build FO4SFRouteLoot.esm, run check + census, write plan.json")
    sp_st.add_argument("--out", required=True)
    sp_st.add_argument("--starfield", required=True)
    sp_st.add_argument("--core", required=True)
    sp_st.add_argument("--port", required=True)
    sp_st.add_argument("--json", help="optional path to route_loot_ids.json")
    sp_st.set_defaults(func=cmd_stage)

    sp_vf = sub.add_parser("verify", help="verify staged FO4SFRouteLoot.esm + census.json + plan.json")
    sp_vf.add_argument("--exp-dir", required=True)
    sp_vf.add_argument("--plan", required=True)
    sp_vf.add_argument("--starfield")
    sp_vf.add_argument("--core")
    sp_vf.add_argument("--port")
    sp_vf.set_defaults(func=cmd_verify)

    sp_cn = sub.add_parser("census", help="run offline route + Vault 111 loot census")
    sp_cn.add_argument("--plugin", required=True)
    sp_cn.add_argument("--starfield", required=True)
    sp_cn.add_argument("--core", required=True)
    sp_cn.add_argument("--port", required=True)
    sp_cn.add_argument("--out")
    sp_cn.add_argument("--json")
    sp_cn.set_defaults(func=cmd_census)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
