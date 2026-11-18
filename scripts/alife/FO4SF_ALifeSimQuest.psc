Scriptname FO4SF_ALifeSimQuest extends Quest
{Standalone multi-squad A-Life for Starfield (docs/alife/MODDER-GUIDE.md). Up to 16 abstract squads walk an offline
 node graph (NodeX/NodeY/NodeZ, EdgeU/EdgeV/EdgeLen, Dijkstra routes), garrison smart-terrain nodes (NodeCap), meet
 hostile squads offline (FactionRelationsFlat, FactionPower) and capture bases and checkpoints. A squad within the
 online radius of the player (OnlineRadiusGlobal, 450 m by default) in the target exterior world is placed as real
 actors that walk between nodes by linked ref on a pooled waymarker; beyond OfflineDespawnRadiusM (620 m), or when the
 player leaves that world, its survivors are counted and it resumes offline. Bases (NodeSpawnFaction >= 0) spawn
 squads for their current owner up to MaxSquadsGlobal. Settings -> Gameplay options OptEnabled, OptMaxSquads and
 OptNotifications drive the globals. Log: Logs/Script/User/StarfieldALife.0.log, lines
 "ALIFE_MOD rt=<s> step=<event> key=value ...". Modder API: FO4SF_ALifeAPI.}

; Long notes stay in ";" comments (tests/test_papyrus_strings.py keeps every doc comment and string under 3,072 bytes).
; Squad states: 0 empty, 1 garrisoned, 2 marching_offline, 3 online_3d, 4 in_combat_offline, 5 dead_cooldown.
; Orders: 0 patrol, 1 reinforce, 2 raid. NodeKind: 0 relay, 1 base, 2 checkpoint, 3 lair, 4 resource.
; FactionRelationsFlat[a * F + b]: 1 ally, 0 neutral, -1 enemy. All coordinates are in metres; merged world position
; = local node position + (MergeOffsetX, MergeOffsetY).

; ---------------------------------------------------------------- records (the A-Life plugin writer fills these)

ActorBase[] Property SquadTemplates Auto Const Mandatory
{One NPC_ squad template per faction, by faction index.}
Faction[] Property SquadFactions Auto Const Mandatory
{One FACT per faction, by faction index; each placed member's group faction.}
int[] Property FactionSquadSize Auto Const Mandatory
float[] Property FactionPower Auto Const Mandatory
int[] Property FactionRelationsFlat Auto Const Mandatory
ObjectReference[] Property Waymarkers Auto Const Mandatory
{Pooled persistent XMarkerHeading refs in the target world; one per online squad.}
float[] Property NodeX Auto Const Mandatory
float[] Property NodeY Auto Const Mandatory
float[] Property NodeZ Auto Const Mandatory
int[] Property NodeCap Auto Const Mandatory
int[] Property NodeKind Auto Const Mandatory
int[] Property NodeInitialOwner Auto Const Mandatory
int[] Property NodeSpawnFaction Auto Const Mandatory
int[] Property EdgeU Auto Const Mandatory
int[] Property EdgeV Auto Const Mandatory
float[] Property EdgeLen Auto Const Mandatory
float Property MergeOffsetX Auto Const
float Property MergeOffsetY Auto Const
float Property OnlineSpawnRadiusM = 450.0 Auto Const
float Property OfflineDespawnRadiusM = 620.0 Auto Const
float Property OfflineSpeedMps = 1.35 Auto Const
float Property TickIntervalS = 2.0 Auto Const
int Property MaxActiveSquads = 8 Auto Const
float Property RespawnCooldownS = 120.0 Auto Const
GlobalVariable Property SimEnabledGlobal Auto Const Mandatory
GlobalVariable Property OnlineRadiusGlobal Auto Const Mandatory
GlobalVariable Property MaxSquadsGlobal Auto Const Mandatory
GlobalVariable Property NotificationsGlobal Auto Const Mandatory
GameplayOption Property OptEnabled Auto Const
GameplayOption Property OptMaxSquads Auto Const
GameplayOption Property OptNotifications Auto Const
Potion Property FieldTransponder Auto Const
{The Field Transponder aid item; the player is given one and it is returned after each use.}

; ---------------------------------------------------------------- constants

string LOG_NAME = "StarfieldALife"
int TIMER_TICK = 1
int TIMER_TRANSPONDER = 2
int MAX_SQ = 16
int MAX_MEM = 8
int ST_EMPTY = 0
int ST_GARRISON = 1
int ST_MARCH = 2
int ST_ONLINE = 3
int ST_COMBAT = 4
int ST_DEAD = 5
int ORD_PATROL = 0
int ORD_REINFORCE = 1
int ORD_RAID = 2
float ARRIVE_M = 15.0
float ENCOUNTER_M = 15.0
float DWELL_S = 45.0
float DWELL_JITTER_S = 30.0
float STUCK_S = 60.0
float STUCK_MIN_M = 2.0
float STUCK_NEAR_PLAYER_M = 35.0
int STUCK_SKIP_AFTER = 3
float REPLACE_M = 30.0
float NOTIFY_GAP_S = 20.0
float ATTRITION = 0.15
float MIN_LOSS = 0.05
float ROUT_FRACTION = 0.25
int SUMMARY_EVERY = 30

; ---------------------------------------------------------------- state

bool inited = False
bool graphValid = False
bool ticking = False
bool worldWarned = False
int nodeCount = 0
int edgeCount = 0
int factionCount = 0
int tickCount = 0
float lastTickT = 0.0
float lastNotifyT = -1000.0
int spawnCursor = 0
WorldSpace simWorld
int[] nodeOwner
float[] baseNextSpawn
int[] sqFaction
int[] sqState
int[] sqCurr
int[] sqGoal
int[] sqEdgeU
int[] sqEdgeV
float[] sqEdgeLen
float[] sqProg
int[] sqMembers
float[] sqStrength
int[] sqOrder
float[] sqTimer
float[] sqReplenT
int[] sqMarker
float[] sqStuckX
float[] sqStuckY
float[] sqStuckT
int[] sqStuckCount
bool[] sqWarned
Actor[] sqActors
int[] markerOwner
int statSpawns = 0
int statBattles = 0
int statCaptures = 0
int statMaterialized = 0
int statDematerialized = 0
int statDefeated = 0
int statEdges = 0

; ---------------------------------------------------------------- lifecycle

Event OnQuestInit()
    InitOnce("quest_init")
EndEvent

Event OnQuestStarted()
    InitOnce("quest_started")
EndEvent

Function InitOnce(string why)
    ; idempotent: OnQuestInit and OnQuestStarted may both arrive; the flag is set before any external call
    if inited
        return
    endif
    inited = True
    AllocateState()
    graphValid = GraphOk()
    float now = Utility.GetCurrentRealTime()
    int n = 0
    while n < nodeCount
        int owner = NodeInitialOwner[n]
        if owner < -1 || owner >= factionCount
            owner = -1
        endif
        nodeOwner[n] = owner
        baseNextSpawn[n] = now
        n += 1
    endwhile
    lastTickT = now
    RegisterHooks()
    SyncOptions(why)
    GiveTransponder()
    Trace("step=init why=" + why + " valid=" + graphValid + " nodes=" + nodeCount + " edges=" + edgeCount + " factions=" + factionCount + " pool=" + PoolSize() + " max_squads=" + SquadLimit() + " online_m=" + OnlineRadius() + " offline_m=" + DespawnRadius() + " speed=" + OfflineSpeedMps + " tick_s=" + TickSeconds() + " offset=" + MergeOffsetX + "," + MergeOffsetY)
    StartTimer(TickSeconds(), TIMER_TICK)
EndFunction

Function AllocateState()
    nodeOwner = new int[128]
    baseNextSpawn = new float[128]
    sqFaction = new int[16]
    sqState = new int[16]
    sqCurr = new int[16]
    sqGoal = new int[16]
    sqEdgeU = new int[16]
    sqEdgeV = new int[16]
    sqEdgeLen = new float[16]
    sqProg = new float[16]
    sqMembers = new int[16]
    sqStrength = new float[16]
    sqOrder = new int[16]
    sqTimer = new float[16]
    sqReplenT = new float[16]
    sqMarker = new int[16]
    sqStuckX = new float[16]
    sqStuckY = new float[16]
    sqStuckT = new float[16]
    sqStuckCount = new int[16]
    sqWarned = new bool[16]
    sqActors = new Actor[128]
    markerOwner = new int[16]
    int i = 0
    while i < MAX_SQ
        sqMarker[i] = -1
        sqEdgeV[i] = -1
        markerOwner[i] = -1
        i += 1
    endwhile
EndFunction

bool Function GraphOk()
    string why = ""
    if NodeX == None || NodeY == None || NodeZ == None || NodeCap == None || NodeKind == None || NodeInitialOwner == None || NodeSpawnFaction == None
        why = "node_arrays_missing"
    elseif EdgeU == None || EdgeV == None || EdgeLen == None
        why = "edge_arrays_missing"
    elseif SquadTemplates == None || SquadFactions == None || FactionSquadSize == None || FactionPower == None || FactionRelationsFlat == None
        why = "faction_arrays_missing"
    elseif Waymarkers == None || Waymarkers.Length < 1
        why = "no_waymarkers"
    endif
    if why == ""
        int n = NodeX.Length
        int e = EdgeU.Length
        int f = SquadFactions.Length
        if n < 2 || n > 128 || NodeY.Length != n || NodeZ.Length != n || NodeCap.Length != n || NodeKind.Length != n || NodeInitialOwner.Length != n || NodeSpawnFaction.Length != n
            why = "node_lengths"
        elseif e < 1 || e > 128 || EdgeV.Length != e || EdgeLen.Length != e
            why = "edge_lengths"
        elseif f < 1 || f > 8 || SquadTemplates.Length != f || FactionSquadSize.Length != f || FactionPower.Length != f || FactionRelationsFlat.Length != f * f
            why = "faction_lengths"
        else
            int k = 0
            while k < e && why == ""
                if EdgeU[k] < 0 || EdgeU[k] >= n || EdgeV[k] < 0 || EdgeV[k] >= n || EdgeLen[k] < 0.0
                    why = "edge_index edge=" + k
                endif
                k += 1
            endwhile
        endif
        if why == ""
            nodeCount = n
            edgeCount = e
            factionCount = f
            return True
        endif
    endif
    nodeCount = 0
    edgeCount = 0
    factionCount = 0
    Trace("step=error reason=graph_refused detail=" + why)
    return False
EndFunction

Function RegisterHooks()
    RegisterForGameplayOptionChangedEvent()
    Actor player = Game.GetPlayer()
    if player != None
        RegisterForRemoteEvent(player, "OnPlayerLoadGame")
    endif
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    if !inited
        InitOnce("load_game")
        return
    endif
    ; GetCurrentRealTime restarts with every game session: shift every stored timestamp onto the new clock
    float now = Utility.GetCurrentRealTime()
    float shift = now - lastTickT
    RebaseTimes(shift)
    lastTickT = now
    simWorld = None
    RegisterHooks()
    SyncOptions("load_game")
    Trace("step=load_game shift_s=" + shift + " " + Summary())
    CancelTimer(TIMER_TICK)
    StartTimer(TickSeconds(), TIMER_TICK)
EndEvent

Function RebaseTimes(float shift)
    lastNotifyT += shift
    int n = 0
    while n < nodeCount
        baseNextSpawn[n] = baseNextSpawn[n] + shift
        n += 1
    endwhile
    int i = 0
    while i < MAX_SQ
        sqTimer[i] = sqTimer[i] + shift
        sqReplenT[i] = sqReplenT[i] + shift
        sqStuckT[i] = sqStuckT[i] + shift
        i += 1
    endwhile
EndFunction

; ---------------------------------------------------------------- gameplay options

Function SyncOptions(string why)
    if OptEnabled != None && SimEnabledGlobal != None
        SimEnabledGlobal.SetValue(OptEnabled.GetValue())
    endif
    if OptMaxSquads != None && MaxSquadsGlobal != None
        float v = OptMaxSquads.GetValue()
        if v < 1.0
            v = 1.0
        elseif v > 16.0
            v = 16.0
        endif
        MaxSquadsGlobal.SetValue(v)
    endif
    if OptNotifications != None && NotificationsGlobal != None
        NotificationsGlobal.SetValue(OptNotifications.GetValue())
    endif
    Trace("step=options why=" + why + " enabled=" + SimOn() + " max_squads=" + SquadLimit() + " notifications=" + NotifyOn() + " online_m=" + OnlineRadius())
EndFunction

Event OnGameplayOptionChanged(GameplayOption[] aChangedOptions)
    if aChangedOptions == None
        return
    endif
    bool ours = False
    if OptEnabled != None && aChangedOptions.Find(OptEnabled) >= 0
        ours = True
    endif
    if OptMaxSquads != None && aChangedOptions.Find(OptMaxSquads) >= 0
        ours = True
    endif
    if OptNotifications != None && aChangedOptions.Find(OptNotifications) >= 0
        ours = True
    endif
    if ours
        SyncOptions("gpof_menu")
        GameplayOption.NotifyGameplayOptionUpdateFinished()
    endif
EndEvent

bool Function SimOn()
    return SimEnabledGlobal == None || SimEnabledGlobal.GetValue() != 0.0
EndFunction

bool Function NotifyOn()
    return NotificationsGlobal != None && NotificationsGlobal.GetValue() != 0.0
EndFunction

int Function SquadLimit()
    int lim = MaxActiveSquads
    if MaxSquadsGlobal != None && MaxSquadsGlobal.GetValue() > 0.0
        lim = MaxSquadsGlobal.GetValueInt()
    endif
    if lim < 0
        lim = 0
    elseif lim > MAX_SQ
        lim = MAX_SQ
    endif
    return lim
EndFunction

float Function OnlineRadius()
    if OnlineRadiusGlobal != None && OnlineRadiusGlobal.GetValue() > 0.0
        return OnlineRadiusGlobal.GetValue()
    endif
    return OnlineSpawnRadiusM
EndFunction

float Function DespawnRadius()
    ; hysteresis: never closer than 50 m beyond the online radius
    float r = OfflineDespawnRadiusM
    float minR = OnlineRadius() + 50.0
    if r < minR
        r = minR
    endif
    return r
EndFunction

float Function TickSeconds()
    if TickIntervalS < 0.5
        return 0.5
    endif
    return TickIntervalS
EndFunction

int Function PoolSize()
    if Waymarkers == None
        return 0
    endif
    if Waymarkers.Length > MAX_SQ
        return MAX_SQ
    endif
    return Waymarkers.Length
EndFunction

; ---------------------------------------------------------------- main loop

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_TICK
        Tick()
        StartTimer(TickSeconds(), TIMER_TICK)
    elseif aiTimerID == TIMER_TRANSPONDER
        GiveTransponder()
    endif
EndEvent

Function Tick()
    if ticking || !graphValid
        return
    endif
    ticking = True
    float now = Utility.GetCurrentRealTime()
    float dt = now - lastTickT
    float maxDt = TickSeconds() * 3.0
    if dt < 0.0
        dt = 0.0
    elseif dt > maxDt
        dt = maxDt
    endif
    lastTickT = now
    tickCount += 1
    if !SimOn()
        if OnlineCount() > 0
            DematerializeAll("disabled", now)
        endif
        ticking = False
        return
    endif
    Actor player = Game.GetPlayer()
    bool inWorld = PlayerInSimWorld(player)
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float onR = OnlineRadius()
    ExpireCooldowns(now)
    SpawnFromBases(now)
    int i = 0
    while i < MAX_SQ
        int st = sqState[i]
        if st == ST_ONLINE
            UpdateOnline(i, player, inWorld, now)
        elseif st == ST_MARCH
            AdvanceOffline(i, dt, now)
        elseif st == ST_GARRISON
            GarrisonThink(i, now)
        endif
        st = sqState[i]
        if inWorld && (st == ST_GARRISON || st == ST_MARCH || st == ST_COMBAT)
            if Dist2(SquadWX(i), SquadWY(i), px, py) <= onR
                Materialize(i, player, now)
            endif
        endif
        i += 1
    endwhile
    ResolveEncounters(dt, now)
    if tickCount % SUMMARY_EVERY == 0
        Trace("step=tick " + Summary())
    endif
    ticking = False
EndFunction

bool Function PlayerInSimWorld(Actor player)
    if player == None || player.IsInInterior()
        return False
    endif
    WorldSpace pw = player.GetWorldSpace()
    if pw == None
        return False
    endif
    if simWorld == None && Waymarkers[0] != None
        simWorld = Waymarkers[0].GetWorldSpace()
    endif
    if simWorld == None
        if !worldWarned
            worldWarned = True
            Trace("step=warn reason=sim_world_unknown marker=" + Id(Waymarkers[0]))
        endif
        return False
    endif
    return pw == simWorld
EndFunction

Function ExpireCooldowns(float now)
    int i = 0
    while i < MAX_SQ
        if sqState[i] == ST_DEAD && now >= sqTimer[i]
            sqState[i] = ST_EMPTY
        endif
        i += 1
    endwhile
EndFunction

; ---------------------------------------------------------------- spawning

Function SpawnFromBases(float now)
    if ActiveCount() >= SquadLimit()
        return
    endif
    int tries = 0
    bool done = False
    while tries < nodeCount && !done
        int n = (spawnCursor + tries) % nodeCount
        int owner = nodeOwner[n]
        if NodeSpawnFaction[n] >= 0 && owner >= 0 && owner < factionCount && now >= baseNextSpawn[n]
            baseNextSpawn[n] = now + RespawnCooldownS
            SpawnSquad(owner, n, "base", now)
            spawnCursor = (n + 1) % nodeCount
            done = True
        endif
        tries += 1
    endwhile
EndFunction

int Function SpawnSquad(int f, int n, string why, float now)
    if f < 0 || f >= factionCount || n < 0 || n >= nodeCount
        Trace("step=warn reason=spawn_refused faction=" + f + " node=" + n + " why=" + why)
        return -1
    endif
    int i = FreeSlot()
    if i < 0
        Trace("step=warn reason=no_free_slot faction=" + f + " node=" + n + " why=" + why)
        return -1
    endif
    int size = FactionSize(f)
    sqFaction[i] = f
    sqState[i] = ST_GARRISON
    sqCurr[i] = n
    sqGoal[i] = n
    sqEdgeU[i] = n
    sqEdgeV[i] = -1
    sqEdgeLen[i] = 0.0
    sqProg[i] = 0.0
    sqMembers[i] = size
    sqStrength[i] = (size as float) * Power(f)
    sqOrder[i] = ORD_PATROL
    sqTimer[i] = now + Dwell()
    sqReplenT[i] = now + RespawnCooldownS * 0.25
    sqMarker[i] = -1
    sqStuckCount[i] = 0
    sqWarned[i] = False
    statSpawns += 1
    Trace("step=squad_spawn squad=" + i + " faction=" + f + " node=" + n + " members=" + size + " strength=" + sqStrength[i] + " why=" + why + " active=" + ActiveCount())
    return i
EndFunction

int Function FreeSlot()
    int i = 0
    while i < MAX_SQ
        if sqState[i] == ST_EMPTY
            return i
        endif
        i += 1
    endwhile
    return -1
EndFunction

int Function FactionSize(int f)
    int size = 4
    if f >= 0 && f < factionCount
        size = FactionSquadSize[f]
    endif
    if size < 1
        size = 1
    elseif size > MAX_MEM
        size = MAX_MEM
    endif
    return size
EndFunction

float Function Power(int f)
    if f >= 0 && f < factionCount && FactionPower[f] > 0.0
        return FactionPower[f]
    endif
    return 1.0
EndFunction

int Function Relation(int a, int b)
    if a < 0 || b < 0 || a >= factionCount || b >= factionCount
        return 0
    endif
    return FactionRelationsFlat[a * factionCount + b]
EndFunction

float Function Dwell()
    return DWELL_S + Utility.RandomFloat(0.0, DWELL_JITTER_S)
EndFunction

; ---------------------------------------------------------------- offline graph movement and orders

Function GarrisonThink(int i, float now)
    int f = sqFaction[i]
    int n = sqCurr[i]
    if NodeSpawnFaction[n] >= 0 && nodeOwner[n] == f && sqMembers[i] < FactionSize(f) && now >= sqReplenT[i]
        sqMembers[i] = sqMembers[i] + 1
        sqStrength[i] = (sqMembers[i] as float) * Power(f)
        sqReplenT[i] = now + RespawnCooldownS * 0.25
        Trace("step=replenish squad=" + i + " faction=" + f + " node=" + n + " members=" + sqMembers[i])
    endif
    if now >= sqTimer[i]
        ChooseOrder(i, now)
    endif
EndFunction

Function ChooseOrder(int i, float now)
    int f = sqFaction[i]
    int cur = sqCurr[i]
    int[] prev = new int[128]
    float[] dist = Distances(cur, prev)
    int raid = -1
    int reinforce = -1
    int patrolCount = 0
    int k = 0
    while k < nodeCount
        if k != cur && dist[k] >= 0.0 && NodeCap[k] > 0
            patrolCount += 1
            int owner = nodeOwner[k]
            bool capturable = NodeKind[k] == 1 || NodeKind[k] == 2
            if (owner >= 0 && Relation(f, owner) < 0) || (owner < 0 && capturable)
                if raid < 0 || dist[k] < dist[raid]
                    raid = k
                endif
            elseif owner == f && Occupancy(k, i) < NodeCap[k]
                if reinforce < 0 || dist[k] < dist[reinforce]
                    reinforce = k
                endif
            endif
        endif
        k += 1
    endwhile
    int roll = Utility.RandomInt(0, 99)
    int goal = -1
    int order = ORD_PATROL
    if raid >= 0 && roll < 40
        goal = raid
        order = ORD_RAID
    elseif reinforce >= 0 && roll < 70
        goal = reinforce
        order = ORD_REINFORCE
    elseif patrolCount > 0
        int pick = Utility.RandomInt(0, patrolCount - 1)
        k = 0
        while k < nodeCount && goal < 0
            if k != cur && dist[k] >= 0.0 && NodeCap[k] > 0
                if pick == 0
                    goal = k
                endif
                pick -= 1
            endif
            k += 1
        endwhile
    endif
    if goal < 0
        sqTimer[i] = now + Dwell()
        return
    endif
    sqGoal[i] = goal
    sqOrder[i] = order
    Trace("step=order squad=" + i + " faction=" + f + " order=" + OrderName(order) + " node=" + cur + " goal=" + goal + " route_m=" + dist[goal] + " owner=" + nodeOwner[goal])
    Depart(i, now)
EndFunction

Function Depart(int i, float now)
    int cur = sqCurr[i]
    int nxt = NextHop(cur, sqGoal[i])
    if nxt < 0
        sqGoal[i] = cur
        Garrison(i, cur, now)
        return
    endif
    sqEdgeU[i] = cur
    sqEdgeV[i] = nxt
    sqEdgeLen[i] = EdgeBetween(cur, nxt)
    sqProg[i] = 0.0
    if sqState[i] == ST_ONLINE
        RetargetOnline(i, nxt, now)
    else
        sqState[i] = ST_MARCH
    endif
EndFunction

Function AdvanceOffline(int i, float dt, float now)
    float walk = OfflineSpeedMps * dt
    int hops = 0
    while walk > 0.0 && sqState[i] == ST_MARCH && hops < 8
        float remain = sqEdgeLen[i] - sqProg[i]
        if walk < remain
            sqProg[i] = sqProg[i] + walk
            walk = 0.0
        else
            walk -= remain
            ArriveAt(i, sqEdgeV[i], now)
        endif
        hops += 1
    endwhile
EndFunction

Function ArriveAt(int i, int n, float now)
    sqCurr[i] = n
    sqEdgeU[i] = n
    sqEdgeV[i] = -1
    sqProg[i] = 0.0
    sqEdgeLen[i] = 0.0
    statEdges += 1
    Trace("step=node_arrive squad=" + i + " faction=" + sqFaction[i] + " node=" + n + " goal=" + sqGoal[i] + " state=" + StateName(sqState[i]))
    if n != sqGoal[i]
        Depart(i, now)
        return
    endif
    if NodeCap[n] > 0 && Occupancy(n, i) < NodeCap[n]
        Garrison(i, n, now)
        return
    endif
    ; full garrison or road relay: pass through to the nearest node with room
    int alt = NearestFree(n, i)
    if alt >= 0
        Trace("step=reroute squad=" + i + " faction=" + sqFaction[i] + " node=" + n + " goal=" + alt + " cap=" + NodeCap[n])
        sqGoal[i] = alt
        Depart(i, now)
    else
        Garrison(i, n, now)
    endif
EndFunction

Function Garrison(int i, int n, float now)
    if sqState[i] != ST_ONLINE
        sqState[i] = ST_GARRISON
    endif
    sqTimer[i] = now + Dwell()
    Trace("step=garrison squad=" + i + " faction=" + sqFaction[i] + " node=" + n + " occupied=" + Occupancy(n, i) + " cap=" + NodeCap[n] + " online=" + (sqState[i] == ST_ONLINE))
    TryCapture(i, n, now)
EndFunction

int Function Occupancy(int n, int exclude)
    int c = 0
    int j = 0
    while j < MAX_SQ
        int st = sqState[j]
        if j != exclude && (st == ST_GARRISON || st == ST_COMBAT || st == ST_ONLINE) && sqEdgeV[j] < 0 && sqCurr[j] == n
            c += 1
        endif
        j += 1
    endwhile
    return c
EndFunction

int Function NearestFree(int from, int i)
    int f = sqFaction[i]
    int[] prev = new int[128]
    float[] dist = Distances(from, prev)
    int best = -1
    int k = 0
    while k < nodeCount
        if k != from && NodeCap[k] > 0 && dist[k] >= 0.0 && Occupancy(k, i) < NodeCap[k]
            int owner = nodeOwner[k]
            if !(owner >= 0 && Relation(f, owner) < 0)
                if best < 0 || dist[k] < dist[best]
                    best = k
                endif
            endif
        endif
        k += 1
    endwhile
    return best
EndFunction

Function TryCapture(int i, int n, float now)
    int f = sqFaction[i]
    int kind = NodeKind[n]
    if (kind != 1 && kind != 2) || nodeOwner[n] == f || HostilePresent(n, f)
        return
    endif
    int old = nodeOwner[n]
    nodeOwner[n] = f
    if NodeSpawnFaction[n] >= 0
        baseNextSpawn[n] = now + RespawnCooldownS
    endif
    statCaptures += 1
    Trace("step=capture squad=" + i + " faction=" + f + " node=" + n + " kind=" + KindName(kind) + " owner_from=" + old + " owner_to=" + f)
    Notify("A-Life: faction " + f + " captured " + KindName(kind) + " " + n, now)
EndFunction

bool Function HostilePresent(int n, int f)
    int j = 0
    while j < MAX_SQ
        int st = sqState[j]
        if (st == ST_GARRISON || st == ST_MARCH || st == ST_COMBAT || st == ST_ONLINE) && NodeOf(j) == n && Relation(f, sqFaction[j]) < 0
            return True
        endif
        j += 1
    endwhile
    return False
EndFunction

int Function NodeOf(int i)
    ; the node a squad stands on, or -1 while it is between nodes
    if sqEdgeV[i] < 0
        return sqCurr[i]
    endif
    if sqProg[i] <= 0.5
        return sqEdgeU[i]
    endif
    if sqProg[i] >= sqEdgeLen[i] - 0.5
        return sqEdgeV[i]
    endif
    return -1
EndFunction

; ---------------------------------------------------------------- offline encounters

Function ResolveEncounters(float dt, float now)
    bool[] engaged = new bool[16]
    int i = 0
    while i < MAX_SQ
        if IsOffline(i)
            int j = i + 1
            while j < MAX_SQ && IsOffline(i)
                if IsOffline(j) && Relation(sqFaction[i], sqFaction[j]) < 0 && Meets(i, j)
                    if sqState[i] != ST_COMBAT || sqState[j] != ST_COMBAT
                        statBattles += 1
                        Trace("step=battle squad=" + i + " faction=" + sqFaction[i] + " foe=" + j + " foe_faction=" + sqFaction[j] + " node=" + NodeOf(i) + " strength=" + sqStrength[i] + " foe_strength=" + sqStrength[j])
                    endif
                    sqState[i] = ST_COMBAT
                    sqState[j] = ST_COMBAT
                    engaged[i] = True
                    engaged[j] = True
                    if dt > 0.0
                        Fight(i, j, dt, now)
                    endif
                endif
                j += 1
            endwhile
        endif
        i += 1
    endwhile
    i = 0
    while i < MAX_SQ
        if sqState[i] == ST_COMBAT && !engaged[i]
            if sqEdgeV[i] >= 0
                sqState[i] = ST_MARCH
            else
                sqState[i] = ST_GARRISON
            endif
            Trace("step=battle_end squad=" + i + " faction=" + sqFaction[i] + " winner=-1 reason=disengaged members=" + sqMembers[i])
            if sqEdgeV[i] < 0
                TryCapture(i, sqCurr[i], now)
            endif
        endif
        i += 1
    endwhile
EndFunction

bool Function IsOffline(int i)
    int st = sqState[i]
    return st == ST_GARRISON || st == ST_MARCH || st == ST_COMBAT
EndFunction

bool Function Meets(int i, int j)
    int ni = NodeOf(i)
    if ni >= 0 && ni == NodeOf(j)
        return True
    endif
    if sqEdgeV[i] < 0 || sqEdgeV[j] < 0
        return False
    endif
    if sqEdgeU[i] == sqEdgeU[j] && sqEdgeV[i] == sqEdgeV[j]
        return Math.abs(sqProg[i] - sqProg[j]) <= ENCOUNTER_M
    endif
    if sqEdgeU[i] == sqEdgeV[j] && sqEdgeV[i] == sqEdgeU[j]
        return Math.abs(sqProg[i] - (sqEdgeLen[j] - sqProg[j])) <= ENCOUNTER_M
    endif
    return False
EndFunction

Function Fight(int i, int j, float dt, float now)
    ; attrition normalised to 2 s ticks: each side loses ATTRITION of the other's strength (randomised +-20%)
    int fi = sqFaction[i]
    int fj = sqFaction[j]
    float pi = Power(fi)
    float pj = Power(fj)
    float k = dt / 2.0
    float li = ATTRITION * sqStrength[j] * k * Utility.RandomFloat(0.8, 1.2)
    float lj = ATTRITION * sqStrength[i] * k * Utility.RandomFloat(0.8, 1.2)
    if li < MIN_LOSS * pi * k
        li = MIN_LOSS * pi * k
    endif
    if lj < MIN_LOSS * pj * k
        lj = MIN_LOSS * pj * k
    endif
    sqStrength[i] = sqStrength[i] - li
    sqStrength[j] = sqStrength[j] - lj
    sqMembers[i] = MembersFor(sqStrength[i], pi)
    sqMembers[j] = MembersFor(sqStrength[j], pj)
    bool deadI = sqStrength[i] < ROUT_FRACTION * pi
    bool deadJ = sqStrength[j] < ROUT_FRACTION * pj
    int node = NodeOf(i)
    if deadI && deadJ
        Trace("step=battle_end squad=" + i + " foe=" + j + " winner=-1 loser=both node=" + node)
        DefeatSquad(i, -1, "battle", now)
        DefeatSquad(j, -1, "battle", now)
    elseif deadJ
        Trace("step=battle_end squad=" + i + " faction=" + fi + " winner=" + i + " loser=" + j + " node=" + node + " members=" + sqMembers[i])
        DefeatSquad(j, i, "battle", now)
    elseif deadI
        Trace("step=battle_end squad=" + j + " faction=" + fj + " winner=" + j + " loser=" + i + " node=" + node + " members=" + sqMembers[j])
        DefeatSquad(i, j, "battle", now)
    endif
EndFunction

int Function MembersFor(float strength, float power)
    if strength <= 0.0
        return 0
    endif
    int m = Math.Ceiling(strength / power)
    if m > MAX_MEM
        m = MAX_MEM
    endif
    return m
EndFunction

Function DefeatSquad(int i, int winner, string why, float now)
    int f = sqFaction[i]
    int node = NodeOf(i)
    ClearActors(i)
    ReleaseMarker(i)
    sqState[i] = ST_DEAD
    sqMembers[i] = 0
    sqStrength[i] = 0.0
    sqEdgeV[i] = -1
    sqTimer[i] = now + RespawnCooldownS
    statDefeated += 1
    Trace("step=squad_defeated squad=" + i + " faction=" + f + " node=" + node + " winner=" + winner + " why=" + why + " cooldown_s=" + RespawnCooldownS)
    Notify("A-Life: a faction " + f + " squad was defeated", now)
EndFunction

; ---------------------------------------------------------------- online 3D bubble

Function Materialize(int i, Actor player, float now)
    int f = sqFaction[i]
    ActorBase tpl = SquadTemplates[f]
    if tpl == None
        if !sqWarned[i]
            sqWarned[i] = True
            Trace("step=error reason=no_template squad=" + i + " faction=" + f)
        endif
        return
    endif
    int m = AcquireMarker(i)
    if m < 0
        if !sqWarned[i]
            sqWarned[i] = True
            Trace("step=warn reason=marker_pool_full squad=" + i + " pool=" + PoolSize())
        endif
        return
    endif
    sqWarned[i] = False
    string fromState = StateName(sqState[i])
    ObjectReference mk = Waymarkers[m]
    float wx = SquadWX(i)
    float wy = SquadWY(i)
    PlaceMarker(mk, wx, wy, SquadZ(i))
    Faction fac = SquadFactions[f]
    int count = sqMembers[i]
    if count < 1
        count = 1
    elseif count > MAX_MEM
        count = MAX_MEM
    endif
    int placed = 0
    int k = 0
    while k < count
        Actor a = mk.PlaceActorAtMe(tpl, 4, None, False, False, True, None, True)
        if a != None
            a.MoveTo(mk, ((k % 4) as float) * 1.5 - 2.25, ((k / 4) as float) * -1.5 - 1.5, 0.0, False, False)
            if fac != None
                a.SetGroupFaction(fac)
            endif
            sqActors[i * MAX_MEM + k] = a
            placed += 1
        endif
        k += 1
    endwhile
    if placed == 0
        ReleaseMarker(i)
        Trace("step=error reason=place_failed squad=" + i + " faction=" + f)
        return
    endif
    sqState[i] = ST_ONLINE
    sqMembers[i] = placed
    int target = sqEdgeV[i]
    if target < 0
        target = sqCurr[i]
    endif
    RetargetOnline(i, target, now)
    sqStuckCount[i] = 0
    statMaterialized += 1
    Trace("step=materialize squad=" + i + " faction=" + f + " members=" + placed + " node=" + sqCurr[i] + " target=" + target + " from=" + fromState + " pos=" + wx + "," + wy + " player_m=" + Dist2(wx, wy, player.GetPositionX(), player.GetPositionY()) + " marker=" + m)
EndFunction

Function UpdateOnline(int i, Actor player, bool inWorld, float now)
    int alive = AliveCount(i)
    if alive == 0
        DefeatSquad(i, -1, "wiped_online", now)
        return
    endif
    Actor leader = Leader(i)
    float lx = leader.GetPositionX()
    float ly = leader.GetPositionY()
    float pd = Dist2(lx, ly, player.GetPositionX(), player.GetPositionY())
    if !inWorld
        Dematerialize(i, "player_left_world", now)
        return
    endif
    if pd > DespawnRadius()
        Dematerialize(i, "player_far", now)
        return
    endif
    int f = sqFaction[i]
    if alive < sqMembers[i]
        sqMembers[i] = alive
        sqStrength[i] = (alive as float) * Power(f)
    endif
    int target = sqEdgeV[i]
    if target < 0
        if now >= sqTimer[i]
            ChooseOrder(i, now)
        endif
        return
    endif
    float tx = NodeX[target] + MergeOffsetX
    float ty = NodeY[target] + MergeOffsetY
    sqProg[i] = ProjectProgress(i, lx, ly)
    if Dist2(lx, ly, tx, ty) <= ARRIVE_M
        sqStuckCount[i] = 0
        ArriveAt(i, target, now)
        return
    endif
    ; a persistent marker can read its editor spot again when its cell reloads: place it again when found far off
    ObjectReference mk = Waymarkers[sqMarker[i]]
    if Dist2(mk.GetPositionX(), mk.GetPositionY(), tx, ty) > REPLACE_M
        Trace("step=marker_replace squad=" + i + " target=" + target + " marker=" + sqMarker[i])
        RetargetOnline(i, target, now)
        return
    endif
    if leader.IsInCombat()
        sqStuckT[i] = now
    elseif Dist2(lx, ly, sqStuckX[i], sqStuckY[i]) >= STUCK_MIN_M
        sqStuckX[i] = lx
        sqStuckY[i] = ly
        sqStuckT[i] = now
    elseif now - sqStuckT[i] >= STUCK_S && pd > STUCK_NEAR_PLAYER_M
        sqStuckCount[i] = sqStuckCount[i] + 1
        bool skip = sqStuckCount[i] >= STUCK_SKIP_AFTER
        Trace("step=stuck_relink squad=" + i + " target=" + target + " count=" + sqStuckCount[i] + " skip=" + skip + " leader_target_m=" + Dist2(lx, ly, tx, ty))
        if skip
            sqStuckCount[i] = 0
            ArriveAt(i, target, now)
        else
            RetargetOnline(i, target, now)
        endif
    endif
EndFunction

Function RetargetOnline(int i, int node, float now)
    int m = sqMarker[i]
    if m < 0
        return
    endif
    ObjectReference mk = Waymarkers[m]
    PlaceMarker(mk, NodeX[node] + MergeOffsetX, NodeY[node] + MergeOffsetY, NodeZ[node])
    LinkSquad(i, mk)
    Actor leader = Leader(i)
    if leader != None
        sqStuckX[i] = leader.GetPositionX()
        sqStuckY[i] = leader.GetPositionY()
    endif
    sqStuckT[i] = now
EndFunction

Function Dematerialize(int i, string why, float now)
    int f = sqFaction[i]
    Actor leader = Leader(i)
    if leader != None && sqEdgeV[i] >= 0
        sqProg[i] = ProjectProgress(i, leader.GetPositionX(), leader.GetPositionY())
    endif
    int alive = ClearActors(i)
    ReleaseMarker(i)
    statDematerialized += 1
    if alive <= 0
        DefeatSquad(i, -1, "wiped_online", now)
        return
    endif
    sqMembers[i] = alive
    sqStrength[i] = (alive as float) * Power(f)
    if sqEdgeV[i] >= 0
        sqState[i] = ST_MARCH
    else
        sqState[i] = ST_GARRISON
    endif
    Trace("step=dematerialize squad=" + i + " faction=" + f + " members=" + alive + " why=" + why + " node=" + sqCurr[i] + " next=" + sqEdgeV[i] + " prog_m=" + sqProg[i])
EndFunction

Function DematerializeAll(string why, float now)
    int i = 0
    while i < MAX_SQ
        if sqState[i] == ST_ONLINE
            Dematerialize(i, why, now)
        endif
        i += 1
    endwhile
EndFunction

float Function ProjectProgress(int i, float lx, float ly)
    int u = sqEdgeU[i]
    int v = sqEdgeV[i]
    if v < 0
        return 0.0
    endif
    float ax = NodeX[u] + MergeOffsetX
    float ay = NodeY[u] + MergeOffsetY
    float dx = NodeX[v] + MergeOffsetX - ax
    float dy = NodeY[v] + MergeOffsetY - ay
    float l2 = dx * dx + dy * dy
    if l2 <= 0.0001
        return 0.0
    endif
    float t = ((lx - ax) * dx + (ly - ay) * dy) / l2
    if t < 0.0
        t = 0.0
    elseif t > 1.0
        t = 1.0
    endif
    return t * sqEdgeLen[i]
EndFunction

Function PlaceMarker(ObjectReference mk, float tx, float ty, float tz)
    ; merged-world placement: MoveTo onto the player with the difference as the offset, then snap to the navmesh
    Actor player = Game.GetPlayer()
    mk.MoveTo(player, tx - player.GetPositionX(), ty - player.GetPositionY(), tz - player.GetPositionZ(), False, False)
    mk.MoveToNearestNavmeshLocation()
EndFunction

Function LinkSquad(int i, ObjectReference target)
    int k = 0
    while k < MAX_MEM
        Actor a = sqActors[i * MAX_MEM + k]
        if a != None && !a.IsDead()
            a.SetLinkedRef(target)
            a.EvaluatePackage()
        endif
        k += 1
    endwhile
EndFunction

Actor Function Leader(int i)
    int k = 0
    while k < MAX_MEM
        Actor a = sqActors[i * MAX_MEM + k]
        if a != None && !a.IsDead()
            return a
        endif
        k += 1
    endwhile
    return None
EndFunction

int Function AliveCount(int i)
    int c = 0
    int k = 0
    while k < MAX_MEM
        Actor a = sqActors[i * MAX_MEM + k]
        if a != None && !a.IsDead()
            c += 1
        endif
        k += 1
    endwhile
    return c
EndFunction

int Function ClearActors(int i)
    ; living members are disabled and deleted; bodies are only flagged for deletion so they unload with their cell
    int alive = 0
    int k = 0
    while k < MAX_MEM
        int idx = i * MAX_MEM + k
        Actor a = sqActors[idx]
        if a != None
            if !a.IsDead()
                alive += 1
                a.SetLinkedRef(None)
                a.DisableNoWait()
            endif
            a.Delete()
            sqActors[idx] = None
        endif
        k += 1
    endwhile
    return alive
EndFunction

int Function AcquireMarker(int i)
    if sqMarker[i] >= 0
        return sqMarker[i]
    endif
    int m = 0
    int pool = PoolSize()
    while m < pool
        if markerOwner[m] < 0 && Waymarkers[m] != None
            markerOwner[m] = i
            sqMarker[i] = m
            return m
        endif
        m += 1
    endwhile
    return -1
EndFunction

Function ReleaseMarker(int i)
    int m = sqMarker[i]
    if m >= 0 && m < MAX_SQ
        markerOwner[m] = -1
    endif
    sqMarker[i] = -1
EndFunction

int Function OnlineCount()
    int c = 0
    int i = 0
    while i < MAX_SQ
        if sqState[i] == ST_ONLINE
            c += 1
        endif
        i += 1
    endwhile
    return c
EndFunction

int Function ActiveCount()
    int c = 0
    int i = 0
    while i < MAX_SQ
        int st = sqState[i]
        if st == ST_GARRISON || st == ST_MARCH || st == ST_ONLINE || st == ST_COMBAT
            c += 1
        endif
        i += 1
    endwhile
    return c
EndFunction

; ---------------------------------------------------------------- positions and routes

float Function SquadX(int i)
    int u = sqEdgeU[i]
    int v = sqEdgeV[i]
    if v < 0 || sqEdgeLen[i] <= 0.0
        return NodeX[sqCurr[i]]
    endif
    return NodeX[u] + (NodeX[v] - NodeX[u]) * (sqProg[i] / sqEdgeLen[i])
EndFunction

float Function SquadY(int i)
    int u = sqEdgeU[i]
    int v = sqEdgeV[i]
    if v < 0 || sqEdgeLen[i] <= 0.0
        return NodeY[sqCurr[i]]
    endif
    return NodeY[u] + (NodeY[v] - NodeY[u]) * (sqProg[i] / sqEdgeLen[i])
EndFunction

float Function SquadZ(int i)
    int u = sqEdgeU[i]
    int v = sqEdgeV[i]
    if v < 0 || sqEdgeLen[i] <= 0.0
        return NodeZ[sqCurr[i]]
    endif
    return NodeZ[u] + (NodeZ[v] - NodeZ[u]) * (sqProg[i] / sqEdgeLen[i])
EndFunction

float Function SquadWX(int i)
    return SquadX(i) + MergeOffsetX
EndFunction

float Function SquadWY(int i)
    return SquadY(i) + MergeOffsetY
EndFunction

float Function EdgeBetween(int u, int v)
    float best = -1.0
    int e = 0
    while e < edgeCount
        if (EdgeU[e] == u && EdgeV[e] == v) || (EdgeU[e] == v && EdgeV[e] == u)
            if best < 0.0 || EdgeLen[e] < best
                best = EdgeLen[e]
            endif
        endif
        e += 1
    endwhile
    if best < 0.0
        best = 0.0
    endif
    return best
EndFunction

float[] Function Distances(int src, int[] prev)
    ; Dijkstra over the property arrays (n <= 128, O(n^2 + n*e)); prev[x] is x's neighbour on the way back to src
    int n = nodeCount
    float[] dist = new float[128]
    bool[] done = new bool[128]
    int i = 0
    while i < n
        dist[i] = -1.0
        prev[i] = -1
        i += 1
    endwhile
    if src < 0 || src >= n
        return dist
    endif
    dist[src] = 0.0
    int rounds = 0
    while rounds < n
        int u = -1
        i = 0
        while i < n
            if !done[i] && dist[i] >= 0.0 && (u < 0 || dist[i] < dist[u])
                u = i
            endif
            i += 1
        endwhile
        if u < 0
            rounds = n
        else
            done[u] = True
            int e = 0
            while e < edgeCount
                int v = -1
                if EdgeU[e] == u
                    v = EdgeV[e]
                elseif EdgeV[e] == u
                    v = EdgeU[e]
                endif
                if v >= 0 && !done[v]
                    float nd = dist[u] + EdgeLen[e]
                    if dist[v] < 0.0 || nd < dist[v]
                        dist[v] = nd
                        prev[v] = u
                    endif
                endif
                e += 1
            endwhile
            rounds += 1
        endif
    endwhile
    return dist
EndFunction

int Function NextHop(int from, int goal)
    ; rooted at the goal, so prev[from] is from's next node toward it
    if from == goal || goal < 0 || goal >= nodeCount
        return -1
    endif
    int[] prev = new int[128]
    float[] dist = Distances(goal, prev)
    if dist[from] < 0.0
        return -1
    endif
    return prev[from]
EndFunction

; ---------------------------------------------------------------- modder API (wrapped by FO4SF_ALifeAPI)

bool Function IsSimRunning()
    return inited && graphValid && SimOn() && IsRunning()
EndFunction

Function SetSimEnabled(bool abEnabled)
    if SimEnabledGlobal != None
        if abEnabled
            SimEnabledGlobal.SetValue(1.0)
        else
            SimEnabledGlobal.SetValue(0.0)
        endif
    endif
    Trace("step=api call=set_enabled enabled=" + abEnabled)
EndFunction

int Function ApiSpawnSquad(int aiFaction, int aiNode)
    int i = SpawnSquad(aiFaction, aiNode, "api", Utility.GetCurrentRealTime())
    Trace("step=api call=spawn faction=" + aiFaction + " node=" + aiNode + " squad=" + i)
    return i
EndFunction

int Function ApiOrderRaid(int aiFaction, int aiTargetNode)
    ; the faction's free squad nearest (by graph) to the target node marches on it
    if aiFaction < 0 || aiFaction >= factionCount || aiTargetNode < 0 || aiTargetNode >= nodeCount
        Trace("step=api call=raid refused=1 faction=" + aiFaction + " node=" + aiTargetNode)
        return -1
    endif
    int[] prev = new int[128]
    float[] dist = Distances(aiTargetNode, prev)
    int best = -1
    int i = 0
    while i < MAX_SQ
        int st = sqState[i]
        if sqFaction[i] == aiFaction && (st == ST_GARRISON || st == ST_MARCH || st == ST_ONLINE) && dist[sqCurr[i]] >= 0.0
            if best < 0 || dist[sqCurr[i]] < dist[sqCurr[best]]
                best = i
            endif
        endif
        i += 1
    endwhile
    if best >= 0
        sqGoal[best] = aiTargetNode
        sqOrder[best] = ORD_RAID
        if sqEdgeV[best] < 0
            Depart(best, Utility.GetCurrentRealTime())
        endif
    endif
    Trace("step=api call=raid faction=" + aiFaction + " goal=" + aiTargetNode + " squad=" + best + " order=raid")
    return best
EndFunction

int Function GetOwnerOfNode(int aiNode)
    if aiNode < 0 || aiNode >= nodeCount
        return -1
    endif
    return nodeOwner[aiNode]
EndFunction

bool Function SetOwnerOfNode(int aiNode, int aiFaction)
    if aiNode < 0 || aiNode >= nodeCount || aiFaction < -1 || aiFaction >= factionCount
        return False
    endif
    int old = nodeOwner[aiNode]
    nodeOwner[aiNode] = aiFaction
    Trace("step=api call=set_owner node=" + aiNode + " owner_from=" + old + " owner_to=" + aiFaction)
    return True
EndFunction

int Function GetActiveSquads()
    return ActiveCount()
EndFunction

int Function GetNodeTotal()
    return nodeCount
EndFunction

int Function GetFactionTotal()
    return factionCount
EndFunction

int Function GetSquadStateId(int aiSquad)
    if aiSquad < 0 || aiSquad >= MAX_SQ
        return -1
    endif
    return sqState[aiSquad]
EndFunction

int Function GetSquadFactionId(int aiSquad)
    if aiSquad < 0 || aiSquad >= MAX_SQ || sqState[aiSquad] == ST_EMPTY
        return -1
    endif
    return sqFaction[aiSquad]
EndFunction

int Function GetSquadNodeId(int aiSquad)
    if aiSquad < 0 || aiSquad >= MAX_SQ || sqState[aiSquad] == ST_EMPTY
        return -1
    endif
    return sqCurr[aiSquad]
EndFunction

string Function Summary()
    return "active=" + ActiveCount() + "/" + SquadLimit() + " online=" + OnlineCount() + " enabled=" + SimOn() + " " + TerritoryText() + " spawns=" + statSpawns + " edges=" + statEdges + " battles=" + statBattles + " captures=" + statCaptures + " defeated=" + statDefeated + " materialized=" + statMaterialized + " dematerialized=" + statDematerialized + " ticks=" + tickCount
EndFunction

string Function TerritoryText()
    string s = "owned="
    int f = -1
    while f < factionCount
        int c = 0
        int n = 0
        while n < nodeCount
            if nodeOwner[n] == f && NodeKind[n] != 0
                c += 1
            endif
            n += 1
        endwhile
        if f >= 0
            s += "F" + f + ":" + c + ","
        else
            s += "free:" + c + ","
        endif
        f += 1
    endwhile
    return s
EndFunction

string Function LogStatus()
    string s = Summary()
    Trace("step=status " + s)
    return s
EndFunction

string Function BeaconReport(Actor akPlayer)
    ; for the Field Transponder: nearest squad and nearest node, from the player's position in the merged world
    string head = "A-Life transponder. Squads active: " + ActiveCount() + ", in range: " + OnlineCount() + "."
    if !graphValid
        return head + " No graph loaded."
    endif
    if akPlayer == None || !PlayerInSimWorld(akPlayer)
        return head + " No signal: outside the A-Life region."
    endif
    float px = akPlayer.GetPositionX()
    float py = akPlayer.GetPositionY()
    int best = -1
    float bestD = 0.0
    int i = 0
    while i < MAX_SQ
        int st = sqState[i]
        if st == ST_GARRISON || st == ST_MARCH || st == ST_ONLINE || st == ST_COMBAT
            float d = Dist2(SquadWX(i), SquadWY(i), px, py)
            if best < 0 || d < bestD
                best = i
                bestD = d
            endif
        endif
        i += 1
    endwhile
    string sq = " No squads."
    if best >= 0
        sq = " Nearest squad: faction " + sqFaction[best] + ", " + StateName(sqState[best]) + ", " + sqMembers[best] + " members, " + (bestD as int) + " m " + Compass(SquadWX(best) - px, SquadWY(best) - py) + "."
    endif
    int node = -1
    float nodeD = 0.0
    int n = 0
    while n < nodeCount
        float dn = Dist2(NodeX[n] + MergeOffsetX, NodeY[n] + MergeOffsetY, px, py)
        if node < 0 || dn < nodeD
            node = n
            nodeD = dn
        endif
        n += 1
    endwhile
    string terr = " Nearest node " + node + " (" + KindName(NodeKind[node]) + "), owner " + OwnerText(nodeOwner[node]) + ", " + (nodeD as int) + " m " + Compass(NodeX[node] + MergeOffsetX - px, NodeY[node] + MergeOffsetY - py) + ". Territory " + TerritoryText()
    Trace("step=status source=transponder squad=" + best + " squad_m=" + bestD + " node=" + node + " node_m=" + nodeD)
    return head + sq + terr
EndFunction

Function OnTransponderUsed()
    ; the aid item is consumed on use: give it back shortly after, when the player has none left
    StartTimer(0.5, TIMER_TRANSPONDER)
EndFunction

Function GiveTransponder()
    Actor player = Game.GetPlayer()
    if FieldTransponder != None && player != None && player.GetItemCount(FieldTransponder) < 1
        player.AddItem(FieldTransponder, 1, True)
    endif
EndFunction

; ---------------------------------------------------------------- shared helpers

string Function StateName(int st)
    if st == ST_GARRISON
        return "garrisoned"
    elseif st == ST_MARCH
        return "marching_offline"
    elseif st == ST_ONLINE
        return "online_3d"
    elseif st == ST_COMBAT
        return "in_combat_offline"
    elseif st == ST_DEAD
        return "dead_cooldown"
    endif
    return "empty"
EndFunction

string Function OrderName(int order)
    if order == ORD_RAID
        return "raid"
    elseif order == ORD_REINFORCE
        return "reinforce"
    endif
    return "patrol"
EndFunction

string Function KindName(int kind)
    if kind == 1
        return "base"
    elseif kind == 2
        return "checkpoint"
    elseif kind == 3
        return "lair"
    elseif kind == 4
        return "resource"
    endif
    return "relay"
EndFunction

string Function OwnerText(int owner)
    if owner < 0
        return "none"
    endif
    return "faction " + owner
EndFunction

string Function Compass(float dx, float dy)
    ; +Y north, +X east
    float ax = Math.abs(dx)
    float ay = Math.abs(dy)
    string ns = "N"
    if dy < 0.0
        ns = "S"
    endif
    string ew = "E"
    if dx < 0.0
        ew = "W"
    endif
    if ax > ay * 2.414
        return ew
    elseif ay > ax * 2.414
        return ns
    endif
    return ns + ew
EndFunction

Function Notify(string msg, float now)
    if NotifyOn() && now - lastNotifyT >= NOTIFY_GAP_S
        lastNotifyT = now
        Debug.Notification(msg)
    endif
EndFunction

float Function Dist2(float ax, float ay, float bx, float by)
    float dx = ax - bx
    float dy = ay - by
    return Math.sqrt(dx * dx + dy * dy)
EndFunction

int Function Id(Form f)
    if f == None
        return 0
    endif
    return f.GetFormID()
EndFunction

Function Trace(string msg)
    Debug.OpenUserLog(LOG_NAME)
    Debug.TraceUser(LOG_NAME, "ALIFE_MOD rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
