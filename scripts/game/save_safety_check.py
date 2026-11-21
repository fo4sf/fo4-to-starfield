#!/usr/bin/env python3
"""Compare two Starfield/FO4SF builds or bundles for savegame compatibility.

Usage:
  python scripts/game/save_safety_check.py --before <prev-dir> --after <next-dir>
                                           [--before-plugins a.esm,b.esm] [--after-plugins a.esm,b.esm]
                                           [--json] [--out <report-path>]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from fo4sf.save_safety import (  # noqa: E402
    SaveSafetyError,
    compare_builds,
    format_text_report,
)


def _split_csv(val: str):
    items = [x.strip() for x in val.split(",") if x.strip()]
    return items or None


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Check whether swapping between two builds will invalidate saves.")
    ap.add_argument("--before", required=True, help="Previous staged bundle or installed Starfield directory.")
    ap.add_argument("--after", required=True, help="Next staged bundle or installed Starfield directory.")
    ap.add_argument("--before-plugins", default="", help="Optional comma-separated plugin list for --before.")
    ap.add_argument("--after-plugins", default="", help="Optional comma-separated plugin list for --after.")
    ap.add_argument("--json", action="store_true", help="Emit structured JSON report.")
    ap.add_argument("--out", default="", help="Optional file path to write the report.")
    ap.add_argument(
        "--fail-on-breaking",
        action="store_true",
        help="Exit with code 2 when the swap is BREAKING.",
    )
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = compare_builds(
            args.before,
            args.after,
            before_plugins=_split_csv(args.before_plugins),
            after_plugins=_split_csv(args.after_plugins),
        )
    except SaveSafetyError as exc:
        sys.stderr.write(f"save_safety_check: {exc}\n")
        return 1

    rendered = json.dumps(report, indent=2) + "\n" if args.json else format_text_report(report)
    if args.out:
        out_abs = os.path.abspath(args.out)
        parent = os.path.dirname(out_abs)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(out_abs, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)

    sys.stdout.write(rendered)
    if args.fail_on_breaking and report["verdict"] == "BREAKING":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
