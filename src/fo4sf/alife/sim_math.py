"""Deterministic offline A-Life preview: the multi-squad simulation the Papyrus runtime runs, in pure Python.

Mirrors FO4SF_ALifeSimQuest's offline rules (board contract of alife-runtime) so a modder can balance a config in
well under a second for 1,000 ticks, with no game:

  spawning   a base (NodeSpawnFaction >= 0) spawns one squad for its CURRENT owner (skipped while unowned) once
             per respawn_cooldown_s, while active squads (including defeated ones still cooling down) are below
             min(max_active_squads, 16). members = squad_size, strength = members * combat_power.
  orders     a garrisoned squad dwells 45 s + U(0, 30) s, then draws Raid 40% (nearest node owned by a hostile
             faction, or an unowned base/checkpoint, capacity > 0) / Reinforce 30% (nearest own node with free
             capacity) / Patrol 30% (random reachable node with capacity); a missing target falls through to Patrol.
  movement   Dijkstra routes (ties: lower node index); squads pass through intermediate nodes whatever their
             garrisons; offline_step_m_per_s * tick_real_s metres per tick, remainder carried over nodes.
  arrival    a full goal (or a relay) reroutes to the nearest node with free capacity by graph distance from the
             goal (ties: lower index); with none free the squad holds at the goal and re-orders after its dwell.
  combat     hostile squads (FactionRelationsFlat < 0) on the same node, or on the same edge within 15 m, fight:
             each tick each loses max(0.15 * enemy strength * tick_real_s / 2, 0.05 * own power); strength below
             0.25 * combat_power routs (defeat; slot freed after respawn_cooldown_s); members = ceil(strength /
             power). Fighting squads neither move nor re-order.
  capture    a squad that garrisons (or wins) at a base or checkpoint with no hostile squad present takes it.
  replenish  a squad garrisoned at its own faction's base regains one member every respawn_cooldown_s / 4.

usage: python -m fo4sf.alife.sim_math <config.json> [--ticks 1000] [--seed 42] [--events]
"""
import argparse
import heapq
import json
import math
import random
import sys

from . import schema

DWELL_S = 45.0
DWELL_JITTER_S = 30.0         # dwell = 45 s + U(0, 30) s
ENCOUNTER_M = 15.0
DAMAGE_RATE = 0.15            # strength lost per enemy strength per 2 s
MIN_DAMAGE = 0.05             # x own combat_power per tick
ROUT_FRACTION = 0.25          # strength below 0.25 x combat_power routs (defeat)
REPLENISH_DIVISOR = 4.0       # +1 member every respawn_cooldown_s / 4 at an own base
RAID_P, REINFORCE_P = 0.40, 0.30
SQUAD_SLOTS = 16
CAPTURABLE = ("base", "checkpoint")


class Graph:
    """Nodes, shortest edge lengths and all-pairs Dijkstra (ties go to the lower node index)."""

    def __init__(self, nodes, edges):
        self.nodes = nodes
        self.n = len(nodes)
        self.adj = [dict() for _ in range(self.n)]
        for e in edges:
            u, v, w = e["u"], e["v"], float(e["len_m"])
            if w < self.adj[u].get(v, math.inf):
                self.adj[u][v] = w
                self.adj[v][u] = w
        self.dist, self.prev = [], []
        for s in range(self.n):
            d, p = self._dijkstra(s)
            self.dist.append(d)
            self.prev.append(p)

    def _dijkstra(self, src):
        dist = [math.inf] * self.n
        prev = [-1] * self.n
        done = [False] * self.n
        dist[src] = 0.0
        pq = [(0.0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if done[u]:
                continue
            done[u] = True
            for v in sorted(self.adj[u]):
                nd = d + self.adj[u][v]
                if nd < dist[v] - 1e-9 or (abs(nd - dist[v]) <= 1e-9 and not done[v] and u < prev[v]):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))
        return dist, prev

    def route(self, src, dst):
        """[src, ..., dst] shortest path, or None when unreachable."""
        if math.isinf(self.dist[src][dst]):
            return None
        path, x = [], dst
        while x >= 0:
            path.append(x)
            if x == src:
                break
            x = self.prev[src][x]
        return path[::-1]

    def edge_len(self, u, v):
        return self.adj[u][v]


class Squad:
    __slots__ = ("sid", "faction", "state", "node", "goal", "path", "hop", "progress", "members", "strength",
                 "dwell", "order", "free_at", "home")

    def __init__(self, sid, faction, node, members, strength, dwell):
        self.sid, self.faction, self.node, self.home = sid, faction, node, node
        self.state = "garrisoned"
        self.goal, self.path, self.hop, self.progress = node, [node], 0, 0.0
        self.members, self.strength, self.dwell = members, strength, dwell
        self.order, self.free_at = "spawn", None

    # where the squad is: ("node", n) or ("edge", lo, hi, metres from lo)
    def place(self, g):
        if self.state in ("garrisoned", "in_combat_node"):
            return ("node", self.node)
        u, v = self.path[self.hop], self.path[self.hop + 1]
        length = g.edge_len(u, v)
        return ("edge", min(u, v), max(u, v), self.progress if u < v else length - self.progress)


def _load(cfg):
    if isinstance(cfg, str):
        cfg = schema.load_alife_config(cfg)
    return schema.checked(cfg)


def simulate(cfg, ticks=1000, seed=42, record_events=False):
    """Run the offline simulation; returns a dict:
      squads_spawned, edges_traversed, battles, captures {faction_id: n}, garrison_utilization (mean occupied /
      capacity over ticks, 0..1), per_faction {faction_id: {spawned, losses, nodes_owned}}, plus ticks,
      sim_seconds, reroutes, replenishes, orders {raid, reinforce, patrol}, final_owners [faction id or None],
      active_squads_end and, with record_events, events [(tick, step, {..})].
    cfg is a config dict, a writer payload or a path; an invalid config raises schema.AlifeConfigError."""
    norm = _load(cfg)
    sim, facs, nodes = norm["simulation"], norm["factions"], norm["nodes"]
    g = Graph(nodes, norm["edges"])
    F, N = len(facs), len(nodes)
    rel = schema.relations_flat(norm)
    hostile = [[rel[a * F + b] < 0 for b in range(F)] for a in range(F)]
    dt = float(sim["tick_real_s"])
    step_m = float(sim["offline_step_m_per_s"]) * dt
    cooldown = float(sim["respawn_cooldown_s"])
    max_active = min(int(sim["max_active_squads"]), SQUAD_SLOTS)
    power = [f["combat_power"] for f in facs]
    size = [f["squad_size"] for f in facs]
    cap = [n["capacity"] for n in nodes]
    kind = [n["kind"] for n in nodes]
    owner = [n["initial_owner"] for n in nodes]
    bases = [i for i, n in enumerate(nodes) if n["spawn_faction"] >= 0]
    next_spawn = {b: 0.0 for b in bases}
    next_replenish = {}
    rng = random.Random(seed)

    def new_dwell():
        return max(1, math.ceil((DWELL_S + rng.uniform(0.0, DWELL_JITTER_S)) / dt - 1e-9))
    squads = []
    events = []
    stats = {"squads_spawned": 0, "edges_traversed": 0, "battles": 0, "reroutes": 0, "replenishes": 0}
    orders = {"raid": 0, "reinforce": 0, "patrol": 0}
    captures = {f["id"]: 0 for f in facs}
    per = {f["id"]: {"spawned": 0, "losses": 0, "nodes_owned": 0} for f in facs}
    battling = set()
    util_sum, total_cap = 0.0, float(sum(cap)) or 1.0

    def log(tick, step, **kw):
        if record_events:
            events.append((tick, step, kw))

    def alive():
        return [s for s in squads if s.state != "dead_cooldown"]

    def occupancy(n):
        return sum(1 for s in squads if s.state == "garrisoned" and s.node == n)

    def admit(n):
        return cap[n] > 0 and occupancy(n) < cap[n]

    def hostiles_at(n, f):
        return [s for s in alive() if s.state in ("garrisoned", "in_combat_node") and s.node == n
                and hostile[f][s.faction]]

    def nearest(src, ok):
        best = None
        for i in range(N):
            if i != src and ok(i) and not math.isinf(g.dist[src][i]):
                if best is None or g.dist[src][i] < g.dist[src][best] - 1e-9:
                    best = i
        return best

    def depart(s, goal, order, tick):
        path = g.route(s.node, goal)
        if not path or len(path) < 2:
            s.dwell = new_dwell()
            return
        s.state, s.goal, s.path, s.hop, s.progress, s.order = "marching_offline", goal, path, 0, 0.0, order
        log(tick, "order", squad=s.sid, faction=facs[s.faction]["id"], node=s.node, goal=goal, order=order)

    def give_order(s, tick):
        f = s.faction
        r = rng.random()
        goal, order = None, None
        if r < RAID_P:
            goal = nearest(s.node, lambda i: cap[i] > 0 and (
                (owner[i] >= 0 and hostile[f][owner[i]]) or (owner[i] < 0 and kind[i] in CAPTURABLE)))
            order = "raid"
        elif r < RAID_P + REINFORCE_P:
            goal = nearest(s.node, lambda i: owner[i] == f and admit(i))
            order = "reinforce"
        if goal is None:
            choices = [i for i in range(N) if i != s.node and cap[i] > 0 and not math.isinf(g.dist[s.node][i])]
            if not choices:
                s.dwell = new_dwell()
                return
            goal, order = rng.choice(choices), "patrol"
        orders[order] += 1
        depart(s, goal, order, tick)

    def try_capture(s, tick):
        n = s.node
        if kind[n] in CAPTURABLE and owner[n] != s.faction and not hostiles_at(n, s.faction):
            log(tick, "capture", squad=s.sid, faction=facs[s.faction]["id"], node=n, owner_from=owner[n],
                owner_to=s.faction)
            owner[n] = s.faction
            captures[facs[s.faction]["id"]] += 1

    def settle(s, tick):
        """A squad standing at s.node with no fight: garrison, reroute or hold."""
        n = s.node
        if admit(n) or (s.state == "garrisoned"):
            s.state, s.dwell = "garrisoned", new_dwell()
            log(tick, "garrison", squad=s.sid, faction=facs[s.faction]["id"], node=n)
            try_capture(s, tick)
            return
        alt = nearest(n, admit)
        if alt is None:
            s.state, s.dwell = "garrisoned", new_dwell()     # holds over capacity until its next order
            return
        stats["reroutes"] += 1
        log(tick, "reroute", squad=s.sid, faction=facs[s.faction]["id"], node=n, goal=alt)
        s.state = "garrisoned"                                # departs from here
        depart(s, alt, s.order, tick)

    def spawn(tick, t):
        for b in bases:
            f = owner[b]
            if f < 0 or t + 1e-9 < next_spawn[b]:
                continue
            active = [s for s in squads if s.state != "dead_cooldown" or (s.free_at or 0) > t + 1e-9]
            if len(active) >= max_active:
                continue
            for s in list(squads):                            # reuse a freed slot
                if s.state == "dead_cooldown" and (s.free_at or 0) <= t + 1e-9:
                    squads.remove(s)
            sid = stats["squads_spawned"]
            s = Squad(sid, f, b, size[f], size[f] * power[f], new_dwell())
            squads.append(s)
            next_spawn[b] = t + cooldown
            stats["squads_spawned"] += 1
            per[facs[f]["id"]]["spawned"] += 1
            log(tick, "squad_spawn", squad=sid, faction=facs[f]["id"], node=b, members=s.members)

    def move(s, tick):
        left = step_m
        while left > 0:
            u, v = s.path[s.hop], s.path[s.hop + 1]
            length = g.edge_len(u, v)
            if s.progress + left < length:
                s.progress += left
                return
            left -= length - s.progress
            s.hop += 1
            s.progress = 0.0
            s.node = v
            stats["edges_traversed"] += 1
            log(tick, "node_arrive", squad=s.sid, faction=facs[s.faction]["id"], node=v)
            if s.hop >= len(s.path) - 1:
                if hostiles_at(v, s.faction):
                    s.state = "in_combat_node"
                else:
                    s.state = "arrived"
                return

    for tick in range(1, ticks + 1):
        t = tick * dt
        spawn(tick, t)
        # replenish garrisons at their own bases
        for s in alive():
            if s.state == "garrisoned" and kind[s.node] == "base" and owner[s.node] == s.faction:
                full = size[s.faction] * power[s.faction]
                if s.strength < full - 1e-9 and t + 1e-9 >= next_replenish.get(s.sid, 0.0):
                    s.strength = min(full, s.strength + power[s.faction])
                    s.members = min(size[s.faction], s.members + 1)
                    next_replenish[s.sid] = t + cooldown / REPLENISH_DIVISOR
                    stats["replenishes"] += 1
                    log(tick, "replenish", squad=s.sid, faction=facs[s.faction]["id"], node=s.node)
        # orders, then movement (squads still fighting since last tick neither re-order nor move)
        fighting = {sid for key in battling for sid in key}
        for s in alive():
            if s.state == "garrisoned" and s.sid not in fighting:
                s.dwell -= 1
                if s.dwell <= 0:
                    give_order(s, tick)
        for s in alive():
            if s.state == "marching_offline" and s.sid not in fighting:
                move(s, tick)
        for s in alive():
            if s.state == "arrived":
                settle(s, tick)
        # encounters
        live = alive()
        pairs = []
        for i, a in enumerate(live):
            pa = a.place(g)
            for b in live[i + 1:]:
                if not hostile[a.faction][b.faction]:
                    continue
                pb = b.place(g)
                if pa[0] == "node" and pb[0] == "node":
                    met = pa[1] == pb[1]
                elif pa[0] == "edge" and pb[0] == "edge":
                    met = pa[1:3] == pb[1:3] and abs(pa[3] - pb[3]) <= ENCOUNTER_M
                else:
                    met = False
                if met:
                    pairs.append((a, b))
        now = set()
        loss = {}
        for a, b in pairs:
            key = (a.sid, b.sid)
            now.add(key)
            if key not in battling:
                stats["battles"] += 1
                log(tick, "battle", squad=a.sid, faction=facs[a.faction]["id"], loser=b.sid,
                    node=a.node if a.place(g)[0] == "node" else -1)
            for x, y in ((a, b), (b, a)):
                loss[y.sid] = loss.get(y.sid, 0.0) + max(DAMAGE_RATE * x.strength * dt / 2.0,
                                                         MIN_DAMAGE * power[y.faction])
        in_fight = {sid for key in now for sid in key}
        for s in live:
            if s.sid in loss:
                s.strength -= loss[s.sid]
                if s.strength < ROUT_FRACTION * power[s.faction]:
                    s.strength, s.members, s.state = 0.0, 0, "dead_cooldown"
                    s.free_at = t + cooldown
                    per[facs[s.faction]["id"]]["losses"] += 1
                    log(tick, "squad_defeated", squad=s.sid, faction=facs[s.faction]["id"])
                else:
                    s.members = min(size[s.faction], math.ceil(s.strength / power[s.faction] - 1e-9))
        for key in battling - now:
            log(tick, "battle_end", squad=key[0], loser=key[1])
        battling = now
        # survivors of finished node fights settle (garrison / capture / reroute)
        for s in alive():
            if s.state == "in_combat_node" and s.sid not in in_fight:
                if not hostiles_at(s.node, s.faction):
                    s.state = "arrived"
                    settle(s, tick)
        occ = {}
        for s in squads:
            if s.state == "garrisoned":
                occ[s.node] = occ.get(s.node, 0) + 1
        util_sum += sum(min(c, cap[n]) for n, c in occ.items()) / total_cap
    for i, o in enumerate(owner):
        if o >= 0:
            per[facs[o]["id"]]["nodes_owned"] += 1
    out = dict(stats)
    out.update({"captures": captures, "per_faction": per, "orders": orders,
                "garrison_utilization": round(util_sum / ticks, 6) if ticks else 0.0,
                "ticks": ticks, "sim_seconds": ticks * dt, "seed": seed,
                "final_owners": [facs[o]["id"] if o >= 0 else None for o in owner],
                "active_squads_end": len(alive())})
    if record_events:
        out["events"] = events
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m fo4sf.alife.sim_math", description=__doc__.split("\n")[0])
    ap.add_argument("config")
    ap.add_argument("--ticks", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--events", action="store_true")
    a = ap.parse_args(argv)
    try:
        res = simulate(a.config, a.ticks, a.seed, a.events)
    except schema.AlifeConfigError as e:
        print("\n".join(e.problems), file=sys.stderr)
        return 2
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
