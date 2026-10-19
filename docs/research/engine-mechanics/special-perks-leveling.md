# SPECIAL, perks and leveling (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved.

## In short
- FO4: SPECIAL are seven AVIF records of type "Special (Attribute)"; perks are PERK records with a flat
  DATA (level requirement, rank count) and an NNAM "Next Perk" chain, one record per rank; the perk chart is a UI over
  them. Starfield: skills are PERK records with a category (Combat/Science/Tech/Physical/Social), a tier
  (Basic..Master) and up to several ranks inside one record, each rank gated by an Activity Tracker (the "challenge").
- Both games share the perk effect machinery (PRKE + entry points). Starfield's entry point table keeps FO4's 158
  entries at the same indices (with "Action Points" renamed "Oxygen") and adds 59 more. **verified** (xEdit).
- Verdict: SPECIAL values and FO4 perk effects **translate** (AVIF and entry point indices map almost 1:1); the
  FO4 perk chart, SPECIAL allocation at Vault 111 exit, and the level-up flow **rebuild** (UI: Scaleform, likely SFSE);
  Starfield's skill/challenge UI is **dropped** from our world.
- Starfield traits and backgrounds are PERK records with flag bits. They are fenced out (our player starts as the
  Vault 111 survivor), but the Trait flag can carry FO4's few trait-like perks if needed.

## How Fallout 4 does it
**Records** (counts: AVIF 359, PERK 538, GLOB 1346, BOOK 327, MISC 2176; **verified**, docs/measurements/fo4_esm.json)

| Record | Key fields | Label |
|---|---|---|
| AVIF | EDID, FULL, DESC, ANAM abbreviation, NAM0 default value, AVFL flags (Skill, Maximum 10, Maximum 100, Percentage, Hardcoded ...), NAM1 type enum: Derived Attribute, Special (Attribute), Skill, AI Attribute, Resistance, Condition, Charge, Int Value, Variable, Resource | verified (xEdit) |
| AVIF SPECIAL | xEdit comment: "S.P.E.C.I.A.L start at index 5, so FormID 0x2bc+5 to 0x2bc+11" (hardcoded AVIFs) | verified as xEdit's note; exact per-stat FormIDs unresolved here |
| PERK | VMAD (fragments), FULL, DESC, ICON, CTDA conditions (requirements such as SPECIAL >= n, player level), DATA {Trait, Level, Num Ranks, Playable, Hidden}, SNAM sound, NNAM Next Perk, FNAM SWF (perk card animation), Effects (PRKE header: type, rank, priority; DATA = Quest+Stage / Ability SPEL / Entry Point + function; PRKC per-tab conditions; EPFT/EPFD parameters; PRKF end) | verified (xEdit) |
| Entry points | 158 entries (index 0-157), e.g. 22 Mod Exp, 82 Mod Kill Experience, 79 Mod VATS Attack Action Points, 101 Set Rads To Health Mult, 120 Mod Exp Location, 121 Mod Exp Speech | verified (xEdit) |
| BOOK | DATA flags incl. "Add Perk" with a Teaches union (AVIF / SPEL / PERK); FO4 magazines use this route | field verified (xEdit); "magazines use Add Perk" supported hypothesis |
| MISC bobbleheads | permanent SPECIAL/skill bonus on pickup | mechanism (script vs perk) unresolved |

**Behaviour**
- Perk ranks: each rank is its own PERK record linked by NNAM; the chart shows the first, with DATA Level as the
  player-level gate and conditions as the SPECIAL gate. **supported hypothesis** (field layout verified; chart logic
  is engine/SWF code).
- XP: Papyrus `Game.RewardPlayerXP(int auiXPAmount, bool abDirect = false)` grants XP, `abDirect` skips modifiers
  (**verified**, falloutck). Kill/lock/hack/discovery XP and the level curve come from game settings; their GMST names
  and values are **unresolved** here (not invented; see checks).
- Level-up grants a perk point; SPECIAL is allocated in the "You're SPECIAL!" book at Vault 111 / Sanctuary
  (MQ101-side). **supported hypothesis** (game knowledge; the record path is not checked).
- Papyrus: `Actor.AddPerk`, `RemovePerk`, `HasPerk`, `GetLevel` on Actor (**verified**, falloutck Actor Script);
  AV access via `ObjectReference.GetValue/SetValue/ModValue(ActorValue)` (**supported hypothesis**, FO4 changed from
  string AV names to ActorValue forms).

## How Starfield does it
Counts: AVIF 1107, PERK 502, GLOB 2677, BOOK 992, CHAL 8 (**verified**, sf_esm.json).

| Piece | Starfield form | Label |
|---|---|---|
| AVIF | same AVFL/NAM1 layout plus VMAD, components, NLDT, NAM2 Min, NAM3 Max, new type "Anim Graph Variable" | verified (xEdit) |
| Skill | PERK DATA {Perk Category: None/Combat/Science/Tech/Physical/Social, Perk Skill Group: Basic/Advanced/Expert/Master, Crew Assignment Requirement, Flags: Trait, Playable, Hidden, Crew, Background, Hidden on Data Menu}; TNAM restriction KYWD; UNAM training PERK; GNAM icon | verified (xEdit) |
| Ranks | repeated PRRK..PRRF blocks inside one PERK, each with effects, conditions, an Activity Tracker, a DESC and PRUC "Quantum Essence Upgrade Cost" | verified (xEdit) |
| Challenge | the rank's Activity Tracker: ATCP count, ATAN activity type (30 types: Kill, Craft, Lockpick, Sprint, Speech Challenge, Scan Planet, Cripple Limb, Take Hit Damage ...), progression evaluator (DNAM + CITC + conditions), ATAV config | verified (xEdit) |
| CHAL record | only EDID + components in xEdit; 8 records. Not the skill challenges; probably the separate Challenges menu | layout verified; purpose supported hypothesis |
| Entry points | 217 entries; 0-157 match FO4 by index except 136 (Apply Bloody Mess Spell -> Mod Oxygen Use) and 155 (VATS Apply Paralyzing Palm Spell -> Mod Jumping Oxygen); AP renamed Oxygen, Fatigue renamed CarbonDioxide; 158-216 new (ship, research, workshop, zero-G, social skill) | verified (xEdit diff) |
| Traits / backgrounds | PERK with the Trait or Background flag | verified (xEdit) |
| BOOK | keeps "Add Perk" Teaches; skill magazines plausibly use it | field verified; usage supported hypothesis |
| Leveling | one skill point per level, skills to rank 4, a challenge gates each next rank | supported hypothesis (PC Gamer guide) |

Not in Starfield's PERK: xEdit's SF definition comments out ICON, record-level conditions (both marked "not in
Starfield.esm"), SNAM, NNAM and FNAM SWF. **verified** (xEdit comment block); whether the engine would still read
SNAM/NNAM/FNAM is unresolved.

## Mapping for the port

| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| SPECIAL AVIFs (hardcoded) | AVIF; SF has no SPECIAL stats | translate / new AVIF | make 7 new AVIFs of type Special (Attribute) in our plugin, or reuse unused hardcoded slots if they exist (unresolved) |
| FO4 skill-style AVs (CarryWeight, ActionPoints, Rads ...) | SF AVIFs by editor id; AP -> Oxygen is likely | translate | map table needed, built from both AVIF dumps |
| PERK DATA + NNAM chain | PERK with Ranks blocks | translate | fold an NNAM chain into one SF PERK with N ranks, or keep one record per rank (simpler, no rank UI needed) |
| PERK conditions (SPECIAL/level gates) | per-rank CTDA | translate | record-level CTDA is gone, move to rank 1 conditions |
| PRKE entry points 0-157 | same index | data copy | except 136, 155 (FO4-only effects need a script shim) |
| PRKE Quest+Stage / Ability | same union | data copy | |
| PERK FNAM SWF perk cards | none | rebuild (UI) | FO4 SWFs are the player's own files; need our perk chart SWF |
| Perk chart, SPECIAL book, level-up menu | Starfield skills menu | rebuild (Scaleform + SFSE) | see ../next-phase/animations-ui-and-start.md (menus) |
| Game.RewardPlayerXP calls in quest scripts | SF Game script | script shim / verify | presence in SF's Game.psc unresolved |
| Kill/quest XP GMSTs | SF GMSTs | translate | after a GMST dump of both |
| Bobbleheads (MISC + effect) | MISC + SPEL/perk | translate | after checking FO4's mechanism |
| Magazines (BOOK Add Perk) | BOOK Add Perk | data copy | |
| SF skills, challenges, traits, backgrounds | none in our world | drop / fence | keep SF skill perks off our player; Starborn and crew perks fenced |

## What must be rebuilt, and what needs SFSE or the Creation Kit
- A perk chart / SPECIAL / level-up UI. Starfield's skills menu reads category, tier and ranks; FO4 has 7 SPECIAL
  columns x 10 levels. Reskinning the SF menu is unlikely to fit; a new Scaleform menu opened via SFSE is the likely
  route (supported hypothesis; same decision as the Pip-Boy).
- New AVIFs for SPECIAL and the derived formulas (carry weight from STR, AP from AGI, HP from END). Derived AV
  formulas are engine code in FO4 (unresolved how they are bound); in Starfield they will need perks, AV modifiers or
  a script quest.
- The new-game flow (no Starfield intro, phase 1) must give the player zero SF skill points and no background/traits:
  needs a check of what SF's chargen quest grants. CK2 can author the plugin; no SFSE needed for the data.

## Port status and links
- No converter for PERK/AVIF yet (no file in the repo handles them; grep of docs found only perk loot mentions in
  docs/actors/raider-conversion.md, where `crDamage075` is a raider perk).
- ROADMAP.md C2 lists "SPECIAL and perks" in the base core; PLAN.md's non-goal on VATS/Pip-Boy is under revision there.
- Menus: [../next-phase/animations-ui-and-start.md](../next-phase/animations-ui-and-start.md). Quests and scripts that
  award XP: [../next-phase/npcs-ai-factions-dialogue-quests.md](../next-phase/npcs-ai-factions-dialogue-quests.md).

## Open questions and cheap checks
- xEdit: list Fallout4.esm AVIF where NAM1 = Special; note FormIDs and editor ids (one filter).
- xEdit: diff AVIF editor ids FO4 vs SF (Strength..Luck, ActionPoints, Rads, CarryWeight present in SF?).
- xEdit: GMST editor ids matching `XP|Level|Perk` in both masters, with values.
- ContentResources.zip: `grep -n "RewardPlayerXP\|AddPerk\|GetLevel" Game.psc Actor.psc`.
- Fallout4 CK Base.zip: grep a bobblehead MISC's script name (MISC editor id `Bobblehead*`, VMAD).
- xEdit: one SF skill PERK (e.g. a Combat Basic skill) to see rank count and ATAV JSON, confirm CHAL is unrelated.
- In game: does SF's level-up still prompt a skill point if the player has no SF skills unlocked (UI side effect).

## Sources
- xEdit definitions, TES5Edit dev-4.1.6: [wbDefinitionsFO4.pas](https://github.com/TES5Edit/TES5Edit/blob/dev-4.1.6/Core/wbDefinitionsFO4.pas),
  [wbDefinitionsSF1.pas](https://github.com/TES5Edit/TES5Edit/blob/dev-4.1.6/Core/wbDefinitionsSF1.pas) (PERK, AVIF,
  BOOK, entry point enums, wbActivityTracker, wbPerkActivityTypes, CHAL)
- [RewardPlayerXP - Game (falloutck)](https://falloutck.uesp.net/wiki/RewardPlayerXP_-_Game);
  [Actor Script (falloutck)](https://falloutck.uesp.net/wiki/Actor_Script);
  [Papyrus FAQs (falloutck)](https://falloutck.uesp.net/wiki/Papyrus_FAQs)
- [Starfield Mod:Script-Actor (starfieldwiki)](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-Actor)
- [How to rank up your skills in Starfield (PC Gamer)](https://pcgamer.com/starfield-how-to-rank-up-skills)
- Project: docs/measurements/fo4_esm.json, sf_esm.json; docs/ROADMAP.md (C2); docs/PLAN.md (non-goals)
