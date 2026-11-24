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
bool Property EnableS3HouseSearch = False Auto Const
Actor[] Property S3House1Bloatflies Auto Const
Actor[] Property S3House2Bloatflies Auto Const
Scene Property S3Stage50Scene Auto Const
ObjectReference Property S3House1Marker Auto Const
ObjectReference Property S3House2Marker Auto Const
Package Property S3House1TravelPack Auto Const
Package Property S3House2TravelPack Auto Const
GlobalVariable Property S3CreatureSlotReady Auto Const
ObjectReference[] Property S3BloatflyMarkers Auto Const
string Property CreaturePlugin = "" Auto Const
int Property CreatureBloatflyNpcId = 0 Auto Const
float Property S3ArrivalRadius = 10.0 Auto Const
float Property S3House1X = -2313.44 Auto Const
float Property S3House1Y = -1372.02 Auto Const
float Property S3House1Z = 112.66 Auto Const
float Property S3House2X = -2296.17 Auto Const
float Property S3House2Y = -1424.97 Auto Const
float Property S3House2Z = 111.77 Auto Const
int Property S3House1RequiredKills = 3 Auto Const
int Property S3House2RequiredKills = 3 Auto Const

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
bool s3House1Started = False
bool s3House1Cleared = False
int s3House1Dead = 0
bool s3House2Started = False
bool s3House2Cleared = False
int s3House2Dead = 0
bool s3ConcordPointed = False
int s3Stage = 0
Actor[] s3SpawnedHouse1
Actor[] s3SpawnedHouse2
bool s3CreatureSlotEmpty = False
bool s3EmptyLogged = False
bool s3Stage50SceneStarted = False
int s3Stage50Retries = 0
bool s3Stage50MenuOpened = False
bool s3Stage50AttemptOpened = False
bool s3Stage50Pending = False
bool s3Stage50Restarting = False
bool s3Stage50Phase1 = False
float s3Stage50Phase1At = 0.0
float s3Stage50AttemptStartedAt = 0.0
int s3Stage50CheckTicks = 0

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
    if S3Stage50Scene != None
        RegisterForRemoteEvent(S3Stage50Scene, "OnBegin")
        RegisterForRemoteEvent(S3Stage50Scene, "OnPhaseBegin")
        RegisterForRemoteEvent(S3Stage50Scene, "OnEnd")
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
    s3Stage50Pending = False
    s3Stage50MenuOpened = False
    s3Stage50AttemptOpened = False
    s3Stage50Restarting = False
    s3Stage50Phase1 = False
    s3Stage50Phase1At = 0.0
    s3Stage50AttemptStartedAt = 0.0
    s3Stage50CheckTicks = 0
    s3Stage50Retries = 0
    ownSceneStopPending = False
    sceneAttemptStartedAt = 0.0
    CancelTimer(2)
    CancelTimer(4)
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
            if s3Stage50Pending || (S3Stage50Scene != None && S3Stage50Scene.IsPlaying())
                s3Stage50MenuOpened = True
                s3Stage50AttemptOpened = True
                s3Stage50Pending = False
                s3Stage50Phase1 = False
                s3Stage50Phase1At = 0.0
                s3Stage50Retries = 0
                s3Stage50AttemptStartedAt = 0.0
                CancelTimer(4)
                Trace("codsworth s3_stage50 dialogue menu opened")
            endif
            bool anyPlaying = (scn != None && scn.IsPlaying()) || (postScn != None && postScn.IsPlaying())
            if sceneTalkPending || anyPlaying
                sceneMenuOpened = True
                sceneTalkPending = False
                scenePhase1Entered = False
                scenePhase1At = 0.0
                sceneRestartCount = 0
                sceneAttemptStartedAt = 0.0
                CancelTimer(2)
                Trace("codsworth dialogue menu opened")
            endif
        elseif sceneMenuOpened || s3Stage50MenuOpened
            if s3Stage50MenuOpened
                s3Stage50MenuOpened = False
                Trace("codsworth s3_stage50 dialogue menu closed stage=" + EffectiveStage())
            endif
            if sceneMenuOpened
                sceneMenuOpened = False
                Trace("codsworth dialogue menu closed stage=" + EffectiveStage())
            endif
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
    if S3Stage50Scene != None && akSender == S3Stage50Scene
        s3Stage50Phase1 = False
        s3Stage50Phase1At = 0.0
        s3Stage50CheckTicks = 0
        Trace("codsworth01 s3_stage50 scene started")
        return
    endif
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
    if S3Stage50Scene != None && akSender == S3Stage50Scene
        Trace("codsworth01 s3_stage50 phase=" + auiPhaseIndex)
        if auiPhaseIndex >= 1
            s3Stage50Phase1 = True
            s3Stage50Phase1At = Utility.GetCurrentRealTime()
            if s3Stage50Pending && !s3Stage50MenuOpened && !dialogueMenuOpen
                CancelTimer(4)
                StartTimer(SceneOpenCheckSeconds, 4)
            endif
        endif
        return
    endif
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
    if S3Stage50Scene != None && akSender == S3Stage50Scene
        if s3Stage50Restarting
            s3Stage50Restarting = False
            return
        endif
        if !completed && s3House2Cleared && !s3ConcordPointed
            if GetStageDone(100) || GetStage() >= 100 || s3Stage50MenuOpened || s3Stage50AttemptOpened || ShouldUseMessageBox()
                s3Stage50Pending = False
                s3Stage50MenuOpened = False
                s3Stage50AttemptOpened = False
                s3Stage50Phase1 = False
                s3Stage50Phase1At = 0.0
                s3Stage50AttemptStartedAt = 0.0
                CancelTimer(4)
                CompleteS3AndPointToConcord()
            elseif s3Stage50Pending && !s3Stage50MenuOpened
                float nowEnd50 = Utility.GetCurrentRealTime()
                if s3Stage50AttemptStartedAt > 0.0 && nowEnd50 < s3Stage50AttemptStartedAt
                    s3Stage50AttemptStartedAt = nowEnd50
                endif
                float attElapsed50 = nowEnd50 - s3Stage50AttemptStartedAt
                if s3Stage50AttemptStartedAt > 0.0 && attElapsed50 < (SceneOpenCheckSeconds - 0.05)
                    CancelTimer(4)
                    StartTimer(SceneOpenCheckSeconds - attElapsed50, 4)
                else
                    RestartOrCompleteS3Stage50Scene("scene_incomplete")
                endif
            else
                s3Stage50Pending = False
                s3Stage50AttemptOpened = False
                s3Stage50Phase1 = False
                s3Stage50Phase1At = 0.0
                s3Stage50AttemptStartedAt = 0.0
            endif
        else
            s3Stage50Pending = False
            s3Stage50AttemptOpened = False
            s3Stage50Phase1 = False
            s3Stage50Phase1At = 0.0
            s3Stage50AttemptStartedAt = 0.0
        endif
        return
    endif
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
    if IsWarfareMode() || talkBoxOpen || dialogueMenuOpen || sceneTalkPending || s3Stage50Pending
        return
    endif
    if EnableS3HouseSearch && !completed && !s3ConcordPointed && EffectiveStage() == 50 && S3Stage50Scene != None && !ShouldUseMessageBox()
        s3Stage50SceneStarted = False
        s3Stage50Retries = 0
        StartS3Stage50Scene()
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
    GlobalVariable r11FullGlob = Game.GetFormFromFile(0x000B8B, "FO4SFMission.esm") as GlobalVariable
    bool r11S3Gate = r11FullGlob != None && r11FullGlob.GetValue() != 0.0
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
                    if r11S3Gate
                        AdvanceTo(22, "info")
                    else
                        AdvanceTo(30, "info")
                    endif
                    SyncProgress()
                endif
                Message r1 = ResolveTalkMsg(1)
                if r1 != None
                    curMsg = r1
                endif
            elseif btn == 2
                if !completed
                    if r11S3Gate
                        AdvanceTo(24, "info")
                    else
                        AdvanceTo(40, "info")
                    endif
                    SyncProgress()
                endif
                Message r2 = ResolveTalkMsg(2)
                if r2 != None
                    curMsg = r2
                endif
            else
                if btn == 3 && !completed
                    if r11S3Gate
                        AdvanceTo(30, "info")
                        SyncProgress()
                        StartTimer(0.1, 1)
                    else
                        AdvanceTo(100, "info")
                        SyncProgress()
                    endif
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
    elseif aiTimerID == 4
        CheckS3Stage50SceneOpen()
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
    if EnableS3HouseSearch && !completed
        UpdateS3HouseSearchProgress()
    endif
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

int Function CountDeadActors(Actor[] actors)
    if actors == None
        return 0
    endif
    int total = 0
    int i = 0
    while i < actors.Length
        Actor a = actors[i]
        if a != None && a.IsDead()
            total += 1
        endif
        i += 1
    endwhile
    return total
EndFunction

ObjectReference Function ResolveCommonwealthHostAnchor()
    ObjectReference mm = Game.GetFormFromFile(0x0A775B, "FO4TerrainCore.esm") as ObjectReference
    if mm != None
        return mm
    endif
    ObjectReference wb = Game.GetFormFromFile(0x005C50, "FO4TerrainCore.esm") as ObjectReference
    if wb != None
        return wb
    endif
    Actor p = Game.GetPlayer()
    if p != None && !p.IsInInterior()
        return p
    endif
    return None
EndFunction

Function PlaceMarkerInCommonwealth(ObjectReference mk, float tx, float ty, float tz)
    if mk == None
        return
    endif
    ObjectReference host = ResolveCommonwealthHostAnchor()
    if host == None
        return
    endif
    float dx = mk.GetPositionX() - tx
    float dy = mk.GetPositionY() - ty
    if mk.GetWorldSpace() != host.GetWorldSpace() || dx * dx + dy * dy > 4.0
        mk.MoveTo(host, tx - host.GetPositionX(), ty - host.GetPositionY(), tz - host.GetPositionZ(), False, False)
    endif
    mk.EnableNoWait(False)
EndFunction

Function DriveCodsworthToS3Marker(ObjectReference marker, float tx, float ty, float tz)
    if marker != None
        PlaceMarkerInCommonwealth(marker, tx, ty, tz)
    endif
    Actor cods = ResolveCodsworth()
    if cods == None || marker == None
        return
    endif
    EnsureCodsworthAlias(cods)
    cods.SetRestrained(False)
    cods.SetLinkedRef(marker, None, True)
    cods.EvaluatePackage()
EndFunction

Function InitS3SpawnedArrays()
    if s3SpawnedHouse1 == None || s3SpawnedHouse1.Length != 3
        s3SpawnedHouse1 = new Actor[3]
    endif
    if s3SpawnedHouse2 == None || s3SpawnedHouse2.Length != 3
        s3SpawnedHouse2 = new Actor[3]
    endif
EndFunction

Function SpawnS3HouseBloatflies(int houseIndex)
    InitS3SpawnedArrays()
    bool hasStaticList = (houseIndex == 1 && S3House1Bloatflies != None && S3House1Bloatflies.Length > 0) || (houseIndex == 2 && S3House2Bloatflies != None && S3House2Bloatflies.Length > 0)
    if hasStaticList
        s3CreatureSlotEmpty = False
        return
    endif
    ActorBase flyBase = None
    if S3CreatureSlotReady != None && S3CreatureSlotReady.GetValue() != 0.0 && CreaturePlugin != "" && CreatureBloatflyNpcId > 0
        flyBase = Game.GetFormFromFile(CreatureBloatflyNpcId, CreaturePlugin) as ActorBase
    endif
    if flyBase == None || S3BloatflyMarkers == None || S3BloatflyMarkers.Length < 6
        s3CreatureSlotEmpty = True
        if !s3EmptyLogged
            s3EmptyLogged = True
            Trace("codsworth01 s3 creature_slot=empty fallback=arrival_advance")
        endif
        return
    endif
    s3CreatureSlotEmpty = False
    float[] fx = new float[6]
    float[] fy = new float[6]
    float[] fz = new float[6]
    fx[0] = -2313.14
    fy[0] = -1372.39
    fz[0] = 112.66
    fx[1] = -2316.80
    fy[1] = -1377.73
    fz[1] = 112.66
    fx[2] = -2323.03
    fy[2] = -1375.19
    fz[2] = 112.66
    fx[3] = -2294.09
    fy[3] = -1424.36
    fz[3] = 111.75
    fx[4] = -2288.62
    fy[4] = -1432.94
    fz[4] = 111.75
    fx[5] = -2286.38
    fy[5] = -1426.89
    fz[5] = 111.75
    int baseOff = 0
    if houseIndex == 2
        baseOff = 3
    endif
    int i = 0
    while i < 3
        int idx = baseOff + i
        ObjectReference mk = S3BloatflyMarkers[idx]
        if mk != None
            PlaceMarkerInCommonwealth(mk, fx[idx], fy[idx], fz[idx])
            Actor bf = mk.PlaceActorAtMe(flyBase, 0, None, True, False, False)
            if houseIndex == 1
                s3SpawnedHouse1[i] = bf
            else
                s3SpawnedHouse2[i] = bf
            endif
        endif
        i += 1
    endwhile
    Trace("codsworth01 s3 spawned bloatflies house=" + houseIndex + " count=3")
EndFunction

bool Function IsActorNearS3House(Actor a, float hx, float hy, float hz)
    if a == None
        return False
    endif
    float dx = a.GetPositionX() - hx
    float dy = a.GetPositionY() - hy
    return dx * dx + dy * dy <= S3ArrivalRadius * S3ArrivalRadius
EndFunction

float Function GetCodsworthHouseDist(int houseIndex)
    Actor cods = ResolveCodsworth()
    if cods == None
        return -1.0
    endif
    float hx = S3House1X
    float hy = S3House1Y
    if houseIndex == 2
        hx = S3House2X
        hy = S3House2Y
    endif
    float dx = cods.GetPositionX() - hx
    float dy = cods.GetPositionY() - hy
    return Math.Sqrt(dx * dx + dy * dy)
EndFunction

bool Function IsArrivedAtS3House(int houseIndex)
    float hx = S3House1X
    float hy = S3House1Y
    float hz = S3House1Z
    if houseIndex == 2
        hx = S3House2X
        hy = S3House2Y
        hz = S3House2Z
    endif
    return IsActorNearS3House(ResolveCodsworth(), hx, hy, hz)
EndFunction

bool Function StartS3House1Search()
{R11 Step 3q (gated behind EnableS3HouseSearch == True; default False preserves 2g-fix):
 Begins Sanctuary House 1 search (-2313.44, -1372.02, 112.66; PACK 0019E138 -> 0019E136) with 3 Bloatfly slots or
 creature_slot=empty arrival advance along FO4 stages 20->30->32.}
    if !EnableS3HouseSearch || completed || s3House1Started
        return False
    endif
    s3House1Started = True
    if EffectiveStage() < 20
        SetStage(20)
        applied = 20
        s3Stage = 20
    endif
    SetStage(30)
    applied = 30
    s3Stage = 30
    SetObjectiveDisplayed(30, True, True)
    SetObjectiveDisplayed(32, True, True)
    SetActive(True)
    DriveCodsworthToS3Marker(S3House1Marker, S3House1X, S3House1Y, S3House1Z)
    SpawnS3HouseBloatflies(1)
    Trace("codsworth01 stage 30 house=1")
    SetStage(32)
    applied = 32
    s3Stage = 32
    return True
EndFunction

bool Function StartS3House2Search()
{R11 Step 3q: Advances Sanctuary search to House 2 (-2296.17, -1424.97, 111.77; PACK 0019E144 -> 0019E143)
 with 3 Bloatfly slots or creature_slot=empty arrival advance (stages 36->38).}
    if !EnableS3HouseSearch || completed || !s3House1Cleared || s3House2Started
        return False
    endif
    s3House2Started = True
    SetStage(36)
    applied = 36
    s3Stage = 36
    SetObjectiveDisplayed(34, True, True)
    SetActive(True)
    DriveCodsworthToS3Marker(S3House2Marker, S3House2X, S3House2Y, S3House2Z)
    SpawnS3HouseBloatflies(2)
    Trace("codsworth01 stage 36 house=2")
    SetStage(38)
    applied = 38
    s3Stage = 38
    return True
EndFunction

int Function RecordS3BloatflyKill(int houseIndex)
{R11 Step 3q: Records one Bloatfly kill in House 1 (3 required) or House 2 (3 required) and advances stages strictly at 3/3.}
    if !EnableS3HouseSearch || completed
        return 0
    endif
    if houseIndex == 1 && s3House1Started && !s3House1Cleared
        if s3House1Dead < S3House1RequiredKills
            s3House1Dead += 1
        endif
        UpdateS3HouseSearchProgress()
        return s3House1Dead
    elseif houseIndex == 2 && s3House2Started && !s3House2Cleared
        if s3House2Dead < S3House2RequiredKills
            s3House2Dead += 1
        endif
        UpdateS3HouseSearchProgress()
        return s3House2Dead
    endif
    return 0
EndFunction

Function StartS3Stage50Scene()
    if S3Stage50Scene == None || ShouldUseMessageBox()
        CompleteS3AndPointToConcord()
        return
    endif
    if s3Stage50SceneStarted || s3ConcordPointed || completed
        return
    endif
    s3Stage50SceneStarted = True
    s3Stage50MenuOpened = False
    s3Stage50AttemptOpened = False
    s3Stage50Retries = 0
    s3Stage50Phase1 = False
    s3Stage50Phase1At = 0.0
    s3Stage50AttemptStartedAt = Utility.GetCurrentRealTime()
    s3Stage50CheckTicks = 0
    if !S3Stage50Scene.IsPlaying()
        s3Stage50Restarting = False
    endif
    s3Stage50Pending = True
    Actor cods = ResolveCodsworth()
    EnsureCodsworthAlias(cods)
    if cods != None
        cods.AllowPCDialogue(True)
        cods.BlockActivation(False, False)
    endif
    if !S3Stage50Scene.IsPlaying()
        S3Stage50Scene.Start()
        if !S3Stage50Scene.IsPlaying()
            S3Stage50Scene.ForceStart()
        endif
    endif
    Trace("codsworth01 stage 50 scene started")
    StartTimer(SceneOpenCheckSeconds, 4)
EndFunction

Function RestartOrCompleteS3Stage50Scene(string reason)
    if s3ConcordPointed || completed
        return
    endif
    if S3Stage50Scene == None || ShouldUseMessageBox()
        s3Stage50Pending = False
        s3Stage50Phase1 = False
        s3Stage50Phase1At = 0.0
        s3Stage50AttemptStartedAt = 0.0
        CancelTimer(4)
        CompleteS3AndPointToConcord()
        return
    endif
    Actor cods = ResolveCodsworth()
    if s3Stage50Retries < MaxSceneRestarts
        s3Stage50Retries += 1
        if S3Stage50Scene.IsPlaying()
            s3Stage50Restarting = True
            S3Stage50Scene.Stop()
        endif
        s3Stage50Pending = True
        s3Stage50MenuOpened = False
        s3Stage50AttemptOpened = False
        s3Stage50Phase1 = False
        s3Stage50Phase1At = 0.0
        s3Stage50AttemptStartedAt = Utility.GetCurrentRealTime()
        s3Stage50CheckTicks = 0
        EnsureCodsworthAlias(cods)
        S3Stage50Scene.Start()
        if !S3Stage50Scene.IsPlaying()
            S3Stage50Scene.ForceStart()
        endif
        Trace("codsworth01 s3_stage50 scene_restart retry=" + s3Stage50Retries + "/" + MaxSceneRestarts + " reason=" + reason)
        CancelTimer(4)
        StartTimer(SceneOpenCheckSeconds, 4)
    else
        s3Stage50Pending = False
        s3Stage50Phase1 = False
        s3Stage50Phase1At = 0.0
        s3Stage50AttemptStartedAt = 0.0
        CancelTimer(4)
        if S3Stage50Scene.IsPlaying()
            s3Stage50Restarting = True
            S3Stage50Scene.Stop()
        else
            s3Stage50Restarting = False
        endif
        if cods != None
            cods.AllowPCDialogue(True)
            cods.BlockActivation(False, False)
        endif
        Trace("codsworth01 s3_stage50 ERROR scene_failed retries=" + s3Stage50Retries + "/" + MaxSceneRestarts + " reason=" + reason + " actor_talkable=true")
    endif
EndFunction

Function CheckS3Stage50SceneOpen()
    if !s3Stage50Pending || s3ConcordPointed || completed
        return
    endif
    if S3Stage50Scene == None || ShouldUseMessageBox()
        s3Stage50Pending = False
        s3Stage50Phase1 = False
        s3Stage50Phase1At = 0.0
        s3Stage50AttemptStartedAt = 0.0
        CompleteS3AndPointToConcord()
        return
    endif
    if s3Stage50MenuOpened || s3Stage50AttemptOpened || dialogueMenuOpen
        s3Stage50Pending = False
        s3Stage50Phase1 = False
        s3Stage50Phase1At = 0.0
        s3Stage50AttemptStartedAt = 0.0
        return
    endif
    s3Stage50CheckTicks += 1
    float nowRt = Utility.GetCurrentRealTime()
    if s3Stage50AttemptStartedAt > 0.0 && nowRt < s3Stage50AttemptStartedAt
        s3Stage50AttemptStartedAt = nowRt
    endif
    float attemptElapsed = SceneOpenCheckSeconds
    if s3Stage50AttemptStartedAt > 0.0
        attemptElapsed = nowRt - s3Stage50AttemptStartedAt
    endif
    bool phase1Elapsed = False
    if s3Stage50Phase1
        if nowRt < s3Stage50Phase1At
            s3Stage50Phase1At = nowRt
        elseif (nowRt - s3Stage50Phase1At) >= (SceneOpenCheckSeconds - 0.05)
            phase1Elapsed = True
        endif
    endif
    if !S3Stage50Scene.IsPlaying()
        if attemptElapsed < (SceneOpenCheckSeconds - 0.05)
            StartTimer(SceneOpenCheckSeconds - attemptElapsed, 4)
        else
            RestartOrCompleteS3Stage50Scene("scene_inactive")
        endif
    elseif (phase1Elapsed || s3Stage50CheckTicks >= SceneMaxWaitChecks) && attemptElapsed >= (SceneOpenCheckSeconds - 0.05)
        RestartOrCompleteS3Stage50Scene("dialogue_menu_timeout")
    elseif phase1Elapsed || s3Stage50CheckTicks >= SceneMaxWaitChecks
        StartTimer(SceneOpenCheckSeconds - attemptElapsed, 4)
    else
        StartTimer(SceneOpenCheckSeconds, 4)
    endif
EndFunction

Function UpdateS3HouseSearchProgress()
{R11 Step 3q: Drives exact FO4 S3 stage chain 20 -> 30 -> 32 -> 34 -> 36 -> 38 -> 40 -> 50 -> 100 for 3+3 Bloatflies
 or advances cleanly on arrival when creature_slot=empty.}
    if !EnableS3HouseSearch || completed
        return
    endif
    if !s3House1Started
        if EffectiveStage() >= 30
            StartS3House1Search()
        else
            return
        endif
    endif
    if s3House1Started && !s3House1Cleared
        if s3CreatureSlotEmpty
            if IsArrivedAtS3House(1)
                s3House1Dead = S3House1RequiredKills
                Trace("codsworth01 s3 creature_slot=empty arrival house=1 codsworth_dist=" + GetCodsworthHouseDist(1))
            endif
        else
            int polled1 = CountDeadActors(S3House1Bloatflies)
            if s3SpawnedHouse1 != None
                int sp1 = CountDeadActors(s3SpawnedHouse1)
                if sp1 > polled1
                    polled1 = sp1
                endif
            endif
            if polled1 > s3House1Dead
                s3House1Dead = polled1
            endif
        endif
        if s3House1Dead > S3House1RequiredKills
            s3House1Dead = S3House1RequiredKills
        endif
        if s3House1Dead >= S3House1RequiredKills
            s3House1Cleared = True
            SetStage(34)
            applied = 34
            s3Stage = 34
            SetObjectiveCompleted(32)
            Trace("codsworth01 house1_cleared dead=" + s3House1Dead + "/" + S3House1RequiredKills + " stage=34")
            StartS3House2Search()
        endif
    endif
    if s3House2Started && !s3House2Cleared
        if s3CreatureSlotEmpty
            if IsArrivedAtS3House(2)
                s3House2Dead = S3House2RequiredKills
                Trace("codsworth01 s3 creature_slot=empty arrival house=2 codsworth_dist=" + GetCodsworthHouseDist(2))
            endif
        else
            int polled2 = CountDeadActors(S3House2Bloatflies)
            if s3SpawnedHouse2 != None
                int sp2 = CountDeadActors(s3SpawnedHouse2)
                if sp2 > polled2
                    polled2 = sp2
                endif
            endif
            if polled2 > s3House2Dead
                s3House2Dead = polled2
            endif
        endif
        if s3House2Dead > S3House2RequiredKills
            s3House2Dead = S3House2RequiredKills
        endif
        if s3House2Dead >= S3House2RequiredKills
            s3House2Cleared = True
            SetStage(40)
            applied = 40
            s3Stage = 40
            SetObjectiveCompleted(34)
            SetObjectiveCompleted(30)
            Trace("codsworth01 house2_cleared dead=" + s3House2Dead + "/" + S3House2RequiredKills + " stage=40")
            SetStage(50)
            applied = 50
            s3Stage = 50
            StartS3Stage50Scene()
        endif
    endif
EndFunction

bool Function CompleteS3AndPointToConcord()
{R11 Step 3q: Finalizes S3 after House 1 (3/3) and House 2 (3/3) Bloatflies are cleared -> stage 100, points to Concord.}
    if !EnableS3HouseSearch || !s3House1Cleared || !s3House2Cleared || s3ConcordPointed
        return False
    endif
    s3ConcordPointed = True
    s3Stage50Pending = False
    s3Stage50AttemptStartedAt = 0.0
    CancelTimer(4)
    completed = True
    SetStage(100)
    applied = 100
    s3Stage = 100
    SetObjectiveCompleted(10)
    SetObjectiveDisplayed(55, True, True)
    SetObjectiveCompleted(55)
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
    Trace("codsworth01 stage 100 concord_pointed=" + pointedStr)
    return True
EndFunction
