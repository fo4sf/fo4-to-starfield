"""A7d Act II Glowing Sea & Molecular Level places/doors verifier (`MQ204`, `MQ205` bridge, `MQ206`).

Prototype, offline — verifies:
  1. FormID reservation `FO4SFMission.esm:0x000B10..0x000B6F` (`FO4SF_MQ204`=0x000B10,
     `FO4SF_MQ206`=0x000B30), strictly disjoint from `A1(d)` (`0x800..0x9FF`), `A4`
     (`0xA00..0xA7F`), `A7` (`0xA80..0xACF`), and `A7c` (`0xAD0..0xB0F`), fitting inside
     the `A5` Pip-Boy Act II scan window (`0x000800..0x000BFF`).
  2. Already-converted `interiors_b10` (`FO4Port.esm`, 269 interior CELLs) readiness & door
     audit for all 20 Act II interior cells — zero interior reconversion required — including
     the already-wired `PrydwenHull01` exterior load door (`0x0045AD` / marker `0x00E183` <->
     `FO4TerrainCore.esm:0x0A774D`), unwired exterior doors, internal two-way `XTEL` webs,
     and the 2 missing elevator/transition cells (`ElevTransHiTechInstitute` `0x0021A107`,
     `MassFusion02Trans` `0x0014FC9B`) plus 3 unneeded alias/storage cells.
  3. Optional read-only binary verification directly against a staged `FO4Port.esm` and
     `doors.json` via `fo4sf.planet.esm.Plugin` (zero writes, zero local drive paths).
  4. `W6` 4-axis reachability & Open-Mode dead-giver simulation for `FO4SF_MQ204` and
     `FO4SF_MQ206` (Track 1 13-plugin & Track 2 22-plugin + `W7` Open Mode).
  5. `A5`-compatible 7-column `FO4SFPipboyQuestObjectives.tsv` row generation with verified
     Commonwealth coordinates.
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

A1D_RESERVED_RANGE = (0x000800, 0x0009FF)
A4_RESERVED_RANGE = (0x000A00, 0x000A7F)
A7_RESERVED_RANGE = (0x000A80, 0x000ACF)
A7C_RESERVED_RANGE = (0x000AD0, 0x000B0F)
A7D_RESERVED_RANGE = (0x000B10, 0x000B6F)
A5_PIPBOY_ACT2_SCAN_RANGE = (0x000800, 0x000BFF)

# Canonical Fallout 4 Commonwealth map bounds (WRLD 0x0000003C MNAM outer cell edges)
COMMONWEALTH_X_BOUNDS = (-135168.0, 118784.0)
COMMONWEALTH_Y_BOUNDS = (-147456.0, 106496.0)

# Already-wired Prydwen exterior load door verified in interiors_b10/port/doors.json
PRYDWEN_WIRED_DOOR = {
    "src": "1E42ED:Fallout4.esm",
    "cell_edid": "FO4Port_PrydwenHull01",
    "cell_local_id": "003846",
    "interior_door": "0045AD",
    "marker": "00E183",
    "return_plugin": "FO4TerrainCore.esm",
    "return_id": "0A774D",
    "return_local": (725.353286, -144.392657, 79.542857),
    "return_merged": (-474.646714, -2844.392657, 79.542857),
}


@dataclass(frozen=True)
class StagedPlaceSpec:
    fo4_edid: str
    fo4_cell_id: int
    port_edid: str
    port_cell_id: int
    staged_ref_count: int
    mission_ids: Tuple[str, ...]
    expected_internal_xtel_count: int
    exterior_door_status: str  # "wired", "unwired", "internal_only", "scripted_relay"
    door_and_trigger_notes: Tuple[str, ...]


@dataclass(frozen=True)
class MissingCellSpec:
    fo4_edid: str
    fo4_cell_id: int
    port_edid: str
    category: str  # "transition_cell" or "alias_or_storage"
    mitigation: str


A7D_STAGED_PLACES: Tuple[StagedPlaceSpec, ...] = (
    StagedPlaceSpec(
        fo4_edid="GoodneighborTheMemoryDen",
        fo4_cell_id=0x00022884,
        port_edid="FO4Port_GoodneighborTheMemoryDen",
        port_cell_id=0x0100ED4A,
        staged_ref_count=1258,
        mission_ids=("FO4SF_MQ204", "FO4SF_MQ206"),
        expected_internal_xtel_count=0,
        exterior_door_status="unwired",
        door_and_trigger_notes=(
            "MQ203->MQ204 handoff (DoctorAmari 0x0009A680); exterior Goodneighbor door 0x00022886 unwired",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="MQ203KelloggsBrain",
        fo4_cell_id=0x000D393F,
        port_edid="FO4Port_MQ203KelloggsBrain",
        port_cell_id=0x0100F23E,
        staged_ref_count=1136,
        mission_ids=("FO4SF_MQ204",),
        expected_internal_xtel_count=4,
        exterior_door_status="internal_only",
        door_and_trigger_notes=(
            "4 internal XTEL links (0x0100F67D<->0x0100F67E, 0x0100F690<->0x0100F691); Virgil clue handoff into MQ204",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="VirgilsLab01",
        fo4_cell_id=0x00156C0E,
        port_edid="FO4Port_VirgilsLab01",
        port_cell_id=0x01069B10,
        staged_ref_count=539,
        mission_ids=("FO4SF_MQ204", "FO4SF_MQ206"),
        expected_internal_xtel_count=0,
        exterior_door_status="unwired",
        door_and_trigger_notes=(
            "Rocky Cave exterior mouth unwired; Virgil (0x0006B503) + MQ206SignalInterceptorPlans (0x0003FC16) + lab terminal fallback",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="SentinelSite01",
        fo4_cell_id=0x001614C5,
        port_edid="FO4Port_SentinelSite01",
        port_cell_id=0x010481E9,
        staged_ref_count=5245,
        mission_ids=("FO4SF_MQ204",),
        expected_internal_xtel_count=0,
        exterior_door_status="unwired",
        door_and_trigger_notes=(
            "Glowing Sea landmark interior; exterior hatch unwired",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="GlowingSeaPOIDB05Int",
        fo4_cell_id=0x001F4190,
        port_edid="FO4Port_GlowingSeaPOIDB05Int",
        port_cell_id=0x0106132A,
        staged_ref_count=161,
        mission_ids=("FO4SF_MQ204",),
        expected_internal_xtel_count=0,
        exterior_door_status="unwired",
        door_and_trigger_notes=(
            "Optional Glowing Sea waypoint interior; exterior hatch unwired",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="GlowingSeaPOIDB06Int",
        fo4_cell_id=0x001F59B9,
        port_edid="FO4Port_GlowingSeaPOIDB06Int",
        port_cell_id=0x01047339,
        staged_ref_count=1254,
        mission_ids=("FO4SF_MQ204",),
        expected_internal_xtel_count=0,
        exterior_door_status="unwired",
        door_and_trigger_notes=(
            "Optional Glowing Sea waypoint interior; exterior hatch unwired",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="GreenetechGenetics01",
        fo4_cell_id=0x0009656C,
        port_edid="FO4Port_GreenetechGenetics01",
        port_cell_id=0x01056471,
        staged_ref_count=6176,
        mission_ids=("FO4SF_MQ206",),
        expected_internal_xtel_count=2,
        exterior_door_status="unwired",
        door_and_trigger_notes=(
            "MQ205 Hunter/Hunted Courser Z2-47 (0x0004EFEC) chip site; 2 internal XTEL pairs to GreenetechGenetics02 (0x01057C86<->0x0104C992, 0x01057C92<->0x0104C99F); exterior door 0x00021EDD unwired",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="GreenetechGenetics02",
        fo4_cell_id=0x00164A88,
        port_edid="FO4Port_GreenetechGenetics02",
        port_cell_id=0x0104BE53,
        staged_ref_count=2887,
        mission_ids=("FO4SF_MQ206",),
        expected_internal_xtel_count=2,
        exterior_door_status="internal_only",
        door_and_trigger_notes=(
            "Upper floors of Greenetech Genetics; 2 internal XTEL pairs back to GreenetechGenetics01",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="OldNorthChurch01",
        fo4_cell_id=0x00066EF3,
        port_edid="FO4Port_OldNorthChurch01",
        port_cell_id=0x0103C790,
        staged_ref_count=1294,
        mission_ids=("FO4SF_MQ206",),
        expected_internal_xtel_count=1,
        exterior_door_status="unwired",
        door_and_trigger_notes=(
            "1 internal XTEL link to RailroadHQ01 (0x0103CC9E<->0x0103D18A); exterior church entrance unwired",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="RailroadHQ01",
        fo4_cell_id=0x00092B21,
        port_edid="FO4Port_RailroadHQ01",
        port_cell_id=0x0103CC9F,
        staged_ref_count=1264,
        mission_ids=("FO4SF_MQ206",),
        expected_internal_xtel_count=2,
        exterior_door_status="internal_only",
        door_and_trigger_notes=(
            "2 internal XTEL links (0x0103D18A<->OldNorthChurch01, 0x0103D189<->EscapeTunnel); TinkerTom (0x00045ACB), Desdemona (0x00045AD1), TinkerTomScanner (0x0016FF08)",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="RailroadHQEscapeTunnel",
        fo4_cell_id=0x00137C87,
        port_edid="FO4Port_RailroadHQEscapeTunnel",
        port_cell_id=0x0105AAB9,
        staged_ref_count=692,
        mission_ids=("FO4SF_MQ206",),
        expected_internal_xtel_count=1,
        exterior_door_status="unwired",
        door_and_trigger_notes=(
            "1 internal XTEL link to RailroadHQ01 (0x0105AD6C<->0x0103D189); exterior exit unwired",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="PrydwenHull01",
        fo4_cell_id=0x0005C92E,
        port_edid="FO4Port_PrydwenHull01",
        port_cell_id=0x01003846,
        staged_ref_count=3651,
        mission_ids=("FO4SF_MQ206",),
        expected_internal_xtel_count=2,
        exterior_door_status="wired",
        door_and_trigger_notes=(
            "ALREADY WIRED exterior load door: 0x0045AD (src 1E42ED:Fallout4.esm) / marker 0x00E183 <-> FO4TerrainCore.esm:0x0A774D (merged -474.65, -2844.39, 79.54); plus 2 internal XTEL links to PrydwenHull02/03",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="PrydwenHull02",
        fo4_cell_id=0x0014FC54,
        port_edid="FO4Port_PrydwenHull02",
        port_cell_id=0x0104026D,
        staged_ref_count=483,
        mission_ids=("FO4SF_MQ206",),
        expected_internal_xtel_count=1,
        exterior_door_status="internal_only",
        door_and_trigger_notes=(
            "Command Deck; 1 internal XTEL link to PrydwenHull01 (0x0104044C<->0x010045AA); BoSElderMaxson (0x000642B8)",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="PrydwenHull03",
        fo4_cell_id=0x0021630B,
        port_edid="FO4Port_PrydwenHull03",
        port_cell_id=0x0101099A,
        staged_ref_count=95,
        mission_ids=("FO4SF_MQ206",),
        expected_internal_xtel_count=1,
        exterior_door_status="internal_only",
        door_and_trigger_notes=(
            "Forecastle; 1 internal XTEL link to PrydwenHull01 (0x010109F9<->0x010045AE)",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="BostonAirportRuins01",
        fo4_cell_id=0x00084A56,
        port_edid="FO4Port_BostonAirportRuins01",
        port_cell_id=0x0102E5FA,
        staged_ref_count=4939,
        mission_ids=("FO4SF_MQ206",),
        expected_internal_xtel_count=0,
        exterior_door_status="unwired",
        door_and_trigger_notes=(
            "Adjacent to exterior BostonAirportWorkshopRef (0x000B3506) & BoSProctorIngram (0x000642B5); exterior door unwired",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="TheCastle01",
        fo4_cell_id=0x000ADEC8,
        port_edid="FO4Port_TheCastle01",
        port_cell_id=0x01047D16,
        staged_ref_count=1228,
        mission_ids=("FO4SF_MQ206",),
        expected_internal_xtel_count=0,
        exterior_door_status="unwired",
        door_and_trigger_notes=(
            "Optional Minutemen tunnels; primary Minutemen build site is exterior Sanctuary workbench (FO4TerrainCore.esm:0x005C50)",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="InstituteConcourse",
        fo4_cell_id=0x0002A199,
        port_edid="FO4Port_InstituteConcourse",
        port_cell_id=0x0103D252,
        staged_ref_count=5317,
        mission_ids=("FO4SF_MQ206",),
        expected_internal_xtel_count=6,
        exterior_door_status="scripted_relay",
        door_and_trigger_notes=(
            "MQ206 Stage 1200 relay MoveTo destination (no exterior load door in vanilla); 6 internal XTEL doors link BioScience, AdvSystems, Robotics, SRB, FEVlab/Reactor",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="InstituteAdvSystems",
        fo4_cell_id=0x0002A19A,
        port_edid="FO4Port_InstituteAdvSystems",
        port_cell_id=0x0103E757,
        staged_ref_count=306,
        mission_ids=("FO4SF_MQ206",),
        expected_internal_xtel_count=2,
        exterior_door_status="internal_only",
        door_and_trigger_notes=(
            "2 internal XTEL links (0x0103E88B<->InstituteConcourse, 0x0103E88A<->InstituteReactor)",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="InstituteBioScience",
        fo4_cell_id=0x0002A19C,
        port_edid="FO4Port_InstituteBioScience",
        port_cell_id=0x0103E890,
        staged_ref_count=943,
        mission_ids=("FO4SF_MQ206",),
        expected_internal_xtel_count=4,
        exterior_door_status="internal_only",
        door_and_trigger_notes=(
            "4 internal XTEL links (Concourse 0x0103EC3B<->0x0103E709 + FEVlab 0x0103EC3D/E<->0x0103F218/7)",
        ),
    ),
    StagedPlaceSpec(
        fo4_edid="InstituteSRB",
        fo4_cell_id=0x0002A19D,
        port_edid="FO4Port_InstituteSRB",
        port_cell_id=0x0103FB4B,
        staged_ref_count=207,
        mission_ids=("FO4SF_MQ206",),
        expected_internal_xtel_count=1,
        exterior_door_status="internal_only",
        door_and_trigger_notes=(
            "1 internal XTEL link to InstituteConcourse (0x0103FC1A<->0x0103E70B); paired with Robotics 0x0103FAB4, FEVlab 0x0103ED77, Reactor 0x0105D25A, Tunnel01 0x0105B3C0",
        ),
    ),
)

A7D_MISSING_CELLS: Tuple[MissingCellSpec, ...] = (
    MissingCellSpec(
        fo4_edid="ElevTransHiTechInstitute",
        fo4_cell_id=0x0021A107,
        port_edid="FO4Port_ElevTransHiTechInstitute",
        category="transition_cell",
        mitigation="Bypass elevator transition cell: use direct scripted MoveTo into FO4Port_InstituteConcourse (0x0103D252) and existing Concourse internal XTEL doors.",
    ),
    MissingCellSpec(
        fo4_edid="MassFusion02Trans",
        fo4_cell_id=0x0014FC9B,
        port_edid="FO4Port_MassFusion02Trans",
        category="transition_cell",
        mitigation="Act III Mass Fusion transition cell (not needed for MQ204/MQ206); bypass with direct floor-to-floor MoveTo when Act III is wired.",
    ),
    MissingCellSpec(
        fo4_edid="InstituteAliasCell",
        fo4_cell_id=0x0017CA01,
        port_edid="FO4Port_InstituteAliasCell",
        category="alias_or_storage",
        mitigation="Vanilla holding/alias storage cell; clean-room quests use persistent references in FO4SFMission.esm directly.",
    ),
    MissingCellSpec(
        fo4_edid="BostonAirportAliasCell",
        fo4_cell_id=0x00172297,
        port_edid="FO4Port_BostonAirportAliasCell",
        category="alias_or_storage",
        mitigation="Vanilla holding/alias storage cell; clean-room quests use persistent references in FO4SFMission.esm directly.",
    ),
    MissingCellSpec(
        fo4_edid="PackInRelayTower",
        fo4_cell_id=0x00191E94,
        port_edid="FO4Port_PackInRelayTower",
        category="alias_or_storage",
        mitigation="Vanilla PackIn prefab storage cell; not required at runtime.",
    ),
)

A7D_NEXT_MISSIONS: Tuple[Dict[str, Any], ...] = (
    {
        "quest_edid": "FO4SF_MQ204",
        "fo4_source_edid": "MQ204",
        "fo4_source_formid": 0x0006B500,
        "reserved_local_id": 0x000B10,
        "reserved_block": (0x000B10, 0x000B2F),
        "title": "The Glowing Sea",
        "start_stage": 10,
        "completion_stages": (200,),
        "stages": (10, 15, 20, 50, 200),
        "objectives": (
            (15, "Travel to the Glowing Sea and search for Virgil", -56092.31, -78515.81, "Edge of the Glowing Sea"),
            (20, "Locate Virgil in the Rocky Cave", -116397.02, -136728.78, "Rocky Cave"),
            (50, "Speak with Virgil inside his laboratory", -116397.02, -136728.78, "Virgil's Laboratory"),
        ),
        "transitions": (
            {"from": 10, "to": 15, "kind": "primary", "npc_gated": False, "label": "Quest initialized from MQ203 debrief or SW Glowing Sea proximity"},
            {"from": 15, "to": 20, "kind": "primary", "npc_gated": True, "label": "Crater of Atom clue from CoAMotherIsolde (0x0012DB48)"},
            {"from": 15, "to": 20, "kind": "open_mode", "npc_gated": False, "label": "GLOW-01 dead Isolde -> GlowingSea_COA_Virgil_Note (0x0019CBAE) or direct Rocky Cave arrival"},
            {"from": 20, "to": 50, "kind": "primary", "npc_gated": False, "label": "Enter FO4Port_VirgilsLab01 (0x01069B10) / approach cave mouth (MQ204CarMoved bypass)"},
            {"from": 50, "to": 200, "kind": "primary", "npc_gated": True, "label": "Virgil briefing (0x0006B503, IgnoreFriendlyHits=True) arms Courser / MQ206"},
            {"from": 50, "to": 200, "kind": "open_mode", "npc_gated": False, "label": "GLOW-04 dead/hostile Virgil -> lab terminal fallback arms Courser / MQ206"},
        ),
        "break_it_batches": (
            {"bat_id": "a7d1", "axis": "giver_dead", "target": "MotherIsolde dead (Virgil_Note fallback) + Virgil dead (lab terminal fallback)"},
            {"bat_id": "a7d2", "axis": "out_of_order", "target": "Direct Rocky Cave arrival bypassing Crater + save/reload & fast travel away"},
        ),
        "known_bugs": ("GLOW-01", "GLOW-02", "GLOW-03", "GLOW-04", "GLOW-05"),
    },
    {
        "quest_edid": "FO4SF_MQ206",
        "fo4_source_edid": "MQ206 (with MQ205 Hunter/Hunted bridge + MQ206Min/RR/BoS)",
        "fo4_source_formid": 0x000B1752,
        "reserved_local_id": 0x000B30,
        "reserved_block": (0x000B30, 0x000B6F),
        "title": "The Molecular Level",
        "start_stage": 10,
        "completion_stages": (1200,),
        "stages": (10, 20, 65, 100, 200, 300, 350, 700, 1000, 1200),
        "objectives": (
            (10, "Eliminate the Institute Courser at Greenetech Genetics and take the Courser Chip", -4120.00, -14800.00, "Greenetech Genetics"),
            (20, "Have the Courser Chip decoded at Railroad HQ", 32768.00, -4096.00, "Old North Church"),
            (100, "Return to Virgil for the Signal Interceptor plans", -116397.02, -136728.78, "Virgil's Laboratory"),
            (200, "Recruit a faction engineer or prepare solo assembly", -79872.00, 91648.00, "Sanctuary Hills"),
            (350, "Build and power the Signal Interceptor at the workbench", -79872.00, 91648.00, "Sanctuary Hills"),
            (1000, "Step onto the Signal Interceptor platform and relay to the Institute", 48073.90, -3331.96, "Boston Airport"),
        ),
        "transitions": (
            {"from": 10, "to": 20, "kind": "primary", "npc_gated": False, "label": "Defeat Courser Z2-47 (GreenetechGenetics01 0x01056471) and acquire Courser Chip (0x0006D0E8)"},
            {"from": 20, "to": 100, "kind": "primary", "npc_gated": True, "label": "Tinker Tom decodes Courser Chip inside RailroadHQ01 (0x0103CC9F)"},
            {"from": 20, "to": 65, "kind": "open_mode", "npc_gated": False, "label": "MOL-05 hostile/dead Railroad -> self-service decode branch on TinkerTomScanner (0x0016FF08)"},
            {"from": 65, "to": 100, "kind": "open_mode", "npc_gated": False, "label": "TinkerTomScanner grants CourserChipHolotape (0x0008575B) -> return to Virgil"},
            {"from": 100, "to": 200, "kind": "primary", "npc_gated": True, "label": "Virgil gives MQ206SignalInterceptorPlans (0x0003FC16)"},
            {"from": 100, "to": 200, "kind": "open_mode", "npc_gated": False, "label": "Dead Virgil -> loot SignalInterceptorPlans from lab desk/terminal in VirgilsLab01"},
            {"from": 200, "to": 300, "kind": "primary", "npc_gated": True, "label": "Select Sturges (Min), TinkerTom (RR), or ProctorIngram (BoS)"},
            {"from": 200, "to": 300, "kind": "open_mode", "npc_gated": False, "label": "MOL-03 all faction engineers dead -> Solo Open-Mode self-build (TeleporterFaction=0)"},
            {"from": 300, "to": 350, "kind": "primary", "npc_gated": False, "label": "Commit build site (Sanctuary 0x005C50 always allowed) and place Reflector Platform"},
            {"from": 350, "to": 700, "kind": "primary", "npc_gated": False, "label": "MOL-01 Workbench Assembly Menu builds Platform/Emitter/Dish/Console + power atomically"},
            {"from": 700, "to": 1000, "kind": "primary", "npc_gated": True, "label": "Engineer calibrates MQ206Console (0x00154AD6)"},
            {"from": 700, "to": 1000, "kind": "open_mode", "npc_gated": False, "label": "MOL-02 R10 watchdog / direct player console activation arms relay without AI pathing stall"},
            {"from": 1000, "to": 1200, "kind": "primary", "npc_gated": False, "label": "Step onto platform / activate relay -> direct MoveTo FO4Port_InstituteConcourse (0x0103D252)"},
        ),
        "break_it_batches": (
            {"bat_id": "a7d3", "axis": "giver_dead", "target": "Railroad wiped (TinkerTomScanner) + all 3 faction engineers dead (solo workbench build)"},
            {"bat_id": "a7d4", "axis": "save_reload", "target": "Mid-assembly reload + faction switch before stage 700 + relay MoveTo 0x0103D252"},
        ),
        "known_bugs": ("MOL-01", "MOL-02", "MOL-03", "MOL-04", "MOL-05"),
    },
)


def check_formid_disjointness() -> Dict[str, Any]:
    """Verify A7d FormID reservation (0xB10..0xB6F) is strictly disjoint from A1(d), A4, A7, and A7c."""
    issues: List[str] = []
    seen_ranges: List[Tuple[str, int, int]] = [
        ("A1d_Min00_Scenes", A1D_RESERVED_RANGE[0], A1D_RESERVED_RANGE[1]),
        ("A4_NextMissions", A4_RESERVED_RANGE[0], A4_RESERVED_RANGE[1]),
        ("A7_MQ104_MQ105", A7_RESERVED_RANGE[0], A7_RESERVED_RANGE[1]),
        ("A7c_MQ106_MQ203", A7C_RESERVED_RANGE[0], A7C_RESERVED_RANGE[1]),
    ]
    for m in A7D_NEXT_MISSIONS:
        lo, hi = m["reserved_block"]
        qid = m["reserved_local_id"]
        if not (A7D_RESERVED_RANGE[0] <= lo <= qid <= hi <= A7D_RESERVED_RANGE[1]):
            issues.append(f"{m['quest_edid']}: 0x{qid:06X} / 0x{lo:06X}..0x{hi:06X} outside A7d 0xB10..0xB6F")
        if not (A5_PIPBOY_ACT2_SCAN_RANGE[0] <= qid <= A5_PIPBOY_ACT2_SCAN_RANGE[1]):
            issues.append(f"{m['quest_edid']}: 0x{qid:06X} outside A5 Act II scan window 0x800..0xBFF")
        for other_name, olo, ohi in seen_ranges:
            if not (hi < olo or lo > ohi):
                issues.append(
                    f"{m['quest_edid']} (0x{lo:06X}..0x{hi:06X}) overlaps {other_name} (0x{olo:06X}..0x{ohi:06X})"
                )
        seen_ranges.append((m["quest_edid"], lo, hi))
    return {
        "pass": not issues,
        "a7d_range": f"0x{A7D_RESERVED_RANGE[0]:06X}..0x{A7D_RESERVED_RANGE[1]:06X}",
        "a5_act2_scan_window": f"0x{A5_PIPBOY_ACT2_SCAN_RANGE[0]:06X}..0x{A5_PIPBOY_ACT2_SCAN_RANGE[1]:06X}",
        "issues": issues,
    }


def evaluate_a7d_missions(missions: Sequence[Mapping[str, Any]] = A7D_NEXT_MISSIONS) -> Dict[str, Any]:
    """Run W6 reachability & Open-Mode dead-giver simulation over A7d mission state graphs."""
    report: Dict[str, Any] = {"pass": True, "missions": []}
    for m in missions:
        stages = list(m["stages"])
        start = int(m["start_stage"])
        finals = set(int(x) for x in m["completion_stages"])
        transitions = list(m["transitions"])

        def _check(open_mode: bool) -> Dict[str, Any]:
            adj: Dict[int, List[int]] = {s: [] for s in stages}
            for tr in transitions:
                if open_mode and tr.get("npc_gated", False):
                    continue
                adj.setdefault(int(tr["from"]), []).append(int(tr["to"]))

            seen = {start}
            q: deque[int] = deque([start])
            while q:
                cur = q.popleft()
                for nxt in adj.get(cur, ()):
                    if nxt not in seen:
                        seen.add(nxt)
                        q.append(nxt)

            # In Normal Mode all stages must be reachable (or optional fallback stages like 65 are valid);
            # in Open Mode every reached non-final stage must reach a final stage without dead-ending.
            if open_mode:
                unreachable: List[int] = []
                check_stages = sorted(seen)
            else:
                unreachable = sorted(s for s in stages if s not in seen)
                check_stages = stages

            stuck: List[int] = []
            for s in check_stages:
                if s in finals:
                    continue
                sub_seen = {s}
                sq: deque[int] = deque([s])
                can_finish = False
                while sq:
                    cur = sq.popleft()
                    if cur in finals:
                        can_finish = True
                        break
                    for nxt in adj.get(cur, ()):
                        if nxt not in sub_seen:
                            sub_seen.add(nxt)
                            sq.append(nxt)
                if not can_finish:
                    stuck.append(s)
            return {
                "pass": not unreachable and not stuck and bool(seen & finals),
                "unreachable": unreachable,
                "stuck": stuck,
            }

        normal_res = _check(open_mode=False)
        open_res = _check(open_mode=True)
        ok = normal_res["pass"] and open_res["pass"]
        if not ok:
            report["pass"] = False
        report["missions"].append({
            "quest_edid": m["quest_edid"],
            "reserved_local_id": f"0x{m['reserved_local_id']:06X}",
            "normal": normal_res,
            "open_mode": open_res,
            "pass": ok,
        })
    return report


def emit_a5_objective_tsv_rows(missions: Sequence[Mapping[str, Any]] = A7D_NEXT_MISSIONS) -> List[str]:
    """Emit A5-compatible 7-column FO4SFPipboyQuestObjectives.tsv rows validated against Commonwealth bounds."""
    rows: List[str] = []
    for m in missions:
        qid = f"0x{m['reserved_local_id']:06X}"
        qname = m["title"]
        for stage_idx, label, x, y, place in m["objectives"]:
            if not (math.isfinite(x) and math.isfinite(y)):
                raise ValueError(f"Non-finite objective coordinates for {qid}:{stage_idx}")
            if not (COMMONWEALTH_X_BOUNDS[0] <= x <= COMMONWEALTH_X_BOUNDS[1]):
                raise ValueError(f"X={x} out of Commonwealth bounds for {qid}:{stage_idx}")
            if not (COMMONWEALTH_Y_BOUNDS[0] <= y <= COMMONWEALTH_Y_BOUNDS[1]):
                raise ValueError(f"Y={y} out of Commonwealth bounds for {qid}:{stage_idx}")
            rows.append(f"{qid}\t{stage_idx}\t{qname}\t{label}\t{x:.2f}\t{y:.2f}\t{place}")
    return rows


def verify_staged_interiors_b10(
    port_esm: Path,
    doors_json: Optional[Path] = None,
    places: Sequence[StagedPlaceSpec] = A7D_STAGED_PLACES,
    missing_specs: Sequence[MissingCellSpec] = A7D_MISSING_CELLS,
) -> Dict[str, Any]:
    """Read-only offline binary verification of a staged interiors_b10 FO4Port.esm (and optional doors.json)."""
    src_root = Path(__file__).resolve().parents[2] / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from fo4sf.planet.esm import Plugin, Record, zstring  # noqa: E402

    issues: List[str] = []
    want_present = {p.port_edid: p for p in places}
    want_missing = {m.port_edid: m for m in missing_specs}
    found: Dict[str, Dict[str, Any]] = {}
    unexpected_present: List[str] = []
    total_cells = 0

    with Plugin(str(port_esm)) as plg:
        masters = list(plg.masters)
        cur_edid: Optional[str] = None
        for s, e in plg.groups.get("CELL", []):
            for item in plg.walk(s, e):
                if item[0] != "REC":
                    continue
                _, off, sig, _ = item
                if sig == b"CELL":
                    total_cells += 1
                    rec = Record.parse(plg.buf, off)
                    edid = next((zstring(d) for st, d in rec.subs if st == b"EDID"), "")
                    if edid in want_present:
                        cur_edid = edid
                        found[edid] = {"formid": rec.formid, "refs": 0, "xtel_count": 0}
                    else:
                        cur_edid = None
                        if edid in want_missing:
                            unexpected_present.append(edid)
                elif sig == b"REFR" and cur_edid is not None:
                    found[cur_edid]["refs"] += 1
                    rec = Record.parse(plg.buf, off)
                    for st, d in rec.subs:
                        if st == b"XTEL" and len(d) >= 4:
                            struct.unpack("<I", d[:4])
                            found[cur_edid]["xtel_count"] += 1
                            break

    for spec in places:
        hit = found.get(spec.port_edid)
        if hit is None:
            issues.append(f"missing required staged cell {spec.port_edid} (expected 0x{spec.port_cell_id:08X})")
            continue
        if hit["formid"] != spec.port_cell_id:
            issues.append(
                f"{spec.port_edid}: FormID 0x{hit['formid']:08X} != expected 0x{spec.port_cell_id:08X}"
            )
        if hit["xtel_count"] < spec.expected_internal_xtel_count:
            issues.append(
                f"{spec.port_edid}: internal XTEL count {hit['xtel_count']} < expected {spec.expected_internal_xtel_count}"
            )

    prydwen_door_ok: Optional[bool] = None
    if doors_json is not None:
        raw = json.loads(doors_json.read_text(encoding="utf-8"))
        doors = raw.get("doors", [])
        match = next(
            (
                d for d in doors
                if str(d.get("cell_edid", "")) == PRYDWEN_WIRED_DOOR["cell_edid"]
                and str(d.get("interior_door", "")).upper() == PRYDWEN_WIRED_DOOR["interior_door"]
            ),
            None,
        )
        if match is None:
            prydwen_door_ok = False
            issues.append("doors.json missing wired PrydwenHull01 load door 0045AD")
        else:
            ret = match.get("return_destination", {})
            ok = (
                str(match.get("marker", "")).upper() == PRYDWEN_WIRED_DOOR["marker"]
                and str(ret.get("plugin", "")) == PRYDWEN_WIRED_DOOR["return_plugin"]
                and str(ret.get("id", "")).upper() == PRYDWEN_WIRED_DOOR["return_id"]
            )
            prydwen_door_ok = ok
            if not ok:
                issues.append(
                    f"doors.json PrydwenHull01 0045AD mismatch: marker={match.get('marker')} return={ret.get('plugin')}:{ret.get('id')}"
                )

    return {
        "pass": not issues,
        "masters": masters,
        "total_cells": total_cells,
        "verified_present": len(found),
        "expected_present": len(places),
        "missing_cells_confirmed_absent": sorted(k for k in want_missing if k not in unexpected_present),
        "unexpected_present": sorted(unexpected_present),
        "prydwen_wired_door_ok": prydwen_door_ok,
        "issues": issues,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="A7d Glowing Sea (MQ204) + Molecular Level (MQ206) offline places & doors verifier."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_audit = sub.add_parser("audit-a7d", help="Run FormID, W6, and optional staged interiors_b10 binary checks.")
    p_audit.add_argument("--port-esm", type=Path, default=None, help="Optional path to staged FO4Port.esm (read-only).")
    p_audit.add_argument("--doors-json", type=Path, default=None, help="Optional path to staged doors.json (read-only).")
    sub.add_parser("emit-tsv", help="Print A5-compatible FO4SFPipboyQuestObjectives.tsv rows for A7d.")
    args = parser.parse_args(argv)

    if args.cmd == "audit-a7d":
        fid_res = check_formid_disjointness()
        w6_res = evaluate_a7d_missions()
        staged_res = (
            verify_staged_interiors_b10(args.port_esm, args.doors_json)
            if args.port_esm is not None
            else None
        )
        overall = bool(fid_res["pass"] and w6_res["pass"] and (staged_res is None or staged_res["pass"]))
        payload = {
            "pass": overall,
            "formids": fid_res,
            "w6": w6_res,
            "prydwen_wired_door": PRYDWEN_WIRED_DOOR,
            "staged_places": [
                {
                    "fo4_edid": p.fo4_edid,
                    "fo4_cell_id": f"0x{p.fo4_cell_id:08X}",
                    "port_edid": p.port_edid,
                    "port_cell_id": f"0x{p.port_cell_id:08X}",
                    "staged_ref_count": p.staged_ref_count,
                    "expected_internal_xtel_count": p.expected_internal_xtel_count,
                    "exterior_door_status": p.exterior_door_status,
                }
                for p in A7D_STAGED_PLACES
            ],
            "missing_cells": [
                {
                    "fo4_edid": m.fo4_edid,
                    "fo4_cell_id": f"0x{m.fo4_cell_id:08X}",
                    "category": m.category,
                    "mitigation": m.mitigation,
                }
                for m in A7D_MISSING_CELLS
            ],
            "staged_binary_verification": staged_res,
        }
        print(json.dumps(payload, indent=2))
        return 0 if overall else 1

    if args.cmd == "emit-tsv":
        for row in emit_a5_objective_tsv_rows():
            print(row)
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
