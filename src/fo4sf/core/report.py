"""The owner's eight-bullet work-period report from a ledger (docs/ai/leader-core.md §1: generated from the fold, so
it cannot drift from the state).  python scripts/leader_report.py --ledger <leader dir or ledger.jsonl> [--now ISO] [--json]
Exit 0 with the report; 1 when there is no ledger or it is corrupt (the message says where)."""
import argparse
import json
import os

from .state import Ledger, fold

LEDGER_FILE = "ledger.jsonl"


def ledger_path(p):
    return os.path.join(p, LEDGER_FILE) if os.path.isdir(p) else p


def report(path, now=None):
    """(bullets, state) from the ledger at `path` (a folder or the file). Raises FileNotFoundError / ValueError."""
    p = ledger_path(path)
    if not os.path.exists(p):
        raise FileNotFoundError(f"no ledger at {p}")
    s = fold(Ledger(p).read())
    return s.report(now), s


def main(argv=None):
    ap = argparse.ArgumentParser(prog="leader_report.py", description="the owner's work-period report from the leader's ledger")
    ap.add_argument("--ledger", required=True, help="the leader folder (ledger.jsonl inside) or the ledger file")
    ap.add_argument("--now", default=None, help="the report's 'now' (ISO, UTC); default: the clock")
    ap.add_argument("--json", action="store_true", help="the bullets and the folded state as one JSON object")
    a = ap.parse_args(argv)
    try:
        bullets, s = report(a.ledger, a.now)
    except (OSError, ValueError) as e:
        print(f"report: {e}")
        return 1
    if a.json:
        print(json.dumps({"bullets": bullets, "events": s.events, "controller": s.controller_status(a.now),
                          "tasks": s.tasks_by_status(), "campaigns": sorted(s.campaigns),
                          "build": s.build, "blockers": sorted(n for n, b in s.blockers.items() if b.get("open"))},
                         sort_keys=True))
    else:
        for b in bullets:
            print("- " + b)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
