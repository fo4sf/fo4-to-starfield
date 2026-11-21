"""Read-only inspection and diff report for an installed port's deploy record (`IB2`).

Reads `<Starfield>/Data/FO4Port.deploy.json` (or `--record <path>`) and compares what the deploy record says is
installed — owned files, recorded byte sizes and SHA-256 digests, `Plugins.txt` pre-install / post-install snapshots,
`plugins_restore_pending` / `cleanup_pending` flags, and backup/temporary artifacts — against what is currently in
`<Starfield>/Data` and the live `Plugins.txt`.

100% read-only on game state: NEVER mutates `Data`, `Plugins.txt`, or `*.deploy.json`.
Prints JSON to stdout, or writes `--out <path>` ONLY inside a `FO4SF-Owner-Tests` folder outside every Git worktree
and outside every game installation folder.

Usage:
  python scripts/terrain/port_install_report.py --starfield <starfield-dir> [--out <owner-tests-dir>/report.json]
  python scripts/terrain/port_install_report.py --starfield <starfield-dir> --counts-only
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for _p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "scripts"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import deploy_starfield as ds  # noqa: E402
from fo4sf import pipeline  # noqa: E402

OWNER_TESTS_DIRNAME = "fo4sf-owner-tests"


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def validate_report_out_path(
    out_path: str,
    *,
    starfield_dir: str = "",
    record_path: str = "",
    plugins_txt_path: str = "",
) -> Path:
    """Enforce `IB2` / `R4` output safety: `--out` must be outside Git worktrees, outside game/Data folders,
    and inside a `FO4SF-Owner-Tests` directory."""
    pipeline.refuse_unsafe_output_dir(out_path, "--out")
    resolved = Path(os.path.abspath(out_path)).resolve()

    if starfield_dir:
        sf_resolved = Path(os.path.abspath(starfield_dir)).resolve()
        if _is_within(resolved, sf_resolved):
            raise ValueError(f"--out {out_path} is inside --starfield ({starfield_dir}); refusing to write into game folder")

    if record_path:
        rec_parent = Path(os.path.abspath(record_path)).resolve().parent
        if _is_within(resolved, rec_parent):
            raise ValueError(f"--out {out_path} is inside the deploy record folder ({rec_parent}); refusing output")

    if plugins_txt_path:
        pt_resolved = Path(os.path.abspath(plugins_txt_path)).resolve()
        if resolved == pt_resolved:
            raise ValueError(f"--out {out_path} points to Plugins.txt; refusing output")

    if not any(part.casefold() == OWNER_TESTS_DIRNAME for part in resolved.parts):
        raise ValueError(
            f"--out {out_path} must be under a FO4SF-Owner-Tests directory outside Git worktrees and game folders"
        )
    return resolved


def _decode_b64_snapshot(raw_b64: Optional[str]) -> Tuple[Optional[bytes], List[str], Optional[str]]:
    """Return `(raw_bytes, lines, decode_error)` for a base64 `Plugins.txt` snapshot field."""
    if raw_b64 is None:
        return None, [], None
    if not isinstance(raw_b64, str):
        return None, [], "not_a_base64_string"
    try:
        raw_bytes = base64.b64decode(raw_b64, validate=True)
    except Exception:
        try:
            raw_bytes = base64.b64decode(raw_b64)
        except Exception as exc:  # noqa: BLE001
            return None, [], f"invalid_base64: {exc}"
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    return raw_bytes, text.splitlines(), None


def _meaningful_plugin_entries(lines: Sequence[str]) -> List[Tuple[str, bool, str]]:
    """Parse `Plugins.txt` lines (skipping blank lines and `#` comments) into `(plugin_name, is_active, raw_line)`."""
    out: List[Tuple[str, bool, str]] = []
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        active = s.startswith("*")
        name = s[1:].strip() if active else s
        if name:
            out.append((name, active, s))
    return out


def _mtime_utc_iso(path: str) -> Optional[str]:
    try:
        ts = os.path.getmtime(path)
    except OSError:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _scan_data_extras(data_dir: str, recorded_set: set, spec: dict, manifest_filename: str) -> Tuple[List[str], List[str], List[str]]:
    """Return `(unrecorded_bundle_files, other_deploy_records, temp_or_backup_files)` in `Data`."""
    if not os.path.isdir(data_dir):
        return [], [], []
    unrecorded_bundle: List[str] = []
    other_records: List[str] = []
    temp_or_backups: List[str] = []
    stem_low = spec["stem"].casefold()

    for fn in sorted(os.listdir(data_dir)):
        full = os.path.join(data_dir, fn)
        if not os.path.isfile(full):
            continue
        low = fn.casefold()
        if low == manifest_filename.casefold():
            continue
        if low.endswith(".deploy.json"):
            other_records.append(fn)
            continue
        if ds.deployable(fn, spec) and low not in recorded_set:
            unrecorded_bundle.append(fn)
            continue
        is_temp_prefix = low.startswith(".fo4port-") or low.startswith(f".{stem_low}-")
        is_backup_name = low.startswith(stem_low) and any(
            low.endswith(sfx) or (sfx + ".") in low for sfx in (".bak", ".orig", ".old", ".backup", ".tmp")
        )
        if is_temp_prefix or is_backup_name:
            temp_or_backups.append(fn)
    return unrecorded_bundle, other_records, temp_or_backups


def _scan_plugins_txt_backups(plugins_txt: str) -> List[str]:
    parent = os.path.dirname(os.path.abspath(plugins_txt)) if plugins_txt else ""
    if not parent or not os.path.isdir(parent):
        return []
    base_low = os.path.basename(plugins_txt).casefold()
    found: List[str] = []
    for fn in sorted(os.listdir(parent)):
        full = os.path.join(parent, fn)
        if not os.path.isfile(full):
            continue
        low = fn.casefold()
        if low == base_low:
            continue
        if low.startswith(".fo4port-plugins-") or (
            low.startswith(base_low) and any(tok in low for tok in (".bak", ".orig", ".old", ".backup", ".tmp"))
        ):
            found.append(fn)
    return found


def inspect_port_install(
    starfield_dir: str,
    *,
    plugin_name: str = ds.PLUGIN,
    record_path: str = "",
    plugins_txt_override: str = "",
) -> Dict:
    """Read-only comparison of the port's deploy record against `<starfield_dir>/Data` and `Plugins.txt`."""
    req_spec = ds.plugin_bundle_spec(plugin_name or ds.PLUGIN)
    data_dir = os.path.join(starfield_dir, "Data")
    rec_path = record_path or os.path.join(data_dir, req_spec["manifest"])
    rec_filename = os.path.basename(rec_path)

    differences: List[Dict[str, str]] = []

    if not os.path.isfile(rec_path):
        target_pt = plugins_txt_override or ds.plugins_txt_path()
        unrec, other_rec, data_bak = _scan_data_extras(data_dir, set(), req_spec, rec_filename)
        pt_bak = _scan_plugins_txt_backups(target_pt)
        live_exists = os.path.isfile(target_pt)
        live_lines = ds.read_lines(target_pt) if live_exists else []
        differences.append({
            "category": "record",
            "code": "missing_deploy_record",
            "detail": f"{rec_filename} is not present in Data",
        })
        for fn in unrec:
            differences.append({
                "category": "data",
                "code": "unrecorded_bundle_file",
                "detail": f"{fn} exists in Data without a deploy record",
            })
        counts = {
            "record_exists": 0,
            "record_complete": 0,
            "record_has_plugin_name_key": 0,
            "pending_restore_flag": 0,
            "cleanup_pending_flag": 0,
            "recorded_files": 0,
            "published_files": 0,
            "data_files_matching": 0,
            "data_files_missing": 0,
            "data_files_changed": 0,
            "unrecorded_bundle_files_in_data": len(unrec),
            "other_deploy_records_in_data": len(other_rec),
            "temp_or_backup_files_in_data": len(data_bak),
            "owned_plugins_expected_active": 0,
            "owned_plugins_active_in_live": 0,
            "owned_plugins_inactive_or_missing": 0,
            "snapshot_original_lines": 0,
            "snapshot_activated_lines": 0,
            "live_plugins_txt_lines": len(_meaningful_plugin_entries(live_lines)),
            "plugins_txt_added_since_snapshot": 0,
            "plugins_txt_removed_since_snapshot": 0,
            "plugins_txt_activation_toggles": 0,
            "plugins_txt_order_changed": 0,
            "plugins_txt_backup_or_temp_files": len(pt_bak),
            "total_differences": len(differences),
        }
        return {
            "schema_version": 1,
            "read_only": True,
            "plugin_name": req_spec["plugin_esm"],
            "record": {
                "manifest_filename": rec_filename,
                "exists": False,
                "mtime_utc": None,
                "complete": False,
                "old_format_without_plugin_name": False,
                "plugins_restore_pending": False,
                "cleanup_pending": False,
                "restore_pending_note": None,
                "recorded_files": [],
                "published_files": [],
                "unpublished_recorded_files": [],
            },
            "data_comparison": {
                "data_dir_exists": os.path.isdir(data_dir),
                "files": [],
                "unrecorded_bundle_files": unrec,
                "other_deploy_records": other_rec,
                "temp_or_backup_files_in_data": data_bak,
                "core_plugin_present": os.path.isfile(os.path.join(data_dir, ds.CORE_PLUGIN)),
            },
            "plugins_txt_comparison": {
                "live_exists": live_exists,
                "recorded_path_matches_target": None,
                "backup_or_temp_files": pt_bak,
            },
            "differences": differences,
            "counts": counts,
        }

    with open(rec_path, encoding="utf-8") as f:
        manifest = json.load(f)
    if not isinstance(manifest, dict):
        raise ValueError(f"{rec_filename}: deploy record root must be a JSON object")

    has_plugin_name_key = "plugin_name" in manifest and manifest.get("plugin_name") not in (None, "")
    eff_plugin_raw = manifest.get("plugin_name") if has_plugin_name_key else ds.PLUGIN
    spec = ds.plugin_bundle_spec(eff_plugin_raw)

    if spec["plugin_esm"].casefold() != req_spec["plugin_esm"].casefold():
        differences.append({
            "category": "record",
            "code": "plugin_name_mismatch",
            "detail": f"record plugin {spec['plugin_esm']} differs from requested {req_spec['plugin_esm']}",
        })

    complete = manifest.get("complete") is True
    pending_restore = bool(manifest.get("plugins_restore_pending"))
    cleanup_pending = bool(manifest.get("cleanup_pending"))

    if not complete:
        differences.append({
            "category": "record",
            "code": "incomplete_install_record",
            "detail": f"record complete={manifest.get('complete')!r} (interrupted install or rollback)",
        })
    if cleanup_pending:
        differences.append({
            "category": "record",
            "code": "cleanup_pending_flag_set",
            "detail": "record has cleanup_pending=True",
        })

    restore_note: Optional[str] = None
    if pending_restore:
        if complete:
            restore_note = (
                "complete is True while plugins_restore_pending is True (deploy_starfield.publish sets "
                "plugins_restore_pending=True before writing Plugins.txt and leaves it True; uninstall only "
                "invokes restore_plugins when complete is False)"
            )
        else:
            restore_note = "complete is False with plugins_restore_pending=True (interrupted install awaiting restore)"
        differences.append({
            "category": "record",
            "code": "pending_restore_flag_set",
            "detail": restore_note,
        })

    raw_files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    recorded_files = [str(x) for x in raw_files if isinstance(x, str)]
    raw_pub = manifest.get("published_files") if isinstance(manifest.get("published_files"), list) else []
    published_files = [str(x) for x in raw_pub if isinstance(x, str)]
    pub_casefold = {x.casefold() for x in published_files}
    unpublished = [x for x in recorded_files if x.casefold() not in pub_casefold]
    if unpublished:
        differences.append({
            "category": "record",
            "code": "unpublished_recorded_files",
            "detail": f"{len(unpublished)} recorded file(s) not listed in published_files: {unpublished}",
        })

    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    file_rows: List[Dict] = []
    n_match = 0
    n_missing = 0
    n_changed = 0

    for rel in recorded_files:
        art = artifacts.get(rel) if isinstance(artifacts.get(rel), dict) else {}
        rec_size = art.get("size") if isinstance(art.get("size"), int) else None
        rec_sha = art.get("sha256").lower() if isinstance(art.get("sha256"), str) else None
        full = os.path.join(data_dir, rel)
        exists = os.path.isfile(full)
        if not exists:
            n_missing += 1
            file_rows.append({
                "name": rel,
                "recorded_size": rec_size,
                "recorded_sha256": rec_sha,
                "exists_in_data": False,
                "actual_size": None,
                "actual_sha256": None,
                "matches_recorded": False,
                "status": "missing",
            })
            differences.append({
                "category": "data",
                "code": "missing_recorded_file",
                "detail": f"Data/{rel} is listed in record but missing on disk",
            })
            continue

        actual = ds.artifact_identity(full)
        size_ok = rec_size is not None and actual["size"] == rec_size
        sha_ok = rec_sha is not None and actual["sha256"] == rec_sha
        if rec_size is None or rec_sha is None:
            n_changed += 1
            status = "missing_recorded_identity"
            matches = False
            differences.append({
                "category": "record",
                "code": "missing_artifact_identity",
                "detail": f"record lacks size/sha256 pin for {rel}",
            })
        elif size_ok and sha_ok:
            n_match += 1
            status = "match"
            matches = True
        else:
            n_changed += 1
            status = "content_changed"
            matches = False
            differences.append({
                "category": "data",
                "code": "changed_recorded_file",
                "detail": (
                    f"Data/{rel} differs from record (recorded size={rec_size} sha256={rec_sha[:12]}..., "
                    f"actual size={actual['size']} sha256={actual['sha256'][:12]}...)"
                ),
            })
        file_rows.append({
            "name": rel,
            "recorded_size": rec_size,
            "recorded_sha256": rec_sha,
            "exists_in_data": True,
            "actual_size": actual["size"],
            "actual_sha256": actual["sha256"],
            "matches_recorded": matches,
            "status": status,
        })

    recorded_set = {x.casefold() for x in recorded_files}
    unrec_bundle, other_records, data_backups = _scan_data_extras(data_dir, recorded_set, spec, rec_filename)
    for fn in unrec_bundle:
        differences.append({
            "category": "data",
            "code": "unrecorded_bundle_file",
            "detail": f"Data/{fn} matches {spec['stem']} bundle naming but is not in record files",
        })
    for fn in data_backups:
        differences.append({
            "category": "data",
            "code": "temp_or_backup_file_in_data",
            "detail": f"Data/{fn} temporary or backup file present",
        })

    core_path = os.path.join(data_dir, ds.CORE_PLUGIN)
    core_present = os.path.isfile(core_path)
    core_ident = ds.artifact_identity(core_path) if core_present else None

    # Plugins.txt comparison
    recorded_pt = manifest.get("plugins_txt") if isinstance(manifest.get("plugins_txt"), str) else ""
    default_env_pt = ds.plugins_txt_path()
    target_pt = plugins_txt_override or default_env_pt or recorded_pt
    pt_path_matches = (
        bool(recorded_pt and target_pt)
        and os.path.normcase(os.path.abspath(recorded_pt)) == os.path.normcase(os.path.abspath(target_pt))
    )
    if not plugins_txt_override and recorded_pt and default_env_pt and not pt_path_matches:
        differences.append({
            "category": "plugins_txt",
            "code": "plugins_txt_path_mismatch",
            "detail": "manifest plugins_txt path does not match current environment LOCALAPPDATA Plugins.txt path",
        })

    orig_bytes, orig_raw_lines, orig_err = _decode_b64_snapshot(manifest.get("plugins_original"))
    act_bytes, act_raw_lines, act_err = _decode_b64_snapshot(manifest.get("plugins_activated"))
    if orig_err:
        differences.append({"category": "record", "code": "invalid_plugins_original_b64", "detail": orig_err})
    if act_err:
        differences.append({"category": "record", "code": "invalid_plugins_activated_b64", "detail": act_err})

    live_exists = bool(target_pt) and os.path.isfile(target_pt)
    live_bytes: Optional[bytes] = None
    live_raw_lines: List[str] = []
    if live_exists:
        with open(target_pt, "rb") as f:
            live_bytes = f.read()
        live_raw_lines = live_bytes.decode("utf-8-sig", errors="replace").splitlines()
    else:
        differences.append({
            "category": "plugins_txt",
            "code": "missing_live_plugins_txt",
            "detail": "live Plugins.txt does not exist",
        })

    orig_entries = _meaningful_plugin_entries(orig_raw_lines)
    act_entries = _meaningful_plugin_entries(act_raw_lines)
    live_entries = _meaningful_plugin_entries(live_raw_lines)

    act_by_key = {name.casefold(): (name, is_act, raw_l) for name, is_act, raw_l in act_entries}
    live_by_key = {name.casefold(): (name, is_act, raw_l) for name, is_act, raw_l in live_entries}

    live_only = [name for name, _a, _r in live_entries if name.casefold() not in act_by_key]
    snapshot_only = [name for name, _a, _r in act_entries if name.casefold() not in live_by_key]

    activation_toggles: List[Dict[str, str]] = []
    for k, (sname, s_act, s_raw) in act_by_key.items():
        if k in live_by_key:
            _lname, l_act, l_raw = live_by_key[k]
            if s_act != l_act:
                activation_toggles.append({
                    "plugin": sname,
                    "snapshot_line": s_raw,
                    "live_line": l_raw,
                })

    common_act_order = [name.casefold() for name, _a, _r in act_entries if name.casefold() in live_by_key]
    common_live_order = [name.casefold() for name, _a, _r in live_entries if name.casefold() in act_by_key]
    order_changed = common_act_order != common_live_order

    exact_bytes_match = (act_bytes is not None and live_bytes is not None and act_bytes == live_bytes)
    exact_lines_match = [x[2] for x in act_entries] == [x[2] for x in live_entries]

    plugins_added = [str(x) for x in (manifest.get("plugins_added") or []) if isinstance(x, str)]
    plugins_replaced = manifest.get("plugins_replaced") if isinstance(manifest.get("plugins_replaced"), list) else []
    owned_esm_files = [rel for rel in recorded_files if rel.lower().endswith(".esm")]
    if not owned_esm_files:
        owned_esm_files = [ds.plugin_name(x) for x in plugins_added] or [spec["plugin_esm"]]

    live_active_set = {name.casefold() for name, is_act, _r in live_entries if is_act}
    owned_active = [p for p in owned_esm_files if p.casefold() in live_active_set]
    owned_inactive = [p for p in owned_esm_files if p.casefold() not in live_active_set]

    for p in owned_inactive:
        differences.append({
            "category": "plugins_txt",
            "code": "owned_plugin_not_active",
            "detail": f"{p} is owned by the install record but is not active in live Plugins.txt",
        })

    if live_exists and act_bytes is not None and not exact_lines_match:
        differences.append({
            "category": "plugins_txt",
            "code": "plugins_txt_drifted_from_snapshot",
            "detail": (
                f"live Plugins.txt differs from recorded plugins_activated snapshot "
                f"(+{len(live_only)} added, -{len(snapshot_only)} removed, "
                f"{len(activation_toggles)} active-flag toggle(s), order_changed={order_changed})"
            ),
        })
    elif live_exists and act_bytes is not None and exact_lines_match and not exact_bytes_match:
        differences.append({
            "category": "plugins_txt",
            "code": "plugins_txt_whitespace_or_encoding_diff",
            "detail": "live Plugins.txt has identical active entries to snapshot but different raw bytes/comments",
        })

    pt_backups = _scan_plugins_txt_backups(target_pt)
    if pt_backups:
        differences.append({
            "category": "plugins_txt",
            "code": "plugins_txt_backup_or_temp_file",
            "detail": f"Plugins.txt directory contains {len(pt_backups)} backup/temp file(s)",
        })

    counts = {
        "record_exists": 1,
        "record_complete": int(complete),
        "record_has_plugin_name_key": int(has_plugin_name_key),
        "pending_restore_flag": int(pending_restore),
        "cleanup_pending_flag": int(cleanup_pending),
        "recorded_files": len(recorded_files),
        "published_files": len(published_files),
        "data_files_matching": n_match,
        "data_files_missing": n_missing,
        "data_files_changed": n_changed,
        "unrecorded_bundle_files_in_data": len(unrec_bundle),
        "other_deploy_records_in_data": len(other_records),
        "temp_or_backup_files_in_data": len(data_backups),
        "owned_plugins_expected_active": len(owned_esm_files),
        "owned_plugins_active_in_live": len(owned_active),
        "owned_plugins_inactive_or_missing": len(owned_inactive),
        "snapshot_original_lines": len(orig_entries),
        "snapshot_activated_lines": len(act_entries),
        "live_plugins_txt_lines": len(live_entries),
        "plugins_txt_added_since_snapshot": len(live_only),
        "plugins_txt_removed_since_snapshot": len(snapshot_only),
        "plugins_txt_activation_toggles": len(activation_toggles),
        "plugins_txt_order_changed": int(order_changed),
        "plugins_txt_backup_or_temp_files": len(pt_backups),
        "total_differences": len(differences),
    }

    return {
        "schema_version": 1,
        "read_only": True,
        "plugin_name": spec["plugin_esm"],
        "record": {
            "manifest_filename": rec_filename,
            "exists": True,
            "mtime_utc": _mtime_utc_iso(rec_path),
            "complete": complete,
            "old_format_without_plugin_name": not has_plugin_name_key,
            "plugins_restore_pending": pending_restore,
            "cleanup_pending": cleanup_pending,
            "restore_pending_note": restore_note,
            "recorded_files": recorded_files,
            "published_files": published_files,
            "unpublished_recorded_files": unpublished,
        },
        "data_comparison": {
            "data_dir_exists": os.path.isdir(data_dir),
            "files": file_rows,
            "unrecorded_bundle_files": unrec_bundle,
            "other_deploy_records": other_records,
            "temp_or_backup_files_in_data": data_backups,
            "core_plugin_present": core_present,
            "core_plugin_size": core_ident["size"] if core_ident else None,
            "core_plugin_sha256": core_ident["sha256"] if core_ident else None,
        },
        "plugins_txt_comparison": {
            "live_exists": live_exists,
            "recorded_path_matches_target": pt_path_matches,
            "plugins_added": plugins_added,
            "plugins_replaced": plugins_replaced,
            "original_snapshot": {
                "present": orig_bytes is not None,
                "line_count": len(orig_entries),
                "lines": [x[2] for x in orig_entries],
            },
            "activated_snapshot": {
                "present": act_bytes is not None,
                "line_count": len(act_entries),
                "lines": [x[2] for x in act_entries],
            },
            "live": {
                "exists": live_exists,
                "line_count": len(live_entries),
                "lines": [x[2] for x in live_entries],
            },
            "exact_bytes_match_activated_snapshot": exact_bytes_match,
            "exact_lines_match_activated_snapshot": exact_lines_match,
            "owned_plugins_expected_active": owned_esm_files,
            "owned_plugins_active_in_live": owned_active,
            "owned_plugins_inactive_or_missing_in_live": owned_inactive,
            "live_only_plugins": live_only,
            "snapshot_only_plugins": snapshot_only,
            "activation_state_changes": activation_toggles,
            "common_order_changed": order_changed,
            "backup_or_temp_files": pt_backups,
        },
        "differences": differences,
        "counts": counts,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--starfield", required=True, help="Starfield game root directory (read-only)")
    ap.add_argument("--plugin-name", default=ds.PLUGIN, help="port plugin name (default: FO4Port.esm)")
    ap.add_argument("--record", default="", help="optional explicit deploy record path (default: <Starfield>/Data/<stem>.deploy.json)")
    ap.add_argument("--plugins-txt", default="", help="optional explicit Plugins.txt path for testing (read-only)")
    ap.add_argument("--out", default="", help="optional JSON output file under FO4SF-Owner-Tests (refuses Git worktrees & game dirs)")
    ap.add_argument("--counts-only", action="store_true", help="print only the numeric counts JSON summary to stdout")
    return ap


def main(argv=None) -> int:
    ap = build_arg_parser()
    a = ap.parse_args(argv)
    try:
        resolved_out: Optional[Path] = None
        if a.out:
            resolved_out = validate_report_out_path(
                a.out,
                starfield_dir=a.starfield,
                record_path=a.record,
                plugins_txt_path=a.plugins_txt,
            )
        report = inspect_port_install(
            a.starfield,
            plugin_name=a.plugin_name,
            record_path=a.record,
            plugins_txt_override=a.plugins_txt,
        )
        if resolved_out is not None:
            os.makedirs(resolved_out.parent, exist_ok=True)
            tmp = str(resolved_out) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=1)
            os.replace(tmp, str(resolved_out))
        payload = {"counts": report["counts"]} if a.counts_only else report
        print(json.dumps(payload, indent=1))
        return 0
    except (OSError, ValueError) as exc:
        print(f"port_install_report: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
