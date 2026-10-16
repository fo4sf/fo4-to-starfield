Scriptname FO4SF_LoadDoor extends ObjectReference
{Experimental player-only travel. Properties use a plugin-local full-plugin ID,
 never a runtime load-order prefix. Record attachment and native acceptance required.}

string Property DestinationPlugin Auto
int Property DestinationId Auto
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
    akActionRef.MoveTo(destination, 0.0, 0.0, 0.0, True, False)
    ; Return from the native call is NOT a judged arrival or successful round trip.
    Debug.Trace("FO4SF_LoadDoor MoveTo returned")
    Moving = False
EndEvent
