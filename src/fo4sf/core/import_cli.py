"""leader_import.py: existing records into the ledger as events, from the command line (docs/ai/leader-core.md §3).

python scripts/leader_import.py --ledger <leader dir or ledger.jsonl> [--queue <dir>]... [--queues <parent dir>]
                                [--deploy <Data/FO4Port.deploy.json>] [--install <Data/FO4SFExp.install.json>]...
                                [--active-after-load yes|no] [--no-report]
One line per source with the number of events added, in the order queues, deploy manifest, install records (so the
fold ends on the current build and its plugins); idempotent (a second run adds nothing: every event carries the
importer's src key, the same key a runner with a lease folder writes live, §10); never writes to the files it reads;
exit 1 when a source could not be read (the other sources still import), 0 otherwise; ends with the eight-bullet
report of the resulting fold.
"""
import argparse
import os

from .import_queue import import_deploy, import_install, import_queue
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


def main(argv=None):
    ap = argparse.ArgumentParser(prog="leader_import.py",
                                 description="existing queue, install and deploy records into the leader's ledger (section 3)")
    ap.add_argument("--ledger", required=True, help="the leader folder (ledger.jsonl inside) or the ledger file")
    ap.add_argument("--queue", action="append", default=[], metavar="DIR", help="a queue folder (repeatable)")
    ap.add_argument("--queues", default=None, metavar="PARENT", help="every child folder with a queue.json (e.g. the testqueue folder)")
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

    queues = list(a.queue)
    if a.queues:
        if not os.path.isdir(a.queues):
            failed += 1
            print(f"{a.queues}: not a folder")
        else:
            yes, no = queue_folders(a.queues)
            queues += yes
            for p in no:
                print(f"{p}: skipped (no queue.json)")
    if not a.queue and not a.queues and not a.install and not a.deploy:
        ap.error("nothing to import: give --queue, --queues, --deploy or --install")
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
