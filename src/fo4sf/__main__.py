"""Minimal CLI for fo4-to-starfield.

python -m fo4sf status   # print config summary and optional manifest coverage (requires config.toml)
"""
from __future__ import annotations

import argparse
import json
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
        rc = _print_manifest(Path(args.manifest))
        _print_failure_summary(Path(args.manifest).parent)
        return rc

    # Optional auto-discovery in staging_dir or work_dir
    for key in ("staging_dir", "work_dir"):
        d = paths.get(key)
        if d:
            base = Path(d)
            cand = base / "manifest.json"
            if cand.is_file():
                rc = _print_manifest(cand)
                _print_failure_summary(base)
                return rc
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



def _print_failure_summary(base: Path) -> None:
    """Print a short failure-summary if present next to the manifest."""
    summary_path = base / "failure-summary.json"
    if not summary_path.is_file():
        return
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("failure summary must be an object")
        attempted = data.get("attempted", 0)
        successes = data.get("successes", 0)
        total_fail = data.get("total_failures", 0)
        pct = data.get("success_percent", 0.0)
        top = data.get("top")
        if top is None:
            top = []
        if not isinstance(top, list):
            raise ValueError("failure summary top must be a list")
        # Render the complete advisory report before printing any success banner.
        lines = [f"\n  Latest batch: {successes}/{attempted} succeeded ({pct}%), {total_fail} failures"]
        if top:
            lines.append("  Top failure reasons:")
            for item in top[:3]:
                if not isinstance(item, dict):
                    raise ValueError("failure summary reason must be an object")
                lines.append(
                    f"    {item.get('count', 0):4d} ({item.get('percent', 0):5.1f}%)  {item.get('reason', '')[:60]}"
                )
    except (OSError, UnicodeError, ValueError, TypeError) as e:
        print(f"  failure-summary error: {e}", file=sys.stderr)
        return
    print("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fo4sf", description="Fallout 4 → Starfield conversion tools")
    parser.add_argument("--config", help="path to config.toml (default: ./config.toml)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="show configuration summary and manifest coverage")
    p_status.add_argument("--manifest", help="explicit path to manifest.json")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
