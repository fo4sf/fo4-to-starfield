"""Read-only survey of every Fallout 4 worldspace in the given plugins: cells, LAND heights, land textures (LTEX and
their grass lists), GRAS models and placed references by landscape family (trees, grass, plants, rocks, cliffs).
Next-phase research for every worldspace, DLC included (/mnt/project-files/research/next-phase/).

    py scripts/terrain/fo4_world_survey.py OUT_JSON Fallout4.esm [DLC*.esm ...]   (Fallout4.esm first)

Form keys are "<owner plugin>:<6 hex>" so DLC records that override or place Fallout4.esm bases resolve.
"""
import json, os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src"))
from fo4sf import fo4land as fl

CATS = (("tree", "landscape\\trees"), ("grass", "landscape\\grass"), ("plant", "landscape\\plants"),
        ("rock", "landscape\\rocks"), ("cliff", "landscape\\cliffs"))

def fields(buf, off):
    return list(fl.iter_subrecords(fl.record_data(buf, off)))

def first(fs, sig):
    return next((d for s, d in fs if s == sig), None)

def u32(d, o=0):
    return struct.unpack_from("I", d, o)[0]

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    out_path, plugins = argv[0], argv[1:]
    names = [os.path.basename(p) for p in plugins]
    bases, ltex, grass, txst, worlds = {}, {}, {}, {}, []
    def gkey(pi, masters, fid):
        mi = fid // 16777216
        owner = masters[mi] if mi != len(masters) else names[pi]
        return "%s:%06X" % (owner, fid % 16777216)
    for pi, path in enumerate(plugins):
        with fl.Plugin(path) as p:
            buf = p.buf
            hdr = fields(buf, 0)
            masters = [fl.zstring(d) for s, d in hdr if s == b"MAST"]
            for item in fl.iter_items(buf, p.body, len(buf)):
                if item[0] != "GRUP":
                    continue
                label = bytes(item[3])
                if label in (b"STAT", b"SCOL", b"MSTT", b"FLOR", b"TREE", b"LTEX", b"GRAS", b"TXST"):
                    for typ, off, _f, fid in fl.iter_items(buf, item[1] + 24, item[2]):
                        if typ == "GRUP":
                            continue
                        fs = fields(buf, off)
                        k = gkey(pi, masters, fid)
                        edid = fl.zstring(first(fs, b"EDID") or b"")
                        if label == b"LTEX":
                            t = first(fs, b"TNAM")
                            ltex[k] = {"edid": edid, "txst": gkey(pi, masters, u32(t)) if t else None,
                                       "grass": [gkey(pi, masters, u32(d)) for s, d in fs if s == b"GNAM"]}
                        elif label == b"GRAS":
                            grass[k] = {"edid": edid, "model": fl.zstring(first(fs, b"MODL") or b"")}
                        elif label == b"TXST":
                            txst[k] = {"edid": edid, "diffuse": fl.zstring(first(fs, b"TX00") or b"")}
                        else:
                            model = fl.zstring(first(fs, b"MODL") or b"").lower()
                            cat = next((c for c, m in CATS if m in model), "other")
                            bases[k] = (label.decode(), cat, edid)
                elif label == b"WRLD":
                    survey_worlds(buf, item[1] + 24, item[2], pi, masters, gkey, names[pi], worlds)
    for w in worlds:
        cats = {}
        for b, n in w.pop("ref_bases").items():
            t, c, _e = bases.get(b, ("?", "unknown", ""))
            key = c if t != "FLOR" else "flora"
            cats[key] = cats.get(key, 0) + n
            if c == "tree":
                w["tree_bases"][b] = n
        w["refs_by_category"] = cats
        w["tree_bases"] = dict(sorted(w["tree_bases"].items(), key=lambda kv: -kv[1])[:25])
        w["ltex_use"] = dict(sorted(w["ltex_use"].items(), key=lambda kv: -kv[1])[:40])
        w["ltex_named"] = {k: (ltex.get(k, {}).get("edid"), len(ltex.get(k, {}).get("grass", []))) for k in w["ltex_use"]}
    out = {"plugins": names, "worlds": worlds, "ltex": ltex, "grass": grass, "txst_used": {
        k: txst.get(k) for k in {v["txst"] for v in ltex.values() if v["txst"]}}}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    for w in worlds:
        print(w["plugin"], w["edid"], "parent", w["parent"], "cells", w["cells"], "land", w["land"],
              "z m", w["zmin_m"], w["zmax_m"], "x", w["xr"], "y", w["yr"], "refs", w["refs"], w["refs_by_category"])
    print("LTEX", len(ltex), "with grass", sum(1 for v in ltex.values() if v["grass"]), "GRAS", len(grass))
    return out

def survey_worlds(buf, start, end, pi, masters, gkey, pname, worlds):
    cur = None
    for item in fl.iter_items(buf, start, end):
        if item[0] == "GRUP":
            if item[4] == 1 and cur is not None:
                walk(buf, item[1] + 24, item[2], pi, masters, gkey, cur)
            continue
        typ, off, _f, fid = item
        if typ != b"WRLD":
            continue
        fs = fields(buf, off)
        par = first(fs, b"WNAM")
        cur = {"plugin": pname, "edid": fl.zstring(first(fs, b"EDID") or b""), "fid": gkey(pi, masters, fid),
               "parent": gkey(pi, masters, u32(par)) if par else None, "cells": 0, "land": 0,
               "zmin_m": None, "zmax_m": None, "xr": [None, None], "yr": [None, None], "refs": 0, "actors": 0,
               "ref_bases": {}, "tree_bases": {}, "ltex_use": {}}
        worlds.append(cur)

def walk(buf, start, end, pi, masters, gkey, w):
    for item in fl.iter_items(buf, start, end):
        if item[0] == "GRUP":
            walk(buf, item[1] + 24, item[2], pi, masters, gkey, w)
            continue
        typ, off, _f, fid = item
        if typ == b"CELL":
            xy = first(fields(buf, off), b"XCLC")
            if xy is not None and len(xy) != 0:
                x, y = struct.unpack_from("ii", xy)
                w["cells"] += 1
                w["xr"] = [x if w["xr"][0] is None else min(w["xr"][0], x), x if w["xr"][1] is None else max(w["xr"][1], x)]
                w["yr"] = [y if w["yr"][0] is None else min(w["yr"][0], y), y if w["yr"][1] is None else max(w["yr"][1], y)]
        elif typ == b"LAND":
            w["land"] += 1
            for s, d in fields(buf, off):
                if s == b"VHGT" and len(d) == max(len(d), fl.VHGT_MIN_SIZE):
                    z = fl.decode_vhgt(d) / 70.0
                    lo, hi = round(float(z.min()), 2), round(float(z.max()), 2)
                    w["zmin_m"] = lo if w["zmin_m"] is None else min(w["zmin_m"], lo)
                    w["zmax_m"] = hi if w["zmax_m"] is None else max(w["zmax_m"], hi)
                elif s in (b"BTXT", b"ATXT") and len(d) == max(len(d), 4):
                    k = gkey(pi, masters, u32(d))
                    w["ltex_use"][k] = w["ltex_use"].get(k, 0) + 1
        elif typ in (b"REFR", b"ACHR"):
            if typ == b"ACHR":
                w["actors"] += 1
                continue
            name = first(fields(buf, off), b"NAME")
            if name is not None:
                w["refs"] += 1
                k = gkey(pi, masters, u32(name))
                w["ref_bases"][k] = w["ref_bases"].get(k, 0) + 1

if __name__ == "__main__":
    main()
