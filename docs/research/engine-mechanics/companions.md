# Companions and followers (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: **verified** /
**supported hypothesis** / **unresolved**.

Read with [quests.md](quests.md), [dialogue.md](dialogue.md) and
[ai-packages-and-schedules.md](ai-packages-and-schedules.md): a companion is a quest, an alias, packages and a lot
of dialogue, plus an affinity layer on top.

## In short

- Both engines build companions from the same parts: a **follower framework quest** that holds the current follower
  in an alias (the alias carries the follow package, the teammate state and the command dialogue), **per-companion
  quests** for recruitment, talks and personal stories, and an **affinity** score that unlocks talks. **supported
  hypothesis** (FO4 CK community docs; Starfield mods and xEdit); the exact quest editor ids per game are listed below
  with their own labels.
- FO4's affinity is **scripted**: `CompanionActorScript` on each companion, the hidden actor value `CA_Affinity`
  (cap reported as 1100), reactions sent as **keywords** (`CA_Event_Likes`, `CA_CustomEvent_CaitLikes`,
  `CA__CustomEvent_MinSettlementHelp` ...), a size multiplier (`CA_Size_Small` 0.5 / Normal 1 / Large 1.5), cooldowns in
  script. **supported hypothesis** for the values (Fallout wiki, Nexus CK threads); the script itself is **verified** on
  the PC (FO4 CK sources: `CompanionActorScript` 56 names, `FollowersScript` 98, job 15)
- Starfield made affinity **a record**: **AFFE** Affinity Event (flags Allow Repeated, Template, Fill Companion
  Dialogue; a list of follower NPC plus reaction GLOB; actor value; event size GLOB; distance to player GLOB;
  **cooldown in minutes GLOB**; required faction; "add to event" chaining). DIAL, INFO and quest stages can carry an
  AFFE directly. Story gates are globals (`COM_StoryGate_AffinityRequired`, `COM_StoryGate_TimerDuration`). **verified**
  (xEdit AFFE, DIAL ANAM, INFO NAM8, QUST stage NAM1; globals from the Affinity Enhanced mod description)
- Both games ship a script called **`CompanionActorScript`** (FO4's affinity script; Starfield's companion actor script,
  seen in SFSE-era console mods). Papyrus script names are global, so converted FO4 scripts must be **renamed into our
  own namespace** or they replace Starfield's. **verified** that Starfield ships the script (PC probe, 5,029 sources);
  the rule applies to every converted script.
- Verdict: the companion **records** (NPC_, quests, aliases, dialogue, packages) translate as data; **affinity is
  rebuilt** on Starfield's AFFE system (recommended: it is data, saved and cooled down by the engine) with FO4's
  numbers; **command mode** and the **companion perks** need checks; romance and talks are ordinary quest dialogue.

## How Fallout 4 does it

| part | what it is | label |
|---|---|---|
| Follower framework | a `Followers` quest (script `FollowersScript`) holds the companion alias and the dogmeat alias; the alias adds the follow package, teammate state and the "Companion" factions | supported hypothesis (names from community docs; check in Base.zip) |
| Per companion | a pre-recruit quest, an affinity quest and a `COMP<Name>` quest per companion (e.g. `COMPPiper`), per a CK forum thread; topic dialogue for idle chatter and reactions | supported hypothesis |
| Actor | NPC_ with `CompanionActorScript` (affinity settings struct array `EventData_Array`: keyword, global disposition, message) | supported hypothesis (Nexus CK thread) |
| Affinity value | hidden actor value `CA_Affinity` (`getav ca_affinity`); tiers 1000 idolize, 750 confidant, 500 admiration, 250 friend, 0 neutral, -500 disdain (warning), -1000 hatred (leaves for good); quests cap progress at a tier until done (MacCready, Curie stop at 499) | supported hypothesis (Fallout wiki) |
| Reactions | likes +15, loves +35, dislikes -15, hates -35, times the size scalar; repeatable actions such as weapon modding and stealing have 48 in-game hour cooldowns; passive gain while following | supported hypothesis (Fallout wiki) |
| Talks | `CA_WantsToTalk` actor value plus a force-greet package: `Alias_Cait.TryToSetActorValue(CA_WantsToTalk, 2)` then `EvaluatePackage()` in a forum example; `affinityscenehandlerscript` handles the end of the talk | supported hypothesis |
| Romance | flirt and romance options in the 500 and top-tier talks are Charisma checks (INFO challenge field) | supported hypothesis |
| Companion perks | one perk per companion at idolize (Cait Trigger Rush 001F4187, Codsworth Robot Sympathy 001EB99B, Preston United We Stand 00084298 ...), added by script, kept forever | supported hypothesis (form ids from the Fallout wiki; check in Fallout4.esm) |
| Commands | **command mode**: hold activate on the companion, aim at objects; the DIAL Command category subtypes (Call, Follow, Move, Attack, Inspect, Retrieve, Stay, Release, Trade, Assign, Enter ...) give the voiced barks | verified for the subtypes (xEdit); engine-side command mode is FO4 behaviour |
| Inventory | trade via the companion's container (Trade subtype); carry weight from the companion's actor values | supported hypothesis |
| Essential | companions are protected/essential while following; they bleed out and get up | supported hypothesis |
| Dogmeat | separate alias and slot (a dog plus one human with Lone Wanderer exceptions) | supported hypothesis |

## How Starfield does it

| part | what it is | label |
|---|---|---|
| Affinity events | **AFFE** records (see In short); reaction values per companion are globals; Starfield's documented values: loves +50, likes +25, dislikes -15, hates -35, plus a hidden "wants to talk" state worth +1 | verified record (xEdit); values from the Starfield wiki |
| Where events fire | DIAL ANAM (topic-level), INFO NAM8 (line-level), QUST stage NAM1 (stage reached), and scripts that send an event | verified (xEdit) |
| Story gates | 8 gates at 100 to 800 affinity, each also needing a minimum real-time gap (30 min, then 1 h); globals `COM_StoryGate_AffinityRequired`, `COM_StoryGate_TimerDuration`; action event records named `COM_Event_Action...` | supported hypothesis (Starfield wiki; Affinity Enhanced mod) |
| Framework | follower and crew state: `IsFollower`, `IsPlayerTeamMate`, `IsCompanion`, crew factions (`PotentialCrewFaction`, `AvailableCrewFaction`, `CurrentCrewFaction`), `PlayerAllyFaction`, `PlayerFriendFaction`; Join / Leave / Wait dialogue unlocks after `MQ101` | supported hypothesis (console utility mod's output) |
| Crew | companions double as **ship crew** (crew slots, ship skills, outpost assignment) | verified game behaviour; **fenced out** of our world |
| Commitment | romance ends in a "commitment" quest per companion; Barrett's gate 5 starts his quest, gate 6 his commitment | supported hypothesis (Starfield wiki) |
| Commands | follower orders through dialogue (wait, follow, trade); Starfield's core scripts still declare `SetCommandState`, `SetPlayerTeammate`, `IsPlayerTeammate` and `GetPlayerFollowers` (PC probe, verified names), so the engine side of command mode likely survives; the hold-activate UI is **unresolved** | |

## Mapping for the port

| FO4 piece | Starfield counterpart | verdict | notes |
|---|---|---|---|
| companion NPC_ | NPC_ | translate | bodies and faces per [actors-and-npcs.md](actors-and-npcs.md) |
| `Followers` framework quest | **our own** framework quest | rebuild (small) | do not reuse Starfield's crew/follower quest: it brings crew, ship and outpost hooks |
| per-companion quests, talks, romance | QUST, SCEN, INFO | translate | ordinary quest and dialogue conversion |
| `CA_Affinity`, `CA_WantsToTalk` actor values | AVIF (ours) | translate | keep FO4 names under our prefix |
| keyword-sent reactions plus `CompanionActorScript` | **AFFE** records (ours) | rebuild as data (recommended) | one AFFE per FO4 event keyword; reaction GLOBs per companion with FO4's numbers (+15/+35/-15/-35, size scalars); cooldown GLOB |
| script-only cooldowns (48 h) | AFFE cooldown in minutes | translate | 48 in-game hours expressed in real minutes depends on our timescale ([weather-time-climate.md](weather-time-climate.md)) |
| affinity tiers and quest caps | our own gate globals plus quest conditions | rebuild | FO4 tiers (250/500/750/1000) not Starfield's (100..800) |
| companion perks (PERK) | PERK | translate | needs our SPECIAL/perk layer ([special-perks-leveling.md](special-perks-leveling.md)) |
| command mode | unresolved | check, then SFSE or dialogue fallback | breadth first: dialogue orders (follow, wait, trade, dismiss) |
| `CompanionActorScript` and other same-named scripts | name clash | rename | our script namespace, e.g. `FO4SF:` folders or an `FO4_` prefix, decided once for all converted scripts |
| Dogmeat slot | our framework | rebuild | |

## What must be rebuilt, and what needs SFSE or the Creation Kit

- **Rebuild:** the follower framework (ours, small), the affinity layer on AFFE, the tier gates, command mode or its
  dialogue fallback, all companion scripts (recompiled, renamed).
- **Creation Kit:** lip sync for companion voice (the biggest voice sets in the game: Preston alone has 2,421 lines);
  see [dialogue.md](dialogue.md).
- **SFSE:** only if command mode must be faithful and CE2 lacks it.

## Port status and links

- Codsworth stands on Starfield's mini bot race with his FO4 model and 20 converted lines (#361); Preston is a
  converted NPC with his own faction (v6e fix, untested). Neither has affinity or follower behaviour yet.
- Plans: [../next-phase/voice-lipsync-companions.md](../next-phase/voice-lipsync-companions.md) (companions section)
  and [../next-phase/npcs-ai-factions-dialogue-quests.md](../next-phase/npcs-ai-factions-dialogue-quests.md).

## Open questions and cheap checks

- FO4 framework names (`Followers` quest, the `CA_` keyword list): a QUST/KYWD editor-id scan of Fallout4.esm, or a
  grep of the FO4 CK sources now on the PC (`Data\Scripts\Source\Base\Base.zip`), both read-only.
- Answered by the PC probe (verified): Starfield ships `CompanionActorScript`, `SQ_FollowersScript`, `SQ_CompanionsScript`
  and `SQ_CrewScript`; its `CompanionActorScript` declares no `SendAffinityEvent` or `TryToModAffinity`, and there is no
  `FollowersScript`. FO4's side (job 15, FO4 CK sources): `FollowersScript` has 98 functions (companion slots,
  Dogmeat, affinity events, loitering, teleport, vertibird events) with no Starfield counterpart, and FO4's
  `CompanionActorScript` shares only 2 of its 56 names with Starfield's; FO4's `Actor` adds 8 companion natives
  (`SetCompanion`, `AllowCompanion`, `FollowerFollow`, `FollowerWait`, follow distances) that Starfield lacks
  ([papyrus-and-script-extenders.md](papyrus-and-script-extenders.md)).
- Does CE2 keep FO4's command mode (hold activate on a follower)? A Starfield game setting or script search for
  "CommandMode" in ContentResources.zip and the exe strings.
- AFFE's "Fill Companion Dialogue" flag: what it fills. One vanilla AFFE dump.

## Sources

- xEdit SF1 AFFE, DIAL, INFO, QUST: https://github.com/TES5Edit/TES5Edit/blob/dev-4.1.6/Core/wbDefinitionsSF1.pas
- Fallout wiki, Affinity: https://fallout.fandom.com/wiki/Affinity
- FO4 CK forum threads: https://forums.nexusmods.com/topic/5835817-affinity-system-in-creation-kit ,
  https://forums.nexusmods.com/topic/12870213-creation-kit-how-to-make-a-companion-use-a-different-affinity-keyword
- Starfield wiki, Affinity: https://starfieldwiki.net/wiki/Starfield:Affinity
- Starfield mods: Affinity Enhanced https://www.nexusmods.com/starfield/mods/6891 ; console utilities
  https://www.nexusmods.com/starfield/mods/3622
