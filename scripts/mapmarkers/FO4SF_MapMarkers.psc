Scriptname FO4SF_MapMarkers extends Quest
{Puts the Commonwealth's map markers into the world the player walks in (fo4-to-starfield, docs/terrain/map-markers.md
 "Markers in the merged world"). The markers are persistent references of FO4TerrainCore.esm's overlay world, and a
 persistent reference of that world stays at its LOCAL position in the base world (door probe (a), 16 Oct; the
 mission's actors, 18 Oct), while the player walks in a world made at run time (FF0054C8 in the mission log) that
 places the core's records at local + the merge offset: no icon showed (owner, 19 Oct, v6). Every Interval seconds,
 with the player outdoors inside the overlay's merged extent, each marker that is not at its merged spot in the
 player's world is enabled and moved there (MoveTo onto the player with the difference as the offset, the form
 FO4SF_LoadDoor and the mission's Relocate use). Every move goes to the user log "fo4sf_map"
 (My Games\Starfield\Logs\Script\User\fo4sf_map.0.log).}

ObjectReference[] Property Markers Auto Const Mandatory
{The core's MapMarker references (dotnet/MapMarkers fills them from the core plugin).}

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
{A marker within this many units of its merged spot, in the player's world, counts as placed.}

float Property SameWorld = 100000.0 Auto Const
{GetDistance above this means the marker is in another world (it reads float max there, 18 Oct).}

float Property Interval = 2.0 Auto Const

int Property MaxMoves = 40 Auto Const
{Stop moving after this many moves in one session (a move that never lands would otherwise repeat every Interval).}

string LogName = "fo4sf_map"
int moves = 0

Event OnInit()
    Debug.OpenUserLog(LogName)
    Trace("init markers=" + Markers.Length)
    StartTimer(Interval, 1)
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID == 1
        Place(Game.GetPlayer())
        StartTimer(Interval, 1)
    endif
EndEvent

Function Place(Actor player)
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
            if before > SameWorld || ex * ex + ey * ey > Tolerance * Tolerance
                m.Enable(False)
                m.MoveTo(player, x - px, y - py, z - pz, True, False)
                moves += 1
                Trace("moved " + i + " to " + m.GetPositionX() + " " + m.GetPositionY() + " " + m.GetPositionZ() + " target " + x + " " + y + " " + z + " before=" + before + " d=" + player.GetDistance(m) + " moves=" + moves)
            endif
        endif
        i += 1
    endwhile
EndFunction

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MAP rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
