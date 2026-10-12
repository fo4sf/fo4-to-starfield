"""core64c: every Fallout 4 exterior object of the 64 x 64-cell core on the core64 terrain (docs/terrain/core64c.md).

    dotnet run --project dotnet/Fo4Land -c Release -- <Fallout4.esm> export-exterior Commonwealth -55 <y0> 54 <y0+9> <work>/export/band_<y0>_<y0+9>.json
           (11 bands, y0 = -55, -45, ..., 45: one band at a time keeps the exporter's memory small)
    python scripts/terrain/make_core64c.py select  --work <work> --core <terrain_core64>
    python scripts/terrain/make_core64c.py measure --work <work> --fo4-data <FO4 Data>
    python scripts/convert_batch.py --cell-json <work>/convert_input.json --staging <work>/convert --prefix fo4core
           --max-texture <cap> --types <printed by select> --limit 1000000 --resume  + the usual converter arguments
    python scripts/terrain/make_core64c.py stage --work <work> --core <terrain_core64> --out <terrain_core64c> --sf-esm <Starfield.esm>
    python scripts/terrain/make_core64c.py check --work <work> --core <terrain_core64> --out <terrain_core64c>
           [--fo4 <Fallout4.esm>] [--fo4-data <FO4 Data>] [--sf-data <Starfield Data>]

select   reads every export band, classifies every reference (exterior.select: convert, or skip with a reason, never
         silently) and writes selected.json (the references to place, slimmed to the fields placing needs),
         convert_input.json (one entry per model: all convert_batch needs) and selection.json (counts, skipped refs).
measure  before converting: models, materials and textures the converter would write (a dry run of its material
         logic over the FO4 archives' DDS headers: no texture is decoded), their size at full resolution and under
         texture caps, the mesh size (from the source NIF sizes) and the references per region; measure.json.
stage    places the converted references (exterior.place) in the core64 worldspace, hard-links the converted files
         into Data\\ (no second copy), copies core64's Data files (BTD, its meshes\\terrain copy, mask), writes
         objects.json and builds FO4TerrainCore.esm + FO4TerrainCore_Mars.esm with dotnet/TerrainOverlays (objects
         after every core64 record: core64's FormIDs do not move, the Mars plugin stays byte-identical), and plan.json:
         core64's probes within 500 m of the arrival re-judged with the objects, object tops at three familiar places
         and screenshot spots.
check    raw-walks the plugin (core64 records unchanged, REFRs per cell, bases, positions), object z - terrain z under
         every placed origin (BTD; with --fo4 also FO4's own LAND), every model / geometry / material / texture file,
         every plan point re-derived from the converted collision, archive size; offline_check.json.
Everything this writes stays outside the repo (derived game data).
"""
import argparse
import glob
import json
import math
import os
import shutil
import statistics
import struct
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "src"))
from fo4sf import btd, exterior  # noqa: E402
from fo4sf import terrain_grid as tg  # noqa: E402

sys.path.insert(0, HERE)
import make_exp2c as x2c  # noqa: E402
import overlay_records  # noqa: E402

EDID_PREFIX = "FO4Core_"
ASSET_PREFIX = "fo4core"
DATA_TREES = ("meshes", "geometries", "materials", "textures")
# fields of an exported reference that placing, reporting and the plan need (the export has about 25)
SLIM_KEYS = ("formkey", "type", "base_editor_id", "base_formkey", "model", "pos", "rot", "scale", "disabled",
             "persistent", "exterior_cell")
# Every large vanilla Starfield archive stops just below 4 GiB (Starfield - Textures02, Meshes01, Voices01, ...:
# 4,294,061,043 to 4,294,946,755 bytes, never more; read-only directory listing, 2026-10-11): Bethesda's own archives
# split at 2^32 bytes. Whether the engine reads an archive beyond 4 GiB is unresolved, so one archive stays below it.
ARCHIVE_LIMIT = 2 ** 32
ARCHIVE_BUDGET = int(3.8 * 2 ** 30)       # what the staged Data tree may hold (headroom for the archive's own tables)
REGION_CELLS = 16                         # report references per 16 x 16 Starfield cells (1.6 km)


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def save(path, value, indent=None):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=indent)
    os.replace(tmp, path)


def core_params(core):
    """(overlays_params.json, its single overlay) of the staged core64 terrain."""
    prm = load(os.path.join(core, "overlays_params.json"))
    if len(prm["overlays"]) != 1:
        sys.exit(f"{core}: core64c needs exactly one overlay, found {len(prm['overlays'])}")
    return prm, prm["overlays"][0]


def slim(ref):
    out = {k: ref.get(k) for k in SLIM_KEYS}
    out["enable_parent"] = ref.get("enable_parent")
    return out


def region_of(cell, size=REGION_CELLS):
    return int(math.floor(cell[0] / size)), int(math.floor(cell[1] / size))


# ------------------------------------------------------------------------------------------------------------- select
def select_bands(paths):
    """Every export band through exterior.select: (kept slim references, skipped entries, totals)."""
    kept, skipped = [], []
    tot = {"bands": 0, "cells": 0, "refs": 0, "deferred": 0}
    seen = set()
    for p in paths:
        export = load(p)
        tot["bands"] += 1
        tot["cells"] += len((export.get("exterior") or {}).get("cells") or [])
        tot["refs"] += len(export["refs"])
        tot["deferred"] += len(export.get("deferred_refs", []))
        sub, skip = exterior.select(export)
        for r in sub["refs"]:
            if r["formkey"] in seen:
                raise ValueError(f"{r['formkey']} exported twice (overlapping bands?)")
            seen.add(r["formkey"])
            kept.append(slim(r))
        skipped += skip
        del export, sub
    return kept, skipped, tot


def convert_list(kept):
    """One entry per model (convert_batch --cell-json reads only "model" and "type")."""
    by_model = {}
    for r in kept:
        by_model.setdefault(exterior.source_key(r["model"]), {"model": r["model"], "type": r["type"],
                                                               "formkey": r["formkey"]})
    return [by_model[k] for k in sorted(by_model)]


def cmd_select(a):
    t0 = time.time()
    paths = sorted(glob.glob(os.path.join(a.work, "export", "band_*.json")))
    if not paths:
        sys.exit(f"no export bands in {os.path.join(a.work, 'export')}")
    kept, skipped, tot = select_bands(paths)
    _prm, ov = core_params(a.core)
    cmin, cmax = ov["cell_min"], ov["cell_max"]
    regions, cells = {}, {}
    for r in kept:
        c = tg.sf_cell_of(r["pos"][0] / exterior.UNITS_PER_METRE, r["pos"][1] / exterior.UNITS_PER_METRE)
        cells[c] = cells.get(c, 0) + 1
        g = region_of(c)
        regions[g] = regions.get(g, 0) + 1
    models = convert_list(kept)
    save(os.path.join(a.work, "selected.json"), {"core": os.path.abspath(a.core), "refs": kept})
    save(os.path.join(a.work, "convert_input.json"), {"schema_version": 2, "cell": "core64c", "refs": models})
    rep = {"bands": [os.path.basename(p) for p in paths], **tot, "to_convert": len(kept), "models": len(models),
           "skipped": len(skipped), "skip_reasons": exterior.reason_counts(skipped),
           "skip_types": type_counts(skipped), "convert_types": list(exterior.CONVERT_TYPES),
           "sf_cells_with_refs": len(cells), "refs_per_sf_cell_max": max(cells.values()) if cells else 0,
           "densest_sf_cells": [[list(c), n] for c, n in sorted(cells.items(), key=lambda kv: -kv[1])[:10]],
           "outside_core_cells": sum(n for c, n in cells.items() if not (cmin <= c[0] <= cmax and cmin <= c[1] <= cmax)),
           "in_mask_ring": sum(n for c, n in cells.items() if cmin <= c[0] <= cmax and cmin <= c[1] <= cmax
                               and (c[0] in (cmin, cmax) or c[1] in (cmin, cmax))),
           "regions": {f"{g[0]},{g[1]}": n for g, n in sorted(regions.items())}, "region_cells": REGION_CELLS,
           "seconds": round(time.time() - t0, 1), "skipped_refs": skipped}
    save(os.path.join(a.work, "selection.json"), rep)
    print(f"{rep['refs']:,} references + {rep['deferred']:,} deferred in {rep['cells']:,} FO4 cells: convert "
          f"{rep['to_convert']:,} ({rep['models']:,} models), skip {rep['skipped']:,}: {rep['skip_reasons']}")
    print(f"Starfield cells with references {rep['sf_cells_with_refs']}, max {rep['refs_per_sf_cell_max']} per cell; "
          f"outside the core {rep['outside_core_cells']}, in the mask ring {rep['in_mask_ring']}; {rep['seconds']} s")
    print("convert_batch --types " + ",".join(exterior.CONVERT_TYPES))
    return 0


def type_counts(skipped):
    out = {}
    for s in skipped:
        k = f"{s['reason']}:{s.get('type')}"
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


# ------------------------------------------------------------------------------------------------------------ measure
BC_BYTES_PER_BLOCK = {"BC1": 8, "BC4": 8, "BC5": 16}


def bc_size(fmt, width, height, cap=0):
    """Bytes of a block-compressed DDS (DX10 header, 148 B) with texconv's full mip chain (floor(log2(max side)) + 1
    levels), top levels dropped until both sides are at most `cap` (0 = no cap), exactly as textures.cap_dds does."""
    w, h = max(1, int(width)), max(1, int(height))
    n = max(w, h).bit_length()
    drop = 0
    while cap and max(max(1, w >> drop), max(1, h >> drop)) > cap and drop < n - 1:
        drop += 1
    bb = BC_BYTES_PER_BLOCK[fmt]
    return 148 + sum(max(1, (max(1, w >> i) + 3) // 4) * max(1, (max(1, h >> i) + 3) // 4) * bb for i in range(drop, n))


class DryConverter:
    """The converter's material decisions (pipeline.Converter._shape_material: BGSM, blended decal, texture set,
    effect glass / grime decal, neutral) without converting anything: _convert_texture_set / _convert_glass record
    which outputs a material would get (format, source dimensions read from the archive's DX10 records)."""

    def __init__(self, src):
        from fo4sf import pipeline
        self.pipeline = pipeline
        conv = pipeline.Converter.__new__(pipeline.Converter)    # no texconv, no template, no neutral material
        conv.src, conv.prefix, conv._materials, conv._blend_cache = src, ASSET_PREFIX, {}, {}
        conv.stats = {"assets": 0, "failed": 0, "materials_ok": 0, "materials_fallback": 0}
        conv.material_errors = {}
        conv.neutral = "materials\\neutral.mat"
        conv._convert_texture_set = self._texture_set
        conv._convert_glass = self._glass
        self.conv, self.src = conv, src
        self.outputs = {}                                        # material stem -> [(kind, fmt, w, h)]
        self.mat_stem = {}                                       # material path the shapes get -> stem
        self.dims_cache = {}

    def dims(self, name):
        n = name.replace("\\", "/").lstrip("/")
        n = n if n.lower().startswith("textures/") else "textures/" + n
        if n.lower() not in self.dims_cache:
            got = None
            for a in self.src.textures:
                i = a.find(n)
                if i is not None:
                    e = a.entries[i]
                    got = (e.width, e.height)
                    break
            self.dims_cache[n.lower()] = got
        return self.dims_cache[n.lower()]

    def _texture_set(self, stem, diffuse, normal, spec, smoothness=1.0, spec_mult=1.0, alpha_test=False,
                     alpha_ref=128, decal=False):
        d = self.dims(diffuse)
        n = self.dims(normal) if normal else None
        s = self.dims(spec) if spec else None
        if d is None or (n is None and not decal):
            raise FileNotFoundError("diffuse or normal texture missing from archives")
        nd = n or (4, 4)
        out = [("color", "BC1", *d), ("normal", "BC5", *nd),
               ("rough", "BC4", *(s if s else (max(4, nd[0] // 4), max(4, nd[1] // 4))))]
        if alpha_test or decal:
            out.append(("opacity", "BC4", *d))                   # upper bound: only when the alpha really cuts out
        self.outputs[stem] = out
        return self._mat(stem)

    def _mat(self, stem):
        path = f"materials\\{ASSET_PREFIX}\\{stem}.mat"
        self.mat_stem[path] = stem
        return path

    def _glass(self, base, normal):
        d = self.dims(base) if base else None
        if d is None:
            raise FileNotFoundError("glass base texture missing")
        n = self.dims(normal) if normal else None
        stem = "glass/" + base.lower() + "|" + (normal or "").lower()
        self.outputs[stem] = [("color", "BC1", *d)] + ([("normal", "BC5", *n)] if n else []) + [("rough", "BC4", 16, 16)]
        return self._mat(stem)

    def model(self, name):
        """(ok, reason, materials used) for one model, by the converter's own shape and material logic."""
        from fo4sf import nif
        raw = self.src.mesh(name)
        if raw is None:
            return False, "not in the mesh archives", []
        try:
            src = nif.parse(raw)
            shapes = [s for s in nif.fo4_trishapes(src) if s.positions and s.triangles]
        except Exception as e:                                   # noqa: BLE001  (the converter fails it the same way)
            return False, f"{type(e).__name__}: {e}", []
        if not shapes:
            return False, "no static BSTriShape geometry", []
        mats = [self.conv._shape_material(src, s) for s in shapes]
        if all(m is None for m in mats):
            return False, "only effect-shader shapes", []
        return True, "", sorted({m for m in mats if m})


def mesh_entry_size(src, name):
    for a in src.meshes:
        i = a.find(name)
        if i is not None:
            return a.entries[i].unpacked or a.entries[i].packed
    return 0


def cmd_measure(a):
    from fo4sf import pipeline
    t0 = time.time()
    src = pipeline.Fo4Archives(a.fo4_data)
    models = load(os.path.join(a.work, "convert_input.json"))["refs"]
    sel = load(os.path.join(a.work, "selection.json"))
    dry = DryConverter(src)
    ok, failed, mats_of, nif_bytes = [], {}, {}, 0
    for k, m in enumerate(models):
        name = exterior.source_key(m["model"])
        good, why, mats = dry.model(name)
        if good:
            ok.append(name)
            mats_of[name] = mats
            nif_bytes += mesh_entry_size(src, name)
        else:
            failed[name] = why
        if (k + 1) % 2000 == 0:
            print(f"  {k + 1:,} / {len(models):,} models, {len(dry.outputs):,} texture sets, {time.time() - t0:.0f} s",
                  flush=True)
    caps = [int(c) for c in a.caps.split(",") if c.strip()]
    tex = {"materials": len(dry.outputs), "textures": sum(len(v) for v in dry.outputs.values()),
           "by_kind": {}, "full_bytes": 0, "capped_bytes": {str(c): 0 for c in caps}, "max_side": {}}
    for outs in dry.outputs.values():
        for kind, fmt, w, h in outs:
            full = bc_size(fmt, w, h)
            k = tex["by_kind"].setdefault(kind, {"count": 0, "full_bytes": 0})
            k["count"] += 1
            k["full_bytes"] += full
            tex["full_bytes"] += full
            side = str(max(w, h))
            tex["max_side"][side] = tex["max_side"].get(side, 0) + 1
            for c in caps:
                tex["capped_bytes"][str(c)] += bc_size(fmt, w, h, cap=c)
    tex["max_side"] = dict(sorted(tex["max_side"].items(), key=lambda kv: int(kv[0])))
    from fo4sf import textures as tx
    tex["kind_caps"] = {}
    for spec in (x for x in a.kind_caps.split(";") if x.strip()):
        kc = tx.parse_texture_caps(spec)
        tex["kind_caps"][spec] = sum(bc_size(f, w, h, cap=kc.get(k, 0)) for outs in dry.outputs.values()
                                     for k, f, w, h in outs)
    # mesh output size: converted .nif + .mesh bytes per source NIF byte, from a finished conversion (exp2c) if given
    ratio = None
    if a.calibrate and os.path.isfile(os.path.join(a.calibrate, "manifest.json")):
        man = load(os.path.join(a.calibrate, "manifest.json"))
        src_b = sum(mesh_entry_size(src, i["source"]) for i in man["items"])
        out_b = sum(os.path.getsize(os.path.join(r, f)) for t in ("meshes", "geometries")
                    for r, _d, fs in os.walk(os.path.join(a.calibrate, t)) for f in fs)
        ratio = out_b / src_b if src_b else None
    mesh_est = int(nif_bytes * ratio) if ratio else None
    # a split by region (REGION_CELLS x REGION_CELLS Starfield cells, each with its own archive) at full resolution:
    # every region archive needs the textures of every material its models use, so shared materials repeat
    mat_bytes = {st: sum(bc_size(f, w, h) for _k, f, w, h in outs) for st, outs in dry.outputs.items()}
    nif_size = {n: mesh_entry_size(src, n) for n in ok}
    regions = {}
    for r in load(os.path.join(a.work, "selected.json"))["refs"]:
        name = exterior.source_key(r["model"])
        if name not in mats_of:
            continue
        g = region_of(tg.sf_cell_of(r["pos"][0] / exterior.UNITS_PER_METRE, r["pos"][1] / exterior.UNITS_PER_METRE))
        regions.setdefault(g, {"refs": 0, "models": set()})
        regions[g]["refs"] += 1
        regions[g]["models"].add(name)
    split = {}
    for g, v in sorted(regions.items()):
        stems = {dry.mat_stem[m] for n in v["models"] for m in mats_of[n] if m in dry.mat_stem}
        tb = sum(mat_bytes[st] for st in stems)
        mb = int(sum(nif_size[n] for n in v["models"]) * (ratio or 0))
        split[f"{g[0]},{g[1]}"] = {"refs": v["refs"], "models": len(v["models"]), "materials": len(stems),
                                   "texture_bytes_full": tb, "mesh_bytes_estimate": mb, "archive_estimate": tb + mb}
    rep = {"region_split_full_resolution": {
               "region_cells": REGION_CELLS, "regions": split,
               "sum_bytes": sum(v["archive_estimate"] for v in split.values()),
               "largest_region_bytes": max(v["archive_estimate"] for v in split.values()),
               "regions_over_budget": sum(1 for v in split.values() if v["archive_estimate"] > ARCHIVE_BUDGET)},
           "references": sel["refs"] + sel["deferred"], "to_convert_refs": sel["to_convert"], "models": len(models),
           "models_converting": len(ok), "models_failing": len(failed), "failing": failed, "textures": tex,
           "source_nif_bytes": nif_bytes, "mesh_bytes_per_source_byte": ratio, "mesh_bytes_estimate": mesh_est,
           "archive_limit": ARCHIVE_LIMIT, "archive_budget": ARCHIVE_BUDGET,
           "seconds": round(time.time() - t0, 1)}
    rep["data_estimate"] = {"full": tex["full_bytes"] + (mesh_est or 0),
                            **{f"cap_{c}": tex["capped_bytes"][str(c)] + (mesh_est or 0) for c in caps}}
    fits = [c for c in caps if rep["data_estimate"][f"cap_{c}"] <= ARCHIVE_BUDGET]
    rep["largest_cap_within_budget"] = max(fits) if fits else None
    save(os.path.join(a.work, "measure.json"), rep, indent=1)
    gib = 2 ** 30
    print(f"{len(models):,} models: {len(ok):,} convert, {len(failed):,} fail; {tex['materials']:,} materials, "
          f"{tex['textures']:,} textures; {time.time() - t0:.0f} s")
    print(f"textures full resolution {tex['full_bytes'] / gib:.2f} GiB; " +
          ", ".join(f"cap {c}: {tex['capped_bytes'][str(c)] / gib:.2f} GiB" for c in caps))
    print(f"meshes: source {nif_bytes / gib:.2f} GiB, estimate {(mesh_est or 0) / gib:.2f} GiB (ratio {ratio})")
    print(f"largest cap within the {ARCHIVE_BUDGET / gib:.2f} GiB budget: {rep['largest_cap_within_budget']}")
    for spec, b in tex["kind_caps"].items():
        print(f"textures with {spec}: {b / gib:.2f} GiB; with meshes {(b + (mesh_est or 0)) / gib:.2f} GiB")
    rs = rep["region_split_full_resolution"]
    print(f"full resolution split into {len(rs['regions'])} regions of {REGION_CELLS} x {REGION_CELLS} cells: "
          f"{rs['sum_bytes'] / gib:.2f} GiB in all (one archive: {rep['data_estimate']['full'] / gib:.2f}), largest "
          f"{rs['largest_region_bytes'] / gib:.2f} GiB, {rs['regions_over_budget']} over the budget")
    return 0


# ------------------------------------------------------------------------------------------------------------ terrain
class Terrain:
    """The core64 BTD (raw u16 heights), decoded with the formula and edge clamping of make_cw_overlays.decode_at and
    tg.point_interp; the local frame is the CW frame (core64's origin is CW (0, 0): position = FO4 position / 70)."""

    def __init__(self, path):
        t = btd.read(overlay_records.read_bytes(path))
        self.raw, self.hmin, self.hmax, self.n = t.heights_raw, t.hmin, t.hmax, t.ncx
        self.step = (self.hmax - self.hmin) / 65535.0
        self.origin = tg.grid_origin(self.n)

    def window(self, x0, y0, x1, y1):
        """(heights in metres, origin x, origin y) of the samples covering [x0, x1] x [y0, y1] (plus one sample)."""
        last = self.raw.shape[0] - 1
        c0 = min(max(int(math.floor((x0 - self.origin) / tg.SF_STEP_M)) - 1, 0), last)
        c1 = min(max(int(math.ceil((x1 - self.origin) / tg.SF_STEP_M)) + 1, 0), last)
        r0 = min(max(int(math.floor((y0 - self.origin) / tg.SF_STEP_M)) - 1, 0), last)
        r1 = min(max(int(math.ceil((y1 - self.origin) / tg.SF_STEP_M)) + 1, 0), last)
        win = self.hmin + self.raw[r0:r1 + 1, c0:c1 + 1].astype(np.float64) / 65535.0 * (self.hmax - self.hmin)
        return win, self.origin + c0 * tg.SF_STEP_M, self.origin + r0 * tg.SF_STEP_M

    def bilinear(self, xs, ys):
        """Bilinear height at many points at once (tg.point_interp's "bilinear" rule and clamping)."""
        xs, ys = np.asarray(xs, np.float64), np.asarray(ys, np.float64)
        rows, cols = self.raw.shape
        u = np.clip((xs - self.origin) / tg.SF_STEP_M, 0.0, cols - 1.0)
        v = np.clip((ys - self.origin) / tg.SF_STEP_M, 0.0, rows - 1.0)
        c = np.minimum(u.astype(np.int64), cols - 2)
        r = np.minimum(v.astype(np.int64), rows - 2)
        fu, fv = u - c, v - r
        h = lambda rr, cc: self.hmin + self.raw[rr, cc].astype(np.float64) / 65535.0 * (self.hmax - self.hmin)  # noqa: E731
        return (h(r, c) * (1 - fu) * (1 - fv) + h(r, c + 1) * fu * (1 - fv) + h(r + 1, c) * (1 - fu) * fv
                + h(r + 1, c + 1) * fu * fv)


class CoreWorld(x2c.World):
    """make_exp2c.World over a part of the core: the placed references whose origin lies in `area` (x0, y0, x1, y1),
    their converted collision, and a window of the core BTD around it. Indices k are into this local list."""

    def __init__(self, data_dir, bases, placed, terrain, area, margin=60.0):
        x0, y0, x1, y1 = area
        self.bases = bases
        self.placed = [p for p in placed if x0 - margin <= p["pos"][0] <= x1 + margin
                       and y0 - margin <= p["pos"][1] <= y1 + margin]
        self.model_tris, self.collision_errors = {}, {}
        from fo4sf import sfbodies
        for i in sorted({p["base"] for p in self.placed}):
            try:
                with open(os.path.join(data_dir, "meshes", bases[i]["model"]), "rb") as f:
                    bodies = sfbodies.nif_bodies(f.read())
                self.model_tris[i] = np.array([t for body in bodies for t in body["triangles"]],
                                              np.float64).reshape(-1, 3, 3)
            except (OSError, ValueError, struct.error) as e:
                self.collision_errors[bases[i]["model"]] = f"{type(e).__name__}: {e}"
        self.tris, self.owners = exterior.world_triangles(self.model_tris, self.placed)
        self.index = exterior.SurfaceIndex(self.tris, self.owners)
        self.heights, self.ox, self.oy = terrain.window(x0 - margin, y0 - margin, x1 + margin, y1 + margin)
        self.area = (x0, y0, x1, y1)
        self.step, self.hmin, self.n = terrain.step, terrain.hmin, terrain.n
        self.by_src = {p["src"]: k for k, p in enumerate(self.placed)}

    def ground(self, x, y):
        return tg.point_interp(self.heights, self.ox, self.oy, tg.SF_STEP_M, x, y)["bilinear"]

    def ground_all(self, x, y):
        return tg.point_interp(self.heights, self.ox, self.oy, tg.SF_STEP_M, x, y)

    def segment_blocked(self, p0, p1, ignore=(), step=2.0):
        """Does the segment p0 -> p1 (x, y, z) cross a collision triangle of a placed object not in `ignore`, or run
        under the terrain? (Line of sight for a screenshot spot.)"""
        p0, p1 = np.asarray(p0, np.float64), np.asarray(p1, np.float64)
        d = p1 - p0
        n = max(2, int(math.hypot(d[0], d[1]) / step) + 1)
        for t in np.linspace(0.0, 1.0, n):
            q = p0 + t * d
            if self.ground(q[0], q[1]) > q[2]:
                return True
        idx = np.unique(np.concatenate([self.index.near(*(p0 + t * d)[:2], step) for t in np.linspace(0.0, 1.0, n)]))
        if not len(idx):
            return False
        if ignore:
            idx = idx[~np.isin(self.owners[idx], list(ignore))]
        tri = self.tris[idx]
        e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
        h = np.cross(d, e2)
        det = (e1 * h).sum(axis=1)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        s = p0 - tri[:, 0]
        u = (s * h).sum(axis=1) * inv
        q = np.cross(s, e1)
        v = (q * d).sum(axis=1) * inv
        t = (q * e2).sum(axis=1) * inv
        return bool((ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-6) & (t < 1 - 1e-6)).any())


# ---------------------------------------------------------------------------------------------------------------- plan
NEAR_M = 510.0              # core64 probes this close to the arrival (exact in the core64 run, 2026-10-11)
AREA_M = 560.0              # local collision world: arrival +- this (every point and every teleport position)
DROP_MARGIN = 40.0          # drop at least this far above the highest expected landing of the entry (as core64)
TOP_CLEAR = 10.0            # and at least this far above every collision top within 1 m of a point
REF_LABEL = x2c.REF_LABEL
SHOP = "1B5F12:Fallout4.esm"            # RedRExt_Workshop02: Red Rocket shop floor and roof (exp2c)
STATION = "0211C0:Fallout4.esm"         # RedRExt_Workshop01: the station (rocket tower, canopy)
HOUSE_ROOF = "01DAAC:Fallout4.esm"      # Res01PlayerHouseRoofRR: the player's house in Sanctuary, its roof
MUSEUM = "01CC81:Fallout4.esm"          # ConcordMuseumBLD (ConcordMuseum01.nif): Museum of Freedom, Concord
# familiar object tops (judged: each >= x2c.MIN_DISCRIMINATION above the terrain under it) and screenshot spots
# (terrain south of the landmark: the runner faces north, heading 0, at every point and takes a screenshot there)
TOPS = (("redrocket_roof", SHOP), ("sanctuary_house_roof", HOUSE_ROOF), ("concord_museum_roof", MUSEUM))
VIEWS = (("view_redrocket", (STATION, SHOP)), ("view_sanctuary_house", (HOUSE_ROOF,)), ("view_concord_museum", (MUSEUM,)))
ROOF_FLAT_TOL = (0.02, 0.1, 0.25)       # level first; a low-pitched roof only if no level part is found
RUNNER_KEYS = x2c.RUNNER_KEYS
ENTRY_OWN = ("label", "points", "drop_z", "z_ref", "spawn_local", "settle_ms")
ROLES = ("terrain within 500 m", "familiar object tops", "informational")


def object_top(world, k, label, drop_z, tols=ROOF_FLAT_TOL):
    """The landing point on placed object k with the most level neighbourhood (exterior.pick_points), level first,
    then up to the next flat tolerance (a pitched roof). Returns a plan point dict or None."""
    for tol in tols:
        picks = exterior.pick_points(world.index, world.ground, k, world.bounds(k), drop_z, count=1, flat_tol=tol)
        if picks:
            x, y, land, free = picks[0]
            return {"label": label, "x": round(x, 4), "y": round(y, 4), "kind": "object_top",
                    "expect": round(land["centre"], 4), "landing": x2c.landing_json(world, land),
                    "above_terrain": round(land["centre"] - land["ground"], 4), "flat_tol": tol,
                    "discrimination": round(x2c.discrimination(world, x, y, land["centre"]), 4),
                    "owner": world.describe(k)}
    return None


def view_spot(world, label, owners, drop_z, dmin=20.0, dmax=90.0):
    """Open terrain south of a landmark (the runner faces north at every point) from where the landmark's middle is
    in sight: the nearest candidate (2 m grid, at most 25 degrees off north) that x2c.reference_ok accepts (level,
    nothing above the terrain within 1 m) and whose line of sight from eye height (1.7 m) is not blocked."""
    ks = [world.by_src[o] for o in owners]
    if not all((world.owners == k).any() for k in ks):
        return None                                      # disabled or without collision: no target to look at
    b = [world.bounds(k) for k in ks]
    cx = (min(v[0] for v in b) + max(v[2] for v in b)) / 2
    cy = (min(v[1] for v in b) + max(v[3] for v in b)) / 2
    y_south = min(v[1] for v in b)
    zs = world.tris[np.isin(world.owners, ks)][:, :, 2]
    target = (cx, cy, float(zs.min() + zs.max()) / 2)
    cands = []
    for d in np.arange(dmin, dmax + 1e-9, 2.0):
        for dx in np.arange(-d * 0.45, d * 0.45 + 1e-9, 2.0):
            x, y = cx + dx, y_south - d
            cands.append((math.hypot(dx, cy - y), round(x, 4), round(y, 4)))
    for _, x, y in sorted(cands):
        g = x2c.reference_ok(world, x, y, clear=1.0)
        if g is None:
            continue
        if world.segment_blocked((x, y, g + 1.7), target, ignore=set(ks)):
            continue
        land = world.landing(x, y, drop_z)
        return {"label": label, "x": x, "y": y, "kind": "view", "expect": round(g, 4), "terrain_expect": round(g, 4),
                "landing": x2c.landing_json(world, land), "target": [round(v, 3) for v in target],
                "distance_to_target_m": round(math.hypot(target[0] - x, target[1] - y), 1),
                "owner": world.describe(ks[0])}
    return None


def leg_cost(world, a, b, drop_z, capsule=x2c.CAPSULE):
    return sum(x2c.position_cost(exterior.capsule_hits(world.index, world.ground, x, y, z, radius=capsule[0],
                                                       height=capsule[1]))
               for x, y, z in exterior.setpos_path(a, (b["x"], b["y"]), drop_z))


def path_key(start, seq):
    """(longest jump, total distance) of visiting seq [(x, y)] from start: what order_entry minimises."""
    ln, here = [], start
    for q in seq:
        ln.append(math.hypot(q[0] - here[0], q[1] - here[1]))
        here = q
    return round(max(ln), 3), round(sum(ln), 3)


def spoke_order(start, points, sector_deg=45.0):
    """Points near the arrival (< 100 m) first, then by bearing sector around the arrival, outward in one sector and
    inward in the next (a zig-zag over the spokes), so no jump crosses the arrival or skips a sector at 500 m."""
    def bearing(p):
        return math.degrees(math.atan2(p["y"] - start[1], p["x"] - start[0])) % 360.0

    def dist(p):
        return math.hypot(p["x"] - start[0], p["y"] - start[1])
    near = sorted((p for p in points if dist(p) < 100), key=lambda p: (dist(p), p["label"]))
    far = [p for p in points if dist(p) >= 100]
    sectors = {}
    for p in far:
        sectors.setdefault(int(bearing(p) // sector_deg), []).append(p)
    out = list(near)
    for n, s in enumerate(sorted(sectors)):
        out += sorted(sectors[s], key=lambda p: (dist(p), p["label"]), reverse=bool(n % 2))
    return out


def two_opt(start, order):
    """Reverse sub-sequences while that lowers (longest jump, total distance) from start (the arrival)."""
    order = list(order)
    best = path_key(start, [(p["x"], p["y"]) for p in order])
    improved = True
    while improved:
        improved = False
        for i in range(len(order) - 1):
            for j in range(i + 1, len(order)):
                cand = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                k = path_key(start, [(p["x"], p["y"]) for p in cand])
                if k < best:
                    order, best, improved = cand, k, True
    return order


def order_entry(world, start, points, drop_z, exhaustive=6):
    """Visiting order: up to `exhaustive` points every order, by (teleport positions overlapping collision, longest
    jump, total distance); more points by a spoke zig-zag around the arrival improved by 2-opt on (longest jump, total
    distance). Short jumps matter: the core64 run read every probe within 500 m of the arrival exactly, while single
    1 to 2 km jumps hung at the drop height (2026-10-11)."""
    import itertools
    if len(points) <= exhaustive:
        nodes = [tuple(start)] + [(p["x"], p["y"], p["expect"]) for p in points]
        cost = {(i, j): leg_cost(world, nodes[i], points[j], drop_z) for i in range(len(points) + 1)
                for j in range(len(points)) if i != j + 1}

        def key(perm):
            legs = [(0, perm[0])] + [(perm[k] + 1, perm[k + 1]) for k in range(len(perm) - 1)]
            ln = [math.hypot(nodes[i][0] - points[j]["x"], nodes[i][1] - points[j]["y"]) for i, j in legs]
            return sum(cost[leg] for leg in legs), round(max(ln), 1), round(sum(ln), 1), perm
        best = min(itertools.permutations(range(len(points))), key=key)
        return [points[k] for k in best]
    return two_opt(start[:2], spoke_order(start, points))


def entry_drop(world, points):
    """Drop height of an entry: DROP_MARGIN above its highest expected landing and TOP_CLEAR above every collision
    top within 1 m of any of its points, rounded up to 5 m."""
    top = max(p["expect"] for p in points) + DROP_MARGIN
    for p in points:
        for dx, dy in exterior.disc_offsets(1.0):
            s = world.index.surfaces(p["x"] + dx, p["y"] + dy)
            if s:
                top = max(top, s[0][0] + TOP_CLEAR)
    return float(math.ceil(top / 5.0) * 5.0)


def settle_for(drop, lowest):
    import make_cw_overlays as cwo
    return cwo.settle_ms(drop, lowest)


def plan_entry(base, label, drop_z, points, z_ref, spawn_local, settle_ms):
    """One runner entry: every key of core64's entry `base` except the ones core64c sets (ENTRY_OWN), then its own."""
    e = {k: v for k, v in base.items() if k not in ENTRY_OWN}
    e.update(label=label, spawn_local=spawn_local, z_ref=z_ref, drop_z=drop_z, settle_ms=settle_ms,
             points=[{k: p[k] for k in x2c.POINT_KEYS} for p in points])
    return e


def validate_plan(plan, base, kinds):
    """Problems of the entries against the runner's keys and core64's entry (x2c.validate_plan's rules with this
    experiment's own keys): unknown keys, a base key not carried, z_ref not this entry's terrain reference, duplicate
    labels, point keys."""
    problems = []
    for i, e in enumerate(plan):
        tag = f"entry {i + 1}"
        problems += [f"{tag}: key {k!r} is not read by the runner" for k in e if k not in RUNNER_KEYS]
        problems += [f"{tag}: core64 key {k!r} not carried" for k, v in base.items() if k not in ENTRY_OWN and e.get(k) != v]
        labels = [p["label"] for p in e.get("points", [])]
        if len(set(labels)) != len(labels):
            problems.append(f"{tag}: duplicate point labels")
        if e.get("z_ref") not in labels or kinds.get((i, e.get("z_ref"))) != "terrain_ref":
            problems.append(f"{tag}: z_ref {e.get('z_ref')!r} is not its terrain reference point")
        problems += [f"{tag}: point {p.get('label')} keys {sorted(p)}" for p in e.get("points", [])
                     if tuple(sorted(p)) != tuple(sorted(x2c.POINT_KEYS))]
    return problems


def scenario_reads(world, entry, meta, scenario):
    """x2c.scenario_reads with this plan's kinds: terrain points (terrain, terrain_ref, terrain_near_object, view)
    read the terrain without objects; object points then land on the highest terrain sample under their disc."""
    reads = []
    for p in entry["points"]:
        on_terrain = meta[p["label"]]["kind"] in ("terrain", "terrain_ref", "terrain_near_object", "view")
        if scenario == "no_objects":
            reads.append(p["expect"] if on_terrain else
                         max(world.ground(p["x"] + dx, p["y"] + dy) for dx, dy in exterior.disc_offsets(0.6)))
        elif scenario == "flat_terrain":
            reads.append(world.hmin if on_terrain else p["expect"])
        else:
            raise ValueError(scenario)
    return reads


SCENARIOS = (("no_objects", "flat_terrain"), ("no_objects",), ("no_objects",))


def build_plan(world, ov, base, core_exp):
    """Three entries, each ONE coc arrival at core64's COC marker, heights judged against the terrain reference
    zref_ground read in the same test (z_ref):
    1 terrain within 500 m  core64's probes within NEAR_M of the arrival that stay clear of objects (exact in core64)
    2 object tops           Red Rocket shop roof, the Sanctuary player house roof, the Concord museum roof (each at
                            least x2c.MIN_DISCRIMINATION above the terrain: without the objects the entry fails)
    3 informational         core64 probes now on or near an object, and screenshot spots south of the three places
    Returns (plan, expected-json part)."""
    sx, sy, sz = ov["spawn"]
    land_spawn = world.landing(sx, sy, sz)
    start = (sx, sy, land_spawn["centre"])
    spawn_local = [sx, sy, round(land_spawn["centre"], 4)]
    ref = x2c.reference_point(world, (sx, sy))
    if ref is None:
        sys.exit(f"no open level terrain within {x2c.REF_SEARCH} m of the arrival for {REF_LABEL}")

    near, seen = [], set()
    for e in core_exp["entries"]:
        for p in e["points"]:
            if p["from_arrival_m"] <= NEAR_M and p["label"] not in seen:
                seen.add(p["label"])
                near.append({"label": p["label"], "x": p["x_cw"], "y": p["y_cw"], "expect": p["expect"],
                             "core64": {"kind": p["kind"], "from_arrival_m": p["from_arrival_m"]}})
    terr = x2c.terrain_points(world, near, 300.0)
    for t, p in zip(terr, near):
        t["core64"] = p["core64"]
    judged_terrain = [p for p in terr if p["kind"] == "terrain"]
    info = [p for p in terr if p["kind"] != "terrain"]

    tops, missing = [], []
    for label, src in TOPS:
        k = world.by_src.get(src)
        if k is not None and not (world.owners == k).any():
            k = None                                     # disabled or without collision
        p = object_top(world, k, label, 300.0) if k is not None else None
        if p is None or p["discrimination"] < x2c.MIN_DISCRIMINATION:
            missing.append({"label": label, "src": src, "reason": "not placed or no collision" if k is None else
                            "no landing point" if p is None else f"only {p['discrimination']} m above the terrain"})
            if p is not None:
                info.append(p)
            continue
        p["object_class"] = x2c.object_class(p["discrimination"])
        tops.append(p)
    if not tops:
        sys.exit(f"no familiar object top: {missing}")
    views = []
    for label, owners in VIEWS:
        if all(o in world.by_src for o in owners):
            v = view_spot(world, label, owners, 300.0)
            if v is not None:
                views.append(v)
                continue
        missing.append({"label": label, "src": owners[0], "reason": "no open terrain with a clear view south of it"})
    info += views

    groups, plan, kinds = [], [], {}
    labels = [f"terrain_core64c 1/3 (terrain within {NEAR_M:.0f} m): core64's probes near the arrival that stay clear "
              f"of objects, relative to {REF_LABEL} (a flat or missing BTD fails)",
              f"terrain_core64c 2/3 (familiar object tops): Red Rocket shop roof, Sanctuary player house roof, Concord "
              f"museum roof, >= {x2c.MIN_DISCRIMINATION} m above the terrain, relative to {REF_LABEL} (fails if the "
              f"objects are missing)",
              "terrain_core64c 3/3 (informational): core64 probes now on or near objects, and screenshot spots facing "
              "north at Red Rocket, the Sanctuary house and the Concord museum"]
    for i, pts in enumerate((judged_terrain, tops, info)):
        pts = [ref] + pts
        drop = entry_drop(world, pts)
        order = order_entry(world, start, pts, drop)
        groups.append(order)
        settle = settle_for(drop, min(p["expect"] for p in order))
        plan.append(plan_entry(base, labels[i], drop, order, REF_LABEL, spawn_local, settle))
        kinds.update({(i, p["label"]): p["kind"] for p in order})
    problems = validate_plan(plan, base, kinds)
    if problems:
        sys.exit("plan: " + "; ".join(problems))
    entries = []
    for i, (e, g) in enumerate(zip(plan, groups)):
        meta = {p["label"]: p for p in g}
        pred = {}
        for sc in SCENARIOS[i]:
            v, worst, _ = x2c.judge_heights(e["points"], scenario_reads(world, e, meta, sc), e["z_ref"])
            pred[sc] = {"verdict": v, "worst_m": round(worst, 3)}
        paths, clear = x2c.path_report(world, start, e["points"], e["drop_z"])
        here, legs = start[:2], []
        for p in e["points"]:
            legs.append(round(math.hypot(p["x"] - here[0], p["y"] - here[1]), 1))
            here = (p["x"], p["y"])
        entries.append({"label": e["label"], "role": ROLES[i], "drop_z": e["drop_z"], "settle_ms": e["settle_ms"],
                        "z_ref": e["z_ref"], "predicted": pred, "teleports_clear": clear, "legs_m": legs,
                        "longest_leg_m": max(legs), "teleport_positions_on_objects": sum(
                            1 for t in paths for pos in t["positions"] if any(h != "terrain" for h in pos[3])),
                        "teleports": paths})
    return plan, {"spawn": {"marker": ov["spawn"], "landing": x2c.landing_json(world, land_spawn),
                            "spawn_local": spawn_local, "core64_spawn_local": base["spawn_local"]},
                  "reference": ref, "entries": entries, "missing": missing,
                  "points": [dict(p, entry=i) for i, g in enumerate(groups) for p in g]}


# --------------------------------------------------------------------------------------------------------------- stage
def link_tree(src, dst):
    """Hard-link every file of src into dst (same volume: no second copy of the converted files), copying when a link
    is not possible; a file already linked to the same source is kept. Returns (linked, copied, kept)."""
    linked = copied = kept = 0
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        os.makedirs(os.path.join(dst, rel), exist_ok=True)
        for fn in files:
            s, d = os.path.join(root, fn), os.path.join(dst, rel, fn)
            if os.path.exists(d):
                if os.path.samefile(s, d):
                    kept += 1
                    continue
                os.remove(d)
            try:
                os.link(s, d)
                linked += 1
            except OSError:
                shutil.copy2(s, d)
                copied += 1
    return linked, copied, kept


def data_files(out):
    """[(path relative to Data with '/', bytes)] of the staged Data tree, sorted."""
    data = os.path.join(out, "Data")
    files = []
    for root, _dirs, names in os.walk(data):
        for fn in names:
            p = os.path.join(root, fn)
            files.append((os.path.relpath(p, data).replace(os.sep, "/"), os.path.getsize(p)))
    return sorted(files)


def ba2_size(files):
    """Size of a General BA2 holding `files` stored (no compression), as Archive2 writes it: 24-byte header (+ 8 in
    v2/v3), a 36-byte record per file, the data, then the name table (u16 length + name). An estimate within the
    header variant; the dry run in check measures the real one."""
    return 32 + sum(36 + b + 2 + len(n) for n, b in files)


def terrain_edids(prm):
    out = set()
    for o in prm["overlays"]:
        out |= {o["world"], o["block"], o["location"], o["anchor"]["edid"], o["coc"], o["coc"] + "Marker"}
    return {e.lower() for e in out}


def place_all(a, ov):
    sel = load(os.path.join(a.work, "selected.json"))
    man = load(os.path.join(a.work, "convert", "manifest.json"))
    bases, placed, skipped_conv = exterior.place(sel, man, ov["cell_min"], ov["cell_max"], EDID_PREFIX)
    items = {i["source"].replace("/", "\\").lower(): i for i in man["items"]}
    for b in bases:
        b["collision"] = x2c.collision_kind(items[b["key"]])
    return bases, placed, skipped_conv, man


def cmd_stage(a):
    t0 = time.time()
    prm, ov = core_params(a.core)
    core_plan = load(os.path.join(a.core, "plan.json"))
    core_exp = load(os.path.join(a.core, "expected.json"))
    selrep = load(os.path.join(a.work, "selection.json"))
    bases, placed, skipped_conv, man = place_all(a, ov)
    skipped = selrep["skipped_refs"] + skipped_conv
    total = selrep["refs"] + selrep["deferred"]
    if len(placed) + len(skipped) != total:
        sys.exit(f"accounting: {len(placed)} placed + {len(skipped)} skipped != {total} exported")
    clash = sorted({b["edid"].lower() for b in bases} & terrain_edids(prm))
    if clash:
        sys.exit(f"base EditorIDs clash with core64's records: {clash}")
    print(f"{len(bases):,} bases, {len(placed):,} references placed, {len(skipped):,} skipped "
          f"({exterior.reason_counts(skipped)}); {time.time() - t0:.0f} s")

    out = a.out
    os.makedirs(out, exist_ok=True)
    base_files = x2c.copy_base_data(a.core, out)                       # BTD, its meshes\terrain copy, mask
    for tree in DATA_TREES:
        ln, cp, kp = link_tree(os.path.join(a.work, "convert", tree), os.path.join(out, "Data", tree))
        print(f"Data\\{tree}: {ln} linked, {cp} copied, {kp} kept")
    files = data_files(out)
    data_bytes = sum(b for _, b in files)
    archive = ba2_size(files)
    print(f"Data tree: {len(files):,} files, {data_bytes / 2 ** 30:.3f} GiB; one stored archive about "
          f"{archive / 2 ** 30:.3f} GiB (limit {ARCHIVE_LIMIT / 2 ** 30:.0f} GiB, budget {ARCHIVE_BUDGET / 2 ** 30:.2f})")
    if archive > ARCHIVE_BUDGET:
        sys.exit("the Data tree does not fit one archive below 4 GiB: lower convert_batch --max-texture, or split it "
                 "into region plugins with their own archives (docs/terrain/core64c.md)")

    objects = {"world": ov["world"], "edid_prefix": EDID_PREFIX,
               "bases": [{k: b[k] for k in ("edid", "model", "door", "source", "collision") if k in b} for b in bases],
               "refs": [{k: p[k] for k in ("src", "base", "cell", "pos", "rot", "scale", "disabled")} for p in placed]}
    save(os.path.join(out, "objects.json"), objects)
    save(os.path.join(out, "overlays_params.json"), dict(prm, objects="objects.json"), indent=1)
    save(os.path.join(out, "skipped.json"), {"counts": exterior.reason_counts(skipped), "types": type_counts(skipped),
                                             "refs": skipped})
    for name in ("preview.png",):
        if os.path.isfile(os.path.join(a.core, name)):
            shutil.copy2(os.path.join(a.core, name), os.path.join(out, name))

    t1 = time.time()
    if a.sf_esm:
        subprocess.run(["dotnet", "run", "--project", os.path.join(REPO, "dotnet", "TerrainOverlays"), "-c", "Release",
                        "--", a.sf_esm, out], check=True)
    plugin_s = round(time.time() - t1, 1)

    t2 = time.time()
    terrain = Terrain(os.path.join(out, *ov["btd_file"].split("/")))
    sx, sy = ov["spawn"][:2]
    area = (sx - AREA_M, sy - AREA_M, sx + AREA_M, sy + AREA_M)
    world = CoreWorld(os.path.join(out, "Data"), bases, placed, terrain, area)
    if world.collision_errors:
        sys.exit(f"converted collision unreadable: {world.collision_errors}")
    print(f"local world: {len(world.placed):,} references, {len(world.model_tris):,} models, {len(world.tris):,} "
          f"collision triangles ({time.time() - t2:.0f} s)")
    plan, exp = build_plan(world, ov, core_plan[0], core_exp)
    save(os.path.join(out, "plan.json"), plan, indent=1)
    ids = load(os.path.join(out, "formids.json")) if os.path.exists(os.path.join(out, "formids.json")) else None
    lb = prm.get("anchor_load_byte", overlay_records.ANCHOR_LOAD_BYTE)
    for p in exp["points"]:
        for o in (p.get("owner"), (p.get("nearby_object") or {}).get("owner")):
            if o and ids:
                o["refr"] = lb + ids["refs"][o["src"]]
    tex = dict(man["stats"].get("textures") or {})
    log_path = os.path.join(a.work, "convert", "texture_log.json")
    if os.path.isfile(log_path):
        log = load(log_path)
        caps = {}
        for v in log.values():
            caps[v["kind"]] = v["cap"]
        tex.update(caps=caps, by_kind={k: {"textures": sum(1 for v in log.values() if v["kind"] == k),
                                           "full_bytes": sum(v["bytes"] for v in log.values() if v["kind"] == k),
                                           "written_bytes": sum(v["out_bytes"] for v in log.values() if v["kind"] == k)}
                                       for k in sorted(caps)})
    expected = {
        "experiment": "terrain_core64c", "core": os.path.abspath(a.core), "base_files": base_files,
        "hypothesis": "FO4 position / 70 = core64 position in metres for terrain and objects alike (core64's origin is "
                      "CW (0, 0)); an object's collision then sits on the BTD as in FO4",
        "objects": {"exported": total, "placed": len(placed), "bases": len(bases),
                    "doors": sum(1 for b in bases if "door" in b),
                    "initially_disabled": sum(p["disabled"] for p in placed),
                    "fo4_persistent_placed_temporary": sum(p["fo4_persistent"] for p in placed),
                    "enable_parent_not_translated": sum(p["enable_parent"] for p in placed),
                    "collision": {k: sum(1 for p in placed if bases[p["base"]]["collision"] == k)
                                  for k in sorted({b["collision"] for b in bases})},
                    "skipped": exterior.reason_counts(skipped)},
        "data": {"files": len(files), "bytes": data_bytes, "archive_estimate": archive,
                 "archive_limit": ARCHIVE_LIMIT, "textures": tex,
                 "texture_caps": ",".join(f"{k}={v}" for k, v in sorted((tex.get("caps") or {}).items())) or "none"},
        "times_s": {"stage_place": round(t1 - t0, 1), "plugin": plugin_s, "plan": round(time.time() - t2, 1)},
        **exp}
    save(os.path.join(out, "expected.json"), expected, indent=1)
    readme(out, prm, ov, plan, expected)
    for i, e in enumerate(plan):
        d = expected["entries"][i]
        print(f"entry {i + 1} ({d['role']}): {len(e['points'])} points from {e['drop_z']} m, settle {e['settle_ms']} ms, "
              f"predicted {d['predicted']}, longest leg {d['longest_leg_m']} m, teleports clear {d['teleports_clear']}")
    print(f"spawn_local {expected['spawn']['spawn_local']}; missing {expected['missing']}; {time.time() - t0:.0f} s")
    return 0


def readme(out, prm, ov, plan, exp):
    pl = [prm["plugin"], prm["mars"]["plugin"]]
    base = os.path.splitext(prm["plugin"])[0]
    o, d = exp["objects"], exp["data"]
    ref = exp["reference"]
    lines = [
        "Terrain core64c (Claude, 2026-10-11). NOT deployed, NOT queued. Recipe: docs/terrain/core64c.md",
        "(branch claude/terrain-core64-objects). Base: core64 (" + exp["core"] + "): the same BTD, mask, Location,",
        "Mars registration, anchor, COC marker and FormIDs, plus EVERY Fallout 4 exterior object of the 64 x 64-cell",
        f"core that converts: {o['placed']:,} references of {o['bases']:,} models (STAT, {o['doors']} rigged DOOR) at",
        f"FO4 position / 70 in {ov['world']}, in the same plugin after core64's records. Skipped and why: skipped.json",
        f"({', '.join(f'{k} {v:,}' for k, v in o['skipped'].items())}).",
        f"Data tree {d['files']:,} files, {d['bytes'] / 2 ** 30:.2f} GiB (textures capped {d['texture_caps']}),",
        f"one stored archive of about {d['archive_estimate'] / 2 ** 30:.2f} GiB (vanilla archives stop below 4 GiB).",
        "",
        "Install (game closed). The runner does it:",
        f"  scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> --plugins {','.join(pl)} --pack",
        f"  --pack builds \"{base} - Main.ba2\" from Data\\ (Archive2 -format=General -compression=None: every entry",
        "  stored, BTD included; textures load from the General archive, verified with exp2c on 2026-10-11).",
        f"Queue: testqueue.py plan-terrain --staging <build> --exp-dir <this folder> --out <queue> --plugins {','.join(pl)} --fresh",
        "Never install together with another terrain experiment (every Mars plugin overrides MarsPlanetData).",
        "",
        f"Plan: {len(plan)} entries, each ONE coc {plan[0]['coc']} arrival (fresh launch). spawn_local {plan[0]['spawn_local']}",
        f"= where the player lands under the COC marker {ov['spawn']}. Heights are judged relative to {REF_LABEL}",
        f"({ref['x']}, {ref['y']} -> {ref['expect']}: open level terrain {ref['distance_from_arrival']} m from the arrival,",
        f"nothing above it within {x2c.REF_CLEAR} m). The runner faces north at every point and takes a screenshot there.",
    ]
    meta = {(q["entry"], q["label"]): q for q in exp["points"]}
    for i, e in enumerate(plan):
        dd = exp["entries"][i]
        pr = dd["predicted"]
        lines += ["", f"  {e['label']}", f"  drop_z {e['drop_z']}, settle {e['settle_ms']} ms; predicted without the objects: "
                  f"{pr['no_objects']['verdict']} (worst {pr['no_objects']['worst_m']} m)" +
                  (f", on flat terrain: {pr['flat_terrain']['verdict']} (worst {pr['flat_terrain']['worst_m']} m)"
                   if "flat_terrain" in pr else "") + f"; longest jump {dd['longest_leg_m']} m"]
        for p in e["points"]:
            m = meta[(i, p["label"])]
            owner = (m.get("owner") or {}).get("edid", "")
            near = m.get("nearby_object") or {}
            what = {"terrain": "terrain (core64 probe)", "terrain_ref": "terrain, the Z reference",
                    "terrain_covered": "core64 probe now on " + owner,
                    "terrain_near_object": f"terrain, {owner} {near.get('height', 0):.2f} m high at {near.get('distance')} m",
                    "object_top": f"top of {owner}, {m.get('discrimination', 0):.2f} m above the terrain",
                    "view": f"screenshot spot, {m.get('distance_to_target_m')} m south of {owner}"}[m["kind"]]
            lines.append(f"    {p['label']:<30} x {p['x']:>10.4f}  y {p['y']:>10.4f}  -> {p['expect']:.4f}   {what}")
    lines += ["", "Files: " + ", ".join(pl) + ", Data\\ (core64's BTD, its meshes\\terrain copy and mask; converted meshes,",
              "geometries, materials, textures under fo4core\\), objects.json, formids.json, skipped.json, plan.json,",
              "expected.json, offline_check.json (make_core64c.py check). Uninstall: exp_install.py uninstall."]
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# --------------------------------------------------------------------------------------------------------------- check
def abs_stats(values):
    v = np.abs(np.asarray(values, np.float64))
    return {"count": int(v.size), "median_mm": round(float(np.median(v)) * 1000, 2),
            "p95_mm": round(float(np.percentile(v, 95)) * 1000, 2), "p99_mm": round(float(np.percentile(v, 99)) * 1000, 2),
            "max_mm": round(float(v.max()) * 1000, 2), "within_1cm": int((v <= 0.01).sum()),
            "within_5cm": int((v <= 0.05).sum())}


def archive_dry_run(archive2, out, scratch, files):
    """Build the archive exp_install.py --pack would build (Archive2 -format=General -compression=None, every top-level
    folder of Data) into `scratch`, read its header back and delete it: (report, problems)."""
    from fo4sf import ba2
    data = os.path.join(out, "Data")
    os.makedirs(scratch, exist_ok=True)
    path = os.path.join(scratch, "core64c_dry - Main.ba2")
    folders = sorted(d for d in os.listdir(data) if os.path.isdir(os.path.join(data, d)))
    t0 = time.time()
    r = subprocess.run([archive2, ",".join(folders), f"-create={path}", f"-root={data}", "-format=General",
                        "-compression=None"], cwd=data, capture_output=True, text=True)
    rep = {"seconds": round(time.time() - t0, 1), "returncode": r.returncode}
    problems = []
    try:
        if r.returncode != 0 or not os.path.isfile(path):
            return rep, [f"Archive2 failed: {(r.stdout or '')[-300:]} {(r.stderr or '')[-300:]}"]
        rep["bytes"] = os.path.getsize(path)
        arc = ba2.Ba2(path)
        rep["entries"] = len(arc.entries)
        rep["packed_entries"] = sum(1 for e in arc.entries if e.packed)
        names = {e.name.replace("\\", "/").lower() for e in arc.entries}
        want = {n.lower() for n, _ in files}
        rep["missing"] = sorted(want - names)[:20]
        rep["extra"] = sorted(names - want)[:20]
        if rep["packed_entries"]:
            problems.append(f"{rep['packed_entries']} entries packed")
        if names != want:
            problems.append("archive entries differ from the Data tree")
        return rep, problems
    finally:
        if os.path.exists(path):
            os.remove(path)


def cmd_check(a):
    import make_cw_overlays as cwo
    t0 = time.time()
    out = a.out
    prm, ov = core_params(out)
    cprm, _cov = core_params(a.core)
    plan = load(os.path.join(out, "plan.json"))
    exp = load(os.path.join(out, "expected.json"))
    objects = load(os.path.join(out, "objects.json"))
    ids = load(os.path.join(out, "formids.json"))
    checks, rep = [], {}

    def need(cond, what):
        checks.append([what, bool(cond)])

    # 1. core64 unchanged: params, Data files, Mars plugin, every core64 record of the main plugin
    need({k: v for k, v in prm.items() if k != "objects"} == cprm and prm.get("objects") == "objects.json",
         "overlays_params.json = core64's + objects")
    for rel in exp["base_files"] + [prm["mars"]["plugin"]]:
        need(os.path.isfile(os.path.join(a.core, *rel.split("/"))) and
             x2c.sha256(os.path.join(out, *rel.split("/"))) == x2c.sha256(os.path.join(a.core, *rel.split("/"))),
             f"{rel} byte-identical to core64")
    terrain = Terrain(os.path.join(out, *ov["btd_file"].split("/")))
    cwo.check_plugins(out, prm, {ov["tag"]: terrain.raw}, need, rep, overlay_records.vanilla_mars_count(a.sf_data))
    mk = cwo.mask_report(out, ov["world"], ov["n"], tuple(ov["mask_outer_edges"]))
    need(mk["pixels_differ"] == 0, f"mask exact ({mk['outer_edges']})")
    old = overlay_records.walk_plugin(os.path.join(a.core, prm["plugin"]))
    new = overlay_records.walk_plugin(os.path.join(out, prm["plugin"]))
    by = {r["fid"]: r for r in new["records"]}
    same = sum(1 for r in old["records"] if r["fid"] in by and by[r["fid"]]["sig"] == r["sig"]
               and by[r["fid"]]["flags"] == r["flags"] and by[r["fid"]]["fields"] == r["fields"])
    need(same == len(old["records"]), f"every core64 record unchanged ({same}/{len(old['records'])})")
    old_max = max(r["fid"] & 0xFFFFFF for r in old["records"])
    old_fids = {o["fid"] for o in old["records"]}
    added = [r for r in new["records"] if r["fid"] not in old_fids]
    need(added and min(r["fid"] & 0xFFFFFF for r in added) > old_max,
         f"every new record's FormID after core64's last (0x{old_max:06X})")
    need(new["masters"] == ["Starfield.esm"], f"masters {new['masters']}")
    del old

    # 2. object records: STAT / DOOR = bases, models, dependencies, REFRs as objects.json, cells
    own = len(new["masters"]) << 24
    recs = new["records"]
    stats = [r for r in recs if r["sig"] in ("STAT", "DOOR")]
    need(len(stats) == len(objects["bases"]), f"{len(stats):,} STAT/DOOR = {len(objects['bases']):,} bases")
    from fo4sf import fo4land
    missing = [m for m in (fo4land.zstring(overlay_records.field(r, "MODL", b"")) for r in stats)
               if not os.path.isfile(os.path.join(out, "Data", "meshes", m))]
    need(not missing, f"every base model is in Data\\meshes ({len(missing)} missing: {missing[:5]})")
    problems, worst_pos, worst_rot = x2c.ref_record_check(recs, own, objects, ids)
    need(not problems, f"every REFR matches objects.json ({len(problems)} problems: {problems[:3]})")
    need(worst_pos < 1e-3 and worst_rot < 1e-5, f"REFR position / rotation as written (worst {worst_pos:.2e} m, {worst_rot:.2e} rad)")
    refrs = sum(1 for r in recs if r["sig"] == "REFR")
    need(refrs == len(objects["refs"]) + 2, f"{refrs:,} REFR = {len(objects['refs']):,} objects + COC marker + anchor")
    rep["plugin_records"] = {s: sum(1 for r in recs if r["sig"] == s) for s in sorted({r["sig"] for r in recs})}
    rep["plugin_bytes"] = new["bytes"]
    del new, recs, by, stats
    cells = x2c.walk_cells(os.path.join(out, prm["plugin"]))
    per_cell = {}
    for r in objects["refs"]:
        per_cell[tuple(r["cell"])] = per_cell.get(tuple(r["cell"]), 0) + 1
    want = dict(per_cell)
    want[tuple(ov["spawn_cell"])] = want.get(tuple(ov["spawn_cell"]), 0) + 1        # + the COC marker
    got = {c["grid"]: len(c["refs"]) for c in cells.values() if c["grid"] is not None and c["refs"]}
    need(got == want, f"REFRs per exterior cell as objects.json ({len(got):,} cells with references)")
    wrong = [r["src"] for r in objects["refs"] if list(r["cell"]) != list(tg.sf_cell_of(r["pos"][0], r["pos"][1]))]
    need(not wrong, f"every reference in the cell of its written position ({len(wrong)} not: {wrong[:5]})")
    rep["cells"] = {"with_refs": len(got), "max_refs": max(got.values()), "densest": sorted(
        ([list(k), v] for k, v in got.items()), key=lambda kv: -kv[1])[:5]}
    deps = x2c.dependency_check(os.path.join(out, "Data"), [b["model"] for b in objects["bases"]], prefix=ASSET_PREFIX,
                                vanilla=x2c.vanilla_textures(a.sf_data))
    need(not deps["missing"], f"every geometry / material / texture the models name exists ({deps['missing_count']} "
                              f"missing: {deps['missing'][:5]}; {deps['counts']})")
    rep["dependencies"] = deps

    # 3. object z - terrain z under every placed origin: the BTD, and with --fo4 FO4's own LAND
    pos = np.array([r["pos"] for r in objects["refs"]], np.float64)
    g = terrain.bilinear(pos[:, 0], pos[:, 1])
    dz = pos[:, 2] - g
    rep["object_minus_btd"] = {"objects": int(len(dz)), "histogram_m": {
        f"{lo}..{hi}": int(((dz >= lo) & (dz < hi)).sum()) for lo, hi in
        ((-500, -1), (-1, -0.25), (-0.25, -0.05), (-0.05, 0.05), (0.05, 0.25), (0.25, 1), (1, 500))}}
    by_src = {r["src"]: i for i, r in enumerate(objects["refs"])}
    k = by_src.get(STATION)
    if k is not None:
        gb = terrain.bilinear([pos[k, 0]], [pos[k, 1]])[0]
        need(abs(pos[k, 2] - gb) <= terrain.step, f"Red Rocket station z - BTD = {(pos[k, 2] - gb) * 1000:.2f} mm "
                                                     f"(within one step {terrain.step * 1000:.2f} mm)")
    if a.fo4:
        xs, ys = pos[:, 0] * 70.0 / 4096.0, pos[:, 1] * 70.0 / 4096.0
        box = (int(math.floor(xs.min())) - 1, int(math.floor(xs.max())) + 1, int(math.floor(ys.min())) - 1,
               int(math.floor(ys.max())) + 1)
        g4 = np.array([np.nan if v is None else v for v in x2c.fo4_ground(a.fo4, objects["refs"], box)], np.float64)
        ok = np.isfinite(g4)
        diff = g[ok] - g4[ok]
        rep["btd_minus_fo4_land_under_objects"] = abs_stats(diff)
        worst = np.argsort(-np.abs(diff))[:5]
        idx = np.nonzero(ok)[0]
        rep["btd_minus_fo4_land_under_objects"]["worst"] = [
            {"src": objects["refs"][idx[j]]["src"], "pos": objects["refs"][idx[j]]["pos"],
             "edid": objects["bases"][objects["refs"][idx[j]]["base"]]["edid"], "btd_minus_fo4_mm": round(float(diff[j]) * 1000, 1)}
            for j in worst]
        rep["btd_minus_fo4_land_under_objects"]["no_fo4_land"] = int((~ok).sum())
        if k is not None:
            need(abs(pos[k, 2] - g4[k]) < 1e-3, f"Red Rocket station z - FO4 LAND = {(pos[k, 2] - g4[k]) * 1000:.2f} mm (FO4: 0)")
        s = rep["btd_minus_fo4_land_under_objects"]
        print(f"BTD - FO4 LAND under {s['count']:,} origins: median {s['median_mm']} mm, p99 {s['p99_mm']} mm, "
              f"max {s['max_mm']} mm")

    # 4. every plan point re-derived from the converted collision (local world) and the predicted verdicts
    bases, placed = objects["bases"], [dict(r) for r in objects["refs"]]
    sx, sy = ov["spawn"][:2]
    world = CoreWorld(os.path.join(out, "Data"), bases, placed, terrain, (sx - AREA_M, sy - AREA_M, sx + AREA_M, sy + AREA_M))
    need(not world.collision_errors, f"local world: converted collision decodes ({len(world.collision_errors)} errors)")
    metas = {(q["entry"], q["label"]): q for q in exp["points"]}
    kinds = {kk: q["kind"] for kk, q in metas.items()}
    core_plan = load(os.path.join(a.core, "plan.json"))
    pr = validate_plan(plan, core_plan[0], kinds)
    need(not pr, f"plan entries: runner keys, core64's keys carried, z_ref on its terrain reference ({pr[:3]})")
    land0 = world.landing(*ov["spawn"])
    need(all(abs(land0["centre"] - e["spawn_local"][2]) < 1e-3 and e["spawn_local"][:2] == ov["spawn"][:2] for e in plan),
         f"spawn_local = where the player lands under the COC marker ({land0['centre']:.4f})")
    need(exterior.clearance(world.index, ov["spawn"][0], ov["spawn"][1], land0["centre"]) >= x2c.PLAYER_HEIGHT,
         "room for the player above the arrival")
    pts = []
    for e, entry in enumerate(plan):
        need(entry["coc"] == ov["coc"], f"entry {e + 1}: coc {entry['coc']}")
        low = min(p["expect"] for p in entry["points"])
        need(entry["settle_ms"] >= 1000.0 * cwo.fall_seconds(entry["drop_z"], low),
             f"entry {e + 1}: settle {entry['settle_ms']} ms covers the fall")
        here = ov["spawn"][:2]
        for p in entry["points"]:
            meta = metas[(e, p["label"])]
            d = math.hypot(p["x"] - sx, p["y"] - sy)
            need(d <= NEAR_M, f"{p['label']}: {d:.0f} m from the arrival (<= {NEAR_M:.0f})")
            land = world.landing(p["x"], p["y"], entry["drop_z"])
            if meta["kind"] in ("terrain", "terrain_ref", "terrain_near_object", "view"):
                hs = world.ground_all(p["x"], p["y"])
                err = max(abs(v - p["expect"]) for v in hs.values())
                need(not land["on_object"] and err <= world.step, f"{p['label']}: terrain, decoded within one step")
                if meta["kind"] != "terrain_near_object":
                    near = exterior.nearby_object(world.index.top, world.ground, p["x"], p["y"], entry["drop_z"],
                                                  radii=x2c.TERRAIN_CLEAR_RADII)
                    need(near is None, f"{p['label']}: no object within {x2c.TERRAIN_CLEAR_RADII[-1]} m")
                if meta["kind"] == "terrain_ref":
                    need(x2c.reference_ok(world, p["x"], p["y"]) is not None, f"{p['label']} (entry {e + 1}): level open terrain")
            else:
                owner = world.by_src[meta["owner"]["src"]]
                err = abs(land["centre"] - p["expect"])
                need(land["on_object"] and land["owner"] == owner and err < 1e-3,
                     f"{p['label']}: lands on {meta['owner']['edid']} at {p['expect']} (error {err * 1000:.2f} mm)")
                if e == 1:
                    dd = x2c.discrimination(world, p["x"], p["y"], p["expect"])
                    need(dd >= x2c.MIN_DISCRIMINATION, f"{p['label']}: {dd:.2f} m above the terrain under its disc")
            tops = [s[0][0] for dx, dy in exterior.disc_offsets(1.0) if (s := world.index.surfaces(p["x"] + dx, p["y"] + dy))]
            need(entry["drop_z"] >= max(tops + [p["expect"]]) + TOP_CLEAR - 1e-6,
                 f"{p['label']}: drop_z {entry['drop_z']} >= every collision top within 1 m + {TOP_CLEAR:g}")
            pts.append({"entry": e, "label": p["label"], "kind": meta["kind"], "expect": p["expect"],
                        "landing": x2c.landing_json(world, land), "error_mm": round(err * 1000, 3),
                        "from_previous_m": round(math.hypot(p["x"] - here[0], p["y"] - here[1]), 1)})
            here = (p["x"], p["y"])
        meta = {p["label"]: metas[(e, p["label"])] for p in entry["points"]}
        pred = {sc: x2c.judge_heights(entry["points"], scenario_reads(world, entry, meta, sc), entry["z_ref"])[:2]
                for sc in SCENARIOS[e]}
        need(x2c.judge_heights(entry["points"], [p["expect"] for p in entry["points"]], entry["z_ref"])[0] == "PASS",
             f"entry {e + 1} passes on its own expectations")
        if e == 0:
            need(pred["flat_terrain"][0] == "FAIL" and pred["no_objects"][0] == "PASS",
                 f"entry 1 fails on flat terrain ({pred['flat_terrain'][1]:.2f} m) and does not depend on the objects")
        if e == 1:
            need(pred["no_objects"][0] == "FAIL" and pred["no_objects"][1] >= x2c.MIN_DISCRIMINATION,
                 f"entry 2 fails without the objects (worst {pred['no_objects'][1]:.2f} m)")
    rep["points"] = pts
    if a.fo4_data:
        rep["fo4_collision_tops"] = x2c.fo4_collision_tops(a.fo4_data, plan, metas)
        for t in rep["fo4_collision_tops"]:
            if t["entry"] == 1:
                need(t["diff_mm"] is not None and abs(t["diff_mm"]) < 1.0 and t["layer"] == 1,
                     f"{t['label']}: FO4's own collision top {t['fo4_top']} (layer {t['layer']}) = expect ({t['diff_mm']} mm)")

    # 5. the archive the installer builds: one General archive, every entry stored, below 4 GiB
    files = data_files(out)
    est = ba2_size(files)
    rep["archive"] = {"files": len(files), "data_bytes": sum(b for _, b in files), "estimate_bytes": est,
                      "by_folder": {f: sum(b for n, b in files if n.split("/")[0].lower() == f)
                                    for f in sorted({n.split("/")[0].lower() for n, _ in files})}}
    need(est < ARCHIVE_LIMIT, f"one stored archive about {est / 2 ** 30:.3f} GiB < 4 GiB")
    need(all(n.isascii() for n, _ in files), "archive paths are plain ASCII")
    # FO4's own file names keep their spaces (e.g. "loose planks 01.nif"); exp2c packed 33 such paths the same way
    # and its objects loaded in game, so they are counted, not refused
    rep["archive"]["paths_with_spaces"] = sum(1 for n, _ in files if " " in n)
    if a.archive2 and a.scratch:
        dry, probs = archive_dry_run(a.archive2, out, a.scratch, files)
        rep["archive"]["dry_run"] = dry
        need(not probs and dry.get("bytes", ARCHIVE_LIMIT) < ARCHIVE_LIMIT,
             f"Archive2 dry run: {dry.get('bytes', 0) / 2 ** 30:.3f} GiB, {dry.get('entries')} entries, "
             f"{dry.get('packed_entries')} packed ({probs})")
    rep["checks"] = checks
    rep["pass"] = all(c[1] for c in checks)
    rep["seconds"] = round(time.time() - t0, 1)
    save(os.path.join(out, "offline_check.json"), rep, indent=1)
    for what, good in checks:
        if not good or len(checks) < 400:
            print(("  ok   " if good else "  FAIL ") + what)
    print(f"{sum(1 for c in checks if c[1])} of {len(checks)} checks ok; {rep['seconds']} s")
    print("CHECK", "PASS" if rep["pass"] else "FAIL")
    return 0 if rep["pass"] else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select")
    s.add_argument("--work", required=True)
    s.add_argument("--core", required=True, help="the staged core64 terrain (overlays_params.json, plugins, Data)")
    s = sub.add_parser("measure")
    s.add_argument("--work", required=True)
    s.add_argument("--fo4-data", required=True)
    s.add_argument("--caps", default="256,512,1024,2048")
    s.add_argument("--kind-caps", default="color=1024,normal=512,rough=256,opacity=512",
                   help="per-kind cap sets to price, separated by ';' (convert_batch --max-texture syntax)")
    s.add_argument("--calibrate", default="", help="a finished convert_batch staging (e.g. exp2c's) for the mesh size")
    for name in ("stage", "check"):
        s = sub.add_parser(name)
        s.add_argument("--work", required=True)
        s.add_argument("--core", required=True)
        s.add_argument("--out", required=True)
        if name == "stage":
            s.add_argument("--sf-esm", default="", help="Starfield.esm: build the plugins with dotnet/TerrainOverlays")
        else:
            s.add_argument("--sf-data", default="", help="Starfield Data (vanilla Mars entries, texture archives)")
            s.add_argument("--fo4", default="", help="Fallout4.esm: FO4's own terrain under every object")
            s.add_argument("--fo4-data", default="", help="FO4 Data: object tops against FO4's own collision")
            s.add_argument("--archive2", default="", help="Archive2.exe: build the archive into --scratch and measure it")
            s.add_argument("--scratch", default="", help="folder for the Archive2 dry run (deleted afterwards)")
    a = ap.parse_args()
    return {"select": cmd_select, "measure": cmd_measure, "stage": cmd_stage, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
