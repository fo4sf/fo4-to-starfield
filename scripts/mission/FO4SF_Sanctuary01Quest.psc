Scriptname FO4SF_Sanctuary01Quest extends Quest
{Sanctuary settlement quest (FO4SFMission.esm 0x000817, completed IN PLACE from Fallout 4's Min01 0x05DEE4;
 started via StartNoWait when FO4SF_Min00 reaches stage 200; Story mode only via FO4SF_GameMode == 1).
 Preserves stage 10 -> 100 Sanctuary Hills workshop workbench activation (0250FE -> FO4TerrainCore.esm 0x005C50
 of base ACTI 0x0A2ECD at merged -2329.250, -1420.193, 112.086) and continues in place through Sturges'
 Min01 milestones: 5 beds (1000/1050) -> 5 clean water (1200/1250) -> 5 food (1300/1350) -> 2 defense (1400/1450)
 -> completion (1500) + FO4SF_MinRecruit00 (0x000A20) handoff.
 Supports W6 break-it axes: giver dead (Open-Mode workbench fallback), out-of-order pre-built resources (SANC-01),
 save/reload at every stage (SANC-04), and fast travel away (SANC-03).}

Form Property XMarkerBase Auto Const Mandatory

; A4 Min01 in-place properties (optional Auto Const with Game.GetFormFromFile fallbacks so legacy builds stay safe)
Actor Property Sturges Auto Const
GlobalVariable Property BedCount Auto Const
GlobalVariable Property BedTotal Auto Const
GlobalVariable Property BedPercent Auto Const
GlobalVariable Property WaterCount Auto Const
GlobalVariable Property WaterTotal Auto Const
GlobalVariable Property WaterPercent Auto Const
GlobalVariable Property FoodCount Auto Const
GlobalVariable Property FoodTotal Auto Const
GlobalVariable Property FoodPercent Auto Const
GlobalVariable Property SafetyCount Auto Const
GlobalVariable Property SafetyTotal Auto Const
GlobalVariable Property SafetyPercent Auto Const
Message Property SturgesTalkMsg Auto Const
Message Property SturgesReply0Msg Auto Const
Message Property SturgesReply1Msg Auto Const
Message Property SturgesReply2Msg Auto Const
Message Property SturgesDoneMsg Auto Const
Message Property WorkbenchBuildMsg Auto Const

string LogName = "fo4sf_mission"
string CorePlugin = "FO4TerrainCore.esm"
string CoreFallbackPlugin = "FO4TerrainCore_Mars.esm"
string MissionPlugin = "FO4SFMission.esm"
int BenchRefId = 0x005C50
int BenchBaseId = 0x0A2ECD
float BenchLocalX = -1129.250
float BenchLocalY = 1279.807
float BenchLocalZ = 112.086
float SturgesLocalX = -1127.0
float SturgesLocalY = 1281.5
float SturgesLocalZ = 112.1
float MergeOffsetX = -1200.0
float MergeOffsetY = -2700.0
float BindRadius = 300.0
float SearchRadius = 15.0
float BenchFallbackRadius = 3.0
float BenchFallbackLimit = 120.0

bool instanceStarted = False
bool completed = False
bool benchActivated = False
bool sturgesHeld = False
bool talkBoxOpen = False
bool benchMenuOpen = False
bool a4Upgraded = False
bool minRecruitHandoffDone = False
int talkSessionId = 0
int applied = 0
int pendingStage = -1
string pendingStageBy = "other"
ObjectReference markerRef = None
ObjectReference boundBench = None
WorldSpace commonwealthWorld = None
float benchNearSec = 0.0

Actor Function ResolveSturges()
    if Sturges != None
        return Sturges
    endif
    return Game.GetFormFromFile(0x000A01, MissionPlugin) as Actor
EndFunction

GlobalVariable Function ResolveGlob(GlobalVariable propVal, int localId)
    if propVal != None
        return propVal
    endif
    return Game.GetFormFromFile(localId, MissionPlugin) as GlobalVariable
EndFunction

Message Function ResolveMsg(Message propVal, int localId)
    if propVal != None
        return propVal
    endif
    return Game.GetFormFromFile(localId, MissionPlugin) as Message
EndFunction

bool Function HasFullMin01()
    return ResolveGlob(BedTotal, 0x000A03) != None
EndFunction

bool Function IsSturgesDeadOrMissing()
    Actor st = ResolveSturges()
    if st == None
        return True
    endif
    return st.IsDead()
EndFunction

bool Function IsWarfareMode()
    GlobalVariable gm = Game.GetFormFromFile(0x000870, "FO4SFCoreValues.esm") as GlobalVariable
    if gm != None && (gm.GetValue() as int) == 2
        return True
    endif
    return False
EndFunction

int Function EffectiveStage()
{B1/B4 resilience: if engine GetStage() lags behind applied, use applied; if GetStage() advanced (e.g. console setstage), use GetStage().}
    int raw = GetStage()
    if applied > raw
        return applied
    endif
    return raw
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

Function AdvanceTo(int n, string by = "Trigger")
    pendingStage = n
    pendingStageBy = by
    SetStage(n)
    if n > applied
        applied = n
        Trace("sanctuary01 stage " + n + " by=" + by)
        ApplyStage(n, by)
    endif
EndFunction

Event OnStageSet(int auiStageID, int auiItemID)
    if auiStageID > applied
        string cause = "other"
        if auiStageID == pendingStage
            cause = pendingStageBy
        elseif auiStageID == 100 && benchActivated
            cause = "bench"
        endif
        applied = auiStageID
        Trace("sanctuary01 stage " + auiStageID + " by=" + cause)
        ApplyStage(auiStageID, cause)
    endif
EndEvent

Function ApplyStage(int n, string by)
    if n == 50
        SetObjectiveDisplayed(50, True, True)
    elseif n == 100
        SetObjectiveCompleted(10)
        if !HasFullMin01()
            FinishQuest(by)
        else
            ; Full Min01 in place on 0x000817: continue into Sturges / resource milestones
            if IsSturgesDeadOrMissing()
                Trace("sanctuary01 open_mode sturges_unavailable -> stage 1000")
                AdvanceTo(1000, "open_mode")
            else
                SetObjectiveDisplayed(50, True, True)
                Trace("sanctuary01 objective 50 sturges")
            endif
        endif
    elseif n == 1000
        SetObjectiveCompleted(10)
        CleanupMarker()
        SetObjectiveCompleted(50)
        SetObjectiveDisplayed(1000, True, True)
        CheckMilestoneProgress(1000)
    elseif n == 1050
        SetObjectiveCompleted(1000)
        if IsSturgesDeadOrMissing()
            AdvanceTo(1200, "open_mode")
        else
            SetObjectiveDisplayed(1050, True, True)
        endif
    elseif n == 1200
        SetObjectiveCompleted(1050)
        SetObjectiveDisplayed(1200, True, True)
        CheckMilestoneProgress(1200)
    elseif n == 1250
        SetObjectiveCompleted(1200)
        if IsSturgesDeadOrMissing()
            AdvanceTo(1300, "open_mode")
        else
            SetObjectiveDisplayed(1250, True, True)
        endif
    elseif n == 1300
        SetObjectiveCompleted(1250)
        SetObjectiveDisplayed(1300, True, True)
        CheckMilestoneProgress(1300)
    elseif n == 1350
        SetObjectiveCompleted(1300)
        if IsSturgesDeadOrMissing()
            AdvanceTo(1400, "open_mode")
        else
            SetObjectiveDisplayed(1350, True, True)
        endif
    elseif n == 1400
        SetObjectiveCompleted(1350)
        SetObjectiveDisplayed(1400, True, True)
        CheckMilestoneProgress(1400)
    elseif n == 1450
        SetObjectiveCompleted(1400)
        if IsSturgesDeadOrMissing()
            AdvanceTo(1500, "open_mode")
        else
            SetObjectiveDisplayed(1450, True, True)
        endif
    elseif n == 1500
        SetObjectiveCompleted(1450)
        FinishQuest(by)
    endif
EndFunction

Function StartMinRecruit00IfNeeded()
    if minRecruitHandoffDone || IsWarfareMode()
        return
    endif
    Quest firstStep = Game.GetFormFromFile(0x000A20, MissionPlugin) as Quest
    if firstStep != None
        if firstStep.IsRunning() || firstStep.IsCompleted()
            minRecruitHandoffDone = True
        else
            bool startedStep = firstStep.StartNoWait()
            if startedStep || firstStep.IsRunning()
                minRecruitHandoffDone = True
            endif
            Trace("sanctuary01 handoff minrecruit00=started")
        endif
    endif
EndFunction

Function StartMq103StoryHandoffIfNeeded()
    if IsWarfareMode()
        return
    endif
    Quest mq103Quest = Game.GetFormFromFile(0x000A50, MissionPlugin) as Quest
    if mq103Quest != None && !mq103Quest.IsRunning() && !mq103Quest.IsCompleted()
        bool startedMq103 = mq103Quest.StartNoWait()
        Trace("sanctuary01 handoff mq103 start_requested ok=" + startedMq103)
    endif
EndFunction

Function FinishQuest(string by)
    if completed
        StartMinRecruit00IfNeeded()
        return
    endif
    completed = True
    Actor st = ResolveSturges()
    if st != None
        st.SetRestrained(False)
    endif
    sturgesHeld = False
    CompleteQuest()
    CancelTimer(1)
    CleanupMarker()
    Trace("sanctuary01 finished stage=" + EffectiveStage() + " by=" + by)
    StartMinRecruit00IfNeeded()
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
        Trace("mission gate mode=2 started=false quest=sanctuary01")
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
    BindSturges()
    AdvanceTo(10, "Trigger")
    EnsureGuideMarker(player)
    TryBindBench(player)
    SetObjectiveDisplayed(10, True, True)
    SetActive(True)
    StartMq103StoryHandoffIfNeeded()
    Trace("min01 objective 10 bench")
    Trace("sanctuary01 init stage=10 bench_ref=0x005C50")
    Trace("sanctuary01 min01_mode full_min01=" + HasFullMin01())
    StartTimer(1.0, 1)
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    talkSessionId += 1
    talkBoxOpen = False
    benchMenuOpen = False
    sturgesHeld = False
    int st = EffectiveStage()
    Trace("sanctuary01 reload stage=" + st + " complete=" + completed)
    if st == 100 && IsCompleted() && HasFullMin01() && !a4Upgraded
        ; Upgrade a saved legacy 2-stage stub cleanly (never gated on !completed, which serialized True in a1d)
        a4Upgraded = True
        completed = False
        AdvanceTo(1500, "legacy_compat")
        StartMinRecruit00IfNeeded()
        return
    endif
    if completed
        StartMinRecruit00IfNeeded()
        return
    endif
    if !completed
        if !IsRunning()
            Start()
        endif
        if applied > GetStage()
            SetStage(applied)
        endif
        if boundBench != None
            UnregisterForRemoteEvent(boundBench, "OnActivate")
            UnregisterForRemoteEvent(boundBench, "OnWorkshopMode")
            boundBench = None
        endif
        Actor player = Game.GetPlayer()
        BindSturges()
        EnsureGuideMarker(player)
        TryBindBench(player)
        KeepSturges(player)
        CheckMilestoneProgress(st)
        StartTimer(1.0, 1)
    endif
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID != 1
        return
    endif
    int raw = GetStage()
    if raw > applied
        string extCause = "other"
        if raw == pendingStage
            extCause = pendingStageBy
        elseif raw == 100 && benchActivated
            extCause = "bench"
        endif
        applied = raw
        Trace("sanctuary01 stage " + raw + " by=" + extCause)
        ApplyStage(raw, extCause)
    elseif !completed && applied > raw
        if !IsRunning()
            Start()
        endif
        SetStage(applied)
    endif
    int st = EffectiveStage()
    if !completed
        Actor player = Game.GetPlayer()
        KeepSturges(player)
        if st >= 1000 && st < 1500
            CheckMilestoneProgress(st)
        endif
        if boundBench == None || boundBench.IsDeleted()
            EnsureGuideMarker(player)
            TryBindBench(player)
            if st < 100 && (boundBench == None || boundBench.IsDeleted()) && IsCommonwealthExterior(player)
                float dx = player.GetPositionX() - (BenchLocalX + MergeOffsetX)
                float dy = player.GetPositionY() - (BenchLocalY + MergeOffsetY)
                if dx * dx + dy * dy <= BenchFallbackRadius * BenchFallbackRadius
                    benchNearSec += 1.0
                    GlobalVariable tm = Game.GetFormFromFile(0x000860, "FO4SFCoreValues.esm") as GlobalVariable
                    float lim = BenchFallbackLimit
                    if tm != None && tm.GetValue() != 0.0
                        lim = 8.0
                    endif
                    if benchNearSec >= lim
                        benchActivated = True
                        AdvanceTo(100, "fallback")
                        Trace("sanctuary01 fallback unbound_bench near_sec=" + benchNearSec)
                    endif
                else
                    benchNearSec = 0.0
                endif
            endif
        endif
        if !completed
            StartTimer(1.0, 1)
        endif
    endif
EndEvent

Function BindSturges()
    Actor st = ResolveSturges()
    if st != None && !st.IsDead()
        st.AllowPCDialogue(True)
        st.BlockActivation(False, False)
        RegisterForRemoteEvent(st, "OnActivate")
        ReferenceAlias sAlias = GetAlias(1) as ReferenceAlias
        if sAlias != None
            sAlias.ForceRefTo(st)
        endif
    endif
EndFunction

Function KeepSturges(Actor player)
    Actor st = ResolveSturges()
    if st == None || st.IsDead() || !IsCommonwealthExterior(player)
        return
    endif
    if st.GetCombatState() != 0
        if sturgesHeld
            st.SetRestrained(False)
            sturgesHeld = False
        endif
        return
    endif
    float sx = SturgesLocalX + MergeOffsetX
    float sy = SturgesLocalY + MergeOffsetY
    float sz = SturgesLocalZ
    float pdx = player.GetPositionX() - sx
    float pdy = player.GetPositionY() - sy
    if pdx * pdx + pdy * pdy <= BindRadius * BindRadius
        float sdx = st.GetPositionX() - sx
        float sdy = st.GetPositionY() - sy
        if !sturgesHeld || (sdx * sdx + sdy * sdy) > 625.0
            st.SetRestrained(False)
            st.MoveTo(player, sx - player.GetPositionX(), sy - player.GetPositionY(), sz - player.GetPositionZ(), False, False)
            st.SetRestrained(True)
            st.AllowPCDialogue(True)
            st.BlockActivation(False, False)
            sturgesHeld = True
            Trace("sanctuary01 keeper sturges placed held=true")
        endif
    endif
EndFunction

float Function UpdatePercent(GlobalVariable gCount, GlobalVariable gTotal, GlobalVariable gPct, float fallbackTarget)
    float c = 0.0
    float t = fallbackTarget
    if gCount != None
        c = gCount.GetValue()
    endif
    if gTotal != None && gTotal.GetValue() > 0.0
        t = gTotal.GetValue()
    endif
    float pct = (c / t) * 100.0
    if pct > 100.0
        pct = 100.0
    elseif pct < 0.0
        pct = 0.0
    endif
    if gPct != None
        gPct.SetValue(pct)
    endif
    return pct
EndFunction

Function CheckMilestoneProgress(int st)
    if st == 1000
        float bp = UpdatePercent(ResolveGlob(BedCount, 0x000A02), ResolveGlob(BedTotal, 0x000A03), ResolveGlob(BedPercent, 0x000A04), 5.0)
        if bp >= 100.0
            AdvanceTo(1050, "beds")
        endif
    elseif st == 1200
        float wp = UpdatePercent(ResolveGlob(WaterCount, 0x000A05), ResolveGlob(WaterTotal, 0x000A06), ResolveGlob(WaterPercent, 0x000A07), 5.0)
        if wp >= 100.0
            AdvanceTo(1250, "water")
        endif
    elseif st == 1300
        float fp = UpdatePercent(ResolveGlob(FoodCount, 0x000A08), ResolveGlob(FoodTotal, 0x000A09), ResolveGlob(FoodPercent, 0x000A0A), 5.0)
        if fp >= 100.0
            AdvanceTo(1350, "food")
        endif
    elseif st == 1400
        float sp = UpdatePercent(ResolveGlob(SafetyCount, 0x000A0B), ResolveGlob(SafetyTotal, 0x000A0C), ResolveGlob(SafetyPercent, 0x000A0D), 2.0)
        if sp >= 100.0
            AdvanceTo(1450, "defense")
        endif
    endif
EndFunction

Function RunSturgesTalk()
    if talkBoxOpen || completed
        return
    endif
    talkBoxOpen = True
    int mySession = talkSessionId
    int st = EffectiveStage()
    Trace("sanctuary01 sturges talk opened stage=" + st)
    if st == 10 || st == 50 || st == 100
        bool okAdvance = True
        Message mTalk = ResolveMsg(SturgesTalkMsg, 0x000A10)
        if mTalk != None
            int btn = mTalk.Show()
            Trace("sanctuary01 sturges choice button=" + btn)
            if btn < 0
                okAdvance = False
            elseif btn == 0
                Message r0 = ResolveMsg(SturgesReply0Msg, 0x000A11)
                if r0 != None
                    r0.Show()
                endif
            elseif btn == 1
                Message r1 = ResolveMsg(SturgesReply1Msg, 0x000A12)
                if r1 != None
                    r1.Show()
                endif
            elseif btn == 2
                Message r2 = ResolveMsg(SturgesReply2Msg, 0x000A13)
                if r2 != None
                    r2.Show()
                endif
            endif
        endif
        if okAdvance && mySession == talkSessionId
            if st < 100
                SetObjectiveCompleted(10)
                CleanupMarker()
            endif
            AdvanceTo(1000, "sturges")
        endif
    elseif st == 1050
        AdvanceTo(1200, "sturges")
    elseif st == 1250
        AdvanceTo(1300, "sturges")
    elseif st == 1350
        AdvanceTo(1400, "sturges")
    elseif st == 1450
        bool doneOk = True
        Message mDone = ResolveMsg(SturgesDoneMsg, 0x000A14)
        if mDone != None
            if mDone.Show() < 0
                doneOk = False
            endif
        endif
        if doneOk && mySession == talkSessionId
            AdvanceTo(1500, "sturges")
        endif
    endif
    if mySession == talkSessionId
        talkBoxOpen = False
    endif
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

Function EnsureGuideMarker(Actor player)
    if boundBench != None || XMarkerBase == None || !IsCommonwealthExterior(player)
        return
    endif
    float mx = BenchLocalX + MergeOffsetX
    float my = BenchLocalY + MergeOffsetY
    float mz = BenchLocalZ
    if markerRef == None || markerRef.IsDeleted()
        markerRef = player.PlaceAtMe(XMarkerBase, 1, True, False, False)
        if markerRef != None
            float px = player.GetPositionX()
            float py = player.GetPositionY()
            float pz = player.GetPositionZ()
            markerRef.MoveTo(player, mx - px, my - py, mz - pz, False, False)
            ReferenceAlias benchAlias = GetAlias(0) as ReferenceAlias
            if benchAlias != None
                benchAlias.ForceRefTo(markerRef)
            endif
        endif
    endif
EndFunction

Function CleanupMarker()
    if markerRef != None && !markerRef.IsDeleted()
        markerRef.DisableNoWait(False)
        markerRef.Delete()
    endif
    markerRef = None
EndFunction

Function TryBindBench(Actor player)
    if player == None
        return
    endif
    string cName = ActiveCorePlugin()
    if cName == ""
        return
    endif
    float mx = BenchLocalX + MergeOffsetX
    float my = BenchLocalY + MergeOffsetY
    float mz = BenchLocalZ
    ObjectReference cand = Game.GetFormFromFile(BenchRefId, cName) as ObjectReference
    if cand == None && IsCommonwealthExterior(player)
        float dx = player.GetPositionX() - mx
        float dy = player.GetPositionY() - my
        if dx * dx + dy * dy <= BindRadius * BindRadius
            Form benchBase = Game.GetFormFromFile(BenchBaseId, cName)
            if benchBase != None
                cand = Game.FindClosestReferenceOfType(benchBase, mx, my, mz, SearchRadius)
            endif
        endif
    endif
    if cand != None && cand != boundBench
        if boundBench != None
            UnregisterForRemoteEvent(boundBench, "OnActivate")
            UnregisterForRemoteEvent(boundBench, "OnWorkshopMode")
        endif
        boundBench = cand
        RegisterForRemoteEvent(boundBench, "OnActivate")
        RegisterForRemoteEvent(boundBench, "OnWorkshopMode")
        ReferenceAlias benchAlias = GetAlias(0) as ReferenceAlias
        if benchAlias != None
            benchAlias.ForceRefTo(boundBench)
        endif
        CleanupMarker()
        Trace("sanctuary01 bench_bound ref=" + boundBench + " loaded=" + boundBench.Is3DLoaded())
    endif
EndFunction

Function RunWorkbenchBuildMenu()
{Console-free Sanctuary workbench build menu (0xA15): increments Min01 Bed/Water/Food/Safety GLOBs (+1 per click),
 refreshes percent GLOBs, and runs CheckMilestoneProgress so both normal Min01 and SANC-01 pre-building work via
 keyboard+mouse without console commands.}
    if completed || benchMenuOpen || IsWarfareMode()
        return
    endif
    Message bm = ResolveMsg(WorkbenchBuildMsg, 0x000A15)
    if bm == None
        return
    endif
    benchMenuOpen = True
    int mySession = talkSessionId
    Trace("sanctuary01 bench build menu opened stage=" + EffectiveStage())
    int loops = 0
    bool finishedMenu = False
    while !finishedMenu && !completed && loops < 16 && mySession == talkSessionId
        loops += 1
        int btn = bm.Show()
        if btn < 0 || mySession != talkSessionId
            finishedMenu = True
        elseif btn == 0
            GlobalVariable gb = ResolveGlob(BedCount, 0x000A02)
            if gb != None
                float nv = gb.GetValue() + 1.0
                gb.SetValue(nv)
                UpdatePercent(gb, ResolveGlob(BedTotal, 0x000A03), ResolveGlob(BedPercent, 0x000A04), 5.0)
                Trace("sanctuary01 bench build item=bed count=" + nv)
            endif
        elseif btn == 1
            GlobalVariable gw = ResolveGlob(WaterCount, 0x000A05)
            if gw != None
                float nv = gw.GetValue() + 1.0
                gw.SetValue(nv)
                UpdatePercent(gw, ResolveGlob(WaterTotal, 0x000A06), ResolveGlob(WaterPercent, 0x000A07), 5.0)
                Trace("sanctuary01 bench build item=water count=" + nv)
            endif
        elseif btn == 2
            GlobalVariable gf = ResolveGlob(FoodCount, 0x000A08)
            if gf != None
                float nv = gf.GetValue() + 1.0
                gf.SetValue(nv)
                UpdatePercent(gf, ResolveGlob(FoodTotal, 0x000A09), ResolveGlob(FoodPercent, 0x000A0A), 5.0)
                Trace("sanctuary01 bench build item=food count=" + nv)
            endif
        elseif btn == 3
            GlobalVariable gs = ResolveGlob(SafetyCount, 0x000A0B)
            if gs != None
                float nv = gs.GetValue() + 1.0
                gs.SetValue(nv)
                UpdatePercent(gs, ResolveGlob(SafetyTotal, 0x000A0C), ResolveGlob(SafetyPercent, 0x000A0D), 2.0)
                Trace("sanctuary01 bench build item=defense count=" + nv)
            endif
        else
            finishedMenu = True
        endif
        if !finishedMenu
            CheckMilestoneProgress(EffectiveStage())
        endif
    endwhile
    if mySession == talkSessionId
        benchMenuOpen = False
    endif
EndFunction

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    if completed || akActionRef != Game.GetPlayer()
        return
    endif
    Actor st = ResolveSturges()
    if st != None && akSender == st
        RunSturgesTalk()
        return
    endif
    if boundBench != None && akSender == boundBench
        int cur = EffectiveStage()
        if cur < 100
            CompleteSanctuaryObjective(akSender)
            if HasFullMin01() && !completed
                RunWorkbenchBuildMenu()
            endif
            return
        endif
        if IsSturgesDeadOrMissing()
            ; Open-Mode workbench fallback advances resource report stages when Sturges is dead
            if cur == 100
                AdvanceTo(1000, "open_mode")
            elseif cur == 1050
                AdvanceTo(1200, "open_mode")
            elseif cur == 1250
                AdvanceTo(1300, "open_mode")
            elseif cur == 1350
                AdvanceTo(1400, "open_mode")
            elseif cur == 1450
                AdvanceTo(1500, "open_mode")
                return
            endif
        endif
        if HasFullMin01() && !completed
            RunWorkbenchBuildMenu()
        endif
    endif
EndEvent

Event ObjectReference.OnWorkshopMode(ObjectReference akSender, bool aStart)
    if !completed && aStart && boundBench != None && akSender == boundBench && EffectiveStage() < 100
        CompleteSanctuaryObjective(akSender)
    endif
EndEvent

Function CompleteSanctuaryObjective(ObjectReference refUsed)
    if completed || EffectiveStage() >= 100
        return
    endif
    benchActivated = True
    Trace("min01 bench activated -> stage 100")
    Trace("sanctuary01 bench_activated=true ref=" + refUsed + " complete=true")
    AdvanceTo(100, "bench")
EndFunction

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
