Scriptname FO4SF_PipboyTravel Hidden
{Native-to-Papyrus fast-travel, live marker-discovery sync and multi-world travel bridge for the Pip-Boy MAP
 (docs/ui/pipboy-map-s1-s4.md, Slice 4). FO4SFPipboyMenu.dll syncs live engine ExtraMapMarker kDiscovered (0x20) bits
 into FO4SF_MapDisc00..13, writes the selected marker's local FormID, plugin code, store index and arrival coordinates
 into FO4SFPipboyTravel.esm's GLOB records on the main thread, and dispatches FO4SF_PipboyTravel.Go (0 args, slot 0x2F).}

Function TraceLine(string asMsg) global
    Debug.OpenUserLog("FO4SF_PipboyTravel")
    Debug.TraceUser("FO4SF_PipboyTravel", asMsg)
EndFunction

GlobalVariable Function TravelGlobal(int aiLocalId) global
    return Game.GetFormFromFile(aiLocalId, "FO4SFPipboyTravel.esm") as GlobalVariable
EndFunction

string Function PluginNameForCode(int aiPluginCode) global
    if aiPluginCode == 1
        return "FO4TerrainCore.esm"
    elseif aiPluginCode == 2
        return "FO4CapitalWasteland.esm"
    elseif aiPluginCode == 3
        return "FO4Mojave.esm"
    elseif aiPluginCode == 4
        return "FO4Appalachia.esm"
    endif
    return "FO4SFMapMarkers.esm"
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

Function SyncMarkerDiscovered(ObjectReference akMarker, int aiMarkerIndex) global
    if akMarker != None
        akMarker.SetMarkerDiscovered()
    endif
    MarkBitDiscovered(aiMarkerIndex)
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
    GlobalVariable gSurv = Game.GetFormFromFile(0x000841, "FO4SFCoreValues.esm") as GlobalVariable
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

    string pluginName = PluginNameForCode(pluginCode)

    ObjectReference dest = Game.GetFormFromFile(targetId, pluginName) as ObjectReference
    if dest == None
        TraceLine("step=go idx=" + storeIdx + " plugin=" + pluginName + " id=" + targetId + " result=dest_not_found")
        return
    endif

    ; Native CollectMainThreadState syncs live ExtraMapMarker kDiscovered (0x20) + init_disc into FO4SF_MapDisc00..13
    ; before dispatching Go(), so native and Papyrus agree on the exact same discovery bitset (FNAM 0x03/0x13 sets
    ; Visible/CanTravelTo on undiscovered markers, so IsMapMarkerVisible/CanFastTravelToMarker must not bypass discovery).
    bool canTravel = IsBitDiscovered(storeIdx)
    if !canTravel
        TraceLine("step=go idx=" + storeIdx + " id=" + targetId + " result=not_discovered")
        return
    endif

    WorldSpace startWorld = player.GetWorldSpace()
    float startX = player.GetPositionX()
    float startY = player.GetPositionY()
    float dx0 = arrX - startX
    float dy0 = arrY - startY
    float tripMetres = Math.Sqrt(dx0 * dx0 + dy0 * dy0)
    bool hasExplicitArrival = (arrX != 0.0 || arrY != 0.0 || arrZ != 0.0)
    bool crossWorld = pluginCode >= 2

    GlobalVariable gDays = Game.GetFormFromFile(0x000039, "Starfield.esm") as GlobalVariable
    float daysBefore = 0.0
    if gDays != None
        daysBefore = gDays.GetValue()
    endif

    bool usedFallback = False
    if engineEnabled && !crossWorld
        Game.FastTravel(dest)
        Utility.Wait(0.25)
    endif

    float dxAfter = player.GetPositionX() - arrX
    float dyAfter = player.GetPositionY() - arrY
    float remDist = Math.Sqrt(dxAfter * dxAfter + dyAfter * dyAfter)

    ; Merged runtime world or cross-worldspace travel (normal loading fade, never opening Starfield's star map)
    if crossWorld || (hasExplicitArrival && remDist > 75.0) || (!hasExplicitArrival && player.GetWorldSpace() == startWorld && player.GetDistance(dest) > 75.0)
        usedFallback = True
        Game.FadeOutGame(True, True, 0.0, 0.35, True)
        Utility.Wait(0.35)
        if tripMetres > 1.0
            AdvanceTravelClock(tripMetres)
        endif
        player.MoveTo(dest, 0.0, 0.0, 0.0, !hasExplicitArrival, False)
        player.WaitFor3DLoad()
        Utility.Wait(0.15)
        if hasExplicitArrival
            player.SetPosition(arrX, arrY, arrZ)
            player.SetAngle(0.0, 0.0, arrH)
        endif
        Game.FadeOutGame(False, True, 0.15, 0.45, False)
    elseif tripMetres > 1.0 && (gDays == None || (gDays.GetValue() - daysBefore) < 0.001)
        AdvanceTravelClock(tripMetres)
    endif

    SQ_FollowersScript followers = SQ_FollowersScript.GetScript()
    if followers != None
        followers.TeleportFollowers(player, None, True, False, False, False, False)
    endif

    SyncMarkerDiscovered(dest, storeIdx)
    TraceLine("step=go idx=" + storeIdx + " plugin=" + pluginName + " id=" + targetId + " enabled=" + engineEnabled + " cross_world=" + crossWorld + " fallback=" + usedFallback + " px=" + player.GetPositionX() + " py=" + player.GetPositionY() + " pz=" + player.GetPositionZ())
EndFunction
