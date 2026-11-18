"""Pip-Boy STAT and DATA integration for FO4SFReputation.esm (both Stage=5 kit INI and Stage=2 AS3 shell).

Both Pip-Boy routes in #817 consume the shared Karma AVIF in FO4SFCoreValues.esm (0x830 FO4SF_Karma) plus
the faction standing AVIF records in FO4SFReputation.esm:
  - FO4SFCoreValues.esm:0x830 FO4SF_Karma (-1000..+1000)
  - FO4SFReputation.esm:0x805 FO4SF_VendorBuyMult (0.75..1.50)
  - FO4SFReputation.esm:0x820..0x82E FO4SF_Fame_* (0..100)
  - FO4SFReputation.esm:0x830..0x83E FO4SF_Infamy_* (0..100)
  - FO4SFReputation.esm:0x840..0x84E FO4SF_RepState_* (0..15 16-state matrix code)
"""
from typing import Dict, List, Mapping, Tuple

from fo4sf.core.core_values import CORE_VALUES_PLUGIN

from .tables import (
    CORE_FACTIONS,
    KARMA_TIERS,
    PLUGIN_NAME,
    RECORD_IDS,
    SHARED_CORE_FORM_IDS,
    STATE_BY_CODE,
    evaluate_faction_reputation,
    evaluate_karma,
    slot_factions,
)

# Exact character set and column limits enforced by scripts/ui/make_pipboy_kit.py & sfse/FO4SFPipboyMenu
KIT_ALLOWED_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 !#%&'()*+,-./:;<=>?[]_")
TAB_MAX_COLS = 9
SUB_MAX_COLS = 13
ROW_LABEL_MAX_COLS = 33
FOOTER_LABEL_MAX_COLS = 10
MAX_ROWS_PER_PAGE = 64

TSV_HEADER = (
    "slot\tpage\ttarget_list\tfaction_key\tdisplay_label\t"
    "fame_av_hex\tinfamy_av_hex\tstate_av_hex\tkarma_av_hex"
)


def runtime_av_hex(load_index: int, local_id: int) -> str:
    if not (1 <= int(load_index) <= 0xFE):
        raise ValueError(f"load_index must be in 0x01..0xFE (got {load_index:#x})")
    if not (0x800 <= int(local_id) <= 0xFFFFFF):
        raise ValueError(f"local_id must be in 0x800..0xFFFFFF (got {local_id:#x})")
    full_id = ((int(load_index) & 0xFF) << 24) | (int(local_id) & 0xFFFFFF)
    return f"{full_id:08X}"


def validate_kit_label(label: str, max_cols: int, what: str) -> str:
    if not label:
        raise ValueError(f"{what} is empty")
    bad = sorted({c for c in label if c not in KIT_ALLOWED_CHARS})
    if bad:
        raise ValueError(f"{what} {label!r} contains disallowed kit characters: {bad}")
    if len(label) > max_cols:
        raise ValueError(f"{what} {label!r} length {len(label)} exceeds {max_cols} columns")
    return label


def build_kit_page_sections(
    load_index: int = 0x0A,
    core_load_index: int = 0x02,
    slot_count: int = 8,
) -> Tuple[str, str]:
    """Build [Page STAT/KARMA] and [Page DATA/REPUTATION] blocks valid for FO4SFPipboyMenu.ini Stage=5."""
    validate_kit_label("STAT", TAB_MAX_COLS, "tab")
    validate_kit_label("KARMA", SUB_MAX_COLS, "sub-tab")
    validate_kit_label("DATA", TAB_MAX_COLS, "tab")
    validate_kit_label("REPUTATION", SUB_MAX_COLS, "sub-tab")

    karma_hex = runtime_av_hex(core_load_index, SHARED_CORE_FORM_IDS["KarmaAvId"])
    buy_hex = runtime_av_hex(load_index, RECORD_IDS["VendorBuyMultAvId"])

    stat_rows = [
        ("GLOBAL KARMA", f"av:{karma_hex}"),
        ("VENDOR BUY MULT", f"av:{buy_hex}"),
    ]
    for lbl, _ in stat_rows:
        validate_kit_label(lbl, ROW_LABEL_MAX_COLS, "STAT/KARMA row")
    validate_kit_label("KARMA", FOOTER_LABEL_MAX_COLS, "STAT/KARMA footer")

    stat_lines = [
        "[Page STAT/KARMA]",
        *(f"Row={lbl}|{val}" for lbl, val in stat_rows),
        f"Footer=KARMA|av:{karma_hex}",
        "Footer=HP|health",
        "Footer=LEVEL|level",
    ]

    rep_rows: List[Tuple[str, str]] = []
    for fac in slot_factions(slot_count):
        base_lbl = str(fac["pipboy_label"])
        fame_lbl = validate_kit_label(f"{base_lbl} FAME", ROW_LABEL_MAX_COLS, "DATA/REPUTATION row")
        inf_lbl = validate_kit_label(f"{base_lbl} INFAMY", ROW_LABEL_MAX_COLS, "DATA/REPUTATION row")
        st_lbl = validate_kit_label(f"{base_lbl} STATE", ROW_LABEL_MAX_COLS, "DATA/REPUTATION row")
        rep_rows.append((fame_lbl, f"av:{runtime_av_hex(load_index, int(fac['fame_av_id']))}"))
        rep_rows.append((inf_lbl, f"av:{runtime_av_hex(load_index, int(fac['infamy_av_id']))}"))
        rep_rows.append((st_lbl, f"av:{runtime_av_hex(load_index, int(fac['state_av_id']))}"))

    if len(rep_rows) > MAX_ROWS_PER_PAGE:
        raise ValueError(f"DATA/REPUTATION row count {len(rep_rows)} exceeds {MAX_ROWS_PER_PAGE}")

    data_lines = [
        "[Page DATA/REPUTATION]",
        *(f"Row={lbl}|{val}" for lbl, val in rep_rows),
        f"Footer=KARMA|av:{karma_hex}",
    ]
    return "\n".join(stat_lines), "\n".join(data_lines)


def inject_pipboy_kit_pages(
    base_ini_text: str,
    load_index: int = 0x0A,
    core_load_index: int = 0x02,
    slot_count: int = 8,
) -> str:
    """Insert or replace [Page STAT/KARMA] and [Page DATA/REPUTATION] in a FO4SFPipboyMenu.ini document."""
    stat_sec, data_sec = build_kit_page_sections(load_index, core_load_index=core_load_index, slot_count=slot_count)

    # Strip any prior [Page STAT/KARMA] or [Page DATA/REPUTATION] blocks first for idempotency
    cleaned_lines: List[str] = []
    skip_section = False
    for line in base_ini_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            skip_section = stripped.upper() in ("[PAGE STAT/KARMA]", "[PAGE DATA/REPUTATION]")
        if not skip_section:
            cleaned_lines.append(line)

    out_lines: List[str] = []
    inserted_stat = False
    inserted_data = False

    idx = 0
    while idx < len(cleaned_lines):
        line = cleaned_lines[idx]
        stripped = line.strip()
        if stripped.upper() == "[PAGE INV/ITEMS]" and not inserted_stat:
            if out_lines and out_lines[-1].strip() != "":
                out_lines.append("")
            out_lines.extend(stat_sec.splitlines())
            out_lines.append("")
            inserted_stat = True
        elif stripped.upper().startswith("[PAGE MAP/") and not inserted_data:
            if out_lines and out_lines[-1].strip() != "":
                out_lines.append("")
            out_lines.extend(data_sec.splitlines())
            out_lines.append("")
            inserted_data = True
        out_lines.append(line)
        idx += 1

    if not inserted_stat:
        out_lines.extend(["", *stat_sec.splitlines()])
    if not inserted_data:
        out_lines.extend(["", *data_sec.splitlines()])
    return "\n".join(out_lines).rstrip("\n") + "\n"


def build_shell_manifest(slot_count: int = 8) -> Dict[str, object]:
    """Build JSON manifest for Stage=2 AS3 FO4SF_Fo4Shell (STAT -> PerksList, DATA -> StatsList)."""
    factions = slot_factions(slot_count)
    return {
        "schema": 1,
        "plugin": PLUGIN_NAME,
        "core_values_plugin": CORE_VALUES_PLUGIN,
        "stat_perks_karma": {
            "target": "Menu_mc.DataObj.PerksList",
            "karma_av_id": f"0x{SHARED_CORE_FORM_IDS['KarmaAvId']:04X}",
            "karma_value_glob_id": f"0x{SHARED_CORE_FORM_IDS['KarmaValueGlobId']:04X}",
            "karma_tier_glob_id": f"0x{SHARED_CORE_FORM_IDS['KarmaTierGlobId']:04X}",
            "vendor_buy_mult_av_id": f"0x{RECORD_IDS['VendorBuyMultAvId']:04X}",
            "tiers": [
                {
                    "tier": t.tier,
                    "min": t.min_karma,
                    "max": t.max_karma,
                    "title": t.title,
                    "perk_edid": t.perk_edid,
                    "perk_id": f"0x{t.perk_id:04X}",
                }
                for t in KARMA_TIERS
            ],
        },
        "data_stats_reputation": {
            "target": "Menu_mc.DataObj.StatsList",
            "category": "Reputation",
            "factions": [
                {
                    "slot": fac["index"],
                    "key": fac["key"],
                    "label": fac["pipboy_label"],
                    "fact_id": f"0x{int(fac['fact_id']):04X}",
                    "fame_av_id": f"0x{int(fac['fame_av_id']):04X}",
                    "infamy_av_id": f"0x{int(fac['infamy_av_id']):04X}",
                    "state_av_id": f"0x{int(fac['state_av_id']):04X}",
                }
                for fac in factions
            ],
            "states": [
                {
                    "code": code,
                    "state_id": STATE_BY_CODE[code].state_id,
                    "title": STATE_BY_CODE[code].title,
                    "disposition": STATE_BY_CODE[code].disposition,
                    "buy_mult": STATE_BY_CODE[code].buy_mult,
                    "sell_mult": STATE_BY_CODE[code].sell_mult,
                    "allow_trade": STATE_BY_CODE[code].allow_trade,
                    "gmst_form_id": STATE_BY_CODE[code].gmst_form_id,
                    "esm_status": STATE_BY_CODE[code].esm_status,
                }
                for code in sorted(STATE_BY_CODE)
            ],
        },
    }


def format_shell_tsv(slot_count: int = 8) -> str:
    """Serialize FO4SFPipboyReputation.tsv consumed by the Stage=2 shell bridge."""
    karma_hex = f"0x{SHARED_CORE_FORM_IDS['KarmaAvId']:04X}"
    rows = [
        TSV_HEADER,
        f"-1\tSTAT\tPerksList\tGlobalKarma\tKARMA\t0x0000\t0x0000\t0x0000\t{karma_hex}",
    ]
    for fac in slot_factions(slot_count):
        rows.append(
            f"{fac['index']}\tDATA\tStatsList\t{fac['key']}\t{fac['pipboy_label']}\t"
            f"0x{int(fac['fame_av_id']):04X}\t0x{int(fac['infamy_av_id']):04X}\t"
            f"0x{int(fac['state_av_id']):04X}\t{karma_hex}"
        )
    return "\n".join(rows) + "\n"


def format_as3_stat_karma_entry(karma_value: float) -> Dict[str, object]:
    """Build a STAT -> PerksList AS3 object `{text, rank, maxRank, description}` from FO4SF_RepKarma."""
    info = evaluate_karma(karma_value)
    k_int = int(round(float(info["karma"])))
    return {
        "text": f"Karma: {info['title']} ({k_int:+d})",
        "rank": int(info["tier"]) + 3,
        "maxRank": 5,
        "description": (
            f"Moral alignment {info['title']} ({k_int:+d} on -1000..+1000). "
            f"Dialogue tag {info['dialogue_tag']}; ending slide {info['ending_slide']}."
        ),
    }


def format_as3_data_reputation_rows(
    karma_value: float,
    faction_scores: Mapping[str, Tuple[float, float]],
) -> List[Dict[str, object]]:
    """Build DATA -> StatsList Reputation category entries `{category, text, value, showAsPercent}`."""
    k_info = evaluate_karma(karma_value)
    k_int = int(round(float(k_info["karma"])))
    rows: List[Dict[str, object]] = [
        {
            "category": "Reputation",
            "text": f"Karma ({k_info['title']})",
            "value": f"{k_int:+d}",
            "showAsPercent": False,
        }
    ]
    for fac in CORE_FACTIONS:
        key = str(fac["key"])
        fame, infamy = faction_scores.get(key, (0.0, 0.0))
        state = evaluate_faction_reputation(fame, infamy)
        rows.append(
            {
                "category": "Reputation",
                "text": f"{key}: {state.title}",
                "value": f"{int(round(fame))}/{int(round(infamy))}",
                "showAsPercent": False,
            }
        )
    return rows
