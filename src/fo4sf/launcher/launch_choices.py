"""Pre-launch Story/Warfare, variant, Survival, and filtered start-place selection & persistence (Round 12–14).

Reads ONLY the restart-only launch choices (`start.mode`, `start.variant`, `start.survival`, `start.place`), filters
`src/fo4sf/core/start_places.json` by Mode/variant, validates row availability strictly from loaded plugins
and loaded places (guaranteeing no Story row except `fo4_prewar_sanctuary` / `fo4_vault111` claims available until Task 6),
refuses `--survival on` when `FO4SFHardcore.esm` is absent, propagates `schema_version`, `start_variant`, `nonce`,
`created_at`, and selected `min_difficulty`, and atomically writes `%LOCALAPPDATA%\\FO4SF\\launch_choices.json`
before `Starfield.exe` boots.
"""

from __future__ import annotations

import json
import ntpath
import os
import posixpath
import struct
import time
import uuid
import zlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from ..core import start_places as sp
from ..core import warfare_starts as ws

LAUNCH_CHOICES_FILENAME = "launch_choices.json"
LAUNCH_CHOICES_SCHEMA_VERSION = 2
ALLOWED_STORY_IDS: Tuple[str, ...] = ("fo4_prewar_sanctuary", "fo4_vault111")
MODE_CHOICES: Tuple[str, ...] = ("story", "warfare")
VARIANT_CHOICES: Tuple[str, ...] = ("normal", "quick")
HARDCORE_PLUGIN = "FO4SFHardcore.esm"
CONTENT_PLUGINS: frozenset[str] = frozenset({
    "fo4port.esm",
    "fo4terraincore.esm",
    "fo4sfhome.esm",
    "fo4sfnewgame.esm",
    "fo4sfprewar.esm",
    "fo4sfprewar_sanctuary.esm",
    "fo4sfcorevalues.esm",
    "fo4sfhardcore.esm",
    "fo4sfreputation.esm",
    "fo4sfprogression.esm",
    "fo4sfcompanions.esm",
})
RESTART_ONLY_KEYS: Tuple[str, ...] = (
    "schema_version",
    "mode",
    "game_mode",
    "survival",
    "survival_start",
    "survival_locked",
    "story_id",
    "story_choice_idx",
    "start_variant",
    "warfare_faction_slot",
    "warfare_start_idx",
    "place_id",
    "start_place_row",
    "min_difficulty",
    "created_at",
    "nonce",
)


def _is_windows_style_path(path: str) -> bool:
    return bool(
        (len(path) >= 2 and path[1] == ":" and path[0].isalpha())
        or path.startswith("\\\\")
        or ("\\" in path and "/" not in path)
    )


def default_launch_choices_path(env: Optional[Dict[str, str]] = None) -> str:
    """Return `%LOCALAPPDATA%\\FO4SF\\launch_choices.json` (or XDG state path off Windows)."""
    e = os.environ if env is None else env
    local = e.get("LOCALAPPDATA") or ""
    if local:
        mod = (
            ntpath
            if _is_windows_style_path(local)
            else (posixpath if local.startswith("/") else os.path)
        )
        return mod.join(local, "FO4SF", LAUNCH_CHOICES_FILENAME)
    state_home = e.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(state_home, "FO4SF", LAUNCH_CHOICES_FILENAME)


def _iter_subrecords(raw: memoryview, compressed: bool = False):
    data = zlib.decompress(bytes(raw[4:])) if compressed else raw
    pos = 0
    n = len(data)
    while pos + 6 <= n:
        sig = bytes(data[pos : pos + 4])
        sz = struct.unpack_from("<H", data, pos + 4)[0]
        pos += 6
        if sig == b"XXXX" and sz == 4 and pos + 4 <= n:
            big_sz = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            if pos + 6 <= n:
                sig = bytes(data[pos : pos + 4])
                pos += 6
                val = data[pos : pos + big_sz]
                pos += big_sz
                yield sig, val
            continue
        val = data[pos : pos + sz]
        pos += sz
        yield sig, val


def _edid_from_record(rec_body: memoryview, fl: int) -> str:
    for sig, val in _iter_subrecords(rec_body, bool(fl & 0x00040000)):
        if sig == b"EDID":
            return bytes(val).split(b"\0", 1)[0].decode("utf-8", "replace")
    return ""


def _cell_fields(rec_body: memoryview, fl: int) -> Tuple[str, Optional[bytes], Optional[Tuple[int, int]]]:
    edid = ""
    data_b: Optional[bytes] = None
    xy: Optional[Tuple[int, int]] = None
    for sig, val in _iter_subrecords(rec_body, bool(fl & 0x00040000)):
        if sig == b"EDID" and not edid:
            edid = bytes(val).split(b"\0", 1)[0].decode("utf-8", "replace")
        elif sig == b"DATA" and data_b is None:
            data_b = bytes(val)
        elif sig == b"XCLC" and xy is None and len(val) >= 8:
            xy = struct.unpack_from("<2i", val, 0)
    return edid, data_b, xy


def _scan_single_tes4_places(
    esm_path: str,
    markers: Set[str],
    interior_cells: Set[str],
    exterior_cells: Set[Tuple[int, int]],
) -> bool:
    """Scan one real TES4 plugin for persistent marker EDIDs and CELL coords in O(CELL+persistent) time."""
    try:
        size = os.path.getsize(esm_path)
    except OSError:
        return False
    if size < 48:
        return False
    with open(esm_path, "rb") as f:
        head = f.read(24)
        if len(head) < 24 or head[:4] != b"TES4":
            return False
        tes4_sz = struct.unpack_from("<I", head, 4)[0]
        if 24 + tes4_sz + 24 > size:
            return False
        f.seek(0)
        buf = memoryview(f.read())
    if bytes(buf[24 + tes4_sz : 24 + tes4_sz + 4]) != b"GRUP":
        return False

    def walk(start: int, end: int, in_wrld: bool, cur_gt: Optional[int]) -> None:
        off = start
        while off + 24 <= end:
            typ = bytes(buf[off : off + 4])
            if typ == b"GRUP":
                gs, _lbl, gt = struct.unpack_from("<4sI4si", buf, off)[1:4]
                if gs < 24 or off + gs > end:
                    break
                # Skip temporary Exterior/Interior child clusters (gt == 9) and non-spatial top groups.
                if gt == 9 or gt == 10:
                    off += gs
                    continue
                if gt == 0 and _lbl not in (b"CELL", b"WRLD"):
                    off += gs
                    continue
                walk(off + 24, off + gs, in_wrld or (_lbl == b"WRLD" and gt == 0), gt)
                off += gs
            else:
                sz, fl, _fid = struct.unpack_from("<III", buf, off + 4)
                rec_end = off + 24 + sz
                if rec_end > end:
                    break
                body = buf[off + 24 : rec_end]
                if typ == b"CELL":
                    edid, data_b, xy = _cell_fields(body, fl)
                    is_int = (
                        bool(fl & 0x00000001)
                        or (data_b is not None and len(data_b) >= 1 and bool(data_b[0] & 0x01))
                        or (not in_wrld and xy is None)
                    )
                    if is_int:
                        if edid:
                            interior_cells.add(edid)
                    elif xy is not None:
                        exterior_cells.add(xy)
                elif typ == b"REFR" and (bool(fl & 0x00000400) or cur_gt == 8):
                    edid = _edid_from_record(body, fl)
                    if edid:
                        markers.add(edid)
                off = rec_end

    walk(24 + tes4_sz, len(buf), False, None)
    return True


def scan_data_dir_places(
    data_dir: str,
    *,
    plugin_names: Optional[Iterable[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Inspect real FO4SF TES4 ESMs in `data_dir` for loaded markers, interior cells, and exterior cells.

    Returns `None` when `data_dir` holds no real parseable FO4SF TES4 plugin (e.g. unit-test stubs).
    """
    if not data_dir or not os.path.isdir(data_dir):
        return None
    targets = (
        tuple(plugin_names)
        if plugin_names is not None
        else ("FO4TerrainCore.esm", "FO4Port.esm", "FO4SFPrewar.esm", "FO4SFPrewar_Sanctuary.esm")
    )
    markers: Set[str] = set()
    interior_cells: Set[str] = set()
    exterior_cells: Set[Tuple[int, int]] = set()
    parsed: List[str] = []
    present: Set[str] = set()
    for name in os.listdir(data_dir):
        if name.casefold().endswith((".esm", ".esp", ".esl")):
            present.add(name.casefold())
    for want in targets:
        p = os.path.join(data_dir, want)
        if os.path.isfile(p) and _scan_single_tes4_places(p, markers, interior_cells, exterior_cells):
            parsed.append(want)
    if not parsed:
        return None
    return {
        "parsed_plugins": parsed,
        "present_plugins": present,
        "markers": markers,
        "interior_cells": interior_cells,
        "exterior_cells": exterior_cells,
    }


def _row_meta_map(path: str = sp.START_PLACES_JSON) -> Dict[str, Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    out: Dict[str, Dict[str, Any]] = {}
    for entry in raw.get("places", ()):
        pid = str(entry.get("id") or "").strip()
        if pid:
            out[pid] = entry
    return out


def known_start_place_ids(start_places_path: str = sp.START_PLACES_JSON) -> Set[str]:
    """Return every start-place id defined in `start_places.json`."""
    return set(_row_meta_map(start_places_path))


def _resolve_session_filters(
    *,
    starfield_dir: str = "",
    entries: Optional[Sequence[Tuple[str, bool]]] = None,
    loaded_plugins: Optional[Iterable[str]] = None,
    loaded_places: Optional[Dict[str, Any]] = None,
    strict_session: bool = False,
) -> Tuple[Optional[Set[str]], Optional[Dict[str, Any]], bool]:
    data_dir = os.path.join(starfield_dir, "Data") if starfield_dir else ""
    scanned_places = loaded_places if loaded_places is not None else scan_data_dir_places(data_dir)
    if loaded_plugins is not None:
        eff_plugins: Optional[Set[str]] = {str(p).strip().casefold() for p in loaded_plugins if str(p).strip()}
    else:
        eff_plugins = active_plugins_from_entries(entries, data_dir=data_dir)
        if eff_plugins is None and strict_session and scanned_places is not None:
            present = scanned_places.get("present_plugins")
            if present is not None:
                eff_plugins = {str(p).strip().casefold() for p in present if str(p).strip()}

    has_content_entries = bool(
        entries and any(str(name).strip().casefold() in CONTENT_PLUGINS for name, _ticked in entries)
    )
    enforce_plugins = (
        strict_session
        or loaded_plugins is not None
        or (eff_plugins is not None and (scanned_places is not None or has_content_entries))
    )
    places_arg = scanned_places
    if strict_session and places_arg is None:
        places_arg = {"markers": set(), "interior_cells": set(), "exterior_cells": set()}
    return eff_plugins, places_arg, enforce_plugins


def filtered_places_for_session(
    *,
    mode: Optional[str] = None,
    starfield_dir: str = "",
    entries: Optional[Sequence[Tuple[str, bool]]] = None,
    loaded_plugins: Optional[Iterable[str]] = None,
    loaded_places: Optional[Dict[str, Any]] = None,
    start_places_path: str = sp.START_PLACES_JSON,
    strict_session: bool = False,
) -> Tuple[List[sp.StartPlaceRow], Dict[str, str], Optional[Set[str]], Optional[Dict[str, Any]]]:
    """Evaluate valid available start places strictly from loaded plugins & places for `mode`."""
    eff_plugins, places_arg, enforce_plugins = _resolve_session_filters(
        starfield_dir=starfield_dir,
        entries=entries,
        loaded_plugins=loaded_plugins,
        loaded_places=loaded_places,
        strict_session=strict_session,
    )
    all_rows = sp.load_start_places(start_places_path)
    avail_rows, reasons = evaluate_start_places(
        all_rows,
        start_places_path=start_places_path,
        mode=mode,
        loaded_plugins=eff_plugins if enforce_plugins else None,
        loaded_places=places_arg,
    )
    return avail_rows, reasons, eff_plugins, places_arg


def available_place_options(
    mode: str,
    *,
    variant: str = "",
    starfield_dir: str = "",
    entries: Optional[Sequence[Tuple[str, bool]]] = None,
    loaded_plugins: Optional[Iterable[str]] = None,
    loaded_places: Optional[Dict[str, Any]] = None,
    start_places_path: str = sp.START_PLACES_JSON,
    strict_session: bool = False,
) -> List[str]:
    """Return `[""] + [filtered place ids]` for the launcher UI / CLI."""
    mode_norm = str(mode or "story").strip().lower()
    if mode_norm not in MODE_CHOICES:
        return [""]
    variant_norm = str(variant or "").strip().lower()
    avail_rows, _reasons, _eff, _places = filtered_places_for_session(
        mode=mode_norm,
        starfield_dir=starfield_dir,
        entries=entries,
        loaded_plugins=loaded_plugins,
        loaded_places=loaded_places,
        start_places_path=start_places_path,
        strict_session=strict_session,
    )
    if mode_norm == "story" and variant_norm in VARIANT_CHOICES:
        avail_rows = [
            r for r in avail_rows
            if str(getattr(r, "start_variant", "") or "").strip().lower() == variant_norm
        ]
    return [""] + [r.id for r in avail_rows]


def unavailable_place_entries(
    mode: Optional[str] = None,
    *,
    starfield_dir: str = "",
    entries: Optional[Sequence[Tuple[str, bool]]] = None,
    loaded_plugins: Optional[Iterable[str]] = None,
    loaded_places: Optional[Dict[str, Any]] = None,
    start_places_path: str = sp.START_PLACES_JSON,
    strict_session: bool = False,
) -> List[Dict[str, str]]:
    """Return unavailable/locked rows for `mode` with id, name, mode, start_variant, and exact reason."""
    mode_norm = None if mode is None else str(mode or "story").strip().lower()
    if mode_norm is not None and mode_norm not in MODE_CHOICES:
        return []
    all_rows = sp.load_start_places(start_places_path)
    _avail, reasons, _eff, _places = filtered_places_for_session(
        mode=mode_norm,
        starfield_dir=starfield_dir,
        entries=entries,
        loaded_plugins=loaded_plugins,
        loaded_places=loaded_places,
        start_places_path=start_places_path,
        strict_session=strict_session,
    )
    out: List[Dict[str, str]] = []
    for row in all_rows:
        if mode_norm is not None and row.mode != mode_norm:
            continue
        reason = reasons.get(row.id)
        if not reason:
            continue
        out.append({
            "id": row.id,
            "name": row.name,
            "mode": row.mode,
            "story_id": row.story_id,
            "faction_label": row.faction_label,
            "start_variant": str(getattr(row, "start_variant", "") or ""),
            "reason": reason,
        })
    return out


def settings_problem(
    values: Dict[str, Any],
    *,
    start_places_path: str = sp.START_PLACES_JSON,
    warfare_starts_path: str = ws.WARFARE_STARTS_JSON,
) -> str:
    """Return a refusal message when `start.mode` / `start.place` cannot resolve cleanly, else `""`."""
    folder = str(values.get("instance") or values.get("starfield") or "").strip()
    data_dir = os.path.join(folder, "Data") if folder else ""
    scanned = scan_data_dir_places(data_dir)
    try:
        resolve_and_build_launch_choices(
            values,
            starfield_dir=folder if scanned is not None else "",
            loaded_places=scanned,
            start_places_path=start_places_path,
            warfare_starts_path=warfare_starts_path,
            strict_session=False,
        )
    except ValueError as exc:
        return str(exc)
    return ""


def active_plugins_from_entries(
    entries: Optional[Sequence[Tuple[str, bool]]],
    *,
    data_dir: str = "",
) -> Optional[Set[str]]:
    """Return casefolded active plugins from `Plugins.txt` entries, intersecting real Data files when present."""
    if entries is None:
        return None
    active = {str(name).strip().casefold() for name, ticked in entries if ticked and str(name).strip()}
    if not active:
        return set()
    if data_dir and os.path.isdir(data_dir):
        on_disk = {
            fn.casefold()
            for fn in os.listdir(data_dir)
            if fn.casefold().endswith((".esm", ".esp", ".esl")) and os.path.isfile(os.path.join(data_dir, fn))
        }
        has_real_fo4sf = any(
            os.path.isfile(os.path.join(data_dir, nm)) and os.path.getsize(os.path.join(data_dir, nm)) >= 48
            for nm in ("FO4TerrainCore.esm", "FO4Port.esm", "FO4SFNewGame.esm")
        )
        if has_real_fo4sf:
            active = {p for p in active if p in on_disk}
        if "starfield.esm" in on_disk:
            active.add("starfield.esm")
    return active


def evaluate_start_places(
    rows: Optional[Sequence[sp.StartPlaceRow]] = None,
    *,
    start_places_path: str = sp.START_PLACES_JSON,
    mode: Optional[str] = None,
    loaded_plugins: Optional[Iterable[str]] = None,
    loaded_places: Optional[Dict[str, Any]] = None,
    allow_story_ids: Sequence[str] = ALLOWED_STORY_IDS,
) -> Tuple[List[sp.StartPlaceRow], Dict[str, str]]:
    """Validate and filter start rows strictly from loaded plugins & loaded places.

    Returns `(available_rows, unavailable_reasons_by_id)`.
    """
    all_rows = list(sp.load_start_places(start_places_path) if rows is None else rows)
    meta = _row_meta_map(start_places_path) if os.path.isfile(start_places_path) else {}
    plugin_set = None if loaded_plugins is None else {str(p).strip().casefold() for p in loaded_plugins if str(p).strip()}
    allow_story = set(allow_story_ids)
    mode_norm = None if mode is None else str(mode).strip().lower()
    if mode_norm is not None and mode_norm not in MODE_CHOICES:
        raise ValueError(f"start.mode: expected 'story' or 'warfare', got {mode!r}")

    avail: List[sp.StartPlaceRow] = []
    reasons: Dict[str, str] = {}

    for row in all_rows:
        if mode_norm is not None and row.mode != mode_norm:
            continue
        extra = meta.get(row.id, {})
        if not row.available:
            reasons[row.id] = row.unavailable_reason or "Row marked unavailable in start_places.json"
            continue
        if row.mode == "story" and row.id not in allow_story:
            reasons[row.id] = f"Story row {row.id!r} is locked until Task 6 (only {', '.join(sorted(allow_story))} allowed)"
            continue

        req_plugins = [
            str(p).strip()
            for p in (extra.get("required_plugins") or row.required_plugins or (row.plugin,))
            if str(p).strip()
        ]
        if plugin_set is not None:
            missing_plugins = [p for p in req_plugins if p.casefold() not in plugin_set]
            if missing_plugins:
                reasons[row.id] = f"Missing loaded plugin(s): {', '.join(missing_plugins)}"
                continue

        if loaded_places is not None:
            markers = loaded_places.get("markers")
            interiors = loaded_places.get("interior_cells")
            exteriors = loaded_places.get("exterior_cells")
            anchor_edid = str(extra.get("anchor_edid") or row.anchor_edid or row.marker_edid or "").strip()
            if row.is_interior:
                if interiors is not None and row.space not in interiors:
                    reasons[row.id] = f"Interior cell {row.space!r} is not loaded"
                    continue
                if row.marker_source != "vault_anchor" and markers is not None and anchor_edid and anchor_edid not in markers:
                    reasons[row.id] = f"Interior marker {anchor_edid!r} is not loaded"
                    continue
            else:
                if markers is not None and anchor_edid and anchor_edid not in markers:
                    reasons[row.id] = f"Exterior anchor/marker {anchor_edid!r} is not loaded"
                    continue
                raw_cell = extra.get("cell") if extra.get("cell") is not None else row.cell
                if exteriors is not None and isinstance(raw_cell, (list, tuple)) and len(raw_cell) == 2:
                    cxy = (int(raw_cell[0]), int(raw_cell[1]))
                    if cxy not in exteriors:
                        reasons[row.id] = f"Exterior cell {cxy} is not loaded"
                        continue

        avail.append(row)

    return avail, reasons


def resolve_and_build_launch_choices(
    values: Dict[str, Any],
    *,
    starfield_dir: str = "",
    entries: Optional[Sequence[Tuple[str, bool]]] = None,
    loaded_plugins: Optional[Iterable[str]] = None,
    loaded_places: Optional[Dict[str, Any]] = None,
    start_places_path: str = sp.START_PLACES_JSON,
    warfare_starts_path: str = ws.WARFARE_STARTS_JSON,
    nonce: str = "",
    created_at: Optional[int] = None,
    strict_session: bool = False,
) -> Dict[str, Any]:
    """Validate pre-launch choices (`start.mode`, `start.variant`, `start.survival`, `start.place`) and build `launch_choices.json`."""
    mode = str(values.get("start.mode", "story") or "story").strip().lower()
    if mode not in MODE_CHOICES:
        raise ValueError(f"start.mode: {mode!r} is not one of story, warfare")
    requested_variant = str(values.get("start.variant", "") or "").strip().lower()
    if requested_variant not in ("",) + VARIANT_CHOICES:
        raise ValueError(f"start.variant: {requested_variant!r} is not one of '', normal, quick")
    if mode != "story" and requested_variant:
        raise ValueError(f"start.variant {requested_variant!r} is only valid for mode='story', not mode={mode!r}")
    survival = bool(values.get("start.survival", False))
    requested_place = str(values.get("start.place", "") or "").strip()

    all_rows = sp.load_start_places(start_places_path)
    eff_plugins, places_arg, enforce_plugins = _resolve_session_filters(
        starfield_dir=starfield_dir,
        entries=entries,
        loaded_plugins=loaded_plugins,
        loaded_places=loaded_places,
        strict_session=strict_session,
    )
    avail_for_mode, reasons = evaluate_start_places(
        all_rows,
        start_places_path=start_places_path,
        mode=mode,
        loaded_plugins=eff_plugins if enforce_plugins else None,
        loaded_places=places_arg,
    )

    if survival:
        known_plugin_set = eff_plugins
        if known_plugin_set is None and isinstance(places_arg, dict) and places_arg.get("present_plugins") is not None:
            known_plugin_set = {
                str(p).strip().casefold() for p in places_arg.get("present_plugins", ()) if str(p).strip()
            }
        if enforce_plugins:
            if known_plugin_set is None or HARDCORE_PLUGIN.casefold() not in known_plugin_set:
                raise ValueError(f"start.survival: --survival on requires {HARDCORE_PLUGIN} to be present and active")

    if not avail_for_mode:
        why = "; ".join(f"{k}: {v}" for k, v in sorted(reasons.items())) or f"no available {mode} start places"
        raise ValueError(f"start.place ({mode}): no valid start row for loaded plugins/places ({why})")

    if requested_place:
        matched = [r for r in avail_for_mode if r.id == requested_place]
        if not matched:
            all_by_id = {r.id: r for r in all_rows}
            row_info = all_by_id.get(requested_place)
            if row_info is None:
                raise ValueError(f"start.place: unknown start place {requested_place!r}")
            if row_info.mode != mode:
                raise ValueError(f"start.place {requested_place!r} is for mode={row_info.mode!r}, not mode={mode!r}")
            why = reasons.get(requested_place) or row_info.unavailable_reason or "plugins or places not loaded"
            raise ValueError(f"start.place {requested_place!r} is unavailable: {why}")
        chosen = matched[0]
        if mode == "story" and requested_variant:
            row_variant = str(getattr(chosen, "start_variant", "") or "").strip().lower()
            if row_variant != requested_variant:
                raise ValueError(
                    f"start.variant {requested_variant!r} is incompatible with start.place {chosen.id!r} "
                    f"(variant={row_variant!r})"
                )
    elif mode == "story" and requested_variant:
        matching_var = [
            r for r in avail_for_mode
            if str(getattr(r, "start_variant", "") or "").strip().lower() == requested_variant
        ]
        if not matching_var:
            why = "; ".join(
                f"{r.id}: {reasons.get(r.id) or r.unavailable_reason or 'unavailable'}"
                for r in all_rows
                if r.mode == "story"
                and str(getattr(r, "start_variant", "") or "").strip().lower() == requested_variant
            ) or f"no available story start for variant={requested_variant!r}"
            raise ValueError(f"start.variant ({requested_variant}): no valid story start for loaded plugins/places ({why})")
        chosen = matching_var[0]
    else:
        chosen = avail_for_mode[0]

    if enforce_plugins or places_arg is not None:
        canonical_avail, _all_reasons = evaluate_start_places(
            all_rows,
            start_places_path=start_places_path,
            mode=None,
            loaded_plugins=eff_plugins if enforce_plugins else None,
            loaded_places=places_arg,
            allow_story_ids=ALLOWED_STORY_IDS,
        )
    else:
        canonical_avail = [r for r in all_rows if r.available and (r.mode != "story" or r.id in ALLOWED_STORY_IDS)]
    start_place_row = next((i for i, r in enumerate(canonical_avail) if r.id == chosen.id), 0)

    wf_rows = ws.load_warfare_starts(warfare_starts_path)
    wf_idx = -1
    if chosen.mode == "warfare":
        wf_key = chosen.warfare_key or chosen.id
        wf_idx = next((i for i, w in enumerate(wf_rows) if w.key == wf_key), -1)
        if wf_idx < 0:
            raise ValueError(f"start.place {chosen.id!r}: warfare_key {wf_key!r} missing from warfare_starts.json")

    story_choices = sp.available_story_choices(canonical_avail)
    story_choice_idx = -1
    start_variant = "none"
    if chosen.mode == "story":
        story_choice_idx = next((i for i, (sid, _lbl) in enumerate(story_choices) if sid == chosen.story_id), 0)
        start_variant = str(getattr(chosen, "start_variant", "") or "").strip().lower()
        if start_variant not in VARIANT_CHOICES:
            raise ValueError(f"start.place {chosen.id!r}: invalid story start_variant {start_variant!r}")

    surv_i = 1 if survival else 0
    nonce_str = str(nonce or "").strip() or uuid.uuid4().hex[:16]
    created_epoch = int(time.time()) if created_at is None else int(created_at)
    return {
        "schema_version": LAUNCH_CHOICES_SCHEMA_VERSION,
        "mode": chosen.mode,
        "game_mode": 1 if chosen.mode == "story" else 2,
        "survival": survival,
        "survival_start": surv_i,
        "survival_locked": surv_i if chosen.mode == "warfare" else 0,
        "story_id": chosen.story_id if chosen.mode == "story" else "none",
        "story_choice_idx": story_choice_idx,
        "start_variant": start_variant,
        "warfare_faction_slot": chosen.faction_slot if chosen.mode == "warfare" else -1,
        "warfare_start_idx": wf_idx,
        "place_id": chosen.id,
        "start_place_row": start_place_row,
        "min_difficulty": int(chosen.min_difficulty),
        "created_at": created_epoch,
        "nonce": nonce_str,
    }


def write_launch_choices(path: str, payload: Dict[str, Any]) -> str:
    """Atomically write `launch_choices.json` (`.tmp` + `fsync` + `os.replace`)."""
    bad = set(payload) - set(RESTART_ONLY_KEYS)
    if bad:
        raise ValueError(f"launch_choices payload contains non-restart keys: {sorted(bad)}")
    if not str(payload.get("nonce") or "").strip():
        raise ValueError("launch_choices payload requires a non-empty nonce")
    if int(payload.get("created_at") or 0) <= 0:
        raise ValueError("launch_choices payload requires a positive created_at timestamp")
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return path


def read_launch_choices(path: str) -> Optional[Dict[str, Any]]:
    """Read `launch_choices.json`, returning `None` when absent."""
    if not path or not os.path.isfile(path):
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))
