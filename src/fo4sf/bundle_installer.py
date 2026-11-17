"""One-command bundle installer, post-check, save-swap warning, and byte-identical rollback.

Wraps `scripts/game/exp_install.py` and `scripts/game/plugin_toggle.py` into a deterministic workflow:
  1. Refuses if `Starfield.exe`, `CreationKit.exe`, `sfse_loader.exe`, or the FO4SF launcher is open,
     or if target drive free space would fall below `--min-free-gb`.
  2. Evaluates save-swap safety against any currently installed plugin set (removed/reordered plugins,
     changed TES4/QUST/VMAD signatures) and emits a one-line `SAVE-WARNING:` when saves are invalidated.
  3. Backs up `Plugins.txt`, INI files (`StarfieldCustom.ini`, `StarfieldPrefs.ini`, `Starfield.ini`),
     `launcher_settings.json`, `FO4SFExp.install.json`, `FO4SF.toggle.json`, and creates hardlinks of all
     previously installed owner `.esm`/`.ba2` files under `<work_dir>/owner-files/`.
  4. Uninstalls the previous experiment (handling held `FO4SFBridge.esm` via `plugin_toggle.py`), installs
     the new bundle, restores prior holds, orders `Plugins.txt`, and runs a dynamic post-check against the
     newly written `FO4SFExp.install.json` (never hardcoding `"FO4TerrainCore - Main.ba2"` when `plugins[0]`
     or split archives produce `"FO4ActorRaider - Main.ba2"`, etc.).
  5. Writes `<work_dir>/install_receipt.json` and provides a matching `rollback` command that restores
     byte-identical files and prints every artifact it compared.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import stat
import struct
import subprocess
import sys
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from fo4sf.launcher.crashwatch import System

WATCHED_PROCESSES = ("Starfield.exe", "CreationKit.exe", "sfse_loader.exe", "FO4SFLauncher.exe")
LAUNCHER_LOCK_NAMES = ("launcher.lock", "fo4sf-launcher.lock")
HASH_SIZE_CUTOFF = 600 * 1024 * 1024  # 600 MiB row-hash cutoff matching prep.ps1/rollback.ps1 snapshot rows
COMPRESSED_RECORD_FLAG = 0x00040000


class BundleInstallRefused(RuntimeError):
    """Raised when preflight, post-check, or rollback verification refuses an operation."""


def _now_utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_writable_if_exists(path: str) -> None:
    if os.path.lexists(path):
        try:
            os.chmod(path, os.stat(path).st_mode | stat.S_IWRITE)
        except OSError:
            pass


def _remove_file(path: str) -> None:
    _make_writable_if_exists(path)
    os.remove(path)


def _copy_preserving_bytes_and_stat(src: str, dst: str) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    src_stat = os.stat(src)
    with open(src, "rb") as fp:
        raw = fp.read()
    tmp = dst + ".bundle-tmp"
    _make_writable_if_exists(tmp)
    with open(tmp, "wb") as fp:
        fp.write(raw)
        fp.flush()
        os.fsync(fp.fileno())
    _make_writable_if_exists(dst)
    for attempt in range(10):
        try:
            os.replace(tmp, dst)
            break
        except PermissionError:
            if attempt == 9:
                raise
            _make_writable_if_exists(dst)
            time.sleep(0.05)
    os.utime(dst, ns=(src_stat.st_atime_ns, src_stat.st_mtime_ns))
    try:
        os.chmod(dst, stat.S_IMODE(src_stat.st_mode))
    except OSError:
        pass


def _hardlink_or_copy(src: str, dst: str, require_hardlink: bool = False) -> str:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.lexists(dst):
        _remove_file(dst)
    try:
        os.link(src, dst)
        return "hardlink"
    except OSError as exc:
        if require_hardlink:
            raise BundleInstallRefused(f"Cannot create hardlink {dst} -> {src}: {exc}") from exc
        _copy_preserving_bytes_and_stat(src, dst)
        return "copy"


# ---------------------------------------------------------------------------
# Lightweight TES4 / QUST / VMAD signature inspector for 1-line save warnings
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PluginSaveSignature:
    plugin: str
    masters: Tuple[str, ...]
    quest_forms: Tuple[int, ...]
    quest_stage_counts: Tuple[Tuple[int, int], ...]
    quest_alias_counts: Tuple[Tuple[int, int], ...]
    vmad_digest: str


def _iter_subrecords(payload: bytes) -> Iterable[Tuple[bytes, bytes]]:
    pos = 0
    big: Optional[int] = None
    n_len = len(payload)
    while pos + 6 <= n_len:
        typ = payload[pos : pos + 4]
        sz = struct.unpack_from("<H", payload, pos + 4)[0]
        pos += 6
        if typ == b"XXXX":
            if sz == 4 and pos + 4 <= n_len:
                big = struct.unpack_from("<I", payload, pos)[0]
                pos += 4
                continue
            break
        if big is not None:
            sz, big = big, None
        if pos + sz > n_len:
            break
        yield typ, payload[pos : pos + sz]
        pos += sz


def inspect_plugin_save_signature(path: str) -> Optional[PluginSaveSignature]:
    """Extract TES4 masters, QUST stage/alias counts, and VMAD property layout digest from an `.esm`/`.esp`."""
    try:
        with open(path, "rb") as fp:
            blob = fp.read()
    except OSError:
        return None
    if len(blob) < 24 or blob[:4] != b"TES4":
        return None

    masters: List[str] = []
    quests: List[int] = []
    stage_counts: List[Tuple[int, int]] = []
    alias_counts: List[Tuple[int, int]] = []
    vmad_hasher = hashlib.sha256()

    def walk_region(start: int, end: int) -> None:
        pos = start
        while pos + 24 <= end:
            rec_type = blob[pos : pos + 4]
            if rec_type == b"GRUP":
                grup_size = struct.unpack_from("<I", blob, pos + 4)[0]
                if grup_size < 24 or pos + grup_size > end:
                    break
                walk_region(pos + 24, pos + grup_size)
                pos += grup_size
                continue
            data_size, flags, form_id = struct.unpack_from("<III", blob, pos + 4)
            rec_end = pos + 24 + data_size
            if rec_end > end:
                break
            payload = blob[pos + 24 : rec_end]
            if (flags & COMPRESSED_RECORD_FLAG) and len(payload) >= 4:
                try:
                    payload = zlib.decompress(payload[4:])
                except zlib.error:
                    payload = b""
            if rec_type == b"TES4" and pos == 0:
                for styp, sdata in _iter_subrecords(payload):
                    if styp == b"MAST" and sdata.endswith(b"\x00"):
                        masters.append(sdata[:-1].decode("utf-8", errors="replace"))
            else:
                stages = 0
                aliases = 0
                for styp, sdata in _iter_subrecords(payload):
                    if styp == b"VMAD":
                        vmad_hasher.update(rec_type)
                        vmad_hasher.update(struct.pack("<I", form_id & 0x00FFFFFF))
                        vmad_hasher.update(sdata)
                    elif rec_type == b"QUST":
                        if styp == b"INDX":
                            stages += 1
                        elif styp in (b"ALST", b"ALLS"):
                            aliases += 1
                if rec_type == b"QUST":
                    local_fid = form_id & 0x00FFFFFF
                    quests.append(local_fid)
                    stage_counts.append((local_fid, stages))
                    alias_counts.append((local_fid, aliases))
            pos = rec_end

    walk_region(0, len(blob))
    return PluginSaveSignature(
        plugin=os.path.basename(path),
        masters=tuple(masters),
        quest_forms=tuple(sorted(quests)),
        quest_stage_counts=tuple(sorted(stage_counts)),
        quest_alias_counts=tuple(sorted(alias_counts)),
        vmad_digest=vmad_hasher.hexdigest(),
    )


def evaluate_save_swap_warning(
    prev_plugins: Sequence[str],
    prev_plugin_paths: Mapping[str, str],
    new_plugins: Sequence[str],
    new_plugin_paths: Mapping[str, str],
) -> Optional[str]:
    """Return a single-line save-invalidation warning if swapping `prev_plugins` -> `new_plugins` breaks saves."""
    if not prev_plugins:
        return None

    reasons: List[str] = []
    prev_lower = [p.casefold() for p in prev_plugins]
    new_lower = [p.casefold() for p in new_plugins]
    prev_map = {p.casefold(): p for p in prev_plugins}

    removed = [prev_map[k] for k in prev_lower if k not in set(new_lower)]
    if removed:
        sample = ", ".join(removed[:3]) + ("..." if len(removed) > 3 else "")
        reasons.append(f"removed {len(removed)} plugin(s) ({sample})")

    common_prev_order = [k for k in prev_lower if k in set(new_lower)]
    common_new_order = [k for k in new_lower if k in set(prev_lower)]
    if common_prev_order != common_new_order:
        reasons.append("reordered active plugins (form-index shift)")
    elif new_lower[: len(common_prev_order)] != common_prev_order:
        reasons.append("inserted plugin(s) ahead of existing masters (form-index shift)")

    prev_path_ci = {k.casefold(): v for k, v in prev_plugin_paths.items()}
    new_path_ci = {k.casefold(): v for k, v in new_plugin_paths.items()}
    changed_qust: List[str] = []
    changed_vmad: List[str] = []
    for k in common_prev_order:
        p_old = prev_path_ci.get(k)
        p_new = new_path_ci.get(k)
        if not p_old or not p_new or not os.path.isfile(p_old) or not os.path.isfile(p_new):
            continue
        if sha256_file(p_old) == sha256_file(p_new):
            continue
        sig_old = inspect_plugin_save_signature(p_old)
        sig_new = inspect_plugin_save_signature(p_new)
        if sig_old and sig_new:
            if (
                sig_old.quest_forms != sig_new.quest_forms
                or sig_old.quest_stage_counts != sig_new.quest_stage_counts
                or sig_old.quest_alias_counts != sig_new.quest_alias_counts
            ):
                changed_qust.append(sig_new.plugin)
            if sig_old.vmad_digest != sig_new.vmad_digest:
                changed_vmad.append(sig_new.plugin)

    if changed_qust:
        sample = ", ".join(changed_qust[:3]) + ("..." if len(changed_qust) > 3 else "")
        reasons.append(f"changed quest/stage/alias layout in {sample}")
    if changed_vmad:
        sample = ", ".join(changed_vmad[:3]) + ("..." if len(changed_vmad) > 3 else "")
        reasons.append(f"changed VMAD script/property layout in {sample}")

    if not reasons:
        return None
    return (
        f"SAVE-WARNING: Swapping this bundle invalidates existing saves ({'; '.join(reasons)}); "
        "start a New Game or roll back before loading prior saves."
    )


# ---------------------------------------------------------------------------
# Process, Launcher Lock, Snapshot, and Post-Check Helpers
# ---------------------------------------------------------------------------

def check_not_running(
    starfield_dir: str,
    launcher_settings_path: str = "",
    pids_fn: Optional[Callable[[str], Sequence[int]]] = None,
    launcher_open_fn: Optional[Callable[[], bool]] = None,
) -> None:
    """Refuse if Starfield, Creation Kit, SFSE loader, or the FO4SF launcher is open."""
    query_pids = pids_fn if pids_fn is not None else System().pids
    active_procs: List[str] = []
    for image in WATCHED_PROCESSES:
        pids = list(query_pids(image))
        if pids:
            active_procs.append(f"{image} (pid {','.join(map(str, pids))})")
    if active_procs:
        raise BundleInstallRefused(
            f"Refusing bundle operation while game or launcher process is open: {'; '.join(active_procs)}"
        )

    lock_dirs = [os.path.join(starfield_dir, "Data")]
    if launcher_settings_path:
        lock_dirs.append(os.path.dirname(os.path.abspath(launcher_settings_path)))
    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        lock_dirs.append(os.path.join(local_app, "fo4sf"))
    for d in lock_dirs:
        if not d or not os.path.isdir(d):
            continue
        for lname in LAUNCHER_LOCK_NAMES:
            lpath = os.path.join(d, lname)
            if os.path.exists(lpath):
                raise BundleInstallRefused(f"Refusing bundle operation while launcher lock exists: {lpath}")

    if launcher_open_fn is not None and launcher_open_fn():
        raise BundleInstallRefused("Refusing bundle operation while FO4SF launcher UI/CLI is open")


def resolve_bundle_plugins(bundle_dir: str, plugins_csv: str = "") -> List[str]:
    if plugins_csv.strip():
        out = [p.strip() for p in plugins_csv.split(",") if p.strip()]
    else:
        bplan = os.path.join(bundle_dir, "bundle_plan.json")
        if os.path.isfile(bplan):
            with open(bplan, encoding="utf-8") as fp:
                bp = json.load(fp)
            if isinstance(bp.get("plugins"), list) and bp["plugins"]:
                return [str(x).strip() for x in bp["plugins"] if str(x).strip()]
        out = sorted(f for f in os.listdir(bundle_dir) if f.lower().endswith((".esm", ".esp", ".esl")))
    if not out:
        raise BundleInstallRefused(f"No plugins found to install in bundle folder: {bundle_dir}")
    return out


def compute_snapshot_rows(
    starfield_dir: str,
    plugins_txt_path: str,
    ini_paths: Sequence[str],
    hash_cutoff_bytes: int = HASH_SIZE_CUTOFF,
) -> List[str]:
    """Compute deterministic state rows across Data, Data/SFSE/Plugins, game root, Plugins.txt, and INIs."""
    rows: List[str] = []
    data_dir = os.path.join(starfield_dir, "Data")
    if os.path.isdir(data_dir):
        for fn in sorted(os.listdir(data_dir)):
            full = os.path.join(data_dir, fn)
            if not os.path.isfile(full):
                continue
            st = os.stat(full)
            digest = sha256_file(full) if st.st_size < hash_cutoff_bytes else "-"
            rows.append(f"DATA|{fn}|{st.st_size}|{st.st_mtime_ns}|{digest}")

    sfse_plugins = os.path.join(data_dir, "SFSE", "Plugins")
    if os.path.isdir(sfse_plugins):
        rel_files: List[Tuple[str, str]] = []
        for r, _dirs, files in os.walk(sfse_plugins):
            for fn in files:
                full = os.path.join(r, fn)
                rel = os.path.relpath(full, data_dir).replace("\\", "/")
                rel_files.append((rel, full))
        for rel, full in sorted(rel_files):
            st = os.stat(full)
            rows.append(f"SFSE|{rel}|{st.st_size}|{st.st_mtime_ns}|{sha256_file(full)}")

    if os.path.isdir(starfield_dir):
        for fn in sorted(os.listdir(starfield_dir)):
            full = os.path.join(starfield_dir, fn)
            if not os.path.isfile(full):
                continue
            st = os.stat(full)
            rows.append(f"ROOT|{fn}|{st.st_size}|{st.st_mtime_ns}")

    if os.path.isfile(plugins_txt_path):
        rows.append(f"PLUGINS|{sha256_file(plugins_txt_path)}")
    else:
        rows.append("PLUGINS|MISSING")

    for ini in sorted(ini_paths, key=lambda p: os.path.basename(p).casefold()):
        bname = os.path.basename(ini)
        if os.path.isfile(ini):
            rows.append(f"INI|{bname}|{sha256_file(ini)}")
        else:
            rows.append(f"INI|{bname}|MISSING")

    return rows


def collect_ini_paths(starfield_dir: str, my_games_dir: str = "") -> List[str]:
    candidates: List[str] = []
    if my_games_dir:
        for fn in ("StarfieldCustom.ini", "StarfieldPrefs.ini", "Starfield.ini"):
            p = os.path.join(my_games_dir, fn)
            if os.path.isfile(p) or fn == "StarfieldCustom.ini":
                candidates.append(p)
    root_ini = os.path.join(starfield_dir, "Starfield.ini")
    if os.path.isfile(root_ini):
        candidates.append(root_ini)
    seen = set()
    unique: List[str] = []
    for p in candidates:
        key = os.path.normcase(os.path.abspath(p))
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def run_postcheck(starfield_dir: str, plugins_txt_path: str) -> Dict[str, object]:
    """Verify the installed bundle dynamically from `Data/FO4SFExp.install.json` and `Plugins.txt`.

    Fixes the `prep.ps1` failure that hardcoded `"FO4TerrainCore - Main.ba2"` when `exp_install.py` named the
    archive after `plugins[0]` (e.g. `"FO4ActorRaider - Main.ba2"`) or split across multiple `<Plugin> - Main.ba2`s.
    """
    data_dir = os.path.join(starfield_dir, "Data")
    rec_path = os.path.join(data_dir, "FO4SFExp.install.json")
    if not os.path.isfile(rec_path):
        raise BundleInstallRefused(f"Post-check failed: missing install receipt {rec_path}")

    with open(rec_path, encoding="utf-8") as fp:
        rec = json.load(fp)
    if not rec.get("complete", True) or rec.get("cleanup_pending"):
        raise BundleInstallRefused("Post-check failed: FO4SFExp.install.json is marked incomplete or cleanup_pending")

    plugins: List[str] = list(rec.get("plugins") or [])
    files_map: Dict[str, str] = dict(rec.get("files") or {})
    if not plugins or not files_map:
        raise BundleInstallRefused("Post-check failed: FO4SFExp.install.json lists no plugins or files")

    # Dynamically discover every archive owned by this install (single Main.ba2, Textures.ba2, or split Main.ba2s)
    archives = list(rec.get("archives") or [k for k in files_map if k.lower().endswith(".ba2")])
    valid_stems = {os.path.splitext(p)[0].casefold() for p in plugins}

    if (rec.get("pack") or rec.get("source_inputs")) and not archives:
        raise BundleInstallRefused("Post-check failed: packed bundle has Data inputs but zero .ba2 archives in receipt")

    for arc in archives:
        if " - " not in arc or not arc.lower().endswith(".ba2"):
            raise BundleInstallRefused(f"Post-check failed: invalid archive filename {arc!r}")
        stem = arc.split(" - ", 1)[0].casefold()
        if stem not in valid_stems:
            raise BundleInstallRefused(
                f"Post-check failed: archive {arc!r} does not match any active bundle plugin stem in {plugins}"
            )
        if arc not in files_map:
            raise BundleInstallRefused(f"Post-check failed: archive {arc!r} missing from receipt files map")

    verified_files: Dict[str, Dict[str, object]] = {}
    for rel_name, expected_sha in sorted(files_map.items()):
        full = os.path.join(data_dir, *rel_name.replace("\\", "/").split("/"))
        if not os.path.isfile(full):
            raise BundleInstallRefused(f"Post-check failed: installed file missing from Data: {rel_name}")
        actual_sha = sha256_file(full)
        if actual_sha.lower() != str(expected_sha).lower():
            raise BundleInstallRefused(
                f"Post-check failed: SHA-256 mismatch on {rel_name} (expected {expected_sha[:12]}, got {actual_sha[:12]})"
            )
        verified_files[rel_name] = {"size": os.path.getsize(full), "sha256": actual_sha}

    held_off: set[str] = set()
    toggle_path = os.path.join(data_dir, "FO4SF.toggle.json")
    if os.path.isfile(toggle_path):
        with open(toggle_path, encoding="utf-8") as fp:
            t_rec = json.load(fp)
        held_off = {str(x).casefold() for x in (t_rec.get("off") or [])}

    if not os.path.isfile(plugins_txt_path):
        raise BundleInstallRefused(f"Post-check failed: Plugins.txt missing at {plugins_txt_path}")
    with open(plugins_txt_path, encoding="utf-8-sig") as fp:
        raw_lines = [ln.strip() for ln in fp if ln.strip() and not ln.strip().startswith("#")]
    ticked = {ln[1:].strip().casefold() for ln in raw_lines if ln.startswith("*")}

    for p in plugins:
        if p.casefold() in held_off:
            if p.casefold() in ticked:
                raise BundleInstallRefused(f"Post-check failed: held-off plugin {p} is still ticked in Plugins.txt")
        elif p.casefold() not in ticked:
            raise BundleInstallRefused(f"Post-check failed: active bundle plugin {p} is not ticked in Plugins.txt")

    return {
        "ok": True,
        "plugins": plugins,
        "archives": archives,
        "verified_files": verified_files,
    }


# ---------------------------------------------------------------------------
# Subprocess Runner for exp_install.py and plugin_toggle.py
# ---------------------------------------------------------------------------

def _run_game_tool(
    script_path: str,
    args: Sequence[str],
    plugins_txt_path: str,
    log_path: Optional[str] = None,
) -> Tuple[int, str]:
    env = dict(os.environ)
    # Bind LOCALAPPDATA when plugins_txt_path follows <LOCALAPPDATA>/Starfield/Plugins.txt so synthetic folder tests
    # and custom FO4SF instances stay 100% isolated from the host user profile.
    p_abs = os.path.abspath(plugins_txt_path)
    parent = os.path.dirname(p_abs)
    if os.path.basename(p_abs).casefold() == "plugins.txt" and os.path.basename(parent).casefold() == "starfield":
        env["LOCALAPPDATA"] = os.path.dirname(parent)

    argv = [sys.executable, script_path, *args]
    res = subprocess.run(argv, capture_output=True, text=True, env=env)
    combined = ((res.stdout or "") + (res.stderr or "")).strip()
    if log_path:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as fp:
            fp.write(f"$ {' '.join(argv)}\n{combined}\nrc={res.returncode}\n")
    return res.returncode, combined


# ---------------------------------------------------------------------------
# Top-Level Install & Rollback Operations
# ---------------------------------------------------------------------------

def install_bundle(
    *,
    bundle_dir: str,
    starfield_dir: str,
    work_dir: str,
    plugins_txt_path: str,
    my_games_dir: str = "",
    launcher_settings_path: str = "",
    plugins_csv: str = "",
    prepacked_ba2: str = "",
    split_archives: str = "none",
    max_archive_bytes: int = 3 * (1024 ** 3),
    prepacked_dir: str = "",
    with_sfse_sidecar: bool = False,
    min_free_gb: float = 24.0,
    dry_run: bool = False,
    require_hardlinks: bool = False,
    pids_fn: Optional[Callable[[str], Sequence[int]]] = None,
    launcher_open_fn: Optional[Callable[[], bool]] = None,
    free_bytes_fn: Optional[Callable[[str], int]] = None,
    repo_root: Optional[str] = None,
) -> Dict[str, object]:
    """Back up state + owner hardlinks, install a bundle, run dynamic post-check, and write `install_receipt.json`."""
    bundle_abs = os.path.abspath(bundle_dir)
    sf_abs = os.path.abspath(starfield_dir)
    work_abs = os.path.abspath(work_dir)
    ptxt_abs = os.path.abspath(plugins_txt_path)
    data_dir = os.path.join(sf_abs, "Data")

    if not os.path.isdir(bundle_abs):
        raise BundleInstallRefused(f"Bundle directory not found: {bundle_abs}")
    if not os.path.isdir(data_dir):
        raise BundleInstallRefused(f"Starfield Data directory not found: {data_dir}")
    if not os.path.isfile(ptxt_abs):
        raise BundleInstallRefused(f"Plugins.txt not found: {ptxt_abs}")

    check_not_running(
        sf_abs,
        launcher_settings_path=launcher_settings_path,
        pids_fn=pids_fn,
        launcher_open_fn=launcher_open_fn,
    )

    plugins = resolve_bundle_plugins(bundle_abs, plugins_csv)
    for p in plugins:
        if not os.path.isfile(os.path.join(bundle_abs, p)):
            raise BundleInstallRefused(f"Selected plugin missing from bundle folder: {p}")

    # Estimate required bytes for space floor check
    needed_bytes = sum(os.path.getsize(os.path.join(bundle_abs, p)) for p in plugins)
    bundle_data_dir = os.path.join(bundle_abs, "Data")
    has_loose_data = False
    if prepacked_ba2:
        if not os.path.isfile(prepacked_ba2):
            raise BundleInstallRefused(f"Prepacked BA2 not found: {prepacked_ba2}")
        needed_bytes += os.path.getsize(prepacked_ba2)
    elif prepacked_dir:
        if not os.path.isdir(prepacked_dir):
            raise BundleInstallRefused(f"Prepacked split directory not found: {prepacked_dir}")
        for fn in os.listdir(prepacked_dir):
            if fn.lower().endswith(".ba2"):
                needed_bytes += os.path.getsize(os.path.join(prepacked_dir, fn))
    elif os.path.isdir(bundle_data_dir):
        for r, _dirs, files in os.walk(bundle_data_dir):
            for fn in files:
                has_loose_data = True
                needed_bytes += os.path.getsize(os.path.join(r, fn))

    get_free = free_bytes_fn if free_bytes_fn is not None else (lambda p: shutil.disk_usage(p).free)
    free_now = int(get_free(sf_abs))
    floor_bytes = int(min_free_gb * (1024 ** 3))
    if floor_bytes > 0 and (free_now - needed_bytes) < floor_bytes:
        after_gb = (free_now - needed_bytes) / (1024 ** 3)
        raise BundleInstallRefused(
            f"Target drive would drop to {after_gb:.2f} GiB free "
            f"(free={free_now / (1024 ** 3):.2f} GiB, needed={needed_bytes / (1024 ** 3):.2f} GiB, floor={min_free_gb:.2f} GiB)"
        )

    # Inspect prior install for owner hardlinks and 1-line save-invalidation warning
    prev_exp_path = os.path.join(data_dir, "FO4SFExp.install.json")
    prev_rec: Optional[Dict[str, object]] = None
    prev_plugins: List[str] = []
    owner_rel_files: List[str] = []
    if os.path.isfile(prev_exp_path):
        with open(prev_exp_path, encoding="utf-8") as fp:
            prev_rec = json.load(fp)
        prev_plugins = list(prev_rec.get("plugins") or [])
        owner_rel_files = sorted((prev_rec.get("files") or {}).keys())

    prev_plugin_paths = {p: os.path.join(data_dir, p) for p in prev_plugins if os.path.isfile(os.path.join(data_dir, p))}
    new_plugin_paths = {p: os.path.join(bundle_abs, p) for p in plugins}
    save_warning = evaluate_save_swap_warning(prev_plugins, prev_plugin_paths, plugins, new_plugin_paths)
    if save_warning:
        print(save_warning)

    expected_primary_archive = f"{os.path.splitext(plugins[0])[0]} - Main.ba2" if (has_loose_data or prepacked_ba2 or prepacked_dir) else ""
    ini_paths = collect_ini_paths(sf_abs, my_games_dir)

    sidecar_rel_files: List[Tuple[str, str]] = []
    sidecar_root = os.path.join(bundle_abs, "sfse_sidecar", "SFSE", "Plugins")
    if with_sfse_sidecar and os.path.isdir(sidecar_root):
        for fn in sorted(os.listdir(sidecar_root)):
            src_sc = os.path.join(sidecar_root, fn)
            if os.path.isfile(src_sc):
                rel_sc = f"SFSE/Plugins/{fn}"
                dst_sc = os.path.join(data_dir, "SFSE", "Plugins", fn)
                if os.path.exists(dst_sc):
                    raise BundleInstallRefused(f"Refusing to overwrite existing SFSE plugin in Data: {rel_sc}")
                sidecar_rel_files.append((rel_sc, src_sc))

    if dry_run:
        plan = {
            "mode": "dry-run",
            "action": "install",
            "bundle_dir": bundle_abs,
            "starfield_dir": sf_abs,
            "work_dir": work_abs,
            "plugins": plugins,
            "expected_primary_archive": expected_primary_archive,
            "owner_hardlink_candidates": owner_rel_files,
            "ini_backups": [os.path.basename(p) for p in ini_paths if os.path.isfile(p)],
            "sidecar_files": [rel for rel, _ in sidecar_rel_files],
            "needed_bytes": needed_bytes,
            "free_bytes": free_now,
            "save_warning": save_warning or "",
        }
        print(
            f"DRY-RUN install: {len(plugins)} plugin(s), primary_archive={expected_primary_archive or 'none'}, "
            f"owner_hardlinks={len(owner_rel_files)}, ini_backups={len(plan['ini_backups'])}, writes=0"
        )
        return plan

    before_dir = os.path.join(work_abs, "before-files")
    owner_dir = os.path.join(work_abs, "owner-files")
    if os.path.exists(before_dir) or os.path.exists(owner_dir):
        raise BundleInstallRefused(f"Backup folder already exists under {work_abs}; refusing to overwrite prior backup")
    os.makedirs(before_dir, exist_ok=True)
    os.makedirs(owner_dir, exist_ok=True)

    # 1. Byte copies of Plugins.txt, INIs, launcher_settings.json, FO4SFExp.install.json, FO4SF.toggle.json
    backed_up_configs: Dict[str, Dict[str, object]] = {}
    _copy_preserving_bytes_and_stat(ptxt_abs, os.path.join(before_dir, "Plugins.txt"))
    backed_up_configs["Plugins.txt"] = {
        "target": ptxt_abs,
        "sha256": sha256_file(ptxt_abs),
        "size": os.path.getsize(ptxt_abs),
    }

    ini_backup_dir = os.path.join(before_dir, "inis")
    os.makedirs(ini_backup_dir, exist_ok=True)
    ini_manifest: List[Dict[str, object]] = []
    for idx, ini_p in enumerate(ini_paths):
        if os.path.isfile(ini_p):
            slot_name = f"{idx:02d}_{os.path.basename(ini_p)}"
            _copy_preserving_bytes_and_stat(ini_p, os.path.join(ini_backup_dir, slot_name))
            ini_manifest.append(
                {"slot": slot_name, "name": os.path.basename(ini_p), "target": ini_p, "sha256": sha256_file(ini_p), "present": True}
            )
        else:
            ini_manifest.append({"slot": "", "name": os.path.basename(ini_p), "target": ini_p, "sha256": "", "present": False})

    optional_meta = [
        ("FO4SFExp.install.json", os.path.join(data_dir, "FO4SFExp.install.json")),
        ("FO4SF.toggle.json", os.path.join(data_dir, "FO4SF.toggle.json")),
    ]
    if launcher_settings_path:
        optional_meta.append(("launcher_settings.json", os.path.abspath(launcher_settings_path)))

    meta_manifest: Dict[str, Dict[str, object]] = {}
    for label, full_p in optional_meta:
        if os.path.isfile(full_p):
            _copy_preserving_bytes_and_stat(full_p, os.path.join(before_dir, label))
            meta_manifest[label] = {"target": full_p, "present": True, "sha256": sha256_file(full_p)}
        else:
            meta_manifest[label] = {"target": full_p, "present": False, "sha256": ""}

    # 2. Hardlinks of all previously installed owner Data files
    owner_manifest: Dict[str, Dict[str, object]] = {}
    for rel_f in owner_rel_files:
        src_f = os.path.join(data_dir, *rel_f.replace("\\", "/").split("/"))
        if not os.path.isfile(src_f):
            raise BundleInstallRefused(f"Prior receipt lists missing file in Data, cannot safely link backup: {rel_f}")
        dst_f = os.path.join(owner_dir, *rel_f.replace("\\", "/").split("/"))
        link_mode = _hardlink_or_copy(src_f, dst_f, require_hardlink=require_hardlinks)
        st = os.stat(src_f)
        owner_manifest[rel_f] = {
            "size": st.st_size,
            "mtime_ns": st.st_mtime_ns,
            "sha256": sha256_file(src_f),
            "link_mode": link_mode,
        }

    with open(os.path.join(work_abs, "owner-files-before.json"), "w", encoding="utf-8") as fp:
        json.dump(owner_manifest, fp, indent=1)

    saves_dir = os.path.join(my_games_dir, "Saves") if my_games_dir else ""
    saves_rows: List[str] = []
    if saves_dir and os.path.isdir(saves_dir):
        for fn in sorted(os.listdir(saves_dir)):
            sp = os.path.join(saves_dir, fn)
            if os.path.isfile(sp):
                st = os.stat(sp)
                saves_rows.append(f"{fn}|{st.st_size}|{st.st_mtime_ns}")
    with open(os.path.join(work_abs, "saves-before.txt"), "w", encoding="utf-8") as fp:
        fp.write("\n".join(saves_rows) + ("\n" if saves_rows else ""))

    before_rows = compute_snapshot_rows(sf_abs, ptxt_abs, ini_paths)
    with open(os.path.join(work_abs, "hashes-before.txt"), "w", encoding="utf-8") as fp:
        fp.write("\n".join(before_rows) + "\n")

    # 3. Execute swap through plugin_toggle.py and exp_install.py
    root = Path(repo_root).resolve() if repo_root else Path(__file__).resolve().parents[2]
    exp_script = str(root / "scripts" / "game" / "exp_install.py")
    toggle_script = str(root / "scripts" / "game" / "plugin_toggle.py")
    op_log = os.path.join(work_abs, "bundle-install.log")

    toggle_path = os.path.join(data_dir, "FO4SF.toggle.json")
    prior_held: List[str] = []
    prior_toggle_why = "bundle swap hold"
    if os.path.isfile(toggle_path):
        with open(toggle_path, encoding="utf-8") as fp:
            t_data = json.load(fp)
        prior_held = [str(x) for x in (t_data.get("off") or [])]
        if t_data.get("why"):
            prior_toggle_why = str(t_data["why"])

    if prior_held:
        rc, out = _run_game_tool(toggle_script, ["on", "--starfield", sf_abs], ptxt_abs, op_log)
        if rc != 0:
            raise BundleInstallRefused(f"plugin_toggle.py on failed (rc={rc}): {out}")

    if os.path.isfile(prev_exp_path):
        rc, out = _run_game_tool(exp_script, ["uninstall", "--starfield", sf_abs], ptxt_abs, op_log)
        if rc != 0:
            raise BundleInstallRefused(f"exp_install.py uninstall failed (rc={rc}); run rollback: {out}")

    install_args = ["install", "--exp-dir", bundle_abs, "--starfield", sf_abs, "--plugins", ",".join(plugins)]
    if prepacked_ba2:
        install_args += ["--pack", "--prepacked", prepacked_ba2]
    elif prepacked_dir:
        install_args += ["--pack", "--prepacked-dir", prepacked_dir]
    elif has_loose_data:
        install_args.append("--pack")
        if split_archives != "none":
            install_args += ["--split-archives", split_archives, "--max-archive-bytes", str(max_archive_bytes)]

    rc, out = _run_game_tool(exp_script, install_args, ptxt_abs, op_log)
    if rc != 0:
        raise BundleInstallRefused(f"exp_install.py install failed (rc={rc}); run rollback: {out}")

    added_sidecars: Dict[str, str] = {}
    for rel_sc, src_sc in sidecar_rel_files:
        dst_sc = os.path.join(data_dir, *rel_sc.split("/"))
        _copy_preserving_bytes_and_stat(src_sc, dst_sc)
        added_sidecars[rel_sc] = sha256_file(dst_sc)

    # Restore non-experiment holds (such as FO4SFBridge.esm) that remain owned after swap
    new_plugin_set = {p.casefold() for p in plugins}
    rehold = [p for p in prior_held if p.casefold() not in new_plugin_set or p.casefold() == "fo4sfbridge.esm"]
    if rehold:
        rc, out = _run_game_tool(
            toggle_script,
            ["off", "--plugins", ",".join(rehold), "--starfield", sf_abs, "--why", prior_toggle_why],
            ptxt_abs,
            op_log,
        )
        if rc != 0:
            raise BundleInstallRefused(f"plugin_toggle.py off restore failed (rc={rc}); run rollback: {out}")
        before_toggle = os.path.join(before_dir, "FO4SF.toggle.json")
        if os.path.isfile(before_toggle) and os.path.isfile(toggle_path):
            with open(before_toggle, "rb") as f1, open(toggle_path, "rb") as f2:
                same_toggle = f1.read() == f2.read()
            if same_toggle:
                _copy_preserving_bytes_and_stat(before_toggle, toggle_path)

    rc, out = _run_game_tool(exp_script, ["order", "--starfield", sf_abs], ptxt_abs, op_log)
    if rc != 0:
        raise BundleInstallRefused(f"exp_install.py order failed (rc={rc}); run rollback: {out}")

    rc, out = _run_game_tool(exp_script, ["active", "--starfield", sf_abs], ptxt_abs, op_log)
    if rc != 0:
        raise BundleInstallRefused(f"exp_install.py active failed (rc={rc}); run rollback: {out}")

    # 4. Run dynamic post-check (verifies actual archive names in FO4SFExp.install.json, never hardcoded!)
    post = run_postcheck(sf_abs, ptxt_abs)

    after_rows = compute_snapshot_rows(sf_abs, ptxt_abs, ini_paths)
    with open(os.path.join(work_abs, "hashes-after.txt"), "w", encoding="utf-8") as fp:
        fp.write("\n".join(after_rows) + "\n")
    _copy_preserving_bytes_and_stat(ptxt_abs, os.path.join(work_abs, "Plugins.after-install.txt"))

    receipt = {
        "kind": "fo4sf-bundle-install-receipt",
        "version": 1,
        "installed_at": _now_utc_iso(),
        "bundle_dir": bundle_abs,
        "starfield_dir": sf_abs,
        "work_dir": work_abs,
        "plugins_txt": ptxt_abs,
        "my_games_dir": my_games_dir,
        "plugins": post["plugins"],
        "archives": post["archives"],
        "verified_files": post["verified_files"],
        "added_sidecars": added_sidecars,
        "backed_up_configs": backed_up_configs,
        "ini_manifest": ini_manifest,
        "meta_manifest": meta_manifest,
        "owner_files_before": owner_manifest,
        "hashes_before_rows": len(before_rows),
        "hashes_after_rows": len(after_rows),
        "save_warning": save_warning or "",
    }
    receipt_path = os.path.join(work_abs, "install_receipt.json")
    with open(receipt_path, "w", encoding="utf-8") as fp:
        json.dump(receipt, fp, indent=1)

    print(
        f"POST-CHECK OK: {len(post['plugins'])} plugin(s), "
        f"archives={post['archives'] or ['none']}, receipt={os.path.basename(receipt_path)}"
    )
    return receipt


def rollback_bundle(
    *,
    work_dir: str,
    starfield_dir: str = "",
    plugins_txt_path: str = "",
    dry_run: bool = False,
    pids_fn: Optional[Callable[[str], Sequence[int]]] = None,
    launcher_open_fn: Optional[Callable[[], bool]] = None,
    repo_root: Optional[str] = None,
) -> Dict[str, object]:
    """Cleanly uninstall the bundle, restore byte-identical owner files/configs, and report every comparison."""
    work_abs = os.path.abspath(work_dir)
    receipt_path = os.path.join(work_abs, "install_receipt.json")
    if not os.path.isfile(receipt_path):
        raise BundleInstallRefused(f"Cannot roll back: missing {receipt_path}")

    with open(receipt_path, encoding="utf-8") as fp:
        receipt = json.load(fp)

    sf_abs = os.path.abspath(starfield_dir or receipt["starfield_dir"])
    ptxt_abs = os.path.abspath(plugins_txt_path or receipt["plugins_txt"])
    data_dir = os.path.join(sf_abs, "Data")
    before_dir = os.path.join(work_abs, "before-files")
    owner_dir = os.path.join(work_abs, "owner-files")

    launcher_meta = (receipt.get("meta_manifest") or {}).get("launcher_settings.json") or {}
    check_not_running(
        sf_abs,
        launcher_settings_path=str(launcher_meta.get("target") or ""),
        pids_fn=pids_fn,
        launcher_open_fn=launcher_open_fn,
    )

    owner_manifest: Dict[str, Dict[str, object]] = dict(receipt.get("owner_files_before") or {})
    for rel_f, info in sorted(owner_manifest.items()):
        saved_f = os.path.join(owner_dir, *rel_f.replace("\\", "/").split("/"))
        if not os.path.isfile(saved_f):
            raise BundleInstallRefused(f"Rollback refused: backup owner file missing: {saved_f}")
        actual_sha = sha256_file(saved_f)
        if actual_sha.lower() != str(info["sha256"]).lower():
            raise BundleInstallRefused(
                f"Rollback refused: backup owner file {rel_f} is corrupted "
                f"(expected {str(info['sha256'])[:12]}, got {actual_sha[:12]})"
            )

    before_ptxt = os.path.join(before_dir, "Plugins.txt")
    if not os.path.isfile(before_ptxt):
        raise BundleInstallRefused(f"Rollback refused: missing backup {before_ptxt}")

    if dry_run:
        summary = {
            "mode": "dry-run",
            "action": "rollback",
            "starfield_dir": sf_abs,
            "work_dir": work_abs,
            "owner_files_verified": sorted(owner_manifest.keys()),
            "sidecars_to_remove": sorted((receipt.get("added_sidecars") or {}).keys()),
            "inis_to_compare": [m["name"] for m in (receipt.get("ini_manifest") or [])],
        }
        print(
            f"DRY-RUN rollback: verified {len(owner_manifest)} backup owner file(s), "
            f"sidecars_to_remove={len(summary['sidecars_to_remove'])}, writes=0"
        )
        return summary

    root = Path(repo_root).resolve() if repo_root else Path(__file__).resolve().parents[2]
    exp_script = str(root / "scripts" / "game" / "exp_install.py")
    toggle_script = str(root / "scripts" / "game" / "plugin_toggle.py")
    op_log = os.path.join(work_abs, "bundle-rollback.log")

    # 1. Release any active toggle holds and uninstall the current experiment if receipt differs from before
    live_exp = os.path.join(data_dir, "FO4SFExp.install.json")
    before_exp = os.path.join(before_dir, "FO4SFExp.install.json")
    exp_meta = (receipt.get("meta_manifest") or {}).get("FO4SFExp.install.json") or {}
    already_before = (
        bool(exp_meta.get("present"))
        and os.path.isfile(live_exp)
        and os.path.isfile(before_exp)
        and sha256_file(live_exp) == sha256_file(before_exp)
    ) or (not exp_meta.get("present") and not os.path.exists(live_exp))

    if not already_before:
        live_toggle = os.path.join(data_dir, "FO4SF.toggle.json")
        if os.path.isfile(live_toggle):
            with open(live_toggle, encoding="utf-8") as fp:
                held = (json.load(fp).get("off") or [])
            if held:
                rc, out = _run_game_tool(toggle_script, ["on", "--starfield", sf_abs], ptxt_abs, op_log)
                if rc != 0:
                    raise BundleInstallRefused(f"Rollback plugin_toggle.py on failed (rc={rc}): {out}")

        if os.path.isfile(live_exp):
            rc, out = _run_game_tool(exp_script, ["uninstall", "--starfield", sf_abs], ptxt_abs, op_log)
            if rc != 0:
                raise BundleInstallRefused(f"Rollback exp_install.py uninstall failed (rc={rc}): {out}")

        # Remove any SFSE sidecars added by bundle install
        for rel_sc, expected_sc_sha in sorted((receipt.get("added_sidecars") or {}).items()):
            dst_sc = os.path.join(data_dir, *rel_sc.split("/"))
            if os.path.isfile(dst_sc):
                if sha256_file(dst_sc).lower() != str(expected_sc_sha).lower():
                    raise BundleInstallRefused(f"Rollback refused: SFSE sidecar {rel_sc} modified since install")
                _remove_file(dst_sc)

        # Link or copy back every prior owner file and restore exact mtime
        for rel_f, info in sorted(owner_manifest.items()):
            dst_f = os.path.join(data_dir, *rel_f.replace("\\", "/").split("/"))
            if os.path.lexists(dst_f):
                raise BundleInstallRefused(f"Rollback refused: {rel_f} still exists in Data after uninstall")
            saved_f = os.path.join(owner_dir, *rel_f.replace("\\", "/").split("/"))
            _hardlink_or_copy(saved_f, dst_f, require_hardlink=False)
            _make_writable_if_exists(dst_f)
            mtime_ns = int(info["mtime_ns"])
            os.utime(dst_f, ns=(mtime_ns, mtime_ns))

        if exp_meta.get("present"):
            _copy_preserving_bytes_and_stat(before_exp, live_exp)
        elif os.path.exists(live_exp):
            _remove_file(live_exp)

    # 2. Restore toggle record, launcher_settings.json, INI files, and Plugins.txt byte-for-byte
    meta_manifest = receipt.get("meta_manifest") or {}
    for label in ("FO4SF.toggle.json", "launcher_settings.json"):
        info = meta_manifest.get(label) or {}
        target = str(info.get("target") or "")
        if not target:
            continue
        if info.get("present"):
            _copy_preserving_bytes_and_stat(os.path.join(before_dir, label), target)
        elif os.path.exists(target):
            _remove_file(target)

    ini_manifest: List[Dict[str, object]] = list(receipt.get("ini_manifest") or [])
    ini_backup_dir = os.path.join(before_dir, "inis")
    for ini_item in ini_manifest:
        target = str(ini_item["target"])
        if ini_item.get("present"):
            _copy_preserving_bytes_and_stat(os.path.join(ini_backup_dir, str(ini_item["slot"])), target)
        elif os.path.exists(target):
            _remove_file(target)

    _copy_preserving_bytes_and_stat(before_ptxt, ptxt_abs)

    # 3. Verify byte-identical restoration and print explicit comparison report
    comparisons: List[str] = []

    ptxt_before_sha = str((receipt.get("backed_up_configs") or {}).get("Plugins.txt", {}).get("sha256") or sha256_file(before_ptxt))
    ptxt_after_sha = sha256_file(ptxt_abs)
    if ptxt_after_sha != ptxt_before_sha:
        raise BundleInstallRefused(f"Rollback comparison failed: Plugins.txt SHA-256 {ptxt_after_sha} != {ptxt_before_sha}")
    comparisons.append(f"COMPARED Plugins.txt bytes: BYTE-IDENTICAL (sha256={ptxt_after_sha[:16]}...)")

    compared_inis: List[str] = []
    for ini_item in ini_manifest:
        target = str(ini_item["target"])
        bname = str(ini_item["name"])
        if ini_item.get("present"):
            now_sha = sha256_file(target)
            if now_sha != str(ini_item["sha256"]):
                raise BundleInstallRefused(f"Rollback comparison failed: INI {bname} SHA-256 {now_sha} != {ini_item['sha256']}")
            compared_inis.append(f"{bname}=IDENTICAL")
        else:
            if os.path.exists(target):
                raise BundleInstallRefused(f"Rollback comparison failed: INI {bname} existed after rollback but was absent before")
            compared_inis.append(f"{bname}=ABSENT-AS-BEFORE")
    comparisons.append(f"COMPARED INI files ({len(ini_manifest)}): {', '.join(compared_inis) or 'none'}")

    restored_archives: List[str] = []
    for rel_f, info in sorted(owner_manifest.items()):
        dst_f = os.path.join(data_dir, *rel_f.replace("\\", "/").split("/"))
        if not os.path.isfile(dst_f):
            raise BundleInstallRefused(f"Rollback comparison failed: owner file missing after restore: {rel_f}")
        now_sha = sha256_file(dst_f)
        if now_sha.lower() != str(info["sha256"]).lower():
            raise BundleInstallRefused(f"Rollback comparison failed: owner file {rel_f} SHA-256 mismatch")
        if rel_f.lower().endswith(".ba2"):
            restored_archives.append(f"{rel_f} ({now_sha[:12]}...)")
    comparisons.append(
        f"COMPARED owner Data files ({len(owner_manifest)} file(s); archives: {', '.join(restored_archives) or 'none'}): BYTE-IDENTICAL"
    )

    for label in ("FO4SFExp.install.json", "FO4SF.toggle.json", "launcher_settings.json"):
        info = meta_manifest.get(label) or {}
        target = str(info.get("target") or "")
        if not target:
            continue
        if info.get("present"):
            now_sha = sha256_file(target)
            if now_sha != str(info["sha256"]):
                raise BundleInstallRefused(f"Rollback comparison failed: {label} SHA-256 mismatch")
            comparisons.append(f"COMPARED {label}: BYTE-IDENTICAL ({now_sha[:12]}...)")
        else:
            if os.path.exists(target):
                raise BundleInstallRefused(f"Rollback comparison failed: {label} still present after rollback")
            comparisons.append(f"COMPARED {label}: ABSENT-AS-BEFORE")

    ini_targets = [str(m["target"]) for m in ini_manifest]
    rollback_rows = compute_snapshot_rows(sf_abs, ptxt_abs, ini_targets)
    with open(os.path.join(work_abs, "hashes-rollback.txt"), "w", encoding="utf-8") as fp:
        fp.write("\n".join(rollback_rows) + "\n")

    with open(os.path.join(work_abs, "hashes-before.txt"), encoding="utf-8") as fp:
        before_rows = [ln.rstrip("\r\n") for ln in fp if ln.strip()]

    if rollback_rows != before_rows:
        added = sorted(set(rollback_rows) - set(before_rows))[:5]
        missing = sorted(set(before_rows) - set(rollback_rows))[:5]
        raise BundleInstallRefused(
            f"Rollback snapshot rows differ from hashes-before.txt (missing={missing}, extra={added})"
        )
    comparisons.append(
        f"COMPARED hashes-before.txt vs hashes-rollback.txt (Data, SFSE, Root, Plugins.txt, INIs): IDENTICAL ({len(rollback_rows)} rows)"
    )

    for line in comparisons:
        print(line)

    return {
        "ok": True,
        "rows_compared": len(rollback_rows),
        "owner_files_restored": len(owner_manifest),
        "comparisons": comparisons,
    }
