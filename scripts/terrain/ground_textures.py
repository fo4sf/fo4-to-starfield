"""Fallout 4 ground textures on the native Commonwealth terrain (docs/terrain/ground-textures.md).

    python scripts/terrain/ground_textures.py palette --fo4-data <FO4 Data> --sf-data <Starfield Data> --out <palette.json>
    python scripts/terrain/ground_textures.py build --from <staged exp2b2> --fo4-data <FO4 Data> --sf-data <Starfield Data>
                                                    --out <staging dir, e.g. C:\\Modding\\staging\\terrain_exp2t>
                                                    [--palette <palette.json>]
    python scripts/terrain/ground_textures.py check --from <staged exp2b2> --out <staging dir>

palette  average albedo of every FO4 land texture (TXST diffuse or its BGSM) and every Starfield LTEX (its .mat in the
         Creation Kit's ContentResources.zip -> albedo DDS, low mips only); the mapping table (fo4sf.ground_map) was
         chosen with it. Written outside the repo (derived from game files).
build    reads the FO4 LAND texture layers (BTXT/ATXT/VTXT) of the BTD footprint, turns them into per-vertex weights,
         maps every FO4 LTEX to a vanilla Starfield LTEX, resamples onto the BTD grid and writes the BTD's texture
         sections (LTEX table, quadrant bytes, 3-bit alphas). Heights, header, cell min/max and LOD4 heights stay
         byte-identical to the source BTD (checked). Stages exp2b2's plugins, mask and params unchanged, a runner plan
         (the usual probes + four ground-type spots, "fresh": true), reference renders and a mapping report.
check    re-reads the staged BTD: heights identical to the source, texture sections decode, per-spot textures.
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
            out[fid] = {"edid": edid(f), "txst": t.get("EDID", ""), "diffuse": t.get("TX00", ""), "bgsm": t.get("MNAM", "")}
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
    bad = {k: ("%08X" % v, "%08X" % sf[k] if k in sf else None) for k, v in ground_map.SF_FORMID.items() if sf.get(k) != v}
    rows = []
    for fo4, v in sorted(pal["fo4"].items()):
        cat = ground_map.category(fo4)
        cands = [(texpreview.delta_e(v["color"], pal["sf"][c]["color"]), c) for c in ground_map.SF_CANDIDATES[cat]
                 if v["color"] and pal["sf"].get(c, {}).get("color")]
        cands.sort()
        best = cands[0][1] if cands else None
        chosen = ground_map.sf_for(fo4)
        de = next((d for d, c in cands if c == chosen), None)
        rows.append({"fo4": fo4, "category": cat, "nearest": best, "nearest_de": round(cands[0][0], 1) if cands else None,
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


# ------------------------------------------------------------------------------------------------------- build
# Four places with known FO4 ground types for the in-game screenshots (one per type), nearest to Red Rocket. FO4
# terrain textures only: the exp2t plugin has no statics, so FO4's road meshes and Red Rocket's concrete pad are absent
# and the terrain painted under them is what shows. In FO4 the road network is static meshes over terrain painted
# RubbleRock01 (the grey bands in reference/fo4_overview.png); Asphalt01 is painted on paved lots (the Red Rocket
# forecourt, parking areas; patchy, so a smaller neighbourhood). Each spot is an FO4 vertex whose (2 radius + 1)^2
# neighbourhood is >= purity of the listed textures: (label, description, FO4 LTEX, min distance m, radius, purity).
SPOTS = [
    ("ground_road", "road bed (FO4 terrain RubbleRock01 under the road meshes)", ("LRubbleRock01", "LRubbleRock01Grass"),
     20.0, 2, 0.9),
    ("ground_lot", "paved lot (FO4 terrain Asphalt01: forecourt / parking area)", ("LAsphalt01",), 0.0, 1, 0.85),
    ("ground_grass", "dried grass (FO4 DriedGrass01)", ("LDriedGrass01", "LDriedGrass01NoGrass", "LDriedGrass02Weeds"),
     30.0, 2, 0.9),
    ("ground_dirt", "dirt (FO4 RootsEroded01 / DirtPath01)", ("LRootsEroded01", "LRootsEroded01Grass01", "LDirtPath01"),
     30.0, 2, 0.9),
]
SPOT_MAX_SLOPE = 10.0
SPOT_SEPARATION_M = 8.0
SPOT_MAX_ERROR_M = 0.05     # decoded BTD vs FO4 height / 70 at the spot, worst interpolation rule (runner: 0.5 m)
FO4_TILES_PER_CELL_AT_1024 = 16      # fo76utils render.md: ~16384 / 2^mip texels per FO4 cell (illustrative)


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


def encode_btd(sf_keys, sf_w, origin_units, n):
    """Texture sections for an n x n-cell BTD from vertex-grid weights. Returns (table order, quad_map, words, stats)."""
    cov = {k: float(w.sum()) for k, w in zip(sf_keys, sf_w)}
    order = landtex.table_order(sf_keys, cov)
    grids = [sf_w[sf_keys.index(k)] for k in order]
    rows, cols = grids[0].shape
    xs = tg.sample_coords(n)
    cx = axis(xs, origin_units[0], cols)
    qm = np.zeros((2 * n, 2 * n, 8), np.uint8)
    words = np.zeros((n * 128, n * 128), np.uint16)
    M, err, agree, total, dropped = len(order), 0.0, 0, 0, 0.0
    counts = np.zeros(landtex.MAX_TEXTURES + 1, np.int64)
    for band in range(2 * n):
        ys = xs[band * 64:(band + 1) * 64]
        ry = axis(ys, origin_units[1], rows)
        B = np.stack([sample(g, ry, cx) for g in grids]).astype(np.float64)
        B /= np.maximum(B.sum(0), 1e-12)
        q, wd, st = landtex.encode(B, M)
        qm[band] = q[0]
        words[band * 64:(band + 1) * 64] = wd
        dec = landtex.decode(q, wd, M)
        err += float(np.abs(dec - B).sum() / 2)              # total variation distance per sample, summed
        agree += int((np.argmax(dec, 0) == np.argmax(B, 0)).sum())
        total += B.shape[1] * B.shape[2]
        dropped += st["dropped"] * B.shape[1] * B.shape[2]
        counts += np.array(st["textures_per_quadrant"])
    stats = {"samples": total, "mean_weight_error": err / total, "dominant_texture_kept": agree / total,
             "weight_dropped_by_6_texture_limit": dropped / total, "quadrants_by_texture_count": counts.tolist(),
             "coverage": {k: cov[k] / sum(cov.values()) for k in order}}
    return order, qm, words, stats


def find_spots(fo4_keys, fo4_w, heights, origin_units, near_m, err_fn, step, used):
    """One FO4 vertex per SPOTS entry: pure neighbourhood, gentle slope, decoded BTD = FO4 height / 70 within
    SPOT_MAX_ERROR_M under every interpolation rule, away from the other plan points; nearest to near_m."""
    from numpy.lib.stride_tricks import sliding_window_view
    rows, cols = heights.shape
    out = []
    for label, desc, wanted, min_d, radius, purity in SPOTS:
        idx = [i for i, k in enumerate(fo4_keys) if k in wanted]
        if not idx:
            print(f"  {label}: none of {wanted} in the region")
            continue
        pur = sum(fo4_w[i] for i in idx)
        k = 2 * radius + 1
        er = np.full(pur.shape, 0.0)
        er[radius:rows - radius, radius:cols - radius] = sliding_window_view(pur, (k, k)).min(axis=(-1, -2))
        rr, cc = np.nonzero(er >= purity)
        xm = m(origin_units[0] + cc * tg.FO4_VERTEX_UNITS)
        ym = m(origin_units[1] + rr * tg.FO4_VERTEX_UNITS)
        d = np.hypot(xm - near_m[0], ym - near_m[1])
        pick = None
        for j in np.argsort(d):
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
            pick = (r, c, float(d[j]), e)
            break
        if pick is None:
            print(f"  {label}: no vertex meets purity {purity}, slope {SPOT_MAX_SLOPE} and error {SPOT_MAX_ERROR_M} m")
            continue
        r, c, dist, e = pick
        x, y = m(origin_units[0] + c * tg.FO4_VERTEX_UNITS), m(origin_units[1] + r * tg.FO4_VERTEX_UNITS)
        used.append((x, y))
        top = sorted(((float(fo4_w[i][r, c]), fo4_keys[i]) for i in range(len(fo4_keys))), reverse=True)[:3]
        out.append({"label": label, "x": round(x, 4), "y": round(y, 4), "expect": round(m(float(heights[r, c])), 4),
                    "ground": desc, "purity": {"radius_vertices": radius, "min_weight": purity}, "fo4_textures": {kk: round(w, 3) for w, kk in top if w > 0.005},
                    "sf_mapped": ground_map.sf_for(top[0][1]), "dist_from_redrocket_m": round(dist, 1),
                    "slope_deg": round(tg.local_slope_deg(heights, r, c, tg.FO4_VERTEX_UNITS), 2),
                    "predicted_error_m": round(e, 6), "fo4_cell": list(fo4land.cell_of(x * 70, y * 70)),
                    "sf_cell": list(tg.sf_cell_of(x, y))})
    return out


def build(a):
    if not a.out:
        sys.exit("--out is required")
    src, out = os.path.abspath(a.source), os.path.abspath(a.out)
    if os.path.normcase(src) == os.path.normcase(out):
        sys.exit("--out must differ from --from")
    exp = read_json(os.path.join(src, "expected.json"))
    plan = read_json(os.path.join(src, "plan.json"))
    src_btd = read_bytes(os.path.join(src, "Data", "Terrain", BTD_NAME))
    t = btd.read(src_btd)
    n = t.ncx
    fc = exp["fo4_cells"]
    cells = (fc["x"][0], fc["x"][1], fc["y"][0], fc["y"][1])
    roi = exp["region_of_interest_m"]
    roi_cells = tg.fo4_cells_covering(roi["xmin"], roi["xmax"], roi["ymin"], roi["ymax"])
    print(f"BTD {n} x {n} cells, FO4 cells {cells}, region of interest cells {roi_cells}")

    names, cellw, vhgt, vclr, nobase = read_fo4(os.path.join(a.fo4_data, "Fallout4.esm"), cells, roi_cells)

    def fo4_name(fid):
        return names.get(fid, ground_map.FO4_DEFAULT) if fid else ground_map.FO4_DEFAULT

    unmapped = sorted({fo4_name(f) for w in cellw.values() for f in w} - set(ground_map.MAP))
    x0, x1, y0, y1 = cells
    sf_grid = landtex.WeightGrid(x0, y0, x1 - x0 + 1, y1 - y0 + 1, missing=ground_map.sf_for(ground_map.FO4_DEFAULT))
    rx0, rx1, ry0, ry1 = roi_cells
    fo4_grid = landtex.WeightGrid(rx0, ry0, rx1 - rx0 + 1, ry1 - ry0 + 1, missing=ground_map.FO4_DEFAULT)
    for xy, w in cellw.items():
        sf_grid.add_cell(*xy, w, key=lambda f: ground_map.sf_for(fo4_name(f)))
        if rx0 <= xy[0] <= rx1 and ry0 <= xy[1] <= ry1:
            fo4_grid.add_cell(*xy, w, key=fo4_name)
    sf_keys, sf_w = sf_grid.finish()
    fo4_keys, fo4_w = fo4_grid.finish()
    unknown_sf = [k for k in sf_keys if k not in ground_map.SF_FORMID]
    if unknown_sf:
        sys.exit(f"no Starfield FormID for {unknown_sf} (ground_map.SF_FORMID)")
    print(f"FO4: {len(cellw)} cells, {len(names)} LTEX, {nobase} quadrants without BTXT (default texture), "
          f"{len(fo4_keys)} textures in the region; unmapped (category fallback): {unmapped}")

    order, qm, words, stats = encode_btd(sf_keys, sf_w, (x0 * 4096, y0 * 4096), n)
    new = btd.Btd(t.version, t.hmin, t.hmax, [ground_map.SF_FORMID[k] for k in order], t.heights_raw, words, qm)
    data = btd.write(new)
    d_src, d_new = btd.height_digest(src_btd), btd.height_digest(data)
    same = {k: d_src[k] == d_new[k] for k in d_src}
    print(f"BTD {len(data):,} B (source {len(src_btd):,}); height sections identical: {same}")
    if not all(same.values()):
        sys.exit("heights changed: refusing to stage")
    print(f"textures: table {order}\n  {json.dumps({k: v for k, v in stats.items() if k != 'coverage'})}")

    # ------------------------------------------------------------------ stage (copy exp2b2, replace the BTD)
    if os.path.exists(out):
        mine = os.path.exists(os.path.join(out, "expected.json")) and \
            read_json(os.path.join(out, "expected.json")).get("experiment") == "terrain_exp2t"
        if not (a.replace and mine):
            sys.exit(f"{out} exists; pass --replace to rebuild an earlier exp2t staging there, or pick another folder")
        shutil.rmtree(out)
    os.makedirs(out)
    for f in os.listdir(src):
        p = os.path.join(src, f)
        if os.path.isfile(p) and (f.lower().endswith(".esm") or f == "exp2_params.json"):
            shutil.copy2(p, os.path.join(out, f))
    for root, _dirs, files in os.walk(os.path.join(src, "Data")):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), src)
            dst = os.path.join(out, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if f.lower() == BTD_NAME.lower():
                with open(dst, "wb") as fh:
                    fh.write(data)
            else:
                shutil.copy2(os.path.join(root, f), dst)
    btd_copies = [os.path.relpath(os.path.join(r, f), out) for r, _d, fs in os.walk(os.path.join(out, "Data"))
                  for f in fs if f.lower() == BTD_NAME.lower()]

    # ------------------------------------------------------------------ spots + plan
    merged, _ = fo4land.merge_cells(vhgt, rx0, ry0, rx1 - rx0 + 1, ry1 - ry0 + 1)
    dec_h = new.heights_m()
    o = tg.grid_origin(n)
    step = (t.hmax - t.hmin) / 65535.0
    origin_roi = (rx0 * 4096.0, ry0 * 4096.0)

    def err(r, c):
        xu, yu = origin_roi[0] + c * tg.FO4_VERTEX_UNITS, origin_roi[1] + r * tg.FO4_VERTEX_UNITS
        hs = tg.point_interp(dec_h, o, o, tg.SF_STEP_M, m(xu), m(yu))
        return max(abs(h - m(float(merged[r, c]))) for h in hs.values())

    test = dict(plan[0])
    used = [(p["x"], p["y"]) for p in test["points"]]
    rr = exp["structure"]["pos_m"]
    spots = find_spots(fo4_keys, fo4_w, merged, origin_roi, rr, err, step, used)
    back = btd.read(data)
    for s in spots:
        s["sf_decoded"] = decoded_at(back, order, n, s["x"], s["y"])
        s["sf_mapped_in_table"] = s["sf_mapped"] in order
    test["label"] = (f"terrain exp2t: exp2b2 ({n}x{n}-cell BTD, Absolute, Mars) with FO4 ground textures mapped to "
                     f"{len(order)} vanilla Starfield LTEX; screenshots at {len(spots)} ground-type spots")
    test["points"] = list(test["points"]) + [{k: s[k] for k in ("label", "x", "y", "expect")} for s in spots]
    test["fresh"] = True
    write_json(os.path.join(out, "plan.json"), [test])
    ltex = {"table": [{"index": i, "formid": "%08X" % ground_map.SF_FORMID[k], "edid": k,
                       "coverage": round(stats["coverage"][k], 5)} for i, k in enumerate(order)],
            "rule": "table order = rarest first (top layers) .. most common last (bottom); per quadrant the 6 textures "
                    "with the largest weight, bytes 0..4 slots (alpha group k), byte 6 base, ascending table index"}
    fo4_cov = {k: float(w.sum()) for k, w in zip(fo4_keys, fo4_w)}
    tot = sum(fo4_cov.values())
    expected = dict(exp, experiment="terrain_exp2t", ltex=ltex, spawn_local=test.get("spawn_local"),
                    ground_textures={
                        "source": "FO4 LAND BTXT/ATXT/VTXT of every footprint cell, over-compositing per quadrant, "
                                  "bilinear onto the BTD grid, fo4sf.ground_map (FO4 LTEX -> vanilla Starfield LTEX)",
                        "heights_identical_to": os.path.join(src, "Data", "Terrain", BTD_NAME), "height_digest": d_new,
                        "encode_stats": stats, "fo4_quadrants_without_btxt": nobase, "unmapped_fo4": unmapped,
                        "region_fo4_coverage": {k: round(v / tot, 4) for k, v in
                                                sorted(fo4_cov.items(), key=lambda kv: -kv[1])},
                        "mapping_used": {k: ground_map.sf_for(k) for k in fo4_keys},
                        "spots": spots, "btd_copies": btd_copies})
    expected["btd_bytes"] = len(data)
    write_json(os.path.join(out, "expected.json"), expected)
    readme(out, src, n, order, spots, test, len(data), btd_copies)
    if a.palette:
        render_all(a, out, read_json(a.palette), fo4_keys, fo4_w, merge_vclr(vclr, rx0, ry0, rx1 - rx0 + 1,
                                                                             ry1 - ry0 + 1),
                   origin_roi, back, order, n, roi, spots, test, rr)
    else:
        print("no --palette: reference renders skipped")
    print(f"staged {out}: plan {len(test['points'])} points ({len(spots)} ground spots), fresh: true")
    return 0


def decoded_at(t, order, n, x, y):
    """Top decoded Starfield textures (weight > 1 %) at the BTD sample nearest to world (x, y)."""
    o = tg.grid_origin(n)
    c, r = int(round((x - o) / tg.SF_STEP_M)), int(round((y - o) / tg.SF_STEP_M))
    qy, qx = r // 64, c // 64
    q = t.quad_map[qy:qy + 1, qx:qx + 1]
    w = t.weights[qy * 64:(qy + 1) * 64, qx * 64:(qx + 1) * 64]
    dec = landtex.decode(q, w, len(order))[:, r - qy * 64, c - qx * 64]
    return {order[i]: round(float(dec[i]), 3) for i in np.argsort(-dec) if dec[i] > 0.01}


def readme(out, src, n, order, spots, test, nbytes, copies):
    lines = [
        "Terrain experiment 2t (Claude, 2026-10-11). NOT deployed. Recipe: docs/terrain/ground-textures.md",
        "(branch claude/terrain-ground-textures, stacked on claude/terrain-overlay-records).",
        f"exp2b2 ({src}) with Fallout 4's ground textures in the BTD: the {n} x {n}-cell BTD keeps its heights byte for",
        "byte (header, cell min/max, LOD4 heights and every block's height half; SHA-256 in expected.json) and gets a new",
        f"LTEX table of {len(order)} vanilla Starfield land textures, quadrant texture bytes and 3-bit alphas mapped from",
        "the FO4 LAND layers (BTXT/ATXT/VTXT). Plugins, overlay mask and params are exp2b2's, unchanged.",
        f"BTD: {nbytes:,} B, staged at: {', '.join(copies)}.",
        "",
        "Install (game closed). The runner does it; --pack stores the Data tree uncompressed in 'FO4TerrainExp2 - Main.ba2':",
        "  scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> "
        "--plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm --pack",
        "Queue (one test, relaunch first because repeat coc into a merged world is erratic):",
        f"  python scripts/game/testqueue.py plan-terrain --staging <build dir> --exp-dir {out} --out <queue dir> "
        "--plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm --fresh",
        "",
        "In game: coc FO4CW_RedRocketSpawn, then the usual 14 probes and these ground-type spots (worldspace frame; the",
        "runner adds the merge offset from the arrival). Every probe takes a screenshot looking north (pt<k>.png):",
    ]
    base = len(test["points"]) - len(spots)
    for k, s in enumerate(spots):
        lines.append(f"  pt{base + k:<3d} {s['label']:13s} x {s['x']:10.4f} y {s['y']:10.4f} -> {s['expect']:9.4f}  "
                     f"FO4 {', '.join(s['fo4_textures'])} -> Starfield {s['sf_mapped']}")
    lines += ["Compare with reference/compare_spots.png (FO4 vs mapped Starfield textures, top-down, illustrative tiling)",
              "and reference/compare_overview.png (average colours over the region of interest, hill-shaded).",
              "Uninstall: exp_install.py uninstall."]
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
            txt = ", ".join(s["fo4_textures"]) if side == "FO4" else ", ".join(s["sf_decoded"])
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
def check(a):
    """Staged exp2t: heights identical to --from, texture sections decode, plan spots present."""
    out, src = os.path.abspath(a.out), os.path.abspath(a.source)
    exp = read_json(os.path.join(out, "expected.json"))
    plan = read_json(os.path.join(out, "plan.json"))
    ok = True
    src_d = btd.height_digest(read_bytes(os.path.join(src, "Data", "Terrain", BTD_NAME)))
    copies = exp["ground_textures"]["btd_copies"]
    first = None
    for rel in copies:
        data = read_bytes(os.path.join(out, rel))
        first = first or data
        d = btd.height_digest(data)
        same = all(d[k] == src_d[k] for k in src_d)
        ok &= same and data == first
        print(f"{rel}: {len(data):,} B, heights identical to the source: {same}, same bytes as the first copy: "
              f"{data == first}")
    t = btd.read(first)
    order = [e["edid"] for e in exp["ltex"]["table"]]
    ids = ["%08X" % f for f in t.ltex]
    table_ok = ids == [e["formid"] for e in exp["ltex"]["table"]]
    ok &= table_ok
    q = t.quad_map.reshape(-1, 8)
    layout_ok = bool((q[:, 5] == 0).all() and (q[:, 7] == 0).all() and (q <= len(order)).all() and (q[:, 0] > 0).all())
    ok &= layout_ok
    print(f"LTEX table matches expected.json: {table_ok}; quadrant bytes 5 and 7 empty, values <= n, slot 0 set: "
          f"{layout_ok}; weights max {int(t.weights.max())}, bit 15 set {int((t.weights >> 15).sum())}")
    for s in exp["ground_textures"]["spots"]:
        got = decoded_at(t, order, t.ncx, s["x"], s["y"])
        top = next(iter(got))
        good = top == s["sf_mapped"]
        print(f"  {s['label']:13s} FO4 {list(s['fo4_textures'])} -> mapped {s['sf_mapped']}, decoded {got} "
              f"{'ok' if good else 'DIFFERENT TOP TEXTURE'}")
        ok &= good
    pts = {p["label"] for p in plan[0]["points"]}
    ok &= all(s["label"] in pts for s in exp["ground_textures"]["spots"]) and plan[0].get("fresh") is True
    print(f"plan: {len(plan[0]['points'])} points, fresh {plan[0].get('fresh')}; check {'PASS' if ok else 'FAIL'}")
    write_json(os.path.join(out, "offline_check_textures.json"), {"pass": bool(ok), "source_digest": src_d})
    return ok


# ------------------------------------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("palette", "suggest", "build", "check"))
    ap.add_argument("--fo4-data", default=r"C:\Program Files (x86)\Steam\steamapps\content\app_377160\depot_377163\Data")
    ap.add_argument("--sf-data", default=r"D:\SteamLibrary\steamapps\common\Starfield\Data")
    ap.add_argument("--content-resources", default=r"D:\SteamLibrary\steamapps\common\Starfield\Tools\ContentResources.zip")
    ap.add_argument("--from", dest="source", help="staged exp2b2 folder (BTD, plugins, mask, plan)")
    ap.add_argument("--palette", help="palette.json from the palette command (renders use its colours)")
    ap.add_argument("--replace", action="store_true", help="build: replace an earlier exp2t staging in --out")
    ap.add_argument("--out", help="output: palette.json (palette), suggestion json (suggest), staging dir (build/check)")
    a = ap.parse_args(argv)
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
