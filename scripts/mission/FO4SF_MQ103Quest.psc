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
 W6 break-it safe: Piper/Mayor/Ellie dead Open-Mode fallbacks (JOTC-01/JOTC-05), out-of-order direct walk to gate
 (JOTC-02), save/reload mid-scene recovery (JOTC-04), and fast travel away resilience.}

Form Property XMarkerBase Auto Const
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
string MissionPlugin = "FO4SFMission.esm"
int GateRefId = 0x013E79
float GateLocalX = -216.36
float GateLocalY = -429.39
float GateLocalZ = 19.20
float MergeOffsetX = -1200.0
float MergeOffsetY = -2700.0
float PlaceRadius = 300.0
float GateProximityRadius = 150.0
float GateOverrideRadius = 8.0

bool instanceStarted = False
bool completed = False
bool gateActorsPlaced = False
bool talkOpen = False
int applied = 0
int pendingStage = -1
string pendingStageBy = "other"
ObjectReference gateRef = None

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

bool Function IsCommonwealthExterior(Actor player)
{B2 guard: reject interiors (e.g. FO4SF_MapMarkersHop 100008F4), null WorldSpace, or out-of-Commonwealth XY before MoveTo.}
    if player == None || player.IsInInterior()
        return False
    endif
    if player.GetWorldSpace() == None
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

bool Function AreGateNpcsDead()
    Actor p = ResolvePiper()
    Actor m = ResolveMayor()
    bool pDead = (p == None || p.IsDead())
    bool mDead = (m == None || m.IsDead())
    return pDead || mDead
EndFunction

bool Function IsEllieDead()
    Actor e = ResolveEllie()
    return e == None || e.IsDead()
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
        gateRef.Lock(False, False)
        gateRef.SetOpen(True)
    endif
    Trace("mq103 gate unlocked by=" + by)
EndFunction

Function ApplyStage(int n, string by)
    if n == 10
        SetObjectiveDisplayed(10, True, True)
        SetActive(True)
    elseif n == 20
        UnlockDiamondCityGate(by)
        SetObjectiveCompleted(10)
        SetObjectiveDisplayed(20, True, True)
    elseif n == 25
        SetObjectiveDisplayed(20, True, True)
    elseif n == 30
        UnlockDiamondCityGate(by)
        SetObjectiveCompleted(20)
        SetObjectiveDisplayed(30, True, True)
    elseif n == 100
        if completed
            return
        endif
        completed = True
        SetObjectiveCompleted(30)
        if MQ104Armed != None
            MQ104Armed.SetValue(1.0)
        endif
        CompleteQuest()
        CancelTimer(1)
        Trace("mq103 complete stage=100 mq104_armed=1 by=" + by)
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
    if !IsRunning()
        Start()
    endif
    Actor player = Game.GetPlayer()
    if player != None
        RegisterForRemoteEvent(player, "OnPlayerLoadGame")
    endif
    BindRefs()
    AdvanceTo(10, "Trigger")
    Trace("mq103 init stage=10 gate_ref=0x013E79")
    StartTimer(1.0, 1)
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    talkOpen = False
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
    if Game.IsPluginInstalled(CorePlugin)
        ObjectReference g = Game.GetFormFromFile(GateRefId, CorePlugin) as ObjectReference
        if g != None && g != gateRef
            gateRef = g
            RegisterForRemoteEvent(gateRef, "OnActivate")
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
    Actor player = Game.GetPlayer()
    if IsCommonwealthExterior(player)
        float gx = GateLocalX + MergeOffsetX
        float gy = GateLocalY + MergeOffsetY
        float gz = GateLocalZ
        float dx = player.GetPositionX() - gx
        float dy = player.GetPositionY() - gy
        float d2 = dx * dx + dy * dy
        if d2 <= PlaceRadius * PlaceRadius && !gateActorsPlaced
            PlaceGateActors(player, gx, gy, gz)
        endif
        ; JOTC-01 Open-Mode gate override if player walks up to gate while Piper/Mayor are dead
        if st == 10 && d2 <= GateOverrideRadius * GateOverrideRadius && AreGateNpcsDead()
            Trace("mq103 open_mode gate_npcs_dead -> unlocking gate")
            AdvanceTo(20, "open_mode")
        endif
    endif
    if gateRef == None
        BindRefs()
    endif
    if !completed
        StartTimer(1.0, 1)
    endif
EndEvent

Function PlaceGateActors(Actor player, float gx, float gy, float gz)
    Actor p = ResolvePiper()
    if p != None && !p.IsDead()
        p.MoveTo(player, (gx - 7.5) - player.GetPositionX(), (gy - 3.5) - player.GetPositionY(), gz - player.GetPositionZ(), False, False)
        p.SetRestrained(True)
        p.AllowPCDialogue(True)
    endif
    Actor m = ResolveMayor()
    if m != None && !m.IsDead()
        m.MoveTo(player, (gx - 2.5) - player.GetPositionX(), (gy - 1.5) - player.GetPositionY(), gz - player.GetPositionZ(), False, False)
        m.SetRestrained(True)
        m.AllowPCDialogue(True)
    endif
    Actor e = ResolveEllie()
    if e != None && !e.IsDead()
        e.MoveTo(player, (gx + 2.5) - player.GetPositionX(), (gy + 2.0) - player.GetPositionY(), gz - player.GetPositionZ(), False, False)
        e.SetRestrained(True)
        e.AllowPCDialogue(True)
    endif
    gateActorsPlaced = True
    Trace("mq103 gate actors placed")
EndFunction

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    if completed || akActionRef != Game.GetPlayer() || talkOpen
        return
    endif
    int st = EffectiveStage()
    Actor p = ResolvePiper()
    Actor m = ResolveMayor()
    Actor e = ResolveEllie()
    if (p != None && akSender == p) || (m != None && akSender == m)
        talkOpen = True
        if st == 10
            if GateTalkMsg != None
                int btn = GateTalkMsg.Show()
                Trace("mq103 gate choice button=" + btn)
            endif
            if GateOpenMsg != None
                GateOpenMsg.Show()
            endif
            AdvanceTo(20, "piper_gate")
            AdvanceTo(30, "piper_lead")
        elseif st == 20 || st == 25
            AdvanceTo(30, "piper_lead")
        endif
        talkOpen = False
    elseif gateRef != None && akSender == gateRef
        ; JOTC-01: activating gate directly unlocks via override if scene skipped or NPCs dead
        if st == 10
            if GateOpenMsg != None
                GateOpenMsg.Show()
            endif
            AdvanceTo(20, "gate_override")
            AdvanceTo(30, "gate_override")
        elseif st == 30 && IsEllieDead()
            ; JOTC-05 Open-Mode dossier fallback if Ellie is dead
            if DossierMsg != None
                DossierMsg.Show()
            endif
            AdvanceTo(100, "dossier")
        endif
    elseif e != None && akSender == e
        talkOpen = True
        if st < 30
            AdvanceTo(30, "out_of_order")
        endif
        if AgencyTalkMsg != None
            int abtn = AgencyTalkMsg.Show()
            Trace("mq103 ellie choice button=" + abtn)
        endif
        AdvanceTo(100, "ellie")
        talkOpen = False
    endif
EndEvent

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
