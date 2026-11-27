#!/usr/bin/env python3
"""Offline bundle verifier and console-free log checker for `docs/testing/fo4-beginning-pilot.md` (`V1`).

Usage:
    python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir <staged_bundle>
    python scripts/testing/check_beginning_pilot.py check-logs [--log-dir <Script/User dir>] \
        [--newgame-log <fo4sf_newgame.1.log> <fo4sf_newgame.0.log>] \
        [--mission-log <fo4sf_mission.1.log> <fo4sf_mission.0.log>] \
        [--progression-log <FO4SFProgression.1.log> <FO4SFProgression.0.log>]
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
    evaluate_session2_sheet_lines,
    verify_bundle_beginning_readiness,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_bun = sub.add_parser(
        "check-bundle",
        help="Verify offline that a staged bundle carries all B1..B8 plugins, scripts, meshes, and voices.",
    )
    p_bun.add_argument("--bundle-dir", required=True)
    p_bun.add_argument(
        "--require-arsenal",
        action="store_true",
        help="Require the full FO4SFCoreValues.esm arsenal WEAP set (0x000899..0x0008D6) even if S2-S6 mission records are absent.",
    )

    p_log = sub.add_parser(
        "check-logs",
        help="Evaluate fo4sf_newgame, fo4sf_mission, and FO4SFProgression logs (single or rotated multi-session) into B1..B8 verdicts.",
    )
    p_log.add_argument(
        "--log-dir",
        default="",
        help="Directory holding rotated *.3.log .. *.0.log files; read in chronological order when per-channel paths are omitted.",
    )
    p_log.add_argument(
        "--newgame-log",
        nargs="+",
        default=None,
        help="One or more fo4sf_newgame log files in chronological order (e.g. fo4sf_newgame.1.log fo4sf_newgame.0.log).",
    )
    p_log.add_argument(
        "--mission-log",
        nargs="+",
        default=None,
        help="One or more fo4sf_mission log files in chronological order (e.g. fo4sf_mission.1.log fo4sf_mission.0.log).",
    )
    p_log.add_argument(
        "--progression-log",
        nargs="+",
        default=None,
        help="Optional FO4SFProgression log file(s) in chronological order.",
    )
    p_log.add_argument(
        "--min-hold-pass2",
        type=int,
        default=None,
        help="Optional explicit minimum stopped count for pass 2 (defaults to dynamic X of N check).",
    )
    p_log.add_argument("--require-all-pass", action="store_true", help="Exit non-zero unless all 8 steps reached PASS.")

    args = ap.parse_args(argv)
    if args.cmd == "check-bundle":
        res = verify_bundle_beginning_readiness(
            args.bundle_dir,
            require_arsenal=True if args.require_arsenal else None,
        )
        for spec in BEGINNING_STEPS:
            info = res["steps"][spec.step_id]
            detail = "ok" if not info["issues"] else "; ".join(info["issues"])
            print(f"{info['status']:4s}  {spec.step_id} [{spec.label}] ({spec.title}): {detail}")
        aw = res["arsenal_weaps"]
        aw_detail = aw["detail"] if not aw["issues"] else "; ".join(aw["issues"])
        print(f"{aw['status']:4s}  arsenal_weap [FO4SFCoreValues.esm] (Arsenal WEAP Set): {aw_detail}")
        pa = res.get("pod_anim")
        if isinstance(pa, dict):
            pa_detail = pa["detail"] if not pa["issues"] else "; ".join(pa["issues"])
            print(f"{pa['status']:4s}  pod_anim [FO4SFVaultPod.esm] (CryoPod Animation & Placement): {pa_detail}")
        if not res["ok"]:
            return 1
        print(f"beginning bundle check: ok (all {len(BEGINNING_STEPS)} beginning steps staged)")
        return 0

    if args.cmd == "check-logs":
        res = evaluate_beginning_logs(
            newgame_log_path=args.newgame_log,
            mission_log_path=args.mission_log,
            min_hold_pass2=args.min_hold_pass2,
            progression_log_path=args.progression_log,
            log_dir=args.log_dir or None,
        )
        for spec in BEGINNING_STEPS:
            info = res["steps"][spec.step_id]
            print(f"{info['status']:11s}  {spec.step_id}: {info['detail']}")
        if args.log_dir:
            sheet_rows = evaluate_session2_sheet_lines(args.log_dir)
            found_cnt = sum(1 for r in sheet_rows if r["status"] == "found")
            print(f"session2 sheet lines: {found_cnt}/{len(sheet_rows)} found")
        if not res["ok"]:
            return 1
        if args.require_all_pass and not res["all_pass"]:
            return 2
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
