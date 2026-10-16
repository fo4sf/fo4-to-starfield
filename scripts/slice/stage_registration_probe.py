"""Stage a companion-only H_ll registration experiment; never install or run it."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf import overlay_grid as og


def require(ok, message):
    if not ok:
        raise ValueError(message)


def records(data, start=0, end=None, depth=0):
    """Strict bounded raw walk; no decompression or rewritten record headers."""
    end = len(data) if end is None else end
    require(depth < 16, "group nesting limit")
    while start < end:
        require(end - start >= 24, "truncated record header")
        sig = data[start:start + 4]
        size, flags, fid = struct.unpack_from("<III", data, start + 4)
        stop = start + size if sig == b"GRUP" else start + 24 + size
        require(start + 24 <= stop <= end, "invalid record/group size")
        if sig == b"GRUP":
            yield from records(data, start + 24, stop, depth + 1)
        else:
            yield sig, fid, flags, start + 24, stop
        start = stop


def fields(data, rec):
    require(not rec[2] & 0x40000, "compressed target unsupported")
    pos, end = rec[3:]
    while pos < end:
        require(end - pos >= 6, "truncated subrecord header")
        sig, size = struct.unpack_from("<4sH", data, pos)
        require(sig != b"XXXX", "extended target subrecord unsupported")
        begin = pos + 6
        require(begin + size <= end, "truncated subrecord body")
        yield sig, begin, begin + size
        pos = begin + size


def masters(data):
    header = next(records(data))
    require(header[0] == b"TES4", "missing TES4")
    return [data[a:b].rstrip(b"\0").decode("utf-8")
            for sig, a, b in fields(data, header) if sig == b"MAST"]


def world_id(data, name):
    found = []
    for rec in records(data):
        if rec[0] == b"WRLD":
            edids = [data[a:b].rstrip(b"\0").decode("utf-8")
                     for sig, a, b in fields(data, rec) if sig == b"EDID"]
            if edids == [name]:
                require(not rec[2] & 0x20, "deleted world")
                found.append(rec[1])
    require(len(found) == 1, "need one named world")
    require(found[0] >> 24 == len(masters(data)), "world must be core-owned")
    return found[0] & 0xFFFFFF


def replace_payload(data, rec, payload, flags):
    """Keep all bytes except the target payload, its size/flags and enclosing group sizes."""
    start, end = rec[3] - 24, rec[4]
    delta = len(payload) - (end - rec[3])
    prefix = bytearray(data[:rec[3]])

    def groups(lo, hi):
        while lo < hi:
            size = struct.unpack_from("<I", data, lo + 4)[0]
            if data[lo:lo + 4] == b"GRUP":
                stop = lo + size
                if lo < start < stop:
                    struct.pack_into("<I", prefix, lo + 4, size + delta)
                    groups(lo + 24, stop)
            else:
                stop = lo + 24 + size
            lo = stop

    groups(0, len(data))
    struct.pack_into("<II", prefix, start + 4, len(payload), flags)
    return bytes(prefix) + payload + data[end:]


def patch_registration(data, core_name, local_id, old, new):
    """Replace exactly 16 CNAM bytes after resolving the file-local master index."""
    ms = masters(data)
    require(len(ms) == len(set(ms)), "duplicate masters")
    require(ms.count(core_name) == 1 and ms[:1] == ["Starfield.esm"], "unexpected masters")
    require(0 < local_id <= 0xFFFFFF, "invalid local world ID")
    for pair in (old, new):
        require(len(pair) == 2 and all(math.isfinite(v) for v in pair), "nonfinite registration")
        require(abs(pair[0]) <= math.pi / 2 and abs(pair[1]) <= math.pi, "registration out of range")
    all_records = list(records(data))
    require([r[0] for r in all_records] == [b"TES4", b"PNDT"], "companion must contain only TES4 and PNDT")
    planet = all_records[1]
    require(planet[1] == 0x03F59A and not planet[2] & 0x20, "not active MarsPlanetData")
    if planet[2] & 0x40000:
        payload = data[planet[3]:planet[4]]
        require(len(payload) >= 4, "truncated compressed record")
        size = struct.unpack_from("<I", payload)[0]
        require(size <= 1024 * 1024, "compressed record exceeds experiment limit")
        decoder = zlib.decompressobj()
        raw = decoder.decompress(payload[4:], size + 1)
        require(len(raw) == size and decoder.eof and not decoder.unused_data
                and not decoder.unconsumed_tail, "invalid compressed record")
        expanded = replace_payload(data, planet, raw, planet[2] & ~0x40000)
        changed, details = patch_registration(expanded, core_name, local_id, old, new)
        new_record = list(records(changed))[1]
        new_raw = changed[new_record[3]:new_record[4]]
        out = replace_payload(data, planet, struct.pack("<I", size) + zlib.compress(new_raw), planet[2])
        details.update(compressed=True, cnam_payload_offset=details.pop("cnam_offset") - planet[3],
                       compressed_file_size_delta=len(out) - len(data))
        return out, details
    arrays = [(a, b) for sig, a, b in fields(data, planet)
              if sig == b"CNAM" and b - a >= 20 and (b - a) % 20 == 0]
    require(len(arrays) == 1, "need one CNAM worldspace array")
    a, b = arrays[0]
    target = (ms.index(core_name) << 24) | local_id
    entries = [(p, struct.unpack_from("<ddI", data, p)) for p in range(a, b, 20)]
    hits = [p for p, e in entries if e[2] == target]
    require(len(hits) == 1, "need one target registration")
    pos = hits[0]
    require(data[pos:pos + 16] == struct.pack("<dd", *old), "baseline registration mismatch")
    require(tuple(old) != tuple(new), "registration would be unchanged")
    require(not any(p != pos and abs(e[0] - new[0]) < 1e-9 and abs(e[1] - new[1]) < 1e-9
                    for p, e in entries), "candidate duplicates another registration")
    out = data[:pos] + struct.pack("<dd", *new) + data[pos + 16:]
    require(out[:pos] == data[:pos] and out[pos + 16:] == data[pos + 16:], "unexpected byte change")
    return out, {"compressed": False, "cnam_offset": pos, "world_form_id_in_companion": f"{target:08X}",
                 "entry_count": len(entries), "changed_byte_count": sum(x != y for x, y in zip(data, out))}


def pin(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def safe_name(name):
    require(isinstance(name, str) and name not in ("", ".", "..")
            and not any(c in name for c in "/\\:"), "expected plain filename")
    return name


def stage(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    require(output != source and source not in output.parents, "output must be separate from baseline")
    require(not output.exists(), "output already exists; choose a fresh candidate")
    params_bytes = (source / "overlays_params.json").read_bytes()
    params = json.loads(params_bytes)
    require(len(params["overlays"]) == 1, "single-overlay experiment only")
    overlay, mars = params["overlays"][0], params["mars"]
    ref = mars["reference"]
    old = (overlay["latitude"], overlay["longitude"])
    require(old == (ref["latitude"], ref["longitude"]), "baseline is not the measured reference registration")
    offset = ref["offset_cells"]
    radius = mars["radius_km"]
    require(len(offset) == 2 and all(math.isfinite(v) for v in offset), "invalid measured offset")
    require(math.isfinite(radius) and radius > 0, "invalid planet radius")
    new = og.latlon_for_offset((0, 0), old, offset, radius)
    core_name, companion_name = safe_name(params["plugin"]), safe_name(mars["plugin"])
    require(core_name != companion_name, "core and companion must differ")
    core = (source / core_name).read_bytes()
    companion = (source / companion_name).read_bytes()
    local_id = world_id(core, overlay["world"])
    candidate, details = patch_registration(companion, core_name, local_id, old, new)
    inputs = {"overlays_params.json": params_bytes, core_name: core, companion_name: companion}
    source_pins = {name: pin(data) for name, data in inputs.items()}
    # Refuse source movement before publication; published pins still require fresh preflight at installation.
    for name, expected in source_pins.items():
        require(pin((source / name).read_bytes()) == expected, f"source changed: {name}")
    report = {"status": "offline candidate; independent review and native measurement pending",
              "native_accepted": False, "complete_installation": False,
              "hypothesis": "H_ll local planet scale; landing-origin snapping remains unresolved",
              "source_stage": str(source), "source_pins": source_pins,
              "candidate": {companion_name: pin(candidate)}, "world": overlay["world"],
              "baseline_lat_lon": old, "candidate_lat_lon": new, "reference_offset_cells": offset,
              "predicted_offset_cells": og.predicted_offset(*new, old, offset, radius),
              "spawn_local_xyz": overlay["spawn"], "patch": details,
              "unchanged": "entire core, terrain, FNAM, cells, references, doors, masters and CNAM world ID",
              "acceptance": "Claude: fresh session, pin complete stack/load order, measure settled spawn minus local XY; read selected persistent reference. Zero XY does not prove door trip, Z, facing or save/reload."}
    output.mkdir(parents=True, exist_ok=False)
    # Report is written last. Any partial directory is deliberately retained and must not be deployed.
    with (output / companion_name).open("xb") as f:
        f.write(candidate)
    require(pin((output / companion_name).read_bytes()) == pin(candidate), "candidate readback mismatch")
    with (output / "registration-probe.json").open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2, allow_nan=False)
        f.write("\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-stage", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.source_stage, args.out), indent=2, allow_nan=False))
