"""Per-cell interior census tool for `IB1` start-path interiors (`scripts/terrain/interior_start_census.py`).

Reads a built interior plugin (`--plugin <FO4Port.esm>` or `--stage <interiors_bNN>`) raw in Python without game files
and reports, per interior cell:
  - `containers_with_non_credit_loot` (and `containers_total`, `containers_with_converted_fo4_loot`)
  - `usable_furniture` (`usable_beds_and_benches`, `usable_beds`, `usable_benches`, `usable_chairs`)
  - `carried_locks` (`xloc`)
  - `carried_enable_parents` (`xesp`)
  - `carried_linked_refs` (`xlkr`, excluding internal activation-chain / MultirefLOD helper links)
  - `carried_activate_chains` (`xapr`)

Usage:
  python scripts/terrain/interior_start_census.py --plugin <FO4Port.esm> [--cells <c1,c2>] [--start-path-only] [--out <census.json>]
  python scripts/terrain/interior_start_census.py --stage <interiors_bNN> [--start-path-only] [--out <census.json>]
"""
from __future__ import annotations

import argparse
import json
import os
import struct
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for _p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "scripts"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fo4sf import fo4land as fl, pipeline  # noqa: E402

DELETED_FLAG = 0x00000020
COMPRESSED_FLAG = 0x00040000
CELL_INTERIOR_FLAG = 0x0001

CREDITS_REF = ("starfield.esm", 0x00000F)
LEGACY_LINK_CUSTOM02 = ("starfield.esm", 0x05D5E7)
MULTIREF_LOD_FO4 = ("fallout4.esm", 0x195411)
SLEEP_FURN_KEYWORDS = frozenset({
    ("starfield.esm", 0x021B18),  # IsSleepFurniture
    ("starfield.esm", 0x1FA760),  # AnimFurnBed
    ("starfield.esm", 0x00F666),  # AnimFurnSleep_Floor
})
VANILLA_BENCH_FIDS = frozenset({
    ("starfield.esm", 0x2B6A61),  # WorkbenchChem
    ("starfield.esm", 0x2B6A62),  # WorkbenchArmor
    ("starfield.esm", 0x2B6A63),  # WorkbenchWeapon
    ("starfield.esm", 0x2B6A65),  # WorkbenchFood
})
VANILLA_BED_FIDS = frozenset({
    ("starfield.esm", 0x1FA770),  # Bed_Single01
    ("starfield.esm", 0x088968),  # _Template_Bed_Single0_Inverse
    ("starfield.esm", 0x112342),  # _Template_Bed_Single01
    ("starfield.esm", 0x331235),  # Neon_ContainerA_Bed_Single01
})

# Canonical Fallout 4 start-path interior cell EditorIDs plus common test/prompt aliases.
START_PATH_CELLS = (
    "ConcordMuseum01",
    "ConcordSpeakeasy",
    "ConcordSpeakeasy01",
    "ConcordFactory",
    "ConcordWorkhouse01",
    "ConcordCivicAccess01",
    "SanctuaryBasementJahani",
    "SanctuaryRootCellar01",
)
START_PATH_CASEFOLD = frozenset(c.casefold() for c in START_PATH_CELLS)


def _iter_subrecords_xxxx(raw_bytes: bytes):
    """Iterate Starfield/FO4 subrecords, supporting XXXX 32-bit length prefixes."""
    pos = 0
    end = len(raw_bytes)
    large_len: Optional[int] = None
    while pos + 6 <= end:
        sig = raw_bytes[pos : pos + 4]
        sz = struct.unpack_from("<H", raw_bytes, pos + 4)[0]
        pos += 6
        if sig == b"XXXX" and sz == 4 and pos + 4 <= end:
            large_len = struct.unpack_from("<I", raw_bytes, pos)[0]
            pos += 4
            continue
        if large_len is not None:
            sz = large_len
            large_len = None
        yield sig, raw_bytes[pos : pos + sz]
        pos += sz


def _record_payload(buf: memoryview, off: int, rflags: int) -> bytes:
    size = struct.unpack_from("<I", buf, off + 4)[0]
    raw = bytes(buf[off + 24 : off + 24 + size])
    if rflags & COMPRESSED_FLAG:
        return zlib.decompress(raw[4:])
    return raw


def _resolve_fid(raw_fid: int, masters_lower: Sequence[str], self_mod_lower: str) -> Optional[Tuple[str, int]]:
    if raw_fid == 0:
        return None
    idx = (raw_fid >> 24) & 0xFF
    local = raw_fid & 0x00FFFFFF
    owner = masters_lower[idx] if idx < len(masters_lower) else self_mod_lower
    return (owner, local)


def _read_vmad_str(data: bytes, pos: int) -> Tuple[str, int]:
    n = struct.unpack_from("<H", data, pos)[0]
    pos += 2
    return data[pos : pos + n].decode("cp1252", errors="replace"), pos + n


def _skip_or_parse_vmad_val(data: bytes, pos: int, ptype: int, obj_fmt: int, ver: int, masters_lower: Sequence[str], self_mod_lower: str):
    if ptype == 1:
        raw_fid = struct.unpack_from("<I", data, pos + 4)[0] if obj_fmt == 2 else struct.unpack_from("<I", data, pos)[0]
        return _resolve_fid(raw_fid, masters_lower, self_mod_lower), pos + 8
    if ptype == 2:
        return _read_vmad_str(data, pos)
    if ptype == 3:
        return struct.unpack_from("<i", data, pos)[0], pos + 4
    if ptype == 4:
        return struct.unpack_from("<f", data, pos)[0], pos + 4
    if ptype == 5:
        return bool(data[pos]), pos + 1
    if ptype == 7:
        mcount = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        d = {}
        for _ in range(mcount):
            pn, pv, pos = _parse_vmad_prop(data, pos, obj_fmt, ver, masters_lower, self_mod_lower)
            d[pn] = pv
        return d, pos
    if ptype in (11, 12, 13, 14, 15, 17):
        et = 7 if ptype == 17 else (ptype - 10)
        acount = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        arr = []
        for _ in range(acount):
            v, pos = _skip_or_parse_vmad_val(data, pos, et, obj_fmt, ver, masters_lower, self_mod_lower)
            arr.append(v)
        return arr, pos
    raise ValueError(f"unsupported VMAD property type {ptype}")


def _parse_vmad_prop(data: bytes, pos: int, obj_fmt: int, ver: int, masters_lower: Sequence[str], self_mod_lower: str):
    pname, pos = _read_vmad_str(data, pos)
    ptype = data[pos]
    pos += 1 + (1 if ver >= 4 else 0)
    pval, pos = _skip_or_parse_vmad_val(data, pos, ptype, obj_fmt, ver, masters_lower, self_mod_lower)
    return pname, pval, pos


def _parse_vmad_chains(sdata: bytes, masters_lower: Sequence[str], self_mod_lower: str) -> Tuple[int, bool]:
    """Return `(xapr_edges, has_legacy_single_chain)` from a REFR `VMAD` subrecord."""
    edges = 0
    legacy = False
    if len(sdata) < 6:
        return 0, False
    try:
        ver, obj_fmt, scount = struct.unpack_from("<hHH", sdata, 0)
        pos = 6
        for _ in range(scount):
            sname, pos = _read_vmad_str(sdata, pos)
            if ver >= 4:
                pos += 1
            pcount = struct.unpack_from("<H", sdata, pos)[0]
            pos += 2
            props = {}
            for _ in range(pcount):
                pn, pv, pos = _parse_vmad_prop(sdata, pos, obj_fmt, ver, masters_lower, self_mod_lower)
                props[pn.lower()] = pv
            sl = sname.lower()
            if sl == "fo4sf_activatechain":
                targets = props.get("targets") or []
                edges += sum(1 for t in targets if t is not None)
            elif sl == "defaultactivatelinkedrefonactivate":
                edges += 1
                legacy = True
    except (struct.error, ValueError, IndexError):
        return edges, legacy
    return edges, legacy


def _strip_edid_prefix(cell_edid: str) -> str:
    if "_" in cell_edid and cell_edid.lower().startswith("fo4"):
        return cell_edid.split("_", 1)[1]
    return cell_edid


def _matches_cell_filter(cell_edid: str, wanted: Optional[Set[str]]) -> bool:
    if wanted is None:
        return True
    low = cell_edid.casefold()
    stripped = _strip_edid_prefix(cell_edid).casefold()
    return low in wanted or stripped in wanted


def measure_plugin(
    plugin_path: str,
    *,
    only_cells: Optional[Iterable[str]] = None,
    start_path_only: bool = False,
) -> Dict:
    """Inspect `plugin_path` and return per-cell and aggregate counts for `IB1`."""
    if not os.path.isfile(plugin_path):
        raise FileNotFoundError(f"plugin not found: {plugin_path}")
    self_mod = os.path.basename(plugin_path)
    self_mod_lower = self_mod.lower()

    wanted: Optional[Set[str]] = None
    if start_path_only:
        wanted = set(START_PATH_CASEFOLD)
    if only_cells:
        extra = {c.strip().casefold() for c in only_cells if c and c.strip()}
        wanted = (wanted | extra) if wanted is not None else extra

    chain_keywords: Set[Tuple[str, int]] = set()
    containers_meta: Dict[Tuple[str, int], Dict] = {}
    furniture_kind_map: Dict[Tuple[str, int], str] = {}

    with fl.Plugin(plugin_path) as p:
        buf = p.buf
        hdr = list(_iter_subrecords_xxxx(fl.record_data(buf, 0)))
        masters = [fl.zstring(d) for s, d in hdr if s == b"MAST"]
        masters_lower = [m.lower() for m in masters]

        # Pass 1: top-level KYWD, CONT, and FURN base records.
        for item in fl.iter_items(buf, p.body, len(buf)):
            if item[0] != "GRUP":
                continue
            _g, off, end, label, _gt = item
            if label == b"KYWD":
                for rec in fl.iter_items(buf, off + 24, end):
                    if rec[0] == "GRUP" or (rec[2] & DELETED_FLAG):
                        continue
                    key = _resolve_fid(rec[3], masters_lower, self_mod_lower)
                    if key is None:
                        continue
                    subs = list(_iter_subrecords_xxxx(_record_payload(buf, rec[1], rec[2])))
                    edid = next((fl.zstring(d) for s, d in subs if s == b"EDID"), "")
                    if edid.lower().endswith("_activatechainlink"):
                        chain_keywords.add(key)
            elif label == b"CONT":
                for rec in fl.iter_items(buf, off + 24, end):
                    if rec[0] == "GRUP" or (rec[2] & DELETED_FLAG):
                        continue
                    key = _resolve_fid(rec[3], masters_lower, self_mod_lower)
                    if key is None:
                        continue
                    subs = list(_iter_subrecords_xxxx(_record_payload(buf, rec[1], rec[2])))
                    edid = next((fl.zstring(d) for s, d in subs if s == b"EDID"), "")
                    cnto_items: List[Tuple[Tuple[str, int], int]] = []
                    for s, d in subs:
                        if s == b"CNTO" and len(d) >= 8:
                            i_raw, cnt = struct.unpack_from("<Ii", d, 0)
                            i_res = _resolve_fid(i_raw, masters_lower, self_mod_lower)
                            if i_res is not None and cnt > 0:
                                cnto_items.append((i_res, int(cnt)))
                    has_non_credit = any(it != CREDITS_REF for it, _c in cnto_items)
                    has_converted_own = any(it[0] == self_mod_lower for it, _c in cnto_items)
                    containers_meta[key] = {
                        "edid": edid,
                        "item_entries": len(cnto_items),
                        "non_credit": has_non_credit,
                        "converted_fo4": has_converted_own,
                    }
            elif label == b"FURN":
                for rec in fl.iter_items(buf, off + 24, end):
                    if rec[0] == "GRUP" or (rec[2] & DELETED_FLAG):
                        continue
                    key = _resolve_fid(rec[3], masters_lower, self_mod_lower)
                    if key is None:
                        continue
                    subs = list(_iter_subrecords_xxxx(_record_payload(buf, rec[1], rec[2])))
                    edid = next((fl.zstring(d) for s, d in subs if s == b"EDID"), "")
                    wbdt = next((d[0] for s, d in subs if s == b"WBDT" and len(d) >= 1), 0)
                    kws: List[Tuple[str, int]] = []
                    for s, d in subs:
                        if s == b"KWDA" and len(d) >= 4:
                            for (kw_raw,) in struct.iter_unpack("<I", d[: (len(d) // 4) * 4]):
                                kw_res = _resolve_fid(kw_raw, masters_lower, self_mod_lower)
                                if kw_res is not None:
                                    kws.append(kw_res)
                    if wbdt != 0:
                        fkind = "bench"
                    elif any(kw in SLEEP_FURN_KEYWORDS for kw in kws) or "bed" in edid.lower():
                        fkind = "bed"
                    else:
                        fkind = "chair"
                    furniture_kind_map[key] = fkind

        # Pass 2: walk interior CELLs and their placed REFR children.
        cells_report: Dict[str, Dict] = {}

        def walk_refrs(start: int, end: int, acc: Dict) -> None:
            for it in fl.iter_items(buf, start, end):
                if it[0] == "GRUP":
                    walk_refrs(it[1] + 24, it[2], acc)
                    continue
                typ, roff, rflags, _fid = it
                if typ != b"REFR" or (rflags & DELETED_FLAG):
                    continue
                payload = _record_payload(buf, roff, rflags)
                base_res: Optional[Tuple[str, int]] = None
                has_xesp = False
                has_xloc = False
                raw_xlkr: List[Tuple[Optional[Tuple[str, int]], Tuple[str, int]]] = []
                native_xapr = 0
                vmad_edges = 0
                legacy_chain = False

                for sig, sdata in _iter_subrecords_xxxx(payload):
                    if sig == b"NAME" and len(sdata) >= 4:
                        base_res = _resolve_fid(struct.unpack_from("<I", sdata, 0)[0], masters_lower, self_mod_lower)
                    elif sig == b"XESP" and len(sdata) >= 8:
                        if _resolve_fid(struct.unpack_from("<I", sdata, 0)[0], masters_lower, self_mod_lower) is not None:
                            has_xesp = True
                    elif sig == b"XLOC" and len(sdata) >= 12:
                        has_xloc = True
                    elif sig == b"XLKR" and len(sdata) >= 8:
                        for off_l in range(0, (len(sdata) // 8) * 8, 8):
                            u_raw, t_raw = struct.unpack_from("<II", sdata, off_l)
                            t_res = _resolve_fid(t_raw, masters_lower, self_mod_lower)
                            u_res = _resolve_fid(u_raw, masters_lower, self_mod_lower)
                            if t_res is not None:
                                raw_xlkr.append((u_res, t_res))
                    elif sig == b"XAPR" and len(sdata) >= 8:
                        if struct.unpack_from("<I", sdata, 0)[0] != 0:
                            native_xapr += 1
                    elif sig == b"VMAD":
                        vmad_edges, legacy_chain = _parse_vmad_chains(sdata, masters_lower, self_mod_lower)

                acc["placed_refs"] += 1
                if base_res in containers_meta:
                    cmeta = containers_meta[base_res]
                    acc["containers_total"] += 1
                    if cmeta["non_credit"]:
                        acc["containers_with_non_credit_loot"] += 1
                    if cmeta["converted_fo4"]:
                        acc["containers_with_converted_fo4_loot"] += 1

                fkind = furniture_kind_map.get(base_res) if base_res else None
                if fkind is None and base_res in VANILLA_BENCH_FIDS:
                    fkind = "bench"
                elif fkind is None and base_res in VANILLA_BED_FIDS:
                    fkind = "bed"
                if fkind is not None:
                    acc["usable_furniture"] += 1
                    if fkind == "bed":
                        acc["usable_beds"] += 1
                        acc["usable_beds_and_benches"] += 1
                    elif fkind == "bench":
                        acc["usable_benches"] += 1
                        acc["usable_beds_and_benches"] += 1
                    else:
                        acc["usable_chairs"] += 1

                if has_xloc:
                    acc["carried_locks"] += 1
                if has_xesp:
                    acc["carried_enable_parents"] += 1

                pure_links = 0
                for u_res, _t_res in raw_xlkr:
                    if u_res == MULTIREF_LOD_FO4:
                        continue
                    if u_res in chain_keywords:
                        continue
                    if legacy_chain and u_res == LEGACY_LINK_CUSTOM02:
                        continue
                    pure_links += 1
                acc["carried_linked_refs"] += pure_links
                acc["carried_activate_chains"] += native_xapr + vmad_edges

        def walk_cell_groups(start: int, end: int) -> None:
            cur_acc: Optional[Dict] = None
            cur_fid: Optional[int] = None
            for it in fl.iter_items(buf, start, end):
                if it[0] == "GRUP":
                    _g, off_g, end_g, label_g, gtype = it
                    if gtype in (2, 3):  # interior block / sub-block
                        walk_cell_groups(off_g + 24, end_g)
                    elif gtype == 6 and cur_acc is not None and struct.unpack_from("<I", label_g, 0)[0] == cur_fid:
                        walk_refrs(off_g + 24, end_g, cur_acc)
                    continue
                typ, roff, rflags, fid = it
                if typ != b"CELL" or (rflags & DELETED_FLAG):
                    cur_acc = None
                    cur_fid = None
                    continue
                subs = list(_iter_subrecords_xxxx(_record_payload(buf, roff, rflags)))
                cflags = next((struct.unpack_from("<H", d, 0)[0] for s, d in subs if s == b"DATA" and len(d) >= 2), 0)
                if not (cflags & CELL_INTERIOR_FLAG):
                    cur_acc = None
                    cur_fid = None
                    continue
                edid = next((fl.zstring(d) for s, d in subs if s == b"EDID"), f"CELL_{fid & 0xFFFFFF:06X}")
                if not _matches_cell_filter(edid, wanted):
                    cur_acc = None
                    cur_fid = None
                    continue
                src_cell = _strip_edid_prefix(edid)
                cur_fid = fid
                cur_acc = {
                    "cell_editor_id": edid,
                    "source_cell": src_cell,
                    "is_start_path": src_cell.casefold() in START_PATH_CASEFOLD,
                    "placed_refs": 0,
                    "containers_total": 0,
                    "containers_with_non_credit_loot": 0,
                    "containers_with_converted_fo4_loot": 0,
                    "usable_furniture": 0,
                    "usable_beds_and_benches": 0,
                    "usable_beds": 0,
                    "usable_benches": 0,
                    "usable_chairs": 0,
                    "carried_locks": 0,
                    "carried_enable_parents": 0,
                    "carried_linked_refs": 0,
                    "carried_activate_chains": 0,
                }
                cells_report[edid] = cur_acc

        for item in fl.iter_items(buf, p.body, len(buf)):
            if item[0] == "GRUP" and item[3] == b"CELL":
                walk_cell_groups(item[1] + 24, item[2])

    metric_keys = (
        "placed_refs",
        "containers_total",
        "containers_with_non_credit_loot",
        "containers_with_converted_fo4_loot",
        "usable_furniture",
        "usable_beds_and_benches",
        "usable_beds",
        "usable_benches",
        "usable_chairs",
        "carried_locks",
        "carried_enable_parents",
        "carried_linked_refs",
        "carried_activate_chains",
    )

    ordered_cells = dict(sorted(cells_report.items(), key=lambda kv: kv[0].casefold()))

    def sum_metrics(rows: Iterable[Dict]) -> Dict[str, int]:
        rows_list = list(rows)
        out_sum = {"cells": len(rows_list)}
        for mk in metric_keys:
            out_sum[mk] = sum(int(r[mk]) for r in rows_list)
        return out_sum

    return {
        "plugin": self_mod,
        "masters": masters,
        "totals": sum_metrics(ordered_cells.values()),
        "start_path_totals": sum_metrics(r for r in ordered_cells.values() if r["is_start_path"]),
        "cells": ordered_cells,
    }


def resolve_stage_plugin(stage_dir: str, plugin_name: str = "FO4Port.esm") -> str:
    """Locate `<stage>/port/<plugin>` or `<stage>/plugin/<plugin>` for a batch stage directory."""
    for sub in ("port", "plugin", ""):
        cand = os.path.join(stage_dir, sub, plugin_name) if sub else os.path.join(stage_dir, plugin_name)
        if os.path.isfile(cand):
            return cand
    raise FileNotFoundError(f"no {plugin_name} found under {stage_dir}")


def build_arg_parser(prog: Optional[str] = None) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog=prog, description=__doc__.splitlines()[0])
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--plugin", default="", help="path to built FO4Port.esm (or custom interior .esm)")
    grp.add_argument("--stage", default="", help="interior batch stage directory holding port/FO4Port.esm")
    ap.add_argument("--plugin-name", default="FO4Port.esm", help="plugin filename when --stage is used (default: FO4Port.esm)")
    ap.add_argument("--cells", action="append", default=[], help="comma-separated or repeatable cell EditorID filter")
    ap.add_argument("--start-path-only", action="store_true",
                    help="measure only the 5 start-path interiors (Concord Museum, 3 Concord interiors, Sanctuary basement)")
    ap.add_argument("--out", default="", help="optional JSON output path (outside Git worktrees and game folders)")
    return ap


def run_from_namespace(a) -> int:
    if a.out:
        pipeline.refuse_unsafe_output_dir(a.out, "--out")
    plugin_path = a.plugin or resolve_stage_plugin(a.stage, a.plugin_name)
    cell_tokens: List[str] = []
    for raw in a.cells or []:
        cell_tokens.extend(tok.strip() for tok in raw.split(",") if tok.strip())
    result = measure_plugin(
        plugin_path,
        only_cells=cell_tokens or None,
        start_path_only=bool(a.start_path_only),
    )
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        tmp = a.out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=1)
        os.replace(tmp, a.out)
    print(json.dumps(result, indent=1))
    return 0


def main(argv=None) -> int:
    ap = build_arg_parser()
    a = ap.parse_args(argv)
    try:
        return run_from_namespace(a)
    except (OSError, ValueError) as exc:
        print(f"interior_start_census: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
