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
; R11-fix #2: Clean Sanctuary bench swap is OFF by default in candidate-2g-fix (also controlled by FO4SFWorkshop.esm:0x00084A)
bool Property EnableCleanBenchSwap = False Auto

string LogName = "fo4sf_mission"
string CorePlugin = "FO4TerrainCore.esm"
string CoreFallbackPlugin = "FO4TerrainCore_Mars.esm"
string MissionPlugin = "FO4SFMission.esm"
string WorkshopPlugin = "FO4SFWorkshop.esm"
int BenchRefId = 0x005C50
int BenchBaseId = 0x0A2ECD
int CleanBenchBaseId = 0x000849
int CleanBenchSwapGlobId = 0x00084A
float CleanBenchSelfHealSeconds = 3.5
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
float TalkFallbackRadius = 3.5
float TalkFallbackSeconds = 8.0

bool instanceStarted = False
bool completed = False
bool benchActivated = False
bool sturgesHeld = False
bool sturgesArrivedS9 = False
bool talkBoxOpen = False
bool benchMenuOpen = False
bool workshopModeActive = False
bool workshopMenuOpen = False
bool cleanBenchVerifyPending = False
bool cleanBenchSawWorkshop = False
bool cleanBenchSelfHealed = False
bool a4Upgraded = False
bool minRecruitHandoffDone = False
int talkSessionId = 0
int applied = 0
int pendingStage = -1
string pendingStageBy = "other"
ObjectReference markerRef = None
ObjectReference sturgesTalkProxy = None
float sturgesNearSec = 0.0
ObjectReference boundBench = None
ObjectReference sanctuaryBenchOverride = None
ObjectReference coreBenchDisabled = None
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
{R11-fix #3: Treat Sturges not yet arrived from S9 (!IsSturgesReadyForSanctuary()) identically to missing/dead
 so stage 100 never shows objective 50 ("Talk to Sturges") while Sturges is disabled.}
    Actor st = ResolveSturges()
    if st == None || st.IsDead()
        return True
    endif
    if !IsSturgesReadyForSanctuary()
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

bool Function HasS9HardStop()
    GlobalVariable hs = Game.GetFormFromFile(0x000BF5, MissionPlugin) as GlobalVariable
    return hs != None && hs.GetValue() != 0.0
EndFunction

Function EngageTarget(Actor akAttacker, Actor akTarget) global
    if akAttacker != None && akTarget != None && !akAttacker.IsDead()
        akAttacker.StartCombat(akTarget)
    endif
EndFunction

bool Function IsTestModeEnabled()
    GlobalVariable tm = Game.GetFormFromFile(0x000860, "FO4SFCoreValues.esm") as GlobalVariable
    return tm != None && tm.GetValue() != 0.0
EndFunction

Function RegisterMenuGuards()
{A2.1: Track workshop and interactive menus so Sturges talk fallback can NEVER count or fire while any menu is open.}
    RegisterForMenuOpenCloseEvent("WorkshopMenu")
    RegisterForMenuOpenCloseEvent("WorkshopBuilderMenu")
    RegisterForMenuOpenCloseEvent("WorkshopQuickMenu")
    RegisterForMenuOpenCloseEvent("Workshop_BlueprintMenu")
    RegisterForMenuOpenCloseEvent("DialogueMenu")
    RegisterForMenuOpenCloseEvent("MessageBoxMenu")
    RegisterForMenuOpenCloseEvent("ContainerMenu")
    RegisterForMenuOpenCloseEvent("BarterMenu")
    RegisterForMenuOpenCloseEvent("TerminalMenu")
    RegisterForMenuOpenCloseEvent("BookMenu")
    RegisterForMenuOpenCloseEvent("DataMenu")
    RegisterForMenuOpenCloseEvent("InventoryMenu")
    RegisterForMenuOpenCloseEvent("PauseMenu")
    RegisterForMenuOpenCloseEvent("Console")
    RegisterForMenuOpenCloseEvent("FO4SF_PipboyMenu")
EndFunction

Event OnMenuOpenCloseEvent(string asMenuName, bool abOpening)
    if abOpening
        sturgesNearSec = 0.0
        if asMenuName == "WorkshopMenu" || asMenuName == "WorkshopBuilderMenu" || asMenuName == "WorkshopQuickMenu" || asMenuName == "Workshop_BlueprintMenu"
            workshopMenuOpen = True
            cleanBenchSawWorkshop = True
            cleanBenchVerifyPending = False
            CancelTimer(3)
        endif
    else
        if asMenuName == "WorkshopMenu" || asMenuName == "WorkshopBuilderMenu" || asMenuName == "WorkshopQuickMenu" || asMenuName == "Workshop_BlueprintMenu"
            workshopMenuOpen = False
        endif
    endif
EndEvent

bool Function IsAnyMenuOrWorkshopOpen()
{A2.1 / R11-fix #8: Multi-layer menu guard using native pause/dialogue/control checks and explicit boolean workshop/dialog flags (no sticky counter).}
    if talkBoxOpen || benchMenuOpen || workshopModeActive || workshopMenuOpen
        return True
    endif
    if Utility.IsGameMenuPaused() || Game.IsPlayerInDialogue()
        return True
    endif
    if !Game.IsMovementControlsEnabled() || !Game.IsActivateControlsEnabled()
        return True
    endif
    return False
EndFunction

bool Function IsCleanBenchSwapEnabled()
{R11-fix #2: Clean bench swap is OFF by default in candidate-2g-fix (EnableCleanBenchSwap == False and FO4SFWorkshop.esm:0x00084A == 0.0).
 Returns True only when explicitly switched ON and not self-healed.}
    if cleanBenchSelfHealed
        return False
    endif
    if EnableCleanBenchSwap
        return True
    endif
    if Game.IsPluginInstalled(WorkshopPlugin)
        GlobalVariable sw = Game.GetFormFromFile(CleanBenchSwapGlobId, WorkshopPlugin) as GlobalVariable
        if sw != None && sw.GetValue() != 0.0
            return True
        endif
    endif
    return False
EndFunction

bool Function IsSturgesReadyForSanctuary()
{A2.1 / S9: Sturges arrives with Preston's group in S9 and is NO LONGER placed at the bench by stage 100 in normal play.
 Returns True only after S9 arrival (OnSturgesArrivedFromConcord or Sturges already enabled by S9) or explicit TestMode.}
    if sturgesArrivedS9 || IsTestModeEnabled()
        return True
    endif
    Actor st = ResolveSturges()
    if st != None && !st.IsDisabled() && !st.IsDead()
        return True
    endif
    return False
EndFunction

Function OnSturgesArrivedFromConcord()
{S9 handoff entry point: called when Preston's group reaches Sanctuary from Concord so Sturges is ready for First Settlement.}
    sturgesArrivedS9 = True
    Actor st = ResolveSturges()
    if st != None && !st.IsDead()
        if st.IsDisabled()
            st.EnableNoWait(False)
            Trace("sanctuary01 sturges enabled by=s9_arrival")
        endif
        BindSturges()
    endif
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
    ; Task 1i (#858 F7): resolve host world dynamically from persistent V111 exit marker (0x0A775B, flags=0x400) FIRST,
    ; using Sanctuary workbench (0x005C50, flags=0x0) strictly as secondary fallback.
    ObjectReference coreV111 = Game.GetFormFromFile(0x0A775B, CorePlugin) as ObjectReference
    if coreV111 != None
        commonwealthWorld = coreV111.GetWorldSpace()
        if commonwealthWorld != None
            return commonwealthWorld
        endif
    endif
    ObjectReference coreBench = Game.GetFormFromFile(BenchRefId, CorePlugin) as ObjectReference
    if coreBench != None
        commonwealthWorld = coreBench.GetWorldSpace()
        if commonwealthWorld != None
            return commonwealthWorld
        endif
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
        ObjectReference activeBench = Game.GetFormFromFile(BenchRefId, cName) as ObjectReference
        if activeBench != None
            commonwealthWorld = activeBench.GetWorldSpace()
            if commonwealthWorld != None
                return commonwealthWorld
            endif
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
    if n == 20
        Trace("sanctuary01 stage 20 concord_arrival_handoff by=" + by)
    elseif n == 50
        if IsSturgesDeadOrMissing()
            Trace("sanctuary01 open_mode sturges_unavailable -> stage 1000")
            AdvanceTo(1000, "open_mode")
        else
            SetObjectiveDisplayed(50, True, True)
        endif
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
    elseif n == 220
        SetObjectiveCompleted(10)
        SetObjectiveDisplayed(220, True, True)
        SetActive(True)
        BindSturges()
        Trace("sanctuary01 objective 220 talk_to_sturges")
    elseif n == 1000
        SetObjectiveCompleted(10)
        CleanupMarker()
        SetObjectiveCompleted(50)
        SetObjectiveCompleted(220)
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
    if minRecruitHandoffDone || IsWarfareMode() || HasS9HardStop()
        return
    endif
    Quest firstStep = Game.GetFormFromFile(0x000A20, MissionPlugin) as Quest
    if firstStep != None
        if firstStep.IsCompleted()
            minRecruitHandoffDone = True
        elseif firstStep.IsRunning()
            FO4SF_MinRecruit00Quest nextMr = firstStep as FO4SF_MinRecruit00Quest
            if nextMr != None
                nextMr.WakeFromPredecessor()
            endif
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

Function StartPostOpeningHandoffs()
{R1/R5: Deliberate one-tracked-opening-mission design choice: in Fallout 4, MQ103 starts when MQ102 ends while Min01 is still running; here MQ103 waits until Sanctuary01 completes, and after that it can also start at the Diamond City gate.
 S9 hard stop holds MinRecruit00 and MQ103 off at Min01 1000.}
    if HasS9HardStop()
        Trace("sanctuary01 s9_hard_stop minrecruit00=0 mq103=0")
        return
    endif
    StartMinRecruit00IfNeeded()
    if IsWarfareMode()
        return
    endif
    Quest mq103Quest = Game.GetFormFromFile(0x000A50, MissionPlugin) as Quest
    if mq103Quest != None && !mq103Quest.IsCompleted()
        if mq103Quest.IsRunning()
            FO4SF_MQ103Quest nextMq103 = mq103Quest as FO4SF_MQ103Quest
            if nextMq103 != None
                nextMq103.WakeFromPredecessor()
            endif
        else
            bool startedMq103 = mq103Quest.StartNoWait()
            Trace("sanctuary01 post_complete handoff mq103 start_requested ok=" + startedMq103)
        endif
    endif
EndFunction

Function FinishQuest(string by)
    if completed
        StartPostOpeningHandoffs()
        return
    endif
    completed = True
    Actor st = ResolveSturges()
    if st != None
        st.SetRestrained(False)
    endif
    sturgesHeld = False
    if sturgesTalkProxy != None && !sturgesTalkProxy.IsDeleted()
        sturgesTalkProxy.DisableNoWait(False)
        sturgesTalkProxy.Delete()
    endif
    sturgesTalkProxy = None
    CompleteQuest()
    CancelTimer(1)
    CleanupMarker()
    Trace("sanctuary01 finished stage=" + EffectiveStage() + " by=" + by)
    StartPostOpeningHandoffs()
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
    RegisterMenuGuards()
    AdvanceTo(10, "Trigger")
    EnsureGuideMarker(player)
    TryBindBench(player)
    SetObjectiveDisplayed(10, True, True)
    SetActive(True)
    ; R1: Do NOT start FO4SF_MQ103 during the opening; First Settlement stays the sole active HUD objective.
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
    workshopModeActive = False
    workshopMenuOpen = False
    cleanBenchVerifyPending = False
    cleanBenchSawWorkshop = False
    CancelTimer(3)
    sturgesHeld = False
    sturgesNearSec = 0.0
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
        if st >= 100
            BindSturges()
            KeepSturges(player)
        endif
        EnsureGuideMarker(player)
        TryBindBench(player)
        CheckMilestoneProgress(st)
        StartTimer(1.0, 1)
    endif
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID == 3
        if cleanBenchVerifyPending && !cleanBenchSawWorkshop && !workshopModeActive && !workshopMenuOpen && sanctuaryBenchOverride != None && !cleanBenchSelfHealed
            cleanBenchSelfHealed = True
            cleanBenchVerifyPending = False
            Trace("sanctuary01 clean_bench_swap self_heal reason=no_workshop_menu")
            RestoreCoreBench("self_heal")
        else
            cleanBenchVerifyPending = False
        endif
        return
    endif
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
        if st >= 100
            KeepSturges(player)
            CheckSturgesTalkFallback(player, st)
        endif
        if st >= 1000 && st < 1500
            CheckMilestoneProgress(st)
        endif
        bool wantSwapNow = IsCleanBenchSwapEnabled()
        if wantSwapNow && (sanctuaryBenchOverride == None || boundBench != sanctuaryBenchOverride)
            TryBindBench(player)
        elseif !wantSwapNow && sanctuaryBenchOverride != None && boundBench == sanctuaryBenchOverride
            RestoreCoreBench("switch_off")
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
    if EffectiveStage() < 100
        ; R3: Sturges remains InitiallyDisabled during opening/stage 10 until S9 arrival
        return
    endif
    Actor st = ResolveSturges()
    if st == None || st.IsDead() || !IsCommonwealthExterior(player)
        return
    endif
    ; A2.1 / S9: Sturges now arrives with Preston's group in S9 and is NO LONGER enabled or teleported
    ; onto the workbench by stage 100 in normal play. Only S9 arrival (or TestMode) activates him here.
    if !IsSturgesReadyForSanctuary()
        return
    endif
    if st.IsDisabled()
        if sturgesArrivedS9 || IsTestModeEnabled()
            st.EnableNoWait(False)
            BindSturges()
            Trace("sanctuary01 sturges enabled stage=" + EffectiveStage())
        else
            return
        endif
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
        if IsTestModeEnabled()
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
        else
            ; S9 normal play: keep Sturges talkable at his S9 arrival spot without teleporting him onto the workbench
            if !sturgesHeld
                BindSturges()
                sturgesHeld = True
            endif
        endif
        if sturgesTalkProxy == None || sturgesTalkProxy.IsDeleted()
            Activator talkActi = Game.GetFormFromFile(0x000A0E, MissionPlugin) as Activator
            if talkActi != None
                sturgesTalkProxy = st.PlaceAtMe(talkActi, 1, True, False, False)
                if sturgesTalkProxy != None
                    sturgesTalkProxy.MoveTo(st, 0.0, 0.0, 1.0, False, False)
                    RegisterForRemoteEvent(sturgesTalkProxy, "OnActivate")
                    Trace("sanctuary01 sturges talk_proxy spawned")
                endif
            endif
        endif
    endif
EndFunction

Function CheckSturgesTalkFallback(Actor player, int st)
{R4 / A2.1: Timed proximity fallback while Sturges is alive & arrived from S9.
 IMPOSSIBLE while ANY menu (WorkshopMenu, DialogueMenu, PauseMenu, Pip-Boy, etc.) is open:
 resets sturgesNearSec to 0.0 and suppresses popup whenever IsAnyMenuOrWorkshopOpen() is True.}
    if IsAnyMenuOrWorkshopOpen() || player == None
        sturgesNearSec = 0.0
        return
    endif
    if !IsSturgesReadyForSanctuary()
        sturgesNearSec = 0.0
        return
    endif
    bool talkStage = (st == 100 || st == 220 || st == 1050 || st == 1250 || st == 1350 || st == 1450)
    Actor stActor = ResolveSturges()
    if !talkStage || stActor == None || stActor.IsDead() || stActor.IsDisabled() || !stActor.Is3DLoaded()
        sturgesNearSec = 0.0
        return
    endif
    if player.GetDistance(stActor) <= TalkFallbackRadius
        sturgesNearSec += 1.0
        if sturgesNearSec >= TalkFallbackSeconds
            if IsAnyMenuOrWorkshopOpen()
                sturgesNearSec = 0.0
                return
            endif
            sturgesNearSec = 0.0
            Trace("sanctuary01 talk_fallback actor=sturges stage=" + st + " near_sec=" + TalkFallbackSeconds)
            RunSturgesTalk()
        endif
    else
        sturgesNearSec = 0.0
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
        if HasS9HardStop()
            Trace("sanctuary01 stage 1000 held=true hard_stop=true minrecruit00=0 mq103=0 beds_pct=" + bp)
            return
        endif
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
    if IsAnyMenuOrWorkshopOpen() || completed
        return
    endif
    talkBoxOpen = True
    int mySession = talkSessionId
    int st = EffectiveStage()
    Trace("sanctuary01 sturges talk opened stage=" + st)
    if st == 220
        bool introOk = True
        Message mIntro = Game.GetFormFromFile(0x000BF4, MissionPlugin) as Message
        if mIntro != None
            if mIntro.Show() < 0
                introOk = False
            endif
        endif
        if introOk && mySession == talkSessionId
            SetObjectiveCompleted(220)
            Trace("sanctuary01 min01_sturges_intro form=001188B4 -> stage 1000")
            AdvanceTo(1000, "sturges_intro")
        endif
    elseif st == 10 || st == 50 || st == 100
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
    elseif st == 1000 || st == 1200 || st == 1300 || st == 1400
        ; R2/R8: Stand-in build counter only via Sturges (never over the real workshop on bench OnActivate)
        if mySession == talkSessionId
            talkBoxOpen = False
        endif
        RunWorkbenchBuildMenu()
        return
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

Function RestoreCoreBench(string reason)
{R11-fix #2: Re-enable 04005C50, disable sanctuaryBenchOverride, and re-bind boundBench + Alias 0 back to 04005C50.}
    cleanBenchVerifyPending = False
    CancelTimer(3)
    ObjectReference coreRef = coreBenchDisabled
    if coreRef == None
        string cName = ActiveCorePlugin()
        if cName != ""
            coreRef = Game.GetFormFromFile(BenchRefId, cName) as ObjectReference
        endif
    endif
    if sanctuaryBenchOverride != None && !sanctuaryBenchOverride.IsDeleted()
        UnregisterForRemoteEvent(sanctuaryBenchOverride, "OnActivate")
        UnregisterForRemoteEvent(sanctuaryBenchOverride, "OnWorkshopMode")
        sanctuaryBenchOverride.DisableNoWait(False)
    endif
    if boundBench != None && boundBench != coreRef
        UnregisterForRemoteEvent(boundBench, "OnActivate")
        UnregisterForRemoteEvent(boundBench, "OnWorkshopMode")
    endif
    if coreRef != None
        if coreRef.IsDisabled()
            coreRef.EnableNoWait(False)
        endif
        boundBench = coreRef
        RegisterForRemoteEvent(boundBench, "OnActivate")
        RegisterForRemoteEvent(boundBench, "OnWorkshopMode")
        ReferenceAlias bAliasRestore = GetAlias(0) as ReferenceAlias
        if bAliasRestore != None
            bAliasRestore.ForceRefTo(boundBench)
        endif
        CleanupMarker()
        Trace("sanctuary01 bench_bound ref=" + boundBench + " loaded=" + boundBench.Is3DLoaded())
        Trace("sanctuary01 clean_bench_swap active=false ref=" + boundBench)
    else
        boundBench = None
    endif
EndFunction

Function TryBindBench(Actor player)
    if player == None
        return
    endif
    RegisterMenuGuards()
    bool wantSwap = IsCleanBenchSwapEnabled()
    if !wantSwap && sanctuaryBenchOverride != None && !sanctuaryBenchOverride.IsDeleted()
        RestoreCoreBench("load_switch_off")
        return
    endif
    if wantSwap && sanctuaryBenchOverride != None && !sanctuaryBenchOverride.IsDeleted()
        if sanctuaryBenchOverride.IsDisabled()
            sanctuaryBenchOverride.EnableNoWait(False)
        endif
        if coreBenchDisabled != None && !coreBenchDisabled.IsDisabled()
            coreBenchDisabled.DisableNoWait(False)
        endif
        if boundBench != sanctuaryBenchOverride
            if boundBench != None
                UnregisterForRemoteEvent(boundBench, "OnActivate")
                UnregisterForRemoteEvent(boundBench, "OnWorkshopMode")
            endif
            boundBench = sanctuaryBenchOverride
            RegisterForRemoteEvent(boundBench, "OnActivate")
            RegisterForRemoteEvent(boundBench, "OnWorkshopMode")
            ReferenceAlias bAliasRe = GetAlias(0) as ReferenceAlias
            if bAliasRe != None
                bAliasRe.ForceRefTo(boundBench)
            endif
            CleanupMarker()
            Trace("sanctuary01 bench_bound ref=" + boundBench + " loaded=" + boundBench.Is3DLoaded())
            Trace("sanctuary01 clean_bench_swap active=true ref=" + boundBench)
        endif
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
    if cand == None
        return
    endif
    ; R11 D4 / fix #2: Only swap core bench (0x005C50) for clean bench (FO4SFWorkshop.esm:0x000849)
    ; when explicitly switched ON (FO4SF_SanctuaryCleanBenchSwap 0x00084A == 1 or EnableCleanBenchSwap == True).
    ; Default in candidate-2g-fix is OFF so 04005C50 stays enabled and bound.
    bool swappedClean = False
    ObjectReference targetBench = cand
    if wantSwap && Game.IsPluginInstalled(WorkshopPlugin)
        if !cand.Is3DLoaded()
            return
        endif
        Activator cleanBase = Game.GetFormFromFile(CleanBenchBaseId, WorkshopPlugin) as Activator
        if cleanBase != None
            ObjectReference cleanRef = cand.PlaceAtMe(cleanBase, 1, True, False, False)
            if cleanRef != None
                cleanRef.MoveTo(cand, 0.0, 0.0, 0.0, True, False)
                cand.DisableNoWait(False)
                coreBenchDisabled = cand
                sanctuaryBenchOverride = cleanRef
                targetBench = cleanRef
                swappedClean = True
            endif
        endif
    elseif cand.IsDisabled()
        cand.EnableNoWait(False)
    endif
    if targetBench != None && targetBench != boundBench
        if boundBench != None
            UnregisterForRemoteEvent(boundBench, "OnActivate")
            UnregisterForRemoteEvent(boundBench, "OnWorkshopMode")
        endif
        boundBench = targetBench
        RegisterForRemoteEvent(boundBench, "OnActivate")
        RegisterForRemoteEvent(boundBench, "OnWorkshopMode")
        ReferenceAlias benchAlias = GetAlias(0) as ReferenceAlias
        if benchAlias != None
            benchAlias.ForceRefTo(boundBench)
        endif
        CleanupMarker()
        Trace("sanctuary01 bench_bound ref=" + boundBench + " loaded=" + boundBench.Is3DLoaded())
        if swappedClean
            Trace("sanctuary01 clean_bench_swap active=true ref=" + boundBench)
        else
            Trace("sanctuary01 clean_bench_swap active=false ref=" + boundBench)
        endif
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
    Trace("sanctuary01 stand_in_build_menu opened stage=" + EffectiveStage())
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
    if akActionRef != Game.GetPlayer()
        return
    endif
    if sanctuaryBenchOverride != None && akSender == sanctuaryBenchOverride
        if !IsCleanBenchSwapEnabled()
            RestoreCoreBench("switch_off")
            return
        elseif !cleanBenchSelfHealed
            cleanBenchSawWorkshop = False
            cleanBenchVerifyPending = True
            CancelTimer(3)
            StartTimer(CleanBenchSelfHealSeconds, 3)
        endif
    endif
    if completed
        return
    endif
    Actor st = ResolveSturges()
    if (st != None && akSender == st) || (sturgesTalkProxy != None && akSender == sturgesTalkProxy)
        RunSturgesTalk()
        return
    endif
    if boundBench != None && akSender == boundBench
        int cur = EffectiveStage()
        if cur < 100
            ; R2: Never pop a modal menu over the real workshop on bench activation.
            CompleteSanctuaryObjective(akSender)
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
        ; R2: Only open stand-in counter on bench activation when explicitly opted in via TestMode + Sturges dead
        GlobalVariable tm = Game.GetFormFromFile(0x000860, "FO4SFCoreValues.esm") as GlobalVariable
        if HasFullMin01() && !completed && IsSturgesDeadOrMissing() && tm != None && tm.GetValue() != 0.0
            RunWorkbenchBuildMenu()
        endif
    endif
EndEvent

Event ObjectReference.OnWorkshopMode(ObjectReference akSender, bool aStart)
    if boundBench != None && akSender == boundBench
        workshopModeActive = aStart
        if aStart
            sturgesNearSec = 0.0
            cleanBenchSawWorkshop = True
            cleanBenchVerifyPending = False
            CancelTimer(3)
            if !completed && EffectiveStage() < 100
                CompleteSanctuaryObjective(akSender)
            endif
        else
            workshopMenuOpen = False
        endif
    endif
EndEvent

Function CompleteSanctuaryObjective(ObjectReference refUsed)
    if completed || EffectiveStage() >= 100
        return
    endif
    benchActivated = True
    Trace("min01 bench activated -> stage 100")
    AdvanceTo(100, "bench")
    ; R2: Only log complete=true when CompleteQuest() truly completed the quest (legacy stub); otherwise log complete=false honestly.
    if completed
        Trace("sanctuary01 bench_activated=true ref=" + refUsed + " complete=true")
    else
        Trace("sanctuary01 bench_activated=true ref=" + refUsed + " complete=false stage=" + EffectiveStage())
    endif
EndFunction

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
