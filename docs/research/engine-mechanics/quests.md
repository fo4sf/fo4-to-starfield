# Quests and missions (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: **verified** /
**supported hypothesis** / **unresolved** (docs/ai/research-log.md).

Main sources: xEdit record definitions `wbDefinitionsFO4.pas` and `wbDefinitionsSF1.pas` (TES5Edit dev-4.1.6, read
on 2026-10-19; "xEdit" below), the project's own reading of Fallout4.esm (docs/spikes/B4-mission-anatomy.md) and the
converted mission (docs/mission/when-freedom-calls.md). xEdit definitions are reverse engineered, but its SF1 file
marks QUST as "subrecords checked against Starfield.esm".

## In short

- Both engines run quests the same way: a **QUST** record holds stages, log entries, objectives and aliases; Papyrus
  scripts (a quest script plus stage fragments) do the work; the **Story Manager** starts radiant quests from game
  events. Starfield kept the whole model and added to it. **verified** (xEdit, both QUST layouts side by side)
- What changes is the edges: FO4's quest **type** is a fixed enum (Main, Brotherhood, Institute, Minutemen, Railroad,
  Misc, Side, DLC01-07); Starfield uses a **Quest Type keyword** (QTYP) and a **Quest Faction keyword** (FTYP). Rewards
  move from a single XP global (FO4 XNAM) to per-stage reward blocks (XP, currency, items, affinity). **verified**
- Alias fill types are the same ideas, **reordered**: Starfield inserts "Create Matching Ref" as fill type 5, so FO4's
  "Find Matching Reference" (5) becomes 6, and the match sub-types are reordered too. A converter that copies raw
  bytes breaks; one that maps by meaning (Mutagen's typed records) is fine. **verified** (xEdit)
- Starfield's Story Manager lost most of FO4's "crime and social" events: Kill Actor, Arrest, Jail, Escape Jail, Pay
  Fine, Served Time, Trespass, Bribe, Intimidate, Flatter, Craft Item, Dead Body, Cure, Infect, Pickpocket, Player
  Activate Actor, Change Relationship Rank. FO4 radiant quests that start from those events must be restarted from a
  **Script Event** (SCPT) sent by our own script. **verified** for the enum (xEdit `wbQuestEventEnum` marks each event
  per game); which FO4 quests use them is **unresolved** (one record scan).
- Verdict: **translate as data** (stages, logs, objectives, aliases, conditions) plus **rebuild the scripts**
  (fragments recompiled against Starfield's Papyrus, with a shim for FO4-only natives). The project's mission
  (#353) already proved the shape in game: one QUST, 6 stages, 3 objectives, 10 aliases, a script. **verified**

## How Fallout 4 does it

**Record: QUST** (1,336 in Fallout4.esm). Layout (xEdit):

| part | subrecords | meaning |
|---|---|---|
| header | EDID, VMAD (fragmented: quest script plus stage fragments and alias scripts), FULL (name shown in the Pip-Boy) | |
| general | DNAM: flags (Start Game Enabled, Starts Enabled, Run Once, Allow Repeated Stages, Displayed In HUD, Keep Instance, Want Dormant, Has Dialogue Data ...), priority, delay time, **Type** enum | priority decides which quest's dialogue wins |
| story manager | ENAM event (4-char code), "Story Manager Conditions" block | which event can start the quest, and when |
| other | LNAM location, XNAM Quest Completion XP (a GLOB), QTGL text display globals (numbers shown in log text, e.g. `MQ102FirstRaiderCount`), FLTR editor folder, "Quest Dialogue Conditions" (apply to every INFO in the quest) | |
| stages | INDX (index, flags Run On Start / Run On Stop / Keep Instance Data), per log entry: QSDT (Complete / Fail Quest), conditions, CNAM log text, NAM0 next quest | the Pip-Boy journal |
| objectives | QOBJ index, FNAM flags, NNAM display text, targets QSTA (alias, flags Compass Ignores Locks / Hostile / Straight Line Pathing, keyword) with conditions | compass and map markers point at alias targets |
| aliases | ANAM next alias id, then reference aliases, location aliases, ref collection aliases | see below |
| end | NNAM description, GNAM quest group keyword, SNAM SWF file | |

**Aliases** (the heart of a Bethesda quest). A reference alias is a named slot that the quest fills when it starts.
Fill types (FO4 order): 0 Specific Reference, 1 Unique Actor, 2 Location Alias Reference (a ref of a location ref
type, LCRT, in a location alias), 3 External Alias Reference (another quest's alias), 4 Create Reference to Object (at
or in an alias, with a level), 5 Find Matching Reference (near an alias by linked ref, from the Story Manager event's
data, or closest to an alias), all with match conditions. While a ref sits in an alias it gets the alias's keywords,
inventory, spells, factions, **AI packages** (ALPC), forced voice type, display name, death item and override package
lists (spectator, observe dead body, guard warn, combat). Flags such as Optional, Reserves Reference, Allow Reuse,
Essential, Quest Object, Allow Disabled, Stores Text live in FNAM. **verified** (xEdit)

**Scripts.** Each quest can carry a quest script (extends `Quest`), one generated fragment script for all stages
(named like `QF_Min00_001A001C`), and scripts on aliases (extend `ReferenceAlias` / `LocationAlias` /
`RefCollectionAlias`). Stage fragments are where most story logic lives: `SetStage`, `SetObjectiveDisplayed`,
`SetObjectiveCompleted`, alias `ForceRefTo`, `Enable`, `EvaluatePackage`, `Start()` other quests. The mission spike
read these from `.pex` call lists. **verified** (B4 spike)

**Story Manager.** SMBN (branch), SMQN (quest node, 219 in FO4), SMEN (event node) form a tree per event type. When
the engine fires an event (for example Change Location, Actor Dialogue, Kill Actor, Script Event), it walks that
event's tree and starts the first eligible quest whose conditions pass, filling "From Event" aliases from the event
data. Radiant quests (Minutemen settlement requests, Brotherhood repeatables, random encounters) start this way.
**verified** for the records (xEdit); the behaviour is the documented CK model (Skyrim/FO4 CK wiki).

**Quest structure in practice.** One "mission" in the Pip-Boy is often several quests: When Freedom Calls is four
(`Min00` for the journal, `MQ102` the driver, `DN092` the fight, `DialogueConcordArea` the talk), chained by stage
fragments. **verified** (B4 spike 1.1). Quest priority and "Start Game Enabled" quests (the always-on dialogue quests)
matter as much as the story quests.

**UI.** The Pip-Boy Data tab shows quests with "Displayed In HUD"; objectives show on the HUD and compass; quest
targets need navmesh to path markers. FO4 XP comes from `XPFaction`/`XPMiscQuest`-style globals in XNAM.
**supported hypothesis** for the global names beyond `XPFaction` (seen in B4).

## How Starfield does it

**Record: QUST** (2,077 in Starfield.esm). Same skeleton; the differences that matter for a converter (xEdit):

| change | FO4 | Starfield |
|---|---|---|
| DNAM flags | 16-bit, 16 flags | 32-bit; adds Ship Dialogue Only, Can Be Rejected, Audio Log Only, Don't Stop Interrupt Packages On Alias Fill, Don't Dump Old Location Event Parameter |
| quest type | enum in DNAM | QTYP Quest Type keyword, FTYP Quest Faction keyword |
| new top-level | | QTLM quest time limit (GLOB), QSRC source quest, QDUP dialogue list, NAM3 summary, SCCM script comment, "Mission Board Info" (QMTY mission type, QMSU summary, up to 6 detail lines, keywords) |
| completion XP | XNAM GLOB on the quest | per stage "Stage Complete Data": reward blocks with QRXP XP GLOB, QRCR currency GLOB, QRRD items, conditions; NAM1 **Affinity Change** (AFFE) |
| stage flags | Run On Start/Stop, Keep Instance Data | adds Run On Timer End, Start Quest Timer, Ready To Display On UI |
| log entry | | adds SCFC script flag comment |
| description | NNAM description | commented out in xEdit (not read) |
| alias fill types | 0-5 as above | 0 Specific Reference, 1 Unique Reference (adds ALUB base form), 2 Location Alias Reference, 3 External Alias, 4 Create Reference to Object, **5 Create Matching Ref (new)**, **6 Find Matching Reference** (sub-types reordered: In Collection, Closest To, From Event, Near Alias with optional ALNR ref type) |
| alias extras | | ALFG orbit altitude mult, ALLR legendary rank |

**Story Manager.** SMBN, SMQN (354), SMEN are kept. The event list (xEdit `wbQuestEventEnum`, which marks each event per
game) keeps for Starfield: Crime Gold, Actor Dialogue, Actor Hello, Player Add Item, Attraction Object, Assault Actor,
Change Location, Hack Computer, Iron Sights, Location Loaded, Increase Level, Lock Pick, On Actor Attach, Player Remove
Item, **Script Event**, Trigger Mine Explosion; it adds Ship Docking, Ship Landing and "Clear Location (SF)". It drops
everything listed in "In short". **verified** (xEdit). Starfield's own radiant content (mission boards, bounty boards,
procedural POI quests) runs on this plus the Mission Board block. **supported hypothesis** (record layout; not read
from scripts yet).

**Scripts.** Same model: quest script, fragments, alias scripts. Starfield's Papyrus adds language features but keeps
`Quest`, `ReferenceAlias`, `SetStage`, `SetObjectiveDisplayed` and the rest of the core quest API. The project's
mission script `FO4SF_Min00Quest.psc` compiled against Starfield's sources and ran in game. **verified** (mission PASS
on v6). See [papyrus-and-script-extenders.md](papyrus-and-script-extenders.md) for the native-function gap.

**UI.** Starfield's mission menu groups by Quest Type keyword (Main, Faction, Misc, Activities, Missions) and uses
the quest's faction keyword for the faction tab; a FO4 quest with no QTYP lands in a default group. **supported
hypothesis** (the menu's grouping rule is not read from the UI files; one in-game look at the mission's entry answers
it).

## Mapping for the port

| FO4 piece | Starfield counterpart | verdict | notes |
|---|---|---|---|
| QUST header, flags, priority | QUST DNAM (wider flags) | translate | flag bits 0-15 keep their meaning (xEdit) |
| Type enum (Main, factions, DLC) | QTYP + FTYP keywords | translate to **our own** keywords | do not reuse Starfield's faction keywords; the mission menu needs a group for each (check how unknown keywords display) |
| XNAM completion XP | per-stage reward block on the completing stage | translate | XP values follow FO4's curve; see [special-perks-leveling.md](special-perks-leveling.md) |
| stages, log entries, QTGL | same | data copy | strings move to our own STRINGS files |
| objectives and targets | same | data copy | targets need the alias ids kept |
| reference/location/collection aliases | same, reordered fill enum | translate | map by meaning; FormIDs through the project's deterministic map |
| alias packages, factions, spells, keywords | same fields | translate | the forms they point at must be converted first |
| Story Manager tree | SMBN/SMQN/SMEN | translate, **own tree** | our nodes live under our own branch nodes so Starfield's radiant quests never pick our refs and ours never pick theirs |
| SM events Kill/Arrest/Jail/Trespass/Craft/... | none | **rebuild** | send a Script Event from a script that watches OnDeath, OnItemAdded etc.; or start the quest from the script directly |
| quest script, stage and alias fragments | Papyrus, same API core | **rebuild** (recompile) | sources: FO4 CK's Base.zip, or decompile; shim FO4-only natives |
| Pip-Boy quest display | Starfield mission menu | reuse first | a faithful Pip-Boy is a separate UI job ([ui-pipboy-hud-menus.md](ui-pipboy-hud-menus.md)) |
| quest-start dialogue flags ("Add Idle topic to Hello", Has Dialogue Data) | same bits | data copy | |

## What must be rebuilt, and what needs SFSE or the Creation Kit

- **Rebuild:** every fragment and quest script (8,369 `.pex` in FO4's base game, quests are a large share); Story
  Manager starts for the dropped events; anything that calls FO4-only natives (workshop, Pip-Boy, power armor, VATS).
- **Creation Kit (Starfield):** not needed for quest records (Mutagen writes them). Needed or very useful for
  compiling Papyrus (the compiler ships in Starfield's Tools folder with the CK) and for generating lip files for
  quest dialogue (see [dialogue.md](dialogue.md)).
- **SFSE:** not needed for quests themselves. Only for natives Starfield lacks that a shim cannot fake in Papyrus.

## Port status and links

- Done: the cut-down When Freedom Calls (`FO4SFMission.esm`, PR #353, PASS on v6): own QUST, stages, objectives,
  aliases, an own faction for Preston (v6e, untested). docs/mission/when-freedom-calls.md.
- The new game (draft PR #393) holds FO4's `MQ00` and `MQ101` equivalents in `FO4SFNewGame.esm`; see
  [saves-and-new-game.md](saves-and-new-game.md).
- The quest engine probe (`FO4SFQuestProbe.esm`, `docs/questprobe/engine-questions.md` on the PR #393 branch, built
  offline, not installed) answers five open behaviours in one plugin: stage fragments, OnStageSet (the mission's never
  fired), markers following a forced alias, our own quest-type heading, and our own Story Manager branch under
  Starfield's Script Event node with "Shares Event" set.
- Scale, order and fencing: [../next-phase/npcs-ai-factions-dialogue-quests.md](../next-phase/npcs-ai-factions-dialogue-quests.md)
  sections 6 to 9.

## Open questions and cheap checks

- Which FO4 SMQN nodes use the dropped events (Kill Actor, Craft Item, Trespass ...): one record scan of SMEN/SMQN
  ENAM over Fallout4.esm and the DLC (cloud, from the repo's walker, if the esm is reachable; else a PC read-only job).
- How Starfield's mission menu shows a quest whose QTYP keyword is not one of Starfield's: one look at the mission's
  entry in game (the mission plugin may already answer it).
- Whether FO4's "Keep Instance" and "Want Dormant" flags behave the same in CE2: **unresolved**; low risk.
- Quest **objective markers** across our converted world: they need navmesh and the world-identity fix (the merge
  probe, see project memory); test with the mission's markers after v6e.

## Sources

- xEdit definitions: https://github.com/TES5Edit/TES5Edit/blob/dev-4.1.6/Core/wbDefinitionsFO4.pas (QUST),
  .../wbDefinitionsSF1.pas (QUST, `lReferenceAlias`), .../wbDefinitionsCommon.pas (`wbQuestEventEnum`).
- Fallout 4 CK wiki, Quest: https://falloutck.uesp.net/wiki/Quest ; Skyrim CK Alias tab and radiant tutorial (same
  model): https://ck.uesp.net/wiki/Alias , https://ck.uesp.net/wiki/Bethesda_Tutorial_Radiant_Quests
- Starfield quest stage behaviour (player-facing): https://dev.starfieldwiki.net/wiki/Starfield:Tutorial_Quest
- Repo: docs/spikes/B4-mission-anatomy.md, docs/mission/when-freedom-calls.md, docs/measurements/*.json.
