"""Fallout 4 ground textures on the native Commonwealth terrain (docs/terrain/ground-textures.md).

    python scripts/terrain/ground_textures.py palette --fo4-data <FO4 Data> --sf-data <Starfield Data> --out <palette.json>
    python scripts/terrain/ground_textures.py suggest --palette <palette.json> [--out <suggest.json>]
    python scripts/terrain/ground_textures.py survey [--sf-data <Starfield Data>] [--out <survey.json>]
    python scripts/terrain/ground_textures.py build --from <staged exp2b2> --out <staging dir of variant t, e.g.
                                                    C:\\Modding\\staging\\terrain_exp2t> [--palette <palette.json>]
                                                    [--variants all|t,t0,ta,tb,tc] [--site day|source] [--replace]
    python scripts/terrain/ground_textures.py check --from <staged exp2b2> --out <same> [--variants ...]
    python scripts/terrain/ground_textures.py lighting --run <finished queue dir> [...] [--out <report.json>]

palette  average albedo of every FO4 land texture (TXST diffuse or its BGSM) and every Starfield LTEX (its .mat in the
         Creation Kit's ContentResources.zip -> albedo DDS, low mips only; TerrainSettingsComponent TilingDistance),
         plus 128 px previews next to the json; the mapping table (fo4sf.ground_map) was chosen with it. Written outside
         the repo (derived from game files).
suggest  nearest-colour Starfield candidate per FO4 land texture within its category, next to the frozen table, and a
         check that every Starfield FormID in ground_map (mapped LTEX and placeholders) is that EditorID's LTEX.
survey   LTEX tables of every vanilla BTD (Starfield and official add-on archives) and the BIOM LTEX references: table
         sizes, the six LDefault* placeholders, concrete LTEX per table, where the mapped textures occur.
build    reads the FO4 LAND texture layers (BTXT/ATXT/VTXT) of the BTD footprint, turns them into per-vertex weights,
         maps every FO4 LTEX to a vanilla Starfield LTEX, resamples onto the BTD grid and writes the BTD's texture
         sections (LTEX table, quadrant bytes, 3-bit alphas) for each experiment variant (VARIANTS: t0 control, ta / tb
         vanilla-shaped 11-entry tables, tc template + full mapping, t full mapping). Heights, header, cell min/max and
         LOD4 heights stay byte-identical to the source BTD (checked). Stages exp2b2's plugins, mask and params with the
         Mars registration moved to the daylight site (--site), a runner plan (the usual probes + four ground-type
         spots, "fresh": true), reference renders and a mapping report per variant.
check    re-reads every staged variant: heights identical to the source, table and quadrant layout, each spot's target
         share in the decoded view window and disk, plan, and that the Mars plugin differs only in its site entry.
lighting daylight / night per attempt of finished terrain queues (sky brightness of spawn.png).
"""
import argparse
import glob
import json
import math
import os
import shutil
import struct
import sys
import zipfile
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
from fo4sf import ba2, btd, fo4land, ground_map, landtex, texpreview  # noqa: E402
from fo4sf import terrain_grid as tg  # noqa: E402
from fo4sf.convert_material import parse_bgsm  # noqa: E402

TEXCONV = r"C:\Modding\tools\xedit\Edit Scripts\Texconvx64.exe"
WORLD = "FO4CW_Commonwealth"
BTD_NAME = WORLD + ".btd"
FO4_DEFAULT_DIFFUSE = r"Landscape\Ground\CommonwealthDefault01_d.dds"     # see ground_map.FO4_DEFAULT


def read_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def write_json(p, obj):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)


def edid(fields):
    return fo4land.zstring(next((d for s, d in fields if s == b"EDID"), b""))


# ------------------------------------------------------------------------------------------------------- records
def fo4_land_textures(fo4_esm):
    """{fid: {"edid", "txst", "diffuse" (TXST TX00 or ''), "bgsm" (TXST MNAM or '')}} for every FO4 LTEX."""
    with fo4land.Plugin(fo4_esm) as p:
        txst = {}
        for fid, f in p.group_records(b"TXST"):
            d = {s.decode(): fo4land.zstring(v) for s, v in f if s in (b"EDID", b"TX00", b"MNAM")}
            txst[fid] = d
        out = {}
        for fid, f in p.group_records(b"LTEX"):
            tn = next((struct.unpack_from("<I", d)[0] for s, d in f if s == b"TNAM" and len(d) == 4), 0)
            t = txst.get(tn, {})
            out[fid] = {"edid": edid(f), "txst": t.get("EDID", ""), "diffuse": t.get("TX00", ""),
                        "bgsm": t.get("MNAM", "")}
    return out


def sf_land_textures(sf_esm):
    """{fid: {"edid", "material"}} for every Starfield LTEX (BNAM = material file)."""
    out = {}
    with fo4land.Plugin(sf_esm) as p:
        for fid, f in p.group_records(b"LTEX"):
            out[fid] = {"edid": edid(f), "material": fo4land.zstring(next((d for s, d in f if s == b"BNAM"), b""))}
    return out


# ------------------------------------------------------------------------------------------------------- palette
class Archives:
    """Name -> archive index over several BA2 files (lower-case, forward slashes)."""

    def __init__(self, paths):
        self.arcs, self.where = [], {}
        for p in paths:
            try:
                a = ba2.Ba2(p)
            except ba2.Ba2Error:
                continue
            self.arcs.append(a)
            for n in a.names:
                self.where.setdefault(n.replace("\\", "/").lower(), a)

    def get(self, name):
        return self.where.get(name.replace("\\", "/").lower().lstrip("/"))


def texture_color(arcs, path, work):
    """(mean sRGB colour, small RGBA preview, full width in px) of a texture path ('textures/...'), or Nones."""
    a = arcs.get(path)
    if a is None:
        return None, None, None
    rgba = texpreview.decode_dds(texpreview.tail_dds(a, path, 128), TEXCONV, work)
    return texpreview.mean_color(rgba), rgba, a.entries[a.find(path)].width


def fo4_diffuse_path(t, mats):
    """'textures/...' diffuse of an FO4 LTEX entry (TXST TX00, else the BGSM's diffuse)."""
    if t["diffuse"]:
        return "textures/" + t["diffuse"]
    if t["bgsm"] and mats is not None:
        a = mats.get("materials/" + t["bgsm"])
        if a is not None:
            return "textures/" + parse_bgsm(a.read("materials/" + t["bgsm"].replace("/", "\\"))).diffuse
    return ""


def sf_albedo_path(material, zf, names):
    """(albedo texture 'textures/...', TerrainSettingsComponent TilingDistance or None) of a Starfield terrain
    material (.mat JSON in ContentResources.zip)."""
    m = material.replace("\\", "/")
    if not m.lower().startswith("materials/"):
        m = "materials/" + m
    z = names.get(m.lower())
    if z is None:
        return "", None
    mat = json.loads(zf.read(z).decode("utf-8-sig"))
    tex = ((((mat.get("Summary") or {}).get("Layer1") or {}).get("Textures") or {}).get("Albedo") or {}).get("File", "")
    tiling = None
    for o in mat.get("Objects", []):
        for c in o.get("Components", []):
            if c.get("Type") == "BSMaterial::MRTextureFile" and c.get("Index") == 0 and not tex:
                tex = (c.get("Data") or {}).get("FileName", "")     # no summary: first albedo of the texture set
            if c.get("Type") == "BSMaterial::TerrainSettingsComponent" and tiling is None:
                try:
                    tiling = float((c.get("Data") or {}).get("TilingDistance"))
                except (TypeError, ValueError):
                    pass
    return tex.replace("\\", "/"), tiling


def palette(a):
    """Average colours (and 128 px previews next to palette.json, for the renders) of all FO4 and Starfield LTEX."""
    base = os.path.dirname(os.path.abspath(a.out))
    work, prev = os.path.join(base, "_palette_work"), os.path.join(base, "previews")
    os.makedirs(work, exist_ok=True)
    os.makedirs(prev, exist_ok=True)
    fo4_tex = Archives(sorted(glob.glob(os.path.join(a.fo4_data, "Fallout4 - Textures*.ba2"))))
    fo4_mat = Archives([os.path.join(a.fo4_data, "Fallout4 - Materials.ba2")])
    sf_tex = Archives(sorted(glob.glob(os.path.join(a.sf_data, "Starfield - Textures*.ba2"))))
    from PIL import Image

    def entry(arcs, path, side, name):
        col, rgba, width = texture_color(arcs, path, work) if path else (None, None, None)
        png = ""
        if rgba is not None:
            png = os.path.join(prev, f"{side}_{name}.png")
            Image.fromarray(rgba[..., :3]).save(png)
        return col, png, width

    out = {"fo4": {}, "sf": {}}
    for fid, t in sorted(fo4_land_textures(os.path.join(a.fo4_data, "Fallout4.esm")).items()):
        path = fo4_diffuse_path(t, fo4_mat)
        col, png, width = entry(fo4_tex, path, "fo4", t["edid"])
        out["fo4"][t["edid"]] = {"fid": "%08X" % fid, "txst": t["txst"], "diffuse": path, "color": col, "preview": png,
                                 "width": width}
    path = "textures/" + FO4_DEFAULT_DIFFUSE
    col, png, width = entry(fo4_tex, path, "fo4", "default")
    out["fo4"][ground_map.FO4_DEFAULT] = {"fid": "00000000", "diffuse": path, "color": col, "preview": png,
                                          "width": width}
    with zipfile.ZipFile(a.content_resources) as zf:
        names = {n.lower(): n for n in zf.namelist()}
        for fid, t in sorted(sf_land_textures(os.path.join(a.sf_data, "Starfield.esm")).items()):
            path, tiling = sf_albedo_path(t["material"], zf, names)
            col, png, width = entry(sf_tex, path, "sf", t["edid"])
            out["sf"][t["edid"]] = {"fid": "%08X" % fid, "material": t["material"], "albedo": path, "color": col,
                                    "preview": png, "width": width, "tiling_m": tiling}
    shutil.rmtree(work, ignore_errors=True)
    write_json(a.out, out)
    miss = [k for side in ("fo4", "sf") for k, v in out[side].items() if v["color"] is None]
    print(f"{len(out['fo4'])} FO4 and {len(out['sf'])} Starfield land textures; no colour for {len(miss)}: {miss[:12]}")


def suggest(a):
    """Nearest-colour Starfield candidate per FO4 land texture (within its category) next to the frozen MAP, and a
    check that every FormID in ground_map.SF_FORMID is the Starfield.esm LTEX of that EditorID."""
    pal = read_json(a.palette)
    sf = {v["edid"]: fid for fid, v in sf_land_textures(os.path.join(a.sf_data, "Starfield.esm")).items()}
    known = dict(ground_map.SF_FORMID, **ground_map.PLACEHOLDER_FORMID)
    bad = {k: ("%08X" % v, "%08X" % sf[k] if k in sf else None) for k, v in known.items() if sf.get(k) != v}
    rows = []
    for fo4, v in sorted(pal["fo4"].items()):
        cat = ground_map.category(fo4)
        cands = [(texpreview.delta_e(v["color"], pal["sf"][c]["color"]), c) for c in ground_map.SF_CANDIDATES[cat]
                 if v["color"] and pal["sf"].get(c, {}).get("color")]
        cands.sort()
        best = cands[0][1] if cands else None
        chosen = ground_map.sf_for(fo4)
        de = next((d for d, c in cands if c == chosen), None)
        rows.append({"fo4": fo4, "category": cat, "nearest": best,
                     "nearest_de": round(cands[0][0], 1) if cands else None,
                     "chosen": chosen, "chosen_de": round(de, 1) if de is not None else None,
                     "runner_up": [c for _, c in cands[1:3]]})
    for r in rows:
        flag = "" if r["nearest"] == r["chosen"] else "  <- differs"
        print(f"{r['fo4']:32s} {r['category']:8s} nearest {r['nearest']} ({r['nearest_de']})  chosen {r['chosen']} "
              f"({r['chosen_de']}){flag}")
    print("FormID mismatches:", bad or "none")
    if a.out:
        write_json(a.out, {"rows": rows, "formid_mismatches": bad})
    return 0 if not bad else 1


# ------------------------------------------------------------------------------------------------------- survey
def vanilla_archives(sf_data):
    """Starfield's own and the official add-on archives (Starfield - *.ba2, SFBGS*.ba2); experiment archives that an
    installer put into Data (FO4Terrain* - Main.ba2) are skipped."""
    return [p for p in sorted(glob.glob(os.path.join(sf_data, "*.ba2")))
            if os.path.basename(p).lower().startswith(("starfield - ", "sfbgs"))]


def btd_table(a, i):
    """LTEX FormIDs of BTD entry i of archive a; for an uncompressed entry only the header is read."""
    e = a.entries[i]
    if e.packed:
        b = a.read(i)
    else:
        with open(a.path, "rb") as f:
            f.seek(e.offset)
            b = f.read(0x2C)
            if b[:4] == btd.MAGIC:
                b += f.read(4 * struct.unpack_from("<I", b, 0x28)[0])
    if b[:4] != btd.MAGIC:
        return None
    n = struct.unpack_from("<I", b, 0x28)[0]
    return list(struct.unpack_from(f"<{n}I", b, 0x2C))


def biom_ltex_refs(sf_esm):
    """{LTEX FormID: number of BIOM entries naming it}. BIOM terrain data names land textures in LNAM and ANAM fields
    (u32 FormIDs; 2,943 + 2,059 = 5,002 entries in Starfield.esm 1.16.244)."""
    out = {}
    with fo4land.Plugin(sf_esm) as p:
        for _fid, fields in p.group_records(b"BIOM"):
            for s, d in fields:
                if s in (b"LNAM", b"ANAM") and len(d) >= 4 and len(d) % 4 == 0:
                    for v in struct.unpack(f"<{len(d) // 4}I", d):
                        out[v] = out.get(v, 0) + 1
    return out


def survey(a):
    """LTEX tables of every vanilla BTD (Starfield and official add-on archives) and BIOM references: table sizes,
    the six LDefault* placeholders, concrete LTEX per table, and where the exp2t textures occur."""
    ltex = {fid: v["edid"] for fid, v in sf_land_textures(os.path.join(a.sf_data, "Starfield.esm")).items()}
    biom = biom_ltex_refs(os.path.join(a.sf_data, "Starfield.esm"))
    ph = set(ground_map.PLACEHOLDERS)
    files = []
    for p in vanilla_archives(a.sf_data):
        try:
            arc = ba2.Ba2(p)
        except ba2.Ba2Error:
            continue
        for i, name in enumerate(arc.names):
            if not name.lower().endswith(".btd"):
                continue
            tab = btd_table(arc, i)
            if tab is None:
                continue
            nm = name.replace("\\", "/").lower()
            ed = [ltex.get(f, "%08X" % f) for f in tab]
            files.append({"archive": os.path.basename(p), "name": nm, "top_level": nm.count("/") == 1,
                          "table_size": len(tab), "table": ed,
                          "placeholders": sorted(ph & set(ed)), "placeholder_index": [k for k, e in enumerate(ed) if e in ph],
                          "concrete": [e for e in ed if e not in ph]})
    with_table = [f for f in files if f["table_size"]]
    sizes = {}
    for f in files:
        sizes[f["table_size"]] = sizes.get(f["table_size"], 0) + 1
    concrete = {}
    for f in with_table:
        for e in f["concrete"]:
            concrete.setdefault(e, []).append(f["name"])
    by_edid = {v: k for k, v in ltex.items()}
    ours = sorted(set(ground_map.MAP.values()) | {ground_map.MAP[ground_map.FO4_DEFAULT]})
    report = {
        "btd_files": len(files), "with_table": len(with_table),
        "top_level": sum(f["top_level"] for f in files), "top_level_with_table": sum(f["top_level"] for f in with_table),
        "top_level_with_footprints": sum(1 for f in with_table if f["top_level"] and "LDirtFootprints01" in f["table"]),
        "with_all_six_placeholders": sum(1 for f in with_table if len(f["placeholders"]) == 6),
        "table_sizes": dict(sorted(sizes.items())),
        "largest_tables": [(f["name"], f["table_size"]) for f in sorted(with_table, key=lambda f: -f["table_size"])[:8]],
        "concrete_ltex_in_tables": {k: {"files": len(v), "examples": sorted(set(v))[:4]} for k, v in sorted(concrete.items())},
        "biom_distinct_ltex": len(biom),
        "mapped_ltex": {e: {"in_btd_tables": len(concrete.get(e, [])), "biom_entries": biom.get(by_edid.get(e, -1), 0)}
                        for e in ours},
        "files": files}
    if a.out:
        write_json(a.out, report)
    print(f"{report['btd_files']} BTD files ({report['top_level']} top-level terrain/*.btd), {report['with_table']} with "
          f"an LTEX table ({report['top_level_with_table']} top-level, {report['top_level_with_footprints']} of those "
          f"with LDirtFootprints01); all six placeholders in {report['with_all_six_placeholders']}")
    print("table sizes:", report["table_sizes"])
    print("largest:", report["largest_tables"])
    print("concrete LTEX in vanilla tables:", {k: v["files"] for k, v in report["concrete_ltex_in_tables"].items()})
    m = report["mapped_ltex"]
    print(f"mapped LTEX ({len(m)}): in no vanilla BTD table {sum(1 for v in m.values() if not v['in_btd_tables'])}, "
          f"in no BIOM {sum(1 for v in m.values() if not v['biom_entries'])}, in neither "
          f"{[k for k, v in m.items() if not v['in_btd_tables'] and not v['biom_entries']]}")
    return 0


# ------------------------------------------------------------------------------------------------------- build
# Four places with known FO4 ground types for the in-game screenshots, nearest to Red Rocket. FO4 terrain textures only:
# exp2t has no statics, so FO4's road meshes and Red Rocket's concrete pad are absent and the terrain painted under them
# is what shows. In FO4 the road network is static meshes over terrain painted RubbleRock01 (the grey bands in
# reference/fo4_overview.png); Asphalt01 is painted on paved lots (the Red Rocket forecourt, parking areas).
# Each spot has ONE Starfield target (full mapping). Pre-filter: the FO4 textures that map to it cover the vertex's
# (2 radius + 1)^2 neighbourhood with at least `purity`. Test: on the decoded BTD the target holds at least
# VIEW_MIN_SHARE of the ground the probe screenshot looks at (VIEW_WINDOW) and of the DISK_M disk around the spot.
# (label, description, Starfield target LTEX, min distance from Red Rocket m, purity radius, purity)
SPOTS = [
    ("ground_road", "road bed (FO4 terrain RubbleRock01 under the road meshes)", "LGravelRoad01", 20.0, 2, 0.9),
    ("ground_lot", "paved lot (FO4 terrain Asphalt01: forecourt, parking area)", "LGravelDecorative01", 0.0, 1, 0.85),
    ("ground_grass", "dried grass (FO4 DriedGrass01)", "LGrassDeadWet01", 30.0, 2, 0.9),
    ("ground_dirt", "eroded dirt (FO4 RootsEroded01)", "LDirtPacked04", 30.0, 2, 0.9),
]
# qstep.ps1's terrain step screenshots every probe looking north (heading 0), pitched 15 degrees down, the eye about
# 1.7 m above the ground: the middle of the picture is the ground about 2..7 m north of the spot (6.3 m at the centre).
VIEW_WINDOW = (-3.0, 3.0, 2.0, 7.0)          # dx0, dx1, dy0, dy1 (m) from the spot
DISK_M = 6.0
VIEW_MIN_SHARE = 0.9
WINDOW_STEP_M = 0.25                          # FO4-side sampling of the window and the disk
SPOT_MAX_SLOPE = 10.0
SPOT_SEPARATION_M = 8.0
SPOT_MAX_ERROR_M = 0.05     # decoded BTD vs FO4 height / 70 at the spot, worst interpolation rule (runner: 0.5 m)
FO4_TILES_PER_CELL_AT_1024 = 16      # fo76utils render.md: ~16384 / 2^mip texels per FO4 cell (illustrative)
MIN_COVERAGE = 0.0005       # full mapping: an LTEX with less than 0.05 % of the BTD's weight is folded into the kept
                            # LTEX nearest in colour (palette; else the most common), so no table entry is near-empty

# Experiment variants (ground-textures.md 5). Each changes one thing against the one named in "vs"; all are registered
# at the same site. Built in BUILD_ORDER (t first: the spots come from its BTD).
VARIANTS = {
    "t0": {"suffix": "0", "template": "source", "fold": None, "vs": "exp2b2",
           "what": "control: exp2b2's BTD byte for byte (template table, LDirtFootprints01 everywhere)",
           "changes": "only the registration site (daylight)"},
    "ta": {"suffix": "a", "template": True, "fold": "ta", "vs": "t0",
           "what": "vanilla shape: exp2b2's 7-entry template table + 4 LTEX that vanilla gameplay BTDs carry (11 entries, "
                   "the size of akilacity's table)",
           "changes": "FO4 layers painted with 4 concrete LTEX in a vanilla-shaped table"},
    "tb": {"suffix": "b", "template": True, "fold": "tb", "vs": "ta",
           "what": "as ta, with 4 LTEX that no vanilla BTD table carries (all named by BIOMs; 11 entries)",
           "changes": "LTEX that no vanilla BTD uses"},
    "tc": {"suffix": "c", "template": True, "fold": None, "vs": "tb",
           "what": "exp2b2's template table + the full mapping",
           "changes": "table size (largest vanilla table 18, gameplay 11) and the full set of mapped LTEX"},
    "t": {"suffix": "", "template": False, "fold": None, "vs": "tc",
          "what": "the full mapping only, no placeholders (the original exp2t design)",
          "changes": "no LDefault* placeholders in the table"},
}
BUILD_ORDER = ["t", "tc", "ta", "tb", "t0"]
RUN_ORDER = ["t0", "ta", "t", "tc", "tb"]     # tc and tb only matter when t differs from ta (ground-textures.md 5)
# Mars registration site: raw PNDT CNAM f64 pair (latitude, longitude in radians; commonwealth-scale.md). From the
# runner's save every run at longitude -1.2 (exp2b .. exp2c, 8 arrivals) was at night and every run at longitude 1.2
# (exp1_mars, exp1d, exp3) in daylight (ground-textures.md 5.1): local time follows the longitude (supported). "day" is
# experiment 1's World01 site.
SITES = {"day": (0.2, 1.2), "source": None}


def m(units):
    return units / tg.UNITS_PER_METRE


def axis(coords_m, origin_units, count):
    """Bilinear index/fraction along one axis of an FO4 vertex grid for metre coordinates."""
    i, f = tg._axis_weights(np.asarray(coords_m) * tg.UNITS_PER_METRE, origin_units, tg.FO4_VERTEX_UNITS, count)
    return i, np.minimum(i + 1, count - 1), f


def sample(g, ry, cx):
    """g[rows, cols] at the separable bilinear positions ry = (i0, i1, f) rows and cx = (j0, j1, f) columns."""
    i0, i1, fy = ry
    j0, j1, fx = cx
    a = g[i0][:, j0] * (1 - fx) + g[i0][:, j1] * fx
    b = g[i1][:, j0] * (1 - fx) + g[i1][:, j1] * fx
    return a * (1 - fy)[:, None] + b * fy[:, None]


def points_bilinear(g, ry, cx):
    """g at scattered points: ry, cx are axis() results for the points' y and x (same length)."""
    i0, i1, fy = ry
    j0, j1, fx = cx
    return (g[i0, j0] * (1 - fx) + g[i0, j1] * fx) * (1 - fy) + (g[i1, j0] * (1 - fx) + g[i1, j1] * fx) * fy


def window_bounds(x, y, kind):
    """(x0, x1, y0, y1) metres of a spot's view window ('view') or of the square around its disk ('disk')."""
    if kind == "view":
        dx0, dx1, dy0, dy1 = VIEW_WINDOW
        return x + dx0, x + dx1, y + dy0, y + dy1
    return x - DISK_M, x + DISK_M, y - DISK_M, y + DISK_M


def window_points(x, y, kind, step=WINDOW_STEP_M):
    """Points (X, Y flat arrays, metres) on a step lattice inside a spot's view window or disk."""
    x0, x1, y0, y1 = window_bounds(x, y, kind)
    X, Y = np.meshgrid(np.arange(x0, x1 + 1e-9, step), np.arange(y0, y1 + 1e-9, step))
    X, Y = X.ravel(), Y.ravel()
    if kind == "disk":
        keep = np.hypot(X - x, Y - y) <= DISK_M + 1e-9
        X, Y = X[keep], Y[keep]
    return X, Y


def fo4_shares(fo4_keys, fo4_w, origin_units, x, y, kind):
    """FO4 texture shares over a spot's view window or disk (bilinear weights averaged), largest first, > 0.5 %."""
    X, Y = window_points(x, y, kind)
    rows, cols = fo4_w[0].shape
    ry, cx = axis(Y, origin_units[1], rows), axis(X, origin_units[0], cols)
    got = {k: float(points_bilinear(g, ry, cx).mean()) for k, g in zip(fo4_keys, fo4_w)}
    return {k: round(v, 3) for k, v in sorted(got.items(), key=lambda kv: -kv[1]) if v > 0.005}


def decoded_shares(t, table, x, y, kind):
    """Decoded Starfield texture shares over the BTD samples inside a spot's view window or disk, largest first."""
    n = t.ncx
    o, s, last = tg.grid_origin(n), tg.SF_STEP_M, n * btd.CELL_SAMPLES - 1
    x0, x1, y0, y1 = window_bounds(x, y, kind)
    c0, c1 = max(0, math.ceil((x0 - o) / s - 1e-9)), min(last, math.floor((x1 - o) / s + 1e-9))
    r0, r1 = max(0, math.ceil((y0 - o) / s - 1e-9)), min(last, math.floor((y1 - o) / s + 1e-9))
    if c0 > c1 or r0 > r1:
        return {}
    Q = landtex.SF_QUAD
    qc0, qc1, qr0, qr1 = c0 // Q, c1 // Q, r0 // Q, r1 // Q
    dec = landtex.decode(t.quad_map[qr0:qr1 + 1, qc0:qc1 + 1], t.weights[qr0 * Q:(qr1 + 1) * Q, qc0 * Q:(qc1 + 1) * Q],
                         len(table))
    sub = dec[:, r0 - qr0 * Q:r1 - qr0 * Q + 1, c0 - qc0 * Q:c1 - qc0 * Q + 1].astype(np.float64)
    if kind == "disk":
        X = o + np.arange(c0, c1 + 1) * s - x
        Y = o + np.arange(r0, r1 + 1) * s - y
        vals = sub[:, np.hypot(X[None, :], Y[:, None]) <= DISK_M + 1e-9]
    else:
        vals = sub.reshape(len(table), -1)
    if vals.shape[1] == 0:
        return {}
    mean = vals.mean(1)
    return {table[i]: round(float(mean[i]), 3) for i in np.argsort(-mean, kind="stable") if mean[i] > 0.005}


def read_fo4(fo4_esm, cells, roi_cells):
    """FO4 side: LTEX names, per-cell weights (keys: FO4 LTEX fid, 0 = default), and for the ROI cells VHGT + VCLR."""
    x0, x1, y0, y1 = cells
    want = {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}
    with fo4land.Plugin(fo4_esm) as p:
        names = {fid: edid(f) for fid, f in p.group_records(b"LTEX")}
        world = p.read_world("Commonwealth", cells=want, refs=False, land_textures=True)
    missing = sorted(want - set(world["cells"]))
    if missing:
        sys.exit(f"FO4 cells without a CELL record: {missing[:8]}")
    rx0, rx1, ry0, ry1 = roi_cells
    cellw, vhgt, vclr, nobase = {}, {}, {}, 0
    for xy, c in world["cells"].items():
        tex = c.get("land_tex", [])
        quads = landtex.parse_land_textures(tex)
        nobase += sum(1 for q in quads if not q["base"])
        cellw[xy] = landtex.cell_weights(quads)
        if rx0 <= xy[0] <= rx1 and ry0 <= xy[1] <= ry1:
            vhgt[xy] = fo4land.decode_vhgt(c["vhgt"])
            v = [d for s, d in tex if s == b"VCLR"]
            vclr[xy] = landtex.decode_vclr(v[0]) if v else np.full((33, 33, 3), 255, np.uint8)
    return names, cellw, vhgt, vclr, nobase


def merge_vclr(vclr, x0, y0, nx, ny):
    out = np.full((32 * ny + 1, 32 * nx + 1, 3), 255, np.uint8)
    for (cx, cy), v in vclr.items():
        out[32 * (cy - y0):32 * (cy - y0) + 33, 32 * (cx - x0):32 * (cx - x0) + 33] = v
    return out


def encode_btd(sf_keys, sf_w, origin_units, n, template=(), search=True):
    """Texture sections for an n x n-cell BTD from vertex-grid weights. The table is `template` (entries that stay
    unused, e.g. exp2b2's placeholders) followed by the textures rarest first. Returns (table, quad_map, words, stats)."""
    cov = {k: float(w.sum()) for k, w in zip(sf_keys, sf_w)}
    order = landtex.table_order(sf_keys, cov)
    table = list(template) + order
    off, M = len(template), len(template) + len(order)
    grids = [sf_w[sf_keys.index(k)] for k in order]
    rows, cols = grids[0].shape
    xs = tg.sample_coords(n)
    cx = axis(xs, origin_units[0], cols)
    qm = np.zeros((2 * n, 2 * n, 8), np.uint8)
    words = np.zeros((n * 128, n * 128), np.uint16)
    err, agree, total, dropped = 0.0, 0, 0, 0.0
    counts = np.zeros(landtex.MAX_TEXTURES + 1, np.int64)
    for band in range(2 * n):
        ys = xs[band * 64:(band + 1) * 64]
        ry = axis(ys, origin_units[1], rows)
        Bc = np.stack([sample(g, ry, cx) for g in grids]).astype(np.float64)
        Bc /= np.maximum(Bc.sum(0), 1e-12)
        B = np.zeros((M,) + Bc.shape[1:])
        B[off:] = Bc
        q, wd, st = landtex.encode(B, M, search)
        qm[band] = q[0]
        words[band * 64:(band + 1) * 64] = wd
        dec = landtex.decode(q, wd, M)
        err += float(np.abs(dec - B).sum() / 2)              # total variation distance per sample, summed
        agree += int((np.argmax(dec, 0) == np.argmax(B, 0)).sum())
        total += B.shape[1] * B.shape[2]
        dropped += st["dropped"] * B.shape[1] * B.shape[2]
        counts += np.array(st["textures_per_quadrant"])
    tot = sum(cov.values())
    stats = {"samples": total, "mean_weight_error": err / total, "dominant_texture_kept": agree / total,
             "weight_dropped_by_6_texture_limit": dropped / total, "quadrants_by_texture_count": counts.tolist(),
             "alpha_rounding": "search" if search else "plain", "coverage": {k: cov[k] / tot for k in order}}
    return table, qm, words, stats


def fold_rare(sf_keys, sf_w, pal=None, min_coverage=MIN_COVERAGE):
    """{rare LTEX: kept LTEX} for every LTEX below min_coverage of the total weight: the kept LTEX nearest in average
    colour (palette), else the most common kept one."""
    cov = {k: float(w.sum()) for k, w in zip(sf_keys, sf_w)}
    tot = sum(cov.values()) or 1.0
    kept = [k for k in sf_keys if cov[k] / tot >= min_coverage]
    if not kept:
        return {}
    col = (pal or {}).get("sf", {})
    out = {}
    for k in sf_keys:
        if k in kept:
            continue
        c = col.get(k, {}).get("color")
        cands = [(texpreview.delta_e(c, col[j]["color"]), j) for j in kept if c and col.get(j, {}).get("color")]
        out[k] = min(cands)[1] if cands else max(kept, key=lambda j: (cov[j], j))
    return out


def sf_grid(cellw, cells, key):
    """Starfield-keyed vertex weights over the BTD footprint: (keys, arrays)."""
    x0, x1, y0, y1 = cells
    g = landtex.WeightGrid(x0, y0, x1 - x0 + 1, y1 - y0 + 1, missing=key(0))
    for xy, w in cellw.items():
        g.add_cell(*xy, w, key=key)
    return g.finish()


def find_spots(fo4_keys, fo4_w, heights, origin_units, near_m, err_fn, step, used, mapping=None, share_fn=None,
               spots=None):
    """One FO4 vertex per SPOTS entry: the FO4 textures that map (mapping) to the spot's single Starfield target cover
    its neighbourhood with the entry's purity, gentle slope, decoded BTD = FO4 height / 70 within SPOT_MAX_ERROR_M under
    every interpolation rule, away from the other plan points, and (share_fn(x, y, target) -> {"view", "disk"}) the
    target holds at least VIEW_MIN_SHARE of the decoded view window and disk; nearest to near_m."""
    from numpy.lib.stride_tricks import sliding_window_view
    mapping = mapping or ground_map.sf_for
    rows, cols = heights.shape
    out = []
    for label, desc, target, min_d, radius, purity in (spots or SPOTS):
        idx = [i for i, k in enumerate(fo4_keys) if mapping(k) == target]
        if not idx:
            print(f"  {label}: no FO4 texture in the region maps to {target}")
            continue
        pur = sum(fo4_w[i] for i in idx)
        k = 2 * radius + 1
        er = np.full(pur.shape, 0.0)
        er[radius:rows - radius, radius:cols - radius] = sliding_window_view(pur, (k, k)).min(axis=(-1, -2))
        rr, cc = np.nonzero(er >= purity)
        xm = m(origin_units[0] + cc * tg.FO4_VERTEX_UNITS)
        ym = m(origin_units[1] + rr * tg.FO4_VERTEX_UNITS)
        d = np.hypot(xm - near_m[0], ym - near_m[1])
        pick, low_share = None, 0
        for j in np.argsort(d, kind="stable"):
            if d[j] < min_d:
                continue
            r, c = int(rr[j]), int(cc[j])
            if tg.local_slope_deg(heights, r, c, tg.FO4_VERTEX_UNITS) > SPOT_MAX_SLOPE:
                continue
            if any(math.hypot(xm[j] - u[0], ym[j] - u[1]) < SPOT_SEPARATION_M for u in used):
                continue
            e = err_fn(r, c)
            if e > max(step, SPOT_MAX_ERROR_M):
                continue
            sh = share_fn(float(xm[j]), float(ym[j]), target) if share_fn is not None else None
            if sh is not None and min(sh["view"], sh["disk"]) < VIEW_MIN_SHARE:
                low_share += 1
                continue
            pick = (r, c, float(d[j]), e, sh)
            break
        if pick is None:
            print(f"  {label}: no vertex meets purity {purity}, slope {SPOT_MAX_SLOPE}, error {SPOT_MAX_ERROR_M} m and "
                  f"a {VIEW_MIN_SHARE:.0%} {target} view share ({low_share} rejected on the share)")
            continue
        r, c, dist, e, sh = pick
        x, y = m(origin_units[0] + c * tg.FO4_VERTEX_UNITS), m(origin_units[1] + r * tg.FO4_VERTEX_UNITS)
        used.append((x, y))
        top = sorted(((float(fo4_w[i][r, c]), fo4_keys[i]) for i in range(len(fo4_keys))), reverse=True)[:3]
        rec = {"label": label, "x": round(x, 4), "y": round(y, 4), "expect": round(m(float(heights[r, c])), 4),
               "ground": desc, "sf_mapped": target, "fo4_sources": sorted(fo4_keys[i] for i in idx),
               "purity": {"radius_vertices": radius, "min_weight": purity},
               "fo4_textures": fo4_shares(fo4_keys, fo4_w, origin_units, x, y, "view"),
               "fo4_disk": fo4_shares(fo4_keys, fo4_w, origin_units, x, y, "disk"),
               "fo4_at_vertex": {kk: round(w, 3) for w, kk in top if w > 0.005},
               "dist_from_redrocket_m": round(dist, 1), "skipped_for_low_share": low_share,
               "slope_deg": round(tg.local_slope_deg(heights, r, c, tg.FO4_VERTEX_UNITS), 2),
               "predicted_error_m": round(e, 6), "fo4_cell": list(fo4land.cell_of(x * 70, y * 70)),
               "sf_cell": list(tg.sf_cell_of(x, y))}
        if sh is not None:
            rec["target_share"] = sh
        out.append(rec)
    return out


# ---------------------------------------------------------------------------------------------- Mars registration
def mars_plugins(folder):
    """(experiment plugin, Mars registration plugin) file names in a staged experiment folder."""
    esms = sorted(f for f in os.listdir(folder) if f.lower().endswith(".esm"))
    mars = [f for f in esms if f.lower().endswith("_mars.esm")]
    main = [f for f in esms if f not in mars]
    return (main[0] if len(main) == 1 else None), (mars[0] if len(mars) == 1 else None)


def registration_entry(data, plugin):
    """The one PNDT CNAM master-worldspace entry whose worldspace comes from `plugin` (a master of this registration
    plugin): (PNDT record offset, offsets of the groups around it, offset of the f64 pair inside the record's field
    data (decompressed when the record is compressed), (f64, f64)). Raises ValueError unless there is exactly one."""
    hsize = struct.unpack_from("<I", data, 4)[0]
    masters = [fo4land.zstring(d) for s, d in fo4land.iter_subrecords(data[24:24 + hsize]) if s == b"MAST"]
    low = [x.lower() for x in masters]
    if plugin.lower() not in low:
        raise ValueError(f"{plugin} is not a master of the registration plugin ({masters})")
    idx = low.index(plugin.lower())
    hits = []

    def walk(start, end, groups):
        for item in fo4land.iter_items(data, start, end):
            if item[0] == "GRUP":
                walk(item[1] + 24, item[2], groups + [item[1]])
                continue
            typ, off, _flags, _fid = item
            if typ != b"PNDT":
                continue
            fields = fo4land.record_data(data, off)
            p = 0
            while p + 6 <= len(fields):
                sig, ln = bytes(fields[p:p + 4]), struct.unpack_from("<H", fields, p + 4)[0]
                if sig == b"XXXX":
                    raise ValueError("XXXX field in PNDT")
                if sig == b"CNAM" and ln >= 20 and ln % 20 == 0:
                    for e in range(p + 6, p + 6 + ln, 20):
                        if struct.unpack_from("<I", fields, e + 16)[0] >> 24 == idx:
                            hits.append((off, groups, e, struct.unpack_from("<dd", fields, e)))
                p += 6 + ln
    walk(24 + hsize, len(data), [])
    if len(hits) != 1:
        raise ValueError(f"{len(hits)} PNDT CNAM entries for {plugin}'s worldspaces (want 1)")
    return hits[0]


def relocate_registration(data, plugin, pair):
    """Registration plugin bytes with `plugin`'s PNDT CNAM entry moved to `pair` (raw f64 latitude, longitude). In the
    record's field data exactly those 16 bytes change; a compressed record is recompressed (zlib) and the sizes of the
    record and the groups around it are adjusted. Returns (new bytes, old pair)."""
    off, groups, e, old = registration_entry(data, plugin)
    _typ, size, flags, _fid = struct.unpack_from("<4sIII", data, off)
    fields = bytearray(fo4land.record_data(data, off))
    struct.pack_into("<dd", fields, e, float(pair[0]), float(pair[1]))
    body = struct.pack("<I", len(fields)) + zlib.compress(bytes(fields)) if flags & fo4land.COMPRESSED else bytes(fields)
    delta = len(body) - size
    out = bytearray(data[:off]) + bytearray(data[off:off + 24]) + body + bytearray(data[off + 24 + size:])
    struct.pack_into("<I", out, off + 4, len(body))
    for g in groups:
        struct.pack_into("<I", out, g + 4, struct.unpack_from("<I", out, g + 4)[0] + delta)
    return bytes(out), old


def plugin_records(data):
    """[(type, form id, flags without the compression bit, field data decompressed)] of every record after TES4, in
    file order, and the TES4 header bytes: for comparing two plugins record by record."""
    hsize = struct.unpack_from("<I", data, 4)[0]
    out = []

    def walk(start, end):
        for item in fo4land.iter_items(data, start, end):
            if item[0] == "GRUP":
                walk(item[1] + 24, item[2])
                continue
            typ, off, flags, fid = item
            out.append((typ, fid, flags & ~fo4land.COMPRESSED, fo4land.record_data(data, off)))
    walk(24 + hsize, len(data))
    return bytes(data[:24 + hsize]), out


# ------------------------------------------------------------------------------------------------------- variants
def variant_dir(out, v):
    return out + VARIANTS[v]["suffix"]


def parse_variants(text):
    if text in (None, "", "all"):
        return list(BUILD_ORDER)
    got = [v.strip() for v in text.split(",") if v.strip()]
    bad = [v for v in got if v not in VARIANTS]
    if bad:
        sys.exit(f"unknown variant(s) {bad}; known: {', '.join(BUILD_ORDER)}")
    return [v for v in BUILD_ORDER if v in got]


def build(a):
    if not a.out:
        sys.exit("--out is required")
    src, out = os.path.abspath(a.source), os.path.abspath(a.out)
    variants = parse_variants(a.variants)
    dirs = {v: variant_dir(out, v) for v in variants}
    if any(os.path.normcase(d) == os.path.normcase(src) for d in dirs.values()):
        sys.exit("--out must differ from --from")
    for v, d in dirs.items():
        if os.path.exists(d):
            e = os.path.join(d, "expected.json")
            mine = os.path.exists(e) and str(read_json(e).get("experiment", "")).startswith("terrain_exp2t")
            if not (a.replace and mine):
                sys.exit(f"{d} exists; pass --replace to rebuild an earlier exp2t staging there, or pick another folder")
    exp = read_json(os.path.join(src, "expected.json"))
    plan = read_json(os.path.join(src, "plan.json"))
    src_btd = read_bytes(os.path.join(src, "Data", "Terrain", BTD_NAME))
    t = btd.read(src_btd)
    n = t.ncx
    src_table = [sf_edid_of(f) for f in t.ltex]
    site = SITES[a.site]
    main_plugin, mars_plugin = mars_plugins(src)
    if site is not None and not (main_plugin and mars_plugin):
        sys.exit(f"--site {a.site} needs the experiment and the Mars registration plugin in {src} (or --site source)")
    fc = exp["fo4_cells"]
    cells = (fc["x"][0], fc["x"][1], fc["y"][0], fc["y"][1])
    roi = exp["region_of_interest_m"]
    roi_cells = tg.fo4_cells_covering(roi["xmin"], roi["xmax"], roi["ymin"], roi["ymax"])
    print(f"BTD {n} x {n} cells, FO4 cells {cells}, region of interest cells {roi_cells}, variants {variants}, "
          f"site {a.site} {site or ''}")

    names, cellw, vhgt, vclr, nobase = read_fo4(os.path.join(a.fo4_data, "Fallout4.esm"), cells, roi_cells)

    def fo4_name(fid):
        return names.get(fid, ground_map.FO4_DEFAULT) if fid else ground_map.FO4_DEFAULT

    unmapped = sorted({fo4_name(f) for w in cellw.values() for f in w} - set(ground_map.MAP))
    pal = read_json(a.palette) if a.palette else None
    keys, grids = sf_grid(cellw, cells, lambda f: ground_map.sf_for(fo4_name(f)))
    rare = fold_rare(keys, grids, pal)
    for r, k in rare.items():                           # fold near-empty entries (full mapping)
        grids[keys.index(k)] += grids[keys.index(r)]
    grids = [g for k, g in zip(keys, grids) if k not in rare]
    keys = [k for k in keys if k not in rare]

    def full_map(e):
        s = ground_map.sf_for(e)
        return rare.get(s, s)

    mappings = {"t": full_map, "tc": full_map, "t0": lambda e: "LDirtFootprints01",
                "ta": lambda e: ground_map.folded("ta", e), "tb": lambda e: ground_map.folded("tb", e)}
    unknown_sf = [k for k in keys if k not in ground_map.SF_FORMID]
    if unknown_sf:
        sys.exit(f"no Starfield FormID for {unknown_sf} (ground_map.SF_FORMID)")
    rx0, rx1, ry0, ry1 = roi_cells
    fo4_grid = landtex.WeightGrid(rx0, ry0, rx1 - rx0 + 1, ry1 - ry0 + 1, missing=ground_map.FO4_DEFAULT)
    for xy, w in cellw.items():
        if rx0 <= xy[0] <= rx1 and ry0 <= xy[1] <= ry1:
            fo4_grid.add_cell(*xy, w, key=fo4_name)
    fo4_keys, fo4_w = fo4_grid.finish()
    print(f"FO4: {len(cellw)} cells, {len(names)} LTEX, {nobase} quadrants without BTXT (default texture), "
          f"{len(fo4_keys)} textures in the region; unmapped (category fallback): {unmapped}; folded (< "
          f"{MIN_COVERAGE:.2%} of the weight): {rare}")

    origin = (cells[0] * 4096, cells[2] * 4096)
    search = a.alpha_rounding != "plain"
    built = {}

    def encode(v, ks, gs):
        tmpl = ground_map.TEMPLATE_TABLE if VARIANTS[v]["template"] is True else ()
        table, qm, words, stats = encode_btd(ks, gs, origin, n, tmpl, search)
        new = btd.Btd(t.version, t.hmin, t.hmax, [ground_map.formid(k) for k in table], t.heights_raw, words, qm)
        data = btd.write(new)
        d_src, d_new = btd.height_digest(src_btd), btd.height_digest(data)
        if not all(d_src[k] == d_new[k] for k in d_src):
            sys.exit(f"{v}: heights changed: refusing to stage")
        built[v] = {"table": table, "data": data, "btd": btd.read(data), "stats": stats, "digest": d_new}
        print(f"{v}: BTD {len(data):,} B, table {len(table)} {table}\n   "
              f"{json.dumps({k: x for k, x in stats.items() if k != 'coverage'})}")

    encode("t", keys, grids)
    if "tc" in variants:
        encode("tc", keys, grids)
    del grids
    for v in ("ta", "tb"):
        if v in variants:
            encode(v, *sf_grid(cellw, cells, lambda f, v=v: mappings[v](fo4_name(f))))
    built["t0"] = {"table": src_table, "data": src_btd, "btd": t, "stats": None, "digest": btd.height_digest(src_btd)}

    # ------------------------------------------------------------------ spots (from the full mapping, variant t)
    merged, _ = fo4land.merge_cells(vhgt, rx0, ry0, rx1 - rx0 + 1, ry1 - ry0 + 1)
    dec_h = t.heights_m()
    o = tg.grid_origin(n)
    step = (t.hmax - t.hmin) / 65535.0
    origin_roi = (rx0 * 4096.0, ry0 * 4096.0)

    def err(r, c):
        xu, yu = origin_roi[0] + c * tg.FO4_VERTEX_UNITS, origin_roi[1] + r * tg.FO4_VERTEX_UNITS
        hs = tg.point_interp(dec_h, o, o, tg.SF_STEP_M, m(xu), m(yu))
        return max(abs(h - m(float(merged[r, c]))) for h in hs.values())

    bt = built["t"]

    def share(x, y, target):
        return {kind: decoded_shares(bt["btd"], bt["table"], x, y, kind).get(target, 0.0) for kind in ("view", "disk")}

    test0 = dict(plan[0])
    used = [(p["x"], p["y"]) for p in test0["points"]]
    rr = exp["structure"]["pos_m"]
    spots = find_spots(fo4_keys, fo4_w, merged, origin_roi, rr, err, step, used, mapping=full_map, share_fn=share)

    # ------------------------------------------------------------------ stage every variant
    for v in variants:
        b = built[v]
        vs = []
        for s in spots:
            src_tex = max(s["fo4_textures"], key=s["fo4_textures"].get)
            target = mappings[v](src_tex)
            got = {kind: decoded_shares(b["btd"], b["table"], s["x"], s["y"], kind) for kind in ("view", "disk")}
            vs.append(dict(s, sf_mapped=target, sf_view=got["view"], sf_disk=got["disk"],
                           sf_decoded=decoded_at(b["btd"], b["table"], s["x"], s["y"]),
                           target_share={k: g.get(target, 0.0) for k, g in got.items()}))
        stage_variant(a, v, dirs[v], src, b, exp, plan, vs, site, main_plugin, mars_plugin, n, unmapped, nobase,
                      fo4_keys, fo4_w, mappings[v], rare)
        if pal is not None and v != "t0":
            render_all(a, dirs[v], pal, fo4_keys, fo4_w, merge_vclr(vclr, rx0, ry0, rx1 - rx0 + 1, ry1 - ry0 + 1),
                       origin_roi, b["btd"], b["table"], n, roi, vs, plan_for(plan, vs, v, n, b["table"])[0], rr)
    if pal is None:
        print("no --palette: reference renders skipped")
    return 0


def sf_edid_of(fid):
    """EditorID of a Starfield LTEX FormID that ground_map knows (mapped LTEX or placeholder), else 8 hex digits."""
    for d in (ground_map.SF_FORMID, ground_map.PLACEHOLDER_FORMID):
        for k, f in d.items():
            if f == fid:
                return k
    return "%08X" % fid


def fid_of(k):
    """FormID of a table entry: a known EditorID, else the 8 hex digits sf_edid_of left for an unknown one."""
    try:
        return ground_map.formid(k)
    except KeyError:
        return int(k, 16)


def plan_for(plan, spots, v, n, table):
    """Runner plan of a variant: the source's first test with the spot probes added, every test fresh."""
    test = dict(plan[0])
    test["label"] = (f"terrain exp2{v}: exp2b2 ({n}x{n}-cell BTD, Absolute, Mars) {VARIANTS[v]['what']}; "
                     f"{len(table)}-entry LTEX table; screenshots at {len(spots)} ground-type spots")
    test["points"] = list(test["points"]) + [{k: s[k] for k in ("label", "x", "y", "expect")} for s in spots]
    # a merged planet world needs a relaunch per test (repeat coc is erratic); later tests of the source plan are kept
    return [dict(w, fresh=True) for w in [test] + list(plan[1:])]


def stage_variant(a, v, final, src, b, exp, plan, spots, site, main_plugin, mars_plugin, n, unmapped, nobase,
                  fo4_keys, fo4_w, mapping, rare):
    """Writes the variant into <final>.partial, then replaces <final> with it (an interrupted build leaves no
    half-staged experiment under the real name)."""
    out = final + ".partial"
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    mars = None
    for f in os.listdir(src):
        p = os.path.join(src, f)
        if not os.path.isfile(p) or not (f.lower().endswith(".esm") or f == "exp2_params.json"):
            continue
        if site is not None and f == mars_plugin:
            new, old = relocate_registration(read_bytes(p), main_plugin, site)
            with open(os.path.join(out, f), "wb") as fh:
                fh.write(new)
            mars = {"plugin": f, "source_raw": list(old), "raw": list(site),
                    "note": "raw PNDT CNAM f64 pair (latitude, longitude in radians); in the PNDT record's field data "
                            "only these 16 bytes differ from the source plugin (the record is recompressed); every other "
                            "record is identical"}
        else:
            shutil.copy2(p, os.path.join(out, f))
    for root, _dirs, files in os.walk(os.path.join(src, "Data")):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), src)
            dst = os.path.join(out, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if f.lower() == BTD_NAME.lower():
                with open(dst, "wb") as fh:
                    fh.write(b["data"])
            else:
                shutil.copy2(os.path.join(root, f), dst)
    copies = sorted(os.path.relpath(os.path.join(r, f), out) for r, _d, fs in os.walk(os.path.join(out, "Data"))
                    for f in fs if f.lower() == BTD_NAME.lower())
    new_plan = plan_for(plan, spots, v, n, b["table"])
    write_json(os.path.join(out, "plan.json"), new_plan)
    tmpl = [i for i, k in enumerate(b["table"]) if k in ground_map.TEMPLATE_TABLE] if v != "t0" else []
    ltex = {"table": [{"index": i, "formid": "%08X" % fid_of(k), "edid": k,
                       "coverage": round(b["stats"]["coverage"].get(k, 0.0), 5) if b["stats"] else None}
                      for i, k in enumerate(b["table"])],
            "template_indices": tmpl,
            "rule": "exp2b2's template table (6 LDefault* + LDirtFootprints01, unused) first when the variant has it, "
                    "then the textures rarest first (top layers) .. most common last (bottom); per quadrant the 6 "
                    "textures with the largest weight, bytes 0..4 slots (alpha group k), byte 6 base, ascending index"}
    fo4_cov = {k: float(w.sum()) for k, w in zip(fo4_keys, fo4_w)}
    tot = sum(fo4_cov.values())
    info = dict(VARIANTS[v], name=v, folder=os.path.basename(out))
    expected = dict(exp, experiment=f"terrain_exp2{v}", variant=info, ltex=ltex, spawn_local=new_plan[0].get("spawn_local"),
                    site={"name": a.site, "mars": mars,
                          "why": "daylight: from the runner's save, longitude -1.2 arrived at night 8 of 8 times, "
                                 "longitude 1.2 in daylight (ground-textures.md 5.1)" if site else "source site"},
                    ground_textures={
                        "source": "FO4 LAND BTXT/ATXT/VTXT of every footprint cell, over-compositing per quadrant, "
                                  "bilinear onto the BTD grid, fo4sf.ground_map (FO4 LTEX -> vanilla Starfield LTEX)",
                        "heights_identical_to": os.path.join(src, "Data", "Terrain", BTD_NAME),
                        "height_digest": b["digest"], "encode_stats": b["stats"], "fo4_quadrants_without_btxt": nobase,
                        "unmapped_fo4": unmapped, "folded_rare": rare,
                        "region_fo4_coverage": {k: round(x / tot, 4) for k, x in
                                                sorted(fo4_cov.items(), key=lambda kv: -kv[1])},
                        "mapping_used": {k: mapping(k) for k in fo4_keys},
                        "view_window_m": list(VIEW_WINDOW), "disk_m": DISK_M, "min_share": VIEW_MIN_SHARE,
                        "spots": spots, "btd_copies": copies})
    expected["btd_bytes"] = len(b["data"])
    write_json(os.path.join(out, "expected.json"), expected)
    readme(out, src, v, n, b["table"], spots, new_plan[0], len(b["data"]), copies, mars, final)
    if os.path.exists(final):
        shutil.rmtree(final)
    os.rename(out, final)
    print(f"staged {final}: {len(b['table'])}-entry table, plan {len(new_plan[0]['points'])} points, fresh: true"
          + (f", Mars entry {mars['source_raw']} -> {mars['raw']}" if mars else ""))


def decoded_at(t, table, x, y):
    """Top decoded Starfield textures (weight > 1 %) at the BTD sample nearest to world (x, y)."""
    n = t.ncx
    o = tg.grid_origin(n)
    c, r = int(round((x - o) / tg.SF_STEP_M)), int(round((y - o) / tg.SF_STEP_M))
    qy, qx = r // 64, c // 64
    q = t.quad_map[qy:qy + 1, qx:qx + 1]
    w = t.weights[qy * 64:(qy + 1) * 64, qx * 64:(qx + 1) * 64]
    dec = landtex.decode(q, w, len(table))[:, r - qy * 64, c - qx * 64]
    return {table[i]: round(float(dec[i]), 3) for i in np.argsort(-dec) if dec[i] > 0.01}


def queue_command(out):
    return (f"python scripts/game/testqueue.py plan-terrain --staging C:\\Modding\\staging\\integ_1011 --exp-dir {out} "
            f"--out C:\\Modding\\testqueue\\{os.path.basename(out)} --plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm "
            "--fresh")


def readme(out, src, v, n, table, spots, test, nbytes, copies, mars, final):
    info = VARIANTS[v]
    lines = [
        f"Terrain experiment 2{v} (Claude, 2026-10-11). NOT deployed. Recipe: docs/terrain/ground-textures.md section 5",
        "(branch claude/terrain-ground-textures, stacked on claude/terrain-overlay-records).",
        f"Variant {v}: {info['what']}.",
        f"Against {info['vs']} it changes: {info['changes']}.",
        f"exp2b2 ({src}): the {n} x {n}-cell BTD keeps its heights byte for byte (header, cell min/max, LOD4 heights",
        f"and every block's height half; SHA-256 in expected.json). LTEX table: {len(table)} entries: {', '.join(table)}.",
        f"BTD: {nbytes:,} B, staged at: {', '.join(copies)}.",
        ("Site: " + (f"{mars['plugin']} registers the worldspace at raw (latitude, longitude) {tuple(mars['raw'])} rad "
                     f"instead of exp2b2's {tuple(round(x, 6) for x in mars['source_raw'])}, where every earlier run "
                     "from the runner's save arrived in daylight (exp2b2's site: always night). Only those 16 bytes of "
                     "the PNDT record's fields differ." if mars else "exp2b2's registration, unchanged (night at arrival).")),
        "",
        "Install (game closed). The runner does it; --pack stores the Data tree uncompressed in 'FO4TerrainExp2 - Main.ba2':",
        "  scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> "
        "--plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm --pack",
        "Queue (one test, relaunch first because repeat coc into a merged world is erratic; from the integration worktree):",
        "  " + queue_command(final),
        "Run order: exp2t0, exp2ta, exp2t; then exp2tc and exp2tb only if exp2t differs from exp2ta.",
        "Never install two FO4TerrainExp2 experiments at once (same plugin names; the chain uninstalls between queues).",
        "",
        "In game: coc FO4CW_RedRocketSpawn, then the usual 14 probes and these ground-type spots (worldspace frame; the",
        "runner adds the merge offset from the arrival). Every probe takes a screenshot looking north, 15 degrees down",
        f"(pt<k>.png); its middle shows the ground {VIEW_WINDOW[2]:g}..{VIEW_WINDOW[3]:g} m north of the spot. Shares: FO4 "
        f"layers and the decoded BTD over that view window ({VIEW_WINDOW[1] - VIEW_WINDOW[0]:g} m wide):",
    ]
    base = len(test["points"]) - len(spots)
    for k, s in enumerate(spots):
        fo4 = ", ".join(f"{kk} {x:.0%}" for kk, x in list(s["fo4_textures"].items())[:2])
        sf = ", ".join(f"{kk} {x:.0%}" for kk, x in list(s["sf_view"].items())[:2])
        lines.append(f"  pt{base + k:<3d} {s['label']:13s} x {s['x']:10.4f} y {s['y']:10.4f} -> {s['expect']:9.4f}  "
                     f"FO4 {fo4} -> Starfield {sf}")
    lines += ["Lighting: after the run, `python scripts/terrain/ground_textures.py lighting --run <queue dir>` says",
              "whether the arrival was in daylight; colour and tint can only be judged in daylight shots."]
    lines += (["Compare with reference/compare_spots.png (FO4 vs decoded Starfield textures, top-down, textures tiled at",
               "their material's TilingDistance where it has one, else 2.5 m) and reference/compare_overview.png."]
              if v != "t0" else ["Control: every spot shows LDirtFootprints01 (the exp2b2 look), now in daylight."])
    lines += ["Uninstall: exp_install.py uninstall."]
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def read_bytes(p):
    with open(p, "rb") as f:
        return f.read()


# ------------------------------------------------------------------------------------------------------- renders
def hillshade(h, step_m):
    """0.55..1.15 shading from a heightfield [rows (south first), cols], light from the north-west at 45 degrees."""
    dzdy, dzdx = np.gradient(h, step_m)
    nx, ny, nz = -dzdx, -dzdy, np.ones_like(h)
    ln = np.array([-1.0, 1.0, 1.4])
    ln /= np.linalg.norm(ln)
    s = (nx * ln[0] + ny * ln[1] + nz * ln[2]) / np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)
    return 0.55 + 0.6 * np.clip(s, 0, 1)


def lin(c):
    return texpreview.srgb_to_linear(np.asarray(c, np.float64))


def to_img(linrgb, shade=None):
    rgb = linrgb * (shade[..., None] if shade is not None else 1.0)
    return np.clip(np.rint(texpreview.linear_to_srgb(rgb)), 0, 255).astype(np.uint8)[::-1]   # north up


def preview_tex(pal_entry):
    from PIL import Image
    p = pal_entry.get("preview")
    if p and os.path.exists(p):
        return texpreview.srgb_to_linear(np.asarray(Image.open(p).convert("RGB"), np.float64))
    return None


def render_all(a, out, pal, fo4_keys, fo4_w, vclr, origin_roi, t, order, n, roi, spots, test, rr):
    """Reference renders of one variant: overview (average colours, hill-shaded) and 40 m spot close-ups, FO4 layers
    (left) against the decoded BTD (right). `order` is the BTD's LTEX table. Textures tile every TilingDistance metres
    when the material sets one (220 of 416 Starfield LTEX), else 2.5 m; FO4 textures as fo76utils suggests."""
    from PIL import Image, ImageDraw
    ref = os.path.join(out, "reference")
    os.makedirs(ref, exist_ok=True)
    o = tg.grid_origin(n)
    fo4_lin =[lin(pal["fo4"].get(k, {}).get("color") or (90, 90, 90)) for k in fo4_keys]
    sf_lin = [lin(pal["sf"].get(k, {}).get("color") or (90, 90, 90)) for k in order]
    vlin = (vclr.astype(np.float64) / 255.0)

    # overview: 1 m per pixel over the region of interest
    px = 1.0
    xs = np.arange(roi["xmin"], roi["xmax"], px)
    ys = np.arange(roi["ymin"], roi["ymax"], px)
    rows, cols = fo4_w[0].shape
    cx, ry = axis(xs, origin_roi[0], cols), axis(ys, origin_roi[1], rows)
    fo4_img = np.zeros((len(ys), len(xs), 3))
    for g, c in zip(fo4_w, fo4_lin):
        fo4_img += sample(g, ry, cx)[..., None] * c
    vc = np.stack([sample(vlin[..., i], ry, cx) for i in range(3)], -1)
    fo4_vclr = fo4_img * vc
    # Starfield: decode the BTD window, average colours per sample, then bilinear to the same pixels
    c0, c1 = int((roi["xmin"] - o) / tg.SF_STEP_M) // 64 * 64, -(-int((roi["xmax"] - o) / tg.SF_STEP_M + 1) // 64) * 64
    r0, r1 = int((roi["ymin"] - o) / tg.SF_STEP_M) // 64 * 64, -(-int((roi["ymax"] - o) / tg.SF_STEP_M + 1) // 64) * 64
    dec = landtex.decode(t.quad_map[r0 // 64:r1 // 64, c0 // 64:c1 // 64], t.weights[r0:r1, c0:c1], len(order))
    sf_s = np.tensordot(np.moveaxis(dec, 0, -1), np.array(sf_lin), axes=([2], [0]))
    hm = t.heights_m()[r0:r1, c0:c1]
    wx = o + c0 * tg.SF_STEP_M
    wy = o + r0 * tg.SF_STEP_M
    sx = tg._axis_weights(xs, wx, tg.SF_STEP_M, c1 - c0)
    sy = tg._axis_weights(ys, wy, tg.SF_STEP_M, r1 - r0)
    sxa = (sx[0], np.minimum(sx[0] + 1, c1 - c0 - 1), sx[1])
    sya = (sy[0], np.minimum(sy[0] + 1, r1 - r0 - 1), sy[1])
    sf_img = np.stack([sample(sf_s[..., i], sya, sxa) for i in range(3)], -1)
    shade = hillshade(sample(hm, sya, sxa), px)

    def marks(im, x_of, y_of, scale=1.0):
        d = ImageDraw.Draw(im)
        for p in test["points"]:
            X, Y = x_of(p["x"]), y_of(p["y"])
            ground = p["label"].startswith("ground_")
            col = (255, 230, 0) if ground else (255, 60, 60)
            r = 6 if ground else 3
            d.ellipse([X - r, Y - r, X + r, Y + r], outline=col, width=2 if ground else 1)
            if ground:
                d.text((X + 8, Y - 6), p["label"][7:], fill=col)
        X, Y = x_of(rr[0]), y_of(rr[1])
        d.rectangle([X - 5, Y - 5, X + 5, Y + 5], outline=(60, 220, 255), width=2)

    def xo(x):
        return (x - roi["xmin"]) / px

    def yo(y):
        return len(ys) - 1 - (y - roi["ymin"]) / px

    ims = []
    for name, img, title in (("fo4_overview.png", fo4_vclr, "Fallout 4: LAND layers x vertex colour (avg colours)"),
                             ("fo4_overview_novclr.png", fo4_img, "Fallout 4: LAND layers, no vertex colour"),
                             ("sf_overview.png", sf_img, "Starfield exp2t: decoded BTD layers (avg colours)")):
        im = Image.fromarray(to_img(img, shade))
        marks(im, xo, yo)
        ImageDraw.Draw(im).text((6, 6), title + ", N up, 1 m/px", fill=(255, 255, 255))
        im.save(os.path.join(ref, name))
        ims.append(im)
    w, h = ims[0].size
    both = Image.new("RGB", (2 * w + 8, h), (0, 0, 0))
    both.paste(ims[0], (0, 0))
    both.paste(ims[2], (w + 8, 0))
    both.save(os.path.join(ref, "compare_overview.png"))

    # spot close-ups: 40 m x 40 m at 0.1 m/px, textures tiled (illustrative scale)
    half, ppm = 20.0, 10.0
    tiles = []
    fo4_tex = [preview_tex(pal["fo4"].get(k, {})) for k in fo4_keys]
    sf_tex = [preview_tex(pal["sf"].get(k, {})) for k in order]
    fo4_tile = [58.514 * (pal["fo4"].get(k, {}).get("width") or 1024) / (FO4_TILES_PER_CELL_AT_1024 * 1024)
                for k in fo4_keys]
    sf_tile = [pal["sf"].get(k, {}).get("tiling_m") or 2.5 for k in order]
    for s in spots:
        gx = np.arange(s["x"] - half, s["x"] + half, 1 / ppm)
        gy = np.arange(s["y"] - half, s["y"] + half, 1 / ppm)
        X, Y = np.meshgrid(gx, gy)
        cxs, rys = axis(gx, origin_roi[0], cols), axis(gy, origin_roi[1], rows)
        f_img = np.zeros(X.shape + (3,))
        for g, tex, tile, c in zip(fo4_w, fo4_tex, fo4_tile, fo4_lin):
            wgt = sample(g, rys, cxs)
            if wgt.max() < 1e-4:
                continue
            f_img += wgt[..., None] * (tiled(tex, X, Y, tile) if tex is not None else c)
        f_img *= np.stack([sample(vlin[..., i], rys, cxs) for i in range(3)], -1)
        sxs = tg._axis_weights(gx, wx, tg.SF_STEP_M, c1 - c0)
        sys_ = tg._axis_weights(gy, wy, tg.SF_STEP_M, r1 - r0)
        sxa2 = (sxs[0], np.minimum(sxs[0] + 1, c1 - c0 - 1), sxs[1])
        sya2 = (sys_[0], np.minimum(sys_[0] + 1, r1 - r0 - 1), sys_[1])
        s_img = np.zeros(X.shape + (3,))
        for i, (tex, tile, c) in enumerate(zip(sf_tex, sf_tile, sf_lin)):
            wgt = sample(dec[i].astype(np.float64), sya2, sxa2)
            if wgt.max() < 1e-4:
                continue
            s_img += wgt[..., None] * (tiled(tex, X, Y, tile) if tex is not None else c)
        sh = hillshade(sample(hm, sya2, sxa2), 1 / ppm)
        a_im, b_im = Image.fromarray(to_img(f_img, sh)), Image.fromarray(to_img(s_img, sh))
        for im, side in ((a_im, "FO4"), (b_im, "Starfield")):
            d = ImageDraw.Draw(im)
            c_ = im.size[0] // 2
            d.ellipse([c_ - 5, c_ - 5, c_ + 5, c_ + 5], outline=(255, 230, 0), width=2)
            d.text((6, 6), f"{side} {s['label']} ({s['x']:.1f}, {s['y']:.1f}) 40 m, N up", fill=(255, 255, 255))
            shares = s["fo4_textures"] if side == "FO4" else s.get("sf_view") or s.get("sf_decoded", {})
            txt = "view: " + ", ".join(f"{k} {x:.0%}" for k, x in list(shares.items())[:3])
            d.text((6, im.size[1] - 16), txt[:70], fill=(255, 255, 0))
        tiles.append((a_im, b_im))
    if tiles:
        w, h = tiles[0][0].size
        sheet = Image.new("RGB", (2 * w + 8, len(tiles) * (h + 8)), (0, 0, 0))
        for i, (fa, fb) in enumerate(tiles):
            sheet.paste(fa, (0, i * (h + 8)))
            sheet.paste(fb, (w + 8, i * (h + 8)))
        sheet.save(os.path.join(ref, "compare_spots.png"))
    print(f"renders in {ref}")


def tiled(tex, X, Y, tile_m):
    """Linear colour of a square texture repeated every tile_m metres, sampled (nearest) at world X, Y (row 0 = top of
    the texture = north)."""
    h, w = tex.shape[:2]
    u = np.floor((X / tile_m % 1.0) * w).astype(np.int64) % w
    v = np.floor((1.0 - (Y / tile_m % 1.0)) * h).astype(np.int64) % h
    return tex[v, u]


# ------------------------------------------------------------------------------------------------------- check
def check_one(out, src):
    """One staged variant: heights identical to --from, table and quadrant layout, every spot's target share in the
    decoded view window and disk, plan, Mars registration. Returns ok."""
    exp = read_json(os.path.join(out, "expected.json"))
    plan = read_json(os.path.join(out, "plan.json"))
    v = exp.get("variant", {}).get("name", "t")
    ok = True
    src_bytes = read_bytes(os.path.join(src, "Data", "Terrain", BTD_NAME))
    src_d = btd.height_digest(src_bytes)
    copies = exp["ground_textures"]["btd_copies"]
    first = None
    for rel in copies:
        data = read_bytes(os.path.join(out, rel))
        first = first or data
        d = btd.height_digest(data)
        same = all(d[k] == src_d[k] for k in src_d)
        ok &= same and data == first
        print(f"[{v}] {rel}: {len(data):,} B, heights identical to the source: {same}, same bytes as the first copy: "
              f"{data == first}")
    if v == "t0":
        ok &= first == src_bytes
        print(f"[{v}] control BTD byte-identical to the source: {first == src_bytes}")
    t = btd.read(first)
    table = [e["edid"] for e in exp["ltex"]["table"]]
    ids = ["%08X" % f for f in t.ltex]
    table_ok = ids == [e["formid"] for e in exp["ltex"]["table"]]
    q = t.quad_map.reshape(-1, 8)
    n = len(table)
    layout_ok = bool((q[:, 5] == 0).all() and (q[:, 7] == 0).all() and (q <= n).all() and (q[:, 0] > 0).all())
    used = {n - int(x) for x in np.unique(q[:, :7]) if 0 < int(x) <= n}
    tmpl = set(exp["ltex"].get("template_indices", []))
    tmpl_ok = not (used & tmpl)
    ok &= table_ok and layout_ok and tmpl_ok
    print(f"[{v}] LTEX table ({n}) matches expected.json: {table_ok}; quadrant bytes 5 and 7 empty, values <= n, slot 0 "
          f"set: {layout_ok}; template entries unused: {tmpl_ok}; weights max {int(t.weights.max())}, bit 15 set "
          f"{int((t.weights >> 15).sum())}")
    for s in exp["ground_textures"]["spots"]:
        got = {kind: decoded_shares(t, table, s["x"], s["y"], kind).get(s["sf_mapped"], 0.0) for kind in ("view", "disk")}
        good = min(got.values()) >= VIEW_MIN_SHARE
        print(f"[{v}]   {s['label']:13s} FO4 view {dict(list(s['fo4_textures'].items())[:2])} -> {s['sf_mapped']}: decoded "
              f"view {got['view']:.0%}, disk {got['disk']:.0%} {'ok' if good else 'BELOW ' + format(VIEW_MIN_SHARE, '.0%')}")
        ok &= good
    pts = {p["label"] for p in plan[0]["points"]}
    fresh = all(w.get("fresh") is True for w in plan)
    ok &= all(s["label"] in pts for s in exp["ground_textures"]["spots"]) and fresh
    mars = (exp.get("site") or {}).get("mars")
    if mars:
        main_plugin, _ = mars_plugins(out)
        mine, theirs = read_bytes(os.path.join(out, mars["plugin"])), read_bytes(os.path.join(src, mars["plugin"]))
        _off, _groups, e, pair = registration_entry(mine, main_plugin)
        site_ok, diffs = registration_diff(mine, theirs, e)
        site_ok &= list(pair) == mars["raw"]
        ok &= site_ok
        print(f"[{v}] Mars registration {mars['plugin']}: entry {pair} (expected {tuple(mars['raw'])}); against the "
              f"source plugin: {diffs}; only the entry differs: {site_ok}")
    print(f"[{v}] plan: {len(plan)} test(s), {len(plan[0]['points'])} points in the first, all fresh {fresh}; "
          f"check {'PASS' if ok else 'FAIL'}")
    write_json(os.path.join(out, "offline_check_textures.json"), {"pass": bool(ok), "source_digest": src_d})
    return ok


def registration_diff(mine, theirs, entry):
    """(ok, summary): same TES4 header and records in the same order, every record's field data identical except the
    one PNDT record, which differs only inside the 16 bytes of its site entry at `entry`."""
    h1, r1 = plugin_records(mine)
    h2, r2 = plugin_records(theirs)
    if h1 != h2 or len(r1) != len(r2):
        return False, "header or record count differs"
    bad = []
    for (t1, f1, g1, d1), (t2, f2, g2, d2) in zip(r1, r2):
        if (t1, f1, g1) != (t2, f2, g2) or len(d1) != len(d2):
            bad.append("%s %08X layout" % (t1.decode(), f1))
            continue
        diff = [i for i in range(len(d1)) if d1[i] != d2[i]]
        if diff and not (t1 == b"PNDT" and all(entry <= i < entry + 16 for i in diff)):
            bad.append("%s %08X" % (t1.decode(), f1))
    changed = sum(1 for a_, b_ in zip(r1, r2) if a_[3] != b_[3])
    return not bad, (f"{len(r1)} records, {changed} changed" + (f", unexpected: {bad[:4]}" if bad else ""))


def check(a):
    out, src = os.path.abspath(a.out), os.path.abspath(a.source)
    e = os.path.join(out, "expected.json")
    if os.path.exists(e) and read_json(e).get("variant", {}).get("name", "t") != "t":
        return check_one(out, src)                      # one variant folder named directly
    ok = True
    for v in parse_variants(a.variants):
        d = variant_dir(out, v)
        if not os.path.exists(os.path.join(d, "expected.json")):
            print(f"[{v}] {d}: not staged")
            ok = False
            continue
        ok &= check_one(d, src)
    print(f"all variants: {'PASS' if ok else 'FAIL'}")
    return ok


# ------------------------------------------------------------------------------------------------------- lighting
# Two brightness readings (0..255) of a finished attempt: the top SKY_ROWS rows of spawn.png (sky above the arrival)
# and the median over the probe shots (pt<k>.png) of their top-left and top-right corners (top fifth, outer quarters:
# ground away from the helmet lamp's circle). Fifteen earlier attempts (C:\Modding	estqueue, 2026-10-11): night at
# longitude -1.2 (exp2b .. exp2c): sky 6.4..19.9, corners 6.7..37.0; daylight at longitude 1.2 (exp1_mars, exp1d, exp3):
# sky 103..131, corners 51.1..154.4, except exp1d a1, whose arrival fell into a pit below the overlay (sky 7.3) while its
# probes were in daylight (corners 51.6). Thresholds sit between those groups; a heuristic, not a calibration.
SKY_ROWS = 200
NIGHT_SKY_MAX, DAY_SKY_MIN = 30.0, 60.0
NIGHT_CORNER_MAX, DAY_CORNER_MIN = 40.0, 45.0


def brightness(png, rows=None):
    from PIL import Image
    im = np.asarray(Image.open(png).convert("RGB"), np.float64)
    return float((im[:rows] if rows else im).mean())


def corner_brightness(png):
    from PIL import Image
    im = np.asarray(Image.open(png).convert("RGB"), np.float64)
    h, w = im.shape[:2]
    return float(np.concatenate([im[:h // 5, :w // 4].ravel(), im[:h // 5, w - w // 4:].ravel()]).mean())


def lighting_verdict(sky, corners=None):
    """'daylight', 'night' or 'unclear' from the spawn sky and the probe-corner median (None: no probe shots)."""
    if sky >= DAY_SKY_MIN or (corners is not None and corners >= DAY_CORNER_MIN):
        return "daylight"
    if sky <= NIGHT_SKY_MAX and (corners is None or corners <= NIGHT_CORNER_MAX):
        return "night"
    return "unclear"


def lighting(a):
    """Daylight or night per attempt of finished terrain queues (colour and tint can only be judged in daylight)."""
    if not a.run:
        sys.exit("--run <queue dir> [...] is required")
    rep = []
    for q in a.run:
        for sp in sorted(glob.glob(os.path.join(q, "tests", "*", "*", "spawn.png"))):
            att = os.path.dirname(sp)
            sky = brightness(sp, SKY_ROWS)
            pts = sorted(glob.glob(os.path.join(att, "pt*.png")), key=lambda p: int(os.path.basename(p)[2:-4] or 0))
            cor = {os.path.basename(p)[:-4]: round(corner_brightness(p), 1) for p in pts}
            med = float(np.median(list(cor.values()))) if cor else None
            r = {"attempt": os.path.relpath(att, q), "queue": os.path.basename(os.path.normpath(q)),
                 "sky_top_rows": round(sky, 1), "probe_corner_median": None if med is None else round(med, 1),
                 "verdict": lighting_verdict(sky, med), "probe_corners": cor}
            rep.append(r)
            print(f"{r['queue']} {r['attempt']}: sky {sky:5.1f}, probe corners "
                  f"{'-' if med is None else format(med, '5.1f')} -> {r['verdict']}")
    if not rep:
        print("no spawn.png under the given queue folders")
    if a.out:
        write_json(a.out, {"sky_rows": SKY_ROWS, "thresholds": {"night_sky_max": NIGHT_SKY_MAX, "day_sky_min": DAY_SKY_MIN,
                                                                "night_corner_max": NIGHT_CORNER_MAX,
                                                                "day_corner_min": DAY_CORNER_MIN}, "attempts": rep})
    return 0 if rep else 1


# ------------------------------------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("palette", "suggest", "survey", "build", "check", "lighting"))
    ap.add_argument("--fo4-data", default=r"C:\Program Files (x86)\Steam\steamapps\content\app_377160\depot_377163\Data")
    ap.add_argument("--sf-data", default=r"D:\SteamLibrary\steamapps\common\Starfield\Data")
    ap.add_argument("--content-resources", default=r"D:\SteamLibrary\steamapps\common\Starfield\Tools\ContentResources.zip")
    ap.add_argument("--from", dest="source", help="staged exp2b2 folder (BTD, plugins, mask, plan)")
    ap.add_argument("--palette", help="palette.json from the palette command (renders and the rare-texture fold use it)")
    ap.add_argument("--replace", action="store_true", help="build: replace earlier exp2t stagings in the variant folders")
    ap.add_argument("--variants", default="all",
                    help="build/check: comma list of " + ", ".join(BUILD_ORDER) + " or 'all' (folders: --out + suffix: "
                         + ", ".join(f"{v} '{VARIANTS[v]['suffix']}'" for v in BUILD_ORDER) + ")")
    ap.add_argument("--site", choices=sorted(SITES), default="day",
                    help="build: Mars registration site of every variant (day: raw (0.2, 1.2) rad; source: unchanged)")
    ap.add_argument("--alpha-rounding", choices=("search", "plain"), default="search",
                    help="build: 3-bit alphas by the error search (default) or plain rounding (comparison only)")
    ap.add_argument("--run", nargs="+", help="lighting: finished queue folders (C:\\Modding\\testqueue\\<name>)")
    ap.add_argument("--out", help="output: palette.json (palette), suggestion json (suggest), survey json (survey), "
                                  "staging dir of variant t (build/check), report json (lighting)")
    a = ap.parse_args(argv)
    if a.cmd == "survey":
        return survey(a)
    if a.cmd == "lighting":
        return lighting(a)
    if not a.out and a.cmd != "suggest":
        sys.exit("--out is required")
    if a.cmd == "palette":
        return palette(a)
    if a.cmd == "suggest":
        if not a.palette:
            sys.exit("--palette is required")
        return suggest(a)
    if not a.source:
        sys.exit("--from is required")
    if a.cmd == "build":
        return build(a)
    return 0 if check(a) else 1


if __name__ == "__main__":
    sys.exit(main())
