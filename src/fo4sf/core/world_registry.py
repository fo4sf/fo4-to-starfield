"""Unified world and location registry loader, validator, and Pip-Boy discovery capacity checker (`WS3`).

Reads `src/fo4sf/core/world_registry.json` (metadata only: world/location EditorIDs, hex FormIDs, cell bounds,
planned Starfield host/plugin/marker-slice parameters, and per-part status with repo-relative evidence paths).
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REGISTRY_PATH = os.path.join(HERE, "world_registry.json")

ALLOWED_PART_STATUSES: Tuple[str, ...] = (
    "none",
    "staged",
    "built offline",
    "installed",
    "passed in game",
)

REQUIRED_STATUS_PARTS: Tuple[str, ...] = (
    "terrain",
    "objects",
    "water",
    "ground_textures",
    "walk_mesh",
    "interiors",
    "doors",
    "markers",
    "locations",
    "travel",
    "lod",
)

ALLOWED_WORLD_KINDS: Tuple[str, ...] = (
    "world",
    "child_world",
    "dlc_edit",
    "no_build",
    "other_game_world",
)

CURRENT_PIPBOY_DISC_GLOBALS = 14
PIPBOY_BITS_PER_GLOBAL = 24
CURRENT_PIPBOY_DISC_CAPACITY = CURRENT_PIPBOY_DISC_GLOBALS * PIPBOY_BITS_PER_GLOBAL  # 336


class RegistryError(ValueError):
    """Raised when `world_registry.json` fails schema, uniqueness, slice, or redaction validation."""


@dataclass(frozen=True)
class PartStatus:
    state: str
    evidence: str


@dataclass(frozen=True)
class SourceWorldspace:
    edid: Optional[str]
    form_id: Optional[str]
    defining_plugin: Optional[str]
    parent_world: Optional[str]


@dataclass(frozen=True)
class WorldBounds:
    cell_bbox: Optional[Tuple[int, int, int, int]]
    land_bbox: Optional[Tuple[int, int, int, int]]
    land_cells: int
    ref_bbox: Optional[Tuple[int, int, int, int]]
    height_range_m: Optional[Tuple[float, float]]
    map_marker_count: int


@dataclass(frozen=True)
class PlannedStarfieldWorld:
    world_edid: Optional[str]
    plugin: Optional[str]
    tile_cells: Optional[int]
    cell_count: Optional[int]
    host_planet: Optional[str]
    planet_position: Optional[Tuple[float, float]]
    measured_merge_offset: Optional[Tuple[float, float]]
    pipboy_plugin_code: Optional[int]
    map_picture: Optional[str]
    marker_index_range: Optional[Tuple[int, int]]


@dataclass(frozen=True)
class StartDescriptorRef:
    key: str
    start_cell: str
    surface_anchor: str


@dataclass(frozen=True)
class LocationRow:
    edid: str
    form_id: str
    plugin: str
    form_key: str
    parent_lctn: Optional[str]
    parent_world: str


@dataclass(frozen=True)
class WorldRow:
    key: str
    kind: str
    game: str
    source_plugins: Tuple[str, ...]
    source_worldspace: SourceWorldspace
    bounds: WorldBounds
    planned_starfield_world: PlannedStarfieldWorld
    status: Mapping[str, PartStatus]
    start_descriptors: Tuple[StartDescriptorRef, ...]
    locations: Tuple[LocationRow, ...]


@dataclass(frozen=True)
class WorldOverflowEntry:
    world_key: str
    marker_index_range: Tuple[int, int]
    total_markers: int
    in_capacity_markers: int
    overflow_markers: int


@dataclass(frozen=True)
class DiscoveryCapacityReport:
    capacity_bits: int
    bits_per_global: int
    current_globals: int
    total_reserved_markers: int
    fits_capacity: bool
    shortfall_markers: int
    required_globals_24bit: int
    additional_globals_needed: int
    overflow_by_world: Tuple[WorldOverflowEntry, ...]

    def format_summary(self) -> str:
        if self.fits_capacity:
            return (
                f"Pip-Boy discovery store OK: {self.total_reserved_markers}/{self.capacity_bits} bits used "
                f"({self.current_globals} x {self.bits_per_global}-bit globals)."
            )
        details = ", ".join(
            f"{e.world_key} [{e.marker_index_range[0]}..{e.marker_index_range[1]}) "
            f"overflow={e.overflow_markers}/{e.total_markers}"
            for e in self.overflow_by_world
        )
        return (
            f"Pip-Boy discovery capacity shortfall: {self.total_reserved_markers} reserved markers exceed "
            f"{self.capacity_bits}-bit store ({self.current_globals} x {self.bits_per_global}-bit globals) by "
            f"{self.shortfall_markers} markers (need {self.required_globals_24bit} globals, +{self.additional_globals_needed}); "
            f"overflowing worlds: {details}"
        )


def _check_neutral_path(path_val: str, context: str) -> None:
    if not path_val or not isinstance(path_val, str):
        raise RegistryError(f"{context}: evidence/asset path must be a non-empty string")
    norm = path_val.replace("\\", "/")
    if ":" in norm.split("/")[0] or norm.startswith("/"):
        raise RegistryError(f"{context}: absolute or machine-specific path forbidden ({path_val!r})")
    low = norm.lower()
    for bad in ("users/", "steamapps/", "worktrees/", "owner-tests/"):
        if bad in low:
            raise RegistryError(f"{context}: machine-specific path token forbidden ({path_val!r})")


def _opt_bbox(raw: Any, context: str) -> Optional[Tuple[int, int, int, int]]:
    if raw is None:
        return None
    if not isinstance(raw, list) or len(raw) != 4 or not all(isinstance(v, int) for v in raw):
        raise RegistryError(f"{context}: expected [xmin, xmax, ymin, ymax] integers or null")
    if raw[0] > raw[1] or raw[2] > raw[3]:
        raise RegistryError(f"{context}: inverted bounds {raw}")
    return (raw[0], raw[1], raw[2], raw[3])


def _opt_pair_float(raw: Any, context: str) -> Optional[Tuple[float, float]]:
    if raw is None:
        return None
    if not isinstance(raw, list) or len(raw) != 2 or not all(isinstance(v, (int, float)) for v in raw):
        raise RegistryError(f"{context}: expected [a, b] numbers or null")
    return (float(raw[0]), float(raw[1]))


def _opt_slice(raw: Any, context: str) -> Optional[Tuple[int, int]]:
    if raw is None:
        return None
    if not isinstance(raw, list) or len(raw) != 2 or not all(isinstance(v, int) for v in raw):
        raise RegistryError(f"{context}: expected [start, end] integer slice or null")
    if raw[0] < 0 or raw[1] <= raw[0]:
        raise RegistryError(f"{context}: invalid half-open marker_index_range {raw}")
    return (raw[0], raw[1])


class WorldRegistry:
    """Validated read-only view of `world_registry.json`."""

    def __init__(self, schema_version: int, worlds: Sequence[WorldRow]) -> None:
        self.schema_version = schema_version
        self._worlds: Dict[str, WorldRow] = {}
        self._by_edid: Dict[str, WorldRow] = {}
        self._by_plugin_code: Dict[int, WorldRow] = {}
        self._all_locations: List[LocationRow] = []

        seen_loc_keys: set[str] = set()
        slices: List[Tuple[int, int, str]] = []

        for w in worlds:
            if w.key in self._worlds:
                raise RegistryError(f"duplicate world key: {w.key}")
            self._worlds[w.key] = w
            if w.kind != "dlc_edit" and w.source_worldspace.edid:
                ed_low = w.source_worldspace.edid.lower()
                self._by_edid.setdefault(ed_low, w)

            pcode = w.planned_starfield_world.pipboy_plugin_code
            if pcode is not None:
                if pcode <= 0:
                    raise RegistryError(f"{w.key}: pipboy_plugin_code must be >= 1 or null, got {pcode}")
                if pcode in self._by_plugin_code:
                    other = self._by_plugin_code[pcode].key
                    raise RegistryError(f"duplicate pipboy_plugin_code {pcode} on {w.key} and {other}")
                self._by_plugin_code[pcode] = w

            mslice = w.planned_starfield_world.marker_index_range
            if mslice is not None:
                slices.append((mslice[0], mslice[1], w.key))

            for loc in w.locations:
                if loc.form_key in seen_loc_keys:
                    raise RegistryError(f"duplicate location form_key {loc.form_key} under {w.key}")
                seen_loc_keys.add(loc.form_key)
                self._all_locations.append(loc)

        slices.sort(key=lambda item: (item[0], item[1]))
        for idx in range(len(slices) - 1):
            s0, e0, k0 = slices[idx]
            s1, e1, k1 = slices[idx + 1]
            if e0 > s1:
                raise RegistryError(
                    f"overlapping marker_index_range slices: {k0} [{s0}, {e0}) overlaps {k1} [{s1}, {e1})"
                )

    @property
    def worlds(self) -> Mapping[str, WorldRow]:
        return self._worlds

    def has_world(self, key_or_edid: str) -> bool:
        if key_or_edid in self._worlds:
            return True
        low = key_or_edid.strip().lower()
        for k in self._worlds:
            if k.lower() == low:
                return True
        return low in self._by_edid

    def get_world(self, key_or_edid: str) -> WorldRow:
        if key_or_edid in self._worlds:
            return self._worlds[key_or_edid]
        low = key_or_edid.strip().lower()
        for k, w in self._worlds.items():
            if k.lower() == low:
                return w
        if low in self._by_edid:
            return self._by_edid[low]
        raise KeyError(f"unknown world in registry: {key_or_edid!r}")

    def world_for_plugin_code(self, plugin_code: int) -> Optional[WorldRow]:
        return self._by_plugin_code.get(plugin_code)

    def all_locations(self) -> Tuple[LocationRow, ...]:
        return tuple(self._all_locations)

    def locations_for_world(self, key_or_edid: str) -> Tuple[LocationRow, ...]:
        return self.get_world(key_or_edid).locations

    def discovery_capacity_report(
        self,
        capacity_bits: int = CURRENT_PIPBOY_DISC_CAPACITY,
        bits_per_global: int = PIPBOY_BITS_PER_GLOBAL,
    ) -> DiscoveryCapacityReport:
        if capacity_bits <= 0 or bits_per_global <= 0:
            raise RegistryError("capacity_bits and bits_per_global must be positive")
        current_globals = capacity_bits // bits_per_global
        max_end = 0
        overflow_entries: List[WorldOverflowEntry] = []

        sliced_worlds = [
            w for w in self._worlds.values() if w.planned_starfield_world.marker_index_range is not None
        ]
        sliced_worlds.sort(key=lambda w: w.planned_starfield_world.marker_index_range[0])  # type: ignore[index]

        for w in sliced_worlds:
            start, end = w.planned_starfield_world.marker_index_range  # type: ignore[misc]
            max_end = max(max_end, end)
            total = end - start
            in_cap = max(0, min(end, capacity_bits) - start)
            over = total - in_cap
            if over > 0:
                overflow_entries.append(
                    WorldOverflowEntry(
                        world_key=w.key,
                        marker_index_range=(start, end),
                        total_markers=total,
                        in_capacity_markers=in_cap,
                        overflow_markers=over,
                    )
                )

        shortfall = max(0, max_end - capacity_bits)
        req_globals = math.ceil(max_end / bits_per_global) if max_end > 0 else current_globals
        extra_globals = max(0, req_globals - current_globals)
        return DiscoveryCapacityReport(
            capacity_bits=capacity_bits,
            bits_per_global=bits_per_global,
            current_globals=current_globals,
            total_reserved_markers=max_end,
            fits_capacity=(shortfall == 0),
            shortfall_markers=shortfall,
            required_globals_24bit=req_globals,
            additional_globals_needed=extra_globals,
            overflow_by_world=tuple(overflow_entries),
        )


def parse_world_registry(doc: Mapping[str, Any]) -> WorldRegistry:
    if not isinstance(doc, Mapping):
        raise RegistryError("registry root must be a JSON object")
    schema_version = int(doc.get("schema_version", 0))
    if schema_version != 1:
        raise RegistryError(f"unsupported registry schema_version: {schema_version}")
    raw_worlds = doc.get("worlds")
    if not isinstance(raw_worlds, list) or not raw_worlds:
        raise RegistryError("registry 'worlds' must be a non-empty list")

    parsed_worlds: List[WorldRow] = []
    for raw_w in raw_worlds:
        if not isinstance(raw_w, Mapping):
            raise RegistryError("each world entry must be an object")
        key = str(raw_w.get("key", "")).strip()
        if not key:
            raise RegistryError("world row missing 'key'")
        kind = str(raw_w.get("kind", "")).strip()
        if kind not in ALLOWED_WORLD_KINDS:
            raise RegistryError(f"{key}: invalid kind {kind!r}")
        game = str(raw_w.get("game", "")).strip()
        if not game:
            raise RegistryError(f"{key}: missing 'game'")
        src_plugins_raw = raw_w.get("source_plugins")
        if not isinstance(src_plugins_raw, list) or not all(isinstance(p, str) and p for p in src_plugins_raw):
            raise RegistryError(f"{key}: 'source_plugins' must be a list of plugin filenames")
        for p in src_plugins_raw:
            if "/" in p or "\\" in p or ":" in p:
                raise RegistryError(f"{key}: source_plugin must be basename only, got {p!r}")

        sw_raw = raw_w.get("source_worldspace")
        if not isinstance(sw_raw, Mapping):
            raise RegistryError(f"{key}: missing 'source_worldspace' object")
        sw = SourceWorldspace(
            edid=sw_raw.get("edid"),
            form_id=sw_raw.get("form_id"),
            defining_plugin=sw_raw.get("defining_plugin"),
            parent_world=sw_raw.get("parent_world"),
        )

        b_raw = raw_w.get("bounds")
        if not isinstance(b_raw, Mapping):
            raise RegistryError(f"{key}: missing 'bounds' object")
        bounds = WorldBounds(
            cell_bbox=_opt_bbox(b_raw.get("cell_bbox"), f"{key}.bounds.cell_bbox"),
            land_bbox=_opt_bbox(b_raw.get("land_bbox"), f"{key}.bounds.land_bbox"),
            land_cells=int(b_raw.get("land_cells", 0)),
            ref_bbox=_opt_bbox(b_raw.get("ref_bbox"), f"{key}.bounds.ref_bbox"),
            height_range_m=_opt_pair_float(b_raw.get("height_range_m"), f"{key}.bounds.height_range_m"),
            map_marker_count=int(b_raw.get("map_marker_count", 0)),
        )

        psw_raw = raw_w.get("planned_starfield_world")
        if not isinstance(psw_raw, Mapping):
            raise RegistryError(f"{key}: missing 'planned_starfield_world' object")
        map_pic = psw_raw.get("map_picture")
        if map_pic is not None:
            _check_neutral_path(map_pic, f"{key}.planned_starfield_world.map_picture")
        pcode_raw = psw_raw.get("pipboy_plugin_code")
        if pcode_raw is not None and (isinstance(pcode_raw, bool) or not isinstance(pcode_raw, int)):
            raise RegistryError(f"{key}: pipboy_plugin_code must be int or null")
        psw = PlannedStarfieldWorld(
            world_edid=psw_raw.get("world_edid"),
            plugin=psw_raw.get("plugin"),
            tile_cells=int(psw_raw["tile_cells"]) if psw_raw.get("tile_cells") is not None else None,
            cell_count=int(psw_raw["cell_count"]) if psw_raw.get("cell_count") is not None else None,
            host_planet=psw_raw.get("host_planet"),
            planet_position=_opt_pair_float(psw_raw.get("planet_position"), f"{key}.planet_position"),
            measured_merge_offset=_opt_pair_float(psw_raw.get("measured_merge_offset"), f"{key}.measured_merge_offset"),
            pipboy_plugin_code=pcode_raw,
            map_picture=map_pic,
            marker_index_range=_opt_slice(psw_raw.get("marker_index_range"), f"{key}.marker_index_range"),
        )

        st_raw = raw_w.get("status")
        if not isinstance(st_raw, Mapping):
            raise RegistryError(f"{key}: missing 'status' object")
        extra_parts = set(st_raw.keys()) - set(REQUIRED_STATUS_PARTS)
        missing_parts = set(REQUIRED_STATUS_PARTS) - set(st_raw.keys())
        if missing_parts or extra_parts:
            raise RegistryError(f"{key}: status keys mismatch (missing={sorted(missing_parts)}, extra={sorted(extra_parts)})")
        status_map: Dict[str, PartStatus] = {}
        for part in REQUIRED_STATUS_PARTS:
            pentry = st_raw[part]
            if not isinstance(pentry, Mapping):
                raise RegistryError(f"{key}.status.{part}: must be an object with 'state' and 'evidence'")
            state = pentry.get("state")
            if state == "built_offline":
                state = "built offline"
            evidence = pentry.get("evidence")
            if state not in ALLOWED_PART_STATUSES:
                raise RegistryError(f"{key}.status.{part}: invalid state {state!r}")
            _check_neutral_path(evidence, f"{key}.status.{part}.evidence")
            status_map[part] = PartStatus(state=state, evidence=evidence)

        sdesc_raw = raw_w.get("start_descriptors", [])
        if not isinstance(sdesc_raw, list):
            raise RegistryError(f"{key}: 'start_descriptors' must be a list")
        sdescs = tuple(
            StartDescriptorRef(
                key=str(sd["key"]),
                start_cell=str(sd["start_cell"]),
                surface_anchor=str(sd["surface_anchor"]),
            )
            for sd in sdesc_raw
        )

        locs_raw = raw_w.get("locations", [])
        if not isinstance(locs_raw, list):
            raise RegistryError(f"{key}: 'locations' must be a list")
        loc_rows: List[LocationRow] = []
        for lr in locs_raw:
            if not isinstance(lr, Mapping):
                raise RegistryError(f"{key}: location entry must be an object")
            allowed_loc_keys = {"edid", "form_id", "plugin", "form_key", "parent_lctn", "parent_world"}
            if set(lr.keys()) != allowed_loc_keys:
                raise RegistryError(f"{key}: location keys must be strictly {sorted(allowed_loc_keys)}, got {sorted(lr.keys())}")
            if lr["parent_world"] != key:
                raise RegistryError(f"{key}: location {lr.get('form_key')} parent_world={lr['parent_world']!r} != {key!r}")
            loc_rows.append(
                LocationRow(
                    edid=str(lr["edid"]),
                    form_id=str(lr["form_id"]),
                    plugin=str(lr["plugin"]),
                    form_key=str(lr["form_key"]),
                    parent_lctn=str(lr["parent_lctn"]) if lr["parent_lctn"] is not None else None,
                    parent_world=key,
                )
            )

        parsed_worlds.append(
            WorldRow(
                key=key,
                kind=kind,
                game=game,
                source_plugins=tuple(src_plugins_raw),
                source_worldspace=sw,
                bounds=bounds,
                planned_starfield_world=psw,
                status=status_map,
                start_descriptors=sdescs,
                locations=tuple(loc_rows),
            )
        )

    return WorldRegistry(schema_version=schema_version, worlds=parsed_worlds)


def load_world_registry(path: str = DEFAULT_REGISTRY_PATH) -> WorldRegistry:
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    return parse_world_registry(doc)
