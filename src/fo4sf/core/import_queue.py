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
Every event carries src = "<file>:<line>" (a row of a file that only grows), "<file>#<key>" (a queue.json, written
once) or "<file>@<sha256 of the file>" (a record rewritten in place: a new deploy or install is a new event); an
import skips src keys already in the ledger.
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
    """results.jsonl rows with their 1-based line numbers; a partial last line is not a row."""
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8-sig") as f:
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
    for line, r in _rows(rp):
        out = outcome_from_queue(r.get("verdict"), r.get("class"))
        put("task_finished", f"{rp}:{line}", t=r.get("t"), task=task_id(campaign, r["id"]), outcome=out.value,
            attempt=r.get("attempt", 0), detail=f"{r.get('class', '')} {r.get('detail', '')}".strip(), source="IN_GAME",
            campaign=campaign, build_id=q.get("build_id"), evidence=[r["dir"]] if r.get("dir") else [])
    return added


def record_plugins(rec):
    """The plugin names an install record carries, in every shape the writers used: `plugins` (exp_install.py since
    270b0ec, 2026-10-12), `plugins_added` (`*Name` lines: every exp_install.py record, and the only key before 270b0ec),
    `plugin` (bridge_install.py, one plugin) and `plugins_replaced[].active`; in that order, each name once."""
    names, seen = [], set()

    def add(n):
        n = str(n or "").lstrip("*").strip()
        if n and n.casefold() not in seen:
            seen.add(n.casefold())
            names.append(n)
    for n in rec.get("plugins") or []:
        add(n)
    for n in rec.get("plugins_added") or []:
        add(n)
    add(rec.get("plugin"))
    for x in rec.get("plugins_replaced") or []:
        if isinstance(x, dict):
            add(x.get("active"))
    return names


def import_install(record_path, ledger, active_after_load=None):
    """An FO4SFExp/FO4SFBridge install record -> one plugins_verified event (active_after_load unknown unless given).
    The fold merges these by plugin name, so the Exp and the Bridge record together name both plugins."""
    rec = _load(record_path)
    if not rec:
        return 0
    names = record_plugins(rec)
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
