"""python -m fo4sf.combined: offline tools for the combined core (nothing here touches a game).

  seed OUT_DIR PLUGIN...           read-only draft of a pack from the player's own plugins (seed.py)
  simulate --pack FILE [--pack FILE] --seed N --days D [--out STATE.json] [--resume STATE.json]
  demo --seed N --days D           the built-in synthetic fixtures (placeholder names, not game facts)
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter

from . import seed as _seed
from . import sim
from .fixtures import REGION_1, REGION_2
from .model import WorldState, load_pack

HOURS_PER_DAY = 24


def summary(ws: WorldState) -> dict:
    """What a run changed, small enough to print: event counts by kind, who holds what, settlement sizes."""
    return {
        "hour": ws.hour,
        "events": dict(sorted(Counter(e["kind"] for e in ws.events).items())),
        "holders": {k: p.holder for k, p in sorted(ws.places.items())},
        "settlements": {k: {"population": s.population, "stage": s.stage, "morale": s.morale}
                        for k, s in sorted(ws.settlements.items())},
        "squads": len(ws.squads),
    }


def _print(obj) -> None:
    print(json.dumps(obj, indent=1, sort_keys=True))


def cmd_seed(args) -> int:
    report = _seed.seed(args.out_dir, args.plugins)
    _print({k: report[k] for k in ("locations", "settlement_candidates", "base_candidates", "factions",
                                   "overrides", "deleted_records", "compressed_records", "problems")})
    return 0


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cmd_simulate(args) -> int:
    if args.resume:
        with open(args.resume, encoding="utf-8") as f:
            ws = WorldState.from_json(f.read())   # the save carries its own seed; --seed is ignored
    else:
        ws = WorldState(seed=args.seed)
    for path in args.pack or []:
        load_pack(ws, _load_json(path))          # raises ValueError listing every problem
    if not ws.places:
        print("simulate: no places; give at least one --pack or a --resume state", file=sys.stderr)
        return 2
    sim.run(ws, args.days * HOURS_PER_DAY)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(ws.to_json())
    _print(summary(ws))
    return 0


def cmd_demo(args) -> int:
    ws = WorldState(seed=args.seed)
    load_pack(ws, copy.deepcopy(REGION_1))
    load_pack(ws, copy.deepcopy(REGION_2))
    sim.run(ws, args.days * HOURS_PER_DAY)
    _print(summary(ws))
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m fo4sf.combined", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seed", help="draft a pack from plugins (read-only)")
    s.add_argument("out_dir")
    s.add_argument("plugins", nargs="+", metavar="PLUGIN")
    s.set_defaults(fn=cmd_seed)
    s = sub.add_parser("simulate", help="run the simulation on JSON packs")
    s.add_argument("--pack", action="append", metavar="FILE")
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--days", type=int, required=True)
    s.add_argument("--out", metavar="STATE.json")
    s.add_argument("--resume", metavar="STATE.json")
    s.set_defaults(fn=cmd_simulate)
    s = sub.add_parser("demo", help="run the built-in synthetic fixtures")
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--days", type=int, default=30)
    s.set_defaults(fn=cmd_demo)
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.fn(args)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
