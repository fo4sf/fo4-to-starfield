Scriptname FO4SF_NewGameQuest extends Quest
{A Fallout 4 new game in Starfield (fo4-to-starfield, docs/newgame/vault111-start.md): this quest is Starfield's startup
 quest (the plugin overrides the DefaultObject StartupQuest_DO, Starfield.esm 00562D, which names MQ101 in vanilla). On
 a NEW game it moves the player in front of their cryo pod in the converted Vault 111 (FO4Port.esm) during the first
 load, fades the screen in once the vault has loaded, holds off Starfield's start quests, opens the cog door from its
 console, and takes the player up the elevator onto the Commonwealth at Fallout 4's surface arrival. Every step and a
 status line every 5 s go to the user log "fo4sf_newgame" (My Games\Starfield\Logs\Script\User\fo4sf_newgame.0.log).
 Stages are the published contract (NG-14) other scripts and mods may listen to; make_newgame.py STAGE_CONTRACT lists
 the same numbers with the same meanings (tests/test_newgame.py) and the doc's stage table explains them:
   0 started: as Starfield's startup quest, the guard, the move into the vault and the hold-off
   1 stood down: not a new game, or no move into the vault (Starfield's opening is asked to start if the game still loads)
   5 mode chosen: start mode and survival choice stored
   10 in the vault: the player stands at their pod
   20 looks done: character creation closed, or LooksWait passed
   30 cog door opened: from its console
   40 on the surface: the elevator ride is over
   200 complete: landed, or put on the fallback spot
   210 warfare complete: landed at the faction start spot}
; KEEP EVERY DOC COMMENT AND STRING OF THIS SCRIPT SHORT: tests/test_papyrus_strings.py holds each at or under 3,072.
; newgame_v11 crashed the game while it loaded its data files, before the main menu, on every launch (29 to 31 Oct
; 2026), and v10 did not: the crash dump's register held this script's doc comment bytes 4,096 to 4,103, from a doc
; comment of 4,196 bytes (v10's was 2,745). So Starfield's script loader copies a doc comment into a 4 KB buffer and
; a longer one overwrites what follows it (supported hypothesis, from that dump). The notes below are ";" comments,
; which the compiler leaves out of the .pex. Name calls in them in words, with no opening bracket after the name:
; tests/test_newgame.py counts the calls in this file's text, these notes included.
;
; Why the start must move the player itself (records, PC 21 Oct; the three runs of 28 Oct): the startup quest is what
; moves the player into the game. MQ101's stage 0 picks its start by the GLOB MQ101Debug and the matching entry's
; fragment does the move (the intro's: MoveTo CharGenStartMarker, then WaitFor3dLoad); a value no entry matches moves
; nobody, and the new game never left its loading screen (run 2). Roleplayers' Alternate Start, the open-source mod that
; also replaces StartupQuest_DO, moves the player from its startup quest's OnQuestStarted (Game.FastTravel) and, once
; its start cell has loaded, calls FadeOutGame with (False, True, 0.0, 0.1, False) (";finishes main menu loading"). In
; run 2 our quest, start-game enabled then, never got its OnQuestInit while the version alias's OnInit did, so
; OnQuestInit waits for that first load (supported hypothesis); the start therefore runs from OnQuestStarted, with
; OnQuestInit as a second route, once, from whichever comes first (Begin). A start that finds no new game (a New Game+)
; or cannot move the player at all stands down and, when either of its readings says the game is still loading (the
; player's 3D not in, or no parent cell yet), first asks Starfield's opening to start (HandBack, which waits for
; nothing), so that its stage 0 moves the player and the first load does not wait on a move nobody makes (unverified:
; whether MQ101 started by a script during that load starts up then and moves the player). The temporary-anchor mode,
; whose centering during that load is unverified and hands nothing back when it moves nobody, is built only on request
; since newgame_v11 (the writer's --allow-temporary-anchor).
;
; MQ101 never runs, so the plugin overrides no MQ101Debug: right after the hold-off's first pass the quest writes
; DebugAfterHold (two, the value the main quests' developer skip-start stages write) into the global itself, which opens
; PEO_SustenanceAllowed, whose normal route (MQ101 stage 310) is never reached. The guard logs the value the game read
; (the "guard" line) and the write logs its own line ("mq101debug written").
;
; The places come from other plugins by their plugin-local form ids (the FO4SF_LoadDoor contract): this plugin has no
; master but Starfield.esm, so a rebuilt port or core never needs this plugin rebuilt while those ids stay (stable ids).
; The vault anchor has two modes (AnchorTemporary): a persistent reference, which resolves before the vault loads, or the
; temporary COC marker, which the script must load the cell for (Debug.CenterOnCell) before the same MoveTo (on request
; only since newgame_v11, see above).

GlobalVariable Property GameDaysPassed Auto Const Mandatory
{Starfield.esm 000039 (the record's value is 0; in game it reads about 0.3335 one second into a new game, the 8:00 clock,
 28 Oct). Part of the new-game guard (IsNewGame).}

Quest Property Opening Auto Const Mandatory
{Starfield's MQ101, the opening StartupQuest_DO names in vanilla. With the override nothing starts it on a New Game: the
 guard line logs its stage and whether it runs (0 and false expected), and HandBack asks it to start when our start
 stands down while the game is still loading, so that its stage 0 moves the player as it would have without this
 plugin (unverified: no run has stood down during the first load yet).}

GlobalVariable Property DebugGlobal Auto Const Mandatory
{Starfield's MQ101Debug (Starfield.esm 0A7D31). MQ101's stage 0 has 12 log entries, ten of whose conditions read it
 (records, PC 21 Oct): 0 is the normal intro (entry 2); 1 and 3 to 10 are developer starts; entry 0 is the NG+ start
 (PlayerUnityTimesEntered >= 1, whatever the global holds); entry 11 has no condition and only ghosts Lin, Heller and
 Barrett. Each matching entry's fragment moves the player into the game (entry 2:
 moves PlayerREF to CharGenStartMarker and waits for its 3D; entry 10: SetStage 210 and 250, the pirate fight the first
 build's override of 10 sent the owner to, run 1 of 28 Oct). A value no entry matches (the second build's 2) moves
 nobody, so Starfield's first load never completes (run 2 of 28 Oct). The plugin overrides the record no more; this
 property is read for the guard line and written after the hold-off's first pass, and HandBack never follows a write.}
int Property DebugAfterHold = 2 Auto Const
{Written into DebugGlobal with SetValueInt (the call MQ102's own fragment makes) right after hold-off pass 1, once the
 player has been moved; 0 writes nothing (the writer's --debug-after-hold). 2 is the value the main quests' developer
 skip-start fragments write (MQ102 to MQ305, FFLodge01, City_NA_Viewport02; each then jumps MQ101 to its end, 1800 and
 1810 or 2000; fragment sources, PC 19 Oct);
 a normally finished intro leaves the global at 0. It matches no start entry and opens PEO_SustenanceAllowed's
 "MQ101Debug != 0", whose normal route (MQ101 stage 310 done) is never reached when MQ101 never runs (records, PC 21
 Oct): the owner's decision NG-2 (we set it ourselves). Only after the move: a hand back to MQ101 must find the global
 as the game left it, or its stage 0 would match no entry.}

Quest[] Property HoldOff Auto Const Mandatory
{Starfield start quests stopped on a new game (the writer's --hold list, default MQ00, MQ101, MQ101PostQuest and
 MQ_TutorialQuest_Misc04: the main-quest start, the opening, and the two its stop starts; SQ_ENV, S13 row 2b; then
 S13 row 5's groups, the writer's HoldCompanions, HoldAudioTutorials, HoldCityFaction, HoldGenericDialogue,
 HoldActivities, HoldRadiant, HoldShips and HoldSystem lists, named with their ids in docs/newgame/vault111-start.md
 sections 4e to 4i). Walked twice: in the start,
 right after the move, and again once the vault has loaded, for a quest that started meanwhile (MQ00 is start-game
 enabled, and whether it starts before our start is unverified) and for what MQ101's stage 9000 starts if something had
 started MQ101. Each is stopped only if it runs; each stop is logged with its pass.}

Message Property ExitMessage Auto Const Mandatory
{The elevator prompt (FO4SFNewGame.esm 0x801): 0 Continue, 1 S.P.E.C.I.A.L., 2 Stay.}

Message Property ExitNeedAttrMsg Auto Const
{H00(b) modal notice (FO4SFNewGame.esm 0x81F): shown when Continue is picked before S.P.E.C.I.A.L. is confirmed.}

Message Property ExitFallbackMessage Auto Const Mandatory
{The lift fallback prompt (FO4SFNewGame.esm 0x81A): 0 Go up to the Commonwealth, 1 Retry lift.}

Message Property ReturnMessage Auto Const Mandatory
{The surface lift pad return prompt (FO4SFNewGame.esm 0x80B): button 0 rides back down to Vault 111, button 1 stays.}

Message Property ModePickMsg Auto Const Mandatory
{S4 Box 1 (0x806): 0 Story, 1 Warfare.}
Message Property StoryLineMsg Auto Const
{N2 Story choice (0x81E): available story campaigns from start_places.json.}
Message Property SurvivalPickMsg Auto Const Mandatory
{S4 Box 2 (0x807): 0 Survival: No, 1 Survival: Yes.}
Message Property WarfareDiffMsg Auto Const Mandatory
{S4 Box 3 (0x808): 0..3 starting difficulty.}
Message Property WarfareGroupMsg Auto Const Mandatory
{S4 Box 4 (0x809): starting Warfare faction.}
Message Property WarfareSpotMsg Auto Const Mandatory
{S4 Box 5 (0x80A): starting Warfare deployment spot.}
Message Property StartPickMsg Auto Const
{N2 pre-world appearance prompt (0x802): 0 Quick start, 1 Create character.}
Message Property NoPipboyMsg Auto Const Mandatory
{X2 / A16 (0x817): shown when activating the Vault 111 console before picking up the Pip-Boy.}

string Property VaultPlugin = "FO4Port.esm" Auto Const
int Property VaultAnchorId Auto Const Mandatory
{A reference in FO4Port_Vault111Cryo (the cell's COC marker, or the port's persistent reference nearest to it): MoveTo it
 with the pod's offset puts the player at their pod. Persistent when the port has one (the preferred mode); else the
 temporary COC marker with AnchorTemporary set (the installed port, PC 21 Oct: no persistent reference in the cell).}
bool Property AnchorTemporary = false Auto Const
{True when the anchor is a temporary reference (the writer found no persistent one): it resolves to None while the vault
 is unloaded (verified 16 Oct), so EnterVault first loads the cell with Debug.CenterOnCell on VaultCell, once, and the
 next tick's retry resolves the marker and does the same MoveTo. False is the persistent mode, which centers never.}
string Property VaultCell = "FO4Port_Vault111Cryo" Auto Const
{The vault cell's EditorID, what Debug.CenterOnCell takes in the temporary-anchor mode.}
int Property CenterTicks = 30 Auto Const
{The temporary-anchor mode's bound: after this many tries without the anchor resolving, one more centering at most,
 then a failure line every 10 tries ("vault anchor ... does not resolve after <n> ticks ..."), never a centering loop.
 The tries after the first are the timer's, which come only once the player's 3D is in (CenterOnVault).}
float Property AnchorX Auto Const Mandatory
float Property AnchorY Auto Const Mandatory
float Property AnchorZ Auto Const Mandatory
{The anchor's position in the cell (metres, FO4 position / 70, as the port writes it).}
float Property PodX Auto Const Mandatory
float Property PodY Auto Const Mandatory
float Property PodZ Auto Const Mandatory
float Property PodHeading Auto Const Mandatory
{Where the player stands up from their pod (Fallout 4's pod position plus a step out of it; heading in degrees).}
float Property PodLift = 0.3 Auto Const
{Metres above PodZ the player is put at, so they drop onto the floor. The pod's z is under the floor: run 3 of 28 Oct
 put the player at it (read back -1.045), the bridge saw them 0.69 m lower once the vault had loaded, and 0.64 s later they stood on the
 cell's COC marker 8 m away, moved there by the game (no script line, Papyrus.0.log). On that marker (z -0.738) they
 stood at -0.852; 0.3 above the pod's -1.029 is the marker's own height. The "pod settle" line judges it.}
float Property PodRadius = 1.0 Auto Const
float Property PodDrop = 0.5 Auto Const
{The "pod settle" check, the first tick the player is loaded after the move: within PodRadius (m) of the pod's x and y,
 and at most PodDrop under the start's z (PodZ + PodLift), is ok=true. Evidence only: nothing is moved again.}
int Property CogDoorId = 0 Auto Const
{The cog door VltGearDoor01 (FO4 000330C3) in the port, 0 when the port has none: opened from its console (no Pip-Boy).}
int Property ConsoleRefId = 0 Auto Const
{The gear door console MQ102GearDoorConsoleREF (FO4 00091A49) in the port, 0 when absent: activated with E to open the cog door.}
int Property PortPipboyStaticId = 0 Auto Const
{The ground Pip-Boy static MQ102PipboyTakeFurnitureREF (FO4 00075039) in the port, disabled when picked up.}
float Property ConsoleX Auto Const Mandatory
float Property ConsoleY Auto Const Mandatory
float Property ConsoleZ Auto Const Mandatory
float Property PlatformX Auto Const Mandatory
float Property PlatformY Auto Const Mandatory
float Property PlatformZ Auto Const Mandatory
{The stand spot RespecMoveMarker (FO4 0001B29E) on the floor of V111ElevatorREF (FO4 000244EB) at the bottom of its
 shaft: standing inside the open cage offers the ride up.}
int Property LiftId = 0 Auto Const
int Property LiftBaseId = 0 Auto Const
{Opt-in animated exit: the writer resolves the port's original V111ElevatorREF and its ACTI base. Zero keeps the
 earlier exit. Requires the separately staged production floor-start model, never the animation probe quest.}
float Property LiftRise = 21.6 Auto Const
float Property LiftSeconds = 9.8667 Auto Const
float Property LiftDoneMargin = 0.25 Auto Const
{Measured floor-to-top platform rise (-1.72 to 19.88 m), stage3 duration (9.8667 s), and Done-event arrival margin
 (0.25 s, ~7.5 frames at 30 Hz, covering the observed 9.794 s Done timestamp vs 9.8667 s clip duration while rejecting
 the 0.068 s stale Done from an earlier clip).}

string Property CorePlugin = "FO4TerrainCore.esm" Auto Const
int Property ExitAnchorId Auto Const Mandatory
{A persistent reference in the core world (its Vault 111 map marker): MoveTo it puts the player in the core world at
 the reference's LOCAL position (persistent references are not moved by the merge), a later tick's SetPosition then
 places them (FinishSurface).}
int Property ArrivalDiscoveryId = 0 Auto Const
{Only the canonical Vault 111 map marker, supplied by the writer; zero disables discovery for a custom exit anchor.
 The call is made after confirmed exterior arrival. Its return and the fast-travel reads do not prove map discovery.}
float Property ArrivalX Auto Const Mandatory
float Property ArrivalY Auto Const Mandatory
float Property ArrivalZ Auto Const Mandatory
float Property ArrivalHeading Auto Const Mandatory
{Fallout 4's surface arrival of the elevator ride (the XTEL of Vault111InteriorAutoLoadDoorREF 0001F180), core-local
 metres, heading in degrees.}
float Property FallbackX Auto Const Mandatory
float Property FallbackY Auto Const Mandatory
float Property FallbackZ Auto Const Mandatory
{The exit anchor's own position (core-local): where the player goes if the surface arrival drops them.}
float Property MergeOffsetX = -1200.0 Auto Const
float Property MergeOffsetY = -2700.0 Auto Const
{The core world's measured merge offset (vmad_patch.MERGE_MEASURED): the merged spot = local + this, z unchanged.}

float Property MaxNewGameDays = 1.0 Auto Const
{The guard: a new game has passed less than this many game days. Starfield's clock starts at GameHour 8 (the record's
 value, docs/ai/test-queue.md) and GameDaysPassed carries the hour, so a new game reads about 0.3335 a second in
 (verified in game 28 Oct, two runs: 0.333530 with MQ101 at stage 0, 0.333537 at 250; both read a second into the game,
 not during the first load, where the start reads it now); the first build's 0.25 stood every new game down on this
 test alone. A save the player made should never start this quest at all (supported hypothesis: only a New Game starts
 the startup quest, and the quest is not start-game enabled)...}
int Property MaxNewGameLevel = 1 Auto Const
{...and the player is at most this level: a New Game+ keeps the player's level, so its start stands down (stage 1)
 and, during the first load, asks MQ101 to start, whose entry 0 is the NG+ start (HandBack; that this moves the player
 is unverified). Supported hypothesis: that a New Game+ starts the startup quest, and that the kept level already reads
 during the first load; MQ101's own NG+ test is PlayerUnityTimesEntered >= 1.}
float Property ConsoleRadius = 2.5 Auto Const
float Property PlatformRadius = 2.0 Auto Const
float Property FallDrop = 3.0 Auto Const
{A landing this far below its target z (m) counts as a fall: the player is put on the fallback spot.}
float Property SurfaceWait = 10.0 Auto Const
{Seconds after the ride's MoveTo the player may still be inside before it counts as missed: one more MoveTo, then the
 elevator prompt again.}
int Property SurfaceTries = 3 Auto Const
{SetPositions on the merged arrival, one a tick. Exhaustion stops this exit with failure, without stage 40 or discovery.}
float Property LooksWait = 120.0 Auto Const
{Seconds stage 10 waits for the looks script (FO4SF_NewGameLooks, optional) to set stage 20 (the creator closed, or the
 quick start) before moving on: the fallback when the creator's close event never comes. 0 in a --no-looks build.}

bool Property ClearInventory = true Auto Const
{The starting inventory reset (NG-K8; on by default since S13 row 2, the strip-down of Starfield's own new-game
 items; the writer's --keep-inventory writes false). True: once the player is in the vault, RemoveAllItems (whether
 quest items stay is unverified, ResetInventory) and the count removed logged as "inventory cleared removed=<n>
 left=<n>"; then VaultSuitId.}
int Property VaultSuitId = 0 Auto Const
{With ClearInventory, the vault suit ARMO of the port (FO4Port.esm, resolved by the writer's --vault-suit <EditorID>),
 added and equipped after the reset; 0 is none. Logged as "vault suit equipped <armor> worn=<bool>".}
ActorValue Property O2Capacity Auto Const
{Starfield.esm 0002E2, the O2 capacity a spacesuit's pack adds (an engine value with no record; the writer links it by
 id). With no suit it is 0, Oxygen reads 0 and the O2/CO2 dial is red; +100 clears the dial (PC, 15 Nov). S13 row 2b.}
float Property O2CapacityAmount = 0.0 Auto Const
{With ClearInventory, what FillO2 tops O2Capacity up to, once, right after the reset (the writer's default 100;
 --no-o2-fill and --keep-inventory write 0: nothing). Logged as "o2 capacity added=<n> value=<read back>".}
GlobalVariable Property TestModeGlobal Auto Const
{FO4SFCoreValues.esm FO4SF_TestModeEnabled (0x860), linked by the writer so FO4SFNewGame.esm masters FO4SFCoreValues.esm.}
GlobalVariable Property StartCardOpenGlobal Auto Const
{FO4SFCoreValues.esm FO4SF_StartCardOpen (0x866), drives non-modal FO4SF_StartCardMenu when StartChoiceBackdrop is 2.}
GlobalVariable Property GameModeGlobal Auto Const Mandatory
{FO4SFCoreValues.esm FO4SF_GameMode (0x870): 0 unset, 1 Story, 2 Warfare.}
GlobalVariable Property SurvivalStartGlobal Auto Const Mandatory
{FO4SFCoreValues.esm FO4SF_SurvivalStart (0x871): 0 or 1.}
GlobalVariable Property SurvivalLockedGlobal Auto Const Mandatory
{FO4SFCoreValues.esm FO4SF_SurvivalLocked (0x872): 0 or 1.}
GlobalVariable Property StartDifficultyGlobal Auto Const Mandatory
{FO4SFCoreValues.esm FO4SF_StartDifficulty (0x873): 0..3.}
GlobalVariable Property WarfareFactionGlobal Auto Const Mandatory
{FO4SFCoreValues.esm FO4SF_WarfareFaction (0x874): -1 or 0..7.}
GlobalVariable Property WarfareStartIndexGlobal Auto Const Mandatory
{FO4SFCoreValues.esm FO4SF_WarfareStartIndex (0x875): -1 or row index.}
GlobalVariable Property StartChoiceDoneGlobal Auto Const Mandatory
{FO4SFCoreValues.esm FO4SF_StartChoiceDone (0x876): 0 or 1.}
GlobalVariable Property StartNeutralSpotGlobal Auto Const Mandatory
{FO4SFCoreValues.esm FO4SF_StartNeutralSpot (0x877): 0 default, >= 0.5 logs neutral-room hold during pre-world mode choice.}
GlobalVariable Property StoryLineGlobal Auto Const
{FO4SFCoreValues.esm FO4SF_StoryLine (0x878): selected Story campaign index.}
GlobalVariable Property StartPlaceRowGlobal Auto Const
{FO4SFCoreValues.esm FO4SF_StartPlaceRow (0x879): selected active row in StartPlaceIds.}
GlobalVariable Property PipboyAcquiredGlobal Auto Const Mandatory
{FO4SFCoreValues.esm FO4SF_PipboyAcquired (0x865), set to 1 once the Pip-Boy 3000 is picked up beside the Vault 111 console.}
GlobalVariable Property H00SkipLoadingHookGlobal Auto Const
GlobalVariable Property H00ClearChargenGlobal Auto Const
GlobalVariable Property H00SkipArrivalDiscoveryGlobal Auto Const
GlobalVariable Property H00SkipMapSetupGlobal Auto Const
GlobalVariable Property H00SkipRouteLootGlobal Auto Const
GlobalVariable Property H00SkipMissionActorsGlobal Auto Const
GlobalVariable Property H00SkipLandingQuestsGlobal Auto Const
GlobalVariable Property H00SkipSurfaceSetPosGlobal Auto Const
Armor Property PipboyWristArmor Auto Const Mandatory
{FO4SFNewGame.esm FO4SF_PipboyWrist (0x80D), playable left-wrist Pip-Boy 3000 equipped on pickup.}
ObjectReference Property PipboyCorpseRef Auto Const Mandatory
{FO4SFNewGame.esm FO4SF_PipboyCorpsePickupRef (0x80F), placed persistent pickup beside the Vault-Tec scientist skeleton.}
ObjectReference Property GearDoorConsoleRef Auto Const Mandatory
{FO4SFNewGame.esm FO4SF_GearDoorConsoleRef (0x819), placed persistent named activator at the gear-door console.}
ObjectReference Property StartRoomMarkerRef Auto Const
{FO4SFNewGame.esm FO4SF_StartRoomMarkerRef (0x81D), persistent marker in owned empty FO4SF_StartRoomCell (0x81C).}
Weapon Property VaultPistolBase Auto Const Mandatory
{Starfield.esm WEAP for vault111.pistol_id from route_loot_ids.json, filtered for OnItemAdded.}
int Property VaultPistolId = 0 Auto Const
{Plugin-local FormID of VaultPistolBase in Starfield.esm, logged when adding the inventory event filter.}
bool Property FadeHold = false Auto Const
{W1 / T3: false by default so New Game enters Vault 111 Story mode directly (--fade-hold opts in to pre-world start setup).}
int Property StartChoiceBackdrop = 1 Auto Const
{N2 / S1 / R5 backdrop variant: 1 empty_cell (default), 2 title_card (FO4SF_StartCardMenu), 3 setup_menu (FO4SF_SetupMenu), 0 none.}
float Property StartLoadTimeout = 15.0 Auto Const
{H0 / R10 hard ceiling (seconds) waiting for LoadingMenu close before forcing fade lift and showing set-up prompts.}
bool Property MuteArrivalDiscoveryPopup = true Auto Const
bool Property SilentStarterStrip = true Auto Const
Form[] Property StarterStripItems Auto Const
bool Property SinglePassLandingFade = true Auto Const
string Property PodExitMode = "safe_spawn" Auto Const
float Property PodSafeStep = -3.2 Auto Const
float Property PodSafeHeading = 270.0 Auto Const
bool Property HasPodSafeExitOverride = false Auto Const
int Property RaceMenuMode = 2 Auto Const
{Looks-only creator mode (2 = body and face) shared with FO4SF_NewGameLooks.}
int[] Property CoreMarkerIds Auto Const
{Persistent map marker FormIDs in FO4TerrainCore.esm prepared during shared map setup.}
int[] Property RouteLootRefIds Auto Const
{Exterior corridor container REFR FormIDs in FO4TerrainCore.esm overridden by FO4SFRouteLoot.esm, nearest to exit anchor first.}
int[] Property MapMarkerQuestIds Auto Const
{Optional FO4SFMapMarkers.esm quest FormIDs resolved during shared map setup.}
string[] Property WarfareKeys Auto Const
int[] Property WarfareFactionSlots Auto Const
int[] Property WarfareDistinctFactionSlots Auto Const
int[] Property WarfareMarkerIds Auto Const
float[] Property WarfareMarkerX Auto Const
float[] Property WarfareMarkerY Auto Const
float[] Property WarfareMarkerZ Auto Const
float[] Property WarfareHeadings Auto Const
int[] Property WarfareMinDiffs Auto Const
int[] Property WarfareMaxDiffs Auto Const
int[] Property WarfareBgIndices Auto Const
float[] Property WarfareFames Auto Const
float[] Property WarfareInfamies Auto Const
float[] Property WarfareKarmas Auto Const
int[] Property WarfareSquadCaps Auto Const
int[] Property WarfareGearRowIndices Auto Const
string[] Property WarfareGearPlugins Auto Const
int[] Property WarfareGearIds Auto Const
int[] Property WarfareGearCounts Auto Const
bool[] Property WarfareGearEquips Auto Const
string[] Property StoryChoiceIds Auto Const
string[] Property StartPlaceIds Auto Const
int[] Property StartPlaceModes Auto Const
string[] Property StartPlaceStories Auto Const
string[] Property StartPlacePlugins Auto Const
int[] Property StartPlaceMarkerIds Auto Const
float[] Property StartPlaceX Auto Const
float[] Property StartPlaceY Auto Const
float[] Property StartPlaceZ Auto Const
float[] Property StartPlaceHeadings Auto Const
bool[] Property StartPlaceIsInterior Auto Const
int[] Property StartPlaceQuestMasks Auto Const
int[] Property StartPlaceWarfareRows Auto Const

string LogName = "fo4sf_newgame"
int ticks = 0
float startedAt = 0.0
float arrivedAt = 0.0
bool asked = false
int applied = 0
int centerTries = 0
int centered = 0
bool begun = false                                           ; Begin ran (from OnQuestStarted or OnQuestInit)
bool routed = false                                          ; the start's "start route=" line is written
string lateRoute = ""                                        ; the other start event, when it came before that line
int startRoomMoves = 0                                       ; MoveTo calls onto FO4SF_StartRoomMarkerRef
bool startRoomEntered = false                                ; the player stands in FO4SF_StartRoomCell after a move
bool startRoomUiPrepared = false                             ; fade lifted + body/HUD hidden in FO4SF_StartRoomCell
int vaultMoves = 0                                           ; MoveTo calls onto the vault anchor
bool entered = false                                         ; the player stands in the vault anchor's cell after a move
bool faded = false
int warfareFadeTicks = 0
int storyFadeTicks = 0
bool loadingMenuOpen = false
bool loadingMenuClosedSeen = false
bool loadingHookRegistered = false
bool startUiReady = false
bool h00SuspectsRead = false
bool h00SkipLoading = false
bool h00ClearChargen = false
bool h00SkipDiscovery = false
bool h00SkipMap = false
bool h00SkipLoot = false
bool h00SkipActors = false
bool h00SkipQuests = false
bool h00SkipSetPos = false
bool modeChoiceRan = false
bool modeBoxWaiting = false
int modeBoxWaitSeconds = 0
bool preworldLooksDone = false
string preworldLooksHow = ""
string preworldLooksBy = "Trigger"
bool setupWaitingCreator = false
int pendingStage = -1
string pendingStageBy = "other"
bool looksSetStage20 = false
bool loadHookRegistered = false
bool podChecked = false
float surfaceMovedAt = 0.0                                   ; the ride's MoveTo (real time); 0 while none is pending
int surfaceMoves = 0
int surfaceSets = 0
WorldSpace arrivalWorld = None
int exitFailures = 0
bool exitUsedFallback = false
bool fallbackPending = false
bool discoveryMarkerMoved = false
bool discoveryAttachPending = false
int landingChecks = 0
ObjectReference ridingLift = None
Cell ridingCell = None
float rideStartedAt = 0.0
float riderX = 0.0
float riderY = 0.0
float riderZ = 0.0
bool rideActive = false
bool rideDone = false
bool rideTransferred = false
bool rideFadeStarted = false
InputEnableLayer scannerLayer = None
bool consoleRegistered = false
ObjectReference consoleWatchedRef = None
bool portConsoleRegistered = false
ObjectReference portConsoleWatchedRef = None
bool consoleOpening = false
bool cogDoorRegistered = false
ObjectReference cogDoorWatchedRef = None
bool pipboyRegistered = false
bool pipboyEquipWatchRegistered = false
bool pipboyPickedUp = false
bool itemWatchRegistered = false
bool pistolPickedLogged = false
bool liftSpecConfirmed = false
bool warfareWaitingCreator = false
bool mapSetupDone = false
bool rideMarkerPrepared = false
bool leftArrivalPad = false
bool returnLiftArmed = false
int returnArmTicks = 0
bool returnHasExteriorSample = false
float returnLastExteriorX = 0.0
float returnLastExteriorY = 0.0
bool returnAsked = false
bool returnVaultAsked = false
bool returnSurfacePending = false
int returnSurfaceWaitTicks = 0
int returnSurfaceTries = 0
bool dyingHookRegistered = false
bool vaultPodAutosaved = false
bool vaultSavingRelocked = false
bool vaultRecoveryTriggered = false
int vaultPodAutosaveSkips = 0
bool surfaceFadeInDone = false
bool podExitDone = false

Event OnQuestStarted()
    Begin("OnQuestStarted")
EndEvent

Event OnQuestInit()
    Begin("OnQuestInit")
EndEvent

Function Begin(string route)
{The start, once, from whichever start event comes first; the other only logs that it came, after the start's route
 line (it can arrive while the start is in a call, which releases the script's lock). It runs while the game is still
 on its first loading screen: the guard; on a new game the move into the vault (EnterVault), then the hold-off's first
 pass and the MQ101Debug write; then the timer starts and the start waits for the player's 3D (WaitFor3DLoad, as
 MQ101's own intro entry does after its move) and, if the 3D is in when the wait returns, fades the screen in
 (FadeIn); otherwise, or if the timer sees the 3D first, the timer does. The order is the safety: nothing is held off
 or written before the player has been moved, so a HandBack always finds Starfield's start as the game left it.}
    if begun
        if routed
            Trace("start event " + route + " came after the start: nothing to do")
        else
            lateRoute = route                                ; written right after the start's route line
        endif
        return
    endif
    begun = true
    Debug.OpenUserLog(LogName)
    Trace("init holdoff=" + HoldOff.Length + " vault=" + VaultPlugin + ":" + VaultAnchorId + " anchor_temporary=" + AnchorTemporary + " core=" + CorePlugin + ":" + ExitAnchorId)
    Actor player = Game.GetPlayer()
    bool loaded = player.Is3DLoaded()
    Cell startCell = player.GetParentCell()
    ; still on the first load if either reading says so: a stand-down hands back then (StandDown)
    bool loading = !loaded || startCell == None
    Trace("start route=" + route + " player_loaded=" + loaded + " cell=" + startCell + " loading=" + loading)
    routed = true
    if lateRoute != ""
        Trace("start event " + lateRoute + " came after the start: nothing to do")
    endif
    ; every reading the guard judges, and the debug global as the game read it (the 28 Oct runs: the cause of a stand-down
    ; had to come from the records until this line carried it)
    float days = GameDaysPassed.GetValue()
    int level = player.GetLevel()
    Trace("guard days=" + days + " level=" + level + " opening_stage=" + Opening.GetStage() + " opening_running=" + Opening.IsRunning() + " mq101debug=" + DebugGlobal.GetValue() + " write_after_hold=" + DebugAfterHold)
    if !IsNewGame(days, level)
        Trace("not a new game: days=" + days + " level=" + level + " loading=" + loading + ": standing down")
        StandDown(loading, "not a new game")
        return
    endif
    if UsePreworldRoom()
        startRoomEntered = EnterStartRoom(player)
    else
        entered = EnterVault(player)
    endif
    if startRoomMoves == 0 && vaultMoves == 0 && centered == 0
        ; nothing moved the player, so the first load would never end (28 Oct run 2)
        Trace("no move into the vault: anchor " + VaultPlugin + ":" + VaultAnchorId + " does not resolve; standing down")
        StandDown(loading, "no move into the vault")
        return
    endif
    HoldOffPass(1)
    DisableHandScanner()
    if DebugAfterHold != 0
        ; MQ101 never runs, so its stage 0 never reads this; the write opens the sustenance condition (DebugAfterHold)
        float was = DebugGlobal.GetValue()
        DebugGlobal.SetValueInt(DebugAfterHold)
        Trace("mq101debug written=" + DebugGlobal.GetValue() + " was=" + was)
    endif
    EnsureLoadHookRegistered(player)
    loadingMenuOpen = loading
    if UsePreworldRoom() || FadeHold
        RegisterStartLoadingHook()
    endif
    StartTimer(1.0, 1)
    player.WaitFor3DLoad()                                   ; latent: returns once the 3D is in, or will not load
    bool ready = player.Is3DLoaded()
    Trace("3d wait over loaded=" + ready)
    if ready
        if UsePreworldRoom()
            PrepareStartRoomUi("start")
            Game.ShowFirstPersonGeometry(false)
        else
            FadeIn("start")                                  ; else the timer fades in once the 3D is in
        endif
    endif
EndFunction

Function StandDown(bool loading, string why)
{While the game is still loading (either reading of the start: the player's 3D not in, or no parent cell yet),
 Starfield's opening is asked to start first (HandBack), since nothing else would move the player: before our own
 stage, whose SetStage is latent (Quest.psc: it waits for the quest to start up if it needed to be started) while Begin
 may run from OnQuestInit, our quest still starting up. That this SetStage returns is a supported hypothesis:
 MQ101Script, the startup quest's own script in vanilla, sets stage 400 from its OnQuestInit when MQ101Debug is 1
 (ContentResources.zip, read 29 Oct). Then stage 1 and the quest stops. A stand-down on a running game (startquest from
 the console on a played save: a game day or more, or above level 1) moves nothing and hands nothing back.}
    if loading
        HandBack(why)
    endif
    AdvanceTo(1)
    Stop()
EndFunction

Function HandBack(string why)
{Starfield's opening is asked to start as it would have without this plugin, so that its stage 0 moves the player
 (New Game+'s entry 0, whatever MQ101Debug holds; the intro at 0). Unverified: whether MQ101 started by a script during
 the first load starts up then and moves the player; no run has stood down during that load yet. StartNoWait returns at
 once (Quest.psc: it does not wait for aliases to fill or fragments to run), so nothing of ours waits on MQ101's
 start-up and the "handed back" line always follows: the request's result and MQ101's state at that moment (starting,
 not yet running, is a start under way, not a verdict). The verdict is the screen: Starfield's intro, or a loading
 screen that stays up. Papyrus.0.log cannot tell: MQ101's own Debug.Trace lines are not in run 3's, though its stage 0
 ran then. Called only from StandDown, before anything of ours was held off or written.}
    Trace("handing back to Starfield's start: " + why + "; mq101debug=" + DebugGlobal.GetValue())
    bool requested = Opening.StartNoWait()
    Trace("handed back: requested=" + requested + " opening starting=" + Opening.IsStarting() + " running=" + Opening.IsRunning() + " stage=" + Opening.GetStage())
EndFunction

Function FadeIn(string by)
{Once, from the start's wait or the timer, whichever sees the player's 3D first: each caller checks Is3DLoaded before it
 calls, so the fade never comes while the 3D is still out (the start's wait can return before it is in, and the
 precedent fades only once its start cell has loaded). A player the start moved into the vault is turned to the pod's
 heading again first (EnterVault's turn came during the load; whether it holds then is unverified, and the screen is
 still dark now). Game.FadeOutGame(False, True, 0.0, 0.1, False) then fades in from black over 0.1 s, the call
 Roleplayers' Alternate Start makes once its start cell has loaded. Whether the loading menu can still be up once the
 3D is in is unverified. MQ101's own fragments wait 0.1 s before they fade (with Utility's Wait, which does not run in
 menu mode), since a fade requested while it is up "would be bashed when the loading menu goes away and tells the
 fade menu to fade in" (QF_MQ101_00003448), and its intro entry (Item_02) makes no fade call at all: so a fade of ours
 that comes that early gives way to the loading menu's own fade in, and the screen still comes in (supported
 hypothesis, from that fragment). Then saving and the HUD are turned on: MQ101 never ran, so nothing should have
 turned them off (its stage 0 does, and newgame_v9 had to turn them back on), but a run must not depend on that.}
    if faded
        return
    endif
    faded = true
    UnregisterStartLoadingHook()
    Actor player = Game.GetPlayer()
    if vaultMoves > 0 && StandsInVault(player)
        player.SetAngle(0.0, 0.0, PodHeading)
    endif
    Game.ShowFirstPersonGeometry(true)
    Game.FadeOutGame(False, True, 0.0, 0.1, False)
    Game.SetInChargen(false, false, false)
    Game.SetCharGenHUDMode(0)
    DisableHandScanner()
    Trace("fade in by=" + by + " loaded=" + player.Is3DLoaded() + " cell=" + player.GetParentCell() + "; saving and HUD on")
EndFunction

Function DisableHandScanner()
{Disable Starfield's Chronomark hand scanner (F / MonocleMenu) on a Fallout 4 new game.}
    if scannerLayer == None
        scannerLayer = InputEnableLayer.Create()
        if scannerLayer != None
            scannerLayer.EnableHandscanner(false)
            Trace("blocked input=handscanner")
        endif
    endif
EndFunction

Function NoteLooksStage20()
    looksSetStage20 = true
    RunPodExitHook(Game.GetPlayer())
    if applied < 20
        applied = 20
    endif
    if GetStage() < 20
        SetStage(20)
    endif
    TriggerVaultPodRecoveryAutosave(20)
EndFunction

bool Function IsPreworldLooksHandled()
    if !FadeHold
        return looksSetStage20
    endif
    return preworldLooksDone || looksSetStage20 || UsePreworldRoom()
EndFunction

Function RunPodExitHook(Actor player)
{Stage 15 pod-exit seam: places the player clear of the cryo pod facing PodSafeHeading (safe_spawn) or reserves the cryopod_anim hook without touching fade or exit lift.}
    if podExitDone
        return
    endif
    podExitDone = true
    if GetStage() < 15
        SetStage(15)
    endif
    if applied < 15
        applied = 15
        Trace("stage 15 by=" + PodExitMode)
    endif
    if PodExitMode == "cryopod_anim"
        float animX = PodX
        float animY = PodY
        float animZ = PodZ + PodLift
        float animHdg = PodHeading
        if player != None
            animX = player.GetPositionX()
            animY = player.GetPositionY()
            animZ = player.GetPositionZ()
            animHdg = player.GetAngleZ()
        endif
        Trace("pod_exit mode=cryopod_anim_hook hook_stage=15 clear=true pos=" + animX + " " + animY + " " + animZ + " heading=" + animHdg)
        return
    endif
    if PodExitMode == "safe_spawn"
        float safeX = PodX
        float safeY = PodY
        if !HasPodSafeExitOverride
            safeY = PodY + (PodSafeStep + 2.5)
        endif
        float safeZ = PodZ + PodLift
        if player != None && player.IsInInterior() && StandsInVault(player)
            player.SetPosition(safeX, safeY, safeZ)
            player.SetAngle(0.0, 0.0, PodSafeHeading)
        endif
        float outX = safeX
        float outY = safeY
        float outZ = safeZ
        if player != None
            outX = player.GetPositionX()
            outY = player.GetPositionY()
            outZ = player.GetPositionZ()
        endif
        Trace("pod_exit mode=" + PodExitMode + " hook_stage=15 clear=true pos=" + outX + " " + outY + " " + outZ + " heading=" + PodSafeHeading)
        return
    endif
    float curX = PodX
    float curY = PodY
    float curZ = PodZ + PodLift
    float curHdg = PodHeading
    if player != None
        curX = player.GetPositionX()
        curY = player.GetPositionY()
        curZ = player.GetPositionZ()
        curHdg = player.GetAngleZ()
    endif
    Trace("pod_exit mode=" + PodExitMode + " hook_stage=15 clear=true pos=" + curX + " " + curY + " " + curZ + " heading=" + curHdg)
EndFunction

Function ApplyStage(int n, string by)
    if n <= applied
        return
    endif
    applied = n
    Trace("stage " + n + " by=" + by)
    if n == 10
        SetObjectiveDisplayed(10)
        SetActive(True)
    elseif n == 15
        RunPodExitHook(Game.GetPlayer())
    elseif n == 20
        RunPodExitHook(Game.GetPlayer())
        TriggerVaultPodRecoveryAutosave(n)
    elseif n == 40
        ClearVaultSaveLock()
        SetObjectiveCompleted(10)
    elseif n == 200
        CompleteQuest()
        StartLandingQuests()
        ClearVaultSaveLock()
        ReleaseStoryLandingFade()
    elseif n == 210
        CompleteQuest()
        StartLandingQuests()
        ClearVaultSaveLock()
    endif
EndFunction

Function ClearVaultSaveLock()
    CancelTimer(6)
    CancelTimer(7)
    if vaultSavingRelocked
        vaultSavingRelocked = false
        Game.SetInChargen(false, false, false)
    endif
EndFunction

Function RelockVaultSaving(Actor p, int st)
    if !vaultSavingRelocked && st >= 10 && st < 200 && (GameModeGlobal == None || (GameModeGlobal.GetValue() as int) != 2) && p != None && StandsInVault(p)
        vaultSavingRelocked = true
        Game.SetInChargen(true, false, false)
        Trace("vault_death_recovery=save_locked stage=" + st)
    endif
EndFunction

Function AdvanceTo(int n, string by = "Trigger")
{SetStage, then the stage's actions with explicit B6 cause (OnStageSet never fired on the mission's quest, 18 Oct, so nothing relies on it).}
    string cause = by
    if n == 40 && exitUsedFallback
        cause = "fallback"
    endif
    pendingStage = n
    pendingStageBy = cause
    SetStage(n)
    ApplyStage(n, cause)
EndFunction

Event OnStageSet(int auiStageID, int auiItemID)
    if auiStageID == 20
        TriggerVaultPodRecoveryAutosave(20)
    endif
    if auiStageID == 20 && looksSetStage20
        return
    endif
    string cause = "other"
    if auiStageID == pendingStage
        cause = pendingStageBy
    endif
    ApplyStage(auiStageID, cause)
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID == 6
        RelockVaultSaving(Game.GetPlayer(), GetStage())
        return
    endif
    if aiTimerID == 7
        TriggerVaultPodRecoveryAutosave(GetStage())
        return
    endif
    if aiTimerID == 5
        if SinglePassLandingFade
            return
        endif
        Actor storyPlayer = Game.GetPlayer()
        if storyPlayer == None || storyPlayer.IsInInterior()
            return
        endif
        storyFadeTicks += 1
        if storyPlayer.Is3DLoaded()
            Game.ShowFirstPersonGeometry(true)
            Game.FadeOutGame(False, True, 0.0, 0.1, False)
            Game.SetInChargen(false, false, false)
            Game.SetCharGenHUDMode(0)
            Trace("story fade reassert tick=" + storyFadeTicks)
        endif
        if storyFadeTicks < 3
            StartTimer(2.5, 5)
        endif
        return
    endif
    if aiTimerID == 4
        warfareFadeTicks += 1
        Game.ShowFirstPersonGeometry(true)
        Game.FadeOutGame(False, True, 0.0, 0.1, False)
        Game.SetInChargen(false, false, false)
        Game.SetCharGenHUDMode(0)
        Trace("warfare fade reassert tick=" + warfareFadeTicks)
        if warfareFadeTicks < 2
            StartTimer(2.5, 4)
        endif
        return
    endif
    if aiTimerID == 2
        if modeBoxWaiting
            modeBoxWaitSeconds += 60
            Trace("mode box waiting s=" + modeBoxWaitSeconds)
            StartTimer(60.0, 2)
        endif
        return
    endif
    if aiTimerID != 1
        return
    endif
    Actor player = Game.GetPlayer()
    EnsureLoadHookRegistered(player)
    int stage = GetStage()
    if stage > applied && !(stage == 20 && looksSetStage20)
        string extCause = "other"
        if stage == pendingStage
            extCause = pendingStageBy
        endif
        ApplyStage(stage, extCause)
    endif
    ticks += 1
    if stage == 0
        ; Starfield's Utility.psc has no IsInMenuMode (PC precheck, 19 Oct): loaded 3D is the only wait
        if !player.Is3DLoaded()
            if ticks % 10 == 0
                ; a wait that does not end (a move or a centering that moved nobody) leaves this line, not silence
                Trace("waiting for the 3d tick=" + ticks + " vault_moves=" + vaultMoves + " centered=" + centered + " cell=" + player.GetParentCell())
            endif
            StartTimer(1.0, 1)                               ; the game is still loading
            return
        endif
        if UsePreworldRoom()
            PrepareStartRoomUi("timer")
            if !startRoomEntered
                if startRoomMoves > 0 && StandsInStartRoom(player)
                    startRoomEntered = true
                    Trace("enter start room confirmed after the load pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " cell=" + player.GetParentCell())
                else
                    startRoomEntered = EnterStartRoom(player)
                endif
            endif
            if !startRoomEntered
                StartTimer(1.0, 1)
                return
            endif
        else
            FadeIn("timer")                                  ; once: the start may still be in its 3D wait
            if !entered
                if vaultMoves > 0 && StandsInVault(player)
                    ; the start's move took once the load was through (the cell check right after a MoveTo during the first
                    ; load is unverified): no second move, which would be a second loading screen
                    entered = true
                    Trace("enter vault confirmed after the load pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " cell=" + player.GetParentCell())
                else
                    entered = EnterVault(player)             ; the temporary-anchor mode after its centering, or a missed move
                endif
            endif
            if !entered
                StartTimer(1.0, 1)                           ; retried each second
                return
            endif
        endif
        HoldOffPass(2)                                       ; once the game runs: a quest that started after the first pass
        int chosenMode = RunModeChoiceChain(player)
        if chosenMode == 2
            return
        elseif GetStage() < 10
            if ClearInventory
                ResetInventory(player)
                FillO2(player)
            endif
            AdvanceTo(10)
            startedAt = Utility.GetCurrentRealTime()
        endif
    elseif stage == 5
        if GameModeGlobal != None && (GameModeGlobal.GetValue() as int) == 1
            if !entered
                entered = EnterVault(player)
            endif
            if !entered
                StartTimer(1.0, 1)
                return
            endif
            if ClearInventory
                ResetInventory(player)
                FillO2(player)
            endif
            AdvanceTo(10)
            startedAt = Utility.GetCurrentRealTime()
        endif
    elseif stage == 10
        if !podChecked && player.Is3DLoaded()
            CheckPod(player)
        endif
        EnsureVaultInteractivesRegistered()
        if preworldLooksDone
            preworldLooksDone = false
            looksSetStage20 = true
            Trace("looks done: " + preworldLooksHow)
            AdvanceTo(20, preworldLooksBy)
            NoteLooksStage20()
        elseif Utility.GetCurrentRealTime() - startedAt > LooksWait
            if LooksWait > 0.0
                Trace("looks done: LooksWait fallback after " + LooksWait + " s")
                AdvanceTo(20, "fallback")
            else
                Trace("looks done: no-looks immediate start")
                AdvanceTo(20, "Trigger")
            endif
        endif
    elseif stage == 20 || stage == 30
        if !podChecked && player.Is3DLoaded() && StandsInVault(player)
            CheckPod(player)
        endif
        if rideActive
            PrepareArrivalMarkerDuringRide()
            CheckAscent(player)
        elseif surfaceMovedAt > 0.0
            FinishSurface(player)                            ; the ride's MoveTo is done: the arrival waits for this tick
            if GetStage() >= 40
                PreAttachArrivalMarker(player)
            endif
        else
            InVault(player, stage)
        endif
    elseif stage == 40
        CheckLanding(player)
    elseif stage == 200
        CheckReturnLift(player)
    endif
    if GetStage() < 200 && ticks % 5 == 0
        Trace("status stage=" + GetStage() + " pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " cell=" + player.GetParentCell() + " world=" + player.GetWorldSpace())
    endif
    int curStage = GetStage()
    if curStage < 200 && curStage != 1
        if rideActive || surfaceMovedAt > 0.0 || curStage == 40
            StartTimer(0.15, 1)
        else
            StartTimer(1.0, 1)
        endif
    elseif curStage == 200
        if returnSurfacePending
            StartTimer(1.0, 1)
        else
            StartTimer(5.0, 1)
        endif
    endif
EndEvent

bool Function IsNewGame(float days, int level)
{The new-game guard (make_newgame.py is_new_game is the same rule, tested there). Only the engine's New Game (and New
 Game+) should start the startup quest (supported hypothesis: the precedent's start, and MQ101's NG+ entry); a save the
 player made, or one that gains this plugin, should never start it, and a session started with coc from the main menu
 does not either (Install's map test, 28 Oct, found MQ101, the startup quest then, not running; supported hypothesis).
 So days and level are the whole guard: they keep out a New Game+ and a console start on a played save (a game day or
 more, or above level 1). A console start in a session under a day at level 1 (a coc session from the main menu: the
 map test read days=0.333532 level=1) passes it and runs the whole start, as a New Game does: the move into the vault,
 the hold-off, the write and the fade. The opening-stage test of newgame_v9 (21 Oct review on #393) has nothing left to
 judge: MQ101 never runs.}
    return days < MaxNewGameDays && level <= MaxNewGameLevel
EndFunction

Function HoldOffPass(int pass)
{Pass 1 runs in the start, right after the move; pass 2 once the vault has loaded, at least a tick later. With MQ101
 never started, pass 2 is for a quest that started meanwhile (MQ00 is start-game enabled) and, if something had started
 MQ101 and pass 1 stopped it, for what its stage 9000 starts: MQ101PostQuest and (unless the player has entered the
 Unity) MQ_TutorialQuest_Misc04 (PC read 19 Oct, NG-N1; Stop() does not wait for that). What each pass stopped is in the
 log (make_newgame.py log, held_off_by_pass).}
    int stopped = 0
    int i = 0
    while i < HoldOff.Length
        Quest q = HoldOff[i]
        if q != None && q.IsRunning()
            q.Stop()
            stopped += 1
            Trace("held off " + q + " running_after=" + q.IsRunning() + " pass=" + pass)
        else
            Trace("not running " + q + " pass=" + pass)
        endif
        i += 1
    endwhile
    Trace("hold-off pass " + pass + " stopped=" + stopped + " of " + HoldOff.Length)
EndFunction

bool Function EnterVault(Actor player)
{MoveTo the vault's anchor with the pod's offset (the verified MoveTo form of the mission and FO4SF_Probe), then the
 pod's heading. False when the anchor does not resolve or the player did not land in the anchor's cell; vaultMoves counts
 the MoveTo calls, so Begin can tell "moved, the cell not confirmed yet" from "nothing moved". The first call is Begin's,
 during the first load, as MQ101's own intro moves the player then; whether GetParentCell already names the vault right
 after it is unverified, so the timer confirms the cell once the 3D has loaded before it moves again. In the
 temporary-anchor mode an unresolved anchor means the cell is not loaded yet: CenterOnVault loads it and the retry one
 tick later resolves the marker; the MoveTo then applies the pod's offset even though the player already stands in the
 cell (on the COC marker), so the two modes end at the same spot.}
    ObjectReference anchor = Game.GetFormFromFile(VaultAnchorId, VaultPlugin) as ObjectReference
    if anchor == None
        if AnchorTemporary
            return CenterOnVault()
        endif
        Trace("vault anchor " + VaultPlugin + ":" + VaultAnchorId + " does not resolve")
        return false
    endif
    player.MoveTo(anchor, PodX - AnchorX, PodY - AnchorY, PodZ + PodLift - AnchorZ, False, False)
    vaultMoves += 1
    player.SetAngle(0.0, 0.0, PodHeading)
    bool ok = player.GetParentCell() == anchor.GetParentCell()
    Trace("enter vault ok=" + ok + " pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " target=" + PodX + " " + PodY + " " + (PodZ + PodLift) + " cell=" + player.GetParentCell())
    if ok && TestModeGlobal != None && TestModeGlobal.GetValue() != 0.0
        Debug.Notification("Vault 111")
    endif
    return ok
EndFunction

Function CheckPod(Actor player)
{Where the player stands the first tick they are loaded after the move into the pod: the "pod settle" line (PodRadius,
 PodDrop). In run 3 of 28 Oct that tick came after the game had already put the sunk player on the COC marker.}
    podChecked = true
    ; One set of sequential readings, not an atomic engine snapshot. Earlier lines read XYZ again after computing
    ; dx/dy/drop, so a moving actor could print coordinates that did not reproduce those deltas.
    float sampleStart = Utility.GetCurrentRealTime()
    float sampleX = player.GetPositionX()
    float sampleY = player.GetPositionY()
    float sampleZ = player.GetPositionZ()
    float targetZ = PodZ + PodLift
    float dx = sampleX - PodX
    float dy = sampleY - PodY
    float drop = targetZ - sampleZ
    bool ok = dx * dx + dy * dy <= PodRadius * PodRadius && drop <= PodDrop
    float sampledHeading = player.GetAngleZ()
    bool sampledLoaded = player.Is3DLoaded()
    Cell sampledCell = player.GetParentCell()
    WorldSpace sampledWorld = player.GetWorldSpace()
    float sampleEnd = Utility.GetCurrentRealTime()
    Trace("pod settle ok=" + ok + " pos=" + sampleX + " " + sampleY + " " + sampleZ + " dx=" + dx + " dy=" + dy + " drop=" + drop + " target=" + PodX + " " + PodY + " " + targetZ + " heading=" + sampledHeading + " loaded=" + sampledLoaded + " cell=" + sampledCell + " world=" + sampledWorld + " sample_start=" + sampleStart + " sample_end=" + sampleEnd)
EndFunction

bool Function StandsInVault(Actor player)
{True when the vault anchor resolves and the player stands in its cell.}
    ObjectReference anchor = Game.GetFormFromFile(VaultAnchorId, VaultPlugin) as ObjectReference
    return anchor != None && player.GetParentCell() == anchor.GetParentCell()
EndFunction

bool Function CenterOnVault()
{The temporary-anchor mode (AnchorTemporary): the COC marker resolves to None while the vault is unloaded, so the cell is
 loaded with Debug.CenterOnCell on VaultCell (CenterOnCell(string asCellname), FO4's signature and Starfield's: its
 Debug.psc in ContentResources.zip, read 29 Oct; whether it works in retail is unverified: the log line "centered on
 ..." and the "enter vault ok=" line after it are the proof) and false is returned, so the caller's 1 s retry resolves
 the now-loaded marker and does the MoveTo. Bounded once the player's 3D is in: the first call centers; after
 CenterTicks tries without the anchor resolving one more centering at most; past that a failure line every 10 tries,
 never a loop. The tries after the first are the timer's, which waits for the player's 3D before it tries, so a
 centering during the first load that moves nobody leaves the 3D out and none of this follows: the timer's "waiting
 for the 3d" line every 10 ticks is then the only trace. The guard has run before the first call (Begin's order), so
 a centering never re-judges it. Whether a centering during the first load ends that load in the vault, as a MoveTo
 does, is unverified: the installed port's anchor is persistent.}
    centerTries += 1
    if centered == 0 || (centered == 1 && centerTries > CenterTicks)
        centered += 1
        Debug.CenterOnCell(VaultCell)
        Trace("centered on " + VaultCell + " attempt=" + centered + " tick=" + centerTries + ": temporary anchor " + VaultPlugin + ":" + VaultAnchorId + " does not resolve before the cell loads")
    elseif centerTries > CenterTicks && centerTries % 10 == 0
        Trace("vault anchor " + VaultPlugin + ":" + VaultAnchorId + " does not resolve after " + centerTries + " ticks and " + centered + " centerings on " + VaultCell + ": the temporary-anchor start failed")
    endif
    return false
EndFunction

Function ResetInventory(Actor player)
{The starting inventory reset (NG-K8), once, when the player is confirmed in the vault: RemoveAllItems(None, false,
 false), written with FO4's arguments. Starfield's third parameter is abRespectTargetCapacity (ObjectReference.psc,
 ContentResources.zip, read 29 Oct), so whether quest items stay is unverified: the count before and after is logged
 (GetItemCount(None) counts every item in FO4; unverified in Starfield, so both numbers are logged). When
 SilentStarterStrip is true, Starfield starter armor/watch forms are unequipped and removed silently before
 RemoveAllItems so no removed HUD toast fires, then the vault suit, when the build names one, is added and equipped.}
    int before = player.GetItemCount(None)
    int stripped = 0
    if SilentStarterStrip
        bool useExplicit = StarterStripItems != None && StarterStripItems.Length > 0
        int[] fallbackIds = new int[12]
        int loopLen = 0
        if useExplicit
            loopLen = StarterStripItems.Length
        else
            fallbackIds[0] = 0x001E2B17
            fallbackIds[1] = 0x001E2B18
            fallbackIds[2] = 0x001E2B19
            fallbackIds[3] = 0x0001D1E7
            fallbackIds[4] = 0x0001D1D7
            fallbackIds[5] = 0x000D4893
            fallbackIds[6] = 0x00052792
            fallbackIds[7] = 0x0005278E
            fallbackIds[8] = 0x002EDF1F
            fallbackIds[9] = 0x00029C7A
            fallbackIds[10] = 0x00104631
            fallbackIds[11] = 0x00104632
            loopLen = fallbackIds.Length
        endif
        int si = 0
        while si < loopLen
            Form item = None
            if useExplicit
                item = StarterStripItems[si]
            else
                item = Game.GetFormFromFile(fallbackIds[si], "Starfield.esm")
            endif
            if item != None
                bool worn = player.IsEquipped(item)
                if worn
                    player.UnequipItem(item, false, true)
                endif
                int count = player.GetItemCount(item)
                if count > 0
                    player.RemoveItem(item, count, true)
                    stripped += count
                elseif worn
                    stripped += 1
                endif
            endif
            si += 1
        endwhile
    endif
    player.RemoveAllItems(None, false, false)
    int after = player.GetItemCount(None)
    Trace("inventory starter_strip silent=" + SilentStarterStrip + " stripped=" + stripped + " left=" + after)
    Trace("inventory cleared removed=" + (before - after) + " left=" + after)
    if VaultSuitId > 0
        Armor suit = Game.GetFormFromFile(VaultSuitId, VaultPlugin) as Armor
        if suit == None
            Trace("vault suit " + VaultPlugin + ":" + VaultSuitId + " does not resolve")
            return
        endif
        player.AddItem(suit, 1, true)
        player.EquipItem(suit, false, true)
        Trace("vault suit equipped " + suit + " worn=" + player.IsEquipped(suit))
    else
        Armor fallbackSuit = Game.GetFormFromFile(0x0001D1D7, "Starfield.esm") as Armor
        if fallbackSuit != None
            player.AddItem(fallbackSuit, 1, true)
            player.EquipItem(fallbackSuit, false, true)
            Trace("vault suit fallback equipped " + fallbackSuit + " worn=" + player.IsEquipped(fallbackSuit))
        endif
    endif
EndFunction

Function FillO2(Actor player)
{The O2/CO2 dial without a suit (S13 row 2b), once, right after the reset: ModValue (what console modav does) tops
 O2Capacity up to O2CapacityAmount, so a second call adds nothing. The value stays in the save. Starfield's hazards
 themselves are switched off by holding off SQ_ENV (the HoldOff list), not here.}
    if O2Capacity == None || O2CapacityAmount <= 0.0
        return
    endif
    float added = O2CapacityAmount - player.GetValue(O2Capacity)
    if added > 0.0
        player.ModValue(O2Capacity, added)
    else
        added = 0.0
    endif
    Trace("o2 capacity added=" + added + " value=" + player.GetValue(O2Capacity))
EndFunction

Function InVault(Actor player, int stage)
    if !player.IsInInterior()
        return
    endif
    EnsureVaultInteractivesRegistered()
    if stage == 20 && CogDoorId > 0 && TestModeGlobal != None && TestModeGlobal.GetValue() != 0.0
        ObjectReference cogDoor = Game.GetFormFromFile(CogDoorId, VaultPlugin) as ObjectReference
        if Near(player, ConsoleX, ConsoleY, ConsoleZ, ConsoleRadius)
            if cogDoor != None
                int before = cogDoor.GetOpenState()
                if before != 1 && before != 2
                    cogDoor.SetOpen(True)
                endif
                Trace("cog door open_state before=" + before + " after=" + cogDoor.GetOpenState())
            else
                Trace("cog door " + VaultPlugin + ":" + CogDoorId + " does not resolve")
            endif
            stage = 30
            AdvanceTo(30)
        elseif cogDoor != None
            int doorState = cogDoor.GetOpenState()
            if doorState == 1 || doorState == 2
                Trace("cog door opened directly open_state=" + doorState)
                stage = 30
                AdvanceTo(30, "other")
            endif
        endif
    endif
    if CogDoorId > 0 && stage < 30
        asked = false
        return
    endif
    bool onPlatform = Near(player, PlatformX, PlatformY, PlatformZ, PlatformRadius)
    if !onPlatform
        asked = false
        return
    endif
    if asked
        return
    endif
    PromptVaultExitLift(player)
EndFunction

int Function ShowPausedExitLiftMenu(Actor player)
{Opens paused FO4SF_LiftMenu (FO4SF_StartCardOpen 4.0->5.0->6.0/7.0/8.0) with 40-pt S.P.E.C.I.A.L. sync; returns 0=Ride, 2=Stay, or -1 to fall back.}
    if StartCardOpenGlobal == None || (TestModeGlobal != None && TestModeGlobal.GetValue() != 0.0)
        return -1
    endif
    int si = 0
    while si < 7
        GlobalVariable pGlob = Game.GetFormFromFile(0x000880 + si, "FO4SFCoreValues.esm") as GlobalVariable
        ActorValue sAv = Game.GetFormFromFile(0x000810 + si, "FO4SFCoreValues.esm") as ActorValue
        if pGlob != None && sAv != None && player != None
            float curVal = player.GetValue(sAv)
            if curVal >= 1.0 && curVal <= 10.0
                pGlob.SetValue(curVal)
            endif
        endif
        si += 1
    endwhile
    GlobalVariable reqGlob = Game.GetFormFromFile(0x000887, "FO4SFCoreValues.esm") as GlobalVariable
    if reqGlob != None
        if liftSpecConfirmed
            reqGlob.SetValue(1.0)
        else
            reqGlob.SetValue(0.0)
        endif
    endif
    StartCardOpenGlobal.SetValue(4.0)
    float ackWait = 0.0
    float gVal = StartCardOpenGlobal.GetValue()
    while gVal > 0.5 && gVal < 4.5 && ackWait < 2.0
        Utility.Wait(0.1)
        ackWait += 0.1
        gVal = StartCardOpenGlobal.GetValue()
    endwhile
    if gVal < 4.5
        StartCardOpenGlobal.SetValue(0.0)
        Trace("lift menu fallback reason=unavailable gval=" + gVal)
        return -1
    endif
    Trace("lift menu open=1")
    float menuWait = 0.0
    while gVal >= 3.5 && gVal < 5.5 && menuWait < 3600.0
        Utility.Wait(0.1)
        menuWait += 0.1
        gVal = StartCardOpenGlobal.GetValue()
    endwhile
    StartCardOpenGlobal.SetValue(0.0)
    if reqGlob != None && reqGlob.GetValue() >= 0.5
        int ai = 0
        while ai < 7
            GlobalVariable pGlob2 = Game.GetFormFromFile(0x000880 + ai, "FO4SFCoreValues.esm") as GlobalVariable
            ActorValue sAv2 = Game.GetFormFromFile(0x000810 + ai, "FO4SFCoreValues.esm") as ActorValue
            if pGlob2 != None && sAv2 != None && player != None
                float chosen = pGlob2.GetValue()
                if chosen >= 1.0 && chosen <= 10.0
                    player.SetValue(sAv2, chosen)
                endif
            endif
            ai += 1
        endwhile
        reqGlob.SetValue(0.0)
        liftSpecConfirmed = true
        Trace("lift menu special confirmed=1")
    endif
    if gVal >= 7.5
        Trace("lift menu action=change_appearance")
        if player != None
            RegisterForMenuOpenCloseEvent("ChargenMenu")
            setupWaitingCreator = true
            Game.ShowRaceMenu(player, 1)
            float waitedCreator = 0.0
            while setupWaitingCreator && waitedCreator < LooksWait
                Utility.Wait(0.5)
                waitedCreator += 0.5
            endwhile
            UnregisterForMenuOpenCloseEvent("ChargenMenu")
            setupWaitingCreator = false
        endif
        asked = false
        return 2
    elseif gVal >= 5.5 && gVal < 6.5
        liftSpecConfirmed = true
        Trace("lift menu action=ride")
        return 0
    endif
    Trace("lift menu action=stay gval=" + gVal)
    return 2
EndFunction

Function PromptVaultExitLift(Actor player)
{Shows paused FO4SF_LiftMenu (or falls back to ExitMessage) on the Vault 111 elevator platform.}
    if rideActive || rideTransferred
        return
    endif
    asked = true                                             ; asked once per visit to the platform
    Trace("lift platform waiting cage_door=open")
    int pausedBtn = ShowPausedExitLiftMenu(player)
    int button = pausedBtn
    if button < 0
        button = ExitMessage.Show()
    endif
    Trace("elevator prompt button=" + button)
    if button == 0
        if pausedBtn != 0 && !liftSpecConfirmed && (TestModeGlobal == None || TestModeGlobal.GetValue() == 0.0)
            Trace("elevator continue refused: special unconfirmed")
            if ExitNeedAttrMsg != None
                ExitNeedAttrMsg.Show()
            else
                Debug.Notification("Confirm S.P.E.C.I.A.L. before leaving Vault 111.")
            endif
            asked = false
            StartTimer(0.1, 1)
            return
        endif
        ReadH00SuspectsOnce()
        if LiftId > 0
            if exitFailures >= 3
                int fbBtn = 0
                if ExitFallbackMessage != None
                    fbBtn = ExitFallbackMessage.Show()
                endif
                Trace("elevator fallback prompt button=" + fbBtn + " failures=" + exitFailures)
                if fbBtn == 1
                    Trace("lift cage_door=closing")
                    StartAscent(player)
                else
                    FallbackExitToSurface(player)
                endif
            else
                Trace("lift cage_door=closing")
                StartAscent(player)
            endif
        else
            Trace("lift cage_door=closing")
            RunSharedMapSetup()
            Surface(player)
        endif
    elseif button == 1
        OpenLiftAttributeAllocation()
    else
        Trace("elevator stay")
    endif
EndFunction

Function StartAscent(Actor player)
{One play on the real placed lift. Position remains under the platform's moving collision until completion.}
    if rideActive || rideTransferred
        return
    endif
    ReadH00SuspectsOnce()
    ObjectReference lift = Game.GetFormFromFile(LiftId, VaultPlugin) as ObjectReference
    Form base = Game.GetFormFromFile(LiftBaseId, VaultPlugin)
    Cell vault = player.GetParentCell()
    if lift == None || base == None || vault == None
        FailExit("lift_unavailable")
        return
    endif
    if !player.Is3DLoaded() || !player.IsInInterior() || !StandsInVault(player) || !lift.Is3DLoaded() || lift.GetParentCell() != vault || lift.GetBaseObject() != base
        FailExit("lift_identity_or_cell")
        return
    endif
    if !Near(player, PlatformX, PlatformY, PlatformZ, PlatformRadius)
        return
    endif
    ridingLift = lift
    ridingCell = vault
    riderX = player.GetPositionX()
    riderY = player.GetPositionY()
    riderZ = player.GetPositionZ()
    rideDone = false
    rideFadeStarted = false
    ; Register before playback; the callback checks the exact source and age; a later tick checks the upper position.
    RegisterForAnimationEvent(lift, "Done")
    if !player.Is3DLoaded() || player.GetParentCell() != ridingCell || !Near(player, riderX, riderY, riderZ, PlatformRadius)
        FailExit("lift_rider_left_before_play")
        return
    endif
    rideStartedAt = Utility.GetCurrentRealTime()
    rideActive = true
    bool accepted = lift.PlayAnimation("Play01")
    Trace("ascent play accepted=" + accepted + " ref=" + lift + " from=" + riderZ + " rise=" + LiftRise + " seconds=" + LiftSeconds)
    if !accepted
        UnregisterForAnimationEvent(lift, "Done")
        ReturnPlayerToVaultPlatform(player)
        Utility.Wait(0.5)
        if !lift.Is3DLoaded()
            Utility.Wait(0.25)
        endif
        if lift.Is3DLoaded()
            lift.Reset()
            Utility.Wait(0.25)
        endif
        if !player.Is3DLoaded() || !player.IsInInterior() || player.GetParentCell() != ridingCell || !lift.Is3DLoaded() || !Near(player, PlatformX, PlatformY, PlatformZ, PlatformRadius)
            FailExit("lift_play_refused")
            return
        endif
        RegisterForAnimationEvent(lift, "Done")
        riderX = player.GetPositionX()
        riderY = player.GetPositionY()
        riderZ = player.GetPositionZ()
        rideStartedAt = Utility.GetCurrentRealTime()
        accepted = lift.PlayAnimation("Play01")
        Trace("ascent play retry accepted=" + accepted + " ref=" + lift + " from=" + riderZ)
        if !accepted
            FailExit("lift_play_refused")
            return
        endif
    endif
    RunSharedMapSetup()
EndFunction

Event OnAnimationEvent(ObjectReference akSource, string asEventName)
    if !rideActive || akSource != ridingLift || asEventName != "Done"
        return
    endif
    float elapsed = Utility.GetCurrentRealTime() - rideStartedAt
    ; Prior probe heard a stale Done at 0.068 s from an earlier clip as well as 9.794 s for up. A bare Done is not an end.
    ; LiftDoneMargin (0.25 s) covers the measured 0.073 s delta (9.794 s vs 9.8667 s); physical ascent remains mandatory.
    if elapsed >= LiftSeconds - LiftDoneMargin
        rideDone = true
        Trace("ascent done elapsed=" + elapsed + " ref=" + akSource)
    else
        Trace("ascent ignored early_or_unconfirmed_done elapsed=" + elapsed)
    endif
EndEvent

bool Function AtLiftTop(Actor player)
    if !player.Is3DLoaded() || !player.IsInInterior() || player.GetParentCell() != ridingCell
        return false
    endif
    float dx = player.GetPositionX() - riderX
    float dy = player.GetPositionY() - riderY
    float dz = player.GetPositionZ() - (riderZ + LiftRise)
    return dx * dx + dy * dy <= PlatformRadius * PlatformRadius && dz > -0.75 && dz < 0.75
EndFunction

Function CheckAscent(Actor player)
    if !rideActive || rideTransferred
        return
    endif
    float elapsed = Utility.GetCurrentRealTime() - rideStartedAt
    if elapsed > LiftSeconds + 30.0
        FailExit("lift_timeout")
        return
    endif
    if !player.Is3DLoaded() || ridingLift == None || !ridingLift.Is3DLoaded()
        return
    endif
    if !player.IsInInterior() || player.GetParentCell() != ridingCell || ridingLift.GetParentCell() != ridingCell
        FailExit("lift_cell_changed")
        return
    endif
    if !rideFadeStarted && elapsed >= LiftSeconds - 1.1
        rideFadeStarted = true
        Game.FadeOutGame(True, True, 0.0, 1.0, True)
        Trace("ascent fade_out elapsed=" + elapsed)
    endif
    if !rideDone || !AtLiftTop(player)
        return
    endif
    ; Set the latch before any yielding native. No second play or transition can race this one.
    rideTransferred = true
    rideActive = false
    UnregisterForAnimationEvent(ridingLift, "Done")
    Trace("ascent carried confirmed elapsed=" + elapsed + " z=" + player.GetPositionZ())
    if !AtLiftTop(player)
        FailExit("lift_rider_left_before_arrival")
        return
    endif
    Surface(player)
EndFunction

Function Surface(Actor player)
{The ride up, first half: MoveTo the core anchor, which puts the player at its LOCAL position. FinishSurface places
 them on the merged arrival on a later tick.}
    ReadH00SuspectsOnce()
    ObjectReference anchor = Game.GetFormFromFile(ExitAnchorId, CorePlugin) as ObjectReference
    if anchor == None
        Trace("exit anchor " + CorePlugin + ":" + ExitAnchorId + " does not resolve")
        if LiftId > 0
            FailExit("lift_exit_anchor_unavailable")
        endif
        return
    endif
    ApplyH00PreSurfaceOverrides()
    ClearVaultSaveLock()
    UnregisterStartLoadingHook()
    Game.SetInChargen(false, false, false)
    Game.SetCharGenHUDMode(0)
    surfaceSets = 0
    arrivalWorld = None
    fallbackPending = false
    discoveryMarkerMoved = false
    landingChecks = 0
    surfaceFadeInDone = false
    anchor.Enable(False)
    player.MoveTo(anchor, 0.0, 0.0, 0.0, True, False)
    surfaceMoves += 1
    surfaceMovedAt = Utility.GetCurrentRealTime()
    Trace("surface moveto pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " world=" + player.GetWorldSpace() + " moves=" + surfaceMoves)
EndFunction

Function FinishSurface(Actor player)
{The ride up, second half: SetPosition on the merged arrival, a tick after the MoveTo at the earliest and once the player
 is outside with their 3D loaded. Because persistent references in the overlay world retain their unmerged local XY while
 exterior grid cells are shifted by MergeOffset, the initial MoveTo lands in a procedural exterior cell of the live host
 worldspace resolved from ExitAnchorId / Sanctuary workbench; SetPosition shifts the player onto the merged core cell
 first, and the post-move parent cell must then carry the core plugin's load index. Exhaustion stops the exit with failure.}
    if player.IsInInterior()
        if Utility.GetCurrentRealTime() - surfaceMovedAt > SurfaceWait
            if surfaceMoves < 2
                Trace("surface still inside " + SurfaceWait + " s after the moveto: moving again")
                Surface(player)
            else
                ObjectReference fbAnchor = Game.GetFormFromFile(ExitAnchorId, CorePlugin) as ObjectReference
                TrySurfaceExteriorFallbacks(player, fbAnchor)
                if player.IsInInterior()
                    if LiftId > 0
                        FailExit("lift_surface_missed")
                        return
                    endif
                    Trace("surface missed: still inside after " + surfaceMoves + " moves; the elevator asks again")
                    surfaceMovedAt = 0.0
                    surfaceMoves = 0
                    asked = false
                endif
            endif
        endif
        return
    endif
    if !player.Is3DLoaded()
        return                                               ; outside, still loading: never a missed move
    endif
    WorldSpace w = player.GetWorldSpace()
    ObjectReference anchor = Game.GetFormFromFile(ExitAnchorId, CorePlugin) as ObjectReference
    if w == None || anchor == None
        FailExit("surface_world_or_cell_unavailable")
        return
    endif
    float x = ArrivalX + MergeOffsetX
    float y = ArrivalY + MergeOffsetY
    Trace("surface pre_setposition target=" + x + " " + y + " " + ArrivalZ + " cell=" + player.GetParentCell() + " world=" + w)
    if !h00SkipSetPos
        player.SetPosition(x, y, ArrivalZ)
        player.SetAngle(0.0, 0.0, ArrivalHeading)
        surfaceSets += 1
    endif
    WorldSpace afterWorld = player.GetWorldSpace()
    Cell afterCell = player.GetParentCell()
    ; Check core cell ownership AFTER SetPosition shifts from the unmerged persistent anchor into the merged core grid.
    bool coreCell = false
    if afterCell != None
        int cellMod = afterCell.GetFormID() / 16777216
        int anchorMod = anchor.GetFormID() / 16777216
        coreCell = cellMod == anchorMod
    endif
    float dx = player.GetPositionX() - x
    float dy = player.GetPositionY() - y
    float dz = player.GetPositionZ() - ArrivalZ
    bool ok = dx * dx + dy * dy <= 25.0 && dz > -FallDrop && dz < 3.0 && !player.IsInInterior() && afterWorld != None && coreCell
    if h00SkipSetPos
        Trace("h00 skipped surface setposition pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " cell=" + afterCell + " world=" + afterWorld)
        ok = afterWorld != None && !player.IsInInterior()
    else
        Trace("surface setposition ok=" + ok + " set=" + surfaceSets + " pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " target=" + x + " " + y + " " + ArrivalZ + " core_cell=" + coreCell + " cell=" + afterCell + " world=" + afterWorld)
    endif
    if ok
        arrivalWorld = afterWorld
        surfaceMovedAt = 0.0
        arrivedAt = Utility.GetCurrentRealTime()
        if SinglePassLandingFade && !surfaceFadeInDone
            surfaceFadeInDone = true
            ForceFadeIn("story_landing")
            Trace("ascent gap_closed=true fade_in_at_surface=true")
        endif
        AdvanceTo(40)
    elseif surfaceSets >= SurfaceTries
        if !coreCell
            FailExit("surface_cell_not_core")
        else
            FailExit("surface_position_not_confirmed")
        endif
    endif
EndFunction

Function CheckLanding(Actor player)
{Confirm landing once the player is in arrivalWorld with 3D loaded; fall rescue runs once, and marker discovery runs separately without blocking stage 200.}
    if Utility.GetCurrentRealTime() - arrivedAt < 0.25
        return
    endif
    if !player.Is3DLoaded()
        return
    endif
    if player.IsInInterior() || arrivalWorld == None || player.GetWorldSpace() != arrivalWorld
        FailExit("landing_world_changed")
        return
    endif
    landingChecks += 1
    float z = player.GetPositionZ()
    if !fallbackPending && z < ArrivalZ - FallDrop
        fallbackPending = true
        player.SetPosition(FallbackX + MergeOffsetX, FallbackY + MergeOffsetY, FallbackZ + 1.0)
        Trace("fell z=" + z + ": fallback pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ())
        return
    endif
    bool discovered = RequestArrivalDiscovery(player)
    if !discovered && discoveryAttachPending
        discoveryAttachPending = false
        return
    endif
    Trace("landed z=" + z + " confirmed=True fallback=" + fallbackPending + " world=" + arrivalWorld)
    AdvanceTo(200)
EndFunction

bool Function RequestArrivalDiscovery(Actor player)
    discoveryAttachPending = false
    if h00SkipDiscovery
        Trace("h00 skipped arrival discovery")
        return true
    endif
    if ArrivalDiscoveryId == 0
        Trace("arrival discovery disabled: custom exit anchor")
        return true
    endif
    ObjectReference marker = Game.GetFormFromFile(ArrivalDiscoveryId, CorePlugin) as ObjectReference
    if marker == None
        Trace("arrival discovery failed reason=marker_missing id=" + ArrivalDiscoveryId)
        return false
    endif
    float mx = FallbackX + MergeOffsetX
    float my = FallbackY + MergeOffsetY
    float mz = FallbackZ
    bool sameWorld = marker.GetWorldSpace() == arrivalWorld
    float dx = marker.GetPositionX() - mx
    float dy = marker.GetPositionY() - my
    float dz = marker.GetPositionZ() - mz
    bool atMerged = dx * dx + dy * dy <= 25.0 && dz >= -3.0 && dz <= 3.0
    if !sameWorld || !atMerged
        ; When the separate map-marker mover is not installed, attach the canonical Vault 111 marker once and confirm next tick.
        if !discoveryMarkerMoved && player.Is3DLoaded() && !player.IsInInterior() && player.GetWorldSpace() == arrivalWorld
            discoveryMarkerMoved = true
            discoveryAttachPending = true
            float px = player.GetPositionX()
            float py = player.GetPositionY()
            float pz = player.GetPositionZ()
            marker.Enable(False)
            marker.MoveTo(player, mx - px, my - py, mz - pz, False, False)
            if marker.GetWorldSpace() == arrivalWorld
                marker.SetPosition(mx, my, mz)
            endif
            Trace("arrival discovery marker moved ref=" + marker + " world=" + marker.GetWorldSpace() + " pos=" + marker.GetPositionX() + " " + marker.GetPositionY() + " " + marker.GetPositionZ() + " target=" + mx + " " + my + " " + mz)
        else
            Trace("arrival discovery failed reason=marker_not_attached ref=" + marker + " world=" + marker.GetWorldSpace() + " same_world=" + sameWorld + " at_merged=" + atMerged)
        endif
        return false
    endif
    ; Native reads yield between calls: recheck the player after reading the marker, immediately before mutation.
    bool enabledBefore = Game.IsFastTravelEnabled()
    if !player.Is3DLoaded() || player.IsInInterior() || player.GetWorldSpace() != arrivalWorld || marker.GetWorldSpace() != arrivalWorld
        Trace("arrival discovery failed reason=state_changed_before_discover ref=" + marker)
        return false
    endif
    if MuteArrivalDiscoveryPopup
        Trace("arrival discovery muted=true reason=per_game_flag ref=" + marker)
        return true
    endif
    marker.SetMarkerDiscovered()
    Trace("arrival discovery requested ref=" + marker + " world=" + marker.GetWorldSpace() + " fast_before=" + enabledBefore + " fast_after=" + Game.IsFastTravelEnabled())
    return true
EndFunction

bool Function AtArrival(Actor player)
    if fallbackPending
        return Near(player, FallbackX + MergeOffsetX, FallbackY + MergeOffsetY, FallbackZ + 1.0, 5.0)
    endif
    return Near(player, ArrivalX + MergeOffsetX, ArrivalY + MergeOffsetY, ArrivalZ, 5.0)
EndFunction

Function FailExit(string reason)
    exitFailures += 1
    if ridingLift != None
        UnregisterForAnimationEvent(ridingLift, "Done")
    endif
    rideActive = false
    rideDone = false
    rideTransferred = false
    if rideFadeStarted
        rideFadeStarted = false
        Game.FadeOutGame(False, True, 0.0, 0.5, False)
    endif
    ridingLift = None
    ridingCell = None
    surfaceMovedAt = 0.0
    surfaceMoves = 0
    surfaceSets = 0
    surfaceFadeInDone = false
    exitUsedFallback = false
    asked = false
    Actor player = Game.GetPlayer()
    if player != None && GetStage() < 40
        ReturnPlayerToVaultPlatform(player)
    else
        ResetVaultExitLift()
    endif
    Trace("exit retry n=" + exitFailures + " reason=" + reason + " stage=" + GetStage())
EndFunction

bool Function Near(Actor player, float x, float y, float z, float radius)
    float dx = player.GetPositionX() - x
    float dy = player.GetPositionY() - y
    float dz = player.GetPositionZ() - z
    return dx * dx + dy * dy <= radius * radius && dz < 3.0 && dz > -3.0
EndFunction

Function ReturnPlayerToVaultPlatform(Actor player)
{Returns the player onto the Vault 111 lift platform so InVault offers the lift prompt again.}
    if player == None
        return
    endif
    ResetVaultExitLift()
    if player.IsInInterior() && StandsInVault(player)
        player.SetPosition(PlatformX, PlatformY, PlatformZ + 0.2)
    else
        ObjectReference vAnchor = Game.GetFormFromFile(VaultAnchorId, VaultPlugin) as ObjectReference
        if vAnchor != None
            player.MoveTo(vAnchor, PlatformX - AnchorX, PlatformY - AnchorY, PlatformZ + 0.2 - AnchorZ, False, False)
        endif
    endif
EndFunction

Function ResetVaultExitLift()
{Resets and lowers the Vault 111 exit lift toggle graph back to its floor rest pose before retry.}
    if LiftId <= 0
        return
    endif
    ObjectReference lift = Game.GetFormFromFile(LiftId, VaultPlugin) as ObjectReference
    if lift != None && lift.Is3DLoaded()
        bool lowered = lift.PlayAnimation("Play02")
        if !lowered
            lift.Reset()
        endif
        Trace("lift reset ref=" + lift + " play02=" + lowered)
    endif
EndFunction

Function TryFastTravelSurface(Actor player, ObjectReference travelTarget)
    if travelTarget == None || !player.IsInInterior()
        return
    endif
    travelTarget.Enable(False)
    travelTarget.EnableFastTravel(True)
    Game.FastTravel(travelTarget)
    Utility.Wait(0.5)
    Trace("surface fallback last_resort fasttravel target=" + travelTarget + " interior=" + player.IsInInterior() + " world=" + player.GetWorldSpace())
EndFunction

Function TrySurfaceExteriorFallbacks(Actor player, ObjectReference primaryAnchor)
{After death reload from an interior save, instantiate the exterior world via core anchor 0x000800 or Game.FastTravel if MoveTo stayed inside.}
    if player == None || !player.IsInInterior()
        return
    endif
    Utility.Wait(0.25)
    if !player.IsInInterior()
        return
    endif
    ObjectReference coreAnchor = Game.GetFormFromFile(0x000800, CorePlugin) as ObjectReference
    if coreAnchor != None && coreAnchor != primaryAnchor
        coreAnchor.Enable(False)
        player.MoveTo(coreAnchor, 0.0, 0.0, 0.0, True, False)
        Utility.Wait(0.25)
        Trace("surface fallback anchor=" + coreAnchor + " interior=" + player.IsInInterior() + " world=" + player.GetWorldSpace())
    endif
    if !player.IsInInterior()
        return
    endif
    ObjectReference landMarker = Game.GetFormFromFile(0x0008F2, "FO4SFMapMarkers.esm") as ObjectReference
    TryFastTravelSurface(player, landMarker)
    if player.IsInInterior() && primaryAnchor != landMarker
        TryFastTravelSurface(player, primaryAnchor)
    endif
EndFunction

Function FallbackExitToSurface(Actor player)
{Offered after 3 lift failures: fades to black, logs exit fallback by=move, and moves directly to the surface arrival.}
    exitUsedFallback = true
    Game.FadeOutGame(True, True, 0.0, 0.2, False)
    Trace("exit fallback by=move")
    RunSharedMapSetup()
    Surface(player)
EndFunction

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_NEWGAME rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction

bool Function StartOptionalMissionQuest(int questId)
    Quest q = Game.GetFormFromFile(questId, "FO4SFMission.esm") as Quest
    if q == None
        return false
    endif
    if q.IsRunning()
        return true
    endif
    return q.StartNoWait()
EndFunction

Function StartLandingQuests()
{Stage 200 / 210 handoff: logs mission gate and starts Story quests via StartNoWait (or wakes them once in Warfare so they log mode=2 started=false and Stop).}
    if h00SkipQuests
        Trace("h00 skipped landing quests")
        return
    endif
    int gm = 1
    if GameModeGlobal != None && (GameModeGlobal.GetValue() as int) > 0
        gm = GameModeGlobal.GetValue() as int
    endif
    bool storyAllowed = gm != 2
    Trace("mission gate mode=" + gm + " started=" + storyAllowed)
    bool min00Ok = false
    Quest min00 = Game.GetFormFromFile(0x000800, "FO4SFMission.esm") as Quest
    if min00 != None
        if min00.IsRunning()
            min00Ok = storyAllowed
        else
            min00Ok = min00.StartNoWait() && storyAllowed
        endif
    endif
    bool keeperOk = false
    Quest keeper = Game.GetFormFromFile(0x000814, "FO4SFMission.esm") as Quest
    if keeper != None
        if keeper.IsRunning()
            keeperOk = storyAllowed
        else
            keeperOk = keeper.StartNoWait() && storyAllowed
        endif
    endif
    bool codsworth01Ok = StartOptionalMissionQuest(0x000816) && storyAllowed
    if storyAllowed
        Trace("landing quests started min00=" + min00Ok + " keeper=" + keeperOk + " codsworth01=" + codsworth01Ok)
    endif
EndFunction

Function EnsureLoadHookRegistered(Actor player)
    if player != None
        if !loadHookRegistered
            loadHookRegistered = true
            RegisterForRemoteEvent(player, "OnPlayerLoadGame")
        endif
        if !dyingHookRegistered
            dyingHookRegistered = true
            RegisterForRemoteEvent(player, "OnDying")
        endif
    endif
EndFunction

Function TriggerVaultPodRecoveryAutosave(int stageNum)
{Task 1b (#853 M1): Wait until player is 3D-loaded & standing in Vault 111 (retrying via Timer 7 up to 60 skips),
 autosave once after cryo pod / looks finishes, then Timer 6 re-locks saving inside Vault 111 (< 200).}
    if vaultPodAutosaved || stageNum < 10 || stageNum >= 200 || (GameModeGlobal != None && (GameModeGlobal.GetValue() as int) == 2)
        return
    endif
    Actor player = Game.GetPlayer()
    if player == None || player.IsDead()
        CancelTimer(7)
        return
    endif
    if !player.Is3DLoaded() || !StandsInVault(player)
        vaultPodAutosaveSkips += 1
        Trace("vault_death_recovery=autosave_skip skips=" + vaultPodAutosaveSkips + " stage=" + stageNum)
        if vaultPodAutosaveSkips < 60
            StartTimer(1.0, 7)
        endif
        return
    endif
    CancelTimer(7)
    EnsureLoadHookRegistered(player)
    vaultPodAutosaved = true
    vaultRecoveryTriggered = false
    vaultSavingRelocked = false
    Game.SetInChargen(false, false, false)
    Game.RequestAutoSave()
    Trace("vault_death_recovery=autosave stage=" + stageNum + " skips=" + vaultPodAutosaveSkips)
    StartTimer(1.5, 6)
EndFunction

WorldSpace Function ResolveHostWorld()
{Task 1i (#858 F7): Resolve live host exterior worldspace dynamically from persistent ExitAnchorId (0x0A775B, flags=0x400)
 FIRST, using Sanctuary workbench (0x005C50, flags=0x0) only as secondary fallback.}
    ObjectReference anchor = Game.GetFormFromFile(ExitAnchorId, CorePlugin) as ObjectReference
    if anchor != None
        WorldSpace aws = anchor.GetWorldSpace()
        if aws != None
            return aws
        endif
    endif
    ObjectReference benchRef = Game.GetFormFromFile(0x005C50, CorePlugin) as ObjectReference
    if benchRef != None
        WorldSpace bws = benchRef.GetWorldSpace()
        if bws != None
            return bws
        endif
    endif
    return None
EndFunction

Event Actor.OnDying(Actor akSender, ObjectReference akKiller)
    if akSender == None || akSender != Game.GetPlayer()
        return
    endif
    int st = GetStage()
    if st >= 200 || (GameModeGlobal != None && (GameModeGlobal.GetValue() as int) == 2) || vaultRecoveryTriggered
        return
    endif
    vaultRecoveryTriggered = true
    if vaultPodAutosaved
        Trace("vault_death_recovery=autosave stage=" + st)
        return
    endif
    ActorValue healthAv = Game.GetFormFromFile(0x0002D4, "Starfield.esm") as ActorValue
    if healthAv != None
        akSender.RestoreValue(healthAv, 9999.0)
    endif
    if akSender.IsInInterior() && StandsInVault(akSender)
        akSender.SetPosition(PodX, PodY, PodZ + PodLift)
        akSender.SetAngle(0.0, 0.0, PodHeading)
    else
        ObjectReference podAnchor = Game.GetFormFromFile(VaultAnchorId, VaultPlugin) as ObjectReference
        if podAnchor != None
            akSender.MoveTo(podAnchor, PodX - AnchorX, PodY - AnchorY, PodZ + PodLift - AnchorZ, False, False)
            akSender.SetAngle(0.0, 0.0, PodHeading)
        endif
    endif
    Trace("vault_death_recovery=pod_reset stage=" + st)
    if vaultPodAutosaveSkips >= 60
        vaultPodAutosaveSkips = 0
    endif
    StartTimer(1.0, 7)
EndEvent

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    vaultRecoveryTriggered = false
    EnsureLoadHookRegistered(akSender)
    SyncPipboyOwnedWornState(akSender)
    int st = GetStage()
    if GameModeGlobal != None && (GameModeGlobal.GetValue() as int) == 0 && st >= 10
        GameModeGlobal.SetValue(1.0)
        Trace("mode load default=story stage=" + GetStage())
    endif
    if st >= 10 && st < 40
        h00SuspectsRead = false
        bool wasMidExit = rideActive || rideTransferred || surfaceMovedAt > 0.0
        if ridingLift != None
            UnregisterForAnimationEvent(ridingLift, "Done")
        endif
        rideActive = false
        rideDone = false
        rideTransferred = false
        rideFadeStarted = false
        ridingLift = None
        ridingCell = None
        surfaceMovedAt = 0.0
        surfaceMoves = 0
        surfaceSets = 0
        surfaceFadeInDone = false
        exitUsedFallback = false
        asked = false
        if wasMidExit && akSender != None
            ReturnPlayerToVaultPlatform(akSender)
            Trace("exit reload recovered stage=" + st + " failures=" + exitFailures)
        endif
        if vaultPodAutosaved && !vaultSavingRelocked && akSender != None && StandsInVault(akSender)
            RelockVaultSaving(akSender, st)
        endif
    endif
    if st >= 200 && returnSurfacePending
        returnSurfacePending = false
        returnVaultAsked = false
        returnSurfaceWaitTicks = 0
        returnSurfaceTries = 0
        Trace("return lift reload recovered")
    endif
    if st != 1
        StartTimer(1.0, 1)
    endif
EndEvent

Function RegisterStartLoadingHook()
    if loadingHookRegistered || faded || modeChoiceRan
        return
    endif
    if ReadH00Glob(H00SkipLoadingHookGlobal, 0x000890)
        return
    endif
    loadingHookRegistered = true
    RegisterForMenuOpenCloseEvent("LoadingMenu")
EndFunction

Function UnregisterStartLoadingHook()
    if loadingHookRegistered
        loadingHookRegistered = false
        UnregisterForMenuOpenCloseEvent("LoadingMenu")
    endif
EndFunction

bool Function ReadH00Glob(GlobalVariable propGlob, int fallbackCoreId)
    GlobalVariable g = propGlob
    if g == None
        g = Game.GetFormFromFile(fallbackCoreId, "FO4SFCoreValues.esm") as GlobalVariable
    endif
    return g != None && g.GetValue() >= 0.5
EndFunction

int Function BoolBit(bool flag)
    if flag
        return 1
    endif
    return 0
EndFunction

Function ReadH00SuspectsOnce()
    if h00SuspectsRead
        return
    endif
    h00SuspectsRead = true
    h00SkipLoading = ReadH00Glob(H00SkipLoadingHookGlobal, 0x000890)
    h00ClearChargen = ReadH00Glob(H00ClearChargenGlobal, 0x000891)
    h00SkipDiscovery = ReadH00Glob(H00SkipArrivalDiscoveryGlobal, 0x000892)
    h00SkipMap = ReadH00Glob(H00SkipMapSetupGlobal, 0x000893)
    h00SkipLoot = ReadH00Glob(H00SkipRouteLootGlobal, 0x000894)
    h00SkipActors = ReadH00Glob(H00SkipMissionActorsGlobal, 0x000895)
    h00SkipQuests = ReadH00Glob(H00SkipLandingQuestsGlobal, 0x000896)
    h00SkipSetPos = ReadH00Glob(H00SkipSurfaceSetPosGlobal, 0x000897)
    Trace("h00 suspect FO4SF_H00_SkipLoadingHook=" + BoolBit(h00SkipLoading))
    Trace("h00 suspect FO4SF_H00_ClearChargenBeforeSurface=" + BoolBit(h00ClearChargen))
    Trace("h00 suspect FO4SF_H00_SkipArrivalDiscovery=" + BoolBit(h00SkipDiscovery))
    Trace("h00 suspect FO4SF_H00_SkipMapSetup=" + BoolBit(h00SkipMap))
    Trace("h00 suspect FO4SF_H00_SkipRouteLoot=" + BoolBit(h00SkipLoot))
    Trace("h00 suspect FO4SF_H00_SkipMissionActors=" + BoolBit(h00SkipActors))
    Trace("h00 suspect FO4SF_H00_SkipLandingQuests=" + BoolBit(h00SkipQuests))
    Trace("h00 suspect FO4SF_H00_SkipSurfaceSetPos=" + BoolBit(h00SkipSetPos))
EndFunction

Function ApplyH00PreSurfaceOverrides()
    if h00SkipLoading
        UnregisterStartLoadingHook()
    endif
    if h00ClearChargen
        UnregisterStartLoadingHook()
        Game.FadeOutGame(False, True, 0.0, 0.1, False)
        Game.SetInChargen(false, false, false)
        Game.SetCharGenHUDMode(0)
        Trace("h00 cleared chargen and fade before surface")
    endif
    if h00SkipActors
        int disabledActors = 0
        ObjectReference cods = Game.GetFormFromFile(0x000811, "FO4SFMission.esm") as ObjectReference
        if cods != None
            cods.DisableNoWait(False)
            disabledActors += 1
        endif
        ObjectReference preston = Game.GetFormFromFile(0x000802, "FO4SFMission.esm") as ObjectReference
        if preston != None
            preston.DisableNoWait(False)
            disabledActors += 1
        endif
        int rOff = 0
        while rOff < 8
            int raiderId = 0x000803 + rOff
            ObjectReference raider = Game.GetFormFromFile(raiderId, "FO4SFMission.esm") as ObjectReference
            if raider != None
                raider.DisableNoWait(False)
                disabledActors += 1
            endif
            rOff += 1
        endwhile
        Trace("h00 disabled mission exterior actors count=" + disabledActors)
    endif
    if h00SkipLoot
        int disabledLoot = 0
        int li = 0
        while RouteLootRefIds != None && li < RouteLootRefIds.Length
            ObjectReference rlRef = Game.GetFormFromFile(RouteLootRefIds[li], CorePlugin) as ObjectReference
            if rlRef != None
                rlRef.DisableNoWait(False)
                disabledLoot += 1
            endif
            li += 1
        endwhile
        Trace("h00 disabled route loot refs count=" + disabledLoot)
    endif
EndFunction

string Function BackdropName()
    if StartChoiceBackdrop == 3
        return "setup_menu"
    elseif StartChoiceBackdrop == 2
        return "title_card"
    elseif StartChoiceBackdrop == 0
        return "none"
    endif
    return "empty_cell"
EndFunction

bool Function UsePreworldRoom()
    if !FadeHold || StartChoiceBackdrop <= 0 || StartRoomMarkerRef == None
        return false
    endif
    if StartChoiceDoneGlobal != None && StartChoiceDoneGlobal.GetValue() >= 0.5
        return false
    endif
    return true
EndFunction

bool Function StandsInStartRoom(Actor player)
    return StartRoomMarkerRef != None && player != None && player.GetParentCell() == StartRoomMarkerRef.GetParentCell()
EndFunction

bool Function EnterStartRoom(Actor player)
{Moves the player into our owned empty interior cell FO4SF_StartRoomCell (0x00081C) during New Game setup so nothing of choosing happens in Vault 111 or any game location.}
    if StartRoomMarkerRef == None || player == None
        return false
    endif
    player.MoveTo(StartRoomMarkerRef, 0.0, 0.0, 0.0, False, False)
    startRoomMoves += 1
    player.SetAngle(0.0, 0.0, 0.0)
    bool ok = player.GetParentCell() == StartRoomMarkerRef.GetParentCell()
    Trace("enter start room ok=" + ok + " pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " cell=" + player.GetParentCell())
    return ok
EndFunction

Function PrepareStartRoomUi(string by)
{Lifts main-menu fade immediately in FO4SF_StartRoomCell so LoadingMenu completes its close handoff and every prompt is visible, while hiding player body and Starfield HUD.}
    if startRoomUiPrepared
        return
    endif
    startRoomUiPrepared = true
    Actor player = Game.GetPlayer()
    Game.ShowFirstPersonGeometry(false)
    Game.FadeOutGame(False, True, 0.0, 0.1, False)
    Game.SetInChargen(false, false, false)
    Game.SetCharGenHUDMode(2)
    DisableHandScanner()
    Trace("start room ready by=" + by + " loaded=" + player.Is3DLoaded() + " cell=" + player.GetParentCell() + " backdrop=" + BackdropName())
EndFunction

Function SetStartCardBackdrop(bool showCard)
    if StartChoiceBackdrop != 2 || StartCardOpenGlobal == None
        return
    endif
    if showCard
        StartCardOpenGlobal.SetValue(1.0)
        Utility.Wait(0.1)
    else
        StartCardOpenGlobal.SetValue(0.0)
    endif
EndFunction

Function WaitForStartUiReady()
{H0 / N2 / T3: never show a prompt while LoadingMenu is open or under a fade; waits for LoadingMenu close plus non-menu settle delay and logs which path released it.}
    Game.FadeOutGame(False, True, 0.0, 0.1, False)
    Game.SetInChargen(false, false, false)
    float waitedLoad = 0.0
    bool wasLoading = loadingMenuOpen
    while loadingMenuOpen && !loadingMenuClosedSeen && waitedLoad < StartLoadTimeout
        Utility.Wait(0.25)
        waitedLoad += 0.25
    endwhile
    string how = "already_loaded_delay"
    if loadingMenuOpen && !loadingMenuClosedSeen
        loadingMenuOpen = false
        how = "timeout_delay"
        Trace("mode fade lifted by=timeout s=" + (StartLoadTimeout as int))
    elseif loadingMenuClosedSeen || wasLoading
        how = "loading_menu_close_delay"
    endif
    UnregisterStartLoadingHook()
    Utility.Wait(0.75)
    Game.FadeOutGame(False, True, 0.0, 0.1, False)
    Game.SetInChargen(false, false, false)
    startUiReady = true
    Trace("start ui ready released_by=" + how + " waited_s=" + waitedLoad)
EndFunction

bool Function HoldNeutralSpotForModeChoice(Actor player)
    if StartNeutralSpotGlobal == None || StartNeutralSpotGlobal.GetValue() < 0.5 || player == None
        return false
    endif
    if StartRoomMarkerRef != None
        if !StandsInStartRoom(player)
            EnterStartRoom(player)
        endif
    else
        ObjectReference vAnchor = Game.GetFormFromFile(VaultAnchorId, VaultPlugin) as ObjectReference
        if vAnchor != None
            player.MoveTo(vAnchor, 0.0, 0.0, 0.0, False, False)
        else
            player.SetPosition(AnchorX, AnchorY, AnchorZ)
        endif
    endif
    Trace("mode neutral spot active pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ())
    return true
EndFunction

int Function FindStoryStartPlaceRow(string storyId)
    int idx = 0
    while StartPlaceIds != None && idx < StartPlaceIds.Length
        if StartPlaceModes[idx] == 1 && StartPlaceStories[idx] == storyId
            return idx
        endif
        idx += 1
    endwhile
    return 0
EndFunction

int Function FindWarfareStartPlaceRow(int wfRowIdx, string wfKey)
    int idx = 0
    while StartPlaceIds != None && idx < StartPlaceIds.Length
        if StartPlaceModes[idx] == 2 && (StartPlaceWarfareRows[idx] == wfRowIdx || StartPlaceIds[idx] == wfKey)
            return idx
        endif
        idx += 1
    endwhile
    return 0
EndFunction

Function RunPreworldLooksChoice(Actor player, bool isWarfare)
    SetStartCardBackdrop(false)
    if LooksWait <= 0.0
        preworldLooksDone = true
        preworldLooksHow = "no-looks immediate start"
        preworldLooksBy = "Trigger"
        return
    endif
    int cBtn = 1
    if StartPickMsg != None
        cBtn = StartPickMsg.Show()
        Trace("start choice button=" + cBtn)
    elseif !isWarfare
        preworldLooksDone = true
        preworldLooksHow = "quick start"
        preworldLooksBy = "Trigger"
        return
    endif
    if cBtn == 0
        Trace("quick start: preset kept, creator skipped")
        preworldLooksDone = true
        preworldLooksHow = "quick start"
        preworldLooksBy = "Trigger"
        return
    endif
    Game.ShowFirstPersonGeometry(true)
    RegisterForMenuOpenCloseEvent("ChargenMenu")
    setupWaitingCreator = true
    if isWarfare
        warfareWaitingCreator = true
        Trace("warfare creator open mode=" + RaceMenuMode)
    else
        Trace("looks menu mode=" + RaceMenuMode)
    endif
    Game.ShowRaceMenu(None, RaceMenuMode)
    float waitedCreator = 0.0
    while (setupWaitingCreator || warfareWaitingCreator) && waitedCreator < LooksWait
        Utility.Wait(0.5)
        waitedCreator += 0.5
    endwhile
    UnregisterForMenuOpenCloseEvent("ChargenMenu")
    bool timedOut = setupWaitingCreator || warfareWaitingCreator
    setupWaitingCreator = false
    warfareWaitingCreator = false
    Utility.Wait(2.0)
    Game.SetInChargen(false, false, false)
    preworldLooksDone = true
    if timedOut
        preworldLooksHow = "LooksWait fallback after " + LooksWait + " s"
        preworldLooksBy = "fallback"
    else
        preworldLooksHow = "creator closed"
        preworldLooksBy = "scene"
    endif
EndFunction

Function SpawnAtStoryStartPlace(Actor player, int placeRow)
    string placeId = "fo4_vault111"
    if StartPlaceIds != None && placeRow >= 0 && placeRow < StartPlaceIds.Length
        placeId = StartPlaceIds[placeRow]
    endif
    bool movedOk = entered && StandsInVault(player)
    if !movedOk
        if placeId == "fo4_vault111" || StartPlacePlugins == None || placeRow < 0 || placeRow >= StartPlacePlugins.Length
            int vTry = 0
            while !movedOk && vTry < 3
                vTry += 1
                movedOk = EnterVault(player)
                if !movedOk
                    Utility.Wait(0.25)
                    movedOk = StandsInVault(player)
                endif
            endwhile
        else
            ObjectReference rowMarker = Game.GetFormFromFile(StartPlaceMarkerIds[placeRow], StartPlacePlugins[placeRow]) as ObjectReference
            int rTry = 0
            while rowMarker != None && !movedOk && rTry < 3
                rTry += 1
                player.MoveTo(rowMarker, 0.0, 0.0, 0.0, True, False)
                Utility.Wait(0.25)
                movedOk = player.GetParentCell() == rowMarker.GetParentCell()
            endwhile
            if !movedOk
                Trace("start place move failed place=" + placeId + " fallback=fo4_vault111")
                movedOk = EnterVault(player)
            endif
        endif
    endif
    float w3d = 0.0
    while !player.Is3DLoaded() && w3d < StartLoadTimeout
        Utility.Wait(0.25)
        w3d += 0.25
    endwhile
    entered = movedOk || StandsInVault(player)
    FadeIn("mode_story")
    if startRoomMoves > 0 || preworldLooksDone
        if ClearInventory
            ResetInventory(player)
            FillO2(player)
        endif
        AdvanceTo(10)
        startedAt = Utility.GetCurrentRealTime()
        if preworldLooksDone
            preworldLooksDone = false
            looksSetStage20 = true
            Trace("looks done: " + preworldLooksHow)
            AdvanceTo(20, preworldLooksBy)
            NoteLooksStage20()
        endif
    endif
EndFunction

int Function RunModeChoiceChain(Actor player)
    if modeChoiceRan
        if GameModeGlobal != None && (GameModeGlobal.GetValue() as int) == 2
            return 2
        endif
        return 1
    endif
    if StartChoiceDoneGlobal != None && StartChoiceDoneGlobal.GetValue() >= 0.5
        modeChoiceRan = true
        if GameModeGlobal != None && (GameModeGlobal.GetValue() as int) == 2
            return 2
        endif
        return 1
    endif
    if !FadeHold
        modeChoiceRan = true
        int directRow = FindStoryStartPlaceRow("fo4_commonwealth")
        string directPlace = "fo4_vault111"
        if StartPlaceIds != None && directRow >= 0 && directRow < StartPlaceIds.Length
            directPlace = StartPlaceIds[directRow]
        endif
        if GameModeGlobal != None
            GameModeGlobal.SetValue(1.0)
        endif
        if StoryLineGlobal != None
            StoryLineGlobal.SetValue(0.0)
        endif
        if SurvivalStartGlobal != None
            SurvivalStartGlobal.SetValue(0.0)
        endif
        if SurvivalLockedGlobal != None
            SurvivalLockedGlobal.SetValue(0.0)
        endif
        if StartDifficultyGlobal != None
            StartDifficultyGlobal.SetValue(1.0)
        endif
        if WarfareFactionGlobal != None
            WarfareFactionGlobal.SetValue(-1.0)
        endif
        if WarfareStartIndexGlobal != None
            WarfareStartIndexGlobal.SetValue(-1.0)
        endif
        if StartPlaceRowGlobal != None
            StartPlaceRowGlobal.SetValue(directRow as float)
        endif
        if StartChoiceDoneGlobal != None
            StartChoiceDoneGlobal.SetValue(1.0)
        endif
        Form directHcForm = Game.GetFormFromFile(0x000830, "FO4SFHardcore.esm")
        if directHcForm != None
            ScriptObject directHc = directHcForm.CastAs("FO4SF_HardcoreQuest")
            if directHc != None
                Var[] directHcArgs = new Var[1]
                directHcArgs[0] = "start_choice"
                directHc.CallFunction("EvaluateHardcore", directHcArgs)
            endif
        endif
        Trace("mode choice mode=story survival=0")
        Trace("start record mode=story story=fo4_commonwealth faction=-1 place=" + directPlace + " survival=0 difficulty=1 backdrop=none")
        return 1
    endif
    modeChoiceRan = true
    bool usedNeutralSpot = HoldNeutralSpotForModeChoice(player)
    WaitForStartUiReady()
    string effectiveBackdrop = BackdropName()
    bool usedSetupMenu = false
    int modeVal = 1
    int storyBtn = 0
    int survVal = 0
    int diff = 1
    int pickedSlot = -1
    int rowIdx = -1
    int placeRow = 0
    if StartChoiceBackdrop == 3 && StartCardOpenGlobal != None && StartChoiceDoneGlobal != None
        StartCardOpenGlobal.SetValue(2.0)
        float ackWait = 0.0
        while StartCardOpenGlobal.GetValue() < 2.5 && StartChoiceDoneGlobal.GetValue() < 0.5 && ackWait < 2.0
            Utility.Wait(0.25)
            ackWait += 0.25
        endwhile
        if StartCardOpenGlobal.GetValue() >= 2.5 || StartChoiceDoneGlobal.GetValue() >= 0.5
            usedSetupMenu = true
            if StartChoiceDoneGlobal.GetValue() < 0.5
                modeBoxWaiting = true
                modeBoxWaitSeconds = 0
                StartTimer(60.0, 2)
                while StartChoiceDoneGlobal.GetValue() < 0.5
                    Utility.Wait(0.25)
                endwhile
                modeBoxWaiting = false
            endif
            StartCardOpenGlobal.SetValue(0.0)
            if GameModeGlobal != None && (GameModeGlobal.GetValue() as int) == 2
                modeVal = 2
            endif
            if StoryLineGlobal != None
                storyBtn = StoryLineGlobal.GetValue() as int
            endif
            if SurvivalStartGlobal != None && SurvivalStartGlobal.GetValue() >= 0.5
                survVal = 1
            endif
            if SurvivalLockedGlobal != None
                SurvivalLockedGlobal.SetValue(survVal as float)
            endif
            if StartDifficultyGlobal != None
                diff = StartDifficultyGlobal.GetValue() as int
            endif
            if WarfareFactionGlobal != None
                pickedSlot = WarfareFactionGlobal.GetValue() as int
            endif
            if WarfareStartIndexGlobal != None
                rowIdx = WarfareStartIndexGlobal.GetValue() as int
            endif
            if StartPlaceRowGlobal != None
                placeRow = StartPlaceRowGlobal.GetValue() as int
            endif
            if modeVal == 2 && StartPlaceWarfareRows != None && placeRow >= 0 && placeRow < StartPlaceWarfareRows.Length
                int mappedWfRow = StartPlaceWarfareRows[placeRow]
                if mappedWfRow >= 0 && (WarfareKeys == None || mappedWfRow < WarfareKeys.Length)
                    rowIdx = mappedWfRow
                    if WarfareStartIndexGlobal != None
                        WarfareStartIndexGlobal.SetValue(rowIdx as float)
                    endif
                endif
            endif
        else
            StartCardOpenGlobal.SetValue(0.0)
            effectiveBackdrop = "empty_cell"
            Trace("setup menu unavailable: falling back to empty_cell boxes")
        endif
    endif
    if !usedSetupMenu
        SetStartCardBackdrop(true)
        int mBtn = 0
        if ModePickMsg != None
            modeBoxWaiting = true
            modeBoxWaitSeconds = 0
            StartTimer(60.0, 2)
            mBtn = ModePickMsg.Show()
            modeBoxWaiting = false
        endif
        if mBtn == 1
            modeVal = 2
        endif
        if modeVal == 1
            if StoryLineMsg != None
                storyBtn = StoryLineMsg.Show()
            endif
            string boxStoryId = "fo4_commonwealth"
            if StoryChoiceIds != None && StoryChoiceIds.Length > 0
                if storyBtn < 0 || storyBtn >= StoryChoiceIds.Length
                    storyBtn = 0
                endif
                boxStoryId = StoryChoiceIds[storyBtn]
            else
                storyBtn = 0
            endif
            placeRow = FindStoryStartPlaceRow(boxStoryId)
        else
            storyBtn = -1
            if WarfareDiffMsg != None
                diff = WarfareDiffMsg.Show()
                if diff < 0 || diff > 3
                    diff = 1
                endif
            endif
            int gBtn = 0
            if WarfareGroupMsg != None
                gBtn = WarfareGroupMsg.Show()
                if gBtn < 0 || gBtn >= WarfareDistinctFactionSlots.Length
                    gBtn = 0
                endif
            endif
            pickedSlot = 0
            if WarfareDistinctFactionSlots != None && WarfareDistinctFactionSlots.Length > 0
                pickedSlot = WarfareDistinctFactionSlots[gBtn]
            endif
            int sIdxBtn = 0
            if WarfareSpotMsg != None && WarfareKeys != None && WarfareKeys.Length > 1
                sIdxBtn = WarfareSpotMsg.Show()
                if sIdxBtn < 0 || sIdxBtn >= WarfareKeys.Length
                    sIdxBtn = 0
                endif
            endif
            int r = 0
            while WarfareKeys != None && r < WarfareKeys.Length
                if WarfareFactionSlots[r] == pickedSlot && diff >= WarfareMinDiffs[r] && diff <= WarfareMaxDiffs[r]
                    if rowIdx < 0 || r == sIdxBtn
                        rowIdx = r
                    endif
                endif
                r += 1
            endwhile
            if rowIdx < 0
                rowIdx = 0
            endif
            string wfPlaceKey = "minutemen_sanctuary"
            if WarfareKeys != None && rowIdx < WarfareKeys.Length
                wfPlaceKey = WarfareKeys[rowIdx]
            endif
            placeRow = FindWarfareStartPlaceRow(rowIdx, wfPlaceKey)
        endif
        int sBtn = 0
        if SurvivalPickMsg != None
            sBtn = SurvivalPickMsg.Show()
        endif
        if sBtn == 1
            survVal = 1
        endif
        SetStartCardBackdrop(false)
        if GameModeGlobal != None
            GameModeGlobal.SetValue(modeVal as float)
        endif
        if StoryLineGlobal != None
            StoryLineGlobal.SetValue(storyBtn as float)
        endif
        if SurvivalStartGlobal != None
            SurvivalStartGlobal.SetValue(survVal as float)
        endif
        if SurvivalLockedGlobal != None
            SurvivalLockedGlobal.SetValue(survVal as float)
        endif
        if StartDifficultyGlobal != None
            StartDifficultyGlobal.SetValue(diff as float)
        endif
        if WarfareFactionGlobal != None
            WarfareFactionGlobal.SetValue(pickedSlot as float)
        endif
        if WarfareStartIndexGlobal != None
            WarfareStartIndexGlobal.SetValue(rowIdx as float)
        endif
        if StartPlaceRowGlobal != None
            StartPlaceRowGlobal.SetValue(placeRow as float)
        endif
        if StartChoiceDoneGlobal != None
            StartChoiceDoneGlobal.SetValue(1.0)
        endif
    endif
    if diff < 0 || diff > 3
        diff = 1
    endif
    string modeTag = "story"
    string storyId = "fo4_commonwealth"
    string placeId = "fo4_vault111"
    if modeVal == 1
        pickedSlot = -1
        rowIdx = -1
        if StoryChoiceIds != None && StoryChoiceIds.Length > 0
            if storyBtn < 0 || storyBtn >= StoryChoiceIds.Length
                storyBtn = 0
            endif
            storyId = StoryChoiceIds[storyBtn]
        else
            storyBtn = 0
        endif
        if StartPlaceIds == None || placeRow < 0 || placeRow >= StartPlaceIds.Length || StartPlaceModes[placeRow] != 1
            placeRow = FindStoryStartPlaceRow(storyId)
        endif
        if StartPlaceIds != None && placeRow >= 0 && placeRow < StartPlaceIds.Length
            placeId = StartPlaceIds[placeRow]
        endif
    else
        modeTag = "warfare"
        storyBtn = -1
        storyId = "none"
        if WarfareKeys != None && (rowIdx < 0 || rowIdx >= WarfareKeys.Length)
            rowIdx = 0
        elseif rowIdx < 0
            rowIdx = 0
        endif
        if pickedSlot < 0
            if WarfareFactionSlots != None && rowIdx >= 0 && rowIdx < WarfareFactionSlots.Length
                pickedSlot = WarfareFactionSlots[rowIdx]
            else
                pickedSlot = 0
            endif
        endif
        placeId = "minutemen_sanctuary"
        if WarfareKeys != None && rowIdx >= 0 && rowIdx < WarfareKeys.Length
            placeId = WarfareKeys[rowIdx]
        endif
        if StartPlaceIds == None || placeRow < 0 || placeRow >= StartPlaceIds.Length || StartPlaceModes[placeRow] != 2
            placeRow = FindWarfareStartPlaceRow(rowIdx, placeId)
        endif
        if StartPlaceIds != None && placeRow >= 0 && placeRow < StartPlaceIds.Length
            placeId = StartPlaceIds[placeRow]
        endif
    endif
    Form hcForm = Game.GetFormFromFile(0x000830, "FO4SFHardcore.esm")
    if hcForm != None
        ScriptObject hc = hcForm.CastAs("FO4SF_HardcoreQuest")
        if hc != None
            Var[] hcArgs = new Var[1]
            hcArgs[0] = "start_choice"
            hc.CallFunction("EvaluateHardcore", hcArgs)
        endif
    endif
    Trace("mode choice mode=" + modeTag + " survival=" + survVal)
    if modeVal == 2
        Trace("warfare pick faction=" + pickedSlot + " start=" + placeId + " difficulty=" + diff)
    endif
    Trace("start record mode=" + modeTag + " story=" + storyId + " faction=" + pickedSlot + " place=" + placeId + " survival=" + survVal + " difficulty=" + diff + " backdrop=" + effectiveBackdrop)
    AdvanceTo(5)
    if modeVal == 1
        if startRoomMoves > 0 || usedNeutralSpot
            RunPreworldLooksChoice(player, false)
        endif
        SpawnAtStoryStartPlace(player, placeRow)
        return 1
    endif
    RunWarfareBranch(player, rowIdx)
    return 2
EndFunction

Function ForceFadeIn(string by)
{T5: Always re-asserts fade-in, saving, first-person geometry, and HUD even if faded was already true.}
    faded = true
    UnregisterStartLoadingHook()
    Actor player = Game.GetPlayer()
    Game.ShowFirstPersonGeometry(true)
    Game.FadeOutGame(False, True, 0.0, 0.1, False)
    Game.SetInChargen(false, false, false)
    Game.SetCharGenHUDMode(0)
    DisableHandScanner()
    Trace("fade in by=" + by + " loaded=" + player.Is3DLoaded() + " cell=" + player.GetParentCell() + "; saving and HUD on")
EndFunction

Function ReleaseStoryLandingFade()
{V1: Release Starfield's interior-to-exterior LoadingMenu black fade after Story exterior arrival; single-pass skips Timer 5 re-dims.}
    Actor player = Game.GetPlayer()
    if player == None || player.IsInInterior()
        return
    endif
    if SinglePassLandingFade
        if !surfaceFadeInDone
            ForceFadeIn("story_landing")
            surfaceFadeInDone = true
        endif
        Trace("story_fade single_pass=true already_faded=" + faded)
        return
    endif
    float w3d = 0.0
    while !player.Is3DLoaded() && w3d < StartLoadTimeout
        Utility.Wait(0.25)
        w3d += 0.25
    endwhile
    if player.IsInInterior() || !player.Is3DLoaded()
        return
    endif
    Utility.Wait(0.5)
    if player.IsInInterior() || !player.Is3DLoaded()
        return
    endif
    ForceFadeIn("story_landing")
    storyFadeTicks = 0
    StartTimer(1.5, 5)
EndFunction

Function RunWarfareBranch(Actor player, int rowIdx)
    Game.SetInChargen(false, false, false)
    Form progForm = Game.GetFormFromFile(0x000880, "FO4SFProgression.esm")
    ScriptObject prog = None
    if progForm != None
        prog = progForm.CastAs("FO4SF_ProgressionQuest")
    endif
    if prog != None
        Var[] allocArgs = new Var[1]
        allocArgs[0] = "warfare"
        int tries = 0
        bool allocOk = false
        while !allocOk && tries < 3
            tries += 1
            allocOk = prog.CallFunction("OpenAttributeAllocation", allocArgs) as bool
        endwhile
        if !allocOk
            Var[] spreadArgs = new Var[2]
            spreadArgs[0] = "warfare"
            spreadArgs[1] = false
            allocOk = prog.CallFunction("OfferStandardSpread", spreadArgs) as bool
        endif
        Var[] bgArgs = new Var[1]
        bgArgs[0] = WarfareBgIndices[rowIdx]
        prog.CallFunction("ApplyWarfareBackground", bgArgs)
    endif
    RunPreworldLooksChoice(player, true)
    Game.ShowFirstPersonGeometry(true)
    Game.SetCharGenHUDMode(0)
    player.RemoveAllItems(None, false, false)
    FillO2(player)
    if PipboyWristArmor != None
        player.AddItem(PipboyWristArmor, 1, true)
        player.EquipItem(PipboyWristArmor, false, true)
    endif
    EnsureVaultInteractivesRegistered()
    if !SyncPipboyOwnedWornState(player)
        if PipboyAcquiredGlobal != None
            PipboyAcquiredGlobal.SetValue(1.0)
        endif
    endif
    int gearAdded = 0
    int k = 0
    while k < WarfareGearIds.Length
        if WarfareGearRowIndices[k] == rowIdx
            Form gForm = Game.GetFormFromFile(WarfareGearIds[k], WarfareGearPlugins[k])
            if gForm != None
                player.AddItem(gForm, WarfareGearCounts[k], true)
                if WarfareGearEquips[k]
                    player.EquipItem(gForm, false, true)
                endif
                gearAdded += 1
            endif
        endif
        k += 1
    endwhile
    Trace("warfare gear n=" + gearAdded)
    string markerPlugin = CorePlugin
    int markerId = WarfareMarkerIds[rowIdx]
    int spRow = FindWarfareStartPlaceRow(rowIdx, WarfareKeys[rowIdx])
    if StartPlacePlugins != None && spRow >= 0 && spRow < StartPlacePlugins.Length && StartPlaceModes[spRow] == 2
        markerPlugin = StartPlacePlugins[spRow]
        markerId = StartPlaceMarkerIds[spRow]
    endif
    ObjectReference wMarker = Game.GetFormFromFile(markerId, markerPlugin) as ObjectReference
    float wx = WarfareMarkerX[rowIdx] + MergeOffsetX
    float wy = WarfareMarkerY[rowIdx] + MergeOffsetY
    float wz = WarfareMarkerZ[rowIdx] + 1.0
    bool moveOk = false
    float dist = 9999.0
    ObjectReference targetMarker = wMarker
    int wMoveTry = 0
    while targetMarker != None && player.IsInInterior() && wMoveTry < 3
        wMoveTry += 1
        player.MoveTo(targetMarker, 0.0, 0.0, 0.0, True, False)
        float mWait = 0.0
        while (player.IsInInterior() || !player.Is3DLoaded()) && mWait < SurfaceWait
            Utility.Wait(0.25)
            mWait += 0.25
        endwhile
    endwhile
    if player.IsInInterior()
        ObjectReference eFallback = Game.GetFormFromFile(ExitAnchorId, CorePlugin) as ObjectReference
        if eFallback != None
            targetMarker = eFallback
            wx = ArrivalX + MergeOffsetX
            wy = ArrivalY + MergeOffsetY
            wz = ArrivalZ + 1.0
            int fbTry = 0
            while player.IsInInterior() && fbTry < 3
                fbTry += 1
                player.MoveTo(eFallback, 0.0, 0.0, 0.0, True, False)
                float fbWait = 0.0
                while (player.IsInInterior() || !player.Is3DLoaded()) && fbWait < SurfaceWait
                    Utility.Wait(0.25)
                    fbWait += 0.25
                endwhile
            endwhile
            Trace("warfare move fallback anchor=" + eFallback + " tries=" + fbTry + " interior=" + player.IsInInterior())
        endif
    endif
    if targetMarker != None && !player.IsInInterior()
        int setTry = 0
        while !moveOk && setTry < SurfaceTries
            setTry += 1
            player.SetPosition(wx, wy, wz)
            player.SetAngle(0.0, 0.0, WarfareHeadings[rowIdx])
            Cell wc = player.GetParentCell()
            bool coreCell = false
            if wc != None
                coreCell = (wc.GetFormID() / 16777216) == (targetMarker.GetFormID() / 16777216)
            endif
            float dx = player.GetPositionX() - wx
            float dy = player.GetPositionY() - wy
            float dz = player.GetPositionZ() - wz
            dist = dx * dx + dy * dy
            moveOk = dist <= 25.0 && dz > -FallDrop && dz < 3.0 && !player.IsInInterior() && coreCell
            if !moveOk && setTry < SurfaceTries
                Utility.Wait(0.25)
            endif
        endwhile
    endif
    float wPost3d = 0.0
    while !player.Is3DLoaded() && wPost3d < StartLoadTimeout
        Utility.Wait(0.25)
        wPost3d += 0.25
    endwhile
    Utility.Wait(0.5)
    Trace("warfare move ok=" + moveOk + " marker=" + wMarker + " dist=" + dist + " z=" + player.GetPositionZ())
    RunSharedMapSetup()
    if wMarker != None
        WorldSpace pw = player.GetWorldSpace()
        if pw != None
            wMarker.Enable(False)
            if wMarker.GetWorldSpace() != pw
                wMarker.MoveTo(player, wx - player.GetPositionX(), wy - player.GetPositionY(), WarfareMarkerZ[rowIdx] - player.GetPositionZ(), False, False)
            endif
            if wMarker.GetWorldSpace() == pw
                wMarker.SetPosition(wx, wy, WarfareMarkerZ[rowIdx])
            endif
        endif
        ScriptObject wmm = None
        if MapMarkerQuestIds.Length > 0
            Form wmmForm = Game.GetFormFromFile(MapMarkerQuestIds[0], "FO4SFMapMarkers.esm")
            if wmmForm != None
                wmm = wmmForm.CastAs("FO4SF_MapMarkers")
            endif
        endif
        if wmm != None
            Var[] wmmArgs = new Var[1]
            wmmArgs[0] = wMarker
            wmm.CallFunction("DiscoverSingleMarker", wmmArgs)
        endif
    endif
    int slot = WarfareFactionSlots[rowIdx]
    float fame = WarfareFames[rowIdx]
    float infamy = WarfareInfamies[rowIdx]
    float karma = WarfareKarmas[rowIdx]
    int squadCap = WarfareSquadCaps[rowIdx]
    Form repForm = Game.GetFormFromFile(0x000800, "FO4SFReputation.esm")
    if repForm != None
        ScriptObject rep = repForm.CastAs("FO4SF_ReputationQuest")
        if rep != None
            Var[] repFacArgs = new Var[4]
            repFacArgs[0] = player
            repFacArgs[1] = slot
            repFacArgs[2] = fame
            repFacArgs[3] = infamy
            rep.CallFunction("SetFactionScoresAbsolute", repFacArgs)
            Var[] repKarmaArgs = new Var[2]
            repKarmaArgs[0] = player
            repKarmaArgs[1] = karma
            rep.CallFunction("SetKarmaAbsolute", repKarmaArgs)
        endif
    endif
    Faction fac = Game.GetFormFromFile(0x000810 + slot, "FO4SFReputation.esm") as Faction
    if fac != None
        player.AddToFaction(fac)
    endif
    GlobalVariable sqCapGlob = Game.GetFormFromFile(0x000801, "FO4SFCompanions.esm") as GlobalVariable
    if sqCapGlob != None
        sqCapGlob.SetValue(squadCap as float)
    endif
    Trace("warfare standing slot=" + slot + " fame=" + fame + " infamy=" + infamy + " karma=" + karma + " squad_cap=" + squadCap)
    ForceFadeIn("warfare")
    warfareFadeTicks = 0
    StartTimer(1.5, 4)
    AdvanceTo(210)
EndFunction

Event OnMenuOpenCloseEvent(string asMenuName, bool abOpening)
    if asMenuName == "LoadingMenu"
        if faded || startUiReady || GetStage() >= 5 || h00SkipLoading
            UnregisterStartLoadingHook()
            return
        endif
        if abOpening
            loadingMenuOpen = true
        else
            loadingMenuOpen = false
            loadingMenuClosedSeen = true
            Trace("mode loading menu closed")
        endif
        return
    endif
    if asMenuName == "ChargenMenu" && !abOpening
        if warfareWaitingCreator
            warfareWaitingCreator = false
            setupWaitingCreator = false
            Trace("warfare creator closed")
        elseif setupWaitingCreator
            setupWaitingCreator = false
            Trace("setup creator closed")
        endif
    endif
EndEvent

int Function RunSharedMapSetup()
{X4 / S5 single shared map setup function: prepares all markers as known & undiscovered, logging count and elapsed time.}
    if h00SkipMap
        Trace("h00 skipped shared map setup")
        return 0
    endif
    if mapSetupDone
        return CoreMarkerIds.Length
    endif
    mapSetupDone = true
    float t0 = Utility.GetCurrentRealTime()
    int count = 0
    ScriptObject mm = None
    if MapMarkerQuestIds.Length > 0
        Form mmForm = Game.GetFormFromFile(MapMarkerQuestIds[0], "FO4SFMapMarkers.esm")
        if mmForm != None
            mm = mmForm.CastAs("FO4SF_MapMarkers")
        endif
    endif
    if mm != None
        count = mm.CallFunction("PrepareKnownUndiscoveredAll", new Var[0]) as int
    endif
    int i = 0
    while i < CoreMarkerIds.Length
        ObjectReference cm = Game.GetFormFromFile(CoreMarkerIds[i], CorePlugin) as ObjectReference
        if cm != None
            cm.Enable(False)
            if mm == None
                count += 1
            endif
        endif
        i += 1
    endwhile
    float elapsed = Utility.GetCurrentRealTime() - t0
    Trace("map setup done markers=" + count + " elapsed=" + elapsed)
    return count
EndFunction

bool Function SyncPipboyOwnedWornState(Actor player)
{Syncs FO4SF_PipboyAcquired (1.0 iff owned AND worn; 0.0 if missing or unequipped) for pickup/equip/unequip/load.}
    if PipboyAcquiredGlobal == None || player == None || PipboyWristArmor == None
        return false
    endif
    bool owned = player.GetItemCount(PipboyWristArmor) > 0
    bool worn = owned && player.IsEquipped(PipboyWristArmor)
    if owned && worn
        PipboyAcquiredGlobal.SetValue(1.0)
    else
        PipboyAcquiredGlobal.SetValue(0.0)
    endif
    return owned && worn
EndFunction

Function EnsureVaultInteractivesRegistered()
    Actor player = Game.GetPlayer()
    if !itemWatchRegistered && player != None && VaultPistolBase != None
        itemWatchRegistered = true
        AddInventoryEventFilter(VaultPistolBase)
        Form ownPistol = Game.GetFormFromFile(0x000822, "FO4SFNewGame.esm")
        if ownPistol != None
            AddInventoryEventFilter(ownPistol)
        endif
        Trace("pistol filter added base=" + VaultPistolBase + " id=" + VaultPistolId)
        RegisterForRemoteEvent(player as ObjectReference, "OnItemAdded")
    endif
    if !pipboyEquipWatchRegistered && player != None && PipboyWristArmor != None
        pipboyEquipWatchRegistered = true
        AddInventoryEventFilter(PipboyWristArmor)
        RegisterForRemoteEvent(player, "OnItemEquipped")
        RegisterForRemoteEvent(player, "OnItemUnequipped")
        RegisterForRemoteEvent(player as ObjectReference, "OnItemRemoved")
    endif
    if !pipboyRegistered && PipboyCorpseRef != None
        pipboyRegistered = true
        RegisterForRemoteEvent(PipboyCorpseRef, "OnActivate")
        Trace("pipboy activator registered ref=" + PipboyCorpseRef + " id=" + PipboyCorpseRef.GetFormID() + " pos=" + PipboyCorpseRef.GetPositionX() + " " + PipboyCorpseRef.GetPositionY() + " " + PipboyCorpseRef.GetPositionZ())
    endif
    if !cogDoorRegistered && CogDoorId > 0
        cogDoorWatchedRef = Game.GetFormFromFile(CogDoorId, VaultPlugin) as ObjectReference
        if cogDoorWatchedRef != None
            cogDoorRegistered = true
            if TestModeGlobal == None || TestModeGlobal.GetValue() == 0.0
                cogDoorWatchedRef.BlockActivation(True, False)
            endif
            RegisterForRemoteEvent(cogDoorWatchedRef, "OnActivate")
        endif
    endif
    if !consoleRegistered && GearDoorConsoleRef != None
        consoleWatchedRef = GearDoorConsoleRef
        consoleRegistered = true
        RegisterForRemoteEvent(consoleWatchedRef, "OnActivate")
        Trace("console activator registered ref=" + consoleWatchedRef + " id=" + consoleWatchedRef.GetFormID() + " pos=" + consoleWatchedRef.GetPositionX() + " " + consoleWatchedRef.GetPositionY() + " " + consoleWatchedRef.GetPositionZ())
    endif
    if !portConsoleRegistered && ConsoleRefId > 0
        portConsoleWatchedRef = Game.GetFormFromFile(ConsoleRefId, VaultPlugin) as ObjectReference
        if portConsoleWatchedRef != None
            portConsoleRegistered = true
            if portConsoleWatchedRef != consoleWatchedRef
                RegisterForRemoteEvent(portConsoleWatchedRef, "OnActivate")
                Trace("console port activator registered ref=" + portConsoleWatchedRef)
            endif
        endif
    endif
EndFunction

Event Actor.OnItemEquipped(Actor akSender, Form akBaseObject, ObjectReference akReference)
    if PipboyWristArmor != None && akBaseObject == PipboyWristArmor && akSender == Game.GetPlayer()
        SyncPipboyOwnedWornState(akSender)
    endif
EndEvent

Event Actor.OnItemUnequipped(Actor akSender, Form akBaseObject, ObjectReference akReference)
    if PipboyWristArmor != None && akBaseObject == PipboyWristArmor && akSender == Game.GetPlayer()
        SyncPipboyOwnedWornState(akSender)
    endif
EndEvent

Event ObjectReference.OnItemRemoved(ObjectReference akSender, Form akBaseItem, int aiItemCount, ObjectReference akItemReference, ObjectReference akDestContainer, int aiTransferReason)
    Actor player = Game.GetPlayer()
    if PipboyWristArmor != None && akBaseItem == PipboyWristArmor && player != None && akSender == (player as ObjectReference)
        SyncPipboyOwnedWornState(player)
    endif
EndEvent

Event ObjectReference.OnItemAdded(ObjectReference akSender, Form akBaseItem, int aiItemCount, ObjectReference akItemReference, ObjectReference akSourceContainer, int aiTransferReason)
    if pistolPickedLogged || GetStage() >= 40 || akBaseItem == None || VaultPistolBase == None
        return
    endif
    Form ownPistol = Game.GetFormFromFile(0x000822, "FO4SFNewGame.esm")
    if akBaseItem == VaultPistolBase || (ownPistol != None && akBaseItem == ownPistol)
        pistolPickedLogged = true
        Actor player = Game.GetPlayer()
        bool equipped = False
        if player != None
            if !player.IsEquipped(akBaseItem)
                player.EquipItem(akBaseItem, False, False)
            endif
            equipped = player.IsEquipped(akBaseItem)
        endif
        Trace("pistol picked item=" + akBaseItem + " count=" + aiItemCount + " equipped=" + equipped)
    endif
EndEvent

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    Actor player = Game.GetPlayer()
    if akSender == None || player == None
        return
    endif
    if PipboyCorpseRef != None && akSender == PipboyCorpseRef && (akActionRef == player || akActionRef == None)
        HandlePipboyPickup(player)
        return
    endif
    if akActionRef != player
        return
    endif
    if cogDoorWatchedRef != None && akSender == cogDoorWatchedRef
        if GetStage() < 30 && (TestModeGlobal == None || TestModeGlobal.GetValue() == 0.0)
            int curState = cogDoorWatchedRef.GetOpenState()
            if curState == 1 || curState == 2
                cogDoorWatchedRef.SetOpen(False)
                curState = cogDoorWatchedRef.GetOpenState()
            endif
            Trace("cog door activate blocked by=player open_state=" + curState)
        endif
        return
    endif
    bool isPortConsole = portConsoleWatchedRef != None && akSender == portConsoleWatchedRef
    if !isPortConsole && ConsoleRefId > 0
        ObjectReference portCon = Game.GetFormFromFile(ConsoleRefId, VaultPlugin) as ObjectReference
        isPortConsole = portCon != None && akSender == portCon
    endif
    if (consoleWatchedRef != None && akSender == consoleWatchedRef) || isPortConsole
        if isPortConsole
            Trace("console port ref activated ref=" + akSender)
        endif
        ActivateGearDoorConsole()
    endif
EndEvent

Function ActivateGearDoorConsole()
{Opens Vault 111's gear door from its console activation once the Pip-Boy is equipped, advancing to stage 30.}
    if consoleOpening
        return
    endif
    int stage = GetStage()
    if stage < 10 || stage >= 40
        return
    endif
    bool hasPipboy = PipboyAcquiredGlobal != None && PipboyAcquiredGlobal.GetValue() >= 0.5
    if !hasPipboy && (TestModeGlobal == None || TestModeGlobal.GetValue() == 0.0)
        if NoPipboyMsg != None
            NoPipboyMsg.Show()
        endif
        Trace("console refused: no pipboy")
        return
    endif
    consoleOpening = true
    if ConsoleRefId > 0
        ObjectReference portCon = Game.GetFormFromFile(ConsoleRefId, VaultPlugin) as ObjectReference
        if portCon != None
            portCon.PlayAnimation("Stage2")
        endif
    endif
    ObjectReference cogDoor = None
    if CogDoorId > 0
        cogDoor = Game.GetFormFromFile(CogDoorId, VaultPlugin) as ObjectReference
    endif
    if cogDoor != None
        cogDoor.BlockActivation(False, False)
        int before = cogDoor.GetOpenState()
        if before != 1 && before != 2
            cogDoor.SetOpen(True)
        endif
        Utility.Wait(2.0)
        int after = cogDoor.GetOpenState()
        Trace("cog door console activated ref=" + consoleWatchedRef + " before=" + before + " after=" + after)
        if after != 1 && after != 2
            Trace("cog door open failed state=" + after)
            if TestModeGlobal == None || TestModeGlobal.GetValue() == 0.0
                cogDoor.BlockActivation(True, False)
            endif
            consoleOpening = false
            return
        endif
    else
        Trace("cog door " + VaultPlugin + ":" + CogDoorId + " does not resolve")
        if CogDoorId > 0
            Trace("cog door open failed state=-1")
            consoleOpening = false
            return
        endif
    endif
    consoleOpening = false
    if GetStage() < 30
        AdvanceTo(30, "vault_console")
        Debug.Notification("Vault door open - follow the catwalk to the elevator platform.")
        Trace("catwalk hint shown")
    endif
EndFunction

Function HandlePipboyPickup(Actor player)
{Equips FO4SF_PipboyWrist, raises wrist via IdleExamineWatch (0x000C154F), sets FO4SF_PipboyAcquired=1 when owned+worn.}
    if pipboyPickedUp
        return
    endif
    pipboyPickedUp = true
    if PipboyCorpseRef != None
        UnregisterForRemoteEvent(PipboyCorpseRef, "OnActivate")
    endif
    if PipboyWristArmor != None
        player.AddItem(PipboyWristArmor, 1, true)
        player.EquipItem(PipboyWristArmor, false, true)
    endif
    SyncPipboyOwnedWornState(player)
    bool examinePlayed = false
    Idle examineIdle = Game.GetFormFromFile(0x000C154F, "Starfield.esm") as Idle
    if examineIdle != None && player != None
        examinePlayed = player.PlayIdle(examineIdle)
    endif
    if PipboyCorpseRef != None
        PipboyCorpseRef.DisableNoWait(False)
    endif
    if PortPipboyStaticId > 0
        ObjectReference staticPipboy = Game.GetFormFromFile(PortPipboyStaticId, VaultPlugin) as ObjectReference
        if staticPipboy != None
            staticPipboy.DisableNoWait(False)
        endif
    endif
    bool worn = false
    if PipboyWristArmor != None
        worn = player.IsEquipped(PipboyWristArmor)
    endif
    Trace("pipboy pickup equipped flag=1 worn=" + worn)
    Trace("pipboy pickup examine_idle=" + examinePlayed)
EndFunction

Function OpenLiftAttributeAllocation()
    Form progForm = Game.GetFormFromFile(0x000880, "FO4SFProgression.esm")
    ScriptObject prog = None
    if progForm != None
        prog = progForm.CastAs("FO4SF_ProgressionQuest")
    endif
    if prog != None
        Var[] liftArgs = new Var[1]
        liftArgs[0] = "Lift"
        bool edited = prog.CallFunction("OpenAttributeAllocation", liftArgs) as bool
        if edited
            liftSpecConfirmed = true
        endif
        Trace("elevator attribute_allocation edited=" + edited + " confirmed=" + liftSpecConfirmed)
    else
        ScriptObject specScript = (self as ScriptObject).CastAs("FO4SF_NewGameSpecial")
        if specScript != None
            Actor player = Game.GetPlayer()
            Var[] specArgs = new Var[1]
            specArgs[0] = player
            bool specEdited = specScript.CallFunction("AllocateFromLift", specArgs) as bool
            if specEdited
                liftSpecConfirmed = true
            endif
            Trace("elevator attribute_allocation fallback=FO4SF_NewGameSpecial edited=" + specEdited + " confirmed=" + liftSpecConfirmed)
        else
            liftSpecConfirmed = true
            Trace("elevator attribute_allocation missing FO4SFProgression.esm:0x000880 and FO4SF_NewGameSpecial")
        endif
    endif
    asked = false
    StartTimer(0.1, 1)
EndFunction

Function PrepareArrivalMarkerDuringRide()
{Pre-resolves and enables the Vault 111 map marker during the lift ascent so arrival needs no extra setup tick.}
    if h00SkipDiscovery || rideMarkerPrepared || ArrivalDiscoveryId == 0
        return
    endif
    rideMarkerPrepared = true
    ObjectReference marker = Game.GetFormFromFile(ArrivalDiscoveryId, CorePlugin) as ObjectReference
    if marker != None
        marker.Enable(False)
        Trace("arrival marker prepared during ride ref=" + marker)
    endif
EndFunction

Function PreAttachArrivalMarker(Actor player)
    if h00SkipDiscovery || discoveryMarkerMoved || ArrivalDiscoveryId == 0 || arrivalWorld == None
        return
    endif
    ObjectReference marker = Game.GetFormFromFile(ArrivalDiscoveryId, CorePlugin) as ObjectReference
    if marker == None || !player.Is3DLoaded() || player.IsInInterior() || player.GetWorldSpace() != arrivalWorld
        return
    endif
    float mx = FallbackX + MergeOffsetX
    float my = FallbackY + MergeOffsetY
    float mz = FallbackZ
    float dx = marker.GetPositionX() - mx
    float dy = marker.GetPositionY() - my
    float dz = marker.GetPositionZ() - mz
    bool atMerged = marker.GetWorldSpace() == arrivalWorld && dx * dx + dy * dy <= 25.0 && dz >= -3.0 && dz <= 3.0
    if !atMerged
        discoveryMarkerMoved = true
        float px = player.GetPositionX()
        float py = player.GetPositionY()
        float pz = player.GetPositionZ()
        marker.Enable(False)
        marker.MoveTo(player, mx - px, my - py, mz - pz, False, False)
        if marker.GetWorldSpace() == arrivalWorld
            marker.SetPosition(mx, my, mz)
        endif
        Trace("arrival discovery marker preattached ref=" + marker + " world=" + marker.GetWorldSpace() + " pos=" + marker.GetPositionX() + " " + marker.GetPositionY() + " " + marker.GetPositionZ() + " target=" + mx + " " + my + " " + mz)
    endif
EndFunction

Function CheckReturnLift(Actor player)
{Post-stage-200 return lift loop: prompts Ride down / Stay once the player leaves > 12 m for >= 2 valid Commonwealth exterior ticks and steps back onto the surface pad.}
    if player == None || !player.Is3DLoaded()
        return
    endif
    float sx = ArrivalX + MergeOffsetX
    float sy = ArrivalY + MergeOffsetY
    float sz = ArrivalZ
    if returnSurfacePending
        if !player.IsInInterior()
            player.SetPosition(sx, sy, sz)
            player.SetAngle(0.0, 0.0, ArrivalHeading)
            if player.GetWorldSpace() != None
                arrivalWorld = player.GetWorldSpace()
            endif
            returnSurfacePending = false
            returnSurfaceWaitTicks = 0
            returnSurfaceTries = 0
            leftArrivalPad = false
            returnLiftArmed = false
            returnArmTicks = 0
            returnHasExteriorSample = true
            returnLastExteriorX = sx
            returnLastExteriorY = sy
            returnAsked = true
            Trace("return lift arrived surface pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ())
            return
        endif
        returnSurfaceWaitTicks += 1
        if returnSurfaceWaitTicks == 5 || returnSurfaceWaitTicks == 10 || returnSurfaceWaitTicks == 15
            ObjectReference rAnchor = Game.GetFormFromFile(ExitAnchorId, CorePlugin) as ObjectReference
            if rAnchor != None && returnSurfaceTries < 3
                returnSurfaceTries += 1
                player.MoveTo(rAnchor, 0.0, 0.0, 0.0, True, False)
                Trace("return lift surface retry n=" + returnSurfaceTries)
            endif
        elseif returnSurfaceWaitTicks >= 20
            returnSurfacePending = false
            returnVaultAsked = false
            returnSurfaceWaitTicks = 0
            returnSurfaceTries = 0
            Trace("return lift surface retry exhausted; re-arming prompt")
        endif
        return
    endif
    if player.IsInInterior()
        returnArmTicks = 0
        returnHasExteriorSample = false
        if !StandsInVault(player)
            return
        endif
        if !Near(player, PlatformX, PlatformY, PlatformZ, PlatformRadius)
            returnVaultAsked = false
            return
        endif
        if returnVaultAsked
            return
        endif
        returnVaultAsked = true
        int ubtn = ExitMessage.Show()
        Trace("return vault lift prompt button=" + ubtn)
        if ubtn == 0
            ObjectReference eAnchor = Game.GetFormFromFile(ExitAnchorId, CorePlugin) as ObjectReference
            if eAnchor != None
                returnSurfacePending = true
                returnSurfaceWaitTicks = 0
                returnSurfaceTries = 0
                player.MoveTo(eAnchor, 0.0, 0.0, 0.0, True, False)
                Trace("return lift surface moveto requested")
            endif
        elseif ubtn == 1
            OpenLiftAttributeAllocation()
            returnVaultAsked = false
        endif
        return
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float pz = player.GetPositionZ()
    Cell pCell = player.GetParentCell()
    WorldSpace pWorld = player.GetWorldSpace()
    if !player.Is3DLoaded() || player.IsInInterior() || pWorld == None || pCell == None
        returnArmTicks = 0
        returnHasExteriorSample = false
        return
    endif
    WorldSpace wantWorld = arrivalWorld
    if wantWorld == None
        wantWorld = ResolveHostWorld()
    endif
    if wantWorld != None && pWorld != wantWorld
        returnArmTicks = 0
        returnHasExteriorSample = false
        return
    endif
    float minMapX = MergeOffsetX - 3200.0
    float maxMapX = MergeOffsetX + 3200.0
    float minMapY = MergeOffsetY - 3200.0
    float maxMapY = MergeOffsetY + 3200.0
    if px < minMapX || px > maxMapX || py < minMapY || py > maxMapY
        returnArmTicks = 0
        returnHasExteriorSample = false
        return
    endif
    float prevX = sx
    float prevY = sy
    if returnHasExteriorSample
        prevX = returnLastExteriorX
        prevY = returnLastExteriorY
    endif
    returnHasExteriorSample = true
    returnLastExteriorX = px
    returnLastExteriorY = py
    float stepDx = px - prevX
    float stepDy = py - prevY
    float stepSq = stepDx * stepDx + stepDy * stepDy
    if stepSq > 40000.0
        returnArmTicks = 0
        return
    endif
    if leftArrivalPad && !returnLiftArmed
        returnLiftArmed = true
    endif
    float dx = px - sx
    float dy = py - sy
    float distSq = dx * dx + dy * dy
    if !returnLiftArmed
        if distSq > 144.0
            returnArmTicks += 1
            if returnArmTicks >= 2
                returnLiftArmed = true
                leftArrivalPad = true
                returnAsked = false
                Trace("return lift armed dist_sq=" + distSq)
            endif
        else
            returnArmTicks = 0
        endif
        return
    endif
    float padDx = px - sx
    float padDy = py - sy
    float padDz = pz - sz
    if padDx * padDx + padDy * padDy > PlatformRadius * PlatformRadius || padDz <= -3.0 || padDz >= 3.0
        returnAsked = false
        return
    endif
    if returnAsked || ReturnMessage == None
        return
    endif
    returnAsked = true
    int rbtn = ReturnMessage.Show()
    Trace("return lift prompt button=" + rbtn)
    if rbtn == 0
        ObjectReference vAnchor = Game.GetFormFromFile(VaultAnchorId, VaultPlugin) as ObjectReference
        if vAnchor != None
            if LiftId > 0
                ObjectReference lift = Game.GetFormFromFile(LiftId, VaultPlugin) as ObjectReference
                if lift != None && lift.Is3DLoaded()
                    lift.PlayAnimation("Play02")
                endif
            endif
            returnVaultAsked = true
            player.MoveTo(vAnchor, PlatformX - AnchorX, PlatformY - AnchorY, PlatformZ + 0.2 - AnchorZ, False, False)
            Trace("return lift moved to vault platform")
        endif
    endif
EndFunction
