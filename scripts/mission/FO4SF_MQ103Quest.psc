Scriptname FO4SF_MQ103Quest extends Quest
{"Jewel of the Commonwealth" (FO4SFMission.esm 0x000A50, source-audited from Fallout 4's MQ103 0x0229E5
 + DialogueDiamondCityEntrance 0x0190BC).
 Story mode only (FO4SF_GameMode 0x000870 == 1; stops silently in Warfare mode == 2).
 Stages:
   10  = Objective 10: Travel to the Diamond City main gate (DmndGateREF 04013E79 / merged -1416.36, -3129.39, 19.20)
   20  = Objective 20: Gate unlocked (FO4SF_DCGateUnlocked=1); enter Diamond City & ask about Shaun
   25  = Directed to Nick Valentine
   30  = Objective 30: Visit Valentine Detective Agency (FO4Port_DmndValentines01 02006B30)
   100 = CompleteQuest -> set FO4SF_MQ104Armed=1 (handoff to Unlikely Valentine / Vault 114 02002593).
 W6 break-it safe: persistent GateProxyActi (0x000A59) + gateRef.DisableNoWait(False) for STAT 0x013E79,
 Piper/Mayor/Ellie dead Open-Mode fallbacks (JOTC-01/JOTC-05), out-of-order direct walk to gate (JOTC-02),
 save/reload mid-scene recovery (JOTC-04), WorldSpace identity guard, and fast travel away resilience.}

Form Property XMarkerBase Auto Const
Activator Property GateProxyActi Auto Const
Actor Property Piper Auto Const
Actor Property Mayor Auto Const
Actor Property Ellie Auto Const
GlobalVariable Property DCGateUnlocked Auto Const
GlobalVariable Property MQ104Armed Auto Const
Message Property GateTalkMsg Auto Const
Message Property GateOpenMsg Auto Const
Message Property AgencyTalkMsg Auto Const
Message Property DossierMsg Auto Const

string LogName = "fo4sf_mission"
string CorePlugin = "FO4TerrainCore.esm"
string CoreFallbackPlugin = "FO4TerrainCore_Mars.esm"
string MissionPlugin = "FO4SFMission.esm"
int GateRefId = 0x013E79
int GateProxyActiId = 0x000A59
float GateLocalX = -216.36
float GateLocalY = -429.39
float GateLocalZ = 19.20
float EllieLocalX = -192.0
float EllieLocalY = -402.0
float EllieLocalZ = 19.3
float MergeOffsetX = -1200.0
float MergeOffsetY = -2700.0
float PlaceRadius = 300.0
float GateProximityRadius = 150.0
float GateOverrideRadius = 8.0
float TalkFallbackRadius = 3.5
float TalkFallbackSeconds = 8.0

bool instanceStarted = False
bool gateDeferred = False
bool completed = False
bool gateActorsPlaced = False
bool elliePlaced = False
bool talkOpen = False
int talkSessionId = 0
int applied = 0
int pendingStage = -1
string pendingStageBy = "other"
ObjectReference gateRef = None
ObjectReference gateMarker = None
ObjectReference gateProxy = None
ObjectReference piperTalkProxy = None
ObjectReference ellieTalkProxy = None
float talkNearSec = 0.0
WorldSpace commonwealthWorld = None

bool Function IsTestModeEnabled()
    GlobalVariable tm = Game.GetFormFromFile(0x000860, "FO4SFCoreValues.esm") as GlobalVariable
    return tm != None && tm.GetValue() != 0.0
EndFunction

bool Function IsSanctuaryOpeningRunning()
    Quest sanc = Game.GetFormFromFile(0x000817, MissionPlugin) as Quest
    return sanc != None && sanc.IsRunning() && !sanc.IsCompleted()
EndFunction

bool Function CheckPredecessorOrGateProximity(Actor player)
{R1/R5: Deliberate one-tracked-opening-mission design (in FO4 MQ103 starts when MQ102 ends while Min01 runs): requires Sanctuary01 completion OR physical arrival at Diamond City gate (< 150 m) OR TestMode.
 S9: Holds strictly OFF while FO4SF_S9_HardStopAtMin01_1000 (0x000BF5) is non-zero.}
    GlobalVariable s9HardStop = Game.GetFormFromFile(0x000BF5, MissionPlugin) as GlobalVariable
    if s9HardStop != None && s9HardStop.GetValue() != 0.0
        return False
    endif
    if IsTestModeEnabled()
        return True
    endif
    Quest min00 = Game.GetFormFromFile(0x000800, MissionPlugin) as Quest
    if min00 != None && !min00.IsCompleted() && min00.GetStage() < 200
        return False
    endif
    if !IsSanctuaryOpeningRunning()
        return True
    endif
    if IsCommonwealthExterior(player)
        float dx = player.GetPositionX() - (GateLocalX + MergeOffsetX)
        float dy = player.GetPositionY() - (GateLocalY + MergeOffsetY)
        if dx * dx + dy * dy <= GateProximityRadius * GateProximityRadius
            return True
        endif
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
{B1/B4 resilience: max(GetStage(), applied) so lagged engine GetStage() never stalls gate talk or stage handlers.}
    int raw = GetStage()
    if applied > raw
        return applied
    endif
    return raw
EndFunction

string Function ActiveCorePlugin()
    if Game.IsPluginInstalled(CorePlugin)
        return CorePlugin
    endif
    if Game.IsPluginInstalled(CoreFallbackPlugin)
        return CoreFallbackPlugin
    endif
    return ""
EndFunction

WorldSpace Function ResolveCommonwealthWorld()
    if commonwealthWorld != None
        return commonwealthWorld
    endif
    string cName = ActiveCorePlugin()
    if cName != ""
        ObjectReference v111Marker = Game.GetFormFromFile(0x0A775B, cName) as ObjectReference
        if v111Marker != None
            commonwealthWorld = v111Marker.GetWorldSpace()
            if commonwealthWorld != None
                return commonwealthWorld
            endif
        endif
        WorldSpace coreWs = Game.GetFormFromFile(0x000803, cName) as WorldSpace
        if coreWs != None
            commonwealthWorld = coreWs
            return commonwealthWorld
        endif
    endif
    return None
EndFunction

bool Function IsCommonwealthExterior(Actor player)
{B2 + WorldSpace identity guard: rejects interiors (FO4SF_MapMarkersHop 100008F4), New Atlantis / alien planets,
 and out-of-Commonwealth XY before any MoveTo/PlaceAt.}
    if player == None || player.IsInInterior()
        return False
    endif
    WorldSpace ws = player.GetWorldSpace()
    if ws == None
        return False
    endif
    WorldSpace wantWs = ResolveCommonwealthWorld()
    if wantWs == None || ws != wantWs
        return False
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    if px < MergeOffsetX - 3200.0 || px > MergeOffsetX + 3200.0 || py < MergeOffsetY - 3200.0 || py > MergeOffsetY + 3200.0
        return False
    endif
    return True
EndFunction

Actor Function ResolvePiper()
    if Piper != None
        return Piper
    endif
    return Game.GetFormFromFile(0x000A52, MissionPlugin) as Actor
EndFunction

Actor Function ResolveMayor()
    if Mayor != None
        return Mayor
    endif
    return Game.GetFormFromFile(0x000A54, MissionPlugin) as Actor
EndFunction

Actor Function ResolveEllie()
    if Ellie != None
        return Ellie
    endif
    return Game.GetFormFromFile(0x000A56, MissionPlugin) as Actor
EndFunction

Activator Function ResolveGateProxyBase()
    if GateProxyActi != None
        return GateProxyActi
    endif
    return Game.GetFormFromFile(GateProxyActiId, MissionPlugin) as Activator
EndFunction

bool Function AreGateNpcsDead()
    Actor p = ResolvePiper()
    Actor m = ResolveMayor()
    bool pDead = (p == None || p.IsDead())
    bool mDead = (m == None || m.IsDead())
    return pDead && mDead
EndFunction

bool Function IsEllieDead()
    Actor e = ResolveEllie()
    return e == None || e.IsDead()
EndFunction

Function CleanupGateMarker()
    if gateMarker != None && !gateMarker.IsDeleted()
        gateMarker.DisableNoWait(False)
        gateMarker.Delete()
    endif
    gateMarker = None
EndFunction

Function CleanupGateProxy()
    if gateProxy != None
        UnregisterForRemoteEvent(gateProxy, "OnActivate")
        if !gateProxy.IsDeleted()
            gateProxy.DisableNoWait(False)
            gateProxy.Delete()
        endif
    endif
    gateProxy = None
EndFunction

Function ReleaseActors()
    Actor p = ResolvePiper()
    if p != None
        p.SetRestrained(False)
    endif
    Actor m = ResolveMayor()
    if m != None
        m.SetRestrained(False)
    endif
    Actor e = ResolveEllie()
    if e != None
        e.SetRestrained(False)
    endif
EndFunction

Function CheckCombatReleases()
    Actor p = ResolvePiper()
    if p != None && !p.IsDead() && p.GetCombatState() != 0
        p.SetRestrained(False)
    endif
    Actor m = ResolveMayor()
    if m != None && !m.IsDead() && m.GetCombatState() != 0
        m.SetRestrained(False)
    endif
    Actor e = ResolveEllie()
    if e != None && !e.IsDead() && e.GetCombatState() != 0
        e.SetRestrained(False)
    endif
EndFunction

Function AdvanceTo(int n, string by = "Trigger")
    pendingStage = n
    pendingStageBy = by
    SetStage(n)
    if n > applied
        applied = n
        Trace("mq103 stage " + n + " by=" + by)
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
        Trace("mq103 stage " + auiStageID + " by=" + cause)
        ApplyStage(auiStageID, cause)
    endif
EndEvent

Function UnlockDiamondCityGate(string by)
    if DCGateUnlocked != None
        DCGateUnlocked.SetValue(1.0)
    endif
    if gateRef != None
        ; 0x013E79 is a STAT door mesh in FO4TerrainCore.esm: disable collision mesh as well as Lock/SetOpen
        gateRef.DisableNoWait(False)
        gateRef.Lock(False, False)
        gateRef.SetOpen(True)
    endif
    Trace("mq103 gate unlocked by=" + by)
EndFunction

Function ApplyStage(int n, string by)
    if n == 10
        SetObjectiveDisplayed(10, True, True)
        ; R1: Never steal HUD SetActive(True) while Sanctuary01 (First Settlement) is still active
        if !IsSanctuaryOpeningRunning()
            SetActive(True)
        endif
    elseif n == 20
        UnlockDiamondCityGate(by)
        SetObjectiveCompleted(10)
        CleanupGateMarker()
        SetObjectiveDisplayed(20, True, True)
    elseif n == 25
        SetObjectiveDisplayed(20, True, True)
    elseif n == 30
        UnlockDiamondCityGate(by)
        SetObjectiveCompleted(10)
        CleanupGateMarker()
        SetObjectiveCompleted(20)
        SetObjectiveDisplayed(30, True, True)
    elseif n == 100
        if completed
            return
        endif
        completed = True
        SetObjectiveCompleted(10)
        SetObjectiveCompleted(20)
        SetObjectiveCompleted(30)
        CleanupGateMarker()
        CleanupGateProxy()
        ReleaseActors()
        if MQ104Armed != None
            MQ104Armed.SetValue(1.0)
        endif
        CompleteQuest()
        CancelTimer(1)
        Trace("mq103 complete stage=100 mq104_armed=1 by=" + by)
        if !IsWarfareMode()
            Quest mq104Quest = Game.GetFormFromFile(0x000A80, MissionPlugin) as Quest
            if mq104Quest != None && !mq104Quest.IsCompleted()
                if mq104Quest.IsRunning()
                    FO4SF_MQ104Quest nextMq104 = mq104Quest as FO4SF_MQ104Quest
                    if nextMq104 != None
                        nextMq104.WakeFromPredecessor()
                    endif
                else
                    bool startedMq104 = mq104Quest.StartNoWait()
                    Trace("mq104 start_requested ok=" + startedMq104)
                endif
            endif
        endif
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
        Trace("mission gate mode=2 started=false quest=mq103")
        Stop()
        return
    endif
    Actor player = Game.GetPlayer()
    if !CheckPredecessorOrGateProximity(player)
        ; R1: Deliberate one-tracked-opening-mission choice (in FO4 MQ103 starts after MQ102 while Min01 runs).
        ; Stay dormant on RunOnce quest (never Stop()) so Sanctuary01 completion or reload can wake it.
        Trace("mq103 gate_deferred reason=opening_active")
        gateDeferred = True
        instanceStarted = False
        if player != None
            RegisterForRemoteEvent(player, "OnPlayerLoadGame")
        endif
        return
    endif
    gateDeferred = False
    if !IsRunning()
        Start()
    endif
    if player != None
        RegisterForRemoteEvent(player, "OnPlayerLoadGame")
    endif
    BindRefs()
    AdvanceTo(10, "Trigger")
    if player != None
        EnsureGateMarkerAndProxy(player)
    endif
    Trace("mq103 init stage=10 gate_ref=0x013E79")
    StartTimer(1.0, 1)
EndFunction

Function WakeFromPredecessor()
    if completed || instanceStarted
        return
    endif
    if CheckPredecessorOrGateProximity(Game.GetPlayer())
        gateDeferred = False
        Trace("mq103 gate_resumed")
        StartQuestInstance()
    endif
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    talkSessionId += 1
    talkOpen = False
    gateActorsPlaced = False
    elliePlaced = False
    talkNearSec = 0.0
    commonwealthWorld = None
    if gateDeferred && !instanceStarted
        WakeFromPredecessor()
        return
    endif
    int st = EffectiveStage()
    Trace("mq103 reload stage=" + st + " complete=" + completed)
    if !completed
        if !IsRunning()
            Start()
        endif
        if applied > GetStage()
            SetStage(applied)
        endif
        gateRef = None
        BindRefs()
        if gateProxy != None && !gateProxy.IsDeleted()
            RegisterForRemoteEvent(gateProxy, "OnActivate")
        endif
        if gateMarker != None && !gateMarker.IsDeleted() && st < 20
            ReferenceAlias gateAlias = GetAlias(0) as ReferenceAlias
            if gateAlias != None
                gateAlias.ForceRefTo(gateMarker)
            endif
        endif
        if st >= 20
            UnlockDiamondCityGate("reload")
        endif
        StartTimer(1.0, 1)
    endif
EndEvent

Function BindRefs()
    Actor p = ResolvePiper()
    if p != None && !p.IsDead()
        p.AllowPCDialogue(True)
        p.BlockActivation(False, False)
        RegisterForRemoteEvent(p, "OnActivate")
    endif
    Actor m = ResolveMayor()
    if m != None && !m.IsDead()
        m.AllowPCDialogue(True)
        m.BlockActivation(False, False)
        RegisterForRemoteEvent(m, "OnActivate")
    endif
    Actor e = ResolveEllie()
    if e != None && !e.IsDead()
        e.AllowPCDialogue(True)
        e.BlockActivation(False, False)
        RegisterForRemoteEvent(e, "OnActivate")
    endif
    string cName = ActiveCorePlugin()
    if cName != ""
        ObjectReference g = Game.GetFormFromFile(GateRefId, cName) as ObjectReference
        if g != None && g != gateRef
            gateRef = g
            RegisterForRemoteEvent(gateRef, "OnActivate")
            if EffectiveStage() >= 20
                UnlockDiamondCityGate("late_bind")
            endif
        endif
    endif
EndFunction

Function EnsureGateMarkerAndProxy(Actor player)
    if !IsCommonwealthExterior(player)
        return
    endif
    float gx = GateLocalX + MergeOffsetX
    float gy = GateLocalY + MergeOffsetY
    float gz = GateLocalZ
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float pz = player.GetPositionZ()
    if EffectiveStage() < 20 && XMarkerBase != None && (gateMarker == None || gateMarker.IsDeleted())
        gateMarker = player.PlaceAtMe(XMarkerBase, 1, True, False, False)
        if gateMarker != None
            gateMarker.MoveTo(player, gx - px, gy - py, gz - pz, False, False)
            ReferenceAlias gateAlias = GetAlias(0) as ReferenceAlias
            if gateAlias != None
                gateAlias.ForceRefTo(gateMarker)
            endif
        endif
    endif
    float dx = px - gx
    float dy = py - gy
    if dx * dx + dy * dy <= PlaceRadius * PlaceRadius && (gateProxy == None || gateProxy.IsDeleted())
        Activator proxyBase = ResolveGateProxyBase()
        if proxyBase != None
            gateProxy = player.PlaceAtMe(proxyBase, 1, True, False, False)
            if gateProxy != None
                gateProxy.MoveTo(player, gx - px, gy - py, (gz + 1.2) - pz, False, False)
                RegisterForRemoteEvent(gateProxy, "OnActivate")
                Trace("mq103 gate proxy spawned")
            endif
        endif
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
    CheckCombatReleases()
    Actor player = Game.GetPlayer()
    if IsCommonwealthExterior(player)
        EnsureGateMarkerAndProxy(player)
        float gx = GateLocalX + MergeOffsetX
        float gy = GateLocalY + MergeOffsetY
        float gz = GateLocalZ
        float dx = player.GetPositionX() - gx
        float dy = player.GetPositionY() - gy
        float d2 = dx * dx + dy * dy
        if d2 <= PlaceRadius * PlaceRadius
            PlaceGateActors(player, gx, gy, gz)
            PlaceEllieAtAgency(player)
        endif
        ; JOTC-01 Open-Mode gate override if player walks up to gate while BOTH Piper and Mayor are dead
        if st == 10 && d2 <= GateOverrideRadius * GateOverrideRadius && AreGateNpcsDead()
            Trace("mq103 open_mode gate_npcs_dead -> unlocking gate")
            AdvanceTo(20, "open_mode")
            AdvanceTo(30, "open_mode")
        elseif st == 20 && AreGateNpcsDead()
            AdvanceTo(30, "open_mode")
        endif
        CheckTalkFallback(player, st)
    endif
    if gateRef == None
        BindRefs()
    endif
    if !completed
        StartTimer(1.0, 1)
    endif
EndEvent

Function PlaceGateActors(Actor player, float gx, float gy, float gz)
{Places only Piper and Mayor outside the Diamond City main gate (R3: enables them only when MQ103 reaches DC). Ellie stays post-gate at Valentine's Agency.}
    Actor p = ResolvePiper()
    if p != None && !p.IsDead()
        if p.IsDisabled()
            p.EnableNoWait(False)
            BindRefs()
        endif
        if p.GetCombatState() == 0
            float txp = gx - 7.5
            float typ = gy - 3.5
            float dpx = p.GetPositionX() - txp
            float dpy = p.GetPositionY() - typ
            if !gateActorsPlaced || (dpx * dpx + dpy * dpy) > 625.0
                p.SetRestrained(False)
                p.MoveTo(player, txp - player.GetPositionX(), typ - player.GetPositionY(), gz - player.GetPositionZ(), False, False)
                p.SetRestrained(True)
                p.AllowPCDialogue(True)
                p.BlockActivation(False, False)
            endif
            if piperTalkProxy == None || piperTalkProxy.IsDeleted()
                Activator talkActi = Game.GetFormFromFile(0x000A5A, MissionPlugin) as Activator
                if talkActi != None
                    piperTalkProxy = p.PlaceAtMe(talkActi, 1, True, False, False)
                    if piperTalkProxy != None
                        piperTalkProxy.MoveTo(p, 0.0, 0.0, 1.0, False, False)
                        RegisterForRemoteEvent(piperTalkProxy, "OnActivate")
                    endif
                endif
            endif
        endif
    endif
    Actor m = ResolveMayor()
    if m != None && !m.IsDead()
        if m.IsDisabled()
            m.EnableNoWait(False)
            BindRefs()
        endif
        if m.GetCombatState() == 0
            float txm = gx - 2.5
            float tym = gy - 1.5
            float dmx = m.GetPositionX() - txm
            float dmy = m.GetPositionY() - tym
            if !gateActorsPlaced || (dmx * dmx + dmy * dmy) > 625.0
                m.SetRestrained(False)
                m.MoveTo(player, txm - player.GetPositionX(), tym - player.GetPositionY(), gz - player.GetPositionZ(), False, False)
                m.SetRestrained(True)
                m.AllowPCDialogue(True)
                m.BlockActivation(False, False)
            endif
        endif
    endif
    if !gateActorsPlaced
        gateActorsPlaced = True
        Trace("mq103 gate actors placed")
    endif
EndFunction

Function PlaceEllieAtAgency(Actor player)
{Places Ellie at her post-gate Valentine's Agency coordinates (R3: enables Ellie only at stage >= 20).}
    if EffectiveStage() < 20
        return
    endif
    Actor e = ResolveEllie()
    if e == None || e.IsDead()
        return
    endif
    if e.IsDisabled()
        e.EnableNoWait(False)
        BindRefs()
    endif
    if e.GetCombatState() != 0
        return
    endif
    float ex = EllieLocalX + MergeOffsetX
    float ey = EllieLocalY + MergeOffsetY
    float ez = EllieLocalZ
    float edx = e.GetPositionX() - ex
    float edy = e.GetPositionY() - ey
    if !elliePlaced || (edx * edx + edy * edy) > 625.0
        e.SetRestrained(False)
        e.MoveTo(player, ex - player.GetPositionX(), ey - player.GetPositionY(), ez - player.GetPositionZ(), False, False)
        e.SetRestrained(True)
        e.AllowPCDialogue(True)
        e.BlockActivation(False, False)
        elliePlaced = True
        Trace("mq103 ellie placed post_gate")
    endif
    if ellieTalkProxy == None || ellieTalkProxy.IsDeleted()
        Activator talkActi = Game.GetFormFromFile(0x000A5C, MissionPlugin) as Activator
        if talkActi != None
            ellieTalkProxy = e.PlaceAtMe(talkActi, 1, True, False, False)
            if ellieTalkProxy != None
                ellieTalkProxy.MoveTo(e, 0.0, 0.0, 1.0, False, False)
                RegisterForRemoteEvent(ellieTalkProxy, "OnActivate")
            endif
        endif
    endif
EndFunction

Function RunGateTalk(int st)
    if talkOpen || completed
        return
    endif
    talkOpen = True
    int mySession = talkSessionId
    if st == 10
        bool okAdvance = True
        if GateTalkMsg != None
            int btn = GateTalkMsg.Show()
            Trace("mq103 gate choice button=" + btn)
            if btn < 0 || mySession != talkSessionId
                okAdvance = False
            endif
        endif
        if okAdvance
            if GateOpenMsg != None
                GateOpenMsg.Show()
            endif
            if mySession == talkSessionId
                AdvanceTo(20, "piper_gate")
                AdvanceTo(30, "piper_lead")
            endif
        endif
    elseif st == 20 || st == 25
        AdvanceTo(30, "piper_lead")
    endif
    if mySession == talkSessionId
        talkOpen = False
    endif
EndFunction

Function RunEllieTalk(int st)
    if talkOpen || completed
        return
    endif
    talkOpen = True
    int mySession = talkSessionId
    bool okEllie = True
    if AgencyTalkMsg != None
        int abtn = AgencyTalkMsg.Show()
        Trace("mq103 ellie choice button=" + abtn)
        if abtn < 0 || mySession != talkSessionId
            okEllie = False
        endif
    endif
    if okEllie
        if st < 30
            AdvanceTo(30, "out_of_order")
        endif
        AdvanceTo(100, "ellie")
    endif
    if mySession == talkSessionId
        talkOpen = False
    endif
EndFunction

Function CheckTalkFallback(Actor player, int st)
{R4: Timed proximity fallback while Piper/Mayor or Ellie is alive so topicless OnActivate never stalls.}
    if talkOpen || completed || player == None
        talkNearSec = 0.0
        return
    endif
    if st == 10
        Actor p = ResolvePiper()
        Actor m = ResolveMayor()
        bool nearP = (p != None && !p.IsDead() && !p.IsDisabled() && p.Is3DLoaded() && player.GetDistance(p) <= TalkFallbackRadius)
        bool nearM = (m != None && !m.IsDead() && !m.IsDisabled() && m.Is3DLoaded() && player.GetDistance(m) <= TalkFallbackRadius)
        if nearP || nearM
            talkNearSec += 1.0
            if talkNearSec >= TalkFallbackSeconds
                talkNearSec = 0.0
                Trace("mq103 talk_fallback actor=piper_gate stage=10 near_sec=" + TalkFallbackSeconds)
                RunGateTalk(st)
            endif
            return
        endif
    elseif st >= 20 && st <= 30
        Actor e = ResolveEllie()
        if e != None && !e.IsDead() && !e.IsDisabled() && e.Is3DLoaded() && player.GetDistance(e) <= TalkFallbackRadius
            talkNearSec += 1.0
            if talkNearSec >= TalkFallbackSeconds
                talkNearSec = 0.0
                Trace("mq103 talk_fallback actor=ellie stage=" + st + " near_sec=" + TalkFallbackSeconds)
                RunEllieTalk(st)
            endif
            return
        endif
    endif
    talkNearSec = 0.0
EndFunction

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    if completed || akActionRef != Game.GetPlayer() || talkOpen
        return
    endif
    int st = EffectiveStage()
    Actor p = ResolvePiper()
    Actor m = ResolveMayor()
    Actor e = ResolveEllie()
    if (p != None && akSender == p) || (m != None && akSender == m) || (piperTalkProxy != None && akSender == piperTalkProxy)
        RunGateTalk(st)
    elseif (gateProxy != None && akSender == gateProxy) || (gateRef != None && akSender == gateRef)
        ; JOTC-01 / JOTC-05: persistent GateProxyActi (and gateRef fallback) unlocks gate or reads dead-Ellie dossier
        talkOpen = True
        int mySession = talkSessionId
        if st == 10
            bool okGate = True
            if GateOpenMsg != None
                int gbtn = GateOpenMsg.Show()
                if gbtn < 0 || mySession != talkSessionId
                    okGate = False
                endif
            endif
            if okGate
                AdvanceTo(20, "gate_override")
                AdvanceTo(30, "gate_override")
            endif
        elseif st >= 20 && st <= 30 && IsEllieDead()
            bool okDossier = True
            if DossierMsg != None
                int dbtn = DossierMsg.Show()
                if dbtn < 0 || mySession != talkSessionId
                    okDossier = False
                endif
            endif
            if okDossier
                AdvanceTo(100, "dossier")
            endif
        endif
        if mySession == talkSessionId
            talkOpen = False
        endif
    elseif (e != None && akSender == e) || (ellieTalkProxy != None && akSender == ellieTalkProxy)
        RunEllieTalk(st)
    endif
EndEvent

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
