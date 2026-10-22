"""Minimal CLI for fo4-to-starfield.

python -m fo4sf status   # print config summary (including directory existence) and optional manifest coverage (requires config.toml)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .manifest import ManifestError, load_manifest, summarize_manifest


def cmd_status(args: argparse.Namespace) -> int:
    try:
        cfg = load_config(args.config)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 1

    print("fo4-to-starfield status")
    print(f"  config: {Path(args.config or 'config.toml').resolve()}")
    fo4 = cfg.get("fo4", {})
    data_dirs = fo4.get("data_dirs", [])
    print(f"  Fallout 4 data dirs: {len(data_dirs)} configured")
    for i, d in enumerate(data_dirs):
        exists = d.is_dir() if isinstance(d, Path) else Path(d).is_dir()
        print(f"    [{i}] {d} ({'exists' if exists else 'MISSING'})")
    sf = cfg.get("starfield", {})
    sf_dir = sf.get("data_dir")
    if sf_dir:
        exists = sf_dir.is_dir() if isinstance(sf_dir, Path) else Path(sf_dir).is_dir()
        print(f"  Starfield data dir: {sf_dir} ({'exists' if exists else 'MISSING'})")
    else:
        print("  Starfield data dir: missing")
    paths = cfg.get("paths", {})
    for key in ("work_dir", "staging_dir"):
        d = paths.get(key)
        if d:
            exists = d.is_dir() if isinstance(d, Path) else Path(d).is_dir()
            print(f"  {key}: {d} ({'exists' if exists else 'MISSING or not created'})")
        else:
            print(f"  {key}: missing")

    if args.manifest:
        return _print_manifest(Path(args.manifest))

    # Optional auto-discovery in staging_dir or work_dir
    for key in ("staging_dir", "work_dir"):
        d = paths.get(key)
        if d:
            cand = Path(d) / "manifest.json"
            if cand.is_file():
                return _print_manifest(cand)
    print("  Manifest: not found (run a conversion stage to generate one)")
    return 0


def _print_manifest(manifest_path: Path) -> int:
    try:
        items = load_manifest(manifest_path)
    except ManifestError as e:
        print(f"  manifest error: {e}", file=sys.stderr)
        return 1
    summary = summarize_manifest(items)
    print(f"\n  Manifest: {manifest_path} ({summary['total']} items)")
    if summary["by_type"]:
        print("  By type:")
        for k, v in sorted(summary["by_type"].items()):
            print(f"    {k}: {v}")
    if summary["by_tier"]:
        print("  By fidelity tier:")
        for k, v in sorted(summary["by_tier"].items()):
            print(f"    {k}: {v}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fo4sf", description="Fallout 4 → Starfield conversion tools")
    parser.add_argument("--config", help="path to config.toml (default: ./config.toml)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="show configuration summary (with dir existence), and manifest coverage")
    p_status.add_argument("--manifest", help="explicit path to manifest.json")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
