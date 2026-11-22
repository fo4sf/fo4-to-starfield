Scriptname FO4SF_MQ105Quest extends Quest
{"Getting a Clue" (FO4SFMission.esm 0x000AB0, source-audited from Fallout 4's MQ105 0x0229E6).
 Story mode only (FO4SF_GameMode 0x000870 == 1; stops silently in Warfare mode == 2).
 Stages:
   10  = Objective 10: Sit down and brief Nick Valentine at his agency (DmndValentines01 0x01006B30)
   30  = Objective 30: Gain access to Kellogg's house (DmndStandsKellogg01 0x0106B72C, door 0x000021B4)
   60  = Objective 60: Search Kellogg's house for hidden room (button 0x0011E23C -> door 0x0011E235) & cigar clue
   80  = Objective 80: Inspect KelloggCigar01 (FO4SF_KelloggCigar 0x000AB5) and pick up trail with Dogmeat
   100 = Following trail west across Commonwealth toward Fort Hagen (00090A / merged -2456.84, -2781.07)
   200 = CompleteQuest -> set FO4SF_MQ106Armed=1 at Fort Hagen (FO4SFFortHagen.esm 0D RoofLoadDoorId 0x0547B0).
 W6 break-it safe: CLUE-01..05 (Nick/Geneva/Mayor/Dogmeat dead Open-Mode fallbacks, Master lockpick/direct entry
 to Kellogg's House, direct desk/button secret room trigger, direct Fort Hagen arrival bypassing Dogmeat pathing,
 OnPlayerLoadGame re-sync of secret door/enable markers across all 6 stages).}

Form Property XMarkerBase Auto Const
Actor Property NickValentine Auto Const
Actor Property Geneva Auto Const
Actor Property Dogmeat Auto Const
MiscObject Property KelloggCigar Auto Const
GlobalVariable Property KelloggHouseUnlocked Auto Const
GlobalVariable Property KelloggSecretOpened Auto Const
GlobalVariable Property MQ106Armed Auto Const
Message Property AgencyBriefMsg Auto Const
Message Property AgencyDossierMsg Auto Const
Message Property GenevaKeyMsg Auto Const
Message Property SecretRoomMsg Auto Const
Message Property TrailHandoffMsg Auto Const

string LogName = "fo4sf_mission"
string CorePlugin = "FO4TerrainCore.esm"
string CoreMarsPlugin = "FO4TerrainCore_Mars.esm"
string PortPlugin = "FO4Port.esm"
string FortHagenPlugin = "FO4SFFortHagen.esm"
string MissionPlugin = "FO4SFMission.esm"
int CommonwealthWorldId = 0x000803
int CommonwealthAnchorId = 0x0A775B

; Verified FO4Port.esm (interiors_b10) cell IDs
int ValentinesCellId = 0x006B30
int KelloggHouseCellId = 0x06B72C
int FortHagen01CellId = 0x00BA4B
int FortHagen02CellId = 0x00CFC6

; Verified FO4TerrainCore.esm Fort Hagen roof load door & marker (FO4SFFortHagen.esm 0D)
int FortHagenRoofDoorId = 0x0547B0
int FortHagenRoofMarkerId = 0x0A774C

; Verified local coords (FO4 / 70) + MergeOffset (-1200, -2700)
float DiamondCityLocalX = -216.36
float DiamondCityLocalY = -429.39
float DiamondCityLocalZ = 19.20
float FortHagenLocalX = -1256.84
float FortHagenLocalY = -81.07
float MergeOffsetX = -1200.0
float MergeOffsetY = -2700.0

float PlaceRadius = 300.0
float FortHagenArrivalRadius = 150.0
float TalkFallbackRadius = 3.5
float TalkFallbackSeconds = 8.0

bool instanceStarted = False
bool completed = False
bool actorsPlaced = False
bool dogmeatEnabled = False
bool talkOpen = False
int talkSessionId = 0
bool cigarGranted = False
float talkNearSec = 0.0
int applied = 0
int pendingStage = -1
string pendingStageBy = "other"
ObjectReference fortHagenDoorRef = None
ObjectReference nickTalkProxy = None
ObjectReference genevaTalkProxy = None
ObjectReference dogmeatTalkProxy = None

bool Function IsTestModeEnabled()
    GlobalVariable tm = Game.GetFormFromFile(0x000860, "FO4SFCoreValues.esm") as GlobalVariable
    return tm != None && tm.GetValue() != 0.0
EndFunction

bool Function CheckPredecessorGate()
{R5: MQ105 starts only after MQ104 completes (or FO4SF_MQ105Armed >= 1) or TestMode.}
    if IsTestModeEnabled()
        return True
    endif
    GlobalVariable armed = Game.GetFormFromFile(0x000A89, MissionPlugin) as GlobalVariable
    if armed != None && armed.GetValue() >= 1.0
        return True
    endif
    Quest mq104 = Game.GetFormFromFile(0x000A80, MissionPlugin) as Quest
    if mq104 != None && (mq104.IsCompleted() || mq104.GetStage() >= 200)
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
{B1/B4 resilience: max(GetStage(), applied) so lagged engine GetStage() never stalls agency, Geneva, or trail handlers.}
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
{B2/T1 guard: reject interiors (e.g. FO4SF_MapMarkersHop 100008F4), null/wrong WorldSpace, or out-of-Commonwealth XY.}
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
{B2 mid-tick recheck before MoveTo so a FO4SF_MapMarkersHop ComeBack jump never misplaces hub actors.}
    if !IsCommonwealthExterior(player)
        return False
    endif
    float dx = player.GetPositionX() - snapX
    float dy = player.GetPositionY() - snapY
    float dz = player.GetPositionZ() - snapZ
    return (dx * dx + dy * dy + dz * dz) <= 25.0
EndFunction

Actor Function ResolveNick()
    if NickValentine != None
        return NickValentine
    endif
    return Game.GetFormFromFile(0x000A82, MissionPlugin) as Actor
EndFunction

Actor Function ResolveGeneva()
    if Geneva != None
        return Geneva
    endif
    return Game.GetFormFromFile(0x000AB2, MissionPlugin) as Actor
EndFunction

Actor Function ResolveDogmeat()
    if Dogmeat != None
        return Dogmeat
    endif
    return Game.GetFormFromFile(0x000AB4, MissionPlugin) as Actor
EndFunction

bool Function IsNickUnavailable()
    Actor nick = ResolveNick()
    return nick == None || nick.IsDead()
EndFunction

bool Function IsGenevaUnavailable()
    Actor gen = ResolveGeneva()
    return gen == None || gen.IsDead()
EndFunction

bool Function IsDogmeatUnavailable()
    Actor dog = ResolveDogmeat()
    return dog == None || dog.IsDead()
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

bool Function IsAtFortHagen(Actor player)
    if player == None
        return False
    endif
    if IsInCellId(player, FortHagen01CellId) || IsInCellId(player, FortHagen02CellId)
        return True
    endif
    if IsCommonwealthExterior(player)
        string cp = ActiveCorePlugin()
        if cp != ""
            ObjectReference marker = Game.GetFormFromFile(FortHagenRoofMarkerId, cp) as ObjectReference
            if marker != None && player.GetDistance(marker) <= FortHagenArrivalRadius
                return True
            endif
        endif
        float fx = FortHagenLocalX + MergeOffsetX
        float fy = FortHagenLocalY + MergeOffsetY
        float dx = player.GetPositionX() - fx
        float dy = player.GetPositionY() - fy
        if dx * dx + dy * dy <= FortHagenArrivalRadius * FortHagenArrivalRadius
            return True
        endif
    endif
    return False
EndFunction

Function AdvanceTo(int n, string by = "Trigger")
    pendingStage = n
    pendingStageBy = by
    SetStage(n)
    if n > applied
        applied = n
        Trace("mq105 stage " + n + " by=" + by)
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
        Trace("mq105 stage " + auiStageID + " by=" + cause)
        ApplyStage(auiStageID, cause)
    endif
EndEvent

Function SyncClueGlobals(int st, string by)
    if st >= 60 && KelloggHouseUnlocked != None
        KelloggHouseUnlocked.SetValue(1.0)
    endif
    if st >= 80 && KelloggSecretOpened != None
        KelloggSecretOpened.SetValue(1.0)
        Trace("mq105 secret_room unlocked by=" + by)
    endif
EndFunction

Function GrantKelloggCigar()
    if cigarGranted
        return
    endif
    Actor player = Game.GetPlayer()
    if player != None && KelloggCigar != None
        player.AddItem(KelloggCigar, 1, True)
        cigarGranted = True
        Trace("mq105 kellogg_cigar granted=true")
    endif
EndFunction

Function ApplyStage(int n, string by)
    if n == 10
        SetObjectiveDisplayed(10, True, True)
        SetActive(True)
    elseif n == 30
        SetObjectiveCompleted(10)
        SetObjectiveDisplayed(30, True, True)
    elseif n == 60
        SyncClueGlobals(60, by)
        SetObjectiveCompleted(10)
        SetObjectiveCompleted(30)
        SetObjectiveDisplayed(60, True, True)
    elseif n == 80
        SyncClueGlobals(80, by)
        GrantKelloggCigar()
        SetObjectiveCompleted(60)
        SetObjectiveDisplayed(80, True, True)
    elseif n == 100
        SyncClueGlobals(100, by)
        GrantKelloggCigar()
        SetObjectiveDisplayed(80, True, True)
    elseif n == 200
        if completed
            return
        endif
        completed = True
        ReleaseAllActors()
        SyncClueGlobals(200, by)
        SetObjectiveCompleted(80)
        if MQ106Armed != None
            MQ106Armed.SetValue(1.0)
        endif
        bool fhInstalled = Game.IsPluginInstalled(FortHagenPlugin)
        CompleteQuest()
        CancelTimer(1)
        Quest mq106 = Game.GetFormFromFile(0x000AD0, MissionPlugin) as Quest
        bool started106 = False
        if mq106 != None && !mq106.IsRunning() && !mq106.IsCompleted()
            mq106.StartNoWait()
            started106 = True
        endif
        Trace("mq105 complete stage=200 mq106_armed=1 forthagen_plugin=" + fhInstalled + " by=" + by)
        Trace("mq106 start_requested ok=" + started106)
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
        Trace("mission gate mode=2 started=false quest=mq105")
        Stop()
        return
    endif
    if !CheckPredecessorGate()
        Trace("mq105 gate_deferred reason=mq104_incomplete")
        instanceStarted = False
        Stop()
        return
    endif
    if !IsRunning()
        Start()
    endif
    Actor player = Game.GetPlayer()
    if player != None
        RegisterForRemoteEvent(player, "OnPlayerLoadGame")
    endif
    BindRefs()
    AdvanceTo(10, "Trigger")
    if player != None && IsInCellId(player, KelloggHouseCellId)
        AdvanceTo(60, "out_of_order")
    elseif player != None && IsAtFortHagen(player)
        AdvanceTo(200, "out_of_order")
    endif
    Trace("mq105 init stage=" + EffectiveStage() + " kellogg_cell=0x06B72C forthagen_door=0x0547B0")
    if !completed
        StartTimer(1.0, 1)
    endif
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    talkOpen = False
    talkSessionId += 1
    actorsPlaced = False
    talkNearSec = 0.0
    int st = EffectiveStage()
    Trace("mq105 reload stage=" + st + " complete=" + completed)
    if !completed
        if !IsRunning()
            Start()
        endif
        if applied > GetStage()
            SetStage(applied)
        endif
        fortHagenDoorRef = None
        BindRefs()
        SyncClueGlobals(st, "reload")
        StartTimer(1.0, 1)
    endif
EndEvent

Function BindRefs()
    Actor nick = ResolveNick()
    if nick != None && !nick.IsDead()
        nick.AllowPCDialogue(True)
        nick.BlockActivation(False, False)
        RegisterForRemoteEvent(nick, "OnActivate")
    endif
    Actor gen = ResolveGeneva()
    if gen != None && !gen.IsDead()
        gen.AllowPCDialogue(True)
        gen.BlockActivation(False, False)
        RegisterForRemoteEvent(gen, "OnActivate")
    endif
    Actor dog = ResolveDogmeat()
    if dog != None && !dog.IsDead()
        dog.AllowPCDialogue(True)
        dog.BlockActivation(False, False)
        RegisterForRemoteEvent(dog, "OnActivate")
    endif
    string cp = ActiveCorePlugin()
    if cp != ""
        ObjectReference fhDoor = Game.GetFormFromFile(FortHagenRoofDoorId, cp) as ObjectReference
        if fhDoor != None && fhDoor != fortHagenDoorRef
            fortHagenDoorRef = fhDoor
            RegisterForRemoteEvent(fortHagenDoorRef, "OnActivate")
        endif
    endif
EndFunction

Function ReleaseIfInCombat(Actor a)
    if a != None && !a.IsDead() && a.GetCombatState() != 0
        a.SetRestrained(False)
    endif
EndFunction

Function ReleaseAllActors()
    Actor gen = ResolveGeneva()
    if gen != None && !gen.IsDead()
        gen.SetRestrained(False)
    endif
    Actor dog = ResolveDogmeat()
    if dog != None && !dog.IsDead()
        dog.SetRestrained(False)
    endif
EndFunction

Function PlaceHubActors(Actor player)
    if !IsCommonwealthExterior(player)
        return
    endif
    int st = EffectiveStage()
    float snapX = player.GetPositionX()
    float snapY = player.GetPositionY()
    float snapZ = player.GetPositionZ()
    float gx = DiamondCityLocalX + MergeOffsetX
    float gy = DiamondCityLocalY + MergeOffsetY
    float gz = DiamondCityLocalZ
    Actor nick = ResolveNick()
    if nick != None && !nick.IsDead()
        if nick.IsDisabled()
            nick.EnableNoWait(False)
            BindRefs()
        endif
        if nickTalkProxy == None || nickTalkProxy.IsDeleted()
            Activator nActi = Game.GetFormFromFile(0x000970, MissionPlugin) as Activator
            if nActi != None
                nickTalkProxy = nick.PlaceAtMe(nActi, 1, True, False, False)
                if nickTalkProxy != None
                    nickTalkProxy.MoveTo(nick, 0.0, 0.0, 1.0, False, False)
                    RegisterForRemoteEvent(nickTalkProxy, "OnActivate")
                endif
            endif
        endif
    endif
    Actor gen = ResolveGeneva()
    if gen != None && !gen.IsDead()
        if gen.IsDisabled()
            gen.EnableNoWait(False)
            BindRefs()
        endif
        if !IsPlayerStableAt(player, snapX, snapY, snapZ)
            return
        endif
        gen.SetRestrained(False)
        gen.MoveTo(player, (gx - 1.5) - snapX, (gy + 4.0) - snapY, gz - snapZ, False, False)
        if gen.GetCombatState() == 0
            gen.SetRestrained(True)
        endif
        gen.AllowPCDialogue(True)
        if genevaTalkProxy == None || genevaTalkProxy.IsDeleted()
            Activator gActi = Game.GetFormFromFile(0x000970, MissionPlugin) as Activator
            if gActi != None
                genevaTalkProxy = gen.PlaceAtMe(gActi, 1, True, False, False)
                if genevaTalkProxy != None
                    genevaTalkProxy.MoveTo(gen, 0.0, 0.0, 1.0, False, False)
                    RegisterForRemoteEvent(genevaTalkProxy, "OnActivate")
                endif
            endif
        endif
    endif
    if st >= 80
        Actor dog = ResolveDogmeat()
        if dog != None && !dog.IsDead()
            if dog.IsDisabled()
                dog.EnableNoWait(False)
                BindRefs()
            endif
            if !IsPlayerStableAt(player, snapX, snapY, snapZ)
                return
            endif
            dog.SetRestrained(False)
            dog.MoveTo(player, (gx - 5.5) - snapX, (gy - 5.5) - snapY, gz - snapZ, False, False)
            if dog.GetCombatState() == 0
                dog.SetRestrained(True)
            endif
            dog.AllowPCDialogue(True)
            if dogmeatTalkProxy == None || dogmeatTalkProxy.IsDeleted()
                Activator dActi = Game.GetFormFromFile(0x000970, MissionPlugin) as Activator
                if dActi != None
                    dogmeatTalkProxy = dog.PlaceAtMe(dActi, 1, True, False, False)
                    if dogmeatTalkProxy != None
                        dogmeatTalkProxy.MoveTo(dog, 0.0, 0.0, 1.0, False, False)
                        RegisterForRemoteEvent(dogmeatTalkProxy, "OnActivate")
                    endif
                endif
            endif
        endif
        dogmeatEnabled = True
    endif
    if !IsPlayerStableAt(player, snapX, snapY, snapZ)
        return
    endif
    actorsPlaced = True
    Trace("mq105 hub actors placed diamond_city=true")
EndFunction

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
    ReleaseIfInCombat(ResolveGeneva())
    ReleaseIfInCombat(ResolveDogmeat())
    Actor player = Game.GetPlayer()
    if player != None
        if IsCommonwealthExterior(player)
            float gx = DiamondCityLocalX + MergeOffsetX
            float gy = DiamondCityLocalY + MergeOffsetY
            float dx = player.GetPositionX() - gx
            float dy = player.GetPositionY() - gy
            if dx * dx + dy * dy <= PlaceRadius * PlaceRadius && (!actorsPlaced || (st >= 80 && !dogmeatEnabled))
                PlaceHubActors(player)
            endif
        endif

        ; CLUE-05 Open-Mode dead-Nick fallback at agency / Diamond City hub
        if st == 10 && IsNickUnavailable()
            Trace("mq105 open_mode nick_unavailable -> dossier stage 30")
            if AgencyDossierMsg != None
                AgencyDossierMsg.Show()
            endif
            AdvanceTo(30, "open_mode")
            st = EffectiveStage()
        endif

        ; CLUE-01 Open-Mode dead-Geneva fallback OR entering DmndStandsKellogg01 directly (out-of-order / lockpick)
        if st == 30 && (IsGenevaUnavailable() || IsInCellId(player, KelloggHouseCellId))
            string why = "kellogg_entry"
            if IsGenevaUnavailable()
                why = "open_mode"
            endif
            AdvanceTo(60, why)
            st = EffectiveStage()
        endif

        ; CLUE-02 / CLUE-03 inside Kellogg's house: secret room button/desk inspection -> cigar clue
        if st == 60 && IsInCellId(player, KelloggHouseCellId)
            if SecretRoomMsg != None
                SecretRoomMsg.Show()
            endif
            AdvanceTo(80, "secret_button")
            st = EffectiveStage()
        endif

        ; CLUE-04 / CLUE-05 Open-Mode dead-Dogmeat fallback marks Fort Hagen directly
        if st == 80 && IsDogmeatUnavailable()
            Trace("mq105 open_mode dogmeat_unavailable -> direct fort_hagen stage 100")
            AdvanceTo(100, "open_mode")
            st = EffectiveStage()
        endif

        ; CLUE-04 Direct arrival at Fort Hagen (exterior 00090A / RoofMarkerId 0x0A774C / FortHagen01 / FortHagen02)
        if st >= 30 && IsAtFortHagen(player)
            AdvanceTo(200, "fort_hagen_arrival")
            return
        endif
        CheckTalkFallback(player, st)
    endif
    if fortHagenDoorRef == None
        BindRefs()
    endif
    if !completed
        StartTimer(1.0, 1)
    endif
EndEvent

Function RunNickTalk(int st)
    if talkOpen || completed
        return
    endif
    talkOpen = True
    int myTalkSession = talkSessionId
    if st == 10
        int nbtn = 0
        if AgencyBriefMsg != None
            nbtn = AgencyBriefMsg.Show()
            Trace("mq105 agency brief choice button=" + nbtn)
        endif
        if talkSessionId == myTalkSession && nbtn >= 0 && nbtn != 3
            AdvanceTo(30, "nick_brief")
        endif
    elseif st == 60
        int sbtn = 0
        if SecretRoomMsg != None
            sbtn = SecretRoomMsg.Show()
        endif
        if talkSessionId == myTalkSession && sbtn >= 0 && sbtn != 1
            AdvanceTo(80, "secret_button")
        endif
    endif
    talkOpen = False
EndFunction

Function RunGenevaTalk(int st)
    if talkOpen || completed
        return
    endif
    talkOpen = True
    int myTalkSession = talkSessionId
    if st < 60
        int gbtn = 0
        if GenevaKeyMsg != None
            gbtn = GenevaKeyMsg.Show()
            Trace("mq105 geneva key choice button=" + gbtn)
        endif
        if talkSessionId == myTalkSession && gbtn >= 0 && gbtn != 3
            AdvanceTo(60, "geneva_key")
        endif
    endif
    talkOpen = False
EndFunction

Function RunDogmeatTalk(int st)
    if talkOpen || completed
        return
    endif
    talkOpen = True
    int myTalkSession = talkSessionId
    int dbtn = 0
    if TrailHandoffMsg != None
        dbtn = TrailHandoffMsg.Show()
        Trace("mq105 trail handoff choice button=" + dbtn)
    endif
    if talkSessionId == myTalkSession && dbtn >= 0
        if st < 80
            AdvanceTo(80, "out_of_order")
        endif
        AdvanceTo(100, "dogmeat_trail")
    endif
    talkOpen = False
EndFunction

Function CheckTalkFallback(Actor player, int st)
{R4: Timed proximity fallback while Nick, Geneva, or Dogmeat is alive so topicless OnActivate never stalls.}
    if talkOpen || completed || player == None
        talkNearSec = 0.0
        return
    endif
    if st == 10 || st == 60
        Actor nick = ResolveNick()
        if nick != None && !nick.IsDead() && !nick.IsDisabled() && nick.Is3DLoaded() && player.GetDistance(nick) <= TalkFallbackRadius
            talkNearSec += 1.0
            if talkNearSec >= TalkFallbackSeconds
                talkNearSec = 0.0
                Trace("mq105 talk_fallback actor=nick stage=" + st + " near_sec=" + TalkFallbackSeconds)
                RunNickTalk(st)
            endif
            return
        endif
    elseif st == 30
        Actor gen = ResolveGeneva()
        if gen != None && !gen.IsDead() && !gen.IsDisabled() && gen.Is3DLoaded() && player.GetDistance(gen) <= TalkFallbackRadius
            talkNearSec += 1.0
            if talkNearSec >= TalkFallbackSeconds
                talkNearSec = 0.0
                Trace("mq105 talk_fallback actor=geneva stage=30 near_sec=" + TalkFallbackSeconds)
                RunGenevaTalk(st)
            endif
            return
        endif
    elseif st == 80
        Actor dog = ResolveDogmeat()
        if dog != None && !dog.IsDead() && !dog.IsDisabled() && dog.Is3DLoaded() && player.GetDistance(dog) <= TalkFallbackRadius
            talkNearSec += 1.0
            if talkNearSec >= TalkFallbackSeconds
                talkNearSec = 0.0
                Trace("mq105 talk_fallback actor=dogmeat stage=80 near_sec=" + TalkFallbackSeconds)
                RunDogmeatTalk(st)
            endif
            return
        endif
    endif
    talkNearSec = 0.0
EndFunction

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    if completed || akActionRef != Game.GetPlayer() || talkOpen
        return
    endif
    int st = EffectiveStage()
    Actor nick = ResolveNick()
    Actor gen = ResolveGeneva()
    Actor dog = ResolveDogmeat()

    if (nick != None && akSender == nick) || (nickTalkProxy != None && akSender == nickTalkProxy)
        RunNickTalk(st)
    elseif (gen != None && akSender == gen) || (genevaTalkProxy != None && akSender == genevaTalkProxy)
        RunGenevaTalk(st)
    elseif (dog != None && akSender == dog) || (dogmeatTalkProxy != None && akSender == dogmeatTalkProxy)
        RunDogmeatTalk(st)
    elseif fortHagenDoorRef != None && akSender == fortHagenDoorRef
        ; Activating Fort Hagen roof load door (0x0547B0) completes MQ105 and hands off to FO4SFFortHagen.esm (0D)
        AdvanceTo(200, "fort_hagen_door")
    endif
EndEvent

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
