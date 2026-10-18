"""Import existing records into the ledger as events; never write to the files read (docs/ai/leader-core.md §3).

Sources and the field names they are read with (verified against main 16a1d2d):
  <queue>/queue.json      build_id, plugin_sha256, staging, commit, created, tests[].id/kind/cell/ref
  <queue>/results.jsonl   id, kind, cell, ref, attempt, verdict, class, detail, dir, t   (last row per id is final)
  <queue>/state.json      not read: the runner writes a results row for every attempt (PRECONDITION and BREAKER
                          included) and checkpoints state.json together with it, so done/attempts repeat the rows;
                          breaker counters, status and updated are the runner's own bookkeeping
  Data/FO4SFExp.install.json      plugins, plugins_replaced[].active, complete, pack   (exp_install.py)
  Data/FO4SFBridge.install.json   plugin (the one plugin bridge_install.py activates; its record has no plugins), complete
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

A requested source must exist and be the record its writer produces: a JSON object whose top level carries the key
that tells the three records apart (SHAPES: a queue.json has a `tests` list, an install record names its `plugins`,
`plugins_added` or `plugin`, a deploy manifest has an `artifacts` object and pins a build). A missing file (FileNotFoundError) or
anything else (ValueError) fails the source before anything of it is written: the CLI says FAILED and exits 1, the
other sources still import. A mistyped recovery path, or a deploy manifest given as --install, must never read as
"already imported" or as a record with no plugins. What may be absent inside a valid record (no results.jsonl yet,
no pin) is not an error. A queue folder's name is its campaign (task_id), so a second folder of the same name is
refused (CampaignBound) before its rows could fold into the first campaign's tasks, by the importer and by the lease
runner's live writes alike (runner_events.check_binding), unless it is the same queue relocated or archived: the same
build, the same plan (queue_identity: the planned queue's created time, its build pin and its tests, carried as
`queue_id` on every task_queued / task_finished event) and results that agree, line for line, with the rows already
imported from the bound folder. Build equality alone is not enough: two queues planned against one build can test
other refs or routes (Codex review 5558689652).
"""
import hashlib
import json
import os

from .model import Event, local_to_utc_iso, outcome_from_queue

PIN_KEYS = ("build_id", "plugin_sha256", "staging", "commit", "game_version")
DEPLOY_PLUGIN = "FO4Port.esm"          # deploy_starfield.py PLUGIN: the artifact whose sha256 is the build's pin
BY = "import"

SHAPES = {                              # the top-level key its writer always sets, the one that tells the records apart
    "queue.json": (lambda r: isinstance(r.get("tests"), list), "a tests list (testqueue.py plan writes one)"),
    "install record": (lambda r: isinstance(r.get("plugins"), list) or isinstance(r.get("plugins_added"), list)
                       or (isinstance(r.get("plugin"), str) and r["plugin"]),
                       "a plugins or plugins_added list (exp_install.py) or a plugin (bridge_install.py)"),
    "deploy manifest": (lambda r: isinstance(r.get("artifacts"), dict), "an artifacts object (deploy_starfield.py install writes one)"),
}


IDENTITY_PIN = ("build_id", "plugin_sha256")   # the build itself; staging, commit and game_version may be re-pinned in place


class CampaignBound(ValueError):
    """A queue folder whose campaign name the ledger already binds to another folder holding another queue."""


def queue_identity(q):
    """The planned queue's identity, which relocating or archiving the folder does not change: the first 16 hex digits
    of the sha256 of its `created` time, its build (IDENTITY_PIN) and its tests as planned. Two queues planned against
    one build differ in their tests or their created time; a re-pin in place (pin-game-version) keeps the identity."""
    ident = {"created": q.get("created"), "pin": {k: q.get(k) for k in IDENTITY_PIN}, "tests": q.get("tests")}
    return hashlib.sha256(json.dumps(ident, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]


def _record(p, what):
    """The record a requested source file holds. A missing file raises FileNotFoundError; a top level that is not a
    JSON object, or lacks the key its writer always sets (SHAPES), raises ValueError: the CLI reports the source
    FAILED and exits 1, the other sources still import. A deploy manifest given as --install (or the reverse, or a
    queue.json of another shape) stops here instead of reading as a record with nothing in it."""
    if not os.path.exists(p):
        raise FileNotFoundError(f"{what} not found: {p}")
    with open(p, encoding="utf-8-sig") as f:             # utf-8-sig like the runner: a hand-edited file may carry a BOM
        rec = json.load(f)
    if not isinstance(rec, dict):
        raise ValueError(f"{what} is not a JSON object: {p}")
    has, expect = SHAPES[what]
    if not has(rec):
        raise ValueError(f"{what} lacks {expect}: {p} is not one")
    return rec


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


def bound_to(events, campaign):
    """(queue folders, build ids, queue identities, rows) the ledger already binds to `campaign`: the src keys,
    build_id and queue_id of its task_queued and task_finished events, written by the importer and the live runner
    alike (runner_events.py), and {results line: (task, outcome, attempt)} of its task_finished rows. Folders are
    os.path.normcase'd, so a Windows path spelled in another case is the same folder. Events written before queue_id
    existed add None to the identities."""
    folders, builds, ids, rows = set(), set(), set(), {}
    for e in events:
        if e.ev in ("task_queued", "task_finished") and e.get("campaign") == campaign and e.get("src"):
            src = e.get("src")
            file = src.rsplit("#", 1)[0] if "#" in src else src.rsplit(":", 1)[0]   # queue.json#<id> / results.jsonl:<line>
            folders.add(os.path.normcase(os.path.dirname(file)))
            builds.add(e.get("build_id"))
            ids.add(e.get("queue_id"))
            if e.ev == "task_finished" and "#" not in src and src.rsplit(":", 1)[-1].isdigit():
                rows.setdefault(int(src.rsplit(":", 1)[-1]), (e.get("task"), e.get("outcome"), e.get("attempt", 0)))
    return folders, builds, ids, rows


def bind(events, qdir, q, campaign, rows=None):
    """Refuse (CampaignBound) `qdir` when the ledger's `events` already bind `campaign` to another folder and this is
    not the same queue relocated: its build is not among the builds bound there, or it has none (without a build
    nothing tells a relocated copy from a different queue); its queue_identity is not the one bound (another plan
    against the same build: other refs, routes or tests, or a bound ledger written before queue identities); or one
    of its results `rows` ([(line, row)], results.jsonl) disagrees with the row the ledger holds for that line (a
    copy that was run apart). A different queue under the same folder name is a different campaign and its rows must
    not fold into this one's tasks. Called before anything of the queue is written, by import_queue and by the lease
    runner's first live event (runner_events.check_binding). The same folder again, or the same queue relocated or
    archived (same build, same plan, rows that agree), passes."""
    folders, builds, ids, bound_rows = bound_to(events, campaign)
    here, build = os.path.normcase(os.path.abspath(qdir)), q.get("build_id")
    if not folders or here in folders:
        return
    where = f"campaign {campaign!r} is already bound to {', '.join(sorted(folders))}"
    rename = "a different queue under the same folder name is a different campaign, rename the folder before importing or running it"
    if not build or build not in builds:
        raise CampaignBound(f"{where} (build {', '.join(sorted(str(b) for b in builds))}); {qdir} holds build {build}: "
                            f"{rename}")
    qid = queue_identity(q)
    if qid not in ids:
        known = ", ".join(sorted(str(i) for i in ids if i)) or "none recorded"
        raise CampaignBound(f"{where} (build {build}, queue identity {known}); {qdir} holds the same build but another "
                            f"plan (queue identity {qid}: its created time or tests differ): {rename}")
    for line, r in rows or []:
        have = bound_rows.get(line)
        if have is None:
            continue
        mine = (task_id(campaign, r["id"]), outcome_from_queue(r.get("verdict"), r.get("class")).value, r.get("attempt", 0))
        if mine != have:
            raise CampaignBound(f"{where}; {qdir} holds the same plan but its results.jsonl line {line} reads {mine}, the "
                                f"ledger's {have}: a copy that ran apart, not a relocation; {rename}")


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
    qp = os.path.join(qdir, "queue.json")
    q = _record(qp, "queue.json")
    for t in q["tests"]:
        if not isinstance(t, dict) or not t.get("id"):
            raise ValueError(f"queue.json test without an id: {str(t)[:80]} ({qp})")
    campaign = campaign or os.path.basename(qdir.rstrip("\\/"))
    events = ledger.read()
    rp = os.path.join(qdir, "results.jsonl")
    rows, corrupt = _rows(rp)
    bind(events, qdir, q, campaign, rows)                # another folder of this name, another queue: nothing is written
    qid = queue_identity(q)
    seen = {e.get("src") for e in events if e.get("src")}
    added = 0

    def put(ev, src, **fields):
        nonlocal added
        if src in seen:
            return
        t = local_to_utc_iso(fields.pop("t", None) or q.get("created") or "")   # the runner writes local wall-clock time
        ledger.append(Event(ev, BY, t=t, fields=dict(fields, src=src)))
        seen.add(src)
        added += 1

    pins = {k: q[k] for k in PIN_KEYS if q.get(k)}
    if pins:
        put("build_pinned", pin_src(qdir, q), **pins)
    for t in q["tests"]:
        put("task_queued", f"{qp}#{t['id']}", task=task_id(campaign, t["id"]), kind=t.get("kind"), cell=t.get("cell"),
            ref=t.get("ref"), campaign=campaign, build_id=q.get("build_id"), queue_id=qid)
    for line, text in corrupt:                               # a line that is not a row: the ledger says so, once
        put("ledger_repaired", f"{rp}:{line}", dropped=text[:200], reason="results.jsonl line is not a row")
    for line, r in rows:
        out = outcome_from_queue(r.get("verdict"), r.get("class"))
        put("task_finished", f"{rp}:{line}", t=r.get("t"), task=task_id(campaign, r["id"]), outcome=out.value,
            attempt=r.get("attempt", 0), detail=f"{r.get('class', '')} {r.get('detail', '')}".strip(), source="IN_GAME",
            campaign=campaign, build_id=q.get("build_id"), queue_id=qid, evidence=[r["dir"]] if r.get("dir") else [])
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


def record_sha256(rec, name):
    """The sha256 an install record holds for one of its plugins: `files` (rel path or name -> digest, exp_install.py:541,
    bridge_install.py:180) or the bridge's `source_sha256`; None when the record does not name one."""
    want = name.casefold()
    for key in ("files", "source_sha256"):
        d = rec.get(key)
        if not isinstance(d, dict):
            continue
        for rel, h in d.items():
            if str(rel).replace("\\", "/").rsplit("/", 1)[-1].casefold() == want and isinstance(h, str) and h:
                return h
    return None


def import_install(record_path, ledger, active_after_load=None):
    """An FO4SFExp/FO4SFBridge install record -> one plugins_verified event (active_after_load unknown unless given).
    The event names its record (`source`, the file name) and each plugin's sha256 from the record, so the fold merges
    the Exp and the Bridge record into one list, drops a plugin a rewritten record no longer lists, and starts the load
    confirmation over when a plugin's file changed (state.merge_plugins). exp_install.py records list `plugins` (older
    ones only `plugins_added`); a bridge_install.py record names the one `plugin` it activated."""
    rec = _record(record_path, "install record")
    names = record_plugins(rec)
    src = _content_src(record_path, "plugins")
    if src in ledger.sources():
        return 0
    ledger.append(Event("plugins_verified", BY, fields={
        "plugins": [{"name": n, "sha256": record_sha256(rec, n), "active_after_load": active_after_load} for n in names],
        "source": os.path.basename(record_path),
        "complete": rec.get("complete"), "pack": rec.get("pack"), "src": src}))
    return 1


def import_deploy(manifest_path, ledger):
    """The deploy manifest -> one build_pinned event (deploy_pins); an install the deployer did not complete says so.
    A manifest that pins nothing (no artifacts[FO4Port.esm].sha256, no pin key) is a failure, never zero events."""
    rec = _record(manifest_path, "deploy manifest")
    pins = deploy_pins(rec)
    if not pins:
        raise ValueError(f"deploy manifest pins nothing: no artifacts[{DEPLOY_PLUGIN}].sha256 and no pin key in {manifest_path}")
    src = _content_src(manifest_path, "pin")
    if src in ledger.sources():
        return 0
    if "complete" in rec:
        pins["complete"] = bool(rec["complete"])
    ledger.append(Event("build_pinned", BY, fields=dict(pins, src=src)))
    return 1
