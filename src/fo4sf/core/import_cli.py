"""leader_import.py: existing records into the ledger as events, from the command line (docs/ai/leader-core.md §3).

python scripts/leader_import.py --ledger <leader dir or ledger.jsonl> [--queue <dir>]... [--queues <parent dir>]...
                                [--deploy <Data/FO4Port.deploy.json>] [--install <Data/FO4SFExp.install.json>]...
                                [--active-after-load yes|no] [--no-report]
One line per source with the number of events added, in the order queues, deploy manifest, install records (so the
fold ends on the current build and its plugins); idempotent (a second run adds nothing: every event carries the
importer's src key, the same key a runner with a lease folder writes live, §10); never writes to the files it reads;
exit 1 when a source could not be read, does not exist, is not the record its writer produces (a queue.json without a
`tests` list, an install record without `plugins` or `plugin`, a deploy manifest without `artifacts` or one that pins
nothing: import_queue.SHAPES), or is a queue folder whose name the ledger already binds to another folder with a
different build (the other sources still import; nothing of a failed source is written), 0 otherwise; ends with the
eight-bullet report of the resulting fold.
"""
import argparse
import datetime
import json
import os

from .import_queue import import_deploy, import_install, import_queue
from .model import local_to_utc_iso, parse_iso
from .state import Ledger, fold

LEDGER_FILE = "ledger.jsonl"


def ledger_path(p):
    """A leader folder (ledger.jsonl inside, created on the first append) or the ledger file itself."""
    return p if p.lower().endswith(".jsonl") and not os.path.isdir(p) else os.path.join(p, LEDGER_FILE)


def queue_folders(parent):
    """(queue folders, other folders) among the children of `parent`: a queue folder holds a queue.json."""
    yes, no = [], []
    for name in sorted(os.listdir(parent)):
        p = os.path.join(parent, name)
        if os.path.isdir(p):
            (yes if os.path.exists(os.path.join(p, "queue.json")) else no).append(p)
    return yes, no


def queue_created(q):
    """When a queue was planned, as an aware UTC time: queue.json's `created` (testqueue.py plan writes the local wall
    clock with no zone, like every runner time, so it goes through local_to_utc_iso first), else the file's mtime (UTC
    already); a queue whose queue.json cannot be read sorts first (it fails on its own line, before anything that
    matters). Never compare a naive `created` with an mtime: on a Mountain-time PC 10:00 local is 16:00Z, and read as
    10:00Z it sorted before a 13:00Z file, so the older queue imported last and pinned the wrong build."""
    path = os.path.join(q, "queue.json")
    try:
        with open(path, encoding="utf-8-sig") as f:
            created = json.load(f).get("created")
        if created:
            return parse_iso(local_to_utc_iso(str(created)))
        return datetime.datetime.fromtimestamp(os.path.getmtime(path), datetime.timezone.utc)
    except (OSError, ValueError, TypeError, AttributeError):
        return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)


def in_planning_order(queues):
    """The queues found under --queues parents, oldest first, so the newest queue's pin is the fold's current build
    (until a deploy manifest follows); folder names say nothing about age (walk_core64g_1016 sorted after
    door_trip_sdm_round, planned a day later). Explicit --queue folders keep the order they were given in."""
    seen, out = set(), []
    for q in queues:
        key = os.path.normcase(os.path.abspath(q))
        if key not in seen:
            seen.add(key)
            out.append(q)
    return sorted(out, key=lambda q: (queue_created(q), os.path.normcase(os.path.abspath(q))))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="leader_import.py",
                                 description="existing queue, install and deploy records into the leader's ledger (section 3)")
    ap.add_argument("--ledger", required=True, help="the leader folder (ledger.jsonl inside) or the ledger file")
    ap.add_argument("--queue", action="append", default=[], metavar="DIR", help="a queue folder (repeatable)")
    ap.add_argument("--queues", action="append", default=[], metavar="PARENT",
                    help="every child folder with a queue.json (e.g. the testqueue folder; repeatable, one per drive)")
    ap.add_argument("--deploy", default=None, metavar="MANIFEST", help="Data/FO4Port.deploy.json")
    ap.add_argument("--install", action="append", default=[], metavar="RECORD",
                    help="Data/FO4SFExp.install.json or Data/FO4SFBridge.install.json (repeatable)")
    ap.add_argument("--active-after-load", choices=["yes", "no"], default=None,
                    help="what exp_install.py active said for the install records (unknown when not given)")
    ap.add_argument("--no-report", action="store_true", help="do not print the eight bullets afterwards")
    a = ap.parse_args(argv)
    ledger = Ledger(ledger_path(a.ledger))
    failed = total = 0

    def source(label, fn):
        nonlocal failed, total
        try:
            n = fn()
        except (OSError, ValueError, KeyError, TypeError) as e:
            failed += 1
            print(f"{label}: FAILED: {type(e).__name__}: {e}")
            return
        total += n
        print(f"{label}: {n} event(s) added")

    queues, found = list(a.queue), []            # --queue folders in the order given; a parent's children oldest first
    for parent in a.queues:
        if not os.path.isdir(parent):
            failed += 1
            print(f"{parent}: not a folder")
        else:
            yes, no = queue_folders(parent)
            found += yes
            for p in no:
                print(f"{p}: skipped (no queue.json)")
    if not a.queue and not a.queues and not a.install and not a.deploy:
        ap.error("nothing to import: give --queue, --queues, --deploy or --install")
    given = {os.path.normcase(os.path.abspath(q)) for q in queues}
    queues += [q for q in in_planning_order(found) if os.path.normcase(os.path.abspath(q)) not in given]
    for q in queues:
        source(f"queue {q}", lambda q=q: import_queue(q, ledger))
    if a.deploy:
        source(f"deploy {a.deploy}", lambda: import_deploy(a.deploy, ledger))
    active = None if a.active_after_load is None else a.active_after_load == "yes"
    for r in a.install:
        source(f"install {r}", lambda r=r: import_install(r, ledger, active))
    print(f"total: {total} event(s) added to {ledger.path}" + (f"; {failed} source(s) failed" if failed else ""))
    if not a.no_report:
        try:
            bullets = fold(ledger.read()).report()
        except ValueError as e:
            print(f"report: {e}")
            return 1
        for b in bullets:
            print("- " + b)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
