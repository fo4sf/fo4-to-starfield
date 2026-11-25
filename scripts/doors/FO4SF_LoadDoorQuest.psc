Scriptname FO4SF_LoadDoorQuest extends Quest
{StartGameEnabled load-door controller quest for FO4SF_ConfirmedLoadDoor (P1 v2 cold-reload fix).

Why a Quest owns the active MoveTo + StartTimer loop:
  When saving inside an interior cell, quitting, relaunching, and activating an exterior-bound
  ("out") load door, an ObjectReference script on the interior door can lose timer state or keep
  stale busy flags while the interior cell unloads. Hosting the transition loop on a persistent
  StartGameEnabled Quest keeps timers alive across interior unload, hooks Actor.OnPlayerLoadGame to
  cancel stale timers and reset busy/inFlight on reload, and prioritizes persistent surface anchor
  FO4TerrainCore.esm:0x0A775B with an immediate 1.5 s retry anchor if still inside.}

string Property ExitAnchorPlugin = "FO4TerrainCore.esm" Auto
{Primary persistent exterior anchor plugin for "out" transitions.}

int Property ExitAnchorId = 0x0A775B Auto
{Primary persistent exterior surface anchor FormID (0x0A775B FO4Core_CommonwealthMapMarkerVault111).}

string Property SecondaryExitAnchorPlugin = "FO4TerrainCore.esm" Auto
{Secondary persistent exterior anchor plugin used on 1.5 s retry when needed.}

int Property SecondaryExitAnchorId = 0x0A775C Auto
{Secondary persistent exterior surface anchor FormID (0x0A775C FO4Core_CommonwealthMapMarkerConcord).}

float Property OutRetryAfterSeconds = 1.5 Auto
{For "out" transitions still inside the interior after MoveTo, immediately try retry anchor after this delay.}

bool Property EnableLog = true Auto
string Property LogName = "fo4sf_loaddoor" Auto

int TIMER_ARRIVAL = 1
bool initialized = false
bool busy = false
bool inFlight = false
bool settlePending = false
bool activeIsOut = false
bool activeUseDestPos = false
bool activeRequireCoreCell = true
int activeAttempt = 0
int activeMaxTries = 3
int activeWaitStep = 0
int activeMaxWaitSteps = 40
float activeTx = 0.0
float activeTy = 0.0
float activeTz = 0.0
float activeHeading = 0.0
float activePosTolSq = 25.0
float activeFallDrop = 6.0
float activeWaitStepSec = 0.25
float activeSettleSec = 0.35
float attemptStartedAt = 0.0
ObjectReference activeDoor = None
ObjectReference activeAnchor = None
Cell activeBeforeCell = None
Cell activeAnchorCell = None
string activeTargetPlugin = ""
int activeTargetFormId = 0
string activeFallbackPlugin = ""
int activeFallbackFormId = 0
string activeDirection = "in"
string activeDoorTag = "museum_door"
string lastReason = ""
Actor registeredPlayer = None

Event OnInit()
    EnsureInitialized()
EndEvent

Event OnQuestInit()
    EnsureInitialized()
EndEvent

Event OnQuestStarted()
    EnsureInitialized()
EndEvent

Function EnsureInitialized()
    if !IsRunning()
        StartNoWait()
    endif
    RegisterLoadGameEvent()
    if !initialized
        initialized = true
        Actor player = Game.GetPlayer()
        Cell curCell = None
        if player != None
            curCell = player.GetParentCell()
        endif
        Log("FO4SF_LOADDOOR quest_init cell=" + curCell + " exit_anchor=0x0A775B")
    endif
EndFunction

Function RegisterLoadGameEvent()
    Actor player = Game.GetPlayer()
    if player == None
        return
    endif
    if registeredPlayer != player
        registeredPlayer = player
        RegisterForRemoteEvent(player, "OnPlayerLoadGame")
    endif
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    ResetAfterReload(akSender)
EndEvent

Function ResetAfterReload(Actor player)
    CancelTimer(TIMER_ARRIVAL)
    if activeDoor != None
        FO4SF_ConfirmedLoadDoor prevDoor = activeDoor as FO4SF_ConfirmedLoadDoor
        if prevDoor != None
            prevDoor.ResetOnReload()
        endif
    endif
    busy = false
    inFlight = false
    settlePending = false
    activeDoor = None
    activeAnchor = None
    activeBeforeCell = None
    activeAnchorCell = None
    activeAttempt = 0
    activeWaitStep = 0
    attemptStartedAt = 0.0
    lastReason = ""
    registeredPlayer = None
    RegisterLoadGameEvent()

    Actor curPlayer = player
    if curPlayer == None
        curPlayer = Game.GetPlayer()
    endif
    Cell curCell = None
    bool isInt = false
    if curPlayer != None
        curCell = curPlayer.GetParentCell()
        isInt = curPlayer.IsInInterior()
    endif
    Log("FO4SF_LOADDOOR reload_ready cell=" + curCell + " interior=" + isInt)
EndFunction

bool Function BeginDoorTransition(ObjectReference doorRef, Actor player, ObjectReference explicitAnchor, string tgtPlugin, int tgtFormId, string fbPlugin, int fbFormId, string dirStr, string doorTag, bool useDestPos, float tx, float ty, float tz, float headingDeg, bool reqCoreCell, float posTolSq, float fallDrop, int maxRetries, float waitStepSec, int maxWaitSteps, float settleSec)
    EnsureInitialized()
    if player == None
        return false
    endif
    if busy
        float nowCheck = Utility.GetCurrentRealTime()
        if attemptStartedAt > 0.0 && (nowCheck - attemptStartedAt) >= 15.0
            Log("FO4SF_LOADDOOR controller_watchdog_reset tag=" + activeDoorTag + " new_tag=" + doorTag)
            ClearState(false, "controller_watchdog_reset")
        else
            Log("FO4SF_LOADDOOR ignored tag=" + doorTag + " dir=" + dirStr + " reason=controller_busy active_tag=" + activeDoorTag)
            return false
        endif
    endif

    bool isOut = (dirStr == "out" || dirStr == "OUT" || dirStr == "Out")
    activeDoor = doorRef
    activeTargetPlugin = tgtPlugin
    activeTargetFormId = tgtFormId
    activeFallbackPlugin = fbPlugin
    activeFallbackFormId = fbFormId
    activeDirection = dirStr
    activeDoorTag = doorTag
    activeIsOut = isOut
    activeUseDestPos = useDestPos
    activeTx = tx
    activeTy = ty
    activeTz = tz
    activeHeading = headingDeg
    activeRequireCoreCell = reqCoreCell
    activePosTolSq = posTolSq
    activeFallDrop = fallDrop
    activeMaxTries = maxRetries
    if activeMaxTries < 1
        activeMaxTries = 1
    endif
    activeWaitStepSec = waitStepSec
    if activeWaitStepSec <= 0.05
        activeWaitStepSec = 0.25
    endif
    activeMaxWaitSteps = maxWaitSteps
    if activeMaxWaitSteps < 1
        activeMaxWaitSteps = 1
    endif
    activeSettleSec = settleSec
    if activeSettleSec <= 0.0
        activeSettleSec = 0.1
    endif

    ObjectReference anchor = ResolvePrimaryAnchor(explicitAnchor, isOut, tgtPlugin, tgtFormId, fbPlugin, fbFormId)
    if anchor == None
        Log("FO4SF_LOADDOOR failed tag=" + doorTag + " dir=" + dirStr + " attempts=0 reason=anchor_missing plugin=" + tgtPlugin + " formid=" + tgtFormId)
        ClearState(false, "anchor_missing")
        return false
    endif

    busy = true
    inFlight = true
    settlePending = false
    activeBeforeCell = player.GetParentCell()
    activeAnchor = anchor
    activeAnchorCell = anchor.GetParentCell()
    activeAttempt = 1
    activeWaitStep = 0
    attemptStartedAt = Utility.GetCurrentRealTime()
    lastReason = ""

    player.MoveTo(activeAnchor, 0.0, 0.0, 0.0, True, False)
    StartTimer(activeWaitStepSec, TIMER_ARRIVAL)
    return true
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID != TIMER_ARRIVAL || !inFlight
        return
    endif

    Actor player = Game.GetPlayer()
    if player == None || activeAnchor == None
        FinishFailed(player, "player_or_anchor_lost")
        return
    endif

    float nowRt = Utility.GetCurrentRealTime()
    if attemptStartedAt <= 0.0 || nowRt < attemptStartedAt
        attemptStartedAt = nowRt
    endif
    float elapsed = nowRt - attemptStartedAt

    if !settlePending
        bool ready = IsTransitionReady(player, activeBeforeCell, activeAnchorCell, activeIsOut)
        if !ready
            if activeIsOut && player.IsInInterior() && elapsed >= OutRetryAfterSeconds && activeAttempt < activeMaxTries
                lastReason = "still_interior_1p5s"
                Log("FO4SF_LOADDOOR retry tag=" + activeDoorTag + " dir=" + activeDirection + " attempt=" + activeAttempt + "/" + activeMaxTries + " reason=still_interior_fast elapsed=" + elapsed + " cell=" + player.GetParentCell() + " pos=" + FormatPos(player))
                AdvanceAttemptAndRetryMove(player)
                return
            endif
            activeWaitStep += 1
            if activeWaitStep < activeMaxWaitSteps
                StartTimer(activeWaitStepSec, TIMER_ARRIVAL)
                return
            endif
        else
            if activeUseDestPos
                player.SetPosition(activeTx, activeTy, activeTz)
                player.SetAngle(0.0, 0.0, activeHeading)
                settlePending = true
                StartTimer(activeSettleSec, TIMER_ARRIVAL)
                return
            endif
        endif
    endif

    bool confirmed = ConfirmLanding(player, activeAnchor, activeAnchorCell, activeIsOut, activeTx, activeTy, activeTz)
    if confirmed
        bool coreCell = IsCoreCellMatch(player.GetParentCell(), activeAnchor)
        Log("FO4SF_LOADDOOR confirmed tag=" + activeDoorTag + " dir=" + activeDirection + " attempts=" + activeAttempt + " core_cell=" + coreCell + " cell=" + player.GetParentCell() + " world=" + player.GetWorldSpace() + " pos=" + FormatPos(player) + " heading=" + activeHeading)
        ClearState(true, "")
        return
    endif

    Log("FO4SF_LOADDOOR retry tag=" + activeDoorTag + " dir=" + activeDirection + " attempt=" + activeAttempt + "/" + activeMaxTries + " reason=" + lastReason + " cell=" + player.GetParentCell() + " pos=" + FormatPos(player))
    if activeAttempt >= activeMaxTries
        FinishFailed(player, lastReason)
        return
    endif

    AdvanceAttemptAndRetryMove(player)
EndEvent

Function AdvanceAttemptAndRetryMove(Actor player)
    activeAttempt += 1
    activeWaitStep = 0
    settlePending = false
    attemptStartedAt = Utility.GetCurrentRealTime()
    if NeedsMoveTo(player, activeAnchorCell, activeIsOut)
        ObjectReference retryAnchor = ResolveRetryAnchor(activeAnchor, activeIsOut, activeTargetPlugin, activeTargetFormId, activeFallbackPlugin, activeFallbackFormId)
        if retryAnchor != None
            activeAnchor = retryAnchor
            activeAnchorCell = retryAnchor.GetParentCell()
        endif
        player.MoveTo(activeAnchor, 0.0, 0.0, 0.0, True, False)
    endif
    StartTimer(activeWaitStepSec, TIMER_ARRIVAL)
EndFunction

Function FinishFailed(Actor player, string reason)
    if player != None
        Log("FO4SF_LOADDOOR failed tag=" + activeDoorTag + " dir=" + activeDirection + " attempts=" + activeAttempt + " reason=" + reason + " cell=" + player.GetParentCell() + " world=" + player.GetWorldSpace() + " pos=" + FormatPos(player))
    else
        Log("FO4SF_LOADDOOR failed tag=" + activeDoorTag + " dir=" + activeDirection + " attempts=" + activeAttempt + " reason=" + reason)
    endif
    ClearState(false, reason)
EndFunction

Function ClearState(bool ok, string reason)
    CancelTimer(TIMER_ARRIVAL)
    ObjectReference doorRef = activeDoor
    busy = false
    inFlight = false
    settlePending = false
    activeDoor = None
    activeAnchor = None
    activeBeforeCell = None
    activeAnchorCell = None
    attemptStartedAt = 0.0
    if doorRef != None
        FO4SF_ConfirmedLoadDoor loadDoor = doorRef as FO4SF_ConfirmedLoadDoor
        if loadDoor != None
            loadDoor.NotifyControllerComplete(ok, reason)
        endif
    endif
EndFunction

ObjectReference Function ResolvePrimaryAnchor(ObjectReference explicitAnchor, bool isOut, string tgtPlugin, int tgtFormId, string fbPlugin, int fbFormId)
    if isOut
        ; Cold-reload fix: prioritize persistent ExitAnchorId (0x0A775B) first for exterior transitions.
        if ExitAnchorPlugin != "" && ExitAnchorId > 0
            ObjectReference exitRef = Game.GetFormFromFile(ExitAnchorId, ExitAnchorPlugin) as ObjectReference
            if exitRef != None
                return exitRef
            endif
        endif
    endif
    if explicitAnchor != None
        return explicitAnchor
    endif
    if tgtPlugin != "" && tgtFormId > 0
        ObjectReference primary = Game.GetFormFromFile(tgtFormId, tgtPlugin) as ObjectReference
        if primary != None
            return primary
        endif
    endif
    if fbPlugin != "" && fbFormId > 0
        ObjectReference fb = Game.GetFormFromFile(fbFormId, fbPlugin) as ObjectReference
        if fb != None
            return fb
        endif
    endif
    return None
EndFunction

ObjectReference Function ResolveRetryAnchor(ObjectReference currentAnchor, bool isOut, string tgtPlugin, int tgtFormId, string fbPlugin, int fbFormId)
    if isOut
        if SecondaryExitAnchorPlugin != "" && SecondaryExitAnchorId > 0
            ObjectReference sec = Game.GetFormFromFile(SecondaryExitAnchorId, SecondaryExitAnchorPlugin) as ObjectReference
            if sec != None && sec != currentAnchor
                return sec
            endif
        endif
        if fbPlugin != "" && fbFormId > 0
            ObjectReference fb = Game.GetFormFromFile(fbFormId, fbPlugin) as ObjectReference
            if fb != None && fb != currentAnchor
                return fb
            endif
        endif
        if tgtPlugin != "" && tgtFormId > 0
            ObjectReference tgt = Game.GetFormFromFile(tgtFormId, tgtPlugin) as ObjectReference
            if tgt != None && tgt != currentAnchor
                return tgt
            endif
        endif
        if ExitAnchorPlugin != "" && ExitAnchorId > 0
            ObjectReference ex = Game.GetFormFromFile(ExitAnchorId, ExitAnchorPlugin) as ObjectReference
            if ex != None
                return ex
            endif
        endif
    endif
    if fbPlugin != "" && fbFormId > 0
        ObjectReference fbIn = Game.GetFormFromFile(fbFormId, fbPlugin) as ObjectReference
        if fbIn != None
            return fbIn
        endif
    endif
    if tgtPlugin != "" && tgtFormId > 0
        ObjectReference priIn = Game.GetFormFromFile(tgtFormId, tgtPlugin) as ObjectReference
        if priIn != None
            return priIn
        endif
    endif
    return currentAnchor
EndFunction

bool Function IsTransitionReady(Actor player, Cell beforeCell, Cell anchorCell, bool isOut)
    bool stateOk = false
    if isOut
        stateOk = !player.IsInInterior()
    else
        stateOk = player.IsInInterior()
    endif
    if !stateOk || !player.Is3DLoaded()
        return false
    endif
    if isOut
        return true
    endif
    Cell curCell = player.GetParentCell()
    return (anchorCell != None && curCell == anchorCell) || (anchorCell == None && curCell != beforeCell)
EndFunction

bool Function NeedsMoveTo(Actor player, Cell anchorCell, bool isOut)
    if isOut
        return player.IsInInterior()
    endif
    if !player.IsInInterior()
        return true
    endif
    if anchorCell != None && player.GetParentCell() != anchorCell
        return true
    endif
    return false
EndFunction

bool Function ConfirmLanding(Actor player, ObjectReference anchor, Cell anchorCell, bool isOut, float tx, float ty, float tz)
    if isOut
        if player.IsInInterior()
            lastReason = "still_interior"
            return false
        endif
    else
        if !player.IsInInterior()
            lastReason = "still_exterior"
            return false
        endif
    endif

    if !player.Is3DLoaded()
        lastReason = "not_3d_loaded"
        return false
    endif

    Cell afterCell = player.GetParentCell()
    if afterCell == None
        lastReason = "cell_unavailable"
        return false
    endif

    if isOut
        WorldSpace afterWorld = player.GetWorldSpace()
        if afterWorld == None
            lastReason = "world_unavailable"
            return false
        endif
        if activeRequireCoreCell && !IsCoreCellMatch(afterCell, anchor)
            lastReason = "surface_cell_not_core"
            return false
        endif
    else
        if anchorCell != None && afterCell != anchorCell
            lastReason = "interior_cell_mismatch"
            return false
        endif
    endif

    if activeUseDestPos
        float dx = player.GetPositionX() - tx
        float dy = player.GetPositionY() - ty
        float dz = player.GetPositionZ() - tz
        bool posOk = (dx * dx + dy * dy <= activePosTolSq) && (dz > -activeFallDrop) && (dz < 3.0)
        if !posOk
            lastReason = "position_not_confirmed"
            return false
        endif
    endif

    return true
EndFunction

bool Function IsCoreCellMatch(Cell afterCell, ObjectReference anchor)
    if afterCell == None || anchor == None
        return false
    endif
    int cellMod = afterCell.GetFormID() / 16777216
    int anchorMod = anchor.GetFormID() / 16777216
    return cellMod == anchorMod
EndFunction

string Function FormatPos(Actor player)
    return player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ()
EndFunction

Function Log(string msg)
    if !EnableLog
        return
    endif
    Debug.OpenUserLog(LogName)
    Debug.TraceUser(LogName, msg)
EndFunction
