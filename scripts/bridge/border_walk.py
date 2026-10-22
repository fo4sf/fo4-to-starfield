"""Where the playable border is: walk straight out from the Red Rocket arrival in several directions until Boundary
Reached stops the player, then plot where each walk stopped (the owner's ask, 2026-10-22: "plot out and take SS of
where the border ends compared to where you are on the surface map").

usage:
  python scripts/bridge/border_walk.py plan --core <core build dir> --out <NEW folder> [--rays 8] [--length-m 1200]
         [--first-heading 0]
      per ray one walk test (testqueue.py plan-walk): coc FO4Core_RedRocketSpawn, then walk with real input along a
      straight line from the arrival (waypoints every WP_STEP_M, none kept but the last), each with its own
      walk_ground.json (walk_route.ground_file over a CORRIDOR_M corridor). The walk runner reads getpos every leg,
      takes a screenshot every shot_every legs, looks for the "BOUNDARY REACHED" popup after every leg and stops there
      (qstep.ps1 walk kind; it closes the popup with Tab). Writes plan.json, ground_<ray>.json and README.txt. Rays are
      clipped to the core's terrain. Refuses an existing --out.
  python scripts/game/testqueue.py plan-walk ... --exp-dir <out> --out <queue>   (as the v6i Red Rocket walks)
  python scripts/game/testqueue.py run --queue <queue> --max-attempts 1
  python scripts/bridge/border_walk.py report --queue <queue> --plan <out> [--markers <fo4_locations_world.csv>]
         [--extra "label:x,y" ...] [--svg <file>] [--csv <file>]
      per ray: why the walk stopped (boundary, stuck, the goal, ...), the last position read before it (the game's
      world frame and the core's local frame), its distance and bearing from the arrival, and the screenshot taken
      with the popup. Writes a CSV and an SVG map: the arrival, each ray's walked line, a red cross where Boundary
      Reached stopped it, FO4 locations (--markers) and any --extra world points (e.g. the owner's own reading).
A ray that ends on stuck or off the route says only that the border is beyond its last read, never where it is.
Game data stays outside the repo; nothing here touches the game or its install.
"""
import argparse
import csv
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "scripts", "terrain"))
sys.path.insert(0, os.path.join(REPO, "scripts", "game"))

SPAWN_COC = "FO4Core_RedRocketSpawn"
WP_STEP_M = 12.0                 # a waypoint every this many metres (walk_route's LEG_MAX)
CORRIDOR_M = 40.0                # ground file corridor; the walk's own detours (+-50 degrees) stay inside it
OFFROUTE_M = 35.0
EDGE_MARGIN_M = 100.0            # rays stop this far inside the terrain (core64's ground may end 100 m inside)
WALK_SPEED = 4.6


def load(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def save(p, obj, indent=1):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=indent)


def heading_xy(deg):
    """Unit vector of a compass heading (0 = +y north, 90 = +x east), as player.setangle z."""
    r = math.radians(deg)
    return math.sin(r), math.cos(r)


def ray_end(start, deg, length, box):
    """The end of a ray from start along deg, at most length metres and clipped to box (x0, y0, x1, y1)."""
    dx, dy = heading_xy(deg)
    t = length
    for v, d, lo, hi in ((start[0], dx, box[0], box[2]), (start[1], dy, box[1], box[3])):
        if d > 1e-9:
            t = min(t, (hi - v) / d)
        elif d < -1e-9:
            t = min(t, (lo - v) / d)
    t = max(t, 0.0)
    return start[0] + dx * t, start[1] + dy * t, t


def ray_points(start, end, step=WP_STEP_M):
    """Points from start (excluded) to end (included), at most step apart."""
    d = math.hypot(end[0] - start[0], end[1] - start[1])
    n = max(1, math.ceil(d / step))
    return [(start[0] + (end[0] - start[0]) * k / n, start[1] + (end[1] - start[1]) * k / n) for k in range(1, n + 1)]


def walk_entry(label, spawn, deg, wps, length, ground, gsha):
    return {"label": label, "travel": f"coc {SPAWN_COC}", "spawn_local": list(spawn),
            "start": list(wps[0][:3]), "waypoints": wps, "ground": ground, "ground_sha256": gsha,
            "goal_radius": 5.0, "max_leg_m": 15.0, "speed": WALK_SPEED, "z_tol": 0.6, "fell_m": 3.0,
            "offroute_m": OFFROUTE_M, "stuck_m": 0.6, "stuck_k": 3, "shot_every": 3, "time_of_day": 12,
            "fresh": True, "length_m": round(length, 2), "max_legs": min(400, int(math.ceil(length / 8.0)) + 40),
            "expect": "FAIL BOUNDARY or PASS",
            "basis": f"a straight walk on heading {deg:g} from the Red Rocket arrival: a BOUNDARY stop is where the "
                     f"border is on this line; PASS means no border within {length:.0f} m"}


def cmd_plan(a):
    import walk_route as wr
    out = os.path.abspath(a.out)
    if os.path.exists(out):
        sys.exit(f"{out} exists: plan writes a new folder only")
    core = os.path.abspath(a.core)
    first = load(os.path.join(core, "plan.json"))[0]
    if first.get("coc") != SPAWN_COC:
        sys.exit(f"{core}: plan.json's first entry is not the {SPAWN_COC} arrival")
    spawn = [float(v) for v in first["spawn_local"]]
    objects = load(os.path.join(core, "objects.json"))
    _prm, ov = __import__("make_core64c").core_params(core)
    terrain = __import__("make_core64c").Terrain(os.path.join(core, *ov["btd_file"].split("/")))
    lo = terrain.origin + EDGE_MARGIN_M
    hi = terrain.origin + (terrain.raw.shape[0] - 1) * wr.tg.SF_STEP_M - EDGE_MARGIN_M
    box = (lo, lo, hi, hi)
    os.makedirs(out)
    plan, rays = [], []
    for k in range(a.rays):
        deg = (a.first_heading + 360.0 * k / a.rays) % 360.0
        ex, ey, length = ray_end(spawn, deg, a.length_m, box)
        if length < 2 * WP_STEP_M:
            print(f"  heading {deg:g}: the terrain ends {length:.0f} m away, skipped")
            continue
        area = (min(spawn[0], ex) - CORRIDOR_M, min(spawn[1], ey) - CORRIDOR_M,
                max(spawn[0], ex) + CORRIDOR_M, max(spawn[1], ey) + CORRIDOR_M)
        world, terr, _p, _o, btd_path = wr.core_world(core, area, objects)
        pts = ray_points(spawn, (ex, ey))
        wps = [[round(spawn[0], 4), round(spawn[1], 4), round(spawn[2], 3), 3.0, 1]]
        for n, (x, y) in enumerate(pts):
            last = n == len(pts) - 1
            wps.append([round(x, 4), round(y, 4), round(float(world.ground(x, y)), 3), 5.0 if last else 3.0,
                        1 if last else 0])
        corners = [(spawn[0], spawn[1], spawn[2]), (ex, ey, wps[-1][2])]
        name = f"ground_h{int(round(deg)):03d}.json"
        save(os.path.join(out, name), wr.ground_file(world, terr, btd_path, corners, corridor=CORRIDOR_M), indent=None)
        gsha = wr.sha256(os.path.join(out, name))
        label = f"border_h{int(round(deg)):03d}"
        plan.append(walk_entry(label, spawn, deg, wps, length, name, gsha))
        rays.append({"label": label, "heading": deg, "end_local": [round(ex, 3), round(ey, 3)],
                     "length_m": round(length, 1), "ground": name})
        print(f"  {label}: {length:.0f} m to ({ex:.0f}, {ey:.0f}) local, {len(wps)} waypoints")
        del world
    save(os.path.join(out, "plan.json"), plan)
    save(os.path.join(out, "rays.json"), {"core": core, "spawn_local": spawn, "box_local": box, "rays": rays})
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write("Border walk (scripts/bridge/border_walk.py, Claude): one straight walk per ray from the Red Rocket "
                "arrival; the runner stops a walk on BOUNDARY REACHED.\n"
                f"spawn (local) {spawn}; {len(plan)} rays of at most {a.length_m:g} m, clipped {EDGE_MARGIN_M:g} m "
                "inside the terrain.\n\n"
                + "".join(f"{r['label']}: heading {r['heading']:g}, {r['length_m']} m, to local {r['end_local']}\n"
                          for r in rays)
                + "\nPlan as the Red Rocket walks (testqueue.py plan-walk --exp-dir <this folder>), run with "
                  "--max-attempts 1, then border_walk.py report.\n")
    print(f"planned {out}: {len(plan)} walk tests")
    return 0


# ---------------------------------------------------------------------------------------------------------- report
def parse3(s):
    v = str(s or "").split()
    if len(v) != 3:
        return None
    try:
        p = [float(x) for x in v]
    except ValueError:
        return None
    return p if all(math.isfinite(x) for x in p) else None


def ray_result(test, obs):
    """One ray's summary from its walk observations: the stop, the last read and the popup's leg."""
    legs = [x for x in obs.get("legs") or [] if isinstance(x, dict)]
    reads = [(x, parse3(x.get("used") or x.get("read"))) for x in legs]
    reads = [(x, p) for x, p in reads if p is not None]
    popup = next((x for x in legs if re.search(r"BOUNDARY|REACHED", str(x.get("popup") or ""), re.I)), None)
    before = [p for x, p in reads if popup is None or (x.get("n") or 0) <= (popup.get("n") or 0)]
    arrival = parse3(obs.get("spawn_read")) or (reads[0][1] if reads else None)
    last = before[-1] if before else None
    stop = obs.get("walk_stopped") or ""
    if popup is not None:
        stop = "boundary"
    shots = [x.get("shot") for x in legs if x.get("shot")]
    r = {"label": test.get("ref") or test.get("id"), "stop": stop or "none recorded", "legs": len(legs),
         "arrival": arrival, "last": last, "popup_leg": popup.get("n") if popup else None,
         "popup_text": str(popup.get("popup")).strip()[:80] if popup else "",
         "popup_shot": (popup.get("shot") or popup.get("popup_shot")) if popup else None,
         "last_shot": shots[-1] if shots else None}
    if arrival and last:
        dx, dy = last[0] - arrival[0], last[1] - arrival[1]
        r["dist_m"] = round(math.hypot(dx, dy), 1)
        r["bearing"] = round(math.degrees(math.atan2(dx, dy)) % 360.0, 1)
    return r


def latest_attempt(qdir, test_id):
    """The test's newest attempt folder a<n> (door_rounds.latest_attempt): an interrupted attempt's renamed folder
    (a1_interrupted...) never counts (Codex on #444)."""
    d = os.path.join(qdir, "tests", test_id)
    tries = sorted((int(m.group(1)), n) for n in (os.listdir(d) if os.path.isdir(d) else [])
                   for m in [re.fullmatch(r"a(\d+)", n)] if m)
    return os.path.join(d, tries[-1][1]) if tries else None


def svg_map(results, offset, markers, extra, path):
    pts = [p for r in results for p in (r["arrival"], r["last"]) if p] + [e[1] for e in extra]
    if not pts:
        return
    x0, x1 = min(p[0] for p in pts) - 400, max(p[0] for p in pts) + 400
    y0, y1 = min(p[1] for p in pts) - 400, max(p[1] for p in pts) + 400
    W = 900.0
    s = W / max(x1 - x0, y1 - y0)
    H = (y1 - y0) * s

    def X(x):
        return (x - x0) * s

    def Y(y):
        return H - (y - y0) * s
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" '
           f'viewBox="0 0 {W:.0f} {H:.0f}" font-family="sans-serif" font-size="11">',
           f'<rect width="{W:.0f}" height="{H:.0f}" fill="#f4f1ea"/>']
    for m in markers:
        if x0 <= m[1] <= x1 and y0 <= m[2] <= y1:
            out.append(f'<circle cx="{X(m[1]):.1f}" cy="{Y(m[2]):.1f}" r="2" fill="#888"/>'
                       f'<text x="{X(m[1]) + 3:.1f}" y="{Y(m[2]) - 3:.1f}" fill="#777">{m[0]}</text>')
    for r in results:
        a, b = r["arrival"], r["last"]
        if not (a and b):
            continue
        col = "#c0392b" if r["stop"] == "boundary" else "#2c7a7b"
        out.append(f'<line x1="{X(a[0]):.1f}" y1="{Y(a[1]):.1f}" x2="{X(b[0]):.1f}" y2="{Y(b[1]):.1f}" '
                   f'stroke="{col}" stroke-width="2"/>')
        if r["stop"] == "boundary":
            out.append(f'<path d="M{X(b[0]) - 6:.1f},{Y(b[1]) - 6:.1f} l12,12 m0,-12 l-12,12" stroke="#c0392b" '
                       f'stroke-width="3"/>')
        out.append(f'<text x="{X(b[0]) + 8:.1f}" y="{Y(b[1]) + 4:.1f}" fill="{col}">{r["label"]} {r["stop"]} '
                   f'{r.get("dist_m", "?")} m</text>')
    for name, p in extra:
        out.append(f'<rect x="{X(p[0]) - 5:.1f}" y="{Y(p[1]) - 5:.1f}" width="10" height="10" fill="#8e44ad"/>'
                   f'<text x="{X(p[0]) + 8:.1f}" y="{Y(p[1]) + 4:.1f}" fill="#8e44ad">{name}</text>')
    a = next((r["arrival"] for r in results if r["arrival"]), None)
    if a:
        out.append(f'<circle cx="{X(a[0]):.1f}" cy="{Y(a[1]):.1f}" r="6" fill="#1a5276"/>'
                   f'<text x="{X(a[0]) + 9:.1f}" y="{Y(a[1]) - 8:.1f}" fill="#1a5276">Red Rocket arrival</text>')
    out.append(f'<text x="8" y="{H - 8:.0f}" fill="#333">game world frame (getpos metres), north up; red cross = '
               f'Boundary Reached; teal = walk ended for another reason</text></svg>')
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def cmd_report(a):
    q = load(os.path.join(a.queue, "queue.json"))
    rays = load(os.path.join(a.plan, "rays.json"))
    labels = {r["label"] for r in rays["rays"]}
    results = []
    for t in q.get("tests") or []:
        if t.get("kind") != "walk" or t.get("ref") not in labels:
            continue
        d = latest_attempt(a.queue, t["id"])
        obs = load(os.path.join(d, "obs.json")) if d and os.path.exists(os.path.join(d, "obs.json")) else {}
        results.append(ray_result(t, obs))
    offset = None
    for r in results:
        if r["arrival"]:
            offset = [r["arrival"][k] - rays["spawn_local"][k] for k in range(2)]
            break
    markers = []
    if a.markers:
        with open(a.markers, encoding="utf-8") as f:
            markers = [(m["name"], float(m["world_x"]), float(m["world_y"])) for m in csv.DictReader(f)]
    extra = []
    for e in a.extra or []:
        name, xy = e.rsplit(":", 1)
        extra.append((name, [float(v) for v in xy.split(",")]))
    rows = []
    for r in results:
        loc = [round(r["last"][k] - offset[k], 1) for k in range(2)] if r["last"] and offset else None
        rows.append([r["label"], r["stop"], r["legs"], r.get("dist_m"), r.get("bearing"),
                     *(r["last"][:2] if r["last"] else ["", ""]), *(loc or ["", ""]), r["popup_text"],
                     r["popup_shot"] or "", r["last_shot"] or ""])
        print(f"{r['label']:14s} {r['stop']:10s} {r.get('dist_m', '?')} m on bearing {r.get('bearing', '?')}; "
              f"last read {r['last']}" + (f"; popup {r['popup_text']!r} ({r['popup_shot']})" if r["popup_leg"] is not None else ""))
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["ray", "stop", "legs", "dist_m", "bearing", "world_x", "world_y", "local_x", "local_y",
                        "popup", "popup_shot", "last_shot"])
            w.writerows(rows)
    if a.svg:
        svg_map(results, offset, markers, extra, a.svg)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--core", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--rays", type=int, default=8)
    p.add_argument("--length-m", type=float, default=1200.0)
    p.add_argument("--first-heading", type=float, default=0.0)
    r = sub.add_parser("report")
    r.add_argument("--queue", required=True)
    r.add_argument("--plan", required=True)
    r.add_argument("--markers")
    r.add_argument("--extra", action="append", help='"label:x,y" in the game world frame')
    r.add_argument("--svg")
    r.add_argument("--csv")
    a = ap.parse_args(argv)
    return cmd_plan(a) if a.cmd == "plan" else cmd_report(a)


if __name__ == "__main__":
    sys.exit(main())
