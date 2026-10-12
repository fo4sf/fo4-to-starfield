"""Map one exported Fallout 4 actor to Starfield NPC_ specs, and plan its npc_nav tests (docs/actors/raider-conversion.md).

  python raider_map.py spec  --fo4 <export-fo4 json> --out <spec.json> [--table <mapping.md>] [--form-id F04800]
  python raider_map.py plans --stage <actor staging dir> --n2a <exp dir> --n2b <exp dir> --n2a-queue <queue dir>
                             [--slot 02]
  python raider_map.py check-queue --plan <exp dir>\\plan.json --queue <queue dir>

`spec` reads what `dotnet/ActorRaider export-fo4` wrote (the placed actor, its base, and per template category the record
that category resolves to at the encounter level) and writes the input of `ActorRaider write`: the conversion and a calm
probe, the same record without factions. Every Starfield link in the spec carries FormID, EditorID and record type; the
writer refuses to write when Starfield.esm disagrees.

The record keeps what makes it this Fallout 4 actor (name, faction intent, weapon, death loot, combat style intent) and
inherits native Starfield behaviour (traits, stats, AI data and packages, attack data, keywords, scripts) from a vanilla
Spacer template through the template flags, so the game runs it like its own actor. `plans` writes the npc_nav plan.json
of runs N2a (the calm probe walks on command, against N0's citizen) and N2b (the hostile conversion comes for the player
on its own, against the vanilla Spacer); scripts/game/testqueue.py plan-npc, PR #68 format. `check-queue` fails when a
planned queue lost a key of its plan.json (an older testqueue.py drops keys it does not know).
"""
import argparse
import json
import os
import sys


def sf(fid, edid, rtype):
    """A Starfield.esm link as the writer validates it."""
    return {"id": fid, "edid": edid, "type": rtype}


# Starfield.esm records used by the mapping (each read with dotnet/ActorRaider sf-dump / sf-find, Starfield.esm of
# 2026-10-03; the writer re-checks FormID, EditorID and type on every run)
HUMAN_RACE = sf("0000347D", "HumanRace", "Race")
ENC_SPACER_01 = sf("00270255", "EncSpacer01Template", "Npc")          # LCharSpacer entry 1 (level 1 of 10), NpcLevel 8
SPACER_FACES_M = [sf("0027BB78", "EncSpacerFaceM01", "Npc"), sf("0027BB77", "EncSpacerFaceM02", "Npc"),
                  sf("0027BB76", "EncSpacerFaceM03", "Npc"), sf("0027BB75", "EncSpacerFaceM04", "Npc")]
SPACER_FACES_F = [sf("0027BB7A", "EncSpacerFaceF01", "Npc"), sf("0027BB79", "EncSpacerFaceF02", "Npc"),
                  sf("000FEA4C", "EncSpacerFaceF03", "Npc")]
SPACER_FACTION = sf("0027BB8C", "SpacerFaction", "Faction")            # Enemy to PlayerFaction 01C21C
GROUP_SPACERS = sf("0004CE26", "GroupFactionSpacers", "Faction")
CS_SPACER_ASSAULT = sf("002C562D", "csSpacer_Assault", "CombatStyle")
COACHMAN = sf("0026D96B", "Coachman", "Weapon")                        # double barrel; NpcsUseAmmo False
LLD_SPACER = sf("0027BB74", "LLD_Spacer", "LeveledItem")
OUTFIT_TANKTOP_BROWN = sf("0005B422", "Outfit_Clothes_Mechanic_Tanktop_Brown", "Outfit")
OUTFIT_SPACESUIT_SPACER = sf("003D094D", "Outfit_Spacesuit_Spacer_AssaultOrNoRole", "Outfit")
DEFAULT_MASTER_HUMAN = sf("002C55CA", "DefaultMasterPackageList_Human", "FormList")
DEFAULT_COMBAT_MASTER = sf("000102ED", "DefaultCombatMasterPackageList", "FormList")
SPACER_MALE_01 = sf("002BCA3E", "SpacerMale01", "VoiceType")           # EncSpacerFaceM01's voice
CRIMSON_FLEET_CLASS = sf("00010B2F", "CrimsonFleetClass", "Class")      # EncSpacer01Template's class
# templated vanilla NPC_ records still carry the inherited voice and class (LvlSpacer_Male: VTCK SpacerMale01, CNAM
# CrimsonFleetClass with Traits and Stats templated); the record does the same instead of writing null links
TEMPLATE_VALUES = {"EncSpacerFaceM01": {"voice": SPACER_MALE_01}, "EncSpacer01Template": {"class": CRIMSON_FLEET_CLASS}}

# Fallout 4 -> Starfield, keyed by Fallout 4 EditorID (FormIDs of the two games are unrelated)
RACES = {"HumanRace": HUMAN_RACE}
# the faction ladder: FO4 LCharRaider (7 tiers, EncRaider01Template at level 1) and Starfield LCharSpacer (10 tiers,
# EncSpacer01Template at level 1) have the same shape; tier 1 maps to tier 1 and takes the Starfield tier's level
TIERS = {"EncRaider01Template": (ENC_SPACER_01, 8)}
FACTIONS = {"RaiderFaction": [SPACER_FACTION, GROUP_SPACERS]}
FORMATION = {"RaiderFaction": GROUP_SPACERS}
COMBAT_STYLES = {"csRaiderRanged": CS_SPACER_ASSAULT}
WEAPONS = {"LL_DoubleBarrelShotgun": COACHMAN}        # LL_HandmadeGun (pipe guns): no Starfield analog chosen
DEATH_ITEMS = {"LLD_Raider": LLD_SPACER}
OUTFITS = {"Outfit_Raider": OUTFIT_TANKTOP_BROWN}     # placeholder look; spacers have no default outfit
PACKAGE_LISTS = {"DefaultMasterPackageList": DEFAULT_MASTER_HUMAN,
                 "DefaultCombatMasterPackageList": DEFAULT_COMBAT_MASTER}
FLAGS = {"Respawn": "Respawn", "Essential": "Essential", "Protected": "Protected", "Unique": "Unique"}

# ACBS template categories: inherited from the Spacer templates (native behaviour) or the record's own (the Fallout 4
# identity). Unknown1 / Unknown2 are Starfield's template slots 13 and 14, unnamed in Mutagen 0.55.0-alpha.67; in
# Starfield.esm they almost always share the behaviour template, never Traits alone (ActorRaider sf-tplstats), so they
# go with it.
INHERIT = ["Traits", "Stats", "SpellList", "AiData", "AiPackages", "Script", "DefPackList", "AttackData", "Keywords",
           "Unknown1", "Unknown2"]
OWN = ["Factions", "BaseData", "Inventory"]
CATEGORY_BITS = {"Traits": 0, "Stats": 1, "Factions": 2, "SpellList": 3, "AiData": 4, "AiPackages": 5,
                 "ModelOrAnimation": 6, "BaseData": 7, "Inventory": 8, "Script": 9, "DefPackList": 10,
                 "AttackData": 11, "Keywords": 12, "Unknown1": 13, "Unknown2": 14}

# every sampled vanilla human NPC_ has these (EncSpacer01Template, EncSpacerFaceM01, LvlSpacer_Male, LvlSpacer)
HUMAN_BOUNDS = [[-0.31, -0.31, 0.0], [0.31, 0.31, 1.8]]
# Raw scan of Starfield.esm (7,131 NPC_): every record has form version 581 (Mutagen writes 576 unless told) and carries
# PRPS, STON, PRON and EDCT, also the 2,821 that inherit Traits. Vanilla templated records carry their template's values,
# so the writer copies PRPS from the Stats template (as 2,692 of 4,046 Stats-templated NPC_ whose template is an NPC_)
# and STON / PRON from the Traits template (2,287 / 2,317 of 2,318); EDCT, the tint count, is 0 (no tints written).
VANILLA_CONSTANTS = {"nam5": "FF00", "geared_up_weapons": 1, "unused": 43, "form_version": 581,
                     "copied": {"properties": "Stats", "skin_tone_index": "Traits", "pronoun": "Traits"}}


class MappingError(ValueError):
    pass


def template_flags(names):
    bits = 0
    for n in names:
        if n not in CATEGORY_BITS:
            raise MappingError(f"unknown template category {n!r}")
        bits |= 1 << CATEGORY_BITS[n]
    return bits


def face_for(edid, female):
    """FO4 encRaiderFace{M,F}<n> -> Starfield EncSpacerFace{M,F}<n>, wrapping at the Starfield count (4 male, 3 female)."""
    tail = edid[len("encRaiderFace"):] if edid.lower().startswith("encraiderface") else ""
    faces = SPACER_FACES_F if female else SPACER_FACES_M
    if len(tail) >= 2 and tail[0].upper() in "MF" and tail[1:].isdigit():
        faces = SPACER_FACES_F if tail[0].upper() == "F" else SPACER_FACES_M
        return faces[(int(tail[1:]) - 1) % len(faces)]
    return faces[0]


def runtime_id(slot, local):
    """Console FormID of a record of a full-master plugin at load slot `slot` (two hex digits)."""
    s = int(str(slot), 16)
    loc = int(str(local), 16)
    if not 1 <= s <= 0xFD or not 0x800 <= loc <= 0xFFFFFF:
        raise MappingError(f"slot {slot} / local id {local} out of range")
    return f"{s:02X}{loc:06X}"


def pick_weapon(items, level):
    """The first weapon entry (at or below the encounter level) of the actor's leveled weapon lists that has a Starfield
    analog, plus a row for every entry looked at."""
    seen = []
    for it in items:
        for e in it.get("entries") or []:
            if e.get("level", 1) > level:
                continue
            seen.append(e["edid"])
            if e["edid"] in WEAPONS:
                return WEAPONS[e["edid"]], e["edid"], seen
    return None, None, seen


def map_npc(fo4, form_id="F04800"):
    """(spec, rows): the writer's spec and the mapping table (FO4 field, FO4 value, Starfield field, value, how)."""
    f, cats, base = fo4["fields"], fo4["categories"], fo4["base"]
    level = int(fo4.get("player_level", 1))
    rows = []

    def row(fo4_field, fo4_val, sf_field, sf_val, how):
        rows.append({"fo4": fo4_field, "fo4_value": fo4_val, "sf": sf_field, "sf_value": sf_val, "how": how})

    stats_src = cats["Stats"]["source"]
    if stats_src not in TIERS:
        raise MappingError(f"no Starfield tier for the Fallout 4 stats template {stats_src!r}")
    tier, tier_level = TIERS[stats_src]
    traits_src = cats["Traits"]["source"]
    face = face_for(traits_src, bool(f.get("female")))
    race = f["race"]["edid"]
    if race not in RACES:
        raise MappingError(f"no Starfield race for {race!r}")

    templates = {"Traits": face}
    templates.update({c: tier for c in INHERIT if c != "Traits"})
    spec = {"role": "conversion", "editor_id": "FO4_" + base["edid"], "form_id": form_id,
            "name": f.get("name") or base["edid"], "level": tier_level,
            "xp_value_offset": int(f.get("xp_value_offset", 0)), "disposition_base": int(f.get("disposition_base", 35)),
            "height": [float(f["height"][0]), float(f["height"][1])], "race": RACES[race],
            "default_template": tier, "templates": templates, "use_template": list(INHERIT),
            "object_bounds": HUMAN_BOUNDS, **json.loads(json.dumps(VANILLA_CONSTANTS))}
    row("EDID", base["edid"], "EditorID", spec["editor_id"], "prefixed")
    row("FULL", f.get("name"), "Name", spec["name"], "copied (English string of the BaseData source)")
    row("RNAM race", race, "Race", RACES[race]["edid"], "mapped (Traits inherit the same race)")
    row("TPLT + TPTA", f"{base['default_template']['edid']} / {cats['Traits']['hops'][0]['via']['edid'] if cats['Traits']['hops'] else '-'}",
        "DefaultTemplate + TemplateActors", f"{tier['edid']} / Traits {face['edid']}",
        f"FO4 at player level {level} resolves to {stats_src} and {traits_src}; mapped tier for tier, no leveled list")

    flags = [FLAGS[x] for x in f.get("flags", []) if x in FLAGS]
    spec["flags"] = flags
    row("ACBS flags", ", ".join(f.get("flags", [])), "Flags", ", ".join(flags) or "-",
        "kept where Starfield has the flag; AutoCalcStats goes with the inherited Stats")
    lv = f.get("level") or {}
    row("ACBS level", lv.get("level", lv.get("pc_level_mult")), "Level", tier_level,
        f"tier 1 -> tier 1: {tier['edid']}'s level (Stats inherited from it)")

    factions = []
    for fa in f.get("factions", []):
        targets = FACTIONS.get(fa["edid"])
        if not targets:
            row("SNAM faction", fa["edid"], "Factions", "-", "dropped: no Starfield equivalent in the table")
            continue
        for t in targets:
            factions.append({"faction": t, "rank": int(fa.get("rank", 0))})
        row("SNAM faction", f"{fa['edid']} rank {fa.get('rank', 0)}", "Factions",
            " + ".join(t["edid"] for t in targets), "mapped (hostility: SpacerFaction is Enemy to PlayerFaction)")
        if fa["edid"] in FORMATION:
            spec["formation_faction"] = FORMATION[fa["edid"]]
    if not factions:
        raise MappingError("no faction mapped: the actor would have no allegiance")
    spec["factions"] = factions

    weapon, wsrc, seen = pick_weapon(f.get("items", []), level)
    if weapon is None:
        raise MappingError(f"no weapon with a Starfield analog among {seen}")
    spec["items"] = [{"item": weapon, "count": 1}]
    row("CNTO weapons", " / ".join(seen), "Items", f"{weapon['edid']} x1",
        f"{wsrc}: same weapon type (double barrel). No ammo given: supported hypothesis that an NPC needs none "
        "(NpcsUseAmmo False in the WEAP, verified; 74 of 84 vanilla NPC_ with a WEAP directly in CNTO carry no AMMO, "
        "the companions among them)")
    weapon_lists = {it["edid"] for it in f.get("items", []) if any(e["edid"] in WEAPONS for e in it.get("entries") or [])}
    others = [it["edid"] for it in f.get("items", []) if it["edid"] not in weapon_lists]
    if others:
        row("CNTO other", ", ".join(others), "Items", "-", "dropped (loot comes from the death item)")

    def one(key, table, fo4_field, sf_label, note=""):
        src = (f.get(key) or {}).get("edid") or ""
        if src and src in table:
            spec[key] = table[src]
            row(fo4_field, src, sf_label, table[src]["edid"], "mapped" + note)
        elif src:
            row(fo4_field, src, sf_label, "-", "dropped: no equivalent in the table")

    # Which template category owns INAM and ZNAM in Starfield is unresolved. In the template semantics xEdit documents
    # for Skyrim and Fallout 4 (same CK lineage; a supported hypothesis for Starfield) the death item goes with Traits
    # and the combat style with AI Data, both inherited here: the written values may be overridden.
    one("death_item", DEATH_ITEMS, "INAM death item", "DeathItem",
        f"; written, but probably overridden (supported hypothesis): the death item goes with Traits, inherited from "
        f"{face['edid']}, which has none, so the effective death item may be none. Vanilla LvlSpacer has the same "
        f"shape (own LLD_Spacer, Traits from faces without one)")
    one("default_outfit", OUTFITS, "DOFT outfit", "DefaultOutfit", " (placeholder look)")
    spec["space_outfit"] = OUTFIT_SPACESUIT_SPACER
    row("(none)", "-", "SpaceOutfit", OUTFIT_SPACESUIT_SPACER["edid"], "added: what the Spacer templates wear")
    one("combat_style", COMBAT_STYLES, "ZNAM combat style", "CombatStyle",
        f"; written, but probably taken from AI Data (supported hypothesis), inherited from {tier['edid']}, whose "
        f"combat style is the same csSpacer_Assault (verified), so the effective value is the same either way")
    one("default_package_list", PACKAGE_LISTS, "DPLT", "DefaultPackageList", " (DefPackList inherited: the same list)")
    one("combat_override_package_list", PACKAGE_LISTS, "ECOR", "CombatOverridePackageList")

    ai = f.get("ai", {})
    row("AIDT", ", ".join(f"{k} {v}" for k, v in ai.items()), "Aggression...", "inherited",
        f"from {tier['edid']} (Starfield spacers: Unaggressive, Brave + reaction radii RDSA; hostility via the faction)")
    for src, vals in ((face, TEMPLATE_VALUES.get(face["edid"], {})), (tier, TEMPLATE_VALUES.get(tier["edid"], {}))):
        spec.update(vals)
    row("VTCK voice", (f.get("voice") or {}).get("edid"), "Voice", (spec.get("voice") or {}).get("edid", "inherited"),
        f"inherited from {face['edid']} (Traits); the same value written, as vanilla templated NPC_ do")
    row("CNAM class", (f.get("class") or {}).get("edid"), "Class", (spec.get("class") or {}).get("edid", "inherited"),
        f"inherited from {tier['edid']} (Stats); the same value written")
    row("PRPS actor values", f"{len(f.get('properties', []))} values", "Properties", f"{tier['edid']}'s, copied",
        "inherited with Stats; written too, because every vanilla NPC_ carries PRPS (7,131 of 7,131), as a copy of the "
        "Stats template's (as 2,692 of 4,046 vanilla Stats-templated NPC_ do)")
    row("(none)", "-", "STON skin tone, PRON pronoun, EDCT tint count", f"{face['edid']}'s, copied; EDCT 0",
        "in every vanilla NPC_; STON / PRON as the Traits template's (2,287 / 2,317 of 2,318 vanilla), EDCT 0: no tint "
        "blocks written (the look is inherited)")
    row("PRKR perks", ", ".join(p["edid"] for p in f.get("perks", [])) or "-", "Perks", "inherited", "")
    row("KWDA", ", ".join(k["edid"] for k in f.get("keywords", [])) or "-", "Keywords", "inherited", "")
    row("PNAM head parts, face", f"{f.get('head_parts', 0)} head parts", "HeadParts, Tints, morphs", "inherited",
        f"from {face['edid']}: placeholder appearance")
    return spec, rows


def table_md(rows):
    out = ["| Fallout 4 | value | Starfield | value | how |", "|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['fo4']} | {r['fo4_value']} | {r['sf']} | {r['sf_value']} | {r['how']} |")
    return "\n".join(out) + "\n"




def calm_probe(npc, form_id=None):
    """The conversion without its factions (and formation faction): nothing left gives it an Enemy relation to the
    player, so a walk can be credited to a command. Everything else (templates, flags, inventory, copied values) is the
    conversion's. Used by N2a only; the conversion itself is judged in N2b."""
    probe = json.loads(json.dumps(npc))
    probe.update(role="calm_probe", editor_id=npc["editor_id"] + "_Calm", factions=[],
                 form_id=form_id or f"{int(npc['form_id'], 16) + 1:06X}")
    probe.pop("formation_faction", None)
    return probe


# --------------------------------------------------------------------------------------------------- npc_nav plans
QASMOKE = {"travel": "coc QASmoke", "a": [-8, -4, 0], "b": [5, 10, 0], "drop": 0.5, "settle_ms": 1500,
           "reads_s": [0, 3, 8, 15, 30], "radius": 2.5, "min_progress": 5.0}     # exactly N0's (npc_nav_n0 plan.json)
# N2b's one deviation from N0: a hostile actor (the raider, the vanilla Spacer) may step away from the player's feet while
# the runner confirms the handle (game time runs between the console sessions), so the handle may stand up to 3 m from
# A, the judge's spawn_tol, instead of 2 m. It only checks which ref was spawned. N2a's calm probe keeps N0's 2 m.
HOSTILE = {"handle_tol": 3.0}
N0_CITIZEN = "002B211C"           # EncCitizen01Template: N0's actor, whose controls and baseline gate N2a's FAILs
VANILLA_SPACER = ENC_SPACER_01["id"]   # EncSpacer01Template: not templated, the raider's behaviour template
# both N2 runs depend on one unresolved question: does GetIsID <base> confirm a spawned actor whose template chain has no
# leveled list (N0_ptr_lvl asks it for a chain WITH a leveled list)? N2a_base answers it first (its spawn is confirmed or
# not); every other N2 test waits for that and is not run, so no launch is spent, when it is not.
SPAWN_ANSWERED = "DECIDED"         # testqueue.py requires verdict: PASS or FAIL, i.e. the spawn was confirmed and read


def plans(raider_id, probe_id, n2a_queue):
    """(n2a, n2b) plan.json lists.

    N2a, navigation of the converted record: the calm probe (the conversion without factions) with N0's methods in
    QASmoke. A calm actor is what N0's citizen is, so N0's controls (same method) and baseline gate its FAILs
    (control_npc), and its own baseline (N2a_base, no command) shows whether a PASS is the command's doing.

    N2b, hostility of the converted record: the conversion and the vanilla Spacer template it inherits its behaviour
    from, both without a command (baselines, judged from the spawn read so an approach before the reads counts). The
    vanilla Spacer is the reference: hostility carried over when both come for the player."""
    def test(label, npc, method, expect, basis, **kw):
        return {"label": label, "npc": npc, "method": method, **QASMOKE, "control": False, "expect": expect,
                "basis": basis, **kw}
    first = {"test": "N2a_base", "verdict": SPAWN_ANSWERED}              # same queue (no "queue" key)
    probe = (f"the calm probe {probe_id} is the conversion without factions (no Enemy relation to the player; AI data "
             f"inherited from EncSpacer01Template: Unaggressive, verified)")
    n2a = [
        test("N2a_base", probe_id, "none", "PASS",
             f"supported hypothesis: {probe}, so nothing brings it to the player without a command. Its spawn answers "
             "the GetIsID question for a direct NPC_ template chain (unresolved: INCONCLUSIVE SPAWN with GetIsID 0 "
             "while GetSelf names PickLastRef's ref = GetIsID does not confirm it)"),
        test("N2a_ptr", probe_id, "ptr_player", "PASS",
             "verified: the QASmoke navmesh covers A and B (PR #61 3.1); supported hypothesis: the converted record "
             "walks on command like N0's citizen (its control, gated with N0_base)", control_npc=N0_CITIZEN,
             requires=first),
        test("N2a_cf", probe_id, "cf_pathto_player", "PASS",
             "verified: the QASmoke navmesh covers A and B; supported hypothesis: as N2a_ptr, the cf syntax settled by "
             "N0_cf, its control", control_npc=N0_CITIZEN, requires=first),
        test("N2a_follow", probe_id, "follow_player", "PASS",
             "supported hypothesis: SetPlayerTeammate makes the calm probe follow as it makes N0's citizen follow "
             "(N0_follow, its control); no claim about a hostile actor", control_npc=N0_CITIZEN, requires=first),
    ]
    hostile = ("SpacerFaction is Enemy to PlayerFaction (verified in Starfield.esm) and the Spacer AI data with its "
               "reaction radii is inherited")
    n2b = [
        test("N2b_spacer_base", VANILLA_SPACER, "none", "FAIL WANDER",
             "supported hypothesis: a vanilla Spacer (SpacerFaction is Enemy to PlayerFaction, verified) comes for the "
             "player without a command; the reference for N2b_base. PASS (stayed away) = the approach rule does not "
             "show hostility here (it may shoot from range), so N2b_base says nothing either", **HOSTILE),
        test("N2b_base", raider_id, "none", "FAIL WANDER",
             f"supported hypothesis: {hostile}, so the conversion comes for the player like the vanilla Spacer. PASS "
             "while N2b_spacer_base came = the hostility or the pursuit did not carry over",
             requires=dict(first, queue=n2a_queue), **HOSTILE),
    ]
    return n2a, n2b


def check_queue(plan_path, queue_path):
    """Problems (empty: fine) of a planned queue against its plan.json: every planned test is there, under its label,
    with the npc, method and every gating key the plan gave it. testqueue.py of a checkout without this branch silently
    drops keys it does not know (control_npc, a same-queue requires), which turns every FAIL into INCONCLUSIVE CONTROL
    or runs a test whose precondition was meant to hold it back."""
    with open(plan_path, encoding="utf-8") as fh:
        plan = json.load(fh)
    plan = plan.get("tests") if isinstance(plan, dict) else plan
    with open(os.path.join(queue_path, "queue.json"), encoding="utf-8") as fh:
        q = json.load(fh)
    by_label = {t.get("ref"): t for t in q.get("tests", [])}
    ids = {t.get("ref"): t.get("id") for t in q.get("tests", [])}
    problems = []
    for w in plan:
        t = by_label.get(w["label"])
        if t is None:
            problems.append(f"{w['label']}: not in the queue")
            continue
        for k in ("npc", "control_npc"):
            if w.get(k) and str(t.get(k) or "").upper() != str(w[k]).upper():
                problems.append(f"{w['label']}: {k} {t.get(k)!r}, the plan says {w[k]!r}")
        for k in ("method", "handle_tol", "expect"):
            if k in w and t.get(k) != w[k]:
                problems.append(f"{w['label']}: {k} {t.get(k)!r}, the plan says {w[k]!r}")
        r = w.get("requires")
        if r:
            got = t.get("requires") or {}
            same_q = not r.get("queue")
            want_q = os.path.normcase(os.path.abspath(queue_path if same_q else r["queue"]))
            want_t = ids.get(r["test"], r["test"]) if same_q else None
            if os.path.normcase(got.get("queue") or "") != want_q or got.get("verdict") != r.get("verdict", "PASS") \
                    or (want_t and got.get("test") != want_t) or not got.get("test"):
                problems.append(f"{w['label']}: requires {got or None}, the plan says {r}")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("spec")
    s.add_argument("--fo4", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--table", default="")
    s.add_argument("--plugin", default="FO4ActorRaider.esm")
    s.add_argument("--form-id", default="F04800")
    p = sub.add_parser("plans")
    p.add_argument("--stage", required=True, help="the actor staging dir (holds spec.json)")
    p.add_argument("--n2a", required=True)
    p.add_argument("--n2b", required=True)
    p.add_argument("--n2a-queue", required=True, help="the queue dir N2a is planned into (N2b_base waits for its base)")
    p.add_argument("--slot", default="02", help="load slot of the plugin (first line of Plugins.txt: 02)")
    c = sub.add_parser("check-queue")
    c.add_argument("--plan", required=True)
    c.add_argument("--queue", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "spec":
        with open(a.fo4, encoding="utf-8") as fh:
            fo4 = json.load(fh)
        try:
            npc, rows = map_npc(fo4, a.form_id)
        except MappingError as e:
            sys.exit(f"mapping failed: {e}")
        probe = calm_probe(npc)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"plugin": a.plugin, "source": {"achr": fo4["achr"], "base": fo4["base"]}, "npcs": [npc, probe],
                       "rows": rows}, fh, indent=1)
        if a.table:
            with open(a.table, "w", encoding="utf-8") as fh:
                fh.write(table_md(rows))
        print(f"{npc['editor_id']} ({a.plugin}:{npc['form_id']}) + {probe['editor_id']} ({probe['form_id']}): "
              f"{len(rows)} mapping rows -> {a.out}")
        return 0
    if a.cmd == "check-queue":
        problems = check_queue(a.plan, a.queue)
        for x in problems:
            print("  " + x)
        if problems:
            sys.exit(f"{a.queue}: {len(problems)} problems against {a.plan} (plan it from a checkout with "
                     "claude/actor-raider's testqueue.py)")
        print(f"{a.queue}: every test of {a.plan} planned with its keys")
        return 0
    with open(os.path.join(a.stage, "spec.json"), encoding="utf-8") as fh:
        spec = json.load(fh)
    role = {n.get("role"): n for n in spec["npcs"]}
    rid = runtime_id(a.slot, role["conversion"]["form_id"])
    pid = runtime_id(a.slot, role["calm_probe"]["form_id"])
    n2a, n2b = plans(rid, pid, os.path.abspath(a.n2a_queue))
    for d, tests in ((a.n2a, n2a), (a.n2b, n2b)):
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "plan.json"), "w", encoding="utf-8") as fh:
            json.dump(tests, fh, indent=1)
        print(f"{len(tests)} tests -> {os.path.join(d, 'plan.json')} (raider {rid}, calm probe {pid})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
