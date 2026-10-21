"""interior_census.py: every interior CELL of Fallout 4's plugins, how it is reached, and where it stands in the port
(docs/terrain/interior-batches.md).

  python scripts/terrain/interior_census.py --out <census.json> [--backlog docs/terrain/data/interior-backlog.json]
         [--port-cells <cell export dir or a text file of editor ids>] (repeatable) Fallout4.esm [DLCRobot.esm DLCworkshop01.esm ...]

interior_backlog.py measured the interiors an exterior load door of the Commonwealth core leads into, and the ones
behind them. This lists every interior cell the plugins hold (Fallout4.esm first, then the DLC in load order), read
raw with src/fo4sf/fo4land.py (no Mutagen, no load order), so the cells no Commonwealth door leads into are counted
too: the ones behind other worldspaces' doors (Diamond City, Goodneighbor, ...), the ones no load door leads into at
all (quest holding cells, editor test cells), and the DLC's own interiors.

Per interior cell: form key ("<6 hex>:<owner plugin>", as Mutagen and the exports write it; a DLC record that overrides a Fallout4.esm cell keeps the
Fallout4.esm key and lists both plugins; a later plugin's copy of a reference replaces the earlier one, and one flagged
Deleted (record flag 0x20) removes it, so the counts and door edges are the game's, as interior_content.py's), editor id, DATA flags, location (XLCN), encounter zone (XEZN: the ECZN's
level band and flags, the leveling the port folds into the cell's Starfield location), references by record type,
lights, navmeshes, distinct bases, load doors out (their destination: an interior form key or a worldspace editor id)
and in.
Reach, by breadth-first search over the load doors from every worldspace (a door leads from its own cell to the cell
its XTEL destination door stands in):
  worldspace       a worldspace's load door leads straight in (`entered_from` names the worldspaces)
  behind_interior  reached only through other interiors (`hop` = interiors passed through + 1)
  no_load_door     no load door anywhere leads in (scripted moves, holding cells, test cells; `test_name` flags the
                   editor ids that look like test or holding cells, a name pattern, not a judgment of the cell)
  closed           load doors lead in, but only from cells that are themselves never reached
Status: `in_port` (one of --port-cells), then interior_backlog's `backlog` (its rank) or `second_hop`, else `new`.
"""
import argparse
import json
import os
import re
import struct
import sys
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
from fo4sf import fo4land as fl  # noqa: E402

GROUP_TOP, GROUP_WORLD, GROUP_INT_BLOCK, GROUP_INT_SUB, GROUP_EXT_BLOCK, GROUP_EXT_SUB, GROUP_CELL = 0, 1, 2, 3, 4, 5, 6
GROUP_PERSISTENT, GROUP_TEMPORARY = 8, 9
CELL_INTERIOR = 0x0001
DELETED = 0x20                  # record flag "Deleted": every record's header (xEdit Core/wbInterface.pas IsDeleted)
# Placed-reference signatures (FO4): objects, actors and the projectile/hazard placements.
PLACED = (b"REFR", b"ACHR", b"PGRE", b"PMIS", b"PARW", b"PBAR", b"PBEA", b"PCON", b"PFLA", b"PHZD")
TEST_NAME = re.compile(r"^(zz|aaa|test|qa|debug|ctest|warehouse)|test(cell)?$|holding|packin|template|dummy|"
                       r"^cc[a-z]{3}fo4", re.I)
# ECZN DATA (Fallout 4): owner u32, location u32, rank u8, min level u8, flags u8, max level u8: the 12 bytes Mutagen
# writes for an EncounterZone (xEdit declares the levels itS8, but Mutagen's MinLevel/MaxLevel/Rank are Byte and
# Fo4Export emits them unsigned, so the census reads them the same way and a level of 255 is 255 here as in the export).
# The flags are the four the port carries over: NeverResets 1, MatchPcBelowMinimumLevel 2, DisableCombatBoundary 4,
# Workshop 8.
ECZN_DATA = struct.Struct("<IIBBBB")


def u32(d, o=0):
    return struct.unpack_from("<I", d, o)[0]


def zone_data(d):
    """{"owner", "location" (raw form ids), "rank", "min_level", "flags", "max_level"} of an ECZN DATA, or None when
    it is not the 12-byte layout above."""
    if len(d) < ECZN_DATA.size:
        return None
    owner, location, rank, lo, flags, hi = ECZN_DATA.unpack_from(d)
    return {"owner": owner, "location": location, "rank": rank, "min_level": lo, "flags": flags, "max_level": hi}


class Keys:
    """Form keys "<6 hex>:<owner plugin>" (Mutagen's, as the cell exports and interior-backlog.json) for the
    plugins in load order."""

    def __init__(self):
        self.names = []

    def add(self, name):
        self.names.append(name)

    def key(self, pi, masters, fid):
        mi = fid >> 24
        owner = masters[mi] if mi < len(masters) else self.names[pi]
        return "%06X:%s" % (fid & 0xFFFFFF, owner)


def read_plugin(path, pi, keys, out):
    """Walk one plugin: top-level record signatures (bases), every CELL (interior or worldspace) with its placed
    references, the WRLD editor ids, the LCTN editor ids and the ECZN level bands. Fills `out` (see census())."""
    name = os.path.basename(path)
    keys.add(name)
    with fl.Plugin(path) as p:
        buf = p.buf
        hdr = list(fl.iter_subrecords(fl.record_data(buf, 0)))
        masters = [fl.zstring(d) for s, d in hdr if s == b"MAST"]
        K = lambda fid: keys.key(pi, masters, fid)  # noqa: E731
        for item in fl.iter_items(buf, p.body, len(buf)):
            if item[0] != "GRUP":
                continue
            _g, off, end, label, _gt = item
            if label == b"CELL":
                walk_cells(buf, off + 24, end, None, K, name, out)
            elif label == b"WRLD":
                walk_worlds(buf, off + 24, end, K, name, out)
            else:
                for rec in fl.iter_items(buf, off + 24, end):
                    if rec[0] == "GRUP":
                        continue
                    typ, roff, _flags, fid = rec
                    out["bases"][K(fid)] = typ.decode("ascii")
                    if typ == b"LCTN":
                        for s, d in fl.iter_subrecords(fl.record_data(buf, roff)):
                            if s == b"EDID":
                                out["locations"][K(fid)] = fl.zstring(d)
                                break
                    elif typ == b"ECZN":
                        zone = {"editor_id": ""}
                        for s, d in fl.iter_subrecords(fl.record_data(buf, roff)):
                            if s == b"EDID":
                                zone["editor_id"] = fl.zstring(d)
                            elif s == b"DATA":
                                data = zone_data(d)
                                if data:
                                    data["owner"] = K(data["owner"]) if data["owner"] else None
                                    data["location"] = K(data["location"]) if data["location"] else None
                                    zone.update(data)
                        out["zones"][K(fid)] = zone                 # the last plugin's record wins, as the cell's


def walk_worlds(buf, start, end, K, plugin, out):
    world = None
    for item in fl.iter_items(buf, start, end):
        if item[0] == "GRUP":
            _g, off, gend, label, gtype = item
            if gtype == GROUP_WORLD and world is not None:
                walk_cells(buf, off + 24, gend, world, K, plugin, out)
            continue
        typ, off, _flags, fid = item
        if typ == b"WRLD":
            world = K(fid)
            eid = next((fl.zstring(d) for s, d in fl.iter_subrecords(fl.record_data(buf, off)) if s == b"EDID"), "")
            out["worlds"].setdefault(world, eid or world)


def walk_cells(buf, start, end, world, K, plugin, out):
    """CELL records and their children groups below `start`, interior (world None) or of one worldspace."""
    cell = None
    for item in fl.iter_items(buf, start, end):
        if item[0] == "GRUP":
            _g, off, gend, label, gtype = item
            if gtype in (GROUP_INT_BLOCK, GROUP_INT_SUB, GROUP_EXT_BLOCK, GROUP_EXT_SUB):
                walk_cells(buf, off + 24, gend, world, K, plugin, out)
            elif gtype == GROUP_CELL and cell is not None and K(u32(label)) == cell["formkey"]:
                read_children(buf, off + 24, gend, cell, K, out)
            continue
        typ, off, _flags, fid = item
        if typ != b"CELL":
            cell = None
            continue
        key = K(fid)
        fields = list(fl.iter_subrecords(fl.record_data(buf, off)))
        flags = next((struct.unpack_from("<H", d)[0] for s, d in fields if s == b"DATA" and len(d) >= 2), 0)
        interior = world is None and bool(flags & CELL_INTERIOR)
        if not interior:
            # A worldspace cell: only its load doors matter here (the place a door into an interior stands in).
            cell = out["ext"].setdefault(key, {"formkey": key, "world": world, "load_doors": [], "plugins": []})
            cell["plugins"].append(plugin)
            continue
        cell = out["cells"].get(key)
        if cell is None:
            cell = out["cells"][key] = {"formkey": key, "editor_id": "", "flags": 0, "location": None, "zone": None,
                                        "plugins": [], "placed": Counter(), "bases": Counter(), "navmeshes": 0,
                                        "load_doors": []}
        cell["plugins"].append(plugin)
        cell["flags"] = flags                                   # the last plugin's record wins, as in the game
        for s, d in fields:
            if s == b"EDID":
                cell["editor_id"] = fl.zstring(d)
            elif s == b"XLCN" and len(d) >= 4 and u32(d):
                cell["location"] = K(u32(d))
            elif s == b"XEZN" and len(d) >= 4 and u32(d):
                cell["zone"] = K(u32(d))


def read_children(buf, start, end, cell, K, out):
    for item in fl.iter_items(buf, start, end):
        if item[0] == "GRUP":
            read_children(buf, item[1] + 24, item[2], cell, K, out)
            continue
        typ, off, flags, fid = item
        if typ == b"NAVM":
            # Same rule as placed refs below: a later plugin's copy of a navmesh replaces the earlier one, and a copy
            # with the Deleted flag takes it back and adds nothing.
            navms = out.setdefault("navms", {})
            pcell = navms.pop(K(fid), None)
            if pcell is not None:
                pcell["navmeshes"] -= 1
            if "navmeshes" in cell and not flags & DELETED:
                cell["navmeshes"] += 1
                navms[K(fid)] = cell
            continue
        if typ not in PLACED:
            continue
        need_base = "placed" in cell                            # worldspace cells only keep their load doors
        ref = K(fid)
        # A later plugin's override of the same reference replaces the earlier one, as in the game, so a DLC that
        # edits a vanilla ref takes back what the earlier copy added instead of counting the ref twice; one it
        # re-saves with the Deleted record flag (0x20, Core/wbInterface.pas IsDeleted; interior_content.py's DELETED)
        # takes it back and adds nothing, not even a load door its XTEL still names (the record keeps no live data),
        # and is remembered as deleted so that a still later plugin's copy counts again.
        seen = out.setdefault("refs", {})
        prev = seen.pop(ref, None)
        if prev is not None:
            pcell, ptyp, pbase, pdoor = prev
            if "placed" in pcell:
                pcell["placed"][ptyp] -= 1
                if not pcell["placed"][ptyp]:
                    del pcell["placed"][ptyp]
                if pbase:
                    pcell["bases"][pbase] -= 1
                    if not pcell["bases"][pbase]:
                        del pcell["bases"][pbase]
            if pdoor:
                pcell["load_doors"] = [d for d in pcell["load_doors"] if d["ref"] != ref]
                out["door_cell"].pop(ref, None)
        if flags & DELETED:
            out.setdefault("deleted", set()).add(ref)
            continue
        out.get("deleted", set()).discard(ref)
        base, xtel = None, None
        for s, d in fl.iter_subrecords(fl.record_data(buf, off)):
            if s == b"NAME" and len(d) >= 4:
                base = K(u32(d))
            elif s == b"XTEL" and len(d) >= 4 and u32(d):
                xtel = K(u32(d))
        seen[ref] = (cell, typ.decode("ascii"), base if need_base else None, bool(xtel))
        if need_base:
            cell["placed"][typ.decode("ascii")] += 1
            if base:
                cell["bases"][base] += 1
        if xtel:
            cell["load_doors"].append({"ref": ref, "base": base, "destination_door": xtel})
            out["door_cell"][ref] = cell["formkey"]


def census(paths, port_cells=(), backlog=None):
    keys = Keys()
    out = {"bases": {}, "locations": {}, "zones": {}, "worlds": {}, "cells": {}, "ext": {}, "door_cell": {}}
    for pi, path in enumerate(paths):
        read_plugin(path, pi, keys, out)
    result = summarize(out, [os.path.basename(p) for p in paths], port_cells, backlog)
    result["totals"]["refs_deleted"] = len(out.get("deleted", ()))
    return result


def summarize(out, plugins, port_cells=(), backlog=None):
    cells, ext, door_cell = out["cells"], out["ext"], out["door_cell"]
    world_of = {k: c["world"] for k, c in ext.items()}

    def place(cell_key):
        """("interior", key) or ("world", world editor id) of the cell a door stands in; None when unknown."""
        if cell_key in cells:
            return ("interior", cell_key)
        if cell_key in world_of:
            return ("world", out["worlds"].get(world_of[cell_key], world_of[cell_key]))
        return None

    inbound = {k: [] for k in cells}
    for src_key, src in list(cells.items()) + list(ext.items()):
        here = place(src_key)
        for door in src["load_doors"]:
            dest_cell = door_cell.get(door["destination_door"])
            door["destination"] = place(dest_cell) if dest_cell else None
            if dest_cell in cells and dest_cell != src_key:
                inbound[dest_cell].append({"from": here, "door": door["ref"]})
    # breadth-first reach from every worldspace
    reach, queue = {}, deque()
    for k, ins in inbound.items():
        worlds = sorted({f["from"][1] for f in ins if f["from"] and f["from"][0] == "world"})
        if worlds:
            reach[k] = {"reach": "worldspace", "hop": 1, "entered_from": worlds}
            queue.append(k)
    while queue:
        k = queue.popleft()
        for door in cells[k]["load_doors"]:
            d = door.get("destination")
            if d and d[0] == "interior" and d[1] not in reach:
                reach[d[1]] = {"reach": "behind_interior", "hop": reach[k]["hop"] + 1, "entered_from": [k]}
                queue.append(d[1])
            elif d and d[0] == "interior" and reach[d[1]]["reach"] == "behind_interior" and \
                    reach[d[1]]["hop"] == reach[k]["hop"] + 1 and k not in reach[d[1]]["entered_from"]:
                reach[d[1]]["entered_from"].append(k)
    port = {e.casefold() for e in port_cells}
    locations = out.get("locations", {})
    zones = out.get("zones", {})

    def zone_row(key):
        """The cell's encounter zone as the port folds it: the ECZN's form key and editor id, its level band and
        flags, and the LCTN it names (which may be an exterior location, so it never stands in for the cell's own).
        None without XEZN; a zone the plugins do not hold keeps its form key and nothing else."""
        if not key:
            return None
        z = zones.get(key)
        if z is None:
            return {"formkey": key, "editor_id": None, "min_level": None, "max_level": None, "flags": None,
                    "rank": None, "location": None}
        return {"formkey": key, "editor_id": z.get("editor_id") or None, "min_level": z.get("min_level"),
                "max_level": z.get("max_level"), "flags": z.get("flags"), "rank": z.get("rank"),
                "location": locations.get(z.get("location"), z.get("location"))}
    bl = {}
    if backlog:
        for c in backlog.get("backlog", []):
            bl[c["formkey"]] = ("backlog", c.get("rank"))
        for c in backlog.get("second_hop", []):
            bl.setdefault(c["formkey"], ("second_hop", c.get("after_rank")))
        for c in backlog.get("converted", []):
            bl.setdefault(c["formkey"], ("converted_in_integ", None))
    rows = []
    for k, c in cells.items():
        r = reach.get(k)
        if r is None:
            r = {"reach": "closed" if inbound[k] else "no_load_door", "hop": None, "entered_from": []}
        if c["editor_id"].casefold() in port:
            status, rank = "in_port", None
        else:
            status, rank = bl.get(k, ("new", None))
            if status == "converted_in_integ":
                status = "new"                                  # converted in integ_1011 but not in this port
        placed = c["placed"]
        lights = sum(n for b, n in c["bases"].items() if out["bases"].get(b) == "LIGH")
        doors_out = []
        for d in c["load_doors"]:
            dest = d.get("destination")
            doors_out.append({"ref": d["ref"], "to": None if dest is None else
                              (cells[dest[1]]["editor_id"] or dest[1]) if dest[0] == "interior" else "world:" + dest[1]})
        rows.append({
            "formkey": k, "editor_id": c["editor_id"], "plugins": c["plugins"], "flags": c["flags"],
            "location": locations.get(c["location"], c["location"]), "encounter_zone": zone_row(c.get("zone")),
            "refs": sum(placed.values()), "placed": dict(sorted(placed.items())), "lights": lights,
            "navmeshes": c["navmeshes"], "distinct_bases": len(c["bases"]),
            "base_types": dict(sorted(Counter(out["bases"].get(b, "?") for b in c["bases"]).items())),
            "load_doors_out": doors_out,
            "load_doors_in": [{"from": f["from"][1] if f["from"] and f["from"][0] == "world" else
                               (cells[f["from"][1]]["editor_id"] if f["from"] else None), "door": f["door"]}
                              for f in inbound[k]],
            "reach": r["reach"], "hop": r["hop"], "entered_from": [
                e if r["reach"] == "worldspace" else (cells[e]["editor_id"] or e) for e in r["entered_from"]],
            "test_name": bool(TEST_NAME.search(c["editor_id"] or "")), "status": status, "backlog_rank": rank})
    rows.sort(key=lambda r: (r["formkey"].split(":")[1] != plugins[0], r["editor_id"].casefold(), r["formkey"]))
    totals = Counter()
    for r in rows:
        totals["interiors"] += 1
        totals[f"reach_{r['reach']}"] += 1
        totals[f"status_{r['status']}"] += 1
        totals[f"plugin_{r['formkey'].split(':')[1]}"] += 1
        if r["test_name"]:
            totals["test_name"] += 1
        if r["location"]:
            totals["with_location"] += 1
        if r["encounter_zone"]:
            totals["with_encounter_zone"] += 1
        if r["reach"] in ("worldspace", "behind_interior") and r["status"] == "new":
            totals["reached_new"] += 1
    missing_port = sorted(port - {r["editor_id"].casefold() for r in rows})
    if missing_port:
        raise ValueError(f"port cells not among the interiors: {missing_port}")
    return {"note": "scripts/terrain/interior_census.py: every interior CELL of the plugins (docs/terrain/interior-batches.md)",
            "plugins": plugins, "totals": dict(sorted(totals.items())), "worlds": out["worlds"], "cells": rows}


def port_cell_names(specs):
    """Editor ids from directories of cell exports (<EditorID>.json, the build's helper files left out) or text
    files (one per line)."""
    helpers = {"editorids", "formids", "lighting", "merged", "manifest", "promote", "teleports", "doors", "doors_check",
               "failure-summary", "build-state", "activation", "texture_log", "objects"}
    names = []
    for s in specs:
        if os.path.isdir(s):
            names += [n[:-5] for n in sorted(os.listdir(s)) if n.lower().endswith(".json") and n[:-5] not in helpers
                      and not n.startswith(("routes", "probe"))]
        else:
            with open(s, encoding="utf-8-sig") as f:
                names += [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    return names


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--backlog", default="")
    ap.add_argument("--port-cells", action="append", default=[])
    ap.add_argument("plugins", nargs="+")
    a = ap.parse_args(argv)
    if os.path.basename(a.plugins[0]).casefold() != "fallout4.esm":
        sys.exit("Fallout4.esm comes first")
    for p in a.plugins:
        if os.path.abspath(a.out) == os.path.abspath(p):
            sys.exit("--out is one of the plugins")
    backlog = None
    if a.backlog:
        with open(a.backlog, encoding="utf-8-sig") as f:
            backlog = json.load(f)
    result = census(a.plugins, port_cell_names(a.port_cells), backlog)
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    os.replace(tmp, a.out)
    print(json.dumps(result["totals"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
