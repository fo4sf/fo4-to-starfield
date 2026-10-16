"""Read-only Commonwealth door inventory; writes metadata, never plugins or assets."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


def key(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9A-Fa-f]{6}:[^:/\\\x00]+\.(?:esm|esp|esl)", value, re.I):
        raise ValueError(f"invalid full source key: {value!r}")
    return value.casefold()


def unique(rows, field):
    result = {}
    for row in rows:
        identity = key(row[field])
        if identity in result and result[identity] != row:
            raise ValueError(f"conflicting duplicate {field}: {identity}")
        result[identity] = row
    return result


def inventory(bands, objects, core_map, port_map, interiors, prefix="FO4Port_"):
    """Full source keys are the join keys; mapped cells do not prove functional doors."""
    doors, dependencies = [], []
    for band in bands:
        if band.get("worldspace", {}).get("editor_id") != "Commonwealth":
            raise ValueError("expected Commonwealth export")
        doors.extend(r for r in band["refs"] if r.get("type") == "Door")
        dependencies.extend(band["teleport_dependencies"])
    doors = unique(doors, "formkey")
    dependencies = unique(dependencies, "source")
    selected_objects = unique((r for r in objects["refs"] if key(r["src"]) in doors), "src")
    core_refs = {}
    for source, value in core_map["refs"].items():
        normalized = key(source)
        if normalized in core_refs:
            raise ValueError("duplicate normalized core source key")
        if not isinstance(value, str) or not re.fullmatch(r"[0-9A-Fa-f]{6}", value):
            raise ValueError("invalid core local ID")
        core_refs[normalized] = value
    port_refs = {}
    auxiliary_port_refs = []
    for identity, value in port_map.items():
        if identity.startswith("REFR:"):
            _, cell_name, source = identity.split(":", 2)
            if ":" not in source:
                auxiliary_port_refs.append(identity)
                continue  # Synthetic floor/marker reservations have no source FormKey.
            normalized = (cell_name.casefold(), key(source))
            if normalized in port_refs:
                raise ValueError("duplicate normalized port source key")
            if type(value) is not int or not 0 < value <= 0xFFFFFF:
                raise ValueError("invalid port local ID")
            port_refs[normalized] = value
    cells = unique(interiors, "formkey")
    output = []
    for source, door in sorted(doors.items()):
        teleport = door.get("teleport_destination")
        dependency = dependencies.get(source)
        warnings = []
        if teleport is not None and dependency is None:
            warnings.append("missing_destination_dependency")
        destination = teleport.get("door") if teleport is not None else None
        if dependency and (key(dependency["door"]) if dependency.get("door") else None) != (key(destination) if destination else None):
            raise ValueError(f"teleport/dependency mismatch: {source}")
        location = dependency.get("destination_cell") if dependency else None
        interior = cells.get(key(location["formkey"])) if location else None
        cell_name = prefix + interior["cell"] if interior else None
        target_cell = port_map.get("CELL:" + cell_name) if cell_name else None
        target_ref = port_refs.get((cell_name.casefold(), key(destination))) if cell_name and destination else None
        interior_door = None
        if interior and destination:
            interior_door = unique(interior["refs"], "formkey").get(key(destination))
        return_link = interior_door.get("teleport_destination") if interior_door else None
        reciprocal = bool(return_link and return_link.get("door") and key(return_link["door"]) == source)
        obj = selected_objects.get(source)
        core_id = core_refs.get(source)
        if bool(obj) != (core_id is not None):
            warnings.append("core_objects_map_disagree")
        if obj and not 0 <= obj["base"] < len(objects["bases"]):
            raise ValueError("invalid object base index")
        base = objects["bases"][obj["base"]] if obj else None
        if teleport is not None and not location:
            warnings.append("unresolved_destination_cell")
        output.append({
            "source": door["formkey"], "source_cell": door.get("source_cell"),
            "base": door.get("base_formkey"), "load_door": teleport is not None,
            "disabled": door.get("disabled"), "persistent_source": door.get("persistent"),
            "destination_door": destination, "destination_cell": location,
            "interior_export_present": interior is not None,
            "interior_cell_mapped": target_cell is not None,
            "port_cell_id": target_cell, "port_door_id": target_ref,
            "source_return_is_reciprocal": reciprocal,
            "core_reference_id": core_id, "core_object_present": obj is not None,
            "core_base_editor_id": base.get("edid") if base else None,
            "core_base_has_door_metadata": isinstance(base.get("door"), dict) if base else False,
            "warnings": warnings,
        })
    loads = [r for r in output if r["load_door"]]
    return {"schema": 1, "core_plugin": core_map["plugin"],
            "counts": {"doors": len(output), "load_doors": len(loads),
                       "exported_mapped_interiors": sum("CELL:" + prefix + c["cell"] in port_map for c in interiors),
                       "load_doors_to_mapped_interiors": sum(r["interior_cell_mapped"] for r in loads),
                       "placed_load_doors_to_mapped_interiors": sum(r["interior_cell_mapped"] and r["core_object_present"] and r["core_reference_id"] is not None for r in loads),
                       "unresolved_load_destinations": sum(not r["destination_cell"] for r in loads)},
            "doors": output, "auxiliary_port_reference_keys": sorted(auxiliary_port_refs), "native_acceptance": False,
            "limitations": ["Mapped IDs and source exports are planning evidence, not plugin readback or native acceptance.",
                            "Interior conversion means a source export plus a CELL map entry, not working scripts, doors or actors.",
                            "No destination is inferred from editor names. Unresolved dependencies remain unresolved.",
                            "Core IDs belong only to the pinned map, not another build or load-order prefix."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exports", type=Path, required=True)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--port", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("preserve the old report; choose a new output")
    pins = {}

    def read(path):
        data = path.read_bytes()
        pins[path] = hashlib.sha256(data).hexdigest()
        return json.loads(data)

    port_map = read(args.port / "formids.json")
    interiors, unavailable = [], []
    for name in sorted(k.removeprefix("CELL:FO4Port_") for k in port_map if k.startswith("CELL:FO4Port_")):
        if Path(name).name != name or "/" in name or "\\" in name:
            raise ValueError("invalid mapped cell name")
        path = args.port / (name + ".json")
        if path.is_file():
            cell = read(path)
            if cell["cell"] != name:
                raise ValueError("interior filename/export disagreement")
            interiors.append(cell)
        else:
            unavailable.append(name)
    paths = sorted(args.exports.glob("band_*.json"))
    if not paths:
        raise ValueError("no band exports")
    # Retain only door/dependency metadata while reading large bands sequentially.
    bands = []
    for path in paths:
        band = read(path)
        bands.append({"worldspace": band["worldspace"],
                      "refs": [r for r in band["refs"] if r.get("type") == "Door"],
                      "teleport_dependencies": band["teleport_dependencies"]})
    report = inventory(bands, read(args.core / "objects.json"), read(args.core / "formids.json"), port_map, interiors)
    report["mapped_cells_without_source_export"] = unavailable
    report["input_pins"] = [{"path": str(p.resolve()), "sha256": sha} for p, sha in pins.items()]
    for path, sha in pins.items():
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != sha:
                raise ValueError(f"input changed during inventory: {path.name}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(report["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
