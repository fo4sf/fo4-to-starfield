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
string MissionPlugin = "FO4SFMission.esm"
int TenpinesBenchRefId = 0x01A793
float TenpinesLocalX = -317.0
float TenpinesLocalY = 1276.37
float TenpinesLocalZ = 87.71
float CorvegaLocalX = -512.0
float CorvegaLocalY = 479.0
float CorvegaLocalZ = 54.0
float MergeOffsetX = -1200.0
float MergeOffsetY = -2700.0
float PlaceRadius = 300.0
float BossMinZ = 35.0

bool instanceStarted = False
bool completed = False
bool spokesmanHeld = False
bool bossPlaced = False
bool talkOpen = False
int applied = 0
int pendingStage = -1
string pendingStageBy = "other"
ObjectReference tenpinesBench = None

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

bool Function IsCommonwealthExterior(Actor player)
{B2 guard: reject interiors (e.g. FO4SF_MapMarkersHop 100008F4), null WorldSpace, or out-of-Commonwealth XY before MoveTo.}
    if player == None || player.IsInInterior()
        return False
    endif
    if player.GetWorldSpace() == None
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

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    talkOpen = False
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
    if Game.IsPluginInstalled(CorePlugin)
        ObjectReference wb = Game.GetFormFromFile(TenpinesBenchRefId, CorePlugin) as ObjectReference
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
    Actor player = Game.GetPlayer()
    if IsCommonwealthExterior(player)
        ; Keep Tenpines spokesman placed when player approaches within PlaceRadius
        Actor sp = ResolveSpokesman()
        if sp != None && !sp.IsDead()
            float tx = TenpinesLocalX + MergeOffsetX + 2.0
            float ty = TenpinesLocalY + MergeOffsetY + 1.5
            float tz = TenpinesLocalZ
            float pdx = player.GetPositionX() - tx
            float pdy = player.GetPositionY() - ty
            if pdx * pdx + pdy * pdy <= PlaceRadius * PlaceRadius && !spokesmanHeld
                sp.MoveTo(player, tx - player.GetPositionX(), ty - player.GetPositionY(), tz - player.GetPositionZ(), False, False)
                sp.SetRestrained(True)
                sp.AllowPCDialogue(True)
                spokesmanHeld = True
                Trace("minrecruit00 tenpines spokesman placed")
            endif
        endif
        ; Keep Corvega boss placed & guarded against subterranean clipping (STEP-03)
        Actor boss = ResolveBoss()
        if st == 100 && boss != None
            if boss.IsDead()
                AdvanceTo(200, "boss_dead")
            else
                float cx = CorvegaLocalX + MergeOffsetX
                float cy = CorvegaLocalY + MergeOffsetY
                float cz = CorvegaLocalZ
                float bdx = player.GetPositionX() - cx
                float bdy = player.GetPositionY() - cy
                if bdx * bdx + bdy * bdy <= PlaceRadius * PlaceRadius
                    if !bossPlaced || boss.GetPositionZ() < BossMinZ
                        boss.MoveTo(player, cx - player.GetPositionX(), cy - player.GetPositionY(), cz - player.GetPositionZ(), False, False)
                        bossPlaced = True
                        Trace("minrecruit00 corvega boss leashed z=" + cz)
                    endif
                endif
            endif
        endif
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

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    if completed || akActionRef != Game.GetPlayer() || talkOpen
        return
    endif
    int st = EffectiveStage()
    Actor sp = ResolveSpokesman()
    Actor pr = ResolvePreston()
    if sp != None && akSender == sp
        talkOpen = True
        if st == 50
            if TalkMsg != None
                int btn = TalkMsg.Show()
                Trace("minrecruit00 tenpines choice button=" + btn)
                if btn != 3 && BriefMsg != None
                    BriefMsg.Show()
                endif
            endif
            AdvanceTo(100, "spokesman")
        elseif st == 200
            if RewardMsg != None
                RewardMsg.Show()
            endif
            AdvanceTo(450, "spokesman")
        endif
        talkOpen = False
    elseif tenpinesBench != None && akSender == tenpinesBench
        ; STEP-01 Open-Mode workbench/note fallback when spokesman is dead
        if st == 50 && IsSpokesmanDead()
            if NoteMsg != None
                NoteMsg.Show()
            endif
            AdvanceTo(100, "open_mode")
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
