"""Import existing records into the ledger as events; never write to the files read (docs/ai/leader-core.md §3).

Sources and the field names they are read with (verified against main 16a1d2d):
  <queue>/queue.json      build_id, plugin_sha256, staging, commit, created, tests[].id/kind/cell/ref
  <queue>/results.jsonl   id, kind, cell, ref, attempt, verdict, class, detail, dir, t   (last row per id is final)
  <queue>/state.json      not read: the runner writes a results row for every attempt (PRECONDITION and BREAKER
                          included) and checkpoints state.json together with it, so done/attempts repeat the rows;
                          breaker counters, status and updated are the runner's own bookkeeping
  Data/FO4SFExp.install.json, Data/FO4SFBridge.install.json   plugins, plugins_replaced[].active, complete, pack
  Data/FO4Port.deploy.json   artifacts[FO4Port.esm].sha256 (deploy_starfield.py artifact_identity) -> plugin_sha256,
                             build_id = its first 8 hex digits (as testqueue.py plan derives it), complete;
                             explicit pin keys (PIN_KEYS) win when a manifest carries them
Every event carries src = "<file>:<line>" (a row of a file that only grows), "<file>#<test id>" or
"<file>#pin:<digest of the pin fields>" (a queue.json: a rewritten pin is a new event) or
"<file>@<key>:<first 16 hex of the content's sha256>@<mtime ns>" (a record rewritten in place: a new deploy or
install is a new event, a re-deploy of the same bytes too); an import skips src keys already in the ledger. A runner
given a lease folder writes the same keys live (runner_events.py, leader-core.md §10), so importing its queue
afterwards adds nothing: the import is the recovery path when a live write was lost. A recovered row lands after the
results written since it was lost, so the fold (state.py) orders a task's results by row, never by ledger position.
"""
import hashlib
import json
import os

from .model import Event, local_to_utc_iso, outcome_from_queue

PIN_KEYS = ("build_id", "plugin_sha256", "staging", "commit", "game_version")
DEPLOY_PLUGIN = "FO4Port.esm"          # deploy_starfield.py PLUGIN: the artifact whose sha256 is the build's pin
BY = "import"


def _load(p, default=None):
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8-sig") as f:             # utf-8-sig like the runner: a hand-edited file may carry a BOM
        return json.load(f)


def _content_src(p, key):
    """src for a record that is rewritten in place: path, the sha256 of its bytes and its mtime, so a re-deploy of a
    build already imported earlier (the same bytes, a new file) is a new event and the pin follows it."""
    st = os.stat(p)
    with open(p, "rb") as f:
        return f"{os.path.abspath(p)}@{key}:{hashlib.sha256(f.read()).hexdigest()[:16]}@{st.st_mtime_ns}"


def pin_src(qdir, q):
    """src of a queue's build_pinned: the queue.json path plus a digest of the pin fields, so a pin rewritten in place
    (pin-game-version, a re-plan into the same folder) is a new event."""
    pins = {k: q[k] for k in PIN_KEYS if q.get(k)}
    digest = hashlib.sha256(json.dumps(pins, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"{os.path.join(os.path.abspath(qdir), 'queue.json')}#pin:{digest}"


def task_id(campaign, test_id):
    """The ledger's task id: the queue folder's name and the test id, because the planners repeat test ids across
    campaigns (0000_terrain_<coc> in every terrain campaign) and two campaigns must never merge in the fold."""
    return f"{campaign}/{test_id}"


def deploy_pins(rec):
    """The pin a deploy manifest carries. deploy_starfield.py install writes no build_id: the pin is the installed
    plugin's sha256 under artifacts[FO4Port.esm], and build_id is its first 8 hex digits, the derivation
    testqueue.py plan uses (build_id = digest[:8]). Explicit pin keys win when a manifest carries them."""
    pins = {k: rec[k] for k in PIN_KEYS if rec.get(k)}
    sha = ((rec.get("artifacts") or {}).get(DEPLOY_PLUGIN) or {}).get("sha256")
    if sha:
        pins.setdefault("plugin_sha256", sha)
        pins.setdefault("build_id", sha[:8])
    return pins


def _rows(p):
    """(rows, corrupt): results.jsonl rows with their 1-based line numbers, and the complete lines that are not rows.
    A partial last line (the row in flight when the power went) is not a row and is not reported; a complete line
    that does not parse (a torn line the runner terminated before its next row, leader-core.md §10, or a hand edit)
    is skipped and reported, never a reason to refuse the queue's other rows."""
    if not os.path.exists(p):
        return [], []
    with open(p, encoding="utf-8-sig") as f:
        lines = f.read().split("\n")
    out, corrupt = [], []
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            if not isinstance(r, dict) or not r.get("id"):
                raise ValueError("not a results row")
            out.append((i, r))
        except ValueError:
            if i < len(lines):                           # only the last line may be partial
                corrupt.append((i, line))
    return out, corrupt


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
        t = local_to_utc_iso(fields.pop("t", None) or q.get("created") or "")   # the runner writes local wall-clock time
        ledger.append(Event(ev, BY, t=t, fields=dict(fields, src=src)))
        seen.add(src)
        added += 1

    qp = os.path.join(qdir, "queue.json")
    pins = {k: q[k] for k in PIN_KEYS if q.get(k)}
    if pins:
        put("build_pinned", pin_src(qdir, q), **pins)
    for t in q.get("tests", []):
        put("task_queued", f"{qp}#{t['id']}", task=task_id(campaign, t["id"]), kind=t.get("kind"), cell=t.get("cell"),
            ref=t.get("ref"), campaign=campaign, build_id=q.get("build_id"))
    rp = os.path.join(qdir, "results.jsonl")
    rows, corrupt = _rows(rp)
    for line, text in corrupt:                               # a line that is not a row: the ledger says so, once
        put("ledger_repaired", f"{rp}:{line}", dropped=text[:200], reason="results.jsonl line is not a row")
    for line, r in rows:
        out = outcome_from_queue(r.get("verdict"), r.get("class"))
        put("task_finished", f"{rp}:{line}", t=r.get("t"), task=task_id(campaign, r["id"]), outcome=out.value,
            attempt=r.get("attempt", 0), detail=f"{r.get('class', '')} {r.get('detail', '')}".strip(), source="IN_GAME",
            campaign=campaign, build_id=q.get("build_id"), evidence=[r["dir"]] if r.get("dir") else [])
    return added


def import_install(record_path, ledger, active_after_load=None):
    """An FO4SFExp/FO4SFBridge install record -> one plugins_verified event (active_after_load unknown unless given)."""
    rec = _load(record_path)
    if not rec:
        return 0
    names = list(rec.get("plugins") or [])
    names += [x["active"].lstrip("*").strip() for x in rec.get("plugins_replaced", []) if x.get("active")]
    src = _content_src(record_path, "plugins")
    if src in ledger.sources():
        return 0
    ledger.append(Event("plugins_verified", BY, fields={
        "plugins": [{"name": n, "active_after_load": active_after_load} for n in names],
        "complete": rec.get("complete"), "pack": rec.get("pack"), "src": src}))
    return 1


def import_deploy(manifest_path, ledger):
    """The deploy manifest -> one build_pinned event (deploy_pins); an install the deployer did not complete says so."""
    rec = _load(manifest_path)
    if not rec:
        return 0
    src = _content_src(manifest_path, "pin")
    if src in ledger.sources():
        return 0
    pins = deploy_pins(rec)
    if not pins:
        return 0
    if "complete" in rec:
        pins["complete"] = bool(rec["complete"])
    ledger.append(Event("build_pinned", BY, fields=dict(pins, src=src)))
    return 1
