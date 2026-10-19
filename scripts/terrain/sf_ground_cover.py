"""Read-only: how Starfield worldspaces get grass. For each named WRLD: its biome (BNAM), the biome's terrain data
(LNAM main / ANAM alternate entries: mask, land texture, ground cover), each ground cover's grasses and landscape
textures (GCVR GNAM / DNAM / LNAM), each grass's model and DNAM, each land texture's material (LTEX BNAM).
Field layout from xEdit's Starfield definitions (wbDefinitionsSF1.pas: BIOM, GCVR, GRAS, LTEX, WRLD); raw record walk
with fo4land's reader, so plugins with masters need no load order (Mutagen refuses ours without one).

    py scripts/terrain/sf_ground_cover.py OUT_JSON Starfield.esm [our.esm ...] --worlds akilacity,NewAtlantis,...

Form keys are "<owner plugin>:<6 hex>".
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src"))
from fo4sf import fo4land as fl  # noqa: E402

TYPES = (b"WRLD", b"BIOM", b"GCVR", b"GRAS", b"LTEX")


def read(plugins):
    """{type: {key: [(sig, bytes), ...]}} for the top-level records of TYPES (a WRLD's children are skipped)."""
    names = [os.path.basename(p) for p in plugins]
    recs = {t.decode(): {} for t in TYPES}
    keyers = []
    for pi, path in enumerate(plugins):
        with fl.Plugin(path) as p:
            masters = [fl.zstring(d) for s, d in fl.iter_subrecords(fl.record_data(p.buf, 0)) if s == b"MAST"]

            def key(fid, masters=masters, own=names[pi]):
                mi = fid // 16777216
                return "%s:%06X" % (masters[mi] if mi != len(masters) else own, fid % 16777216)
            keyers.append(key)
            for item in fl.iter_items(p.buf, p.body, len(p.buf)):
                if item[0] != "GRUP" or bytes(item[3]) not in TYPES:
                    continue
                for typ, off, _f, fid in fl.iter_items(p.buf, item[1] + 24, item[2]):
                    if typ != "GRUP":
                        recs[typ.decode()][key(fid)] = (pi, list(fl.iter_subrecords(fl.record_data(p.buf, off))))
    return recs, keyers


def edid(fields):
    return next((fl.zstring(d) for s, d in fields if s == b"EDID"), "")


def survey(plugins, worlds):
    recs, keyers = read(plugins)
    by_edid = {edid(f).lower(): (k, pi, f) for k, (pi, f) in recs["WRLD"].items()}

    def ref(pi, d, o=0):
        return keyers[pi](struct.unpack_from("I", d, o)[0])

    def name(kind, k):
        r = recs[kind].get(k)
        return edid(r[1]) if r else None

    out = {"worlds": {}, "biomes": {}, "ground_covers": {}, "grasses": {}, "land_textures": {},
           "totals": {k: len(v) for k, v in recs.items()}}
    for w in worlds:
        hit = by_edid.get(w.lower())
        if hit is None:
            out["worlds"][w] = None
            continue
        k, pi, f = hit
        bnam = next((d for s, d in f if s == b"BNAM" and len(d) == 4), None)
        data = next((d for s, d in f if s == b"DATA"), b"")
        out["worlds"][w] = {"form": k, "biome": ref(pi, bnam) if bnam else None,
                            "data_flags": data[0] if len(data) else None}
        if bnam:
            add_biome(out, recs, ref(pi, bnam), ref, name)
    return out


def add_biome(out, recs, bk, ref, name):
    if bk in out["biomes"] or bk not in recs["BIOM"]:
        return
    pi, f = recs["BIOM"][bk]
    terrain = []
    for s, d in f:
        if s in (b"LNAM", b"ANAM") and len(d) == 12:
            mask = struct.unpack_from("I", d)[0]
            lt, gc = ref(pi, d, 4), ref(pi, d, 8)
            null = struct.unpack_from("I", d, 8)[0] == 0
            terrain.append({"kind": "main" if s == b"LNAM" else "alternate", "mask": mask,
                            "land_texture": lt, "land_texture_edid": name("LTEX", lt),
                            "ground_cover": None if null else gc, "ground_cover_edid": None if null else name("GCVR", gc)})
            add_ltex(out, recs, lt)
            if not null:
                add_gcvr(out, recs, gc, ref, name)
    out["biomes"][bk] = {"edid": name("BIOM", bk), "terrain": terrain}


def add_ltex(out, recs, k):
    if k in out["land_textures"] or k not in recs["LTEX"]:
        return
    f = recs["LTEX"][k][1]
    out["land_textures"][k] = {"edid": edid(f), "material": next((fl.zstring(d) for s, d in f if s == b"BNAM"), None)}


def add_gcvr(out, recs, k, ref, name):
    if k in out["ground_covers"] or k not in recs["GCVR"]:
        return
    pi, f = recs["GCVR"][k]
    grasses, ltex, last = [], [], None
    for s, d in f:
        if s == b"GNAM" and len(d) == 4:
            last = {"grass": ref(pi, d), "grass_edid": name("GRAS", ref(pi, d)), "density": None}
            grasses.append(last)
            add_gras(out, recs, ref(pi, d))
        elif s == b"DNAM" and len(d) == 2 and last is not None:
            last["density"] = struct.unpack_from("h", d)[0]
        elif s == b"LNAM" and len(d) == 4:
            ltex.append(ref(pi, d))
            add_ltex(out, recs, ref(pi, d))
    yn = next((d for s, d in f if s == b"YNAM" and len(d) == 4), None)
    out["ground_covers"][k] = {"edid": edid(f), "grasses": grasses, "land_textures": ltex,
                               "painted_threshold": struct.unpack_from("f", yn)[0] if yn else None}


def add_gras(out, recs, k):
    if k in out["grasses"] or k not in recs["GRAS"]:
        return
    f = recs["GRAS"][k][1]
    dnam = next((d for s, d in f if s == b"DNAM"), b"")
    out["grasses"][k] = {"edid": edid(f), "model": next((fl.zstring(d) for s, d in f if s == b"MODL"), None),
                         "dnam_hex": bytes(dnam).hex()}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    worlds = []
    if "--worlds" in argv:
        i = argv.index("--worlds")
        worlds = [w for w in argv[i + 1].split(",") if w]
        del argv[i:i + 2]
    out_path, plugins = argv[0], argv[1:]
    for target in (out_path, out_path + ".tmp"):       # read-only: never write over an input
        for src in plugins:
            if os.path.normcase(os.path.realpath(target)) == os.path.normcase(os.path.realpath(src)) or (
                    os.path.exists(target) and os.path.samefile(target, src)):
                sys.exit(f"refused: output {target} is the input {src}; nothing written")
    out = survey(plugins, worlds)
    with open(out_path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    os.replace(out_path + ".tmp", out_path)
    for w, v in out["worlds"].items():
        b = out["biomes"].get(v["biome"]) if v and v["biome"] else None
        print(w, "missing" if v is None else f"{v['form']} biome {v['biome']} {b['edid'] if b else None} "
              f"DATA {v['data_flags']} terrain {len(b['terrain']) if b else 0}")
        for t in (b["terrain"] if b else []):
            print("   ", t["kind"], t["mask"], t["land_texture_edid"], t["ground_cover_edid"])
    for k, g in out["ground_covers"].items():
        print("GCVR", k, g["edid"], "grasses", [x["grass_edid"] for x in g["grasses"]], "ltex", len(g["land_textures"]),
              "threshold", g["painted_threshold"])
    for k, g in out["grasses"].items():
        print("GRAS", k, g["edid"], g["model"], g["dnam_hex"])
    print("totals", out["totals"])
    return out


if __name__ == "__main__":
    main()
