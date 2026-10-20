"""Offline placement-frame oracle for plugins that add refs to a core worldspace.

Reports every REFR/ACHR placed into the shared worldspace: position, exterior cell
computed from that position (Starfield 100 m grid), whether the core contains a
local LAND record in that cell. External SFBK/BTD or inherited terrain is not
decoded here: absence of local LAND is coverage UNKNOWN, not missing terrain.
Optional --anchor EDID measures Euclidean source-WRLD distance in metres, using
the plugin's overrides of core references by canonical source key. It does not
measure a runtime merge offset or prove native placement/activation.
Flags unknown coverage or a computed cell that disagrees with its parent CELL's XCLC
(persistent cell XCLC is ignored for spatial checks).

Exits 1 when any flag or inconclusive (missing position) is raised.

Usage:
  python scripts/oracles/placement_frame.py --plugin mission.esp --core core.esp \\
      --world-edid TestWorld --json
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fo4sf.fo4land import Plugin, iter_items, iter_subrecords, record_data  # noqa: E402
from fo4sf.terrain_grid import sf_cell_of, SF_CELL_M  # noqa: E402


def canonical_world(plugin, fid, kind="world"):
    """Resolve an on-disk full-plugin FormID via TES4 MAST order and self name.

    These are source FormKeys, not runtime FF/FE mappings or merge-frame proof.
    """
    names = []
    for sig, raw in iter_subrecords(record_data(plugin.buf, 0)):
        if sig != b"MAST":
            continue
        if not raw.endswith(b"\0"):
            raise ValueError("world master name is not terminated")
        name = raw[:-1].decode("cp1252").casefold()
        if not name or any(c in name for c in ("/", "\\", ":", "\0")) or name in names:
            raise ValueError("invalid or duplicate world master name")
        names.append(name)
    own = Path(plugin.path).name.casefold()
    if own in names:
        raise ValueError("world plugin lists itself as a master")
    names.append(own)
    index, local = fid >> 24, fid & 0xFFFFFF
    if index >= len(names) or index >= 0xFE or local == 0:
        raise ValueError(f"{kind} FormID {fid:08X} has no supported owning master")
    return {"plugin": names[index], "local_id": f"{local:06X}"}


def reference_names(plugin):
    """Read placed EDID/header flags throughout the source plugin.

    Outside-world overrides must invalidate an old core anchor rather than
    leave its stale coordinates available for the selected world.
    """
    names = {}

    def walk(first, last):
        for item in iter_items(plugin.buf, first, last):
            if item[0] == "GRUP":
                walk(item[1] + 24, item[2])
            elif item[0] in (b"REFR", b"ACHR"):
                fields = [raw for sig, raw in iter_subrecords(record_data(plugin.buf, item[1]))
                          if sig == b"EDID"]
                if len(fields) > 1:
                    raise ValueError("duplicate EDID fields on placed reference")
                edid = None
                if fields:
                    if not fields[0].endswith(b"\0") or b"\0" in fields[0][:-1]:
                        raise ValueError("invalid placed-reference EDID")
                    edid = fields[0][:-1].decode("cp1252")
                names.setdefault(item[3], []).append({"edid": edid, "record_flags": item[2]})

    walk(plugin.body, len(plugin.buf))
    return names


def collect_refs(plugin_path, world_edid, with_names=False):
    """Return local LAND cells, refs and canonically identified source WRLD."""
    with Plugin(plugin_path) as p:
        source_hash = hashlib.sha256(p.buf).hexdigest()
        data = p.read_world(world_edid, cells=None, refs=True)
        world_key = canonical_world(p, data["world_fid"])
        cells_with_coverage = set()
        sources = list(data["cells"].values())
        persistent = data.get("persistent_cell")
        if persistent:
            sources.append(persistent)
        for cell in sources:
            if not cell:
                continue
            # fo4land does not expose per-cell sfbk/btd keys. Never infer absent
            # external terrain from an empty exterior CELL or those missing keys.
            has_terrain = cell.get("vhgt") is not None or cell.get("land_fid") is not None
            xy = (cell["x"], cell["y"]) if cell.get("x") is not None else None
            if xy and has_terrain and not cell.get("persistent_cell"):
                cells_with_coverage.add(xy)
        refs = []
        for cell in sources:
            if not cell:
                continue
            is_persistent = bool(cell.get("persistent_cell"))
            parent = (cell["x"], cell["y"]) if cell.get("x") is not None else None
            for bucket in ("refs", "persistent_refs"):
                for r in cell.get(bucket, []):
                    rr = dict(r)
                    rr["parent_xy"] = parent
                    rr["parent_fid"] = cell["fid"]
                    rr["is_persistent_parent"] = is_persistent
                    refs.append(rr)
        source_refs = {}
        if with_names:
            metadata = reference_names(p)
            for fid, rows in metadata.items():
                if len(rows) != 1:
                    raise ValueError("missing or duplicate source reference for anchor lookup")
                source_refs[fid] = dict(rows[0], fid=fid, in_selected_world=False,
                                       source_key=canonical_world(p, fid, kind="reference"))
            for ref in refs:
                if ref["fid"] not in source_refs:
                    raise ValueError("missing source reference for anchor lookup")
                ref.update(source_refs[ref["fid"]])
                ref["in_selected_world"] = True
                source_refs[ref["fid"]] = ref
        if source_hash != hashlib.sha256(p.buf).hexdigest():
            raise ValueError("plugin changed during placement read")
        return cells_with_coverage, refs, data["world_fid"], world_key, source_hash, list(source_refs.values())


def valid_position(pos):
    return bool(pos and len(pos) == 3 and all(math.isfinite(float(v)) for v in pos))


def select_anchor(name, core_refs, plugin_records, identity_ok):
    """Select the effective source reference; never guess among distinct keys."""
    result = {"requested_edid": name, "distance_frame": "source WRLD metres; no runtime merge adjustment"}
    if not identity_ok:
        return dict(result, status="world_identity")
    effective = {}
    for role, refs in [("core", core_refs), ("plugin", plugin_records)]:
        for ref in refs:
            key = (ref["source_key"]["plugin"], ref["source_key"]["local_id"])
            if role == "plugin" and key not in effective and not ref["in_selected_world"]:
                continue
            effective[key] = (role, ref)
    matches = [(role, ref) for role, ref in effective.values()
               if ref.get("edid") is not None and ref["edid"].casefold() == name.casefold()]
    # Deleted (0x20) matches are tombstones, not fallback candidates. Initially
    # disabled references can still supply a file-coordinate measurement; no
    # runtime enabled/activation claim is made (flags are included in the report).
    live = [(role, ref) for role, ref in matches if not ref["record_flags"] & 0x20]
    inside = [(role, ref) for role, ref in live if ref["in_selected_world"]]
    if not inside:
        status = "outside_selected_world" if live else "deleted" if matches else "missing"
        return dict(result, status=status)
    if len(inside) != 1:
        return dict(result, status="ambiguous", candidates=len(inside))
    role, ref = inside[0]
    if not valid_position(ref.get("pos")):
        return dict(result, status="invalid_position", source_key=ref["source_key"])
    return dict(result, status="ok", edid=ref["edid"], fid=f"{ref['fid']:08X}",
                source_key=ref["source_key"], source_role=role, pos=list(ref["pos"]),
                record_flags=ref["record_flags"])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plugin", required=True)
    ap.add_argument("--core", required=True)
    ap.add_argument("--world-edid", required=True, help="EDID of the shared worldspace")
    ap.add_argument("--anchor", help="case-insensitive placed-reference EDID for source-coordinate distance")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.anchor is not None and not args.anchor.strip():
        ap.error("--anchor must be a nonempty EDID")

    try:
        core_cells, core_refs, core_fid, core_key, core_hash, _ = collect_refs(
            args.core, args.world_edid, with_names=args.anchor is not None)
        _, plugin_refs, plugin_fid, plugin_key, plugin_hash, plugin_records = collect_refs(
            args.plugin, args.world_edid, with_names=args.anchor is not None)
    except Exception as exc:
        print(f"failed to read plugins: {exc}", file=sys.stderr)
        return 2

    identity_ok = plugin_key == core_key
    if not identity_ok:
        print(f"warning: world identity mismatch plugin={plugin_key} core={core_key}", file=sys.stderr)
    anchor = select_anchor(args.anchor, core_refs, plugin_records, identity_ok) if args.anchor is not None else None

    flags = []
    report = []
    for r in plugin_refs:
        pos = r.get("pos")
        has_pos = valid_position(pos)
        if not has_pos:
            entry = {
                "fid": f"{r.get('fid', 0):08X}",
                "type": r.get("type"),
                "pos": None,
                "computed_cell": None,
                "parent_cell": list(r.get("parent_xy")) if r.get("parent_xy") else None,
                "core_has_coverage": None,
                "flag": True,
                "reason": "missing_or_invalid_position",
            }
            if anchor is not None:
                entry["anchor_distance_m"] = None
            report.append(entry)
            flags.append(entry)
            continue

        # Positions are treated as Starfield metres (core worldspace)
        computed = sf_cell_of(pos[0], pos[1])
        parent = r.get("parent_xy")
        is_persistent = r.get("is_persistent_parent", False)
        has_coverage = True if identity_ok and computed in core_cells else None
        # Persistent parent XCLC is not a spatial constraint
        disagree = (not is_persistent) and parent is not None and tuple(parent) != computed
        reasons = []
        if not identity_ok:
            reasons.append("world_identity")
        if disagree:
            reasons.append("parent_mismatch")
        if has_coverage is None:
            reasons.append("coverage_unknown")
        flag = bool(reasons)
        entry = {
            "fid": f"{r.get('fid', 0):08X}",
            "type": r.get("type"),
            "pos": [round(float(v), 2) for v in pos],
            "computed_cell": list(computed),
            "parent_cell": list(parent) if parent else None,
            "core_has_coverage": has_coverage,
            "flag": flag,
            "reason": reasons[0] if reasons else None,
            "reasons": reasons,
        }
        if anchor is not None:
            entry["anchor_distance_m"] = math.dist(pos, anchor["pos"]) if anchor["status"] == "ok" else None
        report.append(entry)
        if flag:
            flags.append(entry)

    out = {
        "world_fid": f"{core_fid:08X}",
        "plugin_world_fid": f"{plugin_fid:08X}",
        "identity_ok": identity_ok,
        "world_key": core_key,
        "plugin_world_key": plugin_key,
        "source_sha256": {"core": core_hash, "plugin": plugin_hash},
        "core_coverage_cells": len(core_cells),
        "coverage_basis": "local LAND records only; external/inherited terrain unassessed",
        "refs": report,
        "flagged": len(flags),
        "cell_size_m": SF_CELL_M,
    }
    if anchor is not None:
        out["anchor"] = anchor
    if args.json:
        print(json.dumps(out, indent=2, allow_nan=False))
    else:
        print(f"world {out['world_fid']} (plugin {out['plugin_world_fid']})  "
              f"core coverage cells: {out['core_coverage_cells']}  cell={SF_CELL_M}m")
        print(f"refs: {len(report)}  flagged: {len(flags)}")
        if anchor is not None:
            print(f"anchor {args.anchor!r}: {anchor['status']} ({anchor['distance_frame']})")
        for e in report:
            mark = "FLAG" if e["flag"] else "ok  "
            print(f"  {mark} {e['fid']} {e['type']} pos={e['pos']} "
                  f"cell={e['computed_cell']} parent={e['parent_cell']} "
                  f"coverage={e['core_has_coverage']} reason={e.get('reason')}"
                  + (f" anchor_distance_m={e['anchor_distance_m']}" if anchor is not None else ""))
    anchor_failed = anchor is not None and anchor["status"] != "ok"
    return 1 if flags or not identity_ok or anchor_failed else 0


if __name__ == "__main__":
    sys.exit(main())
