"""Offline CLI demo for world-state-driven A-Life radiant missions (Round 9 X9, prototype, offline).

Runs the pure-Python A-Life simulator across >= 20 seeds on a preset or config file, generates
contextual radiant requests from the resulting world state, verifies 100% completability, and
prints sample missions and aggregate statistics with cross-OS path scrubbing.

Usage:
  python scripts/alife/demo_radiant_missions.py [--preset fo4sf_commonwealth] [--seeds 25] [--ticks 600] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from fo4sf.alife import radiant_missions, schema  # noqa: E402


def format_report(summary: dict, source_label: str) -> str:
    safe_source = radiant_missions.cross_os_basename(source_label)
    lines = [
        f"X9 Radiant Missions Offline Verification ({safe_source})",
        f"  seeds={summary['num_seeds']} ticks={summary['ticks_per_seed']} "
        f"generated={summary['total_missions_generated']} "
        f"completable={summary['completable_missions']}/{summary['total_missions_generated']} "
        f"all_completable={summary['all_completable']} "
        f"unique_targets={summary['unique_target_nodes']}",
        f"  by_request_type={json.dumps(summary['by_request_type'], sort_keys=True)}",
        f"  by_device_tab={json.dumps(summary['by_secondary_device_tab'], sort_keys=True)}",
        "  sample_requests:",
    ]
    for sample in summary["sample_missions"]:
        lines.append(
            f"    [seed {sample['seed']:02d}] {sample['mission_id']} ({sample['request_type']}) "
            f"giver={sample['giver']} -> target={sample['target']} "
            f"trigger={sample['trigger']} dist={sample['distance_m']:.0f}m ({sample['hops']} hops) "
            f"reward={sample['reward_caps']}c tab={sample['device_tab']} "
            f"w7_fallback={sample['dead_giver_fallback']}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Offline A-Life world-state radiant mission verifier (X9).")
    ap.add_argument("--config", help="Path to an A-Life config JSON file.")
    ap.add_argument("--preset", default="fo4sf_commonwealth", help="Built-in A-Life preset name.")
    ap.add_argument("--seeds", type=int, default=25, help="Number of simulation seeds (>= 20).")
    ap.add_argument("--ticks", type=int, default=600, help="Simulation ticks per seed.")
    ap.add_argument("--max-per-seed", type=int, default=3, help="Max requests generated per seed (1..5).")
    ap.add_argument("--faction", default=None, help="Optional friendly faction id.")
    ap.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = ap.parse_args(argv)

    if args.config:
        cfg = schema.load_alife_config(args.config)
        source_label = args.config
    else:
        cfg = schema.load_preset(args.preset)
        source_label = f"{args.preset}.json"

    summary = radiant_missions.run_multi_seed_verification(
        cfg,
        num_seeds=args.seeds,
        ticks=args.ticks,
        max_per_seed=args.max_per_seed,
        friendly_faction=args.faction,
    )
    if args.json:
        out = dict(summary)
        out["source"] = radiant_missions.cross_os_basename(source_label)
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print(format_report(summary, source_label))
    return 0 if summary["all_completable"] else 1


if __name__ == "__main__":
    sys.exit(main())
