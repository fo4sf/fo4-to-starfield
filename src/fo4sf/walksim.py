"""Offline walk of a player capsule over placed collision triangles: does a straight walk get where a test expects?

Used by the stairs route planner (scripts/game/routes.py) to check a route before it goes to the game: the start must
be (nearly) free, and a walk along the lane must climb the stair without being stopped by a wall, a railing, a static
door or debris lying on the steps (docs/ai/research-log.md, 2026-10-13, "stairs: where the player got stuck").

Model (assumptions, labelled; checked against the 64 decided in-game stairs results of batch_full and
supervised_1011 with scripts/game/stairs_calib.py: 59 verdicts agree, 57 also where the player stopped; not measured
in the engine):
- The player is a vertical cylinder of PLAYER_RADIUS from its feet + STEP_UP to its feet + PLAYER_HEIGHT; it stands on
  the highest upward-facing surface under its foot disc that is at most STEP_UP above its feet (lower ones: it drops).
  Radius 0.35 m: assumed (docs/slice/redrocket-door.md assumed the same). batch_full 0002's push-out does not pin it
  (corrected after QA on PR #111): the face its teleport point overlapped is the closed load door 1828D6's at y 28.00,
  0.11 m north of it, not a wall plug's at y 27.77, and the game read the player 0.47 m south, 0.23 m further than a
  0.35 m capsule needs.
- Collision triangles are ONE-SIDED, front face by winding ((b - a) x (c - a)): a triangle only touches the capsule
  when the capsule's centre is on its front side. FO4 floor tiles face up and ceiling tiles face down (verified by
  winding, BldDecoSmFlrOnly01 / BldDecoSmCeilOnly01), and in game a player climbed BldDecoSmStairsBlock03 0EBED7 up
  through the BldDecoSmFlrOnly01 0EBEDC slab 1.7 m above the stair's foot (batch_full 0004, PASS).
- A one-sided floor that cuts the capsule below its centre lifts the player onto it: a "lift". batch_full 0002 / 0003
  made the same approach under the library's gallery slab and were read standing on the slab, then stopped 1.3 m
  further, 0.01-0.05 m before the converted stair helper comes up through the slab; this walk climbs on from there
  (docs/testing/stairs-routes.md, section 1a: unresolved). The planner refuses a lift higher than STEP_UP: a start
  under a floor is not where FO4's level design walks.
- A start that overlaps something is pushed out by the engine: Cambridge 0135 / 0143 / 0139 and Fort Hagen 0287 /
  0422 / 0424 were read 0.1-0.8 m from their teleport point, over a rail, a chair, a cabinet or a door leaf, and then
  climbed. walk() takes the nearest free spot within START_NUDGE and reports the distance ("nudge"). A start with no
  free spot that close is blocked: the library landing's 0.49 m slot between a wall and a rail (0006 / 0007, the
  player did not move).
- Blocked by walls at an angle, the player slides along them (collide and slide); head-on it stops.
"""
import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

PLAYER_RADIUS = 0.35      # assumed (see above; docs/slice/redrocket-door.md assumed the same)
PLAYER_HEIGHT = 1.8       # assumed
STEP_UP = 0.35            # highest step walked up without a ramp, and the band under the capsule that never blocks
#                           (assumed; FO4 treads are 0.23-0.33 m and every FO4 stair here has a helper ramp)
STEP_DOWN = 0.5           # a lower support than this counts as a drop
WALKABLE_NZ = 0.64        # cos 50 degrees: steeper upward faces are walls, not floors
FOOT_RING = 0.7           # the foot disc: centre + 8 points at FOOT_RING * radius
SAMPLE = 0.1              # metres of forward input per step
START_NUDGE = 0.5         # how far the engine is assumed to push an overlapping start out (see above)

# FO4 / Starfield collision layers a walking player collides with (FO4 COLL layer indices; Starfield shares 0-36):
# STATIC, ANIMSTATIC, TRANSPARENT, TREES, PROPS, TERRAIN, TRAP, GROUND, DEBRIS_LARGE, TRANSPARENT_SMALL,
# INVISIBLE_WALL, TRANSPARENT_SMALL_ANIM, 29 (FO4's sandbag walls use it), STAIRHELPER. Clutter (4) is left out: it
# is pushed aside rather than walked into. Triggers, non-collidable, zones, small debris and picks never block.
BLOCKING_LAYERS = frozenset({1, 2, 3, 9, 10, 13, 14, 17, 20, 26, 27, 28, 29, 31})


def _clip_band(poly, zlo, zhi):
    """The part of a polygon [(x, y, z)] between z = zlo and z = zhi (Sutherland-Hodgman)."""
    def clip(poly, inside, level):
        out = []
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            ia, ib = inside(a), inside(b)
            if ia:
                out.append(a)
            if ia != ib:
                t = (level - a[2]) / (b[2] - a[2])
                out.append(tuple(a[k] + (b[k] - a[k]) * t for k in range(3)))
        return out
    poly = clip(list(poly), lambda p: p[2] >= zlo, zlo)
    return clip(poly, lambda p: p[2] <= zhi, zhi) if poly else []


def _xy_distance(poly, x, y) -> float:
    """xy distance from (x, y) to a convex polygon's projection (0 inside)."""
    n = len(poly)
    if n >= 3:
        s = [(poly[(i + 1) % n][0] - poly[i][0]) * (y - poly[i][1]) - (poly[(i + 1) % n][1] - poly[i][1]) * (x - poly[i][0])
             for i in range(n)]
        if (all(v >= -1e-12 for v in s) or all(v <= 1e-12 for v in s)) and any(abs(v) > 1e-12 for v in s):
            return 0.0
    best = math.inf
    for i in range(n):
        (ax, ay, _), (bx, by, _) = poly[i], poly[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        ll = dx * dx + dy * dy
        t = 0.0 if ll < 1e-18 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / ll))
        best = min(best, math.hypot(x - ax - t * dx, y - ay - t * dy))
    return best


class Scene:
    """Placed collision triangles (N, 3, 3) in metres, each with an owner label, bucketed on an xy grid."""

    def __init__(self, tris, owners: Sequence[str] = (), cell: float = 2.0):
        self.tris = np.asarray(tris, np.float64).reshape(-1, 3, 3)
        self.owners = list(owners) if len(owners) else ["?"] * len(self.tris)
        n = np.cross(self.tris[:, 1] - self.tris[:, 0], self.tris[:, 2] - self.tris[:, 0])
        ln = np.linalg.norm(n, axis=1)
        keep = ln > 1e-12
        self.tris, n, ln = self.tris[keep], n[keep], ln[keep]
        self.owners = [o for o, k in zip(self.owners, keep.tolist()) if k]
        self.normals = n / ln[:, None]
        self.lo = self.tris.min(axis=1)
        self.hi = self.tris.max(axis=1)
        self.cell = cell
        self.buckets: Dict[Tuple[int, int], np.ndarray] = {}
        if len(self.tris):
            i0 = np.floor(self.lo[:, :2] / cell).astype(np.int64)
            i1 = np.floor(self.hi[:, :2] / cell).astype(np.int64)
            tmp: Dict[Tuple[int, int], list] = {}
            for k in range(len(self.tris)):
                for i in range(i0[k, 0], i1[k, 0] + 1):
                    for j in range(i0[k, 1], i1[k, 1] + 1):
                        tmp.setdefault((int(i), int(j)), []).append(k)
            self.buckets = {key: np.array(v, np.int64) for key, v in tmp.items()}

    def near(self, x: float, y: float, r: float) -> np.ndarray:
        i0, i1 = int(math.floor((x - r) / self.cell)), int(math.floor((x + r) / self.cell))
        j0, j1 = int(math.floor((y - r) / self.cell)), int(math.floor((y + r) / self.cell))
        parts = [self.buckets[(i, j)] for i in range(i0, i1 + 1) for j in range(j0, j1 + 1) if (i, j) in self.buckets]
        if not parts:
            return np.zeros(0, np.int64)
        idx = np.unique(np.concatenate(parts))
        ok = (self.lo[idx, 0] <= x + r) & (self.hi[idx, 0] >= x - r) & (self.lo[idx, 1] <= y + r) & (self.hi[idx, 1] >= y - r)
        return idx[ok]

    def surfaces(self, x: float, y: float, below: float = math.inf, up_only: bool = True) -> List[Tuple[float, int]]:
        """[(z, triangle)] of the (upward-facing, walkable) triangles covering (x, y) not above `below`, highest first."""
        idx = self.near(x, y, 0.0)
        if up_only:
            idx = idx[self.normals[idx, 2] >= WALKABLE_NZ]
        if not len(idx):
            return []
        t = self.tris[idx]
        a, b, c = t[:, 0], t[:, 1], t[:, 2]
        d = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
        ok = np.abs(d) > 1e-12
        d = np.where(ok, d, 1.0)
        l1 = ((b[:, 1] - c[:, 1]) * (x - c[:, 0]) + (c[:, 0] - b[:, 0]) * (y - c[:, 1])) / d
        l2 = ((c[:, 1] - a[:, 1]) * (x - c[:, 0]) + (a[:, 0] - c[:, 0]) * (y - c[:, 1])) / d
        l3 = 1.0 - l1 - l2
        z = l1 * a[:, 2] + l2 * b[:, 2] + l3 * c[:, 2]
        hit = ok & (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9) & (z <= below + 1e-9)
        return sorted(zip(z[hit].tolist(), idx[hit].tolist()), reverse=True)

    def support(self, x: float, y: float, below: float, radius: float = PLAYER_RADIUS) -> Optional[Tuple[float, int]]:
        """(z, triangle) of the highest walkable surface under the foot disc not above `below`, or None."""
        best = None
        r = FOOT_RING * radius
        for k in range(9):
            dx, dy = (0.0, 0.0) if k == 0 else (r * math.cos(k * math.pi / 4), r * math.sin(k * math.pi / 4))
            s = self.surfaces(x + dx, y + dy, below)
            if s and (best is None or s[0][0] > best[0]):
                best = s[0]
        return best

    def blockers(self, x: float, y: float, z: float, radius: float = PLAYER_RADIUS, height: float = PLAYER_HEIGHT,
                 skin: float = STEP_UP, passed: frozenset = frozenset()) -> List[int]:
        """Triangles a player standing at (x, y, z) touches between z + skin and z + height, front faces only (a
        capsule centred inside a solid sees only back faces: free_start checks that case with enclosing());
        `passed` are faces the player went through from behind (a ceiling it dropped through) and no longer touches.
        Walls taken from both sides instead were tried and matched the game worse: batch_full 0022's walk then stopped
        on the stair top where the game walked on, and Cambridge 0139's start could not be pushed out of a chair."""
        idx = self.near(x, y, radius)
        if not len(idx):
            return []
        idx = idx[(self.hi[idx, 2] > z + skin) & (self.lo[idx, 2] < z + height)]
        if passed:
            idx = np.array([k for k in idx.tolist() if k not in passed], np.int64)
        if not len(idx):
            return []
        centre = np.array([x, y, z + height / 2])
        front = ((centre - self.tris[idx, 0]) * self.normals[idx]).sum(axis=1) >= -1e-6
        out = []
        for k in idx[front].tolist():
            poly = _clip_band([tuple(v) for v in self.tris[k].tolist()], z + skin, z + height)
            if poly and _xy_distance(poly, x, y) < radius:
                out.append(k)
        return out

    def enclosing(self, x: float, y: float, z: float, reach: float = 20.0) -> List[str]:
        """Owners of the walls around a capsule standing at (x, y, z) whose centre is INSIDE a solid: of horizontal
        rays from its centre along +x, -x, +y and -y, none meets the front of a wall first and at least two meet the
        back of one (a box seen from inside; a ray meeting nothing within `reach` does not count). [] otherwise."""
        zc = z + PLAYER_HEIGHT / 2
        idx = self.near(x, y, reach)
        if not len(idx):
            return []
        idx = idx[(np.abs(self.normals[idx, 2]) < WALKABLE_NZ) & (self.lo[idx, 2] <= zc) & (self.hi[idx, 2] >= zc)]
        if not len(idx):
            return []
        a, b, c = self.tris[idx, 0], self.tris[idx, 1], self.tris[idx, 2]
        e1, e2 = b - a, c - a
        tvec = np.array([x, y, zc]) - a
        q = np.cross(tvec, e1)
        backs = []
        for dvec in ((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, -1.0, 0.0)):
            dv = np.array(dvec)
            p = np.cross(dv, e2)                                      # Moller-Trumbore, all candidates at once
            det = (e1 * p).sum(axis=1)
            ok = np.abs(det) > 1e-12
            det = np.where(ok, det, 1.0)
            u = (tvec * p).sum(axis=1) / det
            v = (q @ dv) / det
            t = (e2 * q).sum(axis=1) / det
            hit = ok & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (t > 1e-6) & (t <= reach)
            if not hit.any():
                continue
            k = int(idx[np.nonzero(hit)[0][np.argmin(t[hit])]])
            if float(np.dot(self.normals[k, :2], dv[:2])) <= 0:
                return []                                             # a wall's front first: outside
            backs.append(self.owners[k])
        return sorted(set(backs)) if len(backs) >= 2 else []

    def toward(self, k: int, x: float, y: float, z: float) -> Tuple[float, float]:
        """Horizontal part of triangle k's normal, turned to the side the capsule standing at (x, y, z) is on."""
        n = self.normals[k]
        side = float(np.dot(np.array([x, y, z + PLAYER_HEIGHT / 2]) - self.tris[k, 0], n))
        return (float(n[0]), float(n[1])) if side >= 0 else (-float(n[0]), -float(n[1]))


def _lift(scene: Scene, x: float, y: float, z: float, hits: List[int]) -> Optional[float]:
    """When every triangle touching the capsule is a walkable upward face below the capsule's centre (a one-sided
    floor the player is inside of), the height it lifts the player to; else None."""
    if not hits or any(scene.normals[k, 2] < WALKABLE_NZ for k in hits):
        return None
    top = scene.support(x, y, z + PLAYER_HEIGHT / 2)
    return top[0] if top is not None and top[0] > z else None


def _slide(scene: Scene, hits: List[int], d: Tuple[float, float], at: Sequence[float]) -> Optional[Tuple[float, float]]:
    """The forward move d with its component into the blocking faces removed (collide and slide), or None head-on;
    `at` is where the capsule stands (x, y, z), which side of each wall it meets."""
    walls = [k for k in hits if scene.normals[k, 2] < WALKABLE_NZ]
    if not walls:
        return None
    n = np.array([scene.toward(k, *at) for k in walls]).sum(axis=0)
    ln = float(np.hypot(*n))
    if ln < 1e-9:
        return None
    n = n / ln
    into = d[0] * n[0] + d[1] * n[1]
    if into >= 0:
        return None
    s = (d[0] - into * n[0], d[1] - into * n[1])
    return s if math.hypot(*s) >= 0.25 * math.hypot(*d) else None


def _stand(scene: Scene, x: float, y: float, z0: float, drop_from: float, radius: float = PLAYER_RADIUS):
    """(z, lift, blockers) of a player put at (x, y, z0): it drops onto the highest surface at most `drop_from` above
    z0, and one-sided floors inside the capsule lift it. z is None when nothing is under it."""
    s = scene.support(x, y, z0 + drop_from)
    if s is None:
        return None, 0.0, []
    z = s[0]
    hits = scene.blockers(x, y, z, radius=radius)
    lifted = _lift(scene, x, y, z, hits) if hits else None
    if lifted is not None:
        return lifted, lifted - z, []
    return z, 0.0, hits


def push_direction(scene: Scene, hits: List[int], at: Sequence[float]) -> Optional[Tuple[float, float]]:
    """Unit horizontal direction that pushes a capsule standing at `at` (x, y, z) out of the faces `hits` (each
    normal turned towards it), or None when they push from opposite sides (wedged: the library landing's wall and
    rail) or have no horizontal component (a ceiling)."""
    dirs = {}
    for k in hits:
        n = scene.toward(k, *at)
        ln = float(np.hypot(*n))
        if ln >= 0.2:
            u = (round(float(n[0]) / ln, 2), round(float(n[1]) / ln, 2))
            dirs[(scene.owners[k], u)] = u               # one vote per face direction and owner, not per triangle
    if not dirs:
        return None
    sx, sy = sum(u[0] for u in dirs.values()), sum(u[1] for u in dirs.values())
    if any(u[0] * v[0] + u[1] * v[1] < -0.5 for u in dirs.values() for v in dirs.values()):
        return None                                        # pushed from opposite sides
    ln = math.hypot(sx, sy)
    return (sx / ln, sy / ln) if ln > 1e-9 else None


def free_start(scene: Scene, start: Sequence[float], drop_from: float = 0.5, nudge: float = START_NUDGE,
               radius: float = PLAYER_RADIUS):
    """(x, y, z, lift, pushed, start_by) of where a player teleported to `start` ends up standing: the point itself if
    nothing overlaps the capsule there, else pushed out along push_direction() in 5 cm steps, at most `nudge`, onto a
    floor within STEP_UP of where it stood (no climbing onto what it overlapped). x is None when nothing is under the
    start; pushed is None when it stays stuck; start_by lists what overlaps the capsule at the teleport point."""
    x, y, z0 = float(start[0]), float(start[1]), float(start[2])
    z, lift, hits = _stand(scene, x, y, z0, drop_from, radius)
    if z is None:
        return None, None, None, 0.0, 0.0, []
    if not hits:
        inside = scene.enclosing(x, y, z)
        if inside:                                         # teleported into a solid wider than the capsule
            return x, y, z, lift, None, inside
        return x, y, z, lift, 0.0, []
    start_by = sorted({scene.owners[k] for k in hits})
    d = push_direction(scene, hits, (x, y, z))
    if d is None:
        return x, y, z, lift, None, start_by
    for k in range(1, int(round(nudge / 0.05)) + 1):
        r = 0.05 * k
        nx, ny = x + r * d[0], y + r * d[1]
        s = scene.support(nx, ny, z + STEP_UP)
        if s is None or s[0] < z - STEP_UP:
            break
        nhits = scene.blockers(nx, ny, s[0], radius=radius)
        if not nhits:
            return nx, ny, s[0], 0.0, r, start_by
        if push_direction(scene, nhits, (nx, ny, s[0])) is None:
            break
    return x, y, z, lift, None, start_by


def walk(scene: Scene, start: Sequence[float], heading: float, distance: float, step: float = SAMPLE,
         drop_from: float = 0.5, nudge: float = START_NUDGE, clearance: float = 0.0) -> dict:
    """Walk straight from start (x, y, z: the runner's teleport point; the player drops onto the highest surface at
    most `drop_from` above z and is pushed out of an overlap by up to `nudge`) along `heading` (degrees, clockwise
    from +y) for `distance` metres of forward input. `clearance` widens the capsule (a planner's safety margin on the
    assumed radius; 0 to replay what the game did).
    Returns {"ok_start", "start_by" (what overlapped the teleport point), "nudge" (metres pushed out), "start" (where
    it stood), "start_drop" (teleport z minus standing z), "end" (x, y, z), "walked" (metres actually moved),
    "stopped_by" (owner) or None, "max_z", "min_z", "lift" (highest lift onto a one-sided floor), "drop" (largest
    drop), "void" (no floor under the start, or walked off all collision), "overhang_at" (metres of input after which
    the capsule's centre first stood over a drop deeper than STEP_DOWN, held up only by the rim of its foot disc:
    the edge of a hole) or None}."""
    out = {"ok_start": False, "start_by": [], "nudge": 0.0, "start": None, "start_drop": 0.0, "end": None,
           "walked": 0.0, "stopped_by": None, "max_z": None, "min_z": None, "lift": 0.0, "drop": 0.0, "void": False,
           "overhang_at": None}
    radius = PLAYER_RADIUS + clearance
    x, y, z, lift, pushed, start_by = free_start(scene, start, drop_from, nudge, radius)
    out["start_by"] = start_by
    if x is None:
        out["void"] = True
        return out
    out.update(start=(x, y, z), start_drop=float(start[2]) - z)
    if pushed is None:
        out.update(end=(x, y, z), max_z=z, min_z=z)
        return out
    out.update(ok_start=True, nudge=pushed, lift=lift)
    ux, uy = math.sin(math.radians(heading)), math.cos(math.radians(heading))
    max_z = min_z = z
    walked, done, over_edge = 0.0, 0.0, 0
    passed = frozenset()
    while done < distance - 1e-9:
        d = (step * ux, step * uy)
        done += step
        moved, last_hits = False, []
        for attempt in range(2):
            nx, ny = x + d[0], y + d[1]
            s = scene.support(nx, ny, z + STEP_UP)
            if s is None:
                out["void"] = True
                out.update(end=(x, y, z), walked=walked, max_z=max_z, min_z=min_z)
                return out
            nz = s[0]
            now_passed = passed
            if nz < z - STEP_DOWN:                # a drop: downward faces between the two heights were passed from above
                now_passed = passed | {k for k in scene.near(nx, ny, PLAYER_RADIUS).tolist()
                                       if scene.normals[k, 2] < -0.5 and nz < scene.hi[k, 2] <= z + STEP_UP}
            hits = scene.blockers(nx, ny, nz, radius=radius, passed=now_passed)
            for _ in range(3):                    # one-sided floors inside the capsule lift the player onto them
                lz = _lift(scene, nx, ny, nz, hits)
                if lz is None:
                    break
                out["lift"] = max(out["lift"], lz - nz)
                nz = lz
                hits = scene.blockers(nx, ny, nz, radius=radius, passed=now_passed)
            if not hits:
                if nz < z - STEP_DOWN:
                    out["drop"] = max(out["drop"], z - nz)
                walked += math.hypot(*d)
                if out["overhang_at"] is None:      # the centre itself over a drop: it would slide off an edge here
                    c = scene.surfaces(nx, ny, nz + 0.05)
                    over_edge = over_edge + 1 if not c or c[0][0] < nz - STEP_DOWN else 0
                    if over_edge >= 2:              # two samples running: not a seam between two floor tiles
                        out["overhang_at"] = done - step
                x, y, z = nx, ny, nz
                passed = now_passed
                max_z, min_z = max(max_z, z), min(min_z, z)
                moved = True
                break
            if attempt == 0:
                last_hits = hits
                slid = _slide(scene, hits, d, (nx, ny, nz))
                if slid is None:
                    break
                d = slid
        if not moved:
            out["stopped_by"] = scene.owners[last_hits[0]] if last_hits else "?"
            break
    out.update(end=(x, y, z), walked=walked, max_z=max_z, min_z=min_z)
    return out
