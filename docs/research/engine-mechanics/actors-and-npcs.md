# Actors and NPCs (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved.

Scope: NPC_, RACE, templates (ACBS template flags, TPTA), face data, leveled actors (LVLN), actor values on NPCs,
classes, outfits, inventory, voice type assignment, essential/protected, persistence, creatures and robots.
"xEdit" below means TES5Edit dev-4.1.6 `Core/wbDefinitionsFO4.pas` and `wbDefinitionsSF1.pas` (community
reverse-engineered definitions; a field name there is verified as xEdit's layout, its engine meaning is not).

## In short
- **Same skeleton, different face.** NPC_ keeps the same core in both games: ACBS, factions (SNAM), death item (INAM),
  voice (VTCK), templates (TPLT + TPTA), race (RNAM), perks, PRPS actor values, inventory (CNTO), AIDT, packages
  (PKID), class (CNAM), outfit (DOFT), default package list (DPLT), crime faction (CRIF), combat style (ZNAM)
  (verified, xEdit). Field-level overlap is only 0.51 (verified, docs/FORMAT-GAP.md).
- **Templates carry over; Starfield adds two slots.** FO4 has 13 template categories; Starfield has 15. xEdit names
  bits 13 and 14 `Reaction Radius` and `Combat Style` (verified as xEdit's naming; it answers the "slots 13/14"
  question in docs/actors/raider-conversion.md as a supported hypothesis, since Mutagen leaves them unnamed).
- **Faces do not translate.** FO4 stores morph keys/values, face-morph regions and indexed tint layers; Starfield
  stores face-dial positions, morph-group blends, string-named tint layers and colour strings (verified, xEdit).
  Verdict: rebuild (Starfield template faces for generics, FO4 head as an ARMO for the named cast).
- **Verdict by part:** identity, flags, factions, inventory, leveled lists, voice assignment = translate; AIDT
  hostility = translate into relations / RDSA (see [factions](factions-crime-relationships.md)); face, body and
  creature races = rebuild; robot mods = rebuild on Starfield's object-template path (unresolved).

## How Fallout 4 does it

**NPC_ (verified, xEdit `wbRecord(NPC_`):**

| part | subrecords / fields |
|---|---|
| configuration | ACBS: flags u32, XP offset, level or level mult, calc min/max level, disposition, template flags u16, bleedout override |
| ACBS flags (selection) | 0 Female, 1 Essential, 3 Respawn, 4 Auto-calc stats, 5 Unique, 6 Doesn't affect stealth meter, 7 PC Level Mult, 11 Protected, 12 No Loot, 13 No Rumors, 17 Very Simple Actor, 20 Simple Actor, 23 No Activation/Hellos, 25 Disable Combat, 26 Spawns Dead, 27 Player Protected, 28 Do Not Use Load Doors, 29 Is Ghost, 31 Invulnerable |
| templates | TPLT default template (LVLN or NPC_), LTPT legendary template, LTPC legendary chance (GLOB), TPTA 13 per-category templates |
| behaviour | SNAM factions, AIDT, PKID packages, DPLT, override package lists SPOR / OCOR / GWOR / ECOR / FCPL / RCLR, ZNAM combat style, CRIF crime faction, CNAM class |
| stats and kit | PRKZ/PRKR perks, PRPS actor values, CNTO inventory, INAM death item, DOFT default outfit, SOFT sleeping outfit, PFRN power armor stand, GNAM gift filter |
| look | RNAM race, WNAM skin, ANAM far-away model, PNAM head parts, HCLF/BCLF hair colours, FTST head texture, QNAM texture lighting, MSDK/MSDV morph keys/values, TETI/TEND tint layers, MRSV body morph regions, FMRI/FMRS face morphs, FMIN morph intensity, NAM6/NAM4 height, MWGT weight |
| voice | VTCK voice type |

- **Template flags** (verified, xEdit `wbTemplateFlags`): 0 Traits, 1 Stats, 2 Factions, 3 Spell List, 4 AI Data,
  5 AI Packages, 6 Model/Animation, 7 Base Data, 8 Inventory, 9 Script, 10 Def Pack List, 11 Attack Data,
  12 Keywords. A set bit means "take this category from the TPTA entry (or TPLT)".
- **Vanilla example** (verified, docs/actors/raider-conversion.md): `LvlRaider` 0002898B, template flags 0x19BF,
  TPLT `LCharRaider` (LVLN, 7 tiers by level), Traits from `LCharRaiderFaceAndGender` (14 faces).
- **Named NPC example** (verified, docs/spikes/B4-mission-anatomy.md section 2): Preston 00019FD9: Essential,
  AutoCalcStats, Unique, IsGhost; class `ZeroSPECIALclass`; combat style `csPreston`; 9 factions; outfit
  `PrestonGarveyOutfit`; 9 head parts, 14 tint layers, 11 morphs, 30 face-morph regions; 7 scripts; no DPLT.
- **Face assets:** per-NPC facegen `.nif` + `.tri` (verified, FORMAT-GAP "Facegen" row). The CK bakes them; the
  exact folder layout is not re-checked here (supported hypothesis: `Meshes\Actors\Character\FaceGenData`).
- **RACE** (45 records, verified count): carries the chargen data itself: tint list (TINL), morph presets
  (MSID/MSM0/MSM1), hair colour lookup textures (HNAM/HLTX), default face textures, wrinkle maps, preset NPCs
  (RPRM/RPRF), behaviour graph and subgraph data (verified, xEdit).
- **LVLN** (228): entries of NPC_ / LVLN with level and count, LVLF flags, LVLG global (verified, xEdit). Used as
  TPLT targets so one ACHR spawns a level-appropriate variant.
- **Other counts** (verified, docs/measurements/fo4_esm.json): CLAS 31, OTFT 388, VTYP 531, HDPT 396, NPC_ 3,015.
- **Robots (Automatron):** NPC_ has an object template (`wbObjectTemplate`) and attach parent slots (APPR), and
  FURN workbench type 9 is `Robot Mod` (verified, xEdit). How robot OMODs reach the actor at run time is a
  supported hypothesis (OMOD on the actor via object template), not checked here. DLC plugins are unmeasured.

## How Starfield does it

**NPC_ (verified, xEdit `wbRecord(NPC_` in SF1):**
- **Same:** ACBS layout (minus the trailing bleedout override and padding), SNAM, INAM, VTCK, TPLT, LTPT, LTPC, TPTA,
  RNAM, WNAM, ATKR, override package lists SPOR / OCOR / GWOR / ECOR / FCPL / RCLR, PRKR, PRPS, CNTO, AIDT, PKID,
  CNAM, DNAM, PNAM head parts, ZNAM, NAM6/NAM4, MWGT, DOFT, DPLT, CRIF, MRSV.
- **Renamed:** SOFT is `Space Outfit`, not sleeping outfit. ACBS bit 19 is `Opposite Gender Anims`; bit 25 is
  `Forced Starts Dead`.
- **New:** ACBS bit 30 `Ignore Friendly Hits`; TPLT/LTPT may also point at BMMO; RDSA reaction-radius array (warn /
  attack / flee radii and package lists; was AIDT's aggro block); FLEE settings; RPLD / RPLI sound and sight detection
  package lists; QSTA / BNAM affinity event quest and dialogue branch; HEFA formation faction; LNAM plural name;
  ONA2 race overrides; STON skin tone; colour strings HCOL / FHCL / BCOL / ECOL / JCOL / TETC; PRON pronoun.
- **Gone (not in xEdit's SF1 NPC_):** far-away model ANAM, HCLF/BCLF, GNAM gift filter, NAM8 sound level, PFRN,
  FTST, MSDK/MSDV, TETI/TEND. ACBS bits for No Loot, No Rumors, Very Simple Actor, Disable Combat, Player Protected and
  Do Not Use Load Doors show as "Unknown" in SF1 (verified as xEdit naming; whether the engine still reads them is
  unresolved).
- **Face data** (verified, xEdit): `AVMD Tints` blocks (MNAM, TNAM group, QNAM name, VNAM texture, NNAM colour,
  INTV intensity, counted by EDCT); face dial positions (FMSI + FMRS float); face-morph phenotypes (FMRI with morph
  groups FMRG + FMRS); morph blends (BMPN/BMPV). Assets: `BSFaceGenNiNode` plus morph `.dat` (MRPH records, 998 in
  Starfield.esm) (verified, FORMAT-GAP and sf_esm.json).
- **Always present:** 16 subrecords in all 7,131 vanilla NPC_ (EDID, OBND, ODTY, ACBS, RNAM, PRPS, AIDT, DATA, DNAM,
  NAM5, NAM6, NAM4, MWGT, EDCT, STON, PRON); form version 581 (verified, raider-conversion section 3).
- **RACE** (31): chargen moved out: skin tone tables (BSTT/HSTT/FSTT), face custom texture base path (FCTP), morph race
  (NAM8), bone modifiers; per-race animation roots and skeleton rigs (verified, xEdit).
- **LVLN** (243): adds ONAM override name and LVLP leveled pack-in (verified, xEdit).
- **VTYP** (683): adds ANAM `Animation Face Archetype` and PNAM pronoun override (verified, xEdit). FO4's VTYP has
  only flags. The face archetype is a supported hypothesis for which FaceFX set a voice drives.
- **Other counts** (verified): CLAS 8, OTFT 596, HDPT 230, NPC_ 7,131. 5,445 of 7,131 NPC_ use templates (verified,
  raider-conversion).

## Mapping for the port

| FO4 piece | Starfield counterpart | verdict | notes |
|---|---|---|---|
| ACBS flags Female/Essential/Respawn/Unique/Protected/Is Ghost/Invulnerable | same bits | data copy | verified same bit positions |
| ACBS bits shown "Unknown" in SF (No Loot, Disable Combat, Do Not Use Load Doors ...) | none named | translate or drop | unresolved whether CE2 honours them; do not copy blind |
| ACBS template flags 0-12 | same 0-12 | data copy | bits 13/14 chosen by the converter (Starfield template's) |
| TPLT/TPTA to LVLN | TPLT/TPTA | translate | GetIsID did not confirm a templated spawn through a chain without LVLN (raider-conversion, unresolved) |
| LTPT/LTPC legendary | same fields | translate | see [combat](combat-detection-stealth.md) |
| SNAM factions | SNAM | translate | FormID map to our FO4_ factions |
| AIDT aggro block | RDSA + AIDT flag | rebuild | hostility model differs |
| PRPS actor values | PRPS | translate | AVIF 359 vs 1,107; map by editor id, drop FO4-only (SPECIAL needs own AVIFs) |
| CNTO, INAM, DOFT | same | translate | weapons and armour wait on their own converters |
| SOFT sleeping outfit | none (SOFT = space outfit) | drop | never write FO4 SOFT into Starfield SOFT |
| PFRN power armor stand | none | drop / script | power armor is its own system |
| CNAM class | CNAM | translate | 31 FO4 classes; Starfield's 8 do not cover SPECIAL; make our own CLAS |
| VTCK | VTCK | translate | our own VTYPs (next-phase note, section 5) |
| head parts, tints, morphs | different model | rebuild | route (a) template faces / (b) FO4 head as skin ARMO |
| RACE (human) | HumanRace | translate | proven by the raider and Preston |
| RACE (creatures, robots) | new races | rebuild | skeleton + behaviour graph; animation track |
| Automatron robot OMODs | object template / OMOD | rebuild | unresolved |
| persistent ACHR | persistent ACHR | translate | merge offset must be fixed in the world build |

## What must be rebuilt, and what needs SFSE or the Creation Kit
- **Faces:** no field mapping exists. Starfield's morph `.dat` and face-dial system need either Starfield presets
  (cheap) or the FO4 facegen head as a skin/armour mesh (supported hypothesis that it renders; Codsworth's model
  works that way). A true morph translation would need the CK's face tools or a reverse-engineered `.dat` writer
  (unresolved).
- **Creatures:** new RACE + skeleton + behaviour graph per creature family; until the animation track lands they stay
  Starfield stand-ins (next-phase note, section 3).
- **SPECIAL and FO4 actor values:** our own AVIF set; PRPS references remapped.
- **SFSE / CK:** nothing in this area needs SFSE so far. The CK is needed only if faces are generated from morph data
  (unresolved).

## Port status and links
- Converted raider (`FO4_LvlRaider` F04800 and calm probe F04801) and Preston on Starfield templates: spawn, path,
  fight, die, Essential (verified in game, next-phase note section 3; docs/actors/raider-conversion.md).
- Mutagen 0.55 types NPC_, LVLN, VTYP, CSTY, FACT on both sides (verified, next-phase note section 1).
- Persistent-cell merge offset (-1200, -2700) worked around per actor in the mission (verified, next-phase note).
- Plan level: [npcs-ai-factions-dialogue-quests](../next-phase/npcs-ai-factions-dialogue-quests.md) (section 3),
  [voice-lipsync-companions](../next-phase/voice-lipsync-companions.md),
  [animations-ui-and-start](../next-phase/animations-ui-and-start.md).

## Open questions and cheap checks
- Do CE2 actors honour ACBS bits xEdit marks Unknown? Dump bit histograms over Starfield.esm NPC_ (Mutagen, offline).
- Slots 13/14 = Reaction Radius / Combat Style: compare each NPC_'s slot-13 template's RDSA and slot-14 template's
  ZNAM with its own (offline scan).
- Does Starfield ship per-NPC facegen? List `facegen` paths in sf_ba2.json-style archive listing (offline).
- Automatron: dump one robot NPC_ (e.g. a DLC01 robot) and its object template from DLCRobot.esm in xEdit.
- AVIF map: diff AVIF editor ids between the two esm files (offline).
- DLC record totals: recon.py over each DLC esm (next-phase note, section 10).

## Sources
- xEdit definitions: https://github.com/TES5Edit/TES5Edit (branch dev-4.1.6, `Core/wbDefinitionsFO4.pas`,
  `Core/wbDefinitionsSF1.pas`, `Core/wbDefinitionsCommon.pas`), read locally.
- Repo: docs/FORMAT-GAP.md, docs/measurements/fo4_esm.json and sf_esm.json, docs/actors/raider-conversion.md,
  docs/spikes/B4-mission-anatomy.md, docs/mission/when-freedom-calls.md.
- Next phase note: ../next-phase/npcs-ai-factions-dialogue-quests.md.
