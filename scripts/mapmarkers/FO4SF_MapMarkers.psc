Scriptname FO4SF_MapMarkers extends Quest
{Puts the Commonwealth's map markers into the world the player walks in (fo4-to-starfield, docs/terrain/map-markers.md
 "Markers in the merged world"). The markers are persistent references of FO4TerrainCore.esm's overlay world, and a
 persistent reference of that world stays at its LOCAL position in the base world (door probe (a), 16 Oct; the
 mission's actors, 18 Oct), while the player walks in a world made at run time (FF0054C8 in the mission log) that
 places the core's records at local + the merge offset: no icon showed (owner, 19 Oct, v6). Every Interval seconds,
 with the player outdoors inside the overlay's merged extent, each marker that is not at its merged spot in the
 player's world is enabled and moved there (MoveTo onto the player with the difference as the offset, the form
 FO4SF_LoadDoor and the mission's Relocate use, but keeping the reference's own rotation: the list also holds the
 landing spot's pad, whose facing is the ship's). The player is read again before every move, and a pass stops once
 they are indoors, in another world or outside the extent. A reference the game will not move (the landing pad) is
 left alone for the rest of the session. Every move goes to the user log "fo4sf_map"
 (My Games\Starfield\Logs\Script\User\fo4sf_map.0.log).}

ObjectReference[] Property Markers Auto Const Mandatory
{The core's MapMarker references (dotnet/MapMarkers fills them from the core plugin), then the plugin's own: its
 markers (--extra) and the landing spot's pad, trigger, marker and heading (--landing).}

float[] Property LocalX Auto Const Mandatory
float[] Property LocalY Auto Const Mandatory
float[] Property LocalZ Auto Const Mandatory
{Each marker's written (local) position, so the target does not depend on where a marker was last moved to.}

float Property MergeOffsetX = -1200.0 Auto Const
float Property MergeOffsetY = -2700.0 Auto Const
{vmad_patch.MERGE_MEASURED (measured in game); z unchanged.}

float Property MinX = -4400.0 Auto Const
float Property MaxX = 2000.0 Auto Const
float Property MinY = -5900.0 Auto Const
float Property MaxY = 500.0 Auto Const
{The overlay's merged extent (local -3200..3200 m + the merge offset). Coordinates alone cannot tell two exterior
 worlds apart: a player standing outdoors in another world inside this box would pull the markers there.}

float Property Tolerance = 5.0 Auto Const
{A marker within this many units of its merged spot (x, y), in the player's world, counts as placed.}

float Property ZTolerance = 0.05 Auto Const
{The same for height: a save made before a build that lifted LocalZ holds the markers at the old height, and the
 moved markers' saved positions outlive the records (docs/JOURNAL.md, changed references); a marker more than this
 far from its LocalZ is moved again. Half the lift step: dotnet/MapMarkers accepts --z-lift in steps of 0.1 m only,
 so any change between builds is at least 0.1 m and is seen, while a landed move (within 0.01 m, fo4sf_map.0.log
 22 Oct) is not moved again.}

float Property SameWorld = 100000.0 Auto Const
{GetDistance above this means the marker is in another world (it reads float max there, 18 Oct).}

float Property Interval = 2.0 Auto Const

int Property MaxMoves = 40 Auto Const
{Stop moving after this many moves in one game session (a move that never lands would otherwise repeat every
 Interval). The count is saved state; it starts over when a build changes the markers' count or their height (budgetN,
 budgetZ), so a later lift reaches a save whose budget an earlier placement spent (Codex on #483), and at every game
 session (NewSession), so markers a session left in the wrong place are put right in the next one.}

int Property LandingPadID = 0x007145 Auto Const
{ShipLandingMarker_80m_Large (Starfield.esm), the landing spot's pad. dotnet/MapMarkers lists the landing spot last, as
 pad, trigger, marker, heading, all four in one quest, so the pad is fourth from its quest's end and the marker two
 places after it.}

bool Property BorderSignal = True Auto Const
{Write "border=off" / "border=on" to this log when the player enters or leaves our world, for the SFSE plugin
 FO4SFBorder (sfse/FO4SFBorder/README.md), which turns the game's border regions off only while the line says off.}

string LogName = "fo4sf_map"
; the border signal's state: -1 none written this session, 0 off (our world), 1 on; ourWorld is the player's world
; seen while in one of the core's cells (the runtime instance changes every launch, so it is learned, not a property)
int border = -1
WorldSpace ourWorld = None
float lastRealTime = -1.0
int moves = 0
; the build the move budget was spent on: the marker count and LocalZ[0] (every lift changes it). Const properties
; read the installed records, these two the save, so a new build differs on the first pass after it.
int budgetN = -1
float budgetZ = 0.0
; this game session (Place's own clock, as Border keeps its own): the references the game refused to move, and whether
; the landing marker was shown on the star map
float placeRealTime = -1.0
bool[] refused
bool landingShown = False

Event OnInit()
    Debug.OpenUserLog(LogName)
    Trace("init markers=" + Markers.Length)
    RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")
    StartTimer(Interval, 1)
EndEvent

; Every save load starts a new session, for Place (the move budget, the refused list, the landing) and for Border (the
; log opened again, the signal written again). The clocks alone miss a launch whose first pass reads a later real time
; than the save's last one (Codex on #570: saved 20 s, first pass at 90 s), so the load clears them. OnPlayerLoadGame
; is declared on Actor (PC read, 19 Oct: docs/newgame/vault111-start.md); the mission's keeper registers the same way.
Event Actor.OnPlayerLoadGame(Actor akSender)
    placeRealTime = 0.0                                       ; NewSession: unset, so a new session
    lastRealTime = 1000000000.0                               ; Border: any clock is below it, so a new session
EndEvent

Function ResetBudget()
    if Markers.Length > 0 && (budgetN != Markers.Length || budgetZ != LocalZ[0])
        Trace("budget reset for markers=" + Markers.Length + " z0=" + LocalZ[0] + " (was " + budgetN + " / " + budgetZ + ", moves=" + moves + ")")
        budgetN = Markers.Length
        budgetZ = LocalZ[0]
        moves = 0
        refused = new bool[128]                                 ; a new build can list other references at those places
        landingShown = False
    endif
EndFunction

; A new game session (the real-time clock starts over at every launch, as Border reads it): the move budget starts over,
; and so does the list of references the game refused to move. A save from before this script had these variables
; brings them in unset (0.0 or the initial -1.0), so either one counts as a new session and the list is made; a save
; load sets 0.0 (OnPlayerLoadGame).
bool Function NewSession()
    float rt = Utility.GetCurrentRealTime()
    bool fresh = placeRealTime <= 0.0 || rt < placeRealTime
    if fresh
        Debug.OpenUserLog(LogName)                              ; a load in a new launch runs no OnInit to open it
        RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")  ; a save from before the registration ran OnInit
        if moves > 0
            Trace("session: move budget starts over (was moves=" + moves + ")")
        endif
        moves = 0
        refused = new bool[128]                                 ; a quest lists at most 100 (dotnet/MapMarkers PerQuest)
        landingShown = False
    endif
    placeRealTime = rt
    return fresh
EndFunction

; Once per session and quest, what Border's guards read: a coc session from the main menu at Red Rocket wrote no border
; line in 240 s while "moved 9" lines kept coming (Review, 2026-10-28), and the log could not say whether 0x800 ticked
; or its Markers[0] was None.
Function SessionLine(Actor player)
    ObjectReference first = None
    if Markers.Length > 0
        first = Markers[0]
    endif
    Trace("session id=" + GetFormID() + " signal=" + SignalQuest() + " enabled=" + BorderSignal + " markers=" + Markers.Length + " first=" + first + " interior=" + player.IsInInterior())
EndFunction

; The landing spot's map marker, found after its pad, is marked discovered and shown on the star map, so the planet
; map can offer it as a place to land (owner, 2026-10-28: Mars's map had no Commonwealth location; a vanilla landing
; site is discovered when the player lands there). Once per session, wherever the player is; one reference read per
; quest, so the border signal is not held up.
Function ShowLanding()
    if landingShown
        return
    endif
    landingShown = True
    int i = Markers.Length - 4
    if i < 0
        return
    endif
    ObjectReference pad = Markers[i]
    ObjectReference marker = Markers[i + 2]
    if pad != None && marker != None && pad.GetBaseObject() == Game.GetForm(LandingPadID)
        marker.SetMarkerDiscovered()
        marker.SetMarkerVisibleOnStarMap(True)
        Trace("landing marker " + (i + 2) + " discovered and shown on the star map")
    endif
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID == 1
        Place(Game.GetPlayer())
        StartTimer(Interval, 1)
    endif
EndEvent

Function Place(Actor player)
    ResetBudget()
    if NewSession()
        SessionLine(player)
    endif
    Border(player)
    ShowLanding()
    if player.IsInInterior()
        return
    endif
    WorldSpace w = player.GetWorldSpace()
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    if px < MinX || px > MaxX || py < MinY || py > MaxY
        return
    endif
    int i = 0
    while i < Markers.Length && moves < MaxMoves              ; the budget holds per move, not per batch
        ObjectReference m = Markers[i]
        if m != None && !refused[i]
            float x = LocalX[i] + MergeOffsetX
            float y = LocalY[i] + MergeOffsetY
            float z = LocalZ[i]
            float before = player.GetDistance(m)                ; float max: another world
            float bx = m.GetPositionX()
            float by = m.GetPositionY()
            float ex = bx - x
            float ey = by - y
            float ez = m.GetPositionZ() - z
            if before > SameWorld || ex * ex + ey * ey > Tolerance * Tolerance || ez * ez > ZTolerance * ZTolerance
                ; the player as they are now, just before the move: a load door can take them away while a pass runs,
                ; and a pass that read them once put about 300 markers into Vault 95 at the target plus the trip and
                ; spent every budget (PC, 2026-10-24 10:24, fo4sf_map.0.log)
                if player.IsInInterior() || player.GetWorldSpace() != w
                    Trace("pass stopped at " + i + ": the player went indoors or to another world")
                    return
                endif
                px = player.GetPositionX()
                py = player.GetPositionY()
                float pz = player.GetPositionZ()
                if px < MinX || px > MaxX || py < MinY || py > MaxY
                    return
                endif
                m.Enable(False)
                m.MoveTo(player, x - px, y - py, z - pz, False, False)   ; no match-rotation: keep the record's
                moves += 1
                float d = player.GetDistance(m)
                Trace("moved " + i + " to " + m.GetPositionX() + " " + m.GetPositionY() + " " + m.GetPositionZ() + " target " + x + " " + y + " " + z + " before=" + before + " d=" + d + " moves=" + moves)
                float sx = m.GetPositionX() - bx
                float sy = m.GetPositionY() - by
                if d > SameWorld && sx * sx + sy * sy < 0.0001
                    ; still where it was, in its own world: the game refused the move ("cannot be moved", the landing
                    ; pad, 2026-10-24), so it is not tried again this session (it spent its quest's whole budget)
                    refused[i] = True
                    Trace("refused " + i + ": not moved again this session")
                endif
            endif
        endif
        i += 1
    endwhile
EndFunction

; Only the first quest (0x800) writes the signal: every quest of the plugin runs this script, and only the first one's
; Markers[0] is a core marker (dotnet/MapMarkers lists the core's markers first; the extra and landing records that fill
; the later quests are this plugin's own), so a later quest would read the plugin's index as the core's and write
; border=on (PC, 2026-10-24: on/on/off/on within 0.8 s on the first load at Red Rocket). Low 12 bits, so a light
; plugin's FE-prefixed (negative) id gives the same answer.
bool Function SignalQuest()
    int low = QuestLow()
    return low == 2048
EndFunction

; The quest's FormID, low 12 bits (2048 for 0x800, 2049 for 0x801, ...), on every log line so the quests can be told apart.
int Function QuestLow()
    int low = GetFormID() % 4096
    if low < 0
        low += 4096
    endif
    return low
EndFunction

; In our world: the player's cell is one of the core's own cells (the runtime instance keeps the core's cell ids:
; docs/terrain/door-rounds.md), or the player is outdoors in the same world as when they last were (the generated
; land past our cells). Indoors keeps the last state, so a door out lands with the border already off.
Function Border(Actor player)
    if !BorderSignal || !SignalQuest() || Markers.Length == 0 || Markers[0] == None
        return
    endif
    float rt = Utility.GetCurrentRealTime()
    if rt < lastRealTime                                      ; a new game session: the plugin skips old lines
        Debug.OpenUserLog(LogName)
        border = -1
        ourWorld = None
    endif
    lastRealTime = rt
    if player.IsInInterior()
        return
    endif
    int core = Markers[0].GetFormID() / 16777216
    Cell c = player.GetParentCell()
    WorldSpace w = player.GetWorldSpace()
    int want = 1
    if c != None && c.GetFormID() / 16777216 == core
        ourWorld = w
        want = 0
    elseif ourWorld != None && w == ourWorld
        want = 0
    endif
    if want != border
        border = want
        if want == 0
            Trace("border=off cell=" + c + " world=" + w)
        else
            Trace("border=on cell=" + c + " world=" + w)
        endif
    endif
EndFunction

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MAP rt=" + Utility.GetCurrentRealTime() + " q=" + QuestLow() + " " + msg)
EndFunction
