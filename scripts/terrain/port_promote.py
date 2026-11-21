"""port_promote.py: the interior promotion list for dotnet/PluginSpike (docs/terrain/port-promotions.md).

  python scripts/terrain/port_promote.py --out <PluginSpike output dir>/promote.json
         --containers-table scripts/terrain/clusters/container_table.json --items-table scripts/terrain/clusters/item_table.json
         [--names <export-names json>] [--starfield-data <Starfield Data folder>]
         [--furniture <Fo4Land export-furniture json> [--fo4-data <Fallout 4 Data folder>]]
         [--fo4-loot --manifest <manifest.json> [--fo4-plugin <Fallout4.esm> ...] [--loot-table <json>] [--loot-fallbacks-out <json>]]
         [--usable-beds-benches [--benches-table scripts/terrain/clusters/bench_table.json]] <cell export.json> ...

The converted interiors (FO4Port.esm) placed every FO4 container, loose item, activator and terminal as a plain STAT
(or an MSTT when its model has a dynamic body): nothing to open, take, press or read (owner's play test, 18 Oct
19:32Z to 19:41Z). The exterior core promotes the same classes (make_cluster.py, make_core64c.py, TerrainOverlays);
this writes the same lists for the cell exports PluginSpike reads, with the same rules and tables, so PluginSpike gives
those references a CONT / MISC / ACTI / TERM base instead (dotnet/PluginSpike/Promotions.cs):
  containers  FO4 Container, the container table's name and vanilla inventory (or, with --fo4-loot, Fallout 4's CNTO/LVLI
              loot wherever a converted item model exists in --manifest, logging every fallback)
  items       FO4 MiscItem / Ingestible / Weapon, the item table's name, value and weight (MISC, as the core)
  activators  FO4 Activator, its FO4 name from --names (none: an ACTI without a name, as FO4 shows no prompt)
  terminals   FO4 Terminal, its name and one body line (make_cluster.TERMINAL_BODY); needs --starfield-data (the
              vanilla terminal's furniture block is read from Starfield.esm by PluginSpike)
  furniture   (with --furniture) FO4 chairs (NPCChairTech03_Free_270 0027D5) and, with --usable-beds-benches, FO4 beds
              (Bed_Single01 1FA770: IsSleepFurniture 021B18 + AnimFurnBed 1FA760)
  benches     (with --usable-beds-benches) FO4 weapon / armor / chem / cooking workbenches (Starfield.esm 2B6A63 /
              2B6A62 / 2B6A61 / 2B6A65, keeping WBDT bench type and recipe keywords; power armor stations skipped)
Left out as the core leaves them out: initially disabled references and ones without a model or with a marker model.
Edids are the core's (make_core64c.promoted_edid) with FO4Port_ for FO4Core_: one base per FO4 base record.
A reference the port puts on its own posed model or on a DOOR base keeps it (PluginSpike counts it as kept).
"""
import argparse
import fnmatch
import json
import math
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)
import make_cluster  # noqa: E402
import make_core64c  # noqa: E402
from fo4sf import fo4loot, fo4station, nif, pipeline  # noqa: E402

PREFIX = "FO4Port_"
KINDS = ("containers", "items", "activators", "terminals", "furniture")
CHAIR_TEMPLATE = "0027D5"         # NPCChairTech03_Free_270:Starfield.esm (PC dump, 2026-10-18 20:03Z, SfInspect furn)
BED_TEMPLATE = "1FA770"           # Bed_Single01:Starfield.esm (IsSleepFurniture 021B18, AnimFurnBed 1FA760, Bed_Marker.nif)
BENCH_TEMPLATES = {
    "weapon": "2B6A63",           # WorkbenchWeapon:Starfield.esm (WBDT=2, Weapon Workbench)
    "armor": "2B6A62",            # WorkbenchArmor:Starfield.esm (WBDT=7, Spacesuit Workbench)
    "chem": "2B6A61",             # WorkbenchChem:Starfield.esm (WBDT=5, Pharmaceutical Lab)
    "cooking": "2B6A65",          # WorkbenchFood:Starfield.esm (WBDT=5, Cooking Station)
}
BENCH_DEFAULT_NAMES = {k: v["name"] for k, v in make_cluster.BENCH_KINDS.items()}
COOKING_ALIASES = ("CookingFire*", "CookingGround*", "CookingSpit*", "CookingStove*")
FURNITURE_TYPES = ("Furniture",)
CHAIR_KEYWORD_PREFIX = "animfurnchair"
BED_KEYWORD_SUBSTRINGS = ("animfurnbed", "animfurnsleep", "issleepfurniture")
BED_EDID_RE = re.compile(r"(bed|mattress|sleepingbag|sleepbag|bunk|cot)(?!.*(ruined|broken|frameonly))", re.I)
UNITS_PER_METRE = 70.0
DEFAULT_BENCH_TABLE = os.path.join(HERE, "clusters", "bench_table.json")


def furniture_kind(base, usable_beds_benches=False):
    """"chair" (or "bed" when `usable_beds_benches` is True), or why a FO4 furniture base is not promoted here."""
    if base is None:
        return "not in the furniture export"
    if base.get("bench_type") not in (None, "None", 0):
        return "crafting bench"
    keywords = [str(k).casefold() for k in base.get("keywords") or []]
    entry_types = {str(e.get("type")) for e in base.get("entry_points") or []}
    sits = "Sit" in entry_types
    if sits and any(k.startswith(CHAIR_KEYWORD_PREFIX) for k in keywords):
        return "chair"
    if usable_beds_benches:
        lays_or_sleeps = bool(entry_types & {"Lay", "Sleep"})
        has_bed_kw = any(any(sub in k for sub in BED_KEYWORD_SUBSTRINGS) for k in keywords)
        if has_bed_kw or lays_or_sleeps:
            return "bed"
    anim = next((k for k in keywords if k.startswith("animfurn")), "no AnimFurn keyword")
    return f"not a chair yet ({anim})"


def chair_markers(nif_bytes):
    """[{"offset": metres, "rotation_z": degrees}] from a FO4 NIF's furniture markers, None when it has none."""
    if not nif_bytes:
        return None
    marks = nif.furniture_markers(nif.parse(nif_bytes))
    if not marks:
        return None
    return [{"offset": [round(c / UNITS_PER_METRE, 4) for c in m["offset"]],
             "rotation_z": round(math.degrees(m["heading"]), 3)} for m in marks]


def furniture(refs, placed, bases, mesh=None, names=None, prefix=PREFIX, usable_beds_benches=False):
    """(entries, report): every placed FO4 Furniture reference that furniture_kind calls a chair (and a bed when
    `usable_beds_benches` is True), one shared base per FO4 base, markers from its NIF when `mesh` reads one."""
    order = {src: i for i, src in enumerate(placed)}
    names, entries, rep, markers = names or {}, [], Counter(), {}
    for r in refs:
        if str(r.get("type")) not in FURNITURE_TYPES:
            continue
        src, base = r.get("formkey"), r.get("base_formkey")
        why = make_cluster.left_out_reason(r, order, {})
        if why:
            rep[f"left out: {why}"] += 1
            continue
        base_info = (bases or {}).get(base)
        if bases is not None:
            kind = furniture_kind(base_info, usable_beds_benches=usable_beds_benches)
        elif usable_beds_benches and BED_EDID_RE.search(str(r.get("base_editor_id") or "")):
            kind = "bed"
        else:
            kind = "not in the furniture export"
        if kind not in ("chair", "bed"):
            rep[f"left out: {kind}"] += 1
            continue
        if base not in markers:
            markers[base] = chair_markers(mesh("meshes\\" + str(r["model"]).lstrip("\\"))) if mesh else None
        default_label = "Bed" if kind == "bed" else "Chair"
        template_hex = BED_TEMPLATE if kind == "bed" else CHAIR_TEMPLATE
        name = names.get(base) or ((base_info or {}).get("name") or default_label)
        entries.append({"src": src, "edid": port_edid("furn", base, src, prefix=prefix), "name": name,
                        "template": template_hex, "markers": markers[base], "slot": order[src]})
        if kind == "bed":
            rep["beds with FO4 markers" if markers[base] else "beds with the template marker"] += 1
            rep["beds"] += 1
        else:
            rep["chairs with FO4 markers" if markers[base] else "chairs with the template marker"] += 1
    entries.sort(key=lambda e: e["slot"])
    for e in entries:
        del e["slot"]
    rep["furniture"] = len(entries)
    return entries, dict(rep)


def _match_bench_kind(edid, bench_table):
    """Return (kind_or_none, skip_reason_or_none) for a FO4 furniture base editor_id against bench_table.json."""
    entry, match_type = make_cluster.table_entry(bench_table or {}, edid or "")
    if match_type == "none" and edid:
        low_edid = edid.casefold()
        by = (bench_table or {}).get("by_editor_id") or {}
        best = None
        for k, v in by.items():
            kl = k.casefold()
            if kl == low_edid:
                entry, match_type = v, "exact"
                break
            if kl.endswith("*") and low_edid.startswith(kl[:-1]) and (best is None or len(kl) > len(best[0])):
                best = (kl, v)
        if match_type == "none" and best is not None:
            entry, match_type = best[1], "prefix"
    if match_type != "none" and isinstance(entry, dict):
        kind = entry.get("kind")
        if kind is None:
            return None, entry.get("reason") or "skipped bench kind"
        return kind, None
    for pat in COOKING_ALIASES:
        if fnmatch.fnmatchcase((edid or "").casefold(), pat.casefold()):
            return "cooking", None
    return None, None


def benches(refs, placed, bench_table, furniture_bases=None, raw_fo4_furn=None, names=None, prefix=PREFIX):
    """(entries, report): placed FO4 crafting workbenches (weapon, armor, chem, cooking) mapped to Starfield bench
    templates (2B6A63, 2B6A62, 2B6A61, 2B6A65); power armor stations and non-benches are skipped with reasons."""
    order = {src: i for i, src in enumerate(placed)}
    names = names or {}
    raw_fo4_furn = raw_fo4_furn or {}
    entries, rep = [], Counter()
    for r in refs:
        if str(r.get("type")) not in FURNITURE_TYPES:
            continue
        src, base = r.get("formkey"), r.get("base_formkey")
        why = make_cluster.left_out_reason(r, order, {})
        if why:
            continue
        edid = str(r.get("base_editor_id") or "")
        if furniture_bases is not None and base in furniture_bases:
            fb = furniture_bases[base]
            edid = edid or str(fb.get("editor_id") or "")
            if fb.get("bench_type") in (None, "None", 0):
                continue
            is_bench_record = True
        elif base in raw_fo4_furn:
            rb = raw_fo4_furn[base]
            edid = edid or str(rb.get("edid") or "")
            if rb.get("wbdt") in (None, 0):
                continue
            is_bench_record = True
        else:
            is_bench_record = False

        kind, skip_reason = _match_bench_kind(edid, bench_table)
        if skip_reason:
            rep[f"skipped: {skip_reason}"] += 1
            continue
        if kind not in BENCH_TEMPLATES:
            if is_bench_record:
                rep["skipped: unknown bench kind"] += 1
            continue
        disp_name = names.get(base) or BENCH_DEFAULT_NAMES[kind]
        entries.append({
            "src": src,
            "edid": port_edid("furn", base, src, prefix=prefix),
            "kind": kind,
            "name": disp_name,
            "template": BENCH_TEMPLATES[kind],
            "slot": order[src],
        })
        rep[f"bench_{kind}"] += 1
    entries.sort(key=lambda e: e["slot"])
    for e in entries:
        del e["slot"]
    rep["benches"] = len(entries)
    return entries, dict(rep)


def port_edid(kind, base, src, prefix=PREFIX):
    """The core's promoted edid (FO4Core_<kind>_<6 hex>_<plugin>) under the port's prefix."""
    core = make_core64c.promoted_edid(kind, base, src)
    return prefix + core[len(make_core64c.EDID_PREFIX):]


def cell_refs(paths):
    """(refs, placed): every exported reference of the given cell exports in file order, and the source keys of the
    ones PluginSpike can place (a model that is not a marker), in the same order. A source in two exports is refused."""
    refs, placed, seen = [], [], {}
    for p in paths:
        cell = make_cluster.load(p)
        for r in cell.get("refs", []):
            src = r.get("formkey")
            if src in seen:
                raise ValueError(f"{src} is in both {seen[src]} and {p}")
            seen[src] = p
            refs.append(r)
            if r.get("model") and not make_cluster.MARKER_RE.search(str(r["model"])):
                placed.append(src)
    return refs, placed


def _raw_fo4_furn_bases(refs, fo4_plugins):
    """Read raw `FURN` bases (`WBDT` bench type + `EDID`) from `Fallout4.esm` for placed `Furniture` refs."""
    if not fo4_plugins:
        return {}
    fo4_esm = next((p for p in fo4_plugins if os.path.basename(p).casefold() == "fallout4.esm" and os.path.isfile(p)), None)
    if not fo4_esm:
        return {}
    wanted_ids = set()
    for r in refs:
        if str(r.get("type")) in FURNITURE_TYPES and r.get("base_formkey"):
            fk = str(r["base_formkey"])
            left, _, right = fk.partition(":")
            if right.casefold() == "fallout4.esm":
                try:
                    wanted_ids.add(int(left, 16) & 0xFFFFFF)
                except ValueError:
                    pass
    if not wanted_ids:
        return {}
    parsed = fo4station.read_bases(fo4_esm, wanted_ids, groups=("FURN",))
    return {f"{fid:06X}:Fallout4.esm": info for fid, info in parsed.items()}


def promote(refs, placed, containers_table, items_table, names=None, starfield_esm=None, furniture_bases=None, mesh=None,
            prefix=PREFIX, *, fo4_loot=False, loot_index=None, manifest_models=None, explicit_loot_map=None,
            usable_beds_benches=False, bench_table=None, raw_fo4_furn=None):
    """The promote.json document: per kind the entries PluginSpike reads ({"src", "edid", ...}) and a report.
    With `fo4_loot=False` and `usable_beds_benches=False` (defaults), output is 100% SHA-256 identical to cd03411a."""
    out, report = {"note": "scripts/terrain/port_promote.py: interior promotions read by dotnet/PluginSpike "
                           "(Promotions.cs) from its output dir", "starfield_esm": starfield_esm}, {}
    conts, report["containers"] = make_cluster.containers(refs, placed, containers_table)
    out["containers"] = [{"src": e["src"], "edid": port_edid("cont", e["base"], e["src"], prefix=prefix), "name": e["name"],
                          "items": e["items"]} for e in conts["containers"]]
    its, report["items"] = make_cluster.items(refs, placed, items_table)
    out["items"] = [{"src": e["src"], "edid": port_edid("misc", e["base"], e["src"], prefix=prefix), "name": e["name"],
                     "value": e["value"], "weight": e["weight"]} for e in its["items"]]

    if fo4_loot:
        ref_base_by_src = {
            r["formkey"]: (str(r.get("base_formkey") or ""), str(r.get("base_editor_id") or ""))
            for r in refs if r.get("formkey")
        }
        names_map = names or {}

        def _item_edid(norm_fk: str) -> str:
            return port_edid("misc", norm_fk, norm_fk, prefix=prefix)

        def _item_meta(norm_fk: str, meta: dict):
            raw_edid = str(meta.get("edid") or norm_fk.split(":", 1)[0])
            tbl_entry, _ = make_cluster.table_entry(items_table or {}, raw_edid)
            tbl_entry = tbl_entry or {}
            disp_name, _ = make_cluster.display_name(
                tbl_entry.get("name"),
                raw_edid,
                norm_fk,
                names_map,
                missing=meta.get("full") or make_cluster.humanize(raw_edid),
            )
            if not disp_name:
                disp_name = meta.get("full") or make_cluster.humanize(raw_edid) or "Item"
            val = tbl_entry.get("value") if "value" in tbl_entry else meta.get("value")
            wt = tbl_entry.get("weight") if "weight" in tbl_entry else meta.get("weight")
            return disp_name, int(val if val is not None else 5), float(wt if wt is not None else 0.5)

        loot_items, loot_rep = fo4loot.resolve_containers_fo4_loot(
            out["containers"],
            ref_base_by_src,
            loot_index or fo4loot.Fo4LootIndex(),
            manifest_models or {},
            edid_for_item_fn=_item_edid,
            item_meta_fn=_item_meta,
            explicit_loot_map=explicit_loot_map,
        )
        out["loot_items"] = loot_items
        report["fo4_loot"] = loot_rep

    actis, report["activators"] = make_cluster.activators(refs, placed, names=names)
    out["activators"] = [{"src": e["src"], "edid": port_edid("acti", e["base"], e["src"], prefix=prefix), "name": e["name"]}
                         for e in actis["activators"]]
    terms, report["terminals"] = make_cluster.terminals(refs, placed, names=names)
    out["terminals"] = []
    for e in terms["terminals"]:
        edid = port_edid("term", e["base"], e["src"], prefix=prefix)
        out["terminals"].append({"src": e["src"], "edid": edid, "menu_edid": prefix + "tmlm_" + edid[len(prefix + "term_"):],
                                 "name": e["name"], "body": e["body"]})
    out["furniture"], report["furniture"] = (
        furniture(refs, placed, furniture_bases, mesh, names, prefix=prefix, usable_beds_benches=usable_beds_benches)
        if (furniture_bases is not None or usable_beds_benches)
        else ([], {})
    )
    active_kinds = list(KINDS)
    if usable_beds_benches:
        out["benches"], report["benches"] = benches(
            refs, placed, bench_table, furniture_bases=furniture_bases,
            raw_fo4_furn=raw_fo4_furn, names=names, prefix=prefix,
        )
        active_kinds.append("benches")

    master_kinds = [("terminals", "terminal's"), ("furniture", "chair/bed's" if usable_beds_benches else "chair's")]
    if usable_beds_benches:
        master_kinds.append(("benches", "workbench's"))
    for kind, what in master_kinds:
        if out[kind] and not starfield_esm:
            raise ValueError(f"{len(out[kind])} {kind} need --starfield-data (PluginSpike copies the vanilla "
                             f"{what} furniture block from Starfield.esm)")
    for kind in active_kinds:                                 # one shared base per edid carries one value (Promotions.cs)
        first = {}
        for e in out[kind]:
            sig = {k: v for k, v in e.items() if k != "src"}
            if first.setdefault(e["edid"], (e["src"], sig))[1] != sig:
                raise ValueError(f"{e['src']} and {first[e['edid']][0]} share {kind} {e['edid']} with different values")
    out["report"] = report
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("exports", nargs="+", help="the cell exports PluginSpike is given (dotnet/Fo4Export)")
    ap.add_argument("--out", required=True, help="promote.json in PluginSpike's output dir")
    ap.add_argument("--containers-table", required=True)
    ap.add_argument("--items-table", required=True)
    ap.add_argument("--names", default="", help="FO4 display names: dotnet/Fo4Land export-names over Fallout4.esm")
    ap.add_argument("--starfield-data", default="", help="Starfield's Data folder (Starfield.esm: terminal and chair templates)")
    ap.add_argument("--furniture", default="", help="dotnet/Fo4Land export-furniture over Fallout4.esm: promotes chairs (and beds with --usable-beds-benches)")
    ap.add_argument("--fo4-data", default="", help="Fallout 4's Data folder: the chairs'/beds' sit/sleep markers from their NIFs, and Fallout4.esm when needed")
    ap.add_argument("--prefix", default="fo4port", help="EditorID prefix slug (default fo4port -> FO4Port_)")
    ap.add_argument("--fo4-loot", action="store_true",
                    help="off by default: populate containers from Fallout 4 CNTO/LVLI records where converted items exist in --manifest, logging fallbacks")
    ap.add_argument("--manifest", default="", help="with --fo4-loot: conversion manifest.json listing converted FO4 models")
    ap.add_argument("--fo4-plugin", action="append", default=[],
                    help="with --fo4-loot / --usable-beds-benches: Fallout4.esm (first) and optional DLC .esm paths in load order")
    ap.add_argument("--loot-table", default="", help="with --fo4-loot: optional JSON mapping FO4 item FormKeys to target <plugin>:<hex> forms")
    ap.add_argument("--loot-fallbacks-out", default="", help="with --fo4-loot: optional path to write logged container loot fallbacks JSON")
    ap.add_argument("--usable-beds-benches", action="store_true",
                    help="off by default: also promote FO4 beds (Bed_Single01 1FA770) and crafting benches (2B6A63/2B6A62/2B6A61/2B6A65)")
    ap.add_argument("--benches-table", default=DEFAULT_BENCH_TABLE,
                    help="with --usable-beds-benches: FO4 workbench table JSON (default: scripts/terrain/clusters/bench_table.json)")
    a = ap.parse_args(argv)
    edid_prefix = pipeline.editor_id_prefix(a.prefix) + "_"
    refs, placed = cell_refs(a.exports)
    sf = os.path.abspath(os.path.join(a.starfield_data, "Starfield.esm")) if a.starfield_data else None
    if sf and not os.path.isfile(sf):
        raise SystemExit(f"no Starfield.esm in {a.starfield_data}")
    mesh = None
    if a.fo4_data:
        has_ba2 = os.path.isdir(a.fo4_data) and any(fn.lower().endswith(".ba2") for fn in os.listdir(a.fo4_data))
        if has_ba2:
            mesh = pipeline.Fo4Archives(a.fo4_data).mesh

    fo4_plugins = list(a.fo4_plugin)
    if not fo4_plugins and a.fo4_data:
        cand_fo4 = os.path.join(a.fo4_data, "Fallout4.esm")
        if os.path.isfile(cand_fo4):
            fo4_plugins.append(cand_fo4)

    loot_index = None
    manifest_models = None
    explicit_loot_map = None
    if a.fo4_loot:
        loot_index = fo4loot.Fo4LootIndex.from_plugins(fo4_plugins) if fo4_plugins else fo4loot.Fo4LootIndex()
        manifest_models = fo4loot.load_manifest_models(a.manifest) if a.manifest else {}
        if a.loot_table:
            explicit_loot_map = make_cluster.load(a.loot_table)

    bench_tbl = None
    raw_fo4_furn = None
    if a.usable_beds_benches:
        bench_tbl = make_cluster.load(a.benches_table) if a.benches_table and os.path.isfile(a.benches_table) else {}
        if not a.furniture and fo4_plugins:
            raw_fo4_furn = _raw_fo4_furn_bases(refs, fo4_plugins)

    doc = promote(
        refs,
        placed,
        make_cluster.load(a.containers_table),
        make_cluster.load(a.items_table),
        make_cluster.load_names(a.names) if a.names else None,
        sf,
        make_cluster.load(a.furniture)["furniture"] if a.furniture else None,
        mesh,
        prefix=edid_prefix,
        fo4_loot=a.fo4_loot,
        loot_index=loot_index,
        manifest_models=manifest_models,
        explicit_loot_map=explicit_loot_map,
        usable_beds_benches=a.usable_beds_benches,
        bench_table=bench_tbl,
        raw_fo4_furn=raw_fo4_furn,
    )
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    if a.fo4_loot and a.loot_fallbacks_out:
        os.makedirs(os.path.dirname(os.path.abspath(a.loot_fallbacks_out)), exist_ok=True)
        with open(a.loot_fallbacks_out, "w", encoding="utf-8") as f:
            json.dump(doc["report"]["fo4_loot"], f, indent=1)
    summary_kinds = list(KINDS) + (["benches"] if a.usable_beds_benches else [])
    print(f"wrote {a.out}: " + ", ".join(f"{len(doc[k])} {k}" for k in summary_kinds) + f" from {len(a.exports)} cell exports")
    if a.fo4_loot:
        lr = doc["report"]["fo4_loot"]
        print(
            f"fo4_loot: {lr['containers_fo4_resolved']}/{lr['containers_total']} containers populated from FO4 CNTO/LVLI "
            f"({lr['containers_non_credit_loot']} non-credit, {lr['loot_item_bases']} converted loot base(s)); "
            f"{lr['fallback_count']} fallback(s) logged"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
