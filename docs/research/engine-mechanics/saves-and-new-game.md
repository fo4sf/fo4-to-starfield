# Saves and the new game (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved.

## In short
- Both games save the player's changes on top of the plugins: changed forms (deltas against the records) plus the
  Papyrus VM state (variables, properties, suspended stacks). FO4 writes `.fos` (magic `FO4_SAVEGAME`, **verified**);
  Starfield writes `.sfs`, whose internal layout is not publicly documented (**unresolved**). Verdict: no save
  conversion; the port starts fresh games only.
- FO4's start is quest-driven: MQ101 (prewar Sanctuary, mirror character creation, Vault 111 cryo) then MQ102 (vault
  exit). Starfield's start is also quest-driven: MQ101 on Vectera, character creation in `CharGenMenu`, 144
  start-enabled quests (**verified**, project job AT).
- Port verdict: **rebuild** the start as our own start quest that runs on new game, moves the player into converted
  Vault 111, and keeps Starfield's intro and start quests from running. Plugin work (CK or our writer); no SFSE needed
  for the move itself (**supported hypothesis**).
- Character creation: Starfield's `ShowRaceMenu` and `SetInChargen` natives exist (**verified**, Starfield wiki Game
  script page), so we can open Starfield's own creator from our quest. An FO4-style mirror scene is later polish.

## How Fallout 4 does it
**Save file** (`Documents\My Games\Fallout4\Saves\*.fos`):
- Header: `FO4_SAVEGAME` signature, a screenshot at 4 bytes per pixel, then a version string new in FO4; "pretty
  similar to Skyrim" otherwise (**verified**, Nexus forum save-format thread). By analogy with Skyrim's documented
  format: plugin list, global data tables (game time, weather, etc.), change forms with per-form change flags, the
  Papyrus VM block, FormID array (**supported hypothesis**).
- Papyrus in saves: variable and property values, running function stacks resume on load; removed properties are
  discarded with a warning; removing a mod mid-save is unsupported (**verified**, falloutck Save File Notes (Papyrus)).
- `Game.RequestSave` / `RequestAutoSave` are the script entry points (**verified**, falloutck Game Script).

**New game flow** (quest names MQ101 "War Never Changes", MQ102 "Out of Time" are **supported hypothesis** from UESP
naming; editor ids MQ101 / MQ102 **verified** by the SKK article and B4):
1. Intro video, then MQ101 in the prewar worldspace `SanctuaryHillsWorld` (1,728 cells, 118 LAND, 4,276 refs;
   **verified**, project survey in trees-grass-terrain.md section 2) and the prewar house interior.
2. Mirror scene: character creation for both spouses. The vanilla menu is `LooksMenu` (the F4SE mod of the same name
   extends it) (**supported hypothesis**). Script side: `Game.ShowRaceMenu(akMenuTarget, uiMode, ...)`,
   `SetInChargen`, `SetCharGenHUDMode`, `PrecacheCharGen` (**verified**, falloutck Game Script). The face sculpt is
   part of that menu. Then Codsworth, the Vault-Tec rep (name, SPECIAL card), the bomb, the elevator ride into Vault 111.
3. MQ101 calls `PlayerREF.RemoveAllItems()` at stage 0 (video to mirror) and again at stage 900 (move to the postwar
   vault) (**verified**, SKK FastStart article).
4. Vault 111: the cryo sequence (Kellogg scene), wake up, the vault walk, the gear door. MQ102 stage 10 is the vault
   exit and stage 15 "Radios on"; many vanilla systems hang off those stages, and they can back up for minutes at the
   exit (**verified** as the SKK author describes).
- **Community skip (FO4)**: SKK FastStart intercepts MQ101 at stage 20, bypasses the stage 900 clear-down, marks MQ101
  completed and sets MQ102 stages 10 and 15 done; SKK SyntheticPlayer intercepts at stage 0 by editing base scripts
  (**verified**, same article). Lesson: an FO4 start must set the stages other systems key off, not just move the
  player. Workshop registration takes about two minutes after the looks menu (**verified**, same).

## How Starfield does it
**Save file** (`.sfs`): Papyrus semantics are the same engine family (**supported hypothesis**). Saves grow with
runtime-generated data (procedural POIs, landing overlays, leveled spawns); the SFSE "Save Cleaner" removes about 40 %
of a save by erasing such data, and its author calls that unsafe (**verified** as described on its article). Header,
compression and chunk layout: **unresolved** (no public spec found). `RequestSave`, `RequestAutoSave`,
`RequestSaveByName` exist (**verified**, Starfield wiki Game script page). The SFSE serialization API is disabled
since 0.2.12 (**verified**, sfse_whatsnew), so an SFSE plugin cannot store its own co-save data today.

**New game flow**:
- Main menu new game starts the title sequence (`StartTitleSequence`, `ShowTitleSequenceMenu`,
  `HideTitleSequenceMenu` are Game natives, **verified** names) and the opening quest MQ101 "One Small Step" on
  Vectera (Argos mine). The fragment `QF_MQ101_00003448.psc` exists in the shipped sources and calls
  `Game.SetLocalTime(...)` for staged arrivals (**verified**, docs/ai/test-queue.md). Display name and the Vectera
  setting: **verified** by Roleplayers' Alternate Start's page naming "One Small Step" and the Vectera introduction.
- Character creation is `CharGenMenu` (menu name **verified**: SFSE 0.2.2 notes mention CharGenMenu errors in
  sfee.dll). It picks body, face, a **background** and up to three **traits** (count **supported hypothesis**).
  Backgrounds and traits are PERK records with DATA flags `Trait` 0x01 and `Background` 0x10 (**verified**, xEdit
  wbDefinitionsSF1.pas PERK). FO4's PERK DATA only has a `Trait` bool (**verified**, wbDefinitionsFO4.pas).
- Console `showlooksmenu player 1` reopens the appearance editor (**verified** as used by Alternate Start Starfield
  per PCGamesN; behaviour **supported**).
- 144 quests are start-enabled, including MQ00, SQ_PlayerShip, SQ_ENV, radiant parents and about 40 dialogue quests
  (**verified**, job AT `SfInspect startquests`).
- `CreateStarbornGame` exists for the NG+ path (**verified** name). The NG+ start quest MQ401 reads globals
  `MQ401_VariantChance` / `MQ401_ForceVariant` (**verified**, Choose Your Own Adventure mod page).

**Community alternate starts (Starfield)**, how they work:
| Mod | Mechanism | Label |
|---|---|---|
| Alternate Start Starfield (SpaceDov4, pre-CK) | ships premade save files per background; player loads one, then `showlooksmenu player 1` | verified (PCGamesN, eXputer) |
| Roleplayers' Alternate Start (ZeCroque) | plugin (`RoleplayersAlternateStart.esm`); custom start area like the Unity; vanilla One Small Step skipped on alternate paths; level and skill manager; no SFSE stated | verified (Nexus 15094) |
| Choose Your Own Adventure (NG+) | bat files setting MQ401 globals by console | verified (Nexus 3673) |
How the plugin route keeps MQ101 from running (start-enabled flag removed, or stages forced) is not described on
the page (**unresolved**; read its esm in xEdit).

## Mapping for the port
| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| `.fos` saves | `.sfs` | drop | no conversion; fresh start only |
| MQ101 prewar (SanctuaryHillsWorld, house) | none | rebuild (later) | phase 1 starts at the cryo pod; prewar needs its own overlay world |
| Mirror character creation (LooksMenu) | `CharGenMenu` via `Game.ShowRaceMenu` | translate | Starfield creator first; FO4 sliders are a UI item |
| Spouse creation | none | drop for now | spouse becomes a fixed NPC |
| FO4 SPECIAL card | Starfield skills, no SPECIAL | rebuild | Fallout systems phase |
| Starfield backgrounds / traits | PERK flags | fence or hide | our start picks none or a neutral background |
| MQ101 stage 900 / MQ102 stages 10, 15 | our start quest stages | translate | set the stages FO4 systems listen to |
| Vault 111 cryo wake-up and exit | converted interiors + scripted doors | rebuild | phase 1 acceptance |
| 144 Starfield start quests | override to not start | data (override records) | which ones: npcs-ai note section 8 |
| Starfield MQ101 on Vectera | must not run | override | start-enabled flag or stage-gate (to test) |

## What must be rebuilt, and what needs SFSE or the Creation Kit
- **Our start quest** (plugin, start-enabled): stage 0 waits for the title sequence to end, fades out, moves the
  player to a marker in the converted cryo pod cell (`MoveTo`), clears Starfield starting items, adds FO4 starting
  gear, optionally calls `Game.ShowRaceMenu`, sets FO4-compat stages, then fades in. Natives used all exist in
  Starfield (`MoveTo`, `FadeOutGame`, `ShowRaceMenu`, `SetInChargen`) (**verified** names).
- **Holding off Starfield's start**: override the start-enabled flag on MQ101 and the fenced start quests, or let
  them start and stop them at once. Which one survives the engine's new-game path is **unresolved** (first in-game
  proof, as animations-ui-and-start.md section 4 plans: start a game, record where the player appears, `sqv`).
- **CK**: not required for the start quest itself (our writer already writes quests and VMAD); CK2 is needed only if
  we compile fragment scripts there.
- **SFSE**: not required for the start. Needed only for an FO4-style looks menu or skipping the title sequence if
  Papyrus cannot.

## Port status and links
- The new-game build exists offline: draft PR #393 (branch `claude/new-game-start-v75g3a`), design in
  `docs/newgame/vault111-start.md` on that branch. It stops `MQ00` and `MQ101` from our start-game quest (option A),
  with the `MQ101Debug` global as fallback B. **verified** from Starfield's sources on the PC (19 Oct): MQ00's only
  fragment sets `MQ101Debug` to 10 and starts MQ101, and `MQ101Script` jumps to stage 400 only when the global reads 1,
  so overriding the global alone is undone by MQ00. Staged at D:\Modding\staging\newgame_v1, untested in game.
- Its quest engine probe (`docs/questprobe/engine-questions.md`, same branch) tests stage fragments, OnStageSet,
  alias-following markers, our own quest-type heading and our own Story Manager branch under the Script Event node.
- The plan-level route is in [../next-phase/animations-ui-and-start.md](../next-phase/animations-ui-and-start.md)
  section 4; holding off quests is in
  [../next-phase/npcs-ai-factions-dialogue-quests.md](../next-phase/npcs-ai-factions-dialogue-quests.md) section 8.
- Vault 111 interiors: [WP10-vault111-first-light.md](../../spikes/WP10-vault111-first-light.md); the cog door and
  console sequence: [B4-mission-anatomy.md](../../spikes/B4-mission-anatomy.md) section 3.
- SanctuaryHillsWorld is surveyed but not built (trees-grass-terrain.md section 2).

## Open questions and cheap checks
- In xEdit: does Starfield MQ101 carry the Start Game Enabled flag, and what does Roleplayers' Alternate Start
  override on it? (read-only, one record).
- Grep ContentResources.zip `QF_MQ101_00003448.psc` for `ShowRaceMenu`, `SetInChargen`, `RemoveAllItems` to see how
  Starfield opens chargen and clears items.
- Grep FO4 `Base.zip` (or decompiled `QF_MQ101_*`) for the same calls and stage numbers 0, 20, 900.
- In game (later, Claude): new game with a minimal start-quest plugin; record arrival position, `sqv` list, whether
  the title sequence plays.
- `.sfs` header: hex-dump the first 64 bytes of one save (read-only) to label magic and compression.

## Sources
- xEdit definitions dev-4.1.6: wbDefinitionsFO4.pas, wbDefinitionsSF1.pas (PERK) ([TES5Edit](https://github.com/TES5Edit/TES5Edit)).
- [Save file format documentation (Nexus forums)](https://forums.nexusmods.com/topic/3481260-save-file-format-documentation)
- [Save File Notes (Papyrus) (falloutck)](https://falloutck.uesp.net/wiki/Save_File_Notes_(Papyrus)); [Game Script (falloutck)](https://falloutck.uesp.net/wiki/Game_Script)
- [SKK FastStart new game article](https://www.nexusmods.com/fallout4/articles/1038)
- [Starfield Mod: Script-Game](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-Game)
- [sfse_whatsnew.txt](https://raw.githubusercontent.com/ianpatt/sfse/master/sfse_whatsnew.txt)
- [Starfield Save Cleaner article](https://www.nexusmods.com/starfield/articles/762)
- [Roleplayers' Alternate Start](https://www.nexusmods.com/starfield/mods/15094); [Choose Your Own Adventure NG+](https://www.nexusmods.com/starfield/mods/3673)
- [PCGamesN: Alternate Start Starfield](https://www.pcgamesn.com/starfield/alternate-start-mod); [eXputer: skip intro mod](https://exputer.com/news/games/starfield-mod-skip-intro/)
