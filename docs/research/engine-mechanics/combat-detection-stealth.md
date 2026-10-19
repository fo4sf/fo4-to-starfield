# Combat, detection and stealth (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved.

Scope: CSTY combat styles, combat AI, cover, detection (stealth meter, light and sound), aggression / confidence /
assistance (AIDT), morale, fleeing, surrender, legendary enemies, and Starfield's differences. "xEdit" = TES5Edit
dev-4.1.6 `wbDefinitionsFO4.pas` / `wbDefinitionsSF1.pas` / `wbDefinitionsCommon.pas`.

## In short
- **CSTY is a superset in Starfield.** Every FO4 block (general, melee, close range, long range, cover, flight, flags)
  is still there with the same leading fields; Starfield appends fields to most blocks, turns ranged accuracy and
  cover search into structs, and adds tunnel, space-combat blocks and per-block template links (verified, xEdit).
  Verdict: translate field by field, defaults for new fields from a matching Starfield style.
- **AIDT lost its aggro block.** FO4 AIDT = aggression, confidence, energy, morality, mood, assistance, plus aggro
  radius behaviour and warn / warn-attack / attack radii. Starfield AIDT keeps the six values plus one "Has Reaction
  Radius Behavior" byte; the radii moved to the NPC_ RDSA array, and fleeing has its own FLEE block (verified,
  xEdit). Verdict: rebuild aggro radii as RDSA entries, or inherit RDSA from a Starfield template (what the raider
  does).
- **Hostility source differs** (FO4 aggression vs Starfield Enemy relation + RDSA, verified, raider-conversion);
  details in [factions](factions-crime-relationships.md).
- **Detection uses the same condition hooks** (GetDetected, IsSneaking, GetLightLevel, IsInCombat, GetCombatState,
  IsFleeing, GetShouldAttack exist in both condition tables, verified, xEdit), and ACBS bit 6 "Doesn't affect stealth
  meter" is in both. Starfield adds sight and sound detection package lists on NPC_ (RPLD / RPLI). The detection
  formula and its game settings are **unresolved** for both games here.
- **Legendary enemies:** NPC_ LTPT legendary template and LTPC legendary chance exist in both (verified, xEdit).
  Starfield adds a Legendary Item record LGDI (84 in Starfield.esm) and legendary ranks; FO4's legendary effects are
  OMODs with a "Legendary Mod" flag (verified field names). Verdict: translate the actor side; rebuild the effects.

## How Fallout 4 does it

**CSTY (112, verified count; layout verified, xEdit):**

| subrecord | fields |
|---|---|
| CSGD general | offensive mult, defensive mult, group offensive mult, equipment score mults (melee, magic, ranged, shout, unarmed, staff), avoid / dodge / evade threat chance |
| CSMD | unknown (ignored by xEdit) |
| CSME melee | attack / power attack staggered mults, power attack blocking, bash mults, special attack, block / attack when staggered |
| CSRA | ranged accuracy mult (one float) |
| CSCR close range | dueling circle / fallback, flanking distance / stalk time / variance, charging distance and probabilities, throw max targets |
| CSLR long range | strafe, adjust range, crouch, wait, range mults |
| CSCV | cover search distance mult (one float) |
| CSFL flight | hover, dive bomb, ground attack, perch, flying attack chances and times |
| DATA flags | Dueling, Flanking, Allow Dual Wielding, Charging, Retarget Any Nearby Melee Target |

- **Where styles attach:** NPC_ ZNAM (via the AI Data template category, supported hypothesis from xEdit/CK
  lineage, raider-conversion section 3) and PACK CNAM "combat style while this package runs" (verified field;
  falloutck Package page).
- **AIDT** (verified, xEdit `wbAIDT`): Aggression (Unaggressive, Aggressive, Very Aggressive, Frenzied), Confidence
  (Cowardly, Cautious, Average, Brave, Foolhardy), Energy (0-100), Morality (Any Crime, Violence Against Enemies,
  Property Crime Only, No Crime), Mood (Neutral, Angry, Fear, Happy, Sad, Surprised, Puzzled, Disgusted), Assistance
  (Helps Nobody, Helps Allies, Helps Friends and Allies), aggro block (Aggro Radius Behavior bool, Warn, Warn/Attack,
  Attack radii u32), and from form version 29 No Slow Approach.
- **How aggression and assistance act** (falloutck Faction page, verified as documented): Aggressive attacks Enemy;
  Very Aggressive attacks Enemy and Neutral; Frenzied attacks everyone; assistance follows Ally/Friend relations.
- **Examples** (verified): raiders VeryAggressive, Foolhardy, HelpsFriendsAndAllies (raider-conversion section 1);
  Preston Aggressive, Foolhardy, NoCrime, HelpsAllies, combat style `csPreston` (B4 section 2).
- **Cover:** navmesh carries cover data (cover arrays and cover-to-triangle maps, 8-byte raw cover entries in older
  navmesh versions) (verified, xEdit NAVM). CSTY CSCV scales how far actors search for cover.
- **Fleeing and morale:** driven by Confidence against the fight's odds (CE lineage, supported hypothesis); package
  interrupt override "Combat" and NPC_ ECOR combat override list can replace default combat behaviour (verified
  fields).
- **Bleedout / surrender:** ACBS flags Doesn't bleed, Has Bleedout Override, No Bleedout Recovery, Essential,
  Protected (verified, xEdit). Essential actors enter bleedout instead of dying (CE lineage, supported hypothesis).
  A general "surrender" mechanic is not identified in the records (unresolved; FO4 yields are scripted per quest,
  supported hypothesis).
- **Detection and stealth:** HUD stealth states Hidden / Caution / Danger (supported hypothesis, common knowledge,
  no primary source read). Light level, sound, distance and the Sneak skill/Perception feed detection (CE lineage,
  supported hypothesis). Condition functions GetDetected, IsSneaking, GetLightLevel exist (verified, xEdit).
- **Legendary enemies:** NPC_ LTPT (LVLN or NPC_) and LTPC (GLOB) (verified, xEdit). The mid-fight "mutation"
  (heal and power up at low health) and the legendary drop are a supported hypothesis of script plus perk/spell
  logic; which script or quest runs it is unresolved. OMOD flag "Legendary Mod" marks legendary weapon/armour mods
  (verified, xEdit).
- **VATS** is FO4-only as a player system; its condition function GetVatsTargetHeight still exists in Starfield's
  table (verified, xEdit), which says nothing about a working VATS.

## How Starfield does it

**CSTY (161, verified count; layout verified, xEdit SF1):**
- **Same leading fields** in CSGD, CSME, CSCR, CSLR, CSFL; DATA flags 0x01-0x10 unchanged.
- **Appended:** CSGD heal ally distance, jump cost mult, taunt delay mult; CSCR retreat chance and distance mult;
  CSLR provide suppressive fire mult, retreat chance, hide time and distance mult.
- **Restructured:** CSRA is a struct (ranged accuracy mult, throw mult, grenade advanced throwing, flash target, throw
  at group, close range attack chance); CSCV is a struct (cover search distance mult, suppression sensitivity).
- **New blocks:** CSTN tunnel; space combat CSSG, CSSM, CSSR, CSSA, CSSD (pilot skill, maneuvers, repair, detection
  ratings); DATA flags 0x20 Prefer Walking While Strafing, 0x40 Use Group Cohesion, 0x80 Maintain Attack From Cover
  Until Suppressed; TNAM template default combat style and UNAM per-block template links (a style can inherit any
  block from another style).
- **AIDT** (verified, xEdit SF1): same six enums, then "Has Reaction Radius Behavior". **RDSA** entries: reaction type
  (Warn, Warn and Attack, Attack, Curious, Flee, Warn and Alarm), target (Player, Enemies, Neutral, combinations),
  package list, flags (fight back, avoid target, warnings before attack ...), radius / exit radius / timers, each
  value either a float or a GLOB. **FLEE**: flee distance, safe timer, chance of diversion animation (float or
  GLOB).
- **Template slots:** TPTA slots 13 Reaction Radius and 14 Combat Style (xEdit naming, verified as xEdit's), so
  reaction radii and combat style inherit separately from AI Data.
- **Detection:** NPC_ RPLD sound detection and RPLI sight detection package lists (verified, xEdit); HUD shows a
  hidden / detected indicator (supported hypothesis, player guides). Starfield's stealth needs a skill to show the
  meter (supported hypothesis, player guides).
- **Suppression** is a CE2 concept (CSCV suppression sensitivity, the "until suppressed" flag; verified fields); its
  engine behaviour is unresolved.
- **Legendary:** LTPT / LTPC kept; LGDI legendary item records (84, verified count); OMOD "Legendary Mod" flag kept;
  ALLR "Legendary Rank" field exists (verified, xEdit; owning record not traced here).
- **Cover:** navmesh cover entries are 12 bytes in raw form (8 in FO4) (verified, xEdit); converted navmesh already
  handles this in docs/actors/navmesh-conversion.md (not re-checked here).

## Mapping for the port

| FO4 piece | Starfield counterpart | verdict | notes |
|---|---|---|---|
| CSTY CSGD / CSME / CSCR / CSLR / CSFL | same, longer | translate | copy FO4 fields, append Starfield defaults |
| CSRA float | CSRA struct field 1 | translate | other grenade/throw fields from a Starfield style |
| CSCV float | CSCV struct field 1 | translate | suppression sensitivity default |
| CSMD | none | drop | xEdit ignores it |
| DATA flags | same low bits | data copy | new bits 0 |
| (none) | TNAM / UNAM templates, space blocks | leave empty | or template to a Starfield ground style |
| AIDT six values | AIDT six values | data copy | |
| AIDT aggro block | RDSA entries | rebuild | Warn / Warn-Attack / Attack radii to RDSA Warn / Warn and Attack / Attack |
| No Slow Approach | none | drop | |
| Confidence-based fleeing | FLEE + RDSA Flee + CSTY retreat | translate | defaults from a Starfield template |
| ZNAM, PACK CNAM | same | translate | |
| ECOR combat override list | ECOR | translate | |
| LTPT / LTPC | same | translate | legendary NPC templates map 1:1 |
| legendary OMODs | OMOD / LGDI | rebuild | with the weapon/armour converter |
| mutation behaviour | script / perk | script shim | after the Papyrus census |
| stealth meter, detection tuning | Starfield's | keep Starfield | FO4 tuning values unresolved |

## What must be rebuilt, and what needs SFSE or the Creation Kit
- **Aggro radii to RDSA:** the converter writes RDSA entries, or sets the Reaction Radius template slot to a Starfield
  template with the right behaviour (cheap first).
- **Creature combat:** deathclaws, mirelurks and robots need races, attack data and animations; until then Starfield
  stand-ins (next-phase note, section 3).
- **Legendary system:** effects, drops and mutation need the item converter and scripts.
- **VATS:** player system outside this note; would need its own rebuild (SFSE likely, unresolved).
- **FO4 stealth feel:** if Starfield's skill-gated stealth meter must show without the skill, that is a perk/UI change
  (unresolved whether a plugin can do it).

## Port status and links
- Forced combat works for a converted raider: c2 / c4 PASS ENGAGED (verified, B4 section 2 summary of the raider
  ladder); StartCombat / StopCombat compile and run in the mission (verified, next-phase note section 7).
- The raider inherits AI Data, RDSA and combat style csSpacer_Assault from EncSpacer01Template (verified,
  raider-conversion section 3).
- Plan: CSTY "map them, or pick the nearest Starfield style per class (cheap first)"
  ([next-phase note](../next-phase/npcs-ai-factions-dialogue-quests.md), section 4).

## Open questions and cheap checks
- Field defaults: dump csSpacer_Assault and two other Starfield CSTY in xEdit to pick defaults for new fields.
- Aggro usage: count FO4 NPC_ with Aggro Radius Behavior set and their radii (offline scan).
- RDSA patterns: histogram of RDSA reaction types in Starfield.esm NPC_ (offline scan).
- Detection settings: list `fDetection*` / `fSneak*` game settings in both esm files and diff (offline; names
  unverified until listed).
- Legendary mutation: grep the decompiled FO4 scripts for LTPT-related logic once the Papyrus census runs.
- Starfield stealth meter without the skill: one in-game test with a fresh character sneaking.

## Sources
- xEdit: https://github.com/TES5Edit/TES5Edit (dev-4.1.6, `Core/wbDefinitionsFO4.pas`, `wbDefinitionsSF1.pas`,
  `wbDefinitionsCommon.pas`), read locally.
- Fallout 4 CK wiki: https://falloutck.uesp.net/wiki/Faction, https://falloutck.uesp.net/wiki/Package.
- Starfield stealth (player guide, supported hypothesis only):
  https://www.gamerevolution.com/?p=944680, https://www.gamesradar.com/starfield-stealth.
- Repo: docs/actors/raider-conversion.md, docs/spikes/B4-mission-anatomy.md, docs/measurements/*.json,
  ../next-phase/npcs-ai-factions-dialogue-quests.md.
