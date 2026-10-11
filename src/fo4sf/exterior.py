"""Fallout 4 exterior references -> placements in a Starfield worldspace (terrain experiment 2c).

Input: an exterior placement export (dotnet/Fo4Land export-exterior, schema v2 like dotnet/Fo4Export's cell exports) and
the converter's manifest (scripts/convert_batch.py). Every reference ends in exactly one of two lists, never silently
dropped: `placed` (a converted model at FO4 position / 70) or `skipped` with a reason code and detail.

Frames: a FO4 position (x, y, z) in game units becomes (x, y, z) / 70 metres in the worldspace's own frame, the same
absolute mapping the experiment 2 BTD uses (hypothesis H, docs/terrain/experiment2.md). The Starfield exterior cell is
floor(x / 100 m), floor(y / 100 m) (terrain_grid.sf_cell_of). Rotations are copied (radians, both games use the same
reference convention); for offline geometry they are applied as PluginSpike does: Bethesda angles turn clockwise seen
from the positive axis, X then Y then Z (`ref_matrix`; a pure Z rotation is the familiar clockwise heading).
"""
import math
import re
from typing import Dict, List, Optional, Tuple

from . import terrain_grid as tg

UNITS_PER_METRE = 70.0

# base record types whose models go through the converter (convert_batch's interior default plus the loose items an
# exterior holds: plants, food, weapons, ammunition, armour; they become plain statics here, visuals only)
CONVERT_TYPES = ("Static", "StaticCollection", "MovableStatic", "Furniture", "Door", "Activator", "Container",
                 "MiscItem", "Terminal", "Flora", "Ingestible", "Weapon", "Ammunition", "Armor")

# types that are never converted, with the reason (everything else outside CONVERT_TYPES gets "type_not_translated")
TYPE_REASONS = {
    "Light": "light source: exterior lights are not translated (daylight scene, no Starfield LIGH records built)",
    "TextureSet": "decal (placed texture set): no decal translation yet",
    "BendableSpline": "bendable spline (power lines, cables): no Starfield equivalent built yet",
    "IdleMarker": "idle marker: AI animation marker, editor-only",
    "SoundMarker": "sound marker: ambient sound not translated",
    "AcousticSpace": "acoustic space: ambient sound not translated",
}
# the same model filter convert_batch applies to cell exports (editor markers; fog / light / particle effect meshes)
MARKER_RE = re.compile(r"marker", re.I)
EFFECTS_RE = re.compile(r"^\\?effects[\\/]", re.I)


def source_key(model: str) -> str:
    """convert_batch's identity of a model: 'meshes\\' + the model path, compared case-insensitively."""
    return ("meshes\\" + model.replace("/", "\\").lstrip("\\")).lower()


def classify(ref: dict, convert_types=CONVERT_TYPES) -> Tuple[str, Optional[str], str]:
    """('convert', None, '') or ('skip', reason code, detail) for one exported reference."""
    t, model = ref.get("type") or "?", ref.get("model") or ""
    if t in TYPE_REASONS:
        return "skip", "type_not_translated", TYPE_REASONS[t]
    if t not in convert_types:
        return "skip", "type_not_translated", f"base type {t} is not converted"
    if not model:
        what = {"Activator": "trigger volume or primitive (no model)", "Static": "static without a model (collision "
                "plane / primitive)"}.get(t, f"{t} base without a model")
        return "skip", "no_model", what
    if MARKER_RE.search(model):
        return "skip", "editor_marker", f"editor marker model {model}"
    if EFFECTS_RE.search(model):
        return "skip", "effect", f"effect mesh (fog, light beam or particles) {model}"
    return "convert", None, ""


def select(export: dict, convert_types=CONVERT_TYPES) -> Tuple[dict, List[dict]]:
    """(cell JSON with only the references to convert, [skipped entries]) for convert_batch --cell-json."""
    keep, skipped = [], []
    for r in export["refs"]:
        action, code, detail = classify(r, convert_types)
        if action == "convert":
            keep.append(r)
        else:
            skipped.append(skip_entry(r, code, detail))
    for d in export.get("deferred_refs", []):
        skipped.append(skip_entry(d, "deferred", d.get("reason", "deferred by the exporter")))
    sub = {k: v for k, v in export.items() if k not in ("refs", "deferred_refs")}
    sub["refs"] = keep
    return sub, skipped


def skip_entry(ref: dict, code: str, detail: str) -> dict:
    return {"formkey": ref.get("formkey"), "type": ref.get("type"), "base_editor_id": ref.get("base_editor_id"),
            "model": ref.get("model"), "exterior_cell": ref.get("exterior_cell"), "reason": code, "detail": detail}


# ------------------------------------------------------------------------------------------------------------ geometry
def ref_matrix(rot) -> Tuple[float, ...]:
    """Row-major 3x3 world rotation of a reference (radians, Bethesda clockwise angles, X then Y then Z), the matrix
    PluginSpike.RotateOffset and scripts/game/routes.py use: R = Rz(-z) Ry(-y) Rx(-x)."""
    cx, sx = math.cos(-rot[0]), math.sin(-rot[0])
    cy, sy = math.cos(-rot[1]), math.sin(-rot[1])
    cz, sz = math.cos(-rot[2]), math.sin(-rot[2])
    rx = (1, 0, 0, 0, cx, -sx, 0, sx, cx)
    ry = (cy, 0, sy, 0, 1, 0, -sy, 0, cy)
    rz = (cz, -sz, 0, sz, cz, 0, 0, 0, 1)
    return _mul(rz, _mul(ry, rx))


def _mul(a, b):
    return tuple(sum(a[3 * r + k] * b[3 * k + c] for k in range(3)) for r in range(3) for c in range(3))


def to_world(v, pos_m, rot, scale):
    """A model-space point (metres) of a reference placed at pos_m (metres) with rot (radians) and scale."""
    m = ref_matrix(rot)
    return tuple(pos_m[a] + scale * (m[3 * a] * v[0] + m[3 * a + 1] * v[1] + m[3 * a + 2] * v[2]) for a in range(3))


def metres(pos_units) -> Tuple[float, float, float]:
    return tuple(float(v) / UNITS_PER_METRE for v in pos_units)


# ------------------------------------------------------------------------------------------------------------ placing
def plugin_editor_id(manifest_editor_id: str, prefix: str) -> str:
    """The base record EditorID in the experiment plugin: convert_batch's 'FO4Port_<stem>' with our own prefix, so the
    experiment never shares an EditorID with FO4Port.esm."""
    return prefix + manifest_editor_id[len("FO4Port_"):] if manifest_editor_id.startswith("FO4Port_") \
        else prefix + manifest_editor_id


def place(selected: dict, manifest: dict, cell_min: int, cell_max: int, edid_prefix: str = "FO4CW_"):
    """Join the selected references with the converter manifest.
    Returns (bases, placed, skipped): bases = [{"key", "edid", "model", "door"?}] in first-use order;
    placed = [{"src", "base", "cell", "pos", "rot", "scale", "disabled", ...}] (pos in metres, door origin offsets
    applied); skipped = [{..., "reason", "detail"}]."""
    items = {i["source"].replace("/", "\\").lower(): i for i in manifest["items"]}
    failures = {f["nif"].replace("/", "\\").lower(): f["reason"] for f in manifest.get("failures", [])}
    bases, base_index, placed, skipped = [], {}, [], []
    edids = set()
    for r in sorted(selected["refs"], key=lambda r: r["formkey"]):
        key = source_key(r["model"])
        item = items.get(key)
        if item is None:
            if key in failures:
                skipped.append(skip_entry(r, "conversion_failed", failures[key]))
            else:
                skipped.append(skip_entry(r, "not_converted", "model missing from the converter manifest"))
            continue
        pos = metres(r["pos"])
        cell = tg.sf_cell_of(pos[0], pos[1])
        if not (cell_min <= cell[0] <= cell_max and cell_min <= cell[1] <= cell_max):
            skipped.append(skip_entry(r, "outside_terrain", f"Starfield cell {list(cell)} outside {cell_min}..{cell_max}"))
            continue
        if key not in base_index:
            edid = plugin_editor_id(item["editor_id"], edid_prefix)
            if edid.lower() in edids:
                raise ValueError(f"duplicate base EditorID {edid}")
            edids.add(edid.lower())
            base = {"key": key, "edid": edid, "model": item["model"], "source": item["source"]}
            if "door" in item:
                base["door"] = item["door"]
            base_index[key] = len(bases)
            bases.append(base)
        b = bases[base_index[key]]
        scale = float(r.get("scale") or 1.0)
        rot = [float(v) for v in r["rot"]]
        if "door" in b:                          # rigged door: its NIF origin is the hinge, shift as PluginSpike does
            off = b["door"]["origin_offset"]
            m = ref_matrix(rot)
            pos = tuple(pos[a] + scale * sum(m[3 * a + k] * off[k] for k in range(3)) for a in range(3))
        placed.append({"src": r["formkey"], "base": base_index[key], "cell": list(cell),
                       "pos": [round(v, 5) for v in pos], "rot": rot, "scale": scale,
                       "disabled": bool(r.get("disabled")), "fo4_persistent": bool(r.get("persistent")),
                       "fo4_cell": r.get("exterior_cell"), "enable_parent": r.get("enable_parent") is not None})
    return bases, placed, skipped


def reason_counts(skipped: List[dict]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for s in skipped:
        out[s["reason"]] = out.get(s["reason"], 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


# ------------------------------------------------------------------------------------------------------------ surfaces
def point_in_triangle_z(tri, x, y) -> Optional[float]:
    """z of the triangle's plane at (x, y) when (x, y) lies inside its xy projection (edges included), else None."""
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = tri
    d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(d) < 1e-12:
        return None
    l1 = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / d
    l2 = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / d
    l3 = 1.0 - l1 - l2
    if min(l1, l2, l3) < -1e-9:
        return None
    return l1 * az + l2 * bz + l3 * cz


def surfaces_at(tris, x, y) -> List[float]:
    """Every z where a triangle covers (x, y), highest first."""
    zs = [z for t in tris if (z := point_in_triangle_z(t, x, y)) is not None]
    return sorted(zs, reverse=True)


def top_z(tris, x, y, below=math.inf) -> Optional[float]:
    """Highest surface at (x, y) not above `below` (what a player dropped from `below` lands on), or None."""
    zs = [z for z in surfaces_at(tris, x, y) if z <= below]
    return zs[0] if zs else None


def disc_offsets(radius: float, rings: int = 2, per_ring: int = 8):
    """(dx, dy) samples of a disc: the centre plus `rings` rings of `per_ring` points."""
    out = [(0.0, 0.0)]
    for k in range(1, rings + 1):
        r = radius * k / rings
        out += [(r * math.cos(2 * math.pi * j / per_ring), r * math.sin(2 * math.pi * j / per_ring)) for j in range(per_ring)]
    return out


def landing(tris, ground, x, y, drop_z, radius=0.6):
    """What a player dropped at (x, y) from drop_z lands on, judged over a disc of `radius` (about the character
    capsule): {"z": highest support under the drop, "spread": max - min support over the disc, "ground": terrain z,
    "on_object": the support is a collision surface above the terrain}. ground(x, y) is the terrain height."""
    zs, objs = [], []
    for dx, dy in disc_offsets(radius):
        g = ground(x + dx, y + dy)
        o = top_z(tris, x + dx, y + dy, drop_z)
        zs.append(max(g, o) if o is not None else g)
        objs.append(o is not None and o > g)
    g0 = ground(x, y)
    return {"z": max(zs), "spread": max(zs) - min(zs), "ground": g0, "on_object": objs[0],
            "all_on_object": all(objs)}
