"""Walking routes to a load door for the runner's door_trip test (docs/slice/cave-core64c.md): from where the player
stands after an arrival (the coc arrival outside, the XTEL arrival inside) to within the door's activation range, over
the converted collision and terrain, so the runner WALKS to the door instead of teleporting next to it.

plan(support, blocked, start, door, ...) searches a grid (A*) whose edges are walked in 0.25 m samples exactly as
make_redrocket_door.walk_profile walks a straight line: every sample stands on the highest support at most CLIMB above
the previous one (a step or a 50 degree slope: assumed player limits), never drops more than MAX_DROP (a ledge), and its
player capsule (blocked: an inflated radius for planning, so steering drift stays clear) touches nothing. The node path
is then pulled taut into waypoints (the longest straight walks that stay valid), which the runner steers through with
player.setangle z and timed W holds, reading the position after every hold.

support(x, y, below) -> (z, owner) | None: the highest walkable surface at (x, y) not above `below`.
blocked(x, y, z) -> [owner, ...]: what a standing player (feet at z) overlaps, [] when clear.
Pure functions, no game data: tests/test_door_route.py runs them on synthetic worlds.
"""
import heapq
import math

SAMPLE = 0.25       # m between the samples of a walk (make_redrocket_door.walk_profile's step)
CLIMB = 0.3         # m a sample may rise over the previous one (a 0.3 m step or a 50 degree slope: assumed)
MAX_DROP = 1.0      # m a sample may fall below the previous one (a ledge the player steps off: assumed harmless)
GRID = 0.5          # m between grid nodes (every sample of a grid edge lies on the 0.25 m half grid)
SPEED = 4.6         # m/s the player runs with W held (route runs, scripts/game/routes.py: about 4.6 m/s)


def heading(a, b):
    """Degrees clockwise from north (+y), as player.setangle z and testqueue.heading_to."""
    return round(math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) % 360, 1)


def walk(support, blocked, a, b, z0, climb=CLIMB, max_drop=MAX_DROP, step=SAMPLE):
    """The straight walk from a to b (xy) starting on floor z0: (ok, samples [(x, y, z)], why). ok when every sample
    has a floor at most `climb` above the previous one and at most `max_drop` below it and its capsule is clear. The
    samples exclude a itself (the walk's start is checked by whoever stands there)."""
    d = math.hypot(b[0] - a[0], b[1] - a[1])
    n = max(1, int(math.ceil(d / step - 1e-9)))
    prev, pts = z0, []
    for k in range(1, n + 1):
        f = k / n
        x, y = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
        hit = support(x, y, prev + climb)
        if hit is None:
            return False, pts, f"no floor at {x:.2f}, {y:.2f}"
        z = float(hit[0])
        if prev - z > max_drop:
            return False, pts, f"a drop of {prev - z:.2f} m at {x:.2f}, {y:.2f}"
        hits = blocked(x, y, z)
        if hits:
            return False, pts, f"the capsule touches {', '.join(str(h) for h in list(hits)[:3])} at {x:.2f}, {y:.2f}"
        pts.append((x, y, z))
        prev = z
    return True, pts, ""


class _Cache:
    """support / blocked answers by rounded position: grid edges share their samples."""

    def __init__(self, support, blocked):
        self._s, self._b, self.s, self.b = support, blocked, {}, {}
        self.calls = 0

    def support(self, x, y, below):
        k = (round(x, 3), round(y, 3), round(below, 2))
        if k not in self.s:
            self.s[k] = self._s(x, y, below)
        return self.s[k]

    def blocked(self, x, y, z):
        k = (round(x, 3), round(y, 3), round(z, 2))
        if k not in self.b:
            self.calls += 1
            self.b[k] = self._b(x, y, z)
        return self.b[k]


def free_near(blocked, start, start_free):
    """blocked, except within start_free (xy) of start: an arrival point whose capsule already touches something (the
    engine pushes an arriving player clear; the route only has to leave from there)."""
    if start_free <= 0:
        return blocked

    def b(x, y, z):
        return [] if math.hypot(x - start[0], y - start[1]) <= start_free else blocked(x, y, z)
    return b


def search(support, blocked, start, goal, bounds, grid=GRID, climb=CLIMB, max_drop=MAX_DROP, max_nodes=400000):
    """A* over a grid aligned on start (x, y, z: the feet) inside bounds (x0, y0, x1, y1). goal(x, y, z) -> True where
    the walk may end; its (xy) target for the heuristic is goal.at. Returns (the node path [(x, y, z)] from start to the
    first goal node reached or None, capsule queries). Edges are 8-connected and walked like walk()."""
    c = _Cache(support, blocked)
    c_blocked = c.blocked
    sx, sy, sz = start
    tx, ty = goal.at[0], goal.at[1]

    def h(x, y):
        return max(0.0, math.hypot(tx - x, ty - y) - goal.radius)

    def key(i, j, z):
        # a node is a grid point on a floor: the same (x, y) on a deck more than one climb above the ground is another
        # node with other edges (Codex's review of PR #107, 2026-10-14: keyed by (x, y) alone, a cheaper visit on the
        # lower floor suppressed the upper one, and no route over a stacked floor was found)
        return i, j, int(round(z / climb))

    s0 = key(0, 0, sz)
    best = {s0: 0.0}
    zs = {s0: sz}
    prev = {s0: None}
    openq = [(h(sx, sy), 0.0, s0)]
    done = set()
    steps = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
    while openq:
        _f, g, node = heapq.heappop(openq)
        if node in done:
            continue
        done.add(node)
        x, y, z = sx + node[0] * grid, sy + node[1] * grid, zs[node]
        if goal(x, y, z):
            path = []
            while node is not None:
                path.append((sx + node[0] * grid, sy + node[1] * grid, zs[node]))
                node = prev[node]
            return path[::-1], c.calls
        if len(done) > max_nodes:
            break
        for di, dj in steps:
            ni, nj = node[0] + di, node[1] + dj
            nx, ny = sx + ni * grid, sy + nj * grid
            if not (bounds[0] <= nx <= bounds[2] and bounds[1] <= ny <= bounds[3]):
                continue
            ok, pts, _why = walk(c.support, c_blocked, (x, y), (nx, ny), z, climb, max_drop)
            if not ok:
                continue
            nz = pts[-1][2]
            nb = key(ni, nj, nz)                                                 # the floor the walk ends on
            if nb in done:
                continue
            cost = g + math.hypot(nx - x, ny - y) + 2.0 * max(0.0, nz - z)      # level ways first
            if cost < best.get(nb, math.inf):
                best[nb], zs[nb], prev[nb] = cost, nz, node
                heapq.heappush(openq, (cost + h(nx, ny), cost, nb))
    return None, c.calls


def pull(support, blocked, path, climb=CLIMB, max_drop=MAX_DROP, z_tol=0.35, lookahead=6):
    """Waypoints from a node path: from each waypoint on, the farthest later node a straight walk() reaches (its last
    sample within z_tol of that node's floor: the same level), looking up to `lookahead` nodes past a node it cannot
    reach (greedy: a straight walk to a node beyond a wall is not searched for), so the runner walks few long straight
    legs. Consecutive nodes are always reachable (they are an A* edge)."""
    c = _Cache(support, blocked)
    out, i = [path[0]], 0
    while i < len(path) - 1:
        j, misses = i + 1, 0
        for k in range(i + 1, len(path)):
            ok, pts, _ = walk(c.support, c.blocked, path[i], path[k], path[i][2], climb, max_drop)
            if ok and abs(pts[-1][2] - path[k][2]) <= z_tol:
                j, misses = k, 0
            else:
                misses += 1
                if misses > lookahead:
                    break
        out.append(path[j])
        i = j
    # second pass: drop a waypoint whose neighbours see each other (the greedy pass leaves short corner legs)
    changed = True
    while changed and len(out) > 2:
        changed = False
        for k in range(1, len(out) - 1):
            ok, pts, _ = walk(c.support, c.blocked, out[k - 1], out[k + 1], out[k - 1][2], climb, max_drop)
            if ok and abs(pts[-1][2] - out[k + 1][2]) <= z_tol:
                del out[k]
                changed = True
                break
    return out


class Goal:
    """Where a route to an automatic door may end: the feet within `radius` of the door's origin (3D), the player
    standing there inside the door's activation range when that range (fAutoDoorActivateDistance, 3 m) is measured to
    the origin."""

    def __init__(self, door, radius):
        self.at, self.radius = door, radius

    def __call__(self, x, y, z):
        return math.dist((x, y, z), self.at) <= self.radius


def plan(support, blocked_r, start, door, bounds, goal_m=2.7, radii=(0.6, 0.5, 0.45, 0.35), grid=GRID,
         climb=CLIMB, max_drop=MAX_DROP, start_free=0.0, target=None):
    """The route from start (feet) to within goal_m of the door's origin (or of `target`, e.g. the point in front of
    the door that the walk at the door starts from): for each level in turn (radii: whatever blocked_r takes, e.g. a
    capsule radius, largest first: room for steering drift), A* then pull. blocked_r(level) -> blocked(x, y, z);
    start_free: free_near. Returns a dict: waypoints [(x, y, z)] (start first, the goal node last), radius (the level
    used), length (m), legs [{from, to, length, heading, rise, drop, z_min, z_max}], nodes (the A* path), calls
    (capsule queries), tried [(level, found)], goal_m and end_to_door_m; waypoints None when no level finds a way."""
    tried = []
    goal = Goal(target if target is not None else door, goal_m)
    for r in radii:
        bl = free_near(blocked_r(r), start, start_free)
        path, calls = search(support, bl, start, goal, bounds, grid, climb, max_drop)
        tried.append((r, path is not None))
        if path is None:
            continue
        wps = pull(support, bl, path, climb, max_drop)
        legs = []
        for a, b in zip(wps, wps[1:]):
            _ok, pts, _ = walk(support, bl, a, b, a[2], climb, max_drop)
            zs = [a[2]] + [p[2] for p in pts]
            dz = [zs[k + 1] - zs[k] for k in range(len(zs) - 1)]
            legs.append({"from": [round(v, 4) for v in a], "to": [round(v, 4) for v in b],
                         "length": round(math.hypot(b[0] - a[0], b[1] - a[1]), 3), "heading": heading(a, b),
                         "rise": round(max(0.0, max(dz, default=0.0)), 4),
                         "drop": round(max(0.0, -min(dz, default=0.0)), 4),
                         "z_min": round(min(zs), 4), "z_max": round(max(zs), 4)})
        return {"waypoints": [[round(v, 4) for v in p] for p in wps], "radius": r,
                "length": round(sum(x["length"] for x in legs), 3), "legs": legs,
                "nodes": [[round(v, 4) for v in p] for p in path], "calls": calls, "tried": tried,
                "goal_m": goal_m, "end_to_door_m": round(math.dist(wps[-1], door), 3)}
    return {"waypoints": None, "tried": tried, "goal_m": goal_m}


class NavCover:
    """Where Fallout 4's own navmesh lets characters walk, as a walkability oracle for search(): tris (N, 3, 3) are the
    navmesh triangles in metres (FO4 units / 70, the frame the converted world uses), bucketed on an xy grid.
    covered(x, y, z) when a triangle lies under (x, y) within ztol of z; blocked_at(margin) is a blocked() for search:
    clear only when the point and 8 points on a circle of `margin` around it are covered (a margin from the navmesh's
    open borders, which FO4 generates about one agent radius from walls)."""

    def __init__(self, tris, ztol=1.0, cell=4.0):
        import numpy as np
        self.np = np
        self.tris = np.asarray(tris, np.float64).reshape(-1, 3, 3)
        self.ztol, self.cell = ztol, cell
        self.buckets = {}
        lo = np.floor(self.tris[:, :, :2].min(axis=1) / cell).astype(int)
        hi = np.floor(self.tris[:, :, :2].max(axis=1) / cell).astype(int)
        for k in range(len(self.tris)):
            for i in range(lo[k, 0], hi[k, 0] + 1):
                for j in range(lo[k, 1], hi[k, 1] + 1):
                    self.buckets.setdefault((i, j), []).append(k)
        self.buckets = {key: np.array(v) for key, v in self.buckets.items()}

    def heights(self, x, y):
        """z of every navmesh triangle under (x, y)."""
        np = self.np
        idx = self.buckets.get((int(math.floor(x / self.cell)), int(math.floor(y / self.cell))))
        if idx is None:
            return []
        t = self.tris[idx]
        a, b, c = t[:, 0], t[:, 1], t[:, 2]
        d = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
        ok = np.abs(d) > 1e-12
        d = np.where(ok, d, 1.0)
        l1 = ((b[:, 1] - c[:, 1]) * (x - c[:, 0]) + (c[:, 0] - b[:, 0]) * (y - c[:, 1])) / d
        l2 = ((c[:, 1] - a[:, 1]) * (x - c[:, 0]) + (a[:, 0] - c[:, 0]) * (y - c[:, 1])) / d
        l3 = 1.0 - l1 - l2
        hit = ok & (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
        return (l1 * a[:, 2] + l2 * b[:, 2] + l3 * c[:, 2])[hit].tolist()

    def covered(self, x, y, z):
        return any(abs(h - z) <= self.ztol for h in self.heights(x, y))

    def blocked_at(self, margin):
        offs = [(0.0, 0.0)] + [(margin * math.cos(a), margin * math.sin(a))
                               for a in (k * math.pi / 4 for k in range(8))] if margin > 0 else [(0.0, 0.0)]

        def blocked(x, y, z):
            return [] if all(self.covered(x + dx, y + dy, z) for dx, dy in offs) else ["off the FO4 navmesh"]
        return blocked


def both(*fns):
    """blocked() that reports what any of several blocked() report (e.g. the navmesh and a capsule)."""
    def blocked(x, y, z):
        out = []
        for f in fns:
            out += list(f(x, y, z))
        return out
    return blocked


def replay(support, blocked, waypoints, climb=CLIMB, max_drop=MAX_DROP):
    """Walk the waypoints again leg by leg with another capsule (e.g. the assumed real one): [(leg, ok, why)]."""
    out = []
    for k, (a, b) in enumerate(zip(waypoints, waypoints[1:])):
        ok, _pts, why = walk(support, blocked, a, b, a[2], climb, max_drop)
        out.append((k, ok, why))
    return out


def contacts(support, blocked, waypoints, climb=CLIMB, max_drop=MAX_DROP, step=SAMPLE):
    """Every sample of the waypoints' walk (floor as walk() finds it, whatever blocked says) whose capsule touches
    something: [{leg, at [x, y, z], by [...]}] and the samples without a floor or after a ledge ({leg, at, why})."""
    out = []
    for k, (a, b) in enumerate(zip(waypoints, waypoints[1:])):
        ok, pts, why = walk(support, lambda *_: [], a, b, a[2], climb, max_drop, step)
        if not ok:
            out.append({"leg": k, "at": [round(v, 3) for v in (pts[-1] if pts else a)], "why": why})
        for x, y, z in pts:
            hits = blocked(x, y, z)
            if hits:
                out.append({"leg": k, "at": [round(x, 3), round(y, 3), round(z, 3)], "by": sorted({str(h) for h in hits})})
    return out


def lateral(waypoints, offset):
    """The waypoints shifted sideways by `offset` m (left of the walking direction positive), each by the mean normal
    of its legs: a route the runner might walk with a constant steering drift. The start stays where it is."""
    out = [list(waypoints[0])]
    n = len(waypoints)
    for k in range(1, n):
        normals = []
        for a, b in ((waypoints[k - 1], waypoints[k]),) + (((waypoints[k], waypoints[k + 1]),) if k + 1 < n else ()):
            d = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
            normals.append((-(b[1] - a[1]) / d, (b[0] - a[0]) / d))
        nx, ny = sum(v[0] for v in normals) / len(normals), sum(v[1] for v in normals) / len(normals)
        ln = math.hypot(nx, ny) or 1.0
        out.append([waypoints[k][0] + offset * nx / ln, waypoints[k][1] + offset * ny / ln, waypoints[k][2]])
    return out


def toward(support, blocked, start, door, reach=2.7, climb=CLIMB, max_drop=MAX_DROP, step=SAMPLE):
    """The walk straight at the door from start (feet) until the feet are within `reach` of the door's origin: what the
    runner does after the last waypoint. {"reaches", "walked_m", "to_door_m" (the closest sample), "why" (what stopped
    it), "floor" [z ...], and when it reaches, "end" [x, y, z]: the first sample within reach}. blocked: the capsule
    (a contact stops the walk, as a wall would)."""
    d = math.hypot(door[0] - start[0], door[1] - start[1])
    n = max(1, int(math.ceil(d / step - 1e-9)))
    prev, zs, closest = start[2], [], math.dist(start, door)
    for k in range(1, n + 1):
        f = k / n
        x, y = start[0] + (door[0] - start[0]) * f, start[1] + (door[1] - start[1]) * f
        hit = support(x, y, prev + climb)
        if hit is None or prev - float(hit[0]) > max_drop:
            return {"reaches": False, "walked_m": round(d * (k - 1) / n, 3), "to_door_m": round(closest, 3),
                    "why": "no floor" if hit is None else "a ledge", "floor": zs}
        z = float(hit[0])
        if math.dist((x, y, z), door) <= reach:
            return {"reaches": True, "walked_m": round(d * f, 3), "to_door_m": round(math.dist((x, y, z), door), 3),
                    "why": "", "floor": zs + [round(z, 4)], "end": [round(x, 4), round(y, 4), round(z, 4)]}
        hits = blocked(x, y, z)
        if hits:
            return {"reaches": False, "walked_m": round(d * (k - 1) / n, 3), "to_door_m": round(closest, 3),
                    "why": "the capsule touches " + ", ".join(sorted({str(h) for h in hits})[:3]), "floor": zs}
        zs.append(round(z, 4))
        closest = min(closest, math.dist((x, y, z), door))
        prev = z
    return {"reaches": False, "walked_m": round(d, 3), "to_door_m": round(closest, 3), "why": "at the door's xy",
            "floor": zs}


def walk_ms(length, speed=SPEED, factor=1.6, extra_ms=8000):
    """The W-hold budget of a routed leg: factor x the route at `speed`, plus the final approach at the door."""
    return int(round(length / speed * 1000 * factor + extra_ms, -2))
