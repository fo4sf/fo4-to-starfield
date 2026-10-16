"""The worker result contract (docs/ai/leader-core.md §8): what a worker hands back for a task card, the rules a
result must satisfy before the ledger takes it, and the events a task's life leaves behind.

Rules (ContractError names every violation, and nothing is written when one is found):
- a result names its task and attempt; the attempt is 1..card.max_attempts and the one the ledger shows running;
- outcome and source are the enums of model.py; a decided outcome (PASS / FAIL) carries at least one evidence item
  unless the card's evidence rule is the one word "none"; an undecided outcome can never be reported as completed
  (model.Event refuses);
- a result may claim `verified` only as an IN_GAME PASS: an OFFLINE / SIMULATED / HYPOTHESIS pass is recorded, and
  the fold keeps the capability inconclusive, but a worker that *claims* verification from such a source is refused;
- every time a result or a start carries is an aware ISO timestamp (a naive local time would age by the zone);
- the card in hand is the card the ledger queued: a card never queued, queued twice under one id with different
  content, or differing from the queued one cannot start or finish anything;
- a task is started only when its dependencies passed and no attempt of it is still running (or lost), and the
  attempt is the next one the ledger shows;
- a running task past the card's timeout is expired by the leader into an INCONCLUSIVE result that says so, with
  the same capability_result a worker's INCONCLUSIVE would leave.
"""
import datetime
from dataclasses import asdict, dataclass, field

from .model import Event, Outcome, Source, now_iso, parse_iso
from .state import fold


class ContractError(ValueError):
    """A result or a transition the contract refuses; str(e) lists the violations."""


@dataclass
class WorkerResult:
    task: str
    attempt: int
    outcome: str                                      # Outcome value
    source: str                                       # Source value
    detail: str = ""
    evidence: list = field(default_factory=list)      # paths, hashes, URLs, read lines: what the verdict rests on
    pins: dict = field(default_factory=dict)          # commit, build_id, plugin_sha256, runner, ...
    started: str = None
    finished: str = None
    by: str = ""
    verified: bool = False                            # the worker's claim that the capability is verified

    @property
    def completed(self):
        return Outcome(self.outcome).decided

    def to_dict(self):
        return asdict(self)


def bad_time(label, value):
    """Why `value` is not an aware ISO timestamp (None when it is): the ledger's times are UTC with a zone (§1)."""
    if not isinstance(value, str) or not value.strip():
        return f"{label}: an ISO timestamp with a zone"
    try:
        d = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return f"{label}: not an ISO timestamp: {value!r}"
    if d.tzinfo is None:
        return f"{label}: a naive time ({value!r}); the ledger takes aware UTC times (a local time would age by the zone)"
    return None


def violations(card, result):
    """Every way `result` breaks the contract for `card`, as strings; empty when it is acceptable."""
    out = []
    if result.task != card.id:
        out.append(f"task: result is for {result.task!r}, the card is {card.id!r}")
    if isinstance(result.attempt, bool) or not isinstance(result.attempt, int) or result.attempt < 1:
        out.append("attempt: a positive integer")
    elif result.attempt > card.max_attempts:
        out.append(f"attempt {result.attempt} is beyond the card's max_attempts {card.max_attempts}")
    try:
        outcome = Outcome(result.outcome)
    except ValueError:
        out.append(f"outcome: unknown {result.outcome!r}")
        outcome = None
    try:
        source = Source(result.source)
    except ValueError:
        out.append(f"source: unknown {result.source!r}")
        source = None
    if not isinstance(result.evidence, list) or not all(isinstance(x, str) and x.strip() for x in result.evidence):
        out.append("evidence: a list of non-empty strings")
    elif outcome is not None and outcome.decided and not result.evidence and card.needs_evidence:
        out.append(f"a {outcome.value} needs evidence; the card requires: {', '.join(card.evidence_required)}")
    if result.verified and not (outcome == Outcome.PASS and source == Source.IN_GAME):
        out.append(f"verified claimed from {result.outcome} {result.source}: only an IN_GAME PASS verifies")
    if result.verified and not card.capability:
        out.append("verified claimed for a card that names no capability")
    if not isinstance(result.pins, dict):
        out.append("pins: an object")
    for label, value in (("started", result.started), ("finished", result.finished)):
        if value is not None:
            why = bad_time(label, value)
            if why:
                out.append(why)
    return out


class Worker:
    """Writes a task's life to the ledger: start (task_started), finish (task_finished and, for a card with a
    capability, capability_result), expire (a timeout as INCONCLUSIVE). Every write is checked against the card and
    the ledger's current state first."""

    def __init__(self, ledger, by):
        self.ledger, self.by = ledger, by

    def state(self):
        return fold(self.ledger.read())

    def queue(self, card, now=None):
        """Queue the card (its task_queued line). Idempotent for the same card; refused for an id the ledger already
        holds under a different card. Returns the events written ([] when it was queued already)."""
        s = self.state()
        self._same_card(card, s)
        if card.id in s.cards:
            return []
        if card.id in s.tasks:
            raise ContractError(f"{card.id} is in the ledger without a card (queued by another writer): a new id")
        return [self.ledger.append(e) for e in card.events(self.by, t=now)]

    @staticmethod
    def _same_card(card, state):
        """ContractError unless the card in hand is the one the ledger queued under its id (or none is queued)."""
        if card.id in state.card_conflicts:
            raise ContractError(f"{card.id}: two different cards were queued under this id; the first stands, "
                                f"and nothing runs until the ledger says which (a new id for the other)")
        queued = state.cards.get(card.id)
        if queued is None:
            return
        mine = card.to_dict()
        if queued != mine:
            diff = sorted(k for k in set(queued) | set(mine) if queued.get(k) != mine.get(k))
            raise ContractError(f"{card.id}: the card in hand differs from the one queued in the ledger "
                                f"({', '.join(diff)}); the queued card is the authority (TaskCard.from_event)")

    def start(self, card, attempt=None, now=None):
        now = now or now_iso()
        why = bad_time("now", now)
        if why:
            raise ContractError(why)
        s = self.state()
        if card.id not in s.cards:
            raise ContractError(f"{card.id} is not queued: queue the card first (Worker.queue), so a resumed leader can re-read it")
        self._same_card(card, s)
        t = s.tasks.get(card.id)
        if t and t.get("status") == "running":
            raise ContractError(f"{card.id} attempt {t.get('attempt')} is running or lost: finish or expire it first")
        why = card.not_ready(s)
        if why:
            raise ContractError(why)
        next_attempt = (t.get("attempt", 0) + 1) if t else 1
        if attempt is None:
            attempt = next_attempt
        if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
            raise ContractError("attempt: a positive integer")
        if attempt != next_attempt:
            raise ContractError(f"attempt {attempt} given, the ledger's next attempt of {card.id} is {next_attempt}")
        if attempt > card.max_attempts:
            raise ContractError(f"attempt {attempt} is beyond the card's max_attempts {card.max_attempts}")
        if t and t.get("status") == "completed":
            raise ContractError(f"{card.id} is completed ({t.get('outcome')}): a new card for a new run")
        f = {"task": card.id, "attempt": attempt, "owner": card.owner, "timeout_s": card.timeout_s, "started": now}
        if card.campaign:
            f["campaign"] = card.campaign
        return self.ledger.append(Event("task_started", self.by, t=now, fields=f))

    def finish(self, card, result, now=None):
        now = now or result.finished or now_iso()
        bad = violations(card, result)
        why = bad_time("now", now)
        if why:
            bad.append(why)
        if bad:
            raise ContractError("; ".join(bad))
        s = self.state()
        self._same_card(card, s)
        t = s.tasks.get(card.id)
        if not t or t.get("status") != "running":
            raise ContractError(f"{card.id} is not running ({t.get('status') if t else 'not in the ledger'}): start it first")
        if t.get("attempt") != result.attempt:
            raise ContractError(f"{card.id}: attempt {t.get('attempt')} is running, the result is for attempt {result.attempt}")
        outcome = Outcome(result.outcome)
        f = {"task": card.id, "attempt": result.attempt, "outcome": result.outcome, "source": result.source,
             "detail": result.detail, "evidence": list(result.evidence), "pins": dict(result.pins),
             "completed": result.completed, "owner": card.owner, "worker": result.by, "verified": bool(result.verified)}
        if result.started:
            f["started"] = result.started
        if card.campaign:
            f["campaign"] = card.campaign
        says = card.capability and (outcome.decided or outcome == Outcome.INCONCLUSIVE)
        if says:                                      # the verdict rides on the task line too: a crash between the
            f["capability"] = card.capability         # two appends loses nothing (the fold reads it from either)
            if result.pins.get("build_id"):
                f["build_id"] = result.pins["build_id"]
        events = [self.ledger.append(Event("task_finished", self.by, t=now, fields=f))]
        if says:
            events.append(self.ledger.append(self._capability_event(card, result.outcome, result.source,
                                                                    list(result.evidence), result.attempt,
                                                                    result.pins.get("build_id"), now)))
        return events

    def _capability_event(self, card, outcome, source, evidence, attempt, build_id, now):
        cf = {"capability": card.capability, "outcome": outcome, "source": source, "evidence": evidence,
              "task": card.id, "attempt": attempt}
        if build_id:
            cf["build_id"] = build_id
        if card.campaign:
            cf["campaign"] = card.campaign
        return Event("capability_result", self.by, t=now, fields=cf)

    def running_since(self, task):
        """(attempt, started) of the task_started that is still open, else None."""
        open_ = None
        for e in self.ledger.read():
            if e.get("task") != task:
                continue
            if e.ev == "task_started":
                open_ = (e.get("attempt"), e.get("started") or e.t)
            elif e.ev == "task_finished":
                open_ = None
        return open_

    def expire(self, card, now=None):
        """A running attempt past the card's timeout becomes an INCONCLUSIVE result that says so (and, for a card
        with a capability, the capability_result a worker's INCONCLUSIVE would leave); else None. Returns the
        task_finished event."""
        now = now or now_iso()
        why = bad_time("now", now)
        if why:
            raise ContractError(why)
        self._same_card(card, self.state())
        run = self.running_since(card.id)
        if not run:
            return None
        attempt, started = run
        age = (parse_iso(now) - parse_iso(started)).total_seconds()
        if age < card.timeout_s:
            return None
        f = {"task": card.id, "attempt": attempt, "outcome": Outcome.INCONCLUSIVE.value, "source": Source.OFFLINE.value,
             "detail": f"timeout: attempt {attempt} ran {int(age)} s, the card allows {card.timeout_s} s; no result from the worker",
             "evidence": [], "pins": {}, "completed": False, "owner": card.owner, "started": started, "expired": True}
        if card.campaign:
            f["campaign"] = card.campaign
        if card.capability:
            f["capability"] = card.capability
        ev = self.ledger.append(Event("task_finished", self.by, t=now, fields=f))
        if card.capability:
            self.ledger.append(self._capability_event(card, Outcome.INCONCLUSIVE.value, Source.OFFLINE.value, [],
                                                      attempt, None, now))
        return ev
