Scriptname FO4SF_Codsworth01Quest extends Quest
{MQ102-lite Sanctuary conversation quest (FO4SFMission.esm 0x000816, started via StartNoWait at FO4SFNewGame stage 200).
 Story mode only (FO4SF_GameMode 0x000870 != 2). Drives objective 10 on Codsworth and runs the 4-choice Sanctuary talk:
   stage 20 = choice 1 (date / what happened)
   stage 30 = choice 2 (Sanctuary / family)
   stage 40 = choice 3 (nearby survivors)
   stage 100 = choice 4 (head to Concord -> completes FO4SF_Codsworth01 and gives FO4SF_Min00 stage 10).}

Actor Property Codsworth Auto Const
Scene Property CodsworthScene Auto Const
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
float SceneOpenCheckSeconds = 1.5
int SceneMaxWaitChecks = 16

bool instanceStarted = False
bool dialogueSeen = False
bool dialogueMenuOpen = False
bool talkBoxOpen = False
bool sceneTalkPending = False
bool sceneMenuOpened = False
bool scenePhase1Entered = False
int sceneCheckTicks = 0
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

Function RegisterCodsworthSceneEvents()
    Scene scn = ResolveCodsworthScene()
    if scn != None
        RegisterForRemoteEvent(scn, "OnBegin")
        RegisterForRemoteEvent(scn, "OnPhaseBegin")
        RegisterForRemoteEvent(scn, "OnEnd")
    endif
EndFunction

Function BindCodsworthActivation()
    Actor cods = ResolveCodsworth()
    if cods != None
        cods.AllowPCDialogue(True)
        cods.BlockActivation(False, False)
        EnsureCodsworthAlias(cods)
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
    if talkProxy == None || talkProxy.IsDeleted()
        Activator acti = ResolveTalkActi()
        if acti != None
            talkProxy = cods.PlaceAtMe(acti, 1, True, True, False)
            if talkProxy != None
                talkProxy.SetScale(ProxyScale)
                talkProxy.SetPosition(cx, cy, cz + ProxyZOffset)
                talkProxy.EnableNoWait(False)
                talkProxy.BlockActivation(False, False)
                RegisterForRemoteEvent(talkProxy, "OnActivate")
                proxyLastX = cx
                proxyLastY = cy
                proxyLastZ = cz
                if !proxyLogged
                    proxyLogged = True
                    Trace("codsworth talk proxy ready ref=" + talkProxy + " z=" + (cz + ProxyZOffset))
                endif
            endif
        endif
    else
        float mx = cx - proxyLastX
        float my = cy - proxyLastY
        float mz = cz - proxyLastZ
        if mx * mx + my * my + mz * mz > ProxyResyncDrift * ProxyResyncDrift
            talkProxy.SetPosition(cx, cy, cz + ProxyZOffset)
            proxyLastX = cx
            proxyLastY = cy
            proxyLastZ = cz
        endif
    endif
EndFunction

Function ClearObjectiveOnConcordStart()
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
    SetObjectiveDisplayed(10, True, False)
    SetActive(True)
    Trace("codsworth01 init stage=10")
    StartTimer(1.0, 1)
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    dialogueMenuOpen = False
    talkBoxOpen = False
    sceneTalkPending = False
    sceneMenuOpened = False
    scenePhase1Entered = False
    sceneCheckTicks = 0
    CancelTimer(2)
    Trace("codsworth01 reload stage=" + GetStage() + " choices=" + choicesCount)
    BindCodsworthActivation()
    if !completed
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
            if sceneTalkPending || (scn != None && scn.IsPlaying())
                sceneMenuOpened = True
                sceneTalkPending = False
                scenePhase1Entered = False
                CancelTimer(2)
                Trace("codsworth dialogue menu opened")
            endif
        elseif sceneMenuOpened
            Trace("codsworth dialogue menu closed stage=" + GetStage())
            SyncProgress()
        endif
    endif
EndEvent

Event Scene.OnBegin(Scene akSender)
    Scene scn = ResolveCodsworthScene()
    if scn != None && akSender == scn
        dialogueSeen = True
        Trace("codsworth talk scene started stage=" + GetStage())
    endif
EndEvent

Event Scene.OnPhaseBegin(Scene akSender, int auiPhaseIndex)
    Scene scn = ResolveCodsworthScene()
    if scn != None && akSender == scn && auiPhaseIndex == 1
        scenePhase1Entered = True
    endif
EndEvent

Event Scene.OnEnd(Scene akSender)
    Scene scn = ResolveCodsworthScene()
    if scn != None && akSender == scn
        SyncProgress()
        Trace("codsworth talk scene ended stage=" + GetStage() + " completed=" + completed)
        if sceneTalkPending && !sceneMenuOpened && !completed
            sceneTalkPending = False
            scenePhase1Entered = False
            CancelTimer(2)
            Trace("codsworth talk fallback=messagebox reason=scene_incomplete")
            RunCodsworthTalk()
        else
            sceneTalkPending = False
            sceneMenuOpened = False
            scenePhase1Entered = False
        endif
    endif
EndEvent

Function CheckCodsworthSceneOpen()
    if !sceneTalkPending
        return
    endif
    if dialogueMenuOpen || sceneMenuOpened || talkBoxOpen || completed
        sceneTalkPending = False
        scenePhase1Entered = False
        return
    endif
    sceneCheckTicks += 1
    Scene scn = ResolveCodsworthScene()
    if scn == None || !scn.IsPlaying()
        sceneTalkPending = False
        scenePhase1Entered = False
        Trace("codsworth talk fallback=messagebox reason=scene_inactive")
        RunCodsworthTalk()
    elseif scenePhase1Entered || sceneCheckTicks >= SceneMaxWaitChecks
        sceneTalkPending = False
        scenePhase1Entered = False
        scn.Stop()
        Trace("codsworth talk fallback=messagebox reason=dialogue_menu_timeout")
        RunCodsworthTalk()
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
    Scene scn = ResolveCodsworthScene()
    if scn == None
        Trace("codsworth talk fallback=messagebox reason=no_scene")
        RunCodsworthTalk()
        return
    endif
    if completed
        if talkProxy != None && akSender == talkProxy && cods != None
            cods.Activate(player, True)
        endif
        return
    endif
    EnsureCodsworthAlias(cods)
    dialogueSeen = True
    sceneTalkPending = True
    sceneMenuOpened = False
    scenePhase1Entered = False
    sceneCheckTicks = 0
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
    Trace("codsworth scene talk requested scene=" + scn + " via=" + via + " stage=" + GetStage())
    StartTimer(SceneOpenCheckSeconds, 2)
EndEvent

Function RunCodsworthTalk()
    if talkBoxOpen || IsWarfareMode()
        return
    endif
    Message curMsg = ResolveTalkMsg(-1)
    if curMsg == None
        return
    endif
    talkBoxOpen = True
    dialogueSeen = True
    Trace("codsworth talk opened stage=" + GetStage())
    int steps = 0
    bool doneLoop = False
    while !doneLoop && steps < 16
        steps += 1
        int btn = curMsg.Show()
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
    endwhile
    talkBoxOpen = False
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
    SyncProgress()
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID == 2
        CheckCodsworthSceneOpen()
        return
    elseif aiTimerID != 1
        return
    endif
    EnsureTalkProxy(Game.GetPlayer())
    SyncProgress()
    if !completed
        StartTimer(1.0, 1)
    elseif talkProxy == None || talkProxy.IsDeleted()
        StartTimer(5.0, 1)
    endif
EndEvent

Function SyncProgress()
    string infoCause = "other"
    if dialogueSeen
        infoCause = "info"
    endif
    if GetStageDone(20) && !choice1Seen
        choice1Seen = True
        choicesCount += 1
        if applied < 20
            applied = 20
            Trace("codsworth01 stage 20 by=" + infoCause)
        endif
        Trace("codsworth01 choice=1 choices=" + choicesCount)
    endif
    if GetStageDone(30) && !choice2Seen
        choice2Seen = True
        choicesCount += 1
        if applied < 30
            applied = 30
            Trace("codsworth01 stage 30 by=" + infoCause)
        endif
        Trace("codsworth01 choice=2 choices=" + choicesCount)
    endif
    if GetStageDone(40) && !choice3Seen
        choice3Seen = True
        choicesCount += 1
        if applied < 40
            applied = 40
            Trace("codsworth01 stage 40 by=" + infoCause)
        endif
        Trace("codsworth01 choice=3 choices=" + choicesCount)
    endif
    if !completed && (GetStageDone(100) || GetStage() >= 100)
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
