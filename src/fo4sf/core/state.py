"""The append-only ledger and the fold that turns it into the leader's state (docs/ai/leader-core.md §1).

A power cut can leave a partial last line: read() treats it as "not an event" and the next append() drops it and
records a ledger_repaired event, so the file never holds a corrupt line in the middle. A last line that is a whole
event and only lacks its newline (the cut came after the closing brace) is an event for both: read() counts it and
append() terminates it. Current state is fold(events); nothing here rewrites history.
"""
from dataclasses import dataclass, field
import os

from .filelock import locked
from .model import CapabilityState, Event, Outcome, Source, now_iso, parse_iso


def _is_event(line):
    try:
        Event.from_json(line)
        return True
    except ValueError:
        return False


class Ledger:
    def __init__(self, path):
        self.path = path
        self.truncated = None            # the partial last line seen by the last read(), if any

    def read(self):
        """Yield events in order. A partial (unparsable) last line is skipped and kept in self.truncated;
        an unparsable line anywhere else is corruption and raises."""
        self.truncated = None
        if not os.path.exists(self.path):
            return []
        with open(self.path, encoding="utf-8") as f:
            lines = f.read().split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        events = []
        for i, line in enumerate(lines):
            try:
                events.append(Event.from_json(line))
            except ValueError:
                if i == len(lines) - 1:
                    self.truncated = line
                    break
                raise ValueError(f"{self.path}: corrupt line {i + 1}")
        return events

    def sources(self):
        """The `src` keys already in the ledger (imports are idempotent on this)."""
        return {e.get("src") for e in self.read() if e.get("src")}

    def append(self, event):
        """Append one line, under the ledger's lock (filelock.py): the repair of a torn tail and the append are one
        step, so a second writer never sees, or truncates, a line in flight."""
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with locked(self.path + ".lock"):
            return self._append(event)

    def _append(self, event):
        repaired = None
        if os.path.exists(self.path) and os.path.getsize(self.path):
            with open(self.path, "rb+") as f:
                f.seek(-1, os.SEEK_END)
                if f.read(1) != b"\n":                       # the last line has no newline: a write was cut short
                    f.seek(0)
                    data = f.read()
                    keep = data.rfind(b"\n") + 1
                    tail = data[keep:].decode("utf-8", "replace")
                    if _is_event(tail):                      # a whole event, only its newline is missing: terminate it
                        f.write(b"\n")                       # (read() already counts it; dropping it would lose it)
                    else:                                    # a partial line: drop it, remember what was dropped
                        repaired = tail
                        f.seek(keep)
                        f.truncate()
        with open(self.path, "a", encoding="utf-8") as f:
            if repaired is not None:
                f.write(Event("ledger_repaired", event.by, fields={"dropped": repaired}).to_json() + "\n")
            f.write(event.to_json() + "\n")
            f.flush()
            os.fsync(f.fileno())
        return event


@dataclass
class LeaderState:
    leader: dict = field(default_factory=dict)        # commit, branch, host, session
    build: dict = field(default_factory=dict)         # build_id, plugin_sha256, staging, commit, game_version
    plugins: list = field(default_factory=list)       # [{name, sha256, active_after_load}]
    load_order: list = field(default_factory=list)
    controller: dict = field(default_factory=dict)    # owner, purpose, expires, since, released
    tasks: dict = field(default_factory=dict)         # id -> {status, outcome, owner, attempt, detail, campaign}
    cards: dict = field(default_factory=dict)         # id -> the card dict of the first task_queued that carried one
    card_conflicts: set = field(default_factory=set)  # ids queued again with a different card (the first one stands)
    capabilities: dict = field(default_factory=dict)  # (capability, build_id) -> CapabilityState
    declared: set = field(default_factory=set)
    blockers: dict = field(default_factory=dict)      # name -> {evidence, owner, open}
    recovery_points: list = field(default_factory=list)
    campaigns: set = field(default_factory=set)
    changes: list = field(default_factory=list)       # leader_started commits seen, in order
    events: int = 0
    unknown_events: int = 0                           # lines of a type this checkout does not know (kept, not folded)
    bad_events: list = field(default_factory=list)    # (index, type, why) of known types whose fields the fold could not read

    # ---- controller
    def controller_status(self, now=None):
        """'none' | 'held' | 'released' | 'ambiguous' (expired without a release: nothing may send input)."""
        c = self.controller
        if not c:
            return "none"
        if c.get("released"):
            return "released"
        if c.get("expires") and parse_iso(c["expires"]) <= parse_iso(now or now_iso()):
            return "ambiguous"
        return "held"

    # ---- capabilities
    def capability(self, name, build_id=None):
        return self.capabilities.get((name, build_id or self.build.get("build_id")), CapabilityState.UNTESTED)

    def capabilities_by_state(self, build_id=None):
        b = build_id or self.build.get("build_id")
        names = set(self.declared) | {n for n, _ in self.capabilities}
        out = {s: [] for s in CapabilityState}
        for n in sorted(names):
            out[self.capability(n, b)].append(n)
        return out

    # ---- tasks
    def tasks_by_status(self, build_id=None):
        """Task ids per status; with build_id, only the tasks of that build (the report's queue is the pinned build's;
        a task that names no build is listed either way)."""
        out = {}
        for tid, t in self.tasks.items():
            if build_id and t.get("build_id") and t["build_id"] != build_id:
                continue
            out.setdefault(t["status"], []).append(tid)
        return out

    # ---- the eight bullets of the owner's work-period report
    def report(self, now=None):
        caps = self.capabilities_by_state()
        by = self.tasks_by_status(self.build.get("build_id"))   # the queue of the pinned build, not of every campaign
        pins = ", ".join(f"{k}={v}" for k, v in self.build.items() if v) or "no build pinned"
        plugins = ", ".join(p.get("name", "?") + ("" if p.get("active_after_load") else " (not confirmed after load)")
                            for p in self.plugins) or "none recorded"
        ctl = self.controller
        status = self.controller_status(now)
        owner = f"{ctl.get('owner')} ({status}, {ctl.get('purpose', '')})" if ctl else "none"
        blockers = [f"{n}: {', '.join(b.get('evidence') or ['no evidence recorded'])}"
                    for n, b in self.blockers.items() if b.get("open")]
        if self.bad_events:                           # the ledger is append-only: the report says so, the writer fixes it
            shown = "; ".join(f"#{i} {ev}: {why}" for i, ev, why in self.bad_events[:3])
            blockers.append(f"ledger: {len(self.bad_events)} event(s) the fold could not read ({shown})")
        if self.card_conflicts:
            blockers.append("ledger: two cards queued under one id: " + ", ".join(sorted(self.card_conflicts)))
        return [
            "Core changes: " + (", ".join(self.changes[-3:]) if self.changes else "none recorded"),
            "Newly worked in game: " + (", ".join(caps[CapabilityState.VERIFIED]) or "nothing verified on this build"),
            "Failed: " + (", ".join(caps[CapabilityState.FAILED]) or "none")
            + ("; inconclusive: " + ", ".join(caps[CapabilityState.INCONCLUSIVE]) if caps[CapabilityState.INCONCLUSIVE] else ""),
            "Untested: " + (", ".join(caps[CapabilityState.UNTESTED]) or "none declared"),
            f"Pins: {pins}; plugins: {plugins}; leader commit {self.leader.get('commit', '?')}",
            "Controller: " + owner,
            "Blockers: " + ("; ".join(blockers) or "none open"),
            "Next queue: " + (", ".join(by.get("queued", [])) or "empty")
            + (f" (running: {', '.join(by['running'])})" if by.get("running") else ""),
        ]


def _apply_capability(s, f):
    """A capability verdict (a capability_result, or a task_finished of a card that names its capability)."""
    out, src = Outcome(f["outcome"]), Source(f["source"])
    key = (f["capability"], f.get("build_id") or s.build.get("build_id"))
    if out == Outcome.PASS and src == Source.IN_GAME:
        s.capabilities[key] = CapabilityState.VERIFIED
    elif out == Outcome.FAIL:
        s.capabilities[key] = CapabilityState.FAILED
    elif out.decided or out == Outcome.INCONCLUSIVE:
        # an offline / simulated / hypothetical PASS, or any INCONCLUSIVE: pending in-game evidence,
        # and it never overwrites an in-game verdict already on this build
        s.capabilities.setdefault(key, CapabilityState.INCONCLUSIVE)
    # SKIPPED / CIRCUIT_BROKEN: no change (untested stays untested)


def fold(events, now=None):
    """Current state from the events, in order. Enforces the rules of leader-core.md §1. A known event whose fields
    the fold cannot read (a missing or wrongly shaped field from a writer bug or a hand edit) is skipped and listed
    in bad_events, so one bad line never makes the whole ledger unreadable; the report names it as a blocker."""
    s = LeaderState()
    for e in events:
        s.events += 1
        if not e.known:
            s.unknown_events += 1
            continue
        try:
            _fold_one(s, e)
        except (KeyError, TypeError, AttributeError, ValueError) as x:
            s.bad_events.append((s.events, e.ev, f"{type(x).__name__}: {x}"))
    return s


def _fold_one(s, e):
    f = e.fields
    if e.ev == "leader_started":
        s.leader = {k: f.get(k) for k in ("commit", "branch", "host", "session")}
        if f.get("commit"):
            s.changes.append(f["commit"])
    elif e.ev == "build_pinned":
        s.build = {k: f.get(k) for k in ("build_id", "plugin_sha256", "staging", "commit", "game_version") if f.get(k)}
        s.plugins, s.load_order = [], []
    elif e.ev == "plugins_verified":
        # one event per install record (Exp, Bridge) or per check: merged by plugin name, the newer entry wins
        # field by field except that an unknown (null) never erases a known value; `replace: true` is a full
        # snapshot; a new pin (build_pinned) clears everything
        if f.get("replace"):
            s.plugins, s.load_order = [], []
        for p in f.get("plugins") or []:
            name = str(p.get("name") or "") if isinstance(p, dict) else ""
            if not name:
                continue
            for i, q in enumerate(s.plugins):
                if str(q.get("name", "")).casefold() == name.casefold():
                    merged = dict(q)
                    merged.update({k: v for k, v in p.items() if v is not None and k != "name"})
                    s.plugins[i] = merged
                    break
            else:
                s.plugins.append(dict(p))
        if "load_order" in f:
            s.load_order = list(f.get("load_order") or [])
    elif e.ev == "controller_claimed":
        parse_iso(f["expires"])                                     # a lease without a readable expiry is no lease
        s.controller = {"owner": f["owner"], "purpose": f.get("purpose"), "expires": f["expires"],
                        "since": e.t, "released": False}
    elif e.ev == "controller_renewed":
        if s.controller and s.controller.get("owner") == f.get("owner"):
            parse_iso(f["expires"])
            s.controller["expires"] = f["expires"]
    elif e.ev == "controller_released":
        if s.controller:
            s.controller["released"] = True
    elif e.ev in ("task_queued", "task_assigned"):
        t = s.tasks.setdefault(f["task"], {"status": "queued", "outcome": None, "attempt": 0, "detail": ""})
        t["owner"] = f.get("owner", t.get("owner"))
        t["campaign"] = f.get("campaign", t.get("campaign"))
        t["build_id"] = f.get("build_id", t.get("build_id"))
        if isinstance(f.get("card"), dict):                         # the first card queued under an id stands
            if f["task"] not in s.cards:
                s.cards[f["task"]] = dict(f["card"])
            elif s.cards[f["task"]] != f["card"]:
                s.card_conflicts.add(f["task"])
    elif e.ev == "task_started":
        t = s.tasks.setdefault(f["task"], {"status": "queued", "outcome": None, "attempt": 0, "detail": ""})
        t["status"], t["attempt"] = "running", f.get("attempt", t["attempt"] + 1)
        t["build_id"] = f.get("build_id", t.get("build_id"))
    elif e.ev == "task_finished":
        out = Outcome(f["outcome"])
        t = s.tasks.setdefault(f["task"], {"status": "queued", "outcome": None, "attempt": 0, "detail": ""})
        t["outcome"], t["detail"] = out.value, f.get("detail", "")
        t["attempt"] = f.get("attempt", t["attempt"])
        t["campaign"] = f.get("campaign", t.get("campaign"))
        t["build_id"] = f.get("build_id", t.get("build_id"))
        # SKIPPED and CIRCUIT_BROKEN are terminal but never "completed"
        t["status"] = {Outcome.SKIPPED: "skipped", Outcome.CIRCUIT_BROKEN: "circuit_broken",
                       Outcome.INCONCLUSIVE: "inconclusive"}.get(out, "completed")
        if f.get("campaign"):
            s.campaigns.add(f["campaign"])
        if f.get("capability") and f.get("source"):                 # a worker's result names the card's capability
            _apply_capability(s, f)                                 # (§8: the capability_result that follows repeats it)
    elif e.ev == "capability_declared":
        s.declared.add(f["capability"])
    elif e.ev == "capability_result":
        _apply_capability(s, f)
        if f.get("campaign"):
            s.campaigns.add(f["campaign"])
    elif e.ev == "blocker_opened":
        s.blockers[f["blocker"]] = {"evidence": list(f.get("evidence") or []), "owner": f.get("owner"), "open": True}
    elif e.ev == "blocker_closed":
        if f["blocker"] in s.blockers:
            s.blockers[f["blocker"]]["open"] = False
    elif e.ev == "recovery_point":
        s.recovery_points.append(dict({k: f.get(k) for k in ("kind", "path", "sha256", "build_id")}, t=e.t))
    # ledger_repaired: bookkeeping only
