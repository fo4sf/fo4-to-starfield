# Health, damage and effects (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved.

## In short
- Both games run the same effects pipeline: AVIF actor values, MGEF magic effects (archetypes), SPEL / ENCH / ALCH
  carrying effect items (EFID + EFIT), DMGT damage types bound to resistance AVs, BPTD body parts with per-limb
  condition AVs. Starfield's MGEF archetype list keeps FO4's 0-49 in order (48 Jetpack renamed Boostpack) and adds
  50-55. **verified** (xEdit).
- Layout differences are small but real: EFIT Area is u32 in FO4 and float in Starfield; SPIT Type is u32 in FO4 and
  u8 in Starfield; FO4 DMGT holds an array of (AV, SPEL) pairs, Starfield one pair plus a name. **verified** (xEdit).
- FO4-specific gameplay: AP, Rads reducing max HP, limb crippling, chem addiction/withdrawal, Survival mode needs
  and diseases. Starfield: Oxygen/CO2 instead of AP (supported hypothesis), afflictions (injuries, infections,
  environmental), environmental damage types, optional "Sustenance" gameplay option.
- Verdict: chems, food, stimpaks, damage types **translate** (record-for-record with field fixes); Rads-to-HP and
  limb crippling **translate if the engine hooks still fire** (unresolved); Survival mode **rebuild as a script
  quest** (FO4's is mostly script already, supported hypothesis); Starfield afflictions and environmental hazards are
  **fenced out** or reused deliberately for radiation.

## How Fallout 4 does it
Counts: AVIF 359, MGEF 638, SPEL 326, ENCH 217, ALCH 231, BPTD 40, DMGT 8, HAZD 59, RFCT 41 (**verified**, fo4_esm.json).

| Piece | Records / fields | Label |
|---|---|---|
| Health, AP, Rads | AVIFs (hardcoded); "RadResistIngestion at index 0x29" per xEdit comment; entry points 101 Set Rads To Health Mult, 106 Mod Rads for Rad Health Max, 96 Mod Sprint AP Drain Rate | verified (xEdit) |
| Limbs | BPTD part: Part Type enum, Health Percent, Actor Value (limb condition AV), cripple art/debris/explosion, BPND flags "On Cripple", "Show Cripple Geometry"; papyrus events `OnCripple`, `OnPartialCripple`, function `ResetHealthAndLimbs` | verified (xEdit; falloutck Actor Script) |
| Limb AVs | AVIF NAM1 type "Condition" (e.g. Perception/Endurance/Left/Right Attack/Mobility condition) | type verified; editor ids supported hypothesis |
| Damage types | DMGT DNAM array of {Actor Value (resistance), Spell}; WEAP/ARMO/OMOD carry typed damage and resistances | verified (xEdit) |
| Magic effect | MGEF DATA: flags, Resist Value AVIF, Archetype (0-49: Value Modifier, Script, Cure Disease, Absorb, Dual Value Modifier, Paralysis, Cure Addiction, Concussion, Stimpak, Accumulate Magnitude, Stagger, Peak Value Modifier, Cloak, Slow Time, Damage, Immunity, Jetpack, Chameleon ...), primary/secondary AV, Perk to Apply, Equip Ability, IMAD, hit shaders and art | verified (xEdit) |
| Spell | SPEL SPIT {Base Cost, Flags (PC Start Spell, Ignore Resistance ...), Type u32: Spell, Disease, Power, Lesser Power, Ability, Poison, Addiction, Voice}, effects | verified (xEdit) |
| Ingestible | ALCH ENIT {Value, Flags: Food Item, Medicine, Poison; Addiction (form), Addiction Chance, Sound - Consume SNDR}, DNAM Addiction Name, effects; record flag Medicine | verified (xEdit) |
| Effect item | EFID MGEF, EFIT {Magnitude float, Area u32, Duration u32}, CTDA | verified (xEdit) |
| Addiction and withdrawal | ALCH points to an addiction SPEL (Type Addiction); withdrawal is that spell's effects; cured by Cure Addiction archetype (Addictol) | fields verified; behaviour supported hypothesis |
| Radiation | Rads AV accumulates from hazards (HAZD), ingestion and weapons; reduces max HP | supported hypothesis (entry points verified) |
| Survival mode | hunger, thirst, sleep stages lowering SPECIAL; 6 diseases; adrenaline; bed-only saves; no fast travel; ammo weight; slower healing; crippled limbs persist | behaviour supported hypothesis (Fallout wiki); quest/script names (likely an `HC_`-prefixed manager quest) unresolved |

## How Starfield does it
Counts: AVIF 1107, MGEF 853, SPEL 584, ENCH 106, ALCH 353, BPTD 27, DMGT 11, HAZD 75, RFCT none (**verified**, sf_esm.json).

| Piece | Starfield form | Label |
|---|---|---|
| MGEF | same core; archetypes 0-49 as FO4 (26 Summon Duplicate, 36 Command, 48 Boostpack named), new 50 Capacity Value Modifier, 51 Reset Flora, 52 Drop Resources, 53 Antigravity, 54 Track Damage, 55 Gravity Wielder; new flags Dynamic Restart, Animate Start/Stop Reaction | verified (xEdit) |
| SPEL | SPIT Type u8 at offset 8: Spell, Disease, Power, Lesser Power, Ability, Poison, Enchantment, Potion, Wort Craft, Leveled Spell, Addiction, Voice Power | verified (xEdit) |
| ALCH | same ENIT (Addiction now typed SPEL, sound is a Wwise sound reference), plus components, CVPA/CDIX and more | verified (xEdit) |
| Effect item | EFIT {Magnitude, Area float, Duration}; new MNAM/ANAM/ZNAM global overrides, EFIF flags, MUID | verified (xEdit) |
| DMGT | DNAM {Resistance AV, Spell}, FULL, VMAD | verified (xEdit) |
| BPTD | BPD2 keeps Damage Mult, Part Type, Health Percent, Actor Value, To Hit Chance, cripple fields; dismember/explode data gone | verified (xEdit) |
| Stamina | Oxygen and CarbonDioxide replace AP and Fatigue in entry point names | supported hypothesis |
| Rads entry points | 101 and 106 keep their FO4 names | verified (xEdit); engine use unresolved |
| Afflictions | injuries (concussion, fractures, sprains, lacerations ...), environmental (burns, frostbite, radiation poisoning, lung damage ...), infections, addiction; cured by matching aid items, doctors, time | supported hypothesis (VideoGamer guide); which records implement them unresolved |
| Environmental damage | thermal, corrosive, airborne, radiation; spacesuit protection is time-limited | supported hypothesis (guides) |
| Gameplay options | Sustenance (None / Positive / Positive + Negative), Food Healing, Sleep Healing, Ammo Weight, affliction and environmental sliders | supported hypothesis (Destructoid, 2024 update) |
| Crafting | Pharmaceutical Lab = WBDT Alchemy (05), keyword 102158 shared with FO4's chem bench | verified (docs/terrain/stations.md) |

## Mapping for the port
| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| ALCH (chems, food, stimpak, Nuka) | ALCH | translate | ENIT same; sound SNDR -> WWED; components optional |
| SPEL | SPEL | translate | SPIT Type u32 -> u8 at new offset |
| EFIT | EFIT | translate | Area int -> float |
| MGEF archetype 0-49 | same index | data copy of enum | 48 Jetpack = Boostpack; check FO4 MGEF using it (none expected) |
| MGEF visuals (EFSH, ARTO, RFCT, IMAD) | SF forms; RFCT is FO4-only | translate / drop | RFCT ("Hit Visuals") has no SF record |
| DMGT (8, arrays) | DMGT (one pair each) | translate | split each FO4 DMGT array into SF records or map to vanilla SF DMGTs |
| Resistance AVs | SF AVIFs | translate | map table, from AVIF dumps |
| Rads, Rads-to-HP | entry points 101/106 exist | translate, test | if the engine ignores them, a script quest drives max HP |
| BPTD limbs + condition AVs | BPTD | translate | dismember/gore drops; crippling depends on engine hooks (unresolved) |
| Addiction / withdrawal | SPEL Type Addiction | translate | SF uses the same type for its addiction affliction (supported hypothesis) |
| Survival mode | none (Sustenance option partly) | rebuild (script quest + MGEF) | reuse FO4's own scripts recompiled against shims |
| HAZD radiation zones | HAZD (SF has its own layout) | translate | see the Glowing Sea |
| SF afflictions and env damage | none in FO4 | fence / optional reuse | planet atmosphere hazards must be off on our planet (own ecosystem) |

## What must be rebuilt, and what needs SFSE or the Creation Kit
- Rads meter and HP bar overlay (red part of the HP bar): HUD work, Scaleform; SFSE if a new HUD element is needed.
- Limb condition display (Pip-Boy STAT page): part of the Pip-Boy rebuild.
- Survival mode: a quest with timers, needs AVs, disease SPELs and bed-save rules; bed-only saving and the
  fast-travel block need either GMST/INI changes or SFSE (unresolved).
- Our planet's atmosphere must not inflict Starfield environmental afflictions (biome/planet data); radiation in the
  Glowing Sea comes from FO4 HAZD/MGEF instead. CK2 authoring is enough for the data side.

## Port status and links
- docs/terrain/stations.md maps the chem bench to SF's Pharmaceutical Lab (WBDT 05, keyword 102158, **verified**).
- docs/actors/raider-conversion.md drops raider stimpak/chem inventory to the death item for now.
- Related: [vats.md](vats.md) (BPTD to-hit), [special-perks-leveling.md](special-perks-leveling.md) (entry points),
  [../next-phase/npcs-ai-factions-dialogue-quests.md](../next-phase/npcs-ai-factions-dialogue-quests.md) (Papyrus shims),
  [../next-phase/animations-ui-and-start.md](../next-phase/animations-ui-and-start.md) (HUD and Pip-Boy).

## Open questions and cheap checks
- xEdit: Starfield.esm AVIF editor ids for Health, Rads, ActionPoints, Oxygen, CarbonDioxide, limb conditions.
- xEdit: any Starfield.esm PERK/MGEF using entry point 101/106 or archetype Stimpak (31), Cure Addiction (28)?
- xEdit: list Starfield.esm SPEL with Type Disease / Addiction (are afflictions spells?).
- xEdit: FO4 DMGT 8 records with their AV/SPEL arrays vs Starfield's 11 DMGT names.
- FO4 CK Base.zip: list `HC_*.psc` (survival manager names; confirms how much is script).
- ContentResources.zip: grep `Affliction` and `Sustenance` in `*.psc` (script or engine?).
- In game: apply a converted FO4 Rad-damage MGEF to the player and watch max HP (does the engine still cap it).

## Sources
- xEdit definitions, TES5Edit dev-4.1.6: [wbDefinitionsFO4.pas](https://github.com/TES5Edit/TES5Edit/blob/dev-4.1.6/Core/wbDefinitionsFO4.pas),
  [wbDefinitionsSF1.pas](https://github.com/TES5Edit/TES5Edit/blob/dev-4.1.6/Core/wbDefinitionsSF1.pas) (MGEF, SPEL/SPIT,
  ALCH, EFIT/wbEffect, DMGT, BPTD, AVIF, entry point enums)
- [Actor Script (falloutck)](https://falloutck.uesp.net/wiki/Actor_Script) (OnCripple, ResetHealthAndLimbs)
- [Survival mode (Fallout wiki)](https://fallout.fandom.com/wiki/Survival_mode)
- [Starfield how to cure afflictions (VideoGamer)](https://www.videogamer.com/guides/starfield-cure-afflictions/)
- [Starfield May update difficulty tweaks explained (Destructoid)](https://www.destructoid.com/starfield-all-may-update-difficulty-tweaks-explained/)
- Project: docs/measurements/*_esm.json, docs/terrain/stations.md, docs/actors/raider-conversion.md
