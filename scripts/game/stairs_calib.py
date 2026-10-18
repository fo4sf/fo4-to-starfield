"""Check the offline walk (src/fo4sf/walksim.py) against what the game did, and replay planned stairs routes.

usage:
  python stairs_calib.py results --queue <queue dir> [--queue <queue dir> ...] --staging <pinned build> --fo4-data <FO4 Data>
                                 [--scene converted|planner] [--movables] [--speed 4.6] [--json out.json]
  python stairs_calib.py routes  --routes-dir <dir> [--prefix routesfull_] --staging <pinned build> --fo4-data <FO4 Data>
                                 [--scene converted|planner] [--movables] [--json out.json]

results: every decided stairs test of the queues (final verdict PASS or FAIL) is walked offline from its route's
teleport point (push-out of an overlapping start allowed, as the game does; bare capsule; walk_ms at --speed), and the
offline verdict is compared with the game's. A stop (STUCK / FALL) agrees only when the offline walk also ends where
the game read the player: within PLACE_XY metres across and PLACE_Z up or down (QA on PR #111: batch_full 0002 counted
as an agreement while the offline walk stopped at the start, 1.9 m from where the game stopped).
routes: every stairs route of the route files is replayed the same way. The planner keeps only lanes the walk climbs,
so a PASS here shows the files are consistent with the build's converted collision, not that the routes are right.

Scenes: "converted" reads the build's converted collision (fo4sf.sfbodies on <staging>/meshes); "planner" is the
planner's own scene (routes.walk_scene: FO4's collision, steep helpers flattened as the converter does). Both place
references with routes.ref_matrix, leave out initially disabled references and doors open by default, and leave out
movable objects unless --movables.
"""
import argparse
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
sys.path.insert(0, HERE)
from fo4sf import pipeline, sfbodies, walksim  # noqa: E402
import routes  # noqa: E402

PLACE_XY = 0.75      # metres: the offline stop and the game's read end this close across
PLACE_Z = 0.5        # and this close in height
DECIDED = ("PASS", "FAIL")


def load(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def parse3(s):
    try:
        v = [float(x) for x in str(s).split()]
    except ValueError:
        return None
    return v if len(v) == 3 else None


class ConvertedCell:
    """The converted collision of one cell of a staging build, per placed reference (sfbodies read-back)."""

    def __init__(self, staging, cell, items, movables=False):
        self.staging, self.cell, self.items, self.movables = staging, cell, items, movables
        self.cache = {}

    def bodies(self, key):
        if key not in self.cache:
            it = self.items.get(key)
            out = []
            p = os.path.join(self.staging, "meshes", it["model"]) if it and it.get("model") else None
            if p and os.path.exists(p):
                try:
                    with open(p, "rb") as f:
                        for b in sfbodies.nif_bodies(f.read()):
                            if b["layer"] in walksim.BLOCKING_LAYERS and b["triangles"]:
                                out.append(np.array(b["triangles"], float).reshape(-1, 3, 3))
                except Exception:                          # noqa: BLE001  (an unreadable model has no collision here)
                    out = []
            reach = max((float(np.hypot(T[..., 0], T[..., 1]).max()) for T in out), default=0.0)
            self.cache[key] = (out, reach)
        return self.cache[key]

    def scene(self, centre, radius):
        tris, owners = [], []
        for r in self.cell["refs"]:
            if not r.get("model") or r.get("type") == "Light" or r.get("disabled"):
                continue
            key = "meshes\\" + r["model"].lstrip("\\").lower()
            item = self.items.get(key)
            if item is None or (r.get("type") == "Door" and r.get("open_by_default")):
                continue
            if item.get("movable") and not self.movables:
                continue
            out, reach = self.bodies(key)
            if not out:
                continue
            sc = r.get("scale", 1.0) or 1.0
            pos = np.array(r["pos"], float) * routes.UNIT
            if math.hypot(pos[0] - centre[0], pos[1] - centre[1]) > radius + reach * sc + 0.1:
                continue
            R = np.array(routes.ref_matrix(r["rot"]), float).reshape(3, 3)
            name = f"{os.path.basename(r['model'].replace(chr(92), '/'))[:-4]}/{r['formkey'].split(':')[0]}"
            for T in out:
                P = (T * sc) @ R.T + pos
                lo, hi = P.min(axis=1), P.max(axis=1)
                ok = (lo[:, 0] <= centre[0] + radius) & (hi[:, 0] >= centre[0] - radius) & \
                     (lo[:, 1] <= centre[1] + radius) & (hi[:, 1] >= centre[1] - radius)
                if ok.any():
                    tris.append(P[ok])
                    owners += [name] * int(ok.sum())
        return walksim.Scene(np.concatenate(tris) if tris else np.zeros((0, 3, 3)), owners)


class Scenes:
    """Walk scenes around routes, per cell, from the converted build or from the planner."""

    def __init__(self, staging, fo4_data, which="converted", movables=False):
        self.staging, self.which, self.movables = staging, which, movables
        self.items = {it["source"].lower(): it for it in load(os.path.join(staging, "manifest.json"))["items"]}
        self.src = pipeline.Fo4Archives(fo4_data) if which == "planner" else None
        self.cells, self.tri_cache = {}, {}

    def around(self, cellname, route):
        if cellname not in self.cells:
            cell = load(os.path.join(self.staging, cellname + ".json"))
            self.cells[cellname] = (cell, ConvertedCell(self.staging, cell, self.items, self.movables))
        cell, conv = self.cells[cellname]
        start, hi = np.array(route["start"], float), np.array(route["expect"]["high"], float)
        centre = (start + hi) / 2
        radius = float(np.hypot(*(hi - start)[:2])) / 2 + 4.0
        if self.which == "converted":
            return conv.scene(centre, radius)
        items = self.items if not self.movables else {k: dict(v, movable=None) for k, v in self.items.items()}
        return routes.walk_scene(cell, (centre[0], centre[1]), radius, self.src, items, self.tri_cache)


def replay(scene, route, speed=routes.RUN_SPEED):
    """(verdict, why, walk) of one stairs route walked offline as the game would walk it: the start pushed out of an
    overlap (walksim.START_NUDGE), the bare capsule, walk_ms at `speed`."""
    lo = route["expect"]["low"]
    w = walksim.walk(scene, route["start"], route["heading"], route["walk_ms"] / 1000.0 * speed)
    if not w["ok_start"]:
        if w["void"]:
            return "FALL", "no floor at the start", w
        return "STUCK", "start blocked by " + ", ".join(w["start_by"][:2]), w
    rise = w["end"][2] - lo[2]
    if w["void"] or w["end"][2] < lo[2] - 0.5:
        return "FALL", f"end z {w['end'][2]:.2f}", w
    if rise >= route["expect"]["min_rise"]:
        return "PASS", f"rise {rise:.2f}" + (f", lifted {w['lift']:.2f}" if w["lift"] > walksim.STEP_UP else ""), w
    return "STUCK", f"rise {rise:.2f}, stopped by {w['stopped_by']}", w


def agreement(game, sim, game_end, sim_end):
    """"same" (same verdict; for a stop also the same place), "verdict" (same verdict, another place) or "no"."""
    if game != sim:
        return "no"
    if game == "PASS":
        return "same"
    if game_end is None or sim_end is None:
        return "verdict"
    dxy = math.hypot(game_end[0] - sim_end[0], game_end[1] - sim_end[1])
    return "same" if dxy <= PLACE_XY and abs(game_end[2] - sim_end[2]) <= PLACE_Z else "verdict"


def decided_results(queue_dir):
    """[(test, record, obs)] of the queue's stairs tests whose final verdict is PASS or FAIL."""
    q = load(os.path.join(queue_dir, "queue.json"))
    tests = {t["id"]: t for t in q["tests"] if t["kind"] == "stairs"}
    final = {}
    p = os.path.join(queue_dir, "results.jsonl")
    if os.path.exists(p):
        with open(p, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    if r.get("id") in tests:
                        final[r["id"]] = r
    out = []
    for tid, r in sorted(final.items()):
        if r.get("verdict") not in DECIDED:
            continue
        obs_p = os.path.join(r.get("dir") or "", "obs.json")
        obs = load(obs_p) if os.path.exists(obs_p) else {}
        out.append((tests[tid], r, obs))
    return out


def cmd_results(a):
    scenes = Scenes(a.staging, a.fo4_data, a.scene, a.movables)
    rows, tally = [], {}
    for qd in a.queue:
        for t, rec, obs in decided_results(qd):
            route = load(t["routes_file"])["routes"][t["route_index"]]
            sim, why, w = replay(scenes.around(t["cell"], route), route, a.speed)
            game = rec["class"] if rec["verdict"] == "FAIL" else "PASS"
            res = obs.get("result") or {}
            game_end = parse3(res.get("end_read"))
            sim_end = [round(float(x), 2) for x in w["end"]] if w["end"] else None
            agree = agreement(game, sim, game_end, sim_end)
            tally[agree] = tally.get(agree, 0) + 1
            off = (round(math.hypot(game_end[0] - sim_end[0], game_end[1] - sim_end[1]), 2)
                   if game_end and sim_end else None)
            rows.append({"queue": os.path.basename(os.path.normpath(qd)), "id": t["id"], "cell": t["cell"],
                         "ref": t["ref"], "model": t["model"].split("\\")[-1], "game": game, "detail": rec.get("detail"),
                         "sim": sim, "why": why, "agree": agree, "game_start": parse3(res.get("start_read")),
                         "game_end": game_end, "sim_end": sim_end, "end_apart_xy": off, "lift": round(w["lift"], 2),
                         "nudge": w["nudge"], "walked": round(w["walked"], 2)})
            print(f"{t['id'][:44]:44s} game {game:5s} sim {sim:5s} {agree:7s} | {why} | sim_end {sim_end} "
                  f"game_end {game_end} apart {off}")
    n = len(rows)
    print(f"{n} decided stairs results ({a.scene} scene{', movables in' if a.movables else ''}): "
          f"same verdict {tally.get('same', 0) + tally.get('verdict', 0)}, same verdict and place "
          f"{tally.get('same', 0)}, another place {tally.get('verdict', 0)}, another verdict {tally.get('no', 0)}")
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"scene": a.scene, "movables": a.movables, "place_xy": PLACE_XY, "place_z": PLACE_Z,
                       "tally": tally, "rows": rows}, f, indent=1)


def cmd_routes(a):
    scenes = Scenes(a.staging, a.fo4_data, a.scene, a.movables)
    rows, tally = [], {}
    for fn in sorted(os.listdir(a.routes_dir)):
        if not (fn.startswith(a.prefix) and fn.endswith(".json")):
            continue
        cellname = fn[len(a.prefix):-5]
        for k, route in enumerate(load(os.path.join(a.routes_dir, fn))["routes"]):
            if route["kind"] != "stairs":
                continue
            sim, why, w = replay(scenes.around(cellname, route), route, a.speed)
            if sim == "PASS" and w["lift"] > walksim.STEP_UP:
                sim = "PASS-LIFT"
            tally[sim] = tally.get(sim, 0) + 1
            rows.append({"cell": cellname, "index": k, "ref": route["ref"], "probe": route.get("probe"),
                         "model": route["model"].split("\\")[-1], "sim": sim, "why": why, "nudge": w["nudge"],
                         "sim_end": [round(float(x), 2) for x in w["end"]] if w["end"] else None,
                         "planned_sim_end": route.get("sim_end"),
                         "helper_crossing": route.get("helper_crossing"), "movable_near": route.get("movable_near")})
            if sim != "PASS" or w["nudge"]:
                print(rows[-1])
    print(f"{len(rows)} stairs routes replayed ({a.scene} scene): {tally}")
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"scene": a.scene, "movables": a.movables, "tally": tally, "rows": rows}, f, indent=1)


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("results", "routes"):
        p = sub.add_parser(name)
        p.add_argument("--staging", required=True)
        p.add_argument("--fo4-data", required=True)
        p.add_argument("--scene", choices=("converted", "planner"), default="converted")
        p.add_argument("--movables", action="store_true", help="keep movable objects in the scene")
        p.add_argument("--speed", type=float, default=routes.RUN_SPEED)
        p.add_argument("--json", default="")
        if name == "results":
            p.add_argument("--queue", action="append", required=True)
        else:
            p.add_argument("--routes-dir", required=True)
            p.add_argument("--prefix", default="routesfull_")
    a = ap.parse_args(argv)
    (cmd_results if a.cmd == "results" else cmd_routes)(a)


if __name__ == "__main__":
    main()
