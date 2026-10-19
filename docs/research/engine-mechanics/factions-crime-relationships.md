# Factions, crime and relationships (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved.

Scope: FACT (relations, reactions, crime values, vendor data), RELA relationships, the crime system (bounty, jail,
trespass, theft and ownership, assault and murder), Starfield's crime factions, and how the port keeps Starfield
crime out of our world. "xEdit" = TES5Edit dev-4.1.6 `wbDefinitionsFO4.pas` / `wbDefinitionsSF1.pas` /
`wbDefinitionsCommon.pas`.

## In short
- **Faction relations work the same way.** XNAM entries (faction or race, modifier, group combat reaction Neutral /
  Enemy / Ally / Friend) are identical in both games (verified, xEdit `wbFactionRelations`). Verdict: translate
  (FormID map), all 699 FACTs into our FO4_ namespace.
- **Hostility is computed differently in practice.** FO4 makes enemies hostile through AIDT aggression against the
  relation (Very Aggressive attacks Neutral; Aggressive attacks Enemy); FO4 raiders have no relation to the player at
  all. Starfield's Spacers are Unaggressive and hostile through an Enemy relation to PlayerFaction plus RDSA
  reaction radii (verified, docs/actors/raider-conversion.md). Verdict: rebuild hostility as explicit relations.
- **FO4's crime system is mostly off.** The FO4 CK wiki says crime is "simplified and deprecated": only Attack on
  Sight (with Track Crime) is used; arrest and crime gold are unused and vanilla defines no jail markers (falloutck
  Faction page, verified as documented). Starfield runs full bounty, arrest, prison, contraband (smuggling) and
  piracy (verified fields, xEdit SF1 FACT).
- **RELA** (64 in Fallout4.esm, 0 in Starfield.esm, verified counts) still has a definition in xEdit's SF1 with the
  same DATA layout (verified). So the record type likely loads in CE2 (supported hypothesis), but Starfield's own
  content does not use it. Verdict: data copy, then one in-game check of `GetRelationshipRank`.
- **Fence:** our cells, locations and NPCs carry no Starfield crime faction; our FACTs set no prisons; Starfield
  factions touch our actors only through PlayerFaction (next-phase note, section 4).

Ties to Starfield's own faction features (herds, formations, faction voices, arrest and prison) and the rule for
reusing them: [starfield-systems-to-reuse.md](starfield-systems-to-reuse.md).

## How Fallout 4 does it

**FACT (699, verified count; layout verified, xEdit):**

| subrecord | content |
|---|---|
| FULL | name |
| XNAM (array) | relation: faction/race, modifier, group combat reaction |
| DATA | flags: Hidden From NPC, Special Combat, Track Crime, Ignore Crimes (Murder, Assault, Stealing, Trespass, Pickpocket), Do Not Report Crimes Against Members, Crime Gold - Use Defaults, Vendor, Can Be Owner |
| JAIL / WAIT / STOL / PLCN / JOUT | exterior jail marker, follower wait marker, stolen goods container, player inventory container, jail outfit |
| CRGR | shared crime faction list (FLST) |
| CRVA | crime values: Arrest, Attack On Sight, Murder, Assault, Trespass, Pickpocket, Steal Multiplier, Escape |
| RNAM / MNAM / FNAM | ranks: rank number, male and female titles (deprecated per the CK wiki) |
| VEND / VENC / VENV | vendor buy/sell list, merchant container, vendor values (hours, radius, buys stolen / non-stolen, buy everything not in list) |
| PLVD, CITC + conditions | vendor location, vendor conditions |

- **Reactions** (falloutck Faction page, verified as documented): Enemy is attacked by Aggressive, Very Aggressive and
  Frenzied actors; Neutral (the default for any pair) by Very Aggressive and Frenzied; Friend and Ally only by
  Frenzied. "Helps Friends and Allies" actors assist Friends and Allies; "Helps Allies" actors assist Allies only.
- **Crime in practice:** only Attack on Sight is live; Arrest and crime gold are listed as unused; Exterior Jail
  Marker, stolen goods and player inventory containers and jail outfit are undefined in vanilla (same source).
  The Morality AIDT value (Any Crime, Violence Against Enemies, Property Crime Only, No Crime) and NPC_ CRIF still
  exist (verified, xEdit).
- **Ownership:** XOWN (owner FACT or NPC_, plus a `No Crime` byte in FO4+) and XRNK faction rank on refs and cells;
  LCTN FNAM `Unreported Crime Faction` (verified, xEdit). Condition functions IsTrespassing, GetCrimeGold,
  GetCrimeGoldViolent, GetFactionRelation, IsHostileToActor exist (verified, xEdit condition table).
- **Companion crime factions:** Preston carries `CompanionCrimeFaction_Preston` and a "crime hostility" script
  among 7 (verified, B4 section 2). Supported hypothesis: companion disapproval and "turn hostile on assault" run
  through these factions plus scripts, not through bounty.
- **RELA (64, verified count; layout verified, xEdit):** DATA = parent NPC_, child NPC_, rank (Lover, Ally,
  Confidant, Friend, Acquaintance, Rival, Foe, Enemy, Archnemesis), flags (Secret), association type (ASTP; 13 ASTP records,
  FO4-only). Rank feeds `GetRelationshipRank` (verified as a condition function in both games' tables) and,
  per CE lineage, how actors react to each other (supported hypothesis).
- **Vanilla example:** RaiderFaction 0001CBED has 9 relations, none to PlayerFaction (verified,
  raider-conversion section 2).

## How Starfield does it

**FACT (812, verified count; layout verified, xEdit SF1):**
- **Same:** FULL, XNAM relations (identical enum), DATA flags 0-15 (same names and bits), CRGR, CRVA first fields,
  ranks, VEND / VENC / VENV, PLVD, conditions.
- **New:** VMAD scripts; DNAM `Faction Type` keyword; DATA bits 16 Ignore Crimes: Piracy, 17 Ignore Crimes:
  Smuggling, 18 Report Crimes By Members Against Members; CRVA adds Piracy and Smuggle Multiplier; PRIS array of
  prison locations (prison door marker, ship landing marker, cargo contraband, inventory contraband, companion wait
  marker); VTCK voice (VTYP or FLST); `Herd` block (search radius, min/max herd members, idle chatter times);
  `Create Group` with formation radius.
- **Gone:** JAIL, WAIT, STOL, PLCN, JOUT (folded into PRIS). VENV radius is a float, not u16.
- **NPC_ side:** CRIF crime faction kept; new HEFA formation faction; ACBS bit 30 Ignore Friendly Hits (verified,
  xEdit).
- **Crime in practice:** bounty, arrest by guards, prison time or fines, contraband scanning on landing (supported
  hypothesis from player guides and the PRIS / smuggling fields; no CK doc read, the Bethesda wiki was in
  maintenance). Crime-faction editor ids (UC, Freestar, Neon and so on) are **unresolved** here; list them before
  writing the fence.
- **Ownership:** XOWN with No Crime byte and LCTN FNAM Unreported Crime Faction are unchanged (verified, xEdit).
- **RELA:** 0 records in Starfield.esm; definition present in xEdit SF1 with VMAD added (verified). Starfield's
  companion system uses affinity events instead (AFFE 1,360 records; NPC_ QSTA / BNAM affinity quest and branch;
  verified counts and fields).
- **In-game finding** (verified, Oct 18-19, next-phase note section 4): an NPC with no faction is neutral to the
  player; neutral actors turn hostile on any stray hit, and `IgnoreFriendlyHits` did not prevent it. Preston did this
  twice.

## Mapping for the port

| FO4 piece | Starfield counterpart | verdict | notes |
|---|---|---|---|
| FACT XNAM relations | XNAM | translate | carry all, including Ally/Friend to PlayerFaction 01C21C |
| aggression-driven hostility (raiders, creatures) | Enemy relation to PlayerFaction (+ RDSA) | rebuild | one rule: FO4 Very Aggressive with no player relation becomes Enemy to PlayerFaction |
| DATA flags 0-15 | same bits | data copy | leave bits 16-18 clear |
| CRVA | CRVA | data copy | Attack On Sight is what FO4 uses; piracy/smuggle 0 |
| JAIL / WAIT / STOL / PLCN / JOUT | PRIS | drop | vanilla FO4 leaves them empty |
| CRGR | CRGR | translate | our own lists only |
| vendor VEND / VENC / VENV | same | translate | radius u16 to float |
| ranks | ranks | data copy | unused by FO4, harmless |
| NPC_ CRIF | CRIF | translate | only to our own factions |
| LCTN FNAM unreported crime faction | same | translate | never a Starfield faction |
| XOWN / XRNK | same | translate | needed for sandbox UseOwnedOnly and theft checks |
| RELA | RELA (unused by vanilla) | data copy | check in game |
| ASTP association types | none in Starfield.esm | data copy | same caveat as RELA |
| companion crime factions + scripts | affinity events (AFFE) or our scripts | rebuild | companion design is its own topic |

## How the port keeps Starfield crime out (the fence)
1. No Starfield FACT is ever written into our NPC_ SNAM / CRIF, our LCTN FNAM, or our XOWN.
2. Our FACTs leave PRIS empty and smuggling/piracy at 0, so no prison transfer or contraband scan has a target
   (supported hypothesis; needs one in-game check).
3. Hostility to the player is an explicit relation, so no FO4 actor depends on Starfield aggression or reaction-radius
   defaults by accident.
4. Starfield's bounty on the player from its own factions should never rise in our world because no Starfield crime
   faction member is present (supported hypothesis). Still to check: whether a global crime system (guards, contraband
   scan on landing) runs regardless of faction in a worldspace with no planet data.
5. For deliberate FO4 crime (Diamond City, Goodneighbor attack-on-sight), use our own factions with Track Crime +
   Attack On Sight only, matching FO4's live subset.

## What must be rebuilt, and what needs SFSE or the Creation Kit
- Aggression-to-relation rebuild (converter rule, offline, synthetic-fixture tests).
- Companion approval: FO4 affinity scripts versus Starfield AFFE; separate design.
- No SFSE or CK need identified. If Starfield's crime UI or arrest flow fires in our world anyway, a script fence or
  SFSE hook may be needed (unresolved).

## Port status and links
- Mission: Preston gets an own faction (since Oct 19), needed after the neutral-hostility finding (next-phase note).
- Raider conversion uses SpacerFaction + GroupFactionSpacers as a stand-in; an own FO4_RaiderFaction is planned
  (docs/actors/raider-conversion.md, section 7).
- Plan: N3 converts all 699 FACTs with relations ([next-phase note](../next-phase/npcs-ai-factions-dialogue-quests.md),
  sections 4, 8, 9).

## Open questions and cheap checks
- List Starfield crime factions: FACT with Track Crime set and a PRIS entry in Starfield.esm (offline scan).
- RELA in CE2: one plugin with a RELA, read `GetRelationshipRank` in the console (one PC run).
- How many FO4 FACTs have Track Crime / Attack On Sight set (offline scan).
- Which FO4 hostile groups have no PlayerFaction relation (input for the aggression rule; offline scan).
- Does Starfield's contraband scan or arrest dialogue run in our worldspace? One walk past a guard with a stolen item.

## Sources
- xEdit: https://github.com/TES5Edit/TES5Edit (dev-4.1.6, `Core/wbDefinitionsFO4.pas`, `wbDefinitionsSF1.pas`,
  `wbDefinitionsCommon.pas`), read locally.
- Fallout 4 CK wiki: https://falloutck.uesp.net/wiki/Faction.
- Starfield crime overview (player guides, supported hypothesis only): https://www.wepc.com/gaming/starfield-jail-guide/,
  https://www.shacknews.com/article/136888/smuggle-contraband-starfield.
- Repo: docs/actors/raider-conversion.md, docs/spikes/B4-mission-anatomy.md, docs/measurements/*.json,
  ../next-phase/npcs-ai-factions-dialogue-quests.md.
