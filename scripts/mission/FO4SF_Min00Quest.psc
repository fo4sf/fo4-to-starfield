Scriptname FO4SF_Min00Quest extends Quest
{A cut-down "When Freedom Calls" (fo4-to-starfield, docs/mission/when-freedom-calls.md): the Concord raiders,
 Preston Garvey and the reward, started at FO4SFNewGame stage 200 via StartNoWait().
 Stages: 10 started (find Preston), 20 the fight started, 30 the raiders are cleared (talk to Preston), 35 Preston's
 final exchange (0x092A), 40 talked to Preston (the reward), 200 complete (starts FO4SF_Sanctuary01 0x000817). Every
 stage change and a status line every 5 s go to the user log "fo4sf_mission"
 (My Games\Starfield\Logs\Script\User\fo4sf_mission.0.log).}

Actor Property Preston Auto Const Mandatory
{Preston's placed actor (FO4SFMission.esm 0x802).}

Actor[] Property Raiders Auto Const Mandatory
{The Concord raiders' placed actors (FO4SFMission.esm 0x803 on).}

MiscObject Property Credits Auto Const Mandatory
{Starfield's credits: the reward that stands in for Fallout 4's caps.}

Actor Property Codsworth Auto Const
{Codsworth's placed actor (FO4SFMission.esm 0x811), set only on his keeper quest (FO4SF_CodsworthKeeper, 0x814); None
 on FO4SF_Min00 and in a --no-codsworth build. Not part of the mission.}

bool Property KeeperOnly = False Auto Const
{True on FO4SF_CodsworthKeeper: this instance only keeps Codsworth (enabled, put back at his merged spot, PlaceCodsworth)
 and Preston (put back at his merged spot, KeepPreston) and never runs the mission.}

bool Property MuteDuplicateObjectiveToasts = True Auto Const

Message Property PrestonTalkMsg Auto Const
Message Property PrestonReply0Msg Auto Const
Message Property PrestonReply1Msg Auto Const
Message Property PrestonReply2Msg Auto Const
GlobalVariable Property TalkUseMessageBox Auto Const
Weapon Property RaiderWeapon Auto Const
Ammo Property RaiderAmmo Auto Const
Weapon Property RaiderSidearm Auto Const
Ammo Property RaiderSidearmAmmo Auto Const
float Property RaiderPrimaryRecordDamage = 0.0 Auto Const
float Property RaiderSidearmRecordDamage = 0.0 Auto Const
ActorValue Property AttackDamageMult Auto Const
float Property PrestonSceneCheckSeconds = 1.5 Auto Const
int Property PrestonSceneMaxWaitChecks = 16 Auto Const
int Property PrestonMaxSceneRestarts = 3 Auto Const
bool Property EnableS4Balcony = False Auto Const
bool Property EnableS6ToS9Full = False Auto Const
ObjectReference Property S4BalconyMarker Auto Const
ObjectReference Property S9MuseumExitMarker Auto Const
ObjectReference[] Property S9PatrolWaypoints Auto Const
ObjectReference Property DiamondCityMapMarker Auto Const
Actor[] Property MinutemenGroup Auto Const
int Property S4ExteriorRaiderCount = 3 Auto Const
float Property S4BalconyX = -2010.51 Auto Const
float Property S4BalconyY = -1697.71 Auto Const
float Property S4BalconyZ = 98.51 Auto Const
string Property S4BalconyZLabel = "98.51" Auto Const
float Property S9MuseumExitX = -2010.57 Auto Const
float Property S9MuseumExitY = -1697.94 Auto Const
float Property S9MuseumExitZ = 89.26 Auto Const
int Property LaserMusketId = 0 Auto Const
int Property FusionCellId = 0 Auto Const
int Property BottlecapId = 0 Auto Const
int Property DiamondCityMapMarkerId = 0x000B8A Auto Const
float Property DiamondCityMapMarkerX = -1416.36 Auto Const
float Property DiamondCityMapMarkerY = -3129.39 Auto Const
float Property DiamondCityMapMarkerZ = 21.80 Auto Const
int Property S4MusketFusionCells = 15 Auto Const
int Property S9RewardCaps = 100 Auto Const
int Property S9RewardFusionCells = 50 Auto Const
bool Property StopAtFusionCorePowerArmor = False Auto Const
Actor[] Property S5MuseumRaiders Auto Const
ObjectReference[] Property S5MuseumDoors Auto Const
ObjectReference[] Property S5MuseumLootMarkers Auto Const
ObjectReference Property S4DisplayMusketRef Auto Const
ObjectReference[] Property S4FusionCellRefs Auto Const
Actor Property SturgesRef Auto Const
Scene Property S6PrestonRoomScene Auto Const
Scene Property S6SturgesRoomScene Auto Const
int Property PipePistolId = 0x0008A2 Auto Const
int Property PipeRifleId = 0x0008A3 Auto Const
int Property Ammo38Id = 0x0008A1 Auto Const
int Property CompPrestonMusketId = 0x00089E Auto Const
int Property CompPrestonAmmoId = 0x00089C Auto Const
int Property StimpakId = 0x000851 Auto Const
int Property BobbyPinId = 0x0008A5 Auto Const
float Property S9PatrolFailsafeSeconds = 180.0 Auto Const
float Property S9SanctuaryX = -2356.32 Auto Const
float Property S9SanctuaryY = -1470.44 Auto Const
float Property S9SanctuaryZ = 109.14 Auto Const
float Property S9SanctuaryPlayerRadius = 120.0 Auto Const
float Property S9SanctuaryGroupFarDist = 150.0 Auto Const
float Property S9SanctuaryArrivalRadius = 35.0 Auto Const

float Property MergeOffsetX = -1200.0 Auto Const
float Property MergeOffsetY = -2700.0 Auto Const
{The core world's merge offset (vmad_patch.MERGE_MEASURED): the world the player walks in places the core's records at
 their local position + this; z unchanged.}

float Property RelocateRadius = 800.0 Auto Const
{Move an actor only when the player stands outdoors within this many units of that actor's merged spot.}

float Property RelocateGap = 1500.0 Auto Const
{...and Preston is farther than this from the player.}

float Property PrestonLocalX = -811.14 Auto Const
float Property PrestonLocalY = 1002.46 Auto Const
float Property PrestonLocalZ = 89.09 Auto Const
{Preston's spot in the plugin (ACHR 0x802, the museum door's outside arrival: points.json "preston" pos).}

float Property CodsworthLocalX = -1146.709 Auto Const
float Property CodsworthLocalY = 1293.837 Auto Const
float Property CodsworthLocalZ = 111.734 Auto Const
{Codsworth's spot in the plugin (ACHR 0x811, Fallout 4's ACHR 01CA7D: points.json "codsworth" pos).}

float Property PlaceRadius = 300.0 Auto Const
{Preston and Codsworth are placed only when the player stands outdoors within this many m of their merged spot.}

float Property HoldRadius = 25.0 Auto Const
{Preston (Codsworth) counts as at his spot within this many m of it (and within RelocateGap of the player).}

float Property HeldRadius = 3.0 Auto Const
{...and he is held there (HoldPreston, HoldCodsworth) when calm and within this many m of it.}

int Property RewardCount = 100 Auto Const
{Fallout 4 gives 100 caps (DialogueConcordArea stage 40).}

float Property CodsworthCheck = 5.0 Auto Const
{Seconds between the keeper's relocation checks (KeepCodsworth, KeepPreston).}

int Property KeeperStatusEvery = 12 Auto Const
{The keeper logs where Preston and Codsworth are every this many checks (12 x 5 s = a minute), and at each save load.}

float Property EngageRadius = 60.0 Auto Const
{The fight starts when the player comes this close (m) to a living raider, as FO4's DN092 StartCombat on its ambush.}

float Property FindRadius = 20.0 Auto Const
{...or, before the fight, comes this close (m) to Preston or activates him.}

float Property TalkRadius = 3.0 Auto Const
{Standing this close (m) to Preston counts as the fallback talk completion if the scene cannot start or times out.}

float Property TalkFallbackSeconds = 120.0 Auto Const
{Seconds within TalkRadius with no active scene before fallback completion triggers (logged as stage 40 by=fallback).}

float Property TalkSceneTimeout = 120.0 Auto Const
{Maximum seconds an active Preston talk scene blocks the proximity fallback before timeout.}

float Property GiveConcordRadius = 150.0 Auto Const
{Distance (m) from the Concord museum door at which FO4SF_Min00 displays its first objective if Codsworth has not given it yet.}

float Property Wfc01CheckRadius = 150.0 Auto Const
float Property Wfc01DoorRadius = 100.0 Auto Const
float Property Wfc01SubterraneanDrop = 8.0 Auto Const
float Property Wfc01MaxDrift = 140.0 Auto Const
float Property Wfc01AbsentDistance = 250.0 Auto Const
float Property Wfc01AbsentLimit = 60.0 Auto Const
float Property Wfc01StuckMoveRadius = 2.0 Auto Const
float Property Wfc01StuckLimit = 60.0 Auto Const

string LogName = "fo4sf_mission"
bool instanceStarted = False
bool min00Given = False
bool obj10DisplayedOnce = False
bool obj60DisplayedOnce = False
bool obj70DisplayedOnce = False
bool obj85DisplayedOnce = False
bool obj86DisplayedOnce = False
bool obj87DisplayedOnce = False
bool obj90DisplayedOnce = False
bool obj95DisplayedOnce = False
bool obj150DisplayedOnce = False
bool sanctuaryObj1000DisplayedOnce = False
int ticks = 0
int relocateFails = 0
int codsworthFails = 0
int prestonFails = 0
int keeperChecks = 0
int prestonMoves = 0
float prestonOff = -1.0
string prestonState = "none"
bool prestonHeld = False
int prestonHolds = 0
bool prestonPlaced = False
bool prestonFollow = False
bool prestonFighting = False
int codsworthMoves = 0
float codsworthOff = -1.0
string codsworthState = "none"
bool codsworthHeld = False
int codsworthHolds = 0
bool codsworthFighting = False
bool codsworthKept = False
int applied = 0
int pendingStage = -1
string pendingStageBy = "other"
bool prestonFound = False
bool talkActivated = False
int talkFailures = 0
float talkStartedAt = 0.0
float talkNearSec = 0.0
bool prestonUsedFallback = False
bool prestonTalkLogged = False
bool prestonTalkBoxOpen = False
bool prestonFallbackActive = False
int talkSessionId = 0
bool prestonTalkReloaded = False
bool prestonDialogueMenuOpen = False
bool prestonScenePending = False
bool prestonSceneMenuOpened = False
bool prestonScenePhase1 = False
float prestonPhase1At = 0.0
int prestonSceneChecks = 0
int prestonSceneRestarts = 0
bool prestonPostSceneActive = False
bool ownPrestonSceneStop = False
float prestonAttemptStartedAt = 0.0
int sanctuaryStartRetries = 0
bool mq103ProxAttempted = False
bool minRecruitProxAttempted = False
bool mq104ProxAttempted = False
bool mq105ProxAttempted = False
bool mq106ProxAttempted = False
bool mq203ProxAttempted = False
bool mq204ProxAttempted = False
bool mq206ProxAttempted = False
bool s4BalconySetup = False
int s5RaiderEngageTicks = 0
bool s4BalconyActive = False
bool s4PrestonArmed = False
bool s4StreetCleared = False
bool s4MusketTaken = False
bool s4FusionCellsPlaced = False
bool s5MuseumInitialized = False
bool s5MuseumCleared = False
int s5MuseumRaidersDead = 0
bool s6BasementUnlockedPending = False
bool s6RoomEventsRegistered = False
bool s6RoomScenePending = False
bool s6RoomSceneMenuOpened = False
bool s6RoomSceneRestarting = False
bool s6RoomScenePhase1 = False
float s6RoomPhase1At = 0.0
float s6RoomAttemptStartedAt = 0.0
int s6RoomSceneRetries = 0
int s6RoomSceneTicks = 0
bool s6SturgesScenePending = False
bool s6SturgesSceneMenuOpened = False
bool s6SturgesSceneRestarting = False
bool s6SturgesScenePhase1 = False
float s6SturgesPhase1At = 0.0
float s6SturgesAttemptStartedAt = 0.0
int s6SturgesSceneRetries = 0
int s6SturgesSceneTicks = 0
int s6FullStage = 0
bool s9LobbyCompleted = False
bool s9DiamondCityRevealed = False
bool s9DiamondCityMerged = False
bool s9PatrolStarted = False
bool s9PatrolRelease = False
float s9PatrolStartedAt = 0.0
float s9PatrolElapsed = 0.0
bool s9GroupArrived = False
string s9ArrivalVia = ""

float[] raiderTargetX
float[] raiderTargetY
float[] raiderTargetZ
float[] raiderCorpseX
float[] raiderCorpseY
float[] raiderCorpseZ
float[] raiderAbsentSec
bool[] raiderCleared
bool[] raiderRescued
bool[] raiderEngaged
bool[] raiderArmed
float[] raiderStartCombatAt
float[] raiderRescueSec
float[] raiderRescueX
float[] raiderRescueY
float[] raiderRescueZ
float[] raiderRescueHp
ActorValue healthAvCache

bool Function IsWarfareMode()
    GlobalVariable gm = Game.GetFormFromFile(0x000870, "FO4SFCoreValues.esm") as GlobalVariable
    if gm != None && (gm.GetValue() as int) == 2
        return True
    endif
    return False
EndFunction

bool Function IsTestModeEnabled()
    GlobalVariable tm = Game.GetFormFromFile(0x000860, "FO4SFCoreValues.esm") as GlobalVariable
    return tm != None && tm.GetValue() != 0.0
EndFunction

bool Function ShouldUseMessageBox()
    GlobalVariable g = TalkUseMessageBox
    if g == None
        g = Game.GetFormFromFile(0x000979, "FO4SFMission.esm") as GlobalVariable
    endif
    if g != None && g.GetValue() != 0.0
        return True
    endif
    return False
EndFunction

int Function EffectiveStage()
    int st = GetStage()
    if applied > st
        return applied
    endif
    return st
EndFunction

WorldSpace Function ResolveCommonwealthWorld()
    ; Task 1i (#858 F7): resolve host world dynamically from persistent V111 exit marker (0x0A775B, flags=0x400)
    ; FIRST, using Sanctuary workbench (0x005C50, flags=0x0) only as secondary fallback — NEVER hardcoded FO4SFMission world copies.
    ObjectReference v111Marker = Game.GetFormFromFile(0x0A775B, "FO4TerrainCore.esm") as ObjectReference
    if v111Marker == None
        v111Marker = Game.GetFormFromFile(0x0A775B, "FO4TerrainCore_Mars.esm") as ObjectReference
    endif
    if v111Marker != None
        WorldSpace mws = v111Marker.GetWorldSpace()
        if mws != None
            return mws
        endif
    endif
    ObjectReference benchRef = Game.GetFormFromFile(0x005C50, "FO4TerrainCore.esm") as ObjectReference
    if benchRef != None
        WorldSpace bws = benchRef.GetWorldSpace()
        if bws != None
            return bws
        endif
    endif
    if prestonPlaced && Preston != None && !Preston.IsInInterior()
        return Preston.GetWorldSpace()
    endif
    return None
EndFunction

bool Function IsCommonwealthExterior(Actor player)
    if player == None || player.IsInInterior()
        return False
    endif
    WorldSpace ws = player.GetWorldSpace()
    if ws == None
        return False
    endif
    WorldSpace cws = ResolveCommonwealthWorld()
    if cws != None && ws != cws
        return False
    endif
    float cx = player.GetPositionX()
    float cy = player.GetPositionY()
    if cx < MergeOffsetX - 3600.0 || cx > MergeOffsetX + 3600.0
        return False
    endif
    if cy < MergeOffsetY - 3600.0 || cy > MergeOffsetY + 3600.0
        return False
    endif
    return True
EndFunction

bool Function IsPlayerStableAt(Actor player, float px, float py, float pz)
    if !IsCommonwealthExterior(player)
        return False
    endif
    float dx = player.GetPositionX() - px
    float dy = player.GetPositionY() - py
    float dz = player.GetPositionZ() - pz
    return dx * dx + dy * dy + dz * dz <= 25.0
EndFunction

Function EnsurePrestonAlias()
    talkSessionId += 1
    if Preston == None
        return
    endif
    ReferenceAlias al = GetAlias(0) as ReferenceAlias
    if al != None && al.GetActorRef() != Preston
        al.ForceRefTo(Preston)
    endif
EndFunction

Scene Function ResolvePrestonScene()
{Resolve 0x000900 directly from FO4SFMission.esm rather than binding a VMAD Scene property.}
    return Game.GetFormFromFile(0x000900, "FO4SFMission.esm") as Scene
EndFunction

Scene Function ResolvePrestonSceneLogged()
    Scene fileScn = Game.GetFormFromFile(0x000900, "FO4SFMission.esm") as Scene
    if fileScn != None
        Trace("preston scene resolved via=file scene=" + fileScn)
        return fileScn
    endif
    Trace("preston scene resolved via=none")
    return None
EndFunction

Scene Function ResolvePrestonPostScene()
    return Game.GetFormFromFile(0x000990, "FO4SFMission.esm") as Scene
EndFunction

Scene Function ResolveActivePrestonScene(bool postMode)
    if postMode
        return ResolvePrestonPostScene()
    endif
    return ResolvePrestonScene()
EndFunction

Function EnsureKeeperPrestonAlias()
    if Preston == None
        return
    endif
    Quest keeper = Game.GetFormFromFile(0x000814, "FO4SFMission.esm") as Quest
    if keeper != None
        if !keeper.IsRunning()
            keeper.Start()
        endif
        ReferenceAlias al = keeper.GetAlias(0) as ReferenceAlias
        if al != None && al.GetActorRef() != Preston
            al.ForceRefTo(Preston)
        endif
    endif
EndFunction

Function RegisterPrestonSceneEvents()
    Scene scn = ResolvePrestonScene()
    if scn != None
        RegisterForRemoteEvent(scn, "OnBegin")
        RegisterForRemoteEvent(scn, "OnPhaseBegin")
        RegisterForRemoteEvent(scn, "OnEnd")
    endif
    Scene postScn = ResolvePrestonPostScene()
    if postScn != None
        EnsureKeeperPrestonAlias()
        RegisterForRemoteEvent(postScn, "OnBegin")
        RegisterForRemoteEvent(postScn, "OnPhaseBegin")
        RegisterForRemoteEvent(postScn, "OnEnd")
    endif
EndFunction

Event OnQuestStarted()
    StartQuestInstance()
EndEvent

Event OnQuestInit()
    StartQuestInstance()
EndEvent

Function LogWarfareStop()
    if KeeperOnly
        Trace("mission gate mode=2 started=false quest=keeper")
    else
        Trace("mission gate mode=2 started=false")
    endif
EndFunction

Function StartQuestInstance()
    if instanceStarted
        return
    endif
    instanceStarted = True
    Debug.OpenUserLog(LogName)
    if IsWarfareMode()
        LogWarfareStop()
        Stop()
        return
    endif
    if !IsRunning()
        Start()
    endif
    if KeeperOnly
        Trace("keeper init codsworth=" + Codsworth)
        RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")
        KeepCodsworthLoad()
        return
    endif
    Trace("mission gate mode=1 started=true")
    InitRaiderTracking()
    Trace("init raiders=" + Raiders.Length)
    RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")
    EnsureActorTalkable(Preston)
    EnsurePrestonAlias()
    RegisterForMenuOpenCloseEvent("DialogueMenu")
    RegisterForRemoteEvent(Preston, "OnActivate")
    RegisterPrestonSceneEvents()
    RegisterS6RoomEvents()
    Preston.IgnoreFriendlyHits(True)                     ; a stray shot in the fight must not turn him (in game 18 Oct 15:16)
    SyncPrestonFightHold(EffectiveStage())
    ; M1: starts silent with NO objective shown until Codsworth's talk finishes or the player reaches <= 150 m of Concord
    StartTimer(1.0, 1)
    KeepCodsworthStart()
EndFunction

Function SyncPrestonFightHold(int stage)
{Task 0d: Keep Preston passive and untargeted while Concord raiders fight (stage < 30) so raiders engage and aim
 exclusively at the player while Preston stands visibly at the Museum doorway/balcony. Un-ghosts at stage >= 30.}
    if Preston == None || KeeperOnly
        return
    endif
    if stage < 30
        bool changed = False
        if !Preston.IsGhost()
            Preston.SetGhost(True)
            changed = True
        endif
        ActorValue aggrAv = Game.GetAggressionAV()
        if aggrAv != None && Preston.GetValue(aggrAv) != 0.0
            Preston.SetValue(aggrAv, 0.0)
        endif
        Weapon pw = Preston.GetEquippedWeapon()
        if pw != None
            Preston.UnequipItem(pw, False, True)
            changed = True
        endif
        if Preston.GetCombatState() != 0 || Preston.GetCombatTarget() != None
            Preston.StopCombat()
            Preston.StopCombatAlarm()
            changed = True
        endif
        if changed
            Trace("preston hold_fire stage=" + stage + " ghost=true")
        endif
    elseif Preston.IsGhost()
        Preston.SetGhost(False)
        Trace("preston hold_fire stage=" + stage + " ghost=false")
    endif
EndFunction

Function ClearCodsworthObjectiveForConcord()
    FO4SF_Codsworth01Quest cods01 = Game.GetFormFromFile(0x000816, "FO4SFMission.esm") as FO4SF_Codsworth01Quest
    if cods01 != None
        cods01.ClearObjectiveOnConcordStart()
    endif
EndFunction

Function GiveFromCodsworth()
{Called by FO4SF_Codsworth01Quest at stage 100 so Codsworth's last choice reveals FO4SF_Min00 objective 10.}
    if KeeperOnly || IsWarfareMode()
        return
    endif
    if !IsRunning()
        Start()
    endif
    int st = EffectiveStage()
    if !min00Given && st < 10
        min00Given = True
        Trace("min00 given by=codsworth")
        AdvanceTo(10, "info")
    elseif st < 20
        EnsurePrestonAlias()
        if FO4SF_QuestToastUtil.ShowObjectiveOnce(Self, 10, MuteDuplicateObjectiveToasts, obj10DisplayedOnce)
            obj10DisplayedOnce = True
        endif
    endif
EndFunction

Function InitRaiderTracking()
    int count = Raiders.Length
    if raiderCleared != None && raiderCleared.Length == count && raiderRescued != None && raiderRescued.Length == count && raiderEngaged != None && raiderEngaged.Length == count && raiderArmed != None && raiderArmed.Length == count && raiderStartCombatAt != None && raiderStartCombatAt.Length == count
        if raiderCorpseX == None || raiderCorpseX.Length != count
            raiderCorpseX = new float[count]
            raiderCorpseY = new float[count]
            raiderCorpseZ = new float[count]
            int ci = 0
            while ci < count
                raiderCorpseX[ci] = raiderTargetX[ci]
                raiderCorpseY[ci] = raiderTargetY[ci]
                raiderCorpseZ[ci] = raiderTargetZ[ci]
                ci += 1
            endwhile
        endif
        return
    endif
    raiderTargetX = new float[count]
    raiderTargetY = new float[count]
    raiderTargetZ = new float[count]
    raiderCorpseX = new float[count]
    raiderCorpseY = new float[count]
    raiderCorpseZ = new float[count]
    raiderAbsentSec = new float[count]
    raiderCleared = new bool[count]
    raiderRescued = new bool[count]
    raiderEngaged = new bool[count]
    raiderArmed = new bool[count]
    raiderStartCombatAt = new float[count]
    raiderRescueSec = new float[count]
    raiderRescueX = new float[count]
    raiderRescueY = new float[count]
    raiderRescueZ = new float[count]
    raiderRescueHp = new float[count]
    float doorX = PrestonLocalX + MergeOffsetX
    float doorY = PrestonLocalY + MergeOffsetY
    float doorZ = PrestonLocalZ
    int i = 0
    while i < count
        Actor r = Raiders[i]
        float tx = doorX - 18.0
        float ty = doorY
        float tz = doorZ
        bool clearAbsentDead = False
        if r != None
            float rx = r.GetPositionX()
            float ry = r.GetPositionY()
            float rz = r.GetPositionZ()
            float ux = rx + MergeOffsetX
            float uy = ry + MergeOffsetY
            if (ux - doorX) * (ux - doorX) + (uy - doorY) * (uy - doorY) <= RelocateRadius * RelocateRadius
                tx = ux
                ty = uy
                tz = rz
            elseif (rx - doorX) * (rx - doorX) + (ry - doorY) * (ry - doorY) <= Wfc01MaxDrift * Wfc01MaxDrift && rz >= doorZ - Wfc01SubterraneanDrop
                tx = rx
                ty = ry
                tz = rz
            elseif r.IsDead()
                ; N2: Never invent doorX-18.0 for an already-dead raider outside Concord on late init (prevents corpse pileups).
                tx = rx
                ty = ry
                tz = rz
                clearAbsentDead = True
            endif
        endif
        raiderTargetX[i] = tx
        raiderTargetY[i] = ty
        raiderTargetZ[i] = tz
        raiderCorpseX[i] = tx
        raiderCorpseY[i] = ty
        raiderCorpseZ[i] = tz
        raiderAbsentSec[i] = 0.0
        raiderCleared[i] = clearAbsentDead
        raiderRescued[i] = False
        raiderEngaged[i] = False
        raiderArmed[i] = False
        raiderStartCombatAt[i] = -999.0
        raiderRescueSec[i] = 0.0
        raiderRescueX[i] = tx
        raiderRescueY[i] = ty
        raiderRescueZ[i] = tz
        raiderRescueHp[i] = -1.0
        i += 1
    endwhile
EndFunction

Function KeepCodsworthStart()
{Starts Codsworth's own check once (review 20 Oct); also from the mission timer, for a save that ran OnQuestInit before
 this check existed.}
    if Codsworth != None && !codsworthKept
        codsworthKept = True
        StartTimer(CodsworthCheck, 2)
    endif
EndFunction

Function KeepCodsworthLoad()
{The keeper's start, at its init and on every save load: Codsworth enabled, fresh budgets of failed moves for him and
 Preston, one line each of where they are (in the log and on screen), the timer (re)started.}
    if Codsworth != None
        if Codsworth.IsDisabled()
            Codsworth.Enable()
            Trace("codsworth was disabled: enabled")
        endif
        EnsureActorTalkable(Codsworth)
        codsworthFails = 0
        codsworthKept = True
        codsworthHeld = False
    endif
    EnsureActorTalkable(Preston)
    prestonFails = 0
    prestonHeld = False
    ; prestonFollow stays as the save left it. Clearing it here would put the door hold back over a follow.
    TracePreston("keeper load")
    if IsTestModeEnabled()
        Debug.Notification("FO4SF keeper: Preston " + (prestonOff as int) + " m from his spot (last: " + prestonState + ", moves " + prestonMoves + ")")
    endif
    if Codsworth != None
        TraceCodsworth("keeper load")
        if IsTestModeEnabled()
            Debug.Notification("FO4SF keeper: Codsworth " + (codsworthOff as int) + " m from his spot (last: " + codsworthState + ", moves " + codsworthMoves + ")")
        endif
    endif
    StartTimer(CodsworthCheck, 2)
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    if KeeperOnly
        KeepCodsworthLoad()
        return
    endif
    relocateFails = 0
    prestonHeld = False
    talkActivated = False
    talkStartedAt = 0.0
    talkNearSec = 0.0
    prestonTalkBoxOpen = False
    prestonFallbackActive = False
    prestonTalkReloaded = True
    prestonDialogueMenuOpen = False
    prestonScenePending = False
    prestonSceneMenuOpened = False
    prestonScenePhase1 = False
    prestonPhase1At = 0.0
    prestonSceneChecks = 0
    prestonSceneRestarts = 0
    prestonPostSceneActive = False
    s6RoomScenePending = False
    s6RoomSceneMenuOpened = False
    s6RoomSceneRestarting = False
    s6RoomScenePhase1 = False
    s6RoomPhase1At = 0.0
    s6RoomAttemptStartedAt = 0.0
    s6RoomSceneTicks = 0
    s6SturgesScenePending = False
    s6SturgesSceneMenuOpened = False
    s6SturgesSceneRestarting = False
    s6SturgesScenePhase1 = False
    s6SturgesPhase1At = 0.0
    s6SturgesAttemptStartedAt = 0.0
    s6SturgesSceneTicks = 0
    ownPrestonSceneStop = False
    prestonAttemptStartedAt = 0.0
    CancelTimer(3)
    CancelTimer(5)
    CancelTimer(6)
    EnsureActorTalkable(Preston)
    RegisterForRemoteEvent(Preston, "OnActivate")
    InitRaiderTracking()
    int st = GetStage()
    if applied > st
        st = applied
    endif
    Trace("reload mission stage=" + st + " relocate_fails=" + relocateFails)
    if st < 200
        EnsurePrestonAlias()
        RegisterForMenuOpenCloseEvent("DialogueMenu")
        RegisterPrestonSceneEvents()
        RegisterS6RoomEvents()
        if st == 20
            CheckConcordRaidersWfc01(Game.GetPlayer(), False)
        endif
        StartTimer(1.0, 1)
    else
        RegisterForMenuOpenCloseEvent("DialogueMenu")
        RegisterPrestonSceneEvents()
        CheckConcordRaidersWfc01(Game.GetPlayer(), False)
    endif
EndEvent

Function AdvanceTo(int n, string by = "Trigger")
{SetStage, then the stage's actions. Apply runs each stage once.}
    if KeeperOnly
        return
    endif
    pendingStage = n
    pendingStageBy = by
    SetStage(n)
    Apply(n, by)
    if pendingStage == n
        pendingStage = -1
    endif
EndFunction

Event OnStageSet(int auiStageID, int auiItemID)
    if KeeperOnly
        return
    endif
    string cause = "other"
    if auiStageID == pendingStage
        cause = pendingStageBy
        pendingStage = -1
    elseif auiStageID == 35 && talkActivated && !prestonUsedFallback
        cause = "info"
    endif
    Apply(auiStageID, cause)
    Scene scn = ResolvePrestonScene()
    if !EnableS6ToS9Full && EffectiveStage() == 40 && (scn == None || !scn.IsPlaying())
        AdvanceTo(200, "Trigger")
        CompleteQuest()
        Trace("complete stage=" + EffectiveStage())
    endif
EndEvent

Function Apply(int auiStageID, string by = "other")
    if KeeperOnly || auiStageID <= applied
        return
    endif
    applied = auiStageID
    Trace("stage " + auiStageID + " by=" + by)
    if auiStageID == 10
        min00Given = True
        if FO4SF_QuestToastUtil.ShowObjectiveOnce(Self, 10, MuteDuplicateObjectiveToasts, obj10DisplayedOnce)
            obj10DisplayedOnce = True
        endif
    elseif auiStageID == 20
        SetObjectiveCompleted(10)
        if FO4SF_QuestToastUtil.ShowObjectiveOnce(Self, 85, MuteDuplicateObjectiveToasts, obj85DisplayedOnce)
            obj85DisplayedOnce = True
        endif
    elseif auiStageID == 30
        Preston.StopCombat()                             ; in game 18 Oct: downed in the fight, he got up and shot the player
        SetObjectiveCompleted(85)
        if FO4SF_QuestToastUtil.ShowObjectiveOnce(Self, 86, MuteDuplicateObjectiveToasts, obj86DisplayedOnce)
            obj86DisplayedOnce = True
        endif
    elseif auiStageID == 35
        if EnableS6ToS9Full
            SetObjectiveCompleted(60)
            if FO4SF_QuestToastUtil.ShowObjectiveOnce(Self, 86, MuteDuplicateObjectiveToasts, obj86DisplayedOnce)
                obj86DisplayedOnce = True
            endif
        elseif by == "info" && !prestonUsedFallback && !prestonTalkLogged
            prestonTalkLogged = True
            Trace("preston talk end info=0x092A -> stage 40")
            AdvanceTo(40, "info")
        else
            AdvanceTo(40, "other")
        endif
    elseif auiStageID == 40
        SetObjectiveCompleted(86)
        if !EnableS6ToS9Full
            Game.GetPlayer().AddItem(Credits, RewardCount)
            Trace("reward credits=" + RewardCount)
        endif
    elseif auiStageID == 200
        CancelTimer(1)
        ; R1: Follow Fallout4.esm Min00 -> Min01 (First Settlement only). Do NOT auto-start MQ103 here;
        ; MQ103 starts organically via Diamond City gate proximity or Sanctuary handoff after First Settlement.
        Quest sanctuaryQuest = Game.GetFormFromFile(0x000817, "FO4SFMission.esm") as Quest
        if sanctuaryQuest != None && !sanctuaryQuest.IsRunning()
            bool startedSanctuary = sanctuaryQuest.StartNoWait()
            Trace("sanctuary01 start_requested ok=" + startedSanctuary)
            if !sanctuaryQuest.IsRunning()
                StartTimer(5.0, 4)
            endif
        endif
    endif
EndFunction

Function EnsureSanctuaryStarted()
    if KeeperOnly || IsWarfareMode()
        return
    endif
    Quest sanctuaryQuest = Game.GetFormFromFile(0x000817, "FO4SFMission.esm") as Quest
    if sanctuaryQuest == None || sanctuaryQuest.IsRunning() || sanctuaryQuest.IsCompleted()
        CancelTimer(4)
        return
    endif
    bool ok = sanctuaryQuest.StartNoWait()
    sanctuaryStartRetries += 1
    Trace("sanctuary01 start_retry n=" + sanctuaryStartRetries + " ok=" + ok)
    if !sanctuaryQuest.IsRunning() && !sanctuaryQuest.IsCompleted() && sanctuaryStartRetries < 60
        StartTimer(5.0, 4)
    endif
EndFunction

Message Function ResolvePrestonMsg(int slot)
    if slot == 0
        if PrestonReply0Msg != None
            return PrestonReply0Msg
        endif
        return Game.GetFormFromFile(0x000976, "FO4SFMission.esm") as Message
    elseif slot == 1
        if PrestonReply1Msg != None
            return PrestonReply1Msg
        endif
        return Game.GetFormFromFile(0x000977, "FO4SFMission.esm") as Message
    elseif slot == 2
        if PrestonReply2Msg != None
            return PrestonReply2Msg
        endif
        return Game.GetFormFromFile(0x000978, "FO4SFMission.esm") as Message
    endif
    if PrestonTalkMsg != None
        return PrestonTalkMsg
    endif
    return Game.GetFormFromFile(0x000975, "FO4SFMission.esm") as Message
EndFunction

Function RunPrestonTalk(int stage, Message startMsg)
    if !ShouldUseMessageBox()
        Trace("preston messagebox suppressed reason=glob_off stage=" + stage)
        return
    endif
    if prestonTalkBoxOpen || startMsg == None || IsWarfareMode()
        return
    endif
    ; A2.2: Never show MessageBox if native DialogueMenu is open (never both).
    if prestonDialogueMenuOpen || prestonSceneMenuOpened
        Trace("preston messagebox suppressed reason=dialogue_menu_open stage=" + stage)
        return
    endif
    prestonTalkReloaded = False
    talkSessionId += 1
    int mySession = talkSessionId
    prestonTalkBoxOpen = True
    Message curMsg = startMsg
    Trace("preston talk opened stage=" + stage)
    int steps = 0
    bool doneLoop = False
    while !doneLoop && steps < 16
        steps += 1
        int btn = curMsg.Show()
        if prestonTalkReloaded || mySession != talkSessionId || btn < 0
            doneLoop = True
        else
            Trace("preston choice button=" + btn)
            if btn == 0
                Message r0 = ResolvePrestonMsg(0)
                if r0 != None
                    curMsg = r0
                endif
            elseif btn == 1
                Message r1 = ResolvePrestonMsg(1)
                if r1 != None
                    curMsg = r1
                endif
            elseif btn == 2
                Message r2 = ResolvePrestonMsg(2)
                if r2 != None
                    curMsg = r2
                endif
            else
                if btn == 3 && EffectiveStage() == 30
                    talkActivated = True
                    prestonUsedFallback = False
                    AdvanceTo(35, "info")
                    if !EnableS6ToS9Full && EffectiveStage() == 40
                        AdvanceTo(200, "Trigger")
                        CompleteQuest()
                        Trace("complete stage=" + EffectiveStage())
                    endif
                endif
                doneLoop = True
            endif
        endif
    endwhile
    if !prestonTalkReloaded && mySession == talkSessionId
        prestonTalkBoxOpen = False
        ; R11 Review Item #1: Clear fallback latch when MessageBox exits without advancing past stage 30 (< 35)
        ; or after reaching completion (>= 200) so Preston is never locked out of subsequent activation.
        int endSt = EffectiveStage()
        if endSt < 35 || endSt >= 200
            prestonFallbackActive = False
        endif
    endif
EndFunction

Function FallbackPrestonToMessageBox(string reason)
    if !ShouldUseMessageBox()
        Trace("preston fallback suppressed reason=glob_off orig=" + reason)
        return
    endif
    ; A2.2: Never open MessageBox if DialogueMenu already opened, fallback already latched, or talk already finished.
    if prestonDialogueMenuOpen || prestonSceneMenuOpened || prestonTalkBoxOpen || prestonFallbackActive || prestonTalkLogged
        prestonScenePending = False
        prestonScenePhase1 = False
        prestonPhase1At = 0.0
        CancelTimer(3)
        Trace("preston fallback suppressed reason=dialogue_active orig=" + reason)
        return
    endif
    prestonScenePending = False
    prestonScenePhase1 = False
    prestonPhase1At = 0.0
    CancelTimer(3)
    ; A2.2 + C1: Latch prestonFallbackActive BEFORE scn.Stop() so any concurrent/late native greeting
    ; firing OnBegin/OnPhaseBegin/OnMenuOpenCloseEvent immediately suppresses itself (never both).
    prestonFallbackActive = True
    Scene scn = ResolvePrestonScene()
    if scn != None && scn.IsPlaying()
        ownPrestonSceneStop = True
        scn.Stop()
    endif
    if prestonDialogueMenuOpen || prestonSceneMenuOpened
        ; R11 Review Item #1: Clear fallback latch when yielding to a late-opened DialogueMenu so it never strands future talks.
        prestonFallbackActive = False
        Trace("preston fallback suppressed reason=late_dialogue_open orig=" + reason)
        return
    endif
    Trace("preston talk fallback=messagebox reason=" + reason)
    Message talkMsg = ResolvePrestonMsg(-1)
    if talkMsg != None
        RunPrestonTalk(EffectiveStage(), talkMsg)
    elseif EffectiveStage() == 30
        prestonUsedFallback = True
        AdvanceTo(40, "fallback")
    endif
EndFunction

Function RestartOrFailPrestonScene(string reason, bool postMode)
    if KeeperOnly || ShouldUseMessageBox()
        return
    endif
    if prestonDialogueMenuOpen || prestonSceneMenuOpened || prestonTalkBoxOpen
        prestonScenePending = False
        prestonScenePhase1 = False
        prestonPhase1At = 0.0
        prestonAttemptStartedAt = 0.0
        CancelTimer(3)
        return
    endif
    int st = EffectiveStage()
    if !postMode && (st != 30 || prestonTalkLogged)
        prestonScenePending = False
        prestonScenePhase1 = False
        prestonPhase1At = 0.0
        prestonAttemptStartedAt = 0.0
        CancelTimer(3)
        return
    endif
    Scene scn = ResolveActivePrestonScene(postMode)
    if scn == None
        int usedRetries = prestonSceneRestarts
        prestonScenePending = False
        prestonScenePhase1 = False
        prestonPhase1At = 0.0
        prestonSceneRestarts = 0
        prestonPostSceneActive = False
        prestonAttemptStartedAt = 0.0
        CancelTimer(3)
        EnsureActorTalkable(Preston)
        Trace("preston talk ERROR scene_failed retries=" + usedRetries + " reason=" + reason + " actor_talkable=true")
        return
    endif
    if prestonSceneRestarts < PrestonMaxSceneRestarts
        prestonSceneRestarts += 1
        prestonScenePending = False
        if postMode
            EnsureKeeperPrestonAlias()
        else
            EnsurePrestonAlias()
        endif
        RegisterPrestonSceneEvents()
        EnsureActorTalkable(Preston)
        if scn.IsPlaying()
            ownPrestonSceneStop = True
            scn.Stop()
        endif
        prestonPostSceneActive = postMode
        prestonScenePending = True
        prestonSceneMenuOpened = False
        prestonScenePhase1 = False
        prestonPhase1At = 0.0
        prestonAttemptStartedAt = Utility.GetCurrentRealTime()
        prestonSceneChecks = 0
        if !postMode
            talkActivated = True
            prestonUsedFallback = False
            talkStartedAt = Utility.GetCurrentRealTime()
        endif
        scn.Start()
        if !scn.IsPlaying()
            scn.ForceStart()
        endif
        Trace("preston talk scene_restart retry=" + prestonSceneRestarts + "/" + PrestonMaxSceneRestarts + " reason=" + reason + " stage=" + st)
        StartTimer(PrestonSceneCheckSeconds, 3)
    else
        int maxUsed = prestonSceneRestarts
        prestonScenePending = False
        if scn.IsPlaying()
            ownPrestonSceneStop = True
            scn.Stop()
        endif
        prestonScenePhase1 = False
        prestonPhase1At = 0.0
        prestonSceneRestarts = 0
        prestonPostSceneActive = False
        prestonAttemptStartedAt = 0.0
        CancelTimer(3)
        EnsureActorTalkable(Preston)
        Trace("preston talk ERROR scene_failed retries=" + maxUsed + " reason=" + reason + " actor_talkable=true")
    endif
EndFunction

Function CheckPrestonSceneOpen()
    if KeeperOnly || !prestonScenePending
        return
    endif
    int st = EffectiveStage()
    bool stageValid = (prestonPostSceneActive && st >= 200) || (!prestonPostSceneActive && st == 30 && !prestonTalkLogged)
    if prestonDialogueMenuOpen || prestonSceneMenuOpened || prestonTalkBoxOpen || prestonFallbackActive || !stageValid
        prestonScenePending = False
        prestonScenePhase1 = False
        prestonPhase1At = 0.0
        prestonAttemptStartedAt = 0.0
        return
    endif
    prestonSceneChecks += 1
    float nowRt = Utility.GetCurrentRealTime()
    if prestonAttemptStartedAt > 0.0 && nowRt < prestonAttemptStartedAt
        prestonAttemptStartedAt = nowRt
    endif
    float attemptElapsed = PrestonSceneCheckSeconds
    if prestonAttemptStartedAt > 0.0
        attemptElapsed = nowRt - prestonAttemptStartedAt
    endif
    bool phase1Elapsed = False
    if prestonScenePhase1
        if nowRt < prestonPhase1At
            prestonPhase1At = nowRt
        elseif (nowRt - prestonPhase1At) >= (PrestonSceneCheckSeconds - 0.05)
            phase1Elapsed = True
        endif
    endif
    Scene scn = ResolveActivePrestonScene(prestonPostSceneActive)
    if scn == None || !scn.IsPlaying()
        if ShouldUseMessageBox()
            FallbackPrestonToMessageBox("scene_inactive")
        elseif attemptElapsed < (PrestonSceneCheckSeconds - 0.05)
            StartTimer(PrestonSceneCheckSeconds - attemptElapsed, 3)
        else
            RestartOrFailPrestonScene("scene_inactive", prestonPostSceneActive)
        endif
    elseif (phase1Elapsed || prestonSceneChecks >= PrestonSceneMaxWaitChecks) && attemptElapsed >= (PrestonSceneCheckSeconds - 0.05)
        prestonScenePending = False
        prestonScenePhase1 = False
        prestonPhase1At = 0.0
        if prestonDialogueMenuOpen || prestonSceneMenuOpened
            return
        endif
        if ShouldUseMessageBox()
            FallbackPrestonToMessageBox("dialogue_menu_timeout")
        else
            RestartOrFailPrestonScene("dialogue_menu_timeout", prestonPostSceneActive)
        endif
    elseif phase1Elapsed || prestonSceneChecks >= PrestonSceneMaxWaitChecks
        StartTimer(PrestonSceneCheckSeconds - attemptElapsed, 3)
    else
        StartTimer(PrestonSceneCheckSeconds, 3)
    endif
EndFunction

Event OnMenuOpenCloseEvent(string asMenuName, bool abOpening)
    if KeeperOnly || asMenuName != "DialogueMenu"
        return
    endif
    prestonDialogueMenuOpen = abOpening
    Scene scn = ResolvePrestonScene()
    Scene postScn = ResolvePrestonPostScene()
    bool primaryPlaying = scn != None && scn.IsPlaying()
    bool postPlaying = postScn != None && postScn.IsPlaying()
    bool s6PrestonPlaying = S6PrestonRoomScene != None && S6PrestonRoomScene.IsPlaying()
    bool s6SturgesPlaying = S6SturgesRoomScene != None && S6SturgesRoomScene.IsPlaying()
    if abOpening
        if s6RoomScenePending || s6PrestonPlaying
            s6RoomSceneMenuOpened = True
            s6RoomScenePending = False
            s6RoomScenePhase1 = False
            s6RoomPhase1At = 0.0
            s6RoomSceneRetries = 0
            s6RoomAttemptStartedAt = 0.0
            CancelTimer(5)
            Trace("s6 preston room dialogue menu opened")
        endif
        if s6SturgesScenePending || s6SturgesPlaying
            s6SturgesSceneMenuOpened = True
            s6SturgesScenePending = False
            s6SturgesScenePhase1 = False
            s6SturgesPhase1At = 0.0
            s6SturgesSceneRetries = 0
            s6SturgesAttemptStartedAt = 0.0
            CancelTimer(6)
            Trace("s6 sturges room dialogue menu opened")
        endif
        int st = EffectiveStage()
        if prestonTalkBoxOpen || prestonFallbackActive
            ; A2.2: Suppress any late native greeting scene unconditionally when MessageBox fallback is active.
            if primaryPlaying
                ownPrestonSceneStop = True
                scn.Stop()
                Trace("preston scene suppressed reason=single_talk stage=" + st)
            endif
            if postPlaying
                ownPrestonSceneStop = True
                postScn.Stop()
                Trace("preston scene suppressed reason=single_talk stage=" + st)
            endif
            return
        endif
        if st >= 200
            if primaryPlaying
                ownPrestonSceneStop = True
                scn.Stop()
                Trace("preston scene suppressed reason=single_talk stage=" + st)
            endif
            if prestonPostSceneActive || postPlaying
                prestonPostSceneActive = True
                prestonSceneMenuOpened = True
                prestonScenePending = False
                prestonScenePhase1 = False
                prestonPhase1At = 0.0
                prestonSceneRestarts = 0
                prestonAttemptStartedAt = 0.0
                CancelTimer(3)
                Trace("preston dialogue menu opened mode=post stage=" + st)
            endif
            return
        endif
        if prestonTalkLogged || st >= 35
            if scn != None
                if scn.IsPlaying()
                    ownPrestonSceneStop = True
                endif
                scn.Stop()
                Trace("preston scene suppressed reason=single_talk stage=" + st)
            endif
            return
        endif
        if prestonScenePending || talkActivated || primaryPlaying
            talkActivated = True
            prestonUsedFallback = False
            prestonSceneMenuOpened = True
            prestonScenePending = False
            prestonScenePhase1 = False
            prestonPhase1At = 0.0
            prestonSceneRestarts = 0
            prestonAttemptStartedAt = 0.0
            CancelTimer(3)
            Trace("preston dialogue menu opened")
        endif
    elseif prestonSceneMenuOpened || s6RoomSceneMenuOpened || s6SturgesSceneMenuOpened
        if prestonSceneMenuOpened
            prestonSceneMenuOpened = False
            Trace("preston dialogue menu closed stage=" + EffectiveStage())
        endif
        if s6RoomSceneMenuOpened
            s6RoomSceneMenuOpened = False
            Trace("s6 preston room dialogue menu closed stage=" + EffectiveStage())
            if EffectiveStage() < 40 && s6FullStage < 40
                AdvanceS6PrestonGroupTalk()
            endif
        endif
        if s6SturgesSceneMenuOpened
            s6SturgesSceneMenuOpened = False
            Trace("s6 sturges room dialogue menu closed stage=" + EffectiveStage())
        endif
    endif
EndEvent

Event Scene.OnBegin(Scene akSender)
    if KeeperOnly
        return
    endif
    if S6PrestonRoomScene != None && akSender == S6PrestonRoomScene
        s6RoomScenePhase1 = False
        s6RoomPhase1At = 0.0
        s6RoomSceneTicks = 0
        Trace("s6 preston room scene started")
        return
    endif
    if S6SturgesRoomScene != None && akSender == S6SturgesRoomScene
        s6SturgesScenePhase1 = False
        s6SturgesPhase1At = 0.0
        s6SturgesSceneTicks = 0
        Trace("s6 sturges room scene started")
        return
    endif
    Scene scn = ResolvePrestonScene()
    Scene postScn = ResolvePrestonPostScene()
    if scn != None && akSender == scn
        ; C1 + A2.2: Never allow a queued/late DEVT scene to run if MessageBox fallback already latched or talk finished.
        if prestonTalkBoxOpen || prestonFallbackActive || prestonTalkLogged || EffectiveStage() >= 35 || ShouldUseMessageBox()
            if akSender.IsPlaying()
                ownPrestonSceneStop = True
            endif
            akSender.Stop()
            Trace("preston scene suppressed reason=single_talk stage=" + EffectiveStage())
            return
        endif
        prestonPostSceneActive = False
        talkActivated = True
        prestonUsedFallback = False
        FaceActorToward(Preston, Game.GetPlayer())
        if talkStartedAt <= 0.0
            talkStartedAt = Utility.GetCurrentRealTime()
        endif
        if EffectiveStage() == 30 && !prestonScenePending && !prestonSceneMenuOpened && !prestonDialogueMenuOpen
            ownPrestonSceneStop = False
            prestonScenePending = True
            prestonScenePhase1 = False
            prestonPhase1At = 0.0
            prestonAttemptStartedAt = Utility.GetCurrentRealTime()
            prestonSceneChecks = 0
            Trace("preston scene talk requested scene=" + scn + " stage=30")
            StartTimer(PrestonSceneCheckSeconds, 3)
        endif
        Trace("preston talk scene started stage=" + EffectiveStage())
    elseif postScn != None && akSender == postScn
        int st = EffectiveStage()
        if prestonTalkBoxOpen || prestonFallbackActive || st < 200 || ShouldUseMessageBox()
            if akSender.IsPlaying()
                ownPrestonSceneStop = True
            endif
            akSender.Stop()
            Trace("preston scene suppressed reason=single_talk stage=" + st)
            return
        endif
        prestonPostSceneActive = True
        FaceActorToward(Preston, Game.GetPlayer())
        if !prestonScenePending && !prestonSceneMenuOpened && !prestonDialogueMenuOpen
            ownPrestonSceneStop = False
            prestonScenePending = True
            prestonScenePhase1 = False
            prestonPhase1At = 0.0
            prestonAttemptStartedAt = Utility.GetCurrentRealTime()
            prestonSceneChecks = 0
            Trace("preston scene talk requested scene=" + postScn + " stage=" + st + " mode=post")
            StartTimer(PrestonSceneCheckSeconds, 3)
        endif
        Trace("preston talk scene started stage=" + st + " mode=post")
    endif
EndEvent

Event Scene.OnPhaseBegin(Scene akSender, int auiPhaseIndex)
    if KeeperOnly
        return
    endif
    if S6PrestonRoomScene != None && akSender == S6PrestonRoomScene
        Trace("s6 preston room scene phase=" + auiPhaseIndex)
        if auiPhaseIndex >= 1
            s6RoomScenePhase1 = True
            s6RoomPhase1At = Utility.GetCurrentRealTime()
            if s6RoomScenePending && !s6RoomSceneMenuOpened && !prestonDialogueMenuOpen
                CancelTimer(5)
                StartTimer(PrestonSceneCheckSeconds, 5)
            endif
        endif
        return
    endif
    if S6SturgesRoomScene != None && akSender == S6SturgesRoomScene
        Trace("s6 sturges room scene phase=" + auiPhaseIndex)
        if auiPhaseIndex >= 1
            s6SturgesScenePhase1 = True
            s6SturgesPhase1At = Utility.GetCurrentRealTime()
            if s6SturgesScenePending && !s6SturgesSceneMenuOpened && !prestonDialogueMenuOpen
                CancelTimer(6)
                StartTimer(PrestonSceneCheckSeconds, 6)
            endif
        endif
        return
    endif
    Scene scn = ResolvePrestonScene()
    Scene postScn = ResolvePrestonPostScene()
    if scn != None && akSender == scn
        ; A2.2: Immediately stop any late native phase advance if fallback/box already owns the talk (never both).
        if prestonTalkBoxOpen || prestonFallbackActive || prestonTalkLogged || EffectiveStage() >= 35
            if akSender.IsPlaying()
                ownPrestonSceneStop = True
            endif
            akSender.Stop()
            Trace("preston scene suppressed reason=single_talk stage=" + EffectiveStage())
            return
        endif
        Trace("preston talk scene phase=" + auiPhaseIndex + " stage=" + EffectiveStage())
        if auiPhaseIndex >= 1
            prestonScenePhase1 = True
            prestonPhase1At = Utility.GetCurrentRealTime()
            if prestonScenePending && !prestonSceneMenuOpened && !prestonDialogueMenuOpen
                CancelTimer(3)
                StartTimer(PrestonSceneCheckSeconds, 3)
            endif
        endif
    elseif postScn != None && akSender == postScn
        int st = EffectiveStage()
        if prestonTalkBoxOpen || prestonFallbackActive || st < 200 || ShouldUseMessageBox()
            if akSender.IsPlaying()
                ownPrestonSceneStop = True
            endif
            akSender.Stop()
            Trace("preston scene suppressed reason=single_talk stage=" + st)
            return
        endif
        Trace("preston talk scene phase=" + auiPhaseIndex + " stage=" + st + " mode=post")
        if auiPhaseIndex >= 1
            prestonScenePhase1 = True
            prestonPhase1At = Utility.GetCurrentRealTime()
            if prestonScenePending && !prestonSceneMenuOpened && !prestonDialogueMenuOpen
                CancelTimer(3)
                StartTimer(PrestonSceneCheckSeconds, 3)
            endif
        endif
    endif
EndEvent

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    if KeeperOnly
        return
    endif
    Actor player = Game.GetPlayer()
    if player == None || (akActionRef != None && akActionRef != player)
        return
    endif
    if akSender == SturgesRef && EnableS6ToS9Full && EffectiveStage() >= 35
        TriggerS6RoomScene(True, "activate")
        return
    endif
    ObjectReference termRef = LookupOptionalForm(0x00E35E, "FO4Port.esm") as ObjectReference
    if termRef != None && akSender == termRef
        if !termRef.IsLocked() || PlayerHasBobbyPin(player) || EffectiveStage() >= 40
            termRef.BlockActivation(False, False)
            termRef.Unlock(False)
            termRef.SetLockLevel(0)
            termRef.Lock(False, False, False)
            TryOpenS6BasementGate("terminal")
        else
            termRef.BlockActivation(True, False)
            Trace("s6 basement_terminal locked needs=bobby_pin_or_stage40")
        endif
        return
    endif
    ObjectReference gateRef = LookupOptionalForm(0x00EDF0, "FO4Port.esm") as ObjectReference
    if gateRef != None && akSender == gateRef
        if !gateRef.IsLocked()
            gateRef.BlockActivation(False, False)
            TryOpenS6BasementGate("already_unlocked")
        elseif PlayerHasBobbyPin(player)
            TryOpenS6BasementGate("bobby_pin")
        else
            gateRef.BlockActivation(True, False)
            if IsTestModeEnabled()
                Debug.Notification("Locked (Novice). Requires Bobby Pin or Security Terminal.")
            endif
            Trace("s6 basement_gate locked needs=bobby_pin_or_terminal")
        endif
        return
    endif
    if akSender == Preston && akActionRef == player
        if EnableS6ToS9Full && s5MuseumCleared && EffectiveStage() == 35 && s6FullStage < 40 && S6PrestonRoomScene != None
            TriggerS6RoomScene(False, "activate")
            return
        endif
        if prestonTalkBoxOpen || prestonDialogueMenuOpen || prestonSceneMenuOpened || prestonScenePending
            return
        endif
        ; R11 Review Item #1: Never let stale prestonFallbackActive alone block OnActivate when no box/menu/scene is active.
        if prestonFallbackActive
            prestonFallbackActive = False
        endif
        prestonSceneRestarts = 0
        int stage = EffectiveStage()
        Trace("preston activated at stage " + stage)
        if stage < 20
            FoundPreston("activated")                    ; the next check starts the fight
        elseif stage == 30
            FaceActorToward(Preston, Game.GetPlayer())
            Scene scn = ResolvePrestonSceneLogged()
            ; A2.2: Re-check after ResolvePrestonSceneLogged() so a concurrent native DEVT greeting that already
            ; opened DialogueMenu (observed in 2g run3 at rt=343.486 vs 343.662) is never overwritten or re-armed.
            if prestonTalkBoxOpen || prestonDialogueMenuOpen || prestonSceneMenuOpened || prestonFallbackActive || prestonTalkLogged || EffectiveStage() != 30
                return
            endif
            if ShouldUseMessageBox()
                FallbackPrestonToMessageBox("glob")
            elseif scn != None
                EnsurePrestonAlias()
                RegisterPrestonSceneEvents()
                if prestonTalkBoxOpen || prestonDialogueMenuOpen || prestonSceneMenuOpened || prestonFallbackActive
                    return
                endif
                prestonFallbackActive = False
                prestonPostSceneActive = False
                talkActivated = True
                prestonUsedFallback = False
                talkStartedAt = Utility.GetCurrentRealTime()
                ownPrestonSceneStop = False
                prestonScenePending = True
                prestonSceneMenuOpened = False
                prestonScenePhase1 = False
                prestonPhase1At = 0.0
                prestonAttemptStartedAt = Utility.GetCurrentRealTime()
                prestonSceneChecks = 0
                if !scn.IsPlaying()
                    scn.Start()
                    if !scn.IsPlaying()
                        scn.ForceStart()
                    endif
                endif
                Trace("preston talk scene triggered stage=30")
                Trace("preston scene talk requested scene=" + scn + " stage=30")
                StartTimer(PrestonSceneCheckSeconds, 3)
            else
                RestartOrFailPrestonScene("no_scene", False)
            endif
        elseif stage >= 200
            if ShouldUseMessageBox()
                Message postMsg = ResolvePrestonMsg(-1)
                if postMsg != None
                    RunPrestonTalk(stage, postMsg)
                endif
            else
                FaceActorToward(Preston, Game.GetPlayer())
                Scene postScn = ResolvePrestonPostScene()
                if postScn != None
                    EnsureKeeperPrestonAlias()
                    RegisterPrestonSceneEvents()
                    EnsureActorTalkable(Preston)
                    if prestonTalkBoxOpen || prestonDialogueMenuOpen || prestonSceneMenuOpened || prestonFallbackActive
                        return
                    endif
                    prestonFallbackActive = False
                    prestonPostSceneActive = True
                    ownPrestonSceneStop = False
                    prestonScenePending = True
                    prestonSceneMenuOpened = False
                    prestonScenePhase1 = False
                    prestonPhase1At = 0.0
                    prestonAttemptStartedAt = Utility.GetCurrentRealTime()
                    prestonSceneChecks = 0
                    if !postScn.IsPlaying()
                        postScn.Start()
                        if !postScn.IsPlaying()
                            postScn.ForceStart()
                        endif
                    endif
                    Trace("preston talk scene triggered stage=" + stage + " mode=post")
                    Trace("preston scene talk requested scene=" + postScn + " stage=" + stage + " mode=post")
                    StartTimer(PrestonSceneCheckSeconds, 3)
                else
                    RestartOrFailPrestonScene("no_post_scene", True)
                endif
            endif
        endif
    endif
EndEvent

Event Scene.OnEnd(Scene akSender)
    if KeeperOnly
        return
    endif
    Scene scn = ResolvePrestonScene()
    Scene postScn = ResolvePrestonPostScene()
    if scn != None && akSender == scn
        if ownPrestonSceneStop
            ownPrestonSceneStop = False
            return
        endif
        int st = EffectiveStage()
        bool endInfoDone = GetStageDone(35) || st == 35 || GetStage() == 35
        Trace("preston talk scene ended stage=" + st + " end_info=" + endInfoDone)
        if endInfoDone
            prestonScenePending = False
            prestonSceneMenuOpened = False
            prestonScenePhase1 = False
            prestonPhase1At = 0.0
            prestonAttemptStartedAt = 0.0
            CancelTimer(3)
            if applied < 35
                Apply(35, "info")
            endif
            if !EnableS6ToS9Full && EffectiveStage() == 40
                AdvanceTo(200, "Trigger")
                CompleteQuest()
                Trace("complete stage=" + EffectiveStage())
            endif
        elseif st == 30 && !prestonTalkLogged && !prestonFallbackActive
            if prestonScenePending && !prestonSceneMenuOpened
                ; F1: Never count restart OnEnds into talkFailures (prevents stage 40 by=fallback skip),
                ; and count a retry ONLY after a full PrestonSceneCheckSeconds window.
                if ShouldUseMessageBox()
                    FallbackPrestonToMessageBox("scene_incomplete")
                else
                    float nowEnd = Utility.GetCurrentRealTime()
                    if prestonAttemptStartedAt > 0.0 && nowEnd < prestonAttemptStartedAt
                        prestonAttemptStartedAt = nowEnd
                    endif
                    float attElapsed = nowEnd - prestonAttemptStartedAt
                    if prestonAttemptStartedAt > 0.0 && attElapsed < (PrestonSceneCheckSeconds - 0.05)
                        CancelTimer(3)
                        StartTimer(PrestonSceneCheckSeconds - attElapsed, 3)
                    else
                        RestartOrFailPrestonScene("scene_incomplete", False)
                    endif
                endif
            else
                talkFailures += 1
                talkActivated = False
                talkStartedAt = 0.0
                Trace("preston talk retry n=" + talkFailures + " reason=scene_incomplete")
                prestonScenePending = False
                prestonSceneMenuOpened = False
                prestonScenePhase1 = False
                prestonPhase1At = 0.0
                prestonAttemptStartedAt = 0.0
                EnsureActorTalkable(Preston)
            endif
        else
            prestonScenePending = False
            prestonSceneMenuOpened = False
            prestonScenePhase1 = False
            prestonPhase1At = 0.0
            prestonAttemptStartedAt = 0.0
        endif
    elseif postScn != None && akSender == postScn
        if ownPrestonSceneStop
            ownPrestonSceneStop = False
            return
        endif
        int st = EffectiveStage()
        Trace("preston talk scene ended stage=" + st + " mode=post")
        if st >= 200 && prestonScenePending && !prestonSceneMenuOpened && !prestonFallbackActive && !ShouldUseMessageBox()
            float nowPost = Utility.GetCurrentRealTime()
            if prestonAttemptStartedAt > 0.0 && nowPost < prestonAttemptStartedAt
                prestonAttemptStartedAt = nowPost
            endif
            float postElapsed = nowPost - prestonAttemptStartedAt
            if prestonAttemptStartedAt > 0.0 && postElapsed < (PrestonSceneCheckSeconds - 0.05)
                CancelTimer(3)
                StartTimer(PrestonSceneCheckSeconds - postElapsed, 3)
            else
                RestartOrFailPrestonScene("scene_incomplete", True)
            endif
        else
            prestonScenePending = False
            prestonSceneMenuOpened = False
            prestonScenePhase1 = False
            prestonPhase1At = 0.0
            prestonAttemptStartedAt = 0.0
            prestonPostSceneActive = False
            CancelTimer(3)
            EnsureActorTalkable(Preston)
        endif
    elseif S6PrestonRoomScene != None && akSender == S6PrestonRoomScene
        HandleS6RoomSceneEnded(False)
    elseif S6SturgesRoomScene != None && akSender == S6SturgesRoomScene
        HandleS6RoomSceneEnded(True)
    endif
EndEvent

Event ObjectReference.OnLockStateChanged(ObjectReference akSender)
    if KeeperOnly
        return
    endif
    ObjectReference gateRef = LookupOptionalForm(0x00EDF0, "FO4Port.esm") as ObjectReference
    if gateRef != None && akSender == gateRef && !gateRef.IsLocked()
        TryOpenS6BasementGate("terminal")
        return
    endif
    ObjectReference termRef = LookupOptionalForm(0x00E35E, "FO4Port.esm") as ObjectReference
    if termRef != None && akSender == termRef && !termRef.IsLocked()
        TryOpenS6BasementGate("terminal")
    endif
EndEvent

bool Function MarkPrestonFallback(string why)
    if !prestonUsedFallback
        prestonUsedFallback = True
        Trace(why)
    endif
    return True
EndFunction

bool Function TalkCompleteReady(int stage, float dp)
    if stage != 30
        return False
    endif
    if prestonTalkLogged
        return True
    endif
    if prestonTalkBoxOpen || prestonDialogueMenuOpen || prestonScenePending
        talkNearSec = 0.0
        return False
    endif
    if talkFailures >= 3
        return MarkPrestonFallback("preston talk fallback tries=" + talkFailures)
    endif
    float nowRt = Utility.GetCurrentRealTime()
    if talkStartedAt > 0.0 && nowRt < talkStartedAt
        talkStartedAt = nowRt
    endif
    Scene scn = ResolvePrestonScene()
    if scn != None && scn.IsPlaying()
        talkNearSec = 0.0
        if talkStartedAt > 0.0 && (nowRt - talkStartedAt) > TalkSceneTimeout
            talkFailures += 1
            ownPrestonSceneStop = True
            scn.Stop()
            talkActivated = False
            talkStartedAt = 0.0
            Trace("preston talk retry n=" + talkFailures + " reason=timeout")
            if talkFailures >= 3
                return MarkPrestonFallback("preston talk timeout")
            endif
        endif
        return False
    endif
    if talkActivated && talkStartedAt > 0.0 && (nowRt - talkStartedAt) >= 15.0
        talkFailures += 1
        talkActivated = False
        talkStartedAt = 0.0
        Trace("preston talk retry n=" + talkFailures + " reason=after_activate")
        if talkFailures >= 3
            return MarkPrestonFallback("preston talk fallback after_activate")
        endif
        return False
    endif
    if dp < TalkRadius
        talkNearSec += 1.0
        float limit = TalkFallbackSeconds
        if IsTestModeEnabled()
            limit = 8.0
        endif
        if talkNearSec >= limit
            if scn == None
                return MarkPrestonFallback("preston talk fallback no_scene")
            endif
            return MarkPrestonFallback("preston talk fallback near_sec=" + talkNearSec)
        endif
    else
        talkNearSec = 0.0
    endif
    return False
EndFunction

Function FoundPreston(string how)
{The player reached Preston before the fight (activated him, or came within FindRadius): the fight starts at the next
 check, with every raider put into combat with the player. Logged once. A dead Preston is never found.}
    if !prestonFound && !Preston.IsDead()
        prestonFound = True
        Trace("found preston " + how)
    endif
EndFunction

float Function ComputeEffectiveWeaponDamage(Actor r, float recordDmg)
{R13 E3: Compute effective weapon damage from the VMAD-bound record damage * Actor AttackDamageMult when resolved else 1.0.}
    float mult = 1.0
    if r != None && AttackDamageMult != None
        float av = r.GetValue(AttackDamageMult)
        if av > 0.0
            mult = av
        endif
    endif
    return recordDmg * mult
EndFunction

Function ArmRaiderForCombat(Actor r, int idx)
{C3 + R11 D3 + R13 E3 + fix4 + Task 0d: Ensure each Concord raider is unrestrained, aggressive, brave, unequips only wrong
 weapons (keeping FO4 0x0988 outfits intact!), equips softened non-playable RaiderWeapon (0x97B, 4.0 dmg) +
 deterministic AmmoShotshell=60, and logs effective damage.}
    if r == None || r.IsDead()
        return
    endif
    r.SetRestrained(False)
    Weapon curW = r.GetEquippedWeapon()
    if curW != None && curW != RaiderWeapon && curW != RaiderSidearm
        r.UnequipItem(curW, False, True)
    endif
    ActorValue aggrAv = Game.GetAggressionAV()
    if aggrAv != None
        r.SetValue(aggrAv, 2.0)
    endif
    ActorValue confAv = Game.GetConfidenceAV()
    if confAv != None
        r.SetValue(confAv, 4.0)
    endif
    int targetShells = 60
    if RaiderAmmo != None
        int curShells = r.GetItemCount(RaiderAmmo)
        if curShells < targetShells
            r.AddItem(RaiderAmmo, targetShells - curShells, True)
        elseif curShells > targetShells
            r.RemoveItem(RaiderAmmo, curShells - targetShells, True)
        endif
    endif
    if RaiderWeapon != None
        if r.GetItemCount(RaiderWeapon) < 1
            r.AddItem(RaiderWeapon, 1, True)
        endif
        r.EquipItem(RaiderWeapon, False, True)
    endif
    r.EvaluatePackage()
    if raiderArmed != None && idx >= 0 && idx < raiderArmed.Length
        raiderArmed[idx] = True
    endif
    int shells = 0
    if RaiderAmmo != None
        shells = r.GetItemCount(RaiderAmmo)
    endif
    Weapon eqPrimary = r.GetEquippedWeapon()
    bool eqMatch = (RaiderWeapon != None && eqPrimary == RaiderWeapon)
    float effPrimaryDmg = ComputeEffectiveWeaponDamage(r, RaiderPrimaryRecordDamage)
    Trace("arm raider " + idx + " ammo=" + shells + " weapon=" + eqPrimary + " eq_match=" + eqMatch + " dmg=" + RaiderPrimaryRecordDamage + " eff_dmg=" + effPrimaryDmg + " playable=false standin=true")
EndFunction

Function EquipBalancedRaiderSidearm(Actor r, int idx)
{R11 Part 3 E3 + R13 fix4 + R12 S4/S5: When EnableS4Balcony is True, prefers Pipe Pistol/Rifle (0x08A2/0x08A3) + .38 (0x08A1)
 from FO4SFCoreValues.esm when present; otherwise equips softened FO4SF_ConcordRaiderSidearm (WEAP 0x097A, 1.5 dmg, ObjectTemplates preserved) + Ammo777mm (36 rounds),
 strips RaiderWeapon + RaiderAmmo FIRST, and logs effective damage.}
    if r == None || r.IsDead()
        return
    endif
    Weapon chosenWeap = None
    Ammo chosenAmmo = None
    string weapLabel = "eon"
    if EnableS4Balcony
        int wantWeapId = PipePistolId
        if idx % 2 == 1
            wantWeapId = PipeRifleId
        endif
        Weapon pw = LookupOptionalForm(wantWeapId, "FO4SFCoreValues.esm") as Weapon
        if pw == None
            pw = LookupOptionalForm(PipePistolId, "FO4SFCoreValues.esm") as Weapon
        endif
        Ammo pa = LookupOptionalForm(Ammo38Id, "FO4SFCoreValues.esm") as Ammo
        if pw != None && pa != None
            chosenWeap = pw
            chosenAmmo = pa
            weapLabel = "pipe"
        endif
    endif
    if chosenWeap == None || chosenAmmo == None
        if RaiderSidearm == None || RaiderSidearmAmmo == None
            return
        endif
        chosenWeap = RaiderSidearm
        chosenAmmo = RaiderSidearmAmmo
    endif
    if r.GetItemCount(chosenWeap) < 1
        r.AddItem(chosenWeap, 1, True)
    endif
    if RaiderWeapon != None && chosenWeap != RaiderWeapon
        r.UnequipItem(RaiderWeapon, False, True)
        int curCoachman = r.GetItemCount(RaiderWeapon)
        if curCoachman > 0
            r.RemoveItem(RaiderWeapon, curCoachman, True)
        endif
    endif
    if RaiderAmmo != None && chosenAmmo != RaiderAmmo
        int curShells = r.GetItemCount(RaiderAmmo)
        if curShells > 0
            r.RemoveItem(RaiderAmmo, curShells, True)
        endif
    endif
    r.EquipItem(chosenWeap, False, True)
    int targetSidearmAmmo = 36
    int curSidearmAmmo = r.GetItemCount(chosenAmmo)
    if curSidearmAmmo < targetSidearmAmmo
        r.AddItem(chosenAmmo, targetSidearmAmmo - curSidearmAmmo, True)
    elseif curSidearmAmmo > targetSidearmAmmo
        r.RemoveItem(chosenAmmo, curSidearmAmmo - targetSidearmAmmo, True)
    endif
    r.EvaluatePackage()
    Weapon eqSidearm = r.GetEquippedWeapon()
    if weapLabel == "pipe"
        bool eqPipeMatch = (eqSidearm == chosenWeap)
        Trace("arm raider " + idx + " sidearm=" + weapLabel + " sidearm_ammo=" + r.GetItemCount(chosenAmmo) + " weapon=" + eqSidearm + " eq_match=" + eqPipeMatch)
    else
        bool eqMatch = (eqSidearm == RaiderSidearm)
        float effSidearmDmg = ComputeEffectiveWeaponDamage(r, RaiderSidearmRecordDamage)
        Trace("arm raider " + idx + " sidearm=eon sidearm_ammo=" + r.GetItemCount(chosenAmmo) + " weapon=" + eqSidearm + " eq_match=" + eqMatch + " dmg=" + RaiderSidearmRecordDamage + " eff_dmg=" + effSidearmDmg + " playable=false standin=true")
    endif
EndFunction

float Function GetRaiderHealth(Actor r)
    if r == None
        return 0.0
    endif
    if healthAvCache == None
        healthAvCache = Game.GetFormFromFile(0x0002D4, "Starfield.esm") as ActorValue
    endif
    if healthAvCache != None
        return r.GetValue(healthAvCache)
    endif
    return 0.0
EndFunction

Function WriteOffRaider(Actor r, int idx, string reason, float elapsed)
    if r != None
        r.StopCombat()
        r.DisableNoWait(False)
    endif
    raiderCleared[idx] = True
    raiderAbsentSec[idx] = 0.0
    raiderRescueSec[idx] = 0.0
    int fid = 0
    if r != None
        fid = r.GetFormID()
    endif
    Trace("wfc01 raider cleared " + reason + " id=" + fid + " raider=" + idx + " elapsed=" + elapsed + " disabled=true")
EndFunction

Function CheckConcordRaidersWfc01(Actor player, bool advanceClock)
{WFC-01 anti-stall & R11 Part 3 E5: rescues living raiders AND non-cleared dead raiders that fell below terrain
 (z < targetZ - 8 m), drifted far (> 140 m from their Concord street/corpse spot, e.g. 2.9 km away after reload),
 or loaded into another world while the player is within 150 m of the museum door; and writes off (stops combat +
 disables) any living raider that remains absent/unloaded (> 250 m or !Is3DLoaded) for > 60 s within 100 m of the
 Concord door or stays loaded within 2 m with no damage for 60 s after a rescue.}
    if player == None || player.IsInInterior() || !IsCommonwealthExterior(player)
        return
    endif
    InitRaiderTracking()
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float pz = player.GetPositionZ()
    WorldSpace pws = player.GetWorldSpace()
    float doorX = PrestonLocalX + MergeOffsetX
    float doorY = PrestonLocalY + MergeOffsetY
    float doorZ = PrestonLocalZ
    float ddx = px - doorX
    float ddy = py - doorY
    float ddz = pz - doorZ
    float doorDist = Math.Sqrt(ddx * ddx + ddy * ddy + ddz * ddz)
    int i = 0
    while i < Raiders.Length
        Actor r = Raiders[i]
        if r == None || raiderCleared[i] || r.IsDisabled()
            raiderAbsentSec[i] = 0.0
            raiderRescueSec[i] = 0.0
        else
            bool deadRaider = r.IsDead()
            float tx = raiderTargetX[i]
            float ty = raiderTargetY[i]
            float tz = raiderTargetZ[i]
            float cx = tx
            float cy = ty
            float cz = tz
            if deadRaider
                raiderAbsentSec[i] = 0.0
                raiderRescueSec[i] = 0.0
                cx = raiderCorpseX[i]
                cy = raiderCorpseY[i]
                cz = raiderCorpseZ[i]
            endif
            if doorDist < Wfc01CheckRadius
                float rz = r.GetPositionZ()
                float drift = SpotOff(r, cx, cy, cz)
                WorldSpace rws = r.GetWorldSpace()
                bool wrongWorld = r.IsInInterior() || rws == None || rws != pws
                if !wrongWorld && rz >= tz - Wfc01SubterraneanDrop && SpotOff(r, tx, ty, tz) <= Wfc01MaxDrift
                    raiderCorpseX[i] = r.GetPositionX()
                    raiderCorpseY[i] = r.GetPositionY()
                    raiderCorpseZ[i] = rz
                elseif (wrongWorld || rz < cz - Wfc01SubterraneanDrop || drift > Wfc01MaxDrift) && IsPlayerStableAt(player, px, py, pz)
                    r.MoveTo(player, cx - px, cy - py, cz - pz, True, False)
                    r.SetPosition(cx, cy, cz)
                    if deadRaider
                        Trace("wfc01 rescue_dead raider=" + i + " z=" + rz + " target_z=" + cz + " drift=" + drift)
                    else
                        r.EvaluatePackage()
                        raiderRescued[i] = True
                        raiderRescueSec[i] = 0.0
                        raiderRescueX[i] = r.GetPositionX()
                        raiderRescueY[i] = r.GetPositionY()
                        raiderRescueZ[i] = r.GetPositionZ()
                        raiderRescueHp[i] = GetRaiderHealth(r)
                        Trace("wfc01 rescue raider=" + i + " z=" + rz + " target_z=" + cz + " drift=" + drift)
                    endif
                endif
            endif
            if !deadRaider && advanceClock
                float distToPlayer = player.GetDistance(r)
                if doorDist <= Wfc01DoorRadius && (!r.Is3DLoaded() || distToPlayer > Wfc01AbsentDistance)
                    raiderAbsentSec[i] = raiderAbsentSec[i] + 1.0
                    if raiderAbsentSec[i] > Wfc01AbsentLimit
                        WriteOffRaider(r, i, "absent", raiderAbsentSec[i])
                    endif
                else
                    raiderAbsentSec[i] = 0.0
                endif
                if !raiderCleared[i] && raiderRescued[i]
                    if r.Is3DLoaded()
                        float moved = SpotOff(r, raiderRescueX[i], raiderRescueY[i], raiderRescueZ[i])
                        float hp = GetRaiderHealth(r)
                        bool tookDamage = raiderRescueHp[i] > 0.0 && hp < raiderRescueHp[i] - 0.01
                        if moved < Wfc01StuckMoveRadius && !tookDamage
                            raiderRescueSec[i] = raiderRescueSec[i] + 1.0
                            if hp > raiderRescueHp[i]
                                raiderRescueHp[i] = hp
                            endif
                            if raiderRescueSec[i] >= Wfc01StuckLimit
                                WriteOffRaider(r, i, "stuck", raiderRescueSec[i])
                            endif
                        else
                            raiderRescueSec[i] = 0.0
                            raiderRescueX[i] = r.GetPositionX()
                            raiderRescueY[i] = r.GetPositionY()
                            raiderRescueZ[i] = r.GetPositionZ()
                            raiderRescueHp[i] = hp
                        endif
                    else
                        raiderRescueSec[i] = 0.0
                    endif
                endif
            endif
        endif
        i += 1
    endwhile
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID == 2
        KeepCodsworth()
        return
    elseif aiTimerID == 3
        CheckPrestonSceneOpen()
        return
    elseif aiTimerID == 4
        EnsureSanctuaryStarted()
        return
    elseif aiTimerID == 5
        CheckS6RoomSceneOpen(False)
        return
    elseif aiTimerID == 6
        CheckS6RoomSceneOpen(True)
        return
    elseif aiTimerID != 1
        return
    endif
    if KeeperOnly
        return
    endif
    if EffectiveStage() < 200
        if !IsRunning()
            Start()
        endif
        if applied > 0 && GetStage() < applied
            SetStage(applied)
        endif
    endif
    Actor player = Game.GetPlayer()
    InitRaiderTracking()
    KeepCodsworthStart()
    ReleaseInFight("mission")                            ; every check, whatever the budget or where the player is
    if relocateFails < 10
        Relocate(player)
    endif
    int rawStage = GetStage()
    int stage = EffectiveStage()
    if !min00Given && stage < 10 && IsCommonwealthExterior(player)
        float gdx = player.GetPositionX() - (PrestonLocalX + MergeOffsetX)
        float gdy = player.GetPositionY() - (PrestonLocalY + MergeOffsetY)
        float gdz = player.GetPositionZ() - PrestonLocalZ
        if gdx * gdx + gdy * gdy + gdz * gdz <= GiveConcordRadius * GiveConcordRadius
            min00Given = True
            Trace("min00 given by=concord")
            ClearCodsworthObjectiveForConcord()
            AdvanceTo(10, "Trigger")
            stage = 10
        endif
    endif
    if (GetStageDone(35) || rawStage == 35) && applied < 35
        if talkActivated && !prestonUsedFallback
            Apply(35, "info")
        else
            Apply(35, "other")
        endif
        stage = EffectiveStage()
    endif
    if rawStage >= 40 && applied < 40
        Apply(40, "other")
        stage = EffectiveStage()
    elseif rawStage > applied && rawStage < 35
        Apply(rawStage, "other")
        stage = EffectiveStage()
    endif
    if stage == 10 && min00Given && !IsObjectiveDisplayed(10) && (!MuteDuplicateObjectiveToasts || !obj10DisplayedOnce)
        EnsurePrestonAlias()
        if FO4SF_QuestToastUtil.ShowObjectiveOnce(Self, 10, MuteDuplicateObjectiveToasts, obj10DisplayedOnce)
            obj10DisplayedOnce = True
        endif
    elseif stage == 20 && !IsObjectiveDisplayed(85) && (!MuteDuplicateObjectiveToasts || !obj85DisplayedOnce)
        if FO4SF_QuestToastUtil.ShowObjectiveOnce(Self, 85, MuteDuplicateObjectiveToasts, obj85DisplayedOnce)
            obj85DisplayedOnce = True
        endif
    elseif stage == 30 && !IsObjectiveDisplayed(86) && (!MuteDuplicateObjectiveToasts || !obj86DisplayedOnce)
        EnsurePrestonAlias()
        if FO4SF_QuestToastUtil.ShowObjectiveOnce(Self, 86, MuteDuplicateObjectiveToasts, obj86DisplayedOnce)
            obj86DisplayedOnce = True
        endif
    endif
    if EnableS4Balcony && !s4BalconySetup && stage >= 10 && stage < 30 && IsCommonwealthExterior(player)
        SetupS4BalconyEncounter(player)
    endif
    if s4BalconyActive && !s9PatrolRelease
        MaintainS4PrestonBalcony(player, "mission")
    endif
    if EnableS6ToS9Full && s9PatrolStarted && !s9GroupArrived
        if prestonTalkReloaded
            ResumeS9PatrolAfterLoad(player)
        endif
        CheckS9SanctuaryArrival(player, 1.0)
    endif
    float dp = player.GetDistance(Preston)
    if stage < 20 && dp < FindRadius
        FoundPreston("near d=" + dp)
    endif
    if stage == 20
        CheckConcordRaidersWfc01(player, True)
    else
        CheckConcordRaidersWfc01(player, False)
    endif
    SyncPrestonFightHold(stage)
    bool everyone = prestonFound || stage >= 20          ; once the fight is on, no raider stands by
    int dead = 0
    bool fighting = false
    float nearest = -1.0
    float nowCombatRt = Utility.GetCurrentRealTime()
    int i = 0
    while i < Raiders.Length
        Actor r = Raiders[i]
        if r == None || r.IsDead() || raiderCleared[i]
            dead += 1
        else
            float d = player.GetDistance(r)
            if nearest < 0.0 || d < nearest
                nearest = d
            endif
            if !raiderArmed[i] && stage < 30 && (everyone || d < EngageRadius) && r.Is3DLoaded()
                ArmRaiderForCombat(r, i)
                EquipBalancedRaiderSidearm(r, i)
            endif
            if (r.GetCombatState() == 1 && r.GetCombatTarget() == player && raiderEngaged[i]) || (raiderEngaged[i] && nowCombatRt >= raiderStartCombatAt[i] && (nowCombatRt - raiderStartCombatAt[i]) < 4.0)
                fighting = true
            elseif stage < 30 && (everyone || d < EngageRadius) && r.Is3DLoaded()
                ; FO4's forced fight: every living loaded raider is put into combat with the player, even if
                ; faction-alerted (GetCombatState == 2) or targeting someone else, rate-limited to once per 4 s (C3 + Task 0d).
                r.StartCombat(player)
                raiderEngaged[i] = True
                raiderStartCombatAt[i] = nowCombatRt
                fighting = true
                Trace("startcombat raider " + i + " d=" + d)
            elseif r.GetCombatState() != 0
                fighting = true
            endif
        endif
        i += 1
    endwhile
    if EnableS6ToS9Full
        SyncS5ExteriorDoors(player)
        if IsPlayerInMuseum(player)
            UpdateS5MuseumEncounter(player)
        endif
    endif
    bool readyTalk = TalkCompleteReady(stage, dp)
    int target = NextStage(stage, dead, Raiders.Length, fighting, readyTalk, prestonFound)
    if EnableS4Balcony && EnableS6ToS9Full
        ; S4 -> S5 transition: clearing Concord street raiders keeps Preston on 3F and moves player into Museum
        ; (objective 60 "Enter the Museum") instead of jumping prematurely to street stage 30 talk.
        if dead >= Raiders.Length && !s4StreetCleared && stage < 35
            s4StreetCleared = True
            SetObjectiveCompleted(85)
            if FO4SF_QuestToastUtil.ShowObjectiveOnce(Self, 60, MuteDuplicateObjectiveToasts, obj60DisplayedOnce)
                obj60DisplayedOnce = True
            endif
            Trace("s4 street_cleared dead=" + dead + "/" + Raiders.Length + " next=enter_museum")
        endif
        if !s5MuseumCleared && target >= 30
            target = 20
        endif
    endif
    ; every stage on the way is set in order, so each one's objectives and log line happen
    while stage < target && stage < 40
        string nextBy = "Trigger"
        if stage < 10
            if !min00Given
                min00Given = True
                Trace("min00 given by=concord")
                ClearCodsworthObjectiveForConcord()
            endif
            stage = 10
        elseif stage < 20
            stage = 20
        elseif stage < 30
            stage = 30
        else
            stage = 40
            if prestonUsedFallback
                nextBy = "fallback"
            elseif prestonTalkLogged
                nextBy = "info"
            else
                nextBy = "other"
            endif
        endif
        AdvanceTo(stage, nextBy)
    endwhile
    if stage >= 30
        SyncPrestonFightHold(stage)
    endif
    ticks += 1
    if ticks % 5 == 0
        Trace("status stage=" + stage + " dead=" + dead + "/" + Raiders.Length + " nearest_raider=" + nearest + " preston=" + dp + " preston_off=" + prestonOff + " held=" + prestonHeld + " pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ())
    endif
    if Preston.GetCombatTarget() == player               ; he never fights the player (in game 18 Oct: "treats me like an enemy")
        Preston.StopCombat()
        Trace("preston was targeting the player: stopcombat")
    endif
    Scene endScn = ResolvePrestonScene()
    if !EnableS6ToS9Full && EffectiveStage() == 40 && (endScn == None || !endScn.IsPlaying()) ; in game 18 Oct the status stayed at 40 after the reward: set 200
        AdvanceTo(200, "Trigger")
        CompleteQuest()
        Trace("complete stage=" + EffectiveStage())
    endif
    if EffectiveStage() < 200                            ; stage 200 cancels the timer (Apply)
        StartTimer(1.0, 1)
    endif
EndEvent

int Function NextStage(int stage, int dead, int total, bool fighting, bool atPreston, bool found)
{The stage the encounter has reached, whoever started the fight (scripts/mission/make_mission.py next_stage is the
 same rule, tested there): the fight counts as started when a raider fights or is dead, or when the player has found
 Preston (FoundPreston); all raiders dead or cleared is stage 30; completing talk at Preston after that is stage 40.}
    int s = stage
    if s < 20 && (fighting || dead > 0 || found)
        s = 20
    endif
    if s < 30 && total > 0 && dead == total
        s = 30
    endif
    if s == 30 && atPreston
        s = 40
    endif
    return s
EndFunction

bool Function IsStoryQuestComplete(int formId)
{R5: Strict IsCompleted() check only. Never treat intermediate stage >= 100 (e.g. MQ105@100 following trail to
 Fort Hagen, MQ106@100 Kellogg, MQ203@100 lounger) as completed.}
    Quest q = Game.GetFormFromFile(formId, "FO4SFMission.esm") as Quest
    return q != None && q.IsCompleted()
EndFunction

Function CheckPostConcordSanctuaryHandoff()
    if IsWarfareMode()
        return
    endif
    if !IsRunning() && KeeperOnly
        Start()
    endif
    bool min00Done = applied >= 200 || IsCompleted()
    if KeeperOnly
        Quest min00 = Game.GetFormFromFile(0x000800, "FO4SFMission.esm") as Quest
        min00Done = min00 != None && min00.IsCompleted()
    endif
    if min00Done
        Quest sanctuaryQuest = Game.GetFormFromFile(0x000817, "FO4SFMission.esm") as Quest
        if sanctuaryQuest != None && !sanctuaryQuest.IsRunning() && !sanctuaryQuest.IsCompleted()
            bool ok = sanctuaryQuest.StartNoWait()
            Trace("sanctuary01 postload_start ok=" + ok)
        endif
    endif
EndFunction

Function Relocate(Actor player)
{Moves the raiders (Codsworth: KeepCodsworth) from their unmerged local position to the same spot in the merged world the
 player walks in, and puts Preston at his fixed spot (PlacePreston). Never from an interior.}
    if player.IsInInterior()
        return
    endif
    if !IsCommonwealthExterior(player)
        return
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float pz = player.GetPositionZ()
    if PlacePreston(player, "mission")
        relocateFails += 1
    endif
    int i = 0
    while i < Raiders.Length
        if !IsPlayerStableAt(player, px, py, pz)
            return
        endif
        if MoveOver(Raiders[i], player, px, py, pz, "raider " + i)
            relocateFails += 1
        endif
        i += 1
    endwhile
EndFunction

Function KeepCodsworth()
{Codsworth has his own check every CodsworthCheck seconds with its own budget of 10 failed moves. It keeps running after
 stage 200, which ends the mission's timer.}
    CheckPostConcordSanctuaryHandoff()
    Actor player = Game.GetPlayer()
    if Codsworth != None
        ReleaseCodsworthInFight("keeper")
    endif
    if Codsworth != None && codsworthFails < 10
        if PlaceCodsworth(player)
            codsworthFails += 1
            if codsworthFails >= 10
                codsworthState = "gave up"
                Trace("keeper gave up codsworth fails=" + codsworthFails)
                if IsTestModeEnabled()
                    Debug.Notification("FO4SF keeper: Codsworth not placed after 10 tries; stopped until the next load")
                endif
            endif
        endif
    endif
    if KeeperOnly
        KeepPreston(player)
        if Codsworth != None && keeperChecks % KeeperStatusEvery == 0
            TraceCodsworth("keeper status")
        endif
        CheckA4ProximityStarts(player)
        CheckA7ProximityStarts(player)
        CheckA7cdProximityStarts(player)
    endif
    if (Codsworth != None && (codsworthFails < 10 || codsworthHolds > 0)) || (KeeperOnly && (prestonFails < 10 || prestonHolds > 0))
        StartTimer(CodsworthCheck, 2)
    elseif KeeperOnly
        ; R11 A2.4: Keep KeeperOnly Timer 2 alive for CheckA4/A7/A7cdProximityStarts even if both
        ; Codsworth and Preston placement budgets reach 10 with zero holds.
        StartTimer(CodsworthCheck, 2)
    endif
EndFunction

Function CheckA4ProximityStarts(Actor player)
{R1/R5: Console-free proximity discovery for JOTC-02 Diamond City gate (MQ103) & Tenpines Bluff (MinRecruit00) on
 KeeperOnly Timer 2, strictly gated behind BOTH FO4SF_Min00 (0x000800) AND FO4SF_Sanctuary01 (0x000817) completion so
 First Settlement stays the sole active tracked opening mission (deliberate one-tracked-mission rule aligned with W2).}
    if !IsCommonwealthExterior(player) || IsWarfareMode()
        return
    endif
    if !IsStoryQuestComplete(0x000800) || !IsStoryQuestComplete(0x000817)
        return
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float r2 = 150.0 * 150.0
    float dcx = px - (-1416.36)
    float dcy = py - (-3129.39)
    if !mq103ProxAttempted && dcx * dcx + dcy * dcy <= r2
        Quest mq103Quest = Game.GetFormFromFile(0x000A50, "FO4SFMission.esm") as Quest
        if mq103Quest != None && !mq103Quest.IsRunning() && !mq103Quest.IsCompleted()
            mq103ProxAttempted = True
            mq103Quest.StartNoWait()
            Trace("mq103 started by=proximity")
        endif
    endif
    float tpx = px - (-1517.0)
    float tpy = py - (-1423.63)
    if !minRecruitProxAttempted && tpx * tpx + tpy * tpy <= r2
        Quest stepQuest = Game.GetFormFromFile(0x000A20, "FO4SFMission.esm") as Quest
        if stepQuest != None && !stepQuest.IsRunning() && !stepQuest.IsCompleted()
            minRecruitProxAttempted = True
            stepQuest.StartNoWait()
            Trace("minrecruit00 started by=proximity")
        endif
    endif
EndFunction

Function CheckA7ProximityStarts(Actor player)
{R5: Console-free proximity discovery for Park Street / Vault 114 (MQ104) & Fort Hagen (MQ105) on KeeperOnly Timer 2,
 strictly gated behind prior quest completion (MQ103 -> MQ104 -> MQ105) so no post-opening quest fires early.}
    if !IsCommonwealthExterior(player) || IsWarfareMode()
        return
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float r2 = 150.0 * 150.0
    float psx = px - (-987.46)
    float psy = py - (-2927.73)
    float v14x = px - (-1085.43)
    float v14y = py - (-2958.22)
    if !mq104ProxAttempted && IsStoryQuestComplete(0x000A50) && ((psx * psx + psy * psy <= r2) || (v14x * v14x + v14y * v14y <= r2))
        Quest mq104Quest = Game.GetFormFromFile(0x000A80, "FO4SFMission.esm") as Quest
        if mq104Quest != None && !mq104Quest.IsRunning() && !mq104Quest.IsCompleted()
            mq104ProxAttempted = True
            mq104Quest.StartNoWait()
            Trace("mq104 started by=proximity")
        endif
    endif
    float fhx = px - (-2456.84)
    float fhy = py - (-2781.07)
    if !mq105ProxAttempted && IsStoryQuestComplete(0x000A80) && fhx * fhx + fhy * fhy <= r2
        Quest mq105Quest = Game.GetFormFromFile(0x000AB0, "FO4SFMission.esm") as Quest
        if mq105Quest != None && !mq105Quest.IsRunning() && !mq105Quest.IsCompleted()
            mq105ProxAttempted = True
            mq105Quest.StartNoWait()
            Trace("mq105 started by=proximity")
        endif
    endif
EndFunction

Function CheckA7cdProximityStarts(Actor player)
{R5: Console-free proximity discovery for Act II missions (MQ106 Fort Hagen, MQ203 Goodneighbor, MQ204 Glowing Sea,
 MQ206 Greenetech/Railroad) on KeeperOnly Timer 2, each strictly gated behind the prior quest's completion so Fort Hagen
 never starts MQ105 and MQ106 together.}
    if IsWarfareMode() || !IsCommonwealthExterior(player)
        return
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float r2 = 160.0 * 160.0
    float fhx = px - (-2456.84)
    float fhy = py - (-2781.07)
    if !mq106ProxAttempted && IsStoryQuestComplete(0x000AB0) && fhx * fhx + fhy * fhy <= r2
        Quest mq106Quest = Game.GetFormFromFile(0x000AD0, "FO4SFMission.esm") as Quest
        if mq106Quest != None && !mq106Quest.IsRunning() && !mq106Quest.IsCompleted()
            mq106ProxAttempted = True
            mq106Quest.StartNoWait()
            Trace("mq106 started by=proximity")
        endif
    endif
    float gnx = px - (-902.48)
    float gny = py - (-2870.07)
    if !mq203ProxAttempted && IsStoryQuestComplete(0x000AD0) && gnx * gnx + gny * gny <= r2
        Quest mq203Quest = Game.GetFormFromFile(0x000AF0, "FO4SFMission.esm") as Quest
        if mq203Quest != None && !mq203Quest.IsRunning() && !mq203Quest.IsCompleted()
            mq203ProxAttempted = True
            mq203Quest.StartNoWait()
            Trace("mq203 started by=proximity")
        endif
    endif
    float crx = px - (-2624.44)
    float cry = py - (-4357.85)
    float rcx = px - (-2862.82)
    float rcy = py - (-4653.27)
    if !mq204ProxAttempted && IsStoryQuestComplete(0x000AF0) && ((crx * crx + cry * cry <= r2) || (rcx * rcx + rcy * rcy <= r2))
        Quest mq204Quest = Game.GetFormFromFile(0x000B10, "FO4SFMission.esm") as Quest
        if mq204Quest != None && !mq204Quest.IsRunning() && !mq204Quest.IsCompleted()
            mq204ProxAttempted = True
            mq204Quest.StartNoWait()
            Trace("mq204 started by=proximity")
        endif
    endif
    float gtx = px - (-1238.10)
    float gty = py - (-2687.39)
    float rrx = px - (-734.83)
    float rry = py - (-2696.65)
    if !mq206ProxAttempted && IsStoryQuestComplete(0x000B10) && ((gtx * gtx + gty * gty <= r2) || (rrx * rrx + rry * rry <= r2))
        Quest mq206Quest = Game.GetFormFromFile(0x000B30, "FO4SFMission.esm") as Quest
        if mq206Quest != None && !mq206Quest.IsRunning() && !mq206Quest.IsCompleted()
            mq206ProxAttempted = True
            mq206Quest.StartNoWait()
            Trace("mq206 started by=proximity")
        endif
    endif
EndFunction

Function KeepPreston(Actor player)
{The keeper keeps Preston at his merged spot after the mission too, and preserves dead Concord raiders after reload (E5).}
    ReleaseInFight("keeper")
    if prestonFails < 10
        if PlacePreston(player, "keeper")
            prestonFails += 1
            if prestonFails >= 10
                prestonState = "gave up"
                Trace("keeper gave up preston fails=" + prestonFails)
                if IsTestModeEnabled()
                    Debug.Notification("FO4SF keeper: Preston not placed after 10 tries; stopped until the next load")
                endif
            endif
        endif
    endif
    if s4BalconyActive && !s9PatrolRelease
        MaintainS4PrestonBalcony(player, "keeper")
    endif
    keeperChecks += 1
    if keeperChecks % KeeperStatusEvery == 0
        TracePreston("keeper status")
    endif
EndFunction

Function BeginFollow()
{FO4SF_COMPreston.FollowTest (test-only, gated behind FO4SF_TestModeEnabled != 0) arms this instance. While prestonFollow
 is set, PlacePreston neither moves him back to the museum door nor restrains him.}
    GlobalVariable testMode = Game.GetFormFromFile(0x000860, "FO4SFCoreValues.esm") as GlobalVariable
    if testMode == None || testMode.GetValue() == 0.0
        Trace("follow preston test-only refused: test mode off")
        return
    endif
    prestonFollow = True
    prestonHeld = False
    prestonState = HeldState("follow", False)
    string who = "mission"
    if KeeperOnly
        who = "keeper"
    endif
    Trace("follow preston armed by=" + who)
EndFunction

bool Function PlacePreston(Actor player, string who)
{Preston's fixed spot (FAL-128): PrestonLocalX/Y/Z + the merge offset, by PlaceAt. FAL-866: once BeginFollow has armed
 this instance, none of that runs.}
    if prestonFollow
        prestonState = HeldState("follow", False)
        return False
    endif
    float tx = PrestonLocalX + MergeOffsetX
    float ty = PrestonLocalY + MergeOffsetY
    float tz = PrestonLocalZ
    bool fighting = Preston.GetCombatState() != 0         ; released already (ReleaseInFight)
    string s = PlaceAt(Preston, "Preston", tx, ty, tz, player, who, "at the museum door", fighting)
    prestonOff = SpotOff(Preston, tx, ty, tz)
    if s == "placed" || s == "move failed"
        prestonMoves += 1
    endif
    if HoldDue(s, fighting, prestonHeld, prestonOff)
        HoldPreston(who)
    endif
    prestonState = HeldState(s, prestonHeld)
    if s == "placed" || s == "at spot"
        prestonPlaced = True
    endif
    return s == "move failed"
EndFunction

bool Function PlaceCodsworth(Actor player)
{Codsworth's fixed spot (FAL-163): CodsworthLocalX/Y/Z + the merge offset, by PlaceAt, Preston's rule; only the keeper
 places him.}
    float tx = CodsworthLocalX + MergeOffsetX
    float ty = CodsworthLocalY + MergeOffsetY
    float tz = CodsworthLocalZ
    bool fighting = Codsworth.GetCombatState() != 0       ; released already (ReleaseCodsworthInFight)
    string s = PlaceAt(Codsworth, "Codsworth", tx, ty, tz, player, "keeper", "in Sanctuary", fighting)
    codsworthOff = SpotOff(Codsworth, tx, ty, tz)
    if s == "placed" || s == "move failed"
        codsworthMoves += 1
    endif
    if HoldDue(s, fighting, codsworthHeld, codsworthOff)
        HoldCodsworth("keeper")
    endif
    codsworthState = HeldState(s, codsworthHeld)
    return s == "move failed"
EndFunction

string Function PlaceAt(ObjectReference a, string name, float tx, float ty, float tz, Actor player, string who, string where, bool fighting, bool ignoreRadius = False)
{The fixed-spot rule of Preston (FAL-128) and Codsworth (FAL-163), also supporting R11 merged-world marker placement.}
    float dp = player.GetDistance(a)                      ; float max: another world
    float off = SpotOff(a, tx, ty, tz)
    if off <= HoldRadius && dp < RelocateGap
        return "at spot"
    endif
    if player.IsInInterior()
        return "off, player inside"
    endif
    if !IsCommonwealthExterior(player)
        return "off, player inside"
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float pz = player.GetPositionZ()
    if !ignoreRadius && (px - tx) * (px - tx) + (py - ty) * (py - ty) > PlaceRadius * PlaceRadius
        return "off, player away"
    endif
    if dp < RelocateGap && fighting
        return "off, fighting"                            ; the fight moves it; it is put back once the fight is over
    endif
    if !IsPlayerStableAt(player, px, py, pz)
        return "off, player inside"
    endif
    Trace("world " + name + " player=" + player.GetWorldSpace() + " actor=" + a.GetWorldSpace() + " cell=" + a.GetParentCell())
    a.MoveTo(player, tx - px, ty - py, tz - pz, True, False)
    float d = player.GetDistance(a)
    float after = SpotOff(a, tx, ty, tz)
    bool failed = after > HoldRadius || d >= RelocateGap || a.IsInInterior() || a.GetWorldSpace() == None
    Trace("world " + name + " after=" + a.GetWorldSpace() + " cell=" + a.GetParentCell())
    Trace("moved " + name + " to " + a.GetPositionX() + " " + a.GetPositionY() + " " + a.GetPositionZ() + " target " + tx + " " + ty + " " + tz + " before=" + dp + " off=" + off + " d=" + d + " failed=" + failed + " by=" + who)
    if IsTestModeEnabled()
        Debug.Notification("FO4SF: " + name + " put back " + where + " (" + who + ", was " + (off as int) + " m off, failed=" + failed + ")")
    endif
    if failed
        return "move failed"
    endif
    return "placed"
EndFunction

bool Function HoldDue(string s, bool fighting, bool held, float off)
{Whether PlaceAt's result s calls for a hold (FAL-170, FAL-163).}
    if fighting
        return False
    endif
    return s == "placed" || (s == "at spot" && !held && off <= HeldRadius)
EndFunction

Function HoldPreston(string who)
{Holds Preston where he stands.}
    HoldActor(Preston, "preston", who, prestonOff)
    prestonHeld = True
    prestonHolds += 1
EndFunction

Function HoldCodsworth(string who)
{Holds Codsworth where he stands, as Preston (HoldPreston).}
    HoldActor(Codsworth, "codsworth", who, codsworthOff)
    codsworthHeld = True
    codsworthHolds += 1
EndFunction

Function EnsureActorTalkable(Actor a)
    if a != None
        a.AllowPCDialogue(True)
        a.BlockActivation(False, False)
        if a == Preston && !KeeperOnly
            a.IgnoreFriendlyHits(True)
        endif
    endif
EndFunction

float Function SnapActorToFloor(Actor a, string label)
{Snap actor onto nearby floor/navmesh (guarding against roof warps > 1.0 m) and trace ground_dz.}
    if a == None
        return 0.0
    endif
    float preX = a.GetPositionX()
    float preY = a.GetPositionY()
    float preZ = a.GetPositionZ()
    a.MoveToNearestNavmeshLocation()
    float postZ = a.GetPositionZ()
    float dz = postZ - preZ
    if dz > 1.0 || dz < -1.0
        a.SetPosition(preX, preY, preZ)
        dz = 0.0
    endif
    Trace("hold " + label + " ground_dz=" + dz)
    return dz
EndFunction

Function FaceActorToward(Actor actorRef, ObjectReference targetRef)
{Turn actorRef yaw toward targetRef on Z-up XY plane when a conversation starts.}
    if actorRef == None || targetRef == None
        return
    endif
    float dx = targetRef.GetPositionX() - actorRef.GetPositionX()
    float dy = targetRef.GetPositionY() - actorRef.GetPositionY()
    if dx * dx + dy * dy < 0.0001
        return
    endif
    float deg = 0.0
    if dy > 0.0001
        deg = Math.atan(dx / dy)
    elseif dy < -0.0001
        deg = Math.atan(dx / dy) + 180.0
    elseif dx >= 0.0
        deg = 90.0
    else
        deg = 270.0
    endif
    if deg < 0.0
        deg += 360.0
    elseif deg >= 360.0
        deg -= 360.0
    endif
    actorRef.SetAngle(0.0, 0.0, deg)
    Trace("preston face player angle_z=" + deg)
EndFunction

Function HoldActor(Actor a, string name, string who, float off)
{Snap onto navmesh floor, SetRestrained(True), keep player talk activation unblocked, and log hold + ground_dz.}
    SnapActorToFloor(a, name)
    bool ok = a.SetRestrained(True)
    EnsureActorTalkable(a)
    Trace("hold " + name + " by=" + who + " off=" + off + " ok=" + ok)
EndFunction

bool Function ReleaseInFight(string who)
{Lets Preston go while he fights, whatever this instance's prestonHeld says.}
    if ReleaseActor(Preston, "preston", who, prestonFighting)
        prestonHeld = False
        prestonFighting = True
        return True
    endif
    prestonFighting = False
    return False
EndFunction

bool Function ReleaseCodsworthInFight(string who)
{Codsworth's release in a fight, as Preston's (ReleaseInFight), from the keeper on every check.}
    if ReleaseActor(Codsworth, "codsworth", who, codsworthFighting)
        codsworthHeld = False
        codsworthFighting = True
        return True
    endif
    codsworthFighting = False
    return False
EndFunction

bool Function ReleaseActor(Actor a, string name, string who, bool logged)
{SetRestrained(False) while the actor fights, whatever any flag says; "release <name> by=<who> reason=fighting" once
 per fight (logged: already written). Returns whether it fights.}
    if a.GetCombatState() != 0
        a.SetRestrained(False)
        if !logged
            Trace("release " + name + " by=" + who + " reason=fighting")
        endif
        return True
    endif
    return False
EndFunction

string Function HeldState(string s, bool held)
{A state, with ", held" while this instance holds the actor.}
    if held
        return s + ", held"
    endif
    return s
EndFunction

float Function SpotOff(ObjectReference a, float tx, float ty, float tz)
{A reference's distance (m) from a point, by position only.}
    float ex = a.GetPositionX() - tx
    float ey = a.GetPositionY() - ty
    float ez = a.GetPositionZ() - tz
    return Math.Sqrt(ex * ex + ey * ey + ez * ez)
EndFunction

Function TracePreston(string what)
    prestonOff = SpotOff(Preston, PrestonLocalX + MergeOffsetX, PrestonLocalY + MergeOffsetY, PrestonLocalZ)
    TraceSpot(what, Preston, "preston", prestonOff, prestonState, prestonMoves, prestonHeld, prestonHolds, prestonFails)
EndFunction

Function TraceCodsworth(string what)
    codsworthOff = SpotOff(Codsworth, CodsworthLocalX + MergeOffsetX, CodsworthLocalY + MergeOffsetY, CodsworthLocalZ)
    TraceSpot(what, Codsworth, "codsworth", codsworthOff, codsworthState, codsworthMoves, codsworthHeld, codsworthHolds, codsworthFails)
EndFunction

Function TraceSpot(string what, Actor a, string name, float off, string spotState, int moves, bool held, int holds, int fails)
{One keeper line of where an actor is (State is a Papyrus keyword, so the parameter is spotState).}
    Actor player = Game.GetPlayer()
    Trace(what + " " + name + " d=" + player.GetDistance(a) + " off=" + off + " state=" + spotState + " moves=" + moves + " held=" + held + " holds=" + holds + " at " + a.GetPositionX() + " " + a.GetPositionY() + " " + a.GetPositionZ() + " disabled=" + a.IsDisabled() + " dead=" + a.IsDead() + " fails=" + fails + " player=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " interior=" + player.IsInInterior())
EndFunction

bool Function MoveOver(Actor a, Actor player, float px, float py, float pz, string what)
{C3: Moves one raider into the player's loaded Commonwealth worldspace when the player is within PlaceRadius (300 m) of
 its merged Concord spot and it is still farther than RelocateGap. Supports both merged-authored raider ACHRs (C3) and
 legacy unmerged saves without ever offsetting twice or dropping raiders into unloaded cells 500 m away.}
    if a == None
        return False
    endif
    float before = player.GetDistance(a)                  ; float max: another world; finite: this world (the world proof)
    if before < RelocateGap
        return False                                      ; already where the player is
    endif
    float doorX = PrestonLocalX + MergeOffsetX
    float doorY = PrestonLocalY + MergeOffsetY
    float rx = a.GetPositionX()
    float ry = a.GetPositionY()
    float z = a.GetPositionZ()
    float x = rx
    float y = ry
    float mx = rx - doorX
    float my = ry - doorY
    if mx * mx + my * my > RelocateRadius * RelocateRadius
        x = rx + MergeOffsetX
        y = ry + MergeOffsetY
        float hx = x - (PrestonLocalX + MergeOffsetX)
        float hy = y - (PrestonLocalY + MergeOffsetY)
        if hx * hx + hy * hy > RelocateRadius * RelocateRadius
            return False                                  ; moved already or outside Concord: never offset twice
        endif
    endif
    float dx = px - x
    float dy = py - y
    if dx * dx + dy * dy > PlaceRadius * PlaceRadius
        return False                                      ; wait until Concord cells are loaded (<= 300 m)
    endif
    WorldSpace wa = a.GetWorldSpace()                     ; evidence for Codex's world-identity point (#353): which
    WorldSpace wp = player.GetWorldSpace()                ; world each side is in before a move (only moves: Codex 4331303552)
    if wp == None || !IsPlayerStableAt(player, px, py, pz)
        return False
    endif
    Trace("world " + what + " player=" + wp + " actor=" + wa + " cell=" + a.GetParentCell())
    a.MoveTo(player, x - px, y - py, z - pz, True, False)
    float d = player.GetDistance(a)
    WorldSpace afterWs = a.GetWorldSpace()
    bool failed = d >= RelocateGap || a.IsInInterior() || afterWs == None || SpotOff(a, x, y, z) > HoldRadius
    Trace("world " + what + " after=" + afterWs + " cell=" + a.GetParentCell())
    Trace("moved " + what + " to " + a.GetPositionX() + " " + a.GetPositionY() + " " + a.GetPositionZ() + " target " + x + " " + y + " " + z + " before=" + before + " d=" + d + " failed=" + failed)
    if !failed
        SnapActorToFloor(a, what)
        a.EvaluatePackage()
    endif
    return failed
EndFunction

Function Trace(string msg)
    ; User log is opened once at start and once on OnPlayerLoadGame (2f)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction

Form Function LookupOptionalForm(int formId, string pluginName)
{R11 Step 3q: Nullable lookup for optional A4 weapons/items not yet built; returns None with zero crash when formId <= 0.}
    if formId <= 0 || pluginName == ""
        return None
    endif
    return Game.GetFormFromFile(formId, pluginName)
EndFunction

Function ApplyPrestonMode(bool balconyHold, bool patrolFree)
{R11 Step 3q: Coordinates Preston hold/release across both FO4SF_Min00 (0x0800) and FO4SF_CodsworthKeeper (0x0814).
 While balconyHold is True (S4), PlacePreston yields to MaintainS4PrestonBalcony (Z=98.51). Once patrolFree is True
 (S6/S9 patrol & Sanctuary arrival), prestonFollow stays True so neither 0x0800 nor 0x0814 ever re-restrains or yanks him.}
    s4BalconyActive = balconyHold
    s9PatrolRelease = patrolFree
    if balconyHold || patrolFree
        prestonFollow = True
        prestonHeld = False
        prestonState = HeldState("follow", False)
    endif
    if patrolFree && Preston != None
        Preston.SetRestrained(False)
    endif
EndFunction

Function SyncKeeperPrestonMode(bool balconyHold, bool patrolFree)
{R11 Step 3q: Applies Preston hold/patrol mode on Self (0x0800) AND FO4SF_CodsworthKeeper (0x0814) together.}
    ApplyPrestonMode(balconyHold, patrolFree)
    FO4SF_Min00Quest keeperQ = Game.GetFormFromFile(0x000814, "FO4SFMission.esm") as FO4SF_Min00Quest
    if keeperQ != None && keeperQ != Self
        keeperQ.ApplyPrestonMode(balconyHold, patrolFree)
    endif
EndFunction

Function MaintainS4PrestonBalcony(Actor player, string who)
{R11 Step 3q: Holds Preston at the Museum balcony (-2010.51, -1697.71, 98.51 m) during S4 on both 0x0800 and 0x0814.}
    if !s4BalconyActive || s9PatrolRelease || Preston == None || Preston.IsDead()
        return
    endif
    if player == None || !IsCommonwealthExterior(player)
        return
    endif
    if Preston.GetCombatState() != 0
        return
    endif
    MoveActorToExteriorSpot(Preston, "Preston", S4BalconyMarker, S4BalconyX, S4BalconyY, S4BalconyZ, player, who, "on the museum balcony")
    prestonOff = SpotOff(Preston, S4BalconyX, S4BalconyY, S4BalconyZ)
    if !prestonHeld && prestonOff <= HeldRadius
        HoldPreston(who)
    endif
EndFunction

bool Function RelocateMarkerToMergedWorld(ObjectReference mk, string name, float tx, float ty, float tz, Actor player)
{R11 Step 3q: Moves a persistent FO4SFMission marker (0xB82..0xB8A) from the unmerged base world (0x01000803) into
 player's runtime merged Commonwealth world via PlaceAt (ignoreRadius=True) before SetLinkedRef or AddToMap.}
    if mk == None || player == None || !IsCommonwealthExterior(player)
        return False
    endif
    if player.GetDistance(mk) >= RelocateGap || SpotOff(mk, tx, ty, tz) > HoldRadius
        PlaceAt(mk, name, tx, ty, tz, player, "s9_marker", "in the Commonwealth", False, True)
        return True
    endif
    return False
EndFunction

Function MoveActorToExteriorSpot(Actor a, string name, ObjectReference marker, float fx, float fy, float fz, Actor player, string who, string where)
{R11 Step 3q: Moves an actor to a Commonwealth exterior spot via PlaceAt (merged-worldspace-safe MoveTo relative to
 player) followed by exact SetPosition snap for sub-HoldRadius vertical offsets such as S4 balcony z=98.51 m.}
    if a == None
        return
    endif
    float tx = fx
    float ty = fy
    float tz = fz
    if marker != None
        tx = marker.GetPositionX()
        ty = marker.GetPositionY()
        tz = marker.GetPositionZ()
    endif
    if player != None && !player.IsInInterior() && IsCommonwealthExterior(player)
        PlaceAt(a, name, tx, ty, tz, player, who, where, False)
    endif
    if SpotOff(a, tx, ty, tz) > 0.25
        a.SetPosition(tx, ty, tz)
    endif
EndFunction

Function ArmPrestonBalconyMusket()
    if s4PrestonArmed || Preston == None
        return
    endif
    Weapon compMusket = LookupOptionalForm(CompPrestonMusketId, "FO4SFCoreValues.esm") as Weapon
    Ammo compAmmo = LookupOptionalForm(CompPrestonAmmoId, "FO4SFCoreValues.esm") as Ammo
    if compMusket == None
        return
    endif
    s4PrestonArmed = True
    if Preston.GetItemCount(compMusket) < 1
        Preston.AddItem(compMusket, 1, True)
    endif
    if compAmmo != None && Preston.GetItemCount(compAmmo) < 50
        Preston.AddItem(compAmmo, 50, True)
    endif
    Preston.EquipItem(compMusket, False, True)
    Trace("s4 preston equipped comp_laser_musket=0x089E")
EndFunction

ObjectReference Function ResolveCommonwealthHostAnchor()
    ObjectReference wb = Game.GetFormFromFile(0x005C50, "FO4TerrainCore.esm") as ObjectReference
    if wb != None
        return wb
    endif
    ObjectReference mm = Game.GetFormFromFile(0x0A775B, "FO4TerrainCore.esm") as ObjectReference
    if mm != None
        return mm
    endif
    Actor p = Game.GetPlayer()
    if p != None && !p.IsInInterior()
        return p
    endif
    return None
EndFunction

Function PlaceMarkerInCommonwealth(ObjectReference mk, float tx, float ty, float tz)
    if mk == None
        return
    endif
    ObjectReference host = ResolveCommonwealthHostAnchor()
    if host == None
        return
    endif
    float dx = mk.GetPositionX() - tx
    float dy = mk.GetPositionY() - ty
    if mk.GetWorldSpace() != host.GetWorldSpace() || dx * dx + dy * dy > 4.0
        mk.MoveTo(host, tx - host.GetPositionX(), ty - host.GetPositionY(), tz - host.GetPositionZ(), False, False)
    endif
    mk.EnableNoWait(False)
EndFunction

Function SyncS4DisplayPickups()
    if !EnableS4Balcony || KeeperOnly
        return
    endif
    if S4DisplayMusketRef != None && !s4MusketTaken
        PlaceMarkerInCommonwealth(S4DisplayMusketRef, -2015.41, -1697.13, 88.19)
    endif
    if S4FusionCellRefs != None
        if S4FusionCellRefs.Length > 0 && S4FusionCellRefs[0] != None && (!s4FusionCellsPlaced || !S4FusionCellRefs[0].IsDisabled())
            PlaceMarkerInCommonwealth(S4FusionCellRefs[0], -2014.75, -1696.80, 88.16)
        endif
        if S4FusionCellRefs.Length > 1 && S4FusionCellRefs[1] != None && (!s4FusionCellsPlaced || !S4FusionCellRefs[1].IsDisabled())
            PlaceMarkerInCommonwealth(S4FusionCellRefs[1], -2014.56, -1696.47, 88.16)
        endif
        if S4FusionCellRefs.Length > 2 && S4FusionCellRefs[2] != None && (!s4FusionCellsPlaced || !S4FusionCellRefs[2].IsDisabled())
            PlaceMarkerInCommonwealth(S4FusionCellRefs[2], -2014.45, -1696.57, 88.16)
        endif
        s4FusionCellsPlaced = True
    endif
EndFunction

bool Function SetupS4BalconyEncounter(Actor player)
{R11 Step 3q (gated behind EnableS4Balcony == True; default False preserves 2g-fix):
 Places Preston at the Museum balcony (-2010.51, -1697.71, 98.51 m), equips FO4_CompPrestonLaserMusket (0x089E),
 syncs 0x0800 & 0x0814 to hold balcony Z=98.51, stages exterior street raider count (3), and displays objectives
 60 ("Enter the Museum") and 70 ("(Optional) Take the Laser Musket").}
    if !EnableS4Balcony || KeeperOnly || s4BalconySetup
        return False
    endif
    SyncKeeperPrestonMode(True, False)
    SyncS4DisplayPickups()
    if Preston != None
        MoveActorToExteriorSpot(Preston, "Preston", S4BalconyMarker, S4BalconyX, S4BalconyY, S4BalconyZ, player, "s4_balcony", "on the museum balcony")
        ArmPrestonBalconyMusket()
        EnsureActorTalkable(Preston)
    endif
    s4BalconySetup = True
    if FO4SF_QuestToastUtil.ShowObjectiveOnce(Self, 60, MuteDuplicateObjectiveToasts, obj60DisplayedOnce)
        obj60DisplayedOnce = True
    endif
    if FO4SF_QuestToastUtil.ShowObjectiveOnce(Self, 70, MuteDuplicateObjectiveToasts, obj70DisplayedOnce)
        obj70DisplayedOnce = True
    endif
    Trace("s4 balcony preston_z=" + S4BalconyZLabel + " ext_raiders=" + S4ExteriorRaiderCount)
    return True
EndFunction

bool Function TryGrantS4FallenMinutemanMusket(Actor player)
{R11 Step 3q: Optional fallen-Minuteman Laser Musket + 15 Fusion Cells pickup hook; nullable lookup with zero crash if unbuilt.}
    if !EnableS4Balcony || KeeperOnly || player == None || s4MusketTaken
        return False
    endif
    Weapon musket = LookupOptionalForm(LaserMusketId, "FO4SFCoreValues.esm") as Weapon
    if musket == None
        Trace("s4 laser_musket skipped reason=not_built_yet")
        return False
    endif
    player.AddItem(musket, 1, False)
    Ammo fcell = LookupOptionalForm(FusionCellId, "FO4SFCoreValues.esm") as Ammo
    int grantedCells = 0
    if fcell != None && S4MusketFusionCells > 0
        player.AddItem(fcell, S4MusketFusionCells, False)
        grantedCells = S4MusketFusionCells
    endif
    s4MusketTaken = True
    SetObjectiveCompleted(70)
    Trace("s4 laser_musket granted cells=" + grantedCells)
    return True
EndFunction

bool Function AdvanceS6PrestonGroupTalk()
{R11 Step 3q (gated behind EnableS6ToS9Full == True): S6 Museum 3F room group talk -> stage 40.}
    if !EnableS6ToS9Full || KeeperOnly || s6FullStage >= 40
        return False
    endif
    SyncKeeperPrestonMode(False, True)
    UnlockS6RoomDoors()
    s6FullStage = 40
    applied = 40
    SetStage(40)
    SetObjectiveCompleted(60)
    SetObjectiveCompleted(86)
    if FO4SF_QuestToastUtil.ShowObjectiveOnce(Self, 87, MuteDuplicateObjectiveToasts, obj87DisplayedOnce)
        obj87DisplayedOnce = True
    endif
    Trace("s6 stage 40 preston_group talk")
    if s6BasementUnlockedPending
        s6BasementUnlockedPending = False
        AdvanceS6BasementGateOpened()
    endif
    return True
EndFunction

bool Function AdvanceS6BasementGateOpened()
{R11 Step 3q: S6 Museum basement security gate unlocked -> stage 45.}
    if !EnableS6ToS9Full || KeeperOnly || s6FullStage < 40 || s6FullStage >= 45
        return False
    endif
    s6FullStage = 45
    applied = 45
    SetStage(45)
    SetObjectiveCompleted(87)
    if FO4SF_QuestToastUtil.ShowObjectiveOnce(Self, 90, MuteDuplicateObjectiveToasts, obj90DisplayedOnce)
        obj90DisplayedOnce = True
    endif
    Trace("s6 stage 45 basement_gate opened")
    return True
EndFunction

bool Function AdvanceS6FusionCorePicked()
{R11 Step 3q: S6 Museum basement Fusion Core collected -> stage 50 -> displays Obj 95 "Put the Fusion Core in the Power Armor" and stops.}
    if !EnableS6ToS9Full || KeeperOnly || s6FullStage < 45 || s6FullStage >= 50
        return False
    endif
    s6FullStage = 50
    applied = 50
    SetStage(50)
    SetObjectiveCompleted(90)
    if FO4SF_QuestToastUtil.ShowObjectiveOnce(Self, 95, MuteDuplicateObjectiveToasts, obj95DisplayedOnce)
        obj95DisplayedOnce = True
    endif
    if StopAtFusionCorePowerArmor
        Trace("s6 stage 50 fusion_core picked obj=95 stop=put_fusion_core_in_pa")
    else
        Trace("s6 stage 50 fusion_core picked")
    endif
    return True
EndFunction

ObjectReference Function ResolveDiamondCityMapMarker()
    if DiamondCityMapMarker != None
        return DiamondCityMapMarker
    endif
    return LookupOptionalForm(DiamondCityMapMarkerId, "FO4SFMission.esm") as ObjectReference
EndFunction

bool Function RevealDiamondCityMapMarker(Actor player)
{R11 Step 3q: Enables 0x000B8A FO4SF_DiamondCityMapMarker (STAT 0x000010 MapMarker), relocates it into player's
 merged Commonwealth exterior when outdoors, and calls AddToMap(False).}
    ObjectReference dcMarker = ResolveDiamondCityMapMarker()
    if dcMarker == None
        return False
    endif
    dcMarker.EnableNoWait(False)
    if player != None && IsCommonwealthExterior(player)
        RelocateMarkerToMergedWorld(dcMarker, "DiamondCityMapMarker", DiamondCityMapMarkerX, DiamondCityMapMarkerY, DiamondCityMapMarkerZ, player)
        s9DiamondCityMerged = True
    endif
    dcMarker.AddToMap(False)
    s9DiamondCityRevealed = True
    return True
EndFunction

bool Function CompleteS9LobbyTalkAndReward(Actor player)
{R11 Step 3q: S9 Museum lobby talk (stage 90) grants exact FO4 QF_DialogueConcordArea_000179F3 L33-34 reward
 (100 Caps + 50 Fusion Cells, NEVER silent Starfield Credits), reveals real MapMarker 0xB8A Diamond City via AddToMap()
 (stage 150 parity), and strictly leaves FO4SF_MQ103 (0x0A50) and FO4SF_MinRecruit00 (0x0A20) untouched at stage 0.}
    if !EnableS6ToS9Full || KeeperOnly || player == None || s9LobbyCompleted
        return False
    endif
    s9LobbyCompleted = True
    s6FullStage = 90
    applied = 90
    SetStage(90)
    SetObjectiveCompleted(140)

    Form capsForm = LookupOptionalForm(BottlecapId, "FO4SFCoreValues.esm")
    bool capsFormOk = False
    if capsForm != None && S9RewardCaps > 0
        player.AddItem(capsForm, S9RewardCaps, False)
        capsFormOk = True
    endif
    Form cellForm = LookupOptionalForm(FusionCellId, "FO4SFCoreValues.esm")
    bool cellsFormOk = False
    if cellForm != None && S9RewardFusionCells > 0
        player.AddItem(cellForm, S9RewardFusionCells, False)
        cellsFormOk = True
    endif
    Trace("s9 stage 90 reward caps=" + S9RewardCaps + " fusion_cells=" + S9RewardFusionCells + " credits=0 caps_form_ok=" + capsFormOk + " cells_form_ok=" + cellsFormOk)

    RevealDiamondCityMapMarker(player)
    s6FullStage = 150
    applied = 150
    SetStage(150)
    if FO4SF_QuestToastUtil.ShowObjectiveOnce(Self, 150, MuteDuplicateObjectiveToasts, obj150DisplayedOnce)
        obj150DisplayedOnce = True
    endif
    Trace("s9 stage 150 diamond_city addtomap=" + s9DiamondCityRevealed + " mq103_stage=0 minrecruit00_stage=0")
    return True
EndFunction

int Function PrepareAndChainS9PatrolWaypoints(Actor player)
{R11 Step 3q: Relocates persistent S9PatrolWaypoints (0xB82..0xB89) into player's runtime merged Commonwealth world
 before chaining SetLinkedRef along Concord -> Red Rocket -> Sanctuary North Bridge and linking Preston + group.}
    int wpCount = 0
    if S9PatrolWaypoints == None || S9PatrolWaypoints.Length == 0
        return 0
    endif
    wpCount = S9PatrolWaypoints.Length
    if player != None && IsCommonwealthExterior(player)
        int ri = 0
        while ri < wpCount
            ObjectReference rWp = S9PatrolWaypoints[ri]
            if rWp != None
                RelocateMarkerToMergedWorld(rWp, "S9PatrolWP_" + ri, rWp.GetPositionX(), rWp.GetPositionY(), rWp.GetPositionZ(), player)
            endif
            ri += 1
        endwhile
    endif
    int wi = 0
    while wi + 1 < wpCount
        ObjectReference curWp = S9PatrolWaypoints[wi]
        ObjectReference nxtWp = S9PatrolWaypoints[wi + 1]
        if curWp != None && nxtWp != None
            curWp.SetLinkedRef(nxtWp, None, True)
        endif
        wi += 1
    endwhile
    ObjectReference firstWp = S9PatrolWaypoints[0]
    if firstWp != None
        if Preston != None
            Preston.SetRestrained(False)
            Preston.SetLinkedRef(firstWp, None, True)
            Preston.EvaluatePackage()
        endif
        if MinutemenGroup != None
            int mi = 0
            while mi < MinutemenGroup.Length
                Actor gm = MinutemenGroup[mi]
                if gm != None
                    gm.SetRestrained(False)
                    gm.SetLinkedRef(firstWp, None, True)
                    gm.EvaluatePackage()
                endif
                mi += 1
            endwhile
        endif
    endif
    return wpCount
EndFunction

bool Function BeginS9MuseumExitAndPatrol(Actor player = None)
{R11 Step 3q: Releases Preston on BOTH 0x0800 and 0x0814, places Preston & group outside the Museum front exit
 (-2010.57, -1697.94, 89.26), ensures 0xB8A Diamond City MapMarker + 0xB82..0xB89 waypoints are relocated into player's
 merged Commonwealth world, and starts P9 SetLinkedRef patrol along the Red Rocket road corridor (never east quarry!).}
    if !EnableS6ToS9Full || KeeperOnly || !s9LobbyCompleted || s9PatrolStarted
        return False
    endif
    if player == None
        player = Game.GetPlayer()
    endif
    SyncKeeperPrestonMode(False, True)
    if Preston != None
        Preston.SetRestrained(False)
        prestonHeld = False
        MoveActorToExteriorSpot(Preston, "Preston", S9MuseumExitMarker, S9MuseumExitX, S9MuseumExitY, S9MuseumExitZ, player, "s9_exit", "outside the museum")
    endif
    if MinutemenGroup != None
        int gi = 0
        while gi < MinutemenGroup.Length
            Actor m = MinutemenGroup[gi]
            if m != None
                m.SetRestrained(False)
                MoveActorToExteriorSpot(m, "Minuteman", S9MuseumExitMarker, S9MuseumExitX, S9MuseumExitY, S9MuseumExitZ, player, "s9_exit", "outside the museum")
            endif
            gi += 1
        endwhile
    endif
    Trace("min01 museum_exit moveto_front=true")

    if !s9DiamondCityMerged && player != None && IsCommonwealthExterior(player)
        RevealDiamondCityMapMarker(player)
    endif
    int wpCount = PrepareAndChainS9PatrolWaypoints(player)
    s9PatrolStarted = True
    s9PatrolStartedAt = Utility.GetCurrentRealTime()
    s9PatrolElapsed = 0.0
    Trace("min01 patrol started route=red_rocket waypoints=" + wpCount)
    return True
EndFunction

bool Function ResumeS9PatrolAfterLoad(Actor player)
{R11 Step 3q: Re-applies patrol release on 0x0800 & 0x0814, merged-world waypoints, SetRestrained(False), and
 EvaluatePackage() after a mid-patrol save reload.}
    if !EnableS6ToS9Full || KeeperOnly || !s9PatrolStarted || s9GroupArrived
        return False
    endif
    SyncKeeperPrestonMode(False, True)
    PrepareAndChainS9PatrolWaypoints(player)
    prestonTalkReloaded = False
    Trace("min01 patrol resumed_after_load")
    return True
EndFunction

bool Function CheckS9SanctuaryArrival(Actor player, float deltaSec = 1.0)
{R11 Step 3q: Completes S9 walk either when Preston reaches Sanctuary via P9 patrol walk or via unloaded/elapsed-time
 failsafe (>= 180 s or player already in Sanctuary > 150 m ahead of group). Calls FO4SF_Sanctuary01Quest
 OnSturgesArrivedFromConcord() + AdvanceTo(1000, "s9_arrival") (HARD STOP) while leaving MQ103 & MinRecruit00 at stage 0.}
    if !EnableS6ToS9Full || KeeperOnly || !s9PatrolStarted || s9GroupArrived
        return False
    endif
    if deltaSec > 0.0
        s9PatrolElapsed = s9PatrolElapsed + deltaSec
    endif
    bool arrived = False
    string via = ""
    float prestonDist = 99999.0
    if Preston != None
        prestonDist = SpotOff(Preston, S9SanctuaryX, S9SanctuaryY, S9SanctuaryZ)
    endif
    if prestonDist <= S9SanctuaryArrivalRadius
        arrived = True
        via = "p9_patrol_walk"
    else
        bool playerInSanctuary = False
        if player != None
            float pDist = SpotOff(player, S9SanctuaryX, S9SanctuaryY, S9SanctuaryZ)
            if pDist <= S9SanctuaryPlayerRadius
                playerInSanctuary = True
            endif
        endif
        if s9PatrolElapsed >= S9PatrolFailsafeSeconds || (playerInSanctuary && prestonDist > S9SanctuaryGroupFarDist)
            arrived = True
            via = "unloaded_failsafe"
            ObjectReference lastWp = None
            if S9PatrolWaypoints != None && S9PatrolWaypoints.Length > 0
                lastWp = S9PatrolWaypoints[S9PatrolWaypoints.Length - 1]
            endif
            if Preston != None
                MoveActorToExteriorSpot(Preston, "Preston", lastWp, S9SanctuaryX, S9SanctuaryY, S9SanctuaryZ, player, "s9_failsafe", "in Sanctuary")
                Preston.EvaluatePackage()
            endif
            if MinutemenGroup != None
                int mi = 0
                while mi < MinutemenGroup.Length
                    Actor gm = MinutemenGroup[mi]
                    if gm != None
                        MoveActorToExteriorSpot(gm, "Minuteman", lastWp, S9SanctuaryX, S9SanctuaryY, S9SanctuaryZ, player, "s9_failsafe", "in Sanctuary")
                        gm.EvaluatePackage()
                    endif
                    mi += 1
                endwhile
            endif
        endif
    endif
    if !arrived
        return False
    endif
    SyncKeeperPrestonMode(False, True)
    s9GroupArrived = True
    s9ArrivalVia = via
    SetObjectiveCompleted(150)
    s6FullStage = 200
    applied = 200
    SetStage(200)
    CompleteQuest()
    Trace("min01 group_arrived sanctuary=true via=" + via)

    Quest sanctuaryQuest = Game.GetFormFromFile(0x000817, "FO4SFMission.esm") as Quest
    if sanctuaryQuest != None
        if !sanctuaryQuest.IsRunning()
            sanctuaryQuest.StartNoWait()
        endif
        FO4SF_Sanctuary01Quest sancScript = sanctuaryQuest as FO4SF_Sanctuary01Quest
        if sancScript != None
            sancScript.OnSturgesArrivedFromConcord()
            sancScript.AdvanceTo(1000, "s9_arrival")
        endif
        sanctuaryQuest.SetStage(1000)
        if FO4SF_QuestToastUtil.ShowObjectiveOnce(sanctuaryQuest, 1000, MuteDuplicateObjectiveToasts, sanctuaryObj1000DisplayedOnce)
            sanctuaryObj1000DisplayedOnce = True
        endif
    endif
    Trace("sanctuary01 stage 1000 obj=1000 hard_stop=true")
    return True
EndFunction

; ------------------------------------------------------------------ S5/S6 Concord Museum interior + 3F scenes + basement gate helpers

bool Function IsPlayerInMuseum(Actor player)
    if player == None || !player.IsInInterior()
        return False
    endif
    Cell museumCell = LookupOptionalForm(0x00E2F4, "FO4Port.esm") as Cell
    return museumCell != None && player.GetParentCell() == museumCell
EndFunction

Function PlaceRefInMuseum(ObjectReference r, ObjectReference anchor, float tx, float ty, float tz, float headingDeg = 0.0)
    if r == None || anchor == None
        return
    endif
    r.MoveTo(anchor, tx - 8.228572, ty - 0.000002, tz - (-0.914286), False, False)
    if headingDeg != 0.0
        r.SetAngle(0.0, 0.0, headingDeg)
    endif
    r.EnableNoWait(False)
EndFunction

Function HideOverlappingCoreStatic(ObjectReference refObj, int coreStaticLocalId)
    if refObj == None || coreStaticLocalId <= 0
        return
    endif
    Form statBase = LookupOptionalForm(coreStaticLocalId, "FO4TerrainCore.esm")
    if statBase == None
        return
    endif
    ObjectReference overlap = Game.FindClosestReferenceOfTypeFromRef(statBase, refObj, 3.0)
    if overlap != None && overlap != refObj && !overlap.IsDisabled()
        overlap.DisableNoWait(False)
    endif
EndFunction

Function PlaceDoorInCommonwealth(ObjectReference mk, float tx, float ty, float tz, float headingDeg, int hideStaticLocalId = 0)
    if mk == None
        return
    endif
    PlaceMarkerInCommonwealth(mk, tx, ty, tz)
    if Math.Abs(mk.GetPositionZ() - tz) > 1.0
        mk.SetPosition(tx, ty, tz)
    endif
    mk.SetAngle(0.0, 0.0, headingDeg)
    mk.EnableNoWait(False)
    HideOverlappingCoreStatic(mk, hideStaticLocalId)
EndFunction

Function SyncS5ExteriorDoors(Actor player)
    SyncS4DisplayPickups()
    if S5MuseumDoors == None || S5MuseumDoors.Length < 4 || player == None || player.IsInInterior()
        return
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float dx = px - (-2010.69)
    float dy = py - (-1698.04)
    if dx * dx + dy * dy > 350.0 * 350.0
        return
    endif
    PlaceDoorInCommonwealth(S5MuseumDoors[0], -2010.69, -1698.04, 89.26, 130.0, 0x0019E6)
    PlaceDoorInCommonwealth(S5MuseumDoors[3], -1991.27, -1722.57, 97.42, 128.97, 0x001E75)
EndFunction

Function UnlockS6RoomDoors()
    ObjectReference pDoor = LookupOptionalForm(0x00EFA9, "FO4Port.esm") as ObjectReference
    if pDoor != None
        pDoor.SetLockLevel(0)
        pDoor.Lock(False, False, False)
        pDoor.SetOpen(True)
    endif
    ObjectReference pExitDoor = LookupOptionalForm(0x00EFAA, "FO4Port.esm") as ObjectReference
    if pExitDoor != None
        pExitDoor.SetLockLevel(0)
        pExitDoor.Lock(False, False, False)
        pExitDoor.SetOpen(True)
    endif
EndFunction

Function RegisterS6RoomEvents()
    if KeeperOnly || !EnableS6ToS9Full
        return
    endif
    ObjectReference gateSync = LookupOptionalForm(0x00EDF0, "FO4Port.esm") as ObjectReference
    if gateSync != None
        gateSync.BlockActivation(gateSync.IsLocked(), False)
    endif
    ObjectReference termSync = LookupOptionalForm(0x00E35E, "FO4Port.esm") as ObjectReference
    if termSync != None
        termSync.BlockActivation(termSync.IsLocked(), False)
    endif
    if s6RoomEventsRegistered
        return
    endif
    s6RoomEventsRegistered = True
    if S6PrestonRoomScene != None
        RegisterForRemoteEvent(S6PrestonRoomScene, "OnBegin")
        RegisterForRemoteEvent(S6PrestonRoomScene, "OnPhaseBegin")
        RegisterForRemoteEvent(S6PrestonRoomScene, "OnEnd")
    endif
    if S6SturgesRoomScene != None
        RegisterForRemoteEvent(S6SturgesRoomScene, "OnBegin")
        RegisterForRemoteEvent(S6SturgesRoomScene, "OnPhaseBegin")
        RegisterForRemoteEvent(S6SturgesRoomScene, "OnEnd")
    endif
    if SturgesRef != None
        RegisterForRemoteEvent(SturgesRef, "OnActivate")
    endif
    ObjectReference termRef = LookupOptionalForm(0x00E35E, "FO4Port.esm") as ObjectReference
    if termRef != None
        RegisterForRemoteEvent(termRef, "OnActivate")
        RegisterForRemoteEvent(termRef, "OnLockStateChanged")
    endif
    ObjectReference gateRef = LookupOptionalForm(0x00EDF0, "FO4Port.esm") as ObjectReference
    if gateRef != None
        RegisterForRemoteEvent(gateRef, "OnActivate")
        RegisterForRemoteEvent(gateRef, "OnLockStateChanged")
    endif
EndFunction

Function InitializeS5MuseumEncounter(Actor player)
    if s5MuseumInitialized
        return
    endif
    ObjectReference anchor = LookupOptionalForm(0x00E2F5, "FO4Port.esm") as ObjectReference
    if anchor == None
        return
    endif
    s5MuseumInitialized = True
    RegisterS6RoomEvents()
    SyncKeeperPrestonMode(False, True)
    s4BalconyActive = False

    ObjectReference staticFrontDoor = LookupOptionalForm(0x00EDEC, "FO4Port.esm") as ObjectReference
    if staticFrontDoor != None && !staticFrontDoor.IsDisabled()
        staticFrontDoor.DisableNoWait(False)
    endif
    ObjectReference staticRoofDoor = LookupOptionalForm(0x00EDF5, "FO4Port.esm") as ObjectReference
    if staticRoofDoor != None && !staticRoofDoor.IsDisabled()
        staticRoofDoor.DisableNoWait(False)
    endif

    if S5MuseumDoors != None && S5MuseumDoors.Length >= 3
        PlaceRefInMuseum(S5MuseumDoors[1], anchor, 9.02, 0.0, -0.914, 90.0)
        PlaceRefInMuseum(S5MuseumDoors[2], anchor, -21.943, 9.02, 9.143, 90.0)
    endif

    ; Restroom Medkit (FO4Port.esm:0x00E3B6) -> inject real FO4SF_Stimpak (0x000851) once
    ObjectReference medkit = LookupOptionalForm(0x00E3B6, "FO4Port.esm") as ObjectReference
    Form stimpak = LookupOptionalForm(StimpakId, "FO4SFCoreValues.esm")
    if medkit != None && stimpak != None && medkit.GetItemCount(stimpak) < 1
        medkit.AddItem(stimpak, 1, True)
    endif

    ; Place A4.5 2 loose Stimpaks, Caps, Bobby Pin, Pipe Weapon + .38, Basement Terminal proxy, Fusion Core
    if S5MuseumLootMarkers != None
        if S5MuseumLootMarkers.Length > 0
            PlaceRefInMuseum(S5MuseumLootMarkers[0], anchor, 4.2, -3.6, 3.1)
        endif
        if S5MuseumLootMarkers.Length > 1
            PlaceRefInMuseum(S5MuseumLootMarkers[1], anchor, -4.8, 2.4, 5.9)
        endif
        if S5MuseumLootMarkers.Length > 2
            PlaceRefInMuseum(S5MuseumLootMarkers[2], anchor, 6.5, -1.2, -0.1)
        endif
        if S5MuseumLootMarkers.Length > 3
            PlaceRefInMuseum(S5MuseumLootMarkers[3], anchor, -12.2, 2.1, -3.1)
        endif
        if S5MuseumLootMarkers.Length > 4
            PlaceRefInMuseum(S5MuseumLootMarkers[4], anchor, 2.0, 4.0, 0.0)
        endif
        if S5MuseumLootMarkers.Length > 5
            PlaceRefInMuseum(S5MuseumLootMarkers[5], anchor, -14.092, -1.750, -3.566, 90.0)
        endif
        if S5MuseumLootMarkers.Length > 6
            PlaceRefInMuseum(S5MuseumLootMarkers[6], anchor, -11.196, -1.584, -2.663)
        endif
    endif

    ; Place 7 FO4 floor-by-floor Museum Raiders inside FO4Port_ConcordMuseum01
    if S5MuseumRaiders != None
        float[] rx = new float[7]
        float[] ry = new float[7]
        float[] rz = new float[7]
        rx[0] = -24.517
        ry[0] = 14.337
        rz[0] = 0.016
        rx[1] = -11.429
        ry[1] = 2.743
        rz[1] = 5.486
        rx[2] = -10.444
        ry[2] = -15.563
        rz[2] = 5.486
        rx[3] = -9.759
        ry[3] = -13.360
        rz[3] = 5.486
        rx[4] = -12.571
        ry[4] = -2.514
        rz[4] = 8.914
        rx[5] = 3.570
        ry[5] = -7.295
        rz[5] = 9.143
        rx[6] = -1.156
        ry[6] = -7.658
        rz[6] = 9.143
        int ri = 0
        while ri < S5MuseumRaiders.Length && ri < 7
            Actor mr = S5MuseumRaiders[ri]
            if mr != None
                PlaceRefInMuseum(mr, anchor, rx[ri], ry[ri], rz[ri])
                ArmRaiderForCombat(mr, ri)
                EquipBalancedRaiderSidearm(mr, ri)
            endif
            ri += 1
        endwhile
    endif

    ; Place 3F Room NPCs behind locked PrestonDoorREF (0x0100EFA9)
    if Preston != None
        PlaceRefInMuseum(Preston, anchor, 11.033, -5.869, 9.143)
        EnsureActorTalkable(Preston)
    endif
    if SturgesRef != None
        PlaceRefInMuseum(SturgesRef, anchor, 9.752, -6.655, 9.143)
        EnsureActorTalkable(SturgesRef)
    endif
    if MinutemenGroup != None
        float[] gx = new float[3]
        float[] gy = new float[3]
        float[] gz = new float[3]
        gx[0] = 9.654
        gy[0] = -2.732
        gz[0] = 9.143
        gx[1] = 7.675
        gy[1] = 3.486
        gz[1] = 9.143
        gx[2] = 11.106
        gy[2] = 0.584
        gz[2] = 9.143
        int gi = 0
        int posIdx = 0
        while gi < MinutemenGroup.Length && posIdx < 3
            Actor gm = MinutemenGroup[gi]
            if gm != None && gm != SturgesRef && gm != Preston
                PlaceRefInMuseum(gm, anchor, gx[posIdx], gy[posIdx], gz[posIdx])
                posIdx += 1
            endif
            gi += 1
        endwhile
    endif

    ObjectReference pDoor = LookupOptionalForm(0x00EFA9, "FO4Port.esm") as ObjectReference
    if pDoor != None && !s5MuseumCleared
        pDoor.Lock(True, False, False)
        pDoor.SetLockLevel(255)
    endif
    ObjectReference pExitDoor = LookupOptionalForm(0x00EFAA, "FO4Port.esm") as ObjectReference
    if pExitDoor != None && !s5MuseumCleared
        pExitDoor.Lock(True, False, False)
        pExitDoor.SetLockLevel(255)
    endif
    Trace("s5 museum initialized raiders=" + S5MuseumRaiders.Length + " medkit_stimpak=" + (stimpak != None))
EndFunction

Function UpdateS5MuseumEncounter(Actor player)
    if !EnableS6ToS9Full || KeeperOnly || player == None
        return
    endif
    if !s5MuseumInitialized
        InitializeS5MuseumEncounter(player)
    endif
    if s5MuseumCleared || S5MuseumRaiders == None || S5MuseumRaiders.Length == 0
        return
    endif
    s5RaiderEngageTicks += 1
    bool doEngage = IsPlayerInMuseum(player) && ((s5RaiderEngageTicks % 3) == 1)
    int deadCount = 0
    int i = 0
    while i < S5MuseumRaiders.Length
        Actor mr = S5MuseumRaiders[i]
        if mr == None || mr.IsDead()
            deadCount += 1
        elseif doEngage && mr.Is3DLoaded()
            mr.SetRestrained(False)
            mr.EvaluatePackage()
            if !mr.IsInCombat() || mr.GetCombatTarget() != player
                var[] combatArgs = new var[1]
                combatArgs[0] = player
                mr.CallFunctionNoWait("StartCombat", combatArgs)
            endif
            var[] pathArgs = new var[3]
            pathArgs[0] = player
            pathArgs[1] = 1.0
            pathArgs[2] = 1.0
            mr.CallFunctionNoWait("PathToReference", pathArgs)
        endif
        i += 1
    endwhile
    s5MuseumRaidersDead = deadCount
    if deadCount >= S5MuseumRaiders.Length
        s5MuseumCleared = True
        UnlockS6RoomDoors()
        EnsureActorTalkable(Preston)
        if SturgesRef != None
            EnsureActorTalkable(SturgesRef)
        endif
        AdvanceTo(35, "s5_museum_cleared")
        Trace("s5 museum_cleared dead=" + deadCount + "/" + S5MuseumRaiders.Length + " stage=35 preston_door=unlocked")
    endif
EndFunction

bool Function PlayerHasBobbyPin(Actor player)
    if player == None
        return False
    endif
    Form bp = LookupOptionalForm(BobbyPinId, "FO4SFCoreValues.esm")
    return bp != None && player.GetItemCount(bp) >= 1
EndFunction

bool Function TryOpenS6BasementGate(string reason)
    if !EnableS6ToS9Full || KeeperOnly
        return False
    endif
    ObjectReference gateRef = LookupOptionalForm(0x00EDF0, "FO4Port.esm") as ObjectReference
    if gateRef != None
        gateRef.BlockActivation(False, False)
        gateRef.Unlock(False)
        gateRef.SetLockLevel(0)
        gateRef.Lock(False, False, True)
        gateRef.SetOpen(True)
    endif
    ObjectReference termRef = LookupOptionalForm(0x00E35E, "FO4Port.esm") as ObjectReference
    if termRef != None
        termRef.BlockActivation(False, False)
        termRef.Unlock(False)
        termRef.SetLockLevel(0)
        termRef.Lock(False, False, False)
    endif
    Trace("basement_gate_unlock=" + reason)
    if s6FullStage >= 40
        return AdvanceS6BasementGateOpened()
    endif
    s6BasementUnlockedPending = True
    Trace("s6 basement_gate unlocked reason=" + reason + " pending_stage40=true")
    return True
EndFunction

Function TriggerS6RoomScene(bool isSturges, string via)
    Scene scn = S6PrestonRoomScene
    Actor speaker = Preston
    int timerId = 5
    if isSturges
        scn = S6SturgesRoomScene
        speaker = SturgesRef
        timerId = 6
    endif
    if speaker != None
        EnsureActorTalkable(speaker)
    endif
    if ShouldUseMessageBox()
        if !isSturges
            AdvanceS6PrestonGroupTalk()
        else
            Debug.MessageBox("Sturges: Grab the Fusion Core in the basement, then bring it up to the roof Power Armor.")
        endif
        return
    endif
    if scn == None
        RestartOrFailS6RoomScene(isSturges, "no_scene")
        return
    endif
    if isSturges
        s6SturgesScenePending = True
        s6SturgesSceneMenuOpened = False
        s6SturgesScenePhase1 = False
        s6SturgesPhase1At = 0.0
        s6SturgesAttemptStartedAt = Utility.GetCurrentRealTime()
        s6SturgesSceneTicks = 0
        if !scn.IsPlaying()
            s6SturgesSceneRestarting = False
        endif
    else
        s6RoomScenePending = True
        s6RoomSceneMenuOpened = False
        s6RoomScenePhase1 = False
        s6RoomPhase1At = 0.0
        s6RoomAttemptStartedAt = Utility.GetCurrentRealTime()
        s6RoomSceneTicks = 0
        if !scn.IsPlaying()
            s6RoomSceneRestarting = False
        endif
    endif
    if !scn.IsPlaying()
        scn.Start()
        if !scn.IsPlaying()
            scn.ForceStart()
        endif
    endif
    Trace("s6 room_scene requested sturges=" + isSturges + " via=" + via)
    CancelTimer(timerId)
    StartTimer(PrestonSceneCheckSeconds, timerId)
EndFunction

Function HandleS6RoomSceneEnded(bool isSturges)
    if isSturges
        if s6SturgesSceneRestarting
            s6SturgesSceneRestarting = False
            return
        endif
    elseif s6RoomSceneRestarting
        s6RoomSceneRestarting = False
        return
    endif
    int timerId = 5
    bool pending = s6RoomScenePending
    bool opened = s6RoomSceneMenuOpened
    float attStarted = s6RoomAttemptStartedAt
    if isSturges
        timerId = 6
        pending = s6SturgesScenePending
        opened = s6SturgesSceneMenuOpened
        attStarted = s6SturgesAttemptStartedAt
    endif
    if !isSturges && (opened || GetStageDone(40) || EffectiveStage() >= 40)
        s6RoomScenePending = False
        s6RoomScenePhase1 = False
        s6RoomPhase1At = 0.0
        s6RoomAttemptStartedAt = 0.0
        CancelTimer(5)
        AdvanceS6PrestonGroupTalk()
        return
    endif
    if pending && !opened && !ShouldUseMessageBox()
        float nowEnd = Utility.GetCurrentRealTime()
        if attStarted > 0.0 && nowEnd < attStarted
            attStarted = nowEnd
            if isSturges
                s6SturgesAttemptStartedAt = nowEnd
            else
                s6RoomAttemptStartedAt = nowEnd
            endif
        endif
        float attElapsed = nowEnd - attStarted
        if attStarted > 0.0 && attElapsed < (PrestonSceneCheckSeconds - 0.05)
            CancelTimer(timerId)
            StartTimer(PrestonSceneCheckSeconds - attElapsed, timerId)
        else
            RestartOrFailS6RoomScene(isSturges, "scene_incomplete")
        endif
        return
    endif
    if isSturges
        s6SturgesScenePending = False
        s6SturgesScenePhase1 = False
        s6SturgesPhase1At = 0.0
        s6SturgesAttemptStartedAt = 0.0
    else
        s6RoomScenePending = False
        s6RoomScenePhase1 = False
        s6RoomPhase1At = 0.0
        s6RoomAttemptStartedAt = 0.0
    endif
    CancelTimer(timerId)
EndFunction

Function RestartOrFailS6RoomScene(bool isSturges, string reason)
    if ShouldUseMessageBox()
        if isSturges
            s6SturgesScenePending = False
            s6SturgesScenePhase1 = False
            s6SturgesPhase1At = 0.0
            s6SturgesAttemptStartedAt = 0.0
        else
            s6RoomScenePending = False
            s6RoomScenePhase1 = False
            s6RoomPhase1At = 0.0
            s6RoomAttemptStartedAt = 0.0
            AdvanceS6PrestonGroupTalk()
        endif
        return
    endif
    Scene scn = S6PrestonRoomScene
    Actor speaker = Preston
    int timerId = 5
    if isSturges
        scn = S6SturgesRoomScene
        speaker = SturgesRef
        timerId = 6
        if scn == None
            s6SturgesScenePending = False
            s6SturgesScenePhase1 = False
            s6SturgesPhase1At = 0.0
            s6SturgesAttemptStartedAt = 0.0
            CancelTimer(6)
            if speaker != None
                EnsureActorTalkable(speaker)
            endif
            Trace("s6 sturges ERROR scene_failed retries=" + s6SturgesSceneRetries + "/" + PrestonMaxSceneRestarts + " reason=" + reason + " actor_talkable=true")
            return
        endif
        if s6SturgesSceneRetries < PrestonMaxSceneRestarts
            s6SturgesSceneRetries += 1
            if scn.IsPlaying()
                s6SturgesSceneRestarting = True
                scn.Stop()
            endif
            s6SturgesScenePending = True
            s6SturgesSceneMenuOpened = False
            s6SturgesScenePhase1 = False
            s6SturgesPhase1At = 0.0
            s6SturgesAttemptStartedAt = Utility.GetCurrentRealTime()
            s6SturgesSceneTicks = 0
            if speaker != None
                EnsureActorTalkable(speaker)
            endif
            scn.Start()
            if !scn.IsPlaying()
                scn.ForceStart()
            endif
            Trace("s6 sturges scene_restart retry=" + s6SturgesSceneRetries + "/" + PrestonMaxSceneRestarts + " reason=" + reason)
            CancelTimer(6)
            StartTimer(PrestonSceneCheckSeconds, 6)
        else
            s6SturgesScenePending = False
            s6SturgesScenePhase1 = False
            s6SturgesPhase1At = 0.0
            s6SturgesAttemptStartedAt = 0.0
            CancelTimer(6)
            if scn.IsPlaying()
                s6SturgesSceneRestarting = True
                scn.Stop()
            else
                s6SturgesSceneRestarting = False
            endif
            if speaker != None
                EnsureActorTalkable(speaker)
            endif
            Trace("s6 sturges ERROR scene_failed retries=" + s6SturgesSceneRetries + "/" + PrestonMaxSceneRestarts + " reason=" + reason + " actor_talkable=true")
        endif
        return
    endif

    if scn == None
        s6RoomScenePending = False
        s6RoomScenePhase1 = False
        s6RoomPhase1At = 0.0
        s6RoomAttemptStartedAt = 0.0
        CancelTimer(5)
        if speaker != None
            EnsureActorTalkable(speaker)
        endif
        Trace("s6 preston ERROR scene_failed retries=" + s6RoomSceneRetries + "/" + PrestonMaxSceneRestarts + " reason=" + reason + " actor_talkable=true")
        return
    endif
    if s6RoomSceneRetries < PrestonMaxSceneRestarts
        s6RoomSceneRetries += 1
        if scn.IsPlaying()
            s6RoomSceneRestarting = True
            scn.Stop()
        endif
        s6RoomScenePending = True
        s6RoomSceneMenuOpened = False
        s6RoomScenePhase1 = False
        s6RoomPhase1At = 0.0
        s6RoomAttemptStartedAt = Utility.GetCurrentRealTime()
        s6RoomSceneTicks = 0
        if speaker != None
            EnsureActorTalkable(speaker)
        endif
        scn.Start()
        if !scn.IsPlaying()
            scn.ForceStart()
        endif
        Trace("s6 preston scene_restart retry=" + s6RoomSceneRetries + "/" + PrestonMaxSceneRestarts + " reason=" + reason)
        CancelTimer(5)
        StartTimer(PrestonSceneCheckSeconds, 5)
    else
        s6RoomScenePending = False
        s6RoomScenePhase1 = False
        s6RoomPhase1At = 0.0
        s6RoomAttemptStartedAt = 0.0
        CancelTimer(5)
        if scn.IsPlaying()
            s6RoomSceneRestarting = True
            scn.Stop()
        else
            s6RoomSceneRestarting = False
        endif
        if speaker != None
            EnsureActorTalkable(speaker)
        endif
        Trace("s6 preston ERROR scene_failed retries=" + s6RoomSceneRetries + "/" + PrestonMaxSceneRestarts + " reason=" + reason + " actor_talkable=true")
    endif
EndFunction

Function CheckS6RoomSceneOpen(bool isSturges)
    if isSturges
        if !s6SturgesScenePending || s6SturgesSceneMenuOpened || prestonDialogueMenuOpen
            s6SturgesScenePending = False
            s6SturgesScenePhase1 = False
            s6SturgesPhase1At = 0.0
            s6SturgesAttemptStartedAt = 0.0
            return
        endif
        s6SturgesSceneTicks += 1
        float sNowRt = Utility.GetCurrentRealTime()
        if s6SturgesAttemptStartedAt > 0.0 && sNowRt < s6SturgesAttemptStartedAt
            s6SturgesAttemptStartedAt = sNowRt
        endif
        float sAttemptElapsed = PrestonSceneCheckSeconds
        if s6SturgesAttemptStartedAt > 0.0
            sAttemptElapsed = sNowRt - s6SturgesAttemptStartedAt
        endif
        bool sPhase1Elapsed = False
        if s6SturgesScenePhase1
            if sNowRt < s6SturgesPhase1At
                s6SturgesPhase1At = sNowRt
            elseif (sNowRt - s6SturgesPhase1At) >= (PrestonSceneCheckSeconds - 0.05)
                sPhase1Elapsed = True
            endif
        endif
        if S6SturgesRoomScene == None
            RestartOrFailS6RoomScene(True, "scene_inactive")
        elseif !S6SturgesRoomScene.IsPlaying()
            if sAttemptElapsed < (PrestonSceneCheckSeconds - 0.05)
                StartTimer(PrestonSceneCheckSeconds - sAttemptElapsed, 6)
            else
                RestartOrFailS6RoomScene(True, "scene_inactive")
            endif
        elseif (sPhase1Elapsed || s6SturgesSceneTicks >= PrestonSceneMaxWaitChecks) && sAttemptElapsed >= (PrestonSceneCheckSeconds - 0.05)
            RestartOrFailS6RoomScene(True, "dialogue_menu_timeout")
        elseif sPhase1Elapsed || s6SturgesSceneTicks >= PrestonSceneMaxWaitChecks
            StartTimer(PrestonSceneCheckSeconds - sAttemptElapsed, 6)
        else
            StartTimer(PrestonSceneCheckSeconds, 6)
        endif
        return
    endif

    if !s6RoomScenePending || s6RoomSceneMenuOpened || prestonDialogueMenuOpen || s6FullStage >= 40
        s6RoomScenePending = False
        s6RoomScenePhase1 = False
        s6RoomPhase1At = 0.0
        s6RoomAttemptStartedAt = 0.0
        return
    endif
    s6RoomSceneTicks += 1
    float pNowRt = Utility.GetCurrentRealTime()
    if s6RoomAttemptStartedAt > 0.0 && pNowRt < s6RoomAttemptStartedAt
        s6RoomAttemptStartedAt = pNowRt
    endif
    float pAttemptElapsed = PrestonSceneCheckSeconds
    if s6RoomAttemptStartedAt > 0.0
        pAttemptElapsed = pNowRt - s6RoomAttemptStartedAt
    endif
    bool pPhase1Elapsed = False
    if s6RoomScenePhase1
        if pNowRt < s6RoomPhase1At
            s6RoomPhase1At = pNowRt
        elseif (pNowRt - s6RoomPhase1At) >= (PrestonSceneCheckSeconds - 0.05)
            pPhase1Elapsed = True
        endif
    endif
    if S6PrestonRoomScene == None
        RestartOrFailS6RoomScene(False, "scene_inactive")
    elseif !S6PrestonRoomScene.IsPlaying()
        if pAttemptElapsed < (PrestonSceneCheckSeconds - 0.05)
            StartTimer(PrestonSceneCheckSeconds - pAttemptElapsed, 5)
        else
            RestartOrFailS6RoomScene(False, "scene_inactive")
        endif
    elseif (pPhase1Elapsed || s6RoomSceneTicks >= PrestonSceneMaxWaitChecks) && pAttemptElapsed >= (PrestonSceneCheckSeconds - 0.05)
        RestartOrFailS6RoomScene(False, "dialogue_menu_timeout")
    elseif pPhase1Elapsed || s6RoomSceneTicks >= PrestonSceneMaxWaitChecks
        StartTimer(PrestonSceneCheckSeconds - pAttemptElapsed, 5)
    else
        StartTimer(PrestonSceneCheckSeconds, 5)
    endif
EndFunction
