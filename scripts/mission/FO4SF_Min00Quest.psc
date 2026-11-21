Scriptname FO4SF_Min00Quest extends Quest
{A cut-down "When Freedom Calls" (fo4-to-starfield, docs/mission/when-freedom-calls.md): the Concord raiders,
 Preston Garvey and the reward, started at FO4SFNewGame stage 200 via StartNoWait().
 Stages: 10 started (find Preston), 20 the fight started, 30 the raiders are cleared (talk to Preston), 35 Preston's
 final exchange (0x092A), 40 talked to Preston (the reward), 200 complete (starts FO4SF_Sanctuary01 0x000817). Every
 stage change and a status line every 5 s go to the user log "fo4sf_mission"
 (My Games\Starfield\Logs\Script\User\fo4sf_mission.0.log).}

Actor Property Preston Auto Const Mandatory
{Preston's placed actor (FO4SFMission.esm 0x802).}

Actor[] Property Raiders Auto Const Mandatory
{The Concord raiders' placed actors (FO4SFMission.esm 0x803 on).}

MiscObject Property Credits Auto Const Mandatory
{Starfield's credits: the reward that stands in for Fallout 4's caps.}

Actor Property Codsworth Auto Const
{Codsworth's placed actor (FO4SFMission.esm 0x811), set only on his keeper quest (FO4SF_CodsworthKeeper, 0x814); None
 on FO4SF_Min00 and in a --no-codsworth build. Not part of the mission.}

bool Property KeeperOnly = False Auto Const
{True on FO4SF_CodsworthKeeper: this instance only keeps Codsworth (enabled, put back at his merged spot, PlaceCodsworth)
 and Preston (put back at his merged spot, KeepPreston) and never runs the mission.}

Scene Property PrestonTalkScene Auto Const
{Short 3-exchange Starfield player-dialogue Scene (0x900) on FO4SF_Min00 when built with --alias; None on --no-alias
 and on FO4SF_CodsworthKeeper.}

Message Property PrestonTalkMsg Auto Const
Message Property PrestonReply0Msg Auto Const
Message Property PrestonReply1Msg Auto Const
Message Property PrestonReply2Msg Auto Const
GlobalVariable Property TalkUseMessageBox Auto Const
float Property PrestonSceneCheckSeconds = 1.5 Auto Const
int Property PrestonSceneMaxWaitChecks = 16 Auto Const

float Property MergeOffsetX = -1200.0 Auto Const
float Property MergeOffsetY = -2700.0 Auto Const
{The core world's merge offset (vmad_patch.MERGE_MEASURED): the world the player walks in places the core's records at
 their local position + this; z unchanged.}

float Property RelocateRadius = 800.0 Auto Const
{Move an actor only when the player stands outdoors within this many units of that actor's merged spot.}

float Property RelocateGap = 1500.0 Auto Const
{...and Preston is farther than this from the player.}

float Property PrestonLocalX = -811.14 Auto Const
float Property PrestonLocalY = 1002.46 Auto Const
float Property PrestonLocalZ = 89.09 Auto Const
{Preston's spot in the plugin (ACHR 0x802, the museum door's outside arrival: points.json "preston" pos).}

float Property CodsworthLocalX = -1146.709 Auto Const
float Property CodsworthLocalY = 1293.837 Auto Const
float Property CodsworthLocalZ = 111.734 Auto Const
{Codsworth's spot in the plugin (ACHR 0x811, Fallout 4's ACHR 01CA7D: points.json "codsworth" pos).}

float Property PlaceRadius = 300.0 Auto Const
{Preston and Codsworth are placed only when the player stands outdoors within this many m of their merged spot.}

float Property HoldRadius = 25.0 Auto Const
{Preston (Codsworth) counts as at his spot within this many m of it (and within RelocateGap of the player).}

float Property HeldRadius = 3.0 Auto Const
{...and he is held there (HoldPreston, HoldCodsworth) when calm and within this many m of it.}

int Property RewardCount = 100 Auto Const
{Fallout 4 gives 100 caps (DialogueConcordArea stage 40).}

float Property CodsworthCheck = 5.0 Auto Const
{Seconds between the keeper's relocation checks (KeepCodsworth, KeepPreston).}

int Property KeeperStatusEvery = 12 Auto Const
{The keeper logs where Preston and Codsworth are every this many checks (12 x 5 s = a minute), and at each save load.}

float Property EngageRadius = 60.0 Auto Const
{The fight starts when the player comes this close (m) to a living raider, as FO4's DN092 StartCombat on its ambush.}

float Property FindRadius = 20.0 Auto Const
{...or, before the fight, comes this close (m) to Preston or activates him.}

float Property TalkRadius = 3.0 Auto Const
{Standing this close (m) to Preston counts as the fallback talk completion if the scene cannot start or times out.}

float Property TalkFallbackSeconds = 120.0 Auto Const
{Seconds within TalkRadius with no active scene before fallback completion triggers (logged as stage 40 by=fallback).}

float Property TalkSceneTimeout = 120.0 Auto Const
{Maximum seconds an active Preston talk scene blocks the proximity fallback before timeout.}

float Property GiveConcordRadius = 150.0 Auto Const
{Distance (m) from the Concord museum door at which FO4SF_Min00 displays its first objective if Codsworth has not given it yet.}

float Property Wfc01CheckRadius = 150.0 Auto Const
float Property Wfc01DoorRadius = 100.0 Auto Const
float Property Wfc01SubterraneanDrop = 8.0 Auto Const
float Property Wfc01MaxDrift = 140.0 Auto Const
float Property Wfc01AbsentDistance = 250.0 Auto Const
float Property Wfc01AbsentLimit = 60.0 Auto Const
float Property Wfc01StuckMoveRadius = 2.0 Auto Const
float Property Wfc01StuckLimit = 60.0 Auto Const

string LogName = "fo4sf_mission"
bool instanceStarted = False
bool min00Given = False
int ticks = 0
int relocateFails = 0
int codsworthFails = 0
int prestonFails = 0
int keeperChecks = 0
int prestonMoves = 0
float prestonOff = -1.0
string prestonState = "none"
bool prestonHeld = False
int prestonHolds = 0
bool prestonFollow = False
bool prestonFighting = False
int codsworthMoves = 0
float codsworthOff = -1.0
string codsworthState = "none"
bool codsworthHeld = False
int codsworthHolds = 0
bool codsworthFighting = False
bool codsworthKept = False
int applied = 0
int pendingStage = -1
string pendingStageBy = "other"
bool prestonFound = False
bool talkActivated = False
int talkFailures = 0
float talkStartedAt = 0.0
float talkNearSec = 0.0
bool prestonUsedFallback = False
bool prestonTalkLogged = False
bool prestonTalkBoxOpen = False
bool prestonDialogueMenuOpen = False
bool prestonScenePending = False
bool prestonSceneMenuOpened = False
bool prestonScenePhase1 = False
int prestonSceneChecks = 0

float[] raiderTargetX
float[] raiderTargetY
float[] raiderTargetZ
float[] raiderAbsentSec
bool[] raiderCleared
bool[] raiderRescued
float[] raiderRescueSec
float[] raiderRescueX
float[] raiderRescueY
float[] raiderRescueZ
float[] raiderRescueHp
ActorValue healthAvCache

bool Function IsWarfareMode()
    GlobalVariable gm = Game.GetFormFromFile(0x000870, "FO4SFCoreValues.esm") as GlobalVariable
    if gm != None && (gm.GetValue() as int) == 2
        return True
    endif
    return False
EndFunction

bool Function IsTestModeEnabled()
    GlobalVariable tm = Game.GetFormFromFile(0x000860, "FO4SFCoreValues.esm") as GlobalVariable
    return tm != None && tm.GetValue() != 0.0
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

Function EnsurePrestonAlias()
    if Preston == None
        return
    endif
    ReferenceAlias al = GetAlias(0) as ReferenceAlias
    if al != None && al.GetActorRef() != Preston
        al.ForceRefTo(Preston)
    endif
EndFunction

Function RegisterPrestonSceneEvents()
    if PrestonTalkScene != None
        RegisterForRemoteEvent(PrestonTalkScene, "OnBegin")
        RegisterForRemoteEvent(PrestonTalkScene, "OnPhaseBegin")
        RegisterForRemoteEvent(PrestonTalkScene, "OnEnd")
    endif
EndFunction

Event OnQuestStarted()
    StartQuestInstance()
EndEvent

Event OnQuestInit()
    StartQuestInstance()
EndEvent

Function LogWarfareStop()
    if KeeperOnly
        Trace("mission gate mode=2 started=false quest=keeper")
    else
        Trace("mission gate mode=2 started=false")
    endif
EndFunction

Function StartQuestInstance()
    if instanceStarted
        return
    endif
    instanceStarted = True
    Debug.OpenUserLog(LogName)
    if IsWarfareMode()
        LogWarfareStop()
        Stop()
        return
    endif
    if KeeperOnly
        Trace("keeper init codsworth=" + Codsworth)
        RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")
        KeepCodsworthLoad()
        return
    endif
    Trace("mission gate mode=1 started=true")
    InitRaiderTracking()
    Trace("init raiders=" + Raiders.Length)
    RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")
    EnsureActorTalkable(Preston)
    EnsurePrestonAlias()
    RegisterForMenuOpenCloseEvent("DialogueMenu")
    RegisterForRemoteEvent(Preston, "OnActivate")
    RegisterPrestonSceneEvents()
    Preston.IgnoreFriendlyHits(True)                     ; a stray shot in the fight must not turn him (in game 18 Oct 15:16)
    ; M1: starts silent with NO objective shown until Codsworth's talk finishes or the player reaches <= 150 m of Concord
    StartTimer(1.0, 1)
    KeepCodsworthStart()
EndFunction

Function ClearCodsworthObjectiveForConcord()
    FO4SF_Codsworth01Quest cods01 = Game.GetFormFromFile(0x000816, "FO4SFMission.esm") as FO4SF_Codsworth01Quest
    if cods01 != None
        cods01.ClearObjectiveOnConcordStart()
    endif
EndFunction

Function GiveFromCodsworth()
{Called by FO4SF_Codsworth01Quest at stage 100 so Codsworth's last choice reveals FO4SF_Min00 objective 10.}
    if IsWarfareMode()
        return
    endif
    if !min00Given && GetStage() < 10
        min00Given = True
        Trace("min00 given by=codsworth")
        AdvanceTo(10, "info")
    elseif GetStage() < 20
        SetObjectiveDisplayed(10)
        SetActive(True)
    endif
EndFunction

Function InitRaiderTracking()
    int count = Raiders.Length
    if raiderCleared != None && raiderCleared.Length == count && raiderRescued != None && raiderRescued.Length == count
        return
    endif
    raiderTargetX = new float[count]
    raiderTargetY = new float[count]
    raiderTargetZ = new float[count]
    raiderAbsentSec = new float[count]
    raiderCleared = new bool[count]
    raiderRescued = new bool[count]
    raiderRescueSec = new float[count]
    raiderRescueX = new float[count]
    raiderRescueY = new float[count]
    raiderRescueZ = new float[count]
    raiderRescueHp = new float[count]
    float doorX = PrestonLocalX + MergeOffsetX
    float doorY = PrestonLocalY + MergeOffsetY
    float doorZ = PrestonLocalZ
    int i = 0
    while i < count
        Actor r = Raiders[i]
        float tx = doorX - 18.0
        float ty = doorY
        float tz = doorZ
        if r != None
            float rx = r.GetPositionX()
            float ry = r.GetPositionY()
            float rz = r.GetPositionZ()
            float ux = rx + MergeOffsetX
            float uy = ry + MergeOffsetY
            if (ux - doorX) * (ux - doorX) + (uy - doorY) * (uy - doorY) <= RelocateRadius * RelocateRadius
                tx = ux
                ty = uy
                tz = rz
            elseif (rx - doorX) * (rx - doorX) + (ry - doorY) * (ry - doorY) <= Wfc01MaxDrift * Wfc01MaxDrift && rz >= doorZ - Wfc01SubterraneanDrop
                tx = rx
                ty = ry
                tz = rz
            endif
        endif
        raiderTargetX[i] = tx
        raiderTargetY[i] = ty
        raiderTargetZ[i] = tz
        raiderAbsentSec[i] = 0.0
        raiderCleared[i] = False
        raiderRescued[i] = False
        raiderRescueSec[i] = 0.0
        raiderRescueX[i] = tx
        raiderRescueY[i] = ty
        raiderRescueZ[i] = tz
        raiderRescueHp[i] = -1.0
        i += 1
    endwhile
EndFunction

Function KeepCodsworthStart()
{Starts Codsworth's own check once (review 20 Oct); also from the mission timer, for a save that ran OnQuestInit before
 this check existed.}
    if Codsworth != None && !codsworthKept
        codsworthKept = True
        StartTimer(CodsworthCheck, 2)
    endif
EndFunction

Function KeepCodsworthLoad()
{The keeper's start, at its init and on every save load: Codsworth enabled, fresh budgets of failed moves for him and
 Preston, one line each of where they are (in the log and on screen), the timer (re)started.}
    if Codsworth != None
        if Codsworth.IsDisabled()
            Codsworth.Enable()
            Trace("codsworth was disabled: enabled")
        endif
        EnsureActorTalkable(Codsworth)
        codsworthFails = 0
        codsworthKept = True
        codsworthHeld = False
    endif
    EnsureActorTalkable(Preston)
    prestonFails = 0
    prestonHeld = False
    ; prestonFollow stays as the save left it. Clearing it here would put the door hold back over a follow.
    TracePreston("keeper load")
    if IsTestModeEnabled()
        Debug.Notification("FO4SF keeper: Preston " + (prestonOff as int) + " m from his spot (last: " + prestonState + ", moves " + prestonMoves + ")")
    endif
    if Codsworth != None
        TraceCodsworth("keeper load")
        if IsTestModeEnabled()
            Debug.Notification("FO4SF keeper: Codsworth " + (codsworthOff as int) + " m from his spot (last: " + codsworthState + ", moves " + codsworthMoves + ")")
        endif
    endif
    StartTimer(CodsworthCheck, 2)
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    if KeeperOnly
        KeepCodsworthLoad()
        return
    endif
    relocateFails = 0
    prestonHeld = False
    prestonTalkBoxOpen = False
    prestonDialogueMenuOpen = False
    prestonScenePending = False
    prestonSceneMenuOpened = False
    prestonScenePhase1 = False
    prestonSceneChecks = 0
    CancelTimer(3)
    EnsureActorTalkable(Preston)
    RegisterForRemoteEvent(Preston, "OnActivate")
    InitRaiderTracking()
    int st = GetStage()
    Trace("reload mission stage=" + st + " relocate_fails=" + relocateFails)
    if st < 200
        EnsurePrestonAlias()
        RegisterForMenuOpenCloseEvent("DialogueMenu")
        RegisterPrestonSceneEvents()
        if st == 20
            CheckConcordRaidersWfc01(Game.GetPlayer(), False)
        endif
        StartTimer(1.0, 1)
    endif
EndEvent

Function AdvanceTo(int n, string by = "Trigger")
{SetStage, then the stage's actions. Apply runs each stage once.}
    pendingStage = n
    pendingStageBy = by
    SetStage(n)
    Apply(n, by)
    if pendingStage == n
        pendingStage = -1
    endif
EndFunction

Event OnStageSet(int auiStageID, int auiItemID)
    string cause = "other"
    if auiStageID == pendingStage
        cause = pendingStageBy
        pendingStage = -1
    elseif auiStageID == 35 && talkActivated && !prestonUsedFallback
        cause = "info"
    endif
    Apply(auiStageID, cause)
EndEvent

Function Apply(int auiStageID, string by = "other")
    if auiStageID <= applied
        return
    endif
    applied = auiStageID
    Trace("stage " + auiStageID + " by=" + by)
    if auiStageID == 10
        min00Given = True
        SetObjectiveDisplayed(10)
        SetActive(True)
    elseif auiStageID == 20
        SetObjectiveCompleted(10)
        SetObjectiveDisplayed(85)
    elseif auiStageID == 30
        Preston.StopCombat()                             ; in game 18 Oct: downed in the fight, he got up and shot the player
        SetObjectiveCompleted(85)
        SetObjectiveDisplayed(86)
    elseif auiStageID == 35
        if by == "info" && !prestonUsedFallback && !prestonTalkLogged
            prestonTalkLogged = True
            Trace("preston talk end info=0x092A -> stage 40")
            AdvanceTo(40, "info")
        else
            AdvanceTo(40, "other")
        endif
    elseif auiStageID == 40
        SetObjectiveCompleted(86)
        Game.GetPlayer().AddItem(Credits, RewardCount)
        Trace("reward credits=" + RewardCount)
    elseif auiStageID == 200
        CancelTimer(1)
        Quest sanctuaryQuest = Game.GetFormFromFile(0x000817, "FO4SFMission.esm") as Quest
        if sanctuaryQuest != None && !sanctuaryQuest.IsRunning()
            bool startedSanctuary = sanctuaryQuest.StartNoWait()
            Trace("sanctuary01 start_requested ok=" + startedSanctuary)
        endif
    endif
EndFunction

Message Function ResolvePrestonMsg(int slot)
    if slot == 0
        if PrestonReply0Msg != None
            return PrestonReply0Msg
        endif
        return Game.GetFormFromFile(0x000976, "FO4SFMission.esm") as Message
    elseif slot == 1
        if PrestonReply1Msg != None
            return PrestonReply1Msg
        endif
        return Game.GetFormFromFile(0x000977, "FO4SFMission.esm") as Message
    elseif slot == 2
        if PrestonReply2Msg != None
            return PrestonReply2Msg
        endif
        return Game.GetFormFromFile(0x000978, "FO4SFMission.esm") as Message
    endif
    if PrestonTalkMsg != None
        return PrestonTalkMsg
    endif
    return Game.GetFormFromFile(0x000975, "FO4SFMission.esm") as Message
EndFunction

Function RunPrestonTalk(int stage, Message startMsg)
    if prestonTalkBoxOpen || startMsg == None || IsWarfareMode()
        return
    endif
    prestonTalkBoxOpen = True
    Message curMsg = startMsg
    Trace("preston talk opened stage=" + stage)
    int steps = 0
    bool doneLoop = False
    while !doneLoop && steps < 16
        steps += 1
        int btn = curMsg.Show()
        Trace("preston choice button=" + btn)
        if btn == 0
            Message r0 = ResolvePrestonMsg(0)
            if r0 != None
                curMsg = r0
            endif
        elseif btn == 1
            Message r1 = ResolvePrestonMsg(1)
            if r1 != None
                curMsg = r1
            endif
        elseif btn == 2
            Message r2 = ResolvePrestonMsg(2)
            if r2 != None
                curMsg = r2
            endif
        else
            if btn == 3 && GetStage() == 30
                talkActivated = True
                prestonUsedFallback = False
                AdvanceTo(35, "info")
                if GetStage() == 40
                    AdvanceTo(200, "Trigger")
                    CompleteQuest()
                    Trace("complete stage=" + GetStage())
                endif
            endif
            doneLoop = True
        endif
    endwhile
    prestonTalkBoxOpen = False
EndFunction

Function FallbackPrestonToMessageBox(string reason)
    prestonScenePending = False
    prestonScenePhase1 = False
    CancelTimer(3)
    Trace("preston talk fallback=messagebox reason=" + reason)
    Message talkMsg = ResolvePrestonMsg(-1)
    if talkMsg != None
        RunPrestonTalk(GetStage(), talkMsg)
    elseif GetStage() == 30
        prestonUsedFallback = True
        AdvanceTo(40, "fallback")
    endif
EndFunction

Function CheckPrestonSceneOpen()
    if KeeperOnly || !prestonScenePending
        return
    endif
    if prestonDialogueMenuOpen || prestonSceneMenuOpened || prestonTalkBoxOpen || prestonTalkLogged || GetStage() != 30
        prestonScenePending = False
        prestonScenePhase1 = False
        return
    endif
    prestonSceneChecks += 1
    if PrestonTalkScene == None || !PrestonTalkScene.IsPlaying()
        FallbackPrestonToMessageBox("scene_inactive")
    elseif prestonScenePhase1 || prestonSceneChecks >= PrestonSceneMaxWaitChecks
        prestonScenePending = False
        prestonScenePhase1 = False
        PrestonTalkScene.Stop()
        FallbackPrestonToMessageBox("dialogue_menu_timeout")
    else
        StartTimer(PrestonSceneCheckSeconds, 3)
    endif
EndFunction

Event OnMenuOpenCloseEvent(string asMenuName, bool abOpening)
    if KeeperOnly || asMenuName != "DialogueMenu"
        return
    endif
    prestonDialogueMenuOpen = abOpening
    if abOpening
        if prestonScenePending || talkActivated || (PrestonTalkScene != None && PrestonTalkScene.IsPlaying())
            talkActivated = True
            prestonUsedFallback = False
            prestonSceneMenuOpened = True
            prestonScenePending = False
            prestonScenePhase1 = False
            CancelTimer(3)
            Trace("preston dialogue menu opened")
        endif
    elseif prestonSceneMenuOpened
        Trace("preston dialogue menu closed stage=" + GetStage())
    endif
EndEvent

Event Scene.OnBegin(Scene akSender)
    if !KeeperOnly && PrestonTalkScene != None && akSender == PrestonTalkScene
        talkActivated = True
        prestonUsedFallback = False
        if talkStartedAt <= 0.0
            talkStartedAt = Utility.GetCurrentRealTime()
        endif
        Trace("preston talk scene started stage=" + GetStage())
    endif
EndEvent

Event Scene.OnPhaseBegin(Scene akSender, int auiPhaseIndex)
    if !KeeperOnly && PrestonTalkScene != None && akSender == PrestonTalkScene && auiPhaseIndex == 1
        prestonScenePhase1 = True
    endif
EndEvent

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    if akSender == Preston && akActionRef == Game.GetPlayer()
        if prestonTalkBoxOpen || prestonDialogueMenuOpen || prestonScenePending
            return
        endif
        int stage = GetStage()
        Trace("preston activated at stage " + stage)
        if stage < 20
            FoundPreston("activated")                    ; the next check starts the fight
        elseif stage == 30
            Message talkMsg = ResolvePrestonMsg(-1)
            if ShouldUseMessageBox()
                if talkMsg != None
                    Trace("preston talk fallback=messagebox reason=glob")
                    RunPrestonTalk(stage, talkMsg)
                else
                    prestonUsedFallback = True
                    AdvanceTo(40, "fallback")
                endif
            elseif PrestonTalkScene != None
                EnsurePrestonAlias()
                talkActivated = True
                prestonUsedFallback = False
                talkStartedAt = Utility.GetCurrentRealTime()
                prestonScenePending = True
                prestonSceneMenuOpened = False
                prestonScenePhase1 = False
                prestonSceneChecks = 0
                if !PrestonTalkScene.IsPlaying()
                    PrestonTalkScene.Start()
                    if !PrestonTalkScene.IsPlaying()
                        PrestonTalkScene.ForceStart()
                    endif
                endif
                Trace("preston talk scene triggered stage=30")
                Trace("preston scene talk requested scene=" + PrestonTalkScene + " stage=30")
                StartTimer(PrestonSceneCheckSeconds, 3)
            elseif talkMsg != None
                Trace("preston talk fallback=messagebox reason=no_scene")
                RunPrestonTalk(stage, talkMsg)
            else
                prestonUsedFallback = True
                AdvanceTo(40, "fallback")
            endif
        elseif stage >= 200
            Message postMsg = ResolvePrestonMsg(-1)
            if postMsg != None
                RunPrestonTalk(stage, postMsg)
            endif
        endif
    endif
EndEvent

Event Scene.OnEnd(Scene akSender)
    if !KeeperOnly && PrestonTalkScene != None && akSender == PrestonTalkScene
        int st = GetStage()
        bool endInfoDone = GetStageDone(35) || st == 35
        Trace("preston talk scene ended stage=" + st + " end_info=" + endInfoDone)
        if endInfoDone
            prestonScenePending = False
            prestonSceneMenuOpened = False
            prestonScenePhase1 = False
            CancelTimer(3)
            if applied < 35
                Apply(35, "info")
            endif
            if GetStage() == 40
                AdvanceTo(200, "Trigger")
                CompleteQuest()
                Trace("complete stage=" + GetStage())
            endif
        elseif st == 30 && !prestonTalkLogged
            talkFailures += 1
            talkActivated = False
            talkStartedAt = 0.0
            Trace("preston talk retry n=" + talkFailures + " reason=scene_incomplete")
            if prestonScenePending && !prestonSceneMenuOpened
                FallbackPrestonToMessageBox("scene_incomplete")
            else
                prestonScenePending = False
                prestonSceneMenuOpened = False
                prestonScenePhase1 = False
            endif
        else
            prestonScenePending = False
            prestonSceneMenuOpened = False
            prestonScenePhase1 = False
        endif
    endif
EndEvent

bool Function MarkPrestonFallback(string why)
    if !prestonUsedFallback
        prestonUsedFallback = True
        Trace(why)
    endif
    return True
EndFunction

bool Function TalkCompleteReady(int stage, float dp)
    if stage != 30
        return False
    endif
    if prestonTalkLogged
        return True
    endif
    if prestonTalkBoxOpen || prestonDialogueMenuOpen || prestonScenePending
        talkNearSec = 0.0
        return False
    endif
    if PrestonTalkScene == None
        if dp < TalkRadius
            return MarkPrestonFallback("preston talk fallback no_scene")
        endif
        return False
    endif
    if talkFailures >= 3
        return MarkPrestonFallback("preston talk fallback tries=" + talkFailures)
    endif
    if PrestonTalkScene.IsPlaying()
        talkNearSec = 0.0
        if talkStartedAt > 0.0 && (Utility.GetCurrentRealTime() - talkStartedAt) > TalkSceneTimeout
            talkFailures += 1
            PrestonTalkScene.Stop()
            talkActivated = False
            talkStartedAt = 0.0
            Trace("preston talk retry n=" + talkFailures + " reason=timeout")
            if talkFailures >= 3
                return MarkPrestonFallback("preston talk timeout")
            endif
        endif
        return False
    endif
    if talkActivated && talkStartedAt > 0.0 && (Utility.GetCurrentRealTime() - talkStartedAt) >= 15.0
        talkFailures += 1
        talkActivated = False
        talkStartedAt = 0.0
        Trace("preston talk retry n=" + talkFailures + " reason=after_activate")
        if talkFailures >= 3
            return MarkPrestonFallback("preston talk fallback after_activate")
        endif
        return False
    endif
    if dp < TalkRadius
        talkNearSec += 1.0
        float limit = TalkFallbackSeconds
        if IsTestModeEnabled()
            limit = 8.0
        endif
        if talkNearSec >= limit
            return MarkPrestonFallback("preston talk fallback near_sec=" + talkNearSec)
        endif
    else
        talkNearSec = 0.0
    endif
    return False
EndFunction

Function FoundPreston(string how)
{The player reached Preston before the fight (activated him, or came within FindRadius): the fight starts at the next
 check, with every raider put into combat with the player. Logged once. A dead Preston is never found.}
    if !prestonFound && !Preston.IsDead()
        prestonFound = True
        Trace("found preston " + how)
    endif
EndFunction

float Function GetRaiderHealth(Actor r)
    if r == None
        return 0.0
    endif
    if healthAvCache == None
        healthAvCache = Game.GetFormFromFile(0x0002D4, "Starfield.esm") as ActorValue
    endif
    if healthAvCache != None
        return r.GetValue(healthAvCache)
    endif
    return 0.0
EndFunction

Function WriteOffRaider(Actor r, int idx, string reason, float elapsed)
    if r != None
        r.StopCombat()
        r.DisableNoWait(False)
    endif
    raiderCleared[idx] = True
    raiderAbsentSec[idx] = 0.0
    raiderRescueSec[idx] = 0.0
    int fid = 0
    if r != None
        fid = r.GetFormID()
    endif
    Trace("wfc01 raider cleared " + reason + " id=" + fid + " raider=" + idx + " elapsed=" + elapsed + " disabled=true")
EndFunction

Function CheckConcordRaidersWfc01(Actor player, bool advanceClock)
{WFC-01 anti-stall at stage 20: rescues living raiders that fell below terrain (z < targetZ - 8 m) or drifted far
 (> 140 m from their Concord street spot) while the player is within 150 m of the museum door, and writes off (stops
 combat + disables) any living raider that remains absent/unloaded (> 250 m or !Is3DLoaded) for > 60 s within 100 m of
 the Concord door or stays loaded within 2 m with no damage for 60 s after a rescue.}
    if player == None || player.IsInInterior()
        return
    endif
    InitRaiderTracking()
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float pz = player.GetPositionZ()
    float doorX = PrestonLocalX + MergeOffsetX
    float doorY = PrestonLocalY + MergeOffsetY
    float doorZ = PrestonLocalZ
    float ddx = px - doorX
    float ddy = py - doorY
    float ddz = pz - doorZ
    float doorDist = Math.Sqrt(ddx * ddx + ddy * ddy + ddz * ddz)
    int i = 0
    while i < Raiders.Length
        Actor r = Raiders[i]
        if r == None || r.IsDead() || raiderCleared[i]
            raiderAbsentSec[i] = 0.0
            raiderRescueSec[i] = 0.0
        else
            float tx = raiderTargetX[i]
            float ty = raiderTargetY[i]
            float tz = raiderTargetZ[i]
            if doorDist < Wfc01CheckRadius
                float rz = r.GetPositionZ()
                float drift = SpotOff(r, tx, ty, tz)
                if rz < tz - Wfc01SubterraneanDrop || drift > Wfc01MaxDrift
                    r.MoveTo(player, tx - px, ty - py, tz - pz, True, False)
                    r.SetPosition(tx, ty, tz)
                    r.EvaluatePackage()
                    raiderRescued[i] = True
                    raiderRescueSec[i] = 0.0
                    raiderRescueX[i] = r.GetPositionX()
                    raiderRescueY[i] = r.GetPositionY()
                    raiderRescueZ[i] = r.GetPositionZ()
                    raiderRescueHp[i] = GetRaiderHealth(r)
                    Trace("wfc01 rescue raider=" + i + " z=" + rz + " target_z=" + tz + " drift=" + drift)
                endif
            endif
            if advanceClock
                float distToPlayer = player.GetDistance(r)
                if doorDist <= Wfc01DoorRadius && (!r.Is3DLoaded() || distToPlayer > Wfc01AbsentDistance)
                    raiderAbsentSec[i] = raiderAbsentSec[i] + 1.0
                    if raiderAbsentSec[i] > Wfc01AbsentLimit
                        WriteOffRaider(r, i, "absent", raiderAbsentSec[i])
                    endif
                else
                    raiderAbsentSec[i] = 0.0
                endif
                if !raiderCleared[i] && raiderRescued[i]
                    if r.Is3DLoaded()
                        float moved = SpotOff(r, raiderRescueX[i], raiderRescueY[i], raiderRescueZ[i])
                        float hp = GetRaiderHealth(r)
                        bool tookDamage = raiderRescueHp[i] > 0.0 && hp < raiderRescueHp[i] - 0.01
                        if moved < Wfc01StuckMoveRadius && !tookDamage
                            raiderRescueSec[i] = raiderRescueSec[i] + 1.0
                            if hp > raiderRescueHp[i]
                                raiderRescueHp[i] = hp
                            endif
                            if raiderRescueSec[i] >= Wfc01StuckLimit
                                WriteOffRaider(r, i, "stuck", raiderRescueSec[i])
                            endif
                        else
                            raiderRescueSec[i] = 0.0
                            raiderRescueX[i] = r.GetPositionX()
                            raiderRescueY[i] = r.GetPositionY()
                            raiderRescueZ[i] = r.GetPositionZ()
                            raiderRescueHp[i] = hp
                        endif
                    else
                        raiderRescueSec[i] = 0.0
                    endif
                endif
            endif
        endif
        i += 1
    endwhile
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID == 2
        KeepCodsworth()
        return
    elseif aiTimerID == 3
        CheckPrestonSceneOpen()
        return
    elseif aiTimerID != 1
        return
    endif
    Actor player = Game.GetPlayer()
    InitRaiderTracking()
    KeepCodsworthStart()
    ReleaseInFight("mission")                            ; every check, whatever the budget or where the player is
    if relocateFails < 10
        Relocate(player)
    endif
    int stage = GetStage()
    if !min00Given && stage < 10 && player != None && !player.IsInInterior()
        float gdx = player.GetPositionX() - (PrestonLocalX + MergeOffsetX)
        float gdy = player.GetPositionY() - (PrestonLocalY + MergeOffsetY)
        float gdz = player.GetPositionZ() - PrestonLocalZ
        if gdx * gdx + gdy * gdy + gdz * gdz <= GiveConcordRadius * GiveConcordRadius
            min00Given = True
            Trace("min00 given by=concord")
            ClearCodsworthObjectiveForConcord()
            AdvanceTo(10, "Trigger")
            stage = 10
        endif
    endif
    if (GetStageDone(35) || stage == 35) && applied < 35
        if talkActivated && !prestonUsedFallback
            Apply(35, "info")
        else
            Apply(35, "other")
        endif
        stage = GetStage()
    endif
    if stage >= 40 && applied < 40
        Apply(40, "other")
    elseif stage > applied && stage < 35
        Apply(stage, "other")
    endif
    float dp = player.GetDistance(Preston)
    if stage < 20 && dp < FindRadius
        FoundPreston("near d=" + dp)
    endif
    if stage == 20
        CheckConcordRaidersWfc01(player, True)
    endif
    bool everyone = prestonFound || stage >= 20          ; once the fight is on, no raider stands by
    int dead = 0
    bool fighting = false
    float nearest = -1.0
    int i = 0
    while i < Raiders.Length
        Actor r = Raiders[i]
        if r.IsDead() || raiderCleared[i]
            dead += 1
        else
            float d = player.GetDistance(r)
            if nearest < 0.0 || d < nearest
                nearest = d
            endif
            if r.GetCombatState() != 0
                fighting = true
            elseif stage < 30 && (everyone || d < EngageRadius) && r.Is3DLoaded()
                ; FO4's forced fight: a living raider that is not fighting is put into combat, near the player or once
                ; the fight is on (our raider never engages unprompted, npc_combat_c1)
                r.StartCombat(player)
                fighting = true
                Trace("startcombat raider " + i + " d=" + d)
            endif
        endif
        i += 1
    endwhile
    bool readyTalk = TalkCompleteReady(stage, dp)
    int target = NextStage(stage, dead, Raiders.Length, fighting, readyTalk, prestonFound)
    ; every stage on the way is set in order, so each one's objectives and log line happen
    while stage < target && stage < 40
        string nextBy = "Trigger"
        if stage < 10
            if !min00Given
                min00Given = True
                Trace("min00 given by=concord")
                ClearCodsworthObjectiveForConcord()
            endif
            stage = 10
        elseif stage < 20
            stage = 20
        elseif stage < 30
            stage = 30
        else
            stage = 40
            if prestonUsedFallback
                nextBy = "fallback"
            elseif prestonTalkLogged
                nextBy = "info"
            else
                nextBy = "other"
            endif
        endif
        AdvanceTo(stage, nextBy)
    endwhile
    ticks += 1
    if ticks % 5 == 0
        Trace("status stage=" + stage + " dead=" + dead + "/" + Raiders.Length + " nearest_raider=" + nearest + " preston=" + dp + " preston_off=" + prestonOff + " held=" + prestonHeld + " pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ())
    endif
    if Preston.GetCombatTarget() == player               ; he never fights the player (in game 18 Oct: "treats me like an enemy")
        Preston.StopCombat()
        Trace("preston was targeting the player: stopcombat")
    endif
    if GetStage() == 40                                  ; in game 18 Oct the status stayed at 40 after the reward: set 200
        AdvanceTo(200, "Trigger")
        CompleteQuest()
        Trace("complete stage=" + GetStage())
    endif
    if GetStage() < 200                                  ; stage 200 cancels the timer (Apply)
        StartTimer(1.0, 1)
    endif
EndEvent

int Function NextStage(int stage, int dead, int total, bool fighting, bool atPreston, bool found)
{The stage the encounter has reached, whoever started the fight (scripts/mission/make_mission.py next_stage is the
 same rule, tested there): the fight counts as started when a raider fights or is dead, or when the player has found
 Preston (FoundPreston); all raiders dead or cleared is stage 30; completing talk at Preston after that is stage 40.}
    int s = stage
    if s < 20 && (fighting || dead > 0 || found)
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

Function Relocate(Actor player)
{Moves the raiders (Codsworth: KeepCodsworth) from their unmerged local position to the same spot in the merged world the
 player walks in, and puts Preston at his fixed spot (PlacePreston). Never from an interior.}
    if player.IsInInterior()
        return
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float pz = player.GetPositionZ()
    if PlacePreston(player, "mission")
        relocateFails += 1
    endif
    int i = 0
    while i < Raiders.Length
        if MoveOver(Raiders[i], player, px, py, pz, "raider " + i)
            relocateFails += 1
        endif
        i += 1
    endwhile
EndFunction

Function KeepCodsworth()
{Codsworth has his own check every CodsworthCheck seconds with its own budget of 10 failed moves. It keeps running after
 stage 200, which ends the mission's timer.}
    Actor player = Game.GetPlayer()
    if Codsworth != None
        ReleaseCodsworthInFight("keeper")
    endif
    if Codsworth != None && codsworthFails < 10
        if PlaceCodsworth(player)
            codsworthFails += 1
            if codsworthFails >= 10
                codsworthState = "gave up"
                Trace("keeper gave up codsworth fails=" + codsworthFails)
                if IsTestModeEnabled()
                    Debug.Notification("FO4SF keeper: Codsworth not placed after 10 tries; stopped until the next load")
                endif
            endif
        endif
    endif
    if KeeperOnly
        KeepPreston(player)
        if Codsworth != None && keeperChecks % KeeperStatusEvery == 0
            TraceCodsworth("keeper status")
        endif
    endif
    if (Codsworth != None && (codsworthFails < 10 || codsworthHolds > 0)) || (KeeperOnly && (prestonFails < 10 || prestonHolds > 0))
        StartTimer(CodsworthCheck, 2)
    endif
EndFunction

Function KeepPreston(Actor player)
{The keeper keeps Preston at his merged spot after the mission too.}
    ReleaseInFight("keeper")
    if prestonFails < 10
        if PlacePreston(player, "keeper")
            prestonFails += 1
            if prestonFails >= 10
                prestonState = "gave up"
                Trace("keeper gave up preston fails=" + prestonFails)
                if IsTestModeEnabled()
                    Debug.Notification("FO4SF keeper: Preston not placed after 10 tries; stopped until the next load")
                endif
            endif
        endif
    endif
    keeperChecks += 1
    if keeperChecks % KeeperStatusEvery == 0
        TracePreston("keeper status")
    endif
EndFunction

Function BeginFollow()
{FO4SF_COMPreston.FollowTest (test-only, gated behind FO4SF_TestModeEnabled != 0) arms this instance. While prestonFollow
 is set, PlacePreston neither moves him back to the museum door nor restrains him.}
    GlobalVariable testMode = Game.GetFormFromFile(0x000860, "FO4SFCoreValues.esm") as GlobalVariable
    if testMode == None || testMode.GetValue() == 0.0
        Trace("follow preston test-only refused: test mode off")
        return
    endif
    prestonFollow = True
    prestonHeld = False
    prestonState = HeldState("follow", False)
    string who = "mission"
    if KeeperOnly
        who = "keeper"
    endif
    Trace("follow preston armed by=" + who)
EndFunction

bool Function PlacePreston(Actor player, string who)
{Preston's fixed spot (FAL-128): PrestonLocalX/Y/Z + the merge offset, by PlaceAt. FAL-866: once BeginFollow has armed
 this instance, none of that runs.}
    if prestonFollow
        prestonState = HeldState("follow", False)
        return False
    endif
    float tx = PrestonLocalX + MergeOffsetX
    float ty = PrestonLocalY + MergeOffsetY
    float tz = PrestonLocalZ
    bool fighting = Preston.GetCombatState() != 0         ; released already (ReleaseInFight)
    string s = PlaceAt(Preston, "Preston", tx, ty, tz, player, who, "at the museum door", fighting)
    prestonOff = SpotOff(Preston, tx, ty, tz)
    if s == "placed" || s == "move failed"
        prestonMoves += 1
    endif
    if HoldDue(s, fighting, prestonHeld, prestonOff)
        HoldPreston(who)
    endif
    prestonState = HeldState(s, prestonHeld)
    return s == "move failed"
EndFunction

bool Function PlaceCodsworth(Actor player)
{Codsworth's fixed spot (FAL-163): CodsworthLocalX/Y/Z + the merge offset, by PlaceAt, Preston's rule; only the keeper
 places him.}
    float tx = CodsworthLocalX + MergeOffsetX
    float ty = CodsworthLocalY + MergeOffsetY
    float tz = CodsworthLocalZ
    bool fighting = Codsworth.GetCombatState() != 0       ; released already (ReleaseCodsworthInFight)
    string s = PlaceAt(Codsworth, "Codsworth", tx, ty, tz, player, "keeper", "in Sanctuary", fighting)
    codsworthOff = SpotOff(Codsworth, tx, ty, tz)
    if s == "placed" || s == "move failed"
        codsworthMoves += 1
    endif
    if HoldDue(s, fighting, codsworthHeld, codsworthOff)
        HoldCodsworth("keeper")
    endif
    codsworthState = HeldState(s, codsworthHeld)
    return s == "move failed"
EndFunction

string Function PlaceAt(Actor a, string name, float tx, float ty, float tz, Actor player, string who, string where, bool fighting)
{The fixed-spot rule of Preston (FAL-128) and Codsworth (FAL-163).}
    float dp = player.GetDistance(a)                      ; float max: another world
    float off = SpotOff(a, tx, ty, tz)
    if off <= HoldRadius && dp < RelocateGap
        return "at spot"
    endif
    if player.IsInInterior()
        return "off, player inside"
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float pz = player.GetPositionZ()
    if (px - tx) * (px - tx) + (py - ty) * (py - ty) > PlaceRadius * PlaceRadius
        return "off, player away"
    endif
    if dp < RelocateGap && fighting
        return "off, fighting"                            ; the fight moves it; it is put back once the fight is over
    endif
    Trace("world " + name + " player=" + player.GetWorldSpace() + " actor=" + a.GetWorldSpace() + " cell=" + a.GetParentCell())
    a.MoveTo(player, tx - px, ty - py, tz - pz, True, False)
    float d = player.GetDistance(a)
    float after = SpotOff(a, tx, ty, tz)
    bool failed = after > HoldRadius || d >= RelocateGap
    Trace("world " + name + " after=" + a.GetWorldSpace() + " cell=" + a.GetParentCell())
    Trace("moved " + name + " to " + a.GetPositionX() + " " + a.GetPositionY() + " " + a.GetPositionZ() + " target " + tx + " " + ty + " " + tz + " before=" + dp + " off=" + off + " d=" + d + " failed=" + failed + " by=" + who)
    if IsTestModeEnabled()
        Debug.Notification("FO4SF: " + name + " put back " + where + " (" + who + ", was " + (off as int) + " m off, failed=" + failed + ")")
    endif
    if failed
        return "move failed"
    endif
    return "placed"
EndFunction

bool Function HoldDue(string s, bool fighting, bool held, float off)
{Whether PlaceAt's result s calls for a hold (FAL-170, FAL-163).}
    if fighting
        return False
    endif
    return s == "placed" || (s == "at spot" && !held && off <= HeldRadius)
EndFunction

Function HoldPreston(string who)
{Holds Preston where he stands.}
    HoldActor(Preston, "preston", who, prestonOff)
    prestonHeld = True
    prestonHolds += 1
EndFunction

Function HoldCodsworth(string who)
{Holds Codsworth where he stands, as Preston (HoldPreston).}
    HoldActor(Codsworth, "codsworth", who, codsworthOff)
    codsworthHeld = True
    codsworthHolds += 1
EndFunction

Function EnsureActorTalkable(Actor a)
    if a != None
        a.AllowPCDialogue(True)
        a.BlockActivation(False, False)
    endif
EndFunction

Function HoldActor(Actor a, string name, string who, float off)
{SetRestrained(True), keep player talk activation unblocked, and one log line, "hold <name> by=<who> off=<m> ok=<bool>".}
    bool ok = a.SetRestrained(True)
    EnsureActorTalkable(a)
    Trace("hold " + name + " by=" + who + " off=" + off + " ok=" + ok)
EndFunction

bool Function ReleaseInFight(string who)
{Lets Preston go while he fights, whatever this instance's prestonHeld says.}
    if ReleaseActor(Preston, "preston", who, prestonFighting)
        prestonHeld = False
        prestonFighting = True
        return True
    endif
    prestonFighting = False
    return False
EndFunction

bool Function ReleaseCodsworthInFight(string who)
{Codsworth's release in a fight, as Preston's (ReleaseInFight), from the keeper on every check.}
    if ReleaseActor(Codsworth, "codsworth", who, codsworthFighting)
        codsworthHeld = False
        codsworthFighting = True
        return True
    endif
    codsworthFighting = False
    return False
EndFunction

bool Function ReleaseActor(Actor a, string name, string who, bool logged)
{SetRestrained(False) while the actor fights, whatever any flag says; "release <name> by=<who> reason=fighting" once
 per fight (logged: already written). Returns whether it fights.}
    if a.GetCombatState() != 0
        a.SetRestrained(False)
        if !logged
            Trace("release " + name + " by=" + who + " reason=fighting")
        endif
        return True
    endif
    return False
EndFunction

string Function HeldState(string s, bool held)
{A state, with ", held" while this instance holds the actor.}
    if held
        return s + ", held"
    endif
    return s
EndFunction

float Function SpotOff(Actor a, float tx, float ty, float tz)
{An actor's distance (m) from a point, by position only.}
    float ex = a.GetPositionX() - tx
    float ey = a.GetPositionY() - ty
    float ez = a.GetPositionZ() - tz
    return Math.Sqrt(ex * ex + ey * ey + ez * ez)
EndFunction

Function TracePreston(string what)
    prestonOff = SpotOff(Preston, PrestonLocalX + MergeOffsetX, PrestonLocalY + MergeOffsetY, PrestonLocalZ)
    TraceSpot(what, Preston, "preston", prestonOff, prestonState, prestonMoves, prestonHeld, prestonHolds, prestonFails)
EndFunction

Function TraceCodsworth(string what)
    codsworthOff = SpotOff(Codsworth, CodsworthLocalX + MergeOffsetX, CodsworthLocalY + MergeOffsetY, CodsworthLocalZ)
    TraceSpot(what, Codsworth, "codsworth", codsworthOff, codsworthState, codsworthMoves, codsworthHeld, codsworthHolds, codsworthFails)
EndFunction

Function TraceSpot(string what, Actor a, string name, float off, string spotState, int moves, bool held, int holds, int fails)
{One keeper line of where an actor is (State is a Papyrus keyword, so the parameter is spotState).}
    Actor player = Game.GetPlayer()
    Trace(what + " " + name + " d=" + player.GetDistance(a) + " off=" + off + " state=" + spotState + " moves=" + moves + " held=" + held + " holds=" + holds + " at " + a.GetPositionX() + " " + a.GetPositionY() + " " + a.GetPositionZ() + " disabled=" + a.IsDisabled() + " dead=" + a.IsDead() + " fails=" + fails + " player=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " interior=" + player.IsInInterior())
EndFunction

bool Function MoveOver(Actor a, Actor player, float px, float py, float pz, string what)
{Moves one raider when the player is within RelocateRadius of its merged spot and it is still farther than RelocateGap.}
    float before = player.GetDistance(a)                  ; float max: another world; finite: this world (the world proof)
    if before < RelocateGap
        return False                                      ; already where the player is
    endif
    float x = a.GetPositionX() + MergeOffsetX
    float y = a.GetPositionY() + MergeOffsetY
    float z = a.GetPositionZ()
    float dx = px - x
    float dy = py - y
    if dx * dx + dy * dy > RelocateRadius * RelocateRadius
        return False                                      ; the player is not at its merged spot
    endif
    float hx = x - (PrestonLocalX + MergeOffsetX)
    float hy = y - (PrestonLocalY + MergeOffsetY)
    if hx * hx + hy * hy > RelocateRadius * RelocateRadius
        return False                                      ; moved already: never offset twice
    endif
    WorldSpace wa = a.GetWorldSpace()                     ; evidence for Codex's world-identity point (#353): which
    WorldSpace wp = player.GetWorldSpace()                ; world each side is in before a move (only moves: Codex 4331303552)
    Trace("world " + what + " player=" + wp + " actor=" + wa + " cell=" + a.GetParentCell())
    a.MoveTo(player, x - px, y - py, z - pz, True, False)
    float d = player.GetDistance(a)
    bool failed = d >= RelocateGap
    Trace("world " + what + " after=" + a.GetWorldSpace() + " cell=" + a.GetParentCell())
    Trace("moved " + what + " to " + a.GetPositionX() + " " + a.GetPositionY() + " " + a.GetPositionZ() + " target " + x + " " + y + " " + z + " before=" + before + " d=" + d + " failed=" + failed)
    if !failed
        a.EvaluatePackage()
    endif
    return failed
EndFunction

Function Trace(string msg)
    ; User log is opened once at start and once on OnPlayerLoadGame (2f)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
