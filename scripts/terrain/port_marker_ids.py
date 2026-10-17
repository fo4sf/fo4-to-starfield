"""Checked bootstrap and pure reservation planning for interior arrival markers.

No disk writes, caller integration, or save-compatibility guarantee. The caller
must durably publish the returned state under a writer lease BEFORE publishing
either plugin, pin its hash externally, and refuse missing state on resume.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import re

import vmad_patch as vp

MAX_ID = 0xFFFFFF


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def plugin_key(name):
    _require(isinstance(name, str) and name == name.strip()
             and re.fullmatch(r'[^<>:"/\\|?*\x00-\x1f]+\.(?:esm|esp)', name, re.I),
             "expected a plain full-plugin filename (.esm or .esp)")
    return name.casefold()


def source_key(source):
    _require(isinstance(source, str), "source must be a full FormKey")
    fid, sep, plugin = source.partition(":")
    _require(sep and re.fullmatch(r"[0-9a-fA-F]{6}", fid) and int(fid, 16) > 0,
             "source must contain six hex digits and its owning plugin")
    return fid.lower() + ":" + plugin_key(plugin)


def _local(value):
    _require(type(value) is int and 0x800 <= value <= MAX_ID, "invalid plugin-local ID")
    return value


def _hex_local(value):
    _require(isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{6}", value), "invalid local hex ID")
    return _local(int(value, 16))


def _pairs(items):
    out = {}
    for key, value in items:
        _require(key not in out, "duplicate JSON key")
        out[key] = value
    return out


def _json(raw):
    try:
        return json.loads(raw, object_pairs_hook=_pairs)
    except (TypeError, UnicodeError, json.JSONDecodeError) as err:
        raise ValueError("invalid JSON") from err


def _map(raw):
    data = _json(raw)
    _require(isinstance(data, dict), "map must be an object")
    out = {}
    for key, value in data.items():
        _require(isinstance(key, str) and key and key == key.strip(), "invalid map identity")
        canonical = key.casefold()
        _require(canonical not in out, "ambiguous map identity")
        out[canonical] = _local(value)
    return out


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _snapshot(raw, map_raw, name):
    plugin = vp.Plugin(raw)
    records = plugin.records()  # Reject duplicate serialized record IDs.
    masters = [plugin_key(n) for n in plugin.masters()]
    _require(len(masters) < 254 and len(set(masters)) == len(masters), "invalid full-plugin masters")
    own = len(masters) << 24
    identities = _map(map_raw)
    _require(not any(k.startswith("mark:") for k in identities), "base map already contains generated markers")
    _require(len(set(identities.values())) == len(identities), "ambiguous base map IDs")
    for key, local in identities.items():
        record = records.get(own | local)
        # Real port maps retain IDs for filtered/unemitted sources. Those IDs
        # remain occupied even when there is no current serialized record.
        _require(record is None or key.partition(":")[0].upper() == record[0].decode("ascii"),
                 "base map identity names a different record type")
    next_id = plugin.hedr()[2]
    _require(next_id == plugin.own_max(len(masters)) + 1 and 0x800 <= next_id <= MAX_ID + 1,
             "base HEDR next ID does not match actual records")
    fingerprints = {}
    for record, path in plugin.walk():
        location = json.dumps([(kind, label.hex()) for kind, label in path], separators=(",", ":")).encode()
        fingerprints[f"{record.fid:08x}"] = _digest(record.serialize() + location)
    return {"plugin": plugin_key(name), "sha256": _digest(raw), "masters": masters,
            "next_id": max(next_id, max(identities.values(), default=0x7FF) + 1),
            "source_ids": identities, "records": fingerprints}


def _occupied(base):
    return {int(fid, 16) & MAX_ID for fid in base["records"]
            if int(fid, 16) >> 24 == len(base["masters"])} | set(base["source_ids"].values())


def _validate(state):
    _require(isinstance(state, dict) and set(state) == {"format", "base", "reservations", "next_id"}
             and type(state["format"]) is int and state["format"] == 1, "invalid reservation schema")
    base = state["base"]
    _require(isinstance(base, dict) and set(base) == {"plugin", "sha256", "masters", "next_id", "source_ids", "records"},
             "invalid base snapshot")
    _require(plugin_key(base["plugin"]) == base["plugin"], "noncanonical plugin")
    _require(isinstance(base["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", base["sha256"]), "invalid base hash")
    _require(isinstance(base["masters"], list) and len(base["masters"]) < 254
             and all(plugin_key(n) == n for n in base["masters"])
             and len(set(base["masters"])) == len(base["masters"]), "invalid masters")
    _require(isinstance(base["records"], dict) and all(
        re.fullmatch(r"[0-9a-f]{8}", k) and isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v)
        for k, v in base["records"].items()), "invalid record fingerprints")
    _require(isinstance(base["source_ids"], dict), "invalid base identities")
    for key, value in base["source_ids"].items():
        _require(key and key == key.strip().casefold() and not key.startswith("mark:")
                 and _local(value), "invalid base identity")
    _require(len(set(base["source_ids"].values())) == len(base["source_ids"]), "duplicate base IDs")
    occupied = _occupied(base)
    _require(type(base["next_id"]) is int and base["next_id"] == max(occupied, default=0x7FF) + 1,
             "invalid base next ID")
    reservations = state["reservations"]
    _require(isinstance(reservations, dict), "invalid reservations")
    for source, value in reservations.items():
        _require(source_key(source) == source, "noncanonical source")
        _require(_local(value) not in occupied, "marker reservation collides with base record")
    _require(len(set(reservations.values())) == len(reservations), "duplicate marker IDs")
    _require(type(state["next_id"]) is int and state["next_id"] == max(
        base["next_id"], max(reservations.values(), default=0x7FF) + 1), "invalid reservation next ID")


@dataclass(frozen=True)
class Plan:
    state: bytes
    sha256: str
    assignments: dict


def _plan(state, sources):
    _validate(state)
    raw = (json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return Plan(raw, _digest(raw), {s: state["reservations"][s] for s in sources})


def bootstrap(base_raw, base_map_raw, patched_raw, patched_map_raw, doors, *, plugin, core_plugin):
    """Import an existing checked generation; never infer IDs from new door order."""
    base = _snapshot(base_raw, base_map_raw, plugin)
    target = plugin_key(plugin)
    plugin_key(core_plugin)
    _require(isinstance(doors, list) and doors, "bootstrap needs actual door entries")
    reservations, seen_doors = {}, set()
    expected_map = dict(base["source_ids"])
    cells = {v: k.removeprefix("cell:") for k, v in base["source_ids"].items() if k.startswith("cell:")}
    original_records = vp.Plugin(base_raw).records()
    own = len(base["masters"]) << 24
    for door in doors:
        source = source_key(door["src"])
        dest = door["destination"]
        _require(source not in reservations and plugin_key(dest["plugin"]) == target,
                 "duplicate source or wrong destination owner")
        marker, ref, cell = _local(dest["id"]), _hex_local(dest["ref"]), _hex_local(dest["cell"])
        _require(ref not in seen_doors and marker not in reservations.values(), "duplicate endpoint")
        seen_doors.add(ref)
        _require(cell in cells, "destination CELL missing from base map")
        _require(original_records.get(own | cell, (None,))[0] == b"CELL", "destination CELL is not emitted")
        record = original_records.get(own | ref)
        _require(record is not None and record[0] == b"REFR" and record[3][-2:] == (
            (vp.GROUP_CELL_CHILDREN, own | cell), (vp.GROUP_TEMPORARY, own | cell)),
            "interior door is not emitted in its declared cell")
        inner_source = source_key(dest["door"])
        _require(base["source_ids"].get(f"refr:{cells[cell]}:{inner_source}") == ref,
                 "interior source reference does not match base map")
        for field in ("pos", "rot"):
            vector = dest["arrival"][field]
            _require(isinstance(vector, list) and len(vector) == 3 and all(
                type(v) in (int, float) and math.isfinite(v) for v in vector), "invalid marker transform")
        _hex_local(door["ids"]["arrival"])
        reservations[source] = marker
        expected_map[f"mark:{cells[cell]}:{source}"] = marker
    _require(_map(patched_map_raw) == expected_map, "patched marker map differs from checked source identities")
    # Keep original filename spelling for the raw VMAD comparison.
    checks = vp.check_port(vp.Plugin(base_raw), vp.Plugin(patched_raw), doors, core_plugin)
    failed = [message for message, good in checks if not good]
    _require(not failed, "raw generation check failed: " + "; ".join(failed))
    state = {"format": 1, "base": base, "reservations": reservations,
             "next_id": max(base["next_id"], max(reservations.values()) + 1)}
    return _plan(state, reservations)


def reserve(state_raw, expected_sha256, base_raw, base_map_raw, sources, *, plugin):
    """Plan against externally pinned state; caller must persist it before use.

    Supports unchanged bases and append-only base growth. Existing base records
    or source IDs changing need a separately reviewed migration, not guessing.
    """
    _require(_digest(state_raw) == expected_sha256, "reservation state hash mismatch")
    state = _json(state_raw)
    _validate(state)
    before = state["base"]
    after = _snapshot(base_raw, base_map_raw, plugin)
    _require(before["plugin"] == after["plugin"] and before["masters"] == after["masters"], "plugin lineage changed")
    _require(all(after["source_ids"].get(k) == v for k, v in before["source_ids"].items()), "base source identities changed")
    _require(all(after["records"].get(k) == v for k, v in before["records"].items()), "existing base records changed")
    _require(not (_occupied(after) & set(state["reservations"].values())), "base growth occupied a reserved marker ID")
    selected = [source_key(source) for source in sources]
    _require(len(set(selected)) == len(selected), "duplicate requested source identity")
    next_id = max(state["next_id"], after["next_id"])
    for source in sorted(set(selected) - state["reservations"].keys()):
        _require(next_id <= MAX_ID, "marker ID range exhausted")
        state["reservations"][source] = next_id
        next_id += 1
    state["base"], state["next_id"] = after, next_id
    return _plan(state, selected)
