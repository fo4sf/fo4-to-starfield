"""The playable slice's working door: the Red Rocket cave load door between the converted Commonwealth terrain (terrain
experiment 2d) and the converted interior RedRocket01 of the pinned build (docs/slice/redrocket-door.md).

    python scripts/slice/make_redrocket_door.py stage --fo4 <Fallout4.esm> --sf-esm <Starfield.esm> --port <build dir>
           --exp2d <terrain_exp2d> --out <slice folder>
    python scripts/slice/make_redrocket_door.py check --sf-esm <Starfield.esm> --port <build dir> --exp2d <terrain_exp2d>
           --out <slice folder>

stage  reads both ends of the Fallout 4 link from Fallout4.esm (dotnet/SliceDoor fo4: interior door 05E844 in
       RedRocket01, exterior door 08EB65 in the Commonwealth persistent cell, each with its XTEL), the vanilla automatic
       cave door (SliceDoor sf-door) and the converted cell as the build holds it (SliceDoor port); checks that exp2d
       does not place the exterior door already (it skipped it: editor marker model) and that the build has no
       interior door ref (the converter never places marker models); converts both ends to Starfield (position / 70,
       rotation and scale copied, XTEL arrival / 70) and measures them against the ground: the exterior against exp2d's
       BTD and converted collision, the interior against the build's converted collision; writes slice_params.json and
       builds FO4SliceRedRocket.esm with SliceDoor build; copies exp2d's plugins and Data tree (one install = terrain,
       objects, navmesh and the door); writes plan.json (one door_trip test), expected.json and README.txt.
check  SliceDoor check (Mutagen read-back with the masters, every link resolved, XTEL both ways), a raw byte compare of
       the three override records with their masters' records, the exp2d copies byte for byte, the plan through the
       runner's own door_test, and the load order the runner produces. Writes offline_check.json.
Everything this writes stays outside the repo (derived game data).
"""
import argparse
import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "scripts", "game"))
sys.path.insert(0, os.path.join(REPO, "scripts", "terrain"))
from fo4sf import exterior, sfbodies  # noqa: E402

UNITS = 70.0                                         # FO4 units per metre (PluginSpike, exp2c)
PLUGIN = "FO4SliceRedRocket.esm"
EXP2_PLUGINS = ("FO4TerrainExp2.esm", "FO4TerrainExp2_Mars.esm")
INNER, OUTER = "05E844", "08EB65"                    # Fallout4.esm: RedRocket01's door, the Commonwealth door
FO4_CELL = "RedRocket01"
PORT_CELL = "FO4Port_RedRocket01"
DOOR_BASE = {"plugin": "Starfield.esm", "id": "24F9CE", "editor_id": "AutoloadDoor_Cave"}
EDIDS = {"outside": "FO4SL_RedRocketCaveDoorExt", "inside": "FO4SL_RedRocketCaveDoorInt"}
SAVE = "fo4sf_slice_rrdoor"
NEAR_M = 1.0                                         # the last-try teleport: this far in front of the door
PLAN_KEYS = ("radius", "start_tol", "reload_tol", "ground_tol", "walk_ms", "walk_step_ms", "settle_ms", "drop",
             "near_wait_ms", "load_wait_s")
# the overlay's merge offset the last exp2d run measured (C:\Modding\testqueue\terrain_exp2d results.jsonl, a1,
# 2026-10-12 00:13: "offset -1200.0, -2699.8, 0.01 from spawn"); used only for the expected merged positions in
# expected.json / README, the runner measures its own at every arrival
LAST_OFFSET = (-1200.0, -2699.8, 0.01)


# ------------------------------------------------------------------------------------------------------------- frames
def metres(v):
    return [float(x) / UNITS for x in v]


def side(ref, edid):
    """A Starfield placement of one Fallout 4 door reference: position / 70 (metres), rotation copied (radians), scale
    copied, its XTEL arrival / 70 with its rotation and flags (TransitionInterior is never written: 0 of 964 vanilla
    XTELs set it)."""
    x = ref["xtel"]
    if x is None:
        raise ValueError(f"{ref['formid']}: no XTEL")
    if x.get("transition_interior"):
        raise ValueError(f"{ref['formid']}: XTEL with a transition interior is not handled")
    if int(x["flags"]) & ~7:
        raise ValueError(f"{ref['formid']}: unknown XTEL flag bits {x['flags']}")
    return {"edid": edid, "src": ref["formid"] + ":Fallout4.esm", "pos": [round(v, 5) for v in metres(ref["pos"])],
            "rot": [float(v) for v in ref["rot"]], "scale": float(ref["scale"] if ref["scale"] is not None else 1.0),
            "xtel": {"pos": [round(v, 5) for v in metres(x["pos"])], "rot": [float(v) for v in x["rot"]],
                     "flags": int(x["flags"])}}


def link_pair(doc, inner=INNER, outer=OUTER, cell=FO4_CELL):
    """(inner, outer) refs from SliceDoor fo4's JSON, checked: the interior one in `cell`, the exterior one in a
    worldspace's persistent cell, each XTEL naming the other, both persistent, the same DOOR base."""
    refs = {r["formid"]: r for r in doc["refs"]}
    i, o = refs.get(inner), refs.get(outer)
    if i is None or o is None:
        raise ValueError(f"Fallout4.esm: door {inner if i is None else outer} not found")
    problems = []
    if i["where"] != "interior" or i["cell_editor_id"] != cell:
        problems.append(f"{inner} is in {i['where']} {i['cell_editor_id']}, not interior {cell}")
    if "persistent cell" not in o["where"]:
        problems.append(f"{outer} is in {o['where']}, not a worldspace's persistent cell")
    if (i["xtel"] or {}).get("door") != outer or (o["xtel"] or {}).get("door") != inner:
        problems.append("the two XTELs do not name each other")
    if not (i["persistent_group"] and o["persistent_group"]):
        problems.append("not both persistent")
    if i["base"] != o["base"]:
        problems.append(f"different bases {i['base']} / {o['base']}")
    if problems:
        raise ValueError("Fallout4.esm link: " + "; ".join(problems))
    return i, o


def double_placement(objects, skipped, src):
    """How exp2d handles the exterior door's Fallout 4 reference: ("placed", ...) would be a second door model at the
    same spot, ("skipped", reason, detail), or ("absent", ...) when the exterior export never had it."""
    if any(r.get("src") == src for r in objects.get("refs", [])):
        return ("placed", "exp2d places it already", "")
    for r in skipped.get("refs", []):
        if r.get("formkey") == src:
            return ("skipped", r.get("reason", ""), r.get("detail", ""))
    return ("absent", "not in exp2d's export", "")


def heading(a, b):
    """Degrees clockwise from north (+y), as player.setangle z and testqueue.heading_to."""
    return round(math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) % 360, 1)


def plan_entry(sides, travel, spawn_local, overrides=None):
    """The runner's door_trip test (testqueue.door_test validates it): outside in the world's own frame, inside in the
    interior's frame; start = the XTEL arrival point the other side's door gives (where the game itself puts a player in
    front of this door), near = NEAR_M in front of the door, ground / floor = what a player lands on at the arrival."""
    o, i = sides["outside"], sides["inside"]
    e = {"label": "rr_cave_door", "travel": travel, "spawn_local": spawn_local,
         "outside": {"start": o["start"], "door": o["door"], "arrival": o["arrival"], "near": o["near"],
                     "ground": o["ground"]},
         "inside": {"cell": PORT_CELL, "start": i["start"], "door": i["door"], "arrival": i["arrival"],
                    "near": i["near"], "floor": i["floor"]},
         "save": SAVE, "radius": 4.0, "start_tol": 3.0, "reload_tol": 1.0, "ground_tol": 1.0, "walk_ms": 8000,
         "walk_step_ms": 500, "settle_ms": 6000, "drop": 0.5, "near_wait_ms": 6000, "load_wait_s": 90,
         "expect": "PASS",
         "basis": "supported hypothesis: vanilla keeps its automatic cave doors (AutoloadDoor_Cave, 45 of them) in "
                  "overlay worldspaces' persistent cells with XTELs to interior caves, as written here; whether our "
                  "overlay's merge offset is applied to the return arrival is unresolved"}
    e.update(overrides or {})
    return e


# ------------------------------------------------------------------------------------------------------- raw plugins
def records(path):
    """{form id: (type, flags, data)} of every record in a plugin (data decompressed), walked through its groups."""
    with open(path, "rb") as f:
        buf = f.read()
    out = {}

    def walk(pos, end):
        while pos < end:
            typ = buf[pos:pos + 4]
            size = struct.unpack_from("<I", buf, pos + 4)[0]
            if typ == b"GRUP":
                walk(pos + 24, pos + size)
                pos += size
                continue
            flags, fid = struct.unpack_from("<II", buf, pos + 8)
            data = buf[pos + 24:pos + 24 + size]
            if flags & 0x40000:
                data = zlib.decompress(data[4:])
            out[fid] = (typ.decode("ascii", "replace"), flags & ~0x40000, data)
            pos += 24 + size
    hsize = struct.unpack_from("<I", buf, 4)[0]
    walk(24 + hsize, len(buf))
    return out


def compare_override(master, ours, master_index, our_index):
    """How an override record's data differs from its master's: 'identical', 'formid bytes only' (every differing byte
    is the top byte of a little-endian form id, master_index in the master's file and our_index in ours) or a
    description of the first other difference."""
    if master[0] != ours[0]:
        return f"type {master[0]} vs {ours[0]}"
    if master[1] != ours[1]:
        return f"record flags 0x{master[1]:X} vs 0x{ours[1]:X}"
    a, b = master[2], ours[2]
    if a == b:
        return "identical"
    if len(a) != len(b):
        return f"size {len(a)} vs {len(b)}"
    diff = [k for k in range(len(a)) if a[k] != b[k]]
    if all(k >= 3 and a[k] == master_index and b[k] == our_index for k in diff):
        return "formid bytes only"
    return f"byte {diff[0]}: {a[diff[0]]:#x} vs {b[diff[0]]:#x}"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def load(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def save(p, v, indent=1):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(v, f, indent=indent)
    os.replace(tmp, p)


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


def tool(*args):
    """dotnet/SliceDoor (built in Release first)."""
    proj = os.path.join(REPO, "dotnet", "SliceDoor")
    subprocess.run(["dotnet", "build", proj, "-c", "Release", "--nologo", "-v", "q"], check=True, capture_output=True)
    dll = os.path.join(proj, "bin", "Release", "net9.0", "SliceDoor.dll")
    r = subprocess.run(["dotnet", dll] + [str(a) for a in args], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


# --------------------------------------------------------------------------------------------------------- geometry
class Interior:
    """The converted interior's collision (the build's own converted NIFs, placed as PluginSpike places them)."""

    def __init__(self, port_dir, cell_name):
        cell = load(os.path.join(port_dir, f"{cell_name}.json"))
        manifest = load(os.path.join(port_dir, "manifest.json"))
        bases, placed, self.skipped = exterior.place(cell, manifest, -10 ** 6, 10 ** 6, "FO4Port_")
        tris, self.errors = {}, {}
        for k, b in enumerate(bases):
            try:
                with open(os.path.join(port_dir, "meshes", b["model"]), "rb") as f:
                    bodies = sfbodies.nif_bodies(f.read())
                tris[k] = np.array([t for body in bodies for t in body["triangles"]], np.float64).reshape(-1, 3, 3)
            except (OSError, ValueError, struct.error) as e:
                self.errors[b["model"]] = f"{type(e).__name__}: {e}"
        self.bases, self.placed = bases, placed
        t, own = exterior.world_triangles(tris, placed)
        self.index = exterior.SurfaceIndex(t, own)

    def support(self, x, y, below):
        """The highest collision surface at (x, y) not above `below`: (z, owner) or None."""
        hit = self.index.top(x, y, below)
        return None if hit is None else (round(float(hit[0]), 4), self.describe(hit[1])["model"])

    def describe(self, k):
        p = self.placed[k]
        return {"src": p["src"], "model": self.bases[p["base"]]["model"]}


FEET = 0.5          # a floor under a point counts when it is at most this far above the point's z (XTEL / door z)
CLIMB = 0.3         # per 0.25 m sample of a walk: a 0.3 m step or a 50 degree slope (the player's limits: assumed)
CAPSULE = (0.35, 1.8, 0.3)   # radius, height, skin (contacts lower than a step are not obstacles): assumed, unresolved
ACTIVATE_M = 3.0    # Starfield.esm GMST fAutoDoorActivateDistance (051542) = 3


def walk_profile(support, a, b, z0, step=0.25, climb=CLIMB, blocked=None):
    """The floor a straight walk from a to b (xy) follows: starting on z0, every `step` metres the highest support at
    most `climb` above the previous floor. support(x, y, below) -> (z, owner) or None; blocked(x, y, z) -> the owners a
    standing player there would overlap (CAPSULE) or []. Returns the samples [(distance, z, owner)], the largest rise
    and drop between neighbours, how many samples had no support (a gap) and the first sample whose capsule overlaps
    something (where a straight walk would stop)."""
    n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / step))
    pts, prev, gaps, stop = [], z0, 0, None
    for k in range(n + 1):
        f = k / n
        x, y = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
        d = round(math.hypot(x - a[0], y - a[1]), 3)
        hit = support(x, y, prev + climb)
        if hit is None:
            gaps += 1
            pts.append((d, None, None, False))
            continue
        prev = hit[0]
        hits = blocked(x, y, hit[0]) if blocked is not None else []
        pts.append((d, round(hit[0], 4), hit[1], not hits))
        if stop is None and hits:
            stop = {"distance": d, "z": round(hit[0], 4), "by": [str(h) for h in hits][:4]}
    zs = [p[1] for p in pts if p[1] is not None]
    steps = [zs[k + 1] - zs[k] for k in range(len(zs) - 1)]
    return {"samples": pts, "max_rise": round(max(steps, default=0.0), 4), "max_drop": round(-min(steps, default=0.0), 4),
            "gaps": gaps, "blocked": stop, "length": round(math.hypot(b[0] - a[0], b[1] - a[1]), 3)}


def clear_until_range(walk, door, a, reach=ACTIVATE_M - 0.3):
    """True when a straight walk (walk_profile from a to door) has a floor and a clear capsule at every sample until its
    feet are within `reach` of the door (where the automatic door should load), climbing at most CLIMB per sample."""
    for d, z, _own, clear in walk["samples"]:
        if z is None:
            return False
        f = d / walk["length"] if walk["length"] else 0.0
        x, y = a[0] + (door[0] - a[0]) * f, a[1] + (door[1] - a[1]) * f
        if math.dist((x, y, z), door) < reach:
            return True
        if not clear:
            return False
    return False


def pick_start(support, blocked, door, arr, min_m=ACTIVATE_M + 1.5, max_m=8.0):
    """Where the runner starts its walk at the door: the arrival point (the other door's XTEL) when a straight walk from
    it reaches the door's activation range on a clear floor; else the clear spot closest to the arrival, min_m..max_m
    from the door, from which such a walk exists (rings around the door, 15 degree steps). (start, walk, how)."""
    fa = support(arr[0], arr[1], arr[2] + FEET)
    a0 = [arr[0], arr[1], round(max(arr[2], (fa[0] if fa else arr[2]) + 0.05), 4)]
    w0 = walk_profile(support, a0, door, fa[0] if fa else arr[2], blocked=blocked)
    if fa is not None and not blocked(arr[0], arr[1], fa[0]) and clear_until_range(w0, door, a0):
        return a0, w0, "arrival"
    base = math.atan2(arr[0] - door[0], arr[1] - door[1])
    best = None
    for d in np.arange(min_m, max_m + 0.01, 0.5):
        for da in range(-90, 91, 15):
            ang = base + math.radians(da)
            x, y = door[0] + d * math.sin(ang), door[1] + d * math.cos(ang)
            hit = support(x, y, max(door[2], arr[2]) + 1.5)
            if hit is None or blocked(x, y, hit[0]):
                continue
            s = [round(x, 4), round(y, 4), round(hit[0] + 0.05, 4)]
            w = walk_profile(support, s, door, hit[0], blocked=blocked)
            if not clear_until_range(w, door, s):
                continue
            cost = math.hypot(x - arr[0], y - arr[1])
            if best is None or cost < best[0]:
                best = (cost, s, w)
    if best is None:
        return a0, w0, "arrival (no clear straight walk found)"
    return best[1], best[2], f"clear spot {best[0]:.2f} m from the arrival"


def pick_near(support, blocked, door, start, door_floor, dists=(1.0, 1.5, 2.0), max_3d=2.5):
    """The last-try spot in front of a door: on a floor no more than 1 m from the door's own floor, its feet within
    max_3d of the door (well inside ACTIVATE_M), the capsule clear; tried NEAR_M first straight towards the start, then
    turning away from that line and further out. None when no candidate holds."""
    base = math.atan2(start[0] - door[0], start[1] - door[1])
    for d in dists:
        for da in (0, 30, -30, 60, -60, 90, -90, 120, -120, 150, -150, 180):
            ang = base + math.radians(da)
            x, y = door[0] + d * math.sin(ang), door[1] + d * math.cos(ang)
            hit = support(x, y, door[2] + FEET)
            if hit is None or (door_floor is not None and abs(hit[0] - door_floor) > 1.0):
                continue
            if math.dist((x, y, hit[0]), door) > max_3d or blocked(x, y, hit[0]):
                continue
            return {"pos": [round(x, 4), round(y, 4), round(hit[0] + 0.05, 4)], "distance": d, "angle": da,
                    "floor_owner": hit[1], "to_door_m": round(math.dist((x, y, hit[0]), door), 3)}
    return None


def exterior_world(exp2d):
    import make_exp2c                                                   # noqa: E402  (numpy, the terrain modules)
    prm = load(os.path.join(exp2d, "exp2_params.json"))
    obj = load(os.path.join(exp2d, "objects.json"))
    w = make_exp2c.World(os.path.join(exp2d, "Data"), obj["bases"], obj["refs"],
                         os.path.join(exp2d, *prm["btd_file"].split("/")))
    return w, prm, obj


def exterior_support(world):
    """support(x, y, below) on exp2d: the highest converted collision surface not above `below` when it stands above
    the terrain (BTD), else the terrain."""
    def support(x, y, below):
        g = float(world.ground(x, y))
        hit = world.index.top(x, y, below)
        if hit is not None and hit[0] > g:
            return round(float(hit[0]), 4), world.describe(hit[1])["edid"]
        return round(g, 4), "terrain"
    return support


def measure(support, blocked, door, arr, extra=None):
    """One side of the link: the door, the arrival the other side's XTEL gives (= the walk's start: where the game puts
    a player in front of this door), what stands under both, the floor a straight walk from the arrival to the door
    follows (and where its capsule would first touch something), and the last-try spot in front of the door."""
    fa = support(arr[0], arr[1], arr[2] + FEET)
    fd = support(door[0], door[1], door[2] + FEET)
    arrival_walk = walk_profile(support, arr, door, fa[0] if fa else arr[2], blocked=blocked)
    # the walk starts at the arrival point when a straight walk from there reaches the door; otherwise (the RedRocket01
    # arrival touches a rock mound, and a mound stands on the straight line) at the clear spot closest to it
    start, walk, how = pick_start(support, blocked, door, arr)
    nr = pick_near(support, blocked, door, start, fd[0] if fd else None)
    out = {"door": door, "arrival": arr, "start": start, "start_pick": how, "arrival_walk": arrival_walk,
           "near": nr["pos"] if nr else None, "near_pick": nr,
           "arrival_floor": fa[0] if fa else None, "arrival_floor_owner": fa[1] if fa else None,
           "arrival_above_floor": round(arr[2] - fa[0], 4) if fa else None,
           "door_floor": fd[0] if fd else None, "door_floor_owner": fd[1] if fd else None,
           "door_above_floor": round(door[2] - fd[0], 4) if fd else None,
           "door_from_arrival_m": round(math.dist(door, arr), 3), "walk": walk}
    out.update(extra or {})
    return out


def measure_outside(world, o_door, o_arr):
    """The exterior door and its approach against exp2d's terrain (BTD) and converted collision. ground: what the
    returning player lands on at the arrival point (exterior.landing over a 0.6 m disc, from the arrival z + FEET), the
    judge's reference after the load."""
    from make_exp2c import landing_json                                 # noqa: E402
    la = world.landing(o_arr[0], o_arr[1], o_arr[2] + FEET)
    r, h, skin = CAPSULE

    def blocked(x, y, z):
        return [world.describe(k)["edid"] if isinstance(k, (int, np.integer)) else k
                for k in exterior.capsule_hits(world.index, world.ground, x, y, z, radius=r, height=h, skin=skin)]
    return measure(exterior_support(world), blocked, o_door, o_arr, {
        "ground": round(la["centre"], 4), "arrival_landing": landing_json(world, la),
        "door_terrain": round(float(world.ground(o_door[0], o_door[1])), 4)})


def measure_inside(interior, i_door, i_arr):
    r, h, skin = CAPSULE

    def blocked(x, y, z):
        return [interior.describe(k)["model"] for k in
                exterior.capsule_hits(interior.index, lambda _x, _y: -1e9, x, y, z, radius=r, height=h, skin=skin)]
    m = measure(interior.support, blocked, i_door, i_arr)
    m["floor"] = m["arrival_floor"]
    return m


# ------------------------------------------------------------------------------------------------------------- stage
def cmd_stage(a):
    out = os.path.abspath(a.out)
    ev = os.path.join(out, "evidence")
    os.makedirs(ev, exist_ok=True)
    port_esm = os.path.join(a.port, "FO4Port.esm")
    # 1. evidence, read-only (dotnet/SliceDoor)
    for args in (("fo4", a.fo4, os.path.join(ev, "fo4_door_link.json"), INNER, OUTER),
                 ("sf-door", a.sf_esm, os.path.join(ev, "sf_autoload_door.json"), DOOR_BASE["id"])):
        code, text = tool(*args)
        if code:
            sys.exit(f"SliceDoor {args[0]} failed ({code}):\n{text[-2000:]}")
    link = load(os.path.join(ev, "fo4_door_link.json"))
    inner, outer = link_pair(link)
    o_side, i_side = side(outer, EDIDS["outside"]), side(inner, EDIDS["inside"])
    fo4_base = link["door_bases"][0]
    sfd = load(os.path.join(ev, "sf_autoload_door.json"))
    if sfd["door"]["editor_id"] != DOOR_BASE["editor_id"] or "Automatic" not in sfd["door"]["flags"]:
        sys.exit(f"vanilla door base {DOOR_BASE['id']} is not the automatic cave door: {sfd['door']}")
    code, text = tool("port", port_esm, PORT_CELL, os.path.join(ev, f"port_{FO4_CELL}.json"), *i_side["pos"], 4)
    if code:
        sys.exit(f"SliceDoor port failed ({code}):\n{text[-2000:]}")
    port = load(os.path.join(ev, f"port_{FO4_CELL}.json"))
    if port["xtel_refs"] or port["door_based_refs"]:
        sys.exit(f"{PORT_CELL} already has a load door ({port['xtel_refs'] or port['door_based_refs']}): override it "
                 f"instead of adding one")
    # 2. exp2d: the world, its arrival, and whether the exterior door is placed already
    world, prm, obj = exterior_world(a.exp2d)
    skipped = load(os.path.join(a.exp2d, "skipped.json"))
    dp = double_placement(obj, skipped, outer["formid"] + ":Fallout4.esm")
    if dp[0] == "placed":
        sys.exit(f"exp2d already places {outer['formid']}: a second door model would stand there (remove it first)")
    e0 = load(os.path.join(a.exp2d, "plan.json"))[0]
    travel = e0.get("travel") or f"coc {e0['coc']}"
    # 3. ground and floor (the doors themselves are copied from Fallout 4; the approach points are ours)
    outside = measure_outside(world, o_side["pos"], i_side["xtel"]["pos"])
    interior = Interior(a.port, FO4_CELL)
    if interior.errors:
        print(f"note: {len(interior.errors)} interior models without readable collision: {sorted(interior.errors)[:5]}")
    inside = measure_inside(interior, i_side["pos"], o_side["xtel"]["pos"])
    # 4. the plugin
    params = {"plugin": PLUGIN, "door_base": DOOR_BASE,
              "world": {"plugin": EXP2_PLUGINS[0], "editor_id": prm["world"]},
              "interior": {"plugin": "FO4Port.esm", "editor_id": PORT_CELL},
              "outside": o_side, "inside": i_side}
    save(os.path.join(out, "slice_params.json"), params)
    code, text = tool("build", os.path.join(out, "slice_params.json"), a.sf_esm,
                      os.path.join(a.exp2d, EXP2_PLUGINS[0]), port_esm, out)
    print(text.strip())
    if code:
        sys.exit(f"SliceDoor build failed ({code})")
    # 5. what exp2d installs, copied: its plugins byte for byte and its Data tree
    for p in EXP2_PLUGINS:
        shutil.copy2(os.path.join(a.exp2d, p), os.path.join(out, p))
    c, k = copy_tree(os.path.join(a.exp2d, "Data"), os.path.join(out, "Data"))
    print(f"exp2d Data: {c} copied, {k} up to date")
    for f in ("exp2_params.json", "objects.json", "skipped.json", "formids.json"):
        shutil.copy2(os.path.join(a.exp2d, f), os.path.join(out, "exp2d_" + f))
    # 6. the runner's plan and the expectations
    sides = {"outside": outside, "inside": inside}
    entry = plan_entry(sides, travel, e0["spawn_local"])
    save(os.path.join(out, "plan.json"), [entry])
    off = LAST_OFFSET
    merged = {k: [round(outside[k][j] + off[j], 3) for j in range(3)] for k in ("door", "arrival", "start", "near")}
    expected = {
        "slice": "Red Rocket cave door (docs/slice/redrocket-door.md)",
        "fo4": {"interior_door": inner, "exterior_door": outer, "door_base": fo4_base},
        "starfield": {"door_base": sfd["door"],
                      "vanilla_refs": {k: sfd[k] for k in ("refs_total", "refs_interior", "refs_world",
                                                           "refs_world_persistent_cell", "refs_in_overlay_worlds",
                                                           "scale_min", "scale_max", "world_xtel_refs")}},
        "port": {k: port[k] for k in ("cell", "refs_persistent", "refs_temporary", "xtel_refs", "door_based_refs",
                                      "plugin_xtel_refs")},
        "exp2d_exterior_door": {"status": dp[0], "reason": dp[1], "detail": dp[2]},
        "plugin": {"file": PLUGIN, "formids": {"exterior": "000800", "interior": "000801"},
                   "masters": ["Starfield.esm", EXP2_PLUGINS[0], "FO4Port.esm"]},
        "outside": outside, "inside": inside,
        "merged_with_last_offset": {"offset": off, **merged},
        "interior_skipped_models": len(interior.skipped), "interior_collision_errors": interior.errors,
        "plan": entry}
    save(os.path.join(out, "expected.json"), expected)
    readme(out, expected, a)
    print(f"staged {out}: exterior door at {o_side['pos']} (floor {outside['door_floor']} "
          f"{outside['door_floor_owner']}), arrival outside {outside['arrival']} lands {outside['ground']}; "
          f"interior door at {i_side['pos']} (floor {inside['door_floor']}), arrival inside {inside['arrival']} "
          f"(floor {inside['floor']})")
    return 0


def readme(out, e, a):
    o, i, m = e["outside"], e["inside"], e["merged_with_last_offset"]
    text = f"""Slice: the Red Rocket cave door (Claude, 2026-10-12). NOT deployed, NOT queued. docs/slice/redrocket-door.md.
One install = terrain experiment 2d (terrain, 8,069 FO4 objects, converted navmesh; its plugins and Data copied byte
for byte) + {PLUGIN}: the Fallout 4 load door between the Commonwealth and RedRocket01 (the cave behind Red Rocket),
as the vanilla automatic cave door AutoloadDoor_Cave (24F9CE:Starfield.esm) at both ends, each XTEL naming the other.
FO4Port.esm (the pinned build) is a master: it must load BEFORE {PLUGIN}.

Install (game closed). The runner does it (plan below); its cycle.ps1 moves {PLUGIN} after FO4Port.esm
(exp_install.py order), because the deploy activates FO4Port.esm after the experiment's plugins:
  scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> --plugins {",".join(EXP2_PLUGINS)},{PLUGIN} --pack
By hand: Plugins.txt order *FO4TerrainExp2.esm, *FO4TerrainExp2_Mars.esm, *FO4Port.esm, *{PLUGIN}; the Data tree in
"FO4TerrainExp2 - Main.ba2" (Archive2, -compression=None) as for exp2d. Never together with another terrain experiment.

Runner (one door_trip test, --fresh):
  testqueue.py plan-door --staging <pinned build> --exp-dir <this folder> --out <queue> --plugins {",".join(EXP2_PLUGINS)},{PLUGIN} --fresh

In game by hand (test save, console): tgm; coc FO4CW_RedRocketSpawn; read the arrival (player.getpos x / y / z,
settled) -> S; offset O = S - (-989.0286, 1147.2, 105.2609). Last exp2d run: O = {m['offset']}.
  player.setpos x {o['start'][0]:.3f} + O.x; y {o['start'][1]:.3f} + O.y; z {o['start'][2] + 0.5:.3f} + O.z
  (with the last offset: x {m['start'][0]:.3f}, y {m['start'][1]:.3f}, z {m['start'][2] + 0.5:.3f}); face north
  (setangle z {heading(o['start'], o['door'])}) and walk into the hole under the tree roots 5 m ahead: within 3 m of
  the door (fAutoDoorActivateDistance) it fades and loads RedRocket01.
  Expect inside: player.getpos near ({i['arrival'][0]:.2f}, {i['arrival'][1]:.2f}, {i['arrival'][2]:.2f}); player.GetInCell {PORT_CELL} = 1.
  Inside: player.setpos x {i['start'][0]:.3f}; y {i['start'][1]:.3f}; z {i['start'][2] + 0.5:.3f} ({i['start_pick']}),
  setangle z {heading(i['start'], i['door'])} and walk {math.dist(i['start'], i['door']):.1f} m to the cave mouth: it loads the Commonwealth.
  Expect outside: near ({o['arrival'][0]:.2f}, {o['arrival'][1]:.2f}) + O (last offset: {m['arrival'][0]:.2f}, {m['arrival'][1]:.2f}),
  z about {o['ground']:.2f} + O.z. Then: save {SAVE}; load {SAVE}; the same position again.

Numbers (world frame = FO4 / 70):
  exterior door   {o['door']}  floor under it {o['door_floor']} ({o['door_floor_owner']}; terrain {o['door_terrain']})
  arrival outside {o['arrival']}  lands on {o['ground']}
  interior door   {i['door']}  floor {i['door_floor']} ({i['door_floor_owner']})
  arrival inside  {i['arrival']}  floor {i['floor']} ({i['arrival_floor_owner']})
Files: {PLUGIN}, the exp2d plugins and Data, slice_params.json (what SliceDoor build wrote), plan.json, expected.json,
evidence\\ (SliceDoor fo4 / sf-door / port / check JSON), offline_check.json (check), exp2d_*.json (exp2d's own).
Uninstall: exp_install.py uninstall.
"""
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(text)


# ------------------------------------------------------------------------------------------------------------- check
def cmd_check(a):
    out = os.path.abspath(a.out)
    ev = os.path.join(out, "evidence")
    port_esm = os.path.join(a.port, "FO4Port.esm")
    exp2 = os.path.join(a.exp2d, EXP2_PLUGINS[0])
    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

    code, text = tool("check", os.path.join(out, PLUGIN), a.sf_esm, exp2, port_esm,
                      os.path.join(out, "slice_params.json"), os.path.join(ev, "check_plugin.json"))
    rep = load(os.path.join(ev, "check_plugin.json"))
    add("SliceDoor check (Mutagen read-back, links, XTEL both ways)", code == 0 and rep["ok"],
        f"{sum(c['ok'] for c in rep['checks'])} of {len(rep['checks'])} pass")
    # raw: the override records are the masters' own records (the world and its persistent cell byte for byte: master
    # index 01 is FO4TerrainExp2.esm in both files; the interior cell up to its form ids' master byte, 01 -> 02)
    ours, ex, po = records(os.path.join(out, PLUGIN)), records(exp2), records(port_esm)
    wrld = [(fid, r) for fid, r in ours.items() if r[0] == "WRLD"]
    cells = [(fid, r) for fid, r in ours.items() if r[0] == "CELL"]
    refs = [(fid, r) for fid, r in ours.items() if r[0] == "REFR"]
    add("raw record set", len(wrld) == 1 and len(cells) == 2 and len(refs) == 2 and len(ours) == 5,
        ", ".join(f"{t} {sum(1 for r in ours.values() if r[0] == t)}" for t in sorted({r[0] for r in ours.values()})))
    for fid, r in wrld + cells:
        if fid >> 24 == 1:
            res = compare_override(ex.get(fid, ("missing", 0, b"")), r, 1, 1)
            add(f"{r[0]} {fid:08X} = FO4TerrainExp2.esm's record", res == "identical", res)
        elif fid >> 24 == 2:
            res = compare_override(po.get((fid & 0xFFFFFF) | 0x01000000, ("missing", 0, b"")), r, 1, 2)
            add(f"{r[0]} {fid:08X} = FO4Port.esm's record", res in ("identical", "formid bytes only"), res)
        else:
            add(f"{r[0]} {fid:08X}", False, "an override of an unexpected master")
    add("door references are this plugin's 0x800 / 0x801", sorted(fid for fid, _ in refs) == [0x03000800, 0x03000801],
        ", ".join(f"{fid:08X}" for fid, _ in refs))
    # the exp2d copies
    for p in EXP2_PLUGINS:
        add(f"{p} copied byte for byte", sha256(os.path.join(out, p)) == sha256(os.path.join(a.exp2d, p)), p)
    n_src = sum(len(f) for _, _, f in os.walk(os.path.join(a.exp2d, "Data")))
    n_out = sum(len(f) for _, _, f in os.walk(os.path.join(out, "Data")))
    size_src = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(os.path.join(a.exp2d, "Data")) for f in fs)
    size_out = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(os.path.join(out, "Data")) for f in fs)
    add("exp2d Data tree copied", n_src == n_out and size_src == size_out, f"{n_out} files, {size_out:,} B")
    # the plan, through the runner's own planner
    import testqueue                                                     # noqa: E402
    plan = load(os.path.join(out, "plan.json"))
    t = testqueue.door_test(0, plan[0])
    add("plan.json is a valid door_trip test", True,
        f"{t['id']}, headings out {t['heading_out']} / in {t['heading_in']}, step timeout {testqueue.step_timeout(t)} s")
    exp = load(os.path.join(out, "expected.json"))
    o, i = exp["outside"], exp["inside"]
    add("the exterior door is placed once (exp2d skips the Fallout 4 marker door)",
        exp["exp2d_exterior_door"]["status"] == "skipped", str(exp["exp2d_exterior_door"]))
    for name, m in (("exterior", o), ("interior", i)):
        add(f"{name} door base on the floor under it (0 <= door z - floor <= 1.5 m: the trigger box stands in the "
            f"opening)", m["door_floor"] is not None and -0.3 <= m["door_above_floor"] <= 1.5,
            f"door z {m['door'][2]}, floor {m['door_floor']} ({m['door_floor_owner']})")
        add(f"{name} arrival (the other door's XTEL point) over a floor within 0.5 m",
            m["arrival_floor"] is not None and abs(m["arrival_above_floor"]) <= 0.5,
            f"XTEL z {m['arrival'][2]}, floor {m['arrival_floor']} ({m['arrival_floor_owner']})")
        w = m["walk"]
        add(f"{name} straight walk from the start ({m['start_pick']}) reaches {ACTIVATE_M - 0.3:g} m of the door on a "
            f"floor with the capsule clear (assumed capsule {CAPSULE[0]} x {CAPSULE[1]} m, climb {CLIMB} m per 0.25 m)",
            clear_until_range(w, m["door"], m["start"]),
            f"{w['length']} m, largest rise {w['max_rise']} m, largest drop {w['max_drop']} m, "
            + (f"capsule first touches {w['blocked']['by']} at {w['blocked']['distance']} m "
               f"({w['length'] - w['blocked']['distance']:.2f} m before the door)" if w["blocked"] else "capsule clear"))
        add(f"{name} last-try spot in front of the door (floor, capsule clear, within 2.5 m of the door)",
            m["near"] is not None, str(m["near_pick"]))
        add(f"{name} arrival outside the {ACTIVATE_M:g} m activation range of its own side's door (no immediate "
            f"return)", m["door_from_arrival_m"] > ACTIVATE_M, f"{m['door_from_arrival_m']} m")
    add("outside: the returning player lands within 0.5 m of the XTEL point", abs(o["arrival"][2] - o["ground"]) <= 0.5,
        f"XTEL z {o['arrival'][2]}, lands on {o['ground']} "
        f"({'object' if o['arrival_landing']['on_object'] else 'terrain'}); terrain under the door {o['door_terrain']}")
    hop = [abs(o["start"][k] - plan[0]["spawn_local"][k]) for k in range(2)]
    add("the hop from the coc arrival to the outside start stays within 2 cells per axis", max(hop) <= 200.0,
        f"dx {hop[0]:.1f} m, dy {hop[1]:.1f} m")
    # the load order the runner produces (pre_launch appends the experiment, cycle.ps1's deploy appends FO4Port.esm,
    # exp_install.py order moves this plugin after its masters)
    import exp_install                                                   # noqa: E402
    plugins = list(EXP2_PLUGINS) + [PLUGIN]
    masters = {p: exp_install.plugin_masters(os.path.join(out, p)) for p in plugins}
    lines = [f"*{p}" for p in plugins] + ["*FO4Port.esm"]
    new, moved, missing = exp_install.order_lines(lines, plugins, masters)
    want = ["*FO4TerrainExp2.esm", "*FO4TerrainExp2_Mars.esm", "*FO4Port.esm", f"*{PLUGIN}"]
    add("load order after exp_install.py order", new == want and not missing, " ".join(new))
    add("plan needs the runner features door_trip and plugin_order",
        testqueue.plugin_order_needed(out, plugins) and "door_trip" in testqueue.runner_features.needs([t]),
        str(sorted(set(testqueue.runner_features.needs([t])) | {"plugin_order"})))
    ok = all(c["ok"] for c in checks)
    save(os.path.join(out, "offline_check.json"), {"ok": ok, "checks": checks, "plugin_check": rep})
    print("all checks pass" if ok else f"{sum(not c['ok'] for c in checks)} checks FAIL")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("stage", "check"):
        s = sub.add_parser(name)
        s.add_argument("--sf-esm", required=True)
        s.add_argument("--port", required=True, help="the pinned build folder (FO4Port.esm, manifest, cell exports)")
        s.add_argument("--exp2d", required=True, help="terrain experiment 2d's staged folder")
        s.add_argument("--out", required=True)
        if name == "stage":
            s.add_argument("--fo4", required=True, help="Fallout4.esm")
    a = ap.parse_args(argv)
    return cmd_stage(a) if a.cmd == "stage" else cmd_check(a)


if __name__ == "__main__":
    sys.exit(main())
