Scriptname FO4SF_ALifeControllerQuest extends Quest
{A-Life slice 1 (docs/alife/alife-slice1.md): one squad moves from A to B, loaded first (rung 1a), then offline (rung 1b).
 Rung 1a: a 4-member Minutemen squad is placed at the Red Rocket marker spot in the merged world and walks to Concord
 by its linked ref alone (SetLinkedRef + EvaluatePackage, no alias package: the P9 recipe, docs/combined-core.md
 CC-63). The route is a chain of waypoints served by a small pool of reusable XMarkerHeading waymarkers: waypoint i
 uses Waymarkers[i % pool size], moved into the merged world when the squad reaches the previous one.
 Rung 1b: no actor. One abstract squad walks the north-west offline graph (the plugin's NodeX/NodeY/EdgeU/EdgeV/EdgeLen
 properties, written by dotnet/ALife from scripts/alife/nw_subgraph.json) along its shortest route at OfflineSpeed m/s,
 one OfflineStep s step per tick, and garrisons at the goal when the goal has room (garrison capacity NodeCap).
 Rung 1b refuses to start until rung 1a passed on this save (loaded before offline); force=1 runs it anyway and the
 summary then never says PASS.
 Every line goes to the user log FO4SF_ALife (Logs/Script/User/FO4SF_ALife.0.log) as
   FO4SF_ALIFE rt=<real s> step=<name> key=value ...
 and make_alife.py log reads it back and judges it. Console commands (plugin-local quest id 0x800):
   cgf "FO4SF_ALifeControllerQuest.Rung1a"
   cgf "FO4SF_ALifeControllerQuest.Rung1b" <ticks per timer> <force 0|1>
   cgf "FO4SF_ALifeControllerQuest.Status"
   cgf "FO4SF_ALifeControllerQuest.StopAll"}

; ---------------------------------------------------------------- records (dotnet/ALife writes these)

ActorBase Property SquadBase Auto Const Mandatory
{NPC_ FO4SF_ALife_Minuteman: the raider plugin's calm probe under our Minutemen faction (Ally to the player).}

Faction Property SquadFaction Auto Const Mandatory
{FACT FO4SF_ALifeMinutemenFaction: also each member's group faction.}

ObjectReference[] Property Waymarkers Auto Const Mandatory
{The reusable waymarker pool: persistent XMarkerHeading REFRs in the core world's persistent cell.}

float[] Property NodeX Auto Const Mandatory
float[] Property NodeY Auto Const Mandatory
float[] Property NodeZ Auto Const Mandatory
{Node positions in the core's local frame, metres (FO4 position / 70). Merged = local + MergeOffset.}

int[] Property NodeCap Auto Const Mandatory
{Garrison capacity in squads per node; 0 is a road relay a squad passes through but never garrisons.}

int[] Property EdgeU Auto Const Mandatory
int[] Property EdgeV Auto Const Mandatory
float[] Property EdgeLen Auto Const Mandatory
{Undirected edges as node indices with their length in m.}

int Property Rung1aFrom Auto Const Mandatory
int Property Rung1aTo Auto Const Mandatory
int Property Rung1bFrom Auto Const Mandatory
int Property Rung1bGoal Auto Const Mandatory
float Property Rung1bExpectedM Auto Const Mandatory
{The route length make_alife.py computed for rung 1b; the summary compares the script's own route with it.}

; ---------------------------------------------------------------- tunables (defaults chosen; see docs/alife/alife-slice1.md)

int Property Mode = 0 Auto Const
{0 idle (commands only); 1 starts rung 1a at quest start; 2 starts rung 1b (forced) at quest start.}
float Property MergeOffsetX = -1200.0 Auto Const
float Property MergeOffsetY = -2700.0 Auto Const
{The core world's merge offset, as FO4SF_Min00Quest (measured in game): merged spot = local spot + this.}
int Property SquadSize = 4 Auto Const
float Property PlaceRadius = 300.0 Auto Const
{Rung 1a starts only when the player stands outdoors within this many m (XY) of the start spot in the merged world.}
float Property WaymarkerSpacing = 40.0 Auto Const
int Property MaxWaypoints = 16 Auto Const
float Property WaymarkerRadius = 10.0 Auto Const
{The squad advances to the next waypoint when its leader is this close (XY m) to the current one.}
float Property ArriveRadius = 15.0 Auto Const
float Property ReplaceRadius = 25.0 Auto Const
{A waymarker read farther than this (XY m) from its waypoint is placed again (snap-back check; a navmesh snap moves
 it a few m at most).}
float Property SampleSeconds = 2.0 Auto Const
float Property Rung1aTimeout = 500.0 Auto Const
float Property MaxStepSpeed = 6.0 Auto Const
float Property SpreadRadius = 25.0 Auto Const
float Property SpreadOkFraction = 0.9 Auto Const
float Property MaxSnapError = 0.5 Auto Const
float Property StuckSeconds = 60.0 Auto Const
float Property StuckMinMove = 2.0 Auto Const
float Property StuckNearPlayer = 35.0 Auto Const
{Stops within this many m of the player are not stuck (the owner's call on P9's stops near the player).}
float Property OfflineSpeed = 1.35 Auto Const
float Property OfflineStep = 1.0 Auto Const
float Property OfflineTimer = 1.0 Auto Const
float Property OfflineMinPlayerM = 1000.0 Auto Const
int Property OfflineMaxTicks = 5000 Auto Const

; ---------------------------------------------------------------- state

string LogName = "FO4SF_ALife"
int TIMER_1A = 1
int TIMER_1B = 2
int MAX_SQUAD = 16
int mode1a = 0                  ; 0 idle, 1 walking, 2 arrived, 3 failed
int mode1b = 0                  ; 0 idle, 1 walking, 2 garrisoned, 3 failed
bool rung1aPassed = False
int[] occupancy
Actor[] squad
float[] lastX
float[] lastY
float[] wpX
float[] wpY
float[] wpZ
int wpCount = 0
int wp = 0
int reusedCount = 0
float destX = 0.0
float destY = 0.0
float t0 = 0.0
float lastT = 0.0
int samples = 0
int spreadOk = 0
float maxStep = 0.0
int teleports = 0
float maxSnap = 0.0
int cellsCrossed = 0
int lastCell = 0
float stuckX = 0.0
float stuckY = 0.0
float stuckT = 0.0
int stuckCount = 0
int[] route
int routeLen = 0
int hop = 0
float walked = 0.0
float doneM = 0.0
float routeM = 0.0
int ticks = 0
int ticksPerTimer = 1
bool forced = False
bool monotonic = True
float lastProgress = 0.0
float playerM1b = 0.0

; ---------------------------------------------------------------- console entry points

FO4SF_ALifeControllerQuest Function Q() global
    return Game.GetFormFromFile(2048, "FO4SFALife.esm") as FO4SF_ALifeControllerQuest
EndFunction

Function Rung1a() global
    FO4SF_ALifeControllerQuest c = Q()
    if c != None
        c.StartRung1a()
    endif
EndFunction

Function Rung1b(int perTimer, int force) global
    FO4SF_ALifeControllerQuest c = Q()
    if c != None
        c.StartRung1b(perTimer, force != 0)
    endif
EndFunction

Function Status() global
    FO4SF_ALifeControllerQuest c = Q()
    if c != None
        c.LogStatus()
    endif
EndFunction

Function StopAll() global
    FO4SF_ALifeControllerQuest c = Q()
    if c != None
        c.Shutdown("command")
    endif
EndFunction

; ---------------------------------------------------------------- lifecycle

Event OnQuestInit()
    ResetOccupancy()
    RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")
    Trace("step=init nodes=" + NodeX.Length + " edges=" + EdgeU.Length + " pool=" + Waymarkers.Length + " squad_size=" + SquadSize + " mode=" + Mode + " offset=" + MergeOffsetX + "," + MergeOffsetY)
    if !GraphOk()
        return
    endif
    if Mode == 1
        StartRung1a()
    elseif Mode == 2
        StartRung1b(10, True)
    endif
EndEvent

Event Actor.OnPlayerLoadGame(Actor akSender)
    RebaseTimers(Utility.GetCurrentRealTime())
    Trace("step=load_game rt_rebased=" + (mode1a == 1) + " rung1a=" + mode1a + " rung1b=" + mode1b)
EndEvent

Function RebaseTimers(float now)
    if mode1a == 1
        float elapsed = lastT - t0
        if elapsed < 0.0
            elapsed = 0.0
        endif
        float stuckAge = lastT - stuckT
        if stuckAge < 0.0
            stuckAge = 0.0
        endif
        t0 = now - elapsed
        lastT = now
        stuckT = now - stuckAge
    endif
EndFunction

Function ResetOccupancy()
    occupancy = new int[128]
EndFunction

bool Function GraphOk()
    int n = NodeX.Length
    int e = EdgeU.Length
    bool ok = n > 1 && n <= 128 && NodeY.Length == n && NodeZ.Length == n && NodeCap.Length == n
    ok = ok && e > 0 && e <= 128 && EdgeV.Length == e && EdgeLen.Length == e && Waymarkers.Length > 0
    ok = ok && Rung1aFrom >= 0 && Rung1aFrom < n && Rung1aTo >= 0 && Rung1aTo < n && Rung1bFrom >= 0 && Rung1bFrom < n && Rung1bGoal >= 0 && Rung1bGoal < n
    if !ok
        Trace("step=graph_refused nodes=" + n + " edges=" + e + " pool=" + Waymarkers.Length)
    endif
    return ok
EndFunction

Function LogStatus()
    Actor player = Game.GetPlayer()
    Trace("step=status rung1a=" + mode1a + " rung1a_passed=" + rung1aPassed + " wp=" + wp + "/" + wpCount + " rung1b=" + mode1b + " ticks=" + ticks + " hop=" + hop + "/" + (routeLen - 1) + " live_actors=" + LiveActors() + " player=" + player.GetPositionX() + "," + player.GetPositionY() + " interior=" + player.IsInInterior())
EndFunction

Function Shutdown(string why)
    CancelTimer(TIMER_1A)
    CancelTimer(TIMER_1B)
    int removed = ClearSquad()
    ResetOccupancy()
    if mode1a == 1
        mode1a = 3
    endif
    if mode1b == 1
        mode1b = 3
    endif
    Trace("step=stop why=" + why + " removed=" + removed + " occupancy_reset=1")
EndFunction

; ---------------------------------------------------------------- rung 1a: loaded 3D walk

Function StartRung1a()
    if !GraphOk()
        return
    endif
    if SquadSize < 1 || SquadSize > MAX_SQUAD
        Trace("step=rung1a_refused reason=bad_squad_size squad_size=" + SquadSize + " max=" + MAX_SQUAD)
        return
    endif
    if mode1a == 1 || mode1b == 1
        Trace("step=rung1a_refused reason=busy rung1a=" + mode1a + " rung1b=" + mode1b)
        return
    endif
    Actor player = Game.GetPlayer()
    float sx = NodeX[Rung1aFrom] + MergeOffsetX
    float sy = NodeY[Rung1aFrom] + MergeOffsetY
    float sz = NodeZ[Rung1aFrom]
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float pd = Dist2(px, py, sx, sy)
    if player.IsInInterior() || pd > PlaceRadius
        ; coordinates alone cannot tell two exterior worlds apart: start only where the merged spot is near the player
        Trace("step=rung1a_refused reason=player_not_at_start interior=" + player.IsInInterior() + " player_m=" + pd + " radius=" + PlaceRadius + " spot=" + sx + "," + sy)
        return
    endif
    ClearSquad()
    ResetOccupancy()
    RegisterForRemoteEvent(player, "OnPlayerLoadGame")
    ; the waypoints: evenly spaced on the straight line from start to destination (the navmesh walk finds the road)
    float ex = NodeX[Rung1aTo] + MergeOffsetX
    float ey = NodeY[Rung1aTo] + MergeOffsetY
    float ez = NodeZ[Rung1aTo]
    float total = Dist2(sx, sy, ex, ey)
    wpCount = Math.Ceiling(total / WaymarkerSpacing)
    if wpCount < 1
        wpCount = 1
    endif
    if wpCount > MaxWaypoints
        wpCount = MaxWaypoints
    endif
    wpX = new float[16]
    wpY = new float[16]
    wpZ = new float[16]
    int k = 0
    while k < wpCount
        float f = ((k + 1) as float) / (wpCount as float)
        wpX[k] = sx + (ex - sx) * f
        wpY[k] = sy + (ey - sy) * f
        wpZ[k] = sz + (ez - sz) * f
        k += 1
    endwhile
    destX = ex
    destY = ey
    ; spawn: pool marker 0 at the start spot, snapped to the navmesh, then the squad on it
    ObjectReference spawnAt = PlaceWaymarker(0, sx, sy, sz, -1)
    squad = new Actor[16]
    lastX = new float[16]
    lastY = new float[16]
    maxSnap = 0.0
    reusedCount = 0
    int i = 0
    while i < SquadSize && i < MAX_SQUAD
        Actor a = spawnAt.PlaceActorAtMe(SquadBase, 4, None, False, False, True, None, True)
        if a != None
            a.MoveTo(spawnAt, (i as float) * 1.5 - 2.25, -1.5, 0.0, False, False)
            a.SetGroupFaction(SquadFaction)
            squad[i] = a
            lastX[i] = a.GetPositionX()
            lastY[i] = a.GetPositionY()
            float snap = Math.abs(a.GetPositionZ() - spawnAt.GetPositionZ())
            if snap > maxSnap
                maxSnap = snap
            endif
            Trace("step=rung1a_spawn member=" + i + " id=" + a.GetFormID() + " pos=" + a.GetPositionX() + "," + a.GetPositionY() + "," + a.GetPositionZ() + " z_snap_m=" + snap + " loaded=" + a.Is3DLoaded() + " cell=" + Id(a.GetParentCell()) + " world=" + Id(a.GetWorldSpace()))
        else
            Trace("step=rung1a_spawn member=" + i + " id=0 failed=1")
        endif
        i += 1
    endwhile
    wp = 0
    ObjectReference first = PlaceWaymarker(0, wpX[0], wpY[0], wpZ[0], 0)
    LinkSquad(first)
    t0 = Utility.GetCurrentRealTime()
    lastT = t0
    samples = 0
    spreadOk = 0
    maxStep = 0.0
    teleports = 0
    cellsCrossed = 0
    lastCell = 0
    stuckCount = 0
    Actor leader = Leader()
    if leader != None
        stuckX = leader.GetPositionX()
        stuckY = leader.GetPositionY()
        lastCell = Id(leader.GetParentCell())
    endif
    stuckT = t0
    mode1a = 1
    Trace("step=rung1a_start from=" + Rung1aFrom + " to=" + Rung1aTo + " route_m=" + total + " waypoints=" + wpCount + " pool=" + Waymarkers.Length + " members=" + LiveActors() + " dest=" + destX + "," + destY + " player_m=" + pd)
    StartTimer(SampleSeconds, TIMER_1A)
EndFunction

ObjectReference Function PlaceWaymarker(int pool, float tx, float ty, float tz, int waypoint)
    ; the merged-world placement of FO4SF_Min00Quest: MoveTo onto the player with the difference as the offset
    ObjectReference m = Waymarkers[pool % Waymarkers.Length]
    Actor player = Game.GetPlayer()
    m.MoveTo(player, tx - player.GetPositionX(), ty - player.GetPositionY(), tz - player.GetPositionZ(), False, False)
    float before = m.GetPositionZ()
    m.MoveToNearestNavmeshLocation()
    Trace("step=rung1a_waymarker_place waypoint=" + waypoint + " marker=" + m.GetFormID() + " slot=" + (pool % Waymarkers.Length) + " target=" + tx + "," + ty + " pos=" + m.GetPositionX() + "," + m.GetPositionY() + "," + m.GetPositionZ() + " snapped_dz=" + (m.GetPositionZ() - before) + " cell=" + Id(m.GetParentCell()))
    return m
EndFunction

Function LinkSquad(ObjectReference target)
    int i = 0
    while i < squad.Length
        Actor a = squad[i]
        if a != None && !a.IsDead()
            a.SetLinkedRef(target)
            a.EvaluatePackage()
        endif
        i += 1
    endwhile
EndFunction

Actor Function Leader()
    int i = 0
    while i < squad.Length
        if squad[i] != None && !squad[i].IsDead()
            return squad[i]
        endif
        i += 1
    endwhile
    return None
EndFunction

int Function LiveActors()
    int n = 0
    if squad == None
        return 0
    endif
    int i = 0
    while i < squad.Length
        if squad[i] != None && !squad[i].IsDead()
            n += 1
        endif
        i += 1
    endwhile
    return n
EndFunction

int Function ClearSquad()
    int n = 0
    if squad == None
        return 0
    endif
    int i = 0
    while i < squad.Length
        if squad[i] != None
            squad[i].SetLinkedRef(None)
            squad[i].Disable(False)
            squad[i].Delete()
            n += 1
        endif
        squad[i] = None
        i += 1
    endwhile
    return n
EndFunction

Function Rung1aSample()
    float now = Utility.GetCurrentRealTime()
    if now < lastT
        RebaseTimers(now)
    endif
    float t = now - t0
    float dt = now - lastT
    lastT = now
    Actor player = Game.GetPlayer()
    Actor leader = Leader()
    if leader == None
        Finish1a(False, "no_live_member", t)
        return
    endif
    float lx = leader.GetPositionX()
    float ly = leader.GetPositionY()
    float spread = 0.0
    float step = 0.0
    int loaded = 0
    int alive = 0
    int arrived = 0
    int i = 0
    while i < squad.Length
        Actor a = squad[i]
        if a != None && !a.IsDead()
            alive += 1
            float ax = a.GetPositionX()
            float ay = a.GetPositionY()
            float d = Dist2(ax, ay, lx, ly)
            if d > spread
                spread = d
            endif
            if dt > 0.0
                float s = Dist2(ax, ay, lastX[i], lastY[i]) / dt
                if s > step
                    step = s
                endif
            endif
            lastX[i] = ax
            lastY[i] = ay
            if a.Is3DLoaded()
                loaded += 1
            endif
            if Dist2(ax, ay, destX, destY) <= ArriveRadius
                arrived += 1
            endif
        endif
        i += 1
    endwhile
    samples += 1
    if spread <= SpreadRadius
        spreadOk += 1
    endif
    if step > maxStep
        maxStep = step
    endif
    if step >= MaxStepSpeed
        teleports += 1
    endif
    int cellId = Id(leader.GetParentCell())
    if cellId != 0 && lastCell != 0 && cellId != lastCell
        cellsCrossed += 1
    endif
    if cellId != 0
        lastCell = cellId
    endif
    float toWp = Dist2(lx, ly, wpX[wp], wpY[wp])
    ; a persistent ref can read its editor (unmerged) spot again when its cell reloads (docs/mission/when-freedom-calls.md,
    ; 19 Oct: actors snapped back): a waymarker found far from its waypoint is placed again and the squad relinked
    ObjectReference cur = Waymarkers[wp % Waymarkers.Length]
    float off = Dist2(cur.GetPositionX(), cur.GetPositionY(), wpX[wp], wpY[wp])
    if off > ReplaceRadius
        Trace("step=rung1a_waymarker_replace t=" + (now - t0) + " wp=" + wp + " marker=" + cur.GetFormID() + " off_m=" + off)
        LinkSquad(PlaceWaymarker(wp, wpX[wp], wpY[wp], wpZ[wp], wp))
    endif
    float toDest = Dist2(lx, ly, destX, destY)
    float playerM = Dist2(lx, ly, player.GetPositionX(), player.GetPositionY())
    Trace("step=rung1a_progress t=" + t + " wp=" + wp + "/" + wpCount + " leader_wp_m=" + toWp + " leader_dest_m=" + toDest + " leader_3d_wp_m=" + leader.GetDistance(Waymarkers[wp % Waymarkers.Length]) + " spread_m=" + spread + " step_mps=" + step + " alive=" + alive + " loaded=" + loaded + " arrived=" + arrived + " cell=" + cellId + " cells_crossed=" + cellsCrossed + " player_m=" + playerM + " package=" + Id(leader.GetCurrentPackage()))
    ; stuck: no real move for StuckSeconds, away from the player
    if Dist2(lx, ly, stuckX, stuckY) >= StuckMinMove
        stuckX = lx
        stuckY = ly
        stuckT = now
    elseif now - stuckT >= StuckSeconds && playerM > StuckNearPlayer
        stuckCount += 1
        Trace("step=rung1a_stuck t=" + t + " still_s=" + (now - stuckT) + " wp=" + wp + " leader_wp_m=" + toWp + " player_m=" + playerM + " count=" + stuckCount)
        LinkSquad(Waymarkers[wp % Waymarkers.Length])
        stuckT = now
    endif
    if alive > 0 && arrived == alive
        Trace("step=rung1a_arrived t=" + t + " members=" + arrived + " alive=" + alive + " cells_crossed=" + cellsCrossed)
        bool admitted = GarrisonCheck(Rung1aTo, "rung1a")
        Finish1a(arrived == SquadSize && admitted, "arrived", t)
        return
    endif
    if wp < wpCount - 1 && toWp <= WaymarkerRadius
        wp += 1
        bool reused = wp >= Waymarkers.Length
        if reused
            reusedCount += 1
        endif
        ObjectReference nextM = PlaceWaymarker(wp, wpX[wp], wpY[wp], wpZ[wp], wp)
        LinkSquad(nextM)
        Trace("step=rung1a_waymarker_advance t=" + t + " wp=" + wp + "/" + wpCount + " marker=" + nextM.GetFormID() + " reused=" + reused + " leader_dest_m=" + toDest)
    endif
    if t >= Rung1aTimeout
        Finish1a(False, "timeout", t)
        return
    endif
    StartTimer(SampleSeconds, TIMER_1A)
EndFunction

Function Finish1a(bool arrivedOk, string why, float t)
    float okFrac = 0.0
    if samples > 0
        okFrac = (spreadOk as float) / (samples as float)
    endif
    bool pass = arrivedOk && teleports == 0 && okFrac >= SpreadOkFraction && maxSnap < MaxSnapError && t <= Rung1aTimeout && cellsCrossed >= 1 && reusedCount >= 1
    string result = "FAIL"
    if pass
        result = "PASS"
        rung1aPassed = True
        mode1a = 2
    else
        mode1a = 3
    endif
    Trace("step=summary rung=1a result=" + result + " why=" + why + " t=" + t + " members=" + LiveActors() + "/" + SquadSize + " samples=" + samples + " spread_ok=" + okFrac + " max_step_mps=" + maxStep + " teleports=" + teleports + " z_snap_max_m=" + maxSnap + " cells_crossed=" + cellsCrossed + " reused=" + reusedCount + " stuck=" + stuckCount + " waypoints=" + wpCount + " pool=" + Waymarkers.Length)
EndFunction

bool Function GarrisonCheck(int node, string who)
    int cap = NodeCap[node]
    int occ = occupancy[node]
    bool admitted = cap > 0 && occ < cap
    if admitted
        occupancy[node] = occ + 1
    endif
    Trace("step=garrison_cap_check who=" + who + " node=" + node + " cap=" + cap + " occupied=" + occ + " admitted=" + admitted)
    return admitted
EndFunction

; ---------------------------------------------------------------- rung 1b: offline subgraph walk

Function StartRung1b(int perTimer, bool force)
    if !GraphOk()
        return
    endif
    if mode1a == 1 || mode1b == 1
        Trace("step=rung1b_refused reason=busy rung1a=" + mode1a + " rung1b=" + mode1b)
        return
    endif
    if !rung1aPassed && !force
        Trace("step=rung1b_refused reason=rung1a_not_passed")
        return
    endif
    ResetOccupancy()
    forced = force && !rung1aPassed
    int removed = ClearSquad()
    Actor player = Game.GetPlayer()
    playerM1b = Dist2(player.GetPositionX(), player.GetPositionY(), NodeX[Rung1bFrom] + MergeOffsetX, NodeY[Rung1bFrom] + MergeOffsetY)
    int goal = Rung1bGoal
    if !Route(Rung1bFrom, goal)
        Trace("step=rung1b_refused reason=no_route from=" + Rung1bFrom + " goal=" + goal)
        return
    endif
    if NodeCap[goal] <= 0 || occupancy[goal] >= NodeCap[goal]
        int alt = NearestFree(Rung1bFrom, goal)
        Trace("step=garrison_cap_check who=rung1b_plan node=" + goal + " cap=" + NodeCap[goal] + " occupied=" + occupancy[goal] + " admitted=False reroute=" + alt)
        if alt < 0 || !Route(Rung1bFrom, alt)
            Trace("step=rung1b_refused reason=no_free_garrison goal=" + goal)
            return
        endif
    endif
    ticksPerTimer = perTimer
    if ticksPerTimer < 1
        ticksPerTimer = 1
    endif
    hop = 0
    walked = 0.0
    doneM = 0.0
    ticks = 0
    monotonic = True
    lastProgress = 0.0
    mode1b = 1
    Trace("step=rung1b_start from=" + Rung1bFrom + " goal=" + route[routeLen - 1] + " hops=" + (routeLen - 1) + " route_m=" + routeM + " expected_m=" + Rung1bExpectedM + " speed=" + OfflineSpeed + " step_s=" + OfflineStep + " ticks_per_timer=" + ticksPerTimer + " live_actors=" + LiveActors() + " removed=" + removed + " player_m=" + playerM1b + " forced=" + forced)
    Trace("step=rung1b_route nodes=" + RouteText() + " route_m=" + routeM)
    StartTimer(OfflineTimer, TIMER_1B)
EndFunction

string Function RouteText()
    string s = ""
    int i = 0
    while i < routeLen
        if i > 0
            s += ">"
        endif
        s += route[i]
        i += 1
    endwhile
    return s
EndFunction

float Function EdgeBetween(int u, int v)
    int e = 0
    float best = -1.0
    while e < EdgeU.Length
        if (EdgeU[e] == u && EdgeV[e] == v) || (EdgeU[e] == v && EdgeV[e] == u)
            if best < 0.0 || EdgeLen[e] < best
                best = EdgeLen[e]
            endif
        endif
        e += 1
    endwhile
    return best
EndFunction

float[] Function Distances(int src, int[] prev)
    ; Dijkstra over the property arrays (n <= 128, O(n^2 + n*e)); prev gets the predecessor of each node
    int n = NodeX.Length
    float[] dist = new float[128]
    bool[] done = new bool[128]
    int i = 0
    while i < n
        dist[i] = -1.0
        prev[i] = -1
        i += 1
    endwhile
    dist[src] = 0.0
    int round = 0
    while round < n
        int u = -1
        i = 0
        while i < n
            if !done[i] && dist[i] >= 0.0 && (u < 0 || dist[i] < dist[u])
                u = i
            endif
            i += 1
        endwhile
        if u < 0
            round = n
        else
            done[u] = True
            int e = 0
            while e < EdgeU.Length
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
            round += 1
        endif
    endwhile
    return dist
EndFunction

bool Function Route(int src, int dst)
    int[] prev = new int[128]
    float[] dist = Distances(src, prev)
    if dist[dst] < 0.0
        return False
    endif
    int[] rev = new int[128]
    int n = 0
    int x = dst
    while x >= 0 && n < 128
        rev[n] = x
        n += 1
        x = prev[x]
    endwhile
    route = new int[128]
    routeLen = n
    int i = 0
    while i < n
        route[i] = rev[n - 1 - i]
        i += 1
    endwhile
    routeM = dist[dst]
    return True
EndFunction

int Function NearestFree(int src, int skip)
    ; the reachable node with garrison room nearest to the planned goal (by graph distance from it); -1 if none
    int[] prev = new int[128]
    float[] fromSrc = Distances(src, prev)
    float[] fromGoal = Distances(skip, prev)
    int best = -1
    int i = 0
    while i < NodeX.Length
        if i != skip && i != src && NodeCap[i] > 0 && occupancy[i] < NodeCap[i] && fromSrc[i] >= 0.0 && fromGoal[i] >= 0.0
            if best < 0 || fromGoal[i] < fromGoal[best] || (fromGoal[i] == fromGoal[best] && i < best)
                best = i
            endif
        endif
        i += 1
    endwhile
    return best
EndFunction

Function Rung1bTick()
    int k = 0
    while k < ticksPerTimer && mode1b == 1
        OneTick()
        k += 1
    endwhile
    if mode1b == 1
        StartTimer(OfflineTimer, TIMER_1B)
    endif
EndFunction

Function OneTick()
    ticks += 1
    walked += OfflineSpeed * OfflineStep
    int u = route[hop]
    int v = route[hop + 1]
    float len = EdgeBetween(u, v)
    bool goalReached = False
    while !goalReached && walked >= len
        walked -= len
        doneM += len
        Trace("step=rung1b_node_arrive tick=" + ticks + " node=" + v + " hop=" + (hop + 1) + "/" + (routeLen - 1) + " done_m=" + doneM + " cap=" + NodeCap[v])
        hop += 1
        if hop >= routeLen - 1
            goalReached = True
            walked = 0.0
        else
            u = route[hop]
            v = route[hop + 1]
            len = EdgeBetween(u, v)
            Trace("step=rung1b_edge_step tick=" + ticks + " from=" + u + " to=" + v + " edge_m=" + len + " carry_m=" + walked)
        endif
    endwhile
    float progress = doneM + walked
    if progress <= lastProgress && !goalReached
        monotonic = False
    endif
    lastProgress = progress
    float x = NodeX[u]
    float y = NodeY[u]
    if !goalReached && len > 0.0
        x = NodeX[u] + (NodeX[v] - NodeX[u]) * walked / len
        y = NodeY[u] + (NodeY[v] - NodeY[u]) * walked / len
    else
        x = NodeX[route[routeLen - 1]]
        y = NodeY[route[routeLen - 1]]
    endif
    Trace("step=rung1b_tick tick=" + ticks + " hop=" + hop + "/" + (routeLen - 1) + " from=" + u + " to=" + v + " walked_m=" + walked + " edge_m=" + len + " progress_m=" + progress + " pos=" + x + "," + y + " live_actors=" + LiveActors())
    if goalReached
        Finish1b(True)
    elseif ticks >= OfflineMaxTicks
        Finish1b(False)
    endif
EndFunction

Function Finish1b(bool reached)
    int goal = route[routeLen - 1]
    bool admitted = False
    if reached
        admitted = GarrisonCheck(goal, "rung1b")
    endif
    int expected = Math.Ceiling((routeM / (OfflineSpeed * OfflineStep)) - 0.0001)
    int off = ticks - expected
    if off < 0
        off = -off
    endif
    float lenOff = Math.abs(routeM - Rung1bExpectedM)
    bool far = playerM1b >= OfflineMinPlayerM
    bool pass = reached && admitted && monotonic && off <= 1 && lenOff < 0.5 && LiveActors() == 0 && far && !forced
    string result = "FAIL"
    if pass
        result = "PASS"
        mode1b = 2
    elseif reached && admitted
        mode1b = 2
    else
        mode1b = 3
    endif
    Trace("step=summary rung=1b result=" + result + " reached=" + reached + " state=garrisoned:" + admitted + " goal=" + goal + " ticks=" + ticks + " expected_ticks=" + expected + " route_m=" + routeM + " expected_m=" + Rung1bExpectedM + " monotonic=" + monotonic + " live_actors=" + LiveActors() + " player_m=" + playerM1b + " far=" + far + " forced=" + forced)
EndFunction

; ---------------------------------------------------------------- shared

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_1A && mode1a == 1
        Rung1aSample()
    elseif aiTimerID == TIMER_1B && mode1b == 1
        Rung1bTick()
    endif
EndEvent

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
    Debug.OpenUserLog(LogName)
    Debug.TraceUser(LogName, "FO4SF_ALIFE rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
