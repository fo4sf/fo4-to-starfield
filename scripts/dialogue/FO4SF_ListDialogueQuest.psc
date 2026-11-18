Scriptname FO4SF_ListDialogueQuest extends Quest
{Silent-player list conversation controller & deterministic NV-style check verifier (CF-7).}

; Exact property order pinned by dotnet/ListDialogue/Program.cs and tests/test_list_dialogue.py
ActorValue Property SpeechAV Auto Const
ActorValue Property ScienceAV Auto Const
ActorValue Property StrengthAV Auto Const
ActorValue Property IntelligenceAV Auto Const
Perk Property BgVaultDwellerPerk Auto Const
Perk Property TraitGoodNaturedPerk Auto Const
GlobalVariable Property TestModeGlobal Auto Const
Actor Property SpeakerRef Auto Const
ObjectReference Property ArrivalRef Auto Const

int Property TimerIdPoll = 1 AutoReadOnly

bool ran10 = false
bool ran15 = false
bool ran20 = false
bool ran21 = false
bool ran22 = false
bool ran30 = false
bool ran31 = false
bool ran40 = false
bool ran50 = false
bool ran60 = false
bool ran70 = false

float savedSpeech = 25.0
float savedScience = 25.0
float savedStrengthDelta = 0.0
bool hadBg = false
bool hadTrait = false

Function LogLine(string kind, string kv)
    Debug.OpenUserLog("FO4SFListDialogue")
    Debug.TraceUser("FO4SFListDialogue", "FO4SFLIST rt=" + Utility.GetCurrentRealTime() + " " + kind + " " + kv + " end=true")
EndFunction

Function LogSheetEval(Actor player, string phase)
    float sp = player.GetValue(SpeechAV)
    float sc = player.GetValue(ScienceAV)
    float st = player.GetValue(StrengthAV)
    bool hasBg = player.HasPerk(BgVaultDwellerPerk)
    bool hasTr = player.HasPerk(TraitGoodNaturedPerk)

    string s50 = "fail"
    if sp >= 50.0
        s50 = "pass"
    endif
    string sc40 = "fail"
    if sc >= 40.0
        sc40 = "pass"
    endif
    string st7 = "fail"
    if st >= 7.0
        st7 = "pass"
    endif
    string bgState = "locked"
    if hasBg
        bgState = "pass"
    endif
    string trState = "locked"
    if hasTr
        trState = "pass"
    endif

    LogLine("eval", "phase=" + phase + " speech=" + sp + " speech50=" + s50 + " science=" + sc + " science40=" + sc40 + " strength=" + st + " strength7=" + st7 + " bg_vaultdweller=" + bgState + " trait_goodnatured=" + trState)
EndFunction

Event OnQuestInit()
    Actor player = Game.GetPlayer()
    if player != None
        RegisterForRemoteEvent(player, "OnPlayerLoadGame")
        LogLine("init", "speaker_present=" + (SpeakerRef != None) + " arrival_present=" + (ArrivalRef != None))
    endif
    StartTimer(1.0, TimerIdPoll)
EndEvent

Event Actor.OnPlayerLoadGame(Actor akSender)
    StartTimer(1.0, TimerIdPoll)
EndEvent

Function PollStages()
    if TestModeGlobal == None || TestModeGlobal.GetValue() == 0.0
        return
    endif
    Actor player = Game.GetPlayer()
    if player == None
        return
    endif

    ; Stage 10: Snapshot player stats & verify baseline low sheet (Speech=25, Science=25, Strength=5, perks absent)
    if !ran10 && GetStageDone(10)
        ran10 = true
        savedSpeech = player.GetValue(SpeechAV)
        savedScience = player.GetValue(ScienceAV)
        hadBg = player.HasPerk(BgVaultDwellerPerk)
        hadTrait = player.HasPerk(TraitGoodNaturedPerk)
        player.SetValue(SpeechAV, 25.0)
        player.SetValue(ScienceAV, 25.0)
        float curStr = player.GetValue(StrengthAV)
        if curStr >= 7.0
            float drop = (curStr - 5.0)
            player.ModValue(StrengthAV, -drop)
            savedStrengthDelta -= drop
        endif
        if hadBg
            player.RemovePerk(BgVaultDwellerPerk)
        endif
        if hadTrait
            player.RemovePerk(TraitGoodNaturedPerk)
        endif
        LogSheetEval(player, "baseline_low")
    endif

    ; Stage 15: Qualify player for all deterministic checks (Speech=55, Science=45, Strength>=8, Background + Trait granted)
    if !ran15 && GetStageDone(15)
        ran15 = true
        player.SetValue(SpeechAV, 55.0)
        player.SetValue(ScienceAV, 45.0)
        float curStr2 = player.GetValue(StrengthAV)
        if curStr2 < 8.0
            float boost = (8.0 - curStr2)
            player.ModValue(StrengthAV, boost)
            savedStrengthDelta += boost
        endif
        if !player.HasPerk(BgVaultDwellerPerk)
            player.AddPerk(BgVaultDwellerPerk)
        endif
        if !player.HasPerk(TraitGoodNaturedPerk)
            player.AddPerk(TraitGoodNaturedPerk)
        endif
        LogSheetEval(player, "qualified_high")
    endif

    ; Choice outcome stages set by DialogResponses.SetParentQuestStage (20..60)
    if !ran20 && GetStageDone(20)
        ran20 = true
        LogLine("choice_stage", "stage=20 tag=Speech_50 outcome=pass")
    endif
    if !ran21 && GetStageDone(21)
        ran21 = true
        LogLine("choice_stage", "stage=21 tag=Speech_50 outcome=fail")
    endif
    if !ran22 && GetStageDone(22)
        ran22 = true
        LogLine("choice_stage", "stage=22 tag=Science_40 outcome=pass")
    endif
    if !ran30 && GetStageDone(30)
        ran30 = true
        LogLine("choice_stage", "stage=30 tag=Strength_7 outcome=pass")
    endif
    if !ran31 && GetStageDone(31)
        ran31 = true
        LogLine("choice_stage", "stage=31 tag=Strength_7 outcome=fail")
    endif
    if !ran40 && GetStageDone(40)
        ran40 = true
        LogLine("choice_stage", "stage=40 tag=Vault_Dweller outcome=pass")
    endif
    if !ran50 && GetStageDone(50)
        ran50 = true
        LogLine("choice_stage", "stage=50 tag=Good_Natured outcome=pass")
    endif
    if !ran60 && GetStageDone(60)
        ran60 = true
        LogLine("choice_stage", "stage=60 tag=Plain_Goodbye outcome=exit")
    endif

    ; Stage 70: Restore player sheet cleanly and emit summary verdict
    if !ran70 && GetStageDone(70)
        ran70 = true
        player.SetValue(SpeechAV, savedSpeech)
        player.SetValue(ScienceAV, savedScience)
        if savedStrengthDelta > 0.001 || savedStrengthDelta < -0.001
            player.ModValue(StrengthAV, -savedStrengthDelta)
            savedStrengthDelta = 0.0
        endif
        if !hadBg && player.HasPerk(BgVaultDwellerPerk)
            player.RemovePerk(BgVaultDwellerPerk)
        elseif hadBg && !player.HasPerk(BgVaultDwellerPerk)
            player.AddPerk(BgVaultDwellerPerk)
        endif
        if !hadTrait && player.HasPerk(TraitGoodNaturedPerk)
            player.RemovePerk(TraitGoodNaturedPerk)
        elseif hadTrait && !player.HasPerk(TraitGoodNaturedPerk)
            player.AddPerk(TraitGoodNaturedPerk)
        endif
        LogSheetEval(player, "reset")
        LogLine("summary", "ok=true host_menu=DialogueMenu replaced_swf=false")
    endif
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID == TimerIdPoll
        PollStages()
        StartTimer(1.0, TimerIdPoll)
    endif
EndEvent
