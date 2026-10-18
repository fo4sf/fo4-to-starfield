"""The runner's own ledger events (docs/ai/leader-core.md §10): what `testqueue.py run` writes, live, when it was
given a lease folder (the ledger lives there), so the owner's report shows the queue, the running attempt and the
results without a re-import.

Every event that has a file counterpart carries the same `src` key import_queue.py uses (`queue.json#pin:<digest of
the pin fields>`, `queue.json#<id>`, `results.jsonl:<line>`) and the same campaign-scoped task id (`<queue folder
name>/<test id>`, import_queue.task_id), so a later import of the same folder adds nothing: the importer is the
recovery path when a live write was lost. Pure Python; nothing here reads or writes a file.
"""
import os

from .import_queue import PIN_KEYS, pin_src, task_id
from .model import Event, now_iso, outcome_from_queue

SOURCE = "IN_GAME"                      # every queue row is an in-game result (leader-core.md §2)


def campaign_of(qdir):
    return os.path.basename(os.path.abspath(qdir).rstrip("\\/"))


def queue_src(qdir, key):
    return f"{os.path.join(os.path.abspath(qdir), 'queue.json')}#{key}"


def row_src(qdir, line):
    return f"{os.path.join(os.path.abspath(qdir), 'results.jsonl')}:{line}"


def build_pinned(qdir, q, by):
    """The queue's pin (build_id, plugin_sha256, staging, commit, game_version), or None when the queue has none."""
    pins = {k: q[k] for k in PIN_KEYS if q.get(k)}
    if not pins:
        return None
    return Event("build_pinned", by, fields=dict(pins, src=pin_src(qdir, q)))


def task_queued(qdir, q, t, by, owner):
    campaign = campaign_of(qdir)
    return Event("task_queued", by, fields={
        "task": task_id(campaign, t["id"]), "kind": t.get("kind"), "cell": t.get("cell"), "ref": t.get("ref"),
        "owner": owner, "campaign": campaign, "build_id": q.get("build_id"), "src": queue_src(qdir, t["id"])})


def task_started(qdir, q, t, attempt, by, owner, started=None):
    """An attempt begins: no src (the queue files never record a start), so a resumed run shows it running or lost."""
    started = started or now_iso()
    campaign = campaign_of(qdir)
    return Event("task_started", by, t=started, fields={
        "task": task_id(campaign, t["id"]), "attempt": attempt, "owner": owner, "campaign": campaign,
        "build_id": q.get("build_id"), "started": started})


def task_finished(qdir, q, rec, line, by, owner):
    """One results.jsonl row (any attempt, PRECONDITION and BREAKER rows included) as the importer would write it."""
    out = outcome_from_queue(rec.get("verdict"), rec.get("class"))
    campaign = campaign_of(qdir)
    return Event("task_finished", by, fields={
        "task": task_id(campaign, rec["id"]), "outcome": out.value, "attempt": rec.get("attempt", 0),
        "detail": f"{rec.get('class', '')} {rec.get('detail', '')}".strip(), "source": SOURCE,
        "campaign": campaign, "build_id": q.get("build_id"),
        "evidence": [rec["dir"]] if rec.get("dir") else [], "completed": out.decided, "owner": owner,
        "pins": {k: q[k] for k in ("build_id", "commit", "plugin_sha256") if q.get(k)}, "src": row_src(qdir, line)})


def recovery_point(q, name, by):
    """The dedicated save the runner created for this build (loaded on every later launch)."""
    return Event("recovery_point", by, fields={"kind": "save", "path": name, "build_id": q.get("build_id")})
