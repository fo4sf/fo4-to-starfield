Scriptname FO4SF_NewGameQuest extends Quest
{A Fallout 4 new game in Starfield (fo4-to-starfield, docs/newgame/vault111-start.md): this quest is Starfield's startup
 quest. The plugin overrides the DefaultObject StartupQuest_DO (Starfield.esm 00562D), which names MQ101 in vanilla, so
 a New Game starts this quest instead of Starfield's opening (our own start, the owner's pick F, 29 Oct). On a NEW game
 it moves the player in front of their cryo pod in the converted Vault 111 (FO4Port.esm) while the game is still on its
 first loading screen, fades the screen in once the vault has loaded, holds off Starfield's start quests, opens the cog
 door from its console, and takes the player up the elevator onto the Commonwealth at Fallout 4's surface arrival.
 Every step and a status line every 5 s go to the user log "fo4sf_newgame"
 (My Games\Starfield\Logs\Script\User\fo4sf_newgame.0.log), the evidence of a run.
 Why the start must move the player itself (records, PC 21 Oct; the three runs of 28 Oct): the startup quest is what
 moves the player into the game. MQ101's stage 0 picks its start by the GLOB MQ101Debug and the matching entry's
 fragment does the move (the intro's: MoveTo CharGenStartMarker, then WaitFor3dLoad); a value no entry matches moves
 nobody, and the new game never left its loading screen (run 2). Roleplayers' Alternate Start, the open-source mod that
 also replaces StartupQuest_DO, moves the player from its startup quest's OnQuestStarted (Game.FastTravel) and, once
 its start cell has loaded, calls Game.FadeOutGame(False, True, 0.0, 0.1, False) (";finishes main menu loading"). In
 run 2 our quest, start-game enabled then, never got its OnQuestInit while the version alias's OnInit did, so
 OnQuestInit waits for that first load (supported hypothesis); the start therefore runs from OnQuestStarted, with
 OnQuestInit as a second route, once, from whichever comes first (Begin). A start that finds no new game (a New Game+)
 or cannot move the player at all stands down and, when either of its readings says the game is still loading (the
 player's 3D not in, or no parent cell yet), first asks Starfield's opening to start (HandBack, which waits for
 nothing), so that its stage 0 moves the player and the first load does not wait on a move nobody makes (unverified:
 whether MQ101 started by a script during that load starts up then and moves the player). The temporary-anchor mode,
 whose centering during that load is unverified and hands nothing back when it moves nobody, is built only on request
 since newgame_v11 (the writer's --allow-temporary-anchor).
 MQ101 never runs, so the plugin overrides no MQ101Debug: right after the hold-off's first pass the quest writes
 DebugAfterHold (two, the value the main quests' developer skip-start stages write) into the global itself, which opens
 PEO_SustenanceAllowed, whose normal route (MQ101 stage 310) is never reached. The guard logs the value the game read
 (the "guard" line) and the write logs its own line ("mq101debug written").
 Stages are the published contract (NG-14) other scripts and mods may listen to; make_newgame.py STAGE_CONTRACT lists
 the same numbers with the same meanings (tests/test_newgame.py) and the doc's stage table explains them:
   0 started: as Starfield's startup quest, the guard, the move into the vault and the hold-off
   1 stood down: not a new game, or no move into the vault (Starfield's opening is asked to start if the game still loads)
   10 in the vault: the player stands at their pod
   20 looks done: character creation closed, or LooksWait passed
   30 cog door opened: from its console
   40 on the surface: the elevator ride is over
   200 complete: landed, or put on the fallback spot
 The places come from other plugins by their plugin-local form ids (the FO4SF_LoadDoor contract): this plugin has no
 master but Starfield.esm, so a rebuilt port or core never needs this plugin rebuilt while those ids stay (stable ids).
 The vault anchor has two modes (AnchorTemporary): a persistent reference, which resolves before the vault loads, or the
 temporary COC marker, which the script must load the cell for (Debug.CenterOnCell) before the same MoveTo (on request
 only since newgame_v11, see above).}

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
 MQ_TutorialQuest_Misc04: the main-quest start, the opening, and the two its stop starts). Walked twice: in the start,
 right after the move, and again once the vault has loaded, for a quest that started meanwhile (MQ00 is start-game
 enabled, and whether it starts before our start is unverified) and for what MQ101's stage 9000 starts if something had
 started MQ101. Each is stopped only if it runs; each stop is logged with its pass.}

Message Property ExitMessage Auto Const Mandatory
{The elevator prompt (FO4SFNewGame.esm 0x801): button 0 rides up, button 1 stays.}

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
float Property ConsoleX Auto Const Mandatory
float Property ConsoleY Auto Const Mandatory
float Property ConsoleZ Auto Const Mandatory
float Property PlatformX Auto Const Mandatory
float Property PlatformY Auto Const Mandatory
float Property PlatformZ Auto Const Mandatory
{The elevator platform V111ElevatorREF (FO4 000244EB) at the bottom of its shaft: standing on it offers the ride up.}

string Property CorePlugin = "FO4TerrainCore.esm" Auto Const
int Property ExitAnchorId Auto Const Mandatory
{A persistent reference in the core world (its Vault 111 map marker): MoveTo it puts the player in the core world at
 the reference's LOCAL position (persistent references are not moved by the merge), a later tick's SetPosition then
 places them (FinishSurface).}
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
float Property PlatformRadius = 2.5 Auto Const
float Property FallDrop = 3.0 Auto Const
{A landing this far below its target z (m) counts as a fall: the player is put on the fallback spot.}
float Property SurfaceWait = 10.0 Auto Const
{Seconds after the ride's MoveTo the player may still be inside before it counts as missed: one more MoveTo, then the
 elevator prompt again.}
int Property SurfaceTries = 3 Auto Const
{SetPositions on the merged arrival, one a tick, before stage 40 goes on without one taking (CheckLanding's fallback
 then decides).}
float Property LooksWait = 120.0 Auto Const
{Seconds stage 10 waits for the looks script (FO4SF_NewGameLooks, optional) to set stage 20 (the creator closed, or the
 quick start) before moving on: the fallback when the creator's close event never comes. 0 in a --no-looks build.}

bool Property ClearInventory = false Auto Const
{The starting inventory reset (NG-K8, the writer's --clear-inventory; off until an in-game run shows what Starfield
 leaves the player with when MQ101 never runs). True: once the player is in the vault, RemoveAllItems (whether
 quest items stay is unverified, ResetInventory) and the count removed logged as "inventory cleared removed=<n>
 left=<n>"; then VaultSuitId.}
int Property VaultSuitId = 0 Auto Const
{With ClearInventory, the vault suit ARMO of the port (FO4Port.esm, resolved by the writer's --vault-suit <EditorID>),
 added and equipped after the reset; 0 is none. Logged as "vault suit equipped <armor> worn=<bool>".}

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
bool podChecked = false
float surfaceMovedAt = 0.0                                   ; the ride's MoveTo (real time); 0 while none is pending
int surfaceMoves = 0
int surfaceSets = 0

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
    if DebugAfterHold != 0
        ; MQ101 never runs, so its stage 0 never reads this; the write opens the sustenance condition (DebugAfterHold)
        float was = DebugGlobal.GetValue()
        DebugGlobal.SetValueInt(DebugAfterHold)
        Trace("mq101debug written=" + DebugGlobal.GetValue() + " was=" + was)
    endif
    StartTimer(1.0, 1)
    player.WaitFor3DLoad()                                   ; latent: returns once the 3D is in, or will not load
    bool ready = player.Is3DLoaded()
    Trace("3d wait over loaded=" + ready)
    if ready
        FadeIn("start")                                      ; else the timer fades in once the 3D is in
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
    Trace("fade in by=" + by + " loaded=" + player.Is3DLoaded() + " cell=" + player.GetParentCell() + "; saving and HUD on")
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
    endif
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID != 1
        return
    endif
    Actor player = Game.GetPlayer()
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
        FadeIn("timer")                                      ; once: the start may still be in its 3D wait
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
        if ClearInventory
            ResetInventory(player)
        endif
        AdvanceTo(10)
        startedAt = Utility.GetCurrentRealTime()
    elseif stage == 10
        if !podChecked && player.Is3DLoaded()
            CheckPod(player)
        endif
        if Utility.GetCurrentRealTime() - startedAt > LooksWait
            Trace("looks done: LooksWait fallback after " + LooksWait + " s")
            AdvanceTo(20)
        endif
    elseif stage == 20 || stage == 30
        if surfaceMovedAt > 0.0
            FinishSurface(player)                            ; the ride's MoveTo is done: the arrival waits for this tick
        else
            InVault(player, stage)
        endif
    elseif stage == 40
        CheckLanding(player)
    endif
    if ticks % 5 == 0
        Trace("status stage=" + GetStage() + " pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " cell=" + player.GetParentCell() + " world=" + player.GetWorldSpace())
    endif
    if GetStage() < 200 && GetStage() != 1
        StartTimer(1.0, 1)
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
    float dx = player.GetPositionX() - PodX
    float dy = player.GetPositionY() - PodY
    float drop = PodZ + PodLift - player.GetPositionZ()
    bool ok = dx * dx + dy * dy <= PodRadius * PodRadius && drop <= PodDrop
    Trace("pod settle ok=" + ok + " pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " dx=" + dx + " dy=" + dy + " drop=" + drop)
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
    endif
EndFunction

Function InVault(Actor player, int stage)
    if !player.IsInInterior()
        return
    endif
    if stage == 20 && CogDoorId > 0 && Near(player, ConsoleX, ConsoleY, ConsoleZ, ConsoleRadius)
        ObjectReference cogDoor = Game.GetFormFromFile(CogDoorId, VaultPlugin) as ObjectReference
        if cogDoor != None
            int before = cogDoor.GetOpenState()
            cogDoor.SetOpen(True)
            Trace("cog door open_state before=" + before + " after=" + cogDoor.GetOpenState())
        else
            Trace("cog door " + VaultPlugin + ":" + CogDoorId + " does not resolve")
        endif
        AdvanceTo(30)
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
    int button = ExitMessage.Show()
    Trace("elevator prompt button=" + button)
    if button == 0
        Surface(player)
    endif
EndFunction

Function Surface(Actor player)
{The ride up, first half: MoveTo the core anchor, which puts the player at its LOCAL position. FinishSurface places
 them on the merged arrival on a later tick.}
    ObjectReference anchor = Game.GetFormFromFile(ExitAnchorId, CorePlugin) as ObjectReference
    if anchor == None
        Trace("exit anchor " + CorePlugin + ":" + ExitAnchorId + " does not resolve")
        return
    endif
    player.MoveTo(anchor, 0.0, 0.0, 0.0, True, False)
    surfaceMoves += 1
    surfaceMovedAt = Utility.GetCurrentRealTime()
    Trace("surface moveto pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " world=" + player.GetWorldSpace() + " moves=" + surfaceMoves)
EndFunction

Function FinishSurface(Actor player)
{The ride up, second half: SetPosition on the merged arrival, a tick after the MoveTo at the earliest and once the player
 is outside with their 3D loaded (the load door's MoveTo, wait, SetPosition order: FO4SF_LoadDoor's SettleSeconds,
 PASS on the Super Duper Mart round trip, 17 Oct). Run 3 of 28 Oct called it in the MoveTo's own tick: the game ignored
 it, the player stood at the anchor's local spot until the fall check's SetPosition 5.7 s later moved them. A SetPosition
 that does not take (the position read back is more than 5 m off) is tried again next tick, SurfaceTries in all, then
 stage 40 goes on and CheckLanding decides. Still inside SurfaceWait seconds after the MoveTo: one more MoveTo, then the
 elevator prompt again. Outside but not loaded yet: it waits.}
    if player.IsInInterior()
        if Utility.GetCurrentRealTime() - surfaceMovedAt > SurfaceWait
            if surfaceMoves < 2
                Trace("surface still inside " + SurfaceWait + " s after the moveto: moving again")
                Surface(player)
            else
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
    float x = ArrivalX + MergeOffsetX
    float y = ArrivalY + MergeOffsetY
    player.SetPosition(x, y, ArrivalZ)
    player.SetAngle(0.0, 0.0, ArrivalHeading)
    surfaceSets += 1
    float dx = player.GetPositionX() - x
    float dy = player.GetPositionY() - y
    bool ok = dx * dx + dy * dy <= 25.0
    Trace("surface setposition ok=" + ok + " set=" + surfaceSets + " pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " target=" + x + " " + y + " " + ArrivalZ)
    if ok || surfaceSets >= SurfaceTries
        surfaceMovedAt = 0.0
        arrivedAt = Utility.GetCurrentRealTime()
        AdvanceTo(40)
    endif
EndFunction

Function CheckLanding(Actor player)
{Three seconds after the arrival: a player below the arrival by FallDrop fell (the surface elevator platform may not be
 solid in the core) and goes to the fallback, the map marker's spot on the ground; then the quest completes.}
    if Utility.GetCurrentRealTime() - arrivedAt < 3.0
        return
    endif
    float z = player.GetPositionZ()
    if z < ArrivalZ - FallDrop
        player.SetPosition(FallbackX + MergeOffsetX, FallbackY + MergeOffsetY, FallbackZ + 1.0)
        Trace("fell z=" + z + ": fallback pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ())
    else
        Trace("landed z=" + z)
    endif
    AdvanceTo(200)
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
