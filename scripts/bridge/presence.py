"""Where the installed NPCs and named references really are (docs/terrain/door-rounds.md, "Presence"): a readout the
runner takes with no one at the PC, for the NPC, mission and map threads. Report-only: it says where each reference
resolves, never that a mission works.

usage:
  python scripts/bridge/presence.py stage --plugin <installed FO4SFMission.esm> --index HH --core <core build dir>
         --out <NEW folder> [--extra <plugin>:<local hex>:<index hex>,...]
      every placed actor (ACHR) of --plugin, grouped by place (CLUSTER_M); one terrain test per group that hops from
      the Red Rocket arrival to the group and resolves each actor there (FO4SF_Probe.Resolve), plus, with --extra, one
      test at the arrival that resolves those references (the map markers, say). Writes plan.json, presence.json,
      README.txt. Refuses an existing --out.
  python scripts/game/testqueue.py plan-terrain --staging <installed FO4Port staging> --exp-dir <out> --out <queue>
         --bridge <installed bridge staging>
  python scripts/bridge/presence.py judge --queue <queue> [--presence <out>/presence.json]
      per reference, from its test's latest attempt after the test's ack: MISSING (no resolve line, or form=none),
      INDEX (another load index than planned: re-plan), DISABLED, then where it is. For an actor: NEAR_MERGED (within
      NEAR_M of its record position + the build's merge: where the drawn world puts it), AT_LOCAL (within NEAR_M of the
      record position itself: not moved into the drawn world), or ELSEWHERE with both distances; for an extra, its
      position. Also counts the papyrus.log lines that mention "moved" or "relocat" (the mission script's own lines).
Game data stays outside the repo; nothing here touches the game or its install.
"""
import argparse
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import door_rounds as dr  # noqa: E402

CLUSTER_M = 300.0                # actors closer than this to a group's first actor share its test
STAND_OFF_M = 4.0                # stand this far east of the group's first actor, not inside it
NEAR_M = 25.0
SCRIPT_LINE = re.compile(r"moved|relocat", re.I)


def actors(plug):
    """[(local, ref)] of every own placed actor (ACHR) with a position, in id order."""
    out = []
    for local in sorted(plug.recs):
        if plug.recs[local][0] == "ACHR":
            r = plug.ref(local)
            if r and dr.finite(r["pos"]):
                out.append((local, r))
    return out


def clusters(items, radius=CLUSTER_M):
    """Greedy groups by xy distance to each group's first member, in input order."""
    groups = []
    for local, r in items:
        for g in groups:
            if math.dist(g[0][1]["pos"][:2], r["pos"][:2]) <= radius:
                g.append((local, r))
                break
        else:
            groups.append([(local, r)])
    return groups


def parse_extra(s):
    out = []
    for item in [x.strip() for x in s.split(",") if x.strip()]:
        m = re.fullmatch(r"([^:]+\.es[mpl]):([0-9A-Fa-f]{1,6}):([0-9A-Fa-f]{2})", item)
        if not m:
            sys.exit(f"bad --extra {item!r}: want <plugin>:<local hex>:<index hex>")
        out.append({"plugin": m.group(1), "id": int(m.group(2), 16), "index": m.group(3).upper()})
    return out


def stage(a):
    out, core_dir = os.path.abspath(a.out), os.path.abspath(a.core)
    if os.path.exists(out):
        sys.exit(f"{out} exists: the stage writes a new folder only")
    plug = dr.Installed(os.path.abspath(a.plugin))
    merge = dr.vmad_patch.merge_offset(core_dir)
    first = dr.load(os.path.join(core_dir, "plan.json"))[0]
    if first.get("coc") != dr.SPAWN_COC or first["points"][0]["label"] != "zref_ground":
        sys.exit(f"{core_dir}: plan.json's first entry is not the {dr.SPAWN_COC} arrival with zref_ground first")
    spawn, zref = first["spawn_local"], {k: first["points"][0][k] for k in ("label", "x", "y", "expect")}
    drop = float(first.get("drop_z", 175.0))
    index = f"{int(a.index, 16):02X}"
    extra = parse_extra(a.extra)
    found = actors(plug)
    if not found and not extra:
        sys.exit(f"{plug.name} has no placed actors and no --extra was given")
    plan, tests = [], []
    if extra:
        tag = "presence-extra"
        plan.append({"coc": dr.SPAWN_COC, "travel": "", "spawn_local": list(spawn), "settle_ms": dr.SETTLE_MS,
                     "z_ref": "zref_ground", "drop_z": drop, "points": [dict(zref)],
                     "beyond": {"x": spawn[0], "y": spawn[1] + 120.0},
                     "console_post": [dr.ack(tag)] + [dr.resolve(e["plugin"], e["id"]) for e in extra],
                     "label": f"presence: at the Red Rocket arrival, resolve {len(extra)} named references"})
        tests.append({"test": 0, "ack": tag, "refs": [dict(e, kind="extra") for e in extra]})
    for g in clusters(found):
        k = len(plan)
        tag = f"presence-{k}"
        p = g[0][1]["pos"]
        stand = {"label": "group", "x": round(p[0] + STAND_OFF_M, 4), "y": round(p[1], 4), "expect": round(p[2], 4)}
        plan.append({"coc": dr.SPAWN_COC, "travel": "", "spawn_local": list(spawn), "settle_ms": dr.SETTLE_MS,
                     "z_ref": "zref_ground", "hop_m": dr.HOP_M, "hop_wait_ms": dr.HOP_WAIT_MS,
                     "drop_z": round(max(drop, p[2] + dr.STAND_ABOVE_M), 4), "points": [dict(zref), stand],
                     "beyond": {"x": stand["x"], "y": stand["y"] + 120.0},
                     "console_post": [dr.ack(tag)] + [dr.resolve(plug.name, local) for local, _ in g],
                     "label": f"presence: {len(g)} actors of {plug.name} near local ({p[0]:.0f}, {p[1]:.0f}), "
                              f"{math.dist(spawn[:2], p[:2]):.0f} m from the arrival"})
        tests.append({"test": k, "ack": tag, "refs": [
            {"plugin": plug.name, "id": local, "index": index, "kind": "actor", "edid": plug.edid(local),
             "base": f"{r['base_full']:08X}" if r["base_full"] is not None else None,
             "local": [round(v, 4) for v in r["pos"]],
             "merged": [round(v, 4) for v in dr.vmad_patch.merged(r["pos"], merge)]} for local, r in g]})
    os.makedirs(out)
    dr.save(os.path.join(out, "plan.json"), plan)
    info = {"plugin": plug.path, "index": index, "core": core_dir, "merge": list(merge), "near_m": NEAR_M, "tests": tests}
    dr.save(os.path.join(out, "presence.json"), info)
    lines = [f"Presence readout (scripts/bridge/presence.py): {len(found)} actors of {plug.path} (index {index}),"
             f" {len(extra)} extra references, {len(plan)} tests. Report-only."]
    for t in tests:
        for r in t["refs"]:
            lines.append(f"  test {t['test']:04d} {r['plugin']}:{r['id']:06X} {r.get('edid') or ''} {r['kind']}"
                         + (f" local {r['local']} merged {r['merged']}" if r["kind"] == "actor" else ""))
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


def read_ref(events, ref, near=NEAR_M):
    """{"state", "why", "resolve"} for one reference from the events after its test's ack."""
    hits = [e for e in events if e.get("kind") == "resolve" and e.get("id") == ref["id"]
            and str(e.get("plugin", "")).casefold() == ref["plugin"].casefold()]
    hit = hits[-1] if hits else None
    if hit is None or not hit.get("form"):
        return {"state": "MISSING", "why": "no resolve line" if hit is None else "form=none: no such form loaded"}
    got = {k: hit.get(k) for k in ("form", "pos", "cell", "world", "disabled", "loaded")}
    if hit["form"][:2] != ref["index"]:
        return {"state": "INDEX", "why": f"loads at {hit['form'][:2]}, planned {ref['index']}: re-plan", "resolve": got}
    want = f"{ref['index']}{ref['id']:06X}"
    if any(e.get("form") != want for e in hits):
        return {"state": "CONFLICT", "why": f"replies name {sorted({str(e.get('form')) for e in hits})}, planned {want}",
                "resolve": got}
    if hit.get("ref") is not True:
        return {"state": "NOT_A_REF", "why": "the form is not a placed reference", "resolve": got}
    if hit.get("disabled") is True:
        return {"state": "DISABLED", "why": f"disabled at {hit.get('pos')}", "resolve": got}
    pos = hit.get("pos")
    if ref["kind"] != "actor":
        return {"state": "PRESENT", "why": f"at {pos}, loaded={hit.get('loaded')}", "resolve": got}
    if not dr.finite(pos):
        return {"state": "NO_POSITION", "why": f"position {pos}", "resolve": got}
    dm, dl = math.dist(pos, ref["merged"]), math.dist(pos, ref["local"])
    state = "NEAR_MERGED" if dm <= near else "AT_LOCAL" if dl <= near else "ELSEWHERE"
    return {"state": state, "why": f"{dm:.1f} m from merged, {dl:.1f} m from local, loaded={hit.get('loaded')}",
            "resolve": got}


def judge(a):
    qdir = os.path.abspath(a.queue)
    q = dr.load(os.path.join(qdir, "queue.json"))
    info = dr.load(a.presence or os.path.join(q["experiment"], "presence.json"))
    rows = []
    for t in info["tests"]:
        test = q["tests"][t["test"]] if t["test"] < len(q["tests"]) else None
        if test is None or not test["id"].startswith(f"{t['test']:04d}_"):
            rows += [dict(r, test=t["test"], state="NOT_PLANNED", why="the queue has no such test") for r in t["refs"]]
            continue
        d = dr.latest_attempt(qdir, test["id"])
        if d is None:
            rows += [dict(r, test=t["test"], state="NOT_RUN", why="no attempt folder") for r in t["refs"]]
            continue
        events = dr.bridge_log.read_events(os.path.join(d, "bridge.log"))
        at = next((i for i, e in enumerate(events) if e.get("kind") == "ack" and e.get("tag") == t["ack"]), None)
        script = 0
        pl = os.path.join(d, "papyrus.log")
        if os.path.exists(pl):
            with open(pl, encoding="utf-8", errors="replace") as f:
                script = sum(1 for ln in f if SCRIPT_LINE.search(ln))
        for r in t["refs"]:
            got = ({"state": "NO_ACK", "why": f"no 'FO4SF ack {t['ack']}' (console or bridge failed)"} if at is None
                   else read_ref(events[at + 1:], r, info.get("near_m", NEAR_M)))
            rows.append(dict(r, test=t["test"], attempt=os.path.basename(d), papyrus_moved_lines=script, **got))
    dr.save(os.path.join(qdir, "presence_report.json"), {"presence": a.presence or q["experiment"], "results": rows})
    for r in rows:
        print(f"{r['test']:04d} {r['plugin']}:{r['id']:06X} {(r.get('edid') or ''):28s} {r['state']:12s} {r['why']}")
    print(f"{len(rows)} references; {os.path.join(qdir, 'presence_report.json')}")
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage")
    s.add_argument("--plugin", required=True, help="the installed plugin whose actors are read (FO4SFMission.esm)")
    s.add_argument("--index", required=True, help="its load index in the runner's launch (hex; door_rounds.py order)")
    s.add_argument("--core", required=True, help="the core build (plan.json, overlays_params.json, formids.json)")
    s.add_argument("--extra", default="", help="<plugin>:<local hex>:<index hex>,... resolved at the arrival")
    s.add_argument("--out", required=True)
    j = sub.add_parser("judge")
    j.add_argument("--queue", required=True)
    j.add_argument("--presence", default="")
    a = ap.parse_args(argv)
    (stage if a.cmd == "stage" else judge)(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
