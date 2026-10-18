"""port_promote.py: the interior promotion list for dotnet/PluginSpike (docs/terrain/port-promotions.md).

  python scripts/terrain/port_promote.py --out <PluginSpike output dir>/promote.json
         --containers-table scripts/terrain/clusters/container_table.json --items-table scripts/terrain/clusters/item_table.json
         [--names <export-names json>] [--starfield-data <Starfield Data folder>] <cell export.json> ...

The converted interiors (FO4Port.esm) placed every FO4 container, loose item, activator and terminal as a plain STAT
(or an MSTT when its model has a dynamic body): nothing to open, take, press or read (owner's play test, 18 Oct
19:32Z to 19:41Z). The exterior core promotes the same classes (make_cluster.py, make_core64c.py, TerrainOverlays);
this writes the same lists for the cell exports PluginSpike reads, with the same rules and tables, so PluginSpike gives
those references a CONT / MISC / ACTI / TERM base instead (dotnet/PluginSpike/Promotions.cs):
  containers  FO4 Container, the container table's name and vanilla inventory (a table "skip" entry, the settlement
              workshops, stays out)
  items       FO4 MiscItem / Ingestible / Weapon, the item table's name, value and weight (MISC, as the core)
  activators  FO4 Activator, its FO4 name from --names (none: an ACTI without a name, as FO4 shows no prompt)
  terminals   FO4 Terminal, its name and one body line (make_cluster.TERMINAL_BODY); needs --starfield-data (the
              vanilla terminal's furniture block is read from Starfield.esm by PluginSpike)
Left out as the core leaves them out: initially disabled references and ones without a model or with a marker model.
Edids are the core's (make_core64c.promoted_edid) with FO4Port_ for FO4Core_: one base per FO4 base record.
A reference the port puts on its own posed model or on a DOOR base keeps it (PluginSpike counts it as kept).
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
sys.path.insert(0, HERE)
import make_cluster  # noqa: E402
import make_core64c  # noqa: E402

PREFIX = "FO4Port_"
KINDS = ("containers", "items", "activators", "terminals")


def port_edid(kind, base, src):
    """The core's promoted edid (FO4Core_<kind>_<6 hex>_<plugin>) under the port's prefix."""
    core = make_core64c.promoted_edid(kind, base, src)
    return PREFIX + core[len(make_core64c.EDID_PREFIX):]


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


def promote(refs, placed, containers_table, items_table, names=None, starfield_esm=None):
    """The promote.json document: per kind the entries PluginSpike reads ({"src", "edid", ...}) and a report."""
    out, report = {"note": "scripts/terrain/port_promote.py: interior promotions read by dotnet/PluginSpike "
                           "(Promotions.cs) from its output dir", "starfield_esm": starfield_esm}, {}
    conts, report["containers"] = make_cluster.containers(refs, placed, containers_table)
    out["containers"] = [{"src": e["src"], "edid": port_edid("cont", e["base"], e["src"]), "name": e["name"],
                          "items": e["items"]} for e in conts["containers"]]
    its, report["items"] = make_cluster.items(refs, placed, items_table)
    out["items"] = [{"src": e["src"], "edid": port_edid("misc", e["base"], e["src"]), "name": e["name"],
                     "value": e["value"], "weight": e["weight"]} for e in its["items"]]
    actis, report["activators"] = make_cluster.activators(refs, placed, names=names)
    out["activators"] = [{"src": e["src"], "edid": port_edid("acti", e["base"], e["src"]), "name": e["name"]}
                         for e in actis["activators"]]
    terms, report["terminals"] = make_cluster.terminals(refs, placed, names=names)
    out["terminals"] = []
    for e in terms["terminals"]:
        edid = port_edid("term", e["base"], e["src"])
        out["terminals"].append({"src": e["src"], "edid": edid, "menu_edid": PREFIX + "tmlm_" + edid[len(PREFIX + "term_"):],
                                 "name": e["name"], "body": e["body"]})
    if out["terminals"] and not starfield_esm:
        raise ValueError(f"{len(out['terminals'])} terminals need --starfield-data (PluginSpike copies the vanilla "
                         "terminal's furniture block from Starfield.esm)")
    for kind in KINDS:                                        # one shared base per edid carries one value (Promotions.cs)
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
    ap.add_argument("--starfield-data", default="", help="Starfield's Data folder (Starfield.esm: the terminal template)")
    a = ap.parse_args(argv)
    refs, placed = cell_refs(a.exports)
    sf = os.path.abspath(os.path.join(a.starfield_data, "Starfield.esm")) if a.starfield_data else None
    if sf and not os.path.isfile(sf):
        raise SystemExit(f"no Starfield.esm in {a.starfield_data}")
    doc = promote(refs, placed, make_cluster.load(a.containers_table), make_cluster.load(a.items_table),
                  make_cluster.load_names(a.names) if a.names else None, sf)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    print(f"wrote {a.out}: " + ", ".join(f"{len(doc[k])} {k}" for k in KINDS) + f" from {len(a.exports)} cell exports")
    return 0


if __name__ == "__main__":
    sys.exit(main())
