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
{The elevator prompt (FO4SFNewGame.esm 0x801): 0 Continue, 1 S.P.E.C.I.A.L., 2 Character, 3 Stay.}

Message Property ReturnMessage Auto Const Mandatory
{The surface lift pad return prompt (FO4SFNewGame.esm 0x80B): button 0 rides back down to Vault 111, button 1 stays.}

Message Property ModePickMsg Auto Const Mandatory
{S4 Box 1 (0x806): 0 Story, 1 Warfare.}
Message Property SurvivalPickMsg Auto Const Mandatory
{S4 Box 2 (0x807): 0 Survival: No, 1 Survival: Yes.}
Message Property WarfareDiffMsg Auto Const Mandatory
{S4 Box 3 (0x808): 0..3 starting difficulty.}
Message Property WarfareGroupMsg Auto Const Mandatory
{S4 Box 4 (0x809): starting Warfare faction.}
Message Property WarfareSpotMsg Auto Const Mandatory
{S4 Box 5 (0x80A): starting Warfare deployment spot.}
Message Property NoPipboyMsg Auto Const Mandatory
{X2 (0x811): shown when activating the Vault 111 console before picking up the Pip-Boy.}

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
GlobalVariable Property PipboyAcquiredGlobal Auto Const Mandatory
{FO4SFNewGame.esm FO4SF_PipboyAcquired (0x80C), set to 1 once the Pip-Boy 3000 is picked up beside the Vault 111 console.}
Armor Property PipboyWristArmor Auto Const Mandatory
{FO4SFNewGame.esm FO4SF_PipboyWrist (0x80D), playable left-wrist Pip-Boy 3000 equipped on pickup.}
ObjectReference Property PipboyCorpseRef Auto Const Mandatory
{FO4SFNewGame.esm FO4SF_PipboyCorpsePickupRef (0x80F), placed persistent pickup beside the Vault-Tec scientist skeleton.}
bool Property FadeHold = true Auto Const
{S4: holds screen black and saving off from vault entry until start mode choice completes (--no-fade-hold sets false).}
int Property RaceMenuMode = 2 Auto Const
{Looks-only creator mode (2 = body and face) shared with FO4SF_NewGameLooks.}
int[] Property CoreMarkerIds Auto Const
{Persistent map marker FormIDs in FO4TerrainCore.esm prepared during shared map setup.}
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
int vaultMoves = 0                                           ; MoveTo calls onto the vault anchor
bool entered = false                                         ; the player stands in the vault anchor's cell after a move
bool faded = false
bool fadeHeld = false
bool modeChoiceRan = false
bool loadHookRegistered = false
bool podChecked = false
float surfaceMovedAt = 0.0                                   ; the ride's MoveTo (real time); 0 while none is pending
int surfaceMoves = 0
int surfaceSets = 0
WorldSpace arrivalWorld = None
bool exitFailed = false
bool fallbackPending = false
bool discoveryMarkerMoved = false
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
InputEnableLayer scannerLayer = None
bool consoleRegistered = false
ObjectReference consoleWatchedRef = None
bool cogDoorRegistered = false
ObjectReference cogDoorWatchedRef = None
bool pipboyRegistered = false
bool pipboyPickedUp = false
bool itemWatchRegistered = false
bool pistolPickedLogged = false
bool liftSpecConfirmed = false
bool liftCharRespecUsed = false
bool liftWaitingCreator = false
bool warfareWaitingCreator = false
bool mapSetupDone = false
bool rideMarkerPrepared = false
bool leftArrivalPad = false
bool returnAsked = false
bool returnVaultAsked = false
bool returnSurfacePending = false

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
    entered = EnterVault(player)
    if vaultMoves == 0 && centered == 0
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
    StartTimer(1.0, 1)
    player.WaitFor3DLoad()                                   ; latent: returns once the 3D is in, or will not load
    bool ready = player.Is3DLoaded()
    Trace("3d wait over loaded=" + ready)
    if ready
        if FadeHold
            HoldFadeForModeChoice()
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
    Actor player = Game.GetPlayer()
    if vaultMoves > 0 && StandsInVault(player)
        player.SetAngle(0.0, 0.0, PodHeading)
    endif
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
            Trace("handscanner disabled=true")
        endif
    endif
EndFunction

Function AdvanceTo(int n)
{SetStage, then the stage's actions (OnStageSet never fired on the mission's quest, 18 Oct, so nothing relies on it).}
    SetStage(n)
    if n <= applied
        return
    endif
    applied = n
    Trace("stage " + n)
    if n == 10
        SetObjectiveDisplayed(10)
        SetActive(True)
    elseif n == 40
        SetObjectiveCompleted(10)
    elseif n == 200
        CompleteQuest()
        StartLandingQuests()
    elseif n == 210
        CompleteQuest()
        StartLandingQuests()
    endif
EndFunction

Event OnTimer(int aiTimerID)
    if exitFailed
        return
    endif
    if aiTimerID != 1
        return
    endif
    Actor player = Game.GetPlayer()
    EnsureLoadHookRegistered(player)
    int stage = GetStage()
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
        if FadeHold
            HoldFadeForModeChoice()
        else
            FadeIn("timer")                                  ; once: the start may still be in its 3D wait
        endif
        if !entered
            if vaultMoves > 0 && StandsInVault(player)
                ; the start's move took once the load was through (the cell check right after a MoveTo during the first
                ; load is unverified): no second move, which would be a second loading screen
                entered = true
                Trace("enter vault confirmed after the load pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " cell=" + player.GetParentCell())
            else
                entered = EnterVault(player)                 ; the temporary-anchor mode after its centering, or a missed move
            endif
        endif
        if !entered
            StartTimer(1.0, 1)                               ; retried each second
            return
        endif
        HoldOffPass(2)                                       ; once the game runs: a quest that started after the first pass
        int chosenMode = RunModeChoiceChain(player)
        if chosenMode == 2
            return
        endif
        if ClearInventory
            ResetInventory(player)
            FillO2(player)
        endif
        AdvanceTo(10)
        startedAt = Utility.GetCurrentRealTime()
    elseif stage == 5
        if GameModeGlobal != None && (GameModeGlobal.GetValue() as int) == 1
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
        if Utility.GetCurrentRealTime() - startedAt > LooksWait
            Trace("looks done: LooksWait fallback after " + LooksWait + " s")
            AdvanceTo(20)
        endif
    elseif stage == 20 || stage == 30
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
    if GetStage() < 200 && GetStage() != 1 && !exitFailed
        StartTimer(1.0, 1)
    elseif GetStage() == 200 && !exitFailed
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
    if ok
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
 ContentResources.zip, read 29 Oct), so whether quest items stay is unverified: the count left says how many items
 stayed, not which. The count before and after is logged (GetItemCount(None) counts every item in FO4; unverified in
 Starfield, so both numbers are logged), then the vault suit, when the build names one, is added and equipped.}
    int before = player.GetItemCount(None)
    player.RemoveAllItems(None, false, false)
    int after = player.GetItemCount(None)
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
                AdvanceTo(30)
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
    asked = true                                             ; asked once per visit to the platform
    Trace("lift platform waiting cage_door=open")
    int button = ExitMessage.Show()
    Trace("elevator prompt button=" + button)
    if button == 0
        if !liftSpecConfirmed && (TestModeGlobal == None || TestModeGlobal.GetValue() == 0.0)
            Debug.Notification("Confirm S.P.E.C.I.A.L. before leaving Vault 111.")
            Trace("elevator continue refused: special unconfirmed")
            asked = false
            StartTimer(0.1, 1)
            return
        endif
        Trace("lift cage_door=closing")
        if LiftId > 0
            StartAscent(player)
        else
            RunSharedMapSetup()
            Surface(player)
        endif
    elseif button == 1
        OpenLiftAttributeAllocation()
    elseif button == 2
        OpenLiftCharacterRespec()
    else
        Trace("elevator stay")
    endif
EndFunction

Function StartAscent(Actor player)
{One play on the real placed lift. Position remains under the platform's moving collision until completion.}
    if rideActive || rideTransferred || exitFailed
        return
    endif
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
        FailExit("lift_play_refused")
        return
    endif
    RunSharedMapSetup()
EndFunction

Event OnAnimationEvent(ObjectReference akSource, string asEventName)
    if !rideActive || exitFailed || akSource != ridingLift || asEventName != "Done"
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
    if !rideActive || rideTransferred || exitFailed
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
    ObjectReference anchor = Game.GetFormFromFile(ExitAnchorId, CorePlugin) as ObjectReference
    if anchor == None
        Trace("exit anchor " + CorePlugin + ":" + ExitAnchorId + " does not resolve")
        if LiftId > 0
            FailExit("lift_exit_anchor_unavailable")
        endif
        return
    endif
    surfaceSets = 0
    arrivalWorld = None
    fallbackPending = false
    discoveryMarkerMoved = false
    landingChecks = 0
    player.MoveTo(anchor, 0.0, 0.0, 0.0, True, False)
    surfaceMoves += 1
    surfaceMovedAt = Utility.GetCurrentRealTime()
    Trace("surface moveto pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " world=" + player.GetWorldSpace() + " moves=" + surfaceMoves)
EndFunction

Function FinishSurface(Actor player)
{The ride up, second half: SetPosition on the merged arrival, a tick after the MoveTo at the earliest and once the player
 is outside with their 3D loaded. Because persistent references in the overlay world retain their unmerged local XY while
 exterior grid cells are shifted by MergeOffset, the initial MoveTo lands in a procedural Mars Surface cell of the runtime
 MarsPlanetWorld; SetPosition shifts the player onto the merged core cell first, and the post-move parent cell must then
 carry the core plugin's load index. Exhaustion stops the exit with failure.}
    if player.IsInInterior()
        if Utility.GetCurrentRealTime() - surfaceMovedAt > SurfaceWait
            if surfaceMoves < 2
                Trace("surface still inside " + SurfaceWait + " s after the moveto: moving again")
                Surface(player)
            else
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
    player.SetPosition(x, y, ArrivalZ)
    player.SetAngle(0.0, 0.0, ArrivalHeading)
    surfaceSets += 1
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
    Trace("surface setposition ok=" + ok + " set=" + surfaceSets + " pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " target=" + x + " " + y + " " + ArrivalZ + " core_cell=" + coreCell + " cell=" + afterCell + " world=" + afterWorld)
    if ok
        arrivalWorld = afterWorld
        surfaceMovedAt = 0.0
        arrivedAt = Utility.GetCurrentRealTime()
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
{Confirm the landing on a later loaded tick in the attached exterior world. A fallback move is checked on another
 tick; exhaustion is failure. Discovery is requested only after the landing and marker's placement both confirm.}
    if Utility.GetCurrentRealTime() - arrivedAt < 3.0
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
    if !AtArrival(player)
        FailExit("landing_position_not_confirmed")
        return
    endif
    if !RequestArrivalDiscovery(player)
        if landingChecks >= 30
            FailExit("arrival_marker_not_attached")
        endif
        return
    endif
    Trace("landed z=" + z + " confirmed=True fallback=" + fallbackPending + " world=" + arrivalWorld)
    AdvanceTo(200)
EndFunction

bool Function RequestArrivalDiscovery(Actor player)
    if ArrivalDiscoveryId == 0
        Trace("arrival discovery disabled: custom exit anchor")
        return true
    endif
    ObjectReference marker = Game.GetFormFromFile(ArrivalDiscoveryId, CorePlugin) as ObjectReference
    if marker == None
        Trace("arrival discovery waits: marker missing")
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
        if !discoveryMarkerMoved && player.Is3DLoaded() && !player.IsInInterior() && player.GetWorldSpace() == arrivalWorld && AtArrival(player)
            discoveryMarkerMoved = true
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
            Trace("arrival discovery waits: marker world=" + marker.GetWorldSpace() + " same_world=" + sameWorld + " at_merged=" + atMerged)
        endif
        return false
    endif
    ; Native reads yield between calls: recheck the player after reading the marker, immediately before mutation.
    bool enabledBefore = Game.IsFastTravelEnabled()
    if !player.Is3DLoaded() || player.IsInInterior() || player.GetWorldSpace() != arrivalWorld || !AtArrival(player) || marker.GetWorldSpace() != arrivalWorld
        return false
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
    exitFailed = true
    rideActive = false
    if ridingLift != None
        UnregisterForAnimationEvent(ridingLift, "Done")
    endif
    surfaceMovedAt = 0.0
    Trace("exit failed reason=" + reason + " stage=" + GetStage())
EndFunction

bool Function Near(Actor player, float x, float y, float z, float radius)
    float dx = player.GetPositionX() - x
    float dy = player.GetPositionY() - y
    float dz = player.GetPositionZ() - z
    return dx * dx + dy * dy <= radius * radius && dz < 3.0 && dz > -3.0
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
    if !loadHookRegistered && player != None
        loadHookRegistered = true
        RegisterForRemoteEvent(player, "OnPlayerLoadGame")
    endif
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    if GameModeGlobal != None && (GameModeGlobal.GetValue() as int) == 0 && GetStage() >= 10
        GameModeGlobal.SetValue(1.0)
        Trace("mode load default=story stage=" + GetStage())
    endif
EndEvent

Function HoldFadeForModeChoice()
    if fadeHeld || faded
        return
    endif
    fadeHeld = true
    Game.FadeOutGame(True, True, 0.0, 0.1, True)
    Game.SetInChargen(true, true, false)
    Trace("mode fade held")
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
    modeChoiceRan = true
    int mBtn = 0
    if ModePickMsg != None
        mBtn = ModePickMsg.Show()
    endif
    int modeVal = 1
    if mBtn == 1
        modeVal = 2
    endif
    int sBtn = 0
    if SurvivalPickMsg != None
        sBtn = SurvivalPickMsg.Show()
    endif
    int survVal = 0
    if sBtn == 1
        survVal = 1
    endif
    if GameModeGlobal != None
        GameModeGlobal.SetValue(modeVal as float)
    endif
    if SurvivalStartGlobal != None
        SurvivalStartGlobal.SetValue(survVal as float)
    endif
    if SurvivalLockedGlobal != None
        SurvivalLockedGlobal.SetValue(survVal as float)
    endif
    FO4SF_HardcoreQuest hc = Game.GetFormFromFile(0x000830, "FO4SFHardcore.esm") as FO4SF_HardcoreQuest
    if hc != None
        hc.EvaluateHardcore("start_choice")
    endif
    if modeVal == 1
        if StartChoiceDoneGlobal != None
            StartChoiceDoneGlobal.SetValue(1.0)
        endif
        Trace("mode choice mode=story survival=" + survVal)
        AdvanceTo(5)
        FadeIn("mode_story")
        return 1
    endif
    int diff = 1
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
    int pickedSlot = 0
    if WarfareDistinctFactionSlots.Length > 0
        pickedSlot = WarfareDistinctFactionSlots[gBtn]
    endif
    int sIdxBtn = 0
    if WarfareSpotMsg != None && WarfareKeys.Length > 1
        sIdxBtn = WarfareSpotMsg.Show()
        if sIdxBtn < 0 || sIdxBtn >= WarfareKeys.Length
            sIdxBtn = 0
        endif
    endif
    int rowIdx = -1
    int r = 0
    while r < WarfareKeys.Length
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
    if StartDifficultyGlobal != None
        StartDifficultyGlobal.SetValue(diff as float)
    endif
    if WarfareFactionGlobal != None
        WarfareFactionGlobal.SetValue(pickedSlot as float)
    endif
    if WarfareStartIndexGlobal != None
        WarfareStartIndexGlobal.SetValue(rowIdx as float)
    endif
    if StartChoiceDoneGlobal != None
        StartChoiceDoneGlobal.SetValue(1.0)
    endif
    Trace("mode choice mode=warfare survival=" + survVal)
    Trace("warfare pick faction=" + pickedSlot + " start=" + WarfareKeys[rowIdx] + " difficulty=" + diff)
    AdvanceTo(5)
    RunWarfareBranch(player, rowIdx)
    return 2
EndFunction

Function RunWarfareBranch(Actor player, int rowIdx)
    if LooksWait > 0.0
        RegisterForMenuOpenCloseEvent("ChargenMenu")
        warfareWaitingCreator = true
        Trace("warfare creator open mode=" + RaceMenuMode)
        Game.ShowRaceMenu(None, RaceMenuMode)
        float waited = 0.0
        while warfareWaitingCreator && waited < LooksWait
            Utility.Wait(0.5)
            waited += 0.5
        endwhile
        warfareWaitingCreator = false
    endif
    FO4SF_ProgressionQuest prog = Game.GetFormFromFile(0x000880, "FO4SFProgression.esm") as FO4SF_ProgressionQuest
    if prog != None
        int tries = 0
        bool allocOk = false
        while !allocOk && tries < 5
            tries += 1
            allocOk = prog.OpenAttributeAllocation("warfare")
        endwhile
        prog.ApplyWarfareBackground(WarfareBgIndices[rowIdx])
    endif
    player.RemoveAllItems(None, false, false)
    FillO2(player)
    if PipboyWristArmor != None
        player.AddItem(PipboyWristArmor, 1, true)
        player.EquipItem(PipboyWristArmor, false, true)
    endif
    if PipboyAcquiredGlobal != None
        PipboyAcquiredGlobal.SetValue(1.0)
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
    ObjectReference wMarker = Game.GetFormFromFile(WarfareMarkerIds[rowIdx], CorePlugin) as ObjectReference
    float wx = WarfareMarkerX[rowIdx] + MergeOffsetX
    float wy = WarfareMarkerY[rowIdx] + MergeOffsetY
    float wz = WarfareMarkerZ[rowIdx] + 1.0
    bool moveOk = false
    float dist = 9999.0
    if wMarker != None
        player.MoveTo(wMarker, 0.0, 0.0, 0.0, True, False)
        float mWait = 0.0
        while (player.IsInInterior() || !player.Is3DLoaded()) && mWait < SurfaceWait
            Utility.Wait(0.25)
            mWait += 0.25
        endwhile
        int setTry = 0
        while !moveOk && setTry < SurfaceTries
            setTry += 1
            player.SetPosition(wx, wy, wz)
            player.SetAngle(0.0, 0.0, WarfareHeadings[rowIdx])
            Cell wc = player.GetParentCell()
            bool coreCell = false
            if wc != None
                coreCell = (wc.GetFormID() / 16777216) == (wMarker.GetFormID() / 16777216)
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
        FO4SF_MapMarkers wmm = None
        if MapMarkerQuestIds.Length > 0
            wmm = Game.GetFormFromFile(MapMarkerQuestIds[0], "FO4SFMapMarkers.esm") as FO4SF_MapMarkers
        endif
        if wmm != None
            wmm.DiscoverSingleMarker(wMarker)
        endif
    endif
    int slot = WarfareFactionSlots[rowIdx]
    float fame = WarfareFames[rowIdx]
    float infamy = WarfareInfamies[rowIdx]
    float karma = WarfareKarmas[rowIdx]
    int squadCap = WarfareSquadCaps[rowIdx]
    FO4SF_ReputationQuest rep = Game.GetFormFromFile(0x000800, "FO4SFReputation.esm") as FO4SF_ReputationQuest
    if rep != None
        rep.SetFactionScoresAbsolute(player, slot, fame, infamy)
        rep.SetKarmaAbsolute(player, karma)
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
    FadeIn("warfare")
    AdvanceTo(210)
EndFunction

Event OnMenuOpenCloseEvent(string asMenuName, bool abOpening)
    if asMenuName == "ChargenMenu" && !abOpening
        if warfareWaitingCreator
            warfareWaitingCreator = false
            Trace("warfare creator closed")
        endif
        if liftWaitingCreator
            liftWaitingCreator = false
            asked = false
            Trace("elevator character creator closed")
            StartTimer(0.1, 1)
        endif
    endif
EndEvent

int Function RunSharedMapSetup()
{X4 / S5 single shared map setup function: prepares all markers as known & undiscovered, logging count and elapsed time.}
    if mapSetupDone
        return CoreMarkerIds.Length
    endif
    mapSetupDone = true
    float t0 = Utility.GetCurrentRealTime()
    int count = 0
    FO4SF_MapMarkers mm = None
    if MapMarkerQuestIds.Length > 0
        mm = Game.GetFormFromFile(MapMarkerQuestIds[0], "FO4SFMapMarkers.esm") as FO4SF_MapMarkers
    endif
    if mm != None
        count = mm.PrepareKnownUndiscoveredAll()
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

Function EnsureVaultInteractivesRegistered()
    Actor player = Game.GetPlayer()
    if !itemWatchRegistered && player != None
        itemWatchRegistered = true
        RegisterForRemoteEvent(player as ObjectReference, "OnItemAdded")
    endif
    if !pipboyRegistered && PipboyCorpseRef != None
        pipboyRegistered = true
        RegisterForRemoteEvent(PipboyCorpseRef, "OnActivate")
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
    if !consoleRegistered && ConsoleRefId > 0
        consoleWatchedRef = Game.GetFormFromFile(ConsoleRefId, VaultPlugin) as ObjectReference
        if consoleWatchedRef != None
            consoleRegistered = true
            RegisterForRemoteEvent(consoleWatchedRef, "OnActivate")
            Trace("console registered ref=" + consoleWatchedRef + " pos=" + consoleWatchedRef.GetPositionX() + " " + consoleWatchedRef.GetPositionY() + " " + consoleWatchedRef.GetPositionZ())
        endif
    endif
EndFunction

Event ObjectReference.OnItemAdded(ObjectReference akSender, Form akBaseItem, int aiItemCount, ObjectReference akItemReference, ObjectReference akSourceContainer, int aiTransferReason)
    if pistolPickedLogged || GetStage() >= 40 || akBaseItem == None
        return
    endif
    if akBaseItem as Weapon != None
        pistolPickedLogged = true
        Trace("pistol picked item=" + akBaseItem + " count=" + aiItemCount)
    endif
EndEvent

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    Actor player = Game.GetPlayer()
    if akSender == None || player == None || akActionRef != player
        return
    endif
    if PipboyCorpseRef != None && akSender == PipboyCorpseRef
        HandlePipboyPickup(player)
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
    if consoleWatchedRef != None && akSender == consoleWatchedRef
        ActivateGearDoorConsole()
    endif
EndEvent

Function ActivateGearDoorConsole()
{Opens Vault 111's gear door from its console activation once the Pip-Boy is equipped, advancing to stage 30.}
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
        int after = cogDoor.GetOpenState()
        Trace("cog door console activated ref=" + consoleWatchedRef + " before=" + before + " after=" + after)
    else
        Trace("cog door " + VaultPlugin + ":" + CogDoorId + " does not resolve")
    endif
    if stage < 30
        AdvanceTo(30)
    endif
EndFunction

Function HandlePipboyPickup(Actor player)
{Equips FO4SF_PipboyWrist, sets FO4SF_PipboyAcquired to 1, and disables the corpse pickup reference once.}
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
    if PipboyAcquiredGlobal != None
        PipboyAcquiredGlobal.SetValue(1.0)
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
EndFunction

Function OpenLiftAttributeAllocation()
    FO4SF_ProgressionQuest prog = Game.GetFormFromFile(0x000880, "FO4SFProgression.esm") as FO4SF_ProgressionQuest
    if prog != None
        bool edited = prog.OpenAttributeAllocation("lift")
        if edited
            liftSpecConfirmed = true
        endif
        Trace("elevator attribute_allocation edited=" + edited + " confirmed=" + liftSpecConfirmed)
    else
        liftSpecConfirmed = true
        Trace("elevator attribute_allocation missing FO4SFProgression.esm:0x000880")
    endif
    asked = false
    StartTimer(0.1, 1)
EndFunction

Function OpenLiftCharacterRespec()
    if liftCharRespecUsed
        Debug.Notification("Character appearance can only be changed once on the lift.")
        Trace("elevator character respec refused: limit_1")
        asked = false
        StartTimer(0.1, 1)
        return
    endif
    liftCharRespecUsed = true
    RegisterForMenuOpenCloseEvent("ChargenMenu")
    liftWaitingCreator = true
    Trace("elevator character respec used=1 mode=" + RaceMenuMode)
    Game.ShowRaceMenu(None, RaceMenuMode)
EndFunction

Function PrepareArrivalMarkerDuringRide()
{Pre-resolves and enables the Vault 111 map marker during the lift ascent so arrival needs no extra setup tick.}
    if rideMarkerPrepared || ArrivalDiscoveryId == 0
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
    if discoveryMarkerMoved || ArrivalDiscoveryId == 0 || arrivalWorld == None
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
{Post-stage-200 return lift loop: prompts Ride down / Stay once the player leaves > 12 m and steps back onto the surface pad.}
    if !player.Is3DLoaded()
        return
    endif
    float sx = ArrivalX + MergeOffsetX
    float sy = ArrivalY + MergeOffsetY
    float sz = ArrivalZ
    if returnSurfacePending
        if !player.IsInInterior()
            player.SetPosition(sx, sy, sz)
            player.SetAngle(0.0, 0.0, ArrivalHeading)
            returnSurfacePending = false
            leftArrivalPad = false
            returnAsked = true
            Trace("return lift arrived surface pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ())
        endif
        return
    endif
    if player.IsInInterior()
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
                player.MoveTo(eAnchor, 0.0, 0.0, 0.0, True, False)
                Trace("return lift surface moveto requested")
            endif
        elseif ubtn == 1
            OpenLiftAttributeAllocation()
            returnVaultAsked = false
        elseif ubtn == 2
            OpenLiftCharacterRespec()
            returnVaultAsked = false
        endif
        return
    endif
    float dx = player.GetPositionX() - sx
    float dy = player.GetPositionY() - sy
    float distSq = dx * dx + dy * dy
    if !leftArrivalPad
        if distSq > 144.0
            leftArrivalPad = true
            returnAsked = false
            Trace("return lift armed dist_sq=" + distSq)
        endif
        return
    endif
    if !Near(player, sx, sy, sz, PlatformRadius)
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
