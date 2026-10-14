"""Build movement test routes for a converted cell from Fallout 4's own data (no guessing from screenshots).

usage: python routes.py --fo4-data <FO4 Data> --cell-json <cell.json> --manifest <manifest.json> --out routes.json
                        [--formids formids.json] [--max 40] [--probes-out probes.json]

Stairs: every placed model whose FO4 collision has a stair ramp: the L_STAIRHELPER body (layer 31) if present, else the
collision triangles sloped 20-50 degrees. The ramp's low and high ends (node space -> placement) give a start point 0.8 m
before the low end, the heading towards the high end, and the expected height at the top. Ends steeper than
MAX_RAMP_SLOPE apart are not a ramp (bevels on a railing frame) and get no route; they are listed as skipped.
A foot buried under the neighbours' floors (terrain, mounds, or a floor slab less than a player's height above the
ramp) moves the start to where the ramp comes out of them. Every candidate lane across the ramp (the centre first,
then 0.25 m steps to either side) is walked offline over FO4's own collision of the stair and its neighbours
(fo4sf.walksim: a 0.35 x 1.8 m capsule, one-sided triangles; doors open by default and movable objects left out): the
first lane whose start is free and whose walk climbs the flight is the route; a stair with no such lane (a wall,
railing, closed door or debris in the way, no floor at the start, a lift through a floor slab, a flight rising less
than MIN_RISE) is listed as skipped with the reason (docs/ai/research-log.md, 2026-10-13).
What the walk cannot vouch for is written on the route: "helper_crossing" when the walk meets the place where the
converter's flattened stair helper comes up through the floor (moved from FO4's; batch_full 0002 / 0003 stopped there,
cause unresolved), and "movable_near" for movable objects the walk leaves out. --probes-out writes, for each route with
a helper crossing, the route itself, a probe with a run-up before the crossing and one starting past it
(docs/testing/stairs-routes.md, sections 1a and 5).
Models are placed as the game places them: the NIF's scene root transform is not applied (nif.world_transforms).
Doors: every placed converted door (manifest item with "door"): start 1.6 m in front of the FO4 origin facing through
the opening, press E, walk; pass = the player ends at least 1 m past the door plane.
Coordinates are metres in Starfield cell space (FO4 units / 70); reference rotations use Bethesda's clockwise angles,
composed as FO4's precombined physics shows (ref_matrix).
"""
import argparse
import json
import math
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src"))
from fo4sf import fo4_compounds, fo4collision, hkpackfile, meshcollision, nif, pipeline, walksim  # noqa: E402

UNIT = 1.0 / 70.0
STAIRHELPER = 31
RUN_SPEED = 4.6        # m/s: unobstructed batch_full stairs walks moved 4.4-4.9 m/s over their walk_ms (631-2229 ms)
MIN_WALK = 2.9         # metres (630 ms): no shorter walk has been measured in game
START_BACK = 0.8       # the start stands this far before the ramp's (emerged) low end
START_BACKS = (START_BACK, 0.5, 0.3)   # or closer, when that spot is taken or has no floor (_check_foot)
OVERSHOOT = 0.6        # walk this far past the high end; it was about 2 m (walk_ms assumed 4 m/s, plus 1 m), which
#                        walked BldDecoSmStairsShort01 0F032D off its top into the collapsed floor (batch_full 0022)
EDGE_MARGIN = 0.5      # a walk must stay clear of drops for this much further (the player does not stop dead)
MIN_RISE = 0.2         # a flight rising less above its surroundings is no stairs test (Vault 114's CinderBlockStairs02
#                        rises 0.15 m out of the cave floor: supervised_1011 0010 "STUCK" at 0.10 of 0.12 after walking
#                        2.7 m over it; Cambridge's HitFloorEdge02Stairs01 rising 0.23 m out of debris passed, 0140 / 0143)
LANE_STEP = 0.25       # lanes across the ramp, from the centre out
CLEARANCES = (0.1, 0.0)  # lanes are first checked with this much more room than the assumed 0.35 m capsule needs (the
#                        radius is assumed, +-0.1 m: Cambridge 0135 / 0143 started 0.1-0.2 m closer to
#                        rails); a stair with no such lane takes the first lane that fits the bare capsule, marked
#                        "tight" (Diamond City's ShackStairs01 between two shack walls passed in game, batch_full 0248)
CROSSING_STEP = 0.02   # metres along the walk between samples of the helper's top face (helper_crossing)
CROSSING_MOVED = 0.02  # a converted crossing closer than this to FO4's is FO4's own (not recorded)
PROBE_PAST = walksim.PLAYER_RADIUS + 0.25   # the past-crossing probe starts this far beyond the crossing, so the
#                        capsule standing there does not reach back to it
PROBE_RUNUP = 1.3      # the run-up probe starts this far before the crossing: batch_full 0002 / 0003 came up on the
#                        library's gallery slab about 1.3 m before the crossing (offline lift point) and ran into it
MOVABLE_MARGIN = 0.45  # movable objects whose collision comes within PLAYER_RADIUS + this of a walk line are listed
MOVABLE_TOUCH = walksim.PLAYER_RADIUS + 0.1   # and a lane that would touch one is the last choice (plan_stairs)


def ref_matrix(rot):
    """Row-major world rotation of a reference (radians, Bethesda clockwise angles): R = Rx(-x) Ry(-y) Rz(-z), i.e.
    the model turns about Z first, then Y, then X (fixed axes). Verified against FO4's precombined physics: of the
    tilted references of BostonPublicLibrary02 found in its precombine, 312 match only this composition, 3 only the
    X-first one (Rz Ry Rx, used here before and still in exterior.ref_matrix and PluginSpike.RotateOffset), 85 both;
    the debris piles and fallen floor chunks on the library stairs match it 93-100 % against 0-13 %
    (docs/ai/research-log.md, 2026-10-13). Pure Z rotations (most stairs, doors and walls) agree either way."""
    cx, sx = math.cos(-rot[0]), math.sin(-rot[0])
    cy, sy = math.cos(-rot[1]), math.sin(-rot[1])
    cz, sz = math.cos(-rot[2]), math.sin(-rot[2])
    rx = (1, 0, 0, 0, cx, -sx, 0, sx, cx)
    ry = (cy, 0, sy, 0, 1, 0, -sy, 0, cy)
    rz = (cz, -sz, 0, sz, cz, 0, 0, 0, 1)
    return nif._matmul(rx, nif._matmul(ry, rz))


def apply(m, v):
    return tuple(m[3 * i] * v[0] + m[3 * i + 1] * v[1] + m[3 * i + 2] * v[2] for i in range(3))


def collision_bodies(f, compounds=False):
    """(layer, points, triangles) of every FO4 collision body of a NIF, points in NIF root space (metres), placed as the
    game places a reference: without the scene root's own transform (nif.world_transforms placed=True).
    compounds=True also decodes hknpDynamicCompoundShape bodies (fo4_compounds: furniture and props such as
    HightechOfficeChair or OfficeFileCabinetDrawer01, which the converter turns into several convex bodies), one
    (layer, points, triangles) per leaf; without it they are skipped, as the terrain scripts expect."""
    world = nif.world_transforms(f, placed=True)
    for i in range(len(f.blocks)):
        if f.type_of(i) != "bhkNPCollisionObject":
            continue
        target, _, data = struct.unpack_from("<iHi", f.blocks[i], 0)
        body = struct.unpack_from("<I", f.blocks[i], 10)[0] if len(f.blocks[i]) >= 14 else 0
        if not (0 <= data < len(f.blocks)) or f.type_of(data) != "bhkPhysicsSystem":
            continue
        n, = struct.unpack_from("<I", f.blocks[data], 0)
        try:
            p = hkpackfile.Packfile(f.blocks[data][4:4 + n])
        except hkpackfile.PackfileError:
            continue
        classes = dict(p.objects())
        sysobj = next(o for o, c in classes.items() if c == "hknpPhysicsSystemData")
        at, nb = p.array(sysobj + fo4collision.SYS_BODIES)
        tr, rot, _ = world(target)
        to_root = lambda v: tuple(a + b * UNIT for a, b in zip(apply(rot, v), tr))
        for k in ([body] if 0 <= body < nb else []):
            b = at + fo4collision.BODY_SIZE * k
            shape = p.pointer(b)
            layer = p.unpack("<I", b + 20)[0] & 0x7F
            cls = classes.get(shape)
            try:
                if cls == "hknpConvexPolytopeShape":
                    pts, tris = fo4collision._convex(p, shape)
                elif cls == "hknpCompressedMeshShape":
                    pts, tris = fo4collision._compressed_mesh(p, p.pointer(shape + fo4collision.CMS_DATA))
                elif cls == "hknpDynamicCompoundShape" and compounds:
                    for leaf in fo4_compounds.decode_body(f.blocks[data][4:4 + n], k)["leaves"]:
                        yield layer, [to_root(v) for v in leaf["points"]], leaf["triangles"]
                    continue
                else:
                    continue
            except (IndexError, ValueError, hkpackfile.PackfileError):
                continue
            yield layer, [to_root(v) for v in pts], tris


# A ramp's low and high ends (ends()) must be a walkable run apart. Every FO4 stair ramp in the 15 converted cells is at
# most 46.4 degrees end to end (V111HallStairs01's helper); the railing frames around the Prydwen stairwells
# (PryPlatformInCornerStairs01/02, PryPlatformWallStairs01) only have small 20-50 degree bevels on their posts, whose
# lowest and highest points sit 0.03 m apart under a 0.91 m rise (88 degrees): not a ramp.
MAX_RAMP_SLOPE = 60.0
NOT_A_RAMP = "sloped triangles, no ramp"


def ramp_slope(points):
    """Slope in degrees of the line from a ramp's low end to its high end (90 when they are stacked)."""
    lo, hi = ends(points)
    return math.degrees(math.atan2(hi[2] - lo[2], math.hypot(hi[0] - lo[0], hi[1] - lo[1])))


def ramp_points(f):
    """Node-space-transformed (NIF root, metres) points of the stair ramp of a FO4 NIF and how they were found:
    ([], None) if it has no sloped collision at all, ([], NOT_A_RAMP) if what it has is not a ramp (ramp_slope above
    MAX_RAMP_SLOPE)."""
    helper, sloped = [], []
    for layer, pts, tris in collision_bodies(f):
        if layer == STAIRHELPER:
            helper += pts
            continue
        for t in tris:
            a, b_, c = (pts[x] for x in t)
            u = [b_[q] - a[q] for q in range(3)]
            v = [c[q] - a[q] for q in range(3)]
            nrm = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            ln = math.sqrt(sum(x * x for x in nrm)) or 1
            tilt = math.degrees(math.acos(max(-1, min(1, nrm[2] / ln))))
            if 20 < tilt < 50:
                sloped += [a, b_, c]
    for pts, how in ((helper, "stairhelper"), (sloped, "sloped-collision")):
        if pts and ramp_slope(pts) <= MAX_RAMP_SLOPE:
            return pts, how
    return ([], NOT_A_RAMP) if helper or sloped else ([], None)


def walkable_triangles(f):
    """Upward-facing collision triangles (normal z / |n| >= 0.3, front face by winding) of a FO4 NIF in NIF root
    space: what can be stood on. Downward faces (ceiling tiles, undersides) are not floors: FO4 collision is one-sided
    (BldDecoSmFlrOnly01 faces up, BldDecoSmCeilOnly01 down; fo4sf.walksim). Only layers a player stands on
    (walksim.BLOCKING_LAYERS, the stair helper left out); compound bodies (furniture) included."""
    out = []
    for layer, pts, tris in collision_bodies(f, compounds=True):
        if layer == STAIRHELPER or layer not in walksim.BLOCKING_LAYERS:
            continue
        for t in tris:
            a, b, c = (pts[x] for x in t)
            u = [b[q] - a[q] for q in range(3)]
            v = [c[q] - a[q] for q in range(3)]
            nz = u[0] * v[1] - u[1] * v[0]
            ln = math.sqrt((u[1] * v[2] - u[2] * v[1]) ** 2 + (u[2] * v[0] - u[0] * v[2]) ** 2 + nz * nz)
            if ln > 1e-9 and nz / ln >= 0.3:
                out.append((a, b, c))
    return out


def solid_triangles(f):
    """Every collision triangle of a FO4 NIF on a layer that stops a walking player (walksim.BLOCKING_LAYERS, the
    stair helper included), in NIF root space, winding kept; compound bodies (furniture) included. Stair helpers
    steeper than meshcollision.STAIR_HELPER_MAX_SLOPE are flattened as the converter flattens them (their foot moves
    out along the ramp), so the walk sees the ramp the game has."""
    out = []
    for layer, pts, tris in collision_bodies(f, compounds=True):
        if layer not in walksim.BLOCKING_LAYERS:
            continue
        if layer == STAIRHELPER:
            pts = meshcollision._flatten_helper(pts, tris, None)
        out += [tuple(pts[x] for x in t) for t in tris]
    return out


def helper_pairs(f):
    """[(FO4 triangle, converted triangle)] of every stair-helper (layer 31) triangle of a FO4 NIF in NIF root space:
    the converted one flattened as the converter flattens it (meshcollision._flatten_helper; the same triangle when
    the helper is gentle enough). helper_crossing() compares the two."""
    out = []
    for layer, pts, tris in collision_bodies(f, compounds=True):
        if layer != STAIRHELPER:
            continue
        flat = meshcollision._flatten_helper(pts, tris, None)
        out += [(tuple(pts[x] for x in t), tuple(flat[x] for x in t)) for t in tris]
    return out


def tread_levels(f):
    """Distinct heights (metres, NIF root space) of a model's treads: upward collision triangles that are nearly flat
    (nz/|n| >= 0.9), stair-helper bodies left out; heights within 4 cm are one tread. A flight has 3 or more. Railings
    and trims named "stair" have none (library run 2026-10-11: all 7 routes on BldDecoSmRailStairs* ended STUCK or
    FALL; they are rails beside the stairs, the steps are another model), so they get no stairs route."""
    zs = []
    for layer, pts, tris in collision_bodies(f):
        if layer == STAIRHELPER:
            continue
        for t in tris:
            a, b, c = (pts[x] for x in t)
            u = [b[q] - a[q] for q in range(3)]
            v = [c[q] - a[q] for q in range(3)]
            n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            ln = math.sqrt(sum(x * x for x in n))
            if ln > 1e-9 and n[2] / ln >= 0.9:
                zs += [a[2], b[2], c[2]]
    levels = []
    for z in sorted(zs):
        if not levels or z - levels[-1] > 0.04:
            levels.append(z)
    return levels


def door_twins(refs, items):
    """{formkey: formkey} for door references placed on the same spot (within 0.1 m). FO4 double doors are two
    single-leaf doors, each hinged at its own jamb (library BldWoodPDbDoor01 100196 + 10019C, rotated 180 degrees to
    each other); a route through the middle is blocked by the second leaf until that door is activated as well."""
    doors = [r for r in refs
             if r.get("model") and items.get("meshes\\" + r["model"].lstrip("\\").lower(), {}).get("door")]
    out = {}
    for i, a in enumerate(doors):
        for b in doors[i + 1:]:
            if all(abs(a["pos"][k] - b["pos"][k]) <= 0.1 / UNIT for k in range(3)):
                out[a["formkey"]] = b["formkey"]
                out[b["formkey"]] = a["formkey"]
    return out


def surface_z(tris, x, y, below):
    """Highest z of any triangle over (x, y) that is not above `below`, or None."""
    best = None
    for a, b, c in tris:
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        l1 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / d
        l2 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / d
        l3 = 1 - l1 - l2
        if min(l1, l2, l3) < -1e-6:
            continue
        z = l1 * a[2] + l2 * b[2] + l3 * c[2]
        if z <= below and (best is None or z > best):
            best = z
    return best


BURY_ABOVE = walksim.PLAYER_HEIGHT    # a floor less than a player's height above the ramp buries it


def emerge(lo, hi, ground, above=BURY_ABOVE):
    """Where a ramp from lo to hi comes out of the surrounding ground: (fraction along the ramp, ground z there or None).
    FO4 sinks the foot of stairs into terrain and mounds (Parsons' retaining-wall stairs start 2.5 m below the grass),
    and under floor slabs: BostonPublicLibrary02's 3.66 m BldDecoSmStairs03 / StairsBlock03 bridge a 2.05 m step to
    the gallery, their lower half under the gallery floor 1.69 m above the foot, and nothing under that foot but the
    void. Teleporting to a buried foot puts the player under the floor (batch_full 0002 / 0003 started there; both
    stopped on the slab where the converted helper comes up through it, docs/testing/stairs-routes.md section 1a).
    ground(x, y, below) is the highest walkable surface of the neighbouring models; one up
    to `above` over the ramp buries it (it was 1.5 m: missed the gallery slab).
    Where nothing at all lies under or near the ramp (it hangs in the void), any floor over it up to the flight's top
    buries it: BostonPublicLibrary02's BldDecoSmStairs01 0EF6A4 rises 3.66 m from 2.74 m under the floor it ends on,
    and StairsBlock01 0EF797's foot even sticks out past that floor's edge into the void (skipped over when a covered
    part follows)."""
    steps = 40
    first_void = None                        # the first sample of a void stretch no covered sample has followed yet
    for s in range(steps + 1):
        t = s / steps
        p = tuple(lo[i] + t * (hi[i] - lo[i]) for i in range(3))
        g = ground(p[0], p[1], p[2] + above)
        if g is not None and g <= p[2] + 0.15:                       # a floor at the ramp: it is out here
            return first_void or (t, g)
        if g is None:
            cover = ground(p[0], p[1], hi[2] + 0.15)
            if cover is None or cover <= p[2] + 0.15:                # nothing under, near or over the ramp
                first_void = first_void or (t, None)
                continue
        first_void = None                                            # under a floor
    return first_void or (1.0, None)


def door_frame(f):
    """(centre, unit normal) of a door model in its local space (metres): bounds of all render shapes, normal along the
    thinner horizontal axis. None if it has no geometry."""
    pts = []
    hinge = nif.door_hinge(f, placed=True)          # the closed leaf spans the opening: use it alone when there is one
    moving = nif.descendants(f, hinge[0]) if hinge else None
    for s in nif.fo4_trishapes(f, placed=True):
        if moving is not None and s.block not in moving:
            continue
        for v in s.positions:
            pts.append(tuple((sum(s.rotation[3 * r + k] * v[k] for k in range(3)) * s.scale + s.translation[r]) * UNIT
                             for r in range(3)))
    if not pts:
        return None
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    centre = tuple((lo[i] + hi[i]) / 2 for i in range(3))
    axis = (1.0, 0.0, 0.0) if hi[0] - lo[0] <= hi[1] - lo[1] else (0.0, 1.0, 0.0)
    return (centre[0], centre[1], lo[2]), axis


def ends(points):
    zs = [p[2] for p in points]
    lo_z, hi_z = min(zs), max(zs)
    low = [p for p in points if p[2] <= lo_z + 0.05]
    high = [p for p in points if p[2] >= hi_z - 0.05]
    mean = lambda ps: tuple(sum(p[i] for p in ps) / len(ps) for i in range(3))
    return mean(low), mean(high)


def model_collision(key, src, cache):
    """{"walk": walkable_triangles, "solid": solid_triangles, "helper": helper_pairs, "reach": farthest collision
    vertex from the model's origin in xy (metres, unscaled)} of one FO4 model (NIF root space), cached by key."""
    if key not in cache:
        raw = src.mesh(key)
        empty = {"walk": [], "solid": [], "helper": []}
        try:
            f = nif.parse(raw) if raw else None
            cache[key] = ({"walk": walkable_triangles(f), "solid": solid_triangles(f), "helper": helper_pairs(f)}
                          if f else empty)
        except Exception:                                  # noqa: BLE001  (one unreadable model must not stop routes)
            cache[key] = empty
        cache[key]["reach"] = max((math.hypot(v[0], v[1]) for t in cache[key]["walk"] + cache[key]["solid"] for v in t),
                                  default=0.0)
    return cache[key]


def moves_aside(r, item):
    """True for a reference whose collision is not where the walk meets it: a door FO4 opens by default (Fort Hagen's
    UtilMetalDoor01 / 02 at the foot of two flights: batch_full 0422 / 0424 walked through their closed-leaf
    position) and a movable object the player pushes (manifest "movable")."""
    return bool((r.get("type") == "Door" and r.get("open_by_default")) or (item or {}).get("movable"))


def placed_triangles(cell, centre, radius, src, items, cache, kind, skip=None):
    """[(formkey, model, (a, b, c))] of the `kind` ("walk" / "solid") collision of every model placed within
    `radius` of `centre` (xy), the reference `skip` left out; initially disabled references have no collision, and
    the "solid" scene leaves out what moves_aside() (open doors, movable objects)."""
    out = []
    for r in cell["refs"]:
        if r is skip or not r.get("model") or r.get("type") == "Light" or r.get("disabled"):
            continue
        key = "meshes\\" + r["model"].lstrip("\\").lower()
        if key not in items or (kind == "solid" and moves_aside(r, items[key])):
            continue
        pos = tuple(x * UNIT for x in r["pos"])
        sc = r.get("scale", 1.0) or 1.0
        coll = model_collision(key, src, cache)
        # a model's collision can lie far from its origin (VltGearDoorStairs01: 16-22 m; precombined CM*.NIF)
        if math.hypot(pos[0] - centre[0], pos[1] - centre[1]) > radius + coll["reach"] * sc + 0.1:
            continue
        tris = coll[kind]
        if not tris:
            continue
        R = ref_matrix(r["rot"])
        pl = lambda v: tuple(a + b for a, b in zip(apply(R, tuple(x * sc for x in v)), pos))
        for a, b, c in tris:
            pa, pb, pc = pl(a), pl(b), pl(c)
            if min(p[0] for p in (pa, pb, pc)) > centre[0] + radius or max(p[0] for p in (pa, pb, pc)) < centre[0] - radius:
                continue
            if min(p[1] for p in (pa, pb, pc)) > centre[1] + radius or max(p[1] for p in (pa, pb, pc)) < centre[1] - radius:
                continue
            out.append((r["formkey"], r["model"], (pa, pb, pc)))
    return out


def neighbour_ground(cell, stair_ref, centre, radius, src, items, cache):
    """ground(x, y, below) over the walkable collision of the models placed within `radius` of `centre` (not the stair)."""
    tris = [t for _, _, t in placed_triangles(cell, centre, radius, src, items, cache, "walk", skip=stair_ref)]
    return lambda x, y, below: surface_z(tris, x, y, below)


def walk_scene(cell, centre, radius, src, items, cache):
    """fo4sf.walksim.Scene of everything solid around a stair (the stair itself included), owners "model/formkey"."""
    placed = placed_triangles(cell, centre, radius, src, items, cache, "solid")
    owners = [f"{os.path.basename(m.replace(chr(92), '/'))[:-4]}/{fk.split(':')[0]}" for fk, m, _ in placed]
    return walksim.Scene([t for _, _, t in placed], owners)


def lane_offsets(ramp, lo, hi, radius=walksim.PLAYER_RADIUS, step=LANE_STEP):
    """Sideways offsets (metres, + = right of the climb) of the lanes a player fits in across a ramp: 0 first, then
    alternating outwards in `step`s while the capsule stays on the ramp's width (its points projected sideways)."""
    d = (hi[0] - lo[0], hi[1] - lo[1])
    run = math.hypot(*d) or 1.0
    n = (d[1] / run, -d[0] / run)
    side = [(p[0] - lo[0]) * n[0] + (p[1] - lo[1]) * n[1] for p in ramp]
    left, right = min(side) + radius + 0.05, max(side) - radius - 0.05
    out = [0.0]
    k = 1
    while k * step <= max(-left, right) + 1e-9:
        for off in (-k * step, k * step):
            if left - 1e-9 <= off <= right + 1e-9:
                out.append(off)
        k += 1
    return out, n


def check_lane(scene, ground, lo, hi, clearance=0.0):
    """Walk one lane (lo -> hi: the ramp's ends moved sideways onto the lane) offline over `scene`. Returns (route
    fields, None) when a player teleported START_BACK before the emerged foot stands free there and climbs at least
    0.8 of the flight, else (None, why). The foot moves to where the ramp comes out of the neighbours' floors
    (ground: neighbour_ground). A walk that climbs but then runs off the top into a drop is retried stopping 0.2 m
    past the top (BldDecoSmStairsShort01 0F032D, batch_full 0022). A ramp "almost all buried" (emerging past 0.8 of
    its length) is more likely an overlapping piece (Prydwen platform stairs passed in game from their plain foot):
    the plain foot is tried first, then the emerged one (Parsons' retaining-wall stairs, whose plain foot is in the
    ground)."""
    t, g = emerge(lo, hi, ground)
    feet = [(t, g)] if t < 0.8 else [(0.0, None), (t, g)]
    first_why = None
    for t, g in feet:
        fields, why = _check_foot(scene, ground, lo, hi, t, g, clearance)
        if fields:
            return dict(fields, emerges=round(feet[-1][0], 2)), None
        first_why = first_why or why
    return None, first_why


def _check_foot(scene, ground, lo, hi, t, g, clearance):
    """check_lane() for one foot: the ramp from `t` along it (ground z `g` there) to its top. The start stands
    START_BACK before the foot, or closer (START_BACKS) when something there overlaps the player or it has no floor
    (Cambridge's HitFloorEdge02Stairs01 16D87C: a rail end 0.8 m before the foot; the game pushed the player 0.28 m
    forward, batch_full 0143)."""
    heading = round(math.degrees(math.atan2(hi[0] - lo[0], hi[1] - lo[1])) % 360, 1)
    if t > 0:
        lo = tuple(lo[i] + t * (hi[i] - lo[i]) for i in range(2)) + (max(lo[2] + t * (hi[2] - lo[2]), g or -1e9),)
    d = (hi[0] - lo[0], hi[1] - lo[1])
    run = math.hypot(*d) or 1.0
    rise = hi[2] - lo[2]
    if rise < MIN_RISE:
        return None, f"rises {rise:.2f} m above its surroundings"
    first_why = None
    for back in START_BACKS:
        sx, sy = lo[0] - back * d[0] / run, lo[1] - back * d[1] / run
        sz = ground(sx, sy, lo[2] + 1.0)
        start = (sx, sy, (sz if sz is not None and t > 0 else lo[2]) + 0.3)
        fields, why, retry = _walk_lane(scene, start, heading, back, run, lo, hi, rise, clearance)
        if fields:
            return dict(fields, buried_fraction=round(t, 2)), None
        first_why = first_why or why
        if not retry:
            break
    return None, first_why


def _walk_lane(scene, start, heading, back, run, lo, hi, rise, clearance):
    """(route fields, None, False) when the walk from `start` climbs at least 0.8 of the flight and walking
    EDGE_MARGIN further would neither fall nor stand over the edge of a drop, else (None, why, whether a start closer
    to the foot may help). The walk ends OVERSHOOT past the top, or 0.2 m / right at the top when that is too close
    to a drop (BldDecoSmStairsShort01 0F032D, batch_full 0022: the old 2 m overshoot walked into the collapsed floor;
    BldDecoSmStairs03 0EBECE's top is 0.9 m of void short of the next floor)."""
    why = None
    drop = lambda w: w["void"] or w["min_z"] < lo[2] - 0.5 or w["end"][2] < lo[2] - 0.5
    for over in (OVERSHOOT, 0.2, 0.0):
        dist = max(back + run + over, MIN_WALK)
        w = walksim.walk(scene, start, heading, dist, nudge=0.0, clearance=clearance)
        if not w["ok_start"]:
            return None, ("no floor at the start" if w["void"] else "start blocked by " + ", ".join(w["start_by"][:2])), True
        if w["start_drop"] > 0.8:
            return None, f"start {w['start_drop']:.2f} m above the floor under it", True
        if w["lift"] > walksim.STEP_UP:
            return None, f"lifted {w['lift']:.2f} m through a floor", False
        if drop(w):
            why = "falls off the walk"
            if w["max_z"] - lo[2] >= 0.8 * rise:
                continue            # it got up, then fell: try the shorter walk
            return None, why, False
        if w["end"][2] - lo[2] < 0.8 * rise:
            why = f"stopped by {w['stopped_by']}" if w["stopped_by"] else f"ends {w['end'][2] - lo[2]:.2f} m up"
            return None, why, False
        # the drop check walks EDGE_MARGIN further with the bare capsule: a wider one may stop short of an edge
        # that the player then walks off
        m = walksim.walk(scene, start, heading, dist + EDGE_MARGIN, nudge=0.0, clearance=0.0)
        if drop(m) or m["overhang_at"] is not None:
            why = "the walk ends at a drop"
            continue
        return {"start": [round(x, 2) for x in start], "heading": heading,
                "walk_ms": int(1000 * dist / RUN_SPEED),
                "expect": {"low": [round(x, 2) for x in lo], "high": [round(x, 2) for x in hi],
                           "min_rise": round(0.8 * rise, 2)},
                "sim_end": [round(x, 2) for x in w["end"]]}, None, False
    return None, why, False


def plan_stairs(cell, stair_ref, placed_ramp, src, items, cache, helper=None):
    """(route fields + "lane" (+ "tight"), None) for the first lane across a placed stair ramp that check_lane()
    accepts, the centre first, with the planner's clearance and then without it, else (None, why the centre lane
    failed). A lane whose capsule would touch a movable object (movables_near closer than MOVABLE_TOUCH; the walk
    leaves them out) is taken only when no other lane with the same clearance avoids one, and lists them in
    "movable_near" (also those within PLAYER_RADIUS + MOVABLE_MARGIN). With the stair's placed `helper` (helper_pairs),
    a lane whose walk meets a converted helper crossing gets "helper_crossing" and "_probes": the run-up and the
    past-crossing probes' route fields, or {"probe": name, "skipped": why}."""
    lo, hi = ends(placed_ramp)
    run = math.hypot(hi[0] - lo[0], hi[1] - lo[1]) or 1.0
    centre = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2)
    ground = neighbour_ground(cell, stair_ref, centre, run / 2 + 4.0, src, items, cache)
    scene = walk_scene(cell, centre, run / 2 + 4.0, src, items, cache)
    offsets, n = lane_offsets(placed_ramp, lo, hi)
    whys = {}

    def finish(found):
        if helper:
            found = annotate_stairs(found, helper, ground)
            if "helper_crossing" in found:
                found["_probes"] = []
                for name, make in (("runup", lambda: runup_probe(scene, ground, found, found["helper_crossing"])),
                                   ("past_crossing",
                                    lambda: past_crossing_probe(scene, helper, found, found["helper_crossing"]))):
                    probe, pwhy = make()
                    found["_probes"].append(probe or {"probe": name, "skipped": pwhy})
        return found, None

    for clearance in CLEARANCES:
        touching = None
        for off in offsets:
            shift = lambda p: (p[0] + off * n[0], p[1] + off * n[1], p[2])
            fields, why = check_lane(scene, ground, shift(lo), shift(hi), clearance)
            if fields:
                found = dict(fields, lane=off, **({"tight": True} if clearance < max(CLEARANCES) else {}))
                near = movables_near(cell, found["start"], found["sim_end"], src, items, cache)
                if near:
                    found["movable_near"] = near
                if not any(d < MOVABLE_TOUCH for d in near.values()):
                    return finish(found)
                touching = touching or found
                why = "touches a movable object"
            if clearance == min(CLEARANCES):
                whys.setdefault(why, []).append(off)
        if touching:
            return finish(touching)
    # why the centre lane failed, then how many of the other lanes failed for each other reason
    centre = next(w for w, offs in whys.items() if 0.0 in offs)
    rest = sorted(((len([o for o in offs if o]), w) for w, offs in whys.items() if any(offs)), reverse=True)
    return None, centre + "".join(f"; {k} other lane{'s' * (k > 1)}: {w}" for k, w in rest[:2] if k)


def _faces_up(t, min_nz=0.3):
    u = [t[1][i] - t[0][i] for i in range(3)]
    v = [t[2][i] - t[0][i] for i in range(3)]
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    ln = math.sqrt(sum(x * x for x in n))
    return ln > 1e-12 and n[2] / ln >= min_nz


def _first_rise_through(tris, start, u, dist, floor_z):
    """Distance along the walk (start + s * u, 0 <= s <= dist) at which the top face of `tris` first comes up through
    the level floor_z from below it, or None (it never does, or it first appears at or above that level: a toe or a
    step standing on the floor, which the walk meets as such)."""
    prev = None
    for i in range(int(dist / CROSSING_STEP) + 1):
        s = i * CROSSING_STEP
        z = surface_z(tris, start[0] + s * u[0], start[1] + s * u[1], 1e9)
        if z is not None and z >= floor_z:
            if prev is None:
                return None
            return prev[0] + (floor_z - prev[1]) / (z - prev[1]) * (s - prev[0]) if z > prev[1] else s
        prev = (s, z) if z is not None else None
    return None


def helper_crossing(helper, start, heading, dist, floor_z):
    """Where the stair's own converted helper comes up through the floor the walk starts on (level floor_z), on the walk
    line from `start` along `heading` for `dist` metres, when the converter's flattening moved that crossing away from
    FO4's: {"at": [x, y, z] (converted helper), "fo4_at": [x, y, z] or None (FO4's helper on the same line), "moved":
    metres along the walk from the converted crossing to FO4's (+: the walk meets the converted one first), "depth":
    how far the helper reaches below that floor (its toe), "slope": the converted top face's slope in degrees}, else
    None. `helper` is [(FO4 triangle, converted triangle)] placed (helper_pairs).
    Why it is recorded: BostonPublicLibrary02's BldDecoSmStairs03 / StairsBlock03 helpers pierce the gallery slab 1.6 m
    above their toes; the flattened helper comes out of it at x 24.34 (0EBECE, 0EBED6), FO4's at 23.89. batch_full 0002
    and 0003 stopped with the player 0.01-0.05 m before the converted crossing, the mirrored 0004 passed its crossing;
    why is unresolved (docs/testing/stairs-routes.md, section 1a). The offline walk climbs such a crossing, so a route
    through one is a test of that hypothesis rather than a route the walk vouches for."""
    if not helper:
        return None
    u = (math.sin(math.radians(heading)), math.cos(math.radians(heading)))
    fo4 = [a for a, _ in helper if _faces_up(a)]
    conv = [b for _, b in helper if _faces_up(b)]
    sc = _first_rise_through(conv, start, u, dist, floor_z)
    if sc is None:
        return None
    sf = _first_rise_through(fo4, start, u, dist, floor_z)
    if sf is not None and abs(sf - sc) < CROSSING_MOVED:
        return None
    at = lambda s: [round(start[0] + s * u[0], 2), round(start[1] + s * u[1], 2), round(floor_z, 2)]
    x, y = start[0] + sc * u[0], start[1] + sc * u[1]
    slope = None
    for t in conv:                                   # the top face under the crossing (a little past it)
        if surface_z([t], x + 0.05 * u[0], y + 0.05 * u[1], 1e9) is not None:
            n = (t[1][1] - t[0][1]) * (t[2][2] - t[0][2]) - (t[1][2] - t[0][2]) * (t[2][1] - t[0][1]), \
                (t[1][2] - t[0][2]) * (t[2][0] - t[0][0]) - (t[1][0] - t[0][0]) * (t[2][2] - t[0][2]), \
                (t[1][0] - t[0][0]) * (t[2][1] - t[0][1]) - (t[1][1] - t[0][1]) * (t[2][0] - t[0][0])
            slope = round(math.degrees(math.acos(n[2] / math.sqrt(sum(c * c for c in n)))), 1)
            break
    return {"at": at(sc), "fo4_at": at(sf) if sf is not None else None,
            "moved": round(sf - sc, 2) if sf is not None else None,
            "depth": round(floor_z - min(v[2] for t in conv for v in t), 2), "slope": slope}


def past_crossing_probe(scene, helper, found, crossing):
    """(route fields, None) for a probe that starts on the converted helper PROBE_PAST beyond a helper_crossing() of a
    planned route `found` and climbs the rest of the flight, else (None, why). Paired with the route through the
    crossing, it tells whether a stop at the crossing comes from the crossing itself (the probe passes) or from the
    helper (both stop)."""
    heading = found["heading"]
    u = (math.sin(math.radians(heading)), math.cos(math.radians(heading)))
    start = found["start"]
    s = math.hypot(crossing["at"][0] - start[0], crossing["at"][1] - start[1]) + PROBE_PAST
    x, y = start[0] + s * u[0], start[1] + s * u[1]
    hz = surface_z([b for _, b in helper if _faces_up(b)], x, y, 1e9)
    if hz is None:
        return None, "no helper past the crossing"
    hi = tuple(found["expect"]["high"])
    lo = (x, y, hz)
    rise = hi[2] - hz
    if rise < MIN_RISE:
        return None, f"rises {rise:.2f} m past the crossing"
    run = math.hypot(hi[0] - x, hi[1] - y)
    fields, why, _ = _walk_lane(scene, (x, y, hz + 0.3), heading, 0.0, run, lo, hi, rise, 0.0)
    return (dict(fields, probe="past_crossing"), None) if fields else (None, why)


def runup_probe(scene, ground, found, crossing):
    """(route fields, None) for a probe that starts on the floor PROBE_RUNUP before a helper_crossing() of a planned
    route `found` (the run-up batch_full 0002 / 0003 had on the gallery slab before they stopped at the crossing) and
    walks the route's lane with its expectations, else (None, why): the route itself already starts that far back, or
    the spot is taken or has no floor."""
    heading = found["heading"]
    u = (math.sin(math.radians(heading)), math.cos(math.radians(heading)))
    start, at = found["start"], crossing["at"]
    if math.hypot(at[0] - start[0], at[1] - start[1]) >= PROBE_RUNUP - 0.05:
        return None, "the route starts that far back"
    x, y = at[0] - PROBE_RUNUP * u[0], at[1] - PROBE_RUNUP * u[1]
    g = ground(x, y, at[2] + walksim.STEP_UP)
    if g is None:
        return None, "no floor for the run-up"
    lo, hi = tuple(found["expect"]["low"]), tuple(found["expect"]["high"])
    back, run = math.hypot(lo[0] - x, lo[1] - y), math.hypot(hi[0] - lo[0], hi[1] - lo[1])
    fields, why, _ = _walk_lane(scene, (x, y, g + 0.3), heading, back, run, lo, hi, hi[2] - lo[2], 0.0)
    return (dict(fields, probe="runup"), None) if fields else (None, why)


def _all_collision_points(key, src, cache):
    """Every collision vertex of a FO4 model on any layer (NIF root space; movable clutter is on layers the walk scene
    leaves out), or [] when it has none; cached under ("all", key)."""
    if ("all", key) not in cache:
        pts = []
        try:
            raw = src.mesh(key)
            if raw:
                for _, p, _ in collision_bodies(nif.parse(raw), compounds=True):
                    pts += list(p)
        except Exception:                                  # noqa: BLE001  (an unreadable model is listed by origin)
            pts = []
        cache[("all", key)] = pts
    return cache[("all", key)]


def movables_near(cell, a, b, src, items, cache, reach=walksim.PLAYER_RADIUS + MOVABLE_MARGIN):
    """{"model/formkey": metres} of the movable objects (manifest "movable") whose collision (any layer; the origin
    when it has none) comes within `reach` (xy) of the walk from a to b (x, y, z), from 0.6 m under the lower end to
    a player's height over the upper end. The walk scene leaves movable objects out: that the player pushes them aside
    is a supported hypothesis (docs/ai/research-log.md, 2026-10-10), so a lane that meets one is listed, not vouched
    for."""
    zlo, zhi = min(a[2], b[2]) - 0.6, max(a[2], b[2]) + walksim.PLAYER_HEIGHT
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    half = math.hypot(b[0] - a[0], b[1] - a[1]) / 2 + reach
    out = {}
    for r in cell["refs"]:
        key = "meshes\\" + (r.get("model") or "").lstrip("\\").lower()
        if not (items.get(key) or {}).get("movable") or r.get("disabled"):
            continue
        pos = tuple(x * UNIT for x in r["pos"])
        if math.hypot(pos[0] - mid[0], pos[1] - mid[1]) > half + 3.0:      # clutter is small
            continue
        sc = r.get("scale", 1.0) or 1.0
        R = ref_matrix(r["rot"])
        pts = _all_collision_points(key, src, cache) or [(0.0, 0.0, 0.0)]
        best = None
        for v in pts:
            p = tuple(q + o for q, o in zip(apply(R, tuple(c * sc for c in v)), pos))
            if zlo <= p[2] <= zhi:
                d = _seg_dist_xy(a, b, p)
                best = d if best is None else min(best, d)
        if best is not None and best < reach:
            name = f"{os.path.basename(r['model'].replace(chr(92), '/'))[:-4]}/{r['formkey'].split(':')[0]}"
            out[name] = round(best, 2)
    return out


def _seg_dist_xy(a, b, p):
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = dx * dx + dy * dy
    t = 0.0 if n == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n))
    return math.hypot(a[0] + t * dx - p[0], a[1] + t * dy - p[1])


def annotate_stairs(found, helper, ground):
    """found + "helper_crossing" (when the walk meets one, helper_crossing()); the floor is the neighbours' floor under
    the start (else the start's own height less the 0.3 m teleport lift)."""
    start, end = found["start"], found["sim_end"]
    g = ground(start[0], start[1], start[2]) if ground else None
    floor_z = g if g is not None else start[2] - 0.3
    dist = math.hypot(end[0] - start[0], end[1] - start[1])
    c = helper_crossing(helper, start, found["heading"], dist, floor_z)
    return dict(found, helper_crossing=c) if c else found


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fo4-data", required=True)
    ap.add_argument("--cell-json", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max", type=int, default=40)
    ap.add_argument("--formids", default="", help="plugin formids.json: door routes get the door's Starfield ref id "
                    "(local FormID) so the runner can close it before each crossing")
    ap.add_argument("--probes-out", default="", help="also write probe routes for every stairs route that meets a "
                    "converted helper crossing: the route itself (probe through_crossing), one with a 1.3 m run-up on "
                    "the floor before the crossing (runup) and one starting past it (past_crossing); plan them with "
                    "testqueue.py plan --routes-prefix <its prefix>")
    a = ap.parse_args(argv)
    formids = json.load(open(a.formids, encoding="utf-8-sig")) if a.formids else {}
    src = pipeline.Fo4Archives(a.fo4_data)
    cell = json.load(open(a.cell_json, encoding="utf-8-sig"))
    man = json.load(open(a.manifest))
    items = {it["source"].lower(): it for it in man["items"]}
    routes, cache, skipped, tri_cache, tread_cache, checked = [], {}, {}, {}, {}, []
    probes, probes_skipped = [], []
    twins = door_twins(cell["refs"], items)
    for r in cell["refs"]:
        model = r.get("model") or ""
        key = "meshes\\" + model.lstrip("\\").lower()
        it = items.get(key)
        if not it:
            continue
        pos = tuple(x * UNIT for x in r["pos"])
        R = ref_matrix(r["rot"])
        sc = r.get("scale", 1.0) or 1.0
        place = lambda v: tuple(a_ + b_ for a_, b_ in zip(apply(R, tuple(x * sc for x in v)), pos))
        if it.get("door"):
            # facing from the door's own geometry: the thinnest horizontal axis of its local bounds is the door normal;
            # the route crosses the middle of the opening, once from each side (a leaf may swing towards the player)
            if key not in cache:
                raw = src.mesh(key)
                cache[key] = door_frame(nif.parse(raw)) if raw else None
            frame = cache[key]
            if frame is None:
                continue
            centre_l, axis_l = frame
            centre = place(centre_l)
            n = tuple(x - y for x, y in zip(place(axis_l), pos))
            local = formids.get(f"REFR:FO4Port_{cell['cell']}:{r['formkey']}")
            twin = twins.get(r["formkey"])
            twin_local = formids.get(f"REFR:FO4Port_{cell['cell']}:{twin}") if twin else None
            for side in (1, -1):
                ns = tuple(side * x for x in n)
                start = tuple(centre[i] - 1.6 * ns[i] for i in range(3))
                routes.append({"cell": cell["cell"], "kind": "door", "ref": r["formkey"], "model": model, "side": side,
                               **({"sf_ref_local": f"{local:06X}"} if local is not None else {}),
                               **({"twin": twin} if twin else {}),
                               **({"sf_ref_local_twin": f"{twin_local:06X}"} if twin_local is not None else {}),
                               "start": [round(start[0], 2), round(start[1], 2), round(pos[2] + 0.3, 2)],
                               "heading": round(math.degrees(math.atan2(ns[0], ns[1])) % 360, 1), "use": True,
                               "walk_ms": 1100,
                               "expect": {"plane_point": [round(x, 3) for x in centre],
                                          "plane_normal": [round(x, 4) for x in ns], "min_past": 0.8}})
            continue
        if "stair" not in model.lower():
            continue
        if key not in cache:
            raw = src.mesh(key)
            cache[key] = ramp_points(nif.parse(raw)) if raw else ([], None)
        pts, how = cache[key]
        if not pts:
            label = model if how is None else f"{model} ({how})"
            skipped[label] = skipped.get(label, 0) + 1
            continue
        if how == "sloped-collision":                     # no helper: only a real flight of treads counts as stairs
            if key not in tread_cache:
                tread_cache[key] = tread_levels(nif.parse(src.mesh(key)))
            if len(tread_cache[key]) < 3:
                skipped[model + " (no helper, no treads: railing or trim)"] = \
                    skipped.get(model + " (no helper, no treads: railing or trim)", 0) + 1
                continue
        placed_ramp = [place(p) for p in pts]
        helper = [(tuple(place(v) for v in fa), tuple(place(v) for v in fb))
                  for fa, fb in model_collision(key, src, tri_cache)["helper"]]
        found, why = plan_stairs(cell, r, placed_ramp, src, items, tri_cache, helper)
        checked.append({"ref": r["formkey"], "model": model, **({"lane": found["lane"]} if found else {"skipped": why}),
                        **({"helper_crossing": found["helper_crossing"]} if found and "helper_crossing" in found else {})})
        if found is None:
            label = f"{model} (no clear lane: {why})"
            skipped[label] = skipped.get(label, 0) + 1
            continue
        if found["emerges"] >= 0.8 and found["buried_fraction"] == 0.0:   # "almost all buried", plain foot kept
            skipped[model + " (looks buried, route kept)"] = skipped.get(model + " (looks buried, route kept)", 0) + 1
        near = found.get("movable_near")
        # the player runs ~4.6 m/s: the walk ends OVERSHOOT past the high end (mirrored flights share landings, a
        # longer walk goes up one and down the other); sim_end is where the offline walk (walksim) ended
        route = {"cell": cell["cell"], "kind": "stairs", "ref": r["formkey"], "model": model, "ramp": how,
                 "buried_fraction": found["buried_fraction"], "emerges": found["emerges"], "lane": found["lane"],
                 "start": found["start"], "heading": found["heading"], "use": False, "walk_ms": found["walk_ms"],
                 "expect": found["expect"], "sim_end": found["sim_end"],
                 **({"tight": True} if found.get("tight") else {}),
                 **({"helper_crossing": found["helper_crossing"]} if "helper_crossing" in found else {}),
                 **({"movable_near": near} if near else {})}
        routes.append(route)
        if "helper_crossing" in found:
            probes.append(dict(route, probe="through_crossing"))
            for pr in found["_probes"]:
                if "skipped" in pr:
                    probes_skipped.append({"ref": r["formkey"], "model": model, **pr})
                else:
                    probes.append({**{k: route[k] for k in ("cell", "kind", "ref", "model", "ramp", "lane", "use")},
                                   **pr, "helper_crossing": found["helper_crossing"]})
    routes = routes[:a.max]
    with open(a.out, "w") as f:
        json.dump({"routes": routes, "skipped_stairs_without_ramp": skipped, "stairs_checked": checked}, f, indent=1)
    if a.probes_out:
        with open(a.probes_out, "w") as f:
            json.dump({"routes": probes, "probes_skipped": probes_skipped}, f, indent=1)
    print(f"{len(routes)} routes ({sum(r['kind'] == 'stairs' for r in routes)} stairs, "
          f"{sum(r['kind'] == 'door' for r in routes)} doors); stairs skipped: {skipped}"
          + (f"; {len(probes)} probe routes" if a.probes_out else ""))


if __name__ == "__main__":
    main()
