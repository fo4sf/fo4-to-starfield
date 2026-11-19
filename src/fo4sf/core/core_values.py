"""Single shared value store contract (`FO4SFCoreValues.esm`).

Loads `core_values.json` as the sole source of FormIDs and EditorIDs for
S.P.E.C.I.A.L., the 13 Fallout skills, karma, radiation, hardcore survival
meters, the shared stimpak, and the test-mode gate. Every C# writer, Papyrus
script, and Python mirror derives its shared IDs from this table.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple

CORE_VALUES_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "core_values.json")
CORE_VALUES_PLUGIN = "FO4SFCoreValues.esm"

START_MODE_GLOB_EDIDS: Tuple[str, ...] = (
    "FO4SF_GameMode",
    "FO4SF_SurvivalStart",
    "FO4SF_SurvivalLocked",
    "FO4SF_StartDifficulty",
    "FO4SF_WarfareFaction",
    "FO4SF_WarfareStartIndex",
    "FO4SF_StartChoiceDone",
    "FO4SF_StartNeutralSpot",
    "FO4SF_StoryLine",
    "FO4SF_StartPlaceRow",
)


@dataclass(frozen=True)
class CoreValueRecord:
    form_id: int
    record_type: str
    edid: str
    name: str = ""
    abbr: str = ""
    default: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    flags: Tuple[str, ...] = ()
    items: Tuple[str, ...] = ()
    effect: str = ""
    constant: bool = False


def load_core_values(path: str = CORE_VALUES_JSON) -> Tuple[str, int, Tuple[CoreValueRecord, ...]]:
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)
    plugin = str(raw["plugin"])
    next_id = int(str(raw["next_form_id"]), 16)
    records: List[CoreValueRecord] = []
    seen_ids: Dict[int, str] = {}
    seen_edids: Dict[str, int] = {}
    for entry in raw["records"]:
        fid = int(str(entry["id"]), 16)
        edid = str(entry["edid"])
        rtype = str(entry["type"])
        if fid >= next_id:
            raise ValueError(f"FormID 0x{fid:06X} ({edid}) >= next_form_id 0x{next_id:06X}")
        if fid in seen_ids:
            raise ValueError(f"Duplicate FormID 0x{fid:06X}: {seen_ids[fid]} vs {edid}")
        if edid.lower() in seen_edids:
            raise ValueError(f"Duplicate EditorID {edid}")
        seen_ids[fid] = edid
        seen_edids[edid.lower()] = fid
        records.append(
            CoreValueRecord(
                form_id=fid,
                record_type=rtype,
                edid=edid,
                name=str(entry.get("name", "")),
                abbr=str(entry.get("abbr", "")),
                default=float(entry.get("default", 0.0)),
                min_val=float(entry.get("min", 0.0)),
                max_val=float(entry.get("max", 0.0)),
                flags=tuple(entry.get("flags", ())),
                items=tuple(entry.get("items", ())),
                effect=str(entry.get("effect", "")),
                constant=bool(entry.get("constant", False)),
            )
        )
    return plugin, next_id, tuple(records)


def core_values_by_edid(path: str = CORE_VALUES_JSON) -> Dict[str, CoreValueRecord]:
    _, _, records = load_core_values(path)
    return {rec.edid: rec for rec in records}


def core_values_by_id(path: str = CORE_VALUES_JSON) -> Dict[int, CoreValueRecord]:
    _, _, records = load_core_values(path)
    return {rec.form_id: rec for rec in records}


def core_form_id(edid: str, path: str = CORE_VALUES_JSON) -> int:
    by_edid = core_values_by_edid(path)
    if edid not in by_edid:
        raise KeyError(f"{edid} is not defined in {CORE_VALUES_PLUGIN}")
    return by_edid[edid].form_id
