"""Canonical progression data tables and deterministic character/reputation math (CF-6, Phase B item 2e).

Implements every owner decision from PR #806 (`#issuecomment-6930665309`):
1. 40-point S.P.E.C.I.A.L. creation pool (`5` base each + `5` pool = `40` total, range `1..10`), with the `28`-point
   FO4 preset exposed only as an off-by-default `GLOB` (`FO4SF_SpecialPool28 = 0`).
2. 13 New Vegas skills (`1..100`): `initial = 2 + 2 * GovSPECIAL + ceil(LCK / 2)`, `+15` for 3 Tag Skills, `+10` for
   Background's 3 signature skills, and `10 + floor(INT / 2)` skill points per level (`+2` with `Educated`).
3. Backgrounds (choose `1`, Wasteland origins — never trades/professions) and Traits (`0..2` at creation, each pairing
   an upside with a trade-off, plus `1` free respec at the Vault / opening exit).
4. Perk cadence driven purely by a `GLOB` (`FO4SF_PerkCadenceLevels = 2` default = `1` Perk per `2` levels; tunable at
   runtime to `1`, `2`, `3`, etc. with zero fixed-cadence assumptions).
5. Independent `Karma` (`[-1000..+1000]`) AND per-faction `REPU` (`Fame` / `Infamy` 16-state New Vegas matrix): faction
   disposition and vendor pricing depend ONLY on `REPU`, never on `Karma`.
"""
from __future__ import annotations

import math
from typing import Iterable

from fo4sf.core.core_values import CORE_VALUES_PLUGIN, core_form_id

PLUGIN_NAME = "FO4SFProgression.esm"
PLUGIN_MASTERS: tuple[str, str] = ("Starfield.esm", CORE_VALUES_PLUGIN)

SPECIAL_POOL_DEFAULT = 40
SPECIAL_POOL_FO4_OPT = 28
SPECIAL_MIN = 1
SPECIAL_MAX = 10
TAG_SKILL_COUNT = 3
TAG_SKILL_BONUS = 15
BACKGROUND_SKILL_BONUS = 10
MAX_TRAITS = 2
DEFAULT_PERK_CADENCE = 2

SHARED_CORE_FORM_IDS: dict[str, int] = {
    "SpecialAVList": core_form_id("FO4SF_SpecialAVList"),
    "SkillAVList": core_form_id("FO4SF_SkillAVList"),
    "KarmaAV": core_form_id("FO4SF_Karma"),
    "KarmaGlobal": core_form_id("FO4SF_KarmaValue"),
    "TestModeGlobal": core_form_id("FO4SF_TestModeEnabled"),
}

# 1. Seven S.P.E.C.I.A.L. Attributes (owned by FO4SFCoreValues.esm, 0x810..0x816)
SPECIAL_TABLE: tuple[dict, ...] = (
    {"plugin": CORE_VALUES_PLUGIN, "id": core_form_id("FO4SF_Special_Strength"), "edid": "FO4SF_Special_Strength", "key": "STR", "name": "Strength", "abbr": "STR"},
    {"plugin": CORE_VALUES_PLUGIN, "id": core_form_id("FO4SF_Special_Perception"), "edid": "FO4SF_Special_Perception", "key": "PER", "name": "Perception", "abbr": "PER"},
    {"plugin": CORE_VALUES_PLUGIN, "id": core_form_id("FO4SF_Special_Endurance"), "edid": "FO4SF_Special_Endurance", "key": "END", "name": "Endurance", "abbr": "END"},
    {"plugin": CORE_VALUES_PLUGIN, "id": core_form_id("FO4SF_Special_Charisma"), "edid": "FO4SF_Special_Charisma", "key": "CHA", "name": "Charisma", "abbr": "CHA"},
    {"plugin": CORE_VALUES_PLUGIN, "id": core_form_id("FO4SF_Special_Intelligence"), "edid": "FO4SF_Special_Intelligence", "key": "INT", "name": "Intelligence", "abbr": "INT"},
    {"plugin": CORE_VALUES_PLUGIN, "id": core_form_id("FO4SF_Special_Agility"), "edid": "FO4SF_Special_Agility", "key": "AGI", "name": "Agility", "abbr": "AGI"},
    {"plugin": CORE_VALUES_PLUGIN, "id": core_form_id("FO4SF_Special_Luck"), "edid": "FO4SF_Special_Luck", "key": "LCK", "name": "Luck", "abbr": "LCK"},
)

# 2. Thirteen New Vegas Skills (owned by FO4SFCoreValues.esm, 0x820..0x82C)
SKILLS_TABLE: tuple[dict, ...] = (
    {"plugin": CORE_VALUES_PLUGIN, "id": core_form_id("FO4SF_Skill_Barter"), "edid": "FO4SF_Skill_Barter", "name": "Barter", "abbr": "Bar", "gov": "CHA"},
    {"plugin": CORE_VALUES_PLUGIN, "id": core_form_id("FO4SF_Skill_EnergyWeapons"), "edid": "FO4SF_Skill_EnergyWeapons", "name": "Energy Weapons", "abbr": "EWp", "gov": "PER"},
    {"plugin": CORE_VALUES_PLUGIN, "id": core_form_id("FO4SF_Skill_Explosives"), "edid": "FO4SF_Skill_Explosives", "name": "Explosives", "abbr": "Exp", "gov": "PER"},
    {"plugin": CORE_VALUES_PLUGIN, "id": core_form_id("FO4SF_Skill_Guns"), "edid": "FO4SF_Skill_Guns", "name": "Guns", "abbr": "Gun", "gov": "AGI"},
    {"plugin": CORE_VALUES_PLUGIN, "id": core_form_id("FO4SF_Skill_Lockpick"), "edid": "FO4SF_Skill_Lockpick", "name": "Lockpick", "abbr": "Lck", "gov": "PER"},
    {"plugin": CORE_VALUES_PLUGIN, "id": core_form_id("FO4SF_Skill_Medicine"), "edid": "FO4SF_Skill_Medicine", "name": "Medicine", "abbr": "Med", "gov": "INT"},
    {"plugin": CORE_VALUES_PLUGIN, "id": core_form_id("FO4SF_Skill_MeleeWeapons"), "edid": "FO4SF_Skill_MeleeWeapons", "name": "Melee Weapons", "abbr": "Mel", "gov": "STR"},
    {"plugin": CORE_VALUES_PLUGIN, "id": core_form_id("FO4SF_Skill_Repair"), "edid": "FO4SF_Skill_Repair", "name": "Repair", "abbr": "Rep", "gov": "INT"},
    {"plugin": CORE_VALUES_PLUGIN, "id": core_form_id("FO4SF_Skill_Science"), "edid": "FO4SF_Skill_Science", "name": "Science", "abbr": "Sci", "gov": "INT"},
    {"plugin": CORE_VALUES_PLUGIN, "id": core_form_id("FO4SF_Skill_Sneak"), "edid": "FO4SF_Skill_Sneak", "name": "Sneak", "abbr": "Snk", "gov": "AGI"},
    {"plugin": CORE_VALUES_PLUGIN, "id": core_form_id("FO4SF_Skill_Speech"), "edid": "FO4SF_Skill_Speech", "name": "Speech", "abbr": "Spc", "gov": "CHA"},
    {"plugin": CORE_VALUES_PLUGIN, "id": core_form_id("FO4SF_Skill_Survival"), "edid": "FO4SF_Skill_Survival", "name": "Survival", "abbr": "Srv", "gov": "END"},
    {"plugin": CORE_VALUES_PLUGIN, "id": core_form_id("FO4SF_Skill_Unarmed"), "edid": "FO4SF_Skill_Unarmed", "name": "Unarmed", "abbr": "Unm", "gov": "END"},
)

# 3. Nine Wasteland Backgrounds (owned by FO4SFProgression.esm, 0x820..0x828) — choose 1 at creation
BACKGROUNDS_TABLE: tuple[dict, ...] = (
    {"plugin": PLUGIN_NAME, "id": 0x820, "edid": "FO4SF_BG_VaultDweller", "name": "Vault Dweller", "skills": ("Science", "Medicine", "Speech")},
    {"plugin": PLUGIN_NAME, "id": 0x821, "edid": "FO4SF_BG_WastelandScavenger", "name": "Wasteland Scavenger", "skills": ("Repair", "Lockpick", "Survival")},
    {"plugin": PLUGIN_NAME, "id": 0x822, "edid": "FO4SF_BG_CaravanGuard", "name": "Caravan Guard", "skills": ("Guns", "Barter", "Survival")},
    {"plugin": PLUGIN_NAME, "id": 0x823, "edid": "FO4SF_BG_FieldMedic", "name": "Field Medic", "skills": ("Medicine", "Science", "Survival")},
    {"plugin": PLUGIN_NAME, "id": 0x824, "edid": "FO4SF_BG_BrotherhoodScribe", "name": "Brotherhood Scribe", "skills": ("Energy Weapons", "Science", "Repair")},
    {"plugin": PLUGIN_NAME, "id": 0x825, "edid": "FO4SF_BG_EnclaveRemnant", "name": "Enclave Remnant", "skills": ("Energy Weapons", "Speech", "Science")},
    {"plugin": PLUGIN_NAME, "id": 0x826, "edid": "FO4SF_BG_TribalHunter", "name": "Tribal Hunter", "skills": ("Melee Weapons", "Sneak", "Survival")},
    {"plugin": PLUGIN_NAME, "id": 0x827, "edid": "FO4SF_BG_DesertRanger", "name": "Desert Ranger", "skills": ("Guns", "Sneak", "Survival")},
    {"plugin": PLUGIN_NAME, "id": 0x828, "edid": "FO4SF_BG_MinutemanVolunteer", "name": "Minuteman Volunteer", "skills": ("Guns", "Repair", "Speech")},
)

# 4. Nine Trade-Off Traits (owned by FO4SFProgression.esm, 0x830..0x838) — choose 0..2 at creation, 1 free exit respec
TRAITS_TABLE: tuple[dict, ...] = (
    {"plugin": PLUGIN_NAME, "id": 0x830, "edid": "FO4SF_Trait_SmallFrame", "name": "Small Frame", "upside": "AGI +1", "downside": "CarryWeight -15"},
    {"plugin": PLUGIN_NAME, "id": 0x831, "edid": "FO4SF_Trait_TriggerDiscipline", "name": "Trigger Discipline", "upside": "Guns/EWp +10", "downside": "ReloadSpeed -0.15"},
    {"plugin": PLUGIN_NAME, "id": 0x832, "edid": "FO4SF_Trait_FastShot", "name": "Fast Shot", "upside": "ReloadSpeed +0.20", "downside": "Guns/EWp -5"},
    {"plugin": PLUGIN_NAME, "id": 0x833, "edid": "FO4SF_Trait_Kamikaze", "name": "Kamikaze", "upside": "ActionPoints +15", "downside": "DamageResist -15"},
    {"plugin": PLUGIN_NAME, "id": 0x834, "edid": "FO4SF_Trait_HeavyHanded", "name": "Heavy Handed", "upside": "Melee/Unarmed +10", "downside": "LCK -1"},
    {"plugin": PLUGIN_NAME, "id": 0x835, "edid": "FO4SF_Trait_FourEyes", "name": "Four Eyes", "upside": "PER +2 with eyewear", "downside": "Base PER -1"},
    {"plugin": PLUGIN_NAME, "id": 0x836, "edid": "FO4SF_Trait_GoodNatured", "name": "Good Natured", "upside": "Speech/Med/Repair/Sci/Barter +5", "downside": "Combat skills -5"},
    {"plugin": PLUGIN_NAME, "id": 0x837, "edid": "FO4SF_Trait_Skilled", "name": "Skilled", "upside": "All 13 skills +5", "downside": "XP gain -10%"},
    {"plugin": PLUGIN_NAME, "id": 0x838, "edid": "FO4SF_Trait_WildWasteland", "name": "Wild Wasteland", "upside": "Unlocks uncanny encounters", "downside": "Alters rare world events"},
)

# 5. Eight Core Playable Perks (owned by FO4SFProgression.esm, 0x840..0x847) — unlocked on GLOB-driven cadence
PERKS_TABLE: tuple[dict, ...] = (
    {"plugin": PLUGIN_NAME, "id": 0x840, "edid": "FO4SF_Perk_Educated", "name": "Educated", "min_level": 4, "req_special": {"INT": 4}, "req_skills": {}},
    {"plugin": PLUGIN_NAME, "id": 0x841, "edid": "FO4SF_Perk_Comprehension", "name": "Comprehension", "min_level": 4, "req_special": {"INT": 4}, "req_skills": {}},
    {"plugin": PLUGIN_NAME, "id": 0x842, "edid": "FO4SF_Perk_StrongBack", "name": "Strong Back", "min_level": 8, "req_special": {"STR": 5, "END": 5}, "req_skills": {}},
    {"plugin": PLUGIN_NAME, "id": 0x843, "edid": "FO4SF_Perk_Toughness", "name": "Toughness", "min_level": 6, "req_special": {"END": 5}, "req_skills": {}},
    {"plugin": PLUGIN_NAME, "id": 0x844, "edid": "FO4SF_Perk_Finesse", "name": "Finesse", "min_level": 10, "req_special": {"LCK": 5}, "req_skills": {}},
    {"plugin": PLUGIN_NAME, "id": 0x845, "edid": "FO4SF_Perk_Commando", "name": "Commando", "min_level": 8, "req_special": {"AGI": 6}, "req_skills": {"Guns": 45}},
    {"plugin": PLUGIN_NAME, "id": 0x846, "edid": "FO4SF_Perk_JuryRigging", "name": "Jury Rigging", "min_level": 14, "req_special": {}, "req_skills": {"Repair": 90}},
    {"plugin": PLUGIN_NAME, "id": 0x847, "edid": "FO4SF_Perk_ActionPerson", "name": "Action Boy", "min_level": 12, "req_special": {"AGI": 6}, "req_skills": {}},
)


class ProgressionError(ValueError):
    pass


def validate_special_allocation(alloc: dict[str, int], *, use_fo4_pool_28: bool = False) -> dict[str, int]:
    expected_keys = {r["key"] for r in SPECIAL_TABLE}
    if set(alloc.keys()) != expected_keys:
        raise ProgressionError(f"SPECIAL allocation must specify exact keys {sorted(expected_keys)}")
    for k, v in alloc.items():
        if not isinstance(v, int) or v < SPECIAL_MIN or v > SPECIAL_MAX:
            raise ProgressionError(f"SPECIAL {k}={v} out of range {SPECIAL_MIN}..{SPECIAL_MAX}")
    pool = SPECIAL_POOL_FO4_OPT if use_fo4_pool_28 else SPECIAL_POOL_DEFAULT
    total = sum(alloc.values())
    if total != pool:
        raise ProgressionError(f"SPECIAL sum {total} != required pool {pool}")
    return dict(alloc)


def compute_initial_skills(
    special: dict[str, int],
    *,
    background_name: str,
    tag_skills: list[str] | tuple[str, ...],
    traits: list[str] | tuple[str, ...] = (),
) -> dict[str, int]:
    if len(set(tag_skills)) != TAG_SKILL_COUNT or len(tag_skills) != TAG_SKILL_COUNT:
        raise ProgressionError(f"must choose exactly {TAG_SKILL_COUNT} distinct Tag Skills")
    known_skills = {s["name"] for s in SKILLS_TABLE}
    for ts in tag_skills:
        if ts not in known_skills:
            raise ProgressionError(f"unknown Tag Skill {ts!r}")

    bg = next((b for b in BACKGROUNDS_TABLE if b["name"] == background_name), None)
    if bg is None:
        raise ProgressionError(f"unknown Background {background_name!r}")

    if len(traits) > MAX_TRAITS or len(set(traits)) != len(traits):
        raise ProgressionError(f"traits must be 0..{MAX_TRAITS} distinct traits")
    known_traits = {t["name"] for t in TRAITS_TABLE}
    for tr in traits:
        if tr not in known_traits:
            raise ProgressionError(f"unknown Trait {tr!r}")

    eff_special = dict(special)
    if "Small Frame" in traits:
        eff_special["AGI"] = min(SPECIAL_MAX, eff_special["AGI"] + 1)
    if "Heavy Handed" in traits:
        eff_special["LCK"] = max(SPECIAL_MIN, eff_special["LCK"] - 1)
    if "Four Eyes" in traits:
        eff_special["PER"] = max(SPECIAL_MIN, eff_special["PER"] - 1)

    luck_bonus = math.ceil(eff_special["LCK"] / 2.0)
    out: dict[str, int] = {}
    for s in SKILLS_TABLE:
        sname = s["name"]
        val = 2 + 2 * eff_special[s["gov"]] + luck_bonus
        if sname in bg["skills"]:
            val += BACKGROUND_SKILL_BONUS
        if sname in tag_skills:
            val += TAG_SKILL_BONUS
        if "Skilled" in traits:
            val += 5
        if "Good Natured" in traits:
            if sname in ("Speech", "Medicine", "Repair", "Science", "Barter"):
                val += 5
            elif sname in ("Energy Weapons", "Explosives", "Guns", "Melee Weapons", "Unarmed"):
                val -= 5
        out[sname] = max(1, min(100, val))
    return out


def apply_exit_trait_respec(
    current_traits: list[str] | tuple[str],
    new_traits: list[str] | tuple[str],
    *,
    respec_used: bool,
) -> tuple[list[str], bool]:
    """Enforce the owner rule: 0..2 traits with exactly ONE free respec at the Vault/opening exit."""
    if respec_used:
        raise ProgressionError("Vault exit trait respec has already been used (limit 1)")
    if len(new_traits) > MAX_TRAITS or len(set(new_traits)) != len(new_traits):
        raise ProgressionError(f"respec must select 0..{MAX_TRAITS} distinct traits")
    known_traits = {t["name"] for t in TRAITS_TABLE}
    for tr in new_traits:
        if tr not in known_traits:
            raise ProgressionError(f"unknown Trait {tr!r}")
    return list(new_traits), True


def compute_derived_stats(special: dict[str, int], level: int = 1, traits: Iterable[str] | tuple[str, ...] = ()) -> dict[str, float]:
    trait_set = set(traits)
    eff_agi = min(SPECIAL_MAX, special["AGI"] + (1 if "Small Frame" in trait_set else 0))
    carry = 150.0 + 10.0 * special["STR"] - (15.0 if "Small Frame" in trait_set else 0.0)
    max_hp = 90.0 + 20.0 * special["END"] + 5.0 * max(0, level - 1)
    ap = 65.0 + 3.0 * eff_agi + (15.0 if "Kamikaze" in trait_set else 0.0)
    companion_nerve_pct = 5.0 * special["CHA"]
    return {
        "CarryWeight": carry,
        "MaxHP": max_hp,
        "ActionPoints": ap,
        "CompanionNervePct": companion_nerve_pct,
    }


def skill_points_for_level(intel: int, *, has_educated: bool = False) -> int:
    return 10 + (intel // 2) + (2 if has_educated else 0)


def grants_perk_at_level(level: int, cadence_glob: int = DEFAULT_PERK_CADENCE) -> bool:
    """GLOB-driven Perk cadence (`FO4SF_PerkCadenceLevels`, default 2): never assumes fixed cadence."""
    if cadence_glob < 1:
        raise ProgressionError(f"cadence_glob must be >= 1, got {cadence_glob}")
    if level < 2:
        return False
    if cadence_glob == 1:
        return True
    return (level % cadence_glob) == 0


def karma_tier(karma: float) -> str:
    clamped = max(-1000.0, min(1000.0, float(karma)))
    if clamped <= -750.0:
        return "Very Evil"
    if clamped <= -250.0:
        return "Evil"
    if clamped < 250.0:
        return "Neutral"
    if clamped < 750.0:
        return "Good"
    return "Very Good"
