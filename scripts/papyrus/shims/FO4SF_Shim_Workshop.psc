Scriptname FO4SF_Shim_Workshop Hidden
{Pure-Papyrus Starfield shim library for Fallout 4 workshop radio receivers, resource recalculation, settlement picker menus, and Component->Resource breakdown helpers.}

Function MakeRadioReceiver(ObjectReference akRef, float afFrequency, float afVolume = 1.0, OutputModel aOverrideModel = None, bool abActive = true, bool abNoStatic = false) Global
    if akRef == None
        return
    endif
    akRef.SetRadioFrequency(afFrequency)
    akRef.SetRadioVolume(afVolume)
    akRef.SetRadioOn(abActive)
EndFunction

Function RecalculateResources(ObjectReference akWorkshop) Global
EndFunction

Function WaitForWorkshopResourceRecalc(ObjectReference akWorkshop) Global
EndFunction

Location Function OpenWorkshopSettlementMenu(ObjectReference akRef, Keyword akActionKW, Message astrConfirm = None, Location aLocToHighlight = None) Global
    if akRef != None
        return akRef.GetCurrentLocation()
    endif
    return aLocToHighlight
EndFunction

Location Function OpenWorkshopSettlementMenuEx(ObjectReference akRef, Keyword akActionKW, Message astrConfirm = None, Location aLocToHighlight = None, FormList akIncludeKeywordList = None, FormList akExcludeKeywordList = None, bool abExcludeZeroPopulation = false, bool abOnlyOwnedWorkshops = true, bool abTurnOffHeader = false, bool abOnlyPotentialVassalSettlements = false, bool abDisableReservedByQuests = false) Global
    if akRef != None
        return akRef.GetCurrentLocation()
    endif
    return aLocToHighlight
EndFunction

int Function GetObjectComponentCount(MiscObject akItem, Component akComponent) Global
    if akItem != None && akComponent != None && akComponent.MappedResource != None
        return akItem.GetObjectResourceCount(akComponent.MappedResource)
    endif
    return 0
EndFunction

int Function RemoveComponents(ObjectReference akContainer, Component akComponent, int aiCount, bool abSilent = false) Global
    if akContainer != None && akComponent != None && akComponent.MappedResource != None
        return akContainer.RemoveResources(akComponent.MappedResource, aiCount, abSilent)
    endif
    return 0
EndFunction
