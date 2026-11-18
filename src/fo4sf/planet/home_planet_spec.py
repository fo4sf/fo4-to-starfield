"""Source-attributed specification and pure record builders for our isolated home host (`FO4SFHome.esm`)
and single host registration plugin (`FO4TerrainCore_Home.esm`).

Design invariants (`W2`, `W3`, `W4`, `WL1`, `WL2`, `C2`, `C3`, `WB1`, `WB2`, `WB3`):
- `FO4SFHome.esm` holds our own isolated star system (`STDT 0x800`), our own location chain (`LCTN 0x801..0x804`
  under `Universe 0x01A53A`), our own home planet (`PNDT 0x805`), our own biome (`BIOM 0x806`), plus under default
  `WB1`–`WB3` parameters our own clear temperate weather (`WTHR 0x807`), climate (`CLMT 0x808`), atmosphere
  (`ATMO 0x809`), Fallout 4 converted ground land texture (`LTEX 0x80A`), and neutral water (`WATR 0x80C`).
- Zero whole-record copies of any Starfield star, planet, biome, weather, climate, or atmosphere (`0` `PCCC`/`XMPM`
  Houdini blobs copied).
- Every subrecord is constructed field-by-field from `STAR_FIELD_SPEC`, `PLANET_FIELD_SPEC`, `BIOM_FIELD_SPEC`,
  `WTHR_FIELD_SPEC`, `CLMT_FIELD_SPEC`, `ATMO_FIELD_SPEC`, `LTEX_FIELD_SPEC`, and `WB3_OVERRIDE_SPEC`.
- Every external `Starfield.esm` trait/pattern reference is resolved by `EditorID` at stage time; `FO4WG1RedRocket.esm`
  is never referenced.
- `FO4TerrainCore_Home.esm` is the ONE registration plugin for the host, built from `world_registry.json`:
  it overrides the home `PNDT` (`CNAM` master worldspaces) plus each registered world's `WRLD` (`SNAM`/`PNAM`,
  `BNAM` biome, `FNAM` flags, and `WB3` `CNAM`/`ZNAM`/`NAM3`/`NAM4`/`DNAM`/`MNAM`/`ONAM`/`FULL` overrides) and
  `LCTN` (`PNAM` surface parent, `WL1` lever keywords, `WB3` `DATA`/`FULL` overrides, and optional merged
  `FO4SFMapMarkers.esm` `LCSR` rows when staged with `--map-markers`), leaving `FO4TerrainCore.esm` untouched
  and byte-identical.
"""
from __future__ import annotations

import hashlib
import math
import os
import struct
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..core.world_registry import load_world_registry
from . import census, esm, probe, records, wb_records

HOME_MASTER = "FO4SFHome.esm"
HOME_REGISTRATION = "FO4TerrainCore_Home.esm"
MARS_REGISTRATION = "FO4TerrainCore_Mars.esm"
CORE_PLUGIN = "FO4TerrainCore.esm"
MAP_MARKERS_PLUGIN = "FO4SFMapMarkers.esm"
CORE_LCTN_LOCAL = 0x000802
CORE_WRLD_LOCAL = 0x000803

STAR = 0x800
SYSTEM_LOC = 0x801
PLANET_LOC = 0x802
ORBIT_LOC = 0x803
SURFACE_LOC = 0x804
PLANET = 0x805
BIOME = 0x806
HOME_WEATHER = wb_records.HOME_WEATHER
HOME_CLIMATE = wb_records.HOME_CLIMATE
HOME_ATMO = wb_records.HOME_ATMO
HOME_GROUND_LTEX = wb_records.HOME_GROUND_LTEX
HOME_SURFACE_TREE = wb_records.HOME_SURFACE_TREE
HOME_WATER = wb_records.HOME_WATER
HOME_SUN_PRESET = wb_records.HOME_SUN_PRESET

FORM_VERSION = 581

DEFAULT_HOME_SYSTEM_ID = 0x000F04F2
DEFAULT_HOME_PLANET_ID = 1
DEFAULT_STAR_NAME = "FO4SF Home"
DEFAULT_PLANET_NAME = "Earth"
DEFAULT_BODY_NAME = "fo4sf_home_earth"
DEFAULT_BIOME_EDID = "FO4SFHomeBiome"
DEFAULT_BIOME_NAME = "FO4SF Home Biome"
DEFAULT_TEMP_C = 15.0
DEFAULT_CLIMATE = "ours"
DEFAULT_SKY_ATMO = "ours"
DEFAULT_GROUND_LTEX = "ours"
DEFAULT_TERRAIN_PATTERN = wb_records.DEFAULT_TERRAIN_PATTERN_EDID
DEFAULT_SURFACE_TREE = "none"
DEFAULT_WB3_MODE = "ours"
DEFAULT_SUN_PRESET = "SunPresetTypeG2"
DEFAULT_ORBITAL_MESHES = "starfield"
DEFAULT_STAR_OFFSET_PC: Tuple[float, float, float] = (3.0, 2.0, 1.5)

CLIMATE_CHOICES: Tuple[str, ...] = wb_records.CLIMATE_CHOICES
SKY_ATMO_CHOICES: Tuple[str, ...] = wb_records.SKY_CHOICES
GROUND_LTEX_CHOICES: Tuple[str, ...] = wb_records.GROUND_LTEX_CHOICES
TERRAIN_PATTERN_CHOICES: Tuple[str, ...] = wb_records.TERRAIN_PATTERN_CHOICES
SURFACE_TREE_CHOICES: Tuple[str, ...] = wb_records.SURFACE_TREE_CHOICES
WB3_MODE_CHOICES: Tuple[str, ...] = wb_records.WB3_MODE_CHOICES
SUN_PRESET_CHOICES: Tuple[str, ...] = wb_records.SUN_PRESET_CHOICES
ORBITAL_MESHES_CHOICES: Tuple[str, ...] = wb_records.ORBITAL_MESHES_CHOICES

# WL2: only bits proven in docs/world/three-way-study.md (431 / 433 Starfield.esm WRLDs, including all hand-built
# cities NewAtlantis, CydoniaCity, AkilaCity, NeonCity and LC172World, carry FNAM = 0x00).
ALLOWED_WRLD_FNAM_BITS = 0x00

# WL1: the five candidate location-lever keywords resolved by EditorID from Starfield.esm.
LEVER_KEYWORD_EDIDS: Tuple[str, ...] = (
    "PCM_OverlayExclusionZone",
    "PCM_OverlayExclusionZone_HumanLocations",
    "LocTypeNoPCMScanTreeContent",
    "LocTypeNoPCMCreatureContent",
    "LocTypeSENotAllowed",
)

# W2: breathable, temperate, zero-fauna/flora, rocky 1g planet trait keywords chosen one by one.
HOME_PLANET_TRAIT_KEYWORD_EDIDS: Tuple[str, ...] = (
    "PlanetAtmosphereType05O2",
    "PlanetPressure02Terrestrial",
    "PlanetTemperature03Temperate",
    "PlanetGravity01Terrestrial",
    "PlanetWaterQuality01Safe",
    "PlanetWaterAbundance02Terrestrial",
    "PlanetFaunaAbundance00None",
    "PlanetFloraAbundance00None",
    "PlanetType07Rock",
    "PlanetMagnetosphereType04Strong",
    "LocTypeNoPCMScanTreeContent",
)

FORBIDDEN_PLANET_KEYWORD_EDIDS: Tuple[str, ...] = (
    "PlanetAtmosphereType01CO2",
    "PlanetPressure01Thin",
    "PlanetTemperature02Cold",
    "LocTypeNoHumanPresence",
)

STAR_FIELD_SPEC: Tuple[Dict[str, Any], ...] = (
    {
        "subrecord": "EDID",
        "field": "editor_id",
        "value": "FO4SFHomeStar (derived from star_name parameter)",
        "source": "FO4SF home host identifier (not SolStar)",
    },
    {
        "subrecord": "BGSOrbitedDataComponent_Component/DATA",
        "field": "gravity_well_m_s2, mass_kg, radius_km, gravity_scale",
        "value": [0.0, 1.9885e30, 696300.0, 1.0],
        "source": "Solar physical constants matching Starfield.esm SolStar (0x0005E5CB) light/physics",
    },
    {
        "subrecord": "BGSStarDataComponent_Component/DATA",
        "field": "catalogue_id, spectral_class, abs_magnitude, mass_kg, inner_hz_au, outer_hz_au, hip, temp_k",
        "value": {
            "spectral_class": "G2",
            "abs_magnitude": 4.85,
            "mass_kg": 1.9885e30,
            "inner_hz_au": 0.75,
            "outer_hz_au": 1.76,
            "hip": 0,
            "temperature_k": 5830,
        },
        "source": "G2V solar spectral/habitable-zone physics from SolStar (0x0005E5CB), HIP cleared to 0",
    },
    {
        "subrecord": "TESPlanetModel_Component/MODL",
        "field": "star_mesh",
        "value": "orbital_meshes parameter (default 'Data/Meshes/Planets/HoudiniPlanets/HoudiniPlanet_star.nif'; 'none' omits component)",
        "source": "Standard BSGalaxy unit-sphere star mesh path (120/123 STDT in Starfield.esm; XMPM/PCCC omitted; '--orbital-meshes none' staged variant)",
    },
    {
        "subrecord": "TESFullName_Component/FULL",
        "field": "full_name",
        "value": "star_name parameter (default 'FO4SF Home')",
        "source": "Plain non-localized string parameter",
    },
    {
        "subrecord": "KSIZ+KWDA",
        "field": "star_class_keyword",
        "value": "Star_Class_G",
        "source": "Starfield.esm KYWD Star_Class_G resolved by EditorID",
    },
    {
        "subrecord": "ANAM",
        "field": "star_body_name",
        "value": "star_name parameter (default 'FO4SF Home')",
        "source": "Plain non-localized star body name parameter",
    },
    {
        "subrecord": "BNAM",
        "field": "galaxy_position_pc",
        "value": "Sol BNAM + star_offset_pc (verified >= 0.5 pc from every star in Data)",
        "source": "Census-verified isolated parsec coordinates",
    },
    {
        "subrecord": "DNAM",
        "field": "system_id",
        "value": "Free u32 system_id unused across Starfield.esm and Data plugins",
        "source": "Read-only Data census (free_system_and_planet_ids)",
    },
    {
        "subrecord": "ENAM",
        "field": "star_light_rgba",
        "value": "0xFFEDFCFC",
        "source": "G2 daylight tint from SolStar (0x0005E5CB) per 14 Nov solar-light rule",
    },
    {
        "subrecord": "PNAM",
        "field": "sun_preset",
        "value": "sun_preset parameter (default 'SunPresetTypeG2'; optional 'ours' -> FO4SFHomeSunPreset 0x0100080D)",
        "source": "14 Nov G2 solar daylight preset (Starfield.esm SunPresetTypeG2 or our standalone FO4SFHomeSunPreset)",
    },
)

PLANET_FIELD_SPEC: Tuple[Dict[str, Any], ...] = (
    {
        "subrecord": "EDID",
        "field": "editor_id",
        "value": "<planet_tag>PlanetData (default 'EarthPlanetData' in FO4SFHome.esm)",
        "source": "Derived from planet_name parameter in FO4SFHome.esm namespace",
    },
    {
        "subrecord": "TESPlanetModel_Component/MODL",
        "field": "planet_mesh",
        "value": "orbital_meshes parameter (default 'Data/Meshes/Planets/HoudiniPlanets/HoudiniPlanet.nif'; 'none' omits component)",
        "source": "Standard BSGalaxy unit-sphere planet mesh path; XMPM/PCCC omitted (zero whole-record clone; '--orbital-meshes none' staged variant)",
    },
    {
        "subrecord": "BGSKeywordForm_Component/KSIZ+KWDA",
        "field": "trait_keywords",
        "value": list(HOME_PLANET_TRAIT_KEYWORD_EDIDS),
        "source": "Chosen one-by-one breathable/temperate/no-life trait keywords resolved by EditorID",
    },
    {
        "subrecord": "TESFullName_Component/FULL",
        "field": "full_name",
        "value": "planet_name parameter (default 'Earth')",
        "source": "Plain non-localized string parameter",
    },
    {
        "subrecord": "PPBD",
        "field": "planet_biome_entry",
        "value": "100% FO4SFHomeBiome (0x01000806), 0 fauna, 0 flora, 0 resource generation",
        "source": "Our own neutral BIOM record in FO4SFHome.esm (W4)",
    },
    {
        "subrecord": "FNAM (top-level)",
        "field": "surface_tree",
        "value": "surface_tree parameter (default 'none' = omitted; 'ours_empty' -> FO4SFHomeSurfaceTree 0x0100080B; control 'EarthSurfaceTree')",
        "source": "Omitted by default so zero Starfield SFTR/SFPT procedural surface tree attaches (WB2)",
    },
    {
        "subrecord": "GNAM (top-level)",
        "field": "albedo_scalar",
        "value": 0.56,
        "source": "Terrestrial bond/visual albedo float",
    },
    {
        "subrecord": "BDST..BDED/ANAM",
        "field": "body_name",
        "value": "body_name parameter (default 'fo4sf_home_earth'; control 'Earth'; drives planetdata/biomemaps/<anam_lower>.biom)",
        "source": "Non-colliding internal body name parameter matched to staged .biom path so vanilla earth.biom cannot be picked up (HUD FULL stays planet_name 'Earth') (C9)",
    },
    {
        "subrecord": "BDST..BDED/CNAM",
        "field": "body_class",
        "value": 2,
        "source": "Starfield rocky terrestrial body type enum (2 = Rock)",
    },
    {
        "subrecord": "BDST..BDED/DNAM",
        "field": "unique_space_cell",
        "value": "0x00000000 + 0x00",
        "source": "Cleared so zero Starfield space cell attaches to our planet",
    },
    {
        "subrecord": "BDST..BDED/ENAM",
        "field": "orbital_data_72b",
        "value": {
            "major_axis_km": 149598000.0,
            "minor_axis_km": 149577100.0,
            "aphelion_km": 152097700.0,
            "eccentricity": 0.016709,
            "incline_rad": 0.0,
            "mean_orbit_km": 149598000.0,
            "axial_tilt_rad": 0.4090926,
            "rotational_velocity": 1.0,
            "start_angle": 0.0,
            "perihelion_angle": 0.0,
            "apply_orbital_velocity": 1,
            "geostationary": 0,
        },
        "source": "Earth 1 AU orbital constants (~149,598,000 km, e=0.016709, 23.44 deg tilt, 24 h rotation=1.0)",
    },
    {
        "subrecord": "BDST..BDED/FNAM",
        "field": "orbited_data_24b",
        "value": {
            "gravity_well": 1495471000.0,
            "mass_kg": 5.972e24,
            "radius_km": 6371.0,
            "surface_gravity_g": 1.0,
            "flags": 0xD7,
        },
        "source": "Earth physical constants (mass 5.972e24 kg, radius 6371.0 km, surface gravity 1.0 g)",
    },
    {
        "subrecord": "BDST..BDED/GNAM",
        "field": "galaxy_ids_12b",
        "value": "(system_id, 0, planet_id)",
        "source": "Census-verified unused (system_id, planet_id) tuple",
    },
    {
        "subrecord": "BDST..BDED/HNAM",
        "field": "planet_details_catalogue",
        "value": "G2 / FO4SFHome / Yes / Strong / 5.97E+24 / Rock / 365 d / temp_c",
        "source": "Synthesised PlanetDetails struct with zero Sol/Starfield strings",
    },
    {
        "subrecord": "BDST..BDED/INAM",
        "field": "atmosphere_data_16b",
        "value": {
            "atmosphere": "sky_atmo parameter (default 'ours' -> FO4SFHomeAtmosphere 0x01000809; controls ATMO_Jemison | ATMO_Earth)",
            "rayleigh": 0.25,
            "mie": 0.0025,
            "scale_height": 0.001,
        },
        "source": "Our own standalone BETH v8 REFL ATMO record in FO4SFHome.esm by default (WB1; zero Starfield ATMO references)",
    },
    {
        "subrecord": "BDST..BDED/KNAM",
        "field": "rings_and_day_length_29b",
        "value": {"rings": "", "day_length_days": 1.0},
        "source": "No planetary rings, 1.0 Earth day (24.0 h)",
    },
    {
        "subrecord": "BDST..BDED/NNAM",
        "field": "body_sentinel_u32",
        "value": "0x80000000",
        "source": "Standard PNDT body end sentinel",
    },
    {
        "subrecord": "TEMP",
        "field": "temperature_celsius",
        "value": "temp_c parameter (default 15.0 C)",
        "source": "Temperate Earth mean surface temperature parameter (15.0 C)",
    },
    {
        "subrecord": "DENS",
        "field": "density_g_cm3",
        "value": 5.51,
        "source": "Earth bulk density physical constant (5.51 g/cm^3)",
    },
    {
        "subrecord": "PHLA",
        "field": "perihelion_longitude_deg",
        "value": 335.0,
        "source": "Orbital longitude scalar (degrees)",
    },
    {
        "subrecord": "RSCS",
        "field": "resource_seed_u32",
        "value": 0,
        "source": "Zeroed resource seed (no procedural resource deposits)",
    },
)

BIOM_FIELD_SPEC: Tuple[Dict[str, Any], ...] = (
    {
        "subrecord": "EDID+FULL",
        "field": "biome_identity",
        "value": f"{DEFAULT_BIOME_EDID} / '{DEFAULT_BIOME_NAME}'",
        "source": "Our own neutral BIOM record in FO4SFHome.esm (W4)",
    },
    {
        "subrecord": "ENAM",
        "field": "climate",
        "value": "climate parameter (default 'ours' -> FO4SFHomeClimate 0x01000808 + FO4SFHomeClearWeather 0x01000807; control ClimateUniqueNewAtlantis)",
        "source": "Our own clear temperate CLMT + WTHR in FO4SFHome.esm by default (WB1; zero Starfield climate/weather references)",
    },
    {
        "subrecord": "MNAM+WNAM+YNAM+UNAM+CNAM+BMC1..3+TNAM",
        "field": "biome_scalars",
        "value": "MNAM=0x00, WNAM/YNAM/UNAM=1.0, neutral earth-brown map colors, TNAM=0",
        "source": "Neutral terrestrial scalar defaults (zero gas-giant flag)",
    },
    {
        "subrecord": "NNAM",
        "field": "terrain_pattern_style",
        "value": "pattern_style parameter (default PatternStyleFieldsHillsFieldsFlat, 38.11 m smallest height range; control PatternStyleHillsRockyFieldsRocky, 372.61 m)",
        "source": "Smallest-relief PTST in Starfield.esm (46/46 PTST records hold only EDID over 258 SFPT->SFBK .btd tiles) (WB2)",
    },
    {
        "subrecord": "LNAM[0..6]",
        "field": "land_textures_and_ground_cover",
        "value": "Slots 0..6 -> FO4SFHomeGroundDirt01 (0x0100080A, converted FO4 dirt .mat + .dds; control LDirtFootprints01), ground_cover = 0x00000000",
        "source": "Our own Fallout 4 converted LTEX record in FO4SFHome.esm across all 7 slots with zero GCVR grass (WB2)",
    },
    {
        "subrecord": "BTPS+BDFS",
        "field": "terrain_shader_and_distance_fade",
        "value": "56-float UV scale table + 11-float distance fade table",
        "source": "Standard Starfield BIOM terrain shader UV/fade constants",
    },
    {
        "subrecord": "NAM2+NAM3+NAM4",
        "field": "pcm_biome_density_globals",
        "value": "PCM_BiomeDensity_None",
        "source": "Starfield.esm GLOB PCM_BiomeDensity_None resolved by EditorID (zero procedural POI density)",
    },
    {
        "subrecord": "GNAM / NAM1",
        "field": "procedural_objects_and_resources",
        "value": "0 GNAM entries, 0 NAM1 resource entries",
        "source": "Omitted so zero Starfield flora, rocks, structures, or resources can spawn",
    },
)


def _wstr32(text: str) -> bytes:
    b = text.encode("cp1252") + b"\0"
    return struct.pack("<I", len(b)) + b


def _bstr32(text: str) -> bytes:
    b = text.encode("cp1252")
    return struct.pack("<I", len(b)) + b


def resolve_edids_in_group(sf: esm.Plugin, group: str, wanted_edids: Sequence[str]) -> Dict[str, int]:
    """Resolve `wanted_edids` (case-insensitive) to 32-bit `Starfield.esm` FormIDs within top group `group`."""
    want_map = {w.lower(): w for w in wanted_edids}
    found: Dict[str, int] = {}
    for rec in sf.records(group, [group.encode("ascii")]):
        low = rec.edid.lower()
        if low in want_map:
            found[want_map[low]] = rec.formid & 0xFFFFFF
            if len(found) == len(want_map):
                break
    return found


def resolve_home_references(
    sf: esm.Plugin,
    sky_atmo: str = DEFAULT_SKY_ATMO,
    lever_keywords: Sequence[str] = (),
    *,
    climate: str = DEFAULT_CLIMATE,
    ground_ltex: str = DEFAULT_GROUND_LTEX,
    pattern_style: str = DEFAULT_TERRAIN_PATTERN,
    surface_tree: str = DEFAULT_SURFACE_TREE,
    sun_preset: str = DEFAULT_SUN_PRESET,
    wb3_mode: str = DEFAULT_WB3_MODE,
) -> Dict[str, Any]:
    """Resolve every `Starfield.esm` record needed by `FO4SFHome.esm` and `FO4TerrainCore_Home.esm` by EditorID,
    while binding our own `FO4SFHome.esm` local FormIDs (`0x01000807..0x0100080D`) when `ours` options are selected."""
    if sf.masters:
        raise records.PlanetError(f"{sf.path} has masters {sf.masters}: expected Starfield.esm itself")
    if sky_atmo not in SKY_ATMO_CHOICES:
        raise records.PlanetError(f"sky_atmo {sky_atmo!r} must be one of {SKY_ATMO_CHOICES}")
    if climate not in CLIMATE_CHOICES:
        raise records.PlanetError(f"climate {climate!r} must be one of {CLIMATE_CHOICES}")
    if ground_ltex not in GROUND_LTEX_CHOICES:
        raise records.PlanetError(f"ground_ltex {ground_ltex!r} must be one of {GROUND_LTEX_CHOICES}")
    if pattern_style not in TERRAIN_PATTERN_CHOICES:
        raise records.PlanetError(f"pattern_style {pattern_style!r} must be one of {TERRAIN_PATTERN_CHOICES}")
    if surface_tree not in SURFACE_TREE_CHOICES:
        raise records.PlanetError(f"surface_tree {surface_tree!r} must be one of {SURFACE_TREE_CHOICES}")
    if sun_preset not in SUN_PRESET_CHOICES:
        raise records.PlanetError(f"sun_preset {sun_preset!r} must be one of {SUN_PRESET_CHOICES}")
    if wb3_mode not in WB3_MODE_CHOICES:
        raise records.PlanetError(f"wb3_mode {wb3_mode!r} must be one of {WB3_MODE_CHOICES}")

    for lev in lever_keywords:
        if lev not in LEVER_KEYWORD_EDIDS:
            raise records.PlanetError(f"unknown lever keyword {lev!r}; expected one of {LEVER_KEYWORD_EDIDS}")

    kw_names = records.keyword_edids(sf)
    by_kw_edid = {ed.lower(): fid & 0xFFFFFF for fid, ed in kw_names.items() if ed}

    needed_kws = (
        list(records.KEYWORDS.keys())
        + ["Star_Class_G"]
        + list(HOME_PLANET_TRAIT_KEYWORD_EDIDS)
        + list(lever_keywords)
    )
    resolved_kws: Dict[str, int] = {}
    for name in dict.fromkeys(needed_kws):
        fid = by_kw_edid.get(name.lower())
        if fid is None:
            raise records.PlanetError(f"Starfield.esm is missing required KYWD {name!r}")
        resolved_kws[name] = fid

    forbidden_fids = {
        name: by_kw_edid[name.lower()]
        for name in FORBIDDEN_PLANET_KEYWORD_EDIDS
        if name.lower() in by_kw_edid
    }

    locs = resolve_edids_in_group(sf, "LCTN", [records.UNIVERSE_EDID])
    if records.UNIVERSE_EDID not in locs:
        raise records.PlanetError(f"Starfield.esm is missing LCTN {records.UNIVERSE_EDID!r}")

    own_master = lambda loc_id: (1 << 24) | loc_id  # noqa: E731

    if sky_atmo == "ours":
        atmo_edid = wb_records.DEFAULT_ATMO_EDID
        atmo_fid = own_master(HOME_ATMO)
    else:
        atmos = resolve_edids_in_group(sf, "ATMO", [sky_atmo])
        if sky_atmo not in atmos:
            raise records.PlanetError(f"Starfield.esm is missing ATMO {sky_atmo!r}")
        atmo_edid = sky_atmo
        atmo_fid = atmos[sky_atmo]

    if sun_preset == "ours":
        sun_preset_edid = wb_records.DEFAULT_SUN_PRESET_EDID
        sun_preset_fid = own_master(HOME_SUN_PRESET)
    else:
        sunps = resolve_edids_in_group(sf, "SUNP", ["SunPresetTypeG2"])
        if "SunPresetTypeG2" not in sunps:
            raise records.PlanetError("Starfield.esm is missing SUNP 'SunPresetTypeG2'")
        sun_preset_edid = "SunPresetTypeG2"
        sun_preset_fid = sunps["SunPresetTypeG2"]

    if surface_tree == "none":
        surface_tree_edid = "none"
        surface_tree_fid: Optional[int] = None
    elif surface_tree == "ours_empty":
        surface_tree_edid = wb_records.DEFAULT_SURFACE_TREE_EDID
        surface_tree_fid = own_master(HOME_SURFACE_TREE)
    else:
        sftrs = resolve_edids_in_group(sf, "SFTR", ["EarthSurfaceTree"])
        if "EarthSurfaceTree" not in sftrs:
            raise records.PlanetError("Starfield.esm is missing SFTR 'EarthSurfaceTree'")
        surface_tree_edid = "EarthSurfaceTree"
        surface_tree_fid = sftrs["EarthSurfaceTree"]

    matt_dirt_fid: Optional[int] = None
    if ground_ltex == "ours":
        matts = resolve_edids_in_group(sf, "MATT", ["MaterialDirtlSand"])
        if "MaterialDirtlSand" not in matts:
            raise records.PlanetError("Starfield.esm is missing MATT 'MaterialDirtlSand'")
        matt_dirt_fid = matts["MaterialDirtlSand"]
        ground_ltex_edid = wb_records.DEFAULT_GROUND_LTEX_EDID
        ground_ltex_fid = own_master(HOME_GROUND_LTEX)
    else:
        ltexs = resolve_edids_in_group(sf, "LTEX", ["LDirtFootprints01"])
        if "LDirtFootprints01" not in ltexs:
            raise records.PlanetError("Starfield.esm is missing LTEX 'LDirtFootprints01'")
        ground_ltex_edid = "LDirtFootprints01"
        ground_ltex_fid = ltexs["LDirtFootprints01"]

    if climate in ("ours", "ours_empty"):
        clmt_edid = wb_records.DEFAULT_CLIMATE_EDID
        clmt_fid = own_master(HOME_CLIMATE)
    else:
        clmts = resolve_edids_in_group(sf, "CLMT", [climate, "DefaultClimate"])
        clmt_fid = clmts.get(climate) or clmts.get("DefaultClimate")
        if clmt_fid is None:
            raise records.PlanetError(f"Starfield.esm is missing CLMT {climate!r} and 'DefaultClimate'")
        clmt_edid = climate if climate in clmts else "DefaultClimate"

    ptsts = resolve_edids_in_group(sf, "PTST", [pattern_style])
    if pattern_style not in ptsts:
        raise records.PlanetError(f"Starfield.esm is missing PTST {pattern_style!r}")

    globs = resolve_edids_in_group(sf, "GLOB", ["PCM_BiomeDensity_None"])
    if "PCM_BiomeDensity_None" not in globs:
        raise records.PlanetError("Starfield.esm is missing GLOB 'PCM_BiomeDensity_None'")

    silent_music_fid: Optional[int] = None
    if wb3_mode == "ours":
        muscs = resolve_edids_in_group(sf, "MUSC", ["_NONE"])
        if "_NONE" not in muscs:
            raise records.PlanetError("Starfield.esm is missing MUSC '_NONE'")
        silent_music_fid = muscs["_NONE"]

    return {
        "keywords": resolved_kws,
        "forbidden_keywords": forbidden_fids,
        "universe_lctn": locs[records.UNIVERSE_EDID],
        "atmo_edid": atmo_edid,
        "atmo_fid": atmo_fid,
        "sun_preset_edid": sun_preset_edid,
        "sun_preset_fid": sun_preset_fid,
        "surface_tree_edid": surface_tree_edid,
        "surface_tree_fid": surface_tree_fid,
        "ground_ltex_edid": ground_ltex_edid,
        "ground_ltex_fid": ground_ltex_fid,
        "matt_dirt_fid": matt_dirt_fid,
        "climate_edid": clmt_edid,
        "climate_fid": clmt_fid,
        "pattern_style_edid": pattern_style,
        "pattern_style_fid": ptsts[pattern_style],
        "biome_density_none_fid": globs["PCM_BiomeDensity_None"],
        "silent_music_fid": silent_music_fid,
    }


def free_system_and_planet_ids(
    sf: esm.Plugin,
    data_dir: Optional[str] = None,
    preferred_system_id: int = DEFAULT_HOME_SYSTEM_ID,
    preferred_planet_id: int = DEFAULT_HOME_PLANET_ID,
    star_offset_pc: Tuple[float, float, float] = DEFAULT_STAR_OFFSET_PC,
) -> Dict[str, Any]:
    """Scan `Starfield.esm` and every plugin in `data_dir` (read-only) to select an unused `(system_id, planet_id)`
    and an isolated parsec map position (`>= 0.5 pc` from every star)."""
    skip = ("starfield.esm", HOME_MASTER.lower(), HOME_REGISTRATION.lower()) + census.OWN_PLUGINS
    bodies = (
        census.plugin_bodies(data_dir, skip=skip)
        if data_dir
        else {
            "stars": [],
            "planets": [],
            "locations": [],
            "overlays": [],
            "read": [],
            "unreadable": [],
        }
    )

    used_systems: Dict[int, List[str]] = {}
    taken_positions: List[Tuple[float, float, float]] = []

    sol_pos = (0.0, 0.0, 0.0)
    for fid, edid, name, sid, pos in records.stars(sf):
        if sid is not None:
            used_systems.setdefault(sid, []).append(f"Starfield.esm:{edid or records.fid_hex(fid)}")
        if pos is not None:
            taken_positions.append(pos)
            if name.lower() == "sol":
                sol_pos = pos

    for _, edid, name, g in records.planets(sf):
        if g is not None and g[0] < records.ID_UNSET:
            used_systems.setdefault(g[0], []).append(f"Starfield.esm:{edid or name}")

    for r in sf.records("LCTN", [b"LCTN"]):
        x, _y = records.location_ids(r)
        if x is not None and x >= 0:
            used_systems.setdefault(x, []).append(f"Starfield.esm:{r.edid}")

    for src, edid, sid, _pid in census.overlay_worlds(sf, "Starfield.esm"):
        if sid is not None and sid >= 0:
            used_systems.setdefault(sid, []).append(f"{src}:{edid}")

    for src, sid, pos in bodies["stars"]:
        if sid is not None:
            used_systems.setdefault(sid, []).append(src)
        if pos is not None:
            taken_positions.append(tuple(pos))

    for src, edid, name, g, _new in bodies["planets"]:
        if g is not None and g[0] < records.ID_UNSET:
            used_systems.setdefault(g[0], []).append(f"{src}:{edid or name}")

    for src, edid, x, _y, *_rest in bodies["locations"]:
        if x is not None and x >= 0:
            used_systems.setdefault(x, []).append(f"{src}:{edid}")

    for src, edid, sid, _pid in bodies["overlays"]:
        if sid is not None and sid >= 0:
            used_systems.setdefault(sid, []).append(f"{src}:{edid}")

    if preferred_system_id not in used_systems and 0 < preferred_system_id < records.ID_UNSET:
        system_id = preferred_system_id
    else:
        finite_ids = [s for s in used_systems if 0 <= s < records.ID_UNSET]
        system_id = (max(finite_ids) + 1) if finite_ids else preferred_system_id
        while system_id in used_systems:
            system_id += 1

    if not (0 < preferred_planet_id < records.ID_UNSET):
        raise records.PlanetError(f"preferred_planet_id {preferred_planet_id} out of range")
    planet_id = preferred_planet_id

    position_pc, nearest_star_pc = records.free_position(sol_pos, taken_positions, offset=star_offset_pc)
    return {
        "system_id": system_id,
        "planet_id": planet_id,
        "position_pc": list(position_pc),
        "nearest_star_pc": nearest_star_pc,
        "used_system_count": len(used_systems),
        "stars_checked": len(taken_positions),
        "plugins_read": bodies["read"],
        "plugins_unreadable": bodies["unreadable"],
    }


def build_home_biome(formid: int, refs: Dict[str, Any], edid: str = DEFAULT_BIOME_EDID,
                     name: str = DEFAULT_BIOME_NAME) -> esm.Record:
    """Author our own neutral `BIOM` record (`0x806`) from `BIOM_FIELD_SPEC` with zero procedural flora/fauna/rocks."""
    btps_floats: List[float] = []
    for slot in range(6):
        scale = (5 - slot) / 6.0
        btps_floats.extend([scale, scale, 1.0, 1.0, 0.0, 1.0, 0.0, 1.0])
    btps_floats.extend([0.0] * 8)
    btps = struct.pack("<56f", *btps_floats)
    bdfs = struct.pack("<11f", 0.2, 0.1, 0.003125, 0.003125, 0.0, 1.0, 0.0, 1.0, 0.6, 0.1, 0.25)

    ltex = refs["ground_ltex_fid"]
    density_none = refs["biome_density_none_fid"]

    subs: List[Tuple[bytes, bytes]] = [
        (b"EDID", esm.zbytes(edid)),
        (b"FULL", esm.zbytes(name)),
        (b"ENAM", struct.pack("<I", refs["climate_fid"])),
        (b"MNAM", b"\x00"),
        (b"WNAM", struct.pack("<f", 1.0)),
        (b"YNAM", struct.pack("<f", 1.0)),
        (b"UNAM", struct.pack("<f", 1.0)),
        (b"NNAM", struct.pack("<I", refs["pattern_style_fid"])),
        (b"CNAM", bytes([0x8C, 0x82, 0x74, 0xFF])),
        (b"BMC1", bytes([0x8C, 0x82, 0x74, 0xFF])),
        (b"BMC2", bytes([0x6E, 0x66, 0x5A, 0xFF])),
        (b"BMC3", bytes([0x50, 0x4A, 0x42, 0xFF])),
        (b"TNAM", struct.pack("<I", 0)),
    ]
    for slot in range(7):
        subs.append((b"LNAM", struct.pack("<III", slot, ltex, 0)))
    subs.extend(
        [
            (b"BTPS", btps),
            (b"BDFS", bdfs),
            (b"NAM2", struct.pack("<I", density_none)),
            (b"NAM3", struct.pack("<I", density_none)),
            (b"NAM4", struct.pack("<I", density_none)),
        ]
    )
    return esm.Record(b"BIOM", formid, subs, flags=0, vc=0, version=FORM_VERSION, unknown=0)


def build_home_star(
    formid: int,
    system_id: int,
    position_pc: Sequence[float],
    refs: Dict[str, Any],
    star_name: str = DEFAULT_STAR_NAME,
    orbital_meshes: str = DEFAULT_ORBITAL_MESHES,
) -> esm.Record:
    """Author our own isolated `STDT` record (`0x800`) from `STAR_FIELD_SPEC` with zero `PCCC`/`XMPM` copy."""
    if orbital_meshes not in ORBITAL_MESHES_CHOICES:
        raise records.PlanetError(f"orbital_meshes {orbital_meshes!r} must be one of {ORBITAL_MESHES_CHOICES}")
    if len(position_pc) != 3 or not all(math.isfinite(v) for v in position_pc):
        raise records.PlanetError(f"invalid star position {position_pc!r}")
    star_tag = records.tag(star_name)
    edid = f"{star_tag}Star" if not star_tag.lower().endswith("star") else star_tag
    orbited_data = struct.pack("<dfff", 0.0, 1.9885e30, 696300.0, 1.0)
    star_data = (
        _bstr32(star_tag[:8].upper())
        + _bstr32("G2")
        + struct.pack("<ffffIII", 4.85, 1.9885e30, 0.75, 1.76, 0, 0, 5830)
    )
    kw_g = refs["keywords"]["Star_Class_G"]
    model_comp: List[Tuple[bytes, bytes]] = (
        [
            (b"BFCB", esm.zbytes("TESPlanetModel_Component")),
            (b"MODL", esm.zbytes("Data/Meshes/Planets/HoudiniPlanets/HoudiniPlanet_star.nif")),
            (b"FLLD", struct.pack("<I", 1)),
            (b"BFCE", b""),
        ]
        if orbital_meshes == "starfield"
        else []
    )
    subs: List[Tuple[bytes, bytes]] = [
        (b"EDID", esm.zbytes(edid)),
        (b"BFCB", esm.zbytes("BGSOrbitedDataComponent_Component")),
        (b"DATA", orbited_data),
        (b"BFCE", b""),
        (b"BFCB", esm.zbytes("BGSStarDataComponent_Component")),
        (b"DATA", star_data),
        (b"BFCE", b""),
        *model_comp,
        (b"BFCB", esm.zbytes("TESFullName_Component")),
        (b"FULL", esm.zbytes(star_name)),
        (b"BFCE", b""),
        (b"BFCB", esm.zbytes("TESModel_Component")),
        (b"FLLD", struct.pack("<I", 1)),
        (b"BFCE", b""),
        (b"KSIZ", struct.pack("<I", 1)),
        (b"KWDA", struct.pack("<I", kw_g)),
        (b"ANAM", esm.zbytes(star_name)),
        (b"BNAM", struct.pack("<3f", float(position_pc[0]), float(position_pc[1]), float(position_pc[2]))),
        (b"DNAM", struct.pack("<I", system_id)),
        (b"ENAM", struct.pack("<I", 0xFFEDFCFC)),
        (b"PNAM", struct.pack("<I", refs["sun_preset_fid"])),
    ]
    return esm.Record(b"STDT", formid, subs, flags=0, vc=0, version=FORM_VERSION, unknown=0)


def build_home_planet(
    formid: int,
    biome_formid: int,
    system_id: int,
    planet_id: int,
    refs: Dict[str, Any],
    planet_name: str = DEFAULT_PLANET_NAME,
    body_name: str = DEFAULT_BODY_NAME,
    star_name: str = DEFAULT_STAR_NAME,
    temp_c: float = DEFAULT_TEMP_C,
    orbital_meshes: str = DEFAULT_ORBITAL_MESHES,
) -> esm.Record:
    """Author our own `PNDT` record (`0x805`) from `PLANET_FIELD_SPEC` with zero whole-record copy."""
    if orbital_meshes not in ORBITAL_MESHES_CHOICES:
        raise records.PlanetError(f"orbital_meshes {orbital_meshes!r} must be one of {ORBITAL_MESHES_CHOICES}")
    clean_body = body_name.strip()
    if not clean_body or "/" in clean_body or "\\" in clean_body:
        raise records.PlanetError(f"invalid body_name {body_name!r}")
    planet_tag = records.tag(planet_name)
    star_tag = records.tag(star_name)
    edid = f"{planet_tag}PlanetData"
    trait_fids = [refs["keywords"][k] for k in HOME_PLANET_TRAIT_KEYWORD_EDIDS]

    ppbd = records.pack_biome(
        {
            "biome": biome_formid,
            "chance": 100.0,
            "unknown": 0,
            "resource_generation": 0,
            "fauna": [],
            "keywords": [],
            "flora_entry_size": 9,
            "flora": [],
            "extra": [],
        }
    )

    enam_orbital = struct.pack(
        "<6d4fBB6x",
        149598000.0,
        149577100.0,
        152097700.0,
        0.016709,
        0.0,
        149598000.0,
        0.4090926,
        1.0,
        0.0,
        0.0,
        1,
        0,
    )
    fnam_orbited = struct.pack("<d3fI", 1495471000.0, 5.972e24, 6371.0, 1.0, 0xD7)
    gnam_galaxy = struct.pack("<III", system_id, 0, planet_id)

    hnam_details = (
        struct.pack("<I", 0)
        + _wstr32("G2")
        + _wstr32(star_tag)
        + _wstr32("Yes")
        + _wstr32("Strong")
        + _wstr32("5.97E+24")
        + _wstr32("Rock")
        + _wstr32(star_tag)
        + struct.pack(
            "<dddffffffiffdfI",
            0.0,
            149598000.0,
            0.0,
            5.51,
            8.0,
            27.0,
            0.75,
            1.76,
            335.0,
            -2,
            354.0,
            365.0,
            0.0,
            float(temp_c),
            0,
        )
    )
    inam_atmo = struct.pack("<I3f", refs["atmo_fid"], 0.25, 0.0025, 0.001)
    knam_rings = struct.pack("<IddBII", 0, 0.0, 1.0, 0, 0, 0)

    model_comp: List[Tuple[bytes, bytes]] = (
        [
            (b"BFCB", esm.zbytes("TESPlanetModel_Component")),
            (b"MODL", esm.zbytes("Data/Meshes/Planets/HoudiniPlanets/HoudiniPlanet.nif")),
            (b"FLLD", struct.pack("<I", 1)),
            (b"BFCE", b""),
        ]
        if orbital_meshes == "starfield"
        else []
    )
    sftr_sub: List[Tuple[bytes, bytes]] = (
        [(b"FNAM", struct.pack("<I", refs["surface_tree_fid"]))]
        if refs["surface_tree_fid"] is not None
        else []
    )

    subs: List[Tuple[bytes, bytes]] = [
        (b"EDID", esm.zbytes(edid)),
        *model_comp,
        (b"BFCB", esm.zbytes("BGSKeywordForm_Component")),
        (b"KSIZ", struct.pack("<I", len(trait_fids))),
        (b"KWDA", struct.pack(f"<{len(trait_fids)}I", *trait_fids)),
        (b"BFCE", b""),
        (b"BFCB", esm.zbytes("TESFullName_Component")),
        (b"FULL", esm.zbytes(planet_name)),
        (b"BFCE", b""),
        (b"BFCB", esm.zbytes("TESModel_Component")),
        (b"FLLD", struct.pack("<I", 1)),
        (b"BFCE", b""),
        (b"PPBD", ppbd),
        *sftr_sub,
        (b"GNAM", struct.pack("<f", 0.56)),
        (b"BDST", b""),
        (b"ANAM", esm.zbytes(clean_body)),
        (b"CNAM", bytes([2])),
        (b"DNAM", struct.pack("<I", 0) + b"\0"),
        (b"ENAM", enam_orbital),
        (b"FNAM", fnam_orbited),
        (b"GNAM", gnam_galaxy),
        (b"HNAM", hnam_details),
        (b"INAM", inam_atmo),
        (b"KNAM", knam_rings),
        (b"NNAM", struct.pack("<I", 0x80000000)),
        (b"BDED", b""),
        (b"TEMP", struct.pack("<f", float(temp_c))),
        (b"DENS", struct.pack("<f", 5.51)),
        (b"PHLA", struct.pack("<f", 335.0)),
        (b"RSCS", struct.pack("<I", 0)),
    ]
    return esm.Record(b"PNDT", formid, subs, flags=0, vc=0, version=FORM_VERSION, unknown=0)


def build_home_master(
    sf: esm.Plugin,
    data_dir: Optional[str] = None,
    star_name: str = DEFAULT_STAR_NAME,
    planet_name: str = DEFAULT_PLANET_NAME,
    body_name: str = DEFAULT_BODY_NAME,
    temp_c: float = DEFAULT_TEMP_C,
    sky_atmo: str = DEFAULT_SKY_ATMO,
    lever_keywords: Sequence[str] = (),
    system_id: Optional[int] = None,
    planet_id: Optional[int] = None,
    star_offset_pc: Tuple[float, float, float] = DEFAULT_STAR_OFFSET_PC,
    *,
    climate: str = DEFAULT_CLIMATE,
    ground_ltex: str = DEFAULT_GROUND_LTEX,
    pattern_style: str = DEFAULT_TERRAIN_PATTERN,
    surface_tree: str = DEFAULT_SURFACE_TREE,
    sun_preset: str = DEFAULT_SUN_PRESET,
    orbital_meshes: str = DEFAULT_ORBITAL_MESHES,
    wb3_mode: str = DEFAULT_WB3_MODE,
) -> Tuple[esm.PluginWriter, Dict[str, Any]]:
    """Build `FO4SFHome.esm` (`STDT 0x800`, `LCTN 0x801..0x804`, `PNDT 0x805`, `BIOM 0x806`, plus our `WB1`–`WB3`
    `WTHR`/`CLMT`/`ATMO`/`LTEX`/`SFTR`/`WATR`/`SUNP` records when selected) and return `(writer, report)`."""
    refs = resolve_home_references(
        sf,
        sky_atmo=sky_atmo,
        lever_keywords=lever_keywords,
        climate=climate,
        ground_ltex=ground_ltex,
        pattern_style=pattern_style,
        surface_tree=surface_tree,
        sun_preset=sun_preset,
        wb3_mode=wb3_mode,
    )
    free_info = free_system_and_planet_ids(
        sf,
        data_dir=data_dir,
        preferred_system_id=system_id if system_id is not None else DEFAULT_HOME_SYSTEM_ID,
        preferred_planet_id=planet_id if planet_id is not None else DEFAULT_HOME_PLANET_ID,
        star_offset_pc=star_offset_pc,
    )
    if system_id is not None and free_info["system_id"] != system_id:
        raise records.PlanetError(f"requested system_id {system_id:#x} is already in use")
    sid = free_info["system_id"]
    pid = free_info["planet_id"]
    pos_pc = free_info["position_pc"]

    w = esm.PluginWriter(["Starfield.esm"], esm.ESM)
    own = w.own

    kw = refs["keywords"]
    star_tag = records.tag(star_name)
    planet_tag = records.tag(planet_name)
    sys_edid = f"S{star_tag}"
    pl_edid = f"{sys_edid}_P{planet_tag}"

    surface_kws = [kw["LocTypeSurface"]]
    for lev in lever_keywords:
        kfid = kw[lev]
        if kfid not in surface_kws:
            surface_kws.append(kfid)

    star_rec = build_home_star(own(STAR), sid, pos_pc, refs, star_name=star_name, orbital_meshes=orbital_meshes)
    sys_loc = records.new_location(own(SYSTEM_LOC), sys_edid, star_name, [kw["LocTypeStarSystem"]], refs["universe_lctn"], sid, 0, version=FORM_VERSION)
    pl_loc = records.new_location(own(PLANET_LOC), pl_edid, planet_name, [kw["LocTypePlanet"], kw["LocTypeMajorOrbital"]], own(SYSTEM_LOC), sid, pid, version=FORM_VERSION)
    orb_loc = records.new_location(own(ORBIT_LOC), f"{pl_edid}_Orbit", planet_name, [kw["LocTypeOrbit"]], own(PLANET_LOC), sid, pid, version=FORM_VERSION)
    surf_loc = records.new_location(own(SURFACE_LOC), f"{pl_edid}_Surface", planet_name, surface_kws, own(PLANET_LOC), sid, pid, version=FORM_VERSION)
    biome_rec = build_home_biome(own(BIOME), refs)
    planet_rec = build_home_planet(
        own(PLANET),
        own(BIOME),
        sid,
        pid,
        refs,
        planet_name=planet_name,
        body_name=body_name,
        star_name=star_name,
        temp_c=temp_c,
        orbital_meshes=orbital_meshes,
    )

    for rec in (star_rec, sys_loc, pl_loc, orb_loc, surf_loc, biome_rec, planet_rec):
        w.add(rec)

    authored_wb_records: Dict[str, str] = {}
    if climate == "ours":
        wthr_rec = wb_records.build_home_weather(own(HOME_WEATHER))
        clmt_rec = wb_records.build_home_climate(own(HOME_CLIMATE), weather_formid=own(HOME_WEATHER))
        w.add(wthr_rec)
        w.add(clmt_rec)
        authored_wb_records["WTHR"] = records.fid_hex(wthr_rec.formid)
        authored_wb_records["CLMT"] = records.fid_hex(clmt_rec.formid)
    elif climate == "ours_empty":
        clmt_rec = wb_records.build_home_climate(own(HOME_CLIMATE), weather_formid=None)
        w.add(clmt_rec)
        authored_wb_records["CLMT"] = records.fid_hex(clmt_rec.formid)

    if sky_atmo == "ours":
        atmo_rec = wb_records.build_home_atmosphere(own(HOME_ATMO))
        w.add(atmo_rec)
        authored_wb_records["ATMO"] = records.fid_hex(atmo_rec.formid)

    if ground_ltex == "ours":
        assert refs["matt_dirt_fid"] is not None
        ltex_rec = wb_records.build_home_ground_ltex(own(HOME_GROUND_LTEX), refs["matt_dirt_fid"])
        w.add(ltex_rec)
        authored_wb_records["LTEX"] = records.fid_hex(ltex_rec.formid)

    if surface_tree == "ours_empty":
        sftr_rec = wb_records.build_home_empty_surface_tree(own(HOME_SURFACE_TREE))
        w.add(sftr_rec)
        authored_wb_records["SFTR"] = records.fid_hex(sftr_rec.formid)

    if wb3_mode == "ours":
        watr_rec = wb_records.build_home_water(own(HOME_WATER))
        w.add(watr_rec)
        authored_wb_records["WATR"] = records.fid_hex(watr_rec.formid)

    if sun_preset == "ours":
        sunp_rec = wb_records.build_home_sun_preset(own(HOME_SUN_PRESET))
        w.add(sunp_rec)
        authored_wb_records["SUNP"] = records.fid_hex(sunp_rec.formid)

    field_sources: Dict[str, Any] = {
        "STDT": list(STAR_FIELD_SPEC),
        "PNDT": list(PLANET_FIELD_SPEC),
        "BIOM": list(BIOM_FIELD_SPEC),
        "WTHR": list(wb_records.WTHR_FIELD_SPEC),
        "CLMT": list(wb_records.CLMT_FIELD_SPEC),
        "ATMO": list(wb_records.ATMO_FIELD_SPEC),
        "LTEX": list(wb_records.LTEX_FIELD_SPEC),
        "WB3_OVERRIDES": list(wb_records.WB3_OVERRIDE_SPEC),
    }

    report = {
        "master": HOME_MASTER,
        "system_id": f"0x{sid:08X}",
        "system_id_int": sid,
        "planet_id": pid,
        "authored_wb_records": authored_wb_records,
        "star": {
            "formid": records.fid_hex(star_rec.formid),
            "edid": star_rec.edid,
            "name": star_name,
            "position_pc": pos_pc,
            "nearest_star_pc": free_info["nearest_star_pc"],
            "sun_preset": f"{refs['sun_preset_edid']} ({records.fid_hex(refs['sun_preset_fid'])})",
            "orbital_meshes": orbital_meshes,
        },
        "planet": {
            "formid": records.fid_hex(planet_rec.formid),
            "edid": planet_rec.edid,
            "name": planet_name,
            "body_name": body_name.strip(),
            "temp_c": float(temp_c),
            "sky_atmo": sky_atmo,
            "sky_atmo_edid": refs["atmo_edid"],
            "sky_atmo_fid": records.fid_hex(refs["atmo_fid"]),
            "surface_tree": surface_tree,
            "surface_tree_fid": records.fid_hex(refs["surface_tree_fid"]) if refs["surface_tree_fid"] is not None else None,
            "orbital_meshes": orbital_meshes,
            "trait_keywords": list(HOME_PLANET_TRAIT_KEYWORD_EDIDS),
        },
        "biome": {
            "formid": records.fid_hex(biome_rec.formid),
            "edid": biome_rec.edid,
            "name": DEFAULT_BIOME_NAME,
            "ground_ltex": f"{refs['ground_ltex_edid']} ({records.fid_hex(refs['ground_ltex_fid'])})",
            "pattern_style": f"{refs['pattern_style_edid']} ({records.fid_hex(refs['pattern_style_fid'])})",
            "pcm_density_global": f"PCM_BiomeDensity_None ({records.fid_hex(refs['biome_density_none_fid'])})",
            "climate": f"{refs['climate_edid']} ({records.fid_hex(refs['climate_fid'])})",
        },
        "locations": {
            "system": {"formid": records.fid_hex(sys_loc.formid), "edid": sys_loc.edid, "parent": records.fid_hex(refs["universe_lctn"])},
            "planet": {"formid": records.fid_hex(pl_loc.formid), "edid": pl_loc.edid, "parent": records.fid_hex(sys_loc.formid)},
            "orbit": {"formid": records.fid_hex(orb_loc.formid), "edid": orb_loc.edid, "parent": records.fid_hex(pl_loc.formid)},
            "surface": {
                "formid": records.fid_hex(surf_loc.formid),
                "edid": surf_loc.edid,
                "parent": records.fid_hex(pl_loc.formid),
                "lever_keywords": list(lever_keywords),
            },
        },
        "census": free_info,
        "field_sources": field_sources,
    }
    return w, report


# ------------------------------------------------------------------------------------------------ W3 registration
def _remap_formid(fid: int, src_self_idx: int, dst_master_idx: int) -> int:
    if (fid >> 24) == src_self_idx:
        return (dst_master_idx << 24) | (fid & 0xFFFFFF)
    return fid


def canonical_formkey(plugin: esm.Plugin, plugin_name: str, formid: int) -> Tuple[str, int]:
    """Resolve `formid` inside `plugin` to `(defining_plugin_lower, local_24bit_id)` (`0` and `0xFFFFFFFF` stay sentinels)."""
    if formid in (0, 0xFFFFFFFF):
        return ("", formid)
    hi = formid >> 24
    lo = formid & 0xFFFFFF
    owner = plugin.masters[hi] if hi < len(plugin.masters) else plugin_name
    return (owner.lower(), lo)


def remap_formid_to_masters(
    formid: int,
    src_plugin: esm.Plugin,
    src_name: str,
    dst_masters: Sequence[str],
) -> int:
    """Remap `formid` from `src_plugin`'s master/self table into `dst_masters`."""
    if formid in (0, 0xFFFFFFFF):
        return formid
    owner_low, lo = canonical_formkey(src_plugin, src_name, formid)
    dst_low = [m.lower() for m in dst_masters]
    if owner_low not in dst_low:
        raise records.PlanetError(
            f"cannot remap FormID {formid:#010x} (owner {owner_low!r}) into masters {list(dst_masters)}"
        )
    return (dst_low.index(owner_low) << 24) | lo


def canonical_lcsr_rows(
    plugin: esm.Plugin,
    plugin_name: str,
    lctn_rec: esm.Record,
) -> List[Tuple[Tuple[str, int], Tuple[str, int], Tuple[str, int], int, int]]:
    """Extract canonical `(lcrt_fk, refr_fk, wrld_fk, grid_u32, tail_u32)` rows from `lctn_rec`'s `LCSR` subrecords."""
    rows: List[Tuple[Tuple[str, int], Tuple[str, int], Tuple[str, int], int, int]] = []
    for data in lctn_rec.all(b"LCSR"):
        if len(data) % 20 != 0:
            raise records.PlanetError(f"{plugin_name} LCTN {lctn_rec.edid} has malformed LCSR length {len(data)}")
        for off in range(0, len(data), 20):
            lcrt, refr, wrld, grid, tail = struct.unpack_from("<5I", data, off)
            rows.append(
                (
                    canonical_formkey(plugin, plugin_name, lcrt),
                    canonical_formkey(plugin, plugin_name, refr),
                    canonical_formkey(plugin, plugin_name, wrld),
                    grid,
                    tail,
                )
            )
    return rows


def remap_lcsr_rows_to_masters(
    src_plugin: esm.Plugin,
    src_name: str,
    lctn_rec: esm.Record,
    dst_masters: Sequence[str],
) -> List[bytes]:
    """Return 20-byte `LCSR` chunks from `lctn_rec` with `lcrt`, `refr`, and `wrld` remapped into `dst_masters`."""
    out: List[bytes] = []
    for data in lctn_rec.all(b"LCSR"):
        if len(data) % 20 != 0:
            raise records.PlanetError(f"{src_name} LCTN {lctn_rec.edid} has malformed LCSR length {len(data)}")
        for off in range(0, len(data), 20):
            lcrt, refr, wrld, grid, tail = struct.unpack_from("<5I", data, off)
            out.append(
                struct.pack(
                    "<5I",
                    remap_formid_to_masters(lcrt, src_plugin, src_name, dst_masters),
                    remap_formid_to_masters(refr, src_plugin, src_name, dst_masters),
                    remap_formid_to_masters(wrld, src_plugin, src_name, dst_masters),
                    grid,
                    tail,
                )
            )
    return out


WORLD_DISPLAY_NAMES: Dict[str, str] = {
    "Commonwealth": "Commonwealth",
    "FarHarbor": "Far Harbor",
    "NukaWorld": "Nuka-World",
}


def _remap_lctn_override(
    src_lctn: esm.Record,
    src_self_idx: int,
    dst_master_idx: int,
    surface_parent_fid: int,
    overlay_kw_fid: int,
    lever_kw_fids: Sequence[int],
    system_id: int,
    planet_id: int,
    extra_lcsr_chunks: Sequence[bytes] = (),
    *,
    wb3_mode: str = "passthrough",
    wb3_display_name: Optional[str] = None,
) -> esm.Record:
    out_fid = _remap_formid(src_lctn.formid, src_self_idx, dst_master_idx)
    kws = [overlay_kw_fid]
    for lk in lever_kw_fids:
        if lk not in kws:
            kws.append(lk)

    merged_lcsr: List[bytes] = []
    seen_lcsr: set[bytes] = set()
    for sig, data in src_lctn.subs:
        if sig == b"LCSR" and len(data) % 20 == 0:
            for off in range(0, len(data), 20):
                lcrt, refr, wrld, grid, tail = struct.unpack_from("<5I", data, off)
                refr = _remap_formid(refr, src_self_idx, dst_master_idx)
                wrld = _remap_formid(wrld, src_self_idx, dst_master_idx)
                row_b = struct.pack("<5I", lcrt, refr, wrld, grid, tail)
                if row_b not in seen_lcsr:
                    merged_lcsr.append(row_b)
                    seen_lcsr.add(row_b)
    for row_b in extra_lcsr_chunks:
        if row_b not in seen_lcsr:
            merged_lcsr.append(row_b)
            seen_lcsr.add(row_b)

    new_subs: List[Tuple[bytes, bytes]] = []
    saw_ksiz = saw_kwda = saw_pnam = saw_full = saw_data = emitted_lcsr = False
    for sig, data in src_lctn.subs:
        if sig == b"LCSR" and len(data) % 20 == 0:
            if not emitted_lcsr and merged_lcsr:
                new_subs.append((b"LCSR", b"".join(merged_lcsr)))
                emitted_lcsr = True
        elif sig == b"LCPR" and len(data) % 16 == 0:
            chunks = []
            for off in range(0, len(data), 16):
                actor, loc, grid, tail = struct.unpack_from("<4I", data, off)
                actor = _remap_formid(actor, src_self_idx, dst_master_idx)
                loc = _remap_formid(loc, src_self_idx, dst_master_idx)
                chunks.append(struct.pack("<4I", actor, loc, grid, tail))
            new_subs.append((sig, b"".join(chunks)))
        elif sig == b"LCID":
            if len(data) > 0 and len(data) % 4 == 0:
                fids = [_remap_formid(x, src_self_idx, dst_master_idx) for x in struct.unpack(f"<{len(data) // 4}I", data)]
                new_subs.append((sig, struct.pack(f"<{len(fids)}I", *fids)))
            elif wb3_mode != "ours":
                new_subs.append((sig, data))
        elif sig == b"FULL" and wb3_mode == "ours" and wb3_display_name:
            new_subs.append((b"FULL", esm.zbytes(wb3_display_name)))
            saw_full = True
        elif sig == b"KSIZ":
            new_subs.append((b"KSIZ", struct.pack("<I", len(kws))))
            saw_ksiz = True
        elif sig == b"KWDA":
            new_subs.append((b"KWDA", struct.pack(f"<{len(kws)}I", *kws)))
            saw_kwda = True
        elif sig == b"DATA" and wb3_mode == "ours" and len(data) == 8:
            # WB3: clear LC172WorldLocation's inherited max_level = 16 (0000000000001000 -> all zero)
            new_subs.append((b"DATA", b"\x00" * 8))
            saw_data = True
        elif sig == b"PNAM":
            new_subs.append((b"PNAM", struct.pack("<I", surface_parent_fid)))
            saw_pnam = True
        elif sig == b"XNAM" and len(data) == 4:
            new_subs.append((b"XNAM", struct.pack("<i", system_id)))
        elif sig == b"YNAM" and len(data) == 4:
            new_subs.append((b"YNAM", struct.pack("<i", planet_id)))
        else:
            new_subs.append((sig, data))

    if merged_lcsr and not emitted_lcsr:
        insert_idx = next((i + 1 for i, (s, _) in enumerate(new_subs) if s == b"EDID"), 0)
        new_subs.insert(insert_idx, (b"LCSR", b"".join(merged_lcsr)))
    if wb3_mode == "ours" and wb3_display_name and not saw_full:
        insert_idx = next((i for i, (s, _) in enumerate(new_subs) if s == b"KSIZ"), len(new_subs))
        new_subs.insert(insert_idx, (b"FULL", esm.zbytes(wb3_display_name)))
    if not saw_ksiz:
        new_subs.append((b"KSIZ", struct.pack("<I", len(kws))))
    if not saw_kwda:
        new_subs.append((b"KWDA", struct.pack(f"<{len(kws)}I", *kws)))
    if wb3_mode == "ours" and not saw_data:
        insert_idx = next((i for i, (s, _) in enumerate(new_subs) if s == b"PNAM"), len(new_subs))
        new_subs.insert(insert_idx, (b"DATA", b"\x00" * 8))
    if not saw_pnam:
        new_subs.append((b"PNAM", struct.pack("<I", surface_parent_fid)))

    return esm.Record(b"LCTN", out_fid, new_subs, src_lctn.flags, src_lctn.vc, src_lctn.version, src_lctn.unknown)


def _compute_wb3_mnam_bounds(src_wrld: esm.Record, tile_cells: int = 64) -> bytes:
    """Compute 16-byte `WRLD.MNAM` (`usable_x, usable_y, nw_x, nw_y, se_x, se_y`) from `NAM0`/`NAM9` or `tile_cells`."""
    nam0 = probe.top_level(src_wrld, b"NAM0")
    nam9 = probe.top_level(src_wrld, b"NAM9")
    if nam0 and len(nam0) == 8 and nam9 and len(nam9) == 8:
        min_x_m, min_y_m = struct.unpack("<2f", nam0)
        max_x_m, max_y_m = struct.unpack("<2f", nam9)
        min_cx = int(round(min_x_m / 100.0))
        min_cy = int(round(min_y_m / 100.0))
        max_cx = int(round(max_x_m / 100.0)) - 1
        max_cy = int(round(max_y_m / 100.0)) - 1
        span_x = max(100, int(round(max_x_m - min_x_m)))
        span_y = max(100, int(round(max_y_m - min_y_m)))
        return struct.pack("<IIhhhh", span_x, span_y, min_cx, max_cy, max_cx, min_cy)
    half = tile_cells // 2
    span = tile_cells * 100
    return struct.pack("<IIhhhh", span, span, -half, tile_cells - half - 1, tile_cells - half - 1, -half)


def _remap_wrld_override(
    src_wrld: esm.Record,
    src_self_idx: int,
    dst_master_idx: int,
    system_id: int,
    planet_id: int,
    biome_fid: int,
    fnam_flags: int = ALLOWED_WRLD_FNAM_BITS,
    *,
    wb3_mode: str = "passthrough",
    wb3_display_name: Optional[str] = None,
    wb3_climate_fid: Optional[int] = None,
    wb3_water_fid: Optional[int] = None,
    wb3_silent_music_fid: Optional[int] = None,
    wb3_tile_cells: int = 64,
) -> esm.Record:
    if fnam_flags & ~ALLOWED_WRLD_FNAM_BITS:
        raise records.PlanetError(
            f"WRLD FNAM {fnam_flags:#04x} sets unproven bits outside ALLOWED_WRLD_FNAM_BITS ({ALLOWED_WRLD_FNAM_BITS:#04x})"
        )
    out_fid = _remap_formid(src_wrld.formid, src_self_idx, dst_master_idx)
    new_subs: List[Tuple[bytes, bytes]] = []
    inside_comp: Optional[str] = None
    saw_top_bnam = False
    saw_top_fnam = False
    saw_top_full = False
    saw_top_cnam = False
    saw_top_nam3 = False
    saw_top_nam4 = False
    saw_top_dnam = False
    saw_top_mnam = False
    saw_top_onam = False
    saw_top_znam = False

    # Inspect source DNAM so coastal DLC worlds (Far Harbor +6.43 m, Nuka-World +4.64 m) keep their sea height
    src_dnam_raw = probe.top_level(src_wrld, b"DNAM")
    src_land_h, src_water_h = struct.unpack("<2f", src_dnam_raw) if (src_dnam_raw and len(src_dnam_raw) == 8) else (-2048.0, -200.0)
    wb3_land_h = -120.0 if abs(src_land_h - (-2048.0)) < 1e-3 else src_land_h
    wb3_water_h = -200.0 if src_water_h <= -100.0 else src_water_h
    wb3_mnam_bytes = _compute_wb3_mnam_bounds(src_wrld, tile_cells=wb3_tile_cells) if wb3_mode == "ours" else b""

    for sig, data in src_wrld.subs:
        if sig == b"BFCB":
            inside_comp = esm.zstring(data)
            new_subs.append((sig, data))
            continue
        if sig == b"BFCE":
            inside_comp = None
            new_subs.append((sig, data))
            continue

        if inside_comp == "BGSWorldSpaceOverlay_Component":
            if sig == b"SNAM":
                new_subs.append((b"SNAM", struct.pack("<i", system_id)))
            elif sig == b"PNAM":
                new_subs.append((b"PNAM", struct.pack("<i", planet_id)))
            elif sig == b"BNAM" and len(data) == 4:
                sfbk_fid = _remap_formid(struct.unpack("<I", data)[0], src_self_idx, dst_master_idx)
                new_subs.append((b"BNAM", struct.pack("<I", sfbk_fid)))
            else:
                new_subs.append((sig, data))
            continue

        if inside_comp is None:
            if sig == b"FULL" and wb3_mode == "ours" and wb3_display_name:
                new_subs.append((b"FULL", esm.zbytes(wb3_display_name)))
                saw_top_full = True
            elif sig in (b"XLCN", b"WNAM") and len(data) == 4:
                remapped = _remap_formid(struct.unpack("<I", data)[0], src_self_idx, dst_master_idx)
                new_subs.append((sig, struct.pack("<I", remapped)))
            elif sig == b"CNAM" and len(data) == 4:
                if wb3_mode == "ours" and wb3_climate_fid is not None:
                    new_subs.append((b"CNAM", struct.pack("<I", wb3_climate_fid)))
                else:
                    remapped = _remap_formid(struct.unpack("<I", data)[0], src_self_idx, dst_master_idx)
                    new_subs.append((b"CNAM", struct.pack("<I", remapped)))
                saw_top_cnam = True
            elif sig == b"BNAM" and len(data) == 4:
                new_subs.append((b"BNAM", struct.pack("<I", biome_fid)))
                saw_top_bnam = True
            elif sig == b"NAM3" and len(data) == 4 and wb3_mode == "ours" and wb3_water_fid is not None:
                new_subs.append((b"NAM3", struct.pack("<I", wb3_water_fid)))
                saw_top_nam3 = True
            elif sig == b"NAM4" and len(data) == 4 and wb3_mode == "ours":
                new_subs.append((b"NAM4", struct.pack("<f", wb3_water_h)))
                saw_top_nam4 = True
            elif sig == b"DNAM" and len(data) == 8 and wb3_mode == "ours":
                new_subs.append((b"DNAM", struct.pack("<2f", wb3_land_h, wb3_water_h)))
                saw_top_dnam = True
            elif sig == b"MNAM" and len(data) == 16 and wb3_mode == "ours":
                new_subs.append((b"MNAM", wb3_mnam_bytes))
                saw_top_mnam = True
            elif sig == b"ONAM" and len(data) == 16 and wb3_mode == "ours":
                new_subs.append((b"ONAM", struct.pack("<4f", 1.0, 0.0, 0.0, 0.0)))
                saw_top_onam = True
            elif sig == b"ZNAM" and len(data) == 4 and wb3_mode == "ours" and wb3_silent_music_fid is not None:
                new_subs.append((b"ZNAM", struct.pack("<I", wb3_silent_music_fid)))
                saw_top_znam = True
            elif sig == b"FNAM":
                new_subs.append((b"FNAM", bytes([fnam_flags])))
                saw_top_fnam = True
            else:
                new_subs.append((sig, data))
        else:
            new_subs.append((sig, data))

    def _top_idx_after(target_sig: bytes) -> Optional[int]:
        comp = None
        for idx, (s, d) in enumerate(new_subs):
            if s == b"BFCB":
                comp = esm.zstring(d)
            elif s == b"BFCE":
                comp = None
            elif comp is None and s == target_sig:
                return idx + 1
        return None

    def _top_idx_before(target_sig: bytes) -> Optional[int]:
        comp = None
        for idx, (s, d) in enumerate(new_subs):
            if s == b"BFCB":
                comp = esm.zstring(d)
            elif s == b"BFCE":
                comp = None
            elif comp is None and s == target_sig:
                return idx
        return None

    if not saw_top_bnam:
        idx = _top_idx_after(b"XLCN")
        new_subs.insert(idx if idx is not None else len(new_subs), (b"BNAM", struct.pack("<I", biome_fid)))
    if not saw_top_fnam:
        idx = _top_idx_after(b"DATA")
        new_subs.insert(idx if idx is not None else len(new_subs), (b"FNAM", bytes([fnam_flags])))

    if wb3_mode == "ours":
        if wb3_display_name and not saw_top_full:
            idx = _top_idx_before(b"XLCN")
            new_subs.insert(idx if idx is not None else len(new_subs), (b"FULL", esm.zbytes(wb3_display_name)))
        if wb3_climate_fid is not None and not saw_top_cnam:
            # Canonical Starfield WRLD order (NewAtlantis / DefaultWorld): CNAM immediately after top-level BNAM
            idx = _top_idx_after(b"BNAM")
            new_subs.insert(idx if idx is not None else len(new_subs), (b"CNAM", struct.pack("<I", wb3_climate_fid)))
        if wb3_water_fid is not None and not saw_top_nam3:
            idx = _top_idx_after(b"CNAM") or _top_idx_after(b"BNAM")
            new_subs.insert(idx if idx is not None else len(new_subs), (b"NAM3", struct.pack("<I", wb3_water_fid)))
        if not saw_top_nam4:
            idx = _top_idx_after(b"NAM3") or _top_idx_after(b"BNAM")
            new_subs.insert(idx if idx is not None else len(new_subs), (b"NAM4", struct.pack("<f", wb3_water_h)))
        if not saw_top_dnam:
            idx = _top_idx_after(b"NAM4")
            new_subs.insert(idx if idx is not None else len(new_subs), (b"DNAM", struct.pack("<2f", wb3_land_h, wb3_water_h)))
        if not saw_top_mnam:
            idx = _top_idx_after(b"DNAM")
            new_subs.insert(idx if idx is not None else len(new_subs), (b"MNAM", wb3_mnam_bytes))
        if not saw_top_onam:
            idx = _top_idx_after(b"MNAM")
            new_subs.insert(idx if idx is not None else len(new_subs), (b"ONAM", struct.pack("<4f", 1.0, 0.0, 0.0, 0.0)))
        if wb3_silent_music_fid is not None and not saw_top_znam:
            # Canonical Starfield WRLD order (NewAtlantis / DefaultWorld): ZNAM immediately after NAM9 (before GNAM)
            idx = _top_idx_after(b"NAM9") or _top_idx_before(b"GNAM")
            new_subs.insert(idx if idx is not None else len(new_subs), (b"ZNAM", struct.pack("<I", wb3_silent_music_fid)))

    return esm.Record(b"WRLD", out_fid, new_subs, src_wrld.flags, src_wrld.vc, src_wrld.version, src_wrld.unknown)


def build_home_registration(
    sf: esm.Plugin,
    home_master_path: str,
    world_plugin_dirs: Sequence[str],
    world_keys: Sequence[str] = ("Commonwealth",),
    lever_keywords: Sequence[str] = (),
    fnam_flags: int = ALLOWED_WRLD_FNAM_BITS,
    registry: Optional[Dict[str, Any]] = None,
    position_overrides: Optional[Dict[str, Tuple[float, float]]] = None,
    map_markers_path: Optional[str] = None,
    *,
    wb3_mode: str = DEFAULT_WB3_MODE,
) -> Tuple[esm.PluginWriter, Dict[str, Any]]:
    """Build `FO4TerrainCore_Home.esm` from `world_registry.json`:
    - `1` `PNDT` override (`0x01000805` in `FO4SFHome.esm`) listing all registered worlds in `CNAM`
    - For each world in `world_keys`: `1` `WRLD` override + `1` `LCTN` override (`3` records total for `Commonwealth`).
    - When `wb3_mode == 'ours'` (`WB3` default): overrides inherited `LC172World` / `LC172WorldLocation` fields inside
      `FO4TerrainCore_Home.esm` (`CNAM`, `ZNAM`, `NAM3`, `NAM4`, `DNAM`, `MNAM`, `ONAM`, `FULL`, `LCTN.DATA`) while
      never touching `FO4TerrainCore.esm`; labels every `WB3` lever `untested`.
    - When `map_markers_path` (`--map-markers <FO4SFMapMarkers.esm>`) is given: adds `FO4SFMapMarkers.esm` as a master
      and merges its `LCSR` rows of `FO4TerrainCore.esm:000802` into our `LCTN` override (`C3`).
    """
    if not world_keys:
        raise records.PlanetError("world_keys must name at least one world from world_registry.json")
    if wb3_mode not in WB3_MODE_CHOICES:
        raise records.PlanetError(f"wb3_mode {wb3_mode!r} must be one of {WB3_MODE_CHOICES}")

    # Resolve only keywords (+ _NONE MUSC when wb3_mode == 'ours') from sf so synthetic b7dc7f52 fixtures stay minimal
    kw_names = records.keyword_edids(sf)
    by_kw_edid = {ed.lower(): fid & 0xFFFFFF for fid, ed in kw_names.items() if ed}
    for lev in lever_keywords:
        if lev not in LEVER_KEYWORD_EDIDS:
            raise records.PlanetError(f"unknown lever keyword {lev!r}; expected one of {LEVER_KEYWORD_EDIDS}")
    overlay_kw_fid = by_kw_edid.get("loctypeoverlay")
    if overlay_kw_fid is None:
        raise records.PlanetError("Starfield.esm is missing required KYWD 'LocTypeOverlay'")
    lever_kw_fids: List[int] = []
    for lev in lever_keywords:
        lk = by_kw_edid.get(lev.lower())
        if lk is None:
            raise records.PlanetError(f"Starfield.esm is missing required KYWD {lev!r}")
        lever_kw_fids.append(lk)

    wb3_silent_music_fid: Optional[int] = None
    if wb3_mode == "ours":
        muscs = resolve_edids_in_group(sf, "MUSC", ["_NONE"])
        if "_NONE" not in muscs:
            raise records.PlanetError("Starfield.esm is missing MUSC '_NONE' required by WB3")
        wb3_silent_music_fid = muscs["_NONE"]

    reg_data = registry if registry is not None else load_world_registry()
    raw_worlds = reg_data["worlds"] if isinstance(reg_data, dict) else reg_data.worlds
    if isinstance(raw_worlds, dict):
        by_key = dict(raw_worlds)
    else:
        by_key = {(r["key"] if isinstance(r, dict) else r.key): r for r in raw_worlds}

    home_idx = 1  # masters[1] == FO4SFHome.esm
    wb3_climate_fid: Optional[int] = None
    wb3_water_fid: Optional[int] = None

    with esm.Plugin(home_master_path) as hm:
        if hm.masters != ["Starfield.esm"]:
            raise records.PlanetError(f"{home_master_path} has masters {hm.masters}, expected ['Starfield.esm']")
        pndts = [r for r in hm.records("PNDT", [b"PNDT"]) if r.formid == ((1 << 24) | PLANET)]
        if len(pndts) != 1:
            raise records.PlanetError(f"{home_master_path} is missing home PNDT {(1 << 24) | PLANET:#010x}")
        home_planet = pndts[0]
        sid, _parent, pid = records.galaxy(home_planet)

        if wb3_mode == "ours":
            bioms = [r for r in hm.records("BIOM", [b"BIOM"]) if r.formid == ((1 << 24) | BIOME)]
            if len(bioms) == 1:
                enam_b = bioms[0].get(b"ENAM")
                if enam_b and len(enam_b) == 4:
                    raw_clmt, = struct.unpack("<I", enam_b)
                    wb3_climate_fid = (home_idx << 24) | (raw_clmt & 0xFFFFFF) if (raw_clmt >> 24) == 1 else raw_clmt
            watrs = [r for r in hm.records("WATR", [b"WATR"]) if r.formid == ((1 << 24) | HOME_WATER)]
            if len(watrs) != 1:
                raise records.PlanetError(f"{home_master_path} is missing home WATR {(1 << 24) | HOME_WATER:#010x} for WB3")
            wb3_water_fid = (home_idx << 24) | HOME_WATER

    # Resolve each world's plugin path and planned metadata from world_registry.json
    world_specs = []
    masters = ["Starfield.esm", os.path.basename(home_master_path)]
    for wkey in world_keys:
        if wkey not in by_key:
            raise records.PlanetError(f"world key {wkey!r} not in world_registry.json")
        row = by_key[wkey]
        if isinstance(row, dict):
            planned = row.get("planned_starfield_world") or {}
            plug_name = planned.get("plugin")
            world_edid = planned.get("world_edid")
            raw_pos = planned.get("planet_position")
            tile_cells = int(planned.get("tile_cells") or 64)
        else:
            planned_obj = row.planned_starfield_world
            plug_name = planned_obj.plugin
            world_edid = planned_obj.world_edid
            raw_pos = planned_obj.planet_position
            tile_cells = int(getattr(planned_obj, "tile_cells", 64) or 64)
        pos = (position_overrides or {}).get(wkey) or raw_pos
        if not plug_name or not world_edid or not pos or len(pos) != 2:
            raise records.PlanetError(f"world {wkey!r} has incomplete planned_starfield_world in world_registry.json")
        plug_path = None
        for d in world_plugin_dirs:
            cand = os.path.join(d, plug_name)
            if os.path.isfile(cand):
                plug_path = cand
                break
        if plug_path is None:
            raise records.PlanetError(f"world plugin {plug_name!r} for {wkey!r} not found in search dirs")
        if plug_name not in masters:
            masters.append(plug_name)
        world_specs.append((wkey, plug_name, plug_path, world_edid, (float(pos[0]), float(pos[1])), tile_cells))

    mm_lcsr_chunks: List[bytes] = []
    mm_name: Optional[str] = None
    if map_markers_path:
        mm_name = os.path.basename(map_markers_path)
        if not any(m.lower() == CORE_PLUGIN.lower() for m in masters):
            raise records.PlanetError(
                f"--map-markers {mm_name} requires {CORE_PLUGIN} in world_keys {list(world_keys)}"
            )
        if all(m.lower() != mm_name.lower() for m in masters):
            masters.append(mm_name)
        with esm.Plugin(map_markers_path) as mm:
            mm_lctns = [
                r
                for r in mm.records("LCTN", [b"LCTN"])
                if canonical_record_owner(mm, r.formid, mm_name) == (CORE_PLUGIN.lower(), CORE_LCTN_LOCAL, True)
            ]
            if len(mm_lctns) != 1:
                raise records.PlanetError(
                    f"{mm_name} has {len(mm_lctns)} LCTN overrides of {CORE_PLUGIN}:{CORE_LCTN_LOCAL:06X}, expected 1"
                )
            mm_lcsr_chunks = remap_lcsr_rows_to_masters(mm, mm_name, mm_lctns[0], masters)

    writer = esm.PluginWriter(masters, esm.ESM)
    surface_parent_fid = (home_idx << 24) | SURFACE_LOC
    home_biome_fid = (home_idx << 24) | BIOME

    cnam_entries: List[Tuple[float, float, int]] = []
    wrld_overrides: List[esm.Record] = []
    lctn_overrides: List[esm.Record] = []
    registered_report: List[Dict[str, Any]] = []

    for wkey, plug_name, plug_path, world_edid, (lat, lon), tile_cells in world_specs:
        dst_master_idx = masters.index(plug_name)
        disp_name = WORLD_DISPLAY_NAMES.get(wkey, wkey)
        with esm.Plugin(plug_path) as wp:
            src_self_idx = wp.self_index
            wrlds = [w for w in census.worlds(wp) if w.edid == world_edid]
            if len(wrlds) != 1:
                raise records.PlanetError(f"{plug_name} has {len(wrlds)} WRLD records with EditorID {world_edid!r}")
            src_wrld = wrlds[0]
            xlcn_b = probe.top_level(src_wrld, b"XLCN")
            if xlcn_b is None or len(xlcn_b) != 4:
                raise records.PlanetError(f"{plug_name} WRLD {world_edid!r} has no 4-byte XLCN location")
            xlcn_fid = struct.unpack("<I", xlcn_b)[0]
            locs = [r for r in wp.records("LCTN", [b"LCTN"]) if r.formid == xlcn_fid]
            if len(locs) != 1:
                raise records.PlanetError(f"{plug_name} has no LCTN {xlcn_fid:#010x} for WRLD {world_edid!r}")
            src_lctn = locs[0]

        remapped_wrld = _remap_wrld_override(
            src_wrld,
            src_self_idx,
            dst_master_idx,
            sid,
            pid,
            home_biome_fid,
            fnam_flags=fnam_flags,
            wb3_mode=wb3_mode,
            wb3_display_name=disp_name,
            wb3_climate_fid=wb3_climate_fid,
            wb3_water_fid=wb3_water_fid,
            wb3_silent_music_fid=wb3_silent_music_fid,
            wb3_tile_cells=tile_cells,
        )
        extra_chunks = (
            mm_lcsr_chunks
            if mm_name and plug_name.lower() == CORE_PLUGIN.lower() and (src_lctn.formid & 0xFFFFFF) == CORE_LCTN_LOCAL
            else ()
        )
        remapped_lctn = _remap_lctn_override(
            src_lctn,
            src_self_idx,
            dst_master_idx,
            surface_parent_fid,
            overlay_kw_fid,
            lever_kw_fids,
            sid,
            pid,
            extra_lcsr_chunks=extra_chunks,
            wb3_mode=wb3_mode,
            wb3_display_name=disp_name,
        )
        wrld_overrides.append(remapped_wrld)
        lctn_overrides.append(remapped_lctn)
        cnam_entries.append((lat, lon, remapped_wrld.formid))
        lcsr_total = sum(len(d) // 20 for d in remapped_lctn.all(b"LCSR"))
        w_entry: Dict[str, Any] = {
            "world_key": wkey,
            "world_plugin": plug_name,
            "world_edid": world_edid,
            "wrld_formid": records.fid_hex(remapped_wrld.formid),
            "lctn_formid": records.fid_hex(remapped_lctn.formid),
            "lcsr_rows": lcsr_total,
            "latitude_rad": lat,
            "longitude_rad": lon,
            "fnam_flags": fnam_flags,
            "lever_keywords": list(lever_keywords),
            "wb3_mode": wb3_mode,
        }
        if wb3_mode == "ours":
            w_entry["wb3_status"] = "untested"
            w_entry["wb3_overrides"] = list(wb_records.WB3_OVERRIDE_SPEC)
        registered_report.append(w_entry)

    pndt_override = records.registration_record(home_planet, (home_idx << 24) | PLANET, cnam_entries)
    writer.add(pndt_override)
    for wr in wrld_overrides:
        writer.add(wr)
    for lr in lctn_overrides:
        writer.add(lr)

    report: Dict[str, Any] = {
        "registration_plugin": HOME_REGISTRATION,
        "masters": masters,
        "record_count": len(writer.records),
        "pndt_override": records.fid_hex(pndt_override.formid),
        "biome_formid": records.fid_hex(home_biome_fid),
        "surface_parent_formid": records.fid_hex(surface_parent_fid),
        "wb3_mode": wb3_mode,
        "wb3_status": "untested" if wb3_mode == "ours" else "passthrough",
        "worlds": registered_report,
    }
    if mm_name is not None:
        report["map_markers_plugin"] = mm_name
        report["map_markers_lcsr_rows"] = len(mm_lcsr_chunks)
    return writer, report


# ------------------------------------------------------------------------------------------------ offline checks
def canonical_record_owner(plugin: esm.Plugin, formid: int, plugin_name: str) -> Tuple[str, int, bool]:
    """Return `(defining_plugin_lower, local_24bit_id, is_override)` for `formid` inside `plugin`."""
    idx = formid >> 24
    local = formid & 0xFFFFFF
    if idx < len(plugin.masters):
        return plugin.masters[idx].lower(), local, True
    return plugin_name.lower(), local, False


def _sha256_path(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_load_order_overrides(
    plugin_paths: Sequence[str],
    *,
    allow_map_markers_pair: bool = False,
    pinned_map_markers_sha256: Optional[str] = None,
    map_markers_plugin_name: str = MAP_MARKERS_PLUGIN,
) -> List[str]:
    """Verify `PNDT`, `LCTN`, and `WRLD` overrides across `plugin_paths` in load order (`W3`, `C3`).

    When `allow_map_markers_pair` is `True`, allows **only** `FO4SFMapMarkers.esm` followed later in load order
    by `FO4TerrainCore_Home.esm` on `fo4terraincore.esm:000802` (`LCTN`) and `fo4terraincore.esm:000803` (`WRLD`),
    and **only** when:
      (a) `FO4TerrainCore_Home.esm`'s `LCTN` override `LCSR` rows include every `LCSR` row of `FO4SFMapMarkers.esm`'s,
      (b) the `FO4SFMapMarkers.esm` file SHA-256 matches `pinned_map_markers_sha256`, and
      (c) `FO4SFMapMarkers.esm` loads before `FO4SFHome.esm` and `FO4TerrainCore_Home.esm`.
    Refuses every other duplicate override, naming both plugins and the colliding `owner:XXXXXX` FormKey.
    """
    problems: List[str] = []
    orig_names = [os.path.basename(p) for p in plugin_paths]
    names_low = [n.lower() for n in orig_names]
    mm_low = map_markers_plugin_name.lower()
    hm_low = HOME_MASTER.lower()
    hr_low = HOME_REGISTRATION.lower()

    if allow_map_markers_pair and mm_low in names_low:
        mm_idx = names_low.index(mm_low)
        mm_disp = orig_names[mm_idx]
        for tgt_low, tgt_disp in ((hm_low, HOME_MASTER), (hr_low, HOME_REGISTRATION)):
            if tgt_low in names_low and names_low.index(tgt_low) < mm_idx:
                problems.append(
                    f"invalid load order: {mm_disp} loads after {tgt_disp}; "
                    f"{HOME_MASTER} and {HOME_REGISTRATION} must load after {mm_disp}"
                )
    if hm_low in names_low and hr_low in names_low and names_low.index(hr_low) < names_low.index(hm_low):
        problems.append(f"invalid load order: {HOME_REGISTRATION} loads before its master {HOME_MASTER}")

    sha_by_low: Dict[str, str] = {}
    lcsr_by_plugin_and_key: Dict[Tuple[str, str, int], List[Any]] = {}
    per_plugin_overrides: List[Tuple[str, str, List[Tuple[str, str, int, str]]]] = []

    for path, name, nlow in zip(plugin_paths, orig_names, names_low):
        if nlow == mm_low:
            sha_by_low[nlow] = _sha256_path(path)
        ov_rows: List[Tuple[str, str, int, str]] = []
        with esm.Plugin(path) as p:
            for rtype in ("PNDT", "LCTN"):
                for rec in p.records(rtype, [rtype.encode("ascii")]):
                    owner, local, is_override = canonical_record_owner(p, rec.formid, name)
                    if not is_override:
                        continue
                    if rtype == "LCTN":
                        lcsr_by_plugin_and_key[(nlow, owner, local)] = canonical_lcsr_rows(p, name, rec)
                    ov_rows.append((rtype, owner, local, rec.edid))
            for rec in census.worlds(p):
                owner, local, is_override = canonical_record_owner(p, rec.formid, name)
                if not is_override:
                    continue
                ov_rows.append(("WRLD", owner, local, rec.edid))
        per_plugin_overrides.append((name, nlow, ov_rows))

    mm_hash_ok = False
    mm_lcsr_subset_ok = False
    if allow_map_markers_pair and mm_low in names_low:
        mm_disp = orig_names[names_low.index(mm_low)]
        actual_sha = sha_by_low[mm_low]
        if not pinned_map_markers_sha256:
            problems.append(
                f"{mm_disp} is active without a pinned map_markers_sha256 in plan.json (re-stage with --map-markers)"
            )
        elif actual_sha.lower() != pinned_map_markers_sha256.lower():
            problems.append(
                f"{mm_disp} sha256 mismatch: installed file has {actual_sha}, plan.json pinned {pinned_map_markers_sha256}"
            )
        else:
            mm_hash_ok = True

        mm_lcsr = lcsr_by_plugin_and_key.get((mm_low, CORE_PLUGIN.lower(), CORE_LCTN_LOCAL))
        hr_lcsr = lcsr_by_plugin_and_key.get((hr_low, CORE_PLUGIN.lower(), CORE_LCTN_LOCAL))
        if mm_lcsr is not None and hr_low in names_low:
            if hr_lcsr is None:
                problems.append(
                    f"{HOME_REGISTRATION} is missing LCTN override of {CORE_PLUGIN.lower()}:{CORE_LCTN_LOCAL:06X} "
                    f"required by {mm_disp}"
                )
            else:
                hr_set = set(hr_lcsr)
                missing_lcsr = [r for r in mm_lcsr if r not in hr_set]
                if missing_lcsr:
                    problems.append(
                        f"{HOME_REGISTRATION} LCTN override of {CORE_PLUGIN.lower()}:{CORE_LCTN_LOCAL:06X} "
                        f"is missing {len(missing_lcsr)} LCSR row(s) from {mm_disp}"
                    )
                else:
                    mm_lcsr_subset_ok = True
        elif mm_lcsr is None:
            # Map-markers plugin without an LCTN 000802 override needs no LCSR rows copied
            mm_lcsr_subset_ok = True

    seen: Dict[Tuple[str, str, int], List[Tuple[str, str]]] = {}
    for cur_name, cur_low, ov_rows in per_plugin_overrides:
        for rtype, owner, local, edid in ov_rows:
            key = (rtype, owner, local)
            for prev_name, prev_low in seen.get(key, ()):
                allowed = (
                    allow_map_markers_pair
                    and prev_low == mm_low
                    and cur_low == hr_low
                    and (
                        (rtype == "LCTN" and owner == CORE_PLUGIN.lower() and local == CORE_LCTN_LOCAL)
                        or (rtype == "WRLD" and owner == CORE_PLUGIN.lower() and local == CORE_WRLD_LOCAL)
                    )
                    and mm_hash_ok
                    and mm_lcsr_subset_ok
                )
                if not allowed:
                    problems.append(
                        f"duplicate {rtype} override of {owner}:{local:06X} ({edid}) in both {prev_name} and {cur_name}"
                    )
            seen.setdefault(key, []).append((cur_name, cur_low))

    return problems


def check_no_duplicate_overrides(plugin_paths: Sequence[str]) -> List[str]:
    """Refuse any plugin set in which two plugins override the same `PNDT`, `LCTN`, or `WRLD` record (`W3`).
    Returns a list of human-readable collision errors (`[]` when clean)."""
    return check_load_order_overrides(plugin_paths, allow_map_markers_pair=False)


def check_home_stage(
    sf_path: str,
    home_master_path: str,
    home_reg_path: str,
    data_dir: Optional[str] = None,
    expected_world_count: int = 1,
    expected_levers: Sequence[str] = (),
    map_markers_path: Optional[str] = None,
    *,
    expected_climate: Optional[str] = None,
    expected_sky: Optional[str] = None,
    expected_ground_ltex: Optional[str] = None,
    expected_surface_tree: Optional[str] = None,
    expected_wb3_mode: Optional[str] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    """Comprehensive offline verification for `W2`, `W3`, `W4`, `WL1`, `WL2`, `WB1`, `WB2`, and `WB3`."""
    problems: List[str] = []
    with esm.Plugin(sf_path) as sf:
        kw_names = records.keyword_edids(sf)
        by_kw_edid = {ed.lower(): fid & 0xFFFFFF for fid, ed in kw_names.items() if ed}
        forbidden_ids = {
            by_kw_edid[name.lower()]
            for name in FORBIDDEN_PLANET_KEYWORD_EDIDS
            if name.lower() in by_kw_edid
        }

        with esm.Plugin(home_master_path) as hm:
            if hm.masters != ["Starfield.esm"]:
                problems.append(f"{HOME_MASTER} masters {hm.masters} != ['Starfield.esm']")
            if any(m.lower() == "fo4wg1redrocket.esm" for m in hm.masters):
                problems.append(f"{HOME_MASTER} must never reference FO4WG1RedRocket.esm")
            if hm.localized:
                problems.append(f"{HOME_MASTER} has LOCALIZED flag set")

            hm_group_order = list(hm.groups.keys())
            canonical_hm_groups = [g for g in esm.GROUP_ORDER if g in hm.groups]
            if hm_group_order != canonical_hm_groups:
                problems.append(
                    f"{HOME_MASTER} top-group order {hm_group_order} != canonical Starfield order {canonical_hm_groups}"
                )

            own = lambda loc_id: (1 << 24) | loc_id  # noqa: E731
            by_fid: Dict[int, esm.Record] = {}
            for grp in hm.groups:
                for rec in hm.records(grp):
                    by_fid[rec.formid] = rec

            mandatory_sigs = {
                own(STAR): b"STDT",
                own(SYSTEM_LOC): b"LCTN",
                own(PLANET_LOC): b"LCTN",
                own(ORBIT_LOC): b"LCTN",
                own(SURFACE_LOC): b"LCTN",
                own(PLANET): b"PNDT",
                own(BIOME): b"BIOM",
            }
            optional_wb_sigs = {
                own(HOME_WEATHER): b"WTHR",
                own(HOME_CLIMATE): b"CLMT",
                own(HOME_ATMO): b"ATMO",
                own(HOME_GROUND_LTEX): b"LTEX",
                own(HOME_SURFACE_TREE): b"SFTR",
                own(HOME_WATER): b"WATR",
                own(HOME_SUN_PRESET): b"SUNP",
            }
            for fid, wsig in mandatory_sigs.items():
                if fid not in by_fid or by_fid[fid].sig != wsig:
                    problems.append(f"{HOME_MASTER} missing {wsig.decode()} {fid:#010x}")
            for fid, rec in sorted(by_fid.items()):
                if fid not in mandatory_sigs:
                    if fid not in optional_wb_sigs:
                        problems.append(f"{HOME_MASTER} holds unexpected record {fid:#010x} ({rec.sig.decode()})")
                    elif rec.sig != optional_wb_sigs[fid]:
                        problems.append(
                            f"{HOME_MASTER} record {fid:#010x} has sig {rec.sig.decode()}, expected {optional_wb_sigs[fid].decode()}"
                        )
            if problems:
                return problems, {}

            star_rec = by_fid[own(STAR)]
            planet_rec = by_fid[own(PLANET)]
            biome_rec = by_fid[own(BIOME)]
            surf_rec = by_fid[own(SURFACE_LOC)]
            biom_pndt_refs = wb_records.collect_biom_and_pndt_references(sf, hm, home_master_name=HOME_MASTER)

            # WB1: verify zero Starfield climate, weather, or atmosphere when 'ours' is selected
            if expected_climate in ("ours", "ours_empty"):
                sf_clmt_wthr = [
                    r
                    for r in biom_pndt_refs
                    if r["owner"].lower() == "starfield.esm" and r["record_type"] in ("CLMT", "WTHR", "WTHS")
                ]
                if sf_clmt_wthr:
                    problems.append(f"WB1 failed: BIOM/CLMT still references Starfield climate/weather {sf_clmt_wthr}")
            if expected_sky == "ours":
                sf_atmo = [
                    r
                    for r in biom_pndt_refs
                    if r["owner"].lower() == "starfield.esm" and r["record_type"] == "ATMO"
                ]
                if sf_atmo:
                    problems.append(f"WB1 failed: PNDT/ATMO still references Starfield atmosphere {sf_atmo}")

            # WB2: verify FO4 land texture across all 7 LNAM slots and surface tree setting
            if expected_ground_ltex == "ours":
                if own(HOME_GROUND_LTEX) not in by_fid:
                    problems.append(f"WB2 failed: {HOME_MASTER} missing LTEX {own(HOME_GROUND_LTEX):#010x}")
                lnams = biome_rec.all(b"LNAM")
                if len(lnams) != 7:
                    problems.append(f"WB2 failed: BIOM has {len(lnams)} LNAM slots, expected 7")
                for expected_slot, lbuf in enumerate(lnams):
                    slot_i, lfid, gfid = struct.unpack_from("<3I", lbuf, 0)
                    if (slot_i, lfid, gfid) != (expected_slot, own(HOME_GROUND_LTEX), 0):
                        problems.append(
                            f"WB2 failed: BIOM LNAM[{expected_slot}] = {(slot_i, hex(lfid), hex(gfid))} "
                            f"!= {(expected_slot, hex(own(HOME_GROUND_LTEX)), '0x0')}"
                        )
            fnam_top = wb_records.pndt_surface_tree_fnam(planet_rec)
            if expected_surface_tree == "none":
                if fnam_top is not None:
                    problems.append("WB2 failed: PNDT carries top-level FNAM when surface_tree='none'")
            elif expected_surface_tree == "ours_empty":
                if not fnam_top or struct.unpack("<I", fnam_top)[0] != own(HOME_SURFACE_TREE):
                    problems.append(f"WB2 failed: PNDT FNAM != {own(HOME_SURFACE_TREE):#010x}")

            # Zero whole-record Houdini PCCC/XMPM copies
            for label, rec in (("STDT", star_rec), ("PNDT", planet_rec)):
                if rec.get(b"PCCC") is not None or rec.get(b"XMPM") is not None:
                    problems.append(f"{HOME_MASTER} {label} {rec.edid} contains copied PCCC/XMPM Houdini data")

            sid = records.star_system_id(star_rec)
            psys, ppar, pid = records.galaxy(planet_rec)
            if psys != sid or ppar != 0:
                problems.append(f"PNDT galaxy {(psys, ppar, pid)} does not match STDT system_id {sid:#x}")

            if records.master_worldspaces(planet_rec):
                problems.append("FO4SFHome.esm PNDT must hold zero Starfield master worldspaces")

            # Verify zero Starfield worldspace or location uses sid
            sf_sys_locs = records.system_locations(sf, sid)
            if sf_sys_locs:
                problems.append(f"Starfield.esm has {len(sf_sys_locs)} locations under system_id {sid:#x}")
            sf_sys_worlds = [w for w in census.overlay_worlds(sf, "Starfield.esm") if w[2] == sid]
            if sf_sys_worlds:
                problems.append(f"Starfield.esm has overlay worlds under system_id {sid:#x}: {sf_sys_worlds}")

            if data_dir:
                skip = ("starfield.esm", HOME_MASTER.lower(), HOME_REGISTRATION.lower()) + census.OWN_PLUGINS
                other = census.plugin_bodies(data_dir, skip=skip)
                if any(s == sid for _, s, _ in other["stars"]):
                    problems.append(f"system_id {sid:#x} collides with another plugin star in Data")
                if any(g[0] == sid for _, _, _, g, _ in other["planets"]):
                    problems.append(f"system_id {sid:#x} collides with another plugin planet in Data")

            # Check planet physical values & trait keywords
            phys = records.orbital(planet_rec)
            if abs(phys.get("surface_gravity", 0.0) - 1.0) > 1e-4:
                problems.append(f"PNDT surface_gravity {phys.get('surface_gravity')} != 1.0")
            if abs(phys.get("radius_km", 0.0) - 6371.0) > 0.1:
                problems.append(f"PNDT radius_km {phys.get('radius_km')} != 6371.0")
            if abs(phys.get("rotational_velocity", 0.0) - 1.0) > 1e-4:
                problems.append(f"PNDT rotational_velocity {phys.get('rotational_velocity')} != 1.0")

            p_desc = records.describe_planet(planet_rec, kw_names)
            anam_raw = records.body_get(planet_rec.subs, b"ANAM")
            p_body_name = esm.zstring(anam_raw) if anam_raw else ""
            if not p_body_name:
                problems.append("PNDT BDST..BDED ANAM body_name is empty")
            p_kw_fids = {int(fid_s, 16) for fid_s, _ in p_desc["keywords"]}
            bad_present = sorted(kw_names.get(k, hex(k)) for k in (p_kw_fids & forbidden_ids))
            if bad_present:
                problems.append(f"PNDT carries forbidden hazard/exclusion keywords: {bad_present}")

            # W4: check BIOM has zero GNAM/NAM1/fauna/flora and PNDT PPBD names our BIOM
            ppbd_list = records.biomes(planet_rec)
            if len(ppbd_list) != 1 or ppbd_list[0]["biome"] != own(BIOME):
                problems.append(f"PNDT PPBD {[hex(x['biome']) for x in ppbd_list]} != [{own(BIOME):#010x}]")
            if any(b["fauna"] or b["flora"] or b["resource_generation"] for b in ppbd_list):
                problems.append("PNDT PPBD has non-empty fauna, flora, or resource_generation")
            if biome_rec.all(b"GNAM") or biome_rec.all(b"NAM1"):
                problems.append("BIOM carries procedural GNAM objects or NAM1 resources")

            # Check surface location lever keywords
            surf_kw_fid = by_kw_edid["loctypesurface"]
            want_surf_kws = [surf_kw_fid] + [
                by_kw_edid[k.lower()] for k in expected_levers if k != "LocTypeSurface"
            ]
            if records.keywords_of(surf_rec) != want_surf_kws:
                problems.append(f"home surface LCTN keywords {records.keywords_of(surf_rec)} != {want_surf_kws}")

        # W3 + WL1 + WL2 + WB3: inspect FO4TerrainCore_Home.esm
        with esm.Plugin(home_reg_path) as reg:
            if len(reg.masters) < 3 or reg.masters[:2] != ["Starfield.esm", os.path.basename(home_master_path)]:
                problems.append(f"{HOME_REGISTRATION} masters {reg.masters} invalid")
            if any(m.lower() == "fo4wg1redrocket.esm" for m in reg.masters):
                problems.append(f"{HOME_REGISTRATION} must never reference FO4WG1RedRocket.esm")
            reg_group_order = list(reg.groups.keys())
            canonical_reg_groups = [g for g in esm.GROUP_ORDER if g in reg.groups]
            if reg_group_order != canonical_reg_groups:
                problems.append(
                    f"{HOME_REGISTRATION} top-group order {reg_group_order} != canonical Starfield order {canonical_reg_groups}"
                )
            reg_pndts = list(reg.records("PNDT", [b"PNDT"]))
            reg_lctns = list(reg.records("LCTN", [b"LCTN"]))
            reg_wrlds = census.worlds(reg)
            total_recs = len(reg_pndts) + len(reg_lctns) + len(reg_wrlds)
            want_total = 1 + 2 * expected_world_count
            if total_recs != want_total:
                problems.append(f"{HOME_REGISTRATION} has {total_recs} records, expected {want_total}")
            if len(reg_pndts) != 1 or reg_pndts[0].formid != ((1 << 24) | PLANET):
                problems.append(f"{HOME_REGISTRATION} PNDT override missing or wrong FormID")
            else:
                mws = records.master_worldspaces(reg_pndts[0])
                if len(mws) != expected_world_count:
                    problems.append(f"{HOME_REGISTRATION} CNAM lists {len(mws)} worlds, expected {expected_world_count}")

            want_reg_kws = [by_kw_edid["loctypeoverlay"]] + [
                by_kw_edid[k.lower()] for k in expected_levers if k != "LocTypeOverlay"
            ]
            silent_musc = resolve_edids_in_group(sf, "MUSC", ["_NONE"]).get("_NONE") if expected_wb3_mode == "ours" else None

            for wrec in reg_wrlds:
                ov = census.overlay_of(wrec)
                if ov is None or ov[0] != sid or ov[1] != pid:
                    problems.append(f"WRLD {wrec.edid} overlay {ov} != ({sid}, {pid}, ...)")
                bnam_b = probe.top_level(wrec, b"BNAM")
                bnam_fid = struct.unpack("<I", bnam_b)[0] if bnam_b and len(bnam_b) == 4 else None
                if bnam_fid != ((1 << 24) | BIOME):
                    problems.append(f"WRLD {wrec.edid} BNAM {bnam_fid!r} != {(1 << 24) | BIOME:#010x}")
                fnam_b = probe.top_level(wrec, b"FNAM") or b""
                fnam_val = int.from_bytes(fnam_b, "little") if fnam_b else 0
                if fnam_val & ~ALLOWED_WRLD_FNAM_BITS:
                    problems.append(f"WRLD {wrec.edid} FNAM {fnam_val:#04x} sets unproven bits")
                if expected_wb3_mode == "ours":
                    cnam_b = probe.top_level(wrec, b"CNAM")
                    if not cnam_b or len(cnam_b) != 4:
                        problems.append(f"WB3 failed: WRLD {wrec.edid} missing CNAM climate override")
                    nam3_b = probe.top_level(wrec, b"NAM3")
                    nam3_fid = struct.unpack("<I", nam3_b)[0] if nam3_b and len(nam3_b) == 4 else None
                    if nam3_fid != ((1 << 24) | HOME_WATER):
                        problems.append(f"WB3 failed: WRLD {wrec.edid} NAM3 {nam3_fid!r} != {(1 << 24) | HOME_WATER:#010x}")
                    znam_b = probe.top_level(wrec, b"ZNAM")
                    znam_fid = struct.unpack("<I", znam_b)[0] if znam_b and len(znam_b) == 4 else None
                    if znam_fid != silent_musc:
                        problems.append(f"WB3 failed: WRLD {wrec.edid} ZNAM {znam_fid!r} != {silent_musc!r}")
                    mnam_b = probe.top_level(wrec, b"MNAM")
                    if not mnam_b or mnam_b == bytes(16):
                        problems.append(f"WB3 failed: WRLD {wrec.edid} MNAM map bounds remained zero")

            for lrec in reg_lctns:
                pnam_b = lrec.get(b"PNAM")
                pnam_fid = struct.unpack("<I", pnam_b)[0] if pnam_b and len(pnam_b) == 4 else None
                if pnam_fid != ((1 << 24) | SURFACE_LOC):
                    problems.append(f"LCTN {lrec.edid} PNAM {pnam_fid!r} != {(1 << 24) | SURFACE_LOC:#010x}")
                if records.keywords_of(lrec) != want_reg_kws:
                    problems.append(f"LCTN {lrec.edid} keywords {records.keywords_of(lrec)} != {want_reg_kws}")
                if expected_wb3_mode == "ours":
                    ldata = lrec.get(b"DATA")
                    if ldata != b"\x00" * 8:
                        problems.append(f"WB3 failed: LCTN {lrec.edid} DATA {ldata!r} not cleared to zero")

            if map_markers_path:
                mm_name = os.path.basename(map_markers_path)
                if mm_name.lower() not in [m.lower() for m in reg.masters]:
                    problems.append(f"{HOME_REGISTRATION} masters {reg.masters} missing {mm_name}")
                with esm.Plugin(map_markers_path) as mm:
                    mm_lctns = [
                        r
                        for r in mm.records("LCTN", [b"LCTN"])
                        if canonical_record_owner(mm, r.formid, mm_name) == (CORE_PLUGIN.lower(), CORE_LCTN_LOCAL, True)
                    ]
                    reg_core_lctns = [
                        r
                        for r in reg_lctns
                        if canonical_record_owner(reg, r.formid, HOME_REGISTRATION)
                        == (CORE_PLUGIN.lower(), CORE_LCTN_LOCAL, True)
                    ]
                    if len(mm_lctns) == 1 and len(reg_core_lctns) == 1:
                        mm_rows = canonical_lcsr_rows(mm, mm_name, mm_lctns[0])
                        hr_rows = set(canonical_lcsr_rows(reg, HOME_REGISTRATION, reg_core_lctns[0]))
                        miss = [r for r in mm_rows if r not in hr_rows]
                        if miss:
                            problems.append(
                                f"{HOME_REGISTRATION} LCTN override missing {len(miss)} LCSR row(s) from {mm_name}"
                            )

    problems.extend(check_no_duplicate_overrides([home_master_path, home_reg_path]))

    summary = {
        "system_id": f"0x{sid:08X}",
        "planet_id": pid,
        "body_name": p_body_name,
        "surface_gravity_g": round(phys.get("surface_gravity", 0.0), 4),
        "radius_km": round(phys.get("radius_km", 0.0), 2),
        "mean_orbit_km": round(phys.get("mean_orbit", 0.0), 1),
        "rotational_velocity": round(phys.get("rotational_velocity", 0.0), 4),
        "temp_c": round(phys.get("temp", 0.0), 2),
        "planet_keywords": [name for _, name in p_desc["keywords"]],
        "biome_formid": f"0x{(1 << 24) | BIOME:08X}",
        "top_group_order": hm_group_order,
        "registration_records": want_total,
        "biom_and_pndt_references": biom_pndt_refs,
        "field_sources": {
            "STDT": list(STAR_FIELD_SPEC),
            "PNDT": list(PLANET_FIELD_SPEC),
            "BIOM": list(BIOM_FIELD_SPEC),
            "WTHR": list(wb_records.WTHR_FIELD_SPEC),
            "CLMT": list(wb_records.CLMT_FIELD_SPEC),
            "ATMO": list(wb_records.ATMO_FIELD_SPEC),
            "LTEX": list(wb_records.LTEX_FIELD_SPEC),
            "WB3_OVERRIDES": list(wb_records.WB3_OVERRIDE_SPEC),
        },
    }
    return problems, summary
