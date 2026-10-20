"""L2 simulation prototype: advances the world state on game time, deterministically.

Paper prototype to tune rules before any game work. Every number here is a
placeholder to argue with, not a balance decision. The RNG is seeded from
(seed, hour), so a run resumed from a saved state replays exactly; every draw
comes from that per-tick RNG and dicts are walked in sorted order.

Lessons from the first prototype that this version encodes: growth needs a role
rule and a beds cap, faction strength needs a sink (daily upkeep), capture must
hurt the settlement, factions prefer to retake what they lost, and caravans can
be raided so supply lines are breakable.
"""
from __future__ import annotations

import random

from .model import GOODS, STRENGTH_CAP, Squad, WorldState  # noqa: F401  (STRENGTH_CAP re-exported for callers)

TICK_HOURS = 6
STAGE_POP = (0, 4, 8, 14, 22)        # population needed for stage 0..4
NEWS_HOURS_PER_ROUTE_HOUR = 1        # news travels at travel speed

# Faction economy (placeholders to tune): income and upkeep both scale with territory, so holding
# more costs more and a faction that over-extends bleeds strength while a failed attack is a total loss.
STRENGTH_INCOME_PER_PLACE = 2        # strength gained per held place per day
UPKEEP_PER_PLACE = 1                 # strength paid per held place per day, floor 0
RETAKE_WEIGHT = 3                    # a lost place counts this many times when picking a target

# Caravan raiding (placeholders): a hostile faction holding a place next to either end of the route
# gets one interception roll per caravan, scaled by its strength.
RAID_CHANCE_PER_STRENGTH = 0.01      # chance = min(cap, strength * this)
RAID_CHANCE_CAP = 0.35
RAID_STRENGTH_GAIN = 1               # loot feeds the raider a little

# Player hooks (placeholders). Reputation follows New Vegas: fame and infamy per faction, with gains
# in the NV tiers (verified in the design notes), the tier chosen by how much the player did.
REP_TIERS = (1, 2, 4, 7, 12)
PLAYER_DEFENCE_BONUS = 10            # defence a player garrison adds to the next attack at that place
PLAYER_DEFENCE_HOURS = 72            # a garrison the player leaves goes home after this long
PLAYER_DEFENCE_FAME = 4
TRADE_GOODS_PER_TIER = 10            # goods handed over per reputation tier step


def _rng(ws: WorldState) -> random.Random:
    return random.Random(ws.seed * 1_000_003 + ws.hour)


def _event(ws: WorldState, kind: str, place: str, **info) -> None:
    ws.events.append({"hour": ws.hour, "kind": kind, "place": place,
                      "region": ws.places[place].region, **info})


def _new_id(ws: WorldState, prefix: str) -> str:
    i = ws.next_id
    ws.next_id += 1
    return f"{prefix}{i}"


def _rep_tier(amount: int) -> int:
    """NV-style gain for `amount` units of help: tiers 1, 2, 4, 7, 12."""
    return REP_TIERS[min(len(REP_TIERS) - 1, max(0, amount) // TRADE_GOODS_PER_TIER)]


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
        elif (s.morale >= 70 and ws.hour % 24 == 0 and not short
              and s.population < s.beds):
            _add_settler(s)
            _event(ws, "settler_arrived", sid)
        stage = max(i for i, p in enumerate(STAGE_POP) if s.population >= p)
        if stage != s.stage:
            _event(ws, "stage_changed", sid, old=s.stage, new=stage)
            s.stage = stage


def _add_settler(s) -> None:
    s.population += 1
    # keep food ahead of mouths, then fill the scarcest other role
    if 3 * s.roles["farmer"] < s.population + 2:
        s.roles["farmer"] += 1
        return
    order = sorted(("guard", "scavenger", "trader", "crafter", "doctor"),
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


def _raider(ws: WorldState, q: Squad, rng: random.Random) -> str | None:
    """Faction that intercepts caravan `q`, or None. One roll per hostile faction holding a place
    next to either end of the route, in sorted order so the draw sequence is fixed."""
    ends = {q.at, q.goal}
    near = set()
    for end in sorted(ends):
        near.update(n for n, _ in ws.neighbours(end))
    near -= ends
    for fid in sorted(ws.factions):
        if not _hostile(ws, fid, q.faction):
            continue
        if not any(ws.places[n].holder == fid for n in sorted(near)):
            continue
        chance = min(RAID_CHANCE_CAP, ws.factions[fid].strength * RAID_CHANCE_PER_STRENGTH)
        if rng.random() < chance:
            return fid
    return None


# --- factions ----------------------------------------------------------------

def _hostile(ws: WorldState, a: str, b: str | None) -> bool:
    return b is not None and a != b and ws.factions[a].relations.get(b, 0) < 0


def _lost_places(ws: WorldState, fid: str) -> set[str]:
    """Places `fid` once held and does not hold now, read back from the event log so a resumed
    save knows them too (no extra model field needed)."""
    return {e["place"] for e in ws.events
            if e["kind"] == "place_taken" and e.get("previous") == fid
            and ws.places[e["place"]].holder != fid}


def _daily_strength(ws: WorldState, fid: str, held: list[str]) -> None:
    f = ws.factions[fid]
    f.strength = min(STRENGTH_CAP, f.strength + STRENGTH_INCOME_PER_PLACE * len(held))
    f.strength = max(0, f.strength - UPKEEP_PER_PLACE * len(held))


def _faction_tick(ws: WorldState, rng: random.Random) -> None:
    for fid in sorted(ws.factions):
        f = ws.factions[fid]
        held = sorted(p for p, pl in ws.places.items() if pl.holder == fid)
        if ws.hour % 24 == 0:
            _daily_strength(ws, fid, held)
        if f.strength < 6 or rng.random() * 100 > f.aggression * 0.25:
            continue
        lost = _lost_places(ws, fid)
        targets = []
        for p in held:
            for n, hours in ws.neighbours(p):
                pl = ws.places[n]
                if pl.story_lock or any(x.home == n for x in ws.factions.values()):
                    continue
                if pl.holder is None or _hostile(ws, fid, pl.holder):
                    targets.extend([(n, hours, p)] * (RETAKE_WEIGHT if n in lost else 1))
        if not targets:
            continue
        target, hours, origin = rng.choice(sorted(targets))
        size = f.strength // 3
        f.strength -= size
        q = Squad(id=_new_id(ws, "s"), faction=fid, size=size, at=origin, goal=target,
                  kind="attack", eta=ws.hour + hours)
        ws.squads[q.id] = q
        _event(ws, "attack_launched", origin, faction=fid, target=target, size=size,
               retake=target in lost)


def _garrisons(ws: WorldState, place: str) -> list[str]:
    return sorted(qid for qid, q in ws.squads.items() if q.kind == "garrison" and q.at == place)


def _defence(ws: WorldState, place: str) -> int:
    d = ws.places[place].defence
    holder = ws.places[place].holder
    if holder is not None:
        d += min(ws.factions[holder].strength, 10) // 2   # garrison share
    s = ws.settlements.get(place)
    if s:
        d += 2 * s.roles["guard"] + s.stock["ammo"] // 10
    d += sum(ws.squads[g].size for g in _garrisons(ws, place))  # player_defended
    return d


def _resolve_arrivals(ws: WorldState, rng: random.Random) -> None:
    for qid in sorted(ws.squads):
        q = ws.squads.get(qid)
        if q is None or q.eta > ws.hour:      # None: a garrison consumed by an attack this tick
            continue
        del ws.squads[qid]
        if q.kind == "garrison":              # the player's helpers go home unused
            continue
        pl = ws.places[q.goal]
        if q.kind == "caravan":
            raider = _raider(ws, q, rng)
            dest = ws.settlements.get(q.goal)
            if raider is not None:
                r = ws.factions[raider]
                r.strength = min(STRENGTH_CAP, r.strength + RAID_STRENGTH_GAIN)
                _event(ws, "caravan_raided", q.goal, faction=q.faction, raider=raider,
                       origin=q.at, cargo=q.cargo)
            elif dest and pl.holder == q.faction:
                for g, n in q.cargo.items():
                    dest.stock[g] += n
                _event(ws, "caravan_arrived", q.goal, faction=q.faction, cargo=q.cargo)
            else:
                _event(ws, "caravan_lost", q.goal, faction=q.faction)
            continue
        if pl.holder == q.faction:
            f = ws.factions[q.faction]
            f.strength = min(STRENGTH_CAP, f.strength + q.size)
            continue
        defence = _defence(ws, q.goal)
        for g in _garrisons(ws, q.goal):      # a player garrison is spent on one attack
            del ws.squads[g]
        if pl.story_lock or rng.random() * (q.size + defence) >= q.size:
            _event(ws, "attack_failed", q.goal, faction=q.faction, defender=pl.holder)
            continue
        old = pl.holder
        retaken = q.goal in _lost_places(ws, q.faction)
        pl.holder = q.faction
        s = ws.settlements.get(q.goal)
        if s and s.population:
            for _ in range((s.population + 1) // 2):
                _remove_settler(s)
            s.morale = min(s.morale, 30)
        f = ws.factions[q.faction]
        f.strength = min(STRENGTH_CAP, f.strength + q.size // 2)
        _event(ws, "place_taken", q.goal, faction=q.faction, previous=old, retaken=retaken)


# --- player-facing hooks -----------------------------------------------------

def player_helped(ws: WorldState, faction: str, amount: int = 10) -> None:
    """New Vegas-style: fame with the faction, and a share of infamy with its enemies."""
    ws.reputation[faction].fame += amount
    for other, rel in sorted(ws.factions[faction].relations.items()):
        if rel < 0 and other in ws.reputation:
            ws.reputation[other].infamy += amount // 2


def player_defended(ws: WorldState, place: str, bonus: int = PLAYER_DEFENCE_BONUS) -> str:
    """The player stands guard: a garrison squad adds `bonus` defence to the next attack on `place`
    (spent by that attack, or gone after PLAYER_DEFENCE_HOURS). Fame with the holder, if any.
    Returns the garrison squad id."""
    q = Squad(id=_new_id(ws, "g"), faction="player", size=bonus, at=place, goal=place,
              kind="garrison", eta=ws.hour + PLAYER_DEFENCE_HOURS)
    ws.squads[q.id] = q
    holder = ws.places[place].holder
    if holder is not None and holder in ws.reputation:
        player_helped(ws, holder, PLAYER_DEFENCE_FAME)
    _event(ws, "player_defended", place, holder=holder, bonus=bonus)
    return q.id


def player_traded(ws: WorldState, settlement: str, goods: dict[str, int]) -> dict[str, int]:
    """Move goods with a settlement: positive amounts go in, negative come out (clamped to stock).
    Giving earns fame with the holder in NV tiers; taking earns nothing. Returns what moved."""
    s = ws.settlements[settlement]
    moved = {}
    for g in sorted(goods):
        if g not in GOODS:
            raise ValueError(f"unknown good {g}")
        n = max(goods[g], -s.stock[g])
        if n:
            s.stock[g] += n
            moved[g] = n
    given = sum(n for n in moved.values() if n > 0)
    holder = ws.places[settlement].holder
    if given and holder is not None and holder in ws.reputation:
        ws.reputation[holder].fame += _rep_tier(given)
    _event(ws, "player_traded", settlement, goods=moved)
    return moved


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
