Scriptname FO4SF_NewGameQuest extends Quest
{A Fallout 4 new game in Starfield (fo4-to-starfield, docs/newgame/vault111-start.md): on a NEW game only, holds off
 Starfield's opening quests, puts the player in front of their cryo pod in the converted Vault 111 (FO4Port.esm), opens
 the cog door from its console, and takes the player up the elevator onto the Commonwealth at Fallout 4's surface
 arrival. Stages: 1 stood down (not a new game), 10 in the vault, 20 looks done, 30 cog door opened, 40 on the surface,
 200 complete. Every step and a status line every 5 s go to the user log "fo4sf_newgame"
 (My Games\Starfield\Logs\Script\User\fo4sf_newgame.0.log), the evidence of a run.
 The places come from other plugins by their plugin-local form ids (the FO4SF_LoadDoor contract): this plugin has no
 master but Starfield.esm, so a rebuilt port or core never needs this plugin rebuilt while those ids stay (stable ids).}

GlobalVariable Property GameDaysPassed Auto Const Mandatory
{Starfield.esm 000039, 0 on a new game. Part of the new-game guard (IsNewGame).}

Quest[] Property HoldOff Auto Const Mandatory
{Starfield start quests stopped on a new game before the player is moved (the writer's --hold list, default MQ00 and
 MQ101: the main-quest start and the opening). Each is stopped only if it runs; each stop is logged.}

Message Property ExitMessage Auto Const Mandatory
{The elevator prompt (FO4SFNewGame.esm 0x801): button 0 rides up, button 1 stays.}

string Property VaultPlugin = "FO4Port.esm" Auto Const
int Property VaultAnchorId Auto Const Mandatory
{A persistent reference in FO4Port_Vault111Cryo (the cell's COC marker): MoveTo it puts the player in the vault.}
float Property AnchorX Auto Const Mandatory
float Property AnchorY Auto Const Mandatory
float Property AnchorZ Auto Const Mandatory
{The anchor's position in the cell (metres, FO4 position / 70, as the port writes it).}
float Property PodX Auto Const Mandatory
float Property PodY Auto Const Mandatory
float Property PodZ Auto Const Mandatory
float Property PodHeading Auto Const Mandatory
{Where the player stands up from their pod (Fallout 4's pod position plus a step out of it; heading in degrees).}
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
 the reference's LOCAL position (persistent references are not moved by the merge), SetPosition then places them.}
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

float Property MaxNewGameDays = 0.25 Auto Const
{The guard: a new game has passed less than this many game days...}
int Property MaxNewGameLevel = 1 Auto Const
{...and the player is at most this level. An existing save that gains this plugin stands down (stage 1).}
float Property ConsoleRadius = 2.5 Auto Const
float Property PlatformRadius = 2.5 Auto Const
float Property FallDrop = 3.0 Auto Const
{A landing this far below its target z (m) counts as a fall: the player is put on the fallback spot.}
float Property LooksWait = 120.0 Auto Const
{Seconds stage 10 waits for the looks script (FO4SF_NewGameLooks, optional) to set stage 20 before moving on.}

string LogName = "fo4sf_newgame"
int ticks = 0
float startedAt = 0.0
float arrivedAt = 0.0
bool asked = false
int applied = 0

Event OnQuestInit()
    Debug.OpenUserLog(LogName)
    Trace("init holdoff=" + HoldOff.Length + " vault=" + VaultPlugin + ":" + VaultAnchorId + " core=" + CorePlugin + ":" + ExitAnchorId)
    StartTimer(1.0, 1)
EndEvent

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
            StartTimer(1.0, 1)                               ; the game is still loading
            return
        endif
        float days = GameDaysPassed.GetValue()
        int level = player.GetLevel()
        if !IsNewGame(days, level)
            Trace("not a new game: days=" + days + " level=" + level + ": standing down")
            AdvanceTo(1)
            Stop()
            return
        endif
        HoldOffStart()
        if !EnterVault(player)
            StartTimer(1.0, 1)                               ; the port is not loaded yet or the move missed: retried
            return
        endif
        AdvanceTo(10)
        startedAt = Utility.GetCurrentRealTime()
    elseif stage == 10
        if Utility.GetCurrentRealTime() - startedAt > LooksWait
            Trace("looks: no stage 20 after " + LooksWait + " s; going on")
            AdvanceTo(20)
        endif
    elseif stage == 20 || stage == 30
        InVault(player, stage)
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
{The new-game guard (make_newgame.py is_new_game is the same rule, tested there).}
    return days < MaxNewGameDays && level <= MaxNewGameLevel
EndFunction

Function HoldOffStart()
    int i = 0
    while i < HoldOff.Length
        Quest q = HoldOff[i]
        if q != None && q.IsRunning()
            q.Stop()
            Trace("held off " + q + " running_after=" + q.IsRunning())
        else
            Trace("not running " + q)
        endif
        i += 1
    endwhile
EndFunction

bool Function EnterVault(Actor player)
{MoveTo the vault's anchor with the pod's offset (the verified MoveTo form of the mission and FO4SF_Probe), then the
 pod's heading. False when the anchor does not resolve or the player did not land in the anchor's cell.}
    ObjectReference anchor = Game.GetFormFromFile(VaultAnchorId, VaultPlugin) as ObjectReference
    if anchor == None
        Trace("vault anchor " + VaultPlugin + ":" + VaultAnchorId + " does not resolve")
        return false
    endif
    player.MoveTo(anchor, PodX - AnchorX, PodY - AnchorY, PodZ - AnchorZ, False, False)
    player.SetAngle(0.0, 0.0, PodHeading)
    bool ok = player.GetParentCell() == anchor.GetParentCell()
    Trace("enter vault ok=" + ok + " pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " target=" + PodX + " " + PodY + " " + PodZ + " cell=" + player.GetParentCell())
    if ok
        Debug.Notification("Vault 111")
    endif
    return ok
EndFunction

Function InVault(Actor player, int stage)
    if !player.IsInInterior()
        return
    endif
    if stage == 20 && CogDoorId > 0 && Near(player, ConsoleX, ConsoleY, ConsoleZ, ConsoleRadius)
        ObjectReference door = Game.GetFormFromFile(CogDoorId, VaultPlugin) as ObjectReference
        if door != None
            int before = door.GetOpenState()
            door.SetOpen(True)
            Trace("cog door open_state before=" + before + " after=" + door.GetOpenState())
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
{The ride up: MoveTo the core anchor, then SetPosition on the merged arrival (FO4SF_LoadDoor's UseDestinationPosition
 form, PASS on the Super Duper Mart round trip, 17 Oct).}
    ObjectReference anchor = Game.GetFormFromFile(ExitAnchorId, CorePlugin) as ObjectReference
    if anchor == None
        Trace("exit anchor " + CorePlugin + ":" + ExitAnchorId + " does not resolve")
        return
    endif
    player.MoveTo(anchor, 0.0, 0.0, 0.0, True, False)
    Trace("surface moveto pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " world=" + player.GetWorldSpace())
    player.SetPosition(ArrivalX + MergeOffsetX, ArrivalY + MergeOffsetY, ArrivalZ)
    player.SetAngle(0.0, 0.0, ArrivalHeading)
    Trace("surface setposition pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " target=" + (ArrivalX + MergeOffsetX) + " " + (ArrivalY + MergeOffsetY) + " " + ArrivalZ)
    arrivedAt = Utility.GetCurrentRealTime()
    AdvanceTo(40)
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
