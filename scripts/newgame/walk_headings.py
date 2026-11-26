"""Binary-derived console-free walking headings, measured-speed timings, overshoot margins & A3 hand-play proof.

Computes exact Starfield compass headings (`GetAngle Z` degrees and radians), distances,
measured-speed hold-W durations (`4.8 m/s` default from `2g` on-foot run measurements:
`44.8 m / 9.0 s = 4.98 m/s` on `5a`, `47.5 m / 10.4 s = 4.57 m/s` on `5b`, range `4.6-5.0 m/s`),
and safe overshoot margins before a wall, railing, closed door, or drop for every straight
walking sub-segment across:
  - Opening path (`L1`-`L5`, 34 segments): Vault 111 Cryo Pod -> Pip-Boy -> Console ->
    Exit Lift -> Commonwealth Surface -> Sanctuary (Codsworth) -> Concord (Preston).
  - Extended first-mission places (`L6`-`L9`, 63 segments): Sanctuary Hills enterable houses
    (Codsworth search loop + workbench) and Concord Museum of Freedom (front door -> stairs ->
    Preston's balcony room -> basement terminal/gate/fusion core -> roof Power Armor & Minigun).

Heading convention (verified against `scripts/core/FO4SF_CoreCandidateWalk.psc:229-233` and
confirmed on foot in `2g` on heading `210.8 deg`):
  fwdX = sin(heading_rad), fwdY = cos(heading_rad)
  0 deg   = North (+Y)
  90 deg  = East  (+X)
  180 deg = South (-Y)
  270 deg = West  (-X)
  heading_deg = degrees(atan2(dx, dy)) % 360.0
"""
from __future__ import annotations

import argparse
import json
import math
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

FO4_TO_SF_SCALE = 1.0 / 70.0
MERGE_OFFSET_X = -1200.0
MERGE_OFFSET_Y = -2700.0
FO4_NAVM_V15_STRIDE = 21

# Starfield player forward speeds (m/s). Default run speed updated from 2g on-foot measurements (D6):
# 5a covered 44.8 m in 9.0 s (~4.98 m/s), 5b covered 47.5 m in 10.4 s (~4.57 m/s) -> 4.6-5.0 m/s band.
WALK_SPEED_MPS = 1.60
MEASURED_RUN_SPEED_MIN_MPS = 4.60
MEASURED_RUN_SPEED_MAX_MPS = 5.00
RUN_SPEED_MPS = 4.80

# Offline A3 hand-play physical bounds
PLAYER_EYE_HEIGHT_M = 1.65
STARFIELD_MAX_STEP_HEIGHT_M = 0.50
FIRST_PERSON_REACH_M = 2.00
LIFT_PLATFORM_RADIUS_M = 2.00

Point3 = Tuple[float, float, float]


@dataclass(frozen=True)
class WalkSegment:
    leg_id: str
    seg_id: str
    zone: str  # "interior_vault111", "exterior_commonwealth", or "interior_museum"
    label: str
    start: Point3
    target: Point3
    start_yaw_deg: Optional[float]
    action_at_target: str
    anchor_ref: str
    aim_target: Optional[Point3] = None
    safe_overshoot_m: float = 0.0
    overshoot_hazard: str = ""


def compass_heading_deg(start: Point3, target: Point3) -> float:
    """Starfield `GetAngle Z` compass heading in [0, 360) degrees (0=N/+Y, 90=E/+X)."""
    dx = target[0] - start[0]
    dy = target[1] - start[1]
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return 0.0
    return math.degrees(math.atan2(dx, dy)) % 360.0


def compass_heading_rad(start: Point3, target: Point3) -> float:
    return math.radians(compass_heading_deg(start, target))


def horizontal_distance(start: Point3, target: Point3) -> float:
    return math.hypot(target[0] - start[0], target[1] - start[1])


def distance_3d(start: Point3, target: Point3) -> float:
    return math.sqrt(
        (target[0] - start[0]) ** 2
        + (target[1] - start[1]) ** 2
        + (target[2] - start[2]) ** 2
    )


def compass_cardinal(deg: float) -> str:
    dirs = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")
    idx = int(((deg % 360.0) + 11.25) // 22.5) % 16
    return dirs[idx]


# Binary-derived anchor coordinates (runtime space: interior meters or merged exterior meters)
BINARY_ANCHORS: Dict[str, Dict[str, Any]] = {
    "v111_cryo_start": {
        "source": "FO4SFNewGame.esm / 2g live log (FO4Port_Vault111Cryo 020011F3)",
        "pos": (9.143, -6.614, -0.852),
        "yaw_deg": 0.0,
    },
    "v111_door_1_closed": {
        "source": "FO4Port.esm:0x0100126E (FO4Port_V111Door01, closed by default)",
        "pos": (-7.314, -7.314, 0.000),
        "yaw_deg": 90.0,
    },
    "v111_door_2_closed": {
        "source": "FO4Port.esm:0x01001234 (FO4Port_V111DoorSpecial01, closed by default)",
        "pos": (-31.086, -7.314, 0.000),
        "yaw_deg": 90.0,
    },
    "v111_door_3_open": {
        "source": "FO4Port.esm:0x01001608 (FO4Port_V111DoorSpecial01, ONAM open by default)",
        "pos": (-40.229, -7.314, 0.000),
        "yaw_deg": 90.0,
    },
    "v111_pipboy_pickup": {
        "source": "FO4SFNewGame.esm:0x00080F (FO4SF_PipboyCorpsePickupRef, runtime 0A00080F)",
        "pos": (-55.049, -0.922, 0.776),
        "yaw_deg": 217.98,
    },
    "v111_geardoor_console": {
        "source": "FO4SFNewGame.esm:0x000819 (FO4SF_GearDoorConsoleRef, runtime 0A000819)",
        "pos": (-54.364, -1.815, 1.754),
        "yaw_deg": 180.0,
    },
    "v111_armory_pistol": {
        "source": "FO4SFNewGame.esm:0x000820 (FO4SF_Vault111PistolRef, runtime 0A000820, wireframe armory cage top shelf)",
        "pos": (-57.0338, 30.006, 1.29),
        "yaw_deg": 270.0,
    },
    "v111_armory_ammo": {
        "source": "FO4SFNewGame.esm:0x000821 (FO4SF_Vault111AmmoRef, runtime 0A000821, shelf below 0x820)",
        "pos": (-57.0522, 30.3703, 0.696),
        "yaw_deg": 270.0,
    },
    "v111_gear_door": {
        "source": "FO4Port.esm:0x0100126D (FO4Port_VltGearDoor01)",
        "pos": (-54.857, -2.743, -0.143),
        "yaw_deg": 180.0,
    },
    "v111_exit_lift_platform": {
        "source": "FO4SFExitLift / RespecMoveMarker (0001B29E, PlatformRadius=2.0 m)",
        "pos": (-77.742, -3.958, -1.751),
        "yaw_deg": 270.0,
    },
    "surface_hilltop_arrival": {
        "source": "FO4SFNewGame stage 200 / 2g live log (merged MarsPlanetWorld)",
        "pos": (-2467.781, -1406.925, 127.451),
        "yaw_deg": 90.0,
    },
    "v111_creek_footbridge": {
        "source": "FO4TerrainCore.esm:0x014BA7 (FO4Core_shackbridgefree02, merged)",
        "pos": (-2404.680, -1401.770, 105.270),
        "yaw_deg": 339.5,
    },
    "sanctuary_codsworth": {
        "source": "FO4SFMission.esm:0x000811 (FO4SF_CodsworthREF, runtime 09000811, merged)",
        "pos": (-2346.709, -1406.163, 111.734),
        "yaw_deg": 135.0,
    },
    "sanctuary_north_bridge": {
        "source": "FO4TerrainCore.esm:0x005199 (FO4Core_northbridge, merged)",
        "pos": (-2296.340, -1509.490, 111.370),
        "yaw_deg": 135.0,
    },
    "concord_map_marker": {
        "source": "FO4TerrainCore.esm:0x0A775C (FO4Core_CommonwealthMapMarkerConcord, merged)",
        "pos": (-2061.230, -1657.460, 86.930),
        "yaw_deg": 0.0,
    },
    "concord_preston_museum_door": {
        "source": "FO4SFMission.esm:0x000802 (FO4SF_Min00_PrestonREF, runtime 09000802, merged)",
        "pos": (-2011.143, -1697.543, 89.086),
        "yaw_deg": 310.0,
    },
    # Extended first-mission places (L6 Sanctuary houses + L7-L9 Museum of Freedom)
    "sanctuary_player_house": {
        "source": "FO4TerrainCore.esm Sanctuary player house open exterior shell (merged)",
        "pos": (-2347.500, -1395.500, 112.240),
        "yaw_deg": 0.0,
    },
    "sanctuary_search_house_1": {
        "source": "Fallout4.esm:0x19E136 (MQ102CodsworthSearchMarker01, NE house, merged)",
        "pos": (-2313.440, -1372.020, 112.660),
        "yaw_deg": 0.0,
    },
    "sanctuary_search_house_2": {
        "source": "Fallout4.esm:0x1B2F9A (MQ102CodsworthSearchMarker04, SE house, merged)",
        "pos": (-2285.440, -1431.280, 111.770),
        "yaw_deg": 0.0,
    },
    "sanctuary_workbench": {
        "source": "FO4TerrainCore.esm:0x005C50 (SanctuaryWorkshopREF 0250FE, merged)",
        "pos": (-2329.250, -1420.193, 112.086),
        "yaw_deg": 0.0,
    },
    "museum_front_arrival": {
        "source": "FO4Port_ConcordMuseum01 (012540) front door 077D22 interior arrival",
        "pos": (8.057, 0.000, -0.914),
        "yaw_deg": 270.0,
    },
    "museum_preston_door": {
        "source": "FO4Port.esm:0x013047 (PrestonDoorREF 01E2EA, lock 255 until interior raiders clear)",
        "pos": (5.490, -7.310, 9.140),
        "yaw_deg": 90.0,
    },
    "museum_preston_room": {
        "source": "FO4Port_ConcordMuseum01 upstairs balcony room (Preston & Sturges)",
        "pos": (8.500, -5.000, 9.140),
        "yaw_deg": 0.0,
    },
    "museum_basement_terminal": {
        "source": "FO4Port.esm:0x0125AB (ConcordMuseumBasementTerminal 08110D, Novice lock 25)",
        "pos": (-14.090, -2.510, -3.570),
        "yaw_deg": 90.0,
    },
    "museum_basement_gate": {
        "source": "FO4Port.esm:0x013042 (MQ03SecurityGateREF 05C66C, Novice lock 25)",
        "pos": (-13.710, -0.460, -3.660),
        "yaw_deg": 90.0,
    },
    "museum_basement_generator": {
        "source": "FO4Port.esm:0x012585 (PowerGenerator01 09A147, Fusion Core inside cage)",
        "pos": (-10.630, -0.660, -3.540),
        "yaw_deg": 90.0,
    },
    "museum_preston_exit_door": {
        "source": "FO4Port.esm:0x013046 (PrestonExitDoor 01E2E9, lock 255 until Preston briefing)",
        "pos": (7.450, 5.350, 9.140),
        "yaw_deg": 0.0,
    },
    "museum_roof_door_int": {
        "source": "FO4Port.esm:0x013048 (museum_roof 02C1C6 interior arrival)",
        "pos": (-21.903, 8.683, 9.143),
        "yaw_deg": 270.0,
    },
    "museum_roof_arrival_ext": {
        "source": "FO4TerrainCore.esm:0x00677F (museum_roof 029AD8 exterior merged arrival)",
        "pos": (-1990.577, -1724.185, 97.559),
        "yaw_deg": 270.0,
    },
    "museum_roof_power_armor": {
        "source": "FO4TerrainCore.esm:0x008913 (PowerArmorFurniture 0370E3, merged)",
        "pos": (-1995.730, -1723.100, 97.540),
        "yaw_deg": 280.0,
    },
    "museum_roof_minigun": {
        "source": "FO4TerrainCore.esm:0x005119 (MQ102MinigunREF 01F583, merged)",
        "pos": (-2004.720, -1715.400, 102.680),
        "yaw_deg": 310.0,
    },
}


# Complete obstacle-free straight walking sub-segments from New Game to end of When Freedom Calls (34 segs)
OPENING_WALK_SEGMENTS: Tuple[WalkSegment, ...] = (
    # ---------------- LEG 1: Vault 111 Cryo Pod -> Pip-Boy 3000 (0A00080F)
    WalkSegment(
        leg_id="L1",
        seg_id="1a",
        zone="interior_vault111",
        label="Cryo Pod start -> Cryo hallway centerline",
        start=(9.143, -6.614, -0.852),
        target=(6.360, -7.310, -0.670),
        start_yaw_deg=0.0,
        action_at_target="Turn west (270.0 deg) down main Vault 111 corridor",
        anchor_ref="v111_cryo_start",
        safe_overshoot_m=8.7,
        overshoot_hazard="corridor south wall past centerline",
    ),
    WalkSegment(
        leg_id="L1",
        seg_id="1b",
        zone="interior_vault111",
        label="Main Vault 111 hallway -> Closed Door 1 (0200126E)",
        start=(6.360, -7.310, -0.670),
        target=(-6.100, -7.310, 0.000),
        start_yaw_deg=None,
        action_at_target="Press E to open closed FO4Port_V111Door01 (0200126E at -7.31, -7.31)",
        anchor_ref="v111_door_1_closed",
        aim_target=(-7.314, -7.314, 0.900),
        safe_overshoot_m=1.2,
        overshoot_hazard="closed Door 1 leaf (0200126E)",
    ),
    WalkSegment(
        leg_id="L1",
        seg_id="1c",
        zone="interior_vault111",
        label="Through Door 1 -> Closed Door 2 (02001234)",
        start=(-6.100, -7.310, 0.000),
        target=(-29.900, -7.310, 0.000),
        start_yaw_deg=None,
        action_at_target="Press E to open closed FO4Port_V111DoorSpecial01 (02001234 at -31.09, -7.31)",
        anchor_ref="v111_door_2_closed",
        aim_target=(-31.086, -7.314, 0.900),
        safe_overshoot_m=1.2,
        overshoot_hazard="closed Door 2 leaf (02001234)",
    ),
    WalkSegment(
        leg_id="L1",
        seg_id="1d",
        zone="interior_vault111",
        label="Through Door 2 & open Door 3 (02001608) -> West corridor end",
        start=(-29.900, -7.310, 0.000),
        target=(-41.000, -7.310, 0.130),
        start_yaw_deg=None,
        action_at_target="Door 3 (02001608) is open by default (ONAM); bear slightly WNW around pillar",
        anchor_ref="v111_door_3_open",
        safe_overshoot_m=3.8,
        overshoot_hazard="corridor west pillar/wall",
    ),
    WalkSegment(
        leg_id="L1",
        seg_id="1e",
        zone="interior_vault111",
        label="Clear corridor pillar -> Gear-door chamber vestibule",
        start=(-41.000, -7.310, 0.130),
        target=(-47.000, -6.000, 0.000),
        start_yaw_deg=None,
        action_at_target="Turn due North (0.0 deg) toward control-deck ramp",
        anchor_ref="v111_pipboy_pickup",
        safe_overshoot_m=1.7,
        overshoot_hazard="vestibule west wall/railing",
    ),
    WalkSegment(
        leg_id="L1",
        seg_id="1f",
        zone="interior_vault111",
        label="Gear-door chamber vestibule -> Foot of control-deck ramp",
        start=(-47.000, -6.000, 0.000),
        target=(-47.000, 0.000, 0.000),
        start_yaw_deg=None,
        action_at_target="Turn due West (270.0 deg) to climb control-deck ramp",
        anchor_ref="v111_pipboy_pickup",
        safe_overshoot_m=3.5,
        overshoot_hazard="chamber north wall past ramp foot",
    ),
    WalkSegment(
        leg_id="L1",
        seg_id="1g",
        zone="interior_vault111",
        label="Climb control-deck ramp -> Pip-Boy 3000 pickup spot",
        start=(-47.000, 0.000, 0.000),
        target=(-54.500, 0.000, 0.590),
        start_yaw_deg=None,
        action_at_target="Turn to 210.8 deg SSW, pitch down ~50 deg, press E on Pip-Boy 3000 (0A00080F, 1.82 m eye reach)",
        anchor_ref="v111_pipboy_pickup",
        aim_target=(-55.049, -0.922, 0.776),
        safe_overshoot_m=1.4,
        overshoot_hazard="control-deck west bulkhead/skeleton",
    ),
    # ---------------- LEG 2: Pip-Boy 3000 -> Vault Door Console (0A000819)
    WalkSegment(
        leg_id="L2",
        seg_id="2a",
        zone="interior_vault111",
        label="Pip-Boy pickup spot -> Gear Door Console activation stance",
        start=(-54.500, 0.000, 0.590),
        target=(-54.118, -0.588, 0.590),
        start_yaw_deg=210.8,
        action_at_target="Aim 191.3 deg SSW (level/-21 deg) at Vault Door Controls (0A000819, 1.34 m eye reach), press E, wait ~5 s for gear door",
        anchor_ref="v111_geardoor_console",
        aim_target=(-54.364, -1.815, 1.754),
        safe_overshoot_m=1.0,
        overshoot_hazard="console pedestal & control-deck ledge",
    ),
    # ---------------- LEG 3: Vault Door Console -> Open Gear Door -> Catwalk -> Exit Lift Platform
    WalkSegment(
        leg_id="L3",
        seg_id="3a",
        zone="interior_vault111",
        label="Control deck -> Down ramp to chamber floor",
        start=(-54.118, -0.588, 0.590),
        target=(-47.000, 0.000, 0.000),
        start_yaw_deg=191.3,
        action_at_target="Turn due South (180.0 deg) to align with open gear door",
        anchor_ref="v111_gear_door",
        safe_overshoot_m=16.8,
        overshoot_hazard="east chamber bulkhead",
    ),
    WalkSegment(
        leg_id="L3",
        seg_id="3b",
        zone="interior_vault111",
        label="Ramp foot -> Gear-door centerline",
        start=(-47.000, 0.000, 0.000),
        target=(-47.000, -3.960, 0.000),
        start_yaw_deg=None,
        action_at_target="Turn due West (270.0 deg) facing open Vault 111 gear door (0200126D)",
        anchor_ref="v111_gear_door",
        safe_overshoot_m=3.1,
        overshoot_hazard="chamber south wall",
    ),
    WalkSegment(
        leg_id="L3",
        seg_id="3c",
        zone="interior_vault111",
        label="Through open Gear Door -> Upper catwalk landing",
        start=(-47.000, -3.960, 0.000),
        target=(-65.100, -3.960, 1.040),
        start_yaw_deg=None,
        action_at_target="Stop before west railing; turn due North (0.0 deg) onto stair landing",
        anchor_ref="v111_exit_lift_platform",
        safe_overshoot_m=1.6,
        overshoot_hazard="west catwalk railing & cavern drop",
    ),
    WalkSegment(
        leg_id="L3",
        seg_id="3d",
        zone="interior_vault111",
        label="Catwalk landing -> Top of elevator cavern stairs",
        start=(-65.100, -3.960, 1.040),
        target=(-65.100, -1.310, 0.470),
        start_yaw_deg=None,
        action_at_target="Turn WSW (254.2 deg) down staircase to elevator floor",
        anchor_ref="v111_exit_lift_platform",
        safe_overshoot_m=1.0,
        overshoot_hazard="north stair landing railing/wall",
    ),
    WalkSegment(
        leg_id="L3",
        seg_id="3e",
        zone="interior_vault111",
        label="Down stairs -> Open Exit Lift cage entrance",
        start=(-65.100, -1.310, 0.470),
        target=(-74.480, -3.960, -1.610),
        start_yaw_deg=None,
        action_at_target="Turn due West (270.0 deg) into open elevator cage",
        anchor_ref="v111_exit_lift_platform",
        safe_overshoot_m=5.5,
        overshoot_hazard="elevator shaft south rim / cage wall",
    ),
    WalkSegment(
        leg_id="L3",
        seg_id="3f",
        zone="interior_vault111",
        label="Lift cage entrance -> Center of Exit Lift Platform",
        start=(-74.480, -3.960, -1.610),
        target=(-77.742, -3.958, -1.751),
        start_yaw_deg=None,
        action_at_target="Stop inside PlatformRadius (2.0 m); allocate 33 SPECIAL points & click Continue (if Stay picked, step >2 m out & back in)",
        anchor_ref="v111_exit_lift_platform",
        safe_overshoot_m=2.3,
        overshoot_hazard="elevator cage west back wall",
    ),
    # ---------------- LEG 4: Commonwealth Hilltop Arrival -> Sanctuary Hills (Codsworth 09000811)
    # 100% verified offline against Fallout4.esm Commonwealth WRLD 0x0000003C NAVM (terrain unproven in game)
    WalkSegment(
        leg_id="L4",
        seg_id="4a",
        zone="exterior_commonwealth",
        label="Vault 111 hilltop landing -> Hilltop road north hairpin entry",
        start=(-2467.781, -1406.925, 127.451),
        target=(-2458.000, -1368.000, 123.582),
        start_yaw_deg=90.0,
        action_at_target="Follow Vault 111 access road NNE (33.7 deg) around hilltop switchback",
        anchor_ref="surface_hilltop_arrival",
        safe_overshoot_m=14.2,
        overshoot_hazard="hilltop north cliff edge",
    ),
    WalkSegment(
        leg_id="L4",
        seg_id="4b",
        zone="exterior_commonwealth",
        label="Hilltop road north hairpin entry -> Switchback crest",
        start=(-2458.000, -1368.000, 123.582),
        target=(-2454.000, -1362.000, 119.938),
        start_yaw_deg=None,
        action_at_target="Turn ESE (105.9 deg) down paved Vault 111 switchback trail",
        anchor_ref="surface_hilltop_arrival",
        safe_overshoot_m=1.8,
        overshoot_hazard="steep hilltop embankment drop",
    ),
    WalkSegment(
        leg_id="L4",
        seg_id="4c",
        zone="exterior_commonwealth",
        label="Switchback crest -> Mid-slope descent",
        start=(-2454.000, -1362.000, 119.938),
        target=(-2426.000, -1370.000, 113.000),
        start_yaw_deg=None,
        action_at_target="Continue East (90.0 deg) toward lower trail bend",
        anchor_ref="v111_creek_footbridge",
        safe_overshoot_m=5.4,
        overshoot_hazard="mid-slope cliff rock ledge",
    ),
    WalkSegment(
        leg_id="L4",
        seg_id="4d",
        zone="exterior_commonwealth",
        label="Mid-slope descent -> Lower trail bend",
        start=(-2426.000, -1370.000, 113.000),
        target=(-2420.000, -1370.000, 110.511),
        start_yaw_deg=None,
        action_at_target="Bear SE (135.0 deg) down to creek approach",
        anchor_ref="v111_creek_footbridge",
        safe_overshoot_m=22.2,
        overshoot_hazard="east hillside brush/bank",
    ),
    WalkSegment(
        leg_id="L4",
        seg_id="4e",
        zone="exterior_commonwealth",
        label="Lower trail bend -> Creek approach",
        start=(-2420.000, -1370.000, 110.511),
        target=(-2416.000, -1374.000, 108.542),
        start_yaw_deg=None,
        action_at_target="Descend SSE (157.8 deg) straight to Vault 111 creek footbridge (04014BA7)",
        anchor_ref="v111_creek_footbridge",
        safe_overshoot_m=12.6,
        overshoot_hazard="creek north embankment",
    ),
    WalkSegment(
        leg_id="L4",
        seg_id="4f",
        zone="exterior_commonwealth",
        label="Creek approach -> Vault 111 creek footbridge (04014BA7)",
        start=(-2416.000, -1374.000, 108.542),
        target=(-2404.680, -1401.770, 105.270),
        start_yaw_deg=None,
        action_at_target="Cross footbridge SE (143.1 deg) onto Sanctuary west bank",
        anchor_ref="v111_creek_footbridge",
        safe_overshoot_m=10.0,
        overshoot_hazard="footbridge railing/south creek bank",
    ),
    WalkSegment(
        leg_id="L4",
        seg_id="4g",
        zone="exterior_commonwealth",
        label="Creek footbridge -> Sanctuary west bank",
        start=(-2404.680, -1401.770, 105.270),
        target=(-2400.000, -1408.000, 105.497),
        start_yaw_deg=None,
        action_at_target="Climb SE (127.1 deg) onto paved Sanctuary west road (clears NW house)",
        anchor_ref="sanctuary_codsworth",
        safe_overshoot_m=20.0,
        overshoot_hazard="Sanctuary west yard trees/fences",
    ),
    WalkSegment(
        leg_id="L4",
        seg_id="4h",
        zone="exterior_commonwealth",
        label="Sanctuary west bank -> Sanctuary west road curve",
        start=(-2400.000, -1408.000, 105.497),
        target=(-2361.820, -1436.900, 110.220),
        start_yaw_deg=None,
        action_at_target="Turn NNE (30.8 deg) up Sanctuary street to Codsworth 2.83 m C6-safe standoff",
        anchor_ref="sanctuary_codsworth",
        safe_overshoot_m=15.0,
        overshoot_hazard="Sanctuary south cul-de-sac houses",
    ),
    WalkSegment(
        leg_id="L4",
        seg_id="4i",
        zone="exterior_commonwealth",
        label="Sanctuary west road curve -> Codsworth 2.83 m dialogue standoff",
        start=(-2361.820, -1436.900, 110.220),
        target=(-2344.709, -1408.163, 111.734),
        start_yaw_deg=None,
        action_at_target="Aim 315.0 deg NW at Codsworth (09000811, 2.83 m away for safe C6 camera), press E & finish dialogue",
        anchor_ref="sanctuary_codsworth",
        aim_target=(-2346.709, -1406.163, 111.734),
        safe_overshoot_m=4.6,
        overshoot_hazard="player house curb/wall (1.0 m before C6 radius)",
    ),
    # ---------------- LEG 5: Sanctuary (Codsworth) -> Sanctuary Bridge -> Red Rocket -> Concord Museum (Preston)
    # 100% verified offline against Fallout4.esm Commonwealth WRLD 0x0000003C NAVM (5a/5b ran in game in 2g; rest unproven)
    WalkSegment(
        leg_id="L5",
        seg_id="5a",
        zone="exterior_commonwealth",
        label="Codsworth standoff -> Sanctuary west road curve",
        start=(-2344.709, -1408.163, 111.734),
        target=(-2361.820, -1436.900, 110.220),
        start_yaw_deg=315.0,
        action_at_target="Follow paved Sanctuary road SSE (162.6 deg) toward the bridge",
        anchor_ref="sanctuary_north_bridge",
        safe_overshoot_m=6.0,
        overshoot_hazard="shifts 5b onto SW house wall (16.6 m direct west house wall)",
    ),
    WalkSegment(
        leg_id="L5",
        seg_id="5b",
        zone="exterior_commonwealth",
        label="Sanctuary west road curve -> Sanctuary south road straight",
        start=(-2361.820, -1436.900, 110.220),
        target=(-2350.290, -1473.690, 109.210),
        start_yaw_deg=None,
        action_at_target="Turn East (91.0 deg) to Sanctuary North Bridge approach",
        anchor_ref="sanctuary_north_bridge",
        safe_overshoot_m=12.0,
        overshoot_hazard="creek bank past road (0 m if 5a overshot >6 m: hits SW house wall, still 14)",
    ),
    WalkSegment(
        leg_id="L5",
        seg_id="5c",
        zone="exterior_commonwealth",
        label="Sanctuary south road -> Sanctuary North Bridge approach",
        start=(-2350.290, -1473.690, 109.210),
        target=(-2332.000, -1474.000, 108.327),
        start_yaw_deg=None,
        action_at_target="Align SE (137.0 deg) straight across Sanctuary North Bridge (04005199)",
        anchor_ref="sanctuary_north_bridge",
        safe_overshoot_m=1.4,
        overshoot_hazard="bridge north guardrail & river embankment",
    ),
    WalkSegment(
        leg_id="L5",
        seg_id="5d",
        zone="exterior_commonwealth",
        label="Across Sanctuary North Bridge (04005199) -> South bridge highway",
        start=(-2332.000, -1474.000, 108.327),
        target=(-2278.000, -1532.000, 107.743),
        start_yaw_deg=None,
        action_at_target="Follow paved highway East (86.8 deg) to Red Rocket Truck Stop",
        anchor_ref="sanctuary_north_bridge",
        safe_overshoot_m=7.2,
        overshoot_hazard="south roadside slope/trees past junction",
    ),
    WalkSegment(
        leg_id="L5",
        seg_id="5e",
        zone="exterior_commonwealth",
        label="South bridge highway -> Red Rocket Truck Stop road",
        start=(-2278.000, -1532.000, 107.743),
        target=(-2206.000, -1528.000, 106.429),
        start_yaw_deg=None,
        action_at_target="Pass Red Rocket bearing SSE (145.2 deg) onto Concord highway",
        anchor_ref="concord_map_marker",
        safe_overshoot_m=20.0,
        overshoot_hazard="Red Rocket east driveway embankment",
    ),
    WalkSegment(
        leg_id="L5",
        seg_id="5f",
        zone="exterior_commonwealth",
        label="Red Rocket Truck Stop road -> Concord descent upper",
        start=(-2206.000, -1528.000, 106.429),
        target=(-2174.000, -1574.000, 103.668),
        start_yaw_deg=None,
        action_at_target="Descend paved road SE (135.0 deg) toward Concord",
        anchor_ref="concord_map_marker",
        safe_overshoot_m=3.8,
        overshoot_hazard="steep roadside slope drop (dz=-0.51 m)",
    ),
    WalkSegment(
        leg_id="L5",
        seg_id="5g",
        zone="exterior_commonwealth",
        label="Concord descent upper -> Concord north road",
        start=(-2174.000, -1574.000, 103.668),
        target=(-2140.000, -1608.000, 90.134),
        start_yaw_deg=None,
        action_at_target="Continue SE (132.9 deg) into Concord outskirts",
        anchor_ref="concord_map_marker",
        safe_overshoot_m=20.8,
        overshoot_hazard="Concord outskirts west curb/house",
    ),
    WalkSegment(
        leg_id="L5",
        seg_id="5h",
        zone="exterior_commonwealth",
        label="Concord north road -> Concord northern outskirts",
        start=(-2140.000, -1608.000, 90.134),
        target=(-2112.000, -1634.000, 88.228),
        start_yaw_deg=None,
        action_at_target="Continue SE (128.7 deg) toward Concord Main Street junction",
        anchor_ref="concord_map_marker",
        safe_overshoot_m=12.4,
        overshoot_hazard="Concord street corner building wall",
    ),
    WalkSegment(
        leg_id="L5",
        seg_id="5i",
        zone="exterior_commonwealth",
        label="Concord northern outskirts -> Main Street junction",
        start=(-2112.000, -1634.000, 88.228),
        target=(-2102.000, -1642.000, 88.348),
        start_yaw_deg=None,
        action_at_target="Turn ESE (110.8 deg) to Concord Map Marker (040A775C)",
        anchor_ref="concord_map_marker",
        safe_overshoot_m=21.4,
        overshoot_hazard="Concord Workhouse / south sidewalk wall",
    ),
    WalkSegment(
        leg_id="L5",
        seg_id="5j",
        zone="exterior_commonwealth",
        label="Main Street junction -> Concord Map Marker (040A775C)",
        start=(-2102.000, -1642.000, 88.348),
        target=(-2061.230, -1657.460, 86.930),
        start_yaw_deg=None,
        action_at_target="Inside GiveConcordRadius (150 m); defeat raiders & advance SE (128.4 deg) down Main Street",
        anchor_ref="concord_map_marker",
        safe_overshoot_m=15.0,
        overshoot_hazard="Concord sewer pit / Main Street curb",
    ),
    WalkSegment(
        leg_id="L5",
        seg_id="5k",
        zone="exterior_commonwealth",
        label="Concord Map Marker -> Preston Garvey 2.83 m dialogue standoff",
        start=(-2061.230, -1657.460, 86.930),
        target=(-2013.143, -1695.543, 89.086),
        start_yaw_deg=None,
        action_at_target="Aim 135.0 deg SE at Preston Garvey (09000802, 2.83 m away), press E & finish voiced talk",
        anchor_ref="concord_preston_museum_door",
        aim_target=(-2011.143, -1697.543, 89.086),
        safe_overshoot_m=3.0,
        overshoot_hazard="Museum of Freedom front steps/wall",
    ),
)


# Extended navmesh-verified walk legs for R11 D6 (Sanctuary houses + Museum interior/basement/roof, 63 segs)
EXTENDED_PLACE_WALK_SEGMENTS: Tuple[WalkSegment, ...] = (
    # ---------------- LEG 6: Sanctuary Hills Enterable Houses (Codsworth Search Loop + Workbench, WRLD 0x3C NAVM)
    WalkSegment(
        leg_id="L6", seg_id="6a", zone="exterior_commonwealth",
        label="Codsworth standoff -> Player house front entry",
        start=(-2344.709, -1408.163, 111.734), target=(-2341.230, -1402.920, 111.980),
        start_yaw_deg=315.0, action_at_target="Turn NW (319.8 deg) through open front doorway into Player House",
        anchor_ref="sanctuary_player_house", safe_overshoot_m=0.6, overshoot_hazard="player house exterior porch wall",
    ),
    WalkSegment(
        leg_id="L6", seg_id="6b", zone="exterior_commonwealth",
        label="Player house entry -> Player house living room",
        start=(-2341.230, -1402.920, 111.980), target=(-2347.500, -1395.500, 112.240),
        start_yaw_deg=None, action_at_target="Inspect Shaun's house; exit NE (45.0 deg) toward street",
        anchor_ref="sanctuary_player_house", safe_overshoot_m=4.0, overshoot_hazard="player house north interior wall",
    ),
    WalkSegment(
        leg_id="L6", seg_id="6c", zone="exterior_commonwealth",
        label="Player house interior -> Player house rear/side yard",
        start=(-2347.500, -1395.500, 112.240), target=(-2341.520, -1389.530, 112.230),
        start_yaw_deg=None, action_at_target="Turn ESE (105.0 deg) out to Sanctuary cul-de-sac road",
        anchor_ref="sanctuary_player_house", safe_overshoot_m=8.2, overshoot_hazard="rear yard hedge/fence",
    ),
    WalkSegment(
        leg_id="L6", seg_id="6d", zone="exterior_commonwealth",
        label="Player house yard -> Sanctuary cul-de-sac north curb",
        start=(-2341.520, -1389.530, 112.230), target=(-2333.090, -1391.780, 112.100),
        start_yaw_deg=None, action_at_target="Turn ENE (70.6 deg) across cul-de-sac toward NE search house",
        anchor_ref="sanctuary_search_house_1", safe_overshoot_m=15.0, overshoot_hazard="cul-de-sac opposite curb",
    ),
    WalkSegment(
        leg_id="L6", seg_id="6e", zone="exterior_commonwealth",
        label="Cul-de-sac curb -> NE Search House 1 driveway",
        start=(-2333.090, -1391.780, 112.100), target=(-2309.790, -1383.580, 111.890),
        start_yaw_deg=None, action_at_target="Turn NNW (336.3 deg) into NE Search House 1 (MQ102CodsworthSearchMarker01)",
        anchor_ref="sanctuary_search_house_1", safe_overshoot_m=15.6, overshoot_hazard="cul-de-sac east yard fence",
    ),
    WalkSegment(
        leg_id="L6", seg_id="6f", zone="exterior_commonwealth",
        label="NE House 1 driveway -> NE House 1 hallway",
        start=(-2309.790, -1383.580, 111.890), target=(-2314.310, -1373.300, 112.670),
        start_yaw_deg=None, action_at_target="Step NNE (34.2 deg) to MQ102CodsworthSearchMarker01 (0x19E136)",
        anchor_ref="sanctuary_search_house_1", safe_overshoot_m=1.6, overshoot_hazard="NE house rear interior wall",
    ),
    WalkSegment(
        leg_id="L6", seg_id="6g", zone="exterior_commonwealth",
        label="NE House 1 hallway -> MQ102CodsworthSearchMarker01",
        start=(-2314.310, -1373.300, 112.670), target=(-2313.440, -1372.020, 112.670),
        start_yaw_deg=None, action_at_target="Clear bloatflies inside NE House 1; exit SSE (168.7 deg)",
        anchor_ref="sanctuary_search_house_1", safe_overshoot_m=2.8, overshoot_hazard="NE house north bedroom wall",
    ),
    WalkSegment(
        leg_id="L6", seg_id="6h", zone="exterior_commonwealth",
        label="NE House 1 interior -> Cul-de-sac east road",
        start=(-2313.440, -1372.020, 112.670), target=(-2311.010, -1384.190, 111.880),
        start_yaw_deg=None, action_at_target="Head SSE (147.5 deg) across cul-de-sac to SE Search House 2",
        anchor_ref="sanctuary_search_house_2", safe_overshoot_m=8.2, overshoot_hazard="cul-de-sac center tree/curb",
    ),
    WalkSegment(
        leg_id="L6", seg_id="6i", zone="exterior_commonwealth",
        label="Cul-de-sac east road -> SE Search House 2 front yard",
        start=(-2311.010, -1384.190, 111.880), target=(-2287.590, -1420.910, 111.460),
        start_yaw_deg=None, action_at_target="Turn SSW (207.8 deg) through open carport/door into SE House 2",
        anchor_ref="sanctuary_search_house_2", safe_overshoot_m=1.4, overshoot_hazard="SE house front exterior wall",
    ),
    WalkSegment(
        leg_id="L6", seg_id="6j", zone="exterior_commonwealth",
        label="SE House 2 front yard -> SE House 2 main room",
        start=(-2287.590, -1420.910, 111.460), target=(-2290.860, -1427.100, 111.740),
        start_yaw_deg=None, action_at_target="Turn SE (128.4 deg) through interior hall",
        anchor_ref="sanctuary_search_house_2", safe_overshoot_m=5.4, overshoot_hazard="SE house kitchen counter/wall",
    ),
    WalkSegment(
        leg_id="L6", seg_id="6k", zone="exterior_commonwealth",
        label="SE House 2 main room -> SE House 2 rear room",
        start=(-2290.860, -1427.100, 111.740), target=(-2286.820, -1430.300, 111.750),
        start_yaw_deg=None, action_at_target="Step SE (125.4 deg) to MQ102CodsworthSearchMarker04 (0x1B2F9A)",
        anchor_ref="sanctuary_search_house_2", safe_overshoot_m=3.0, overshoot_hazard="SE house rear bedroom wall",
    ),
    WalkSegment(
        leg_id="L6", seg_id="6l", zone="exterior_commonwealth",
        label="SE House 2 rear room -> MQ102CodsworthSearchMarker04",
        start=(-2286.820, -1430.300, 111.750), target=(-2285.440, -1431.280, 111.750),
        start_yaw_deg=None, action_at_target="Clear bloatflies inside SE House 2; exit NW (303.6 deg)",
        anchor_ref="sanctuary_search_house_2", safe_overshoot_m=1.4, overshoot_hazard="SE house east exterior wall",
    ),
    WalkSegment(
        leg_id="L6", seg_id="6m", zone="exterior_commonwealth",
        label="SE House 2 marker -> SE House 2 main room exit",
        start=(-2285.440, -1431.280, 111.750), target=(-2290.530, -1427.900, 111.710),
        start_yaw_deg=None, action_at_target="Turn NNE (18.9 deg) out doorway onto cul-de-sac street",
        anchor_ref="sanctuary_workbench", safe_overshoot_m=1.6, overshoot_hazard="SE house west wall",
    ),
    WalkSegment(
        leg_id="L6", seg_id="6n", zone="exterior_commonwealth",
        label="SE House 2 exit -> Cul-de-sac south road",
        start=(-2290.530, -1427.900, 111.710), target=(-2287.050, -1417.740, 111.370),
        start_yaw_deg=None, action_at_target="Head WNW (282.2 deg) toward Sanctuary Workbench house",
        anchor_ref="sanctuary_workbench", safe_overshoot_m=5.2, overshoot_hazard="cul-de-sac north sidewalk",
    ),
    WalkSegment(
        leg_id="L6", seg_id="6o", zone="exterior_commonwealth",
        label="Cul-de-sac south road -> Workbench driveway approach",
        start=(-2287.050, -1417.740, 111.370), target=(-2312.370, -1412.280, 111.770),
        start_yaw_deg=None, action_at_target="Turn SW (236.6 deg) under Workbench house carport",
        anchor_ref="sanctuary_workbench", safe_overshoot_m=20.0, overshoot_hazard="Sanctuary west road curb",
    ),
    WalkSegment(
        leg_id="L6", seg_id="6p", zone="exterior_commonwealth",
        label="Workbench driveway -> Workbench house carport",
        start=(-2312.370, -1412.280, 111.770), target=(-2329.370, -1423.480, 112.100),
        start_yaw_deg=None, action_at_target="Step North (7.1 deg) to Sanctuary Workbench (04005C50)",
        anchor_ref="sanctuary_workbench", safe_overshoot_m=3.8, overshoot_hazard="carport west wall/railing",
    ),
    WalkSegment(
        leg_id="L6", seg_id="6q", zone="exterior_commonwealth",
        label="Workbench carport -> Sanctuary Workbench (04005C50) stance",
        start=(-2329.370, -1423.480, 112.100), target=(-2329.250, -1422.500, 112.090),
        start_yaw_deg=None, action_at_target="Aim North at Sanctuary Workshop (04005C50), press E if testing bench; step East (93.1 deg) to exit",
        anchor_ref="sanctuary_workbench", aim_target=(-2329.250, -1420.193, 112.086),
        safe_overshoot_m=1.0, overshoot_hazard="Sanctuary workbench & house wall",
    ),
    WalkSegment(
        leg_id="L6", seg_id="6r", zone="exterior_commonwealth",
        label="Sanctuary Workbench -> Carport pillar clearance",
        start=(-2329.250, -1422.500, 112.090), target=(-2327.710, -1422.580, 112.090),
        start_yaw_deg=None, action_at_target="Turn NNE (20.9 deg) out to main Sanctuary street",
        anchor_ref="sanctuary_codsworth", safe_overshoot_m=0.8, overshoot_hazard="carport east pillar",
    ),
    WalkSegment(
        leg_id="L6", seg_id="6s", zone="exterior_commonwealth",
        label="Carport clearance -> Sanctuary main street",
        start=(-2327.710, -1422.580, 112.090), target=(-2323.990, -1412.850, 111.840),
        start_yaw_deg=None, action_at_target="Turn WNW (282.7 deg) back to Codsworth standoff",
        anchor_ref="sanctuary_codsworth", safe_overshoot_m=15.0, overshoot_hazard="north yard hedge",
    ),
    WalkSegment(
        leg_id="L6", seg_id="6t", zone="exterior_commonwealth",
        label="Sanctuary main street -> Return to Codsworth standoff",
        start=(-2323.990, -1412.850, 111.840), target=(-2344.709, -1408.163, 111.734),
        start_yaw_deg=None, action_at_target="Speak to Codsworth (09000811) after searching houses, then start Leg L5 to Concord",
        anchor_ref="sanctuary_codsworth", aim_target=(-2346.709, -1406.163, 111.734),
        safe_overshoot_m=5.0, overshoot_hazard="west roadside house curb",
    ),

    # ---------------- LEG 7: Museum of Freedom Front Door -> Upstairs -> Preston's Room (ConcordMuseum01 NAVM 0x197BB0)
    WalkSegment(
        leg_id="L7", seg_id="7a", zone="interior_museum",
        label="Museum front arrival -> Rotunda west entry",
        start=(8.057, 0.000, -0.914), target=(-8.640, 2.280, 0.080),
        start_yaw_deg=270.0, action_at_target="Clear lobby raiders; bear SW (235.2 deg) around rotunda desk",
        anchor_ref="museum_front_arrival", safe_overshoot_m=2.0, overshoot_hazard="rotunda display wall",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7b", zone="interior_museum",
        label="Rotunda west entry -> Rotunda south passage",
        start=(-8.640, 2.280, 0.080), target=(-11.770, 0.110, 0.010),
        start_yaw_deg=None, action_at_target="Turn WSW (258.3 deg) toward west hall",
        anchor_ref="museum_front_arrival", safe_overshoot_m=0.4, overshoot_hazard="rotunda exhibit divider",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7c", zone="interior_museum",
        label="Rotunda south passage -> West hall entry",
        start=(-11.770, 0.110, 0.010), target=(-15.490, -0.670, 0.000),
        start_yaw_deg=None, action_at_target="Turn South (181.9 deg) down west corridor",
        anchor_ref="museum_front_arrival", safe_overshoot_m=0.2, overshoot_hazard="west corridor wall",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7d", zone="interior_museum",
        label="West hall entry -> West hall mid",
        start=(-15.490, -0.670, 0.000), target=(-15.600, -3.960, 0.130),
        start_yaw_deg=None, action_at_target="Bear SSW (213.1 deg) to basement-stair lobby",
        anchor_ref="museum_front_arrival", safe_overshoot_m=1.4, overshoot_hazard="south partition wall",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7e", zone="interior_museum",
        label="West hall mid -> Lower stair landing",
        start=(-15.600, -3.960, 0.130), target=(-17.600, -7.010, 0.090),
        start_yaw_deg=None, action_at_target="Turn East (86.0 deg) down/across lower stair landing",
        anchor_ref="museum_front_arrival", safe_overshoot_m=2.2, overshoot_hazard="south stair bulkhead",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7f", zone="interior_museum",
        label="Lower stair landing -> Lower connector floor",
        start=(-17.600, -7.010, 0.090), target=(-9.020, -6.420, -3.510),
        start_yaw_deg=None, action_at_target="Turn WNW (299.4 deg) toward main west stair foot",
        anchor_ref="museum_front_arrival", safe_overshoot_m=2.2, overshoot_hazard="east basement wall",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7g", zone="interior_museum",
        label="Lower connector -> Main west stairwell foot",
        start=(-9.020, -6.420, -3.510), target=(-14.990, -3.050, -3.450),
        start_yaw_deg=None, action_at_target="Turn NW (320.5 deg) onto west ascent stairs",
        anchor_ref="museum_front_arrival", safe_overshoot_m=0.6, overshoot_hazard="basement terminal partition",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7h", zone="interior_museum",
        label="Main west stairwell foot -> Mid-flight landing",
        start=(-14.990, -3.050, -3.450), target=(-18.170, 0.800, -1.770),
        start_yaw_deg=None, action_at_target="Climb West (263.6 deg) up main museum staircase to 2nd floor",
        anchor_ref="museum_front_arrival", safe_overshoot_m=2.6, overshoot_hazard="north stair railing/wall",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7i", zone="interior_museum",
        label="Main west stairs -> 2nd-floor west landing",
        start=(-18.170, 0.800, -1.770), target=(-28.740, -0.390, 3.800),
        start_yaw_deg=None, action_at_target="Turn South (172.3 deg) up remaining steps onto 2nd-floor gallery",
        anchor_ref="museum_front_arrival", safe_overshoot_m=2.0, overshoot_hazard="west stairwell wall",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7j", zone="interior_museum",
        label="2nd-floor west landing -> 2nd-floor SW corner",
        start=(-28.740, -0.390, 3.800), target=(-27.800, -7.330, 5.490),
        start_yaw_deg=None, action_at_target="Turn SE (131.2 deg) into 2nd-floor exhibit wing",
        anchor_ref="museum_front_arrival", safe_overshoot_m=1.4, overshoot_hazard="2nd-floor south wall",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7k", zone="interior_museum",
        label="2nd-floor SW corner -> 2nd-floor south exhibit entry",
        start=(-27.800, -7.330, 5.490), target=(-25.390, -9.440, 5.590),
        start_yaw_deg=None, action_at_target="Turn ESE (100.2 deg) along 2nd-floor south gallery",
        anchor_ref="museum_front_arrival", safe_overshoot_m=3.4, overshoot_hazard="exhibit pillar",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7l", zone="interior_museum",
        label="2nd-floor south exhibit entry -> 2nd-floor mid gallery",
        start=(-25.390, -9.440, 5.590), target=(-18.290, -10.720, 5.570),
        start_yaw_deg=None, action_at_target="Continue East (88.8 deg) fighting 2nd-floor raiders",
        anchor_ref="museum_front_arrival", safe_overshoot_m=3.6, overshoot_hazard="gallery exhibit case",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7m", zone="interior_museum",
        label="2nd-floor mid gallery -> 2nd-floor east gallery",
        start=(-18.290, -10.720, 5.570), target=(-7.860, -10.510, 5.570),
        start_yaw_deg=None, action_at_target="Turn SSE (151.4 deg) into south side gallery",
        anchor_ref="museum_front_arrival", safe_overshoot_m=1.8, overshoot_hazard="rotunda 2nd-floor railing",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7n", zone="interior_museum",
        label="2nd-floor east gallery -> South side room entry",
        start=(-7.860, -10.510, 5.570), target=(-4.960, -15.820, 5.610),
        start_yaw_deg=None, action_at_target="Turn SW (226.1 deg) around ruined exhibit wall",
        anchor_ref="museum_front_arrival", safe_overshoot_m=1.4, overshoot_hazard="south room wall",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7o", zone="interior_museum",
        label="South side room entry -> South wing west bend",
        start=(-4.960, -15.820, 5.610), target=(-10.700, -21.330, 5.550),
        start_yaw_deg=None, action_at_target="Turn East (93.9 deg) toward 3rd-floor stairs",
        anchor_ref="museum_front_arrival", safe_overshoot_m=0.8, overshoot_hazard="south wing exterior wall",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7p", zone="interior_museum",
        label="South wing west bend -> Foot of 3rd-floor stairs",
        start=(-10.700, -21.330, 5.550), target=(-0.450, -22.040, 5.590),
        start_yaw_deg=None, action_at_target="Turn NE (43.5 deg) onto 3rd-floor staircase",
        anchor_ref="museum_preston_door", safe_overshoot_m=2.0, overshoot_hazard="east stairwell wall",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7q", zone="interior_museum",
        label="Foot of 3rd-floor stairs -> Lower 3rd-floor flight",
        start=(-0.450, -22.040, 5.590), target=(2.710, -18.710, 6.130),
        start_yaw_deg=None, action_at_target="Continue NE (49.4 deg) up stairs to mid-landing",
        anchor_ref="museum_preston_door", safe_overshoot_m=3.0, overshoot_hazard="stair east wall",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7r", zone="interior_museum",
        label="Lower 3rd-floor flight -> 3rd-floor stair landing",
        start=(2.710, -18.710, 6.130), target=(6.520, -15.450, 7.490),
        start_yaw_deg=None, action_at_target="Turn WNW (294.7 deg) up top flight onto 3rd-floor catwalk",
        anchor_ref="museum_preston_door", safe_overshoot_m=2.8, overshoot_hazard="landing exterior wall",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7s", zone="interior_museum",
        label="3rd-floor stair landing -> 3rd-floor upper hallway",
        start=(6.520, -15.450, 7.490), target=(-7.080, -9.200, 9.180),
        start_yaw_deg=None, action_at_target="Turn NE (42.2 deg) onto upper gallery walkway",
        anchor_ref="museum_preston_door", safe_overshoot_m=8.0, overshoot_hazard="upper gallery west wall",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7t", zone="interior_museum",
        label="3rd-floor upper hallway -> Preston corridor entry",
        start=(-7.080, -9.200, 9.180), target=(-4.990, -6.890, 9.140),
        start_yaw_deg=None, action_at_target="Turn East (92.3 deg) through PrestonDoorREF (02013047, unlocked when raiders clear)",
        anchor_ref="museum_preston_door", safe_overshoot_m=1.6, overshoot_hazard="upper balcony railing",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7u", zone="interior_museum",
        label="Preston corridor -> Through PrestonDoorREF (02013047)",
        start=(-4.990, -6.890, 9.140), target=(7.450, -7.390, 9.140),
        start_yaw_deg=None, action_at_target="Open PrestonDoorREF (02013047 at 5.49, -7.31) with E; turn NNE (23.6 deg) into Preston's room",
        anchor_ref="museum_preston_door", aim_target=(5.490, -7.310, 9.140),
        safe_overshoot_m=3.0, overshoot_hazard="Preston's room east balcony wall",
    ),
    WalkSegment(
        leg_id="L7", seg_id="7v", zone="interior_museum",
        label="PrestonDoorREF -> Preston & Sturges balcony room",
        start=(7.450, -7.390, 9.140), target=(8.500, -5.000, 9.140),
        start_yaw_deg=None, action_at_target="Speak with Preston & Sturges (real dialogue) for Fusion Core & Roof Power Armor briefing",
        anchor_ref="museum_preston_room", safe_overshoot_m=3.2, overshoot_hazard="Preston's room north wall/door",
    ),

    # ---------------- LEG 8: Museum Preston's Room -> Basement Terminal & Security Gate -> Fusion Core (ConcordMuseum01 NAVM)
    WalkSegment(
        leg_id="L8", seg_id="8a", zone="interior_museum",
        label="Preston's room -> Exit PrestonDoorREF (02013047)",
        start=(8.500, -5.000, 9.140), target=(5.420, -7.070, 9.140),
        start_yaw_deg=236.1, action_at_target="Head West (264.3 deg) along 3rd-floor upper hallway",
        anchor_ref="museum_preston_door", safe_overshoot_m=3.0, overshoot_hazard="upper corridor south wall",
    ),
    WalkSegment(
        leg_id="L8", seg_id="8b", zone="interior_museum",
        label="PrestonDoorREF -> 3rd-floor hallway west end",
        start=(5.420, -7.070, 9.140), target=(-6.700, -8.280, 9.160),
        start_yaw_deg=None, action_at_target="Step SSW (202.1 deg) to 3rd-floor stair top",
        anchor_ref="museum_basement_terminal", safe_overshoot_m=3.6, overshoot_hazard="upper gallery railing",
    ),
    WalkSegment(
        leg_id="L8", seg_id="8c", zone="interior_museum",
        label="3rd-floor hallway west -> Top of 3rd-floor descent stairs",
        start=(-6.700, -8.280, 9.160), target=(-7.080, -9.200, 9.180),
        start_yaw_deg=None, action_at_target="Descend ESE (114.7 deg) down 3rd-floor stairs",
        anchor_ref="museum_basement_terminal", safe_overshoot_m=3.4, overshoot_hazard="stairwell south wall",
    ),
    WalkSegment(
        leg_id="L8", seg_id="8d", zone="interior_museum",
        label="Top of 3rd-floor stairs -> 3rd-floor mid-landing",
        start=(-7.080, -9.200, 9.180), target=(6.520, -15.450, 7.490),
        start_yaw_deg=None, action_at_target="Turn SW (229.4 deg) down lower flight",
        anchor_ref="museum_basement_terminal", safe_overshoot_m=2.2, overshoot_hazard="landing east wall",
    ),
    WalkSegment(
        leg_id="L8", seg_id="8e", zone="interior_museum",
        label="3rd-floor mid-landing -> Lower stair step",
        start=(6.520, -15.450, 7.490), target=(2.710, -18.710, 6.130),
        start_yaw_deg=None, action_at_target="Continue WSW (236.7 deg) onto 2nd-floor south wing",
        anchor_ref="museum_basement_terminal", safe_overshoot_m=5.6, overshoot_hazard="south wing wall",
    ),
    WalkSegment(
        leg_id="L8", seg_id="8f", zone="interior_museum",
        label="Lower stair step -> 2nd-floor south wing east",
        start=(2.710, -18.710, 6.130), target=(-2.930, -22.420, 5.610),
        start_yaw_deg=None, action_at_target="Turn WNW (283.8 deg) across south wing",
        anchor_ref="museum_basement_terminal", safe_overshoot_m=1.8, overshoot_hazard="south wing exterior wall",
    ),
    WalkSegment(
        leg_id="L8", seg_id="8g", zone="interior_museum",
        label="2nd-floor south wing east -> South wing west corner",
        start=(-2.930, -22.420, 5.610), target=(-10.570, -20.540, 5.660),
        start_yaw_deg=None, action_at_target="Turn NE (49.9 deg) around ruined exhibit wall",
        anchor_ref="museum_basement_terminal", safe_overshoot_m=0.6, overshoot_hazard="south wing west wall",
    ),
    WalkSegment(
        leg_id="L8", seg_id="8h", zone="interior_museum",
        label="South wing west corner -> 2nd-floor south room exit",
        start=(-10.570, -20.540, 5.660), target=(-4.960, -15.820, 5.610),
        start_yaw_deg=None, action_at_target="Turn NW (324.8 deg) back to 2nd-floor main gallery",
        anchor_ref="museum_basement_terminal", safe_overshoot_m=1.6, overshoot_hazard="exhibit partition",
    ),
    WalkSegment(
        leg_id="L8", seg_id="8i", zone="interior_museum",
        label="South room exit -> 2nd-floor main gallery",
        start=(-4.960, -15.820, 5.610), target=(-8.770, -10.420, 5.590),
        start_yaw_deg=None, action_at_target="Turn West (267.0 deg) along 2nd-floor gallery toward west stairs",
        anchor_ref="museum_basement_terminal", safe_overshoot_m=0.8, overshoot_hazard="rotunda railing",
    ),
    WalkSegment(
        leg_id="L8", seg_id="8j", zone="interior_museum",
        label="2nd-floor main gallery -> 2nd-floor west end",
        start=(-8.770, -10.420, 5.590), target=(-26.050, -11.330, 5.590),
        start_yaw_deg=None, action_at_target="Turn North (3.4 deg) to west stairwell vestibule",
        anchor_ref="museum_basement_terminal", safe_overshoot_m=0.8, overshoot_hazard="west gallery wall",
    ),
    WalkSegment(
        leg_id="L8", seg_id="8k", zone="interior_museum",
        label="2nd-floor west end -> West stairwell vestibule",
        start=(-26.050, -11.330, 5.590), target=(-25.780, -6.920, 5.490),
        start_yaw_deg=None, action_at_target="Turn WNW (284.0 deg) to top of basement stairwell",
        anchor_ref="museum_basement_terminal", safe_overshoot_m=1.4, overshoot_hazard="north doorway frame",
    ),
    WalkSegment(
        leg_id="L8", seg_id="8l", zone="interior_museum",
        label="West stairwell vestibule -> Top of basement stairs",
        start=(-25.780, -6.920, 5.490), target=(-29.190, -6.070, 5.490),
        start_yaw_deg=None, action_at_target="Turn North (4.6 deg) down stairs toward basement",
        anchor_ref="museum_basement_terminal", safe_overshoot_m=1.4, overshoot_hazard="west stairwell wall",
    ),
    WalkSegment(
        leg_id="L8", seg_id="8m", zone="interior_museum",
        label="Top of basement stairs -> Mid-landing",
        start=(-29.190, -6.070, 5.490), target=(-28.740, -0.390, 3.800),
        start_yaw_deg=None, action_at_target="Turn East (91.6 deg) all the way down into Museum basement",
        anchor_ref="museum_basement_terminal", safe_overshoot_m=9.0, overshoot_hazard="north stair landing wall",
    ),
    WalkSegment(
        leg_id="L8", seg_id="8n", zone="interior_museum",
        label="Mid-landing -> Basement generator hall entry",
        start=(-28.740, -0.390, 3.800), target=(-15.080, -0.780, -3.200),
        start_yaw_deg=None, action_at_target="Turn SSE (164.2 deg) to ConcordMuseumBasementTerminal (020125AB)",
        anchor_ref="museum_basement_terminal", safe_overshoot_m=1.0, overshoot_hazard="basement security cage mesh",
    ),
    WalkSegment(
        leg_id="L8", seg_id="8o", zone="interior_museum",
        label="Basement hall entry -> Basement Terminal (020125AB) stance",
        start=(-15.080, -0.780, -3.200), target=(-14.650, -2.300, -3.430),
        start_yaw_deg=None, action_at_target="Hack Novice ConcordMuseumBasementTerminal (020125AB) to unlock gate, then step North (7.1 deg) to gate",
        anchor_ref="museum_basement_terminal", aim_target=(-14.090, -2.510, -3.570),
        safe_overshoot_m=4.2, overshoot_hazard="basement south wall",
    ),
    WalkSegment(
        leg_id="L8", seg_id="8p", zone="interior_museum",
        label="Basement Terminal -> MQ03SecurityGateREF (02013042) & Fusion Core cage",
        start=(-14.650, -2.300, -3.430), target=(-14.380, -0.090, -3.360),
        start_yaw_deg=None, action_at_target="Open/pick Novice MQ03SecurityGateREF (02013042), step 2.2 m East (99 deg) into un-navmeshed cage to take Fusion Core from PowerGenerator01 (02012585)",
        anchor_ref="museum_basement_gate", aim_target=(-13.710, -0.460, -3.660),
        safe_overshoot_m=1.2, overshoot_hazard="basement north cage wall (cage interior has 0 FO4 NAVM tris by design)",
    ),

    # ---------------- LEG 9: Museum Preston's Room -> Roof Door -> Exterior Roof Power Armor & Vertibird Minigun
    WalkSegment(
        leg_id="L9", seg_id="9a", zone="interior_museum",
        label="Preston's room -> Through PrestonExitDoor (02013046) to north corridor",
        start=(8.500, -5.000, 9.140), target=(5.840, 7.120, 9.190),
        start_yaw_deg=347.6, action_at_target="Open PrestonExitDoor (02013046 at 7.45, 5.35, unlocked after briefing); turn West (273.2 deg) down roof hall",
        anchor_ref="museum_preston_exit_door", aim_target=(7.450, 5.350, 9.140),
        safe_overshoot_m=0.8, overshoot_hazard="north roof hallway wall",
    ),
    WalkSegment(
        leg_id="L9", seg_id="9b", zone="interior_museum",
        label="Upper north roof corridor -> Museum Roof Door (02013048)",
        start=(5.840, 7.120, 9.190), target=(-21.903, 8.683, 9.143),
        start_yaw_deg=None, action_at_target="Press E on Museum Roof Door (02013048 -> exterior roof -1990.58, -1724.18, 97.56)",
        anchor_ref="museum_roof_door_int", aim_target=(-21.940, 9.140, 9.140),
        safe_overshoot_m=2.4, overshoot_hazard="roof stairwell west wall",
    ),
    WalkSegment(
        leg_id="L9", seg_id="9c", zone="exterior_commonwealth",
        label="Exterior Museum Roof arrival -> T-45 Power Armor (04008913)",
        start=(-1990.577, -1724.185, 97.440), target=(-1995.730, -1723.100, 97.700),
        start_yaw_deg=281.9, action_at_target="Insert Fusion Core & climb into T-45 Power Armor (04008913), then turn NW (316.0 deg) toward Vertibird",
        anchor_ref="museum_roof_power_armor", aim_target=(-1995.730, -1723.100, 97.540),
        safe_overshoot_m=2.6, overshoot_hazard="roof parapet / west roof drop",
    ),
    WalkSegment(
        leg_id="L9", seg_id="9d", zone="exterior_commonwealth",
        label="T-45 Power Armor -> Crashed Vertibird upper deck ramp",
        start=(-1995.730, -1723.100, 97.700), target=(-2003.040, -1715.530, 101.050),
        start_yaw_deg=None, action_at_target="Step West (265.1 deg) beside Vertibird gun mount",
        anchor_ref="museum_roof_minigun", safe_overshoot_m=1.0, overshoot_hazard="Vertibird fuselage / north roof parapet drop",
    ),
    WalkSegment(
        leg_id="L9", seg_id="9e", zone="exterior_commonwealth",
        label="Vertibird deck ramp -> Vertibird Minigun (04005119) rip-off stance",
        start=(-2003.040, -1715.530, 101.050), target=(-2004.440, -1715.650, 101.380),
        start_yaw_deg=None, action_at_target="Press E on Vertibird Minigun (04005119, 1.35 m 3D reach) in Power Armor, then drop to Concord street for Wave 2 & Deathclaw",
        anchor_ref="museum_roof_minigun", aim_target=(-2004.720, -1715.400, 102.680),
        safe_overshoot_m=3.6, overshoot_hazard="west roof parapet & 12 m drop to Concord street",
    ),
)

ALL_WALK_SEGMENTS: Tuple[WalkSegment, ...] = OPENING_WALK_SEGMENTS + EXTENDED_PLACE_WALK_SEGMENTS

# Vault 111 optional armory cage walk leg (G11: Pip-Boy deck -> unlocked doors 02001607/02001609/0200160A -> 02001539 -> 0A000820/0A000821)
VAULT_ARMORY_WALK_SEGMENTS: Tuple[WalkSegment, ...] = (
    WalkSegment(
        leg_id="L10",
        seg_id="10a",
        zone="interior_vault111",
        label="Pip-Boy pickup spot -> Down ramp to Vault 111 chamber floor",
        start=(-54.500, 0.000, 0.590),
        target=(-47.000, 0.000, 0.000),
        start_yaw_deg=90.0,
        action_at_target="Continue East (90.0 deg) toward east doorway (02001607)",
        anchor_ref="v111_armory_pistol",
        safe_overshoot_m=16.8,
        overshoot_hazard="east chamber bulkhead beyond T-junction",
    ),
    WalkSegment(
        leg_id="L10",
        seg_id="10b",
        zone="interior_vault111",
        label="Chamber floor -> Through unlocked door 02001607 (-40.23, 0.00) to N-S corridor T-junction",
        start=(-47.000, 0.000, 0.000),
        target=(-32.914, 0.000, 0.131),
        start_yaw_deg=None,
        action_at_target="Press E on unlocked door 02001607 if closed, then turn North (0.0 deg) up corridor toward 02001609",
        anchor_ref="v111_armory_pistol",
        safe_overshoot_m=3.9,
        overshoot_hazard="east wall behind T-junction",
    ),
    WalkSegment(
        leg_id="L10",
        seg_id="10c",
        zone="interior_vault111",
        label="N-S corridor T-junction -> Through 02001609 (-32.91, 3.66) to security-hall corner",
        start=(-32.914, 0.000, 0.131),
        target=(-32.914, 14.630, 0.030),
        start_yaw_deg=None,
        action_at_target="Pass through unlocked door 02001609, turn West (270.0 deg) down Vault security hall",
        anchor_ref="v111_armory_pistol",
        safe_overshoot_m=1.0,
        overshoot_hazard="north bulkhead wall at security-hall bend",
    ),
    WalkSegment(
        leg_id="L10",
        seg_id="10d",
        zone="interior_vault111",
        label="Security-hall corner -> Overseer vestibule West turn",
        start=(-32.914, 14.630, 0.030),
        target=(-53.029, 14.630, 0.000),
        start_yaw_deg=None,
        action_at_target="Turn North (0.0 deg) toward unlocked Overseer door 0200160A (-53.03, 18.29)",
        anchor_ref="v111_armory_pistol",
        safe_overshoot_m=3.9,
        overshoot_hazard="west security-office alcove wall",
    ),
    WalkSegment(
        leg_id="L10",
        seg_id="10e",
        zone="interior_vault111",
        label="Overseer vestibule -> Through 0200160A (-53.03, 18.29) to armory gate vestibule",
        start=(-53.029, 14.630, 0.000),
        target=(-53.029, 29.714, 0.000),
        start_yaw_deg=None,
        action_at_target="Open unlocked Overseer door 0200160A with E, turn West (275.1 deg) through open wire gate 02001539",
        anchor_ref="v111_armory_pistol",
        safe_overshoot_m=8.4,
        overshoot_hazard="north Overseer office wall",
    ),
    WalkSegment(
        leg_id="L10",
        seg_id="10f",
        zone="interior_vault111",
        label="Armory gate vestibule -> Wire armory cage shelf (0A000820 / 0A000821 stance)",
        start=(-53.029, 29.714, 0.000),
        target=(-56.250, 30.000, 0.000),
        start_yaw_deg=None,
        action_at_target="Pass wire gate 02001539 (-54.92, 29.71); aim West at 0A000820 (0.86 m reach) & 0A000821 (1.30 m reach) & press E",
        anchor_ref="v111_armory_pistol",
        aim_target=(-57.0338, 30.006, 1.29),
        safe_overshoot_m=0.5,
        overshoot_hazard="wire armory cage shelf & west locker wall",
    ),
)


def segments_for_scope(scope: str = "opening") -> Tuple[WalkSegment, ...]:
    if scope == "opening":
        return OPENING_WALK_SEGMENTS
    if scope == "extended":
        return EXTENDED_PLACE_WALK_SEGMENTS
    if scope == "armory":
        return VAULT_ARMORY_WALK_SEGMENTS
    if scope == "all":
        return ALL_WALK_SEGMENTS
    raise ValueError(f"Unknown scope {scope!r}; expected opening, extended, armory, or all")


def compute_route_rows(
    segments: Sequence[WalkSegment] = OPENING_WALK_SEGMENTS,
    run_speed_mps: float = RUN_SPEED_MPS,
    walk_speed_mps: float = WALK_SPEED_MPS,
) -> List[Dict[str, Any]]:
    """Compute heading (deg & rad), cardinal, 2D/3D distance, measured-speed hold durations, and safe overshoot."""
    if run_speed_mps <= 0.0 or walk_speed_mps <= 0.0:
        raise ValueError("Speeds must be positive")
    rows: List[Dict[str, Any]] = []
    for seg in segments:
        hdg_deg = compass_heading_deg(seg.start, seg.target)
        hdg_rad = math.radians(hdg_deg)
        d2 = horizontal_distance(seg.start, seg.target)
        d3 = distance_3d(seg.start, seg.target)
        aim_deg = compass_heading_deg(seg.target, seg.aim_target) if seg.aim_target else None
        aim_dist = distance_3d(seg.target, seg.aim_target) if seg.aim_target else None
        rows.append({
            "leg_id": seg.leg_id,
            "seg_id": seg.seg_id,
            "zone": seg.zone,
            "label": seg.label,
            "start": [round(c, 3) for c in seg.start],
            "target": [round(c, 3) for c in seg.target],
            "start_yaw_deg": seg.start_yaw_deg,
            "heading_deg": round(hdg_deg, 2),
            "heading_rad": round(hdg_rad, 4),
            "cardinal": compass_cardinal(hdg_deg),
            "distance_2d_m": round(d2, 2),
            "distance_3d_m": round(d3, 2),
            "run_speed_mps": round(run_speed_mps, 2),
            "hold_w_run_sec": round(d2 / run_speed_mps, 2),
            "hold_w_run_fast_sec": round(d2 / MEASURED_RUN_SPEED_MAX_MPS, 2),
            "hold_w_run_slow_sec": round(d2 / MEASURED_RUN_SPEED_MIN_MPS, 2),
            "hold_w_walk_sec": round(d2 / walk_speed_mps, 2),
            "safe_overshoot_m": round(seg.safe_overshoot_m, 2),
            "overshoot_hazard": seg.overshoot_hazard,
            "aim_heading_deg": round(aim_deg, 2) if aim_deg is not None else None,
            "aim_distance_m": round(aim_dist, 2) if aim_dist is not None else None,
            "action_at_target": seg.action_at_target,
            "anchor_ref": seg.anchor_ref,
        })
    return rows


def check_route_continuity(segments: Sequence[WalkSegment] = OPENING_WALK_SEGMENTS) -> Dict[str, Any]:
    """Verify consecutive same-zone segments within each leg chain cleanly (gap <= 0.02 m) and stay finite."""
    issues: List[str] = []
    by_leg: Dict[str, List[WalkSegment]] = {}
    for seg in segments:
        by_leg.setdefault(seg.leg_id, []).append(seg)
        for pt in (seg.start, seg.target):
            if not all(math.isfinite(c) for c in pt):
                issues.append(f"{seg.seg_id}: non-finite coordinate {pt}")
        if horizontal_distance(seg.start, seg.target) < 0.1:
            issues.append(f"{seg.seg_id}: degenerate zero-length segment")

    # Within-leg continuity (skipping explicit load-door zone transitions like 9b interior -> 9c exterior roof)
    for leg_id, segs in by_leg.items():
        for a, b in zip(segs, segs[1:]):
            if a.zone != b.zone:
                continue
            gap = distance_3d(a.target, b.start)
            if gap > 0.02:
                issues.append(f"{leg_id} gap {a.seg_id}->{b.seg_id}: {gap:.3f} m > 0.02 m")

    for prev_leg, next_leg in (("L1", "L2"), ("L2", "L3"), ("L4", "L5"), ("L4", "L6"), ("L6", "L5"), ("L7", "L8")):
        if prev_leg in by_leg and next_leg in by_leg:
            gap = distance_3d(by_leg[prev_leg][-1].target, by_leg[next_leg][0].start)
            if gap > 0.02:
                issues.append(f"handoff gap {prev_leg}->{next_leg}: {gap:.3f} m > 0.02 m")

    leg_totals = {
        leg_id: round(sum(horizontal_distance(s.start, s.target) for s in segs), 2)
        for leg_id, segs in by_leg.items()
    }
    return {
        "pass": not issues,
        "segment_count": len(segments),
        "leg_totals_m": leg_totals,
        "issues": issues,
    }


def export_walk_marker_spec(
    segments: Sequence[WalkSegment] = OPENING_WALK_SEGMENTS,
    run_speed_mps: float = RUN_SPEED_MPS,
) -> Dict[str, Any]:
    """Optional diagnostic XMarkerHeading walk-marker spec so an automated driver can turn to each leg waypoint."""
    markers: List[Dict[str, Any]] = []
    rows = compute_route_rows(segments, run_speed_mps=run_speed_mps)
    for idx, row in enumerate(rows, start=1):
        markers.append({
            "index": idx,
            "edid": f"FO4SF_WalkMarker_{row['seg_id']}",
            "leg_id": row["leg_id"],
            "zone": row["zone"],
            "pos": row["target"],
            "heading_deg": row["heading_deg"],
            "heading_rad": row["heading_rad"],
            "hold_w_run_sec": row["hold_w_run_sec"],
            "safe_overshoot_m": row["safe_overshoot_m"],
            "action_at_target": row["action_at_target"],
        })
    return {
        "schema": "fo4sf_walk_markers_v1",
        "optional_diagnostic_only": True,
        "run_speed_mps": round(run_speed_mps, 2),
        "measured_run_speed_range_mps": [MEASURED_RUN_SPEED_MIN_MPS, MEASURED_RUN_SPEED_MAX_MPS],
        "marker_count": len(markers),
        "markers": markers,
    }


def _pt_in_tri_2d(px: float, py: float, a: Point3, b: Point3, c: Point3) -> Optional[float]:
    v0x, v0y = c[0] - a[0], c[1] - a[1]
    v1x, v1y = b[0] - a[0], b[1] - a[1]
    v2x, v2y = px - a[0], py - a[1]
    d00 = v0x * v0x + v0y * v0y
    d01 = v0x * v1x + v0y * v1y
    d02 = v0x * v2x + v0y * v2y
    d11 = v1x * v1x + v1y * v1y
    d12 = v1x * v2x + v1y * v2y
    den = d00 * d11 - d01 * d01
    if abs(den) < 1e-12:
        return None
    inv = 1.0 / den
    u = (d11 * d02 - d01 * d12) * inv
    v = (d00 * d12 - d01 * d02) * inv
    if u >= -0.02 and v >= -0.02 and (u + v) <= 1.02:
        return a[2] + u * (c[2] - a[2]) + v * (b[2] - a[2])
    return None


def verify_exterior_navm_segments(
    fo4_esm: Path,
    segments: Sequence[WalkSegment] = OPENING_WALK_SEGMENTS,
    step_m: float = 0.5,
) -> Dict[str, Any]:
    """Read-only offline check: verify every exterior_commonwealth segment stays 100% on Fallout4.esm WRLD 0x3C NAVM."""
    src_root = Path(__file__).resolve().parents[2] / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from fo4sf.planet.esm import Plugin, Record  # noqa: E402

    ext_segs = [s for s in segments if s.zone == "exterior_commonwealth"]
    if not ext_segs:
        return {"pass": True, "cells": 0, "triangles": 0, "sampled_points": 0, "hits": 0, "issues": []}

    min_x = min(min(s.start[0], s.target[0]) for s in ext_segs) - 90.0
    max_x = max(max(s.start[0], s.target[0]) for s in ext_segs) + 90.0
    min_y = min(min(s.start[1], s.target[1]) for s in ext_segs) - 90.0
    max_y = max(max(s.start[1], s.target[1]) for s in ext_segs) + 90.0

    all_tris: List[Tuple[Point3, Point3, Point3]] = []
    navm_cells = 0
    with Plugin(str(fo4_esm)) as plg:
        in_cw = False
        for s, e in plg.groups.get("WRLD", []):
            for item in plg.walk(s, e):
                if item[0] != "REC":
                    continue
                _, off, sig, _ = item
                if sig == b"WRLD":
                    in_cw = (Record.parse(plg.buf, off).formid == 0x0000003C)
                elif sig == b"NAVM" and in_cw:
                    rec = Record.parse(plg.buf, off)
                    nvnm = next((d for st, d in rec.subs if st == b"NVNM"), None)
                    if not nvnm or len(nvnm) < 24:
                        continue
                    nv = struct.unpack_from("<I", nvnm, 16)[0]
                    if nv == 0:
                        continue
                    vx0, vy0, _ = struct.unpack_from("<3f", nvnm, 20)
                    mx0 = vx0 * FO4_TO_SF_SCALE + MERGE_OFFSET_X
                    my0 = vy0 * FO4_TO_SF_SCALE + MERGE_OFFSET_Y
                    if not (min_x <= mx0 <= max_x and min_y <= my0 <= max_y):
                        continue
                    verts = [
                        (x * FO4_TO_SF_SCALE + MERGE_OFFSET_X, y * FO4_TO_SF_SCALE + MERGE_OFFSET_Y, z * FO4_TO_SF_SCALE)
                        for x, y, z in (struct.unpack_from("<3f", nvnm, 20 + i * 12) for i in range(nv))
                    ]
                    nt_off = 20 + nv * 12
                    nt = struct.unpack_from("<I", nvnm, nt_off)[0]
                    navm_cells += 1
                    for i in range(nt):
                        v0, v1, v2 = struct.unpack_from("<3H", nvnm, nt_off + 4 + i * FO4_NAVM_V15_STRIDE)
                        if v0 < nv and v1 < nv and v2 < nv:
                            all_tris.append((verts[v0], verts[v1], verts[v2]))

    issues: List[str] = []
    if not all_tris:
        issues.append("Fallout4.esm missing Commonwealth WRLD 0x0000003C NAVM triangles in route bounds")
        return {"pass": False, "cells": 0, "triangles": 0, "sampled_points": 0, "hits": 0, "issues": issues}

    cell_sz = 4.0
    grid: Dict[Tuple[int, int], List[int]] = {}
    for idx, (a, b, c) in enumerate(all_tris):
        gx0 = int(math.floor(min(a[0], b[0], c[0]) / cell_sz))
        gx1 = int(math.floor(max(a[0], b[0], c[0]) / cell_sz))
        gy0 = int(math.floor(min(a[1], b[1], c[1]) / cell_sz))
        gy1 = int(math.floor(max(a[1], b[1], c[1]) / cell_sz))
        for gx in range(gx0, gx1 + 1):
            for gy in range(gy0, gy1 + 1):
                grid.setdefault((gx, gy), []).append(idx)

    total_pts = 0
    hit_pts = 0
    for seg in ext_segs:
        d = horizontal_distance(seg.start, seg.target)
        steps = max(2, int(math.ceil(d / step_m)))
        seg_miss = 0
        for i in range(steps + 1):
            t = i / steps
            px = seg.start[0] + t * (seg.target[0] - seg.start[0])
            py = seg.start[1] + t * (seg.target[1] - seg.start[1])
            total_pts += 1
            gx = int(math.floor(px / cell_sz))
            gy = int(math.floor(py / cell_sz))
            hit = False
            for idx in grid.get((gx, gy), ()):
                a, b, c = all_tris[idx]
                if _pt_in_tri_2d(px, py, a, b, c) is not None:
                    hit = True
                    break
            if hit:
                hit_pts += 1
            else:
                seg_miss += 1
        if seg_miss > 0:
            issues.append(f"Commonwealth WRLD 0x3C NAVM miss on seg {seg.seg_id}: {seg_miss}/{steps + 1}")

    return {
        "pass": not issues,
        "cells": navm_cells,
        "triangles": len(all_tris),
        "sampled_points": total_pts,
        "hits": hit_pts,
        "issues": issues,
    }


def verify_museum_navm_segments(
    fo4_esm: Path,
    segments: Sequence[WalkSegment] = EXTENDED_PLACE_WALK_SEGMENTS,
    step_m: float = 0.25,
    z_tol_m: float = 1.25,
) -> Dict[str, Any]:
    """Read-only offline 3D check: verify every interior_museum segment stays 100% on ConcordMuseum01 NAVM (0x017DF7)."""
    src_root = Path(__file__).resolve().parents[2] / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from fo4sf.planet.esm import Plugin, Record  # noqa: E402

    mus_segs = [s for s in segments if s.zone == "interior_museum"]
    if not mus_segs:
        return {"pass": True, "triangles": 0, "sampled_points": 0, "hits": 0, "max_step_dz_m": 0.0, "issues": []}

    tris: List[Tuple[Point3, Point3, Point3]] = []
    with Plugin(str(fo4_esm)) as plg:
        in_mus = False
        for s, e in plg.groups.get("CELL", []):
            for item in plg.walk(s, e):
                if item[0] != "REC":
                    continue
                _, off, sig, _ = item
                if sig == b"CELL":
                    in_mus = (Record.parse(plg.buf, off).formid == 0x017DF7)
                elif sig == b"NAVM" and in_mus:
                    rec = Record.parse(plg.buf, off)
                    nvnm = next((d for st, d in rec.subs if st == b"NVNM"), None)
                    if not nvnm or len(nvnm) < 24:
                        continue
                    nv = struct.unpack_from("<I", nvnm, 16)[0]
                    verts = [
                        tuple(c * FO4_TO_SF_SCALE for c in struct.unpack_from("<3f", nvnm, 20 + i * 12))
                        for i in range(nv)
                    ]
                    nt_off = 20 + nv * 12
                    nt = struct.unpack_from("<I", nvnm, nt_off)[0]
                    for i in range(nt):
                        v0, v1, v2 = struct.unpack_from("<3H", nvnm, nt_off + 4 + i * FO4_NAVM_V15_STRIDE)
                        if v0 < nv and v1 < nv and v2 < nv:
                            tris.append((verts[v0], verts[v1], verts[v2]))

    issues: List[str] = []
    if not tris:
        issues.append("Fallout4.esm missing ConcordMuseum01 (0x017DF7) NAVM triangles")
        return {"pass": False, "triangles": 0, "sampled_points": 0, "hits": 0, "max_step_dz_m": 0.0, "issues": issues}

    total_pts = 0
    hit_pts = 0
    max_step_dz = 0.0
    for seg in mus_segs:
        d = horizontal_distance(seg.start, seg.target)
        steps = max(2, int(math.ceil(d / step_m)))
        seg_miss = 0
        prev_z: Optional[float] = None
        for i in range(steps + 1):
            t = i / steps
            px = seg.start[0] + t * (seg.target[0] - seg.start[0])
            py = seg.start[1] + t * (seg.target[1] - seg.start[1])
            exp_z = seg.start[2] + t * (seg.target[2] - seg.start[2])
            ref_z = prev_z if prev_z is not None else exp_z
            total_pts += 1
            best_z: Optional[float] = None
            for a, b, c in tris:
                z = _pt_in_tri_2d(px, py, a, b, c)
                if z is not None and abs(z - ref_z) <= z_tol_m:
                    if best_z is None or abs(z - exp_z) < abs(best_z - exp_z):
                        best_z = z
            if best_z is not None:
                hit_pts += 1
                if prev_z is not None:
                    max_step_dz = max(max_step_dz, abs(best_z - prev_z))
                prev_z = best_z
            else:
                seg_miss += 1
        if seg_miss > 0:
            issues.append(f"ConcordMuseum01 3D NAVM miss on seg {seg.seg_id}: {seg_miss}/{steps + 1}")

    return {
        "pass": not issues,
        "triangles": len(tris),
        "sampled_points": total_pts,
        "hits": hit_pts,
        "max_step_dz_m": round(max_step_dz, 3),
        "issues": issues,
    }


def _read_vault111_navm_metrics(
    fo4_esm: Path,
    segments: Sequence[WalkSegment] = OPENING_WALK_SEGMENTS,
) -> Dict[str, Any]:
    src_root = Path(__file__).resolve().parents[2] / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from fo4sf.planet.esm import Plugin, Record, zstring  # noqa: E402

    verts: List[Point3] = []
    tris: List[Tuple[int, int, int]] = []
    with Plugin(str(fo4_esm)) as plg:
        cur = None
        for s, e in plg.groups.get("CELL", []):
            for item in plg.walk(s, e):
                if item[0] != "REC":
                    continue
                _, off, sig, _ = item
                if sig == b"CELL":
                    rec = Record.parse(plg.buf, off)
                    edid = next((zstring(d) for st, d in rec.subs if st == b"EDID"), "")
                    cur = edid if edid == "Vault111Cryo" else None
                elif sig == b"NAVM" and cur:
                    rec = Record.parse(plg.buf, off)
                    if rec.formid != 0x000B11DC:
                        continue
                    nvnm = next(d for st, d in rec.subs if st == b"NVNM")
                    nv = struct.unpack_from("<I", nvnm, 16)[0]
                    verts = [
                        tuple(c * FO4_TO_SF_SCALE for c in struct.unpack_from("<3f", nvnm, 20 + i * 12))
                        for i in range(nv)
                    ]
                    nt_off = 20 + nv * 12
                    nt = struct.unpack_from("<I", nvnm, nt_off)[0]
                    tris = [
                        struct.unpack_from("<3H", nvnm, nt_off + 4 + i * FO4_NAVM_V15_STRIDE)
                        for i in range(nt)
                    ]

    issues: List[str] = []
    if not tris:
        return {
            "pass": False,
            "triangles": 0,
            "sampled_points": 0,
            "hits": 0,
            "max_step_dz_m": 0.0,
            "issues": ["Fallout4.esm missing Vault111Cryo NAVM 0x000B11DC"],
        }

    total_pts = 0
    hit_pts = 0
    max_step_dz = 0.0
    for seg in segments:
        if seg.zone != "interior_vault111":
            continue
        d = horizontal_distance(seg.start, seg.target)
        steps = max(2, int(d / 0.25))
        seg_miss = 0
        prev_z: Optional[float] = None
        for i in range(steps + 1):
            t = i / steps
            px = seg.start[0] + t * (seg.target[0] - seg.start[0])
            py = seg.start[1] + t * (seg.target[1] - seg.start[1])
            exp_z = seg.start[2] + t * (seg.target[2] - seg.start[2])
            total_pts += 1
            best_z: Optional[float] = None
            for a, b, c in tris:
                z = _pt_in_tri_2d(px, py, verts[a], verts[b], verts[c])
                if z is not None:
                    if best_z is None or abs(z - exp_z) < abs(best_z - exp_z):
                        best_z = z
            if best_z is not None:
                hit_pts += 1
                if prev_z is not None:
                    max_step_dz = max(max_step_dz, abs(best_z - prev_z))
                prev_z = best_z
            else:
                seg_miss += 1
        if seg_miss > 0:
            issues.append(f"Vault111Cryo NAVM miss on seg {seg.seg_id}: {seg_miss}/{steps + 1}")

    return {
        "pass": not issues,
        "triangles": len(tris),
        "sampled_points": total_pts,
        "hits": hit_pts,
        "max_step_dz_m": round(max_step_dz, 3),
        "issues": issues,
    }


def verify_against_staged_esms(
    newgame_esm: Optional[Path] = None,
    mission_esm: Optional[Path] = None,
    core_esm: Optional[Path] = None,
    fo4_esm: Optional[Path] = None,
    tolerance_m: float = 0.05,
    scope: str = "opening",
) -> Dict[str, Any]:
    """Read-only binary parity check against staged ESMs and optional Fallout4.esm NAVMs."""
    src_root = Path(__file__).resolve().parents[2] / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from fo4sf.planet.esm import Plugin, Record  # noqa: E402

    segs = segments_for_scope(scope)
    issues: List[str] = []
    checked: Dict[str, Any] = {}

    def _read_ref_positions(esm_path: Path, want_local_ids: Sequence[int]) -> Dict[int, Point3]:
        want = set(want_local_ids)
        found: Dict[int, Point3] = {}
        with Plugin(str(esm_path)) as plg:
            for grp in ("CELL", "WRLD"):
                for s, e in plg.groups.get(grp, []):
                    for item in plg.walk(s, e):
                        if item[0] != "REC":
                            continue
                        _, off, sig, _ = item
                        if sig not in (b"REFR", b"ACHR"):
                            continue
                        rec = Record.parse(plg.buf, off)
                        lid = rec.formid & 0xFFFFFF
                        if lid not in want:
                            continue
                        data = next((d for st, d in rec.subs if st == b"DATA" and len(d) >= 24), None)
                        if data:
                            x, y, z = struct.unpack_from("<3f", data, 0)
                            found[lid] = (x, y, z)
        return found

    if newgame_esm is not None:
        ng = _read_ref_positions(newgame_esm, (0x00080F, 0x000819))
        for lid, anchor_key in ((0x00080F, "v111_pipboy_pickup"), (0x000819, "v111_geardoor_console")):
            exp = BINARY_ANCHORS[anchor_key]["pos"]
            got = ng.get(lid)
            if got is None:
                issues.append(f"FO4SFNewGame.esm missing 0x{lid:06X} ({anchor_key})")
            else:
                err = distance_3d(got, exp)
                checked[anchor_key] = {"err_m": round(err, 4)}
                if err > tolerance_m:
                    issues.append(f"{anchor_key}: binary {got} vs table {exp} (err={err:.3f} m)")

    if mission_esm is not None:
        ms = _read_ref_positions(mission_esm, (0x000802, 0x000811))
        for lid, anchor_key in ((0x000811, "sanctuary_codsworth"), (0x000802, "concord_preston_museum_door")):
            exp = BINARY_ANCHORS[anchor_key]["pos"]
            got_raw = ms.get(lid)
            if got_raw is None:
                issues.append(f"FO4SFMission.esm missing 0x{lid:06X} ({anchor_key})")
            else:
                got_merged = (
                    got_raw if (got_raw[0] < -1500.0 and got_raw[1] < -1000.0)
                    else (got_raw[0] + MERGE_OFFSET_X, got_raw[1] + MERGE_OFFSET_Y, got_raw[2])
                )
                err = distance_3d(got_merged, exp)
                checked[anchor_key] = {"err_m": round(err, 4)}
                if err > tolerance_m:
                    issues.append(f"{anchor_key}: binary {got_merged} vs table {exp} (err={err:.3f} m)")

    if core_esm is not None:
        core_want = [0x014BA7, 0x005199, 0x0A775C]
        core_pairs = [
            (0x014BA7, "v111_creek_footbridge"),
            (0x005199, "sanctuary_north_bridge"),
            (0x0A775C, "concord_map_marker"),
        ]
        if scope in ("extended", "all"):
            core_want.extend([0x005C50, 0x008913, 0x005119])
            core_pairs.extend([
                (0x005C50, "sanctuary_workbench"),
                (0x008913, "museum_roof_power_armor"),
                (0x005119, "museum_roof_minigun"),
            ])
        cr = _read_ref_positions(core_esm, core_want)
        for lid, anchor_key in core_pairs:
            exp = BINARY_ANCHORS[anchor_key]["pos"]
            got_raw = cr.get(lid)
            if got_raw is None:
                issues.append(f"FO4TerrainCore.esm missing 0x{lid:06X} ({anchor_key})")
            else:
                got_merged = (got_raw[0] + MERGE_OFFSET_X, got_raw[1] + MERGE_OFFSET_Y, got_raw[2])
                err = distance_3d(got_merged, exp)
                checked[anchor_key] = {"err_m": round(err, 4)}
                if err > tolerance_m:
                    issues.append(f"{anchor_key}: binary {got_merged} vs table {exp} (err={err:.3f} m)")

    navm_summary: Optional[Dict[str, Any]] = None
    ext_navm_summary: Optional[Dict[str, Any]] = None
    museum_navm_summary: Optional[Dict[str, Any]] = None
    if fo4_esm is not None:
        if any(s.zone == "interior_vault111" for s in segs):
            v111_segs = tuple(segs) if scope != "all" else tuple(OPENING_WALK_SEGMENTS) + VAULT_ARMORY_WALK_SEGMENTS
            v111_res = _read_vault111_navm_metrics(fo4_esm, segments=v111_segs)
            navm_summary = {
                "triangles": v111_res["triangles"],
                "sampled_points": v111_res["sampled_points"],
                "hits": v111_res["hits"],
                "max_step_dz_m": v111_res["max_step_dz_m"],
            }
            issues.extend(v111_res["issues"])
        if any(s.zone == "exterior_commonwealth" for s in segs):
            ext_res = verify_exterior_navm_segments(fo4_esm, segments=segs)
            ext_navm_summary = {
                "cells": ext_res["cells"],
                "triangles": ext_res["triangles"],
                "sampled_points": ext_res["sampled_points"],
                "hits": ext_res["hits"],
            }
            issues.extend(ext_res["issues"])
        if any(s.zone == "interior_museum" for s in segs):
            mus_res = verify_museum_navm_segments(fo4_esm, segments=segs)
            museum_navm_summary = {
                "triangles": mus_res["triangles"],
                "sampled_points": mus_res["sampled_points"],
                "hits": mus_res["hits"],
                "max_step_dz_m": mus_res["max_step_dz_m"],
            }
            issues.extend(mus_res["issues"])

    result: Dict[str, Any] = {
        "pass": not issues,
        "checked_anchors": checked,
        "vault111_navm": navm_summary,
        "commonwealth_navm": ext_navm_summary,
        "issues": issues,
    }
    if museum_navm_summary is not None:
        result["museum_navm"] = museum_navm_summary
    return result


def _read_quest_objective_targets(esm_path: Path, want_edids: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
    src_root = Path(__file__).resolve().parents[2] / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from fo4sf.planet.esm import Plugin, Record, zstring  # noqa: E402

    want = set(want_edids)
    out: Dict[str, List[Dict[str, Any]]] = {}
    with Plugin(str(esm_path)) as plg:
        for s, e in plg.groups.get("QUST", []):
            for item in plg.walk(s, e):
                if item[0] != "REC" or item[2] != b"QUST":
                    continue
                rec = Record.parse(plg.buf, item[1])
                edid = next((zstring(d) for st, d in rec.subs if st == b"EDID"), "")
                if edid not in want:
                    continue
                objs: List[Dict[str, Any]] = []
                cur: Optional[Dict[str, Any]] = None
                for st, d in rec.subs:
                    if st == b"QOBJ" and len(d) >= 2:
                        cur = {"index": struct.unpack_from("<H", d, 0)[0], "text": "", "target_aliases": []}
                        objs.append(cur)
                    elif st == b"NNAM" and cur is not None:
                        cur["text"] = zstring(d)
                    elif st == b"QSTA" and cur is not None and len(d) >= 4:
                        cur["target_aliases"].append(struct.unpack_from("<i", d, 0)[0])
                out[edid] = objs
    return out


def audit_vault111_handplay(
    newgame_esm: Optional[Path] = None,
    mission_esm: Optional[Path] = None,
    port_esm: Optional[Path] = None,
    core_esm: Optional[Path] = None,
    fo4_esm: Optional[Path] = None,
    exitlift_esm: Optional[Path] = None,
    newgame_psc: Optional[Path] = None,
) -> Dict[str, Any]:
    """Offline A3 Vault Exit Hand-Play Proof: geometry, doors, reach, lift control, objective markers & honest game boundary."""
    src_root = Path(__file__).resolve().parents[2] / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from fo4sf.planet.esm import Plugin, Record, zstring  # noqa: E402

    if newgame_psc is None:
        newgame_psc = Path(__file__).resolve().parent / "FO4SF_NewGameQuest.psc"

    issues: List[str] = []
    gaps: List[str] = []

    # 1. First-person standing eye-height reach to Pip-Boy (0A00080F) & Gear Door Console (0A000819)
    by_id = {s.seg_id: s for s in OPENING_WALK_SEGMENTS}
    reach_checks: Dict[str, Any] = {}
    for seg_id, label in (("1g", "pipboy_0A00080F"), ("2a", "console_0A000819")):
        seg = by_id[seg_id]
        assert seg.aim_target is not None
        eye = (seg.target[0], seg.target[1], seg.target[2] + PLAYER_EYE_HEIGHT_M)
        d3 = distance_3d(eye, seg.aim_target)
        dh = horizontal_distance(seg.target, seg.aim_target)
        pitch_deg = math.degrees(math.atan2(seg.aim_target[2] - eye[2], max(dh, 1e-6)))
        ok = d3 <= FIRST_PERSON_REACH_M
        reach_checks[label] = {
            "eye_pos": [round(c, 3) for c in eye],
            "target_pos": [round(c, 3) for c in seg.aim_target],
            "reach_3d_m": round(d3, 3),
            "pitch_deg": round(pitch_deg, 1),
            "within_2m_reach": ok,
        }
        if not ok:
            issues.append(f"{label} eye-to-target reach {d3:.2f} m exceeds {FIRST_PERSON_REACH_M:.2f} m")

    # 2. Lift platform boarding & Stay step-off re-entry check (FO4SF_NewGameQuest.psc)
    psc_text = newgame_psc.read_text(encoding="utf-8") if newgame_psc.exists() else ""
    m_rad = re.search(r"float\s+Property\s+PlatformRadius\s*=\s*([0-9.]+)", psc_text)
    plat_radius = float(m_rad.group(1)) if m_rad else 0.0
    has_stay_stepoff = (
        "bool onPlatform = Near(player, PlatformX, PlatformY, PlatformZ, PlatformRadius)" in psc_text
        and "if !onPlatform\n        asked = false" in psc_text.replace("\r\n", "\n")
    )
    dead_lift_handler_absent = (
        "HandleLiftControlActivate" not in psc_text
        and "liftRegistered" not in psc_text
        and "liftWatchedRef" not in psc_text
    )
    lift_seg = by_id["3f"]
    lift_anchor = BINARY_ANCHORS["v111_exit_lift_platform"]["pos"]
    lift_err = distance_3d(lift_seg.target, lift_anchor)
    # Check FO4SFExitLift.esm ACTI 0x0100E0E6 FULL subrecord (FO4 VltElevator 0x0244EF has FULL == "", so no crosshair [E] prompt)
    lift_base_full: Optional[str] = None
    if exitlift_esm is not None and exitlift_esm.exists():
        with Plugin(str(exitlift_esm)) as plg:
            for s, e in plg.groups.get("ACTI", []):
                for item in plg.walk(s, e):
                    if item[0] == "REC" and item[2] == b"ACTI":
                        rec = Record.parse(plg.buf, item[1])
                        if (rec.formid & 0xFFFFFF) == 0x00E0E6:
                            full_bytes = next((d for st, d in rec.subs if st == b"FULL"), None)
                            lift_base_full = zstring(full_bytes) if full_bytes is not None else ""
    lift_check = {
        "platform_radius_m": plat_radius,
        "target_to_platform_center_m": round(lift_err, 4),
        "near_dz_tolerance_m": 3.0 if "dz < 3.0 && dz > -3.0" in psc_text else None,
        "auto_platform_prompt_preserved": "PromptVaultExitLift(player)" in psc_text,
        "stay_stepoff_reentry_wired": has_stay_stepoff,
        "dead_lift_onactivate_removed": dead_lift_handler_absent,
        "retrigger_after_stay": "step >2.0 m out of open cage entrance (resets asked=false in InVault) and step back onto platform; matches FO4 RespecTriggerREF 0x08C94A & Vault111AscendAgainTriggerREF 0x09A149",
        "lift_base_0x0100E0E6_full_name": lift_base_full,
        "lift_base_has_full_name": bool(lift_base_full) if lift_base_full is not None else False,
    }
    if plat_radius < 1.5 or lift_err > plat_radius:
        issues.append(f"Exit lift target err {lift_err:.3f} m outside PlatformRadius {plat_radius:.2f} m")
    if not has_stay_stepoff:
        issues.append("FO4SF_NewGameQuest.psc missing InVault PlatformRadius Stay step-off reset (asked = false)")
    if not dead_lift_handler_absent:
        issues.append("FO4SF_NewGameQuest.psc still contains dead lift OnActivate handler")

    # 3. Vault 111 corridor door states in FO4Port.esm (optional binary read)
    door_checks: Dict[str, Any] = {}
    if port_esm is not None and port_esm.exists():
        want_doors = {0x00126E: "door_1_V111Door01", 0x001234: "door_2_V111DoorSpecial01", 0x001608: "door_3_V111DoorSpecial01_ONAM", 0x00126D: "gear_door_VltGearDoor01"}
        with Plugin(str(port_esm)) as plg:
            in_v111 = False
            for s, e in plg.groups.get("CELL", []):
                for item in plg.walk(s, e):
                    if item[0] != "REC":
                        continue
                    _, off, sig, _ = item
                    if sig == b"CELL":
                        edid = next((zstring(d) for st, d in Record.parse(plg.buf, off).subs if st == b"EDID"), "")
                        in_v111 = (edid == "FO4Port_Vault111Cryo")
                    elif in_v111 and sig == b"REFR":
                        rec = Record.parse(plg.buf, off)
                        lid = rec.formid & 0xFFFFFF
                        if lid in want_doors:
                            xloc = next((d for st, d in rec.subs if st == b"XLOC"), None)
                            lock_lvl = xloc[0] if xloc else 0
                            onam = any(st == b"ONAM" for st, _ in rec.subs)
                            door_checks[want_doors[lid]] = {
                                "local_id": f"0x{lid:06X}",
                                "lock_level": lock_lvl,
                                "open_by_default": onam,
                                "unlocked": lock_lvl == 0,
                            }
                            if lock_lvl != 0:
                                issues.append(f"Vault 111 door {want_doors[lid]} has unexpected lock level {lock_lvl}")

    # 4. Objective marker audit across FO4SFNewGame.esm & FO4SFMission.esm (honest gap reporting)
    objective_markers: Dict[str, Any] = {}
    if newgame_esm is not None and newgame_esm.exists():
        ng_objs = _read_quest_objective_targets(newgame_esm, ("FO4SF_NewGame",))
        objective_markers.update(ng_objs)
        for obj in ng_objs.get("FO4SF_NewGame", []):
            if not obj["target_aliases"]:
                gaps.append(
                    f"FO4SF_NewGame Obj {obj['index']} ({obj['text']!r}) has 0 QSTA compass targets "
                    "(player navigates Vault 111 corridor by sight + catwalk hint; stage-driven Pip-Boy/Console/Lift compass markers belong in S2/2h)"
                )
    if mission_esm is not None and mission_esm.exists():
        ms_objs = _read_quest_objective_targets(mission_esm, ("FO4SF_Codsworth01", "FO4SF_Min00", "FO4SF_Sanctuary01"))
        objective_markers.update(ms_objs)
        for qname, objs in ms_objs.items():
            for obj in objs:
                if not obj["target_aliases"]:
                    gaps.append(
                        f"{qname} Obj {obj['index']} ({obj['text']!r}) has 0 QSTA compass targets "
                        "(relies on hostile compass dots in combat)"
                    )

    # 5. Navmesh step-height & zero-jump verification (Vault 111 + Museum)
    navm_checks: Dict[str, Any] = {}
    if fo4_esm is not None and fo4_esm.exists():
        v111 = _read_vault111_navm_metrics(fo4_esm)
        navm_checks["vault111"] = v111
        if not v111["pass"]:
            issues.extend(v111["issues"])
        if v111["max_step_dz_m"] > STARFIELD_MAX_STEP_HEIGHT_M:
            issues.append(f"Vault 111 max step dz {v111['max_step_dz_m']} m > {STARFIELD_MAX_STEP_HEIGHT_M} m")
        mus = verify_museum_navm_segments(fo4_esm, segments=EXTENDED_PLACE_WALK_SEGMENTS)
        navm_checks["museum"] = mus
        if not mus["pass"]:
            issues.extend(mus["issues"])
        if mus["max_step_dz_m"] > STARFIELD_MAX_STEP_HEIGHT_M:
            issues.append(f"Museum max step dz {mus['max_step_dz_m']} m > {STARFIELD_MAX_STEP_HEIGHT_M} m")

    only_game_can_prove = [
        "Live Starfield physics & door-leaf collision clearance on FO4Port_V111Door01 (0200126E) and FO4Port_V111DoorSpecial01 (02001234) when opened by first-person E (2g used moveto past L1).",
        "Live Starfield capsule walk through open VltGearDoor01 (0200126D), down the Vault 111 catwalk stairs (3c-3e), and across the elevator threshold onto vltelevator_anim.nif without setpos (2g used setpos onto the lift).",
        "Live Stay-and-reenter lift loop on foot: stepping >2.0 m out of the open cage entrance (resetting asked=false in InVault) and stepping back onto the platform to re-open ExitMessage (ACTI 0x0100E0E6 has no FULL display name, matching FO4's buttonless RespecTriggerREF 0x08C94A / Vault111AscendAgainTriggerREF 0x09A149 design).",
        "Converted Commonwealth terrain collision & height continuity on L4 (Vault 111 switchback -> footbridge -> Sanctuary) and L5c-L5k (Sanctuary North Bridge -> Red Rocket -> Concord); only 5a/5b ran on foot in 2g.",
        "Live door/collision walkability inside Sanctuary houses (L6) and Concord Museum of Freedom stairs/basement/roof (L7-L9) once FO4Port.esm + promoted museum doors are bundled in 2h.",
        "Live player navigation inside Vault 111 without compass targets on FO4SF_NewGame Objective 10 ('Leave Vault 111').",
    ]

    return {
        "pass": not issues,
        "offline_only_unproven_in_game": True,
        "first_person_reach": reach_checks,
        "lift_platform": lift_check,
        "vault111_doors": door_checks,
        "objective_markers": objective_markers,
        "navmesh_steps": navm_checks,
        "known_offline_gaps": gaps,
        "only_game_can_prove": only_game_can_prove,
        "issues": issues,
    }


def format_markdown_table(rows: Sequence[Dict[str, Any]], run_speed_mps: float = RUN_SPEED_MPS) -> str:
    lines = [
        f"| Leg | Seg | Segment | Start `(x, y, z)` | Target `(x, y, z)` | `GetAngle Z` (deg / rad) | Dist (m) | Hold `W` (s @ {run_speed_mps:.1f} m/s) | Safe Overshoot (m) | Action at Target |",
        "|---|---|---|---|---|---:|---:|---:|---|---|",
    ]
    for r in rows:
        sp = f"({r['start'][0]:.2f}, {r['start'][1]:.2f}, {r['start'][2]:.2f})"
        tp = f"({r['target'][0]:.2f}, {r['target'][1]:.2f}, {r['target'][2]:.2f})"
        hdg = f"**{r['heading_deg']:.1f} deg** {r['cardinal']} (`{r['heading_rad']:.4f}`)"
        ov = f"**{r['safe_overshoot_m']:.1f} m** ({r['overshoot_hazard']})" if r["overshoot_hazard"] else f"{r['safe_overshoot_m']:.1f} m"
        lines.append(
            f"| {r['leg_id']} | `{r['seg_id']}` | {r['label']} | `{sp}` | `{tp}` | {hdg} | {r['distance_2d_m']:.2f} | {r['hold_w_run_sec']:.1f} | {ov} | {r['action_at_target']} |"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute & verify console-free walking headings, overshoot margins, and A3 hand-play proof.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    for cmd_name, help_txt in (
        ("table", "Print Markdown table of obstacle-free walking segments."),
        ("json", "Print JSON payload of continuity check and computed segment headings."),
        ("export-markers-json", "Print optional diagnostic walk-marker spec JSON."),
    ):
        p = sub.add_parser(cmd_name, help=help_txt)
        p.add_argument("--scope", choices=("opening", "extended", "armory", "all"), default="opening")
        p.add_argument("--run-speed", type=float, default=RUN_SPEED_MPS, help=f"Measured player run speed in m/s (default {RUN_SPEED_MPS}; 2g measured 4.6-5.0).")

    p_ver = sub.add_parser("verify", help="Verify continuity and optional binary ESM / NAVM parity.")
    p_ver.add_argument("--scope", choices=("opening", "extended", "armory", "all"), default="opening")
    p_ver.add_argument("--newgame-esm", type=Path, default=None)
    p_ver.add_argument("--mission-esm", type=Path, default=None)
    p_ver.add_argument("--core-esm", type=Path, default=None)
    p_ver.add_argument("--fo4-esm", type=Path, default=None)

    p_hp = sub.add_parser("audit-handplay", help="Run offline A3 Vault Exit Hand-Play Proof.")
    p_hp.add_argument("--newgame-esm", type=Path, default=None)
    p_hp.add_argument("--mission-esm", type=Path, default=None)
    p_hp.add_argument("--port-esm", type=Path, default=None)
    p_hp.add_argument("--core-esm", type=Path, default=None)
    p_hp.add_argument("--fo4-esm", type=Path, default=None)
    p_hp.add_argument("--exitlift-esm", type=Path, default=None)

    args = parser.parse_args(argv)

    if args.cmd == "table":
        segs = segments_for_scope(args.scope)
        print(format_markdown_table(compute_route_rows(segs, run_speed_mps=args.run_speed), run_speed_mps=args.run_speed))
        return 0
    if args.cmd == "json":
        segs = segments_for_scope(args.scope)
        cont = check_route_continuity(segs)
        payload = {
            "scope": args.scope,
            "run_speed_mps": round(args.run_speed, 2),
            "measured_run_speed_range_mps": [MEASURED_RUN_SPEED_MIN_MPS, MEASURED_RUN_SPEED_MAX_MPS],
            "continuity": cont,
            "segments": compute_route_rows(segs, run_speed_mps=args.run_speed),
        }
        print(json.dumps(payload, indent=2))
        return 0 if cont["pass"] else 1
    if args.cmd == "export-markers-json":
        segs = segments_for_scope(args.scope)
        print(json.dumps(export_walk_marker_spec(segs, run_speed_mps=args.run_speed), indent=2))
        return 0
    if args.cmd == "verify":
        segs = segments_for_scope(args.scope)
        cont = check_route_continuity(segs)
        bin_res = verify_against_staged_esms(
            newgame_esm=args.newgame_esm,
            mission_esm=args.mission_esm,
            core_esm=args.core_esm,
            fo4_esm=args.fo4_esm,
            scope=args.scope,
        )
        ok = bool(cont["pass"] and bin_res["pass"])
        print(json.dumps({"pass": ok, "scope": args.scope, "continuity": cont, "binary": bin_res}, indent=2))
        return 0 if ok else 1
    if args.cmd == "audit-handplay":
        res = audit_vault111_handplay(
            newgame_esm=args.newgame_esm,
            mission_esm=args.mission_esm,
            port_esm=args.port_esm,
            core_esm=args.core_esm,
            fo4_esm=args.fo4_esm,
            exitlift_esm=args.exitlift_esm,
        )
        print(json.dumps(res, indent=2))
        return 0 if res["pass"] else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
