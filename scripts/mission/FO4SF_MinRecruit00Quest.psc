Scriptname FO4SF_MinRecruit00Quest extends Quest
{"The First Step" (FO4SFMission.esm 0x000A20, source-audited from Fallout 4's MinRecruit00 0x11B36E).
 Story mode only (FO4SF_GameMode 0x000870 == 1; stops silently in Warfare mode == 2).
 Stages:
   10  = started (Preston briefing / Tenpines Bluff discovery)
   50  = Objective 10: Speak with Tenpines Bluff settlers (workbench 0401A793 / merged -1517.0, -1423.6, 87.7)
   100 = Objective 20: Eliminate Corvega Assembly Plant raider leader (FO4Port_CorvegaAssemblyPlant01 0201535A)
   200 = Objective 30: Report success back to Tenpines Bluff
   450 = Objective 40: Report back to Preston Garvey (Tenpines aligns with Minutemen)
   500 = CompleteQuest -> join Minutemen, award FO4SF_FlareGun (0x000A25), set FO4SF_Min02Unlocked = 1.
 W6 break-it safe: giver dead (Open-Mode Tenpines workbench + Sanctuary reward fallback), out-of-order
 Corvega pre-clear check (STEP-02), Corvega boss Z-leash (STEP-03), save/reload at every stage, fast travel away.}

Form Property XMarkerBase Auto Const
Actor Property TenpinesSpokesman Auto Const
Actor Property CorvegaBoss Auto Const
Actor Property Preston Auto Const
MiscObject Property FlareGun Auto Const
GlobalVariable Property Min02Unlocked Auto Const
Faction Property MinutemenFaction Auto Const
Message Property TalkMsg Auto Const
Message Property BriefMsg Auto Const
Message Property RewardMsg Auto Const
Message Property NoteMsg Auto Const

string LogName = "fo4sf_mission"
string CorePlugin = "FO4TerrainCore.esm"
string CoreFallbackPlugin = "FO4TerrainCore_Mars.esm"
string MissionPlugin = "FO4SFMission.esm"
int TenpinesBenchRefId = 0x01A793
int BenchBaseId = 0x0A2ECD
float TenpinesLocalX = -317.0
float TenpinesLocalY = 1276.37
float TenpinesLocalZ = 87.71
float CorvegaLocalX = -512.0
float CorvegaLocalY = 479.0
float CorvegaLocalZ = 54.0
float MergeOffsetX = -1200.0
float MergeOffsetY = -2700.0
float PlaceRadius = 300.0
float SearchRadius = 15.0
float BossEngageRadius = 80.0
float BossMinZ = 35.0
float TalkFallbackRadius = 3.5
float TalkFallbackSeconds = 8.0

bool instanceStarted = False
bool gateDeferred = False
bool completed = False
bool spokesmanHeld = False
bool bossPlaced = False
bool talkOpen = False
int talkSessionId = 0
int applied = 0
int pendingStage = -1
string pendingStageBy = "other"
ObjectReference tenpinesBench = None
ObjectReference spokesmanTalkProxy = None
float talkNearSec = 0.0
WorldSpace commonwealthWorld = None

bool Function IsTestModeEnabled()
    GlobalVariable tm = Game.GetFormFromFile(0x000860, "FO4SFCoreValues.esm") as GlobalVariable
    return tm != None && tm.GetValue() != 0.0
EndFunction

bool Function CheckPredecessorGate()
{R5: MinRecruit00 starts only after Min00 finishes (stage >= 200) and Sanctuary01 completes, unless TestMode is on.
 S9: Holds strictly OFF while FO4SF_S9_HardStopAtMin01_1000 (0x000BF5) is non-zero.}
    GlobalVariable s9HardStop = Game.GetFormFromFile(0x000BF5, MissionPlugin) as GlobalVariable
    if s9HardStop != None && s9HardStop.GetValue() != 0.0
        return False
    endif
    if IsTestModeEnabled()
        return True
    endif
    Quest min00 = Game.GetFormFromFile(0x000800, MissionPlugin) as Quest
    if min00 != None && !min00.IsCompleted() && min00.GetStage() < 200
        return False
    endif
    Quest sanc = Game.GetFormFromFile(0x000817, MissionPlugin) as Quest
    if sanc != None && !sanc.IsCompleted()
        return False
    endif
    return True
EndFunction

bool Function IsWarfareMode()
    GlobalVariable gm = Game.GetFormFromFile(0x000870, "FO4SFCoreValues.esm") as GlobalVariable
    if gm != None && (gm.GetValue() as int) == 2
        return True
    endif
    return False
EndFunction

int Function EffectiveStage()
{B1/B4 resilience: max(GetStage(), applied) so lagged engine GetStage() never stalls talk or stage handlers.}
    int raw = GetStage()
    if applied > raw
        return applied
    endif
    return raw
EndFunction

string Function ActiveCorePlugin()
    if Game.IsPluginInstalled(CorePlugin)
        return CorePlugin
    endif
    if Game.IsPluginInstalled(CoreFallbackPlugin)
        return CoreFallbackPlugin
    endif
    return ""
EndFunction

WorldSpace Function ResolveCommonwealthWorld()
    if commonwealthWorld != None
        return commonwealthWorld
    endif
    string cName = ActiveCorePlugin()
    if cName != ""
        ObjectReference v111Marker = Game.GetFormFromFile(0x0A775B, cName) as ObjectReference
        if v111Marker != None
            commonwealthWorld = v111Marker.GetWorldSpace()
            if commonwealthWorld != None
                return commonwealthWorld
            endif
        endif
        WorldSpace coreWs = Game.GetFormFromFile(0x000803, cName) as WorldSpace
        if coreWs != None
            commonwealthWorld = coreWs
            return commonwealthWorld
        endif
    endif
    return None
EndFunction

bool Function IsCommonwealthExterior(Actor player)
{B2 + WorldSpace identity guard: rejects interiors (FO4SF_MapMarkersHop 100008F4), New Atlantis / alien planets,
 and out-of-Commonwealth XY before MoveTo.}
    if player == None || player.IsInInterior()
        return False
    endif
    WorldSpace ws = player.GetWorldSpace()
    if ws == None
        return False
    endif
    WorldSpace wantWs = ResolveCommonwealthWorld()
    if wantWs == None || ws != wantWs
        return False
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    if px < MergeOffsetX - 3200.0 || px > MergeOffsetX + 3200.0 || py < MergeOffsetY - 3200.0 || py > MergeOffsetY + 3200.0
        return False
    endif
    return True
EndFunction

Actor Function ResolveSpokesman()
    if TenpinesSpokesman != None
        return TenpinesSpokesman
    endif
    return Game.GetFormFromFile(0x000A22, MissionPlugin) as Actor
EndFunction

Actor Function ResolveBoss()
    if CorvegaBoss != None
        return CorvegaBoss
    endif
    return Game.GetFormFromFile(0x000A24, MissionPlugin) as Actor
EndFunction

Actor Function ResolvePreston()
    if Preston != None
        return Preston
    endif
    return Game.GetFormFromFile(0x000802, MissionPlugin) as Actor
EndFunction

bool Function IsSpokesmanDead()
    Actor sp = ResolveSpokesman()
    return sp == None || sp.IsDead()
EndFunction

bool Function IsPrestonDead()
    Actor pr = ResolvePreston()
    return pr == None || pr.IsDead()
EndFunction

Function AdvanceTo(int n, string by = "Trigger")
    pendingStage = n
    pendingStageBy = by
    SetStage(n)
    if n > applied
        applied = n
        Trace("minrecruit00 stage " + n + " by=" + by)
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
        Trace("minrecruit00 stage " + auiStageID + " by=" + cause)
        ApplyStage(auiStageID, cause)
    endif
EndEvent

Function ApplyStage(int n, string by)
    if n == 50
        SetObjectiveDisplayed(10, True, True)
        SetActive(True)
    elseif n == 100
        SetObjectiveCompleted(10)
        SetObjectiveDisplayed(20, True, True)
        ; STEP-02: Corvega boss pre-cleared before talking to Tenpines
        Actor boss = ResolveBoss()
        if boss != None && boss.IsDead()
            Trace("minrecruit00 corvega pre_cleared -> stage 200")
            AdvanceTo(200, "pre_cleared")
        endif
    elseif n == 200
        SetObjectiveCompleted(20)
        SetObjectiveDisplayed(30, True, True)
        if IsSpokesmanDead()
            Trace("minrecruit00 open_mode spokesman_dead -> bench 0x01A793 claims settlement")
        endif
    elseif n == 450
        SetObjectiveCompleted(30)
        SetObjectiveDisplayed(40, True, True)
        if IsPrestonDead()
            Trace("minrecruit00 open_mode preston_dead -> autonomous completion")
            AdvanceTo(500, "open_mode")
        endif
    elseif n == 500
        if completed
            return
        endif
        completed = True
        Actor spDone = ResolveSpokesman()
        if spDone != None
            spDone.SetRestrained(False)
        endif
        spokesmanHeld = False
        SetObjectiveCompleted(40)
        Actor player = Game.GetPlayer()
        if player != None
            if FlareGun != None
                player.AddItem(FlareGun, 1, False)
            endif
            if MinutemenFaction != None
                player.AddToFaction(MinutemenFaction)
            endif
        endif
        if Min02Unlocked != None
            Min02Unlocked.SetValue(1.0)
        endif
        CompleteQuest()
        CancelTimer(1)
        Trace("minrecruit00 complete stage=500 flare_gun=true min02_unlocked=1 by=" + by)
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
        Trace("mission gate mode=2 started=false quest=minrecruit00")
        Stop()
        return
    endif
    if !CheckPredecessorGate()
        Trace("minrecruit00 gate_deferred reason=opening_incomplete")
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
    AdvanceTo(50, "preston")
    Trace("minrecruit00 init stage=50 tenpines_bench=0x01A793")
    StartTimer(1.0, 1)
EndFunction

Function WakeFromPredecessor()
    if completed || instanceStarted
        return
    endif
    if CheckPredecessorGate()
        gateDeferred = False
        Trace("minrecruit00 gate_resumed")
        StartQuestInstance()
    endif
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    talkSessionId += 1
    talkOpen = False
    spokesmanHeld = False
    bossPlaced = False
    talkNearSec = 0.0
    if gateDeferred && !instanceStarted
        WakeFromPredecessor()
        return
    endif
    int st = EffectiveStage()
    Trace("minrecruit00 reload stage=" + st + " complete=" + completed)
    if !completed
        if !IsRunning()
            Start()
        endif
        if applied > GetStage()
            SetStage(applied)
        endif
        tenpinesBench = None
        BindRefs()
        StartTimer(1.0, 1)
    endif
EndEvent

Function BindRefs()
    Actor sp = ResolveSpokesman()
    if sp != None && !sp.IsDead()
        sp.AllowPCDialogue(True)
        sp.BlockActivation(False, False)
        RegisterForRemoteEvent(sp, "OnActivate")
    endif
    Actor pr = ResolvePreston()
    if pr != None && !pr.IsDead()
        RegisterForRemoteEvent(pr, "OnActivate")
    endif
    string cName = ActiveCorePlugin()
    if cName != ""
        ObjectReference wb = Game.GetFormFromFile(TenpinesBenchRefId, cName) as ObjectReference
        if wb == None
            Actor player = Game.GetPlayer()
            if IsCommonwealthExterior(player)
                float bx = TenpinesLocalX + MergeOffsetX
                float by = TenpinesLocalY + MergeOffsetY
                float dx = player.GetPositionX() - bx
                float dy = player.GetPositionY() - by
                if dx * dx + dy * dy <= PlaceRadius * PlaceRadius
                    Form benchBase = Game.GetFormFromFile(BenchBaseId, cName)
                    if benchBase != None
                        wb = Game.FindClosestReferenceOfType(benchBase, bx, by, TenpinesLocalZ, SearchRadius)
                    endif
                endif
            endif
        endif
        if wb != None && wb != tenpinesBench
            tenpinesBench = wb
            RegisterForRemoteEvent(tenpinesBench, "OnActivate")
            RegisterForRemoteEvent(tenpinesBench, "OnWorkshopMode")
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
    if st == 450 && IsPrestonDead()
        Trace("minrecruit00 open_mode preston_dead -> autonomous completion")
        AdvanceTo(500, "open_mode")
        return
    endif
    Actor player = Game.GetPlayer()
    if IsCommonwealthExterior(player)
        ; R3: Enable and place Tenpines spokesman only when mission is at stage >= 50 and player is within PlaceRadius
        Actor sp = ResolveSpokesman()
        if st >= 50 && sp != None && !sp.IsDead()
            if sp.IsDisabled()
                sp.EnableNoWait(False)
                BindRefs()
                Trace("minrecruit00 spokesman enabled stage=" + st)
            endif
            if sp.GetCombatState() != 0
                if spokesmanHeld
                    sp.SetRestrained(False)
                    spokesmanHeld = False
                endif
            else
                float tx = TenpinesLocalX + MergeOffsetX + 2.0
                float ty = TenpinesLocalY + MergeOffsetY + 1.5
                float tz = TenpinesLocalZ
                float pdx = player.GetPositionX() - tx
                float pdy = player.GetPositionY() - ty
                if pdx * pdx + pdy * pdy <= PlaceRadius * PlaceRadius
                    float sdx = sp.GetPositionX() - tx
                    float sdy = sp.GetPositionY() - ty
                    if !spokesmanHeld || (sdx * sdx + sdy * sdy) > 625.0
                        sp.SetRestrained(False)
                        sp.MoveTo(player, tx - player.GetPositionX(), ty - player.GetPositionY(), tz - player.GetPositionZ(), False, False)
                        sp.SetRestrained(True)
                        sp.AllowPCDialogue(True)
                        spokesmanHeld = True
                        Trace("minrecruit00 tenpines spokesman placed")
                    endif
                    if spokesmanTalkProxy == None || spokesmanTalkProxy.IsDeleted()
                        Activator talkActi = Game.GetFormFromFile(0x000A27, MissionPlugin) as Activator
                        if talkActi != None
                            spokesmanTalkProxy = sp.PlaceAtMe(talkActi, 1, True, False, False)
                            if spokesmanTalkProxy != None
                                spokesmanTalkProxy.MoveTo(sp, 0.0, 0.0, 1.0, False, False)
                                RegisterForRemoteEvent(spokesmanTalkProxy, "OnActivate")
                            endif
                        endif
                    endif
                endif
            endif
        endif
        ; R3: Enable Corvega boss ONLY at stage >= 100 (never during opening / stage 50)
        Actor boss = ResolveBoss()
        if st >= 100 && boss != None
            if boss.IsDead()
                if st == 100
                    AdvanceTo(200, "boss_dead")
                endif
            else
                float cx = CorvegaLocalX + MergeOffsetX
                float cy = CorvegaLocalY + MergeOffsetY
                float cz = CorvegaLocalZ
                float bdx = player.GetPositionX() - cx
                float bdy = player.GetPositionY() - cy
                float bd2 = bdx * bdx + bdy * bdy
                if bd2 <= PlaceRadius * PlaceRadius
                    if boss.IsDisabled()
                        boss.EnableNoWait(False)
                        Trace("minrecruit00 corvega boss enabled stage=" + st)
                    endif
                    if !bossPlaced || boss.GetPositionZ() < BossMinZ
                        boss.SetRestrained(False)
                        boss.MoveTo(player, cx - player.GetPositionX(), cy - player.GetPositionY(), cz - player.GetPositionZ(), False, False)
                        bossPlaced = True
                        Trace("minrecruit00 corvega boss leashed z=" + cz)
                    endif
                    if st == 100 && bd2 <= BossEngageRadius * BossEngageRadius && boss.GetCombatState() == 0
                        boss.SetRestrained(False)
                        boss.StartCombat(player)
                    endif
                endif
            endif
        endif
        CheckTalkFallback(player, st)
    elseif st == 100
        ; Also poll boss death inside CorvegaAssemblyPlant01 interior
        Actor bossIn = ResolveBoss()
        if bossIn != None && bossIn.IsDead()
            AdvanceTo(200, "boss_dead_interior")
        endif
    endif
    if tenpinesBench == None
        BindRefs()
    endif
    if !completed
        StartTimer(1.0, 1)
    endif
EndEvent

Function RunSpokesmanTalk(int st)
    if talkOpen || completed
        return
    endif
    talkOpen = True
    int mySession = talkSessionId
    if st == 50
        bool accepted = True
        if TalkMsg != None
            accepted = False
            int steps = 0
            bool doneLoop = False
            while !doneLoop && steps < 8 && mySession == talkSessionId
                steps += 1
                int btn = TalkMsg.Show()
                Trace("minrecruit00 tenpines choice button=" + btn)
                if btn < 0 || btn == 3 || mySession != talkSessionId
                    doneLoop = True
                elseif btn == 2
                    if BriefMsg != None
                        BriefMsg.Show()
                    endif
                    accepted = True
                    doneLoop = True
                elseif BriefMsg != None
                    BriefMsg.Show()
                endif
            endwhile
        endif
        if accepted && mySession == talkSessionId
            AdvanceTo(100, "spokesman")
        endif
    elseif st == 200
        bool rwOk = True
        if RewardMsg != None
            if RewardMsg.Show() < 0
                rwOk = False
            endif
        endif
        if rwOk && mySession == talkSessionId
            AdvanceTo(450, "spokesman")
        endif
    endif
    if mySession == talkSessionId
        talkOpen = False
    endif
EndFunction

Function CheckTalkFallback(Actor player, int st)
{R4: Timed proximity fallback while Tenpines spokesman or Preston is alive so topicless OnActivate never stalls.}
    if talkOpen || completed || player == None
        talkNearSec = 0.0
        return
    endif
    if st == 50 || st == 200
        Actor sp = ResolveSpokesman()
        if sp != None && !sp.IsDead() && !sp.IsDisabled() && sp.Is3DLoaded() && player.GetDistance(sp) <= TalkFallbackRadius
            talkNearSec += 1.0
            if talkNearSec >= TalkFallbackSeconds
                talkNearSec = 0.0
                Trace("minrecruit00 talk_fallback actor=spokesman stage=" + st + " near_sec=" + TalkFallbackSeconds)
                RunSpokesmanTalk(st)
            endif
            return
        endif
    elseif st == 450
        Actor pr = ResolvePreston()
        if pr != None && !pr.IsDead() && pr.Is3DLoaded() && player.GetDistance(pr) <= TalkFallbackRadius
            talkNearSec += 1.0
            if talkNearSec >= TalkFallbackSeconds
                talkNearSec = 0.0
                Trace("minrecruit00 talk_fallback actor=preston stage=450 near_sec=" + TalkFallbackSeconds)
                AdvanceTo(500, "talk_fallback")
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
    Actor sp = ResolveSpokesman()
    Actor pr = ResolvePreston()
    if (sp != None && akSender == sp) || (spokesmanTalkProxy != None && akSender == spokesmanTalkProxy)
        RunSpokesmanTalk(st)
    elseif tenpinesBench != None && akSender == tenpinesBench
        ; STEP-01 Open-Mode workbench/note fallback when spokesman is dead
        if st == 50 && IsSpokesmanDead()
            bool noteOk = True
            if NoteMsg != None
                if NoteMsg.Show() < 0
                    noteOk = False
                endif
            endif
            if noteOk
                AdvanceTo(100, "open_mode")
            endif
        elseif st == 200 && IsSpokesmanDead()
            AdvanceTo(450, "open_mode")
        endif
    elseif pr != None && akSender == pr && st == 450
        AdvanceTo(500, "preston")
    endif
EndEvent

Event ObjectReference.OnWorkshopMode(ObjectReference akSender, bool aStart)
    if completed || !aStart || tenpinesBench == None || akSender != tenpinesBench
        return
    endif
    int st = EffectiveStage()
    if st == 50 && IsSpokesmanDead()
        AdvanceTo(100, "open_mode")
    elseif st == 200 && IsSpokesmanDead()
        AdvanceTo(450, "open_mode")
    endif
EndEvent

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
