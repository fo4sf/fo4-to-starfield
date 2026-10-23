"""ref_inspect.py: one reference of a plugin and what stands around it (read-only).

  python scripts/terrain/ref_inspect.py --plugin <FO4Port.esm> --ref <local id, hex> [--radius 4] [--manifest <manifest.json> ...]

Prints one JSON object: the REFR's cell, position and rotation (DATA), its base record's signature, editor id and
model, its XTEL door (the linked door's id, when the REFR has one), its VMAD scripts with their properties, and every
other REFR of the same cell within --radius in xy (sorted by z, each with its base's signature, editor id, model and,
with --manifest, that model's door and collision fields as door_audit reads them). Written for the Fort Hagen roof hatch
(port 00C7A6, owner 2026-10-23: could not find or use it from inside): a base that is not a DOOR or ACTI cannot be
activated; a door well above every nearby floor or ladder cannot be reached. Writes nothing.
"""
import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
import door_audit  # noqa: E402
import vmad_patch  # noqa: E402
from fo4sf import fo4land  # noqa: E402

CELL_GROUPS = (vmad_patch.GROUP_CELL_CHILDREN, 8, 9, 10)     # cell children, persistent, temporary, visible distant


def _cell(path):
    """The cell id a record's group path names (its innermost cell-children group), or None."""
    for gtype, label in reversed(path):
        if gtype in CELL_GROUPS:
            return label
    return None


def _base(records, fid, flags):
    b = records.get(fid)
    if b is None:
        return {"base": f"{fid:08X}", "base_sig": "missing or a master's"}
    bf = door_audit._fields(b) or {}
    out = {"base": f"{fid:08X}", "base_sig": b[0].decode(), "base_edid": fo4land.zstring(bf.get(b"EDID", b"")),
           "model": fo4land.zstring(bf.get(b"MODL", b""))}
    if flags is not None:
        out["manifest"] = flags.get(out["model"].lower(), "not in the manifests")
    return out


def _data(fields):
    d = fields.get(b"DATA", b"")
    return struct.unpack_from("<6f", d) if len(d) >= 24 else None


def inspect(plugin_path, local_id, radius=4.0, manifests=()):
    p = vmad_patch.Plugin.read(plugin_path)
    own = len(p.masters())
    records = p.records()
    flags = door_audit.manifest_flags(manifests) if manifests else None
    fid = (own << 24) | local_id
    hit = records.get(fid)
    if hit is None or hit[0] != b"REFR":
        return {"ref": f"{fid:08X}", "error": "missing" if hit is None else f"is a {hit[0].decode()}"}
    fields = door_audit._fields(hit)
    if fields is None:
        return {"ref": f"{fid:08X}", "error": "compressed (not read)"}
    cell, data = _cell(hit[3]), _data(fields)
    out = {"ref": f"{fid:08X}", "edid": fo4land.zstring(fields.get(b"EDID", b"")),
           "cell": None if cell is None else f"{cell:08X}",
           "pos": None if data is None else [round(v, 3) for v in data[:3]],
           "rot": None if data is None else [round(v, 4) for v in data[3:]]}
    out.update(_base(records, struct.unpack("<I", fields[b"NAME"])[0], flags))
    if b"XTEL" in fields:
        out["xtel_door"] = f"{struct.unpack_from('<I', fields[b'XTEL'])[0]:08X}"
    if b"VMAD" in fields:
        try:
            out["scripts"] = vmad_patch.decode(fields[b"VMAD"])["scripts"]
        except ValueError as e:
            out["scripts"] = f"VMAD not parsed: {e}"
    near = []
    if data is not None and cell is not None:
        for ofid, (sig, rflags, rdata, path) in records.items():
            if ofid == fid or sig != b"REFR" or _cell(path) != cell or rflags & vmad_patch.COMPRESSED:
                continue
            of = dict(fo4land.iter_subrecords(rdata))
            od = _data(of)
            if od is None or (od[0] - data[0]) ** 2 + (od[1] - data[1]) ** 2 > radius ** 2:
                continue
            row = {"ref": f"{ofid:08X}", "pos": [round(v, 3) for v in od[:3]], "dz": round(od[2] - data[2], 3)}
            row.update(_base(records, struct.unpack("<I", of[b"NAME"])[0], flags))
            near.append(row)
    out["near"] = sorted(near, key=lambda r: r["pos"][2])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plugin", required=True)
    ap.add_argument("--ref", required=True, type=lambda s: int(s, 16))
    ap.add_argument("--radius", type=float, default=4.0)
    ap.add_argument("--manifest", action="append", default=[])
    a = ap.parse_args(argv)
    print(json.dumps(inspect(a.plugin, a.ref, a.radius, a.manifest), indent=1))


if __name__ == "__main__":
    main()
