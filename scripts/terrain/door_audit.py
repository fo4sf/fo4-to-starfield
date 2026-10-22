"""door_audit.py: what each scripted load door of a core build is made of, on both sides (read-only).

  python scripts/terrain/door_audit.py --core <core64 build with doors> --port <integ staging> [--manifest <manifest.json> ...]

One JSON line per objects.json "doors" entry: the FO4 door (src, editor_id, model), the exterior side's converted model
and, with --manifest (the exterior conversion's manifest.json files), that model's manifest flags (door rig, load_door,
door_not_opening, door_error, collision source); the interior side's REFR in the port plugin with its base record's
signature, editor id and model. A door the player cannot activate shows here as a base that is not a DOOR or ACTI (an FO4
teleport door converted under a name LOAD_DOOR_RE does not know, such as RoofHatch01, stays a STAT: research log
2026-10-08), or as a converted model without collision (door_not_opening: passable, nothing to aim at). Writes nothing.
"""
import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
import vmad_patch  # noqa: E402
from fo4sf import fo4land  # noqa: E402

FLAGS = ("door_not_opening", "door_error", "door_frozen_parts", "load_door")


def manifest_flags(paths):
    """{converted model, lower case: the entry's door-related fields} of the given manifests."""
    out = {}
    for p in paths:
        with open(p, encoding="utf-8-sig") as f:
            for it in json.load(f).get("items", []):
                e = {k: it[k] for k in FLAGS if k in it}
                if "door" in it:
                    e["door_rig"] = it["door"].get("rig", "template")
                    for k in ("dropped_skinned_shapes", "rebound_skinned_shapes"):
                        if k in it["door"]:
                            e[k] = it["door"][k]
                e["collision"] = (it.get("collision_report") or {}).get("source")
                out[str(it.get("model", "")).lower()] = e
    return out


def _fields(rec):
    """{subrecord: data} of a records() entry, or None for a compressed record (not read here)."""
    sig, flags, data, _path = rec
    return None if flags & vmad_patch.COMPRESSED else dict(fo4land.iter_subrecords(data))


def base_of(records, own, ref_fid):
    """The interior door REFR's base: its signature, editor id and model when it is the port's own record."""
    hit = records.get(ref_fid)
    if hit is None or hit[0] != b"REFR":
        return {"interior_ref": f"{ref_fid:08X} " + ("missing" if hit is None else f"is a {hit[0].decode()}")}
    fields = _fields(hit)
    if fields is None:
        return {"interior_ref": f"{ref_fid:08X} compressed (not read)"}
    base = struct.unpack("<I", fields[b"NAME"])[0]
    out = {"interior_ref": f"{ref_fid:08X}", "interior_base": f"{base:08X}", "interior_vmad": b"VMAD" in fields}
    b = records.get(base)
    if b is None:
        out["interior_base_sig"] = "a master's" if (base >> 24) != own else "missing"
        return out
    bf = _fields(b) or {}
    out.update(interior_base_sig=b[0].decode(), interior_base_edid=fo4land.zstring(bf.get(b"EDID", b"")),
               interior_model=fo4land.zstring(bf.get(b"MODL", b"")))
    return out


def audit(core, port, manifests=()):
    _plugin, doors = vmad_patch.core_doors(core)
    p = vmad_patch.Plugin.read(os.path.join(port, vmad_patch.plugin_in(port)))
    own = len(p.masters())
    records = p.records()
    flags = manifest_flags(manifests)
    rows = []
    for e in doors:
        d = e["destination"]
        conv = str(e.get("converted_model") or e.get("model") or "")      # core objects.json: "model" is the converted one
        row = {"src": e["src"], "editor_id": e.get("editor_id") or e.get("edid"), "model": conv, "cell": d.get("cell")}
        if manifests:
            row["exterior"] = flags.get(conv.lower(), "not in the manifests")
        row.update(base_of(records, own, (own << 24) | int(d.get("ref") or d["port_ref"], 16)))
        rows.append(row)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--core", required=True)
    ap.add_argument("--port", required=True)
    ap.add_argument("--manifest", action="append", default=[])
    a = ap.parse_args(argv)
    for row in audit(a.core, a.port, a.manifest):
        print(json.dumps(row))


if __name__ == "__main__":
    main()
