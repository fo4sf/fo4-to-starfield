"""The census: read-only facts the planet probe and the plan rest on, from the user's own Starfield.esm and the
built-in Creations, printed at stage time on the PC (docs/planet/planet-probe.md section 4). Nothing is written to
the game.

What it reads:
  * the template star and planet (records.describe_star / describe_planet) and every star id in use (Starfield.esm
    and every other plugin in Data: the DLC, the built-in Creations and any mod), so our system id and map position
    are checked against all of them;
  * Sol (route B, sol_section): its system id and system location, every body and location id in use there (the
    other plugins' too) and the first free planet id; and the precedent: the bodies the plugins add, each with the
    largest vanilla id of its system, and what their overrides of a vanilla star system location change;
  * the records the probe world copies (LC172World, OverlayBlockLC172World, LC172WorldLocation) and the bases it
    places (XMarker, COCMarkerHeading, EncCitizen01Template), each checked by EditorID;
  * LC172World's references: how many are persistent, how many carry XLCN / XLRL, whether its persistent COC marker
    0010238E is one of LC172WorldLocation's LCPR rows (the location-link question in vanilla's own world);
  * Mars's master worldspaces (LC172World's registration) and the planet of every vanilla overlay world;
  * the coc targets of the session's other arrivals: LC172Ext01, a TempJemisonWorld cell and a New Atlantis cell,
    each an exterior cell with an EditorID and a COCMarkerHeading in it.
"""
import os
import struct

from . import esm
from . import probe
from . import records

LC172_WORLD = 0x02DF8C
LC172_EXT01 = "LC172Ext01"           # the control run's arrival (docs/terrain/map-markers.md)
MARS_PLANET = 0x03F59A               # PNDT MarsPlanetData (overlay_records.py)
NEW_ATLANTIS = 0x01251B              # WRLD NewAtlantis (Jemison)
TEMP_JEMISON_EDID = "TempJemisonWorld"
BASES = {"XMarker": probe.XMARKER, "COCMarkerHeading": probe.COC_MARKER, "EncCitizen01Template": probe.CITIZEN}
PLUGIN_EXTENSIONS = (".esm", ".esp", ".esl")


class CensusError(ValueError):
    pass


def fid(v):
    return f"{v:08X}" if v is not None else None


def find_records(plugin, label, formids):
    """{form id: record} of the wanted form ids in one flat top group, read without parsing the others."""
    want, out = set(formids), {}
    for start, end in plugin.groups.get(label, []):
        for item in plugin.walk(start, end):
            if item[0] != "REC":
                continue
            f = struct.unpack_from("<I", plugin.buf, item[1] + 12)[0]
            if f in want:
                out[f] = plugin.record_at(item[1])
    return out


def worlds(plugin):
    """[WRLD record] of the plugin (the top-level records of the WRLD group, children skipped)."""
    out = []
    for start, end in plugin.groups.get("WRLD", []):
        for item in plugin.walk(start, end, groups=set()):
            if item[0] == "REC":
                out.append(plugin.record_at(item[1]))
    return out


def overlay_of(rec):
    """(system id, planet id, block form id) of a WRLD's overlay component, None without one."""
    ov = probe.component_fields(rec, "BGSWorldSpaceOverlay_Component")
    if not ov or len(ov.get("SNAM", b"")) != 4 or len(ov.get("PNAM", b"")) != 4:
        return None
    b = ov.get("BNAM")
    return (struct.unpack("<i", ov["SNAM"])[0], struct.unpack("<i", ov["PNAM"])[0],
            struct.unpack("<I", b)[0] if b and len(b) == 4 else None)


def u32_or_none(d):
    return struct.unpack("<I", d)[0] if d and len(d) == 4 else None


def describe_world(rec):
    return {"formid": fid(rec.formid), "edid": rec.edid, "overlay": overlay_of(rec),
            "xlcn": fid(u32_or_none(probe.top_level(rec, b"XLCN"))),
            "climate": fid(u32_or_none(probe.top_level(rec, b"CNAM"))),
            "biome": fid(u32_or_none(probe.top_level(rec, b"BNAM"))),
            "parent": fid(u32_or_none(probe.top_level(rec, b"WNAM"))),
            "data_flags": (probe.top_level(rec, b"DATA") or b"").hex(),
            "fnam_flags": (probe.top_level(rec, b"FNAM") or b"").hex(),
            "subrecords": [s.decode("latin1") for s, _ in rec.subs]}


def world_refs(plugin, world_id, location=None):
    """Counts of a world's references by kind, group, XLCN / XLRL, and the LCPR rows of `location` that name them."""
    items = probe.world_items(plugin, world_id)
    rows = probe.lcpr_rows(location.get(b"LCPR")) if location is not None else []
    in_lcpr = {r[0] for r in rows}
    counts, cells = {}, {}
    for it in items:
        r = it["rec"]
        if it["group"] == "cell":
            xc = r.get(b"XCLC")
            cells[r.formid] = {"edid": r.edid, "grid": list(struct.unpack_from("<2i", xc)) if xc and len(xc) >= 8 else None}
            continue
        if it["group"] not in ("persistent", "temporary"):
            continue
        k = (r.sig.decode(), it["group"], "flag" if r.flags & esm.PERSISTENT else "noflag",
             "XLCN" if r.get(b"XLCN") else "-", "XLRL" if r.get(b"XLRL") else "-",
             "LCPR" if r.formid in in_lcpr else "-")
        counts[" ".join(k)] = counts.get(" ".join(k), 0) + 1
    return items, cells, counts, rows


def coc_cells(items, cells):
    """[(cell EditorID, cell form id, grid, COC marker form id)] of the exterior cells that have an EditorID and a
    COCMarkerHeading (base 000032, a Starfield.esm id) among their references, in file order."""
    markers = {}
    for it in items:
        r = it["rec"]
        if r.sig == b"REFR" and it["cell"] is not None and u32_or_none(r.get(b"NAME")) == probe.COC_MARKER:
            markers.setdefault(it["cell"], r.formid)
    out = []
    for cfid, c in cells.items():
        if c["edid"] and c["grid"] is not None and cfid in markers:
            out.append((c["edid"], fid(cfid), c["grid"], fid(markers[cfid])))
    return out


def plugin_bodies(data_dir, skip=("starfield.esm", records.MASTER.lower(), records.REGISTRATION.lower())):
    """The stars, planets and galaxy locations of every plugin next to Starfield.esm (.esm, .esp, .esl: the DLC such
    as ShatteredSpace.esm, the built-in Creations, any mod), each plugin read once, for build_master's clash checks:
    {"stars": [(source, system id, position)], "planets": [(source, EditorID, body name, (system, parent, planet),
    new)], "locations": [(source, EditorID, XNAM, YNAM, keywords, form id, new)] (the locations with an XNAM),
    "system_overrides": [(plugin, form id, record)] (overrides of a Starfield.esm star system location), "read":
    [names], "unreadable": ["name: reason"]}. new: a record of the plugin's own, not an override: its form id's top
    byte is past the master list (len(masters), or FD as SFBGS003.esm writes its own: verified on its Chop Shop,
    FD002810, with one master). Starfield.esm is read on its own, and an installed copy of our own master or
    registration plugin is skipped (their records are the ones being rebuilt)."""
    out = {"stars": [], "planets": [], "locations": [], "system_overrides": [], "read": [], "unreadable": []}
    star_system = records.KEYWORDS["LocTypeStarSystem"]
    for name in sorted(os.listdir(data_dir)):
        low = name.lower()
        if not low.endswith(PLUGIN_EXTENSIONS) or low in skip or not os.path.isfile(os.path.join(data_dir, name)):
            continue
        try:
            with esm.Plugin(os.path.join(data_dir, name)) as p:
                mine = len(p.masters)
                vanilla = [i for i, m in enumerate(p.masters) if m.lower() == "starfield.esm"]
                stars = [(f"{name} {e or fid(f)}", sid, pos) for f, e, n, sid, pos in records.stars(p)]
                planets = [(name, e, n, g, f >> 24 >= mine) for f, e, n, g in records.planets(p) if g is not None]
                locs, overrides = [], []
                for r in p.records("LCTN", [b"LCTN"]):
                    x, y = records.location_ids(r)
                    if x is None:
                        continue
                    kws = records.keywords_of(r)
                    locs.append((name, r.edid, x, y, kws, r.formid, r.formid >> 24 >= mine))
                    if vanilla and r.formid >> 24 == vanilla[0] and (vanilla[0] << 24 | star_system) in kws:
                        overrides.append((name, r.formid & 0xFFFFFF, r))
        except (esm.EsmError, OSError, struct.error) as e:
            out["unreadable"].append(f"{name}: {e}")
            continue
        out["read"].append(name)
        out["stars"] += stars
        out["planets"] += planets
        out["locations"] += locs
        out["system_overrides"] += overrides
    return out


def plugin_stars(data_dir, skip=("starfield.esm", records.MASTER.lower(), records.REGISTRATION.lower())):
    """plugin_bodies' stars, names read and unreadable names: ([(source, system id, position)], read, unreadable)."""
    b = plugin_bodies(data_dir, skip)
    return b["stars"], b["read"], b["unreadable"]


def changed_fields(vanilla, override):
    """The subrecords an override changes: [(signature, the vanilla data's hex, the override's hex)], one per
    signature whose data differ in any of its copies (None where a side has none), in the override's order and then
    the vanilla record's."""
    def by_sig(rec):
        out = {}
        for s, d in rec.subs:
            out.setdefault(s, []).append(bytes(d))
        return out
    a, b = by_sig(vanilla), by_sig(override)
    order = list(dict.fromkeys([s for s, _ in override.subs] + [s for s, _ in vanilla.subs]))
    return [(s.decode("latin1"), b"".join(a[s]).hex() if s in a else None, b"".join(b[s]).hex() if s in b else None)
            for s in order if a.get(s) != b.get(s)]


def sol_section(sf, kw, bodies, star_name=records.DEFAULT_STAR):
    """Route B's facts (records.sol_facts) and the precedent for its planet id: each body a plugin adds (not an
    override) with the largest Starfield.esm body id of its system (a new body one above it follows the rule
    sol_facts uses; hypothesis until read on the PC), and what each plugin's override of a vanilla star system
    location changes (changed_fields: what adding a body there may need)."""
    s = records.sol_facts(sf, kw, star_name, bodies["planets"], bodies["locations"])
    vanilla_max = {}
    for _, _, _, g in records.planets(sf):
        if g is not None:
            vanilla_max[g[0]] = max(vanilla_max.get(g[0], 0), g[2])
    added = [(src, e, n, list(g), vanilla_max.get(g[0])) for src, e, n, g, new in bodies["planets"] if new]
    wanted = {f for _, f, _ in bodies["system_overrides"]}
    vanilla_locs = find_records(sf, "LCTN", wanted) if wanted else {}
    overrides = []
    for src, f, rec in bodies["system_overrides"]:
        v = vanilla_locs.get(f)
        overrides.append({"plugin": src, "formid": fid(f), "edid": rec.edid,
                          "changed": changed_fields(v, rec) if v is not None else "no such Starfield.esm record"})
    loc = s["location"]
    return {"star": {"formid": fid(s["star"].formid), "edid": s["star"].edid, "name": records.star_name(s["star"]),
                     "system_id": s["system_id"]},
            "system_location": {"formid": fid(loc.formid), "edid": loc.edid,
                                "parent": fid(u32_or_none(loc.get(b"PNAM"))),
                                "keywords": [fid(k) for k in records.keywords_of(loc)],
                                "data": (loc.get(b"DATA") or b"").hex()},
            "bodies": [(src, e, n, list(g)) for src, e, n, g in s["bodies"]],
            "location_ynams": sorted({y for _, _, y in s["ynams"]}),
            "free_planet_id": s["free_planet_id"], "why": s["why"],
            "precedent": {"bodies_added_by_plugins": added, "system_location_overrides": overrides}}


def run(sf_path, data_dir=None, planet_name=records.DEFAULT_PLANET, star_name=records.DEFAULT_STAR):
    """The census as a dict (JSON-ready). Raises CensusError when a record the probe copies is missing or renamed."""
    rep = {"starfield": {"path": os.path.basename(sf_path), "bytes": os.path.getsize(sf_path)}}
    bodies = plugin_bodies(data_dir) if data_dir else {"stars": [], "planets": [], "locations": [],
                                                       "system_overrides": [], "read": [], "unreadable": []}
    with esm.Plugin(sf_path) as sf:
        rep["starfield"].update(masters=sf.masters, localized=sf.localized)
        kw_names = records.keyword_edids(sf)
        kw, notes = records.check_keywords(kw_names)
        rep["keywords"] = {k: fid(v) for k, v in kw.items()}
        rep["keyword_notes"] = notes
        star = records.find_star(sf, star_name)
        planet = records.find_planet(sf, planet_name)
        rep["template_star"] = records.describe_star(star)
        rep["template_planet"] = records.describe_planet(planet, kw_names)
        planet_biomes = [b["biome"] for b in records.biomes(planet)]

        # the records the probe world copies, and the bases it places
        problems = []
        all_worlds = worlds(sf)
        by_id = {w.formid: w for w in all_worlds}
        lc172 = by_id.get(LC172_WORLD)
        tw = probe.TEMPLATES
        if lc172 is None or lc172.edid != tw["world"][2]:
            problems.append(f"WRLD {LC172_WORLD:06X} is {lc172.edid if lc172 else 'missing'}, not {tw['world'][2]}")
        blocks = find_records(sf, "SFBK", [tw["block"][1]])
        locs = find_records(sf, "LCTN", [tw["location"][1]])
        block, loc = blocks.get(tw["block"][1]), locs.get(tw["location"][1])
        if block is None or block.edid != tw["block"][2]:
            problems.append(f"SFBK {tw['block'][1]:06X} is {block.edid if block else 'missing'}, not {tw['block'][2]}")
        if loc is None or loc.edid != tw["location"][2]:
            problems.append(f"LCTN {tw['location'][1]:06X} is {loc.edid if loc else 'missing'}, not {tw['location'][2]}")
        bases = {}
        for label in ("STAT", "NPC_"):
            bases.update(find_records(sf, label, [v for v in BASES.values()]))
        for name, f in BASES.items():
            if f not in bases or bases[f].edid != name:
                problems.append(f"base {f:06X} is {bases[f].edid if f in bases else 'missing'}, not {name}")
        if problems:
            raise CensusError("; ".join(problems))
        rep["templates"] = {
            "world": describe_world(lc172),
            "block": {"formid": fid(block.formid), "edid": block.edid, "anam": esm.zstring(block.get(b"ANAM") or b""),
                      "dnam": list(struct.unpack("<2I", block.get(b"DNAM"))) if block.get(b"DNAM") else None,
                      "inam": (block.get(b"INAM") or b"").hex(), "hnam": (block.get(b"HNAM") or b"").hex(),
                      "fnam_bytes": len(block.get(b"FNAM") or b"")},
            "location": {"formid": fid(loc.formid), "edid": loc.edid, "keywords": [fid(k) for k in records.keywords_of(loc)],
                         "parent": fid(u32_or_none(loc.get(b"PNAM"))), "xnam_ynam": records.location_ids(loc),
                         "lcpr_rows": len(probe.lcpr_rows(loc.get(b"LCPR"))),
                         "subrecords": [s.decode("latin1") for s, _ in loc.subs]},
            "bases": {name: fid(f) for name, f in BASES.items()}}

        # LC172World's references and the location links in vanilla's own overlay world
        items, cells, counts, rows = world_refs(sf, LC172_WORLD, loc)
        marker = next((it for it in items if it["rec"].formid == probe.LC172_COC), None)
        rep["lc172"] = {
            "references": counts, "cells": len(cells), "lcpr_rows": len(rows),
            "lcpr_targets": sorted({fid(r[0]) for r in rows})[:40],
            "coc_marker": None if marker is None else {
                "formid": fid(marker["rec"].formid), "group": marker["group"],
                "flags": f"{marker['rec'].flags:08X}", "in_lcpr": any(r[0] == probe.LC172_COC for r in rows),
                "pos": probe.ref_fields(marker["rec"])["pos"],
                "subrecords": [s.decode("latin1") for s, _ in marker["rec"].subs]},
            "coc_cells": coc_cells(items, cells)}
        if not any(c[0].lower() == LC172_EXT01.lower() for c in rep["lc172"]["coc_cells"]) and \
                not any((c["edid"] or "").lower() == LC172_EXT01.lower() for c in cells.values()):
            rep["lc172"]["warning"] = f"no cell {LC172_EXT01} in LC172World"

        # Mars's registrations and the planet of every overlay world
        mars = find_records(sf, "PNDT", [MARS_PLANET]).get(MARS_PLANET)
        rep["mars"] = None if mars is None else {
            "edid": mars.edid, "galaxy": list(records.galaxy(mars)),
            "master_worldspaces": [(la, lo, fid(w)) for la, lo, w in records.master_worldspaces(mars)]}
        overlays = []
        for w in all_worlds:
            o = overlay_of(w)
            if o is not None:
                overlays.append((fid(w.formid), w.edid, o[0], o[1], fid(u32_or_none(probe.top_level(w, b"BNAM")))))
        rep["overlay_worlds"] = {"count": len(overlays),
                                 "on_template_planet": [o for o in overlays
                                                        if (o[2], o[3]) == records.galaxy(planet)[0::2]][:40]}
        na = by_id.get(NEW_ATLANTIS)
        rep["new_atlantis"] = None
        if na is not None:
            na_items, na_cells, na_counts, _ = world_refs(sf, NEW_ATLANTIS)
            na_biome = u32_or_none(probe.top_level(na, b"BNAM"))
            rep["new_atlantis"] = {"world": describe_world(na), "references": na_counts,
                                   "biome_in_planet_biomes": na_biome in planet_biomes,
                                   "coc_cells": coc_cells(na_items, na_cells)[:20]}
        tj = next((w for w in all_worlds if w.edid.lower() == TEMP_JEMISON_EDID.lower()), None)
        rep["temp_jemison"] = None
        if tj is not None:
            tj_items, tj_cells, tj_counts, _ = world_refs(sf, tj.formid)
            rep["temp_jemison"] = {"world": describe_world(tj), "references": tj_counts,
                                   "cells": len(tj_cells), "coc_cells": coc_cells(tj_items, tj_cells)[:20]}
        rep["planet_biomes"] = [fid(b) for b in planet_biomes]
        try:
            rep["sol"] = sol_section(sf, kw, bodies, star_name)
        except records.PlanetError as e:                    # route B's stage stops on it; route A does not need it
            rep["sol"] = {"error": str(e)}
    if data_dir:
        rep["plugin_stars"] = {"plugins": bodies["read"], "unreadable": bodies["unreadable"],
                               "stars": [(s, sid, list(p) if p else None) for s, sid, p in bodies["stars"]]}
        rep["plugin_bodies"] = {
            "planets": [(s, e, n, list(g), new) for s, e, n, g, new in bodies["planets"]],
            "locations": [(s, e, x, y, [fid(k) for k in kws], fid(f), new)
                          for s, e, x, y, kws, f, new in bodies["locations"]]}
    return rep


def arrivals(rep):
    """The session's arrivals after the probe's own: [{label, coc, why}] from the census (LC172Ext01 always; a
    TempJemisonWorld and a New Atlantis cell when the census found one with a COC marker)."""
    out = [{"label": "lc172", "coc": LC172_EXT01,
            "why": "vanilla Mars landing with FO4SFMergeProbe.esm's marker in its persistent cell (the control)"}]
    tj = rep.get("temp_jemison") or {}
    if tj.get("coc_cells"):
        out.append({"label": "temp_jemison", "coc": tj["coc_cells"][0][0],
                    "why": "a standalone world with no overlay component (choice R)"})
    na = rep.get("new_atlantis") or {}
    if na.get("coc_cells"):
        out.append({"label": "new_atlantis", "coc": na["coc_cells"][0][0],
                    "why": "vanilla Jemison: the planet our planet copies, and its city overlay"})
    return out
