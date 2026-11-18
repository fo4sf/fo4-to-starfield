"""Commonwealth DLC & Next-Gen load-order diff report (`WD4`).

Compares Fallout 4's `Commonwealth` (`0x00003C`) across:
  1. Depot `1.10.163` `Fallout4.esm` vs Next-Gen `Fallout4.esm` (isolating base-game drift), and
  2. Next-Gen `Fallout4.esm` + DLC load order (`DLCRobot.esm`, `DLCworkshop01.esm`, `DLCCoast.esm`,
     `DLCworkshop02.esm`, `DLCworkshop03.esm`, `DLCNukaWorld.esm`),
resolving every changed reference against `FO4TerrainCore.esm`'s `formids.json` (`resolved` to a 6-hex core FormID
and section, or marked `new`).

Writes JSON reports only to `--out` outside Git worktrees and game folders (`R4`). Does not write an override `.esm`.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import struct
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
if os.path.join(REPO_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from fo4sf import fo4land, terrain_grid as tg  # noqa: E402
from fo4sf.terrain.path_guard import refuse_unsafe_output_path  # noqa: E402

COMMONWEALTH_LOCAL_FID = 0x00003C
FLAG_DELETED = 0x00000020
FLAG_PERSISTENT = 0x00000400
FLAG_DISABLED = 0x00000800
FLAG_COMPRESSED = 0x00040000

CORE_REF_SECTIONS: Tuple[str, ...] = (
    "refs",
    "containers",
    "items",
    "activators",
    "terminals",
    "workshops",
    "flora",
    "benches",
    "lights",
    "doors",
)


def canonical_form_key(raw_fid: int, masters: Sequence[str], own_plugin: str) -> str:
    idx = (int(raw_fid) >> 24) & 0xFF
    local = int(raw_fid) & 0xFFFFFF
    owner = masters[idx] if idx < len(masters) else own_plugin
    return f"{local:06X}:{owner}"


def load_core_formid_map(formids_path: str) -> Dict[str, Dict[str, str]]:
    """Map canonical lowercase `<6hex>:<plugin>` source key -> `{'ref': <6hex>, 'section': <section>}`."""
    with open(formids_path, encoding="utf-8-sig") as f:
        doc = json.load(f)
    out: Dict[str, Dict[str, str]] = {}
    for sec in CORE_REF_SECTIONS:
        block = doc.get(sec)
        if not isinstance(block, Mapping):
            continue
        for src_key, val in block.items():
            norm = str(src_key).strip().lower()
            if isinstance(val, str):
                out[norm] = {"ref": val.upper(), "section": sec}
            elif isinstance(val, Mapping) and "ref" in val:
                entry: Dict[str, str] = {"ref": str(val["ref"]).upper(), "section": sec}
                if "base" in val:
                    entry["base"] = str(val["base"])
                if "arrival" in val:
                    entry["arrival"] = str(val["arrival"]).upper()
                out[norm] = entry
    return out


def _decompress_payload(buf: Any, off: int, size: int, flags: int) -> bytes:
    raw = bytes(buf[off + 24 : off + 24 + size])
    if flags & FLAG_COMPRESSED:
        return zlib.decompress(raw[4:])
    return raw


def _parse_refr_detail(
    form_key: str,
    plugin_name: str,
    masters: Sequence[str],
    flags: int,
    payload: bytes,
    cell_xy: Optional[Tuple[int, int]],
) -> Dict[str, Any]:
    deleted = bool(flags & FLAG_DELETED)
    disabled = bool(flags & FLAG_DISABLED)
    persistent = bool(flags & FLAG_PERSISTENT)
    base_fk: Optional[str] = None
    pos: Optional[List[float]] = None
    rot: Optional[List[float]] = None
    scale = 1.0
    has_xtel = False
    xtel_door_fk: Optional[str] = None
    has_xmrk = False
    if payload:
        for s, d in fo4land.iter_subrecords(payload):
            if s == b"NAME" and len(d) == 4:
                bfid = struct.unpack_from("<I", d)[0]
                base_fk = canonical_form_key(bfid, masters, plugin_name)
            elif s == b"DATA" and len(d) >= 24:
                vals = struct.unpack_from("<6f", d)
                pos = [round(float(vals[0]), 4), round(float(vals[1]), 4), round(float(vals[2]), 4)]
                rot = [round(float(vals[3]), 6), round(float(vals[4]), 6), round(float(vals[5]), 6)]
            elif s == b"XSCL" and len(d) == 4:
                scale = round(float(struct.unpack_from("<f", d)[0]), 5)
            elif s == b"XTEL" and len(d) >= 4:
                has_xtel = True
                dfid = struct.unpack_from("<I", d)[0]
                xtel_door_fk = canonical_form_key(dfid, masters, plugin_name)
            elif s == b"XMRK":
                has_xmrk = True
    return {
        "form_key": form_key,
        "plugin": plugin_name,
        "cell": list(cell_xy) if cell_xy is not None else "persistent",
        "deleted": deleted,
        "disabled": disabled,
        "persistent": persistent,
        "base": base_fk,
        "pos": pos,
        "rot": rot,
        "scale": scale,
        "is_load_door": has_xtel,
        "xtel_door": xtel_door_fk,
        "is_map_marker": has_xmrk,
    }


def _scan_commonwealth_raw(plugin_path: str) -> Dict[str, Any]:
    """Scan `Commonwealth` (`0x00003C`) in `plugin_path`, returning cell/land/actor counts and raw `REFR` slices."""
    plugin_name = os.path.basename(plugin_path)
    with fo4land.Plugin(plugin_path) as p:
        masters = p.masters()
        fo4_idx = next(
            (i for i, m in enumerate(masters) if m.lower() == "fallout4.esm"),
            0 if plugin_name.lower() == "fallout4.esm" else None,
        )
        if fo4_idx is None:
            return {
                "plugin": plugin_name,
                "masters": masters,
                "has_commonwealth": False,
                "cells": 0,
                "persistent_cell": False,
                "land_keys": {},
                "actor_keys": set(),
                "refrs": {},
            }
        target_wrld_fid = (fo4_idx << 24) | COMMONWEALTH_LOCAL_FID
        grp = p.top_group(b"WRLD")
        off, end = grp if grp is not None else (0, 0)

        wrld_g_start = 0
        wrld_g_end = 0
        cur = off
        while cur < end:
            sig = bytes(p.buf[cur : cur + 4])
            sz = struct.unpack_from("<I", p.buf, cur + 4)[0]
            if sig == b"WRLD":
                fid = struct.unpack_from("<I", p.buf, cur + 12)[0]
                nxt = cur + 24 + sz
                if fid == target_wrld_fid and nxt < end and bytes(p.buf[nxt : nxt + 4]) == b"GRUP":
                    gsz, glabel, gtype = struct.unpack_from("<I4sI", p.buf, nxt + 4)
                    if gtype == 1 and struct.unpack("<I", glabel)[0] == target_wrld_fid:
                        wrld_g_start = nxt + 24
                        wrld_g_end = nxt + gsz
                        break
                cur = nxt
            elif sig == b"GRUP":
                cur += sz
            else:
                cur += 24 + sz

        if wrld_g_start == 0:
            return {
                "plugin": plugin_name,
                "masters": masters,
                "has_commonwealth": False,
                "cells": 0,
                "persistent_cell": False,
                "land_keys": {},
                "actor_keys": set(),
                "refrs": {},
            }

        ext_cells = 0
        persistent_cell = False
        land_keys: Dict[str, bytes] = {}
        actor_keys: Set[str] = set()
        # key_lower -> (canonical_form_key, flags, raw_record_bytes_with_hdr_stripped_or_compressed, cell_xy)
        refrs: Dict[str, Tuple[str, int, bytes, Optional[Tuple[int, int]]]] = {}

        def walk_children(c_start: int, c_end: int, cell_xy: Optional[Tuple[int, int]]) -> None:
            q = c_start
            while q < c_end:
                qsig = bytes(p.buf[q : q + 4])
                qsz = struct.unpack_from("<I", p.buf, q + 4)[0]
                if qsig == b"GRUP":
                    walk_children(q + 24, q + qsz, cell_xy)
                    q += qsz
                else:
                    qfl, qfid = struct.unpack_from("<II", p.buf, q + 8)
                    fk = canonical_form_key(qfid, masters, plugin_name)
                    fk_low = fk.lower()
                    if qsig == b"REFR":
                        raw_rec = bytes(p.buf[q + 24 : q + 24 + qsz])
                        refrs[fk_low] = (fk, qfl, raw_rec, cell_xy)
                    elif qsig == b"LAND":
                        land_keys[fk_low] = bytes(p.buf[q + 24 : q + 24 + qsz])
                    elif qsig == b"ACHR":
                        actor_keys.add(fk_low)
                    q += 24 + qsz

        def walk_wrld(w_start: int, w_end: int) -> None:
            nonlocal ext_cells, persistent_cell
            q = w_start
            while q < w_end:
                qsig = bytes(p.buf[q : q + 4])
                qsz = struct.unpack_from("<I", p.buf, q + 4)[0]
                if qsig == b"GRUP":
                    gtype = struct.unpack_from("<I", p.buf, q + 12)[0]
                    if gtype in (4, 5):
                        walk_wrld(q + 24, q + qsz)
                    q += qsz
                elif qsig == b"CELL":
                    cfl, cfid = struct.unpack_from("<II", p.buf, q + 8)
                    cxy: Optional[Tuple[int, int]] = None
                    if cfl & FLAG_PERSISTENT:
                        persistent_cell = True
                    else:
                        cpayload = _decompress_payload(p.buf, q, qsz, cfl)
                        for cs, cd in fo4land.iter_subrecords(cpayload):
                            if cs == b"XCLC" and len(cd) >= 8:
                                cxy = struct.unpack_from("<2i", cd)
                                break
                        if cxy is None:
                            persistent_cell = True
                        else:
                            ext_cells += 1
                    nxt = q + 24 + qsz
                    if nxt < w_end and bytes(p.buf[nxt : nxt + 4]) == b"GRUP":
                        gsz, glbl, gtype = struct.unpack_from("<I4sI", p.buf, nxt + 4)
                        if gtype == 6 and struct.unpack("<I", glbl)[0] == cfid:
                            walk_children(nxt + 24, nxt + gsz, cxy)
                            q = nxt + gsz
                            continue
                    q = nxt
                else:
                    q += 24 + qsz

        walk_wrld(wrld_g_start, wrld_g_end)
        return {
            "plugin": plugin_name,
            "masters": masters,
            "has_commonwealth": True,
            "cells": ext_cells,
            "persistent_cell": persistent_cell,
            "land_keys": land_keys,
            "actor_keys": actor_keys,
            "refrs": refrs,
        }


def _unpack_refr(
    entry: Tuple[str, int, bytes, Optional[Tuple[int, int]]],
    plugin_name: str,
    masters: Sequence[str],
) -> Dict[str, Any]:
    fk, flags, raw_rec, cell_xy = entry
    payload = zlib.decompress(raw_rec[4:]) if (flags & FLAG_COMPRESSED) else raw_rec
    return _parse_refr_detail(fk, plugin_name, masters, flags, payload, cell_xy)


def _in_core64_bounds(pos_fo4: Optional[Sequence[float]], core_half_m: float = 3200.0) -> Optional[bool]:
    if pos_fo4 is None or len(pos_fo4) < 2:
        return None
    xm = float(pos_fo4[0]) / tg.UNITS_PER_METRE
    ym = float(pos_fo4[1]) / tg.UNITS_PER_METRE
    return (-core_half_m <= xm < core_half_m) and (-core_half_m <= ym < core_half_m)


def _classify_change(base_rec: Optional[Dict[str, Any]], win_rec: Dict[str, Any]) -> Tuple[str, List[str]]:
    if base_rec is None:
        return ("deleted" if win_rec["deleted"] else "added", ["added" if not win_rec["deleted"] else "deleted_new"])
    if win_rec["deleted"] and not base_rec["deleted"]:
        return ("deleted", ["deleted"])
    reasons: List[str] = []
    if base_rec["disabled"] != win_rec["disabled"]:
        reasons.append("disabled" if win_rec["disabled"] else "enabled")
    if base_rec["base"] != win_rec["base"]:
        reasons.append("base_changed")
    if base_rec["pos"] != win_rec["pos"]:
        if base_rec["pos"] and win_rec["pos"]:
            dist = math.hypot(
                win_rec["pos"][0] - base_rec["pos"][0],
                win_rec["pos"][1] - base_rec["pos"][1],
                win_rec["pos"][2] - base_rec["pos"][2],
            )
            if dist > 1e-3:
                reasons.append("moved")
        else:
            reasons.append("moved")
    if base_rec["rot"] != win_rec["rot"]:
        if base_rec["rot"] and win_rec["rot"]:
            rdist = max(abs(a - b) for a, b in zip(win_rec["rot"], base_rec["rot"]))
            if rdist > 1e-4:
                reasons.append("rotated")
        else:
            reasons.append("rotated")
    if abs(float(win_rec["scale"]) - float(base_rec["scale"])) > 1e-4:
        reasons.append("scaled")
    if base_rec["cell"] != win_rec["cell"]:
        reasons.append("cell_changed")
    if not reasons:
        return ("identical_override", [])
    if "disabled" in reasons and "moved" not in reasons:
        primary = "disabled"
    elif "enabled" in reasons and "moved" not in reasons:
        primary = "enabled"
    elif "moved" in reasons or "rotated" in reasons or "scaled" in reasons:
        primary = "moved"
    else:
        primary = "modified"
    return (primary, reasons)


def _resolve_core(fk_low: str, core_map: Mapping[str, Dict[str, str]]) -> Dict[str, Any]:
    hit = core_map.get(fk_low)
    if hit is not None:
        return {
            "status": "resolved",
            "core_ref_id": hit["ref"],
            "core_section": hit["section"],
        }
    return {
        "status": "new",
        "core_ref_id": None,
        "core_section": None,
    }


def compute_commonwealth_dlc_diff(
    *,
    nextgen_fo4: str,
    dlc_paths: Sequence[str],
    core_formids_path: str,
    depot_fo4: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Compute `(summary_report, full_edits_report)` separating base-game drift from per-DLC edits."""
    core_map = load_core_formid_map(core_formids_path)
    ng_scan = _scan_commonwealth_raw(nextgen_fo4)
    dlc_scans = [_scan_commonwealth_raw(p) for p in dlc_paths]

    # 1. Base-game comparison: depot 1.10.163 Fallout4.esm vs Next-Gen Fallout4.esm
    base_diff_records: List[Dict[str, Any]] = []
    base_diff_summary: Optional[Dict[str, Any]] = None
    if depot_fo4 is not None:
        depot_scan = _scan_commonwealth_raw(depot_fo4)
        depot_keys = set(depot_scan["refrs"].keys())
        ng_keys = set(ng_scan["refrs"].keys())
        added_k = sorted(ng_keys - depot_keys)
        removed_k = sorted(depot_keys - ng_keys)
        common_diff_k = sorted(
            k
            for k in (depot_keys & ng_keys)
            if (depot_scan["refrs"][k][1] != ng_scan["refrs"][k][1])
            or (depot_scan["refrs"][k][2] != ng_scan["refrs"][k][2])
        )
        for k in added_k:
            rec_ng = _unpack_refr(ng_scan["refrs"][k], ng_scan["plugin"], ng_scan["masters"])
            res = _resolve_core(k, core_map)
            base_diff_records.append(
                {"form_key": rec_ng["form_key"], "change": "added_in_nextgen", "nextgen": rec_ng, "core": res}
            )
        for k in removed_k:
            rec_dp = _unpack_refr(depot_scan["refrs"][k], depot_scan["plugin"], depot_scan["masters"])
            res = _resolve_core(k, core_map)
            base_diff_records.append(
                {"form_key": rec_dp["form_key"], "change": "removed_in_nextgen", "depot": rec_dp, "core": res}
            )
        for k in common_diff_k:
            rec_dp = _unpack_refr(depot_scan["refrs"][k], depot_scan["plugin"], depot_scan["masters"])
            rec_ng = _unpack_refr(ng_scan["refrs"][k], ng_scan["plugin"], ng_scan["masters"])
            kind, reasons = _classify_change(rec_dp, rec_ng)
            if not reasons and depot_scan["refrs"][k][2] != ng_scan["refrs"][k][2]:
                kind = "subrecord_modified"
                reasons = ["subrecord_bytes_changed"]
            res = _resolve_core(k, core_map)
            base_diff_records.append(
                {
                    "form_key": rec_ng["form_key"],
                    "change": kind,
                    "reasons": reasons,
                    "depot": rec_dp,
                    "nextgen": rec_ng,
                    "core": res,
                }
            )
        land_diff_cells = sum(
            1
            for lk in set(depot_scan["land_keys"]) | set(ng_scan["land_keys"])
            if depot_scan["land_keys"].get(lk) != ng_scan["land_keys"].get(lk)
        )
        base_diff_summary = {
            "depot_refs": len(depot_keys),
            "nextgen_refs": len(ng_keys),
            "added_in_nextgen": len(added_k),
            "removed_in_nextgen": len(removed_k),
            "modified_in_nextgen": len(common_diff_k),
            "land_records_differing": land_diff_cells,
            "resolved_in_core": sum(1 for r in base_diff_records if r["core"]["status"] == "resolved"),
            "marked_new": sum(1 for r in base_diff_records if r["core"]["status"] == "new"),
        }

    # 2. Per-DLC raw counts and winning edits over Next-Gen Fallout4.esm + DLC load order
    all_dlc_ref_keys: Set[str] = set()
    for ds in dlc_scans:
        all_dlc_ref_keys.update(ds["refrs"].keys())

    per_dlc_summary: Dict[str, Any] = {}
    winning_by_key: Dict[str, Tuple[Dict[str, Any], str]] = {}
    for ds in dlc_scans:
        pname = ds["plugin"]
        map_markers = 0
        load_doors = 0
        for k, raw_entry in ds["refrs"].items():
            unpacked = _unpack_refr(raw_entry, pname, ds["masters"])
            if unpacked["is_map_marker"]:
                map_markers += 1
            if unpacked["is_load_door"]:
                load_doors += 1
            winning_by_key[k] = (unpacked, pname)
        per_dlc_summary[pname] = {
            "has_commonwealth": ds["has_commonwealth"],
            "raw_cells": ds["cells"],
            "raw_land_records": len(ds["land_keys"]),
            "raw_refs": len(ds["refrs"]),
            "raw_actors": len(ds["actor_keys"]),
            "raw_map_markers": map_markers,
            "raw_load_doors": load_doors,
            "winning_refs_total": 0,
            "winning_by_kind": {
                "added": 0,
                "moved": 0,
                "disabled": 0,
                "enabled": 0,
                "deleted": 0,
                "modified": 0,
                "identical_override": 0,
            },
            "winning_in_core64_bounds": 0,
            "winning_resolved_in_core": 0,
            "winning_marked_new": 0,
        }

    winning_edits: List[Dict[str, Any]] = []
    new_bases: Set[str] = set()
    for k in sorted(winning_by_key.keys()):
        win_rec, win_plugin = winning_by_key[k]
        base_rec = (
            _unpack_refr(ng_scan["refrs"][k], ng_scan["plugin"], ng_scan["masters"])
            if k in ng_scan["refrs"]
            else None
        )
        kind, reasons = _classify_change(base_rec, win_rec)
        core_res = _resolve_core(k, core_map)
        pos_check = win_rec["pos"] or (base_rec["pos"] if base_rec else None)
        in_c64 = _in_core64_bounds(pos_check)

        if win_rec["base"] and not win_rec["base"].lower().endswith(":fallout4.esm"):
            new_bases.add(win_rec["base"])

        pstat = per_dlc_summary[win_plugin]
        pstat["winning_refs_total"] += 1
        pstat["winning_by_kind"][kind] = pstat["winning_by_kind"].get(kind, 0) + 1
        if in_c64:
            pstat["winning_in_core64_bounds"] += 1
        if core_res["status"] == "resolved":
            pstat["winning_resolved_in_core"] += 1
        else:
            pstat["winning_marked_new"] += 1

        winning_edits.append(
            {
                "form_key": win_rec["form_key"],
                "winning_plugin": win_plugin,
                "kind": kind,
                "reasons": reasons,
                "in_core64_bounds": in_c64,
                "core": core_res,
                "base_record": base_rec,
                "winning_record": win_rec,
            }
        )

    total_resolved = sum(1 for e in winning_edits if e["core"]["status"] == "resolved")
    total_new = sum(1 for e in winning_edits if e["core"]["status"] == "new")
    assert total_resolved + total_new == len(winning_edits)

    summary = {
        "world": "Commonwealth",
        "world_form_id": "00003C:Fallout4.esm",
        "nextgen_base_plugin": ng_scan["plugin"],
        "dlc_load_order": [ds["plugin"] for ds in dlc_scans],
        "base_game_diff": base_diff_summary,
        "per_dlc": per_dlc_summary,
        "totals": {
            "unique_dlc_touched_refs": len(winning_edits),
            "resolved_in_core_formids": total_resolved,
            "marked_new": total_new,
            "in_core64_bounds": sum(1 for e in winning_edits if e["in_core64_bounds"]),
            "dlc_defined_bases_used": len(new_bases),
        },
    }
    full_doc = {
        "summary": summary,
        "dlc_defined_bases": sorted(new_bases),
        "base_game_diff_records": base_diff_records,
        "winning_dlc_edits": winning_edits,
    }
    return summary, full_doc


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Diff Commonwealth DLC edits and base-game drift against core formids.json.")
    ap.add_argument("--nextgen-fo4", required=True, help="Path to Next-Gen Fallout4.esm")
    ap.add_argument("--depot-fo4", default=None, help="Optional path to depot 1.10.163 Fallout4.esm")
    ap.add_argument("--dlc", action="append", default=[], help="DLC .esm path in load order (repeatable)")
    ap.add_argument("--core-formids", required=True, help="Path to FO4TerrainCore formids.json")
    ap.add_argument("--out", required=True, help="Output directory outside Git worktrees and game folders")
    args = ap.parse_args(argv)

    input_paths = [args.nextgen_fo4, args.core_formids, *args.dlc]
    if args.depot_fo4:
        input_paths.append(args.depot_fo4)
    out_dir = str(refuse_unsafe_output_path(args.out, input_paths=input_paths))
    os.makedirs(out_dir, exist_ok=True)

    summary, full_doc = compute_commonwealth_dlc_diff(
        nextgen_fo4=args.nextgen_fo4,
        dlc_paths=args.dlc,
        core_formids_path=args.core_formids,
        depot_fo4=args.depot_fo4,
    )

    sum_path = Path(out_dir, "dlc_edits_summary.json")
    full_path = Path(out_dir, "dlc_edits.json")
    refuse_unsafe_output_path(sum_path, input_paths=input_paths)
    refuse_unsafe_output_path(full_path, input_paths=input_paths)
    sum_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    full_path.write_text(json.dumps(full_doc, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
