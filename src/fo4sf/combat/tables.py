"""Pure-Python combat rules, cross-title data tables, ammo DT/DR math, VATS hit/AP formulas, and log parser.

Mirrors the runtime formulas in scripts/combat/FO4SF_CombatQuest.psc and record definitions in
dotnet/CombatCore/Program.cs so unit tests and offline log verification share one locked specification.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

# Unified 8-zone body-part taxonomy shared across humans, robots, and creatures.
# Maps directly onto Starfield's live limb-condition AVIFs (0x00036C..0x000372).
ZONES: Tuple[str, ...] = (
    "head",
    "torso",
    "left_arm",
    "right_arm",
    "left_leg",
    "right_leg",
    "special_optic",
    "special_core",
)

ZONE_TO_STARFIELD_AVIF: Dict[str, Tuple[int, str]] = {
    "head": (0x00036C, "PerceptionCondition"),
    "torso": (0x00036D, "EnduranceCondition"),
    "left_arm": (0x00036E, "LeftAttackCondition"),
    "right_arm": (0x00036F, "RightAttackCondition"),
    "left_leg": (0x000370, "LeftMobilityCondition"),
    "right_leg": (0x000371, "RightMobilityCondition"),
    "special_optic": (0x00036C, "PerceptionCondition"),
    "special_core": (0x000372, "BrainCondition"),
}

# One unified rule set across humans, robots, and creatures; only zone multipliers vary by anatomy.
ARCHETYPE_ZONE_MULTS: Dict[str, Dict[str, float]] = {
    "human": {
        "head": 2.00,
        "torso": 1.00,
        "left_arm": 0.85,
        "right_arm": 0.85,
        "left_leg": 0.85,
        "right_leg": 0.85,
        "special_optic": 2.20,
        "special_core": 1.50,  # Boostpack / dorsal tank
    },
    "robot": {
        "head": 1.25,
        "torso": 0.75,         # Armored chassis plating
        "left_arm": 0.85,
        "right_arm": 0.85,
        "left_leg": 0.85,
        "right_leg": 0.85,
        "special_optic": 1.75, # Optical sensor array
        "special_core": 1.65,  # Combat Inhibitor / power core
    },
    "creature": {
        "head": 1.75,
        "torso": 0.90,         # Dorsal carapace
        "left_arm": 0.85,
        "right_arm": 0.85,
        "left_leg": 0.85,
        "right_leg": 0.85,
        "special_optic": 2.00,
        "special_core": 1.85,  # Unarmored underbelly / spore sac
    },
}

# VATS base geometry hit-chance modifier per targetable zone.
ZONE_VATS_HIT_FACTOR: Dict[str, float] = {
    "head": 0.65,
    "torso": 1.00,
    "left_arm": 0.80,
    "right_arm": 0.80,
    "left_leg": 0.82,
    "right_leg": 0.82,
    "special_optic": 0.45,
    "special_core": 0.60,
}

# Per-title combat rules table across all 7 Fallout titles + unified FO4SF profile.
TITLE_COMBAT_TABLES: Dict[str, Dict[str, object]] = {
    "FO1": {
        "armor_model": "dt_then_dr",
        "min_damage_floor_mult": 0.00,
        "head_mult": 2.00,
        "limb_mult": 1.00,
        "cripple_limb_hp_pct": 0.0,
        "vats_time_scale": 0.00,  # Turn-based aimed shot (+1 AP)
        "hardcore_limb_cure": "doctor_skill_or_bag",
        "ammo_mod_source": "ac_dr_dmg_div_mult",
    },
    "FO2": {
        "armor_model": "dt_then_dr",
        "min_damage_floor_mult": 0.00,
        "head_mult": 2.00,
        "limb_mult": 1.00,
        "cripple_limb_hp_pct": 0.0,
        "vats_time_scale": 0.00,
        "hardcore_limb_cure": "doctor_skill_or_bag",
        "ammo_mod_source": "jhp_ap_dr_div_mult",
    },
    "FOT": {
        "armor_model": "dt_then_dr",
        "min_damage_floor_mult": 0.05,
        "head_mult": 2.00,
        "limb_mult": 0.90,
        "cripple_limb_hp_pct": 0.0,
        "vats_time_scale": 0.25,  # Continuous Turn-Based (CTB) / squad aimed shot
        "hardcore_limb_cure": "traumakit_or_doctor_bag",
        "ammo_mod_source": "calibre_subtypes",
    },
    "FO3": {
        "armor_model": "dr_only",
        "max_dr_cap_pct": 85.0,
        "min_damage_floor_mult": 0.05,
        "head_mult": 2.00,
        "limb_mult": 1.00,
        "cripple_limb_hp_pct": 0.0,
        "vats_time_scale": 0.02,  # Near-freeze playback
        "hardcore_limb_cure": "stimpak_or_bed",
        "ammo_mod_source": "base_ammo_only",
    },
    "FNV": {
        "armor_model": "dr_then_dt",
        "max_dr_cap_pct": 85.0,
        "min_damage_floor_mult": 0.20,  # fMinDamMultiplier = 0.20
        "head_mult": 2.00,
        "limb_mult": 0.85,
        "cripple_limb_hp_pct": 0.0,
        "vats_time_scale": 0.05,
        "hardcore_limb_cure": "doctors_bag_or_hydra",
        "ammo_mod_source": "amef_subtypes_and_rcpe",
    },
    "FO4": {
        "armor_model": "power_law_dr",
        "min_damage_floor_mult": 0.15,
        "head_mult": 2.00,
        "limb_mult": 0.85,
        "cripple_limb_hp_pct": 0.0,
        "vats_time_scale": 0.04,  # Slow-time VATS
        "hardcore_limb_cure": "stimpak",
        "ammo_mod_source": "omod_receiver_only",
    },
    "FO76": {
        "armor_model": "power_law_dr",
        "min_damage_floor_mult": 0.15,
        "head_mult": 2.00,
        "limb_mult": 0.85,
        "cripple_limb_hp_pct": 0.0,
        "vats_time_scale": 1.00,  # Real-time VATS lock
        "hardcore_limb_cure": "stimpak",
        "ammo_mod_source": "ultracite_receiver_only",
    },
    "FO4SF": {
        "armor_model": "dr_then_dt",
        "max_dr_cap_pct": 85.0,
        "min_damage_floor_mult": 0.20,
        "head_mult": 2.00,
        "limb_mult": 0.85,
        "cripple_limb_hp_pct": 0.0,
        "vats_time_scale": 0.25,  # Slow-time targeting mode on hotkey (V)
        "hardcore_limb_cure": "doctors_bag_in_hardcore_else_stimpak",
        "ammo_mod_source": "calibre_table_and_reloading_bench",
    },
}


@dataclass(frozen=True)
class AmmoSubtypeSpec:
    key: str
    slot: int
    label: str
    dmg_mult: float
    dt_pierce: float
    dt_mult: float
    spread_mult: float
    wear_mult: float


AMMO_SUBTYPES: Dict[str, Tuple[AmmoSubtypeSpec, ...]] = {
    "standard_ballistic": (
        AmmoSubtypeSpec("standard", 0, "Standard", 1.00, 0.0, 1.00, 1.00, 1.00),
        AmmoSubtypeSpec("ap", 1, "AP", 0.95, 15.0, 1.00, 1.00, 1.10),
        AmmoSubtypeSpec("jhp", 2, "JHP", 1.65, 0.0, 2.00, 1.00, 1.00),
        AmmoSubtypeSpec("plus_p", 3, "+P", 1.25, 5.0, 1.00, 1.05, 1.25),
    ),
    "shotgun": (
        AmmoSubtypeSpec("buckshot", 0, "Buckshot", 1.20, 0.0, 1.50, 1.35, 1.00),
        AmmoSubtypeSpec("slug", 1, "Slug", 1.15, 10.0, 1.00, 0.45, 1.05),
        AmmoSubtypeSpec("flechette", 2, "Flechette (AP)", 0.95, 14.0, 1.00, 0.85, 1.10),
        AmmoSubtypeSpec("magnum", 3, "Magnum (+P)", 1.30, 4.0, 1.00, 1.25, 1.25),
    ),
    "energy": (
        AmmoSubtypeSpec("standard_cell", 0, "Standard Cell", 1.00, 0.0, 1.00, 1.00, 1.00),
        AmmoSubtypeSpec("overcharge", 1, "Overcharge (AP)", 1.25, 10.0, 1.00, 1.00, 1.25),
        AmmoSubtypeSpec("optimized", 2, "Optimized (JHP)", 1.30, 5.0, 1.00, 0.95, 1.10),
        AmmoSubtypeSpec("max_charge", 3, "Max Charge (+P)", 1.50, 15.0, 1.00, 1.05, 1.75),
    ),
}

# Calibre data table keyed by Starfield.esm base Ammo EditorID (resolved at runtime via Weapon.GetAmmo()).
# Zero per-weapon edits: every weapon inherits its subtype cycle from its base Ammo calibre.
CALIBRE_FAMILIES: Dict[str, Dict[str, object]] = {
    "Ammo777mm": {
        "starfield_form_id": 0x04AD3E,
        "family": "standard_ballistic",
        "nv_analogue": "5mm / 5.56mm Caseless",
        "subtypes": ("Standard", "FO4SF_Ammo777_AP", "FO4SF_Ammo777_JHP", "FO4SF_Ammo777_PlusP"),
    },
    "Ammo11mm": {
        "starfield_form_id": 0x04AD3F,
        "family": "standard_ballistic",
        "nv_analogue": "10mm / .45 Auto",
        "subtypes": ("Standard", "FO4SF_Ammo11mm_AP", "FO4SF_Ammo11mm_JHP", "FO4SF_Ammo11mm_PlusP"),
    },
    "AmmoShotgun": {
        "starfield_form_id": 0x0547A1,
        "family": "shotgun",
        "nv_analogue": "12 Gauge (Buckshot / Slug / Flechette / Magnum)",
        "subtypes": ("Buckshot", "FO4SF_AmmoShotgun_Slug", "FO4SF_AmmoShotgun_Flechette", "FO4SF_AmmoShotgun_Magnum"),
    },
    "AmmoLaser": {
        "starfield_form_id": 0x00E8EC,
        "family": "energy",
        "nv_analogue": "Microfusion / Energy Cell",
        "subtypes": ("Standard Cell", "FO4SF_AmmoLaser_Overcharge", "FO4SF_AmmoLaser_Optimized", "FO4SF_AmmoLaser_MaxCharge"),
    },
    "Ammo50Cal": {
        "starfield_form_id": 0x2B559A,
        "family": "standard_ballistic",
        "nv_analogue": ".50 MG / .308",
        "subtypes": ("Standard", "FO4SF_Ammo50Cal_AP", "FO4SF_Ammo777_JHP", "FO4SF_Ammo777_PlusP"),
    },
}

# Reloading-bench COBJ recipes hooking into #813 (FO4SFWorkshop.esm WorkbenchIndustrialKeyword 0x0AA209 + IRES).
RELOADING_BENCH_RECIPES: Tuple[Dict[str, object], ...] = (
    {
        "form_id": 0x830,
        "edid": "FO4SF_RCPE_Ammo777_AP",
        "product_edid": "FO4SF_Ammo777_AP",
        "amount": 24,
        "bench_keyword": "WorkbenchIndustrialKeyword",
        "ires_costs": (("ResInorgCommonLead", 2), ("ResInorgCommonIron", 2), ("ResInorgCommonCopper", 1)),
    },
    {
        "form_id": 0x831,
        "edid": "FO4SF_RCPE_Ammo777_JHP",
        "product_edid": "FO4SF_Ammo777_JHP",
        "amount": 24,
        "bench_keyword": "WorkbenchIndustrialKeyword",
        "ires_costs": (("ResInorgCommonLead", 3), ("ResInorgCommonCopper", 2)),
    },
    {
        "form_id": 0x832,
        "edid": "FO4SF_RCPE_Ammo777_PlusP",
        "product_edid": "FO4SF_Ammo777_PlusP",
        "amount": 24,
        "bench_keyword": "WorkbenchIndustrialKeyword",
        "ires_costs": (("ResInorgCommonLead", 2), ("ResInorgCommonCopper", 2), ("ResOrgExoticLubricant", 1)),
    },
    {
        "form_id": 0x833,
        "edid": "FO4SF_RCPE_Shotgun_Slug",
        "product_edid": "FO4SF_AmmoShotgun_Slug",
        "amount": 12,
        "bench_keyword": "WorkbenchIndustrialKeyword",
        "ires_costs": (("ResInorgCommonLead", 3), ("ResInorgCommonIron", 1)),
    },
    {
        "form_id": 0x834,
        "edid": "FO4SF_RCPE_Shotgun_Flechette",
        "product_edid": "FO4SF_AmmoShotgun_Flechette",
        "amount": 12,
        "bench_keyword": "WorkbenchIndustrialKeyword",
        "ires_costs": (("ResInorgCommonIron", 2), ("ResInorgUncommonTungsten", 2)),
    },
    {
        "form_id": 0x835,
        "edid": "FO4SF_RCPE_Laser_Overcharge",
        "product_edid": "FO4SF_AmmoLaser_Overcharge",
        "amount": 20,
        "bench_keyword": "WorkbenchIndustrialKeyword",
        "ires_costs": (("ResInorgCommonCopper", 2), ("ResInorgCommonUranium", 1)),
    },
)


def get_subtype_spec(family: str, slot: int) -> AmmoSubtypeSpec:
    specs = AMMO_SUBTYPES.get(family)
    if not specs:
        raise ValueError(f"unknown ammo family: {family}")
    return specs[slot % len(specs)]


def cycle_ammo_subtype(current_slot: int, family: str = "standard_ballistic") -> AmmoSubtypeSpec:
    specs = AMMO_SUBTYPES.get(family)
    if not specs:
        raise ValueError(f"unknown ammo family: {family}")
    next_slot = (int(current_slot) + 1) % len(specs)
    return specs[next_slot]


def compute_ballistic_dt_dr(
    base_damage: float,
    target_dt: float,
    target_dr_pct: float = 0.0,
    subtype: Optional[AmmoSubtypeSpec] = None,
    min_floor_mult: float = 0.20,
) -> Dict[str, float]:
    """New Vegas DR-then-DT damage model with subtype damage multiplier, DT multiplier, and DT pierce."""
    if base_damage < 0:
        raise ValueError("base_damage must be non-negative")
    sub = subtype or AMMO_SUBTYPES["standard_ballistic"][0]
    scaled_raw = base_damage * sub.dmg_mult
    clamped_dr = min(85.0, max(0.0, target_dr_pct))
    after_dr = scaled_raw * (1.0 - (clamped_dr / 100.0))
    effective_dt = max(0.0, max(0.0, target_dt) * sub.dt_mult - sub.dt_pierce)
    floor_dmg = scaled_raw * min_floor_mult
    final_damage = max(floor_dmg, after_dr - effective_dt)
    return {
        "scaled_raw": round(scaled_raw, 3),
        "after_dr": round(after_dr, 3),
        "effective_dt": round(effective_dt, 3),
        "floor_damage": round(floor_dmg, 3),
        "final_damage": round(final_damage, 3),
    }


def compute_zone_hit(
    base_damage: float,
    zone: str,
    archetype: str = "human",
    target_dt: float = 0.0,
    target_dr_pct: float = 0.0,
    subtype: Optional[AmmoSubtypeSpec] = None,
    limb_hp_before: float = 100.0,
    limb_damage_scale: float = 1.25,
) -> Dict[str, object]:
    """Apply unified hit-location multiplier, DT/DR mitigation, and limb condition damage."""
    if archetype not in ARCHETYPE_ZONE_MULTS:
        raise ValueError(f"unknown archetype: {archetype}")
    zone_map = ARCHETYPE_ZONE_MULTS[archetype]
    if zone not in zone_map:
        raise ValueError(f"unknown zone: {zone}")
    zone_mult = zone_map[zone]
    dt_dr = compute_ballistic_dt_dr(base_damage, target_dt=target_dt, target_dr_pct=target_dr_pct, subtype=subtype)
    applied_hp_damage = round(dt_dr["final_damage"] * zone_mult, 3)
    limb_loss = round(applied_hp_damage * limb_damage_scale, 3)
    limb_after = round(max(0.0, limb_hp_before - limb_loss), 3)
    newly_crippled = limb_hp_before > 0.0 and limb_after <= 0.0
    return {
        "archetype": archetype,
        "zone": zone,
        "zone_mult": zone_mult,
        "effective_dt": dt_dr["effective_dt"],
        "post_dt_damage": dt_dr["final_damage"],
        "applied_damage": applied_hp_damage,
        "limb_hp_before": limb_hp_before,
        "limb_hp_after": limb_after,
        "crippled": limb_after <= 0.0,
        "newly_crippled": newly_crippled,
    }


def evaluate_cripple_state(limb_hp: Mapping[str, float], prev_right_arm_crippled: bool = False) -> Dict[str, object]:
    """Compute slow-walk, aim-sway, perception, and weapon-drop penalties from limb conditions (0..100)."""
    left_leg_c = limb_hp.get("left_leg", 100.0) <= 0.0
    right_leg_c = limb_hp.get("right_leg", 100.0) <= 0.0
    left_arm_c = limb_hp.get("left_arm", 100.0) <= 0.0
    right_arm_c = limb_hp.get("right_arm", 100.0) <= 0.0
    head_c = limb_hp.get("head", 100.0) <= 0.0 or limb_hp.get("special_optic", 100.0) <= 0.0
    torso_c = limb_hp.get("torso", 100.0) <= 0.0
    core_c = limb_hp.get("special_core", 100.0) <= 0.0

    crippled_legs = int(left_leg_c) + int(right_leg_c)
    crippled_arms = int(left_arm_c) + int(right_arm_c)

    if crippled_legs >= 2:
        speed_mult_delta = -60.0
    elif crippled_legs == 1:
        speed_mult_delta = -40.0
    else:
        speed_mult_delta = 0.0

    if crippled_arms >= 2:
        aim_sway = 65.0
    elif crippled_arms == 1:
        aim_sway = 35.0
    else:
        aim_sway = 0.0

    if head_c:
        aim_sway += 20.0

    perception_delta = -4.0 if head_c else 0.0
    drop_weapon = right_arm_c and not prev_right_arm_crippled

    mask = (
        (1 if head_c else 0)
        | (2 if torso_c else 0)
        | (4 if left_arm_c else 0)
        | (8 if right_arm_c else 0)
        | (16 if left_leg_c else 0)
        | (32 if right_leg_c else 0)
        | (64 if core_c else 0)
    )
    return {
        "slow_walk": crippled_legs > 0,
        "speed_mult_delta": speed_mult_delta,
        "aim_sway_penalty": aim_sway,
        "perception_delta": perception_delta,
        "drop_weapon": drop_weapon,
        "frenzy_or_stagger": core_c or torso_c,
        "crippled_legs": crippled_legs,
        "crippled_arms": crippled_arms,
        "cripple_mask": mask,
    }


def resolve_limb_cure(
    limb_hp: Mapping[str, float],
    item_kind: str,
    hardcore_enabled: bool,
) -> Tuple[bool, Dict[str, float], str]:
    """Apply Stimpak vs Doctor's Bag limb-cure rule.

    - Normal mode (hardcore_enabled == False): both 'stimpak' and 'doctors_bag' restore all limbs to 100.
    - Hardcore mode (hardcore_enabled == True): 'stimpak' refuses limb cure (HP HoT only); 'doctors_bag' cures limbs.
    """
    kind = item_kind.strip().lower()
    if kind not in ("stimpak", "doctors_bag"):
        raise ValueError(f"unsupported cure item_kind: {item_kind}")
    if hardcore_enabled and kind == "stimpak":
        return False, dict(limb_hp), "refused_hardcore_requires_doctors_bag"
    healed = {k: 100.0 for k in limb_hp}
    for z in ("head", "torso", "left_arm", "right_arm", "left_leg", "right_leg"):
        healed.setdefault(z, 100.0)
    return True, healed, "cured_all_limbs"


def compute_vats_ap_cost(weapon_class: str, zone: str) -> int:
    base_by_class = {
        "unarmed": 18,
        "melee": 20,
        "pistol": 20,
        "energy": 25,
        "rifle": 28,
        "shotgun": 30,
        "heavy": 38,
    }
    zone_surcharge = {
        "torso": 0,
        "left_arm": 2,
        "right_arm": 2,
        "left_leg": 2,
        "right_leg": 2,
        "head": 4,
        "special_core": 4,
        "special_optic": 5,
    }
    if weapon_class not in base_by_class:
        raise ValueError(f"unknown weapon_class: {weapon_class}")
    if zone not in zone_surcharge:
        raise ValueError(f"unknown zone: {zone}")
    return base_by_class[weapon_class] + zone_surcharge[zone]


def compute_vats_hit_chance(
    distance_m: float,
    weapon_skill: float,
    perception: float,
    zone: str,
    crippled_arms: int = 0,
) -> int:
    """Compute clamped [5, 95]% VATS hit chance from distance, weapon skill (0..100), PER (1..10), and zone."""
    if zone not in ZONE_VATS_HIT_FACTOR:
        raise ValueError(f"unknown zone: {zone}")
    dist = max(0.0, float(distance_m))
    skill = max(0.0, min(100.0, float(weapon_skill)))
    per = max(1.0, min(15.0, float(perception)))
    raw = (38.0 + 0.55 * skill + 3.0 * per - 1.60 * dist) * ZONE_VATS_HIT_FACTOR[zone] - (20.0 * max(0, int(crippled_arms)))
    return int(round(min(95.0, max(5.0, raw))))


def resolve_vats_shot(
    ap_pool: float,
    weapon_class: str,
    zone: str,
    distance_m: float,
    weapon_skill: float,
    perception: float,
    roll_1_to_100: int,
    base_damage: float,
    archetype: str = "human",
    target_dt: float = 0.0,
    target_dr_pct: float = 0.0,
    subtype: Optional[AmmoSubtypeSpec] = None,
    crippled_arms: int = 0,
) -> Dict[str, object]:
    """Validate AP cost, roll against VATS hit chance, and apply zone + ammo subtype damage if hit."""
    ap_cost = compute_vats_ap_cost(weapon_class, zone)
    if ap_pool < ap_cost:
        return {
            "queued": False,
            "reason": "insufficient_ap",
            "ap_before": ap_pool,
            "ap_after": ap_pool,
            "ap_cost": ap_cost,
            "hit_chance": 0,
            "hit": False,
            "applied_damage": 0.0,
        }
    chance = compute_vats_hit_chance(distance_m, weapon_skill, perception, zone, crippled_arms=crippled_arms)
    is_hit = int(roll_1_to_100) <= chance
    ap_after = round(ap_pool - ap_cost, 2)
    if not is_hit:
        return {
            "queued": True,
            "reason": "missed",
            "ap_before": ap_pool,
            "ap_after": ap_after,
            "ap_cost": ap_cost,
            "hit_chance": chance,
            "hit": False,
            "applied_damage": 0.0,
        }
    hit_res = compute_zone_hit(
        base_damage=base_damage,
        zone=zone,
        archetype=archetype,
        target_dt=target_dt,
        target_dr_pct=target_dr_pct,
        subtype=subtype,
    )
    return {
        "queued": True,
        "reason": "hit",
        "ap_before": ap_pool,
        "ap_after": ap_after,
        "ap_cost": ap_cost,
        "hit_chance": chance,
        "hit": True,
        "applied_damage": hit_res["applied_damage"],
        "zone_mult": hit_res["zone_mult"],
        "effective_dt": hit_res["effective_dt"],
    }


ZONE_LINE_RE = re.compile(
    r"\[FO4SF_Combat\]\s+PASS\s+step=zone_hit\s+zone=(?P<zone>[a-z_]+)\s+mult=(?P<mult>[0-9.]+)\s+applied=(?P<applied>[0-9.]+)"
)
AMMO_CYCLE_RE = re.compile(
    r"\[FO4SF_Combat\]\s+PASS\s+step=ammo_cycle\s+calibre=(?P<calibre>\S+)\s+slot=(?P<slot>\d+)\s+subtype=(?P<subtype>\S+)"
)
AMMO_DT_RE = re.compile(
    r"\[FO4SF_Combat\]\s+PASS\s+step=high_dt_hit\s+subtype=(?P<subtype>\S+)\s+target_dt=(?P<dt>[0-9.]+)\s+eff_dt=(?P<eff_dt>[0-9.]+)\s+damage=(?P<dmg>[0-9.]+)"
)
CRIPPLE_RE = re.compile(
    r"\[FO4SF_Combat\]\s+PASS\s+step=limb_crippled\s+zone=(?P<zone>[a-z_]+)\s+speed_delta=(?P<speed>[-0-9.]+)\s+sway=(?P<sway>[0-9.]+)"
)
CURE_RE = re.compile(
    r"\[FO4SF_Combat\]\s+PASS\s+step=limb_cure\s+item=(?P<item>[a-z_]+)\s+hardcore=(?P<hc>[01])\s+cured=(?P<cured>[01])"
)
VATS_RE = re.compile(
    r"\[FO4SF_Combat\]\s+PASS\s+step=vats_shot\s+slow_time=1\s+zone=(?P<zone>[a-z_]+)\s+ap_cost=(?P<ap>\d+)\s+chance=(?P<chance>\d+)\s+queued=1"
)


@dataclass
class CombatLogReport:
    zones_hit: Dict[str, float] = field(default_factory=dict)
    ammo_cycles: List[Tuple[str, int, str]] = field(default_factory=list)
    high_dt_hits: Dict[str, float] = field(default_factory=dict)
    crippled_zones: List[str] = field(default_factory=list)
    cures: List[Tuple[str, int, int]] = field(default_factory=list)
    vats_shots: List[Tuple[str, int, int]] = field(default_factory=list)

    @property
    def zones_pass(self) -> bool:
        required = {"head", "torso", "left_arm", "right_arm", "left_leg", "right_leg"}
        return required.issubset(self.zones_hit.keys())

    @property
    def ammo_dt_pass(self) -> bool:
        if "ap" not in self.high_dt_hits or "standard" not in self.high_dt_hits:
            return False
        return self.high_dt_hits["ap"] > self.high_dt_hits["standard"]

    @property
    def cripple_cure_pass(self) -> bool:
        leg_crippled = any(z in ("left_leg", "right_leg") for z in self.crippled_zones)
        leg_cured = any(cured == 1 for _, _, cured in self.cures)
        return leg_crippled and leg_cured

    @property
    def vats_pass(self) -> bool:
        return len(self.vats_shots) >= 1

    @property
    def all_pass(self) -> bool:
        return self.zones_pass and self.ammo_dt_pass and self.cripple_cure_pass and self.vats_pass


def parse_combat_log(text: str) -> CombatLogReport:
    report = CombatLogReport()
    for line in text.splitlines():
        m = ZONE_LINE_RE.search(line)
        if m:
            report.zones_hit[m.group("zone")] = float(m.group("applied"))
            continue
        m = AMMO_CYCLE_RE.search(line)
        if m:
            report.ammo_cycles.append((m.group("calibre"), int(m.group("slot")), m.group("subtype")))
            continue
        m = AMMO_DT_RE.search(line)
        if m:
            report.high_dt_hits[m.group("subtype").lower()] = float(m.group("dmg"))
            continue
        m = CRIPPLE_RE.search(line)
        if m:
            report.crippled_zones.append(m.group("zone"))
            continue
        m = CURE_RE.search(line)
        if m:
            report.cures.append((m.group("item"), int(m.group("hc")), int(m.group("cured"))))
            continue
        m = VATS_RE.search(line)
        if m:
            report.vats_shots.append((m.group("zone"), int(m.group("ap")), int(m.group("chance"))))
            continue
    return report
