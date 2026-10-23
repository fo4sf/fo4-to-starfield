Scriptname FO4SF_MapMarkers extends Quest
{Puts the Commonwealth's map markers into the world the player walks in (fo4-to-starfield, docs/terrain/map-markers.md
 "Markers in the merged world"). The markers are persistent references of FO4TerrainCore.esm's overlay world, and a
 persistent reference of that world stays at its LOCAL position in the base world (door probe (a), 16 Oct; the
 mission's actors, 18 Oct), while the player walks in a world made at run time (FF0054C8 in the mission log) that
 places the core's records at local + the merge offset: no icon showed (owner, 19 Oct, v6). Every Interval seconds,
 with the player outdoors inside the overlay's merged extent, each marker that is not at its merged spot in the
 player's world is enabled and moved there (MoveTo onto the player with the difference as the offset, the form
 FO4SF_LoadDoor and the mission's Relocate use, but keeping the reference's own rotation: the list also holds the
 landing spot's pad, whose facing is the ship's). Every move goes to the user log "fo4sf_map"
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
{Stop moving after this many moves for one build (a move that never lands would otherwise repeat every Interval).
 The count is saved state; it starts over when a build changes the markers' count or their height (budgetN, budgetZ),
 so a later lift reaches a save whose budget an earlier placement spent (Codex on #483).}

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

Event OnInit()
    Debug.OpenUserLog(LogName)
    Trace("init markers=" + Markers.Length)
    StartTimer(Interval, 1)
EndEvent

Function ResetBudget()
    if Markers.Length > 0 && (budgetN != Markers.Length || budgetZ != LocalZ[0])
        Trace("budget reset for markers=" + Markers.Length + " z0=" + LocalZ[0] + " (was " + budgetN + " / " + budgetZ + ", moves=" + moves + ")")
        budgetN = Markers.Length
        budgetZ = LocalZ[0]
        moves = 0
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
    Border(player)
    if player.IsInInterior()
        return
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float pz = player.GetPositionZ()
    if px < MinX || px > MaxX || py < MinY || py > MaxY
        return
    endif
    int i = 0
    while i < Markers.Length && moves < MaxMoves              ; the budget holds per move, not per batch
        ObjectReference m = Markers[i]
        if m != None
            float x = LocalX[i] + MergeOffsetX
            float y = LocalY[i] + MergeOffsetY
            float z = LocalZ[i]
            float before = player.GetDistance(m)                ; float max: another world
            float ex = m.GetPositionX() - x
            float ey = m.GetPositionY() - y
            float ez = m.GetPositionZ() - z
            if before > SameWorld || ex * ex + ey * ey > Tolerance * Tolerance || ez * ez > ZTolerance * ZTolerance
                m.Enable(False)
                m.MoveTo(player, x - px, y - py, z - pz, False, False)   ; no match-rotation: keep the record's
                moves += 1
                Trace("moved " + i + " to " + m.GetPositionX() + " " + m.GetPositionY() + " " + m.GetPositionZ() + " target " + x + " " + y + " " + z + " before=" + before + " d=" + player.GetDistance(m) + " moves=" + moves)
            endif
        endif
        i += 1
    endwhile
EndFunction

; In our world: the player's cell is one of the core's own cells (the runtime instance keeps the core's cell ids:
; docs/terrain/door-rounds.md), or the player is outdoors in the same world as when they last were (the generated
; land past our cells). Indoors keeps the last state, so a door out lands with the border already off.
Function Border(Actor player)
    if !BorderSignal || Markers.Length == 0 || Markers[0] == None
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
    Debug.TraceUser(LogName, "FO4SF_MAP rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
