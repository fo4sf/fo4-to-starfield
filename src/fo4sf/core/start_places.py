"""Unified New-Game Start-Place Table loader and offline validator (`N2`).

Reads `start_places.json` (shared with `dotnet/NewGame` and `scripts/newgame/make_newgame.py`)
so every Story and Warfare start location is defined as a declarative table row
(`id`, `mode`, `story_id`, `space`, `plugin`, `marker`, `quests`, `available`) rather
than bespoke script branches. Rows with `available: false` (unbuilt future titles)
remain documented in the table but are never offered as selectable buttons in game.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set, Tuple

START_PLACES_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "start_places.json")


@dataclass(frozen=True)
class StartPlaceRow:
    id: str
    mode: str
    story_id: str
    story_label: str
    faction_slot: int
    name: str
    space: str
    is_interior: bool
    plugin: str
    marker_source: str
    marker_edid: str
    quests: Tuple[str, ...]
    quest_mask: int
    warfare_key: str
    available: bool


def load_start_places(
    path: str = START_PLACES_JSON,
    *,
    available_only: bool = False,
    known_plugins: Optional[Iterable[str]] = None,
    known_marker_edids: Optional[Iterable[str]] = None,
) -> Tuple[StartPlaceRow, ...]:
    """Load and validate `start_places.json`.

    When `known_plugins` / `known_marker_edids` are supplied, any row marked
    `available: true` whose `plugin` or `marker_edid` cannot load is refused
    (`N2`: never offer a start that cannot load).
    """
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)

    if int(raw.get("schema_version", 0)) != 1:
        raise ValueError(f"Unsupported start_places schema_version in {path}")

    plugin_set: Optional[Set[str]] = (
        {p.strip().lower() for p in known_plugins} if known_plugins is not None else None
    )
    marker_set: Optional[Set[str]] = (
        {m.strip() for m in known_marker_edids} if known_marker_edids is not None else None
    )

    rows: List[StartPlaceRow] = []
    seen_ids: Set[str] = set()
    for entry in raw.get("places", ()):
        pid = str(entry.get("id", "")).strip()
        if not pid or pid in seen_ids:
            raise ValueError(f"Invalid or duplicate start place id: {pid!r}")
        seen_ids.add(pid)

        mode = str(entry.get("mode", "")).strip().lower()
        if mode not in ("story", "warfare"):
            raise ValueError(f"Start place {pid}: invalid mode {mode!r}")

        story_id = str(entry.get("story_id", "none")).strip() or "none"
        story_label = str(entry.get("story_label", "")).strip()
        faction_slot = int(entry.get("faction_slot", -1))
        name = str(entry.get("name", "")).strip()
        space = str(entry.get("space", "")).strip()
        plugin = str(entry.get("plugin", "")).strip()
        is_interior = bool(entry.get("is_interior", False))
        marker_source = str(entry.get("marker_source", "")).strip()
        marker_edid = str(entry.get("marker_edid", "")).strip()
        quests = tuple(str(q).strip() for q in entry.get("quests", ()) if str(q).strip())
        quest_mask = int(entry.get("quest_mask", 0))
        warfare_key = str(entry.get("warfare_key", "")).strip()
        available = bool(entry.get("available", False))

        if not name or not space or not plugin:
            raise ValueError(f"Start place {pid}: empty name, space, or plugin")
        if not marker_source and not marker_edid:
            raise ValueError(f"Start place {pid}: missing marker_source or marker_edid")
        if mode == "story" and (story_id == "none" or not story_label):
            raise ValueError(f"Start place {pid}: story row needs story_id and story_label")
        if mode == "warfare" and (not (0 <= faction_slot <= 7) or not warfare_key):
            raise ValueError(f"Start place {pid}: warfare row needs faction_slot 0..7 and warfare_key")

        if available:
            if plugin_set is not None and plugin.lower() not in plugin_set:
                raise ValueError(
                    f"Start place {pid}: marked available=true but plugin {plugin!r} is not loaded"
                )
            if marker_edid and marker_set is not None and marker_edid not in marker_set:
                raise ValueError(
                    f"Start place {pid}: marked available=true but marker_edid {marker_edid!r} is absent"
                )

        if available_only and not available:
            continue

        rows.append(
            StartPlaceRow(
                id=pid,
                mode=mode,
                story_id=story_id,
                story_label=story_label,
                faction_slot=faction_slot,
                name=name,
                space=space,
                is_interior=is_interior,
                plugin=plugin,
                marker_source=marker_source,
                marker_edid=marker_edid,
                quests=quests,
                quest_mask=quest_mask,
                warfare_key=warfare_key,
                available=available,
            )
        )

    if available_only and not any(r.mode == "story" for r in rows):
        raise ValueError(f"start_places.json has zero available story rows: {path}")
    return tuple(rows)


def available_story_choices(rows: Sequence[StartPlaceRow]) -> List[Tuple[str, str]]:
    """Return distinct `(story_id, story_label)` pairs among available Story rows."""
    out: List[Tuple[str, str]] = []
    seen: Set[str] = set()
    for r in rows:
        if r.available and r.mode == "story" and r.story_id not in seen:
            seen.add(r.story_id)
            out.append((r.story_id, r.story_label))
    return out
