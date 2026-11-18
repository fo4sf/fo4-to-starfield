Scriptname FO4SF_Codsworth01Quest extends Quest
{MQ102-lite Sanctuary conversation quest (FO4SFMission.esm 0x000816, started via StartNoWait at FO4SFNewGame stage 200).
 Story mode only (FO4SF_GameMode 0x000870 != 2). Drives objective 10 on Codsworth and tracks the 4-choice Scene (0x0940):
   stage 20 = choice 1 (date / what happened)
   stage 30 = choice 2 (Sanctuary / family)
   stage 40 = choice 3 (nearby survivors)
   stage 100 = choice 4 (head to Concord -> completes FO4SF_Codsworth01 and gives FO4SF_Min00 stage 10).}

string LogName = "fo4sf_mission"
bool instanceStarted = False
bool choice1Seen = False
bool choice2Seen = False
bool choice3Seen = False
bool choice4Seen = False
int choicesCount = 0
bool completed = False

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
    SetStage(10)
    SetObjectiveDisplayed(10, True, False)
    SetActive(True)
    Trace("codsworth01 init stage=10")
    StartTimer(1.0, 1)
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    Trace("codsworth01 reload stage=" + GetStage() + " choices=" + choicesCount)
    if !completed
        StartTimer(1.0, 1)
    endif
EndEvent

Event OnStageSet(int auiStageID, int auiItemID)
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
    if GetStageDone(20) && !choice1Seen
        choice1Seen = True
        choicesCount += 1
        Trace("codsworth01 choice=1 choices=" + choicesCount)
    endif
    if GetStageDone(30) && !choice2Seen
        choice2Seen = True
        choicesCount += 1
        Trace("codsworth01 choice=2 choices=" + choicesCount)
    endif
    if GetStageDone(40) && !choice3Seen
        choice3Seen = True
        choicesCount += 1
        Trace("codsworth01 choice=3 choices=" + choicesCount)
    endif
    if !completed && (GetStageDone(100) || GetStage() >= 100)
        completed = True
        if !choice4Seen
            choice4Seen = True
            choicesCount += 1
        endif
        if GetStage() < 100
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
        Trace("codsworth talk end -> min00 stage 10")
        Trace("codsworth01 complete choices=" + choicesCount + " concord_pointed=" + pointedStr)
    endif
EndFunction

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
