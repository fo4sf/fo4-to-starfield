"""Build a self-contained Fallout 4 DLC interiors stage (`FO4DLC.esm`, prefix `fo4dlc`, labeled `TEST-STATION`)
from exported DLC cell JSONs and converted/rewritten DLC manifests, excluding any cell already owned by `FO4Port.esm`
(or `Fallout4.esm`) so two plugins never define or compete for the same interior cell.

Refuses any output folder inside a Git worktree or inside a game installation directory (Rule R4).

Usage:
  python scripts/terrain/interior_dlc.py --census <interior_census.json> --exports <dir> --manifest <manifest.json> [...]
         --out <stage_dir> --pluginspike <PluginSpike.dll> --starfield <Starfield game dir>
         [--owned-stage <interiors_b10>] [--staging <stage-dlc>] [--extra-staging <d5-scol-out>] [--no-pack]
"""
from collections import Counter
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS_DIR)
for _p in (os.path.join(ROOT, "src"), SCRIPTS_DIR, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fo4sf import pipeline  # noqa: E402
import deploy_starfield  # noqa: E402
import pack_staging  # noqa: E402
import port_promote  # noqa: E402
import vmad_patch  # noqa: E402

_CB_SPEC = importlib.util.spec_from_file_location("convert_batch_for_dlc", os.path.join(SCRIPTS_DIR, "convert_batch.py"))
convert_batch = importlib.util.module_from_spec(_CB_SPEC)
_CB_SPEC.loader.exec_module(convert_batch)

DEFAULT_PLUGIN = "FO4DLC.esm"
DEFAULT_PREFIX = "fo4dlc"
DEFAULT_LABEL = "TEST-STATION"
DEFAULT_ROOT_PARENT = "Starfield.esm:01B736"
DEFAULT_LIGHTING = {
    "*": {
        "LIGHTING_TEMPLATE": "006658",
        "IMAGE_SPACE": "122393",
        "LIGHT_MERGE_M": "2",
    }
}
DLC_LOAD_ORDER = ("DLCRobot", "DLCworkshop01", "DLCCoast", "DLCworkshop02", "DLCworkshop03", "DLCNukaWorld")
ASSET_SUBDIRS = ("meshes", "materials", "textures", "geometries", "animations")


def _load_json(path: str):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def _save_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_head() -> Optional[str]:
    try:
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or None
    except OSError:
        return None


def _row_plugins(row: dict) -> List[str]:
    plugins = [p for p in (row.get("plugins") or []) if not pipeline.is_excluded_dlc_name(p)]
    if not plugins:
        owner = (row.get("formkey") or "").partition(":")[2]
        if owner and not pipeline.is_excluded_dlc_name(owner):
            plugins = [owner]
    return plugins


def collect_owned_cells(owned_stages: Sequence[str]) -> Dict[str, str]:
    """Return {cell_edid_casefold: source_label} for every cell already owned by an existing FO4Port stage."""
    owned: Dict[str, str] = {}
    for st in owned_stages or ():
        if not st:
            continue
        marker = os.path.join(st, "result.json") if os.path.isdir(st) else st
        doc = _load_json(marker)
        stage_name = doc.get("name") or os.path.basename(os.path.abspath(st))
        for c in ((doc.get("pins") or {}).get("base_exports") or {}):
            owned.setdefault(c.casefold(), f"{stage_name}:base")
        for c in (doc.get("cells") or {}):
            owned.setdefault(c.casefold(), stage_name)
    return owned


def select_dlc_cells(census: dict, owned_stages: Sequence[str] = ()) -> dict:
    """Partition load-door-reachable non-test DLC-touched cells into `selected` (net-new DLC cells) and `excluded`
    (cells already owned by FO4Port / Fallout4.esm)."""
    owned_map = collect_owned_cells(owned_stages)
    dlc_reachable = []
    for row in census.get("cells") or []:
        if row.get("reach") not in ("worldspace", "behind_interior"):
            continue
        if row.get("test_name"):
            continue
        plugins = _row_plugins(row)
        if not any(p.lower() != "fallout4.esm" for p in plugins):
            continue
        dlc_reachable.append(row)

    order_map = {p.lower(): idx for idx, p in enumerate(DLC_LOAD_ORDER)}
    selected = []
    excluded = []
    for row in dlc_reachable:
        edid = row["editor_id"]
        fk = row.get("formkey") or ""
        owner_plugin = fk.partition(":")[2]
        plugins = _row_plugins(row)
        reasons = []
        if edid.casefold() in owned_map:
            reasons.append(f"owned by FO4Port stage ({owned_map[edid.casefold()]})")
        if owner_plugin.lower() == "fallout4.esm":
            reasons.append("base Fallout4.esm cell overridden by DLC")
        if reasons:
            excluded.append({
                "editor_id": edid,
                "formkey": fk,
                "owner_plugin": owner_plugin,
                "plugins": plugins,
                "reach": row.get("reach"),
                "reason": "; ".join(reasons),
            })
        else:
            selected.append({
                "editor_id": edid,
                "formkey": fk,
                "owner_plugin": owner_plugin,
                "plugins": plugins,
                "reach": row.get("reach"),
                "entered_from": row.get("entered_from"),
                "refs": row.get("refs", 0),
            })

    selected.sort(key=lambda r: (order_map.get(r["owner_plugin"][:-4].lower(), 99), r["editor_id"].casefold()))
    excluded.sort(key=lambda r: r["editor_id"].casefold())
    by_plugin = dict(sorted(Counter(r["owner_plugin"] for r in selected).items()))
    return {
        "dlc_reachable_total": len(dlc_reachable),
        "selected_count": len(selected),
        "excluded_count": len(excluded),
        "by_plugin": by_plugin,
        "selected_cells": selected,
        "excluded_cells": excluded,
    }


def _build_overlay_staging(primary_staging: str, extra_stagings: Sequence[str], overlay_dir: str) -> int:
    """Create a hard-linked (or copied on cross-volume fallback) read-only union of `primary_staging` + `extra_stagings`
    under `overlay_dir` without modifying any input staging folder. Returns copy fallback count."""
    copies = 0
    shutil.rmtree(overlay_dir, ignore_errors=True)
    os.makedirs(overlay_dir, exist_ok=True)
    for src_root in [primary_staging] + [s for s in extra_stagings if s]:
        for sub in ASSET_SUBDIRS:
            sub_root = os.path.join(src_root, sub)
            if not os.path.isdir(sub_root):
                continue
            for d, _dirs, files in os.walk(sub_root):
                rel_d = os.path.relpath(d, src_root)
                dst_d = os.path.join(overlay_dir, rel_d)
                os.makedirs(dst_d, exist_ok=True)
                for fn in files:
                    src_f = os.path.join(d, fn)
                    dst_f = os.path.join(dst_d, fn)
                    if os.path.exists(dst_f):
                        os.remove(dst_f)
                    try:
                        os.link(src_f, dst_f)
                    except OSError:
                        shutil.copyfile(src_f, dst_f)
                        copies += 1
    return copies


def _placed_counts(log_path: str, edid_prefix: str) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    rx = re.compile(rf"cell {re.escape(edid_prefix)}_(\S+) \S+: placed (\d+) references .*?\+ (\d+) lights .*?skipped (\d+)")
    if not os.path.isfile(log_path):
        return out
    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = rx.search(line)
            if m:
                out[m.group(1)] = {"placed": int(m.group(2)), "lights": int(m.group(3)), "skipped": int(m.group(4))}
    return out


def build_dlc_interiors(
    census_path: str,
    exports_dir: str,
    manifest_paths: Sequence[str],
    out_dir: str,
    pluginspike_dll: str,
    starfield_dir: str,
    owned_stages: Sequence[str] = (),
    plugin_name: str = DEFAULT_PLUGIN,
    prefix: str = DEFAULT_PREFIX,
    root_location_parent: str = DEFAULT_ROOT_PARENT,
    label: str = DEFAULT_LABEL,
    lighting_path: str = "",
    staging_dir: str = "",
    extra_stagings: Sequence[str] = (),
    no_pack: bool = False,
    no_promote: bool = False,
    pack_ratio_override: Optional[float] = None,
    build_archive_fn: Optional[Callable] = None,
) -> dict:
    """Build self-contained FO4DLC.esm (+ optional BA2 archives) into `out_dir`, excluding FO4Port-owned cells."""
    t0 = time.time()
    out_dir = os.path.abspath(out_dir)
    pipeline.refuse_unsafe_output_dir(out_dir, "--out")
    if os.path.exists(out_dir):
        raise ValueError(f"--out {out_dir} already exists")
    plugin_esm, _stem = pack_staging.normalize_plugin_name(plugin_name)
    prefix = (prefix or DEFAULT_PREFIX).strip()
    if not re.fullmatch(r"[a-z0-9_]+", prefix):
        raise ValueError(f"--prefix {prefix!r}: lower-case letters, digits and _ only")
    edid_prefix = pipeline.editor_id_prefix(prefix)
    if not manifest_paths:
        raise ValueError("at least one --manifest is required")
    if not no_pack and not staging_dir:
        raise ValueError("--staging is required unless --no-pack is set")

    census = _load_json(census_path)
    selection = select_dlc_cells(census, owned_stages=owned_stages)
    selected_cells = selection["selected_cells"]
    excluded_cells = selection["excluded_cells"]
    if not selected_cells:
        raise ValueError("0 net-new DLC cells selected from census")

    export_paths = []
    missing_exports = []
    for c in selected_cells:
        ep = os.path.join(exports_dir, c["editor_id"] + ".json")
        if not os.path.isfile(ep):
            missing_exports.append(c["editor_id"])
        else:
            export_paths.append(ep)
    if missing_exports:
        raise FileNotFoundError(f"missing {len(missing_exports)} DLC cell export(s) in {exports_dir}: {missing_exports[:5]}")

    os.makedirs(out_dir)
    raw_dir = os.path.join(out_dir, "plugin")
    port_dir = os.path.join(out_dir, "port")
    os.makedirs(raw_dir)
    os.makedirs(port_dir)
    log_path = os.path.join(out_dir, "build.log")

    _save_json(os.path.join(out_dir, "dlc_plan.json"), selection)

    # 1. Merge converted/rewritten manifests without reconverting
    manifest_docs = [_load_json(mp) for mp in manifest_paths]
    merged_manifest = convert_batch.merge_manifests(manifest_docs)
    bad_prefix = [
        it["editor_id"]
        for it in merged_manifest.get("items") or []
        if not it.get("editor_id", "").startswith(edid_prefix + "_")
    ]
    if bad_prefix:
        raise ValueError(
            f"{len(bad_prefix)} manifest item(s) do not use EditorID prefix {edid_prefix}_ (first: {bad_prefix[:5]}): "
            f"run convert_batch.py rewrite-manifest-prefix --prefix {prefix} first"
        )
    merged_manifest_path = os.path.join(raw_dir, "manifest_merged.json")
    _save_json(merged_manifest_path, merged_manifest)

    # 2. Lighting + port_promote
    if lighting_path:
        shutil.copyfile(lighting_path, os.path.join(raw_dir, "lighting.json"))
    else:
        _save_json(os.path.join(raw_dir, "lighting.json"), DEFAULT_LIGHTING)

    sf_data = os.path.join(starfield_dir, "Data")
    steps: Dict[str, dict] = {
        "manifest": {
            "inputs": len(manifest_paths),
            "assets": len(merged_manifest.get("items") or []),
            "failures": len(merged_manifest.get("failures") or []),
        }
    }
    if not no_promote:
        tables = os.path.join(ROOT, "scripts", "terrain", "clusters")
        t_prom = time.time()
        rc_prom = port_promote.main(
            [
                "--out", os.path.join(raw_dir, "promote.json"),
                "--containers-table", os.path.join(tables, "container_table.json"),
                "--items-table", os.path.join(tables, "item_table.json"),
                "--starfield-data", sf_data,
                "--prefix", prefix,
            ] + export_paths
        )
        steps["promote"] = {"exit": rc_prom, "seconds": round(time.time() - t_prom, 1)}
        if rc_prom != 0:
            raise RuntimeError("port_promote failed")

    # 3. PluginSpike -> self-contained FO4DLC.esm
    spike_cmd = [
        "dotnet", pluginspike_dll, raw_dir, merged_manifest_path,
        "--plugin-name", plugin_esm,
        "--edid-prefix", edid_prefix,
    ]
    if root_location_parent and root_location_parent.lower() != DEFAULT_ROOT_PARENT.lower():
        spike_cmd += ["--root-location-parent", root_location_parent]
    spike_cmd += export_paths
    env = dict(os.environ, STARFIELD_DATA=sf_data)
    t_spike = time.time()
    with open(log_path, "a", encoding="utf-8") as log_f:
        log_f.write("$ " + " ".join(spike_cmd) + "\n")
        log_f.flush()
        proc = subprocess.run(spike_cmd, stdout=log_f, stderr=subprocess.STDOUT, env=env)
    steps["pluginspike"] = {"exit": proc.returncode, "seconds": round(time.time() - t_spike, 1)}
    if proc.returncode != 0:
        raise RuntimeError(f"PluginSpike failed with exit code {proc.returncode}; see {log_path}")

    # 4. Offline verification of FO4DLC.esm: self-contained masters, all selected cells present, 0 excluded cells present
    raw_plugin_path = os.path.join(raw_dir, plugin_esm)
    plug = vmad_patch.Plugin.read(raw_plugin_path)
    masters = plug.masters()
    forbidden_masters = [m for m in masters if m.lower() in ("fo4port.esm", "fo4terraincore.esm")]
    if forbidden_masters:
        raise RuntimeError(f"{plugin_esm} must be self-contained, but masters {forbidden_masters}")
    fids = _load_json(os.path.join(raw_dir, "formids.json"))
    records = plug.records()
    own_hi = len(masters) << 24
    missing_cells = []
    for c in selected_cells:
        ck = f"CELL:{edid_prefix}_{c['editor_id']}"
        loc = fids.get(ck)
        if loc is None or (own_hi | loc) not in records or records[own_hi | loc][0] != b"CELL":
            missing_cells.append(c["editor_id"])
    leaked_excluded = [
        e["editor_id"] for e in excluded_cells if f"CELL:{edid_prefix}_{e['editor_id']}" in fids
    ]
    if missing_cells or leaked_excluded:
        raise RuntimeError(f"cell verification failed: missing={missing_cells}, leaked_excluded={leaked_excluded}")

    for fname in (plugin_esm, "formids.json", "teleports.json", "promote.json", "lighting.json"):
        src_f = os.path.join(raw_dir, fname)
        if os.path.isfile(src_f):
            dst_f = os.path.join(port_dir, fname)
            try:
                os.link(src_f, dst_f)
            except OSError:
                shutil.copyfile(src_f, dst_f)

    # 5. Optional BA2 packing via scripts/pack_staging.py
    if not no_pack:
        overlay_dir = os.path.join(out_dir, "_combined_staging")
        try:
            if extra_stagings:
                overlay_copies = _build_overlay_staging(staging_dir, extra_stagings, overlay_dir)
                pack_src = overlay_dir
            else:
                overlay_copies = 0
                pack_src = staging_dir
            pack_res = pack_staging.pack_staging(
                staging=pack_src,
                out_dir=port_dir,
                starfield=starfield_dir,
                plugin=plugin_esm,
                pack_ratio_override=pack_ratio_override,
                log_path=log_path,
                scratch_parent=out_dir,
                build_archive_fn=build_archive_fn or deploy_starfield.build_archive,
            )
            pack_res["overlay_copies"] = overlay_copies
            steps["pack"] = pack_res
            if not pack_res.get("pass"):
                raise RuntimeError(f"pack_staging failed: {pack_res.get('problem')}")
        finally:
            shutil.rmtree(overlay_dir, ignore_errors=True)

    placed = _placed_counts(log_path, edid_prefix)
    cells_report = {}
    for c in selected_cells:
        edid = c["editor_id"]
        row = {
            "formkey": c["formkey"],
            "owner_plugin": c["owner_plugin"],
            "plugins": c["plugins"],
            "reach": c["reach"],
            "coc": f"{edid_prefix}_{edid}",
            "result": "converted",
        }
        if edid in placed:
            row.update(placed[edid])
        cells_report[edid] = row

    teleports = _load_json(os.path.join(raw_dir, "teleports.json")) if os.path.isfile(os.path.join(raw_dir, "teleports.json")) else {}
    steps["teleports"] = {k: v for k, v in teleports.items() if not isinstance(v, list)}
    install = pack_staging.install_set(port_dir, plugin=plugin_esm)
    pins = {
        "commit": _git_head(),
        "census": _sha256(census_path),
        "plugin": _sha256(os.path.join(port_dir, plugin_esm)),
        "plugin_bytes": os.path.getsize(os.path.join(port_dir, plugin_esm)),
        "formids": _sha256(os.path.join(port_dir, "formids.json")),
    }
    result = {
        "classification": label,
        "architecture": "self-contained",
        "name": os.path.basename(out_dir),
        "pass": True,
        "error": None,
        "installed": False,
        "plugin_name": plugin_esm,
        "prefix": prefix,
        "edid_prefix": edid_prefix,
        "core": None,
        "masters": masters,
        "dlc_reachable_total": selection["dlc_reachable_total"],
        "selected_count": selection["selected_count"],
        "excluded_count": selection["excluded_count"],
        "by_plugin": selection["by_plugin"],
        "excluded_cells": excluded_cells,
        "pins": pins,
        "install": install,
        "steps": steps,
        "cells": cells_report,
        "totals": {"converted": len(cells_report), "excluded_fo4port_owned": len(excluded_cells)},
        "seconds": round(time.time() - t0, 1),
    }
    if root_location_parent and root_location_parent.lower() != DEFAULT_ROOT_PARENT.lower():
        result["root_location_parent"] = root_location_parent
    _save_json(os.path.join(out_dir, "result.json"), result)

    with open(os.path.join(out_dir, "README.txt"), "w", encoding="utf-8") as f:
        f.write(
            f"[{label}] Self-contained Fallout 4 DLC interiors stage ({plugin_esm}, prefix {prefix}).\n"
            f"PASS. NOT installed, NOT queued. Masters: {', '.join(masters)} (zero dependency on FO4Port.esm or FO4TerrainCore.esm).\n"
            f"Reachable non-test DLC cells in census: {selection['dlc_reachable_total']}\n"
            f"  Built into {plugin_esm}: {selection['selected_count']} net-new DLC cells ({selection['by_plugin']})\n"
            f"  Excluded (already owned by FO4Port.esm / Fallout4.esm): {selection['excluded_count']}\n"
        )
        for ex in excluded_cells:
            f.write(f"    - {ex['editor_id']} ({ex['formkey']}, plugins={ex['plugins']}): {ex['reason']}\n")
        if install["files"]:
            f.write(
                "\nFiles in port\\:\n"
                + "".join(f"  port\\{n}\n" for n in install["files"])
                + "\nPlugins.txt activation order:\n"
                + "".join(f"  *{n}\n" for n in install["plugins_txt"])
            )
    return result


def add_cli_arguments(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--census", required=True, help="interior_census.py output JSON covering base + DLC plugins")
    ap.add_argument("--exports", required=True, help="directory of Fo4Export cell JSONs")
    ap.add_argument("--manifest", action="append", default=[], required=True,
                    help="converted/rewritten manifest JSON (repeatable; merged in order)")
    ap.add_argument("--owned-stage", action="append", default=[],
                    help="existing FO4Port stage (e.g. interiors_b10) whose cells must be excluded (repeatable)")
    ap.add_argument("--out", required=True, help="new output stage directory outside Git worktrees and game folders")
    ap.add_argument("--pluginspike", required=True, help="path to built PluginSpike.dll")
    ap.add_argument("--starfield", required=True, help="Starfield game root")
    ap.add_argument("--staging", default="", help="primary DLC asset staging folder for BA2 packing")
    ap.add_argument("--extra-staging", action="append", default=[],
                    help="additional converted asset staging folder overlaid during BA2 packing (repeatable)")
    ap.add_argument("--lighting", default="", help="optional lighting.json override")
    ap.add_argument("--plugin-name", default=DEFAULT_PLUGIN, help="target plugin name (default: FO4DLC.esm)")
    ap.add_argument("--prefix", default=DEFAULT_PREFIX, help="asset/EditorID prefix slug (default: fo4dlc)")
    ap.add_argument("--root-location-parent", default=DEFAULT_ROOT_PARENT,
                    help="parent LCTN FormKey for FO4DLC_InteriorsLocation (default: Starfield.esm:01B736)")
    ap.add_argument("--label", default=DEFAULT_LABEL, help="stage classification label (default: TEST-STATION)")
    ap.add_argument("--pack-ratio", type=float, default=None, help="optional packed/loose texture ratio override")
    ap.add_argument("--no-pack", action="store_true", help="build FO4DLC.esm without packing BA2 archives")
    ap.add_argument("--no-promote", action="store_true", help="skip port_promote.py (for offline unit tests)")


def run_from_namespace(a: argparse.Namespace) -> int:
    try:
        res = build_dlc_interiors(
            census_path=a.census,
            exports_dir=a.exports,
            manifest_paths=a.manifest,
            out_dir=a.out,
            pluginspike_dll=a.pluginspike,
            starfield_dir=a.starfield,
            owned_stages=a.owned_stage,
            plugin_name=a.plugin_name,
            prefix=a.prefix,
            root_location_parent=a.root_location_parent,
            label=a.label,
            lighting_path=a.lighting,
            staging_dir=a.staging,
            extra_stagings=a.extra_staging,
            no_pack=a.no_pack,
            no_promote=a.no_promote,
            pack_ratio_override=a.pack_ratio,
        )
    except Exception as e:  # noqa: BLE001
        sys.exit(f"interior_dlc: {e}")
    print(json.dumps({
        "classification": res["classification"],
        "plugin_name": res["plugin_name"],
        "pass": res["pass"],
        "dlc_reachable_total": res["dlc_reachable_total"],
        "selected_count": res["selected_count"],
        "excluded_count": res["excluded_count"],
        "by_plugin": res["by_plugin"],
        "excluded_cells": [e["editor_id"] for e in res["excluded_cells"]],
        "install": res["install"],
        "seconds": res["seconds"],
    }, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_cli_arguments(ap)
    return run_from_namespace(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
