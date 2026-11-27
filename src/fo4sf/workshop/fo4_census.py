"""Offline census parser for Fallout4.esm workshop buildables, PRPS values, CMPO components, junk MISC, and scrap recipes.

Usage:
  python -m fo4sf.workshop.fo4_census --master <path/to/Fallout4.esm> --out <private/out.json>

Design constraints:
- Explicit --master path (never assumes Data/Fallout4.esm exists in the Starfield install dir).
- Excludes the Creation Club category (FLST 0024A0DC WorkshopMenu01CreationClub) by default.
- Never writes census data inside the Git checkout unless explicitly directed by caller; keep game outputs private.
"""
from __future__ import annotations

import argparse
import json
import os
import struct
import zlib
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

DEFAULT_MENU_MAIN_FID = 0x00106DA2        # FLST WorkshopMenuMain
DEFAULT_CC_CATEGORY_FID = 0x0024A0DC      # FLST WorkshopMenu01CreationClub
DEFAULT_SCRAP_FILTER_FID = 0x00106D8F     # KYWD WorkshopRecipeFilterScrap


def _iter_records(esm_bytes: bytes) -> Iterable[Tuple[str, int, int, bytes]]:
    """Yield (sig, flags, form_id, raw_payload_without_record_header) for every non-GRUP record."""
    n = len(esm_bytes)

    def walk(off: int, end: int):
        while off + 24 <= end:
            sig = esm_bytes[off : off + 4].decode("latin1")
            size = struct.unpack_from("<I", esm_bytes, off + 4)[0]
            if sig == "GRUP":
                if size < 24 or off + size > end:
                    break
                yield from walk(off + 24, off + size)
                off += size
            else:
                flags = struct.unpack_from("<I", esm_bytes, off + 8)[0]
                fid = struct.unpack_from("<I", esm_bytes, off + 12)[0]
                rec_end = off + 24 + size
                if rec_end > end:
                    break
                yield sig, flags, fid, esm_bytes[off + 24 : rec_end]
                off = rec_end

    yield from walk(0, n)


def _decompress_payload(flags: int, raw: bytes) -> bytes:
    if flags & 0x00040000:
        if len(raw) < 4:
            return b""
        return zlib.decompress(raw[4:])
    return raw


def _iter_subrecords(payload: bytes) -> Iterable[Tuple[str, bytes]]:
    pos = 0
    big_len: Optional[int] = None
    n = len(payload)
    while pos + 6 <= n:
        sig = payload[pos : pos + 4].decode("latin1")
        slen = struct.unpack_from("<H", payload, pos + 4)[0]
        pos += 6
        if sig == "XXXX" and slen == 4 and pos + 4 <= n:
            big_len = struct.unpack_from("<I", payload, pos)[0]
            pos += 4
            continue
        if big_len is not None:
            slen = big_len
            big_len = None
        if pos + slen > n:
            break
        yield sig, payload[pos : pos + slen]
        pos += slen


def _edid(subs: Sequence[Tuple[str, bytes]]) -> str:
    for k, v in subs:
        if k == "EDID":
            return v.rstrip(b"\x00").decode("utf-8", errors="replace")
    return ""


def _parse_prps(blob: bytes) -> List[Dict[str, float]]:
    entries: List[Dict[str, float]] = []
    for off in range(0, len(blob) - (len(blob) % 8), 8):
        av_fid, val = struct.unpack_from("<If", blob, off)
        entries.append({"actor_value_fid": av_fid, "value": round(float(val), 6)})
    return entries


def _parse_fvpa(blob: bytes) -> List[Dict[str, int]]:
    items: List[Dict[str, int]] = []
    for off in range(0, len(blob) - (len(blob) % 8), 8):
        comp_fid, count = struct.unpack_from("<II", blob, off)
        items.append({"component_fid": comp_fid, "count": int(count)})
    return items


def _parse_cvpa(blob: bytes) -> List[Dict[str, int]]:
    items: List[Dict[str, int]] = []
    for off in range(0, len(blob) - (len(blob) % 8), 8):
        comp_fid, count = struct.unpack_from("<II", blob, off)
        items.append({"component_fid": comp_fid, "count": int(count)})
    return items


def run_census(
    esm_bytes: bytes,
    *,
    exclude_cc: bool = True,
    menu_root_fid: int = DEFAULT_MENU_MAIN_FID,
    cc_flst_fid: int = DEFAULT_CC_CATEGORY_FID,
    scrap_filter_fid: int = DEFAULT_SCRAP_FILTER_FID,
) -> Dict[str, object]:
    """Parse Fallout 4 ESM bytes into a deterministic structured census dictionary."""
    records: Dict[int, Tuple[str, List[Tuple[str, bytes]]]] = {}
    by_sig: Dict[str, List[int]] = {}
    for sig, flags, fid, raw in _iter_records(esm_bytes):
        subs = list(_iter_subrecords(_decompress_payload(flags, raw)))
        records[fid] = (sig, subs)
        by_sig.setdefault(sig, []).append(fid)

    menu_filter_fids: Set[int] = set()
    menu_tree: List[Dict[str, object]] = []
    excluded_branches: List[str] = []

    def walk_menu(fid: int, trail: Tuple[str, ...]) -> None:
        if fid not in records:
            return
        sig, subs = records[fid]
        edid = _edid(subs) or f"{fid:08X}"
        if exclude_cc and (fid == cc_flst_fid or "creationclub" in edid.lower()):
            excluded_branches.append(edid)
            return
        if sig == "KYWD":
            menu_filter_fids.add(fid)
            menu_tree.append({
                "form_id": f"{fid:08X}",
                "editor_id": edid,
                "path": list(trail),
            })
        elif sig == "FLST":
            for k, v in subs:
                if k == "LNAM" and len(v) == 4:
                    child_fid = struct.unpack("<I", v)[0]
                    walk_menu(child_fid, trail + (edid,))

    walk_menu(menu_root_fid, ())

    components: List[Dict[str, object]] = []
    for fid in by_sig.get("CMPO", ()):
        _, subs = records[fid]
        edid = _edid(subs)
        scrap_fid = next((struct.unpack("<I", v)[0] for k, v in subs if k == "GNAM" and len(v) == 4), None)
        mod_scrap_fid = next((struct.unpack("<I", v)[0] for k, v in subs if k == "MNAM" and len(v) == 4), None)
        components.append({
            "form_id": f"{fid:08X}",
            "editor_id": edid,
            "scrap_item_fid": f"{scrap_fid:08X}" if scrap_fid is not None else None,
            "mod_scrap_fid": f"{mod_scrap_fid:08X}" if mod_scrap_fid is not None else None,
        })

    junk_items: List[Dict[str, object]] = []
    for fid in by_sig.get("MISC", ()):
        _, subs = records[fid]
        cvpas: List[Dict[str, int]] = []
        for k, v in subs:
            if k == "CVPA":
                cvpas.extend(_parse_cvpa(v))
        if cvpas:
            junk_items.append({
                "form_id": f"{fid:08X}",
                "editor_id": _edid(subs),
                "components": [
                    {"component_fid": f"{c['component_fid']:08X}", "count": c["count"]}
                    for c in cvpas
                ],
            })

    prps_records: List[Dict[str, object]] = []
    for sig, fids in sorted(by_sig.items()):
        for fid in fids:
            _, subs = records[fid]
            props: List[Dict[str, float]] = []
            for k, v in subs:
                if k == "PRPS":
                    props.extend(_parse_prps(v))
            if props:
                prps_records.append({
                    "sig": sig,
                    "form_id": f"{fid:08X}",
                    "editor_id": _edid(subs),
                    "prps": [
                        {"actor_value_fid": f"{p['actor_value_fid']:08X}", "value": p["value"]}
                        for p in props
                    ],
                })

    menu_recipes: List[Dict[str, object]] = []
    scrap_recipes: List[Dict[str, object]] = []
    for fid in by_sig.get("COBJ", ()):
        _, subs = records[fid]
        edid = _edid(subs)
        bnam = next((struct.unpack("<I", v)[0] for k, v in subs if k == "BNAM" and len(v) == 4), None)
        cnam = next((struct.unpack("<I", v)[0] for k, v in subs if k == "CNAM" and len(v) == 4), None)
        fnams = [struct.unpack("<I", v)[0] for k, v in subs if k == "FNAM" and len(v) == 4]
        fvpas: List[Dict[str, int]] = []
        for k, v in subs:
            if k == "FVPA":
                fvpas.extend(_parse_fvpa(v))
        entry = {
            "form_id": f"{fid:08X}",
            "editor_id": edid,
            "bnam_fid": f"{bnam:08X}" if bnam is not None else None,
            "cnam_fid": f"{cnam:08X}" if cnam is not None else None,
            "fnam_fids": [f"{f:08X}" for f in fnams],
            "ingredients": [
                {"component_fid": f"{x['component_fid']:08X}", "count": x["count"]}
                for x in fvpas
            ],
        }
        if any(f in menu_filter_fids for f in fnams):
            menu_recipes.append(entry)
        if scrap_filter_fid in fnams:
            scrap_recipes.append(entry)

    return {
        "schema_version": 1,
        "exclude_creation_club": exclude_cc,
        "excluded_branches": excluded_branches,
        "counts": {
            "menu_leaf_keywords": len(menu_filter_fids),
            "menu_recipes": len(menu_recipes),
            "scrap_recipes": len(scrap_recipes),
            "components": len(components),
            "junk_items": len(junk_items),
            "prps_records": len(prps_records),
        },
        "menu_tree": menu_tree,
        "components": components,
        "junk_items": junk_items,
        "prps_records": prps_records,
        "menu_recipes": menu_recipes,
        "scrap_recipes": scrap_recipes,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Offline FO4 workshop census parser (outputs to a private path).")
    p.add_argument("--master", required=True, help="Explicit path to Fallout4.esm")
    p.add_argument("--out", required=True, help="Private JSON output path outside the repo")
    p.add_argument("--include-cc", action="store_true", help="Include Creation Club menu branch")
    args = p.parse_args(argv)

    with open(args.master, "rb") as f:
        data = f.read()
    report = run_census(data, exclude_cc=not args.include_cc)
    out_dir = os.path.dirname(os.path.abspath(args.out))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    c = report["counts"]
    print(
        f"fo4_census: menu_kw={c['menu_leaf_keywords']} menu_cobj={c['menu_recipes']} "
        f"scrap_cobj={c['scrap_recipes']} cmpo={c['components']} junk={c['junk_items']} prps={c['prps_records']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
