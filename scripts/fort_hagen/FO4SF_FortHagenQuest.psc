Scriptname FO4SF_FortHagenQuest extends Quest
{Runtime controller for Fort Hagen's two elevator systems and exterior roof gate
 (docs/mission/fort-hagen-elevators.md). Resolves FO4Port.esm and FO4TerrainCore.esm
 records at run time so FO4SFFortHagen.esm masters Starfield.esm only.}

Form Property XMarkerBase Auto Const Mandatory
int Property Anchor01Id Auto Const Mandatory
int Property UpperCall01Id Auto Const Mandatory
int Property UpperCall01BaseId Auto Const Mandatory
int Property LowerCall01Id Auto Const Mandatory
int Property InnerPanel01Id Auto Const Mandatory
int Property InnerPanel01BaseId Auto Const Mandatory
int Property UpperDoor01Id Auto Const Mandatory
int Property LowerDoor01Id Auto Const Mandatory
int Property OuterDoor01BaseId Auto Const Mandatory
int Property InnerDoor01Id Auto Const Mandatory
int Property InnerDoor01BaseId Auto Const Mandatory
int Property Planks01Id Auto Const Mandatory
int Property Planks01BaseId Auto Const Mandatory
int Property BlockerDoor01Id Auto Const Mandatory
int Property BlockerDoor01BaseId Auto Const Mandatory
int Property BlockerBoards01Id Auto Const Mandatory
int Property BlockerBoards01BaseId Auto Const Mandatory
int Property MaintSwitch01Id Auto Const Mandatory
int Property MaintSwitch01BaseId Auto Const Mandatory
float Property UpperLandingX Auto Const Mandatory
float Property UpperLandingY Auto Const Mandatory
float Property UpperLandingZ Auto Const Mandatory
float Property LowerCarX Auto Const Mandatory
float Property LowerCarY Auto Const Mandatory
float Property LowerCarZ Auto Const Mandatory

int Property Marker02Id Auto Const Mandatory
int Property Call02Id Auto Const Mandatory
int Property Call02BaseId Auto Const Mandatory
int Property Panel02Id Auto Const Mandatory
int Property Panel02BaseId Auto Const Mandatory
int Property OuterDoor02Id Auto Const Mandatory
int Property OuterDoor02BaseId Auto Const Mandatory
int Property LoadDoor02Id Auto Const Mandatory
int Property LoadDoor02BaseId Auto Const Mandatory

int Property RoofMarkerId Auto Const Mandatory
int Property RoofCallId Auto Const Mandatory
int Property RoofCallBaseId Auto Const Mandatory
int Property RoofPanelId Auto Const Mandatory
int Property RoofPanelBaseId Auto Const Mandatory
int Property RoofOuterDoorId Auto Const Mandatory
int Property RoofOuterDoorBaseId Auto Const Mandatory
int Property RoofLoadDoorId Auto Const Mandatory
int Property RoofLoadDoorBaseId Auto Const Mandatory
int Property RoofGateId Auto Const Mandatory
int Property RoofGateBaseId Auto Const Mandatory
int Property RoofTermId Auto Const Mandatory
int Property RoofTermBaseId Auto Const Mandatory
float Property RoofCenterX Auto Const Mandatory
float Property RoofCenterY Auto Const Mandatory
float Property RoofCenterZ Auto Const Mandatory
float Property RoofGateX Auto Const Mandatory
float Property RoofGateY Auto Const Mandatory
float Property RoofGateZ Auto Const Mandatory
float Property RoofTermX Auto Const Mandatory
float Property RoofTermY Auto Const Mandatory
float Property RoofTermZ Auto Const Mandatory
float Property RoofCallX Auto Const Mandatory
float Property RoofCallY Auto Const Mandatory
float Property RoofCallZ Auto Const Mandatory
float Property RoofPanelX Auto Const Mandatory
float Property RoofPanelY Auto Const Mandatory
float Property RoofPanelZ Auto Const Mandatory
float Property RoofOuterDoorX Auto Const Mandatory
float Property RoofOuterDoorY Auto Const Mandatory
float Property RoofOuterDoorZ Auto Const Mandatory
float Property RoofLoadDoorX Auto Const Mandatory
float Property RoofLoadDoorY Auto Const Mandatory
float Property RoofLoadDoorZ Auto Const Mandatory

string Property PortPlugin = "FO4Port.esm" Auto Const
string Property CorePlugin = "FO4TerrainCore.esm" Auto Const
string Property CoreFallbackPlugin = "FO4TerrainCore_Mars.esm" Auto Const
float Property PollSeconds = 1.5 Auto Const
float Property RoofRadius = 80.0 Auto Const
float Property SearchRadius = 2.5 Auto Const
float Property DoorOpenWaitSeconds = 0.6 Auto Const
float Property ShaftRideSeconds = 1.0 Auto Const

string LogName = "fo4sf_forthagen"
int activeZone = 0
bool busy = False
bool roofGateOpened = False

ObjectReference fh01UpperCall
ObjectReference fh01LowerCall
ObjectReference fh01InnerPanel
ObjectReference fh01UpperDoor
ObjectReference fh01LowerDoor
ObjectReference fh01InnerDoor

ObjectReference fh02Call
ObjectReference fh02Panel
ObjectReference fh02OuterDoor
ObjectReference fh02LoadDoor

ObjectReference roofCall
ObjectReference roofPanel
ObjectReference roofOuterDoor
ObjectReference roofLoadDoor
ObjectReference roofGate
ObjectReference roofTerm

Function Trace(string msg)
    Debug.OpenUserLog(LogName)
    Debug.TraceUser(LogName, "FO4SF_FORTHAGEN rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction

Event OnQuestInit()
    Trace("init quest=" + (self as Quest))
    Actor p = Game.GetPlayer()
    if p != None
        RegisterForRemoteEvent(p, "OnPlayerLoadGame")
    endif
    activeZone = 0
    busy = False
    StartTimer(PollSeconds, 1)
EndEvent

Event Actor.OnPlayerLoadGame(Actor akSender)
    Trace("load_game roof_gate_opened=" + roofGateOpened)
    ClearBindings()
    activeZone = 0
    busy = False
    StartTimer(PollSeconds, 1)
EndEvent

string Function ActiveCorePlugin()
    if Game.GetFormFromFile(RoofMarkerId, CorePlugin) != None
        return CorePlugin
    endif
    if Game.GetFormFromFile(RoofMarkerId, CoreFallbackPlugin) != None
        return CoreFallbackPlugin
    endif
    return ""
EndFunction

ObjectReference Function ResolveRef(string pluginName, int refId, int baseId, float wantX, float wantY, float wantZ, bool allowClosest)
    ObjectReference direct = Game.GetFormFromFile(refId, pluginName) as ObjectReference
    if direct != None
        return direct
    endif
    if allowClosest && baseId > 0
        Form baseForm = Game.GetFormFromFile(baseId, pluginName)
        if baseForm != None
            return Game.FindClosestReferenceOfType(baseForm, wantX, wantY, wantZ, SearchRadius)
        endif
    endif
    return None
EndFunction

ObjectReference Function BindActivate(ObjectReference current, ObjectReference nextRef)
    if current == nextRef
        return current
    endif
    if current != None
        UnregisterForRemoteEvent(current, "OnActivate")
    endif
    if nextRef != None
        RegisterForRemoteEvent(nextRef, "OnActivate")
    endif
    return nextRef
EndFunction

Function ClearBindings()
    fh01UpperCall = BindActivate(fh01UpperCall, None)
    fh01LowerCall = BindActivate(fh01LowerCall, None)
    fh01InnerPanel = BindActivate(fh01InnerPanel, None)
    fh01UpperDoor = BindActivate(fh01UpperDoor, None)
    fh01LowerDoor = None
    fh01InnerDoor = None
    fh02Call = BindActivate(fh02Call, None)
    fh02Panel = BindActivate(fh02Panel, None)
    fh02OuterDoor = None
    fh02LoadDoor = None
    roofCall = BindActivate(roofCall, None)
    roofPanel = BindActivate(roofPanel, None)
    roofGate = BindActivate(roofGate, None)
    roofTerm = BindActivate(roofTerm, None)
    roofOuterDoor = None
    roofLoadDoor = None
EndFunction

int Function DetectZone(Actor player)
    Cell pCell = player.GetParentCell()
    if pCell == None
        return 0
    endif
    ObjectReference a01 = Game.GetFormFromFile(Anchor01Id, PortPlugin) as ObjectReference
    if a01 != None && a01.GetParentCell() == pCell
        return 1
    endif
    ObjectReference m02 = Game.GetFormFromFile(Marker02Id, PortPlugin) as ObjectReference
    if m02 != None && m02.GetParentCell() == pCell
        return 2
    endif
    if !pCell.IsInterior() && ActiveCorePlugin() != ""
        float dx = player.GetPositionX() - RoofCenterX
        float dy = player.GetPositionY() - RoofCenterY
        if (dx * dx + dy * dy) <= (RoofRadius * RoofRadius)
            return 3
        endif
    endif
    return 0
EndFunction

bool Function DisablePortBlocker(int refId, int baseId, float x, float y, float z)
    ObjectReference r = ResolveRef(PortPlugin, refId, baseId, x, y, z, True)
    if r != None && !r.IsDisabled()
        r.Disable()
        return True
    endif
    return r != None && r.IsDisabled()
EndFunction

Function SyncZone01()
    bool planksOff = DisablePortBlocker(Planks01Id, Planks01BaseId, -10.971, 67.429, 5.029)
    bool doorOff = DisablePortBlocker(BlockerDoor01Id, BlockerDoor01BaseId, -10.784, 54.720, -2.457)
    bool boardsOff = DisablePortBlocker(BlockerBoards01Id, BlockerBoards01BaseId, -8.927, 54.815, -2.239)
    bool maintOff = DisablePortBlocker(MaintSwitch01Id, MaintSwitch01BaseId, -9.829, 67.886, -2.946)

    fh01UpperCall = BindActivate(fh01UpperCall, ResolveRef(PortPlugin, UpperCall01Id, UpperCall01BaseId, -11.986, 67.419, 4.905, True))
    fh01LowerCall = BindActivate(fh01LowerCall, ResolveRef(PortPlugin, LowerCall01Id, UpperCall01BaseId, -9.921, 67.429, -2.405, True))
    fh01InnerPanel = BindActivate(fh01InnerPanel, ResolveRef(PortPlugin, InnerPanel01Id, InnerPanel01BaseId, -11.882, 68.037, -2.405, True))
    fh01UpperDoor = BindActivate(fh01UpperDoor, ResolveRef(PortPlugin, UpperDoor01Id, OuterDoor01BaseId, -10.971, 67.657, 3.657, True))
    fh01LowerDoor = ResolveRef(PortPlugin, LowerDoor01Id, OuterDoor01BaseId, -10.971, 67.657, -3.657, True)
    fh01InnerDoor = ResolveRef(PortPlugin, InnerDoor01Id, InnerDoor01BaseId, -10.971, 69.486, -3.657, True)

    if activeZone != 1
        Trace("fh01_ready planks=" + planksOff + " blocker_door=" + doorOff + " boards=" + boardsOff + " maint=" + maintOff + " upper_call=" + (fh01UpperCall != None) + " panel=" + (fh01InnerPanel != None))
    endif
EndFunction

Function SyncZone02()
    fh02Call = BindActivate(fh02Call, ResolveRef(PortPlugin, Call02Id, Call02BaseId, 20.796, 2.502, -9.554, True))
    fh02Panel = BindActivate(fh02Panel, ResolveRef(PortPlugin, Panel02Id, Panel02BaseId, 21.410, 2.314, -9.554, True))
    fh02OuterDoor = ResolveRef(PortPlugin, OuterDoor02Id, OuterDoor02BaseId, 21.029, 1.371, -10.971, True)
    fh02LoadDoor = ResolveRef(PortPlugin, LoadDoor02Id, LoadDoor02BaseId, 22.857, 1.371, -10.971, True)
    if activeZone != 2
        Trace("fh02_ready call=" + (fh02Call != None) + " panel=" + (fh02Panel != None) + " outer=" + (fh02OuterDoor != None) + " load_door=" + (fh02LoadDoor != None))
    endif
EndFunction

Function SyncZoneRoof()
    string coreName = ActiveCorePlugin()
    if coreName == ""
        return
    endif
    roofCall = BindActivate(roofCall, ResolveRef(coreName, RoofCallId, RoofCallBaseId, RoofCallX, RoofCallY, RoofCallZ, True))
    roofPanel = BindActivate(roofPanel, ResolveRef(coreName, RoofPanelId, RoofPanelBaseId, RoofPanelX, RoofPanelY, RoofPanelZ, True))
    roofOuterDoor = ResolveRef(coreName, RoofOuterDoorId, RoofOuterDoorBaseId, RoofOuterDoorX, RoofOuterDoorY, RoofOuterDoorZ, True)
    roofLoadDoor = ResolveRef(coreName, RoofLoadDoorId, RoofLoadDoorBaseId, RoofLoadDoorX, RoofLoadDoorY, RoofLoadDoorZ, True)
    roofGate = BindActivate(roofGate, ResolveRef(coreName, RoofGateId, RoofGateBaseId, RoofGateX, RoofGateY, RoofGateZ, True))
    roofTerm = BindActivate(roofTerm, ResolveRef(coreName, RoofTermId, RoofTermBaseId, RoofTermX, RoofTermY, RoofTermZ, True))
    if roofGateOpened && roofGate != None && !roofGate.IsDisabled()
        roofGate.Disable()
    endif
    if activeZone != 3
        Trace("fh_roof_ready gate=" + (roofGate != None) + " term=" + (roofTerm != None) + " call=" + (roofCall != None) + " load_door=" + (roofLoadDoor != None))
    endif
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID != 1
        return
    endif
    Actor player = Game.GetPlayer()
    if player != None && !busy
        int z = DetectZone(player)
        if z != activeZone && activeZone != 0
            ClearBindings()
        endif
        if z == 1
            SyncZone01()
        elseif z == 2
            SyncZone02()
        elseif z == 3
            SyncZoneRoof()
        endif
        activeZone = z
    endif
    StartTimer(PollSeconds, 1)
EndEvent

Function OpenDoorSafe(ObjectReference doorRef)
    if doorRef != None
        int st = doorRef.GetOpenState()
        if st == 3 || st == 4
            doorRef.SetOpen(True)
        endif
    endif
EndFunction

Function CloseDoorSafe(ObjectReference doorRef)
    if doorRef != None
        int st = doorRef.GetOpenState()
        if st == 1 || st == 2
            doorRef.SetOpen(False)
        endif
    endif
EndFunction

Function RideDown01(Actor player)
    busy = True
    Trace("fh01_ride dir=down")
    OpenDoorSafe(fh01UpperDoor)
    Utility.Wait(DoorOpenWaitSeconds)
    OpenDoorSafe(fh01InnerDoor)
    OpenDoorSafe(fh01LowerDoor)
    player.SetPosition(LowerCarX, LowerCarY, LowerCarZ)
    player.SetAngle(0.0, 0.0, 180.0)
    CloseDoorSafe(fh01UpperDoor)
    Trace("fh01_arrived floor=lower pos=(" + player.GetPositionX() + "," + player.GetPositionY() + "," + player.GetPositionZ() + ")")
    busy = False
EndFunction

Function RideUp01(Actor player)
    busy = True
    Trace("fh01_ride dir=up")
    CloseDoorSafe(fh01InnerDoor)
    CloseDoorSafe(fh01LowerDoor)
    Utility.Wait(ShaftRideSeconds)
    OpenDoorSafe(fh01UpperDoor)
    player.SetPosition(UpperLandingX, UpperLandingY, UpperLandingZ)
    player.SetAngle(0.0, 0.0, 180.0)
    Utility.Wait(DoorOpenWaitSeconds)
    CloseDoorSafe(fh01UpperDoor)
    Trace("fh01_arrived floor=upper pos=(" + player.GetPositionX() + "," + player.GetPositionY() + "," + player.GetPositionZ() + ")")
    busy = False
EndFunction

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    Actor player = Game.GetPlayer()
    if player == None || akActionRef != player || busy
        return
    endif
    if akSender == fh01UpperCall || akSender == fh01UpperDoor
        RideDown01(player)
    elseif akSender == fh01LowerCall
        OpenDoorSafe(fh01LowerDoor)
        OpenDoorSafe(fh01InnerDoor)
        Trace("fh01_lower_open")
    elseif akSender == fh01InnerPanel
        RideUp01(player)
    elseif akSender == fh02Call
        OpenDoorSafe(fh02OuterDoor)
        Trace("fh02_outer_open")
    elseif akSender == fh02Panel
        busy = True
        OpenDoorSafe(fh02OuterDoor)
        Trace("fh02_panel_dispatch")
        if fh02LoadDoor != None
            fh02LoadDoor.Activate(player)
        endif
        busy = False
    elseif akSender == roofTerm || akSender == roofGate
        roofGateOpened = True
        if roofGate != None && !roofGate.IsDisabled()
            roofGate.Disable()
        endif
        Trace("fh_roof_gate_opened via=" + (akSender == roofTerm))
    elseif akSender == roofCall
        OpenDoorSafe(roofOuterDoor)
        Trace("fh_roof_outer_open")
    elseif akSender == roofPanel
        busy = True
        OpenDoorSafe(roofOuterDoor)
        Trace("fh_roof_panel_dispatch")
        if roofLoadDoor != None
            roofLoadDoor.Activate(player)
        endif
        busy = False
    endif
EndEvent
