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
    akActionRef.MoveTo(destination, 0.0, 0.0, 0.0, True, False)
    ; Return from the native call is NOT a judged arrival or successful round trip.
    Debug.Trace("FO4SF_LoadDoor MoveTo returned")
    TracePosition("after_move", akActionRef)
    if UseDestinationPosition
        ; Experimental: the writer must supply this runtime instance's measured
        ; merged arrival, never a guessed or globally reused merge offset.
        ; MoveTo is void; completion alone cannot certify the target world.
        Debug.TraceUser("fo4sf", "FO4SF_LoadDoor requested_position=" + DestinationX + " " + DestinationY + " " + DestinationZ)
        akActionRef.SetPosition(DestinationX, DestinationY, DestinationZ)
        TracePosition("after_position", akActionRef)
    endif
    Moving = False
EndEvent

Function TracePosition(string phase, ObjectReference target)
    string line = "FO4SF_LoadDoor phase=" + phase + " destination=" + DestinationPlugin + ":" + DestinationId
    line += " ref=" + target.GetFormID() + " pos=" + target.GetPositionX() + " " + target.GetPositionY() + " " + target.GetPositionZ()
    line += " angle=" + target.GetAngleZ() + " cell=" + target.GetParentCell() + " world=" + target.GetWorldSpace()
    Debug.Trace(line)
    Debug.TraceUser("fo4sf", line)
EndFunction
