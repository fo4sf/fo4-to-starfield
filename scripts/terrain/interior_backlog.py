"""interior_backlog.py: the interior conversion backlog of the Commonwealth core, ranked (docs/terrain/interior-backlog.md).

The core's exterior is converted (core64c..g: every Fallout4.esm exterior reference that converts); its load doors lead
into interiors, and only the interiors FO4Port.esm converts (integ_1011) are there to arrive in. This lists every FO4
interior an exterior load door of the core leads into, measures each from its own cell export, and ranks them.

  doors  --work <core64c work> --build <core64 staging> --out <doors.json> [--cells-txt <cells.txt>]
         Every exterior load door of the band exports (<work>/export/band_*.json, dotnet/Fo4Land export-exterior): a
         reference with a teleport destination. Its destination cell is the export's teleport_dependencies entry for it:
         the CELL record Fallout4.esm stores the destination door reference in (dotnet/Fo4Export/TeleportDependencies.cs
         walks every cell's temporary and persistent references). Whether the core build placed the door (objects.json
         refs by source key), and the two landmarks' FO4 positions (read from the bands, not typed in). --cells-txt
         writes the destination interiors' editor ids, one per line, for the exporter:
           dotnet dotnet/Fo4Export/bin/Release/net9.0/Fo4Export.dll <Fallout4.esm> export <EditorID> <dir>/<EditorID>.json
  plan   --doors <doors.json> --exports <dir> --manifest <integ manifest.json> --converted <integ staging>
         [--core-build <core64 staging>] [--fo4-data <FO4 Data>] [--dryrun <staging> ...] --json <out.json>
         [--md-table <out.md>] [--next-cells-txt <cells.txt>]
         Per destination interior, from its export (<dir>/<EditorID>.json): references, deferred placements (actors),
         lights, distinct models, the models convert_batch --cell-json would convert (convert_batch.cell_candidates, the
         same rule), how many of those integ_1011's manifest already converted (or failed), the load doors inside it that
         lead on to other interiors, with --fo4-data the candidates no FO4 mesh archive holds, an effort estimate; then
         the ranking and, in rank order, how many models each cell adds to the conversion (models are shared: a cell
         converted earlier makes later ones cheaper). --dryrun takes
         convert_batch stagings of exported cells (manifest.json: seconds, converted, failures) and puts the measured
         rate into the effort estimate.
         Second hop: the interiors no exterior door leads into but a load door of a measured interior does, followed
         until no new interior turns up (exports from the same <dir>), are measured the same way and listed apart
         ("second_hop", after the ranked backlog); --next-cells-txt writes the ones still without an export, to export
         and re-run.

Ranking (the request's keys, in order): more exterior doors into the cell first; then nearer to Red Rocket or Sanctuary,
by RING_M rings of the straight-line distance from the cell's nearest exterior door to the nearer landmark (whole metres
would leave the third key no ties to break); then the larger fraction of its convertible models already converted;
then the exact distance; then the editor id. Cells FO4Port.esm already converts are listed with status "converted" and
not ranked.
"""
import argparse
import glob
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

UNITS_PER_METRE = 70.0           # FO4 game units per metre, as the plugin writers (PluginSpike, exterior.py)
RING_M = 1000.0                  # distance rings for the second ranking key
# Landmarks (Fallout4.esm, Commonwealth): the Red Rocket building and the Sanctuary map marker, the same references
# make_cw_overlays.py LANDMARKS names; their positions are read from the band exports.
LANDMARKS = {"red_rocket": "0211C0:Fallout4.esm", "sanctuary": "072A48:Fallout4.esm"}
# Effort classes (a judgment, documented in the doc): the smallest class whose limits a cell stays within.
EFFORT_CLASSES = (("S", 300, 50), ("M", 1500, 200), ("L", 5000, 600))   # (class, max references, max new models)
DRYRUN_TOP = 20                  # "high value": the first DRYRUN_TOP ranked backlog cells
DRYRUN_PICK = 3                  # the dry run converts this many of them, the smallest by references


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def _convert_batch():
    spec = importlib.util.spec_from_file_location("convert_batch_rules", os.path.join(ROOT, "scripts", "convert_batch.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def source_key(path):
    """A model identity for comparisons: lower case, backslashes, no leading separator ('meshes\\x\\y.nif')."""
    return path.replace("/", "\\").lstrip("\\").lower()


def metres(a, b):
    """Straight-line distance in metres between two FO4 positions (x, y; z ignored), game units in."""
    return math.hypot(a[0] - b[0], a[1] - b[1]) / UNITS_PER_METRE


# ---- doors ----------------------------------------------------------------------------------------------------------

def door_model_kind(model):
    """'model' (a visible door the core build converts and places), 'marker' (an editor-marker model: the converter
    never places it; docs/ai/decisions.md 2026-10-12 writes such a door as Starfield's AutoloadDoor_Cave), or 'none'
    (the base has no model)."""
    if not model:
        return "none"
    return "marker" if re.search(r"marker", model, re.I) else "model"


def arrival(door):
    """An enabled exterior door with a recorded arrival: placed by the core build, or an AutoLoadMarker01 door
    (decisions.md 2026-10-12 writes those as AutoloadDoor_Cave; other marker doors such as InvisibleDoor01 have no
    recorded path). An initially disabled door is no way in."""
    return not door["disabled"] and (door["placed"] or bool(re.search(r"autoloadmarker", door["model"] or "", re.I)))


def census(bands, placed, landmarks=LANDMARKS):
    """Every exterior load door of the bands (dicts as the exporter writes them, iterated once), with its destination.
    placed: the source keys the core build placed. Returns {"doors": [...], "landmarks": {name: [x, y, z]}, "totals"}."""
    doors, deps, found, tot = [], {}, {}, Counter()
    wanted = {v: k for k, v in landmarks.items()}
    for band in bands:
        tot["bands"] += 1
        for d in band.get("teleport_dependencies", []):
            if d["source"] in deps:
                raise ValueError(f"{d['source']} exported twice (overlapping bands?)")
            deps[d["source"]] = d
        for r in band.get("refs", []):
            tot["refs"] += 1
            if r.get("type") == "Door":
                tot["doors"] += 1
            if r.get("formkey") in wanted:
                found[wanted[r["formkey"]]] = list(r["pos"])
            if r.get("teleport_destination"):
                doors.append(r)
        for r in band.get("deferred_refs", []):
            if r.get("teleport_destination"):         # the exporter defers only non-REFR placements; none teleport
                raise ValueError(f"deferred placement {r.get('formkey')} has a teleport destination")
    missing = sorted(set(landmarks) - set(found))
    if missing:
        raise ValueError(f"landmark references not in the bands: {missing}")
    out = []
    for r in doors:
        dep = deps.get(r["formkey"])
        if dep is None:
            raise ValueError(f"load door {r['formkey']} has no teleport_dependencies entry")
        cell = dep.get("destination_cell")
        model = r.get("model") or ""
        out.append({"formkey": r["formkey"], "type": r.get("type"), "base_editor_id": r.get("base_editor_id"),
                    "model": model, "model_kind": door_model_kind(model), "pos": r["pos"],
                    "exterior_cell": r.get("exterior_cell"), "placed": r["formkey"] in placed,
                    "disabled": bool(r.get("disabled")), "enable_parent": bool(r.get("enable_parent")),
                    "destination_door": dep.get("door"), "destination_cell": cell,
                    "kind": "unresolved" if cell is None else "interior" if cell.get("worldspace") is None else "worldspace"})
    tot["load_doors"] = len(out)
    tot.update({f"to_{k}": n for k, n in Counter(d["kind"] for d in out).items()})
    return {"doors": out, "landmarks": found, "totals": dict(tot)}


def destinations(doors):
    """{cell formkey: {"formkey", "editor_id", "doors": [door, ...]}} for the doors that lead into interiors."""
    cells = {}
    for d in doors:
        if d["kind"] != "interior":
            continue
        c = d["destination_cell"]
        cells.setdefault(c["formkey"], {"formkey": c["formkey"], "editor_id": c.get("editor_id"), "doors": []})["doors"].append(d)
    return cells


def lead_ons(export):
    """The interiors an export's own load doors lead into: [(cell formkey, editor id, destination door)], one per door;
    links into worldspaces, back into the same cell and unresolved ones left out."""
    out = []
    for t in export.get("teleport_dependencies", []):
        c = t.get("destination_cell")
        if c is not None and c.get("worldspace") is None and c.get("formkey") != export.get("formkey"):
            out.append((c["formkey"], c.get("editor_id"), t.get("door")))
    return out


def second_hop(start, exports):
    """The interiors reached only through other interiors: from the exports of `start` (the editor ids of the cells an
    exterior door leads into), follow every load door of every export into interiors not in `start`, until no new
    interior turns up (a cell without an export in `exports` is recorded, not followed). Returns {cell formkey:
    {"formkey", "editor_id", "hop" (2 = behind a first-hop cell), "reached_from": {editor id: doors},
    "destination_doors"}} in discovery order."""
    known = {exports[e]["formkey"] for e in start}
    found, frontier, hop = {}, [(e, exports[e]) for e in sorted(start)], 2
    while frontier:
        nxt = []
        for eid, exp in frontier:
            for fk, teid, door in lead_ons(exp):
                if fk in known:
                    continue
                s = found.get(fk)
                if s is None:
                    s = found[fk] = {"formkey": fk, "editor_id": teid, "hop": hop, "reached_from": Counter(),
                                     "destination_doors": []}
                    if teid in exports:
                        nxt.append((teid, exports[teid]))
                s["reached_from"][eid] += 1
                s["destination_doors"].append(door)
        frontier, hop = nxt, hop + 1
    return found


# ---- per-cell measures ----------------------------------------------------------------------------------------------

def manifest_sets(manifest):
    """(converted source keys, failed source keys) of a convert_batch manifest."""
    return ({source_key(i["source"]) for i in manifest.get("items", [])},
            {source_key(f["nif"]) for f in manifest.get("failures", [])})


def cell_measures(export, candidates, converted, failed, core_sources=frozenset(), archive=None):
    """What one interior export holds. candidates: the meshes convert_batch would convert for it (cell_candidates);
    archive: the source keys of every mesh in the FO4 archives (None: not checked)."""
    refs = export.get("refs", [])
    models = {source_key("meshes\\" + r["model"].lstrip("\\/")) for r in refs if r.get("model")}
    cand = {source_key(c) for c in candidates}
    conv = cand & converted
    fail = (cand - conv) & failed
    inner = Counter()
    for t in export.get("teleport_dependencies", []):
        c = t.get("destination_cell")
        if c is None:
            inner["(unresolved)"] += 1
        elif c.get("worldspace") is None and c.get("formkey") != export.get("formkey"):
            inner[c.get("editor_id") or c["formkey"]] += 1
    return {"refs": len(refs), "deferred": len(export.get("deferred_refs", [])),
            "actors": sum(1 for d in export.get("deferred_refs", []) if d.get("type") == "PlacedNpc"),
            "lights": sum(1 for r in refs if r.get("type") == "Light"),
            "types": dict(Counter(r.get("type") or "?" for r in refs).most_common()),
            "distinct_models": len(models), "convertible_models": len(cand),
            "converted_in_integ": len(conv), "failed_in_integ": len(fail),
            "converted_fraction": round(len(conv) / len(cand), 4) if cand else 1.0,
            "in_core_build": len(cand & core_sources), "new_models": len(cand - conv - fail),
            "teleports_inside": len(export.get("teleport_dependencies", [])),
            "leads_to_interiors": dict(sorted(inner.items())), "_new": sorted(cand - conv - fail),
            **({} if archive is None else {"missing_from_archives": len(cand - archive)})}


def effort(m, seconds_per_model=None):
    """Effort estimate of one cell: its class (EFFORT_CLASSES) and, with a measured rate, the conversion seconds."""
    cls = "XL"
    for name, max_refs, max_new in EFFORT_CLASSES:
        if m["refs"] <= max_refs and m["new_models"] <= max_new:
            cls = name
            break
    out = {"class": cls, "new_models": m["new_models"], "refs_to_place": m["refs"], "actors_deferred": m["actors"],
           "load_doors_in_cell": m["teleports_inside"]}
    if seconds_per_model is not None:
        out["convert_s_est"] = round(m["new_models"] * seconds_per_model, 1)
    return out


def nearest(doors, landmarks):
    """(metres, landmark name, door formkey) of the door nearest to a landmark."""
    best = None
    for d in doors:
        for name, pos in sorted(landmarks.items()):
            m = metres(d["pos"], pos)
            if best is None or m < best[0]:
                best = (m, name, d["formkey"])
    return best


def rank_key(c):
    """The ranking (module docstring): doors, distance ring, converted fraction, distance, editor id."""
    return (-c["doors"], int(c["nearest_m"] // RING_M), -c["converted_fraction"], c["nearest_m"], c["editor_id"] or "")


def rank(cells):
    """Backlog cells in rank order with "rank" and the models each adds in that order ("adds_models", cumulative)."""
    out = sorted(cells, key=rank_key)
    seen, total = set(), 0
    for i, c in enumerate(out, 1):
        add = [m for m in c["_new"] if m not in seen]
        seen.update(add)
        total += len(add)
        c["rank"], c["adds_models"], c["cumulative_new_models"] = i, len(add), total
    return out


def pick_dryrun(ranked, top=DRYRUN_TOP, pick=DRYRUN_PICK):
    """The dry run's cells: of the first `top` ranked that are enterable, the `pick` smallest by references (then new
    models, rank)."""
    return sorted((c for c in ranked[:top] if c["enterable"]), key=lambda c: (c["refs"], c["new_models"], c["rank"]))[:pick]


def dryrun_result(staging):
    """A convert_batch staging's measured outcome (manifest.json, failure-summary.json)."""
    man = load(os.path.join(staging, "manifest.json"))
    summary_path = os.path.join(staging, "failure-summary.json")
    summary = load(summary_path) if os.path.exists(summary_path) else {}
    attempted = len(man["items"]) + len(man["failures"])
    return {"staging": staging, "seconds": man["seconds"], "attempted": attempted, "converted": len(man["items"]),
            "failed": len(man["failures"]), "reused": man["stats"].get("reused", 0),
            "seconds_per_model": round(man["seconds"] / attempted, 3) if attempted else None,
            "reasons": summary.get("reasons", dict(Counter(f["reason"].split(":")[0].strip() for f in man["failures"]))),
            "failures": man["failures"],
            "load_doors": sum(1 for i in man["items"] if "load_door" in i),
            "doors": sum(1 for i in man["items"] if "door" in i),
            "movables": sum(1 for i in man["items"] if "movable" in i)}


def placeable(export, manifest):
    """PluginSpike's per-cell counters for a cell export with this manifest (Program.cs): "placed" and "skipped" over
    the references that are neither the COC marker nor a light (placed when the model was converted), plus the light
    references (the writer merges lights within LIGHT_MERGE_M, 3 m, so it writes fewer) and the COC markers."""
    have = {source_key(i["source"]) for i in manifest["items"]}
    out = Counter()
    for r in export["refs"]:
        if r.get("base_editor_id") == "COCMarkerHeading":
            out["coc_markers"] += 1
        elif r.get("type") == "Light":
            out["light_refs"] += 1
        elif r.get("model") and source_key("meshes\\" + r["model"].lstrip("\\/")) in have:
            out["placed"] += 1
        else:
            out["skipped"] += 1
    return {k: out.get(k, 0) for k in ("placed", "skipped", "light_refs", "coc_markers")}


def converted_cells(integ):
    """Editor ids of the interiors a staging's plugin converts: its <Cell>.json exports ("cell" == file stem)."""
    out = set()
    for p in glob.glob(os.path.join(integ, "*.json")):
        stem = os.path.splitext(os.path.basename(p))[0]
        if stem in ("merged", "manifest", "formids", "editorids", "lighting") or stem.startswith(("routes", "probe")):
            continue
        try:
            d = load(p)
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and d.get("cell") == stem and "refs" in d:
            out.add(stem)
    return out


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---- the plan -------------------------------------------------------------------------------------------------------

def plan(doors_doc, exports, candidates_of, converted, failed, done_cells, core_sources=frozenset(), dryruns=(),
         archive=None):
    """The backlog document. exports: {editor id: export dict}; candidates_of(export) -> convert_batch's meshes."""
    landmarks = doors_doc["landmarks"]
    rate = None
    measured = [d for d in dryruns if d.get("attempted")]
    if measured:
        rate = round(sum(d["seconds"] for d in measured) / sum(d["attempted"] for d in measured), 3)
    backlog, done = [], []
    for fk, c in sorted(destinations(doors_doc["doors"]).items()):
        eid = c["editor_id"]
        if eid not in exports:
            raise ValueError(f"no export for destination interior {eid} ({fk})")
        exp = exports[eid]
        if exp.get("formkey") != fk:
            raise ValueError(f"export {eid} is cell {exp.get('formkey')}, the doors lead into {fk}")
        held = {r["formkey"] for r in exp.get("refs", [])}
        lost = [d["destination_door"] for d in c["doors"] if d["destination_door"] not in held]
        if lost:                            # the export must hold every destination door the census put in it
            raise ValueError(f"{eid}: destination doors not in its export: {lost}")
        m = cell_measures(exp, candidates_of(exp), converted, failed, core_sources, archive)
        near = nearest(c["doors"], landmarks)
        kinds = Counter(d["model_kind"] for d in c["doors"])
        placed_n = sum(1 for d in c["doors"] if d["placed"])
        entry = {"editor_id": eid, "formkey": fk, "status": "converted" if eid in done_cells else "backlog",
                 "doors": len(c["doors"]), "doors_placed_by_core": placed_n,
                 # distinct positions of the enabled doors (stacked quest-state doors count once; not a ranking key)
                 "entrances": len({tuple(d["pos"]) for d in c["doors"] if not d["disabled"]}),
                 "doors_marker": kinds.get("marker", 0), "doors_without_model": kinds.get("none", 0),
                 "doors_disabled": sum(1 for d in c["doors"] if d["disabled"]),
                 "doors_enable_parent": sum(1 for d in c["doors"] if d["enable_parent"]),
                 "enterable": any(arrival(d) for d in c["doors"]),
                 "nearest_m": round(near[0], 1), "nearest_landmark": near[1], "nearest_door": near[2],
                 "distance_m": {k: round(min(metres(d["pos"], p) for d in c["doors"]), 1) for k, p in sorted(landmarks.items())},
                 **m,
                 "exterior_doors": [{k: d[k] for k in ("formkey", "base_editor_id", "model_kind", "exterior_cell", "pos",
                                                       "placed", "disabled", "enable_parent", "destination_door")}
                                    for d in c["doors"]]}
        entry["effort"] = effort(entry, rate)
        (done if entry["status"] == "converted" else backlog).append(entry)
    ranked = rank(backlog)
    picks = pick_dryrun(ranked)
    union = set().union(*(c["_new"] for c in ranked))
    hops = []                               # interiors reached only through other interiors (second_hop)
    reach = {c["editor_id"]: c["rank"] for c in ranked}
    reach.update((c["editor_id"], 0) for c in done)
    for fk, s in second_hop([c["editor_id"] for c in ranked + done], exports).items():
        eid = s["editor_id"]
        # reachable once the earliest-ranked cell leading into it is converted (0: through a converted interior)
        reach[eid] = after = min(reach[p] for p in s["reached_from"] if p in reach)
        entry = {"editor_id": eid, "formkey": fk, "status": "not_exported", "hop": s["hop"], "after_rank": after,
                 "reached_from": dict(sorted(s["reached_from"].items())),
                 "doors_from_interiors": sum(s["reached_from"].values())}
        exp = exports.get(eid)
        if exp is not None:
            if exp.get("formkey") != fk:
                raise ValueError(f"export {eid} is cell {exp.get('formkey')}, the doors lead into {fk}")
            held = {r["formkey"] for r in exp.get("refs", [])}
            lost = [d for d in s["destination_doors"] if d not in held]
            if lost:
                raise ValueError(f"{eid}: destination doors not in its export: {lost}")
            entry["status"] = "converted" if eid in done_cells else "backlog"
            entry.update(cell_measures(exp, candidates_of(exp), converted, failed, core_sources, archive))
            entry["effort"] = effort(entry, rate)
        hops.append(entry)
    hops.sort(key=lambda c: (c["after_rank"], c["hop"], c["editor_id"] or ""))
    seen = set(union)
    for c in hops:                          # the models each adds after the whole ranked backlog, in this order
        if c["status"] == "backlog":
            add = [m for m in c["_new"] if m not in seen]
            seen.update(add)
            c["adds_models"], c["cumulative_new_models"] = len(add), len(seen)
    for c in ranked + done + hops:
        c.pop("_new", None)
    ws = {}
    for d in doors_doc["doors"]:
        if d["kind"] == "worldspace":
            ws.setdefault(d["destination_cell"]["worldspace"], []).append(
                {k: d[k] for k in ("formkey", "base_editor_id", "model_kind", "exterior_cell", "placed", "destination_door")})
    t = dict(doors_doc["totals"])
    if archive is not None:
        t["backlog_cells_with_models_missing_from_archives"] = sum(1 for c in ranked if c.get("missing_from_archives"))
        t["backlog_new_models_missing_from_archives"] = len(union - archive)
    t.update({"interiors": len(ranked) + len(done), "interiors_converted": len(done), "interiors_backlog": len(ranked),
              "doors_into_converted": sum(c["doors"] for c in done), "doors_into_backlog": sum(c["doors"] for c in ranked),
              "backlog_not_enterable": sum(1 for c in ranked if not c["enterable"]),
              "backlog_refs": sum(c["refs"] for c in ranked), "backlog_new_models": len(union),
              "backlog_new_models_per_cell_sum": sum(c["new_models"] for c in ranked),
              "backlog_new_models_in_core_build": len(union & core_sources),
              "effort_classes": dict(sorted(Counter(c["effort"]["class"] for c in ranked).items()))})
    hb = [c for c in hops if c["status"] == "backlog"]
    t.update({"second_hop_interiors": len(hops), "second_hop_converted": sum(1 for c in hops if c["status"] == "converted"),
              "second_hop_not_exported": sum(1 for c in hops if c["status"] == "not_exported"),
              "second_hop_backlog": len(hb), "second_hop_backlog_through_converted": sum(1 for c in hb if c["after_rank"] == 0),
              "doors_into_second_hop_backlog": sum(c["doors_from_interiors"] for c in hb),
              "second_hop_backlog_refs": sum(c["refs"] for c in hb), "second_hop_adds_models": len(seen) - len(union),
              "backlog_and_second_hop_new_models": len(seen)})
    if archive is not None:
        t["second_hop_new_models_missing_from_archives"] = len(seen - union - archive)
    if rate is not None:
        t["backlog_convert_s_est"] = round(t["backlog_new_models"] * rate, 1)
        t["backlog_and_second_hop_convert_s_est"] = round(len(seen) * rate, 1)
    return {"note": "scripts/terrain/interior_backlog.py plan: every FO4 interior an exterior load door of the core leads "
                    "into, ranked, then the interiors reached only through those (docs/terrain/interior-backlog.md)",
            "rank_key": "doors desc, ring of nearest_m (RING_M) asc, converted_fraction desc, nearest_m asc, editor_id",
            "ring_m": RING_M, "effort_classes": [list(e) for e in EFFORT_CLASSES], "seconds_per_model": rate,
            "landmarks": {k: {"formkey": LANDMARKS.get(k), "pos": v} for k, v in sorted(landmarks.items())},
            "totals": t, "dryrun_pick": [c["editor_id"] for c in picks], "dryrun": list(dryruns),
            "worldspace_destinations": dict(sorted(ws.items())),
            "backlog": ranked, "converted": sorted(done, key=lambda c: c["editor_id"]), "second_hop": hops}


def md_table(doc, limit=0):
    """The ranked backlog as a markdown table, then the second-hop interiors not converted."""
    rows = ["| # | Interior | Doors (placed) | Nearest m | Refs | Models | Convertible | Converted | New | Adds | Class | Leads on to |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in doc["backlog"][:limit or None]:
        on = ", ".join(f"{k} x{n}" if n > 1 else k for k, n in c["leads_to_interiors"].items()) or "-"
        name = c["editor_id"] + ("" if c["enterable"] else " (no arrival)")
        rows.append(f"| {c['rank']} | {name} | {c['doors']} ({c['doors_placed_by_core']}) | {c['nearest_m']:.0f} "
                    f"| {c['refs']:,} | {c['distinct_models']:,} | {c['convertible_models']:,} | {c['converted_in_integ']:,} "
                    f"({100 * c['converted_fraction']:.0f}%) | {c['new_models']:,} | {c['adds_models']:,} | {c['effort']['class']} | {on} |")
    hops = [c for c in doc.get("second_hop", []) if c["status"] != "converted"]
    if hops:
        rows += ["", "| After rank | Interior | Hop | Reached from (doors) | Refs | Convertible | Converted | New | Adds | Class |",
                 "|---|---|---|---|---|---|---|---|---|---|"]
    for c in hops:
        frm = ", ".join(f"{k} x{n}" if n > 1 else k for k, n in c["reached_from"].items())
        if c["status"] == "not_exported":
            rows.append(f"| {c['after_rank']} | {c['editor_id']} | {c['hop']} | {frm} | not exported | | | | | |")
            continue
        rows.append(f"| {c['after_rank']} | {c['editor_id']} | {c['hop']} | {frm} | {c['refs']:,} | {c['convertible_models']:,} "
                    f"| {c['converted_in_integ']:,} ({100 * c['converted_fraction']:.0f}%) | {c['new_models']:,} "
                    f"| {c['adds_models']:,} | {c['effort']['class']} |")
    return "\n".join(rows) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("doors")
    p.add_argument("--work", required=True)
    p.add_argument("--build", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--cells-txt", default="")
    p = sub.add_parser("plan")
    p.add_argument("--doors", required=True)
    p.add_argument("--exports", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--converted", required=True, help="the interiors' staging (integ_1011): its <Cell>.json exports")
    p.add_argument("--core-build", default="", help="core64 staging: count candidates the exterior build converted")
    p.add_argument("--fo4-data", default="", help="FO4 Data folder: count candidates no FO4 mesh archive holds")
    p.add_argument("--dryrun", nargs="*", default=[])
    p.add_argument("--json", required=True)
    p.add_argument("--md-table", default="")
    p.add_argument("--next-cells-txt", default="", help="write the second-hop interiors without an export, one per line")
    a = ap.parse_args(argv)
    if a.cmd == "doors":
        paths = sorted(glob.glob(os.path.join(a.work, "export", "band_*.json")))
        if not paths:
            sys.exit(f"no export bands under {a.work}")
        placed = {r["src"] for r in load(os.path.join(a.build, "objects.json"))["refs"]}
        doc = census((load(p) for p in paths), placed)
        doc["inputs"] = {"bands": [os.path.basename(p) for p in paths], "build": a.build}
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=1)
        cells = sorted({c["editor_id"] for c in destinations(doc["doors"]).values()})
        if a.cells_txt:
            with open(a.cells_txt, "w", encoding="utf-8", newline="\n") as f:
                f.write("".join(e + "\n" for e in cells))
        print(json.dumps(doc["totals"]), f"{len(cells)} destination interiors -> {a.out}")
        return 0
    doors_doc = load(a.doors)
    cb = _convert_batch()
    wanted = set(cb.DEFAULT_CELL_TYPES.split(","))
    manifest = load(a.manifest)
    converted, failed = manifest_sets(manifest)
    exports = {}
    want = [c["editor_id"] for c in destinations(doors_doc["doors"]).values()]
    while want:                             # the destinations, then each hop of interiors behind them that is exported
        for eid in want:
            p = os.path.join(a.exports, eid + ".json")
            if os.path.exists(p):
                exports[eid] = load(p)
        start = [c["editor_id"] for c in destinations(doors_doc["doors"]).values() if c["editor_id"] in exports]
        want = [s["editor_id"] for s in second_hop(start, exports).values() if s["editor_id"] not in exports
                and os.path.exists(os.path.join(a.exports, s["editor_id"] + ".json"))]
    core = frozenset()
    if a.core_build:
        core = frozenset(source_key(b["source"]) for b in load(os.path.join(a.core_build, "objects.json"))["bases"])
    dry = []
    for s in a.dryrun:
        d = dryrun_result(s)
        cell = os.path.basename(os.path.normpath(s))
        d["cell"] = cell
        if cell in exports:
            d.update(placeable(exports[cell], load(os.path.join(s, "manifest.json"))))
        dry.append(d)
    archive = None
    if a.fo4_data:
        sys.path.insert(0, os.path.join(ROOT, "src"))
        from fo4sf import pipeline
        archive = {source_key(n) for n in pipeline.Fo4Archives(a.fo4_data).mesh_names("")}
    doc = plan(doors_doc, exports, lambda e: cb.cell_candidates(e, wanted), converted, failed,
               converted_cells(a.converted), core, dry, archive)
    doc["inputs"] = {"doors": a.doors, "exports": a.exports, "manifest": a.manifest,
                     "manifest_sha256": sha256(a.manifest), "converted": a.converted, "core_build": a.core_build,
                     "candidate_types": cb.DEFAULT_CELL_TYPES, "fo4_data": a.fo4_data}
    with open(a.json, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    if a.md_table:
        with open(a.md_table, "w", encoding="utf-8", newline="\n") as f:
            f.write(md_table(doc))
    todo = sorted(c["editor_id"] for c in doc["second_hop"] if c["status"] == "not_exported")
    if a.next_cells_txt:
        with open(a.next_cells_txt, "w", encoding="utf-8", newline="\n") as f:
            f.write("".join(e + "\n" for e in todo))
    print(json.dumps(doc["totals"], indent=1))
    print("dry run pick:", doc["dryrun_pick"])
    if todo:
        print(f"{len(todo)} second-hop interiors without an export (export them and re-run):", " ".join(todo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
