Scriptname FO4SF_LoadDoor extends ObjectReference
{Experimental player-only travel. Properties use a plugin-local full-plugin ID,
 never a runtime load-order prefix. Record attachment and native acceptance required.}

string Property DestinationPlugin Auto
int Property DestinationId Auto
; Explicit opt-in: zero is a valid world coordinate, not an unset sentinel.
bool Property UseDestinationPosition = False Auto
float Property DestinationX Auto
float Property DestinationY Auto
float Property DestinationZ Auto
; A missed trip (the player still in the cell they activated from, with the engine's
; "BOUNDARY REACHED"; docs/terrain/border.md) is retried with the same MoveTo this many times, each after
; RetryWaitSeconds. 0 turns retries off.
int Property MoveRetries = 1 Auto
float Property RetryWaitSeconds = 0.5 Auto
; With UseDestinationPosition, the wait between the MoveTo and the SetPosition. The BOUNDARY REACHED popup pauses
; Papyrus, so whether the trace stops before or after phase=settled tells which step raised it (docs/terrain/border.md).
float Property SettleSeconds = 1.0 Auto
bool Moving = False

Event OnLoad()
    ; A saved interrupted activation must not permanently lock this reference.
    ; Loading a door alone never moves the player.
    Moving = False
EndEvent

Event OnActivate(ObjectReference akActionRef)
    if akActionRef != Game.GetPlayer() || Moving
        return
    endif
    if DestinationPlugin == "" || DestinationId <= 0 || DestinationId > 0x00FFFFFF
        Debug.Trace("FO4SF_LoadDoor refused: invalid destination properties")
        return
    endif
    ObjectReference destination = Game.GetFormFromFile(DestinationId, DestinationPlugin) as ObjectReference
    if destination == None || destination == Self
        Debug.Trace("FO4SF_LoadDoor refused: destination unavailable or self")
        return
    endif
    Moving = True
    Debug.Trace("FO4SF_LoadDoor requested " + DestinationPlugin + ":" + DestinationId)
    TracePosition("marker", destination)
    TracePosition("before_move", akActionRef)
    Cell origin = akActionRef.GetParentCell()
    akActionRef.MoveTo(destination, 0.0, 0.0, 0.0, True, False)
    ; Return from the native call is NOT a judged arrival or successful round trip.
    Debug.Trace("FO4SF_LoadDoor MoveTo returned")
    TracePosition("after_move", akActionRef)
    int retries = 0
    while retries < MoveRetries && !Arrived(akActionRef, destination, origin)
        Utility.Wait(RetryWaitSeconds)
        if !Arrived(akActionRef, destination, origin)
            retries += 1
            Debug.Trace("FO4SF_LoadDoor retry " + retries + " of " + MoveRetries)
            akActionRef.MoveTo(destination, 0.0, 0.0, 0.0, True, False)
            TracePosition("after_retry", akActionRef)
        endif
    endwhile
    if retries > 0 && !Arrived(akActionRef, destination, origin)
        Debug.Trace("FO4SF_LoadDoor retry gave up after " + retries)
    endif
    if UseDestinationPosition
        ; Experimental: the writer must supply this runtime instance's measured
        ; merged arrival, never a guessed or globally reused merge offset.
        ; MoveTo is void; completion alone cannot certify the target world.
        string requestedPosition = "FO4SF_LoadDoor requested_position=" + DestinationX + " " + DestinationY + " " + DestinationZ
        Debug.Trace(requestedPosition)
        Debug.TraceUser("fo4sf", requestedPosition)
        Utility.Wait(SettleSeconds)
        TracePosition("settled", akActionRef)
        akActionRef.SetPosition(DestinationX, DestinationY, DestinationZ)
        TracePosition("after_position", akActionRef)
    endif
    Moving = False
EndEvent

; The trip left the player's starting cell (an exterior door near a cell edge can be activated from the next cell, so
; not the door's). Compared by cell, not world: on an exterior trip the player's GetWorldSpace() may be the runtime
; instance (FF...) while the marker's is the core's WRLD (door-rounds.md, --world-instance). A destination in the
; starting cell counts as arrived. Not a judged arrival: the doors_out judge still decides.
bool Function Arrived(ObjectReference target, ObjectReference destination, Cell origin)
    return destination.GetParentCell() == origin || target.GetParentCell() != origin
EndFunction

Function TracePosition(string phase, ObjectReference target)
    string line = "FO4SF_LoadDoor phase=" + phase + " destination=" + DestinationPlugin + ":" + DestinationId
    line += " ref=" + target.GetFormID() + " pos=" + target.GetPositionX() + " " + target.GetPositionY() + " " + target.GetPositionZ()
    line += " angle=" + target.GetAngleZ() + " cell=" + target.GetParentCell() + " world=" + target.GetWorldSpace()
    Debug.Trace(line)
    Debug.TraceUser("fo4sf", line)
EndFunction
