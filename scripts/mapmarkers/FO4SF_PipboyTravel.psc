Scriptname FO4SF_PipboyTravel Hidden
{Native-to-Papyrus fast-travel and 24-bit marker-discovery bridge for the Pip-Boy MAP (docs/ui/pipboy-map-s1-s4.md,
 Slice 4). FO4SFPipboyMenu.dll writes the selected marker's local FormID, plugin code, store index and merged arrival
 coordinates into FO4SFPipboyTravel.esm's GLOB records at +0x48 on the main thread, then dispatches FO4SF_PipboyTravel.Go
 with zero arguments (IVirtualMachine::DispatchStaticCall slot 0x2F).}

Function TraceLine(string asMsg) global
    Debug.OpenUserLog("FO4SF_PipboyTravel")
    Debug.TraceUser("FO4SF_PipboyTravel", asMsg)
EndFunction

GlobalVariable Function TravelGlobal(int aiLocalId) global
    return Game.GetFormFromFile(aiLocalId, "FO4SFPipboyTravel.esm") as GlobalVariable
EndFunction

int Function BitScale(int aiBitIndex) global
    int scale = 1
    int k = 0
    while k < aiBitIndex
        scale = scale * 2
        k += 1
    endwhile
    return scale
EndFunction

bool Function IsBitDiscovered(int aiMarkerIndex) global
    if aiMarkerIndex < 0
        return False
    endif
    int groupIdx = aiMarkerIndex / 24
    int bitIdx = aiMarkerIndex % 24
    if groupIdx >= 14
        return False
    endif
    GlobalVariable discGlob = TravelGlobal(0x810 + groupIdx)
    if discGlob == None
        return False
    endif
    int scale = BitScale(bitIdx)
    int raw = discGlob.GetValueInt()
    return ((raw / scale) % 2) != 0
EndFunction

Function MarkBitDiscovered(int aiMarkerIndex) global
    if aiMarkerIndex < 0
        return
    endif
    int groupIdx = aiMarkerIndex / 24
    int bitIdx = aiMarkerIndex % 24
    if groupIdx >= 14
        return
    endif
    GlobalVariable discGlob = TravelGlobal(0x810 + groupIdx)
    if discGlob == None
        return
    endif
    int scale = BitScale(bitIdx)
    int raw = discGlob.GetValueInt()
    if ((raw / scale) % 2) == 0
        int updated = raw + scale
        discGlob.SetValue(updated as float)
    endif
EndFunction

Function AdvanceTravelClock(float afDistanceMetres) global
    if afDistanceMetres <= 1.0
        return
    endif
    ; ~4.0 m/s overland walking pace -> game hours elapsed (20x timescale equivalent)
    float hours = (afDistanceMetres / 4.0) * 20.0 / 3600.0
    if hours < 0.05
        hours = 0.05
    elseif hours > 12.0
        hours = 12.0
    endif
    GlobalVariable gHour = Game.GetFormFromFile(0x000038, "Starfield.esm") as GlobalVariable
    GlobalVariable gDays = Game.GetFormFromFile(0x000039, "Starfield.esm") as GlobalVariable
    if gHour != None
        float nextHour = gHour.GetValue() + hours
        while nextHour >= 24.0
            nextHour -= 24.0
        endwhile
        gHour.SetValue(nextHour)
    endif
    if gDays != None
        gDays.SetValue(gDays.GetValue() + (hours / 24.0))
    endif
EndFunction

Function Go() global
    Actor player = Game.GetPlayer()
    if player == None
        TraceLine("step=go result=no_player")
        return
    endif

    GlobalVariable gTarget = TravelGlobal(0x800)
    GlobalVariable gPlugin = TravelGlobal(0x801)
    GlobalVariable gSurv = TravelGlobal(0x802)
    GlobalVariable gIdx = TravelGlobal(0x803)
    GlobalVariable gX = TravelGlobal(0x804)
    GlobalVariable gY = TravelGlobal(0x805)
    GlobalVariable gZ = TravelGlobal(0x806)
    GlobalVariable gH = TravelGlobal(0x807)

    if gTarget == None || gPlugin == None || gIdx == None
        TraceLine("step=go result=missing_globals")
        return
    endif

    if gSurv != None && gSurv.GetValue() >= 0.5
        TraceLine("step=go result=survival_blocked")
        return
    endif

    if player.IsInCombat()
        TraceLine("step=go result=in_combat")
        return
    endif

    bool engineEnabled = Game.IsFastTravelEnabled()
    int targetId = gTarget.GetValueInt()
    int pluginCode = gPlugin.GetValueInt()
    int storeIdx = gIdx.GetValueInt()
    float arrX = 0.0
    float arrY = 0.0
    float arrZ = 0.0
    float arrH = 0.0
    if gX != None && gY != None && gZ != None && gH != None
        arrX = gX.GetValue()
        arrY = gY.GetValue()
        arrZ = gZ.GetValue()
        arrH = gH.GetValue()
    endif

    string pluginName = "FO4SFMapMarkers.esm"
    if pluginCode == 1
        pluginName = "FO4TerrainCore.esm"
    endif

    ObjectReference dest = Game.GetFormFromFile(targetId, pluginName) as ObjectReference
    if dest == None
        TraceLine("step=go idx=" + storeIdx + " plugin=" + pluginName + " id=" + targetId + " result=dest_not_found")
        return
    endif

    bool canTravel = dest.CanFastTravelToMarker() || dest.IsMapMarkerVisible() || IsBitDiscovered(storeIdx)
    if !canTravel
        TraceLine("step=go idx=" + storeIdx + " id=" + targetId + " result=not_discovered")
        return
    endif

    float startX = player.GetPositionX()
    float startY = player.GetPositionY()
    float dx0 = arrX - startX
    float dy0 = arrY - startY
    float tripMetres = Math.Sqrt(dx0 * dx0 + dy0 * dy0)

    bool usedFallback = False
    if engineEnabled
        Game.FastTravel(dest)
        Utility.Wait(0.25)
    endif

    float dxAfter = player.GetPositionX() - arrX
    float dyAfter = player.GetPositionY() - arrY
    float remDist = Math.Sqrt(dxAfter * dxAfter + dyAfter * dyAfter)

    ; Merged runtime world fallback when Game.FastTravel is a no-op on runtime-relocated markers
    if remDist > 75.0 && (arrX != 0.0 || arrY != 0.0 || arrZ != 0.0)
        usedFallback = True
        Game.FadeOutGame(True, True, 0.0, 0.35, True)
        Utility.Wait(0.35)
        AdvanceTravelClock(tripMetres)
        player.MoveTo(dest, 0.0, 0.0, 0.0, False, False)
        Utility.Wait(0.15)
        player.SetPosition(arrX, arrY, arrZ)
        player.SetAngle(0.0, 0.0, arrH)
        SQ_FollowersScript followers = SQ_FollowersScript.GetScript()
        if followers != None
            followers.TeleportFollowers(player, None, True, False, False, False, False)
        endif
        Game.FadeOutGame(False, True, 0.15, 0.45, False)
    endif

    dest.SetMarkerDiscovered()
    MarkBitDiscovered(storeIdx)
    TraceLine("step=go idx=" + storeIdx + " plugin=" + pluginName + " id=" + targetId + " enabled=" + engineEnabled + " fallback=" + usedFallback + " px=" + player.GetPositionX() + " py=" + player.GetPositionY() + " pz=" + player.GetPositionZ())
EndFunction
