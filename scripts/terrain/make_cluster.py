"""make_cluster.py: the Commonwealth-wide promotion lists for make_core64c.py stage --cluster (docs/terrain/commonwealth-build-plan.md
section 3). R05 slice 1 promoted one hand-written reference (scripts/terrain/clusters/r05_medkit.json); this reads the band
exports (dotnet/Fo4Land export-exterior: every reference carries its FO4 base type) and core64c's objects.json (the references
the build placed) and writes, per class, every placed reference of that class with a name and a vanilla inventory from a
table, so the same promotion path runs over all 1,708 cells.

  report     --work <work> --build <core64c staging>                     counts of placed references by FO4 base type
  containers --work <work> --build <core64c staging> --table <json> --out <cluster.json> [--limit N] [--only-known]

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

CONTAINER_TYPES = ("Container",)                      # Mutagen type names in the export's "type"


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
    a = ap.parse_args(argv)
    placed = placed_sources(a.build)
    if a.cmd == "report":
        all_c, placed_c = by_type(band_refs(a.work), placed)
        print(f"placed {sum(placed_c.values()):,} of {sum(all_c.values()):,} exported references")
        for t, n in all_c.most_common():
            print(f"  {t:<18} exported {n:>8,}  placed {placed_c.get(t, 0):>8,}")
        return 0
    table = load(a.table)
    cl, rep = containers(band_refs(a.work), placed, table, a.limit, a.only_known)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(cl, f, indent=1)
    print(json.dumps(rep, indent=1))
    print(f"wrote {a.out}: {rep['containers']:,} containers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
