"""L2 simulation prototype: advances the world state on game time, deterministically.

Paper prototype to tune rules before any game work. Every number here is a
placeholder to argue with, not a balance decision. The RNG is seeded from
(seed, hour), so a run resumed from a saved state replays exactly.
"""
from __future__ import annotations

import random

from worldstate import GOODS, Squad, WorldState

TICK_HOURS = 6
STAGE_POP = (0, 4, 8, 14, 22)        # population needed for stage 0..4
NEWS_HOURS_PER_ROUTE_HOUR = 1        # news travels at travel speed


def _rng(ws: WorldState) -> random.Random:
    return random.Random(ws.seed * 1_000_003 + ws.hour)


def _event(ws: WorldState, kind: str, place: str, **info) -> None:
    ws.events.append({"hour": ws.hour, "kind": kind, "place": place,
                      "region": ws.places[place].region, **info})


def _new_id(ws: WorldState, prefix: str) -> str:
    i = ws.next_id
    ws.next_id += 1
    return f"{prefix}{i}"


# --- settlements -----------------------------------------------------------

def _settlement_tick(ws: WorldState) -> None:
    for sid in sorted(ws.settlements):
        s = ws.settlements[sid]
        r = s.roles
        s.stock["food"] += 3 * r["farmer"]
        s.stock["water"] += 3 * r["farmer"]
        s.stock["scrap"] += 2 * r["scavenger"]
        made = min(r["crafter"], s.stock["scrap"] // 2)
        s.stock["scrap"] -= 2 * made
        s.stock["ammo"] += 3 * made
        s.stock["medicine"] += r["doctor"]
        need = s.population
        short = 0
        for g in ("food", "water"):
            if s.stock[g] >= need:
                s.stock[g] -= need
            else:
                short += need - s.stock[g]
                s.stock[g] = 0
        if short:
            s.morale = max(0, s.morale - 5)
        elif s.stock["food"] > 2 * need and s.stock["water"] > 2 * need:
            s.morale = min(100, s.morale + 2)
        if s.morale <= 10 and s.population > 0:
            _remove_settler(s)
            _event(ws, "settler_left", sid)
        elif s.morale >= 70 and ws.hour % 24 == 0 and not short:
            _add_settler(s)
            _event(ws, "settler_arrived", sid)
        stage = max(i for i, p in enumerate(STAGE_POP) if s.population >= p)
        if stage != s.stage:
            _event(ws, "stage_changed", sid, old=s.stage, new=stage)
            s.stage = stage


def _add_settler(s) -> None:
    s.population += 1
    # fill the scarcest of food producers, guards and traders first
    order = sorted(("farmer", "guard", "scavenger", "trader", "crafter", "doctor"),
                   key=lambda r: (s.roles[r], r))
    s.roles[order[0]] += 1


def _remove_settler(s) -> None:
    s.population -= 1
    biggest = max(sorted(s.roles), key=lambda r: s.roles[r])
    if s.roles[biggest]:
        s.roles[biggest] -= 1


# --- caravans and supply ---------------------------------------------------

def _dispatch_caravans(ws: WorldState) -> None:
    for sid in sorted(ws.settlements):
        s = ws.settlements[sid]
        holder = ws.places[sid].holder
        if not s.roles["trader"] or holder is None:
            continue
        if any(q.kind == "caravan" and q.at == sid for q in ws.squads.values()):
            continue
        friends = [(n, h) for n, h in ws.neighbours(sid)
                   if n in ws.settlements and ws.places[n].holder == holder]
        if not friends:
            continue
        target, hours = min(friends, key=lambda nh: (ws.settlements[nh[0]].stock["food"], nh[0]))
        surplus = s.stock["food"] - 3 * s.population
        if surplus < 6:
            continue
        cargo = {"food": surplus // 2}
        s.stock["food"] -= cargo["food"]
        q = Squad(id=_new_id(ws, "c"), faction=holder, size=2, at=sid, goal=target,
                  kind="caravan", cargo=cargo, eta=ws.hour + hours)
        ws.squads[q.id] = q


# --- factions ----------------------------------------------------------------

def _hostile(ws: WorldState, a: str, b: str | None) -> bool:
    return b is not None and a != b and ws.factions[a].relations.get(b, 0) < 0


def _faction_tick(ws: WorldState, rng: random.Random) -> None:
    for fid in sorted(ws.factions):
        f = ws.factions[fid]
        held = sorted(p for p, pl in ws.places.items() if pl.holder == fid)
        if ws.hour % 24 == 0:
            f.strength += len(held)
        if f.strength < 6 or rng.random() * 100 > f.aggression * 0.25:
            continue
        targets = []
        for p in held:
            for n, hours in ws.neighbours(p):
                pl = ws.places[n]
                if pl.story_lock or any(x.home == n for x in ws.factions.values()):
                    continue
                if pl.holder is None or _hostile(ws, fid, pl.holder):
                    targets.append((n, hours, p))
        if not targets:
            continue
        target, hours, origin = rng.choice(sorted(targets))
        size = f.strength // 3
        f.strength -= size
        q = Squad(id=_new_id(ws, "s"), faction=fid, size=size, at=origin, goal=target,
                  kind="attack", eta=ws.hour + hours)
        ws.squads[q.id] = q
        _event(ws, "attack_launched", origin, faction=fid, target=target, size=size)


def _defence(ws: WorldState, place: str) -> int:
    d = ws.places[place].defence
    s = ws.settlements.get(place)
    if s:
        d += 2 * s.roles["guard"] + s.stock["ammo"] // 10
    return d


def _resolve_arrivals(ws: WorldState, rng: random.Random) -> None:
    for qid in sorted(ws.squads):
        q = ws.squads[qid]
        if q.eta > ws.hour:
            continue
        del ws.squads[qid]
        pl = ws.places[q.goal]
        if q.kind == "caravan":
            dest = ws.settlements.get(q.goal)
            if dest and pl.holder == q.faction:
                for g, n in q.cargo.items():
                    dest.stock[g] += n
                _event(ws, "caravan_arrived", q.goal, faction=q.faction, cargo=q.cargo)
            else:
                _event(ws, "caravan_lost", q.goal, faction=q.faction)
            continue
        if pl.holder == q.faction:
            ws.factions[q.faction].strength += q.size
            continue
        defence = _defence(ws, q.goal)
        if pl.story_lock or rng.random() * (q.size + defence) >= q.size:
            _event(ws, "attack_failed", q.goal, faction=q.faction, defender=pl.holder)
            continue
        old = pl.holder
        pl.holder = q.faction
        ws.factions[q.faction].strength += q.size // 2
        _event(ws, "place_taken", q.goal, faction=q.faction, previous=old)


# --- player-facing hooks -----------------------------------------------------

def player_helped(ws: WorldState, faction: str, amount: int = 10) -> None:
    """New Vegas-style: fame with the faction, and a share of infamy with its enemies."""
    ws.reputation[faction].fame += amount
    for other, rel in sorted(ws.factions[faction].relations.items()):
        if rel < 0 and other in ws.reputation:
            ws.reputation[other].infamy += amount // 2


def news_for(ws: WorldState, place: str, since: int = 0) -> list[dict]:
    """Events that have had time to travel to `place` (spread along routes)."""
    dist = _distances(ws, place)
    out = []
    for e in ws.events:
        if e["hour"] < since or e["place"] not in dist:
            continue
        if e["hour"] + dist[e["place"]] * NEWS_HOURS_PER_ROUTE_HOUR <= ws.hour:
            out.append(e)
    return out


def _distances(ws: WorldState, start: str) -> dict[str, int]:
    best = {start: 0}
    todo = [start]
    while todo:
        todo.sort(key=lambda p: (best[p], p))
        p = todo.pop(0)
        for n, h in ws.neighbours(p):
            if n not in best or best[p] + h < best[n]:
                best[n] = best[p] + h
                todo.append(n)
    return best


def tick(ws: WorldState) -> None:
    ws.hour += TICK_HOURS
    rng = _rng(ws)
    _resolve_arrivals(ws, rng)
    _settlement_tick(ws)
    _dispatch_caravans(ws)
    _faction_tick(ws, rng)


def run(ws: WorldState, hours: int) -> None:
    end = ws.hour + hours
    while ws.hour < end:
        tick(ws)


assert set(GOODS) >= {"food", "water", "scrap", "ammo", "medicine"}
