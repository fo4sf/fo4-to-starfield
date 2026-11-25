"""Warfare start descriptor loader and offline validator (`S3`).

Reads `warfare_starts.json` (the table consumed by `dotnet/NewGame` and
`scripts/newgame/make_newgame.py`) and validates faction slots (`0..7`),
difficulty ranges (`0..3`), `FO4TerrainCore.esm` map-marker EditorIDs, gear
entries, standing, and squad cap.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set, Tuple

WARFARE_STARTS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "warfare_starts.json")


@dataclass(frozen=True)
class WarfareGearItem:
    plugin: str
    form_id: int
    count: int
    equip: bool


@dataclass(frozen=True)
class WarfareStartRow:
    key: str
    faction_slot: int
    faction_name: str
    name: str
    marker_edid: str
    marker_plugin: str
    heading: float
    min_difficulty: int
    max_difficulty: int
    background_index: int
    fame: float
    infamy: float
    karma: float
    squad_cap: int
    gear: Tuple[WarfareGearItem, ...]
    anchor_edid: str = ""
    pos: Optional[Tuple[float, float, float]] = None
    cell: Optional[Tuple[int, int]] = None


def load_warfare_starts(
    path: str = WARFARE_STARTS_JSON,
    known_marker_edids: Optional[Iterable[str]] = None,
    known_exterior_cells: Optional[Iterable[Tuple[int, int]]] = None,
) -> Tuple[WarfareStartRow, ...]:
    """Load and validate `warfare_starts.json`.

    When `known_marker_edids` or `known_exterior_cells` is supplied, refuses any row
    whose `anchor_edid`/`marker_edid` or `cell` is missing from those sets.
    """
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)

    if int(raw.get("schema_version", 0)) != 1:
        raise ValueError(f"Unsupported warfare_starts schema_version in {path}")

    marker_set: Optional[Set[str]] = (
        {m.strip() for m in known_marker_edids} if known_marker_edids is not None else None
    )
    cell_set: Optional[Set[Tuple[int, int]]] = (
        {(int(c[0]), int(c[1])) for c in known_exterior_cells}
        if known_exterior_cells is not None
        else None
    )

    rows: List[WarfareStartRow] = []
    seen_keys: Set[str] = set()
    for entry in raw.get("starts", ()):
        key = str(entry["key"]).strip()
        if not key or key in seen_keys:
            raise ValueError(f"Invalid or duplicate warfare start key: {key!r}")
        seen_keys.add(key)

        slot = int(entry["faction_slot"])
        if not (0 <= slot <= 7):
            raise ValueError(f"Warfare start {key}: faction_slot {slot} outside 0..7")

        min_diff = int(entry["min_difficulty"])
        max_diff = int(entry["max_difficulty"])
        if not (0 <= min_diff <= max_diff <= 3):
            raise ValueError(f"Warfare start {key}: invalid difficulty range {min_diff}..{max_diff}")

        marker_edid = str(entry["marker_edid"]).strip()
        anchor_edid = str(entry.get("anchor_edid") or marker_edid).strip()
        if not marker_edid and not anchor_edid:
            raise ValueError(f"Warfare start {key}: empty marker_edid")
        check_edid = anchor_edid or marker_edid
        if marker_set is not None and check_edid not in marker_set:
            raise ValueError(f"Warfare start {key}: unknown marker_edid {check_edid!r} (not in terrain core)")

        raw_pos = entry.get("pos")
        pos_tuple: Optional[Tuple[float, float, float]] = None
        if raw_pos is not None:
            if not isinstance(raw_pos, (list, tuple)) or len(raw_pos) != 3:
                raise ValueError(f"Warfare start {key}: invalid pos {raw_pos!r}")
            pos_tuple = (float(raw_pos[0]), float(raw_pos[1]), float(raw_pos[2]))

        raw_cell = entry.get("cell")
        cell_tuple: Optional[Tuple[int, int]] = None
        if raw_cell is not None:
            if not isinstance(raw_cell, (list, tuple)) or len(raw_cell) != 2:
                raise ValueError(f"Warfare start {key}: invalid cell {raw_cell!r}")
            cell_tuple = (int(raw_cell[0]), int(raw_cell[1]))
        if cell_set is not None:
            if cell_tuple is None:
                raise ValueError(f"Warfare start {key}: missing cell coordinates")
            if cell_tuple not in cell_set:
                raise ValueError(f"Warfare start {key}: unknown exterior cell {cell_tuple} (not in terrain core)")

        squad_cap = int(entry["squad_cap"])
        if squad_cap < 1:
            raise ValueError(f"Warfare start {key}: squad_cap {squad_cap} must be >= 1")

        gear_items: List[WarfareGearItem] = []
        for g in entry.get("gear", ()):
            g_plugin = str(g["plugin"]).strip()
            g_id = int(str(g["id"]), 16)
            g_cnt = int(g["count"])
            if not g_plugin or g_id <= 0 or g_cnt <= 0:
                raise ValueError(f"Warfare start {key}: invalid gear item {g!r}")
            gear_items.append(
                WarfareGearItem(
                    plugin=g_plugin,
                    form_id=g_id,
                    count=g_cnt,
                    equip=bool(g.get("equip", False)),
                )
            )
        if not gear_items:
            raise ValueError(f"Warfare start {key}: gear list must not be empty")

        rows.append(
            WarfareStartRow(
                key=key,
                faction_slot=slot,
                faction_name=str(entry["faction_name"]).strip(),
                name=str(entry["name"]).strip(),
                marker_edid=marker_edid,
                marker_plugin=str(entry.get("marker_plugin", "FO4TerrainCore.esm")).strip(),
                heading=float(entry.get("heading", 0.0)),
                min_difficulty=min_diff,
                max_difficulty=max_diff,
                background_index=int(entry.get("background_index", 0)),
                fame=float(entry["fame"]),
                infamy=float(entry.get("infamy", 0.0)),
                karma=float(entry["karma"]),
                squad_cap=squad_cap,
                gear=tuple(gear_items),
                anchor_edid=anchor_edid,
                pos=pos_tuple,
                cell=cell_tuple,
            )
        )

    return tuple(rows)


def distinct_warfare_factions(rows: Sequence[WarfareStartRow]) -> List[Tuple[int, str]]:
    """Return distinct `(faction_slot, faction_name)` pairs preserving table order."""
    out: List[Tuple[int, str]] = []
    seen: Set[int] = set()
    for r in rows:
        if r.faction_slot not in seen:
            seen.add(r.faction_slot)
            out.append((r.faction_slot, r.faction_name))
    return out
