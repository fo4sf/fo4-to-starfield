Scriptname FO4SF_AnimatedLoadDoor extends FO4SF_LoadDoor
{Experimental: a scripted load door that opens before the trip and is shut again behind the player.
 Attach to a DOOR reference whose base has an animation graph (load_door.anim, docs/spikes/load-door-animations.md).
 FO4SF_LoadDoor's travel and its properties are unchanged; this adds only the wait for the open animation.
 Not compiled or run yet: GetOpenState / SetOpen / Utility.Wait in Starfield's Papyrus are a PC read (check A3).}

; Seconds the door's Open clip takes (load_door.anim.open_seconds; FO4's Open sequence length). 0 or less: wait for the
; door's own open state only, at most MaxWaitSeconds.
float Property OpenSeconds = 0.0 Auto
float Property MaxWaitSeconds = 3.0 Auto
bool Busy = False

Event OnLoad()
    Busy = False
    Parent.OnLoad()
EndEvent

Event OnActivate(ObjectReference akActionRef)
    if akActionRef != Game.GetPlayer() || Busy
        return
    endif
    Busy = True
    ; The engine has already started this DOOR's open (or close, when it stood open) before OnActivate runs:
    ; GetOpenState 1 open, 2 opening, 3 closed, 4 closing (FO4's values).
    int openState = GetOpenState()
    if openState == 3 || openState == 4
        SetOpen(True)
    endif
    float waited = 0.0
    float limit = MaxWaitSeconds
    if OpenSeconds > 0.0 && OpenSeconds < limit
        limit = OpenSeconds + 0.25
    endif
    while GetOpenState() != 1 && waited < limit
        Utility.Wait(0.1)
        waited += 0.1
    endwhile
    Debug.Trace("FO4SF_AnimatedLoadDoor open_state=" + GetOpenState() + " waited=" + waited)
    Parent.OnActivate(akActionRef)
    ; Shut behind the player, so the door is closed when they come back; the player is already in the other cell.
    SetOpen(False)
    Busy = False
EndEvent
