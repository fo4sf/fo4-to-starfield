Scriptname FO4SF_R11P1Quest extends Quest
{Round 11 Probe P1 helper quest (Museum of Freedom interior, dynamic exterior doors, basement gate, NAVM raider climb, status log).

Zero WRLD/PNDT overrides: ExtFrontInDoor (0x04000810) and ExtRoofInDoor (0x04000813) start in a
probe-owned holding interior cell (0x0400080F) and are relocated dynamically onto MarsPlanetWorld
whenever the player is outdoors within 350 m of Concord.

Triggers (in-world E-activation OR P3-clean .txt batch files using runtime hex FormID):
  - Activate GateActivator in basement OR stage 10 (bat p1b): resolves persistent BasementGate
    (FO4Port.esm:0x00EDF0 via Game.GetFormFromFile), unlocks and opens once without ever relocking;
    logs FO4SF_R11P1 basement_gate opened=true.
  - Activate RaiderTrigger on 3F OR stage 20 (bat p1k): synchronously enables GroundRaider
    (FO4ActorRaider.esm:0xF04800, InitiallyDisabled until triggered), waits for 3D load, sets
    hostile Aggression/Confidence + hides spacesuit, places on ground-floor NAVM 0x0100EFA8,
    starts combat against the player on 3F, and logs 15 periodic XYZ/Z telemetry ticks (30 s).
  - Stage 30 (bat p1q): syncs exterior doors if outdoors and logs a full state snapshot
    (cell, interior flag, worldspace, player XYZ, gate state, raider state) to fo4sf_r11p1.0.log.
}

Group References
    ObjectReference Property GateActivator Auto
    {Persistent basement terminal/switch activator in FO4Port_ConcordMuseum01.}

    string Property PortPlugin = "FO4Port.esm" Auto
    {Plugin owning persistent basement security gate.}

    int Property BasementGateLocalId = 0 Auto
    {Local FormID (0x00EDF0 via VMAD) of persistent basement security gate in PortPlugin.}

    int Property BasementTerminalLocalId = 0x00E35E Auto
    {Local FormID (0x00E35E) of persistent FO4Port ConcordMuseumBasementTerminal linked to BasementGate via XLKR.}

    int Property MuseumCellLocalId = 0x00E2F4 Auto
    {Local FormID (0x00E2F4) of FO4Port_ConcordMuseum01 for interior-only batch guards.}

    ObjectReference Property ExtFrontInDoor Auto
    {Persistent Museum front entry door activator authored in holding cell 0x0400080F.}

    ObjectReference Property ExtRoofInDoor Auto
    {Persistent Museum 3F roof entry door activator authored in holding cell 0x0400080F.}

    ObjectReference Property RaiderTrigger Auto
    {Persistent 3F activator in FO4Port_ConcordMuseum01 to start the raider climb probe with E.}

    Actor Property GroundRaider Auto
    {InitiallyDisabled hostile ground-floor raider (FO4ActorRaider.esm:0xF04800) on Museum NAVM 0x0100EFA8.}

    ActorValue Property HideSpacesuitAV Auto
    {Starfield.esm:0x000B120E ActorShouldForceHideSpacesuit_AV bound via VMAD.}
EndGroup

Group ExteriorTargets
    float Property ExtFrontX = -2010.69 Auto
    float Property ExtFrontY = -1698.04 Auto
    float Property ExtFrontZ = 89.26 Auto
    float Property ExtFrontRotZ = 130.0 Auto
    float Property ExtRoofX = -1991.27 Auto
    float Property ExtRoofY = -1722.57 Auto
    float Property ExtRoofZ = 97.42 Auto
    float Property ExtRoofRotZ = 128.97 Auto
    float Property ConcordSyncRadius = 350.0 Auto
EndGroup

Group Logging
    bool Property EnableLog = true Auto
    string Property LogName = "fo4sf_r11p1" Auto
EndGroup

bool started = false
bool gateOpened = false
int navTrackTicks = 0
int navTrackMaxTicks = 15
int TIMER_RAIDER_NAV = 1
int TIMER_EXT_SYNC = 2

Event OnInit()
    EnsureStarted("on_init")
EndEvent

Event OnQuestInit()
    EnsureStarted("quest_init")
EndEvent

Event OnQuestStarted()
    EnsureStarted("quest_started")
EndEvent

Function EnsureStarted(string sourceTag)
    RegisterHooks()
    if !started
        started = true
        LogSnapshot("init")
    else
        LogSnapshot(sourceTag)
    endif
    HideInteriorStaticDoors()
    SyncExteriorDoors(sourceTag)
    StartTimer(2.0, TIMER_EXT_SYNC)
EndFunction

Function HandleLoadGame()
    RegisterHooks()
    if gateOpened
        ObjectReference gate = ResolveBasementGate()
        if gate != None
            ; Ensure opened gate stays unlocked across save/quit/load!
            gate.SetLockLevel(0)
            gate.Lock(false, false)
        endif
    endif
    HideInteriorStaticDoors()
    LogSnapshot("load_game")
    SyncExteriorDoors("load_game")
    StartTimer(2.0, TIMER_EXT_SYNC)
EndFunction

Function HideInteriorStaticDoors()
    if PortPlugin == ""
        return
    endif
    ObjectReference staticFront = Game.GetFormFromFile(0x00EDEC, PortPlugin) as ObjectReference
    if staticFront != None && !staticFront.IsDisabled()
        staticFront.DisableNoWait(false)
    endif
    ObjectReference staticRoof = Game.GetFormFromFile(0x00EDF5, PortPlugin) as ObjectReference
    if staticRoof != None && !staticRoof.IsDisabled()
        staticRoof.DisableNoWait(false)
    endif
EndFunction

Function HideOverlappingCoreStatic(ObjectReference doorRef, int coreStaticLocalId)
    if doorRef == None || coreStaticLocalId <= 0
        return
    endif
    Form statBase = Game.GetFormFromFile(coreStaticLocalId, "FO4TerrainCore.esm")
    if statBase == None
        return
    endif
    ObjectReference overlap = Game.FindClosestReferenceOfTypeFromRef(statBase, doorRef, 3.0)
    if overlap != None && overlap != doorRef && !overlap.IsDisabled()
        overlap.DisableNoWait(false)
    endif
EndFunction

Function RegisterHooks()
    Actor player = Game.GetPlayer()
    if player != None
        RegisterForRemoteEvent(player, "OnPlayerLoadGame")
    endif
    if GateActivator != None
        RegisterForRemoteEvent(GateActivator, "OnActivate")
    endif
    ObjectReference termRef = ResolveBasementTerminal()
    if termRef != None
        RegisterForRemoteEvent(termRef, "OnActivate")
        RegisterForRemoteEvent(termRef, "OnLockStateChanged")
    endif
    ObjectReference gateRef = ResolveBasementGate()
    if gateRef != None
        RegisterForRemoteEvent(gateRef, "OnActivate")
        RegisterForRemoteEvent(gateRef, "OnLockStateChanged")
    endif
    if RaiderTrigger != None
        RegisterForRemoteEvent(RaiderTrigger, "OnActivate")
    endif
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    HandleLoadGame()
EndEvent

Event ObjectReference.OnLockStateChanged(ObjectReference akSender)
    ObjectReference gateRef = ResolveBasementGate()
    if gateRef != None && akSender == gateRef && !gateRef.IsLocked() && !gateOpened
        OpenBasementGate("gate_lock_changed")
    endif
EndEvent

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    ObjectReference termRef = ResolveBasementTerminal()
    ObjectReference gateRef = ResolveBasementGate()
    if akSender == GateActivator
        OpenBasementGate("terminal_activate")
    elseif termRef != None && akSender == termRef
        if !termRef.IsLocked()
            OpenBasementGate("port_terminal_activate")
        endif
    elseif gateRef != None && akSender == gateRef
        if !gateRef.IsLocked() && !gateOpened
            OpenBasementGate("gate_picked_activate")
        endif
    elseif akSender == RaiderTrigger
        StartRaiderNavTest()
    endif
EndEvent

bool Function IsPlayerInMuseum(Actor player)
    if player == None || !player.IsInInterior()
        return false
    endif
    Cell cur = player.GetParentCell()
    if cur == None || PortPlugin == "" || MuseumCellLocalId <= 0
        return false
    endif
    Cell museumCell = Game.GetFormFromFile(MuseumCellLocalId, PortPlugin) as Cell
    return (museumCell != None && cur == museumCell)
EndFunction

Event OnStageSet(int auiStageID, int auiItemID)
    Actor player = Game.GetPlayer()
    if auiStageID == 10
        if !IsPlayerInMuseum(player)
            Log("FO4SF_R11P1 batch_guard blocked=stage_10 reason=outside_museum_run_p1f_first")
            Debug.Notification("FO4SF P1: Interior-only! Enter Museum (bat p1f) first.")
            return
        endif
        player.SetPosition(-14.38, -0.10, -3.32)
        player.SetAngle(0.0, 0.0, 110.0)
        OpenBasementGate("stage_10")
    elseif auiStageID == 20
        if !IsPlayerInMuseum(player)
            Log("FO4SF_R11P1 batch_guard blocked=stage_20 reason=outside_museum_run_p1f_first")
            Debug.Notification("FO4SF P1: Interior-only! Enter Museum (bat p1f) first.")
            return
        endif
        player.SetPosition(-4.00, 7.50, 9.15)
        player.SetAngle(0.0, 0.0, 180.0)
        StartRaiderNavTest()
    elseif auiStageID == 30
        SyncExteriorDoors("stage_30")
        LogSnapshot("stage_30")
    endif
EndEvent

ObjectReference Function ResolveBasementGate()
    if PortPlugin != "" && BasementGateLocalId > 0
        return Game.GetFormFromFile(BasementGateLocalId, PortPlugin) as ObjectReference
    endif
    return None
EndFunction

ObjectReference Function ResolveBasementTerminal()
    if PortPlugin != "" && BasementTerminalLocalId > 0
        return Game.GetFormFromFile(BasementTerminalLocalId, PortPlugin) as ObjectReference
    endif
    return None
EndFunction

Function SyncExteriorDoors(string sourceTag)
    Actor player = Game.GetPlayer()
    if player == None || player.IsInInterior()
        return
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float pz = player.GetPositionZ()
    float dx = px - ExtFrontX
    float dy = py - ExtFrontY
    if dx * dx + dy * dy > ConcordSyncRadius * ConcordSyncRadius
        return
    endif
    PlaceExteriorDoor(player, ExtFrontInDoor, "p1_front_in", ExtFrontX, ExtFrontY, ExtFrontZ, ExtFrontRotZ, 0x0019E6, px, py, pz, sourceTag)
    PlaceExteriorDoor(player, ExtRoofInDoor, "p1_roof_in", ExtRoofX, ExtRoofY, ExtRoofZ, ExtRoofRotZ, 0x001E75, px, py, pz, sourceTag)
EndFunction

Function PlaceExteriorDoor(Actor player, ObjectReference doorRef, string tag, float tx, float ty, float tz, float rotZDeg, int hideCoreStaticLocalId, float px, float py, float pz, string sourceTag)
    if doorRef == None
        return
    endif
    bool needMove = (doorRef.GetWorldSpace() != player.GetWorldSpace())
    if !needMove
        float ddx = doorRef.GetPositionX() - tx
        float ddy = doorRef.GetPositionY() - ty
        float ddz = doorRef.GetPositionZ() - tz
        if ddx * ddx + ddy * ddy > 2.25 || ddz > 3.0 || ddz < -3.0
            needMove = true
        endif
    endif
    if needMove
        doorRef.MoveTo(player, tx - px, ty - py, tz - pz, True, False)
        doorRef.SetPosition(tx, ty, tz)
        doorRef.SetAngle(0.0, 0.0, rotZDeg)
        Log("FO4SF_R11P1 ext_door_placed tag=" + tag + " source=" + sourceTag + " pos=" + doorRef.GetPositionX() + " " + doorRef.GetPositionY() + " " + doorRef.GetPositionZ() + " world=" + doorRef.GetWorldSpace())
    else
        doorRef.SetAngle(0.0, 0.0, rotZDeg)
    endif
    HideOverlappingCoreStatic(doorRef, hideCoreStaticLocalId)
EndFunction

Function OpenBasementGate(string sourceTag)
    ObjectReference gate = ResolveBasementGate()
    if gate == None
        Log("FO4SF_R11P1 basement_gate opened=false reason=gate_ref_missing source=" + sourceTag)
        return
    endif
    bool lockedBefore = gate.IsLocked()
    int lockLevelBefore = gate.GetLockLevel()
    if gateOpened
        gate.SetLockLevel(0)
        gate.Lock(false, false)
        Log("FO4SF_R11P1 basement_gate opened=true already_open=true source=" + sourceTag + " locked_before=" + lockedBefore + " lock_level_before=" + lockLevelBefore + " locked_after=" + gate.IsLocked() + " ref=" + gate)
        return
    endif
    ObjectReference termRef = ResolveBasementTerminal()
    if termRef != None && termRef.IsLocked()
        termRef.SetLockLevel(0)
        termRef.Lock(false, false)
    endif
    gate.SetLockLevel(0)
    gate.Lock(false, false)
    gate.SetOpen(true)
    gate.PlayGamebryoAnimation("Open", false, 0.0)
    gateOpened = true
    Log("FO4SF_R11P1 basement_gate opened=true already_open=false source=" + sourceTag + " locked_before=" + lockedBefore + " lock_level_before=" + lockLevelBefore + " locked_after=" + gate.IsLocked() + " ref=" + gate)
EndFunction

Function StartRaiderNavTest()
    Actor player = Game.GetPlayer()
    if player == None || GroundRaider == None
        Log("FO4SF_R11P1 raider_combat started=false reason=ref_missing")
        return
    endif

    ; Synchronously enable InitiallyDisabled raider and wait up to 2.0 s for 3D load before positioning/combat.
    GroundRaider.Enable(false)
    int w = 0
    while w < 20 && !GroundRaider.Is3DLoaded()
        Utility.Wait(0.1)
        w += 1
    endwhile

    if GroundRaider.IsDead()
        GroundRaider.Resurrect()
    endif
    GroundRaider.SetRestrained(false)

    ActorValue avAgg = Game.GetAggressionAV()
    if avAgg != None
        GroundRaider.SetValue(avAgg, 2.0)
    endif
    ActorValue avConf = Game.GetConfidenceAV()
    if avConf != None
        GroundRaider.SetValue(avConf, 4.0)
    endif
    if HideSpacesuitAV != None
        GroundRaider.SetValue(HideSpacesuitAV, 1.0)
    endif

    GroundRaider.SetPosition(-3.0, 0.0, 0.25)
    GroundRaider.EvaluatePackage()
    GroundRaider.StartCombat(player)
    var[] initPathArgs = new var[3]
    initPathArgs[0] = player
    initPathArgs[1] = 1.0
    initPathArgs[2] = 1.0
    GroundRaider.CallFunctionNoWait("PathToReference", initPathArgs)
    navTrackTicks = 0
    Log("FO4SF_R11P1 raider_combat started=true loaded=" + GroundRaider.Is3DLoaded() + " wait_steps=" + w + " raider=" + GroundRaider + " raider_pos=" + FormatActorPos(GroundRaider) + " player_pos=" + FormatActorPos(player) + " dist=" + GroundRaider.GetDistance(player))
    StartTimer(2.0, TIMER_RAIDER_NAV)
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_EXT_SYNC
        HideInteriorStaticDoors()
        SyncExteriorDoors("timer")
        StartTimer(2.0, TIMER_EXT_SYNC)
        return
    endif
    if aiTimerID != TIMER_RAIDER_NAV
        return
    endif
    Actor player = Game.GetPlayer()
    if player == None || GroundRaider == None
        return
    endif
    navTrackTicks += 1
    if !GroundRaider.IsDead() && IsPlayerInMuseum(player)
        GroundRaider.SetRestrained(false)
        GroundRaider.EvaluatePackage()
        if !GroundRaider.IsInCombat() || (navTrackTicks % 2) == 1
            GroundRaider.StartCombat(player)
            var[] pathArgs = new var[3]
            pathArgs[0] = player
            pathArgs[1] = 1.0
            pathArgs[2] = 1.0
            GroundRaider.CallFunctionNoWait("PathToReference", pathArgs)
        endif
    endif
    float rz = GroundRaider.GetPositionZ()
    float pz = player.GetPositionZ()
    bool climbed = (rz > 4.0)
    Log("FO4SF_R11P1 raider_nav tick=" + navTrackTicks + "/" + navTrackMaxTicks + " dead=" + GroundRaider.IsDead() + " combat=" + GroundRaider.IsInCombat() + " climbed_stairs=" + climbed + " raider_pos=" + FormatActorPos(GroundRaider) + " player_z=" + pz + " dist=" + GroundRaider.GetDistance(player))
    if navTrackTicks < navTrackMaxTicks && !GroundRaider.IsDead()
        StartTimer(2.0, TIMER_RAIDER_NAV)
    endif
EndEvent

Function LogSnapshot(string tag)
    Actor player = Game.GetPlayer()
    if player == None
        Log("FO4SF_R11P1 snapshot tag=" + tag + " player=None")
        return
    endif
    bool raiderDead = false
    if GroundRaider != None
        raiderDead = GroundRaider.IsDead()
    endif
    ObjectReference gate = ResolveBasementGate()
    bool gateLocked = false
    int gateLockLvl = -1
    if gate != None
        gateLocked = gate.IsLocked()
        gateLockLvl = gate.GetLockLevel()
    endif
    Log("FO4SF_R11P1 snapshot tag=" + tag + " cell=" + player.GetParentCell() + " interior=" + player.IsInInterior() + " world=" + player.GetWorldSpace() + " pos=" + FormatActorPos(player) + " gate_opened=" + gateOpened + " gate_locked=" + gateLocked + " gate_lock_level=" + gateLockLvl + " raider_dead=" + raiderDead)
EndFunction

string Function FormatActorPos(Actor a)
    return a.GetPositionX() + " " + a.GetPositionY() + " " + a.GetPositionZ()
EndFunction

Function Log(string msg)
    if !EnableLog
        return
    endif
    Debug.OpenUserLog(LogName)
    Debug.TraceUser(LogName, msg)
EndFunction
