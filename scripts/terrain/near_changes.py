"""near_changes.py: what changed between two core builds around one spot (read-only).

  python scripts/terrain/near_changes.py --old <core build A> --new <core build B> --center=X,Y [--radius 300]
      [--old-manifest <manifest.json> ...] [--new-manifest <manifest.json> ...]

Both builds are make_core64c stage outputs (objects.json); X,Y and the radius are core-local metres, as objects.json
positions (Red Rocket's workshop station sits at about -1005, 1136). Every reference within the radius in either build,
matched by its FO4 source key, is listed when it differs: only in one build, a different class (STAT or a promoted
class: containers, items, activators, workshops, doors, ...), a different placement (position, rotation, scale, disabled,
open by default; numbers within TOLERANCE), different promoted fields (editor id, name, radius, a door's destination and
arrival), a different base (model, door, collision source), or, with
the conversions' manifests, a different conversion of its model (door rig, door_error / door_not_opening, movable mass,
collision source). Written for the v6 Red Rocket crash (2026-10-19): v5 walked past Red Rocket, v6 crashes near it.
Prints one JSON line per changed reference, then a count per kind of change. Writes nothing.
"""
import argparse
import json
import math
import os
from collections import Counter

BASE_FIELDS = ("model", "door", "collision")
PLACEMENT_FIELDS = ("pos", "rot", "scale", "disabled", "open_by_default")
PROMOTED_FIELDS = ("model", "edid", "name", "radius", "vanilla", "destination", "arrival")
TOLERANCE = 1e-3    # metres, radians and scale: float rounding between builds, not a move
CONVERSION_FIELDS = ("door_rig", "door_error", "door_not_opening", "movable_kg", "collision_source", "load_door")


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def placements(objects):
    """{src: {"class", "pos", "base" fields}} of one objects.json: STAT references and every promoted class."""
    out = {}
    bases = objects.get("bases") or []
    for r in objects.get("refs") or []:
        b = bases[r["base"]] if isinstance(r.get("base"), int) and 0 <= r["base"] < len(bases) else {}
        out[r["src"]] = {"class": "STAT", **{k: r[k] for k in PLACEMENT_FIELDS if k in r},
                         **{k: b.get(k) for k in BASE_FIELDS if k in b}}
    for key, entries in objects.items():
        if key in ("world", "edid_prefix", "bases", "refs", "lights", "light_bases", "garage_buttons") \
                or not isinstance(entries, list):
            continue
        for e in entries:
            if isinstance(e, dict) and "src" in e:
                out[e["src"]] = {"class": key, **{k: e[k] for k in PLACEMENT_FIELDS + PROMOTED_FIELDS if k in e}}
    return out


def conversions(paths):
    """{converted model (model_key: lower case, forward slashes): its conversion fields} of the given manifests."""
    out = {}
    for p in paths:
        for it in load(p).get("items", []):
            e = {}
            if "door" in it:
                e["door_rig"] = it["door"].get("rig", "template")
            for k in ("door_error", "door_not_opening", "load_door"):
                if k in it:
                    e[k] = it[k]
            if "movable" in it:
                e["movable_kg"] = it["movable"].get("mass_kg")
            src = (it.get("collision_report") or {}).get("source")
            if src:
                e["collision_source"] = src
            out[model_key(it.get("model"))] = e
    return out


def model_key(model):
    return str(model or "").replace("\\", "/").lower()


def same(a, b):
    """Equal, numbers within TOLERANCE at any depth (positions, rotations, a door's arrival point)."""
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(a - b) <= TOLERANCE
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    return a == b


def near(pos, center, radius):
    return bool(pos) and math.hypot(pos[0] - center[0], pos[1] - center[1]) <= radius


def changes(old, new, center, radius, old_conv=None, new_conv=None):
    """[(src, {"kinds": [...], "old": ..., "new": ...})] for references within radius of center in either build."""
    a, b = placements(old), placements(new)
    rows = []
    for src in sorted(set(a) | set(b)):
        pa, pb = a.get(src), b.get(src)
        if not (near((pa or {}).get("pos"), center, radius) or near((pb or {}).get("pos"), center, radius)):
            continue
        kinds = []
        if pa is None or pb is None:
            kinds.append("only_new" if pa is None else "only_old")
        else:
            if pa["class"] != pb["class"]:
                kinds.append("class")
            kinds += [f"base.{k}" for k in BASE_FIELDS if pa.get(k) != pb.get(k)]
            kinds += [f"placement.{k}" for k in PLACEMENT_FIELDS if not same(pa.get(k), pb.get(k))]
            kinds += [f"promoted.{k}" for k in PROMOTED_FIELDS if k not in BASE_FIELDS and not same(pa.get(k), pb.get(k))]
        row = {"src": src, "old": pa, "new": pb}
        if old_conv is not None and new_conv is not None:
            ca = old_conv.get(model_key(pa.get("model")), {}) if pa else {}
            cb = new_conv.get(model_key(pb.get("model")), {}) if pb else {}
            kinds += [f"conversion.{k}" for k in CONVERSION_FIELDS if ca.get(k) != cb.get(k)]
            if ca != cb:
                row["old_conversion"], row["new_conversion"] = ca, cb
        if kinds:
            row["kinds"] = kinds
            rows.append(row)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--center", required=True, help="X,Y in core-local metres (write --center=-1005,1136 for a negative X)")
    ap.add_argument("--radius", type=float, default=300.0)
    ap.add_argument("--old-manifest", action="append", default=[])
    ap.add_argument("--new-manifest", action="append", default=[])
    a = ap.parse_args(argv)
    center = tuple(float(v) for v in a.center.split(","))
    with_conv = bool(a.old_manifest and a.new_manifest)
    rows = changes(load(os.path.join(a.old, "objects.json")), load(os.path.join(a.new, "objects.json")), center,
                   a.radius, conversions(a.old_manifest) if with_conv else None,
                   conversions(a.new_manifest) if with_conv else None)
    for r in rows:
        print(json.dumps(r, sort_keys=True))
    print(json.dumps({"changed_references": len(rows),
                      "by_kind": dict(sorted(Counter(k for r in rows for k in r["kinds"]).items()))}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
