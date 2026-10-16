"""Fallout 4 exterior lights -> Starfield LIGH records (docs/terrain/exterior-lights.md).

Reads FO4 LIGH bases and the light fields of placed light references straight from Fallout4.esm with fo4land's raw
record walker (no Mutagen), and maps them to the fields dotnet/TerrainOverlays writes onto a copy of one vanilla
Starfield light. Every mapping rule below names its evidence; the doc has the full table.

FO4 LIGH (Fallout4.esm, raw, checked field by field against Mutagen.Bethesda.Fallout4 0.55 on the 146 Commonwealth
exterior bases): OBND 6 x i16 (units); MODL; DATA 60 or 64 bytes = i32 time, u32 radius (units), RGBA colour, u32 flags,
f32 falloff exponent, FOV, near clip (units), flicker period, flicker intensity amplitude, flicker movement amplitude
(units), constant, scalar, exponent, god rays near clip, u32 value[, f32 weight]; FNAM f32 fade (the intensity
multiplier); NAM0 gobo texture; LNAM lens flare; WGDR god rays; SNAM sound.
FO4 light REFR: XRDS f32 = radius DELTA in units (5,834 Commonwealth light refs carry it; none equals its base radius,
the smallest is -0.981 x the base: a delta, never an absolute radius), XLIG = f32 FOV delta, fade delta, end distance
cap, shadow depth bias, near clip delta, volumetric intensity (16 to 24 bytes), XEMI emittance.
"""
import math
import struct

from . import fo4land

UNITS_PER_METRE = 70.0              # the project's FO4 -> Starfield scale (positions are FO4 / 70 m)

# FO4 DATA flags (Mutagen.Bethesda.Fallout4 Light.Flag, raw DATA offset 12)
F4_DYNAMIC = 0x1
F4_CAN_BE_CARRIED = 0x2
F4_FLICKER = 0x8
F4_OFF_BY_DEFAULT = 0x20
F4_PULSE = 0x80
F4_SHADOW_SPOT = 0x400
F4_SHADOW_HEMI = 0x800
F4_SHADOW_OMNI = 0x1000
F4_NONSHADOW_SPOT = 0x4000
F4_NON_SPECULAR = 0x8000
F4_ATTENUATION_ONLY = 0x10000
F4_NONSHADOW_BOX = 0x20000
F4_IGNORE_ROUGHNESS = 0x40000
F4_NO_RIM = 0x80000
F4_AMBIENT_ONLY = 0x100000
F4_FLAG_NAMES = {F4_DYNAMIC: "dynamic", F4_CAN_BE_CARRIED: "can be carried", F4_FLICKER: "flicker",
                 F4_OFF_BY_DEFAULT: "off by default", F4_PULSE: "pulse", F4_SHADOW_SPOT: "shadow spotlight",
                 F4_SHADOW_HEMI: "shadow hemisphere", F4_SHADOW_OMNI: "shadow omnidirectional",
                 F4_NONSHADOW_SPOT: "non-shadow spotlight", F4_NON_SPECULAR: "non specular",
                 F4_ATTENUATION_ONLY: "attenuation only", F4_NONSHADOW_BOX: "non-shadow box",
                 F4_IGNORE_ROUGHNESS: "ignore roughness", F4_NO_RIM: "no rim lighting", F4_AMBIENT_ONLY: "ambient only"}

# Starfield DAT2 flags (Mutagen.Bethesda.Starfield Light.Flag). Bit 0x1 has no Mutagen name; 1,560 of the 1,575
# Starfield.esm LIGH records set it, and of the 21 LIGH records Starfield.esm shares with Fallout4.esm (same FormID and
# EditorID) every one whose FO4 flags have 0x1 (FO4's "dynamic") has it in Starfield, while every other FO4 bit is
# cleared (scripts/terrain/light_census.py): FO4's bit 0x1 is carried as it is.
SF_DYNAMIC = 0x1
SF_CAN_BE_CARRIED = 0x2
SF_OFF_BY_DEFAULT = 0x20
SF_DISABLE_SPECULAR = 0x40
# Starfield DAT2 light type and flicker effect (Mutagen enums LightType / FlickerEffectOption, raw DAT2 bytes 56 / 57)
SF_OMNI, SF_SHADOW_SPOT, SF_NONSHADOW_SPOT = 0, 1, 2
SF_FLICKER_NONE, SF_FLICKER, SF_PULSE = 0, 1, 2
# record header flag both Mutagen schemas name Random Anim Start
RANDOM_ANIM_START = 0x10000

# Intensity. FO4 lights are colour x fade (FNAM); Starfield lights carry a luminous power in lumens (DAT2 offset 52:
# LGT_*_2k = 2000, _8k = 8000, _75k = 75000 in Starfield.esm) and no fade field. Over the 4,712 placements of vanilla
# omnidirectional lights in exterior cells, base lumens / base radius^2 has the median 333 lm/m^2 (p25 78, p75 1,667):
# lumens = LUMENS_PER_M2 x FO4 fade x radius_m^2 keeps a FO4 light as bright as a typical vanilla exterior light of its
# size (supported hypothesis; tune after a night screenshot, make_cluster.py lights --lumens-per-m2).
LUMENS_PER_M2 = 333.0
# Starfield REFR XLIG fade: over 28,070 vanilla exterior light REFRs it is never 0 or negative and lies in [0.01, 1.6]
# (median 0.45): a multiplier, not FO4's +/- delta (supported hypothesis). A FO4 reference's own intensity (base fade
# + its XLIG delta, relative to the base fade: ref_intensity) spans 0.08 to 15 (p1, p99) over the Commonwealth, wider
# than that range, so one LIGH per FO4 base takes the MEDIAN intensity of its references into its lumens and each
# reference keeps intensity / median as its XLIG fade, clamped to the vanilla range (826 of 6,249 clamp, against
# 1,612 when the base keeps its own fade).
XLIG_FADE_MIN, XLIG_FADE_MAX = 0.01, 1.6


# ------------------------------------------------------------------------------------------------------------ reading
def parse_ligh(fields):
    """One FO4 LIGH record's fields [(sig, bytes)] -> dict (units as stored: radius, near clip and movement amplitude
    in FO4 units, angles in degrees)."""
    out = {"edid": "", "bounds": None, "model": None, "fade": None, "gobo": None, "lens": None, "god_rays": None,
           "sound": None, "data_size": 0}
    for sig, d in fields:
        if sig == b"EDID":
            out["edid"] = fo4land.zstring(d)
        elif sig == b"OBND" and len(d) >= 12:
            out["bounds"] = list(struct.unpack_from("<6h", d))
        elif sig == b"MODL":
            out["model"] = fo4land.zstring(d) or None
        elif sig == b"DATA" and len(d) >= 40:
            # older form versions stop early: 48 bytes (form version 95: no exponent, no god rays near clip), 60 (no
            # weight); a missing trailing value reads as 0, as Mutagen reads them
            t, radius = struct.unpack_from("<iI", d, 0)
            r, g, b, _a = d[8], d[9], d[10], d[11]
            flags, = struct.unpack_from("<I", d, 12)
            n = min((len(d) - 16) // 4, 10)
            (falloff, fov, near, fper, famp, fmov, const, scalar, expo, grnc) = \
                list(struct.unpack_from(f"<{n}f", d, 16)) + [0.0] * (10 - n)
            value, = struct.unpack_from("<I", d, 56) if len(d) >= 60 else (0,)
            weight, = struct.unpack_from("<f", d, 60) if len(d) >= 64 else (0.0,)
            out.update(time=t, radius=radius, color=[r, g, b], flags=flags, falloff=falloff, fov=fov, near_clip=near,
                       flicker_period=fper, flicker_intensity=famp, flicker_movement=fmov, constant=const,
                       scalar=scalar, exponent=expo, god_rays_near_clip=grnc, value=value, weight=weight,
                       data_size=len(d))
        elif sig == b"FNAM" and len(d) >= 4:
            out["fade"], = struct.unpack_from("<f", d)
        elif sig == b"NAM0":
            out["gobo"] = fo4land.zstring(d) or None
        elif sig == b"LNAM" and len(d) >= 4:
            out["lens"] = struct.unpack_from("<I", d)[0] or None
        elif sig == b"WGDR" and len(d) >= 4:
            out["god_rays"] = struct.unpack_from("<I", d)[0] or None
        elif sig == b"SNAM" and len(d) >= 4:
            out["sound"] = struct.unpack_from("<I", d)[0] or None
    if not out["data_size"]:
        raise ValueError(f"LIGH {out['edid'] or '?'} has no DATA")
    if out["fade"] is None:
        out["fade"] = 1.0                    # no FNAM: FO4's default fade (every one of the 146 exterior bases has one)
    return out


XLIG_KEYS = ("fov", "fade", "end_distance_cap", "shadow_depth_bias", "near_clip", "volumetric")


def parse_light_ref(fields):
    """A FO4 light REFR's fields -> {"base", "radius_delta" (units) or None, "lighting" {XLIG_KEYS} or None,
    "emittance"}. XLIG is 16, 20 or 24 bytes (Mutagen's Break0 / Break1); missing trailing values are 0."""
    out = {"base": None, "radius_delta": None, "lighting": None, "emittance": None}
    for sig, d in fields:
        if sig == b"NAME" and len(d) >= 4:
            out["base"] = struct.unpack_from("<I", d)[0]
        elif sig == b"XRDS" and len(d) >= 4:
            out["radius_delta"], = struct.unpack_from("<f", d)
        elif sig == b"XLIG" and len(d) >= 16:
            n = min(len(d) // 4, len(XLIG_KEYS))
            vals = list(struct.unpack_from(f"<{n}f", d)) + [0.0] * (len(XLIG_KEYS) - n)
            out["lighting"] = dict(zip(XLIG_KEYS, vals))
        elif sig == b"XEMI" and len(d) >= 4:
            out["emittance"] = struct.unpack_from("<I", d)[0] or None
    return out


def read_bases(plugin, fids):
    """{form id: parse_ligh(...) + "record_flags"} for the LIGH records of an open fo4land.Plugin whose id is in fids."""
    want = set(fids)
    span = plugin.top_group(b"LIGH")
    out = {}
    if span is None:
        return out
    for item in fo4land.iter_items(plugin.buf, span[0], span[1]):
        if item[0] == "GRUP":
            continue
        typ, off, flags, fid = item
        if typ == b"LIGH" and fid in want:
            rec = parse_ligh(fo4land.iter_subrecords(fo4land.record_data(plugin.buf, off)))
            rec["record_flags"] = flags
            out[fid] = rec
    return out


def read_refs(plugin, world_edid, fids):
    """{form id: parse_light_ref(...) + "flags"} for the REFRs of one worldspace (every block, cell and persistent
    child) whose id is in fids; only those records are decompressed."""
    want = set(fids)
    _wfid, start, end, _fields = plugin.find_world(world_edid)
    out = {}

    def walk(s, e):
        for item in fo4land.iter_items(plugin.buf, s, e):
            if item[0] == "GRUP":
                walk(item[1] + 24, item[2])
                continue
            typ, off, flags, fid = item
            if typ == b"REFR" and fid in want:
                r = parse_light_ref(fo4land.iter_subrecords(fo4land.record_data(plugin.buf, off)))
                r["flags"] = flags
                out[fid] = r
    walk(start, end)
    return out


# ------------------------------------------------------------------------------------------------------------ mapping
def _finite(*vals):
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in vals)


def ref_intensity(r, b):
    """A FO4 light reference's intensity relative to its base: (base fade + XLIG fade delta) / base fade, 1.0 without
    XLIG. FO4 adds the delta (no Commonwealth reference goes to or below 0: the smallest result is 0.019)."""
    lig = r.get("lighting")
    return (b["fade"] + lig["fade"]) / b["fade"] if lig else 1.0


def base_scale(intensities):
    """The intensity a LIGH base takes into its lumens: the median of its references' ref_intensity (1.0 for none)."""
    v = sorted(x for x in intensities if _finite(x) and x > 0)
    if not v:
        return 1.0
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2


def map_base(b, lumens_per_m2=LUMENS_PER_M2, scale=1.0):
    """(Starfield light fields or None, skip reason or None, [FO4 features not carried]) for one parse_ligh() result;
    scale: base_scale() of its references.

    Kept: time, colour (RGB, alpha 0), falloff exponent, FOV, flicker period and intensity amplitude (all copied as the
    21 LIGH records Starfield.esm shares with Fallout4.esm copy them); radius, near clip and flicker movement amplitude
    from units to metres; FO4's flicker / pulse flags to Starfield's flicker effect (as the vanilla
    LGT_*_Flicker lights); spot flags to the light type; off by default, can be carried, non specular to their
    Starfield flags; Random Anim Start; luminous power = LUMENS_PER_M2 x fade x scale x radius_m^2."""
    flags = int(b["flags"])
    if flags & F4_AMBIENT_ONLY:
        return None, "ambient_only", []
    if not _finite(b["fade"], float(b["radius"])) or b["fade"] <= 0 or b["radius"] <= 0:
        return None, "no_intensity", []
    radius_m = b["radius"] / UNITS_PER_METRE
    sf_flags = flags & F4_DYNAMIC                   # = SF_DYNAMIC
    if flags & F4_OFF_BY_DEFAULT:
        sf_flags |= SF_OFF_BY_DEFAULT
    if flags & F4_CAN_BE_CARRIED:
        sf_flags |= SF_CAN_BE_CARRIED
    if flags & F4_NON_SPECULAR:
        sf_flags |= SF_DISABLE_SPECULAR
    if flags & F4_SHADOW_SPOT:
        typ = SF_SHADOW_SPOT
    elif flags & F4_NONSHADOW_SPOT:
        typ = SF_NONSHADOW_SPOT
    else:
        typ = SF_OMNI
    effect = SF_PULSE if flags & F4_PULSE else SF_FLICKER if flags & F4_FLICKER else SF_FLICKER_NONE
    dropped = []
    carried = (F4_DYNAMIC | F4_CAN_BE_CARRIED | F4_FLICKER | F4_OFF_BY_DEFAULT | F4_PULSE | F4_SHADOW_SPOT
               | F4_NONSHADOW_SPOT | F4_NON_SPECULAR)
    for bit, name in sorted(F4_FLAG_NAMES.items()):
        if flags & bit and not bit & carried:
            dropped.append(f"flag {name}")
    if flags & ~sum(F4_FLAG_NAMES):
        dropped.append(f"flag bits 0x{flags & ~sum(F4_FLAG_NAMES):X}")
    if b.get("model"):
        dropped.append("model")
    for k in ("gobo", "lens", "god_rays", "sound"):
        if b.get(k):
            dropped.append(k.replace("_", " "))
    bounds = b.get("bounds") or [0] * 6
    if not _finite(scale) or scale <= 0:
        raise ValueError(f"LIGH {b.get('edid')}: scale {scale!r}")
    lumens = max(1, int(round(lumens_per_m2 * b["fade"] * scale * radius_m ** 2)))
    sf = {"time": int(b["time"]), "radius": round(radius_m, 6), "color": [int(c) for c in b["color"]], "flags": sf_flags,
          "type": typ, "falloff": float(b["falloff"]), "fov": float(b["fov"]),
          "near_clip": round(b["near_clip"] / UNITS_PER_METRE, 6),
          "flicker": [float(b["flicker_period"]), float(b["flicker_intensity"]),
                      round(b["flicker_movement"] / UNITS_PER_METRE, 6)],
          "flicker_effect": effect, "lumens": lumens,
          "bounds": [[round(v / UNITS_PER_METRE, 6) for v in bounds[:3]], [round(v / UNITS_PER_METRE, 6) for v in bounds[3:]]],
          "random_anim_start": bool(b.get("record_flags", 0) & RANDOM_ANIM_START)}
    return sf, None, dropped


def map_ref(r, b, scale=1.0):
    """A FO4 light reference's own light fields (parse_light_ref) against its base (parse_ligh) and the base's scale ->
    {"radius_delta" (metres) or None, "lighting" {"fov", "fade", "near_clip"} or None, "fade_clamped": bool}. XLIG's
    fade becomes ref_intensity / scale within XLIG_FADE_MIN..XLIG_FADE_MAX; FOV (degrees) and the near clip delta (to
    metres) are kept; FO4's end distance cap and volumetric intensity are 0 on every Commonwealth light. A reference
    without XLIG gets one (FOV and near clip deltas 0) when its base's scale is not 1, so that it keeps its own
    intensity rather than the base's median."""
    out = {"radius_delta": None, "lighting": None, "fade_clamped": False}
    if r.get("radius_delta") is not None and _finite(r["radius_delta"]):
        out["radius_delta"] = round(r["radius_delta"] / UNITS_PER_METRE, 6)
    lig = r.get("lighting")
    if lig or abs(scale - 1.0) > 1e-9:
        ratio = ref_intensity(r, b) / scale
        fade = min(max(ratio, XLIG_FADE_MIN), XLIG_FADE_MAX)
        out["fade_clamped"] = abs(fade - ratio) > 1e-9
        out["lighting"] = {"fov": round(float(lig["fov"]), 6) if lig else 0.0, "fade": round(fade, 6),
                           "near_clip": round(lig["near_clip"] / UNITS_PER_METRE, 6) if lig else 0.0}
    return out
