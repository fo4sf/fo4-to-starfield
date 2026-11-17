Scriptname FO4SF_ActivateChain extends ObjectReference
{Converter interactive-fidelity activation chain (XAPD / XAPR translation).
 Drives one or more linked target references with optional per-target delays,
 and enforces ParentActivateOnly on child references when flagged.}

bool Property ParentActivateOnly = False Auto Const
ObjectReference[] Property Targets Auto Const
float[] Property Delays Auto Const
bool[] Property UnblockTargets Auto Const

bool Busy = False

Event OnInit()
    ApplyChildRule()
EndEvent

Event OnCellAttach()
    ApplyChildRule()
EndEvent

Event OnLoad()
    ; Clear any saved mid-chain guard so reloading a save never leaves a switch stuck.
    Busy = False
    ApplyChildRule()
EndEvent

Function ApplyChildRule()
    if ParentActivateOnly
        Self.BlockActivation(True, False)
    endif
EndFunction

Event OnActivate(ObjectReference akActionRef)
    if Busy || Targets == None || Targets.Length == 0
        return
    endif
    Busy = True
    int i = 0
    while i < Targets.Length
        ObjectReference target = Targets[i]
        float waitSeconds = 0.0
        if Delays != None && i < Delays.Length
            waitSeconds = Delays[i]
        endif
        bool unblock = False
        if UnblockTargets != None && i < UnblockTargets.Length
            unblock = UnblockTargets[i]
        endif
        if waitSeconds > 0.0
            Utility.Wait(waitSeconds)
        endif
        if target != None && target != Self
            if unblock
                target.BlockActivation(False, False)
                target.Activate(akActionRef, False)
                target.BlockActivation(True, False)
            else
                target.Activate(akActionRef, False)
            endif
        endif
        i += 1
    endwhile
    Busy = False
EndEvent
