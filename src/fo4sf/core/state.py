"""The append-only ledger and the fold that turns it into the leader's state (docs/ai/leader-core.md §1).

A power cut can leave a partial last line: read() treats it as "not an event" and the next append() drops it and
records a ledger_repaired event, so the file never holds a corrupt line in the middle. Current state is fold(events);
nothing here rewrites history.
"""
from dataclasses import dataclass, field
import os

from .model import CapabilityState, Event, Outcome, Source, now_iso, parse_iso


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
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        repaired = None
        if os.path.exists(self.path) and os.path.getsize(self.path):
            with open(self.path, "rb+") as f:
                f.seek(-1, os.SEEK_END)
                if f.read(1) != b"\n":                       # a partial last line: drop it, remember what was dropped
                    f.seek(0)
                    data = f.read()
                    keep = data.rfind(b"\n") + 1
                    repaired = data[keep:].decode("utf-8", "replace")
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
    capabilities: dict = field(default_factory=dict)  # (capability, build_id) -> CapabilityState
    declared: set = field(default_factory=set)
    blockers: dict = field(default_factory=dict)      # name -> {evidence, owner, open}
    recovery_points: list = field(default_factory=list)
    campaigns: set = field(default_factory=set)
    changes: list = field(default_factory=list)       # leader_started commits seen, in order
    events: int = 0

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
    def tasks_by_status(self):
        out = {}
        for tid, t in self.tasks.items():
            out.setdefault(t["status"], []).append(tid)
        return out

    # ---- the eight bullets of the owner's work-period report
    def report(self, now=None):
        caps = self.capabilities_by_state()
        by = self.tasks_by_status()
        pins = ", ".join(f"{k}={v}" for k, v in self.build.items() if v) or "no build pinned"
        plugins = ", ".join(p.get("name", "?") + ("" if p.get("active_after_load") else " (not confirmed after load)")
                            for p in self.plugins) or "none recorded"
        ctl = self.controller
        status = self.controller_status(now)
        owner = f"{ctl.get('owner')} ({status}, {ctl.get('purpose', '')})" if ctl else "none"
        blockers = [f"{n}: {', '.join(b.get('evidence') or ['no evidence recorded'])}"
                    for n, b in self.blockers.items() if b.get("open")]
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


def fold(events, now=None):
    """Current state from the events, in order. Enforces the rules of leader-core.md §1."""
    s = LeaderState()
    for e in events:
        s.events += 1
        f = e.fields
        if e.ev == "leader_started":
            s.leader = {k: f.get(k) for k in ("commit", "branch", "host", "session")}
            if f.get("commit"):
                s.changes.append(f["commit"])
        elif e.ev == "build_pinned":
            s.build = {k: f.get(k) for k in ("build_id", "plugin_sha256", "staging", "commit", "game_version") if f.get(k)}
            s.plugins, s.load_order = [], []
        elif e.ev == "plugins_verified":
            s.plugins = list(f.get("plugins") or [])
            s.load_order = list(f.get("load_order") or [])
        elif e.ev == "controller_claimed":
            s.controller = {"owner": f.get("owner"), "purpose": f.get("purpose"), "expires": f.get("expires"),
                            "since": e.t, "released": False}
        elif e.ev == "controller_renewed":
            if s.controller and s.controller.get("owner") == f.get("owner"):
                s.controller["expires"] = f.get("expires")
        elif e.ev == "controller_released":
            if s.controller:
                s.controller["released"] = True
        elif e.ev in ("task_queued", "task_assigned"):
            t = s.tasks.setdefault(f["task"], {"status": "queued", "outcome": None, "attempt": 0, "detail": ""})
            t["owner"] = f.get("owner", t.get("owner"))
            t["campaign"] = f.get("campaign", t.get("campaign"))
        elif e.ev == "task_started":
            t = s.tasks.setdefault(f["task"], {"status": "queued", "outcome": None, "attempt": 0, "detail": ""})
            t["status"], t["attempt"] = "running", f.get("attempt", t["attempt"] + 1)
        elif e.ev == "task_finished":
            out = Outcome(f["outcome"])
            t = s.tasks.setdefault(f["task"], {"status": "queued", "outcome": None, "attempt": 0, "detail": ""})
            t["outcome"], t["detail"] = out.value, f.get("detail", "")
            t["attempt"] = f.get("attempt", t["attempt"])
            t["campaign"] = f.get("campaign", t.get("campaign"))
            # SKIPPED and CIRCUIT_BROKEN are terminal but never "completed"
            t["status"] = {Outcome.SKIPPED: "skipped", Outcome.CIRCUIT_BROKEN: "circuit_broken",
                           Outcome.INCONCLUSIVE: "inconclusive"}.get(out, "completed")
            if f.get("campaign"):
                s.campaigns.add(f["campaign"])
        elif e.ev == "capability_declared":
            s.declared.add(f["capability"])
        elif e.ev == "capability_result":
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
            if f.get("campaign"):
                s.campaigns.add(f["campaign"])
        elif e.ev == "blocker_opened":
            s.blockers[f["blocker"]] = {"evidence": list(f.get("evidence") or []), "owner": f.get("owner"), "open": True}
        elif e.ev == "blocker_closed":
            if f["blocker"] in s.blockers:
                s.blockers[f["blocker"]]["open"] = False
        elif e.ev == "recovery_point":
            s.recovery_points.append({k: f.get(k) for k in ("kind", "path", "sha256", "build_id")} | {"t": e.t})
        # ledger_repaired: bookkeeping only
    return s
