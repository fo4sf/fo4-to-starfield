"""Inventory planner: the tiered test queues for a port staging (research/next-phase/testing-automation.md 2.1 and
2.2, task T-inventory). Tier 1 is a smoke test per cell, tier 2 the interaction tests, planned only for the cells that
passed tier 1, so a broken cell never costs a night of interaction tests.

  plan     --staging <port staging> --out <dir> [--cells A,B | --batch interior-batches.json --batch-number N]
           [--smoke-per-cell 1] [--plugin-index 02] [--bridge <staged bridge>]
           writes <dir>/inventory.json (the build's hashes and every cell's state, with the reason when a cell has no
           smoke test) and <dir>/tier1/queue.json (testqueue.py plan --kinds fall: coc into the cell, drop onto a
           floor point, read the landing).
  promote  --inventory <dir> [--kinds stairs,door,movable,travel] [--per-cell 12]
           reads tier 1's results, refuses when the staging's FO4Port.esm or any other staged file changed since the
           plan (plan pins every file's sha256 in staging_files.json, the probe_*.txt floor points aside), and writes <dir>/promotion.json (each cell promoted or held, with why) and
           <dir>/tier2/queue.json for the promoted cells.

Both commands only read the staging and write under --out; probe_points.py may add probe_<cell>_<n>.txt files to the
staging, as testqueue.py plan does. Nothing here launches the game; the queues run with testqueue.py run and its caps.
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import testqueue as tq  # noqa: E402

TIER2_KINDS = ("stairs", "door", "movable", "travel")
SKIP = {"editorids.json", "formids.json", "lighting.json", "merged.json", "manifest.json"}


def staged_cells(staging):
    """The cell names testqueue.py plan would plan in this staging (the same file rule)."""
    out = []
    for name in sorted(os.listdir(staging)):
        if not name.endswith(".json") or name in SKIP or name.startswith(("routes", "build")):
            continue
        c = tq.load(os.path.join(staging, name))
        if isinstance(c, dict) and "refs" in c and c.get("cell") and c["cell"] != "merged":
            out.append(c["cell"])
    return out


def wanted_cells(a):
    """The cells to inventory, in order, without duplicates: --cells, one batch of interior-batches.json, or every
    staged cell."""
    if a.cells and a.batch:
        sys.exit("give --cells or --batch, not both")
    if a.batch:
        d = tq.load(a.batch)
        rows = [b for b in (d or {}).get("batches", []) if b.get("batch") == a.batch_number]
        if a.batch_number is None or len(rows) != 1:
            sys.exit(f"{a.batch}: --batch-number must name one of its batches")
        names = [c.get("editor_id") if isinstance(c, dict) else c for c in rows[0].get("cells", [])]
    elif a.cells:
        names = [c.strip() for c in a.cells.split(",")]
    else:
        names = None
    if names is None:
        return None
    out = []
    for n in names:
        if not isinstance(n, str) or not n.replace("_", "").isalnum():
            sys.exit(f"bad cell name {n!r}")
        if n not in out:
            out.append(n)
    if not out:
        sys.exit("no cell named")
    return out


fingerprint = tq.staging_fingerprint                     # every staged file's sha256 (the probe points aside)


def pin_staging(qdir, files, skip, cells=None):
    """Write the staging fingerprint into the planned queue, so testqueue.py run refuses a staging changed after the
    plan, not only a changed FO4Port.esm (Runner.staging_mismatch; Codex on #405). With `cells` (the promoted ones), a
    travel test into a cell outside them is dropped: both ends of a trip must have passed smoke (Codex on #405).
    Returns how many tests were dropped."""
    p = os.path.join(qdir, "queue.json")
    q = tq.load(p)
    dropped = 0
    if cells is not None:
        keep = [t for t in q["tests"] if t["kind"] != "travel" or t.get("dest_cell") in cells]
        dropped = len(q["tests"]) - len(keep)
        q["tests"] = keep
    q["staging_files"], q["staging_skip"] = files, [os.path.abspath(x) for x in skip]
    tq.save_atomic(p, q)
    return dropped


def digest(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def run_plan(args):
    """testqueue.py plan with these arguments, its summary line returned instead of printed."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        tq.main(["plan", *args])
    return buf.getvalue().strip()


def plan(a):
    staging = os.path.abspath(a.staging)
    esm = os.path.join(staging, "FO4Port.esm")
    if not os.path.exists(esm):
        sys.exit(f"no FO4Port.esm in {staging}")
    if a.smoke_per_cell < 1:
        sys.exit("--smoke-per-cell must be at least 1")
    out = os.path.abspath(a.out)
    if os.path.exists(out):
        sys.exit(f"{out} exists: an inventory is planned into a new folder")
    staged = staged_cells(staging)
    want = wanted_cells(a)
    cells = want if want is not None else staged
    present = [c for c in cells if c in staged]
    rows = {c: {"cell": c, "state": "not_in_staging", "why": "no exported cell json in the staging"}
            for c in cells if c not in staged}
    if not present:
        sys.exit("none of the cells is in the staging: " + ", ".join(cells))
    extra = ["--bridge", a.bridge] if a.bridge else []
    files = fingerprint(staging, [out])
    os.makedirs(out)
    t1 = os.path.join(out, "tier1")
    try:
        summary = run_plan(["--staging", staging, "--out", t1, "--kinds", "fall", "--per-cell", str(a.smoke_per_cell),
                            "--cells", ",".join(present), "--plugin-index", a.plugin_index, *extra])
        pin_staging(t1, files, [out])
    except BaseException:                                 # a refused plan (a missing --bridge, ...) leaves nothing
        shutil.rmtree(out, ignore_errors=True)
        raise
    q = tq.load(os.path.join(t1, "queue.json"))
    by_cell = {}
    for t in q["tests"]:
        by_cell.setdefault(t["cell"], []).append(t["id"])
    for c in present:
        rows[c] = ({"cell": c, "state": "smoke", "tests": by_cell[c]} if c in by_cell else
                   {"cell": c, "state": "no_point", "why": "probe_points.py found no floor point to drop onto"})
    if not q["tests"]:
        shutil.rmtree(out)
        sys.exit("no smoke test could be planned: every cell is no_point or not_in_staging")
    tq.save_atomic(os.path.join(out, "staging_files.json"), files)
    inv = {"created": tq.now(), "staging": staging, "plugin_sha256": q["plugin_sha256"], "build_id": q["build_id"],
           "staging_files": len(files), "staging_digest": digest(files),
           "plugin_index": a.plugin_index, "bridge": os.path.abspath(a.bridge) if a.bridge else "",
           "source": ({"batch": os.path.abspath(a.batch), "batch_number": a.batch_number} if a.batch else
                      {"cells": a.cells} if a.cells else {"all": True}),
           "cells": [rows[c] for c in cells], "counts": counts(rows[c]["state"] for c in cells)}
    tq.save_atomic(os.path.join(out, "inventory.json"), inv)
    print(f"tier 1: {summary}; cells {inv['counts']}")


def counts(states):
    out = {}
    for s in states:
        out[s] = out.get(s, 0) + 1
    return out


def final_rows(qdir):
    """The last results.jsonl row of every test (a torn line is not a row)."""
    final = {}
    p = os.path.join(qdir, "results.jsonl")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and r.get("id"):
                    final[r["id"]] = r
    return final


def cell_verdict(ids, final):
    """promoted when every smoke test of the cell has a final PASS; else held with the first reason."""
    for i in ids:
        r = final.get(i)
        if r is None:
            return "held", f"{i} not run"
        if r.get("verdict") != "PASS":
            return "held", f"{i} {r.get('verdict')} {r.get('class', '')}: {r.get('detail', '')}".rstrip(": ")
    return "promoted", f"{len(ids)} smoke test(s) passed"


def promote(a):
    d = os.path.abspath(a.inventory)
    inv = tq.load(os.path.join(d, "inventory.json"))
    if not inv:
        sys.exit(f"no inventory.json in {d}")
    t2 = os.path.join(d, "tier2")
    if os.path.exists(t2):
        sys.exit(f"{t2} exists: tier 2 was already planned")
    kinds = [k.strip() for k in a.kinds.split(",") if k.strip()]
    bad = [k for k in kinds if k not in TIER2_KINDS]
    if bad or not kinds:
        sys.exit(f"tier 2 kinds are {TIER2_KINDS}: {a.kinds!r}")
    esm = os.path.join(inv["staging"], "FO4Port.esm")
    if not os.path.exists(esm) or tq.sha256(esm) != inv["plugin_sha256"]:
        sys.exit(f"{esm} is not the build the inventory planned ({inv['build_id']}): plan the inventory again")
    pinned = tq.load(os.path.join(d, "staging_files.json"))
    if not isinstance(pinned, dict) or digest(pinned) != inv.get("staging_digest"):
        sys.exit(f"{d}: staging_files.json missing or not the one inventory.json pinned: plan the inventory again")
    now_files = fingerprint(inv["staging"], [d])
    if now_files != pinned:
        moved = sorted(k for k in set(pinned) | set(now_files) if pinned.get(k) != now_files.get(k))
        sys.exit(f"the staging changed since the smoke tier was planned ({len(moved)} file(s): "
                 f"{', '.join(moved[:5])}{', ...' if len(moved) > 5 else ''}): plan the inventory again")
    final = final_rows(os.path.join(d, "tier1"))
    rows = []
    for c in inv["cells"]:
        if c["state"] != "smoke":
            rows.append({"cell": c["cell"], "state": "held", "why": c["state"] + ": " + c.get("why", "")})
            continue
        state, why = cell_verdict(c["tests"], final)
        rows.append({"cell": c["cell"], "state": state, "why": why})
    up = [r["cell"] for r in rows if r["state"] == "promoted"]
    res = {"created": tq.now(), "build_id": inv["build_id"], "kinds": kinds, "cells": rows,
           "counts": counts(r["state"] for r in rows)}
    tq.save_atomic(os.path.join(d, "promotion.json"), res)
    if not up:
        sys.exit(f"no cell passed tier 1 ({res['counts']}): promotion.json written, no tier 2 queue")
    extra = ["--bridge", inv["bridge"]] if inv.get("bridge") else []
    try:
        summary = run_plan(["--staging", inv["staging"], "--out", t2, "--kinds", ",".join(kinds), "--per-cell",
                            str(a.per_cell), "--cells", ",".join(up), "--plugin-index", inv["plugin_index"], *extra])
        dropped = pin_staging(t2, pinned, [d], set(up))
    except BaseException:                                 # a refused plan leaves no tier2/ to block the next promote
        shutil.rmtree(t2, ignore_errors=True)
        raise
    print(f"tier 2: {summary}; {dropped} travel test(s) into a held cell dropped; cells {res['counts']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--staging", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--cells", default="", help="comma-separated cell names (default: every staged cell)")
    p.add_argument("--batch", default="", help="interior-batches.json (#396): the cells of --batch-number")
    p.add_argument("--batch-number", type=int, default=None)
    p.add_argument("--smoke-per-cell", type=int, default=1, help="floor points dropped onto per cell (default 1)")
    p.add_argument("--plugin-index", default="02")
    p.add_argument("--bridge", default="", help="staged bridge folder (testqueue.py plan --bridge)")
    r = sub.add_parser("promote")
    r.add_argument("--inventory", required=True, help="the folder inventory.py plan wrote")
    r.add_argument("--kinds", default=",".join(TIER2_KINDS))
    r.add_argument("--per-cell", type=int, default=12)
    a = ap.parse_args(argv)
    return plan(a) if a.cmd == "plan" else promote(a)


if __name__ == "__main__":
    main()
