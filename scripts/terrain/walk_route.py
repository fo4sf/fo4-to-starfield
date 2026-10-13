"""Plan a continuous walk Red Rocket <-> Sanctuary on core64c over Fallout 4's own navmesh
(docs/terrain/walk-redrocket-sanctuary.md).

usage:
  python scripts/terrain/walk_route.py plan --fo4 <Fallout4.esm> --core <terrain_core64c> --out <walk staging dir>
  python scripts/terrain/walk_route.py show --out <walk staging dir>

plan   1. reads the NAVM records of the Fallout 4 cells around Red Rocket and Sanctuary (Fallout4.esm, worldspace
          Commonwealth), joins their triangles over shared edges and edge links and finds the shortest triangle
          corridor (A*) from the Red Rocket arrival over the middle of the Sanctuary bridge deck (a via point: the river
          bed under the bridge is navmesh too) to the Sanctuary cul-de-sac; the funnel through it is Fallout 4's own
          shortest path (reported, with what a standing capsule meets along it in core64c);
       2. rasterises a 25 m band around that corridor (0.5 m cells, core64c's local frame = FO4 position / 70): a cell
          is walkable when Fallout 4's navmesh covers it (where layers overlap, the one the corridor itself uses:
          the bridge deck, not the river bed; the ground under the Red Rocket canopy, not its roof), the ground under it
          (the BTD terrain or a converted object: road, deck, kerb) is within 1 m of the navmesh, and no converted
          collision stands in a 0.35 m standing capsule above a 0.4 m step. Fallout 4's baked navmesh runs through cars
          and guardrails, so the converted collision decides there;
       3. finds the shortest walkable cell path (A*, steps of at most 0.4 m, a cost for passing closer than 2 m to
          anything not walkable), pulls it straight where a 0.75 m clearance holds (line of sight), places waypoints
          (at most 12 m apart, 8 m on the bridge, 4 m before and after every turn of 30 degrees or more, 2 m before
          and after every cell border) and checks the result exactly: the expected ground of every waypoint and its
          source, the capsule every 0.5 m (exterior.capsule_hits), the local cell borders crossed, the bridge span, the
          reverse test's setup teleport.
       Writes route.json (both directions and the report), walk_ground.json (what the runner's judge compares every
       position read with: a BTD window and the converted object surfaces of a 12 m corridor), plan.json (two runner
       tests for testqueue.py plan-walk) and README.txt. Exit 1 when the final path is blocked anywhere.
show   prints the route summary of a staged walk.
Everything it writes stays outside the repo (derived game data).
"""
import argparse
import hashlib
import heapq
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "src"))
from fo4sf import exterior, fo4land  # noqa: E402
from fo4sf import navmesh as nm  # noqa: E402
from fo4sf import terrain_grid as tg  # noqa: E402

UNITS = 70.0                     # FO4 units per metre (core64c's local frame = FO4 position / 70)
CELL_M = 100.0                   # Starfield exterior cell
FO4_CELL_M = 4096.0 / UNITS      # Fallout 4 exterior cell in metres (58.5 m)
WORLD = "Commonwealth"
COC = "FO4Core_RedRocketSpawn"
GOAL_SRC = "0788BD:Fallout4.esm"     # SancRoadLoop01: the cul-de-sac's loop pieces all turn about this point
BRIDGE_SRC = "01F970:Fallout4.esm"   # NorthBridge: the bridge into Sanctuary
AGENT_R = 0.45                   # m: Fallout 4's funnel (reference length): portals narrowed by this at both ends
STEP_UP = 0.4                    # m: what the player steps up without a jump (the capsule starts this high)
CAPSULE = (0.35, 1.8)            # radius, height (assumption, as make_exp2c.CAPSULE minus a margin)
GRID_STEP = 0.5                  # walkability raster
BAND_M = 25.0                    # the raster covers Fallout 4's corridor +- this
NAV_ABOVE = 12.0                 # navmesh layers up to this far above the terrain count (a bridge deck, not a roof)
NAV_SUP_TOL = 1.0                # the ground under a cell must be within this of the navmesh
TRI_SAMPLE = 0.2                 # m between the sample points of a collision triangle (the blocking raster)
MAX_RISE = 0.4                   # m between neighbouring cells (0.5 m apart: 39 degrees)
CLEAR_PREF, CLEAR_W = 2.0, 3.0   # cells closer than CLEAR_PREF to anything not walkable cost up to (1 + CLEAR_W) x
CLEAR_MAX = 4.0
LOS_CLEAR = 0.75                 # a straightened segment keeps this clear of anything not walkable
LOS_STEP = 0.25
LEG_MAX = 12.0                   # m between waypoints on open ground
LEG_BRIDGE = 8.0                 # m between waypoints on the bridge
CORNER_DEG = 30.0                # a turn at least this sharp is a corner: approached and left 4 m in a straight line
CORNER_LEAD = 4.0
TURN_KEEP = 2.0                  # degrees: polyline corners straighter than this are dropped
REACH_OPEN = 2.5                 # m: the runner counts a waypoint as reached this close (a corner: REACH_CORNER)
REACH_CORNER = 1.2
GOAL_RADIUS = 3.0
BORDER_M = 2.0                   # a waypoint this far before and after every cell border: a read on each side
KEEP_KINDS = ("start", "goal", "corner", "border", "bridge")
GOAL_CLEAR = 1.5                 # the goal cell keeps this much clearance
SAMPLE_M = 0.5                   # path samples for the exact capsule and ground checks
CORRIDOR_M = 12.0                # walk_ground.json covers the path +- this (the judge's OFFROUTE limit is inside it)
GRID_M = 0.5                     # object surface nodes of walk_ground.json
UP_NZ = 0.5                      # a collision triangle counts as a surface when |normal z| >= this (slope <= 60 deg)
NAV_ZTOL = 1.5
AREA_MARGIN = 60.0
MAX_AXIS_M = 200.0               # teleport rule (docs/terrain/core64c.md): the reverse test's setup teleport
FO4_MARGIN_CELLS = 1
WALK_SPEED = 4.6                 # m/s, the player's run (route runner 2026-10-08, docs/JOURNAL.md)
VERSION = 1


# --------------------------------------------------------------------------------------------------------- navmesh
class TriMesh:
    """Navmesh triangles of several NAVM records as one graph. v: (T, 3, 3) vertices in metres, keys[i] = (navmesh
    FormID, triangle), nbrs[i] = [(j, k)]: triangle j lies across edge k of triangle i (vertices k and k + 1)."""

    def __init__(self, verts, keys, nbrs, bucket=4.0):
        self.v = np.asarray(verts, np.float64).reshape(-1, 3, 3)
        self.keys = list(keys)
        self.nbrs = [list(n) for n in nbrs]
        self.c = self.v.mean(axis=1) if len(self.v) else np.zeros((0, 3))
        self.bucket = bucket
        self.buckets = {}
        if len(self.v):
            lo = np.floor(self.v[:, :, :2].min(axis=1) / bucket).astype(np.int64)
            hi = np.floor(self.v[:, :, :2].max(axis=1) / bucket).astype(np.int64)
            for k in range(len(self.v)):
                for i in range(lo[k, 0], hi[k, 0] + 1):
                    for j in range(lo[k, 1], hi[k, 1] + 1):
                        self.buckets.setdefault((int(i), int(j)), []).append(k)
            self.buckets = {key: np.array(val, np.int64) for key, val in self.buckets.items()}

    @classmethod
    def from_navs(cls, navs, scale=1.0 / UNITS, skip_flags=nm.F_DELETED):
        """navs: {FormID: Nvnm} (file units). Joins shared edges (edge value = a triangle of the same navmesh) and
        edge links (to a triangle of another loaded navmesh); deleted triangles are left out."""
        keys, verts, index = [], [], {}
        for fid in sorted(navs):
            m = navs[fid]
            V = np.asarray(m.vertices, np.float64) * scale
            for ti in range(len(m.triangles)):
                if int(m.triangles["flags"][ti]) & skip_flags:
                    continue
                index[(fid, ti)] = len(keys)
                keys.append((fid, ti))
                verts.append(V[m.triangles["v"][ti]])
        nbrs = [[] for _ in keys]
        for i, (fid, ti) in enumerate(keys):
            m = navs[fid]
            fl = int(m.triangles["flags"][ti])
            for k in range(3):
                e = int(m.triangles["e"][ti][k])
                if fl & nm.EDGE_LINK_BITS[k]:
                    if not 0 <= e < len(m.links):
                        continue
                    link = m.links[e]
                    other = (int(link["navmesh"]), int(link["tri"]))
                elif e >= 0:
                    other = (fid, e)
                else:
                    continue
                j = index.get(other)
                if j is not None and j != i:
                    nbrs[i].append((j, k))
        return cls(np.array(verts).reshape(-1, 3, 3), keys, nbrs)

    def under(self, x, y):
        """(triangle indices, z) of every triangle covering (x, y)."""
        idx = self.buckets.get((int(math.floor(x / self.bucket)), int(math.floor(y / self.bucket))))
        if idx is None:
            return np.zeros(0, np.int64), np.zeros(0)
        t = self.v[idx]
        a, b, c = t[:, 0], t[:, 1], t[:, 2]
        d = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
        ok = np.abs(d) > 1e-12
        d = np.where(ok, d, 1.0)
        l1 = ((b[:, 1] - c[:, 1]) * (x - c[:, 0]) + (c[:, 0] - b[:, 0]) * (y - c[:, 1])) / d
        l2 = ((c[:, 1] - a[:, 1]) * (x - c[:, 0]) + (a[:, 0] - c[:, 0]) * (y - c[:, 1])) / d
        l3 = 1.0 - l1 - l2
        hit = ok & (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
        z = l1 * a[:, 2] + l2 * b[:, 2] + l3 * c[:, 2]
        return idx[hit], z[hit]

    def locate(self, x, y, z=None, ztol=NAV_ZTOL):
        """(triangle, z) under (x, y) nearest to z (z None: the highest), or None."""
        idx, zz = self.under(x, y)
        if z is not None:
            keep = np.abs(zz - z) <= ztol
            idx, zz = idx[keep], zz[keep]
        if not len(idx):
            return None
        k = int(np.argmin(np.abs(zz - z))) if z is not None else int(np.argmax(zz))
        return int(idx[k]), float(zz[k])

    def layer(self, x, y, lo, hi, near=None):
        """z of the triangle under (x, y) between lo and hi nearest to `near` (None: the highest), or None."""
        _idx, zz = self.under(x, y)
        zz = zz[(zz >= lo) & (zz <= hi)]
        if not len(zz):
            return None
        return float(zz.max()) if near is None else float(zz[np.argmin(np.abs(zz - near))])

    def nearest(self, x, y, z, ztol=NAV_ZTOL, radius=15.0):
        """(triangle, point (x, y, z)) of the triangle point closest to (x, y) in xy among the triangles within ztol
        of z, or None."""
        near = np.nonzero((np.hypot(self.c[:, 0] - x, self.c[:, 1] - y) <= radius)
                          & (np.abs(self.c[:, 2] - z) <= ztol + 3.0))[0]
        best = None
        for i in near.tolist():
            p = closest_on_triangle(self.v[i], (x, y))
            if abs(p[2] - z) > ztol:
                continue
            d = math.hypot(p[0] - x, p[1] - y)
            if best is None or d < best[0]:
                best = (d, i, p)
        return None if best is None else (best[1], best[2])


def closest_on_triangle(tri, xy):
    """The point of a triangle (3, 3) closest to xy in the xy plane, with its z on the triangle's plane."""
    x, y = xy
    a, b, c = (np.asarray(t, np.float64) for t in tri)
    d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(d) > 1e-12:
        l1 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / d
        l2 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / d
        if l1 >= 0 and l2 >= 0 and l1 + l2 <= 1:
            return (float(x), float(y), float(l1 * a[2] + l2 * b[2] + (1 - l1 - l2) * c[2]))
    best = None
    for p, q in ((a, b), (b, c), (c, a)):
        e = q - p
        ln = e[0] * e[0] + e[1] * e[1]
        t = 0.0 if ln < 1e-18 else min(1.0, max(0.0, ((x - p[0]) * e[0] + (y - p[1]) * e[1]) / ln))
        r = p + t * e
        dd = math.hypot(r[0] - x, r[1] - y)
        if best is None or dd < best[0]:
            best = (dd, (float(r[0]), float(r[1]), float(r[2])))
    return best[1]


def astar(mesh, start, goal):
    """Triangle indices from start to goal (shortest by centroid-to-centroid distance in 3D), or None."""
    if start == goal:
        return [start]
    gx = mesh.c[goal]
    openq = [(float(np.linalg.norm(mesh.c[start] - gx)), 0.0, start)]
    came = {start: None}
    cost = {start: 0.0}
    while openq:
        _f, g, i = heapq.heappop(openq)
        if i == goal:
            out = []
            while i is not None:
                out.append(i)
                i = came[i]
            return out[::-1]
        if g > cost[i] + 1e-9:
            continue
        for j, _k in mesh.nbrs[i]:
            ng = g + float(np.linalg.norm(mesh.c[j] - mesh.c[i]))
            if ng < cost.get(j, math.inf) - 1e-9:
                cost[j], came[j] = ng, i
                heapq.heappush(openq, (ng + float(np.linalg.norm(mesh.c[j] - gx)), ng, j))
    return None


def cross(u, v):
    """z of the 2D cross product: > 0 when v turns counter-clockwise (left) from u."""
    return u[0] * v[1] - u[1] * v[0]


def portals(mesh, path):
    """[(left, right)] of the edges a triangle path crosses, in travel order; left / right as seen walking from one
    triangle's centroid to the next (3D points, z on the edge)."""
    out = []
    for i, j in zip(path, path[1:]):
        k = next((k for jj, k in mesh.nbrs[i] if jj == j), None)
        if k is None:
            raise ValueError(f"triangles {i} and {j} are not neighbours")
        p, q = mesh.v[i][k], mesh.v[i][(k + 1) % 3]
        d = mesh.c[j] - mesh.c[i]
        sp, sq = cross(d, p - mesh.c[i]), cross(d, q - mesh.c[i])
        out.append((tuple(p), tuple(q)) if sp >= sq else (tuple(q), tuple(p)))
    return out


def narrow(left, right, r):
    """A portal shortened by r at both ends (a point when it is not longer than 2 r)."""
    left, right = np.asarray(left, np.float64), np.asarray(right, np.float64)
    ln = math.hypot(*(right - left)[:2])
    if ln <= 2 * r + 1e-6:
        mid = tuple((left + right) / 2)
        return mid, mid
    u = (right - left) / ln
    return tuple(left + u * r), tuple(right - u * r)


def funnel(start, goal, gates):
    """The shortest polyline from start to goal through the gates [(left, right)] (simple stupid funnel algorithm,
    Mononen 2010, with cross() > 0 = left). Points are 3D tuples; corners keep the z of the gate point they are."""
    pts = [(tuple(start), tuple(start))] + [(tuple(a), tuple(b)) for a, b in gates] + [(tuple(goal), tuple(goal))]

    def sub(a, b):
        return (a[0] - b[0], a[1] - b[1])

    def same(a, b):
        return abs(a[0] - b[0]) < 1e-9 and abs(a[1] - b[1]) < 1e-9

    path = [tuple(start)]
    apex, left, right = pts[0][0], pts[0][0], pts[0][1]
    ai = li = ri = 0
    i = 1
    while i < len(pts):
        lp, rp = pts[i]
        if cross(sub(right, apex), sub(rp, apex)) >= 0:              # the right side moves in
            if same(apex, right) or cross(sub(left, apex), sub(rp, apex)) < 0:
                right, ri = rp, i
            else:                                                    # right crossed over left: left is a corner
                if not same(path[-1], left):
                    path.append(left)
                apex, ai = left, li
                left = right = apex
                li = ri = ai
                i = ai + 1
                continue
        if cross(sub(left, apex), sub(lp, apex)) <= 0:               # the left side moves in
            if same(apex, left) or cross(sub(right, apex), sub(lp, apex)) > 0:
                left, li = lp, i
            else:                                                    # left crossed over right: right is a corner
                if not same(path[-1], right):
                    path.append(right)
                apex, ai = right, ri
                left = right = apex
                li = ri = ai
                i = ai + 1
                continue
        i += 1
    if not same(path[-1], goal):
        path.append(tuple(goal))
    return [tuple(float(v) for v in p) for p in path]


def turn_deg(a, b, c):
    """Heading change at b (degrees, 0 = straight on)."""
    u, v = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
    nu, nv = math.hypot(*u), math.hypot(*v)
    if nu < 1e-9 or nv < 1e-9:
        return 0.0
    cosv = max(-1.0, min(1.0, (u[0] * v[0] + u[1] * v[1]) / (nu * nv)))
    return math.degrees(math.acos(cosv))


def straighten(points, keep_deg=TURN_KEEP):
    """Drop interior points whose turn is below keep_deg and points closer than 0.05 m to the previous one."""
    out = [points[0]]
    for p in points[1:]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) >= 0.05:
            out.append(p)
    changed = True
    while changed and len(out) > 2:
        changed = False
        for k in range(1, len(out) - 1):
            if turn_deg(out[k - 1], out[k], out[k + 1]) < keep_deg:
                del out[k]
                changed = True
                break
    return out


# ------------------------------------------------------------------------------------------------ walkability grid
class Grid:
    """A walkability raster: cell (i, j) covers x0 + i * step .. + step, y0 + j * step .. + step. nav: Fallout 4's
    navmesh z (NaN: none), sup: the ground z under the cell centre, own: the converted object that ground belongs to
    (-1: terrain), blocked: converted collision in the standing capsule, walk: walkable, clear: metres to the nearest
    cell that is not walkable (capped at CLEAR_MAX)."""

    def __init__(self, x0, y0, nx, ny, step=GRID_STEP):
        self.x0, self.y0, self.nx, self.ny, self.step = float(x0), float(y0), int(nx), int(ny), float(step)
        self.nav = np.full((nx, ny), np.nan)
        self.sup = np.full((nx, ny), np.nan)
        self.own = np.full((nx, ny), -1, np.int64)
        self.blocked = np.zeros((nx, ny), bool)
        self.walk = np.zeros((nx, ny), bool)
        self.clear = np.zeros((nx, ny))

    def centre(self, i, j):
        return (self.x0 + (i + 0.5) * self.step, self.y0 + (j + 0.5) * self.step)

    def cell(self, x, y):
        i, j = int(math.floor((x - self.x0) / self.step)), int(math.floor((y - self.y0) / self.step))
        return (i, j) if 0 <= i < self.nx and 0 <= j < self.ny else None

    def finish(self, nav_sup_tol=NAV_SUP_TOL):
        """walk and clear from nav, sup and blocked."""
        self.walk = (~np.isnan(self.nav)) & (~np.isnan(self.sup)) & (~self.blocked) & \
            (np.abs(np.nan_to_num(self.nav) - np.nan_to_num(self.sup)) <= nav_sup_tol)
        self.clear = clearance(self.walk, self.step)
        return self


def clearance(walk, step, cap=CLEAR_MAX):
    """Metres from every cell to the nearest cell that is not walkable (or the grid edge), by repeated 8-neighbour
    erosion (chessboard distance), capped at cap."""
    out = np.zeros(walk.shape)
    cur = walk.copy()
    n = 0
    while cur.any() and n * step < cap:
        n += 1
        out[cur] = n * step
        pad = np.pad(cur, 1, constant_values=False)
        nxt = cur.copy()
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                nxt &= pad[1 + di:1 + di + cur.shape[0], 1 + dj:1 + dj + cur.shape[1]]
        cur = nxt
    return out


def segment_distance(px, py, poly):
    """Distance from every point (arrays px, py) to a polyline [(x, y, ...)] in xy."""
    best = np.full(np.shape(px), np.inf)
    for a, b in zip(poly, poly[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = dx * dx + dy * dy
        t = np.zeros_like(best) if ln < 1e-18 else np.clip(((px - a[0]) * dx + (py - a[1]) * dy) / ln, 0.0, 1.0)
        best = np.minimum(best, np.hypot(a[0] + t * dx - px, a[1] + t * dy - py))
    return best


def lattice(n):
    """Barycentric weights (K, 3) of a triangle sampled n steps per edge."""
    w = [(i / n, j / n) for i in range(n + 1) for j in range(n + 1 - i)]
    return np.array([(1.0 - a - b, a, b) for a, b in w])


def mark_blocked(grid, tris, step_up=STEP_UP, top=CAPSULE[1], radius=CAPSULE[0], spacing=TRI_SAMPLE):
    """Sample every collision triangle every `spacing` metres and mark each cell whose centre lies within `radius` of
    a sample point between its ground + step_up and its ground + top (inside a standing capsule there)."""
    tris = np.asarray(tris, np.float64).reshape(-1, 3, 3)
    if not len(tris):
        return grid
    edge = np.max(np.linalg.norm(tris - np.roll(tris, 1, axis=1), axis=2), axis=1)
    ns = np.maximum(1, np.ceil(edge / spacing).astype(np.int64))
    for n in np.unique(ns).tolist():
        w = lattice(n)
        pts = np.einsum("kc,tcd->tkd", w, tris[ns == n]).reshape(-1, 3)
        fi = (pts[:, 0] - grid.x0) / grid.step
        fj = (pts[:, 1] - grid.y0) / grid.step
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                ci = np.floor(fi).astype(np.int64) + di
                cj = np.floor(fj).astype(np.int64) + dj
                ok = (ci >= 0) & (ci < grid.nx) & (cj >= 0) & (cj < grid.ny)
                ci, cj, p = ci[ok], cj[ok], pts[ok]
                cx, cy = grid.x0 + (ci + 0.5) * grid.step, grid.y0 + (cj + 0.5) * grid.step
                s = grid.sup[ci, cj]
                hit = (np.hypot(p[:, 0] - cx, p[:, 1] - cy) <= radius) & (p[:, 2] > s + step_up) & (p[:, 2] < s + top)
                grid.blocked[ci[hit], cj[hit]] = True
    return grid


NEIGHBOURS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


def grid_astar(grid, start, goal, max_rise=MAX_RISE):
    """Cells from start to goal over walkable cells (8 neighbours, no corner cutting, a rise of at most max_rise
    per orthogonal step, 1.4 x on a diagonal), each step's length weighted by (1 + CLEAR_W * how far its target cell
    is inside CLEAR_PREF of anything not walkable); None when unreachable."""
    if not (grid.walk[start] and grid.walk[goal]):
        return None
    gx, gy = grid.centre(*goal)

    def h(c):
        x, y = grid.centre(*c)
        return math.hypot(x - gx, y - gy)
    openq = [(h(start), 0.0, start)]
    came, cost = {start: None}, {start: 0.0}
    while openq:
        _f, g, c = heapq.heappop(openq)
        if c == goal:
            out = []
            while c is not None:
                out.append(c)
                c = came[c]
            return out[::-1]
        if g > cost[c] + 1e-9:
            continue
        i, j = c
        for di, dj in NEIGHBOURS:
            ni, nj = i + di, j + dj
            if not (0 <= ni < grid.nx and 0 <= nj < grid.ny) or not grid.walk[ni, nj]:
                continue
            diag = di != 0 and dj != 0
            if diag and not (grid.walk[i + di, j] and grid.walk[i, j + dj]):
                continue
            if abs(grid.sup[ni, nj] - grid.sup[i, j]) > max_rise * (1.4142 if diag else 1.0):
                continue
            step = grid.step * (1.4142 if diag else 1.0)
            w = 1.0 + CLEAR_W * max(0.0, CLEAR_PREF - grid.clear[ni, nj]) / CLEAR_PREF
            ng = g + step * w
            if ng < cost.get((ni, nj), math.inf) - 1e-9:
                cost[(ni, nj)], came[(ni, nj)] = ng, c
                heapq.heappush(openq, (ng + h((ni, nj)), ng, (ni, nj)))
    return None


def line_ok(grid, p, q, min_clear=LOS_CLEAR, max_rise=MAX_RISE, step=LOS_STEP):
    """Can the player walk straight from p to q (x, y)? Every sample every `step` metres on a walkable cell, at least
    min_clear from anything not walkable (near an end: as clear as that end's cell allows), no rise above max_rise per
    grid step between consecutive samples."""
    d = math.hypot(q[0] - p[0], q[1] - p[1])
    n = max(1, int(math.ceil(d / step)))
    t = np.linspace(0.0, 1.0, n + 1)
    xs, ys = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
    ci = np.floor((xs - grid.x0) / grid.step).astype(np.int64)
    cj = np.floor((ys - grid.y0) / grid.step).astype(np.int64)
    if (ci < 0).any() or (ci >= grid.nx).any() or (cj < 0).any() or (cj >= grid.ny).any():
        return False
    if not grid.walk[ci, cj].all():
        return False
    ends = [grid.clear[ci[0], cj[0]], grid.clear[ci[-1], cj[-1]]]
    need = np.full(len(t), min_clear)
    along = t * d
    need[along < 1.0] = min(min_clear, ends[0])
    need[along > d - 1.0] = np.minimum(need[along > d - 1.0], min(min_clear, ends[1]))
    if (grid.clear[ci, cj] + 1e-9 < need).any():
        return False
    z = grid.sup[ci, cj]
    return bool((np.abs(np.diff(z)) <= max_rise * max(step, 1e-9) / grid.step + 1e-9).all())


def smooth(points, ok):
    """Greedy line-of-sight pull: from each kept point the farthest later point it sees (ok(a, b)), by bisection
    (visibility is taken as monotone along the path). The first and last points are kept."""
    out = [points[0]]
    i, n = 0, len(points)
    while i < n - 1:
        if ok(points[i], points[n - 1]):
            best = n - 1
        else:
            lo, hi = i + 1, n - 1
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if ok(points[i], points[mid]):
                    lo = mid
                else:
                    hi = mid
            best = lo
        out.append(points[best])
        i = best
    return out


def prune(points, ok):
    """Drop every interior point whose neighbours see each other (ok(prev, next)), until none can go."""
    pts = list(points)
    changed = True
    while changed and len(pts) > 2:
        changed = False
        for k in range(1, len(pts) - 1):
            if ok(pts[k - 1], pts[k + 1]):
                del pts[k]
                changed = True
                break
    return pts


def grid_z(grid, x, y, fallback=math.nan):
    """The ground z of the raster cell under (x, y) (the layer the corridor uses), else fallback."""
    c = grid.cell(x, y)
    if c is None or np.isnan(grid.sup[c]):
        return fallback
    return float(grid.sup[c])


def nearest_cell(grid, c, need=0.0, max_m=15.0):
    """The walkable cell with clearance >= need closest to cell c (c itself when it qualifies), or None."""
    r = int(math.ceil(max_m / grid.step))
    best = None
    for di in range(-r, r + 1):
        for dj in range(-r, r + 1):
            i, j = c[0] + di, c[1] + dj
            if 0 <= i < grid.nx and 0 <= j < grid.ny and grid.walk[i, j] and grid.clear[i, j] >= need - 1e-9:
                d = di * di + dj * dj
                if best is None or d < best[0]:
                    best = (d, (i, j))
    return None if best is None else best[1]


# ---------------------------------------------------------------------------------------------------- the polyline
def arc_lengths(points):
    s = [0.0]
    for a, b in zip(points, points[1:]):
        s.append(s[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return s


def point_at(points, s_list, s):
    """(x, y, z) at arc length s along the polyline (z interpolated)."""
    s = min(max(s, 0.0), s_list[-1])
    for k in range(1, len(points)):
        if s <= s_list[k] + 1e-9 or k == len(points) - 1:
            seg = s_list[k] - s_list[k - 1]
            t = 0.0 if seg < 1e-12 else (s - s_list[k - 1]) / seg
            a, b = points[k - 1], points[k]
            return tuple(float(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return tuple(float(v) for v in points[-1])


def samples(points, step=SAMPLE_M):
    """[(s, x, y, z)] every `step` metres along the polyline, the end included."""
    s_list = arc_lengths(points)
    n = max(1, int(math.ceil(s_list[-1] / step)))
    return [(s,) + point_at(points, s_list, s) for s in np.linspace(0.0, s_list[-1], n + 1).tolist()]


def place_waypoints(points, span=None, borders=(), leg_max=LEG_MAX, leg_bridge=LEG_BRIDGE, corner_deg=CORNER_DEG,
                    lead=CORNER_LEAD, min_gap=1.5, merge_m=1.0, border_m=BORDER_M):
    """Waypoints along the polyline: [{"s", "x", "y", "z", "kind", "turn", "keep"}]. Required: the start, every
    corner (kind corner when its turn >= corner_deg, else bend), lead metres before and after each corner (kind lead),
    border_m before and after each cell border crossed (borders: their arc lengths; kind border), the two ends of the
    bridge span (s0 + 1, s1 - 1, kind bridge) and the goal; then fill points so that no gap exceeds leg_max
    (leg_bridge where the gap overlaps the span). Points closer than merge_m along the path become one (the sharper
    corner; the goal and the start stay). keep: the runner must read the player there (start, goal, corners, borders,
    everything on the bridge); the others it may walk past in one straight leg (walk_eval.py). span: (s0, s1) or None."""
    s_list = arc_lengths(points)
    total = s_list[-1]
    req = {0.0: ("start", 0.0), total: ("goal", 0.0)}
    for b in borders:
        for s in (b - border_m, b + border_m):
            if 0.0 < s < total and all(abs(s - r) >= min_gap for r in req):
                req[s] = ("border", 0.0)
    for k in range(1, len(points) - 1):
        t = turn_deg(points[k - 1], points[k], points[k + 1])
        req[s_list[k]] = ("corner" if t >= corner_deg else "bend", t)
    for k in range(1, len(points) - 1):
        if req[s_list[k]][0] != "corner":
            continue
        for s in (s_list[k] - lead, s_list[k] + lead):
            if 0.0 < s < total and all(abs(s - r) >= min_gap for r in req):
                req[s] = ("lead", 0.0)
    if span:
        for s in (span[0] + 1.0, span[1] - 1.0):
            if 0.0 < s < total and all(abs(s - r) >= min_gap for r in req):
                req[s] = ("bridge", 0.0)
    keys = sorted(req)
    out = []
    for a, b in zip(keys, keys[1:]):
        out.append((a,) + req[a])
        on_bridge = span is not None and a < span[1] and b > span[0]
        gap = leg_bridge if on_bridge else leg_max
        n = int(math.ceil((b - a) / gap - 1e-9))
        for m in range(1, n):
            out.append((a + (b - a) * m / n, "fill", 0.0))
    out.append((keys[-1],) + req[keys[-1]])
    merged = [out[0]]
    for p in out[1:]:                                 # corners closer than merge_m: keep the sharper one
        if p[1] != "goal" and merged[-1][1] != "start" and p[0] - merged[-1][0] < merge_m:
            if p[2] > merged[-1][2]:
                merged[-1] = p
            continue
        if p[1] == "goal" and merged[-1][1] != "start" and p[0] - merged[-1][0] < merge_m:
            merged[-1] = p
            continue
        merged.append(p)
    wps = []
    for s, kind, t in merged:
        x, y, z = point_at(points, s_list, s)
        keep = kind in KEEP_KINDS or (span is not None and span[0] - 1e-6 <= s <= span[1] + 1e-6)
        wps.append({"s": round(s, 3), "x": x, "y": y, "z": z, "kind": kind, "turn": round(t, 1), "keep": keep})
    return wps


def reach_of(wp):
    if wp["kind"] == "goal":
        return GOAL_RADIUS
    return REACH_CORNER if wp["kind"] in ("corner", "lead") else REACH_OPEN


def cell_of(x, y, cell=CELL_M):
    return (int(math.floor(x / cell)), int(math.floor(y / cell)))


def crossings(smp, cell=CELL_M):
    """The cell borders a sampled path crosses: (cells in order, [{"s", "from", "to", "axis", "at"}])."""
    cells, out = [], []
    prev = None
    for s, x, y, _z in smp:
        c = cell_of(x, y, cell)
        if c != prev:
            if prev is not None:
                axis = "x" if c[0] != prev[0] else "y"
                at = max(c[0], prev[0]) * cell if axis == "x" else max(c[1], prev[1]) * cell
                out.append({"s": round(s, 1), "from": list(prev), "to": list(c), "axis": axis, "at": at})
            cells.append(list(c))
            prev = c
    return cells, out


def polyline_distance(points, x, y):
    """(xy distance from (x, y) to the polyline, arc length of the closest point)."""
    best, s_best, s0 = math.inf, 0.0, 0.0
    for a, b in zip(points, points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = dx * dx + dy * dy
        t = 0.0 if ln < 1e-18 else max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / ln))
        d = math.hypot(a[0] + t * dx - x, a[1] + t * dy - y)
        if d < best:
            best, s_best = d, s0 + t * math.sqrt(ln)
        s0 += math.sqrt(ln)
    return best, s_best


# ------------------------------------------------------------------------------------------------------- the world
def up_surfaces(index, x, y, up_nz=UP_NZ):
    """[(z, owner)] of the collision triangles covering (x, y) whose |normal z| >= up_nz, highest first."""
    idx = index.buckets.get((int(math.floor(x / index.cell)), int(math.floor(y / index.cell))))
    if idx is None:
        return []
    t = index.tris[idx]
    a, b, c = t[:, 0], t[:, 1], t[:, 2]
    n = np.cross(b - a, c - a)
    ln = np.linalg.norm(n, axis=1)
    up = np.abs(n[:, 2]) >= up_nz * np.maximum(ln, 1e-12)
    d = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    ok = (np.abs(d) > 1e-12) & up
    d = np.where(ok, d, 1.0)
    l1 = ((b[:, 1] - c[:, 1]) * (x - c[:, 0]) + (c[:, 0] - b[:, 0]) * (y - c[:, 1])) / d
    l2 = ((c[:, 1] - a[:, 1]) * (x - c[:, 0]) + (a[:, 0] - c[:, 0]) * (y - c[:, 1])) / d
    l3 = 1.0 - l1 - l2
    hit = ok & (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
    z = l1 * a[:, 2] + l2 * b[:, 2] + l3 * c[:, 2]
    return sorted(zip(z[hit].tolist(), index.owners[idx][hit].tolist()), reverse=True)


def support(world, x, y, z_hint, above=1.0):
    """What a player standing at (x, y) near z_hint stands on: {"z", "source" ("terrain" or the object's EditorID),
    "src" (its FO4 reference), "owner" (local index or None), "terrain"}: the highest walkable surface not above
    max(terrain, z_hint) + above (the terrain or a converted object's upward-facing collision)."""
    g = world.ground(x, y)
    below = max(g, z_hint) + above
    best = None
    for z, o in up_surfaces(world.index, x, y):
        if z <= below:
            best = (z, o)
            break
    if best is not None and best[0] > g + 0.005:
        p = world.placed[best[1]]
        return {"z": best[0], "source": world.bases[p["base"]]["edid"], "src": p["src"], "owner": best[1], "terrain": g}
    return {"z": g, "source": "terrain", "src": None, "owner": None, "terrain": g}


def capsule_block(world, x, y, z_feet):
    """Converted collision (or terrain) inside a standing capsule that starts STEP_UP above the feet: [EditorID]."""
    r, h = CAPSULE
    hits = exterior.capsule_hits(world.index, world.ground, x, y, z_feet + STEP_UP, radius=r, height=h - STEP_UP)
    return ["terrain" if o == "terrain" else world.bases[world.placed[o]["base"]]["edid"] for o in hits]


def path_lift(corridor, ground, step=1.0):
    """(xs, ys, lift) every `step` metres along the Fallout 4 corridor polyline: how far its navmesh point stands above
    the terrain there (about 0 on the ground, the deck's height over the river bed on the bridge)."""
    out = samples(corridor, step)
    xs = np.array([p[1] for p in out])
    ys = np.array([p[2] for p in out])
    lift = np.array([p[3] - ground(p[1], p[2]) for p in out])
    return xs, ys, lift


def nearest_lift(px, py, lifted, chunk=4096):
    """The lift of the corridor sample nearest to every point (arrays px, py)."""
    xs, ys, lift = lifted
    flat_x, flat_y = np.ravel(px), np.ravel(py)
    out = np.empty(len(flat_x))
    for k in range(0, len(flat_x), chunk):
        d = (flat_x[k:k + chunk, None] - xs[None, :]) ** 2 + (flat_y[k:k + chunk, None] - ys[None, :]) ** 2
        out[k:k + chunk] = lift[np.argmin(d, axis=1)]
    return out.reshape(np.shape(px))


def build_grid(world, mesh, corridor, band=BAND_M, step=GRID_STEP):
    """The walkability raster of the band around the Fallout 4 corridor polyline (module doc, step 2). Where navmesh
    layers overlap (the Red Rocket canopy roof over the pumps, the bridge deck over the river bed), a cell takes the
    layer nearest to its terrain + the lift of the nearest corridor point, so it follows the corridor's own layer."""
    xs, ys = [p[0] for p in corridor], [p[1] for p in corridor]
    x0, y0 = math.floor((min(xs) - band) / step) * step, math.floor((min(ys) - band) / step) * step
    nx = int(math.ceil((max(xs) + band - x0) / step))
    ny = int(math.ceil((max(ys) + band - y0) / step))
    grid = Grid(x0, y0, nx, ny, step)
    ii, jj = np.meshgrid(np.arange(nx), np.arange(ny), indexing="ij")
    cx, cy = x0 + (ii + 0.5) * step, y0 + (jj + 0.5) * step
    inband = segment_distance(cx, cy, corridor) <= band
    lifted = path_lift(corridor, world.ground)
    bi, bj = np.nonzero(inband)
    lifts = nearest_lift(cx[bi, bj], cy[bi, bj], lifted)
    for i, j, lift in zip(bi, bj, lifts):
        x, y = float(cx[i, j]), float(cy[i, j])
        g = world.ground(x, y)
        z = mesh.layer(x, y, g - 3.0, g + NAV_ABOVE, near=g + float(lift))
        if z is None:
            continue
        s = support(world, x, y, z)
        grid.nav[i, j], grid.sup[i, j] = z, s["z"]
        grid.own[i, j] = -1 if s["owner"] is None else s["owner"]
    lo = world.tris[:, :, :2].min(axis=1)
    hi = world.tris[:, :, :2].max(axis=1)
    near = (hi[:, 0] >= x0) & (lo[:, 0] <= x0 + nx * step) & (hi[:, 1] >= y0) & (lo[:, 1] <= y0 + ny * step)
    mark_blocked(grid, world.tris[near])
    return grid.finish()


# ----------------------------------------------------------------------------------------------------------- inputs
def load_json(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(p, v, indent=1):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(v, f, indent=indent)
    os.replace(tmp, p)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def fo4_navs(fo4_esm, x0, y0, x1, y1):
    """{FormID: Nvnm} and {FormID: FO4 cell} of the NAVM records in the FO4 cells covering the metre box."""
    cx0, cy0 = int(math.floor(x0 / FO4_CELL_M)) - FO4_MARGIN_CELLS, int(math.floor(y0 / FO4_CELL_M)) - FO4_MARGIN_CELLS
    cx1, cy1 = int(math.floor(x1 / FO4_CELL_M)) + FO4_MARGIN_CELLS, int(math.floor(y1 / FO4_CELL_M)) + FO4_MARGIN_CELLS
    want = {(x, y) for x in range(cx0, cx1 + 1) for y in range(cy0, cy1 + 1)}
    with fo4land.Plugin(fo4_esm) as p:
        raw = nm.world_navmeshes(p, WORLD, want)
    navs, cells = {}, {}
    for cell, fid, _fl, b in raw:
        navs[fid] = nm.parse(b, "fo4")
        cells[fid] = cell
    return navs, cells, (cx0, cy0, cx1, cy1)


def core_world(core, area, objects):
    """make_core64c.CoreWorld over `area` from the staged core64c folder (its objects.json loaded, Data, BTD)."""
    sys.path.insert(0, HERE)
    import make_core64c as c64
    prm, ov = c64.core_params(core)
    btd_path = os.path.join(core, *ov["btd_file"].split("/"))
    terrain = c64.Terrain(btd_path)
    world = c64.CoreWorld(os.path.join(core, "Data"), objects["bases"], objects["refs"], terrain, area)
    if world.collision_errors:
        sys.exit(f"converted collision unreadable: {world.collision_errors}")
    return world, terrain, prm, ov, btd_path


def bridge_deck(world, src=BRIDGE_SRC):
    """(owner, centre (x, y, z of the deck top), xy box) of the bridge's converted collision."""
    k = world.by_src.get(src)
    if k is None:
        sys.exit(f"bridge {src} not among the placed references of the area")
    t = world.tris[world.owners == k]
    lo, hi = t.reshape(-1, 3).min(axis=0), t.reshape(-1, 3).max(axis=0)
    cx, cy = float((lo[0] + hi[0]) / 2), float((lo[1] + hi[1]) / 2)
    top = [z for z, o in up_surfaces(world.index, cx, cy) if o == k]
    if not top:
        sys.exit(f"no upward surface of {src} at its box centre")
    return k, (cx, cy, max(top)), (float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1]))


def snap(mesh, x, y, z, what):
    """(triangle, point, xy distance) for (x, y, z): the triangle under it within NAV_ZTOL, else the closest one."""
    hit = mesh.locate(x, y, z)
    if hit is not None:
        return hit[0], (x, y, hit[1]), 0.0
    near = mesh.nearest(x, y, z)
    if near is None:
        sys.exit(f"{what}: no navmesh triangle within 15 m of ({x:.2f}, {y:.2f}, {z:.2f})")
    return near[0], near[1], math.hypot(near[1][0] - x, near[1][1] - y)


# ------------------------------------------------------------------------------------------------------------- plan
def fo4_corridor(mesh, start, via, goal):
    """(Fallout 4's own shortest path start -> via -> goal over its navmesh (funnel, portals narrowed by AGENT_R),
    the triangle corridor); start / via / goal = (triangle, point)."""
    p1 = astar(mesh, start[0], via[0])
    p2 = astar(mesh, via[0], goal[0])
    if p1 is None or p2 is None:
        sys.exit(f"no navmesh connection: start->via {p1 is not None}, via->goal {p2 is not None}")
    corridor = p1 + p2[1:]
    gates = [narrow(a, b, AGENT_R) for a, b in portals(mesh, corridor)]
    return straighten(funnel(start[1], goal[1], gates)), corridor


def walk_path(grid, start_xy, via_xy, goal_xy, bridge_owner):
    """The walkable polyline start -> via (on the bridge deck) -> goal: cells by grid_astar, straightened by
    line_ok; [(x, y, z)] with z = the ground of each point's cell."""
    s = nearest_cell(grid, grid.cell(*start_xy), 0.0, 10.0)
    v = grid.cell(*via_xy)
    on_deck = [(i, j) for i, j in zip(*np.nonzero(grid.walk & (grid.own == bridge_owner)))]
    if v is None or not on_deck:
        sys.exit("the bridge deck has no walkable cell")
    v = min(on_deck, key=lambda c: (-min(grid.clear[c], CLEAR_PREF), (c[0] - v[0]) ** 2 + (c[1] - v[1]) ** 2))
    g = nearest_cell(grid, grid.cell(*goal_xy), GOAL_CLEAR, 15.0)
    if s is None or g is None:
        sys.exit(f"no walkable cell near the start ({s}) or the goal ({g})")
    a, b = grid_astar(grid, s, v), grid_astar(grid, v, g)
    if a is None or b is None:
        sys.exit(f"no walkable path: start->deck {a is not None}, deck->goal {b is not None}")
    cells = a + b[1:]
    pts = [grid.centre(*c) for c in cells]

    def ok(p, q):
        return line_ok(grid, p, q)
    pulled = prune(smooth(pts, ok), ok)
    start = (float(start_xy[0]), float(start_xy[1]))
    if math.hypot(pulled[0][0] - start[0], pulled[0][1] - start[1]) <= 1.0 and len(pulled) > 2:
        pulled = pulled[1:]                              # the arrival itself starts the walk
    out = [start] + [(float(x), float(y)) for x, y in pulled if (x, y) != start]
    return straighten([(x, y, grid_z(grid, x, y)) for x, y in out]), cells


def ground_file(world, terrain, btd_path, corners, corridor=CORRIDOR_M, step=GRID_M):
    """walk_ground.json: the BTD window around the path and the upward converted collision surfaces on a step grid
    within `corridor` of the path, with their owners."""
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    x0, y0 = min(xs) - corridor - 2.0, min(ys) - corridor - 2.0
    x1, y1 = max(xs) + corridor + 2.0, max(ys) + corridor + 2.0
    heights, ox, oy = terrain.window(x0, y0, x1, y1)
    gx0, gy0 = math.floor(x0 / step) * step, math.floor(y0 / step) * step
    nx, ny = int(math.ceil((x1 - gx0) / step)) + 1, int(math.ceil((y1 - gy0) / step)) + 1
    owners, owner_of, nodes = [], {}, {}
    ii, jj = np.meshgrid(np.arange(nx), np.arange(ny), indexing="ij")
    near = segment_distance(gx0 + ii * step, gy0 + jj * step, corners) <= corridor
    for i, j in zip(*np.nonzero(near)):
        x, y = gx0 + i * step, gy0 + j * step
        g = world.ground(x, y)
        surf = [(z, o) for z, o in up_surfaces(world.index, x, y) if g - 1.0 <= z <= g + 15.0]
        if not surf:
            continue
        row = []
        for z, o in surf:
            if o not in owner_of:
                owner_of[o] = len(owners)
                p = world.placed[o]
                owners.append({"src": p["src"], "edid": world.bases[p["base"]]["edid"]})
            row.append([round(z, 3), owner_of[o]])
        nodes[f"{int(i)},{int(j)}"] = row
    return {"version": VERSION, "frame": "core64c local: metres = FO4 position / 70 (the overlay's own frame)",
            "terrain": {"x0": ox, "y0": oy, "step": tg.SF_STEP_M, "rows": np.round(heights, 4).tolist(),
                        "btd": os.path.basename(btd_path), "btd_sha256": sha256(btd_path),
                        "rule": "bilinear, clamped at the window's edge (make_core64c.Terrain, terrain_grid)"},
            "surfaces": {"x0": gx0, "y0": gy0, "step": step, "nx": nx, "ny": ny, "up_nz": UP_NZ, "nodes": nodes},
            "owners": owners, "corridor_m": corridor, "path": [[round(p[0], 3), round(p[1], 3)] for p in corners]}


def direction(world, corners, smp, wps, bridge_k, reverse=False):
    """One direction's waypoints with their expected ground, its cells and crossings and the bridge span."""
    if reverse:
        corners = [tuple(p) for p in corners[::-1]]
    total = arc_lengths(corners)[-1]
    out_wps = []
    seq = wps[::-1] if reverse else wps

    def top(x, y, b):
        return next(((z, o) for z, o in up_surfaces(world.index, x, y) if z <= b), None)
    for n, w in enumerate(seq):
        sup = support(world, w["x"], w["y"], w["z"])
        land = exterior.landing(top, world.ground, w["x"], w["y"], max(sup["terrain"], w["z"]) + 1.0, radius=CAPSULE[0])
        kind = w["kind"]
        if reverse and kind in ("start", "goal"):
            kind = "goal" if kind == "start" else "start"
        wp = {"label": f"wp_{n:02d}", "s": round(total - w["s"] if reverse else w["s"], 2),
              "x": round(w["x"], 4), "y": round(w["y"], 4), "z": round(sup["z"], 3), "source": sup["source"],
              "src": sup["src"], "terrain": round(sup["terrain"], 3), "disc_max": round(land["z"], 3),
              "disc_spread": round(land["spread"], 3), "kind": kind, "turn": w["turn"], "keep": w["keep"]}
        wp["reach"] = reach_of(wp)
        out_wps.append(wp)
    ds = [(total - s, x, y, z) for s, x, y, z in smp[::-1]] if reverse else smp
    cells, cross_ = crossings(ds)
    on = [s for s, x, y, z in ds if support(world, x, y, z)["owner"] == bridge_k]
    span = [round(min(on), 2), round(max(on), 2)] if on else None
    return {"waypoints": out_wps, "cells": cells, "crossings": cross_, "bridge_span": span, "length_m": round(total, 2)}


def cmd_plan(a):
    t0 = time.time()
    core = os.path.abspath(a.core)
    core_plan = load_json(os.path.join(core, "plan.json"))
    spawn = [float(v) for v in core_plan[0]["spawn_local"]]
    # the area: the arrival, the cul-de-sac and the bridge, +- AREA_MARGIN
    objects = load_json(os.path.join(core, "objects.json"))
    by_src = {r["src"]: r for r in objects["refs"]}
    if GOAL_SRC not in by_src or BRIDGE_SRC not in by_src:
        sys.exit(f"{GOAL_SRC} or {BRIDGE_SRC} not placed in {core}")
    goal_pos, bridge_pos = by_src[GOAL_SRC]["pos"], by_src[BRIDGE_SRC]["pos"]
    xs, ys = [spawn[0], goal_pos[0], bridge_pos[0]], [spawn[1], goal_pos[1], bridge_pos[1]]
    area = (min(xs) - AREA_MARGIN, min(ys) - AREA_MARGIN, max(xs) + AREA_MARGIN, max(ys) + AREA_MARGIN)
    world, terrain, prm, _ov, btd_path = core_world(core, area, objects)
    del objects, by_src
    print(f"core64c area {tuple(round(v, 1) for v in area)}: {len(world.placed):,} references, {len(world.tris):,} "
          f"collision triangles ({time.time() - t0:.0f} s)")
    navs, _nav_cells, fo4_box = fo4_navs(a.fo4, *area)
    mesh = TriMesh.from_navs(navs)
    print(f"Fallout4.esm {WORLD} cells x {fo4_box[0]}..{fo4_box[2]}, y {fo4_box[1]}..{fo4_box[3]}: {len(navs)} NAVM, "
          f"{len(mesh.keys):,} triangles, {sum(len(n) for n in mesh.nbrs):,} neighbour links")

    bridge_k, deck, deck_box = bridge_deck(world)
    goal_ground = support(world, goal_pos[0], goal_pos[1], world.ground(goal_pos[0], goal_pos[1]))
    s_tri = snap(mesh, spawn[0], spawn[1], spawn[2], "start")
    v_tri = snap(mesh, deck[0], deck[1], deck[2], "bridge deck")
    g_tri = snap(mesh, goal_pos[0], goal_pos[1], goal_ground["z"], "goal")
    fo4_path, corridor = fo4_corridor(mesh, (s_tri[0], s_tri[1]), (v_tri[0], v_tri[1]), (g_tri[0], g_tri[1]))
    t1 = time.time()
    grid = build_grid(world, mesh, fo4_path)
    print(f"walkability raster {grid.nx} x {grid.ny} ({GRID_STEP} m): {int((~np.isnan(grid.nav)).sum()):,} cells on "
          f"navmesh, {int(grid.blocked.sum()):,} blocked, {int(grid.walk.sum()):,} walkable ({time.time() - t1:.0f} s)")
    corners, cells = walk_path(grid, spawn[:2], deck[:2], goal_pos[:2], bridge_k)
    if any(math.isnan(p[2]) for p in corners):
        corners = [(x, y, z if not math.isnan(z) else support(world, x, y, spawn[2])["z"]) for x, y, z in corners]
    # every z along the path is the raster's ground (its corridor layer): a straight line between two points of an
    # arched bridge deck runs under the deck in its middle
    smp = [(s, x, y, grid_z(grid, x, y, z)) for s, x, y, z in samples(corners)]
    sups = [support(world, x, y, z) for _s, x, y, z in smp]
    on_bridge = [s for (s, _x, _y, _z), sp in zip(smp, sups) if sp["owner"] == bridge_k]
    span = (min(on_bridge), max(on_bridge)) if on_bridge else None
    if span is None:
        sys.exit("the planned path never stands on the bridge deck")
    borders = [c["s"] for c in crossings(smp)[1]]
    wps = place_waypoints(corners, span, borders)
    for w in wps:
        w["z"] = grid_z(grid, w["x"], w["y"], w["z"])

    # exact checks along the path: capsule, navmesh, slope
    blocked, off_nav, steep, prev = [], [], {"deg": 0.0}, None
    for (s, x, y, z), sp in zip(smp, sups):
        hit = capsule_block(world, x, y, sp["z"])
        if hit:
            blocked.append({"s": round(s, 2), "x": round(x, 3), "y": round(y, 3), "z": round(sp["z"], 3), "hits": hit})
        if mesh.locate(x, y, sp["z"], NAV_SUP_TOL) is None:
            off_nav.append(round(s, 2))
        if prev is not None and s - prev[0] > 1e-6:
            deg = math.degrees(math.atan2(abs(sp["z"] - prev[1]), s - prev[0]))
            if deg > steep["deg"]:
                steep = {"deg": round(deg, 1), "s": round(s, 2), "rise_m": round(sp["z"] - prev[1], 3),
                         "from": prev[2], "to": sp["source"]}
        prev = (s, sp["z"], sp["source"])
    slope = steep["deg"]
    # Fallout 4's own funnel path, checked the same way: what its baked navmesh runs through in core64c
    fo4_smp = samples(fo4_path)
    fo4_hits = []
    for s, x, y, z in fo4_smp:
        sp = support(world, x, y, grid_z(grid, x, y, z))
        hit = capsule_block(world, x, y, sp["z"])
        if hit:
            fo4_hits.append({"s": round(s, 2), "x": round(x, 3), "y": round(y, 3), "hits": hit})
    fwd = direction(world, corners, smp, wps, bridge_k)
    rev = direction(world, corners, smp, wps, bridge_k, reverse=True)
    gaps = [b["s"] - a_["s"] for a_, b in zip(fwd["waypoints"], fwd["waypoints"][1:])]
    st = rev["waypoints"][0]
    tele = {"from": spawn, "to": [st["x"], st["y"], round(st["z"] + 1.0, 3)],
            "axis_m": [round(abs(st["x"] - spawn[0]), 2), round(abs(st["y"] - spawn[1]), 2)],
            "capsule_at_landing": capsule_block(world, st["x"], st["y"], st["z"])}
    tele["within_rule"] = bool(max(tele["axis_m"]) <= MAX_AXIS_M)
    fo4_cells = []
    for _s, x, y, _z in smp:
        c = [int(math.floor(x / FO4_CELL_M)), int(math.floor(y / FO4_CELL_M))]
        if not fo4_cells or fo4_cells[-1] != c:
            fo4_cells.append(c)
    report = {
        "length_m": fwd["length_m"], "fo4_navmesh_shortest_m": round(arc_lengths(fo4_path)[-1], 2),
        "corners": len(corners), "waypoints": len(wps), "kept": sum(1 for w in wps if w["keep"]),
        "max_gap_m": round(max(gaps), 2), "min_gap_m": round(min(gaps), 2),
        "sharp_turns": sum(1 for w in wps if w["kind"] == "corner"),
        "cells_local": fwd["cells"], "crossings_local": fwd["crossings"], "fo4_cells": fo4_cells,
        "bridge": {"src": BRIDGE_SRC, "edid": world.bases[world.placed[bridge_k]["base"]]["edid"],
                   "deck_centre": [round(v, 3) for v in deck], "deck_box": [round(v, 2) for v in deck_box],
                   "span_s": [round(span[0], 2), round(span[1], 2)], "span_m": round(span[1] - span[0], 2),
                   "waypoints_on_deck": sum(1 for w in fwd["waypoints"] if w["src"] == BRIDGE_SRC)},
        "start": {"spawn_local": spawn},
        "goal": {"src": GOAL_SRC, "pos": goal_pos, "walk_goal": [round(v, 3) for v in corners[-1]],
                 "from_loop_centre_m": round(math.hypot(corners[-1][0] - goal_pos[0], corners[-1][1] - goal_pos[1]), 2)},
        "capsule_blocked": blocked, "off_navmesh_s": off_nav, "path_samples": len(smp),
        "min_clearance_m": round(min(float(grid.clear[grid.cell(x, y)]) for _s, x, y, _z in smp
                                     if grid.cell(x, y) is not None), 2),
        "min_clearance_astar_m": round(float(min(grid.clear[c] for c in cells)), 2),
        "max_slope_deg": round(slope, 1), "steepest": steep,
        "fo4_path_capsule": {"samples": len(fo4_smp), "blocked": len(fo4_hits),
                             "objects": sorted({h for b in fo4_hits for h in b["hits"]}), "first": fo4_hits[:40]},
        "sources": sorted({w["source"] for w in fwd["waypoints"]}),
        "setup_teleport": tele,
        "raster": {"step": GRID_STEP, "nx": grid.nx, "ny": grid.ny, "on_navmesh": int((~np.isnan(grid.nav)).sum()),
                   "blocked": int(grid.blocked.sum()), "walkable": int(grid.walk.sum())},
        "navmesh": {"cells": list(fo4_box), "records": len(navs), "triangles": len(mesh.keys),
                    "corridor_triangles": len(corridor),
                    "corridor_navmeshes": sorted({f"{mesh.keys[i][0]:08X}" for i in corridor})},
    }
    os.makedirs(a.out, exist_ok=True)
    ground = ground_file(world, terrain, btd_path, corners)
    gpath = os.path.join(a.out, "walk_ground.json")
    save_json(gpath, ground, indent=None)
    gsha = sha256(gpath)
    route = {"version": VERSION, "made": time.strftime("%Y-%m-%dT%H:%M:%S"), "core": core,
             "core_plugin": prm["plugin"], "core_plugin_sha256": sha256(os.path.join(core, prm["plugin"])),
             "fo4_esm": os.path.basename(a.fo4), "fo4_esm_size": os.path.getsize(a.fo4),
             "frame": ground["frame"], "corners": [[round(v, 4) for v in p] for p in corners],
             "fo4_path": [[round(v, 4) for v in p] for p in fo4_path],
             "forward": fwd, "reverse": rev, "report": report, "ground": "walk_ground.json", "ground_sha256": gsha}
    save_json(os.path.join(a.out, "route.json"), route)
    plan = runner_plan(fwd, rev, spawn, report, gsha)
    save_json(os.path.join(a.out, "plan.json"), plan)
    write_readme(a.out, route, plan)
    show(route)
    print(f"walk_ground.json {os.path.getsize(gpath):,} B ({len(ground['surfaces']['nodes']):,} surface nodes, "
          f"{len(ground['owners'])} owners); {time.time() - t0:.0f} s")
    return 1 if blocked or off_nav or not tele["within_rule"] or tele["capsule_at_landing"] else 0


def runner_plan(fwd, rev, spawn, report, gsha):
    """plan.json for testqueue.py plan-walk: forward (from the coc arrival) and reverse (a setup teleport to the
    cul-de-sac first, then the walk back)."""
    common = {"travel": f"coc {COC}", "spawn_local": spawn, "goal_radius": GOAL_RADIUS, "ground": "walk_ground.json",
              "ground_sha256": gsha, "max_leg_m": 15.0, "speed": WALK_SPEED, "z_tol": 0.6, "fell_m": 3.0,
              "offroute_m": 10.0, "stuck_m": 0.6, "stuck_k": 3, "shot_every": 3, "time_of_day": 12, "fresh": True}
    out = []
    for label, d, setup in (("walk_redrocket_to_sanctuary", fwd, False), ("walk_sanctuary_to_redrocket", rev, True)):
        wps = d["waypoints"]
        e = dict(common, label=label, setup=setup,
                 start=[wps[0]["x"], wps[0]["y"], wps[0]["z"]],
                 waypoints=[[w["x"], w["y"], w["z"], w["reach"], 1 if w["keep"] else 0] for w in wps],
                 bridge={"src": report["bridge"]["src"], "edid": report["bridge"]["edid"], "span": d["bridge_span"],
                         "min_reads": 2},
                 cells=d["cells"], crossings=d["crossings"], length_m=d["length_m"],
                 max_legs=int(math.ceil(d["length_m"] / 8.0)) + 25,
                 expect="PASS",
                 basis="the path is on Fallout 4's own navmesh, clear of every converted collision for a standing "
                       "capsule, and every waypoint stands on the expected core64c ground (route.json report)")
        if setup:
            e.update(drop=1.0, settle_ms=6000, start_tol=3.0)
        out.append(e)
    return out


def write_readme(out, route, plan):
    r = route["report"]
    lines = [
        "Walk Red Rocket <-> Sanctuary on core64c (Claude). Recipe and evidence rules: "
        "docs/terrain/walk-redrocket-sanctuary.md (branch claude/walk-redrocket-sanctuary).",
        "NOT a copy of core64c: the runner installs the core64c staging folder (testqueue.py plan-walk --install-exp); "
        "this folder holds only the route, the judge's ground and plan.json.",
        f"core64c plugin {route['core_plugin']} sha256 {route['core_plugin_sha256']}.",
        f"Route: {r['length_m']} m (Fallout 4's navmesh shortest {r['fo4_navmesh_shortest_m']} m; "
        f"{r['navmesh']['records']} NAVM records of Fallout4.esm, {r['navmesh']['corridor_triangles']} corridor "
        f"triangles), {r['waypoints']} waypoints ({r['kept']} kept; gaps {r['min_gap_m']}..{r['max_gap_m']} m), "
        f"{r['sharp_turns']} sharp turns, clearance >= {r['min_clearance_m']} m on the raster.",
        f"Bridge {r['bridge']['edid']} ({r['bridge']['src']}): {r['bridge']['span_m']} m of the path on its deck, "
        f"{r['bridge']['waypoints_on_deck']} waypoints there.",
        f"Local cells: {' -> '.join(str(tuple(c)) for c in r['cells_local'])} ({len(r['crossings_local'])} borders); "
        f"Fallout 4 cells: {len(r['fo4_cells'])}.",
        f"Exact capsule check: {len(r['capsule_blocked'])} of {r['path_samples']} path samples blocked, "
        f"{len(r['off_navmesh_s'])} off the navmesh; max slope {r['max_slope_deg']} deg. Fallout 4's own funnel path: "
        f"{r['fo4_path_capsule']['blocked']} of {r['fo4_path_capsule']['samples']} samples blocked.",
        f"Reverse setup teleport {r['setup_teleport']['axis_m']} m per axis (rule: at most {MAX_AXIS_M:.0f}).",
        f"walk_ground.json sha256 {route['ground_sha256']}.",
        "",
        "Tests (plan.json, testqueue.py plan-walk):"]
    for e in plan:
        lines.append(f"  {e['label']}: {len(e['waypoints'])} waypoints, {e['length_m']} m, setup teleport "
                     f"{'yes' if e['setup'] else 'no'}, at most {e['max_legs']} legs")
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")


def show(route):
    r = route["report"]
    print(f"route {r['length_m']} m (FO4 navmesh shortest {r['fo4_navmesh_shortest_m']} m), {r['corners']} corners, "
          f"{r['waypoints']} waypoints (gaps {r['min_gap_m']}..{r['max_gap_m']} m), {r['sharp_turns']} sharp turns, "
          f"max slope {r['max_slope_deg']} deg, min raster clearance {r['min_clearance_m']} m")
    print(f"start {r['start']}, goal {r['goal']}")
    b = r["bridge"]
    print(f"bridge {b['edid']} {b['src']}: span s {b['span_s']} ({b['span_m']} m), {b['waypoints_on_deck']} waypoints on "
          f"the deck, deck centre {b['deck_centre']}")
    print(f"local cells {r['cells_local']}")
    for c in r["crossings_local"]:
        print(f"  border {c['axis']} = {c['at']:.0f} at s {c['s']} ({tuple(c['from'])} -> {tuple(c['to'])})")
    print(f"fo4 cells {r['fo4_cells']}")
    print(f"exact capsule blocked at {len(r['capsule_blocked'])} of {r['path_samples']} samples"
          + (f": {r['capsule_blocked'][:6]}" if r["capsule_blocked"] else "")
          + f"; off the navmesh at {r['off_navmesh_s'][:10]}")
    print(f"sources {r['sources']}; steepest {r.get('steepest')}")
    f4 = r.get("fo4_path_capsule") or {}
    print(f"Fallout 4's own funnel path: capsule blocked at {f4.get('blocked')} of {f4.get('samples')} samples by "
          f"{f4.get('objects')}")
    print(f"setup teleport {r['setup_teleport']}; raster {r['raster']}")
    for w in route["forward"]["waypoints"]:
        print(f"  {w['label']} s {w['s']:7.2f}  x {w['x']:10.3f}  y {w['y']:9.3f}  z {w['z']:8.3f} ({w['source']}, "
              f"terrain {w['terrain']:.3f}, disc max {w['disc_max']:.3f})  {w['kind']} {w['turn']:.0f} "
              f"reach {w['reach']}{' keep' if w.get('keep') else ''}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--fo4", required=True, help="Fallout4.esm")
    p.add_argument("--core", required=True, help="the staged core64c folder (terrain_core64c)")
    p.add_argument("--out", required=True, help="the walk staging folder to write")
    s = sub.add_parser("show")
    s.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "plan":
        return cmd_plan(a)
    show(load_json(os.path.join(a.out, "route.json")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
