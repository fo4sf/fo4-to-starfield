"""CF-1 multi-title StartWorld descriptor table for FO4SFNewGame + Combat, Reputation, and Squad seeds.

Parameterizes New Game world starts across all seven Fallout titles plus faction alternate starts without
hardcoding Vault111Cryo assumptions:
  - Standard vault / courier / villager starts initialize neutral Karma (0), 0 faction Fame/Infamy, and the
    base 2-slot companion cap.
  - Tactical and faction starts (`bunkeralpha`, `minuteman_volunteer`, `brotherhood_initiate`, `ncr_trooper`,
    `desert_ranger`) seed explicit `combat_title_rule`, `initial_fame`, and `squad_base_cap` descriptors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional


@dataclass(frozen=True)
class StartWorldDescriptor:
    key: str
    title: str
    world_id: str
    start_cell: str
    surface_anchor: str
    combat_title_rule: int = 0          # FO4SFCombat.esm 0x803 (0=FO4SF/FNV, 1=FO3, 2=FO4, 3=FO76, 4=Classic)
    initial_karma: int = 0              # FO4SFReputation.esm 0x801 (-1000..+1000)
    initial_fame: Mapping[str, int] = field(default_factory=dict)  # FO4SFReputation.esm faction slot -> Fame
    squad_base_cap: int = 2             # FO4SFCompanions.esm 0x801 (2 default; 4 for tactical/leadership starts)
    default_background: Optional[str] = None


START_WORLD_TABLE: Dict[str, StartWorldDescriptor] = {
    "vault111": StartWorldDescriptor(
        key="vault111",
        title="FO4",
        world_id="Commonwealth",
        start_cell="FO4Port_Vault111Cryo",
        surface_anchor="Commonwealth_Vault111Hilltop",
        combat_title_rule=0,
        initial_karma=0,
        initial_fame={},
        squad_base_cap=2,
        default_background="VaultDweller",
    ),
    "vault101": StartWorldDescriptor(
        key="vault101",
        title="FO3",
        world_id="CapitalWasteland",
        start_cell="FO3Port_Vault101Exit",
        surface_anchor="CapitalWasteland_ScenicOverlook",
        combat_title_rule=1,
        initial_karma=0,
        initial_fame={},
        squad_base_cap=2,
        default_background="VaultDweller",
    ),
    "goodsprings": StartWorldDescriptor(
        key="goodsprings",
        title="FNV",
        world_id="MojaveWasteland",
        start_cell="FNVPort_GSDocMitchellHouse",
        surface_anchor="Mojave_GoodspringsPorch",
        combat_title_rule=0,
        initial_karma=0,
        initial_fame={},
        squad_base_cap=2,
        default_background="MojaveCourier",
    ),
    "vault76": StartWorldDescriptor(
        key="vault76",
        title="FO76",
        world_id="Appalachia",
        start_cell="FO76Port_Vault76Bedroom",
        surface_anchor="Appalachia_Vault76Plaza",
        combat_title_rule=3,
        initial_karma=0,
        initial_fame={},
        squad_base_cap=2,
        default_background="VaultDweller",
    ),
    "vault13": StartWorldDescriptor(
        key="vault13",
        title="FO1",
        world_id="SouthernCalifornia",
        start_cell="FO1Port_Vault13Cave",
        surface_anchor="SoCal_Vault13Entrance",
        combat_title_rule=4,
        initial_karma=0,
        initial_fame={},
        squad_base_cap=2,
        default_background="VaultDweller",
    ),
    "arroyo": StartWorldDescriptor(
        key="arroyo",
        title="FO2",
        world_id="NorthernCalifornia",
        start_cell="FO2Port_TempleOfTrials",
        surface_anchor="NorCal_ArroyoBridge",
        combat_title_rule=4,
        initial_karma=0,
        initial_fame={},
        squad_base_cap=2,
        default_background="WastelandScavenger",
    ),
    "bunkeralpha": StartWorldDescriptor(
        key="bunkeralpha",
        title="FOT",
        world_id="MidwestCorridor",
        start_cell="FOTPort_BunkerAlphaBriefing",
        surface_anchor="Midwest_BrahminWoodLZ",
        combat_title_rule=0,
        initial_karma=0,
        initial_fame={"Brotherhood": 40},
        squad_base_cap=4,
        default_background="BrotherhoodScribe",
    ),
    # Faction / leadership alternate starts requiring explicit Reputation & Warfare Squad start descriptors
    "minuteman_volunteer": StartWorldDescriptor(
        key="minuteman_volunteer",
        title="FO4",
        world_id="Commonwealth",
        start_cell="FO4Port_ConcordMuseum",
        surface_anchor="Commonwealth_Concord",
        combat_title_rule=0,
        initial_karma=150,
        initial_fame={"Minutemen": 45, "Settlers": 30},
        squad_base_cap=4,
        default_background="MinutemanVolunteer",
    ),
    "brotherhood_initiate": StartWorldDescriptor(
        key="brotherhood_initiate",
        title="FO4",
        world_id="Commonwealth",
        start_cell="FO4Port_CambridgePD",
        surface_anchor="Commonwealth_CambridgePoliceStation",
        combat_title_rule=0,
        initial_karma=0,
        initial_fame={"Brotherhood": 45},
        squad_base_cap=2,
        default_background="BrotherhoodScribe",
    ),
    "ncr_trooper": StartWorldDescriptor(
        key="ncr_trooper",
        title="FNV",
        world_id="MojaveWasteland",
        start_cell="FNVPort_MojaveOutpostBarracks",
        surface_anchor="Mojave_OutpostCourtyard",
        combat_title_rule=0,
        initial_karma=0,
        initial_fame={"NCR": 45},
        squad_base_cap=2,
        default_background="CaravanGuard",
    ),
    "desert_ranger": StartWorldDescriptor(
        key="desert_ranger",
        title="FNV",
        world_id="MojaveWasteland",
        start_cell="FNVPort_RangerStationAlpha",
        surface_anchor="Mojave_RangerStation",
        combat_title_rule=0,
        initial_karma=100,
        initial_fame={"NCR": 50},
        squad_base_cap=4,
        default_background="DesertRanger",
    ),
}


def get_start_world(key: str) -> StartWorldDescriptor:
    norm = key.strip().lower()
    if norm not in START_WORLD_TABLE:
        raise KeyError(f"unknown StartWorld descriptor: {key}")
    return START_WORLD_TABLE[norm]
