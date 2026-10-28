# A Fallout 4 new game: the Vault 111 start (phase 1)

Written 2026-10-19 by Claude-cloud (the new-game thread). Phase 1 of the approved roadmap: a new game that opens in
Vault 111 with no Starfield intro, which everything else plugs into. **In game once (28 Oct 2026, section 10): the first
build sent the owner to Starfield's pirate-fight developer start and our quest stood down; both causes are fixed
offline and the build waits for a restage.** Labels follow docs/ai/research-log.md (verified, supported hypothesis,
unresolved).

Files: `dotnet/NewGame/Program.cs` (the plugin writer and its checks), `dotnet/NewGame/Records.cs` (the read-only PC
record reader, section 6a), `scripts/newgame/FO4SF_NewGameQuest.psc` (the
quest script), `scripts/newgame/FO4SF_NewGameLooks.psc` (optional character creation),
`scripts/newgame/FO4SF_NewGameSpecial.psc` (optional SPECIAL at the vault terminal),
`scripts/newgame/FO4SF_NewGameVersion.psc` (optional save version check), `scripts/newgame/make_newgame.py` (precheck,
stage, verify, fold, log reader), `tests/test_newgame.py`.

## 1. What the player gets (the defaults)

1. **Start:** our quest starts with the game (start game enabled, run once) and waits each second until the player's 3D
   is loaded (Starfield's Utility.psc has no IsInMenuMode, so open menus are not awaited).
2. **Guard:** it acts only on a new game. That means fewer than one game day has passed, the player is at level 1, and
   Starfield's opening (`MQ101`) is running, still below stage 105, where it turns saving back on, and not completed. A
   save the player made always has the opening at 105 or later, so even an early level-1 save stands down (21 Oct
   review). A New Game has the opening running, because its stage 0 is what placed the player before our quest could
   run (section 11; **unverified** in game until run 3, whose `guard` line prints `opening_running`). A session started with `coc` from the main menu never starts MQ101, so it stands down too
   (since newgame_v9: Install's map-test session of 28 Oct on v8 found MQ101 not running, and the quest moved that
   character from Red Rocket into the vault). An existing save that gains the plugin stands the quest down at stage 1 and nothing
   moves. The owner's test saves are safe. The day limit was 0.25 in the first build, which stood every new game down:
   Starfield's clock starts at 8:00 and `GameDaysPassed` carries the hour, so a new game reads about 0.3335 a second in
   (**verified** in game 28 Oct, two runs; section 10). The guard now logs every reading it judges (the `guard` line).
3. **Starfield's opening is held off:** the quest stops `MQ00` (the main-quest start), `MQ101` (the opening),
   `MQ101PostQuest` and `MQ_TutorialQuest_Misc04` if they run, and logs each stop. The list is walked twice: once before
   the move, and once one tick later, because stopping MQ101 runs its stage 9000, which starts the last two (section 2).
   Saving and the HUD, which MQ101's stage 0 had turned off, are turned back on right after the first pass.
   The plugin overrides no Starfield record (section 2, B). MQ101's start stage picks its start by the global
   `MQ101Debug`: 0 is the intro, whose own fragment moves the player to its start marker and waits for the 3D; 1 and 3
   to 10 are developer starts (10, the first build's override, is the pirate fight: section 10). A value no entry
   matches moves nobody, and the new game never leaves its loading screen (the second build's override of 2: section
   11). So Starfield's intro places the player, our quest starts once that first load is through, and right after the
   hold-off's first pass has stopped MQ101 the quest writes 2 into the global itself (`SetValueInt`), logged as
   `mq101debug written=2.000000 was=0.000000`. 2 is the value the main quests' developer skip-start stages write; a
   normally finished intro leaves 0. It opens the sustenance condition (`MQ101Debug != 0`), whose normal route (MQ101
   stage 310) a held-off intro never reaches.
   The intro's stage 0 also empties the inventory and equips Starfield's miner spacesuit after its 3D wait; with the
   inventory reset off (the default, section 4c) the player wears it at the pod.
4. **The cryo pod:** the player is moved into the converted Vault 111 (`FO4Port_Vault111Cryo`) and stands up one metre
   in front of their own pod, facing out of it (on the installed port, which has no persistent reference in the cell,
   the script first loads the cell by centering on it: section 3a). The notification reads "Vault 111" and the objective is "Leave Vault
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
| **A. Stop the opening quests at start (default)** | Our start-game quest stops MQ00, MQ101, MQ101PostQuest and MQ_TutorialQuest_Misc04 from Papyrus (`Quest.Stop`), then moves the player. **verified** (ContentResources.zip, PC 19 Oct): MQ00's only fragment, stage 10, sets MQ101Debug to 10, waits 0.1 s and starts MQ101; MQ101Script's OnQuestInit jumps to stage 400 only when MQ101Debug reads 1. **verified** (records report, PC 21 Oct): MQ00 is "Important Script Functions and Aliases", StartGameEnabled with 18 aliases, and its stage 10 is not a start-up stage, so vanilla never runs it; holding MQ00 off is no longer load-bearing and stays in the list only as the approved default. **verified** (19 Oct read): MQ101's stage 9000 runs on stop; it always starts MQ101PostQuest and, when the player never entered the Unity, MQ_TutorialQuest_Misc04, and restores neither saving nor the HUD. So the script walks the hold-off list a second time one tick after the first pass (NG-19, NG-N1) and restores saving and the HUD itself | Edits no Starfield quest record; reversible by removing our plugin; the list is a build option (`--hold`) | **unresolved** whether one tick is enough for stage 9000 to have started its quests; with no override the intro's stage 0 has run (character generation on, the move to its start marker, the chargen HUD mode) before our quest starts, so the hold-off stops a running intro, and whether any of its scene, controls or menus outlive the stop is **unverified** until the next run (28 Oct: neither run reached the hold-off; the log says what each pass stopped) |
| **B. The debug global (written after the hold-off by default: `--debug-after-hold <n>`, 0 for no write; `--mq101debug <n>` overrides the record, experiments only)** | No record override. Right after hold-off pass 1 has stopped MQ101, the quest writes 2 into Starfield's GLOB `MQ101Debug` (0A7D31) with `SetValueInt`. **verified** (records report, PC 21 Oct, lines 352 to 396; the fragment sources, PC 19 Oct; the owner's two runs, 28 Oct): MQ101's stage 0 has 12 log entries, ten of them conditioned on the global. Entry 0 is the NG+ start (`PlayerUnityTimesEntered >= 1`, whatever the global holds). Entry 2 (`== 0`) is the normal intro: its fragment (`Fragment_Stage_0000_Item_02`) disables controls in MQ101's input layer, turns character generation on, moves the player to `CharGenStartMarker`, sets the chargen HUD mode and waits for the player's 3D; after the wait it empties the inventory, equips the miner spacesuit, helmet, backpack and clothes, and takes Lin's and Heller's weapons. Nothing after its 3D wait sets a stage or starts a scene, so stopping MQ101 then leaves nothing that restarts it. Entries 1 and 10 (`== 1`, `== 10`) and 3 to 9 (6, 3, 4, 5, 7, 8, 9) are developer starts, each moving the player itself; entry 11 has no condition and only ghosts Lin, Heller and Barrett. Entry 10's fragment (`Fragment_Stage_0000_Item_10`) moves the player to the Scene08 marker, equips the miner gear and the Cutter, enables Barrett's ship, sets stages 210 and 250 ("make pirate ship land") and the local time to 10: the pirate fight with no cutscene and no mine, where the owner landed in run 1 (log: `opening_stage=250`). A value no entry matches moves nobody: the second build's override of 2 left the new game on its loading screen (run 2, section 11). MQ00's stage 10 writes 10 and starts MQ101, but nothing runs that stage on a New Game (the records report: it is no start-up stage; StartupQuest_DO 00562D starts MQ101), so the 19 Oct belief that vanilla writes 10 was wrong. 2 is the value the main quests' developer skip-start fragments write (MQ102 to MQ305, FFLodge01 and City_NA_Viewport02, each of which then jumps MQ101 to its end: 1800 and 1810, or 2000); a normally finished intro leaves 0 (MQ101's own fragments never write the global). Writing it opens PEO_SustenanceAllowed's `MQ101Debug != 0`, whose normal route (`GetStageDone(MQ101, 310)`) a held-off intro never reaches (NG-2, NG-M1; its four conditions are in the 21 Oct report). SKK Fast Start's 8 is entry 8 (New Atlantis), a start that moves the player itself; RoleplayersAlternateStart writes its unmatched 11 only after its own quest has placed the player (the research thread's read, 28 Oct), the same order as ours | No record touched; the write comes after MQ101 is stopped, so its stage 0 never reads it; sustenance stays possible | **unverified** until the next run: the write's log line, and that nothing reads the global in the moment between the stop and the write |
| C. Override MQ00 / MQ101 without StartGameEnabled | Plugin overrides of Starfield's quest records | The opening never starts | Edits Starfield records; anything that expects MQ101 (NG+, Constellation, achievements) may break; hardest to undo in a save |
| D. Our own start menu (as SKK) | A message box after character creation picking Vault 111 or Starfield's own start | Players keep the choice | More UI; only worth it once the Fallout start works |

The ladder for the next in-game proof: the default (A, and B's write of 2 after the hold-off) first; `--debug-after-hold
0` if the write itself does harm (the global then stays at the intro's 0, and PEO_SustenanceAllowed's `!= 0` stays
closed). `--mq101debug 8` (SKK's New Atlantis start, a value an entry matches) is **not** a rung with today's guard:
entry 8 sets MQ101's stages 500 and 1310 itself, so the guard would read the opening past 105 and stand down, as it did
in run 1. Never an override no entry matches (2, 11): it hangs the first load (section 11). `--mq101debug 10` is the
first build's pirate-fight start, kept only to reproduce run 1; C only on the owner's word.
Which of Starfield's other 142
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
  contract): the vault anchor is a reference of `FO4Port_Vault111Cryo`, persistent when the cell has one (its COC marker
  when that is persistent, else the port's persistent reference nearest to it) and otherwise the cell's temporary COC
  marker, which the script must load the cell for first (section 3a: a temporary reference in an unloaded cell resolves
  to none, 16 Oct probe), and every resolved reference must be the named plugin's own record; the exit anchor is the core's persistent
  `FO4Core_CommonwealthMapMarkerVault111`; the cog door is the port's reference keyed
  `REFR:FO4Port_Vault111Cryo:0330C3:Fallout4.esm` (Mutagen prints six digits; the id is matched as a number) in its stable `formids.json`. The writer reads the port, its
  `formids.json` and the core to find those ids and refuses when any is missing or ambiguous; `check` re-reads them.
  Because port and core ids are stable across rebuilds, a rebuilt port or core does not need a rebuilt plugin, but the
  stage pins their SHA-256 and `verify` refuses an install against other bytes until the stage is re-run (a quick,
  offline re-check).
- Alternative: master FO4Port.esm and the core and place our own markers (a WRLD and CELL override, as the mission
  does). That costs a rebuild after every port or core build and ties the start to one build pair.

## 3a. The vault anchor: persistent, or the temporary COC marker

- **The evidence (PC, 21 Oct, real data):** the installed port's `FO4Port_Vault111Cryo` has **0 persistent references of
  1,166**; its COC marker is `001338:FO4Port.esm`, temporary, and every terminal is temporary. So the writer as it stood
  refused the build ("has no persistent reference of FO4Port.esm to anchor the start on"). **verified** (16 Oct probe):
  a temporary reference in an unloaded cell resolves to None via `Game.GetFormFromFile`, and `player.moveto` a
  non-persistent reference fails. A later port build (another thread) will make each cell's COC marker persistent with
  the same form id; until then the start needs a way in that does not depend on a persistent reference.
- **Two modes, one property.** The writer's `Resolve` prefers a persistent anchor (the COC marker when it is persistent,
  else the port's persistent reference nearest to it) and writes `AnchorTemporary = false`: the **persistent mode**, the
  one the start returns to by itself once the port marks its COC markers persistent (the id stays, so the same plugin
  needs no rebuild beyond the re-stage that pins the new port's bytes). When the cell has no persistent reference the
  writer anchors on the temporary COC marker itself and writes `AnchorTemporary = true` and `VaultCell =
  "FO4Port_Vault111Cryo"` (the cell's EditorID): the **temporary mode**. `write` and `check` print the mode after the
  anchor's id (`vault anchor FO4Port.esm:001338 temporary`), `offline_check.txt` keeps the line, `make_newgame.py`
  reads it into plan.json as `anchor` and `check` holds a build to its mode (a temporary-anchor build fails the check
  against a port with a persistent reference, and the other way round). `--require-persistent-anchor` restores the
  refusal, for a build that must not rely on the fallback.
- **The script in the temporary mode:** `EnterVault` resolves the anchor as before. When it comes back None and
  `AnchorTemporary` is set, `CenterOnVault` calls `Debug.CenterOnCell(VaultCell)` once, logs `centered on
  FO4Port_Vault111Cryo attempt=1 tick=1: ...` and returns false, so the existing 1 s retry resolves the now-loaded marker
  and does the same `MoveTo` with the pod's offset: the player, already standing in the cell on the COC marker after the
  centering, still ends at their pod, and the `enter vault ok=` line is the same proof as in the persistent mode. The
  wait is bounded: after `CenterTicks` ticks (30) without the anchor resolving the script centers once more, at most,
  and past that logs a failure line every 10 ticks (`vault anchor FO4Port.esm:<id> does not resolve after <n> ticks and
  <m> centerings on FO4Port_Vault111Cryo: the temporary-anchor start failed`) instead of recentering in a loop. The
  guard and the hold-off run before the first `EnterVault` as before (once, before the hold-off), so a centering never
  re-judges them; the persistent mode never centers.
- **What is unverified:** FO4 declares `Function CenterOnCell(string asCellname) native global` in Debug.psc. Starfield's
  Debug.psc is **believed** to declare `CenterOnCell` (and `CenterOnCellAndWait`), **unverified** until the PC precheck
  reads it (it is in the quest script's NATIVES, so a miss fails the precheck: the script would not compile); whether
  the call works in retail Starfield, loads the cell and leaves the player in it is **unverified** until the PC run (the
  `centered on` line followed by `enter vault ok=True` is the proof; the failure line is the counter-proof). The
  selftest covers the resolver and the plugin: the no-persistent-reference fixture (every reference of the cell
  temporary, as on the PC) writes a temporary-anchor build and still refuses under `--require-persistent-anchor`, and
  mutations of `AnchorTemporary` and `VaultCell` are rejected.
- `make_newgame.py log` prints `centered` (the first centering line's text; None in the persistent mode).

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
  them; Starfield's Actor.psc does not, but the script compiled for newgame_v7 on 23 Oct, so a script higher in Actor's
  `extends` chain does: the precheck follows that chain since run 2, section 11, and only a miss along the whole chain
  means `--no-special`), the `%.0f` token substitution in a Starfield
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

- The question (NG-K8, with NG-N3): FO4's MQ101 runs `PlayerREF.RemoveAllItems()` at stages 0 and 900 (**verified**
  from the SKK FastStart article and a forum post, research note 06-fo4-vault111-chain; the fragment itself was not
  read); Starfield's MQ101 stage 0 entry 2 (the intro) runs `RemoveAllItems()` after its 3D wait and equips the miner
  spacesuit, helmet, backpack and clothes (**verified**, PC read of QF_MQ101_00003448.psc, 19 Oct; NG-N3 answered).
  Since newgame_v9 that fragment runs before our quest, so a default build leaves the player in the miner suit at the pod
  (**unverified** in game until run 3). The answer is `--clear-inventory --vault-suit <the port's Vault 111 suit
  EditorID>`: the reset runs after the move into the vault, well after the fragment's few calls. The reset stays a writer option, **off by default** until the owner picks it:
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
   `--no-special` (a function counts as present when any script in the base's `extends` chain declares it, as the
   compiler resolves it); a missing `OnPlayerLoadGame` or `OnInit` means `--no-version`. The inventory reset's natives
   (`RemoveAllItems`, `GetItemCount`, `AddItem`, `EquipItem`, `IsEquipped`) belong to the quest script, so a miss there
   is a core miss (section 4c).
2. `python scripts\newgame\make_newgame.py stage --out D:\Modding\staging\newgame_v1 --fo4 <Fallout4.esm> --port
   <installed FO4Port.esm> --port-ids <that port build's formids.json> --core <installed FO4TerrainCore.esm>` runs
   points, write, check and the Papyrus compile, then writes plan.json and README.txt. Inputs are read only; the output is
   one new folder on D:.
   Options: `--hold <list>` (default `MQ00,MQ101,MQ101PostQuest,MQ_TutorialQuest_Misc04`), `--debug-after-hold <n>`
   (default 2, the value the quest writes after the hold-off; 0 writes nothing), `--mq101debug <n>` (a GLOB override,
   none by default, experiments only: a value no MQ101 entry matches hangs the first load, section 11;
   `--no-mq101debug` is kept for old command lines: alone it changes nothing, but it still cancels a `--mq101debug`
   given with it), `--no-looks`, `--race-menu-mode <n>` (default 0, section 4),
   `--no-special` (section 4a), `--no-version`, `--build-version <n>` (default 1, section 4b), `--pod-ref <hex>`,
   `--terminal-ref <hex>`, `--clear-inventory` and `--vault-suit <EditorID>` (off by default, section 4c), and
   `--require-persistent-anchor` (refuse a vault cell without a persistent reference instead of the temporary-anchor
   mode, section 3a). plan.json records them, the anchor's id and mode (`anchor`), and the stage contract.
3. The offline checks are `offline_check.txt` (every record, property and resolved id) and the selftest
   (`dotnet run -c Release --project dotnet\NewGame -- selftest <scratch>`, synthetic masters and mutations). The
   selftest builds the default, `--no-looks`, `--mq101debug 0`, `--mq101debug 8`, `--debug-after-hold 0`,
   `--mq101debug 10`, no-cog-door, two-quest-hold,
   `--race-menu-mode 1`, `--no-special`, temporary-terminal-only, `--no-version`, `--build-version 2`,
   `--clear-inventory` and `--clear-inventory --vault-suit` variants, and each build must fail `check` under the
   others' options; `--vault-suit` without `--clear-inventory`, without an EditorID, or naming an ARMO the port lacks,
   has twice, or that another plugin owns is refused. A port whose vault cell has no persistent reference (every
   reference temporary, the installed port's shape) builds a temporary-anchor plugin whose `write` and `check` lines say
   `temporary`, fails `check` against the port with persistent references (and that build fails against it), and is
   refused under `--require-persistent-anchor`. It also checks the four MESG records (two buttons each,
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

## 10. In game, run 1 (28 Oct 2026): FAIL, Starfield's pirate-fight developer start

**Build:** FO4SFNewGame.esm sha256 3fb78b14 (newgame_v7, staged 23 Oct at 118d5d8 against port 9AF962D2 and core
DC751664), installed on the owner's word 28 Oct with Plugins.txt QuestProbe, Core, Mars, Raider, Mission, NewGame,
Port, MapMarkers, Bridge (all nine active, Install's copy). Starfield 1.16.244, SFSE 0.2.21.

**The owner's report (17:29 and 17:35 UTC, typos fixed, meaning kept):** "I ended up at the beginning stage of the game
where you fight the pirates. That mission activated with no cutscene or anything; I didn't need to go through the mine
part." Then, after flying on: "I landed at Mars and don't see anything."

**The logs (Install's copy, `D:\Modding\testqueue\newgame_20261028\`):** four new games between 10:35 and 11:24 PC
time. Two ended within six seconds of the version line (`.3`, `.1`). The two that reached the guard stood down:

- `fo4sf_newgame.2.log` (10:44): `init holdoff=4 vault=fo4port.esm:4920 anchor_temporary=true core=fo4terraincore.esm:685915`,
  then `not a new game: days=0.333530 level=1 opening_stage=0 fresh=true: standing down`, `stage 1`.
- `fo4sf_newgame.0.log` (11:24): the same init, then `not a new game: days=0.333537 level=1 opening_stage=250
  fresh=false: standing down`, `stage 1`.

Papyrus.0.log has no error of ours. Starfield prints booleans as `true` / `false` and plugin names lowercased; the log
reader takes both spellings since this run.

**Cause 1, verified (records, fragments, log): the override's value.** The installed plugin overrides GLOB `MQ101Debug`
to 10 (read from the esm's GLOB group: `FLTV 10.0`). MQ101's stage 0 entry 10 needs `MQ101Debug == 10` (records report,
21 Oct) and its fragment sets stages 210 and 250, the pirate landing (the 19 Oct fragment copy, section 2, row B). That
is the start the owner described, and `opening_stage=250` is what our guard read. Our quest did run, saw the opening
past stage 105 and stood down as designed, so Vault 111 never came. The 19 Oct reading that vanilla writes 10 (MQ00's
stage 10) was wrong: that stage runs only when something sets it.

**Cause 2, verified (log): the day limit.** The 10:44 run stood down with the opening still at stage 0: `days=0.333530`
failed the 0.25 limit alone. Starfield's clock starts at GameHour 8 (the record's value) and `GameDaysPassed` carries
the hour, so every new game reads about 0.3335 a second in. The limit is now one game day; a player's save is kept out
by the opening-stage test, not by this number.

**Fix (#569, offline):** the override is 2, the inert start (row B); the day limit is 1.0; the guard logs every
reading it judges and the global as the game read it (`guard days=... opening_stage=... mq101debug=... expected=...`);
`make_newgame.py log` reports it as `guard`. Nothing else in the start changed. The hold-off, the saving and HUD
restore, `Debug.CenterOnCell`, the move into the vault, the cog door and the elevator are still **unverified in game**:
run 1 never reached them.

**Correction (run 2, section 11):** 2 is not an inert start. No stage-0 entry matches it, so nothing moves the player
and the new game never leaves its loading screen. Since newgame_v9 the plugin overrides nothing and the quest writes 2
after the hold-off.

**Mars:** the owner flew the vanilla game to Mars and landed at a vanilla site. Our world is an overlay worldspace on
Mars that a vanilla landing does not enter; it is reached by `coc FO4Core_RedRocketSpawn` or, once this start works,
by the Vault 111 elevator. Whether the "Commonwealth Landing Area" marker (#524) is offered as a landing choice from
orbit is the Map thread's question (its markers are known to register only after a visit, 24 Oct).

**Next on the PC (done 28 Oct):** newgame_v8 was restaged from main, reinstalled and run: section 11.

## 11. In game, run 2 (28 Oct 2026): FAIL, the new game never left its loading screen

**Build:** FO4SFNewGame.esm 5167F6AA (newgame_v8, staged from main e9c12e2b after #569): GLOB `MQ101Debug` overridden
to 2.0, the vault anchor FO4Port.esm:001338 (persistent), staged `--no-special` on the precheck's word. Install's copy of
Plugins.txt: QuestProbe, Port, Core, Mars, Raider, Mission, NewGame, MapMarkers, Bridge, all active. FOCCSidecar.dll
present with `bEnabled=0`. Starfield 1.16.244, SFSE 0.2.21.

**The owner's report (19:39 UTC, typos fixed, meaning kept):** "So I clicked new game a few minutes ago and it has just
been stuck on the loading screen. It's not crashed. I can't click any buttons or anything but there's a little loading
circle on the right." Then: "I can run console commands."

**The logs (Install's copy, `D:\Modding\testqueue\newgame_20261028_run2\`):** `fo4sf_newgame.0.log` has two lines, both
at 13:35:28 PC time (rt 64.0): the log opening and `version saved=1.000000 (new game)`. There is no `init holdoff` and
no `guard` line. The map and bridge scripts logged their init in their own logs and nothing after, at the same second.
Papyrus.0.log (13:34:36 to 13:35:28) holds only the engine's bind errors and property warnings of a new game's first
phase and vanilla `SFFL_SE_EC08` alias errors: none of the fragment loads and OnQuestInit lines that follow the first
load in run 1. Install's snapshot:
the game's main thread busy on one core, memory flat at 8.1 GB, the console working.

**Cause, verified (fragment sources, records, both runs' logs): the override's value.** MQ101's stage 0 runs the entry
whose `MQ101Debug` condition matches, and each start's fragment is what moves the player into the game: the intro's
entry 2 moves the player to `CharGenStartMarker` and waits for the 3D, entry 10 to the pirate landing. No entry
matches 2 (entry 11, the conditionless one, only ghosts three NPCs), so nobody moved the player and Starfield's first
load never finished. The quest did start: its version alias filled, and that is the `version saved` line. Its
OnQuestInit only fires after that load (run 1: 1 s and 7 s after `version saved`), so the script that acts never ran.
Run 3 reads the same way: a `version saved` line with no `init holdoff` line means the first load did not finish.
Section 10's "inert start" was wrong: 2 is a value the main quests' developer skip-start stages write, not a start.

**Ruled out:** FOCCSidecar.dll returns from `SFSEPlugin_Load` before registering anything when `bEnabled=0` (its
source); the plugin order loads every plugin after its masters; the vault anchor is read only by our quest's script,
which never ran.

**Fix (newgame_v9, offline):** the plugin overrides no record. Starfield's intro places the player as it does without
mods; our quest starts after that load, and the guard and the hold-off run as before. Right after hold-off pass 1 has
stopped MQ101, the quest writes `DebugAfterHold` (2) into the global with `SetValueInt`, the call the developer
skip-start fragments make. The guard line now ends `mq101debug=<read> write_after_hold=<n>`, and the write logs `mq101debug
written=<n> was=<n>`; `make_newgame.py log` reports both (`guard`, `mq101debug_written`). `--debug-after-hold 0`
writes nothing; `--mq101debug <n>` still builds an override for experiments. The guard now also needs MQ101
running, so a `coc` session from the main menu stands down (section 1, step 2).

**Install's map-test session (28 Oct, v8 installed, `coc FO4Core_RedRocketSpawn` from the main menu):** the quest ran
end to end on that character. The guard read `days=0.333532 level=1 opening_stage=0 fresh=true`; hold-off pass 1 held
MQ00 and found MQ101, MQ101PostQuest and MQ_TutorialQuest_Misc04 not running; saving and the HUD were restored; `enter
vault ok=true` in `FO4Port_Vault111Cryo`, stage 10, pass 2 stopped none, and the start prompt showed. So the move into
the vault and the prompt work once a load completes; stage 10 onward past the prompt was not exercised. It also showed
that a `coc` session passed the old guard, which v9 closes.

**SPECIAL:** v8 was staged `--no-special` because the precheck found neither `SetValue` nor `GetValue` in Starfield's
Actor.psc. The compiler resolves inherited functions, and v7 compiled the same script on 23 Oct, so the declarations
sit higher in the `extends` chain. The precheck now walks that chain, so v9 stages with SPECIAL again.

**Unverified in game:** the intro's stage 0 turns character generation on and sets the chargen HUD mode before our
quest starts; the hold-off's restore of saving and the HUD (section 1, step 3) is what undoes that. Its input layer is
deleted by MQ101's stage 9000 when we stop it. After its 3D wait the fragment empties the inventory and equips the miner
suit, which nothing undoes in a default build. The fragment and our first tick both follow the 3D load; entry 2 has no
stage set or scene after its wait, so the stop cannot be undone by it, and hold-off pass 2's lines for MQ101 would show
a restart. Run 3 is the first New Game that reaches the hold-off.

**Next on the PC:** after this PR merges, restage newgame_v9 from main against the installed port and core with SPECIAL
(no `--no-special` unless the precheck still reports a miss), reinstall on the owner's line, start a new game from the
main menu, then read `make_newgame.py log`. Expected: the `guard` line shows `opening_running=true` and ends
`mq101debug=0.000000 write_after_hold=2`, then `mq101debug written=2.000000 was=0.000000`; the player stands at the
pod in the miner spacesuit (the default build has no inventory reset; `--clear-inventory --vault-suit` is the answer).

## Sources

- [SKK Fast Start New Game (Nexus Starfield 5971)](https://www.nexusmods.com/starfield/mods/5971): MQ101Debug = 8, the
  `NewAtlantisSpaceport03` check, MQ101 stage checks.
- RoleplayersAlternateStart (GitHub ZeCroque, `Data/Scripts/Source/RAS`, read by the research thread 28 Oct): its
  startup quest places the player first and writes its unmatched MQ101Debug value afterwards.
- [ECS Asteria (Nexus Starfield 16206)](https://www.nexusmods.com/starfield/mods/16206): a new game teleports the player
  from a start script and guards against mid-game installs.
- docs/spikes/B4-mission-anatomy.md section 3 (the Vault 111 exit chain, verified ids), docs/terrain/scripted-doors.md,
  docs/ROADMAP.md, scripts/door_bridge/FO4SF_LoadDoor.psc, the mission (#353) as the pattern.
