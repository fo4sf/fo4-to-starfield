"""IDs-only loot table loader and corridor validator (`2i`).

Enforces that `route_loot_ids.json` holds strictly hex FormIDs, integer counts,
numeric coordinates, plugin filenames, and category tags (zero game text).
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple

from fo4sf.core.core_values import core_form_id

HERE = os.path.dirname(os.path.abspath(__file__))
ROUTE_LOOT_IDS_JSON = os.path.join(HERE, "route_loot_ids.json")

ROUTE_LOOT_PLUGIN = "FO4SFRouteLoot.esm"
ROUTE_LOOT_MASTERS: Tuple[str, ...] = (
    "Starfield.esm",
    "FO4SFCoreValues.esm",
    "FO4SFRads.esm",
    "FO4SFWorkshop.esm",
    "FO4TerrainCore.esm",
    "FO4Port.esm",
)
ALLOWED_CATEGORIES = frozenset({"ammo", "aid", "junk", "caps", "vault_armory"})
ROUTE_CONTAINER_CATEGORIES = frozenset({"ammo", "aid", "junk", "caps"})
CREDITS_FORM_ID = 0x00000F
HEX_ID_RE = re.compile(r"^0x[0-9A-Fa-f]{6}$")
PLUGIN_FILE_RE = re.compile(r"^[A-Za-z0-9_.-]+\.esm$")


@dataclass(frozen=True)
class LootItemEntry:
    plugin: str
    form_id: int
    count: int


@dataclass(frozen=True)
class VaultPickupSpec:
    own_ref_id: int
    plugin: str
    form_id: int
    count: int
    pos_m: Tuple[float, float, float]
    rot_rad: Tuple[float, float, float]


@dataclass(frozen=True)
class RouteLootSpec:
    plugin: str
    masters: Tuple[str, ...]
    corridor_radius_m: float
    corridor_polyline_m: Tuple[Tuple[float, float], ...]
    categories: Dict[str, Tuple[LootItemEntry, ...]]
    fo4_container_categories: Dict[int, str]
    vault_cell_id: int
    vault_case_template_id: int
    vault_own_case_base_id: int
    vault_own_case_ref_id: int
    vault_case_pos_m: Tuple[float, float, float]
    vault_case_rot_rad: Tuple[float, float, float]
    vault_port_locker_cont_id: int
    vault_pistol_id: int
    vault_ammo_id: int
    vault_stimpak_id: int
    vault_min_ammo_rounds: int
    vault_min_stimpaks: int
    vault_pickups: Tuple[VaultPickupSpec, ...]


def parse_hex_id_strict(raw: Any, field: str) -> int:
    if not isinstance(raw, str) or not HEX_ID_RE.match(raw):
        raise ValueError(f"{field}: expected 0xXXXXXX hex FormID string, got {raw!r}")
    val = int(raw, 16)
    if val <= 0 or val > 0xFFFFFF:
        raise ValueError(f"{field}: local FormID out of range: {raw!r}")
    return val


def _check_no_disallowed_strings(node: Any, allowed_plugins: frozenset[str], path: str = "$") -> None:
    """Reject any string value that is not a hex FormID, allowed plugin filename, or allowed category tag."""
    if isinstance(node, dict):
        for k, v in node.items():
            if not isinstance(k, str):
                raise ValueError(f"{path}: non-string JSON key {k!r}")
            # Keys in fo4_container_categories must be hex FormIDs; other keys are structural snake_case / category tags.
            if path.endswith(".fo4_container_categories"):
                parse_hex_id_strict(k, f"{path}.{k}")
            elif not re.match(r"^[a-z0-9_]+$", k):
                raise ValueError(f"{path}: disallowed key {k!r}")
            _check_no_disallowed_strings(v, allowed_plugins, f"{path}.{k}")
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            _check_no_disallowed_strings(item, allowed_plugins, f"{path}[{idx}]")
    elif isinstance(node, str):
        if HEX_ID_RE.match(node):
            return
        if node in ALLOWED_CATEGORIES:
            return
        if node in allowed_plugins or node == ROUTE_LOOT_PLUGIN:
            return
        raise ValueError(f"{path}: disallowed string value {node!r} (IDs, counts, and category tags only)")
    elif isinstance(node, (int, float, bool)) or node is None:
        return
    else:
        raise ValueError(f"{path}: unexpected JSON value type {type(node).__name__}")


def point_to_segment_distance_xy(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> float:
    dx = bx - ax
    dy = by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq <= 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len_sq))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def corridor_distance_m(px: float, py: float, polyline_xy: Sequence[Tuple[float, float]]) -> float:
    if len(polyline_xy) < 2:
        raise ValueError("corridor polyline requires at least 2 points")
    return min(
        point_to_segment_distance_xy(
            px,
            py,
            polyline_xy[i][0],
            polyline_xy[i][1],
            polyline_xy[i + 1][0],
            polyline_xy[i + 1][1],
        )
        for i in range(len(polyline_xy) - 1)
    )


def validate_route_loot_doc(doc: Dict[str, Any]) -> RouteLootSpec:
    if not isinstance(doc, dict) or doc.get("schema_version") != 1:
        raise ValueError("route_loot_ids.json must be a schema_version=1 JSON object")

    plugin = doc.get("plugin")
    if plugin != ROUTE_LOOT_PLUGIN or not PLUGIN_FILE_RE.match(plugin):
        raise ValueError(f"expected plugin={ROUTE_LOOT_PLUGIN!r}, got {plugin!r}")

    masters = tuple(doc.get("masters") or ())
    if masters != ROUTE_LOOT_MASTERS:
        raise ValueError(f"masters {masters} != expected {ROUTE_LOOT_MASTERS}")

    allowed_plugins = frozenset(masters)
    _check_no_disallowed_strings(doc, allowed_plugins)

    currency = doc.get("currency") or {}
    if currency.get("plugin") != "Starfield.esm" or parse_hex_id_strict(currency.get("id"), "currency.id") != CREDITS_FORM_ID:
        raise ValueError("currency must remain Starfield.esm:0x00000F")

    radius_m = float(doc.get("corridor_radius_m", 0.0))
    if not math.isfinite(radius_m) or radius_m <= 0.0 or radius_m > 2000.0:
        raise ValueError(f"invalid corridor_radius_m: {radius_m}")

    raw_poly = doc.get("corridor_polyline_m") or []
    if not isinstance(raw_poly, list) or len(raw_poly) < 2:
        raise ValueError("corridor_polyline_m must have >= 2 [x, y] waypoints")
    poly: List[Tuple[float, float]] = []
    for i, pt in enumerate(raw_poly):
        if not isinstance(pt, list) or len(pt) != 2:
            raise ValueError(f"corridor_polyline_m[{i}] must be [x, y]")
        x, y = float(pt[0]), float(pt[1])
        if not (math.isfinite(x) and math.isfinite(y)):
            raise ValueError(f"corridor_polyline_m[{i}] non-finite")
        poly.append((x, y))

    raw_cats = doc.get("categories") or {}
    if set(raw_cats.keys()) != ALLOWED_CATEGORIES:
        raise ValueError(f"categories keys {set(raw_cats.keys())} != {ALLOWED_CATEGORIES}")

    stimpak_expected = core_form_id("FO4SF_Stimpak")
    cats: Dict[str, Tuple[LootItemEntry, ...]] = {}
    for cat_name, items in raw_cats.items():
        if not isinstance(items, list) or not items:
            raise ValueError(f"category {cat_name!r} must have >= 1 item")
        parsed_items: List[LootItemEntry] = []
        for idx, it in enumerate(items):
            plg = it.get("plugin")
            if plg not in allowed_plugins:
                raise ValueError(f"categories.{cat_name}[{idx}].plugin {plg!r} not in masters")
            fid = parse_hex_id_strict(it.get("id"), f"categories.{cat_name}[{idx}].id")
            cnt = it.get("count")
            if not isinstance(cnt, int) or isinstance(cnt, bool) or cnt < 1 or cnt > 10000:
                raise ValueError(f"categories.{cat_name}[{idx}].count invalid: {cnt!r}")
            parsed_items.append(LootItemEntry(plg, fid, cnt))
        cats[cat_name] = tuple(parsed_items)

    # Verify non-credit items exist in ammo, aid, junk, and vault_armory.
    for non_credit_cat in ("ammo", "aid", "junk", "vault_armory"):
        if not any(not (it.plugin == "Starfield.esm" and it.form_id == CREDITS_FORM_ID) for it in cats[non_credit_cat]):
            raise ValueError(f"category {non_credit_cat!r} lacks non-credit items")

    # Verify CoreValues stimpak, Rads items, and Workshop scrap junk IDs are wired accurately.
    if not any(it.plugin == "FO4SFCoreValues.esm" and it.form_id == stimpak_expected for it in cats["aid"]):
        raise ValueError("aid category must reference FO4SFCoreValues.esm FO4SF_Stimpak (0x000851)")
    rads_ids = {it.form_id for it in cats["aid"] if it.plugin == "FO4SFRads.esm"}
    if not {0x000820, 0x000821}.issubset(rads_ids):
        raise ValueError("aid category must reference FO4SFRads.esm 0x000820 and 0x000821")
    wk_ids = {it.form_id for it in cats["junk"] if it.plugin == "FO4SFWorkshop.esm"}
    if not {0x000820, 0x000821, 0x000822, 0x000823}.issubset(wk_ids):
        raise ValueError("junk category must reference FO4SFWorkshop.esm scrap junk MISC 0x000820..0x000823")

    v111 = doc.get("vault111") or {}
    v_cell = parse_hex_id_strict(v111.get("cell_id"), "vault111.cell_id")
    v_tpl = parse_hex_id_strict(v111.get("case_template_id"), "vault111.case_template_id")
    v_case_base = parse_hex_id_strict(v111.get("own_case_base_id"), "vault111.own_case_base_id")
    v_case_ref = parse_hex_id_strict(v111.get("own_case_ref_id"), "vault111.own_case_ref_id")
    v_locker = parse_hex_id_strict(v111.get("port_locker_cont_id"), "vault111.port_locker_cont_id")
    v_pistol = parse_hex_id_strict(v111.get("pistol_id"), "vault111.pistol_id")
    v_ammo = parse_hex_id_strict(v111.get("ammo_id"), "vault111.ammo_id")
    v_stim = parse_hex_id_strict(v111.get("stimpak_id"), "vault111.stimpak_id")
    min_ammo = int(v111.get("min_ammo_rounds", 0))
    min_stim = int(v111.get("min_stimpaks", 0))
    if v_stim != stimpak_expected:
        raise ValueError(f"vault111.stimpak_id 0x{v_stim:06X} != 0x{stimpak_expected:06X}")
    if min_ammo < 48 or min_stim < 2:
        raise ValueError("vault111 requires min_ammo_rounds >= 48 and min_stimpaks >= 2")
    if v_case_base < 0x800 or v_case_ref < 0x800 or v_case_base == v_case_ref:
        raise ValueError("vault111 own FormIDs must be distinct and >= 0x800")

    def _vec3(raw_v: Any, label: str) -> Tuple[float, float, float]:
        if not isinstance(raw_v, list) or len(raw_v) != 3:
            raise ValueError(f"{label}: expected [x, y, z]")
        vals = (float(raw_v[0]), float(raw_v[1]), float(raw_v[2]))
        if not all(math.isfinite(x) for x in vals):
            raise ValueError(f"{label}: non-finite coordinate")
        return vals

    case_pos = _vec3(v111.get("case_pos_m"), "vault111.case_pos_m")
    case_rot = _vec3(v111.get("case_rot_rad"), "vault111.case_rot_rad")

    armory_pistol_cnt = sum(it.count for it in cats["vault_armory"] if it.plugin == "Starfield.esm" and it.form_id == v_pistol)
    armory_ammo_cnt = sum(it.count for it in cats["vault_armory"] if it.plugin == "Starfield.esm" and it.form_id == v_ammo)
    armory_stim_cnt = sum(it.count for it in cats["vault_armory"] if it.plugin == "FO4SFCoreValues.esm" and it.form_id == v_stim)
    if armory_pistol_cnt < 1 or armory_ammo_cnt < min_ammo or armory_stim_cnt < min_stim:
        raise ValueError("vault_armory category does not satisfy Vault 111 pistol/ammo/stimpak minimums")

    used_own_ids = {v_case_base, v_case_ref}
    pickups: List[VaultPickupSpec] = []
    for idx, pk in enumerate(v111.get("pickups") or []):
        rid = parse_hex_id_strict(pk.get("own_ref_id"), f"vault111.pickups[{idx}].own_ref_id")
        if rid < 0x800 or rid in used_own_ids:
            raise ValueError(f"vault111.pickups[{idx}].own_ref_id 0x{rid:06X} invalid or duplicate")
        used_own_ids.add(rid)
        plg = pk.get("plugin")
        if plg not in allowed_plugins:
            raise ValueError(f"vault111.pickups[{idx}].plugin {plg!r} not in masters")
        iid = parse_hex_id_strict(pk.get("id"), f"vault111.pickups[{idx}].id")
        cnt = pk.get("count")
        if not isinstance(cnt, int) or isinstance(cnt, bool) or cnt < 1:
            raise ValueError(f"vault111.pickups[{idx}].count invalid")
        pickups.append(
            VaultPickupSpec(
                own_ref_id=rid,
                plugin=plg,
                form_id=iid,
                count=cnt,
                pos_m=_vec3(pk.get("pos_m"), f"vault111.pickups[{idx}].pos_m"),
                rot_rad=_vec3(pk.get("rot_rad"), f"vault111.pickups[{idx}].rot_rad"),
            )
        )
    if not pickups:
        raise ValueError("vault111.pickups must not be empty")

    raw_map = doc.get("fo4_container_categories") or {}
    if not isinstance(raw_map, dict) or not raw_map:
        raise ValueError("fo4_container_categories must be a non-empty mapping")
    fo4_map: Dict[int, str] = {}
    for hex_k, cat_v in raw_map.items():
        fid = parse_hex_id_strict(hex_k, f"fo4_container_categories[{hex_k}]")
        if cat_v not in ROUTE_CONTAINER_CATEGORIES:
            raise ValueError(f"fo4_container_categories[{hex_k}] has invalid category {cat_v!r}")
        if fid in fo4_map:
            raise ValueError(f"duplicate FO4 container FormID 0x{fid:06X}")
        fo4_map[fid] = cat_v

    return RouteLootSpec(
        plugin=plugin,
        masters=masters,
        corridor_radius_m=radius_m,
        corridor_polyline_m=tuple(poly),
        categories=cats,
        fo4_container_categories=fo4_map,
        vault_cell_id=v_cell,
        vault_case_template_id=v_tpl,
        vault_own_case_base_id=v_case_base,
        vault_own_case_ref_id=v_case_ref,
        vault_case_pos_m=case_pos,
        vault_case_rot_rad=case_rot,
        vault_port_locker_cont_id=v_locker,
        vault_pistol_id=v_pistol,
        vault_ammo_id=v_ammo,
        vault_stimpak_id=v_stim,
        vault_min_ammo_rounds=min_ammo,
        vault_min_stimpaks=min_stim,
        vault_pickups=tuple(pickups),
    )


def load_route_loot_spec(json_path: str = ROUTE_LOOT_IDS_JSON) -> RouteLootSpec:
    with open(json_path, encoding="utf-8") as f:
        doc = json.load(f)
    return validate_route_loot_doc(doc)
