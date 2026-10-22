"""Compare a converted Starfield NIF's drawn-geometry AABB with its collision AABB.

Offline only: this does not prove the in-game activate prompt. Exit 1 when a model is flagged
(missing, unreadable, no_mesh, much-smaller, or offset collision), including partial body
decode and malformed manifest entries. Nonfinite --scale / per-item scale is rejected before
comparison. JSON output never emits NaN/Infinity.

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

# Collision extent / mesh extent on the mesh's longest axis below this is "much smaller".
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
    except (TypeError, ValueError) as err:
        raise ValueError(f"scale is not a finite number: {value!r}") from err
    if not math.isfinite(scale):
        raise ValueError(f"scale is not finite: {value!r}")
    return scale


def _finite_xyz(v):
    return isinstance(v, (list, tuple)) and len(v) == 3 and all(_finite_number(x) for x in v)


def _finite_aabb(lo, hi):
    return _finite_xyz(lo) and _finite_xyz(hi)


def _round_xyz(v, n=4):
    if not _finite_xyz(v):
        raise ValueError("nonfinite bound")
    return [round(x, n) for x in v]


def aabb_info(lo, hi):
    return {"min": _round_xyz(lo), "max": _round_xyz(hi),
            "center": _round_xyz([(lo[a] + hi[a]) / 2 for a in range(3)]),
            "extent": _round_xyz([hi[a] - lo[a] for a in range(3)])}


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

    Box templates use sfcollision.read_box. Other fo4-native tagfiles use sfbodies.nif_bodies
    (existing Starfield tagfile readback). fo4collision.decode is FO4 packfile-only and is not used.
    """
    bodies = []
    errors = []
    world = nif.world_transforms(f)
    for i in range(len(f.blocks)):
        if f.type_of(i) != "bhkNPCollisionObject":
            continue
        target, _, data = struct.unpack_from("<iHi", f.blocks[i], 0)
        if not (0 <= data < len(f.blocks)) or f.type_of(data) != "bhkPhysicsSystem":
            errors.append(f"collision object {i}: bad physics system")
            continue
        n, = struct.unpack_from("<I", f.blocks[data], 0)
        blob = f.blocks[data][4:4 + n]
        if not (0 <= target < len(f.blocks)):
            errors.append(f"collision object {i}: invalid target {target}")
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
        except (sfbodies.BodyError, ValueError, struct.error, IndexError) as err:
            errors.append(f"collision object {i}: {err}")
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
    longest = max(range(3), key=lambda a: m_ext[a])
    if m_ext[longest] >= MIN_EXTENT and c_ext[longest] < SMALLER_RATIO * m_ext[longest]:
        flags.append("much_smaller")
    m_c = [(m_lo[a] + m_hi[a]) / 2 for a in range(3)]
    c_c = [(c_lo[a] + c_hi[a]) / 2 for a in range(3)]
    diag = math.sqrt(sum(x * x for x in m_ext))
    dist = math.sqrt(sum((m_c[a] - c_c[a]) ** 2 for a in range(3)))
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
        mesh = mesh_aabb(f, scale)
    except (ValueError, struct.error, IndexError, nif.NifError) as err:
        mesh = None
        errors.append(str(err))
    bodies, body_errors = collision_bodies(f, scale)
    errors.extend(body_errors)
    coll = combined_aabb(bodies)
    flags = []
    if errors:
        flags.append("unreadable")
    for flag in flag_bounds(mesh, coll):
        if flag not in flags:
            flags.append(flag)
    report = {"path": path, "scale": scale, "flags": flags,
              "mesh": aabb_info(*mesh) if mesh else None,
              "collision": {"bodies": len(bodies), "per_body": bodies,
                            **(aabb_info(*coll) if coll else {"min": None, "max": None})}}
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
        except (OSError, json.JSONDecodeError, UnicodeError) as err:
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
