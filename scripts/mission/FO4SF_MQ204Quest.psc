Scriptname FO4SF_MQ204Quest extends Quest
{"The Glowing Sea" (FO4SFMission.esm 0x000B10, source-audited from Fallout 4's MQ204 0x06B500).
 Story mode only (FO4SF_GameMode 0x000870 == 1; stops silently in Warfare mode == 2).
 Stages:
   10  = Entered MQ204 -> immediately displays Objective 15 (Search the Glowing Sea for Virgil)
   15  = Objective 15: Reach Crater of Atom (Mother Isolde or Open-Mode VirgilNote) / southwest Glowing Sea
   20  = Objective 20: Reach Virgil inside Rocky Cave (FO4Port_VirgilsLab01 0x069B10)
   50  = Virgil briefed / LabTerminal read -> arming Courser Hunt
   200 = CompleteQuest -> set FO4SF_MQ206Armed=1 and StartNoWait() on FO4SF_MQ206 (0x000B30).
 Track 1 vs Track 2 rads:
   - When FO4SFRads.esm is NOT installed (13-plugin Track 1), applies a bounded scripted rads tick inside the
     southwest Glowing Sea quadrant (X <= -2000, Y <= -3800) scaled by FO4SF_RadResist (0x000804) onto
     FO4SF_Rads (0x000800), setting FO4SF_GlowingSeaRadsActive=1 while exposed.
   - When FO4SFRads.esm IS installed (22-plugin Track 2), defers ambient rads to FO4SFRads.esm so rads never double-stack.
 W6 break-it safe: GLOW-01..05 (Virgil IgnoreFriendlyHits + StopCombat against PA Targeting HUD aggro,
 dead-Isolde VirgilNote fallback, direct Rocky Cave entry skipping Crater, dead-Virgil LabTerminalProxyActi fallback).}

Form Property XMarkerBase Auto Const
Actor Property MotherIsolde Auto Const
Actor Property Virgil Auto Const
MiscObject Property VirgilNote Auto Const
Activator Property LabTerminalProxyActi Auto Const
GlobalVariable Property GlowingSeaRadsActive Auto Const
GlobalVariable Property MQ206Armed Auto Const
Message Property IsoldeTalkMsg Auto Const
Message Property VirgilNoteMsg Auto Const
Message Property VirgilTalkMsg Auto Const
Message Property LabTerminalMsg Auto Const

string LogName = "fo4sf_mission"
string CorePlugin = "FO4TerrainCore.esm"
string CoreMarsPlugin = "FO4TerrainCore_Mars.esm"
string PortPlugin = "FO4Port.esm"
string CoreValuesPlugin = "FO4SFCoreValues.esm"
string RadsPlugin = "FO4SFRads.esm"
string MissionPlugin = "FO4SFMission.esm"
int CommonwealthAnchorId = 0x0A775B
int CommonwealthFallbackAnchorId = 0x005C50

; Verified FO4Port.esm cell ID
int VirgilsLabCellId = 0x069B10

; Verified merged coordinates (Crater -2624.44, -4357.85; Rocky Cave -2862.82, -4653.27)
float CraterX = -2624.44
float CraterY = -4357.85
float CraterZ = 107.64
float RockyCaveX = -2862.82
float RockyCaveY = -4653.27
float RockyCaveZ = 143.19
float GlowingSeaMaxX = -2000.0
float GlowingSeaMaxY = -3800.0
float MergeOffsetX = -1200.0
float MergeOffsetY = -2700.0

float PlaceRadius = 300.0
float ArrivalRadius = 110.0
float TalkFallbackRadius = 3.5
float TalkFallbackSeconds = 8.0

bool instanceStarted = False
bool gateDeferred = False
bool completed = False
bool isoldePlaced = False
bool virgilPlaced = False
bool noteGranted = False
bool radsDeferredLogged = False
bool talkOpen = False
int talkSessionId = 0
int applied = 0
int pendingStage = -1
string pendingStageBy = "other"
float talkNearSec = 0.0
ObjectReference labTerminalProxyRef = None
ObjectReference isoldeTalkProxy = None
ObjectReference virgilTalkProxy = None

bool Function IsTestModeEnabled()
    GlobalVariable tm = Game.GetFormFromFile(0x000860, CoreValuesPlugin) as GlobalVariable
    return tm != None && tm.GetValue() != 0.0
EndFunction

bool Function CheckPredecessorGate()
{R5: MQ204 starts strictly behind MQ203 completion (stage >= 300 or FO4SF_MQ204Armed >= 1) unless TestMode is on.}
    if IsTestModeEnabled()
        return True
    endif
    GlobalVariable armed = Game.GetFormFromFile(0x000AF5, MissionPlugin) as GlobalVariable
    if armed != None && armed.GetValue() >= 1.0
        return True
    endif
    Quest mq203 = Game.GetFormFromFile(0x000AF0, MissionPlugin) as Quest
    if mq203 != None && (mq203.IsCompleted() || mq203.GetStage() >= 300)
        return True
    endif
    return False
EndFunction

bool Function IsWarfareMode()
    GlobalVariable gm = Game.GetFormFromFile(0x000870, CoreValuesPlugin) as GlobalVariable
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
    ObjectReference fallbackAnchor = Game.GetFormFromFile(CommonwealthFallbackAnchorId, cp) as ObjectReference
    if fallbackAnchor != None
        WorldSpace fws = fallbackAnchor.GetWorldSpace()
        if fws != None
            return fws
        endif
    endif
    return None
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

Actor Function ResolveIsolde()
    if MotherIsolde != None
        return MotherIsolde
    endif
    return Game.GetFormFromFile(0x000B12, MissionPlugin) as Actor
EndFunction

Actor Function ResolveVirgil()
    if Virgil != None
        return Virgil
    endif
    return Game.GetFormFromFile(0x000B14, MissionPlugin) as Actor
EndFunction

bool Function IsIsoldeUnavailable()
    Actor iso = ResolveIsolde()
    return iso == None || iso.IsDead()
EndFunction

bool Function IsVirgilUnavailable()
    Actor vg = ResolveVirgil()
    return vg == None || vg.IsDead()
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

bool Function IsInGlowingSeaZone(Actor player)
    if !IsCommonwealthExterior(player)
        return False
    endif
    return player.GetPositionX() <= GlowingSeaMaxX && player.GetPositionY() <= GlowingSeaMaxY
EndFunction

Function ApplyGlowingSeaRadsIfEnabled(Actor player)
{R7 / 15 Nov owner environment-damage rule (S13 row 2b): Fallout radiation comes strictly from our S9 FO4SFRads.esm
 system, never ad-hoc ambient damage in the 13-plugin player opening bundle. Gated OFF unless FO4SFRads.esm is loaded.}
    if player == None
        return
    endif
    if !Game.IsPluginInstalled(RadsPlugin)
        if GlowingSeaRadsActive != None
            GlowingSeaRadsActive.SetValue(0.0)
        endif
        if !radsDeferredLogged && IsInGlowingSeaZone(player)
            radsDeferredLogged = True
            Trace("mq204 rads_gated active=false reason=s9_fo4sfrads_absent")
        endif
        return
    endif
    bool inZone = IsInGlowingSeaZone(player)
    if !inZone
        if GlowingSeaRadsActive != None
            GlowingSeaRadsActive.SetValue(0.0)
        endif
        return
    endif
    if GlowingSeaRadsActive != None
        GlowingSeaRadsActive.SetValue(1.0)
    endif
    ActorValue radsAv = Game.GetFormFromFile(0x000800, CoreValuesPlugin) as ActorValue
    if radsAv == None
        return
    endif
    float resist = 0.0
    ActorValue resistAv = Game.GetFormFromFile(0x000804, CoreValuesPlugin) as ActorValue
    if resistAv != None
        resist = player.GetValue(resistAv)
    endif
    if resist < 0.0
        resist = 0.0
    endif
    float mult = 100.0 / (100.0 + resist)
    float delta = 6.0 * mult
    float cur = player.GetValue(radsAv)
    if cur + delta > 950.0
        delta = 950.0 - cur
    endif
    if delta > 0.01
        player.ModValue(radsAv, delta)
    endif
EndFunction

Function KeepVirgilPeaceful(Actor player)
    Actor vg = ResolveVirgil()
    if vg != None && !vg.IsDead()
        vg.IgnoreFriendlyHits(True)
        if player != None && vg.GetCombatTarget() == player
            vg.StopCombat()
            Trace("mq204 virgil stopcombat reason=pa_targeting_guard")
        endif
    endif
EndFunction

Function GrantVirgilNote(string why)
    if noteGranted
        return
    endif
    Actor player = Game.GetPlayer()
    if player != None && VirgilNote != None
        if player.GetItemCount(VirgilNote) <= 0
            player.AddItem(VirgilNote, 1, True)
        endif
        noteGranted = True
        Trace("mq204 virgil_note granted=true by=" + why)
    endif
EndFunction

Function AdvanceTo(int n, string by = "Trigger")
    pendingStage = n
    pendingStageBy = by
    SetStage(n)
    if n > applied
        applied = n
        Trace("mq204 stage " + n + " by=" + by)
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
        Trace("mq204 stage " + auiStageID + " by=" + cause)
        ApplyStage(auiStageID, cause)
    endif
EndEvent

Function ApplyStage(int n, string by)
    if n == 10 || n == 15
        SetObjectiveDisplayed(15, True, True)
        SetActive(True)
    elseif n == 20
        SetObjectiveCompleted(15)
        SetObjectiveDisplayed(20, True, True)
    elseif n == 50
        SetObjectiveCompleted(15)
        SetObjectiveCompleted(20)
    elseif n == 200
        if completed
            return
        endif
        completed = True
        ReleaseAllActors()
        SetObjectiveCompleted(15)
        SetObjectiveCompleted(20)
        if GlowingSeaRadsActive != None
            GlowingSeaRadsActive.SetValue(0.0)
        endif
        if MQ206Armed != None
            MQ206Armed.SetValue(1.0)
        endif
        CompleteQuest()
        CancelTimer(1)
        Quest mq206 = Game.GetFormFromFile(0x000B30, MissionPlugin) as Quest
        bool started206 = False
        if mq206 != None && !mq206.IsCompleted()
            if mq206.IsRunning()
                FO4SF_MQ206Quest nextMq206 = mq206 as FO4SF_MQ206Quest
                if nextMq206 != None
                    nextMq206.WakeFromPredecessor()
                endif
                started206 = True
            else
                mq206.StartNoWait()
                started206 = True
            endif
        endif
        Trace("mq204 complete stage=200 mq206_armed=1 mq206_started=" + started206 + " rads_plugin=" + Game.IsPluginInstalled(RadsPlugin) + " by=" + by)
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
        Trace("mission gate mode=2 started=false quest=mq204")
        Stop()
        return
    endif
    if !CheckPredecessorGate()
        Trace("mq204 gate_deferred reason=mq203_incomplete")
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
    AdvanceTo(15, "Trigger")
    if player != None && (IsInCellId(player, VirgilsLabCellId) || IsNearXY(player, RockyCaveX, RockyCaveY, ArrivalRadius))
        AdvanceTo(20, "out_of_order")
    endif
    Trace("mq204 init stage=" + EffectiveStage() + " rads_plugin=" + Game.IsPluginInstalled(RadsPlugin))
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
        Trace("mq204 gate_resumed")
        StartQuestInstance()
    endif
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    talkOpen = False
    talkSessionId += 1
    isoldePlaced = False
    virgilPlaced = False
    talkNearSec = 0.0
    if gateDeferred && !instanceStarted
        WakeFromPredecessor()
        return
    endif
    int st = EffectiveStage()
    Trace("mq204 reload stage=" + st + " complete=" + completed)
    if !completed
        if !IsRunning()
            Start()
        endif
        if applied > GetStage()
            SetStage(applied)
        endif
        BindRefs()
        StartTimer(1.0, 1)
    endif
EndEvent

Function BindRefs()
    Actor iso = ResolveIsolde()
    if iso != None && !iso.IsDead()
        iso.AllowPCDialogue(True)
        iso.BlockActivation(False, False)
        RegisterForRemoteEvent(iso, "OnActivate")
    endif
    Actor vg = ResolveVirgil()
    if vg != None && !vg.IsDead()
        vg.AllowPCDialogue(True)
        vg.BlockActivation(False, False)
        vg.IgnoreFriendlyHits(True)
        RegisterForRemoteEvent(vg, "OnActivate")
    endif
EndFunction

Function ReleaseAllActors()
    Actor iso = ResolveIsolde()
    if iso != None && !iso.IsDead()
        iso.SetRestrained(False)
    endif
    Actor vg = ResolveVirgil()
    if vg != None && !vg.IsDead()
        vg.SetRestrained(False)
    endif
EndFunction

Function ReleaseIfInCombat(Actor a)
    if a != None && !a.IsDead() && a.GetCombatState() != 0
        a.SetRestrained(False)
    endif
EndFunction

Function PlaceIsolde(Actor player)
    if !IsCommonwealthExterior(player) || isoldePlaced || EffectiveStage() < 15
        return
    endif
    Actor iso = ResolveIsolde()
    float snapX = player.GetPositionX()
    float snapY = player.GetPositionY()
    float snapZ = player.GetPositionZ()
    if iso != None && !iso.IsDead()
        if iso.IsDisabled()
            iso.EnableNoWait(False)
            BindRefs()
        endif
        if !IsPlayerStableAt(player, snapX, snapY, snapZ)
            return
        endif
        iso.SetRestrained(False)
        iso.MoveTo(player, CraterX - snapX, CraterY - snapY, CraterZ - snapZ, False, False)
        if iso.GetCombatState() == 0
            iso.SetRestrained(True)
        endif
        iso.AllowPCDialogue(True)
        if isoldeTalkProxy == None || isoldeTalkProxy.IsDeleted()
            Activator iActi = Game.GetFormFromFile(0x000B19, MissionPlugin) as Activator
            if iActi != None
                isoldeTalkProxy = iso.PlaceAtMe(iActi, 1, True, False, False)
                if isoldeTalkProxy != None
                    isoldeTalkProxy.MoveTo(iso, 0.0, 0.0, 1.0, False, False)
                    RegisterForRemoteEvent(isoldeTalkProxy, "OnActivate")
                endif
            endif
        endif
    endif
    if !IsPlayerStableAt(player, snapX, snapY, snapZ)
        return
    endif
    isoldePlaced = True
    Trace("mq204 isolde placed crater=true")
EndFunction

Function PlaceVirgil(Actor player)
    if !IsCommonwealthExterior(player) || virgilPlaced || EffectiveStage() < 20
        return
    endif
    Actor vg = ResolveVirgil()
    float snapX = player.GetPositionX()
    float snapY = player.GetPositionY()
    float snapZ = player.GetPositionZ()
    if vg != None && !vg.IsDead()
        if vg.IsDisabled()
            vg.EnableNoWait(False)
            BindRefs()
        endif
        if !IsPlayerStableAt(player, snapX, snapY, snapZ)
            return
        endif
        vg.SetRestrained(False)
        vg.MoveTo(player, RockyCaveX - snapX, RockyCaveY - snapY, RockyCaveZ - snapZ, False, False)
        if vg.GetCombatState() == 0
            vg.SetRestrained(True)
        endif
        vg.AllowPCDialogue(True)
        vg.IgnoreFriendlyHits(True)
        if virgilTalkProxy == None || virgilTalkProxy.IsDeleted()
            Activator vActi = Game.GetFormFromFile(0x000B1A, MissionPlugin) as Activator
            if vActi != None
                virgilTalkProxy = vg.PlaceAtMe(vActi, 1, True, False, False)
                if virgilTalkProxy != None
                    virgilTalkProxy.MoveTo(vg, 0.0, 0.0, 1.0, False, False)
                    RegisterForRemoteEvent(virgilTalkProxy, "OnActivate")
                endif
            endif
        endif
    endif
    if !IsPlayerStableAt(player, snapX, snapY, snapZ)
        return
    endif
    virgilPlaced = True
    Trace("mq204 virgil placed rocky_cave=true")
EndFunction

Function EnsureLabTerminalProxy(Actor player)
    if LabTerminalProxyActi == None || player == None
        return
    endif
    if labTerminalProxyRef != None && !labTerminalProxyRef.IsDeleted()
        return
    endif
    if IsInCellId(player, VirgilsLabCellId) || IsNearXY(player, RockyCaveX, RockyCaveY, PlaceRadius)
        float snapX = player.GetPositionX()
        float snapY = player.GetPositionY()
        float snapZ = player.GetPositionZ()
        labTerminalProxyRef = player.PlaceAtMe(LabTerminalProxyActi, 1, True, False, False)
        if labTerminalProxyRef != None
            if IsCommonwealthExterior(player) && IsPlayerStableAt(player, snapX, snapY, snapZ)
                labTerminalProxyRef.MoveTo(player, (RockyCaveX + 2.5) - snapX, (RockyCaveY + 2.5) - snapY, (RockyCaveZ + 1.0) - snapZ, False, False)
            else
                labTerminalProxyRef.MoveTo(player, 2.0, 2.0, 0.5, False, False)
            endif
            RegisterForRemoteEvent(labTerminalProxyRef, "OnActivate")
            Trace("mq204 lab terminal proxy spawned")
        endif
    endif
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
    Actor player = Game.GetPlayer()
    if player == None
        StartTimer(1.0, 1)
        return
    endif

    ReleaseIfInCombat(ResolveIsolde())
    KeepVirgilPeaceful(player)
    ApplyGlowingSeaRadsIfEnabled(player)

    if IsNearXY(player, CraterX, CraterY, PlaceRadius) && !isoldePlaced
        PlaceIsolde(player)
    endif
    if IsNearXY(player, RockyCaveX, RockyCaveY, PlaceRadius) && !virgilPlaced
        PlaceVirgil(player)
    endif
    if IsInCellId(player, VirgilsLabCellId) || IsNearXY(player, RockyCaveX, RockyCaveY, PlaceRadius)
        EnsureLabTerminalProxy(player)
    endif

    ; Open-Mode dead-Isolde fallback at Crater of Atom
    if st < 20 && IsNearXY(player, CraterX, CraterY, ArrivalRadius) && IsIsoldeUnavailable()
        GrantVirgilNote("open_mode")
        RunVirgilNoteModal()
        st = EffectiveStage()
    endif

    ; Direct Rocky Cave arrival skips Crater cleanly
    if st < 20 && (IsInCellId(player, VirgilsLabCellId) || IsNearXY(player, RockyCaveX, RockyCaveY, ArrivalRadius))
        AdvanceTo(20, "out_of_order")
        st = EffectiveStage()
    endif
    CheckTalkFallback(player, st)

    if !completed
        StartTimer(1.0, 1)
    endif
EndEvent

Function CheckTalkFallback(Actor player, int st)
{R4: Timed proximity fallback while Mother Isolde or Virgil is alive so topicless OnActivate never stalls.}
    if talkOpen || completed || player == None
        talkNearSec = 0.0
        return
    endif
    if st < 20
        Actor iso = ResolveIsolde()
        if iso != None && !iso.IsDead() && !iso.IsDisabled() && iso.Is3DLoaded() && player.GetDistance(iso) <= TalkFallbackRadius
            talkNearSec += 1.0
            if talkNearSec >= TalkFallbackSeconds
                talkNearSec = 0.0
                Trace("mq204 talk_fallback actor=isolde stage=" + st + " near_sec=" + TalkFallbackSeconds)
                RunIsoldeTalk()
            endif
            return
        endif
    elseif st < 200
        Actor vg = ResolveVirgil()
        if vg != None && !vg.IsDead() && !vg.IsDisabled() && vg.Is3DLoaded() && player.GetDistance(vg) <= TalkFallbackRadius
            talkNearSec += 1.0
            if talkNearSec >= TalkFallbackSeconds
                talkNearSec = 0.0
                Trace("mq204 talk_fallback actor=virgil stage=" + st + " near_sec=" + TalkFallbackSeconds)
                RunVirgilTalk()
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
    Actor iso = ResolveIsolde()
    Actor vg = ResolveVirgil()
    if ((iso != None && akSender == iso) || (isoldeTalkProxy != None && akSender == isoldeTalkProxy)) && st < 20
        RunIsoldeTalk()
        return
    endif
    if ((vg != None && akSender == vg) || (virgilTalkProxy != None && akSender == virgilTalkProxy)) && st < 200
        RunVirgilTalk()
        return
    endif
    if akSender == labTerminalProxyRef && st < 200
        RunLabTerminalFallback()
    endif
EndEvent

Function RunIsoldeTalk()
    if talkOpen || IsoldeTalkMsg == None
        return
    endif
    talkOpen = True
    talkSessionId += 1
    int sid = talkSessionId
    int btn = IsoldeTalkMsg.Show()
    if sid != talkSessionId
        return
    endif
    talkOpen = False
    if btn < 0 || btn == 3
        return
    endif
    GrantVirgilNote("talk")
    AdvanceTo(20, "talk")
EndFunction

Function RunVirgilNoteModal()
    if talkOpen
        return
    endif
    if VirgilNoteMsg != None
        talkOpen = True
        talkSessionId += 1
        int sid = talkSessionId
        int btn = VirgilNoteMsg.Show()
        if sid != talkSessionId
            return
        endif
        talkOpen = False
        if btn < 0 || btn == 1
            return
        endif
    endif
    AdvanceTo(20, "open_mode")
EndFunction

Function RunVirgilTalk()
    if talkOpen || VirgilTalkMsg == None
        return
    endif
    talkOpen = True
    talkSessionId += 1
    int sid = talkSessionId
    int btn = VirgilTalkMsg.Show()
    if sid != talkSessionId
        return
    endif
    talkOpen = False
    if btn < 0 || btn == 3
        return
    endif
    AdvanceTo(50, "talk")
    AdvanceTo(200, "talk")
EndFunction

Function RunLabTerminalFallback()
    if talkOpen || LabTerminalMsg == None
        return
    endif
    talkOpen = True
    talkSessionId += 1
    int sid = talkSessionId
    int btn = LabTerminalMsg.Show()
    if sid != talkSessionId
        return
    endif
    talkOpen = False
    if btn < 0 || btn == 1
        return
    endif
    AdvanceTo(50, "open_mode")
    AdvanceTo(200, "open_mode")
EndFunction

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
