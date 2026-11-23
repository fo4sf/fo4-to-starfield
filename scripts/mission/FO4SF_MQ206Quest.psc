Scriptname FO4SF_MQ206Quest extends Quest
{"The Molecular Level" (FO4SFMission.esm 0x000B30, source-audited from Fallout 4's MQ205/MQ206 0x0B1752).
 Story mode only (FO4SF_GameMode 0x000870 == 1; stops silently in Warfare mode == 2).
 Stages:
   10   = Objective 10: Track and defeat Institute Courser Z2-47 (0x000B32) at Greenetech Genetics (0x056471)
   20   = Objective 20: Courser Chip acquired (0x000B39); decode at Railroad HQ (0x03CC9F) with Tinker Tom
   65   = Open-Mode Stage 65: Tinker Tom dead/hostile -> self-decode via ScannerProxyActi (0x000B3C)
   100  = Objective 30: Decoded Courser Chip Holotape (0x000B3A) ready; return to Virgil (0x069B10) or terminal
   200  = Objective 50: Signal Interceptor Schematics (0x000B3B) ready; choose faction ally (Minutemen/Railroad/BoS) or Solo Open-Mode
   300  = Objective 100: Faction or Solo chosen (switchable before Stage 1000); assemble 4 Signal Interceptor parts
   350  = All 4 parts built (Platform + Beam + Dish + Console); wire & power +27 unified grid
   600  = Array powered (+27 Power)
   700  = Objective 150: Signal Interceptor ReadyToTeleport=1; activate ConsoleProxyActi (0x000B3D)
   1000 = Objective 250: Relay fired -> MoveTo FO4Port_InstituteConcourse (0x03D252)
   1200 = CompleteQuest -> set FO4SF_MQ207Armed=1 inside Institute Concourse.
 W6 break-it safe: MOL-01..05 (Stage 65 Railroad self-decode, dead-Virgil terminal schematics, switchable
 faction branch + Solo Open-Mode workbench self-build, unified +27 power gate without vanilla wire/snap traps,
 clean relay MoveTo FO4Port_InstituteConcourse 0x03D252, OnPlayerLoadGame full re-sync).}

Form Property XMarkerBase Auto Const
Actor Property CourserZ247 Auto Const
Actor Property Desdemona Auto Const
Actor Property TinkerTom Auto Const
Actor Property ProctorIngram Auto Const
Actor Property Sturges Auto Const
Actor Property Virgil Auto Const
MiscObject Property CourserChip Auto Const
MiscObject Property CourserChipHolotape Auto Const
MiscObject Property SignalInterceptorPlans Auto Const
Activator Property ScannerProxyActi Auto Const
Activator Property ConsoleProxyActi Auto Const
GlobalVariable Property TeleporterFaction Auto Const
GlobalVariable Property BuiltPlatform Auto Const
GlobalVariable Property BuiltBeam Auto Const
GlobalVariable Property BuiltDish Auto Const
GlobalVariable Property BuiltConsole Auto Const
GlobalVariable Property ArrayPowered Auto Const
GlobalVariable Property ReadyToTeleport Auto Const
GlobalVariable Property MQ207Armed Auto Const
Message Property TinkerDecodeMsg Auto Const
Message Property ScannerMsg Auto Const
Message Property VirgilPlansMsg Auto Const
Message Property FactionPickMsg Auto Const
Message Property WorkbenchBuildMsg Auto Const
Message Property RelayFireMsg Auto Const
Message Property OpenModeFallbackMsg Auto Const

string LogName = "fo4sf_mission"
string CorePlugin = "FO4TerrainCore.esm"
string CoreMarsPlugin = "FO4TerrainCore_Mars.esm"
string PortPlugin = "FO4Port.esm"
string MissionPlugin = "FO4SFMission.esm"
int CommonwealthWorldId = 0x000803
int CommonwealthAnchorId = 0x0A775B

; Verified FO4Port.esm cell IDs and persistent (0x400) Institute Concourse COCMarkerHeading
int Greenetech01CellId = 0x056471
int Greenetech02CellId = 0x04BE53
int RailroadHQCellId = 0x03CC9F
int VirgilsLabCellId = 0x069B10
int InstituteConcourseCellId = 0x03D252
int InstituteConcourseMarkerId = 0x03D52E

; Verified Sanctuary workbench ref & base ACTI IDs in FO4TerrainCore.esm
int SanctuaryBenchRefId = 0x005C50
int SanctuaryBenchBaseId = 0x0A2ECD
float SanctuaryBenchX = -2329.250
float SanctuaryBenchY = -1420.193
float SanctuaryBenchZ = 112.086

; Verified merged coordinates (FO4/70 + MergeOffset -1200, -2700)
float GreenetechX = -1238.10
float GreenetechY = -2687.39
float GreenetechZ = 12.18
float RailroadX = -734.83
float RailroadY = -2696.65
float RailroadZ = 10.16
float AirportX = -513.23
float AirportY = -2747.60
float AirportZ = 10.27
float SanctuaryX = -2353.83
float SanctuaryY = -1440.36
float SanctuaryZ = 112.76
float RockyCaveX = -2862.82
float RockyCaveY = -4653.27
float MergeOffsetX = -1200.0
float MergeOffsetY = -2700.0

float PlaceRadius = 260.0
float EngageRadius = 45.0
float TalkFallbackRadius = 3.5
float TalkFallbackSeconds = 8.0

bool instanceStarted = False
bool gateDeferred = False
bool completed = False
bool courserPlaced = False
bool railroadPlaced = False
bool airportPlaced = False
bool chipGranted = False
bool holotapeGranted = False
bool plansGranted = False
bool talkOpen = False
int talkSessionId = 0
int applied = 0
int pendingStage = -1
string pendingStageBy = "other"
float talkNearSec = 0.0
ObjectReference scannerProxyRef = None
ObjectReference consoleProxyRef = None
ObjectReference sanctuaryBenchRef = None
ObjectReference tomTalkProxy = None
ObjectReference desTalkProxy = None
ObjectReference ingramTalkProxy = None

bool Function IsTestModeEnabled()
    GlobalVariable tm = Game.GetFormFromFile(0x000860, "FO4SFCoreValues.esm") as GlobalVariable
    return tm != None && tm.GetValue() != 0.0
EndFunction

bool Function CheckPredecessorGate()
{R5: MQ206 starts strictly behind MQ204 completion (stage >= 200 or FO4SF_MQ206Armed >= 1) unless TestMode is on.}
    if IsTestModeEnabled()
        return True
    endif
    GlobalVariable armed = Game.GetFormFromFile(0x000B18, MissionPlugin) as GlobalVariable
    if armed != None && armed.GetValue() >= 1.0
        return True
    endif
    Quest mq204 = Game.GetFormFromFile(0x000B10, MissionPlugin) as Quest
    if mq204 != None && (mq204.IsCompleted() || mq204.GetStage() >= 200)
        return True
    endif
    return False
EndFunction

bool Function IsWarfareMode()
    GlobalVariable gm = Game.GetFormFromFile(0x000870, "FO4SFCoreValues.esm") as GlobalVariable
    if gm != None && (gm.GetValue() as int) == 2
        return True
    endif
    return False
EndFunction

int Function EffectiveStage()
    int raw = GetStage()
    if applied > raw
        return applied
    endif
    return raw
EndFunction

string Function ActiveCorePlugin()
    if Game.IsPluginInstalled(CorePlugin)
        return CorePlugin
    elseif Game.IsPluginInstalled(CoreMarsPlugin)
        return CoreMarsPlugin
    endif
    return ""
EndFunction

WorldSpace Function ResolveCommonwealthWorld()
    string cp = ActiveCorePlugin()
    if cp == ""
        return None
    endif
    ObjectReference anchor = Game.GetFormFromFile(CommonwealthAnchorId, cp) as ObjectReference
    if anchor != None
        WorldSpace aws = anchor.GetWorldSpace()
        if aws != None
            return aws
        endif
    endif
    return Game.GetFormFromFile(CommonwealthWorldId, cp) as WorldSpace
EndFunction

bool Function IsCommonwealthExterior(Actor player)
    if player == None || !player.Is3DLoaded() || player.IsInInterior()
        return False
    endif
    WorldSpace ws = player.GetWorldSpace()
    WorldSpace wantWs = ResolveCommonwealthWorld()
    if ws == None || wantWs == None || ws != wantWs
        return False
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    if px < MergeOffsetX - 3200.0 || px > MergeOffsetX + 3200.0 || py < MergeOffsetY - 3200.0 || py > MergeOffsetY + 3200.0
        return False
    endif
    return True
EndFunction

bool Function IsPlayerStableAt(Actor player, float snapX, float snapY, float snapZ)
    if !IsCommonwealthExterior(player)
        return False
    endif
    float dx = player.GetPositionX() - snapX
    float dy = player.GetPositionY() - snapY
    float dz = player.GetPositionZ() - snapZ
    return (dx * dx + dy * dy + dz * dz) <= 25.0
EndFunction

Actor Function ResolveCourser()
    if CourserZ247 != None
        return CourserZ247
    endif
    return Game.GetFormFromFile(0x000B32, MissionPlugin) as Actor
EndFunction

Actor Function ResolveDesdemona()
    if Desdemona != None
        return Desdemona
    endif
    return Game.GetFormFromFile(0x000B34, MissionPlugin) as Actor
EndFunction

Actor Function ResolveTinkerTom()
    if TinkerTom != None
        return TinkerTom
    endif
    return Game.GetFormFromFile(0x000B36, MissionPlugin) as Actor
EndFunction

Actor Function ResolveIngram()
    if ProctorIngram != None
        return ProctorIngram
    endif
    return Game.GetFormFromFile(0x000B38, MissionPlugin) as Actor
EndFunction

Actor Function ResolveSturges()
    if Sturges != None
        return Sturges
    endif
    return Game.GetFormFromFile(0x000A01, MissionPlugin) as Actor
EndFunction

Actor Function ResolveVirgil()
    if Virgil != None
        return Virgil
    endif
    return Game.GetFormFromFile(0x000B14, MissionPlugin) as Actor
EndFunction

bool Function IsInCellId(Actor player, int portCellId)
    if player == None || !player.IsInInterior()
        return False
    endif
    Cell cur = player.GetParentCell()
    if cur != None && Game.IsPluginInstalled(PortPlugin)
        Cell target = Game.GetFormFromFile(portCellId, PortPlugin) as Cell
        if target != None && cur == target
            return True
        endif
    endif
    return False
EndFunction

bool Function IsNearXY(Actor player, float tx, float ty, float radius)
    if !IsCommonwealthExterior(player)
        return False
    endif
    float dx = player.GetPositionX() - tx
    float dy = player.GetPositionY() - ty
    return (dx * dx + dy * dy) <= radius * radius
EndFunction

bool Function AllFourPartsBuilt()
    return BuiltPlatform != None && BuiltPlatform.GetValue() >= 1.0 && \
           BuiltBeam != None && BuiltBeam.GetValue() >= 1.0 && \
           BuiltDish != None && BuiltDish.GetValue() >= 1.0 && \
           BuiltConsole != None && BuiltConsole.GetValue() >= 1.0
EndFunction

Function GrantItemOnce(MiscObject item, string tag, string why)
    Actor player = Game.GetPlayer()
    if player != None && item != None
        if player.GetItemCount(item) <= 0
            player.AddItem(item, 1, True)
        endif
        Trace("mq206 " + tag + " granted=true by=" + why)
    endif
EndFunction

Function AdvanceTo(int n, string by = "Trigger")
    pendingStage = n
    pendingStageBy = by
    SetStage(n)
    if n > applied
        applied = n
        Trace("mq206 stage " + n + " by=" + by)
        ApplyStage(n, by)
    endif
EndFunction

Event OnStageSet(int auiStageID, int auiItemID)
    if auiStageID > applied
        string cause = "other"
        if auiStageID == pendingStage
            cause = pendingStageBy
        endif
        applied = auiStageID
        Trace("mq206 stage " + auiStageID + " by=" + cause)
        ApplyStage(auiStageID, cause)
    endif
EndEvent

Function ApplyStage(int n, string by)
    if n == 10
        SetObjectiveDisplayed(10, True, True)
        SetActive(True)
    elseif n == 20
        SetObjectiveCompleted(10)
        if !chipGranted
            chipGranted = True
            GrantItemOnce(CourserChip, "courser_chip", by)
        endif
        SetObjectiveDisplayed(20, True, True)
    elseif n == 65
        SetObjectiveCompleted(10)
        SetObjectiveDisplayed(20, True, True)
        Trace("mq206 railroad_self_decode armed=true by=" + by)
    elseif n == 100
        SetObjectiveCompleted(20)
        if !holotapeGranted
            holotapeGranted = True
            GrantItemOnce(CourserChipHolotape, "courser_holotape", by)
        endif
        SetObjectiveDisplayed(30, True, True)
    elseif n == 200
        SetObjectiveCompleted(30)
        if !plansGranted
            plansGranted = True
            GrantItemOnce(SignalInterceptorPlans, "interceptor_plans", by)
        endif
        SetObjectiveDisplayed(50, True, True)
    elseif n == 300
        SetObjectiveCompleted(50)
        SetObjectiveDisplayed(100, True, True)
    elseif n == 350
        SetObjectiveDisplayed(100, True, True)
    elseif n == 600
        if ArrayPowered != None
            ArrayPowered.SetValue(1.0)
        endif
        SetObjectiveCompleted(100)
        SetObjectiveDisplayed(150, True, True)
    elseif n == 700
        if ArrayPowered != None
            ArrayPowered.SetValue(1.0)
        endif
        if ReadyToTeleport != None
            ReadyToTeleport.SetValue(1.0)
        endif
        SetObjectiveCompleted(100)
        SetObjectiveDisplayed(150, True, True)
    elseif n == 1000
        SetObjectiveCompleted(150)
        SetObjectiveDisplayed(250, True, True)
    elseif n == 1200
        if completed
            return
        endif
        completed = True
        ReleaseAllActors()
        SetObjectiveCompleted(250)
        if MQ207Armed != None
            MQ207Armed.SetValue(1.0)
        endif
        int chosen = 0
        if TeleporterFaction != None
            chosen = TeleporterFaction.GetValue() as int
        endif
        CompleteQuest()
        CancelTimer(1)
        Trace("mq206 complete stage=1200 faction=" + chosen + " mq207_armed=1 institute_cell=0x03D252 by=" + by)
    endif
EndFunction

Event OnQuestStarted()
    StartQuestInstance()
EndEvent

Event OnQuestInit()
    StartQuestInstance()
EndEvent

Function StartQuestInstance()
    if instanceStarted
        return
    endif
    instanceStarted = True
    Debug.OpenUserLog(LogName)
    if IsWarfareMode()
        Trace("mission gate mode=2 started=false quest=mq206")
        Stop()
        return
    endif
    if !CheckPredecessorGate()
        Trace("mq206 gate_deferred reason=mq204_incomplete")
        gateDeferred = True
        instanceStarted = False
        Actor pDefer = Game.GetPlayer()
        if pDefer != None
            RegisterForRemoteEvent(pDefer, "OnPlayerLoadGame")
        endif
        return
    endif
    gateDeferred = False
    if !IsRunning()
        Start()
    endif
    Actor player = Game.GetPlayer()
    if player != None
        RegisterForRemoteEvent(player, "OnPlayerLoadGame")
    endif
    BindRefs()
    AdvanceTo(10, "Trigger")
    if player != None && IsInCellId(player, InstituteConcourseCellId)
        AdvanceTo(1200, "out_of_order")
    endif
    Trace("mq206 init stage=" + EffectiveStage() + " institute_cell=0x03D252")
    if !completed
        StartTimer(1.0, 1)
    endif
EndFunction

Function WakeFromPredecessor()
    if completed || instanceStarted
        return
    endif
    if CheckPredecessorGate()
        gateDeferred = False
        Trace("mq206 gate_resumed")
        StartQuestInstance()
    endif
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    talkOpen = False
    talkSessionId += 1
    courserPlaced = False
    railroadPlaced = False
    airportPlaced = False
    talkNearSec = 0.0
    if gateDeferred && !instanceStarted
        WakeFromPredecessor()
        return
    endif
    int st = EffectiveStage()
    Trace("mq206 reload stage=" + st + " complete=" + completed)
    if !completed
        if !IsRunning()
            Start()
        endif
        if applied > GetStage()
            SetStage(applied)
        endif
        sanctuaryBenchRef = None
        BindRefs()
        StartTimer(1.0, 1)
    endif
EndEvent

Function BindTalkable(Actor a)
    if a != None && !a.IsDead()
        a.AllowPCDialogue(True)
        a.BlockActivation(False, False)
        RegisterForRemoteEvent(a, "OnActivate")
    endif
EndFunction

Function TryBindSanctuaryBench(Actor player)
    string cp = ActiveCorePlugin()
    if cp == ""
        return
    endif
    ObjectReference bench = Game.GetFormFromFile(SanctuaryBenchRefId, cp) as ObjectReference
    if bench == None && player != None && IsCommonwealthExterior(player) && IsNearXY(player, SanctuaryBenchX, SanctuaryBenchY, PlaceRadius)
        Form benchBase = Game.GetFormFromFile(SanctuaryBenchBaseId, cp)
        if benchBase != None
            bench = Game.FindClosestReferenceOfType(benchBase, SanctuaryBenchX, SanctuaryBenchY, SanctuaryBenchZ, 15.0)
        endif
    endif
    if bench != None && bench != sanctuaryBenchRef
        if sanctuaryBenchRef != None
            UnregisterForRemoteEvent(sanctuaryBenchRef, "OnActivate")
        endif
        sanctuaryBenchRef = bench
        RegisterForRemoteEvent(sanctuaryBenchRef, "OnActivate")
        Trace("mq206 sanctuary_bench bound=true")
    endif
EndFunction

Function BindRefs()
    Actor crs = ResolveCourser()
    if crs != None && !crs.IsDead()
        crs.SetRestrained(False)
        RegisterForRemoteEvent(crs, "OnDeath")
    endif
    BindTalkable(ResolveDesdemona())
    BindTalkable(ResolveTinkerTom())
    BindTalkable(ResolveIngram())
    BindTalkable(ResolveSturges())
    Actor vg = ResolveVirgil()
    if vg != None && !vg.IsDead()
        vg.IgnoreFriendlyHits(True)
        BindTalkable(vg)
    endif
    TryBindSanctuaryBench(Game.GetPlayer())
EndFunction

Function ReleaseAllActors()
    Actor crs = ResolveCourser()
    if crs != None && !crs.IsDead()
        crs.SetRestrained(False)
    endif
    Actor des = ResolveDesdemona()
    if des != None && !des.IsDead()
        des.SetRestrained(False)
    endif
    Actor tom = ResolveTinkerTom()
    if tom != None && !tom.IsDead()
        tom.SetRestrained(False)
    endif
    Actor ing = ResolveIngram()
    if ing != None && !ing.IsDead()
        ing.SetRestrained(False)
    endif
    Actor stg = ResolveSturges()
    if stg != None && !stg.IsDead()
        stg.SetRestrained(False)
    endif
EndFunction

Function ReleaseIfInCombat(Actor a)
    if a != None && !a.IsDead() && a.GetCombatState() != 0
        a.SetRestrained(False)
    endif
EndFunction

Function PlaceCourser(Actor player)
    if !IsCommonwealthExterior(player) || courserPlaced || EffectiveStage() < 10
        return
    endif
    Actor crs = ResolveCourser()
    if crs == None || crs.IsDead()
        courserPlaced = True
        return
    endif
    if crs.IsDisabled()
        crs.EnableNoWait(False)
        BindRefs()
        Trace("mq206 courser enabled stage=" + EffectiveStage())
    endif
    float snapX = player.GetPositionX()
    float snapY = player.GetPositionY()
    float snapZ = player.GetPositionZ()
    if !IsPlayerStableAt(player, snapX, snapY, snapZ)
        return
    endif
    crs.SetRestrained(False)
    crs.MoveTo(player, GreenetechX - snapX, GreenetechY - snapY, GreenetechZ - snapZ, False, False)
    if !IsPlayerStableAt(player, snapX, snapY, snapZ)
        return
    endif
    courserPlaced = True
    Trace("mq206 courser placed greenetech=true")
EndFunction

Function PlaceRailroadActors(Actor player)
    if !IsCommonwealthExterior(player) || railroadPlaced || EffectiveStage() < 20
        return
    endif
    float snapX = player.GetPositionX()
    float snapY = player.GetPositionY()
    float snapZ = player.GetPositionZ()
    Actor des = ResolveDesdemona()
    if des != None && !des.IsDead()
        if des.IsDisabled()
            des.EnableNoWait(False)
            BindRefs()
        endif
        if !IsPlayerStableAt(player, snapX, snapY, snapZ)
            return
        endif
        des.SetRestrained(False)
        des.MoveTo(player, RailroadX - snapX, RailroadY - snapY, RailroadZ - snapZ, False, False)
        if des.GetCombatState() == 0
            des.SetRestrained(True)
        endif
        des.AllowPCDialogue(True)
        if desTalkProxy == None || desTalkProxy.IsDeleted()
            Activator dActi = Game.GetFormFromFile(0x000B3E, MissionPlugin) as Activator
            if dActi != None
                desTalkProxy = des.PlaceAtMe(dActi, 1, True, False, False)
                if desTalkProxy != None
                    desTalkProxy.MoveTo(des, 0.0, 0.0, 1.0, False, False)
                    RegisterForRemoteEvent(desTalkProxy, "OnActivate")
                endif
            endif
        endif
    endif
    Actor tom = ResolveTinkerTom()
    if tom != None && !tom.IsDead()
        if tom.IsDisabled()
            tom.EnableNoWait(False)
            BindRefs()
        endif
        if !IsPlayerStableAt(player, snapX, snapY, snapZ)
            return
        endif
        tom.SetRestrained(False)
        tom.MoveTo(player, (RailroadX + 3.8) - snapX, (RailroadY + 1.6) - snapY, RailroadZ - snapZ, False, False)
        if tom.GetCombatState() == 0
            tom.SetRestrained(True)
        endif
        tom.AllowPCDialogue(True)
        if tomTalkProxy == None || tomTalkProxy.IsDeleted()
            Activator tActi = Game.GetFormFromFile(0x000B3F, MissionPlugin) as Activator
            if tActi != None
                tomTalkProxy = tom.PlaceAtMe(tActi, 1, True, False, False)
                if tomTalkProxy != None
                    tomTalkProxy.MoveTo(tom, 0.0, 0.0, 1.0, False, False)
                    RegisterForRemoteEvent(tomTalkProxy, "OnActivate")
                endif
            endif
        endif
    endif
    if !IsPlayerStableAt(player, snapX, snapY, snapZ)
        return
    endif
    railroadPlaced = True
    Trace("mq206 railroad actors placed=true")
EndFunction

Function PlaceAirportActors(Actor player)
    if !IsCommonwealthExterior(player) || airportPlaced || EffectiveStage() < 200
        return
    endif
    float snapX = player.GetPositionX()
    float snapY = player.GetPositionY()
    float snapZ = player.GetPositionZ()
    Actor ing = ResolveIngram()
    if ing != None && !ing.IsDead()
        if ing.IsDisabled()
            ing.EnableNoWait(False)
            BindRefs()
        endif
        if !IsPlayerStableAt(player, snapX, snapY, snapZ)
            return
        endif
        ing.SetRestrained(False)
        ing.MoveTo(player, AirportX - snapX, AirportY - snapY, AirportZ - snapZ, False, False)
        if ing.GetCombatState() == 0
            ing.SetRestrained(True)
        endif
        ing.AllowPCDialogue(True)
        if ingramTalkProxy == None || ingramTalkProxy.IsDeleted()
            Activator iActi = Game.GetFormFromFile(0x000B48, MissionPlugin) as Activator
            if iActi != None
                ingramTalkProxy = ing.PlaceAtMe(iActi, 1, True, False, False)
                if ingramTalkProxy != None
                    ingramTalkProxy.MoveTo(ing, 0.0, 0.0, 1.0, False, False)
                    RegisterForRemoteEvent(ingramTalkProxy, "OnActivate")
                endif
            endif
        endif
    endif
    if !IsPlayerStableAt(player, snapX, snapY, snapZ)
        return
    endif
    airportPlaced = True
    Trace("mq206 ingram placed airport=true")
EndFunction

Function EnsureScannerProxy(Actor player)
    if ScannerProxyActi == None || player == None
        return
    endif
    if scannerProxyRef != None && !scannerProxyRef.IsDeleted()
        return
    endif
    if IsInCellId(player, RailroadHQCellId) || IsNearXY(player, RailroadX, RailroadY, PlaceRadius)
        float snapX = player.GetPositionX()
        float snapY = player.GetPositionY()
        float snapZ = player.GetPositionZ()
        scannerProxyRef = player.PlaceAtMe(ScannerProxyActi, 1, True, False, False)
        if scannerProxyRef != None
            if IsCommonwealthExterior(player) && IsPlayerStableAt(player, snapX, snapY, snapZ)
                scannerProxyRef.MoveTo(player, (RailroadX + 2.0) - snapX, (RailroadY - 2.0) - snapY, (RailroadZ + 1.0) - snapZ, False, False)
            else
                scannerProxyRef.MoveTo(player, 2.0, 2.0, 0.5, False, False)
            endif
            RegisterForRemoteEvent(scannerProxyRef, "OnActivate")
            Trace("mq206 scanner proxy spawned")
        endif
    endif
EndFunction

Function EnsureConsoleProxy(Actor player)
    if ConsoleProxyActi == None || player == None
        return
    endif
    if consoleProxyRef != None && !consoleProxyRef.IsDeleted()
        return
    endif
    if EffectiveStage() >= 200 && IsNearXY(player, SanctuaryX, SanctuaryY, PlaceRadius)
        float snapX = player.GetPositionX()
        float snapY = player.GetPositionY()
        float snapZ = player.GetPositionZ()
        if !IsPlayerStableAt(player, snapX, snapY, snapZ)
            return
        endif
        consoleProxyRef = player.PlaceAtMe(ConsoleProxyActi, 1, True, False, False)
        if consoleProxyRef != None
            consoleProxyRef.MoveTo(player, (SanctuaryX + 4.0) - snapX, (SanctuaryY + 2.0) - snapY, (SanctuaryZ + 1.0) - snapZ, False, False)
            RegisterForRemoteEvent(consoleProxyRef, "OnActivate")
            Trace("mq206 console proxy spawned sanctuary=true")
        endif
    endif
EndFunction

Function FireRelayToInstitute(Actor player, string why)
{R8 truth: NEVER complete MQ206 when FO4Port.esm or persistent marker 0x03D52E is absent and nobody moved!}
    if player == None
        return
    endif
    if Game.IsPluginInstalled(PortPlugin)
        ObjectReference concourseMarker = Game.GetFormFromFile(InstituteConcourseMarkerId, PortPlugin) as ObjectReference
        if concourseMarker != None
            AdvanceTo(1000, why)
            player.MoveTo(concourseMarker)
            Trace("mq206 relay_move dest=0x03D52E ok=true")
            AdvanceTo(1200, why)
            return
        endif
    endif
    Trace("mq206 relay_blocked reason=missing_port_cell cell=0x03D252 marker=0x03D52E")
EndFunction

Event Actor.OnDeath(Actor akSender, ObjectReference akKiller)
    if completed
        return
    endif
    Actor crs = ResolveCourser()
    if akSender == crs && EffectiveStage() < 20
        AdvanceTo(20, "boss_death")
    endif
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID != 1 || completed
        return
    endif
    int raw = GetStage()
    if raw > applied
        applied = raw
        ApplyStage(raw, "other")
    elseif applied > raw
        if !IsRunning()
            Start()
        endif
        SetStage(applied)
    endif
    int st = EffectiveStage()
    Actor player = Game.GetPlayer()
    if player == None
        StartTimer(1.0, 1)
        return
    endif

    ReleaseIfInCombat(ResolveDesdemona())
    ReleaseIfInCombat(ResolveTinkerTom())
    ReleaseIfInCombat(ResolveIngram())
    ReleaseIfInCombat(ResolveSturges())
    Actor vg = ResolveVirgil()
    if vg != None && !vg.IsDead()
        vg.IgnoreFriendlyHits(True)
        if vg.GetCombatTarget() == player
            vg.StopCombat()
        endif
    endif

    if IsNearXY(player, GreenetechX, GreenetechY, PlaceRadius) && !courserPlaced
        PlaceCourser(player)
    endif
    if IsNearXY(player, RailroadX, RailroadY, PlaceRadius) && !railroadPlaced
        PlaceRailroadActors(player)
    endif
    if IsNearXY(player, AirportX, AirportY, PlaceRadius) && !airportPlaced
        PlaceAirportActors(player)
    endif
    if IsInCellId(player, RailroadHQCellId) || IsNearXY(player, RailroadX, RailroadY, PlaceRadius)
        EnsureScannerProxy(player)
    endif
    if st >= 100 && vg != None && !vg.IsDead() && vg.IsDisabled()
        vg.EnableNoWait(False)
        BindTalkable(vg)
    endif
    if st >= 200
        Actor stgEn = ResolveSturges()
        if stgEn != None && !stgEn.IsDead() && stgEn.IsDisabled()
            stgEn.EnableNoWait(False)
            BindTalkable(stgEn)
        endif
        EnsureConsoleProxy(player)
        if IsNearXY(player, SanctuaryX, SanctuaryY, PlaceRadius) && (sanctuaryBenchRef == None || sanctuaryBenchRef.IsDeleted())
            TryBindSanctuaryBench(player)
        endif
    endif

    ; Courser Z2-47 hostile combat & chip acquisition
    Actor crs = ResolveCourser()
    if crs != None && st < 20
        if crs.IsDead()
            AdvanceTo(20, "boss_death")
            st = EffectiveStage()
        elseif crs.Is3DLoaded() && player.GetDistance(crs) <= EngageRadius && crs.GetCombatState() == 0
            crs.SetRestrained(False)
            crs.StartCombat(player)
        endif
    endif

    ; Stage 65 Open-Mode fallback if Tinker Tom is dead while player is at Railroad HQ
    Actor tom = ResolveTinkerTom()
    if st == 20 && (tom == None || tom.IsDead()) && (IsInCellId(player, RailroadHQCellId) || IsNearXY(player, RailroadX, RailroadY, 90.0))
        AdvanceTo(65, "open_mode")
        st = EffectiveStage()
    endif

    ; Dead-Virgil Open-Mode schematics fallback at Rocky Cave
    if st == 100 && (vg == None || vg.IsDead()) && (IsInCellId(player, VirgilsLabCellId) || IsNearXY(player, RockyCaveX, RockyCaveY, 110.0))
        AdvanceTo(200, "open_mode")
        st = EffectiveStage()
    endif

    ; Direct arrival inside Institute Concourse completes MQ206 cleanly
    if IsInCellId(player, InstituteConcourseCellId)
        AdvanceTo(1200, "institute_arrival")
        return
    endif
    CheckTalkFallback(player, st)

    if !completed
        StartTimer(1.0, 1)
    endif
EndEvent

Function CheckTalkFallback(Actor player, int st)
{R4: Timed proximity fallback while Tinker Tom, Virgil, Desdemona, Ingram, or Sturges is alive so topicless OnActivate never stalls.}
    if talkOpen || completed || player == None
        talkNearSec = 0.0
        return
    endif
    if st == 20 || st == 65
        Actor tom = ResolveTinkerTom()
        if tom != None && !tom.IsDead() && !tom.IsDisabled() && tom.Is3DLoaded() && player.GetDistance(tom) <= TalkFallbackRadius
            talkNearSec += 1.0
            if talkNearSec >= TalkFallbackSeconds
                talkNearSec = 0.0
                Trace("mq206 talk_fallback actor=tinker_tom stage=" + st + " near_sec=" + TalkFallbackSeconds)
                RunTinkerDecode()
            endif
            return
        endif
    elseif st == 100
        Actor vg = ResolveVirgil()
        if vg != None && !vg.IsDead() && !vg.IsDisabled() && vg.Is3DLoaded() && player.GetDistance(vg) <= TalkFallbackRadius
            talkNearSec += 1.0
            if talkNearSec >= TalkFallbackSeconds
                talkNearSec = 0.0
                Trace("mq206 talk_fallback actor=virgil stage=100 near_sec=" + TalkFallbackSeconds)
                RunVirgilPlans()
            endif
            return
        endif
    elseif st == 200
        Actor des = ResolveDesdemona()
        Actor ing = ResolveIngram()
        Actor stg = ResolveSturges()
        bool nearAlly = (des != None && !des.IsDead() && !des.IsDisabled() && des.Is3DLoaded() && player.GetDistance(des) <= TalkFallbackRadius) || \
                        (ing != None && !ing.IsDead() && !ing.IsDisabled() && ing.Is3DLoaded() && player.GetDistance(ing) <= TalkFallbackRadius) || \
                        (stg != None && !stg.IsDead() && !stg.IsDisabled() && stg.Is3DLoaded() && player.GetDistance(stg) <= TalkFallbackRadius)
        if nearAlly
            talkNearSec += 1.0
            if talkNearSec >= TalkFallbackSeconds
                talkNearSec = 0.0
                Trace("mq206 talk_fallback actor=faction_ally stage=200 near_sec=" + TalkFallbackSeconds)
                RunFactionPick()
            endif
            return
        endif
    endif
    talkNearSec = 0.0
EndFunction

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    if completed || akActionRef != Game.GetPlayer()
        return
    endif
    int st = EffectiveStage()
    Actor tom = ResolveTinkerTom()
    Actor des = ResolveDesdemona()
    Actor ing = ResolveIngram()
    Actor stg = ResolveSturges()
    Actor vg = ResolveVirgil()

    if (tom != None && akSender == tom) || (tomTalkProxy != None && akSender == tomTalkProxy)
        if st == 20 || st == 65
            RunTinkerDecode()
        elseif st >= 200 && st < 1000
            RunFactionPick()
        endif
        return
    endif
    if akSender == scannerProxyRef
        if st == 20 || st == 65
            RunScannerSelfDecode()
        endif
        return
    endif
    if akSender == vg && st == 100
        RunVirgilPlans()
        return
    endif
    if ((des != None && akSender == des) || (desTalkProxy != None && akSender == desTalkProxy) || \
        (ing != None && akSender == ing) || (ingramTalkProxy != None && akSender == ingramTalkProxy) || \
        (stg != None && akSender == stg)) && st >= 200 && st < 1000
        RunFactionPick()
        return
    endif
    if akSender == sanctuaryBenchRef && st >= 200 && st < 1000
        if st == 200
            if AreAllEngineersUnavailable()
                RunOpenModeFallback()
            else
                RunFactionPick()
            endif
        else
            RunWorkbenchAssembly()
        endif
        return
    endif
    if akSender == consoleProxyRef
        if st == 200
            if AreAllEngineersUnavailable()
                RunOpenModeFallback()
            else
                RunFactionPick()
            endif
        elseif st > 200 && st < 700
            RunWorkbenchAssembly()
        elseif st >= 700 && st < 1000
            RunRelayFire()
        endif
    endif
EndEvent

Function RunTinkerDecode()
    if talkOpen || TinkerDecodeMsg == None
        return
    endif
    talkOpen = True
    talkSessionId += 1
    int sid = talkSessionId
    int btn = TinkerDecodeMsg.Show()
    if sid != talkSessionId
        return
    endif
    talkOpen = False
    if btn < 0 || btn == 2
        return
    endif
    AdvanceTo(100, "tinker_tom")
EndFunction

Function RunScannerSelfDecode()
    if talkOpen || ScannerMsg == None
        return
    endif
    talkOpen = True
    talkSessionId += 1
    int sid = talkSessionId
    int btn = ScannerMsg.Show()
    if sid != talkSessionId
        return
    endif
    talkOpen = False
    if btn < 0 || btn == 1
        return
    endif
    if EffectiveStage() < 65
        AdvanceTo(65, "open_mode")
    endif
    AdvanceTo(100, "open_mode")
EndFunction

Function RunVirgilPlans()
    if talkOpen || VirgilPlansMsg == None
        return
    endif
    talkOpen = True
    talkSessionId += 1
    int sid = talkSessionId
    int btn = VirgilPlansMsg.Show()
    if sid != talkSessionId
        return
    endif
    talkOpen = False
    if btn < 0 || btn == 2
        return
    endif
    AdvanceTo(200, "virgil")
EndFunction

bool Function AreAllEngineersUnavailable()
    Actor stg = ResolveSturges()
    Actor tom = ResolveTinkerTom()
    Actor ing = ResolveIngram()
    return (stg == None || stg.IsDead()) && (tom == None || tom.IsDead()) && (ing == None || ing.IsDead())
EndFunction

Function RunOpenModeFallback()
    if talkOpen
        return
    endif
    if OpenModeFallbackMsg != None
        talkOpen = True
        talkSessionId += 1
        int sid = talkSessionId
        int btn = OpenModeFallbackMsg.Show()
        if sid != talkSessionId
            return
        endif
        talkOpen = False
        if btn < 0 || btn == 1
            return
        endif
    endif
    if TeleporterFaction != None
        TeleporterFaction.SetValue(0.0)
    endif
    Trace("mq206 faction_selected=0 reason=open_mode_engineers_unavailable")
    if EffectiveStage() < 300
        AdvanceTo(300, "open_mode")
    endif
    RunWorkbenchAssembly()
EndFunction

Function RunFactionPick()
    if talkOpen || FactionPickMsg == None
        return
    endif
    talkOpen = True
    talkSessionId += 1
    int sid = talkSessionId
    int btn = FactionPickMsg.Show()
    if sid != talkSessionId
        return
    endif
    talkOpen = False
    if btn < 0 || btn == 4
        return
    endif
    int chosen = 0
    if btn == 0
        chosen = 1
    elseif btn == 1
        chosen = 2
    elseif btn == 2
        chosen = 3
    else
        chosen = 0
    endif
    if TeleporterFaction != None
        TeleporterFaction.SetValue(chosen as float)
    endif
    Trace("mq206 faction_selected=" + chosen)
    if EffectiveStage() < 300
        AdvanceTo(300, "faction_pick")
    endif
    RunWorkbenchAssembly()
EndFunction

Function RunWorkbenchAssembly()
    if talkOpen || WorkbenchBuildMsg == None
        return
    endif
    talkOpen = True
    talkSessionId += 1
    int sid = talkSessionId
    bool keepOpen = True
    while keepOpen
        int btn = WorkbenchBuildMsg.Show()
        if sid != talkSessionId
            return
        endif
        if btn < 0 || btn == 5
            keepOpen = False
        elseif btn == 0 && BuiltPlatform != None
            BuiltPlatform.SetValue(1.0)
            Trace("mq206 stand_in_build part=platform kind=messagebox_counter")
            Trace("mq206 built part=platform")
        elseif btn == 1 && BuiltBeam != None
            BuiltBeam.SetValue(1.0)
            Trace("mq206 stand_in_build part=beam kind=messagebox_counter")
            Trace("mq206 built part=beam")
        elseif btn == 2 && BuiltDish != None
            BuiltDish.SetValue(1.0)
            Trace("mq206 stand_in_build part=dish kind=messagebox_counter")
            Trace("mq206 built part=dish")
        elseif btn == 3 && BuiltConsole != None
            BuiltConsole.SetValue(1.0)
            Trace("mq206 stand_in_build part=console kind=messagebox_counter")
            Trace("mq206 built part=console")
        elseif btn == 4
            if AllFourPartsBuilt()
                if EffectiveStage() < 350
                    AdvanceTo(350, "workbench")
                endif
                AdvanceTo(600, "workbench")
                AdvanceTo(700, "workbench")
                keepOpen = False
            else
                Trace("mq206 power_refused reason=parts_incomplete")
            endif
        endif
        if AllFourPartsBuilt() && EffectiveStage() < 350
            AdvanceTo(350, "workbench")
        endif
    endwhile
    talkOpen = False
EndFunction

Function RunRelayFire()
    if talkOpen || RelayFireMsg == None
        return
    endif
    talkOpen = True
    talkSessionId += 1
    int sid = talkSessionId
    int btn = RelayFireMsg.Show()
    if sid != talkSessionId
        return
    endif
    talkOpen = False
    if btn < 0 || btn == 1
        return
    endif
    FireRelayToInstitute(Game.GetPlayer(), "relay")
EndFunction

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
