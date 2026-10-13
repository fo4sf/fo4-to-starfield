"""The walk kind (docs/terrain/walk-redrocket-sanctuary.md): steering for qstep.ps1 and the judge for testqueue.py.

usage (qstep.ps1, one call per leg; plain Python, no numpy):
  python walk_eval.py init  --spec <spec.json> --state <walk_state.json> --offset "ox oy oz"
  python walk_eval.py steer --spec <spec.json> --state <walk_state.json> --read "x y z" [--reread]
steer prints one JSON object: {"action": "aim" | "reread" | "done" | "stop", "heading", "hold_ms", "wp", "dist",
"reason", ...}. qstep.ps1 types only "player.setangle z <heading>" and holds W for hold_ms (both validated again there);
it never types a setpos during the walk.

The player walks with real input from the coc arrival (or, for the reverse test, from a setup teleport made before the
walk starts) over the planned waypoints (scripts/terrain/walk_route.py, core64c's local frame; the game's frame is that
plus the overlay's merge offset O = arrival read - spawn_local). Each leg: read the position (console getpos), aim at the
next waypoint not yet reached (player.setangle z), or straight past waypoints the plan does not keep (a waypoint's
fifth value 0) while they lie within LOOK_TOL of the line, hold W for the time that distance (at most max_leg_m) takes
at the measured speed, check the HUD and the screen centre for a popup ("BOUNDARY REACHED"). The controller counts a
waypoint as reached within its radius or once the player has passed it along the route (a kept one only within twice
its radius), measures the speed,
steps aside (+-50 degrees for 1 s) after a leg without movement, and stops on: the goal, stuck (stuck_k legs without
movement, or PROGRESS_LEGS legs without PROGRESS_M of progress along the route), off the route (offroute_m), far below
the route (FELL_STOP: falling through the world), a confirmed jump (two reads agreeing on a move no walk can make),
the leg budget.

The judge decides from the raw reads alone (testqueue.py judge -> judge here): PASS only when the last read is within
goal_radius of the goal, every leg was read, every move between two reads is plausible for walking, every read stands
within z_tol on the terrain (core64c's BTD) or on a converted object's surface (walk_ground.json, its sha256 pinned in
the test), every planned cell border was crossed between two reads, at least bridge.min_reads reads stood on the bridge
deck with reads before and after it, nothing but the walk's own console commands was typed, no popup was seen and the
screenshots exist. FAIL classes: BOUNDARY (the popup), FELL (through the terrain, or off the route's surface, e.g. the
bridge), HEIGHTS (below the ground by more than z_tol), JUMP (a confirmed move no walk makes), OFFROUTE, STUCK.
Everything else that keeps it from a PASS is INCONCLUSIVE (UNREAD, READ, OFFGROUND, HUDGAP, NOHUD, NOTREACHED,
CROSSING, BRIDGE, NOSHOT, TYPED, START, ANCHOR, GROUND).
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys

V_MAX = 9.0           # m/s: faster than any run or sprint (the player runs about 4.6 m/s)
SLACK_S = 2.0         # s added to every hold for the moves it cannot account for (start, stop, a step down)
JUMP_MIN = 1.0        # m
FELL_STOP = 15.0      # m below the route: the step stops walking (the judge's limit is the test's fell_m)
PROGRESS_LEGS = 6     # legs without PROGRESS_M of progress along the route = stuck
PROGRESS_M = 1.0
DETOUR_DEG = 50.0
DETOUR_MS = 1000
V_LO, V_HI = 1.5, 8.0
MIN_HOLD_MS = 400
MAX_HOLD_MS = 8000    # input.ps1 holdg takes at most 10 s
AGREE_M = 1.0         # two reads within this agree (a confirmed position)
LOOK_TOL = 1.0        # m: a waypoint the plan does not keep may be walked past when it lies this close to the leg
WALK_CMD = re.compile(r"(ClearConsole|player\.getpos [xyz]|player\.setangle [xz] -?\d{1,3}(\.\d{1,2})?)")


# ------------------------------------------------------------------------------------------------------------ geometry
def parse3(s):
    if not isinstance(s, str):
        return None
    v = s.split()
    if len(v) != 3:
        return None
    try:
        out = [float(x) for x in v]
    except ValueError:
        return None
    return out if all(math.isfinite(x) for x in out) else None


def heading(a, b):
    """Creation Engine z angle from a to b: 0 north (+y), 90 east (+x), degrees."""
    return math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) % 360.0


def project(poly, x, y):
    """(xy distance to the polyline, arc length of the closest point, segment index, t on it)."""
    best = (math.inf, 0.0, 0, 0.0)
    s0 = 0.0
    for k, (a, b) in enumerate(zip(poly, poly[1:])):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln2 = dx * dx + dy * dy
        ln = math.sqrt(ln2)
        t = 0.0 if ln2 < 1e-18 else max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / ln2))
        d = math.hypot(a[0] + t * dx - x, a[1] + t * dy - y)
        if d < best[0]:
            best = (d, s0 + t * ln, k, t)
        s0 += ln
    return best


def arc_lengths(poly):
    s = [0.0]
    for a, b in zip(poly, poly[1:]):
        s.append(s[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return s


def seg_dist(a, b, p):
    """xy distance from p to the segment a-b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln2 = dx * dx + dy * dy
    t = 0.0 if ln2 < 1e-18 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / ln2))
    return math.hypot(a[0] + t * dx - p[0], a[1] + t * dy - p[1])


def keep_of(w):
    """A waypoint the runner must read the player at (the plan's fifth value; a 4-value waypoint is always kept)."""
    return len(w) < 5 or bool(w[4])


def route_z(poly, x, y):
    """The planned ground z at the route point closest to (x, y) (waypoint z interpolated)."""
    _d, _s, k, t = project(poly, x, y)
    if len(poly) == 1:
        return poly[0][2]
    a, b = poly[k], poly[k + 1]
    return a[2] + (b[2] - a[2]) * t


def cell_of(x, y, cell=100.0):
    return (int(math.floor(x / cell)), int(math.floor(y / cell)))


# -------------------------------------------------------------------------------------------------------------- ground
class Ground:
    """walk_ground.json (scripts/terrain/walk_route.py ground_file): the core64c BTD window (bilinear, clamped at its
    edge, as make_core64c.Terrain) and the upward converted collision surfaces on a grid along the route."""

    def __init__(self, data):
        t = data["terrain"]
        self.tx0, self.ty0, self.tstep, self.rows = float(t["x0"]), float(t["y0"]), float(t["step"]), t["rows"]
        s = data["surfaces"]
        self.sx0, self.sy0, self.sstep = float(s["x0"]), float(s["y0"]), float(s["step"])
        self.nodes = s["nodes"]
        self.owners = data["owners"]
        self.path = data["path"]
        self.corridor = float(data["corridor_m"])

    def terrain(self, x, y):
        rows, cols = len(self.rows), len(self.rows[0])
        u = min(max((x - self.tx0) / self.tstep, 0.0), cols - 1.0)
        v = min(max((y - self.ty0) / self.tstep, 0.0), rows - 1.0)
        c, r = min(int(u), cols - 2), min(int(v), rows - 2)
        fu, fv = u - c, v - r
        h = self.rows
        return (h[r][c] * (1 - fu) * (1 - fv) + h[r][c + 1] * fu * (1 - fv) + h[r + 1][c] * (1 - fu) * fv
                + h[r + 1][c + 1] * fu * fv)

    def surfaces(self, x, y, r=0.75):
        """[(z, owner index)] of the surface nodes within r of (x, y)."""
        i0, i1 = math.floor((x - r - self.sx0) / self.sstep), math.ceil((x + r - self.sx0) / self.sstep)
        j0, j1 = math.floor((y - r - self.sy0) / self.sstep), math.ceil((y + r - self.sy0) / self.sstep)
        out = []
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                if math.hypot(self.sx0 + i * self.sstep - x, self.sy0 + j * self.sstep - y) > r:
                    continue
                for z, o in self.nodes.get(f"{i},{j}", ()):
                    out.append((z, o))
        return out

    def covered(self, x, y):
        return project(self.path, x, y)[0] <= self.corridor

    def classify(self, x, y, z, tol, fell):
        """(class, source, dz): ok (within tol of the terrain or of an object surface: source "terrain" or the
        object's EditorID), fell (more than fell below the terrain), low (below the terrain and every surface by
        more than tol), high (above or between the known surfaces), out (outside the corridor the file covers).
        dz: z minus the nearest candidate."""
        if not self.covered(x, y):
            return "out", None, None
        g = self.terrain(x, y)
        cands = [(g, "terrain")] + [(sz, self.owners[o]["edid"]) for sz, o in self.surfaces(x, y)]
        best = min(cands, key=lambda c: abs(z - c[0]))
        dz = z - best[0]
        if abs(dz) <= tol:
            return "ok", best[1], dz
        if z < g - fell:
            return "fell", "terrain", z - g
        if z < min(c[0] for c in cands) - tol:
            return "low", best[1], dz
        return "high", best[1], dz

    def owner_src(self, x, y, z, tol):
        """The FO4 reference (src) of the object surface within tol of z near (x, y), or None (terrain / nothing)."""
        best = None
        for sz, o in self.surfaces(x, y):
            if abs(z - sz) <= tol and (best is None or abs(z - sz) < best[0]):
                best = (abs(z - sz), self.owners[o]["src"])
        return None if best is None else best[1]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def load_ground(test):
    """(Ground, None) for the test's walk_ground.json when its sha256 is the planned one, else (None, why)."""
    p = test.get("ground_path") or ""
    if not p or not os.path.isfile(p):
        return None, f"ground file {p!r} not found"
    got = sha256(p)
    if got != test.get("ground_sha256"):
        return None, f"ground file {p} changed since planning (sha256 {got[:12]}, planned {str(test.get('ground_sha256'))[:12]})"
    with open(p, encoding="utf-8") as f:
        return Ground(json.load(f)), None


# ------------------------------------------------------------------------------------------------------------- steering
def init_state(test, offset):
    return {"offset": [float(v) for v in offset], "wp": 1 if len(test["waypoints"]) > 1 else 0, "legs": 0,
            "prev": None, "hold_prev": 0, "speed": float(test.get("speed", 4.6)), "still": 0, "pending": None,
            "best_s": None, "since_best": 0, "misreads": 0}


def steer(st, test, read, reread=False):
    """The next action for one position read (merged frame "x y z" or None). Updates st; returns a dict."""
    O = st["offset"]
    W = test["waypoints"]
    poly = [w[:3] for w in W]
    g = parse3(read) if isinstance(read, str) else (list(read) if read else None)
    if g is None:
        return {"action": "stop", "reason": "unread", "wp": st["wp"]}
    p = [g[k] - O[k] for k in range(3)]
    out = {"local": [round(v, 3) for v in p], "wp": st["wp"]}
    prev = st["prev"]
    if prev is not None:
        moved = math.hypot(p[0] - prev[0], p[1] - prev[1])
        limit = V_MAX * (st["hold_prev"] / 1000.0 + SLACK_S) + JUMP_MIN
        if moved > limit:
            if not reread:
                st["pending"] = p
                return dict(out, action="reread", reason=f"moved {moved:.1f} m after a {st['hold_prev']} ms hold "
                                                          f"(limit {limit:.1f} m)")
            first = st["pending"]
            st["pending"] = None
            if first is not None and math.dist(first, p) <= AGREE_M:
                return dict(out, action="stop", reason="jump", moved=round(moved, 2), confirmed=True)
            return dict(out, action="stop", reason="jump_unconfirmed", moved=round(moved, 2), confirmed=False)
        if reread and st["pending"] is not None:
            st["misreads"] += 1                       # the first read was implausible, this one is not
        st["pending"] = None
    d_route, s_now, _k, _t = project(poly, p[0], p[1])
    if d_route > float(test.get("offroute_m", 10.0)):
        return dict(out, action="stop", reason="offroute", off_m=round(d_route, 2))
    if p[2] < route_z(poly, p[0], p[1]) - FELL_STOP:
        return dict(out, action="stop", reason="fell", below_m=round(route_z(poly, p[0], p[1]) - p[2], 2))
    S = arc_lengths(poly)
    wp = st["wp"]
    while wp < len(W):
        d = math.hypot(p[0] - W[wp][0], p[1] - W[wp][1])
        if d <= W[wp][3]:
            wp += 1
            continue
        if wp < len(W) - 1:
            # passed along the route (measured on the nearby segments only: the route may come back close to
            # itself); a waypoint to keep only when the player went by it within twice its radius
            lo, hi = max(0, wp - 1), min(len(W) - 1, wp + 3)
            s_here = S[lo] + project(poly[lo:hi + 1], p[0], p[1])[1]
            if s_here >= S[wp] + 0.25 and (not keep_of(W[wp]) or d <= max(2 * W[wp][3], 3.0)):
                wp += 1
                continue
        break
    st["wp"] = wp
    out["wp"] = wp
    if wp >= len(W):
        return dict(out, action="done", reason="goal")
    if prev is not None and st["hold_prev"] >= MIN_HOLD_MS:
        moved = math.hypot(p[0] - prev[0], p[1] - prev[1])
        st["still"] = st["still"] + 1 if moved < float(test.get("stuck_m", 0.6)) else 0
        if st["hold_prev"] >= 800 and moved >= 1.0 and not st.get("detoured"):
            v = moved / (st["hold_prev"] / 1000.0)
            st["speed"] = min(V_HI, max(V_LO, 0.5 * st["speed"] + 0.5 * v))
    if st["best_s"] is None or s_now >= st["best_s"] + PROGRESS_M:
        st["best_s"], st["since_best"] = s_now, 0
    else:
        st["since_best"] += 1
    if st["still"] >= int(test.get("stuck_k", 3)) or st["since_best"] >= PROGRESS_LEGS:
        return dict(out, action="stop", reason="stuck", still=st["still"], since_best=st["since_best"])
    if st["legs"] >= int(test.get("max_legs", 60)):
        return dict(out, action="stop", reason="legs")
    st["detoured"] = st["still"] >= 1
    max_leg = float(test.get("max_leg_m", 15.0))
    k = wp
    if not st["detoured"]:
        # one straight leg past waypoints the plan does not need a read at, while they stay on the line (LOOK_TOL)
        while k + 1 < len(W) and not keep_of(W[k]) and \
                math.hypot(p[0] - W[k + 1][0], p[1] - W[k + 1][1]) <= max_leg and \
                all(seg_dist(p, W[k + 1], W[j]) <= LOOK_TOL for j in range(wp, k + 1)):
            k += 1
    target = W[k]
    dist = math.hypot(p[0] - target[0], p[1] - target[1])
    h = heading(p, target)
    if st["detoured"]:
        h = (h + (DETOUR_DEG if st["still"] % 2 == 1 else -DETOUR_DEG)) % 360.0
        hold = DETOUR_MS
    else:
        hold = int(min(MAX_HOLD_MS, max(MIN_HOLD_MS, min(dist, max_leg) / st["speed"] * 1000.0)))
    st["legs"] += 1
    st["prev"], st["hold_prev"] = p, hold
    return dict(out, action="aim", heading=round(h, 1), hold_ms=hold, dist=round(dist, 2), target=k,
                detour=st["detoured"], speed=round(st["speed"], 2), route_s=round(s_now, 1))


# ---------------------------------------------------------------------------------------------------------------- judge
def judge(test, obs, shot_ok, ground=None):
    """(verdict, class, detail) of one walk test from its raw observations (module doc)."""
    if not obs.get("offset"):
        why = obs.get("offset_missing") or "the arrival was not read or never settled"
        return "INCONCLUSIVE", "ANCHOR", f"no merge offset ({why}): no walk"
    if ground is None:
        ground, why = load_ground(test)
        if ground is None:
            return "INCONCLUSIVE", "GROUND", why
    O = (list(obs["offset"]) + [0.0, 0.0, 0.0])[:3]
    W = test["waypoints"]
    poly = [w[:3] for w in W]
    tol, fell = float(test.get("z_tol", 0.6)), float(test.get("fell_m", 3.0))
    notes = [f"offset {O[0]:.1f}, {O[1]:.1f}, {O[2]:.2f}"]
    if test.get("setup"):
        su = obs.get("setup") or {}
        sr = parse3(su.get("read"))
        st = test["start"]
        if sr is None or not su.get("settled"):
            return "INCONCLUSIVE", "START", "the setup teleport's landing was not read or never settled: no walk"
        d0 = math.hypot(sr[0] - O[0] - st[0], sr[1] - O[1] - st[1])
        if d0 > float(test.get("start_tol", 3.0)):
            return "INCONCLUSIVE", "START", f"the setup teleport landed {d0:.1f} m from the start: no walk"
        notes.append(f"setup teleport landed {d0:.2f} m from the start (setup, not walking evidence)")
    legs = [x for x in obs.get("legs") or [] if isinstance(x, dict)]
    if not legs:
        return "INCONCLUSIVE", "UNREAD", f"no leg was read; {'; '.join(notes)}"
    bad_cmd = [c for x in legs for c in x.get("cmds") or [] if not WALK_CMD.fullmatch(str(c))]
    reads, problems, fails = [], [], []
    held, gap = 0, 0                                  # walking time and legs since the last read
    prev = None
    for x in legs:
        n = x.get("n")
        used = parse3(x.get("used"))
        if x.get("popup") and re.search(r"BOUNDARY|REACHED", str(x.get("popup")), re.I):
            fails.append(("BOUNDARY", f"leg {n}: popup on screen: {str(x.get('popup'))[:80]!r}"))
        if used is None:
            problems.append(("UNREAD", f"leg {n}: position not read"))
            held += int(x.get("hold_ms") or 0)
            gap += 1
            continue
        p = [used[k] - O[k] for k in range(3)]
        if prev is not None:
            moved = math.hypot(p[0] - prev[0], p[1] - prev[1])
            limit = V_MAX * (held / 1000.0 + SLACK_S * (gap + 1)) + JUMP_MIN
            if moved > limit:
                if x.get("confirmed"):
                    fails.append(("JUMP", f"leg {n}: moved {moved:.1f} m after {held} ms of walking (limit {limit:.1f} "
                                          f"m), confirmed by a second read"))
                else:
                    problems.append(("READ", f"leg {n}: an implausible {moved:.1f} m move, not confirmed"))
        cls, src, dz = ground.classify(p[0], p[1], p[2], tol, fell)
        rz = route_z(poly, p[0], p[1])
        d_route = project(poly, p[0], p[1])[0]
        if d_route > float(test.get("offroute_m", 10.0)) or cls == "out":
            fails.append(("OFFROUTE", f"leg {n}: {d_route:.1f} m from the route"))
        elif cls == "fell":
            fails.append(("FELL", f"leg {n}: z {p[2]:.2f}, {-dz:.1f} m below the terrain: no ground there"))
        elif p[2] < rz - fell:
            fails.append(("FELL", f"leg {n}: z {p[2]:.2f}, {rz - p[2]:.1f} m below the route's surface there "
                                  f"({rz:.2f}): off the planned surface"))
        elif cls == "low":
            fails.append(("HEIGHTS", f"leg {n}: z {p[2]:.2f} is {-dz:.2f} m below the nearest ground ({src})"))
        elif cls == "high":
            problems.append(("OFFGROUND", f"leg {n}: z {p[2]:.2f} is {dz:+.2f} m from every known surface"))
        if x.get("hud") is False:
            problems.append(("HUDGAP", f"leg {n}: the HUD was gone for {x.get('hud_gap_s')} s"))
        reads.append({"n": n, "p": p, "cls": cls, "src": src, "dz": dz,
                      "on": ground.owner_src(p[0], p[1], p[2], tol) if cls == "ok" else None,
                      "s": project(poly, p[0], p[1])[1], "cell": cell_of(used[0], used[1])})
        prev, held, gap = p, int(x.get("hold_ms") or 0), 0
    stop = obs.get("walk_stopped") or ""
    last = reads[-1] if reads else None
    goal = W[-1]
    reached = last is not None and math.hypot(last["p"][0] - goal[0], last["p"][1] - goal[1]) <= float(
        test.get("goal_radius", 3.0))
    if stop == "stuck" and not reached:
        fails.append(("STUCK", f"no progress at {last['p'][0]:.1f}, {last['p'][1]:.1f} (route s {last['s']:.1f} of "
                               f"{test.get('length_m')} m)" if last else "no progress"))
    if stop == "offroute" and not any(c == "OFFROUTE" for c, _ in fails):
        fails.append(("OFFROUTE", "the step left the route"))
    if stop == "jump" and not any(c == "JUMP" for c, _ in fails):
        fails.append(("JUMP", "the step stopped on a confirmed jump"))
    walked = sum(math.hypot(b["p"][0] - a["p"][0], b["p"][1] - a["p"][1]) for a, b in zip(reads, reads[1:]))
    zs = [abs(r["dz"]) for r in reads if r["dz"] is not None and r["cls"] == "ok"]
    on_obj = sorted({r["src"] for r in reads if r["cls"] == "ok" and r["src"] != "terrain"})
    stats = (f"{len(reads)} reads over {len(legs)} legs, walked {walked:.1f} m of {test.get('length_m')} m, "
             f"|dz| max {max(zs) if zs else float('nan'):.2f} m on terrain/objects"
             + (f" (objects: {', '.join(on_obj[:6])}{'...' if len(on_obj) > 6 else ''})" if on_obj else "")
             + f", step stopped: {stop or 'no reason recorded'}")
    if fails:
        # the first failing leg decides, except that a popup on screen explains everything after it
        cls, why = next((f for f in fails if f[0] == "BOUNDARY"), fails[0])
        more = f" (+{len(fails) - 1} more)" if len(fails) > 1 else ""
        return "FAIL", cls, f"{why}{more}; {stats}; {'; '.join(notes)}"
    if bad_cmd:
        return "INCONCLUSIVE", "TYPED", f"typed during the walk: {bad_cmd[:3]}; {stats}"
    if stop == "jump_unconfirmed":
        problems.insert(0, ("READ", "two reads disagreed on an implausible move"))
    if stop == "nohud":
        problems.insert(0, ("NOHUD", "the HUD did not come back"))
    if problems:
        cls, why = problems[0]
        return "INCONCLUSIVE", cls, f"{why} ({len(problems)} problem(s)); {stats}; {'; '.join(notes)}"
    if not reached:
        return "INCONCLUSIVE", "NOTREACHED", (f"ended {math.hypot(last['p'][0] - goal[0], last['p'][1] - goal[1]):.1f} m "
                                              f"from the goal; {stats}; {'; '.join(notes)}")
    # the planned cell borders, in the game's frame: each crossed between two consecutive reads
    seen = list(zip([r["cell"] for r in reads], [r["cell"] for r in reads[1:]]))
    missing = []
    for c in test.get("crossings") or []:
        a = cell_of(c["from"][0] * 100.0 + O[0] + 50.0, c["from"][1] * 100.0 + O[1] + 50.0)
        b = cell_of(c["to"][0] * 100.0 + O[0] + 50.0, c["to"][1] * 100.0 + O[1] + 50.0)
        if (a, b) not in seen:
            missing.append(f"{a}->{b}")
    if missing:
        return "INCONCLUSIVE", "CROSSING", f"cell borders not seen between two reads: {missing}; {stats}"
    br = test.get("bridge") or {}
    if br:
        on = [r for r in reads if r["on"] == br.get("src")]
        span = br.get("span") or [0.0, 0.0]
        before = [r for r in reads if r["s"] < span[0] - 0.5]
        after = [r for r in reads if r["s"] > span[1] + 0.5]
        if len(on) < int(br.get("min_reads", 2)) or not before or not after:
            return ("INCONCLUSIVE", "BRIDGE", f"{len(on)} reads on the {br.get('edid')} deck ({len(before)} before, "
                    f"{len(after)} after it), need {br.get('min_reads', 2)} with reads on both sides; {stats}")
        notes.append(f"{len(on)} reads on the {br.get('edid')} deck")
    shots = [x.get("shot") for x in legs if x.get("shot")]
    if not shot_ok(obs.get("shot")) or not shots or not all(shot_ok(s) for s in shots):
        return "INCONCLUSIVE", "NOSHOT", f"a screenshot is missing ({len(shots)} leg shots); {stats}"
    cells = []
    for r in reads:
        if not cells or cells[-1] != r["cell"]:
            cells.append(r["cell"])
    notes.append(f"cells {' -> '.join(f'({c[0]},{c[1]})' for c in cells)}")
    return "PASS", "PASS", f"reached the goal ({math.hypot(last['p'][0] - goal[0], last['p'][1] - goal[1]):.1f} m); " \
                           f"{stats}; {'; '.join(notes)}"


# ------------------------------------------------------------------------------------------------------------------ CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("init", "steer"))
    ap.add_argument("--spec", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--offset", default="")
    ap.add_argument("--read", default="")
    ap.add_argument("--reread", action="store_true")
    a = ap.parse_args(argv)
    with open(a.spec, encoding="utf-8-sig") as f:
        test = json.load(f)
    if a.cmd == "init":
        off = parse3(a.offset)
        if off is None:
            print(json.dumps({"action": "stop", "reason": "bad offset"}))
            return 4
        st = init_state(test, off)
        out = {"action": "init", "wp": st["wp"]}
    else:
        with open(a.state, encoding="utf-8") as f:
            st = json.load(f)
        out = steer(st, test, a.read.strip() or None, a.reread)
    with open(a.state, "w", encoding="utf-8") as f:
        json.dump(st, f)
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
