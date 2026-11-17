Scriptname FO4SF_Shim_PowerArmor Hidden
{Pure-Papyrus Starfield shim library for Fallout 4 Actor.IsInPowerArmor.}

bool Function IsInPowerArmor(Actor akActor) Global
    if akActor == None
        return false
    endif
    Perk paPerk = Game.GetFormFromFile(0x0001F8A9, "FO4SFPowerArmor.esm") as Perk
    if paPerk != None && akActor.HasPerk(paPerk)
        return true
    endif
    Keyword paKeyword = Game.GetFormFromFile(0x0004D8A1, "FO4Port.esm") as Keyword
    if paKeyword != None && akActor.WornHasKeyword(paKeyword)
        return true
    endif
    return false
EndFunction
