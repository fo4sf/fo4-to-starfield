"""What a player dropped at a point of a staged overlay lands on: a vertical trace through the converted collision of
every placed reference that can reach the point, and through the BTD terrain (docs/terrain/core64c.md, "The
northeast probe").

    python scripts/terrain/collision_surface.py trace --staging <terrain_core64c> --point X,Y[,LABEL] [--point ...]
           [--runner-test <queue>\\tests\\<id>\\a1 ...] [--conventions xyz,zyx] [--sphere 0.3,0.4,0.5]
           [--drop-z 175] [--reach 3] [--bounds-cache <file>] [--out <report.json>]
    python scripts/terrain/collision_surface.py clear --staging <terrain_core64c> --near X,Y[,LABEL] [--search-m 30]
           [--prev X,Y,Z] [--next X,Y] [--fo4 <Fallout4.esm>] [--bounds-cache <file>] [--out <proposal.json>]
    python scripts/terrain/collision_surface.py rotations --staging <terrain_core64c> --fo4-data <FO4 Data>
           [--min-tilt-deg 3] [--cells N] [--out <report.json>]

trace   for every point and every reference-rotation convention: every crossing of the vertical line through (x, y)
        with a collision triangle (highest first: height, reference, model, body index / shape class / layer / node,
        slope), the highest crossing at or below the drop height (`top`), the terrain under the point (the three
        interpolation rules of make_cw_overlays / terrain_grid), the support a dropped point lands on (max of the
        two), the landing over 0.4 and 0.6 m discs (exterior.landing), the nearest surface standing more than 0.1 m
        above the terrain within `reach` (exterior.nearby_object) and, with --sphere, where a dropped sphere of each
        radius first touches (a model of the capsule's round bottom: faces, edges and vertices exactly, the terrain
        sampled every 5 cm; feet = centre - radius). With --runner-test the points, their readings, the merge offset
        and the ground reference come from a finished runner attempt (spec.json + obs.json): each reading is moved
        into the local frame (minus the merge offset; z minus the ground reference's read - expect) and compared
        with every prediction.
clear   the collision-clear terrain point nearest `--near` (0.5 m grid within --search-m) under EVERY convention, by
        core64c's waypoint rule (make_core64c.waypoint_ok: the three interpolation rules within one quantisation
        step, at most 0.1 m of relief under the 0.6 m disc, no surface above the terrain within 1 m, nothing reaching
        into a 3 m column of radius 1 m, the drop lands on the terrain) plus no surface above the terrain within
        --clear-m (default 2 m); with --prev / --next the teleports to and from it (setpos x, y, z as qstep makes
        them, exterior.setpos_path) are checked against every object; with --fo4 FO4's own LAND height there.
rotations  FO4's own oracle for the composition: Fallout 4's precombined render meshes
        (meshes\\PreCombined\\<cell FormID>_*_OC.nif, BSPackedCombined(Shared)GeomDataExtra) store each combined
        reference's transform as a rotation matrix, built from the reference's angles by FO4's tools. For every
        tilted reference of the staging (|x|, |y| rotation over --min-tilt-deg) that is the only combined instance
        at its position with its scale, the stored matrix is compared with every convention.

Selection is exhaustive: a reference can only reach a point if the bounding sphere of its model's collision (radius
about the model origin, times the reference scale; rotation does not change it) comes within `reach` of the point,
so every model's radius is computed once (all models of objects.json, cached in --bounds-cache, keyed by size and
mtime) and every reference that passes is placed. Disabled references are left out (initially disabled
references have no collision in game) and listed. A reference whose model collision does not decode makes every
point within 200 m of it INCONCLUSIVE (never silently skipped). Exit codes: trace 0, or 2 when a point is
INCONCLUSIVE; clear 0 (found), 1 (none within --search-m), 2 (INCONCLUSIVE); rotations 0.

Collision is the converted Starfield collision read back by sfbodies.nif_bodies (compressed meshes, convex hulls
with their convex radius, spheres, boxes, on the node transform as written). Reference rotations (Bethesda angles,
clockwise per axis) are composed by a convention, all equal when x = y = 0 (a heading: the only part verified in
game before this tool, docs/ai/research-log.md 2026-10-11):
  xyz   R = Rz(-z) Ry(-y) Rx(-x): X applied first. exterior.ref_matrix, routes.ref_matrix, PluginSpike.RotateOffset;
        core64c's plan judged its points with this one.
  zyx   R = Rx(-x) Ry(-y) Rz(-z): Z applied first. FO4's precombined transforms are built this way (`rotations`)
        and it explains every core64c landing read in game (docs/terrain/core64c.md, "The northeast probe").
Any permutation of x, y, z is accepted (the order the axis rotations are applied in, about the world axes).
Everything here is local-frame metres (FO4 position / 70). Read only: nothing is written outside --out and the
bounds cache, no game is touched.
"""
import argparse
import hashlib
import json
import math
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "src"))
from fo4sf import btd, exterior, sfbodies  # noqa: E402
from fo4sf import terrain_grid as tg  # noqa: E402

DROP_Z = 175.0                 # core64c entry 1's drop height
REACH_M = 3.0                  # references whose collision can come this close to a point are placed
DISCS = (0.4, 0.6)             # landing discs (exterior.landing): 0.4 m = x2c's capsule radius, 0.6 m = plan disc
RINGS = (0.15, 0.3, 0.45, 0.6, 0.8, 1.0, 1.5, 2.0, 2.5, 3.0)
ELEVATED = 0.1                 # m above the terrain: a surface that may catch a dropped player (exterior.nearby_object)
TERRAIN_SAMPLE_M = 0.05        # sphere contact on the terrain: sample spacing
CLEAR_M = 2.0                  # clear: no surface above the terrain this close (core64c's waypoint rule asks 1 m)
CONVENTIONS = {
    "xyz": "R = Rz(-z) Ry(-y) Rx(-x): X applied first (exterior.ref_matrix, routes.ref_matrix, PluginSpike."
           "RotateOffset; core64c's plan)",
    "zyx": "R = Rx(-x) Ry(-y) Rz(-z): Z applied first",
}
UNREADABLE_REACH_M = 200.0     # a reference whose model does not decode is assumed to reach this far (no bound known)
MATCH_M = 0.05                 # a prediction "explains" a reading within this (readings are printed to 0.01 m)
RUNNER_TOLERANCE = 0.5         # testqueue.py terrain judge


def _rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


AXES = {"x": _rx, "y": _ry, "z": _rz}


def rotation(rot, convention):
    """3x3 world rotation (column vectors) of a reference with Bethesda angles rot (x, y, z radians, clockwise per
    axis). convention = the order the three axis rotations are applied in, about the world axes: "xyz" = Rz Ry Rx
    (X first), "zyx" = Rx Ry Rz (Z first); any permutation of x, y, z is accepted."""
    if sorted(convention) != ["x", "y", "z"]:
        raise ValueError(f"unknown rotation convention {convention!r}: a permutation of xyz (known: "
                         f"{', '.join(CONVENTIONS)})")
    ang = dict(zip("xyz", (float(v) for v in rot)))
    m = np.eye(3)
    for axis in convention:
        m = AXES[axis](-ang[axis]) @ m
    return m


def describe_convention(convention):
    return CONVENTIONS.get(convention) or ("R = " + " ".join(f"R{a}(-{a})" for a in reversed(convention))
                                            + f": {convention[0].upper()} applied first")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path):
    with open(path, encoding="utf-8-sig") as f:              # the runner writes obs.json with a BOM
        return json.load(f)


# ----------------------------------------------------------------------------------------------------------- models
def read_model(path):
    """Collision of one converted NIF: {"tris": (N, 3, 3) model space metres, "body": (N,) body index, "bodies":
    [{"shape", "layer", "node", "triangles"}], "radius": max distance of a collision vertex from the model origin}."""
    with open(path, "rb") as f:
        bodies = sfbodies.nif_bodies(f.read())
    tris, body = [], []
    for k, b in enumerate(bodies):
        t = np.asarray(b["triangles"], np.float64).reshape(-1, 3, 3)
        tris.append(t)
        body.append(np.full(len(t), k, np.int64))
    tris = np.concatenate(tris) if tris else np.zeros((0, 3, 3))
    body = np.concatenate(body) if body else np.zeros(0, np.int64)
    radius = float(np.sqrt((tris.reshape(-1, 3) ** 2).sum(axis=1)).max()) if len(tris) else 0.0
    return {"tris": tris, "body": body, "radius": radius,
            "bodies": [{"shape": b["shape"], "layer": b["layer"], "node": b["node"], "triangles": len(b["triangles"])}
                       for b in bodies]}


class Staging:
    """A staged overlay: objects.json (bases, refs), Data\\meshes, the BTD; model collision read on demand."""

    def __init__(self, root, btd_path=None):
        self.root = root
        self.objects_path = os.path.join(root, "objects.json")
        objects = load_json(self.objects_path)
        self.bases, self.refs = objects["bases"], objects["refs"]
        self.world = objects.get("world")
        self.data = os.path.join(root, "Data")
        if btd_path is None:
            tdir = os.path.join(self.data, "Terrain")
            found = sorted(f for f in os.listdir(tdir) if f.lower().endswith(".btd")) if os.path.isdir(tdir) else []
            want = [f for f in found if self.world and f.lower() == f"{self.world.lower()}.btd"]
            if len(want or found) != 1:
                raise SystemExit(f"{tdir}: expected one BTD (found {found}); pass --btd")
            btd_path = os.path.join(tdir, (want or found)[0])
        self.btd_path = btd_path
        self.terrain = Terrain(btd_path)
        self.models = {}
        self._formids = None

    def model_path(self, base):
        return os.path.join(self.data, "meshes", *self.bases[base]["model"].replace("\\", "/").split("/"))

    def model(self, base):
        if base not in self.models:
            try:
                self.models[base] = read_model(self.model_path(base))
            except (OSError, ValueError, struct.error, IndexError) as e:
                self.models[base] = {"error": f"{type(e).__name__}: {e}"}
        return self.models[base]

    def radii(self, cache_path=None):
        """{base index: collision radius or None (unreadable)} for every base, from the cache when its size and mtime
        still match the model file."""
        cache = {}
        if cache_path and os.path.exists(cache_path):
            cache = load_json(cache_path)
        out, changed = {}, False
        for i, b in enumerate(self.bases):
            path = self.model_path(i)
            try:
                st = os.stat(path)
                key = [st.st_size, st.st_mtime_ns]
            except OSError as e:
                out[i] = None
                self.models[i] = {"error": f"{type(e).__name__}: {e}"}
                continue
            c = cache.get(b["model"])
            if c is None or c.get("key") != key:
                try:                                     # read and drop: the few models a point needs are re-read
                    c = {"key": key, "radius": read_model(path)["radius"], "error": None}
                except (OSError, ValueError, struct.error, IndexError) as e:
                    c = {"key": key, "radius": None, "error": f"{type(e).__name__}: {e}"}
                cache[b["model"]] = c
                changed = True
            out[i] = c.get("radius")
            if c.get("error"):
                self.models[i] = {"error": c["error"]}
        if cache_path and changed:
            os.makedirs(os.path.dirname(os.path.abspath(cache_path)), exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f)
        return out

    def plugin_ids(self):
        """formids.json of the staging ({"plugin", "bases": {edid: id}, "refs": {src: id}}: FormIDs inside the plugin,
        without the load-order prefix), or {} when it has none."""
        if self._formids is None:
            path = os.path.join(self.root, "formids.json")
            self._formids = load_json(path) if os.path.exists(path) else {}
        return self._formids

    def describe(self, k, body=None):
        r, b = self.refs[k], self.bases[self.refs[k]["base"]]
        d = {"ref": r["src"], "edid": b["edid"], "model": b["model"], "source_model": b.get("source"),
             "collision": b.get("collision"), "pos": r["pos"], "rot": r["rot"], "scale": r["scale"]}
        ids = self.plugin_ids()
        if ids:
            d["plugin"] = ids.get("plugin")
            d["refr_in_plugin"] = ids.get("refs", {}).get(r["src"])
            d["base_in_plugin"] = ids.get("bases", {}).get(b["edid"])
        if body is not None:
            m = self.model(r["base"])
            bd = m["bodies"][body]
            d["body"] = {"index": int(body), "shape": bd["shape"], "layer": bd["layer"], "node": bd["node"]}
            if "sha256" not in m:
                m["sha256"] = sha256(self.model_path(r["base"]))
            d["model_sha256"] = m["sha256"]
        return d


class Terrain:
    """The staged BTD (raw u16 heights, make_cw_overlays' decode and edge clamping); local frame metres."""

    def __init__(self, path):
        with open(path, "rb") as f:
            t = btd.read(f.read())
        self.raw, self.hmin, self.hmax, self.n = t.heights_raw, t.hmin, t.hmax, t.ncx
        self.step = (self.hmax - self.hmin) / 65535.0
        self.origin = tg.grid_origin(self.n)

    def _h(self, r, c):
        return self.hmin + self.raw[r, c].astype(np.float64) / 65535.0 * (self.hmax - self.hmin)

    def bilinear(self, xs, ys):
        xs, ys = np.asarray(xs, np.float64), np.asarray(ys, np.float64)
        rows, cols = self.raw.shape
        u = np.clip((xs - self.origin) / tg.SF_STEP_M, 0.0, cols - 1.0)
        v = np.clip((ys - self.origin) / tg.SF_STEP_M, 0.0, rows - 1.0)
        c = np.minimum(u.astype(np.int64), cols - 2)
        r = np.minimum(v.astype(np.int64), rows - 2)
        fu, fv = u - c, v - r
        return (self._h(r, c) * (1 - fu) * (1 - fv) + self._h(r, c + 1) * fu * (1 - fv)
                + self._h(r + 1, c) * (1 - fu) * fv + self._h(r + 1, c + 1) * fu * fv)

    def ground(self, x, y):
        return float(self.bilinear([x], [y])[0])

    def rules(self, x, y):
        """The three interpolation rules at (x, y) (tg.point_interp over the 2 x 2 samples around it)."""
        rows, cols = self.raw.shape
        u = min(max((x - self.origin) / tg.SF_STEP_M, 0.0), cols - 1.0)
        v = min(max((y - self.origin) / tg.SF_STEP_M, 0.0), rows - 1.0)
        c, r = min(int(u), cols - 2), min(int(v), rows - 2)
        win = self._h(np.array([[r, r], [r + 1, r + 1]]), np.array([[c, c + 1], [c, c + 1]]))
        return tg.point_interp(win, self.origin + c * tg.SF_STEP_M, self.origin + r * tg.SF_STEP_M, tg.SF_STEP_M, x, y)


# ---------------------------------------------------------------------------------------------------------- geometry
def ray_hits(tris, x, y):
    """[(z, i)] of every crossing of the vertical line through (x, y) with tris (N, 3, 3), highest first; edges and
    vertices count (as exterior.point_in_triangle_z), triangles seen edge-on (no xy area) do not."""
    tris = np.asarray(tris, np.float64).reshape(-1, 3, 3)
    if not len(tris):
        return []
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    d = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    ok = np.abs(d) > 1e-12
    d = np.where(ok, d, 1.0)
    l1 = ((b[:, 1] - c[:, 1]) * (x - c[:, 0]) + (c[:, 0] - b[:, 0]) * (y - c[:, 1])) / d
    l2 = ((c[:, 1] - a[:, 1]) * (x - c[:, 0]) + (a[:, 0] - c[:, 0]) * (y - c[:, 1])) / d
    l3 = 1.0 - l1 - l2
    hit = ok & (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
    z = l1 * a[:, 2] + l2 * b[:, 2] + l3 * c[:, 2]
    idx = np.nonzero(hit)[0]
    return sorted(((float(z[i]), int(i)) for i in idx), key=lambda t: (-t[0], t[1]))


def slope_deg(tri):
    """Angle (degrees) between a triangle's plane and the horizontal."""
    t = np.asarray(tri, np.float64)
    n = np.cross(t[1] - t[0], t[2] - t[0])
    ln = float(np.linalg.norm(n))
    return 90.0 if ln < 1e-12 else math.degrees(math.acos(min(1.0, abs(float(n[2])) / ln)))


def _quad_roots(a, b, c):
    """Real roots of a t^2 + b t + c = 0 per element (NaN where none); (N,) arrays -> two (N,) arrays."""
    a, b, c = (np.asarray(v, np.float64) for v in (a, b, c))
    lin = np.abs(a) < 1e-14
    disc = b * b - 4 * a * c
    sq = np.sqrt(np.where(disc >= 0, disc, np.nan))
    aa = np.where(lin, 1.0, a)
    r1 = np.where(lin, np.where(np.abs(b) > 1e-14, -c / np.where(np.abs(b) > 1e-14, b, 1.0), np.nan), (-b - sq) / (2 * aa))
    r2 = np.where(lin, np.nan, (-b + sq) / (2 * aa))
    return r1, r2


def sphere_drop(tris, x, y, r):
    """(centre z, triangle index) where a sphere of radius r, moving down the vertical through (x, y), first touches
    one of tris (N, 3, 3): the highest contact over every face (from above), edge and vertex; (None, None) when it
    touches none. Exact for planar triangles."""
    tris = np.asarray(tris, np.float64).reshape(-1, 3, 3)
    if not len(tris) or r <= 0:
        hits = ray_hits(tris, x, y)
        return (hits[0][0], hits[0][1]) if hits else (None, None)
    lo, hi = tris[:, :, :2].min(axis=1), tris[:, :, :2].max(axis=1)
    near = np.nonzero((lo[:, 0] <= x + r) & (hi[:, 0] >= x - r) & (lo[:, 1] <= y + r) & (hi[:, 1] >= y - r))[0]
    if not len(near):
        return None, None
    t = tris[near]
    cand_z, cand_i = [], []
    # vertices
    v = t.reshape(-1, 3)
    d2 = (v[:, 0] - x) ** 2 + (v[:, 1] - y) ** 2
    ok = d2 <= r * r
    cand_z.append(np.where(ok, v[:, 2] + np.sqrt(np.maximum(r * r - d2, 0.0)), -np.inf))
    cand_i.append(np.repeat(near, 3))
    # faces, from above: the centre stands r off the plane along the upward normal, the contact point inside
    a, b, c = t[:, 0], t[:, 1], t[:, 2]
    n = np.cross(b - a, c - a)
    ln = np.linalg.norm(n, axis=1)
    n = n / np.where(ln > 1e-12, ln, 1.0)[:, None]
    n = np.where((n[:, 2] < 0)[:, None], -n, n)
    up = (ln > 1e-12) & (n[:, 2] > 1e-9)
    nz = np.where(up, n[:, 2], 1.0)
    zc = (r + (n * a).sum(axis=1) - n[:, 0] * x - n[:, 1] * y) / nz
    px, py = x - r * n[:, 0], y - r * n[:, 1]
    d = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    dok = np.abs(d) > 1e-12
    d = np.where(dok, d, 1.0)
    l1 = ((b[:, 1] - c[:, 1]) * (px - c[:, 0]) + (c[:, 0] - b[:, 0]) * (py - c[:, 1])) / d
    l2 = ((c[:, 1] - a[:, 1]) * (px - c[:, 0]) + (a[:, 0] - c[:, 0]) * (py - c[:, 1])) / d
    inside = up & dok & (l1 >= -1e-9) & (l2 >= -1e-9) & (1.0 - l1 - l2 >= -1e-9)
    cand_z.append(np.where(inside, zc, -np.inf))
    cand_i.append(near)
    # edges: the highest centre on the segment's "tube" of radius r over the vertical line
    for i0, i1 in ((0, 1), (1, 2), (2, 0)):
        A, E = t[:, i0], t[:, i1] - t[:, i0]
        ax, ay = x - A[:, 0], y - A[:, 1]
        qa = E[:, 0] ** 2 + E[:, 1] ** 2
        qb = -2.0 * (ax * E[:, 0] + ay * E[:, 1])
        qc = ax * ax + ay * ay
        ez2 = E[:, 2] ** 2
        roots = [*_quad_roots(qa, qb, qc - r * r),
                 *_quad_roots(4 * qa * (qa + ez2), 4 * qb * (qa + ez2), qb * qb - 4 * ez2 * (r * r - qc))]
        best = np.full(len(t), -np.inf)
        for tt in roots + [np.zeros(len(t)), np.ones(len(t))]:
            tt = np.clip(np.nan_to_num(tt, nan=-1.0), -1.0, 2.0)
            valid = (tt >= 0.0) & (tt <= 1.0)
            s = r * r - (qa * tt * tt + qb * tt + qc)
            valid &= s >= -1e-12
            z = A[:, 2] + tt * E[:, 2] + np.sqrt(np.maximum(s, 0.0))
            best = np.maximum(best, np.where(valid, z, -np.inf))
        cand_z.append(best)
        cand_i.append(near)
    z = np.concatenate(cand_z)
    i = np.concatenate(cand_i)
    if not np.isfinite(z).any():
        return None, None
    k = int(np.argmax(z))
    return float(z[k]), int(i[k])


def terrain_sphere(terrain, x, y, r, step=TERRAIN_SAMPLE_M):
    """Centre z where a sphere of radius r dropped at (x, y) first touches the bilinear terrain, sampled every `step`
    (a lower bound: within about step^2 / (8 r) of the exact contact)."""
    if r <= 0:
        return terrain.ground(x, y)
    n = int(math.ceil(r / step))
    g = np.arange(-n, n + 1) * step
    dx, dy = np.meshgrid(g, g)
    d2 = dx * dx + dy * dy
    m = d2 <= r * r
    h = terrain.bilinear(x + dx[m], y + dy[m])
    return float((h + np.sqrt(r * r - d2[m])).max())


# ------------------------------------------------------------------------------------------------------------- world
def select_refs(staging, radii, points, reach):
    """(placed reference indices, disabled ones, unreadable ones) whose collision bounding sphere comes within reach
    of any (x, y) in points."""
    if not points:
        return [], [], []
    pos = np.array([r["pos"][:2] for r in staging.refs], np.float64)
    rad = np.array([(radii.get(r["base"]) or 0.0) * float(r["scale"]) for r in staging.refs], np.float64)
    bad = np.array([radii.get(r["base"]) is None for r in staging.refs])
    pick = np.zeros(len(staging.refs), bool)
    for x, y in points:
        d = np.hypot(pos[:, 0] - x, pos[:, 1] - y)
        pick |= (d <= rad + reach) & ((rad > 0) | bad)
        pick |= bad & (d <= reach + UNREADABLE_REACH_M)  # unreadable models: assume they reach this far, report them
    idx = np.nonzero(pick)[0].tolist()
    disabled = [k for k in idx if staging.refs[k].get("disabled")]
    unreadable = [k for k in idx if bad[k] and not staging.refs[k].get("disabled")]   # disabled: no collision anyway
    skip = set(disabled) | set(unreadable)
    placed = [k for k in idx if k not in skip]
    return placed, disabled, unreadable


class PlacedWorld:
    """The selected references' converted collision placed with one rotation convention."""

    def __init__(self, staging, refs, convention):
        self.staging, self.convention = staging, convention
        tris, owner, body, local = [], [], [], []
        for k in refs:
            r = staging.refs[k]
            m = staging.model(r["base"])
            if "tris" not in m or not len(m["tris"]):
                continue
            R = rotation(r["rot"], convention)
            w = (m["tris"].reshape(-1, 3) * float(r["scale"])) @ R.T + np.asarray(r["pos"], np.float64)
            tris.append(w.reshape(-1, 3, 3))
            owner.append(np.full(len(m["tris"]), k, np.int64))
            body.append(m["body"])
            local.append(np.arange(len(m["tris"])))
        self.tris = np.concatenate(tris) if tris else np.zeros((0, 3, 3))
        self.owner = np.concatenate(owner) if owner else np.zeros(0, np.int64)
        self.body = np.concatenate(body) if body else np.zeros(0, np.int64)
        self.local = np.concatenate(local) if local else np.zeros(0, np.int64)
        self.index = exterior.SurfaceIndex(self.tris, self.owner, cell=2.0)
        self.terrain = staging.terrain
        self.step = staging.terrain.step

    # the interface make_core64c.waypoint_ok / exterior expect of a world
    def ground(self, x, y):
        return self.terrain.ground(x, y)

    def ground_all(self, x, y):
        return self.terrain.rules(x, y)

    def landing(self, x, y, drop_z, radius=0.6):
        return exterior.landing(self.index.top, self.ground, x, y, drop_z, radius)

    def hit_json(self, z, i, ground):
        k = int(self.owner[i])
        d = self.staging.describe(k, int(self.body[i]))
        d.update(z=round(z, 4), above_terrain=round(z - ground, 4), triangle=int(self.local[i]),
                 slope_deg=round(slope_deg(self.tris[i]), 2))
        return d

    def trace(self, x, y, drop_z, spheres=(), reach=REACH_M):
        g = self.ground(x, y)
        cand = self.index.near(x, y, 0.0)
        hits = [(z, int(cand[i])) for z, i in ray_hits(self.tris[cand], x, y)] if len(cand) else []
        below = [(z, i) for z, i in hits if z <= drop_z]
        top = below[0] if below else None
        support = max(g, top[0]) if top else g
        out = {"terrain": round(g, 4), "terrain_rules": {k: round(v, 4) for k, v in self.ground_all(x, y).items()},
               "hits": [self.hit_json(z, i, g) for z, i in hits],
               "top": self.hit_json(*top, g) if top else None,
               "support": round(support, 4),
               "support_kind": "object" if top and top[0] > g else "terrain"}
        out["discs"] = {}
        for radius in DISCS:
            land = self.landing(x, y, drop_z, radius)
            out["discs"][str(radius)] = {
                "centre": round(land["centre"], 4), "max": round(land["z"], 4), "spread": round(land["spread"], 4),
                "on_object": land["on_object"], "owners": [self.staging.refs[k]["src"] for k in land["owners"]]}
        rings = tuple(r for r in RINGS if r <= reach + 1e-9)
        near = exterior.nearby_object(self.index.top, self.ground, x, y, drop_z, radii=rings, threshold=ELEVATED)
        out["nearest_elevated"] = None if near is None else {
            "within_m": near["distance"], "above_terrain": round(near["height"], 4),
            "ref": self.staging.refs[near["owner"]]["src"],
            "edid": self.staging.bases[self.staging.refs[near["owner"]]["base"]]["edid"]}
        out["spheres"] = {}
        for r in spheres:
            cand = self.index.near(x, y, r)
            cand = cand[self.tris[cand][:, :, 2].min(axis=1) <= drop_z] if len(cand) else cand   # wholly above the drop
            zc, i = sphere_drop(self.tris[cand], x, y, r) if len(cand) else (None, None)
            zt = terrain_sphere(self.terrain, x, y, r)
            if zc is not None and zc > zt:
                k = int(cand[i])
                out["spheres"][str(r)] = {"feet": round(zc - r, 4), "kind": "object", "ref": self.staging.refs[
                    int(self.owner[k])]["src"], "body": int(self.body[k]), "triangle": int(self.local[k])}
            else:
                out["spheres"][str(r)] = {"feet": round(zt - r, 4), "kind": "terrain"}
        return out


# ------------------------------------------------------------------------------------------------------- runner data
def parse_point(text):
    parts = [p.strip() for p in text.split(",")]
    if len(parts) not in (2, 3):
        raise argparse.ArgumentTypeError(f"point {text!r}: X,Y[,LABEL]")
    try:
        x, y = float(parts[0]), float(parts[1])
    except ValueError:
        raise argparse.ArgumentTypeError(f"point {text!r}: X and Y must be numbers")
    return {"label": parts[2] if len(parts) == 3 else f"p{x:.2f}_{y:.2f}", "x": x, "y": y}


def parse3(text):
    try:
        v = [float(t) for t in str(text).split()]
    except ValueError:
        return None
    return v if len(v) == 3 else None


def runner_points(test_dir):
    """Points of one finished runner attempt (spec.json + obs.json) with their readings moved into the local frame:
    x, y minus the merge offset, z minus (the ground reference's read - its plan expectation)."""
    spec = load_json(os.path.join(test_dir, "spec.json"))
    obs = load_json(os.path.join(test_dir, "obs.json"))
    off = obs.get("offset") or [0.0, 0.0, 0.0]
    reads = {p["label"]: parse3(p.get("read")) for p in obs.get("points", [])}
    plan = {p["label"]: p for p in spec.get("points", [])}
    zref = spec.get("z_ref")
    shift = None
    if zref in plan and reads.get(zref):
        shift = reads[zref][2] - float(plan[zref]["expect"])
    out = []
    for p in spec.get("points", []):
        q = {"label": p["label"], "x": float(p["x"]), "y": float(p["y"]), "plan_expect": p.get("expect"),
             "test": spec.get("id"), "drop_z": spec.get("drop_z")}
        rd = reads.get(p["label"])
        if rd is not None:
            q["read"] = rd
            q["read_local"] = [round(rd[0] - off[0], 4), round(rd[1] - off[1], 4),
                               None if shift is None else round(rd[2] - shift, 4)]
            q["xy_error"] = round(math.hypot(q["read_local"][0] - q["x"], q["read_local"][1] - q["y"]), 4)
        q["z_shift"] = None if shift is None else round(shift, 4)
        out.append(q)
    return out


def residuals(point, result, spheres):
    """reading (local z) - each prediction of one convention's trace, and whether it is within MATCH_M."""
    z = (point.get("read_local") or [None, None, None])[2]
    if z is None:
        return None
    preds = {"support": result["support"], "disc_0.6_max": result["discs"]["0.6"]["max"]}
    for r in spheres:
        preds[f"sphere_{r}"] = result["spheres"][str(r)]["feet"]
    return {k: {"predicted": v, "residual": round(z - v, 4), "match": abs(z - v) <= MATCH_M} for k, v in preds.items()}


# ---------------------------------------------------------------------------------------------------------- commands
def make_worlds(staging, points, conventions, reach, cache):
    radii = staging.radii(cache)
    placed, disabled, unreadable = select_refs(staging, radii, [(p["x"], p["y"]) for p in points], reach)
    worlds = {c: PlacedWorld(staging, placed, c) for c in conventions}
    return worlds, {"placed": len(placed), "disabled": [staging.refs[k]["src"] for k in disabled],
                    "unreadable_index": unreadable,
                    "unreadable": [{"ref": staging.refs[k]["src"], "model": staging.bases[staging.refs[k]["base"]]["model"],
                                    "error": staging.model(staging.refs[k]["base"]).get("error")} for k in unreadable],
                    "models_without_collision_radius": sum(1 for v in radii.values() if v == 0.0),
                    "models": len(radii)}


def pins(staging, extra=()):
    out = {"objects.json": sha256(staging.objects_path), "btd": sha256(staging.btd_path)}
    for name in ("FO4TerrainCore.esm", "plan.json", "expected.json"):
        path = os.path.join(staging.root, name)
        if os.path.exists(path):
            out[name] = sha256(path)
    for label, path in extra:
        out[label] = sha256(path)
    return out


def trace_points(staging, points, conventions=tuple(CONVENTIONS), drop_z=DROP_Z, spheres=(), reach=REACH_M, cache=None):
    reach = max(reach, max(spheres, default=0.0), max(DISCS))
    worlds, selection = make_worlds(staging, points, conventions, reach, cache)
    bad = selection.pop("unreadable_index")
    out = []
    for p in points:
        dz = float(p.get("drop_z") or drop_z)
        q = dict(p)
        near_bad = [staging.refs[k]["src"] for k in bad if math.hypot(staging.refs[k]["pos"][0] - p["x"],
                                                                       staging.refs[k]["pos"][1] - p["y"])
                    <= reach + UNREADABLE_REACH_M]
        q["status"] = "INCONCLUSIVE" if near_bad else "TRACED"
        if near_bad:
            q["unreadable_refs"] = near_bad
        q["conventions"] = {}
        for c, w in worlds.items():
            res = w.trace(p["x"], p["y"], dz, spheres, reach)
            res["vs_read"] = residuals(p, res, spheres)
            q["conventions"][c] = res
        out.append(q)
    return out, selection


def summary(points, conventions, spheres):
    """Per convention and prediction: readings explained within MATCH_M and within the runner's tolerance."""
    out = {}
    for c in conventions:
        for key in ["support", "disc_0.6_max"] + [f"sphere_{r}" for r in spheres]:
            rs = [p["conventions"][c]["vs_read"][key]["residual"] for p in points
                  if p["conventions"][c].get("vs_read")]
            if not rs:
                continue
            out[f"{c}/{key}"] = {"readings": len(rs), "within_match_m": sum(abs(r) <= MATCH_M for r in rs),
                                 "within_runner_tolerance": sum(abs(r) <= RUNNER_TOLERANCE for r in rs),
                                 "max_abs_residual": round(max(abs(r) for r in rs), 4)}
    return out


def cmd_trace(a):
    staging = Staging(a.staging, a.btd)
    points = list(a.point or [])
    for d in a.runner_test or []:
        points += runner_points(d)
    if not points:
        raise SystemExit("no points: pass --point or --runner-test")
    conventions = [c.strip() for c in a.conventions.split(",") if c.strip()]
    for c in conventions:
        rotation((0, 0, 0), c)
    spheres = [float(s) for s in a.sphere.split(",")] if a.sphere else []
    traced, selection = trace_points(staging, points, conventions, a.drop_z, spheres, a.reach, a.bounds_cache)
    report = {"tool": "scripts/terrain/collision_surface.py trace", "staging_world": staging.world,
              "conventions": {c: describe_convention(c) for c in conventions}, "reach_m": a.reach, "selection": selection,
              "pins": pins(staging), "summary": summary(traced, conventions, spheres), "points": traced}
    for p in traced:
        line = [f"{p['label']:28s} ({p['x']:.4f}, {p['y']:.4f})"]
        rl = p.get("read_local")
        if rl:
            line.append(f"read {rl[2]}")
        for c in conventions:
            r = p["conventions"][c]
            who = r["top"]["edid"] if r["support_kind"] == "object" else "terrain"
            line.append(f"{c}: {r['support']:.4f} {who}")
        print("  ".join(line))
    for k, v in report["summary"].items():
        print(f"{k:24s} {v}")
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1)
    return 2 if any(p["status"] == "INCONCLUSIVE" for p in traced) else 0


def clear_ok(world, x, y, drop_z, clear_m=CLEAR_M):
    """make_core64c.waypoint_ok's rule plus no surface above the terrain within clear_m. (terrain z, spread) or None."""
    sys.path.insert(0, HERE)
    import make_core64c  # noqa: E402  (imported late: it pulls in the stage pipeline)
    ok = make_core64c.waypoint_ok(world, x, y, drop_z)
    if ok is None:
        return None
    rings = tuple(r for r in RINGS if r <= clear_m + 1e-9)
    if exterior.nearby_object(world.index.top, world.ground, x, y, drop_z, radii=rings, per_ring=36,
                              threshold=-0.05) is not None:
        return None
    return ok


def teleport_legs(world, x, y, prev, nxt, drop_z):
    """What the runner's teleports into (x, y) from prev (x, y, z standing) and out of it to nxt (x, y) pass through
    (exterior.setpos_path: setpos x, then y, then z; the way out starts on the terrain at (x, y), its drop is the next
    point's business): {"in": [{"pos", "hits"}], "out": [...]}, hits = reference FormKeys or "terrain"."""
    def hits(q):
        return [h if h == "terrain" else world.staging.refs[h]["src"]
                for h in exterior.capsule_hits(world.index, world.ground, *q)]
    out = {"in": [], "out": []}
    if prev:
        out["in"] = [{"pos": [round(v, 3) for v in q], "hits": hits(q)}
                     for q in exterior.setpos_path(tuple(prev), (x, y), drop_z)]
    if nxt:
        out["out"] = [{"pos": [round(v, 3) for v in q], "hits": hits(q)}
                      for q in exterior.setpos_path((x, y, world.ground(x, y)), tuple(nxt[:2]), drop_z)[:2]]
    return out


def cmd_clear(a):
    staging = Staging(a.staging, a.btd)
    conventions = [c.strip() for c in a.conventions.split(",") if c.strip()]
    near = a.near
    step = 0.5
    n = int(a.search_m / step)
    cands = sorted((i * i + j * j, round(near["x"] + step * i, 4), round(near["y"] + step * j, 4))
                   for i in range(-n, n + 1) for j in range(-n, n + 1) if (i * i + j * j) * step * step <= a.search_m ** 2)
    reach = a.search_m + max(a.clear_m, 1.0) + 1.0
    # every place a candidate's checks look at: the candidate area, and the teleports' intermediate positions
    # (setpos x first: (candidate x, previous y), then (next x, candidate y))
    extra = [(near["x"], near["y"])]
    if a.prev:
        extra.append((near["x"], a.prev[1]))
    if a.next:
        extra.append((a.next[0], near["y"]))
    worlds, selection = make_worlds(staging, [{"x": x, "y": y} for x, y in extra], conventions, reach, a.bounds_cache)
    if selection.pop("unreadable_index"):              # an object we cannot see may stand anywhere near: no proposal
        cands = []
    found, rejected_legs = None, 0
    for _, x, y in cands:
        oks = {c: clear_ok(w, x, y, a.drop_z, a.clear_m) for c, w in worlds.items()}
        if any(v is None for v in oks.values()):
            continue
        legs = {c: teleport_legs(w, x, y, a.prev, a.next, a.drop_z) for c, w in worlds.items()}
        if any(q["hits"] for lg in legs.values() for q in lg["in"] + lg["out"]):
            rejected_legs += 1
            continue
        found = (x, y, oks, legs)
        break
    report = {"tool": "scripts/terrain/collision_surface.py clear", "near": near, "search_m": a.search_m,
              "clear_m": a.clear_m, "conventions": {c: describe_convention(c) for c in conventions}, "selection": selection,
              "pins": pins(staging), "clear_but_teleport_overlaps": rejected_legs, "point": None}
    if selection["unreadable"]:
        report["status"] = "INCONCLUSIVE"
        print(f"INCONCLUSIVE: unreadable collision near {near['label']}: {selection['unreadable']}")
    elif found is None:
        print(f"no collision-clear terrain point within {a.search_m} m of {near['label']}")
    else:
        x, y, oks, legs = found
        w0 = worlds[conventions[0]]
        g = w0.ground(x, y)
        pt = {"label": a.label or f"{near['label']}_clear", "x": x, "y": y, "kind": "terrain", "expect": round(g, 4),
              "terrain_expect": round(g, 4), "terrain_rules": {k: round(v, 5) for k, v in w0.ground_all(x, y).items()},
              "disc_spread": round(oks[conventions[0]][1], 4),
              "distance_from_near_m": round(math.hypot(x - near["x"], y - near["y"]), 3),
              "per_convention": {c: {"landing": round(w.landing(x, y, a.drop_z)["centre"], 4),
                                     "teleport_in": legs[c]["in"], "teleport_out": legs[c]["out"]}
                                 for c, w in worlds.items()}}
        if a.fo4:
            pt["fo4_land"] = fo4_land_height(a.fo4, x, y)
            if pt["fo4_land"] is not None:
                pt["btd_minus_fo4_land"] = round(g - pt["fo4_land"], 4)
        report["point"] = pt
        print(json.dumps(pt, indent=1))
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1)
    return 2 if selection["unreadable"] else 0 if found else 1


def fo4_land_height(esm, x, y):
    """FO4's own terrain height (LAND, bilinear on the merged vertex grid of the 3 x 3 cells around) at local (x, y)."""
    from fo4sf import fo4land
    ux, uy = x * 70.0, y * 70.0
    cx, cy = int(math.floor(ux / fo4land.CELL_UNITS)), int(math.floor(uy / fo4land.CELL_UNITS))
    wanted = {(i, j) for i in range(cx - 1, cx + 2) for j in range(cy - 1, cy + 2)}
    with fo4land.Plugin(esm) as p:
        world = p.read_world("Commonwealth", cells=wanted, refs=False)
    grids = {xy: fo4land.decode_vhgt(c["vhgt"]) for xy, c in world["cells"].items() if c["vhgt"]}
    merged, _ = fo4land.merge_cells(grids, cx - 1, cy - 1, 3, 3)
    h = fo4land.height_at(merged, (cx - 1) * fo4land.CELL_UNITS, (cy - 1) * fo4land.CELL_UNITS, ux, uy)
    return None if h is None or not math.isfinite(h) else round(h / 70.0, 4)


# --------------------------------------------------------------------------------------------- FO4 precombine oracle
PACKED_TYPES = ("BSPackedCombinedSharedGeomDataExtra", "BSPackedCombinedGeomDataExtra")
COMBINED_SIZE = 72             # BSPackedGeomDataCombined: f32 grayscale scale, NiTransform (9 + 3 + 1 f32), NiBound


def packed_instances(blk, shared=True):
    """[(rotation 9-tuple row-major, translation (FO4 units), scale)] of every combined instance in one
    BSPackedCombined(Shared)GeomDataExtra block (FO4 layout: NiExtraData name i32, vertex desc u64, vertex / triangle
    counts, two flag words, data count, (shape id, offset) per data, then per data 8 u32 (vertex count, LOD levels,
    three LOD triangle count / offset pairs), the instance count, the instances and a vertex desc u64; the unshared
    variant also carries vertex and triangle data, which is not read). Raises ValueError unless the shared layout
    consumes the block exactly."""
    p = 4 + 8
    if len(blk) < p + 20:
        raise ValueError("block too short")
    _nv, _nt, _f1, _f2, ndata = struct.unpack_from("<5I", blk, p)
    p += 20 + 8 * ndata
    out = []
    for _ in range(ndata):
        p += 32
        ncomb, = struct.unpack_from("<I", blk, p)
        p += 4
        if p + COMBINED_SIZE * ncomb > len(blk):
            raise ValueError("instance array runs past the block")
        for k in range(ncomb):
            at = p + COMBINED_SIZE * k
            out.append((struct.unpack_from("<9f", blk, at + 4), struct.unpack_from("<3f", blk, at + 40),
                        struct.unpack_from("<f", blk, at + 52)[0]))
        p += COMBINED_SIZE * ncomb + 8
        if not shared:
            raise ValueError("unshared packed geometry: vertex data not parsed")
    if p != len(blk):
        raise ValueError(f"parsed {p} of {len(blk)} bytes")
    return out


def compare_rotations(refs, instances, conventions, tol=1e-4, match_units=0.5, scale_tol=1e-3):
    """refs: [{"src", "pos" (metres), "rot", "scale"}]; instances: [(rot9, translation units, scale)] of the same FO4
    cell. Each reference is compared with the one instance at its position (within match_units) with its scale; a
    position holding several such instances is ambiguous and skipped. Returns {"matched", "ambiguous", "unmatched",
    per convention {"exact", "max_abs"}}, "examples": first non-exact per convention}."""
    out = {"matched": 0, "ambiguous": 0, "unmatched": 0, "conventions": {c: {"exact": 0, "max_abs": 0.0} for c in conventions},
           "examples": {}}
    if not instances:
        out["unmatched"] = len(refs)
        return out
    T = np.array([t for _, t, _ in instances], np.float64)
    S = np.array([s for *_, s in instances], np.float64)
    for r in refs:
        d = np.linalg.norm(T - np.asarray(r["pos"], np.float64) * 70.0, axis=1)
        ks = np.nonzero((d <= match_units) & (np.abs(S - float(r["scale"])) <= scale_tol))[0]
        if len(ks) != 1:
            out["ambiguous" if len(ks) else "unmatched"] += 1
            continue
        out["matched"] += 1
        M = np.array(instances[int(ks[0])][0], np.float64).reshape(3, 3)
        for c in conventions:
            e = float(np.abs(M - rotation(r["rot"], c)).max())
            st = out["conventions"][c]
            st["max_abs"] = max(st["max_abs"], round(e, 6))
            if e <= tol:
                st["exact"] += 1
            elif c not in out["examples"]:
                out["examples"][c] = {"ref": r["src"], "rot": r["rot"], "max_abs": round(e, 6)}
    return out


def cmd_rotations(a):
    from fo4sf import ba2, fo4land, nif
    objects = load_json(os.path.join(a.staging, "objects.json"))
    lim = math.radians(a.min_tilt_deg)
    cells = {}
    for r in objects["refs"]:
        if math.hypot(r["rot"][0], r["rot"][1]) > lim:
            c = (int(math.floor(r["pos"][0] * 70.0 / 4096.0)), int(math.floor(r["pos"][1] * 70.0 / 4096.0)))
            cells.setdefault(c, []).append(r)
    order = sorted(cells, key=lambda c: (-len(cells[c]), c))
    if a.cells:
        order = order[:a.cells]
    with fo4land.Plugin(a.fo4_esm or os.path.join(a.fo4_data, "Fallout4.esm")) as p:
        world = p.read_world("Commonwealth", cells=set(order), refs=False)
    names = {}
    for fn in sorted(os.listdir(a.fo4_data)):
        if fn.lower().startswith("fallout4 - meshes") and fn.lower().endswith(".ba2"):
            arc = ba2.Ba2(os.path.join(a.fo4_data, fn))
            for n in arc.names:
                low = n.lower().replace("/", "\\")
                if low.startswith("meshes\\precombined\\") and low.endswith("_oc.nif"):
                    names.setdefault(low.rsplit("\\", 1)[-1].split("_")[0], []).append((arc, n))
    conventions = [c.strip() for c in a.conventions.split(",") if c.strip()]
    total = {"cells": 0, "cells_with_precombines": 0, "tilted_refs": 0, "matched": 0, "ambiguous": 0, "unmatched": 0,
             "parse_errors": 0, "conventions": {c: {"exact": 0, "max_abs": 0.0} for c in conventions}, "examples": {}}
    for c in order:
        cell = world["cells"].get(c)
        total["cells"] += 1
        total["tilted_refs"] += len(cells[c])
        insts = []
        for arc, n in (names.get(f"{cell['fid']:08x}", []) if cell else []):
            f = nif.parse(arc.read(n))
            for i in range(len(f.blocks)):
                if f.type_of(i) in PACKED_TYPES:
                    try:
                        insts += packed_instances(f.blocks[i], shared=f.type_of(i) == PACKED_TYPES[0])
                    except (ValueError, struct.error):
                        total["parse_errors"] += 1
        total["cells_with_precombines"] += bool(insts)
        res = compare_rotations(cells[c], insts, conventions)
        for k in ("matched", "ambiguous", "unmatched"):
            total[k] += res[k]
        for cv in conventions:
            total["conventions"][cv]["exact"] += res["conventions"][cv]["exact"]
            total["conventions"][cv]["max_abs"] = max(total["conventions"][cv]["max_abs"], res["conventions"][cv]["max_abs"])
            if cv in res["examples"] and cv not in total["examples"]:
                total["examples"][cv] = res["examples"][cv]
    print(json.dumps(total, indent=1))
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump({"tool": "scripts/terrain/collision_surface.py rotations", "min_tilt_deg": a.min_tilt_deg,
                       "conventions": {c: describe_convention(c) for c in conventions},
                       "objects_sha256": sha256(os.path.join(a.staging, "objects.json")), "result": total}, f, indent=1)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--staging", required=True, help="staged overlay folder (objects.json, Data\\)")
    common.add_argument("--btd", help="BTD to use (default: the staging's Data\\Terrain\\<world>.btd)")
    common.add_argument("--conventions", default=",".join(CONVENTIONS), help="rotation conventions (xyz, zyx)")
    common.add_argument("--drop-z", type=float, default=DROP_Z)
    common.add_argument("--bounds-cache", help="JSON cache of every model's collision radius")
    common.add_argument("--out")
    t = sub.add_parser("trace", parents=[common])
    t.add_argument("--point", type=parse_point, action="append")
    t.add_argument("--runner-test", action="append", help="finished runner attempt folder (spec.json + obs.json)")
    t.add_argument("--sphere", default="", help="sphere radii to drop (m), e.g. 0.3,0.4,0.5")
    t.add_argument("--reach", type=float, default=REACH_M)
    c = sub.add_parser("clear", parents=[common])
    c.add_argument("--near", type=parse_point, required=True)
    c.add_argument("--label")
    c.add_argument("--search-m", type=float, default=30.0)
    c.add_argument("--clear-m", type=float, default=CLEAR_M)
    c.add_argument("--prev", type=lambda s: [float(v) for v in s.split(",")], help="X,Y,Z the player stands at before")
    c.add_argument("--next", type=lambda s: [float(v) for v in s.split(",")], help="X,Y of the next point")
    c.add_argument("--fo4", help="Fallout4.esm: report FO4's own LAND height at the point")
    r = sub.add_parser("rotations")
    r.add_argument("--staging", required=True, help="staged overlay folder (objects.json)")
    r.add_argument("--fo4-data", required=True, help="FO4 Data folder (Fallout4 - Meshes*.ba2)")
    r.add_argument("--fo4-esm", help="Fallout4.esm (default: <fo4-data>\\Fallout4.esm)")
    r.add_argument("--conventions", default="xyz,xzy,yxz,yzx,zxy,zyx")
    r.add_argument("--min-tilt-deg", type=float, default=3.0)
    r.add_argument("--cells", type=int, default=0, help="only the N cells with the most tilted references (0: all)")
    r.add_argument("--out")
    a = ap.parse_args(argv)
    return {"trace": cmd_trace, "clear": cmd_clear, "rotations": cmd_rotations}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
