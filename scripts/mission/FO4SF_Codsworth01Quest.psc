Scriptname FO4SF_Codsworth01Quest extends Quest
{MQ102-lite Sanctuary conversation quest (FO4SFMission.esm 0x000816, started via StartNoWait at FO4SFNewGame stage 200).
 Story mode only (FO4SF_GameMode 0x000870 != 2). Drives objective 10 on Codsworth and runs the 4-choice Sanctuary talk:
   stage 20 = choice 1 (date / what happened)
   stage 30 = choice 2 (Sanctuary / family)
   stage 40 = choice 3 (nearby survivors)
   stage 100 = choice 4 (head to Concord -> completes FO4SF_Codsworth01 and gives FO4SF_Min00 stage 10).}

Actor Property Codsworth Auto Const
Scene Property CodsworthScene Auto Const
Scene Property CodsworthPostScene Auto Const
Activator Property CodsworthTalkActi Auto Const
Message Property CodsworthTalkMsg Auto Const
Message Property CodsworthReply0Msg Auto Const
Message Property CodsworthReply1Msg Auto Const
Message Property CodsworthReply2Msg Auto Const
GlobalVariable Property TalkUseMessageBox Auto Const

string LogName = "fo4sf_mission"
float CodsworthLocalX = -1146.709
float CodsworthLocalY = 1293.837
float CodsworthLocalZ = 111.734
float MergeOffsetX = -1200.0
float MergeOffsetY = -2700.0
float ProxyHoldRadius = 25.0
float ProxyBindRadius = 180.0
float ProxyZOffset = 1.36
float ProxyScale = 1.6
float ProxyResyncDrift = 0.25
float MinTalkCameraDistance = 1.65
float SafeTalkCameraDistance = 1.85
float SceneOpenCheckSeconds = 1.5
int SceneMaxWaitChecks = 16
int MaxSceneRestarts = 3

bool instanceStarted = False
bool dialogueSeen = False
bool dialogueMenuOpen = False
bool talkBoxOpen = False
bool sceneTalkPending = False
bool sceneMenuOpened = False
bool scenePhase1Entered = False
float scenePhase1At = 0.0
int sceneCheckTicks = 0
int sceneRestartCount = 0
bool scenePostActive = False
bool ownSceneStopPending = False
float sceneAttemptStartedAt = 0.0
int talkSessionId = 0
bool codsworthTalkReloaded = False
bool concordCleared = False
ObjectReference talkProxy = None
bool proxyLogged = False
float proxyLastX = 0.0
float proxyLastY = 0.0
float proxyLastZ = 0.0
int applied = 0
int pendingStage = -1
string pendingStageBy = "other"
bool choice1Seen = False
bool choice2Seen = False
bool choice3Seen = False
bool choice4Seen = False
int choicesCount = 0
bool completed = False

int Function EffectiveStage()
    int st = GetStage()
    if applied > st
        return applied
    endif
    return st
EndFunction

Function ShowCodsworthObjective()
    if completed || concordCleared
        return
    endif
    if !IsRunning()
        Start()
    endif
    EnsureCodsworthAlias(ResolveCodsworth())
    SetObjectiveDisplayed(10, True, True)
    SetActive(True)
    SetObjectiveDisplayedAtTop(10)
EndFunction

Actor Function ResolveCodsworth()
    if Codsworth != None
        return Codsworth
    endif
    return Game.GetFormFromFile(0x000811, "FO4SFMission.esm") as Actor
EndFunction

Activator Function ResolveTalkActi()
    if CodsworthTalkActi != None
        return CodsworthTalkActi
    endif
    return Game.GetFormFromFile(0x000970, "FO4SFMission.esm") as Activator
EndFunction

Message Function ResolveTalkMsg(int slot)
    if slot == 0
        if CodsworthReply0Msg != None
            return CodsworthReply0Msg
        endif
        return Game.GetFormFromFile(0x000972, "FO4SFMission.esm") as Message
    elseif slot == 1
        if CodsworthReply1Msg != None
            return CodsworthReply1Msg
        endif
        return Game.GetFormFromFile(0x000973, "FO4SFMission.esm") as Message
    elseif slot == 2
        if CodsworthReply2Msg != None
            return CodsworthReply2Msg
        endif
        return Game.GetFormFromFile(0x000974, "FO4SFMission.esm") as Message
    endif
    if CodsworthTalkMsg != None
        return CodsworthTalkMsg
    endif
    return Game.GetFormFromFile(0x000971, "FO4SFMission.esm") as Message
EndFunction

Scene Function ResolveCodsworthScene()
    if CodsworthScene != None
        return CodsworthScene
    endif
    return Game.GetFormFromFile(0x000940, "FO4SFMission.esm") as Scene
EndFunction

Scene Function ResolveCodsworthPostScene()
    if CodsworthPostScene != None
        return CodsworthPostScene
    endif
    return Game.GetFormFromFile(0x0009C0, "FO4SFMission.esm") as Scene
EndFunction

Scene Function ResolveActiveCodsworthScene(bool postMode)
    if postMode
        return ResolveCodsworthPostScene()
    endif
    return ResolveCodsworthScene()
EndFunction

bool Function ShouldUseMessageBox()
    GlobalVariable g = TalkUseMessageBox
    if g == None
        g = Game.GetFormFromFile(0x000979, "FO4SFMission.esm") as GlobalVariable
    endif
    if g != None && g.GetValue() != 0.0
        return True
    endif
    return False
EndFunction

Function EnsureCodsworthAlias(Actor cods)
    if cods == None
        return
    endif
    ReferenceAlias al = GetAlias(0) as ReferenceAlias
    if al != None && al.GetActorRef() != cods
        al.ForceRefTo(cods)
    endif
EndFunction

Function EnsureKeeperCodsworthAlias(Actor cods)
    if cods == None
        return
    endif
    Quest kq = Game.GetFormFromFile(0x000814, "FO4SFMission.esm") as Quest
    if kq != None
        if !kq.IsRunning()
            kq.StartNoWait()
        endif
        ReferenceAlias al = kq.GetAlias(1) as ReferenceAlias
        if al != None && al.GetActorRef() != cods
            al.ForceRefTo(cods)
        endif
    endif
EndFunction

Function RegisterCodsworthSceneEvents()
    Scene scn = ResolveCodsworthScene()
    if scn != None
        RegisterForRemoteEvent(scn, "OnBegin")
        RegisterForRemoteEvent(scn, "OnPhaseBegin")
        RegisterForRemoteEvent(scn, "OnEnd")
    endif
    Scene postScn = ResolveCodsworthPostScene()
    if postScn != None
        RegisterForRemoteEvent(postScn, "OnBegin")
        RegisterForRemoteEvent(postScn, "OnPhaseBegin")
        RegisterForRemoteEvent(postScn, "OnEnd")
    endif
EndFunction

Function BindCodsworthActivation()
    talkSessionId += 1
    Actor cods = ResolveCodsworth()
    if cods != None
        cods.AllowPCDialogue(True)
        cods.BlockActivation(False, False)
        EnsureCodsworthAlias(cods)
        if completed
            EnsureKeeperCodsworthAlias(cods)
            RegisterForMenuOpenCloseEvent("DialogueMenu")
            RegisterCodsworthSceneEvents()
        endif
        RegisterForRemoteEvent(cods, "OnActivate")
    endif
    if talkProxy != None && !talkProxy.IsDeleted()
        talkProxy.BlockActivation(False, False)
        RegisterForRemoteEvent(talkProxy, "OnActivate")
    endif
    EnsureTalkProxy(Game.GetPlayer())
    Trace("codsworth01 talk ready codsworth=" + cods + " proxy=" + talkProxy)
EndFunction

Function EnsureTalkProxy(Actor player)
    if player == None || player.IsInInterior()
        return
    endif
    Actor cods = ResolveCodsworth()
    if cods == None || cods.IsDisabled() || cods.IsDead()
        if talkProxy != None && !talkProxy.IsDeleted()
            talkProxy.DisableNoWait(False)
        endif
        return
    endif
    cods.AllowPCDialogue(True)
    cods.BlockActivation(False, False)
    float tx = CodsworthLocalX + MergeOffsetX
    float ty = CodsworthLocalY + MergeOffsetY
    float tz = CodsworthLocalZ
    float cx = cods.GetPositionX()
    float cy = cods.GetPositionY()
    float cz = cods.GetPositionZ()
    if talkProxy != None && !talkProxy.IsDeleted()
        if talkProxy.IsDisabled()
            talkProxy.EnableNoWait(False)
        endif
        float mx = cx - proxyLastX
        float my = cy - proxyLastY
        float mz = cz - proxyLastZ
        if mx * mx + my * my + mz * mz > ProxyResyncDrift * ProxyResyncDrift
            talkProxy.SetPosition(cx, cy, cz + ProxyZOffset)
            proxyLastX = cx
            proxyLastY = cy
            proxyLastZ = cz
        endif
        return
    endif
    float ex = cx - tx
    float ey = cy - ty
    float ez = cz - tz
    if ex * ex + ey * ey + ez * ez > ProxyHoldRadius * ProxyHoldRadius
        return
    endif
    float dx = player.GetPositionX() - cx
    float dy = player.GetPositionY() - cy
    if dx * dx + dy * dy > ProxyBindRadius * ProxyBindRadius || !cods.Is3DLoaded()
        return
    endif
    Activator acti = ResolveTalkActi()
    if acti != None
        talkProxy = cods.PlaceAtMe(acti, 1, True, True, False)
        if talkProxy != None
            talkProxy.EnableNoWait(False)
            talkProxy.SetScale(ProxyScale)
            talkProxy.SetPosition(cx, cy, cz + ProxyZOffset)
            talkProxy.BlockActivation(False, False)
            RegisterForRemoteEvent(talkProxy, "OnActivate")
            proxyLastX = cx
            proxyLastY = cy
            proxyLastZ = cz
            if !proxyLogged
                proxyLogged = True
                if !completed && !concordCleared
                    EnsureCodsworthAlias(cods)
                    SetObjectiveDisplayed(10, True, True)
                    SetActive(True)
                endif
                Trace("codsworth talk proxy ready ref=" + talkProxy + " z=" + (cz + ProxyZOffset))
            endif
        endif
    endif
EndFunction

Function ClearObjectiveOnConcordStart()
    concordCleared = True
    if !completed && instanceStarted
        SetObjectiveDisplayed(10, False, False)
        SetActive(False)
        Trace("codsworth01 objective 10 cleared by=concord")
    endif
EndFunction

Function AdvanceTo(int n, string by = "Trigger")
    pendingStage = n
    pendingStageBy = by
    SetStage(n)
    if n > applied
        applied = n
        Trace("codsworth01 stage " + n + " by=" + by)
    endif
    if n >= 20
        SyncProgress()
    endif
    if pendingStage == n
        pendingStage = -1
    endif
EndFunction

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
        Trace("mission gate mode=2 started=false quest=codsworth01")
        Stop()
        return
    endif
    Actor player = Game.GetPlayer()
    if player != None
        RegisterForRemoteEvent(player, "OnPlayerLoadGame")
    endif
    RegisterForMenuOpenCloseEvent("DialogueMenu")
    RegisterCodsworthSceneEvents()
    BindCodsworthActivation()
    AdvanceTo(10, "Trigger")
    ShowCodsworthObjective()
    Trace("codsworth01 init stage=10")
    StartTimer(1.0, 1)
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    dialogueMenuOpen = False
    talkBoxOpen = False
    codsworthTalkReloaded = True
    sceneTalkPending = False
    sceneMenuOpened = False
    scenePhase1Entered = False
    scenePhase1At = 0.0
    sceneCheckTicks = 0
    sceneRestartCount = 0
    scenePostActive = False
    ownSceneStopPending = False
    sceneAttemptStartedAt = 0.0
    CancelTimer(2)
    int st = GetStage()
    if applied > st
        st = applied
    endif
    Trace("codsworth01 reload stage=" + st + " choices=" + choicesCount)
    BindCodsworthActivation()
    if !completed
        if applied > 0 && GetStage() < applied
            SetStage(applied)
        endif
        RegisterForMenuOpenCloseEvent("DialogueMenu")
        RegisterCodsworthSceneEvents()
        StartTimer(1.0, 1)
    elseif talkProxy == None || talkProxy.IsDeleted()
        StartTimer(1.0, 1)
    endif
EndEvent

Event OnMenuOpenCloseEvent(string asMenuName, bool abOpening)
    if asMenuName == "DialogueMenu"
        dialogueMenuOpen = abOpening
        if abOpening
            dialogueSeen = True
            Scene scn = ResolveCodsworthScene()
            Scene postScn = ResolveCodsworthPostScene()
            bool anyPlaying = (scn != None && scn.IsPlaying()) || (postScn != None && postScn.IsPlaying())
            if sceneTalkPending || anyPlaying
                sceneMenuOpened = True
                sceneTalkPending = False
                scenePhase1Entered = False
                scenePhase1At = 0.0
                sceneRestartCount = 0
                ownSceneStopPending = False
                sceneAttemptStartedAt = 0.0
                CancelTimer(2)
                Trace("codsworth dialogue menu opened")
            endif
        elseif sceneMenuOpened
            sceneMenuOpened = False
            Trace("codsworth dialogue menu closed stage=" + EffectiveStage())
            SyncProgress()
        endif
    endif
EndEvent

Function EnsureSafeCodsworthCameraDistance(Actor player, Actor cods)
{C6 + R11 A2.5: When the player activates Codsworth inside his 0.65 m chassis radius (e.g. moveto at d=0.62 m),
 step back to SafeTalkCameraDistance (1.85 m) only after validating ground-Z alignment (|pz - cz| <= 1.5 m) and
 Sanctuary Player House wall clearance (derived from Fallout4.esm WRLD 0x3C: exterior facade lies ~1.15 m NW of
 Codsworth along normal (-0.6428, +0.7660)). If the direct ray back points into the NW house wall, redirect onto
 the nearest unobstructed Sanctuary yard/driveway azimuth at exact 1.85 m. Normal walk-ups (>= 1.65 m) untouched.}
    if player == None || cods == None || player.IsInInterior()
        return
    endif
    float cx = cods.GetPositionX()
    float cy = cods.GetPositionY()
    float cz = cods.GetPositionZ()
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float pz = player.GetPositionZ()
    float dx = px - cx
    float dy = py - cy
    float horiz = Math.Sqrt(dx * dx + dy * dy)
    if horiz >= MinTalkCameraDistance
        return
    endif
    ; A2.5: Ground-Z validation — never shove a player off a roof/ledge or through terrain far from Codsworth's ground plane.
    float dz = pz - cz
    if dz < -1.5 || dz > 1.5
        Trace("codsworth talk camera_guard skipped reason=ground_z_mismatch prev_d=" + horiz + " dz=" + dz)
        return
    endif
    float ux = 0.0
    float uy = 1.0
    if horiz > 0.05
        ux = dx / horiz
        uy = dy / horiz
    else
        float yaw = cods.GetAngleZ()
        ux = Math.Sin(yaw)
        uy = Math.Cos(yaw)
    endif
    float candDx = ux * SafeTalkCameraDistance
    float candDy = uy * SafeTalkCameraDistance
    bool wallAvoid = False
    ; A2.5: Sanctuary Player House wall clearance check around Codsworth's merged Sanctuary spot (-2346.709, -1406.163).
    float sx = cx - (-2346.709)
    float sy = cy - (-1406.163)
    if sx * sx + sy * sy <= 25.0
        float wallProj = candDx * (-0.6428) + candDy * 0.7660
        if wallProj > 1.0
            ; Candidate lies inside the NW Player House wall footprint -> pick closest unobstructed yard/street direction.
            float bestX = 0.6428
            float bestY = -0.7660
            float bestDot = ux * bestX + uy * bestY
            float swDot = ux * (-0.7660) + uy * (-0.6428)
            if swDot > bestDot
                bestDot = swDot
                bestX = -0.7660
                bestY = -0.6428
            endif
            float neDot = ux * 0.7660 + uy * 0.6428
            if neDot > bestDot
                bestDot = neDot
                bestX = 0.7660
                bestY = 0.6428
            endif
            candDx = bestX * SafeTalkCameraDistance
            candDy = bestY * SafeTalkCameraDistance
            wallAvoid = True
        endif
    endif
    float targetZ = pz
    if targetZ < cz - 0.35
        targetZ = cz
    elseif targetZ > cz + 0.60
        targetZ = cz + 0.35
    endif
    float newPx = cx + candDx
    float newPy = cy + candDy
    float toX = cx - newPx
    float toY = cy - newPy
    float facingDeg = 0.0
    if toY > 0.0001
        facingDeg = Math.atan(toX / toY)
    elseif toY < -0.0001
        facingDeg = Math.atan(toX / toY) + 180.0
    elseif toX >= 0.0
        facingDeg = 90.0
    else
        facingDeg = 270.0
    endif
    if facingDeg < 0.0
        facingDeg += 360.0
    elseif facingDeg >= 360.0
        facingDeg -= 360.0
    endif
    player.SetPosition(newPx, newPy, targetZ)
    player.SetAngle(0.0, 0.0, facingDeg)
    Trace("codsworth talk camera_guard prev_d=" + horiz + " safe_d=" + SafeTalkCameraDistance + " wall_avoid=" + wallAvoid + " facing_deg=" + facingDeg)
EndFunction

bool Function RestartOrFailCodsworthScene(string reason, bool postMode)
{R11 Part 3 + F1: When TalkUseMessageBox == 0 (default), NEVER open a MessageBox. Mark ownSceneStopPending before own Stop(),
 count each retry only after a full SceneOpenCheckSeconds window, and log real retry counts.}
    Actor cods = ResolveCodsworth()
    Scene scn = ResolveActiveCodsworthScene(postMode)
    if scn == None
        int usedRetries = sceneRestartCount
        sceneTalkPending = False
        sceneMenuOpened = False
        scenePhase1Entered = False
        scenePhase1At = 0.0
        sceneCheckTicks = 0
        sceneRestartCount = 0
        scenePostActive = False
        ownSceneStopPending = False
        sceneAttemptStartedAt = 0.0
        CancelTimer(2)
        if cods != None
            cods.AllowPCDialogue(True)
            cods.BlockActivation(False, False)
        endif
        Trace("codsworth talk ERROR scene_failed retries=" + usedRetries + " reason=no_scene actor_talkable=true")
        return False
    endif
    if sceneRestartCount < MaxSceneRestarts
        sceneRestartCount += 1
        if postMode
            EnsureKeeperCodsworthAlias(cods)
        else
            EnsureCodsworthAlias(cods)
        endif
        if scn.IsPlaying()
            ownSceneStopPending = True
            scn.Stop()
        endif
        sceneAttemptStartedAt = Utility.GetCurrentRealTime()
        scn.Start()
        if !scn.IsPlaying()
            scn.ForceStart()
        endif
        sceneTalkPending = True
        scenePostActive = postMode
        scenePhase1Entered = False
        scenePhase1At = 0.0
        sceneCheckTicks = 0
        Trace("codsworth talk scene_restart retry=" + sceneRestartCount + "/" + MaxSceneRestarts + " reason=" + reason + " stage=" + EffectiveStage())
        CancelTimer(2)
        StartTimer(SceneOpenCheckSeconds, 2)
        return True
    endif
    int maxUsed = sceneRestartCount
    sceneTalkPending = False
    sceneMenuOpened = False
    scenePhase1Entered = False
    scenePhase1At = 0.0
    sceneCheckTicks = 0
    sceneRestartCount = 0
    scenePostActive = False
    sceneAttemptStartedAt = 0.0
    CancelTimer(2)
    if scn.IsPlaying()
        ownSceneStopPending = True
        scn.Stop()
    else
        ownSceneStopPending = False
    endif
    if cods != None
        cods.AllowPCDialogue(True)
        cods.BlockActivation(False, False)
    endif
    Trace("codsworth talk ERROR scene_failed retries=" + maxUsed + " reason=" + reason + " actor_talkable=true")
    return False
EndFunction

Event Scene.OnBegin(Scene akSender)
    Scene scn = ResolveCodsworthScene()
    Scene postScn = ResolveCodsworthPostScene()
    bool isPrimary = scn != None && akSender == scn
    bool isPost = postScn != None && akSender == postScn
    if isPrimary || isPost
        dialogueSeen = True
        EnsureSafeCodsworthCameraDistance(Game.GetPlayer(), ResolveCodsworth())
        if !ShouldUseMessageBox() && !sceneTalkPending && !sceneMenuOpened && !dialogueMenuOpen && !talkBoxOpen && (isPost || !completed)
            ownSceneStopPending = False
            sceneTalkPending = True
            scenePostActive = isPost
            scenePhase1Entered = False
            scenePhase1At = 0.0
            sceneAttemptStartedAt = Utility.GetCurrentRealTime()
            sceneCheckTicks = 0
            sceneRestartCount = 0
            Trace("codsworth scene talk requested scene=" + akSender + " via=devt stage=" + EffectiveStage())
            StartTimer(SceneOpenCheckSeconds, 2)
        endif
        Trace("codsworth talk scene started stage=" + EffectiveStage())
    endif
EndEvent

Event Scene.OnPhaseBegin(Scene akSender, int auiPhaseIndex)
    Scene scn = ResolveCodsworthScene()
    Scene postScn = ResolveCodsworthPostScene()
    if (scn != None && akSender == scn) || (postScn != None && akSender == postScn)
        Trace("codsworth talk scene phase=" + auiPhaseIndex + " stage=" + EffectiveStage())
        if auiPhaseIndex == 1
            scenePhase1Entered = True
            scenePhase1At = Utility.GetCurrentRealTime()
            if sceneTalkPending && !sceneMenuOpened && !dialogueMenuOpen
                CancelTimer(2)
                StartTimer(SceneOpenCheckSeconds, 2)
            endif
        endif
    endif
EndEvent

Event Scene.OnEnd(Scene akSender)
    Scene scn = ResolveCodsworthScene()
    Scene postScn = ResolveCodsworthPostScene()
    bool isPrimary = scn != None && akSender == scn
    bool isPost = postScn != None && akSender == postScn
    if isPrimary || isPost
        if ownSceneStopPending
            ownSceneStopPending = False
            return
        endif
        SyncProgress()
        Trace("codsworth talk scene ended stage=" + EffectiveStage() + " completed=" + completed)
        if sceneTalkPending && !sceneMenuOpened && (isPost || !completed)
            if ShouldUseMessageBox()
                sceneTalkPending = False
                scenePhase1Entered = False
                scenePhase1At = 0.0
                sceneAttemptStartedAt = 0.0
                CancelTimer(2)
                Trace("codsworth talk fallback=messagebox reason=scene_incomplete")
                RunCodsworthTalk()
            else
                float nowEnd = Utility.GetCurrentRealTime()
                if sceneAttemptStartedAt > 0.0 && nowEnd < sceneAttemptStartedAt
                    sceneAttemptStartedAt = nowEnd
                endif
                float attElapsed = nowEnd - sceneAttemptStartedAt
                if sceneAttemptStartedAt > 0.0 && attElapsed < (SceneOpenCheckSeconds - 0.05)
                    CancelTimer(2)
                    StartTimer(SceneOpenCheckSeconds - attElapsed, 2)
                else
                    RestartOrFailCodsworthScene("scene_incomplete", isPost)
                endif
            endif
        else
            sceneTalkPending = False
            sceneMenuOpened = False
            scenePhase1Entered = False
            scenePhase1At = 0.0
            sceneRestartCount = 0
            scenePostActive = False
            sceneAttemptStartedAt = 0.0
        endif
    endif
EndEvent

Function CheckCodsworthSceneOpen()
    if !sceneTalkPending
        return
    endif
    if dialogueMenuOpen || sceneMenuOpened || talkBoxOpen || (!scenePostActive && completed)
        sceneTalkPending = False
        scenePhase1Entered = False
        scenePhase1At = 0.0
        sceneRestartCount = 0
        sceneAttemptStartedAt = 0.0
        return
    endif
    sceneCheckTicks += 1
    float nowRt = Utility.GetCurrentRealTime()
    if sceneAttemptStartedAt > 0.0 && nowRt < sceneAttemptStartedAt
        sceneAttemptStartedAt = nowRt
    endif
    float attemptElapsed = SceneOpenCheckSeconds
    if sceneAttemptStartedAt > 0.0
        attemptElapsed = nowRt - sceneAttemptStartedAt
    endif
    bool phase1Elapsed = False
    if scenePhase1Entered
        if nowRt < scenePhase1At
            scenePhase1At = nowRt
        elseif (nowRt - scenePhase1At) >= (SceneOpenCheckSeconds - 0.05)
            phase1Elapsed = True
        endif
    endif
    Scene scn = ResolveActiveCodsworthScene(scenePostActive)
    if scn == None || !scn.IsPlaying()
        if ShouldUseMessageBox()
            sceneTalkPending = False
            scenePhase1Entered = False
            scenePhase1At = 0.0
            sceneAttemptStartedAt = 0.0
            Trace("codsworth talk fallback=messagebox reason=scene_inactive")
            RunCodsworthTalk()
        elseif attemptElapsed < (SceneOpenCheckSeconds - 0.05)
            StartTimer(SceneOpenCheckSeconds - attemptElapsed, 2)
        else
            RestartOrFailCodsworthScene("scene_inactive", scenePostActive)
        endif
    elseif (phase1Elapsed || sceneCheckTicks >= SceneMaxWaitChecks) && attemptElapsed >= (SceneOpenCheckSeconds - 0.05)
        if ShouldUseMessageBox()
            sceneTalkPending = False
            scenePhase1Entered = False
            scenePhase1At = 0.0
            sceneAttemptStartedAt = 0.0
            if scn.IsPlaying()
                ownSceneStopPending = True
                scn.Stop()
            endif
            Trace("codsworth talk fallback=messagebox reason=dialogue_menu_timeout")
            RunCodsworthTalk()
        else
            RestartOrFailCodsworthScene("dialogue_menu_timeout", scenePostActive)
        endif
    elseif phase1Elapsed || sceneCheckTicks >= SceneMaxWaitChecks
        StartTimer(SceneOpenCheckSeconds - attemptElapsed, 2)
    else
        StartTimer(SceneOpenCheckSeconds, 2)
    endif
EndFunction

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    Actor player = Game.GetPlayer()
    if player == None || akActionRef != player
        return
    endif
    Actor cods = ResolveCodsworth()
    if akSender != cods && (talkProxy == None || akSender != talkProxy)
        return
    endif
    if IsWarfareMode() || talkBoxOpen || dialogueMenuOpen || sceneTalkPending
        return
    endif
    if ShouldUseMessageBox()
        Trace("codsworth talk fallback=messagebox reason=glob")
        RunCodsworthTalk()
        return
    endif
    bool postMode = completed
    Scene scn = ResolveActiveCodsworthScene(postMode)
    if scn == None
        if cods != None
            cods.AllowPCDialogue(True)
            cods.BlockActivation(False, False)
        endif
        Trace("codsworth talk ERROR scene_failed retries=" + sceneRestartCount + " reason=no_scene actor_talkable=true")
        return
    endif
    if postMode
        EnsureKeeperCodsworthAlias(cods)
    else
        EnsureCodsworthAlias(cods)
    endif
    EnsureSafeCodsworthCameraDistance(player, cods)
    dialogueSeen = True
    ownSceneStopPending = False
    sceneTalkPending = True
    scenePostActive = postMode
    sceneMenuOpened = False
    scenePhase1Entered = False
    scenePhase1At = 0.0
    sceneAttemptStartedAt = Utility.GetCurrentRealTime()
    sceneCheckTicks = 0
    sceneRestartCount = 0
    string via = "actor"
    if talkProxy != None && akSender == talkProxy
        via = "proxy"
    endif
    if !scn.IsPlaying()
        scn.Start()
        if !scn.IsPlaying()
            scn.ForceStart()
        endif
    endif
    Trace("codsworth scene talk requested scene=" + scn + " via=" + via + " stage=" + EffectiveStage())
    StartTimer(SceneOpenCheckSeconds, 2)
EndEvent

Function RunCodsworthTalk()
    if talkBoxOpen || IsWarfareMode()
        return
    endif
    if !ShouldUseMessageBox()
        Trace("codsworth messagebox suppressed reason=glob_off")
        return
    endif
    Message curMsg = ResolveTalkMsg(-1)
    if curMsg == None
        return
    endif
    codsworthTalkReloaded = False
    talkSessionId += 1
    int mySession = talkSessionId
    talkBoxOpen = True
    dialogueSeen = True
    Trace("codsworth talk opened stage=" + EffectiveStage())
    int steps = 0
    bool doneLoop = False
    while !doneLoop && steps < 16
        steps += 1
        int btn = curMsg.Show()
        if codsworthTalkReloaded || mySession != talkSessionId || btn < 0
            doneLoop = True
        else
            Trace("codsworth choice button=" + btn)
            if btn == 0
                if !completed
                    AdvanceTo(20, "info")
                    SyncProgress()
                endif
                Message r0 = ResolveTalkMsg(0)
                if r0 != None
                    curMsg = r0
                endif
            elseif btn == 1
                if !completed
                    AdvanceTo(30, "info")
                    SyncProgress()
                endif
                Message r1 = ResolveTalkMsg(1)
                if r1 != None
                    curMsg = r1
                endif
            elseif btn == 2
                if !completed
                    AdvanceTo(40, "info")
                    SyncProgress()
                endif
                Message r2 = ResolveTalkMsg(2)
                if r2 != None
                    curMsg = r2
                endif
            else
                if btn == 3 && !completed
                    AdvanceTo(100, "info")
                    SyncProgress()
                endif
                doneLoop = True
            endif
        endif
    endwhile
    if !codsworthTalkReloaded && mySession == talkSessionId
        talkBoxOpen = False
    endif
EndFunction

Event OnStageSet(int auiStageID, int auiItemID)
    if auiStageID > applied
        string cause = "other"
        if auiStageID == pendingStage
            cause = pendingStageBy
        elseif dialogueSeen && (auiStageID == 20 || auiStageID == 30 || auiStageID == 40 || auiStageID == 100)
            cause = "info"
        endif
        applied = auiStageID
        Trace("codsworth01 stage " + auiStageID + " by=" + cause)
    endif
    int prevPending = pendingStage
    pendingStage = auiStageID
    SyncProgress()
    if pendingStage == auiStageID
        pendingStage = prevPending
        if pendingStage == auiStageID
            pendingStage = -1
        endif
    endif
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID == 2
        CheckCodsworthSceneOpen()
        return
    elseif aiTimerID == 3
        EnsureTalkProxy(Game.GetPlayer())
        StartTimer(5.0, 3)
        return
    elseif aiTimerID != 1
        return
    endif
    if !completed
        if !IsRunning()
            Start()
        endif
        if applied > 0 && GetStage() < applied
            SetStage(applied)
        endif
        if applied >= 10 && !concordCleared && !IsObjectiveDisplayed(10)
            ShowCodsworthObjective()
        endif
    endif
    EnsureTalkProxy(Game.GetPlayer())
    SyncProgress()
    if !completed
        StartTimer(1.0, 1)
    else
        StartTimer(5.0, 3)
    endif
EndEvent

Function SyncProgress()
    string infoCause = "other"
    if dialogueSeen
        infoCause = "info"
    endif
    if (GetStageDone(20) || pendingStage == 20 || applied == 20) && !choice1Seen
        choice1Seen = True
        choicesCount += 1
        if applied < 20
            applied = 20
            Trace("codsworth01 stage 20 by=" + infoCause)
        endif
        Trace("codsworth01 choice=1 choices=" + choicesCount)
    endif
    if (GetStageDone(30) || pendingStage == 30 || applied == 30) && !choice2Seen
        choice2Seen = True
        choicesCount += 1
        if applied < 30
            applied = 30
            Trace("codsworth01 stage 30 by=" + infoCause)
        endif
        Trace("codsworth01 choice=2 choices=" + choicesCount)
    endif
    if (GetStageDone(40) || pendingStage == 40 || applied == 40) && !choice3Seen
        choice3Seen = True
        choicesCount += 1
        if applied < 40
            applied = 40
            Trace("codsworth01 stage 40 by=" + infoCause)
        endif
        Trace("codsworth01 choice=3 choices=" + choicesCount)
    endif
    if !completed && (GetStageDone(100) || GetStage() >= 100 || applied >= 100 || pendingStage == 100)
        completed = True
        if !choice4Seen
            choice4Seen = True
            choicesCount += 1
        endif
        if applied < 100
            applied = 100
            Trace("codsworth01 stage 100 by=" + infoCause)
        endif
        if GetStage() < 100
            pendingStage = 100
            pendingStageBy = infoCause
            SetStage(100)
        endif
        SetObjectiveCompleted(10)
        FO4SF_Min00Quest min00 = Game.GetFormFromFile(0x000800, "FO4SFMission.esm") as FO4SF_Min00Quest
        string pointedStr = "false"
        if min00 != None
            if !min00.IsRunning()
                min00.StartNoWait()
            endif
            min00.GiveFromCodsworth()
            pointedStr = "true"
        endif
        CompleteQuest()
        if talkProxy != None && !talkProxy.IsDeleted()
            CancelTimer(1)
        endif
        if dialogueSeen
            Trace("codsworth talk end -> min00 stage 10")
        endif
        Trace("codsworth01 complete choices=" + choicesCount + " concord_pointed=" + pointedStr)
    endif
EndFunction

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
