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

The table (scripts/terrain/clusters/container_table.json): {"default": {"name": ..., "items": [...]}, "by_editor_id": {<FO4 base
editor id or prefix*>: {"name", "items"}}}. Items are vanilla Starfield forms (<plugin>:<6 hex>, count >= 1), as
make_core64c.cluster_containers requires; FO4's leveled lists do not resolve, so the table is a content decision of the owner.
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

CONTAINER_TYPES = ("Container",)                      # Mutagen type names in the export's "type"
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


PROMOTED_KEYS = ("containers", "items", "activators", "terminals")   # objects.json classes make_core64c promotes


def placed_sources(build):
    """The source keys core64c placed, in placement order: objects.json refs, with every promoted entry (containers,
    items, activators, terminals) back in its reference_index slot (the order stage placed them in before --cluster)."""
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
        model = str(r.get("model") or "")
        if src not in order:
            why = skipped.get(src) or ("no_model" if not model else "not placed")
        elif r.get("disabled") not in (0, "0", False, None):
            why = "initially disabled"
        elif not model or MARKER_RE.search(model):
            why = "placed without a model / with a marker model"
        else:
            why = None
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
    a = ap.parse_args(argv)
    placed = placed_sources(a.build)
    if a.cmd == "report":
        all_c, placed_c = by_type(band_refs(a.work), placed)
        print(f"placed {sum(placed_c.values()):,} of {sum(all_c.values()):,} exported references")
        for t, n in all_c.most_common():
            print(f"  {t:<18} exported {n:>8,}  placed {placed_c.get(t, 0):>8,}")
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
