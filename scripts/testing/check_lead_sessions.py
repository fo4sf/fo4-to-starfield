#!/usr/bin/env python3
"""Read-only log judge for Lead Sessions 1, 3, and 4 (`K1` / `R11`).

Reads ONLY copied `.log`, `.txt`, and `.out` files inside `--log-dir`, checks
every PASS line and named stop-point condition from the single declarative table
in `src/fo4sf/testing/lead_session_specs.py` (shared with `docs/testing/lead-run-order.md`),
and writes NOTHING to disk unless `--out-dir <folder>` is explicitly passed (in which
case it writes only `<out-dir>/lead_sessions_report.json`).

Usage:
    python scripts/testing/check_lead_sessions.py --log-dir <copied-log-folder>
    python scripts/testing/check_lead_sessions.py --log-dir <copied-log-folder> --session 1
    python scripts/testing/check_lead_sessions.py --log-dir <copied-log-folder> --session 1,3,4 --json
    python scripts/testing/check_lead_sessions.py --log-dir <copied-log-folder> --out-dir <report-dir>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fo4sf.testing.lead_session_specs import (  # noqa: E402
    SUPPORTED_SESSIONS,
    evaluate_session_logs,
    format_report_text,
)


def _parse_sessions(raw: str) -> List[int]:
    val = raw.strip().lower()
    if val == "all":
        return list(SUPPORTED_SESSIONS)
    out: List[int] = []
    for tok in val.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if not tok.isdigit() or int(tok) not in SUPPORTED_SESSIONS:
            raise argparse.ArgumentTypeError(
                f"invalid session {tok!r}; choose 'all' or a comma-separated subset of 1,3,4"
            )
        num = int(tok)
        if num not in out:
            out.append(num)
    if not out:
        raise argparse.ArgumentTypeError("at least one session must be selected")
    return out


def _write_report_inside_out_dir(out_dir: Path, report: dict) -> Path:
    """Write `lead_sessions_report.json` strictly inside the named `out_dir`."""
    resolved_dir = out_dir.resolve()
    resolved_dir.mkdir(parents=True, exist_ok=True)
    target = (resolved_dir / "lead_sessions_report.json").resolve()
    if target.parent != resolved_dir:
        raise ValueError(f"refused write outside named --out-dir: {target}")
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return target


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--log-dir",
        required=True,
        help="Folder of copied logs to inspect (read-only; only .log/.txt/.out files inside this folder are read).",
    )
    parser.add_argument(
        "--session",
        default="all",
        type=_parse_sessions,
        help="Sessions to judge: 'all' (default) or a comma-separated subset of 1,3,4 (e.g. '1' or '3,4').",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the structured JSON report to stdout instead of human-readable text.",
    )
    parser.add_argument(
        "--out-dir",
        default="",
        help="Optional output folder where ONLY lead_sessions_report.json is written. Omit for zero disk writes.",
    )
    parser.add_argument(
        "--allow-map-suppress-fallback",
        action="store_true",
        help="Accept Session 1 Card C MapBlockStarMap=0 hide-only line (step=map_suppress ... sent=hide) when route=create is absent.",
    )
    parser.add_argument(
        "--require-all-pass",
        action="store_true",
        help="Exit non-zero if any required PASS line is MISSING (stop-point FAIL always exits 1).",
    )

    args = parser.parse_args(argv)
    log_dir = Path(args.log_dir)
    if not log_dir.is_dir():
        print(f"error: --log-dir is not an existing directory: {log_dir}", file=sys.stderr)
        return 2

    report = evaluate_session_logs(
        log_dir,
        sessions=args.session,
        allow_map_suppress_fallback=args.allow_map_suppress_fallback,
    )

    if args.out_dir:
        _write_report_inside_out_dir(Path(args.out_dir), report)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_report_text(report))

    if report["any_stop_failure"]:
        return 1
    if args.require_all_pass and report["any_missing"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
