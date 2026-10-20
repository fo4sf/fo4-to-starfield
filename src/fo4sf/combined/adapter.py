"""Engine adapter, step one: a record PLAN for the small state the game must read, not records.

The design's recommended shape (CC-02 option C'; the C' triple below is CC-02's wording, the record blocks are
combined-core-notes/engine-feasibility.md section 1): the state conditions, dialogue and leveled lists need (holder per
place, reputation tiers, the story-mode switch) lives in records the save already keeps; the bulk simulation stays in
the SFSE plugin's sidecar (sidecar.py).
This module names those records and says what value each should carry for a given WorldState. It writes nothing:
no plugin, no Mutagen, no Papyrus. A converter step later turns a Plan into KYWD and GLOB records; a plugin or a
script later performs the writes that changes() lists.

Slot kinds, with the engine block each leans on (the blocks are cited from engine-feasibility.md, "Building blocks"):
- one keyword per place, kind "keyword": the holder code is stored as that keyword's datum on the place's location and
  read by GetKeywordDataForLocation / GetKeywordDataForCurrentLocation (conditions verified in xEdit SF1). The note
  plans a single FOCC_Holder keyword with a datum per location (sections 1 and 3); this plan names one keyword per
  place instead so each slot has its own editor id (our choice, not the note's; a converter may fold them). Whether
  keyword data survives a save is UNRESOLVED (probe P2): these slots are probe-dependent and so is game_view()'s
  value for them. If P2 fails the fallback is one global per place, and only this module changes.
- one global per faction, kind "global": the reputation tier, read by GetGlobalValue (verified). Not probe-dependent.
- one global per play setting, kind "global": survival preset, raid pressure, story mode, story active (section 9 of
  the note names FOCC_StoryMode and FOCC_StoryActive). Not probe-dependent.

Holder codes are small ints assigned from the sorted faction ids: 0 means nobody holds the place, the first faction in
sorted order is 1, and so on. They are stable for a given set of factions, so a pack must be frozen before records
are built; adding a faction later renumbers everything after it, which is why Plan.holder_codes is part of the plan.

Record prefix FOCC_ is design CC-03's default. Editor ids are letters, digits and underscores (ASSUMPTION: Creation
Engine convention, not verified for Creation Engine 2); the length limit is an ASSUMPTION too (no CE2 limit was
verified), chosen short enough to be safe. Every other number here is a
placeholder. Fixture names in the tests are placeholders, not game facts.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import re

from . import reputation
from .model import WorldState
from .modes import RAID_PRESSURE_NAMES, SURVIVAL_PRESET_NAMES

PREFIX = "FOCC_"                       # CC-03 default
EDITOR_ID_MAX = 64                     # ASSUMPTION: no verified CE2 editor-id limit; kept short to be safe
EDITOR_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Slot name parts after the prefix (placeholders; a pack may want shorter ones later).
PLACE_PART = "Place"
REP_PART = "Rep"
SETTINGS_GLOBALS = ("Survival", "RaidPressure", "StoryMode", "StoryActive")

EMPTY_HOLDER = 0                       # holder code for a place nobody holds
PROBE_KEYWORD_DATA = "P2"              # engine-feasibility.md: keyword-data persistence unresolved


@dataclass(frozen=True)
class Slot:
    """One named record the pack needs. `probe` names the PC probe its viability waits on, or None."""
    id: str                            # editor id, prefix included
    kind: str                          # keyword | global
    purpose: str                       # holder | reputation | setting
    subject: str                       # place id, faction id or setting name
    probe: str | None = None


@dataclass
class Plan:
    prefix: str
    holder_codes: dict[str, int]       # faction id -> code; EMPTY_HOLDER is reserved for "no holder"
    slots: list[Slot]                  # sorted by id

    def by_id(self) -> dict[str, Slot]:
        return {s.id: s for s in self.slots}

    def to_dict(self) -> dict:
        return asdict(self)


def editor_id(*parts: str, prefix: str = PREFIX) -> str:
    """Join `parts` under the prefix as a valid editor id. Characters outside [A-Za-z0-9_] become underscores;
    raises ValueError when the result is empty, too long or still invalid."""
    body = "_".join(re.sub(r"[^A-Za-z0-9_]", "_", p) for p in parts if p)
    if not body:
        raise ValueError("editor id needs at least one non-empty part")
    eid = prefix + body
    if len(eid) > EDITOR_ID_MAX:
        raise ValueError(f"editor id {eid!r} longer than {EDITOR_ID_MAX}")
    if not EDITOR_ID_RE.match(eid):
        raise ValueError(f"invalid editor id {eid!r}")
    return eid


def holder_codes(ws: WorldState) -> dict[str, int]:
    """faction id -> holder code: 1, 2, ... in sorted faction-id order (0 is EMPTY_HOLDER)."""
    return {fid: n for n, fid in enumerate(sorted(ws.factions), start=EMPTY_HOLDER + 1)}


def reputation_tier(ws: WorldState, faction: str) -> int:
    """The reputation grid cell as one int: fame level * LEVELS + infamy level (0..15 with 4 levels), so one
    GetGlobalValue condition can test a cell or a row. Faction-wide value only (the regional layer of CC-22 would
    need a global per region, not planned yet)."""
    rep = ws.reputation[faction]
    return reputation.level(rep.fame) * reputation.LEVELS + reputation.level(rep.infamy)


def record_plan(ws: WorldState, prefix: str = PREFIX) -> Plan:
    """The named slots a pack built from `ws` needs. Raises ValueError when two ids collide after sanitising
    (for example places "farm-a" and "farm_a")."""
    slots = []
    for pid in sorted(ws.places):
        slots.append(Slot(editor_id(PLACE_PART, pid, prefix=prefix), "keyword", "holder", pid, PROBE_KEYWORD_DATA))
    for fid in sorted(ws.factions):
        slots.append(Slot(editor_id(REP_PART, fid, prefix=prefix), "global", "reputation", fid))
    for name in SETTINGS_GLOBALS:
        slots.append(Slot(editor_id(name, prefix=prefix), "global", "setting", name))
    seen: dict[str, Slot] = {}
    for s in slots:
        if s.id in seen:
            raise ValueError(f"editor id {s.id!r} collides: {seen[s.id].subject!r} and {s.subject!r}")
        seen[s.id] = s
    return Plan(prefix, holder_codes(ws), sorted(slots, key=lambda s: s.id))


def _setting_value(ws: WorldState, name: str) -> int:
    s = ws.settings
    if name == "Survival":
        return SURVIVAL_PRESET_NAMES.index(s.survival)
    if name == "RaidPressure":
        return RAID_PRESSURE_NAMES.index(s.raid_pressure)
    if name == "StoryMode":
        return int(s.story_mode)
    if name == "StoryActive":          # mirrors Settings.story_active: only counts under story mode
        return int(s.story_mode and bool(s.active_stories))
    raise KeyError(name)


def game_view(ws: WorldState, plan: Plan | None = None) -> dict[str, int]:
    """{slot id: value} for the small state, every value an int (keyword data is one float per (location, keyword),
    engine-feasibility.md; the GLOB value type is unverified, so ints keep comparisons exact either way). Keyword-slot
    values depend on probe P2 (module docstring)."""
    plan = plan or record_plan(ws)
    out = {}
    for s in plan.slots:
        if s.purpose == "holder":
            holder = ws.places[s.subject].holder
            out[s.id] = EMPTY_HOLDER if holder is None else plan.holder_codes[holder]
        elif s.purpose == "reputation":
            out[s.id] = reputation_tier(ws, s.subject)
        else:
            out[s.id] = _setting_value(ws, s.subject)
    return out


def changes(old_view: dict[str, int] | None, new_view: dict[str, int]) -> list[tuple[str, int]]:
    """The minimal writes to move the game from `old_view` to `new_view`: (slot id, value) for every slot that is
    new or whose value differs, sorted by id. A slot present only in the old view is a plan change, not a write,
    and is ignored. None as the old view means nothing is written yet, so everything is a write."""
    old = old_view or {}
    return sorted((k, v) for k, v in new_view.items() if k not in old or old[k] != v)


assert editor_id(PLACE_PART, "x").startswith(PREFIX)
