"""Read-only Starfield location, worldspace, generated-content, map-marker, and lever-keyword census.

Reads `Starfield.esm` (and optionally `FO4TerrainCore.esm` / `FO4TerrainCore_Mars.esm`) via memory-mapped raw parsing
(`src/fo4sf/planet/esm.py`, no Mutagen) and reports:
  - Record counts (`STDT`, `PNDT`, `WRLD`, `LCTN`, `LSCR`, `PCMT`, `PCBN`, `PCCN`, `PKIN`, `KYWD`, `LCRT`, `BIOM`, `GBFM`).
  - Map-marker references per worldspace (`NAME` in `0x000010`, `0x254244`, `0x254245`, `0x31FB3E`).
  - `LCTN` keyword histograms, `SSol` subtree counts, and resolved exclusion/lever keywords by EditorID.
  - Structural subrecord/condition counts across `LSCR` loading screens and `WRLD` flag distributions (zero `FULL`/`DESC`
    display strings ever read or emitted).
  - Our own `FO4TerrainCore.esm` `LCTN` keywords, `WRLD` flags/overlay/biome links, `SFBK` fields, and optional
    `FO4TerrainCore_Mars.esm` `PNDT` master-worldspace override summary.

Refuses any output path inside a Git repository/worktree, inside a game installation directory, or aliasing an input.
"""
from __future__ import annotations

import argparse
import collections
import json
import mmap
import os
import re
import struct
import sys
import zlib
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
if os.path.join(REPO, "src") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "src"))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from fo4_world_census import CensusPathError, refuse_unsafe_output_path  # noqa: E402
from fo4sf.planet import esm, probe, records  # noqa: E402

COMPRESSED = 0x00040000
DELETED = 0x00000020

WANT_TOP_GROUPS = frozenset(
    {
        b"STDT",
        b"PNDT",
        b"WRLD",
        b"LCTN",
        b"LSCR",
        b"PCMT",
        b"PCBN",
        b"PCCN",
        b"PKIN",
        b"KYWD",
        b"LCRT",
        b"BIOM",
        b"GBFM",
    }
)

MAP_MARKER_BASES = frozenset({0x000010, 0x254244, 0x254245, 0x31FB3E})

LEVER_EDITOR_IDS: Tuple[str, ...] = (
    "PCM_OverlayExclusionZone",
    "PCM_OverlayExclusionZone_HumanLocations",
    "LocTypeNoPCMScanTreeContent",
    "LocTypeNoPCMCreatureContent",
    "LocTypeSENotAllowed",
    "LocTypeNoHumanPresence",
    "LocTypeOverlay",
)

LEVER_DISCOVERY_REGEX = re.compile(
    r"(PCM_OverlayExclusionZone|LocTypeOverlayExclusionZone|LocTypeNoPCM|LocTypeSENotAllowed|LocTypeNoHumanPresence|LocTypeOverlay)",
    re.IGNORECASE,
)

HAND_BUILT_WORLD_PROBES: Tuple[str, ...] = (
    "NewAtlantis",
    "CydoniaCity",
    "AkilaCity",
    "NeonCity",
    "LC172World",
    "TempJemisonWorld",
)


def _hex8(fid: Optional[int]) -> Optional[str]:
    if fid is None:
        return None
    return f"0x{fid & 0xFFFFFFFF:08X}"


def _iter_subs_fast(body: bytes) -> Iterator[Tuple[bytes, bytes]]:
    i = 0
    n = len(body)
    while i + 6 <= n:
        sig = body[i : i + 4]
        sz = struct.unpack_from("<H", body, i + 4)[0]
        if sig == b"XXXX":
            if i + 16 > n:
                break
            big = struct.unpack_from("<I", body, i + 6)[0]
            i += 10
            sig = body[i : i + 4]
            yield sig, body[i + 6 : i + 6 + big]
            i += 6 + big
            continue
        yield sig, body[i + 6 : i + 6 + sz]
        i += 6 + sz


def _decompress_body(buf: mmap.mmap, off: int, size: int, flags: int) -> bytes:
    raw = bytes(buf[off + 24 : off + 24 + size])
    if flags & COMPRESSED:
        return zlib.decompress(raw[4:])
    return raw


def _u32_or_none(data: Optional[bytes]) -> Optional[int]:
    if data is not None and len(data) >= 4:
        return struct.unpack_from("<I", data, 0)[0]
    return None


def _inspect_core_plugin(
    core_path: str,
    kywd_by_local: Dict[int, str],
    lctn_by_local: Dict[int, str],
    biom_by_local: Dict[int, str],
) -> Dict[str, Any]:
    counts: Dict[str, int] = collections.Counter()
    lctn_rows: List[Dict[str, Any]] = []
    wrld_rows: List[Dict[str, Any]] = []
    sfbk_rows: List[Dict[str, Any]] = []

    with esm.Plugin(core_path) as plug:
        sf_indices = {i for i, m in enumerate(plug.masters) if m.lower() == "starfield.esm"}
        for gname, spans in sorted(plug.groups.items()):
            for start, end in spans:
                for item in plug.walk(start, end):
                    if item[0] != "REC":
                        continue
                    _kind, roff, rsig, _depth = item
                    counts[rsig.decode("latin1")] += 1
                    if rsig == b"LCTN":
                        rec = plug.record_at(roff)
                        pnam = _u32_or_none(rec.get(b"PNAM"))
                        pnam_edid = lctn_by_local.get(pnam & 0xFFFFFF) if (pnam is not None and (pnam >> 24) in sf_indices) else None
                        kw_fids = records.keywords_of(rec)
                        kw_list = []
                        kw_edids_present = set()
                        for kfid in kw_fids:
                            kedid = kywd_by_local.get(kfid & 0xFFFFFF) if (kfid >> 24) in sf_indices else None
                            if kedid:
                                kw_edids_present.add(kedid)
                            kw_list.append({"form_id": _hex8(kfid), "edid": kedid})
                        lever_state = {lev: (lev in kw_edids_present) for lev in LEVER_EDITOR_IDS[:5]}
                        lctn_rows.append(
                            {
                                "form_id": _hex8(rec.formid),
                                "local_id": f"0x{rec.formid & 0xFFFFFF:06X}",
                                "edid": rec.edid,
                                "parent_lctn": {"form_id": _hex8(pnam), "edid": pnam_edid} if pnam is not None else None,
                                "keywords": kw_list,
                                "exclusion_levers_present": lever_state,
                            }
                        )
                    elif rsig == b"WRLD":
                        rec = plug.record_at(roff)
                        ov = probe.component_fields(rec, "BGSWorldSpaceOverlay_Component")
                        ov_info = None
                        if ov and len(ov.get("SNAM", b"")) == 4 and len(ov.get("PNAM", b"")) == 4:
                            bnam_ov = _u32_or_none(ov.get("BNAM"))
                            ov_info = {
                                "system_id": struct.unpack_from("<i", ov["SNAM"], 0)[0],
                                "planet_id": struct.unpack_from("<i", ov["PNAM"], 0)[0],
                                "sfbk_form_id": _hex8(bnam_ov),
                            }
                        bnam_top = _u32_or_none(probe.top_level(rec, b"BNAM"))
                        bnam_edid = biom_by_local.get(bnam_top & 0xFFFFFF) if (bnam_top is not None and (bnam_top >> 24) in sf_indices) else None
                        cnam_top = _u32_or_none(probe.top_level(rec, b"CNAM"))
                        fnam_bytes = probe.top_level(rec, b"FNAM") or b""
                        data_bytes = probe.top_level(rec, b"DATA") or b""
                        dnam_bytes = probe.top_level(rec, b"DNAM")
                        dnam_vals = list(struct.unpack_from("<2f", dnam_bytes, 0)) if dnam_bytes and len(dnam_bytes) >= 8 else None
                        nam0_bytes = probe.top_level(rec, b"NAM0")
                        nam9_bytes = probe.top_level(rec, b"NAM9")
                        whgt_bytes = probe.top_level(rec, b"WHGT")
                        xclw_bytes = probe.top_level(rec, b"XCLW")
                        wrld_rows.append(
                            {
                                "form_id": _hex8(rec.formid),
                                "local_id": f"0x{rec.formid & 0xFFFFFF:06X}",
                                "edid": rec.edid,
                                "data_flags_hex": data_bytes.hex(),
                                "fnam_flags_hex": fnam_bytes.hex(),
                                "fnam_int": int.from_bytes(fnam_bytes, "little") if fnam_bytes else 0,
                                "overlay": ov_info,
                                "biome": {"form_id": _hex8(bnam_top), "edid": bnam_edid} if bnam_top is not None else None,
                                "climate": _hex8(cnam_top),
                                "dnam_land_water_m": [round(float(v), 3) for v in dnam_vals] if dnam_vals else None,
                                "nam0_min_m": [round(float(v), 3) for v in struct.unpack_from("<2f", nam0_bytes, 0)] if nam0_bytes and len(nam0_bytes) >= 8 else None,
                                "nam9_max_m": [round(float(v), 3) for v in struct.unpack_from("<2f", nam9_bytes, 0)] if nam9_bytes and len(nam9_bytes) >= 8 else None,
                                "whgt_present": bool(whgt_bytes),
                                "xclw_present": bool(xclw_bytes),
                            }
                        )
                    elif rsig == b"SFBK":
                        rec = plug.record_at(roff)
                        dnam_b = rec.get(b"DNAM")
                        enam_b = rec.get(b"ENAM")
                        whgt_b = rec.get(b"WHGT")
                        sfbk_rows.append(
                            {
                                "form_id": _hex8(rec.formid),
                                "local_id": f"0x{rec.formid & 0xFFFFFF:06X}",
                                "edid": rec.edid,
                                "anam": esm.zstring(rec.get(b"ANAM") or b""),
                                "dnam_cells": list(struct.unpack_from("<2I", dnam_b, 0)) if dnam_b and len(dnam_b) >= 8 else None,
                                "enam_hmin_hmax_m": [round(float(v), 3) for v in struct.unpack_from("<2f", enam_b, 0)] if enam_b and len(enam_b) >= 8 else None,
                                "inam_hex": (rec.get(b"INAM") or b"").hex(),
                                "whgt_float": float(struct.unpack_from("<f", whgt_b, 0)[0]) if whgt_b and len(whgt_b) >= 4 else None,
                            }
                        )

        return {
            "plugin": os.path.basename(core_path),
            "bytes": os.path.getsize(core_path),
            "masters": list(plug.masters),
            "record_counts": dict(sorted(counts.items())),
            "locations": lctn_rows,
            "worlds": wrld_rows,
            "blocks": sfbk_rows,
        }


def _inspect_registration_plugin(
    reg_path: str,
    kywd_by_local: Optional[Dict[int, str]] = None,
    lctn_by_owner: Optional[Dict[Tuple[str, int], str]] = None,
    biom_by_owner: Optional[Dict[Tuple[str, int], str]] = None,
) -> Dict[str, Any]:
    counts: Dict[str, int] = collections.Counter()
    pndt_rows: List[Dict[str, Any]] = []
    lctn_rows: List[Dict[str, Any]] = []
    wrld_rows: List[Dict[str, Any]] = []
    kywd_map = kywd_by_local or {}
    lctn_map = lctn_by_owner or {}
    biom_map = biom_by_owner or {}

    with esm.Plugin(reg_path) as plug:
        sf_indices = {i for i, m in enumerate(plug.masters) if m.lower() == "starfield.esm"}

        def _owner_name(fid: int) -> str:
            idx = fid >> 24
            if idx < len(plug.masters):
                return plug.masters[idx].lower()
            return os.path.basename(reg_path).lower()

        for gname, spans in sorted(plug.groups.items()):
            for start, end in spans:
                for item in plug.walk(start, end):
                    if item[0] != "REC":
                        continue
                    _kind, roff, rsig, _depth = item
                    counts[rsig.decode("latin1")] += 1
                    if rsig == b"PNDT":
                        rec = plug.record_at(roff)
                        mws = [
                            {"lat_rad": round(float(la), 6), "lon_rad": round(float(lo), 6), "world_form_id": _hex8(wf)}
                            for la, lo, wf in records.master_worldspaces(rec)
                        ]
                        pndt_rows.append(
                            {
                                "form_id": _hex8(rec.formid),
                                "edid": rec.edid,
                                "master_worldspaces_count": len(mws),
                                "master_worldspaces": mws,
                            }
                        )
                    elif rsig == b"LCTN":
                        rec = plug.record_at(roff)
                        pnam = _u32_or_none(rec.get(b"PNAM"))
                        pnam_edid = lctn_map.get((_owner_name(pnam), pnam & 0xFFFFFF)) if pnam is not None else None
                        kw_fids = records.keywords_of(rec)
                        kw_list = []
                        kw_edids_present = set()
                        for kfid in kw_fids:
                            kedid = kywd_map.get(kfid & 0xFFFFFF) if (kfid >> 24) in sf_indices else None
                            if kedid:
                                kw_edids_present.add(kedid)
                            kw_list.append({"form_id": _hex8(kfid), "edid": kedid})
                        lever_state = {lev: (lev in kw_edids_present) for lev in LEVER_EDITOR_IDS[:5]}
                        lctn_rows.append(
                            {
                                "form_id": _hex8(rec.formid),
                                "local_id": f"0x{rec.formid & 0xFFFFFF:06X}",
                                "edid": rec.edid,
                                "parent_lctn": {"form_id": _hex8(pnam), "edid": pnam_edid} if pnam is not None else None,
                                "keywords": kw_list,
                                "exclusion_levers_present": lever_state,
                            }
                        )
                    elif rsig == b"WRLD":
                        rec = plug.record_at(roff)
                        ov = probe.component_fields(rec, "BGSWorldSpaceOverlay_Component")
                        ov_info = None
                        if ov and len(ov.get("SNAM", b"")) == 4 and len(ov.get("PNAM", b"")) == 4:
                            bnam_ov = _u32_or_none(ov.get("BNAM"))
                            ov_info = {
                                "system_id": struct.unpack_from("<i", ov["SNAM"], 0)[0],
                                "planet_id": struct.unpack_from("<i", ov["PNAM"], 0)[0],
                                "sfbk_form_id": _hex8(bnam_ov),
                            }
                        bnam_top = _u32_or_none(probe.top_level(rec, b"BNAM"))
                        bnam_edid = biom_map.get((_owner_name(bnam_top), bnam_top & 0xFFFFFF)) if bnam_top is not None else None
                        fnam_bytes = probe.top_level(rec, b"FNAM") or b""
                        data_bytes = probe.top_level(rec, b"DATA") or b""
                        wrld_rows.append(
                            {
                                "form_id": _hex8(rec.formid),
                                "local_id": f"0x{rec.formid & 0xFFFFFF:06X}",
                                "edid": rec.edid,
                                "data_flags_hex": data_bytes.hex(),
                                "fnam_flags_hex": fnam_bytes.hex(),
                                "fnam_int": int.from_bytes(fnam_bytes, "little") if fnam_bytes else 0,
                                "overlay": ov_info,
                                "biome": {"form_id": _hex8(bnam_top), "edid": bnam_edid} if bnam_top is not None else None,
                            }
                        )
        return {
            "plugin": os.path.basename(reg_path),
            "bytes": os.path.getsize(reg_path),
            "masters": list(plug.masters),
            "record_counts": dict(sorted(counts.items())),
            "pndt_overrides": pndt_rows,
            "locations": lctn_rows,
            "worlds": wrld_rows,
        }


def run_sf_census(
    starfield_esm: str,
    core_esm: str = "",
    registration_esm: str = "",
    home_esm: str = "",
) -> Dict[str, Any]:
    """Walk `Starfield.esm` (and optional core, home, and registration ESMs) read-only and return a redacted census dictionary."""
    counts: Dict[str, int] = collections.Counter()
    kywd_by_fid: Dict[int, str] = {}
    biom_by_fid: Dict[int, str] = {}
    lctn_by_fid: Dict[int, Tuple[str, Optional[int], List[int]]] = {}
    wrld_by_fid: Dict[int, Dict[str, Any]] = {}
    map_markers_by_wfid: Dict[Optional[int], int] = collections.Counter()

    lscr_sub_hist: Dict[str, int] = collections.Counter()
    lscr_with_ctda = 0
    lscr_with_kwda = 0
    lscr_ctda_total = 0

    with open(starfield_esm, "rb") as fh:
        with mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as buf:
            if len(buf) < 24 or buf[:4] != b"TES4":
                raise ValueError(f"{os.path.basename(starfield_esm)}: not a TES4 plugin")
            hdr_size = struct.unpack_from("<I", buf, 4)[0]

            def walk(start: int, end: int, cur_world: Optional[int]) -> None:
                i = start
                while i + 24 <= end:
                    sig = bytes(buf[i : i + 4])
                    size = struct.unpack_from("<I", buf, i + 4)[0]
                    if sig == b"GRUP":
                        if size < 24 or i + size > end:
                            break
                        label = bytes(buf[i + 8 : i + 12])
                        gtype = struct.unpack_from("<i", buf, i + 12)[0]
                        if gtype == 0 and label not in WANT_TOP_GROUPS and label != b"CELL":
                            i += size
                            continue
                        next_world = struct.unpack_from("<I", label, 0)[0] if gtype == 1 else cur_world
                        walk(i + 24, i + size, next_world)
                        i += size
                        continue

                    if i + 24 + size > end:
                        break
                    flags, fid = struct.unpack_from("<II", buf, i + 8)
                    if not (flags & DELETED):
                        counts[sig.decode("latin1")] += 1
                        if sig == b"KYWD":
                            body = _decompress_body(buf, i, size, flags)
                            for s, v in _iter_subs_fast(body):
                                if s == b"EDID":
                                    kywd_by_fid[fid] = v.rstrip(b"\0").decode("latin1")
                                    break
                        elif sig == b"BIOM":
                            body = _decompress_body(buf, i, size, flags)
                            for s, v in _iter_subs_fast(body):
                                if s == b"EDID":
                                    biom_by_fid[fid] = v.rstrip(b"\0").decode("latin1")
                                    break
                        elif sig == b"LCTN":
                            body = _decompress_body(buf, i, size, flags)
                            edid = ""
                            par: Optional[int] = None
                            kws: List[int] = []
                            for s, v in _iter_subs_fast(body):
                                if s == b"EDID":
                                    edid = v.rstrip(b"\0").decode("latin1")
                                elif s == b"PNAM" and len(v) == 4:
                                    par = struct.unpack_from("<I", v, 0)[0]
                                elif s == b"KWDA" and len(v) >= 4:
                                    kws = list(struct.unpack_from(f"<{len(v) // 4}I", v, 0))
                            lctn_by_fid[fid] = (edid, par, kws)
                        elif sig == b"WRLD":
                            rec = esm.Record.parse(buf, i)
                            ov = probe.component_fields(rec, "BGSWorldSpaceOverlay_Component")
                            has_ov = bool(ov and len(ov.get("SNAM", b"")) == 4 and len(ov.get("PNAM", b"")) == 4)
                            fnam_b = probe.top_level(rec, b"FNAM") or b""
                            data_b = probe.top_level(rec, b"DATA") or b""
                            wrld_by_fid[fid] = {
                                "form_id": _hex8(fid),
                                "edid": rec.edid,
                                "has_overlay_component": has_ov,
                                "data_flags_hex": data_b.hex(),
                                "fnam_flags_hex": fnam_b.hex(),
                            }
                        elif sig == b"LSCR":
                            nonlocal lscr_with_ctda, lscr_with_kwda, lscr_ctda_total
                            body = _decompress_body(buf, i, size, flags)
                            seen_sigs = set()
                            ctda_here = 0
                            for s, _v in _iter_subs_fast(body):
                                sname = s.decode("latin1")
                                seen_sigs.add(sname)
                                if s == b"CTDA":
                                    ctda_here += 1
                            for sname in seen_sigs:
                                lscr_sub_hist[sname] += 1
                            if ctda_here > 0:
                                lscr_with_ctda += 1
                                lscr_ctda_total += ctda_here
                            if "KWDA" in seen_sigs:
                                lscr_with_kwda += 1
                        elif sig == b"REFR":
                            body = _decompress_body(buf, i, size, flags)
                            for s, v in _iter_subs_fast(body):
                                if s == b"NAME" and len(v) >= 4:
                                    base_id = struct.unpack_from("<I", v, 0)[0]
                                    if base_id in MAP_MARKER_BASES:
                                        map_markers_by_wfid[cur_world] += 1
                                    break
                    i += 24 + size

            walk(24 + hdr_size, len(buf), None)

    # Keyword histogram across all 6,017 LCTN
    kw_hist: Dict[str, int] = collections.Counter()
    kw_counts_by_fid: Dict[int, int] = collections.Counter()
    for _fid, (_ed, _par, kws) in lctn_by_fid.items():
        for kfid in kws:
            kw_counts_by_fid[kfid] += 1
            kw_hist[kywd_by_fid.get(kfid, _hex8(kfid) or "?")] += 1

    edid_to_kywd_fid = {edid: fid for fid, edid in kywd_by_fid.items() if edid}
    lever_resolved: Dict[str, Any] = {}
    for lev_edid in LEVER_EDITOR_IDS:
        kfid = edid_to_kywd_fid.get(lev_edid)
        lever_resolved[lev_edid] = {
            "present": kfid is not None,
            "form_id": _hex8(kfid),
            "vanilla_lctn_count": kw_counts_by_fid.get(kfid, 0) if kfid is not None else 0,
        }

    matching_levers = {
        edid: {"form_id": _hex8(fid), "vanilla_lctn_count": kw_counts_by_fid.get(fid, 0)}
        for fid, edid in sorted(kywd_by_fid.items())
        if edid and LEVER_DISCOVERY_REGEX.search(edid)
    }

    # SSol subtree
    ssol_fids = [fid for fid, (ed, _p, _k) in lctn_by_fid.items() if ed == "SSol"]
    children_map: Dict[Optional[int], List[int]] = collections.defaultdict(list)
    for fid, (_ed, par, _k) in lctn_by_fid.items():
        children_map[par if par else None].append(fid)

    ssol_info: Optional[Dict[str, Any]] = None
    if ssol_fids:
        sfid = ssol_fids[0]
        direct = children_map.get(sfid, [])
        descendants = 0
        stack = list(direct)
        while stack:
            cur = stack.pop()
            descendants += 1
            stack.extend(children_map.get(cur, []))
        ssol_info = {
            "form_id": _hex8(sfid),
            "direct_children_count": len(direct),
            "direct_children_edids": sorted(lctn_by_fid[c][0] for c in direct),
            "descendants_count": descendants,
        }

    # Map markers per worldspace
    markers_by_world_named: Dict[str, int] = {}
    for wfid, mcnt in sorted(map_markers_by_wfid.items(), key=lambda kv: (-kv[1], kv[0] or 0)):
        if wfid is None:
            key = "interior_cells"
        else:
            winfo = wrld_by_fid.get(wfid)
            wedid = winfo["edid"] if winfo and winfo["edid"] else "unknown"
            key = f"{_hex8(wfid)} {wedid}"
        markers_by_world_named[key] = mcnt

    # Worldspace flags summary
    fnam_hist: Dict[str, int] = collections.Counter()
    data_hist: Dict[str, int] = collections.Counter()
    overlay_world_count = 0
    probe_worlds: Dict[str, Any] = {}
    edid_to_wrld = {w["edid"].lower(): w for w in wrld_by_fid.values() if w["edid"]}
    for w in wrld_by_fid.values():
        fnam_hist[w["fnam_flags_hex"] or "none"] += 1
        data_hist[w["data_flags_hex"] or "none"] += 1
        if w["has_overlay_component"]:
            overlay_world_count += 1
    for p_edid in HAND_BUILT_WORLD_PROBES:
        if p_edid.lower() in edid_to_wrld:
            w = edid_to_wrld[p_edid.lower()]
            probe_worlds[w["edid"]] = w

    top_record_counts = {k: counts[k] for k in sorted(counts) if k != "REFR"}

    result: Dict[str, Any] = {
        "schema_version": 1,
        "tool": "scripts/terrain/sf_location_census.py",
        "starfield_plugin": os.path.basename(starfield_esm),
        "counts": top_record_counts,
        "refr_scanned_in_wrld_and_cell": counts["REFR"],
        "worldspace_summary": {
            "total": counts["WRLD"],
            "with_overlay_component": overlay_world_count,
            "without_overlay_component": counts["WRLD"] - overlay_world_count,
            "fnam_flags_histogram": dict(sorted(fnam_hist.items(), key=lambda kv: (-kv[1], kv[0]))),
            "data_flags_histogram": dict(sorted(data_hist.items(), key=lambda kv: (-kv[1], kv[0]))),
            "reference_worlds": probe_worlds,
        },
        "map_markers": {
            "total": sum(map_markers_by_wfid.values()),
            "worlds_with_markers": sum(1 for wfid in map_markers_by_wfid if wfid is not None),
            "interior_markers": map_markers_by_wfid.get(None, 0),
            "by_world": markers_by_world_named,
        },
        "lctn_summary": {
            "total": counts["LCTN"],
            "root_count": len(children_map.get(None, [])),
            "ssol": ssol_info,
            "keyword_histogram": dict(kw_hist.most_common()),
        },
        "lever_keywords": lever_resolved,
        "matching_lever_keywords": matching_levers,
        "loading_screens": {
            "total": counts["LSCR"],
            "with_ctda_conditions": lscr_with_ctda,
            "total_ctda_conditions": lscr_ctda_total,
            "with_kwda_keywords": lscr_with_kwda,
            "subrecord_presence_histogram": dict(sorted(lscr_sub_hist.items())),
        },
        "our_core": None,
        "our_home": None,
        "our_registration": None,
    }

    kywd_local = {fid & 0xFFFFFF: ed for fid, ed in kywd_by_fid.items()}
    lctn_local = {fid & 0xFFFFFF: vals[0] for fid, vals in lctn_by_fid.items()}
    biom_local = {fid & 0xFFFFFF: ed for fid, ed in biom_by_fid.items()}
    lctn_owner: Dict[Tuple[str, int], str] = {("starfield.esm", k): v for k, v in lctn_local.items() if v}
    biom_owner: Dict[Tuple[str, int], str] = {("starfield.esm", k): v for k, v in biom_local.items() if v}

    if core_esm:
        core_info = _inspect_core_plugin(core_esm, kywd_local, lctn_local, biom_local)
        result["our_core"] = core_info
        cname = os.path.basename(core_esm).lower()
        for row in core_info["locations"]:
            if row["edid"]:
                lctn_owner[(cname, int(row["local_id"], 16))] = row["edid"]

    if home_esm:
        home_info = _inspect_core_plugin(home_esm, kywd_local, lctn_local, biom_local)
        with esm.Plugin(home_esm) as hp:
            hname = os.path.basename(home_esm).lower()
            home_bioms = []
            for brec in hp.records("BIOM", [b"BIOM"]):
                if brec.edid:
                    biom_owner[(hname, brec.formid & 0xFFFFFF)] = brec.edid
                home_bioms.append({"form_id": _hex8(brec.formid), "local_id": f"0x{brec.formid & 0xFFFFFF:06X}", "edid": brec.edid})
            home_info["biomes"] = home_bioms
        for row in home_info["locations"]:
            if row["edid"]:
                lctn_owner[(hname, int(row["local_id"], 16))] = row["edid"]
        result["our_home"] = home_info

    if registration_esm:
        result["our_registration"] = _inspect_registration_plugin(
            registration_esm,
            kywd_by_local=kywd_local,
            lctn_by_owner=lctn_owner,
            biom_by_owner=biom_owner,
        )

    return result


def inspect_host_plugins(
    starfield_esm: str,
    home_esm: str = "",
    registration_esm: str = "",
    core_esm: str = "",
    port_esm: str = "",
    extra_plugins: Sequence[str] = (),
) -> Dict[str, Any]:
    """Fast read-only inspection of our host, core, port, and registration ESMs resolving keywords, locations,
    and biomes against `Starfield.esm` plus winning zero-Mars location census without walking exterior REFR trees."""
    from fo4sf.planet import home_planet_spec as hspec  # noqa: E402

    kywd_local: Dict[int, str] = {}
    lctn_local: Dict[int, str] = {}
    biom_local: Dict[int, str] = {}
    with esm.Plugin(starfield_esm) as sf:
        for rec in sf.records("KYWD", [b"KYWD"]):
            if rec.edid:
                kywd_local[rec.formid & 0xFFFFFF] = rec.edid
        for rec in sf.records("LCTN", [b"LCTN"]):
            if rec.edid:
                lctn_local[rec.formid & 0xFFFFFF] = rec.edid
        for rec in sf.records("BIOM", [b"BIOM"]):
            if rec.edid:
                biom_local[rec.formid & 0xFFFFFF] = rec.edid

    lctn_owner: Dict[Tuple[str, int], str] = {("starfield.esm", k): v for k, v in lctn_local.items()}
    biom_owner: Dict[Tuple[str, int], str] = {("starfield.esm", k): v for k, v in biom_local.items()}
    out: Dict[str, Any] = {"our_core": None, "our_port": None, "our_home": None, "our_registration": None, "zero_mars_audit": None}

    if core_esm:
        cinfo = _inspect_core_plugin(core_esm, kywd_local, lctn_local, biom_local)
        out["our_core"] = cinfo
        cname = os.path.basename(core_esm).lower()
        for row in cinfo["locations"]:
            if row["edid"]:
                lctn_owner[(cname, int(row["local_id"], 16))] = row["edid"]

    if port_esm:
        pinfo = _inspect_core_plugin(port_esm, kywd_local, lctn_local, biom_local)
        out["our_port"] = pinfo
        pname = os.path.basename(port_esm).lower()
        for row in pinfo["locations"]:
            if row["edid"]:
                lctn_owner[(pname, int(row["local_id"], 16))] = row["edid"]

    if home_esm:
        hinfo = _inspect_core_plugin(home_esm, kywd_local, lctn_local, biom_local)
        with esm.Plugin(home_esm) as hp:
            hname = os.path.basename(home_esm).lower()
            home_bioms = []
            for brec in hp.records("BIOM", [b"BIOM"]):
                if brec.edid:
                    biom_owner[(hname, brec.formid & 0xFFFFFF)] = brec.edid
                home_bioms.append({"form_id": _hex8(brec.formid), "local_id": f"0x{brec.formid & 0xFFFFFF:06X}", "edid": brec.edid})
            hinfo["biomes"] = home_bioms
        for row in hinfo["locations"]:
            if row["edid"]:
                lctn_owner[(hname, int(row["local_id"], 16))] = row["edid"]
        out["our_home"] = hinfo

    if registration_esm:
        out["our_registration"] = _inspect_registration_plugin(
            registration_esm,
            kywd_by_local=kywd_local,
            lctn_by_owner=lctn_owner,
            biom_by_owner=biom_owner,
        )

    audit_list = [p for p in (core_esm, port_esm, *extra_plugins, home_esm, registration_esm) if p]
    if audit_list:
        m_probs, m_summary = hspec.audit_zero_mars_references(audit_list)
        out["zero_mars_audit"] = {"problems": m_probs, **m_summary}
    return out


def write_sf_census_json(out_path: str, payload: Dict[str, Any], input_paths: Sequence[str] = ()) -> None:
    refuse_unsafe_output_path(out_path, input_paths)
    parent = os.path.dirname(os.path.abspath(out_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp_path = out_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    os.replace(tmp_path, out_path)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Read-only Starfield location, worldspace, PCM, and lever-keyword census")
    ap.add_argument("--starfield", required=True, help="Path to Starfield.esm")
    ap.add_argument("--core", default="", help="Optional path to FO4TerrainCore.esm")
    ap.add_argument("--port", default="", help="Optional path to FO4Port.esm")
    ap.add_argument("--home", default="", help="Optional path to FO4SFHome.esm")
    ap.add_argument("--registration", default="", help="Optional path to FO4TerrainCore_Mars.esm / FO4TerrainCore_Home.esm")
    ap.add_argument("--extra-plugins", default="", help="Optional comma-separated extra plugins in load order for zero-Mars census")
    ap.add_argument("--plugins-only", action="store_true", help="Fast mode: inspect --core/--port/--home/--registration against Starfield.esm KYWD/LCTN/BIOM only")
    ap.add_argument("--out", required=True, help="Output JSON path (outside Git worktrees and game folders)")
    args = ap.parse_args(argv)

    extra_list = [p.strip() for p in args.extra_plugins.split(",") if p.strip()]
    inputs = [p for p in (args.starfield, args.core, args.port, args.home, args.registration, *extra_list) if p]
    try:
        refuse_unsafe_output_path(args.out, inputs)
        if args.plugins_only:
            report = inspect_host_plugins(
                args.starfield,
                home_esm=args.home,
                registration_esm=args.registration,
                core_esm=args.core,
                port_esm=args.port,
                extra_plugins=extra_list,
            )
        else:
            report = run_sf_census(args.starfield, args.core, args.registration, home_esm=args.home)
        write_sf_census_json(args.out, report, inputs)
    except (CensusPathError, esm.EsmError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.plugins_only:
        print(json.dumps(report, indent=2))
        return 0

    summary = {
        "counts": report["counts"],
        "map_markers_total": report["map_markers"]["total"],
        "worlds_with_markers": report["map_markers"]["worlds_with_markers"],
        "lever_keywords": report["lever_keywords"],
        "our_core_worlds": report["our_core"]["worlds"] if report["our_core"] else None,
        "our_core_locations": report["our_core"]["locations"] if report["our_core"] else None,
        "our_home_locations": report["our_home"]["locations"] if report["our_home"] else None,
        "our_registration_locations": report["our_registration"]["locations"] if report["our_registration"] else None,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
