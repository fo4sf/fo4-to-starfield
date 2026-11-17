"""Multi-title Karma and 16-state Faction Reputation data tables and pure evaluation logic.

Implements:
  - Separate Global Karma (-1000..+1000) and per-faction Fame x Infamy (0..100 each) axes so moral alignment and
    group standing remain strictly orthogonal ("a bad person can still be liked by certain groups").
  - New Vegas's exact 4x4 = 16-state Fame x Infamy matrix driving FACT disposition (Ally / Friend / Neutral / Enemy),
    vendor buy/sell multipliers and trade-refusal gates, and CTDA dialogue state codes (0..15).
  - Global Karma's 5 tiers (Very Evil .. Very Good) driving [Perk] dialogue tags, moral companion warnings/desertion,
    and ending moral slide indices (0..4).
  - Per-title faction & reputation tables across FO1, FO2, Tactics, FO3, FNV, FO4, and FO76.
"""
from dataclasses import dataclass
from typing import Dict, List, Tuple

PLUGIN_NAME = "FO4SFReputation.esm"
KARMA_MIN = -1000.0
KARMA_MAX = 1000.0
REP_AXIS_MIN = 0.0
REP_AXIS_MAX = 100.0

# Default Fame / Infamy tier cutoffs on a 0..100 axis:
#   0 = None (< 15), 1 = Low (15..39.999), 2 = Medium (40..74.999), 3 = High (>= 75)
DEFAULT_TIER_THRESHOLDS: Tuple[float, float, float] = (15.0, 40.0, 75.0)
TIER_NAMES: Tuple[str, str, str, str] = ("None", "Low", "Medium", "High")

# Deterministic local FormIDs in FO4SFReputation.esm (held equal with dotnet/ReputationCore/Program.cs and PSC)
RECORD_IDS: Dict[str, int] = {
    "QuestId": 0x800,
    "RepKarmaAvId": 0x801,
    "KarmaValueGlobId": 0x802,
    "KarmaTierGlobId": 0x803,
    "EndingMoralSlideGlobId": 0x804,
    "VendorBuyMultAvId": 0x805,
    "RepVendorPerkId": 0x806,
    "CompanionMoralGlobId": 0x807,
    "KarmaPerkVeryEvilId": 0x808,
    "KarmaPerkEvilId": 0x809,
    "KarmaPerkNeutralId": 0x80A,
    "KarmaPerkGoodId": 0x80B,
    "KarmaPerkVeryGoodId": 0x80C,
    "FactFirstId": 0x810,
    "FactListId": 0x81F,
    "FameAvFirstId": 0x820,
    "FameAvListId": 0x82F,
    "InfamyAvFirstId": 0x830,
    "InfamyAvListId": 0x83F,
    "StateAvFirstId": 0x840,
    "StateAvListId": 0x84F,
    "FameGlobFirstId": 0x850,
    "FameGlobListId": 0x85F,
    "InfamyGlobFirstId": 0x860,
    "InfamyGlobListId": 0x86F,
    "StateGlobFirstId": 0x870,
    "StateGlobListId": 0x87F,
    "CharityTokenId": 0x880,
    "TheftTokenId": 0x881,
    "FactionAidTokenId": 0x882,
    "FactionCrimeTokenId": 0x883,
    "VendorNpcId": 0x888,
    "RepTestCellId": 0x890,
}

# Eight core runtime faction slots in FO4SFReputation.esm (indices 0..7)
CORE_FACTIONS: Tuple[Dict[str, object], ...] = tuple(
    {
        "index": idx,
        "key": key,
        "pipboy_label": label,
        "fact_edid": f"FO4SF_RepFact_{key}",
        "fact_id": 0x810 + idx,
        "fame_av_edid": f"FO4SF_Fame_{key}",
        "fame_av_id": 0x820 + idx,
        "infamy_av_edid": f"FO4SF_Infamy_{key}",
        "infamy_av_id": 0x830 + idx,
        "state_av_edid": f"FO4SF_RepState_{key}",
        "state_av_id": 0x840 + idx,
        "fame_glob_edid": f"FO4SF_FameGlob_{key}",
        "fame_glob_id": 0x850 + idx,
        "infamy_glob_edid": f"FO4SF_InfamyGlob_{key}",
        "infamy_glob_id": 0x860 + idx,
        "state_glob_edid": f"FO4SF_StateGlob_{key}",
        "state_glob_id": 0x870 + idx,
    }
    for idx, (key, label) in enumerate(
        (
            ("Minutemen", "MINUTEMEN"),
            ("Brotherhood", "BROTHERHOOD"),
            ("Railroad", "RAILROAD"),
            ("Institute", "INSTITUTE"),
            ("Settlers", "SETTLERS"),
            ("NCR", "NCR"),
            ("Legion", "LEGION"),
            ("Outlaws", "OUTLAWS"),
        )
    )
)


@dataclass(frozen=True)
class ReputationStateSpec:
    code: int
    infamy_tier: int
    fame_tier: int
    title: str
    disposition: str       # "Ally" | "Friend" | "Neutral" | "Enemy"
    buy_mult: float
    sell_mult: float
    allow_trade: bool
    dialogue_tags: Tuple[str, ...]


# Exact 4x4 = 16-state New Vegas Fame x Infamy matrix (code = infamy_tier * 4 + fame_tier)
NV_16_STATE_MATRIX: Dict[Tuple[int, int], ReputationStateSpec] = {
    # Infamy = None (0)
    (0, 0): ReputationStateSpec(0, 0, 0, "Neutral", "Neutral", 1.00, 1.00, True, ("[Neutral]",)),
    (0, 1): ReputationStateSpec(1, 0, 1, "Accepted", "Friend", 0.95, 1.05, True, ("[Accepted+]",)),
    (0, 2): ReputationStateSpec(2, 0, 2, "Liked", "Friend", 0.85, 1.15, True, ("[Accepted+]", "[Liked+]")),
    (0, 3): ReputationStateSpec(3, 0, 3, "Idolized", "Ally", 0.75, 1.25, True, ("[Accepted+]", "[Liked+]", "[Idolized]")),
    # Infamy = Low (1)
    (1, 0): ReputationStateSpec(4, 1, 0, "Shunned", "Neutral", 1.25, 0.80, False, ("[Shunned]",)),
    (1, 1): ReputationStateSpec(5, 1, 1, "Mixed", "Neutral", 1.00, 1.00, True, ("[Mixed]",)),
    (1, 2): ReputationStateSpec(6, 1, 2, "Good-Natured Rascal", "Friend", 0.90, 1.10, True, ("[Accepted+]", "[Liked+]")),
    (1, 3): ReputationStateSpec(7, 1, 3, "Smiling Troublemaker", "Ally", 0.85, 1.15, True, ("[Accepted+]", "[Liked+]")),
    # Infamy = Medium (2)
    (2, 0): ReputationStateSpec(8, 2, 0, "Hated", "Enemy", 1.50, 0.50, False, ("[Hated]",)),
    (2, 1): ReputationStateSpec(9, 2, 1, "Sneering Punk", "Neutral", 1.25, 0.80, False, ("[Shunned]",)),
    (2, 2): ReputationStateSpec(10, 2, 2, "Unpredictable", "Neutral", 1.05, 0.95, True, ("[Mixed]",)),
    (2, 3): ReputationStateSpec(11, 2, 3, "Dark Hero", "Friend", 0.95, 1.05, True, ("[Accepted+]", "[Liked+]")),
    # Infamy = High (3)
    (3, 0): ReputationStateSpec(12, 3, 0, "Vilified", "Enemy", 1.50, 0.00, False, ("[Hated]", "[Vilified]")),
    (3, 1): ReputationStateSpec(13, 3, 1, "Merciful Thug", "Enemy", 1.40, 0.00, False, ("[Hated]",)),
    (3, 2): ReputationStateSpec(14, 3, 2, "Soft-Hearted Devil", "Neutral", 1.15, 0.85, True, ("[Mixed]",)),
    (3, 3): ReputationStateSpec(15, 3, 3, "Wild Child", "Neutral", 1.00, 1.00, True, ("[Mixed]",)),
}

STATE_BY_CODE: Dict[int, ReputationStateSpec] = {spec.code: spec for spec in NV_16_STATE_MATRIX.values()}


@dataclass(frozen=True)
class KarmaTierSpec:
    tier: int
    min_karma: float
    max_karma: float
    title: str
    dialogue_tag: str
    perk_edid: str
    perk_id: int
    ending_slide: int


KARMA_TIERS: Tuple[KarmaTierSpec, ...] = (
    KarmaTierSpec(-2, -1000.0, -750.0, "Very Evil", "[Karma: Very Evil]", "FO4SF_KarmaTag_VeryEvil", 0x808, 0),
    KarmaTierSpec(-1, -749.999, -250.0, "Evil", "[Karma: Evil]", "FO4SF_KarmaTag_Evil", 0x809, 1),
    KarmaTierSpec(0, -249.999, 249.999, "Neutral", "[Karma: Neutral]", "FO4SF_KarmaTag_Neutral", 0x80A, 2),
    KarmaTierSpec(1, 250.0, 749.999, "Good", "[Karma: Good]", "FO4SF_KarmaTag_Good", 0x80B, 3),
    KarmaTierSpec(2, 750.0, 1000.0, "Very Good", "[Karma: Very Good]", "FO4SF_KarmaTag_VeryGood", 0x80C, 4),
)

# FO76's 7-tier single-axis reputation curve projected onto the 16-state Fame/Infamy surface
FO76_TIER_TO_FAME_INFAMY: Dict[str, Tuple[float, float]] = {
    "Hostile": (0.0, 85.0),       # -> Vilified (Enemy)
    "Caution": (0.0, 50.0),       # -> Hated (Enemy)
    "Neutral": (0.0, 0.0),        # -> Neutral
    "Cooperative": (20.0, 0.0),   # -> Accepted
    "Friendly": (45.0, 0.0),      # -> Liked
    "Neighborly": (65.0, 0.0),    # -> Liked (high)
    "Ally": (85.0, 0.0),          # -> Idolized (Ally)
}

# Multi-title faction & reputation definitions across all 7 Fallout titles
TITLE_REPUTATION_TABLES: Dict[str, Dict[str, object]] = {
    "FO4": {
        "title": "FO4",
        "native_fact_count": 699,
        "native_repu_count": 0,
        "karma_enabled": True,
        "karma_note": "Restored global Karma (-1000..+1000) on theft, innocent murder, and charity alongside 16-state faction REPU.",
        "factions": (
            {"id": "Minutemen", "core_slot": 0, "rival": "Raiders_Commonwealth"},
            {"id": "Brotherhood_Commonwealth", "core_slot": 1, "rival": "Institute"},
            {"id": "Railroad", "core_slot": 2, "rival": "Institute"},
            {"id": "Institute", "core_slot": 3, "rival": "Brotherhood_Commonwealth"},
            {"id": "DiamondCity", "core_slot": 4, "rival": "Raiders_Commonwealth"},
            {"id": "Goodneighbor", "core_slot": 4, "rival": "Gunners"},
            {"id": "Raiders_Commonwealth", "core_slot": 7, "rival": "Minutemen"},
            {"id": "Gunners", "core_slot": 7, "rival": "Minutemen"},
        ),
    },
    "FNV": {
        "title": "FNV",
        "native_fact_count": 682,
        "native_repu_count": 13,
        "native_karma_gmst_count": 10,
        "karma_enabled": True,
        "karma_note": "1:1 New Vegas 16-state REPU matrix across all 13 FalloutNV.esm REPU records plus independent global Karma.",
        "factions": (
            {"id": "RepNVGoodsprings", "source_formid": 0x104C22, "core_slot": 4, "rival": "RepNVPowderGanger"},
            {"id": "RepNVPrimm", "source_formid": 0x0F2406, "core_slot": 4, "rival": "RepNVPowderGanger"},
            {"id": "RepNVNovac", "source_formid": 0x129A79, "core_slot": 4, "rival": "RepNVCaesarsLegion"},
            {"id": "RepNVFreeside", "source_formid": 0x129A7A, "core_slot": 4, "rival": None},
            {"id": "RepNVTheStrip", "source_formid": 0x118F61, "core_slot": 4, "rival": None},
            {"id": "RepNVNCR", "source_formid": 0x0F43DE, "core_slot": 5, "rival": "RepNVCaesarsLegion"},
            {"id": "RepNVCaesarsLegion", "source_formid": 0x0F43DD, "core_slot": 6, "rival": "RepNVNCR"},
            {"id": "RepNVBrotherhood", "source_formid": 0x11E662, "core_slot": 1, "rival": "RepNVNCR"},
            {"id": "RepNVBoomer", "source_formid": 0x0FFAE8, "core_slot": 4, "rival": None},
            {"id": "RepNVGreatKhans", "source_formid": 0x11989B, "core_slot": 7, "rival": "RepNVNCR"},
            {"id": "RepNVPowderGanger", "source_formid": 0x1558E6, "core_slot": 7, "rival": "RepNVGoodsprings"},
            {"id": "RepNVWhiteGloveSociety", "source_formid": 0x116F16, "core_slot": 4, "rival": None},
            {"id": "RepNVFollowers", "source_formid": 0x124AD1, "core_slot": 2, "rival": None},
        ),
    },
    "FO3": {
        "title": "FO3",
        "native_fact_count": 326,
        "native_repu_count": 0,
        "native_karma_gmst_count": 10,
        "karma_enabled": True,
        "karma_note": "Fallout 3 global Karma (-1000..+1000, 10 GMSTs) paired with Capital Wasteland settlement/faction standing.",
        "factions": (
            {"id": "Brotherhood_Capital", "core_slot": 1, "rival": "Enclave_Capital"},
            {"id": "Outcasts", "core_slot": 1, "rival": "Brotherhood_Capital"},
            {"id": "Enclave_Capital", "core_slot": 3, "rival": "Brotherhood_Capital"},
            {"id": "Megaton", "core_slot": 4, "rival": "Slavers_ParadiseFalls"},
            {"id": "Tenpenny", "core_slot": 4, "rival": None},
            {"id": "RivetCity", "core_slot": 4, "rival": "Slavers_ParadiseFalls"},
            {"id": "Slavers_ParadiseFalls", "core_slot": 7, "rival": "Regulators"},
            {"id": "Regulators", "core_slot": 0, "rival": "Slavers_ParadiseFalls"},
        ),
    },
    "FO76": {
        "title": "FO76",
        "native_fact_count": 954,
        "native_repu_count": 0,
        "karma_enabled": True,
        "karma_optional": True,
        "karma_note": "7-tier FO76 Hostile..Ally curve mapped onto the 16-state Fame/Infamy matrix; global Karma optional.",
        "factions": (
            {"id": "Settlers_Foundation", "core_slot": 4, "rival": "Raiders_Crater"},
            {"id": "Raiders_Crater", "core_slot": 7, "rival": "Settlers_Foundation"},
            {"id": "Brotherhood_Appalachia", "core_slot": 1, "rival": "Enclave_Whitespring"},
            {"id": "Responders", "core_slot": 0, "rival": "Raiders_Crater"},
            {"id": "FreeStates", "core_slot": 2, "rival": "Enclave_Whitespring"},
            {"id": "Enclave_Whitespring", "core_slot": 3, "rival": "Brotherhood_Appalachia"},
        ),
    },
    "FO1": {
        "title": "FO1",
        "karma_enabled": True,
        "karma_note": "Classic town reputations mapped onto the Fame/Infamy faction axis alongside global Karma.",
        "factions": (
            {"id": "ShadySands", "core_slot": 4, "rival": None},
            {"id": "Junktown", "core_slot": 4, "rival": None},
            {"id": "Hub", "core_slot": 4, "rival": None},
            {"id": "Boneyard", "core_slot": 4, "rival": None},
        ),
    },
    "FO2": {
        "title": "FO2",
        "karma_enabled": True,
        "karma_note": "Northern California town standings mapped onto the Fame/Infamy faction axis alongside global Karma.",
        "factions": (
            {"id": "Arroyo", "core_slot": 4, "rival": None},
            {"id": "Klamath", "core_slot": 4, "rival": None},
            {"id": "VaultCity", "core_slot": 3, "rival": "NewReno"},
            {"id": "NewReno", "core_slot": 7, "rival": "VaultCity"},
            {"id": "NCR_Classic", "core_slot": 5, "rival": "NewReno"},
        ),
    },
    "Tactics": {
        "title": "Tactics",
        "karma_enabled": True,
        "karma_note": "Midwest regional standing mapped onto the Fame/Infamy faction axis alongside global Karma.",
        "factions": (
            {"id": "Brotherhood_Midwest", "core_slot": 1, "rival": None},
        ),
    },
}


def clamp_rep_axis(value: float) -> float:
    v = float(value)
    if v < REP_AXIS_MIN:
        return REP_AXIS_MIN
    if v > REP_AXIS_MAX:
        return REP_AXIS_MAX
    return v


def clamp_karma(value: float) -> float:
    v = float(value)
    if v < KARMA_MIN:
        return KARMA_MIN
    if v > KARMA_MAX:
        return KARMA_MAX
    return v


def rep_tier_index(score: float, thresholds: Tuple[float, float, float] = DEFAULT_TIER_THRESHOLDS) -> int:
    """Return 0 (None), 1 (Low), 2 (Medium), or 3 (High) for a 0..100 Fame or Infamy value."""
    low, med, high = thresholds
    if not (0.0 < low < med < high <= 100.0):
        raise ValueError(f"invalid Fame/Infamy thresholds: {thresholds}")
    s = clamp_rep_axis(score)
    if s >= high:
        return 3
    if s >= med:
        return 2
    if s >= low:
        return 1
    return 0


def evaluate_faction_reputation(
    fame: float,
    infamy: float,
    thresholds: Tuple[float, float, float] = DEFAULT_TIER_THRESHOLDS,
) -> ReputationStateSpec:
    """Evaluate Fame x Infamy on New Vegas's 16-state matrix (strictly independent of global Karma)."""
    f_tier = rep_tier_index(fame, thresholds)
    i_tier = rep_tier_index(infamy, thresholds)
    return NV_16_STATE_MATRIX[(i_tier, f_tier)]


def fo76_tier_to_state(tier_name: str) -> ReputationStateSpec:
    if tier_name not in FO76_TIER_TO_FAME_INFAMY:
        raise ValueError(f"unknown FO76 reputation tier {tier_name!r}")
    fame, infamy = FO76_TIER_TO_FAME_INFAMY[tier_name]
    return evaluate_faction_reputation(fame, infamy)


def companion_moral_global(karma: float) -> int:
    """Global moral companion reaction code stored in FO4SF_CompanionMoralReaction (0x807):
      -2 = good companion desertion (<= -500)
      -1 = good companion warning (-499 .. -250)
       0 = steady (-249 .. +499)
      +1 = evil companion warning (>= +500)
    """
    k = clamp_karma(karma)
    if k <= -500.0:
        return -2
    if k <= -250.0:
        return -1
    if k >= 500.0:
        return 1
    return 0


def companion_reaction_for_alignment(karma: float, alignment: str) -> str:
    """Evaluate how a Good, Evil, or Neutral companion reacts to the player's global Karma."""
    k = clamp_karma(karma)
    norm = alignment.strip().capitalize()
    if norm == "Good":
        if k <= -500.0:
            return "leave"
        if k <= -250.0:
            return "warn"
        return "steady"
    if norm == "Evil":
        if k >= 500.0:
            return "warn"
        return "steady"
    if norm == "Neutral":
        return "ignore"
    raise ValueError(f"unknown companion alignment {alignment!r}")


def evaluate_karma(karma: float) -> Dict[str, object]:
    """Evaluate global Karma (-1000..+1000) into tier (-2..+2), dialogue perk, companion code, and ending slide."""
    k = clamp_karma(karma)
    if k <= -750.0:
        spec = KARMA_TIERS[0]
    elif k <= -250.0:
        spec = KARMA_TIERS[1]
    elif k < 250.0:
        spec = KARMA_TIERS[2]
    elif k < 750.0:
        spec = KARMA_TIERS[3]
    else:
        spec = KARMA_TIERS[4]
    return {
        "karma": k,
        "tier": spec.tier,
        "title": spec.title,
        "dialogue_tag": spec.dialogue_tag,
        "perk_edid": spec.perk_edid,
        "perk_id": spec.perk_id,
        "ending_slide": spec.ending_slide,
        "companion_global": companion_moral_global(k),
        "good_companion": companion_reaction_for_alignment(k, "Good"),
        "neutral_companion": companion_reaction_for_alignment(k, "Neutral"),
        "evil_companion": companion_reaction_for_alignment(k, "Evil"),
    }
