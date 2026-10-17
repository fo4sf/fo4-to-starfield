"""light_census.py: the vanilla evidence behind the FO4 -> Starfield light mapping (docs/terrain/exterior-lights.md),
recomputed from the masters' raw records (src/fo4sf/fo4land.py walker; no Mutagen, nothing written but --out).

    python scripts/terrain/light_census.py --sf-esm <Starfield.esm> [--fo4-esm <Fallout4.esm>] [--out census.json]

Starfield.esm: every LIGH's DAT2 (flag bits, light type, flicker effect, lumens), every REFR of a LIGH in an exterior
cell (inside a worldspace's exterior blocks) with its record flags, XRDS sign and XLIG fade / trailing words, and the
lumens / radius^2 of the omnidirectional bases weighted by those placements (LUMENS_PER_M2). With --fo4-esm: the LIGH
records both masters hold under the same FormID and EditorID, side by side (how Bethesda carried FO4 lights over).
Starfield DAT2 (76 bytes, offsets read on the vanilla records): i32 time, f32 radius (m), RGBA, u32 flags, f32 falloff
exponent, FOV, near clip, flicker period, flicker intensity, flicker movement, shadow offset, inner FOV, u32 (Mutagen:
PbrLightTemperatureK), u32 lumens, u8 type, u8 flicker effect, u8 adaptive, u8, f32 adaptive EC, EV100 min, max,
radius falloff exponent.
"""
import argparse
import json
import os
import struct
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
from fo4sf import fo4land, fo4light  # noqa: E402


def sf_dat2(d):
    """The fields of a Starfield LIGH DAT2 this census reads."""
    t, radius = struct.unpack_from("<if", d, 0)
    flags, = struct.unpack_from("<I", d, 12)
    falloff, fov, near, fper, famp, fmov = struct.unpack_from("<6f", d, 16)
    temp, lumens = struct.unpack_from("<II", d, 48)
    return {"time": t, "radius": radius, "color": list(d[8:11]), "flags": flags, "falloff": falloff, "fov": fov,
            "near_clip": near, "flicker": [fper, famp, fmov], "temperature_word": temp, "lumens": lumens,
            "type": d[56], "flicker_effect": d[57]}


def sf_lights(p):
    """{form id: {"edid", "record_flags", **sf_dat2}} of every Starfield LIGH."""
    s, e = p.top_group(b"LIGH")
    out = {}
    for item in fo4land.iter_items(p.buf, s, e):
        if item[0] == "GRUP":
            continue
        _typ, off, flags, fid = item
        edid, dat2, model = "", None, False
        for sig, d in fo4land.iter_subrecords(fo4land.record_data(p.buf, off)):
            if sig == b"EDID":
                edid = fo4land.zstring(d)
            elif sig == b"MODL" and fo4land.zstring(d):
                model = True
            elif sig == b"DAT2" and len(d) >= 58:
                dat2 = sf_dat2(d)
        if dat2:
            out[fid] = dict(dat2, edid=edid, record_flags=flags, model=model)
    return out


def exterior_light_refs(p, lights):
    """Every REFR of a LIGH inside a worldspace's exterior blocks: [(base fid, record flags, XRDS or None,
    XLIG bytes or None)]."""
    s, e = p.top_group(b"WRLD")
    out = []

    def walk(start, end, exterior):
        for item in fo4land.iter_items(p.buf, start, end):
            if item[0] == "GRUP":
                _g, off, gend, _label, gtype = item
                walk(off + 24, gend, exterior or gtype in (4, 5))
                continue
            typ, off, flags, _fid = item
            if typ != b"REFR" or not exterior:
                continue
            base, xrds, xlig = None, None, None
            for sig, d in fo4land.iter_subrecords(fo4land.record_data(p.buf, off)):
                if sig == b"NAME":
                    base = struct.unpack_from("<I", d)[0]
                elif sig == b"XRDS":
                    xrds = struct.unpack_from("<f", d)[0]
                elif sig == b"XLIG":
                    xlig = bytes(d)
            if base in lights:
                out.append((base, flags, xrds, xlig))
    walk(s, e, False)
    return out


def quantiles(v, qs=(0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0)):
    v = sorted(v)
    return {str(q): round(v[min(len(v) - 1, int(q * len(v)))], 6) for q in qs} if v else {}


def census(sf_esm, fo4_esm=None):
    with fo4land.Plugin(sf_esm) as p:
        lights = sf_lights(p)
        refs = exterior_light_refs(p, lights)
    rep = {"lights": len(lights),
           "flag_bits": {f"0x{1 << b:X}": sum(1 for v in lights.values() if v["flags"] & (1 << b)) for b in range(32)
                         if any(v["flags"] & (1 << b) for v in lights.values())},
           "types": dict(Counter(v["type"] for v in lights.values())),
           "flicker_effects": dict(Counter(v["flicker_effect"] for v in lights.values())),
           "with_model": sum(1 for v in lights.values() if v["model"])}
    placed = Counter(b for b, *_ in refs)
    per_m2 = [lights[b]["lumens"] / lights[b]["radius"] ** 2 for b, n in placed.items() for _ in range(n)
              if lights[b]["type"] == fo4light.SF_OMNI and lights[b]["radius"] > 0 and lights[b]["lumens"] > 0]
    xrds = [x for _b, _f, x, _l in refs if x is not None]
    xlig = [lg for *_r, lg in refs if lg is not None]
    fades = [struct.unpack_from("<f", lg, 4)[0] for lg in xlig if len(lg) >= 8]
    rep["exterior_refs"] = {
        "refs": len(refs), "bases": len(placed),
        "record_flag_bits": {f"0x{1 << b:X}": sum(1 for _b, f, *_r in refs if f & (1 << b)) for b in range(32)
                             if any(f & (1 << b) for _b, f, *_r in refs)},
        "xrds": len(xrds), "xrds_negative": sum(1 for x in xrds if x < 0),
        "xrds_over_base_radius": quantiles([x / lights[b]["radius"] for b, _f, x, _l in refs if x is not None
                                            and lights[b]["radius"] > 0]),
        "xlig": len(xlig), "xlig_sizes": dict(Counter(len(lg) for lg in xlig)),
        "xlig_fade": quantiles(fades), "xlig_fade_zero_or_negative": sum(1 for f in fades if f <= 0),
        "xlig_trailing_words": dict(Counter(lg[24:32].hex() for lg in xlig if len(lg) >= 32).most_common(4)),
        "omni_lumens_per_m2_by_placement": quantiles(per_m2), "omni_placements": len(per_m2)}
    if fo4_esm:
        with fo4land.Plugin(fo4_esm) as q:
            span = q.top_group(b"LIGH")
            fo4 = {}
            for item in fo4land.iter_items(q.buf, span[0], span[1]):
                if item[0] != "GRUP" and item[3] in lights:
                    b = fo4light.parse_ligh(fo4land.iter_subrecords(fo4land.record_data(q.buf, item[1])))
                    if b["edid"] == lights[item[3]]["edid"]:
                        fo4[item[3]] = b
        rep["shared_with_fallout4"] = [
            {"fid": f"{fid:06X}", "edid": b["edid"],
             "fo4": {"radius": b["radius"], "color": b["color"], "flags": f"0x{b['flags']:X}", "fade": b["fade"],
                     "near_clip": round(b["near_clip"], 4), "fov": b["fov"], "falloff": b["falloff"],
                     "flicker": [round(b["flicker_period"], 4), round(b["flicker_intensity"], 4), round(b["flicker_movement"], 4)]},
             "sf": {"radius": round(lights[fid]["radius"], 4), "color": lights[fid]["color"], "flags": f"0x{lights[fid]['flags']:X}",
                    "lumens": lights[fid]["lumens"], "near_clip": round(lights[fid]["near_clip"], 4), "fov": lights[fid]["fov"],
                    "falloff": lights[fid]["falloff"], "flicker": [round(v, 4) for v in lights[fid]["flicker"]],
                    "flicker_effect": lights[fid]["flicker_effect"], "type": lights[fid]["type"]}}
            for fid, b in sorted(fo4.items())]
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sf-esm", required=True)
    ap.add_argument("--fo4-esm", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    rep = census(a.sf_esm, a.fo4_esm or None)
    text = json.dumps(rep, indent=1)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
