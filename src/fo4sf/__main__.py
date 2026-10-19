"""Minimal CLI for fo4-to-starfield.

python -m fo4sf status   # print config summary and optional manifest coverage (requires config.toml)
python -m fo4sf ba2-largest PATH.ba2 [--n 20]   # show largest entries by unpacked size (conversion planning)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .manifest import ManifestError, load_manifest, summarize_manifest
from .ba2 import Ba2, Ba2Error


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


def cmd_ba2_largest(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.is_file():
        print(f"error: {path} is not a file", file=sys.stderr)
        return 1
    try:
        archive = Ba2(str(path))
    except Ba2Error as e:
        print(f"ba2 error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"failed to read {path}: {e}", file=sys.stderr)
        return 1

    n = max(0, args.n)
    largest = archive.largest_entries(n)
    print(f"{path} ({archive.kind} v{archive.version}, {len(archive.entries)} entries)")
    if not largest:
        print("  (no entries)")
        return 0
    print(f"  Top {len(largest)} by unpacked size:")
    for i, e in enumerate(largest, 1):
        ratio = e["packed"] / e["unpacked"] if e["unpacked"] else 0
        print(f"  {i:2}. {e['unpacked']:12,} B unpacked  {e['packed']:12,} B packed  ({ratio:.2f}x)  {e['kind']:4}  {e['name']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fo4sf", description="Fallout 4 → Starfield conversion tools")
    parser.add_argument("--config", help="path to config.toml (default: ./config.toml)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="show configuration summary and manifest coverage")
    p_status.add_argument("--manifest", help="explicit path to manifest.json")
    p_status.set_defaults(func=cmd_status)

    p_ba2 = sub.add_parser("ba2-largest", help="list largest entries in a BA2 by unpacked size (conversion planning)")
    p_ba2.add_argument("path", help="path to a .ba2 file")
    p_ba2.add_argument("--n", type=int, default=10, help="number of largest entries to show (default 10)")
    p_ba2.set_defaults(func=cmd_ba2_largest)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
