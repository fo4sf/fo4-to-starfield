#!/usr/bin/env python3
"""Read Papyrus, SFSE, and crash/process logs from a soak session into a phone-sized report.

Usage:
  python scripts/testing/soak_log_reader.py <log-dir> [--crash-dir <dir>] [--sfse-log-dir <dir>]
                                            [--driver-log <file>] [--include-rotated] [--json] [--out <path>]
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

from fo4sf.testing.soak_report import (  # noqa: E402
    DEFAULT_STALL_SECONDS,
    PHONE_MAX_LINES,
    PHONE_MAX_WIDTH,
    analyze_session,
    format_phone_report,
)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Summarize Starfield Papyrus, SFSE, and crash logs into a phone-readable soak report."
    )
    ap.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Session log folder or Starfield user directory (e.g. <My Games>/Starfield or .../Logs).",
    )
    ap.add_argument("--log-dir", default=None, help="Explicit log root (overrides positional path).")
    ap.add_argument("--sfse-log-dir", default=None, help="Explicit SFSE/Logs directory.")
    ap.add_argument("--crash-dir", default=None, help="Directory scanned for .dmp crash dumps.")
    ap.add_argument("--driver-log", default=None, help="Explicit driver/monitor/crashwatch log file.")
    ap.add_argument(
        "--include-rotated",
        action="store_true",
        help="Read rotated .1.log files alongside .0.log files as separate ordered segments.",
    )
    ap.add_argument(
        "--all-ages",
        action="store_true",
        help="Include older leftover logs from previous days instead of filtering to the latest 12h session window.",
    )
    ap.add_argument(
        "--stall-seconds",
        type=float,
        default=DEFAULT_STALL_SECONDS,
        help=f"Seconds on an intermediate quest stage before flagging a stall (default: {DEFAULT_STALL_SECONDS:g}).",
    )
    ap.add_argument("--max-width", type=int, default=PHONE_MAX_WIDTH, help="Maximum characters per phone-report line.")
    ap.add_argument("--max-lines", type=int, default=PHONE_MAX_LINES, help="Maximum lines in phone-report output.")
    ap.add_argument("--json", action="store_true", help="Emit full structured JSON instead of the phone text card.")
    ap.add_argument("--out", default=None, help="Optional file path to write the rendered report.")
    ap.add_argument(
        "--strict-warn",
        action="store_true",
        help="Exit non-zero on WARN as well as FAIL.",
    )
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    target_log_dir = args.log_dir if args.log_dir is not None else args.path
    if not any((target_log_dir, args.sfse_log_dir, args.crash_dir, args.driver_log)):
        build_parser().error("provide a log directory or at least one of --log-dir, --sfse-log-dir, --crash-dir, --driver-log")

    report = analyze_session(
        target_log_dir,
        sfse_log_dir=args.sfse_log_dir,
        crash_dir=args.crash_dir,
        driver_log=args.driver_log,
        include_rotated=args.include_rotated,
        stall_seconds=args.stall_seconds,
        session_window_hours=None if args.all_ages else 12.0,
    )
    rendered = (
        json.dumps(report, indent=2, sort_keys=False) + "\n"
        if args.json
        else format_phone_report(report, max_width=args.max_width, max_lines=args.max_lines)
    )

    if args.out:
        out_abs = os.path.abspath(args.out)
        parent = os.path.dirname(out_abs)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(out_abs, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)

    sys.stdout.write(rendered)
    if report["verdict"] == "FAIL":
        return 1
    if args.strict_warn and report["verdict"] == "WARN":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
