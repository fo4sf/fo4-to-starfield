"""make_cluster.py: the Commonwealth-wide promotion lists for make_core64c.py stage --cluster (docs/terrain/commonwealth-build-plan.md
section 3). R05 slice 1 promoted one hand-written reference (scripts/terrain/clusters/r05_medkit.json); this reads the band
exports (dotnet/Fo4Land export-exterior: every reference carries its FO4 base type) and core64c's objects.json (the references
the build placed) and writes, per class, every placed reference of that class with a name and a vanilla inventory from a
table, so the same promotion path runs over all 1,708 cells.

  report     --work <work> --build <core64c staging>                     counts of placed references by FO4 base type
  containers --work <work> --build <core64c staging> --table <json> --out <cluster.json> [--limit N] [--only-known]
  items      --work <work> --build <core64c staging> --table <json> --out <cluster.json> [--limit N] [--only-known]
  doors      --work <work> --build <core64c staging> --port <FO4Port staging> --exports <interior cell exports>
             --out <cluster.json> [--fo4 <Fallout4.esm> --fo4-data <FO4 Data>] [--only <src,...>] [--limit N]
             every exterior load door whose XTEL destination lies in a converted interior (docs/terrain/scripted-doors.md)

The table (scripts/terrain/clusters/container_table.json): {"default": {"name": ..., "items": [...]}, "by_editor_id": {<FO4 base
editor id or prefix*>: {"name", "items"}}}. Items are vanilla Starfield forms (<plugin>:<6 hex>, count >= 1), as
make_core64c.cluster_containers requires; FO4's leveled lists do not resolve, so the table is a content decision of the owner.
Only references the build placed (objects.json refs by source key) are listed: a reference core64c skipped has no slot.
"""
import argparse
import glob
import json
import os
import struct
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))

CONTAINER_TYPES = ("Container",)                      # Mutagen type names in the export's "type"
ITEM_TYPES = ("MiscItem", "Ingestible")               # loose items: MISC in Starfield (ALCH as MISC in the first pass)
DOOR_TYPES = ("Door",)
FO4_UNITS_PER_M = 70.0                                # core64: FO4 position / 70 = metres (docs/terrain/core64c.md)
PORT_PLUGIN = "FO4Port.esm"


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


# ------------------------------------------------------------------------------------------------------------- doors
def metres(v):
    return [round(float(x) / FO4_UNITS_PER_M, 5) for x in v]


def read_strings(data):
    """{string id: text} of a Bethesda .STRINGS file (count, data size, [id, offset] directory, then zstrings)."""
    count, _size = struct.unpack_from("<II", data, 0)
    base = 8 + count * 8
    out = {}
    for i in range(count):
        sid, off = struct.unpack_from("<II", data, 8 + i * 8)
        out[sid] = data[base + off:].split(b"\0", 1)[0].decode("cp1252", "replace")
    return out


def fo4_door_bases(fo4_esm, fo4_data, wanted):
    """{FO4 base id (int): {"name", "obnd" (metres, [lo, hi]), "fnam"}} of the DOOR records in `wanted`, read raw
    from Fallout4.esm (src/fo4sf/fo4land). Fallout4.esm is localized: FULL holds a string id resolved through
    Strings\\Fallout4_en.STRINGS of "Fallout4 - Interface.ba2" under fo4_data (name None when it cannot be read)."""
    from fo4sf import fo4land
    strings = None
    try:
        from fo4sf import ba2
        arc = ba2.Ba2(os.path.join(fo4_data, "Fallout4 - Interface.ba2"))
        strings = read_strings(arc.read("strings/fallout4_en.strings"))
    except (OSError, ValueError, KeyError, ImportError):
        strings = None
    out = {}
    with fo4land.Plugin(fo4_esm) as pl:
        localized = bool(struct.unpack_from("<I", pl.buf, 8)[0] & 0x80)
        grp = pl.top_group(b"DOOR")
        if grp is None:
            return out
        for item in fo4land.iter_items(pl.buf, grp[0], grp[1]):
            if item[0] == "GRUP" or item[3] not in wanted:
                continue
            typ, off, _flags, fid = item
            rec = {"name": None, "obnd": None, "fnam": None}
            for sig, d in fo4land.iter_subrecords(fo4land.record_data(pl.buf, off)):
                if sig == b"FULL" and len(d) >= 4:
                    if localized:
                        sid = struct.unpack_from("<I", d)[0]
                        rec["name"] = strings.get(sid) if strings else None
                    else:
                        rec["name"] = fo4land.zstring(d)
                elif sig == b"OBND" and len(d) >= 12:
                    b = struct.unpack_from("<6h", d)
                    rec["obnd"] = [metres(b[:3]), metres(b[3:])]
                elif sig == b"FNAM" and len(d) >= 1:
                    rec["fnam"] = d[0]
            out[fid] = rec
    return out


def interior_index(exports_dir):
    """The converted interiors' cell exports: {cell name: export}, and {door formkey (casefold): (cell name, ref)} over
    their placed refs (deferred refs are not in FO4Port.esm)."""
    cells, doors = {}, {}
    for p in sorted(glob.glob(os.path.join(exports_dir, "*.json"))):
        e = load(p)
        if not isinstance(e, dict) or "refs" not in e or "cell" not in e:
            continue
        cells[e["cell"]] = e
        for r in e["refs"]:
            if str(r.get("type")) in DOOR_TYPES:
                doors[str(r["formkey"]).casefold()] = (e["cell"], r)
    return cells, doors


def port_refrs(port_esm):
    """{local id (int): record type} of every record of FO4Port.esm (raw walk), so a formids.json key counts only
    when its REFR was written."""
    from fo4sf import fo4land
    out = {}
    with fo4land.Plugin(port_esm) as pl:
        def walk(start, end):
            for item in fo4land.iter_items(pl.buf, start, end):
                if item[0] == "GRUP":
                    walk(item[1] + 24, item[2])
                else:
                    out[item[3] & 0xFFFFFF] = item[0].decode("ascii", "replace")
        walk(pl.body, len(pl.buf))
    return out


def doors(refs, placed, skipped, bases, port_ids, port_recs, interiors, fo4_bases=None, only=None, limit=0):
    """({"doors": [...], "unplaced": [...]}, report): every exterior load door of the bands whose XTEL destination door
    is a placed reference of a converted interior export. A door is listed under "doors" (promotable) when both sides
    exist in the plugins: the exterior REFR is placed by the build (objects.json refs: `placed` = {src: slot}) and the
    interior REFR is in FO4Port.esm (formids.json "REFR:FO4Port_<cell>:<door>" and the record written); otherwise
    under "unplaced" with the reason (the editor-marker doors: the cave, the Vault 111 autoload doors).
    Entry: src, editor_id, base (FO4 base formkey), model (FO4), fo4_pos / rot / scale, pos (metres), exterior_cell,
    name (the FO4 base's FULL, else "Door"), obnd (the FO4 base's bounds in metres, or None), fnam, slot, core_base
    ({edid, model} of the converted STAT / DOOR the build placed), destination {door, cell, port_key, port_id (int),
    port_cell_id, plugin}, arrival_in (the exterior door's XTEL: pos / rot inside), arrival_out (the interior door's
    XTEL: pos / rot outside), xtel_flags {out, in}, reciprocal."""
    only_set = {s.casefold() for s in only} if only else None
    skip_by = {str(s.get("formkey", "")).casefold(): s for s in skipped}
    entries, unplaced, rep = [], [], Counter()
    for r in refs:
        if str(r.get("type")) not in DOOR_TYPES:
            continue
        td = r.get("teleport_destination")
        if not td or not td.get("door"):
            rep["doors without XTEL"] += 1
            continue
        rep["load doors"] += 1
        dest = str(td["door"])
        hit = interiors.get(dest.casefold())
        if hit is None:
            rep["destination not a converted interior"] += 1
            continue
        cell_name, iref = hit
        src = str(r["formkey"])
        if only_set is not None and src.casefold() not in only_set:
            rep["not in --only"] += 1
            continue
        base_key = str(r.get("base_formkey") or "")
        fb = (fo4_bases or {}).get(int(base_key.split(":")[0], 16)) if base_key else None
        ret = iref.get("teleport_destination") or {}
        port_key = next((k for k in port_ids if k.casefold() == f"REFR:FO4Port_{cell_name}:{dest}".casefold()), None)
        port_id = port_ids.get(port_key) if port_key else None
        entry = {"src": src, "editor_id": str(r.get("base_editor_id") or ""), "base": base_key,
                 "model": r.get("model") or "", "fo4_pos": list(r["pos"]), "rot": [float(v) for v in r["rot"]],
                 "scale": float(r.get("scale") or 1.0), "pos": metres(r["pos"]), "exterior_cell": r.get("exterior_cell"),
                 "name": (fb or {}).get("name") or "Door", "obnd": (fb or {}).get("obnd"), "fnam": (fb or {}).get("fnam"),
                 "disabled": bool(r.get("disabled")), "enable_parent": r.get("enable_parent"), "lock": r.get("lock_data"),
                 "slot": None, "core_base": None,
                 "destination": {"door": dest, "cell": cell_name, "port_key": port_key, "port_id": port_id,
                                 "port_cell_id": port_ids.get(f"CELL:FO4Port_{cell_name}"), "plugin": PORT_PLUGIN,
                                 "interior_base": iref.get("base_editor_id"), "interior_model": iref.get("model"),
                                 "interior_pos": metres(iref["pos"]), "interior_rot": [float(v) for v in iref["rot"]]},
                 "arrival_in": {"fo4_pos": list(td["pos"]), "pos": metres(td["pos"]), "rot": [float(v) for v in td["rot"]]},
                 "arrival_out": ({"fo4_pos": list(ret["pos"]), "pos": metres(ret["pos"]), "rot": [float(v) for v in ret["rot"]]}
                                 if ret.get("pos") else None),
                 "xtel_flags": {"out": td.get("flags"), "in": ret.get("flags")},
                 "reciprocal": bool(ret.get("door") and str(ret["door"]).casefold() == src.casefold())}
        reasons = []
        slot = placed.get(src)
        if slot is None:
            s = skip_by.get(src.casefold())
            reasons.append("exterior side not placed by the build" + (f": {s['reason']} ({s.get('detail')})" if s else ""))
        else:
            entry["slot"] = slot
            b = bases[slot] if isinstance(slot, int) and bases else None
            if b is not None:
                entry["core_base"] = b
        if port_id is None:
            reasons.append(f"interior side not in FO4Port.esm formids.json (REFR:FO4Port_{cell_name}:{dest})")
        elif port_recs is not None and port_recs.get(int(port_id)) != "REFR":
            reasons.append(f"interior side {port_key} = {int(port_id):06X} is not a REFR of FO4Port.esm")
        if entry["arrival_out"] is None:
            reasons.append("interior door has no XTEL back (no outside arrival)")
        if reasons:
            entry["reason"] = "; ".join(reasons)
            unplaced.append(entry)
            rep["unplaced"] += 1
            continue
        entries.append(entry)
    entries.sort(key=lambda e: e["slot"])
    if limit:
        rep["cut by --limit"] = max(0, len(entries) - limit)
        entries = entries[:limit]
    rep["doors"] = len(entries)
    rep["distinct bases"] = len({e["base"] for e in entries})
    rep["interiors"] = len({e["destination"]["cell"] for e in entries})
    return {"note": "make_cluster.py doors: every exterior load door of the core whose destination is a placed door of "
                    "a converted interior, with both arrival points; read by make_core64c.py stage --cluster (doors: "
                    "ACTI + FO4SF_LoadDoor VMAD + arrival marker) and make_port_doors.py (the interior side)",
            "doors": entries, "unplaced": unplaced}, dict(rep)


def build_bases(build):
    """{reference slot: {"edid", "model"}} of the base each placed reference of objects.json uses."""
    o = load(os.path.join(build, "objects.json"))
    bases = o["bases"]
    out = {}
    for i, r in enumerate(o["refs"]):
        b = bases[r["base"]]
        out[i] = {"edid": b["edid"], "model": b["model"], "door": "door" in b, "collision": b.get("collision")}
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
    p = sub.add_parser("doors")
    p.add_argument("--work", required=True)
    p.add_argument("--build", required=True, help="the core staging (objects.json, formids.json, skipped.json)")
    p.add_argument("--port", required=True, help="the interiors staging (FO4Port.esm, formids.json)")
    p.add_argument("--exports", required=True, help="the interior cell exports (<Cell>.json) FO4Port.esm was built from")
    p.add_argument("--out", required=True)
    p.add_argument("--fo4", default="", help="Fallout4.esm: the door bases' FULL name and bounds")
    p.add_argument("--fo4-data", default="", help="FO4 Data (Fallout4 - Interface.ba2: the localized FULL strings)")
    p.add_argument("--only", default="", help="comma-separated source keys to keep (e.g. 0EE661:Fallout4.esm)")
    p.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    placed = placed_sources(a.build)
    if a.cmd == "doors":
        order = {src: i for i, src in enumerate(placed)}
        skipped = load(os.path.join(a.build, "skipped.json")).get("refs", [])
        ids_path = os.path.join(a.build, "formids.json")
        core_ids = load(ids_path).get("refs", {}) if os.path.isfile(ids_path) else {}
        port_ids = load(os.path.join(a.port, "formids.json"))
        port_recs = port_refrs(os.path.join(a.port, PORT_PLUGIN)) if os.path.isfile(os.path.join(a.port, PORT_PLUGIN)) else None
        _cells, interiors = interior_index(a.exports)
        refs = list(band_refs(a.work))
        fo4_bases = None
        if a.fo4:
            wanted = {int(str(r.get("base_formkey", "0:x")).split(":")[0], 16) for r in refs
                      if str(r.get("type")) in DOOR_TYPES and r.get("base_formkey")}
            fo4_bases = fo4_door_bases(a.fo4, a.fo4_data, wanted)
        only = [s for s in a.only.split(",") if s.strip()] or None
        cl, rep = doors(refs, order, skipped, build_bases(a.build), port_ids, port_recs, interiors, fo4_bases, only, a.limit)
        for e in cl["doors"] + cl["unplaced"]:
            e["core_id"] = core_ids.get(e["src"])
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(cl, f, indent=1)
        print(json.dumps(rep, indent=1))
        for e in cl["doors"]:
            d = e["destination"]
            print(f"  {e['src']} {e['editor_id']} slot {e['slot']} ({e['core_id']}) -> {d['cell']} {d['door']} = "
                  f"{PORT_PLUGIN} {int(d['port_id']):06X}; out {e['arrival_out']['pos']} in {e['arrival_in']['pos']}")
        for e in cl["unplaced"]:
            print(f"  UNPLACED {e['src']} {e['editor_id']} -> {e['destination']['cell']}: {e['reason']}")
        print(f"wrote {a.out}: {rep['doors']} doors, {rep.get('unplaced', 0)} unplaced")
        return 0
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
