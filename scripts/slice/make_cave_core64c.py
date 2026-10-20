"""The Red Rocket cave load door on core64c (the full-object Commonwealth core), walked both ways (docs/slice/cave-routes.md,
docs/slice/door-frames.md; the exp2d door it ports: docs/slice/redrocket-door.md).

    python scripts/slice/make_cave_core64c.py stage --fo4 <Fallout4.esm> --sf-esm <Starfield.esm> --port <pinned build>
           --core <terrain_core64c> --out <slice folder> [--template-world LC172World] [--no-probes]
    python scripts/slice/make_cave_core64c.py check --sf-esm <Starfield.esm> --port <pinned build> --core <terrain_core64c> --out <slice dir>
           --out <slice folder>

stage  1. evidence (dotnet/SliceDoor, read-only): the Fallout 4 link (05E844 in RedRocket01 <-> 08EB65 in the
          Commonwealth persistent cell, AutoloadDoor 01ED77), the vanilla AutoloadDoor_Cave 24F9CE, and RedRocket01 as
          the pinned build holds it (no load door of its own);
       2. core64c places the cave mouth (CaveEntrGround01_Grass 08CCF2) and skips 08EB65 (editor marker), so the door
          is placed once; the ground under both ends and the last-try spots (make_redrocket_door.measure_*);
       3. the walking routes (plan_cave_routes.plan_routes: outside from the coc arrival, inside from the XTEL arrival);
       4. FO4SliceRedRocketCore.esm with SliceDoor build: masters Starfield.esm, FO4TerrainCore.esm, FO4Port.esm; the
          world FO4Core_Commonwealth and its persistent cell overridden (with --template-world the persistent cell takes
          that vanilla world's record shape: fix A of door-frames.md section 3), both doors persistent with XTELs both
          ways, and (unless --no-probes) two XMarker merge probes in exterior cell (-10, 11): one persistent (B), one
          temporary (C, the control);
       5. one install folder: the slice plugin, plus hard links of core64c's two plugins and its whole Data tree (no
          second copy: the runner's exp_install.py installs one folder, and packs Data into "FO4TerrainCore - Main.ba2"
          exactly as for core64c);
       6. plan.json (one door_trip test, both legs routed, facing judged, merge probes read), expected.json, README.txt.
check  SliceDoor check; a raw compare of the override records with their masters; the hard links (the same files as
       core64c's, sizes and times as core64c's data_manifest.json); the plan through the runner's own door_test; the
       load order the runner produces; the routes' own checks; the pins (sha256 of every plugin, plan.json, params).
       Writes offline_check.json.
Everything this writes stays outside the repo (derived game data).
"""
import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
for p in (os.path.join(REPO, "src"), os.path.join(REPO, "scripts"), os.path.join(REPO, "scripts", "game"), os.path.join(REPO, "scripts", "terrain"),
          os.path.join(REPO, "scripts", "actors"), HERE):
    sys.path.insert(0, p)
import make_redrocket_door as rr  # noqa: E402
import plan_cave_routes as pcr  # noqa: E402
from stage_outputs import require_ready_stage  # noqa: E402

PLUGIN = "FO4SliceRedRocketCore.esm"
CORE_PLUGINS = ("FO4TerrainCore.esm", "FO4TerrainCore_Mars.esm")
WORLD = "FO4Core_Commonwealth"
COC = "FO4Core_RedRocketSpawn"
EDIDS = {"outside": "FO4SL_RedRocketCaveDoorExtCore", "inside": "FO4SL_RedRocketCaveDoorIntCore"}
SAVE = "fo4sf_slice_rrcave64c"
# runtime form ids (supported: FO4TerrainCore.esm read as load-order byte 02 in core64 (anchor 02000800), then
# FO4TerrainCore_Mars.esm 03, FO4Port.esm 04, this plugin 05; exp2d's slice door read as 05000800 in game on
# 2026-10-13 with the same plugin count). A wrong byte only makes a diagnostic read another ref or none.
LOAD = {"core": "02", "port": "04", "slice": "05"}
PORT_CELL_ID = 0x002338            # FO4Port_RedRocket01 in the pinned build (docs/slice/redrocket-door.md section 2)
XMARKER = "00003B"                 # Starfield.esm STAT XMarker (verified: fo4land base_records, 2026-10-13)
PROBE_CELL = (-10, 11)             # the exterior cell of the coc arrival, the station and the cave mouth
# probe spots: open level terrain next to core64c's zref_ground (-985.2571, 1138.5143 -> 105.0253), 1 m apart
PROBES = (("000802", "FO4SL_MergeProbePersistentCore", True, (-985.2571, 1138.5143, 105.0253),
           "XMarker, persistent child of exterior cell (-10, 11) (B)"),
          ("000803", "FO4SL_MergeProbeTemporaryCore", False, (-984.2571, 1138.5143, 105.0253),
           "XMarker, temporary in exterior cell (-10, 11) (C, the control)"))
# the third probe: core64c's own anchor, in the overridden persistent cell (A); its runtime id and local position
ANCHOR_PROBE = {"ref": f"{LOAD['core']}000800", "local": [-989.2571, 1146.5143, 105.1429],
                "what": "core64c's anchor FO4Core_CommonwealthAnchor, in the overridden persistent cell (A)"}
ROUTE_KNOBS = {"route_hold_ms": 2000, "route_reach_m": 0.8, "route_speed": 4.6, "route_max_steps": 40,
               "route_final_steps": 6}
MANIFEST = "data_manifest.json"


def deg(rad):
    """A rotation z in radians as a heading in degrees [0, 360) (player.getangle z)."""
    return round(math.degrees(float(rad)) % 360.0, 3)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def load(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def link_file(src, dst):
    """Hard-link src to dst (same volume), keeping a link that is already the same file; never a copy."""
    if os.path.exists(dst):
        if os.path.samefile(src, dst):
            return "kept"
        os.remove(dst)
    os.link(src, dst)
    return "linked"


def link_tree(src, dst):
    """Hard-link every file of src into dst; (linked, kept). A file that cannot be linked stops the staging (a copy
    would be a second 3.6 GiB that check could no longer tie to core64c's checked tree)."""
    linked = kept = 0
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        os.makedirs(os.path.join(dst, rel), exist_ok=True)
        for fn in files:
            if link_file(os.path.join(root, fn), os.path.join(dst, rel, fn)) == "linked":
                linked += 1
            else:
                kept += 1
    return linked, kept


def data_manifest(folder, plugins=()):
    """{path: [size, mtime_ns]} as make_core64c.data_manifest (hard links share both with core64c's files)."""
    files = {}
    for root, _dirs, names in os.walk(os.path.join(folder, "Data")):
        for n in names:
            st = os.stat(os.path.join(root, n))
            files[os.path.relpath(os.path.join(root, n), folder).replace(os.sep, "/")] = [st.st_size, st.st_mtime_ns]
    for pl in plugins:
        st = os.stat(os.path.join(folder, pl))
        files[pl] = [st.st_size, st.st_mtime_ns]
    return files


def plan_entry(sides, routes, spawn_local, o_rot, i_rot, probes, overrides=None):
    """The runner's door_trip test (testqueue.door_test validates it). Both legs walk their route from where the player
    stands (start = the route's first point); arrival_heading = the facing the other door's XTEL gives on arrival."""
    o, i = sides["outside"], sides["inside"]
    ro, ri = routes["outside"]["route"], routes["inside"]["route"]
    reach = max(max(math.dist(q, r[0]) for q in r) for r in (ro, ri))
    e = {"label": "rr_cave_core64c", "travel": f"coc {COC}", "spawn_local": spawn_local,
         "outside": {"start": ro[0], "route": ro, "door": o["door"], "arrival": o["arrival"], "near": o["near"],
                     "ground": o["ground"], "ref": f"{LOAD['slice']}000800", "arrival_heading": deg(o_rot)},
         "inside": {"cell": rr.PORT_CELL, "cell_id": f"{LOAD['port']}{PORT_CELL_ID:06X}", "start": ri[0], "route": ri,
                    "door": i["door"], "arrival": i["arrival"], "near": i["near"], "floor": i["floor"],
                    "arrival_heading": deg(i_rot)},
         "save": SAVE, "radius": 4.0, "start_tol": 3.0, "reload_tol": 1.0, "ground_tol": 1.0, "walk_ms": 8000,
         "walk_step_ms": 500, "settle_ms": 6000, "drop": 0.5, "near_wait_ms": 6000, "load_wait_s": 90,
         # a read beyond moved_m of a leg's start is the other side of the door: past the routes' own reach + 10 m
         "moved_m": float(max(30, math.ceil(reach + 15))), "activate_m": rr.ACTIVATE_M, "facing_tol": 20.0,
         "frame_m": 150.0,
         "route_walk_ms": int(max(routes["outside"]["walk_ms"], routes["inside"]["walk_ms"]) + 10000),
         **ROUTE_KNOBS, "expect": "PASS",
         "basis": "supported hypothesis: the vanilla-shaped persistent cell override makes the overlay merge move the "
                  "persistent door (door-frames.md fix A; the probes tell which storage merges); the routes follow FO4's "
                  "navmesh and the converted collision (cave-routes.md)"}
    if probes:
        e["probes"] = probes
    e.update(overrides or {})
    return e


def bind_plan(t, routes, params, anchor=ANCHOR_PROBE, tol=1e-3):
    """What the runner's own test (testqueue.door_test of plan.json) says that the checked inputs do not: the routes it
    walks against routes.json's, the probes it reads (refs, local positions) against slice_params.json's probes (the
    plugin's runtime ids) and the anchor probe. [] when they agree; else one line per mismatch. Codex's review of PR
    #107 (2026-10-14): check validated plan.json and routes.json each on its own, so an edited waypoint or a shifted
    probe expectation passed."""
    out = []
    for side in ("outside", "inside"):
        mine, theirs = t[side].get("route") or [], routes[side].get("route") or []
        if len(mine) != len(theirs):
            out.append(f"{side} route: {len(mine)} waypoints in plan.json, {len(theirs)} in routes.json")
            continue
        for k, (p, q) in enumerate(zip(mine, theirs)):
            if math.dist(p, q) > tol:
                out.append(f"{side} route waypoint {k}: plan.json {p}, routes.json {list(q)} ({math.dist(p, q):.3f} m apart)")
        if mine and math.dist(t[side]["start"], mine[0]) > tol:
            out.append(f"{side} start {t[side]['start']} is not the route's first waypoint {mine[0]}")
    want = {f"{LOAD['slice']}{p['id']}".upper(): list(p["pos"]) for p in params.get("probes") or []}
    if want:
        want[anchor["ref"].upper()] = list(anchor["local"])
    got = {p["ref"].upper(): list(p["local"]) for p in t.get("probes") or []}
    for ref in sorted(set(want) - set(got)):
        out.append(f"probe {ref} ({want[ref]}) is in slice_params.json but not in plan.json")
    for ref in sorted(set(got) - set(want)):
        out.append(f"probe {ref} ({got[ref]}) is in plan.json but not in slice_params.json")
    for ref in sorted(set(got) & set(want)):
        if math.dist(got[ref], want[ref]) > tol:
            out.append(f"probe {ref}: plan.json expects {got[ref]}, the plugin places it at {want[ref]} "
                       f"({math.dist(got[ref], want[ref]):.3f} m apart)")
    return out


def cmd_stage(a):
    require_ready_stage(a.core)
    t0 = time.time()
    out = os.path.abspath(a.out)
    ev = os.path.join(out, "evidence")
    os.makedirs(ev, exist_ok=True)
    port_esm = os.path.join(a.port, "FO4Port.esm")
    core_esm = os.path.join(a.core, CORE_PLUGINS[0])
    # 1. evidence (read-only)
    for args in (("fo4", a.fo4, os.path.join(ev, "fo4_door_link.json"), rr.INNER, rr.OUTER),
                 ("sf-door", a.sf_esm, os.path.join(ev, "sf_autoload_door.json"), rr.DOOR_BASE["id"])):
        code, text = rr.tool(*args)
        if code:
            sys.exit(f"SliceDoor {args[0]} failed ({code}):\n{text[-2000:]}")
    link = load(os.path.join(ev, "fo4_door_link.json"))
    inner, outer = rr.link_pair(link)
    o_side, i_side = rr.side(outer, EDIDS["outside"]), rr.side(inner, EDIDS["inside"])
    sfd = load(os.path.join(ev, "sf_autoload_door.json"))
    if sfd["door"]["editor_id"] != rr.DOOR_BASE["editor_id"] or "Automatic" not in sfd["door"]["flags"]:
        sys.exit(f"vanilla door base {rr.DOOR_BASE['id']} is not the automatic cave door: {sfd['door']}")
    code, text = rr.tool("port", port_esm, rr.PORT_CELL, os.path.join(ev, f"port_{rr.FO4_CELL}.json"), *i_side["pos"], 4)
    if code:
        sys.exit(f"SliceDoor port failed ({code}):\n{text[-2000:]}")
    port = load(os.path.join(ev, f"port_{rr.FO4_CELL}.json"))
    if port["xtel_refs"] or port["door_based_refs"]:
        sys.exit(f"{rr.PORT_CELL} already has a load door: override it instead of adding one")
    # 2. core64c: the exterior door placed once, the cave mouth present; the ground under both ends
    objects = load(os.path.join(a.core, "objects.json"))
    skipped = load(os.path.join(a.core, "skipped.json"))
    dp = rr.double_placement(objects, skipped, outer["formid"] + ":Fallout4.esm")
    if dp[0] != "skipped":
        sys.exit(f"core64c and 08EB65: {dp} (a second door, or a door core64c never exported)")
    mouth = [r for r in objects["refs"] if r["src"] == "08CCF2:Fallout4.esm"]
    if len(mouth) != 1:
        sys.exit(f"core64c places the cave mouth CaveEntrGround01_Grass 08CCF2 {len(mouth)} times")
    spawn_local = load(os.path.join(a.core, "plan.json"))[0]["spawn_local"]
    world = pcr.core_world(a.core, spawn_local, o_side["pos"])
    outside = rr.measure_outside(world[0], o_side["pos"], i_side["xtel"]["pos"], o_side["scale"])
    interior = rr.Interior(a.port, rr.FO4_CELL)
    inside = rr.measure_inside(interior, i_side["pos"], o_side["xtel"]["pos"], i_side["scale"])
    # 3. the routes
    routes = pcr.plan_routes(a.fo4, a.core, a.port, png=os.path.join(out, "routes.png"), world=world,
                             interior=interior)
    with open(os.path.join(out, "routes.json"), "w", encoding="utf-8") as f:
        json.dump(routes, f, indent=1)
    if not (routes["outside"].get("route") and routes["inside"].get("route")):
        sys.exit("no walking route to a door (routes.json)")
    # 4. the plugin
    # --probe-cell X Y: the probes shifted by whole cells into another exterior cell (cave_probes_1015, 2026-10-15: an
    # override of the COC cell (-10, 11) moved the coc arrival to (50, 50); does an override of a neighbour cell?)
    cell = tuple(a.probe_cell) if getattr(a, "probe_cell", None) else PROBE_CELL
    shift = (100.0 * (cell[0] - PROBE_CELL[0]), 100.0 * (cell[1] - PROBE_CELL[1]))
    probes = [(pid, edid, pers, [pos[0] + shift[0], pos[1] + shift[1], pos[2]], what) for pid, edid, pers, pos, what in PROBES]
    probes_params = [] if a.no_probes else [
        {"id": pid, "edid": edid, "base": XMARKER, "cell": list(cell), "pos": list(pos), "persistent": pers}
        for pid, edid, pers, pos, _what in probes]
    params = {"plugin": PLUGIN, "door_base": rr.DOOR_BASE, "world": {"plugin": CORE_PLUGINS[0], "editor_id": WORLD},
              "interior": {"plugin": "FO4Port.esm", "editor_id": rr.PORT_CELL}, "outside": o_side, "inside": i_side}
    if a.template_world:
        params["persistent_cell"] = {"template_world": a.template_world}
    if probes_params:
        params["probes"] = probes_params
    with open(os.path.join(out, "slice_params.json"), "w", encoding="utf-8") as f:
        json.dump(params, f, indent=1)
    code, text = rr.tool("build", os.path.join(out, "slice_params.json"), a.sf_esm, core_esm, port_esm, out)
    print(text.strip())
    if code:
        sys.exit(f"SliceDoor build failed ({code})")
    # 5. the install folder: core64c's plugins and Data tree as hard links
    for p in CORE_PLUGINS:
        print(f"{p}: {link_file(os.path.join(a.core, p), os.path.join(out, p))}")
    ln, kp = link_tree(os.path.join(a.core, "Data"), os.path.join(out, "Data"))
    print(f"core64c Data: {ln} linked, {kp} already linked")
    # 6. plan, expectations, README
    probes_plan = [] if a.no_probes else (
        [{"ref": f"{LOAD['slice']}{pid}", "local": list(pos), "what": what} for pid, _e, _p, pos, what in probes]
        + [dict(ANCHOR_PROBE)])
    sides = {"outside": outside, "inside": inside}
    # coming back out, the player faces the interior door's XTEL rotation; going in, the exterior door's
    entry = plan_entry(sides, routes, spawn_local, i_side["xtel"]["rot"][2], o_side["xtel"]["rot"][2], probes_plan)
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump([entry], f, indent=1)
    expected = {
        "slice": "Red Rocket cave door on core64c (docs/slice/cave-routes.md, docs/slice/door-frames.md)",
        "fo4": {"interior_door": inner, "exterior_door": outer, "door_base": link["door_bases"][0]},
        "starfield": {"door_base": sfd["door"]}, "port": {k: port[k] for k in ("cell", "xtel_refs", "door_based_refs")},
        "core64c": {"exterior_door": {"status": dp[0], "reason": dp[1], "detail": dp[2]}, "cave_mouth": mouth[0],
                    "spawn_local": spawn_local, "plugins": list(CORE_PLUGINS)},
        "plugin": {"file": PLUGIN, "masters": ["Starfield.esm", CORE_PLUGINS[0], "FO4Port.esm"],
                   "formids": {"exterior": "000800", "interior": "000801",
                               **{f"probe_{'persistent' if p else 'temporary'}": pid for pid, _e, p, _q, _w in PROBES}},
                   "runtime_ids_supported": {"door": f"{LOAD['slice']}000800", "anchor": f"{LOAD['core']}000800",
                                             "interior_cell": f"{LOAD['port']}{PORT_CELL_ID:06X}"},
                   "persistent_cell_template": a.template_world or None, "probes": not a.no_probes},
        "arrival_headings": {"outside": deg(i_side["xtel"]["rot"][2]), "inside": deg(o_side["xtel"]["rot"][2])},
        "outside": outside, "inside": inside, "routes": {k: {x: routes[k].get(x) for x in (
            "length", "level", "end_to_door_m", "final_walk", "capsule_contacts", "drift", "walk_ms")}
            for k in ("outside", "inside")},
        "plan": entry, "seconds": round(time.time() - t0, 1)}
    with open(os.path.join(out, "expected.json"), "w", encoding="utf-8") as f:
        json.dump(expected, f, indent=1)
    readme(out, expected, a)
    print(f"staged {out} in {time.time() - t0:.0f} s: outside route {routes['outside']['length']} m, inside "
          f"{routes['inside']['length']} m; arrival headings {expected['arrival_headings']}")
    return 0


def readme(out, e, a):
    o, i, p = e["outside"], e["inside"], e["plan"]
    plugins = ",".join(CORE_PLUGINS + (PLUGIN,))
    blocked = getattr(a, "blocked", "")
    text = f"""Slice: the Red Rocket cave door on core64c (Claude, 2026-10-13). NOT deployed by staging.
{('STATUS: BLOCKED ON ' + blocked + chr(10)) if blocked else ''}Docs: docs/slice/cave-routes.md (routes, staging), docs/slice/door-frames.md (runner, persistent-ref merge), docs/slice/redrocket-door.md (the exp2d door).
One install = core64c (FO4TerrainCore.esm + FO4TerrainCore_Mars.esm and its Data tree, HARD LINKS to
the terrain_core64c staging, no second copy) + {PLUGIN}: the Fallout 4 load door between the Commonwealth and RedRocket01
as the vanilla automatic cave door AutoloadDoor_Cave (24F9CE:Starfield.esm) at both ends, persistent, XTEL both ways.
Persistent cell: {('the vanilla shape of ' + a.template_world + "'s persistent cell (door-frames.md fix A)") if a.template_world else 'core64c own record'}; merge probes: {'yes' if p.get('probes') else 'no'}.
FO4Port.esm (the pinned build) is a master: it must load BEFORE {PLUGIN}; the runner's cycle.ps1 orders it.

Install (game closed; the runner does it):
  scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> --plugins {plugins} --pack
  (packs Data into "FO4TerrainCore - Main.ba2", 3.63 GiB, built in %TEMP% first; core64c must not be installed at the
  same time: same plugin and archive names, exp_install refuses).
Before installing: python scripts/slice/make_cave_core64c.py check ... (the hard links still core64c's checked files).

Runner (one door_trip test, --fresh):
  testqueue.py plan-door --staging <pinned build> --exp-dir <this folder> --out <queue> --plugins {plugins} --fresh
The test: coc {COC}, read the arrival (merge offset O), read the door's and the probes' getpos, WALK the outside route
({p['outside']['route'][0]} -> ... {len(p['outside']['route'])} points, {e['routes']['outside']['length']} m) to the cave mouth, arrive in RedRocket01
(facing {p['inside']['arrival_heading']} deg), WALK the inside route ({e['routes']['inside']['length']} m) back to the mouth, arrive outside at the
XTEL point + O facing {p['outside']['arrival_heading']} deg, save {SAVE}, teleport away, load, the same spot and heading again.

Numbers (world frame = FO4 / 70):
  exterior door   {o['door']}  floor {o['door_floor']} ({o['door_floor_owner']}; terrain {o['door_terrain']})
  arrival outside {o['arrival']}  lands on {o['ground']}
  interior door   {i['door']}  floor {i['door_floor']} ({i['door_floor_owner']})
  arrival inside  {i['arrival']}  floor {i['floor']} ({i['arrival_floor_owner']})
Files: {PLUGIN}, the hard-linked core64c plugins and Data, slice_params.json, plan.json, expected.json, routes.json,
routes_outside.png / routes_inside.png, evidence\\, offline_check.json (check).
Uninstall: exp_install.py uninstall.
"""
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(text)


def cmd_check(a):
    require_ready_stage(a.core)
    out = os.path.abspath(a.out)
    ev = os.path.join(out, "evidence")
    port_esm = os.path.join(a.port, "FO4Port.esm")
    core_esm = os.path.join(a.core, CORE_PLUGINS[0])
    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

    params = load(os.path.join(out, "slice_params.json"))
    code, _text = rr.tool("check", os.path.join(out, PLUGIN), a.sf_esm, core_esm, port_esm,
                          os.path.join(out, "slice_params.json"), os.path.join(ev, "check_plugin.json"))
    rep = load(os.path.join(ev, "check_plugin.json"))
    add("SliceDoor check (Mutagen read-back, links, XTEL both ways, persistent cell shape, probes)", code == 0 and rep["ok"],
        f"{sum(c['ok'] for c in rep['checks'])} of {len(rep['checks'])} pass")
    # raw: the override records against their masters (master index 01 = FO4TerrainCore.esm, 02 = FO4Port.esm)
    ours, core, po = rr.records(os.path.join(out, PLUGIN)), rr.records(core_esm), rr.records(port_esm)
    probes = params.get("probes") or []
    n_cells = len({tuple(p["cell"]) for p in probes})
    kinds = {t: sum(1 for r in ours.values() if r[0] == t) for t in sorted({r[0] for r in ours.values()})}
    add("raw record set", kinds == {"CELL": 2 + n_cells, "REFR": 2 + len(probes), "WRLD": 1},
        ", ".join(f"{t} {n}" for t, n in kinds.items()))
    template = (params.get("persistent_cell") or {}).get("template_world")
    for fid, r in sorted(ours.items()):
        if r[0] == "REFR":
            continue
        if fid >> 24 == 1:
            res = rr.compare_override(core.get(fid, ("missing", 0, b"")), r, 1, 1)
            ok = res == "identical"
            if not ok and template and r[0] == "CELL" and (r[1] & 0x400):
                ok, res = True, f"{res}: the persistent cell in {template}'s shape (SliceDoor check compares it)"
            add(f"{r[0]} {fid:08X} = FO4TerrainCore.esm's record", ok, res)
        elif fid >> 24 == 2:
            res = rr.compare_override(po.get((fid & 0xFFFFFF) | 0x01000000, ("missing", 0, b"")), r, 1, 2)
            add(f"{r[0]} {fid:08X} = FO4Port.esm's record", res in ("identical", "formid bytes only"), res)
        else:
            add(f"{r[0]} {fid:08X}", False, "an override of an unexpected master")
    refs = sorted(fid for fid, r in ours.items() if r[0] == "REFR")
    want = [0x03000800, 0x03000801] + [0x03000000 | int(p["id"], 16) for p in probes]
    add("references are this plugin's 0x800 / 0x801 (+ probes)", refs == sorted(want), ", ".join(f"{f:08X}" for f in refs))
    # the install folder: core64c's own files, hard-linked, unchanged since core64c's check
    same = [p for p in CORE_PLUGINS if os.path.samefile(os.path.join(out, p), os.path.join(a.core, p))]
    add("core64c plugins hard-linked (the same files)", len(same) == len(CORE_PLUGINS), ", ".join(same))
    cm = load(os.path.join(a.core, MANIFEST))
    mine = data_manifest(out, CORE_PLUGINS)
    diff = {"missing": sorted(set(cm["files"]) - set(mine)), "added": sorted(set(mine) - set(cm["files"])),
            "changed": sorted(f for f in set(cm["files"]) & set(mine) if list(cm["files"][f]) != list(mine[f]))}
    add(f"install tree = core64c's checked tree ({MANIFEST}: sizes and times, check {'PASS' if cm.get('pass') else 'FAIL'})",
        cm.get("pass") and not any(diff.values()),
        f"{len(mine):,} files; " + ", ".join(f"{len(v)} {k}" for k, v in diff.items()))
    sample = [k for k in sorted(cm["files"]) if k.startswith("Data/")][::5000]
    linked = [k for k in sample if os.path.samefile(os.path.join(out, *k.split("/")), os.path.join(a.core, *k.split("/")))]
    add("Data files are hard links to core64c's (every 5,000th)", len(linked) == len(sample), f"{len(linked)} of {len(sample)}")
    # the plan, through the runner's own planner
    import testqueue                                                     # noqa: E402
    import runner_features                                               # noqa: E402
    import exp_install                                                   # noqa: E402
    plan = load(os.path.join(out, "plan.json"))
    t = testqueue.door_test(0, plan[0])
    add("plan.json is a valid door_trip test (both legs routed)", t["outside"].get("route") and t["inside"].get("route"),
        f"{t['id']}, step timeout {testqueue.step_timeout(t)} s, arrival headings {t['outside'].get('arrival_heading')} / "
        f"{t['inside'].get('arrival_heading')}, moved_m {t['moved_m']}")
    plugins = list(CORE_PLUGINS) + [PLUGIN]
    masters = {p: exp_install.plugin_masters(os.path.join(out, p)) for p in plugins}
    new, _moved, missing = exp_install.order_lines([f"*{p}" for p in plugins] + ["*FO4Port.esm"], plugins, masters)
    add("load order after exp_install.py order", new == [f"*{CORE_PLUGINS[0]}", f"*{CORE_PLUGINS[1]}", "*FO4Port.esm",
                                                         f"*{PLUGIN}"] and not missing, " ".join(new))
    need = sorted(set(runner_features.needs([t])) | ({"plugin_order"} if testqueue.plugin_order_needed(out, plugins) else set()))
    add("the runner features the plan needs exist in this checkout", not runner_features.missing(need), ", ".join(need))
    # the routes
    rt = load(os.path.join(out, "routes.json"))
    for side in ("outside", "inside"):
        s = rt[side]
        add(f"{side} route: walkable on FO4's navmesh and the converted floor, ending within reach of the door",
            s.get("route") and not s.get("off_navmesh") and s["final_walk"]["reaches"],
            f"{s.get('length')} m, level {s.get('level')}, final walk {s['final_walk'].get('to_door_m')} m from the door")
    add("outside route: the assumed capsule (0.35 m) touches nothing", not rt["outside"]["capsule_contacts"],
        f"{len(rt['outside']['capsule_contacts'])} contacts")
    # the runner's test bound to the checked inputs: its routes are routes.json's, its probes the plugin's
    bad = bind_plan(t, rt, params)
    add("plan.json's routes and probes (as the runner reads them) are routes.json's and slice_params.json's", not bad,
        "; ".join(bad) if bad else f"{len(t['outside']['route'])} + {len(t['inside']['route'])} waypoints, "
        f"{len(t.get('probes') or [])} probes agree")
    # pins
    pins = {p: sha256(os.path.join(out, p)) for p in plugins}
    pins.update({"FO4Port.esm": sha256(port_esm), "plan.json": sha256(os.path.join(out, "plan.json")),
                 "slice_params.json": sha256(os.path.join(out, "slice_params.json")),
                 "routes.json": sha256(os.path.join(out, "routes.json")),
                 f"core64c {MANIFEST}": sha256(os.path.join(a.core, MANIFEST))})
    commit = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    ok = all(c["ok"] for c in checks)
    with open(os.path.join(out, "offline_check.json"), "w", encoding="utf-8") as f:
        json.dump({"ok": ok, "checked": time.strftime("%Y-%m-%dT%H:%M:%S"), "commit": commit, "pins": pins,
                   "checks": checks, "plugin_check": rep}, f, indent=1)
    print("all checks pass" if ok else f"{sum(not c['ok'] for c in checks)} checks FAIL")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("stage", "check"):
        s = sub.add_parser(name)
        s.add_argument("--sf-esm", required=True)
        s.add_argument("--port", required=True, help="the pinned build folder (FO4Port.esm, manifest, cell exports)")
        s.add_argument("--core", required=True, help="core64c's staged folder")
        s.add_argument("--out", required=True)
        if name == "stage":
            s.add_argument("--fo4", required=True, help="Fallout4.esm")
            s.add_argument("--template-world", default="",
                           help="vanilla world whose persistent cell record shape the override takes (fix A)")
            s.add_argument("--no-probes", action="store_true", help="no XMarker merge probes")
            s.add_argument("--probe-cell", type=int, nargs=2, default=None, metavar=("X", "Y"),
                           help="put the probes in this exterior cell instead of the COC cell (-10, 11), shifted by whole cells")
            s.add_argument("--blocked", default="", help="README status line, e.g. 'persistent-ref placement'")
    a = ap.parse_args(argv)
    return cmd_stage(a) if a.cmd == "stage" else cmd_check(a)


if __name__ == "__main__":
    sys.exit(main())
