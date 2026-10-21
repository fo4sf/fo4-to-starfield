"""Tuning harness: numbers that say whether a simulated world is alive, over many seeds, with constants overridden.

The simulation's constants are placeholders to argue with (sim.py). This module is how the argument gets numbers:
metrics() reads one finished WorldState, sweep() runs fresh worlds over many seeds with optional constant overrides,
check() compares the aggregate with bounds. Nothing here is a balance decision; DEFAULT_BOUNDS describes what a
healthy fixture world looks like (a world where territory moves, nobody is wiped out for good, supply lines are
breakable but not broken) and exists so a tuning change that kills the world fails loudly. The GAMMA/Anomaly
precedent for an offline simulation that keeps moving without the player is combined-core-notes/gamma-anatomy.md
(A-Life, 2.4, V).

Deterministic: no clock, no unseeded randomness, sorted iteration; the same packs, seeds and overrides give the same
numbers. Holder history is rebuilt from the event log (sim.holder_changes: place_taken and place_cleared events carry
`previous`), so a resumed save measures the same as an unbroken run. All fixture names are placeholders, not game facts.
"""
from __future__ import annotations

import contextlib
import copy
from statistics import mean

from . import sim
from .model import WorldState, load_pack

HOURS_PER_DAY = 24
WINDOW_DAYS = 30                    # "places changing hands per 30 days" is the headline rate

# Modules whose uppercase constants sweep() may override; a bare name is looked up in this order. Only modules a
# sweep actually runs belong here (present.plan is not run, so a present override would change nothing).
OVERRIDABLE = {"sim": sim}

# Placeholders: what a healthy fixture world looks like, as an envelope around the measured baseline in
# docs/combined-core.md ("Balance baseline"), so a rule change that freezes or empties the world fails loudly.
# Not balance decisions: a real pack sets its own bounds. home_only_share is reported but not bounded: in the
# fixtures one faction's only route leads to another's home, so it can never leave (a pack-shape finding, not a
# tuning one). (low, high); None leaves that side open.
DEFAULT_BOUNDS = {
    "story_lock_violations": (0, 0),    # invariant, never a tuning question
    "home_violations": (0, 0),          # invariant: a faction's home never changes hands
    "changes_per_30_days": (2, 30),     # territory moves, but not every tick
    "attacks_per_day": (0.1, 3.0),      # pressure exists without constant war
    "landless_share_max": (None, 0.5),  # no faction spends most of its time holding nothing
    "empty_settlements": (None, 1.0),   # four settlements; a run rarely ends with one empty (was 2.5 before the
                                        # shortage and resettlement rules, when 1.6 of 4 ended empty)
    "empty_share": (None, 0.15),        # settlement-hours with nobody home: places fall, but come back
    "mean_morale": (25, None),          # settlers are not all despairing
    "caravans_raided_share": (None, 0.6),  # supply lines are breakable, not broken
}


# --- one world -------------------------------------------------------------------

def _holder_timeline(ws: WorldState) -> list[tuple[int, dict[str, str | None]]]:
    """Holders at hour 0 and after every change (taken or cleared), as (hour, holders), rebuilt backwards from the
    event log."""
    changes = sim.holder_changes(ws)
    holders = {pid: pl.holder for pid, pl in sorted(ws.places.items())}
    start = dict(holders)
    for e in reversed(changes):
        start[e["place"]] = e.get("previous")
    out = [(0, dict(start))]
    cur = start
    for e in changes:
        cur = dict(cur)
        cur[e["place"]] = sim.new_holder(e)
        out.append((e["hour"], cur))
    return out


def _share_of_time(ws: WorldState, holds_too_few) -> dict[str, float]:
    hours = max(ws.hour, 1)
    timeline = _holder_timeline(ws)
    out = {fid: 0 for fid in sorted(ws.factions)}
    for n, (hour, holders) in enumerate(timeline):
        until = timeline[n + 1][0] if n + 1 < len(timeline) else ws.hour
        for fid in out:
            if holds_too_few(fid, sum(h == fid for h in holders.values())):
                out[fid] += max(0, until - hour)
    return {fid: h / hours for fid, h in out.items()}


def landless_share(ws: WorldState) -> dict[str, float]:
    """Share of the run's hours each faction held no place at all. While faction homes never change hands
    (sim invariant) this is 0 by construction; it is kept so a rule change that breaks that shows up here."""
    return _share_of_time(ws, lambda fid, n: n == 0)


def home_only_share(ws: WorldState) -> dict[str, float]:
    """Share of the run's hours each faction held nothing beyond its home: pushed back but not wiped out."""
    return _share_of_time(ws, lambda fid, n: n <= 1)


def frozen_regions(ws: WorldState) -> list[str]:
    """Regions where no place changed hands (taken or cleared) during the run, sorted."""
    moved = {e["region"] for e in sim.holder_changes(ws)}
    return sorted({pl.region for pl in ws.places.values()} - moved)


def empty_hours(ws: WorldState) -> dict[str, int]:
    """Hours each settlement spent with nobody in it, rebuilt from the log: a `settlement_emptied` event opens a span
    and the next `settlement_resettled` or `settler_arrived` at that place closes it (an open span runs to ws.hour).
    A settlement that starts a run empty has no opening event, so its hours before the first arrival do not count;
    saves written before those events existed measure 0 here."""
    out = {sid: 0 for sid in sorted(ws.settlements)}
    open_since: dict[str, int] = {}
    for e in ws.events:
        sid = e["place"]
        if sid not in out:
            continue
        if e["kind"] == "settlement_emptied":
            open_since.setdefault(sid, e["hour"])
        elif e["kind"] in ("settlement_resettled", "settler_arrived") and sid in open_since:
            out[sid] += e["hour"] - open_since.pop(sid)
    for sid, since in open_since.items():
        out[sid] += ws.hour - since
    return out


def metrics(ws: WorldState) -> dict:
    """Numbers for one finished world: scalars plus the per-faction `landless_share` and `home_only_share` and the
    `frozen_regions` list. A place changing hands is any holder change, a player clear included. Rates are per
    day of ws.hour, so a resumed save measures its whole history. `empty_share` is the share of settlement-hours
    with nobody home (empty_hours), the span metric behind the end-state count `empty_settlements`."""
    days = ws.hour / HOURS_PER_DAY
    taken = sim.holder_changes(ws)
    empties = empty_hours(ws)
    raided = sum(e["kind"] == "caravan_raided" for e in ws.events)
    finished = raided + sum(e["kind"] in ("caravan_arrived", "caravan_lost") for e in ws.events)
    share = landless_share(ws)
    home_only = home_only_share(ws)
    settlements = sorted(ws.settlements.values(), key=lambda s: s.place)
    return {
        "days": days,
        "places_changed_hands": len(taken),
        "changes_per_30_days": len(taken) * WINDOW_DAYS / days if days else 0.0,
        "attacks_per_day": sum(e["kind"] == "attack_launched" for e in ws.events) / days if days else 0.0,
        "caravans_raided_share": raided / finished if finished else 0.0,
        "empty_settlements": sum(s.population == 0 for s in settlements),
        "settlements_emptied": sum(e["kind"] == "settlement_emptied" for e in ws.events),
        "resettlements": sum(e["kind"] == "settlement_resettled" for e in ws.events),
        "empty_share": (sum(empties.values()) / (len(empties) * ws.hour)) if empties and ws.hour else 0.0,
        "mean_morale": mean(s.morale for s in settlements) if settlements else 0.0,
        "landless_share": share,
        "landless_share_max": max(share.values(), default=0.0),
        "home_only_share": home_only,
        "home_only_share_max": max(home_only.values(), default=0.0),
        "story_lock_violations": sum(bool(ws.places[e["place"]].story_lock) for e in taken),
        "home_violations": sum(ws.places[f.home].holder != fid for fid, f in sorted(ws.factions.items())),
        "frozen_regions": frozen_regions(ws),
        "frozen_region_count": len(frozen_regions(ws)),
    }


# --- many worlds -----------------------------------------------------------------

def _same_kind(old, new) -> bool:
    """Whether `new` may replace constant `old`: numbers for numbers (int for float is fine, bool is not), else
    the same type, so a sweep fails before it runs rather than inside a tick with a TypeError."""
    if isinstance(old, bool) or isinstance(new, bool):
        return type(old) is type(new)
    if isinstance(old, (int, float)):
        return isinstance(new, (int, float))
    return type(old) is type(new)


def _resolve(name: str):
    """(module, constant) for "sim.NAME" or a bare NAME found in exactly one OVERRIDABLE module."""
    if "." in name:
        mod, _, const = name.partition(".")
        if mod not in OVERRIDABLE:
            raise ValueError(f"override {name}: unknown module {mod!r}, want one of {', '.join(OVERRIDABLE)}")
        found = [(OVERRIDABLE[mod], const)]
    else:
        found = [(m, name) for m in OVERRIDABLE.values() if hasattr(m, name)]
    if not found or not all(hasattr(m, c) for m, c in found):
        raise ValueError(f"override {name}: no such constant")
    if len(found) > 1:
        raise ValueError(f"override {name}: ambiguous, prefix with a module name")
    mod, const = found[0]
    if not const.isupper():
        raise ValueError(f"override {name}: only uppercase constants may be overridden")
    return mod, const


@contextlib.contextmanager
def overrides(values: dict | None):
    """Set module constants for the block, then restore them whatever happens. Keys as in _resolve; a value of
    another kind than the constant (a string for a number) is a ValueError."""
    saved = []
    try:
        for name in sorted(values or {}):
            mod, const = _resolve(name)
            old = getattr(mod, const)
            if not _same_kind(old, values[name]):
                raise ValueError(f"override {name}: {values[name]!r} is not a {type(old).__name__} like {old!r}")
            saved.append((mod, const, old))
            setattr(mod, const, values[name])
        yield
    finally:
        for mod, const, old in reversed(saved):
            setattr(mod, const, old)


def world(packs: list[dict], seed: int) -> WorldState:
    """A fresh world from copies of `packs`, in order."""
    ws = WorldState(seed=seed)
    for pack in packs:
        load_pack(ws, copy.deepcopy(pack))
    return ws


def aggregate(per_seed: dict[int, dict]) -> dict:
    """Means over seeds. Scalars average; the per-faction shares average per faction; `frozen_regions` keeps the
    regions frozen in every seed. `seeds` counts the runs."""
    runs = [per_seed[s] for s in sorted(per_seed)]
    if not runs:
        return {"seeds": 0}
    out: dict = {"seeds": len(runs)}
    for key in sorted(runs[0]):
        vals = [r[key] for r in runs]
        if key in ("landless_share", "home_only_share"):
            factions = sorted({f for v in vals for f in v})
            out[key] = {f: mean(v.get(f, 0.0) for v in vals) for f in factions}
        elif key == "frozen_regions":
            out[key] = sorted(set.intersection(*(set(v) for v in vals)))
        else:
            out[key] = mean(vals)
    return out


def sweep(packs: list[dict], seeds, days: int, overrides_: dict | None = None) -> dict:
    """Fresh worlds per seed for `days`, with `overrides_` applied for the whole sweep and restored after.
    Returns {"days", "overrides", "seeds": {seed: metrics}, "aggregate"}."""
    per_seed = {}
    with overrides(overrides_):
        for seed in sorted(set(seeds)):
            ws = world(packs, seed)
            sim.run(ws, days * HOURS_PER_DAY)
            per_seed[seed] = metrics(ws)
    return {"days": days, "overrides": dict(sorted((overrides_ or {}).items())),
            "seeds": per_seed, "aggregate": aggregate(per_seed)}


def check(agg: dict, bounds: dict | None = None) -> list[str]:
    """Bounds the aggregate breaks, as readable lines (empty when healthy). A bound names an aggregate scalar;
    an unknown name is itself reported so a renamed metric cannot pass silently."""
    broken = []
    for key in sorted(DEFAULT_BOUNDS if bounds is None else bounds):
        lo, hi = (DEFAULT_BOUNDS if bounds is None else bounds)[key]
        v = agg.get(key)
        if not isinstance(v, (int, float)):
            broken.append(f"{key}: not an aggregate number ({v!r})")
        elif lo is not None and v < lo:
            broken.append(f"{key}: {v:.3g} below {lo}")
        elif hi is not None and v > hi:
            broken.append(f"{key}: {v:.3g} above {hi}")
    return broken
