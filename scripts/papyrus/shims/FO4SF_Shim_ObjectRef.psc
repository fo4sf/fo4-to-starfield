Scriptname FO4SF_Shim_ObjectRef Hidden
{Pure-Papyrus Starfield shim library for Fallout 4 ObjectReference functions: PlaceActorAtMe with EncounterZone, SetMotionType abAllowActivate, getLinkedRefArray, SellItem, DeleteWhenAble, and GetEncounterZone.}

Actor Function PlaceActorAtMe(ObjectReference akRef, ActorBase akActorToPlace, int aiLevelMod = 4, Form akZoneOrLoc = None) Global
    if akRef == None || akActorToPlace == None
        return None
    endif
    Location encLoc = akZoneOrLoc as Location
    if encLoc == None && (akZoneOrLoc as EncounterZone) != None
        encLoc = (akZoneOrLoc as EncounterZone).MappedLocation
    endif
    return akRef.PlaceActorAtMe(akActorToPlace, aiLevelMod, encLoc)
EndFunction

Function SetMotionType(ObjectReference akRef, int aeMotionType, bool abAllowActivate = true) Global
    if akRef == None
        return
    endif
    akRef.SetMotionType(aeMotionType, true)
    akRef.BlockActivation(!abAllowActivate, false)
EndFunction

ObjectReference[] Function GetLinkedRefArray(ObjectReference akRef, Keyword keywordLink = None) Global
    if akRef == None
        return new ObjectReference[0]
    endif
    int chainCount = akRef.CountLinkedRefChain(keywordLink, 100)
    if chainCount > 0
        ObjectReference[] outChain = new ObjectReference[chainCount]
        int i = 0
        while i < chainCount
            outChain[i] = akRef.GetNthLinkedRef(i + 1, keywordLink)
            i += 1
        endwhile
        return outChain
    endif
    return FO4SF_NativeBridge.GetLinkedRefChildren(akRef, keywordLink)
EndFunction

int Function SellItem(ObjectReference akSeller, Form Item, int Value, int amountToSell = -1, bool silent = false, Form paymentItem = None, ObjectReference PaymentContainer = None) Global
    if akSeller == None || Item == None
        return 0
    endif
    int held = akSeller.GetItemCount(Item)
    if held <= 0
        return 0
    endif
    int toSell = amountToSell
    if toSell < 0 || toSell > held
        toSell = held
    endif
    akSeller.RemoveItem(Item, toSell, silent, None)
    Form currency = paymentItem
    if currency == None
        currency = Game.GetFormFromFile(0x0000000F, "Starfield.esm")
    endif
    ObjectReference receiver = PaymentContainer
    if receiver == None
        receiver = akSeller
    endif
    int earned = toSell * Value
    if currency != None && earned > 0
        receiver.AddItem(currency, earned, silent)
    endif
    return earned
EndFunction

Function DeleteWhenAble(ObjectReference akRef) Global
    if akRef != None
        akRef.DisableNoWait()
        akRef.Delete()
    endif
EndFunction

EncounterZone Function GetEncounterZone(ObjectReference akRef) Global
    return None
EndFunction
