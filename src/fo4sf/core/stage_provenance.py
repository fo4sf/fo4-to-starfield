"""Shared stage-provenance, directory SHA summary, and arg-normalization helpers."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def current_git_head(repo_dir: str) -> Optional[str]:
    """Return the current 40-char git commit SHA, or None outside a git checkout."""
    try:
        r = subprocess.run(
            ["git", "-C", repo_dir, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    sha = r.stdout.strip().lower()
    return sha if len(sha) >= 7 and all(c in "0123456789abcdef" for c in sha) else None


def is_git_dirty(repo_dir: str) -> Optional[bool]:
    """Return True if git working tree has uncommitted changes, False if clean, None if unavailable."""
    try:
        r = subprocess.run(
            ["git", "-C", repo_dir, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return bool(r.stdout.strip())


def _is_path_like(val: str) -> bool:
    if not val:
        return False
    if os.path.isabs(val):
        return True
    return ("/" in val or "\\" in val) and not val.startswith("-")


def _norm_path_value(val: str) -> str:
    return os.path.normpath(os.path.abspath(val)) if _is_path_like(val) else val


def normalize_args_for_compare(value: Any) -> Any:
    """Recursively normalize args/paths for cross-platform case-insensitive comparison."""
    if isinstance(value, Mapping):
        return {str(k): normalize_args_for_compare(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [normalize_args_for_compare(item) for item in value]
    if isinstance(value, str):
        if _is_path_like(value):
            return os.path.normcase(os.path.normpath(os.path.abspath(value)))
        return value
    return value


def canonicalize_cli_args(argv_tokens: Sequence[str]) -> Dict[str, Any]:
    """Convert a CLI token list into a deterministic sorted dict with normalized path values."""
    out: Dict[str, Any] = {}
    positional: list[str] = []
    tokens = list(argv_tokens)
    i = 0
    while i < len(tokens):
        tok = str(tokens[i])
        if tok.startswith("--"):
            if "=" in tok:
                k, v = tok.split("=", 1)
                out[k] = _norm_path_value(v)
                i += 1
                continue
            vals: list[str] = []
            j = i + 1
            while j < len(tokens) and not str(tokens[j]).startswith("--"):
                vals.append(_norm_path_value(str(tokens[j])))
                j += 1
            if not vals:
                out[tok] = True
            elif len(vals) == 1:
                out[tok] = vals[0]
            else:
                out[tok] = vals
            i = j
        else:
            positional.append(_norm_path_value(tok))
            i += 1
    if positional:
        out["_positional"] = positional
    return dict(sorted(out.items()))


def dir_sha_summary(path: Optional[str]) -> Optional[Dict[str, Any]]:
    """Compute a deterministic SHA-256 tree summary for an asset directory (or None if unset)."""
    if not path:
        return None
    abs_p = os.path.abspath(path)
    if not os.path.isdir(abs_p):
        return {
            "path": abs_p,
            "exists": False,
            "file_count": 0,
            "total_bytes": 0,
            "sha256": None,
        }
    tree_hash = hashlib.sha256()
    file_count = 0
    total_bytes = 0
    for dp, dirs, fns in os.walk(abs_p):
        dirs.sort()
        for fn in sorted(fns):
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, abs_p).replace("\\", "/")
            fsha = sha256_file(full)
            sz = os.path.getsize(full)
            tree_hash.update(f"{rel}\0{sz}\0{fsha}\n".encode("utf-8"))
            file_count += 1
            total_bytes += sz
    return {
        "path": abs_p,
        "exists": True,
        "file_count": file_count,
        "total_bytes": total_bytes,
        "sha256": tree_hash.hexdigest(),
    }


def collect_asset_dir_summaries(named_dirs: Mapping[str, Optional[str]]) -> Dict[str, Dict[str, Any]]:
    """Build `{key: dir_sha_summary}` for every non-empty path in `named_dirs`."""
    summaries: Dict[str, Dict[str, Any]] = {}
    for key in sorted(named_dirs):
        summary = dir_sha_summary(named_dirs[key])
        if summary is not None:
            summaries[key] = summary
    return summaries


def build_provenance(
    repo_dir: str,
    args_value: Any,
    *,
    asset_dirs: Optional[Mapping[str, Optional[str]]] = None,
    codsworth_race_framing: Optional[bool] = None,
    extra: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build standard provenance metadata for stage `plan.json` and `bundle_plan.json`."""
    prov: Dict[str, Any] = {
        "build_head": current_git_head(repo_dir),
        "dirty": is_git_dirty(repo_dir),
        "args": args_value,
        "asset_dirs": collect_asset_dir_summaries(asset_dirs or {}),
        "codsworth_race_framing": bool(codsworth_race_framing),
        "FO4SF_C5_ACTOR_LOOKS_DIR": os.environ.get("FO4SF_C5_ACTOR_LOOKS_DIR"),
    }
    if extra:
        for k, v in extra.items():
            prov[k] = v
    return prov


def stamp_stage_plan(
    stage_dir: str,
    provenance: Mapping[str, Any],
    *,
    plan_filename: str = "plan.json",
    defaults: Optional[Mapping[str, Any]] = None,
) -> str:
    """Merge provenance fields into `<stage_dir>/<plan_filename>` (creating it if absent)."""
    plan_path = os.path.join(os.path.abspath(stage_dir), plan_filename)
    plan: Dict[str, Any] = {}
    if os.path.isfile(plan_path):
        try:
            with open(plan_path, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                plan = loaded
        except (OSError, ValueError):
            plan = {}
    if not plan and defaults:
        plan.update(defaults)
    for k, v in provenance.items():
        plan[k] = v
    os.makedirs(os.path.dirname(plan_path), exist_ok=True)
    with open(plan_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(plan, f, indent=1)
        f.write("\n")
    return plan_path


def check_stage_reuse(
    stage_dir: str,
    expected_args: Any,
    *,
    plan_filename: str = "plan.json",
) -> None:
    """Raise ValueError if `stage_dir` exists and its recorded `args` in `plan_filename` are missing or differ."""
    if not os.path.exists(stage_dir):
        return
    plan_path = os.path.join(os.path.abspath(stage_dir), plan_filename)
    if not os.path.isfile(plan_path):
        raise ValueError(
            f"refusing to reuse existing stage {stage_dir}: missing {plan_filename} (use a fresh --work directory)"
        )
    try:
        with open(plan_path, encoding="utf-8") as f:
            plan = json.load(f)
    except (OSError, ValueError) as exc:
        raise ValueError(
            f"refusing to reuse existing stage {stage_dir}: unreadable {plan_filename} ({exc})"
        ) from exc
    if not isinstance(plan, dict) or "args" not in plan:
        raise ValueError(
            f"refusing to reuse existing stage {stage_dir}: {plan_filename} lacks recorded args (use a fresh --work directory)"
        )
    recorded_norm = normalize_args_for_compare(plan["args"])
    expected_norm = normalize_args_for_compare(expected_args)
    if recorded_norm != expected_norm:
        raise ValueError(
            f"refusing to reuse existing stage {stage_dir}: recorded args in {plan_filename} differ from requested args "
            f"(recorded={recorded_norm!r}, requested={expected_norm!r}); use a fresh --work directory"
        )
