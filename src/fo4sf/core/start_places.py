"""Unified New-Game Start-Place Table loader, unavailable-row policy, and Variant (b) setup model (`N2`, `S1`, `S3`).

Reads `start_places.json` (shared across `FO4SFPipboyMenu.dll`, `dotnet/NewGame`, and
`scripts/newgame/make_newgame.py`) so every Story and Warfare start location is defined
as a declarative table row (`id`, `mode`, `story_id`, `faction_slot`, `faction_label`,
`name`, `space`, `plugin`, `marker`, `quests`, `available`, `unavailable_reason`).

Default unavailable-row policy (`DEFAULT_SHOW_UNAVAILABLE_STARTS = False`):
  - By default (`show_unavailable=False` / `SetupShowUnavailable=0`), rows with
    `available: false` are left OFF so players never see dead entries while only the
    Commonwealth slice is installed (and Variant `(a)`'s `MessageBoxMenu` has no native
    disabled button state).
  - When `show_unavailable=True` (`SetupShowUnavailable=1` / `--show-unavailable-starts 1`),
    Variant `(b)`'s setup screen renders `available: false` rows greyed out (`[LOCKED]`)
    with their one-line `unavailable_reason`, while strictly refusing `confirm()` on any
    `available: false` row (`N2` / `S3`: never offer or confirm a start that cannot load).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

START_PLACES_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "start_places.json")
WARFARE_STARTS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "warfare_starts.json")
DEFAULT_SHOW_UNAVAILABLE_STARTS = False
DIFFICULTY_LABELS: Tuple[str, ...] = ("EASY", "NORMAL", "HARD", "VERY HARD")
ALLOWED_SETUP_GLYPHS = " -.:/0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ',()?!+%&_#=[]<>"


def sanitize_setup_text(raw: str, max_cols: int = 68) -> str:
    """Sanitize a setup screen text line to embedded `SETUP_FONT` glyphs (1:1 with C++ `SanitizeSetupText`)."""
    out: List[str] = []
    for ch in raw:
        if len(out) >= max_cols:
            break
        uc = ch.upper()
        out.append(uc if uc in ALLOWED_SETUP_GLYPHS else " ")
    return "".join(out)


@dataclass(frozen=True)
class StartPlaceRow:
    id: str
    mode: str
    story_id: str
    story_label: str
    faction_slot: int
    faction_label: str
    name: str
    space: str
    is_interior: bool
    plugin: str
    marker_source: str
    marker_edid: str
    quests: Tuple[str, ...]
    quest_mask: int
    warfare_key: str
    min_difficulty: int
    max_difficulty: int
    available: bool
    unavailable_reason: str = ""


@dataclass(frozen=True)
class SetupCommitPayload:
    """Exact `start record` store values committed identically by Variant (a) and Variant (b)."""

    mode_val: int              # 1 = Story, 2 = Warfare -> FO4SF_GameMode (0x000870)
    mode_tag: str              # "story" | "warfare"
    story_choice_idx: int      # 0..N-1 for Story, -1 for Warfare -> FO4SF_StoryLine (0x000878)
    story_id: str              # e.g. "fo4_commonwealth" or "none"
    survival: int              # 0 | 1 -> FO4SF_SurvivalStart (0x000871) & FO4SF_SurvivalLocked (0x000872)
    difficulty: int            # 0..3 -> FO4SF_StartDifficulty (0x000873)
    warfare_faction_slot: int  # -1 for Story, 0..7 for Warfare -> FO4SF_WarfareFaction (0x000874)
    warfare_start_idx: int     # -1 for Story, canonical row index in warfare_starts.json (or all warfare rows) -> FO4SF_WarfareStartIndex (0x000875)
    start_place_row: int       # 0..M-1 among available rows -> FO4SF_StartPlaceRow (0x000879)
    place_id: str              # e.g. "fo4_vault111" or "minutemen_sanctuary"

    def start_record_line(self, backdrop: str) -> str:
        return (
            f"start record mode={self.mode_tag} story={self.story_id} "
            f"faction={self.warfare_faction_slot} place={self.place_id} "
            f"survival={self.survival} difficulty={self.difficulty} backdrop={backdrop}"
        )


def load_start_places(
    path: str = START_PLACES_JSON,
    *,
    available_only: bool = False,
    known_plugins: Optional[Iterable[str]] = None,
    known_marker_edids: Optional[Iterable[str]] = None,
) -> Tuple[StartPlaceRow, ...]:
    """Load and validate `start_places.json` (`N2`, `S1`, `S3`)."""
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
        faction_label = str(entry.get("faction_label", "")).strip()
        name = str(entry.get("name", "")).strip()
        space = str(entry.get("space", "")).strip()
        plugin = str(entry.get("plugin", "")).strip()
        is_interior = bool(entry.get("is_interior", False))
        marker_source = str(entry.get("marker_source", "")).strip()
        marker_edid = str(entry.get("marker_edid", "")).strip()
        quests = tuple(str(q).strip() for q in entry.get("quests", ()) if str(q).strip())
        quest_mask = int(entry.get("quest_mask", 0))
        warfare_key = str(entry.get("warfare_key", "")).strip()
        min_diff = int(entry.get("min_difficulty", 0))
        max_diff = int(entry.get("max_difficulty", 3))
        available = bool(entry.get("available", False))
        unavailable_reason = str(entry.get("unavailable_reason", "")).strip()

        if not name or not space or not plugin:
            raise ValueError(f"Start place {pid}: empty name, space, or plugin")
        if not marker_source and not marker_edid:
            raise ValueError(f"Start place {pid}: missing marker_source or marker_edid")
        if mode == "story" and (story_id == "none" or not story_label):
            raise ValueError(f"Start place {pid}: story row needs story_id and story_label")
        if mode == "warfare" and (not (0 <= faction_slot <= 7) or not warfare_key or not faction_label):
            raise ValueError(f"Start place {pid}: warfare row needs faction_slot 0..7, faction_label, and warfare_key")
        if not (0 <= min_diff <= max_diff <= 3):
            raise ValueError(f"Start place {pid}: invalid difficulty bounds {min_diff}..{max_diff}")

        if available:
            if plugin_set is not None and plugin.lower() not in plugin_set:
                raise ValueError(
                    f"Start place {pid}: marked available=true but plugin {plugin!r} is not loaded"
                )
            if marker_edid and marker_set is not None and marker_edid not in marker_set:
                raise ValueError(
                    f"Start place {pid}: marked available=true but marker_edid {marker_edid!r} is absent"
                )
        else:
            if not unavailable_reason or "\n" in unavailable_reason or "\r" in unavailable_reason:
                raise ValueError(
                    f"Start place {pid}: available=false requires a non-empty single-line unavailable_reason"
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
                faction_label=faction_label,
                name=name,
                space=space,
                is_interior=is_interior,
                plugin=plugin,
                marker_source=marker_source,
                marker_edid=marker_edid,
                quests=quests,
                quest_mask=quest_mask,
                warfare_key=warfare_key,
                min_difficulty=min_diff,
                max_difficulty=max_diff,
                available=available,
                unavailable_reason=unavailable_reason,
            )
        )

    if available_only and not any(r.mode == "story" for r in rows):
        raise ValueError(f"start_places.json has zero available story rows: {path}")
    return tuple(rows)


def load_warfare_start_keys(path: str = WARFARE_STARTS_JSON) -> Tuple[str, ...]:
    """Load canonical Warfare start keys in exact row order from `warfare_starts.json` / `FO4SFWarfareStarts.json`."""
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)
    if int(raw.get("schema_version", 0)) != 1:
        raise ValueError(f"Unsupported warfare_starts schema_version in {path}")
    keys: List[str] = []
    seen: Set[str] = set()
    for entry in raw.get("starts", ()):
        key = str(entry.get("key", "")).strip()
        if not key or key in seen:
            raise ValueError(f"Invalid or duplicate warfare start key in {path}: {key!r}")
        seen.add(key)
        keys.append(key)
    return tuple(keys)


def _load_optional_warfare_keys(warfare_starts_path: Optional[str]) -> Tuple[str, ...]:
    if not warfare_starts_path:
        return ()
    candidates = [warfare_starts_path]
    parent = os.path.dirname(os.path.abspath(warfare_starts_path))
    alt = os.path.join(parent, "FO4SFWarfareStarts.json")
    if alt not in candidates:
        candidates.append(alt)
    for cand in candidates:
        if os.path.isfile(cand):
            return load_warfare_start_keys(cand)
    return ()


def available_story_choices(rows: Sequence[StartPlaceRow]) -> List[Tuple[str, str]]:
    """Return distinct `(story_id, story_label)` pairs among available Story rows."""
    out: List[Tuple[str, str]] = []
    seen: Set[str] = set()
    for r in rows:
        if r.available and r.mode == "story" and r.story_id not in seen:
            seen.add(r.story_id)
            out.append((r.story_id, r.story_label))
    return out


class SetupScreenModel:
    """Single-page Variant (b) setup state machine (`S1` / `S3`), held in 1:1 parity with C++ `setup_places.h`."""

    def __init__(
        self,
        rows: Sequence[StartPlaceRow],
        *,
        show_unavailable: bool = DEFAULT_SHOW_UNAVAILABLE_STARTS,
        warfare_keys: Optional[Sequence[str]] = None,
        warfare_starts_path: Optional[str] = WARFARE_STARTS_JSON,
    ) -> None:
        self._all_rows: Tuple[StartPlaceRow, ...] = tuple(rows)
        self._avail_rows: Tuple[StartPlaceRow, ...] = tuple(r for r in rows if r.available)
        if not any(r.mode == "story" for r in self._avail_rows):
            raise ValueError("SetupScreenModel requires at least one available story row")
        if not any(r.mode == "warfare" for r in self._avail_rows):
            raise ValueError("SetupScreenModel requires at least one available warfare row")
        self.show_unavailable = bool(show_unavailable)
        self._visible_rows: Tuple[StartPlaceRow, ...] = (
            self._all_rows if self.show_unavailable else self._avail_rows
        )
        if warfare_keys is not None:
            self._warfare_keys: Tuple[str, ...] = tuple(
                str(k).strip() for k in warfare_keys if str(k).strip()
            )
        else:
            self._warfare_keys = _load_optional_warfare_keys(warfare_starts_path)

        self.selected_row = 0       # 0=Mode, 1=Story/Faction, 2=StartPlace, 3=Survival, 4=Difficulty
        self.mode_val = 1           # 1=Story, 2=Warfare
        self.story_idx = 0
        self.faction_idx = 0
        self.place_idx = 0
        self.survival = 0           # 0=Off, 1=On
        self.difficulty = 1         # 0..3 (default 1 = Normal)

    def _story_groups(self) -> List[Tuple[str, str, bool]]:
        out: List[Tuple[str, str, bool]] = []
        seen: Dict[str, int] = {}
        for r in self._visible_rows:
            if r.mode != "story":
                continue
            if r.story_id not in seen:
                seen[r.story_id] = len(out)
                out.append((r.story_id, r.story_label, r.available))
            elif r.available and not out[seen[r.story_id]][2]:
                idx = seen[r.story_id]
                out[idx] = (r.story_id, r.story_label, True)
        return out

    def _faction_groups(self) -> List[Tuple[str, int, bool]]:
        out: List[Tuple[str, int, bool]] = []
        seen: Dict[str, int] = {}
        for r in self._visible_rows:
            if r.mode != "warfare":
                continue
            if r.faction_label not in seen:
                seen[r.faction_label] = len(out)
                out.append((r.faction_label, r.faction_slot, r.available))
            elif r.available and not out[seen[r.faction_label]][2]:
                idx = seen[r.faction_label]
                out[idx] = (r.faction_label, r.faction_slot, True)
        return out

    def _places_for_current_group(self) -> List[StartPlaceRow]:
        if self.mode_val == 1:
            groups = self._story_groups()
            if not groups:
                return []
            sid = groups[min(self.story_idx, len(groups) - 1)][0]
            return [r for r in self._visible_rows if r.mode == "story" and r.story_id == sid]
        fgroups = self._faction_groups()
        if not fgroups:
            return []
        flabel = fgroups[min(self.faction_idx, len(fgroups) - 1)][0]
        matching = [
            r
            for r in self._visible_rows
            if r.mode == "warfare"
            and r.faction_label == flabel
            and r.min_difficulty <= self.difficulty <= r.max_difficulty
        ]
        if matching:
            return matching
        return [r for r in self._visible_rows if r.mode == "warfare" and r.faction_label == flabel]

    def current_place_row(self) -> StartPlaceRow:
        places = self._places_for_current_group()
        if not places:
            return self._avail_rows[0]
        return places[min(self.place_idx, len(places) - 1)]

    def move_cursor(self, delta: int) -> None:
        self.selected_row = max(0, min(4, self.selected_row + delta))

    def adjust_row(self, row: int, delta: int) -> None:
        if delta == 0:
            return
        step = 1 if delta > 0 else -1
        if row == 0:
            self.mode_val = 2 if self.mode_val == 1 else 1
            self.place_idx = 0
        elif row == 1:
            if self.mode_val == 1:
                groups = self._story_groups()
                if groups:
                    self.story_idx = (self.story_idx + step) % len(groups)
            else:
                fgroups = self._faction_groups()
                if fgroups:
                    self.faction_idx = (self.faction_idx + step) % len(fgroups)
            self.place_idx = 0
        elif row == 2:
            places = self._places_for_current_group()
            if places:
                self.place_idx = (self.place_idx + step) % len(places)
        elif row == 3:
            self.survival = 0 if self.survival else 1
        elif row == 4:
            self.difficulty = (self.difficulty + step) % 4
            places = self._places_for_current_group()
            if self.place_idx >= len(places):
                self.place_idx = 0

    def render_lines(self) -> Tuple[Tuple[str, str, str, str, str], str]:
        """Return `(five_row_strings, status_line)` rendered onto `FO4SF_SetupScreen.swf`."""
        cur = self.current_place_row()
        mark = lambda idx: "> " if self.selected_row == idx else "  "
        mode_txt = "STORY" if self.mode_val == 1 else "WARFARE"
        if self.mode_val == 1:
            groups = self._story_groups()
            _, slabel, savail = groups[min(self.story_idx, len(groups) - 1)]
            tag1 = "" if savail else "[LOCKED] "
            row1 = f"{mark(1)}STORY LINE: {tag1}{slabel.upper()}"
        else:
            fgroups = self._faction_groups()
            flabel, _, favail = fgroups[min(self.faction_idx, len(fgroups) - 1)]
            tag1 = "" if favail else "[LOCKED] "
            row1 = f"{mark(1)}FACTION: {tag1}{flabel.upper()}"

        ptag = "" if cur.available else "[LOCKED] "
        row0 = sanitize_setup_text(f"{mark(0)}MODE: {mode_txt}", 68)
        row1 = sanitize_setup_text(row1, 68)
        row2 = sanitize_setup_text(f"{mark(2)}START PLACE: {ptag}{cur.name}", 68)
        row3 = sanitize_setup_text(f"{mark(3)}SURVIVAL: {'ON' if self.survival else 'OFF'}", 68)
        row4 = sanitize_setup_text(f"{mark(4)}DIFFICULTY: {DIFFICULTY_LABELS[self.difficulty]}", 68)
        if cur.available:
            status = "READY: PRESS CONFIRM (ENTER) TO BEGIN"
        else:
            status = sanitize_setup_text(f"LOCKED: {cur.unavailable_reason}", 96)
        return (row0, row1, row2, row3, row4), status

    def _resolve_warfare_start_idx(self, cur: StartPlaceRow) -> int:
        """Return canonical `warfare_starts.json` row index for `cur` (fallback: canonical order across all warfare rows)."""
        key = cur.warfare_key or cur.id
        if self._warfare_keys:
            for idx, wf_key in enumerate(self._warfare_keys):
                if wf_key == key:
                    return idx
        all_warfare = [r for r in self._all_rows if r.mode == "warfare"]
        for idx, r in enumerate(all_warfare):
            if (r.warfare_key or r.id) == key or r.id == cur.id:
                return idx
        return 0

    def confirm(self) -> Optional[SetupCommitPayload]:
        """Return exact store payload if `current_place_row().available` is True, else `None` (refused)."""
        cur = self.current_place_row()
        if not cur.available:
            return None

        avail_place_idx = next(i for i, r in enumerate(self._avail_rows) if r.id == cur.id)
        if self.mode_val == 1:
            story_choices = available_story_choices(self._avail_rows)
            s_idx = next((i for i, (sid, _) in enumerate(story_choices) if sid == cur.story_id), 0)
            return SetupCommitPayload(
                mode_val=1,
                mode_tag="story",
                story_choice_idx=s_idx,
                story_id=cur.story_id,
                survival=self.survival,
                difficulty=self.difficulty,
                warfare_faction_slot=-1,
                warfare_start_idx=-1,
                start_place_row=avail_place_idx,
                place_id=cur.id,
            )

        wf_idx = self._resolve_warfare_start_idx(cur)
        return SetupCommitPayload(
            mode_val=2,
            mode_tag="warfare",
            story_choice_idx=-1,
            story_id="none",
            survival=self.survival,
            difficulty=self.difficulty,
            warfare_faction_slot=cur.faction_slot,
            warfare_start_idx=wf_idx,
            start_place_row=avail_place_idx,
            place_id=cur.id,
        )
