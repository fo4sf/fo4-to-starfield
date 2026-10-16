"""Task cards (docs/ai/leader-core.md §4 and §8): a bounded, resumable task as data, with exactly the fields of the
cards the leader hands out, so a card can be validated, stored, queued into the ledger and checked for readiness
by code rather than by reading prose.

A card is refused (CardError, naming the field) when it lacks an objective, an owner, an acceptance line or an
evidence rule, when a number is not positive, or when it carries a field the contract does not know. Nothing here
runs a task: that is the worker's side (worker.py).
"""
import json
from dataclasses import asdict, dataclass, field, fields

from .model import Event

DEFAULT_TIMEOUT_S = 3600


class CardError(ValueError):
    """A card that breaks the contract; str(e) names the field."""


@dataclass
class TaskCard:
    id: str
    objective: str
    owner: str
    acceptance: list                                  # what must be true for a decided result; never empty
    evidence_required: list                           # what a decided result must carry (test output, a read, ...)
    inputs: list = field(default_factory=list)
    dependencies: list = field(default_factory=list)  # task ids whose PASS must be in the ledger first
    timeout_s: int = DEFAULT_TIMEOUT_S
    max_attempts: int = 2
    recovery: str = "the branch is the checkpoint; a second session continues from the last commit"
    not_in_scope: list = field(default_factory=list)
    capability: str = None                            # the capability a decided IN_GAME result verifies or fails
    campaign: str = None

    def __post_init__(self):
        for name in ("id", "objective", "owner"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise CardError(f"{name}: a card needs a non-empty {name}")
        for name in ("acceptance", "evidence_required", "inputs", "dependencies", "not_in_scope"):
            v = getattr(self, name)
            if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
                raise CardError(f"{name}: a list of non-empty strings")
        if not self.acceptance:
            raise CardError("acceptance: a card without an acceptance line cannot be decided")
        if not self.evidence_required:
            raise CardError("evidence_required: say what a decided result must carry ('none' is a choice, not an omission)")
        for name in ("timeout_s", "max_attempts"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
                raise CardError(f"{name}: a positive integer")
        if self.id in self.dependencies:
            raise CardError("dependencies: a card cannot depend on itself")
        for name in ("capability", "campaign", "recovery"):
            v = getattr(self, name)
            if v is not None and (not isinstance(v, str) or not v.strip()):
                raise CardError(f"{name}: a non-empty string or absent")

    def to_dict(self):
        return asdict(self)

    def to_json(self):
        return json.dumps(self.to_dict(), sort_keys=True, indent=1)

    @classmethod
    def from_dict(cls, d):
        if not isinstance(d, dict):
            raise CardError("a card is a JSON object")
        known = {f.name for f in fields(cls)}
        unknown = sorted(set(d) - known)
        if unknown:
            raise CardError(f"unknown card field(s): {', '.join(unknown)}")
        missing = [n for n in ("id", "objective", "owner", "acceptance", "evidence_required") if n not in d]
        if missing:
            raise CardError(f"missing: {', '.join(missing)}")
        return cls(**d)

    @classmethod
    def from_json(cls, text):
        try:
            d = json.loads(text)
        except ValueError as e:
            raise CardError(f"not JSON: {e}") from None
        return cls.from_dict(d)

    def events(self, by, t=None):
        """The ledger lines that queue this card: one task_queued carrying the card (a resumed leader re-reads it)."""
        f = {"task": self.id, "owner": self.owner, "card": self.to_dict()}
        if self.campaign:
            f["campaign"] = self.campaign
        if self.capability:
            f["capability"] = self.capability
        kw = {"t": t} if t else {}
        return [Event("task_queued", by, fields=f, **kw)]

    def not_ready(self, state):
        """Why this card cannot start on `state` (a LeaderState), else None: a dependency without a PASS in the ledger."""
        for dep in self.dependencies:
            t = state.tasks.get(dep)
            if not t:
                return f"dependency {dep} is not in the ledger"
            if t.get("status") != "completed" or t.get("outcome") != "PASS":
                return f"dependency {dep} is {t.get('status')} ({t.get('outcome') or 'no outcome'}), not a PASS"
        return None
