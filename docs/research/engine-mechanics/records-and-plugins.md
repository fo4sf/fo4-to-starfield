# Shared foundations: plugins, FormIDs, conditions, scripts on forms (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: **verified** /
**supported hypothesis** / **unresolved**.

Every mechanism file leans on these. The measured file-format gap (headers, archives, meshes, materials, physics)
is in [docs/FORMAT-GAP.md](../../FORMAT-GAP.md); this page covers the record-level machinery the gameplay systems
share. Full record counts: [record-counts.md](record-counts.md).

## In short

- Both engines read **plugins** (`.esm`/`.esp`, light/small masters) of typed **records** with FormIDs, loaded in
  order, later plugins overriding earlier ones. Same idea, different versions: FO4 header form version 131, Starfield
  581; 116 record types in common, 21 only in FO4, 64 only in Starfield; the shared types still differ field by field
  (subrecord overlap mostly 0.25 to 0.6). **verified** (FORMAT-GAP.md)
- **Conditions (CTDA)** are the glue of quests, dialogue, packages, perks and effects. xEdit lists 479 FO4 condition
  functions and 611 Starfield ones: **458 FO4 functions exist in Starfield under the same name and index**; 21 do
  not, and several of their indices were **reused for different functions** in Starfield. Copying raw condition bytes
  would silently change meaning; a converter maps by name and refuses the rest. **verified** (xEdit tables, compared
  2026-10-19)
- **Scripts attach to forms** through VMAD (script name, properties) in both engines, with fragment variants for
  quests, scenes, infos, packages, perks and terminals. Papyrus is the same language family; see
  [papyrus-and-script-extenders.md](papyrus-and-script-extenders.md). **verified** (xEdit; the mission ran)
- **Names are global**: script names, editor ids used by scripts (`Game.GetFormFromFile`), keywords and globals can
  collide with Starfield's (both games ship a `CompanionActorScript`, for example). The port uses its own prefix for
  every converted editor id and script. **supported hypothesis** for the collision risk per item; the rule is a
  project decision to record in docs/ai/decisions.md.

## Plugins and FormIDs

| | Fallout 4 | Starfield | label |
|---|---|---|---|
| master files | Fallout4.esm plus DLC esm (DLCRobot, DLCworkshop01..03, DLCCoast, DLCNukaWorld) | Starfield.esm plus its own update masters | verified (project's FO4 data paths; Starfield's own list is not needed) |
| light plugins | ESL flag, FormIDs in FE xxx space, 4,096 records | small (light) masters plus a **medium** master tier | supported hypothesis for the medium tier (Starfield 1.12+ plugin changes; not measured) |
| plugin list | `Plugins.txt` with `*` for active | same file, same `*` rule | verified (the install writes it) |
| loose files | read by default if enabled in INI | this install reads no loose files (`sResourceDataDirsFinal=STRINGS\`), so scripts and assets ship in `.ba2` | verified (project memory, the PC) |
| strings | localized `.strings`/`.dlstrings`/`.ilstrings` | same scheme | supported hypothesis |

The port's rule: every converted record gets a **deterministic FormID** from a stable map (FO4 FormID to ours), so
saves, doors, aliases and scripts agree across rebuilds; the v6c and v6e cores share all 683,870 FormIDs. **verified**
(launcher work, #394).

## Conditions (CTDA)

A condition is: function index, comparison, value (or a GLOB), run-on target (subject, target, reference, linked
ref, quest alias, package data, event data, player), parameters. Used in INFO, PACK, QUST (stage log, objectives,
aliases, Story Manager), PERK entry points, MGEF, COBJ, SMQN, LCTN-based filters and more. **verified** (xEdit).

FO4 functions with **no same-named Starfield function** (xEdit, by name; the Starfield function now at the same index
in brackets):

| FO4 function (index) | Starfield at that index | port note |
|---|---|---|
| GetLocationCleared (250) | GetLocationExplored | renamed concept: use the new name |
| GetCurrentLocationCleared (797) | GetCurrentLocationExplored | same |
| GetLocationAliasCleared (598) | GetLocationAliasExplored | same |
| GetInCurrentLocation (359) | GetIsCurrentLocation | renamed |
| GetInCurrentLocationAlias (360) | GetIsCurrentLocationAlias | renamed |
| IsInSameCurrentLocationAsRefAlias (604) | IsInSameCurrentLocationAsAlias | renamed |
| HasMagicEffectKeyword (699) | HasMagicEffectOrSpellKeyword | broader; check semantics |
| MenuMode (36) | MenuPaused | check semantics |
| DialogueHasPerk (507) | GetPerkRank | different; rewrite as HasPerk/GetPerkRank on the subject |
| GetSpeechChallengeSuccessLevel (544) | GetSpeechChallengeSuccessScene | different system (SPCH) |
| GetPlayerWalkAwayFromDialogueScene (728) | GetSpeechChallengeSuccessGame | **index reused**; rebuild |
| GetCurrentAIPackage (110) | GetDistanceFromCelestialBody | **index reused**; rebuild (script or package keyword) |
| GetKillingBlowLimb (495) | EPMagic_EffectIsDetrimental | **index reused**; rebuild |
| IsKillerObject (409) | IsPlayerInShipTargetingMode | **index reused**; rebuild |
| IsInRobotWorkbench (817) | IsDockedWith | **index reused**; Automatron; rebuild |
| DialogueGetAv (506), DialogueGetItemCount (510) | none | rewrite as GetValue / GetItemCount on the right target |
| GetSpellUsageNum (552), HasBeenEaten (127), IsLimbGone (397), IsPS3 (520) | none | rebuild or drop (IsLimbGone matters for dismemberment) |

These are the only rows that need hand work; the other 458 map one to one by name. Starfield adds 153 functions of
its own (planets, ships, outposts, skills). Whether every same-named function has the same parameters is **supported
hypothesis** (xEdit shows parameter types; a diff of parameter types is a cheap next step). Mutagen exposes both
function enums, so the converter can enforce "by name, refuse unknown" at build time.

## Scripts on forms (VMAD)

- VMAD = version, object format, then scripts (name, flags, properties: object, string, int, float, bool, arrays, and
  structs from FO4 on). Fragment variants hold an extra file name plus fragment index tables for QUST (stage, log
  entry), SCEN (begin, end, phases), INFO (begin, end), PACK (begin, change, end), PERK (entry points), TERM (menu
  items). **verified** (xEdit; layouts per game in [papyrus-and-script-extenders.md](papyrus-and-script-extenders.md)).
- Object properties point at forms by FormID, so they follow the deterministic map.
- Alias properties (quest plus alias id) are how fragments reach aliases; they survive conversion if alias ids are
  kept (the mission keeps them). **verified** (mission).

## Shared record families (where each is documented)

| family | records | file |
|---|---|---|
| quests and Story Manager | QUST, SMBN, SMQN, SMEN | [quests.md](quests.md) |
| dialogue and voice | DIAL, INFO, DLBR, SCEN, VTYP, SPCH (SF) | [dialogue.md](dialogue.md) |
| companions | AFFE (SF), ASTP (FO4), quests | [companions.md](companions.md) |
| actors | NPC_, RACE, LVLN, CLAS, OTFT, HDPT | [actors-and-npcs.md](actors-and-npcs.md) |
| AI | PACK, IDLM, CSTY | [ai-packages-and-schedules.md](ai-packages-and-schedules.md), [combat-detection-stealth.md](combat-detection-stealth.md) |
| factions and crime | FACT, RELA (FO4) | [factions-crime-relationships.md](factions-crime-relationships.md) |
| stats and effects | AVIF, PERK, MGEF, SPEL, ENCH, ALCH | [special-perks-leveling.md](special-perks-leveling.md), [health-damage-effects.md](health-damage-effects.md) |
| items and crafting | WEAP, ARMO, AMMO, MISC, CMPO (FO4), IRES (SF), OMOD, COBJ | [items-crafting-modding.md](items-crafting-modding.md) |
| world | WRLD, CELL, REFR, LAND (FO4), NAVM, LCTN, LCRT | [world-cells-navigation.md](world-cells-navigation.md) |

## Port status and links

- The converter writes Starfield records through Mutagen (dotnet/*), with deterministic FormIDs (#394) and per-type
  translators. The record-level gap was measured on Oct 6 (FORMAT-GAP.md).

## Open questions and cheap checks

- Diff the **parameter types** of the 458 shared condition functions (xEdit tables; cloud, minutes).
- Decide and record the **naming rule** for converted editor ids and scripts (prefix or Papyrus namespace folder) in
  docs/ai/decisions.md before the first bulk script conversion.
- Scan Fallout4.esm plus DLC for uses of the 21 FO4-only condition functions (counts tell how much hand work there is).

## Sources

- xEdit condition tables and VMAD: https://github.com/TES5Edit/TES5Edit/blob/dev-4.1.6/Core/wbDefinitionsFO4.pas and
  .../wbDefinitionsSF1.pas
- Repo: docs/FORMAT-GAP.md, docs/measurements/*.json, docs/spikes/S2-S4-S9-plugin-units-loading.md.
