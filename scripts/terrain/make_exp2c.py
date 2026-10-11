"""Terrain experiment 2c: the real Fallout 4 objects around Red Rocket on the exp2b terrain (docs/terrain/experiment2c.md).

    dotnet run --project dotnet/Fo4Land -c Release -- <Fallout4.esm> export-exterior Commonwealth -20 16 -15 21 <work>/export.json
    python scripts/terrain/make_exp2c.py select --export <work>/export.json --work <work>
    python scripts/convert_batch.py --cell-json <work>/convert_input.json --staging <work>/convert --prefix fo4cw
           --types <printed by select> --limit 100000 --resume  + the usual converter arguments (--starfield-data too)
    python scripts/terrain/make_exp2c.py stage --work <work> --exp2b <terrain_exp2b> --out <terrain_exp2c> --sf-esm <Starfield.esm>
    python scripts/terrain/make_exp2c.py check --work <work> --exp2b <terrain_exp2b> --out <terrain_exp2c> [--fo4 <Fallout4.esm>]

select   classifies every exported reference: convert, or skip with a reason (never silently). Writes convert_input.json
         (the references to convert, schema v2) and selection.json.
stage    joins the selection with the converter manifest (exterior.place), copies exp2b's BTD, mask and params, writes
         objects.json for dotnet/TerrainExp2, copies the converted meshes / geometries / materials / textures under
         Data\\, builds FO4TerrainExp2.esm (+ the unchanged Mars plugin) with TerrainExp2, and writes plan.json: the 14
         exp2 terrain points (each re-judged against the placed collision) plus points on large flat objects (dropped
         from 150 m) and on the Red Rocket shop floor (a second entry, dropped from just above the floor, under its roof).
check    raw-walks the plugins (masters, cells, REFR counts, base records, models on disk, exp2b records unchanged),
         decodes the BTD under every placed object's origin (object z - terrain z; with --fo4 also against FO4's own LAND)
         and re-derives every plan point from the converted collision. Writes offline_check.json.
Everything this writes stays outside the repo (derived game data).
"""
import argparse
import hashlib
import json
import math
import os
import shutil
import statistics
import struct
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "src"))
from fo4sf import btd, exterior, fo4land, sfbodies  # noqa: E402
from fo4sf import terrain_grid as tg  # noqa: E402

sys.path.insert(0, HERE)
import overlay_records  # noqa: E402

EDID_PREFIX = "FO4CW_"
BUILDING = "0211C0:Fallout4.esm"        # RedRExt_Workshop01: rocket tower, canopy, shop ceiling (no floor)
SHOP = "1B5F12:Fallout4.esm"            # RedRExt_Workshop02: shop floor and roof, same origin and rotation
SHOP_LOCAL = (-6.0, 9.0, 6.0, 19.0)     # shop footprint in the building's own frame (x0, y0, x1, y1), metres
FLOOR_DROP = 0.75                        # floor entry: dropped from floor + 0.75 m (feet), head stays under the ceiling
PLAYER_HEIGHT = 1.9                      # room needed above the drop height
DROP_Z = 150.0
MIN_FLAT_AREA = 6.0                      # m2 of level (normal z > 0.995) collision for a "large flat object"
NATIVE = ("fo4-native", "fo4-none", "passable-door")
DATA_TREES = ("meshes", "geometries", "materials", "textures")


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def save(path, value, indent=1):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=indent)
    os.replace(tmp, path)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------------------------------------------------- select
def cmd_select(a):
    export = load(a.export)
    sub, skipped = exterior.select(export)
    save(os.path.join(a.work, "convert_input.json"), sub)
    models = sorted({exterior.source_key(r["model"]) for r in sub["refs"]})
    rep = {"export": os.path.abspath(a.export), "refs": len(export["refs"]), "deferred": len(export.get("deferred_refs", [])),
           "to_convert": len(sub["refs"]), "models": len(models), "skipped": len(skipped),
           "skip_reasons": exterior.reason_counts(skipped), "convert_types": list(exterior.CONVERT_TYPES),
           "skipped_refs": skipped}
    save(os.path.join(a.work, "selection.json"), rep)
    print(f"{rep['refs']} references + {rep['deferred']} deferred: convert {rep['to_convert']} ({rep['models']} models), "
          f"skip {rep['skipped']}: {rep['skip_reasons']}")
    print("convert_batch --types " + ",".join(exterior.CONVERT_TYPES))
    return 0


# ------------------------------------------------------------------------------------------------------------- world
class World:
    """Placed objects with their converted collision, the decoded BTD and the queries the plan needs."""

    def __init__(self, data_dir, bases, placed, btd_path):
        self.bases, self.placed = bases, placed
        self.model_tris, self.collision_errors = {}, {}
        for i, b in enumerate(bases):
            try:
                with open(os.path.join(data_dir, "meshes", b["model"]), "rb") as f:
                    bodies = sfbodies.nif_bodies(f.read())
                self.model_tris[i] = np.array([t for body in bodies for t in body["triangles"]], np.float64).reshape(-1, 3, 3)
            except (OSError, ValueError, struct.error) as e:
                self.collision_errors[b["model"]] = f"{type(e).__name__}: {e}"
        self.tris, self.owners = exterior.world_triangles(self.model_tris, placed)
        self.index = exterior.SurfaceIndex(self.tris, self.owners)
        with open(btd_path, "rb") as f:
            t = btd.read(f.read())
        self.heights, self.n = t.heights_m(), t.ncx
        self.step = (t.hmax - t.hmin) / 65535.0
        self.origin = tg.grid_origin(self.n)
        self.by_src = {p["src"]: k for k, p in enumerate(placed)}

    def ground(self, x, y):
        return tg.point_interp(self.heights, self.origin, self.origin, tg.SF_STEP_M, x, y)["bilinear"]

    def ground_all(self, x, y):
        return tg.point_interp(self.heights, self.origin, self.origin, tg.SF_STEP_M, x, y)

    def landing(self, x, y, drop_z):
        return exterior.landing(self.index.top, self.ground, x, y, drop_z)

    def bounds(self, k, local=None):
        """xy AABB (x0, y0, x1, y1) of placed object k's collision, or of a rectangle in its own frame."""
        p = self.placed[k]
        if local is not None:
            x0, y0, x1, y1 = local
            pts = [exterior.to_world((x, y, 0), p["pos"], p["rot"], p["scale"]) for x in (x0, x1) for y in (y0, y1)]
        else:
            pts = self.tris[self.owners == k].reshape(-1, 3)
        pts = np.asarray(pts)
        return float(pts[:, 0].min()), float(pts[:, 1].min()), float(pts[:, 0].max()), float(pts[:, 1].max())

    def describe(self, k):
        if k is None:
            return None
        p, b = self.placed[k], self.bases[self.placed[k]["base"]]
        return {"src": p["src"], "edid": b["edid"], "model": b["model"], "pos": p["pos"], "rot": p["rot"],
                "scale": p["scale"], "collision": b.get("collision")}

    def level_area(self):
        """Per placed object: area (m2) of its level (normal z > 0.995) world collision triangles."""
        if not len(self.tris):
            return np.zeros(len(self.placed))
        u, w = self.tris[:, 1] - self.tris[:, 0], self.tris[:, 2] - self.tris[:, 0]
        n = np.cross(u, w)
        ln = np.linalg.norm(n, axis=1)
        level = n[:, 2] / np.maximum(ln, 1e-12) > 0.995
        return np.bincount(self.owners[level], weights=ln[level] / 2, minlength=len(self.placed))


def terrain_points(world, points, drop_z):
    """exp2b's terrain points re-judged with the objects in place:
    terrain              no object stands more than 0.1 m above the terrain within 0.6 m: expect unchanged
    terrain_covered      a placed object's collision is above the terrain at the point: expect = that surface
    terrain_near_object  the point is terrain but an object within 0.6 m may catch the dropped player: expect
                         unchanged, the reading is informational
    The original terrain expectation is kept as terrain_expect."""
    out = []
    for p in points:
        land = world.landing(p["x"], p["y"], drop_z)
        near = exterior.nearby_object(world.index.top, world.ground, p["x"], p["y"], drop_z)
        q = {"label": p["label"], "x": p["x"], "y": p["y"], "kind": "terrain", "expect": p["expect"],
             "terrain_expect": p["expect"], "landing": landing_json(world, land),
             "nearby_object": None if near is None else {"distance": near["distance"], "height": round(near["height"], 4),
                                                         "owner": world.describe(near["owner"])}}
        if land["on_object"]:
            q.update(kind="terrain_covered", expect=round(land["centre"], 4), owner=world.describe(land["owner"]))
        elif near is not None:
            q.update(kind="terrain_near_object", owner=world.describe(near["owner"]))
        out.append(q)
    return out


def landing_json(world, land):
    return {"centre": round(land["centre"], 4), "max": round(land["z"], 4), "spread": round(land["spread"], 4),
            "ground": round(land["ground"], 4), "on_object": land["on_object"], "all_on_object": land["all_on_object"],
            "owners": [world.placed[k]["src"] for k in land["owners"]]}


def object_point(world, k, label, kind, drop_z, bounds=None, need_clearance=0.0, count=1):
    picks = exterior.pick_points(world.index, world.ground, k, bounds or world.bounds(k), drop_z, count=count,
                                 need_clearance=need_clearance)
    out = []
    for i, (x, y, land, free) in enumerate(picks):
        out.append({"label": label if count == 1 else f"{label}_{i + 1}", "x": round(x, 4), "y": round(y, 4),
                    "kind": kind, "expect": round(land["centre"], 4), "landing": landing_json(world, land),
                    "above_terrain": round(land["centre"] - land["ground"], 4),
                    "clearance": None if math.isinf(free) else round(free, 4), "owner": world.describe(k)})
    return out


def large_flat_objects(world, exclude, count_elevated=1, count_ground=2):
    """The biggest level tops (sampled on a 1 m grid, exposed to a drop from DROP_Z) among plain statics with FO4's
    own collision, upright (|rot x|, |rot y| < 0.02 rad) and enabled: the largest elevated one (>= 3 m above the
    terrain) and the largest ground-level ones (< 1.5 m), each a different model."""
    area = world.level_area()
    scored = []
    for k in np.argsort(-area):
        k = int(k)
        p, b = world.placed[k], world.bases[world.placed[k]["base"]]
        if area[k] < MIN_FLAT_AREA:
            break
        if (p["src"] in exclude or p["disabled"] or b.get("collision") != "fo4-native" or abs(p["rot"][0]) >= 0.02
                or abs(p["rot"][1]) >= 0.02 or b["model"].lower().startswith(("fo4cw\\scol\\", "fo4cw/scol/"))):
            continue
        n = len(exterior.flat_samples(world.index, world.ground, k, world.bounds(k), DROP_Z, step=1.0))
        if n:
            scored.append((-n, p["src"], k))
    scored.sort()
    chosen, models = [], set()
    want = {"elevated": count_elevated, "ground": count_ground}
    for _, src, k in scored:
        b = world.bases[world.placed[k]["base"]]
        if b["model"] in models:
            continue
        pts = object_point(world, k, "", "object_top", DROP_Z)
        if not pts:
            continue
        cls = "elevated" if pts[0]["above_terrain"] >= 3.0 else "ground" if pts[0]["above_terrain"] < 1.5 else None
        if cls is None or want[cls] == 0:
            continue
        want[cls] -= 1
        models.add(b["model"])
        stem = b["edid"][len(EDID_PREFIX):].lower()
        pts[0]["label"] = f"{'roof' if cls == 'elevated' else 'flat'}_{stem}"[:40]
        chosen.append(pts[0])
        if not any(want.values()):
            break
    return chosen


# ------------------------------------------------------------------------------------------------------------- stage
def copy_tree(src, dst):
    """Copy src into dst; files already there with the same size and a newer or equal mtime are kept."""
    copied = kept = 0
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        os.makedirs(os.path.join(dst, rel), exist_ok=True)
        for fn in files:
            s, d = os.path.join(root, fn), os.path.join(dst, rel, fn)
            if os.path.exists(d) and os.path.getsize(d) == os.path.getsize(s) and os.path.getmtime(d) >= os.path.getmtime(s):
                kept += 1
                continue
            shutil.copy2(s, d)
            copied += 1
    return copied, kept


def collision_kind(item):
    if "door" in item:
        return "rigged-door-box"
    src = (item.get("collision_report") or {}).get("source")
    return src if src in NATIVE else "guessed-boxes" if (item.get("collision_report") or {}).get("boxes") else "none"


def cmd_stage(a):
    b2 = a.exp2b
    prm = load(os.path.join(b2, "exp2_params.json"))
    plan_b = load(os.path.join(b2, "plan.json"))
    sel = load(os.path.join(a.work, "convert_input.json"))
    selrep = load(os.path.join(a.work, "selection.json"))
    man = load(os.path.join(a.work, "convert", "manifest.json"))
    bases, placed, skipped_conv = exterior.place(sel, man, prm["cell_min"], prm["cell_max"], EDID_PREFIX)
    items = {i["source"].replace("/", "\\").lower(): i for i in man["items"]}
    for b in bases:
        b["collision"] = collision_kind(items[b["key"]])
    skipped = selrep["skipped_refs"] + skipped_conv
    total = selrep["refs"] + selrep["deferred"]
    if len(placed) + len(skipped) != total:
        sys.exit(f"accounting: {len(placed)} placed + {len(skipped)} skipped != {total} exported")

    out = a.out
    os.makedirs(out, exist_ok=True)
    for rel in (prm["btd_file"], prm["mask"]):                       # both "Data/..." relative to the folder
        s, d = os.path.join(b2, *rel.split("/")), os.path.join(out, *rel.split("/"))
        os.makedirs(os.path.dirname(d), exist_ok=True)
        if not (os.path.exists(d) and sha256(d) == sha256(s)):
            shutil.copy2(s, d)
    for tree in DATA_TREES:
        c, k = copy_tree(os.path.join(a.work, "convert", tree), os.path.join(out, "Data", tree))
        print(f"Data\\{tree}: {c} copied, {k} up to date")

    objects = {"edid_prefix": EDID_PREFIX,
               "bases": [{k: b[k] for k in ("edid", "model", "door", "source", "collision") if k in b} for b in bases],
               "refs": [{k: p[k] for k in ("src", "base", "cell", "pos", "rot", "scale", "disabled")} for p in placed]}
    save(os.path.join(out, "objects.json"), objects, indent=None)
    save(os.path.join(out, "exp2_params.json"), dict(prm, objects="objects.json"))
    save(os.path.join(out, "skipped.json"), {"counts": exterior.reason_counts(skipped), "refs": skipped})

    world = World(os.path.join(out, "Data"), bases, placed, os.path.join(out, *prm["btd_file"].split("/")))
    if world.collision_errors:
        sys.exit(f"converted collision unreadable: {world.collision_errors}")
    print(f"{len(bases)} bases, {len(placed)} references, {len(world.tris):,} collision triangles")

    # entry 1: dropped from 150 m: exp2b's terrain points still clear of objects + the Red Rocket roof + large flat
    # objects; entry 3 (informational): exp2b's terrain points that now land on, or next to, an object
    e1 = plan_b[0]
    terr = terrain_points(world, e1["points"], e1["drop_z"])
    pts1 = [p for p in terr if p["kind"] == "terrain"]
    pts3 = [p for p in terr if p["kind"] != "terrain"]
    shop = world.by_src[SHOP]
    pts1 += object_point(world, shop, "redrocket_roof", "object_top", DROP_Z)
    pts1 += large_flat_objects(world, exclude={BUILDING, SHOP})
    # entry 2: the shop floor (RedRExt_Workshop02), under its ceiling, dropped from floor + FLOOR_DROP
    shop_bounds = world.bounds(world.by_src[BUILDING], local=SHOP_LOCAL)
    origin_z = placed[shop]["pos"][2]
    floor = [z for _x, _y, z in exterior.flat_samples(world.index, world.ground, shop, shop_bounds, origin_z + 1.0)]
    floor_z = statistics.median(floor)
    drop_low = round(floor_z + FLOOR_DROP, 2)
    pts2 = object_point(world, shop, "redrocket_floor", "floor", drop_low, bounds=shop_bounds,
                        need_clearance=FLOOR_DROP + PLAYER_HEIGHT, count=2)
    if len(pts2) < 2:
        sys.exit("no room for two floor points inside the shop")

    spawn = prm["spawn"]
    land_spawn = world.landing(spawn[0], spawn[1], spawn[2])
    spawn_local = [e1["spawn_local"][0], e1["spawn_local"][1], round(land_spawn["centre"], 4)]
    def entry(label, drop_z, pts):
        return {"coc": e1["coc"], "label": label, "anchor": e1["anchor"], "spawn_local": spawn_local, "drop_z": drop_z,
                "settle_ms": e1["settle_ms"], "points": [{k: p[k] for k in ("label", "x", "y", "expect")} for p in pts]}
    plan = [
        entry("terrain exp2c: exp2b terrain + the FO4 objects of cells x -20..-15, y 16..21: terrain points clear of "
              "objects, Red Rocket roof, large flat objects (dropped from 150 m)", e1["drop_z"], pts1),
        entry(f"terrain exp2c: Red Rocket shop floor (RedRExt_Workshop02), dropped from {drop_low} m = {FLOOR_DROP} m "
              f"above the floor, under the shop ceiling", drop_low, pts2),
        entry("terrain exp2c (informational): exp2b terrain points now on or within 0.6 m of a placed object "
              "(dropped from 150 m; expect = object top when covered, else the terrain)", e1["drop_z"], pts3),
    ]
    save(os.path.join(out, "plan.json"), plan)

    # the plugin: TerrainExp2 with objects.json (terrain records keep exp2b's FormIDs; the Mars plugin is rebuilt)
    if a.sf_esm:
        subprocess.run(["dotnet", "run", "--project", os.path.join(REPO, "dotnet", "TerrainExp2"), "-c", "Release", "--",
                        a.sf_esm, out], check=True)
    ids = load(os.path.join(out, "formids.json")) if os.path.exists(os.path.join(out, "formids.json")) else None
    for p in pts1 + pts2 + pts3:
        for o in (p.get("owner"), (p.get("nearby_object") or {}).get("owner")):
            if o and ids:
                o["refr"] = overlay_records.ANCHOR_LOAD_BYTE + ids["refs"][o["src"]]
    expected = {
        "experiment": "terrain_exp2c", "base": os.path.abspath(b2), "hypothesis": "FO4 position / 70 = worldspace "
        "position in metres for terrain (H) and objects alike; an object's collision then sits on the BTD as in FO4",
        "objects": {"exported": total, "placed": len(placed), "bases": len(bases),
                    "doors": sum(1 for b in bases if "door" in b), "initially_disabled": sum(p["disabled"] for p in placed),
                    "fo4_persistent_placed_temporary": sum(p["fo4_persistent"] for p in placed),
                    "enable_parent_not_translated": sum(p["enable_parent"] for p in placed),
                    "collision": {k: sum(1 for p in placed if bases[p["base"]]["collision"] == k)
                                  for k in sorted({b["collision"] for b in bases})},
                    "skipped": exterior.reason_counts(skipped)},
        "spawn": {"marker": spawn, "landing": landing_json(world, land_spawn), "spawn_local": spawn_local,
                  "exp2b_spawn_local": e1["spawn_local"]},
        "floor": {"owner": SHOP, "samples": len(floor), "median_z": round(floor_z, 4), "min_z": round(min(floor), 4),
                  "max_z": round(max(floor), 4), "drop_z": drop_low},
        "entries": [{"label": e["label"], "drop_z": e["drop_z"]} for e in plan],
        "points": [dict(p, entry=0) for p in pts1] + [dict(p, entry=1) for p in pts2] + [dict(p, entry=2) for p in pts3],
    }
    save(os.path.join(out, "expected.json"), expected)
    readme(out, prm, plan, expected)
    print(f"plan: entry 1 {len(pts1)} points, entry 2 {len(pts2)} floor points from {drop_low} m, entry 3 "
          f"{len(pts3)} informational ({[(p['label'], p['kind']) for p in pts3]}); spawn_local {spawn_local}")
    return 0


def readme(out, prm, plan, exp):
    base = os.path.splitext(prm["plugin"])[0]
    pl = [prm["plugin"], prm["mars"]["plugin"]]
    o = exp["objects"]
    lines = [
        "Terrain experiment 2c (Claude, 2026-10-11). NOT deployed. Recipe: docs/terrain/experiment2c.md",
        "(branch claude/terrain-exterior-statics). Experiment 2b (same BTD, mask, Location, Mars registration, anchor and",
        f"FormIDs) plus the real Fallout 4 objects of cells x -20..-15, y 16..21 around Red Rocket: {o['placed']:,} references",
        f"of {o['bases']:,} converted models (STAT, {o['doors']} rigged DOOR) at FO4 position / 70, in one plugin; nothing",
        "depends on FO4Port.esm. Skipped references and why: skipped.json.",
        "",
        "Install (game closed). The runner does it:",
        f"  scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> --plugins {','.join(pl)} --pack",
        f"  --pack puts every folder under Data\\ into \"{base} - Main.ba2\" (General). TEXTURES: Data\\textures\\fo4cw holds",
        "  the converted DDS textures. Starfield normally reads textures from a separate DX10 archive, so they may need",
        f"  their own \"{base} - Textures.ba2\" (Archive2, format DDS); another track adds that to the installer. If the",
        "  objects show without textures (white / grey) only that archive is missing; positions and collision do not",
        "  depend on it.",
        "By hand: build the BA2(s) with Archive2 from Data\\ (root = Data), copy them and the esm files to Starfield\\Data",
        "and add to Plugins.txt, in this order, before FO4Port.esm:  " + "  ".join("*" + p for p in pl),
        "",
        "In game (test save), console: tgm, then for each entry below: coc " + plan[0]["coc"] + ", read the anchor",
        f"(prid {plan[0]['anchor']['ref']}, getpos x/y/z -> A, offset O = A - {plan[0]['anchor']['local']}) or the arrival",
        f"(player.getpos right after coc -> S, O = S - spawn_local {plan[0]['spawn_local']}: the player lands on the pump",
        "island under the canopy, 0.117 m above the terrain), then for every point: player.setpos x <x + O.x>,",
        "player.setpos y <y + O.y>, player.setpos z <drop_z + O.z>, wait 8 s, player.getpos z -> expect + O.z (+-0.5 m).",
    ]
    for e in plan:
        lines += ["", f"  {e['label']}", f"  drop_z {e['drop_z']}"]
        for p in e["points"]:
            meta = next(q for q in exp["points"] if q["label"] == p["label"])
            owner = (meta.get("owner") or {}).get("edid", "")
            near = meta.get("nearby_object") or {}
            what = {"terrain": "terrain", "terrain_covered": "terrain point now on " + owner,
                    "terrain_near_object": f"terrain, {owner} {near.get('height', 0):.2f} m high at {near.get('distance')} m",
                    "object_top": "top of " + owner, "floor": "shop floor " + owner}[meta["kind"]]
            lines.append(f"    {p['label']:<34} x {p['x']:>10.4f}  y {p['y']:>10.4f}  -> {p['expect']:.4f}   {what}")
    lines += [
        "",
        "Files: " + ", ".join(pl) + ", Data\\Terrain (BTD), Data\\textures\\terrain\\overlaymasks (mask), Data\\meshes\\fo4cw,",
        "Data\\geometries, Data\\materials\\fo4cw, Data\\textures\\fo4cw, objects.json (what TerrainExp2 placed), formids.json,",
        "skipped.json, plan.json (runner input, worldspace's own frame), expected.json (every point with its owner and landing),",
        "offline_check.json (make_exp2c.py check). Never install together with experiment 1 or 2b (same plugin names /",
        "MarsPlanetData override). Uninstall: exp_install.py uninstall.",
    ]
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ------------------------------------------------------------------------------------------------------------- check
def fo4_ground(esm, placed, cells):
    """FO4's own terrain height (FO4 LAND, bilinear on the merged vertex grid) under every placed origin, metres."""
    x0, x1, y0, y1 = cells
    wanted = {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}
    with fo4land.Plugin(esm) as p:
        world = p.read_world("Commonwealth", cells=wanted, refs=False)
    grids = {xy: fo4land.decode_vhgt(c["vhgt"]) for xy, c in world["cells"].items() if c["vhgt"]}
    merged, _ = fo4land.merge_cells(grids, x0, y0, x1 - x0 + 1, y1 - y0 + 1)
    ox, oy = x0 * fo4land.CELL_UNITS, y0 * fo4land.CELL_UNITS
    out = []
    for q in placed:
        h = fo4land.height_at(merged, ox, oy, q["pos"][0] * 70.0, q["pos"][1] * 70.0)
        out.append(None if h is None or not math.isfinite(h) else h / 70.0)
    return out


def ref_record_check(recs, own_prefix, objects, ids):
    """Compare the plugin's REFRs with objects.json: count per cell, base, position, rotation, scale, flags."""
    by_fid = {r["fid"]: r for r in recs}
    problems, worst_pos, worst_rot = [], 0.0, 0.0
    bases = objects["bases"]
    base_fid = {b["edid"]: own_prefix | int(ids["bases"][b["edid"]], 16) for b in bases}
    for r in objects["refs"]:
        fid = own_prefix | int(ids["refs"][r["src"]], 16)
        rec = by_fid.get(fid)
        if rec is None or rec["sig"] != "REFR":
            problems.append(f"{r['src']}: no REFR {fid:08X}")
            continue
        q = fo4land.parse_ref(rec["fields"])
        if q["base"] != base_fid[bases[r["base"]]["edid"]]:
            problems.append(f"{r['src']}: base {q['base']:08X}")
        worst_pos = max(worst_pos, max(abs(u - v) for u, v in zip(q["pos"], r["pos"])))
        worst_rot = max(worst_rot, max(abs(u - v) for u, v in zip(q["rot"], r["rot"])))
        if abs(q["scale"] - r["scale"]) > 1e-4:
            problems.append(f"{r['src']}: scale {q['scale']} != {r['scale']}")
        if bool(rec["flags"] & 0x800) != bool(r["disabled"]):
            problems.append(f"{r['src']}: disabled flag")
    return problems, worst_pos, worst_rot


def walk_cells(path):
    """{cell FormID: {"grid": (x, y) or None, "refs": [REFR FormIDs]}} from the plugin's group structure (raw)."""
    buf = overlay_records.read_bytes(path)
    hsize = struct.unpack_from("<I", buf, 4)[0]
    cells, cur = {}, {"id": None}

    def walk(start, end):
        for item in fo4land.iter_items(buf, start, end):
            if item[0] == "GRUP":
                _g, off, gend, label, gtype = item
                if gtype in (6, 8, 9):
                    owner = struct.unpack("<I", label)[0] if gtype == 6 else cur["id"]
                    saved = cur["id"]
                    cur["id"] = owner
                    walk(off + 24, gend)
                    cur["id"] = saved
                else:
                    walk(off + 24, gend)
                continue
            typ, off, _flags, fid = item
            if typ == b"CELL":
                grid = next((struct.unpack_from("<ii", d) for s, d in fo4land.iter_subrecords(fo4land.record_data(buf, off))
                             if s == b"XCLC"), None)
                cells[fid] = {"grid": grid, "refs": []}
                cur["id"] = fid
            elif typ == b"REFR" and cur["id"] in cells:
                cells[cur["id"]]["refs"].append(fid)
    walk(24 + hsize, len(buf))
    return cells


def cmd_check(a):
    out, b2 = a.out, a.exp2b
    prm = load(os.path.join(out, "exp2_params.json"))
    plan = load(os.path.join(out, "plan.json"))
    exp = load(os.path.join(out, "expected.json"))
    objects = load(os.path.join(out, "objects.json"))
    ids = load(os.path.join(out, "formids.json"))
    checks, rep = [], {}

    def need(cond, what):
        checks.append([what, bool(cond)])

    # 1. exp2b parts unchanged: BTD, mask, Mars plugin bytes; terrain records of the main plugin
    for rel in (prm["btd_file"], prm["mask"], prm["mars"]["plugin"]):
        need(sha256(os.path.join(out, *rel.split("/"))) == sha256(os.path.join(b2, *rel.split("/"))),
             f"{rel} byte-identical to exp2b")
    new = overlay_records.walk_plugin(os.path.join(out, prm["plugin"]))
    old = overlay_records.walk_plugin(os.path.join(b2, prm["plugin"]))
    new_by = {r["fid"]: r for r in new["records"]}
    same = sum(1 for r in old["records"] if r["fid"] in new_by and new_by[r["fid"]]["sig"] == r["sig"]
               and new_by[r["fid"]]["flags"] == r["flags"] and new_by[r["fid"]]["fields"] == r["fields"])
    need(same == len(old["records"]), f"every exp2b record unchanged in exp2c ({same}/{len(old['records'])})")
    need(new["masters"] == ["Starfield.esm"], f"masters {new['masters']}")

    # 2. the terrain side through the exp2b check (BTD points, WRLD/LCTN/SFBK, anchor, Mars entry, mask) with the
    #    uncovered terrain points and exp2b's spawn (ground under the COC marker)
    b_plan = load(os.path.join(b2, "plan.json"))
    terr = [p for p in exp["points"] if p["kind"] == "terrain"]
    tplan = [dict(b_plan[0], points=[{k: p[k] for k in ("label", "x", "y", "expect")} for p in terr])]
    ok, trep = overlay_records.check_staging(out, prm, tplan, overlay_records.vanilla_mars_count(a.sf_data))
    for what, good in trep["checks"]:
        need(good, "exp2b check: " + what)
    rep["terrain"] = {k: trep[k] for k in ("points", "plugin", "mars", "mask", "btd") if k in trep}

    # 3. object records: STAT / DOOR, models on disk, REFRs per cell, positions
    own = len(new["masters"]) << 24
    recs = new["records"]
    stats = [r for r in recs if r["sig"] in ("STAT", "DOOR")]
    need(len(stats) == len(objects["bases"]), f"{len(stats)} STAT/DOOR = {len(objects['bases'])} bases")
    missing = []
    for r in stats:
        model = fo4land.zstring(overlay_records.field(r, "MODL", b""))
        if not os.path.isfile(os.path.join(out, "Data", "meshes", model)):
            missing.append(model)
    need(not missing, f"every base model is in Data\\meshes ({len(missing)} missing)")
    deps = dependency_check(os.path.join(out, "Data"), [b["model"] for b in objects["bases"]],
                            vanilla=vanilla_textures(a.sf_data))
    need(not deps["missing"], f"every geometry / material / texture the models name exists: ours in Data, the rest in "
         f"the Starfield texture archives ({deps['missing_count']} missing, {deps['counts']})")
    problems, worst_pos, worst_rot = ref_record_check(recs, own, objects, ids)
    need(not problems, f"every REFR matches objects.json ({len(problems)} problems)")
    need(worst_pos < 1e-3 and worst_rot < 1e-5, f"REFR position / rotation as written (worst {worst_pos:.2e} m, {worst_rot:.2e} rad)")
    cells = walk_cells(os.path.join(out, prm["plugin"]))
    per_cell = {}
    for r in objects["refs"]:
        per_cell[tuple(r["cell"])] = per_cell.get(tuple(r["cell"]), 0) + 1
    got = {c["grid"]: len(c["refs"]) for c in cells.values() if c["grid"] is not None and c["refs"]}
    spawn_cell = tuple(prm["spawn_cell"])
    want = dict(per_cell)
    want[spawn_cell] = want.get(spawn_cell, 0) + 1                    # + the COC marker
    need(got == want, f"REFRs per exterior cell match ({len(got)} cells with references)")
    refrs = sum(1 for r in recs if r["sig"] == "REFR")
    need(refrs == len(objects["refs"]) + 2, f"{refrs} REFR = {len(objects['refs'])} objects + COC marker + anchor")
    rep["plugin"] = {"bytes": new["bytes"], "masters": new["masters"],
                     "records": {s: sum(1 for r in recs if r["sig"] == s) for s in sorted({r["sig"] for r in recs})},
                     "cells_with_refs": len(got), "refs_per_cell_max": max(got.values()), "ref_problems": problems[:20],
                     "worst_pos_m": worst_pos, "worst_rot_rad": worst_rot, "dependencies": deps["counts"]}

    # 4. object z - terrain z under every placed origin (BTD; with --fo4 also FO4's own LAND)
    sel = load(os.path.join(a.work, "convert_input.json"))
    man = load(os.path.join(a.work, "convert", "manifest.json"))
    bases, placed, _ = exterior.place(sel, man, prm["cell_min"], prm["cell_max"], EDID_PREFIX)
    items = {i["source"].replace("/", "\\").lower(): i for i in man["items"]}
    for b in bases:
        b["collision"] = collision_kind(items[b["key"]])
    world = World(os.path.join(out, "Data"), bases, placed, os.path.join(out, *prm["btd_file"].split("/")))
    btd_dz = [p["pos"][2] - world.ground(p["pos"][0], p["pos"][1]) for p in placed]
    fo4_dz = None
    if a.fo4:
        g4 = fo4_ground(a.fo4, placed, (-21, -14, 15, 22))
        fo4_dz = [None if g is None else p["pos"][2] - g for p, g in zip(placed, g4)]
    k = world.by_src[BUILDING]
    gb = world.ground_all(*placed[k]["pos"][:2])
    building = {"src": BUILDING, "pos": placed[k]["pos"], "btd_ground": {m: round(v, 5) for m, v in gb.items()},
                "object_minus_btd_mm": {m: round((placed[k]["pos"][2] - v) * 1000, 2) for m, v in gb.items()},
                "object_minus_fo4_land_mm": None if fo4_dz is None else round(fo4_dz[k] * 1000, 2)}
    need(max(abs(v) for v in building["object_minus_btd_mm"].values()) <= world.step * 1000,
         f"Red Rocket building z - BTD ground within one quantisation step ({building['object_minus_btd_mm']} mm)")
    if fo4_dz is not None:
        need(abs(fo4_dz[k]) < 1e-3, f"Red Rocket building z - FO4 LAND ground = {fo4_dz[k] * 1000:.2f} mm (FO4 says 0)")
        idx = [i for i, f in enumerate(fo4_dz) if f is not None]
        diff = np.array([btd_dz[i] - fo4_dz[i] for i in idx])
        worst = sorted(range(len(idx)), key=lambda j: -abs(diff[j]))[:5]
        rep["fo4_vs_btd_under_objects"] = {
            "objects": len(idx), "median_abs_mm": round(float(np.median(np.abs(diff))) * 1000, 2),
            "p95_abs_mm": round(float(np.percentile(np.abs(diff), 95)) * 1000, 2),
            "p99_abs_mm": round(float(np.percentile(np.abs(diff), 99)) * 1000, 2),
            "max_abs_mm": round(float(np.abs(diff).max()) * 1000, 2),
            "within_1cm": int((np.abs(diff) <= 0.01).sum()), "within_5cm": int((np.abs(diff) <= 0.05).sum()),
            "worst": [{"src": placed[idx[j]]["src"], "edid": bases[placed[idx[j]]["base"]]["edid"],
                       "pos": placed[idx[j]]["pos"], "btd_minus_fo4_mm": round(float(diff[j]) * 1000, 1)} for j in worst]}
    arr = np.array(btd_dz)
    rep["object_minus_btd"] = {"objects": len(arr), "building": building,
                               "histogram_m": {f"{lo}..{hi}": int(((arr >= lo) & (arr < hi)).sum())
                                               for lo, hi in ((-50, -1), (-1, -0.25), (-0.25, -0.05), (-0.05, 0.05),
                                                              (0.05, 0.25), (0.25, 1), (1, 50))},
                               "by_edid": {placed[i]["src"]: {"edid": bases[placed[i]["base"]]["edid"],
                                                              "btd_dz": round(btd_dz[i], 4),
                                                              "fo4_dz": None if fo4_dz is None or fo4_dz[i] is None else round(fo4_dz[i], 4)}
                                           for i in sorted({world.by_src[p["owner"]["src"]] for p in exp["points"] if p.get("owner")})}}

    # 5. every plan point re-derived from the converted collision + BTD (independent of stage's search)
    pts = []
    for e, entry in enumerate(plan):
        for p in entry["points"]:
            meta = next(q for q in exp["points"] if q["label"] == p["label"])
            land = world.landing(p["x"], p["y"], entry["drop_z"])
            err = abs(land["centre"] - p["expect"])
            if meta["kind"] in ("terrain", "terrain_near_object"):
                hs = world.ground_all(p["x"], p["y"])
                err = max(abs(v - p["expect"]) for v in hs.values())
                near = exterior.nearby_object(world.index.top, world.ground, p["x"], p["y"], entry["drop_z"])
                need(not land["on_object"] and err <= world.step, f"{p['label']}: still terrain, decoded within one step")
                need((near is None) == (meta["kind"] == "terrain"), f"{p['label']}: " + (
                    "no object within 0.6 m" if near is None else
                    f"object {world.placed[near['owner']]['src']} {near['height']:.2f} m high at {near['distance']} m"))
            else:
                owner = world.by_src[meta["owner"]["src"]]
                need(land["on_object"] and land["owner"] == owner and err < 1e-3,
                     f"{p['label']}: lands on {meta['owner']['edid']} at {p['expect']} (error {err * 1000:.2f} mm)")
                if meta["kind"] in ("object_top", "floor"):
                    need(land["all_on_object"] and land["spread"] <= 0.02, f"{p['label']}: level, whole disc on the object")
                if meta["kind"] == "floor":
                    free = exterior.clearance(world.index, p["x"], p["y"], land["centre"])
                    need(entry["drop_z"] - p["expect"] >= 0.5 and free >= entry["drop_z"] - p["expect"] + PLAYER_HEIGHT,
                         f"{p['label']}: drop height {entry['drop_z'] - p['expect']:.2f} m, {free:.2f} m free above the floor")
            if entry["drop_z"] >= DROP_Z:                              # the drop starts above everything at the point
                tops = [s[0][0] for dx, dy in exterior.disc_offsets(1.0) if (s := world.index.surfaces(p["x"] + dx, p["y"] + dy))]
                need(entry["drop_z"] >= max(tops + [p["expect"]]) + 10, f"{p['label']}: drop_z {entry['drop_z']} >= "
                     f"every collision top within 1 m + 10 m ({max(tops + [p['expect']]):.2f})")
            pts.append({"entry": e, "label": p["label"], "kind": meta["kind"], "expect": p["expect"],
                        "landing": landing_json(world, land), "error_mm": round(err * 1000, 3)})
    land = world.landing(prm["spawn"][0], prm["spawn"][1], prm["spawn"][2])
    need(abs(land["centre"] - plan[0]["spawn_local"][2]) < 1e-3, f"spawn_local z = what the player lands on under the COC marker")
    need(exterior.clearance(world.index, prm["spawn"][0], prm["spawn"][1], land["centre"]) >= PLAYER_HEIGHT,
         "room for the player above the arrival")
    rep["points"] = pts
    rep["checks"] = checks
    rep["pass"] = all(c[1] for c in checks)
    save(os.path.join(out, "offline_check.json"), rep)
    for what, good in checks:
        print(("  ok   " if good else "  FAIL ") + what)
    for p in pts:
        print(f"  {p['label']:<36} {p['kind']:<16} expect {p['expect']:9.4f}  landing {p['landing']['centre']:9.4f}  "
              f"spread {p['landing']['spread']:.3f}  error {p['error_mm']:.3f} mm")
    print(json.dumps({k: rep[k] for k in ("plugin", "object_minus_btd", "fo4_vs_btd_under_objects") if k in rep}, indent=1)[:6000])
    print("CHECK", "PASS" if rep["pass"] else "FAIL")
    return 0 if rep["pass"] else 1


def dependency_check(data, models, prefix="fo4cw", vanilla=None):
    """Every geometry a converted NIF's BSGeometry blocks name (Data\\geometries\\<path>.mesh), every material its
    shader properties name (Data\\materials\\...) and every texture those .mat files name exists: our own files
    (textures\\<prefix>\\...) under Data, the rest (vanilla parents / textures the template keeps) in `vanilla`, a set
    of lower-case archive names from the Starfield texture archives (None: not checked, counted as unverified)."""
    from fo4sf import nif as nifmod
    from fo4sf import sfnif
    seen_mats, seen_tex, missing = set(), set(), []
    counts = {"nifs": 0, "meshes": 0, "materials": 0, "textures_own": 0, "textures_vanilla": 0, "vanilla_unverified": 0}
    for m in sorted(set(models)):
        with open(os.path.join(data, "meshes", m), "rb") as f:
            n = nifmod.parse(f.read())
        counts["nifs"] += 1
        for i in range(len(n.blocks)):
            if n.type_of(i) != "BSGeometry":
                continue
            for ref in sfnif.parse_bsgeometry(n.blocks[i]).meshes:
                if ref is None:
                    continue
                counts["meshes"] += 1
                rel = ref.path.decode("latin-1").replace("/", "\\") + ".mesh"
                if not os.path.isfile(os.path.join(data, "geometries", rel)):
                    missing.append("geometries\\" + rel)
        for path in nifmod.referenced_paths(n):
            low = path.replace("/", "\\").lower()
            if not low.endswith(".mat") or low in seen_mats:
                continue
            seen_mats.add(low)
            counts["materials"] += 1
            mp = os.path.join(data, low)
            if not os.path.isfile(mp):
                missing.append(path)
                continue
            with open(mp, encoding="utf-8") as f:
                for tex in _json_strings(json.load(f)):
                    rel = tex.replace("/", "\\").lower()
                    if not rel.endswith(".dds") or rel in seen_tex:
                        continue
                    seen_tex.add(rel)
                    rel = rel[len("data\\"):] if rel.startswith("data\\") else rel
                    rel = rel if rel.startswith("textures\\") else "textures\\" + rel
                    if rel.startswith(f"textures\\{prefix}\\"):
                        counts["textures_own"] += 1
                        if not os.path.isfile(os.path.join(data, rel)):
                            missing.append(rel)
                    else:
                        counts["textures_vanilla"] += 1
                        if vanilla is None:
                            counts["vanilla_unverified"] += 1
                        elif rel.replace("\\", "/") not in vanilla:
                            missing.append(rel)
    return {"counts": counts, "missing": sorted(set(missing))[:50], "missing_count": len(set(missing))}


def _json_strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from _json_strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from _json_strings(x)


def vanilla_textures(sf_data):
    """Lower-case names (forward slashes) in the Starfield texture archives, or None without a Data folder."""
    if not sf_data or not os.path.isdir(sf_data):
        return None
    from fo4sf import ba2
    names = set()
    for fn in sorted(os.listdir(sf_data)):
        if fn.lower().startswith("starfield - textures") and fn.lower().endswith(".ba2"):
            names.update(n.replace("\\", "/").lower() for n in ba2.Ba2(os.path.join(sf_data, fn)).names)
    return names


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select")
    s.add_argument("--export", required=True)
    s.add_argument("--work", required=True)
    for name in ("stage", "check"):
        s = sub.add_parser(name)
        s.add_argument("--work", required=True)
        s.add_argument("--exp2b", required=True)
        s.add_argument("--out", required=True)
        if name == "stage":
            s.add_argument("--sf-esm", default="", help="Starfield.esm: build the plugin with dotnet/TerrainExp2")
        else:
            s.add_argument("--sf-data", default="", help="Starfield Data (vanilla Mars entry count)")
            s.add_argument("--fo4", default="", help="Fallout4.esm: also compare against FO4's own terrain under each object")
    a = ap.parse_args()
    return {"select": cmd_select, "stage": cmd_stage, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
