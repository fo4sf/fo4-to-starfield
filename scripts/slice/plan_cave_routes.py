"""Walking routes for the Red Rocket cave door on core64c (docs/slice/cave-core64c.md): the runner's door_trip legs
WALK from where the player stands to each door (outside.route / inside.route), no teleport. Read-only on game data;
writes one JSON file outside the repo.

    python scripts/slice/plan_cave_routes.py --fo4 <Fallout4.esm> --core <terrain_core64c> --port <pinned build>
           --out <routes.json> [--png <routes.png>]

outside  from core64c's coc arrival (spawn_local: the pump island under the Red Rocket canopy the player lands on) to
         the exterior door 08EB65 (FO4 position / 70), over core64c's BTD and converted collision near Red Rocket.
         FO4's navmesh has a hole in the cave mouth (its door triangle lies at the interior door's XTEL point, 5.5 m
         south of the door, where NPCs use the door), so the route ends within TARGET_M of that point and the last
         5.4 m are the runner's straight walk at the door, checked here with the assumed capsule (final_walk);
inside   from the interior XTEL arrival (the exterior door's XTEL / 70) to the interior door 05E844, over the pinned
         build's converted RedRocket01 collision.
Walkability comes from two sources: Fallout 4's own navmesh of those cells (Fallout4.esm NAVM: where FO4 characters
walk; the route must stay on it, with a margin from its open borders) and the converted world (a floor under every
0.25 m sample, at most 0.3 m higher than the last and at most 1 m lower: door_route.walk). The assumed player capsule
(0.35 m x 1.8 m, contacts below 0.3 m ignored: an assumption, unresolved) is added where a route exists with it
(door_route.plan tries levels from the strictest); its remaining contacts along the chosen route are reported, not
hidden. Each leg ends within GOAL_M of its door's origin; the runner then walks at the door itself.
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
for p in (os.path.join(REPO, "src"), os.path.join(REPO, "scripts", "terrain"), os.path.join(REPO, "scripts", "actors"),
          HERE):
    sys.path.insert(0, p)
from fo4sf import exterior, fo4land, navmesh  # noqa: E402
import door_route as dr  # noqa: E402

UNITS = 70.0
GOAL_M = 2.7                 # each route ends with the feet within this of the door's origin (inside the 3 m range)
# (navmesh margin m, capsule radius m or None): strictest first. The margin keeps the route off the navmesh's open
# borders (FO4 draws them about one agent radius from walls); the capsule adds the converted collision's walls.
LEVELS = ((0.3, 0.5), (0.3, 0.35), (0.0, 0.35), (0.3, None), (0.0, None))
CAPSULE = (0.35, 1.8, 0.3)   # radius, height, skin: as make_redrocket_door (assumed)
DRIFT_M = 0.2                # steering drift the report replays the route with, left and right
# the link (Fallout4.esm, docs/slice/redrocket-door.md section 1, verified): positions in FO4 units
EXT_DOOR = (-69646.37, 77664.305, 6907.905)
INT_DOOR = (-116.13465, 169.1064, 0.0)
INT_ARRIVAL = (3.4483528, -463.53928, -0.43591836)      # the exterior door's XTEL: where the player arrives inside
EXT_ARRIVAL = (-69687.12, 77290.0, 6984.0)              # the interior door's XTEL: where the player comes back out
TARGET_M = 0.75              # the outside route ends this close to EXT_ARRIVAL (in front of the cave mouth)
FO4_CELL = "RedRocket01"
EXT_CELLS = {(x, y) for x in (-18, -17) for y in (18, 19)}  # FO4 cells holding the arrival, the station and the door


def metres(v):
    return tuple(float(x) / UNITS for x in v)


def nav_triangles(navs):
    """(N, 3, 3) navmesh triangles in metres (FO4 units / 70: the frame of both converted worlds)."""
    out = [m.vertices[m.triangles["v"]] / UNITS for m in navs.values() if len(m.triangles)]
    return np.concatenate(out) if out else np.zeros((0, 3, 3))


def door_triangles(navs):
    """[(navmesh, triangle, door ref, centre in metres)]: FO4's navmesh door triangles (where NPCs use a door)."""
    out = []
    for fid, m in navs.items():
        for d in m.doors:
            c = m.vertices[m.triangles["v"][int(d[0])]].mean(0) / UNITS
            out.append({"navmesh": f"{fid:06X}", "triangle": int(d[0]), "door": f"{int(d[2]):06X}",
                        "centre": [round(float(v), 3) for v in c]})
    return out


def route_side(name, support, capsule_r, nav, start, door, bounds, start_free=0.0, target=None, target_m=GOAL_M):
    """One leg's route and its report: door_route.plan over LEVELS to within target_m of `target` (default: GOAL_M of
    the door), then the straight walk at the door the runner makes after the last waypoint (door_route.toward with
    the assumed capsule: it must come within GOAL_M of the door's origin), contacts and drift replays."""
    def blocked_at(level):
        margin, r = level
        return nav.blocked_at(margin) if r is None else dr.both(nav.blocked_at(margin), capsule_r(r))
    t = time.time()
    res = dr.plan(support, blocked_at, start, door, bounds, goal_m=target_m, radii=LEVELS, start_free=start_free,
                  target=target)
    out = {"name": name, "start": [round(v, 4) for v in start], "door": [round(v, 4) for v in door],
           "target": [round(v, 4) for v in (target or door)], "target_m": target_m,
           "levels_tried": [{"margin": lv[0], "capsule": lv[1], "found": ok} for lv, ok in res["tried"]],
           "seconds": round(time.time() - t, 1)}
    if not res["waypoints"]:
        out["route"] = None
        return out
    wps = res["waypoints"]
    real = dr.free_near(capsule_r(CAPSULE[0]), start, start_free)
    out["final_walk"] = fw = dr.toward(support, real, wps[-1], door, reach=GOAL_M)
    out["route_planned"] = [list(p) for p in wps]
    if fw["reaches"] and math.dist(wps[-1], door) > GOAL_M:
        # the runner's plan wants a route that ends near its door (testqueue.door_test: within activate_m + 1 m):
        # the straight final walk, checked just above with the assumed capsule, becomes the route's last leg
        wps = [list(p) for p in wps] + [fw["end"]]
        out["final_point_added"] = True
    planned = out["route_planned"]
    length = res["length"] + (fw["walked_m"] if out.get("final_point_added") else 0.0)
    # contacts over the whole route the runner walks; navmesh cover over the planned part only (the final walk into
    # a cave mouth leaves FO4's navmesh by design: its door triangle lies at the XTEL point)
    out.update(route=wps, level={"margin": res["radius"][0], "capsule": res["radius"][1]}, length=round(length, 3),
               length_planned=res["length"], legs=res["legs"], end_to_door_m=round(math.dist(wps[-1], door), 3),
               nodes=len(res["nodes"]), capsule_contacts=dr.contacts(support, real, wps),
               off_navmesh=dr.contacts(support, nav.blocked_at(0.0), planned),
               drift={f"{off:+.1f}": {"capsule_contacts": len(dr.contacts(support, real, dr.lateral(wps, off))),
                                      "off_navmesh": len(dr.contacts(support, nav.blocked_at(0.0),
                                                                     dr.lateral(planned, off)))}
                      for off in (-DRIFT_M, DRIFT_M)},
               walk_ms=dr.walk_ms(length))
    return out


def render(path, side, support, nav, bounds, px=0.25, scale=3, above=50.0):
    """Top-down PNG: the highest surface up to `above` over the start (grey, lighter is higher; an interior needs a
    small `above` to look under its ceiling), FO4 navmesh blue, the route green, its waypoints cyan, the door red."""
    from PIL import Image, ImageDraw
    w, h = int((bounds[2] - bounds[0]) / px), int((bounds[3] - bounds[1]) / px)
    img = Image.new("RGB", (w, h))
    pix = img.load()
    z0 = side["start"][2]
    for j in range(h):
        y = bounds[3] - (j + 0.5) * px
        for i in range(w):
            x = bounds[0] + (i + 0.5) * px
            s = support(x, y, z0 + above)
            v = 0 if s is None else int(max(20, min(235, 128 + (s[0] - z0) * 12)))
            on = nav.covered(x, y, s[0]) if s is not None else False
            pix[i, j] = (v // 2, v // 2, min(255, v // 2 + 90)) if on else (v, v, v)
    d = ImageDraw.Draw(img)

    def P(p):
        return ((p[0] - bounds[0]) / px, (bounds[3] - p[1]) / px)
    if side.get("route"):
        d.line([P(p) for p in side["route"]], fill=(0, 255, 0), width=2)
        for p in side["route"]:
            q = P(p)
            d.ellipse([q[0] - 2, q[1] - 2, q[0] + 2, q[1] + 2], fill=(0, 255, 255))
    q = P(side["door"])
    d.ellipse([q[0] - 4, q[1] - 4, q[0] + 4, q[1] + 4], fill=(255, 40, 0))
    img.resize((w * scale, h * scale)).save(path)


def core_world(core, spawn_local, o_door):
    """(core64c's local collision world around the arrival and the cave door, its bounds)."""
    import make_core64c as mc                                          # noqa: E402  (numpy, the terrain modules)
    with open(os.path.join(core, "objects.json"), encoding="utf-8-sig") as f:
        obj = json.load(f)
    _prm, ov = mc.core_params(core)
    terrain = mc.Terrain(os.path.join(core, *ov["btd_file"].split("/")))
    bounds_o = (min(spawn_local[0], o_door[0]) - 25.0, min(spawn_local[1], o_door[1]) - 20.0,
                max(spawn_local[0], o_door[0]) + 25.0, max(spawn_local[1], o_door[1]) + 15.0)
    world = mc.CoreWorld(os.path.join(core, "Data"), obj["bases"], obj["refs"], terrain, bounds_o, margin=15.0)
    if world.collision_errors:
        sys.exit(f"converted collision unreadable: {world.collision_errors}")
    return world, bounds_o


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fo4", required=True, help="Fallout4.esm")
    ap.add_argument("--core", required=True, help="core64c's staged folder (objects.json, overlays_params.json, Data)")
    ap.add_argument("--port", required=True, help="the pinned build folder (FO4Port.esm, manifest, cell exports)")
    ap.add_argument("--out", required=True, help="routes JSON to write (outside the repo)")
    ap.add_argument("--png", default="", help="also write <png>_outside.png / _inside.png maps")
    a = ap.parse_args(argv)
    out = plan_routes(a.fo4, a.core, a.port, png=a.png)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    return 0 if out["outside"].get("route") and out["inside"].get("route") else 1


def plan_routes(fo4, core, port, png="", world=None, interior=None):
    """Both routes (the module doc): {"outside", "inside", "frames", "assumptions"}. world / interior: a prebuilt
    core_world() result and make_redrocket_door.Interior, else built here."""
    import make_redrocket_door as rr                                   # noqa: E402
    import navmesh_points as npnt                                      # noqa: E402

    with fo4land.Plugin(fo4) as pl:
        ext_navs = {f: navmesh.parse(b) for _c, f, _fl, b in navmesh.world_navmeshes(pl, "Commonwealth", EXT_CELLS)}
        _cfid, int_navs, _refs = npnt.read_cell(pl, FO4_CELL)

    # outside: core64c's world near Red Rocket
    with open(os.path.join(core, "plan.json"), encoding="utf-8-sig") as f:
        spawn_local = json.load(f)[0]["spawn_local"]
    o_door = metres(EXT_DOOR)
    world, bounds_o = world or core_world(core, spawn_local, o_door)
    sup_o = rr.exterior_support(world)
    r_, h_, s_ = CAPSULE

    def cap_o(r):
        return lambda x, y, z: [world.describe(k)["edid"] if isinstance(k, (int, np.integer)) else k for k in
                                exterior.capsule_hits(world.index, world.ground, x, y, z, radius=r, height=h_, skin=s_)]
    fa = sup_o(spawn_local[0], spawn_local[1], spawn_local[2] + 0.5)
    nav_o = dr.NavCover(nav_triangles(ext_navs))
    # FO4's navmesh stops short of the cave mouth (a hole in front of the door; its door triangle lies at the XTEL
    # arrival, where NPCs use the door): the route ends there and the runner walks the last 5.4 m straight at the door
    outside = route_side("outside", sup_o, cap_o, nav_o, (spawn_local[0], spawn_local[1], fa[0]), o_door, bounds_o,
                         target=metres(EXT_ARRIVAL), target_m=TARGET_M)
    outside["start_floor_owner"] = fa[1]
    outside["fo4_door_triangles"] = door_triangles(ext_navs)
    print(f"outside: {outside.get('length')} m, level {outside.get('level')}, tried {outside['levels_tried']}")

    # inside: the pinned build's RedRocket01
    it = interior or rr.Interior(port, FO4_CELL)

    def cap_i(r):
        return lambda x, y, z: [it.describe(k)["model"] for k in exterior.capsule_hits(
            it.index, lambda _x, _y: -1e9, x, y, z, radius=r, height=h_, skin=s_)]
    i_arr, i_door = metres(INT_ARRIVAL), metres(INT_DOOR)
    fi = it.support(i_arr[0], i_arr[1], i_arr[2] + 0.5)
    bounds_i = (min(i_arr[0], i_door[0]) - 12.0, min(i_arr[1], i_door[1]) - 10.0,
                max(i_arr[0], i_door[0]) + 12.0, max(i_arr[1], i_door[1]) + 10.0)
    nav_i = dr.NavCover(nav_triangles(int_navs))
    # the arrival's own capsule touches a rock mound (docs/slice/redrocket-door.md section 5): leave from there
    inside = route_side("inside", it.support, cap_i, nav_i, (i_arr[0], i_arr[1], fi[0]), i_door, bounds_i,
                        start_free=0.8)
    inside["start_floor_owner"] = fi[1]
    inside["fo4_door_triangles"] = door_triangles(int_navs)
    inside["interior_collision_errors"] = it.errors
    print(f"inside: {inside.get('length')} m, level {inside.get('level')}, tried {inside['levels_tried']}")

    out = {"routes": "docs/slice/cave-core64c.md", "outside": outside, "inside": inside,
           "frames": {"outside": "core64c world frame (FO4 / 70); the runner adds the merge offset",
                      "inside": "RedRocket01 interior frame (FO4 / 70)"},
           "assumptions": {"climb_m_per_0.25m": dr.CLIMB, "max_drop_m": dr.MAX_DROP, "capsule": CAPSULE,
                           "goal_m": GOAL_M, "levels": LEVELS, "speed_m_s": dr.SPEED}}
    if png:
        base = os.path.splitext(png)[0]
        render(base + "_outside.png", outside, sup_o, nav_o, bounds_o)
        render(base + "_inside.png", inside, it.support, nav_i, bounds_i, px=0.1, scale=4, above=1.5)
    return out


if __name__ == "__main__":
    sys.exit(main())
