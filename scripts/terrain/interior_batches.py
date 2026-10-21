"""interior_batches.py: the plan that converts every reachable Fallout 4 interior into FO4Port.esm in staged batches
(docs/terrain/interior-batches.md).

  python scripts/terrain/interior_batches.py --census <census.json> --backlog docs/terrain/data/interior-backlog.json
         --out <batches.json> [--md <batches.md>] [--min-cells 20] [--max-cells 30] [--max-refs 60000]
         [--near-m 1000] [--free-gb <D: free now>] [--floor-gb 40]

Reads interior_census.py's census (every interior cell, how it is reached, whether the port has it) and
interior_backlog.py's measures (models, distance to Red Rocket / Sanctuary, rank), and puts every interior a load door
reaches (`reach` worldspace or behind_interior) that the port does not hold yet into batches, in this order:
  0. completes_port  the cells behind an interior the port already holds (Parsons, Vault 114, Prydwen, Kellogg's
            memory): small, and they finish complexes the owner can already enter;
  1. near   the Commonwealth interiors whose nearest exterior door is within --near-m of Red Rocket or Sanctuary
            (a walkable Commonwealth grows from Red Rocket: the backlog doc's recommendation), nearest first;
  2. ranked the rest of the backlog in interior_backlog's rank;
  3. world  the interiors other worldspaces' doors lead into (Diamond City, Goodneighbor, Sanctuary Hills before the
            war): the census finds them, the backlog (Commonwealth doors only) does not; their exterior side is not
            built, so they are reached by coc until those worldspaces are;
and a cell reached only through other interiors right after the last cell it is reached from (never before it).
Left out and listed: Creation Club hook cells (`cc...` editor ids: their doors have no model in this Fallout4.esm, the
backlog doc's "no arrival" cells) and cells no load door reaches (the census's no_load_door / closed).
A batch closes at --max-cells cells, or at --max-refs references once it has --min-cells.

Per cell the plan keeps the census's `plugins`: every plugin that holds the cell, in load order (Fallout4.esm alone for
most; Fallout4.esm then DLCRobot.esm for a cell Automatron overrides; the DLC alone for its own cells). interior_batch.py
exports the cell from all of them, so a DLC's edits to a base-game cell are in the port; a plan written before this key
(batches 1 to 9) is read with the census (`build --census`) or, without one, by the formkey's owner plugin alone.

Estimates (labelled as such in the output): new models per batch = the backlog's `adds_models` (models no earlier
ranked cell brings) where measured, else the cell's distinct bases x the backlog's measured new fraction; archive
bytes per model from the installed port (integ_v6_specmask: FO4Port - Textures.ba2 2,156,974,881 B and - Main.ba2
113,096,481 B for about 4,100 converted models, read 2026-10-19 on the PC); the loose staging as twice the archives.
The build keeps the latest staged batch and one rollback, and grows one work staging (convert_batch --resume), so
the peak is about: work staging + 2 x the cumulative archives. With --free-gb the plan says which batch would cross
--floor-gb.
"""
import argparse
import json
import os
import re
import sys

PORT_MODELS = 4100                      # converted models in the installed port (supported: manifest bytes / 389 B)
TEX_BYTES = 2156974881                  # D:\Modding\staging\integ_v6_specmask_doors_c\FO4Port - Textures.ba2
MAIN_BYTES = 113096481                  # ... FO4Port - Main.ba2
LOOSE_FACTOR = 2.0                      # loose work staging / archives (a judgment, not measured)
CC_HOOK = re.compile(r"^cc[a-z]{3}fo4", re.I)


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def plan(census, backlog, min_cells=20, max_cells=30, max_refs=60000, near_m=1000.0):
    rows = census["cells"]
    by_key = {r["formkey"]: r for r in rows}
    by_eid = {r["editor_id"].casefold(): r for r in rows if r["editor_id"]}
    bl = {c["formkey"]: c for c in backlog.get("backlog", [])}
    sh = {c["formkey"]: c for c in backlog.get("second_hop", [])}
    measured = [c for c in list(bl.values()) + list(sh.values()) if c.get("distinct_models")]
    new_fraction = (sum(c.get("new_models", 0) for c in measured) / max(1, sum(c["distinct_models"] for c in measured)))
    dedupe = (backlog.get("totals", {}).get("backlog_new_models", 0)
              / max(1, backlog.get("totals", {}).get("backlog_new_models_per_cell_sum", 1))) or 1.0

    skipped, todo = [], []
    for r in rows:
        if r["status"] == "in_port":
            continue
        if r["reach"] not in ("worldspace", "behind_interior"):
            continue
        if CC_HOOK.search(r["editor_id"] or "") or (r["editor_id"] or "").upper() == "CTEST":
            skipped.append({"editor_id": r["editor_id"], "formkey": r["formkey"], "reason": "Creation Club hook or test "
                            "cell (its doors' bases have no model in this Fallout4.esm; interior-backlog.md)"})
            continue
        todo.append(r)

    def models(r):
        c = bl.get(r["formkey"]) or sh.get(r["formkey"])
        if c is not None and "adds_models" in c:
            return c["adds_models"], "measured"
        return round(r["distinct_bases"] * new_fraction * dedupe), "estimated"

    def phase(r):
        c = bl.get(r["formkey"])
        if c is not None:
            return (0, c["nearest_m"], 0) if c["nearest_m"] <= near_m else (1, c["rank"], 0)
        s = sh.get(r["formkey"])
        if s is not None and s.get("after_rank", 0) == 0:
            return (0, -1.0, 0)                               # behind an interior the port holds: completes it, first
        if s is not None:
            return (1, s["after_rank"], 1)                    # behind a ranked cell: placed after it below anyway
        if r["reach"] == "worldspace":
            return (2, 0, r["editor_id"].casefold())
        return (2, 1, r["editor_id"].casefold())

    order = sorted(todo, key=lambda r: (phase(r), r["editor_id"].casefold()))
    # A cell reached only through other interiors goes right after the last of its parents (the port already holding a
    # parent counts as placed). Parents are the census's entered_from editor ids.
    placed_eids = {r["editor_id"].casefold() for r in rows if r["status"] == "in_port"}
    pending = {r["formkey"] for r in order}
    seq, waiting = [], []
    for r in order:
        waiting.append(r)
        progress = True
        while progress:
            progress = False
            for w in list(waiting):
                parents = [p.casefold() for p in w["entered_from"]] if w["reach"] == "behind_interior" else []
                known = [p for p in parents if p in by_eid]
                if w["reach"] != "behind_interior" or any(p in placed_eids for p in known) or not any(
                        by_eid[p]["formkey"] in pending for p in known):
                    seq.append(w)
                    placed_eids.add(w["editor_id"].casefold())
                    pending.discard(w["formkey"])
                    waiting.remove(w)
                    progress = True
    seq += waiting                                            # unreachable parents: keep them, in order, at the end

    batches, cur = [], []
    def close():
        if cur:
            batches.append(list(cur))
            cur.clear()
    for r in seq:
        refs = sum(x["refs"] for x in cur)
        if cur and (len(cur) >= max_cells or (len(cur) >= min_cells and refs + r["refs"] > max_refs)):
            close()
        cur.append(r)
    close()

    out, cum_models = [], PORT_MODELS
    per_model = (TEX_BYTES + MAIN_BYTES) / PORT_MODELS
    for i, cells in enumerate(batches, 1):
        cell_rows = []
        for r in cells:
            n, how = models(r)
            c = bl.get(r["formkey"]) or sh.get(r["formkey"]) or {}
            cell_rows.append({"editor_id": r["editor_id"], "formkey": r["formkey"], "plugins": list(r.get("plugins") or []),
                              "phase": "completes_port" if phase(r)[1] == -1.0 else ("near", "ranked", "world")[phase(r)[0]],
                              "reach": r["reach"], "entered_from": r["entered_from"], "refs": r["refs"],
                              "lights": r["lights"], "navmeshes": r["navmeshes"], "load_doors_out": len(r["load_doors_out"]),
                              "doors_to_world": sorted({d["to"] for d in r["load_doors_out"] if (d["to"] or "").startswith("world:")}),
                              "doors_to_interiors": sorted({d["to"] for d in r["load_doors_out"] if d["to"] and not d["to"].startswith("world:")}),
                              "backlog_rank": c.get("rank"), "nearest_m": c.get("nearest_m"), "enterable": c.get("enterable"),
                              "effort": (c.get("effort") or {}).get("class"), "new_models": n, "new_models_kind": how})
        new = sum(x["new_models"] for x in cell_rows)
        cum_models += new
        archives = cum_models * per_model
        out.append({"batch": i, "name": f"interiors_b{i:02d}", "cells": cell_rows, "cell_count": len(cells),
                    "refs": sum(x["refs"] for x in cell_rows), "new_models_est": new, "cumulative_models_est": cum_models,
                    "archives_gb_est": round(archives / 1e9, 2),
                    "work_staging_gb_est": round(archives * LOOSE_FACTOR / 1e9, 2),
                    "peak_gb_est": round((archives * LOOSE_FACTOR + 2 * archives) / 1e9, 2)})
    return {"note": "scripts/terrain/interior_batches.py (docs/terrain/interior-batches.md); *_est are estimates",
            "params": {"min_cells": min_cells, "max_cells": max_cells, "max_refs": max_refs, "near_m": near_m,
                       "port_models": PORT_MODELS, "bytes_per_model": round(per_model), "loose_factor": LOOSE_FACTOR},
            "totals": {"batches": len(out), "cells": sum(b["cell_count"] for b in out), "refs": sum(b["refs"] for b in out),
                       "skipped": len(skipped), "final_archives_gb_est": out[-1]["archives_gb_est"] if out else 0,
                       "final_peak_gb_est": out[-1]["peak_gb_est"] if out else 0},
            "batches": out, "skipped": skipped}


def extend(existing, fresh, min_cells=20, max_cells=30, max_refs=60000):
    """Keep an earlier plan's batches exactly (built batches are pinned to it) and put only the cells it lacks (from
    a plan made over a larger census, e.g. with the DLC plugins) into new batches after its last one, in the fresh
    plan's order. The estimates continue from the earlier plan's cumulative model count."""
    have = {c["formkey"] for b in existing["batches"] for c in b["cells"]}
    fresh_keys = {c["formkey"] for b in fresh["batches"] for c in b["cells"]}
    lost = sorted(have - fresh_keys)
    if lost:
        raise ValueError(f"{len(lost)} cell(s) of the earlier plan are not in the new census's plan (first {lost[:3]})")
    todo = [c for b in fresh["batches"] for c in b["cells"] if c["formkey"] not in have]
    out = [dict(b) for b in existing["batches"]]
    per_model = fresh["params"]["bytes_per_model"]
    cum = out[-1]["cumulative_models_est"] if out else PORT_MODELS
    groups, cur = [], []
    for c in todo:
        refs = sum(x["refs"] for x in cur)
        if cur and (len(cur) >= max_cells or (len(cur) >= min_cells and refs + c["refs"] > max_refs)):
            groups.append(cur)
            cur = []
        cur.append(c)
    if cur:
        groups.append(cur)
    for cells in groups:
        i = len(out) + 1
        new = sum(x["new_models"] for x in cells)
        cum += new
        archives = cum * per_model
        out.append({"batch": i, "name": f"interiors_b{i:02d}", "cells": cells, "cell_count": len(cells),
                    "refs": sum(x["refs"] for x in cells), "new_models_est": new, "cumulative_models_est": cum,
                    "archives_gb_est": round(archives / 1e9, 2), "work_staging_gb_est": round(archives * LOOSE_FACTOR / 1e9, 2),
                    "peak_gb_est": round((archives * LOOSE_FACTOR + 2 * archives) / 1e9, 2)})
    result = dict(existing)
    result["batches"] = out
    result["totals"] = dict(existing["totals"], batches=len(out), cells=sum(b["cell_count"] for b in out),
                            refs=sum(b["refs"] for b in out), final_archives_gb_est=out[-1]["archives_gb_est"] if out else 0,
                            final_peak_gb_est=out[-1]["peak_gb_est"] if out else 0, extended_by=len(todo))
    return result


def disk_check(result, free_gb, floor_gb):
    """Mark the first batch whose peak estimate would leave less than floor_gb free (free_gb measured now, before any
    batch exists)."""
    for b in result["batches"]:
        b["free_after_gb_est"] = round(free_gb - b["peak_gb_est"], 1)
        b["under_floor"] = b["free_after_gb_est"] < floor_gb
    first = next((b["batch"] for b in result["batches"] if b["under_floor"]), None)
    result["totals"]["first_batch_under_floor"] = first
    return result


def markdown(result):
    lines = ["| Batch | Cells | Refs | New models (est) | Archives GB (est) | Peak GB (est) | Interiors |", "|---|---|---|---|---|---|---|"]
    for b in result["batches"]:
        names = ", ".join(c["editor_id"] for c in b["cells"])
        lines.append(f"| {b['batch']} | {b['cell_count']} | {b['refs']:,} | {b['new_models_est']:,} | {b['archives_gb_est']} | "
                     f"{b['peak_gb_est']} | {names} |")
    if result["skipped"]:
        lines += ["", "Left out: " + ", ".join(f"{s['editor_id']} ({s['reason']})" for s in result["skipped"])]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--census", required=True)
    ap.add_argument("--backlog", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--md", default="")
    ap.add_argument("--min-cells", type=int, default=20)
    ap.add_argument("--max-cells", type=int, default=30)
    ap.add_argument("--max-refs", type=int, default=60000)
    ap.add_argument("--near-m", type=float, default=1000.0)
    ap.add_argument("--free-gb", type=float, default=None)
    ap.add_argument("--after", default="", help="an earlier plan to keep as is; only the cells it lacks get new batches")
    ap.add_argument("--floor-gb", type=float, default=40.0)
    a = ap.parse_args(argv)
    if not 0 < a.min_cells <= a.max_cells:
        sys.exit("need 0 < --min-cells <= --max-cells")
    result = plan(load(a.census), load(a.backlog), a.min_cells, a.max_cells, a.max_refs, a.near_m)
    if a.after:
        result = extend(load(a.after), result, a.min_cells, a.max_cells, a.max_refs)
    if a.free_gb is not None:
        disk_check(result, a.free_gb, a.floor_gb)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as f:
            f.write(markdown(result))
    print(json.dumps(result["totals"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
