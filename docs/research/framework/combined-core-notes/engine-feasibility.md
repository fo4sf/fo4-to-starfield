# Combined core: engine feasibility on Starfield (CE2)

Owner: Combined core thread, research worker (Claude-cloud), 2026-10-19. Groundwork item G4 of
[../combined-core.md](../combined-core.md). Labels per docs/ai/research-log.md: **verified** (with path or URL),
**supported hypothesis**, **unresolved**. Paths without a prefix are under `/mnt/project-files/research/`.
Nothing here is decided; it feeds CC-02 and the pillar questions.

## In short

- **Every pillar can be built from CE2 parts we already map**: quests and aliases, globals, Story Manager Script
  Events, FACT relations, LCTN keyword data and linked locations, conditioned leveled lists, packages, Gameplay
  Options. None needs Starfield's outposts, crew or ships. The hard parts are scale (Papyrus speed, arrays, save
  size) and off-screen actors, not missing record types.
- **Correction to CC-02's option B/C (verified): SFSE has no working co-save.** Serialization was disabled in 0.2.12
  and is still off in 0.2.21 (https://raw.githubusercontent.com/ianpatt/sfse/master/sfse_whatsnew.txt;
  engine-mechanics/saves-and-new-game.md). **But** SFSE's messaging interface sends `kMessage_PreSaveGame`,
  `kMessage_PostSaveGame`, `kMessage_PreLoadGame`, `kMessage_PostLoadGame` to plugins with the save name as data
  (**verified**: https://raw.githubusercontent.com/ianpatt/sfse/master/sfse/PluginAPI.h lines 103-110;
  `sfse/Hooks_Serialization.cpp` lines 35-54 dispatch them with `a_name`). So our plugin can write its **own sidecar
  file keyed to the save name**. That is a workable "co-save of our own", with risks listed under system 1.
- **Recommended shape (supported hypothesis): C', a hybrid with a Papyrus floor.** The small, story-relevant state
  (holder per place, reputation per faction, settlement stage) lives in records the save already keeps (globals,
  LCTN keyword data, quest variables), so conditions, dialogue and leveled lists read it with no SFSE. The SFSE plugin
  holds the bulk simulation (squads, stocks, routes, event queue) in a sidecar and pushes results into that floor.
  If SFSE breaks after a game patch (it has twice, engine-mechanics/papyrus-and-script-extenders.md), the world
  freezes instead of corrupting.
- **The biggest engine gap for territory: our interiors have no locations** (no XLCN on converted interior cells,
  **verified**, framework/interiors.md section 4). Territory is per location, so interiors D1 (an LCTN per interior)
  is a hard prerequisite, as combined-core.md already notes.
- `src/fo4sf/core/` in the repo is the **build/test orchestrator** (state model, ledger, importers; "Pure Python, no
  game or engine imports", **verified**, `src/fo4sf/core/__init__.py`), not game runtime. Nothing below goes there.

## Building blocks shared by all systems

| Block | What it gives us | Label |
|---|---|---|
| `GLOB` + condition `GetGlobalValue` (74) | cheap state readable by every condition (dialogue, packages, LVLI entries, SM nodes) | **verified** (xEdit `wbDefinitionsSF1.pas` dev-4.1.6, condition table; `GlobalVariable` script identical to FO4, engine-mechanics/starfield-systems-to-reuse.md, PC job 16) |
| Location keyword data: `Location.Get/Set/ModifyKeywordData`, conditions `GetKeywordDataForLocation` (606), `GetKeywordDataForCurrentLocation` (651), `LocationHasKeyword` (562), `IsLocationLoaded` (625) | one float per (location, keyword): holder id, stage, threat, without a global per place | conditions **verified** (xEdit SF1); Papyrus functions **verified by inference**: FO4's Location script lists them (https://falloutck.uesp.net/wiki/Location_Script_(Papyrus)) and PC job 15 found only 4 FO4-only Location names, all "cleared" (engine-mechanics/papyrus-and-script-extenders.md); persistence across save/load **unresolved** (probe P2) |
| Linked locations: `AddLinkedLocation`, `GetAllLinkedLocations`, `IsLinkedLocation` by keyword | the route graph (supply lines, adjacency for territory) as engine data | same inference as above: **supported hypothesis** until P2 |
| Quest stages, quest variables, condition `GetVMQuestVariable` (629), `GetStageDone` (59) | per-system state and story gates | **verified** (xEdit SF1) |
| Story Manager: Change Location, Location Loaded, **Script Event**, Clear Location (SF) | starting materialization and radiant quests; FO4's Kill/Trespass/Craft events are gone, so we send Script Events | **verified** (engine-mechanics/quests.md, xEdit `wbQuestEventEnum`) |
| Own SM branch under Script Event | Starfield's radiant content never picks our refs, ours never pick theirs | **supported hypothesis** (quests.md; framework/engine-mechanics-notes/quests-dialogue-voice.md R1) |
| Leveled lists with **conditions on each entry** | who spawns at a place follows a global or keyword datum, no script | **verified** that SF LVLI/LVLN carry list and entry conditions (engine-mechanics/leveled-lists-and-encounter-zones.md) |
| FACT XNAM relations, `Faction` script (`SetEnemy`, `SetAlly`, crime gold), `GetFactionRelation` (449) | faction attitudes, changeable at runtime | **verified** (factions-crime-relationships.md; all 23 FO4 Faction functions exist in SF, PC job 16) |
| FACT Herd / Create Group (formation radius), `HEFA` | squads that move together when materialized | fields **verified**, behaviour **supported hypothesis** (starfield-systems-to-reuse.md) |
| Game-time timers (`StartTimerGameTime`), `GetCurrentGameTime` | the coarse simulation tick | **supported hypothesis**: `ScriptObject` FO4-only names are only the 3 looks-menu ones (PC job 15), so FO4's timer API is present; `GetCurrentGameTime` **verified** declared (papyrus-and-script-extenders.md) |
| SFSE custom Papyrus natives | our plugin exposes `FOCC_*` natives to scripts | **verified** "preliminary custom papyrus native function support" (sfse_whatsnew 0.1.1); Cassiopeia registers about 115 natives (papyrus-and-script-extenders.md) |
| Gameplay Options (GPOF) | player-facing switches (survival, story mode, sim speed) without SFSE UI | **verified** pattern used by mods (framework/engine-mechanics-notes/character-systems.md) |

Cross-cutting risks:
- **Papyrus throughput.** Script lag was FO4's worst workshop problem; Workshop Framework needed 10-50 threads
  (**verified**, fo4-systems-internals.md W4). A per-tick loop over hundreds of places in Papyrus is the main
  performance risk (**supported hypothesis**). Mitigation: simulate in the SFSE plugin; Papyrus only applies diffs.
- **Papyrus arrays cap at 128 entries** in FO4-lineage Papyrus (**supported hypothesis** for CE2; unchecked).
  A Commonwealth place table will exceed that; another reason for plugin-side tables.
- **Save bloat.** Starfield saves grow with runtime-made refs; an SFSE save cleaner strips about 40 % and is called
  unsafe by its author (**verified** as described, saves-and-new-game.md). Rule from combined-core.md L3: no permanent
  spawned refs; every `PlaceAtMe` actor is deleted on dissolve.
- **Persistent refs.** Refs held in quest aliases stay persistent and in memory (CE lineage, **supported
  hypothesis**); materialized squads should use aliases only while near, then clear them.
- **Off-screen actors.** FO4 runs its workshop daily update on unloaded settlements, but `CanProduceForWorkshop` is
  valid only while loaded (**verified**, fo4-systems-internals.md W3, falloutck). Real actors far away move at low
  fidelity or not at all (**supported hypothesis**, CE lineage). Design rule: the simulation never depends on an
  unloaded actor doing anything.
- **Starfield leakage.** Any reuse of outposts, crew or Starfield's radiant boards risks Starfield systems acting in
  our world (the fence, starfield-systems-to-reuse.md; the Red Rocket outpost activator crash, quests-dialogue-voice.md R3).

## 1. World-state model (who holds each place)

**Blocks.** Per place: LCTN (with `LocType*` keywords, parent chain, encounter level), a keyword datum
`FOCC_Holder` = faction index, `FOCC_Stage`, `FOCC_Threat`; per faction: a GLOB for strength and reputation. Static
tables (place list, faction index, routes) ship as data: FormLists of LCTN and FACT, linked locations for routes.
Runtime truth: the SFSE plugin's tables, mirrored into the floor above on each tick.

**SFSE.** Natives `FOCC_GetHolder(Location)`, `FOCC_Tick(float days)`, `FOCC_Apply()`; sidecar save
`<save name>.focc` written on `kMessage_PreSaveGame`/`PostSaveGame`, read on `PostLoadGame` (**verified** that the
messages and name exist, PluginAPI.h; the sidecar design is **supported hypothesis**).

**Risks.**
- Sidecar orphans and mismatch: SFSE tells plugins nothing when a save is deleted (`HandleDeleteSave` is internal to
  SFSE's disabled serialization, **verified**, `Hooks_Serialization.cpp` line 60-63); Steam Cloud will not sync the
  sidecar (**supported hypothesis**). Mitigation: store a save-generation counter in a GLOB too; on load, if the
  sidecar's counter differs, rebuild plugin state from the Papyrus floor (lossy but consistent).
- Location data missing on our interiors (**verified**, interiors.md): nothing to hold until D1 lands.
- `GetKeywordData` persistence and whether Starfield's LCTN without a planet parent behaves (interiors.md: what a
  location with no planet parent does is **unresolved**).

**Offline prototype.** (a) Python L1 schema + deterministic L2 on a synthetic seed (G5/G6), unit-tested on Linux.
(b) A synthetic plugin fixture via `dotnet/PluginSpike` (Mutagen): 3 LCTN with linked-location data, 2 FACT,
`FOCC_Holder` keyword, 4 GLOB; test reads them back. (c) Sidecar format and versioning as a pure C++/Python codec with
round-trip tests. **Needs the PC:** P1-P3 below.

## 2. Off-screen faction simulation (abstract squads)

**Precedent (verified).** A-Life keeps AI within about 150 m "online" and everything beyond "offline", updated on a
graph as game time passes, partly "smoke and mirrors"
(https://gamedeveloper.com/design/a-life-an-insight-into-ambitious-ai). Anomaly's Warfare classes points as bases,
resources, territories; non-base points fall to one squad, bases need more squads than the holder; respawn time
depends on bases held; offline squads fight via an `offline_combat_simulator`; story NPCs are excluded from offline
combat (https://www.moddb.com/mods/stalker-anomaly/addons/warfare-alife-overhaul).

**Blocks.** Squads are rows (faction, strength, position = place id, goal, ETA), never actors. Materialization (L3):
on Story Manager **Change Location / Location Loaded** (or a cheap game-time poll of the player's location against
the route graph) a FOCC quest starts, fills **Create Reference to Object** aliases from FACT-specific LVLN at
location-ref-type markers (LCRT, `XLRT`), applies Travel/Patrol/Sandbox packages (templates exist in SF,
**verified**, ai-packages-and-schedules.md), Create Group formation for movement. Dissolve on leaving: write
survivors back to the row, delete actors, quest stops.

**SFSE.** The offline loop, pathing on the route graph and combat resolution belong in the plugin (cost). A Papyrus
version for a 20-place Commonwealth slice is possible (**supported hypothesis**) and is the fallback.

**Risks.** Spawning mid-view (pick markers outside line of sight; FO4 attack markers `WorkshopLinkAttackMarker` are
the pattern, fo4-systems-internals.md); alias quests that fail to fill silently (CE lineage, **supported
hypothesis**); actor-count budgets; Starfield's own spawns in our worldspace (**unresolved**,
companions-ai-factions-combat.md H7).

**Offline prototype.** The L2 squad sim in Python: seed, 2 factions, 10 places, assert determinism and that a
squad's strength is conserved across materialize/dissolve. Plugin fixture: one QUST with 4 "Create Reference to
Object" aliases (fill type 4, **verified** enum, quests.md) and one SMQN under our own SMBN. **PC:** P4, P5.

## 3. Territory capture

**Blocks.** Holder change = set `FOCC_Holder` keyword datum (and GLOB mirror) + swap who appears: LVLN entries
conditioned on `GetKeywordDataForCurrentLocation FOCC_Holder == n` so spawns follow the holder with **no script**
(entry conditions **verified**; the specific condition on an LVLN entry **unresolved** until P6). Cell ownership via
`Cell.SetFactionOwner` (FO4's `Cell` script has 0 names missing in SF, PC job 15, so **supported hypothesis** it
exists). Banners/props: enable-parent markers per faction (`Enable`/`Disable` on one parent ref per holder).
Map overlay: none native; terminal/Pip-Boy page later. "Cleared" state: FO4's `IsCleared/SetCleared` are missing in
SF (**verified**, PC job 15); SF has `GetLocationExplored` (250, **verified** xEdit) and SM "Clear Location (SF)"; we
keep our own cleared datum (papyrus-and-script-extenders.md plan).

**SFSE.** Not needed for the flip itself. Changing LCTN encounter level or parent at runtime needed F4SE in FO4
(`SetEncounterZone`, `SetParent`, falloutck Location page) and has no CE2 native (**supported hypothesis**); avoid it.

**Risks.** Story places (CC-21: locked while a story runs, a GLOB per place on the capture rule); settlement
registration can't be added at runtime: adding `LocTypeWorkshopSettlement` triggers `ResetWorkshop()` in FO4
(**verified** as reported, fo4-systems-internals.md), so every capturable settlement is registered at build time.
Faction relations set at runtime with `SetEnemy`/`SetAlly` are global per faction, not per place.

**Offline prototype.** Converter rule test: from a place table emit LVLN with one conditioned entry per faction and
check the conditions in a Mutagen round-trip. **PC:** P6.

## 4. Cross-region reputation (NV-style fame and infamy)

**Precedent (verified).** NV keeps two scores per faction and town, fame and infamy, each with four levels and
faction-specific thresholds; the pair maps to titles (Accepted ... Vilified, mixed ones like Wild Child); high
infamy means denied service, hit squads or attack on sight
(https://fallout-archive.fandom.com/wiki/Fallout:_New_Vegas_reputations); the engine had a reputation record and
`GetReputation <faction> <fame/infamy>` (https://geck.uesp.net/wiki/GetReputation). Neither FO4 nor Starfield has a
reputation field in FACT (**supported hypothesis**, starfield-systems-to-reuse.md).

**Blocks.** Two GLOBs per (faction, region): `FOCC_Fame_BoS_CW`, `FOCC_Infamy_BoS_CW`; a third GLOB holds the
derived tier for cheap conditions. Gains from our Script Events (kills, quests, trade). Effects: vendor conditions
(VEND/PLVD conditions, **verified** fields, economy-vendors-barter.md), dialogue conditions, FACT relation to
PlayerFaction flipped to Enemy at the hostile tier (`SetEnemy`), hit squads from system 2. Cross-region spread:
the simulation copies a share of a region's change to linked regions over time (route graph). Starfield's DNAM
faction-type keyword may feed Starfield's own reputation/bounty UI (**unresolved**, S5) so we leave it empty.

**SFSE.** None needed. An own UI page is optional (Pip-Boy rebuild).

**Risks.** Global count (factions x regions x 3, fine for GLOBs); FO4's Kill Actor SM event is gone, so kills are
counted by our `OnDeath`/`OnKill` scripts (quests.md); relation flips are global, so "hated in the Mojave, liked in
the Commonwealth" needs per-region proxy factions or per-NPC condition gating (**unresolved** design point).

**Offline prototype.** Pure table test of tier derivation and spread; plugin fixture with the GLOBs and one
conditioned INFO. **PC:** one vendor refusing service at a tier (P7).

## 5. Settlement growth (population, roles, needs, build stages)

**Blocks.** Settlements stay FO4 workshops on Starfield's `WorkshopKeyword` ACTI (29 promoted, offline only,
**verified**, engine-mechanics/workshop-and-settlements.md). Rules are ours (no `WorkshopParentScript` in SF,
**verified**, PC job 15). SF keeps `GetWorkshopResourceObjects`, `CanProduceForWorkshop`, `OnWorkshopObjectPlaced`,
`OnWorkshopObjectRemoved`, `OnWorkshopNPCTransfer` (**verified** as listed,
https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-ObjectReference via fo4-systems-internals.md). Population,
needs and happiness: numbers in our tables (FO4 values are **verified** as documented, falloutck Workshop); per
settlement in AVs on the workbench ref or keyword data (S1, open). Roles: settler actors with our faction plus
packages on owned furniture (beds, crops, guard posts) via `XOWN`; Starfield crew assignment fenced out (S4).
**Build stages without player building:** pre-authored stage layers per settlement as enable-parent groups
(stage 0 ruins, 1 shacks, 2 walls ...), switched by `FOCC_Stage`; this avoids runtime `PlaceAtMe` of hundreds of
statics. Sim Settlements 2 builds plots at runtime; it requires Workshop Framework and its permissions forbid
conversion (**verified**, workshop-items-economy.md): copy the pattern, not files.

**SFSE.** None for stages. Needed only if we must place objects in bulk at runtime (the threading cost WF hit).

**Risks.** Precombined/previs geometry broken by enabling/disabling or scrapping vanilla refs ("scrap everything"
breaks precombines, **verified** as SS2 known issue, engine-mechanics.md); converted worlds may carry no precombines
yet, which helps. Settler count vs actor budget; settlers are persistent refs (save size). Stage layers add records,
not save data (**supported hypothesis**: unchanged disabled refs cost little in saves).

**Offline prototype.** Growth rule in the Python L2 (food/water/beds/defence → population, stage thresholds);
converter test that emits one enable-parent marker per stage and links child refs. **PC:** P8 (stage swap, save
size before/after).

## 6. Supply lines and trade

**Blocks.** Routes = linked locations (keyword `FOCC_Route`) plus a route table with distance and danger. Goods are
plugin-side stocks per settlement, not items. Caravans materialize like squads (system 2) when the player is on a
route: a brahmin and guards with a Travel package between route markers. Trade effects: vendor stock via conditioned
LVLI entries (`GetKeywordDataForLocation FOCC_Supply`), prices via vendor perks/GMSTs (economy-vendors-barter.md).
Raids: a caravan row meets a hostile squad row in L2; the player may meet it in L3.

**Starfield natives considered.** Cargo links ship resources "in real-time" by an automated cargo ship, in Universal
Time (**verified**, https://starfieldwiki.net/wiki/Starfield:Outposts); `OnWorkshopCargoLinkChanged` exists
(**verified** as listed). The Shared Outpost Container (Free Lanes, 2026-04-07) moves items between outposts
(**verified**, workshop-items-economy.md). Reuse outside outposts is **unresolved** (T2) and pulls in ships; default:
our own caravans (CC-13 default).

**SFSE.** Stock tables and route flow in the plugin; the FO4-style "pick a settlement" menu is gone
(`OpenWorkshopSettlementMenu` missing, **verified** PC job 15), so a MESG/terminal list first, SFSE menu later (W7).

**Risks.** Real provisioners walking unloaded (FO4's model) are exactly the off-screen-actor risk; keep them abstract.
Pathing for materialized caravans on our converted navmesh (navmesh converts, **verified** offline,
world-cells-navigation.md; in-game travel over long distances **unresolved**).

**Offline prototype.** Flow/conservation tests in Python (goods in = goods out + losses); plugin fixture with two
LCTN linked by `FOCC_Route`. **PC:** P9.

## 7. Dynamic events and news

**Blocks.** L2 emits events (place fell, caravan lost, settlement grew). Presentation:
- **Terminal and notes first:** TMLM terminal menus with entries conditioned on GLOB/keyword data
  (FO4 TERM maps to TMLM, papyrus-and-script-extenders.md); Message boxes/notifications. No voice needed.
- **Radio:** the mechanism carries (RADR receiver, scene Radio action, `IsPlayerRadioOn`, `GetPlayerRadioFrequency`
  614, **verified**, radio-music-sound.md); a station is a scene loop with phases gated by `GetVMQuestVariable`
  (**verified**, fo4-systems-internals.md). Spoken news needs voiced lines: limited to recombining existing FO4 lines
  (voice is an open legal item, combined-core.md), so radio news is **music/jingle cues plus a terminal or HUD
  text**, unless a later decision allows more. SFSE radio players exist (Star Radio Player etc., **verified** as
  mod pages, radio-music-sound.md) if Wwise gets in the way.
- **Radiant quests from events:** our Script Event → our SM branch → quest with "From Event" aliases.

**SFSE.** Optional (HUD text widget, radio playback).

**Risks.** Spam (rate-limit in L2), stale news after load (sidecar mismatch), `SendStoryEvent` on `Keyword` not yet
confirmed in SF scripts (**unresolved**, starfield-systems-to-reuse.md; a probe compile settles it).

**Offline prototype.** Event-to-message templating in Python with tests; plugin fixture TMLM with 3 conditioned
entries. **PC:** P10.

## 8. Survival as an optional module

**Blocks.** FO4 Survival is mostly script: `HC_Manager` quest, rules loaded from a "Hardcore Rules" FormList
(**verified**, fo4-systems-internals.md, Nexus FO4 46306). Rebuild as our quest + SPEL/MGEF needs + AVs (effects
pipeline same in both games, **verified**, health-damage-effects.md); switches as GPOF options (V3). Tie to economy:
food and water items come from settlement stocks via vendor lists. Starfield Sustenance must be off; needs mods
already require it (**verified** as mod pages, character-systems.md). Fast-travel block: `EnableFastTravel` exists
(**verified** name, world-cells-navigation.md).

**SFSE.** Bed-only saving has no known CE2 native (**unresolved**, V2/V5); likely an SFSE hook or a softer rule.
State must live in AVs/globals, not a co-save (**verified** constraint, engine-mechanics.md).

**Risks.** Clash with Starfield afflictions and environmental damage (fence, health-damage-effects.md); timers in
menus (`WaitMenuMode` missing, PC job 15).

**Offline prototype.** Rules table + FormList fixture; needs-decay math in Python. **PC:** V3, V5.

## 9. Chronological story mode switch

**Blocks.** A start setting chosen in the new-game flow (NG-20 menu entry; Starfield's own `ShowRaceMenu`, start
quest pattern, saves-and-new-game.md) sets `FOCC_StoryMode` GLOB. Each game's opening quest has an SM/start condition
on it and on the previous story's completion stage (`GetStageDone`). "Mute the sandbox" = L2 rules and SM nodes
conditioned on a `FOCC_StoryActive` GLOB plus the CC-21 story-place lock. Dates (2277, 2281, 2287) are just order.

**SFSE.** None. **Risks.** Story quests that assume a fresh world (FO4's MQ102 stages many systems key off,
**verified** lesson, saves-and-new-game.md); other worlds are gated by their converters and legal status.

**Offline prototype.** Plugin fixture: 2 dummy story quests chained by a stage condition and a GLOB; a test checks the
conditions. **PC:** one start with the switch on.

## SFSE summary

| Need | Why | Fallback without SFSE |
|---|---|---|
| Simulation tables + tick (systems 1, 2, 6) | Papyrus speed and array caps | 20-place Papyrus slice, frozen world |
| Sidecar save (`PreSaveGame`/`PostLoadGame`) | no co-save API | Papyrus floor only |
| Custom natives `FOCC_*` | scripts read plugin state | globals and keyword data mirrored per tick |
| Optional: settlement picker menu, HUD news, radio playback, bed-only saves | missing natives/UI | MESG lists, terminals, softer rules |

Version risk: game patches broke most SFSE plugins twice; SFSE is Steam-only today (**verified**,
papyrus-and-script-extenders.md). Keep the plugin small and Address-Library based.

## PC probes (input for G8; none run)

| # | Probe | Answers |
|---|---|---|
| P1 | Plugin writes a sidecar on PreSaveGame, reads on PostLoadGame; save, load, load another save, delete a save | sidecar viability, orphan handling |
| P2 | `SetKeywordData` on our LCTN, leave, save, reload, `GetKeywordDataForLocation` in console | keyword-data persistence, linked locations |
| P3 | Our LCTN without planet parent vs chained to the overlay location: keyword data, explored state | location data on our interiors |
| P4 | Materialize 3 squads (alias quest) at a marker on Change Location, dissolve, 20 cycles, save size | spawn reliability, save bloat |
| P5 | Papyrus tick over 50 places, timed with `Utility.GetCurrentRealTime` | script latency baseline (record per docs/ai/optimization.md) |
| P6 | LVLN entry conditioned on `GetKeywordDataForCurrentLocation`; flip datum, reset cell | data-only territory spawns |
| P7 | Vendor refuses service by fame/infamy tier GLOB | reputation effects |
| P8 | Enable-parent stage swap at a converted settlement; save size before/after | build stages |
| P9 | One materialized caravan on a Travel package across 4 exterior cells | long-route pathing |
| P10 | `Keyword.SendStoryEvent` compile + our SM branch starts a quest | event plumbing |

## Sources

- Project research (cited inline): engine-mechanics/{workshop-and-settlements, factions-crime-relationships,
  starfield-systems-to-reuse, quests, ai-packages-and-schedules, leveled-lists-and-encounter-zones,
  economy-vendors-barter, saves-and-new-game, papyrus-and-script-extenders, radio-music-sound, world-cells-navigation,
  health-damage-effects}.md; framework/{engine-mechanics, interiors, combined-core}.md;
  framework/engine-mechanics-notes/{fo4-systems-internals, workshop-items-economy, character-systems,
  quests-dialogue-voice, companions-ai-factions-combat, tools-and-scripting}.md.
- SFSE: https://raw.githubusercontent.com/ianpatt/sfse/master/sfse_whatsnew.txt,
  https://raw.githubusercontent.com/ianpatt/sfse/master/sfse/PluginAPI.h,
  https://raw.githubusercontent.com/ianpatt/sfse/master/sfse/Hooks_Serialization.cpp (read 2026-10-19).
- xEdit: https://github.com/TES5Edit/TES5Edit dev-4.1.6 `Core/wbDefinitionsSF1.pas` (condition indices above).
- https://falloutck.uesp.net/wiki/Location_Script_(Papyrus); https://geck.uesp.net/wiki/GetReputation;
  https://fallout-archive.fandom.com/wiki/Fallout:_New_Vegas_reputations;
  https://gamedeveloper.com/design/a-life-an-insight-into-ambitious-ai;
  https://www.moddb.com/mods/stalker-anomaly/addons/warfare-alife-overhaul;
  https://starfieldwiki.net/wiki/Starfield:Outposts.
