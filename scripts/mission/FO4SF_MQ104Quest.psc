Scriptname FO4SF_MQ104Quest extends Quest
{"Unlikely Valentine" (FO4SFMission.esm 0x000A80, source-audited from Fallout 4's MQ104 0x01F25E).
 Story mode only (FO4SF_GameMode 0x000870 == 1; stops silently in Warfare mode == 2).
 Stages:
   10  = Objective 10: Search Park Street Station for Nick Valentine (Vault114 0x01002593 / merged -987.46, -2927.73)
   20  = Objective 20: Entered Park Street Station / Vault 114; rescue Nick inside Vault 11402 (0x010109FA)
   40  = Nick's prison door unlocked (NickPrisonDoorREF 0x0007E7A4 / terminal 0x000ADA18); speak with Nick or read case notes
   60  = Objective 30: Escape Vault 114 with Nick Valentine (unlock MQ104NickDoor02REF 0x0008A80C + 0x0007C051)
   85  = Skinny Malone & Darla confrontation at Vault 114 exit chamber (Speech persuasion OR combat victory)
   100 = Objective 40: Meet Nick Valentine outside Vault 114 / at his Diamond City agency
   200 = CompleteQuest -> set FO4SF_MQ105Armed=1 and start FO4SF_MQ105 (0x000AB0, Getting a Clue).
 W6 break-it safe: UVAL-01..05 (Nick/Ellie dead Open-Mode case-notes fallback, R10 5 s door proximity auto-unlock,
 Skinny Malone combat/persuasion parity, Nick tether on reload/surface exit, out-of-order Vault 114 entry).}

Form Property XMarkerBase Auto Const
Actor Property NickValentine Auto Const
Actor Property SkinnyMalone Auto Const
Actor Property Darla Auto Const
GlobalVariable Property Vault114NickFreed Auto Const
GlobalVariable Property Vault114ExitUnlocked Auto Const
GlobalVariable Property MQ105Armed Auto Const
Message Property NickCellTalkMsg Auto Const
Message Property CaseNotesMsg Auto Const
Message Property MaloneTalkMsg Auto Const
Message Property DebriefMsg Auto Const

string LogName = "fo4sf_mission"
string CorePlugin = "FO4TerrainCore.esm"
string CoreMarsPlugin = "FO4TerrainCore_Mars.esm"
string PortPlugin = "FO4Port.esm"
string MissionPlugin = "FO4SFMission.esm"
int CommonwealthWorldId = 0x000803
int CommonwealthAnchorId = 0x0A775B

; Verified FO4Port.esm (interiors_b10) cell IDs
int Vault114CellId = 0x002593
int Vault11402CellId = 0x0109FA
int ValentinesCellId = 0x006B30

; Verified Commonwealth local coords (FO4 / 70) + MergeOffset (-1200, -2700)
float ParkStreetLocalX = 212.54
float ParkStreetLocalY = -227.73
float ParkStreetLocalZ = 19.20
float VaultExitLocalX = 114.57
float VaultExitLocalY = -258.22
float VaultExitLocalZ = 19.20
float DiamondCityLocalX = -216.36
float DiamondCityLocalY = -429.39
float DiamondCityLocalZ = 19.20
float MergeOffsetX = -1200.0
float MergeOffsetY = -2700.0

float PlaceRadius = 300.0
float ParkEntryRadius = 80.0
float ExitDoorOverrideSeconds = 5.0

bool instanceStarted = False
bool completed = False
bool actorsPlaced = False
bool talkOpen = False
int talkSessionId = 0
bool escapeOverrideLogged = False
float escapeWaitSeconds = 0.0
int applied = 0
int pendingStage = -1
string pendingStageBy = "other"

bool Function IsWarfareMode()
    GlobalVariable gm = Game.GetFormFromFile(0x000870, "FO4SFCoreValues.esm") as GlobalVariable
    if gm != None && (gm.GetValue() as int) == 2
        return True
    endif
    return False
EndFunction

int Function EffectiveStage()
{B1/B4 resilience: max(GetStage(), applied) so lagged engine GetStage() never stalls rescue or confrontation handlers.}
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
{B2 mid-tick recheck before MoveTo so a FO4SF_MapMarkersHop ComeBack jump never misplaces actors.}
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

Actor Function ResolveMalone()
    if SkinnyMalone != None
        return SkinnyMalone
    endif
    return Game.GetFormFromFile(0x000A84, MissionPlugin) as Actor
EndFunction

Actor Function ResolveDarla()
    if Darla != None
        return Darla
    endif
    return Game.GetFormFromFile(0x000A86, MissionPlugin) as Actor
EndFunction

bool Function IsNickUnavailable()
    Actor nick = ResolveNick()
    return nick == None || nick.IsDead()
EndFunction

bool Function IsMaloneDefeated()
    Actor mal = ResolveMalone()
    return mal == None || mal.IsDead()
EndFunction

bool Function IsInVault114Cell(Actor player)
    if player == None || !player.IsInInterior()
        return False
    endif
    Cell cur = player.GetParentCell()
    if cur == None
        return False
    endif
    if Game.IsPluginInstalled(PortPlugin)
        Cell v1 = Game.GetFormFromFile(Vault114CellId, PortPlugin) as Cell
        Cell v2 = Game.GetFormFromFile(Vault11402CellId, PortPlugin) as Cell
        if (v1 != None && cur == v1) || (v2 != None && cur == v2)
            return True
        endif
    endif
    return False
EndFunction

bool Function IsInValentinesCell(Actor player)
    if player == None || !player.IsInInterior()
        return False
    endif
    Cell cur = player.GetParentCell()
    if cur != None && Game.IsPluginInstalled(PortPlugin)
        Cell ag = Game.GetFormFromFile(ValentinesCellId, PortPlugin) as Cell
        if ag != None && cur == ag
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
        Trace("mq104 stage " + n + " by=" + by)
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
        Trace("mq104 stage " + auiStageID + " by=" + cause)
        ApplyStage(auiStageID, cause)
    endif
EndEvent

Function SyncVaultDoorGlobals(int st, string by)
    if st >= 40 && Vault114NickFreed != None
        Vault114NickFreed.SetValue(1.0)
    endif
    if st >= 60 && Vault114ExitUnlocked != None
        Vault114ExitUnlocked.SetValue(1.0)
        Trace("mq104 vault114 exit_doors unlocked by=" + by)
    endif
EndFunction

Function ApplyStage(int n, string by)
    if n == 10
        SetObjectiveDisplayed(10, True, True)
        SetActive(True)
    elseif n == 20
        SetObjectiveCompleted(10)
        SetObjectiveDisplayed(20, True, True)
    elseif n == 40
        SyncVaultDoorGlobals(40, by)
        SetObjectiveCompleted(10)
        SetObjectiveDisplayed(20, True, True)
    elseif n == 60
        SyncVaultDoorGlobals(60, by)
        escapeWaitSeconds = 0.0
        SetObjectiveCompleted(20)
        SetObjectiveDisplayed(30, True, True)
    elseif n == 85
        SyncVaultDoorGlobals(85, by)
        SetObjectiveDisplayed(30, True, True)
        if IsMaloneDefeated()
            Trace("mq104 malone pre_cleared -> stage 100")
            AdvanceTo(100, "combat")
        endif
    elseif n == 100
        SyncVaultDoorGlobals(100, by)
        SetObjectiveCompleted(30)
        SetObjectiveDisplayed(40, True, True)
    elseif n == 200
        if completed
            return
        endif
        completed = True
        ReleaseAllActors()
        SyncVaultDoorGlobals(200, by)
        SetObjectiveCompleted(40)
        if MQ105Armed != None
            MQ105Armed.SetValue(1.0)
        endif
        CompleteQuest()
        CancelTimer(1)
        Trace("mq104 complete stage=200 mq105_armed=1 by=" + by)
        if !IsWarfareMode()
            Quest mq105Quest = Game.GetFormFromFile(0x000AB0, MissionPlugin) as Quest
            if mq105Quest != None && !mq105Quest.IsRunning() && !mq105Quest.IsCompleted()
                bool startedMq105 = mq105Quest.StartNoWait()
                Trace("mq105 start_requested ok=" + startedMq105)
            endif
        endif
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
        Trace("mission gate mode=2 started=false quest=mq104")
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
    BindActors()
    AdvanceTo(10, "Trigger")
    if player != None && IsInVault114Cell(player)
        AdvanceTo(20, "out_of_order")
    endif
    Trace("mq104 init stage=" + EffectiveStage() + " vault114_cell=0x002593")
    StartTimer(1.0, 1)
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    talkOpen = False
    talkSessionId += 1
    actorsPlaced = False
    int st = EffectiveStage()
    Trace("mq104 reload stage=" + st + " complete=" + completed)
    if !completed
        if !IsRunning()
            Start()
        endif
        if applied > GetStage()
            SetStage(applied)
        endif
        BindActors()
        SyncVaultDoorGlobals(st, "reload")
        StartTimer(1.0, 1)
    endif
EndEvent

Function BindActors()
    Actor nick = ResolveNick()
    if nick != None && !nick.IsDead()
        nick.AllowPCDialogue(True)
        nick.BlockActivation(False, False)
        RegisterForRemoteEvent(nick, "OnActivate")
    endif
    Actor mal = ResolveMalone()
    if mal != None && !mal.IsDead()
        mal.AllowPCDialogue(True)
        mal.BlockActivation(False, False)
        RegisterForRemoteEvent(mal, "OnActivate")
    endif
    Actor dar = ResolveDarla()
    if dar != None && !dar.IsDead()
        dar.AllowPCDialogue(True)
        dar.BlockActivation(False, False)
        RegisterForRemoteEvent(dar, "OnActivate")
    endif
EndFunction

Function ReleaseIfInCombat(Actor a)
    if a != None && !a.IsDead() && a.GetCombatState() != 0
        a.SetRestrained(False)
    endif
EndFunction

Function ReleaseAllActors()
    Actor nick = ResolveNick()
    if nick != None && !nick.IsDead()
        nick.SetRestrained(False)
    endif
    Actor mal = ResolveMalone()
    if mal != None && !mal.IsDead()
        mal.SetRestrained(False)
    endif
    Actor dar = ResolveDarla()
    if dar != None && !dar.IsDead()
        dar.SetRestrained(False)
    endif
EndFunction

Function PlaceExteriorActors(Actor player)
    if !IsCommonwealthExterior(player)
        return
    endif
    float snapX = player.GetPositionX()
    float snapY = player.GetPositionY()
    float snapZ = player.GetPositionZ()
    float px = ParkStreetLocalX + MergeOffsetX
    float py = ParkStreetLocalY + MergeOffsetY
    float pz = ParkStreetLocalZ
    Actor nick = ResolveNick()
    if nick != None && !nick.IsDead()
        if !IsPlayerStableAt(player, snapX, snapY, snapZ)
            return
        endif
        nick.SetRestrained(False)
        nick.MoveTo(player, (px - 2.0) - snapX, (py - 2.0) - snapY, pz - snapZ, False, False)
        if nick.GetCombatState() == 0
            nick.SetRestrained(True)
        endif
        nick.AllowPCDialogue(True)
    endif
    float ex = VaultExitLocalX + MergeOffsetX
    float ey = VaultExitLocalY + MergeOffsetY
    float ez = VaultExitLocalZ
    Actor mal = ResolveMalone()
    if mal != None && !mal.IsDead()
        if !IsPlayerStableAt(player, snapX, snapY, snapZ)
            return
        endif
        mal.SetRestrained(False)
        mal.MoveTo(player, ex - snapX, ey - snapY, ez - snapZ, False, False)
        if mal.GetCombatState() == 0
            mal.SetRestrained(True)
        endif
        mal.AllowPCDialogue(True)
    endif
    Actor dar = ResolveDarla()
    if dar != None && !dar.IsDead()
        if !IsPlayerStableAt(player, snapX, snapY, snapZ)
            return
        endif
        dar.SetRestrained(False)
        dar.MoveTo(player, (ex + 2.5) - snapX, (ey + 1.0) - snapY, ez - snapZ, False, False)
        if dar.GetCombatState() == 0
            dar.SetRestrained(True)
        endif
        dar.AllowPCDialogue(True)
    endif
    if !IsPlayerStableAt(player, snapX, snapY, snapZ)
        return
    endif
    actorsPlaced = True
    Trace("mq104 actors placed park_street=true")
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
    ReleaseIfInCombat(ResolveNick())
    ReleaseIfInCombat(ResolveMalone())
    ReleaseIfInCombat(ResolveDarla())
    Actor player = Game.GetPlayer()
    if player != None
        bool inVault = IsInVault114Cell(player)
        if inVault && st < 20
            AdvanceTo(20, "vault114_entry")
            st = EffectiveStage()
        endif
        if IsCommonwealthExterior(player)
            float px = ParkStreetLocalX + MergeOffsetX
            float py = ParkStreetLocalY + MergeOffsetY
            float dx = player.GetPositionX() - px
            float dy = player.GetPositionY() - py
            float d2 = dx * dx + dy * dy
            if d2 <= PlaceRadius * PlaceRadius && !actorsPlaced
                PlaceExteriorActors(player)
            endif
            if st == 10 && d2 <= ParkEntryRadius * ParkEntryRadius
                AdvanceTo(20, "park_street_proximity")
                st = EffectiveStage()
            endif
        endif

        ; UVAL-05 Open-Mode dead-Nick fallback: recover Overseer case notes & unlock escape doors
        if st >= 20 && st < 60 && IsNickUnavailable()
            Trace("mq104 open_mode nick_unavailable -> case_notes stage 60")
            if CaseNotesMsg != None
                CaseNotesMsg.Show()
            endif
            AdvanceTo(40, "open_mode")
            AdvanceTo(60, "open_mode")
            st = EffectiveStage()
        endif

        ; UVAL-02 R10 bounded 5 s door override if Nick pathing stalls at 0x0008A80C / 0x0007C051
        if st == 60
            escapeWaitSeconds += 1.0
            if escapeWaitSeconds >= ExitDoorOverrideSeconds
                if !escapeOverrideLogged
                    escapeOverrideLogged = True
                    Trace("mq104 uval02 r10_override exit_doors unlocked after=" + escapeWaitSeconds)
                endif
                AdvanceTo(85, "r10_override")
                st = EffectiveStage()
            endif
        endif

        ; UVAL-03 combat completion if Skinny Malone defeated
        if st == 85 && IsMaloneDefeated()
            AdvanceTo(100, "combat")
            st = EffectiveStage()
        endif

        ; UVAL-05 Open-Mode surface / agency arrival completes MQ104 if Nick is unavailable
        if st == 100 && IsNickUnavailable()
            bool atAgency = IsInValentinesCell(player)
            bool atSurface = IsCommonwealthExterior(player)
            if atAgency || atSurface
                Trace("mq104 open_mode surface_debrief -> stage 200")
                AdvanceTo(200, "open_mode")
            endif
        elseif st == 100 && IsInValentinesCell(player)
            ; UVAL-04 tether Nick into agency on return if alive
            Actor nick = ResolveNick()
            if nick != None && !nick.IsDead()
                nick.MoveTo(player, 2.0, 0.0, 0.0, False, False)
            endif
        endif
    endif
    if !completed
        StartTimer(1.0, 1)
    endif
EndEvent

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    if completed || akActionRef != Game.GetPlayer() || talkOpen
        return
    endif
    int st = EffectiveStage()
    Actor nick = ResolveNick()
    Actor mal = ResolveMalone()
    Actor dar = ResolveDarla()

    if nick != None && akSender == nick
        talkOpen = True
        int myTalkSession = talkSessionId
        if st < 60
            int btn = 0
            if NickCellTalkMsg != None
                btn = NickCellTalkMsg.Show()
                Trace("mq104 nick cell choice button=" + btn)
            endif
            if talkSessionId == myTalkSession && btn >= 0 && btn != 3
                AdvanceTo(40, "nick_cell")
                AdvanceTo(60, "nick_cell")
            endif
        elseif st == 60
            AdvanceTo(85, "nick_escape")
        elseif st >= 100
            int dbtn = 0
            if DebriefMsg != None
                dbtn = DebriefMsg.Show()
            endif
            if talkSessionId == myTalkSession && dbtn >= 0
                AdvanceTo(200, "nick_debrief")
            endif
        endif
        talkOpen = False
    elseif (mal != None && akSender == mal) || (dar != None && akSender == dar)
        talkOpen = True
        int myTalkSession = talkSessionId
        if st < 85
            AdvanceTo(85, "out_of_order")
        endif
        if MaloneTalkMsg != None
            int mbtn = MaloneTalkMsg.Show()
            Trace("mq104 malone confrontation choice button=" + mbtn)
            if talkSessionId == myTalkSession && mbtn >= 0 && mbtn != 3
                if mbtn == 0 || mbtn == 1
                    ReleaseAllActors()
                    AdvanceTo(100, "persuade")
                elseif mbtn == 2
                    ; Combat option chosen; release Malone & Darla to fight
                    ReleaseAllActors()
                endif
            endif
        else
            ReleaseAllActors()
            AdvanceTo(100, "persuade")
        endif
        talkOpen = False
    endif
EndEvent

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
