"""Raw VMAD (Papyrus script attachment) for Starfield REFR records: decode, encode and a record-level patch of an existing
plugin (docs/terrain/scripted-doors.md). Pure stdlib plus src/fo4sf/fo4land's record walk; nothing is deployed.

    python scripts/terrain/vmad_patch.py dump  --plugin <esm> --ref <6 hex local id>
    python scripts/terrain/vmad_patch.py apply --plugin <in.esm> --out <out.esm> --ref <6 hex> --script FO4SF_LoadDoor
           --string DestinationPlugin=FO4TerrainCore.esm --int DestinationId=678543
    python scripts/terrain/vmad_patch.py check --old <in.esm> --new <out.esm> --ref <6 hex> [--ref ...]

Layout (Starfield.esm 1.16.244, 60 REFR VMADs read raw in the design pass; the example 001FDD1E MQ105SetStage50Trigger001):
    int16 version = 6 | uint16 object format = 2 | uint16 script count
    per script:   uint16 name length + name (no NUL) | uint8 status (0 Local, 1 Inherited, 3 Removed) | uint16 property count
    per property: uint16 name length + name | uint8 type | uint8 status (1 Edited, 3 Removed) | value
    value by type: 1 object (format 2) = uint16 unused 0, int16 alias -1, uint32 FormID (file-local master index);
                   2 string = uint16 length + chars; 3 int = int32; 4 float = f32; 5 bool = u8;
                   11..15 arrays = uint32 count + elements of 1..5
    nothing follows the last property (a REFR has no fragments)
The encoder writes exactly what Mutagen 0.55.0-alpha.67 writes for the same script (verified in the design pass: an 80-byte
VMAD "FO4SF_LoadDoor" Local with DestinationPlugin "FO4Port.esm" + DestinationId 0x2339), so both plugins carry one layout.

The patch inserts (or replaces) the VMAD subrecord of one REFR in place: the record's data size and every enclosing GRUP
size grow by the inserted bytes, nothing else moves relative to its group, no record is added, the TES4 header is kept.
A compressed record is refused (none of our REFRs is).
"""
import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
from fo4sf import fo4land  # noqa: E402

VERSION, OBJECT_FORMAT = 6, 2
STATUS_LOCAL, STATUS_INHERITED, STATUS_REMOVED = 0, 1, 3
PROP_EDITED, PROP_REMOVED = 1, 3
TYPES = {"object": 1, "string": 2, "int": 3, "float": 4, "bool": 5}
TYPE_NAMES = {v: k for k, v in TYPES.items()}
COMPRESSED = 0x40000
REC_HDR = 24
GRP_HDR = 24
SCRIPT_NAME_MAX = 0xFFFF


# ------------------------------------------------------------------------------------------------------------ codec
def _name(b):
    data = b.encode("cp1252")
    if len(data) > SCRIPT_NAME_MAX:
        raise ValueError(f"name of {len(data)} bytes")
    return struct.pack("<H", len(data)) + data


def encode_value(ptype, value):
    if ptype == 1:
        return struct.pack("<HhI", 0, -1, int(value))
    if ptype == 2:
        data = str(value).encode("cp1252")
        return struct.pack("<H", len(data)) + data
    if ptype == 3:
        return struct.pack("<i", int(value))
    if ptype == 4:
        return struct.pack("<f", float(value))
    if ptype == 5:
        return struct.pack("<B", 1 if value else 0)
    if 11 <= ptype <= 15:
        return struct.pack("<I", len(value)) + b"".join(encode_value(ptype - 10, v) for v in value)
    raise ValueError(f"property type {ptype} not encoded")


def encode(scripts, version=VERSION, object_format=OBJECT_FORMAT):
    """VMAD bytes of [{"name", "status" (default Local), "properties": [{"name", "type" (1..5, 11..15 or their names),
    "status" (default Edited), "value"}]}]."""
    out = struct.pack("<hHH", version, object_format, len(scripts))
    for s in scripts:
        props = s.get("properties") or []
        out += _name(s["name"]) + struct.pack("<BH", int(s.get("status", STATUS_LOCAL)), len(props))
        for p in props:
            t = p["type"]
            t = TYPES[t] if isinstance(t, str) else int(t)
            out += _name(p["name"]) + struct.pack("<BB", t, int(p.get("status", PROP_EDITED))) + encode_value(t, p["value"])
    return out


def decode_value(data, pos, ptype):
    if ptype == 1:
        unused, alias, fid = struct.unpack_from("<HhI", data, pos)
        return {"unused": unused, "alias": alias, "formid": fid}, pos + 8
    if ptype == 2:
        n = struct.unpack_from("<H", data, pos)[0]
        return data[pos + 2:pos + 2 + n].decode("cp1252", "replace"), pos + 2 + n
    if ptype == 3:
        return struct.unpack_from("<i", data, pos)[0], pos + 4
    if ptype == 4:
        return struct.unpack_from("<f", data, pos)[0], pos + 4
    if ptype == 5:
        return bool(data[pos]), pos + 1
    if 11 <= ptype <= 15:
        n = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        vals = []
        for _ in range(n):
            v, pos = decode_value(data, pos, ptype - 10)
            vals.append(v)
        return vals, pos
    raise ValueError(f"property type {ptype} not decoded")


def decode(data, object_format=OBJECT_FORMAT):
    """{"version", "object_format", "scripts": [{"name", "status", "properties": [{"name", "type", "status", "value"}]}]}.
    ValueError when bytes are left over or the object format is not the one the decoder knows."""
    version, fmt, n = struct.unpack_from("<hHH", data, 0)
    if fmt != object_format:
        raise ValueError(f"object format {fmt}, decoder knows {object_format}")
    pos, scripts = 6, []
    for _ in range(n):
        ln = struct.unpack_from("<H", data, pos)[0]
        name = data[pos + 2:pos + 2 + ln].decode("cp1252", "replace")
        pos += 2 + ln
        status, np_ = struct.unpack_from("<BH", data, pos)
        pos += 3
        props = []
        for _ in range(np_):
            ln = struct.unpack_from("<H", data, pos)[0]
            pname = data[pos + 2:pos + 2 + ln].decode("cp1252", "replace")
            pos += 2 + ln
            ptype, pstatus = struct.unpack_from("<BB", data, pos)
            pos += 2
            value, pos = decode_value(data, pos, ptype)
            props.append({"name": pname, "type": ptype, "status": pstatus, "value": value})
        scripts.append({"name": name, "status": status, "properties": props})
    if pos != len(data):
        raise ValueError(f"{len(data) - pos} bytes after the last property")
    return {"version": version, "object_format": fmt, "scripts": scripts}


def load_door_vmad(script, plugin_property, plugin, id_property, local_id):
    """The scripted door's VMAD: one Local script with the plugin name (string) and the destination's plugin-local id
    (int, 1..0xFFFFFF: the script refuses anything else)."""
    if not (isinstance(local_id, int) and 0 < local_id <= 0xFFFFFF):
        raise ValueError(f"{id_property} {local_id!r} is not a plugin-local id in 1..0xFFFFFF")
    if not plugin or not plugin.lower().endswith((".esm", ".esp", ".esl")):
        raise ValueError(f"{plugin_property} {plugin!r} is not a plugin file name")
    return encode([{"name": script, "status": STATUS_LOCAL, "properties": [
        {"name": plugin_property, "type": "string", "status": PROP_EDITED, "value": plugin},
        {"name": id_property, "type": "int", "status": PROP_EDITED, "value": local_id}]}])


def door_properties(vmad_bytes, script, plugin_property, id_property):
    """(plugin, local id) of a scripted door's VMAD, or None with the reason: exactly one Local script of that name,
    the two Edited properties with those names and types, nothing else."""
    try:
        v = decode(vmad_bytes)
    except (ValueError, struct.error) as e:
        return None, f"VMAD does not decode: {e}"
    if v["version"] != VERSION or v["object_format"] != OBJECT_FORMAT:
        return None, f"VMAD version {v['version']} / format {v['object_format']}"
    if len(v["scripts"]) != 1 or v["scripts"][0]["name"] != script or v["scripts"][0]["status"] != STATUS_LOCAL:
        return None, f"scripts {[(s['name'], s['status']) for s in v['scripts']]}, expected one Local {script}"
    props = {p["name"]: p for p in v["scripts"][0]["properties"]}
    if set(props) != {plugin_property, id_property} or len(v["scripts"][0]["properties"]) != 2:
        return None, f"properties {sorted(props)}"
    a, b = props[plugin_property], props[id_property]
    if (a["type"], a["status"], b["type"], b["status"]) != (TYPES["string"], PROP_EDITED, TYPES["int"], PROP_EDITED):
        return None, "property types or status"
    return (a["value"], b["value"]), ""


# ------------------------------------------------------------------------------------------------------------ records
def subrecord(sig, data):
    if len(data) > 0xFFFF:
        raise ValueError("subrecord over 64 KiB (XXXX) not written")
    return sig + struct.pack("<H", len(data)) + data


def with_vmad(fields, vmad):
    """The REFR's field bytes with VMAD in vanilla position (after EDID, before everything else), replacing an existing one."""
    out, placed = b"", False
    for sig, d in fields:
        if sig == b"VMAD":
            continue
        if not placed and sig != b"EDID":
            out += subrecord(b"VMAD", vmad)
            placed = True
        out += subrecord(sig, d)
    if not placed:
        out += subrecord(b"VMAD", vmad)
    return out


def locate(buf, local_id):
    """(record offset, [enclosing GRUP offsets]) of the record with this plugin-local id (any master index), walking the
    GRUP tree; KeyError if absent."""
    hsize = struct.unpack_from("<I", buf, 4)[0]
    found = []

    def walk(start, end, chain):
        for item in fo4land.iter_items(buf, start, end):
            if item[0] == "GRUP":
                walk(item[1] + GRP_HDR, item[2], chain + [item[1]])
            elif item[3] & 0xFFFFFF == local_id:
                found.append((item[1], chain))
    walk(REC_HDR + hsize, len(buf), [])
    if len(found) != 1:
        raise KeyError(f"{len(found)} records with local id {local_id:06X}")
    return found[0]


def patch(buf, local_id, vmad):
    """buf with the VMAD inserted into (or replaced on) the REFR of this local id; the record's size and each enclosing
    GRUP's size grow by the difference. Returns (new buffer, {"offset", "old_size", "new_size", "groups"})."""
    off, chain = locate(buf, local_id)
    typ, size, flags, fid = struct.unpack_from("<4sIII", buf, off)
    if typ != b"REFR":
        raise ValueError(f"{local_id:06X} is a {typ.decode()} record, not a REFR")
    if flags & COMPRESSED:
        raise ValueError(f"{local_id:06X} is compressed; the patch writes stored records only")
    fields = list(fo4land.iter_subrecords(buf[off + REC_HDR:off + REC_HDR + size]))
    data = with_vmad(fields, vmad)
    delta = len(data) - size
    head = bytearray(buf[off:off + REC_HDR])
    struct.pack_into("<I", head, 4, len(data))
    out = bytearray(buf[:off]) + head + data + buf[off + REC_HDR + size:]
    for g in chain:
        gsize = struct.unpack_from("<I", out, g + 4)[0]
        struct.pack_into("<I", out, g + 4, gsize + delta)
    return bytes(out), {"offset": off, "old_size": size, "new_size": len(data), "groups": chain, "delta": delta}


def records_by_id(buf):
    """{full form id: (type, flags, header bytes, field list)} of every record, and the GRUP headers in file order."""
    hsize = struct.unpack_from("<I", buf, 4)[0]
    recs, groups = {}, []

    def walk(start, end, depth):
        for item in fo4land.iter_items(buf, start, end):
            if item[0] == "GRUP":
                groups.append((depth, bytes(buf[item[1] + 8:item[1] + GRP_HDR]), item[2] - item[1]))
                walk(item[1] + GRP_HDR, item[2], depth + 1)
            else:
                typ, off, flags, fid = item
                size = struct.unpack_from("<I", buf, off + 4)[0]
                recs[fid] = (typ, flags, bytes(buf[off + 8:off + REC_HDR]),
                             list(fo4land.iter_subrecords(fo4land.record_data(buf, off))))
    walk(REC_HDR + hsize, len(buf), 0)
    return recs, groups


def check(old, new, local_ids):
    """Problems (strings) of a patched plugin against its source: the TES4 header is byte-identical, every record but the
    patched ones is identical (type, flags, header, every field), each patched REFR differs from its source only by a
    VMAD field, the GRUP tree has the same labels in the same order and only the sizes of the groups enclosing a patched
    record changed. Empty = nothing else changed."""
    problems = []
    oh, nh = struct.unpack_from("<I", old, 4)[0], struct.unpack_from("<I", new, 4)[0]
    if old[:REC_HDR + oh] != new[:REC_HDR + nh]:
        problems.append("TES4 header differs")
    orec, ogrp = records_by_id(old)
    nrec, ngrp = records_by_id(new)
    if set(orec) != set(nrec):
        problems.append(f"record set differs: {len(orec)} -> {len(nrec)}")
    targets = {i & 0xFFFFFF for i in local_ids}
    for fid, o in orec.items():
        n = nrec.get(fid)
        if n is None:
            continue
        if fid & 0xFFFFFF in targets:
            if (o[0], o[1], o[2]) != (n[0], n[1], n[2]):
                problems.append(f"{fid:08X}: type / flags / header changed")
            of = [(s, d) for s, d in o[3] if s != b"VMAD"]
            nf = [(s, d) for s, d in n[3] if s != b"VMAD"]
            if of != nf:
                problems.append(f"{fid:08X}: a field other than VMAD changed")
            if sum(1 for s, _ in n[3] if s == b"VMAD") != 1:
                problems.append(f"{fid:08X}: no single VMAD")
        elif o != n:
            problems.append(f"{fid:08X}: record changed")
    if [g[:2] for g in ogrp] != [g[:2] for g in ngrp]:
        problems.append("GRUP tree differs")
    else:
        # only the groups on a patched record's chain may change size: locate them in the new file
        chains = set()
        for i in local_ids:
            try:
                chains |= set(locate(new, i & 0xFFFFFF)[1])
            except KeyError as e:
                problems.append(str(e))
        offs = []
        hsize = struct.unpack_from("<I", new, 4)[0]

        def walk(start, end):
            for item in fo4land.iter_items(new, start, end):
                if item[0] == "GRUP":
                    offs.append(item[1])
                    walk(item[1] + GRP_HDR, item[2])
        walk(REC_HDR + hsize, len(new))
        for k, (o, n) in enumerate(zip(ogrp, ngrp)):
            if o[2] != n[2] and offs[k] not in chains:
                problems.append(f"GRUP {k} ({o[1][:4].hex()}) size changed off the patched chain")
    return problems


def refr_vmad(buf, local_id):
    """The VMAD bytes of the REFR with this local id (None if it has none)."""
    off, _chain = locate(buf, local_id)
    size = struct.unpack_from("<I", buf, off + 4)[0]
    for sig, d in fo4land.iter_subrecords(buf[off + REC_HDR:off + REC_HDR + size]):
        if sig == b"VMAD":
            return bytes(d)
    return None


# ---------------------------------------------------------------------------------------------------------------- cli
def read(path):
    with open(path, "rb") as f:
        return f.read()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("dump")
    p.add_argument("--plugin", required=True)
    p.add_argument("--ref", required=True, action="append", help="6 hex plugin-local id (repeatable)")
    p = sub.add_parser("apply")
    p.add_argument("--plugin", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--ref", required=True)
    p.add_argument("--script", required=True)
    p.add_argument("--string", action="append", default=[], help="Name=value string property")
    p.add_argument("--int", action="append", default=[], help="Name=value int property")
    p = sub.add_parser("check")
    p.add_argument("--old", required=True)
    p.add_argument("--new", required=True)
    p.add_argument("--ref", required=True, action="append")
    a = ap.parse_args(argv)
    if a.cmd == "dump":
        buf = read(a.plugin)
        for r in a.ref:
            v = refr_vmad(buf, int(r, 16))
            print(json.dumps({"ref": r, "bytes": v.hex() if v else None, "decoded": decode(v) if v else None}, indent=1))
        return 0
    if a.cmd == "apply":
        if os.path.exists(a.out):
            sys.exit(f"{a.out} exists")
        props = [{"name": k, "type": "string", "value": v} for k, v in (s.split("=", 1) for s in a.string)]
        props += [{"name": k, "type": "int", "value": int(v, 0)} for k, v in (s.split("=", 1) for s in a.int)]
        vmad = encode([{"name": a.script, "properties": props}])
        buf = read(a.plugin)
        out, info = patch(buf, int(a.ref, 16), vmad)
        with open(a.out, "wb") as f:
            f.write(out)
        print(json.dumps({"vmad": vmad.hex(), **info}, indent=1))
        return 0
    probs = check(read(a.old), read(a.new), [int(r, 16) for r in a.ref])
    for pr in probs:
        print("  FAIL " + pr)
    print("CHECK", "PASS" if not probs else "FAIL")
    return 0 if not probs else 1


if __name__ == "__main__":
    sys.exit(main())
