"""door_survey.py: how Fallout 4 sets up every door in exported cells, and what our build makes of each (read-only).

  python scripts/terrain/door_survey.py <cell.json> [<cell.json> ...] [--manifest <manifest.json> ...] [--out <survey.json>]

Reads dotnet/Fo4Export cell exports (with door_bases and scripts: the 2026-10-18 export; older exports give the
reference fields only) and lists one row per Door reference: what FO4 does with it (teleport, lock level and key, open by
default, initially disabled, enable parent, activate parents, linked references, the base's flags such as Automatic /
Hidden / Minimal Use / Sliding, the base's and the reference's scripts) and, with --manifest, what the conversion made of
its model (load door, door rig, passable, error). Prints a summary of the behaviour classes; --out writes every row.
Feeds docs/spikes/door-behaviour.md; writes nothing else.
"""
import argparse
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import door_audit  # noqa: E402


def base_flags(base):
    """The FO4 DOOR's flags as Mutagen names them (export door_bases[..].record.Flags), split into a list."""
    flags = str(((base or {}).get("record") or {}).get("Flags") or "")
    return sorted(f.strip() for f in flags.split(",") if f.strip() and f.strip() != "0")


def script_names(scripts):
    return sorted(str(s.get("name")) for s in scripts or [])


def classes(row):
    """The behaviour classes a door falls in; a door can be in several (a locked load door, a scripted hidden one)."""
    out = []
    if row["teleport"]:
        out.append("load door")
    if row["lock"] and row["lock"]["level"]:
        out.append("locked (key)" if row["lock"]["key"] else "locked")
    if row["open_by_default"]:
        out.append("open by default")
    if row["disabled"] or row["enable_parent"]:
        out.append("enabled by something else")
    if row["activate_parents"]:
        out.append("opened by another reference")
    if row["scripts"] or row["base_scripts"]:
        out.append("scripted")
    out += [f"flag {f}" for f in row["base_flags"]]
    return out or ["plain door"]


def survey(cells, manifests=()):
    flags = door_audit.manifest_flags(manifests) if manifests else {}
    by_source = {}
    for p in manifests:
        with open(p, encoding="utf-8-sig") as f:
            for it in json.load(f).get("items", []):
                by_source[str(it.get("source", "")).lower()] = flags.get(str(it.get("model", "")).lower())
    rows = []
    for path in cells:
        with open(path, encoding="utf-8-sig") as f:
            cell = json.load(f)
        bases = cell.get("door_bases") or {}
        for r in cell.get("refs", []):
            if r.get("type") != "Door":
                continue
            base = bases.get(r.get("base_formkey"))
            tel = r.get("teleport_destination")
            lock = r.get("lock_data")
            row = {"cell": cell.get("cell"), "ref": r.get("formkey"), "base": r.get("base_editor_id"), "model": r.get("model"),
                   "teleport": (tel or {}).get("door"), "lock": lock and {"level": lock.get("level"), "key": lock.get("key")},
                   "open_by_default": bool(r.get("open_by_default")), "disabled": bool(r.get("disabled")),
                   "enable_parent": (r.get("enable_parent") or {}).get("reference"),
                   "activate_parents": [a.get("reference") for a in (r.get("activate_parents") or {}).get("parents", [])],
                   "linked": len(r.get("linked_references") or []), "record_flags": r.get("record_flags"),
                   "base_flags": base_flags(base), "base_scripts": script_names((base or {}).get("scripts")),
                   "scripts": script_names(r.get("scripts")), "base_exported": base is not None}
            row["classes"] = classes(row)
            if manifests:
                row["build"] = by_source.get(("meshes\\" + str(r.get("model") or "").lstrip("\\")).lower(), "not converted")
            rows.append(row)
    return rows


def summary(rows):
    c = Counter(k for r in rows for k in r["classes"])
    scripts = Counter(s for r in rows for s in r["scripts"] + r["base_scripts"])
    return {"doors": len(rows), "classes": dict(c.most_common()), "scripts": dict(scripts.most_common(30)),
            "bases_without_export": sum(1 for r in rows if not r["base_exported"])}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cells", nargs="+")
    ap.add_argument("--manifest", action="append", default=[])
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    rows = survey(a.cells, a.manifest)
    print(json.dumps(summary(rows), indent=1))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=1)


if __name__ == "__main__":
    main()
