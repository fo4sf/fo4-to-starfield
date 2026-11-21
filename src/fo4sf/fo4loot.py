"""Raw Fallout 4 container loot (`CNTO` / `LVLI`) resolver for interior container promotion (`IB1`, `--fo4-loot`).

Reads `Fallout4.esm` (and optional DLC `.esm` plugins in load order) with `fo4land.py` — no Mutagen, no game files
modified — and resolves each placed container's `CNTO` entries (including nested/cyclic `LVLI` leveled lists) to
converted Fallout 4 item models present in `<work>/manifest.json` (written into `FO4Port.esm` as `MISC` bases under
`<Prefix>_misc_<6hex>_<plugin>`), logging every unconverted item or empty container fallback.
"""
from __future__ import annotations

from collections import deque
import json
import os
import struct
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from . import fo4land as fl

DELETED = 0x20
CNTO_STRUCT = struct.Struct("<Ii")
LVLO_MIN_SIZE = 8
ITEM_SIGS = frozenset({"MISC", "ALCH", "WEAP", "AMMO", "BOOK", "ARMO", "KEYM", "NOTE"})

# Vanilla currency / lockpick FormKeys in Fallout4.esm that map directly to Starfield.esm equivalents when no
# standalone converted FO4 model overrides them. Caps001 always maps to Starfield Credits (currency).
FO4_CAPS_FORMKEY = "00000F:Fallout4.esm"
FO4_BOBBYPIN_FORMKEY = "00000A:Fallout4.esm"
SF_CREDITS_FORM = "Starfield.esm:00000F"
SF_DIGIPICK_FORM = "Starfield.esm:00000A"


def _norm_source(path: str) -> str:
    p = path.replace("\\", "/").lstrip("/").lower()
    return p if p.startswith("meshes/") else "meshes/" + p


def _norm_formkey(fk: str) -> str:
    left, sep, right = fk.strip().partition(":")
    if not sep:
        return fk.strip()
    if "." in right:
        hex_part, mod = left, right
    else:
        mod, hex_part = left, right
    if hex_part.lower().startswith("0x"):
        hex_part = hex_part[2:]
    return f"{int(hex_part, 16) & 0xFFFFFF:06X}:{mod}"


def _plugin_masters(path: str) -> List[str]:
    with fl.Plugin(path) as p:
        return [fl.zstring(d) for s, d in fl.iter_subrecords(fl.record_data(p.buf, 0)) if s == b"MAST"]


def _canonical_plugin_names(paths: Sequence[str]) -> Tuple[List[str], Dict[str, str]]:
    canon: Dict[str, str] = {}
    if paths:
        first = os.path.basename(paths[0])
        if first.casefold() == "fallout4.esm":
            canon[first.casefold()] = "Fallout4.esm"
    for path in paths[1:]:
        for m in _plugin_masters(path):
            canon.setdefault(m.casefold(), m)
    ordered = [canon.setdefault(os.path.basename(p).casefold(), os.path.basename(p)) for p in paths]
    return ordered, canon


def _parse_value_weight(sig: str, data_bytes: bytes) -> Tuple[Optional[int], Optional[float]]:
    """Extract (value, weight) from common FO4 item `DATA` subrecord layouts where unambiguous."""
    if sig in ("MISC", "BOOK", "KEYM") and len(data_bytes) >= 8:
        val, wt = struct.unpack_from("<if", data_bytes, 0)
        if val >= 0 and wt >= 0.0 and wt == wt:
            return int(val), round(float(wt), 3)
    if sig == "ALCH" and len(data_bytes) >= 4:
        (wt,) = struct.unpack_from("<f", data_bytes, 0)
        if wt >= 0.0 and wt == wt:
            return None, round(float(wt), 3)
    return None, None


class Fo4LootIndex:
    """In-memory index of `CONT`, `LVLI`, and item base records across `Fallout4.esm` (+ optional DLC plugins)."""

    def __init__(self) -> None:
        self.containers: Dict[str, Dict] = {}   # norm formkey -> {"edid", "entries": [(target_fk, count)]}
        self.leveled: Dict[str, Dict] = {}      # norm formkey -> {"edid", "entries": [(target_fk, count)]}
        self.items: Dict[str, Dict] = {}        # norm formkey -> {"sig", "edid", "model", "full", "value", "weight"}

    @classmethod
    def from_plugins(cls, plugin_paths: Sequence[str]) -> "Fo4LootIndex":
        idx = cls()
        if not plugin_paths:
            return idx
        ordered_names, canon = _canonical_plugin_names(plugin_paths)

        def spell(name: str) -> str:
            return canon.get(name.casefold(), name)

        for pi, path in enumerate(plugin_paths):
            self_name = ordered_names[pi]
            with fl.Plugin(path) as p:
                buf = p.buf
                hdr = list(fl.iter_subrecords(fl.record_data(buf, 0)))
                masters = [spell(fl.zstring(d)) for s, d in hdr if s == b"MAST"]

                def key_of(raw_fid: int) -> str:
                    mi = (raw_fid >> 24) & 0xFF
                    owner = masters[mi] if mi < len(masters) else self_name
                    return f"{raw_fid & 0xFFFFFF:06X}:{owner}"

                for item in fl.iter_items(buf, p.body, len(buf)):
                    if item[0] != "GRUP":
                        continue
                    _g, off, end, label, _gt = item
                    if label in (b"CELL", b"WRLD"):
                        continue
                    sig_str = label.decode("ascii", errors="ignore")
                    if sig_str != "CONT" and sig_str != "LVLI" and sig_str not in ITEM_SIGS:
                        continue
                    for rec in fl.iter_items(buf, off + 24, end):
                        if rec[0] == "GRUP":
                            continue
                        typ, roff, rflags, fid = rec
                        fk = key_of(fid)
                        if rflags & DELETED:
                            idx.containers.pop(fk, None)
                            idx.leveled.pop(fk, None)
                            idx.items.pop(fk, None)
                            continue
                        rsig = typ.decode("ascii", errors="ignore")
                        subs = list(fl.iter_subrecords(fl.record_data(buf, roff)))
                        edid = next((fl.zstring(d) for s, d in subs if s == b"EDID"), "")
                        if rsig == "CONT":
                            entries = []
                            for s, d in subs:
                                if s == b"CNTO" and len(d) >= CNTO_STRUCT.size:
                                    t_fid, cnt = CNTO_STRUCT.unpack_from(d)
                                    if cnt > 0:
                                        entries.append((key_of(t_fid), int(cnt)))
                            idx.containers[fk] = {"edid": edid, "entries": entries}
                        elif rsig == "LVLI":
                            entries = []
                            for s, d in subs:
                                if s == b"LVLO" and len(d) >= LVLO_MIN_SIZE:
                                    t_fid = struct.unpack_from("<I", d, 4)[0]
                                    cnt = struct.unpack_from("<H", d, 8)[0] if len(d) >= 10 else 1
                                    if cnt > 0:
                                        entries.append((key_of(t_fid), int(cnt)))
                            idx.leveled[fk] = {"edid": edid, "entries": entries}
                        elif rsig in ITEM_SIGS:
                            modl = next((fl.zstring(d) for s, d in subs if s == b"MODL"), None)
                            full_raw = next((d for s, d in subs if s == b"FULL"), None)
                            full_txt = (
                                fl.zstring(full_raw)
                                if full_raw is not None and len(full_raw) != 4
                                else None
                            )
                            data_raw = next((d for s, d in subs if s == b"DATA"), b"")
                            val, wt = _parse_value_weight(rsig, data_raw)
                            idx.items[fk] = {
                                "sig": rsig,
                                "edid": edid,
                                "model": modl,
                                "full": full_txt,
                                "value": val,
                                "weight": wt,
                            }
        return idx

    def lvli_leaves(self, lvli_fk: str) -> List[Tuple[str, int]]:
        """Deterministic breadth-first expansion of an `LVLI` to reachable leaf `(item_fk, count)` pairs,
        cutting `LVLI` cycles cleanly."""
        visited_lvli: Set[str] = {lvli_fk.casefold()}
        queue = deque([lvli_fk])
        leaves: List[Tuple[str, int]] = []
        seen_leaves: Set[str] = set()
        while queue:
            cur = queue.popleft()
            node = self.leveled.get(cur)
            if not node:
                continue
            for target_fk, cnt in node["entries"]:
                t_low = target_fk.casefold()
                if target_fk in self.leveled:
                    if t_low not in visited_lvli:
                        visited_lvli.add(t_low)
                        queue.append(target_fk)
                else:
                    if t_low not in seen_leaves:
                        seen_leaves.add(t_low)
                        leaves.append((target_fk, cnt))
        return leaves


def load_manifest_models(manifest_path: str) -> Dict[str, str]:
    """Return `{normalized_fo4_mesh_source: starfield_model_relpath}` for non-posed items in `manifest.json`."""
    if not manifest_path or not os.path.isfile(manifest_path):
        return {}
    with open(manifest_path, encoding="utf-8-sig") as f:
        doc = json.load(f)
    out: Dict[str, str] = {}
    for it in doc.get("items") or []:
        if not isinstance(it, dict) or "pose" in it:
            continue
        src = it.get("source")
        model = it.get("model")
        if isinstance(src, str) and src and isinstance(model, str) and model:
            out.setdefault(_norm_source(src), model)
    return out


def resolve_containers_fo4_loot(
    container_entries: List[dict],
    ref_base_by_src: Dict[str, Tuple[str, str]],
    loot_index: Fo4LootIndex,
    manifest_models: Dict[str, str],
    *,
    edid_for_item_fn,
    item_meta_fn,
    explicit_loot_map: Optional[Dict[str, str]] = None,
    max_leaves_per_lvli: int = 2,
) -> Tuple[List[dict], Dict]:
    """Populate `container_entries` (`[{"src", "edid", "name", "items"}]`) from Fallout 4 `CNTO`/`LVLI` records
    wherever a converted item model exists in `manifest_models` (or `explicit_loot_map`), logging every fallback.

    Returns `(loot_items_list, fo4_loot_report)` and updates each container entry's `"items"` in place (preserving
    per-`edid` agreement across containers sharing the same FO4 `CONT` base).
    """
    explicit = {k.casefold(): v for k, v in (explicit_loot_map or {}).items()}
    loot_items_by_edid: Dict[str, dict] = {}
    fallbacks: List[dict] = []
    cache_by_cont_base: Dict[str, Tuple[List[dict], bool]] = {}

    def try_resolve_leaf(item_fk: str, count: int) -> Tuple[Optional[dict], Optional[str]]:
        norm_fk = _norm_formkey(item_fk)
        low = norm_fk.casefold()
        if low in explicit:
            return {"form": explicit[low], "count": max(1, int(count))}, None
        if low == FO4_CAPS_FORMKEY.casefold():
            return {"form": SF_CREDITS_FORM, "count": max(1, int(count))}, None

        meta = loot_index.items.get(norm_fk)
        if meta is None:
            if low == FO4_BOBBYPIN_FORMKEY.casefold():
                return {"form": SF_DIGIPICK_FORM, "count": max(1, int(count))}, None
            return None, "missing_item_base_record"

        modl = meta.get("model")
        if modl:
            norm_m = _norm_source(modl)
            sf_model = manifest_models.get(norm_m)
            if sf_model:
                misc_edid = edid_for_item_fn(norm_fk)
                if misc_edid not in loot_items_by_edid:
                    name, val, wt = item_meta_fn(norm_fk, meta)
                    loot_items_by_edid[misc_edid] = {
                        "edid": misc_edid,
                        "model": sf_model,
                        "name": name,
                        "value": val,
                        "weight": wt,
                        "source_formkey": norm_fk,
                    }
                return {"form": f"self:{misc_edid}", "count": max(1, int(count))}, None

        if low == FO4_BOBBYPIN_FORMKEY.casefold():
            return {"form": SF_DIGIPICK_FORM, "count": max(1, int(count))}, None
        return None, ("unconverted_item_model" if modl else "item_has_no_model")

    resolved_containers = 0
    non_credit_containers = 0
    fallback_containers = 0

    for entry in container_entries:
        src = entry["src"]
        base_fk_raw, base_edid = ref_base_by_src.get(src, ("", ""))
        base_fk = _norm_formkey(base_fk_raw) if base_fk_raw else ""

        if base_fk in cache_by_cont_base:
            chosen_items, used_fo4 = cache_by_cont_base[base_fk]
            entry["items"] = [dict(x) for x in chosen_items]
            if used_fo4:
                resolved_containers += 1
                if any(x["form"].casefold() != SF_CREDITS_FORM.casefold() for x in chosen_items):
                    non_credit_containers += 1
            else:
                fallback_containers += 1
            continue

        cont_rec = loot_index.containers.get(base_fk)
        if cont_rec is None:
            fallbacks.append({
                "container_base": base_fk or base_fk_raw,
                "container_editor_id": base_edid,
                "item": None,
                "reason": "missing_fo4_cont_record",
                "fallback": "container_table",
            })
            cache_by_cont_base[base_fk] = ([dict(x) for x in entry["items"]], False)
            fallback_containers += 1
            continue

        cnto_entries = cont_rec["entries"]
        if not cnto_entries:
            fallbacks.append({
                "container_base": base_fk,
                "container_editor_id": base_edid or cont_rec.get("edid") or "",
                "item": None,
                "reason": "empty_fo4_cnto",
                "fallback": "container_table",
            })
            cache_by_cont_base[base_fk] = ([dict(x) for x in entry["items"]], False)
            fallback_containers += 1
            continue

        aggregated: Dict[str, int] = {}
        order_forms: List[str] = []

        def add_resolved(item_dict: dict) -> None:
            frm = item_dict["form"]
            if frm not in aggregated:
                order_forms.append(frm)
                aggregated[frm] = 0
            aggregated[frm] += int(item_dict["count"])

        for target_fk_raw, cnt in cnto_entries:
            target_fk = _norm_formkey(target_fk_raw)
            if target_fk in loot_index.leveled:
                leaves = loot_index.lvli_leaves(target_fk)
                if not leaves:
                    fallbacks.append({
                        "container_base": base_fk,
                        "container_editor_id": base_edid or cont_rec.get("edid") or "",
                        "item": target_fk,
                        "reason": "empty_or_unresolved_lvli",
                        "fallback": "skipped_entry",
                    })
                    continue
                converted_non_credit: List[dict] = []
                converted_credit: List[dict] = []
                unconverted_reasons: List[Tuple[str, str]] = []
                for leaf_fk, leaf_cnt in leaves:
                    resolved, why = try_resolve_leaf(leaf_fk, max(1, cnt * leaf_cnt))
                    if resolved is not None:
                        if resolved["form"].casefold() == SF_CREDITS_FORM.casefold():
                            converted_credit.append(resolved)
                        else:
                            converted_non_credit.append(resolved)
                    else:
                        unconverted_reasons.append((leaf_fk, why or "unconverted"))
                picked = (converted_non_credit[:max_leaves_per_lvli]
                          if converted_non_credit
                          else converted_credit[:1])
                if picked:
                    for p_it in picked:
                        add_resolved(p_it)
                    if unconverted_reasons:
                        fallbacks.append({
                            "container_base": base_fk,
                            "container_editor_id": base_edid or cont_rec.get("edid") or "",
                            "item": target_fk,
                            "reason": f"lvli_partial_unconverted ({len(unconverted_reasons)} leaf item(s) unconverted)",
                            "unconverted_leaves": [f"{fk}:{w}" for fk, w in unconverted_reasons[:10]],
                            "fallback": "converted_subset",
                        })
                else:
                    fallbacks.append({
                        "container_base": base_fk,
                        "container_editor_id": base_edid or cont_rec.get("edid") or "",
                        "item": target_fk,
                        "reason": "lvli_no_converted_leaf",
                        "unconverted_leaves": [f"{fk}:{w}" for fk, w in unconverted_reasons[:10]],
                        "fallback": "container_table_if_all_fail",
                    })
            else:
                resolved, why = try_resolve_leaf(target_fk, cnt)
                if resolved is not None:
                    add_resolved(resolved)
                else:
                    fallbacks.append({
                        "container_base": base_fk,
                        "container_editor_id": base_edid or cont_rec.get("edid") or "",
                        "item": target_fk,
                        "reason": why or "unconverted_item_model",
                        "fallback": "container_table_if_all_fail",
                    })

        if order_forms:
            final_items = [{"form": frm, "count": aggregated[frm]} for frm in order_forms]
            entry["items"] = [dict(x) for x in final_items]
            cache_by_cont_base[base_fk] = (final_items, True)
            resolved_containers += 1
            if any(x["form"].casefold() != SF_CREDITS_FORM.casefold() for x in final_items):
                non_credit_containers += 1
        else:
            fallbacks.append({
                "container_base": base_fk,
                "container_editor_id": base_edid or cont_rec.get("edid") or "",
                "item": None,
                "reason": "no_cnto_entries_converted",
                "fallback": "container_table",
            })
            cache_by_cont_base[base_fk] = ([dict(x) for x in entry["items"]], False)
            fallback_containers += 1

    loot_items_sorted = [loot_items_by_edid[k] for k in sorted(loot_items_by_edid, key=str.casefold)]
    report = {
        "containers_total": len(container_entries),
        "containers_fo4_resolved": resolved_containers,
        "containers_non_credit_loot": non_credit_containers,
        "containers_table_fallback": fallback_containers,
        "loot_item_bases": len(loot_items_sorted),
        "fallback_count": len(fallbacks),
        "fallbacks": fallbacks,
    }
    return loot_items_sorted, report
