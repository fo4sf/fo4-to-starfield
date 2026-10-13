"""Read-only navmesh analysis of a vanilla Starfield interior cell, for the npc_nav control (N0b): the cell's NAVM
triangles and their connectivity graph, the placed objects that stand on them, and A/B pairs on which a commanded walk
can be told from an actor's own wandering.

usage:
  python scripts/actors/navmesh_points.py analyze --esm <Starfield.esm> --out <points.json> [--cell QASmoke]
         [--png <top-down.png>] [--old-a -8,-4,0 --old-b 5,10,0] [--trace <npc_nav queue dir>]...
  python scripts/actors/navmesh_points.py show --points <points.json>

What `analyze` does (offline, deterministic, nothing written but --out and --png):
  1. finds the interior CELL with that editor id, its NAVM records (NVNM parsed by src/fo4sf/navmesh.py) and its placed
     references, then their base records (type, editor id, record flags, OBND: Starfield stores 6 f32 in metres);
  2. builds the triangle graph: two triangles are joined by a shared edge (edge value >= 0) or by an edge link to
     another navmesh of the same cell; reports the connected components (triangles, area, bounds, links leaving the
     cell);
  3. places every reference's OBND box (scaled, rotated as the game does: Bethesda angles, X then Y then Z, clockwise)
     and sorts it: light, marker (STAT record flag 0x00800000, e.g. the COC marker), floor (top at most STEP above the
     navmesh), overhead (bottom at least AGENT_HEIGHT above it) or obstacle; obstacles become 2D footprints;
  4. free space: navmesh minus the obstacles grown by AGENT_RADIUS, on a GRID_M grid, with the clearance of every cell
     (distance to the nearest obstacle edge or open navmesh border);
  5. measures the old pair and every candidate pair: on the navmesh, component, straight distance, the navmesh path
     (funnel over the triangle corridor: what the path planner sees, obstacles are not cut out of this navmesh), the
     free-space path (straight when the segment is clear, else grid A* pulled tight), the clearance along the segment
     and at its ends (on the grid, which ranks, and exact, to the obstacle and open-border edges), the "attractor
     progress" (how much closer to B an actor gets by going from A to the arrival marker) and the
     "drift progress" (the same for the worst of: the arrival marker, the navmesh centre, every traced read: fixed
     places only; a wander that moves with the actor is npc_control.py's `wander` table);
  6. keeps pairs that are PAIR_MIN..PAIR_MAX apart, both ends END_CLEAR clear, the segment SEG_CLEAR clear, free path at
     most DETOUR_MAX x straight, A at least A_FROM_ARRIVAL and B at least B_FROM_ARRIVAL from the arrival marker, B at
     least B_FROM_TRACE from every position an actor was read at in the traced runs (--trace: the npc_nav queues of the
     old control), drift progress at most DRIFT_MAX; ranks them (score below) and writes the best ("chosen") and the
     runners-up.
--trace reads only obs.json files of a queue (tests/<id>/a<n>/obs.json): the positions qstep.ps1 read in game.
"""
import argparse
import glob
import heapq
import json
import math
import os
import struct
import sys
from collections import deque

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "src"))
from fo4sf import navmesh as nm  # noqa: E402
from fo4sf.exterior import ref_matrix  # noqa: E402
from fo4sf.fo4land import Plugin, iter_items, iter_subrecords, record_data, zstring  # noqa: E402

VERSION = 2
# the body: raider_map.HUMAN_BOUNDS is +-0.31 m wide and 1.8 m tall (a human NPC_'s OBND); 4 cm of margin
AGENT_RADIUS = 0.35
AGENT_HEIGHT = 1.8
STEP = 0.3                    # a box whose top is at most this far above the navmesh is floor, not an obstacle
GRID_M = 0.1                  # free-space grid
LATTICE_M = 0.5               # candidate points
# N0b's rule (npc_control.py) wants the pair less 6 m (radius 3 m, pre-command allowance 3 m) of walk after the
# command; uncommanded actors moved up to 14.1 m from t0 (npc_nav_n1c N1c_cross_ptr) and came up to 9.5 m towards the
# player (N1c_ptr_player): 22 m leaves 16 m, QASmoke's room fits about 24 m with the ends clear
PAIR_MIN, PAIR_MAX = 22.0, 26.0
END_CLEAR = 2.5               # placeatme puts the actor up to ~1.7 m from the player (N0: 1.3-1.7 m); handle_tol 2 m
SEG_CLEAR = 1.0               # the straight segment keeps a body and a margin away from every obstacle and border
DETOUR_MAX = 1.05
B_FROM_ARRIVAL = 12.0         # an actor idling at the arrival marker is not most of the way to the player
B_FROM_TRACE = 10.0           # every N0 read stayed >= 10.8 m from the old B; B is kept as far from all of them
A_FROM_ARRIVAL = 8.0          # A away from the player's arrival (the COC marker), the middle of N0's wander
DRIFT_MAX = 12.0              # going to a fixed place actors went on their own leaves >= 6 m of an 18 m walk
TARGET_M = 24.0               # as long as the room allows: the longer the walk, the wider the margin over wander
MARKER_FLAG = 0x00800000      # STAT record flag "is marker" (COCMarkerHeading 00000032 carries it, flags 00800004)
SANDBOX_TYPES = ("FURN", "IDLM")
TOP_N = 8


# ------------------------------------------------------------------------------------------------------------ geometry
def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def convex_hull(pts):
    """Counter-clockwise hull of 2D points (monotone chain), without repeated or collinear points."""
    p = sorted({(round(float(x), 6), round(float(y), 6)) for x, y in pts})
    if len(p) <= 2:
        return p
    lo, hi = [], []
    for q in p:
        while len(lo) >= 2 and _cross(lo[-2], lo[-1], q) <= 0:
            lo.pop()
        lo.append(q)
    for q in reversed(p):
        while len(hi) >= 2 and _cross(hi[-2], hi[-1], q) <= 0:
            hi.pop()
        hi.append(q)
    return lo[:-1] + hi[:-1]


def polygon_area(poly):
    return 0.5 * abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                         for i in range(len(poly))))


def box_corners(obnd, pos, rot, scale=1.0):
    """The 8 world corners (8, 3) of an OBND box (x1, y1, z1, x2, y2, z2) placed at pos with rot (radians)."""
    x1, y1, z1, x2, y2, z2 = obnd
    m = np.array(ref_matrix(rot), np.float64).reshape(3, 3)
    c = np.array([(x, y, z) for x in (x1, x2) for y in (y1, y2) for z in (z1, z2)], np.float64) * scale
    return c @ m.T + np.asarray(pos, np.float64)


def seg_dist(px, py, ax, ay, bx, by):
    """Distance of points (arrays) to the segment a-b."""
    dx, dy = bx - ax, by - ay
    ln = dx * dx + dy * dy
    t = np.zeros_like(px) if ln == 0 else np.clip(((px - ax) * dx + (py - ay) * dy) / ln, 0.0, 1.0)
    return np.hypot(px - (ax + t * dx), py - (ay + t * dy))


def seg_seg_dist(a, b, c, d):
    """Exact 2D distance between the segments a-b and c-d (0 when they cross or touch)."""
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    if (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0) and 0 not in (o1, o2, o3, o4):
        return 0.0

    def pt(p, q, r):
        return float(seg_dist(np.array([p[0]]), np.array([p[1]]), q[0], q[1], r[0], r[1])[0])
    return min(pt(a, c, d), pt(b, c, d), pt(c, a, b), pt(d, a, b))


def inside_convex(px, py, poly):
    """Points (arrays) inside a counter-clockwise convex polygon (on the border counts)."""
    ok = np.ones(px.shape, bool)
    for i in range(len(poly)):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % len(poly)]
        ok &= (bx - ax) * (py - ay) - (by - ay) * (px - ax) >= -1e-9
    return ok


# ------------------------------------------------------------------------------------------------------------ navmesh
def tri_xy(m, i):
    return m.vertices[m.triangles["v"][i]][:, :2]


def tri_area(m, i):
    p = tri_xy(m, i)
    return 0.5 * abs(_cross(p[0], p[1], p[2]))


def neighbours(navs, key):
    """[(other key, edge k of this triangle)] across shared edges and same-cell edge links; links to navmeshes that are
    not in `navs` are returned with other None (they leave the cell)."""
    fid, ti = key
    m = navs[fid]
    fl = int(m.triangles["flags"][ti])
    out = []
    for k in range(3):
        e = int(m.triangles["e"][ti][k])
        if fl & nm.EDGE_LINK_BITS[k]:
            L = m.links[e]
            other = (int(L["navmesh"]), int(L["tri"]))
            out.append((other if other[0] in navs else None, k))
        elif e >= 0:
            out.append(((fid, e), k))
    return out


def components(navs):
    """Connected components of the triangle graph: [{'triangles': [(fid, tri)], 'exits': n}], largest area first."""
    seen, comps = set(), []
    for fid in sorted(navs):
        for ti in range(len(navs[fid].triangles)):
            if (fid, ti) in seen:
                continue
            seen.add((fid, ti))
            q, tris, exits = deque([(fid, ti)]), [], 0
            while q:
                cur = q.popleft()
                tris.append(cur)
                for other, _k in neighbours(navs, cur):
                    if other is None:
                        exits += 1
                    elif other not in seen:
                        seen.add(other)
                        q.append(other)
            comps.append({"triangles": sorted(tris), "exits": exits})
    for c in comps:
        c["area_m2"] = sum(tri_area(navs[f], i) for f, i in c["triangles"])
        pts = np.concatenate([navs[f].vertices[navs[f].triangles["v"][i]] for f, i in c["triangles"]])
        c["bounds"] = [pts.min(0).tolist(), pts.max(0).tolist()]
    comps.sort(key=lambda c: (-c["area_m2"], c["triangles"][0]))
    return comps


def boundary_edges(navs):
    """2D segments ((x0, y0), (x1, y1)) of triangle edges with no neighbour (open navmesh border)."""
    out = []
    for fid in sorted(navs):
        m = navs[fid]
        for ti in range(len(m.triangles)):
            fl = int(m.triangles["flags"][ti])
            for k in range(3):
                e = int(m.triangles["e"][ti][k])
                if e < 0 and not fl & nm.EDGE_LINK_BITS[k]:
                    p = tri_xy(m, ti)
                    out.append((tuple(p[k]), tuple(p[(k + 1) % 3])))
    return out


def tri_of(navs, xy, z=None):
    hit = nm.locate(navs, xy[0], xy[1], z)
    return (hit[0][1], hit[0][2]) if hit else None


def portal(navs, a, b):
    """Shared edge (p, q) of adjacent triangles a -> b, 2D."""
    for other, k in neighbours(navs, a):
        if other == b:
            p = tri_xy(navs[a[0]], a[1])
            return tuple(p[k]), tuple(p[(k + 1) % 3])
    raise ValueError(f"{a} and {b} are not adjacent")


def corridor(navs, start, goal):
    """Triangles from start to goal by Dijkstra over portal midpoints (None if not connected)."""
    sa, ga = tri_of(navs, start), tri_of(navs, goal)
    if sa is None or ga is None:
        return None
    best, prev, pq = {sa: 0.0}, {sa: None}, [(0.0, sa, tuple(start[:2]))]
    while pq:
        d, cur, at = heapq.heappop(pq)
        if cur == ga:
            break
        if d > best.get(cur, math.inf):
            continue
        for other, _k in neighbours(navs, cur):
            if other is None:
                continue
            p, q = portal(navs, cur, other)
            mid = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
            nd = d + math.hypot(mid[0] - at[0], mid[1] - at[1])
            if nd < best.get(other, math.inf):
                best[other], prev[other] = nd, cur
                heapq.heappush(pq, (nd, other, mid))
    if ga not in prev:
        return None
    out, cur = [], ga
    while cur is not None:
        out.append(cur)
        cur = prev[cur]
    return out[::-1]


def _area2(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def funnel(portals):
    """String pulling over portals [(left, right)], the first and last being (start, start) and (goal, goal): the
    shortest 2D path through the corridor (simple stupid funnel algorithm)."""
    pts = [portals[0][0]]
    apex = left = right = portals[0][0]
    apex_i = left_i = right_i = 0
    i = 1
    while i < len(portals):
        lft, rgt = portals[i]
        if _area2(apex, right, rgt) >= 0:                  # right side: rgt is not outside the funnel to the right
            if apex == right or _area2(apex, left, rgt) < 0:
                right, right_i = rgt, i                  # tighten
            else:                                        # crossed the left side: left becomes the new apex
                pts.append(left)
                apex, apex_i = left, left_i
                left = right = apex
                left_i = right_i = apex_i
                i = apex_i + 1
                continue
        if _area2(apex, left, lft) <= 0:
            if apex == left or _area2(apex, right, lft) > 0:
                left, left_i = lft, i
            else:
                pts.append(right)
                apex, apex_i = right, right_i
                left = right = apex
                left_i = right_i = apex_i
                i = apex_i + 1
                continue
        i += 1
    if pts[-1] != portals[-1][0]:
        pts.append(portals[-1][0])
    return pts


def navmesh_path(navs, start, goal):
    """(length, points) of the shortest path through the navmesh corridor, or None when start and goal are not
    connected. Ignores placed objects: the path planner's view of a navmesh that has no holes for them."""
    tris = corridor(navs, start, goal)
    if tris is None:
        return None
    s, g = (float(start[0]), float(start[1])), (float(goal[0]), float(goal[1]))
    portals = [(s, s)]
    for a, b in zip(tris, tris[1:]):
        p, q = portal(navs, a, b)
        c = tri_xy(navs[a[0]], a[1]).mean(0)
        # seen from triangle a looking through the edge: p left or right
        if _area2(c, p, q) > 0:                           # c, p, q counter-clockwise: q is left of p
            portals.append(((float(q[0]), float(q[1])), (float(p[0]), float(p[1]))))
        else:
            portals.append(((float(p[0]), float(p[1])), (float(q[0]), float(q[1]))))
    portals.append((g, g))
    pts = funnel(portals)
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:])), pts


# ------------------------------------------------------------------------------------------------------------ objects
def classify(base, corners, floor_z):
    """'light' | 'marker' | 'sandbox' | 'floor' | 'overhead' | 'obstacle' for a placed reference."""
    if base is None:
        return "unknown"
    if base["type"] == "LIGH":
        return "light"
    if base["type"] in SANDBOX_TYPES:
        return "sandbox"
    if base["type"] == "STAT" and base["flags"] & MARKER_FLAG:
        return "marker"
    if base.get("obnd") is None:
        return "unknown"
    z0, z1 = float(corners[:, 2].min()), float(corners[:, 2].max())
    if z1 <= floor_z + STEP:
        return "floor"
    if z0 >= floor_z + AGENT_HEIGHT:
        return "overhead"
    return "obstacle"


def place_objects(refs, bases, navs):
    """Every reference with its base, box, class and 2D footprint (obstacles and sandbox objects)."""
    allv = np.concatenate([m.vertices for m in navs.values()]) if navs else np.zeros((1, 3))
    zmin = float(allv[:, 2].min())
    out = []
    for r in refs:
        b = bases.get(r["base"])
        o = {"form_id": f"{r['fid']:08X}", "type": r["type"], "base": f"{r['base']:08X}",
             "base_type": b["type"] if b else None, "edid": b["edid"] if b else "",
             "pos": [round(x, 3) for x in r["pos"]], "rot": [round(x, 4) for x in r["rot"]], "scale": r["scale"],
             "persistent": r["persistent"]}
        if b and b.get("obnd") is not None:
            c = box_corners(b["obnd"], r["pos"], r["rot"], r["scale"])
            hit = tri_of(navs, c[:, :2].mean(0)) if navs else None
            fz = float(navs[hit[0]].vertices[navs[hit[0]].triangles["v"][hit[1]]][:, 2].mean()) if hit else zmin
            o["z"] = [round(float(c[:, 2].min()), 3), round(float(c[:, 2].max()), 3)]
            o["footprint"] = [[round(x, 3), round(y, 3)] for x, y in convex_hull(c[:, :2])]
            o["class"] = classify(b, c, fz)
        else:
            o["class"] = classify(b, None, zmin) if b and b["type"] in ("LIGH",) + SANDBOX_TYPES else "unknown"
            if b and b["type"] == "STAT" and b["flags"] & MARKER_FLAG:
                o["class"] = "marker"
        out.append(o)
    return out


# ---------------------------------------------------------------------------------------------------------- free space
class FreeSpace:
    """Navmesh cells (GRID_M) and their clearance: the distance to the nearest obstacle footprint or open navmesh
    border (0 inside an obstacle). free = on the navmesh with clearance >= AGENT_RADIUS."""

    def __init__(self, navs, obstacles, grid=GRID_M, agent=AGENT_RADIUS):
        allv = np.concatenate([m.vertices for m in navs.values()])
        lo, hi = allv[:, :2].min(0) - grid, allv[:, :2].max(0) + grid
        self.grid, self.agent, self.lo = grid, agent, lo
        self.nx, self.ny = int(math.ceil((hi[0] - lo[0]) / grid)), int(math.ceil((hi[1] - lo[1]) / grid))
        xs = lo[0] + (np.arange(self.nx) + 0.5) * grid
        ys = lo[1] + (np.arange(self.ny) + 0.5) * grid
        self.X, self.Y = np.meshgrid(xs, ys)                 # [row y, col x]
        on = np.zeros(self.X.shape, bool)
        for m in navs.values():
            for ti in range(len(m.triangles)):
                p = tri_xy(m, ti)
                if _cross(p[0], p[1], p[2]) < 0:
                    p = p[::-1]
                c0, c1 = self._col(p[:, 0].min()), self._col(p[:, 0].max())
                r0, r1 = self._row(p[:, 1].min()), self._row(p[:, 1].max())
                sx, sy = self.X[r0:r1 + 1, c0:c1 + 1], self.Y[r0:r1 + 1, c0:c1 + 1]
                on[r0:r1 + 1, c0:c1 + 1] |= inside_convex(sx, sy, [tuple(q) for q in p])
        clear = np.full(self.X.shape, np.inf)
        self.edges, self.polys = [], []                       # the exact geometry, for exact_clearance
        for a, b in boundary_edges(navs):
            clear = np.minimum(clear, seg_dist(self.X, self.Y, a[0], a[1], b[0], b[1]))
            self.edges.append((a, b))
        for o in obstacles:
            poly = [tuple(q) for q in o["footprint"]]
            if len(poly) < 3:
                continue
            for i in range(len(poly)):
                a, b = poly[i], poly[(i + 1) % len(poly)]
                clear = np.minimum(clear, seg_dist(self.X, self.Y, a[0], a[1], b[0], b[1]))
                self.edges.append((a, b))
            self.polys.append(poly)
            clear[inside_convex(self.X, self.Y, poly)] = 0.0
        clear[~on] = 0.0
        self.on, self.clear = on, clear
        self.free = on & (clear >= agent)

    def _col(self, x):
        return int(min(self.nx - 1, max(0, math.floor((x - self.lo[0]) / self.grid))))

    def _row(self, y):
        return int(min(self.ny - 1, max(0, math.floor((y - self.lo[1]) / self.grid))))

    def cell(self, p):
        return self._row(p[1]), self._col(p[0])

    def clearance(self, p):
        return float(self.clear[self.cell(p)])

    def segment_clearance(self, a, b, step=0.05):
        n = max(2, int(math.ceil(math.dist(a[:2], b[:2]) / step)) + 1)
        t = np.linspace(0.0, 1.0, n)
        xs, ys = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        cols = np.clip(np.floor((xs - self.lo[0]) / self.grid).astype(int), 0, self.nx - 1)
        rows = np.clip(np.floor((ys - self.lo[1]) / self.grid).astype(int), 0, self.ny - 1)
        return float(self.clear[rows, cols].min())

    def exact_clearance(self, a, b=None):
        """The exact distance (no grid) of the point a, or the segment a-b, to the nearest obstacle footprint edge or
        open navmesh border edge; 0 when it touches or enters an obstacle. The grid values (clearance,
        segment_clearance) rank the pairs; this one is reported next to them."""
        b = a if b is None else b
        for poly in self.polys:
            for p in (a, b):
                if inside_convex(np.array([p[0]]), np.array([p[1]]), poly)[0]:
                    return 0.0
        return float(min((seg_seg_dist(a, b, e0, e1) for e0, e1 in self.edges), default=math.inf))

    def labels(self):
        """Connected components of the free cells (4-neighbour): (label array, -1 = not free; [cells per label])."""
        lab = np.full(self.free.shape, -1, int)
        sizes = []
        for r0, c0 in zip(*np.nonzero(self.free)):
            if lab[r0, c0] >= 0:
                continue
            k = len(sizes)
            lab[r0, c0] = k
            q, n = deque([(r0, c0)]), 0
            while q:
                r, c = q.popleft()
                n += 1
                for rr, cc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                    if 0 <= rr < self.ny and 0 <= cc < self.nx and self.free[rr, cc] and lab[rr, cc] < 0:
                        lab[rr, cc] = k
                        q.append((rr, cc))
            sizes.append(n)
        return lab, sizes

    def path(self, a, b):
        """Length of the free-space path a -> b: the straight segment when it keeps AGENT_RADIUS clear, else A* over
        the 8-neighbour free grid pulled tight (greedy line of sight); None when not connected."""
        if self.segment_clearance(a, b) >= self.agent:
            return math.dist(a[:2], b[:2])
        s, g = self.cell(a), self.cell(b)
        if not (self.free[s] and self.free[g]):
            return None
        h = self.grid

        def est(rc):
            return math.hypot(rc[0] - g[0], rc[1] - g[1]) * h
        best, prev, pq = {s: 0.0}, {s: None}, [(est(s), 0.0, s)]
        while pq:
            _f, d, cur = heapq.heappop(pq)
            if cur == g:
                break
            if d > best[cur]:
                continue
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if not (dr or dc):
                        continue
                    nb = (cur[0] + dr, cur[1] + dc)
                    if not (0 <= nb[0] < self.ny and 0 <= nb[1] < self.nx) or not self.free[nb]:
                        continue
                    nd = d + h * math.hypot(dr, dc)
                    if nd < best.get(nb, math.inf):
                        best[nb], prev[nb] = nd, cur
                        heapq.heappush(pq, (nd + est(nb), nd, nb))
        if g not in prev:
            return None
        cells, cur = [], g
        while cur is not None:
            cells.append(cur)
            cur = prev[cur]
        pts = [(float(self.X[c]), float(self.Y[c])) for c in cells[::-1]]
        pts[0], pts[-1] = (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))
        pulled, i = [pts[0]], 0
        while i < len(pts) - 1:
            j = len(pts) - 1
            while j > i + 1 and self.segment_clearance(pts[i], pts[j]) < self.agent:
                j -= 1
            pulled.append(pts[j])
            i = j
        return sum(math.dist(p, q) for p, q in zip(pulled, pulled[1:]))


# ------------------------------------------------------------------------------------------------------------ pairs
def centroid(navs, comp):
    """Area-weighted 2D centroid of a component's triangles."""
    s, cx, cy = 0.0, 0.0, 0.0
    for f, i in comp["triangles"]:
        ar = tri_area(navs[f], i)
        c = tri_xy(navs[f], i).mean(0)
        s, cx, cy = s + ar, cx + ar * c[0], cy + ar * c[1]
    return (cx / s, cy / s, 0.0) if s else (0.0, 0.0, 0.0)


def drift(a, b, attractors):
    """(progress, attractor index): the most an actor at A gets closer to B by going to one of the attractors instead
    of walking to B (the arrival marker, the navmesh centre, the places actors were read at in the traced runs)."""
    if not attractors:
        return None, None
    ds = [math.dist(b[:2], x[:2]) for x in attractors]
    k = int(np.argmin(ds))
    return math.dist(a[:2], b[:2]) - ds[k], k


def measure(navs, comps, fs, a, b, arrival=None, trace=(), attractors=None):
    """Everything known offline about one A/B pair (horizontal metres). attractors: drift() targets (default: the
    arrival and the trace)."""
    comp_of = {k: i for i, c in enumerate(comps) for k in c["triangles"]}
    ta, tb = tri_of(navs, a), tri_of(navs, b)
    d = math.dist(a[:2], b[:2])
    np_ = navmesh_path(navs, a, b) if ta and tb else None
    fp = fs.path(a, b)
    out = {"a": [round(float(x), 3) for x in a], "b": [round(float(x), 3) for x in b], "distance": round(d, 3),
           "a_on_navmesh": ta is not None, "b_on_navmesh": tb is not None,
           "a_tri": [f"{ta[0]:08X}", ta[1]] if ta else None, "b_tri": [f"{tb[0]:08X}", tb[1]] if tb else None,
           "a_component": comp_of.get(ta), "b_component": comp_of.get(tb),
           "same_component": ta is not None and comp_of.get(ta) == comp_of.get(tb),
           "navmesh_path": round(np_[0], 3) if np_ else None,
           "navmesh_path_ratio": round(np_[0] / d, 4) if np_ and d else None,
           "free_path": round(fp, 3) if fp is not None else None,
           "free_path_ratio": round(fp / d, 4) if fp is not None and d else None,
           "a_clearance": round(fs.clearance(a), 3), "b_clearance": round(fs.clearance(b), 3),
           "segment_clearance": round(fs.segment_clearance(a, b), 3),
           "a_clearance_exact": round(fs.exact_clearance(a[:2]), 3),
           "b_clearance_exact": round(fs.exact_clearance(b[:2]), 3),
           "segment_clearance_exact": round(fs.exact_clearance(a[:2], b[:2]), 3)}
    if arrival is not None:
        out["a_from_arrival"] = round(math.dist(a[:2], arrival[:2]), 3)
        out["b_from_arrival"] = round(math.dist(b[:2], arrival[:2]), 3)
        out["attractor_progress"] = round(d - math.dist(b[:2], arrival[:2]), 3)
    if trace:
        out["b_from_trace"] = round(min(math.dist(b[:2], p[:2]) for p in trace), 3)
    if attractors is None:
        attractors = ([arrival] if arrival is not None else []) + list(trace)
    dp, k = drift(a, b, attractors)
    if dp is not None:
        out["drift_progress"] = round(dp, 3)
        out["drift_to"] = r3(attractors[k][:2])
    return out


def score(m):
    """Lower is better: a distance near TARGET_M (the longer the walk, the more of it lies beyond what actors moved on
    their own; npc_control.rule_for asks for the pair less 6 m), little to gain by drifting to
    where actors went on their own (drift_progress, already capped at DRIFT_MAX; a drift away from B is no better than
    none), wide margins at both ends and along the way, B far from the traced reads, A away from the arrival marker.
    Every term saturates, so no single one buys a pair out of the others."""
    return (0.25 * max(m.get("drift_progress", m.get("attractor_progress", 0.0)), 0.0)
            + 0.5 * abs(m["distance"] - TARGET_M)
            - 0.25 * min(m["a_clearance"], 4.0) - 0.25 * min(m["b_clearance"], 4.0)
            - 0.25 * min(m.get("b_from_trace", 16.0), 16.0) - 0.25 * min(m["segment_clearance"], 4.0)
            - 0.25 * min(m.get("a_from_arrival", 16.0), 16.0))


def pick_pairs(navs, comps, fs, arrival, trace=(), lattice=LATTICE_M, top=TOP_N, attractors=None):
    """(ranked pairs, counts of what each filter left). attractors: drift() targets, default the arrival, the
    centre of the largest component and the trace."""
    if attractors is None:
        attractors = [tuple(arrival)] + ([centroid(navs, comps[0])] if comps else []) + [tuple(p) for p in trace]
    lab, _sizes = fs.labels()
    lo = fs.lo
    xs = np.arange(math.ceil(lo[0] / lattice) * lattice, lo[0] + fs.nx * fs.grid, lattice)
    ys = np.arange(math.ceil(lo[1] / lattice) * lattice, lo[1] + fs.ny * fs.grid, lattice)
    pts = [(round(float(x), 3), round(float(y), 3)) for y in ys for x in xs]
    pts = [p for p in pts if fs.clearance(p) >= END_CLEAR]
    counts = {"lattice_points_clear": len(pts)}
    arr = np.asarray(arrival[:2], np.float64)
    tr = np.asarray([p[:2] for p in trace], np.float64) if len(trace) else None
    at = np.asarray([p[:2] for p in attractors], np.float64)
    P = np.asarray(pts, np.float64)
    zs = {p: (nm.locate(navs, p[0], p[1]) or [(0, 0, 0, 0.0)])[0][3] for p in pts}
    from_arr = np.hypot(P[:, 0] - arr[0], P[:, 1] - arr[1])
    bok = from_arr >= B_FROM_ARRIVAL
    btr = (np.min(np.hypot(P[:, None, 0] - tr[None, :, 0], P[:, None, 1] - tr[None, :, 1]), axis=1)
           if tr is not None else np.full(len(pts), 16.0))
    if tr is not None:
        bok &= btr >= B_FROM_TRACE
    counts["b_candidates"] = int(bok.sum())
    aok = from_arr >= A_FROM_ARRIVAL
    counts["a_candidates"] = int(aok.sum())
    D = np.hypot(P[:, None, 0] - P[None, :, 0], P[:, None, 1] - P[None, :, 1])
    near_b = np.min(np.hypot(P[:, None, 0] - at[None, :, 0], P[:, None, 1] - at[None, :, 1]), axis=1)
    dr = D - near_b[None, :]                                                    # [i = A, j = B]
    ok = (D >= PAIR_MIN) & (D <= PAIR_MAX) & aok[:, None] & bok[None, :] & (dr <= DRIFT_MAX)
    ia, ib = np.nonzero(ok)
    counts["pairs_distance_ends_drift"] = int(len(ia))
    clear = np.array([fs.clearance(p) for p in pts])
    rows = []
    for i, j in zip(ia, ib):
        a, b = pts[i], pts[j]
        if lab[fs.cell(a)] < 0 or lab[fs.cell(a)] != lab[fs.cell(b)]:
            continue
        sc = fs.segment_clearance(a, b)
        if sc < SEG_CLEAR:
            continue
        cheap = {"drift_progress": float(dr[i, j]), "distance": float(D[i, j]), "a_clearance": float(clear[i]),
                 "b_clearance": float(clear[j]), "b_from_trace": float(btr[j]), "segment_clearance": sc,
                 "a_from_arrival": float(from_arr[i])}
        rows.append((round(score(cheap), 4), pts[i], pts[j]))
    counts["pairs_clear_segment"] = len(rows)
    rows.sort()
    out = []
    for _s, pa, pb in rows:                        # the full measure (navmesh corridor, free path) for the best only
        a, b = (pa[0], pa[1], zs[pa]), (pb[0], pb[1], zs[pb])
        m = measure(navs, comps, fs, a, b, arrival, trace, attractors)
        if not m["same_component"] or m["free_path_ratio"] is None or m["free_path_ratio"] > DETOUR_MAX:
            continue
        m["score"] = round(score(m), 4)
        out.append(m)
        if len(out) >= top:
            break
    counts["pairs_ranked"] = len(out)
    out.sort(key=lambda m: (m["score"], m["a"], m["b"]))
    return out, counts


# ------------------------------------------------------------------------------------------------------------ reading
def read_cell(plugin, edid):
    """(cell form id, {navm fid: Nvnm}, [ref dicts]) of the interior CELL with this editor id."""
    s, e = plugin.top_group(b"CELL")

    def find(s, e):
        pending = None
        for it in iter_items(plugin.buf, s, e):
            if it[0] == "GRUP":
                _g, off, gend, label, gtype = it
                if gtype in (2, 3):
                    r = find(off + 24, gend)
                    if r:
                        return r
                elif gtype == 6 and pending is not None and struct.unpack("<I", label)[0] == pending:
                    return pending, off + 24, gend
                continue
            typ, off, _flags, fid = it
            if typ == b"CELL":
                fields = iter_subrecords(record_data(plugin.buf, off))
                name = next((zstring(d) for sig, d in fields if sig == b"EDID"), "")
                pending = fid if name.lower() == edid.lower() else None
        return None
    hit = find(s, e)
    if not hit:
        raise KeyError(f"interior cell {edid!r} not found")
    cfid, cs, ce = hit
    navs, refs = {}, []

    def children(s, e, persistent):
        for it in iter_items(plugin.buf, s, e):
            if it[0] == "GRUP":
                children(it[1] + 24, it[2], it[4] == 8)
                continue
            typ, off, _flags, fid = it
            if typ == b"NAVM":
                for sig, d in iter_subrecords(record_data(plugin.buf, off)):
                    if sig == b"NVNM":
                        navs[fid] = nm.parse(bytes(d))
            elif typ in (b"REFR", b"ACHR"):
                r = {"fid": fid, "type": typ.decode(), "base": None, "pos": [0.0, 0.0, 0.0], "rot": [0.0, 0.0, 0.0],
                     "scale": 1.0, "persistent": persistent}
                for sig, d in iter_subrecords(record_data(plugin.buf, off)):
                    if sig == b"NAME" and len(d) >= 4:
                        r["base"] = struct.unpack_from("<I", d)[0]
                    elif sig == b"DATA" and len(d) >= 24:
                        v = struct.unpack_from("<6f", d)
                        r["pos"], r["rot"] = list(v[:3]), list(v[3:])
                    elif sig == b"XSCL" and len(d) >= 4:
                        r["scale"] = struct.unpack_from("<f", d)[0]
                refs.append(r)
    children(cs, ce, False)
    return cfid, navs, refs


def read_bases(plugin, wanted):
    """{form id: {type, edid, flags, obnd}} for the wanted base records; Starfield OBND = 6 f32 (metres)."""
    out = {}
    skip = (b"WRLD", b"CELL", b"DIAL", b"QUST", b"NAVI")
    for item in iter_items(plugin.buf, plugin.body, len(plugin.buf)):
        if item[0] != "GRUP" or item[3] in skip:
            continue
        for it in iter_items(plugin.buf, item[1] + 24, item[2]):
            if it[0] == "GRUP":
                continue
            typ, off, flags, fid = it
            if fid not in wanted:
                continue
            b = {"type": typ.decode(), "edid": "", "flags": flags, "obnd": None}
            for sig, d in iter_subrecords(record_data(plugin.buf, off)):
                if sig == b"EDID":
                    b["edid"] = zstring(d)
                elif sig == b"OBND" and len(d) >= 24 and b["obnd"] is None:
                    b["obnd"] = [round(x, 6) for x in struct.unpack_from("<6f", d)]
            out[fid] = b
    return out


def read_trace(qdir):
    """{test id: [(x, y, z), ...]} of every actor position qstep.ps1 read in a npc_nav queue (spawn, t0, samples)."""
    out = {}
    for p in sorted(glob.glob(os.path.join(qdir, "tests", "*", "a*", "obs.json"))):
        try:
            with open(p, encoding="utf-8-sig") as f:
                o = json.load(f)
        except (OSError, ValueError):
            continue
        tid = os.path.basename(os.path.dirname(os.path.dirname(p)))
        reads = [(o.get("spawn") or {}).get("read"), (o.get("t0") or {}).get("read")]
        reads += [s.get("read") for s in o.get("samples") or [] if isinstance(s, dict)]
        pts = []
        for r in reads:
            try:
                v = [float(x) for x in str(r).split()]
            except ValueError:
                continue
            if len(v) == 3:
                pts.append(tuple(v))
        if pts:
            out[f"{tid}/{os.path.basename(os.path.dirname(p))}"] = pts
    return out


# ------------------------------------------------------------------------------------------------------------ analyze
def r3(v):
    return [round(float(x), 3) for x in v]


def analyze(esm, cell, old_a=None, old_b=None, traces=()):
    with Plugin(esm) as pl:
        cfid, navs, refs = read_cell(pl, cell)
        bases = read_bases(pl, {r["base"] for r in refs if r["base"] is not None})
    if not navs:
        raise SystemExit(f"{cell}: no NAVM in the cell")
    comps = components(navs)
    objs = place_objects(refs, bases, navs)
    allv = np.concatenate([m.vertices for m in navs.values()])
    lo, hi = allv.min(0), allv.max(0)
    near = [o for o in objs if o.get("footprint") and
            max(x for x, _ in o["footprint"]) >= lo[0] - 2 and min(x for x, _ in o["footprint"]) <= hi[0] + 2 and
            max(y for _, y in o["footprint"]) >= lo[1] - 2 and min(y for _, y in o["footprint"]) <= hi[1] + 2]
    obstacles = [o for o in near if o["class"] in ("obstacle", "sandbox")]
    fs = FreeSpace(navs, obstacles)
    lab, sizes = fs.labels()
    markers = [o for o in objs if o["class"] in ("marker", "sandbox")]
    coc = [o for o in markers if o["edid"].lower().startswith("cocmarker")]
    arrival = tuple(coc[0]["pos"]) if coc else tuple(((lo + hi) / 2).tolist())
    trace = {}
    for q in traces:
        for k, v in read_trace(q).items():
            trace[f"{os.path.basename(os.path.normpath(q))}/{k}"] = v
    tpts = [p for v in trace.values() for p in v]
    res = {"tool": "scripts/actors/navmesh_points.py", "version": VERSION,
           "esm": {"name": os.path.basename(esm), "bytes": os.path.getsize(esm)},
           "cell": {"edid": cell, "form_id": f"{cfid:08X}", "navmeshes": len(navs), "references": len(refs)},
           "params": {"agent_radius": AGENT_RADIUS, "agent_height": AGENT_HEIGHT, "step": STEP, "grid_m": GRID_M,
                      "lattice_m": LATTICE_M, "pair_m": [PAIR_MIN, PAIR_MAX], "end_clear": END_CLEAR,
                      "segment_clear": SEG_CLEAR, "detour_max": DETOUR_MAX, "a_from_arrival": A_FROM_ARRIVAL,
                      "b_from_arrival": B_FROM_ARRIVAL, "b_from_trace": B_FROM_TRACE, "drift_max": DRIFT_MAX,
                      "target_m": TARGET_M}}
    res["navmeshes"] = []
    for fid in sorted(navs):
        m = navs[fid]
        tr_e, tr_f = m.triangles["e"], m.triangles["flags"]
        open_edges = sum(1 for ti in range(len(m.triangles)) for k in range(3)
                         if int(tr_e[ti][k]) < 0 and not int(tr_f[ti]) & nm.EDGE_LINK_BITS[k])
        res["navmeshes"].append({
            "form_id": f"{fid:08X}", "parent_cell": f"{m.cell or 0:08X}", "vertices": len(m.vertices),
            "triangles": len(m.triangles), "edge_links": len(m.links), "door_triangles": len(m.doors),
            "cover": len(m.cover), "waypoints": len(m.waypoints), "open_border_edges": open_edges,
            "area_m2": round(sum(tri_area(m, i) for i in range(len(m.triangles))), 3),
            "bounds": [r3(m.vertices.min(0)), r3(m.vertices.max(0))],
            "triangle_height": [round(float(m.triangles["height"].min()), 3),
                                round(float(m.triangles["height"].max()), 3)],
            "vertex_list": [r3(v) for v in m.vertices],
            "triangle_list": [[int(x) for x in t["v"]] + [int(x) for x in t["e"]] for t in m.triangles]})
    res["components"] = [{"id": i, "triangles": len(c["triangles"]),
                          "navmeshes": sorted({f"{f:08X}" for f, _ in c["triangles"]}),
                          "area_m2": round(c["area_m2"], 3), "bounds": [r3(c["bounds"][0]), r3(c["bounds"][1])],
                          "centroid": r3(centroid(navs, c)[:2]), "links_leaving_cell": c["exits"]}
                         for i, c in enumerate(comps)]
    attractors = [tuple(arrival), centroid(navs, comps[0])] + [tuple(p) for p in tpts]
    res["arrival"] = {"form_id": coc[0]["form_id"], "edid": coc[0]["edid"], "pos": coc[0]["pos"]} if coc else None
    cls = {}
    for o in objs:
        cls[o["class"]] = cls.get(o["class"], 0) + 1
    res["objects"] = {"classes": dict(sorted(cls.items())), "near_navmesh": len(near),
                      "obstacles": [{k: o[k] for k in ("form_id", "edid", "base_type", "pos", "rot", "z", "footprint")}
                                    for o in sorted(obstacles, key=lambda o: o["form_id"])],
                      "markers_and_sandbox": [{k: o.get(k) for k in ("form_id", "edid", "base_type", "class", "pos")}
                                              for o in sorted(markers, key=lambda o: o["form_id"])]}
    res["free_space"] = {"free_m2": round(float(fs.free.sum()) * GRID_M * GRID_M, 2),
                         "navmesh_cells_m2": round(float(fs.on.sum()) * GRID_M * GRID_M, 2),
                         "components_m2": [round(s * GRID_M * GRID_M, 2) for s in sorted(sizes, reverse=True)]}
    if trace:
        allp = np.asarray(tpts)
        far = float(np.hypot(allp[:, 0] - arrival[0], allp[:, 1] - arrival[1]).max())
        res["trace"] = {"queues": [os.path.basename(os.path.normpath(q)) for q in traces], "reads": len(tpts),
                        "bounds": [r3(allp.min(0)), r3(allp.max(0))], "max_from_arrival": round(far, 3),
                        "tests": {k: [r3(p) for p in v] for k, v in sorted(trace.items())}}
    if old_a and old_b:
        res["old_pair"] = measure(navs, comps, fs, old_a, old_b, arrival, tpts, attractors)
    pairs, counts = pick_pairs(navs, comps, fs, arrival, tpts, attractors=attractors)
    res["selection"] = counts
    res["candidates"] = pairs
    res["chosen"] = pairs[0] if pairs else None
    if pairs:
        a, b = pairs[0]["a"], pairs[0]["b"]
        res["chosen_reversed"] = measure(navs, comps, fs, b, a, arrival, tpts, attractors)
    return res, navs, fs, objs


# ------------------------------------------------------------------------------------------------------------ picture
def render(res, navs, fs, objs, path, px_per_m=24):
    """Top-down PNG: navmesh triangles by component, free space, obstacles, markers, traced reads, old and new pairs."""
    from PIL import Image, ImageDraw
    lo = fs.lo
    w, h = int(fs.nx * fs.grid * px_per_m) + 1, int(fs.ny * fs.grid * px_per_m) + 1
    pad = 30
    tests = sorted((res.get("trace") or {}).get("tests", {}).items())
    img = Image.new("RGB", (w + 2 * pad, h + 2 * pad + 50 + 14 * len(tests)), (250, 250, 248))
    dr = ImageDraw.Draw(img)

    def P(x, y):
        return (pad + (x - lo[0]) * px_per_m, pad + h - (y - lo[1]) * px_per_m)
    blocked = np.flipud(fs.on & ~fs.free)
    for r, c in zip(*np.nonzero(blocked)):
        x0 = pad + c * fs.grid * px_per_m
        y0 = pad + r * fs.grid * px_per_m
        dr.rectangle([x0, y0, x0 + fs.grid * px_per_m, y0 + fs.grid * px_per_m], fill=(236, 214, 206))
    outline = [(120, 150, 190), (90, 170, 90), (190, 150, 60), (160, 90, 190)]       # one colour per component
    for i, c in enumerate(components(navs)):
        for f, ti in c["triangles"]:
            dr.polygon([P(*q) for q in tri_xy(navs[f], ti)], outline=outline[i % len(outline)], fill=None)
    for o in objs:
        if o.get("footprint") and o["class"] in ("obstacle", "sandbox"):
            dr.polygon([P(x, y) for x, y in o["footprint"]], fill=(90, 90, 90), outline=(40, 40, 40))
    cols = [(200, 60, 60), (60, 140, 60), (60, 60, 200), (180, 120, 0), (140, 0, 160), (0, 140, 160)]
    for n, (k, pts) in enumerate(tests):
        col = cols[n % len(cols)]
        xy = [P(p[0], p[1]) for p in pts]
        if len(xy) > 1:
            dr.line(xy, fill=col, width=1)
        for q in xy:
            dr.ellipse([q[0] - 2, q[1] - 2, q[0] + 2, q[1] + 2], fill=col)
    if res.get("arrival"):
        x, y = P(*res["arrival"]["pos"][:2])
        dr.rectangle([x - 4, y - 4, x + 4, y + 4], outline=(0, 0, 0), width=2)
        dr.text((x + 6, y - 6), "arrival", fill=(0, 0, 0))
    if res.get("components"):
        x, y = P(*res["components"][0]["centroid"][:2])
        dr.line([(x - 5, y - 5), (x + 5, y + 5)], fill=(0, 0, 0), width=2)
        dr.line([(x - 5, y + 5), (x + 5, y - 5)], fill=(0, 0, 0), width=2)
        dr.text((x + 6, y - 6), "navmesh centre", fill=(0, 0, 0))

    def pair(m, col, tag):
        a, b = P(*m["a"][:2]), P(*m["b"][:2])
        dr.line([a, b], fill=col, width=3)
        for q, t in ((a, f"{tag} A"), (b, f"{tag} B")):
            dr.ellipse([q[0] - 5, q[1] - 5, q[0] + 5, q[1] + 5], fill=col)
            dr.text((q[0] + 7, q[1] + 2), t, fill=col)
    if res.get("old_pair"):
        pair(res["old_pair"], (150, 150, 150), "old")
    if res.get("chosen"):
        pair(res["chosen"], (0, 110, 200), "N0b")
    dr.text((pad, h + pad + 8), f"{res['cell']['edid']} {res['cell']['form_id']}: navmesh triangles (outline), "
            f"obstacles (grey), not walkable within {AGENT_RADIUS} m (pink),", fill=(0, 0, 0))
    dr.text((pad, h + pad + 22), "old pair (grey), N0b pair (blue), actor reads of the traced runs (spawn, t0, "
            f"samples; below); 1 m = {px_per_m} px, north up", fill=(0, 0, 0))
    for n, (k, _pts) in enumerate(tests):
        dr.text((pad, h + pad + 40 + 14 * n), f"- {k}", fill=cols[n % len(cols)])
    img.save(path)


# ------------------------------------------------------------------------------------------------------------ main
def _xyz(s):
    v = [float(x) for x in s.split(",")]
    if len(v) != 3:
        raise argparse.ArgumentTypeError(f"want x,y,z: {s!r}")
    return tuple(v)


def summary(res):
    lines = [f"{res['cell']['edid']} {res['cell']['form_id']}: {res['cell']['navmeshes']} navmesh(es), "
             f"{res['cell']['references']} references"]
    for n in res["navmeshes"]:
        lines.append(f"  NAVM {n['form_id']}: {n['vertices']} vertices, {n['triangles']} triangles, {n['edge_links']} "
                     f"edge links, {n['open_border_edges']} open border edges, {n['area_m2']} m2, bounds {n['bounds']}")
    for c in res["components"]:
        lines.append(f"  component {c['id']}: {c['triangles']} triangles, {c['area_m2']} m2, bounds {c['bounds']}")
    lines.append(f"  objects: {res['objects']['classes']}; free space {res['free_space']['free_m2']} m2 of "
                 f"{res['free_space']['navmesh_cells_m2']} m2, components {res['free_space']['components_m2']}")
    if res.get("arrival"):
        lines.append(f"  arrival {res['arrival']['edid']} {res['arrival']['form_id']} at {res['arrival']['pos']}")
    for key in ("old_pair", "chosen", "chosen_reversed"):
        m = res.get(key)
        if m:
            lines.append(f"  {key}: A {m['a']} B {m['b']} {m['distance']} m, same component {m['same_component']}, "
                         f"navmesh path {m['navmesh_path']}, free path {m['free_path']}, segment clearance "
                         f"{m['segment_clearance']} (exact {m.get('segment_clearance_exact')}), ends "
                         f"{m['a_clearance']} / {m['b_clearance']}, attractor progress "
                         f"{m.get('attractor_progress')}, drift progress {m.get('drift_progress')} (to "
                         f"{m.get('drift_to')}), A / B from arrival {m.get('a_from_arrival')} / "
                         f"{m.get('b_from_arrival')}, B from trace {m.get('b_from_trace')}")
    lines.append(f"  selection: {res['selection']}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze")
    a.add_argument("--esm", required=True)
    a.add_argument("--cell", default="QASmoke")
    a.add_argument("--out", required=True)
    a.add_argument("--png", default="")
    a.add_argument("--old-a", type=_xyz, default=None)
    a.add_argument("--old-b", type=_xyz, default=None)
    a.add_argument("--trace", action="append", default=[], help="npc_nav queue dir whose obs.json reads are drawn and "
                   "kept away from B (repeatable)")
    s = sub.add_parser("show")
    s.add_argument("--points", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "show":
        with open(args.points, encoding="utf-8") as f:
            print(summary(json.load(f)))
        return 0
    res, navs, fs, objs = analyze(args.esm, args.cell, args.old_a, args.old_b, args.trace)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    if args.png:
        render(res, navs, fs, objs, args.png)
    print(summary(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
