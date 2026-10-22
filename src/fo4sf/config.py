"""Load and validate fo4-to-starfield config.toml.

Uses tomllib (Python 3.11+). Paths are returned as absolute pathlib.Path objects.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore


class ConfigError(ValueError):
    """Raised when config.toml is missing required sections or values."""


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load config.toml (or the given path) and return a normalised dict.

    Expected sections: fo4, starfield, paths, tools.
    Missing file raises ConfigError. Unknown keys are preserved.
    Paths are resolved to absolute Path objects.
    """
    if tomllib is None:
        raise ConfigError("tomllib requires Python 3.11+")

    cfg_path = Path(path) if path else Path("config.toml")
    if not cfg_path.is_file():
        raise ConfigError(f"config file not found: {cfg_path}")

    with cfg_path.open("rb") as f:
        data = tomllib.load(f)

    # Normalise known path fields to absolute Paths
    def abs_path(p: str) -> Path:
        return Path(p).expanduser().resolve()

    if "fo4" in data and "data_dirs" in data["fo4"]:
        data["fo4"]["data_dirs"] = [abs_path(p) for p in data["fo4"]["data_dirs"]]
    if "starfield" in data and "data_dir" in data["starfield"]:
        data["starfield"]["data_dir"] = abs_path(data["starfield"]["data_dir"])
    if "paths" in data:
        for key in ("work_dir", "staging_dir"):
            if key in data["paths"]:
                data["paths"][key] = abs_path(data["paths"][key])
    if "tools" in data:
        for key, val in list(data["tools"].items()):
            if isinstance(val, str):
                data["tools"][key] = abs_path(val)

    # Enforce presence of core sections early so callers get a clear error
    for section in ("fo4", "starfield", "paths"):
        if section not in data:
            raise ConfigError(f"missing required section [{section}]")

    return data


def require_section(cfg: dict[str, Any], section: str) -> dict[str, Any]:
    if section not in cfg:
        raise ConfigError(f"missing required section [{section}]")
    return cfg[section]
