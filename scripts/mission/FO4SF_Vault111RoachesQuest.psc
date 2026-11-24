Scriptname FO4SF_Vault111RoachesQuest extends Quest
{S2 Vault 111 stage-gated LvlRadRoachAmbush controller (FO4SFMission.esm 0xB90, gated behind --r11-full-mission 1).
Does NOT touch FO4SF_NewGameQuest.psc: monitors FO4SFNewGame (0x000800) stages (20..199) in FO4Port_Vault111Cryo
(FO4Port.esm:0x0011F3), gates spawn on Task 1b Vault 111 death recovery readiness, places 3-5 FO4 LvlRadRoachAmbush
markers relative to anchor 0x01001338, and supports creature_slot=empty fallback when FO4SF_RA5Creatures.esm is absent.}

ObjectReference[] Property RadroachMarkers Auto Const
GlobalVariable Property CreatureSlotReadyGlob Auto Const
GlobalVariable Property Task1bRecoveryReadyGlob Auto Const
bool Property RequireTask1bVaultRecovery = True Auto Const
bool Property RequirePlayerInCryoCell = True Auto Const
string Property NewGamePlugin = "FO4SFNewGame.esm" Auto Const
int Property NewGameQuestId = 0x000800 Auto Const
string Property PortPlugin = "FO4Port.esm" Auto Const
int Property VaultCryoCellId = 0x0011F3 Auto Const
int Property VaultAnchorId = 0x001338 Auto Const
string Property CoreValuesPlugin = "FO4SFCoreValues.esm" Auto Const
int Property GameModeGlobId = 0x000870 Auto Const
string Property CreaturePlugin = "FO4SF_RA5Creatures.esm" Auto Const
int Property CreatureRadroachNpcId = 0x000804 Auto Const
float Property VaultAnchorX = 1.531505 Auto Const
float Property VaultAnchorY = -7.385632 Auto Const
float Property VaultAnchorZ = -0.738497 Auto Const
float Property TriggerRadius = 12.0 Auto Const

; Verified FO4 Vault111Cryo (0x000016D8) LvlRadRoachAmbush (0x000544CB) coords / 70.0:
; [0]=0009F3F1, [1]=00091FBD, [2]=000AC68D, [3]=000AC68E, [4]=000AC68C
float[] roachX
float[] roachY
float[] roachZ
int[] roachStageReq
Actor[] spawnedRoaches
bool[] wavePlaced
bool[] markerSynced

string LogName = "fo4sf_mission"
int TIMER_POLL = 1
bool startedOnce = False
bool blockedLogged = False
bool emptyLogged = False
bool completed = False
int deadCount = 0

Event OnInit()
    InitArrays()
    EnsureStarted("init")
EndEvent

Event OnQuestInit()
    InitArrays()
    EnsureStarted("quest_init")
EndEvent

Event OnQuestStarted()
    InitArrays()
    EnsureStarted("quest_started")
EndEvent

Function InitArrays()
    if roachX != None && roachX.Length == 5
        return
    endif
    roachX = new float[5]
    roachY = new float[5]
    roachZ = new float[5]
    roachStageReq = new int[5]
    spawnedRoaches = new Actor[5]
    wavePlaced = new bool[5]
    markerSynced = new bool[5]

    roachX[0] = -16.591
    roachY[0] = 16.036
    roachZ[0] = -1.779
    roachStageReq[0] = 10

    roachX[1] = -32.753
    roachY[1] = 12.903
    roachZ[1] = 0.0
    roachStageReq[1] = 20

    roachX[2] = -37.120
    roachY[2] = 15.483
    roachZ[2] = 0.0
    roachStageReq[2] = 30

    roachX[3] = -37.373
    roachY[3] = 13.582
    roachZ[3] = 0.0
    roachStageReq[3] = 30

    roachX[4] = -39.628
    roachY[4] = 13.815
    roachZ[4] = 0.0
    roachStageReq[4] = 40
EndFunction

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction

bool Function IsWarfareMode()
    GlobalVariable gm = Game.GetFormFromFile(GameModeGlobId, CoreValuesPlugin) as GlobalVariable
    return gm != None && gm.GetValue() == 2.0
EndFunction

bool Function IsTask1bRecoveryReady()
    if !RequireTask1bVaultRecovery
        return True
    endif
    if Task1bRecoveryReadyGlob != None && Task1bRecoveryReadyGlob.GetValue() != 0.0
        return True
    endif
    return False
EndFunction

bool Function IsPlayerInCryoCell(Actor player)
    if !RequirePlayerInCryoCell
        return True
    endif
    if player == None || !player.IsInInterior()
        return False
    endif
    Cell cryo = Game.GetFormFromFile(VaultCryoCellId, PortPlugin) as Cell
    return cryo != None && player.GetParentCell() == cryo
EndFunction

Function EnsureStarted(string why)
    if startedOnce
        return
    endif
    startedOnce = True
    if IsWarfareMode()
        Trace("s2 vault_roaches skipped reason=warfare_mode")
        Stop()
        return
    endif
    Trace("s2 vault_roaches init why=" + why + " markers=" + RadroachMarkers.Length)
    StartTimer(1.0, TIMER_POLL)
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID != TIMER_POLL || completed
        return
    endif
    EvaluateVaultRoaches()
    if !completed
        StartTimer(1.0, TIMER_POLL)
    endif
EndEvent

bool Function EvaluateVaultRoaches()
    InitArrays()
    if completed || IsWarfareMode()
        return False
    endif
    Actor player = Game.GetPlayer()
    if player == None
        return False
    endif
    Quest ng = Game.GetFormFromFile(NewGameQuestId, NewGamePlugin) as Quest
    int ngStage = 0
    if ng != None
        ngStage = ng.GetStage()
    endif
    if RequirePlayerInCryoCell && (ngStage < 20 || ngStage >= 200)
        if ngStage >= 200
            completed = True
            SetStage(100)
            CompleteQuest()
            Trace("s2 vault_roaches stopped reason=left_vault_stage_200")
        endif
        return False
    endif
    if !IsPlayerInCryoCell(player)
        return False
    endif
    if !IsTask1bRecoveryReady()
        if !blockedLogged
            blockedLogged = True
            Trace("s2 vault_roaches gated reason=task1b_vault_death_recovery_not_ready")
        endif
        return False
    endif

    if GetStage() < 10
        SetStage(10)
        SetObjectiveDisplayed(10, True, True)
        Trace("s2 vault_roaches stage 10 armed")
    endif

    ObjectReference anchor = None
    if RequirePlayerInCryoCell
        anchor = Game.GetFormFromFile(VaultAnchorId, PortPlugin) as ObjectReference
    endif

    ActorBase roachBase = None
    if CreatureSlotReadyGlob != None && CreatureSlotReadyGlob.GetValue() != 0.0
        roachBase = Game.GetFormFromFile(CreatureRadroachNpcId, CreaturePlugin) as ActorBase
    endif
    bool emptySlot = (roachBase == None)
    if emptySlot && !emptyLogged
        emptyLogged = True
        Trace("s2 vault_roaches creature_slot=empty fallback=stage_gate")
    endif

    int totalMarkers = 0
    if RadroachMarkers != None
        totalMarkers = RadroachMarkers.Length
    endif
    if totalMarkers > 5
        totalMarkers = 5
    endif

    int curStage = GetStage()
    if curStage < 10
        curStage = 10
    endif

    int idx = 0
    while idx < totalMarkers
        ObjectReference mk = RadroachMarkers[idx]
        if mk != None
            if anchor != None && !markerSynced[idx]
                mk.MoveTo(anchor, roachX[idx] - VaultAnchorX, roachY[idx] - VaultAnchorY, roachZ[idx] - VaultAnchorZ, False, False)
                mk.EnableNoWait(False)
                markerSynced[idx] = True
            endif
            float dx = player.GetPositionX() - roachX[idx]
            float dy = player.GetPositionY() - roachY[idx]
            bool inRange = (dx * dx + dy * dy <= TriggerRadius * TriggerRadius)
            if !wavePlaced[idx] && (curStage >= roachStageReq[idx] || inRange)
                wavePlaced[idx] = True
                if curStage < roachStageReq[idx]
                    curStage = roachStageReq[idx]
                    SetStage(curStage)
                endif
                if !emptySlot
                    Actor r = mk.PlaceActorAtMe(roachBase, 0, None, True, False, False)
                    spawnedRoaches[idx] = r
                    if r != None
                        r.StartCombat(player)
                    endif
                    Trace("s2 vault_roaches spawn idx=" + idx + " stage=" + curStage)
                else
                    Trace("s2 vault_roaches stage_gate idx=" + idx + " creature_slot=empty stage=" + curStage)
                endif
            endif
        endif
        idx += 1
    endwhile

    if emptySlot
        if curStage >= 40
            completed = True
            SetStage(100)
            SetObjectiveCompleted(10)
            CompleteQuest()
            Trace("s2 vault_roaches complete creature_slot=empty stage=100")
        endif
        return True
    endif

    int deadNow = 0
    int si = 0
    while si < totalMarkers
        Actor sr = spawnedRoaches[si]
        if wavePlaced[si] && (sr == None || sr.IsDead())
            deadNow += 1
        endif
        si += 1
    endwhile
    if deadNow != deadCount
        deadCount = deadNow
        Trace("s2 vault_roaches progress dead=" + deadCount + "/" + totalMarkers)
    endif
    if totalMarkers > 0 && deadCount >= totalMarkers
        completed = True
        SetStage(100)
        SetObjectiveCompleted(10)
        CompleteQuest()
        Trace("s2 vault_roaches complete dead=" + deadCount + "/" + totalMarkers + " stage=100")
    endif
    return True
EndFunction
