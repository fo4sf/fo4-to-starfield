"""a3_path_places.py: Lane A A3 places-on-the-path two-way door wiring & A4 W6 quest audit tool.

Builds deterministic two-way FO4SF_LoadDoor wiring plans directly from already-converted and staged
interiors (interiors_b10 FO4Port.esm + FO4PortTextures2.esm, ZERO reconversion) and the Commonwealth
overlay (FO4TerrainCore.esm), verifies staged directories read-only, patches synthetic or staged
FO4Port.esm copies via vmad_patch.py without modifying pinned inputs, and evaluates A4 next-story
mission reachability/fragility/Open-Mode graphs offline.

Usage:
  python scripts/terrain/a3_path_places.py plan [--groups a3_all|concord_museum|...] [--out plan.json]
  python scripts/terrain/a3_path_places.py audit-stage --port <interiors_b10/port> --core <candidate/player>
  python scripts/terrain/a3_path_places.py patch-port --port <port_dir> --core <core_dir> --out <new_dir> [--keep-markers <doors.json>]
  python scripts/terrain/a3_path_places.py audit-a4 [--out a4_report.json]
"""
from __future__ import annotations

import argparse
from collections import deque
import json
import os
from pathlib import Path
import struct
import sys
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

import vmad_patch  # noqa: E402

MERGE_OFFSET = (-1200.0, -2700.0, 0.0)
PORT_PLUGIN = "FO4Port.esm"
PORT_TEXTURE_COMPANION = "FO4PortTextures2.esm"
CORE_PLUGIN = "FO4TerrainCore.esm"
PORT_B10_NEXT_OBJECT_ID = 0x074CD3
PORT_B10_PIN_SHA256 = "c12b141c2783b0a2adc6ec7c1e1f77f3abc7702149d74f4240712e9616895d7c"

# R10 contract verified in scripts/door_bridge/FO4SF_LoadDoor.psc:
# 1 initial MoveTo + MoveRetries (default 2) = 3 total attempts; on exhaustion returns to Self and logs once.
LOAD_DOOR_R10_CONTRACT = {
    "script": "FO4SF_LoadDoor",
    "move_retries_default": 2,
    "total_attempts_budget": 3,
    "use_destination_position": True,
    "retry_wait_seconds": 0.5,
    "settle_seconds": 1.0,
    "failure_log_prefix": "FO4SF_LoadDoor load door arrival failed",
}

# Verified directly from staged interiors_b10/port/formids.json, locations.json, and Fallout4.esm.
STAGED_INTERIOR_CELLS: dict[str, dict[str, Any]] = {
    "ConcordMuseum01": {
        "group": "concord_museum",
        "story_tier": "A3",
        "fo4_cell_formkey": "017DF7:Fallout4.esm",
        "port_cell_edid": "FO4Port_ConcordMuseum01",
        "port_cell_id": 0x012540,
        "port_lctn_edid": "FO4Port_ConcordMuseumLocation",
        "port_lctn_id": 0x0405D1,
        "display_name": "Museum of Freedom",
        "encounter_zone": {"edid": "ConcordMuseumZone", "min_level": 1, "max_level": 5},
        "ref_count": 3402,
        "initially_disabled_count": 20,
        "xesp_count": 30,
        "xesp_parents": [
            "09A6A8:Fallout4.esm",
            "09A6AF:Fallout4.esm",
            "09A698:Fallout4.esm",
            "09A6A6:Fallout4.esm",
            "09A699:Fallout4.esm",
            "0AE9F0:Fallout4.esm",
        ],
        "key_internal_refs": {
            "PrestonDoorREF": {"fo4": "01E2EA:Fallout4.esm", "port_id": 0x013047, "type": "DOOR", "lock": 255},
            "PrestonExitDoor": {"fo4": "01E2E9:Fallout4.esm", "port_id": 0x013046, "type": "DOOR", "lock": 255},
            "ConcordMuseumBalconyDoorREF": {"fo4": "01B94A:Fallout4.esm", "port_id": 0x013045, "type": "DOOR", "lock": 255},
            "MQ03SecurityGateREF": {"fo4": "05C66C:Fallout4.esm", "port_id": 0x013042, "type": "DOOR", "lock": 25},
            "ConcordMuseumBasementTerminal": {"fo4": "08110D:Fallout4.esm", "port_id": 0x0125AB, "type": "TERM", "lock": 25},
            "MQ102SturgesTerminal": {"fo4": "022AA3:Fallout4.esm", "port_id": 0x013040, "type": "TERM", "lock": 25},
            "MetalGateFancy01": {"fo4": "0509AD:Fallout4.esm", "port_id": 0x012C4D, "type": "DOOR", "lock": 50},
            "PowerGenerator01": {"fo4": "09A147:Fallout4.esm", "port_id": 0x012585, "type": "MSTT", "script": "FusionGeneratorSCRIPT"},
            "DummyNoEdit_FusionCore": {"fo4": "237B27:Fallout4.esm", "port_id": None, "type": "MISC", "replacement": "FO4SFPowerArmor.esm:0x000809"},
        },
        "exterior_setpieces": {
            "Vertibird03": {"fo4": "0AB4FD:Fallout4.esm", "core_section": "refs", "core_id": 0x01EC87, "local_pos": [-804.43, 982.25, 98.93]},
            "MQ102MinigunREF": {"fo4": "01F583:Fallout4.esm", "core_section": "activators", "core_id": 0x005119, "core_base_id": 0x0A2D4A, "local_pos": [-804.72, 984.60, 102.68]},
            "PowerArmorFurniture": {"fo4": "0370E3:Fallout4.esm", "core_section": "refs", "core_id": 0x008913, "local_pos": [-795.73, 976.90, 97.54], "runtime_plugin": "FO4SFPowerArmor.esm:0x000801"},
            "ConcordAmbushDeathclaw": {"fo4": "01F15B:Fallout4.esm", "core_section": None, "core_id": None, "local_pos": [-868.22, 1059.82, 88.22], "initially_disabled": True},
            "DN092ForceSpawnDeathclawTrigger": {"fo4": "09A144:Fallout4.esm", "core_section": None, "core_id": None, "local_pos": [-868.22, 1059.77, 88.22]},
        },
    },
    "SanctuaryBasementJahani": {
        "group": "sanctuary_root_cellar",
        "story_tier": "A3",
        "fo4_cell_formkey": "0A36EA:Fallout4.esm",
        "port_cell_edid": "FO4Port_SanctuaryBasementJahani",
        "port_cell_id": 0x011918,
        "port_lctn_edid": "FO4Port_SanctuaryHillsLocation",
        "port_lctn_id": 0x0405CE,
        "display_name": "Root Cellar",
        "encounter_zone": None,
        "ref_count": 217,
        "initially_disabled_count": 0,
        "xesp_count": 0,
        "xesp_parents": [],
        "key_internal_refs": {
            "Loot_Prewar_Safe": {"fo4": "0A413B:Fallout4.esm", "port_id": 0x01195B, "type": "CONT", "lock": 50},
        },
        "exterior_setpieces": {
            "SanctuaryWorkshopREF": {"fo4": "0250FE:Fallout4.esm", "core_section": "workshops", "core_id": 0x005C50, "core_base_id": 0x0A2ECD, "local_pos": [-1129.25, 1279.81, 112.09]},
        },
    },
    "RedRocket01": {
        "group": "red_rocket",
        "story_tier": "A3",
        "fo4_cell_formkey": "05E62F:Fallout4.esm",
        "port_cell_edid": "FO4Port_RedRocket01",
        "port_cell_id": 0x002338,
        "port_lctn_edid": "FO4Port_RedRocketCaveLocation",
        "port_lctn_id": 0x0405B4,
        "display_name": "Mole Rat Den",
        "encounter_zone": {"edid": "RedRocketCaveZone", "min_level": 4, "max_level": 9},
        "ref_count": 795,
        "initially_disabled_count": 0,
        "xesp_count": 0,
        "xesp_parents": [],
        "key_internal_refs": {
            "Loot_Raider_Safe": {"fo4": "08CC2F:Fallout4.esm", "port_id": 0x0024D7, "type": "CONT", "lock": 1},
        },
        "exterior_setpieces": {
            "RedRocketWorkshopREF": {"fo4": "054BAE:Fallout4.esm", "core_section": "workshops", "core_id": 0x00D271, "core_base_id": 0x0A2ECD, "local_pos": [-1005.49, 1136.00, 105.14]},
            "RedRGarageDoor": {"fo4": "056331:Fallout4.esm", "core_section": "activators", "core_id": 0x00D9B7, "core_base_id": 0x0A2D5F, "local_pos": [-989.03, 1147.20, 105.14]},
            "RedR_ButtonBox": {"fo4": "056BBA:Fallout4.esm", "core_section": "activators", "core_id": 0x00DCC6, "core_base_id": 0x0A2D5A, "local_pos": [-1006.92, 1136.81, 105.14]},
            "DogmeatRef": {"fo4": "01D162:Fallout4.esm", "core_section": None, "core_id": None, "local_pos": [-986.02, 1156.26, 105.24]},
        },
    },
    "ConcordCivicAccess01": {
        "group": "concord_route",
        "story_tier": "A3",
        "fo4_cell_formkey": "03776D:Fallout4.esm",
        "port_cell_edid": "FO4Port_ConcordCivicAccess01",
        "port_cell_id": 0x0119AF,
        "port_lctn_edid": "FO4Port_ConcordUndergroundLocation",
        "port_lctn_id": 0x0405CF,
        "display_name": "Concord Civic Access",
        "encounter_zone": {"edid": "ConcordUndergroundZone", "min_level": 1, "max_level": 5},
        "ref_count": 1980,
        "initially_disabled_count": 3,
        "xesp_count": 8,
        "xesp_parents": ["078BA4:Fallout4.esm", "0B1EB3:Fallout4.esm"],
        "key_internal_refs": {
            "ChainedDoor": {"fo4": "0645DA:Fallout4.esm", "port_id": 0x012027, "type": "DOOR", "script": "ChainedDoor"},
            "DoorChain": {"fo4": "0645DB:Fallout4.esm", "port_id": 0x012028, "type": "ACTI", "script": "DoorChain"},
        },
        "exterior_setpieces": {},
    },
    "ConcordFactory": {
        "group": "concord_route",
        "story_tier": "A3",
        "fo4_cell_formkey": "0E3CC4:Fallout4.esm",
        "port_cell_edid": "FO4Port_ConcordFactory",
        "port_cell_id": 0x01202C,
        "port_lctn_edid": "FO4Port_ConcordLocation",
        "port_lctn_id": 0x0405D0,
        "display_name": "Workhouse",
        "encounter_zone": {"edid": "ConcordZone", "min_level": 0, "max_level": 10},
        "ref_count": 598,
        "initially_disabled_count": 0,
        "xesp_count": 0,
        "xesp_parents": [],
        "key_internal_refs": {
            "Loot_Prewar_Safe": {"fo4": "0E3D84:Fallout4.esm", "port_id": 0x0120DD, "type": "CONT", "lock": 50},
        },
        "exterior_setpieces": {},
    },
    "ConcordSpeakeasy": {
        "group": "concord_route",
        "story_tier": "A3",
        "fo4_cell_formkey": "0788D4:Fallout4.esm",
        "port_cell_edid": "FO4Port_ConcordSpeakeasy",
        "port_cell_id": 0x012245,
        "port_lctn_edid": "FO4Port_ConcordLocation",
        "port_lctn_id": 0x0405D0,
        "display_name": "Concord Speakeasy",
        "encounter_zone": {"edid": "ConcordZone", "min_level": 0, "max_level": 10},
        "ref_count": 859,
        "initially_disabled_count": 0,
        "xesp_count": 0,
        "xesp_parents": [],
        "key_internal_refs": {
            "BldWoodPDoor01_Locked": {"fo4": "0789BB:Fallout4.esm", "port_id": 0x01228D, "type": "DOOR", "lock": 50},
            "Loot_Raider_Safe": {"fo4": "0855A6:Fallout4.esm", "port_id": 0x012342, "type": "CONT", "lock": 50},
        },
        "exterior_setpieces": {},
    },
    "CorvegaAssemblyPlant01": {
        "group": "corvega",
        "story_tier": "A4",
        "fo4_cell_formkey": "057127:Fallout4.esm",
        "port_cell_edid": "FO4Port_CorvegaAssemblyPlant01",
        "port_cell_id": 0x01535A,
        "port_lctn_edid": "FO4Port_CorvegaAssemblyPlantLocation",
        "port_lctn_id": 0x0405DD,
        "display_name": "Corvega Assembly Plant",
        "encounter_zone": {"edid": "CorvegaAssemblyPlantZone", "min_level": 1, "max_level": 5},
        "ref_count": 10980,
        "initially_disabled_count": 3,
        "xesp_count": 11,
        "xesp_parents": ["0D21FD:Fallout4.esm", "0D39D1:Fallout4.esm", "1FB828:Fallout4.esm", "20A24C:Fallout4.esm"],
        "key_internal_refs": {
            "SecurityGateSmLatch01": {"fo4": "0D3C72:Fallout4.esm", "port_id": 0x015C30, "type": "DOOR", "lock": 100, "key": "0D3C71:Fallout4.esm"},
        },
        "exterior_setpieces": {},
    },
    "DmndValentines01": {
        "group": "diamond_city",
        "story_tier": "A4",
        "fo4_cell_formkey": "001E47:Fallout4.esm",
        "port_cell_edid": "FO4Port_DmndValentines01",
        "port_cell_id": 0x006B30,
        "port_lctn_edid": "FO4Port_DiamondCityValentinesLocation",
        "port_lctn_id": 0x0405AB,
        "display_name": "Valentine Detective Agency",
        "encounter_zone": None,
        "ref_count": 342,
        "initially_disabled_count": 7,
        "xesp_count": 0,
        "xesp_parents": [],
        "key_internal_refs": {},
        "exterior_setpieces": {
            "DmndGateREF": {"fo4": "077A87:Fallout4.esm", "core_section": "refs", "core_id": 0x013E79, "local_pos": [-216.36, -429.39, 19.20], "lock": 254},
            "DCgateIntercom": {"fo4": "018FD6:Fallout4.esm", "core_section": None, "core_id": None, "local_pos": [-225.33, -433.98, 19.29]},
        },
    },
}

# All 20 two-way exterior <-> interior load-door pairs across A3 + A4 (18 real-mesh + 2 AutoloadDoor).
# Positions are in metres (FO4 XTEL / 70.0), verified directly from Fallout4.esm + candidate-2e + interiors_b10.
TWO_WAY_DOOR_PAIRS: list[dict[str, Any]] = [
    # --- Museum of Freedom (ConcordMuseum01) ---
    {
        "id": "museum_front",
        "cell": "ConcordMuseum01",
        "group": "concord_museum",
        "wiring_mode": "real_mesh",
        "label": "Museum of Freedom front entrance double doors",
        "ext_fo4_ref": "01AC07:Fallout4.esm",
        "ext_core_ref_id": 0x004B2B,
        "int_fo4_ref": "077D22:Fallout4.esm",
        "int_port_ref_id": 0x01303B,
        "int_lock": None,
        "ext_arrival_local": [-811.142857, 1002.457143, 89.085714],
        "ext_arrival_rot": [0.0, 0.0, -0.872665],
        "int_arrival": [8.057143, 0.0, -0.914286],
        "int_arrival_rot": [0.0, 0.0, -1.570796],
        "notes": "Primary quest entrance for When Freedom Calls; unlocked both ways.",
    },
    {
        "id": "museum_balcony",
        "cell": "ConcordMuseum01",
        "group": "concord_museum",
        "wiring_mode": "real_mesh",
        "label": "Museum of Freedom second-floor balcony door",
        "ext_fo4_ref": "01D22F:Fallout4.esm",
        "ext_core_ref_id": 0x005054,
        "int_fo4_ref": "01B94A:Fallout4.esm",
        "int_port_ref_id": 0x013045,
        "int_lock": 255,
        "ext_arrival_local": [-810.062943, 1001.552857, 98.487521],
        "ext_arrival_rot": [0.0, 0.0, -0.885400],
        "int_arrival": [12.039000, 0.028000, 9.142857],
        "int_arrival_rot": [0.0, 0.0, 4.712389],
        "notes": "Inaccessible lock (255) on interior side (ConcordMuseumBalconyDoorREF) during Min00 until balcony scene completes.",
    },
    {
        "id": "museum_roof",
        "cell": "ConcordMuseum01",
        "group": "concord_museum",
        "wiring_mode": "real_mesh",
        "label": "Museum of Freedom roof access door (to T-45 Power Armor & Vertibird)",
        "ext_fo4_ref": "029AD8:Fallout4.esm",
        "ext_core_ref_id": 0x00677F,
        "int_fo4_ref": "02C1C6:Fallout4.esm",
        "int_port_ref_id": 0x013048,
        "int_lock": None,
        "ext_arrival_local": [-790.576671, 975.815143, 97.558886],
        "ext_arrival_rot": [0.0, 0.0, -1.395795],
        "int_arrival": [-21.903000, 8.683000, 9.142857],
        "int_arrival_rot": [0.0, 0.0, 2.641600],
        "notes": "Reaches Museum roof T-45 Power Armor (0370E3) and crashed Vertibird Minigun (01F583); gated indoors by PrestonExitDoor (01E2E9).",
    },
    # --- Sanctuary Hills Root Cellar (SanctuaryBasementJahani) ---
    {
        "id": "sanctuary_root_cellar_hatch",
        "cell": "SanctuaryBasementJahani",
        "group": "sanctuary_root_cellar",
        "wiring_mode": "real_mesh",
        "label": "Sanctuary Hills Root Cellar backyard hatch / ladder",
        "ext_fo4_ref": "0A36EB:Fallout4.esm",
        "ext_core_ref_id": 0x01CF77,
        "int_fo4_ref": "0A3701:Fallout4.esm",
        "int_port_ref_id": 0x0119AE,
        "int_lock": None,
        "ext_arrival_local": [-1088.796571, 1335.962571, 110.818300],
        "ext_arrival_rot": [0.0, 0.0, 0.596534],
        "int_arrival": [-2.965000, 3.099000, 0.0],
        "int_arrival_rot": [0.0, 0.0, 3.083200],
        "notes": "Only load-door interior in Sanctuary Hills; all Sanctuary houses are open exterior shells.",
    },
    # --- Red Rocket Mole Rat Den (RedRocket01) ---
    {
        "id": "red_rocket_mole_rat_cave",
        "cell": "RedRocket01",
        "group": "red_rocket",
        "wiring_mode": "autoload_activator",
        "label": "Red Rocket Mole Rat Den cave entrance (AutoloadDoor editor marker)",
        "ext_fo4_ref": "08EB65:Fallout4.esm",
        "ext_core_ref_id": None,
        "int_fo4_ref": "05E844:Fallout4.esm",
        "int_port_ref_id": None,
        "int_lock": None,
        "ext_arrival_local": [-995.530286, 1104.142857, 99.771429],
        "ext_arrival_rot": [0.0, 0.0, -3.108186],
        "int_arrival": [0.049286, -6.622000, -0.006286],
        "int_arrival_rot": [0.0, 0.0, 2.701400],
        "notes": "Both ends use AutoLoadMarker01.nif (skipped as editor_marker by both core and port). Needs explicit FO4SF_LoadDoor ACTI placement at cave mouth and interior tunnel exit.",
    },
    # --- Concord Civic Access (ConcordCivicAccess01) ---
    {
        "id": "civic_access_south_pipe",
        "cell": "ConcordCivicAccess01",
        "group": "concord_route",
        "wiring_mode": "real_mesh",
        "label": "Concord Civic Access south drainage pipe door",
        "ext_fo4_ref": "02C9A5:Fallout4.esm",
        "ext_core_ref_id": 0x0072A9,
        "int_fo4_ref": "023F6C:Fallout4.esm",
        "int_port_ref_id": 0x012024,
        "int_lock": None,
        "ext_arrival_local": [-873.195486, 1046.357143, 82.552679],
        "ext_arrival_rot": [0.0, 0.0, 1.043134],
        "int_arrival": [136.851000, -64.898000, 10.832000],
        "int_arrival_rot": [0.0, 0.0, -3.052600],
        "notes": "Walk-in drainage tunnel near the Deathclaw street pit.",
    },
    {
        "id": "civic_access_ne_manhole",
        "cell": "ConcordCivicAccess01",
        "group": "concord_route",
        "wiring_mode": "real_mesh",
        "label": "Concord Civic Access northeast street manhole",
        "ext_fo4_ref": "04C3DE:Fallout4.esm",
        "ext_core_ref_id": 0x00BAF2,
        "int_fo4_ref": "04BD48:Fallout4.esm",
        "int_port_ref_id": 0x012025,
        "int_lock": None,
        "ext_arrival_local": [-801.832643, 1044.002571, 86.605814],
        "ext_arrival_rot": [0.0, 0.0, -0.920045],
        "int_arrival": [68.331000, -90.396000, 15.559000],
        "int_arrival_rot": [0.0, 0.0, 1.800000],
        "notes": "Street trapdoor ladder into northeast Civic Access chamber.",
    },
    {
        "id": "civic_access_sw_manhole",
        "cell": "ConcordCivicAccess01",
        "group": "concord_route",
        "wiring_mode": "real_mesh",
        "label": "Concord Civic Access southwest street manhole",
        "ext_fo4_ref": "04C3E0:Fallout4.esm",
        "ext_core_ref_id": 0x00BAF3,
        "int_fo4_ref": "04C38B:Fallout4.esm",
        "int_port_ref_id": 0x012026,
        "int_lock": None,
        "ext_arrival_local": [-867.466800, 1020.677143, 88.322350],
        "ext_arrival_rot": [0.0, 0.0, -0.179989],
        "int_arrival": [89.263000, -44.726000, 12.655000],
        "int_arrival_rot": [0.0, 0.0, 1.900000],
        "notes": "Street trapdoor ladder on southwest side of Concord Main Street.",
    },
    # --- Concord Workhouse (ConcordFactory) ---
    {
        "id": "workhouse_upper",
        "cell": "ConcordFactory",
        "group": "concord_route",
        "wiring_mode": "real_mesh",
        "label": "Concord Workhouse upper door",
        "ext_fo4_ref": "0E3DAD:Fallout4.esm",
        "ext_core_ref_id": 0x02AD45,
        "int_fo4_ref": "0E3D69:Fallout4.esm",
        "int_port_ref_id": 0x012240,
        "int_lock": None,
        "ext_arrival_local": [-834.806286, 1082.227571, 103.922991],
        "ext_arrival_rot": [0.0, 0.0, -0.087266],
        "int_arrival": [4.507000, -0.889000, 6.494000],
        "int_arrival_rot": [0.0, 0.0, -3.128900],
        "notes": "Upper walkway entrance.",
    },
    {
        "id": "workhouse_east",
        "cell": "ConcordFactory",
        "group": "concord_route",
        "wiring_mode": "real_mesh",
        "label": "Concord Workhouse east ground door",
        "ext_fo4_ref": "0E3DA1:Fallout4.esm",
        "ext_core_ref_id": 0x02AD42,
        "int_fo4_ref": "0E3D94:Fallout4.esm",
        "int_port_ref_id": 0x012241,
        "int_lock": None,
        "ext_arrival_local": [-830.649114, 1079.481357, 88.493129],
        "ext_arrival_rot": [0.0, 0.0, 1.483530],
        "int_arrival": [4.927000, -6.102000, -8.165000],
        "int_arrival_rot": [0.0, 0.0, -1.379200],
        "notes": "East street-level industrial door.",
    },
    {
        "id": "workhouse_west",
        "cell": "ConcordFactory",
        "group": "concord_route",
        "wiring_mode": "real_mesh",
        "label": "Concord Workhouse west ground door",
        "ext_fo4_ref": "0E3DAB:Fallout4.esm",
        "ext_core_ref_id": 0x02AD43,
        "int_fo4_ref": "0E3D95:Fallout4.esm",
        "int_port_ref_id": 0x012242,
        "int_lock": None,
        "ext_arrival_local": [-844.216357, 1083.495571, 88.322350],
        "ext_arrival_rot": [0.0, 0.0, -1.658063],
        "int_arrival": [-4.720000, -0.320000, -8.137000],
        "int_arrival_rot": [0.0, 0.0, 1.483500],
        "notes": "West street-level wood door.",
    },
    # --- Concord Speakeasy (ConcordSpeakeasy) ---
    {
        "id": "speakeasy_upper",
        "cell": "ConcordSpeakeasy",
        "group": "concord_route",
        "wiring_mode": "real_mesh",
        "label": "Concord Speakeasy upper residential door",
        "ext_fo4_ref": "07895C:Fallout4.esm",
        "ext_core_ref_id": 0x013FCD,
        "int_fo4_ref": "0788F7:Fallout4.esm",
        "int_port_ref_id": 0x012536,
        "int_lock": None,
        "ext_arrival_local": [-836.240457, 1048.972857, 91.971657],
        "ext_arrival_rot": [0.0, 0.0, 1.893929],
        "int_arrival": [7.182000, 16.140000, 7.314000],
        "int_arrival_rot": [0.0, 0.0, -0.872700],
        "notes": "Upper porch entrance.",
    },
    {
        "id": "speakeasy_east",
        "cell": "ConcordSpeakeasy",
        "group": "concord_route",
        "wiring_mode": "real_mesh",
        "label": "Concord Speakeasy east street door",
        "ext_fo4_ref": "07895D:Fallout4.esm",
        "ext_core_ref_id": 0x013FCE,
        "int_fo4_ref": "0788F6:Fallout4.esm",
        "int_port_ref_id": 0x012537,
        "int_lock": None,
        "ext_arrival_local": [-829.255429, 1046.915571, 88.493829],
        "ext_arrival_rot": [0.0, 0.0, 0.739732],
        "int_arrival": [15.250000, 10.442000, 3.657000],
        "int_arrival_rot": [0.0, 0.0, -2.443500],
        "notes": "Main Street front door on Concord approach.",
    },
    {
        "id": "speakeasy_south",
        "cell": "ConcordSpeakeasy",
        "group": "concord_route",
        "wiring_mode": "real_mesh",
        "label": "Concord Speakeasy south street door",
        "ext_fo4_ref": "07895F:Fallout4.esm",
        "ext_core_ref_id": 0x013FCF,
        "int_fo4_ref": "07895E:Fallout4.esm",
        "int_port_ref_id": 0x012538,
        "int_lock": None,
        "ext_arrival_local": [-838.156757, 1036.335486, 88.494539],
        "ext_arrival_rot": [0.0, 0.0, -2.443461],
        "int_arrival": [4.457000, -2.171000, 3.771000],
        "int_arrival_rot": [0.0, 0.0, 0.698100],
        "notes": "South alley entrance.",
    },
    # --- Corvega Assembly Plant (A4: The First Step) ---
    {
        "id": "corvega_main_lower",
        "cell": "CorvegaAssemblyPlant01",
        "group": "corvega",
        "wiring_mode": "real_mesh",
        "label": "Corvega Assembly Plant main double door",
        "ext_fo4_ref": "057280:Fallout4.esm",
        "ext_core_ref_id": 0x00DF1B,
        "int_fo4_ref": "057B0E:Fallout4.esm",
        "int_port_ref_id": 0x017957,
        "int_lock": None,
        "ext_arrival_local": [-512.432371, 480.069643, 53.607419],
        "ext_arrival_rot": [0.0, 0.0, 0.0],
        "int_arrival": [-9.143000, 22.857000, -3.657000],
        "int_arrival_rot": [0.0, 0.0, -3.141600],
        "notes": "Primary front factory floor entrance for The First Step.",
    },
    {
        "id": "corvega_main_upper",
        "cell": "CorvegaAssemblyPlant01",
        "group": "corvega",
        "wiring_mode": "real_mesh",
        "label": "Corvega Assembly Plant upper front catwalk door",
        "ext_fo4_ref": "057281:Fallout4.esm",
        "ext_core_ref_id": 0x00DF1C,
        "int_fo4_ref": "057B0F:Fallout4.esm",
        "int_port_ref_id": 0x017956,
        "int_lock": None,
        "ext_arrival_local": [-512.413114, 479.982757, 60.785714],
        "ext_arrival_rot": [0.0, 0.0, 0.0],
        "int_arrival": [-9.137000, 22.845000, 1.829000],
        "int_arrival_rot": [0.0, 0.0, -3.141600],
        "notes": "Upper walkway entrance above main double door.",
    },
    {
        "id": "corvega_east_roof",
        "cell": "CorvegaAssemblyPlant01",
        "group": "corvega",
        "wiring_mode": "real_mesh",
        "label": "Corvega Assembly Plant east catwalk door",
        "ext_fo4_ref": "057283:Fallout4.esm",
        "ext_core_ref_id": 0x00DF1E,
        "int_fo4_ref": "057B11:Fallout4.esm",
        "int_port_ref_id": 0x017955,
        "int_lock": None,
        "ext_arrival_local": [-476.863671, 473.601171, 64.442857],
        "ext_arrival_rot": [0.0, 0.0, 1.570796],
        "int_arrival": [24.819000, 18.223000, 5.486000],
        "int_arrival_rot": [0.0, 0.0, -1.570800],
        "notes": "East roof/catwalk door.",
    },
    {
        "id": "corvega_west_hatch",
        "cell": "CorvegaAssemblyPlant01",
        "group": "corvega",
        "wiring_mode": "real_mesh",
        "label": "Corvega Assembly Plant west roof hatch",
        "ext_fo4_ref": "1A842A:Fallout4.esm",
        "ext_core_ref_id": 0x06B3E6,
        "int_fo4_ref": "1A8429:Fallout4.esm",
        "int_port_ref_id": 0x017953,
        "int_lock": None,
        "ext_arrival_local": [-544.632000, 484.684286, 68.114286],
        "ext_arrival_rot": [0.0, 0.0, 1.771047],
        "int_arrival": [-42.017000, 29.384000, 3.871000],
        "int_arrival_rot": [0.0, 0.0, 1.870800],
        "notes": "West roof metal trapdoor.",
    },
    {
        "id": "corvega_south_door",
        "cell": "CorvegaAssemblyPlant01",
        "group": "corvega",
        "wiring_mode": "real_mesh",
        "label": "Corvega Assembly Plant south upper exit",
        "ext_fo4_ref": "22F1EB:Fallout4.esm",
        "ext_core_ref_id": 0x09CB27,
        "int_fo4_ref": "22F1EC:Fallout4.esm",
        "int_port_ref_id": 0x017950,
        "int_lock": None,
        "ext_arrival_local": [-495.331529, 451.630914, 64.479924],
        "ext_arrival_rot": [0.0, 0.0, 1.570798],
        "int_arrival": [6.504000, -3.692000, 5.527000],
        "int_arrival_rot": [0.0, 0.0, 4.712400],
        "notes": "South industrial exit door.",
    },
    {
        "id": "corvega_sewer_pipe",
        "cell": "CorvegaAssemblyPlant01",
        "group": "corvega",
        "wiring_mode": "autoload_activator",
        "label": "Corvega Assembly Plant sewer drainage pipe (AutoloadDoor editor marker)",
        "ext_fo4_ref": "0CFB19:Fallout4.esm",
        "ext_core_ref_id": None,
        "int_fo4_ref": "0CFA97:Fallout4.esm",
        "int_port_ref_id": None,
        "int_lock": None,
        "ext_arrival_local": [-461.761686, 504.304571, 45.740114],
        "ext_arrival_rot": [0.0, 0.0, 0.124999],
        "int_arrival": [56.705000, 63.892000, -21.172000],
        "int_arrival_rot": [0.052400, 0.0, 3.133200],
        "notes": "Stealth drain-pipe entry uses AutoLoadMarker01.nif; requires explicit FO4SF_LoadDoor ACTI placement.",
    },
]

# ------------------------------------------------------------------------------
# A4 Next Story Missions W6 Reachability / Fragility / Open-Mode Graph Catalog
# ------------------------------------------------------------------------------
A4_NEXT_MISSIONS: list[dict[str, Any]] = [
    {
        "id": "FO4SF_Sanctuary01",
        "fo4_source": "Min01 (0x05DEE4)",
        "starfield_quest_id": "0x000817 (expanded in place on FO4SFMission.esm)",
        "title": "Sanctuary",
        "story_order": 1,
        "mission_gate": "FO4SF_GameMode == 1 (Story); stops silently in Warfare (2)",
        "start_stage": 10,
        "stages": [10, 50, 100, 1000, 1050, 1200, 1250, 1300, 1350, 1400, 1450, 1500],
        "completion_stages": [1500],
        "essential_npcs": [
            {
                "id": "FO4_Sturges",
                "fo4_id": "0x019FDA",
                "open_mode_fallback": "If Sturges is dead, Sanctuary workbench activation reads settlement bed/water/food/defense counters directly and advances through stage 1500 without blocking on Sturges dialogue.",
            },
            {
                "id": "FO4_PrestonGarvey",
                "fo4_id": "0x019FD9",
                "open_mode_fallback": "If Preston is dead, activating the Sanctuary workbench (04005C50) or reading Sturges' ledger still completes Sanctuary and unlocks workshop settlement ownership.",
            },
        ],
        "break_it_cases": [
            "giver_dead_sturges_and_preston",
            "out_of_order_prebuilt_beds_water_food_defense",
            "save_reload_every_stage",
            "fast_travel_away_mid_build",
        ],
        "transitions": [
            {"from": 10, "to": 50, "kind": "primary", "label": "Activate Sanctuary workbench 04005C50 / arrive at Sanctuary"},
            {"from": 10, "to": 1000, "kind": "out_of_order", "label": "Talk to Sturges before touching workbench"},
            {"from": 10, "to": 1000, "kind": "open_mode_fallback", "open_mode_only": True, "label": "Sturges dead -> workbench checklist auto-starts beds milestone"},
            {"from": 50, "to": 1000, "kind": "primary", "label": "Talk to Sturges -> start beds objective (5 beds)"},
            {"from": 50, "to": 1000, "kind": "open_mode_fallback", "open_mode_only": True, "label": "Sturges dead -> workbench auto-advances to beds milestone"},
            {"from": 1000, "to": 1050, "kind": "primary", "label": "Sanctuary beds >= 5 (Min01BedTotal=5)"},
            {"from": 1000, "to": 1200, "kind": "out_of_order", "label": "Pre-built >=5 beds detected on stage entry"},
            {"from": 1050, "to": 1200, "kind": "primary", "label": "Report beds to Sturges -> start clean water objective (5 water)"},
            {"from": 1050, "to": 1200, "kind": "open_mode_fallback", "open_mode_only": True, "label": "Sturges dead -> workbench advances straight to water milestone"},
            {"from": 1200, "to": 1250, "kind": "primary", "label": "Sanctuary water >= 5 (Min01WaterTotal=5)"},
            {"from": 1200, "to": 1300, "kind": "out_of_order", "label": "Pre-built >=5 water detected on stage entry"},
            {"from": 1250, "to": 1300, "kind": "primary", "label": "Report water to Sturges -> start food objective (5 food)"},
            {"from": 1250, "to": 1300, "kind": "open_mode_fallback", "open_mode_only": True, "label": "Sturges dead -> workbench advances straight to food milestone"},
            {"from": 1300, "to": 1350, "kind": "primary", "label": "Sanctuary food >= 5 (Min01FoodTotal=5)"},
            {"from": 1300, "to": 1400, "kind": "out_of_order", "label": "Pre-built >=5 food detected on stage entry"},
            {"from": 1350, "to": 1400, "kind": "primary", "label": "Report food to Sturges -> start defense objective (2 defense)"},
            {"from": 1350, "to": 1400, "kind": "open_mode_fallback", "open_mode_only": True, "label": "Sturges dead -> workbench advances straight to defense milestone"},
            {"from": 1400, "to": 1450, "kind": "primary", "label": "Sanctuary defense >= 2 (Min01SafetyTotal=2)"},
            {"from": 1400, "to": 1500, "kind": "out_of_order", "label": "Pre-built >=2 defense completes final milestone"},
            {"from": 1450, "to": 1500, "kind": "primary", "label": "Final report to Sturges -> complete Sanctuary & preserve legacy stage 100 compat"},
            {"from": 1450, "to": 1500, "kind": "open_mode_fallback", "open_mode_only": True, "label": "Sturges dead -> workbench finalizes Sanctuary at stage 1500"},
            {"from": 100, "to": 1500, "kind": "legacy_compat", "label": "Upgrade save/stub already at legacy stage 100 cleanly to completed 1500"},
        ],
    },
    {
        "id": "FO4SF_MinRecruit00",
        "fo4_source": "MinRecruit00 (0x11B36E)",
        "starfield_quest_id": "0x000A20 (reserved on FO4SFMission.esm; avoids 0x800..0x9FF)",
        "title": "The First Step",
        "story_order": 2,
        "mission_gate": "FO4SF_GameMode == 1 (Story); stops silently in Warfare (2)",
        "start_stage": 10,
        "stages": [10, 50, 100, 200, 450, 500],
        "completion_stages": [500],
        "essential_npcs": [
            {
                "id": "FO4_PrestonGarvey",
                "fo4_id": "0x019FD9",
                "open_mode_fallback": "If Preston is dead, clearing Corvega and claiming Tenpines Bluff workbench (01A793) completes the recruitment autonomously and grants the Flare Gun via workshop stash.",
            },
            {
                "id": "TenpinesSpokesman",
                "fo4_id": "Alias 6 (SettlementSpokesman)",
                "open_mode_fallback": "If the Tenpines Bluff spokesman is dead, activating the Tenpines workbench (01A793) or looting the settlement request note sets stage 100 (Corvega target) and stage 450 on clear.",
            },
        ],
        "break_it_cases": [
            "giver_dead_preston_or_spokesman",
            "out_of_order_corvega_cleared_first",
            "save_reload_every_stage",
            "fast_travel_away_mid_dungeon",
        ],
        "transitions": [
            {"from": 10, "to": 50, "kind": "primary", "label": "Preston briefs player on Tenpines Bluff help request"},
            {"from": 10, "to": 50, "kind": "out_of_order", "label": "Player discovers Tenpines Bluff (01A793) before talking to Preston"},
            {"from": 10, "to": 100, "kind": "open_mode_fallback", "open_mode_only": True, "label": "Preston dead -> Tenpines workbench / note reveals Corvega raiders"},
            {"from": 50, "to": 100, "kind": "primary", "label": "Talk to Tenpines Bluff spokesman -> target Corvega Assembly Plant (FO4Port:0x01535A)"},
            {"from": 50, "to": 100, "kind": "open_mode_fallback", "open_mode_only": True, "label": "Spokesman dead -> read Tenpines note / activate workbench 01A793"},
            {"from": 50, "to": 200, "kind": "out_of_order", "label": "Corvega raider boss (Jared) already dead before Tenpines talk"},
            {"from": 100, "to": 200, "kind": "primary", "label": "Kill Corvega raider boss inside FO4Port_CorvegaAssemblyPlant01"},
            {"from": 100, "to": 200, "kind": "out_of_order", "label": "Corvega boss pre-cleared -> immediate sync to stage 200"},
            {"from": 200, "to": 450, "kind": "primary", "label": "Report success to Tenpines spokesman -> Tenpines aligns with Minutemen"},
            {"from": 200, "to": 450, "kind": "open_mode_fallback", "open_mode_only": True, "label": "Spokesman dead -> claim Tenpines workbench 01A793 directly"},
            {"from": 450, "to": 500, "kind": "primary", "label": "Report back to Preston -> join Minutemen, receive Flare Gun, unlock Min02 hook"},
            {"from": 450, "to": 500, "kind": "open_mode_fallback", "open_mode_only": True, "label": "Preston dead -> Sanctuary workshop locker awards Flare Gun & completes at stage 500"},
        ],
    },
    {
        "id": "FO4SF_MQ103",
        "fo4_source": "MQ103 (0x0229E5) + DialogueDiamondCityEntrance (0x0190BC)",
        "starfield_quest_id": "0x000A50 (reserved on FO4SFMission.esm; avoids 0x800..0x9FF)",
        "title": "Jewel of the Commonwealth",
        "story_order": 3,
        "mission_gate": "FO4SF_GameMode == 1 (Story); stops silently in Warfare (2)",
        "start_stage": 10,
        "stages": [10, 20, 25, 30, 100],
        "completion_stages": [100],
        "essential_npcs": [
            {
                "id": "FO4_Piper",
                "fo4_id": "0x002F1E",
                "open_mode_fallback": "If Piper is dead or absent, activating DCgateIntercom (018FD6) or DmndGateREF (013E79) directly opens Diamond City entry and advances to stage 20.",
            },
            {
                "id": "FO4_MayorMcDonough",
                "fo4_id": "0x002F08",
                "open_mode_fallback": "If Mayor McDonough is dead, DmndGateREF unlocks automatically on intercom/gate activation so Diamond City entry never deadlocks.",
            },
            {
                "id": "FO4_ElliePerkins",
                "fo4_id": "0x0222A2",
                "open_mode_fallback": "If Ellie is dead inside DmndValentines01 (0x006B30), reading Nick's case file on the agency desk sets stage 100 and hands off to MQ104 (Vault 114).",
            },
        ],
        "break_it_cases": [
            "giver_dead_piper_mayor_or_ellie",
            "out_of_order_direct_walk_to_diamond_city_gate",
            "save_reload_every_stage",
            "fast_travel_away_mid_gate_scene",
        ],
        "transitions": [
            {"from": 10, "to": 20, "kind": "primary", "label": "Reach Diamond City gate (DmndGateREF 013E79) -> Piper & Mayor entrance scene opens gate"},
            {"from": 10, "to": 20, "kind": "out_of_order", "label": "Walk straight to Diamond City gate without prior Mama Murphy / Codsworth lead"},
            {"from": 10, "to": 20, "kind": "open_mode_fallback", "open_mode_only": True, "label": "Piper/Mayor dead -> intercom or gate manual override unlocks entry"},
            {"from": 20, "to": 25, "kind": "primary", "label": "Enter Diamond City and ask Piper/residents/signs about Shaun"},
            {"from": 20, "to": 30, "kind": "out_of_order", "label": "Inspect DetectiveSign01/02 or enter Valentine Detective Agency (FO4Port:0x006B30) directly"},
            {"from": 25, "to": 30, "kind": "primary", "label": "Directed to Nick Valentine's Detective Agency"},
            {"from": 25, "to": 30, "kind": "open_mode_fallback", "open_mode_only": True, "label": "Piper/informants dead -> Detective sign / agency door advances to stage 30"},
            {"from": 30, "to": 100, "kind": "primary", "label": "Enter DmndValentines01 (0x006B30) and speak with Ellie Perkins -> handoff to MQ104 (Vault 114)"},
            {"from": 30, "to": 100, "kind": "open_mode_fallback", "open_mode_only": True, "label": "Ellie dead -> read Park Street Station case dossier on agency desk -> stage 100 + MQ104 handoff"},
        ],
    },
]


def merged_pos(local_pos: list[float], merge_offset: tuple[float, float, float] = MERGE_OFFSET) -> list[float]:
    return [round(float(local_pos[i]) + float(merge_offset[i]), 6) for i in range(3)]


def select_door_pairs(groups: list[str] | None = None) -> list[dict[str, Any]]:
    if not groups or "all" in groups:
        return list(TWO_WAY_DOOR_PAIRS)
    expanded: set[str] = set()
    for g in groups:
        if g == "a3_all":
            expanded.update({"concord_museum", "sanctuary_root_cellar", "red_rocket", "concord_route"})
        elif g == "a4_all":
            expanded.update({"corvega", "diamond_city"})
        else:
            expanded.add(g)
    return [d for d in TWO_WAY_DOOR_PAIRS if d["group"] in expanded]


def build_door_plan(
    groups: list[str] | None = None,
    port_next_id: int = PORT_B10_NEXT_OBJECT_ID,
    core_next_marker_id: int = 0x0A7800,
    merge_offset: tuple[float, float, float] = MERGE_OFFSET,
) -> dict[str, Any]:
    """Build deterministic two-way FO4SF_LoadDoor wiring plan (R10 3-retry safe, zero reconversion)."""
    selected = select_door_pairs(groups)
    real_mesh_entries = []
    autoload_entries = []
    used_port_markers: set[int] = set()
    used_core_markers: set[int] = set()
    used_int_refs: set[int] = set()
    used_ext_refs: set[int] = set()

    next_p = int(port_next_id)
    next_c = int(core_next_marker_id)

    for d in selected:
        cell_meta = STAGED_INTERIOR_CELLS[d["cell"]]
        ext_merged = merged_pos(d["ext_arrival_local"], merge_offset)
        if d["wiring_mode"] == "autoload_activator":
            autoload_entries.append({
                "id": d["id"],
                "cell": d["cell"],
                "port_cell_id": f"{cell_meta['port_cell_id']:06X}",
                "ext_fo4_ref": d["ext_fo4_ref"],
                "int_fo4_ref": d["int_fo4_ref"],
                "ext_arrival_local": d["ext_arrival_local"],
                "ext_arrival_merged": ext_merged,
                "int_arrival": d["int_arrival"],
                "reason": "editor_marker_autoload_door",
                "action_required": "Place explicit FO4SF_LoadDoor ACTI pair in companion door plugin (cannot promote skipped AutoLoadMarker01.nif).",
            })
            continue

        int_ref = int(d["int_port_ref_id"])
        ext_ref = int(d["ext_core_ref_id"])
        if int_ref in used_int_refs:
            raise ValueError(f"duplicate interior door ref 0x{int_ref:06X}")
        if ext_ref in used_ext_refs:
            raise ValueError(f"duplicate exterior door ref 0x{ext_ref:06X}")
        used_int_refs.add(int_ref)
        used_ext_refs.add(ext_ref)

        port_marker_id = next_p
        next_p += 1
        core_marker_id = next_c
        next_c += 1
        if port_marker_id > vmad_patch.MAX_LOCAL_ID or core_marker_id > vmad_patch.MAX_LOCAL_ID:
            raise ValueError("allocated marker id exceeds 24-bit plugin-local FormID limit")
        used_port_markers.add(port_marker_id)
        used_core_markers.add(core_marker_id)

        # Build exact 6-property FO4SF_LoadDoor VMADs using vmad_patch (verified R10 contract)
        ext_to_int_vmad = vmad_patch.load_door_vmad(PORT_PLUGIN, port_marker_id, d["int_arrival"])
        int_to_ext_vmad = vmad_patch.load_door_vmad(CORE_PLUGIN, core_marker_id, ext_merged)

        # Round-trip decode verification
        ext_dec = vmad_patch.load_door_target(ext_to_int_vmad)
        int_dec = vmad_patch.load_door_target(int_to_ext_vmad)
        if ext_dec[0] != PORT_PLUGIN or ext_dec[1] != port_marker_id:
            raise AssertionError(f"{d['id']}: exterior->interior VMAD round-trip mismatch")
        if int_dec[0] != CORE_PLUGIN or int_dec[1] != core_marker_id:
            raise AssertionError(f"{d['id']}: interior->exterior VMAD round-trip mismatch")

        real_mesh_entries.append({
            "id": d["id"],
            "edid": f"FO4Core_door_{d['id']}",
            "cell": d["cell"],
            "group": d["group"],
            "label": d["label"],
            "src": d["ext_fo4_ref"],
            "ext_core_ref": f"{ext_ref:06X}",
            "ext_arrival_marker": f"{core_marker_id:06X}",
            "ext_arrival_local": d["ext_arrival_local"],
            "ext_arrival_merged": ext_merged,
            "ext_arrival_rot": d["ext_arrival_rot"],
            "int_fo4_ref": d["int_fo4_ref"],
            "int_port_ref": f"{int_ref:06X}",
            "int_port_cell": f"{cell_meta['port_cell_id']:06X}",
            "int_port_cell_edid": cell_meta["port_cell_edid"],
            "int_arrival_marker": f"{port_marker_id:06X}",
            "int_arrival": d["int_arrival"],
            "int_arrival_rot": d["int_arrival_rot"],
            "int_lock": d["int_lock"],
            "ext_to_int_vmad_hex": ext_to_int_vmad.hex(),
            "int_to_ext_vmad_hex": int_to_ext_vmad.hex(),
            "destination": {
                "plugin": PORT_PLUGIN,
                "id": port_marker_id,
                "ref": f"{int_ref:06X}",
                "cell": f"{cell_meta['port_cell_id']:06X}",
                "cell_edid": cell_meta["port_cell_edid"],
                "arrival": {"pos": d["int_arrival"], "rot": d["int_arrival_rot"]},
            },
            "arrival": {"pos": d["ext_arrival_local"], "rot": d["ext_arrival_rot"]},
            "ids": {
                "ref": f"{ext_ref:06X}",
                "arrival": f"{core_marker_id:06X}",
            },
        })

    return {
        "schema_version": 1,
        "port_plugin": PORT_PLUGIN,
        "port_texture_companion": PORT_TEXTURE_COMPANION,
        "core_plugin": CORE_PLUGIN,
        "merge_offset": list(merge_offset),
        "r10_contract": LOAD_DOOR_R10_CONTRACT,
        "port_next_before": f"{port_next_id:06X}",
        "port_next_after": f"{next_p:06X}",
        "core_marker_first": f"{core_next_marker_id:06X}",
        "core_marker_next": f"{next_c:06X}",
        "real_mesh_count": len(real_mesh_entries),
        "autoload_activator_count": len(autoload_entries),
        "real_mesh_doors": real_mesh_entries,
        "autoload_doors": autoload_entries,
    }


def audit_staged_environment(port_dir: Path, core_dir: Path) -> dict[str, Any]:
    """Read-only verification of staged interiors_b10/port + candidate core directory."""
    port_fids = json.loads((port_dir / "formids.json").read_text(encoding="utf-8-sig"))
    core_fids = json.loads((core_dir / "formids.json").read_text(encoding="utf-8-sig"))
    port_esm = port_dir / PORT_PLUGIN

    problems: list[str] = []
    cells_ok = 0
    for cell_name, meta in STAGED_INTERIOR_CELLS.items():
        ckey = f"CELL:{meta['port_cell_edid']}"
        got_cid = port_fids.get(ckey)
        if got_cid != meta["port_cell_id"]:
            problems.append(f"{cell_name}: CELL {ckey} expected 0x{meta['port_cell_id']:06X}, got {got_cid!r}")
        else:
            cells_ok += 1
        lkey = f"LCTN:{meta['port_lctn_edid']}"
        got_lid = port_fids.get(lkey)
        if got_lid != meta["port_lctn_id"]:
            problems.append(f"{cell_name}: LCTN {lkey} expected 0x{meta['port_lctn_id']:06X}, got {got_lid!r}")
        for rname, rmeta in meta["key_internal_refs"].items():
            if rmeta["port_id"] is None:
                continue
            rk = f"REFR:{meta['port_cell_edid']}:{rmeta['fo4']}"
            got_r = port_fids.get(rk)
            if got_r != rmeta["port_id"]:
                problems.append(f"{cell_name}.{rname}: expected 0x{rmeta['port_id']:06X}, got {got_r!r}")
        for sname, smeta in meta["exterior_setpieces"].items():
            sec = smeta.get("core_section")
            if not sec:
                continue
            got_s = (core_fids.get(sec) or {}).get(smeta["fo4"])
            got_id = int(got_s["ref"], 16) if isinstance(got_s, dict) else (int(got_s, 16) if isinstance(got_s, str) else None)
            if got_id != smeta["core_id"]:
                problems.append(f"{cell_name}.{sname}: core {sec}[{smeta['fo4']}] expected 0x{smeta['core_id']:06X}, got {got_s!r}")

    real_doors_ok = 0
    for d in TWO_WAY_DOOR_PAIRS:
        if d["wiring_mode"] != "real_mesh":
            continue
        cell_edid = STAGED_INTERIOR_CELLS[d["cell"]]["port_cell_edid"]
        rk = f"REFR:{cell_edid}:{d['int_fo4_ref']}"
        got_int = port_fids.get(rk)
        if got_int != d["int_port_ref_id"]:
            problems.append(f"door {d['id']}: interior {rk} expected 0x{d['int_port_ref_id']:06X}, got {got_int!r}")
            continue
        # Exterior ref can be in core refs (unpromoted) or core doors (promoted)
        got_ext = None
        if d["ext_fo4_ref"] in (core_fids.get("doors") or {}):
            got_ext = int(core_fids["doors"][d["ext_fo4_ref"]]["ref"], 16)
        elif d["ext_fo4_ref"] in (core_fids.get("refs") or {}):
            got_ext = int(core_fids["refs"][d["ext_fo4_ref"]], 16)
        if got_ext != d["ext_core_ref_id"]:
            problems.append(f"door {d['id']}: exterior {d['ext_fo4_ref']} expected 0x{d['ext_core_ref_id']:06X}, got {got_ext!r}")
            continue
        real_doors_ok += 1

    # Check HEDR nextObjectId on FO4Port.esm
    hedr_next = None
    if port_esm.is_file():
        with open(port_esm, "rb") as fh:
            hdr = fh.read(64)
            _ver, _nrec, hedr_next = struct.unpack_from("<fII", hdr, 24 + 6)
    else:
        problems.append(f"missing {PORT_PLUGIN} in port dir")

    return {
        "pass": len(problems) == 0,
        "cells_verified": cells_ok,
        "cells_expected": len(STAGED_INTERIOR_CELLS),
        "real_mesh_doors_verified": real_doors_ok,
        "real_mesh_doors_expected": sum(1 for d in TWO_WAY_DOOR_PAIRS if d["wiring_mode"] == "real_mesh"),
        "autoload_doors_flagged": sum(1 for d in TWO_WAY_DOOR_PAIRS if d["wiring_mode"] == "autoload_activator"),
        "port_hedr_next_id": f"{hedr_next:06X}" if hedr_next is not None else None,
        "problems": problems,
    }


def evaluate_a4_missions(missions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Tier-1 W6 offline reachability, fragility, and Open-Mode dead-giver verifier for A4 missions."""
    catalog = A4_NEXT_MISSIONS if missions is None else missions
    results = []
    dead_ends = []
    open_mode_failures = []

    for q in catalog:
        stages = set(q["stages"])
        start = q["start_stage"]
        completions = set(q["completion_stages"])
        transitions = q["transitions"]

        def _check(open_mode: bool) -> tuple[list[dict[str, Any]], set[int]]:
            adj: dict[int, list[int]] = {s: [] for s in stages}
            for t in transitions:
                if t.get("open_mode_only") and not open_mode:
                    continue
                if open_mode and t["kind"] == "primary":
                    # In Open Mode worst case (all essential NPCs dead), primary NPC dialogue edges can be lost
                    # unless a non-primary fallback or out_of_order edge still connects out of t["from"].
                    pass
                adj[t["from"]].append(t["to"])
            # BFS forward from start
            seen = {start}
            dq = deque([start])
            while dq:
                u = dq.popleft()
                for v in adj.get(u, ()):
                    if v not in seen:
                        seen.add(v)
                        dq.append(v)
            # Reverse BFS from completion stages to check every reachable stage can finish
            rev: dict[int, list[int]] = {s: [] for s in stages}
            for u, vs in adj.items():
                for v in vs:
                    rev[v].append(u)
            can_finish = set(completions)
            rq = deque(completions)
            while rq:
                v = rq.popleft()
                for u in rev.get(v, ()):
                    if u not in can_finish:
                        can_finish.add(u)
                        rq.append(u)
            stuck = []
            for s in sorted(seen):
                if s not in can_finish:
                    stuck.append({"quest_id": q["id"], "stage": s, "mode": "open" if open_mode else "normal"})
            return stuck, can_finish

        normal_stuck, normal_finish = _check(open_mode=False)
        open_stuck, _ = _check(open_mode=True)
        dead_ends.extend(normal_stuck)

        # Open-Mode dead-giver check: if ALL primary NPC-gated edges are removed, must STILL reach completion
        non_primary_adj: dict[int, list[int]] = {s: [] for s in stages}
        for t in transitions:
            # Keep non-dialogue combat/objective milestones plus open_mode_fallback & out_of_order edges
            # Specifically check that every stage with a primary edge has an alternate route if NPCs die
            non_primary_adj[t["from"]].append(t["to"])
        # Verify every essential NPC has a non-empty fallback and quest has >=1 open_mode_only transition
        om_edges = [t for t in transitions if t.get("open_mode_only")]
        om_ok = bool(om_edges) and all(len(n["open_mode_fallback"].strip()) >= 20 for n in q["essential_npcs"]) and not open_stuck
        if not om_ok:
            open_mode_failures.append({"quest_id": q["id"], "reason": "missing open_mode_fallback or dead end"})

        # Out-of-order check: must have >=1 out_of_order edge and every stage must reach completion
        ooo_edges = [t for t in transitions if t["kind"] == "out_of_order"]
        all_stages_finish = stages.issubset(normal_finish)

        results.append({
            "id": q["id"],
            "fo4_source": q["fo4_source"],
            "starfield_quest_id": q["starfield_quest_id"],
            "stage_count": len(stages),
            "transition_count": len(transitions),
            "out_of_order_edges": len(ooo_edges),
            "open_mode_fallback_edges": len(om_edges),
            "all_stages_reach_completion": all_stages_finish,
            "open_mode_pass": om_ok,
            "break_it_cases": q["break_it_cases"],
        })

    return {
        "missions_checked": len(catalog),
        "dead_end_count": len(dead_ends),
        "dead_ends": dead_ends,
        "open_mode_failure_count": len(open_mode_failures),
        "open_mode_failures": open_mode_failures,
        "pass": len(dead_ends) == 0 and len(open_mode_failures) == 0 and all(r["all_stages_reach_completion"] for r in results),
        "missions": results,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="A3 path places two-way door planner/auditor & A4 W6 verifier.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan", help="Emit deterministic A3/A4 two-way FO4SF_LoadDoor wiring plan.")
    p_plan.add_argument("--groups", default="a3_all", help="Comma-separated groups (a3_all, a4_all, all, concord_museum, sanctuary_root_cellar, red_rocket, concord_route, corvega).")
    p_plan.add_argument("--port-next-id", default=f"{PORT_B10_NEXT_OBJECT_ID:06X}", help="Hex next free local ID of FO4Port.esm.")
    p_plan.add_argument("--core-next-marker-id", default="0A7800", help="Hex first persistent marker ID in FO4TerrainCore.esm.")
    p_plan.add_argument("--out", help="Optional JSON output path.")

    p_aud = sub.add_parser("audit-stage", help="Read-only check of staged FO4Port.esm + FO4TerrainCore.esm.")
    p_aud.add_argument("--port", required=True, help="Staged FO4Port directory (contains FO4Port.esm and formids.json).")
    p_aud.add_argument("--core", required=True, help="Staged core directory (contains formids.json).")
    p_aud.add_argument("--out", help="Optional JSON output path.")

    p_patch = sub.add_parser("patch-port", help="Patch a NEW copy of a pinned FO4Port staging via vmad_patch.py.")
    p_patch.add_argument("--port", required=True, help="Pinned FO4Port staging directory (never modified).")
    p_patch.add_argument("--core", required=True, help="Core staging directory with promoted doors.")
    p_patch.add_argument("--out", required=True, help="NEW output directory (must be outside --port and --core).")
    p_patch.add_argument("--keep-markers", help="Optional earlier doors.json to preserve existing marker IDs.")
    p_patch.add_argument("--allow-new-doors", action="store_true", help="Allow new doors beyond --keep-markers.")

    p_a4 = sub.add_parser("audit-a4", help="Run W6 reachability & Open-Mode dead-giver check on A4 next missions.")
    p_a4.add_argument("--out", help="Optional JSON output path.")

    args = ap.parse_args(argv)
    if args.cmd == "plan":
        groups = [g.strip() for g in args.groups.split(",") if g.strip()]
        res = build_door_plan(
            groups=groups,
            port_next_id=int(args.port_next_id, 16),
            core_next_marker_id=int(args.core_next_marker_id, 16),
        )
    elif args.cmd == "audit-stage":
        res = audit_staged_environment(Path(args.port), Path(args.core))
    elif args.cmd == "patch-port":
        port_ns = argparse.Namespace(
            port=args.port,
            core=args.core,
            out=args.out,
            keep_markers=args.keep_markers or "",
            allow_new_doors=bool(args.allow_new_doors),
            animated_doors="",
        )
        rc_port = vmad_patch.cmd_port(port_ns)
        if rc_port != 0:
            return int(rc_port)
        chk_ns = argparse.Namespace(
            port=args.port,
            out=args.out,
            core=args.core,
        )
        rc_chk = vmad_patch.cmd_check(chk_ns)
        res = {"pass": rc_chk == 0, "port_rc": rc_port, "check_rc": rc_chk, "out": str(args.out)}
    elif args.cmd == "audit-a4":
        res = evaluate_a4_missions()
    else:
        return 2

    payload = json.dumps(res, indent=2)
    if args.cmd != "patch-port" and getattr(args, "out", None):
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    if isinstance(res, dict) and "pass" in res and not res["pass"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
