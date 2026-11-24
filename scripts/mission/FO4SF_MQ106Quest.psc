Scriptname FO4SF_MQ106Quest extends Quest
{"Reunions" (FO4SFMission.esm 0x000AD0, source-audited from Fallout 4's MQ106 0x0229E7).
 Story mode only (FO4SF_GameMode 0x000870 == 1; stops silently in Warfare mode == 2).
 Stages:
   10  = Objective 10: Follow Dogmeat (or walk directly) to Fort Hagen (merged -2456.84, -2781.07)
   50  = Objective 50: Enter Fort Hagen via 0D RoofLoadDoorId 0x0547B0 (FO4Port_FortHagen01 0x00BA4B)
   75  = Inside Fort Hagen descending to Command Center (FO4Port_FortHagen02 0x00CFC6)
   100 = Objective 100: Confront and defeat Kellogg (hostile armed boss 0x000AD2)
   125 = Combat engaged with Kellogg (either after dialogue or REUN-03 pre-attack)
   150 = Objective 150: Recover CyberBrain (0x000AD3) + KelloggPassword (0x000AD4), read terminal, exit roof
   200 = Objective 200: Exterior roof exit triggers FO4SF_PrydwenArrived=1 (REUN-04); report to Nick or Open-Mode dossier
   500 = CompleteQuest -> set FO4SF_MQ203Armed=1 and StartNoWait() on FO4SF_MQ203 (0x000AF0).
 W6 break-it safe: REUN-01..05 (direct Fort Hagen entry with Dogmeat downed/absent, pre-attacking Kellogg
 without dialogue, Open-Mode TerminalProxyActi backup augmenter/password, exterior load Prydwen trigger,
 Open-Mode dead-Nick dossier or direct Memory Den arrival with CyberBrain).}

Form Property XMarkerBase Auto Const
Actor Property Kellogg Auto Const
Actor Property NickValentine Auto Const
Actor Property Dogmeat Auto Const
MiscObject Property CyberBrain Auto Const
MiscObject Property KelloggPassword Auto Const
Activator Property TerminalProxyActi Auto Const
GlobalVariable Property PrydwenArrived Auto Const
GlobalVariable Property MQ203Armed Auto Const
Message Property ConfrontMsg Auto Const
Message Property TerminalMsg Auto Const
Message Property DebriefMsg Auto Const
Message Property DossierMsg Auto Const

string LogName = "fo4sf_mission"
string CorePlugin = "FO4TerrainCore.esm"
string CoreMarsPlugin = "FO4TerrainCore_Mars.esm"
string PortPlugin = "FO4Port.esm"
string FortHagenPlugin = "FO4SFFortHagen.esm"
string MissionPlugin = "FO4SFMission.esm"
int CommonwealthAnchorId = 0x0A775B
int CommonwealthFallbackAnchorId = 0x005C50

; Verified FO4Port.esm cell IDs
int FortHagen01CellId = 0x00BA4B
int FortHagen02CellId = 0x00CFC6
int MemoryDenCellId = 0x00ED4A

; Verified FO4TerrainCore.esm Fort Hagen roof door & marker
int FortHagenRoofDoorId = 0x0547B0
int FortHagenRoofMarkerId = 0x0A774C

; Verified merged coordinates (FO4/70 + MergeOffset -1200, -2700)
float FortHagenX = -2456.84
float FortHagenY = -2781.07
float FortHagenZ = 81.83
float DiamondCityX = -1416.36
float DiamondCityY = -3129.39
float GoodneighborX = -902.48
float GoodneighborY = -2870.07
float MergeOffsetX = -1200.0
float MergeOffsetY = -2700.0

float PlaceRadius = 260.0
float ArrivalRadius = 150.0
float EngageRadius = 45.0
float TalkFallbackRadius = 3.5
float TalkFallbackSeconds = 8.0

bool instanceStarted = False
bool gateDeferred = False
bool completed = False
bool actorsPlaced = False
bool talkOpen = False
int talkSessionId = 0
bool brainGranted = False
bool passwordGranted = False
bool prydwenLogged = False
float talkNearSec = 0.0
int applied = 0
int pendingStage = -1
string pendingStageBy = "other"
ObjectReference terminalProxyRef = None
ObjectReference roofDoorRef = None
ObjectReference nickTalkProxy = None

bool Function IsTestModeEnabled()
    GlobalVariable tm = Game.GetFormFromFile(0x000860, "FO4SFCoreValues.esm") as GlobalVariable
    return tm != None && tm.GetValue() != 0.0
EndFunction

bool Function CheckPredecessorGate()
{R5: MQ106 starts strictly behind MQ105 completion (stage >= 200 or FO4SF_MQ106Armed >= 1) so Fort Hagen never starts MQ105 and MQ106 together while MQ105 is still at stage 100.}
    if IsTestModeEnabled()
        return True
    endif
    GlobalVariable armed = Game.GetFormFromFile(0x000AB8, MissionPlugin) as GlobalVariable
    if armed != None && armed.GetValue() >= 1.0
        return True
    endif
    Quest mq105 = Game.GetFormFromFile(0x000AB0, MissionPlugin) as Quest
    if mq105 != None && (mq105.IsCompleted() || mq105.GetStage() >= 200)
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
    ObjectReference fallbackAnchor = Game.GetFormFromFile(CommonwealthFallbackAnchorId, cp) as ObjectReference
    if fallbackAnchor != None
        WorldSpace fws = fallbackAnchor.GetWorldSpace()
        if fws != None
            return fws
        endif
    endif
    return None
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

Actor Function ResolveKellogg()
    if Kellogg != None
        return Kellogg
    endif
    return Game.GetFormFromFile(0x000AD2, MissionPlugin) as Actor
EndFunction

Actor Function ResolveNick()
    if NickValentine != None
        return NickValentine
    endif
    return Game.GetFormFromFile(0x000A82, MissionPlugin) as Actor
EndFunction

bool Function IsNickUnavailable()
    Actor nick = ResolveNick()
    return nick == None || nick.IsDead()
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

bool Function IsAtFortHagenExterior(Actor player)
    if !IsCommonwealthExterior(player)
        return False
    endif
    string cp = ActiveCorePlugin()
    if cp != ""
        ObjectReference mk = Game.GetFormFromFile(FortHagenRoofMarkerId, cp) as ObjectReference
        if mk != None && player.GetDistance(mk) <= ArrivalRadius
            return True
        endif
    endif
    return IsNearXY(player, FortHagenX, FortHagenY, ArrivalRadius)
EndFunction

Function GrantKelloggLoot(string why)
    Actor player = Game.GetPlayer()
    if player == None
        return
    endif
    if !brainGranted && CyberBrain != None
        if player.GetItemCount(CyberBrain) <= 0
            player.AddItem(CyberBrain, 1, True)
        endif
        brainGranted = True
        Trace("mq106 cyber_brain granted=true by=" + why)
    endif
    if !passwordGranted && KelloggPassword != None
        if player.GetItemCount(KelloggPassword) <= 0
            player.AddItem(KelloggPassword, 1, True)
        endif
        passwordGranted = True
        Trace("mq106 kellogg_password granted=true by=" + why)
    endif
EndFunction

Function MarkPrydwenArrived(string why)
    if PrydwenArrived != None
        PrydwenArrived.SetValue(1.0)
    endif
    if !prydwenLogged
        prydwenLogged = True
        Trace("mq106 prydwen_arrived=1 by=" + why)
        Trace("mq106 prydwen_stand_in=true kind=global_only")
    endif
EndFunction

Function AdvanceTo(int n, string by = "Trigger")
    pendingStage = n
    pendingStageBy = by
    SetStage(n)
    if n > applied
        applied = n
        Trace("mq106 stage " + n + " by=" + by)
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
        Trace("mq106 stage " + auiStageID + " by=" + cause)
        ApplyStage(auiStageID, cause)
    endif
EndEvent

Function ApplyStage(int n, string by)
    if n == 10
        SetObjectiveDisplayed(10, True, True)
        SetActive(True)
    elseif n == 50
        SetObjectiveCompleted(10)
        SetObjectiveDisplayed(50, True, True)
    elseif n == 75
        SetObjectiveCompleted(10)
        SetObjectiveDisplayed(50, True, True)
    elseif n == 100
        SetObjectiveCompleted(10)
        SetObjectiveCompleted(50)
        SetObjectiveDisplayed(100, True, True)
    elseif n == 125
        SetObjectiveCompleted(10)
        SetObjectiveCompleted(50)
        SetObjectiveDisplayed(100, True, True)
        Actor kel = ResolveKellogg()
        Actor player = Game.GetPlayer()
        if kel != None && !kel.IsDead() && player != None
            kel.SetRestrained(False)
            kel.StartCombat(player)
        endif
    elseif n == 150
        SetObjectiveCompleted(100)
        GrantKelloggLoot(by)
        SetObjectiveDisplayed(150, True, True)
    elseif n == 200
        SetObjectiveCompleted(150)
        GrantKelloggLoot(by)
        MarkPrydwenArrived(by)
        SetObjectiveDisplayed(200, True, True)
    elseif n == 500
        if completed
            return
        endif
        completed = True
        ReleaseAllActors()
        GrantKelloggLoot(by)
        MarkPrydwenArrived(by)
        SetObjectiveCompleted(200)
        if MQ203Armed != None
            MQ203Armed.SetValue(1.0)
        endif
        CompleteQuest()
        CancelTimer(1)
        Quest mq203 = Game.GetFormFromFile(0x000AF0, MissionPlugin) as Quest
        bool started203 = False
        if mq203 != None && !mq203.IsCompleted()
            if mq203.IsRunning()
                FO4SF_MQ203Quest nextMq203 = mq203 as FO4SF_MQ203Quest
                if nextMq203 != None
                    nextMq203.WakeFromPredecessor()
                endif
                started203 = True
            else
                mq203.StartNoWait()
                started203 = True
            endif
        endif
        Trace("mq106 complete stage=500 mq203_armed=1 mq203_started=" + started203 + " prydwen=1 by=" + by)
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
        Trace("mission gate mode=2 started=false quest=mq106")
        Stop()
        return
    endif
    if !CheckPredecessorGate()
        Trace("mq106 gate_deferred reason=mq105_incomplete")
        gateDeferred = True
        instanceStarted = False
        Actor pDefer = Game.GetPlayer()
        if pDefer != None
            RegisterForRemoteEvent(pDefer, "OnPlayerLoadGame")
        endif
        return
    endif
    gateDeferred = False
    if !IsRunning()
        Start()
    endif
    Actor player = Game.GetPlayer()
    if player != None
        RegisterForRemoteEvent(player, "OnPlayerLoadGame")
    endif
    BindRefs()
    AdvanceTo(10, "Trigger")
    if player != None && IsInCellId(player, FortHagen02CellId)
        AdvanceTo(100, "out_of_order")
    elseif player != None && IsInCellId(player, FortHagen01CellId)
        AdvanceTo(75, "out_of_order")
    elseif player != None && IsAtFortHagenExterior(player)
        AdvanceTo(50, "out_of_order")
    endif
    Trace("mq106 init stage=" + EffectiveStage() + " forthagen_plugin=" + Game.IsPluginInstalled(FortHagenPlugin))
    if !completed
        StartTimer(1.0, 1)
    endif
EndFunction

Function WakeFromPredecessor()
    if completed || instanceStarted
        return
    endif
    if CheckPredecessorGate()
        gateDeferred = False
        Trace("mq106 gate_resumed")
        StartQuestInstance()
    endif
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    talkOpen = False
    talkSessionId += 1
    actorsPlaced = False
    talkNearSec = 0.0
    if gateDeferred && !instanceStarted
        WakeFromPredecessor()
        return
    endif
    int st = EffectiveStage()
    Trace("mq106 reload stage=" + st + " complete=" + completed)
    if !completed
        if !IsRunning()
            Start()
        endif
        if applied > GetStage()
            SetStage(applied)
        endif
        roofDoorRef = None
        BindRefs()
        if st >= 150
            GrantKelloggLoot("reload")
        endif
        if st >= 200
            MarkPrydwenArrived("reload")
        endif
        StartTimer(1.0, 1)
    endif
EndEvent

Function TryBindFortHagenRoofDoor()
    string cp = ActiveCorePlugin()
    if cp == ""
        return
    endif
    ObjectReference rd = Game.GetFormFromFile(FortHagenRoofDoorId, cp) as ObjectReference
    if rd != None && rd != roofDoorRef
        roofDoorRef = rd
        RegisterForRemoteEvent(roofDoorRef, "OnActivate")
        Trace("mq106 roof_door bound=true")
    endif
EndFunction

Function BindRefs()
    Actor kel = ResolveKellogg()
    if kel != None && !kel.IsDead()
        kel.SetRestrained(False)
        RegisterForRemoteEvent(kel, "OnDeath")
    endif
    Actor nick = ResolveNick()
    if nick != None && !nick.IsDead()
        nick.AllowPCDialogue(True)
        nick.BlockActivation(False, False)
        RegisterForRemoteEvent(nick, "OnActivate")
    endif
    TryBindFortHagenRoofDoor()
EndFunction

Function ReleaseAllActors()
    Actor kel = ResolveKellogg()
    if kel != None && !kel.IsDead()
        kel.SetRestrained(False)
    endif
    Actor nick = ResolveNick()
    if nick != None && !nick.IsDead()
        nick.SetRestrained(False)
    endif
EndFunction

Function EnsureTerminalProxy(Actor player)
    if TerminalProxyActi == None || player == None
        return
    endif
    if terminalProxyRef != None && !terminalProxyRef.IsDeleted()
        return
    endif
    if IsInCellId(player, FortHagen02CellId) || IsAtFortHagenExterior(player)
        float snapX = player.GetPositionX()
        float snapY = player.GetPositionY()
        float snapZ = player.GetPositionZ()
        terminalProxyRef = player.PlaceAtMe(TerminalProxyActi, 1, True, False, False)
        if terminalProxyRef != None
            if IsCommonwealthExterior(player) && IsPlayerStableAt(player, snapX, snapY, snapZ)
                terminalProxyRef.MoveTo(player, (FortHagenX + 3.0) - snapX, (FortHagenY + 2.0) - snapY, (FortHagenZ + 1.0) - snapZ, False, False)
            else
                terminalProxyRef.MoveTo(player, 2.0, 2.0, 0.5, False, False)
            endif
            RegisterForRemoteEvent(terminalProxyRef, "OnActivate")
            Trace("mq106 terminal proxy spawned")
        endif
    endif
EndFunction

Function PlaceKelloggNearFortHagen(Actor player)
    if !IsCommonwealthExterior(player) || actorsPlaced || EffectiveStage() < 50
        return
    endif
    Actor kel = ResolveKellogg()
    if kel == None || kel.IsDead()
        actorsPlaced = True
        return
    endif
    if kel.IsDisabled()
        kel.EnableNoWait(False)
        BindRefs()
        Trace("mq106 kellogg enabled stage=" + EffectiveStage())
    endif
    float snapX = player.GetPositionX()
    float snapY = player.GetPositionY()
    float snapZ = player.GetPositionZ()
    if !IsPlayerStableAt(player, snapX, snapY, snapZ)
        return
    endif
    kel.SetRestrained(False)
    kel.MoveTo(player, FortHagenX - snapX, FortHagenY - snapY, FortHagenZ - snapZ, False, False)
    if !IsPlayerStableAt(player, snapX, snapY, snapZ)
        return
    endif
    actorsPlaced = True
    Trace("mq106 kellogg placed forthagen=true")
EndFunction

Function CheckNickDebriefFallback(Actor player, int st)
{R3/R4: Enable Nick at stage 200, spawn 360-degree talk proxy, and run timed proximity fallback while alive.}
    if st != 200 || talkOpen || completed || player == None
        talkNearSec = 0.0
        return
    endif
    Actor nick = ResolveNick()
    if nick == None || nick.IsDead()
        talkNearSec = 0.0
        return
    endif
    if nick.IsDisabled()
        nick.EnableNoWait(False)
        BindRefs()
    endif
    if (nickTalkProxy == None || nickTalkProxy.IsDeleted()) && nick.Is3DLoaded()
        Activator talkActi = Game.GetFormFromFile(0x000A8A, MissionPlugin) as Activator
        if talkActi != None
            nickTalkProxy = nick.PlaceAtMe(talkActi, 1, True, False, False)
            if nickTalkProxy != None
                nickTalkProxy.MoveTo(nick, 0.0, 0.0, 1.0, False, False)
                RegisterForRemoteEvent(nickTalkProxy, "OnActivate")
            endif
        endif
    endif
    if nick.Is3DLoaded() && player.GetDistance(nick) <= TalkFallbackRadius
        talkNearSec += 1.0
        if talkNearSec >= TalkFallbackSeconds
            talkNearSec = 0.0
            Trace("mq106 talk_fallback actor=nick stage=200 near_sec=" + TalkFallbackSeconds)
            RunDebriefTalk()
        endif
    else
        talkNearSec = 0.0
    endif
EndFunction

Event Actor.OnDeath(Actor akSender, ObjectReference akKiller)
    if completed
        return
    endif
    Actor kel = ResolveKellogg()
    if akSender == kel && EffectiveStage() < 150
        AdvanceTo(150, "boss_death")
    endif
EndEvent

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

    Actor kel = ResolveKellogg()
    bool inFh1 = IsInCellId(player, FortHagen01CellId)
    bool inFh2 = IsInCellId(player, FortHagen02CellId)
    bool atFhExt = IsAtFortHagenExterior(player)

    if atFhExt && !actorsPlaced
        PlaceKelloggNearFortHagen(player)
    endif
    if atFhExt && (roofDoorRef == None || roofDoorRef.IsDeleted())
        TryBindFortHagenRoofDoor()
    endif
    if inFh2 || atFhExt
        EnsureTerminalProxy(player)
    endif

    ; REUN-01: Direct Fort Hagen arrival advances stage 10 -> 50 even if Dogmeat is downed/absent
    if st < 50 && (atFhExt || inFh1 || inFh2)
        AdvanceTo(50, "Trigger")
        st = EffectiveStage()
    endif
    if st < 75 && inFh1
        AdvanceTo(75, "Trigger")
        st = EffectiveStage()
    endif
    if st < 100 && inFh2
        AdvanceTo(100, "Trigger")
        st = EffectiveStage()
    endif

    ; Hostile Kellogg combat / death / pre-attack (REUN-03)
    if kel != None
        if kel.IsDead() && st < 150
            AdvanceTo(150, "boss_death")
            st = EffectiveStage()
        elseif !kel.IsDead() && st >= 50 && st < 150
            if kel.GetCombatState() != 0
                if st < 125
                    AdvanceTo(125, "combat")
                    st = EffectiveStage()
                endif
            elseif kel.Is3DLoaded() && player.GetDistance(kel) <= EngageRadius
                kel.SetRestrained(False)
                kel.StartCombat(player)
                if st < 125
                    AdvanceTo(125, "combat")
                    st = EffectiveStage()
                endif
            endif
        endif
    endif

    ; REUN-04: Exterior load after stage 150 sets FO4SF_PrydwenArrived=1 -> stage 200
    if st == 150 && IsCommonwealthExterior(player)
        AdvanceTo(200, "exterior_load")
        st = EffectiveStage()
    endif

    ; REUN-05: Open-Mode completion when Nick is dead/unavailable at Diamond City OR direct arrival at Memory Den
    if st == 200
        CheckNickDebriefFallback(player, st)
        if IsInCellId(player, MemoryDenCellId) || IsNearXY(player, GoodneighborX, GoodneighborY, 80.0)
            AdvanceTo(500, "open_mode")
            return
        elseif IsNearXY(player, DiamondCityX, DiamondCityY, 80.0) && IsNickUnavailable()
            RunDossierOpenMode()
            return
        endif
    endif

    if !completed
        StartTimer(1.0, 1)
    endif
EndEvent

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    if completed || akActionRef != Game.GetPlayer()
        return
    endif
    int st = EffectiveStage()
    if akSender == roofDoorRef && st < 50
        AdvanceTo(50, "Trigger")
        return
    endif
    if akSender == terminalProxyRef
        RunTerminalProxy()
        return
    endif
    Actor nick = ResolveNick()
    if ((nick != None && akSender == nick) || (nickTalkProxy != None && akSender == nickTalkProxy)) && st == 200
        RunDebriefTalk()
    endif
EndEvent

Function RunTerminalProxy()
    if talkOpen || TerminalMsg == None
        return
    endif
    talkOpen = True
    talkSessionId += 1
    int sid = talkSessionId
    int btn = TerminalMsg.Show()
    if sid != talkSessionId
        return
    endif
    talkOpen = False
    if btn < 0 || btn == 2
        return
    endif
    GrantKelloggLoot("terminal")
    if EffectiveStage() < 150
        AdvanceTo(150, "open_mode")
    endif
    if IsCommonwealthExterior(Game.GetPlayer()) && EffectiveStage() < 200
        AdvanceTo(200, "terminal")
    endif
EndFunction

Function RunDebriefTalk()
    if talkOpen || DebriefMsg == None
        return
    endif
    talkOpen = True
    talkSessionId += 1
    int sid = talkSessionId
    int btn = DebriefMsg.Show()
    if sid != talkSessionId
        return
    endif
    talkOpen = False
    if btn < 0 || btn == 2
        return
    endif
    AdvanceTo(500, "talk")
EndFunction

Function RunDossierOpenMode()
    if talkOpen
        return
    endif
    if DossierMsg != None
        talkOpen = True
        talkSessionId += 1
        int sid = talkSessionId
        int btn = DossierMsg.Show()
        if sid != talkSessionId
            return
        endif
        talkOpen = False
        if btn < 0 || btn == 1
            return
        endif
    endif
    AdvanceTo(500, "open_mode")
EndFunction

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
