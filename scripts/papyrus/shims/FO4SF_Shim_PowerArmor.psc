Scriptname FO4SF_Shim_PowerArmor Hidden
{Pure-Papyrus Starfield shim library for Fallout 4 Actor.IsInPowerArmor.}

bool Function IsInPowerArmor(Actor akActor) Global
    if akActor == None
        return false
    endif
    ActorValue paAv = Game.GetFormFromFile(0x00080A, "FO4SFPowerArmor.esm") as ActorValue
    if paAv != None && akActor.GetValue(paAv) >= 1.0
        return true
    endif
    Keyword paKeyword = Game.GetFormFromFile(0x0004D8A1, "FO4Port.esm") as Keyword
    if paKeyword != None && akActor.WornHasKeyword(paKeyword)
        return true
    endif
    return false
EndFunction
