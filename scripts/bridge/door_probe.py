"""The scripted door's Step 0 (docs/slice/scripted-door.md "Step 0"): one queue of four fresh-launch terrain tests that
answers the two unknowns of the door design before any door record exists, with FO4SF_Probe.Resolve / MoveTo
(scripts/bridge/FO4SF_Probe.psc, the contract of scripts/door_bridge/FO4SF_LoadDoor.psc: plugin file name +
plugin-local id, Game.GetFormFromFile, MoveTo matching rotation):
  1. does GetFormFromFile resolve a TEMPORARY reference of an unloaded exterior cell from inside an interior (the
     return trip's destination)?
  2. where does the player land after MoveTo to the PERSISTENT core anchor 0x800 (persistent references of the overlay
     read their unmerged position in game), with no offset and with the merge offset (-1200, -2700, 0)?

usage:
  python scripts/bridge/door_probe.py stage --core <terrain core dir> --out <NEW experiment dir>
      reads the three targets from <core>/FO4TerrainCore.esm (the anchor 0x800, the Stimpak 0x0116FB at the Red Rocket
      arrival, the Super Duper Mart door 0x02D22C 728 m away) and checks their storage (persistent / temporary), cells
      and slots (formids.json); hard-links the core's two plugins and Data\\ (never a copy); writes plan.json (four
      tests), probe_targets.json and README.txt. Refuses an existing --out.
  python testqueue.py plan-terrain --staging <FO4Port build> --exp-dir <out> --out <queue> --bridge <staged bridge>
      --plugins FO4TerrainCore.esm,FO4TerrainCore_Mars.esm --fresh
  python scripts/bridge/door_probe.py readme --queue <queue> --exp-dir <out>
      README.txt in the queue folder: what each test types, and which bridge.log line decides which unknown.
Game data stays outside the repo; nothing here touches the game or its install.
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "slice"))
import persistent_refs  # noqa: E402

CORE_PLUGIN = "FO4TerrainCore.esm"
PLUGINS = ("FO4TerrainCore.esm", "FO4TerrainCore_Mars.esm")
WORLD = "FO4Core_Commonwealth"
SPAWN_COC = "FO4Core_RedRocketSpawn"
CAVE_CELL = "FO4Port_RedRocket01"
MERGE = (-1200.0, -2700.0)         # overlays_params planet_target_cell [-12, -27] x 100 m; measured -1200.0, -2700.0
# plugin-local ids: name, local id, the FO4 source and formids.json section that must name the same slot, and the
# storage the test needs ("persistent": the world's persistent cell; "temporary": an exterior cell's temporary group)
TARGETS = (
    ("anchor", 0x000800, None, None, "persistent"),
    ("stimpak", 0x0116FB, "066996:Fallout4.esm", "items", "temporary"),
    ("far_door", 0x02D22C, "0EE661:Fallout4.esm", "refs", "temporary"),
)
NEAR_M, FAR_M = 50.0, 500.0        # the Stimpak must be in the arrival's loaded area, the door far outside it
# the cave's inside arrival (FO4 08EB65's XTEL / 70) and its floor, from docs/slice/cave-routes.md ("start (XTEL arrival)")
CAVE_POINT = {"label": "cave_arrival", "x": 0.0493, "y": -6.622, "expect": 0.2442}
PLAYER_ID = 0x14                   # PlayerRef: FO4SF_Probe.Pos 20 reads the player


def resolve(local):
    return f'cgf "FO4SF_Probe.Resolve" "{CORE_PLUGIN}" {local}'


def moveto(local, dx, dy, dz):
    return f'cgf "FO4SF_Probe.MoveTo" "{CORE_PLUGIN}" {local} {dx:.1f} {dy:.1f} {dz:.1f}'


def ack(tag):
    return f'cgf "FO4SF_Probe.Ack" "{tag}"'


def check_targets(rep, formids):
    """{name: {local, local_hex, edid, base, pos, cell, cell_grid, storage}} from a persistent_refs.walk report of the
    core plugin (with --worlds FO4Core_Commonwealth), or SystemExit naming what does not match: a target missing, in
    the wrong storage, or its slot not the FO4 reference formids.json names."""
    world = (rep.get("worlds") or {}).get(WORLD)
    if not world or not world.get("persistent_cell"):
        sys.exit(f"{WORLD} or its persistent cell not found in the core plugin")
    pcell = world["persistent_cell"]["formid"]
    by_local = {int(r["formid"], 16) & 0xFFFFFF: r for r in rep.get("refs") or []}
    out = {}
    for name, local, src, section, storage in TARGETS:
        r = by_local.get(local)
        if r is None:
            sys.exit(f"{name} {local:06X} is not a reference of the core plugin")
        if storage == "persistent":
            ok = r.get("persistent") and r.get("group") == "persistent children" and r.get("cell") == pcell
        else:
            ok = (not r.get("persistent") and r.get("group") == "temporary children"
                  and r.get("cell_kind") == "exterior")
        if not ok:
            sys.exit(f"{name} {local:06X} is not {storage} where the test needs it: {r.get('group')} "
                     f"{r.get('record_flags')} cell {r.get('cell')} ({r.get('cell_kind')})")
        if src:
            slot = (formids.get(section) or {}).get(src)
            slot = slot.get("ref") if isinstance(slot, dict) else slot
            if slot != f"{local:06X}":
                sys.exit(f"{name}: formids.json {section}[{src}] is {slot!r}, not {local:06X}")
        out[name] = {"local": local, "local_hex": f"{local:06X}", "src": src, "edid": r.get("edid"),
                     "base": r.get("base"), "pos": r.get("pos"), "cell": r.get("cell"), "cell_grid": r.get("cell_grid"),
                     "storage": storage, "record_flags": r.get("record_flags")}
    return out


def check_distances(targets, spawn_local):
    """The Stimpak in the arrival's own loaded area, the far door outside it (xy metres from the coc arrival)."""
    d = {k: math.dist(spawn_local[:2], v["pos"][:2]) for k, v in targets.items()}
    if d["stimpak"] > NEAR_M:
        sys.exit(f"the Stimpak is {d['stimpak']:.1f} m from the arrival (want <= {NEAR_M})")
    if d["far_door"] < FAR_M:
        sys.exit(f"the far door is only {d['far_door']:.1f} m from the arrival (want >= {FAR_M})")
    for k, v in targets.items():
        v["from_arrival_m"] = round(d[k], 1)
    return d


def plan_entries(spawn_local, zref, drop_z=175.0, settle_ms=10000):
    """The four plan.json entries (testqueue.py plan-terrain). zref: the core plan's Z reference point (local frame)."""
    a, s, d = (t[1] for t in TARGETS)
    three = [resolve(a), resolve(s), resolve(d)]
    merged = dict(zref, x=round(zref["x"] + MERGE[0], 4), y=round(zref["y"] + MERGE[1], 4), label="zref_ground")
    after = [f'cgf "FO4SF_Probe.Pos" {PLAYER_ID}', resolve(a), resolve(s)]
    ext = {"spawn_local": list(spawn_local), "drop_z": drop_z, "settle_ms": settle_ms, "z_ref": "zref_ground"}
    return [
        dict(ext, coc=SPAWN_COC, travel=f"coc {SPAWN_COC}", points=[dict(zref)],
             beyond={"x": spawn_local[0], "y": spawn_local[1]},
             label="door probe (a): at the Red Rocket arrival, resolve the anchor, the Stimpak (loaded) and the far door",
             console_post=[ack("door-probe-a")] + three),
        {"coc": CAVE_CELL, "travel": f"coc {CAVE_CELL}", "drop_z": round(CAVE_POINT["expect"] + 1.5, 4),
         "points": [dict(CAVE_POINT)], "beyond": {"x": CAVE_POINT["x"], "y": CAVE_POINT["y"]},
         "label": "door probe (b): inside RedRocket01 (fresh: no exterior loaded this session), the same three",
         "console_post": [ack("door-probe-b")] + three},
        {"coc": CAVE_CELL, "travel": f"coc {CAVE_CELL}", "drop_z": drop_z, "settle_ms": settle_ms, "z_ref": "zref_ground",
         "points": [dict(zref)], "beyond": {"x": zref["x"], "y": zref["y"]},
         "label": "door probe (c): from inside, MoveTo the persistent anchor with no offset, then where the player is",
         "console_post": [ack("door-probe-c"), resolve(a), moveto(a, 0.0, 0.0, 0.0)] + after},
        {"coc": CAVE_CELL, "travel": f"coc {CAVE_CELL}", "drop_z": drop_z, "settle_ms": settle_ms, "z_ref": "zref_ground",
         "points": [merged], "beyond": {"x": merged["x"], "y": merged["y"]},
         "label": "door probe (d): from inside, MoveTo the persistent anchor plus the merge offset (-1200, -2700, 0)",
         "console_post": [ack("door-probe-d"), resolve(a), moveto(a, MERGE[0], MERGE[1], 0.0)] + after},
    ]


def link_tree(src, dst):
    """Hard-link every file of src into dst; the count. A file that cannot be linked stops the stage (no copies)."""
    n = 0
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        os.makedirs(os.path.join(dst, rel), exist_ok=True)
        for fn in files:
            os.link(os.path.join(root, fn), os.path.join(dst, rel, fn))
            n += 1
    return n


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(p, obj):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)


def stage(a):
    core, out = os.path.abspath(a.core), os.path.abspath(a.out)
    if os.path.exists(out):
        sys.exit(f"{out} exists: the stage writes a new folder only")
    rep = persistent_refs.walk(os.path.join(core, CORE_PLUGIN), worlds=[WORLD],
                               refs=[f"{t[1]:06X}" for t in TARGETS])
    targets = check_targets(rep, load(os.path.join(core, "formids.json")))
    first = load(os.path.join(core, "plan.json"))[0]
    if first.get("coc") != SPAWN_COC or first["points"][0]["label"] != "zref_ground":
        sys.exit(f"{core}\\plan.json's first entry is not the {SPAWN_COC} arrival with zref_ground first")
    spawn_local, zref = first["spawn_local"], first["points"][0]
    check_distances(targets, spawn_local)
    os.makedirs(out)
    for p in PLUGINS:
        os.link(os.path.join(core, p), os.path.join(out, p))
    n = link_tree(os.path.join(core, "Data"), os.path.join(out, "Data"))
    plan = plan_entries(spawn_local, {k: zref[k] for k in ("label", "x", "y", "expect")},
                        float(first.get("drop_z", 175.0)), int(first.get("settle_ms", 10000)))
    save(os.path.join(out, "plan.json"), plan)
    info = {"core": core, "plugin": CORE_PLUGIN, "world": WORLD, "persistent_cell": rep["worlds"][WORLD]["persistent_cell"]["formid"],
            "spawn_local": spawn_local, "zref": zref, "merge": list(MERGE), "targets": targets, "data_links": n}
    save(os.path.join(out, "probe_targets.json"), info)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(stage_readme(info))
    print(f"staged {out}: {', '.join(PLUGINS)} and Data ({n} files) hard-linked from {core}; plan.json (4 tests)")
    for k, v in targets.items():
        print(f"  {k:9s} {v['local_hex']} = {v['local']:>7d}  {v['storage']:10s} cell {v['cell']} {v['cell_grid']} "
              f"pos {v['pos']}  {v['from_arrival_m']} m from the arrival")


def stage_readme(info):
    t = info["targets"]
    return f"""Scripted door Step 0: door probe experiment (Claude). docs/slice/scripted-door.md "Step 0".
Plugins and Data hard-linked from {info['core']} ({info['data_links']} Data files linked, 0 copied): nothing new
is installed but the core itself; the probe is the bridge's FO4SF_Probe (Resolve / MoveTo), staged separately.
Targets in {info['plugin']} (read from the plugin; plugin-local ids, as GetFormFromFile takes them):
  anchor    {t['anchor']['local_hex']} = {t['anchor']['local']}  {t['anchor']['edid']}, persistent in the world's persistent cell {info['persistent_cell']}, local {t['anchor']['pos']}
  stimpak   {t['stimpak']['local_hex']} = {t['stimpak']['local']}  {t['stimpak']['src']}, temporary in exterior cell {t['stimpak']['cell']} {t['stimpak']['cell_grid']}, local {t['stimpak']['pos']}, {t['stimpak']['from_arrival_m']} m from the arrival
  far_door  {t['far_door']['local_hex']} = {t['far_door']['local']}  {t['far_door']['src']}, temporary in exterior cell {t['far_door']['cell']} {t['far_door']['cell_grid']}, local {t['far_door']['pos']}, {t['far_door']['from_arrival_m']} m from the arrival
plan.json: four terrain tests, each from a fresh launch (plan-terrain --fresh): (a) coc {SPAWN_COC}, (b) (c) (d)
coc {CAVE_CELL}; console_post types the probe lines; the bridge's log is the evidence (the queue's README.txt says
which line decides what). Install: exp_install.py install --exp-dir <this folder> --plugins {','.join(PLUGINS)} --pack
(the runner does it).
"""


def queue_readme(q, info, plugin_index=None):
    """The queue's README.txt: preconditions, the tests, and which bridge.log line decides which unknown."""
    idx = plugin_index or {"core": 0x02, "port": 0x04}
    t = info["targets"]

    def rt(local, key="core"):
        v = (idx[key] << 24) | local
        return f"{v} = {v:08X}"
    loc = t["anchor"]["pos"]
    merged = (loc[0] + MERGE[0], loc[1] + MERGE[1])
    doubled = (loc[0] + 2 * MERGE[0], loc[1] + 2 * MERGE[1])
    st = t["stimpak"]["pos"]
    br = q.get("bridge") or {}
    lines = [f"Scripted door Step 0: door probe queue (Claude). docs/slice/scripted-door.md \"Step 0\", docs/ai/test-queue.md \"Bridge\".",
             f"Build: FO4Port {q.get('build_id')} ({q.get('staging')}); experiment {q.get('experiment')} (core plugins hard-linked from",
             f"  {info['core']}); bridge {br.get('dir')} (FO4SF_Probe.pex with Resolve / MoveTo); planned at commit {str(q.get('commit'))[:8]}.",
             f"Needs runner features {', '.join(q.get('needs') or [])}: a runner checkout without probe_moveto refuses the queue before",
             "  launching (update the runner's worktree to a commit that has it first).",
             "",
             "BEFORE THE RUN (game closed; the runner never does these):",
             "  1. The game has another bridge installed (Data\\FO4SFBridge.install.json; bridge_t0 on 2026-10-16) and",
             "     bridge_install.py refuses a second one, so the runner would stop before the launch. Swap it:",
             "       python scripts\\game\\bridge_install.py uninstall --dir <the installed bridge's dir> --starfield <game>",
             f"     The runner then installs {br.get('dir')} itself. A queue pinned to the old bridge needs the reverse swap.",
             "  2. Any other installed experiment: exp_install.py uninstall (the pre_launch install refuses otherwise).",
             "Run: python scripts\\game\\testqueue.py run --queue <this folder> --max-attempts 1   (or the chain).",
             "Time: four fresh launches. core64h_accept_1016 (2026-10-16) took 10.8 and 11.6 min per fresh test (install",
             "  check 4.5, launch 2.8, save 0.8, test 3.2): about 45-50 min for the four, plus the first archive build.",
             "",
             "TESTS (each its own launch; console_post typed after the arrival, one console session per line):"]
    for x in q["tests"]:
        lines.append(f"  {x['id']}  travel {x.get('travel') or 'coc ' + x['world_coc']}  fresh={bool(x.get('fresh'))}")
        lines.append(f"      {x.get('model')}")
        for c in x.get("console_post") or []:
            lines.append(f"      > {c}")
    lines += [
        "  After a MoveTo line qstep.ps1 waits up to 90 s for the HUD (obs.json console[k]: hud_back, load_s,",
        "  console_<k>_hud.png) before the next line. The probe points afterwards only keep the step's usual shape:",
        "  (a) zref_ground at the arrival, (b) the cave's XTEL arrival, (c) zref_ground LOCAL, (d) zref_ground MERGED,",
        "  each dropped on and read; a PASS there means only that the player stood at that point.",
        "",
        "WHERE THE EVIDENCE IS: tests\\<id>\\a1\\bridge.log (the bridge's user log of that session, copied after the step),",
        "papyrus.log beside it, obs.json, console_<k>.png. Print the probe lines of one attempt as JSON:",
        "  python scripts\\game\\bridge_log.py events --log <queue>\\tests\\<id>\\a1\\bridge.log",
        "Line formats (FO4SF_Probe.psc; ids are signed decimals, as Papyrus prints an int; the parser gives 8 hex):",
        "  FO4SF resolve plugin=FO4TerrainCore.esm id=<local> form=none",
        "  FO4SF resolve plugin=.. id=.. form=<runtime id> ref=true pos=<x> <y> <z> ang=.. cell=<id>|none cellname=..",
        "        world=<id>|none worldname=.. disabled=<bool> loaded=<bool>       (ref=false: a form that is not a reference)",
        "  FO4SF target ...   MoveTo's own lookup of its destination, the same fields",
        "  FO4SF moveto plugin=.. id=.. offset=<dx> <dy> <dz> phase=before|after|settled pos=.. ang=.. cell=.. cellname=..",
        "        world=.. worldname=.. loaded=..                                  (phase=refused: no reference to move to)",
        "  FO4SF ref=20 pos=.. ang=.. cell=.. disabled=.. loaded=..   FO4SF_Probe.Pos of the player (0x14)",
        "  FO4SF rt=.. pos=.. ang=.. cell=.. world=.. loaded=.. n=..   the bridge's own line every ~0.66 s (the player)",
        "  FO4SF ack door-probe-<a|b|c|d>                             the test's first console line: the console path works",
        "Ids at the runner's order (FO4TerrainCore 02, FO4Port 04; read the index from the lines, never assume it):",
        f"  anchor {t['anchor']['local']} -> {rt(t['anchor']['local'])}; Stimpak {t['stimpak']['local']} -> {rt(t['stimpak']['local'])};"
        f" far door {t['far_door']['local']} -> {rt(t['far_door']['local'])};",
        f"  the world's persistent cell {rt(int(info['persistent_cell'], 16) & 0xFFFFFF)}; the arrival cell (Stimpak's) "
        f"{rt(int(t['stimpak']['cell'], 16) & 0xFFFFFF)}; FO4Port_RedRocket01 {rt(0x002338, 'port')}.",
        "  The merged planet world's id is a runtime id that differs per session (FF.. printed negative: -16707575,",
        "  -16708042, -16708381 in three 2026-10-16 sessions): compare world= only within one session.",
        f"Positions (xy m): the anchor local ({loc[0]:.3f}, {loc[1]:.3f}) z {loc[2]:.3f}; merged = local + ({MERGE[0]:.0f}, {MERGE[1]:.0f}) =",
        f"  ({merged[0]:.3f}, {merged[1]:.3f}), where Red Rocket is drawn (the coc arrival read -2189.257 -1553.486 105.261 in",
        f"  core64h_accept_1016); doubled = ({doubled[0]:.3f}, {doubled[1]:.3f}); the Stimpak merged ({st[0] + MERGE[0]:.3f}, {st[1] + MERGE[1]:.3f}).",
        "",
        "THE CONTROL (decide nothing before it): test 0000 (a), the line \"FO4SF resolve ... id=2048\" after \"FO4SF ack",
        f"door-probe-a\" must read form=<id> ref=true with the low six hex digits 000800 ({rt(t['anchor']['local'])} at index 02).",
        "  form=none there: GetFormFromFile does not take (file name, plugin-local id) on this build, and FO4SF_LoadDoor's",
        "  contract is wrong; the other lines answer nothing. No resolve line at all after the ack: the script or the",
        "  console failed (papyrus.log, console_<k>.png), not an answer. Same test, id=71419 (the Stimpak, loaded at the",
        "  arrival) must read form=.. ref=true loaded=true: the positive control for a temporary reference.",
        "",
        "UNKNOWN 1 (does a TEMPORARY exterior reference resolve from inside an interior while its cell is not loaded?)",
        "  Decides: test 0001 (b), its two lines \"FO4SF resolve ... id=71419\" (the Stimpak) and \"... id=184876\" (the",
        f"  far door). The session starts from this build's dedicated save (made in the launch cell FO4Port_{q.get('launch_cell')},",
        "  an interior) and the test's coc goes straight to RedRocket01: every bridge line before the ack must read",
        "  world=none (no exterior cell loaded in the session), else the reading is not cold.",
        "    both form=none                       -> NO. The return door cannot target a temporary exterior marker: it",
        "                                            needs a persistent one (unknown 2 says with which offset).",
        "    both form=<id> ref=true (loaded=false) -> YES. A temporary arrival marker in the exterior cell is a valid",
        "                                            destination; its pos= says which frame an unloaded temporary",
        f"                                            reference reports (merged = local + ({MERGE[0]:.0f}, {MERGE[1]:.0f}), or local).",
        "    one resolves, the other not          -> not decided: record both lines.",
        "  Supporting: test 0000's id=184876 line (the far door from the exterior, its cell 728 m away and not loaded)",
        "  separates \"unloaded\" from \"seen from an interior\".",
        "",
        "UNKNOWN 2 (where does MoveTo to the PERSISTENT anchor put the player?)",
        "  Decides: the \"FO4SF moveto ... id=2048 ... phase=after\" and \"phase=settled\" lines of test 0002 (c, offset",
        "  0 0 0) and test 0003 (d, offset -1200 -2700 0), each the first arrival in the merged world of its session.",
        f"    (c) within 3 m of merged ({merged[0]:.1f}, {merged[1]:.1f})  -> MoveTo to a persistent overlay reference lands where",
        "                                            the overlay is drawn: a persistent exterior marker, no offset ((d) then",
        f"                                            reads near doubled ({doubled[0]:.1f}, {doubled[1]:.1f})).",
        f"    (c) within 3 m of local ({loc[0]:.1f}, {loc[1]:.1f}) and (d) within 3 m of merged",
        "                                         -> MoveTo uses the stored, unmerged position: a persistent marker plus",
        "                                            the offset (-1200, -2700, 0) (FO4SF_LoadDoor needs offset properties;",
        "                                            valid only while the merge offset stays the same: test 0000's",
        "                                            obs.json offset, the arrival minus spawn_local, is this build's).",
        f"    phase=settled with world=none or cell={rt(0x002338, 'port').split(' ')[0]} (still FO4Port_RedRocket01)",
        "                                         -> the player never left: MoveTo from inside to a persistent exterior",
        "                                            reference did nothing.",
        "    anything else                        -> neither: record the numbers; the door design stays open.",
        "  Supporting, in order after the move: \"FO4SF ref=20\" (the player, read after the HUD came back), the bridge's",
        "  own lines (world=), \"FO4SF resolve ... id=2048\" again (what the anchor reports now), \"... id=71419\" (loaded=true",
        "  only if the player stands at the merged Red Rocket), obs.json console[k] hud_back / load_s and",
        "  console_<k>_hud.png (a popup such as Boundary Reached), the test's verdict at its probe point.",
        "",
        "WHAT IT MEANS FOR THE DOOR (docs/slice/scripted-door.md): unknown 1 YES -> the interior door's destination is a",
        "temporary arrival marker in the exterior cell (it reads merged like every core object): no offset, unknown 2 is",
        "only a fallback. Unknown 1 NO -> a persistent arrival marker, with the offset unknown 2 gives (or, if neither,",
        "the design stays open).",
    ]
    return "\r\n".join(lines) + "\r\n"


def readme(a):
    q = load(os.path.join(a.queue, "queue.json"))
    info = load(os.path.join(a.exp_dir or q["experiment"], "probe_targets.json"))
    text = queue_readme(q, info)
    with open(os.path.join(a.queue, "README.txt"), "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"wrote {os.path.join(a.queue, 'README.txt')} ({len(text.splitlines())} lines)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage")
    s.add_argument("--core", required=True, help="the terrain core's staging folder (FO4TerrainCore.esm, formids.json, plan.json, Data)")
    s.add_argument("--out", required=True, help="a NEW folder")
    r = sub.add_parser("readme")
    r.add_argument("--queue", required=True)
    r.add_argument("--exp-dir", default="")
    a = ap.parse_args(argv)
    (stage if a.cmd == "stage" else readme)(a)


if __name__ == "__main__":
    main()
