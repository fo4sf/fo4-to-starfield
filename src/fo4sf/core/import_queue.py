"""Import existing records into the ledger as events; never write to the files read (docs/ai/leader-core.md §3).

Sources and the field names they are read with (verified against main d628b56):
  <queue>/queue.json      build_id, plugin_sha256, staging, commit, created, tests[].id/kind/cell/ref
  <queue>/results.jsonl   id, kind, cell, ref, attempt, verdict, class, detail, dir, t   (last row per id is final)
  <queue>/state.json      done, breaker, status, updated
  Data/FO4SFExp.install.json, Data/FO4SFBridge.install.json   plugins, plugins_replaced[].active, complete, pack
  Data/FO4Port.deploy.json                                      whatever pin keys it carries (see PIN_KEYS)
Every event carries src = "<file>:<line>" or "<file>#<key>"; an import skips src keys already in the ledger.
"""
import json
import os

from .model import Event, outcome_from_queue

PIN_KEYS = ("build_id", "plugin_sha256", "staging", "commit", "game_version")
BY = "import"


def _load(p, default=None):
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _rows(p):
    """results.jsonl rows with their 1-based line numbers; a partial last line is not a row."""
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        lines = f.read().split("\n")
    out = []
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            out.append((i, json.loads(line)))
        except ValueError:
            if i < len(lines):                           # only the last line may be partial
                raise ValueError(f"{p}: corrupt line {i}")
    return out


def import_queue(qdir, ledger, campaign=None):
    """One queue folder -> build_pinned, task_queued per test, task_finished per result row. Returns events added."""
    qdir = os.path.abspath(qdir)
    q = _load(os.path.join(qdir, "queue.json"))
    if not q:
        return 0
    campaign = campaign or os.path.basename(qdir.rstrip("\\/"))
    seen = ledger.sources()
    added = 0

    def put(ev, src, **fields):
        nonlocal added
        if src in seen:
            return
        ledger.append(Event(ev, BY, t=fields.pop("t", None) or q.get("created") or "", fields=dict(fields, src=src)))
        seen.add(src)
        added += 1

    qp = os.path.join(qdir, "queue.json")
    put("build_pinned", f"{qp}#pin", **{k: q[k] for k in PIN_KEYS if q.get(k)})
    for t in q.get("tests", []):
        put("task_queued", f"{qp}#{t['id']}", task=t["id"], kind=t.get("kind"), cell=t.get("cell"), ref=t.get("ref"),
            campaign=campaign, build_id=q.get("build_id"))
    rp = os.path.join(qdir, "results.jsonl")
    for line, r in _rows(rp):
        out = outcome_from_queue(r.get("verdict"), r.get("class"))
        put("task_finished", f"{rp}:{line}", t=r.get("t"), task=r["id"], outcome=out.value, attempt=r.get("attempt", 0),
            detail=f"{r.get('class', '')} {r.get('detail', '')}".strip(), source="IN_GAME", campaign=campaign,
            build_id=q.get("build_id"), evidence=[r["dir"]] if r.get("dir") else [])
    return added


def import_install(record_path, ledger, active_after_load=None):
    """An FO4SFExp/FO4SFBridge install record -> one plugins_verified event (active_after_load unknown unless given)."""
    rec = _load(record_path)
    if not rec:
        return 0
    names = list(rec.get("plugins") or [])
    names += [x["active"].lstrip("*").strip() for x in rec.get("plugins_replaced", []) if x.get("active")]
    src = f"{os.path.abspath(record_path)}#plugins"
    if src in ledger.sources():
        return 0
    ledger.append(Event("plugins_verified", BY, fields={
        "plugins": [{"name": n, "active_after_load": active_after_load} for n in names],
        "complete": rec.get("complete"), "pack": rec.get("pack"), "src": src}))
    return 1


def import_deploy(manifest_path, ledger):
    """The deploy manifest -> one build_pinned event with whichever pin keys it carries."""
    rec = _load(manifest_path)
    if not rec:
        return 0
    src = f"{os.path.abspath(manifest_path)}#pin"
    if src in ledger.sources():
        return 0
    pins = {k: rec[k] for k in PIN_KEYS if rec.get(k)}
    if not pins:
        return 0
    ledger.append(Event("build_pinned", BY, fields=dict(pins, src=src)))
    return 1
