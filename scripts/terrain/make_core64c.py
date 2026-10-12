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


def bc_size(fmt, width, height, cap=0, mips=None):
    """Bytes of a block-compressed DDS (DX10 header, 148 B) with a full mip chain, top mips dropped until both sides
    are at most `cap` (0 = no cap), as textures.cap_dds writes it."""
    w, h = max(1, int(width)), max(1, int(height))
    while cap and max(w, h) > cap and min(w, h) > 4:
        w, h = max(1, w // 2), max(1, h // 2)
    n = mips or (int(math.log2(max(w, h))) + 1)
    total = 148
    for i in range(n):
        mw, mh = max(1, w >> i), max(1, h >> i)
        total += max(1, (mw + 3) // 4) * max(1, (mh + 3) // 4) * BC_BYTES_PER_BLOCK[fmt]
    return total


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
        return f"materials\\{ASSET_PREFIX}\\{stem}.mat"

    def _glass(self, base, normal):
        d = self.dims(base) if base else None
        if d is None:
            raise FileNotFoundError("glass base texture missing")
        n = self.dims(normal) if normal else None
        stem = "glass/" + base.lower() + "|" + (normal or "").lower()
        self.outputs[stem] = [("color", "BC1", *d)] + ([("normal", "BC5", *n)] if n else []) + [("rough", "BC4", 16, 16)]
        return f"materials\\{ASSET_PREFIX}\\{stem}.mat"

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
    # mesh output size: converted .nif + .mesh bytes per source NIF byte, from a finished conversion (exp2c) if given
    ratio = None
    if a.calibrate and os.path.isfile(os.path.join(a.calibrate, "manifest.json")):
        man = load(os.path.join(a.calibrate, "manifest.json"))
        src_b = sum(mesh_entry_size(src, i["source"]) for i in man["items"])
        out_b = sum(os.path.getsize(os.path.join(r, f)) for t in ("meshes", "geometries")
                    for r, _d, fs in os.walk(os.path.join(a.calibrate, t)) for f in fs)
        ratio = out_b / src_b if src_b else None
    mesh_est = int(nif_bytes * ratio) if ratio else None
    rep = {"references": sel["refs"] + sel["deferred"], "to_convert_refs": sel["to_convert"], "models": len(models),
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
    return 0


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
    s.add_argument("--calibrate", default="", help="a finished convert_batch staging (e.g. exp2c's) for the mesh size")
    a = ap.parse_args()
    return {"select": cmd_select, "measure": cmd_measure}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
