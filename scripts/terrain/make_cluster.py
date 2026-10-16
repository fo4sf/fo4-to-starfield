"""make_cluster.py: the Commonwealth-wide promotion lists for make_core64c.py stage --cluster (docs/terrain/commonwealth-build-plan.md
section 3). R05 slice 1 promoted one hand-written reference (scripts/terrain/clusters/r05_medkit.json); this reads the band
exports (dotnet/Fo4Land export-exterior: every reference carries its FO4 base type) and core64c's objects.json (the references
the build placed) and writes, per class, every placed reference of that class with a name and a vanilla inventory from a
table, so the same promotion path runs over all 1,708 cells.

  report     --work <work> --build <core64c staging>                     counts of placed references by FO4 base type
  containers --work <work> --build <core64c staging> --table <json> --out <cluster.json> [--limit N] [--only-known]
  items      --work <work> --build <core64c staging> --table <json> --out <cluster.json> [--limit N] [--only-known]
  lights     --work <work> --fo4 <Fallout4.esm> --out <cluster.json> [--limit N] [--lumens-per-m2 K]
             every exported Light reference (core64c never placed one: no slot) with its FO4 LIGH base read from
             Fallout4.esm and mapped to Starfield light fields (src/fo4sf/fo4light.py, docs/terrain/exterior-lights.md)

The table (scripts/terrain/clusters/container_table.json): {"default": {"name": ..., "items": [...]}, "by_editor_id": {<FO4 base
editor id or prefix*>: {"name", "items"}}}. Items are vanilla Starfield forms (<plugin>:<6 hex>, count >= 1), as
make_core64c.cluster_containers requires; FO4's leveled lists do not resolve, so the table is a content decision of the owner.
Only references the build placed (objects.json refs by source key) are listed: a reference core64c skipped has no slot.
"""
import argparse
import glob
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
from fo4sf import fo4light  # noqa: E402

CONTAINER_TYPES = ("Container",)                      # Mutagen type names in the export's "type"
ITEM_TYPES = ("MiscItem", "Ingestible")               # loose items: MISC in Starfield (ALCH as MISC in the first pass)
LIGHT_TYPES = ("Light",)
FO4_MASTER = "fallout4.esm"                           # light bases and references are read from Fallout4.esm itself


def load(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def band_refs(work):
    """Every exported reference of every band (type, formkey, base_editor_id, base_formkey, model), in band order."""
    paths = sorted(glob.glob(os.path.join(work, "export", "band_*.json")))
    if not paths:
        raise FileNotFoundError(f"no export bands under {work}")
    for p in paths:
        b = load(p)
        for r in b.get("refs", []):
            yield r


def placed_sources(build):
    """The source keys core64c placed (objects.json refs), in placement order."""
    o = load(os.path.join(build, "objects.json"))
    return [r["src"] for r in o["refs"]]


def by_type(refs, placed):
    """Counter of FO4 base type over the placed references (export type names), and over all exported ones."""
    placed_set = set(placed)
    all_c, placed_c = Counter(), Counter()
    for r in refs:
        t = str(r.get("type") or "?")
        all_c[t] += 1
        if r.get("formkey") in placed_set:
            placed_c[t] += 1
    return all_c, placed_c


def table_entry(table, editor_id):
    """The table's entry for a FO4 base editor id: exact, then the longest "prefix*" match, then default (None if none)."""
    by = table.get("by_editor_id") or {}
    if editor_id in by:
        return by[editor_id], "exact"
    best = None
    for k, v in by.items():
        if k.endswith("*") and editor_id.startswith(k[:-1]) and (best is None or len(k) > len(best[0])):
            best = (k, v)
    if best:
        return best[1], "prefix"
    if table.get("default"):
        return table["default"], "default"
    return None, "none"


def humanize(editor_id):
    """A readable name from a FO4 editor id: "Loot_Prewar_Medkit" -> "Loot Prewar Medkit"."""
    s = editor_id.replace("_", " ")
    out = []
    for i, ch in enumerate(s):
        if ch.isupper() and i and s[i - 1].islower():
            out.append(" ")
        out.append(ch)
    return " ".join("".join(out).split())


def containers(refs, placed, table, limit=0, only_known=False):
    """({"containers": [...]}, report) for every placed reference whose FO4 base is a Container, in placement order:
    src, name (the table's or the humanized editor id), items (the table's), base (FO4 base formkey), editor_id."""
    order = {src: i for i, src in enumerate(placed)}
    entries, rep = [], Counter()
    for r in refs:
        if str(r.get("type")) not in CONTAINER_TYPES:
            continue
        src = r.get("formkey")
        if src not in order:
            rep["not placed"] += 1
            continue
        if r.get("disabled") not in (0, "0", False, None):
            rep["initially disabled"] += 1
            continue
        edid = str(r.get("base_editor_id") or "")
        entry, how = table_entry(table, edid)
        rep[f"table {how}"] += 1
        if entry is None or (only_known and how == "default"):
            rep["skipped (no table entry)" if entry is None else "skipped (default only)"] += 1
            continue
        entries.append({"src": src, "name": entry.get("name") or humanize(edid), "items": entry["items"],
                        "base": r.get("base_formkey"), "editor_id": edid, "slot": order[src]})
    entries.sort(key=lambda e: e["slot"])
    if limit:
        rep["cut by --limit"] = max(0, len(entries) - limit)
        entries = entries[:limit]
    rep["containers"] = len(entries)
    rep["distinct bases"] = len({e["base"] for e in entries})
    return {"note": "make_cluster.py containers: every placed Container reference of the core with the table's name and "
                    "vanilla inventory; read by make_core64c.py stage --cluster", "containers": entries}, dict(rep)


def items(refs, placed, table, limit=0, only_known=False):
    """({"items": [...]}, report) for every placed reference whose FO4 base is a MiscItem or Ingestible, in placement
    order: src, name (the table's or the humanized editor id), value and weight (the table's), base, editor_id, kind
    (the export's type), slot. The writer makes one MISC per FO4 base (as containers: #167) with the converted model."""
    order = {src: i for i, src in enumerate(placed)}
    entries, rep = [], Counter()
    for r in refs:
        kind = str(r.get("type"))
        if kind not in ITEM_TYPES:
            continue
        src = r.get("formkey")
        if src not in order:
            rep["not placed"] += 1
            continue
        if r.get("disabled") not in (0, "0", False, None):
            rep["initially disabled"] += 1
            continue
        edid = str(r.get("base_editor_id") or "")
        entry, how = table_entry(table, edid)
        rep[f"table {how}"] += 1
        if entry is None or (only_known and how == "default"):
            rep["skipped (no table entry)" if entry is None else "skipped (default only)"] += 1
            continue
        entries.append({"src": src, "name": entry.get("name") or humanize(edid), "value": int(entry.get("value", 0)),
                        "weight": float(entry.get("weight", 0.0)), "base": r.get("base_formkey"), "editor_id": edid,
                        "kind": kind, "slot": order[src]})
        rep[kind] += 1
    entries.sort(key=lambda e: e["slot"])
    if limit:
        rep["cut by --limit"] = max(0, len(entries) - limit)
        entries = entries[:limit]
    rep["items"] = len(entries)
    rep["distinct bases"] = len({e["base"] for e in entries})
    return {"note": "make_cluster.py items: every placed MiscItem / Ingestible reference of the core with the table's name, "
                    "value and weight; read by make_core64c.py stage --cluster (items: one MISC per FO4 base)", "items": entries}, dict(rep)


def fo4_local_id(formkey):
    """'08ADFA:Fallout4.esm' -> 0x08ADFA (a Fallout4.esm record's id inside Fallout4.esm), else None."""
    local, _, plugin = str(formkey or "").partition(":")
    if plugin.lower() != FO4_MASTER:
        return None
    try:
        return int(local, 16)
    except ValueError:
        return None


def light_refs(refs):
    """The exported references whose FO4 base is a Light."""
    return [r for r in refs if str(r.get("type")) in LIGHT_TYPES]


def read_light_sources(fo4_esm, refs, world="Commonwealth"):
    """(bases {local id: fo4light.parse_ligh}, references {local id: fo4light.parse_light_ref}) for the given light
    references, read from Fallout4.esm (raw records: the band exports carry no light data)."""
    from fo4sf import fo4land
    base_ids = {i for i in (fo4_local_id(r.get("base_formkey")) for r in refs) if i is not None}
    ref_ids = {i for i in (fo4_local_id(r.get("formkey")) for r in refs) if i is not None}
    with fo4land.Plugin(fo4_esm) as p:
        return fo4light.read_bases(p, base_ids), fo4light.read_refs(p, world, ref_ids)


def lights(refs, bases, ref_fields, limit=0, lumens_per_m2=fo4light.LUMENS_PER_M2):
    """({"light_bases": {FO4 base formkey: Starfield light fields}, "lights": [...]}, report) for every exported Light
    reference, in FO4 source key order (as exterior.place orders the statics). Each light: src, base (FO4 base formkey),
    editor_id, fo4_pos (FO4 units, as exported), rot, scale, disabled, radius_delta (metres), lighting (XLIG) and
    record_flags (its FO4 header's DoesNotLightWater / NeverFades / DoesNotLightLandscape bits) from the reference
    itself. Core64c never placed a light (exterior.TYPE_REASONS), so a light owns no reference slot: make_core64c.py
    stage gives it a new REFR after every reserved one. bases / ref_fields: read_light_sources."""
    entries, out_bases, rep = [], {}, Counter()
    dropped = Counter()
    found = []
    for r in sorted(light_refs(refs), key=lambda r: str(r.get("formkey"))):
        src, bkey = r.get("formkey"), r.get("base_formkey")
        bid, rid = fo4_local_id(bkey), fo4_local_id(src)
        if bid is None or rid is None:
            rep["skipped (not a Fallout4.esm light)"] += 1
            continue
        b, rf = bases.get(bid), ref_fields.get(rid)
        if b is None or rf is None:
            rep["skipped (not found in Fallout4.esm)"] += 1
            continue
        found.append((r, b, rf))
    # every reference of a base (before --limit) sets the base's scale: the median of their own intensities
    per_base = {}
    for r, b, rf in found:
        per_base.setdefault(r["base_formkey"], []).append(fo4light.ref_intensity(rf, b))
    scales = {k: fo4light.base_scale(v) for k, v in per_base.items()}
    for r, b, rf in found:
        src, bkey = r["formkey"], r["base_formkey"]
        sf, why, lost = fo4light.map_base(b, lumens_per_m2, scales[bkey])
        if sf is None:
            rep[f"skipped ({why})"] += 1
            continue
        if bkey not in out_bases:
            out_bases[bkey] = dict(sf, editor_id=b["edid"], intensity_scale=round(scales[bkey], 6), dropped=lost)
        for f in lost:
            dropped[f] += 1
        mr = fo4light.map_ref(rf, b, scales[bkey])
        rep["fade clamped to the vanilla XLIG range"] += mr["fade_clamped"]
        rep["with radius delta (XRDS)"] += mr["radius_delta"] is not None
        rep["with XLIG"] += mr["lighting"] is not None
        for bit, name in ((fo4light.REF_DOES_NOT_LIGHT_WATER, "does not light water"), (fo4light.REF_NEVER_FADES, "never fades"),
                          (fo4light.REF_DOES_NOT_LIGHT_LANDSCAPE, "does not light landscape")):
            rep[f"record flag {name} (0x{bit:X})"] += bool(mr["record_flags"] & bit)
        if rf.get("emittance"):
            rep["emittance (XEMI) not carried"] += 1
        if r.get("enable_parent"):
            rep["enable parent not translated"] += 1
        disabled = r.get("disabled") not in (0, "0", False, None)
        rep["initially disabled"] += disabled
        entries.append({"src": src, "base": bkey, "editor_id": b["edid"], "fo4_pos": [float(v) for v in r["pos"]],
                        "rot": [float(v) for v in r["rot"]], "scale": float(r.get("scale") or 1.0), "disabled": disabled,
                        "radius_delta": mr["radius_delta"], "lighting": mr["lighting"], "record_flags": mr["record_flags"]})
    if limit:
        rep["cut by --limit"] = max(0, len(entries) - limit)
        entries = entries[:limit]
        used = {e["base"] for e in entries}
        out_bases = {k: v for k, v in out_bases.items() if k in used}
    rep["lights"] = len(entries)
    rep["distinct bases"] = len(out_bases)
    rep["features not carried (references)"] = dict(dropped.most_common())
    return {"note": "make_cluster.py lights: every exported FO4 Light reference with its FO4 LIGH base mapped to Starfield "
                    "light fields (src/fo4sf/fo4light.py); read by make_core64c.py stage --cluster (one LIGH per FO4 base, "
                    "new REFR ids after every reserved one)", "lumens_per_m2": lumens_per_m2,
            "light_bases": out_bases, "lights": entries}, dict(rep)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("report")
    p.add_argument("--work", required=True)
    p.add_argument("--build", required=True)
    p = sub.add_parser("containers")
    p.add_argument("--work", required=True)
    p.add_argument("--build", required=True)
    p.add_argument("--table", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--limit", type=int, default=0, help="keep the first N (placement order): a slice before the whole core")
    p.add_argument("--only-known", action="store_true", help="skip references the table only covers by its default entry")
    p = sub.add_parser("items")
    p.add_argument("--work", required=True)
    p.add_argument("--build", required=True)
    p.add_argument("--table", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--only-known", action="store_true")
    p = sub.add_parser("lights")
    p.add_argument("--work", required=True)
    p.add_argument("--fo4", required=True, help="Fallout4.esm (light bases and the references' own light fields)")
    p.add_argument("--out", required=True)
    p.add_argument("--world", default="Commonwealth")
    p.add_argument("--limit", type=int, default=0, help="keep the first N (FO4 source key order)")
    p.add_argument("--lumens-per-m2", type=float, default=fo4light.LUMENS_PER_M2,
                   help="luminous power per square metre of radius at FO4 fade 1 (default: the vanilla exterior median)")
    a = ap.parse_args(argv)
    if a.cmd == "lights":
        refs = light_refs(band_refs(a.work))
        bases, ref_fields = read_light_sources(a.fo4, refs, a.world)
        cl, rep = lights(refs, bases, ref_fields, a.limit, a.lumens_per_m2)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(cl, f, indent=1)
        print(json.dumps(rep, indent=1))
        print(f"wrote {a.out}: {rep['lights']:,} lights over {rep['distinct bases']} LIGH bases")
        return 0
    placed = placed_sources(a.build)
    if a.cmd == "report":
        all_c, placed_c = by_type(band_refs(a.work), placed)
        print(f"placed {sum(placed_c.values()):,} of {sum(all_c.values()):,} exported references")
        for t, n in all_c.most_common():
            print(f"  {t:<18} exported {n:>8,}  placed {placed_c.get(t, 0):>8,}")
        return 0
    table = load(a.table)
    if a.cmd == "items":
        cl, rep = items(band_refs(a.work), placed, table, a.limit, a.only_known)
        key = "items"
    else:
        cl, rep = containers(band_refs(a.work), placed, table, a.limit, a.only_known)
        key = "containers"
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(cl, f, indent=1)
    print(json.dumps(rep, indent=1))
    print(f"wrote {a.out}: {rep[key]:,} {key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
