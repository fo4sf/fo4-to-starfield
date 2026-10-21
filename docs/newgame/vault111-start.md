# A Fallout 4 new game: the Vault 111 start (phase 1)

Written 2026-10-19 by Claude-cloud (the new-game thread). Phase 1 of the approved roadmap: a new game that opens in
Vault 111 with no Starfield intro, which everything else plugs into. **Offline only so far: nothing here has run in
game or been installed.** Labels follow docs/ai/research-log.md (verified, supported hypothesis, unresolved).

Files: `dotnet/NewGame/Program.cs` (the plugin writer and its checks), `dotnet/NewGame/Records.cs` (the read-only PC
record reader, section 6a), `scripts/newgame/FO4SF_NewGameQuest.psc` (the
quest script), `scripts/newgame/FO4SF_NewGameLooks.psc` (optional character creation),
`scripts/newgame/FO4SF_NewGameSpecial.psc` (optional SPECIAL at the vault terminal),
`scripts/newgame/FO4SF_NewGameVersion.psc` (optional save version check), `scripts/newgame/make_newgame.py` (precheck,
stage, verify, fold, log reader), `tests/test_newgame.py`.

## 1. What the player gets (the defaults)

1. **Start:** our quest starts with the game (start game enabled, run once) and waits each second until the player's 3D
   is loaded (Starfield's Utility.psc has no IsInMenuMode, so open menus are not awaited).
2. **Guard:** it acts only on a new game (fewer than 0.25 game days passed and the player at level 1). An existing save
   that gains the plugin stands the quest down at stage 1 and nothing moves. The owner's test saves are safe.
3. **Starfield's opening is held off:** the quest stops `MQ00` (the main-quest start), `MQ101` (the opening),
   `MQ101PostQuest` and `MQ_TutorialQuest_Misc04` if they run, and logs each stop. The list is walked twice: once before
   the move, and once one tick later, because stopping MQ101 runs its stage 9000, which starts the last two (section 2).
   Saving and the HUD, which MQ101's stage 0 had turned off, are turned back on right after the first pass.
   The plugin also overrides Starfield's global `MQ101Debug` to 10, the value MQ00 writes before it starts MQ101
   (section 2, NG-2). That override is a record, not gated by the guard: whether an existing save keeps its own value
   of the global is unverified until the PC run.
4. **The cryo pod:** the player is moved into the converted Vault 111 (`FO4Port_Vault111Cryo`) and stands up one metre
   in front of their own pod, facing out of it. The notification reads "Vault 111" and the objective is "Leave Vault
   111" under FO4's quest name for this part (MQ102's name, read from Fallout4.esm by the points step; "Out of
   Time" is only the fallback when it has none).
5. **Looks:** a message box in the vault asks "Create character" or "Quick start" (NG-6, NG-C9). Create opens
   Starfield's character creation in place of FO4's bathroom mirror and waits for it to close; quick start keeps the
   preset and skips it. A message box needs no voice: the player stays silent (optional script; see section 4).
6. **SPECIAL:** standing at the vault terminal after the looks asks "Set SPECIAL" or "Later". Set opens the
   allocation: FO4's numbers, 1 in each stat, 21 points to spend, 10 at most in one; one button per stat, Reset,
   Confirm, Leave. Confirm writes seven actor values of our own (NG-5, NG-C4; section 4a). The player can skip it and
   ride up; the log then says so (optional script).
7. **The cog door:** standing at its console opens the cog door (no Pip-Boy needed, unlike FO4).
8. **The exit:** standing on the elevator platform asks "Ride the elevator up to the surface?". Yes puts the player at
   FO4's surface arrival of the ride in the Commonwealth core, at the right world position (core-local + the measured
   merge offset). If the player lands more than 3 m below the arrival, they are put on the Vault 111 map marker's spot.
9. The quest completes. The player is **silent** (Starfield's player has no voice; nothing to do), and has **no
   Pip-Boy** (section 5). The stages the quest passes through are a published contract (section 9).
10. **Save version:** the save records the build's version number when the new game starts. Every later load compares
    it with the installed build's and shows a notification when they differ (NG-15, NG-L2; section 4b). Nothing else
    changes (optional script).
11. **Starting inventory (off by default):** the player keeps whatever Starfield gives them. A `--clear-inventory`
    build empties the inventory (quest items kept) right after the move into the pod and logs the count; with
    `--vault-suit <EditorID>` it then adds and equips that armor of the port (NG-K8; section 4c). Off until the first
    in-game proof shows what a game with MQ101 held off leaves in the inventory.

Every step goes to `My Games\Starfield\Logs\Script\User\fo4sf_newgame.0.log`; `make_newgame.py log` summarises it.

## 2. How Starfield's intro is bypassed

| Option | How | For | Against |
|---|---|---|---|
| **A. Stop the opening quests at start (default)** | Our start-game quest stops MQ00, MQ101, MQ101PostQuest and MQ_TutorialQuest_Misc04 from Papyrus (`Quest.Stop`), then moves the player. **verified** (ContentResources.zip, PC 19 Oct): MQ00's only fragment, stage 10, sets MQ101Debug to 10, waits 0.1 s and starts MQ101; MQ101Script's OnQuestInit jumps to stage 400 only when MQ101Debug reads 1. **verified** (same read): MQ101's stage 9000 runs on stop; it always starts MQ101PostQuest and, when the player never entered the Unity, MQ_TutorialQuest_Misc04, and restores neither saving nor the HUD. So the script walks the hold-off list a second time one tick after the first pass (NG-19, NG-N1) and restores saving and the HUD itself | Edits no Starfield quest record; reversible by removing our plugin; the list is a build option (`--hold`) | **unresolved** whether MQ101 has already started its scene, disabled controls or opened its menus before our quest runs, and whether one tick is enough for stage 9000 to have started its quests; the in-game proof decides (the log says what each pass stopped) |
| **B. The debug global (on by default, `--no-mq101debug` turns it off)** | The plugin overrides Starfield's GLOB `MQ101Debug` to 10. The owner decided (2026-10-19, NG-2) that we set it ourselves: stopping MQ00 before its stage 10 runs would leave it at 0, which turns sustenance off (its condition form reads it, NG-M1). 10 is what MQ00 would have written, so a game started our way reads the same value a vanilla start does. `--mq101debug <n>` writes another value. SKK Fast Start New Game (Nexus Starfield 5971) sets it to 8 as a "hard edit in the ESM" and checks the player is in `NewAtlantisSpaceport03` | A path Bethesda built and a public mod relies on; one GLOB override, no quest record touched | **unresolved** which value skips what, and whether 10 is the right one for us (NG-M4): it is unverified until the PC run. The PC precheck (19 Oct, ContentResources.zip, verified lines): `MQ101Script.psc` declares the property (line 14) and branches on `MQ101Debug.GetValueInt() == 1` (line 79); `QF_MQ00_00005790.psc` line 7 sets it to 10; MQ101's fragment shows a debug message box `MQ101DebugMSG01` (line 288); most MQ102 to MQ305 start stages set it to 2; 8 is set by the test quest `QF_TestQuest_LVC_010D747E.psc` (line 101) and read by `SFBGS00D\CruiseModeTestSupportScript.psc` (line 29), so 8 belongs to a cruise-mode test start. MQ101Script's OnQuestInit (lines 75 to 82) only does `SetStage(400)` when the value is 1, and MQ00 writes 10 before starting MQ101, so an override of the global alone is undone by MQ00: B would need MQ00 held off too (the default does), and what stage 400 is remains **unresolved** |
| C. Override MQ00 / MQ101 without StartGameEnabled | Plugin overrides of Starfield's quest records | The opening never starts | Edits Starfield records; anything that expects MQ101 (NG+, Constellation, achievements) may break; hardest to undo in a save |
| D. Our own start menu (as SKK) | A message box after character creation picking Vault 111 or Starfield's own start | Players keep the choice | More UI; only worth it once the Fallout start works |

The ladder for the first in-game proof: the default (A with B's global at 10) first; if the mine scene, its sounds or a
stuck camera still show, a rebuild with `--mq101debug 8` (nothing else changes); `--no-mq101debug` if the global itself
turns out to do harm; C only on the owner's word. Which of Starfield's other 142
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
  contract): the vault anchor is a persistent reference of `FO4Port_Vault111Cryo` (its COC marker when that is persistent,
  else the port's persistent reference nearest to it: a temporary reference in an unloaded cell resolves to none, 16 Oct
  probe), and every resolved reference must be the named plugin's own record; the exit anchor is the core's persistent
  `FO4Core_CommonwealthMapMarkerVault111`; the cog door is the port's reference keyed
  `REFR:FO4Port_Vault111Cryo:0330C3:Fallout4.esm` (Mutagen prints six digits; the id is matched as a number) in its stable `formids.json`. The writer reads the port, its
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
  points step prints every candidate pod (on the PC: MQPlayerCryopodREF 0004A011, the player's, and MQPlayerSpousePodREF
  0004A012, which the rule skips), and `--pod-ref` names one if that ever changes. If the move
  misses the cell, the quest retries each second; the log shows the landing.
- The opening choice: once the player is in the vault, `FO4SF_NewGameLooks` shows MESG `FO4SF_NewGameStart`
  (FO4SFNewGame.esm 0x802), "Create character" or "Quick start". The owner decided (2026-10-19, NG-C9) that phase 1
  has a preset quick start for replays: button 1 skips the creator and keeps the look the player already has (the
  game's default new player; a shipped Fallout-style face preset is a later item, NG-M9). Button 0 opens the creator.
- Character creation: `Game.ShowRaceMenu(None, RaceMenuMode)`. **verified** (PC read, 19 Oct): Starfield's Game.psc
  declares `ShowRaceMenu(ObjectReference akMenuTarget = None, int uiMode = 0, ...)`, the modes FO4's (0 chargen, 1
  remake, 2 haircut, 3 surgery, 4 face paint). The owner wants a looks-only creator (NG-C3); which mode that is, and
  what each shows with MQ101 stopped, is **unresolved** until the in-game C1 test (one mode per run). So the mode is a
  writer option, `--race-menu-mode <n>` (default 0, the full creator), written into the looks script's `RaceMenuMode`
  property; `check` and the selftest hold a build to its mode.
- Waiting for the creator: Starfield's Utility.psc has **no** `IsInMenuMode` (verified, PC precheck 19 Oct).
  **verified** (PC read, 19 Oct): ScriptObject has `RegisterForMenuOpenCloseEvent(string)` and the creator's menu is
  "ChargenMenu" (9 vanilla registrations). The looks script registers for it before the menu opens and sets stage 20 in
  `OnMenuOpenCloseEvent` when "ChargenMenu" closes. The event handler is written with FO4's signature
  `(string asMenuName, bool abOpening)`, **unverified** until the Papyrus compile on the PC; the precheck looks the
  registration and the event up in ScriptObject.psc, and a miss means `--no-looks`. The quest's `LooksWait` (120 s from
  stage 10, so it also covers a player who leaves the choice open) stays as the fallback. The log says which ended the
  wait: `looks done: creator closed`, `looks done: quick start` or `looks done: LooksWait fallback after <LooksWait> s`
  (Papyrus prints the float as `120.000000`); `make_newgame.py log` prints the first ending as `looks_done`. A later
  ending is not logged: once stage 20 is set, the looks script's `Done` does nothing.
- The looks script stays separate so a failed compile drops only it (`--no-looks`, and the quest then does not wait
  and shows no choice). FO4's own looks menu and the bathroom mirror are a later UI item (Scaleform;
  animations-ui-and-start.md section 3). SPECIAL is set at a vault terminal (NG-C4), not here (section 4a).

## 4a. SPECIAL at the vault terminal

- The owner decided (2026-10-19, NG-C4 / NG-K7, page NG-5): SPECIAL is set at a vault terminal for testing; the
  elevator version comes with the remade start. FO4 sets it pre-war with the Vault-Tec Rep, which our start skips.
- The stats: seven AVIF records of our own, `FO4SF_Special_Strength` to `FO4SF_Special_Luck` (FO4SFNewGame.esm 0x810 to
  0x816), each a SpecialAttribute with default 1, range 1 to 10, and the record's flags that name the same numbers
  (DefaultToOne, MinimumOne, MaximumTen: Mutagen's names for the AVFL bits). Starfield has no SPECIAL values, and
  nothing in this repo reads a Starfield AVIF back in full, so the record shape is minimal (name, abbreviation, type,
  default, min, max, those three flags) and **unverified** until the PC run opens the plugin in xEdit next to a shipped
  AVIF. Later phases read the player's values from these records (`Actor.GetValue`).
- The terminal: the points step lists every placed TERM of FO4's Vault111Cryo, nearest the player's pod first (the cryo
  hall's terminals stand by the pods), or the one `--terminal-ref <hex>` names. The writer takes the first of them the
  port carries (its `formids.json` key `REFR:FO4Port_Vault111Cryo:<FO4 id>:Fallout4.esm`), a persistent one preferred,
  and refuses a key that names a reference outside the cell or another plugin's record, as it does the anchor and the
  cog door. When the port carries none, the id is 0 and the prompt watches FO4's spot of the nearest terminal (the
  position is FO4's / 70 either way). A points.json without a terminal refuses a SPECIAL build: `--no-special`, or
  `--terminal-ref`. Which terminal the real cell gives, and whether the installed port carries it, is **unresolved**
  until the PC build (the points step prints every candidate; `offline_check.txt` prints the pick).
- The prompt: `FO4SF_NewGameSpecial` waits for stage 20 (the looks done), then shows MESG `FO4SF_NewGameTerminal`
  (0x803) once per visit when the player stands within 2.5 m of the terminal: "Set SPECIAL" or "Later". Set runs MESG
  `FO4SF_NewGameSpecial` (0x804) in a loop: its text has one `%.0f` token per stat and one for the points left, filled
  from `Message.Show`'s float arguments; the ten buttons are the seven stats, Reset, Confirm and Leave. A stat button
  adds a point (nothing past 10 in one stat, nothing with no points left); Confirm only applies with every point spent
  (a notification says how many are left); Leave keeps the defaults. The loop is bounded: after 300 presses without
  Confirm or Leave (`MaxPresses`, `SPECIAL_MAX_PRESSES`; a pass takes about 22) it ends as Leave and logs it, so a
  message box that returns at once cannot spin. Confirm writes each value with
  `Actor.SetValue(Special[i], value)` and reads two back into the log. `make_newgame.py special_press` is the same
  rule, tested in Python; the three constants live in `SPECIAL_BASE`, `SPECIAL_POINTS`, `SPECIAL_MAX` and are held
  equal to the writer's and the script's by `tests/test_newgame.py`.
- **Unverified** until the PC run: `Actor.SetValue` / `GetValue` with a plugin's own AVIF (FO4's Actor.psc declares
  them; the precheck reads Starfield's, and a miss means `--no-special`), the `%.0f` token substitution in a Starfield
  message box, and a ten-button message box (FO4's MESG limit).
- The quest never waits on SPECIAL: the player can ride the elevator with it unset. The script logs
  `special skipped: left the vault with SPECIAL unset` at stage 40, `special set S=.. P=.. ...` on Confirm, `special
  later` and `special left: ...` for the other buttons; `make_newgame.py log` prints the first ending as `special`.
- The script is separate for the same reason as the looks script: a failed compile drops only it (`--no-special`, and
  the plugin then carries no AVIF and neither MESG).

## 4b. The save version check

- The owner decided (2026-10-19, NG-F5 / NG-L2, page NG-15): a save version from v1, checked on every load with a
  visible warning. This is the first half; the launcher's block on unsafe swaps is a later item.
- The version: GLOB `FO4SF_NewGameVersion` (FO4SFNewGame.esm 0x805) holds the build's version number, `--build-version
  <n>` (default 1, `DefaultBuildVersion` in the writer and `DEFAULT_BUILD_VERSION` in Python, held equal by the tests).
  Bump it when a save made under the old build must not go on under the new one. The GLOB is flagged **Constant**: the
  Creation Kit documents a constant global as not saved, so a loaded save reads the installed plugin's number, not its
  own. Whether Starfield's save keeps that rule is **unverified** until the PC run.
- The alias: the quest's alias 0, "Player", is forced to the player (`PlayerRef` 00000014, the engine's fixed id; the
  door probe reads the player as ref 20). It carries `FO4SF_NewGameVersion`, bound through the quest's VMAD alias
  fragment (the quest's form and the alias id, the shape Mutagen reads back; whether the game binds the script the same
  way is **unverified** until the PC run).
- The script: when the alias fills (`OnInit`, a new game) it writes the GLOB's value into its `SavedVersion` property
  once; the save keeps it (-1 until then). On `OnPlayerLoadGame` (**verified**, PC read 19 Oct: declared on Actor and
  ReferenceAlias) it reads the GLOB again, logs `version load saved=<n> installed=<n>`, and on a mismatch logs `version
  mismatch` and shows "Fallout 4 new game: this save is from build <n>, the installed build is <n>". It sets no stage,
  moves nothing and writes no value: the save is left as it is. `make_newgame.py log` prints `version_saved`,
  `version_load` (the last load's line; a load logs no `init`, so it joins the run before it) and `version_mismatch`.
- Limits: a save that stood the quest down (stage 1, an existing save that gained the plugin) has no check, because the
  quest stops and the alias clears; nothing of ours is in that save to version. Whether the alias stays filled after the
  quest completes at stage 200, and so still receives the load event, is **unverified** until the PC run: the `version
  load` line on a reload after a completed start is the proof. If it does not, the check moves to a quest of its own.
- The script is separate for the same reason as the other two: a failed compile drops only it (`--no-version`, and the
  plugin then carries no GLOB of its own and no alias). The precheck looks `OnPlayerLoadGame` up in ReferenceAlias.psc
  and `OnInit` in ScriptObject.psc; a miss means `--no-version`.

## 4c. The starting inventory reset

- The question (NG-K8, with NG-N3): FO4's MQ101 runs RemoveAllItems at stages 0 and 900 (**verified**, the B4 spike and
  the 19 Oct script read); Starfield's MQ101 stage 0 swaps the outfit and removes items too (PC read 19 Oct). What a
  game started our way, with MQ00 and MQ101 held off before stage 0 has run or after it, leaves in the player's
  inventory is **unresolved** until the first in-game proof. So the reset is a writer option, **off by default**:
  `--clear-inventory`, and the quest script's `ClearInventory` property (false) and `VaultSuitId` (0) record the choice in
  the plugin; `check` holds a build to it, and the selftest's cross-option runs reject a build read under the other
  setting.
- When on: right after the move into the pod succeeds and before stage 10, `ResetInventory` calls
  `player.RemoveAllItems(None, false, false)` (the third argument false keeps quest items), reads
  `GetItemCount(None)` before and after and logs `inventory cleared removed=<n> left=<n> (quest items kept)`. Both
  natives are written with FO4's signatures; Starfield's `ObjectReference.psc` is what the precheck reads, and a miss
  fails the core script (there is no `--no-...` for it: the property is off, but the script must compile). Whether
  Starfield's `GetItemCount(None)` counts every item, as FO4's does, is **unverified**: both numbers are logged so the
  proof can say.
- The suit: `--vault-suit <EditorID>` (only with `--clear-inventory`; refused alone) names an ARMO of FO4Port.esm. The
  writer resolves it offline exactly as it does the anchors and the terminal: exactly one ARMO of that EditorID (any
  case) in the port, the port's own record, else refused (none, two, or another plugin's record). The script resolves it
  with `Game.GetFormFromFile(VaultSuitId, VaultPlugin) as Armor`, `AddItem(suit, 1, true)` and
  `EquipItem(suit, false, true)` (silent), and logs `vault suit equipped <armor> worn=<IsEquipped>`, or that the id did
  not resolve. Whether the installed port carries a wearable vault suit ARMO at all, and under which EditorID, is
  **unresolved**: the owner names it when it exists; the selftest uses a synthetic `FO4Port_VaultSuit111`.
- `make_newgame.py log` prints `inventory_cleared` and `vault_suit` (None when the build kept the inventory, or named no
  suit); plan.json records `clear_inventory` and `vault_suit`.

## 5. What Vault 111 needs from the port today

| Piece | State | Source |
|---|---|---|
| The cryo hall, corridors, stairs | converted and walkable (`coc FO4Port_Vault111Cryo`), sliding doors work | ROADMAP, owner rows 1 and 6 |
| Gear-room gates passable, gear-pit water sheet | fixes on main (static gate leaves, water planes left out); need an interior rebuild | ROADMAP Phase A table |
| Cog door VltGearDoor01 | converted as a door with its own rig (Stage2 as Open, `pipeline.OWN_RIG_ALIASES`, tests/test_cog_door.py); in game it was still a solid static on integ_1018. Whether the installed port carries the rigged door and whether `SetOpen` opens it: **unresolved** | ROADMAP, door_motion.py |
| Cog door console | FO4 activator with MQ03ControlPanelScript; ours is only a spot the quest watches | B4 |
| The SPECIAL terminal | FO4 TERM references of the cryo cell; the converted one is a prop, the SPECIAL script watches its spot (section 4a). Which one the port carries: **unresolved** | this plugin |
| Exit elevator | not connected: both autoload doors (interior 01F180, surface 0998E3) are marker doors the converter never places (`door_skipped`); the elevator is an animated activator. The new-game quest's prompt replaces the ride | scripted-doors.md, research log 2026-10-14 |
| Going back down | not handled: the surface elevator and the descend trigger are not converted; the doors phase owns it | B4 |
| Pip-Boy, the overseer's office skeleton, the cryo cut scene, the spouse, Kellogg | none: later phases (UI with SFSE; NPCs and scenes) | animations-ui-and-start.md |
| The surface arrival | core-local, from the XTEL of 01F180; whether the surface elevator platform is solid there is **unresolved**, hence the fall check and the map-marker fallback | this plugin |

## 6. Build recipe (PC, offline, no game)

1. `python scripts\newgame\make_newgame.py precheck --out D:\Modding\scratch\newgame\precheck.json` reads
   ContentResources.zip only and lists every native and event the four scripts use and every MQ101Debug line. Exit 1
   means a core native is missing: stop and report. A missing `Game.ShowRaceMenu`, `RegisterForMenuOpenCloseEvent` or
   `OnMenuOpenCloseEvent` means stage with `--no-looks`; a missing `Actor.SetValue` or `Actor.GetValue` means
   `--no-special`; a missing `OnPlayerLoadGame` or `OnInit` means `--no-version`. The inventory reset's natives
   (`RemoveAllItems`, `GetItemCount`, `AddItem`, `EquipItem`, `IsEquipped`) belong to the quest script, so a miss there
   is a core miss (section 4c).
2. `python scripts\newgame\make_newgame.py stage --out D:\Modding\staging\newgame_v1 --fo4 <Fallout4.esm> --port
   <installed FO4Port.esm> --port-ids <that port build's formids.json> --core <installed FO4TerrainCore.esm>` runs
   points, write, check and the Papyrus compile, then writes plan.json and README.txt. Inputs are read only; the output is
   one new folder on D:.
   Options: `--hold <list>` (default `MQ00,MQ101,MQ101PostQuest,MQ_TutorialQuest_Misc04`), `--mq101debug <n>`
   (default 10), `--no-mq101debug` (no GLOB override), `--no-looks`, `--race-menu-mode <n>` (default 0, section 4),
   `--no-special` (section 4a), `--no-version`, `--build-version <n>` (default 1, section 4b), `--pod-ref <hex>`,
   `--terminal-ref <hex>`, `--clear-inventory` and `--vault-suit <EditorID>` (off by default, section 4c). plan.json
   records them and the stage contract.
3. The offline checks are `offline_check.txt` (every record, property and resolved id) and the selftest
   (`dotnet run -c Release --project dotnet\NewGame -- selftest <scratch>`, synthetic masters and mutations). The
   selftest builds the default, `--no-looks`, `--no-mq101debug`, `--mq101debug 8`, no-cog-door, two-quest-hold,
   `--race-menu-mode 1`, `--no-special`, temporary-terminal-only, `--no-version`, `--build-version 2`,
   `--clear-inventory` and `--clear-inventory --vault-suit` variants, and each build must fail `check` under the
   others' options; `--vault-suit` without `--clear-inventory`, without an EditorID, or naming an ARMO the port lacks,
   has twice, or that another plugin owns is refused. It also checks the four MESG records (two buttons each,
   ten on the allocation), the seven AVIF, the looks script's `StartMessage` and `RaceMenuMode` properties, the SPECIAL
   script's list, messages and terminal, and the version GLOB (its value and Constant flag), the player alias (forced
   to 00000014, the only alias) and the alias script's binding and `BuildVersion` property; the terminal pick prefers a
   persistent reference and refuses a foreign or missing one.
4. Install is a later owner line: `fold` into a copy of the installed core set, `verify`, then `exp_install.py`, game
   closed, after the current v6e test. Testing needs a NEW game, so it never touches the owner's saves.

## 6a. The record reader (PC, read only, no game): one run for newgame.md sections K and N

`dotnet/NewGame/Records.cs` adds the `records` verb: it opens Starfield.esm, Fallout4.esm and the installed FO4Port.esm
read-only (Mutagen 0.55.0-alpha.67) and writes one plain-text report. Nothing else is written; a plugin or record that
is missing is said so in its section and the run still exits 0. The exact PC command (Fallout 4's Data folder is the
argument; Starfield's defaults to `D:\SteamLibrary\steamapps\common\Starfield\Data`, `--sf-data` for another):

```
dotnet run -c Release --project dotnet\NewGame -- records "<Fallout 4>\Data" --out D:\Modding\scratch\newgame\records.txt
```

Options: `--sf-data <dir>` (Starfield's Data folder), `--port <path>` (another FO4Port.esm than `<sf-data>\FO4Port.esm`),
`--nearest <n>` (how many persistent references the anchor section lists, default 30). The report's sections, and the
newgame.md question each answers:

| Section | Answers | What it lists |
|---|---|---|
| `NG-K1` | NG-K1 | MQ102 (Fallout4.esm 0001CC2A): every stage with its flags, each log entry's flags, text and conditions, the script fragments per stage, and `completes: stage <n>` for the log entries flagged CompleteQuest (or that none is, and completion is scripted) |
| `NG-K2` | NG-K2 | MQ101 (Fallout4.esm): stages 710 to 1000 in the same detail (the cryo scene, 770, 900) |
| `NG-K4` | NG-K4 | every reference in the port's Vault 111 cells (`FO4Port_Vault111*`) whose base record's EditorID mentions PipBoy: cell, reference, base, position (metres), persistence. None means the converted vault has no Pip-Boy prop under that name |
| `NG-K9` | NG-K9 | the conditions that reference MQ102 on records named Codsworth, Dogmeat or Min00 (quests: their own conditions, stage log entries, aliases, objective targets; dialogue responses, scenes and packages named so or owned by a quest named so) and on MQ102's own aliases named for them. It also reads NG-K3 (stage 6 sits in the K1 table) |
| `NG-N4` | NG-N4 (and NG-M1, NG-A1) | Starfield's MQ101 stage 0: each log entry's conditions and the stage's fragments (which of the 12 starts runs under which MQ101Debug value); MQ00's conditions, stages and aliases; the record 002EEA4D (SustenanceAllowed: type, conditions, links); every record whose EditorID mentions StartupQuest |
| `anchor` | the anchor and terminal picks (section 3, 4a) | the persistent references of `FO4Port_Vault111Cryo` nearest the player's pod (FO4's pod / 70; the COC marker when Fallout4.esm is absent) with base and distance, and every terminal in the cell with its persistence |

Conditions print as `[flags] Function(parameters) on <RunOn> <reference> <op> <value>`, every linked record as
`EditorID (Type id:plugin)`. Fallout 4 stores a condition's two parameters as unions (a record id and a number share the
bytes), so the first prints as the record when Fallout4.esm has one of that id, else the number, and the second as the
number with any record of that id after a bar; Starfield's parameters are typed per function. The selftest
(`records-selftest <scratch>`, also run by `selftest`) builds synthetic plugins covering every section, checks the
report line by line, and checks that a missing Fallout4.esm or port is reported, not fatal, and that only `--out` is
written. The real plugins have not been read yet: every fact the report will state is **unresolved** until that PC run,
and its findings go into newgame.md section N as the 19 Oct script read did.

## 7. First in-game proof (later, on the owner's word)

New game with the plugin installed. Record the log, `sqv MQ101`, `sqv MQ00` and screenshots at the pod, at the cog door
and on the surface. PASS means the log reaches stage 200 with "enter vault ok=True" and "landed", there is no Starfield
intro on screen, and the surface screenshot shows the Vault 111 elevator area. Then walk on from there: the
continuous-traversal gate starts at the vault exit.

## 8. Questions for the talk

1. Option A (stop the opening quests) as the default, B as the fallback? Or skip straight to B?
2. Character creation: decided (2026-10-19): looks only, in the vault, with a quick start (NG-C3, NG-C9). Open:
   which `ShowRaceMenu` mode is looks-only (NG-C1, the first in-game test).
3. Should players be able to pick Starfield's own start instead (option D)?
4. Hold off more of Starfield's 144 start quests now, or only after the first `sqv` record?

## 9. The stage contract (NG-14)

The owner decided (2026-10-19) that the start publishes fixed stages, as FO4's MQ102 does, so later phases and other
mods can listen to them. These are the stages of `FO4SF_NewGame` (FO4SFNewGame.esm 0x800). The numbers and their
meanings live in one place each: `scripts/newgame/make_newgame.py` `STAGE_CONTRACT` (the log summary and plan.json
read it), the header of `FO4SF_NewGameQuest.psc`, and this table; `tests/test_newgame.py` holds all three equal, and
the writer's `Stages` array must list every stage but 0. Stage 0 is the quest's start, not a stage record. A stage,
once reached, is never set back. Stage 20 is set by the looks script (the creator closed, or the quick start), or by
the quest after `LooksWait` seconds; a `--no-looks` build does not wait.

| Stage | Meaning |
|---|---|
| 0 | started: waiting for the player's 3D, then the guard and the hold-off |
| 1 | stood down: not a new game, nothing moved |
| 10 | in the vault: the player stands at their pod |
| 20 | looks done: character creation closed, or LooksWait passed |
| 30 | cog door opened: from its console |
| 40 | on the surface: the elevator ride is over |
| 200 | complete: landed, or put on the fallback spot |

`make_newgame.py log` prints the stages a run reached with these names (`stages_named`) and what each hold-off pass
stopped (`held_off_by_pass`). Objective 10, "Leave Vault 111", shows from stage 10 and completes at 40.

## Sources

- [SKK Fast Start New Game (Nexus Starfield 5971)](https://www.nexusmods.com/starfield/mods/5971): MQ101Debug = 8, the
  `NewAtlantisSpaceport03` check, MQ101 stage checks.
- [ECS Asteria (Nexus Starfield 16206)](https://www.nexusmods.com/starfield/mods/16206): a new game teleports the player
  from a start script and guards against mid-game installs.
- docs/spikes/B4-mission-anatomy.md section 3 (the Vault 111 exit chain, verified ids), docs/terrain/scripted-doors.md,
  docs/ROADMAP.md, scripts/door_bridge/FO4SF_LoadDoor.psc, the mission (#353) as the pattern.
