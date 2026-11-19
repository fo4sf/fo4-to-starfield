"""Cross-plugin FormID, record-type, VMAD property, and EditorID uniqueness checker (`1c`).

Resolves script-level `int` and `string` constants across `.psc` files for every
`Game.GetFormFromFile(id, plugin)` call and every C# writer-filled VMAD object
property, checks that `(plugin, id)` exists in that plugin's writer table with
the record type the Papyrus cast/property expects, and asserts that no EditorID
is defined in more than one FO4SF plugin.
"""

from __future__ import annotations

import os
import re
import struct
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from fo4sf.core.core_values import CORE_VALUES_JSON, load_core_values
from fo4sf.planet.esm import Plugin

# Known immutable engine/port base records referenced across scripts
KNOWN_EXTERNAL_RECORDS: Dict[str, Dict[int, Tuple[str, str]]] = {
    "Starfield.esm": {
        0x00000F: ("MISC", "Credits"),
        0x000014: ("ACHR", "PlayerRef"),
        0x000032: ("STAT", "COCMarkerHeading"),
        0x000038: ("GLOB", "GameHour"),
        0x000039: ("GLOB", "GameDaysPassed"),
        0x0002C2: ("AVIF", "Strength"),
        0x0002C3: ("AVIF", "Perception"),
        0x0002C4: ("AVIF", "Endurance"),
        0x0002C5: ("AVIF", "Charisma"),
        0x0002C6: ("AVIF", "Intelligence"),
        0x0002C7: ("AVIF", "Agility"),
        0x0002C8: ("AVIF", "Luck"),
        0x0002D4: ("AVIF", "Health"),
        0x0002D5: ("AVIF", "Oxygen"),
        0x0002DC: ("AVIF", "CarryWeight"),
        0x0002E2: ("AVIF", "O2Capacity"),
        0x000344: ("AVIF", "FollowerState"),
        0x00562D: ("DFOB", "StartupQuest_DO"),
        0x00ABF9: ("ALCH", "MedPack"),
        0x00D773: ("QUST", "DialogueFollowers"),
        0x010C35: ("ACTI", "ElevatorLiftTemplate"),
        0x01A21C: ("KYWD", "WorkshopItemKeyword"),
        0x01C21C: ("FACT", "PlayerFaction"),
        0x01D1D7: ("ARMO", "Clothes_Miner_Jumpsuit"),
        0x0301C5: ("PACK", "DefaultMaster_FollowPackage"),
        0x054BA7: ("KYWD", "WorkshopWorkbenchType"),
        0x0A7D31: ("GLOB", "MQ101Debug"),
        0x1A9565: ("QUST", "SQ_Groups"),
        0x1CCAC2: ("ACTI", "ControlConsoleTemplate"),
        0x1F50AD: ("KYWD", "OutpostBuildKeyword"),
        0x248D20: ("QUST", "SQ_ENV"),
        0x2B559A: ("AMMO", "Ammo50Caliber"),
        0x2C60E9: ("ACTI", "OutpostBeaconActivator"),
    },
    "FO4Port.esm": {
        0x0337F0: ("QUST", "FO4Port_DialogueSceneRef"),
        0x04D8A1: ("KYWD", "ArmorTypePower"),
    },
    "FO4TerrainCore.esm": {
        0x0A2ECD: ("ACTI", "FO4_WorkshopWorkbench"),
        0x0A775B: ("REFR", "FO4Core_CommonwealthMapMarkerVault111"),
    },
    "FO4TerrainCore_Mars.esm": {
        0x0A2ECD: ("ACTI", "FO4_WorkshopWorkbench"),
    },
    "FO4ActorRaider.esm": {
        0xF04801: ("NPC_", "FO4_LvlRaider_Calm"),
    },
    "FO4SFPipboyTravel.esm": {
        **{0x000800 + i: ("GLOB", f"FO4SF_PipboyTravelGlob_{i:02d}") for i in range(32) if i != 2},
    },
}

CAST_EXPECTED_TYPES: Dict[str, Set[str]] = {
    "actorvalue": {"AVIF"},
    "globalvariable": {"GLOB"},
    "perk": {"PERK"},
    "quest": {"QUST"},
    "faction": {"FACT"},
    "formlist": {"FLST"},
    "message": {"MESG"},
    "keyword": {"KYWD"},
    "armor": {"ARMO"},
    "weapon": {"WEAP"},
    "ammo": {"AMMO"},
    "potion": {"ALCH"},
    "ingestible": {"ALCH"},
    "miscobject": {"MISC"},
    "activator": {"ACTI"},
    "furniture": {"FURN"},
    "spell": {"SPEL"},
    "hazard": {"HAZD"},
    "actorbase": {"NPC_"},
    "actor": {"ACHR", "REFR"},
    "objectreference": {"REFR", "ACHR"},
    "gameplayoption": {"GPOF"},
    "form": {
        "MISC", "ALCH", "AMMO", "ARMO", "WEAP", "ACTI", "FURN", "STAT",
        "DOOR", "HAZD", "AVIF", "GLOB", "PERK", "QUST", "FACT", "FLST",
        "MESG", "KYWD", "SPEL", "NPC_", "REFR", "ACHR", "ENCH", "MGEF",
        "WATR", "COBJ", "BPTD",
    },
}

SEMANTIC_CONCEPT_KEYWORDS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("guns", ("skill_guns", "guns")),
    ("speech", ("skill_speech", "speech")),
    ("science", ("skill_science", "science")),
    ("medicine", ("skill_medicine", "medicine")),
    ("repair", ("skill_repair", "repair")),
    ("barter", ("skill_barter", "barter")),
    ("perception", ("perception",)),
    ("charisma", ("charisma",)),
    ("endurance", ("endurance",)),
    ("intelligence", ("intelligence",)),
    ("agility", ("agility",)),
    ("goodwill", ("fame", "state", "repfact")),
)

MUTAGEN_CLASS_TO_TYPE: Dict[str, str] = {
    "ActorValueInformation": "AVIF",
    "Global": "GLOB",
    "Perk": "PERK",
    "Quest": "QUST",
    "Faction": "FACT",
    "FormList": "FLST",
    "Message": "MESG",
    "Keyword": "KYWD",
    "Armor": "ARMO",
    "Weapon": "WEAP",
    "Ammunition": "AMMO",
    "Ingestible": "ALCH",
    "MiscItem": "MISC",
    "Activator": "ACTI",
    "Furniture": "FURN",
    "Spell": "SPEL",
    "MagicEffect": "MGEF",
    "ObjectEffect": "ENCH",
    "Hazard": "HAZD",
    "Water": "WATR",
    "ConstructibleObject": "COBJ",
    "BodyPartData": "BPTD",
    "Npc": "NPC_",
    "PlacedObject": "REFR",
    "PlacedNpc": "ACHR",
    "Cell": "CELL",
    "Worldspace": "WRLD",
    "GameplayOption": "GPOF",
    "GameplayOptionsGroup": "GPOG",
    "DialogTopic": "DIAL",
    "DialogResponses": "INFO",
    "DialogBranch": "DLBR",
    "Race": "RACE",
    "Package": "PACK",
}


@dataclass(frozen=True)
class PscFormRef:
    file_rel: str
    line_no: int
    plugin: str
    form_id: int
    cast_type: str
    lhs_name: str
    func_name: str


@dataclass(frozen=True)
class VmadPropBinding:
    cs_rel: str
    script_name: str
    prop_name: str
    target_plugin: str
    target_id: int


def parse_psc_declared_properties(psc_text: str) -> Tuple[Optional[str], Dict[str, str]]:
    """Return `(script_name, {prop_name_lower: psc_type})` for all declared properties in `psc_text`."""
    clean = re.sub(r"\{[^}]*\}", "", psc_text)
    sm = re.search(r"^\s*Scriptname\s+([A-Za-z_]\w*)", clean, re.I | re.M)
    script_name = sm.group(1) if sm else None
    props: Dict[str, str] = {}
    for line in clean.splitlines():
        code = line.split(";", 1)[0].strip()
        pm = re.match(r"^([A-Za-z_]\w*)(\[\])?\s+Property\s+([A-Za-z_]\w*)\b", code, re.I)
        if pm:
            ptype = pm.group(1) + (pm.group(2) or "")
            props[pm.group(3).lower()] = ptype
    return script_name, props


def parse_cs_vmad_bindings(cs_rel: str, cs_text: str) -> List[VmadPropBinding]:
    """Extract statically resolvable `(script_name, prop_name, target_plugin, target_id)` VMAD bindings from C#."""
    body = _strip_cs_selftest_tail(cs_text)
    m_plg = (
        re.search(r'Plugin\s*=\s*ModKey\.FromFileName\("([^"]+\.esm)"\)', body)
        or re.search(r'const\s+string\s+Plugin\s*=\s*"([^"]+\.esm)"', body)
        or re.search(r'DefaultPlugin\s*=\s*"([^"]+\.esm)"', body)
    )
    own_plugin = m_plg.group(1) if m_plg else ""
    m_scr = re.search(r'ScriptName\s*=\s*"([^"]+)"', body)
    default_script = m_scr.group(1) if m_scr else ""
    if not own_plugin or not default_script:
        return []

    uint_consts: Dict[str, int] = {}
    for line in body.splitlines():
        if "const uint " in line:
            tail = line.split("const uint ", 1)[1].split(";")[0]
            for part in tail.split(","):
                pm = re.match(r"\s*(\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)", part)
                if pm:
                    uint_consts[pm.group(1)] = int(pm.group(2), 0)

    # Load core_values.json map so `Core("FO4SF_...")` / `LoadCoreValueId("FO4SF_...")` resolves cleanly
    _, _, cv_recs = load_core_values()
    cv_by_edid = {r.edid.lower(): r.form_id for r in cv_recs}
    for var_m in re.finditer(r'(\w+)\s*=\s*(?:LoadCoreValueId|CoreId|GetCoreId)\("([^"]+)"\)', body):
        ed = var_m.group(2).lower()
        if ed in cv_by_edid:
            uint_consts[var_m.group(1)] = cv_by_edid[ed]

    modkey_aliases: Dict[str, str] = {
        "SfEsm": "Starfield.esm",
        "CoreValuesEsm": "FO4SFCoreValues.esm",
        "ProgressionEsm": "FO4SFProgression.esm",
        "Plugin": own_plugin,
        "modKey": own_plugin,
    }

    bindings: List[VmadPropBinding] = []

    def resolve_fk(fk_expr: str) -> Optional[Tuple[str, int]]:
        s = fk_expr.strip()
        m_own = re.match(r"^Own\(\s*([A-Za-z0-9_xX+]+)\s*\)$", s)
        if m_own:
            cid = _parse_int_literal(m_own.group(1), uint_consts)
            return (own_plugin, cid) if cid is not None else None
        m_sf = re.match(r"^Sf\(\s*([A-Za-z0-9_xX+]+)\s*\)$", s)
        if m_sf:
            cid = _parse_int_literal(m_sf.group(1), uint_consts)
            return ("Starfield.esm", cid) if cid is not None else None
        m_cv = re.match(r'^(?:Core|CoreFk|CvFk)\(\s*"([^"]+)"\s*\)$', s)
        if m_cv and m_cv.group(1).lower() in cv_by_edid:
            return ("FO4SFCoreValues.esm", cv_by_edid[m_cv.group(1).lower()])
        m_cv_id = re.match(r"^(?:Core|CoreFk|CvFk)\(\s*([A-Za-z0-9_xX+]+)\s*\)$", s)
        if m_cv_id:
            cid = _parse_int_literal(m_cv_id.group(1), uint_consts)
            return ("FO4SFCoreValues.esm", cid) if cid is not None else None
        m_fk = re.match(r"^new\s+FormKey\(\s*(\w+)\s*,\s*([A-Za-z0-9_xX+]+)\s*\)$", s)
        if m_fk and m_fk.group(1) in modkey_aliases:
            cid = _parse_int_literal(m_fk.group(2), uint_consts)
            return (modkey_aliases[m_fk.group(1)], cid) if cid is not None else None
        return None

    for m in re.finditer(r'(?:Obj|ObjProp)\(\s*"([A-Za-z_]\w*)"\s*,\s*([^)]+\)?)\s*\)', body):
        pname, fk_expr = m.group(1), m.group(2)
        if not pname:
            continue
        res = resolve_fk(fk_expr)
        if res is not None:
            bindings.append(VmadPropBinding(cs_rel, default_script, pname, res[0], res[1]))

    for m in re.finditer(r'\["([A-Za-z_]\w*)"\]\s*=\s*([^,\r\n}]+)', body):
        pname, fk_expr = m.group(1), m.group(2)
        res = resolve_fk(fk_expr)
        if res is not None:
            bindings.append(VmadPropBinding(cs_rel, default_script, pname, res[0], res[1]))

    return bindings


def validate_vmad_bindings(
    catalog: Dict[str, Dict[int, Tuple[str, str]]],
    psc_props_by_script: Dict[str, Dict[str, str]],
    bindings: Iterable[VmadPropBinding],
) -> List[str]:
    """Validate C# writer-filled VMAD object properties against `.psc` property types and `catalog`."""
    errors: List[str] = []
    for b in bindings:
        sprops = psc_props_by_script.get(b.script_name.lower())
        if sprops is None:
            errors.append(f"{b.cs_rel}: script {b.script_name} not found for VMAD property {b.prop_name}")
            continue
        ptype = sprops.get(b.prop_name.lower())
        if ptype is None and b.script_name.lower() == "fo4sf_newgamequest":
            for alt_name in ("fo4sf_newgamespecial", "fo4sf_newgameversion"):
                alt = psc_props_by_script.get(alt_name)
                if alt is not None and b.prop_name.lower() in alt:
                    ptype = alt.get(b.prop_name.lower())
                    break
        if ptype is None:
            errors.append(f"{b.cs_rel}: {b.script_name} does not declare property {b.prop_name}")
            continue
        if b.target_plugin not in catalog or b.target_id not in catalog[b.target_plugin]:
            errors.append(
                f"{b.cs_rel}: {b.script_name}.{b.prop_name} -> {b.target_plugin}:0x{b.target_id:06X} missing in writer table"
            )
            continue
        actual_type, actual_edid = catalog[b.target_plugin][b.target_id]
        base_ptype = ptype[:-2] if ptype.endswith("[]") else ptype
        expected = {"QUST"} if base_ptype.lower().startswith("fo4sf_") else CAST_EXPECTED_TYPES.get(base_ptype.lower(), set())
        if expected and actual_type not in expected:
            errors.append(
                f"{b.cs_rel}: {b.script_name}.{b.prop_name} ({ptype}) bound to "
                f"{b.target_plugin}:0x{b.target_id:06X} ({actual_edid}) of wrong type {actual_type}"
            )
    return errors


def _parse_int_literal(expr: str, consts: Dict[str, int]) -> Optional[int]:
    s = expr.strip()
    while s.startswith("(") and s.endswith(")"):
        s = s[1:-1].strip()
    if "+" in s:
        left, right = s.split("+", 1)
        lv = _parse_int_literal(left, consts)
        rv = _parse_int_literal(right, consts)
        if lv is not None and rv is not None:
            return lv + rv
        # Loop variable offset `BaseId + i` -> verify slot 0 (`BaseId`)
        if lv is not None and re.fullmatch(r"[A-Za-z_]\w*", right.strip()):
            return lv
        return None
    if re.fullmatch(r"0[xX][0-9A-Fa-f]+u?", s):
        return int(s.rstrip("uU"), 16)
    if re.fullmatch(r"\d+u?", s):
        return int(s.rstrip("uU"), 10)
    return consts.get(s)


def _infer_type_from_const_name(const_name: str) -> str:
    low = const_name.lower()
    if "avif" in low or low.endswith("avid"):
        return "AVIF"
    if "glob" in low:
        return "GLOB"
    if "gpog" in low:
        return "GPOG"
    if "gpo" in low:
        return "GPOF"
    if "flst" in low or "listid" in low:
        return "FLST"
    if "perk" in low or low.startswith(("bg", "trait", "mut")):
        return "PERK"
    if "quest" in low:
        return "QUST"
    if "fact" in low or "faction" in low:
        return "FACT"
    if "msg" in low or "message" in low:
        return "MESG"
    if "mgef" in low or "effectid" in low:
        return "MGEF"
    if "ench" in low:
        return "ENCH"
    if "spell" in low or low.startswith("ab"):
        return "SPEL"
    if "ammo" in low or "caliber" in low:
        return "AMMO"
    if "cobj" in low or "recipe" in low:
        return "COBJ"
    if "bptd" in low:
        return "BPTD"
    if "hazd" in low or "hazard" in low:
        return "HAZD"
    if "watr" in low or "irradiatedwaterid" in low:
        return "WATR"
    if "kw" in low or "keyword" in low:
        return "KYWD"
    if "cell" in low:
        return "CELL"
    if "dial" in low or "topic" in low:
        return "DIAL"
    if "info" in low:
        return "INFO"
    if "dlbr" in low or "branch" in low:
        return "DLBR"
    if "race" in low:
        return "RACE"
    if "token" in low or "kitid" in low or "coreid" in low or "fanid" in low or "tapeid" in low or "plateid" in low or "canid" in low:
        return "MISC"
    if "pack" in low or "pkg" in low:
        return "PACK"
    if "furn" in low or ("frame" in low and "ref" not in low) or ("chair" in low and "ref" not in low):
        return "FURN"
    if "armor" in low or "helm" in low or "bodyid" in low or "piece" in low or "torsoid" in low or "armid" in low or "legid" in low:
        return "ARMO"
    if "weap" in low:
        return "WEAP"
    if "refid" in low or "markerid" in low:
        return "REFR"
    if "npcid" in low or "baseid" in low or "speakerid" in low:
        return "NPC_"
    if "radaway" in low or "radx" in low or "food" in low or "water" in low or "stimpak" in low or "bagid" in low or "craft" in low or "medkit" in low or "blend" in low or "ration" in low:
        return "ALCH"
    if "acti" in low or "kiosk" in low or "emitter" in low or "switch" in low or "pedestal" in low or "trap" in low or "rack" in low:
        return "ACTI"
    return "MISC"


def _strip_cs_selftest_tail(cs_text: str) -> str:
    cut = len(cs_text)
    for marker in (
        "public static int Fixture(",
        "public static int SelfTest(",
        "static string MakeMaster(",
    ):
        idx = cs_text.find(marker)
        if idx != -1 and idx < cut:
            cut = idx
    return cs_text[:cut]


def parse_cs_writer_records(cs_text: str) -> Tuple[Optional[str], Dict[int, Tuple[str, str]]]:
    """Extract `(plugin_name, {local_id: (record_type, edid)})` from a C# writer `Program.cs`."""
    body = _strip_cs_selftest_tail(cs_text)

    m_plg = (
        re.search(r'Plugin\s*=\s*ModKey\.FromFileName\("([^"]+\.esm)"\)', body)
        or re.search(r'const\s+string\s+Plugin\s*=\s*"([^"]+\.esm)"', body)
        or re.search(r'DefaultPlugin\s*=\s*"([^"]+\.esm)"', body)
    )
    if not m_plg:
        return None, {}
    plugin = m_plg.group(1)

    uint_consts: Dict[str, int] = {}
    str_consts: Dict[str, str] = {}
    # Multi-line & multi-declarator `const uint A = 0x800, B = 0x801;`
    for block_m in re.finditer(r"\bconst\s+uint\s+([^;]+);", body, re.S):
        for part in block_m.group(1).split(","):
            pm = re.match(r"\s*(\w+)\s*=\s*(0x[0-9A-Fa-f]+u?|\d+u?)", part.strip())
            if pm:
                uint_consts[pm.group(1)] = int(pm.group(2).rstrip("uU"), 0)
    for block_m in re.finditer(r"\bconst\s+string\s+([^;]+);", body, re.S):
        for part in block_m.group(1).split(","):
            pm = re.match(r'\s*(\w+)\s*=\s*"([^"]*)"', part.strip())
            if pm:
                str_consts[pm.group(1)] = pm.group(2)

    records: Dict[int, Tuple[str, str]] = {}

    # 1. Pair `<Stem>Id` and `<Stem>Edid` constants when `<Stem>Id` is an owned local FormID (`0x800..0xFFF`)
    for cname, cid in uint_consts.items():
        if not (0x800 <= cid <= 0xFFF) or cname in ("NextId", "MaxPool") or cname.startswith("Sf"):
            continue
        stem = cname[:-2] if cname.endswith("Id") else cname
        edid = str_consts.get(stem + "Edid") or ""
        rtype = _infer_type_from_const_name(cname)
        records[cid] = (rtype, edid)

    # 2. Explicit `new <MutagenClass>(Own(<id>), ...)` or `new FormKey(modKey, <id>)` with `EditorID = ...`
    for m in re.finditer(
        r"new\s+(?:SF\.|Mutagen\.Bethesda\.Starfield\.)?(\w+)\(\s*(?:Own\(|new\s+FormKey\(\s*(?:modKey|Plugin)\s*,\s*)([A-Za-z0-9_xX+() ]+)\)",
        body,
    ):
        cls_name, id_expr = m.group(1), m.group(2)
        rtype = MUTAGEN_CLASS_TO_TYPE.get(cls_name)
        cid = _parse_int_literal(id_expr, uint_consts)
        if not rtype or cid is None or cid < 0x800:
            continue
        snippet = body[m.end() : m.end() + 260]
        em = re.search(r'EditorID\s*=\s*(?:"([^"]+)"|([A-Za-z_]\w*))', snippet)
        edid = ""
        if em:
            edid = em.group(1) or str_consts.get(em.group(2) or "", "")
        prev_type, prev_edid = records.get(cid, (rtype, ""))
        records[cid] = (rtype, edid or prev_edid)

    # 3. Array tuple specs `new(0x820, "FO4SF_...", ...)` or `(0x820, "FO4SF_...", ...)`
    for m in re.finditer(r'(?:new\s*)?\(\s*(0x[0-9A-Fa-f]+)u?\s*,\s*"(FO4SF_[A-Za-z0-9_]+)"', body):
        cid = int(m.group(1), 16)
        edid = m.group(2)
        if cid < 0x800:
            continue
        rtype = _infer_type_from_const_name(edid + "Id")
        if "_BG_" in edid or "_Trait_" in edid or "_Perk_" in edid or "_Mut_" in edid or "_CompPerk_" in edid:
            rtype = "PERK"
        elif "_Special_" in edid or "_Skill_" in edid or edid == "FO4SF_Karma":
            rtype = "AVIF"
        elif "_Fact_" in edid or "_RepFact_" in edid:
            rtype = "FACT"
        records[cid] = (rtype, edid)

    # 4. NewGame `SpecialAvifBase` (if present in legacy/test snapshot)
    if "SpecialAvifBase" in uint_consts and "mod.ActorValueInformation.Add" in body:
        base = uint_consts["SpecialAvifBase"]
        names = ("Strength", "Perception", "Endurance", "Charisma", "Intelligence", "Agility", "Luck")
        for idx, nm in enumerate(names):
            records[base + idx] = ("AVIF", f"FO4SF_Special_{nm}")

    # 5. ReputationCore slot ranges (`0x810..`, `0x820..`, `0x830..`, `0x840..`, `0x850..`, `0x860..`, `0x870..`)
    if plugin == "FO4SFReputation.esm":
        slot_keys = ("Minutemen", "Brotherhood", "Railroad", "Institute", "Settlers", "NCR", "Legion", "Outlaws")
        for i, key in enumerate(slot_keys):
            records[0x810 + i] = ("FACT", f"FO4SF_RepFact_{key}")
            records[0x820 + i] = ("AVIF", f"FO4SF_Fame_{key}")
            records[0x830 + i] = ("AVIF", f"FO4SF_Infamy_{key}")
            records[0x840 + i] = ("AVIF", f"FO4SF_RepState_{key}")
            records[0x850 + i] = ("GLOB", f"FO4SF_FameGlob_{key}")
            records[0x860 + i] = ("GLOB", f"FO4SF_InfamyGlob_{key}")
            records[0x870 + i] = ("GLOB", f"FO4SF_StateGlob_{key}")

    # 6. CombatCore / CompanionsCore / PowerArmorCore placed ref ranges
    if plugin == "FO4SFCombat.esm":
        for off, nm in enumerate(("Head", "Torso", "LArm", "RArm", "LLeg", "RLeg")):
            records.setdefault(0x860 + off, ("REFR", f"FO4SF_ZonePlateRef_{nm}"))
        for cid, ed in (
            (0x866, "FO4SF_ArmoredTargetRef"),
            (0x867, "FO4SF_VatsTargetRef"),
            (0x868, "FO4SF_AmmoPedestalRef"),
            (0x869, "FO4SF_LegTrapRef"),
            (0x86A, "FO4SF_HardcoreSwitchRef"),
            (0x86B, "FO4SF_SupplyRackRef"),
        ):
            records.setdefault(cid, ("REFR", ed))
    if plugin == "FO4SFCompanions.esm":
        for i in range(4):
            records.setdefault(0x835 + i, ("ACHR", f"FO4SF_RecruitRef_{i + 1}"))
        records.setdefault(0x83A, ("ACHR", "FO4SF_StoryCompanionRef"))
    if plugin == "FO4SFMission.esm":
        records.setdefault(0x800, ("QUST", "FO4SF_Min00"))
        records.setdefault(0x814, ("QUST", "FO4SF_CodsworthKeeper"))
        records.setdefault(0x815, ("QUST", "FO4SF_PrestonFollow"))

    return plugin, records


def build_writer_catalog(
    repo_root: str,
    core_values_json: str = CORE_VALUES_JSON,
    include_core_values: bool = True,
) -> Tuple[Dict[str, Dict[int, Tuple[str, str]]], List[str]]:
    """Build `{plugin: {id: (rtype, edid)}}` across `core_values.json` and `dotnet/*/Program.cs`."""
    catalog: Dict[str, Dict[int, Tuple[str, str]]] = {
        k: dict(v) for k, v in KNOWN_EXTERNAL_RECORDS.items()
    }

    if include_core_values and os.path.isfile(core_values_json):
        cv_plugin, _, cv_records = load_core_values(core_values_json)
        catalog[cv_plugin] = {r.form_id: (r.record_type, r.edid) for r in cv_records}

    dotnet_dir = os.path.join(repo_root, "dotnet")
    if os.path.isdir(dotnet_dir):
        for entry in sorted(os.listdir(dotnet_dir)):
            if entry == "CoreValues" or entry.endswith("Probe"):
                continue
            prog = os.path.join(dotnet_dir, entry, "Program.cs")
            if not os.path.isfile(prog):
                continue
            with open(prog, encoding="utf-8") as handle:
                cs_text = handle.read()
            plugin, recs = parse_cs_writer_records(cs_text)
            if plugin and recs:
                catalog.setdefault(plugin, {}).update(recs)

    # Check duplicate EditorIDs across all FO4SF plugins
    edid_owners: Dict[str, List[Tuple[str, int, str]]] = {}
    for plugin, recs in sorted(catalog.items()):
        if not plugin.lower().startswith("fo4sf"):
            continue
        for fid, (rtype, edid) in sorted(recs.items()):
            if not edid:
                continue
            edid_owners.setdefault(edid.lower(), []).append((plugin, fid, edid))

    dup_errors: List[str] = []
    for _, owners in sorted(edid_owners.items()):
        distinct_plugins = {p for p, _, _ in owners}
        if len(distinct_plugins) > 1:
            desc = ", ".join(f"{p}:0x{fid:04X} ({ed})" for p, fid, ed in owners)
            dup_errors.append(f"Duplicate EditorID across plugins: {desc}")

    return catalog, dup_errors


def parse_psc_form_refs(file_rel: str, psc_text: str) -> List[PscFormRef]:
    """Resolve script-level `int` and `string` constants and extract `Game.GetFormFromFile` calls."""
    # Strip `{...}` doc comments
    clean = re.sub(r"\{[^}]*\}", lambda m: "\n" * m.group(0).count("\n"), psc_text)

    int_consts: Dict[str, int] = {}
    str_consts: Dict[str, str] = {}
    func_params: Dict[str, Set[str]] = {}

    current_func = "<module>"
    lines = clean.splitlines()

    for raw_line in lines:
        code = raw_line.split(";", 1)[0].strip()
        if not code:
            continue
        fm = re.match(r"^(?:[A-Za-z_]\w*(?:\[\])?\s+)?(?:Function|Event)\s+([A-Za-z_.]+)\s*\(([^)]*)\)", code, re.I)
        if fm:
            current_func = fm.group(1)
            params: Set[str] = set()
            for p in fm.group(2).split(","):
                ptoks = p.strip().split("=")[0].strip().split()
                if len(ptoks) >= 2:
                    params.add(ptoks[-1])
            func_params[current_func] = params
            continue
        if re.match(r"^End(?:Function|Event)\b", code, re.I):
            current_func = "<module>"
            continue

        if current_func == "<module>":
            im = re.match(r"^int\s+(?:Property\s+)?(\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)\b", code, re.I)
            if im:
                int_consts[im.group(1)] = int(im.group(2), 0)
            sm = re.match(r'^string\s+(?:Property\s+)?(\w+)\s*=\s*"([^"]+)"', code, re.I)
            if sm:
                str_consts[sm.group(1)] = sm.group(2)

    refs: List[PscFormRef] = []
    current_func = "<module>"
    for idx, raw_line in enumerate(lines, start=1):
        code = raw_line.split(";", 1)[0].strip()
        if not code:
            continue
        fm = re.match(r"^(?:[A-Za-z_]\w*(?:\[\])?\s+)?(?:Function|Event)\s+([A-Za-z_.]+)\s*\(", code, re.I)
        if fm:
            current_func = fm.group(1)
        elif re.match(r"^End(?:Function|Event)\b", code, re.I):
            current_func = "<module>"

        for gm in re.finditer(
            r"Game\.GetFormFromFile\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)(?:\s+as\s+([A-Za-z_]\w*))?",
            code,
        ):
            id_expr, plg_expr, cast_raw = gm.group(1).strip(), gm.group(2).strip(), gm.group(3)
            params = func_params.get(current_func, set())
            # Skip helper wrappers whose id or plugin is a runtime function parameter (e.g. GiveIfPresent, LoadDoor)
            if id_expr in params or plg_expr in params:
                continue

            if plg_expr.startswith('"') and plg_expr.endswith('"'):
                plugin = plg_expr[1:-1]
            else:
                plugin = str_consts.get(plg_expr, "")
            if not plugin:
                continue

            fid = _parse_int_literal(id_expr, int_consts)
            if fid is None or fid == 0:
                continue

            lhs_part = code[: gm.start()].strip()
            lhs_m = re.search(r"([A-Za-z_]\w*)\s*=\s*$", lhs_part)
            lhs_name = lhs_m.group(1) if lhs_m else ""
            cast_type = (cast_raw or "Form").strip()

            refs.append(
                PscFormRef(
                    file_rel=file_rel,
                    line_no=idx,
                    plugin=plugin,
                    form_id=fid,
                    cast_type=cast_type,
                    lhs_name=lhs_name,
                    func_name=current_func,
                )
            )
    return refs


def validate_psc_form_refs(
    catalog: Dict[str, Dict[int, Tuple[str, str]]],
    refs: Iterable[PscFormRef],
) -> List[str]:
    """Validate resolved `Game.GetFormFromFile` references against `catalog`."""
    errors: List[str] = []
    for ref in refs:
        # Port/Terrain placed anchors resolved dynamically at build time (e.g. VaultSuitId = 0 default) are checked when in catalog
        if ref.plugin in ("FO4Port.esm", "FO4TerrainCore.esm", "FO4TerrainCore_Mars.esm"):
            if ref.form_id not in catalog.get(ref.plugin, {}):
                continue

        if ref.plugin not in catalog:
            errors.append(
                f"{ref.file_rel}:{ref.line_no} references unknown plugin '{ref.plugin}' (0x{ref.form_id:06X})"
            )
            continue

        plg_table = catalog[ref.plugin]
        if ref.form_id not in plg_table:
            errors.append(
                f"{ref.file_rel}:{ref.line_no} {ref.plugin}:0x{ref.form_id:06X} does not exist in writer table"
            )
            continue

        actual_type, actual_edid = plg_table[ref.form_id]
        cast_low = ref.cast_type.lower()
        if cast_low.startswith("fo4sf_"):
            expected_types = {"QUST"}
        else:
            expected_types = CAST_EXPECTED_TYPES.get(cast_low, set())

        if expected_types and actual_type not in expected_types:
            errors.append(
                f"{ref.file_rel}:{ref.line_no} {ref.plugin}:0x{ref.form_id:06X} ({actual_edid}) is {actual_type}, "
                f"cannot cast as {ref.cast_type}"
            )
            continue

        # Semantic check: catch same-record-type wrong ID bugs (e.g. reading Strength 0x800 as Guns skill!)
        context_low = f"{ref.func_name} {ref.lhs_name}".lower()
        edid_low = actual_edid.lower()
        if edid_low and ref.plugin.lower().startswith("fo4sf"):
            for concept, allowed_tokens in SEMANTIC_CONCEPT_KEYWORDS:
                if re.search(rf"(?:^|_|\b){concept}(?:$|_|\b|av|skill|glob|val)", context_low) or concept in ref.lhs_name.lower() or concept in ref.func_name.lower():
                    if not any(tok in edid_low for tok in allowed_tokens):
                        errors.append(
                            f"{ref.file_rel}:{ref.line_no} semantic mismatch in {ref.func_name}/{ref.lhs_name}: "
                            f"expected '{concept}' record, but {ref.plugin}:0x{ref.form_id:06X} is '{actual_edid}' ({actual_type})"
                        )
                        break

    return errors


def collect_psc_props_by_script(repo_root: str) -> Dict[str, Dict[str, str]]:
    """Scan `scripts/**/*.psc` and return `{script_name_lower: {prop_name_lower: psc_type}}`."""
    out: Dict[str, Dict[str, str]] = {}
    scripts_root = os.path.join(repo_root, "scripts")
    if not os.path.isdir(scripts_root):
        return out
    for dp, dirs, fns in os.walk(scripts_root):
        dirs.sort()
        for fn in sorted(fns):
            if not fn.lower().endswith(".psc"):
                continue
            with open(os.path.join(dp, fn), encoding="utf-8") as handle:
                sname, props = parse_psc_declared_properties(handle.read())
            if sname:
                out[sname.lower()] = props
    return out


_VMAD_PRIMITIVE_PSC_TYPES: Dict[int, str] = {
    2: "string",
    3: "int",
    4: "float",
    5: "bool",
    12: "string[]",
    13: "int[]",
    14: "float[]",
    15: "bool[]",
}


@dataclass(frozen=True)
class BinaryVmadProperty:
    plugin_name: str
    record_edid: str
    script_name: str
    prop_name: str
    prop_type: int
    object_refs: Tuple[Tuple[int, str, int], ...]  # (alias, target_plugin, local_id)


@dataclass(frozen=True)
class BinaryEsmReport:
    plugin_name: str
    masters: Tuple[str, ...]
    own_records: Dict[int, Tuple[str, str]]  # local_id -> (rec_type, edid)
    vmad_properties: Tuple[BinaryVmadProperty, ...]
    cross_plugin_item_refs: Tuple[Tuple[str, str, int], ...]  # (context, target_plugin, local_id)


def _resolve_esm_formid(raw_fid: int, masters: Sequence[str], plugin_name: str) -> Tuple[str, int]:
    idx = (raw_fid >> 24) & 0xFF
    local_id = raw_fid & 0xFFFFFF
    if idx < len(masters):
        return masters[idx], local_id
    return plugin_name, local_id


def parse_binary_vmad_properties(
    vmad_bytes: bytes,
    masters: Sequence[str],
    plugin_name: str,
    record_edid: str,
) -> List[BinaryVmadProperty]:
    """Decode Papyrus VMAD v5/v6 script properties and resolve Object/Object[] FormIDs via `masters`."""
    if len(vmad_bytes) < 6:
        raise ValueError(f"{plugin_name} ({record_edid}): truncated VMAD header ({len(vmad_bytes)} bytes)")
    _ver, obj_fmt, script_count = struct.unpack_from("<HHH", vmad_bytes, 0)
    p = 6
    out: List[BinaryVmadProperty] = []

    def read_elem(elem_type: int) -> Optional[Tuple[int, str, int]]:
        nonlocal p
        if elem_type == 1:
            if obj_fmt == 2:
                _unused, alias, raw_fid = struct.unpack_from("<HhI", vmad_bytes, p)
            else:
                raw_fid, alias, _unused = struct.unpack_from("<IhH", vmad_bytes, p)
            p += 8
            if raw_fid == 0:
                return None
            tgt_plg, local_id = _resolve_esm_formid(raw_fid, masters, plugin_name)
            return (alias, tgt_plg, local_id)
        if elem_type == 2:
            slen = struct.unpack_from("<H", vmad_bytes, p)[0]
            p += 2 + slen
            return None
        if elem_type in (3, 4):
            p += 4
            return None
        if elem_type == 5:
            p += 1
            return None
        raise ValueError(f"{plugin_name} ({record_edid}): unsupported VMAD element type {elem_type} at offset {p}")

    for _ in range(script_count):
        slen = struct.unpack_from("<H", vmad_bytes, p)[0]
        p += 2
        sname = vmad_bytes[p : p + slen].decode("cp1252", "replace")
        p += slen
        p += 1  # status byte
        prop_count = struct.unpack_from("<H", vmad_bytes, p)[0]
        p += 2
        for _ in range(prop_count):
            plen = struct.unpack_from("<H", vmad_bytes, p)[0]
            p += 2
            pname = vmad_bytes[p : p + plen].decode("cp1252", "replace")
            p += plen
            ptype, _pstatus = struct.unpack_from("<BB", vmad_bytes, p)
            p += 2
            obj_refs: List[Tuple[int, str, int]] = []
            if 1 <= ptype <= 5:
                r = read_elem(ptype)
                if r is not None:
                    obj_refs.append(r)
            elif 11 <= ptype <= 15:
                arr_len = struct.unpack_from("<I", vmad_bytes, p)[0]
                p += 4
                for _ in range(arr_len):
                    r = read_elem(ptype - 10)
                    if r is not None:
                        obj_refs.append(r)
            else:
                raise ValueError(f"{plugin_name} ({record_edid}): unsupported VMAD property type {ptype} on {sname}.{pname}")
            if sname:
                out.append(BinaryVmadProperty(plugin_name, record_edid, sname, pname, ptype, tuple(obj_refs)))

    return out


def inspect_esm_binary(esm_path: str) -> BinaryEsmReport:
    """Inspect a compiled `.esm` file's TES4 masters, owned EditorIDs, VMAD bindings, and CNTO/NAME references."""
    plugin_name = os.path.basename(esm_path)
    own_records: Dict[int, Tuple[str, str]] = {}
    vmad_props: List[BinaryVmadProperty] = []
    item_refs: List[Tuple[str, str, int]] = []

    with Plugin(esm_path) as plg:
        masters = tuple(plg.masters)
        self_idx = plg.self_index
        for grp in plg.groups:
            for start, end in plg.groups[grp]:
                for item in plg.walk(start, end):
                    if item[0] != "REC":
                        continue
                    rec = plg.record_at(item[1])
                    rtype = rec.sig.decode("latin1")
                    owner_idx = (rec.formid >> 24) & 0xFF
                    local_id = rec.formid & 0xFFFFFF
                    edid = rec.edid
                    if owner_idx == self_idx:
                        own_records[local_id] = (rtype, edid)

                    vmad_raw = rec.get(b"VMAD")
                    if vmad_raw is not None:
                        vmad_props.extend(
                            parse_binary_vmad_properties(vmad_raw, masters, plugin_name, edid or f"0x{local_id:06X}")
                        )

                    if rtype in ("CONT", "NPC_"):
                        for cnto in rec.all(b"CNTO"):
                            if len(cnto) >= 8:
                                raw_item_fid, _cnt = struct.unpack_from("<Ii", cnto, 0)
                                if raw_item_fid != 0:
                                    tgt_plg, tgt_id = _resolve_esm_formid(raw_item_fid, masters, plugin_name)
                                    item_refs.append((f"{rtype}:{edid or hex(local_id)}.CNTO", tgt_plg, tgt_id))
                    elif rtype in ("REFR", "ACHR") and owner_idx == self_idx:
                        name_sub = rec.get(b"NAME")
                        if name_sub is not None and len(name_sub) == 4:
                            raw_base_fid = struct.unpack_from("<I", name_sub, 0)[0]
                            if raw_base_fid != 0:
                                tgt_plg, tgt_id = _resolve_esm_formid(raw_base_fid, masters, plugin_name)
                                item_refs.append((f"{rtype}:{edid or hex(local_id)}.NAME", tgt_plg, tgt_id))

    return BinaryEsmReport(
        plugin_name=plugin_name,
        masters=masters,
        own_records=own_records,
        vmad_properties=tuple(vmad_props),
        cross_plugin_item_refs=tuple(item_refs),
    )


def validate_staged_esms(
    esm_paths: Sequence[str],
    catalog: Dict[str, Dict[int, Tuple[str, str]]],
    psc_props_by_script: Dict[str, Dict[str, str]],
) -> List[str]:
    """Validate compiled `.esm` files for duplicate EditorIDs, cross-plugin refs, and VMAD property parity."""
    errors: List[str] = []
    merged_catalog: Dict[str, Dict[int, Tuple[str, str]]] = {k: dict(v) for k, v in catalog.items()}
    reports: List[BinaryEsmReport] = []
    inspected_names: Set[str] = set()

    for p in esm_paths:
        rep = inspect_esm_binary(p)
        reports.append(rep)
        inspected_names.add(rep.plugin_name)
        merged_catalog[rep.plugin_name] = dict(merged_catalog.get(rep.plugin_name, {}))
        merged_catalog[rep.plugin_name].update(rep.own_records)

    # 1. Duplicate EditorID check across all FO4SF plugins and any inspected binary .esm
    edid_owners: Dict[str, List[Tuple[str, int, str]]] = {}
    for plg, recs in sorted(merged_catalog.items()):
        if not (plg.lower().startswith("fo4sf") or plg in inspected_names):
            continue
        for fid, (_rt, edid) in sorted(recs.items()):
            if edid:
                edid_owners.setdefault(edid.lower(), []).append((plg, fid, edid))
    for _, owners in sorted(edid_owners.items()):
        if len({p for p, _, _ in owners}) > 1:
            desc = ", ".join(f"{p}:0x{fid:04X} ({ed})" for p, fid, ed in owners)
            errors.append(f"Binary stage duplicate EditorID across plugins: {desc}")

    # 2. Validate VMAD script & property parity + resolved Object FormIDs
    for rep in reports:
        for vp in rep.vmad_properties:
            sprops = psc_props_by_script.get(vp.script_name.lower())
            if sprops is None:
                errors.append(f"{rep.plugin_name} ({vp.record_edid}): VMAD script {vp.script_name} missing in .psc sources")
                continue
            psc_ptype = sprops.get(vp.prop_name.lower())
            if psc_ptype is None:
                errors.append(
                    f"{rep.plugin_name} ({vp.record_edid}): {vp.script_name} does not declare VMAD property {vp.prop_name}"
                )
                continue
            psc_low = psc_ptype.lower()
            if vp.prop_type in _VMAD_PRIMITIVE_PSC_TYPES:
                want_psc = _VMAD_PRIMITIVE_PSC_TYPES[vp.prop_type]
                if psc_low != want_psc:
                    errors.append(
                        f"{rep.plugin_name} ({vp.record_edid}): {vp.script_name}.{vp.prop_name} VMAD type {vp.prop_type} != .psc {psc_ptype}"
                    )
                continue

            if vp.prop_type == 11 and not psc_low.endswith("[]"):
                errors.append(
                    f"{rep.plugin_name} ({vp.record_edid}): {vp.script_name}.{vp.prop_name} is Object[] in VMAD but {psc_ptype} in .psc"
                )
                continue
            if vp.prop_type == 1 and psc_low.endswith("[]"):
                errors.append(
                    f"{rep.plugin_name} ({vp.record_edid}): {vp.script_name}.{vp.prop_name} is scalar Object in VMAD but {psc_ptype} in .psc"
                )
                continue

            base_ptype = psc_low[:-2] if psc_low.endswith("[]") else psc_low
            expected_types = {"QUST"} if base_ptype.startswith("fo4sf_") else CAST_EXPECTED_TYPES.get(base_ptype, set())
            for alias_id, tgt_plg, tgt_id in vp.object_refs:
                if alias_id >= 0:
                    continue
                if tgt_plg in ("FO4Port.esm", "FO4TerrainCore.esm", "FO4TerrainCore_Mars.esm"):
                    if tgt_id not in merged_catalog.get(tgt_plg, {}):
                        continue
                if (
                    vp.script_name.lower() == "fo4sf_newgamequest"
                    and vp.prop_name.lower() == "holdoff"
                    and tgt_plg == "Starfield.esm"
                    and tgt_id not in merged_catalog.get("Starfield.esm", {})
                ):
                    continue
                if tgt_plg not in merged_catalog or tgt_id not in merged_catalog[tgt_plg]:
                    errors.append(
                        f"{rep.plugin_name} ({vp.record_edid}): {vp.script_name}.{vp.prop_name} -> "
                        f"{tgt_plg}:0x{tgt_id:06X} missing in catalog"
                    )
                    continue
                actual_type, actual_edid = merged_catalog[tgt_plg][tgt_id]
                if expected_types and actual_type not in expected_types:
                    errors.append(
                        f"{rep.plugin_name} ({vp.record_edid}): {vp.script_name}.{vp.prop_name} ({psc_ptype}) -> "
                        f"{tgt_plg}:0x{tgt_id:06X} ({actual_edid}) has wrong record type {actual_type}"
                    )

        # 3. Validate cross-plugin FO4SF* item/base references in CNTO and placed REFR/ACHR
        for ctx, tgt_plg, tgt_id in rep.cross_plugin_item_refs:
            if not tgt_plg.lower().startswith("fo4sf"):
                continue
            if tgt_plg not in merged_catalog or tgt_id not in merged_catalog[tgt_plg]:
                errors.append(f"{rep.plugin_name} ({ctx}): unresolved cross-plugin ref {tgt_plg}:0x{tgt_id:06X}")

    return errors


# ---------------------------------------------------------------------------
# Rule R13: Native C++ plugin shared value lookup table & C++ source validator
# ---------------------------------------------------------------------------

CPP_RTTI_TO_RECORD_TYPE: Dict[str, str] = {
    "ActorValueInfo@@": "AVIF",
    "TESGlobal@@": "GLOB",
    "AlchemyItem@@": "ALCH",
    "TESQuest@@": "QUST",
}

NATIVE_CPP_DIRS: Tuple[str, ...] = (
    "sfse/FO4SFPipboyMenu/src",
    "sfse/FO4SFCombat/src",
)


@dataclass(frozen=True)
class NativeCoreValueSpec:
    cpp_rel: str
    const_name: str
    plugin: str
    local_id: int
    record_type: str
    edid: str
    count: int = 1


NATIVE_CORE_VALUE_SPECS: Tuple[NativeCoreValueSpec, ...] = (
    NativeCoreValueSpec(
        "sfse/FO4SFPipboyMenu/src/main.cpp",
        "kRadsLocalId",
        "FO4SFCoreValues.esm",
        0x000800,
        "AVIF",
        "FO4SF_Rads",
    ),
    NativeCoreValueSpec(
        "sfse/FO4SFPipboyMenu/src/main.cpp",
        "kCoreRadResistLocalId",
        "FO4SFCoreValues.esm",
        0x000804,
        "AVIF",
        "FO4SF_RadResist",
    ),
    NativeCoreValueSpec(
        "sfse/FO4SFPipboyMenu/src/main.cpp",
        "kCoreSpecialFirstLocalId",
        "FO4SFCoreValues.esm",
        0x000810,
        "AVIF",
        "FO4SF_Special_Strength",
        count=7,
    ),
    NativeCoreValueSpec(
        "sfse/FO4SFPipboyMenu/src/main.cpp",
        "kCoreHardcoreFastTravelBlockedId",
        "FO4SFCoreValues.esm",
        0x000841,
        "GLOB",
        "FO4SF_HardcoreFastTravelBlocked",
    ),
    NativeCoreValueSpec(
        "sfse/FO4SFPipboyMenu/src/pipboy_map.cpp",
        "kCoreHardcoreFastTravelBlockedId",
        "FO4SFCoreValues.esm",
        0x000841,
        "GLOB",
        "FO4SF_HardcoreFastTravelBlocked",
    ),
    NativeCoreValueSpec(
        "sfse/FO4SFPipboyMenu/src/main.cpp",
        "kCoreStimpakLocalId",
        "FO4SFCoreValues.esm",
        0x000851,
        "ALCH",
        "FO4SF_Stimpak",
    ),
    NativeCoreValueSpec(
        "sfse/FO4SFPipboyMenu/src/main.cpp",
        "kCorePipboyAcquiredId",
        "FO4SFCoreValues.esm",
        0x000865,
        "GLOB",
        "FO4SF_PipboyAcquired",
    ),
    NativeCoreValueSpec(
        "sfse/FO4SFPipboyMenu/src/main.cpp",
        "kCoreStartCardOpenId",
        "FO4SFCoreValues.esm",
        0x000866,
        "GLOB",
        "FO4SF_StartCardOpen",
    ),
    NativeCoreValueSpec(
        "sfse/FO4SFPipboyMenu/src/main.cpp",
        "kCoreGameModeId",
        "FO4SFCoreValues.esm",
        0x000870,
        "GLOB",
        "FO4SF_GameMode",
    ),
    NativeCoreValueSpec(
        "sfse/FO4SFPipboyMenu/src/main.cpp",
        "kCoreSurvivalStartId",
        "FO4SFCoreValues.esm",
        0x000871,
        "GLOB",
        "FO4SF_SurvivalStart",
    ),
    NativeCoreValueSpec(
        "sfse/FO4SFPipboyMenu/src/main.cpp",
        "kCoreSurvivalLockedId",
        "FO4SFCoreValues.esm",
        0x000872,
        "GLOB",
        "FO4SF_SurvivalLocked",
    ),
    NativeCoreValueSpec(
        "sfse/FO4SFPipboyMenu/src/main.cpp",
        "kCoreStartDifficultyId",
        "FO4SFCoreValues.esm",
        0x000873,
        "GLOB",
        "FO4SF_StartDifficulty",
    ),
    NativeCoreValueSpec(
        "sfse/FO4SFPipboyMenu/src/main.cpp",
        "kCoreWarfareFactionId",
        "FO4SFCoreValues.esm",
        0x000874,
        "GLOB",
        "FO4SF_WarfareFaction",
    ),
    NativeCoreValueSpec(
        "sfse/FO4SFPipboyMenu/src/main.cpp",
        "kCoreWarfareStartIndexId",
        "FO4SFCoreValues.esm",
        0x000875,
        "GLOB",
        "FO4SF_WarfareStartIndex",
    ),
    NativeCoreValueSpec(
        "sfse/FO4SFPipboyMenu/src/main.cpp",
        "kCoreStartChoiceDoneId",
        "FO4SFCoreValues.esm",
        0x000876,
        "GLOB",
        "FO4SF_StartChoiceDone",
    ),
    NativeCoreValueSpec(
        "sfse/FO4SFPipboyMenu/src/main.cpp",
        "kCoreStoryLineId",
        "FO4SFCoreValues.esm",
        0x000878,
        "GLOB",
        "FO4SF_StoryLine",
    ),
    NativeCoreValueSpec(
        "sfse/FO4SFPipboyMenu/src/main.cpp",
        "kCoreStartPlaceRowId",
        "FO4SFCoreValues.esm",
        0x000879,
        "GLOB",
        "FO4SF_StartPlaceRow",
    ),
    NativeCoreValueSpec(
        "sfse/FO4SFPipboyMenu/src/main.cpp",
        "kCoreSpecialMenuPendingFirstId",
        "FO4SFCoreValues.esm",
        0x000880,
        "GLOB",
        "FO4SF_SpecialMenuPendingS",
        count=7,
    ),
    NativeCoreValueSpec(
        "sfse/FO4SFPipboyMenu/src/main.cpp",
        "kCoreSpecialMenuCommitReqId",
        "FO4SFCoreValues.esm",
        0x000887,
        "GLOB",
        "FO4SF_SpecialMenuCommitRequested",
    ),
)


@dataclass(frozen=True)
class CppPluginFormRef:
    cpp_rel: str
    line_no: int
    plugin: str
    local_id: int
    rtti_name: str
    paired_edid: str = ""


def _strip_cpp_comments(cpp_text: str) -> str:
    no_block = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), cpp_text, flags=re.S)
    return re.sub(r"//[^\n]*", "", no_block)


def parse_cpp_plugin_form_refs(cpp_rel: str, cpp_text: str) -> Tuple[Dict[str, int], List[CppPluginFormRef]]:
    """Parse C++ `uint32_t` FormID constants and `KitFileForm` / plugin-local FormID lookups in `cpp_text`."""
    clean = _strip_cpp_comments(cpp_text)
    uint_consts: Dict[str, int] = {}
    str_vars: Dict[str, str] = {}

    for m in re.finditer(r"\bconstexpr\s+(?:std::)?uint32_t\s+(\w+)\s*=\s*([^;]+);", clean):
        val = _parse_int_literal(m.group(2).strip(), uint_consts)
        if val is not None:
            uint_consts[m.group(1)] = val

    for m in re.finditer(r'\b(?:constexpr\s+auto|std::string(?:_view)?)\s+(\w+)\s*=\s*"([^"]+\.esm)"(?:sv)?;', clean):
        str_vars[m.group(1)] = m.group(2)

    # Also resolve local aliases such as `const std::uint32_t spLocalId = kCoreSpecialFirstLocalId + ...;`
    local_aliases: Dict[str, int] = dict(uint_consts)
    for m in re.finditer(r"\bconst\s+(?:std::)?uint32_t\s+(\w+)\s*=\s*([^;]+);", clean):
        expr = re.sub(r"static_cast<[^>]+>\(([^)]+)\)", r"\1", m.group(2).strip())
        val = _parse_int_literal(expr, local_aliases)
        if val is not None:
            local_aliases[m.group(1)] = val

    refs: List[CppPluginFormRef] = []
    # Match multi-line KitFileForm(pluginExpr, idExpr, "RTTI@@", ...) calls
    for km in re.finditer(
        r'KitFileForm\(\s*("[^"]+"|[A-Za-z_][A-Za-z0-9_.]*)\s*,\s*([^,]+?)\s*,\s*"([^"]+)"',
        clean,
        flags=re.S,
    ):
        plg_raw, id_raw, rtti_name = km.group(1).strip(), km.group(2).strip(), km.group(3).strip()
        if plg_raw.startswith('"') and plg_raw.endswith('"'):
            plugin = plg_raw[1:-1]
        else:
            plugin = str_vars.get(plg_raw, "")
        if not plugin:
            continue

        id_clean = re.sub(r"static_cast<[^>]+>\(([^)]+)\)", r"\1", id_raw)
        fid = _parse_int_literal(id_clean, local_aliases)
        line_no = clean.count("\n", 0, km.start()) + 1
        if fid is None or fid <= 0:
            continue

        # Look immediately ahead (~260 chars) for a paired AcceptById(..., "FO4SF_...", ...) EditorID
        tail = clean[km.end() : km.end() + 260]
        em = re.search(r'AcceptById\([^,]+,\s*"(FO4SF_[A-Za-z0-9_]+)"', tail)
        paired_edid = em.group(1) if em else ""
        refs.append(CppPluginFormRef(cpp_rel, line_no, plugin, fid, rtti_name, paired_edid))

    # Also match ResolvePluginPrefix("FO4SFCoreValues.esm", prefixVar, ...) + LookupPluginGlobal(prefixVar, ..., idExpr)
    prefix_plugins: Dict[str, str] = {}
    for pm in re.finditer(
        r'ResolvePluginPrefix\(\s*("[^"]+"|[A-Za-z_][A-Za-z0-9_]*)\s*,\s*([A-Za-z_][A-Za-z0-9_]*)',
        clean,
    ):
        plg_raw, prefix_var = pm.group(1).strip(), pm.group(2).strip()
        plg = plg_raw[1:-1] if (plg_raw.startswith('"') and plg_raw.endswith('"')) else str_vars.get(plg_raw, "")
        if plg:
            prefix_plugins[prefix_var] = plg

    for lm in re.finditer(
        r"LookupPluginGlobal\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*[^,]+?,\s*([^)]+?)\s*\)",
        clean,
    ):
        prefix_var, id_raw = lm.group(1).strip(), lm.group(2).strip()
        plugin = prefix_plugins.get(prefix_var, "")
        if not plugin:
            continue
        id_clean = re.sub(r"static_cast<[^>]+>\(([^)]+)\)", r"\1", id_raw)
        fid = _parse_int_literal(id_clean, local_aliases)
        line_no = clean.count("\n", 0, lm.start()) + 1
        if fid is None or fid <= 0:
            continue
        tail = clean[lm.end() : lm.end() + 360]
        em = re.search(r"name=(FO4SF_[A-Za-z0-9_]+)", tail)
        paired_edid = em.group(1) if em else ""
        refs.append(CppPluginFormRef(cpp_rel, line_no, plugin, fid, "TESGlobal@@", paired_edid))

    return uint_consts, refs


def validate_native_core_value_refs(
    repo_root: str,
    catalog: Dict[str, Dict[int, Tuple[str, str]]],
    specs: Sequence[NativeCoreValueSpec] = NATIVE_CORE_VALUE_SPECS,
    cpp_overrides: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Validate native C++ plugin lookups against `core_values.json` / `catalog` and `NATIVE_CORE_VALUE_SPECS` (R13)."""
    errors: List[str] = []
    overrides = cpp_overrides or {}

    core_table = catalog.get("FO4SFCoreValues.esm", {})
    core_edid_to_id: Dict[str, Tuple[int, str]] = {
        edid.lower(): (fid, rtype) for fid, (rtype, edid) in core_table.items() if edid
    }

    cpp_texts: Dict[str, str] = {}
    for rel_dir in NATIVE_CPP_DIRS:
        abs_dir = os.path.join(repo_root, *rel_dir.split("/"))
        if not os.path.isdir(abs_dir):
            continue
        for fn in sorted(os.listdir(abs_dir)):
            if fn.endswith(".cpp"):
                rel = f"{rel_dir}/{fn}"
                if rel in overrides:
                    cpp_texts[rel] = overrides[rel]
                else:
                    with open(os.path.join(abs_dir, fn), encoding="utf-8") as handle:
                        cpp_texts[rel] = handle.read()
    for rel, txt in overrides.items():
        cpp_texts.setdefault(rel, txt)

    parsed_by_file: Dict[str, Tuple[Dict[str, int], List[CppPluginFormRef]]] = {
        rel: parse_cpp_plugin_form_refs(rel, txt) for rel, txt in sorted(cpp_texts.items())
    }

    registered_core_ids: Set[Tuple[str, int]] = set()

    # 1. Validate every entry in the R13 native core-values table against catalog and C++ constants
    for spec in specs:
        plg_table = catalog.get(spec.plugin)
        if plg_table is None:
            errors.append(f"{spec.cpp_rel}:{spec.const_name} references unknown plugin {spec.plugin}")
            continue

        for off in range(spec.count):
            fid = spec.local_id + off
            if spec.plugin == "FO4SFCoreValues.esm":
                registered_core_ids.add((spec.cpp_rel, fid))
            if fid not in plg_table:
                errors.append(
                    f"{spec.cpp_rel}:{spec.const_name} -> {spec.plugin}:0x{fid:06X} ({spec.edid}) missing in writer table"
                )
                continue
            actual_type, actual_edid = plg_table[fid]
            if actual_type != spec.record_type:
                errors.append(
                    f"{spec.cpp_rel}:{spec.const_name} -> {spec.plugin}:0x{fid:06X} is {actual_type}, expected {spec.record_type}"
                )
            if off == 0 and actual_edid != spec.edid:
                errors.append(
                    f"{spec.cpp_rel}:{spec.const_name} -> {spec.plugin}:0x{fid:06X} is '{actual_edid}', expected '{spec.edid}'"
                )

        if spec.cpp_rel not in parsed_by_file:
            errors.append(f"native C++ source file missing for R13 check: {spec.cpp_rel}")
            continue
        consts, _ = parsed_by_file[spec.cpp_rel]
        if spec.const_name not in consts:
            errors.append(f"{spec.cpp_rel}: missing C++ constant {spec.const_name}")
        elif consts[spec.const_name] != spec.local_id:
            errors.append(
                f"{spec.cpp_rel}: C++ constant {spec.const_name}=0x{consts[spec.const_name]:06X} "
                f"!= R13 table 0x{spec.local_id:06X} ({spec.edid})"
            )

    # 2. Validate every actual C++ plugin lookup call-site (catches wrong, missing, untracked, or split IDs)
    for rel, (_, refs) in sorted(parsed_by_file.items()):
        for ref in refs:
            if ref.plugin not in catalog:
                errors.append(
                    f"{ref.cpp_rel}:{ref.line_no} native lookup references unknown plugin '{ref.plugin}' (0x{ref.local_id:06X})"
                )
                continue
            plg_table = catalog[ref.plugin]
            if ref.local_id not in plg_table:
                errors.append(
                    f"{ref.cpp_rel}:{ref.line_no} native lookup {ref.plugin}:0x{ref.local_id:06X} missing in writer table"
                )
                continue

            actual_type, actual_edid = plg_table[ref.local_id]
            expected_type = CPP_RTTI_TO_RECORD_TYPE.get(ref.rtti_name)
            if expected_type and actual_type != expected_type:
                errors.append(
                    f"{ref.cpp_rel}:{ref.line_no} native lookup {ref.plugin}:0x{ref.local_id:06X} ({actual_edid}) "
                    f"is {actual_type}, incompatible with RTTI {ref.rtti_name} ({expected_type})"
                )

            if ref.plugin == "FO4SFCoreValues.esm" and (ref.cpp_rel, ref.local_id) not in registered_core_ids:
                errors.append(
                    f"{ref.cpp_rel}:{ref.line_no} native lookup FO4SFCoreValues.esm:0x{ref.local_id:06X} ({actual_edid}) "
                    f"is missing from NATIVE_CORE_VALUE_SPECS"
                )

            if ref.paired_edid:
                ed_low = ref.paired_edid.lower()
                if ed_low in core_edid_to_id:
                    core_fid, _ = core_edid_to_id[ed_low]
                    if ref.plugin != "FO4SFCoreValues.esm" or ref.local_id != core_fid:
                        errors.append(
                            f"{ref.cpp_rel}:{ref.line_no} split native lookup for {ref.paired_edid}: "
                            f"owned by FO4SFCoreValues.esm:0x{core_fid:06X}, but C++ reads {ref.plugin}:0x{ref.local_id:06X}"
                        )
                elif actual_edid and actual_edid.lower() != ed_low:
                    errors.append(
                        f"{ref.cpp_rel}:{ref.line_no} native lookup EditorID mismatch: C++ expects {ref.paired_edid}, "
                        f"but {ref.plugin}:0x{ref.local_id:06X} is {actual_edid}"
                    )

            if ref.plugin != "FO4SFCoreValues.esm" and actual_edid and actual_edid.lower() in core_edid_to_id:
                core_fid, _ = core_edid_to_id[actual_edid.lower()]
                errors.append(
                    f"{ref.cpp_rel}:{ref.line_no} split native lookup: {actual_edid} belongs to "
                    f"FO4SFCoreValues.esm:0x{core_fid:06X}, not {ref.plugin}:0x{ref.local_id:06X}"
                )

    return errors
