Scriptname FO4SF_WorkshopCoreQuest extends Quest
{Core Settlements, Junk Scrapping (CMPO -> IRES), Bench Recipes (FO4 COBJ + FNV RCPE), and Portable C.A.M.P.s
 (docs/workshop/workshop-camps.md). Attached to QUST FO4SF_WorkshopCoreQuest (0x000800 of FO4SFWorkshop.esm):
 StartGameEnabled, 0 properties (all base forms resolved via Game.GetFormFromFile so FO4SFWorkshop.esm masters
 Starfield.esm only and never overrides a core cell; persistent ObjectReference[] arrays live in quest state so
 placed settlement workbenches, portable C.A.M.P. beacons, and built crafting stations persist across save-quit-reload).

 Stages:
   5   By-hand starter bundle (1 Settlement Kit, 1 Portable C.A.M.P. Kit, 1 Pack-Up Token, 1 Scrapper Kit, 4x each FO4 junk)
   10  Place persistent settlement workbench 2.5 m ahead (+3.0 m lateral offset if a C.A.M.P. beacon is already at 2.5 m)
   15  Deploy persistent Portable C.A.M.P. beacon (OutpostBeaconActivator 0x2C60E9) 2.5 m ahead + verify 45 m exclusion block & refund
   20  Give 4x each FO4 junk item (DeskFan, DuctTape, HotPlate, TinCan) and run deterministic CMPO -> IRES -> MISC scrapping
   30  Audit all 18 CMPO -> IRES -> MISC mappings and all 8 FO4 COBJ + FNV RCPE bench recipes + component availability
   40  Pack up / relocate active Portable C.A.M.P. beacon back into FO4SF_CAMPKit
   50  Explicit post-reload / world persistence audit of tracked settlement benches, C.A.M.P. beacons, and built stations
   60  Full cleanup (Disable + Delete all script-spawned benches and beacons, reset counters)

 User log: My Games\Starfield\Logs\Script\User\FO4SFWorkshopCore.0.log
 Format:   FO4SFWSCORE rt=<real time s> <event> key=value ... end=true}

; ---------------------------------------------------------------- deterministic layout (dotnet/WorkshopCore/Program.cs)

int Version = 1
string LogName = "FO4SFWorkshopCore"
string WorkshopPlugin = "FO4SFWorkshop.esm"
string CorePlugin = "FO4TerrainCore.esm"
string CorePlugin2 = "FO4TerrainCore_Mars.esm"

; Own local FormIDs in FO4SFWorkshop.esm
int CampExclGlobId = 0x000801
int ActiveCampGlobId = 0x000802
int TrackedWsGlobId = 0x000803
int TrackedStGlobId = 0x000804

int CampKitId = 0x000810
int CampPackTokenId = 0x000811
int SettlementKitId = 0x000812

int CmpoIresListId = 0x000818
int CmpoMiscListId = 0x000819
int ScrapJunkListId = 0x00081A
int ScrapTokenId = 0x00081B
int BenchRecipesListId = 0x00081C
int KitFilterListId = 0x00081D

int JunkDeskFanId = 0x000820
int JunkDuctTapeId = 0x000821
int JunkHotPlateId = 0x000822
int JunkTinCanId = 0x000823

; Vanilla Starfield.esm & Terrain Core runtime FormIDs
int CoreBenchBaseId = 0x0A2ECD      ; FO4Core_wkshp_0c1aeb_fallout4 in FO4TerrainCore.esm
int FallbackBenchId = 0x1F50AD      ; Starfield.esm FURN WorkbenchIndustrial (standalone fallback when terrain core is absent)
int BeaconBaseId = 0x2C60E9         ; Starfield.esm ACTI OutpostBeaconActivator
int WorkshopKwId = 0x054BA7         ; Starfield.esm KYWD WorkshopKeyword
int StationFurnKwId = 0x01A21C      ; Starfield.esm KYWD AnimFurnWorkbench (present on all 6 outpost crafting stations)

float AheadM = 2.5
float SideOffsetM = 3.5
float StationScanRadiusM = 85.0

; ---------------------------------------------------------------- persistent quest state (saved in .sfs)

int TIMER_POLL = 1
int TIMER_RELOAD_SETTLE = 2
int TIMER_ARRIVE_SETTLE = 3
float POLL_S = 1.0

int[] StageList
bool[] DoneList

ObjectReference[] TrackedWorkshops
ObjectReference[] TrackedBeacons
ObjectReference[] TrackedStations

Cell LastPlayerCell = None
int ReloadCount = 0
bool CleanupDone = false

; ---------------------------------------------------------------- lifecycle & logging

Event OnInit()
    Debug.OpenUserLog(LogName)
    InitArrays()
    Actor playerRef = Game.GetPlayer()
    SetupHooks(playerRef)
    FormList iresList = GetOwnFormList(CmpoIresListId)
    FormList miscList = GetOwnFormList(CmpoMiscListId)
    FormList recList = GetOwnFormList(BenchRecipesListId)
    int iresN = ListSize(iresList)
    int miscN = ListSize(miscList)
    int recN = ListSize(recList)
    Trace("init version=" + Version + " quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(WorkshopPlugin) + " core=" + ActiveCoreName() + " benchbase=" + Id(ResolveBenchBase()) + " beaconbase=" + Id(Game.GetFormFromFile(BeaconBaseId, "Starfield.esm")) + " workshopkw=" + Id(Game.GetFormFromFile(WorkshopKwId, "Starfield.esm")) + " stationkw=" + Id(Game.GetFormFromFile(StationFurnKwId, "Starfield.esm")) + " cmpo_ires=" + iresN + " cmpo_misc=" + miscN + " recipes=" + recN)
    if playerRef != None
        LastPlayerCell = playerRef.GetParentCell()
    endif
    SyncGlobals()
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Function InitArrays()
    if StageList == None || StageList.Length != 7
        StageList = new int[7]
        DoneList = new bool[7]
        StageList[0] = 5
        StageList[1] = 10
        StageList[2] = 15
        StageList[3] = 20
        StageList[4] = 30
        StageList[5] = 40
        StageList[6] = 50
    endif
    if TrackedWorkshops == None
        TrackedWorkshops = new ObjectReference[0]
    endif
    if TrackedBeacons == None
        TrackedBeacons = new ObjectReference[0]
    endif
    if TrackedStations == None
        TrackedStations = new ObjectReference[0]
    endif
EndFunction

Function SetupHooks(Actor playerRef)
    if playerRef == None
        return
    endif
    RemoveAllInventoryEventFilters()
    Form filterForm = Game.GetFormFromFile(KitFilterListId, WorkshopPlugin)
    if filterForm != None
        AddInventoryEventFilter(filterForm)
    endif
    RegisterForRemoteEvent(playerRef, "OnPlayerLoadGame")
    RegisterForRemoteEvent(playerRef as ObjectReference, "OnItemRemoved")
    RebindWorkshopEvents()
EndFunction

Function RebindWorkshopEvents()
    int i = 0
    while i < TrackedWorkshops.Length
        ObjectReference wsRef = TrackedWorkshops[i]
        if wsRef != None && !wsRef.IsDeleted()
            RegisterForRemoteEvent(wsRef, "OnWorkshopObjectPlaced")
            RegisterForRemoteEvent(wsRef, "OnWorkshopObjectRemoved")
            RegisterForRemoteEvent(wsRef, "OnWorkshopMode")
        endif
        i += 1
    endwhile
    int j = 0
    while j < TrackedBeacons.Length
        ObjectReference bcRef = TrackedBeacons[j]
        if bcRef != None && !bcRef.IsDeleted()
            RegisterForRemoteEvent(bcRef, "OnWorkshopObjectPlaced")
            RegisterForRemoteEvent(bcRef, "OnWorkshopObjectRemoved")
            RegisterForRemoteEvent(bcRef, "OnWorkshopMode")
        endif
        j += 1
    endwhile
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    InitArrays()
    ReloadCount += 1
    Actor playerRef = Game.GetPlayer()
    SetupHooks(playerRef)
    ScanNearbyBuiltStations(playerRef)
    AuditPersistence("reload")
    StartTimer(2.0, TIMER_RELOAD_SETTLE)
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Function Trace(string msg)
    string line = "FO4SFWSCORE rt=" + Utility.GetCurrentRealTime() + " " + msg + " end=true"
    if !Debug.TraceUser(LogName, line)
        Debug.OpenUserLog(LogName)
        Debug.TraceUser(LogName, line)
    endif
EndFunction

Function Say(string msg)
    Debug.Notification(msg)
    Trace("say text=" + msg)
EndFunction

string Function Id(Form baseForm)
    if baseForm == None
        return "none"
    endif
    return "" + baseForm.GetFormID()
EndFunction

FormList Function GetOwnFormList(int localId)
    return Game.GetFormFromFile(localId, WorkshopPlugin) as FormList
EndFunction

GlobalVariable Function GetOwnGlobal(int localId)
    return Game.GetFormFromFile(localId, WorkshopPlugin) as GlobalVariable
EndFunction

int Function ListSize(FormList flstObj)
    if flstObj == None
        return 0
    endif
    return flstObj.GetSize()
EndFunction

string Function ActiveCoreName()
    if Game.IsPluginInstalled(CorePlugin)
        return CorePlugin
    endif
    if Game.IsPluginInstalled(CorePlugin2)
        return CorePlugin2
    endif
    return "standalone"
EndFunction

Form Function ResolveBenchBase()
    string cName = ActiveCoreName()
    if cName != "standalone"
        Form coreBench = Game.GetFormFromFile(CoreBenchBaseId, cName)
        if coreBench != None
            return coreBench
        endif
    endif
    return Game.GetFormFromFile(FallbackBenchId, "Starfield.esm")
EndFunction

float Function GetExclusionRadius()
    GlobalVariable gExcl = GetOwnGlobal(CampExclGlobId)
    if gExcl == None
        return 45.0
    endif
    return gExcl.GetValue()
EndFunction

Function SyncGlobals()
    PruneDeadRefs()
    GlobalVariable gCamp = GetOwnGlobal(ActiveCampGlobId)
    if gCamp != None
        gCamp.SetValue(TrackedBeacons.Length as float)
    endif
    GlobalVariable gWs = GetOwnGlobal(TrackedWsGlobId)
    if gWs != None
        gWs.SetValue(TrackedWorkshops.Length as float)
    endif
    GlobalVariable gSt = GetOwnGlobal(TrackedStGlobId)
    if gSt != None
        gSt.SetValue(TrackedStations.Length as float)
    endif
EndFunction

Function PruneDeadRefs()
    int i = TrackedWorkshops.Length - 1
    while i >= 0
        ObjectReference r = TrackedWorkshops[i]
        if r == None || r.IsDeleted()
            TrackedWorkshops.Remove(i)
        endif
        i -= 1
    endwhile
    int j = TrackedBeacons.Length - 1
    while j >= 0
        ObjectReference b = TrackedBeacons[j]
        if b == None || b.IsDeleted()
            TrackedBeacons.Remove(j)
        endif
        j -= 1
    endwhile
    int k = TrackedStations.Length - 1
    while k >= 0
        ObjectReference s = TrackedStations[k]
        if s == None || s.IsDeleted()
            TrackedStations.Remove(k)
        endif
        k -= 1
    endwhile
EndFunction

string Function HasWorkshopKeywordStr(ObjectReference targetRef)
    Keyword kwObj = Game.GetFormFromFile(WorkshopKwId, "Starfield.esm") as Keyword
    if kwObj == None || targetRef == None
        return "false"
    endif
    return "" + targetRef.HasKeyword(kwObj)
EndFunction

; ---------------------------------------------------------------- workshop build-mode tracking

Event ObjectReference.OnWorkshopMode(ObjectReference akSender, bool aStart)
    Actor playerRef = Game.GetPlayer()
    if !aStart && playerRef != None
        ScanNearbyBuiltStations(playerRef)
        SyncGlobals()
    endif
EndEvent

Event ObjectReference.OnWorkshopObjectPlaced(ObjectReference akSender, ObjectReference akReference)
    if akReference == None
        return
    endif
    if TrackedStations.Find(akReference) < 0
        TrackedStations.Add(akReference)
    endif
    SyncGlobals()
    Trace("station_placed ref=" + Id(akReference) + " base=" + Id(akReference.GetBaseObject()) + " workshop=" + Id(akSender) + " loaded=" + akReference.Is3DLoaded() + " count=" + TrackedStations.Length)
EndEvent

Event ObjectReference.OnWorkshopObjectRemoved(ObjectReference akSender, ObjectReference akReference)
    if akReference == None
        return
    endif
    int idx = TrackedStations.Find(akReference)
    if idx >= 0
        TrackedStations.Remove(idx)
    endif
    SyncGlobals()
    Trace("station_removed ref=" + Id(akReference) + " workshop=" + Id(akSender) + " count=" + TrackedStations.Length)
EndEvent

Function ScanNearbyBuiltStations(Actor playerRef)
    if playerRef == None
        return
    endif
    Keyword furnKw = Game.GetFormFromFile(StationFurnKwId, "Starfield.esm") as Keyword
    if furnKw == None
        return
    endif
    if TrackedWorkshops.Length == 0 && TrackedBeacons.Length == 0
        return
    endif
    ObjectReference[] found = playerRef.FindAllReferencesWithKeyword(furnKw, StationScanRadiusM)
    if found == None
        return
    endif
    int i = 0
    while i < found.Length
        ObjectReference cand = found[i]
        if cand != None && !cand.IsDisabled() && !cand.IsDeleted()
            if TrackedWorkshops.Find(cand) < 0 && TrackedBeacons.Find(cand) < 0 && TrackedStations.Find(cand) < 0
                if IsNearAnyTrackedHub(cand, StationScanRadiusM)
                    TrackedStations.Add(cand)
                    Trace("station_placed ref=" + Id(cand) + " base=" + Id(cand.GetBaseObject()) + " workshop=scan loaded=" + cand.Is3DLoaded() + " count=" + TrackedStations.Length)
                endif
            endif
        endif
        i += 1
    endwhile
EndFunction

bool Function IsNearAnyTrackedHub(ObjectReference candRef, float maxDist)
    int i = 0
    while i < TrackedWorkshops.Length
        ObjectReference ws = TrackedWorkshops[i]
        if ws != None && !ws.IsDeleted() && ws.GetDistance(candRef) <= maxDist
            return true
        endif
        i += 1
    endwhile
    int j = 0
    while j < TrackedBeacons.Length
        ObjectReference bc = TrackedBeacons[j]
        if bc != None && !bc.IsDeleted() && bc.GetDistance(candRef) <= maxDist
            return true
        endif
        j += 1
    endwhile
    return false
EndFunction

; ---------------------------------------------------------------- portable kit drop handling

Event ObjectReference.OnItemRemoved(ObjectReference akSender, Form akBaseItem, int aiItemCount, ObjectReference akItemReference, ObjectReference akDestContainer, int aiTransferReason)
    if akBaseItem == None || akDestContainer != None
        return
    endif
    Actor playerRef = Game.GetPlayer()
    if playerRef == None || akSender != (playerRef as ObjectReference)
        return
    endif
    int baseId = akBaseItem.GetFormID()
    Form campKit = Game.GetFormFromFile(CampKitId, WorkshopPlugin)
    Form packToken = Game.GetFormFromFile(CampPackTokenId, WorkshopPlugin)
    Form settleKit = Game.GetFormFromFile(SettlementKitId, WorkshopPlugin)
    Form scrapToken = Game.GetFormFromFile(ScrapTokenId, WorkshopPlugin)

    if campKit != None && baseId == campKit.GetFormID()
        TryDeployCamp(playerRef, akItemReference, "kit", 0, 0.0)
    elseif packToken != None && baseId == packToken.GetFormID()
        ConsumeDroppedToken(akItemReference)
        playerRef.AddItem(packToken, 1, true)
        PackUpLatestCamp(playerRef, "kit", 0)
    elseif settleKit != None && baseId == settleKit.GetFormID()
        ConsumeDroppedToken(akItemReference)
        PlaceSettlementBench(playerRef, "kit", 0, 0.0)
    elseif scrapToken != None && baseId == scrapToken.GetFormID()
        ConsumeDroppedToken(akItemReference)
        playerRef.AddItem(scrapToken, 1, true)
        ScrapAllJunk(playerRef, "kit", 0)
    endif
EndEvent

Function ConsumeDroppedToken(ObjectReference droppedRef)
    if droppedRef != None && !droppedRef.IsDeleted()
        droppedRef.DisableNoWait(false)
        droppedRef.Delete()
    endif
EndFunction

; ---------------------------------------------------------------- settlement workbench & C.A.M.P. placement

ObjectReference Function PlaceSettlementBench(Actor playerRef, string modeStr, int stageNum, float lateralM)
    Form benchBase = ResolveBenchBase()
    if playerRef == None || benchBase == None
        Trace("bench_placed stage=" + stageNum + " mode=" + modeStr + " ref=none base=none moved=false loaded=false haskw=false cell=none dist=-1.0 count=" + TrackedWorkshops.Length)
        return None
    endif
    ObjectReference benchRef = playerRef.PlaceAtMe(benchBase, 1, true, false, false)
    bool moved = false
    if benchRef != None
        float ang = playerRef.GetAngleZ()
        float dx = AheadM * Math.Sin(ang) + lateralM * Math.Cos(ang)
        float dy = AheadM * Math.Cos(ang) - lateralM * Math.Sin(ang)
        benchRef.MoveTo(playerRef, dx, dy, 0.0, false)
        moved = true
        TrackedWorkshops.Add(benchRef)
        RegisterForRemoteEvent(benchRef, "OnWorkshopObjectPlaced")
        RegisterForRemoteEvent(benchRef, "OnWorkshopObjectRemoved")
        RegisterForRemoteEvent(benchRef, "OnWorkshopMode")
    endif
    SyncGlobals()
    if benchRef != None
        Trace("bench_placed stage=" + stageNum + " mode=" + modeStr + " ref=" + Id(benchRef) + " base=" + Id(benchBase) + " moved=" + moved + " loaded=" + benchRef.Is3DLoaded() + " haskw=" + HasWorkshopKeywordStr(benchRef) + " cell=" + Id(benchRef.GetParentCell()) + " dist=" + playerRef.GetDistance(benchRef) + " count=" + TrackedWorkshops.Length)
        LogRefReading("now", "bench", TrackedWorkshops.Length - 1, benchRef)
        Say("Settlement workbench placed (" + TrackedWorkshops.Length + " active).")
    endif
    return benchRef
EndFunction

float Function NearestHubDistance(Actor playerRef, float targetX, float targetY, float targetZ, float searchRadius)
    float best = 999999.0
    Cell pCell = playerRef.GetParentCell()
    WorldSpace pWs = playerRef.GetWorldSpace()

    int i = 0
    while i < TrackedWorkshops.Length
        ObjectReference ws = TrackedWorkshops[i]
        if ws != None && !ws.IsDisabled() && !ws.IsDeleted()
            if (pWs != None && ws.GetWorldSpace() == pWs) || ws.GetParentCell() == pCell
                float d = PointDistance(targetX, targetY, targetZ, ws)
                if d < best
                    best = d
                endif
            endif
        endif
        i += 1
    endwhile

    int j = 0
    while j < TrackedBeacons.Length
        ObjectReference bc = TrackedBeacons[j]
        if bc != None && !bc.IsDisabled() && !bc.IsDeleted()
            if (pWs != None && bc.GetWorldSpace() == pWs) || bc.GetParentCell() == pCell
                float d2 = PointDistance(targetX, targetY, targetZ, bc)
                if d2 < best
                    best = d2
                endif
            endif
        endif
        j += 1
    endwhile

    Keyword wsKw = Game.GetFormFromFile(WorkshopKwId, "Starfield.esm") as Keyword
    if wsKw != None && searchRadius > 0.0
        ObjectReference[] worldHubs = playerRef.FindAllReferencesWithKeyword(wsKw, searchRadius + 12.0)
        if worldHubs != None
            int k = 0
            while k < worldHubs.Length
                ObjectReference hub = worldHubs[k]
                if hub != None && !hub.IsDisabled() && !hub.IsDeleted()
                    float d3 = PointDistance(targetX, targetY, targetZ, hub)
                    if d3 < best
                        best = d3
                    endif
                endif
                k += 1
            endwhile
        endif
    endif
    return best
EndFunction

float Function PointDistance(float x1, float y1, float z1, ObjectReference targetRef)
    float dx = x1 - targetRef.GetPositionX()
    float dy = y1 - targetRef.GetPositionY()
    float dz = z1 - targetRef.GetPositionZ()
    return Math.Sqrt(dx * dx + dy * dy + dz * dz)
EndFunction

ObjectReference Function TryDeployCamp(Actor playerRef, ObjectReference droppedKitRef, string modeStr, int stageNum, float lateralM)
    Form campKit = Game.GetFormFromFile(CampKitId, WorkshopPlugin)
    Form packToken = Game.GetFormFromFile(CampPackTokenId, WorkshopPlugin)
    Form beaconBase = Game.GetFormFromFile(BeaconBaseId, "Starfield.esm")
    ConsumeDroppedToken(droppedKitRef)

    if playerRef == None || beaconBase == None
        if playerRef != None && campKit != None
            playerRef.AddItem(campKit, 1, true)
        endif
        return None
    endif

    float ang = playerRef.GetAngleZ()
    float dx = AheadM * Math.Sin(ang) + lateralM * Math.Cos(ang)
    float dy = AheadM * Math.Cos(ang) - lateralM * Math.Sin(ang)
    float tx = playerRef.GetPositionX() + dx
    float ty = playerRef.GetPositionY() + dy
    float tz = playerRef.GetPositionZ()

    float minExcl = GetExclusionRadius()
    if minExcl > 0.0
        float nearest = NearestHubDistance(playerRef, tx, ty, tz, minExcl)
        if nearest < minExcl
            if campKit != None
                playerRef.AddItem(campKit, 1, true)
            endif
            Trace("camp_blocked stage=" + stageNum + " mode=" + modeStr + " reason=exclusion_zone nearest_dist=" + nearest + " min_dist=" + minExcl + " refunded=true")
            Say("C.A.M.P. blocked: existing workshop or C.A.M.P. within " + (minExcl as int) + " m (kit refunded).")
            return None
        endif
    endif

    ObjectReference beaconRef = playerRef.PlaceAtMe(beaconBase, 1, true, false, false)
    bool moved = false
    if beaconRef != None
        beaconRef.MoveTo(playerRef, dx, dy, 0.0, false)
        moved = true
        TrackedBeacons.Add(beaconRef)
        RegisterForRemoteEvent(beaconRef, "OnWorkshopObjectPlaced")
        RegisterForRemoteEvent(beaconRef, "OnWorkshopObjectRemoved")
        RegisterForRemoteEvent(beaconRef, "OnWorkshopMode")
        if packToken != None && playerRef.GetItemCount(packToken) < 1
            playerRef.AddItem(packToken, 1, true)
        endif
    endif
    SyncGlobals()
    if beaconRef != None
        Trace("camp_deployed stage=" + stageNum + " mode=" + modeStr + " ref=" + Id(beaconRef) + " base=" + Id(beaconBase) + " moved=" + moved + " loaded=" + beaconRef.Is3DLoaded() + " haskw=" + HasWorkshopKeywordStr(beaconRef) + " cell=" + Id(beaconRef.GetParentCell()) + " dist=" + playerRef.GetDistance(beaconRef) + " active_camps=" + TrackedBeacons.Length)
        LogRefReading("now", "beacon", TrackedBeacons.Length - 1, beaconRef)
        Say("C.A.M.P. deployed (" + TrackedBeacons.Length + " active). Press E on beacon to build.")
    endif
    return beaconRef
EndFunction

bool Function PackUpLatestCamp(Actor playerRef, string modeStr, int stageNum)
    PruneDeadRefs()
    if TrackedBeacons.Length == 0
        Say("No active C.A.M.P. beacon to pack up.")
        Trace("camp_packed stage=" + stageNum + " mode=" + modeStr + " ref=none refunded_kit=false active_camps=0")
        return false
    endif
    int lastIdx = TrackedBeacons.Length - 1
    ObjectReference beaconRef = TrackedBeacons[lastIdx]
    string refIdStr = Id(beaconRef)
    TrackedBeacons.Remove(lastIdx)
    if beaconRef != None
        UnregisterForRemoteEvent(beaconRef, "OnWorkshopObjectPlaced")
        UnregisterForRemoteEvent(beaconRef, "OnWorkshopObjectRemoved")
        UnregisterForRemoteEvent(beaconRef, "OnWorkshopMode")
        beaconRef.DisableNoWait(false)
        beaconRef.Delete()
    endif
    Form campKit = Game.GetFormFromFile(CampKitId, WorkshopPlugin)
    if playerRef != None && campKit != None
        playerRef.AddItem(campKit, 1, true)
    endif
    SyncGlobals()
    Trace("camp_packed stage=" + stageNum + " mode=" + modeStr + " ref=" + refIdStr + " refunded_kit=true active_camps=" + TrackedBeacons.Length)
    Say("C.A.M.P. packed up; Portable C.A.M.P. Kit returned to inventory.")
    return true
EndFunction

; ---------------------------------------------------------------- CMPO -> IRES -> MISC scrapping

Function GiveCmpoResource(Actor playerRef, FormList miscList, int cmpoIndex, int amount)
    if playerRef == None || miscList == None || amount <= 0
        return
    endif
    if cmpoIndex < 0 || cmpoIndex >= miscList.GetSize()
        return
    endif
    Form resMisc = miscList.GetAt(cmpoIndex)
    if resMisc != None
        playerRef.AddItem(resMisc, amount, true)
    endif
EndFunction

int Function CountCmpoResource(Actor playerRef, FormList miscList, int cmpoIndex)
    if playerRef == None || miscList == None || cmpoIndex < 0 || cmpoIndex >= miscList.GetSize()
        return 0
    endif
    Form resMisc = miscList.GetAt(cmpoIndex)
    if resMisc == None
        return 0
    endif
    return playerRef.GetItemCount(resMisc)
EndFunction

Function ScrapAllJunk(Actor playerRef, string modeStr, int stageNum)
    FormList miscList = GetOwnFormList(CmpoMiscListId)
    FormList iresList = GetOwnFormList(CmpoIresListId)
    if playerRef == None || miscList == None || iresList == None || miscList.GetSize() < 18 || iresList.GetSize() < 18
        Trace("scrap_run stage=" + stageNum + " mode=" + modeStr + " junk_removed=0 components_added=0 pass=false")
        return
    endif

    Form fanForm = Game.GetFormFromFile(JunkDeskFanId, WorkshopPlugin)
    Form tapeForm = Game.GetFormFromFile(JunkDuctTapeId, WorkshopPlugin)
    Form plateForm = Game.GetFormFromFile(JunkHotPlateId, WorkshopPlugin)
    Form canForm = Game.GetFormFromFile(JunkTinCanId, WorkshopPlugin)

    int nFan = 0
    int nTape = 0
    int nPlate = 0
    int nCan = 0
    if fanForm != None
        nFan = playerRef.GetItemCount(fanForm)
        if nFan > 0
            playerRef.RemoveItem(fanForm, nFan, true, None)
        endif
    endif
    if tapeForm != None
        nTape = playerRef.GetItemCount(tapeForm)
        if nTape > 0
            playerRef.RemoveItem(tapeForm, nTape, true, None)
        endif
    endif
    if plateForm != None
        nPlate = playerRef.GetItemCount(plateForm)
        if nPlate > 0
            playerRef.RemoveItem(plateForm, nPlate, true, None)
        endif
    endif
    if canForm != None
        nCan = playerRef.GetItemCount(canForm)
        if nCan > 0
            playerRef.RemoveItem(canForm, nCan, true, None)
        endif
    endif

    int totalJunk = nFan + nTape + nPlate + nCan
    int addSteel = nFan * 2 + nCan * 2
    int addAluminum = nCan * 2
    int addAdhesive = nTape * 2
    int addScrews = nFan * 2 + nPlate * 1
    int addCopper = nPlate * 2
    int addCircuitry = nPlate * 1
    int addGears = nFan * 2
    int addCloth = nTape * 1

    GiveCmpoResource(playerRef, miscList, 0, addSteel)
    GiveCmpoResource(playerRef, miscList, 2, addAluminum)
    GiveCmpoResource(playerRef, miscList, 3, addAdhesive)
    GiveCmpoResource(playerRef, miscList, 4, addScrews)
    GiveCmpoResource(playerRef, miscList, 5, addCopper)
    GiveCmpoResource(playerRef, miscList, 6, addCircuitry)
    GiveCmpoResource(playerRef, miscList, 9, addGears)
    GiveCmpoResource(playerRef, miscList, 12, addCloth)

    int totalComps = addSteel + addAluminum + addAdhesive + addScrews + addCopper + addCircuitry + addGears + addCloth
    bool ok = totalJunk > 0 && totalComps > 0
    Trace("scrap_run stage=" + stageNum + " mode=" + modeStr + " junk_removed=" + totalJunk + " components_added=" + totalComps + " steel_iron=" + CountCmpoResource(playerRef, miscList, 0) + " aluminum=" + CountCmpoResource(playerRef, miscList, 2) + " adhesive=" + CountCmpoResource(playerRef, miscList, 3) + " copper=" + CountCmpoResource(playerRef, miscList, 5) + " screws_tungsten=" + CountCmpoResource(playerRef, miscList, 4) + " gears_frame=" + CountCmpoResource(playerRef, miscList, 9) + " circuitry_wire=" + CountCmpoResource(playerRef, miscList, 6) + " cloth_fiber=" + CountCmpoResource(playerRef, miscList, 12) + " pass=" + ok)
    if totalJunk > 0
        Say("Scrapped " + totalJunk + " junk item(s) into " + totalComps + " crafting resources.")
    else
        Say("No salvage junk items in inventory to scrap.")
    endif
EndFunction

; ---------------------------------------------------------------- bench recipes audit (stage 30)

Function AuditBenchRecipes(Actor playerRef, int stageNum)
    FormList iresList = GetOwnFormList(CmpoIresListId)
    FormList miscList = GetOwnFormList(CmpoMiscListId)
    FormList recList = GetOwnFormList(BenchRecipesListId)
    int iresN = ListSize(iresList)
    int miscN = ListSize(miscList)
    int recN = ListSize(recList)

    int validN = 0
    if recList != None
        int i = 0
        while i < recN
            if recList.GetAt(i) != None
                validN += 1
            endif
            i += 1
        endwhile
    endif

    int haveSteel = CountCmpoResource(playerRef, miscList, 0)
    int haveAlum = CountCmpoResource(playerRef, miscList, 2)
    int haveAdh = CountCmpoResource(playerRef, miscList, 3)
    int haveScrews = CountCmpoResource(playerRef, miscList, 4)
    int haveCircuit = CountCmpoResource(playerRef, miscList, 6)
    int haveGears = CountCmpoResource(playerRef, miscList, 9)
    int haveCloth = CountCmpoResource(playerRef, miscList, 12)
    int haveAntisep = CountCmpoResource(playerRef, miscList, 17)

    bool canParts = haveSteel >= 3 && haveAdh >= 2 && haveScrews >= 2 && haveAlum >= 2
    bool canCamp = haveSteel >= 4 && haveAlum >= 3 && haveGears >= 2 && haveCircuit >= 1
    bool canMedkit = haveAntisep >= 2 && haveSteel >= 1 && haveCloth >= 1
    bool ok = (iresN == 18) && (miscN == 18) && (recN == 8) && (validN == 8)
    Trace("recipe_audit stage=" + stageNum + " cmpo_pairs=" + iresN + " recipes_total=" + recN + " fo4_cobj=4 fnv_rcpe=4 valid_forms=" + validN + " can_craft_medkit=" + canMedkit + " can_craft_parts=" + canParts + " can_craft_camp=" + canCamp + " pass=" + ok)
EndFunction

; ---------------------------------------------------------------- persistence & reload audit

Function LogRefReading(string whenStr, string kindStr, int idx, ObjectReference targetRef)
    Actor playerRef = Game.GetPlayer()
    if targetRef == None
        Trace("read when=" + whenStr + " kind=" + kindStr + " idx=" + idx + " ref=none")
        return
    endif
    float distVal = -1.0
    if playerRef != None
        distVal = playerRef.GetDistance(targetRef)
    endif
    Trace("read when=" + whenStr + " kind=" + kindStr + " idx=" + idx + " ref=" + Id(targetRef) + " base=" + Id(targetRef.GetBaseObject()) + " loaded=" + targetRef.Is3DLoaded() + " haskw=" + HasWorkshopKeywordStr(targetRef) + " disabled=" + targetRef.IsDisabled() + " deleted=" + targetRef.IsDeleted() + " cell=" + Id(targetRef.GetParentCell()) + " pos=" + targetRef.GetPositionX() + "," + targetRef.GetPositionY() + "," + targetRef.GetPositionZ() + " dist=" + distVal)
EndFunction

Function AuditPersistence(string whenStr)
    Actor playerRef = Game.GetPlayer()
    if playerRef != None
        ScanNearbyBuiltStations(playerRef)
    endif
    int wsTotal = TrackedWorkshops.Length
    int wsOk = 0
    int i = 0
    while i < wsTotal
        ObjectReference ws = TrackedWorkshops[i]
        LogRefReading(whenStr, "bench", i, ws)
        if ws != None && !ws.IsDeleted() && !ws.IsDisabled() && ws.Is3DLoaded() && HasWorkshopKeywordStr(ws) == "true"
            wsOk += 1
        endif
        i += 1
    endwhile

    int bcTotal = TrackedBeacons.Length
    int bcOk = 0
    int j = 0
    while j < bcTotal
        ObjectReference bc = TrackedBeacons[j]
        LogRefReading(whenStr, "beacon", j, bc)
        if bc != None && !bc.IsDeleted() && !bc.IsDisabled() && bc.Is3DLoaded()
            bcOk += 1
        endif
        j += 1
    endwhile

    int stTotal = TrackedStations.Length
    int stOk = 0
    int k = 0
    while k < stTotal
        ObjectReference st = TrackedStations[k]
        LogRefReading(whenStr, "station", k, st)
        if st != None && !st.IsDeleted() && !st.IsDisabled() && st.Is3DLoaded()
            stOk += 1
        endif
        k += 1
    endwhile

    SyncGlobals()
    bool anyTracked = (wsTotal + bcTotal + stTotal) > 0
    bool allAlive = (wsOk == wsTotal) && (bcOk == bcTotal) && (stOk == stTotal)
    bool passFlag = anyTracked && allAlive
    Trace("reload_audit when=" + whenStr + " reload_count=" + ReloadCount + " benches_ok=" + wsOk + "/" + wsTotal + " beacons_ok=" + bcOk + "/" + bcTotal + " stations_ok=" + stOk + "/" + stTotal + " pass=" + passFlag)
EndFunction

; ---------------------------------------------------------------- stage polling & execution

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_POLL
        PollStages()
        StartTimer(POLL_S, TIMER_POLL)
    elseif aiTimerID == TIMER_RELOAD_SETTLE
        AuditPersistence("reload+2s")
    elseif aiTimerID == TIMER_ARRIVE_SETTLE
        AuditPersistence("arrival")
    endif
EndEvent

Function PollStages()
    InitArrays()
    Actor playerRef = Game.GetPlayer()
    if playerRef != None
        Cell curCell = playerRef.GetParentCell()
        if curCell != LastPlayerCell
            LastPlayerCell = curCell
            StartTimer(2.0, TIMER_ARRIVE_SETTLE)
        endif
    endif

    int i = 0
    while i < StageList.Length
        int stg = StageList[i]
        if !DoneList[i] && GetStageDone(stg)
            DoneList[i] = true
            RunStage(stg, playerRef)
        endif
        i += 1
    endwhile

    if GetStageDone(60) && !CleanupDone
        CleanupDone = true
        CleanupAll()
    endif
EndFunction

Function RunStage(int stageNum, Actor playerRef)
    if playerRef == None
        return
    endif
    if stageNum == 5
        GiveStarterBundle(playerRef)
    elseif stageNum == 10
        float side = 0.0
        if TrackedBeacons.Length > 0
            side = SideOffsetM
        endif
        PlaceSettlementBench(playerRef, "console", 10, side)
    elseif stageNum == 15
        RunStage15CampCheck(playerRef)
    elseif stageNum == 20
        GiveJunkBatch(playerRef, 4)
        ScrapAllJunk(playerRef, "console", 20)
    elseif stageNum == 30
        AuditBenchRecipes(playerRef, 30)
    elseif stageNum == 40
        PackUpLatestCamp(playerRef, "console", 40)
    elseif stageNum == 50
        AuditPersistence("stage50")
    endif
EndFunction

Function RunStage15CampCheck(Actor playerRef)
    Form campKit = Game.GetFormFromFile(CampKitId, WorkshopPlugin)
    if campKit != None && playerRef.GetItemCount(campKit) < 1
        playerRef.AddItem(campKit, 1, true)
    endif
    ObjectReference firstTry = TryDeployCamp(playerRef, None, "console", 15, 0.0)
    if firstTry != None
        ; C.A.M.P. #1 deployed at open site; verify immediate second C.A.M.P. at same site is blocked by 45 m exclusion
        TryDeployCamp(playerRef, None, "console", 15, 0.0)
    else
        ; Already inside an existing workshop's 45 m exclusion zone (camp_blocked just logged!):
        ; temporarily set exclusion to 0 to place C.A.M.P. #1 beside the bench for save-reload testing, then restore exclusion
        GlobalVariable gExcl = GetOwnGlobal(CampExclGlobId)
        float saved = 45.0
        if gExcl != None
            saved = gExcl.GetValue()
            gExcl.SetValue(0.0)
        endif
        TryDeployCamp(playerRef, None, "console", 15, -SideOffsetM)
        if gExcl != None
            gExcl.SetValue(saved)
        endif
    endif
EndFunction

Function GiveJunkBatch(Actor playerRef, int countEach)
    Form fanForm = Game.GetFormFromFile(JunkDeskFanId, WorkshopPlugin)
    Form tapeForm = Game.GetFormFromFile(JunkDuctTapeId, WorkshopPlugin)
    Form plateForm = Game.GetFormFromFile(JunkHotPlateId, WorkshopPlugin)
    Form canForm = Game.GetFormFromFile(JunkTinCanId, WorkshopPlugin)
    if fanForm != None
        playerRef.AddItem(fanForm, countEach, true)
    endif
    if tapeForm != None
        playerRef.AddItem(tapeForm, countEach, true)
    endif
    if plateForm != None
        playerRef.AddItem(plateForm, countEach, true)
    endif
    if canForm != None
        playerRef.AddItem(canForm, countEach, true)
    endif
EndFunction

Function GiveStarterBundle(Actor playerRef)
    Form campKit = Game.GetFormFromFile(CampKitId, WorkshopPlugin)
    Form packToken = Game.GetFormFromFile(CampPackTokenId, WorkshopPlugin)
    Form settleKit = Game.GetFormFromFile(SettlementKitId, WorkshopPlugin)
    Form scrapToken = Game.GetFormFromFile(ScrapTokenId, WorkshopPlugin)
    if campKit != None
        playerRef.AddItem(campKit, 1, true)
    endif
    if packToken != None
        playerRef.AddItem(packToken, 1, true)
    endif
    if settleKit != None
        playerRef.AddItem(settleKit, 1, true)
    endif
    if scrapToken != None
        playerRef.AddItem(scrapToken, 1, true)
    endif
    GiveJunkBatch(playerRef, 4)
    Say("Starter bundle added: C.A.M.P. Kit, Settlement Kit, Pack-Up Token, Scrapper Kit, and salvage junk.")
EndFunction

Function CleanupAll()
    int wsN = TrackedWorkshops.Length
    int i = 0
    while i < wsN
        ObjectReference ws = TrackedWorkshops[i]
        if ws != None && !ws.IsDeleted()
            UnregisterForRemoteEvent(ws, "OnWorkshopObjectPlaced")
            UnregisterForRemoteEvent(ws, "OnWorkshopObjectRemoved")
            UnregisterForRemoteEvent(ws, "OnWorkshopMode")
            ws.DisableNoWait(false)
            ws.Delete()
        endif
        i += 1
    endwhile

    int bcN = TrackedBeacons.Length
    int j = 0
    while j < bcN
        ObjectReference bc = TrackedBeacons[j]
        if bc != None && !bc.IsDeleted()
            UnregisterForRemoteEvent(bc, "OnWorkshopObjectPlaced")
            UnregisterForRemoteEvent(bc, "OnWorkshopObjectRemoved")
            UnregisterForRemoteEvent(bc, "OnWorkshopMode")
            bc.DisableNoWait(false)
            bc.Delete()
        endif
        j += 1
    endwhile

    int stN = TrackedStations.Length
    TrackedWorkshops.Clear()
    TrackedBeacons.Clear()
    TrackedStations.Clear()
    SyncGlobals()
    Trace("cleanup benches_removed=" + wsN + " beacons_removed=" + bcN + " stations_cleared=" + stN)
EndFunction
