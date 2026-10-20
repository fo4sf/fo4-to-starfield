"""L1 world-state model for the combined core (paper prototype, not game code).

Game-neutral: nothing here knows Starfield or Fallout record layouts. A content pack
(L5) supplies places, factions and routes as data; the simulation (sim.py) advances
the state; an engine adapter (later) maps it to globals, aliases or an SFSE co-save.

All names in the synthetic scenario are placeholders, not game facts.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
import json

GOODS = ("food", "water", "scrap", "ammo", "medicine")
ROLES = ("farmer", "guard", "trader", "crafter", "scavenger", "doctor")
PLACE_KINDS = ("settlement", "base", "landmark", "gateway")

# Bump when a saved state's shape changes; from_json refuses anything else so a stale or
# foreign save fails loudly instead of loading half-right.
SCHEMA_VERSION = 1

# Upper bound on Faction.strength. Lives here so packs are validated against the same number the
# simulation clamps to; otherwise an oversized faction would run unclamped until its first daily step.
STRENGTH_CAP = 60


@dataclass
class Place:
    id: str
    region: str
    kind: str                     # settlement | base | landmark | gateway
    holder: str | None = None     # faction id holding it, None if empty
    story_lock: str | None = None  # story id that pins the holder (CC-21)
    defence: int = 0


@dataclass
class Settlement:
    place: str
    population: int = 0
    roles: dict[str, int] = field(default_factory=lambda: {r: 0 for r in ROLES})
    stock: dict[str, int] = field(default_factory=lambda: {g: 0 for g in GOODS})
    morale: int = 50              # 0..100
    stage: int = 0                # growth stage, 0..4
    beds: int = 20                # population cap until the player or a stage adds more


@dataclass
class Faction:
    id: str
    strength: int                 # abstract manpower
    home: str                     # place id that never changes hands
    aggression: int = 50          # 0..100, chance weight to attack
    relations: dict[str, int] = field(default_factory=dict)  # other faction -> -100..100


@dataclass
class Squad:
    id: str
    faction: str
    size: int
    at: str                       # place id
    goal: str | None = None       # target place id
    kind: str = "patrol"          # patrol | attack | caravan
    cargo: dict[str, int] = field(default_factory=dict)
    eta: int = 0                  # game hour of arrival at goal


@dataclass
class Route:
    a: str
    b: str
    hours: int                    # travel time in game hours


@dataclass
class Reputation:
    fame: int = 0
    infamy: int = 0


@dataclass
class WorldState:
    seed: int
    hour: int = 0
    places: dict[str, Place] = field(default_factory=dict)
    settlements: dict[str, Settlement] = field(default_factory=dict)
    factions: dict[str, Faction] = field(default_factory=dict)
    squads: dict[str, Squad] = field(default_factory=dict)
    routes: list[Route] = field(default_factory=list)
    reputation: dict[str, Reputation] = field(default_factory=dict)  # faction -> player rep
    events: list[dict] = field(default_factory=list)
    next_id: int = 1

    def neighbours(self, place: str) -> list[tuple[str, int]]:
        out = []
        for r in self.routes:
            if r.a == place:
                out.append((r.b, r.hours))
            elif r.b == place:
                out.append((r.a, r.hours))
        return sorted(out)

    def to_json(self) -> str:
        d = asdict(self)
        d["schema"] = SCHEMA_VERSION
        return json.dumps(d, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "WorldState":
        d = json.loads(text)
        if d.get("schema") != SCHEMA_VERSION:
            raise ValueError(f"unknown world-state schema {d.get('schema')!r}, want {SCHEMA_VERSION}")
        ws = cls(seed=d["seed"], hour=d["hour"], next_id=d["next_id"])
        ws.places = {k: Place(**v) for k, v in d["places"].items()}
        ws.settlements = {k: Settlement(**v) for k, v in d["settlements"].items()}
        ws.factions = {k: Faction(**v) for k, v in d["factions"].items()}
        ws.squads = {k: Squad(**v) for k, v in d["squads"].items()}
        ws.routes = [Route(**r) for r in d["routes"]]
        ws.reputation = {k: Reputation(**v) for k, v in d["reputation"].items()}
        ws.events = d["events"]
        return ws


def load_pack(ws: WorldState, pack: dict) -> None:
    """Add a validated content pack (L5). Thin alias of pack.load_pack, kept for callers."""
    from . import pack as _pack  # local import: pack.py imports this module

    _pack.load_pack(ws, pack)
