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

Scene Property PrestonPostTalkScene Auto Const
{Repeatable voiced post-mission Starfield player-dialogue Scene (0x990) hosted on FO4SF_CodsworthKeeper (0x814),
 gated by GetStage(FO4SF_Min00) >= 200 and TalkUseMessageBox == 0.}

Message Property PrestonTalkMsg Auto Const
Message Property PrestonReply0Msg Auto Const
Message Property PrestonReply1Msg Auto Const
Message Property PrestonReply2Msg Auto Const
GlobalVariable Property TalkUseMessageBox Auto Const
Weapon Property RaiderWeapon Auto Const
Ammo Property RaiderAmmo Auto Const
Weapon Property RaiderSidearm Auto Const
Ammo Property RaiderSidearmAmmo Auto Const
float Property RaiderSidearmDamage = 3.0 Auto Const
float Property PrestonSceneCheckSeconds = 1.5 Auto Const
int Property PrestonSceneMaxWaitChecks = 16 Auto Const
int Property PrestonMaxSceneRestarts = 3 Auto Const

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
bool prestonPlaced = False
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
bool prestonFallbackActive = False
int talkSessionId = 0
bool prestonTalkReloaded = False
bool prestonDialogueMenuOpen = False
bool prestonScenePending = False
bool prestonSceneMenuOpened = False
bool prestonScenePhase1 = False
float prestonPhase1At = 0.0
int prestonSceneChecks = 0
int prestonSceneRestarts = 0
bool prestonPostSceneActive = False
bool ownPrestonSceneStop = False
float prestonAttemptStartedAt = 0.0
int sanctuaryStartRetries = 0
bool mq103ProxAttempted = False
bool minRecruitProxAttempted = False
bool mq104ProxAttempted = False
bool mq105ProxAttempted = False
bool mq106ProxAttempted = False
bool mq203ProxAttempted = False
bool mq204ProxAttempted = False
bool mq206ProxAttempted = False

float[] raiderTargetX
float[] raiderTargetY
float[] raiderTargetZ
float[] raiderCorpseX
float[] raiderCorpseY
float[] raiderCorpseZ
float[] raiderAbsentSec
bool[] raiderCleared
bool[] raiderRescued
bool[] raiderEngaged
bool[] raiderArmed
float[] raiderStartCombatAt
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

int Function EffectiveStage()
    int st = GetStage()
    if applied > st
        return applied
    endif
    return st
EndFunction

WorldSpace Function ResolveCommonwealthWorld()
    ; Task 1i: resolve host world dynamically from persistent core refs (Sanctuary workbench / V111 marker),
    ; NEVER hardcoded FO4SFMission world copies or Starfield planet worlds.
    ObjectReference benchRef = Game.GetFormFromFile(0x005C50, "FO4TerrainCore.esm") as ObjectReference
    if benchRef != None
        WorldSpace bws = benchRef.GetWorldSpace()
        if bws != None
            return bws
        endif
    endif
    ObjectReference v111Marker = Game.GetFormFromFile(0x0A775B, "FO4TerrainCore.esm") as ObjectReference
    if v111Marker == None
        v111Marker = Game.GetFormFromFile(0x0A775B, "FO4TerrainCore_Mars.esm") as ObjectReference
    endif
    if v111Marker != None
        WorldSpace mws = v111Marker.GetWorldSpace()
        if mws != None
            return mws
        endif
    endif
    if prestonPlaced && Preston != None && !Preston.IsInInterior()
        return Preston.GetWorldSpace()
    endif
    return None
EndFunction

bool Function IsCommonwealthExterior(Actor player)
    if player == None || player.IsInInterior()
        return False
    endif
    WorldSpace ws = player.GetWorldSpace()
    if ws == None
        return False
    endif
    WorldSpace cws = ResolveCommonwealthWorld()
    if cws != None && ws != cws
        return False
    endif
    float cx = player.GetPositionX()
    float cy = player.GetPositionY()
    if cx < MergeOffsetX - 3600.0 || cx > MergeOffsetX + 3600.0
        return False
    endif
    if cy < MergeOffsetY - 3600.0 || cy > MergeOffsetY + 3600.0
        return False
    endif
    return True
EndFunction

bool Function IsPlayerStableAt(Actor player, float px, float py, float pz)
    if !IsCommonwealthExterior(player)
        return False
    endif
    float dx = player.GetPositionX() - px
    float dy = player.GetPositionY() - py
    float dz = player.GetPositionZ() - pz
    return dx * dx + dy * dy + dz * dz <= 25.0
EndFunction

Function EnsurePrestonAlias()
    talkSessionId += 1
    if Preston == None
        return
    endif
    ReferenceAlias al = GetAlias(0) as ReferenceAlias
    if al != None && al.GetActorRef() != Preston
        al.ForceRefTo(Preston)
    endif
EndFunction

Scene Function ResolvePrestonScene()
{C1: Return PrestonTalkScene when bound, otherwise resolve 0x000900 from FO4SFMission.esm (the same route that
 resolved Codsworth's scene in 2f when PrestonTalkScene evaluated to None at runtime despite VMAD binding).}
    if PrestonTalkScene != None
        return PrestonTalkScene
    endif
    return Game.GetFormFromFile(0x000900, "FO4SFMission.esm") as Scene
EndFunction

Scene Function ResolvePrestonSceneLogged()
    if PrestonTalkScene != None
        Trace("preston scene resolved via=property scene=" + PrestonTalkScene)
        return PrestonTalkScene
    endif
    Scene fileScn = Game.GetFormFromFile(0x000900, "FO4SFMission.esm") as Scene
    if fileScn != None
        Trace("preston scene resolved via=file scene=" + fileScn)
        return fileScn
    endif
    Trace("preston scene resolved via=none")
    return None
EndFunction

Scene Function ResolvePrestonPostScene()
    if PrestonPostTalkScene != None
        return PrestonPostTalkScene
    endif
    return Game.GetFormFromFile(0x000990, "FO4SFMission.esm") as Scene
EndFunction

Scene Function ResolveActivePrestonScene(bool postMode)
    if postMode
        return ResolvePrestonPostScene()
    endif
    return ResolvePrestonScene()
EndFunction

Function EnsureKeeperPrestonAlias()
    if Preston == None
        return
    endif
    Quest keeper = Game.GetFormFromFile(0x000814, "FO4SFMission.esm") as Quest
    if keeper != None
        if !keeper.IsRunning()
            keeper.Start()
        endif
        ReferenceAlias al = keeper.GetAlias(0) as ReferenceAlias
        if al != None && al.GetActorRef() != Preston
            al.ForceRefTo(Preston)
        endif
    endif
EndFunction

Function RegisterPrestonSceneEvents()
    Scene scn = ResolvePrestonScene()
    if scn != None
        RegisterForRemoteEvent(scn, "OnBegin")
        RegisterForRemoteEvent(scn, "OnPhaseBegin")
        RegisterForRemoteEvent(scn, "OnEnd")
    endif
    Scene postScn = ResolvePrestonPostScene()
    if postScn != None
        EnsureKeeperPrestonAlias()
        RegisterForRemoteEvent(postScn, "OnBegin")
        RegisterForRemoteEvent(postScn, "OnPhaseBegin")
        RegisterForRemoteEvent(postScn, "OnEnd")
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
    if !IsRunning()
        Start()
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
    if KeeperOnly || IsWarfareMode()
        return
    endif
    if !IsRunning()
        Start()
    endif
    int st = EffectiveStage()
    if !min00Given && st < 10
        min00Given = True
        Trace("min00 given by=codsworth")
        AdvanceTo(10, "info")
    elseif st < 20
        EnsurePrestonAlias()
        SetObjectiveDisplayed(10)
        SetObjectiveDisplayed(10, True, True)
        SetActive(True)
    endif
EndFunction

Function InitRaiderTracking()
    int count = Raiders.Length
    if raiderCleared != None && raiderCleared.Length == count && raiderRescued != None && raiderRescued.Length == count && raiderEngaged != None && raiderEngaged.Length == count && raiderArmed != None && raiderArmed.Length == count && raiderStartCombatAt != None && raiderStartCombatAt.Length == count
        if raiderCorpseX == None || raiderCorpseX.Length != count
            raiderCorpseX = new float[count]
            raiderCorpseY = new float[count]
            raiderCorpseZ = new float[count]
            int ci = 0
            while ci < count
                raiderCorpseX[ci] = raiderTargetX[ci]
                raiderCorpseY[ci] = raiderTargetY[ci]
                raiderCorpseZ[ci] = raiderTargetZ[ci]
                ci += 1
            endwhile
        endif
        return
    endif
    raiderTargetX = new float[count]
    raiderTargetY = new float[count]
    raiderTargetZ = new float[count]
    raiderCorpseX = new float[count]
    raiderCorpseY = new float[count]
    raiderCorpseZ = new float[count]
    raiderAbsentSec = new float[count]
    raiderCleared = new bool[count]
    raiderRescued = new bool[count]
    raiderEngaged = new bool[count]
    raiderArmed = new bool[count]
    raiderStartCombatAt = new float[count]
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
        bool clearAbsentDead = False
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
            elseif r.IsDead()
                ; N2: Never invent doorX-18.0 for an already-dead raider outside Concord on late init (prevents corpse pileups).
                tx = rx
                ty = ry
                tz = rz
                clearAbsentDead = True
            endif
        endif
        raiderTargetX[i] = tx
        raiderTargetY[i] = ty
        raiderTargetZ[i] = tz
        raiderCorpseX[i] = tx
        raiderCorpseY[i] = ty
        raiderCorpseZ[i] = tz
        raiderAbsentSec[i] = 0.0
        raiderCleared[i] = clearAbsentDead
        raiderRescued[i] = False
        raiderEngaged[i] = False
        raiderArmed[i] = False
        raiderStartCombatAt[i] = -999.0
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
    talkActivated = False
    talkStartedAt = 0.0
    talkNearSec = 0.0
    prestonTalkBoxOpen = False
    prestonFallbackActive = False
    prestonTalkReloaded = True
    prestonDialogueMenuOpen = False
    prestonScenePending = False
    prestonSceneMenuOpened = False
    prestonScenePhase1 = False
    prestonPhase1At = 0.0
    prestonSceneChecks = 0
    prestonSceneRestarts = 0
    prestonPostSceneActive = False
    ownPrestonSceneStop = False
    prestonAttemptStartedAt = 0.0
    CancelTimer(3)
    EnsureActorTalkable(Preston)
    RegisterForRemoteEvent(Preston, "OnActivate")
    InitRaiderTracking()
    int st = GetStage()
    if applied > st
        st = applied
    endif
    Trace("reload mission stage=" + st + " relocate_fails=" + relocateFails)
    if st < 200
        EnsurePrestonAlias()
        RegisterForMenuOpenCloseEvent("DialogueMenu")
        RegisterPrestonSceneEvents()
        if st == 20
            CheckConcordRaidersWfc01(Game.GetPlayer(), False)
        endif
        StartTimer(1.0, 1)
    else
        RegisterForMenuOpenCloseEvent("DialogueMenu")
        RegisterPrestonSceneEvents()
        CheckConcordRaidersWfc01(Game.GetPlayer(), False)
    endif
EndEvent

Function AdvanceTo(int n, string by = "Trigger")
{SetStage, then the stage's actions. Apply runs each stage once.}
    if KeeperOnly
        return
    endif
    pendingStage = n
    pendingStageBy = by
    SetStage(n)
    Apply(n, by)
    if pendingStage == n
        pendingStage = -1
    endif
EndFunction

Event OnStageSet(int auiStageID, int auiItemID)
    if KeeperOnly
        return
    endif
    string cause = "other"
    if auiStageID == pendingStage
        cause = pendingStageBy
        pendingStage = -1
    elseif auiStageID == 35 && talkActivated && !prestonUsedFallback
        cause = "info"
    endif
    Apply(auiStageID, cause)
    Scene scn = ResolvePrestonScene()
    if EffectiveStage() == 40 && (scn == None || !scn.IsPlaying())
        AdvanceTo(200, "Trigger")
        CompleteQuest()
        Trace("complete stage=" + EffectiveStage())
    endif
EndEvent

Function Apply(int auiStageID, string by = "other")
    if KeeperOnly || auiStageID <= applied
        return
    endif
    applied = auiStageID
    Trace("stage " + auiStageID + " by=" + by)
    if auiStageID == 10
        min00Given = True
        SetObjectiveDisplayed(10)
        SetObjectiveDisplayed(10, True, True)
        SetActive(True)
    elseif auiStageID == 20
        SetObjectiveCompleted(10)
        SetObjectiveDisplayed(85)
        SetObjectiveDisplayed(85, True, True)
        SetActive(True)
    elseif auiStageID == 30
        Preston.StopCombat()                             ; in game 18 Oct: downed in the fight, he got up and shot the player
        SetObjectiveCompleted(85)
        SetObjectiveDisplayed(86)
        SetObjectiveDisplayed(86, True, True)
        SetActive(True)
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
        ; R1: Follow Fallout4.esm Min00 -> Min01 (First Settlement only). Do NOT auto-start MQ103 here;
        ; MQ103 starts organically via Diamond City gate proximity or Sanctuary handoff after First Settlement.
        Quest sanctuaryQuest = Game.GetFormFromFile(0x000817, "FO4SFMission.esm") as Quest
        if sanctuaryQuest != None && !sanctuaryQuest.IsRunning()
            bool startedSanctuary = sanctuaryQuest.StartNoWait()
            Trace("sanctuary01 start_requested ok=" + startedSanctuary)
            if !sanctuaryQuest.IsRunning()
                StartTimer(5.0, 4)
            endif
        endif
    endif
EndFunction

Function EnsureSanctuaryStarted()
    if KeeperOnly || IsWarfareMode()
        return
    endif
    Quest sanctuaryQuest = Game.GetFormFromFile(0x000817, "FO4SFMission.esm") as Quest
    if sanctuaryQuest == None || sanctuaryQuest.IsRunning() || sanctuaryQuest.IsCompleted()
        CancelTimer(4)
        return
    endif
    bool ok = sanctuaryQuest.StartNoWait()
    sanctuaryStartRetries += 1
    Trace("sanctuary01 start_retry n=" + sanctuaryStartRetries + " ok=" + ok)
    if !sanctuaryQuest.IsRunning() && !sanctuaryQuest.IsCompleted() && sanctuaryStartRetries < 60
        StartTimer(5.0, 4)
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
    if !ShouldUseMessageBox()
        Trace("preston messagebox suppressed reason=glob_off stage=" + stage)
        return
    endif
    if prestonTalkBoxOpen || startMsg == None || IsWarfareMode()
        return
    endif
    ; A2.2: Never show MessageBox if native DialogueMenu is open (never both).
    if prestonDialogueMenuOpen || prestonSceneMenuOpened
        Trace("preston messagebox suppressed reason=dialogue_menu_open stage=" + stage)
        return
    endif
    prestonTalkReloaded = False
    talkSessionId += 1
    int mySession = talkSessionId
    prestonTalkBoxOpen = True
    Message curMsg = startMsg
    Trace("preston talk opened stage=" + stage)
    int steps = 0
    bool doneLoop = False
    while !doneLoop && steps < 16
        steps += 1
        int btn = curMsg.Show()
        if prestonTalkReloaded || mySession != talkSessionId || btn < 0
            doneLoop = True
        else
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
                if btn == 3 && EffectiveStage() == 30
                    talkActivated = True
                    prestonUsedFallback = False
                    AdvanceTo(35, "info")
                    if EffectiveStage() == 40
                        AdvanceTo(200, "Trigger")
                        CompleteQuest()
                        Trace("complete stage=" + EffectiveStage())
                    endif
                endif
                doneLoop = True
            endif
        endif
    endwhile
    if !prestonTalkReloaded && mySession == talkSessionId
        prestonTalkBoxOpen = False
        ; R11 Review Item #1: Clear fallback latch when MessageBox exits without advancing past stage 30 (< 35)
        ; or after reaching completion (>= 200) so Preston is never locked out of subsequent activation.
        int endSt = EffectiveStage()
        if endSt < 35 || endSt >= 200
            prestonFallbackActive = False
        endif
    endif
EndFunction

Function FallbackPrestonToMessageBox(string reason)
    if !ShouldUseMessageBox()
        Trace("preston fallback suppressed reason=glob_off orig=" + reason)
        return
    endif
    ; A2.2: Never open MessageBox if DialogueMenu already opened, fallback already latched, or talk already finished.
    if prestonDialogueMenuOpen || prestonSceneMenuOpened || prestonTalkBoxOpen || prestonFallbackActive || prestonTalkLogged
        prestonScenePending = False
        prestonScenePhase1 = False
        prestonPhase1At = 0.0
        CancelTimer(3)
        Trace("preston fallback suppressed reason=dialogue_active orig=" + reason)
        return
    endif
    prestonScenePending = False
    prestonScenePhase1 = False
    prestonPhase1At = 0.0
    CancelTimer(3)
    ; A2.2 + C1: Latch prestonFallbackActive BEFORE scn.Stop() so any concurrent/late native greeting
    ; firing OnBegin/OnPhaseBegin/OnMenuOpenCloseEvent immediately suppresses itself (never both).
    prestonFallbackActive = True
    Scene scn = ResolvePrestonScene()
    if scn != None && scn.IsPlaying()
        ownPrestonSceneStop = True
        scn.Stop()
    endif
    if prestonDialogueMenuOpen || prestonSceneMenuOpened
        ; R11 Review Item #1: Clear fallback latch when yielding to a late-opened DialogueMenu so it never strands future talks.
        prestonFallbackActive = False
        Trace("preston fallback suppressed reason=late_dialogue_open orig=" + reason)
        return
    endif
    Trace("preston talk fallback=messagebox reason=" + reason)
    Message talkMsg = ResolvePrestonMsg(-1)
    if talkMsg != None
        RunPrestonTalk(EffectiveStage(), talkMsg)
    elseif EffectiveStage() == 30
        prestonUsedFallback = True
        AdvanceTo(40, "fallback")
    endif
EndFunction

Function RestartOrFailPrestonScene(string reason, bool postMode)
    if KeeperOnly || ShouldUseMessageBox()
        return
    endif
    if prestonDialogueMenuOpen || prestonSceneMenuOpened || prestonTalkBoxOpen
        prestonScenePending = False
        prestonScenePhase1 = False
        prestonPhase1At = 0.0
        prestonAttemptStartedAt = 0.0
        CancelTimer(3)
        return
    endif
    int st = EffectiveStage()
    if !postMode && (st != 30 || prestonTalkLogged)
        prestonScenePending = False
        prestonScenePhase1 = False
        prestonPhase1At = 0.0
        prestonAttemptStartedAt = 0.0
        CancelTimer(3)
        return
    endif
    Scene scn = ResolveActivePrestonScene(postMode)
    if scn == None
        int usedRetries = prestonSceneRestarts
        prestonScenePending = False
        prestonScenePhase1 = False
        prestonPhase1At = 0.0
        prestonSceneRestarts = 0
        prestonPostSceneActive = False
        prestonAttemptStartedAt = 0.0
        CancelTimer(3)
        EnsureActorTalkable(Preston)
        Trace("preston talk ERROR scene_failed retries=" + usedRetries + " reason=" + reason + " actor_talkable=true")
        return
    endif
    if prestonSceneRestarts < PrestonMaxSceneRestarts
        prestonSceneRestarts += 1
        prestonScenePending = False
        if postMode
            EnsureKeeperPrestonAlias()
        else
            EnsurePrestonAlias()
        endif
        RegisterPrestonSceneEvents()
        EnsureActorTalkable(Preston)
        if scn.IsPlaying()
            ownPrestonSceneStop = True
            scn.Stop()
        endif
        prestonPostSceneActive = postMode
        prestonScenePending = True
        prestonSceneMenuOpened = False
        prestonScenePhase1 = False
        prestonPhase1At = 0.0
        prestonAttemptStartedAt = Utility.GetCurrentRealTime()
        prestonSceneChecks = 0
        if !postMode
            talkActivated = True
            prestonUsedFallback = False
            talkStartedAt = Utility.GetCurrentRealTime()
        endif
        scn.Start()
        if !scn.IsPlaying()
            scn.ForceStart()
        endif
        Trace("preston talk scene_restart retry=" + prestonSceneRestarts + "/" + PrestonMaxSceneRestarts + " reason=" + reason + " stage=" + st)
        StartTimer(PrestonSceneCheckSeconds, 3)
    else
        int maxUsed = prestonSceneRestarts
        prestonScenePending = False
        if scn.IsPlaying()
            ownPrestonSceneStop = True
            scn.Stop()
        endif
        prestonScenePhase1 = False
        prestonPhase1At = 0.0
        prestonSceneRestarts = 0
        prestonPostSceneActive = False
        prestonAttemptStartedAt = 0.0
        CancelTimer(3)
        EnsureActorTalkable(Preston)
        Trace("preston talk ERROR scene_failed retries=" + maxUsed + " reason=" + reason + " actor_talkable=true")
    endif
EndFunction

Function CheckPrestonSceneOpen()
    if KeeperOnly || !prestonScenePending
        return
    endif
    int st = EffectiveStage()
    bool stageValid = (prestonPostSceneActive && st >= 200) || (!prestonPostSceneActive && st == 30 && !prestonTalkLogged)
    if prestonDialogueMenuOpen || prestonSceneMenuOpened || prestonTalkBoxOpen || prestonFallbackActive || !stageValid
        prestonScenePending = False
        prestonScenePhase1 = False
        prestonPhase1At = 0.0
        prestonAttemptStartedAt = 0.0
        return
    endif
    prestonSceneChecks += 1
    float nowRt = Utility.GetCurrentRealTime()
    if prestonAttemptStartedAt > 0.0 && nowRt < prestonAttemptStartedAt
        prestonAttemptStartedAt = nowRt
    endif
    float attemptElapsed = PrestonSceneCheckSeconds
    if prestonAttemptStartedAt > 0.0
        attemptElapsed = nowRt - prestonAttemptStartedAt
    endif
    bool phase1Elapsed = False
    if prestonScenePhase1
        if nowRt < prestonPhase1At
            prestonPhase1At = nowRt
        elseif (nowRt - prestonPhase1At) >= (PrestonSceneCheckSeconds - 0.05)
            phase1Elapsed = True
        endif
    endif
    Scene scn = ResolveActivePrestonScene(prestonPostSceneActive)
    if scn == None || !scn.IsPlaying()
        if ShouldUseMessageBox()
            FallbackPrestonToMessageBox("scene_inactive")
        elseif attemptElapsed < (PrestonSceneCheckSeconds - 0.05)
            StartTimer(PrestonSceneCheckSeconds - attemptElapsed, 3)
        else
            RestartOrFailPrestonScene("scene_inactive", prestonPostSceneActive)
        endif
    elseif (phase1Elapsed || prestonSceneChecks >= PrestonSceneMaxWaitChecks) && attemptElapsed >= (PrestonSceneCheckSeconds - 0.05)
        prestonScenePending = False
        prestonScenePhase1 = False
        prestonPhase1At = 0.0
        if prestonDialogueMenuOpen || prestonSceneMenuOpened
            return
        endif
        if ShouldUseMessageBox()
            FallbackPrestonToMessageBox("dialogue_menu_timeout")
        else
            RestartOrFailPrestonScene("dialogue_menu_timeout", prestonPostSceneActive)
        endif
    elseif phase1Elapsed || prestonSceneChecks >= PrestonSceneMaxWaitChecks
        StartTimer(PrestonSceneCheckSeconds - attemptElapsed, 3)
    else
        StartTimer(PrestonSceneCheckSeconds, 3)
    endif
EndFunction

Event OnMenuOpenCloseEvent(string asMenuName, bool abOpening)
    if KeeperOnly || asMenuName != "DialogueMenu"
        return
    endif
    prestonDialogueMenuOpen = abOpening
    Scene scn = ResolvePrestonScene()
    Scene postScn = ResolvePrestonPostScene()
    bool primaryPlaying = scn != None && scn.IsPlaying()
    bool postPlaying = postScn != None && postScn.IsPlaying()
    if abOpening
        int st = EffectiveStage()
        if prestonTalkBoxOpen || prestonFallbackActive
            ; A2.2: Suppress any late native greeting scene unconditionally when MessageBox fallback is active.
            if primaryPlaying
                ownPrestonSceneStop = True
                scn.Stop()
                Trace("preston scene suppressed reason=single_talk stage=" + st)
            endif
            if postPlaying
                ownPrestonSceneStop = True
                postScn.Stop()
                Trace("preston scene suppressed reason=single_talk stage=" + st)
            endif
            return
        endif
        if st >= 200
            if primaryPlaying
                ownPrestonSceneStop = True
                scn.Stop()
                Trace("preston scene suppressed reason=single_talk stage=" + st)
            endif
            if prestonPostSceneActive || postPlaying
                prestonPostSceneActive = True
                prestonSceneMenuOpened = True
                prestonScenePending = False
                prestonScenePhase1 = False
                prestonPhase1At = 0.0
                prestonSceneRestarts = 0
                ownPrestonSceneStop = False
                prestonAttemptStartedAt = 0.0
                CancelTimer(3)
                Trace("preston dialogue menu opened mode=post stage=" + st)
            endif
            return
        endif
        if prestonTalkLogged || st >= 35
            if scn != None
                if scn.IsPlaying()
                    ownPrestonSceneStop = True
                endif
                scn.Stop()
                Trace("preston scene suppressed reason=single_talk stage=" + st)
            endif
            return
        endif
        if prestonScenePending || talkActivated || primaryPlaying
            talkActivated = True
            prestonUsedFallback = False
            prestonSceneMenuOpened = True
            prestonScenePending = False
            prestonScenePhase1 = False
            prestonPhase1At = 0.0
            prestonSceneRestarts = 0
            ownPrestonSceneStop = False
            prestonAttemptStartedAt = 0.0
            CancelTimer(3)
            Trace("preston dialogue menu opened")
        endif
    elseif prestonSceneMenuOpened
        prestonSceneMenuOpened = False
        Trace("preston dialogue menu closed stage=" + EffectiveStage())
    endif
EndEvent

Event Scene.OnBegin(Scene akSender)
    if KeeperOnly
        return
    endif
    Scene scn = ResolvePrestonScene()
    Scene postScn = ResolvePrestonPostScene()
    if scn != None && akSender == scn
        ; C1 + A2.2: Never allow a queued/late DEVT scene to run if MessageBox fallback already latched or talk finished.
        if prestonTalkBoxOpen || prestonFallbackActive || prestonTalkLogged || EffectiveStage() >= 35 || ShouldUseMessageBox()
            if akSender.IsPlaying()
                ownPrestonSceneStop = True
            endif
            akSender.Stop()
            Trace("preston scene suppressed reason=single_talk stage=" + EffectiveStage())
            return
        endif
        prestonPostSceneActive = False
        talkActivated = True
        prestonUsedFallback = False
        if talkStartedAt <= 0.0
            talkStartedAt = Utility.GetCurrentRealTime()
        endif
        if EffectiveStage() == 30 && !prestonScenePending && !prestonSceneMenuOpened && !prestonDialogueMenuOpen
            ownPrestonSceneStop = False
            prestonScenePending = True
            prestonScenePhase1 = False
            prestonPhase1At = 0.0
            prestonAttemptStartedAt = Utility.GetCurrentRealTime()
            prestonSceneChecks = 0
            Trace("preston scene talk requested scene=" + scn + " stage=30")
            StartTimer(PrestonSceneCheckSeconds, 3)
        endif
        Trace("preston talk scene started stage=" + EffectiveStage())
    elseif postScn != None && akSender == postScn
        int st = EffectiveStage()
        if prestonTalkBoxOpen || prestonFallbackActive || st < 200 || ShouldUseMessageBox()
            if akSender.IsPlaying()
                ownPrestonSceneStop = True
            endif
            akSender.Stop()
            Trace("preston scene suppressed reason=single_talk stage=" + st)
            return
        endif
        prestonPostSceneActive = True
        if !prestonScenePending && !prestonSceneMenuOpened && !prestonDialogueMenuOpen
            ownPrestonSceneStop = False
            prestonScenePending = True
            prestonScenePhase1 = False
            prestonPhase1At = 0.0
            prestonAttemptStartedAt = Utility.GetCurrentRealTime()
            prestonSceneChecks = 0
            Trace("preston scene talk requested scene=" + postScn + " stage=" + st + " mode=post")
            StartTimer(PrestonSceneCheckSeconds, 3)
        endif
        Trace("preston talk scene started stage=" + st + " mode=post")
    endif
EndEvent

Event Scene.OnPhaseBegin(Scene akSender, int auiPhaseIndex)
    if KeeperOnly
        return
    endif
    Scene scn = ResolvePrestonScene()
    Scene postScn = ResolvePrestonPostScene()
    if scn != None && akSender == scn
        ; A2.2: Immediately stop any late native phase advance if fallback/box already owns the talk (never both).
        if prestonTalkBoxOpen || prestonFallbackActive || prestonTalkLogged || EffectiveStage() >= 35
            if akSender.IsPlaying()
                ownPrestonSceneStop = True
            endif
            akSender.Stop()
            Trace("preston scene suppressed reason=single_talk stage=" + EffectiveStage())
            return
        endif
        Trace("preston talk scene phase=" + auiPhaseIndex + " stage=" + EffectiveStage())
        if auiPhaseIndex >= 1
            prestonScenePhase1 = True
            prestonPhase1At = Utility.GetCurrentRealTime()
            if prestonScenePending && !prestonSceneMenuOpened && !prestonDialogueMenuOpen
                CancelTimer(3)
                StartTimer(PrestonSceneCheckSeconds, 3)
            endif
        endif
    elseif postScn != None && akSender == postScn
        int st = EffectiveStage()
        if prestonTalkBoxOpen || prestonFallbackActive || st < 200 || ShouldUseMessageBox()
            if akSender.IsPlaying()
                ownPrestonSceneStop = True
            endif
            akSender.Stop()
            Trace("preston scene suppressed reason=single_talk stage=" + st)
            return
        endif
        Trace("preston talk scene phase=" + auiPhaseIndex + " stage=" + st + " mode=post")
        if auiPhaseIndex >= 1
            prestonScenePhase1 = True
            prestonPhase1At = Utility.GetCurrentRealTime()
            if prestonScenePending && !prestonSceneMenuOpened && !prestonDialogueMenuOpen
                CancelTimer(3)
                StartTimer(PrestonSceneCheckSeconds, 3)
            endif
        endif
    endif
EndEvent

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    if KeeperOnly
        return
    endif
    if akSender == Preston && akActionRef == Game.GetPlayer()
        if prestonTalkBoxOpen || prestonDialogueMenuOpen || prestonSceneMenuOpened || prestonScenePending
            return
        endif
        ; R11 Review Item #1: Never let stale prestonFallbackActive alone block OnActivate when no box/menu/scene is active.
        if prestonFallbackActive
            prestonFallbackActive = False
        endif
        prestonSceneRestarts = 0
        int stage = EffectiveStage()
        Trace("preston activated at stage " + stage)
        if stage < 20
            FoundPreston("activated")                    ; the next check starts the fight
        elseif stage == 30
            Scene scn = ResolvePrestonSceneLogged()
            ; A2.2: Re-check after ResolvePrestonSceneLogged() so a concurrent native DEVT greeting that already
            ; opened DialogueMenu (observed in 2g run3 at rt=343.486 vs 343.662) is never overwritten or re-armed.
            if prestonTalkBoxOpen || prestonDialogueMenuOpen || prestonSceneMenuOpened || prestonFallbackActive || prestonTalkLogged || EffectiveStage() != 30
                return
            endif
            if ShouldUseMessageBox()
                FallbackPrestonToMessageBox("glob")
            elseif scn != None
                EnsurePrestonAlias()
                RegisterPrestonSceneEvents()
                if prestonTalkBoxOpen || prestonDialogueMenuOpen || prestonSceneMenuOpened || prestonFallbackActive
                    return
                endif
                prestonFallbackActive = False
                prestonPostSceneActive = False
                talkActivated = True
                prestonUsedFallback = False
                talkStartedAt = Utility.GetCurrentRealTime()
                ownPrestonSceneStop = False
                prestonScenePending = True
                prestonSceneMenuOpened = False
                prestonScenePhase1 = False
                prestonPhase1At = 0.0
                prestonAttemptStartedAt = Utility.GetCurrentRealTime()
                prestonSceneChecks = 0
                if !scn.IsPlaying()
                    scn.Start()
                    if !scn.IsPlaying()
                        scn.ForceStart()
                    endif
                endif
                Trace("preston talk scene triggered stage=30")
                Trace("preston scene talk requested scene=" + scn + " stage=30")
                StartTimer(PrestonSceneCheckSeconds, 3)
            else
                RestartOrFailPrestonScene("no_scene", False)
            endif
        elseif stage >= 200
            if ShouldUseMessageBox()
                Message postMsg = ResolvePrestonMsg(-1)
                if postMsg != None
                    RunPrestonTalk(stage, postMsg)
                endif
            else
                Scene postScn = ResolvePrestonPostScene()
                if postScn != None
                    EnsureKeeperPrestonAlias()
                    RegisterPrestonSceneEvents()
                    EnsureActorTalkable(Preston)
                    if prestonTalkBoxOpen || prestonDialogueMenuOpen || prestonSceneMenuOpened || prestonFallbackActive
                        return
                    endif
                    prestonFallbackActive = False
                    prestonPostSceneActive = True
                    ownPrestonSceneStop = False
                    prestonScenePending = True
                    prestonSceneMenuOpened = False
                    prestonScenePhase1 = False
                    prestonPhase1At = 0.0
                    prestonAttemptStartedAt = Utility.GetCurrentRealTime()
                    prestonSceneChecks = 0
                    if !postScn.IsPlaying()
                        postScn.Start()
                        if !postScn.IsPlaying()
                            postScn.ForceStart()
                        endif
                    endif
                    Trace("preston talk scene triggered stage=" + stage + " mode=post")
                    Trace("preston scene talk requested scene=" + postScn + " stage=" + stage + " mode=post")
                    StartTimer(PrestonSceneCheckSeconds, 3)
                else
                    RestartOrFailPrestonScene("no_post_scene", True)
                endif
            endif
        endif
    endif
EndEvent

Event Scene.OnEnd(Scene akSender)
    if KeeperOnly
        return
    endif
    Scene scn = ResolvePrestonScene()
    Scene postScn = ResolvePrestonPostScene()
    if scn != None && akSender == scn
        if ownPrestonSceneStop
            ownPrestonSceneStop = False
            return
        endif
        int st = EffectiveStage()
        bool endInfoDone = GetStageDone(35) || st == 35 || GetStage() == 35
        Trace("preston talk scene ended stage=" + st + " end_info=" + endInfoDone)
        if endInfoDone
            prestonScenePending = False
            prestonSceneMenuOpened = False
            prestonScenePhase1 = False
            prestonPhase1At = 0.0
            prestonAttemptStartedAt = 0.0
            CancelTimer(3)
            if applied < 35
                Apply(35, "info")
            endif
            if EffectiveStage() == 40
                AdvanceTo(200, "Trigger")
                CompleteQuest()
                Trace("complete stage=" + EffectiveStage())
            endif
        elseif st == 30 && !prestonTalkLogged && !prestonFallbackActive
            if prestonScenePending && !prestonSceneMenuOpened
                ; F1: Never count restart OnEnds into talkFailures (prevents stage 40 by=fallback skip),
                ; and count a retry ONLY after a full PrestonSceneCheckSeconds window.
                if ShouldUseMessageBox()
                    FallbackPrestonToMessageBox("scene_incomplete")
                else
                    float nowEnd = Utility.GetCurrentRealTime()
                    if prestonAttemptStartedAt > 0.0 && nowEnd < prestonAttemptStartedAt
                        prestonAttemptStartedAt = nowEnd
                    endif
                    float attElapsed = nowEnd - prestonAttemptStartedAt
                    if prestonAttemptStartedAt > 0.0 && attElapsed < (PrestonSceneCheckSeconds - 0.05)
                        CancelTimer(3)
                        StartTimer(PrestonSceneCheckSeconds - attElapsed, 3)
                    else
                        RestartOrFailPrestonScene("scene_incomplete", False)
                    endif
                endif
            else
                talkFailures += 1
                talkActivated = False
                talkStartedAt = 0.0
                Trace("preston talk retry n=" + talkFailures + " reason=scene_incomplete")
                prestonScenePending = False
                prestonSceneMenuOpened = False
                prestonScenePhase1 = False
                prestonPhase1At = 0.0
                prestonAttemptStartedAt = 0.0
                EnsureActorTalkable(Preston)
            endif
        else
            prestonScenePending = False
            prestonSceneMenuOpened = False
            prestonScenePhase1 = False
            prestonPhase1At = 0.0
            prestonAttemptStartedAt = 0.0
        endif
    elseif postScn != None && akSender == postScn
        if ownPrestonSceneStop
            ownPrestonSceneStop = False
            return
        endif
        int st = EffectiveStage()
        Trace("preston talk scene ended stage=" + st + " mode=post")
        if st >= 200 && prestonScenePending && !prestonSceneMenuOpened && !prestonFallbackActive && !ShouldUseMessageBox()
            float nowPost = Utility.GetCurrentRealTime()
            if prestonAttemptStartedAt > 0.0 && nowPost < prestonAttemptStartedAt
                prestonAttemptStartedAt = nowPost
            endif
            float postElapsed = nowPost - prestonAttemptStartedAt
            if prestonAttemptStartedAt > 0.0 && postElapsed < (PrestonSceneCheckSeconds - 0.05)
                CancelTimer(3)
                StartTimer(PrestonSceneCheckSeconds - postElapsed, 3)
            else
                RestartOrFailPrestonScene("scene_incomplete", True)
            endif
        else
            prestonScenePending = False
            prestonSceneMenuOpened = False
            prestonScenePhase1 = False
            prestonPhase1At = 0.0
            prestonAttemptStartedAt = 0.0
            prestonPostSceneActive = False
            CancelTimer(3)
            EnsureActorTalkable(Preston)
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
    if talkFailures >= 3
        return MarkPrestonFallback("preston talk fallback tries=" + talkFailures)
    endif
    float nowRt = Utility.GetCurrentRealTime()
    if talkStartedAt > 0.0 && nowRt < talkStartedAt
        talkStartedAt = nowRt
    endif
    Scene scn = ResolvePrestonScene()
    if scn != None && scn.IsPlaying()
        talkNearSec = 0.0
        if talkStartedAt > 0.0 && (nowRt - talkStartedAt) > TalkSceneTimeout
            talkFailures += 1
            ownPrestonSceneStop = True
            scn.Stop()
            talkActivated = False
            talkStartedAt = 0.0
            Trace("preston talk retry n=" + talkFailures + " reason=timeout")
            if talkFailures >= 3
                return MarkPrestonFallback("preston talk timeout")
            endif
        endif
        return False
    endif
    if talkActivated && talkStartedAt > 0.0 && (nowRt - talkStartedAt) >= 15.0
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
            if scn == None
                return MarkPrestonFallback("preston talk fallback no_scene")
            endif
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

Function ArmRaiderForCombat(Actor r, int idx)
{C3 + R11 D3: Ensure each Concord raider is unrestrained, aggressive, brave, carries Coachman + deterministic
 AmmoShotshell=60 (removing LL_Ammo_Shotshell random 10..30 spawn variance that produced 30, 70, 30, 30, 20 in 2g),
 and re-evaluates its combat package.}
    if r == None || r.IsDead()
        return
    endif
    r.SetRestrained(False)
    ActorValue aggrAv = Game.GetAggressionAV()
    if aggrAv != None
        r.SetValue(aggrAv, 2.0)
    endif
    ActorValue confAv = Game.GetConfidenceAV()
    if confAv != None
        r.SetValue(confAv, 4.0)
    endif
    int targetShells = 60
    if RaiderAmmo != None
        int curShells = r.GetItemCount(RaiderAmmo)
        if curShells < targetShells
            r.AddItem(RaiderAmmo, targetShells - curShells, True)
        elseif curShells > targetShells
            r.RemoveItem(RaiderAmmo, curShells - targetShells, True)
        endif
    endif
    if RaiderWeapon != None
        if r.GetItemCount(RaiderWeapon) < 1
            r.AddItem(RaiderWeapon, 1, True)
        endif
        r.EquipItem(RaiderWeapon, False, True)
    endif
    r.EvaluatePackage()
    raiderArmed[idx] = True
    int shells = 0
    if RaiderAmmo != None
        shells = r.GetItemCount(RaiderAmmo)
    endif
    Trace("arm raider " + idx + " ammo=" + shells)
EndFunction

Function EquipBalancedRaiderSidearm(Actor r, int idx)
{R11 Part 3 E3: Switch armed Concord street raiders from Coachman (52 dmg) to VMAD-bound FO4SF_ConcordRaiderSidearm
 (WEAP 0x097A, 3 dmg, AmmoList cleared) + deterministic 36 Ammo777mm (0x04AD3E). Adds & equips RaiderSidearm and
 removes Coachman + AmmoShotshell FIRST, then clamps RaiderSidearmAmmo to exact 36 so engine weapon-ammo spawns
 never push sidearm_ammo above 36.}
    if r == None || r.IsDead() || RaiderSidearm == None || RaiderSidearmAmmo == None
        return
    endif
    if r.GetItemCount(RaiderSidearm) < 1
        r.AddItem(RaiderSidearm, 1, True)
    endif
    if RaiderWeapon != None
        r.UnequipItem(RaiderWeapon, False, True)
        int curCoachman = r.GetItemCount(RaiderWeapon)
        if curCoachman > 0
            r.RemoveItem(RaiderWeapon, curCoachman, True)
        endif
    endif
    if RaiderAmmo != None
        int curShells = r.GetItemCount(RaiderAmmo)
        if curShells > 0
            r.RemoveItem(RaiderAmmo, curShells, True)
        endif
    endif
    r.EquipItem(RaiderSidearm, True, True)
    int targetSidearmAmmo = 36
    int curSidearmAmmo = r.GetItemCount(RaiderSidearmAmmo)
    if curSidearmAmmo < targetSidearmAmmo
        r.AddItem(RaiderSidearmAmmo, targetSidearmAmmo - curSidearmAmmo, True)
    elseif curSidearmAmmo > targetSidearmAmmo
        r.RemoveItem(RaiderSidearmAmmo, curSidearmAmmo - targetSidearmAmmo, True)
    endif
    r.EvaluatePackage()
    Trace("arm raider " + idx + " sidearm=eon sidearm_ammo=" + r.GetItemCount(RaiderSidearmAmmo) + " dmg=" + RaiderSidearmDamage + " playable=false standin=true")
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
{WFC-01 anti-stall & R11 Part 3 E5: rescues living raiders AND non-cleared dead raiders that fell below terrain
 (z < targetZ - 8 m), drifted far (> 140 m from their Concord street/corpse spot, e.g. 2.9 km away after reload),
 or loaded into another world while the player is within 150 m of the museum door; and writes off (stops combat +
 disables) any living raider that remains absent/unloaded (> 250 m or !Is3DLoaded) for > 60 s within 100 m of the
 Concord door or stays loaded within 2 m with no damage for 60 s after a rescue.}
    if player == None || player.IsInInterior() || !IsCommonwealthExterior(player)
        return
    endif
    InitRaiderTracking()
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float pz = player.GetPositionZ()
    WorldSpace pws = player.GetWorldSpace()
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
        if r == None || raiderCleared[i] || r.IsDisabled()
            raiderAbsentSec[i] = 0.0
            raiderRescueSec[i] = 0.0
        else
            bool deadRaider = r.IsDead()
            float tx = raiderTargetX[i]
            float ty = raiderTargetY[i]
            float tz = raiderTargetZ[i]
            float cx = tx
            float cy = ty
            float cz = tz
            if deadRaider
                raiderAbsentSec[i] = 0.0
                raiderRescueSec[i] = 0.0
                cx = raiderCorpseX[i]
                cy = raiderCorpseY[i]
                cz = raiderCorpseZ[i]
            endif
            if doorDist < Wfc01CheckRadius
                float rz = r.GetPositionZ()
                float drift = SpotOff(r, cx, cy, cz)
                WorldSpace rws = r.GetWorldSpace()
                bool wrongWorld = r.IsInInterior() || rws == None || rws != pws
                if !wrongWorld && rz >= tz - Wfc01SubterraneanDrop && SpotOff(r, tx, ty, tz) <= Wfc01MaxDrift
                    raiderCorpseX[i] = r.GetPositionX()
                    raiderCorpseY[i] = r.GetPositionY()
                    raiderCorpseZ[i] = rz
                elseif (wrongWorld || rz < cz - Wfc01SubterraneanDrop || drift > Wfc01MaxDrift) && IsPlayerStableAt(player, px, py, pz)
                    r.MoveTo(player, cx - px, cy - py, cz - pz, True, False)
                    r.SetPosition(cx, cy, cz)
                    if deadRaider
                        Trace("wfc01 rescue_dead raider=" + i + " z=" + rz + " target_z=" + cz + " drift=" + drift)
                    else
                        r.EvaluatePackage()
                        raiderRescued[i] = True
                        raiderRescueSec[i] = 0.0
                        raiderRescueX[i] = r.GetPositionX()
                        raiderRescueY[i] = r.GetPositionY()
                        raiderRescueZ[i] = r.GetPositionZ()
                        raiderRescueHp[i] = GetRaiderHealth(r)
                        Trace("wfc01 rescue raider=" + i + " z=" + rz + " target_z=" + cz + " drift=" + drift)
                    endif
                endif
            endif
            if !deadRaider && advanceClock
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
    elseif aiTimerID == 4
        EnsureSanctuaryStarted()
        return
    elseif aiTimerID != 1
        return
    endif
    if KeeperOnly
        return
    endif
    if EffectiveStage() < 200
        if !IsRunning()
            Start()
        endif
        if applied > 0 && GetStage() < applied
            SetStage(applied)
        endif
    endif
    Actor player = Game.GetPlayer()
    InitRaiderTracking()
    KeepCodsworthStart()
    ReleaseInFight("mission")                            ; every check, whatever the budget or where the player is
    if relocateFails < 10
        Relocate(player)
    endif
    int rawStage = GetStage()
    int stage = EffectiveStage()
    if !min00Given && stage < 10 && IsCommonwealthExterior(player)
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
    if (GetStageDone(35) || rawStage == 35) && applied < 35
        if talkActivated && !prestonUsedFallback
            Apply(35, "info")
        else
            Apply(35, "other")
        endif
        stage = EffectiveStage()
    endif
    if rawStage >= 40 && applied < 40
        Apply(40, "other")
        stage = EffectiveStage()
    elseif rawStage > applied && rawStage < 35
        Apply(rawStage, "other")
        stage = EffectiveStage()
    endif
    if stage == 10 && min00Given && !IsObjectiveDisplayed(10)
        EnsurePrestonAlias()
        SetObjectiveDisplayed(10)
        SetObjectiveDisplayed(10, True, True)
        SetActive(True)
    elseif stage == 20 && !IsObjectiveDisplayed(85)
        SetObjectiveDisplayed(85)
        SetObjectiveDisplayed(85, True, True)
    elseif stage == 30 && !IsObjectiveDisplayed(86)
        EnsurePrestonAlias()
        SetObjectiveDisplayed(86)
        SetObjectiveDisplayed(86, True, True)
    endif
    float dp = player.GetDistance(Preston)
    if stage < 20 && dp < FindRadius
        FoundPreston("near d=" + dp)
    endif
    if stage == 20
        CheckConcordRaidersWfc01(player, True)
    else
        CheckConcordRaidersWfc01(player, False)
    endif
    bool everyone = prestonFound || stage >= 20          ; once the fight is on, no raider stands by
    int dead = 0
    bool fighting = false
    float nearest = -1.0
    float nowCombatRt = Utility.GetCurrentRealTime()
    int i = 0
    while i < Raiders.Length
        Actor r = Raiders[i]
        if r == None || r.IsDead() || raiderCleared[i]
            dead += 1
        else
            float d = player.GetDistance(r)
            if nearest < 0.0 || d < nearest
                nearest = d
            endif
            if !raiderArmed[i] && stage < 30 && (everyone || d < EngageRadius) && r.Is3DLoaded()
                ArmRaiderForCombat(r, i)
                EquipBalancedRaiderSidearm(r, i)
            endif
            if (r.GetCombatState() == 1 && raiderEngaged[i]) || (raiderEngaged[i] && nowCombatRt >= raiderStartCombatAt[i] && (nowCombatRt - raiderStartCombatAt[i]) < 10.0)
                fighting = true
            elseif stage < 30 && (everyone || d < EngageRadius) && r.Is3DLoaded()
                ; FO4's forced fight: every living loaded raider is put into combat with the player, even if
                ; faction-alerted (GetCombatState == 2), rate-limited to once per 10 s after initial engage (C3).
                r.StartCombat(player)
                raiderEngaged[i] = True
                raiderStartCombatAt[i] = nowCombatRt
                fighting = true
                Trace("startcombat raider " + i + " d=" + d)
            elseif r.GetCombatState() != 0
                fighting = true
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
    Scene endScn = ResolvePrestonScene()
    if EffectiveStage() == 40 && (endScn == None || !endScn.IsPlaying()) ; in game 18 Oct the status stayed at 40 after the reward: set 200
        AdvanceTo(200, "Trigger")
        CompleteQuest()
        Trace("complete stage=" + EffectiveStage())
    endif
    if EffectiveStage() < 200                            ; stage 200 cancels the timer (Apply)
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

bool Function IsStoryQuestComplete(int formId)
{R5: Strict IsCompleted() check only. Never treat intermediate stage >= 100 (e.g. MQ105@100 following trail to
 Fort Hagen, MQ106@100 Kellogg, MQ203@100 lounger) as completed.}
    Quest q = Game.GetFormFromFile(formId, "FO4SFMission.esm") as Quest
    return q != None && q.IsCompleted()
EndFunction

Function CheckPostConcordSanctuaryHandoff()
    if IsWarfareMode()
        return
    endif
    if !IsRunning() && KeeperOnly
        Start()
    endif
    bool min00Done = applied >= 200 || IsCompleted()
    if KeeperOnly
        Quest min00 = Game.GetFormFromFile(0x000800, "FO4SFMission.esm") as Quest
        min00Done = min00 != None && min00.IsCompleted()
    endif
    if min00Done
        Quest sanctuaryQuest = Game.GetFormFromFile(0x000817, "FO4SFMission.esm") as Quest
        if sanctuaryQuest != None && !sanctuaryQuest.IsRunning() && !sanctuaryQuest.IsCompleted()
            bool ok = sanctuaryQuest.StartNoWait()
            Trace("sanctuary01 postload_start ok=" + ok)
        endif
    endif
EndFunction

Function Relocate(Actor player)
{Moves the raiders (Codsworth: KeepCodsworth) from their unmerged local position to the same spot in the merged world the
 player walks in, and puts Preston at his fixed spot (PlacePreston). Never from an interior.}
    if player.IsInInterior()
        return
    endif
    if !IsCommonwealthExterior(player)
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
        if !IsPlayerStableAt(player, px, py, pz)
            return
        endif
        if MoveOver(Raiders[i], player, px, py, pz, "raider " + i)
            relocateFails += 1
        endif
        i += 1
    endwhile
EndFunction

Function KeepCodsworth()
{Codsworth has his own check every CodsworthCheck seconds with its own budget of 10 failed moves. It keeps running after
 stage 200, which ends the mission's timer.}
    CheckPostConcordSanctuaryHandoff()
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
        CheckA4ProximityStarts(player)
        CheckA7ProximityStarts(player)
        CheckA7cdProximityStarts(player)
    endif
    if (Codsworth != None && (codsworthFails < 10 || codsworthHolds > 0)) || (KeeperOnly && (prestonFails < 10 || prestonHolds > 0))
        StartTimer(CodsworthCheck, 2)
    elseif KeeperOnly
        ; R11 A2.4: Keep KeeperOnly Timer 2 alive for CheckA4/A7/A7cdProximityStarts even if both
        ; Codsworth and Preston placement budgets reach 10 with zero holds.
        StartTimer(CodsworthCheck, 2)
    endif
EndFunction

Function CheckA4ProximityStarts(Actor player)
{R1/R5: Console-free proximity discovery for JOTC-02 Diamond City gate (MQ103) & Tenpines Bluff (MinRecruit00) on
 KeeperOnly Timer 2, strictly gated behind BOTH FO4SF_Min00 (0x000800) AND FO4SF_Sanctuary01 (0x000817) completion so
 First Settlement stays the sole active tracked opening mission (deliberate one-tracked-mission rule aligned with W2).}
    if !IsCommonwealthExterior(player) || IsWarfareMode()
        return
    endif
    if !IsStoryQuestComplete(0x000800) || !IsStoryQuestComplete(0x000817)
        return
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float r2 = 150.0 * 150.0
    float dcx = px - (-1416.36)
    float dcy = py - (-3129.39)
    if !mq103ProxAttempted && dcx * dcx + dcy * dcy <= r2
        Quest mq103Quest = Game.GetFormFromFile(0x000A50, "FO4SFMission.esm") as Quest
        if mq103Quest != None && !mq103Quest.IsRunning() && !mq103Quest.IsCompleted()
            mq103ProxAttempted = True
            mq103Quest.StartNoWait()
            Trace("mq103 started by=proximity")
        endif
    endif
    float tpx = px - (-1517.0)
    float tpy = py - (-1423.63)
    if !minRecruitProxAttempted && tpx * tpx + tpy * tpy <= r2
        Quest stepQuest = Game.GetFormFromFile(0x000A20, "FO4SFMission.esm") as Quest
        if stepQuest != None && !stepQuest.IsRunning() && !stepQuest.IsCompleted()
            minRecruitProxAttempted = True
            stepQuest.StartNoWait()
            Trace("minrecruit00 started by=proximity")
        endif
    endif
EndFunction

Function CheckA7ProximityStarts(Actor player)
{R5: Console-free proximity discovery for Park Street / Vault 114 (MQ104) & Fort Hagen (MQ105) on KeeperOnly Timer 2,
 strictly gated behind prior quest completion (MQ103 -> MQ104 -> MQ105) so no post-opening quest fires early.}
    if !IsCommonwealthExterior(player) || IsWarfareMode()
        return
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float r2 = 150.0 * 150.0
    float psx = px - (-987.46)
    float psy = py - (-2927.73)
    float v14x = px - (-1085.43)
    float v14y = py - (-2958.22)
    if !mq104ProxAttempted && IsStoryQuestComplete(0x000A50) && ((psx * psx + psy * psy <= r2) || (v14x * v14x + v14y * v14y <= r2))
        Quest mq104Quest = Game.GetFormFromFile(0x000A80, "FO4SFMission.esm") as Quest
        if mq104Quest != None && !mq104Quest.IsRunning() && !mq104Quest.IsCompleted()
            mq104ProxAttempted = True
            mq104Quest.StartNoWait()
            Trace("mq104 started by=proximity")
        endif
    endif
    float fhx = px - (-2456.84)
    float fhy = py - (-2781.07)
    if !mq105ProxAttempted && IsStoryQuestComplete(0x000A80) && fhx * fhx + fhy * fhy <= r2
        Quest mq105Quest = Game.GetFormFromFile(0x000AB0, "FO4SFMission.esm") as Quest
        if mq105Quest != None && !mq105Quest.IsRunning() && !mq105Quest.IsCompleted()
            mq105ProxAttempted = True
            mq105Quest.StartNoWait()
            Trace("mq105 started by=proximity")
        endif
    endif
EndFunction

Function CheckA7cdProximityStarts(Actor player)
{R5: Console-free proximity discovery for Act II missions (MQ106 Fort Hagen, MQ203 Goodneighbor, MQ204 Glowing Sea,
 MQ206 Greenetech/Railroad) on KeeperOnly Timer 2, each strictly gated behind the prior quest's completion so Fort Hagen
 never starts MQ105 and MQ106 together.}
    if IsWarfareMode() || !IsCommonwealthExterior(player)
        return
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float r2 = 160.0 * 160.0
    float fhx = px - (-2456.84)
    float fhy = py - (-2781.07)
    if !mq106ProxAttempted && IsStoryQuestComplete(0x000AB0) && fhx * fhx + fhy * fhy <= r2
        Quest mq106Quest = Game.GetFormFromFile(0x000AD0, "FO4SFMission.esm") as Quest
        if mq106Quest != None && !mq106Quest.IsRunning() && !mq106Quest.IsCompleted()
            mq106ProxAttempted = True
            mq106Quest.StartNoWait()
            Trace("mq106 started by=proximity")
        endif
    endif
    float gnx = px - (-902.48)
    float gny = py - (-2870.07)
    if !mq203ProxAttempted && IsStoryQuestComplete(0x000AD0) && gnx * gnx + gny * gny <= r2
        Quest mq203Quest = Game.GetFormFromFile(0x000AF0, "FO4SFMission.esm") as Quest
        if mq203Quest != None && !mq203Quest.IsRunning() && !mq203Quest.IsCompleted()
            mq203ProxAttempted = True
            mq203Quest.StartNoWait()
            Trace("mq203 started by=proximity")
        endif
    endif
    float crx = px - (-2624.44)
    float cry = py - (-4357.85)
    float rcx = px - (-2862.82)
    float rcy = py - (-4653.27)
    if !mq204ProxAttempted && IsStoryQuestComplete(0x000AF0) && ((crx * crx + cry * cry <= r2) || (rcx * rcx + rcy * rcy <= r2))
        Quest mq204Quest = Game.GetFormFromFile(0x000B10, "FO4SFMission.esm") as Quest
        if mq204Quest != None && !mq204Quest.IsRunning() && !mq204Quest.IsCompleted()
            mq204ProxAttempted = True
            mq204Quest.StartNoWait()
            Trace("mq204 started by=proximity")
        endif
    endif
    float gtx = px - (-1238.10)
    float gty = py - (-2687.39)
    float rrx = px - (-734.83)
    float rry = py - (-2696.65)
    if !mq206ProxAttempted && IsStoryQuestComplete(0x000B10) && ((gtx * gtx + gty * gty <= r2) || (rrx * rrx + rry * rry <= r2))
        Quest mq206Quest = Game.GetFormFromFile(0x000B30, "FO4SFMission.esm") as Quest
        if mq206Quest != None && !mq206Quest.IsRunning() && !mq206Quest.IsCompleted()
            mq206ProxAttempted = True
            mq206Quest.StartNoWait()
            Trace("mq206 started by=proximity")
        endif
    endif
EndFunction

Function KeepPreston(Actor player)
{The keeper keeps Preston at his merged spot after the mission too, and preserves dead Concord raiders after reload (E5).}
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
    if s == "placed" || s == "at spot"
        prestonPlaced = True
    endif
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
    if !IsCommonwealthExterior(player)
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
    if !IsPlayerStableAt(player, px, py, pz)
        return "off, player inside"
    endif
    Trace("world " + name + " player=" + player.GetWorldSpace() + " actor=" + a.GetWorldSpace() + " cell=" + a.GetParentCell())
    a.MoveTo(player, tx - px, ty - py, tz - pz, True, False)
    float d = player.GetDistance(a)
    float after = SpotOff(a, tx, ty, tz)
    bool failed = after > HoldRadius || d >= RelocateGap || a.IsInInterior() || a.GetWorldSpace() == None
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
        if a == Preston && !KeeperOnly
            a.IgnoreFriendlyHits(True)
        endif
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
{C3: Moves one raider into the player's loaded Commonwealth worldspace when the player is within PlaceRadius (300 m) of
 its merged Concord spot and it is still farther than RelocateGap. Supports both merged-authored raider ACHRs (C3) and
 legacy unmerged saves without ever offsetting twice or dropping raiders into unloaded cells 500 m away.}
    if a == None
        return False
    endif
    float before = player.GetDistance(a)                  ; float max: another world; finite: this world (the world proof)
    if before < RelocateGap
        return False                                      ; already where the player is
    endif
    float doorX = PrestonLocalX + MergeOffsetX
    float doorY = PrestonLocalY + MergeOffsetY
    float rx = a.GetPositionX()
    float ry = a.GetPositionY()
    float z = a.GetPositionZ()
    float x = rx
    float y = ry
    float mx = rx - doorX
    float my = ry - doorY
    if mx * mx + my * my > RelocateRadius * RelocateRadius
        x = rx + MergeOffsetX
        y = ry + MergeOffsetY
        float hx = x - (PrestonLocalX + MergeOffsetX)
        float hy = y - (PrestonLocalY + MergeOffsetY)
        if hx * hx + hy * hy > RelocateRadius * RelocateRadius
            return False                                  ; moved already or outside Concord: never offset twice
        endif
    endif
    float dx = px - x
    float dy = py - y
    if dx * dx + dy * dy > PlaceRadius * PlaceRadius
        return False                                      ; wait until Concord cells are loaded (<= 300 m)
    endif
    WorldSpace wa = a.GetWorldSpace()                     ; evidence for Codex's world-identity point (#353): which
    WorldSpace wp = player.GetWorldSpace()                ; world each side is in before a move (only moves: Codex 4331303552)
    if wp == None || !IsPlayerStableAt(player, px, py, pz)
        return False
    endif
    Trace("world " + what + " player=" + wp + " actor=" + wa + " cell=" + a.GetParentCell())
    a.MoveTo(player, x - px, y - py, z - pz, True, False)
    float d = player.GetDistance(a)
    WorldSpace afterWs = a.GetWorldSpace()
    bool failed = d >= RelocateGap || a.IsInInterior() || afterWs == None || SpotOff(a, x, y, z) > HoldRadius
    Trace("world " + what + " after=" + afterWs + " cell=" + a.GetParentCell())
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
