Scriptname FOCC_P10Quest extends Quest
{Attached to QUST FOCC_P10_Quest (FO4SFCombinedProbe.esm 0x820 = 2080; not start game enabled; event Script Event),
 the quest the Story Manager branch FOCC_P10_Branch / FOCC_P10_QuestNode should start when FOCC_Probe.P10Send sends
 FOCC_P10_Event (fo4-to-starfield, docs/spikes/combined-core-probes.md P10). Its only job is to log that it started.}

Event OnQuestInit()
    Debug.OpenUserLog("focc")
    Debug.TraceUser("focc", "FOCC rt=" + Utility.GetCurrentRealTime() + " p10 quest started id=" + GetFormID() + " local=2080")
EndEvent
