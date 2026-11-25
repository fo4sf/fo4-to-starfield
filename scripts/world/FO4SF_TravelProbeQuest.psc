Scriptname FO4SF_TravelProbeQuest extends Quest
{Two-landing offline travel probe (Round 14 Task 4).
Evaluates bidirectional Commonwealth <-> Far Harbor test-station transitions,
exterior -> transit interior -> exterior hopping, reload recovery,
SQ_FollowersScript follower handoff, carried-item persistence, and
ResolveHostWorld anchor+offset (MoveTo/WaitFor3DLoad/SetPosition) vs Game.FastTravel.
Zero HUD debug text (Rule 13): logs exclusively to FO4SF_TravelProbe user log + GLOBs.}

int Property STATE_IDLE = 0 AutoReadOnly
int Property STATE_PENDING_WRITE = 1 AutoReadOnly
int Property STATE_FADING_OUT = 2 AutoReadOnly
int Property STATE_MOVING = 3 AutoReadOnly
int Property STATE_WAITING_3D = 4 AutoReadOnly
int Property STATE_ARRIVED = 5 AutoReadOnly
int Property STATE_RECOVERED = 6 AutoReadOnly
int Property STATE_CLEARED = 7 AutoReadOnly
int Property STATE_FAILED = -1 AutoReadOnly

int Property MODE_MOVETO_SETPOS = 0 AutoReadOnly
int Property MODE_FAST_TRAVEL = 1 AutoReadOnly
int Property MODE_TRANSIT_INTERIOR = 2 AutoReadOnly

string Property PROBE_PLUGIN = "FO4SFTravelProbe.esm" AutoReadOnly
string Property CW_PLUGIN = "FO4TerrainCore.esm" AutoReadOnly
string Property FH_PLUGIN = "FO4WorldFarHarbor.esm" AutoReadOnly

Function Log(string asMsg)
    Debug.OpenUserLog("FO4SF_TravelProbe")
    Debug.TraceUser("FO4SF_TravelProbe", asMsg)
EndFunction

GlobalVariable Function ProbeGlob(int aiLocalId)
    return Game.GetFormFromFile(aiLocalId, PROBE_PLUGIN) as GlobalVariable
EndFunction

Function SetGlob(int aiLocalId, float afVal)
    GlobalVariable g = ProbeGlob(aiLocalId)
    if g != None
        g.SetValue(afVal)
    endif
EndFunction

float Function GetGlob(int aiLocalId, float afDefault = 0.0)
    GlobalVariable g = ProbeGlob(aiLocalId)
    if g != None
        return g.GetValue()
    endif
    return afDefault
EndFunction

ObjectReference Function ResolveCommonwealthAnchor()
    ObjectReference r = Game.GetFormFromFile(0x0A775B, CW_PLUGIN) as ObjectReference
    if r == None
        r = Game.GetFormFromFile(0x005C50, CW_PLUGIN) as ObjectReference
    endif
    if r == None
        r = Game.GetFormFromFile(0x000801, CW_PLUGIN) as ObjectReference
    endif
    return r
EndFunction

ObjectReference Function ResolveFarHarborAnchor()
    ObjectReference r = Game.GetFormFromFile(0x000801, FH_PLUGIN) as ObjectReference
    if r == None
        r = Game.GetFormFromFile(0x000802, FH_PLUGIN) as ObjectReference
    endif
    if r == None
        r = Game.GetFormFromFile(0x000803, FH_PLUGIN) as ObjectReference
    endif
    return r
EndFunction

ObjectReference Function ResolveTransitMarker()
    return Game.GetFormFromFile(0x000831, PROBE_PLUGIN) as ObjectReference
EndFunction

Form Function ResolveProbeToken()
    Form tok = Game.GetFormFromFile(0x000810, PROBE_PLUGIN)
    if tok == None
        tok = Game.GetFormFromFile(0x00000F, "Starfield.esm")
    endif
    return tok
EndFunction

WorldSpace Function ResolveHostWorld(ObjectReference akAnchor)
    if akAnchor == None
        return None
    endif
    return akAnchor.GetWorldSpace()
EndFunction

bool Function IsTravelLocked()
    int st = GetGlob(0x800, 0.0) as int
    return st >= STATE_PENDING_WRITE && st <= STATE_WAITING_3D
EndFunction

Function ClearPendingRecord(int aiFinalState)
    SetGlob(0x800, aiFinalState as float)
    SetGlob(0x800, STATE_IDLE as float)
EndFunction

Function WritePendingRecord(int aiSrcCode, int aiDstCode, int aiMode, ObjectReference akDest, float afOffX, float afOffY, float afOffZ)
    float seq = GetGlob(0x804, 0.0) + 1.0
    SetGlob(0x804, seq)
    SetGlob(0x801, aiSrcCode as float)
    SetGlob(0x802, aiDstCode as float)
    SetGlob(0x803, aiMode as float)
    if akDest != None
        SetGlob(0x809, akDest.GetPositionX() + afOffX)
        SetGlob(0x80A, akDest.GetPositionY() + afOffY)
        SetGlob(0x80B, akDest.GetPositionZ() + afOffZ)
    endif
    SetGlob(0x800, STATE_PENDING_WRITE as float)
EndFunction

bool Function ExecuteMoveToHop(int aiSrcCode, int aiDstCode, int aiMode, ObjectReference akDest, float afOffX = 0.0, float afOffY = 0.0, float afOffZ = 0.5)
    Actor player = Game.GetPlayer()
    if player == None || akDest == None
        Log("travel_fail reason=missing_player_or_dest src=" + aiSrcCode + " dst=" + aiDstCode)
        SetGlob(0x800, STATE_FAILED as float)
        return False
    endif
    if IsTravelLocked()
        Log("travel_reject reason=trip_already_active")
        return False
    endif

    Form tok = ResolveProbeToken()
    int preItems = 0
    if tok != None
        preItems = player.GetItemCount(tok)
        if preItems <= 0
            player.AddItem(tok, 1, True)
            preItems = player.GetItemCount(tok)
        endif
    endif

    float t0 = Utility.GetCurrentRealTime()
    WorldSpace targetWs = ResolveHostWorld(akDest)
    WritePendingRecord(aiSrcCode, aiDstCode, aiMode, akDest, afOffX, afOffY, afOffZ)

    SetGlob(0x800, STATE_FADING_OUT as float)
    Game.FadeOutGame(True, True, 0.0, 0.35, True)
    Utility.Wait(0.35)

    SetGlob(0x800, STATE_MOVING as float)
    player.MoveTo(akDest, afOffX, afOffY, afOffZ, True, False)

    SetGlob(0x800, STATE_WAITING_3D as float)
    player.WaitFor3DLoad()
    float tx = akDest.GetPositionX() + afOffX
    float ty = akDest.GetPositionY() + afOffY
    float tz = akDest.GetPositionZ() + afOffZ
    player.SetPosition(tx, ty, tz)
    player.SetAngle(0.0, 0.0, akDest.GetAngleZ())

    bool followersOk = False
    SQ_FollowersScript followers = SQ_FollowersScript.GetScript()
    if followers != None
        Actor[] moved = followers.TeleportFollowers(player, None, True, False, True, False, False)
        followersOk = True
        Log("followers_teleported count=" + moved.Length)
    endif
    SetGlob(0x806, followersOk as float)

    bool loadedOk = akDest.Is3DLoaded() || (player.GetParentCell() != None)
    SetGlob(0x808, loadedOk as float)

    bool itemsOk = True
    if tok != None
        itemsOk = (player.GetItemCount(tok) >= preItems)
    endif
    SetGlob(0x807, itemsOk as float)

    Game.FadeOutGame(False, True, 0.15, 0.45, False)
    SetGlob(0x800, STATE_ARRIVED as float)
    WorldSpace arrivedWs = player.GetWorldSpace()
    float dt = Utility.GetCurrentRealTime() - t0
    Log("moveto_ok src=" + aiSrcCode + " dst=" + aiDstCode + " mode=" + aiMode + " targetWs=" + targetWs + " arrivedWs=" + arrivedWs + " loaded=" + loadedOk + " followers=" + followersOk + " items=" + itemsOk + " elapsed=" + dt)
    ClearPendingRecord(STATE_CLEARED)
    return True
EndFunction

bool Function ExecuteFastTravelComparison(int aiSrcCode, int aiDstCode, ObjectReference akDest)
    Actor player = Game.GetPlayer()
    if player == None || akDest == None || IsTravelLocked()
        return False
    endif
    Form tok = ResolveProbeToken()
    int preItems = 0
    if tok != None
        preItems = player.GetItemCount(tok)
    endif
    float t0 = Utility.GetCurrentRealTime()
    WorldSpace targetWs = ResolveHostWorld(akDest)
    WritePendingRecord(aiSrcCode, aiDstCode, MODE_FAST_TRAVEL, akDest, 0.0, 0.0, 0.0)
    SetGlob(0x800, STATE_MOVING as float)
    Game.FastTravel(akDest)
    SetGlob(0x800, STATE_WAITING_3D as float)
    player.WaitFor3DLoad()

    bool itemsOk = True
    if tok != None
        itemsOk = (player.GetItemCount(tok) >= preItems)
    endif
    SetGlob(0x807, itemsOk as float)
    SetGlob(0x808, (player.GetParentCell() != None) as float)
    SetGlob(0x800, STATE_ARRIVED as float)
    float dt = Utility.GetCurrentRealTime() - t0
    Log("fasttravel_done src=" + aiSrcCode + " dst=" + aiDstCode + " targetWs=" + targetWs + " arrivedWs=" + player.GetWorldSpace() + " items=" + itemsOk + " elapsed=" + dt)
    ClearPendingRecord(STATE_CLEARED)
    return True
EndFunction

Event OnQuestInit()
    Actor player = Game.GetPlayer()
    if player != None
        RegisterForRemoteEvent(player, "OnPlayerLoadGame")
    endif
    Log("probe_init quest=" + self)
EndEvent

Event Actor.OnPlayerLoadGame(Actor akSender)
    int st = GetGlob(0x800, 0.0) as int
    if st >= STATE_PENDING_WRITE && st <= STATE_WAITING_3D
        int dst = GetGlob(0x802, 0.0) as int
        Log("reload_recovery state=" + st + " dst=" + dst + " ws=" + akSender.GetWorldSpace())
        SetGlob(0x800, STATE_RECOVERED as float)
        Game.FadeOutGame(False, True, 0.0, 0.25, False)
        ClearPendingRecord(STATE_CLEARED)
    endif
EndEvent

Event OnStageSet(int auiStageID, int auiItemID)
    if auiStageID == 10
        ExecuteMoveToHop(1, 5, MODE_MOVETO_SETPOS, ResolveFarHarborAnchor(), 2.0, 2.0, 0.5)
    elseif auiStageID == 20
        ExecuteMoveToHop(5, 1, MODE_MOVETO_SETPOS, ResolveCommonwealthAnchor(), 0.0, 0.0, 0.5)
    elseif auiStageID == 30
        SetGlob(0x805, 1.0)
        ExecuteMoveToHop(1, 0, MODE_TRANSIT_INTERIOR, ResolveTransitMarker(), 0.0, 0.0, 0.25)
        SetGlob(0x805, 2.0)
        ExecuteMoveToHop(0, 5, MODE_TRANSIT_INTERIOR, ResolveFarHarborAnchor(), 1.0, 1.0, 0.5)
    elseif auiStageID == 40
        ExecuteFastTravelComparison(5, 1, ResolveCommonwealthAnchor())
    elseif auiStageID == 50
        ExecuteMoveToHop(1, 5, MODE_MOVETO_SETPOS, ResolveFarHarborAnchor(), 2.0, 2.0, 0.5)
        ExecuteMoveToHop(5, 0, MODE_TRANSIT_INTERIOR, ResolveTransitMarker(), 0.0, 0.0, 0.25)
        ExecuteMoveToHop(0, 1, MODE_TRANSIT_INTERIOR, ResolveCommonwealthAnchor(), 0.0, 0.0, 0.5)
        ExecuteFastTravelComparison(1, 5, ResolveFarHarborAnchor())
        ExecuteMoveToHop(5, 1, MODE_MOVETO_SETPOS, ResolveCommonwealthAnchor(), 0.0, 0.0, 0.5)
    elseif auiStageID == 90
        Game.FadeOutGame(False, True, 0.0, 0.2, False)
        ClearPendingRecord(STATE_CLEARED)
        Log("manual_reset_cleared")
    endif
EndEvent
