"""Round trips through every scripted load door of an INSTALLED set (docs/terrain/door-rounds.md): per door one test
in (activate the exterior door, land on the interior arrival marker) and one test out (activate the interior door, land
on the exterior arrival marker), judged from the bridge's log. The Super Duper Mart queues of 2026-10-17 were hand
planned against one core; this plans every door against the plugins actually installed, so a reconverted core (v5's
47 new FLOR bases shifted its appended ids) can not leave a queue pointing at old ids.

usage:
  python scripts/bridge/door_rounds.py order --plugins-txt <Plugins.txt> [--first-index 02]
      the load indices the runner's launch gives (cycle.ps1 re-deploys FO4Port.esm at the end of Plugins.txt, the
      bridge goes last): read them before planning; the judge checks them again against the game's own lines.
  python scripts/bridge/door_rounds.py stage --core <core build dir> --port <installed FO4Port staging>
         --core-index HH --port-index HH --out <NEW folder> [--core-plugin <installed FO4TerrainCore.esm>]
         [--only <cell editor id or FO4 door src>,...] [--limit N]
      reads the doors (objects.json / formids.json of --core) and checks each one in the INSTALLED plugins: the
      exterior door REFR, its base and its FO4SF_LoadDoor VMAD (destination = the port's arrival marker), the interior
      door REFR, its base and its VMAD (destination = the core's arrival marker), both markers. A door that fails a
      check is listed as skipped, with why, and never planned. Writes plan.json (two terrain tests per door),
      rounds.json (what each test must read) and README.txt. Refuses an existing --out. Nothing is linked or copied.
  python scripts/game/testqueue.py plan-terrain --staging <installed FO4Port staging> --exp-dir <out> --out <queue>
         --bridge <installed bridge staging>          (no --plugins: the installed set stays as it is)
  python scripts/game/testqueue.py run --queue <queue> --max-attempts 1
  python scripts/bridge/door_rounds.py judge --queue <queue> [--rounds <out>/rounds.json]
      PASS: the player's last bridge line after the test's ack is within TOL_M of the arrival marker (in the
      interior's cell going in, in the exterior world coming out). FAIL WRONG_PLACE / STAYED otherwise; INCONCLUSIVE
      when the runner did not activate (the GetIsID proof failed: obs.json), the log has no line after the ack, or a
      resolve line shows another load index than planned (INDEX: re-plan with the right --core-index / --port-index).
Game data stays outside the repo; nothing here touches the game or its install.
"""
import argparse
import json
import math
import os
import re
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "scripts", "terrain"))
sys.path.insert(0, os.path.join(REPO, "scripts", "game"))
import vmad_patch  # noqa: E402
import bridge_log  # noqa: E402
from fo4sf import fo4land  # noqa: E402

CORE_PLUGIN = "FO4TerrainCore.esm"
PORT_PLUGIN = "FO4Port.esm"
BRIDGE_PLUGIN = "FO4SFBridge.esm"
SPAWN_COC = "FO4Core_RedRocketSpawn"
COMPRESSED = 0x00040000
CELL_GROUPS = (vmad_patch.GROUP_CELL_CHILDREN, vmad_patch.GROUP_PERSISTENT, vmad_patch.GROUP_TEMPORARY)
HOP_M = 185                      # the SDM round's hops (2026-10-17: 4 hops of 182 m, PASS)
HOP_WAIT_MS = 7000
SETTLE_MS = 14000
STAND_ABOVE_M = 30.0             # the exterior drop starts at least this far above the arrival marker
INTERIOR_DROP_M = 1.5            # the interior drop: just above the marker (the SDM return: expect + 1.5)
# the scripted exterior load doors are ACTI bases in the core (make_core64c: the FO4SF_LoadDoor VMAD does the load, PC
# read of fdd3f0a5 on 2026-10-18: 0A7756 ACTI FO4Core_door_01f65a_fallout4); the port's interior doors are DOOR bases
DOOR_BASES = ("DOOR", "ACTI")
TOL_M = 3.0                      # judge_door_trip.py's 3 m


def load(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def save(p, obj):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)


# ------------------------------------------------------------------------------------------------------------ plugins
def fields(flags, data):
    if flags & COMPRESSED:
        data = zlib.decompress(data[4:])
    return list(fo4land.iter_subrecords(data))


class Installed:
    """One installed plugin's records by local id: kind, base, pos, rot, VMAD destination, cell (from its group)."""

    def __init__(self, path):
        p = vmad_patch.Plugin.read(path)
        self.path, self.name = path, os.path.basename(path)
        self.own = len(p.masters())
        self.recs = {}
        for fid, (sig, flags, data, gpath) in p.records().items():
            if fid >> 24 != self.own:
                continue
            self.recs[fid & 0xFFFFFF] = (sig.decode("ascii", "replace"), flags, data, gpath)

    def ref(self, local):
        """{"sig", "base" (local id, None for another plugin's), "pos", "rot", "cell" (local), "vmad" (bytes or None)},
        None when the id is not a record of this plugin."""
        r = self.recs.get(local)
        if r is None:
            return None
        sig, flags, data, gpath = r
        fs = fields(flags, data)
        out = fo4land.parse_ref(fs)
        base = out["base"]
        cell = next((label for gtype, label in reversed(gpath) if gtype in CELL_GROUPS), None)
        return {"sig": sig, "base": base & 0xFFFFFF if base is not None and base >> 24 == self.own else None,
                "base_full": base, "pos": out["pos"], "rot": out["rot"],
                "cell": cell & 0xFFFFFF if cell is not None else None,
                "vmad": next((d for s, d in fs if s == b"VMAD"), None)}

    def edid(self, local):
        r = self.recs.get(local)
        if r is None:
            return None
        return next((fo4land.zstring(d) for s, d in fields(r[1], r[2]) if s == b"EDID"), None)


def check_ref(plug, local, what, want_sig="REFR"):
    r = plug.ref(local)
    if r is None:
        raise ValueError(f"{what} {local:06X} is not a record of the installed {plug.name}")
    if r["sig"] != want_sig or r["pos"] is None:
        raise ValueError(f"{what} {local:06X} is a {r['sig']} without a position, not a placed reference")
    return r


def check_target(r, what, plugin, local):
    """The decoded (plugin, id, position) of a door REFR's VMAD, or ValueError when it does not lead to plugin:local."""
    if r["vmad"] is None:
        raise ValueError(f"{what} has no VMAD (not a scripted load door in the installed plugin)")
    got_plugin, got_id, pos = vmad_patch.load_door_target(r["vmad"])
    if got_plugin.casefold() != plugin.casefold() or got_id != local:
        raise ValueError(f"{what} leads to {got_plugin}:{got_id:06X}, the build says {plugin}:{local:06X}")
    return pos


def door_round(e, core, port, merge):
    """One door's two legs from the build's entry and the installed plugins, or ValueError naming the first mismatch."""
    ids, d = e["ids"], e["destination"]
    ext_ref, ext_base, ext_arrival = (int(ids[k], 16) for k in ("ref", "base", "arrival"))
    marker, int_ref = int(d["id"]), int(d["ref"], 16)
    door = check_ref(core, ext_ref, "exterior door")
    if door["base"] != ext_base:
        raise ValueError(f"exterior door {ext_ref:06X} has base {door['base_full']:08X}, the build says {ext_base:06X}")
    if core.ref(ext_base) is None or core.ref(ext_base)["sig"] not in DOOR_BASES:
        raise ValueError(f"exterior door base {ext_base:06X} is not a DOOR or ACTI of the installed {core.name}")
    check_target(door, f"exterior door {ext_ref:06X}", port.name, marker)
    inside = check_ref(port, marker, "interior arrival marker")
    idoor = check_ref(port, int_ref, "interior door")
    if idoor["base"] is None or port.ref(idoor["base"]) is None or port.ref(idoor["base"])["sig"] not in DOOR_BASES:
        raise ValueError(f"interior door {int_ref:06X}'s base {idoor['base_full']} is not a DOOR or ACTI of {port.name}")
    if inside["cell"] is None or inside["cell"] != idoor["cell"]:
        raise ValueError(f"interior marker {marker:06X} (cell {inside['cell']}) and door {int_ref:06X} (cell "
                         f"{idoor['cell']}) are not in one cell")
    back = check_target(idoor, f"interior door {int_ref:06X}", core.name, ext_arrival)
    outside = check_ref(core, ext_arrival, "exterior arrival marker")
    cell_edid = port.edid(inside["cell"])
    if not cell_edid or not re.fullmatch(r"[A-Za-z0-9_]+", cell_edid):
        raise ValueError(f"interior cell {inside['cell']:06X} has no usable editor id for coc ({cell_edid!r})")
    merged = list(back) if back is not None else vmad_patch.merged(outside["pos"], merge)
    return {"src": e["src"], "cell_edid": cell_edid, "cell": f"{inside['cell']:06X}",
            "exterior": {"door": f"{ext_ref:06X}", "base": f"{ext_base:06X}", "arrival": f"{ext_arrival:06X}",
                         "arrival_local": [round(v, 4) for v in outside["pos"]],
                         "arrival_merged": [round(v, 4) for v in merged],
                         "return_position_in_vmad": back is not None},
            "interior": {"door": f"{int_ref:06X}", "base": f"{idoor['base']:06X}", "marker": f"{marker:06X}",
                         "marker_pos": [round(v, 4) for v in inside["pos"]]}}


# ------------------------------------------------------------------------------------------------------------- stage
def resolve(plugin, local):
    return f'cgf "FO4SF_Probe.Resolve" "{plugin}" {local}'


def ack(tag):
    return f'cgf "FO4SF_Probe.Ack" "{tag}"'


def full(index, local_hex):
    return f"{index:02X}{local_hex}"


def plan_door(k, r, spawn_local, zref, drop_z, core_index, port_index):
    """(forward entry, return entry, forward expectation, return expectation) for door k."""
    ex, it = r["exterior"], r["interior"]
    stand = ex["arrival_local"]
    dist = math.dist(spawn_local[:2], stand[:2])
    fwd = {"coc": SPAWN_COC, "travel": "", "spawn_local": list(spawn_local), "settle_ms": SETTLE_MS,
           "z_ref": "zref_ground", "hop_m": HOP_M, "hop_wait_ms": HOP_WAIT_MS, "teleport_console": True,
           "drop_z": round(max(drop_z, stand[2] + STAND_ABOVE_M), 4),
           "points": [dict(zref), {"label": "door_front", "x": stand[0], "y": stand[1], "expect": stand[2]}],
           "beyond": {"x": stand[0], "y": stand[1] + 120.0},
           "activate": {"ref": full(core_index, ex["door"]), "base": full(core_index, ex["base"]), "expect": []},
           "console_post": [ack(f"door-fwd-{k}"), resolve(PORT_PLUGIN, int(it["marker"], 16))],
           "label": f"door round {k} IN ({r['cell_edid']}, FO4 {r['src']}): {dist:.0f} m from the Red Rocket arrival "
                    f"to its exterior arrival marker, activate the exterior door {full(core_index, ex['door'])}; "
                    f"expect the interior marker {full(port_index, it['marker'])} at {it['marker_pos']}"}
    m = it["marker_pos"]
    ret = {"coc": r["cell_edid"], "travel": f"coc {r['cell_edid']}", "teleport_console": True,
           "drop_z": round(m[2] + INTERIOR_DROP_M, 4),
           "points": [{"label": "inside_arrival", "x": m[0], "y": m[1], "expect": m[2]}],
           "beyond": {"x": ex["arrival_merged"][0], "y": ex["arrival_merged"][1]},
           "activate": {"ref": full(port_index, it["door"]), "base": full(port_index, it["base"]), "expect": []},
           "console_post": [ack(f"door-ret-{k}"), resolve(CORE_PLUGIN, int(ex["arrival"], 16))],
           "label": f"door round {k} OUT ({r['cell_edid']}): coc inside, activate the interior door "
                    f"{full(port_index, it['door'])}; expect the exterior marker {full(core_index, ex['arrival'])} "
                    f"merged at {ex['arrival_merged']}"}
    efwd = {"leg": "in", "door": k, "src": r["src"], "cell_edid": r["cell_edid"], "ack": f"door-fwd-{k}",
            "pos": m, "cell": full(port_index, r["cell"]), "world": None,
            "resolve": {"plugin": PORT_PLUGIN, "id": int(it["marker"], 16), "index": f"{port_index:02X}"},
            "hops": max(0, math.ceil(dist / HOP_M) - 1)}
    eret = {"leg": "out", "door": k, "src": r["src"], "cell_edid": r["cell_edid"], "ack": f"door-ret-{k}",
            "pos": ex["arrival_merged"], "cell": None, "world": "exterior",
            "resolve": {"plugin": CORE_PLUGIN, "id": int(ex["arrival"], 16), "index": f"{core_index:02X}"}}
    return fwd, ret, efwd, eret


def pick(doors, only):
    if not only:
        return doors
    want = {s.strip().casefold() for s in only.split(",") if s.strip()}
    return [d for d in doors if d["cell_edid"].casefold() in want or d["src"].casefold() in want]


def stage(a):
    core_dir, out = os.path.abspath(a.core), os.path.abspath(a.out)
    if os.path.exists(out):
        sys.exit(f"{out} exists: the stage writes a new folder only")
    core_plugin, entries = vmad_patch.core_doors(core_dir)
    if core_plugin.casefold() != CORE_PLUGIN.casefold():
        sys.exit(f"{core_dir}: formids.json plugin is {core_plugin}, not {CORE_PLUGIN}")
    merge = vmad_patch.merge_offset(core_dir)
    core = Installed(os.path.abspath(a.core_plugin or os.path.join(core_dir, CORE_PLUGIN)))
    port = Installed(os.path.join(os.path.abspath(a.port), PORT_PLUGIN))
    first = load(os.path.join(core_dir, "plan.json"))[0]
    if first.get("coc") != SPAWN_COC or first["points"][0]["label"] != "zref_ground":
        sys.exit(f"{core_dir}: plan.json's first entry is not the {SPAWN_COC} arrival with zref_ground first")
    spawn_local, zref = first["spawn_local"], {k: first["points"][0][k] for k in ("label", "x", "y", "expect")}
    rounds, skipped = [], []
    for e in entries:
        if str(e["destination"].get("plugin", "")).casefold() != PORT_PLUGIN.casefold():
            skipped.append({"src": e["src"], "why": f"destination plugin {e['destination'].get('plugin')}"})
            continue
        try:
            rounds.append(door_round(e, core, port, merge))
        except (ValueError, KeyError) as err:
            skipped.append({"src": e["src"], "why": str(err)})
    rounds = pick(rounds, a.only)[:a.limit or None]
    if not rounds:
        sys.exit("no door passed the checks: " + "; ".join(f"{s['src']}: {s['why']}" for s in skipped))
    ci, pi = int(a.core_index, 16), int(a.port_index, 16)
    plan, expect = [], []
    for k, r in enumerate(rounds):
        f, b, ef, eb = plan_door(k, r, spawn_local, zref, float(first.get("drop_z", 175.0)), ci, pi)
        plan += [f, b]
        expect += [dict(ef, test=2 * k), dict(eb, test=2 * k + 1)]
    os.makedirs(out)
    save(os.path.join(out, "plan.json"), plan)
    info = {"core": core_dir, "core_plugin": core.path, "port_plugin": port.path, "core_index": f"{ci:02X}",
            "port_index": f"{pi:02X}", "merge": list(merge), "tol_m": TOL_M, "doors": rounds, "skipped": skipped,
            "tests": expect}
    save(os.path.join(out, "rounds.json"), info)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(stage_readme(info))
    print(f"staged {out}: {len(rounds)} doors, {len(plan)} tests; {len(skipped)} skipped")
    for r, e in zip(rounds, expect[::2]):
        print(f"  {r['cell_edid']:32s} {r['src']}  out door {r['exterior']['door']} -> in marker {r['interior']['marker']}"
              f"; in door {r['interior']['door']} -> out marker {r['exterior']['arrival']}; {e['hops']} hops")
    for s in skipped:
        print(f"  SKIPPED {s['src']}: {s['why']}")


def stage_readme(info):
    lines = [f"Door round trips (scripts/bridge/door_rounds.py): {len(info['doors'])} scripted load doors, two tests each.",
             f"Checked against the installed plugins {info['core_plugin']} (index {info['core_index']}) and",
             f"{info['port_plugin']} (index {info['port_index']}); the core build {info['core']} gave the pairs.",
             "Plan: testqueue.py plan-terrain --staging <the installed FO4Port staging> --exp-dir <this folder> --out <queue>",
             "  --bridge <the installed bridge staging>  (no --plugins: the installed set is not touched).",
             "Judge: door_rounds.py judge --queue <queue>.", ""]
    for t in info["tests"]:
        lines.append(f"  test {t['test']:04d} {t['leg']:3s} {t['cell_edid']:32s} expect {t['pos']}"
                     + (f" in cell {t['cell']}" if t["cell"] else " in the exterior world"))
    for s in info["skipped"]:
        lines.append(f"  SKIPPED {s['src']}: {s['why']}")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------------------------------------- order
def order(lines, first_index=2, port=PORT_PLUGIN, bridge=BRIDGE_PLUGIN):
    """{plugin: index} of the active Plugins.txt lines after a runner launch: cycle.ps1 re-deploys the port at the end,
    the bridge goes last. Implicit masters (exp_install.implicit) take no line. Assumes full-slot plugins."""
    import exp_install
    names = [ln.strip()[1:].strip() for ln in lines if ln.strip().startswith("*")]
    names = [n for n in names if not exp_install.implicit(n)]
    rest = [n for n in names if n.casefold() not in (port.casefold(), bridge.casefold())]
    return {n: first_index + i for i, n in enumerate(rest + [port, bridge])}


def cmd_order(a):
    with open(a.plugins_txt, encoding="utf-8-sig", errors="replace") as f:
        idx = order(f.read().splitlines(), int(a.first_index, 16))
    for n, i in idx.items():
        print(f"  {i:02X}  {n}")
    print(f"--core-index {idx.get(CORE_PLUGIN, 0):02X} --port-index {idx[PORT_PLUGIN]:02X}"
          if CORE_PLUGIN in idx else f"{CORE_PLUGIN} is not active in {a.plugins_txt}")


# ------------------------------------------------------------------------------------------------------------- judge
def latest_attempt(qdir, test_id):
    d = os.path.join(qdir, "tests", test_id)
    tries = sorted((int(m.group(1)), n) for n in (os.listdir(d) if os.path.isdir(d) else [])
                   for m in [re.fullmatch(r"a(\d+)", n)] if m)
    return os.path.join(d, tries[-1][1]) if tries else None


def judge_test(events, obs, exp, tol=TOL_M):
    """(verdict, why, last position event) of one leg from its bridge events and obs.json."""
    act = (obs or {}).get("activate")
    if isinstance(act, dict) and act.get("selected") is False:
        return "INCONCLUSIVE", "NOT_ACTIVATED: the runner's GetIsID proof failed, nothing was activated", None
    for e in events:
        if e.get("kind") == "resolve" and e.get("plugin", "").casefold() == exp["resolve"]["plugin"].casefold() \
                and e.get("id") == exp["resolve"]["id"] and e.get("form"):
            if e["form"][:2] != exp["resolve"]["index"]:
                return "INCONCLUSIVE", (f"INDEX: {exp['resolve']['plugin']} loads at {e['form'][:2]}, planned "
                                        f"{exp['resolve']['index']}: re-plan"), None
    at = next((i for i, e in enumerate(events) if e.get("kind") == "ack" and e.get("tag") == exp["ack"]), None)
    if at is None:
        return "INCONCLUSIVE", f"NO_ACK: no 'FO4SF ack {exp['ack']}' (console or bridge failed)", None
    pos = [e for e in events[at + 1:] if e.get("kind") == "pos" and e.get("pos")]
    if not pos:
        return "INCONCLUSIVE", "NO_POSITION: no bridge position line after the ack", None
    last = pos[-1]
    dxy = math.dist(last["pos"][:2], exp["pos"][:2])
    dz = abs(last["pos"][2] - exp["pos"][2])
    if exp["cell"] and last.get("cell") != exp["cell"]:
        where = "STAYED" if last.get("world") else "WRONG_PLACE"
        return "FAIL", f"{where}: cell {last.get('cell')}, want {exp['cell']} ({dxy:.1f} m off)", last
    if exp["world"] and not last.get("world"):
        return "FAIL", f"STAYED: still in an interior (cell {last.get('cell')})", last
    if dxy > tol or dz > tol:
        return "FAIL", f"WRONG_PLACE: {dxy:.1f} m off in xy, {dz:.1f} m in z (tolerance {tol} m)", last
    return "PASS", f"{dxy:.2f} m off in xy, {dz:.2f} m in z", last


def judge(a):
    qdir = os.path.abspath(a.queue)
    q = load(os.path.join(qdir, "queue.json"))
    info = load(a.rounds or os.path.join(q["experiment"], "rounds.json"))
    tests, rows = q["tests"], []
    for exp in info["tests"]:
        t = tests[exp["test"]] if exp["test"] < len(tests) else None
        if t is None or not t["id"].startswith(f"{exp['test']:04d}_"):
            rows.append(dict(exp, verdict="INCONCLUSIVE", why="the queue has no such test (planned from another plan.json?)"))
            continue
        d = latest_attempt(qdir, t["id"])
        if d is None:
            rows.append(dict(exp, id=t["id"], verdict="NOT_RUN", why="no attempt folder"))
            continue
        obs = load(os.path.join(d, "obs.json")) if os.path.exists(os.path.join(d, "obs.json")) else {}
        verdict, why, last = judge_test(bridge_log.read_events(os.path.join(d, "bridge.log")), obs, exp, info["tol_m"])
        rows.append(dict(exp, id=t["id"], attempt=os.path.basename(d), verdict=verdict, why=why,
                         got=last and {k: last.get(k) for k in ("pos", "cell", "world")}))
    save(os.path.join(qdir, "door_rounds_judge.json"), {"rounds": a.rounds or q["experiment"], "results": rows})
    for r in rows:
        print(f"{r['test']:04d} {r['leg']:3s} {r['cell_edid']:32s} {r['verdict']:12s} {r['why']}")
    n = {v: sum(1 for r in rows if r["verdict"] == v) for v in ("PASS", "FAIL", "INCONCLUSIVE", "NOT_RUN")}
    print(", ".join(f"{v} {c}" for v, c in n.items()) + f"; {os.path.join(qdir, 'door_rounds_judge.json')}")
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("order")
    o.add_argument("--plugins-txt", required=True)
    o.add_argument("--first-index", default="02", help="the index of the first Plugins.txt plugin (hex)")
    s = sub.add_parser("stage")
    s.add_argument("--core", required=True, help="the core build (objects.json, formids.json, plan.json, overlays_params.json)")
    s.add_argument("--core-plugin", default="", help="the installed FO4TerrainCore.esm (default: the one in --core)")
    s.add_argument("--port", required=True, help="the installed FO4Port build's staging (FO4Port.esm)")
    s.add_argument("--core-index", required=True, help="the core's load index in the runner's launch (hex; see order)")
    s.add_argument("--port-index", required=True, help="FO4Port.esm's load index in the runner's launch (hex)")
    s.add_argument("--out", required=True, help="a NEW folder")
    s.add_argument("--only", default="", help="only these doors: interior cell editor ids or FO4 door srcs, comma-separated")
    s.add_argument("--limit", type=int, default=0)
    j = sub.add_parser("judge")
    j.add_argument("--queue", required=True)
    j.add_argument("--rounds", default="", help="rounds.json (default: the queue's experiment folder)")
    a = ap.parse_args(argv)
    {"order": cmd_order, "stage": stage, "judge": judge}[a.cmd](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
