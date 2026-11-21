Scriptname FO4SF_Codsworth01Quest extends Quest
{MQ102-lite Sanctuary conversation quest (FO4SFMission.esm 0x000816, started via StartNoWait at FO4SFNewGame stage 200).
 Story mode only (FO4SF_GameMode 0x000870 != 2). Drives objective 10 on Codsworth and tracks the 4-choice Scene (0x0940):
   stage 20 = choice 1 (date / what happened)
   stage 30 = choice 2 (Sanctuary / family)
   stage 40 = choice 3 (nearby survivors)
   stage 100 = choice 4 (head to Concord -> completes FO4SF_Codsworth01 and gives FO4SF_Min00 stage 10).}

string LogName = "fo4sf_mission"
bool instanceStarted = False
bool dialogueSeen = False
int applied = 0
int pendingStage = -1
string pendingStageBy = "other"
bool choice1Seen = False
bool choice2Seen = False
bool choice3Seen = False
bool choice4Seen = False
int choicesCount = 0
bool completed = False

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
    AdvanceTo(10, "Trigger")
    SetObjectiveDisplayed(10, True, False)
    SetActive(True)
    Trace("codsworth01 init stage=10")
    StartTimer(1.0, 1)
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    Trace("codsworth01 reload stage=" + GetStage() + " choices=" + choicesCount)
    if !completed
        RegisterForMenuOpenCloseEvent("DialogueMenu")
        StartTimer(1.0, 1)
    endif
EndEvent

Event OnMenuOpenCloseEvent(string asMenuName, bool abOpening)
    if asMenuName == "DialogueMenu" && abOpening
        dialogueSeen = True
    endif
EndEvent

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
    if aiTimerID != 1
        return
    endif
    SyncProgress()
    if !completed
        StartTimer(1.0, 1)
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
        CancelTimer(1)
        if dialogueSeen
            Trace("codsworth talk end -> min00 stage 10")
        endif
        Trace("codsworth01 complete choices=" + choicesCount + " concord_pointed=" + pointedStr)
    endif
EndFunction

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
