Scriptname EncounterZone extends Form
{Pure-Papyrus Starfield adapter for Fallout 4's removed EncounterZone native form class, delegating zone queries and resets to a mapped Starfield Location.}

Location Property MappedLocation Auto

int Function CountActors(Keyword apRequiredLinkedRefKeyword = None, Keyword apExcludeLinkedRefKeyword = None)
    if MappedLocation != None
        return MappedLocation.CountActors(apRequiredLinkedRefKeyword, apExcludeLinkedRefKeyword)
    endif
    return 0
EndFunction

Actor[] Function GetActors(Keyword apRequiredLinkedRefKeyword = None, Keyword apExcludeLinkedRefKeyword = None)
    if MappedLocation != None
        return MappedLocation.GetActors(apRequiredLinkedRefKeyword, apExcludeLinkedRefKeyword)
    endif
    return new Actor[0]
EndFunction

Function Reset()
    if MappedLocation != None
        MappedLocation.Reset()
    endif
EndFunction
