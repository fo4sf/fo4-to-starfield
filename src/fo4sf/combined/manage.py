"""L4 settlement management: the player's actions on a settlement, as pure functions on WorldState.

Design pillar 1 ("settlements that grow"; combined-core design CC-10 "both": the simulation grows a settlement and
the player's own building feeds the same numbers; CC-12 roles and needs: food, water, beds, defence, medicine).
The player reassigns settlers between roles, builds beds, sets a production focus the simulation honours
(sim.PRIORITY_BONUS_PER_WORKER) and sends supplies along the routes as a caravan that the simulation resolves and
hostile neighbours may raid, so the player's own supply lines are breakable like every other (precedent note
settlements-factions-precedents.md, "What this means for us" point 2, a supported hypothesis). `status` summarises
one settlement for a UI or terminal.

Bed caps on recruitment and happiness-driven loss of settlers follow Workshop Framework and Sim Settlements 2
(settlements-factions-precedents.md, "verified" items); the numbers here are placeholders, not those mods' values.

Every action validates its arguments and raises ValueError with a plain message, then records an event through the
simulation's log so news and a resumed save see it. No randomness, no clock; the caravan is the same Squad shape
sim._dispatch_caravans builds, so sim.tick treats both alike. Nothing here runs in a game.
"""
from __future__ import annotations

from . import sim
from .model import GOODS, ROLES, Settlement, WorldState

BEDS_MAX = 60                  # placeholder: most beds one settlement can hold, whoever builds them
THREAT_HOURS = 12              # placeholder: a hostile-held place within this many route hours is a threat
TICKS_PER_DAY = 24 // sim.TICK_HOURS


def _settlement(ws: WorldState, place: str) -> Settlement:
    s = ws.settlements.get(place)
    if s is None:
        raise ValueError(f"{place!r} is not a settlement")
    return s


def _count(n, what: str) -> int:
    if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
        raise ValueError(f"{what} must be a positive integer, got {n!r}")
    return n


def assign_role(ws: WorldState, settlement: str, from_role: str, to_role: str, n: int = 1) -> dict[str, int]:
    """Move `n` settlers from one role to another. Returns the new role counts."""
    s = _settlement(ws, settlement)
    for role in (from_role, to_role):
        if role not in ROLES:
            raise ValueError(f"unknown role {role!r}, want one of {ROLES}")
    if from_role == to_role:
        raise ValueError(f"from_role and to_role are both {from_role!r}")
    n = _count(n, "n")
    if s.roles[from_role] < n:
        raise ValueError(f"{settlement} has {s.roles[from_role]} {from_role}(s), cannot move {n}")
    s.roles[from_role] -= n
    s.roles[to_role] += n
    sim._event(ws, "roles_changed", settlement, from_role=from_role, to_role=to_role, n=n)
    return dict(s.roles)


def add_beds(ws: WorldState, settlement: str, n: int = 1) -> int:
    """The player builds `n` beds (raising the population cap). Returns the new bed count."""
    s = _settlement(ws, settlement)
    n = _count(n, "n")
    if s.beds + n > BEDS_MAX:
        raise ValueError(f"{settlement} has {s.beds} beds; {n} more would pass the cap of {BEDS_MAX}")
    s.beds += n
    sim._event(ws, "beds_added", settlement, n=n, beds=s.beds)
    return s.beds


def set_priority(ws: WorldState, settlement: str, good: str | None) -> str | None:
    """Focus production on `good` (None clears it). Returns the priority now set."""
    s = _settlement(ws, settlement)
    if good is not None and good not in GOODS:
        raise ValueError(f"unknown good {good!r}, want one of {GOODS} or None")
    old, s.priority = s.priority, good
    sim._event(ws, "priority_set", settlement, old=old, new=good)
    return good


def send_supplies(ws: WorldState, from_settlement: str, to_settlement: str, goods: dict[str, int]) -> str:
    """Send `goods` from one settlement to another held by the same faction and reachable by route. The stock
    leaves now; a caravan squad carries it and arrives after the shortest route's hours, where sim.tick delivers
    or loses it like any other caravan. Returns the caravan squad id."""
    src = _settlement(ws, from_settlement)
    _settlement(ws, to_settlement)
    if from_settlement == to_settlement:
        raise ValueError(f"{from_settlement} cannot send supplies to itself")
    holder = ws.places[from_settlement].holder
    if holder is None:
        raise ValueError(f"{from_settlement} is held by no faction, nobody to run the caravan")
    if ws.places[to_settlement].holder != holder:
        raise ValueError(f"{to_settlement} is not held by {holder}, who holds {from_settlement}")
    hours = sim._distances(ws, from_settlement).get(to_settlement)
    if hours is None:
        raise ValueError(f"no route connects {from_settlement} and {to_settlement}")
    if not isinstance(goods, dict) or not goods:
        raise ValueError("goods must be a non-empty dict of good -> amount")
    cargo = {}
    for g in sorted(goods):
        if g not in GOODS:
            raise ValueError(f"unknown good {g!r}, want one of {GOODS}")
        amount = _count(goods[g], f"amount of {g}")
        if src.stock[g] < amount:
            raise ValueError(f"{from_settlement} has {src.stock[g]} {g}, cannot send {amount}")
        cargo[g] = amount
    for g, amount in cargo.items():
        src.stock[g] -= amount
    q = sim.Squad(id=sim._new_id(ws, "c"), faction=holder, size=2, at=from_settlement, goal=to_settlement,
                  kind="caravan", cargo=cargo, eta=ws.hour + hours)
    ws.squads[q.id] = q
    sim._event(ws, "supplies_sent", from_settlement, target=to_settlement, cargo=dict(cargo), squad=q.id,
               eta=q.eta)
    return q.id


def _days_left(stock: int, population: int) -> int | None:
    """Days before `stock` runs out at the simulation's one unit per settler per tick; None when nobody eats."""
    if population <= 0:
        return None
    return stock // (population * TICKS_PER_DAY)


def threats(ws: WorldState, settlement: str, hours: int = THREAT_HOURS) -> list[dict]:
    """Places within `hours` by route whose holder is hostile to the settlement's holder, nearest first.
    An unheld settlement has no faction to be hostile to, so it reports none."""
    _settlement(ws, settlement)
    holder = ws.places[settlement].holder
    out = []
    for pid, dist in sorted(sim._distances(ws, settlement).items(), key=lambda kv: (kv[1], kv[0])):
        other = ws.places[pid].holder
        if pid != settlement and dist <= hours and other is not None and sim._hostile(ws, other, holder):
            out.append({"place": pid, "holder": other, "hours": dist, "kind": ws.places[pid].kind})
    return out


def status(ws: WorldState, settlement: str) -> dict:
    """One settlement as a plain dict for a UI: population, roles, stock, days of food and water left, morale,
    stage, beds, priority, holder, defence, incoming attacks and nearby threats (`threats`)."""
    s = _settlement(ws, settlement)
    incoming = sorted(q.id for q in ws.squads.values() if q.kind == "attack" and q.goal == settlement)
    return {
        "place": settlement,
        "holder": ws.places[settlement].holder,
        "population": s.population,
        "roles": dict(s.roles),
        "stock": dict(s.stock),
        "food_days": _days_left(s.stock["food"], s.population),
        "water_days": _days_left(s.stock["water"], s.population),
        "morale": s.morale,
        "stage": s.stage,
        "beds": s.beds,
        "priority": s.priority,
        "defence": sim._defence(ws, settlement),
        "incoming_attacks": incoming,
        "threats": threats(ws, settlement),
    }


assert set(sim.PRIORITY_ROLE) == set(GOODS)
