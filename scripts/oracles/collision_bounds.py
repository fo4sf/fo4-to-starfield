"""Compare a converted Starfield NIF's drawn-geometry AABB with its collision AABB.

Offline only: this does not prove the in-game activate prompt. Exit 1 when a model is flagged
(missing, unreadable, no_mesh, much-smaller, or offset collision), including partial body
decode, a collision object / physics system whose size disagrees with its layout, a body id other
than 0, a physics system shared by two collision objects or not holding exactly one body, a
collision target that is not a node or BSGeometry, a scene graph that is not a plain tree under
the footer root (a node child table that does not fit its block or names a block past the end, a
block with two parents, a cycle, more than 64 levels, a parent nif.world_transforms would read
differently, geometry or a collision object outside the tree, a collision object whose target is
not the block that names it), a transform composed for a box that is not a plain NiNode /
BSFadeNode / unskinned BSGeometry one with no controller, scale > 0 and a rotation, and
malformed manifest entries.
Nonfinite or non-positive --scale / per-item scale is rejected before comparison, and a nonfinite
point anywhere, a body orientation that is not a unit quaternion, or bounds whose centre / extent /
diagonal overflow, make the model unreadable. JSON output never emits NaN/Infinity, and a structurally
malformed NIF or manifest is an unreadable report, not a traceback.

usage: python scripts/oracles/collision_bounds.py <model.nif> [--scale 0.75]
       python scripts/oracles/collision_bounds.py --manifest staging/manifest.json --staging <staging>
"""
import argparse
import json
import math
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from fo4sf import fo4collision, nif, sfcollision, sfbodies, sfnif  # noqa: E402

# Collision extent / mesh extent below this on any mesh axis of at least MIN_EXTENT is "much smaller".
SMALLER_RATIO = 0.25
# Ignore tiny axes (metres) so a zero-thickness hatch plane does not false-flag.
MIN_EXTENT = 0.05
# Centre distance / mesh diagonal above this is "offset".
OFFSET_RATIO = 0.5


def _corners(center, half):
    return [(center[0] + sx * half[0], center[1] + sy * half[1], center[2] + sz * half[2])
            for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]


def _place(v, t, rot, scale):
    return tuple(t[a] + scale * (rot[3 * a] * v[0] + rot[3 * a + 1] * v[1] + rot[3 * a + 2] * v[2])
                 for a in range(3))


def _aabb(points):
    if not all(math.isfinite(x) for p in points for x in p):
        return [math.nan] * 3, [math.nan] * 3          # min / max would skip a NaN that is not first
    lo = [min(p[a] for p in points) for a in range(3)]
    hi = [max(p[a] for p in points) for a in range(3)]
    return lo, hi


def _scale_aabb(lo, hi, scale):
    pts = [(lo[0], lo[1], lo[2]), (hi[0], hi[1], hi[2])]
    pts = [(p[0] * scale, p[1] * scale, p[2] * scale) for p in pts]
    return _aabb(pts)


def _finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def parse_scale(value):
    if isinstance(value, bool):
        raise ValueError(f"scale is not a finite number: {value!r}")
    try:
        scale = float(value)
    except (TypeError, ValueError, OverflowError) as err:
        raise ValueError(f"scale is not a finite number: {value!r}") from err
    if not math.isfinite(scale):
        raise ValueError(f"scale is not finite: {value!r}")
    if scale <= 0:                                     # REFR scale is positive; 0 hides both boxes below MIN_EXTENT
        raise ValueError(f"scale is not positive: {value!r}")
    return scale


def _finite_xyz(v):
    return isinstance(v, (list, tuple)) and len(v) == 3 and all(_finite_number(x) for x in v)


def _finite_aabb(lo, hi):
    """Corners, centre, extent and diagonal all finite, so aabb_info and flag_bounds cannot overflow."""
    if not (_finite_xyz(lo) and _finite_xyz(hi)):
        return False
    ext = [hi[a] - lo[a] for a in range(3)]
    return (_finite_xyz(ext) and _finite_xyz([(lo[a] + hi[a]) / 2 for a in range(3)])
            and math.isfinite(math.hypot(*ext)))


def _round_xyz(v, n=4):
    if not _finite_xyz(v):
        raise ValueError("nonfinite bound")
    return [round(x, n) for x in v]


def aabb_info(lo, hi):
    return {"min": _round_xyz(lo), "max": _round_xyz(hi),
            "center": _round_xyz([(lo[a] + hi[a]) / 2 for a in range(3)]),
            "extent": _round_xyz([hi[a] - lo[a] for a in range(3)])}


def _is_node(t):
    """NiNode-derived: a "...Node" type, as nif.world_transforms takes it; BSFurnitureMarkerNode is NiExtraData."""
    return t.endswith("Node") and t != "BSFurnitureMarkerNode"


_PLAIN_NODES = ("NiNode", "BSFadeNode")                # draw every child at its stored transform
_MAX_DEPTH = 64                                        # world_transforms stops composing parents at depth > 64


def _av_fields(blk):
    """(controller, rotation, scale, collision ref) of a node or BSGeometry block (nif._av_transform's layout)."""
    _, nextra = struct.unpack_from("<iI", blk, 0)
    controller, = struct.unpack_from("<i", blk, 8 + 4 * nextra)
    *rot, scale, coll = struct.unpack_from("<9ffi", blk, 8 + 4 * nextra + 20)    # past controller, flags, translation
    return controller, rot, scale, coll


def _is_rotation(r, tol=1e-3):
    """Orthonormal with determinant +1. A singular matrix shrinks both boxes below MIN_EXTENT, and Havok turns a body
    but cannot shear or mirror it the way the oracle's matrix product does."""
    det = r[0] * (r[4] * r[8] - r[5] * r[7]) - r[1] * (r[3] * r[8] - r[5] * r[6]) + r[2] * (r[3] * r[7] - r[4] * r[6])
    return det > 0 and all(abs(sum(r[3 * a + k] * r[3 * b + k] for k in range(3)) - (a == b)) <= tol
                           for a in range(3) for b in range(3))


def _scene_errors(f):
    """The scene graph behind the transforms the oracle composes. nif.world_transforms reads any "...Node" child table
    leniently (a table past the block or over 100000 is childless, refs past the end are dropped), takes a block's
    first parent, gives an unlisted block none and stops composing parents 65 levels up, so its result is right only
    for a plain tree under the footer root. Geometry or a collision object outside that tree is never loaded, a collision object
    belongs to the block whose collision ref names it, and every transform composed for a box must be a plain
    NiNode / BSFadeNode or BSGeometry transform: no controller, no skin, scale > 0 and a rotation."""
    errors, n = [], len(f.blocks)
    children = {}
    for i, blk in enumerate(f.blocks):
        if not _is_node(f.type_of(i)):
            continue
        try:
            _, nextra = struct.unpack_from("<iI", blk, 0)
            p = 8 + 4 * nextra + 8 + 52 + 4                # extra refs, controller, flags, transform, collision ref
            count, = struct.unpack_from("<I", blk, p)
        except struct.error:
            errors.append(f"node {i}: truncated before its child table ({len(blk)} bytes)")
            continue
        if count > 100000 or p + 4 + 4 * count > len(blk):
            errors.append(f"node {i}: declares {count} children in a {len(blk)}-byte block")
            continue
        refs = struct.unpack_from(f"<{count}i", blk, p + 4)
        bad = [c for c in refs if not -1 <= c < n]
        if bad:
            errors.append(f"node {i}: child refs {bad} past {n} blocks")
        children[i] = [c for c in refs if 0 <= c < n]
    parents = {}
    for i, kids in children.items():
        for c in kids:
            parents.setdefault(c, []).append(i)
    errors.extend(f"block {c}: listed as a child by nodes {ps}" for c, ps in parents.items() if len(ps) > 1)
    try:
        count, = struct.unpack_from("<I", f.footer, 0)
        roots = struct.unpack_from(f"<{count}i", f.footer, 4) if len(f.footer) == 4 + 4 * count else ()
    except struct.error:
        roots = ()
    root = roots[0] if roots else -1
    if not (0 <= root < n and (_is_node(f.type_of(root)) or f.type_of(root) == "BSGeometry")):
        return errors + [f"footer ({len(f.footer)} bytes) does not name a scene root"]
    if root in parents:
        errors.append(f"root {root}: listed as a child by nodes {parents[root]}")
    depth, up, todo = {root: 0}, {root: None}, [root]  # up: the parent each block in the tree is reached from
    while todo:
        i = todo.pop()
        for c in children.get(i, ()):
            if c not in depth:                         # a second parent or a cycle is reported above
                depth[c], up[c] = depth[i] + 1, i
                todo.append(c)
    if max(depth.values()) > _MAX_DEPTH:
        errors.append(f"scene graph deeper than {_MAX_DEPTH} levels below root {root}")
    nif_parent = _geometry_parents(f)                  # marker bytes can claim children; BSFaceGenNiNode's lose theirs
    errors.extend(f"block {b}: world transform follows parent {nif_parent.get(b)}, scene parent {up[b]}"
                  for b in sorted(depth) if nif_parent.get(b) != up[b])
    owners, leaves = {}, []
    for b in sorted(depth):
        t = f.type_of(b)
        if not (_is_node(t) or t == "BSGeometry"):
            continue
        try:
            coll = _av_fields(f.blocks[b])[3]
            skin = sfnif.parse_bsgeometry(f.blocks[b]).skin if t == "BSGeometry" else -1
        except (struct.error, ValueError, IndexError):
            continue                                   # a truncated node / BSGeometry is reported on its own
        if t == "BSGeometry":
            leaves.append(b)
        if skin != -1:
            errors.append(f"BSGeometry {b}: skin {skin} places it by bones, not by its node")
        if coll != -1 and not (0 <= coll < n and f.type_of(coll) == "bhkNPCollisionObject"):
            errors.append(f"block {b}: collision ref {coll} is not a bhkNPCollisionObject")
        elif coll != -1:
            owners.setdefault(coll, []).append(b)
    for i in range(n):
        if f.type_of(i) == "BSGeometry" and i not in depth:
            errors.append(f"BSGeometry {i}: not in the scene graph below root {root}")
        if f.type_of(i) != "bhkNPCollisionObject":
            continue
        refs = owners.get(i, [])
        if len(refs) != 1:
            errors.append(f"collision object {i}: named by the collision refs of blocks {refs} below root {root}, "
                          "not by one")
            continue
        leaves.append(refs[0])
        target = struct.unpack_from("<i", f.blocks[i], 0)[0] if len(f.blocks[i]) >= 4 else refs[0]
        if target != refs[0]:
            errors.append(f"collision object {i}: target {target} is not block {refs[0]}, which references it")
    seen = set()
    for b in leaves:                                   # every transform composed for a box, up to the root
        while b is not None and b not in seen:
            seen.add(b)
            t = f.type_of(b)
            if _is_node(t) and t not in _PLAIN_NODES:
                errors.append(f"block {b}: {t} is not a plain NiNode / BSFadeNode")
            try:
                controller, rot, scale, _ = _av_fields(f.blocks[b])
            except struct.error:
                controller, rot, scale = -1, (1, 0, 0, 0, 1, 0, 0, 0, 1), 1.0     # reported on its own
            if controller != -1:
                errors.append(f"block {b}: controller {controller} can move its transform")
            if not scale > 0:
                errors.append(f"block {b}: scale {scale} is not positive")
            if not _is_rotation(rot):
                errors.append(f"block {b}: matrix is not a rotation")
            b = up[b]
    return errors


def _geometry_parents(f):
    parent = {}
    for i in range(len(f.blocks)):
        if not f.type_of(i).endswith("Node") or f.type_of(i) == "BSFaceGenNiNode":
            continue
        try:
            for c in nif.node_children(f, i):
                parent.setdefault(c, i)
        except (struct.error, ValueError, IndexError):
            pass
    return parent


def mesh_aabb(f, scale=1.0):
    """Union of BSGeometry.box AABBs in NIF root metres, then optional REFR scale about the origin."""
    world = nif.world_transforms(f)
    parent = _geometry_parents(f)
    ident_t, ident_r, ident_s = (0.0, 0.0, 0.0), (1, 0, 0, 0, 1, 0, 0, 0, 1), 1.0
    points = []
    for i, block in enumerate(f.blocks):
        if f.type_of(i) != "BSGeometry":
            continue
        g = sfnif.parse_bsgeometry(block)
        if all(abs(x) < 1e-12 for x in g.box):
            continue
        center, half = g.box[:3], g.box[3:]
        local = [_place(p, g.translation, g.rotation, g.scale) for p in _corners(center, half)]
        if i in parent:
            t, rot, s = world(parent[i])
        else:
            t, rot, s = ident_t, ident_r, ident_s
        points.extend(_place(p, t, rot, s) for p in local)
    if not points:
        return None
    lo, hi = _aabb(points)
    if scale != 1.0:
        lo, hi = _scale_aabb(lo, hi, scale)
    if not _finite_aabb(lo, hi):
        raise ValueError("nonfinite mesh bounds")
    return lo, hi


def _box_blob_aabb(blob):
    """GO path: 6,168-byte identity hknpBoxShape (sfcollision.read_box, corners at offset 592)."""
    sfcollision.check_template(blob)
    center, half = sfcollision.read_box(blob)
    return _aabb(_corners(center, half))


def collision_bodies(f, scale=1.0):
    """Per-body AABBs in NIF root metres.

    Box templates use sfcollision.read_box. Other fo4-native tagfiles use sfbodies.blob_bodies
    (existing Starfield tagfile readback). fo4collision.decode is FO4 packfile-only and is not used.
    A bhkNPCollisionObject that is not its 14-byte layout (target i32, flags u16, data i32, body id
    u32), a body id other than 0 (it picks one body of the system; converted systems hold one), a
    bhkPhysicsSystem whose size is not its u32 length field plus the blob length it declares, or that
    another collision object already uses, a target that is not a node or BSGeometry (any other
    block's bytes can still read as a transform), or a blob that fails to decode or does not hold
    exactly one body is an error for that object only.
    """
    bodies = []
    errors = []
    systems = {}
    world = nif.world_transforms(f)
    for i in range(len(f.blocks)):
        if f.type_of(i) != "bhkNPCollisionObject":
            continue
        if len(f.blocks[i]) != 14:
            what = "truncated header" if len(f.blocks[i]) < 14 else "trailing bytes after its header"
            errors.append(f"collision object {i}: {what} ({len(f.blocks[i])} bytes)")
            continue
        target, _, data, body_id = struct.unpack_from("<iHiI", f.blocks[i], 0)
        if body_id != 0:
            errors.append(f"collision object {i}: body id {body_id}, not 0")
            continue
        if not (0 <= data < len(f.blocks)) or f.type_of(data) != "bhkPhysicsSystem":
            errors.append(f"collision object {i}: bad physics system")
            continue
        if data in systems:
            errors.append(f"collision object {i}: physics system {data} is also collision object {systems[data]}'s")
            continue
        systems[data] = i
        if len(f.blocks[data]) < 4:
            errors.append(f"collision object {i}: truncated physics system {data} "
                          f"({len(f.blocks[data])} bytes)")
            continue
        n, = struct.unpack_from("<I", f.blocks[data], 0)
        if 4 + n > len(f.blocks[data]):
            errors.append(f"collision object {i}: truncated physics system {data} "
                          f"({len(f.blocks[data]) - 4} of {n} blob bytes)")
            continue
        if 4 + n < len(f.blocks[data]):
            errors.append(f"collision object {i}: physics system {data} has "
                          f"{len(f.blocks[data]) - 4 - n} bytes after its {n}-byte blob")
            continue
        blob = f.blocks[data][4:4 + n]
        if not (0 <= target < len(f.blocks)):
            errors.append(f"collision object {i}: invalid target {target}")
            continue
        if not (_is_node(f.type_of(target)) or f.type_of(target) == "BSGeometry"):
            errors.append(f"collision object {i}: target {target} ({f.type_of(target)}) is not a scene object")
            continue
        t, rot, s = world(target)
        try:
            lo, hi = _box_blob_aabb(blob)
            kind = "hknpBoxShape"
            pts = [_place(p, t, rot, s) for p in _corners(
                [(lo[a] + hi[a]) / 2 for a in range(3)], [(hi[a] - lo[a]) / 2 for a in range(3)])]
            blo, bhi = _aabb(pts)
            if scale != 1.0:
                blo, bhi = _scale_aabb(blo, bhi, scale)
            if not _finite_aabb(blo, bhi):
                errors.append(f"collision object {i}: nonfinite box bounds")
                continue
            bodies.append({"shape": kind, **aabb_info(blo, bhi)})
            continue
        except (sfcollision.CollisionError, struct.error, ValueError):
            pass
        try:
            decoded = sfbodies.blob_bodies(blob)
        except (sfbodies.BodyError, ValueError, struct.error, IndexError, KeyError, OverflowError,
                RecursionError) as err:                # a tagfile missing a section, offsets >= 2**63, cyclic types
            errors.append(f"collision object {i}: {type(err).__name__}: {err}")
            continue
        if len(decoded) != 1:                          # body id 0 picks one; the rest would not follow this target
            errors.append(f"collision object {i}: physics system {data} holds {len(decoded)} bodies, not 1")
            continue
        for body in decoded:
            pts = [_place(p, t, rot, s) for tri in body["triangles"] for p in tri]
            if not pts:
                errors.append(f"collision object {i}: empty {body.get('shape', 'shape')}")
                continue
            if scale != 1.0:
                pts = [(p[0] * scale, p[1] * scale, p[2] * scale) for p in pts]
            blo, bhi = _aabb(pts)
            if not _finite_aabb(blo, bhi):
                errors.append(f"collision object {i}: nonfinite {body.get('shape', 'shape')} bounds")
                continue
            bodies.append({"shape": body["shape"], **aabb_info(blo, bhi)})
    return bodies, errors


def combined_aabb(bodies):
    if not bodies:
        return None
    lo = [min(b["min"][a] for b in bodies) for a in range(3)]
    hi = [max(b["max"][a] for b in bodies) for a in range(3)]
    return lo, hi


def _overlap(a_lo, a_hi, b_lo, b_hi):
    return all(a_lo[a] <= b_hi[a] and b_lo[a] <= a_hi[a] for a in range(3))


def flag_bounds(mesh, collision):
    """mesh/collision are (lo, hi) or None. Does not prove reachability, only AABB mismatch."""
    if mesh is None:
        return ["no_mesh"]
    if collision is None:
        return ["missing"]
    if not _finite_aabb(*mesh) or not _finite_aabb(*collision):
        return ["unreadable"]
    m_lo, m_hi = mesh
    c_lo, c_hi = collision
    m_ext = [m_hi[a] - m_lo[a] for a in range(3)]
    c_ext = [c_hi[a] - c_lo[a] for a in range(3)]
    flags = []
    if any(m_ext[a] >= MIN_EXTENT and c_ext[a] < SMALLER_RATIO * m_ext[a] for a in range(3)):
        flags.append("much_smaller")                   # any axis: a 10 x 10 x 1 m mesh on a 10 x 0.1 x 1 m box
    m_c = [(m_lo[a] + m_hi[a]) / 2 for a in range(3)]
    c_c = [(c_lo[a] + c_hi[a]) / 2 for a in range(3)]
    diag = math.hypot(*m_ext)
    dist = math.dist(m_c, c_c)                         # inf (offset), not OverflowError, for huge scales
    if diag >= MIN_EXTENT and (dist > OFFSET_RATIO * diag or not _overlap(m_lo, m_hi, c_lo, c_hi)):
        flags.append("offset")
    return flags


def audit(data, scale=1.0, path=""):
    try:
        scale = parse_scale(scale)
    except ValueError as err:
        return {"path": path, "scale": None, "flags": ["unreadable"], "error": str(err)}
    try:
        f = nif.parse(data)
    except (nif.NifError, struct.error, ValueError, IndexError) as err:
        return {"path": path, "scale": scale, "flags": ["unreadable"], "error": str(err)}
    errors = []
    try:
        errors.extend(_scene_errors(f))                # a malformed graph can misplace both boxes alike
        mesh = mesh_aabb(f, scale)
    except (ValueError, struct.error, IndexError, nif.NifError) as err:
        mesh = None
        errors.append(str(err))
    try:
        bodies, body_errors = collision_bodies(f, scale)
    except (ValueError, struct.error, IndexError, nif.NifError) as err:
        bodies, body_errors = [], [f"collision: {err}"]
    errors.extend(body_errors)
    coll = combined_aabb(bodies)
    coll_ok = coll is not None and _finite_aabb(*coll)
    if coll is not None and not coll_ok:
        errors.append("collision: nonfinite combined bounds")
    flags = []
    if errors:
        flags.append("unreadable")
    for flag in flag_bounds(mesh, coll):
        if flag not in flags:
            flags.append(flag)
    report = {"path": path, "scale": scale, "flags": flags,
              "mesh": aabb_info(*mesh) if mesh else None,
              "collision": {"bodies": len(bodies), "per_body": bodies,
                            **(aabb_info(*coll) if coll_ok else {"min": None, "max": None})}}
    if errors:
        report["errors"] = errors
    return report


def _model_path(staging, model):
    root = (staging / "meshes").resolve()
    path = (root / str(model).replace("\\", "/")).resolve()
    if not path.is_relative_to(root):
        raise ValueError("model path escapes staging meshes")
    return path


def audit_files(paths, scale=1.0):
    try:
        scale = parse_scale(scale)
    except ValueError as err:
        return [{"path": str(paths[0]) if paths else "", "scale": None,
                 "flags": ["unreadable"], "error": str(err)}]
    reports = []
    for path in paths:
        try:
            reports.append(audit(path.read_bytes(), scale=scale, path=str(path)))
        except OSError as err:
            reports.append({"path": str(path), "scale": scale, "flags": ["unreadable"], "error": str(err)})
    return reports


def audit_manifest(manifest, staging, scale=1.0):
    reports = []
    try:
        scale = parse_scale(scale)
    except ValueError as err:
        return [{"path": "", "scale": None, "flags": ["unreadable"], "error": str(err)}]
    items = manifest.get("items") if isinstance(manifest, dict) else None
    if not isinstance(items, list):
        return [{"path": "", "scale": scale, "flags": ["unreadable"],
                 "error": "manifest items must be a list"}]
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            reports.append({"path": f"<items[{i}]>", "scale": scale, "flags": ["unreadable"],
                            "error": f"manifest item {i} is not an object"})
            continue
        model = item.get("model")
        if not isinstance(model, str) or not model:
            reports.append({"path": str(item.get("source") or f"<items[{i}]>"), "scale": scale,
                            "flags": ["unreadable"], "error": f"manifest item {i} missing model"})
            continue
        try:
            item_scale = parse_scale(item["scale"]) if "scale" in item else scale
        except ValueError as err:
            reports.append({"path": model, "scale": None, "flags": ["unreadable"], "error": str(err)})
            continue
        try:
            path = _model_path(staging, model)
            reports.append(audit(path.read_bytes(), scale=item_scale, path=str(path)))
        except (OSError, ValueError, TypeError) as err:
            reports.append({"path": model, "scale": item_scale, "flags": ["unreadable"], "error": str(err)})
    return reports


_FAIL = {"missing", "unreadable", "much_smaller", "offset", "no_mesh"}


def failed(reports):
    return [r for r in reports if _FAIL.intersection(r.get("flags") or ())]


def research_box_vs_packfile(blob):
    """Evidence helper: sfcollision.read_box vs fo4collision.decode on the same blob."""
    out = {"sfcollision": None, "fo4collision": None}
    try:
        out["sfcollision"] = list(sfcollision.read_box(blob))
    except Exception as err:  # noqa: BLE001  (research: record the failure)
        out["sfcollision"] = f"{type(err).__name__}: {err}"
    try:
        out["fo4collision"] = fo4collision.decode(blob)[2]
    except Exception as err:  # noqa: BLE001
        out["fo4collision"] = f"{type(err).__name__}: {err}"
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("nif", nargs="?", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--staging", type=Path)
    parser.add_argument("--scale", type=float, default=1.0)
    args = parser.parse_args(argv)
    try:
        args.scale = parse_scale(args.scale)
    except ValueError as err:
        parser.error(str(err))
    if args.manifest is not None:
        if args.staging is None:
            parser.error("--manifest requires --staging")
        try:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError, RecursionError) as err:   # also bad UTF-8, > 4300-digit ints, deep nesting
            reports = [{"path": str(args.manifest), "scale": args.scale, "flags": ["unreadable"],
                        "error": str(err)}]
        else:
            reports = audit_manifest(manifest, args.staging.resolve(), scale=args.scale)
    elif args.nif is not None:
        reports = audit_files([args.nif], scale=args.scale)
    else:
        parser.error("a NIF path or --manifest is required")
    result = {"models": len(reports), "flagged": len(failed(reports)), "reports": reports,
              "smaller_ratio": SMALLER_RATIO, "offset_ratio": OFFSET_RATIO}
    print(json.dumps(result, indent=2, allow_nan=False))
    return int(bool(failed(reports) or not reports))


if __name__ == "__main__":
    raise SystemExit(main())
