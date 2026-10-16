"""make_cluster.py: the Commonwealth-wide promotion lists for make_core64c.py stage --cluster (docs/terrain/commonwealth-build-plan.md
section 3). R05 slice 1 promoted one hand-written reference (scripts/terrain/clusters/r05_medkit.json); this reads the band
exports (dotnet/Fo4Land export-exterior: every reference carries its FO4 base type) and core64c's objects.json (the references
the build placed) and writes, per class, every placed reference of that class with a name and a vanilla inventory from a
table, so the same promotion path runs over all 1,708 cells.

  report     --work <work> --build <core64c staging>                     counts of placed references by FO4 base type
  containers --work <work> --build <core64c staging> --table <json> --out <cluster.json> [--limit N] [--only-known]
  items      --work <work> --build <core64c staging> --table <json> --out <cluster.json> [--limit N] [--only-known]
  activators --work <work> --build <core64c staging> --out <cluster.json> [--names <json>] [--table <json>] [--limit N]
  terminals  --work <work> --build <core64c staging> --out <cluster.json> [--names <json>] [--table <json>] [--limit N]
  lights     --work <work> --fo4 <Fallout4.esm> --out <cluster.json> [--limit N] [--lumens-per-m2 K]
             every exported Light reference (core64c never placed one: no slot) with its FO4 LIGH base read from
             Fallout4.esm and mapped to Starfield light fields (src/fo4sf/fo4light.py, docs/terrain/exterior-lights.md)
  workshops  --work <work> --build <core64c staging> --fo4 <Fallout4.esm> --out <cluster.json> [--limit N]
             every placed FO4 settlement workshop: a Container reference whose base carries the workshopscript VMAD
             script in Fallout4.esm (CONT WorkshopWorkbench 0C1AEB and WorkshopWorkbenchNonSettlement 246F86 in the
             core; docs/terrain/stations.md). One ACTI per FO4 base in the game, FULL WORKSHOP_NAME, build radius
             WORKSHOP_RADIUS_M. The container table must skip these bases (a source in two classes is refused).
  benches    --work <work> --build <core64c staging> --fo4 <Fallout4.esm> --table <json> --out <cluster.json> [--limit N]
             every placed FO4 crafting station: a Furniture reference whose base has a WBDT bench type in Fallout4.esm,
             with a kind from the table (scripts/terrain/clusters/bench_table.json: weapon / armor / chem / cooking ->
             the vanilla Starfield bench of BENCH_KINDS). Power armor stations (no Starfield bench type 8), kinds the
             table leaves null and bench types without a table entry are listed under "bench_skipped" with the reason.
  merge      --out <cluster.json> <cluster.json> ...
             one cluster file from several (a class key in two inputs is refused): stage --cluster takes one file

The table (scripts/terrain/clusters/container_table.json): {"default": {"name": ..., "items": [...]}, "by_editor_id": {<FO4 base
editor id or prefix*>: {"name", "items"}}}. Items are vanilla Starfield forms (<plugin>:<6 hex>, count >= 1), as
make_core64c.cluster_containers requires; FO4's leveled lists do not resolve, so the table is a content decision of the owner.
An entry {"skip": "<why>"} leaves the base out of the containers list (the settlement workshops: another class).
Only references the build placed (objects.json refs by source key) are listed: a reference core64c skipped has no slot.
A build that already promoted some classes still lists them: placed_sources rebuilds the unpromoted placement order from
every promoted entry's reference_index.

--names (activators, terminals): the FO4 display names, dotnet/Fo4Land export-names over Fallout4.esm ({"names": {<base
formkey>: {"type", "editor_id", "name"}}}). A name is the table's (when its entry names one), else the FO4 base's FULL,
else, for a base the names file lists without a FULL, none (an activator without a name: Fallout 4 shows it no
activation prompt; a terminal without one is called "Terminal"), else (no names file, or a base it does not list) the
humanized editor id.

activators / terminals (docs/terrain/commonwealth-build-plan.md section 3): every placed FO4 Activator / Terminal
reference, for make_core64c.py stage --cluster ("activators": one ACTI per FO4 base with the converted model and the
name; "terminals": one TERM per FO4 base with a TMLM whose single body text is TERMINAL_BODY). Activators that are pure
triggers or markers never reach the list: core64c places no reference without a model (exterior.classify: no_model,
editor_marker, effect, water), and a placed one without a model or with a marker model is left out here too. The
report's "excluded" lists every exported Activator the list leaves out by reason, then by editor-id pattern
(EXCLUDED_ACTIVATOR_PATTERNS) with counts and the commonest editor ids; reasons come from the build's skipped.json.
"""
import argparse
import fnmatch
import glob
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
from fo4sf import fo4light, fo4station  # noqa: E402

CONTAINER_TYPES = ("Container",)                      # Mutagen type names in the export's "type"
WORKSHOP_TYPES = ("Container",)                       # FO4's settlement workshop is a CONT with the workshopscript VMAD
WORKSHOP_SCRIPT = "workshopscript"                    # (Fallout4.esm CONT 0C1AEB WorkshopWorkbench, 246F86 NonSettlement)
WORKSHOP_NAME = "Workshop"                            # the ACTI's FULL in Starfield (docs/terrain/stations.md)
WORKSHOP_RADIUS_M = 250.0                             # PRPS OutpostBuildAreaRadius: vanilla OutpostPlayerHouseActivator's 250
WORKSHOP_KEYWORD = 0x054BA7                           # KYWD WorkshopKeyword, the same id in Fallout4.esm and Starfield.esm
BENCH_TYPES = ("Furniture",)                          # a crafting station is a FURN with a WBDT bench type
# kind -> the vanilla Starfield bench of that kind (docs/terrain/stations.md: the same WBDT bench type and, armor / chem /
# cooking, the same recipe keyword id as FO4's bench; weapons recipes name Starfield-only WorkbenchWeaponKeyword 2CE1C0)
BENCH_KINDS = {"weapon": {"vanilla": "2B6A63:Starfield.esm", "wbdt": 2, "name": "Weapon Workbench"},
               "armor": {"vanilla": "2B6A62:Starfield.esm", "wbdt": 7, "name": "Spacesuit Workbench"},
               "chem": {"vanilla": "2B6A61:Starfield.esm", "wbdt": 5, "name": "Pharmaceutical Lab"},
               "cooking": {"vanilla": "2B6A65:Starfield.esm", "wbdt": 5, "name": "Cooking Station"}}
WBDT_NAMES = {0: "none", 1: "create object", 2: "weapons", 3: "enchanting", 4: "enchanting experiment", 5: "alchemy",
              6: "alchemy experiment", 7: "armor", 8: "power armor", 9: "robot mod", 11: "research"}
ITEM_TYPES = ("MiscItem", "Ingestible")               # loose items: MISC in Starfield (ALCH as MISC in the first pass)
ACTIVATOR_TYPES = ("Activator",)                      # ACTI in Starfield
TERMINAL_TYPES = ("Terminal",)                        # TERM (+ one TMLM menu) in Starfield
TERMINAL_BODY = "FO4 terminal (text not ported yet)"  # the single body line of every promoted terminal's menu
MARKER_RE = re.compile(r"marker", re.I)               # as src/fo4sf/exterior.MARKER_RE: an editor-marker model

# The report's grouping of the activators the list leaves out (first match wins; case-insensitive fnmatch on the FO4
# base editor id). Over core64c's export (2026-10-16) the no-model / marker-model ones are trigger volumes, package and
# sandbox primitives, comment markers, platform helpers, dummies, zones and the elevator / lift "master" markers.
EXCLUDED_ACTIVATOR_PATTERNS = (
    ("trigger volume", ("*Trigger*", "*Trig")),
    ("package / sandbox primitive", ("*Primitive*",)),
    ("editor / comment marker", ("*Marker*",)),
    ("platform / rotate helper", ("*Helper*",)),
    ("dummy", ("*Dummy*",)),
    ("zone / area", ("*Zone", "*Area", "*Turf")),
    ("master (elevator, lift, breaker)", ("*Master",)),
    ("water plane", ("*Water*",)),
    ("default / music activator", ("Default*Activator", "*MusicActivator")),
)

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


PROMOTED_KEYS = ("containers", "items", "activators", "terminals", "workshops", "benches")   # objects.json classes make_core64c promotes


def placed_sources(build):
    """The source keys core64c placed, in placement order: objects.json refs, with every promoted entry (containers,
    items, activators, terminals, workshops, benches) back in its reference_index slot (the order stage placed them
    in before --cluster)."""
    o = load(os.path.join(build, "objects.json"))
    order = [r["src"] for r in o["refs"]]
    for i, src in sorted((e["reference_index"], e["src"]) for k in PROMOTED_KEYS for e in (o.get(k) or [])):
        order.insert(i, src)
    return order


def load_names(path):
    """{FO4 base formkey: name or None} from dotnet/Fo4Land export-names (None: the base has no FULL); {} without a path."""
    if not path:
        return {}
    return {k: v.get("name") for k, v in load(path)["names"].items()}


def skipped_reasons(build):
    """{source key: reason} of the references the build skipped (its skipped.json), {} when there is none."""
    p = os.path.join(build, "skipped.json")
    if not os.path.isfile(p):
        return {}
    return {r.get("formkey"): r.get("reason") for r in load(p).get("refs", [])}


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


def display_name(table_name, edid, base, names, missing=None):
    """(name, source) of a promoted entry: the table's name, else the FO4 FULL from --names, else `missing` for a base
    --names lists without a FULL (None: no name), else the humanized editor id."""
    if table_name:
        return table_name, "table"
    if base in names:
        return (names[base], "fo4") if names[base] else (missing, "fo4 (no name)")
    return humanize(edid), "editor id"


def excluded_pattern(edid):
    """The EXCLUDED_ACTIVATOR_PATTERNS label of an editor id, "other" when none matches."""
    for label, globs in EXCLUDED_ACTIVATOR_PATTERNS:
        if any(fnmatch.fnmatchcase(edid.casefold(), g.casefold()) for g in globs):
            return label
    return "other"


def excluded_report(left_out, top=6):
    """{reason: {"refs", "patterns": {label: {"refs", "editor_ids": {edid: n} (the commonest `top`)}}}} of the
    (reason, editor id) pairs left out, reasons sorted, patterns by count."""
    out = {}
    for reason in sorted({r for r, _e in left_out}):
        edids = Counter(e for r, e in left_out if r == reason)
        pats = {}
        for e, n in edids.items():
            pats.setdefault(excluded_pattern(e), Counter())[e] += n
        out[reason] = {"refs": sum(edids.values()), "patterns": {
            label: {"refs": sum(c.values()), "editor_ids": dict(c.most_common(top))}
            for label, c in sorted(pats.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))}}
    return out


def left_out_reason(r, order, skipped):
    """Why a placed-class entry leaves an exported reference out, or None: not placed (the build's skipped.json reason
    when known), initially disabled, placed without a model / with a marker model."""
    src, model = r.get("formkey"), str(r.get("model") or "")
    if src not in order:
        return skipped.get(src) or ("no_model" if not model else "not placed")
    if r.get("disabled") not in (0, "0", False, None):
        return "initially disabled"
    if not model or MARKER_RE.search(model):
        return "placed without a model / with a marker model"
    return None


def promoted_class(refs, placed, types, what, table=None, names=None, skipped=None, limit=0, missing_name=None,
                   extra=None):
    """(entries, report, left_out) for every placed reference whose FO4 base type is in `types`, in placement order:
    src, name (display_name), name_from, base, editor_id, slot (+ `extra`). Left out, as (reason, editor id): not
    placed (the build's skipped.json reason when known), initially disabled, placed without a model / with a marker
    model."""
    order = {src: i for i, src in enumerate(placed)}
    names, skipped = names or {}, skipped or {}
    entries, rep, left_out = [], Counter(), []
    for r in refs:
        if str(r.get("type")) not in types:
            continue
        src, edid = r.get("formkey"), str(r.get("base_editor_id") or "")
        why = left_out_reason(r, order, skipped)
        if why:
            rep[f"left out: {why}"] += 1
            left_out.append((why, edid))
            continue
        entry = (table_entry(table, edid)[0] if table else None) or {}
        name, how = display_name(entry.get("name"), edid, r.get("base_formkey"), names, missing_name)
        rep[f"name from {how}"] += 1
        e = {"src": src, "name": name, "name_from": how, "base": r.get("base_formkey"), "editor_id": edid,
             "slot": order[src]}
        e.update(extra or {})
        entries.append(e)
    entries.sort(key=lambda e: e["slot"])
    if limit:
        rep["cut by --limit"] = max(0, len(entries) - limit)
        entries = entries[:limit]
    rep[what] = len(entries)
    rep["distinct bases"] = len({e["base"] for e in entries})
    return entries, dict(rep), left_out


def activators(refs, placed, table=None, names=None, skipped=None, limit=0):
    """({"activators": [...], "excluded": ...}, report): every placed FO4 Activator reference with a model, in placement
    order (promoted_class; name None for a base --names lists without a FULL), and the exported ones left out
    (excluded_report). The writer makes one ACTI per FO4 base with the converted model and the name."""
    entries, rep, left_out = promoted_class(refs, placed, ACTIVATOR_TYPES, "activators", table, names, skipped, limit)
    excl = excluded_report(left_out)
    return {"note": "make_cluster.py activators: every placed FO4 Activator reference of the core with its name; read by "
                    "make_core64c.py stage --cluster (one ACTI per FO4 base with the converted model)",
            "activators": entries, "excluded": excl}, rep


def terminals(refs, placed, table=None, names=None, skipped=None, limit=0):
    """({"terminals": [...], "excluded": ...}, report): every placed FO4 Terminal reference with a model, in placement
    order, with its name (promoted_class; "Terminal" for a base --names lists without a FULL) and the single menu body
    line TERMINAL_BODY. The writer makes one TERM per FO4 base with the converted model and one TMLM with that line."""
    entries, rep, left_out = promoted_class(refs, placed, TERMINAL_TYPES, "terminals", table, names, skipped, limit,
                                            missing_name="Terminal", extra={"body": TERMINAL_BODY})
    excl = excluded_report(left_out)
    return {"note": "make_cluster.py terminals: every placed FO4 Terminal reference of the core with its name and a "
                    "one-line menu body (the FO4 text is not ported yet); read by make_core64c.py stage --cluster (one "
                    "TERM + TMLM per FO4 base with the converted model)", "terminals": entries, "excluded": excl}, rep


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
        if entry.get("skip"):                                 # another class owns the base (the settlement workshops)
            rep[f"skipped by the table ({entry['skip']})"] += 1
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


def station_bases(fo4_esm, refs):
    """{FO4 base local id: fo4station.parse_base} for every Container / Furniture reference's base, read raw from
    Fallout4.esm (the exports carry no script, keyword or bench type). Bases of other plugins are not read."""
    ids = {fo4_local_id(r.get("base_formkey")) for r in refs if str(r.get("type")) in WORKSHOP_TYPES + BENCH_TYPES}
    return fo4station.read_bases(fo4_esm, ids - {None}, ("CONT", "FURN"))


def workshops(refs, placed, bases, skipped=None, limit=0):
    """({"workshops": [...], "excluded": ...}, report): every placed FO4 Container reference whose base carries the
    workshopscript VMAD script (bases: station_bases), in placement order: src, name (WORKSHOP_NAME), base, editor_id,
    radius (WORKSHOP_RADIUS_M, metres), slot. Other containers are counted; the exported workshops left out are listed
    by reason (excluded_report). The writer makes one ACTI per FO4 base with the converted workbench model."""
    order = {src: i for i, src in enumerate(placed)}
    skipped = skipped or {}
    entries, rep, left_out = [], Counter(), []
    for r in refs:
        if str(r.get("type")) not in WORKSHOP_TYPES:
            continue
        b = bases.get(fo4_local_id(r.get("base_formkey")))
        if b is None:
            rep["container base not in Fallout4.esm"] += 1
            continue
        if "scripts_error" in b:
            rep[f"container base with an unreadable VMAD ({b['scripts_error']})"] += 1
            continue
        if not fo4station.has_script(b, WORKSHOP_SCRIPT):
            rep["containers without the workshop script"] += 1
            continue
        src, edid = r.get("formkey"), str(r.get("base_editor_id") or "")
        rep["with WorkshopKeyword in the FO4 KWDA"] += WORKSHOP_KEYWORD in (b.get("keywords") or [])
        why = left_out_reason(r, order, skipped)
        if why:
            rep[f"left out: {why}"] += 1
            left_out.append((why, edid))
            continue
        entries.append({"src": src, "name": WORKSHOP_NAME, "base": r.get("base_formkey"), "editor_id": edid,
                        "radius": WORKSHOP_RADIUS_M, "slot": order[src]})
    entries.sort(key=lambda e: e["slot"])
    if limit:
        rep["cut by --limit"] = max(0, len(entries) - limit)
        entries = entries[:limit]
    rep["workshops"] = len(entries)
    rep["distinct bases"] = len({e["base"] for e in entries})
    return {"note": "make_cluster.py workshops: every placed FO4 settlement workshop (Container with the workshopscript "
                    "VMAD in Fallout4.esm); read by make_core64c.py stage --cluster (one ACTI per FO4 base, WorkshopKeyword + "
                    "the OutpostCategory keywords of OutpostPlayerHouseActivator, PRPS OutpostBuildAreaRadius)",
            "workshops": entries, "excluded": excluded_report(left_out)}, rep


def bench_reason(edid, wbdt, table):
    """(kind, reason) for a FO4 crafting station: the table's kind for the editor id when it names one of BENCH_KINDS
    with the base's WBDT bench type, else None and why (no table entry, a kind the table leaves null with its reason,
    an unknown kind, a kind whose bench type is not the base's)."""
    entry, _how = table_entry(table, edid)
    what = f"FO4 bench type {wbdt} ({WBDT_NAMES.get(wbdt, '?')})"
    if entry is None:
        return None, f"unknown kind: no table entry for {edid} ({what})"
    kind = entry.get("kind")
    if kind is None:
        return None, f"{entry.get('reason') or 'left out by the table'} ({what})"
    if kind not in BENCH_KINDS:
        return None, f"unknown kind {kind!r} in the table ({what})"
    if BENCH_KINDS[kind]["wbdt"] != wbdt:
        return None, (f"table kind {kind} (bench type {BENCH_KINDS[kind]['wbdt']}) disagrees with the base's {what}")
    return kind, None


def benches(refs, placed, bases, table, skipped=None, limit=0):
    """({"kinds": ..., "benches": [...], "bench_skipped": [...], "excluded": ...}, report): every placed FO4 Furniture
    reference whose base has a WBDT bench type (bases: station_bases) and a kind from the table (bench_reason), in
    placement order: src, kind, vanilla (the Starfield bench of that kind), base, editor_id, wbdt, slot. Furniture
    without a bench type is counted; a crafting station without a kind is listed in bench_skipped with its reason
    (power armor, unknown kinds); placed ones left out are in excluded. The writer binds the REFR to the vanilla FURN."""
    order = {src: i for i, src in enumerate(placed)}
    skipped = skipped or {}
    entries, rep, left_out, bench_skipped = [], Counter(), [], []
    for r in refs:
        if str(r.get("type")) not in BENCH_TYPES:
            continue
        b = bases.get(fo4_local_id(r.get("base_formkey")))
        if b is None:
            rep["furniture base not in Fallout4.esm"] += 1
            continue
        wbdt = b.get("wbdt") or 0
        if wbdt == 0:
            rep["furniture that is no crafting station (WBDT 0)"] += 1
            continue
        src, edid = r.get("formkey"), str(r.get("base_editor_id") or "")
        kind, reason = bench_reason(edid, wbdt, table)
        if reason:
            rep[f"skipped: {reason.split(' (')[0]}"] += 1
            bench_skipped.append({"src": src, "base": r.get("base_formkey"), "editor_id": edid, "wbdt": wbdt, "reason": reason})
            continue
        why = left_out_reason(r, order, skipped)
        if why:
            rep[f"left out: {why}"] += 1
            left_out.append((why, edid))
            continue
        entries.append({"src": src, "kind": kind, "vanilla": BENCH_KINDS[kind]["vanilla"], "base": r.get("base_formkey"),
                        "editor_id": edid, "wbdt": wbdt, "slot": order[src]})
        rep[kind] += 1
    entries.sort(key=lambda e: e["slot"])
    if limit:
        rep["cut by --limit"] = max(0, len(entries) - limit)
        entries = entries[:limit]
    rep["benches"] = len(entries)
    rep["distinct bases"] = len({e["base"] for e in entries})
    rep["bench_skipped"] = len(bench_skipped)
    return {"note": "make_cluster.py benches: every placed FO4 crafting station (Furniture with a WBDT bench type in "
                    "Fallout4.esm) with a kind from the bench table; read by make_core64c.py stage --cluster (the REFR keeps "
                    "its slot on the vanilla Starfield bench of its kind, no record of our own)",
            "kinds": {k: v["vanilla"] for k, v in BENCH_KINDS.items()}, "benches": entries, "bench_skipped": bench_skipped,
            "excluded": excluded_report(left_out)}, rep


MERGE_KEYS = ("containers", "items", "activators", "terminals", "lights", "light_bases", "lumens_per_m2", "workshops",
              "benches")                              # what stage --cluster reads; reports (excluded, ...) are dropped


def merge(clusters):
    """One cluster for stage --cluster from several make_cluster outputs ({path or label: loaded json}): the MERGE_KEYS
    of each, a note naming the inputs. ValueError for a key present in two inputs (the lists are not concatenated:
    one generator run per class)."""
    out, owner = {"note": "make_cluster.py merge: " + " + ".join(str(k) for k in clusters)}, {}
    for label, c in clusters.items():
        for k in MERGE_KEYS:
            if k not in c:
                continue
            if k in owner:
                raise ValueError(f"{k!r} is in both {owner[k]} and {label}")
            owner[k] = label
            out[k] = c[k]
    return out


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
    for cmd in ("activators", "terminals"):
        p = sub.add_parser(cmd)
        p.add_argument("--work", required=True)
        p.add_argument("--build", required=True)
        p.add_argument("--out", required=True)
        p.add_argument("--names", default="", help="FO4 display names: dotnet/Fo4Land export-names over Fallout4.esm")
        p.add_argument("--table", default="", help="optional name overrides by FO4 base editor id (exact or prefix*)")
        p.add_argument("--limit", type=int, default=0)
    p = sub.add_parser("lights")
    p.add_argument("--work", required=True)
    p.add_argument("--fo4", required=True, help="Fallout4.esm (light bases and the references' own light fields)")
    p.add_argument("--out", required=True)
    p.add_argument("--world", default="Commonwealth")
    p.add_argument("--limit", type=int, default=0, help="keep the first N (FO4 source key order)")
    p.add_argument("--lumens-per-m2", type=float, default=fo4light.LUMENS_PER_M2,
                   help="luminous power per square metre of radius at FO4 fade 1 (default: the vanilla exterior median)")
    for cmd in ("workshops", "benches"):
        p = sub.add_parser(cmd)
        p.add_argument("--work", required=True)
        p.add_argument("--build", required=True)
        p.add_argument("--fo4", required=True, help="Fallout4.esm: the bases' VMAD scripts and WBDT bench types")
        p.add_argument("--out", required=True)
        p.add_argument("--limit", type=int, default=0)
        if cmd == "benches":
            p.add_argument("--table", required=True, help="scripts/terrain/clusters/bench_table.json: editor id -> kind")
    p = sub.add_parser("merge")
    p.add_argument("--out", required=True)
    p.add_argument("inputs", nargs="+", help="cluster files to merge (one class per input)")
    a = ap.parse_args(argv)
    if a.cmd == "merge":
        try:
            cl = merge({os.path.basename(p): load(p) for p in a.inputs})
        except ValueError as e:
            sys.exit(f"merge: {e}")
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(cl, f, indent=1)
        print(f"wrote {a.out}: " + ", ".join(f"{k} {len(v):,}" for k, v in cl.items() if isinstance(v, (list, dict))))
        return 0
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
    if a.cmd in ("workshops", "benches"):
        refs = [r for r in band_refs(a.work) if str(r.get("type")) in WORKSHOP_TYPES + BENCH_TYPES]
        bases = station_bases(a.fo4, refs)
        if a.cmd == "workshops":
            cl, rep = workshops(refs, placed, bases, skipped_reasons(a.build), a.limit)
        else:
            cl, rep = benches(refs, placed, bases, load(a.table), skipped_reasons(a.build), a.limit)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(cl, f, indent=1)
        print(json.dumps(rep, indent=1))
        for reason, v in cl["excluded"].items():
            print(f"left out, {reason}: {v['refs']:,}")
            for label, pat in v["patterns"].items():
                print(f"  {label:<34} {pat['refs']:>6,}  " + ", ".join(f"{e} {n}" for e, n in pat["editor_ids"].items()))
        print(f"wrote {a.out}: {rep[a.cmd]:,} {a.cmd} over {rep['distinct bases']:,} FO4 bases"
              + (f", {rep['bench_skipped']:,} crafting stations skipped (bench_skipped)" if a.cmd == "benches" else ""))
        return 0
    if a.cmd in ("activators", "terminals"):
        fn = activators if a.cmd == "activators" else terminals
        cl, rep = fn(band_refs(a.work), placed, load(a.table) if a.table else None, load_names(a.names),
                     skipped_reasons(a.build), a.limit)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(cl, f, indent=1)
        print(json.dumps(rep, indent=1))
        for reason, v in cl["excluded"].items():
            print(f"left out, {reason}: {v['refs']:,}")
            for label, pat in v["patterns"].items():
                print(f"  {label:<34} {pat['refs']:>6,}  " + ", ".join(f"{e} {n}" for e, n in pat["editor_ids"].items()))
        print(f"wrote {a.out}: {rep[a.cmd]:,} {a.cmd} over {rep['distinct bases']:,} FO4 bases")
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
