"""Minimal CLI for fo4-to-starfield.

python -m fo4sf status   # print config summary (requires config.toml)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigError, load_config


def cmd_status(args: argparse.Namespace) -> int:
    try:
        cfg = load_config(args.config)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 1

    print("fo4-to-starfield status")
    print(f"  config: {Path(args.config or 'config.toml').resolve()}")
    fo4 = cfg.get("fo4", {})
    print(f"  Fallout 4 data dirs: {len(fo4.get('data_dirs', []))} configured")
    sf = cfg.get("starfield", {})
    print(f"  Starfield data dir: {'set' if sf.get('data_dir') else 'missing'}")
    paths = cfg.get("paths", {})
    print(f"  work_dir: {paths.get('work_dir', 'missing')}")
    print(f"  staging_dir: {paths.get('staging_dir', 'missing')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fo4sf", description="Fallout 4 → Starfield conversion tools")
    parser.add_argument("--config", help="path to config.toml (default: ./config.toml)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="show configuration summary")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
