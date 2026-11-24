Scriptname FO4SF_ConfirmedLoadDoor extends ObjectReference
{Confirmed-arrival two-way load-door bridge for Fallout 4 interiors in Starfield (Round 11 Step 3c / Part 3 v2).

Handles both interior entry (Direction = "in", e.g. Museum front door -> FO4Port_ConcordMuseum01)
and merged exterior exit (Direction = "out", e.g. Museum front door or 3F roof door -> Concord
surface on FO4TerrainCore.esm).

Modeled on FO4SF_NewGameQuest.FinishSurface + CheckLanding using a non-blocking StartTimer / OnTimer
state machine so OnActivate returns immediately after MoveTo rather than blocking while Starfield
unloads the interior cell:
  1. Log FO4SF_LOADDOOR activate_begin BEFORE MoveTo (accepts akActionRef == player || akActionRef == None
     so both in-world E activation and console `<ref>.activate` work cleanly).
  2. Resolve destination anchor (DestinationAnchor -> TargetPlugin/TargetFormId -> optional
     FallbackTargetPlugin/FallbackTargetFormId) and call player.MoveTo(anchor, 0.0, 0.0, 0.0, True, False).
  3. Drive arrival polling on TIMER_ARRIVAL via StartTimer(WaitStepSeconds, TIMER_ARRIVAL):
     wait until player's interior/exterior state matches Direction and player.Is3DLoaded().
  4. When UseDestinationPosition is true, apply SetPosition(DestinationX + MergeOffsetX,
     DestinationY + MergeOffsetY, DestinationZ) and SetAngle(0.0, 0.0, DestinationHeading), then
     arm TIMER_ARRIVAL for SettleSeconds before final confirmation.
  5. Confirm arrival AFTER SetPosition:
     - player.Is3DLoaded() and interior/exterior state matches Direction;
     - for Direction == "out" with RequireCoreCell == true: afterWorld != None and
       afterCell.GetFormID() / 16777216 == anchor.GetFormID() / 16777216 (merged core cell
       ownership check, because persistent exterior anchors sit at unmerged local XY until
       SetPosition shifts the player into the merged core grid);
     - for Direction == "in": afterCell != None and matches anchor's parent cell when known;
     - when UseDestinationPosition is true: XY squared error <= PositionToleranceSq and
       dz > -FallDrop && dz < 3.0.
  6. Retry up to MaxRetries times on transient unconfirmed arrival without re-calling MoveTo when
     already in the target space (preventing 2.9 km bounce-back to the unmerged anchor cell).
}

Group Target
    ObjectReference Property DestinationAnchor Auto
    {Persistent destination anchor reference (optional when TargetPlugin + TargetFormId are set).}

    string Property TargetPlugin = "" Auto
    {Optional plugin name for runtime anchor resolution via Game.GetFormFromFile (e.g. "FO4Port.esm" or "FO4TerrainCore.esm").}

    int Property TargetFormId = 0 Auto
    {Optional local FormID of the persistent anchor in TargetPlugin.}

    string Property FallbackTargetPlugin = "" Auto
    {Optional secondary plugin for exterior MarsPlanetWorld anchor fallback when primary anchor is unavailable.}

    int Property FallbackTargetFormId = 0 Auto
    {Optional secondary local FormID for exterior anchor fallback.}

    string Property Direction = "in" Auto
    {"in" for exterior -> interior entry; "out" for interior -> merged exterior exit.}

    string Property DoorTag = "museum_door" Auto
    {Short identifier included in every FO4SF_LOADDOOR log line.}
EndGroup

Group Coordinates
    bool Property UseDestinationPosition = false Auto
    {When true, applies SetPosition(DestinationX + MergeOffsetX, DestinationY + MergeOffsetY, DestinationZ) and SetAngle after MoveTo.}

    float Property DestinationX = 0.0 Auto
    float Property DestinationY = 0.0 Auto
    float Property DestinationZ = 0.0 Auto
    float Property DestinationHeading = 0.0 Auto
    float Property MergeOffsetX = 0.0 Auto
    float Property MergeOffsetY = 0.0 Auto
EndGroup

Group Confirmation
    bool Property RequireCoreCell = true Auto
    {For Direction == "out", require post-SetPosition parent cell to share anchor's load-order plugin index (FinishSurface coreCell check).}

    float Property PositionToleranceSq = 25.0 Auto
    {Maximum allowed squared XY error (metres^2) after SetPosition (25.0 = 5.0 m radius).}

    float Property FallDrop = 6.0 Auto
    {Maximum downward Z settle tolerance (metres) after SetPosition.}

    int Property MaxRetries = 3 Auto
    {Maximum MoveTo + confirm attempts before logging terminal failure.}

    float Property WaitStepSeconds = 0.25 Auto
    {Non-blocking timer polling interval while waiting for cell transition and 3D load.}

    int Property MaxWaitSteps = 40 Auto
    {Maximum polling ticks per attempt (40 * 0.25 s = 10.0 s).}

    float Property SettleSeconds = 0.35 Auto
    {Non-blocking settle timer after SetPosition before confirming final coordinates and cell ownership.}

    bool Property EnableLog = true Auto
    string Property LogName = "fo4sf_loaddoor" Auto
EndGroup

int TIMER_ARRIVAL = 1
bool busy = false
bool inFlight = false
bool settlePending = false
bool activeIsOut = false
int activeAttempt = 0
int activeMaxTries = 3
int activeWaitStep = 0
float activeTx = 0.0
float activeTy = 0.0
float activeTz = 0.0
ObjectReference activeAnchor = None
Cell activeBeforeCell = None
Cell activeAnchorCell = None
string lastReason = ""

Event OnInit()
    Log("FO4SF_LOADDOOR init tag=" + DoorTag + " dir=" + Direction + " cell=" + GetParentCell())
EndEvent

Event OnLoad()
    CancelTimer(TIMER_ARRIVAL)
    busy = false
    inFlight = false
    settlePending = false
EndEvent

Event OnCellAttach()
    if !inFlight
        busy = false
    endif
    Log("FO4SF_LOADDOOR attached tag=" + DoorTag + " dir=" + Direction + " cell=" + GetParentCell() + " busy=" + busy)
EndEvent

Event OnActivate(ObjectReference akActionRef)
    Actor player = Game.GetPlayer()
    if player == None
        return
    endif
    if akActionRef != None && akActionRef != player
        return
    endif
    if busy
        Log("FO4SF_LOADDOOR ignored tag=" + DoorTag + " dir=" + Direction + " reason=busy")
        return
    endif

    Cell beforeCell = player.GetParentCell()
    Log("FO4SF_LOADDOOR activate_begin tag=" + DoorTag + " dir=" + Direction + " caller=" + akActionRef + " cell=" + beforeCell + " pos=" + FormatPos(player))

    ObjectReference anchor = ResolveAnchor()
    if anchor == None
        Log("FO4SF_LOADDOOR failed tag=" + DoorTag + " dir=" + Direction + " attempts=0 reason=anchor_missing plugin=" + TargetPlugin + " formid=" + TargetFormId)
        return
    endif

    busy = true
    inFlight = true
    settlePending = false
    activeIsOut = (Direction == "out" || Direction == "OUT" || Direction == "Out")
    activeBeforeCell = beforeCell
    activeAnchor = anchor
    activeAnchorCell = anchor.GetParentCell()
    activeTx = DestinationX + MergeOffsetX
    activeTy = DestinationY + MergeOffsetY
    activeTz = DestinationZ
    activeMaxTries = MaxRetries
    if activeMaxTries < 1
        activeMaxTries = 1
    endif
    activeAttempt = 1
    activeWaitStep = 0
    lastReason = ""

    ; Non-blocking MoveTo + StartTimer: return from OnActivate immediately so CE2 cell streaming never stalls.
    player.MoveTo(activeAnchor, 0.0, 0.0, 0.0, True, False)
    StartTimer(GetPollInterval(), TIMER_ARRIVAL)
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID != TIMER_ARRIVAL || !inFlight
        return
    endif

    Actor player = Game.GetPlayer()
    if player == None || activeAnchor == None
        FinishFailed(player, "player_or_anchor_lost")
        return
    endif

    if !settlePending
        bool ready = IsTransitionReady(player, activeBeforeCell, activeAnchorCell, activeIsOut)
        if !ready
            activeWaitStep += 1
            int maxSteps = MaxWaitSteps
            if maxSteps < 1
                maxSteps = 1
            endif
            if activeWaitStep < maxSteps
                StartTimer(GetPollInterval(), TIMER_ARRIVAL)
                return
            endif
        else
            if UseDestinationPosition
                player.SetPosition(activeTx, activeTy, activeTz)
                player.SetAngle(0.0, 0.0, DestinationHeading)
                settlePending = true
                float settleWait = SettleSeconds
                if settleWait <= 0.0
                    settleWait = 0.1
                endif
                StartTimer(settleWait, TIMER_ARRIVAL)
                return
            endif
        endif
    endif

    bool confirmed = ConfirmLanding(player, activeAnchor, activeAnchorCell, activeIsOut, activeTx, activeTy, activeTz)
    if confirmed
        bool coreCell = IsCoreCellMatch(player.GetParentCell(), activeAnchor)
        Log("FO4SF_LOADDOOR confirmed tag=" + DoorTag + " dir=" + Direction + " attempts=" + activeAttempt + " core_cell=" + coreCell + " cell=" + player.GetParentCell() + " world=" + player.GetWorldSpace() + " pos=" + FormatPos(player) + " heading=" + DestinationHeading)
        ClearState()
        return
    endif

    Log("FO4SF_LOADDOOR retry tag=" + DoorTag + " dir=" + Direction + " attempt=" + activeAttempt + "/" + activeMaxTries + " reason=" + lastReason + " cell=" + player.GetParentCell() + " pos=" + FormatPos(player))
    if activeAttempt >= activeMaxTries
        FinishFailed(player, lastReason)
        return
    endif

    activeAttempt += 1
    activeWaitStep = 0
    settlePending = false
    if NeedsMoveTo(player, activeAnchorCell, activeIsOut)
        ObjectReference retryAnchor = ResolveRetryAnchor()
        if retryAnchor != None
            activeAnchor = retryAnchor
            activeAnchorCell = retryAnchor.GetParentCell()
        endif
        player.MoveTo(activeAnchor, 0.0, 0.0, 0.0, True, False)
    endif
    StartTimer(GetPollInterval(), TIMER_ARRIVAL)
EndEvent

Function FinishFailed(Actor player, string reason)
    if player != None
        Log("FO4SF_LOADDOOR failed tag=" + DoorTag + " dir=" + Direction + " attempts=" + activeAttempt + " reason=" + reason + " cell=" + player.GetParentCell() + " world=" + player.GetWorldSpace() + " pos=" + FormatPos(player))
    else
        Log("FO4SF_LOADDOOR failed tag=" + DoorTag + " dir=" + Direction + " attempts=" + activeAttempt + " reason=" + reason)
    endif
    ClearState()
EndFunction

Function ClearState()
    CancelTimer(TIMER_ARRIVAL)
    busy = false
    inFlight = false
    settlePending = false
    activeAnchor = None
    activeBeforeCell = None
    activeAnchorCell = None
EndFunction

float Function GetPollInterval()
    if WaitStepSeconds > 0.05
        return WaitStepSeconds
    endif
    return 0.25
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

ObjectReference Function ResolveAnchor()
    if DestinationAnchor != None
        return DestinationAnchor
    endif
    if TargetPlugin != "" && TargetFormId > 0
        ObjectReference primary = Game.GetFormFromFile(TargetFormId, TargetPlugin) as ObjectReference
        if primary != None
            return primary
        endif
    endif
    return ResolveFallbackAnchor()
EndFunction

ObjectReference Function ResolveRetryAnchor()
    ObjectReference fb = ResolveFallbackAnchor()
    if fb != None
        return fb
    endif
    return ResolveAnchor()
EndFunction

ObjectReference Function ResolveFallbackAnchor()
    if FallbackTargetPlugin != "" && FallbackTargetFormId > 0
        return Game.GetFormFromFile(FallbackTargetFormId, FallbackTargetPlugin) as ObjectReference
    endif
    return None
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
        if RequireCoreCell && !IsCoreCellMatch(afterCell, anchor)
            lastReason = "surface_cell_not_core"
            return false
        endif
    else
        if anchorCell != None && afterCell != anchorCell
            lastReason = "interior_cell_mismatch"
            return false
        endif
    endif

    if UseDestinationPosition
        float dx = player.GetPositionX() - tx
        float dy = player.GetPositionY() - ty
        float dz = player.GetPositionZ() - tz
        bool posOk = (dx * dx + dy * dy <= PositionToleranceSq) && (dz > -FallDrop) && (dz < 3.0)
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
