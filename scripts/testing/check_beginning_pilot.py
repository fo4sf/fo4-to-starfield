#!/usr/bin/env python3
"""Offline bundle verifier and console-free log checker for `docs/testing/fo4-beginning-pilot.md`.

Usage:
    python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir <staged_bundle>
    python scripts/testing/check_beginning_pilot.py check-logs [--newgame-log <fo4sf_newgame.0.log>] [--mission-log <fo4sf_mission.0.log>]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fo4sf.beginning_pilot import (  # noqa: E402
    BEGINNING_STEPS,
    evaluate_beginning_logs,
    verify_bundle_beginning_readiness,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_bun = sub.add_parser("check-bundle", help="Verify offline that a staged bundle carries all B1..B7 plugins, scripts, meshes, and voices.")
    p_bun.add_argument("--bundle-dir", required=True)

    p_log = sub.add_parser("check-logs", help="Evaluate fo4sf_newgame and fo4sf_mission logs into B1..B7 PASS/FAIL/UNTESTED lines.")
    p_log.add_argument("--newgame-log", default="")
    p_log.add_argument("--mission-log", default="")
    p_log.add_argument("--min-hold-pass2", type=int, default=162)
    p_log.add_argument("--require-all-pass", action="store_true", help="Exit non-zero unless all 7 steps reached PASS.")

    args = ap.parse_args(argv)
    if args.cmd == "check-bundle":
        res = verify_bundle_beginning_readiness(args.bundle_dir)
        for spec in BEGINNING_STEPS:
            info = res["steps"][spec.step_id]
            detail = "ok" if not info["issues"] else "; ".join(info["issues"])
            print(f"{info['status']:4s}  {spec.step_id} ({spec.title}): {detail}")
        if not res["ok"]:
            return 1
        print("beginning bundle check: ok (all 7 beginning steps staged)")
        return 0

    if args.cmd == "check-logs":
        res = evaluate_beginning_logs(
            newgame_log_path=args.newgame_log or None,
            mission_log_path=args.mission_log or None,
            min_hold_pass2=args.min_hold_pass2,
        )
        for spec in BEGINNING_STEPS:
            info = res["steps"][spec.step_id]
            print(f"{info['status']:8s}  {spec.step_id}: {info['detail']}")
        if not res["ok"]:
            return 1
        if args.require_all_pass and not res["all_pass"]:
            return 2
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
