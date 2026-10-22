"""Minimal CLI for fo4-to-starfield.

python -m fo4sf status    # print config summary (including directory existence) and optional manifest coverage
python -m fo4sf validate  # check paths, tools, and dependencies (PYTHONPATH=src)
"""
from __future__ import annotations

import argparse
import os
import shutil
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
        if d is None:
            print(f"    [{i}] (blank) (MISSING)")
            continue
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


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate config, paths, and common tools for the conversion toolchain."""
    try:
        cfg = load_config(args.config)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 1

    print("fo4-to-starfield validate")
    ok = True

    fo4 = cfg.get("fo4", {})
    data_dirs = fo4.get("data_dirs", [])
    print(f"  Fallout 4 data dirs ({len(data_dirs)}):")
    if not data_dirs:
        print("    none configured")
        ok = False
    for d in data_dirs:
        if d is None:
            print("    (blank entry): NOT FOUND")
            ok = False
            continue
        p = Path(d)
        if p.is_dir():
            print(f"    {d}: exists")
        else:
            print(f"    {d}: NOT FOUND")
            ok = False

    sf = cfg.get("starfield", {})
    sf_dir = sf.get("data_dir")
    if sf_dir:
        p = Path(sf_dir)
        if p.is_dir():
            print(f"  Starfield data dir: {sf_dir}: exists")
        else:
            print(f"  Starfield data dir: {sf_dir}: NOT FOUND")
            ok = False
    else:
        print("  Starfield data dir: missing in config")
        ok = False

    paths = cfg.get("paths", {})
    for key in ("work_dir", "staging_dir"):
        d = paths.get(key)
        if not d:
            print(f"  {key}: missing in config")
            ok = False
            continue
        p = Path(d)
        if p.is_dir():
            print(f"  {key}: {d}: exists")
        elif p.exists():
            print(f"  {key}: {d}: not a directory")
            ok = False
        else:
            print(f"  {key}: {d}: NOT FOUND (will be created by tools)")

    print("  Tools:")
    tools = {
        "texconv": shutil.which("texconv") or shutil.which("Texconvx64"),
        "python": sys.executable,
    }
    configured = set(cfg.get("tools", {}))
    if "tools" in cfg:
        for name, path in cfg["tools"].items():
            tools[name] = path
    for name, path in tools.items():
        if path and Path(path).is_file() and os.access(path, os.X_OK):
            print(f"    {name}: found at {path}")
        elif path and Path(path).exists():
            print(f"    {name}: not an executable file at {path}")
            ok = False
        elif path:
            print(f"    {name}: configured but NOT FOUND at {path}")
            ok = False
        elif name in configured:
            print(f"    {name}: configured but blank")
            ok = False
        else:
            print(f"    {name}: not found in PATH")
            if name == "texconv":
                print("      (required for texture conversion)")
                ok = False

    print("  Python packages:")
    for display, module in (("numpy", "numpy"), ("Pillow", "PIL")):
        try:
            __import__(module)
            print(f"    {display}: available")
        except ImportError:
            print(f"    {display}: MISSING (pip install {display})")
            ok = False

    if ok:
        print("\n  Validation: OK")
        return 0
    print("\n  Validation: FAILED (see above)", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fo4sf", description="Fallout 4 → Starfield conversion tools")
    parser.add_argument("--config", help="path to config.toml (default: ./config.toml)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="show configuration summary (with dir existence), and manifest coverage")
    p_status.add_argument("--manifest", help="explicit path to manifest.json")
    p_status.set_defaults(func=cmd_status)

    p_validate = sub.add_parser("validate", help="validate config paths, tools, and dependencies")
    p_validate.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
