Scriptname FO4SF_MQ203Quest extends Quest
{"Dangerous Minds" (FO4SFMission.esm 0x000AF0, source-audited from Fallout 4's MQ202/MQ203 0x0229E9).
 Story mode only (FO4SF_GameMode 0x000870 == 1; stops silently in Warfare mode == 2).
 Stages:
   5   = Objective 5: Bring Kellogg's cybernetic brain augmenter to Goodneighbor's Memory Den
   10  = Objective 10: Speak with Doctor Amari (or use LoungerProxyActi if Amari dead) in Memory Den (0x00ED4A)
   100 = Objective 100: Enter the Memory Lounger (safe MessageBox -> MoveTo FO4Port_MQ203KelloggsBrain 0x00F23E)
   110 = Objective 110: Explore Kellogg's memories to locate Virgil's trail (with R10 bridge bypass)
   120 = Objective 120: Speak with Doctor Amari (or Open-Mode lab terminal) and prepare for the Glowing Sea
   300 = CompleteQuest -> set FO4SF_MQ204Armed=1 and StartNoWait() on FO4SF_MQ204 (0x000B10).
 W6 break-it safe: MIND-01..05 (Open-Mode self-scan if Amari dead, safe lounger MessageBox instead of seat trap,
 R10 memory-bridge watchdog/bypass, OnPlayerLoadGame re-sync, Open-Mode lab terminal debrief).}

Form Property XMarkerBase Auto Const
Actor Property DoctorAmari Auto Const
Actor Property NickValentine Auto Const
MiscObject Property CyberBrain Auto Const
Activator Property LoungerProxyActi Auto Const
GlobalVariable Property MemoriesCompleted Auto Const
GlobalVariable Property MQ204Armed Auto Const
Message Property AmariTalkMsg Auto Const
Message Property LoungerMsg Auto Const
Message Property MemoryWalkMsg Auto Const
Message Property LabTerminalMsg Auto Const

string LogName = "fo4sf_mission"
string CorePlugin = "FO4TerrainCore.esm"
string CoreMarsPlugin = "FO4TerrainCore_Mars.esm"
string PortPlugin = "FO4Port.esm"
string MissionPlugin = "FO4SFMission.esm"
int CommonwealthWorldId = 0x000803
int CommonwealthAnchorId = 0x0A775B

; Verified FO4Port.esm cell IDs and persistent (0x400) COCMarkerHeading arrival refs
int MemoryDenCellId = 0x00ED4A
int MemoryDenReturnMarkerId = 0x00F23D
int KelloggsBrainCellId = 0x00F23E
int KelloggsBrainMarkerId = 0x00F2D3

; Verified merged coordinates (Goodneighbor / Memory Den -902.48, -2870.07, 19.20)
float GoodneighborX = -902.48
float GoodneighborY = -2870.07
float GoodneighborZ = 19.20
float GlowingSeaEdgeX = -2001.32
float GlowingSeaEdgeY = -3821.65
float MergeOffsetX = -1200.0
float MergeOffsetY = -2700.0

float PlaceRadius = 260.0
float ArrivalRadius = 90.0
float TalkFallbackRadius = 3.5
float TalkFallbackSeconds = 8.0

bool instanceStarted = False
bool completed = False
bool actorsPlaced = False
bool talkOpen = False
int talkSessionId = 0
int applied = 0
int pendingStage = -1
string pendingStageBy = "other"
ObjectReference loungerProxyRef = None
ObjectReference amariTalkProxy = None
int memoryTicks = 0
float talkNearSec = 0.0

bool Function IsTestModeEnabled()
    GlobalVariable tm = Game.GetFormFromFile(0x000860, "FO4SFCoreValues.esm") as GlobalVariable
    return tm != None && tm.GetValue() != 0.0
EndFunction

bool Function CheckPredecessorGate()
{R5: MQ203 starts strictly behind MQ106 completion (stage >= 500 or FO4SF_MQ203Armed >= 1) unless TestMode is on.}
    if IsTestModeEnabled()
        return True
    endif
    GlobalVariable armed = Game.GetFormFromFile(0x000AD7, MissionPlugin) as GlobalVariable
    if armed != None && armed.GetValue() >= 1.0
        return True
    endif
    Quest mq106 = Game.GetFormFromFile(0x000AD0, MissionPlugin) as Quest
    if mq106 != None && (mq106.IsCompleted() || mq106.GetStage() >= 500)
        return True
    endif
    return False
EndFunction

bool Function IsWarfareMode()
    GlobalVariable gm = Game.GetFormFromFile(0x000870, "FO4SFCoreValues.esm") as GlobalVariable
    if gm != None && (gm.GetValue() as int) == 2
        return True
    endif
    return False
EndFunction

int Function EffectiveStage()
    int raw = GetStage()
    if applied > raw
        return applied
    endif
    return raw
EndFunction

string Function ActiveCorePlugin()
    if Game.IsPluginInstalled(CorePlugin)
        return CorePlugin
    elseif Game.IsPluginInstalled(CoreMarsPlugin)
        return CoreMarsPlugin
    endif
    return ""
EndFunction

WorldSpace Function ResolveCommonwealthWorld()
    string cp = ActiveCorePlugin()
    if cp == ""
        return None
    endif
    ObjectReference anchor = Game.GetFormFromFile(CommonwealthAnchorId, cp) as ObjectReference
    if anchor != None
        WorldSpace aws = anchor.GetWorldSpace()
        if aws != None
            return aws
        endif
    endif
    return Game.GetFormFromFile(CommonwealthWorldId, cp) as WorldSpace
EndFunction

bool Function IsCommonwealthExterior(Actor player)
    if player == None || !player.Is3DLoaded() || player.IsInInterior()
        return False
    endif
    WorldSpace ws = player.GetWorldSpace()
    WorldSpace wantWs = ResolveCommonwealthWorld()
    if ws == None || wantWs == None || ws != wantWs
        return False
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    if px < MergeOffsetX - 3200.0 || px > MergeOffsetX + 3200.0 || py < MergeOffsetY - 3200.0 || py > MergeOffsetY + 3200.0
        return False
    endif
    return True
EndFunction

bool Function IsPlayerStableAt(Actor player, float snapX, float snapY, float snapZ)
    if !IsCommonwealthExterior(player)
        return False
    endif
    float dx = player.GetPositionX() - snapX
    float dy = player.GetPositionY() - snapY
    float dz = player.GetPositionZ() - snapZ
    return (dx * dx + dy * dy + dz * dz) <= 25.0
EndFunction

Actor Function ResolveAmari()
    if DoctorAmari != None
        return DoctorAmari
    endif
    return Game.GetFormFromFile(0x000AF2, MissionPlugin) as Actor
EndFunction

bool Function IsAmariUnavailable()
    Actor am = ResolveAmari()
    return am == None || am.IsDead()
EndFunction

bool Function IsInCellId(Actor player, int portCellId)
    if player == None || !player.IsInInterior()
        return False
    endif
    Cell cur = player.GetParentCell()
    if cur != None && Game.IsPluginInstalled(PortPlugin)
        Cell target = Game.GetFormFromFile(portCellId, PortPlugin) as Cell
        if target != None && cur == target
            return True
        endif
    endif
    return False
EndFunction

bool Function IsNearXY(Actor player, float tx, float ty, float radius)
    if !IsCommonwealthExterior(player)
        return False
    endif
    float dx = player.GetPositionX() - tx
    float dy = player.GetPositionY() - ty
    return (dx * dx + dy * dy) <= radius * radius
EndFunction

Function AdvanceTo(int n, string by = "Trigger")
    pendingStage = n
    pendingStageBy = by
    SetStage(n)
    if n > applied
        applied = n
        Trace("mq203 stage " + n + " by=" + by)
        ApplyStage(n, by)
    endif
EndFunction

Event OnStageSet(int auiStageID, int auiItemID)
    if auiStageID > applied
        string cause = "other"
        if auiStageID == pendingStage
            cause = pendingStageBy
        endif
        applied = auiStageID
        Trace("mq203 stage " + auiStageID + " by=" + cause)
        ApplyStage(auiStageID, cause)
    endif
EndEvent

Function ApplyStage(int n, string by)
    if n == 5
        SetObjectiveDisplayed(5, True, True)
        SetActive(True)
    elseif n == 10
        SetObjectiveCompleted(5)
        SetObjectiveDisplayed(10, True, True)
    elseif n == 100
        SetObjectiveCompleted(5)
        SetObjectiveCompleted(10)
        SetObjectiveDisplayed(100, True, True)
    elseif n == 110
        SetObjectiveCompleted(100)
        SetObjectiveDisplayed(110, True, True)
    elseif n == 120
        SetObjectiveCompleted(110)
        if MemoriesCompleted != None
            MemoriesCompleted.SetValue(1.0)
        endif
        SetObjectiveDisplayed(120, True, True)
    elseif n == 300
        if completed
            return
        endif
        completed = True
        ReleaseAllActors()
        SetObjectiveCompleted(120)
        if MemoriesCompleted != None
            MemoriesCompleted.SetValue(1.0)
        endif
        if MQ204Armed != None
            MQ204Armed.SetValue(1.0)
        endif
        CompleteQuest()
        CancelTimer(1)
        Quest mq204 = Game.GetFormFromFile(0x000B10, MissionPlugin) as Quest
        bool started204 = False
        if mq204 != None && !mq204.IsRunning() && !mq204.IsCompleted()
            mq204.StartNoWait()
            started204 = True
        endif
        Trace("mq203 complete stage=300 memories=1 mq204_armed=1 mq204_started=" + started204 + " by=" + by)
    endif
EndFunction

Event OnQuestStarted()
    StartQuestInstance()
EndEvent

Event OnQuestInit()
    StartQuestInstance()
EndEvent

Function StartQuestInstance()
    if instanceStarted
        return
    endif
    instanceStarted = True
    Debug.OpenUserLog(LogName)
    if IsWarfareMode()
        Trace("mission gate mode=2 started=false quest=mq203")
        Stop()
        return
    endif
    if !CheckPredecessorGate()
        Trace("mq203 gate_deferred reason=mq106_incomplete")
        instanceStarted = False
        Stop()
        return
    endif
    if !IsRunning()
        Start()
    endif
    Actor player = Game.GetPlayer()
    if player != None
        RegisterForRemoteEvent(player, "OnPlayerLoadGame")
    endif
    BindRefs()
    AdvanceTo(5, "Trigger")
    if player != None && IsInCellId(player, KelloggsBrainCellId)
        AdvanceTo(110, "out_of_order")
    elseif player != None && (IsInCellId(player, MemoryDenCellId) || IsNearXY(player, GoodneighborX, GoodneighborY, ArrivalRadius))
        AdvanceTo(10, "out_of_order")
    endif
    Trace("mq203 init stage=" + EffectiveStage() + " memory_den=0x00ED4A brain_cell=0x00F23E")
    if !completed
        StartTimer(1.0, 1)
    endif
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    talkOpen = False
    talkSessionId += 1
    actorsPlaced = False
    talkNearSec = 0.0
    int st = EffectiveStage()
    Trace("mq203 reload stage=" + st + " complete=" + completed)
    if !completed
        if !IsRunning()
            Start()
        endif
        if applied > GetStage()
            SetStage(applied)
        endif
        BindRefs()
        if st >= 120 && MemoriesCompleted != None
            MemoriesCompleted.SetValue(1.0)
        endif
        StartTimer(1.0, 1)
    endif
EndEvent

Function BindRefs()
    Actor am = ResolveAmari()
    if am != None && !am.IsDead()
        am.AllowPCDialogue(True)
        am.BlockActivation(False, False)
        RegisterForRemoteEvent(am, "OnActivate")
    endif
EndFunction

Function ReleaseAllActors()
    Actor am = ResolveAmari()
    if am != None && !am.IsDead()
        am.SetRestrained(False)
    endif
EndFunction

Function ReleaseIfInCombat(Actor a)
    if a != None && !a.IsDead() && a.GetCombatState() != 0
        a.SetRestrained(False)
    endif
EndFunction

Function PlaceHubActors(Actor player)
    if !IsCommonwealthExterior(player) || actorsPlaced
        return
    endif
    Actor am = ResolveAmari()
    float snapX = player.GetPositionX()
    float snapY = player.GetPositionY()
    float snapZ = player.GetPositionZ()
    if am != None && !am.IsDead()
        if am.IsDisabled()
            am.EnableNoWait(False)
            BindRefs()
        endif
        if !IsPlayerStableAt(player, snapX, snapY, snapZ)
            return
        endif
        am.SetRestrained(False)
        am.MoveTo(player, GoodneighborX - snapX, GoodneighborY - snapY, GoodneighborZ - snapZ, False, False)
        if am.GetCombatState() == 0
            am.SetRestrained(True)
        endif
        am.AllowPCDialogue(True)
        if amariTalkProxy == None || amariTalkProxy.IsDeleted()
            Activator talkActi = Game.GetFormFromFile(0x000970, MissionPlugin) as Activator
            if talkActi != None
                amariTalkProxy = am.PlaceAtMe(talkActi, 1, True, False, False)
                if amariTalkProxy != None
                    amariTalkProxy.MoveTo(am, 0.0, 0.0, 1.0, False, False)
                    RegisterForRemoteEvent(amariTalkProxy, "OnActivate")
                endif
            endif
        endif
    endif
    if !IsPlayerStableAt(player, snapX, snapY, snapZ)
        return
    endif
    actorsPlaced = True
    Trace("mq203 amari placed goodneighbor=true")
EndFunction

Function EnsureLoungerProxy(Actor player)
    if LoungerProxyActi == None || player == None
        return
    endif
    if loungerProxyRef != None && !loungerProxyRef.IsDeleted()
        return
    endif
    if IsInCellId(player, MemoryDenCellId) || IsNearXY(player, GoodneighborX, GoodneighborY, PlaceRadius)
        float snapX = player.GetPositionX()
        float snapY = player.GetPositionY()
        float snapZ = player.GetPositionZ()
        loungerProxyRef = player.PlaceAtMe(LoungerProxyActi, 1, True, False, False)
        if loungerProxyRef != None
            if IsCommonwealthExterior(player) && IsPlayerStableAt(player, snapX, snapY, snapZ)
                loungerProxyRef.MoveTo(player, (GoodneighborX + 2.5) - snapX, (GoodneighborY + 2.5) - snapY, (GoodneighborZ + 1.0) - snapZ, False, False)
            else
                loungerProxyRef.MoveTo(player, 2.0, 2.0, 0.5, False, False)
            endif
            RegisterForRemoteEvent(loungerProxyRef, "OnActivate")
            Trace("mq203 lounger proxy spawned")
        endif
    endif
EndFunction

bool Function MovePlayerToKelloggBrain(Actor player)
{R8 truth: only return True when FO4Port.esm persistent marker 0x00F2D3 actually resolves and moves the player.}
    if player == None
        return False
    endif
    if Game.IsPluginInstalled(PortPlugin)
        ObjectReference dest = Game.GetFormFromFile(KelloggsBrainMarkerId, PortPlugin) as ObjectReference
        if dest != None
            player.MoveTo(dest)
            Trace("mq203 brain_move dest=0x00F2D3 ok=true")
            return True
        endif
    endif
    Trace("mq203 brain_move blocked=true reason=missing_port_cell cell=0x00F23E marker=0x00F2D3")
    return False
EndFunction

Function ReturnPlayerFromKelloggBrain(Actor player)
{R10 never-strand return: Kellogg's Brain cell 0x00F23E has zero exit load doors; always move player back to persistent Memory Den marker 0x00F23D or Amari.}
    if player == None || !IsInCellId(player, KelloggsBrainCellId)
        return
    endif
    if Game.IsPluginInstalled(PortPlugin)
        ObjectReference retMarker = Game.GetFormFromFile(MemoryDenReturnMarkerId, PortPlugin) as ObjectReference
        if retMarker != None
            player.MoveTo(retMarker)
            Trace("mq203 brain_return dest=0x00F23D ok=true")
            return
        endif
    endif
    Actor am = ResolveAmari()
    if am != None
        player.MoveTo(am, 1.5, 1.5, 0.0, False, False)
        Trace("mq203 brain_return dest=amari ok=true")
    endif
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID != 1 || completed
        return
    endif
    int raw = GetStage()
    if raw > applied
        applied = raw
        ApplyStage(raw, "other")
    elseif applied > raw
        if !IsRunning()
            Start()
        endif
        SetStage(applied)
    endif
    int st = EffectiveStage()
    Actor player = Game.GetPlayer()
    if player == None
        StartTimer(1.0, 1)
        return
    endif

    ReleaseIfInCombat(ResolveAmari())
    bool inDen = IsInCellId(player, MemoryDenCellId)
    bool inBrain = IsInCellId(player, KelloggsBrainCellId)
    bool nearGn = IsNearXY(player, GoodneighborX, GoodneighborY, PlaceRadius)

    if nearGn && !actorsPlaced
        PlaceHubActors(player)
    endif
    if inDen || nearGn
        EnsureLoungerProxy(player)
    endif

    if st < 10 && (inDen || IsNearXY(player, GoodneighborX, GoodneighborY, ArrivalRadius))
        AdvanceTo(10, "Trigger")
        st = EffectiveStage()
    endif
    if st < 110 && inBrain
        AdvanceTo(110, "Trigger")
        st = EffectiveStage()
    endif
    if st == 110 && inBrain
        memoryTicks += 1
        if memoryTicks >= 6 && !talkOpen
            RunMemoryWalkModal()
        endif
    endif
    ; Open-Mode: if player heads straight to the Glowing Sea after stage 120, finish MQ203 cleanly
    if st == 120 && IsNearXY(player, GlowingSeaEdgeX, GlowingSeaEdgeY, 200.0)
        AdvanceTo(300, "open_mode")
        return
    endif
    CheckAmariTalkFallback(player, st)

    if !completed
        StartTimer(1.0, 1)
    endif
EndEvent

Function CheckAmariTalkFallback(Actor player, int st)
{R4: Timed proximity fallback while Doctor Amari is alive so topicless OnActivate never stalls.}
    if talkOpen || completed || player == None
        talkNearSec = 0.0
        return
    endif
    if st <= 10 || st == 120
        Actor am = ResolveAmari()
        if am != None && !am.IsDead() && !am.IsDisabled() && am.Is3DLoaded() && player.GetDistance(am) <= TalkFallbackRadius
            talkNearSec += 1.0
            if talkNearSec >= TalkFallbackSeconds
                talkNearSec = 0.0
                Trace("mq203 talk_fallback actor=amari stage=" + st + " near_sec=" + TalkFallbackSeconds)
                if st <= 10
                    RunAmariTalk()
                else
                    RunLabTerminalOrDebrief("talk_fallback")
                endif
            endif
            return
        endif
    endif
    talkNearSec = 0.0
EndFunction

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    if completed || akActionRef != Game.GetPlayer()
        return
    endif
    int st = EffectiveStage()
    Actor am = ResolveAmari()
    if (am != None && akSender == am) || (amariTalkProxy != None && akSender == amariTalkProxy)
        if st <= 10
            RunAmariTalk()
        elseif st == 120
            RunLabTerminalOrDebrief("talk")
        endif
        return
    endif
    if akSender == loungerProxyRef
        if st <= 10 && IsAmariUnavailable()
            ; MIND-01 Open-Mode dead-Amari self-scan bypass
            AdvanceTo(100, "open_mode")
            RunLoungerModal()
        elseif st == 100 || st == 110
            RunLoungerModal()
        elseif st == 120
            RunLabTerminalOrDebrief("open_mode")
        endif
    endif
EndEvent

Function RunAmariTalk()
    if talkOpen || AmariTalkMsg == None
        return
    endif
    talkOpen = True
    talkSessionId += 1
    int sid = talkSessionId
    int btn = AmariTalkMsg.Show()
    if sid != talkSessionId
        return
    endif
    talkOpen = False
    if btn < 0 || btn == 3
        return
    endif
    AdvanceTo(100, "talk")
EndFunction

Function RunLoungerModal()
    if talkOpen || LoungerMsg == None
        return
    endif
    talkOpen = True
    talkSessionId += 1
    int sid = talkSessionId
    int btn = LoungerMsg.Show()
    if sid != talkSessionId
        return
    endif
    talkOpen = False
    if btn < 0 || btn == 2
        return
    endif
    if btn == 0
        ; R8 truth: only advance into memory walk if FO4Port.esm persistent marker 0x00F2D3 actually moved the player
        if MovePlayerToKelloggBrain(Game.GetPlayer())
            AdvanceTo(110, "lounger")
            RunMemoryWalkModal()
        endif
    elseif btn == 1
        ; MIND-01 / MIND-02 autonomous pod self-scan (explicitly logged as stand-in)
        Trace("mq203 stand_in_scan=true reason=open_mode_autonomous_scan")
        AdvanceTo(110, "open_mode_stand_in")
        AdvanceTo(120, "open_mode_stand_in")
        if IsAmariUnavailable()
            AdvanceTo(300, "open_mode_stand_in")
        endif
    endif
EndFunction

Function RunMemoryWalkModal()
    if talkOpen || MemoryWalkMsg == None
        return
    endif
    talkOpen = True
    talkSessionId += 1
    int sid = talkSessionId
    int btn = MemoryWalkMsg.Show()
    if sid != talkSessionId
        return
    endif
    talkOpen = False
    if btn < 0 || btn == 2
        return
    endif
    ReturnPlayerFromKelloggBrain(Game.GetPlayer())
    AdvanceTo(120, "memory_walk")
    if IsAmariUnavailable()
        RunLabTerminalOrDebrief("open_mode")
    endif
EndFunction

Function RunLabTerminalOrDebrief(string why)
    if talkOpen
        return
    endif
    if LabTerminalMsg != None
        talkOpen = True
        talkSessionId += 1
        int sid = talkSessionId
        int btn = LabTerminalMsg.Show()
        if sid != talkSessionId
            return
        endif
        talkOpen = False
        if btn < 0 || btn == 1
            return
        endif
    endif
    AdvanceTo(300, why)
EndFunction

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
