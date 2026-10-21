"""Minimal CLI for fo4-to-starfield.

python -m fo4sf status    # print config summary and optional manifest coverage
python -m fo4sf validate  # check paths, tools, and dependencies
"""
from __future__ import annotations

import argparse
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
    print(f"  Fallout 4 data dirs: {len(fo4.get('data_dirs', []))} configured")
    sf = cfg.get("starfield", {})
    print(f"  Starfield data dir: {'set' if sf.get('data_dir') else 'missing'}")
    paths = cfg.get("paths", {})
    print(f"  work_dir: {paths.get('work_dir', 'missing')}")
    print(f"  staging_dir: {paths.get('staging_dir', 'missing')}")

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

    # Paths
    fo4 = cfg.get("fo4", {})
    data_dirs = fo4.get("data_dirs", [])
    print(f"  Fallout 4 data dirs ({len(data_dirs)}):")
    for d in data_dirs:
        p = Path(d)
        status = "exists" if p.is_dir() else "NOT FOUND"
        print(f"    {d}: {status}")
        if not p.is_dir():
            ok = False

    sf = cfg.get("starfield", {})
    sf_dir = sf.get("data_dir")
    if sf_dir:
        p = Path(sf_dir)
        status = "exists" if p.is_dir() else "NOT FOUND"
        print(f"  Starfield data dir: {sf_dir}: {status}")
        if not p.is_dir():
            ok = False
    else:
        print("  Starfield data dir: missing in config")
        ok = False

    paths = cfg.get("paths", {})
    for key in ("work_dir", "staging_dir"):
        d = paths.get(key)
        if d:
            p = Path(d)
            status = "exists" if p.is_dir() else "NOT FOUND (will be created by tools)"
            print(f"  {key}: {d}: {status}")
        else:
            print(f"  {key}: missing in config")
            ok = False

    # Common tools
    print("  Tools:")
    tools = {
        "texconv": shutil.which("texconv") or shutil.which("Texconvx64"),
        "python": sys.executable,
    }
    # Check for optional from config
    if "tools" in cfg:
        for name, path in cfg["tools"].items():
            tools[name] = path

    for name, path in tools.items():
        if path and Path(path).exists():
            print(f"    {name}: found at {path}")
        elif path:
            print(f"    {name}: configured but NOT FOUND at {path}")
            ok = False
        else:
            print(f"    {name}: not found in PATH")
            # texconv is often required, but not always fatal for status
            if name == "texconv":
                print("      (required for texture conversion)")
                ok = False

    # Python deps
    print("  Python packages:")
    for pkg in ("numpy", "Pillow"):
        try:
            __import__(pkg)
            print(f"    {pkg}: available")
        except ImportError:
            print(f"    {pkg}: MISSING (pip install {pkg})")
            ok = False

    if ok:
        print("\n  Validation: OK")
        return 0
    else:
        print("\n  Validation: FAILED (see above)", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fo4sf", description="Fallout 4 → Starfield conversion tools")
    parser.add_argument("--config", help="path to config.toml (default: ./config.toml)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="show configuration summary and manifest coverage")
    p_status.add_argument("--manifest", help="explicit path to manifest.json")
    p_status.set_defaults(func=cmd_status)

    p_validate = sub.add_parser("validate", help="validate config paths, tools, and dependencies")
    p_validate.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
