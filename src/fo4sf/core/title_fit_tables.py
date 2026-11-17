"""Unified multi-title data tables resolving `GAP-J3-01`..`GAP-J3-04` across `FO1`..`FO76` with byte-identical `FO4` defaults.

Derived from the 8-game quest, script, and record census (`docs/research/core-fit-by-title.md`):
  1. `GAP-J3-01`: Canonical `(15.0, 40.0, 75.0)` 16-state `REPU` matrix (`NV_16_STATE_MATRIX`) shared between
     progression and reputation checks (`(fame=1, infamy=1) -> "Mixed"`, `(fame=2, infamy=2) -> "Unpredictable"`).
  2. `GAP-J3-02`: 16-slot faction bank (`0..15`) preserving Fallout 4's 8 core slots (`0..7` at FormIDs `0x810..0x877`)
     byte-for-byte while giving New Vegas's 13 `REPU` records collision-free indices (`0..12`).
  3. `GAP-J3-03`: Source `AMMO` / `.pro` calibre lookup (`TITLE_AMMO_CALIBRE_MAP`) and distinct `.50 Cal` subtype IDs
     without mutating Fallout 4 / Starfield `0x82C..0x836` FormIDs.
  4. `GAP-J3-04`: Per-title `StartWorldFitDefaults` (`perk_cadence_default`, `rads_rule_default`,
     `pa_training_required`, `speech_check_mode`) keeping `FO4` (`vault111`) byte-for-byte unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Tuple

# ---------------------------------------------------------------------------
# 1. Canonical 16-State Reputation Thresholds & Matrix (GAP-J3-01)
# ---------------------------------------------------------------------------

REPU_TIER_THRESHOLDS: Tuple[float, float, float] = (15.0, 40.0, 75.0)

# Indexed as NV_16_STATE_MATRIX[fame_tier][infamy_tier] where tier in 0..3 (None, Low, Medium, High)
NV_16_STATE_MATRIX: Tuple[Tuple[str, str, str, str], ...] = (
    ("Neutral", "Shunned", "Hated", "Vilified"),
    ("Accepted", "Mixed", "Merciful Thug", "Soft-Hearted Devil"),
    ("Liked", "Smiling Troublemaker", "Unpredictable", "Dark Hero"),
    ("Idolized", "Good-Natured Rascal", "Wild Child", "Wild Child"),
)


def repu_axis_tier(score: float, thresholds: Tuple[float, float, float] = REPU_TIER_THRESHOLDS) -> int:
    t1, t2, t3 = thresholds
    if score >= t3:
        return 3
    if score >= t2:
        return 2
    if score >= t1:
        return 1
    return 0


def evaluate_nv_16_state(fame: float, infamy: float) -> Tuple[int, int, str]:
    ft = repu_axis_tier(fame)
    it = repu_axis_tier(infamy)
    return ft, it, NV_16_STATE_MATRIX[ft][it]


# ---------------------------------------------------------------------------
# 2. 16-Slot Multi-Title Faction Bank Preserving FO4 Slots 0..7 (GAP-J3-02)
# ---------------------------------------------------------------------------

FO4_CORE_SLOTS_0_TO_7: Tuple[Tuple[int, str, int], ...] = (
    (0, "Minutemen", 0x000810),
    (1, "Brotherhood", 0x00081E),
    (2, "Railroad", 0x00082C),
    (3, "Institute", 0x00083A),
    (4, "Settlers", 0x000848),
    (5, "DiamondCity", 0x000856),
    (6, "Goodneighbor", 0x000864),
    (7, "RaidersOutlaws", 0x000872),
)

FNV_13_REPU_BANK: Tuple[Tuple[int, str, int], ...] = (
    (0, "NV_NCR", 0x0F43DE),
    (1, "NV_Brotherhood", 0x11EDFC),
    (2, "NV_Followers", 0x124AD1),
    (3, "NV_CaesarsLegion", 0x0F43DD),
    (4, "NV_Goodsprings", 0x104C22),
    (5, "NV_TheStrip", 0x118F61),
    (6, "NV_Freeside", 0x129A7A),
    (7, "NV_PowderGangers", 0x1558E6),
    (8, "NV_Primm", 0x0F43DF),
    (9, "NV_Novac", 0x129A79),
    (10, "NV_Boomers", 0x0FFAE8),
    (11, "NV_GreatKhans", 0x11989B),
    (12, "NV_WhiteGloveSociety", 0x116F16),
)


# ---------------------------------------------------------------------------
# 3. Multi-Title Source Ammo -> Starfield Calibre Family Map (GAP-J3-03)
# ---------------------------------------------------------------------------

FO4_STARFIELD_SUBTYPE_FORMIDS: Mapping[str, int] = {
    "FO4SF_Ammo777_AP": 0x00082C,
    "FO4SF_Ammo777_JHP": 0x00082D,
    "FO4SF_Ammo777_PlusP": 0x00082E,
    "FO4SF_Ammo11mm_AP": 0x00082F,
    "FO4SF_Ammo11mm_JHP": 0x000830,
    "FO4SF_Shotgun_Slug": 0x000831,
    "FO4SF_Shotgun_Flechette": 0x000832,
    "FO4SF_Shotgun_Magnum": 0x000833,
    "FO4SF_Laser_Overcharge": 0x000834,
    "FO4SF_Laser_Optimized": 0x000835,
    "FO4SF_Laser_MaxCharge": 0x000836,
}

EXTENDED_50CAL_SUBTYPE_IDS: Mapping[str, str] = {
    "AP": "FO4SF_Ammo50Cal_AP",
    "JHP": "FO4SF_Ammo50Cal_JHP",
    "Match": "FO4SF_Ammo50Cal_Match",
}

TITLE_AMMO_CALIBRE_MAP: Mapping[str, Mapping[str, str]] = {
    "FO1": {
        "10mm": "pistol_11mm",
        "223_fmg": "rifle_777",
        "5mm": "rifle_777",
        "14mm": "heavy_50cal",
        "shotgun_12ga": "shotgun_12ga",
        "small_energy_cell": "energy_laser",
        "micro_fusion_cell": "energy_laser",
    },
    "FO2": {
        "10mm": "pistol_11mm",
        "44_magnum": "pistol_11mm",
        "223_fmg": "rifle_777",
        "5mm": "rifle_777",
        "762mm": "rifle_777",
        "2mm_ec": "heavy_50cal",
        "shotgun_12ga": "shotgun_12ga",
        "small_energy_cell": "energy_laser",
        "micro_fusion_cell": "energy_laser",
    },
    "FO3": {
        "Ammo10mm": "pistol_11mm",
        "Ammo32Caliber": "pistol_11mm",
        "Ammo44magnum": "pistol_11mm",
        "Ammo556mm": "rifle_777",
        "Ammo5mm": "rifle_777",
        "Ammo308Caliber": "heavy_50cal",
        "AmmoShotgun12Ga": "shotgun_12ga",
        "AmmoSmallEnergyCell": "energy_laser",
        "AmmoMicroFusionCell": "energy_laser",
    },
    "FNV": {
        "Ammo9mm": "pistol_11mm",
        "Ammo10mm": "pistol_11mm",
        "Ammo45Auto": "pistol_11mm",
        "Ammo556mm": "rifle_777",
        "Ammo5mm": "rifle_777",
        "Ammo308": "heavy_50cal",
        "Ammo50MG": "heavy_50cal",
        "Ammo12Ga": "shotgun_12ga",
        "Ammo20Ga": "shotgun_12ga",
        "AmmoSmallEnergyCell": "energy_laser",
        "AmmoMicroFusionCell": "energy_laser",
    },
    "FO4": {
        "Ammo10mm": "pistol_11mm",
        "Ammo38Caliber": "pistol_11mm",
        "Ammo45Caliber": "rifle_777",
        "Ammo556": "rifle_777",
        "Ammo308Caliber": "heavy_50cal",
        "Ammo50Caliber": "heavy_50cal",
        "AmmoShotgunShell": "shotgun_12ga",
        "AmmoFusionCell": "energy_laser",
    },
    "FO76": {
        "Ammo10mm": "pistol_11mm",
        "Ammo556": "rifle_777",
        "Ammo308": "heavy_50cal",
        "Ammo50Caliber": "heavy_50cal",
        "AmmoShotgunShell": "shotgun_12ga",
        "AmmoFusionCell": "energy_laser",
    },
}


# ---------------------------------------------------------------------------
# 4. Per-Title StartWorld Progression, Rads, PA & Speech Defaults (GAP-J3-04)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StartWorldFitDefaults:
    title: str
    start_key: str
    perk_cadence_default: int
    rads_rule_default: int          # 0 = Mode A (-10% Max HP / 100 rads), 1 = Mode B (classic stat sickness)
    pa_training_required: bool
    speech_check_mode: str          # "deterministic" | "roll_pct"
    special_pool_points: int = 40


TITLE_START_FIT_DEFAULTS: Dict[str, StartWorldFitDefaults] = {
    "FO1": StartWorldFitDefaults("FO1", "vault13", perk_cadence_default=3, rads_rule_default=1, pa_training_required=False, speech_check_mode="deterministic"),
    "FO2": StartWorldFitDefaults("FO2", "arroyo", perk_cadence_default=3, rads_rule_default=1, pa_training_required=False, speech_check_mode="deterministic"),
    "FOT": StartWorldFitDefaults("FOT", "bunkeralpha", perk_cadence_default=3, rads_rule_default=1, pa_training_required=False, speech_check_mode="deterministic"),
    "FO3": StartWorldFitDefaults("FO3", "vault101", perk_cadence_default=1, rads_rule_default=1, pa_training_required=True, speech_check_mode="deterministic"),
    "FNV": StartWorldFitDefaults("FNV", "goodsprings", perk_cadence_default=2, rads_rule_default=1, pa_training_required=False, speech_check_mode="deterministic"),
    "FO4": StartWorldFitDefaults("FO4", "vault111", perk_cadence_default=1, rads_rule_default=0, pa_training_required=False, speech_check_mode="deterministic"),
    "FO76": StartWorldFitDefaults("FO76", "vault76", perk_cadence_default=1, rads_rule_default=0, pa_training_required=False, speech_check_mode="deterministic"),
}
