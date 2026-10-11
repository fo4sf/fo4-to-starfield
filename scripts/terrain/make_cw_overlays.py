"""Commonwealth terrain as Starfield overlay worldspaces: one overlay or a grid of edge-matched tiles for any FO4 cell
rectangle (docs/terrain/commonwealth-scale.md). Experiment 3 = 2 x 2 tiles of 14 x 14 cells around Sanctuary,
Vault 111 and Red Rocket.

    python scripts/terrain/make_cw_overlays.py build --fo4 <Fallout4.esm> --sf-data <Starfield Data> --out <dir>
        [--fo4-cells -35 10 -6 40] [--tile 14] [--prefix FO4CW3] [--plugin FO4TerrainExp3.esm] ...
    dotnet run --project dotnet/TerrainOverlays -c Release -- <Starfield.esm> <dir>     (reads overlays_params.json)
    python scripts/terrain/make_cw_overlays.py check --sf-data <Starfield Data> --out <dir>

build writes, all OUTSIDE the repo (derived game data):
  Data/Terrain/<WORLD>.btd                     one BTD per tile, FO4 heights / 70 at CW positions, one shared range
  Data/textures/terrain/overlaymasks/<world>.dds   255 on the outer edges' cell ring, 0 on seams between tiles
  overlays_params.json   what dotnet/TerrainOverlays needs (worlds, blocks, FNAM, anchors, COC, lat/long per tile)
  plan.json              runner format: one entry per tile (own anchor, own frame), one group entry (seam pairs of all
                         tiles in the first tile's frame: passes only if the tiles lie edge to edge in game) and one
                         position entry per other tile read from the first tile's landing
  expected.json, README.txt, preview.png
check re-reads the staged files: decoded heights at every plan point, seam continuity, masks, and a raw record walk of
both plugins (WRLD, XLCN/LCTN, SFBK, anchor, COC cell, PNDT CNAM entries).

Placement (hypothesis H_ll, src/fo4sf/overlay_grid.py): tile lat/long from one measured registration (World01 on
Mars) at true planet scale. Supported, not verified: the experiment measures it (anchors per tile).
"""
import argparse
import json
import math
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
sys.path.insert(0, HERE)
from fo4sf import btd, fo4land, overlay  # noqa: E402
from fo4sf import overlay_grid as og  # noqa: E402
from fo4sf import terrain_grid as tg  # noqa: E402
import overlay_records as orc  # noqa: E402

SPAWN_ABOVE = 2.0
MAX_SLOPE = 25.0
FO4_GRID = (-96, 95)                    # Commonwealth LAND cells on both axes (verified, architecture.md 2)
# FO4 references used as landmarks (Fallout4.esm, Commonwealth; FO4 units): the Red Rocket building (as experiment 2)
# and the Sanctuary / Vault 111 map markers
LANDMARKS = (("redrocket", 0x000211C0, -69232.0, 80304.0),
             ("sanctuary", 0x00072A48, -80768.19, 88174.80),
             ("vault111", 0x0009F272, -89271.98, 91369.30))
DIST = {"near": (0.8, 2.7), "ring": (40.0, 60.0), "inner": (140.0, 170.0)}   # metres from the seam, per side
PLAN_KEYS = ("coc", "label", "anchor", "drop_z", "settle_ms", "points")


def m(units):
    return units / tg.UNITS_PER_METRE


# ---------------------------------------------------------------------------------------------------------------- FO4
class Fo4Heights:
    """Decoded FO4 LAND vertex grids {(cx, cy): (33, 33) FO4 units} from Fallout4.esm or a cached .npz
    (arrays 'grid' (N, 2) cell coordinates and 'heights' (N, 33, 33))."""

    def __init__(self, esm=None, npz=None):
        self.esm, self.npz, self.grids = esm, npz, {}

    def load(self, cells):
        want = {c for c in cells if c not in self.grids}
        if not want:
            return
        if self.npz:
            z = np.load(self.npz)
            for (x, y), h in zip(z["grid"].tolist(), z["heights"]):
                if (x, y) in want:
                    self.grids[(x, y)] = h.astype(np.float64)
        else:
            with fo4land.Plugin(self.esm) as p:
                world = p.read_world("Commonwealth", cells=want, refs=False)
            for xy, c in world["cells"].items():
                if c["vhgt"]:
                    self.grids[xy] = fo4land.decode_vhgt(c["vhgt"])

    def merged(self, x0, x1, y0, y1):
        """Merged vertex grid and its CW-unit origin for the inclusive FO4 cell rectangle (clamped to the LAND grid)."""
        x0, x1 = max(x0, FO4_GRID[0]), min(x1, FO4_GRID[1])
        y0, y1 = max(y0, FO4_GRID[0]), min(y1, FO4_GRID[1])
        cells = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
        self.load(cells)
        missing = [c for c in cells if c not in self.grids]
        if missing:
            sys.exit(f"FO4 cells without VHGT: {missing[:8]} ({len(missing)})")
        g, _ = fo4land.merge_cells(self.grids, x0, y0, x1 - x0 + 1, y1 - y0 + 1)
        return g, (x0 * tg.FO4_CELL_UNITS, y0 * tg.FO4_CELL_UNITS)


def tile_vertices(fo4, tile):
    """FO4 vertex grid around a tile (one extra FO4 cell on every side) and its origin in FO4 units."""
    x0, x1, y0, y1 = tile.bounds_m
    cx0, cx1, cy0, cy1 = tg.fo4_cells_covering(x0, x1, y0, y1)
    return fo4.merged(cx0 - 1, cx1 + 1, cy0 - 1, cy1 + 1)


def tile_heights(fo4, tile):
    """Tile heights in metres [row, col] (row 0 = south) at its BTD sample positions (CW frame)."""
    g, (ox, oy) = tile_vertices(fo4, tile)
    xs, ys = tile.sample_coords()
    return tg.resample_bilinear(g, ox, oy, tg.FO4_VERTEX_UNITS, xs * tg.UNITS_PER_METRE,
                                ys * tg.UNITS_PER_METRE) / tg.UNITS_PER_METRE


# ---------------------------------------------------------------------------------------------------------- points
class TileData:
    def __init__(self, tile, raw, hmin, hmax, verts, vorigin):
        self.tile, self.raw = tile, raw
        self.dec = hmin + raw.astype(np.float64) / 65535.0 * (hmax - hmin)
        self.step = (hmax - hmin) / 65535.0
        self.verts, self.vorigin = verts, vorigin       # FO4 vertex grid (units) and its origin (units)

    def decoded(self, x_cw, y_cw):
        """Height of the written BTD at a CW position under bilinear and both triangle splits."""
        lx, ly = self.tile.to_local(x_cw, y_cw)
        o = tg.grid_origin(self.tile.n)
        return tg.point_interp(self.dec, o, o, tg.SF_STEP_M, lx, ly)

    def vertex(self, r, c):
        """CW position (m) and FO4 height (m) of vertex (r, c) of the tile's FO4 grid."""
        xu = self.vorigin[0] + c * tg.FO4_VERTEX_UNITS
        yu = self.vorigin[1] + r * tg.FO4_VERTEX_UNITS
        return m(xu), m(yu), m(float(self.verts[r, c]))

    def rc_of(self, x_cw, y_cw):
        return ((y_cw * tg.UNITS_PER_METRE - self.vorigin[1]) / tg.FO4_VERTEX_UNITS,
                (x_cw * tg.UNITS_PER_METRE - self.vorigin[0]) / tg.FO4_VERTEX_UNITS)

    def rc_global(self, i, j):
        """Row and column in this tile's FO4 grid of the global vertex (i, j) at (128 i, 128 j) FO4 units."""
        return (j - int(self.vorigin[1] // tg.FO4_VERTEX_UNITS), i - int(self.vorigin[0] // tg.FO4_VERTEX_UNITS))

    def eligible(self, r, c, max_slope=MAX_SLOPE):
        """FO4 vertex inside the tile's own samples whose decoded height equals the FO4 height within one quantisation
        step under every interpolation rule, on a slope the player can stand on."""
        if not (1 <= r < self.verts.shape[0] - 1 and 1 <= c < self.verts.shape[1] - 1):
            return False
        x, y, z = self.vertex(r, c)
        x0, x1, y0, y1 = self.tile.bounds_m
        last = tg.SF_STEP_M
        if not (x0 <= x <= x1 - last and y0 <= y <= y1 - last):
            return False
        if tg.local_slope_deg(self.verts, r, c, tg.FO4_VERTEX_UNITS) > max_slope:
            return False
        return max(abs(v - z) for v in self.decoded(x, y).values()) <= self.step

    def point(self, r, c, label, kind, **meta):
        x, y, z = self.vertex(r, c)
        hs = self.decoded(x, y)
        return {"label": label, "kind": kind, "tile": self.tile.tag, "x_cw": round(x, 4), "y_cw": round(y, 4),
                "expect": round(z, 4), "fo4_units": [x * 70.0, y * 70.0, z * 70.0],
                "fo4_cell": list(fo4land.cell_of(x * 70.0, y * 70.0)), "sf_cell_cw": list(tg.sf_cell_of(x, y)),
                "slope_deg": round(tg.local_slope_deg(self.verts, r, c, tg.FO4_VERTEX_UNITS), 2),
                "decoded": {k: round(v, 5) for k, v in hs.items()},
                "error_m": round(max(abs(v - z) for v in hs.values()), 6), **meta}

    def nearest_eligible(self, x_cw, y_cw, radius=12, max_slope=MAX_SLOPE, prefer_flat=False):
        r0, c0 = (int(round(v)) for v in self.rc_of(x_cw, y_cw))
        cand = sorted(((r, c) for r in range(r0 - radius, r0 + radius + 1) for c in range(c0 - radius, c0 + radius + 1)),
                      key=lambda t: (t[0] - r0) ** 2 + (t[1] - c0) ** 2)
        if prefer_flat:
            for r, c in cand:
                if self.eligible(r, c, max_slope=3.0):
                    return r, c
        return next(((r, c) for r, c in cand if self.eligible(r, c, max_slope)), None)


def vertex_indices_between(lo_m, hi_m):
    """Global FO4 vertex indices k (vertex at k * 128 units = k * 128 / 70 m) with lo_m <= position <= hi_m."""
    s = tg.FO4_VERTEX_UNITS / tg.UNITS_PER_METRE
    return [k for k in range(int(math.floor(lo_m / s)) - 1, int(math.ceil(hi_m / s)) + 2) if lo_m <= k * s <= hi_m]


def seam_pairs(seam, ta, tb, ends=150.0):
    """For each distance class a pair of FO4 vertices on the same FO4 vertex line across the seam, one in tile a (west
    / south) and one in tile b (east / north), DIST metres from the seam line and at least `ends` metres from the ends
    of the segment. Classes are spread along the segment. Returns [(cls, pa, pb)]."""
    out = []
    lo, hi = seam["span_m"]
    at = seam["at_m"]
    s = tg.FO4_VERTEX_UNITS / tg.UNITS_PER_METRE
    along_ok = vertex_indices_between(lo + ends, hi - ends)
    for k, (cls, (dmin, dmax)) in enumerate(DIST.items()):
        mid = (lo + (hi - lo) * (k + 1) / (len(DIST) + 1)) / s
        best = None
        for j in sorted(along_ok, key=lambda v: abs(v - mid)):
            ia = vertex_indices_between(at - dmax, at - dmin)
            ib = vertex_indices_between(at + dmin, at + dmax)
            if seam["axis"] == "x":
                ga = [ta.rc_global(i, j) for i in reversed(ia)]
                gb = [tb.rc_global(i, j) for i in ib]
            else:
                ga = [ta.rc_global(j, i) for i in reversed(ia)]
                gb = [tb.rc_global(j, i) for i in ib]
            ea = next((rc for rc in ga if ta.eligible(*rc)), None)
            eb = next((rc for rc in gb if tb.eligible(*rc)), None)
            if ea and eb:
                best = (ea, eb)
                break
        if best is None:
            sys.exit(f"no eligible {cls} pair on seam {seam['name']}")
        name = f"{seam['axis']}_T{ta.tile.tag}_T{tb.tile.tag}_{cls}"
        pa = ta.point(*best[0], name + "_a", "seam", seam=seam["name"], side="a", distance_class=cls)
        pb = tb.point(*best[1], name + "_b", "seam", seam=seam["name"], side="b", distance_class=cls)
        for p in (pa, pb):
            p["distance_to_seam_m"] = round(abs((p["x_cw"] if seam["axis"] == "x" else p["y_cw"]) - at), 4)
        out.append((cls, pa, pb))
    return out


def interior_points(td, tiles):
    """Landmarks in the tile (at least two cells from an outer edge), else a flat vertex near the tile's centre, plus
    the steepest eligible vertex (5..25 deg) within 150 m of the centre."""
    t = td.tile
    outer = og.outer_edges(t, tiles)
    x0, x1, y0, y1 = t.bounds_m
    margin = {e: 200.0 if e in outer else 0.0 for e in overlay.EDGES}
    pts = []
    for name, fid, xu, yu in LANDMARKS:
        x, y = m(xu), m(yu)
        if x0 + margin["w"] <= x < x1 - margin["e"] and y0 + margin["s"] <= y < y1 - margin["n"]:
            rc = td.nearest_eligible(x, y)
            if rc:
                p = td.point(*rc, name, "landmark", landmark_fid="%08X" % fid,
                             landmark_m=[round(x, 4), round(y, 4)])
                p["dist_from_landmark_m"] = round(math.hypot(p["x_cw"] - x, p["y_cw"] - y), 2)
                pts.append(p)
    cx, cy = t.origin_m
    centre = td.nearest_eligible(cx + 50.0, cy + 50.0, radius=40, prefer_flat=True)
    if centre is None:
        sys.exit(f"no eligible vertex near the centre of tile {t.tag}")
    pts.append(td.point(*centre, f"centre_T{t.tag}", "centre"))
    r0, c0 = (int(round(v)) for v in td.rc_of(cx + 50.0, cy + 50.0))
    best = None
    for r in range(r0 - 80, r0 + 81, 2):
        for c in range(c0 - 80, c0 + 81, 2):
            s = tg.local_slope_deg(td.verts, r, c, tg.FO4_VERTEX_UNITS)
            if 5.0 <= s <= MAX_SLOPE and (best is None or s > best[0]) and td.eligible(r, c):
                best = (s, r, c)
    if best:
        pts.append(td.point(best[1], best[2], f"slope_T{t.tag}", "slope"))
    return pts, centre


# ---------------------------------------------------------------------------------------------------------- build
def build(a):
    tiles = og.split(*og.sf_cells_of_fo4_rect(*a.fo4_cells), a.tile, a.pad)
    gx, gy = og.grid_shape(tiles)
    print(f"FO4 cells {a.fo4_cells} -> {len(tiles)} tiles ({gx} x {gy}) of {a.tile} x {a.tile} cells: " +
          ", ".join(f"T{t.tag} x {t.cells_x} y {t.cells_y}" for t in tiles))
    fo4 = Fo4Heights(a.fo4, a.fo4_npz)
    need = set()
    for t in tiles:                                   # read every FO4 cell once
        cx0, cx1, cy0, cy1 = tg.fo4_cells_covering(*t.bounds_m)
        need |= {(x, y) for x in range(max(cx0 - 1, FO4_GRID[0]), min(cx1 + 1, FO4_GRID[1]) + 1)
                 for y in range(max(cy0 - 1, FO4_GRID[0]), min(cy1 + 1, FO4_GRID[1]) + 1)}
    fo4.load(need)
    print(f"FO4 cells read: {len(fo4.grids)}")
    lo, hi = math.inf, -math.inf
    for t in tiles:                                   # pass 1: shared height range
        h = tile_heights(fo4, t)
        lo, hi = min(lo, float(h.min())), max(hi, float(h.max()))
    hmin, hmax = og.height_range(lo, hi)
    step = (hmax - hmin) / 65535.0
    table, quad = ltex_source(a.sf_data)
    tds = {}
    sizes = {}
    for t in tiles:                                   # pass 2: quantise and write
        h = tile_heights(fo4, t)
        raw = btd.quantize(h, hmin, hmax)
        data = btd.write(btd.Btd(6, hmin, hmax, table, raw, np.zeros_like(raw),
                                 np.tile(np.frombuffer(quad, np.uint8), (2 * t.n, 2 * t.n, 1))))
        path = os.path.join(a.out, "Data", "Terrain", world_name(a, t) + ".btd")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        sizes[t.tag] = len(data)
        verts, vorigin = tile_vertices(fo4, t)
        tds[t] = TileData(t, btd.read(data).heights_raw, hmin, hmax, verts, vorigin)
        print(f"  T{t.tag}: {path} ({len(data):,} B), heights {h.min():.2f}..{h.max():.2f} m")
    print(f"shared range {hmin}..{hmax} m, step {step * 1000:.3f} mm")

    # seams: continuity of the raw samples across every seam (same lattice, same range)
    seam_list = og.seams(tiles)
    seam_rep = [seam_continuity(s, tds[s["a"]], tds[s["b"]]) for s in seam_list]

    # points
    own, anchors, spawns = {}, {}, {}
    for t in tiles:
        pts, centre = interior_points(tds[t], tiles)
        own[t] = pts
        rr = next((p for p in pts if p["label"] == "redrocket"), None)
        ap = rr or next(p for p in pts if p["kind"] == "centre")
        anchors[t] = ap
    pairs = {}
    for s in seam_list:
        pairs[s["name"]] = seam_pairs(s, tds[s["a"]], tds[s["b"]])
        for cls, pa, pb in pairs[s["name"]]:
            own[s["a"]].append(pa)
            own[s["b"]].append(pb)

    targets = og.group_targets(tiles, tuple(a.centre_cell))
    ref = (a.ref_lat, a.ref_lon)
    latlon = {t: og.latlon_for_offset(targets[t], ref, tuple(a.ref_offset), a.radius_km) for t in tiles}
    stage(a, tiles, tds, own, anchors, pairs, seam_rep, targets, latlon, hmin, hmax, sizes, table, quad)


def ltex_source(sf_data):
    """LTEX table and quadrant bytes of vanilla TempJemisonWorld (one plain ground texture), as experiment 2."""
    import make_exp2
    return make_exp2.ltex_template(sf_data)


def world_name(a, t):
    return f"{a.prefix}_T{t.tag}"


def seam_continuity(s, ta, tb):
    """Raw u16 steps across the seam against the steps next to it on both sides: a seam that continues the lattice
    has no step larger than the local slope allows."""
    a_last, b_first = og.seam_raw_continuity(ta.raw.astype(np.int64), tb.raw.astype(np.int64), s["axis"])
    if s["axis"] == "x":
        a_prev, b_next = ta.raw[:, -2].astype(np.int64), tb.raw[:, 1].astype(np.int64)
    else:
        a_prev, b_next = ta.raw[-2, :].astype(np.int64), tb.raw[1, :].astype(np.int64)
    across = np.abs(b_first - a_last)
    beside = np.maximum(np.abs(a_last - a_prev), np.abs(b_next - b_first))
    bad = int((across > 2 * beside + 2).sum())
    return {"seam": s["name"], "axis": s["axis"], "at_m": s["at_m"], "samples": int(across.size),
            "max_step_across_m": float(across.max()) * ta.step, "max_step_beside_m": float(beside.max()) * ta.step,
            "samples_with_step_over_2x_local": bad}


def to_plan_point(p, frame_tile):
    x, y = frame_tile.to_local(p["x_cw"], p["y_cw"])
    return {"label": p["label"], "x": round(x, 4), "y": round(y, 4), "expect": p["expect"]}


def drop_z(points):
    return float(math.ceil((max(p["expect"] for p in points) + 25.0) / 5.0) * 5.0)


def stage(a, tiles, tds, own, anchors, pairs, seam_rep, targets, latlon, hmin, hmax, sizes, table, quad):
    first = tiles[0]
    overlays, plan = [], []
    for k, t in enumerate(tiles):
        w = world_name(a, t)
        ap = anchors[t]
        ax, ay = t.to_local(ap["x_cw"], ap["y_cw"])
        local = [round(ax, 4), round(ay, 4), ap["expect"]]
        fid = orc.ANCHOR_ID + k
        mask_edges = og.outer_edges(t, tiles)
        overlays.append({
            "world": w, "tag": t.tag, "ix": t.ix, "iy": t.iy, "n": t.n,
            "cells_cw": {"x": list(t.cells_x), "y": list(t.cells_y)}, "origin_cw_m": list(t.origin_m),
            "cell_min": tg.cell_range(t.n)[0], "cell_max": tg.cell_range(t.n)[1],
            "btd_path": f"Data\\TERRAIN\\{w}.btd", "btd_file": f"Data/Terrain/{w}.btd", "btd_bytes": sizes[t.tag],
            "fnam": overlay.fnam_values(tds[t].raw), "mask": orc.mask_rel(w), "mask_outer_edges": list(mask_edges),
            "coc": w + "Spawn", "spawn": [local[0], local[1], round(local[2] + SPAWN_ABOVE, 4)],
            "spawn_cell": list(tg.sf_cell_of(local[0], local[1])),
            "anchor": {"edid": w + "Anchor", "local": local, "form_id": fid, "ref": orc.anchor_ref(fid)},
            "location": w + "Location", "block": w + "Block",
            "bounds_min_m": tg.grid_origin(t.n), "bounds_max_m": tg.grid_origin(t.n) + t.n * tg.SF_CELL_M,
            "planet_target_cell": list(targets[t]),
            "latitude": latlon[t][0], "longitude": latlon[t][1]})
    by_tag = {o["tag"]: o for o in overlays}
    alignment_label = f"{a.alignment}, HNAM {a.hnam}"
    for t in tiles:
        o = by_tag[t.tag]
        pts = [to_plan_point(p, t) for p in own[t]]
        plan.append({"coc": o["coc"], "label": f"exp3 tile T{t.tag} ({t.n}x{t.n} cells, CW cells x {t.cells_x} "
                                              f"y {t.cells_y}; {alignment_label}): own heights and its side of every seam",
                     "anchor": {"ref": o["anchor"]["ref"], "local": o["anchor"]["local"]},
                     "spawn_local": o["anchor"]["local"], "drop_z": drop_z(pts), "settle_ms": 8000, "points": pts})
    seam_pts = [p for prs in pairs.values() for _, pa, pb in prs for p in (pa, pb)]
    fo = by_tag[first.tag]
    gpts = [to_plan_point(p, first) for p in seam_pts]
    plan.append({"coc": fo["coc"], "label": f"exp3 group: both sides of every seam in T{first.tag}'s frame "
                                            "(passes only if the tiles lie edge to edge and the seams are exact)",
                 "anchor": {"ref": fo["anchor"]["ref"], "local": fo["anchor"]["local"]},
                 "spawn_local": fo["anchor"]["local"], "drop_z": drop_z(gpts), "settle_ms": 8000, "points": gpts})
    for t in tiles[1:]:
        o = by_tag[t.tag]
        pts = [to_plan_point(p, t) for p in own[t] if p["kind"] in ("centre", "landmark", "slope")]
        plan.append({"coc": fo["coc"], "label": f"exp3 position: tile T{t.tag} read from T{first.tag}'s landing "
                                                f"(its anchor and own points; no spawn fallback)",
                     "anchor": {"ref": o["anchor"]["ref"], "local": o["anchor"]["local"]},
                     "drop_z": drop_z(pts), "settle_ms": 8000, "points": pts})

    mars = None if a.no_mars else {"plugin": a.mars_plugin, "planet": "MarsPlanetData",
                                   "radius_km": a.radius_km,
                                   "hypothesis": "H_ll: true planet scale from the reference registration",
                                   "reference": {"latitude": a.ref_lat, "longitude": a.ref_lon,
                                                 "offset_cells": list(a.ref_offset)}}
    params = {"plugin": a.plugin, "prefix": a.prefix, "hmin": hmin, "hmax": hmax, "alignment": a.alignment,
              "hnam": a.hnam, "mars": mars, "overlays": overlays,
              "note": "latitude/longitude in radians; PNDT CNAM stores latitude first (Mutagen calls it Longitude)"}
    masks = []
    for o in overlays:
        masks.append(write_mask(a.out, o["world"], o["n"], o["mask_outer_edges"], a.mask_writer))
    check = {"points": sum(len(e["points"]) for e in plan), "seams": seam_rep,
             "max_point_error_m": max(p["error_m"] for t in tiles for p in own[t]),
             "quantisation_step_m": (hmax - hmin) / 65535.0}
    expected = {"experiment": a.experiment, "plugin": a.plugin, "fo4_cells": list(a.fo4_cells), "tile": a.tile,
                "grid": list(og.grid_shape(tiles)), "height_range_m": [hmin, hmax],
                "quantisation_step_m": (hmax - hmin) / 65535.0,
                "ltex": {"table": ["%08X" % x for x in table], "quadrant_bytes": list(quad)},
                "frames": "CW = FO4 units / 70 from the FO4 origin; each tile's own frame = CW - origin_cw_m",
                "hypotheses": {"H": "BTD height = world z (Absolute, HNAM 0: no Z offset)",
                               "H_ll": "overlay merge offset moves at true planet scale near the reference registration",
                               "seams": "inner seams with mask 0 keep the tiles' own heights (no blend into procedural "
                                        "ground)"},
                "overlays": overlays, "seams": seam_rep,
                "points": {t.tag: own[t] for t in tiles}, "offline_check": check}
    for name, obj in (("plan.json", plan), ("expected.json", expected), ("overlays_params.json", params)):
        with open(os.path.join(a.out, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=1)
    readme(a, params, plan, masks)
    preview(tds, tiles, own, os.path.join(a.out, "preview.png"))
    print(json.dumps(check, indent=1))
    print(f"staged {len(tiles)} tiles, {len(plan)} plan entries, {check['points']} points in {a.out}; next: dotnet run "
          f"--project dotnet/TerrainOverlays -c Release -- <Starfield.esm> {a.out}")


def write_mask(out, world, n, edges, writer):
    img = overlay.mask_array(n, edges=edges) if edges else np.zeros((n * 100, n * 100), np.uint8)
    dst = os.path.join(out, *orc.mask_rel(world).split("/"))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if writer == "builtin":
        data = overlay.dds_bc4(img)
    else:
        import subprocess
        import tempfile
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            png = os.path.join(tmp, world.lower() + ".png")
            Image.fromarray(img, "L").save(png)
            r = subprocess.run([orc.TEXCONV, "-nologo", "-y", "-f", "BC4_UNORM", "-m", "1", "-o", tmp, png],
                               capture_output=True, text=True)
            made = os.path.join(tmp, world.lower() + ".dds")
            if r.returncode != 0 or not os.path.isfile(made):
                sys.exit("texconv failed:\n" + r.stdout + r.stderr)
            data = orc.read_bytes(made)
    with open(dst, "wb") as f:
        f.write(data)
    return mask_report(out, world, n, edges)


def mask_report(out, world, n, edges):
    data = orc.read_bytes(os.path.join(out, *orc.mask_rel(world).split("/")))
    info = overlay.dds_info(data)
    img = overlay.bc4_decode(data)
    want = overlay.mask_array(n, edges=edges) if edges else np.zeros((n * 100, n * 100), np.uint8)
    differ = int((img.astype(np.int32) != want.astype(np.int32)).sum()) if img.shape == want.shape else int(want.size)
    return {"file": orc.mask_rel(world), "bytes": len(data), "width": info["width"], "height": info["height"],
            "mips": info["mips"], "format": info["format"], "outer_edges": list(edges), "pixels_differ": differ}


def readme(a, params, plan, masks):
    pl = [params["plugin"]] + ([params["mars"]["plugin"]] if params.get("mars") else [])
    base = os.path.splitext(params["plugin"])[0]
    ov = params["overlays"]
    lines = [f"Terrain {a.experiment} (Claude, 2026-10-11). NOT deployed. Recipe: docs/terrain/commonwealth-scale.md",
             "(branch claude/commonwealth-terrain-scale).",
             f"{len(ov)} overlay worldspaces of {ov[0]['n']} x {ov[0]['n']} cells, edge to edge in the Commonwealth frame "
             f"(FO4 cells {a.fo4_cells}), one shared",
             f"height range {params['hmin']}..{params['hmax']} m, alignment {a.alignment} (HNAM {a.hnam}), one Location each,",
             "masks 255 only on the outer edges (seams between tiles 0), a persistent anchor and a COC cell per tile.",
             "Registered on Mars by " + (params["mars"]["plugin"] if params.get("mars") else "nothing") +
             " at lat/long chosen by hypothesis H_ll (true planet scale from World01's measured",
             "offset), so that the tiles should lie edge to edge around planet cell " + str(a.centre_cell) + ".",
             "Never install together with experiment 1 or 2 (all Mars plugins override MarsPlanetData).",
             "",
             "Install (game closed). The runner does it:",
             f"  scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> --plugins {','.join(pl)} --pack",
             f"  --pack puts Data\\Terrain and Data\\textures into \"{base} - Main.ba2\" (loose files are not read).",
             "",
             "Tiles (CW = Commonwealth frame, metres = FO4 units / 70):"]
    for o in ov:
        lines.append(f"  {o['world']}: CW cells x {o['cells_cw']['x']} y {o['cells_cw']['y']}, own origin at CW "
                     f"{o['origin_cw_m']}, coc {o['coc']}, anchor {o['anchor']['ref']} at local {o['anchor']['local']},")
        lines.append(f"      lat {o['latitude']:.9f} lon {o['longitude']:.9f} rad -> predicted planet cell "
                     f"{o['planet_target_cell']}, mask ring on {o['mask_outer_edges'] or 'no edge'}")
    lines += ["",
              "In game (test save), console, per plan entry: tgm; coc <coc>; prid <anchor ref>; getpos x/y/z -> A;",
              "offset O = A - anchor local; for every point: player.setpos x <x+O.x>, y <y+O.y>, z <drop_z+O.z>, wait,",
              "player.getpos z -> expect + O.z (+-0.5 m). Points are in the entry's frame (see the labels).",
              f"Plan: {len(plan)} entries ({len(ov)} tiles, 1 group, {len(ov) - 1} positions), "
              f"{sum(len(e['points']) for e in plan)} points.",
              "Reading: own entries pass -> each tile's heights exact (H); group passes -> tiles edge to edge and seams",
              "exact; position entries give each tile's planet cell in the first tile's landing (tests H_ll).",
              "", "Masks: " + ", ".join(f"{k['file']} ({k['width']} px, ring on {k['outer_edges'] or 'none'}, "
                                         f"{k['pixels_differ']} px differ)" for k in masks)]
    with open(os.path.join(a.out, "README.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def preview(tds, tiles, own, path, k=8):
    from PIL import Image, ImageDraw
    x0 = min(t.cx0 for t in tiles)
    y0 = min(t.cy0 for t in tiles)
    x1 = max(t.cx0 + t.n for t in tiles)
    y1 = max(t.cy0 + t.n for t in tiles)
    px = 128 // k
    W, H = (x1 - x0) * px, (y1 - y0) * px
    img = np.zeros((H, W))
    for t in tiles:
        d = tds[t].dec[::k, ::k]
        r0 = (t.cy0 - y0) * px
        c0 = (t.cx0 - x0) * px
        img[r0:r0 + d.shape[0], c0:c0 + d.shape[1]] = d
    img = img[::-1]
    lo, hi = float(img.min()), float(img.max())
    im = Image.fromarray(((img - lo) / max(hi - lo, 1e-6) * 255).astype(np.uint8)).convert("RGB")
    dr = ImageDraw.Draw(im)

    def xy(x, y):
        return (x / 100.0 - x0) * px, H - 1 - (y / 100.0 - y0) * px

    for t in tiles:
        bx0, bx1, by0, by1 = t.bounds_m
        a, b = xy(bx0, by1), xy(bx1, by0)
        dr.rectangle([a, b], outline=(255, 200, 0))
        dr.text((a[0] + 4, a[1] + 4), f"T{t.tag}", fill=(255, 200, 0))
    for t in tiles:
        for p in own[t]:
            x, y = xy(p["x_cw"], p["y_cw"])
            col = (255, 60, 60) if p["kind"] == "seam" else (60, 220, 255)
            dr.ellipse([x - 3, y - 3, x + 3, y + 3], outline=col)
    dr.text((4, H - 14), f"N up, {lo:.0f}..{hi:.0f} m; red: seam points, cyan: tile points", fill=(255, 255, 0))
    im.save(path)


# ---------------------------------------------------------------------------------------------------------- check
def check(a):
    prm = json.loads(orc.read_bytes(os.path.join(a.out, "overlays_params.json")))
    plan = json.loads(orc.read_bytes(os.path.join(a.out, "plan.json")))
    ok, rep = check_staging(a.out, prm, plan, orc.vanilla_mars_count(a.sf_data), plugins=not a.no_plugins)
    for what, good in rep["checks"]:
        if not good or a.verbose:
            print(("  ok   " if good else "  FAIL ") + what)
    print(f"  {sum(1 for c in rep['checks'] if c[1])} of {len(rep['checks'])} checks ok")
    for p in rep["points"]:
        if a.verbose:
            print(f"  {p['entry']:<5} {p['label']:<26} expect {p['expect']:9.4f} decoded {p['decoded']['bilinear']:9.4f} "
                  f"error {p['error_mm']:7.3f} mm (tile {p['tile']})")
    with open(os.path.join(a.out, "offline_check.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=1)
    print(json.dumps({k: rep[k] for k in ("summary", "seams", "mars") if k in rep}, indent=1))
    print("CHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def check_staging(out, prm, plan, vanilla_mars_entries=None, plugins=True):
    """Offline verification of a staged overlay grid. Returns (ok, report). plugins=False skips the record walk
    (before dotnet/TerrainOverlays ran, and in the synthetic tests)."""
    checks, rep = [], {}

    def need(cond, what):
        checks.append([what, bool(cond)])

    ovs = prm["overlays"]
    tiles, dec, raws, steps = {}, {}, {}, {}
    for o in ovs:
        t = og.Tile(o["ix"], o["iy"], o["cells_cw"]["x"][0], o["cells_cw"]["y"][0], o["n"])
        tiles[o["tag"]] = t
        b = btd.read(orc.read_bytes(os.path.join(out, *o["btd_file"].split("/"))))
        need(b.ncx == b.ncy == o["n"], f"{o['world']}: BTD {b.ncx} x {b.ncy} cells = DNAM {o['n']}")
        need((b.hmin, b.hmax) == (prm["hmin"], prm["hmax"]), f"{o['world']}: BTD range = shared {prm['hmin']}..{prm['hmax']}")
        need(overlay.fnam_match(struct.pack(f"<{len(o['fnam'])}H", *o["fnam"]), b.heights_raw)[0] == o["n"] ** 2,
             f"{o['world']}: params FNAM = SW-corner rule")
        need(list(t.origin_m) == o["origin_cw_m"], f"{o['world']}: origin {o['origin_cw_m']}")
        dec[o["tag"]], raws[o["tag"]], steps[o["tag"]] = b.heights_m(), b.heights_raw, (b.hmax - b.hmin) / 65535.0
    tl = list(tiles.values())
    # tiles abut exactly and seams continue the lattice
    seam_rep = []
    for s in og.seams(tl):
        ta, tb = s["a"], s["b"]
        ra, rb = raws[ta.tag].astype(np.int64), raws[tb.tag].astype(np.int64)
        a_last, b_first = og.seam_raw_continuity(ra, rb, s["axis"])
        a_prev = ra[:, -2] if s["axis"] == "x" else ra[-2, :]
        b_next = rb[:, 1] if s["axis"] == "x" else rb[1, :]
        across = np.abs(b_first - a_last)
        beside = np.maximum(np.abs(a_last - a_prev), np.abs(b_next - b_first))
        bad = int((across > 2 * beside + 2).sum())
        need(bad == 0, f"seam {s['name']}: no step across the seam beyond twice the local slope ({bad} samples)")
        xa = ta.bounds_m[1] if s["axis"] == "x" else ta.bounds_m[3]
        xb = tb.bounds_m[0] if s["axis"] == "x" else tb.bounds_m[2]
        need(xa == xb == s["at_m"], f"seam {s['name']}: tiles abut at {s['at_m']} m")
        seam_rep.append({"seam": s["name"], "max_step_across_m": float(across.max()) * steps[ta.tag],
                         "max_step_beside_m": float(beside.max()) * steps[ta.tag], "bad": bad})
    rep["seams"] = seam_rep
    # plan points: decode in the tile that holds each point (by CW position)
    by_ref = {o["anchor"]["ref"]: o for o in ovs}
    by_coc = {o["coc"]: o for o in ovs}
    pts = []
    for i, w in enumerate(plan):
        need(all(k in w for k in PLAN_KEYS), f"plan entry {i} has {', '.join(PLAN_KEYS)}")
        frame = by_ref.get(w["anchor"]["ref"])
        need(frame is not None and w["anchor"]["local"] == frame["anchor"]["local"], f"plan entry {i}: anchor = a tile anchor")
        need(w["coc"] in by_coc, f"plan entry {i}: coc {w['coc']} is a tile COC cell")
        if "spawn_local" in w:
            need(by_coc[w["coc"]]["anchor"]["ref"] == w["anchor"]["ref"], f"plan entry {i}: spawn_local only with its own tile")
        ft = tiles[frame["tag"]]
        need(w["drop_z"] > max(p["expect"] for p in w["points"]) + 10, f"plan entry {i}: drop_z above every point")
        for p in w["points"]:
            x, y = ft.to_cw(p["x"], p["y"])
            t = og.tile_at(tl, x, y)
            need(t is not None, f"plan entry {i} point {p['label']}: inside a tile")
            if t is None:
                continue
            lx, ly = t.to_local(x, y)
            o = tg.grid_origin(t.n)
            hs = tg.point_interp(dec[t.tag], o, o, tg.SF_STEP_M, lx, ly)
            e = max(abs(v - p["expect"]) for v in hs.values())
            pts.append({"entry": i, "label": p["label"], "tile": t.tag, "x": p["x"], "y": p["y"], "expect": p["expect"],
                        "decoded": {k: round(v, 4) for k, v in hs.items()}, "error_mm": round(e * 1000, 3)})
            need(e <= steps[t.tag], f"plan entry {i} point {p['label']}: decoded within one step in T{t.tag}")
    rep["points"] = pts
    for o in ovs:   # anchors on the ground of their own tile
        t = tiles[o["tag"]]
        ax, ay, az = o["anchor"]["local"]
        g = tg.point_interp(dec[o["tag"]], tg.grid_origin(t.n), tg.grid_origin(t.n), tg.SF_STEP_M, ax, ay)
        need(max(abs(v - az) for v in g.values()) <= steps[o["tag"]], f"{o['world']}: anchor z = ground")
        need(abs(o["spawn"][2] - az - SPAWN_ABOVE) < 1e-6 and o["spawn"][:2] == [ax, ay], f"{o['world']}: COC marker 2 m above the anchor")

    if plugins:
        check_plugins(out, prm, raws, need, rep, vanilla_mars_entries)
    masks = []
    for o in ovs:
        mk = mask_report(out, o["world"], o["n"], tuple(o["mask_outer_edges"]))
        need(mk["format"] == "BC4" and mk["mips"] == 1 and mk["width"] == mk["height"] == o["n"] * 100 and
             mk["pixels_differ"] == 0, f"{o['world']}: mask BC4 {mk['width']} px, ring on {mk['outer_edges']}, exact")
        masks.append(mk)
    rep["masks"] = masks
    rep["checks"] = checks
    ok = all(c[1] for c in checks)
    rep["summary"] = {"checks": len(checks), "failed": sum(1 for c in checks if not c[1]), "points": len(pts),
                      "max_point_error_mm": max(p["error_mm"] for p in pts) if pts else None,
                      "step_mm": round(min(steps.values()) * 1000, 4)}
    rep["pass"] = ok
    return ok, rep


def check_plugins(out, prm, raws, need, rep, vanilla_mars_entries):
    """Raw record walk of the overlay plugin and the Mars registration plugin (independent of Mutagen)."""
    ovs = prm["overlays"]
    d = orc.walk_plugin(os.path.join(out, prm["plugin"]))
    own = len(d["masters"]) << 24
    recs = d["records"]
    by_fid = {r["fid"]: r for r in recs}
    locs = set()
    wrld_fid = {}
    for k, o in enumerate(ovs):
        wr = [r for r in recs if r["sig"] == "WRLD" and orc.edid(r) == o["world"]]
        need(len(wr) == 1, f"one WRLD {o['world']}")
        if not wr:
            continue
        w = wr[0]
        wrld_fid[o["world"]] = w["fid"]
        xlcn = orc.field(w, "XLCN")
        loc = by_fid.get(struct.unpack("<I", xlcn)[0]) if xlcn else None
        need(loc is not None and loc["sig"] == "LCTN" and orc.edid(loc) == o["location"], f"{o['world']}: XLCN -> {o['location']}")
        if loc:
            locs.add(loc["fid"])
            kw = list(struct.unpack(f"<{len(orc.field(loc, 'KWDA', b'')) // 4}I", orc.field(loc, "KWDA", b"")))
            parent = struct.unpack("<I", orc.field(loc, "PNAM"))[0] if orc.field(loc, "PNAM") else None
            need(orc.LOC_TYPE_OVERLAY in kw and parent == orc.MARS_SURFACE, f"{o['world']}: location keyword + Mars parent")
        sfbk = by_fid.get(orc.overlay_block_ref(w))
        need(sfbk is not None and sfbk["sig"] == "SFBK" and orc.edid(sfbk) == o["block"], f"{o['world']}: overlay -> {o['block']}")
        if sfbk:
            fn = orc.field(sfbk, "FNAM", b"")
            exact, cells, worst = overlay.fnam_match(fn, raws[o["tag"]])
            need(fo4land.zstring(orc.field(sfbk, "ANAM", b"")) == o["btd_path"], f"{o['world']}: ANAM {o['btd_path']}")
            need(list(struct.unpack("<2I", orc.field(sfbk, "DNAM"))) == [o["n"], o["n"]], f"{o['world']}: DNAM {o['n']}")
            need(exact == cells == o["n"] ** 2, f"{o['world']}: FNAM {exact}/{cells} cells = SW-corner rule")
            need(list(struct.unpack("<2f", orc.field(sfbk, "ENAM"))) == [prm["hmin"], prm["hmax"]], f"{o['world']}: ENAM range")
            inam = orc.field(sfbk, "INAM", b"\0")[0]
            hnam = struct.unpack("<h", orc.field(sfbk, "HNAM", b"\0\0"))[0]
            need(inam == (1 if prm["alignment"] == "absolute" else 0) and hnam == prm["hnam"], f"{o['world']}: INAM {inam} HNAM {hnam}")
        an = [r for r in recs if r["sig"] == "REFR" and orc.edid(r) == o["anchor"]["edid"]]
        need(len(an) == 1, f"{o['world']}: one anchor REFR")
        if an:
            ar = fo4land.parse_ref(an[0]["fields"])
            need(ar["base"] == orc.XMARKER and an[0]["flags"] & orc.PERSISTENT, f"{o['world']}: anchor XMarker, persistent")
            need(an[0]["fid"] == own | o["anchor"]["form_id"] and o["anchor"]["ref"][2:].upper() == "%06X" % o["anchor"]["form_id"],
                 f"{o['world']}: anchor FormID {an[0]['fid']:08X} = plan ref {o['anchor']['ref']}")
            need(max(abs(p - q) for p, q in zip(ar["pos"], o["anchor"]["local"])) < 1e-3, f"{o['world']}: anchor at {ar['pos']}")
        coc = [r for r in recs if r["sig"] == "CELL" and orc.edid(r) == o["coc"]]
        need(len(coc) == 1, f"{o['world']}: COC cell {o['coc']}")
    need(len(locs) == len(ovs), "every overlay has its own Location (the CK warns about shared ones)")
    rep["plugin"] = {"file": prm["plugin"], "bytes": d["bytes"], "masters": d["masters"],
                     "records": {s: sum(1 for r in recs if r["sig"] == s) for s in sorted({r["sig"] for r in recs})}}

    if prm.get("mars"):
        mp = orc.walk_plugin(os.path.join(out, prm["mars"]["plugin"]))
        pl = [r for r in mp["records"] if r["sig"] == "PNDT"]
        need(len(pl) == 1 and pl[0]["fid"] == orc.MARS_PNDT, "Mars plugin overrides PNDT MarsPlanetData 0003F59A")
        need(mp["masters"][:1] == ["Starfield.esm"] and prm["plugin"] in mp["masters"], f"Mars plugin masters {mp['masters']}")
        idx = mp["masters"].index(prm["plugin"]) << 24 if prm["plugin"] in mp["masters"] else -1
        ents = orc.pndt_entries(pl[0]) if pl else []
        mine = []
        for o in ovs:
            e = [x for x in ents if x[2] == idx | (wrld_fid.get(o["world"], 0) & 0xFFFFFF)]
            need(len(e) == 1, f"PNDT CNAM has one entry for {o['world']}")
            if e:
                need(abs(e[0][0] - o["latitude"]) < 1e-12 and abs(e[0][1] - o["longitude"]) < 1e-12,
                     f"{o['world']}: CNAM latitude first, longitude second ({e[0][0]:.9f}, {e[0][1]:.9f})")
                mine.append({"world": o["world"], "f64_0_latitude": e[0][0], "f64_1_longitude": e[0][1],
                             "index": ents.index(e[0]), "predicted_cell": o["planet_target_cell"]})
        if vanilla_mars_entries is not None:
            need(len(ents) == vanilla_mars_entries + len(ovs), f"PNDT CNAM {len(ents)} = vanilla {vanilla_mars_entries} + {len(ovs)}")
        rep["mars"] = {"file": prm["mars"]["plugin"], "bytes": mp["bytes"], "entries": len(ents), "ours": mine}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("build", "check"))
    ap.add_argument("--fo4", help="Fallout4.esm")
    ap.add_argument("--fo4-npz", help="cached FO4 LAND grids (.npz with 'grid' and 'heights') instead of --fo4")
    ap.add_argument("--sf-data", required=True, help="Starfield Data folder (LTEX template BTD; Starfield.esm for check)")
    ap.add_argument("--out", required=True, help="staging folder, e.g. C:\\Modding\\staging\\terrain_exp3")
    ap.add_argument("--fo4-cells", type=int, nargs=4, default=[-35, 10, -6, 40], metavar=("X0", "X1", "Y0", "Y1"),
                    help="inclusive FO4 cell rectangle (default: experiment 3 around Sanctuary, Vault 111, Red Rocket)")
    ap.add_argument("--tile", type=int, default=14, help="cells per tile side (14 = the largest vanilla unique overlay); "
                                                         "a tile at least as large as the region gives one overlay")
    ap.add_argument("--pad", choices=("centre", "sw"), default="centre")
    ap.add_argument("--prefix", default="FO4CW3", help="EditorID prefix of the worlds (FO4CW3_T00, ...)")
    ap.add_argument("--plugin", default="FO4TerrainExp3.esm")
    ap.add_argument("--mars-plugin", default="FO4TerrainExp3_Mars.esm")
    ap.add_argument("--no-mars", action="store_true")
    ap.add_argument("--experiment", default="terrain_exp3")
    ap.add_argument("--alignment", choices=("relative", "absolute"), default="absolute")
    ap.add_argument("--hnam", type=int, default=0)
    ap.add_argument("--radius-km", type=float, default=og.MARS_RADIUS_KM)
    ap.add_argument("--ref-lat", type=float, default=og.WORLD01_LATLON[0], help="reference registration latitude (rad)")
    ap.add_argument("--ref-lon", type=float, default=og.WORLD01_LATLON[1], help="reference registration longitude (rad)")
    ap.add_argument("--ref-offset", type=int, nargs=2, default=list(og.WORLD01_OFFSET),
                    help="measured planet cell of the reference overlay's local origin")
    ap.add_argument("--centre-cell", type=int, nargs=2, default=[0, 0], help="planet cell for the region's centre")
    ap.add_argument("--mask-writer", choices=("texconv", "builtin"), default="texconv")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--no-plugins", action="store_true", help="check: skip the plugin record walk (before dotnet ran)")
    a = ap.parse_args()
    if a.cmd == "build":
        if not (a.fo4 or a.fo4_npz):
            sys.exit("--fo4 or --fo4-npz is required for build")
        os.makedirs(a.out, exist_ok=True)
        return build(a)
    return check(a)


if __name__ == "__main__":
    sys.exit(main())
