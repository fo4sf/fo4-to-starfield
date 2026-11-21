"""Canonical Pip-Boy mission objective catalog & TSV generator for A5.

Generates and validates `Data/SFSE/Plugins/FO4SFPipboyQuestObjectives.tsv`, which
`FO4SFPipboyMenu.dll` (`PipboyMap::LoadQuestObjectiveCatalog`) loads alongside
`FO4SFPipboyMapMarkers.tsv`.

This table pairs every converted Fallout 4 mission quest objective
`(plugin, quest_local_hex, objective_num)` with:
  - exact Commonwealth FO4 world coordinates `(x_fo4, y_fo4)` matching
    `FO4SFPipboyMapMarkers.tsv` (`pipboy_map_store.py`),
  - location label, and
  - clean-room display fallback text (used only when live `BGSQuestObjective`
    string-pool decoding returns `"Objective <n>"`).

A4 missions (*The First Step*, *Jewel of the Commonwealth*) and later quests
can extend `FO4SFPipboyQuestObjectives.tsv` at stage time without rebuilding
`FO4SFPipboyMenu.dll`.
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pipboy_map_store  # noqa: E402

QUEST_OBJECTIVES_TSV_NAME = "FO4SFPipboyQuestObjectives.tsv"
QUEST_OBJECTIVES_HEADER = (
    "plugin\tquest_local_hex\tobjective_num\tx_fo4\ty_fo4\tlocation_label\tfallback_text"
)


class MissionCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class MissionObjectiveRow:
    plugin: str
    quest_local_id: int
    objective_num: int
    x_fo4: float
    y_fo4: float
    location_label: str
    fallback_text: str


# Canonical converted Track-1 missions (matches SeedDefaultQuestObjectiveCatalog in pipboy_map.cpp
# and exact marker positions from FO4SFPipboyMapMarkers.tsv)
CANONICAL_MISSION_OBJECTIVES: tuple[MissionObjectiveRow, ...] = (
    MissionObjectiveRow(
        plugin="FO4SFNewGame.esm",
        quest_local_id=0x000800,
        objective_num=10,
        x_fo4=-89271.98,
        y_fo4=91369.30,
        location_label="Vault 111",
        fallback_text="Leave Vault 111",
    ),
    MissionObjectiveRow(
        plugin="FO4SFMission.esm",
        quest_local_id=0x000816,
        objective_num=10,
        x_fo4=-80768.19,
        y_fo4=88174.80,
        location_label="Sanctuary Hills",
        fallback_text="Speak with Codsworth",
    ),
    MissionObjectiveRow(
        plugin="FO4SFMission.esm",
        quest_local_id=0x000800,
        objective_num=10,
        x_fo4=-60286.01,
        y_fo4=72977.79,
        location_label="Concord",
        fallback_text="Investigate Concord",
    ),
    MissionObjectiveRow(
        plugin="FO4SFMission.esm",
        quest_local_id=0x000800,
        objective_num=20,
        x_fo4=-57011.77,
        y_fo4=70392.14,
        location_label="Museum of Freedom",
        fallback_text="Clear the hostiles outside the museum",
    ),
    MissionObjectiveRow(
        plugin="FO4SFMission.esm",
        quest_local_id=0x000800,
        objective_num=30,
        x_fo4=-57011.77,
        y_fo4=70392.14,
        location_label="Museum of Freedom",
        fallback_text="Speak with Preston Garvey",
    ),
    MissionObjectiveRow(
        plugin="FO4SFMission.esm",
        quest_local_id=0x000800,
        objective_num=35,
        x_fo4=-57011.77,
        y_fo4=70392.14,
        location_label="Museum of Freedom",
        fallback_text="Speak with Preston Garvey",
    ),
    MissionObjectiveRow(
        plugin="FO4SFMission.esm",
        quest_local_id=0x000817,
        objective_num=10,
        x_fo4=-80768.19,
        y_fo4=88174.80,
        location_label="Sanctuary Hills",
        fallback_text="Activate the Sanctuary workbench",
    ),
    # A4 reserved FormIDs (0x000A20 The First Step, 0x000A50 Jewel of the Commonwealth)
    MissionObjectiveRow(
        plugin="FO4SFMission.esm",
        quest_local_id=0x000A20,
        objective_num=10,
        x_fo4=-22154.77,
        y_fo4=89056.08,
        location_label="Tenpines Bluff",
        fallback_text="Talk to the settlers at Tenpines Bluff",
    ),
    MissionObjectiveRow(
        plugin="FO4SFMission.esm",
        quest_local_id=0x000A20,
        objective_num=20,
        x_fo4=-34808.25,
        y_fo4=32128.49,
        location_label="Corvega Assembly Plant",
        fallback_text="Clear the raiders at Corvega Assembly Plant",
    ),
    MissionObjectiveRow(
        plugin="FO4SFMission.esm",
        quest_local_id=0x000A50,
        objective_num=10,
        x_fo4=-16384.00,
        y_fo4=-27852.80,
        location_label="Diamond City",
        fallback_text="Go to Diamond City",
    ),
)

# Exact Commonwealth reference coordinates for upcoming A4 story missions
# (The First Step: Tenpines Bluff / Corvega; Jewel of the Commonwealth: Diamond City).
A4_KNOWN_LANDMARK_COORDS: dict[str, tuple[float, float]] = {
    "Vault 111": (-89271.98, 91369.30),
    "Sanctuary Hills": (-80768.19, 88174.80),
    "Red Rocket Truck Stop": (-69248.00, 80256.00),
    "Concord": (-60286.01, 72977.79),
    "Museum of Freedom": (-57011.77, 70392.14),
    "Tenpines Bluff": (-22154.77, 89056.08),
    "Corvega Assembly Plant": (-34808.25, 32128.49),
    "Diamond City": (round(pipboy_map_store.DIAMOND_CITY_ONAM[1], 2), round(pipboy_map_store.DIAMOND_CITY_ONAM[2], 2)),
}


def validate_row(row: MissionObjectiveRow) -> None:
    if not row.plugin or any(ch in row.plugin for ch in ("\t", "\r", "\n")):
        raise MissionCatalogError(f"invalid plugin name: {row.plugin!r}")
    if not (0 <= row.quest_local_id <= 0xFFFFFF):
        raise MissionCatalogError(f"quest_local_id out of 24-bit range: {row.quest_local_id:#x}")
    if not (0 <= row.objective_num <= 0xFFFF):
        raise MissionCatalogError(f"objective_num out of 16-bit range: {row.objective_num}")
    if not (math.isfinite(row.x_fo4) and math.isfinite(row.y_fo4)):
        raise MissionCatalogError(f"non-finite coordinates: ({row.x_fo4}, {row.y_fo4})")
    nw_x, nw_y = pipboy_map_store.COMMONWEALTH_NW
    ne_x, _ = pipboy_map_store.COMMONWEALTH_NE
    _, sw_y = pipboy_map_store.COMMONWEALTH_SW
    if not (nw_x <= row.x_fo4 <= ne_x and sw_y <= row.y_fo4 <= nw_y):
        raise MissionCatalogError(
            f"coordinates ({row.x_fo4}, {row.y_fo4}) outside Commonwealth map bounds "
            f"[{nw_x}..{ne_x}] x [{sw_y}..{nw_y}]"
        )
    if not row.location_label or "\t" in row.location_label:
        raise MissionCatalogError(f"invalid location_label: {row.location_label!r}")
    if not row.fallback_text or "\t" in row.fallback_text:
        raise MissionCatalogError(f"invalid fallback_text: {row.fallback_text!r}")


def render_quest_objectives_tsv(rows: Sequence[MissionObjectiveRow] = CANONICAL_MISSION_OBJECTIVES) -> str:
    seen: set[tuple[str, int, int]] = set()
    lines = [QUEST_OBJECTIVES_HEADER]
    for row in rows:
        validate_row(row)
        key = (row.plugin.casefold(), row.quest_local_id, row.objective_num)
        if key in seen:
            raise MissionCatalogError(
                f"duplicate quest objective entry: {row.plugin}:{row.quest_local_id:06X} obj {row.objective_num}"
            )
        seen.add(key)
        lines.append(
            f"{row.plugin}\t{row.quest_local_id:06X}\t{row.objective_num}\t"
            f"{row.x_fo4:.2f}\t{row.y_fo4:.2f}\t{row.location_label}\t{row.fallback_text}"
        )
    return "\n".join(lines) + "\n"


def parse_quest_objectives_tsv(text: str) -> List[MissionObjectiveRow]:
    out: List[MissionObjectiveRow] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip("\r")
        if not line or line.startswith("#"):
            continue
        if line_no == 1 and line.startswith("plugin\t"):
            continue
        cols = line.split("\t")
        if len(cols) < 7:
            raise MissionCatalogError(f"line {line_no}: expected 7 columns, got {len(cols)}")
        row = MissionObjectiveRow(
            plugin=cols[0],
            quest_local_id=int(cols[1], 16) & 0xFFFFFF,
            objective_num=int(cols[2], 10),
            x_fo4=float(cols[3]),
            y_fo4=float(cols[4]),
            location_label=cols[5],
            fallback_text=cols[6],
        )
        validate_row(row)
        out.append(row)
    return out


def write_quest_objectives_tsv(
    out_path: os.PathLike | str,
    rows: Iterable[MissionObjectiveRow] = CANONICAL_MISSION_OBJECTIVES,
) -> Path:
    try:
        safe = Path(pipboy_map_store.refuse_unsafe_output_path(out_path))
    except pipboy_map_store.MapStoreError as exc:
        raise MissionCatalogError(str(exc)) from exc
    row_list = list(rows)
    payload = render_quest_objectives_tsv(row_list)
    safe.parent.mkdir(parents=True, exist_ok=True)
    safe.write_text(payload, encoding="utf-8", newline="\n")
    return safe


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write FO4SFPipboyQuestObjectives.tsv for A5.")
    ap.add_argument("--out", required=True, help="Destination TSV path (outside Git and game install)")
    args = ap.parse_args(argv)
    try:
        written = write_quest_objectives_tsv(args.out)
    except MissionCatalogError as exc:
        sys.stderr.write(f"pipboy_mission_catalog error: {exc}\n")
        return 1
    print(f"wrote {written} ({len(CANONICAL_MISSION_OBJECTIVES)} mission objectives)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
