r"""A-Life slice 1 (docs/alife/alife-slice1.md): the north-west offline graph, the plugin's stage, and the in-game log.

usage:
  python make_alife.py graph --places <fo4_places_smart_terrains.tsv> --edges <commonwealth_alife_graph_edges.tsv>
                             [--out scripts/alife/nw_subgraph.json]
      the item 22 extraction (place rows: FormIDs, EditorIDs, core-frame metres; k-nearest edges with relay road
      nodes) cut down to the north-west subgraph: the ANCHORS below as nodes, each pair joined when a shortest path
      between them passes no other anchor (relays contracted, length summed), each node keeping its KEEP shortest
      such edges, plus the shortest bridges until the graph is connected. Refuses more than 128 nodes or edges
      (one Papyrus array each). Writes nw_subgraph.json, the only graph input of dotnet/ALife and of the tests.
  python make_alife.py route [--graph nw_subgraph.json]
      prints rung 1b's route, its length and the tick the offline squad is due at its goal.
  python make_alife.py stage --out <new dir> --starfield <Starfield.esm> --core <FO4TerrainCore.esm>
                             --raider <FO4ActorRaider.esm> --compiler <PapyrusCompiler.exe> --content-resources <zip>
      dotnet/ALife write + check (offline_check.txt), the Papyrus compile of FO4SF_ALifeControllerQuest.psc against
      ContentResources.zip's base scripts, plan.json (plugin, script and masters' SHA-256) and README.txt. Built in a
      new <out>.partial-<time>-<pid> folder (kept on failure), renamed to <out> only when every step passed; an
      existing <out> is refused; a master that changed during the build is refused. With FO4SF_STARFIELD set to the
      game folder, --starfield, --compiler and --content-resources default to the files under it.
  python make_alife.py fold --stage <stage dir> --core-dir <core experiment dir> --out <new dir> [--raider <esm>]
      a copy of the core experiment folder plus FO4SFALife.esm and Data/Scripts/FO4SF_ALifeControllerQuest.pex, only
      after verify passes on the copy (exp_install.py holds one experiment at a time).
  python make_alife.py verify --exp-dir <experiment dir> --plan <stage dir>/plan.json [--raider <FO4ActorRaider.esm>]
      the install preflight: plugin, script and masters match the plan's hashes. Exit 0 only when all match.
  python make_alife.py log [--file <FO4SF_ALife.0.log>]
      the controller's user log judged independently of its own summary lines: rung 1a and rung 1b verdicts with
      every criterion; exit 0 only when rung 1a passed and, if rung 1b ran, rung 1b passed.
  python make_alife.py log1b [--file <FO4SF_ALife.0.log>]
      rung 1b's own session (its log holds no rung 1a lines): exit 0 only when rung 1b passed.
Nothing here starts the game or writes into its folder.
"""
import argparse
import csv
import datetime
import hashlib
import heapq
import json
import math
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
PROJECT = os.path.join(REPO, "dotnet", "ALife")
GRAPH = os.path.join(HERE, "nw_subgraph.json")
PLUGIN = "FO4SFALife.esm"
SCRIPT = "FO4SF_ALifeControllerQuest"
LOG = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User",
                   "FO4SF_ALife.0.log")
# the script's Auto Const Mandatory properties, in source order: dotnet/ALife fills exactly these
PROPERTIES = ("SquadBase", "SquadFaction", "Waymarkers", "NodeX", "NodeY", "NodeZ", "NodeCap", "EdgeU", "EdgeV",
              "EdgeLen", "Rung1aFrom", "Rung1aTo", "Rung1bFrom", "Rung1bGoal", "Rung1bExpectedM")
ARRAY_CAP = 128                       # Papyrus arrays hold at most 128 elements
MERGE_OFFSET = (-1200.0, -2700.0)     # FO4SF_Min00Quest MergeOffsetX/Y (measured in game): merged = local + offset

# the north-west subgraph: smart-terrain nodes by LCTN EditorID (item 22 Part F rungs 1 and 2)
ANCHORS = (
    "SanctuaryHillsLocation", "Vault111Location", "RedRocketTruckStopLocation", "ConcordLocation",
    "ConcordMuseumLocation", "AbernathyFarmLocation", "RangerCabinLocation", "WickedShippingFleetLockupLocation",
    "USAFSatelliteLocation", "RoboticsDisposalGroundLocation", "ThicketExcavationsLocation", "BedfordStationLocation",
    "StarlightDriveInLocation", "DrumlinDinerLocation", "WaldenPondLocation", "GorskiCabinLocation",
    "SunshineTidingsCoopLocation", "LexingtonLocation", "CorvegaAssemblyPlantLocation", "POIJeffB04Location",
)
# two anchors are exterior cell centres in the extraction (z 0): their spot is taken from their map marker's row
SPOT_FROM = {"RedRocketTruckStopLocation": ("xmrk_edid", "RedRocketTruckStopMapMarker"),
             "AbernathyFarmLocation": ("node_id", "XMRK:0x0006F5D4")}
KEEP = 3
RUNG1A = ("RedRocketTruckStopLocation", "ConcordLocation")
RUNG1B = ("RedRocketTruckStopLocation", "StarlightDriveInLocation")
# the script's tunables used by the judge (FO4SF_ALifeControllerQuest.psc defaults)
SPEED, STEP = 1.35, 1.0
SQUAD, TIMEOUT, MAX_STEP, SPREAD, SPREAD_OK, MAX_SNAP, MIN_CELLS = 4, 500.0, 6.0, 25.0, 0.9, 0.5, 1
OFFLINE_MIN_PLAYER_M = 1000.0
LINE = re.compile(r"FO4SF_ALIFE rt=(?P<rt>[-\d.]+) step=(?P<step>\w+)(?P<rest>.*)$")


# ---------------------------------------------------------------- graph

def read_tsv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def build_subgraph(places, edges, anchors=ANCHORS, keep=KEEP, spot_from=None, rung1a=RUNG1A, rung1b=RUNG1B):
    """The anchors as nodes (positions in core-frame metres, garrison capacity from max_squad_cap) and contracted
    edges: from each anchor, a Dijkstra over the whole edge list that never expands past another anchor; every anchor
    so reached is a candidate edge with the path's length. Each node keeps its `keep` shortest candidates, then the
    shortest remaining candidates are added until the graph is connected. Raises ValueError when an anchor is
    missing or the anchors cannot be connected."""
    spot_from = SPOT_FROM if spot_from is None else spot_from
    by_edid = {}
    for r in places:
        if r.get("lctn_edid"):
            by_edid.setdefault(r["lctn_edid"], r)
    missing = [a for a in anchors if a not in by_edid]
    if missing:
        raise ValueError(f"anchors not in the place rows: {missing}")
    adj = {}
    for e in edges:
        d = _f(e["dist_sf_m"], None)
        if d is None or d < 0:
            continue
        for a, b in ((e["u_id"], e["v_id"]), (e["v_id"], e["u_id"])):
            row = adj.setdefault(a, {})
            row[b] = min(d, row.get(b, math.inf))
    ids = [by_edid[a]["node_id"] for a in anchors]
    index = {nid: i for i, nid in enumerate(ids)}
    cand = {}
    for i, src in enumerate(ids):
        dist = {src: 0.0}
        pq = [(0.0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            if u != src and u in index:
                j = index[u]
                key = (min(i, j), max(i, j))
                cand[key] = min(cand.get(key, math.inf), d)
                continue                                  # never route through another anchor
            for v, w in adj.get(u, {}).items():
                nd = d + w
                if nd < dist.get(v, math.inf):
                    dist[v] = nd
                    heapq.heappush(pq, (nd, v))
    chosen = set()
    for i in range(len(ids)):
        mine = sorted((d, k) for k, d in cand.items() if i in k)
        chosen.update(k for _, k in mine[:keep])
    parent = list(range(len(ids)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b in chosen:
        parent[find(a)] = find(b)
    for d, (a, b) in sorted((d, k) for k, d in cand.items()):
        if find(a) != find(b):
            parent[find(a)] = find(b)
            chosen.add((a, b))
    if len({find(i) for i in range(len(ids))}) != 1:
        raise ValueError("the anchors are not connected by the edge list")
    nodes = []
    for a in anchors:
        r = by_edid[a]
        src = "place row"
        if a in spot_from:
            col, val = spot_from[a]
            alt = next((p for p in places if p.get(col) == val), None)
            if alt is None:
                raise ValueError(f"{a}: no place row with {col} {val} for its spot")
            r_pos, src = alt, f"{col} {val}"
        else:
            r_pos = r
        nodes.append({"id": r["node_id"], "edid": a, "kind": r.get("smart_terrain_class", ""),
                      "x": round(_f(r_pos["x_sf_m"]), 2), "y": round(_f(r_pos["y_sf_m"]), 2),
                      "z": round(_f(r_pos["z_sf_m"]), 2), "cap": int(_f(r.get("max_squad_cap"), 0)),
                      "faction": r.get("initial_faction", ""), "spot": src})
    out_edges = [{"u": a, "v": b, "len_m": round(cand[(a, b)], 2)} for a, b in sorted(chosen)]
    g = {"source": "item 22 extraction: fo4_places_smart_terrains.tsv + commonwealth_alife_graph_edges.tsv",
         "frame": "core local metres (FO4 position / 70); merged world = local + merge_offset",
         "merge_offset": list(MERGE_OFFSET), "nodes": nodes, "edges": out_edges}
    return finish_graph(g, rung1a, rung1b)


def node_index(g, edid):
    for i, n in enumerate(g["nodes"]):
        if n["edid"] == edid:
            return i
    raise ValueError(f"no node {edid}")


def finish_graph(g, rung1a=RUNG1A, rung1b=RUNG1B):
    """Adds the rung entries: rung 1a's start and destination, rung 1b's start, goal, route and its length."""
    a, b = node_index(g, rung1a[0]), node_index(g, rung1a[1])
    g["rung1a"] = {"from": a, "to": b, "from_edid": rung1a[0], "to_edid": rung1a[1],
                   "straight_m": round(xy_dist(g["nodes"][a], g["nodes"][b]), 2)}
    s, t = node_index(g, rung1b[0]), node_index(g, rung1b[1])
    path, length = route(g, s, t)
    g["rung1b"] = {"from": s, "goal": t, "from_edid": rung1b[0], "goal_edid": rung1b[1], "route": path,
                   "route_edids": [g["nodes"][i]["edid"] for i in path], "length_m": round(length, 2),
                   "expected_ticks": expected_ticks(length)}
    return g


def xy_dist(p, q):
    return math.hypot(p["x"] - q["x"], p["y"] - q["y"])


def graph_problems(g):
    """Why the graph cannot be written into the plugin (empty: it can)."""
    p = []
    n, e = len(g.get("nodes", [])), len(g.get("edges", []))
    if not 1 < n <= ARRAY_CAP:
        p.append(f"{n} nodes: 2..{ARRAY_CAP} fit a Papyrus array")
    if not 0 < e <= ARRAY_CAP:
        p.append(f"{e} edges: 1..{ARRAY_CAP} fit a Papyrus array")
    for i, ed in enumerate(g.get("edges", [])):
        if not (0 <= ed["u"] < n and 0 <= ed["v"] < n) or ed["u"] == ed["v"]:
            p.append(f"edge {i} joins {ed['u']} and {ed['v']}")
        if not (isinstance(ed["len_m"], (int, float)) and math.isfinite(ed["len_m"]) and ed["len_m"] > 0):
            p.append(f"edge {i} length {ed['len_m']}")
    for i, nd in enumerate(g.get("nodes", [])):
        if not all(math.isfinite(nd[k]) for k in ("x", "y", "z")) or nd["cap"] < 0:
            p.append(f"node {i} {nd['edid']} position or capacity")
    if not p:
        dist, _ = dijkstra(g, 0)
        if any(d is None for d in dist):
            p.append("the graph is not connected")
        r1b = g.get("rung1b", {})
        if r1b and not p:
            path, length = route(g, r1b["from"], r1b["goal"])
            if path != r1b["route"] or abs(length - r1b["length_m"]) > 0.01:
                p.append("rung1b route or length differs from the graph's shortest path")
            if g["nodes"][r1b["goal"]]["cap"] <= 0:
                p.append("rung1b goal has no garrison capacity")
        r1a = g.get("rung1a", {})
        if r1a and g["nodes"][r1a["to"]]["cap"] <= 0:
            p.append("rung1a destination has no garrison capacity")
    return p


def dijkstra(g, src):
    """Distances (None when unreachable) and predecessors from src; ties go to the lower node index, as the
    script's Distances (it scans nodes in index order and takes a strictly shorter distance only)."""
    n = len(g["nodes"])
    dist = [None] * n
    prev = [-1] * n
    done = [False] * n
    dist[src] = 0.0
    for _ in range(n):
        u = -1
        for i in range(n):
            if not done[i] and dist[i] is not None and (u < 0 or dist[i] < dist[u]):
                u = i
        if u < 0:
            break
        done[u] = True
        for ed in g["edges"]:
            v = ed["v"] if ed["u"] == u else ed["u"] if ed["v"] == u else -1
            if v >= 0 and not done[v]:
                nd = dist[u] + ed["len_m"]
                if dist[v] is None or nd < dist[v]:
                    dist[v] = nd
                    prev[v] = u
    return dist, prev


def route(g, src, dst):
    dist, prev = dijkstra(g, src)
    if dist[dst] is None:
        raise ValueError(f"no route {src} -> {dst}")
    path, x = [], dst
    while x >= 0:
        path.append(x)
        x = prev[x]
    return path[::-1], dist[dst]


def edge_len(g, u, v):
    best = None
    for ed in g["edges"]:
        if {ed["u"], ed["v"]} == {u, v}:
            best = ed["len_m"] if best is None else min(best, ed["len_m"])
    return best


def expected_ticks(length, speed=SPEED, step=STEP):
    """The tick on which the offline squad reaches its goal: the script's Math.Ceiling(route_m / (speed * step))."""
    return math.ceil(length / (speed * step) - 1e-4)


def admit(cap, occupied):
    """The garrison capacity rule: a relay (cap 0) never garrisons; a node garrisons while it has room."""
    return cap > 0 and occupied < cap


def nearest_free(g, src, goal, occupancy):
    """The script's NearestFree: the reachable node with room, nearest to the planned goal by graph distance
    (ties: the lower index); -1 if none."""
    from_src, _ = dijkstra(g, src)
    from_goal, _ = dijkstra(g, goal)
    best = -1
    for i, nd in enumerate(g["nodes"]):
        if i in (goal, src) or not admit(nd["cap"], occupancy.get(i, 0)):
            continue
        if from_src[i] is None or from_goal[i] is None:
            continue
        if best < 0 or from_goal[i] < from_goal[best]:
            best = i
    return best


def plan_offline(g, src, goal, occupancy=None):
    """Rung 1b's plan as the script makes it: the route to the goal, or to nearest_free when the goal is full."""
    occupancy = occupancy or {}
    target = goal
    if not admit(g["nodes"][goal]["cap"], occupancy.get(goal, 0)):
        target = nearest_free(g, src, goal, occupancy)
        if target < 0:
            raise ValueError("no free garrison")
    return route(g, src, target)


def offline_walk(g, path, speed=SPEED, step=STEP, max_ticks=5000):
    """The script's OneTick loop: each tick walks speed*step m along the route, carrying the remainder over each
    node; returns the event list [(tick, kind, data)] and the arrival tick (None when max_ticks ran out)."""
    events, hop, walked, done, tick = [], 0, 0.0, 0.0, 0
    last = len(path) - 1
    while tick < max_ticks:
        tick += 1
        walked += speed * step
        reached = False
        length = edge_len(g, path[hop], path[hop + 1])
        while not reached and walked >= length:
            walked -= length
            done += length
            events.append((tick, "node_arrive", path[hop + 1]))
            hop += 1
            if hop >= last:
                reached, walked = True, 0.0
            else:
                length = edge_len(g, path[hop], path[hop + 1])
                events.append((tick, "edge_step", (path[hop], path[hop + 1])))
        events.append((tick, "tick", round(done + walked, 4)))
        if reached:
            return events, tick
    return events, None


def waypoints(start, end, spacing=40.0, max_points=16):
    """Rung 1a's waypoints: evenly spaced on the straight line, the last one the destination (script StartRung1a)."""
    total = math.hypot(end[0] - start[0], end[1] - start[1])
    n = min(max(1, math.ceil(total / spacing)), max_points)
    return [tuple(s + (e - s) * (k + 1) / n for s, e in zip(start, end)) for k in range(n)]


def pool_slot(waypoint, pool):
    """Which pooled waymarker serves a waypoint (Waymarkers[i % pool]): markers are reused round the route."""
    return waypoint % pool


def merged(node, offset=MERGE_OFFSET):
    return (node["x"] + offset[0], node["y"] + offset[1], node["z"])


def load_graph(path=GRAPH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- log

def parse(lines):
    """[(step, {key: value})] of the controller's lines; other logs' lines are skipped."""
    out = []
    for line in lines:
        m = LINE.search(line)
        if not m:
            continue
        kv = dict(re.findall(r"(\w+)=(\S+)", m.group("rest")))
        kv["rt"] = m.group("rt")
        out.append((m.group("step"), kv))
    return out


def _num(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _bool(v):
    return str(v).lower() in ("true", "1")


def _run(ev, start):
    """The events of one run: from its start line to the next rung's start line."""
    run = ev[start:]
    nxt = next((i for i, (s, _) in enumerate(run[1:], 1) if s in ("rung1a_start", "rung1b_start")), len(run))
    return run[:nxt]


def judge(lines, min_player_m=OFFLINE_MIN_PLAYER_M):
    """Both rungs judged from the raw lines (the script's own summary is reported, not trusted): rung 1a from its
    spawn, progress, arrival and cap lines; rung 1b from its start, tick and cap lines. Only the last run of each
    rung counts. Rung 1b is loaded-first when a rung 1a pass precedes it in the same log, or when it was not forced
    (the script refuses an unforced rung 1b until rung 1a passed on the save)."""
    ev = parse(lines)
    res = {"rung1a": None, "rung1b": None}
    starts = [i for i, (s, _) in enumerate(ev) if s == "rung1a_start"]
    if starts:
        run = _run(ev, starts[-1])
        spawns, i = [], starts[-1] - 1
        while i >= 0 and ev[i][0] in ("rung1a_spawn", "rung1a_waymarker_place"):   # the lines StartRung1a logs first
            if ev[i][0] == "rung1a_spawn":
                spawns.append(ev[i][1])
            i -= 1
        prog = [kv for s, kv in run if s == "rung1a_progress"]
        arrived = [kv for s, kv in run if s == "rung1a_arrived"]
        caps = [kv for s, kv in run if s == "garrison_cap_check" and kv.get("who") == "rung1a"]
        summary = next((kv for s, kv in reversed(run) if s == "summary" and kv.get("rung") == "1a"), None)
        steps = [_num(kv.get("step_mps"), 0.0) for kv in prog]
        spreads = [_num(kv.get("spread_m"), math.inf) for kv in prog]
        ok_frac = sum(1 for s in spreads if s <= SPREAD) / len(spreads) if spreads else 0.0
        snaps = [_num(kv.get("z_snap_m"), math.inf) for kv in spawns if kv.get("failed") != "1"]
        cells = max((int(_num(kv.get("cells_crossed"), 0)) for kv in prog), default=0)
        t_arr = _num(arrived[-1].get("t")) if arrived else None
        crit = {
            "members_spawned": len(snaps) == SQUAD,
            "arrived_all": bool(arrived) and int(_num(arrived[-1].get("members"), 0)) == SQUAD,
            "within_timeout": t_arr is not None and t_arr <= TIMEOUT,
            "no_teleport": bool(steps) and max(steps) < MAX_STEP,
            "cohesion": ok_frac >= SPREAD_OK,
            "z_snap": bool(snaps) and max(snaps) < MAX_SNAP,
            "cells_crossed": cells >= MIN_CELLS,
            "garrison_admitted": bool(caps) and _bool(caps[-1].get("admitted")),
            "waymarkers_reused": any(_bool(kv.get("reused")) for s, kv in run if s == "rung1a_waymarker_advance"),
        }
        res["rung1a"] = {"pass": all(crit.values()), "criteria": crit, "samples": len(prog),
                         "arrived_t": t_arr, "max_step_mps": max(steps, default=None), "spread_ok": round(ok_frac, 3),
                         "cells_crossed": cells, "script_summary": summary}
    starts_b = [i for i, (s, _) in enumerate(ev) if s == "rung1b_start"]
    if starts_b:
        st = ev[starts_b[-1]][1]
        run = _run(ev, starts_b[-1])
        ticks = [kv for s, kv in run if s == "rung1b_tick"]
        prog = [_num(kv.get("progress_m"), 0.0) for kv in ticks]
        mono = all(b > a for a, b in zip(prog, prog[1:-1])) and (len(prog) < 2 or prog[-1] >= prog[-2])
        route_m = _num(st.get("route_m"), 0.0)
        speed, step = _num(st.get("speed"), SPEED), _num(st.get("step_s"), STEP)
        want = expected_ticks(route_m, speed, step)
        caps = [kv for s, kv in run if s == "garrison_cap_check" and kv.get("who") == "rung1b"]
        summary = next((kv for s, kv in reversed(run) if s == "summary" and kv.get("rung") == "1b"), None)
        steps_ok = all(abs((b - a) - speed * step) <= 0.01 for a, b in zip(prog, prog[1:-1]))
        live = [int(_num(kv.get("live_actors"), 1)) for kv in ticks]
        a_pass = res["rung1a"] is not None and res["rung1a"]["pass"] and starts[-1] < starts_b[-1]
        crit = {
            "loaded_first": a_pass or not _bool(st.get("forced")),
            "not_forced": not _bool(st.get("forced")),
            "player_far": _num(st.get("player_m"), 0.0) >= min_player_m,
            "no_live_actors": int(_num(st.get("live_actors"), 1)) == 0 and bool(live) and max(live) == 0,
            "monotonic": bool(prog) and mono,
            "step_per_tick": steps_ok,
            "arrival_tick": bool(ticks) and abs(len(ticks) - want) <= 1,
            "route_matches_plan": abs(route_m - _num(st.get("expected_m"), -1.0)) < 0.5,
            "garrisoned": bool(caps) and _bool(caps[-1].get("admitted")),
        }
        res["rung1b"] = {"pass": all(crit.values()), "criteria": crit, "ticks": len(ticks), "expected_ticks": want,
                         "route_m": route_m, "script_summary": summary}
    return res


# ---------------------------------------------------------------- stage, fold, verify

def run(cmd, cwd=None):
    print("+ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stdout.write(r.stderr)
        sys.exit(f"{os.path.basename(cmd[0])} exit {r.returncode}")
    return r.stdout


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def mandatory_properties(psc_text):
    return [m.group(1) for m in re.finditer(r"^\s*[\w\[\]]+\s+Property\s+(\w+)\s+Auto\s+Const\s+Mandatory\b",
                                            psc_text, re.M | re.I)]


def new_partial(final, create=True):
    base = f"{final}.partial-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
    out, n = base, 1
    while os.path.exists(out):
        out, n = f"{base}-{n}", n + 1
    if create:
        os.makedirs(out)
    return out


def extract_sources(zip_path, work):
    src = os.path.join(work, "Source")
    os.makedirs(src, exist_ok=True)
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            parts = name.split("/")
            if len(parts) == 3 and parts[:2] == ["Scripts", "Source"] and (
                    parts[2].lower().endswith(".psc") or parts[2] == "Starfield_Papyrus_Flags.flg"):
                with z.open(name) as f, open(os.path.join(src, parts[2]), "wb") as o:
                    shutil.copyfileobj(f, o)
                n += 1
    if not os.path.exists(os.path.join(src, "Starfield_Papyrus_Flags.flg")) or n < 2:
        sys.exit(f"{zip_path}: no Scripts/Source base scripts or flags file")
    return src


def compile_script(compiler, src_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    out = run([compiler, SCRIPT + ".psc", "-f=Starfield_Papyrus_Flags.flg", f"-i={HERE};{src_dir}",
               f"-o={out_dir}"], cwd=HERE)
    pex = os.path.join(out_dir, SCRIPT + ".pex")
    if "Compilation succeeded" not in out or not os.path.exists(pex):
        sys.exit(f"the Papyrus compile did not produce {SCRIPT}.pex")
    return pex


def pin(paths):
    return {os.path.basename(p): sha256(p) for p in paths}


def stage(a):
    with open(os.path.join(HERE, SCRIPT + ".psc"), encoding="utf-8") as f:
        props = mandatory_properties(f.read())
    if tuple(props) != PROPERTIES:
        sys.exit(f"{SCRIPT}.psc properties {props} differ from what dotnet/ALife writes {list(PROPERTIES)}")
    g = load_graph(a.graph)
    problems = graph_problems(g)
    if problems:
        sys.exit("graph refused: " + "; ".join(problems))
    final = os.path.abspath(a.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder")
    masters = pin((a.starfield, a.core, a.raider))
    out = new_partial(final)
    work = os.path.join(out, "work")
    os.makedirs(work)
    tool = ["dotnet", "run", "-c", "Release", "--project", PROJECT, "--"]
    run(tool + ["write", a.starfield, a.core, a.raider, a.graph, out, "--plugin", PLUGIN])
    check = run(tool + ["check", os.path.join(out, PLUGIN), a.starfield, a.core, a.raider, a.graph])
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(check)
    src = extract_sources(a.content_resources, work)
    pex = compile_script(a.compiler, src, os.path.join(out, "Data", "Scripts"))
    shutil.copy(os.path.join(HERE, SCRIPT + ".psc"), os.path.join(out, SCRIPT + ".psc"))
    drift = [n for n, h in pin((a.starfield, a.core, a.raider)).items() if h != masters[n]]
    if drift:
        sys.exit(f"a master changed during the build ({', '.join(drift)}); attempt kept in {out}")
    plan = {"kind": "alife", "plugin": PLUGIN, "plugin_sha256": sha256(os.path.join(out, PLUGIN)),
            "script": SCRIPT, "script_sha256": sha256(pex), "masters_sha256": masters,
            "graph_sha256": sha256(a.graph), "rung1a": g["rung1a"], "rung1b": g["rung1b"],
            "log": "<My Games>/Starfield/Logs/Script/User/FO4SF_ALife.0.log"}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""A-Life slice 1 ({datetime.date.today().isoformat()}). docs/alife/alife-slice1.md
{PLUGIN} (sha256 {plan['plugin_sha256']}): QUST FO4SF_ALife (start game enabled) with {SCRIPT}, the squad NPC_,
our Minutemen FACT and the reusable waymarker pool (persistent XMarkerHeading REFRs in the core world's persistent cell).
Graph: {len(g['nodes'])} nodes, {len(g['edges'])} edges. Rung 1a: {g['rung1a']['from_edid']} -> {g['rung1a']['to_edid']}
({g['rung1a']['straight_m']} m straight). Rung 1b: {' > '.join(g['rung1b']['route_edids'])} ({g['rung1b']['length_m']} m,
due on tick {g['rung1b']['expected_ticks']}).
Masters (must match the installed files): {json.dumps(masters)}.
Commands (console, game unpaused after each):
  cgf "{SCRIPT}.Rung1a"
  cgf "{SCRIPT}.Rung1b" 10 0
  cgf "{SCRIPT}.Status"
  cgf "{SCRIPT}.StopAll"
Read the log: python scripts\\alife\\make_alife.py log   (rung 1b's own session: log1b)
""")
    os.replace(out, final)
    print(f"staged {final}: {PLUGIN}, Data/Scripts/{SCRIPT}.pex, offline_check.txt, plan.json, README.txt")


def load_plan(path):
    with open(path, encoding="utf-8") as f:
        plan = json.load(f)
    missing = [k for k in ("plugin", "plugin_sha256", "script", "script_sha256", "masters_sha256") if k not in plan]
    if missing or plan.get("kind") != "alife":
        sys.exit(f"{path} is not an A-Life plan (missing {missing})")
    return plan


def verify_dir(exp_dir, plan, raider=None):
    problems = []

    def same(label, path, want):
        if not os.path.isfile(path):
            problems.append(f"{label}: {path} missing")
        elif sha256(path) != want:
            problems.append(f"{label}: {path} sha256 is not the plan's {want}")

    same("plugin", os.path.join(exp_dir, plan["plugin"]), plan["plugin_sha256"])
    same("script", os.path.join(exp_dir, "Data", "Scripts", plan["script"] + ".pex"), plan["script_sha256"])
    for name, want in plan["masters_sha256"].items():
        if name.lower() == "starfield.esm":
            continue                                   # the game's own master is not in an experiment folder
        path = os.path.join(exp_dir, name)
        if not os.path.isfile(path) and raider and name.lower() == os.path.basename(raider).lower():
            path = raider
        same(f"master {name}", path, want)
    return problems


def verify(a):
    problems = verify_dir(a.exp_dir, load_plan(a.plan), a.raider)
    for p in problems:
        print("FAIL  " + p)
    print("verify: ok" if not problems else f"verify: {len(problems)} problem(s); do not install")
    return 0 if not problems else 1


def fold(a):
    final = os.path.abspath(a.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: fold into a new folder")
    plan = load_plan(os.path.join(a.stage, "plan.json"))
    if os.path.exists(os.path.join(a.core_dir, plan["plugin"])):
        sys.exit(f"{a.core_dir} already holds {plan['plugin']}")
    out = new_partial(final, create=False)
    shutil.copytree(a.core_dir, out)
    shutil.copy2(os.path.join(a.stage, plan["plugin"]), os.path.join(out, plan["plugin"]))
    dst = os.path.join(out, "Data", "Scripts", plan["script"] + ".pex")
    if os.path.exists(dst):
        sys.exit(f"fold refused: the core set already has Data/Scripts/{plan['script']}.pex (attempt kept in {out})")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(os.path.join(a.stage, "Data", "Scripts", plan["script"] + ".pex"), dst)
    problems = verify_dir(out, plan, a.raider)
    if problems:
        for p in problems:
            print("FAIL  " + p)
        sys.exit(f"fold refused: {len(problems)} problem(s); attempt kept in {out}")
    os.replace(out, final)
    print(f"folded {final}: {a.core_dir} + {plan['plugin']} + Data/Scripts/{plan['script']}.pex; verify ok")
    return 0


def log(a):
    with open(a.file, encoding="utf-8", errors="replace") as f:
        res = judge(f)
    print(json.dumps(res, indent=1))
    ok_a = bool(res["rung1a"] and res["rung1a"]["pass"])
    ok_b = res["rung1b"] is None or res["rung1b"]["pass"]
    return 0 if ok_a and ok_b else 1


def log_b(a):
    with open(a.file, encoding="utf-8", errors="replace") as f:
        res = judge(f)
    print(json.dumps(res, indent=1))
    return 0 if res["rung1b"] and res["rung1b"]["pass"] else 1


def graph_cmd(a):
    g = build_subgraph(read_tsv(a.places), read_tsv(a.edges))
    problems = graph_problems(g)
    if problems:
        sys.exit("graph refused: " + "; ".join(problems))
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(g, f, indent=1)
        f.write("\n")
    print(f"wrote {a.out}: {len(g['nodes'])} nodes, {len(g['edges'])} edges; rung 1b "
          f"{' > '.join(g['rung1b']['route_edids'])} {g['rung1b']['length_m']} m")
    return 0


def route_cmd(a):
    g = load_graph(a.graph)
    print(json.dumps({"rung1a": g["rung1a"], "rung1b": g["rung1b"], "problems": graph_problems(g)}, indent=1))
    return 0


def main(argv=None):
    game = os.environ.get("FO4SF_STARFIELD")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("graph")
    g.add_argument("--places", required=True)
    g.add_argument("--edges", required=True)
    g.add_argument("--out", default=GRAPH)
    r = sub.add_parser("route")
    r.add_argument("--graph", default=GRAPH)
    s = sub.add_parser("stage")
    s.add_argument("--out", required=True)
    s.add_argument("--graph", default=GRAPH)
    for name, rel in (("--starfield", ("Data", "Starfield.esm")),
                      ("--compiler", ("Tools", "Papyrus Compiler", "PapyrusCompiler.exe")),
                      ("--content-resources", ("Tools", "ContentResources.zip"))):
        if game:
            s.add_argument(name, default=os.path.join(game, *rel))
        else:
            s.add_argument(name, required=True)
    s.add_argument("--core", required=True)
    s.add_argument("--raider", required=True)
    fo = sub.add_parser("fold")
    fo.add_argument("--stage", required=True)
    fo.add_argument("--core-dir", required=True)
    fo.add_argument("--out", required=True)
    fo.add_argument("--raider", default=None)
    v = sub.add_parser("verify")
    v.add_argument("--exp-dir", required=True)
    v.add_argument("--plan", required=True)
    v.add_argument("--raider", default=None)
    lg = sub.add_parser("log")
    lg.add_argument("--file", default=LOG)
    lb = sub.add_parser("log1b")
    lb.add_argument("--file", default=LOG)
    a = p.parse_args(argv)
    if a.cmd == "stage":
        stage(a)
        return 0
    return {"graph": graph_cmd, "route": route_cmd, "fold": fold, "verify": verify, "log": log,
            "log1b": log_b}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
