Scriptname FO4SF_Min00Quest extends Quest
{A cut-down "When Freedom Calls" (fo4-to-starfield, docs/mission/when-freedom-calls.md): the Concord raiders,
 Preston Garvey and the reward, driven by a one-second check instead of FO4's triggers, scenes and fragments.
 Stages: 10 started (find Preston), 20 the fight started, 30 the raiders are dead (talk to Preston), 40 talked to
 Preston (the reward), 200 complete. Every stage change and a status line every 5 s go to the user log
 "fo4sf_mission" (My Games\Starfield\Logs\Script\User\fo4sf_mission.0.log), the evidence of a run.}

Actor Property Preston Auto Const Mandatory
{Preston's placed actor (FO4SFMission.esm 0x802).}

Actor[] Property Raiders Auto Const Mandatory
{The Concord raiders' placed actors (FO4SFMission.esm 0x803 on).}

MiscObject Property Credits Auto Const Mandatory
{Starfield's credits: the reward that stands in for Fallout 4's caps.}

int Property RewardCount = 100 Auto Const
{Fallout 4 gives 100 caps (DialogueConcordArea stage 40).}

float Property EngageRadius = 60.0 Auto Const
{The fight starts when the player comes this close (m) to a living raider, as FO4's DN092 StartCombat on its ambush.}

float Property TalkRadius = 3.0 Auto Const
{Standing this close (m) to Preston counts as talking to him once the raiders are dead (no dialogue ported yet).}

string LogName = "fo4sf_mission"
int ticks = 0

Event OnQuestInit()
    Debug.OpenUserLog(LogName)
    Trace("init raiders=" + Raiders.Length)
    RegisterForRemoteEvent(Preston, "OnActivate")
    SetStage(10)
    StartTimer(1.0, 1)
EndEvent

Event OnStageSet(int auiStageID, int auiItemID)
    Trace("stage " + auiStageID)
    if auiStageID == 10
        SetObjectiveDisplayed(10)
    elseif auiStageID == 20
        SetObjectiveCompleted(10)
        SetObjectiveDisplayed(85)
        Debug.Notification("When Freedom Calls: kill the raiders")
    elseif auiStageID == 30
        SetObjectiveCompleted(85)
        SetObjectiveDisplayed(86)
        Debug.Notification("When Freedom Calls: talk to Preston Garvey")
    elseif auiStageID == 40
        SetObjectiveCompleted(86)
        Game.GetPlayer().AddItem(Credits, RewardCount)
        Trace("reward credits=" + RewardCount)
        SetStage(200)
    elseif auiStageID == 200
        Debug.Notification("When Freedom Calls: complete")
        CancelTimer(1)
    endif
EndEvent

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    if akSender == Preston && akActionRef == Game.GetPlayer()
        Trace("preston activated at stage " + GetStage())
        if GetStage() == 30
            SetStage(40)
        endif
    endif
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID != 1
        return
    endif
    Actor player = Game.GetPlayer()
    int stage = GetStage()
    int dead = 0
    bool fighting = false
    float nearest = -1.0
    int i = 0
    while i < Raiders.Length
        Actor r = Raiders[i]
        if r.IsDead()
            dead += 1
        else
            float d = player.GetDistance(r)
            if nearest < 0.0 || d < nearest
                nearest = d
            endif
            if r.GetCombatState() != 0
                fighting = true
            elseif stage < 30 && d < EngageRadius && r.Is3DLoaded()
                ; FO4's forced fight: a living raider near the player that is not fighting is put into combat
                r.StartCombat(player)
                fighting = true
                Trace("startcombat raider " + i + " d=" + d)
            endif
        endif
        i += 1
    endwhile
    float dp = player.GetDistance(Preston)
    int target = NextStage(stage, dead, Raiders.Length, fighting, dp < TalkRadius)
    ; every stage on the way is set in order, so each one's objectives and log line happen
    while stage < target && stage < 40
        if stage < 20
            stage = 20
        elseif stage < 30
            stage = 30
        else
            stage = 40
        endif
        SetStage(stage)
    endwhile
    ticks += 1
    if ticks % 5 == 0
        Trace("status stage=" + stage + " dead=" + dead + "/" + Raiders.Length + " nearest_raider=" + nearest + " preston=" + dp + " pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ())
    endif
    if GetStage() < 200                                  ; stage 40 sets 200 (and cancels the timer) in OnStageSet
        StartTimer(1.0, 1)
    endif
EndEvent

int Function NextStage(int stage, int dead, int total, bool fighting, bool atPreston)
{The stage the encounter has reached, whoever started the fight (scripts/mission/make_mission.py next_stage is the
 same rule, tested there): the fight counts as started when a raider fights or is dead, so a quest that starts or
 reloads mid-fight, or after the raiders died between two checks, still advances; all raiders dead is stage 30;
 standing at Preston after that is stage 40. Never goes back.}
    int s = stage
    if s < 20 && (fighting || dead > 0)
        s = 20
    endif
    if s < 30 && total > 0 && dead == total
        s = 30
    endif
    if s == 30 && atPreston
        s = 40
    endif
    return s
EndFunction

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
