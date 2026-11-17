Scriptname FO4SF_Shim_SurvivalRad Hidden
{Pure-Papyrus Starfield shim library for Fallout 4 survival, cannibalism, and magic-effect skill helpers.}

Function StartCannibal(Actor akActor, Actor akTarget) Global
    if akActor == None || akTarget == None
        return
    endif
    ActorValue healthAV = Game.GetFormFromFile(0x000002D4, "Starfield.esm") as ActorValue
    if healthAV != None
        akActor.RestoreValue(healthAV, 25.0)
    endif
EndFunction

string Function GetAssociatedSkill(MagicEffect akEffect) Global
    return ""
EndFunction
