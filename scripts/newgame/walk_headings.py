"""Binary-derived console-free walking headings & obstacle-free sub-segments (`A4`, Round 10).

Computes exact Starfield compass headings (`GetAngle Z` degrees and radians) and distances
for every straight walking sub-segment from New Game (Vault 111 Cryo Pod) through the end of
*When Freedom Calls* (Concord Museum of Freedom front door / Preston Garvey).

Heading convention (verified against `scripts/core/FO4SF_CoreCandidateWalk.psc:229-233`):
  fwdX = sin(heading_rad), fwdY = cos(heading_rad)
  0 deg   = North (+Y)
  90 deg  = East  (+X)
  180 deg = South (-Y)
  270 deg = West  (-X)
  heading_deg = degrees(atan2(dx, dy)) % 360.0

All interior Vault 111 segments are verified against the 1,371-triangle `Vault111Cryo` navmesh
(`NAVM 0x000B11DC`, 21-byte v15 triangle stride, scaled by 1/70 into `FO4Port_Vault111Cryo`)
and `FO4Port.esm` `DOOR` records (`ONAM` open-by-default vs closed). All exterior segments
follow the binary road/bridge centerline in `FO4TerrainCore.esm` (+ `MergeOffset = (-1200, -2700)`).
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

FO4_TO_SF_SCALE = 1.0 / 70.0
MERGE_OFFSET_X = -1200.0
MERGE_OFFSET_Y = -2700.0
FO4_NAVM_V15_STRIDE = 21

# Starfield base forward movement speeds (m/s) for driver hold-W duration estimates
WALK_SPEED_MPS = 1.60
RUN_SPEED_MPS = 3.70  # default W-hold speed (not caps-lock walking, not sprinting)

Point3 = Tuple[float, float, float]


@dataclass(frozen=True)
class WalkSegment:
    leg_id: str
    seg_id: str
    zone: str  # "interior_vault111" or "exterior_commonwealth"
    label: str
    start: Point3
    target: Point3
    start_yaw_deg: Optional[float]
    action_at_target: str
    anchor_ref: str
    aim_target: Optional[Point3] = None


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


# Binary-derived anchor coordinates (in runtime space: interior meters or merged exterior meters)
BINARY_ANCHORS: Dict[str, Dict[str, Any]] = {
    "v111_cryo_start": {
        "source": "FO4SFNewGame.esm / 2f live log (FO4Port_Vault111Cryo 020011F3)",
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
        "source": "FO4SFNewGame stage 200 / 2f live log (merged MarsPlanetWorld)",
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
}


# Complete obstacle-free straight walking sub-segments from New Game to end of When Freedom Calls
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
    ),
    WalkSegment(
        leg_id="L1",
        seg_id="1g",
        zone="interior_vault111",
        label="Climb control-deck ramp -> Pip-Boy 3000 pickup spot",
        start=(-47.000, 0.000, 0.000),
        target=(-54.000, 0.000, 0.590),
        start_yaw_deg=None,
        action_at_target="Turn to 228.8 deg SW, pitch down ~35 deg, press E on Pip-Boy 3000 (0A00080F)",
        anchor_ref="v111_pipboy_pickup",
        aim_target=(-55.049, -0.922, 0.776),
    ),
    # ---------------- LEG 2: Pip-Boy 3000 -> Vault Door Console (0A000819)
    WalkSegment(
        leg_id="L2",
        seg_id="2a",
        zone="interior_vault111",
        label="Pip-Boy pickup spot -> Gear Door Console activation stance",
        start=(-54.000, 0.000, 0.590),
        target=(-54.118, -0.588, 0.590),
        start_yaw_deg=228.8,
        action_at_target="Aim 191.3 deg SSW (level/+10 deg) at Vault Door Controls (0A000819), press E, wait ~5 s for gear door",
        anchor_ref="v111_geardoor_console",
        aim_target=(-54.364, -1.815, 1.754),
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
    ),
    WalkSegment(
        leg_id="L3",
        seg_id="3f",
        zone="interior_vault111",
        label="Lift cage entrance -> Center of Exit Lift Platform",
        start=(-74.480, -3.960, -1.610),
        target=(-77.742, -3.958, -1.751),
        start_yaw_deg=None,
        action_at_target="Stop inside PlatformRadius (2.0 m); allocate 33 SPECIAL points & click Continue to ride up",
        anchor_ref="v111_exit_lift_platform",
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
    ),
    # ---------------- LEG 5: Sanctuary (Codsworth) -> Sanctuary Bridge -> Red Rocket -> Concord Museum (Preston)
    # 100% verified offline against Fallout4.esm Commonwealth WRLD 0x0000003C NAVM (terrain unproven in game)
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
    ),
    WalkSegment(
        leg_id="L5",
        seg_id="5j",
        zone="exterior_commonwealth",
        label="Main Street junction -> Concord Map Marker (040A775C)",
        start=(-2102.000, -1642.000, 88.348),
        target=(-2061.230, -1657.460, 86.930),
        start_yaw_deg=None,
        action_at_target="Inside GiveConcordRadius (150 m); defeat 5 raiders & advance SE (128.4 deg) down Main Street",
        anchor_ref="concord_map_marker",
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
    ),
)


def compute_route_rows(segments: Sequence[WalkSegment] = OPENING_WALK_SEGMENTS) -> List[Dict[str, Any]]:
    """Compute heading (deg & rad), cardinal, 2D/3D distance, and run/walk durations for every segment."""
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
            "hold_w_run_sec": round(d2 / RUN_SPEED_MPS, 2),
            "hold_w_walk_sec": round(d2 / WALK_SPEED_MPS, 2),
            "aim_heading_deg": round(aim_deg, 2) if aim_deg is not None else None,
            "aim_distance_m": round(aim_dist, 2) if aim_dist is not None else None,
            "action_at_target": seg.action_at_target,
            "anchor_ref": seg.anchor_ref,
        })
    return rows


def check_route_continuity(segments: Sequence[WalkSegment] = OPENING_WALK_SEGMENTS) -> Dict[str, Any]:
    """Verify consecutive segments within each leg chain cleanly (gap <= 0.01 m) and stay finite."""
    issues: List[str] = []
    by_leg: Dict[str, List[WalkSegment]] = {}
    for seg in segments:
        by_leg.setdefault(seg.leg_id, []).append(seg)
        for pt in (seg.start, seg.target):
            if not all(math.isfinite(c) for c in pt):
                issues.append(f"{seg.seg_id}: non-finite coordinate {pt}")
        if horizontal_distance(seg.start, seg.target) < 0.1:
            issues.append(f"{seg.seg_id}: degenerate zero-length segment")

    # Within-leg continuity and cross-leg handoffs (L1->L2->L3 inside Vault 111; L4->L5 outdoors)
    for leg_id, segs in by_leg.items():
        for a, b in zip(segs, segs[1:]):
            gap = distance_3d(a.target, b.start)
            if gap > 0.02:
                issues.append(f"{leg_id} gap {a.seg_id}->{b.seg_id}: {gap:.3f} m > 0.02 m")

    for prev_leg, next_leg in (("L1", "L2"), ("L2", "L3"), ("L4", "L5")):
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


def export_walk_marker_spec(segments: Sequence[WalkSegment] = OPENING_WALK_SEGMENTS) -> Dict[str, Any]:
    """Optional diagnostic XMarkerHeading walk-marker spec so an automated driver can turn to each leg waypoint."""
    markers: List[Dict[str, Any]] = []
    rows = compute_route_rows(segments)
    for idx, row in enumerate(rows, start=1):
        markers.append({
            "index": idx,
            "edid": f"FO4SF_WalkMarker_{row['seg_id']}",
            "leg_id": row["leg_id"],
            "zone": row["zone"],
            "pos": row["target"],
            "heading_deg": row["heading_deg"],
            "heading_rad": row["heading_rad"],
            "action_at_target": row["action_at_target"],
        })
    return {
        "schema": "fo4sf_walk_markers_v1",
        "optional_diagnostic_only": True,
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


def verify_against_staged_esms(
    newgame_esm: Optional[Path] = None,
    mission_esm: Optional[Path] = None,
    core_esm: Optional[Path] = None,
    fo4_esm: Optional[Path] = None,
    tolerance_m: float = 0.05,
) -> Dict[str, Any]:
    """Read-only binary parity check against staged ESMs and optional Fallout4.esm Vault111Cryo NAVM."""
    src_root = Path(__file__).resolve().parents[2] / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from fo4sf.planet.esm import Plugin, Record, zstring  # noqa: E402

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
                # Mission ESM may store unmerged local coords (candidate-2f) or merged coords (post-R9/R10)
                got_merged = (
                    got_raw if (got_raw[0] < -1500.0 and got_raw[1] < -1000.0)
                    else (got_raw[0] + MERGE_OFFSET_X, got_raw[1] + MERGE_OFFSET_Y, got_raw[2])
                )
                err = distance_3d(got_merged, exp)
                checked[anchor_key] = {"err_m": round(err, 4)}
                if err > tolerance_m:
                    issues.append(f"{anchor_key}: binary {got_merged} vs table {exp} (err={err:.3f} m)")

    if core_esm is not None:
        cr = _read_ref_positions(core_esm, (0x014BA7, 0x005199, 0x0A775C))
        for lid, anchor_key in (
            (0x014BA7, "v111_creek_footbridge"),
            (0x005199, "sanctuary_north_bridge"),
            (0x0A775C, "concord_map_marker"),
        ):
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
    if fo4_esm is not None:
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
        if not tris:
            issues.append("Fallout4.esm missing Vault111Cryo NAVM 0x000B11DC")
        else:
            total_pts = 0
            hit_pts = 0
            for seg in OPENING_WALK_SEGMENTS:
                if seg.zone != "interior_vault111":
                    continue
                d = horizontal_distance(seg.start, seg.target)
                steps = max(2, int(d / 0.25))
                seg_miss = 0
                for i in range(steps + 1):
                    t = i / steps
                    px = seg.start[0] + t * (seg.target[0] - seg.start[0])
                    py = seg.start[1] + t * (seg.target[1] - seg.start[1])
                    total_pts += 1
                    if any(_pt_in_tri_2d(px, py, verts[a], verts[b], verts[c]) is not None for a, b, c in tris):
                        hit_pts += 1
                    else:
                        seg_miss += 1
                if seg_miss > 0:
                    issues.append(f"Vault111Cryo NAVM miss on seg {seg.seg_id}: {seg_miss}/{steps + 1}")
            navm_summary = {"triangles": len(tris), "sampled_points": total_pts, "hits": hit_pts}

    ext_navm_summary: Optional[Dict[str, Any]] = None
    if fo4_esm is not None:
        ext_res = verify_exterior_navm_segments(fo4_esm)
        ext_navm_summary = {
            "cells": ext_res["cells"],
            "triangles": ext_res["triangles"],
            "sampled_points": ext_res["sampled_points"],
            "hits": ext_res["hits"],
        }
        issues.extend(ext_res["issues"])

    return {
        "pass": not issues,
        "checked_anchors": checked,
        "vault111_navm": navm_summary,
        "commonwealth_navm": ext_navm_summary,
        "issues": issues,
    }


def format_markdown_table(rows: Sequence[Dict[str, Any]]) -> str:
    lines = [
        "| Leg | Seg | Segment | Start `(x, y, z)` | Target `(x, y, z)` | `GetAngle Z` (deg / rad) | Dist (m) | Hold `W` (s, run) | Action at Target |",
        "|---|---|---|---|---|---:|---:|---:|---|",
    ]
    for r in rows:
        sp = f"({r['start'][0]:.2f}, {r['start'][1]:.2f}, {r['start'][2]:.2f})"
        tp = f"({r['target'][0]:.2f}, {r['target'][1]:.2f}, {r['target'][2]:.2f})"
        hdg = f"**{r['heading_deg']:.1f} deg** {r['cardinal']} (`{r['heading_rad']:.4f}`)"
        lines.append(
            f"| {r['leg_id']} | `{r['seg_id']}` | {r['label']} | `{sp}` | `{tp}` | {hdg} | {r['distance_2d_m']:.2f} | {r['hold_w_run_sec']:.1f} | {r['action_at_target']} |"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute & verify console-free walking headings from New Game to Concord.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("table", help="Print Markdown table of all straight obstacle-free walking segments.")
    sub.add_parser("json", help="Print JSON payload of continuity check and computed segment headings.")
    sub.add_parser("export-markers-json", help="Print optional diagnostic walk-marker spec JSON.")
    p_ver = sub.add_parser("verify", help="Verify continuity and optional binary ESM / NAVM parity.")
    p_ver.add_argument("--newgame-esm", type=Path, default=None)
    p_ver.add_argument("--mission-esm", type=Path, default=None)
    p_ver.add_argument("--core-esm", type=Path, default=None)
    p_ver.add_argument("--fo4-esm", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.cmd == "table":
        print(format_markdown_table(compute_route_rows()))
        return 0
    if args.cmd == "json":
        cont = check_route_continuity()
        payload = {"continuity": cont, "segments": compute_route_rows()}
        print(json.dumps(payload, indent=2))
        return 0 if cont["pass"] else 1
    if args.cmd == "export-markers-json":
        print(json.dumps(export_walk_marker_spec(), indent=2))
        return 0
    if args.cmd == "verify":
        cont = check_route_continuity()
        bin_res = verify_against_staged_esms(
            newgame_esm=args.newgame_esm,
            mission_esm=args.mission_esm,
            core_esm=args.core_esm,
            fo4_esm=args.fo4_esm,
        )
        ok = bool(cont["pass"] and bin_res["pass"])
        print(json.dumps({"pass": ok, "continuity": cont, "binary": bin_res}, indent=2))
        return 0 if ok else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
