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
    """One-line summary of configured paths."""
    fo4 = cfg.get("fo4", {}).get("data_dirs", ["(not set)"])
    sf = cfg.get("starfield", {}).get("data_dir", "(not set)")
    work = cfg.get("paths", {}).get("work_dir", "(not set)")
    staging = cfg.get("paths", {}).get("staging_dir", "(not set)")
    return f"FO4 data: {fo4[0] if fo4 else '(none)'}; SF data: {sf}; work: {work}; staging: {staging}"
