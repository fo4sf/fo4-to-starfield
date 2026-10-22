"""L3 radiant work: offers read from the world state, whose completion changes that state (paper prototype).

The design puts radiant quests in L3 beside the presence planner and the news (combined-core design, layer table).
The rule this module exists for comes from GAMMA's reviews: radiant tasks that pay only money get called repetitive,
so "faction tasks should change territory or supply state" (combined-core-notes/gamma-anatomy.md: the player review
in 2.6 is verified; anti-lesson 1 in section 5 is labelled H, the lesson is ours). Every offer here is therefore derived from
something the simulation is doing right now, and completing it goes through the simulation's own player hooks or
a documented direct change, so the next tick runs on a different world. There is no money.

Five kinds, all from the giver's point of view (the faction holding the place the player is at):
  defend    an attack squad is on its way to a place the giver holds; completing stands a garrison (sim.player_defended)
  escort    a caravan is leaving this place; completing delivers its cargo now and the caravan is no longer raidable
  retake    the giver lost a place (sim.holder_changes); completing hands it back and logs a place_taken event
  resupply  a settlement of the giver's is short of food or water; completing gives the shortfall (sim.player_traded)
  clear     a hostile faction holds a place next to the giver's holdings; completing empties it (holder None) and
            logs a place_cleared event, which sim, balance and news read as a loss for the old holder

Offers are data only: no quest records, no engine calls, text from our own neutral templates (display names via
news.display_name). Ids are built from the state (squad ids, place ids, event hours), never from a counter or clock,
so two calls on the same state give the same list. An offer expires at `expires_hour`; complete() refuses an expired
offer or one the world has since made moot, so a stale save or a double hand-in fails loudly. Every number is a
placeholder to tune. Nothing here is a Fallout or Starfield rule.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

from . import news, reputation, sim
from .model import WorldState

KINDS = ("defend", "escort", "retake", "resupply", "clear")

OFFER_LIMIT = 5                      # placeholder: offers a giver shows at once

# Expiry (placeholders): defend and escort end when the squad arrives; the rest run this long from the offer.
RETAKE_OFFER_HOURS = 7 * 24          # counted from the hour the place was taken, so an old loss stops being asked for
RESUPPLY_OFFER_HOURS = 48
CLEAR_OFFER_HOURS = 72

# Resupply thresholds (placeholders), in ticks of consumption (sim eats `population` of food and water per tick).
RESUPPLY_SHORT_TICKS = 2             # short when stock covers fewer ticks than this
RESUPPLY_FILL_TICKS = 4              # the offer asks for enough to cover this many ticks

# Reward as a reputation gain tier 1..5 (reputation.GAIN_TIERS, cited there). Paid as the giver's thanks through
# sim.player_helped on top of whatever the hook itself earns (a defence or a trade carries its own small fame).
DEFEND_SIZE_PER_TIER = 3             # attack size per tier step
ESCORT_GOODS_PER_TIER = sim.TRADE_GOODS_PER_TIER
RESUPPLY_GOODS_PER_TIER = sim.TRADE_GOODS_PER_TIER
RETAKE_TIER = 4
CLEAR_TIER = 3

# fail(): infamy with the giver, per kind. A defence or escort you took and let fall costs trust; walking away from
# the rest costs nothing (placeholders).
FAIL_INFAMY = {"defend": 1, "escort": 1, "retake": 0, "resupply": 0, "clear": 0}

# Our own wording; {fields} come from Offer.detail plus giver, target and place names.
TEMPLATES = {
    "defend": "Hold {target} for {giver} against {attacker} fighters expected by {due}.",
    "escort": "See a caravan safely from {place} to {target} for {giver}, carrying {cargo}.",
    "retake": "Take {target} back from {holder} for {giver}.",
    "resupply": "{target} is running out of {good}; bring {amount} more for {giver}.",
    "clear": "Clear {holder} out of {target}, next door to {near}, for {giver}.",
}


@dataclass(frozen=True)
class Offer:
    """One piece of work on offer. `detail` carries the kind's specifics (squad id, good, amount, holder) and is
    what complete() re-checks against the world."""
    id: str                        # stable: from squad ids, place ids and event hours in the save
    kind: str                      # one of KINDS
    giver: str                     # faction id making the offer
    place: str                     # where it was offered (the giver's place the player stands at)
    target: str                    # place the work is about
    reward_tier: int               # reputation gain tier 1..5
    offered_hour: int
    expires_hour: int              # the offer is gone from this hour on
    text: str
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# --- reading the world ---------------------------------------------------------

def _held(ws: WorldState, fid: str) -> list[str]:
    return sorted(p for p, pl in ws.places.items() if pl.holder == fid)


def _homes(ws: WorldState) -> set[str]:
    return {f.home for f in ws.factions.values()}


def _text(kind: str, names, **fields) -> str:
    shown = {k: (news.display_name(v, names) if isinstance(v, str) or v is None else v) for k, v in fields.items()}
    text = TEMPLATES[kind].format(**shown)
    return text[0].upper() + text[1:]


def _defend(ws, giver, place, names) -> list[Offer]:
    out = []
    held = set(_held(ws, giver))
    for qid in sorted(ws.squads):
        q = ws.squads[qid]
        if q.kind != "attack" or q.goal not in held or q.eta <= ws.hour or sim._garrisons(ws, q.goal):
            continue
        tier = reputation.tier_number(q.size, DEFEND_SIZE_PER_TIER)
        text = _text("defend", names, giver=giver, target=q.goal, attacker=q.faction, due=news._stamp(q.eta))
        out.append(Offer(f"defend:{qid}", "defend", giver, place, q.goal, tier, ws.hour, q.eta, text,
                         {"squad": qid, "attacker": q.faction}))
    return out


def _escort(ws, giver, place, names) -> list[Offer]:
    out = []
    for qid in sorted(ws.squads):
        q = ws.squads[qid]
        if q.kind != "caravan" or q.faction != giver or q.at != place or q.eta <= ws.hour:
            continue
        total = sum(q.cargo.values())
        tier = reputation.tier_number(total, ESCORT_GOODS_PER_TIER)
        text = _text("escort", names, giver=giver, place=place, target=q.goal, cargo=news._cargo(q.cargo))
        out.append(Offer(f"escort:{qid}", "escort", giver, place, q.goal, tier, ws.hour, q.eta, text,
                         {"squad": qid, "cargo": dict(sorted(q.cargo.items()))}))
    return out


def _lost_hour(ws: WorldState, giver: str, target: str) -> int | None:
    """Hour of the latest holder change (taken or cleared) that took `target` from `giver`."""
    loss = _last_loss(ws, giver, target)
    return loss[0] if loss else None


def _last_loss(ws: WorldState, giver: str, target: str) -> tuple[int, int] | None:
    """(hour, index in the append-only event log) of the latest holder change that took `target` from `giver`. The
    index tells two losses in one hour apart (Codex review of #431)."""
    found = [(e["hour"], i) for i, e in enumerate(ws.events) if e["kind"] in sim.HOLDER_CHANGE_KINDS
             and e["place"] == target and e.get("previous") == giver]
    return found[-1] if found else None


def _retake(ws, giver, place, names) -> list[Offer]:
    out = []
    homes = _homes(ws)
    for target in sorted(sim._lost_places(ws, giver)):
        pl = ws.places[target]
        if pl.story_lock or target in homes or (pl.holder is not None and not sim._hostile(ws, giver, pl.holder)):
            continue
        taken, seq = _last_loss(ws, giver, target)
        expires = taken + RETAKE_OFFER_HOURS
        if expires <= ws.hour:
            continue
        text = _text("retake", names, giver=giver, target=target, holder=pl.holder)
        out.append(Offer(f"retake:{giver}:{target}:{taken}:{seq}", "retake", giver, place, target, RETAKE_TIER,
                         ws.hour, expires, text, {"holder": pl.holder, "taken_hour": taken}))
    return out


def _shortfall(ws: WorldState, sid: str, good: str) -> int:
    """Units of `good` the settlement is asked for, 0 when it is not short."""
    s = ws.settlements[sid]
    if not s.population or s.stock[good] >= s.population * RESUPPLY_SHORT_TICKS:
        return 0
    return s.population * RESUPPLY_FILL_TICKS - s.stock[good]


def _resupply(ws, giver, place, names) -> list[Offer]:
    out = []
    for sid in _held(ws, giver):
        if sid not in ws.settlements:
            continue
        for good in ("food", "water"):
            amount = _shortfall(ws, sid, good)
            if not amount:
                continue
            tier = reputation.tier_number(amount, RESUPPLY_GOODS_PER_TIER)
            text = _text("resupply", names, giver=giver, target=sid, good=good, amount=amount)
            out.append(Offer(f"resupply:{giver}:{sid}:{good}", "resupply", giver, place, sid, tier, ws.hour,
                             ws.hour + RESUPPLY_OFFER_HOURS, text, {"good": good, "amount": amount}))
    return out


def _clear_targets(ws: WorldState, giver: str) -> dict[str, str]:
    """Hostile-held places next to the giver's holdings -> the nearest giver place, skipping homes, story-locked
    places and places the giver lost (those are retake offers)."""
    homes, lost, out = _homes(ws), sim._lost_places(ws, giver), {}
    for p in _held(ws, giver):
        for n, _ in ws.neighbours(p):
            pl = ws.places[n]
            if n in out or n in homes or n in lost or pl.story_lock or not sim._hostile(ws, giver, pl.holder):
                continue
            out[n] = p
    return out


def _clear(ws, giver, place, names) -> list[Offer]:
    out = []
    for target, near in sorted(_clear_targets(ws, giver).items()):
        holder = ws.places[target].holder
        text = _text("clear", names, giver=giver, target=target, holder=holder, near=near)
        out.append(Offer(f"clear:{giver}:{target}", "clear", giver, place, target, CLEAR_TIER, ws.hour,
                         ws.hour + CLEAR_OFFER_HOURS, text, {"holder": holder, "near": near}))
    return out


_BUILDERS = {"defend": _defend, "escort": _escort, "retake": _retake, "resupply": _resupply, "clear": _clear}


def offers(ws: WorldState, place: str, limit: int = OFFER_LIMIT,
           names: dict[str, str] | None = None) -> list[Offer]:
    """Work the holder of `place` offers the player there, soonest to expire first (ties by kind, then id), at
    most `limit`. Empty when nobody holds the place. Reads ws only."""
    if place not in ws.places:
        raise KeyError(f"unknown place {place!r}")
    giver = ws.places[place].holder
    if giver is None:
        return []
    found: list[Offer] = []
    for kind in KINDS:
        found.extend(_BUILDERS[kind](ws, giver, place, names))
    found = [o for o in found if not _outcome(ws, o)]   # a handed-in or given-up job is not offered again
    found.sort(key=lambda o: (o.expires_hour, o.kind, o.id))
    return found[:limit]


# --- outcomes ----------------------------------------------------------------------

# Kinds whose id names one attack, caravan or loss, so an outcome retires the id for good. Resupply and clear ids
# repeat: a done job settled its need, so a later offer is new work; a given-up one holds until its window ends.
_ONE_TIME = ("defend", "escort", "retake")


def _outcome(ws: WorldState, offer: Offer) -> bool:
    """Whether this job already has a job_done or job_failed event: any earlier outcome for a one-time id, or for a
    repeating id the same offer instance, or a give-up still inside its window (Codex review of #431)."""
    for e in ws.events:
        if e["kind"] not in ("job_done", "job_failed") or e.get("offer") != offer.id:
            continue
        if offer.kind in _ONE_TIME or e.get("offered") == offer.offered_hour or \
                (e["kind"] == "job_failed" and ws.hour < e.get("until", -1)):
            return True
    return False


def valid(ws: WorldState, offer: Offer) -> str | None:
    """Why `offer` can no longer be completed, or None while it still can."""
    if offer.kind not in KINDS:
        return f"unknown offer kind {offer.kind!r}"
    if offer.giver not in ws.factions or offer.target not in ws.places:
        return "giver or target no longer exists"
    if ws.hour >= offer.expires_hour:
        return f"offer expired at hour {offer.expires_hour}"
    if _outcome(ws, offer):                         # one outcome per offer (Codex review of #431)
        return "this offer was already handed in or given up"
    pl, d = ws.places[offer.target], offer.detail
    if offer.kind == "defend":
        q = ws.squads.get(d.get("squad"))
        if q is None or q.kind != "attack" or q.goal != offer.target:
            return "the attack is over"
        if pl.holder != offer.giver:
            return "the giver no longer holds the place"
        if sim._garrisons(ws, offer.target):
            return "a garrison already stands there"
    elif offer.kind == "escort":
        q = ws.squads.get(d.get("squad"))
        if q is None or q.kind != "caravan" or q.goal != offer.target:
            return "the caravan has already arrived or was lost"
        if pl.holder != offer.giver:
            return "the destination is no longer held by the giver"
    elif offer.kind == "retake":
        if pl.holder == offer.giver:
            return "the giver holds the place again"
        if pl.story_lock or offer.target in _homes(ws):
            return "the place cannot change hands"
        if pl.holder is not None and not sim._hostile(ws, offer.giver, pl.holder):
            return "the place is now held by a friend of the giver"
    elif offer.kind == "resupply":
        if offer.target not in ws.settlements or pl.holder != offer.giver:
            return "the settlement is no longer the giver's"
        if not _shortfall(ws, offer.target, d.get("good", "")):
            return "the settlement is no longer short"
    elif offer.kind == "clear":
        if offer.target not in _clear_targets(ws, offer.giver):
            return "the place is no longer a hostile neighbour of the giver"
    return None


def complete(ws: WorldState, offer: Offer) -> dict:
    """Apply the offer's outcome and pay its reward (sim.player_helped with the tier's points). Raises ValueError
    when valid() says the offer is expired or moot. Returns what changed, for a caller's own text."""
    reason = valid(ws, offer)
    if reason is not None:
        raise ValueError(f"cannot complete {offer.id}: {reason}")
    d, changed = offer.detail, {"kind": offer.kind, "target": offer.target}
    if offer.kind == "defend":
        # the garrison outlasts the attack it was asked to meet (Codex review of #431)
        q = ws.squads[d["squad"]]
        changed["garrison"] = sim.player_defended(ws, offer.target,
                                                  hours=max(sim.PLAYER_DEFENCE_HOURS, q.eta - ws.hour))
    elif offer.kind == "escort":
        q = ws.squads.pop(d["squad"])                       # delivered now: nothing left to raid
        dest = ws.settlements.get(q.goal)
        if dest is not None:
            for g, n in sorted(q.cargo.items()):
                dest.stock[g] += n
        sim._event(ws, "caravan_arrived", q.goal, faction=q.faction, cargo=q.cargo, escorted=True)
        changed["cargo"] = dict(q.cargo)
    elif offer.kind == "retake":
        pl = ws.places[offer.target]
        changed["previous"], pl.holder = pl.holder, offer.giver
        sim._event(ws, "place_taken", offer.target, faction=offer.giver, previous=changed["previous"],
                   retaken=True, player=True)
    elif offer.kind == "resupply":
        changed["moved"] = sim.player_traded(ws, offer.target, {d["good"]: d["amount"]})
    elif offer.kind == "clear":
        pl = ws.places[offer.target]
        changed["previous"], pl.holder = pl.holder, None
        sim._event(ws, "place_cleared", offer.target, faction=offer.giver, previous=changed["previous"],
                   player=True)
    fame = reputation.tier_points(offer.reward_tier)
    sim.player_helped(ws, offer.giver, fame)
    sim._event(ws, "job_done", offer.place, faction=offer.giver, job=offer.kind, target=offer.target, fame=fame,
               offer=offer.id, offered=offer.offered_hour,
               until=offer.expires_hour)
    changed["fame"] = fame
    return changed


def fail(ws: WorldState, offer: Offer) -> int:
    """The player gave the job up or let it lapse: FAIL_INFAMY[kind] infamy with the giver, logged. Allowed on an
    expired offer, once per offer: one already handed in or given up is a ValueError. Returns the infamy applied."""
    if _outcome(ws, offer):                         # one outcome per offer, done or failed (Codex review of #431)
        raise ValueError(f"cannot fail {offer.id}: this offer was already handed in or given up")
    infamy = FAIL_INFAMY.get(offer.kind, 0)
    if offer.giver in ws.reputation and infamy:
        reputation.add(ws, offer.giver, infamy=infamy)
    if offer.place in ws.places:
        sim._event(ws, "job_failed", offer.place, faction=offer.giver, job=offer.kind, target=offer.target,
                   infamy=infamy, offer=offer.id, offered=offer.offered_hour,
               until=offer.expires_hour)
    return infamy


assert set(TEMPLATES) == set(FAIL_INFAMY) == set(_BUILDERS) == set(KINDS)
