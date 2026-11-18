"""L4 reputation rules for the combined core: New Vegas-style fame and infamy per faction (paper prototype).

Source for the shape: research/framework/combined-core-notes/settlements-factions-precedents.md, section 2
("NV reputation, verified"): two independent scales per faction, Fame and Infamy, each with 4 levels; the 4x4 grid
yields named states (Accepted/Liked/Idolized, Shunned/Hated/Vilified, mixed states such as "Smiling Troublemaker" and
"Dark Hero"); each change uses an editor tier 1-5 worth 1/2/4/7/12 points; thresholds are per faction. The same
section says a disguise sets standing to Neutral and that Vilified triggers hit squads.

What the note does NOT give, so every value below is a placeholder labelled unverified: the per-faction level
thresholds, which grid cell each mixed name belongs to, and any vendor or hostility effect per state. Effects here
are abstract tiers for the simulation and for probe P7 (engine-feasibility.md, "vendor refuses service by
reputation tier") to confirm or replace; nothing claims to be a Fallout or Starfield rule.

Regional layer (design CC-22, default "per faction now, per region when a second world exists"):
WorldState.regional_reputation[region][faction] overrides the faction-wide value for that region when present and is
empty by default, so a one-world game never sees it. Gains always land on the faction-wide value and on every
regional layer that already exists for the faction, so reputation still "carries across regions".
"""
from __future__ import annotations

from dataclasses import dataclass

from fo4sf.reputation.tables import (
    FNV_REPU_RECORDS,
    NV_16_STATE_MATRIX,
    STATE_BY_CODE,
    ReputationStateSpec,
    reputation_state_index,
)

from .model import Reputation, WorldState

# Gain tiers 1-5 worth these points (settlements-factions-precedents.md, verified for New Vegas).
GAIN_TIERS = (1, 2, 4, 7, 12)

# Points at which fame or infamy reaches level 0..3 in the combined-core simulation prototype (FO4SFReputation uses
# 15 / 40 / 75 on the 0..100 runtime axis; FalloutNV.esm REPU pool_max values are recorded in FNV_REPU_RECORDS).
LEVEL_THRESHOLDS = (0, 10, 25, 50)
LEVELS = len(LEVEL_THRESHOLDS)

# Canonical 16-state 4x4 grid shared with fo4sf.reputation.tables (index = fame_tier * 4 + infamy_tier).
# Only (fame_tier=2, infamy_tier=3) carries measured GMST 0x0016951C sRepTitlePosTwoNegThreeDesc (verified_gmst_edid);
# the other 15 cells stay esm_status="unverified" with clean code keys.
NEUTRAL = NV_16_STATE_MATRIX[(0, 0)].title
FAME_STATES = tuple(NV_16_STATE_MATRIX[(f, 0)].title for f in range(LEVELS))
INFAMY_STATES = tuple(NV_16_STATE_MATRIX[(0, i)].title for i in range(LEVELS))
MIXED_NAMES_FROM_NOTE = ("Smiling Troublemaker", "Dark Hero")   # cells unknown; not placed in the grid

# Infamy a helped faction's enemies gain, as a divisor of the fame given (PLACEHOLDER; carried over from the first
# prototype's player_helped, not a game fact).
ENEMY_INFAMY_DIVISOR = 2

# Abstract effects per level (PLACEHOLDER tiers, unverified; for probe P7 to confirm or replace).
PRICE_BY_FAME_LEVEL = (1.0, 0.95, 0.9, 0.8)        # vendor price multiplier earned by fame
PRICE_BY_INFAMY_LEVEL = (1.0, 1.1, 1.25, 1.5)      # and the mark-up infamy costs
REFUSE_SERVICE_INFAMY_LEVEL = 2                    # Hated or worse refuses service...
REFUSE_SERVICE_FAME_FLOOR = 2                      # ...unless fame is at least this level (a mixed state)
HOSTILE_INFAMY_LEVEL = 3                           # Vilified: the note's "hit squads" read as hostile on sight


@dataclass(frozen=True)
class Effects:
    """What a faction does about the player, as abstract tiers. The engine adapter maps them later."""
    state: str
    price_multiplier: float
    refuses_service: bool
    hostile_on_sight: bool


def tier_points(tier: int) -> int:
    """Points for editor tier 1..5 (clamped)."""
    return GAIN_TIERS[min(len(GAIN_TIERS), max(1, tier)) - 1]


def tier_number(amount: int, unit: int) -> int:
    """Editor tier 1..5 for `amount` units of help, one tier per `unit` (tier_points turns it into points)."""
    return min(len(GAIN_TIERS), max(0, amount) // max(1, unit) + 1)


def tier_for(amount: int, unit: int) -> int:
    """Points for `amount` units of help, one tier per `unit` (tier 1 below one unit, tier 5 from four up)."""
    return GAIN_TIERS[min(len(GAIN_TIERS) - 1, max(0, amount) // max(1, unit))]


def level(points: int) -> int:
    """Level 0..3 of one scale (points below zero count as zero)."""
    return max(i for i, t in enumerate(LEVEL_THRESHOLDS) if max(0, points) >= t)


def grid_spec(rep: Reputation) -> ReputationStateSpec:
    """Return the canonical ReputationStateSpec from NV_16_STATE_MATRIX for `rep`."""
    return NV_16_STATE_MATRIX[(level(rep.fame), level(rep.infamy))]


def state(rep: Reputation) -> str:
    """Named state of the shared 4x4 grid; mixed cells carry clean code keys (see module docstring)."""
    return grid_spec(rep).title


def standing(ws: WorldState, faction: str, region: str | None = None) -> Reputation:
    """The player's standing with `faction`, regional layer first, faction-wide otherwise."""
    if region is not None:
        layer = ws.regional_reputation.get(region, {})
        if faction in layer:
            return layer[faction]
    return ws.reputation[faction]


def open_region(ws: WorldState, region: str, faction: str) -> Reputation:
    """Start a regional layer for `faction` in `region` from the faction-wide value (CC-22: only when a second
    world exists). Returns the layer's entry; idempotent."""
    layer = ws.regional_reputation.setdefault(region, {})
    if faction not in layer:
        base = ws.reputation[faction]
        layer[faction] = Reputation(fame=base.fame, infamy=base.infamy)
    return layer[faction]


def add(ws: WorldState, faction: str, fame: int = 0, infamy: int = 0) -> None:
    """Add points to the faction-wide value and to every existing regional layer of `faction`."""
    targets = [ws.reputation[faction]]
    for region in sorted(ws.regional_reputation):
        rep = ws.regional_reputation[region].get(faction)
        if rep is not None:
            targets.append(rep)
    for rep in targets:
        rep.fame = max(0, rep.fame + fame)
        rep.infamy = max(0, rep.infamy + infamy)


def helped(ws: WorldState, faction: str, fame: int) -> None:
    """Fame with `faction` and a share of infamy with each faction it is hostile to (NV pattern, note section 2;
    the share itself is a placeholder)."""
    add(ws, faction, fame=fame)
    for other, rel in sorted(ws.factions[faction].relations.items()):
        if rel < 0 and other in ws.reputation:
            add(ws, other, infamy=fame // ENEMY_INFAMY_DIVISOR)


def effects(ws: WorldState, faction: str, region: str | None = None) -> Effects:
    """Abstract effects of the player's standing with `faction` (placeholder tiers)."""
    rep = standing(ws, faction, region)
    f, i = level(rep.fame), level(rep.infamy)
    return Effects(
        state=state(rep),
        price_multiplier=round(PRICE_BY_FAME_LEVEL[f] * PRICE_BY_INFAMY_LEVEL[i], 4),
        refuses_service=i >= REFUSE_SERVICE_INFAMY_LEVEL and f < REFUSE_SERVICE_FAME_FLOOR,
        hostile_on_sight=i >= HOSTILE_INFAMY_LEVEL,
    )


assert len(FAME_STATES) == len(INFAMY_STATES) == LEVELS == 4
