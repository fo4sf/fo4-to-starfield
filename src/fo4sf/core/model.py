"""The enums and the event record, once (docs/ai/leader-core.md §1-2).

Outcome: only PASS and FAIL are decided. SKIPPED and CIRCUIT_BROKEN are terminal but undecided, so nothing that
folds the ledger may count them as done or as verifying a capability. Source says how a result was obtained; only an
IN_GAME PASS on the pinned build verifies a capability (owner's brief §6).
"""
from dataclasses import dataclass, field
import datetime
import enum
import json


class Outcome(str, enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    SKIPPED = "SKIPPED"
    CIRCUIT_BROKEN = "CIRCUIT_BROKEN"

    @property
    def decided(self):
        return self in (Outcome.PASS, Outcome.FAIL)


class Source(str, enum.Enum):
    IN_GAME = "IN_GAME"
    OFFLINE = "OFFLINE"
    SIMULATED = "SIMULATED"
    HYPOTHESIS = "HYPOTHESIS"


class CapabilityState(str, enum.Enum):
    VERIFIED = "verified"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
    UNTESTED = "untested"


# the event types of leader-core.md §1, plus the two the fold needs for bookkeeping
EVENT_TYPES = frozenset({
    "leader_started", "build_pinned", "plugins_verified",
    "task_assigned", "task_queued", "task_started", "task_finished",
    "controller_claimed", "controller_renewed", "controller_released",
    "capability_declared", "capability_result",
    "blocker_opened", "blocker_closed", "recovery_point",
    "ledger_repaired",                      # a partial last line (power cut) was dropped on the next append
})


def outcome_from_queue(verdict, cls=""):
    """Map a testqueue.py (verdict, class) pair onto Outcome (leader-core.md §2)."""
    v = (verdict or "").upper()
    c = (cls or "").upper()
    if v == "PASS":
        return Outcome.PASS
    if v == "FAIL":
        return Outcome.FAIL
    if v == "INCONCLUSIVE" and c == "BREAKER":
        return Outcome.CIRCUIT_BROKEN
    if v == "INCONCLUSIVE" and c == "PRECONDITION":
        return Outcome.SKIPPED
    return Outcome.INCONCLUSIVE


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


@dataclass
class Event:
    """One ledger line: {"t": utc iso, "ev": type, "by": agent, ...fields}."""
    ev: str
    by: str
    t: str = field(default_factory=now_iso)
    fields: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.ev not in EVENT_TYPES:
            raise ValueError(f"unknown event type {self.ev!r}")
        if self.ev == "task_finished":
            out = Outcome(self.fields.get("outcome"))   # raises on an unknown outcome
            if self.fields.get("completed") and not out.decided:
                raise ValueError(f"{out.value} is undecided and cannot be reported as completed")
        if self.ev == "capability_result":
            Outcome(self.fields.get("outcome"))
            Source(self.fields.get("source"))

    def to_json(self):
        d = {"t": self.t, "ev": self.ev, "by": self.by}
        d.update(self.fields)
        return json.dumps(d, sort_keys=True)

    @classmethod
    def from_json(cls, line):
        d = json.loads(line)
        return cls(ev=d.pop("ev"), by=d.pop("by", ""), t=d.pop("t", ""), fields=d)

    def get(self, key, default=None):
        return self.fields.get(key, default)
