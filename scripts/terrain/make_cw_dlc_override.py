"""make_cw_dlc_override.py: staged Commonwealth DLC reference override + two-way DLC interior doors (WB5 & WB5b).

Builds `FO4TerrainCore_DLC.esm` on top of an unchanged `FO4TerrainCore.esm` and pinned `FO4DLC.esm` stage from the
Commonwealth DLC diff JSON (`winning_dlc_edits`):
  - Masters: `Starfield.esm` (0x00), `FO4TerrainCore.esm` (0x01), `FO4DLC.esm` (0x02); own index = 0x03.
  - Core deletions (`kind == "deleted"`, resolved in core): overridden at the exact `0x01XXXXXX` `REFR` FormID with
    `InitiallyDisabled` (`0x00000800`) set — never `Deleted` (`0x00000020`).
  - Core moves / modifications (`kind in ("moved", "modified")`, resolved in core): overridden at the exact `0x01XXXXXX`
    `REFR` FormID with updated `DATA` (`pos / 70`, `rot`), `XSCL`, flags, and `NAME` when `base_changed`.
  - Changed / deleted references absent from `FO4TerrainCore.esm` (`core.status != "resolved"`) are listed by name in
    `not_in_core`.
  - Added DLC references (`kind == "added"`):
      1. Reuse base from `FO4TerrainCore.esm` (`0x01XXXXXX`) when the core already holds a base for that Fallout 4 base;
      2. Otherwise reuse base from `FO4DLC.esm` (`0x02XXXXXX`) by EditorID through `FO4DLC`'s `formids.json` (never
         writing a duplicate base for any model `FO4DLC.esm` holds);
      3. Otherwise, when `--extra-manifest` supplies a converted model neither holds, author a `STAT` base in
         `FO4TerrainCore_DLC.esm` (`0x03XXXXXX`) under the `FO4DLC_` / `fo4dlc\\` prefix and list it by name in
         `override_authored_bases`;
      4. Otherwise list by name in `missing_bases`.
  - Pins `FO4DLC`'s `formids.json` SHA-256 (`PINNED_FO4DLC_FORMIDS_SHA256`) and refuses any stage whose hash differs.
  - Writes Commonwealth -> `FO4DLC.esm` exterior load doors (`DLC06VaultWorkshop` and `DLC04TransitCenter01`) +
    persistent arrival `XMarker`s in the core-build layout (`overlays_params.json`, `objects.json`, `formids.json`) read
    by `scripts/terrain/vmad_patch.py`, and optionally produces the patched `FO4DLC.esm` stage via `--dlc-doors-out`.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
from typing import Any
import zlib

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from fo4sf import exterior, fo4land, terrain_grid as tg  # noqa: E402
from fo4sf.planet import esm as planet_esm  # noqa: E402
from fo4sf.terrain.path_guard import OutputPathRefusedError, refuse_unsafe_output_path  # noqa: E402
import vmad_patch  # noqa: E402

OVERRIDE_PLUGIN_NAME = "FO4TerrainCore_DLC.esm"
EXPECTED_MASTERS = ("Starfield.esm", "FO4TerrainCore.esm", "FO4DLC.esm")
PINNED_FO4DLC_FORMIDS_SHA256 = "abd6b2fbc5779322d645c1b56c10d6eff814b207a5d85d4f7179d8831f44fe46"

ESM_HEDR_VERSION = 0.96
RECORD_FLAG_ESM = 0x00000001
RECORD_FLAG_DELETED = 0x00000020
RECORD_FLAG_PERSISTENT = 0x00000400
RECORD_FLAG_INITIALLY_DISABLED = 0x00000800
RECORD_FLAG_COMPRESSED = 0x00040000
FORM_VERSION_SF = 0x0240

GROUP_TOP = 0
GROUP_WORLD_CHILDREN = 1
GROUP_EXT_CELL_BLOCK = 4
GROUP_EXT_CELL_SUBBLOCK = 5
GROUP_CELL_CHILDREN = 6
GROUP_CELL_PERSISTENT = 8
GROUP_CELL_TEMPORARY = 9

SIG_TO_EXPORT_TYPE: dict[str, str] = {
    "STAT": "Static",
    "SCOL": "StaticCollection",
    "MSTT": "MovableStatic",
    "FURN": "Furniture",
    "DOOR": "Door",
    "ACTI": "Activator",
    "CONT": "Container",
    "MISC": "MiscItem",
    "TERM": "Terminal",
    "FLOR": "Flora",
    "ALCH": "Ingestible",
    "WEAP": "Weapon",
    "AMMO": "Ammunition",
    "ARMO": "Armor",
    "LIGH": "Light",
    "TXST": "TextureSet",
    "BNDS": "BendableSpline",
    "IDLM": "IdleMarker",
    "SOUN": "SoundMarker",
    "ASPC": "AcousticSpace",
    "BOOK": "Book",
    "NOTE": "Note",
}

SKIP_FO4_BASE_SCAN_GROUPS = {b"WRLD", b"CELL", b"DIAL", b"QUST", b"NAVM", b"LAND", b"REGN", b"IDLE", b"PACK", b"PERK"}


def sha256_file(path: str | os.PathLike[str]) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: str | os.PathLike[str]) -> Any:
    with open(path, encoding="utf-8-sig") as stream:
        return json.load(stream)


def _record_fields_decompress(rec: vmad_patch.Record) -> list[tuple[bytes, bytes]]:
    if rec.flags & RECORD_FLAG_COMPRESSED:
        raw = zlib.decompress(rec.data[4:])
        return list(fo4land.iter_subrecords(raw))
    return rec.fields()


def _count_tree_items(items: list[Any]) -> int:
    total = 0
    for item in items:
        total += 1
        if isinstance(item, vmad_patch.Group):
            total += _count_tree_items(item.children)
    return total


def _decode_xtel(data: bytes, masters: list[str], own_plugin: str) -> dict[str, Any] | None:
    if len(data) < 28:
        return None
    tdoor, tx, ty, tz, rx, ry, rz = struct.unpack_from("<I6f", data, 0)
    tflags = struct.unpack_from("<I", data, 28)[0] if len(data) >= 32 else 0
    idx = tdoor >> 24
    plg = masters[idx] if idx < len(masters) else own_plugin
    return {
        "door": f"{tdoor & 0xFFFFFF:06X}:{plg}",
        "pos": [float(tx), float(ty), float(tz)],
        "rot": [float(rx), float(ry), float(rz)],
        "flags": int(tflags),
    }


def read_fo4_metadata(
    fo4_data_dir: Path,
    needed_bases: set[str],
    needed_door_refs: set[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Stream-scan only top-level base groups (and DLC door cells) in FO4 ESMs for needed FormKeys."""
    bases_by_plugin: dict[str, set[int]] = {}
    for fk in needed_bases:
        lid_s, _, plg = fk.partition(":")
        if plg:
            bases_by_plugin.setdefault(plg, set()).add(int(lid_s, 16))

    doors_by_plugin: dict[str, set[int]] = {}
    for fk in needed_door_refs:
        lid_s, _, plg = fk.partition(":")
        if plg:
            doors_by_plugin.setdefault(plg, set()).add(int(lid_s, 16))

    all_plugins = sorted(set(bases_by_plugin) | set(doors_by_plugin))
    base_meta: dict[str, dict[str, Any]] = {}
    door_meta: dict[str, dict[str, Any]] = {}

    for plg in all_plugins:
        candidates = [fo4_data_dir / plg]
        esm_path = next((c for c in candidates if c.is_file()), None)
        if esm_path is None:
            # Case-insensitive fallback
            low = plg.casefold()
            esm_path = next((p for p in fo4_data_dir.iterdir() if p.name.casefold() == low), None)
        if esm_path is None or not esm_path.is_file():
            raise FileNotFoundError(f"Missing Fallout 4 source plugin {plg!r} under {fo4_data_dir}")

        buf = esm_path.read_bytes()
        if buf[:4] != b"TES4":
            raise ValueError(f"{esm_path}: not a TES4 plugin")
        hsize = struct.unpack_from("<I", buf, 4)[0]
        tes4 = vmad_patch.Record(buf[:24], buf[24 : 24 + hsize])
        masters = [fo4land.zstring(d) for s, d in tes4.fields() if s == b"MAST"]
        own_idx = len(masters)
        want_bases = bases_by_plugin.get(plg, set())
        want_doors = doors_by_plugin.get(plg, set())

        def scan_range(start: int, end: int, in_world_or_cell: bool) -> None:
            off = start
            while off < end:
                sig = buf[off : off + 4]
                size = struct.unpack_from("<I", buf, off + 4)[0]
                if sig == b"GRUP":
                    label = buf[off + 8 : off + 12]
                    gtype = struct.unpack_from("<I", buf, off + 12)[0]
                    if gtype == GROUP_TOP:
                        if label in (b"WRLD", b"CELL"):
                            if want_doors:
                                scan_range(off + 24, off + size, True)
                        elif label not in SKIP_FO4_BASE_SCAN_GROUPS and want_bases:
                            scan_range(off + 24, off + size, False)
                    else:
                        scan_range(off + 24, off + size, in_world_or_cell)
                    off += size
                else:
                    fid = struct.unpack_from("<I", buf, off + 12)[0]
                    if (fid >> 24) == own_idx:
                        lid = fid & 0xFFFFFF
                        if not in_world_or_cell and lid in want_bases:
                            rec = vmad_patch.Record(buf[off : off + 24], buf[off + 24 : off + 24 + size])
                            flds = _record_fields_decompress(rec)
                            edid = next((fo4land.zstring(d) for s, d in flds if s == b"EDID"), "")
                            modl = next((fo4land.zstring(d) for s, d in flds if s == b"MODL"), "")
                            base_meta[f"{lid:06X}:{plg}"] = {
                                "sig": sig.decode("latin-1"),
                                "edid": edid,
                                "model": modl,
                            }
                        elif in_world_or_cell and sig == b"REFR" and lid in want_doors:
                            rec = vmad_patch.Record(buf[off : off + 24], buf[off + 24 : off + 24 + size])
                            flds = _record_fields_decompress(rec)
                            edid = next((fo4land.zstring(d) for s, d in flds if s == b"EDID"), "")
                            name_b = next((struct.unpack_from("<I", d)[0] for s, d in flds if s == b"NAME"), None)
                            data_f = next(
                                (struct.unpack_from("<6f", d) for s, d in flds if s == b"DATA" and len(d) >= 24),
                                None,
                            )
                            xtel_b = next((d for s, d in flds if s == b"XTEL"), None)
                            base_fk = None
                            if name_b is not None:
                                b_idx = name_b >> 24
                                b_plg = masters[b_idx] if b_idx < len(masters) else plg
                                base_fk = f"{name_b & 0xFFFFFF:06X}:{b_plg}"
                            door_meta[f"{lid:06X}:{plg}"] = {
                                "edid": edid,
                                "base": base_fk,
                                "pos": list(data_f[:3]) if data_f else None,
                                "rot": list(data_f[3:6]) if data_f else None,
                                "xtel": _decode_xtel(xtel_b, masters, plg) if xtel_b else None,
                            }
                    off += 24 + size

        scan_range(24 + hsize, len(buf), False)

    return base_meta, door_meta


def _find_dlc_manifest(dlc_dir: Path) -> dict[str, Any]:
    for candidate in (
        dlc_dir / "manifest_merged.json",
        dlc_dir / "manifest.json",
        dlc_dir.parent / "plugin" / "manifest_merged.json",
        dlc_dir.parent / "manifest_merged.json",
    ):
        if candidate.is_file():
            return _load_json(candidate)
    raise FileNotFoundError(f"Could not find manifest_merged.json in {dlc_dir} or {dlc_dir.parent / 'plugin'}")


def _index_core_world(core_plugin: vmad_patch.Plugin) -> dict[str, Any]:
    """Extract `FO4Core_Commonwealth` `WRLD`, persistent `CELL`, exterior `(cx, cy)` `CELL`s, and all `REFR`s."""
    wrld_top = next((g for g in core_plugin.items if isinstance(g, vmad_patch.Group) and g.label == b"WRLD"), None)
    if wrld_top is None:
        raise ValueError("Core plugin has no WRLD top group")
    wrld_rec = next((c for c in wrld_top.children if isinstance(c, vmad_patch.Record) and c.sig == b"WRLD"), None)
    wrld_children = next(
        (c for c in wrld_top.children if isinstance(c, vmad_patch.Group) and c.gtype == GROUP_WORLD_CHILDREN),
        None,
    )
    if wrld_rec is None or wrld_children is None:
        raise ValueError("Core plugin WRLD group lacks WRLD record or World Children group")

    pers_cell_rec: vmad_patch.Record | None = None
    cells_by_xy: dict[tuple[int, int], dict[str, Any]] = {}
    cells_by_fid: dict[int, dict[str, Any]] = {}
    block_order: list[tuple[int, int]] = []
    subblock_order: dict[tuple[int, int], list[tuple[int, int]]] = {}
    cell_order_in_subblock: dict[tuple[tuple[int, int], tuple[int, int]], list[int]] = {}

    for item in wrld_children.children:
        if isinstance(item, vmad_patch.Record) and item.sig == b"CELL":
            pers_cell_rec = item
            cells_by_fid[item.fid] = {"rec": item, "persistent": True, "xy": None}
        elif isinstance(item, vmad_patch.Group) and item.gtype == GROUP_EXT_CELL_BLOCK:
            bx, by = struct.unpack("<hh", item.label)
            bkey = (bx, by)
            block_order.append(bkey)
            subblock_order[bkey] = []
            for sub in item.children:
                if isinstance(sub, vmad_patch.Group) and sub.gtype == GROUP_EXT_CELL_SUBBLOCK:
                    sbx, sby = struct.unpack("<hh", sub.label)
                    sbkey = (sbx, sby)
                    subblock_order[bkey].append(sbkey)
                    cell_order_in_subblock[(bkey, sbkey)] = []
                    for citem in sub.children:
                        if isinstance(citem, vmad_patch.Record) and citem.sig == b"CELL":
                            xclc = next(
                                (struct.unpack_from("<ii", d) for s, d in citem.fields() if s == b"XCLC"),
                                None,
                            )
                            if xclc is not None:
                                xy = (int(xclc[0]), int(xclc[1]))
                                info = {
                                    "rec": citem,
                                    "persistent": False,
                                    "xy": xy,
                                    "block": bkey,
                                    "subblock": sbkey,
                                    "tail_block": item.tail,
                                    "tail_subblock": sub.tail,
                                }
                                cells_by_xy[xy] = info
                                cells_by_fid[citem.fid] = info
                                cell_order_in_subblock[(bkey, sbkey)].append(citem.fid)

    if pers_cell_rec is None:
        raise ValueError("Core plugin has no persistent world CELL record")

    refs_by_local: dict[int, tuple[vmad_patch.Record, int, int]] = {}
    own_idx = len(core_plugin.masters())
    for rec, path in core_plugin.walk():
        if rec.sig == b"REFR" and (rec.fid >> 24) == own_idx and len(path) >= 2:
            gtype_leaf = path[-1][0]
            cell_fid = struct.unpack("<I", path[-1][1])[0]
            refs_by_local[rec.fid & 0xFFFFFF] = (rec, cell_fid, gtype_leaf)

    return {
        "wrld_rec": wrld_rec,
        "wrld_tail": wrld_children.tail,
        "pers_cell_rec": pers_cell_rec,
        "cells_by_xy": cells_by_xy,
        "cells_by_fid": cells_by_fid,
        "block_order": block_order,
        "subblock_order": subblock_order,
        "cell_order_in_subblock": cell_order_in_subblock,
        "refs_by_local": refs_by_local,
    }


def _stat_record(fid: int, edid: str, model_rel: str) -> vmad_patch.Record:
    fields = [
        (b"EDID", edid.encode("utf-8") + b"\x00"),
        (b"OBND", b"\x00" * 24),
        (b"ODTY", b"\x00" * 4),
        (b"MODL", model_rel.replace("/", "\\").encode("utf-8") + b"\x00"),
    ]
    return vmad_patch.record_bytes(b"STAT", fid, 0, fields, version=FORM_VERSION_SF)


def _refr_record(
    fid: int,
    base_fid: int,
    pos_m: tuple[float, float, float] | list[float],
    rot_rad: tuple[float, float, float] | list[float],
    scale: float = 1.0,
    flags: int = 0,
    vmad_bytes: bytes | None = None,
    edid: str = "",
) -> vmad_patch.Record:
    fields: list[tuple[bytes, bytes]] = []
    if edid:
        fields.append((b"EDID", edid.encode("utf-8") + b"\x00"))
    if vmad_bytes is not None:
        fields.append((b"VMAD", bytes(vmad_bytes)))
    fields.append((b"NAME", struct.pack("<I", int(base_fid))))
    if abs(float(scale) - 1.0) > 1e-6:
        fields.append((b"XSCL", struct.pack("<f", float(scale))))
    fields.append((b"DATA", struct.pack("<6f", float(pos_m[0]), float(pos_m[1]), float(pos_m[2]), float(rot_rad[0]), float(rot_rad[1]), float(rot_rad[2]))))
    return vmad_patch.record_bytes(b"REFR", fid, flags, fields, version=FORM_VERSION_SF)


def _update_core_refr(
    orig: vmad_patch.Record,
    *,
    new_flags: int,
    new_base_fid: int | None = None,
    new_pos_m: tuple[float, float, float] | None = None,
    new_rot_rad: tuple[float, float, float] | None = None,
    new_scale: float | None = None,
) -> vmad_patch.Record:
    old_fields = orig.fields()
    out_fields: list[tuple[bytes, bytes]] = []
    had_xscl = False
    need_xscl = new_scale is not None and abs(float(new_scale) - 1.0) > 1e-6

    for sig, payload in old_fields:
        if sig == b"NAME" and new_base_fid is not None:
            out_fields.append((b"NAME", struct.pack("<I", int(new_base_fid))))
        elif sig == b"XSCL":
            had_xscl = True
            if new_scale is None:
                out_fields.append((sig, payload))
            elif need_xscl:
                out_fields.append((b"XSCL", struct.pack("<f", float(new_scale))))
        elif sig == b"DATA" and len(payload) >= 24 and (new_pos_m is not None or new_rot_rad is not None):
            ox, oy, oz, orx, ory, orz = struct.unpack_from("<6f", payload, 0)
            px, py, pz = new_pos_m if new_pos_m is not None else (ox, oy, oz)
            rx, ry, rz = new_rot_rad if new_rot_rad is not None else (orx, ory, orz)
            out_fields.append((b"DATA", struct.pack("<6f", px, py, pz, rx, ry, rz) + payload[24:]))
        else:
            out_fields.append((sig, payload))

    if new_scale is not None and need_xscl and not had_xscl:
        # Insert XSCL right before DATA (or at end)
        data_idx = next((i for i, (s, _) in enumerate(out_fields) if s == b"DATA"), len(out_fields))
        out_fields.insert(data_idx, (b"XSCL", struct.pack("<f", float(new_scale))))

    body = b"".join(vmad_patch.encode_field(s, d) for s, d in out_fields)
    ver, unk = struct.unpack_from("<HH", orig.header, 20)
    hdr = orig.sig + struct.pack("<IIIIHH", len(body), int(new_flags), orig.fid, 0, ver, unk)
    return vmad_patch.Record(hdr, body)


def _build_tes4_record(masters: tuple[str, ...], record_and_group_count: int, next_local_id: int) -> vmad_patch.Record:
    fields: list[tuple[bytes, bytes]] = [
        (b"HEDR", struct.pack("<fII", ESM_HEDR_VERSION, int(record_and_group_count), int(next_local_id))),
    ]
    for master in masters:
        fields.append((b"MAST", master.encode("utf-8") + b"\x00"))
        fields.append((b"DATA", b"\x00" * 8))
    return vmad_patch.record_bytes(b"TES4", 0, RECORD_FLAG_ESM, fields, version=FORM_VERSION_SF)


def build_override(
    *,
    edits_path: Path,
    core_dir: Path,
    dlc_dir: Path,
    out_dir: Path,
    fo4_data_dir: Path | None = None,
    base_catalog_path: Path | None = None,
    extra_manifest_path: Path | None = None,
    expected_dlc_formids_sha256: str = PINNED_FO4DLC_FORMIDS_SHA256,
    dlc_doors_out: Path | None = None,
) -> dict[str, Any]:
    extra_inputs = [str(edits_path), str(core_dir), str(dlc_dir)]
    if fo4_data_dir:
        extra_inputs.append(str(fo4_data_dir))
    if base_catalog_path:
        extra_inputs.append(str(base_catalog_path))
    if extra_manifest_path:
        extra_inputs.append(str(extra_manifest_path))

    refuse_unsafe_output_path(out_dir, extra_inputs)
    vmad_patch.require_separate_output(str(out_dir), str(core_dir), str(dlc_dir))
    if dlc_doors_out is not None:
        refuse_unsafe_output_path(dlc_doors_out, [*extra_inputs, str(out_dir)])
        vmad_patch.require_separate_output(str(dlc_doors_out), str(core_dir), str(dlc_dir), str(out_dir))

    core_esm_path = core_dir / "FO4TerrainCore.esm"
    if not core_esm_path.is_file():
        raise FileNotFoundError(f"Missing FO4TerrainCore.esm in {core_dir}")
    core_sha_before = sha256_file(core_esm_path)

    dlc_formids_path = dlc_dir / "formids.json"
    if not dlc_formids_path.is_file():
        raise FileNotFoundError(f"Missing formids.json in {dlc_dir}")
    actual_dlc_formids_sha = sha256_file(dlc_formids_path)
    if expected_dlc_formids_sha256 and actual_dlc_formids_sha.lower() != expected_dlc_formids_sha256.lower():
        raise ValueError(
            f"Refusing FO4DLC stage {dlc_dir}: formids.json sha256 {actual_dlc_formids_sha} != pinned "
            f"{expected_dlc_formids_sha256}"
        )

    dlc_esm_name = vmad_patch.plugin_in(str(dlc_dir))
    if dlc_esm_name != "FO4DLC.esm":
        raise ValueError(f"Expected FO4DLC.esm in {dlc_dir}, found {dlc_esm_name!r}")
    dlc_esm_path = dlc_dir / dlc_esm_name
    dlc_port_next = vmad_patch.next_local_id(str(dlc_esm_path))

    edits_doc = _load_json(edits_path)
    winning_edits: list[dict[str, Any]] = edits_doc.get("winning_dlc_edits") or []
    core_obj = _load_json(core_dir / "objects.json")
    core_fids = _load_json(core_dir / "formids.json")
    core_overlays_params = _load_json(core_dir / "overlays_params.json")
    merge_off = vmad_patch.merge_offset(str(core_dir))

    dlc_fids = _load_json(dlc_formids_path)
    dlc_manifest = _find_dlc_manifest(dlc_dir)
    extra_manifest = _load_json(extra_manifest_path) if extra_manifest_path else {"items": []}

    # Gather base/door catalog either from embedded/explicit catalog or FO4 ESMs
    base_meta: dict[str, dict[str, Any]] = {}
    door_meta: dict[str, dict[str, Any]] = {}
    for embedded in (edits_doc.get("base_catalog"), _load_json(base_catalog_path) if base_catalog_path else None):
        if isinstance(embedded, dict):
            if "bases" in embedded or "doors" in embedded:
                base_meta.update(embedded.get("bases") or {})
                door_meta.update(embedded.get("doors") or {})
            else:
                base_meta.update(embedded)

    needed_bases: set[str] = set()
    needed_doors: set[str] = set()
    for entry in winning_edits:
        wr = entry.get("winning_record") or {}
        br = entry.get("base_record") or {}
        for bfk in (wr.get("base"), br.get("base")):
            if bfk and bfk not in base_meta:
                needed_bases.add(bfk)
        if wr.get("is_load_door"):
            if entry["form_key"] not in door_meta:
                needed_doors.add(entry["form_key"])
            if wr.get("xtel_door") and wr["xtel_door"] not in door_meta:
                needed_doors.add(wr["xtel_door"])

    if needed_bases or needed_doors:
        if fo4_data_dir is None:
            raise ValueError(
                f"{len(needed_bases)} base(s) and {len(needed_doors)} door ref(s) missing from catalog; pass --fo4-data"
            )
        scanned_bases, scanned_doors = read_fo4_metadata(fo4_data_dir, needed_bases, needed_doors)
        base_meta.update(scanned_bases)
        door_meta.update(scanned_doors)

    # Index core bases (load index 0x01 in FO4TerrainCore_DLC.esm)
    core_plugin = vmad_patch.Plugin.read(str(core_esm_path))
    core_world = _index_core_world(core_plugin)

    core_base_by_src: dict[str, dict[str, Any]] = {}
    for b in core_obj.get("bases") or []:
        sk = b.get("source", "").replace("/", "\\").lower()
        edid = b["edid"]
        lid = int(core_fids["bases"][edid], 16)
        core_base_by_src[sk] = {"edid": edid, "local_id": lid, "fid": 0x01000000 | lid, "item": b}

    # Index core ACTI load-door bases by converted model stem so WB5b reuses core door ACTIs when available
    core_door_acti_by_src: dict[str, dict[str, Any]] = {}
    for d in core_obj.get("doors") or []:
        d_ids = (core_fids.get("doors") or {}).get(d["src"])
        if d_ids and "base" in d_ids:
            # Match core_obj["bases"] having the same fo4core model path
            d_mod = d.get("model", "").replace("/", "\\").lower()
            for sk, cb in core_base_by_src.items():
                if cb["item"].get("model", "").replace("/", "\\").lower() == d_mod:
                    lid = int(d_ids["base"], 16)
                    core_door_acti_by_src.setdefault(
                        sk,
                        {"edid": d["edid"], "local_id": lid, "fid": 0x01000000 | lid, "model": d["model"]},
                    )

    core_promoted_own_by_fo4base: dict[str, dict[str, Any]] = {}
    for sec in ("containers", "items", "activators", "terminals", "workshops", "flora"):
        sec_fids = core_fids.get(sec) or {}
        for item in core_obj.get(sec) or []:
            bfk = item.get("base")
            sref = item.get("src")
            if bfk and isinstance(sec_fids, dict) and sref in sec_fids:
                v = sec_fids[sref]
                if isinstance(v, dict) and "base" in v and ":" not in str(v["base"]):
                    lid = int(v["base"], 16)
                    core_promoted_own_by_fo4base.setdefault(
                        bfk,
                        {"section": sec, "local_id": lid, "fid": 0x01000000 | lid},
                    )

    # Index FO4DLC.esm bases & interior REFRs/CELLs through FO4DLC's formids.json (load index 0x02)
    dlc_fids_by_edid: dict[str, tuple[str, int]] = {}
    dlc_cells: dict[str, int] = {}
    dlc_interior_refs: dict[str, tuple[str, int]] = {}
    for key, val in dlc_fids.items():
        parts = key.split(":")
        if parts[0] == "CELL" and len(parts) == 2:
            dlc_cells[parts[1]] = int(val)
        elif parts[0] == "REFR" and len(parts) == 4:
            dlc_interior_refs[f"{parts[2]}:{parts[3]}"] = (parts[1], int(val))
        elif len(parts) == 2 and parts[0] not in ("NAVM", "WRLD", "LAND", "MARK"):
            dlc_fids_by_edid[parts[1]] = (parts[0], int(val))

    dlc_base_by_src: dict[str, dict[str, Any]] = {}
    for it in dlc_manifest.get("items") or []:
        sk = it.get("source", "").replace("/", "\\").lower()
        edid = it.get("editor_id", "")
        if edid in dlc_fids_by_edid:
            sig, lid = dlc_fids_by_edid[edid]
            dlc_base_by_src[sk] = {
                "sig": sig,
                "edid": edid,
                "local_id": lid,
                "fid": 0x02000000 | lid,
                "item": it,
            }

    extra_by_src: dict[str, dict[str, Any]] = {
        it["source"].replace("/", "\\").lower(): it for it in (extra_manifest.get("items") or []) if "source" in it
    }

    own_index = len(EXPECTED_MASTERS)  # 0x03
    next_own_local = 0x000800

    def alloc_own() -> int:
        nonlocal next_own_local
        lid = next_own_local
        next_own_local += 1
        return lid

    # Storage for written records
    authored_stat_records: list[vmad_patch.Record] = []
    override_authored_bases_by_src: dict[str, dict[str, Any]] = {}
    persistent_records: list[vmad_patch.Record] = []
    temp_records_by_cell_fid: dict[int, list[vmad_patch.Record]] = {}

    not_in_core: list[dict[str, Any]] = []
    missing_bases: list[dict[str, Any]] = []
    doors_skipped: list[dict[str, Any]] = []
    resolved_core_counts = Counter()
    added_base_source_counts = Counter()

    # Pre-identify WB5b two-way Commonwealth <-> FO4DLC.esm load doors in deterministic form_key order
    wb5b_candidates: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any], str, int]] = []
    for entry in sorted(winning_edits, key=lambda e: e["form_key"]):
        if entry.get("kind") != "added":
            continue
        wr = entry.get("winning_record") or {}
        if not wr.get("is_load_door"):
            continue
        src_fk = entry["form_key"]
        xtel_fk = wr.get("xtel_door")
        if not xtel_fk or xtel_fk not in dlc_interior_refs:
            # Check if xtel_fk was an unplaced marker door or non-FO4DLC cell
            binfo = base_meta.get(wr.get("base") or "", {})
            doors_skipped.append(
                {
                    "src": src_fk,
                    "base": wr.get("base"),
                    "base_edid": binfo.get("edid", ""),
                    "xtel_door": xtel_fk,
                    "reason": "interior_door_not_placed_in_fo4dlc",
                }
            )
            continue
        ext_dmeta = door_meta.get(src_fk)
        int_dmeta = door_meta.get(xtel_fk)
        if not ext_dmeta or not ext_dmeta.get("xtel") or not int_dmeta or not int_dmeta.get("xtel"):
            doors_skipped.append(
                {
                    "src": src_fk,
                    "base": wr.get("base"),
                    "xtel_door": xtel_fk,
                    "reason": "missing_xtel_data",
                }
            )
            continue
        back_door = (int_dmeta["xtel"] or {}).get("door")
        if back_door != src_fk:
            doors_skipped.append(
                {
                    "src": src_fk,
                    "base": wr.get("base"),
                    "xtel_door": xtel_fk,
                    "reason": f"non_reciprocal_xtel:{back_door}",
                }
            )
            continue
        cell_edid, port_ref_lid = dlc_interior_refs[xtel_fk]
        wb5b_candidates.append((entry, ext_dmeta, int_dmeta, cell_edid, port_ref_lid))

    wb5b_by_src: dict[str, int] = {cand[0]["form_key"]: idx for idx, cand in enumerate(wb5b_candidates)}
    door_objects_entries: list[dict[str, Any]] = []
    door_formids_entries: dict[str, dict[str, str]] = {}

    # 1. Process non-added (changed / deleted) core references
    for entry in winning_edits:
        kind = entry.get("kind")
        if kind == "added":
            continue
        src_fk = entry["form_key"]
        core_info = entry.get("core") or {}
        wr = entry.get("winning_record") or entry.get("base_record") or {}
        bfk = wr.get("base") or ""
        binfo = base_meta.get(bfk, {})
        if core_info.get("status") != "resolved" or not core_info.get("core_ref_id"):
            not_in_core.append(
                {
                    "form_key": src_fk,
                    "winning_plugin": entry.get("winning_plugin"),
                    "kind": kind,
                    "reasons": list(entry.get("reasons") or ()),
                    "base": bfk,
                    "base_edid": binfo.get("edid", ""),
                }
            )
            continue

        core_lid = int(core_info["core_ref_id"], 16)
        if core_lid not in core_world["refs_by_local"]:
            not_in_core.append(
                {
                    "form_key": src_fk,
                    "winning_plugin": entry.get("winning_plugin"),
                    "kind": kind,
                    "reasons": list(entry.get("reasons") or ()),
                    "base": bfk,
                    "base_edid": binfo.get("edid", ""),
                    "detail": f"core_ref_id {core_lid:06X} not found in FO4TerrainCore.esm",
                }
            )
            continue

        orig_rec, orig_cell_fid, orig_gtype = core_world["refs_by_local"][core_lid]

        if kind == "identical_override":
            resolved_core_counts["identical_override_noop"] += 1
            continue

        if kind == "deleted":
            # WB5 mandate: set InitiallyDisabled (0x0800) on that exact core ID, NEVER Deleted (0x0020)!
            new_flags = (orig_rec.flags | RECORD_FLAG_INITIALLY_DISABLED) & ~RECORD_FLAG_DELETED
            over_rec = _update_core_refr(orig_rec, new_flags=new_flags)
            if orig_gtype == GROUP_CELL_PERSISTENT:
                persistent_records.append(over_rec)
            else:
                temp_records_by_cell_fid.setdefault(orig_cell_fid, []).append(over_rec)
            resolved_core_counts["deleted_set_initially_disabled"] += 1
            continue

        # Moved / modified / disabled / enabled override of existing core REFR
        reasons = set(entry.get("reasons") or ())
        new_flags = orig_rec.flags & ~RECORD_FLAG_DELETED
        if wr.get("disabled"):
            new_flags |= RECORD_FLAG_INITIALLY_DISABLED
        else:
            new_flags &= ~RECORD_FLAG_INITIALLY_DISABLED

        new_base_fid: int | None = None
        if "base_changed" in reasons and bfk:
            modl = binfo.get("model") or ""
            sk = exterior.source_key(modl) if modl else ""
            if bfk in core_promoted_own_by_fo4base:
                new_base_fid = core_promoted_own_by_fo4base[bfk]["fid"]
            elif sk and sk in core_base_by_src:
                new_base_fid = core_base_by_src[sk]["fid"]
            elif sk and sk in dlc_base_by_src:
                new_base_fid = dlc_base_by_src[sk]["fid"]

        new_pos_m = exterior.metres(wr["pos"]) if wr.get("pos") is not None else None
        new_rot = tuple(float(v) for v in wr["rot"]) if wr.get("rot") is not None else None
        new_scale = float(wr.get("scale") or 1.0)

        target_cell_fid = orig_cell_fid
        if orig_gtype != GROUP_CELL_PERSISTENT and new_pos_m is not None:
            cxy = tg.sf_cell_of(new_pos_m[0], new_pos_m[1])
            if cxy in core_world["cells_by_xy"]:
                target_cell_fid = core_world["cells_by_xy"][cxy]["rec"].fid

        over_rec = _update_core_refr(
            orig_rec,
            new_flags=new_flags,
            new_base_fid=new_base_fid,
            new_pos_m=new_pos_m,
            new_rot_rad=new_rot,
            new_scale=new_scale,
        )
        if orig_gtype == GROUP_CELL_PERSISTENT:
            persistent_records.append(over_rec)
        else:
            temp_records_by_cell_fid.setdefault(target_cell_fid, []).append(over_rec)
        resolved_core_counts[f"overridden_{kind}"] += 1

    # 2. Process added DLC references (including WB5b exterior load doors)
    for entry in sorted((e for e in winning_edits if e.get("kind") == "added"), key=lambda e: e["form_key"]):
        src_fk = entry["form_key"]
        wr = entry.get("winning_record") or {}
        bfk = wr.get("base") or ""
        binfo = base_meta.get(bfk)
        if not binfo:
            missing_bases.append(
                {
                    "form_key": src_fk,
                    "winning_plugin": entry.get("winning_plugin"),
                    "base": bfk,
                    "base_edid": "",
                    "sig": "?",
                    "model": "",
                    "reason": "base_not_found",
                }
            )
            continue

        sig = binfo.get("sig", "?")
        edid = binfo.get("edid", "")
        modl = binfo.get("model", "")

        # Check if this added ref is one of the WB5b two-way load doors into FO4DLC.esm!
        if src_fk in wb5b_by_src:
            door_k = wb5b_by_src[src_fk]
            _, ext_dmeta, int_dmeta, dest_cell_edid, dest_door_lid = wb5b_candidates[door_k]
            sk = exterior.source_key(modl) if modl else ""
            # Exterior load door requires an activatable base (ACTI in core, or DOOR in FO4DLC.esm)
            if sk in core_door_acti_by_src:
                door_base_fid = core_door_acti_by_src[sk]["fid"]
                door_base_hex = f"{door_base_fid:08X}"
                door_edid = core_door_acti_by_src[sk]["edid"]
                door_model = core_door_acti_by_src[sk]["model"]
                added_base_source_counts["core_door_acti"] += 1
            elif sk in dlc_base_by_src and dlc_base_by_src[sk]["sig"] in ("DOOR", "ACTI"):
                door_base_fid = dlc_base_by_src[sk]["fid"]
                door_base_hex = f"{door_base_fid:08X}"
                door_edid = dlc_base_by_src[sk]["edid"]
                door_model = dlc_base_by_src[sk]["item"]["model"]
                added_base_source_counts["fo4dlc_door"] += 1
            else:
                raise ValueError(f"WB5b door {src_fk} ({edid}, {modl!r}) has no activatable DOOR/ACTI base in core or FO4DLC.esm")

            pos_m = list(exterior.metres(wr["pos"]))
            rot_rad = [float(v) for v in wr["rot"]]
            scale = float(wr.get("scale") or 1.0)
            cxy = tg.sf_cell_of(pos_m[0], pos_m[1])
            if cxy not in core_world["cells_by_xy"]:
                raise ValueError(f"WB5b door {src_fk} at cell {cxy} lies outside FO4TerrainCore.esm exterior grid")

            dest_marker_lid = dlc_port_next + door_k
            dest_cell_lid = dlc_cells[dest_cell_edid]
            int_arr_pos = [round(v, 6) for v in exterior.metres(ext_dmeta["xtel"]["pos"])]
            int_arr_rot = [float(v) for v in ext_dmeta["xtel"]["rot"]]
            ext_arr_pos = [round(v, 6) for v in exterior.metres(int_dmeta["xtel"]["pos"])]
            ext_arr_rot = [float(v) for v in int_dmeta["xtel"]["rot"]]
            ext_arr_cell = list(tg.sf_cell_of(ext_arr_pos[0], ext_arr_pos[1]))

            door_ref_lid = alloc_own()
            ext_arrival_lid = alloc_own()

            # Exterior door VMAD -> FO4DLC.esm interior marker (interior has no overlay merge, so position = int_arr_pos)
            ext_vmad = vmad_patch.load_door_vmad("FO4DLC.esm", dest_marker_lid, int_arr_pos)
            door_refr = _refr_record(
                (own_index << 24) | door_ref_lid,
                door_base_fid,
                [round(v, 5) for v in pos_m],
                rot_rad,
                scale=scale,
                flags=RECORD_FLAG_INITIALLY_DISABLED if wr.get("disabled") else 0,
                vmad_bytes=ext_vmad,
            )
            temp_records_by_cell_fid.setdefault(core_world["cells_by_xy"][cxy]["rec"].fid, []).append(door_refr)

            # Persistent exterior arrival XMarker in FO4Core_Commonwealth's persistent cell (0x01001805)
            arrival_marker = vmad_patch.xmarker_ref(
                (own_index << 24) | ext_arrival_lid,
                ext_arr_pos,
                ext_arr_rot,
                FORM_VERSION_SF,
            )
            persistent_records.append(arrival_marker)

            door_objects_entries.append(
                {
                    "src": src_fk,
                    "edid": door_edid,
                    "model": door_model,
                    "name": "Door",
                    "destination": {
                        "plugin": "FO4DLC.esm",
                        "id": dest_marker_lid,
                        "ref": f"{dest_door_lid:06X}",
                        "cell": f"{dest_cell_lid:06X}",
                        "cell_edid": dest_cell_edid,
                        "door": ext_dmeta["xtel"]["door"],
                        "arrival": {"pos": int_arr_pos, "rot": int_arr_rot},
                    },
                    "arrival": {"pos": ext_arr_pos, "rot": ext_arr_rot, "cell": ext_arr_cell},
                    "cell": list(cxy),
                    "pos": [round(v, 5) for v in pos_m],
                    "rot": rot_rad,
                    "scale": scale,
                }
            )
            door_formids_entries[src_fk] = {
                "base": door_base_hex,
                "ref": f"{door_ref_lid:06X}",
                "arrival": f"{ext_arrival_lid:06X}",
            }
            continue

        # Non-WB5b added reference: classify model first
        export_type = SIG_TO_EXPORT_TYPE.get(sig, sig)
        action, skip_code, skip_detail = exterior.classify({"type": export_type, "model": modl})
        if action != "convert":
            missing_bases.append(
                {
                    "form_key": src_fk,
                    "winning_plugin": entry.get("winning_plugin"),
                    "base": bfk,
                    "base_edid": edid,
                    "sig": sig,
                    "model": modl,
                    "reason": skip_code or "not_convertible",
                    "detail": skip_detail,
                }
            )
            continue

        sk = exterior.source_key(modl)
        door_hinge_off: list[float] | None = None
        resolved_base_fid: int | None = None

        # Priority 1: FO4TerrainCore.esm
        # Note: for unwired load doors (`wr["is_load_door"]`), keep plain non-activatable visual STAT in core so there
        # is never a one-way or broken activation prompt (R10).
        if not wr.get("is_load_door") and bfk in core_promoted_own_by_fo4base:
            resolved_base_fid = core_promoted_own_by_fo4base[bfk]["fid"]
            added_base_source_counts["core_promoted"] += 1
        elif sk in core_base_by_src:
            cb = core_base_by_src[sk]
            resolved_base_fid = cb["fid"]
            if "door" in cb["item"]:
                door_hinge_off = cb["item"]["door"].get("origin_offset")
            added_base_source_counts["core"] += 1
        # Priority 2: FO4DLC.esm through formids.json (never author a second base for a model FO4DLC.esm holds!)
        elif sk in dlc_base_by_src:
            db = dlc_base_by_src[sk]
            if wr.get("is_load_door") and db["sig"] in ("DOOR", "ACTI"):
                # Unwired load door whose only base is an interactive DOOR: skip rather than create a dead prompt (R10)
                missing_bases.append(
                    {
                        "form_key": src_fk,
                        "winning_plugin": entry.get("winning_plugin"),
                        "base": bfk,
                        "base_edid": edid,
                        "sig": sig,
                        "model": modl,
                        "reason": "unwired_load_door_destination_absent",
                    }
                )
                continue
            resolved_base_fid = db["fid"]
            if "door" in db["item"]:
                door_hinge_off = db["item"]["door"].get("origin_offset")
            added_base_source_counts["fo4dlc"] += 1
        # Priority 3: Model neither holds -> write own STAT base in FO4TerrainCore_DLC.esm under fo4dlc prefix
        elif sk in extra_by_src:
            if sk not in override_authored_bases_by_src:
                item = extra_by_src[sk]
                new_edid = exterior.plugin_editor_id(item["editor_id"], "FO4DLC_")
                raw_mod = item["model"].replace("/", "\\").lstrip("\\")
                if not raw_mod.lower().startswith("fo4dlc\\"):
                    # Enforce fo4dlc prefix on authored model path
                    parts = raw_mod.split("\\", 1)
                    raw_mod = "fo4dlc\\" + (parts[1] if len(parts) == 2 else parts[0])
                stat_lid = alloc_own()
                stat_fid = (own_index << 24) | stat_lid
                authored_stat_records.append(_stat_record(stat_fid, new_edid, raw_mod))
                override_authored_bases_by_src[sk] = {
                    "edid": new_edid,
                    "local_id": f"{stat_lid:06X}",
                    "fid": stat_fid,
                    "model": raw_mod,
                    "source": item["source"],
                    "fo4_base": bfk,
                    "fo4_edid": edid,
                }
            resolved_base_fid = override_authored_bases_by_src[sk]["fid"]
            added_base_source_counts["override_authored"] += 1
        else:
            missing_bases.append(
                {
                    "form_key": src_fk,
                    "winning_plugin": entry.get("winning_plugin"),
                    "base": bfk,
                    "base_edid": edid,
                    "sig": sig,
                    "model": modl,
                    "reason": "not_converted",
                }
            )
            continue

        pos_m_t = exterior.metres(wr["pos"])
        scale = float(wr.get("scale") or 1.0)
        rot_rad = [float(v) for v in wr["rot"]]
        if door_hinge_off is not None:
            m = exterior.ref_matrix(rot_rad)
            pos_m_t = tuple(pos_m_t[a] + scale * sum(m[3 * a + k] * door_hinge_off[k] for k in range(3)) for a in range(3))

        cxy = tg.sf_cell_of(pos_m_t[0], pos_m_t[1])
        if cxy not in core_world["cells_by_xy"]:
            missing_bases.append(
                {
                    "form_key": src_fk,
                    "winning_plugin": entry.get("winning_plugin"),
                    "base": bfk,
                    "base_edid": edid,
                    "sig": sig,
                    "model": modl,
                    "reason": "outside_core_grid",
                }
            )
            continue

        ref_lid = alloc_own()
        ref_flags = RECORD_FLAG_INITIALLY_DISABLED if wr.get("disabled") else 0
        refr = _refr_record(
            (own_index << 24) | ref_lid,
            resolved_base_fid,
            [round(v, 5) for v in pos_m_t],
            rot_rad,
            scale=scale,
            flags=ref_flags,
        )
        temp_records_by_cell_fid.setdefault(core_world["cells_by_xy"][cxy]["rec"].fid, []).append(refr)

    # Assemble WRLD override hierarchy matching Starfield's exact canonical structure
    world_children_items: list[Any] = []
    if persistent_records:
        pers_cell = core_world["pers_cell_rec"]
        pers_label = struct.pack("<I", pers_cell.fid)
        pers_grp = vmad_patch.Group(pers_label, GROUP_CELL_PERSISTENT, b"\x00" * 8, persistent_records)
        cell_children_grp = vmad_patch.Group(pers_label, GROUP_CELL_CHILDREN, b"\x00" * 8, [pers_grp])
        world_children_items.extend([pers_cell, cell_children_grp])

    for bkey in core_world["block_order"]:
        subblock_groups: list[vmad_patch.Group] = []
        block_tail = b"\x00" * 8
        for sbkey in core_world["subblock_order"][bkey]:
            sub_items: list[Any] = []
            sub_tail = b"\x00" * 8
            for cell_fid in core_world["cell_order_in_subblock"][(bkey, sbkey)]:
                recs_in_cell = temp_records_by_cell_fid.get(cell_fid)
                if not recs_in_cell:
                    continue
                cinfo = core_world["cells_by_fid"][cell_fid]
                block_tail = cinfo["tail_block"]
                sub_tail = cinfo["tail_subblock"]
                clabel = struct.pack("<I", cell_fid)
                temp_grp = vmad_patch.Group(clabel, GROUP_CELL_TEMPORARY, b"\x00" * 8, recs_in_cell)
                cchild_grp = vmad_patch.Group(clabel, GROUP_CELL_CHILDREN, b"\x00" * 8, [temp_grp])
                sub_items.extend([cinfo["rec"], cchild_grp])
            if sub_items:
                subblock_groups.append(
                    vmad_patch.Group(struct.pack("<hh", sbkey[0], sbkey[1]), GROUP_EXT_CELL_SUBBLOCK, sub_tail, sub_items)
                )
        if subblock_groups:
            world_children_items.append(
                vmad_patch.Group(struct.pack("<hh", bkey[0], bkey[1]), GROUP_EXT_CELL_BLOCK, block_tail, subblock_groups)
            )

    top_groups_by_sig: dict[bytes, vmad_patch.Group] = {}
    if authored_stat_records:
        top_groups_by_sig[b"STAT"] = vmad_patch.Group(b"STAT", GROUP_TOP, b"\x00" * 8, authored_stat_records)

    wrld_rec = core_world["wrld_rec"]
    wrld_children_grp = vmad_patch.Group(
        struct.pack("<I", wrld_rec.fid),
        GROUP_WORLD_CHILDREN,
        core_world["wrld_tail"],
        world_children_items,
    )
    top_groups_by_sig[b"WRLD"] = vmad_patch.Group(b"WRLD", GROUP_TOP, b"\x00" * 8, [wrld_rec, wrld_children_grp])

    ordered_top_groups = [
        top_groups_by_sig[sig.encode("ascii")]
        for sig in planet_esm.GROUP_ORDER
        if sig.encode("ascii") in top_groups_by_sig
    ]
    total_items = _count_tree_items(ordered_top_groups)
    tes4_rec = _build_tes4_record(EXPECTED_MASTERS, total_items, next_own_local)
    plugin_bytes = tes4_rec.serialize() + b"".join(g.serialize() for g in ordered_top_groups)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_plugin_path = out_dir / OVERRIDE_PLUGIN_NAME
    vmad_patch.write_output(str(out_plugin_path), plugin_bytes)

    # Write core-build layout files read by `scripts/terrain/vmad_patch.py`
    world_edid = core_obj.get("world") or "FO4Core_Commonwealth"
    vmad_patch.write_output(
        str(out_dir / "overlays_params.json"),
        json.dumps(core_overlays_params, indent=2).encode("utf-8"),
    )
    objects_doc = {
        "world": world_edid,
        "edid_prefix": "FO4DLC_",
        "bases": list(override_authored_bases_by_src.values()),
        "doors": door_objects_entries,
        "doors_skipped": doors_skipped,
    }
    vmad_patch.write_output(str(out_dir / "objects.json"), json.dumps(objects_doc, indent=2).encode("utf-8"))

    formids_doc = {
        "plugin": OVERRIDE_PLUGIN_NAME,
        "world": world_edid,
        "bases": {v["edid"]: v["local_id"] for v in override_authored_bases_by_src.values()},
        "doors": door_formids_entries,
    }
    vmad_patch.write_output(str(out_dir / "formids.json"), json.dumps(formids_doc, indent=2).encode("utf-8"))

    core_sha_after = sha256_file(core_esm_path)
    if core_sha_after != core_sha_before:
        raise AssertionError(f"FO4TerrainCore.esm hash changed during build ({core_sha_before} -> {core_sha_after})")

    missing_by_reason = Counter(m["reason"] for m in missing_bases)
    distinct_missing_bases = sorted(
        {
            (m["base"], m["sig"], m["base_edid"], m["model"], m["reason"])
            for m in missing_bases
        }
    )

    report = {
        "step": "WB5_WB5b",
        "label": "TEST-STATION",
        "plugin": OVERRIDE_PLUGIN_NAME,
        "plugin_sha256": sha256_file(out_plugin_path),
        "masters": list(EXPECTED_MASTERS),
        "core_sha256_before": core_sha_before,
        "core_sha256_after": core_sha_after,
        "core_unchanged": core_sha_before == core_sha_after,
        "pinned_dlc_formids_sha256": actual_dlc_formids_sha,
        "merge_offset": list(merge_off),
        "counts": {
            "winning_dlc_edits_total": len(winning_edits),
            "changed_or_deleted_total": sum(1 for e in winning_edits if e.get("kind") != "added"),
            "changed_or_deleted_resolved_in_core": sum(resolved_core_counts.values()),
            "deleted_set_initially_disabled": resolved_core_counts["deleted_set_initially_disabled"],
            "overridden_moved": resolved_core_counts["overridden_moved"],
            "overridden_modified": resolved_core_counts["overridden_modified"],
            "identical_override_noop": resolved_core_counts["identical_override_noop"],
            "not_in_core": len(not_in_core),
            "added_total": sum(1 for e in winning_edits if e.get("kind") == "added"),
            "added_placed_total": sum(added_base_source_counts.values()),
            "added_base_from_core": added_base_source_counts["core"]
            + added_base_source_counts["core_promoted"]
            + added_base_source_counts["core_door_acti"],
            "added_base_from_fo4dlc": added_base_source_counts["fo4dlc"] + added_base_source_counts["fo4dlc_door"],
            "added_base_authored_in_override": added_base_source_counts["override_authored"],
            "override_authored_distinct_bases": len(override_authored_bases_by_src),
            "added_missing_refs": len(missing_bases),
            "added_missing_distinct_bases": len(distinct_missing_bases),
            "wb5b_doors_wired": len(door_objects_entries),
            "wb5b_doors_skipped": len(doors_skipped),
        },
        "missing_by_reason": dict(sorted(missing_by_reason.items())),
        "not_in_core": not_in_core,
        "override_authored_bases": list(override_authored_bases_by_src.values()),
        "missing_distinct_bases": [
            {"base": b, "sig": s, "edid": ed, "model": md, "reason": r}
            for b, s, ed, md, r in distinct_missing_bases
        ],
        "missing_bases": missing_bases,
        "wb5b_doors": door_objects_entries,
        "wb5b_doors_skipped": doors_skipped,
    }

    if dlc_doors_out is not None and door_objects_entries:
        rc = vmad_patch.main(["port", "--port", str(dlc_dir), "--core", str(out_dir), "--out", str(dlc_doors_out)])
        if rc != 0:
            raise RuntimeError(f"vmad_patch.py port failed with exit code {rc}")
        rc_chk = vmad_patch.main(["check", "--port", str(dlc_dir), "--out", str(dlc_doors_out), "--core", str(out_dir)])
        if rc_chk != 0:
            raise RuntimeError(f"vmad_patch.py check failed with exit code {rc_chk}")
        report["patched_dlc_plugin_sha256"] = sha256_file(dlc_doors_out / "FO4DLC.esm")

    vmad_patch.write_output(str(out_dir / "wb5_report.json"), json.dumps(report, indent=2).encode("utf-8"))
    return report


def check_override(
    *,
    out_dir: Path,
    core_dir: Path,
    dlc_dir: Path,
    dlc_doors_out: Path | None = None,
    expected_dlc_formids_sha256: str = PINNED_FO4DLC_FORMIDS_SHA256,
) -> dict[str, Any]:
    report = _load_json(out_dir / "wb5_report.json")
    plugin_path = out_dir / OVERRIDE_PLUGIN_NAME
    plugin = vmad_patch.Plugin.read(str(plugin_path))
    core_esm_path = core_dir / "FO4TerrainCore.esm"
    core_plugin = vmad_patch.Plugin.read(str(core_esm_path))
    dlc_formids_path = dlc_dir / "formids.json"
    dlc_manifest = _find_dlc_manifest(dlc_dir)

    checks: list[tuple[str, bool]] = []

    def need(cond: bool, desc: str) -> None:
        checks.append((desc, bool(cond)))

    # 1. Masters & canonical top-group order
    masters = plugin.masters()
    need(tuple(masters) == EXPECTED_MASTERS, f"masters == {list(EXPECTED_MASTERS)} (got {masters})")

    top_sigs = [g.label.decode("latin-1") for g in plugin.items if isinstance(g, vmad_patch.Group) and g.gtype == GROUP_TOP]
    expected_order = [s for s in planet_esm.GROUP_ORDER if s in top_sigs]
    need(bool(top_sigs) and top_sigs == expected_order, f"canonical top-group order {top_sigs}")

    # 2. Core SHA-256 unchanged & FO4DLC formids.json SHA-256 pinned
    core_sha = sha256_file(core_esm_path)
    need(
        core_sha == report["core_sha256_before"] == report["core_sha256_after"],
        f"FO4TerrainCore.esm sha256 unchanged ({core_sha[:16]}...)",
    )
    dlc_fids_sha = sha256_file(dlc_formids_path)
    need(
        not expected_dlc_formids_sha256 or dlc_fids_sha.lower() == expected_dlc_formids_sha256.lower(),
        f"FO4DLC formids.json sha256 matches pin ({dlc_fids_sha[:16]}...)",
    )

    # 3. Zero Deleted records (0x0020); every deleted core override uses InitiallyDisabled (0x0800)
    deleted_flagged = [f"0x{r.fid:08X}" for r, _ in plugin.walk() if r.flags & RECORD_FLAG_DELETED]
    need(len(deleted_flagged) == 0, f"zero records carry Deleted flag 0x0020 (found {len(deleted_flagged)})")

    over_recs = plugin.records()
    core_recs = core_plugin.records()
    core_refr_overrides = {
        fid: val for fid, val in over_recs.items() if (fid >> 24) == 0x01 and val[0] == b"REFR"
    }
    expected_core_overrides = (
        report["counts"]["deleted_set_initially_disabled"]
        + report["counts"]["overridden_moved"]
        + report["counts"]["overridden_modified"]
    )
    need(
        len(core_refr_overrides) == expected_core_overrides,
        f"core REFR overrides written == {expected_core_overrides} (got {len(core_refr_overrides)})",
    )
    need(
        all(fid in core_recs for fid in core_refr_overrides),
        "every 0x01XXXXXX REFR override targets an existing FO4TerrainCore.esm REFR FormID",
    )
    disabled_core_overrides = sum(
        1 for _fid, val in core_refr_overrides.items() if val[1] & RECORD_FLAG_INITIALLY_DISABLED
    )
    need(
        disabled_core_overrides >= report["counts"]["deleted_set_initially_disabled"],
        f"InitiallyDisabled core overrides ({disabled_core_overrides}) >= DLC core deletions ({report['counts']['deleted_set_initially_disabled']})",
    )

    # 4. Complete accounting of changed/deleted and added references + zero duplicate base for FO4DLC models
    c = report["counts"]
    need(
        c["changed_or_deleted_resolved_in_core"] + c["not_in_core"] == c["changed_or_deleted_total"],
        f"every changed/deleted ref resolved in core ({c['changed_or_deleted_resolved_in_core']}) or listed in not_in_core ({c['not_in_core']})",
    )
    need(
        c["added_placed_total"] + c["added_missing_refs"] == c["added_total"],
        f"every added ref placed ({c['added_placed_total']}) or listed in missing_bases ({c['added_missing_refs']})",
    )

    dlc_sources = {
        it.get("source", "").replace("/", "\\").lower()
        for it in (dlc_manifest.get("items") or [])
        if it.get("source")
    }
    own_bases = [r for r, _ in plugin.walk() if (r.fid >> 24) == 0x03 and r.sig != b"REFR"]
    need(
        len(own_bases) == c["override_authored_distinct_bases"],
        f"own non-REFR base records ({len(own_bases)}) == override_authored_distinct_bases ({c['override_authored_distinct_bases']})",
    )
    dup_dlc_models = [
        b["edid"]
        for b in report.get("override_authored_bases") or []
        if b.get("source", "").replace("/", "\\").lower() in dlc_sources
    ]
    need(len(dup_dlc_models) == 0, f"zero override bases duplicate a model FO4DLC.esm holds (dups={dup_dlc_models})")
    bad_prefix = [
        b["edid"]
        for b in report.get("override_authored_bases") or []
        if not b["edid"].lower().startswith("fo4dlc_") or not b["model"].lower().startswith("fo4dlc\\")
    ]
    need(len(bad_prefix) == 0, f"every override-authored base uses fo4dlc prefix (bad={bad_prefix})")

    # 5. WB5b two-way door verification against patched FO4DLC.esm stage (R10)
    core_plugin_name, doors = vmad_patch.core_doors(str(out_dir))
    need(core_plugin_name == OVERRIDE_PLUGIN_NAME, f"core_doors plugin == {OVERRIDE_PLUGIN_NAME}")

    if dlc_doors_out is not None:
        before_dlc = vmad_patch.Plugin.read(str(dlc_dir / "FO4DLC.esm"))
        after_dlc = vmad_patch.Plugin.read(str(dlc_doors_out / "FO4DLC.esm"))
        merge_off = vmad_patch.merge_offset(str(out_dir))
        port_checks = vmad_patch.check_port(before_dlc, after_dlc, doors, core_plugin_name, merge_off)
        for pdesc, pok in port_checks:
            need(pok, f"[vmad_patch] {pdesc}")

        dlc_own = len(after_dlc.masters()) << 24
        after_dlc_recs = after_dlc.records()

        for d in doors:
            src = d["src"]
            ext_ref_fid = 0x03000000 | int(d["ids"]["ref"], 16)
            ext_arr_fid = 0x03000000 | int(d["ids"]["arrival"], 16)
            int_door_fid = dlc_own | int(d["destination"]["ref"], 16)
            int_mark_fid = dlc_own | int(d["destination"]["id"])

            # Exterior door in FO4TerrainCore_DLC.esm -> persistent XMarker in patched FO4DLC.esm
            ext_rec = over_recs.get(ext_ref_fid)
            ext_vm = [v for s, v in fo4land.iter_subrecords(ext_rec[2]) if s == b"VMAD"] if ext_rec else []
            ext_target = vmad_patch.load_door_target(ext_vm[0]) if len(ext_vm) == 1 else None
            int_mark = after_dlc_recs.get(int_mark_fid)
            need(
                ext_target is not None
                and ext_target[0] == "FO4DLC.esm"
                and ext_target[1] == int(d["destination"]["id"])
                and vmad_patch.same_position(ext_target[2], d["destination"]["arrival"]["pos"])
                and int_mark is not None
                and int_mark[0] == b"REFR"
                and bool(int_mark[1] & RECORD_FLAG_PERSISTENT),
                f"{src}: exterior door 0x{ext_ref_fid:08X} -> FO4DLC.esm persistent XMarker 0x{int_mark_fid:08X}",
            )

            # Return interior door in patched FO4DLC.esm -> persistent XMarker in FO4TerrainCore_DLC.esm
            int_rec = after_dlc_recs.get(int_door_fid)
            int_vm = [v for s, v in fo4land.iter_subrecords(int_rec[2]) if s == b"VMAD"] if int_rec else []
            int_target = vmad_patch.load_door_target(int_vm[0]) if len(int_vm) == 1 else None
            ext_mark = over_recs.get(ext_arr_fid)
            want_back = vmad_patch.merged(d["arrival"]["pos"], merge_off)
            need(
                int_target is not None
                and int_target[0] == OVERRIDE_PLUGIN_NAME
                and int_target[1] == int(d["ids"]["arrival"], 16)
                and vmad_patch.same_position(int_target[2], want_back)
                and ext_mark is not None
                and ext_mark[0] == b"REFR"
                and bool(ext_mark[1] & RECORD_FLAG_PERSISTENT),
                f"{src}: return door 0x{int_door_fid:08X} -> {OVERRIDE_PLUGIN_NAME} persistent XMarker 0x{ext_arr_fid:08X}",
            )

    passed = all(ok for _, ok in checks)
    return {
        "step": "WB5_WB5b",
        "plugin": OVERRIDE_PLUGIN_NAME,
        "checks": checks,
        "counts": c,
        "pass": passed,
    }


def cmd_build(args: argparse.Namespace) -> int:
    try:
        rep = build_override(
            edits_path=Path(args.edits),
            core_dir=Path(args.core),
            dlc_dir=Path(args.dlc),
            out_dir=Path(args.out),
            fo4_data_dir=Path(args.fo4_data) if args.fo4_data else None,
            base_catalog_path=Path(args.base_catalog) if args.base_catalog else None,
            extra_manifest_path=Path(args.extra_manifest) if args.extra_manifest else None,
            expected_dlc_formids_sha256=args.expected_dlc_formids_sha256,
            dlc_doors_out=Path(args.dlc_doors_out) if args.dlc_doors_out else None,
        )
    except (OutputPathRefusedError, ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    c = rep["counts"]
    print(
        f"built {rep['plugin']} (masters={rep['masters']}, "
        f"core_resolved={c['changed_or_deleted_resolved_in_core']}, not_in_core={c['not_in_core']}, "
        f"added_placed={c['added_placed_total']}, missing_refs={c['added_missing_refs']}, "
        f"wb5b_doors={c['wb5b_doors_wired']}, core_unchanged={rep['core_unchanged']})"
    )
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    try:
        res = check_override(
            out_dir=Path(args.out),
            core_dir=Path(args.core),
            dlc_dir=Path(args.dlc),
            dlc_doors_out=Path(args.dlc_doors_out) if args.dlc_doors_out else None,
            expected_dlc_formids_sha256=args.expected_dlc_formids_sha256,
        )
    except (ValueError, FileNotFoundError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for desc, ok in res["checks"]:
        print(("  ok   " if ok else "  FAIL ") + desc)
    c = res["counts"]
    print(
        f"wb5 check: {'ok' if res['pass'] else 'FAIL'} "
        f"(core_resolved={c['changed_or_deleted_resolved_in_core']}, not_in_core={c['not_in_core']}, "
        f"added_placed={c['added_placed_total']}, missing_refs={c['added_missing_refs']}, "
        f"wb5b_doors={c['wb5b_doors_wired']})"
    )
    return 0 if res["pass"] else 1


INSTALL_RECORD_NAME = "FO4TerrainCore_DLC.install.json"
DLC_BACKUP_NAME = "FO4TerrainCore_DLC.unpatched_fo4dlc.bak"
GAME_EXE_NAME = "Starfield.exe"


def _ensure_game_closed(action: str, system: Any = None) -> None:
    from fo4sf.launcher import crashwatch

    sys_obj = system if system is not None else crashwatch.System()
    try:
        pids = sys_obj.pids(GAME_EXE_NAME)
    except ValueError as err:
        raise RuntimeError(f"{action}: cannot confirm {GAME_EXE_NAME} is closed ({err})") from err
    if pids:
        joined = ", ".join(str(p) for p in pids)
        raise RuntimeError(f"{action}: {GAME_EXE_NAME} is running (pid {joined}); close the game first")


def _plugins_txt_path() -> Path:
    local = os.environ.get("LOCALAPPDATA", "")
    if not local or not os.path.isabs(local):
        raise RuntimeError("LOCALAPPDATA must identify an absolute Starfield user profile directory")
    return Path(local) / "Starfield" / "Plugins.txt"


def _dlc_install_artifacts(dlc_doors_dir: Path) -> tuple[list[str], list[str]]:
    """Return `(all_data_files, ordered_active_plugins)` from `<fo4dlc-doors-stage>`."""
    names = sorted(os.listdir(dlc_doors_dir))
    ba2s = [n for n in names if n.lower().endswith(".ba2")]
    companions = sorted(
        (n for n in names if n.lower().endswith(".esm") and vmad_patch.TEXTURE_COMPANION.match(n)),
        key=lambda s: int("".join(ch for ch in s if ch.isdigit()) or "0"),
    )
    if "FO4DLC.esm" not in names:
        raise FileNotFoundError(f"{dlc_doors_dir}: missing FO4DLC.esm")
    for req_ba2 in ("FO4DLC - Main.ba2", "FO4DLC - Textures.ba2"):
        if req_ba2 not in ba2s:
            raise FileNotFoundError(
                f"{dlc_doors_dir}: missing required archive {req_ba2!r} (session needs FO4DLC.esm and its archives)"
            )
    data_files = ["FO4DLC.esm", *companions, *ba2s]
    active_plugins = ["FO4DLC.esm", *companions]
    return data_files, active_plugins


def _copy_or_link(src: Path, dst: Path) -> str:
    try:
        os.link(src, dst)
        return "linked"
    except OSError:
        import shutil

        shutil.copy2(src, dst)
        return "copied"


def install_override_session(
    *,
    stage_dir: Path,
    dlc_doors_dir: Path,
    starfield_dir: Path,
    system: Any = None,
) -> dict[str, Any]:
    import base64
    import shutil

    _ensure_game_closed("install", system=system)
    data_dir = starfield_dir / "Data"
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Missing Starfield Data directory: {data_dir}")

    rec_path = data_dir / INSTALL_RECORD_NAME
    if rec_path.exists():
        raise RuntimeError(f"{rec_path} already exists; run uninstall first")

    wb5_rep = _load_json(stage_dir / "wb5_report.json")
    doors_rep = _load_json(dlc_doors_dir / "doors.json")
    installed_core = data_dir / "FO4TerrainCore.esm"
    if not installed_core.is_file():
        raise FileNotFoundError(f"Missing FO4TerrainCore.esm in {data_dir}")
    actual_core_sha = sha256_file(installed_core)
    if actual_core_sha.lower() != str(wb5_rep["core_sha256_before"]).lower():
        raise ValueError(
            f"Installed FO4TerrainCore.esm sha256 {actual_core_sha} != staged core {wb5_rep['core_sha256_before']}"
        )

    dlc_files, dlc_plugins = _dlc_install_artifacts(dlc_doors_dir)
    ptxt = _plugins_txt_path()
    if not ptxt.is_file():
        raise FileNotFoundError(f"Missing Plugins.txt: {ptxt}")
    ptxt_raw_before = ptxt.read_bytes()
    ptxt_text = ptxt_raw_before.decode("utf-8-sig")
    nl = "\r\n" if "\r\n" in ptxt_text else "\n"
    bom = b"\xef\xbb\xbf" if ptxt_raw_before.startswith(b"\xef\xbb\xbf") else b""
    lines = ptxt_text.splitlines()

    def _clean_name(ln: str) -> str:
        return ln.strip().lstrip("*").strip().casefold()

    active_low = {ln.strip()[1:].strip().casefold() for ln in lines if ln.strip().startswith("*")}
    if "fo4terraincore.esm" not in active_low:
        raise ValueError("FO4TerrainCore.esm must be active (*) in Plugins.txt before installing FO4TerrainCore_DLC.esm")
    if OVERRIDE_PLUGIN_NAME.casefold() in {_clean_name(ln) for ln in lines}:
        raise ValueError(f"Plugins.txt already mentions {OVERRIDE_PLUGIN_NAME}")
    if (data_dir / OVERRIDE_PLUGIN_NAME).exists():
        raise FileExistsError(f"{data_dir / OVERRIDE_PLUGIN_NAME} already exists")

    # Determine whether FO4DLC archives are already installed or should be installed from dlc_doors_dir
    added_files: dict[str, str] = {}
    replaced_fo4dlc: dict[str, str] | None = None
    patched_dlc_src = dlc_doors_dir / "FO4DLC.esm"
    patched_dlc_sha = sha256_file(patched_dlc_src)

    data_dlc_esm = data_dir / "FO4DLC.esm"
    if data_dlc_esm.exists():
        # Verify all required archives are already present in Data/
        for fname in dlc_files:
            if fname == "FO4DLC.esm":
                continue
            if not (data_dir / fname).is_file():
                raise FileNotFoundError(
                    f"Data/FO4DLC.esm exists, but required companion/archive {fname!r} is missing from {data_dir}"
                )
        cur_dlc_sha = sha256_file(data_dlc_esm)
        if cur_dlc_sha.lower() != patched_dlc_sha.lower():
            # Allow swapping only if Data/FO4DLC.esm matches the unpatched FO4DLC.esm from doors.json["port"]
            unpatched_port = Path(doors_rep.get("port") or "") / "FO4DLC.esm"
            if not unpatched_port.is_file() or sha256_file(unpatched_port).lower() != cur_dlc_sha.lower():
                raise ValueError(
                    "Data/FO4DLC.esm does not match either the patched or pinned unpatched FO4DLC.esm; refusing overwrite"
                )
            bak_path = data_dir / DLC_BACKUP_NAME
            shutil.copy2(data_dlc_esm, bak_path)
            vmad_patch.write_output(str(data_dlc_esm), patched_dlc_src.read_bytes())
            replaced_fo4dlc = {
                "backup_file": DLC_BACKUP_NAME,
                "original_sha256": cur_dlc_sha,
                "patched_sha256": patched_dlc_sha,
            }
    else:
        for fname in dlc_files:
            if (data_dir / fname).exists():
                raise FileExistsError(f"Refusing partial overwrite: {data_dir / fname} already exists")
        for fname in dlc_files:
            src_f = dlc_doors_dir / fname
            dst_f = data_dir / fname
            _copy_or_link(src_f, dst_f)
            added_files[fname] = sha256_file(dst_f)

    # Install FO4TerrainCore_DLC.esm
    over_src = stage_dir / OVERRIDE_PLUGIN_NAME
    over_dst = data_dir / OVERRIDE_PLUGIN_NAME
    _copy_or_link(over_src, over_dst)
    added_files[OVERRIDE_PLUGIN_NAME] = sha256_file(over_dst)

    # Insert `*FO4DLC.esm`, `*FO4DLCTexturesN.esm`, `*FO4TerrainCore_DLC.esm` after `*FO4TerrainCore.esm` and strictly
    # before `*FO4SFMapMarkers.esm`, `*FO4SFHome.esm`, `*FO4TerrainCore_Home.esm`, and `*FO4TerrainCore_Mars.esm`.
    want_active = [*dlc_plugins, OVERRIDE_PLUGIN_NAME]
    filtered_lines = [ln for ln in lines if _clean_name(ln) not in {p.casefold() for p in want_active}]
    after_core_idx = next(i for i, ln in enumerate(filtered_lines) if _clean_name(ln) == "fo4terraincore.esm") + 1
    before_set = {
        "fo4sfmapmarkers.esm",
        "fo4sfhome.esm",
        "fo4terraincore_home.esm",
        "fo4terraincore_mars.esm",
    }
    before_indices = [i for i, ln in enumerate(filtered_lines) if _clean_name(ln) in before_set]
    insert_at = min(before_indices) if before_indices and min(before_indices) >= after_core_idx else after_core_idx
    new_lines = (
        filtered_lines[:insert_at]
        + [f"*{p}" for p in want_active]
        + filtered_lines[insert_at:]
    )
    ptxt_new_bytes = bom + (nl.join(new_lines) + nl).encode("utf-8")
    vmad_patch.write_output(str(ptxt), ptxt_new_bytes)

    receipt = {
        "plugin": OVERRIDE_PLUGIN_NAME,
        "stage_dir": str(stage_dir.resolve()),
        "dlc_doors_dir": str(dlc_doors_dir.resolve()),
        "added_files": added_files,
        "replaced_fo4dlc": replaced_fo4dlc,
        "activated_plugins": want_active,
        "plugins_txt_before_b64": base64.b64encode(ptxt_raw_before).decode("ascii"),
        "plugins_txt_after_sha256": hashlib.sha256(ptxt_new_bytes).hexdigest(),
    }
    vmad_patch.write_output(str(rec_path), json.dumps(receipt, indent=2).encode("utf-8"))
    return receipt


def uninstall_override_session(*, starfield_dir: Path, system: Any = None) -> dict[str, Any]:
    import base64

    _ensure_game_closed("uninstall", system=system)
    data_dir = starfield_dir / "Data"
    rec_path = data_dir / INSTALL_RECORD_NAME
    if not rec_path.is_file():
        raise FileNotFoundError(f"Nothing installed ({rec_path} not found)")
    receipt = _load_json(rec_path)

    # Verify every added file still matches its recorded SHA-256 before removing
    for fname, expected_sha in (receipt.get("added_files") or {}).items():
        fpath = data_dir / fname
        if fpath.exists():
            got_sha = sha256_file(fpath)
            if got_sha.lower() != str(expected_sha).lower():
                raise ValueError(f"Refusing to remove modified file {fpath} (sha256 {got_sha} != {expected_sha})")

    rep_dlc = receipt.get("replaced_fo4dlc")
    if rep_dlc:
        dlc_esm = data_dir / "FO4DLC.esm"
        bak_path = data_dir / rep_dlc["backup_file"]
        if not bak_path.is_file() or sha256_file(bak_path).lower() != str(rep_dlc["original_sha256"]).lower():
            raise ValueError(f"Missing or corrupted FO4DLC backup {bak_path}")
        if dlc_esm.exists() and sha256_file(dlc_esm).lower() != str(rep_dlc["patched_sha256"]).lower():
            raise ValueError("Data/FO4DLC.esm changed since install; refusing restore")
        vmad_patch.write_output(str(dlc_esm), bak_path.read_bytes())
        bak_path.unlink()

    removed: list[str] = []
    for fname in receipt.get("added_files") or {}:
        fpath = data_dir / fname
        if fpath.exists():
            fpath.unlink()
            removed.append(fname)

    ptxt = _plugins_txt_path()
    raw_before = base64.b64decode(receipt["plugins_txt_before_b64"])
    vmad_patch.write_output(str(ptxt), raw_before)
    rec_path.unlink()
    return {"removed_files": removed, "restored_fo4dlc": bool(rep_dlc)}


def cmd_install(args: argparse.Namespace) -> int:
    try:
        rec = install_override_session(
            stage_dir=Path(args.dir),
            dlc_doors_dir=Path(args.dlc_doors),
            starfield_dir=Path(args.starfield),
        )
    except (FileNotFoundError, FileExistsError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(
        f"installed wb5 session: added={len(rec['added_files'])}, "
        f"plugins={rec['activated_plugins']}"
    )
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    try:
        res = uninstall_override_session(starfield_dir=Path(args.starfield))
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"uninstalled wb5 session: removed={len(res['removed_files'])}, restored_fo4dlc={res['restored_fo4dlc']}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    rec_path = Path(args.starfield) / "Data" / INSTALL_RECORD_NAME
    if not rec_path.is_file():
        print("wb5 status: not installed")
        return 0
    rec = _load_json(rec_path)
    print(f"wb5 status: installed plugins={rec.get('activated_plugins')}")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="Stage FO4TerrainCore_DLC.esm (and optional patched FO4DLC.esm doors stage)")
    b.add_argument("--edits", required=True, help="Path to Commonwealth DLC diff JSON (dlc_edits.json)")
    b.add_argument("--core", required=True, help="Core stage folder (FO4TerrainCore.esm, objects.json, formids.json)")
    b.add_argument("--dlc", required=True, help="Pinned FO4DLC stage folder (FO4DLC.esm, formids.json)")
    b.add_argument("--out", required=True, help="Output stage folder outside Git/game trees")
    b.add_argument("--fo4-data", default="", help="Fallout 4 Data folder for reading base/XTEL records")
    b.add_argument("--base-catalog", default="", help="Optional pre-extracted base/door catalog JSON")
    b.add_argument("--extra-manifest", default="", help="Optional converter manifest for models neither core nor FO4DLC holds")
    b.add_argument(
        "--expected-dlc-formids-sha256",
        default=PINNED_FO4DLC_FORMIDS_SHA256,
        help="Pinned SHA-256 of FO4DLC formids.json (empty string disables pin in synthetic tests only)",
    )
    b.add_argument("--dlc-doors-out", default="", help="Optional output folder for patched FO4DLC.esm stage (WB5b)")

    ck = sub.add_parser("check", help="Offline verification of FO4TerrainCore_DLC.esm and WB5b two-way doors")
    ck.add_argument("--out", required=True, help="Staged FO4TerrainCore_DLC.esm folder")
    ck.add_argument("--core", required=True, help="Core stage folder (verifies FO4TerrainCore.esm SHA-256 unchanged)")
    ck.add_argument("--dlc", required=True, help="Pinned FO4DLC stage folder")
    ck.add_argument("--dlc-doors-out", default="", help="Patched FO4DLC.esm stage folder for WB5b two-way door check")
    ck.add_argument(
        "--expected-dlc-formids-sha256",
        default=PINNED_FO4DLC_FORMIDS_SHA256,
        help="Pinned SHA-256 of FO4DLC formids.json",
    )

    ins = sub.add_parser("install", help="Reversibly install FO4TerrainCore_DLC.esm + patched FO4DLC stage")
    ins.add_argument("--dir", required=True, help="Staged FO4TerrainCore_DLC.esm folder")
    ins.add_argument("--dlc-doors", required=True, help="Patched FO4DLC.esm doors stage folder (with FO4DLC archives)")
    ins.add_argument("--starfield", required=True, help="Starfield game directory")

    for u_name in ("uninstall", "undo"):
        un = sub.add_parser(u_name, help="Restore Data and Plugins.txt byte-for-byte after a WB5 TEST-STATION session")
        un.add_argument("--starfield", required=True, help="Starfield game directory")

    st = sub.add_parser("status", help="Print WB5 install status")
    st.add_argument("--starfield", required=True, help="Starfield game directory")
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_arg_parser()
    args = ap.parse_args(argv)
    return {
        "build": cmd_build,
        "check": cmd_check,
        "install": cmd_install,
        "uninstall": cmd_uninstall,
        "undo": cmd_uninstall,
        "status": cmd_status,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
