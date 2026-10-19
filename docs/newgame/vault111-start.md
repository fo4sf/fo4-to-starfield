# A Fallout 4 new game: the Vault 111 start (phase 1)

Written 2026-10-19 by Claude-cloud (the new-game thread). Phase 1 of the approved roadmap: a new game that opens in
Vault 111 with no Starfield intro, which everything else plugs into. **Offline only so far: nothing here has run in
game or been installed.** Labels follow docs/ai/research-log.md (verified, supported hypothesis, unresolved).

Files: `dotnet/NewGame/Program.cs` (the plugin writer and its checks), `scripts/newgame/FO4SF_NewGameQuest.psc` (the
quest script), `scripts/newgame/FO4SF_NewGameLooks.psc` (optional character creation), `scripts/newgame/make_newgame.py`
(precheck, stage, verify, fold, log reader), `tests/test_newgame.py`.

## 1. What the player gets (the defaults)

   (Starfield has no Papyrus menu check, so it cannot wait for menus).
   menu is open.
2. **Guard:** it acts only on a new game (fewer than 0.25 game days passed and the player at level 1). An existing save
   that gains the plugin stands the quest down at stage 1 and nothing moves. The owner's test saves are safe.
3. **Starfield's opening is held off:** the quest stops `MQ00` (the main-quest start) and `MQ101` (the opening) if they
   run, and logs each one.
4. **The cryo pod:** the player is moved into the converted Vault 111 (`FO4Port_Vault111Cryo`) and stands up one metre
   in front of their own pod, facing out of it. The notification reads "Vault 111" and the objective is "Leave Vault
   111" under FO4's quest name for this part (MQ102's name, read from Fallout4.esm by the points step; "Out of
   Time" is only the fallback when it has none).
5. **Looks:** Starfield's character creation opens once in the vault, in place of FO4's bathroom mirror (optional
   script; see section 4).
6. **The cog door:** standing at its console opens the cog door (no Pip-Boy needed, unlike FO4).
7. **The exit:** standing on the elevator platform asks "Ride the elevator up to the surface?". Yes puts the player at
   FO4's surface arrival of the ride in the Commonwealth core, at the right world position (core-local + the measured
   merge offset). If the player lands more than 3 m below the arrival, they are put on the Vault 111 map marker's spot.
8. The quest completes. The player is **silent** (Starfield's player has no voice; nothing to do), and has **no
   Pip-Boy** (section 5).

Every step goes to `My Games\Starfield\Logs\Script\User\fo4sf_newgame.0.log`; `make_newgame.py log` summarises it.

## 2. How Starfield's intro is bypassed

| Option | How | For | Against |
|---|---|---|---|
| **A. Stop the opening quests at start (default)** | Our start-game quest stops MQ00 and MQ101 from Papyrus (`Quest.Stop`), then moves the player | Edits no Starfield record; reversible by removing our plugin; the list is a build option (`--hold`) | **unresolved** whether MQ101 has already started its scene, disabled controls or opened its menus before our quest runs; the in-game proof decides |
| B. The debug start (`--mq101debug <n>`) | Override Starfield's GLOB `MQ101Debug`. SKK Fast Start New Game (Nexus Starfield 5971) sets it to 8 as a "hard edit in the ESM" and checks the player is in `NewAtlantisSpaceport03` | A path Bethesda built and a public mod relies on | **unresolved** which value skips what. The PC precheck (19 Oct, ContentResources.zip, verified lines): `MQ101Script.psc` declares the property (line 14) and branches on `MQ101Debug.GetValueInt() == 1` (line 79); `QF_MQ00_00005790.psc` line 7 sets it to 10; MQ101's fragment shows a debug message box `MQ101DebugMSG01` (line 288); most MQ102 to MQ305 start stages set it to 2; 8 is set by the test quest `QF_TestQuest_LVC_010D747E.psc` (line 101) and read by `SFBGS00D\CruiseModeTestSupportScript.psc` (line 29), so 8 belongs to a cruise-mode test start. Reading MQ101Script around line 79 decides whether a value fits us |
| C. Override MQ00 / MQ101 without StartGameEnabled | Plugin overrides of Starfield's quest records | The opening never starts | Edits Starfield records; anything that expects MQ101 (NG+, Constellation, achievements) may break; hardest to undo in a save |
| D. Our own start menu (as SKK) | A message box after character creation picking Vault 111 or Starfield's own start | Players keep the choice | More UI; only worth it once the Fallout start works |

The ladder for the first in-game proof: A first; if the mine scene, its sounds or a stuck camera still show, B (a
rebuild with `--mq101debug 8`, nothing else changes); C only on the owner's word. Which of Starfield's other 142
start-game quests to hold off (the ship, the radiant parents, city and companion quests, generic dialogue) is the
`npcs-ai-factions-dialogue-quests.md` section 8 list; the first proof records what runs (`sqv`) before more are added,
because stopping SQ_PlayerShip or SQ_ENV could break the HUD or travel.

## 3. Where the player goes, and why the plugin has no masters but Starfield.esm

- **verified:** FO4Port.esm places FO4 interiors at FO4 position / 70 (metres) in cells named `FO4Port_<cell>` and puts
  each cell's COC marker on Starfield's `COCMarkerHeading` 000032 (`dotnet/PluginSpike`, WP10); `coc
  FO4Port_Vault111Cryo` works in game (journal 2026-10-08, the bridge runs).
- **verified:** persistent references of the core's world stay at their core-local position; MoveTo onto such a
  reference puts the player in the core world at that local spot, and SetPosition to local + (-1200, -2700) then puts
  them where FO4 has it (door probe (e), the Super Duper Mart round trip PASS 17 Oct, `FO4SF_LoadDoor`
  UseDestinationPosition). The new game uses the same two steps for the elevator exit.
- So the script resolves its places at run time with `Game.GetFormFromFile(id, plugin)` (the `FO4SF_LoadDoor`
  contract): the vault anchor is the COC marker of `FO4Port_Vault111Cryo`; the exit anchor is the core's persistent
  `FO4Core_CommonwealthMapMarkerVault111`; the cog door is the port's reference keyed
  `REFR:FO4Port_Vault111Cryo:000330C3:Fallout4.esm` in its stable `formids.json`. The writer reads the port, its
  `formids.json` and the core to find those ids and refuses when any is missing or ambiguous; `check` re-reads them.
  Because port and core ids are stable across rebuilds, a rebuilt port or core does not need a rebuilt plugin, but the
  stage pins their SHA-256 and `verify` refuses an install against other bytes until the stage is re-run (a quick,
  offline re-check).
- Alternative: master FO4Port.esm and the core and place our own markers (a WRLD and CELL override, as the mission
  does). That costs a rebuild after every port or core build and ties the start to one build pair.

## 4. The cryo pod and character creation

- FO4 (**verified**, B4 spike): MQ102 opens the pod after the cut scene; the player has no Pip-Boy until the overseer's
  office; the cog door console needs it (stage 5 and a fail sound without it, stage 7 seats the player and plays the
  plug-in animation).
- Ours: no cut scene and no pod animation (the pod is a converted static). The player stands one metre out of the pod
  along its facing. Which of the pod's axes faces out is a **supported hypothesis** (+Y turned by its z rotation); the
  points step prints every candidate pod, and `--pod-ref` names it if FO4's EditorIDs give more than one. If the move
  misses the cell, the quest retries each second; the log shows the landing.
- Character creation: `FO4SF_NewGameLooks` calls `Game.ShowRaceMenu()` once the player is in the vault. **verified**
  (PC precheck, 19 Oct): Starfield's Game.psc declares `ShowRaceMenu`; what it shows with no arguments is
  **unresolved**. Starfield's Utility.psc has **no** `IsInMenuMode` (verified, same precheck), so neither script waits on
  menus: the quest starts once the player's 3D is loaded, and the looks script sets stage 20 when the call returns. It
  stays a separate script so a failed compile drops only it (`--no-looks`, and the quest then does not wait). FO4's own looks menu and the bathroom mirror are a
  later UI item (Scaleform; animations-ui-and-start.md section 3).
- Alternatives for the talk: keep Starfield's character creation before the vault (option B's path); or skip it and
  set a default look.

## 5. What Vault 111 needs from the port today

| Piece | State | Source |
|---|---|---|
| The cryo hall, corridors, stairs | converted and walkable (`coc FO4Port_Vault111Cryo`), sliding doors work | ROADMAP, owner rows 1 and 6 |
| Gear-room gates passable, gear-pit water sheet | fixes on main (static gate leaves, water planes left out); need an interior rebuild | ROADMAP Phase A table |
| Cog door VltGearDoor01 | converted as a door with its own rig (Stage2 as Open, `pipeline.OWN_RIG_ALIASES`, tests/test_cog_door.py); in game it was still a solid static on integ_1018. Whether the installed port carries the rigged door and whether `SetOpen` opens it: **unresolved** | ROADMAP, door_motion.py |
| Cog door console | FO4 activator with MQ03ControlPanelScript; ours is only a spot the quest watches | B4 |
| Exit elevator | not connected: both autoload doors (interior 01F180, surface 0998E3) are marker doors the converter never places (`door_skipped`); the elevator is an animated activator. The new-game quest's prompt replaces the ride | scripted-doors.md, research log 2026-10-14 |
| Going back down | not handled: the surface elevator and the descend trigger are not converted; the doors phase owns it | B4 |
| Pip-Boy, the overseer's office skeleton, the cryo cut scene, the spouse, Kellogg | none: later phases (UI with SFSE; NPCs and scenes) | animations-ui-and-start.md |
| The surface arrival | core-local, from the XTEL of 01F180; whether the surface elevator platform is solid there is **unresolved**, hence the fall check and the map-marker fallback | this plugin |

## 6. Build recipe (PC, offline, no game)

1. `python scripts\newgame\make_newgame.py precheck --out D:\Modding\scratch\newgame\precheck.json` reads
   ContentResources.zip only and lists every native both scripts call and every MQ101Debug line. Exit 1 means a core
   native is missing: stop and report. A missing `Game.ShowRaceMenu` means stage with `--no-looks`.
2. `python scripts\newgame\make_newgame.py stage --out D:\Modding\staging\newgame_v1 --fo4 <Fallout4.esm> --port
   <installed FO4Port.esm> --port-ids <that port build's formids.json> --core <installed FO4TerrainCore.esm>` runs
   points, write, check and the Papyrus compile, then writes plan.json and README.txt. Inputs are read only; the output is
   one new folder on D:.
3. The offline checks are `offline_check.txt` (every record, property and resolved id) and the selftest
   (`dotnet run -c Release --project dotnet\NewGame -- selftest <scratch>`, synthetic masters and mutations).
4. Install is a later owner line: `fold` into a copy of the installed core set, `verify`, then `exp_install.py`, game
   closed, after the current v6e test. Testing needs a NEW game, so it never touches the owner's saves.

## 7. First in-game proof (later, on the owner's word)

New game with the plugin installed. Record the log, `sqv MQ101`, `sqv MQ00` and screenshots at the pod, at the cog door
and on the surface. PASS means the log reaches stage 200 with "enter vault ok=True" and "landed", there is no Starfield
intro on screen, and the surface screenshot shows the Vault 111 elevator area. Then walk on from there: the
continuous-traversal gate starts at the vault exit.

## 8. Questions for the talk

1. Option A (stop the opening quests) as the default, B as the fallback? Or skip straight to B?
2. Character creation: Starfield's menu in the vault (default), before the vault, or none for now?
3. Should players be able to pick Starfield's own start instead (option D)?
4. Hold off more of Starfield's 144 start quests now, or only after the first `sqv` record?

## Sources

- [SKK Fast Start New Game (Nexus Starfield 5971)](https://www.nexusmods.com/starfield/mods/5971): MQ101Debug = 8, the
  `NewAtlantisSpaceport03` check, MQ101 stage checks.
- [ECS Asteria (Nexus Starfield 16206)](https://www.nexusmods.com/starfield/mods/16206): a new game teleports the player
  from a start script and guards against mid-game installs.
- docs/spikes/B4-mission-anatomy.md section 3 (the Vault 111 exit chain, verified ids), docs/terrain/scripted-doors.md,
  docs/ROADMAP.md, scripts/door_bridge/FO4SF_LoadDoor.psc, the mission (#353) as the pattern.
