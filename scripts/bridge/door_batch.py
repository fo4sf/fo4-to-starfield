"""Door round trips for one batch of converted interiors (docs/testing/interior-batches.md): the cells a conversion
batch delivers, checked against the installed plugins with door_rounds.py, a coverage line per cell, and queue-sized
chunks ready for testqueue.py plan-terrain.

usage:
  python scripts/bridge/door_batch.py stage --batch <batch.json | batch.txt> --core <core build dir>
         --port <installed FO4Port staging> --core-index HH --port-index HH --out <NEW folder>
         [--core-plugin <installed FO4TerrainCore.esm>] [--legs both|out] [--min-out-m M] [--chunk N]
      batch.json: {"name": "...", "cells": ["FO4Port_Vault81Main", ...]}; batch.txt: one cell per line (# comments).
      A cell may be named with or without the FO4Port_ prefix. Every cell gets one coverage state:
        doors          its scripted load doors passed every check and are planned
        too_near       its doors passed every check, but --legs out dropped each one as nearer than --min-out-m
        doors_skipped  the build has doors into it, but each failed a check (the reasons are listed)
        not_wired      in the port, and the interiors plan gives it Commonwealth doors, but none is in the installed
                       core yet (that needs a core whose door cluster was made against this port)
        coc_only       in the port, and the interiors plan gives it no Commonwealth door (city interiors, cells
                       behind other interiors): door_rounds can not test it
        no_door        in the port, no build door leads into it (a batch without the interiors plan)
        not_in_port    no cell of that editor id in the installed FO4Port.esm (not converted, or another name)
      --batch <interior-door-rounds.json> --batch-number N reads one batch of the interiors thread's plan
      (docs/terrain/data/interior-door-rounds.json). --allow-empty writes coverage.json and README.txt even when no
      door can be planned yet, as a readiness report.
      --legs out keeps only the OUT legs (each starts with a coc inside, never at the Red Rocket arrival) of doors whose
      exterior arrival is at least --min-out-m from the Red Rocket arrival (door_out_legs.select, the same checks).
      --legs both plans IN and OUT; every IN leg starts at the Red Rocket arrival (door_rounds.SPAWN_COC).
      --chunk N splits the tests into folders chunk_00, chunk_01, ... of at most N tests (a door's two legs stay in
      one chunk), each with plan.json and rounds.json that plan-terrain and door_rounds.py judge read as they are.
      Writes coverage.json and README.txt with the plan, run and judge commands. Refuses an existing --out, and writes
      nothing when no cell of the batch has a planned door (unless --allow-empty).
Nothing here touches the game or its install.
"""
import argparse
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import door_rounds as dr  # noqa: E402
import door_out_legs  # noqa: E402

PREFIX = "FO4Port_"
CHUNK = 20                       # tests per queue: about one session (docs/ai/optimization.md: ~3 min a launch)
MIN_OUT_M = 1500.0               # the doors_out campaign of 2026-10-19 kept the OUT legs this far from Red Rocket
# the run caps the coordinator set for every unattended queue (2026-10-19): one launch, stop at the first crash,
# 40 GB kept free on the dump drive; 43 = one 18 GB dump plus 25 GB, as for doors_out
RUN_CAPS = "--max-attempts 1 --max-relaunch 1 --crash-budget 1 --min-free-gb 43 --dump-drive D:\\ --wait-for-idle"


def key(name):
    """A cell name compared without case and without the FO4Port_ prefix."""
    n = name.strip()
    return (n[len(PREFIX):] if n.casefold().startswith(PREFIX.casefold()) else n).casefold()


def read_batch(path, number=None):
    """(name, [cells], {key: plan entry}) from batch.json, a text file of one cell per line, or the interiors thread's
    data/interior-door-rounds.json with --batch-number (its plan entry per cell says which cells have Commonwealth
    doors and which only coc reaches); exits on a bad name or an empty batch."""
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    plan = {}
    if path.lower().endswith(".json"):
        b = json.loads(text)
        if isinstance(b, dict) and isinstance(b.get("batches"), list):
            if number is None:
                sys.exit(f"{path} holds several batches: give --batch-number")
            b = next((x for x in b["batches"] if x.get("batch") == number), None)
            if b is None:
                sys.exit(f"{path}: no batch {number}")
            entries = b.get("cells")
            if not isinstance(entries, list) or not all(isinstance(e, dict) and isinstance(e.get("cell"), str)
                                                       for e in entries):
                sys.exit(f"{path}: batch {number}'s cells must be objects with a cell editor id")
            plan = {key(e["cell"]): e for e in entries}
            b = {"name": b.get("name") or f"batch{number}", "cells": [e["cell"] for e in entries]}
        elif number is not None:
            sys.exit(f"{path} is one batch: drop --batch-number")
        name, cells = str(b.get("name") or os.path.splitext(os.path.basename(path))[0]), b.get("cells")
        if not isinstance(cells, list) or not all(isinstance(c, str) for c in cells):
            sys.exit(f"{path}: cells must be a list of cell editor ids")
    else:
        if number is not None:
            sys.exit(f"{path} is one batch: drop --batch-number")
        name = os.path.splitext(os.path.basename(path))[0]
        cells = [ln.split("#", 1)[0].strip() for ln in text.splitlines()]
    cells = [c.strip() for c in cells if c.strip()]
    bad = [c for c in cells if not re.fullmatch(r"[A-Za-z0-9_]+", c)]
    if bad:
        sys.exit(f"{path}: not cell editor ids: {bad}")
    if not cells:
        sys.exit(f"{path}: no cells")
    seen, out = set(), []
    for c in cells:
        if key(c) not in seen:
            seen.add(key(c))
            out.append(c)
    return name, out, plan


def port_cells(port):
    """{key: editor id} of every CELL of the installed port."""
    return {key(e): e for local, r in port.recs.items() if r[0] == "CELL" for e in [port.edid(local)] if e}


def coverage(cells, rounds, skipped, in_port, plan=None):
    """One row per batch cell, in batch order. With the interiors thread's plan, a cell in the port without a planned
    door is not_wired when the plan gives it Commonwealth doors (its exterior doors are not in the installed core yet:
    they need a core whose door cluster was made against this port) and coc_only when it has none."""
    rows, plan = [], plan or {}
    # a skipped door whose destination marker is missing from the port has no cell_edid: the plan's
    # commonwealth_doors[].src says whose it is (Codex on #397), so the failure stays on its cell
    owner = {str(d.get("src")).casefold(): pk for pk, e in plan.items()
             for d in (e.get("commonwealth_doors") or []) if isinstance(d, dict) and d.get("src") is not None}

    def cell_of(s):
        return key(s["cell_edid"]) if s.get("cell_edid") else owner.get(str(s.get("src")).casefold())
    for c in cells:
        k = key(c)
        mine = [r for r in rounds if key(r["cell_edid"]) == k]
        why = [s for s in skipped if cell_of(s) == k]
        if mine:
            rows.append({"cell": c, "state": "doors", "doors": [r["src"] for r in mine],
                         "skipped": [{"src": s["src"], "why": s["why"]} for s in why]})
        elif why:
            rows.append({"cell": c, "state": "doors_skipped", "doors": [],
                         "skipped": [{"src": s["src"], "why": s["why"]} for s in why]})
        elif k in in_port:
            state = "no_door"
            if k in plan:
                state = "not_wired" if plan[k].get("commonwealth_doors") else "coc_only"
            rows.append({"cell": in_port[k], "state": state, "doors": [], "skipped": []})
        else:
            rows.append({"cell": c, "state": "not_in_port", "doors": [], "skipped": []})
    return rows


STATES = ("doors", "too_near", "doors_skipped", "not_wired", "coc_only", "no_door", "not_in_port")


def mark_planned(rows, mine, groups):
    """A doors row keeps only the doors that got a test; a row whose every door was dropped (--legs out under
    --min-out-m) becomes too_near, its doors listed under "near" (the review pass on #397: "doors" means planned)."""
    planned = {mine[k]["src"] for k, _ in groups}
    for r in rows:
        if r["state"] != "doors":
            continue
        near = [d for d in r["doors"] if d not in planned]
        r["doors"] = [d for d in r["doors"] if d in planned]
        if near:
            r["near"] = near
        if not r["doors"]:
            r["state"] = "too_near"
    return rows


def legs(plan, info, which, min_m):
    """[(door, [(plan entry, expectation), ...])] in door order: both legs, or the OUT legs door_out_legs keeps."""
    if which == "both":
        return [(k, [(plan[2 * k], info["tests"][2 * k]), (plan[2 * k + 1], info["tests"][2 * k + 1])])
                for k in range(len(info["doors"]))]
    kept = door_out_legs.select(plan, info, min_m)          # every OUT leg rebuilt and compared before it is kept
    return [(e["door"], [(p, e)]) for p, e, _ in kept]


def chunks(groups, size):
    """Groups of tests packed in order into chunks of at most size tests; a door's legs are never split."""
    out, cur = [], []
    for _, tests in groups:
        if cur and len(cur) + len(tests) > size:
            out.append(cur)
            cur = []
        cur += tests
    if cur:
        out.append(cur)
    return out


def stage(a):
    out = os.path.abspath(a.out)
    if os.path.exists(out):
        sys.exit(f"{out} exists: the stage writes a new folder only")
    if a.chunk < 2 or not (math.isfinite(a.min_out_m) and a.min_out_m >= 0):
        sys.exit("--chunk needs 2 or more tests and --min-out-m a finite distance of 0 or more")
    name, cells, plan_cells = read_batch(a.batch, a.batch_number)
    rounds, skipped, merge, core, port, first = dr.collect(os.path.abspath(a.core), a.core_plugin, a.port)
    want = {key(c) for c in cells}
    mine = [r for r in rounds if key(r["cell_edid"]) in want]
    rows = coverage(cells, mine, skipped, port_cells(port), plan_cells)
    ci, pi = int(a.core_index, 16), int(a.port_index, 16)
    groups = []
    if mine:
        plan, expect = dr.plan_rounds(mine, first, ci, pi)
        info = {"core_index": f"{ci:02X}", "port_index": f"{pi:02X}", "doors": mine, "tests": expect}
        groups = legs(plan, info, a.legs, a.min_out_m)
    rows = mark_planned(rows, mine, groups)
    if not groups and not a.allow_empty:
        sys.exit(f"batch {name}: no door to plan; " + "; ".join(f"{r['cell']} {r['state']}" for r in rows))
    parts = chunks(groups, a.chunk) if groups else []
    base = {"core": os.path.abspath(a.core), "core_plugin": core.path, "port_plugin": port.path,
            "core_index": f"{ci:02X}", "port_index": f"{pi:02X}", "merge": list(merge), "tol_m": dr.TOL_M,
            "doors": mine, "skipped": skipped}
    os.makedirs(out)
    folders = []
    for n, tests in enumerate(parts):
        d = os.path.join(out, f"chunk_{n:02d}")
        os.makedirs(d)
        # #401: rounds.json carries the plan's digest, which plan-terrain checks before it queues the chunk
        dr.save_stage(d, [p for p, _ in tests], dict(base, batch=name, chunk=n,
                                                      tests=[dict(e, test=i) for i, (_, e) in enumerate(tests)]))
        folders.append({"folder": d, "tests": len(tests)})
    cov = {"batch": name, "legs": a.legs, "min_out_m": a.min_out_m if a.legs == "out" else None,
           "cells": rows, "chunks": folders,
           "counts": {s: sum(1 for r in rows if r["state"] == s) for s in STATES}}
    dr.save(os.path.join(out, "coverage.json"), cov)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(readme(cov, a))
    print(f"batch {name}: {len(cells)} cells, " + ", ".join(f"{s} {c}" for s, c in cov["counts"].items())
          + f"; {sum(c['tests'] for c in folders)} tests in {len(folders)} chunks under {out}")
    for r in rows:
        print(f"  {r['cell']:36s} {r['state']:14s} {len(r['doors'])} doors"
              + "".join(f"\n      skipped {s['src']}: {s['why']}" for s in r["skipped"]))


def readme(cov, a):
    q = os.path.join(r"D:\Modding", f"testqueue_batch_{cov['batch']}")
    lines = [f"Door round trips for interior batch {cov['batch']} (scripts/bridge/door_batch.py), legs: {cov['legs']}.",
             "Coverage: " + ", ".join(f"{s} {c}" for s, c in cov["counts"].items()) + " (coverage.json).", "",
             "Per chunk, with the installed set left as it is (no --plugins):",
             "  python scripts\\game\\testqueue.py plan-terrain --staging <the installed FO4Port staging> "
             "--exp-dir <chunk> --out <queue> --bridge <the installed bridge staging>"]
    if cov["legs"] == "both":
        # Codex on #397: a direct testqueue.py run bypasses the campaign's holds, and every IN leg starts at Red Rocket
        lines += [f"Every IN leg starts at {dr.SPAWN_COC}: run these queues only through a campaign "
                  "(scripts\\game\\campaign_arm.py), whose red_rocket hold refuses them until the owner releases it.",
                  "  Each queue entry: its folder, with judge [\"scripts/bridge/door_rounds.py\", \"judge\", \"--queue\", <queue>]."]
    else:
        lines += [f"  python scripts\\game\\testqueue.py run --queue <queue> {RUN_CAPS}",
                  "  python scripts\\bridge\\door_rounds.py judge --queue <queue>",
                  "Stop the batch at the first queue whose run does not end with exit 0 or whose status shows a crash."]
    lines += [f"Queue folders suggested: {q}\\chunk_NN.", ""]
    for c in cov["chunks"]:
        lines.append(f"  {c['folder']}: {c['tests']} tests")
    lines.append("")
    for r in cov["cells"]:
        lines.append(f"  {r['cell']:36s} {r['state']}")
        lines += [f"      skipped {s['src']}: {s['why']}" for s in r["skipped"]]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage")
    s.add_argument("--batch", required=True)
    s.add_argument("--batch-number", type=int, default=None,
                   help="the batch of a multi-batch file (data/interior-door-rounds.json)")
    s.add_argument("--core", required=True)
    s.add_argument("--core-plugin", default="")
    s.add_argument("--port", required=True)
    s.add_argument("--core-index", required=True)
    s.add_argument("--port-index", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--legs", choices=("both", "out"), default="out")
    s.add_argument("--min-out-m", type=float, default=MIN_OUT_M)
    s.add_argument("--chunk", type=int, default=CHUNK)
    s.add_argument("--allow-empty", action="store_true",
                   help="write coverage.json even when no door can be planned yet (a readiness report)")
    a = ap.parse_args(argv)
    stage(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
