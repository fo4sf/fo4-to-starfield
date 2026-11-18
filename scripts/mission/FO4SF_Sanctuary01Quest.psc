Scriptname FO4SF_Sanctuary01Quest extends Quest
{First settlement objective quest (FO4SFMission.esm 0x000817, started via StartNoWait when FO4SF_Min00 reaches stage 200).
 Points HUD objective 10 at the Sanctuary Hills workshop workbench (Fallout4.esm 0250FE -> FO4TerrainCore.esm 0x005C50 of
 base ACTI 0x0A2ECD at merged coordinates -2329.250, -1420.193, 112.086) and completes stage 100 on bench activation.}

Form Property XMarkerBase Auto Const Mandatory

string LogName = "fo4sf_mission"
string CorePlugin = "FO4TerrainCore.esm"
string CoreFallbackPlugin = "FO4TerrainCore_Mars.esm"
int BenchRefId = 0x005C50
int BenchBaseId = 0x0A2ECD
float BenchLocalX = -1129.250
float BenchLocalY = 1279.807
float BenchLocalZ = 112.086
float MergeOffsetX = -1200.0
float MergeOffsetY = -2700.0
float BindRadius = 300.0
float SearchRadius = 15.0

bool instanceStarted = False
bool completed = False
bool benchActivated = False
int applied = 0
int pendingStage = -1
string pendingStageBy = "other"
ObjectReference markerRef = None
ObjectReference boundBench = None
float benchNearSec = 0.0
float BenchFallbackRadius = 3.0
float BenchFallbackLimit = 120.0

Function AdvanceTo(int n, string by = "trigger")
    pendingStage = n
    pendingStageBy = by
    SetStage(n)
    if n > applied
        applied = n
        Trace("sanctuary01 stage " + n + " by=" + by)
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
    endif
EndEvent

bool Function IsWarfareMode()
    GlobalVariable gm = Game.GetFormFromFile(0x000870, "FO4SFCoreValues.esm") as GlobalVariable
    if gm != None && (gm.GetValue() as int) == 2
        return True
    endif
    return False
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
    Actor player = Game.GetPlayer()
    if player != None
        RegisterForRemoteEvent(player, "OnPlayerLoadGame")
    endif
    AdvanceTo(10, "trigger")
    EnsureGuideMarker(player)
    TryBindBench(player)
    SetObjectiveDisplayed(10, True, True)
    SetActive(True)
    Trace("min01 objective 10 bench")
    Trace("sanctuary01 init stage=10 bench_ref=0x005C50")
    StartTimer(1.0, 1)
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    Trace("sanctuary01 reload stage=" + GetStage() + " complete=" + completed)
    if !completed
        if boundBench != None
            UnregisterForRemoteEvent(boundBench, "OnActivate")
            UnregisterForRemoteEvent(boundBench, "OnWorkshopMode")
            boundBench = None
        endif
        Actor player = Game.GetPlayer()
        EnsureGuideMarker(player)
        TryBindBench(player)
        StartTimer(1.0, 1)
    endif
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID != 1
        return
    endif
    int st = GetStage()
    if st > applied
        string extCause = "other"
        if st == pendingStage
            extCause = pendingStageBy
        elseif st == 100 && benchActivated
            extCause = "bench"
        endif
        applied = st
        Trace("sanctuary01 stage " + st + " by=" + extCause)
    endif
    if !completed
        Actor player = Game.GetPlayer()
        if boundBench == None || boundBench.IsDeleted()
            EnsureGuideMarker(player)
            TryBindBench(player)
            if (boundBench == None || boundBench.IsDeleted()) && player != None && !player.IsInInterior()
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
                        completed = True
                        AdvanceTo(100, "fallback")
                        SetObjectiveCompleted(10)
                        CompleteQuest()
                        CancelTimer(1)
                        CleanupMarker()
                        Trace("sanctuary01 fallback unbound_bench near_sec=" + benchNearSec)
                        return
                    endif
                else
                    benchNearSec = 0.0
                endif
            endif
        endif
        StartTimer(1.0, 1)
    endif
EndEvent

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
    if boundBench != None || player == None || XMarkerBase == None
        return
    endif
    if player.IsInInterior()
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
    if cand == None && !player.IsInInterior()
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

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    if !completed && boundBench != None && akSender == boundBench && akActionRef == Game.GetPlayer()
        CompleteSanctuaryObjective(akSender)
    endif
EndEvent

Event ObjectReference.OnWorkshopMode(ObjectReference akSender, bool aStart)
    if !completed && aStart && boundBench != None && akSender == boundBench
        CompleteSanctuaryObjective(akSender)
    endif
EndEvent

Function CompleteSanctuaryObjective(ObjectReference refUsed)
    if completed || GetStage() >= 100
        return
    endif
    completed = True
    benchActivated = True
    AdvanceTo(100, "bench")
    SetObjectiveCompleted(10)
    CompleteQuest()
    CancelTimer(1)
    CleanupMarker()
    Trace("min01 bench activated -> stage 100")
    Trace("sanctuary01 bench_activated=true ref=" + refUsed + " complete=true")
EndFunction

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
