"""Read-only audit of TerrainOverlays container or loose-item records; never native acceptance."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from fo4sf import fo4land, terrain_grid  # noqa: E402

_DELETED = 0x20  # Mutagen 0.55.0-alpha.67 StarfieldMajorRecordFlag.Deleted; IsDeleted also verifies this bit.
_PROMOTED_REFERENCES = ("containers", "items", "activators", "terminals", "workshops", "flora", "benches", "doors")
# Benches reference a vanilla full FormKey, not a plugin-local owned base ID.
_OWNED_BASES = tuple(kind for kind in _PROMOTED_REFERENCES if kind != "benches")


def _one(fields, sig):
    values = [v for s, v in fields if s == sig]
    if len(values) != 1:
        raise ValueError(f"expected exactly one {sig.decode()} field")
    return values[0]


def _text(data):
    if not data.endswith(b"\0") or b"\0" in data[:-1]:
        raise ValueError("string is not a single terminated value")
    # Verified against the installed Mutagen writer's inline FULL/MODL bytes.
    return data[:-1].decode("cp1252")


def _fields(data):
    """Bound every subrecord, including unknown fields and XXXX size prefixes."""
    result, off, extended = [], 0, None
    while off < len(data):
        if off + 6 > len(data):
            raise ValueError("truncated subrecord header")
        sig, size = struct.unpack_from("<4sH", data, off)
        off += 6
        if sig == b"XXXX":
            if size != 4 or extended is not None or off + 4 > len(data):
                raise ValueError("invalid extended subrecord size")
            extended, = struct.unpack_from("<I", data, off)
            off += 4
            continue
        if extended is not None:
            size, extended = extended, None
        if off + size > len(data):
            raise ValueError("subrecord payload exceeds record bounds")
        result.append((sig, bytes(data[off:off + size])))
        off += size
    if extended is not None:
        raise ValueError("extended size has no following subrecord")
    return result


def _local(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{6}", value) or int(value, 16) == 0:
        raise ValueError(f"invalid local record identity: {value!r}")
    return int(value, 16)


def _vector(value, size):
    if not isinstance(value, list) or len(value) != size or any(type(v) not in (int, float) or not math.isfinite(v) for v in value):
        raise ValueError("expected finite numeric coordinates")
    return value


def _scan(blob, wanted, container_bases, base_signature=b"CONT"):
    if len(blob) < 24 or blob[:4] != b"TES4":
        raise ValueError("not a complete plugin header")
    hsize, flags = struct.unpack_from("<II", blob, 4)
    if 24 + hsize > len(blob) or flags & 0x80:
        raise ValueError("truncated or localized plugin; inline names required")
    masters = [_text(v) for s, v in _fields(blob[24:24 + hsize]) if s == b"MAST"]
    if len(set(m.lower() for m in masters)) != len(masters):
        raise ValueError("duplicate masters")
    records, cells, worlds, seen = {}, {}, {}, set()
    cont_count = 0
    uses = Counter()

    own = len(masters) << 24
    wanted = {own | i for i in wanted}
    container_bases = {own | i for i in container_bases}

    def walk(start, end, world=None, cell=None, group=None, top=None):
        nonlocal cont_count
        off = start
        while off < end:
            if off + 24 > end:
                raise ValueError("truncated record/group header")
            sig, size = struct.unpack_from("<4sI", blob, off)
            stop = off + (size if sig == b"GRUP" else 24 + size)
            if stop > end or stop <= off or (sig == b"GRUP" and size < 24):
                raise ValueError("record/group outside its enclosing bytes")
            if sig == b"GRUP":
                label, kind = struct.unpack_from("<Ii", blob, off + 8)
                if kind in (8, 9) and (cell is None or label != cell):
                    raise ValueError("child group differs from its enclosing cell")
                walk(off + 24, stop, label if kind == 1 else world,
                     label if kind in (6, 8, 9) else cell, kind,
                     blob[off + 8:off + 12] if kind == 0 else top)
            else:
                record_flags, fid = struct.unpack_from("<II", blob, off + 8)
                if fid in seen:
                    raise ValueError(f"duplicate plugin record {fid:08X}")
                seen.add(fid)
                if sig == base_signature:
                    cont_count += 1
                if fid in wanted or sig in (b"CELL", b"WRLD", b"REFR"):
                    fields = _fields(fo4land.record_data(blob, off))
                    if sig == b"REFR":
                        base, = struct.unpack("<I", _one(fields, b"NAME"))
                        if base in container_bases:
                            uses[base] += 1
                    if sig == b"CELL":
                        grid = [v for s, v in fields if s == b"XCLC"]
                        cells[fid] = (world, struct.unpack_from("<ii", grid[0]) if len(grid) == 1 else None)
                    elif sig == b"WRLD":
                        worlds[fid] = _text(_one(fields, b"EDID"))
                    # Retain the owning records too: a structurally correct placement under a deleted
                    # CELL/WRLD is not an active container. Unrelated records remain outside this audit.
                    if fid in wanted or sig in (b"CELL", b"WRLD"):
                        records[fid] = (sig, record_flags, fields, cell, group, world, top)
            off = stop
    walk(24 + hsize, len(blob))
    return masters, records, cells, worlds, cont_count, uses


def audit(blob, objects, ids, *, plugin_name, baseline=None, kind="containers"):
    """Compare one promoted record class plus optional declared baseline maps.

    Ordinary static geometry, other promoted classes, assets and engine behavior are
    outside this audit; retain the existing full reference/dependency checks.
    """
    report = {"offline_passed": False, "runtime_accepted": False, "errors": [], "audit_kind": kind,
              kind + "_checked": 0, "baseline_maps_checked": baseline is not None,
              "plugin_sha256": hashlib.sha256(blob).hexdigest()}
    errors = report["errors"]
    try:
        if kind not in ("containers", "items"):
            raise ValueError("audit kind must be containers or items")
        noun, signature = ("container", b"CONT") if kind == "containers" else ("item", b"MISC")
        conts = objects[kind]
        if not isinstance(conts, list) or not conts:
            raise ValueError("no explicit promoted entries to audit")
        sources = [c["src"] for c in conts]
        if len(set(sources)) != len(sources) or set(ids[kind]) != set(sources):
            raise ValueError("promoted sources/mapping do not match uniquely")
        if set(sources) & {r["src"] for r in objects["refs"]}:
            raise ValueError("promoted sources still appear in ordinary placements")
        if ids["plugin"].lower() != plugin_name.lower() or ids["world"] != objects["world"]:
            raise ValueError("promoted plugin/world metadata differs")
        def reference_ids(mapping):
            result = {src: _local(value) for src, value in mapping["refs"].items()}
            for category in _PROMOTED_REFERENCES:
                for src, pair in mapping.get(category, {}).items():
                    if src in result:
                        raise ValueError("source appears in both ordinary and promoted references")
                    result[src] = _local(pair["ref"])
            if len(set(result.values())) != len(result):
                raise ValueError("declared source reference identities are not unique")
            return result

        new_references = reference_ids(ids)
        pairs = {src: (_local(ids[kind][src]["base"]), _local(ids[kind][src]["ref"])) for src in sources}
        base_ids = {pair[0] for pair in pairs.values()}
        if base_ids & set(new_references.values()):
            raise ValueError("promoted base overlaps declared reference identities")
        other_bases = {_local(pair["base"]) for category in _OWNED_BASES if category != kind
                       for pair in ids.get(category, {}).values()}
        if base_ids & other_bases:
            raise ValueError("promoted classes share a base identity")
        local_ids = {v for pair in pairs.values() for v in pair}
        # Master order in the actual header determines file-local link prefixes.
        masters, recs, cells, worlds, count, uses = _scan(blob, local_ids, base_ids, signature)
        own = len(masters) << 24
        expected_uses = Counter(own | pair[0] for pair in pairs.values())
        if count != len(base_ids):
            errors.append(f"{signature.decode()} record count differs from {noun} definitions")
        report[noun + "_base_records"] = count
        links = {name.lower(): n << 24 for n, name in enumerate(masters + [plugin_name])}
        for c in conts:
            src = c["src"]
            try:
                bid, rid = (own | v for v in pairs[src])
                base, ref = recs[bid], recs[rid]
                if base[0] != signature or base[4] != 0 or base[6] != signature or ref[0] != b"REFR" or ref[6] != b"WRLD":
                    raise ValueError(f"mapped records are not {signature.decode()}/REFR")
                if base[1] & _DELETED:
                    raise ValueError("promoted base is deleted")
                if ref[1] & _DELETED:
                    raise ValueError("promoted reference is deleted")
                if uses[bid] != expected_uses[bid]:
                    errors.append(f"{src}: placed reference count differs for promoted base")
                if _text(_one(base[2], b"EDID")) != c["edid"] or _text(_one(base[2], b"FULL")) != c["name"]:
                    errors.append(f"{src}: promoted editor ID/name differs")
                if _text(_one(base[2], b"MODL")).replace("\\", "/").lower() != c["model"].replace("\\", "/").lower():
                    errors.append(f"{src}: promoted model differs")
                if kind == "containers":
                    actual = Counter(struct.unpack("<Ii", v) for s, v in base[2] if s == b"CNTO")
                    expected = Counter()
                    for item in c["items"]:
                        plugin, local = item["form"].rsplit(":", 1)
                        count = item["count"]
                        if type(count) is not int or not 1 <= count <= 0x7FFFFFFF:
                            raise ValueError("invalid inventory count")
                        expected[(links[plugin.lower()] | _local(local), count)] += 1
                    if not expected or actual != expected:
                        errors.append(f"{src}: inventory differs")
                else:
                    value, weight = struct.unpack("<if", _one(base[2], b"DATA"))
                    expected_value, expected_weight = c["value"], c["weight"]
                    if type(expected_value) is not int or not 0 <= expected_value <= 0x7FFFFFFF:
                        raise ValueError("invalid expected item value")
                    expected_weight = _vector([expected_weight], 1)[0]
                    if expected_weight < 0 or expected_weight > 3.4028234663852886e38:
                        raise ValueError("invalid expected item weight")
                    expected_weight = struct.unpack("<f", struct.pack("<f", expected_weight))[0]
                    if value != expected_value or not math.isfinite(weight) or weight != expected_weight:
                        errors.append(f"{src}: item value/weight differs")
                if struct.unpack("<I", _one(ref[2], b"NAME"))[0] != bid:
                    errors.append(f"{src}: reference base differs")
                data = struct.unpack("<6f", _one(ref[2], b"DATA"))
                pos, rot = _vector(c["pos"], 3), _vector(c["rot"], 3)
                if any(not math.isfinite(v) for v in data) or any(abs(a - b) > 1e-3 for a, b in zip(data[:3], pos)) or any(abs(a - b) > 1e-5 for a, b in zip(data[3:], rot)):
                    errors.append(f"{src}: position/rotation differs")
                scales = [struct.unpack("<f", v)[0] for s, v in ref[2] if s == b"XSCL"]
                scale = scales[0] if scales else 1.0
                expected_scale = _vector([c["scale"]], 1)[0]
                if len(scales) > 1 or not math.isfinite(scale) or abs(scale - expected_scale) > 1e-4:
                    errors.append(f"{src}: scale differs")
                if ref[1] & (0x400 | 0x800) or ref[4] != 9:
                    errors.append(f"{src}: reference is not active temporary placement")
                world, grid = cells[ref[3]]
                if recs[ref[3]][1] & _DELETED:
                    raise ValueError("owning cell is deleted")
                if recs[world][1] & _DELETED:
                    raise ValueError("owning world is deleted")
                if ref[5] != world or worlds.get(world) != objects["world"] or grid != tuple(c["cell"]) or tuple(c["cell"]) != terrain_grid.sf_cell_of(*pos[:2]):
                    errors.append(f"{src}: world/cell differs")
                report[kind + "_checked"] += 1
            except (AttributeError, KeyError, TypeError, ValueError, struct.error, UnicodeError) as error:
                errors.append(f"{src}: invalid promoted evidence: {error}")
        if baseline is not None:
            old_references = reference_ids(baseline)
            old_bases = {key: _local(value) for key, value in baseline["bases"].items()}
            new_bases = {key: _local(value) for key, value in ids["bases"].items()}
            for category, old, new in (("bases", old_bases, new_bases), ("refs", old_references, new_references)):
                changed = [key for key in old.keys() & new.keys() if old[key] != new[key]]
                missing = old.keys() - new.keys()
                report[category + "_ids_changed"] = len(changed)
                report[category + "_ids_missing"] = len(missing)
                if changed or missing:
                    errors.append(f"baseline {category}: {len(changed)} changed, {len(missing)} missing identities")
            for category in _OWNED_BASES:
                for src, previous in baseline.get(category, {}).items():
                    current = ids.get(category, {}).get(src)
                    if current is None or _local(previous["base"]) != _local(current["base"]):
                        errors.append(f"{src}: baseline promoted {category} base changed or disappeared")
            if baseline["plugin"].lower() != plugin_name.lower() or baseline["world"] != objects["world"]:
                errors.append("baseline plugin/world differs")
        report["offline_passed"] = not errors and report[kind + "_checked"] == len(conts)
    except (AttributeError, KeyError, TypeError, ValueError, struct.error, UnicodeError, OverflowError, zlib.error, RecursionError) as error:
        errors.append(f"invalid audit inputs/plugin: {error}")
    return report


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plugin", "objects", "ids", "out"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--baseline-ids")
    parser.add_argument("--kind", choices=("containers", "items"), default="containers")
    args = parser.parse_args()
    pins = {}
    try:
        def read(path):
            data = Path(path).read_bytes()
            pins[str(Path(path).resolve())] = hashlib.sha256(data).hexdigest()
            return data
        def document(path):
            return json.loads(read(path).decode("utf-8-sig"), object_pairs_hook=_unique)
        report = audit(read(args.plugin), document(args.objects), document(args.ids), plugin_name=Path(args.plugin).name,
                       baseline=document(args.baseline_ids) if args.baseline_ids else None, kind=args.kind)
    except (OSError, ValueError) as error:
        report = {"offline_passed": False, "runtime_accepted": False, "errors": [str(error)]}
    report["input_sha256"] = pins
    try:
        with Path(args.out).open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    except OSError as error:
        print(f"cannot publish report: {error}", file=sys.stderr)
        return 2
    return 0 if report["offline_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
