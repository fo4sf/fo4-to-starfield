"""Terrain experiment 2d: exp2c (the FO4 objects around Red Rocket on the native terrain) + the Fallout 4 navmesh of
the same cells, converted (docs/actors/navmesh-conversion.md), and the N1 NPC navigation plans that tell world,
navigation and actor failures apart.

    python scripts/terrain/make_exp2d.py stage --exp2c <terrain_exp2c> --out <terrain_exp2d> --fo4 <Fallout4.esm>
           --sf-esm <Starfield.esm>
    python scripts/terrain/make_exp2d.py check --exp2c <terrain_exp2c> --out <terrain_exp2d> --fo4 <Fallout4.esm>
           [--fo4-data <FO4 Data>]
    python scripts/terrain/make_exp2d.py npc --exp2b2 <terrain_exp2b2> --exp2d <terrain_exp2d> --staging-root <dir>
           --queue-root <dir>

stage  copies exp2c (Data tree, objects, params), reads the NAVM records of Fallout 4 cells x -20..-15, y 16..21,
       cuts every navmesh at the 100 m Starfield cell lines (src/fo4sf/navmesh.py convert), writes navmesh.json and
       runs dotnet/TerrainExp2 (objects + navmesh: exp2c's FormIDs unchanged, NAVM after them, a NAVI override with one
       NVMI per new navmesh). Then it picks the NPC points on open terrain over the converted navmesh near Red Rocket
       (same navmesh pair, cross-cell pair), adds them as the first runner entry (the world check of N1c) and writes
       expected.json, navmesh_report.json and README.txt.
check  raw-walks the plugin: every exp2c record unchanged, the Mars plugin and the base Data files byte-identical;
       every NAVM parsed back (exact layout) and byte-compared with the Python reference writer; the NAVI override (one
       NVMI per NAVM, exact layout); edge-link symmetry, no dangling link, cell-line links exact, Fallout 4 portals as
       close as Fallout 4 had them; every navmesh vertex against the decoded BTD and the converted collision (and, with
       --fo4, Fallout 4's own LAND for the ones on neither); the NPC points. Writes offline_check_navmesh.json.
npc    stages the N1 plans (npc_nav_n1a / n1b / n1c) and the world-check copy of exp2b2 the N1a/N1b tests require.
Everything written stays outside the repo (derived game data).
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "src"))
from fo4sf import exterior, fo4land  # noqa: E402
from fo4sf import navmesh as nm  # noqa: E402
from fo4sf import terrain_grid as tg  # noqa: E402

sys.path.insert(0, HERE)
import make_exp2c as c2  # noqa: E402
import overlay_records  # noqa: E402

FO4_CELLS = (-20, 16, -15, 21)                  # x0, y0, x1, y1: exp2c's object cells
NPC = "002B211C"                                # EncCitizen01Template, as N0 / N1 (PR #68)
NPC_CELL = (-10, 11)                            # the Starfield cell of Red Rocket, FO4 cell (-17, 19) lies in it
CROSS_CELLS = ((-11, 11), (-10, 10))            # neighbours for the cross-cell pair
NAV_ZTOL = 0.6                                  # m: a navmesh triangle this close to the terrain is "on" it
SURFACE_TOL = 0.5                               # m: a navmesh vertex this close to the BTD or a collision surface
POINT_CLEAR = 1.5                               # m: no collision above the terrain this close to an NPC point
PAIR_RANGE = (15.0, 22.0)                       # m between A and B (N0 uses 19.1 m)
CROSS_RANGE = (15.0, 28.0)
METHODS = ("ptr_player", "cf_pathto_player", "follow_player")
READS = [0, 5, 15, 30, 60]


def load(path):
    return c2.load(path)


def save(path, value, indent=1):
    c2.save(path, value, indent)


# ------------------------------------------------------------------------------------------------------------- world
def world_from_objects(out, prm):
    """make_exp2c.World from the staged objects.json (bases with models, references as placed)."""
    objects = load(os.path.join(out, "objects.json"))
    return c2.World(os.path.join(out, "Data"), objects["bases"], objects["refs"],
                    os.path.join(out, *prm["btd_file"].split("/"))), objects


def read_plugin_navmeshes(path):
    """({FormID: Nvnm}, {FormID: Nvmi}, {FormID: raw NVNM bytes}, record info) of a plugin, raw."""
    rec = overlay_records.walk_plugin(path)
    navs, raw, subs, nvmis, navi = {}, {}, {}, {}, []
    for r in rec["records"]:
        if r["sig"] == "NAVM":
            subs[r["fid"]] = [(s.decode(), len(d)) for s, d in r["fields"]]
            for s, d in r["fields"]:
                if s == b"NVNM":
                    raw[r["fid"]] = bytes(d)
                    navs[r["fid"]] = nm.parse(d)
        elif r["sig"] == "NAVI":
            navi.append(r)
            for s, d in r["fields"]:
                if s == b"NVMI":
                    e = nm.parse_nvmi(d)
                    nvmis[e.navmesh] = e
    return navs, nvmis, raw, {"subrecords": subs, "navi": navi, "walk": rec}


def door_sources(objects):
    """{Fallout 4 REFR FormID: source key} of the converted references whose base is a rigged DOOR."""
    out = {}
    for r in objects["refs"]:
        if "door" in objects["bases"][r["base"]]:
            out[int(r["src"].split(":")[0], 16)] = r["src"]
    return out


def fo4_navmeshes(fo4_esm, cells=FO4_CELLS):
    x0, y0, x1, y1 = cells
    want = {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}
    with fo4land.Plugin(fo4_esm) as p:
        raw = nm.world_navmeshes(p, "Commonwealth", want)
    return [(fid, nm.parse(b)) for _cell, fid, _fl, b in raw], {fid: cell for cell, fid, _fl, _b in raw}


# ------------------------------------------------------------------------------------------------------------- points
def nav_at(navs, x, y, g, only=None):
    """(navmesh, tri, z) of the converted triangle under (x, y) nearest the terrain g within NAV_ZTOL, or None."""
    sub = navs if only is None else {k: navs[k] for k in only}
    hits = nm.locate(sub, x, y, z=g, ztol=NAV_ZTOL)
    return None if not hits else hits[0][1:]


def point_ok(world, navs, cell_navs, x, y):
    """An NPC point: level open terrain with nothing above it within POINT_CLEAR (make_exp2c.reference_ok: the player
    and the actor land on the terrain, in exp2b2 and in exp2d alike), on a converted triangle within NAV_ZTOL of the
    terrain, and the same navmesh under 8 points 1 m and 2 m around it. Returns (ground, navmesh, tri) or None."""
    if world.index.surfaces(x, y):
        return None
    g = world.ground(x, y)
    hit = nav_at(navs, x, y, g, cell_navs)
    if hit is None:
        return None
    fid, tri, _z = hit
    for r in (1.0, 2.0):
        for k in range(8):
            px, py = x + r * math.cos(k * math.pi / 4), y + r * math.sin(k * math.pi / 4)
            h = nav_at(navs, px, py, world.ground(px, py), cell_navs)
            if h is None or h[0] != fid:
                return None
    if c2.reference_ok(world, x, y, clear=POINT_CLEAR) is None:
        return None
    return g, fid, tri


def line_clear(world, navs, a, b, step=0.5):
    """Every sample of the straight line a -> b on a converted triangle near the terrain and under no collision."""
    n = max(1, int(math.dist(a[:2], b[:2]) / step))
    for i in range(n + 1):
        x, y = a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n
        if world.index.surfaces(x, y) or nav_at(navs, x, y, world.ground(x, y)) is None:
            return False
    return True


def candidates(world, navs, cell, centre, radius, step=1.0, margin=3.0):
    cx0, cy0 = cell[0] * 100.0, cell[1] * 100.0
    cell_navs = [f for f, m in navs.items() if m.grid == tuple(cell)]
    out = []
    xs = np.arange(cx0 + margin, cx0 + 100.0 - margin + 1e-9, step)
    ys = np.arange(cy0 + margin, cy0 + 100.0 - margin + 1e-9, step)
    for x in xs:
        for y in ys:
            if math.hypot(x - centre[0], y - centre[1]) > radius:
                continue
            ok = point_ok(world, navs, cell_navs, float(x), float(y))
            if ok:
                out.append((round(float(x), 4), round(float(y), 4)) + ok)
    return out


def pick_points(world, navs, arrival, radius=45.0):
    """The NPC points: pair 1 (A, B) on one converted navmesh in Red Rocket's cell, PAIR_RANGE apart, the straight line
    between them clear and on navmesh; pair 2 (A2, B2) across a cell line (two navmeshes joined by a cell-line link),
    CROSS_RANGE apart. Closest to the arrival first."""
    t0 = time.time()
    home = candidates(world, navs, NPC_CELL, arrival, radius)
    near = {c: candidates(world, navs, c, arrival, radius + 20.0) for c in CROSS_CELLS}
    rep = {"candidates": {str(NPC_CELL): len(home), **{str(c): len(v) for c, v in near.items()}}}
    best = None
    for a in sorted(home, key=lambda p: math.hypot(p[0] - arrival[0], p[1] - arrival[1])):
        for b in home:
            d = math.dist(a[:2], b[:2])
            if not (PAIR_RANGE[0] <= d <= PAIR_RANGE[1]) or b[3] != a[3]:
                continue
            score = math.hypot(a[0] - arrival[0], a[1] - arrival[1]) + abs(d - 19.0)
            if best is not None and score >= best[0]:
                continue
            if not line_clear(world, navs, a, b) or nm.triangle_path(navs, (a[3], a[4]), (b[3], b[4])) is None:
                continue
            best = (score, a, b)
        if best is not None and math.hypot(a[0] - arrival[0], a[1] - arrival[1]) > best[0]:
            break
    if best is None:
        sys.exit("no NPC pair on one converted navmesh near Red Rocket")
    cross = None
    others = [p for v in near.values() for p in v]
    for a in sorted(home, key=lambda p: math.hypot(p[0] - arrival[0], p[1] - arrival[1])):
        for b in others:
            d = math.dist(a[:2], b[:2])
            if not (CROSS_RANGE[0] <= d <= CROSS_RANGE[1]):
                continue
            score = math.hypot(a[0] - arrival[0], a[1] - arrival[1]) + abs(d - 20.0)
            if cross is not None and score >= cross[0]:
                continue
            if not line_clear(world, navs, a, b):
                continue
            path = nm.triangle_path(navs, (a[3], a[4]), (b[3], b[4]))
            if path is None or len({f for f, _ in path}) < 2:
                continue
            cross = (score, a, b, path)
        if cross is not None and math.hypot(a[0] - arrival[0], a[1] - arrival[1]) > cross[0]:
            break
    if cross is None:
        sys.exit("no cross-cell NPC pair near Red Rocket")
    rep["seconds"] = round(time.time() - t0, 1)

    def pt(label, p):
        return {"label": label, "x": p[0], "y": p[1], "expect": round(p[2], 4), "navmesh": f"{p[3]:08X}", "tri": p[4]}
    path = nm.triangle_path(navs, (best[1][3], best[1][4]), (best[2][3], best[2][4]))
    return {"A": pt("npc_a", best[1]), "B": pt("npc_b", best[2]), "A2": pt("npc_a2", cross[1]),
            "B2": pt("npc_b2", cross[2]),
            "pair": {"distance": round(math.dist(best[1][:2], best[2][:2]), 3), "triangles_on_path": len(path),
                     "navmeshes_on_path": sorted({f"{f:08X}" for f, _ in path})},
            "cross": {"distance": round(math.dist(cross[1][:2], cross[2][:2]), 3), "triangles_on_path": len(cross[3]),
                      "navmeshes_on_path": sorted({f"{f:08X}" for f, _ in cross[3]})},
            "search": rep}


# ------------------------------------------------------------------------------------------------------------- stage
def cmd_stage(a):
    t0 = time.time()
    src, out = a.exp2c, a.out
    prm = load(os.path.join(src, "exp2_params.json"))
    os.makedirs(out, exist_ok=True)
    c, k = c2.copy_tree(os.path.join(src, "Data"), os.path.join(out, "Data"))
    print(f"Data: {c} copied, {k} up to date")
    for fn in ("objects.json", "skipped.json"):
        shutil.copy2(os.path.join(src, fn), os.path.join(out, fn))
    objects = load(os.path.join(out, "objects.json"))

    fo4, cell_of = fo4_navmeshes(a.fo4)
    doors = door_sources(objects)
    pieces, rep = nm.convert(fo4, door_refs=doors)
    rep["fo4_cells"] = {"x": [FO4_CELLS[0], FO4_CELLS[2]], "y": [FO4_CELLS[1], FO4_CELLS[3]]}
    rep["fo4_navmesh_ids"] = sorted(f"{f:08X}" for f, _ in fo4)
    rep["fo4_door_triangles"] = [{"navmesh": f"{f:08X}", "cell": list(cell_of[f]), "tri": int(d["tri"]),
                                  "door": f"{int(d['door']):08X}",
                                  "converted": f"{int(d['door']) & 0xFFFFFF:06X}:Fallout4.esm" in
                                  {s for s in doors.values()}}
                                 for f, m in fo4 for d in m.doors]
    rep["fo4_portal_gap_max_m"] = round(fo4_portal_gap(fo4), 4)
    save(os.path.join(out, "navmesh.json"), nm.export(pieces), indent=None)
    save(os.path.join(out, "exp2_params.json"), dict(prm, navmesh="navmesh.json"))
    print(f"converted {rep['fo4_navmeshes']} navmeshes ({rep['fo4_triangles']:,} triangles) into {rep['pieces']} "
          f"Starfield navmeshes ({rep['triangles']:,} triangles), links {rep['links']}, dropped {rep['dropped']}")
    if a.sf_esm:
        subprocess.run(["dotnet", "run", "--project", os.path.join(REPO, "dotnet", "TerrainExp2"), "-c", "Release",
                        "--", a.sf_esm, out], check=True)
    ids = load(os.path.join(out, "formids.json"))
    navs, nvmis, _raw, _info = read_plugin_navmeshes(os.path.join(out, prm["plugin"]))

    world, _ = world_from_objects(out, prm)
    exp_c = load(os.path.join(src, "expected.json"))
    plan_c = load(os.path.join(src, "plan.json"))
    spawn_local = exp_c["spawn"]["spawn_local"]
    pts = pick_points(world, navs, spawn_local[:2])
    ref = exp_c["reference"]
    entry = {k: v for k, v in plan_c[0].items() if k not in ("label", "points")}
    points = [{"label": ref["label"], "x": ref["x"], "y": ref["y"], "expect": ref["expect"]}] + \
             [{k: pts[n][k] for k in ("label", "x", "y", "expect")} for n in ("A", "B", "A2", "B2")]
    start = (spawn_local[0], spawn_local[1], spawn_local[2])
    points = c2.order_points(world, start, points, entry["drop_z"])
    entry.update(label="terrain exp2d 1/5 (world check of the N1 NPC points): A and B (same navmesh), A2 and B2 "
                       "(across a cell line), open terrain over the converted navmesh, relative to "
                       f"{ref['label']}", points=points)
    plan = [entry] + plan_c                      # first: what N1c requires (0000_...), then exp2c's four entries
    save(os.path.join(out, "plan.json"), plan)
    paths, clear = c2.path_report(world, start, points, entry["drop_z"])
    expected = dict(exp_c, experiment="terrain_exp2d", base=os.path.abspath(src),
                    hypothesis="Fallout 4's navmesh, cut into Starfield's 100 m cells at FO4 position / 70, lets a "
                               "vanilla NPC path on the native terrain where the same NPC does not path without it",
                    navmesh={k: rep[k] for k in ("fo4_navmeshes", "fo4_triangles", "pieces", "triangles", "links",
                                                 "dropped", "kept")},
                    npc_points=pts, npc_entry={"teleports_clear": clear, "teleports": paths},
                    formids={"navmeshes": len(ids.get("navmeshes", [])), "first": (ids.get("navmeshes") or [None])[0],
                             "last": (ids.get("navmeshes") or [None])[-1]})
    save(os.path.join(out, "expected.json"), expected)
    save(os.path.join(out, "navmesh_report.json"), rep)
    readme(out, prm, plan, expected, rep)
    print(f"NPC points: {json.dumps({n: [pts[n]['x'], pts[n]['y'], pts[n]['expect'], pts[n]['navmesh']] for n in ('A', 'B', 'A2', 'B2')})}")
    print(f"pair {pts['pair']}, cross {pts['cross']}; stage {time.time() - t0:.0f} s")
    return 0


def fo4_portal_gap(fo4):
    """The largest gap (m) between the two edges of a Fallout 4 type-0 portal among these navmeshes: what the
    converted portal links inherit."""
    by = dict(fo4)
    worst = 0.0
    for fid, m in fo4:
        t = m.triangles
        for ti in range(len(t)):
            fl = int(t["flags"][ti])
            for k in range(3):
                if not fl & nm.EDGE_LINK_BITS[k]:
                    continue
                L = m.links[int(t["e"][ti][k])]
                o = by.get(int(L["navmesh"]))
                if o is None or int(L["type"]) != 0:
                    continue
                v = t["v"][ti]
                a = m.vertices[int(v[k])] / 70.0, m.vertices[int(v[(k + 1) % 3])] / 70.0
                w = o.triangles["v"][int(L["tri"])]
                kk = int(L["edge"])
                b = o.vertices[int(w[kk])] / 70.0, o.vertices[int(w[(kk + 1) % 3])] / 70.0
                worst = max(worst, nm.segment_gap(a, b))
    return worst


def readme(out, prm, plan, exp, rep):
    pts = exp["npc_points"]
    pl = [prm["plugin"], prm["mars"]["plugin"]]
    lines = [
        "Terrain experiment 2d (Claude, 2026-10-11). NOT deployed, NOT queued. Recipe: docs/actors/navmesh-conversion.md",
        "(branch claude/terrain-navmesh). Base: C:\\Modding\\staging\\terrain_exp2c (exp2b2's terrain + 8,069 FO4 objects;",
        "same plugin names, FormIDs, anchor, COC marker and Mars plugin) plus the Fallout 4 navmesh of cells x -20..-15,",
        f"y 16..21 converted: {rep['fo4_navmeshes']} FO4 navmeshes ({rep['fo4_triangles']:,} triangles) cut at the 100 m",
        f"Starfield cell lines into {rep['pieces']} NAVM records ({rep['triangles']:,} triangles) at FO4 position / 70,",
        f"{rep['links']['cell_line']} cell-line and {rep['links']['fo4_portal']} FO4-portal edge-link pairs, and a NAVI override",
        "(000FF1:Starfield.esm) that holds one NVMI per new navmesh only (as every official plugin with navmesh does).",
        "What was dropped and why: navmesh_report.json.",
        "",
        "Install (game closed). The runner does it:",
        f"  scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> --plugins {','.join(pl)} --pack",
        "  (BTDs stored uncompressed: Archive2 -compression=None, as for exp2b2 / exp2c.)",
        "By hand: build the BA2 with Archive2 from Data\\ (root = Data), copy it and the esm files to Starfield\\Data and",
        "add to Plugins.txt, in this order, before FO4Port.esm:  " + "  ".join("*" + p for p in pl),
        "Never together with experiment 1, 2b or 2c (same plugin names / MarsPlanetData override).",
        "",
        "Runner entries: plan.json = entry 1, the world check of the N1 NPC points (player drops at A, B, A2, B2 and the",
        "Z reference; heights relative to zref_ground; N1c requires its PASS), then exp2c's four entries unchanged (objects",
        "and terrain with the navmesh present). Plan with --fresh.",
        "",
        "In game by hand (test save, console): tgm; coc FO4CW_RedRocketSpawn; read the arrival (player.getpos, settled)",
        f"-> S; offset O = S - {exp['spawn']['spawn_local']} (the pump island under the canopy). Then:",
        "  tnm                                  (ToggleNavMesh: the converted navmesh should show around Red Rocket)",
        f"  player.setpos x <{pts['A']['x']} + O.x>, y <{pts['A']['y']} + O.y>, z <{pts['A']['expect'] + 30:.2f} + O.z>   (A, wait 7 s)",
        f"  player.placeatme {NPC} 1; plr; GetIsID {NPC} (must print 1)",
        f"  player.setpos x <{pts['B']['x']} + O.x>, y <{pts['B']['y']} + O.y>, z <{pts['B']['expect'] + 30:.2f} + O.z>   (B, wait 7 s)",
        "  (console selection still the actor) PathToRef player; close the console; it should walk to you within 30 s.",
        "  Afterwards: disable; markfordelete.",
        "",
        f"NPC points (worldspace frame, metres; actor EncCitizen01Template {NPC}):",
    ]
    for n in ("A", "B", "A2", "B2"):
        p = pts[n]
        lines.append(f"  {p['label']:<8} x {p['x']:>10.4f}  y {p['y']:>10.4f}  terrain {p['expect']:.4f}  navmesh {p['navmesh']}")
    lines += [
        f"  A -> B {pts['pair']['distance']} m on one navmesh ({pts['pair']['navmeshes_on_path']});",
        f"  A2 -> B2 {pts['cross']['distance']} m across a cell line ({pts['cross']['navmeshes_on_path']}).",
        "",
        "Files: the two plugins, Data\\ (BTD, mask, converted models as exp2c), navmesh.json (what TerrainExp2 wrote),",
        "navmesh_report.json (conversion counts, dropped items), objects.json, skipped.json, formids.json (+ the NAVM",
        "FormIDs), plan.json, expected.json, exp2_params.json, offline_check_navmesh.json (make_exp2d.py check).",
        "Uninstall: exp_install.py uninstall.",
    ]
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ------------------------------------------------------------------------------------------------------------- check
def surface_report(world, navs, fo4_ground=None):
    """Every navmesh vertex against the walkable surfaces under it: the decoded BTD (bilinear) and every converted
    collision surface at its x, y. d = the smallest |z - surface|. With fo4_ground(x, y) (Fallout 4's LAND, metres),
    a vertex on neither is classified: FO4's own navmesh is off FO4's terrain there too (it stands on an object we
    did not convert, or floats), or not (a conversion problem)."""
    ds, worst, cls = [], [], {"on_terrain": 0, "on_object": 0, "off": 0, "off_fo4_terrain_too": 0,
                              "off_on_fo4_terrain": 0}
    tri_ok = tri_all = 0
    for fid, m in navs.items():
        vd = np.empty(len(m.vertices))
        for i, (x, y, z) in enumerate(m.vertices):
            g = world.ground(x, y)
            best, what = abs(z - g), "terrain"
            for s, _o in world.index.surfaces(x, y):
                if abs(z - s) < best:
                    best, what = abs(z - s), "object"
            vd[i] = best
            if best <= SURFACE_TOL:
                cls["on_" + what] += 1
            else:
                cls["off"] += 1
                if fo4_ground is not None:
                    h = fo4_ground(x, y)
                    if h is not None and abs(z - h) <= SURFACE_TOL:
                        cls["off_on_fo4_terrain"] += 1
                    else:
                        cls["off_fo4_terrain_too"] += 1
                worst.append((best, f"{fid:08X}", i, round(float(x), 3), round(float(y), 3), round(float(z), 3)))
        ds.append(vd)
        ok = (vd[m.triangles["v"]] <= SURFACE_TOL).all(1)
        tri_ok += int(ok.sum())
        tri_all += len(ok)
    d = np.concatenate(ds)
    worst.sort(reverse=True)
    return {"vertices": len(d), "tolerance_m": SURFACE_TOL, "classes": cls,
            "within": {f"{t} m": int((d <= t).sum()) for t in (0.05, 0.1, 0.25, 0.5, 1.0)},
            "median_m": round(float(np.median(d)), 4), "p95_m": round(float(np.percentile(d, 95)), 4),
            "p99_m": round(float(np.percentile(d, 99)), 4), "max_m": round(float(d.max()), 4),
            "triangles_all_vertices_within": tri_ok, "triangles": tri_all,
            "worst": [{"d": round(w[0], 3), "navmesh": w[1], "vertex": w[2], "pos": list(w[3:])} for w in worst[:25]]}


def off_surface_vertices(world, navs):
    """[(x, y, z, d, navmesh)] of the navmesh vertices more than SURFACE_TOL from the BTD and every converted
    collision surface at their x, y."""
    out = []
    for fid, m in navs.items():
        for x, y, z in m.vertices:
            best = abs(z - world.ground(x, y))
            for s, _o in world.index.surfaces(x, y):
                best = min(best, abs(z - s))
            if best > SURFACE_TOL:
                out.append((float(x), float(y), float(z), best, fid))
    return out


def fo4_own_check(fo4_data, objects, off, ground4, radius=8.0):
    """The off-surface vertices against Fallout 4's OWN data: FO4's LAND and the collision of the source NIFs (read from
    the FO4 mesh archives, decoded by scripts/game/routes.collision_bodies, independent of the converter and of
    sfbodies) of every reference within `radius` m. A vertex on neither our surfaces nor FO4's lies where Fallout 4's
    own navmesh is off its own surfaces too (inherent: a simplified navmesh over rocks, cliffs, logs); one on FO4's but
    not on ours points at the object conversion (e.g. guessed collision boxes) or the BTD."""
    sys.path.insert(0, os.path.join(REPO, "scripts", "game"))
    import routes
    from fo4sf import ba2, nif as nifmod
    archives = [ba2.Ba2(os.path.join(fo4_data, fn)) for fn in sorted(os.listdir(fo4_data))
                if fn.lower().startswith("fallout4 - meshes") and fn.lower().endswith(".ba2")]
    refs, bases = objects["refs"], objects["bases"]
    pos = np.array([r["pos"] for r in refs])
    model_tris, cls = {}, {"on_fo4_own": 0, "off_fo4_own_too": 0}
    by_kind = {}
    for x, y, z, _d, _fid in off:
        near = np.nonzero(np.hypot(pos[:, 0] - x, pos[:, 1] - y) <= radius)[0]
        best = abs(z - ground4(x, y)) if ground4 is not None and ground4(x, y) is not None else math.inf
        for k in near.tolist():
            r = refs[k]
            b = bases[r["base"]]
            if r.get("disabled") or "door" in b:
                continue
            src = b.get("source") or ""
            if src not in model_tris:
                blob = next((a.read(src) for a in archives if a.find(src) is not None), None)
                tris = []
                if blob is not None:
                    try:
                        for _layer, pts, tr in routes.collision_bodies(nifmod.parse(blob)):
                            tris += [tuple(pts[i] for i in t) for t in tr]
                    except Exception:            # an undecodable source collision counts as none (reported below)
                        tris = []
                model_tris[src] = np.array(tris, np.float64).reshape(-1, 3, 3)
            t = model_tris[src]
            if not len(t):
                continue
            mat = np.array(exterior.ref_matrix(r["rot"])).reshape(3, 3)
            w = (t.reshape(-1, 3) * float(r["scale"])) @ mat.T + np.asarray(r["pos"], np.float64)
            for s in exterior.surfaces_at(w.reshape(-1, 3, 3), x, y):
                best = min(best, abs(z - s))
        key = "on_fo4_own" if best <= SURFACE_TOL else "off_fo4_own_too"
        cls[key] += 1
        k = int(np.argmin(np.hypot(pos[:, 0] - x, pos[:, 1] - y)))
        kind = bases[refs[k]["base"]].get("collision", "?")
        by_kind.setdefault(kind, {"on_fo4_own": 0, "off_fo4_own_too": 0})[key] += 1
    cls["by_nearest_collision_kind"] = by_kind
    cls["models_loaded"] = len(model_tris)
    cls["models_without_fo4_collision"] = sum(1 for t in model_tris.values() if not len(t))
    return cls


def fo4_ground_fn(fo4_esm, cells=(-21, 15, -14, 22)):
    x0, y0, x1, y1 = cells
    want = {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}
    with fo4land.Plugin(fo4_esm) as p:
        w = p.read_world("Commonwealth", cells=want, refs=False)
    grids = {xy: fo4land.decode_vhgt(c["vhgt"]) for xy, c in w["cells"].items() if c["vhgt"]}
    merged, _ = fo4land.merge_cells(grids, x0, y0, x1 - x0 + 1, y1 - y0 + 1)
    ox, oy = x0 * fo4land.CELL_UNITS, y0 * fo4land.CELL_UNITS

    def ground(x, y):
        h = fo4land.height_at(merged, ox, oy, x * 70.0, y * 70.0)
        return None if h is None or not math.isfinite(h) else h / 70.0
    return ground


def cmd_check(a):
    src, out = a.exp2c, a.out
    prm = load(os.path.join(out, "exp2_params.json"))
    exp = load(os.path.join(out, "expected.json"))
    plan = load(os.path.join(out, "plan.json"))
    ids = load(os.path.join(out, "formids.json"))
    objects = load(os.path.join(out, "objects.json"))
    checks, rep = [], {}

    def need(cond, what):
        checks.append([what, bool(cond)])

    # 1. exp2c unchanged: the Mars plugin and the base Data files byte for byte, every record of the main plugin
    for rel in [prm["mars"]["plugin"], prm["btd_file"], prm["mask"]] + sorted(exp.get("base_files", [])):
        p1, p2 = os.path.join(out, *rel.split("/")), os.path.join(src, *rel.split("/"))
        need(os.path.isfile(p2) and c2.sha256(p1) == c2.sha256(p2), f"{rel} byte-identical to exp2c")
    navs, nvmis, raw, info = read_plugin_navmeshes(os.path.join(out, prm["plugin"]))
    new = info["walk"]
    old = overlay_records.walk_plugin(os.path.join(src, prm["plugin"]))
    new_by = {r["fid"]: r for r in new["records"]}
    same = sum(1 for r in old["records"] if r["fid"] in new_by and new_by[r["fid"]]["sig"] == r["sig"]
               and new_by[r["fid"]]["flags"] == r["flags"] and new_by[r["fid"]]["fields"] == r["fields"])
    need(same == len(old["records"]), f"every exp2c record unchanged ({same}/{len(old['records'])})")
    added = [r for r in new["records"] if r["fid"] not in {o["fid"] for o in old["records"]}]
    kinds = {}
    for r in added:
        kinds[r["sig"]] = kinds.get(r["sig"], 0) + 1
    need(set(kinds) == {"NAVM", "NAVI"} and kinds.get("NAVI") == 1, f"only NAVM and one NAVI added ({kinds})")
    need(new["masters"] == ["Starfield.esm"], f"masters {new['masters']}")
    own = 0x01000000
    want_ids = [own | int(x, 16) for x in ids["navmeshes"]]
    need(sorted(navs) == sorted(want_ids), f"{len(navs)} NAVM = the {len(want_ids)} FormIDs in formids.json")
    first_obj = max(own | int(v, 16) for v in list(ids["refs"].values()) + list(ids["bases"].values()))
    need(min(want_ids) > first_obj, f"NAVM FormIDs after every exp2c record (first {min(want_ids):08X} > {first_obj:08X})")
    navi = info["navi"][0]
    nver = next((d for s, d in navi["fields"] if s == b"NVER"), b"")
    nvpp = next((d for s, d in navi["fields"] if s == b"NVPP"), None)
    need(navi["fid"] == 0x00000FF1 and nver == (17).to_bytes(4, "little") and nvpp == bytes(8),
         f"NAVI override 00000FF1, NVER 17, empty NVPP ({navi['fid']:08X}, {nver.hex()}, {None if nvpp is None else nvpp.hex()})")
    rep["navm_subrecords"] = sorted({tuple(s for s, _ in v) for v in info["subrecords"].values()})

    # 2. the NVNM bytes against the Python reference writer (same pieces, the FormIDs the plugin got)
    src_navs = load(os.path.join(out, "navmesh.json"))["navmeshes"]
    world_fid = next(r["fid"] for r in new["records"] if r["sig"] == "WRLD")
    world_local = own | (world_fid & 0xFFFFFF)
    door_fid = {s: own | int(v, 16) for s, v in ids["refs"].items()}
    mismatch = []
    for i, e in enumerate(src_navs):
        ref = reference_nvnm(e, world_local, want_ids, door_fid)
        if nm.write_sf(ref) != raw[want_ids[i]]:
            mismatch.append(f"{want_ids[i]:08X}")
    need(not mismatch, f"every NVNM byte-identical to the Python reference writer ({len(mismatch)} differ: {mismatch[:5]})")
    need(all(navs[f].trailer == nm.SF_TRAILER for f in navs), "every NVNM ends with 0c 00 08 00, as vanilla")

    # 3. structure: links, symmetry, dangling, cells, grid, NVMI
    st = nm.validate(navs, nvmis, world_local)
    errs = st.pop("errors")
    need(not errs, f"navmesh structure ({len(errs)} problems: {errs[:3]})")
    need(st["links"] == st["links_symmetric"], f"every edge link symmetric ({st['links_symmetric']}/{st['links']})")
    rep["structure"] = st
    pieces_src = {want_ids[i]: e["src"] for i, e in enumerate(src_navs)}
    cell_gap = 0.0
    for fid, m in navs.items():
        for ti in range(len(m.triangles)):
            fl = int(m.triangles["flags"][ti])
            for k in range(3):
                if not fl & nm.EDGE_LINK_BITS[k]:
                    continue
                L = m.links[int(m.triangles["e"][ti][k])]
                o = navs[int(L["navmesh"])]
                if pieces_src[int(L["navmesh"])] != pieces_src[fid]:
                    continue
                v, w = m.triangles["v"][ti], o.triangles["v"][int(L["tri"])]
                kk = int(L["edge"])
                a1 = m.vertices[int(v[k])], m.vertices[int(v[(k + 1) % 3])]
                b1 = o.vertices[int(w[kk])], o.vertices[int(w[(kk + 1) % 3])]
                cell_gap = max(cell_gap, float(np.abs(np.array(a1) - np.array(b1[::-1])).max()))
    need(cell_gap == 0.0, f"cell-line links join identical points (largest difference {cell_gap} m)")
    nrep = load(os.path.join(out, "navmesh_report.json"))
    need(st["link_gap_max_m"] <= nrep["fo4_portal_gap_max_m"] + 1e-4,
         f"portal links no farther apart than Fallout 4's own portals ({st['link_gap_max_m']:.4f} <= "
         f"{nrep['fo4_portal_gap_max_m']:.4f} m)")
    need(all(e.flags == 0 and e.outline is None and not e.traversals for e in nvmis.values()),
         "every NVMI without outline and traversals (flags 0), the vanilla form of large navmeshes")

    # 4. on the surface: BTD + converted collision (+ FO4 LAND for the rest)
    world, _ = world_from_objects(out, prm)
    ground4 = fo4_ground_fn(a.fo4) if a.fo4 else None
    rep["surface"] = surface_report(world, navs, ground4)
    s = rep["surface"]
    rep["surface_share_within"] = round(s["within"][f"{SURFACE_TOL} m"] / s["vertices"], 4)
    need(rep["surface_share_within"] >= 0.9, f"navmesh vertices within {SURFACE_TOL} m of the BTD or a converted "
         f"collision surface: {s['within'][f'{SURFACE_TOL} m']:,} of {s['vertices']:,} (median {s['median_m']} m, "
         f"{s['triangles_all_vertices_within']:,} of {s['triangles']:,} triangles with all three)")
    if ground4 is not None:
        need(s["classes"]["off_on_fo4_terrain"] <= 0.01 * s["vertices"],
             f"vertices off our surfaces but on FO4's own terrain (a terrain conversion problem): "
             f"{s['classes']['off_on_fo4_terrain']}")
    if a.fo4_data:
        off = off_surface_vertices(world, navs)
        own = fo4_own_check(a.fo4_data, objects, off, ground4)
        rep["surface_fo4_own"] = own
        need(own["on_fo4_own"] <= 0.01 * s["vertices"],
             f"vertices off our surfaces but on FO4's own LAND or source collision (a conversion problem): "
             f"{own['on_fo4_own']} of {len(off)} off; the other {own['off_fo4_own_too']} are off FO4's own surfaces "
             "too (inherent to FO4's navmesh)")

    # 5. the NPC points: terrain landing, on a converted triangle, connected
    pts = exp["npc_points"]
    for n in ("A", "B", "A2", "B2"):
        p = pts[n]
        land = world.landing(p["x"], p["y"], 150.0)
        hit = nav_at(navs, p["x"], p["y"], world.ground(p["x"], p["y"]))
        need(not land["on_object"] and abs(land["centre"] - p["expect"]) <= world.step and
             c2.reference_ok(world, p["x"], p["y"], clear=POINT_CLEAR) is not None,
             f"{p['label']}: open level terrain at {p['expect']}, nothing above it within {POINT_CLEAR} m")
        need(hit is not None and f"{hit[0]:08X}" == p["navmesh"],
             f"{p['label']}: on converted navmesh {p['navmesh']} ({None if hit is None else round(hit[2] - p['expect'], 3)} m "
             "above the terrain)")
    pa = nm.triangle_path(navs, (int(pts["A"]["navmesh"], 16), pts["A"]["tri"]), (int(pts["B"]["navmesh"], 16), pts["B"]["tri"]))
    pc = nm.triangle_path(navs, (int(pts["A2"]["navmesh"], 16), pts["A2"]["tri"]), (int(pts["B2"]["navmesh"], 16), pts["B2"]["tri"]))
    need(pa is not None and len({f for f, _ in pa}) == 1, "A -> B connected inside one navmesh")
    need(pc is not None and len({f for f, _ in pc}) >= 2, "A2 -> B2 connected through an edge link")
    need(tuple(tg.sf_cell_of(pts["A"]["x"], pts["A"]["y"])) == NPC_CELL and
         tuple(tg.sf_cell_of(pts["B"]["x"], pts["B"]["y"])) == NPC_CELL, f"A and B in cell {NPC_CELL} (gnm: current cell)")
    labels = [p["label"] for p in plan[0]["points"]]
    need(plan[0]["z_ref"] in labels and all(pts[n]["label"] in labels for n in ("A", "B", "A2", "B2")),
         "entry 1 holds the four NPC points and its z_ref")
    need(plan[1:] == load(os.path.join(src, "plan.json")), "entries 2 to 5 = exp2c's four entries")
    # informational: what the entry's setpos x / y / z positions overlap (capsule assumed; unresolved whether setpos
    # with the console open resolves an overlap, as in exp2c)
    rep["entry1_teleport_overlaps"] = {leg["to"]: sorted({h for pos in leg["positions"] for h in pos[3]})
                                       for leg in exp["npc_entry"]["teleports"]}

    rep["checks"] = checks
    rep["pass"] = all(c[1] for c in checks)
    save(os.path.join(out, "offline_check_navmesh.json"), rep)
    for what, good in checks:
        print(("  ok   " if good else "  FAIL ") + what)
    print(json.dumps({k: rep[k] for k in ("structure", "surface", "navm_subrecords")}, indent=1)[:5000])
    print("CHECK", "PASS" if rep["pass"] else "FAIL")
    return 0 if rep["pass"] else 1


def reference_nvnm(e, world, fids, door_fid):
    """The Nvnm the Python reference writer makes from a navmesh.json entry (what TerrainExp2 must have written)."""
    v = np.array([x[:3] for x in e["vertices"]], np.float64).reshape(-1, 3)
    extra = np.array([x[3] for x in e["vertices"]], np.int32)
    t = np.zeros(len(e["triangles"]), nm.TRI_DTYPE)
    for i, r in enumerate(e["triangles"]):
        t[i] = (r[0:3], r[3:6], r[6], r[7], r[8], r[9])
    links = np.zeros(len(e["links"]), nm.LINK_DTYPE)
    for i, (typ, tgt, tri, edge) in enumerate(e["links"]):
        links[i] = (typ, fids[tgt], tri, edge)
    doors = np.zeros(len(e["doors"]), nm.DOOR_DTYPE)
    for i, (tri, ex, src) in enumerate(e["doors"]):
        doors[i] = (tri, ex, door_fid[src])
    wps = np.zeros(len(e["waypoints"]), nm.WAYPOINT_DTYPE)
    for i, (x, y, z, tri, ex) in enumerate(e["waypoints"]):
        wps[i] = ((x, y, z), tri, ex)
    g = e["grid"]
    return nm.Nvnm(nm.SF_VERSION, nm.MAGIC, world, tuple(e["cell"]), None, v, extra, t, links, doors, [],
                   np.zeros(0, nm.COVERMAP_DTYPE), wps, g["divisor"], tuple(g["size"]), tuple(g["min"]), tuple(g["max"]),
                   g["lists"], nm.SF_TRAILER)


# ------------------------------------------------------------------------------------------------------------- npc
def n1_test(label, method, a, b, spawn_local, requires, expect, basis, pre=None):
    t = {"label": label, "travel": "coc FO4CW_RedRocketSpawn", "npc": NPC,
         "anchor": {"ref": overlay_records.anchor_ref(), "local": [-989.0286, 1147.2, 105.1434]},
         "spawn_local": spawn_local, "a": a, "b": b, "drop": 30, "settle_ms": 7000, "method": method,
         "reads_s": READS, "radius": 2.5, "min_progress": 5.0, "control": False, "fresh": True,
         "expect": expect, "requires": requires, "basis": basis}
    if pre:
        t["pre"] = list(pre)
        t["pre_wait_ms"] = 20000
    return t


def cmd_npc(a):
    exp = load(os.path.join(a.exp2d, "expected.json"))
    pts = exp["npc_points"]
    root, qroot = a.staging_root, a.queue_root
    xyz = {n: [pts[n]["x"], pts[n]["y"], pts[n]["expect"]] for n in ("A", "B", "A2", "B2")}
    # the world check of exp2b2 at the NPC points: a byte-identical copy of the staged exp2b2 with its own plan.json
    # (plan-npc only accepts a "requires" whose queue tested the very folder it installs)
    wdir = os.path.join(root, "terrain_exp2b2_npc")
    os.makedirs(wdir, exist_ok=True)
    for fn in os.listdir(a.exp2b2):
        s = os.path.join(a.exp2b2, fn)
        if os.path.isfile(s) and (fn.lower().endswith(".esm") or fn == "exp2_params.json"):
            shutil.copy2(s, os.path.join(wdir, fn))
    for fn in ("expected.json", "offline_check.json", "preview.png"):    # exp2b's, not this plan's (first staging)
        if os.path.exists(os.path.join(wdir, fn)):
            os.remove(os.path.join(wdir, fn))
    c2.copy_tree(os.path.join(a.exp2b2, "Data"), os.path.join(wdir, "Data"))
    b2 = load(os.path.join(a.exp2b2, "plan.json"))[0]
    ref = exp["reference"]
    wplan = [dict({k: v for k, v in b2.items() if k not in ("label", "points", "z_ref")},
                  label="terrain exp2b2 world check of the N1 NPC points (A, B, A2, B2), relative to zref_ground",
                  z_ref=ref["label"],
                  points=[{"label": ref["label"], "x": ref["x"], "y": ref["y"], "expect": ref["expect"]}] +
                         [{"label": pts[n]["label"], "x": pts[n]["x"], "y": pts[n]["y"], "expect": pts[n]["expect"]}
                          for n in ("A", "B", "A2", "B2")])]
    save(os.path.join(wdir, "plan.json"), wplan)
    with open(os.path.join(wdir, "README.txt"), "w", encoding="utf-8") as f:
        f.write("World check for N1a / N1b (Claude, 2026-10-11, branch claude/terrain-navmesh). A byte-identical copy of\n"
                "C:\\Modding\\staging\\terrain_exp2b2 (plugins, Data tree, params) with its own plan.json: one terrain entry\n"
                "that drops the player at the N1 NPC points A, B, A2, B2 and the Z reference zref_ground. N1a / N1b\n"
                "require its PASS (the actor's spawn and walk ground is ours, not procedural Mars) and install this folder.\n"
                "Plan with: testqueue.py plan-terrain ... --exp-dir <this folder> --plugins FO4TerrainExp2.esm,\n"
                "FO4TerrainExp2_Mars.esm --fresh. Recipe: docs/actors/navmesh-conversion.md.\n")
    wq_b2 = os.path.join(qroot, "terrain_exp2b2_npc")
    wq_d = os.path.join(qroot, "terrain_exp2d")
    req_b2 = {"queue": wq_b2, "test": "0000_terrain_FO4CW_RedRocketSpawn", "verdict": "PASS"}
    req_d = {"queue": wq_d, "test": "0000_terrain_FO4CW_RedRocketSpawn", "verdict": "PASS"}   # exp2d's entry 1
    sl_b2 = b2["spawn_local"]
    sl_d = exp["spawn"]["spawn_local"]
    variants = {
        "n1a": ("exp2b2, terrain only, no navmesh", sl_b2, req_b2, None, "FAIL NONAV", "FAIL NONAV",
                "supported hypothesis (PR #61 1.4): no NAVM in the plugin worldspace and runtime generation tied to "
                "planet procgen and seed markers"),
        "n1b": ("exp2b2 + GenerateNavMesh (gnm) at A before the spawn", sl_b2, req_b2, ["gnm"],
                "unresolved (PASS if gnm builds navmesh in a plugin worldspace cell)",
                "unresolved (gnm: 'Generates nav-mesh on the current cell'; B2 lies in the next cell)",
                "unresolved: GenerateNavMesh is in the console table (PR #61 1.3), its reach to plugin worldspaces is not"),
        "n1c": ("exp2d, the converted Fallout 4 navmesh", sl_d, req_d, None, "PASS",
                "PASS (unresolved: needs the edge links and the NAVI entries)",
                "supported hypothesis: converted NAVM checked offline (make_exp2d.py check); A and B on one navmesh "
                "(the 'same navmesh' search needs no NAVI); A2 and B2 joined by a cell-line edge link and NVMI merged-to"),
    }
    out = {}
    for key, (world, sl, req, pre, exp_same, exp_cross, basis) in variants.items():
        tests = [n1_test(f"N1{key[-1]}_{m}", m, xyz["A"], xyz["B"], sl, req, exp_same, basis, pre) for m in METHODS]
        tests.append(n1_test(f"N1{key[-1]}_cross_ptr", "ptr_player", xyz["A2"], xyz["B2"], sl, req, exp_cross,
                             basis + "; cross-cell pair", pre))
        d = os.path.join(root, f"npc_nav_{key}")
        os.makedirs(d, exist_ok=True)
        save(os.path.join(d, "plan.json"), tests)
        with open(os.path.join(d, "README.txt"), "w", encoding="utf-8") as f:
            f.write(n1_readme(key, world, tests, pts, req, a))
        out[key] = d
    print(json.dumps(out, indent=1))
    return 0


def n1_readme(key, world, tests, pts, req, a):
    inst = {"n1a": "terrain_exp2b2_npc", "n1b": "terrain_exp2b2_npc", "n1c": "terrain_exp2d"}[key]
    lines = [
        f"NPC navigation N1{key[-1]} (Claude, 2026-10-11, branch claude/terrain-navmesh): {world}.",
        "Runner kind npc_nav (PR #68). The same vanilla actor (EncCitizen01Template 002B211C, as N0), the same methods",
        "and the same A/B points in all three variants (N1a terrain only, N1b + gnm, N1c converted navmesh), on the same",
        "terrain (exp2b2's BTD; exp2d adds the FO4 objects and the navmesh). Frame: the worldspace's own coordinates;",
        "offset from the arrival (the anchor reads its unmerged position). Every test \"fresh\" (a relaunch: repeated",
        "coc into a merged planet world is erratic).",
        f"  A  {pts['A']['x']}, {pts['A']['y']}, {pts['A']['expect']}   B  {pts['B']['x']}, {pts['B']['y']}, {pts['B']['expect']}"
        f"   ({pts['pair']['distance']} m, one navmesh in exp2d)",
        f"  A2 {pts['A2']['x']}, {pts['A2']['y']}, {pts['A2']['expect']}   B2 {pts['B2']['x']}, {pts['B2']['y']}, {pts['B2']['expect']}"
        f"   ({pts['cross']['distance']} m, across a cell line)",
        "Tests: " + ", ".join(f"{t['label']} ({t['method']}{', pre gnm' if t.get('pre') else ''})" for t in tests),
        f"Precondition: {req['test']} in {req['queue']} PASS (the player drops at A, B, A2, B2 and lands on our terrain),",
        "else INCONCLUSIVE PRECONDITION and no launch. FAIL verdicts count only where the same method and N0_base passed",
        "in npc_nav_n0 (else INCONCLUSIVE CONTROL; testqueue.py report re-applies the gate).",
        "What the verdicts separate: world = the precondition (terrain test) and FELL; navigation = NONAV / STALLED",
        "with N0 passing; N1a vs N1c differ only by the navmesh, N1a vs N1b only by gnm.",
        "Plan (after npc_nav_n0 and the world-check queue are planned), with the checkout that runs the chain:",
        f"  python scripts\\game\\testqueue.py plan-npc --staging C:\\Modding\\staging\\<pinned build> ^",
        f"         --exp-dir C:\\Modding\\staging\\npc_nav_{key} --out C:\\Modding\\testqueue\\npc_nav_{key} ^",
        f"         --install-exp C:\\Modding\\staging\\{inst} --plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm ^",
        "         --control-queue C:\\Modding\\testqueue\\npc_nav_n0 --fresh",
        "(plan-npc --fresh and the plan's \"fresh\" need claude/terrain-navmesh's testqueue.py.)",
        "Recipe and expectations: docs/actors/navmesh-conversion.md.",
    ]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("stage", "check"):
        s = sub.add_parser(name)
        s.add_argument("--exp2c", required=True)
        s.add_argument("--out", required=True)
        s.add_argument("--fo4", default="" if name == "check" else None, required=name == "stage",
                       help="Fallout4.esm")
        if name == "check":
            s.add_argument("--fo4-data", default="", help="FO4 Data folder (mesh archives): the off-surface navmesh "
                                                          "vertices against FO4's own collision")
        if name == "stage":
            s.add_argument("--sf-esm", default="", help="Starfield.esm: build the plugin with dotnet/TerrainExp2")
    s = sub.add_parser("npc")
    s.add_argument("--exp2b2", required=True)
    s.add_argument("--exp2d", required=True)
    s.add_argument("--staging-root", required=True)
    s.add_argument("--queue-root", default=r"C:\Modding\testqueue")
    a = ap.parse_args()
    return {"stage": cmd_stage, "check": cmd_check, "npc": cmd_npc}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
