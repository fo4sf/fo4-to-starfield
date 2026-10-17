"""Load config.toml for the fo4sf package.

Paths are absolute or relative to the repo root. Missing file is not an error for status.
"""
import os
try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib
from pathlib import Path
from typing import Optional


class ConfigError(ValueError):
    pass


def load_config(path: Optional[str] = None) -> dict:
    """Load config.toml. Returns empty dict if the file does not exist."""
    if path is None:
        path = os.environ.get("FO4SF_CONFIG", "config.toml")
    p = Path(path)
    if not p.exists():
        return {}
    try:
        with open(p, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        raise ConfigError(f"failed to parse {path}: {e}") from e


def status_summary(cfg: dict) -> str:
    """Multi-line summary of configured paths and versions, with existence checks."""
    lines = []
    fo4_dirs = cfg.get("fo4", {}).get("data_dirs", [])
    fo4_ver = cfg.get("fo4", {}).get("version", "(not set)")
    if fo4_dirs:
        fo4_path = fo4_dirs[0]
        exists = "exists" if Path(fo4_path).is_dir() else "MISSING"
        lines.append(f"FO4 data: {fo4_path} ({exists}); version: {fo4_ver}")
    else:
        lines.append("FO4 data: (not set)")

    sf_dir = cfg.get("starfield", {}).get("data_dir", "(not set)")
    sf_ver = cfg.get("starfield", {}).get("version", "(not set)")
    if sf_dir != "(not set)":
        exists = "exists" if Path(sf_dir).is_dir() else "MISSING"
        lines.append(f"Starfield data: {sf_dir} ({exists}); version: {sf_ver}")
    else:
        lines.append("Starfield data: (not set)")

    work = cfg.get("paths", {}).get("work_dir", "(not set)")
    staging = cfg.get("paths", {}).get("staging_dir", "(not set)")
    if work != "(not set)":
        exists = "exists" if Path(work).is_dir() else "MISSING"
        lines.append(f"work_dir: {work} ({exists})")
    else:
        lines.append("work_dir: (not set)")
    if staging != "(not set)":
        exists = "exists" if Path(staging).is_dir() else "MISSING"
        lines.append(f"staging_dir: {staging} ({exists})")
    else:
        lines.append("staging_dir: (not set)")
    return "\n".join(lines)
