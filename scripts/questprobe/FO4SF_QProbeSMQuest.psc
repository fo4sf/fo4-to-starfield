Scriptname FO4SF_QProbeSMQuest extends Quest
{FO4SF_QProbeSM's script (docs/questprobe/engine-questions.md, E5): the quest is not start game enabled and only our
 Story Manager branch, gated on FO4SF_QProbeEvent, can start it. Starting logs one line and nothing else.}

Event OnQuestInit()
    Debug.OpenUserLog("fo4sf_qprobe")
    Debug.TraceUser("fo4sf_qprobe", "FO4SF_QPROBE rt=" + Utility.GetCurrentRealTime() + " sm quest started")
EndEvent
