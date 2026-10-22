"""What the core placed, and left out, around the door-exit arrivals arrival_ground.py read (door-exit-heights.md).

    python scripts/terrain/arrival_objects.py <core staging dir> <arrival_ground.json> [--radius 20] [--json <out.json>]

<arrival_ground.json> is arrival_ground.py's --json output: each row's marker and read position in core-local metres,
the frame of the core's objects.json. For each row, every reference objects.json places within the radius (in xy) of
either point is listed nearest first: its class (STAT or a promoted class), base model, collision kind (as the core
recorded it: fo4-native and the other native sources, guessed-boxes, rigged-door-box, none), position, height above
the marker and above the read position, scale and disabled flag. skipped.json's references are listed too when their
FO4 cell (4096 units, local metres x 70) touches the radius: skipped refs carry no position, only the cell, so these are
candidates, not proof. Reading it, with arrival_ground's verdict:
  marker floats, player fell: look for an object at about the marker's height with collision "none", or a skipped one.
  player lifted well above the ground: look for an object under the read position whose base z is below it.
Positions are reference origins; objects.json has no bounds, so an object's top is not known. Read-only.
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import near_changes  # noqa: E402

FO4_CELL_M = 4096 / 70.0       # one FO4 exterior cell in metres (FO4 units / 70)


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def collision_of(objects):
    """({src: collision kind} of STAT references, {model: collision kind}) from objects.json's bases. Promoted classes
    (doors, containers, activators, ...) leave refs and carry no base index, only the base's model, so they are matched
    by model."""
    bases = objects.get("bases") or []
    by_src = {r["src"]: bases[r["base"]].get("collision") for r in objects.get("refs") or []
              if isinstance(r.get("base"), int) and 0 <= r["base"] < len(bases)}
    by_model = {near_changes.model_key(b.get("model")): b.get("collision") for b in bases if b.get("model")}
    return by_src, by_model


def placed_near(objects, points, radius):
    """[{src, class, model, collision, pos, dist, dz_marker, dz_got, scale, disabled}] within radius of any point."""
    by_src, by_model = collision_of(objects)
    out = []
    for src, p in near_changes.placements(objects).items():
        pos = p.get("pos")
        if not pos:
            continue
        dist = min(math.hypot(pos[0] - q[0], pos[1] - q[1]) for q in points.values())
        if dist > radius:
            continue
        collision = by_src.get(src, by_model.get(near_changes.model_key(p.get("model"))))
        out.append({"src": src, "class": p["class"], "model": p.get("model"), "collision": collision,
                    "pos": [round(v, 3) for v in pos], "dist": round(dist, 2),
                    **{f"dz_{k}": round(pos[2] - q[2], 2) for k, q in points.items()},
                    "scale": p.get("scale", 1.0), "disabled": bool(p.get("disabled"))})
    return sorted(out, key=lambda e: (e["dist"], e["src"]))


def cells_touching(points, radius):
    """The FO4 cells (x, y) whose square comes within radius of any point."""
    cells = set()
    for x, y, _z in points.values():
        for cx in range(math.floor((x - radius) / FO4_CELL_M), math.floor((x + radius) / FO4_CELL_M) + 1):
            for cy in range(math.floor((y - radius) / FO4_CELL_M), math.floor((y + radius) / FO4_CELL_M) + 1):
                nx = min(max(x, cx * FO4_CELL_M), (cx + 1) * FO4_CELL_M)
                ny = min(max(y, cy * FO4_CELL_M), (cy + 1) * FO4_CELL_M)
                if math.hypot(x - nx, y - ny) <= radius:
                    cells.add((cx, cy))
    return cells


def skipped_near(skipped, points, radius):
    cells = cells_touching(points, radius)
    return [{k: s.get(k) for k in ("formkey", "type", "model", "exterior_cell", "reason", "detail")}
            for s in skipped.get("refs") or []
            if isinstance(s.get("exterior_cell"), list) and len(s["exterior_cell"]) == 2
            and tuple(s["exterior_cell"]) in cells]


def read(objects, skipped, ground_rows, radius):
    out = []
    for r in ground_rows:
        points = {"marker": r["marker_local"], "got": r["got_local"]}
        out.append({"id": r.get("id"), "cell_edid": r.get("cell_edid"), "marker": r.get("marker"), "got": r.get("got"),
                    "marker_local": points["marker"], "got_local": points["got"],
                    "placed": placed_near(objects, points, radius), "skipped": skipped_near(skipped, points, radius)})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("core")
    ap.add_argument("ground")
    ap.add_argument("--radius", type=float, default=20.0, help="metres in xy around the marker and the read position")
    ap.add_argument("--json", default="")
    a = ap.parse_args(argv)
    try:
        objects = load(os.path.join(a.core, "objects.json"))
        sk_path = os.path.join(a.core, "skipped.json")
        skipped = load(sk_path) if os.path.isfile(sk_path) else {}
        found = read(objects, skipped, load(a.ground)["rows"], a.radius)
    except (OSError, ValueError, KeyError) as e:
        sys.exit(str(e))
    for f in found:
        print(f"{f['id']}  {f['cell_edid']}  marker {f['marker_local']} ({f['marker']}), got {f['got_local']} ({f['got']})")
        for e in f["placed"]:
            print(f"  {e['dist']:6.1f} m  {e['class']:<10} {e['collision'] or '-':<16} z {e['pos'][2]:8.2f} "
                  f"(marker {e['dz_marker']:+.1f}, got {e['dz_got']:+.1f})  scale {e['scale']}"
                  f"{'  DISABLED' if e['disabled'] else ''}  {e['src']}  {e['model']}")
        for s in f["skipped"]:
            print(f"  skipped in FO4 cell {s['exterior_cell']}: {s['formkey']} {s['type']} {s['model']} ({s['reason']})")
        print(f"  {len(f['placed'])} placed within {a.radius} m, {len(f['skipped'])} skipped in the cells touching it")
    if a.json:
        with open(a.json, "x", encoding="utf-8") as f:
            json.dump({"radius": a.radius, "rows": found}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
