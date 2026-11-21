"""Build A-Life node graphs for any worldspace: import coordinate tables or marker JSON, connect, contract, cap.

A modder starts from points they already have (xEdit exports, map-marker dumps, hand-made spreadsheets) and ends
with the "nodes" and "edges" of a valid config (<= 128 of each, connected):

  read_coordinate_table(path)   CSV/TSV rows -> node dicts (column names are matched loosely, see COLUMNS)
  read_marker_json(path)        a JSON list of markers (or {"markers"|"nodes"|"refs": [...]}) -> node dicts
  read_edge_table(path)         CSV/TSV u,v[,len_m] rows (node ids or indices) -> edge dicts
  select_anchors(nodes, n)      deterministic cut to at most n nodes (non-relays first, farthest-point spread)
  knn_edges(nodes, k)           each node joined to its k nearest, plus shortest bridges until connected
  contract(nodes, edges, keep)  keep only the kept nodes; dropped nodes become summed-length road segments
  cap_edges(nodes, edges, cap)  drop the longest non-bridge edges until at most cap remain
  nodes_from_nw_subgraph(g)     FO4SF scripts/alife/nw_subgraph.json -> nodes/edges
  build_config(...)             nodes + edges + factions + worldspace -> a config dict (validate it with schema)

usage:
  python -m fo4sf.alife.graph_builder <nodes.csv|tsv|json> --template <config.json> --out <config.json>
                                      [--edges <edges.csv>] [--k 3] [--max-nodes 128] [--road-factor 1.15]
      replaces the template's nodes and edges with the imported graph and validates the result (exit 2 if not).
"""
import argparse
import csv
import heapq
import json
import math
import os
import sys

from . import schema

ARRAY_CAP = schema.ARRAY_CAP
COLUMNS = {
    "id": ("id", "node_id", "name", "edid", "editor_id", "editorid", "marker", "label"),
    "x": ("x", "x_m", "x_sf_m", "pos_x", "posx", "position_x"),
    "y": ("y", "y_m", "y_sf_m", "pos_y", "posy", "position_y"),
    "z": ("z", "z_m", "z_sf_m", "pos_z", "posz", "position_z"),
    "kind": ("kind", "type", "node_kind", "class", "smart_terrain_class"),
    "capacity": ("capacity", "cap", "max_squad_cap", "garrison"),
    "initial_owner": ("initial_owner", "owner", "faction", "initial_faction"),
    "spawn_faction": ("spawn_faction", "spawn", "spawns"),
}
# free-text kinds seen in marker dumps and the FO4SF extraction -> schema node kinds
KIND_ALIASES = {
    "relay": "relay", "road": "relay", "junction": "relay", "waypoint": "relay", "": "relay",
    "base": "base", "settlement": "base", "settlement_base": "base", "outpost": "base", "camp": "base",
    "checkpoint": "checkpoint", "military_or_checkpoint": "checkpoint", "territory_landmark": "checkpoint",
    "landmark": "checkpoint", "district": "checkpoint",
    "lair": "lair", "creature_or_ghoul_lair": "lair", "faction_camp_or_dungeon": "lair", "dungeon": "lair",
    "resource": "resource", "resource_industrial": "resource", "industrial": "resource", "market": "resource",
}
DEFAULT_CAPACITY = {"relay": 0, "base": 3, "checkpoint": 2, "lair": 2, "resource": 2}


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def norm_kind(k):
    k = str(k or "").strip().lower()
    if k not in KIND_ALIASES:
        raise ValueError(f"unknown node kind {k!r}")
    return KIND_ALIASES[k]


def _pick(row, field):
    low = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
    for name in COLUMNS[field]:
        if name in low and str(low[name]).strip() != "":
            return low[name]
    return None


def _node_from_row(row, i):
    nid = _pick(row, "id")
    pos = row.get("pos") or row.get("position")
    if isinstance(pos, (list, tuple)) and len(pos) >= 3:
        x, y, z = (_num(v) for v in pos[:3])
    else:
        x, y, z = (_num(_pick(row, k)) for k in ("x", "y", "z"))
    if x is None or y is None:
        raise ValueError(f"row {i}: no x/y coordinates")
    kind = norm_kind(_pick(row, "kind"))
    cap = _pick(row, "capacity")
    cap = DEFAULT_CAPACITY[kind] if cap is None else int(float(cap))
    n = {"id": str(nid).strip() if nid is not None else f"node{i}", "kind": kind, "x": round(x, 2),
         "y": round(y, 2), "z": round(z or 0.0, 2), "capacity": 0 if kind == "relay" else max(1, cap)}
    for k in ("initial_owner", "spawn_faction"):
        v = _pick(row, k)
        if v is not None and str(v).strip().lower() not in ("", "none", "null", "-1", "unheld"):
            n[k] = str(v).strip()
    return n


def _sniff(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        head = f.readline()
    return "\t" if head.count("\t") >= head.count(",") else ","


def read_coordinate_table(path, delimiter=None):
    """Node dicts {id, kind, x, y, z, capacity[, initial_owner, spawn_faction]} from a CSV or TSV file."""
    delimiter = delimiter or _sniff(path)
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [_node_from_row(r, i) for i, r in enumerate(csv.DictReader(f, delimiter=delimiter))]


def read_marker_json(path):
    """Node dicts from a JSON marker list ([{id|edid, x, y, z | pos: [x, y, z], kind?, ...}]) or an object with a
    markers / nodes / refs list."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        for key in ("markers", "nodes", "refs"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise ValueError(f"{schema.path_basename(path)}: no marker list")
    return [_node_from_row(r, i) for i, r in enumerate(data)]


def read_edge_table(path, nodes, delimiter=None):
    """Edge dicts {u, v, len_m} (node indices) from CSV/TSV rows u,v[,len_m]; u/v are node ids or indices.
    A missing length is the 3D distance."""
    index = {n["id"]: i for i, n in enumerate(nodes)}
    delimiter = delimiter or _sniff(path)
    out = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for i, r in enumerate(csv.DictReader(f, delimiter=delimiter)):
            low = {str(k).strip().lower(): str(v).strip() for k, v in r.items() if k is not None}
            ends = []
            for key in (("u", "from", "u_id", "a"), ("v", "to", "v_id", "b")):
                val = next((low[k] for k in key if low.get(k)), None)
                if val in index:
                    ends.append(index[val])
                elif val is not None and val.lstrip("-").isdigit() and 0 <= int(val) < len(nodes):
                    ends.append(int(val))
                else:
                    raise ValueError(f"edge row {i}: unknown node {val!r}")
            length = _num(next((low[k] for k in ("len_m", "length", "len", "dist_m", "dist_sf_m") if low.get(k)),
                               None))
            u, v = ends
            out.append({"u": u, "v": v, "len_m": round(length if length else dist3(nodes[u], nodes[v]), 2)})
    return out


# ------------------------------------------------------------------------------------------------ geometry
def dist3(a, b):
    return math.dist((a["x"], a["y"], a["z"]), (b["x"], b["y"], b["z"]))


def dist2(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


class _DSU:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self.p[max(ra, rb)] = min(ra, rb)
        return True


def select_anchors(nodes, max_nodes=ARRAY_CAP):
    """At most max_nodes of nodes (original order kept): every non-relay first when they fit, the rest chosen by
    farthest-point sampling from the first node, so the kept set spreads over the map. Deterministic."""
    if len(nodes) <= max_nodes:
        return list(nodes)
    primary = [i for i, n in enumerate(nodes) if n.get("kind", "relay") != "relay"]
    relays = [i for i, n in enumerate(nodes) if n.get("kind", "relay") == "relay"]
    if len(primary) >= max_nodes:
        chosen, pool = [primary[0]], primary
    else:
        chosen, pool = list(primary), relays
        if not chosen:
            chosen = [relays[0]]
    best = {i: min(dist2(nodes[i], nodes[c]) for c in chosen) for i in pool}
    picked = set(chosen)
    while len(chosen) < max_nodes:
        cand = max((i for i in pool if i not in picked), key=lambda i: (best[i], -i), default=None)
        if cand is None:
            break
        chosen.append(cand)
        picked.add(cand)
        for j in pool:
            best[j] = min(best[j], dist2(nodes[cand], nodes[j]))
    return [nodes[i] for i in sorted(picked)]


def knn_edges(nodes, k=3, road_factor=1.15, max_len=None):
    """Edges joining each node to its k nearest (3D distance x road_factor), then the shortest remaining pairs
    until the graph is connected (Kruskal). Lengths are rounded to 0.01 m. Deterministic."""
    n = len(nodes)
    pairs = sorted((dist3(nodes[i], nodes[j]), i, j) for i in range(n) for j in range(i + 1, n))
    chosen = set()
    for i in range(n):
        mine = sorted((d, a, b) for d, a, b in pairs if i in (a, b) and (max_len is None or d <= max_len))
        chosen.update((a, b) for _, a, b in mine[:k])
    dsu = _DSU(n)
    for a, b in chosen:
        dsu.union(a, b)
    for d, a, b in pairs:
        if dsu.union(a, b):
            chosen.add((a, b))
    lengths = {(a, b): d for d, a, b in pairs}
    return [{"u": a, "v": b, "len_m": round(lengths[(a, b)] * road_factor, 2)} for a, b in sorted(chosen)]


def contract(nodes, edges, keep, keep_edges=3):
    """The kept nodes (ids or indices, original order) and contracted edges: from each kept node a Dijkstra over
    every edge that never expands past another kept node; each kept pair so reached is a candidate with the summed
    length. Each node keeps its keep_edges shortest candidates, then shortest bridges until connected.
    Raises ValueError when the kept nodes cannot be connected."""
    index = {n["id"]: i for i, n in enumerate(nodes)}
    kept = sorted({index[k] if isinstance(k, str) else int(k) for k in keep})
    pos = {g: i for i, g in enumerate(kept)}
    adj = {}
    for e in edges:
        for a, b in ((e["u"], e["v"]), (e["v"], e["u"])):
            adj.setdefault(a, {})
            adj[a][b] = min(e["len_m"], adj[a].get(b, math.inf))
    cand = {}
    for src in kept:
        dist = {src: 0.0}
        pq = [(0.0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            if u != src and u in pos:
                key = (min(pos[src], pos[u]), max(pos[src], pos[u]))
                cand[key] = min(cand.get(key, math.inf), d)
                continue
            for v, w in adj.get(u, {}).items():
                if d + w < dist.get(v, math.inf):
                    dist[v] = d + w
                    heapq.heappush(pq, (d + w, v))
    chosen = set()
    for i in range(len(kept)):
        mine = sorted((d, key) for key, d in cand.items() if i in key)
        chosen.update(key for _, key in mine[:keep_edges])
    dsu = _DSU(len(kept))
    for a, b in chosen:
        dsu.union(a, b)
    for d, (a, b) in sorted((d, key) for key, d in cand.items()):
        if dsu.union(a, b):
            chosen.add((a, b))
    if len({dsu.find(i) for i in range(len(kept))}) != 1:
        raise ValueError("the kept nodes are not connected by the edges")
    new_nodes = [dict(nodes[g]) for g in kept]
    return new_nodes, [{"u": a, "v": b, "len_m": round(cand[(a, b)], 2)} for a, b in sorted(chosen)]


def _bridges_ok_to_drop(n, edges, drop):
    rest = [e for i, e in enumerate(edges) if i != drop]
    return len(schema.connected_from(n, rest, 0)) == n


def cap_edges(nodes, edges, cap=ARRAY_CAP):
    """Edges with the longest non-bridge ones removed until at most cap remain (connectivity kept)."""
    edges = list(edges)
    n = len(nodes)
    while len(edges) > cap:
        for i in sorted(range(len(edges)), key=lambda i: (-edges[i]["len_m"], i)):
            if _bridges_ok_to_drop(n, edges, i):
                del edges[i]
                break
        else:
            raise ValueError(f"cannot cut {len(edges)} edges to {cap} without disconnecting the graph")
    return edges


def auto_graph(nodes, edges=None, max_nodes=ARRAY_CAP, k=3, road_factor=1.15):
    """Nodes and edges that fit the config caps: with edges, the kept anchors are contracted over them; without,
    the anchors are joined by knn_edges."""
    anchors = select_anchors(nodes, max_nodes)
    if edges:
        if len(anchors) < len(nodes):
            ids = {n["id"] for n in anchors}
            anchors, edges = contract(nodes, edges, [i for i, n in enumerate(nodes) if n["id"] in ids], k)
    else:
        edges = knn_edges(anchors, k, road_factor)
    return anchors, cap_edges(anchors, edges)


# ------------------------------------------------------------------------------------------------ FO4SF import
NW_FACTION_MAP = {"Settlers_Minutemen": "minutemen", "Raiders": "raiders", "FeralGhouls": "scavengers"}


def nodes_from_nw_subgraph(g, faction_map=None, spawn_kinds=("base", "lair")):
    """FO4SF's nw_subgraph.json (scripts/alife) as nodes and edges: kinds mapped through KIND_ALIASES, cap kept,
    owners mapped through faction_map (unmapped: unowned); owned nodes of spawn_kinds become spawn bases."""
    faction_map = NW_FACTION_MAP if faction_map is None else faction_map
    nodes = []
    for i, n in enumerate(g["nodes"]):
        kind = norm_kind(n.get("kind"))
        owner = faction_map.get(n.get("faction", ""))
        nd = {"index": i, "id": n.get("edid") or n["id"], "kind": kind, "x": n["x"], "y": n["y"], "z": n["z"],
              "capacity": int(n.get("cap", DEFAULT_CAPACITY[kind])) if kind != "relay" else 0,
              "initial_owner": owner, "spawn_faction": owner if owner and kind in spawn_kinds else None}
        if nd["capacity"] <= 0 and kind != "relay":
            nd["capacity"] = 1
        nodes.append(nd)
    edges = [{"u": e["u"], "v": e["v"], "len_m": e["len_m"]} for e in g["edges"]]
    return nodes, edges


def build_config(nodes, edges, *, mod_name, plugin_name, worldspace, factions, masters=None, simulation=None,
                 light_master=True, editor_prefix=None):
    """A config dict (schema_version 1) from parts; nodes get their index. Validate it with schema."""
    masters = list(masters) if masters else [schema.BASE_MASTER]
    cfg = {"schema_version": schema.SCHEMA_VERSION, "mod_name": mod_name, "plugin_name": plugin_name,
           "light_master": light_master, "masters": masters, "worldspace": dict(worldspace),
           "simulation": {**schema.SIM_DEFAULTS, **(simulation or {})},
           "factions": [dict(f, index=i) for i, f in enumerate(factions)],
           "nodes": [dict(n, index=i) for i, n in enumerate(nodes)],
           "edges": [dict(e) for e in edges]}
    if editor_prefix:
        cfg["editor_prefix"] = editor_prefix
    return cfg


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m fo4sf.alife.graph_builder",
                                 description="import a coordinate table or marker JSON into an A-Life config")
    ap.add_argument("points")
    ap.add_argument("--template", required=True, help="config whose factions/worldspace/simulation are kept")
    ap.add_argument("--out", required=True)
    ap.add_argument("--edges")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--max-nodes", type=int, default=ARRAY_CAP)
    ap.add_argument("--road-factor", type=float, default=1.15)
    a = ap.parse_args(argv)
    try:
        if a.points.lower().endswith(".json"):
            nodes = read_marker_json(a.points)
        else:
            nodes = read_coordinate_table(a.points)
        edges = read_edge_table(a.edges, nodes) if a.edges else None
        nodes, edges = auto_graph(nodes, edges, min(a.max_nodes, ARRAY_CAP), a.k, a.road_factor)
        cfg = schema.load_alife_config(a.template)
    except (OSError, ValueError, KeyError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    cfg["nodes"] = [dict(n, index=i) for i, n in enumerate(nodes)]
    cfg["edges"] = edges
    problems = schema.validate_alife_config(cfg)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cfg, f, indent=1)
        f.write("\n")
    print(f"wrote {a.out}: {len(nodes)} nodes, {len(edges)} edges")
    if problems:
        print("still invalid (edit owners/spawns, then validate):\n  " + "\n  ".join(problems), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
