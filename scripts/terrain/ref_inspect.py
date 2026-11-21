"""ref_inspect.py: one reference of a plugin and what stands around it (read-only).

  python scripts/terrain/ref_inspect.py --plugin <FO4Port.esm> --ref <local id, hex> [--radius 4] [--manifest <manifest.json> ...]

Prints one JSON object: the REFR's cell, position and rotation (DATA), its base record's signature, editor id and
model, its XTEL door (the linked door's id, when the REFR has one), its VMAD scripts with their properties, and every
other REFR of the same cell within --radius in xy (sorted by z, each with its base's signature, editor id, model and,
with --manifest, that model's door and collision fields as door_audit reads them). Written for the Fort Hagen roof hatch
(port 00C7A6, owner 2026-10-23: could not find or use it from inside): a base that is not a DOOR or ACTI cannot be
activated; a door well above every nearby floor or ladder cannot be reached. Writes nothing.

Ancestry only (no record payloads or neighbours):
  python -I scripts/terrain/ref_inspect.py --plugin <plugin> --record-path <8-digit STORED id> [--record-path ...]
         [--expect-sha256 <pinned hash>]
Prints the actual masters, file hash, record header offsets and ordered enclosing GRUP headers. IDs are the full
stored IDs qualified through this file's ordinary master table, never runtime load-order IDs. This mode uses the
memory-mapped reader, scans every top group, and refuses missing/duplicate targets or changed inputs. Raw group
labels are retained; only known form-labelled group types are master-qualified. It does not validate map listing,
discovery, field semantics or runtime world membership. Writes nothing, including on error.
"""
import argparse
import hashlib
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
import door_audit  # noqa: E402
import vmad_patch  # noqa: E402
from fo4sf import fo4land  # noqa: E402
from fo4sf.planet import esm  # noqa: E402

CELL_GROUPS = (vmad_patch.GROUP_CELL_CHILDREN, 8, 9, 10)     # cell children, persistent, temporary, visible distant
FORM_LABEL_GROUPS = (1, 6, 8, 9, 10)     # world children and the cell-children groups; block/grid labels stay raw


def stored_id(text):
    """Require a full stored ID: short/local IDs must not silently select a master's record."""
    if not re.fullmatch(r"(?:0[xX])?[0-9a-fA-F]{8}", text):
        raise argparse.ArgumentTypeError("--record-path needs an 8-digit stored hex ID, not a local/runtime ID")
    return int(text, 16)


def _stored_identity(fid, files):
    index = fid >> 24
    out = {"stored_id": f"{fid:08X}"}
    if index >= len(files):
        out["qualification_error"] = f"master index {index:02X} outside this file's master table (runtime/compact IDs are not decoded)"
    else:
        out.update(plugin=files[index], local_id=f"{fid & 0xFFFFFF:06X}")
    return out


def record_paths(plugin_path, ids, expected_sha256=None):
    """Header-only ancestry using the existing bounded GRUP walk, with hashes over the same read-only mapping."""
    if not ids or any(type(fid) is not int or not 0 <= fid <= 0xFFFFFFFF for fid in ids):
        raise ValueError("record_paths requires at least one full stored uint32 ID")
    if expected_sha256 is not None and not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("expected SHA-256 must be 64 hex digits")
    with esm.Plugin(plugin_path) as p:
        before = hashlib.sha256(p.buf).hexdigest()
        if expected_sha256 is not None and before != expected_sha256.lower():
            raise ValueError("plugin SHA-256 does not match the pinned input")
        files = p.masters + [os.path.basename(plugin_path)]
        for fid in ids:
            if "qualification_error" in _stored_identity(fid, files):
                raise ValueError(f"target {fid:08X}: cannot qualify through this file's master table")
        hits = {fid: [] for fid in ids}

        def group(offset, end):
            label = bytes(p.buf[offset + 8:offset + 12])
            gtype = struct.unpack_from("<i", p.buf, offset + 12)[0]
            row = {"offset": offset, "end_offset": end, "type": gtype, "label_hex": label.hex()}
            if gtype == 0:
                row["label_text"] = label.decode("latin1")
            elif gtype in FORM_LABEL_GROUPS:
                row["label_form"] = _stored_identity(struct.unpack("<I", label)[0], files)
            return row

        spans = sorted(span for spans in p.groups.values() for span in spans)
        for start, end in spans:
            top = group(start - 24, end)
            if top["type"] != 0:
                raise ValueError(f"top GRUP at {start - 24} has nonzero type")
            chain = [top]
            for item in p.walk(start, end):
                if item[0] == "GRUP":
                    _, _, _, child_start, child_end, depth = item
                    chain = chain[:depth + 1] + [group(child_start - 24, child_end)]
                else:
                    _, offset, sig, depth = item
                    chain = chain[:depth + 1]
                    size, flags, fid = struct.unpack_from("<III", p.buf, offset + 4)
                    if fid in hits:
                        hits[fid].append({"record": _stored_identity(fid, files), "signature": sig.decode("latin1"),
                                          "offset": offset, "end_offset": offset + 24 + size,
                                          "flags": f"{flags:08X}", "groups": list(chain)})
        after = hashlib.sha256(p.buf).hexdigest()
        if before != after:
            raise ValueError("plugin changed during the ancestry read")
        problems = [f"{fid:08X}: {len(rows)} matches (need exactly one)" for fid, rows in hits.items() if len(rows) != 1]
        if problems:
            raise ValueError("; ".join(problems))
        return {"plugin": os.path.basename(plugin_path), "masters": p.masters, "sha256": before,
                "sha256_after": after, "scan": "all top groups; headers only; file ancestry, not runtime membership",
                "records": [hits[fid][0] for fid in hits]}


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
    selector = ap.add_mutually_exclusive_group(required=True)
    selector.add_argument("--ref", type=lambda s: int(s, 16))
    selector.add_argument("--record-path", action="append", type=stored_id, help="ancestry only: full 8-digit stored ID (repeatable)")
    ap.add_argument("--expect-sha256", help="with --record-path: refuse another input build")
    ap.add_argument("--radius", type=float, default=4.0)
    ap.add_argument("--manifest", action="append", default=[])
    a = ap.parse_args(argv)
    if a.expect_sha256 is not None and not a.record_path:
        ap.error("--expect-sha256 requires --record-path")
    if a.record_path:
        try:
            out = record_paths(a.plugin, a.record_path, a.expect_sha256)
        except (OSError, ValueError, struct.error) as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
            return 2
    else:
        out = inspect(a.plugin, a.ref, a.radius, a.manifest)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
