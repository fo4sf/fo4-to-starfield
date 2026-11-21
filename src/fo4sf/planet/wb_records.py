"""Field-by-field record specifications and pure binary builders for `WB1`, `WB2`, and `WB3`
(`FO4SFHome.esm` weather, climate, atmosphere, Fallout 4 land texture, optional empty surface tree,
neutral dry water, and `FO4TerrainCore_Home.esm` `WRLD`/`LCTN` inherited-field overrides).

Design invariants (`WB1`, `WB2`, `WB3`, `R4`, `R9`):
- Zero whole-record binary copies from `Starfield.esm`: every subrecord of `WTHR`, `CLMT`, `ATMO` (including its
  self-describing `BETH` v8 `REFL` reflection stream), `LTEX`, `SFTR`, and `WATR` is packed field-by-field from
  explicit source tables (`WTHR_FIELD_SPEC`, `CLMT_FIELD_SPEC`, `ATMO_FIELD_SPEC`, `LTEX_FIELD_SPEC`,
  `SFTR_FIELD_SPEC`, `WATR_FIELD_SPEC`, and `WB3_OVERRIDE_SPEC`).
- `FO4SFHomeClearWeather` (`WTHR`), `FO4SFHomeClimate` (`CLMT`), `FO4SFHomeAtmosphere` (`ATMO`),
  `FO4SFHomeSurfaceTree` (`SFTR`), and `FO4SFHomeDryWater` (`WATR`) contain ZERO `Starfield.esm` FormID pointers.
- `FO4SFHomeGroundDirt01` (`LTEX`) binds `Materials\\Terrain\\FO4SFHomeGroundDirt01.mat` (built via
  `fo4sf.terrain.ltex_map.build_terrain_mat` over converted Fallout 4 ground `.dds` maps in the external stage's
  `Data/` tree — never committed to Git and never referencing `FO4WG1RedRocket.esm`).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ..terrain import ltex_map as lm
from . import esm, probe, records

FORM_VERSION = 581

# Local FormIDs inside FO4SFHome.esm (immediately after BIOME = 0x806)
HOME_WEATHER = 0x807
HOME_CLIMATE = 0x808
HOME_ATMO = 0x809
HOME_GROUND_LTEX = 0x80A
HOME_SURFACE_TREE = 0x80B
HOME_WATER = 0x80C
HOME_SUN_PRESET = 0x80D

DEFAULT_WEATHER_EDID = "FO4SFHomeClearWeather"
DEFAULT_CLIMATE_EDID = "FO4SFHomeClimate"
DEFAULT_ATMO_EDID = "FO4SFHomeAtmosphere"
DEFAULT_GROUND_LTEX_EDID = "FO4SFHomeGroundDirt01"
DEFAULT_SURFACE_TREE_EDID = "FO4SFHomeSurfaceTree"
DEFAULT_WATER_EDID = "FO4SFHomeDryWater"
DEFAULT_SUN_PRESET_EDID = "FO4SFHomeSunPreset"

# WB2: smallest height-range PTST across all 46 PTST -> 258 SFPT -> SFBK chains in Starfield.esm
# (-15.44 .. +27.56 m, max SFBK span 38.11 m, mean 29.83 m vs PatternStyleHillsRockyFieldsRocky's 372.61 m max span).
DEFAULT_TERRAIN_PATTERN_EDID = "PatternStyleFieldsHillsFieldsFlat"
CONTROL_TERRAIN_PATTERN_EDID = "PatternStyleHillsRockyFieldsRocky"
TERRAIN_PATTERN_CHOICES: Tuple[str, ...] = (
    DEFAULT_TERRAIN_PATTERN_EDID,
    "PatternStyleFieldsMixed",
    CONTROL_TERRAIN_PATTERN_EDID,
)

CLIMATE_CHOICES: Tuple[str, ...] = ("ours", "ours_empty", "ClimateUniqueNewAtlantis", "DefaultClimate")
SKY_CHOICES: Tuple[str, ...] = ("ours", "ATMO_Jemison", "ATMO_Earth")
GROUND_LTEX_CHOICES: Tuple[str, ...] = ("ours", "LDirtFootprints01")
SURFACE_TREE_CHOICES: Tuple[str, ...] = ("none", "ours_empty", "EarthSurfaceTree")
WB3_MODE_CHOICES: Tuple[str, ...] = ("ours", "passthrough")
SUN_PRESET_CHOICES: Tuple[str, ...] = ("SunPresetTypeG2", "ours")
ORBITAL_MESHES_CHOICES: Tuple[str, ...] = ("starfield", "none")

# Minimal valid Terrain1Layer.mat JSON structure (used when staging synthetic/unit-test ground materials without game archives)
MINIMAL_TERRAIN1LAYER_TEMPLATE: Dict[str, Any] = {
    "Import": ["Data\\MATERIALS\\Layered\\ShaderModels\\Terrain1Layer.mat"],
    "Objects": [
        {
            "Components": [
                {"Data": {"Name": "TemplateGround"}, "Index": 0, "Type": "BSComponentDB::CTName"},
                {"Data": {"ID": "res:44DFC423:0005E661:A06346EA"}, "Index": 0, "Type": "BSMaterial::LayerID"},
            ],
            "Parent": "Data\\MATERIALS\\Layered\\ShaderModels\\Terrain1Layer.mat",
        },
        {
            "Components": [
                {"Data": {"Name": "TemplateGround_Layer1"}, "Index": 0, "Type": "BSComponentDB::CTName"},
                {"Data": {"ID": "res:44DFC445:0005E661:A06346EA"}, "Index": 0, "Type": "BSMaterial::MaterialID"},
            ],
            "ID": "res:44DFC423:0005E661:A06346EA",
            "Parent": "res:D785C4ED:0005DEA9:A06346EA",
        },
        {
            "Components": [
                {"Data": {"Name": "TemplateGround_TextureSet1"}, "Index": 0, "Type": "BSComponentDB::CTName"},
                {"Data": {"FileName": "textures\\template_color.dds"}, "Index": 0, "Type": "BSMaterial::MRTextureFile", "Version": 1},
                {"Data": {"FileName": "textures\\template_normal.dds"}, "Index": 1, "Type": "BSMaterial::MRTextureFile", "Version": 1},
                {"Data": {"FileName": "textures\\template_rough.dds"}, "Index": 3, "Type": "BSMaterial::MRTextureFile", "Version": 1},
            ],
            "ID": "res:44DFC48E:0005E661:A06346EA",
            "Parent": "res:D785C5BE:0005DEA9:A06346EA",
        },
    ],
    "Summary": {
        "Layer1": {
            "Parent": "Data\\MATERIALS\\Layered\\ShaderModels\\Terrain1Layer.mat",
            "Textures": {
                "Albedo": {"File": "textures\\template_color.dds", "UseReplacement": False},
                "Normal": {"File": "textures\\template_normal.dds", "UseReplacement": False},
                "Roughness": {"File": "textures\\template_rough.dds", "UseReplacement": False},
            },
        }
    },
    "Version": 1,
}


WTHR_FIELD_SPEC: Tuple[Dict[str, Any], ...] = (
    {
        "subrecord": "EDID",
        "field": "editor_id",
        "value": DEFAULT_WEATHER_EDID,
        "source": "Our own clear temperate TESWeather record in FO4SFHome.esm (WB1; zero Starfield FormIDs)",
    },
    {
        "subrecord": "LNAM+MNAM+NNAM+CLDC",
        "field": "precipitation_and_shader_refs",
        "value": "0x00000000 x 4",
        "source": "Cleared so zero Starfield SPGD precipitation, EFSH shader, or ARTO camera-mist form is referenced",
    },
    {
        "subrecord": "RNAM+QNAM+PNAM+JNAM",
        "field": "cloud_speed_and_alpha_tables",
        "value": "Neutral 0x7F wind speeds (32 B x 2), 0.0 cloud alphas (1024 B), 1.0 blend scalars (1024 B)",
        "source": "Cloudless clear-sky scalar tables (zero cloud STAT TNAM meshes attached)",
    },
    {
        "subrecord": "NAM0+NAM4+DALC[0..7]",
        "field": "time_of_day_sky_and_directional_ambient_rgb",
        "value": "Temperate clear daylight/dusk/night RGB ramps (608 B NAM0 + 8 x 24 B DALC) and 1.0 multipliers (128 B NAM4)",
        "source": "Authored temperate terrestrial daylight/sky RGB palette preventing uninitialised/DefaultWeather fallback",
    },
    {
        "subrecord": "FNAM+DATA+NAM1",
        "field": "fog_distances_and_weather_classification",
        "value": "FNAM far fog (near=500 m, far=180,000 m, pow=1.0, max=0.35), DATA pleasant=0x01 calm wind, NAM1=0xFFFFFFFF",
        "source": "Clear-horizon terrestrial visibility constants",
    },
    {
        "subrecord": "IMSP+HNAM+FLLD+GNAM+UNAM+VNAM+WNAM",
        "field": "imagespace_volumetric_flare_slots",
        "value": "IMSP=[0]*8, HNAM=[0]*8, GNAM=0x00000000, FLLD=1, UNAM=0, VNAM=1.0, WNAM=1.0",
        "source": "Zeroed Starfield IMGS, VOLI, and LENS FormID slots",
    },
)

CLMT_FIELD_SPEC: Tuple[Dict[str, Any], ...] = (
    {
        "subrecord": "EDID",
        "field": "editor_id",
        "value": DEFAULT_CLIMATE_EDID,
        "source": "Our own TESClimate record in FO4SFHome.esm (WB1)",
    },
    {
        "subrecord": "WLST",
        "field": "weather_list",
        "value": "[(FO4SFHomeClearWeather 0x01000807, chance=100, global=0x00000000)] (omitted in 'ours_empty' mode)",
        "source": "100% weight on our own clear temperate WTHR (zero Starfield WTHR/WTHS references)",
    },
    {
        "subrecord": "TNAM",
        "field": "sun_glare_and_day_phase_timings_5b",
        "value": "sunrise 05:00..09:00 (0x1E, 0x36), sunset 17:00..21:00 (0x66, 0x7E), volatility/moons = 0x00",
        "source": "24 h terrestrial sunrise/sunset phase bytes (10-minute units)",
    },
)

ATMO_FIELD_SPEC: Tuple[Dict[str, Any], ...] = (
    {
        "subrecord": "EDID",
        "field": "editor_id",
        "value": DEFAULT_ATMO_EDID,
        "source": "Our own standalone root BGSAtmosphere record in FO4SFHome.esm (WB1; zero RFDP parent)",
    },
    {
        "subrecord": "REFL/Scattering",
        "field": "rayleigh_and_mie_scattering",
        "value": {
            "Height_m": 80000,
            "UseCustomCoefficients": True,
            "MoleculesPerUnitVolume": 5.545e25,
            "RefractiveIndexOfAir": 1.0003,
            "DepolarizationFactor": 0.035,
            "OzoneAbsorptionCoef": [0.1294, 0.3765, 0.0157, 1.0],
            "RayleighCoef": [0.0745, 0.1961, 0.3725, 1.0],
            "AerosolDensity": 1.0,
            "AerosolAbsorbtion": 0.1,
            "MieCoef": [0.3961, 0.3961, 0.3961, 1.0],
            "AerosolPhaseFunction": 0.76,
            "ScatteringScale": 0.9,
            "EdgeEffectExponent": 2.0,
            "EdgeEffectCoefficient": 1.0,
        },
        "source": "Terrestrial clear blue O2/N2 physical scattering constants packed via our pure-Python BETH v8 REFL encoder",
    },
    {
        "subrecord": "REFL/Stars+CelestialBodies",
        "field": "sky_background_and_illuminance_scalars",
        "value": {
            "PlanetStarfieldBackgroundScale": 100.0,
            "PlanetStarfieldBackgroundGIContribution": 1.0,
            "PlanetStarfieldStarBrightnessScale": 3.0,
            "PlanetStarGlowBackgroundScale": 0.0,
            "HorizonScatteringBlendScale": 0.8,
            "CelestialBodyIlluminanceScale": 0.03,
        },
        "source": "Day/night starfield attenuation scalars",
    },
    {
        "subrecord": "REFL/Overrides+Misc",
        "field": "external_form_pointers_and_resources",
        "value": {
            "pParent": "0x00000000",
            "pSunPresetOverride": "0x00000000",
            "AtmosphereType": "AT_TYPE_OXYGEN",
            "InorganicResources": [],
            "pImageSpaceDay": "0x00000000",
            "pImageSpaceNight": "0x00000000",
            "pClimateOverride": "0x00000000",
        },
        "source": "All five TESForm* pointers set to NULL and InorganicResources emptied so zero Starfield form is referenced",
    },
)

LTEX_FIELD_SPEC: Tuple[Dict[str, Any], ...] = (
    {
        "subrecord": "EDID",
        "field": "editor_id",
        "value": DEFAULT_GROUND_LTEX_EDID,
        "source": "Our own outer-ring LTEX record in FO4SFHome.esm (WB2; never references FO4WG1RedRocket.esm)",
    },
    {
        "subrecord": "BNAM",
        "field": "material_path",
        "value": f"Materials\\Terrain\\{DEFAULT_GROUND_LTEX_EDID}.mat",
        "source": "Terrain1Layer.mat JSON generated by fo4sf.terrain.ltex_map.build_terrain_mat from converted FO4 dirt PBR maps",
    },
    {
        "subrecord": "MNAM+HNAM+QNAM",
        "field": "physics_material_type_and_friction",
        "value": "MNAM = MaterialDirtlSand (MATT physics trait), HNAM = 0x1E1E, QNAM = 0",
        "source": "Physics footstep/friction trait resolved by EditorID from Starfield.esm",
    },
)

WB3_OVERRIDE_SPEC: Tuple[Dict[str, Any], ...] = (
    {
        "record": "WRLD (FO4TerrainCore_Home.esm override)",
        "subrecord": "CNAM",
        "value": "FO4SFHomeClimate (0x01000808) when --climate starts with 'ours'",
        "status": "untested",
        "why": "Replaces inherited null climate with our own clear temperate climate",
    },
    {
        "record": "WRLD (FO4TerrainCore_Home.esm override)",
        "subrecord": "ZNAM",
        "value": "_NONE (Starfield.esm silent Wwise MUSC resolved by EditorID)",
        "status": "untested",
        "why": "Suppresses default Starfield planet/exploration music in the Commonwealth overlay",
    },
    {
        "record": "WRLD (FO4TerrainCore_Home.esm override)",
        "subrecord": "NAM3+NAM4+DNAM",
        "value": "NAM3 = FO4SFHomeDryWater (0x0100080C), NAM4 = -200.0, DNAM = (-120.0, -200.0)",
        "status": "untested",
        "why": "Removes LC172World's Starfield.esm WaterClear (0x00000018) and aligns dry floor with Commonwealth BTD",
    },
    {
        "record": "WRLD (FO4TerrainCore_Home.esm override)",
        "subrecord": "MNAM+ONAM+FULL",
        "value": "MNAM = (6400, 6400, -32, 31, 31, -32), ONAM = (1.0, 0, 0, 0), FULL = 'Commonwealth'",
        "status": "untested",
        "why": "Replaces LC172World's zeroed map bounds and temporary 'Commonwealth 00 (FO4 terrain)' label",
    },
    {
        "record": "LCTN (FO4TerrainCore_Home.esm override)",
        "subrecord": "DATA+FULL",
        "value": "DATA = 0000000000000000 (min=0, max=0), FULL = 'Commonwealth'",
        "status": "untested",
        "why": "Clears LC172WorldLocation's inherited max_level = 16 encounter level cap",
    },
)


def _rgba(r: int, g: int, b: int, a: int = 0) -> bytes:
    return struct.pack("<BBBB", r & 0xFF, g & 0xFF, b & 0xFF, a & 0xFF)


def build_home_weather(formid: int, edid: str = DEFAULT_WEATHER_EDID) -> esm.Record:
    """Author `FO4SFHomeClearWeather` (`WTHR`) field-by-field with zero external `Starfield.esm` FormIDs (`WB1`)."""
    # NAM0: 19 color slots x 8 time-of-day phases x 4 RGBA bytes = 608 B.
    # Phases: Sunrise, Day, Sunset, Night, EarlySunrise, LateSunrise, EarlySunset, LateSunset.
    temperate_phase_rgb = (
        (188, 170, 152),  # Sunrise
        (214, 226, 240),  # Day
        (196, 162, 138),  # Sunset
        (24, 30, 42),     # Night
        (120, 126, 145),  # EarlySunrise
        (202, 208, 222),  # LateSunrise
        (204, 178, 156),  # EarlySunset
        (56, 64, 82),     # LateSunset
    )
    nam0_rows: List[bytes] = []
    for slot_idx in range(19):
        scale = 0.65 if slot_idx in (3, 10, 11) else 1.0  # softer ambient/fog slots vs sky/sunlight slots
        for r, g, b in temperate_phase_rgb:
            nam0_rows.append(_rgba(int(r * scale), int(g * scale), int(b * scale), 0))
    nam0 = b"".join(nam0_rows)
    assert len(nam0) == 608

    nam4 = struct.pack("<32f", *([1.0] * 32))  # 128 B
    # FNAM: 18 floats (72 B): day/night near/far fog, power, max
    fnam = struct.pack(
        "<18f",
        500.0, 180000.0,   # day near, day far
        500.0, 140000.0,   # night near, night far
        1.0, 1.0,          # day power, night power
        0.35, 0.35,        # day max, night max
        0.0, 180000.0,     # high-alt day near/far
        0.0, 140000.0,     # high-alt night near/far
        1.0, 1.0,
        0.35, 0.35,
        1.0, 1.0,
    )
    # DATA: 20 B (wind speed=16, cloud=0, trans_delta=25, sun_glare=127, sun_damage=0, precip=0, classify=0x01 pleasant, lightning RGB)
    data_20b = bytes([
        16, 0, 0, 25, 127, 0,
        0, 255, 0, 255, 0, 1,
        219, 220, 238, 0,
        0, 15, 43, 48,
    ])
    # 8 DALC directional ambient cubes (6 RGBX axes = 24 B per time-of-day phase)
    dalc_subs: List[Tuple[bytes, bytes]] = []
    for r, g, b in temperate_phase_rgb:
        axis_lo = _rgba(max(8, r // 4), max(8, g // 4), max(10, b // 4), 0)
        axis_hi = _rgba(max(14, r // 2), max(14, g // 2), max(18, b // 2), 0)
        dalc_subs.append((b"DALC", axis_lo + axis_hi + axis_lo + axis_hi + axis_lo + axis_hi))

    subs: List[Tuple[bytes, bytes]] = [
        (b"EDID", esm.zbytes(edid)),
        (b"LNAM", struct.pack("<I", 0)),
        (b"MNAM", struct.pack("<I", 0)),
        (b"NNAM", struct.pack("<I", 0)),
        (b"CLDC", struct.pack("<I", 0)),
        (b"RNAM", bytes([0x7F] * 32)),
        (b"QNAM", bytes([0x7F] * 32)),
        (b"PNAM", bytes(1024)),
        (b"JNAM", struct.pack("<256f", *([1.0] * 256))),
        (b"NAM0", nam0),
        (b"NAM4", nam4),
        (b"FNAM", fnam),
        (b"DATA", data_20b),
        (b"NAM1", struct.pack("<I", 0xFFFFFFFF)),
        (b"IMSP", struct.pack("<8I", *([0] * 8))),
        (b"HNAM", struct.pack("<8I", *([0] * 8))),
        *dalc_subs,
        (b"FLLD", struct.pack("<I", 1)),
        (b"GNAM", struct.pack("<I", 0)),
        (b"UNAM", bytes(24)),
        (b"VNAM", struct.pack("<f", 1.0)),
        (b"WNAM", struct.pack("<f", 1.0)),
    ]
    return esm.Record(b"WTHR", formid, subs, flags=0, vc=0, version=FORM_VERSION, unknown=0)


def build_home_climate(
    formid: int,
    weather_formid: Optional[int] = None,
    edid: str = DEFAULT_CLIMATE_EDID,
) -> esm.Record:
    """Author `FO4SFHomeClimate` (`CLMT`) field-by-field (`WB1`).
    When `weather_formid` is given (default `ours`), binds 100% weight to `FO4SFHomeClearWeather`;
    when `None` (`ours_empty`), writes an empty weather list (`EDID` + `TNAM` only)."""
    subs: List[Tuple[bytes, bytes]] = [(b"EDID", esm.zbytes(edid))]
    if weather_formid is not None:
        subs.append((b"WLST", struct.pack("<III", weather_formid, 100, 0)))
    # TNAM (5 B): sunrise 05:00..09:00 (30, 54), sunset 17:00..21:00 (102, 126), volatility/moons = 0
    subs.append((b"TNAM", bytes([0x1E, 0x36, 0x66, 0x7E, 0x00])))
    return esm.Record(b"CLMT", formid, subs, flags=0, vc=0, version=FORM_VERSION, unknown=0)


# BETH v8 reflection primitive type tags (verified against Starfield.esm AtmoDefaultMedium 0x0020CDD3)
_BETH_PRIM_BOOL = -0xF0          # 0xFFFFFF10 (1 B)
_BETH_PRIM_FLOAT = -0xEF         # 0xFFFFFF11 (4 B)
_BETH_PRIM_UINT32 = -0xF3        # 0xFFFFFF0D (4 B)
_BETH_PRIM_STRING = -0xFE        # 0xFFFFFF02 (u16 len + zstr)
_BETH_PRIM_LIST = -0xFD          # 0xFFFFFF03 (16 B in-struct list header; payload in LIST chunk)
_BETH_PRIM_FORM_PTR = -0xFB      # 0xFFFFFF05 (8 B in-struct ptr; serialized as 0xFFFFFF0D + u32 FormID)
_BETH_FORM_REF_TAG = 0xFFFFFF0D  # null/form marker inside OBJT


def _pack_beth_chunk(tag: bytes, payload: bytes) -> bytes:
    return tag + struct.pack("<I", len(payload)) + payload


def encode_bgs_atmosphere_refl(
    *,
    height_m: int = 80000,
    use_custom_coefficients: bool = True,
    molecules_per_m3: float = 5.545e25,
    refractive_index: float = 1.0003,
    depolarization: float = 0.035,
    use_ozone_approx: bool = False,
    ozone_coef: Tuple[float, float, float, float] = (0.1294, 0.3765, 0.0157, 1.0),
    rayleigh_coef: Tuple[float, float, float, float] = (0.0745, 0.1961, 0.3725, 1.0),
    aerosol_density: float = 1.0,
    aerosol_absorption: float = 0.1,
    mie_coef: Tuple[float, float, float, float] = (0.3961, 0.3961, 0.3961, 1.0),
    aerosol_phase_g: float = 0.76,
    scattering_scale: float = 0.9,
    edge_exponent: float = 2.0,
    edge_coef: float = 1.0,
    bg_scale: float = 100.0,
    bg_gi: float = 1.0,
    star_brightness: float = 3.0,
    star_glow: float = 0.0,
    horizon_blend: float = 0.8,
    disable_sim_vis: bool = False,
    static_vis: float = 0.0,
    illuminance_scale: float = 0.03,
    atmosphere_type: str = "AT_TYPE_OXYGEN",
) -> bytes:
    """Encode a complete standalone `BETH` v8 `REFL` stream for `BGSAtmosphere` from pure scalar parameters (`WB1`),
    with all five external `TESForm*` pointers set to `0x00000000` and `InorganicResources` empty (`0` items)."""
    strings = [
        "BGSAtmosphere",
        "BGSAtmosphere::AtmosphereSettings",
        "pParent",
        "BGSAtmosphere::ScatteringSettings",
        "Height",
        "UseCustomCoefficients",
        "BGSAtmosphere::ScatteringSettings::RayleighSettings",
        "MoleculesPerUnitVolume",
        "RefractiveIndexOfAir",
        "DepolarizationFactor",
        "UseOzoneAbsorptionApproximation",
        "XMFLOAT4",
        "x",
        "y",
        "z",
        "w",
        "OzoneAbsorptionCoef",
        "RayleighCoef",
        "Rayleigh",
        "BGSAtmosphere::ScatteringSettings::MieSettings",
        "AerosolDensity",
        "AerosolAbsorbtion",
        "MieCoef",
        "Mie",
        "AerosolPhaseFunction",
        "ScatteringScale",
        "EdgeEffectExponent",
        "EdgeEffectCoefficient",
        "Scattering",
        "BGSAtmosphere::StarSettings",
        "PlanetStarfieldBackgroundScale",
        "PlanetStarfieldBackgroundGIContribution",
        "PlanetStarfieldStarBrightnessScale",
        "PlanetStarGlowBackgroundScale",
        "HorizonScatteringBlendScale",
        "DisableSimulatedVisibility",
        "StaticVisibility",
        "Stars",
        "BGSAtmosphere::CelestialBodySettings",
        "CelestialBodyIlluminanceScale",
        "CelestialBodies",
        "BGSAtmosphere::OverrideSettings",
        "pSunPresetOverride",
        "Overrides",
        "BGSAtmosphere::MiscSettings",
        "AtmosphereType",
        "InorganicResources",
        "pImageSpaceDay",
        "pImageSpaceNight",
        "pClimateOverride",
        "Misc",
        "Settings",
    ]
    str_offsets: Dict[str, int] = {}
    strt_buf = bytearray()
    for s in strings:
        str_offsets[s] = len(strt_buf)
        strt_buf.extend(s.encode("ascii") + b"\x00")

    def t_ref(type_or_class: int | str) -> int:
        return type_or_class if isinstance(type_or_class, int) else str_offsets[type_or_class]

    def build_clas(class_name: str, flags: int, fields: Sequence[Tuple[str, int | str, int, int]]) -> bytes:
        head = struct.pack("<IIHH", str_offsets[class_name], 0, flags, len(fields))
        body = b"".join(
            struct.pack("<IiHH", str_offsets[fname], t_ref(ftype), foff, fsz)
            for fname, ftype, foff, fsz in fields
        )
        return _pack_beth_chunk(b"CLAS", head + body)

    clas_chunks = [
        build_clas("XMFLOAT4", 8, [("x", _BETH_PRIM_FLOAT, 0, 4), ("y", _BETH_PRIM_FLOAT, 4, 4), ("z", _BETH_PRIM_FLOAT, 8, 4), ("w", _BETH_PRIM_FLOAT, 12, 4)]),
        build_clas("BGSAtmosphere::CelestialBodySettings", 0, [("CelestialBodyIlluminanceScale", _BETH_PRIM_FLOAT, 0, 4)]),
        build_clas(
            "BGSAtmosphere::AtmosphereSettings",
            0,
            [
                ("pParent", _BETH_PRIM_FORM_PTR, 0, 8),
                ("Scattering", "BGSAtmosphere::ScatteringSettings", 8, 96),
                ("Stars", "BGSAtmosphere::StarSettings", 104, 28),
                ("CelestialBodies", "BGSAtmosphere::CelestialBodySettings", 132, 4),
                ("Overrides", "BGSAtmosphere::OverrideSettings", 136, 8),
                ("Misc", "BGSAtmosphere::MiscSettings", 144, 48),
            ],
        ),
        build_clas("BGSAtmosphere::OverrideSettings", 0, [("pSunPresetOverride", _BETH_PRIM_FORM_PTR, 0, 8)]),
        build_clas(
            "BGSAtmosphere::ScatteringSettings::MieSettings",
            0,
            [
                ("AerosolDensity", _BETH_PRIM_FLOAT, 0, 4),
                ("AerosolAbsorbtion", _BETH_PRIM_FLOAT, 4, 4),
                ("MieCoef", "XMFLOAT4", 8, 16),
            ],
        ),
        build_clas(
            "BGSAtmosphere::ScatteringSettings::RayleighSettings",
            0,
            [
                ("MoleculesPerUnitVolume", _BETH_PRIM_FLOAT, 0, 4),
                ("RefractiveIndexOfAir", _BETH_PRIM_FLOAT, 4, 4),
                ("DepolarizationFactor", _BETH_PRIM_FLOAT, 8, 4),
                ("UseOzoneAbsorptionApproximation", _BETH_PRIM_BOOL, 12, 1),
                ("OzoneAbsorptionCoef", "XMFLOAT4", 16, 16),
                ("RayleighCoef", "XMFLOAT4", 32, 16),
            ],
        ),
        build_clas("BGSAtmosphere", 0, [("Settings", "BGSAtmosphere::AtmosphereSettings", 280, 192)]),
        build_clas(
            "BGSAtmosphere::MiscSettings",
            0,
            [
                ("AtmosphereType", _BETH_PRIM_STRING, 0, 4),
                ("InorganicResources", _BETH_PRIM_LIST, 8, 16),
                ("pImageSpaceDay", _BETH_PRIM_FORM_PTR, 24, 8),
                ("pImageSpaceNight", _BETH_PRIM_FORM_PTR, 32, 8),
                ("pClimateOverride", _BETH_PRIM_FORM_PTR, 40, 8),
            ],
        ),
        build_clas(
            "BGSAtmosphere::StarSettings",
            0,
            [
                ("PlanetStarfieldBackgroundScale", _BETH_PRIM_FLOAT, 0, 4),
                ("PlanetStarfieldBackgroundGIContribution", _BETH_PRIM_FLOAT, 4, 4),
                ("PlanetStarfieldStarBrightnessScale", _BETH_PRIM_FLOAT, 8, 4),
                ("PlanetStarGlowBackgroundScale", _BETH_PRIM_FLOAT, 12, 4),
                ("HorizonScatteringBlendScale", _BETH_PRIM_FLOAT, 16, 4),
                ("DisableSimulatedVisibility", _BETH_PRIM_BOOL, 20, 1),
                ("StaticVisibility", _BETH_PRIM_FLOAT, 24, 4),
            ],
        ),
        build_clas(
            "BGSAtmosphere::ScatteringSettings",
            0,
            [
                ("Height", _BETH_PRIM_UINT32, 0, 4),
                ("UseCustomCoefficients", _BETH_PRIM_BOOL, 4, 1),
                ("Rayleigh", "BGSAtmosphere::ScatteringSettings::RayleighSettings", 8, 48),
                ("Mie", "BGSAtmosphere::ScatteringSettings::MieSettings", 56, 24),
                ("AerosolPhaseFunction", _BETH_PRIM_FLOAT, 80, 4),
                ("ScatteringScale", _BETH_PRIM_FLOAT, 84, 4),
                ("EdgeEffectExponent", _BETH_PRIM_FLOAT, 88, 4),
                ("EdgeEffectCoefficient", _BETH_PRIM_FLOAT, 92, 4),
            ],
        ),
    ]

    atmo_type_z = atmosphere_type.encode("ascii") + b"\x00"
    null_ptr = struct.pack("<II", _BETH_FORM_REF_TAG, 0)
    objt_payload = b"".join(
        [
            struct.pack("<I", str_offsets["BGSAtmosphere"]),
            null_ptr,  # pParent = NULL
            struct.pack("<IB", int(height_m), 1 if use_custom_coefficients else 0),
            struct.pack("<fffB", molecules_per_m3, refractive_index, depolarization, 1 if use_ozone_approx else 0),
            struct.pack("<4f", *ozone_coef),
            struct.pack("<4f", *rayleigh_coef),
            struct.pack("<ff", aerosol_density, aerosol_absorption),
            struct.pack("<4f", *mie_coef),
            struct.pack("<4f", aerosol_phase_g, scattering_scale, edge_exponent, edge_coef),
            struct.pack("<5fBf", bg_scale, bg_gi, star_brightness, star_glow, horizon_blend, 1 if disable_sim_vis else 0, static_vis),
            struct.pack("<f", illuminance_scale),
            null_ptr,  # pSunPresetOverride = NULL
            struct.pack("<H", len(atmo_type_z)) + atmo_type_z,
            null_ptr,  # pImageSpaceDay = NULL
            null_ptr,  # pImageSpaceNight = NULL
            null_ptr,  # pClimateOverride = NULL
        ]
    )
    # Empty InorganicResources list (element type = _BETH_PRIM_FORM_PTR, count = 0)
    empty_list_payload = struct.pack("<iI", _BETH_PRIM_FORM_PTR, 0)

    chunks = [
        _pack_beth_chunk(b"STRT", bytes(strt_buf)),
        _pack_beth_chunk(b"TYPE", struct.pack("<I", len(clas_chunks))),
        *clas_chunks,
        _pack_beth_chunk(b"OBJT", objt_payload),
        _pack_beth_chunk(b"LIST", empty_list_payload),
    ]
    return b"BETH" + struct.pack("<3I", 8, 4, len(chunks)) + b"".join(chunks)


def inspect_beth_refl_formids(refl: bytes) -> List[int]:
    """Extract every non-zero `0xFFFFFF0D <u32 FormID>` pointer serialized inside `OBJT`/`DIFF`/`LIST` chunks
    of a `BETH` v8 `REFL`/`RDIF` buffer (skipping `STRT`/`TYPE`/`CLAS` schema descriptors)."""
    if len(refl) < 16 or refl[:4] != b"BETH":
        return []
    out: List[int] = []
    marker = struct.pack("<I", _BETH_FORM_REF_TAG)
    _ver, _u1, nchunks = struct.unpack_from("<3I", refl, 4)
    pos = 16
    for _ in range(nchunks):
        if pos + 8 > len(refl):
            break
        tag = refl[pos : pos + 4]
        sz, = struct.unpack_from("<I", refl, pos + 4)
        payload = refl[pos + 8 : pos + 8 + sz]
        pos += 8 + sz
        if tag in (b"OBJT", b"DIFF"):
            p = 0
            while True:
                idx = payload.find(marker, p)
                if idx < 0 or idx + 8 > len(payload):
                    break
                fid, = struct.unpack_from("<I", payload, idx + 4)
                if fid != 0:
                    out.append(fid)
                p = idx + 8
        elif tag == b"LIST" and len(payload) >= 8:
            elem_type, elem_count = struct.unpack_from("<iI", payload, 0)
            if elem_type == _BETH_PRIM_FORM_PTR and elem_count > 0:
                p = 8
                for _i in range(elem_count):
                    if p + 8 <= len(payload):
                        t_marker, fid = struct.unpack_from("<II", payload, p)
                        if t_marker == _BETH_FORM_REF_TAG and fid != 0:
                            out.append(fid)
                        p += 8
    return out


def build_home_atmosphere(formid: int, edid: str = DEFAULT_ATMO_EDID) -> esm.Record:
    """Author `FO4SFHomeAtmosphere` (`ATMO`) field-by-field (`WB1`) with zero external FormID pointers."""
    refl = encode_bgs_atmosphere_refl()
    subs = [
        (b"EDID", esm.zbytes(edid)),
        (b"REFL", refl),
    ]
    return esm.Record(b"ATMO", formid, subs, flags=0, vc=0, version=FORM_VERSION, unknown=0)


def build_home_ground_ltex(
    formid: int,
    matt_dirt_fid: int,
    edid: str = DEFAULT_GROUND_LTEX_EDID,
) -> esm.Record:
    """Author `FO4SFHomeGroundDirt01` (`LTEX`) in `FO4SFHome.esm` (`WB2`)."""
    subs = [
        (b"EDID", esm.zbytes(edid)),
        (b"BNAM", esm.zbytes(f"Materials\\Terrain\\{edid}.mat")),
        (b"MNAM", struct.pack("<I", matt_dirt_fid)),
        (b"HNAM", struct.pack("<H", 0x1E1E)),
        (b"QNAM", struct.pack("<I", 0)),
    ]
    return esm.Record(b"LTEX", formid, subs, flags=0, vc=0, version=FORM_VERSION, unknown=0)


def build_home_empty_surface_tree(formid: int, edid: str = DEFAULT_SURFACE_TREE_EDID) -> esm.Record:
    """Author an empty 2-face `256 x 256` `SFTR` record in `FO4SFHome.esm` with zero Starfield `SFPT` references (`WB2`)."""
    zero_fnam = bytes(65536 * 4)
    zero_gnam = bytes(65536)
    subs = [
        (b"EDID", esm.zbytes(edid)),
        (b"CNAM", struct.pack("<I", 2)),
        (b"DNAM", struct.pack("<I", 256)),
        (b"FNAM", zero_fnam),
        (b"GNAM", zero_gnam),
        (b"FNAM", zero_fnam),
        (b"GNAM", zero_gnam),
        (b"NAM1", esm.zbytes("FO4SFHome\\")),
    ]
    return esm.Record(b"SFTR", formid, subs, flags=0, vc=0, version=FORM_VERSION, unknown=0)


def build_home_water(formid: int, edid: str = DEFAULT_WATER_EDID) -> esm.Record:
    """Author a neutral `WATR` record in `FO4SFHome.esm` with zero Starfield spell/sound/material references (`WB3`)."""
    # 38 floats = 152 B neutral calm water optical/wave constants
    dnam = struct.pack(
        "<38f",
        8.0, 0.165, 0.096, 0.076, 8.84, 6.59, 4.71, 0.514,
        1.0, 0.5, 0.2, 0.0, 0.0, 0.0, 1.0, 1.0,
        0.1, 0.1, 0.1, 1.0, 10.0, 50.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    )
    subs = [
        (b"EDID", esm.zbytes(edid)),
        (b"FULL", esm.zbytes("Water")),
        (b"ANAM", bytes([0x50])),
        (b"FNAM", bytes([0x00])),
        (b"WASH", bytes(40)),
        (b"DATA", b""),
        (b"DNAM", dnam),
        (b"GNAM", bytes(12)),
        (b"NAM0", bytes(12)),
        (b"NAM1", bytes(12)),
    ]
    return esm.Record(b"WATR", formid, subs, flags=0, vc=0, version=FORM_VERSION, unknown=0)


def _synthetic_dds_4x4_rgba(rgba: Tuple[int, int, int, int]) -> bytes:
    """Build a valid 192-byte uncompressed 4x4 RGBA8 DDS image for offline/unit-test staging without game archives."""
    header = bytearray(124)
    struct.pack_into("<IIIIIII", header, 0, 124, 0x1007, 4, 4, 16, 0, 0)
    # DDS_PIXELFORMAT at offset 72 (size=32, flags=0x41 DDPF_RGB|DDPF_ALPHAPIXELS, bitcount=32, masks)
    struct.pack_into("<IIIIIIII", header, 72, 32, 0x41, 0, 32, 0x000000FF, 0x0000FF00, 0x00FF0000, 0xFF000000)
    struct.pack_into("<I", header, 104, 0x1000)  # DDSCAPS_TEXTURE
    pixels = struct.pack("<BBBB", *rgba) * 16
    return b"DDS " + bytes(header) + pixels


def stage_home_ground_assets(
    stage_dir: str,
    edid: str = DEFAULT_GROUND_LTEX_EDID,
    ground_source_dir: str = "",
) -> Dict[str, Any]:
    """Write `Data/materials/terrain/<edid>.mat` + converted Fallout 4 `_color`/`_normal`/`_rough` `.dds` files
    into `stage_dir` using `fo4sf.terrain.ltex_map.build_terrain_mat` (`WB2`).

    When `ground_source_dir` points to an existing converted texture stage (e.g. a `WG1` or batch texture folder),
    copies one converted Fallout 4 Commonwealth ground texture triplet (never referencing `FO4WG1RedRocket.esm`).
    When `ground_source_dir` is empty (synthetic CI unit tests), generates deterministic minimal `.dds` + `.mat`
    files so tests run with zero game files."""
    stem = edid.lower()
    rel_color = f"textures/fo4sfhome/landscape/ground/{stem}_color.dds"
    rel_normal = f"textures/fo4sfhome/landscape/ground/{stem}_normal.dds"
    rel_rough = f"textures/fo4sfhome/landscape/ground/{stem}_rough.dds"
    rel_mat = f"materials/terrain/{edid}.mat"

    dst_color = os.path.join(stage_dir, "Data", *rel_color.split("/"))
    dst_normal = os.path.join(stage_dir, "Data", *rel_normal.split("/"))
    dst_rough = os.path.join(stage_dir, "Data", *rel_rough.split("/"))
    dst_mat = os.path.join(stage_dir, "Data", *rel_mat.split("/"))
    for p in (dst_color, dst_normal, dst_rough, dst_mat):
        os.makedirs(os.path.dirname(p), exist_ok=True)

    source_kind = "synthetic_dds"
    template_mat: Dict[str, Any] = MINIMAL_TERRAIN1LAYER_TEMPLATE

    if ground_source_dir:
        src_abs = os.path.abspath(ground_source_dir)
        manifest_cand = os.path.join(src_abs, "wg1_ltex_manifest.json")
        if os.path.isfile(manifest_cand):
            with open(manifest_cand, encoding="utf-8") as mf:
                mdoc = json.load(mf)
            first = mdoc["entries"][0]
            src_mat_p = os.path.join(src_abs, *first["mat_file"].split("/"))
            if os.path.isfile(src_mat_p):
                with open(src_mat_p, encoding="utf-8") as smf:
                    template_mat = json.load(smf)
            shutil.copyfile(os.path.join(src_abs, *first["textures"]["color"].split("/")), dst_color)
            shutil.copyfile(os.path.join(src_abs, *first["textures"]["normal"].split("/")), dst_normal)
            shutil.copyfile(os.path.join(src_abs, *first["textures"]["rough"].split("/")), dst_rough)
            source_kind = f"converted_fo4:{first.get('fo4_ltex', 'Fallout4.esm:000000')}"
        else:
            # Direct folder containing *_color.dds, *_normal.dds, *_rough.dds
            found_c = sorted(
                os.path.join(r, fn)
                for r, _ds, fs in os.walk(src_abs)
                for fn in fs
                if fn.lower().endswith("_color.dds")
            )
            if not found_c:
                raise FileNotFoundError(f"No *_color.dds found in --ground-source-dir {ground_source_dir}")
            c_src = found_c[0]
            base_prefix = c_src[: -len("_color.dds")]
            n_src = base_prefix + "_normal.dds"
            r_src = base_prefix + "_rough.dds"
            if not (os.path.isfile(n_src) and os.path.isfile(r_src)):
                raise FileNotFoundError(f"Missing matching _normal.dds / _rough.dds beside {c_src}")
            shutil.copyfile(c_src, dst_color)
            shutil.copyfile(n_src, dst_normal)
            shutil.copyfile(r_src, dst_rough)
            source_kind = "converted_fo4_dir"
    else:
        with open(dst_color, "wb") as f:
            f.write(_synthetic_dds_4x4_rgba((112, 94, 74, 255)))
        with open(dst_normal, "wb") as f:
            f.write(_synthetic_dds_4x4_rgba((128, 128, 255, 255)))
        with open(dst_rough, "wb") as f:
            f.write(_synthetic_dds_4x4_rgba((210, 210, 210, 255)))

    mat_doc = lm.build_terrain_mat(template_mat, edid, rel_color, rel_normal, rel_rough)
    mat_bytes = (json.dumps(mat_doc, indent=2) + "\n").encode("utf-8")
    with open(dst_mat, "wb") as f:
        f.write(mat_bytes)

    files_rel = [
        f"Data/{rel_mat}",
        f"Data/{rel_color}",
        f"Data/{rel_normal}",
        f"Data/{rel_rough}",
    ]
    return {
        "edid": edid,
        "source_kind": source_kind,
        "mat_file": f"Data/{rel_mat}",
        "mat_sha256": hashlib.sha256(mat_bytes).hexdigest(),
        "files": files_rel,
    }


def encode_bgs_sun_preset_refl(
    *,
    sun_color: Tuple[float, float, float, float] = (0.9882353, 0.9882353, 0.92941177, 1.0),
    sun_illuminance: float = 20000.0,
    sun_glare_color: Tuple[float, float, float, float] = (0.99215686, 0.99215686, 0.9647059, 1.0),
    sun_disk_texture: str = "",
    disk_size_min: float = 0.02,
    disk_size_max: float = 0.0345,
    dawn_color: Tuple[float, float, float, float] = (0.90588236, 0.7490196, 0.61960787, 1.0),
    dawn_start_angle: float = 50.0,
    dawn_end_angle: float = 80.0,
    night_color: Tuple[float, float, float, float] = (0.3137255, 0.47058824, 0.7058824, 1.0),
    night_illuminance: float = 100.0,
    night_glare_color: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
) -> bytes:
    """Encode a standalone `BETH` v8 `REFL` stream for `BSGalaxy::BGSSunPresetForm` with `pParent = NULL`
    and `SunDiskTexture = ""` so zero `Starfield.esm` FormID or texture is referenced."""
    strings = [
        "BSGalaxy::BGSSunPresetForm",
        "pParent",
        "XMFLOAT4",
        "x",
        "y",
        "z",
        "w",
        "SunColor",
        "SunIlluminance",
        "SunGlareColor",
        "SunDiskTexture",
        "SunDiskScreenSizeMin",
        "SunDiskScreenSizeMax",
        "BSGalaxy::BGSSunPresetForm::DawnDuskSettings",
        "DirectionalColor",
        "TransitionStartAngle",
        "TransitionEndAngle",
        "DuskDawnPreset",
        "BSGalaxy::BGSSunPresetForm::NightSettings",
        "DirectionalIlluminance",
        "GlareColor",
        "NightPreset",
    ]
    str_offsets: Dict[str, int] = {}
    strt_buf = bytearray()
    for s in strings:
        str_offsets[s] = len(strt_buf)
        strt_buf.extend(s.encode("ascii") + b"\x00")

    def t_ref(type_or_class: int | str) -> int:
        return type_or_class if isinstance(type_or_class, int) else str_offsets[type_or_class]

    def build_clas(class_name: str, flags: int, fields: Sequence[Tuple[str, int | str, int, int]]) -> bytes:
        head = struct.pack("<IIHH", str_offsets[class_name], 0, flags, len(fields))
        body = b"".join(
            struct.pack("<IiHH", str_offsets[fname], t_ref(ftype), foff, fsz)
            for fname, ftype, foff, fsz in fields
        )
        return _pack_beth_chunk(b"CLAS", head + body)

    clas_chunks = [
        build_clas(
            "BSGalaxy::BGSSunPresetForm::NightSettings",
            0,
            [
                ("DirectionalColor", "XMFLOAT4", 0, 16),
                ("DirectionalIlluminance", _BETH_PRIM_FLOAT, 16, 4),
                ("GlareColor", "XMFLOAT4", 20, 16),
            ],
        ),
        build_clas(
            "BSGalaxy::BGSSunPresetForm",
            0,
            [
                ("pParent", _BETH_PRIM_FORM_PTR, 280, 8),
                ("SunColor", "XMFLOAT4", 288, 16),
                ("SunIlluminance", _BETH_PRIM_FLOAT, 304, 4),
                ("SunGlareColor", "XMFLOAT4", 308, 16),
                ("SunDiskTexture", _BETH_PRIM_STRING, 328, 8),
                ("SunDiskScreenSizeMin", _BETH_PRIM_FLOAT, 336, 4),
                ("SunDiskScreenSizeMax", _BETH_PRIM_FLOAT, 340, 4),
                ("DuskDawnPreset", "BSGalaxy::BGSSunPresetForm::DawnDuskSettings", 344, 24),
                ("NightPreset", "BSGalaxy::BGSSunPresetForm::NightSettings", 368, 36),
            ],
        ),
        build_clas(
            "XMFLOAT4",
            8,
            [("x", _BETH_PRIM_FLOAT, 0, 4), ("y", _BETH_PRIM_FLOAT, 4, 4), ("z", _BETH_PRIM_FLOAT, 8, 4), ("w", _BETH_PRIM_FLOAT, 12, 4)],
        ),
        build_clas(
            "BSGalaxy::BGSSunPresetForm::DawnDuskSettings",
            0,
            [
                ("DirectionalColor", "XMFLOAT4", 0, 16),
                ("TransitionStartAngle", _BETH_PRIM_FLOAT, 16, 4),
                ("TransitionEndAngle", _BETH_PRIM_FLOAT, 20, 4),
            ],
        ),
    ]
    tex_z = sun_disk_texture.encode("ascii") + b"\x00"
    null_ptr = struct.pack("<II", _BETH_FORM_REF_TAG, 0)
    objt_payload = b"".join(
        [
            struct.pack("<I", str_offsets["BSGalaxy::BGSSunPresetForm"]),
            null_ptr,
            struct.pack("<4f", *sun_color),
            struct.pack("<f", sun_illuminance),
            struct.pack("<4f", *sun_glare_color),
            struct.pack("<H", len(tex_z)) + tex_z,
            struct.pack("<ff", disk_size_min, disk_size_max),
            struct.pack("<4f", *dawn_color),
            struct.pack("<ff", dawn_start_angle, dawn_end_angle),
            struct.pack("<4f", *night_color),
            struct.pack("<f", night_illuminance),
            struct.pack("<4f", *night_glare_color),
        ]
    )
    chunks = [
        _pack_beth_chunk(b"STRT", bytes(strt_buf)),
        _pack_beth_chunk(b"TYPE", struct.pack("<I", len(clas_chunks))),
        *clas_chunks,
        _pack_beth_chunk(b"OBJT", objt_payload),
    ]
    return b"BETH" + struct.pack("<3I", 8, 4, len(chunks)) + b"".join(chunks)


def build_home_sun_preset(formid: int, edid: str = DEFAULT_SUN_PRESET_EDID) -> esm.Record:
    """Author `FO4SFHomeSunPreset` (`SUNP`) in `FO4SFHome.esm` with zero `Starfield.esm` FormID or texture pointers."""
    subs = [
        (b"EDID", esm.zbytes(edid)),
        (b"REFL", encode_bgs_sun_preset_refl()),
    ]
    return esm.Record(b"SUNP", formid, subs, flags=0, vc=0, version=FORM_VERSION, unknown=0)


def pndt_surface_tree_fnam(pndt_rec: esm.Record) -> Optional[bytes]:
    """Return `PNDT`'s 4-byte top-level `FNAM` (`SFTR` FormID) outside both `BFCB..BFCE` components and `BDST..BDED`."""
    in_comp = False
    in_body = False
    for sig, data in pndt_rec.subs:
        if sig == b"BFCB":
            in_comp = True
        elif sig == b"BFCE":
            in_comp = False
        elif sig == b"BDST":
            in_body = True
        elif sig == b"BDED":
            in_body = False
        elif not in_comp and not in_body and sig == b"FNAM":
            return data
    return None


_FAST_REF_GROUPS: Tuple[str, ...] = (
    "KYWD", "LCRT", "GLOB", "LTEX", "WTHR", "WTHS", "CLMT", "WATR", "MATT",
    "LCTN", "MUSC", "MUST", "BIOM", "ATMO", "SFBK", "SFPT", "SFTR", "PNDT",
    "STDT", "PTST", "SUNP", "TODD",
)


def collect_biom_and_pndt_references(
    sf: Optional[esm.Plugin],
    hm: esm.Plugin,
    home_master_name: str = "FO4SFHome.esm",
    fallback_sf_names: Optional[Mapping[int, Tuple[str, str]]] = None,
) -> List[Dict[str, Any]]:
    """Inspect every FormID that `FO4SFHome.esm`'s `BIOM` (`0x806`) and `PNDT` (`0x805`) point at
    (plus any transitive `CLMT -> WTHR/WTHS`, `ATMO -> RFDP/REFL`, and `LTEX -> MNAM` links inside `FO4SFHome.esm`),
    resolving each target's defining plugin, record signature, FormID, and `EditorID` (`WB1` / `WB2` check)."""
    sf_index: Dict[int, Tuple[str, str]] = dict(fallback_sf_names or {})
    if sf is not None:
        for grp in _FAST_REF_GROUPS:
            if grp in sf.groups:
                for r in sf.records(grp):
                    sf_index[r.formid & 0xFFFFFF] = (grp, r.edid)

    hm_index: Dict[int, Tuple[str, str]] = {}
    for grp in hm.groups:
        for r in hm.records(grp):
            hm_index[r.formid & 0xFFFFFF] = (grp, r.edid)

    def describe_fid(fid: int) -> Dict[str, str]:
        hi = fid >> 24
        lo = fid & 0xFFFFFF
        owner = hm.masters[hi] if hi < len(hm.masters) else home_master_name
        if owner.lower() == "starfield.esm":
            rtype, edid = sf_index.get(lo, ("UNKNOWN", ""))
        elif owner.lower() == home_master_name.lower():
            rtype, edid = hm_index.get(lo, ("UNKNOWN", ""))
        else:
            rtype, edid = ("EXTERNAL", "")
        return {
            "form_id": f"0x{fid:08X}",
            "owner": owner,
            "record_type": rtype,
            "edid": edid,
        }

    own = lambda loc_id: (len(hm.masters) << 24) | loc_id  # noqa: E731
    by_fid = {r.formid: r for grp in hm.groups for r in hm.records(grp)}
    biom_rec = by_fid[own(0x806)]
    pndt_rec = by_fid[own(0x805)]

    rows: List[Dict[str, Any]] = []

    # BIOM references: ENAM (climate), NNAM (pattern), LNAM[0..6] (slot_u32, ltex_fid, gcvr_fid), NAM2..NAM4 (density globals)
    for tag, label in (
        (b"ENAM", "climate"),
        (b"NNAM", "terrain_pattern"),
        (b"NAM2", "density_nam2"),
        (b"NAM3", "density_nam3"),
        (b"NAM4", "density_nam4"),
    ):
        raw = biom_rec.get(tag)
        if raw and len(raw) == 4:
            fid, = struct.unpack("<I", raw)
            if fid:
                rows.append({"record": "BIOM", "subrecord": tag.decode("ascii"), "field": label, **describe_fid(fid)})
    for idx, lnam in enumerate(biom_rec.all(b"LNAM")):
        if len(lnam) >= 12:
            slot_idx, ltex_fid, gcvr_fid = struct.unpack_from("<3I", lnam, 0)
            if ltex_fid:
                rows.append({"record": "BIOM", "subrecord": f"LNAM[{slot_idx}]", "field": "ground_ltex", **describe_fid(ltex_fid)})
            if gcvr_fid:
                rows.append({"record": "BIOM", "subrecord": f"LNAM[{slot_idx}].gcvr", "field": "ground_cover", **describe_fid(gcvr_fid)})

    # PNDT references: KWDA traits, PPBD biomes, top-level FNAM surface tree, BDST..BDED INAM atmosphere
    for kidx, kfid in enumerate(records.keywords_of(pndt_rec)):
        rows.append({"record": "PNDT", "subrecord": f"KWDA[{kidx}]", "field": "trait_keyword", **describe_fid(kfid)})
    for bidx, pb in enumerate(records.biomes(pndt_rec)):
        rows.append({"record": "PNDT", "subrecord": f"PPBD[{bidx}]", "field": "planet_biome", **describe_fid(pb["biome"])})
    top_fnam = pndt_surface_tree_fnam(pndt_rec)
    if top_fnam and len(top_fnam) == 4:
        sftr_fid, = struct.unpack("<I", top_fnam)
        if sftr_fid:
            rows.append({"record": "PNDT", "subrecord": "FNAM", "field": "surface_tree", **describe_fid(sftr_fid)})
    inam = records.body_get(pndt_rec.subs, b"INAM")
    if inam and len(inam) >= 4:
        atmo_fid, = struct.unpack_from("<I", inam, 0)
        if atmo_fid:
            rows.append({"record": "PNDT", "subrecord": "BDST..BDED/INAM", "field": "atmosphere", **describe_fid(atmo_fid)})

    # Transitive inspection of any FO4SFHome.esm CLMT, ATMO, or LTEX referenced by BIOM / PNDT
    clmt_raw = biom_rec.get(b"ENAM")
    if clmt_raw and len(clmt_raw) == 4:
        clmt_fid, = struct.unpack("<I", clmt_raw)
        if clmt_fid in by_fid and by_fid[clmt_fid].sig == b"CLMT":
            crec = by_fid[clmt_fid]
            for wtag, wlabel in ((b"WLST", "climate_weather"), (b"WSLT", "climate_weather_settings")):
                for wbuf in crec.all(wtag):
                    for off in range(0, len(wbuf) - (len(wbuf) % 12), 12):
                        wfid, _chance, gfid = struct.unpack_from("<3I", wbuf, off)
                        if wfid:
                            rows.append({"record": "CLMT", "subrecord": wtag.decode("ascii"), "field": wlabel, **describe_fid(wfid)})
                        if gfid:
                            rows.append({"record": "CLMT", "subrecord": f"{wtag.decode('ascii')}.global", "field": "weather_global", **describe_fid(gfid)})

    if inam and len(inam) >= 4:
        atmo_fid, = struct.unpack_from("<I", inam, 0)
        if atmo_fid in by_fid and by_fid[atmo_fid].sig == b"ATMO":
            arec = by_fid[atmo_fid]
            rfdp = arec.get(b"RFDP")
            if rfdp and len(rfdp) == 4:
                pfid, = struct.unpack("<I", rfdp)
                if pfid:
                    rows.append({"record": "ATMO", "subrecord": "RFDP", "field": "atmo_parent", **describe_fid(pfid)})
            for rtag in (b"REFL", b"RDIF"):
                rbuf = arec.get(rtag)
                if rbuf:
                    for rfid in inspect_beth_refl_formids(rbuf):
                        rows.append({"record": "ATMO", "subrecord": rtag.decode("ascii"), "field": "atmo_refl_ptr", **describe_fid(rfid)})

    seen_ltex: set[int] = set()
    for lnam in biom_rec.all(b"LNAM"):
        if len(lnam) >= 12:
            _, ltex_fid, _ = struct.unpack_from("<3I", lnam, 0)
            if ltex_fid in by_fid and by_fid[ltex_fid].sig == b"LTEX" and ltex_fid not in seen_ltex:
                seen_ltex.add(ltex_fid)
                mnam = by_fid[ltex_fid].get(b"MNAM")
                if mnam and len(mnam) == 4:
                    mfid, = struct.unpack("<I", mnam)
                    if mfid:
                        rows.append({"record": "LTEX", "subrecord": "MNAM", "field": "physics_material_type", **describe_fid(mfid)})

    return rows
