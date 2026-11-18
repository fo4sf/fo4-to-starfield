"""Build and verify the `WG1` 29 x 29 Red Rocket ground-texture (`LTEX`) prototype.

Maps Fallout 4's 40 most-used `Commonwealth` `LTEX` land textures to converted Starfield PBR textures
(`_color.dds`, `_normal.dds`, `_rough.dds`), generates 40 `Terrain1Layer.mat` `.mat` material files, appends
40 custom `LTEX` records into `FO4WG1RedRocket.esm`, encodes per-quadrant `quad_map` + 15-bit sequential 3-bit
`weights` into `Data/Terrain/FO4WG1_Commonwealth.btd`, and verifies offline that the decoded `.btd` holds `> 1`
`LTEX` entry and matches Fallout 4's dominant `LTEX` on `>= 90%` of quadrants across the 29 x 29 window.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
if os.path.join(REPO_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(REPO_ROOT, "src"))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from fo4sf import btd, pipeline, terrain_grid as tg, textures  # noqa: E402
from fo4sf.terrain import ltex_map as lm, overlay_postpatch as opp  # noqa: E402
from fo4sf.terrain.path_guard import refuse_unsafe_output_path  # noqa: E402
import make_cw_overlays as mco  # noqa: E402

FIRST_LTEX_LOCAL_FID = 0x000F00
ASSET_PREFIX = "fo4wg1"
PLUGIN_NAME = "FO4WG1RedRocket.esm"
MARS_PLUGIN_NAME = "FO4WG1RedRocket_Mars.esm"
WORLD_EDID = "FO4WG1_Commonwealth"
COC_EDID = "FO4WG1_RedRocketSpawn"


def _clean_stem(diffuse_path: str) -> str:
    rel = diffuse_path.replace("/", "\\").strip("\\")
    if rel.lower().startswith("textures\\"):
        rel = rel[len("textures\\") :]
    low = rel.lower()
    for suf in ("_d.dds", ".dds"):
        if low.endswith(suf):
            rel = rel[: -len(suf)]
            break
    return rel.replace("\\", "/").lower()


def _stage_or_convert_texture_triple(
    *,
    stem: str,
    diffuse: str,
    normal: str,
    spec: str,
    smoothness: float,
    spec_mult: float,
    out_data_dir: str,
    staged_textures_dirs: Sequence[str],
    fo4_archives: Optional[pipeline.Fo4Archives],
    texconv_exe: Optional[str],
) -> Tuple[str, str, str, str]:
    """Ensure `Data/textures/fo4wg1/<stem>_{color,normal,rough}.dds` exist; return `(color, normal, rough, source_mode)`."""
    rel_base = f"textures/{ASSET_PREFIX}/{stem}"
    dst_paths = {
        kind: os.path.join(out_data_dir, *f"{rel_base}_{kind}.dds".split("/"))
        for kind in ("color", "normal", "rough")
    }
    if all(os.path.isfile(p) for p in dst_paths.values()):
        return (
            f"{rel_base}_color.dds",
            f"{rel_base}_normal.dds",
            f"{rel_base}_rough.dds",
            "cached",
        )

    # 1. Check read-only pre-converted staging folders first
    for sdir in staged_textures_dirs:
        if not sdir or not os.path.isdir(sdir):
            continue
        cands = {
            kind: os.path.join(sdir, *f"{stem}_{kind}.dds".split("/"))
            for kind in ("color", "normal", "rough")
        }
        if all(os.path.isfile(p) for p in cands.values()):
            for kind, src_p in cands.items():
                dst_p = dst_paths[kind]
                os.makedirs(os.path.dirname(dst_p), exist_ok=True)
                try:
                    os.link(src_p, dst_p)
                except OSError:
                    shutil.copy2(src_p, dst_p)
            return (
                f"{rel_base}_color.dds",
                f"{rel_base}_normal.dds",
                f"{rel_base}_rough.dds",
                "linked_staged",
            )

    # 2. Convert from Fallout 4 BA2 archives via texconv
    if fo4_archives is None or not texconv_exe:
        raise RuntimeError(f"Missing converted textures for {stem} and no --fo4-data / --texconv supplied")
    d_bytes = fo4_archives.texture(diffuse)
    n_bytes = fo4_archives.texture(normal) if normal else None
    s_bytes = fo4_archives.texture(spec) if spec else None
    if d_bytes is None:
        raise FileNotFoundError(f"FO4 diffuse texture {diffuse!r} not found in archives")

    with tempfile.TemporaryDirectory() as tmp:
        d_in = os.path.join(tmp, "d.dds")
        Path(d_in).write_bytes(d_bytes)
        textures.texconv(texconv_exe, d_in, tmp, "BC1_UNORM_SRGB", ("-srgbi",))

        if n_bytes is not None:
            nr, ng = pipeline._plane_pair(n_bytes, tmp, texconv_exe)
        else:
            nr = np.full((16, 16), 128, dtype=np.uint8)
            ng = np.full((16, 16), 128, dtype=np.uint8)
        n_in = os.path.join(tmp, "n_in.dds")
        textures.write_rg8_snorm(n_in, nr, ng)
        textures.texconv(texconv_exe, n_in, tmp, "BC5_SNORM")

        if s_bytes is not None:
            _sr, sg = pipeline._plane_pair(s_bytes, tmp, texconv_exe)
            rough = textures.roughness_from_smoothness(sg, smoothness, spec_mult)
        else:
            rough = np.full((max(4, nr.shape[0] // 4), max(4, nr.shape[1] // 4)), 190, dtype=np.uint8)
        r_in = os.path.join(tmp, "r_in.dds")
        textures.write_r8(r_in, rough)
        textures.texconv(texconv_exe, r_in, tmp, "BC4_UNORM")

        for kind, fn in (("color", "d.dds"), ("normal", "n_in.dds"), ("rough", "r_in.dds")):
            dst_p = dst_paths[kind]
            os.makedirs(os.path.dirname(dst_p), exist_ok=True)
            pipeline.write_staged(dst_p, Path(tmp, fn).read_bytes())

    return (
        f"{rel_base}_color.dds",
        f"{rel_base}_normal.dds",
        f"{rel_base}_rough.dds",
        "converted_ba2",
    )


def build_wg1_prototype(args: argparse.Namespace) -> Dict[str, Any]:
    inputs = [args.fo4, args.fo4_data, args.sf_data, args.content_resources, *args.staged_textures]
    out_dir = str(refuse_unsafe_output_path(args.out, input_paths=inputs))
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    out_data_dir = os.path.join(out_dir, "Data")

    # 1. Rank Commonwealth top-K (40) LTEX and resolve textures
    ranked_top = lm.rank_world_ltex_top_k(args.fo4, world_edid="Commonwealth", top_k=args.top_k)
    top_keys = [k for k, _ in ranked_top]
    fo4_arc = pipeline.Fo4Archives(args.fo4_data)
    resolved_tex = lm.resolve_fo4_ltex_textures(args.fo4, top_keys, material_archives=fo4_arc.materials)
    mat_template = lm.load_terrain_mat_template(args.content_resources)

    # 2. Build base 29 x 29 Red Rocket terrain stage via make_cw_overlays.py
    # FO4 cells [-23, 24, -23, 24] with --tile 29 --pad origin -> 1 tile (29 x 29) cells -14..14, origin (0.0, 0.0)
    argv_prev = sys.argv
    try:
        sys.argv = [
            "make_cw_overlays.py",
            "build",
            "--fo4",
            args.fo4,
            "--sf-data",
            args.sf_data,
            "--out",
            out_dir,
            "--fo4-cells",
            "-23",
            "24",
            "-23",
            "24",
            "--tile",
            str(args.tile),
            "--pad",
            "origin",
            "--plan",
            "rays",
            "--prefix",
            "FO4WG1",
            "--world",
            WORLD_EDID,
            "--coc",
            COC_EDID,
            "--plugin",
            PLUGIN_NAME,
            "--mars-plugin",
            MARS_PLUGIN_NAME,
            "--experiment",
            "terrain_wg1_redrocket",
            "--mask-writer",
            "builtin",
            "--ref-lat",
            "0.3",
            "--ref-lon",
            "-1.2",
            "--ref-offset",
            "-12",
            "-27",
            "--centre-cell",
            "-12",
            "-27",
        ]
        mco.main()
    finally:
        sys.argv = argv_prev

    # 3. Stage converted PBR textures + 40 .mat files + 40 LTEX record specs
    texconv_exe = args.texconv or shutil.which("texconv") or shutil.which("Texconvx64")
    ltex_mapping: Dict[str, int] = {}
    ltex_records_spec: List[Dict[str, Any]] = []
    manifest_rows: List[Dict[str, Any]] = []
    mode_counts: Dict[str, int] = {}

    for idx, (fo4_key, use_cnt) in enumerate(ranked_top):
        info = resolved_tex[fo4_key]
        local_fid = FIRST_LTEX_LOCAL_FID + idx
        full_sf_fid = 0x01000000 | local_fid  # master 0 = Starfield.esm, own = 01
        safe_edid = re.sub(r"[^A-Za-z0-9_]", "_", info["edid"])
        sf_edid = f"FO4WG1_{safe_edid}"
        stem = _clean_stem(info["diffuse"])
        c_rel, n_rel, r_rel, src_mode = _stage_or_convert_texture_triple(
            stem=stem,
            diffuse=info["diffuse"],
            normal=info["normal"],
            spec=info["spec"],
            smoothness=info["smoothness"],
            spec_mult=info["spec_mult"],
            out_data_dir=out_data_dir,
            staged_textures_dirs=args.staged_textures,
            fo4_archives=fo4_arc,
            texconv_exe=texconv_exe,
        )
        mode_counts[src_mode] = mode_counts.get(src_mode, 0) + 1

        mat_dict = lm.build_terrain_mat(mat_template, sf_edid, c_rel, n_rel, r_rel)
        mat_rel = f"materials/terrain/{sf_edid}.mat"
        mat_dst = os.path.join(out_data_dir, *mat_rel.split("/"))
        pipeline.write_staged(mat_dst, (json.dumps(mat_dict, indent=2) + "\n").encode("utf-8"))

        bnam_str = f"Materials\\Terrain\\{sf_edid}.mat"
        ltex_mapping[fo4_key] = full_sf_fid
        ltex_records_spec.append({"fid_local": local_fid, "edid": sf_edid, "bnam": bnam_str})
        manifest_rows.append(
            {
                "rank": idx + 1,
                "fo4_ltex": fo4_key,
                "fo4_edid": info["edid"],
                "commonwealth_quadrant_uses": use_cnt,
                "sf_ltex_fid": f"{full_sf_fid:08X}",
                "sf_edid": sf_edid,
                "mat_file": f"Data/{mat_rel}",
                "textures": {"color": f"Data/{c_rel}", "normal": f"Data/{n_rel}", "rough": f"Data/{r_rel}"},
                "texture_source": src_mode,
            }
        )

    # 4. Read FO4 LAND layers over the 29 x 29 window and encode BTD LTEX table + quad_map + weights
    prm = json.loads(Path(out_dir, "overlays_params.json").read_text(encoding="utf-8"))
    ov = prm["overlays"][0]
    n_cells = int(ov["n"])
    origin_cw_m = (float(ov["origin_cw_m"][0]), float(ov["origin_cw_m"][1]))
    g_min = tg.grid_origin(n_cells) + origin_cw_m[0]
    g_max = g_min + n_cells * tg.SF_CELL_M
    gy_min = tg.grid_origin(n_cells) + origin_cw_m[1]
    gy_max = gy_min + n_cells * tg.SF_CELL_M
    cx0, cx1, cy0, cy1 = tg.fo4_cells_covering(g_min, g_max, gy_min, gy_max)
    window_cells = {(x, y) for x in range(cx0 - 1, cx1 + 2) for y in range(cy0 - 1, cy1 + 2)}

    fo4_quad_layers, _ = lm.read_fo4_world_land_layers(args.fo4, world_edid="Commonwealth", cells=window_cells)
    ltex_table, quad_map, weights, enc_stats = lm.encode_btd_ltex_window(
        fo4_quad_layers,
        n_sf_cells=n_cells,
        origin_cw_m=origin_cw_m,
        ltex_mapping=ltex_mapping,
        default_fo4_key="Fallout4.esm:000000",
        fallback_sf_fid=lm.PLAIN_GROUND_SF_FID,
    )

    btd_path = os.path.join(out_dir, *ov["btd_file"].split("/"))
    orig_btd = btd.read(Path(btd_path).read_bytes())
    patched_btd = btd.Btd(
        orig_btd.version,
        orig_btd.hmin,
        orig_btd.hmax,
        ltex_table,
        orig_btd.heights_raw,
        weights,
        quad_map,
    )
    pipeline.write_staged(btd_path, btd.write(patched_btd))

    # 5. Build overlay .esm via dotnet/TerrainOverlays (untouched) and post-patch our 40 LTEX records
    dotnet_exe = shutil.which("dotnet")
    if not dotnet_exe:
        raise RuntimeError("dotnet CLI not found on PATH")
    sf_esm = os.path.join(args.sf_data, "Starfield.esm")
    dll_path = os.path.join(REPO_ROOT, "dotnet", "TerrainOverlays", "bin", "Release", "net9.0", "TerrainOverlays.dll")
    if not os.path.isfile(dll_path):
        subprocess.run([dotnet_exe, "build", os.path.join(REPO_ROOT, "dotnet", "TerrainOverlays"), "-c", "Release", "--nologo"], check=True)
    subprocess.run([dotnet_exe, dll_path, sf_esm, out_dir], check=True)

    plugin_path = os.path.join(out_dir, PLUGIN_NAME)
    opp.patch_overlay_plugin(
        plugin_path,
        world_display_name="FO4WG1_Commonwealth (Red Rocket 29x29 LTEX prototype)",
        map_marker_name="FO4WG1_RedRocketArrival",
        ltex_records=ltex_records_spec,
    )

    manifest_doc = {
        "world": WORLD_EDID,
        "plugin": PLUGIN_NAME,
        "tile_cells": n_cells,
        "top_k": args.top_k,
        "fallback_sf_fid": f"{lm.PLAIN_GROUND_SF_FID:08X}",
        "texture_source_counts": mode_counts,
        "ltex_mapping": {k: f"{v:08X}" for k, v in ltex_mapping.items()},
        "quad_gt_dominant": enc_stats["quad_gt_dominant"],
        "entries": manifest_rows,
    }
    Path(out_dir, "wg1_ltex_manifest.json").write_text(json.dumps(manifest_doc, indent=2) + "\n", encoding="utf-8")

    return check_wg1_stage(out_dir)


def check_wg1_stage(stage_dir: str) -> Dict[str, Any]:
    refuse_unsafe_output_path(stage_dir)
    manifest = json.loads(Path(stage_dir, "wg1_ltex_manifest.json").read_text(encoding="utf-8"))
    prm = json.loads(Path(stage_dir, "overlays_params.json").read_text(encoding="utf-8"))
    ov = prm["overlays"][0]

    btd_path = os.path.join(stage_dir, *ov["btd_file"].split("/"))
    dec_btd = btd.read(Path(btd_path).read_bytes())

    ltex_mapping = {k: int(v, 16) for k, v in manifest["ltex_mapping"].items()}
    vrep = lm.verify_btd_against_fo4_dominants(dec_btd, manifest["quad_gt_dominant"], ltex_mapping)

    # Verify plugin LTEX records and .mat + .dds files on disk
    plug = opp.RawPlugin.read(os.path.join(stage_dir, manifest["plugin"]))
    ltex_recs = [
        it
        for g in plug.items
        if isinstance(g, opp.RawGroup) and g.label == b"LTEX"
        for it in g.children
        if isinstance(it, opp.RawRecord) and it.sig == b"LTEX"
    ]
    missing_assets: List[str] = []
    for row in manifest["entries"]:
        mat_p = os.path.join(stage_dir, *row["mat_file"].split("/"))
        if not os.path.isfile(mat_p):
            missing_assets.append(row["mat_file"])
        for tpath in row["textures"].values():
            tp = os.path.join(stage_dir, *tpath.split("/"))
            if not os.path.isfile(tp):
                missing_assets.append(tpath)

    if vrep["ltex_table_size"] <= 1:
        raise AssertionError(f"Expected > 1 LTEX in BTD table, found {vrep['ltex_table_size']}")
    if len(ltex_recs) != len(manifest["entries"]):
        raise AssertionError(f"Expected {len(manifest['entries'])} LTEX records in plugin, found {len(ltex_recs)}")
    if missing_assets:
        raise AssertionError(f"Missing staged .mat/.dds assets: {missing_assets[:5]}")
    if vrep["dominant_blended_match_ratio"] < 0.90:
        raise AssertionError(
            f"Dominant LTEX match ratio {vrep['dominant_blended_match_ratio']:.4f} < 0.90"
        )

    report = {
        "step": "WG1",
        "plugin": manifest["plugin"],
        "world": manifest["world"],
        "tile_cells": manifest["tile_cells"],
        "plugin_ltex_records": len(ltex_recs),
        "btd_ltex_table_size": vrep["ltex_table_size"],
        "distinct_ltex_used_in_window": vrep["distinct_ltex_referenced_in_quads"],
        "quadrants_total": vrep["quadrants_total"],
        "dominant_blended_matches": vrep["dominant_blended_matches"],
        "dominant_blended_match_ratio": vrep["dominant_blended_match_ratio"],
        "base_slot_matches": vrep["base_slot_matches"],
        "base_slot_match_ratio": vrep["base_slot_match_ratio"],
        "missing_assets": len(missing_assets),
        "texture_source_counts": manifest["texture_source_counts"],
        "pass": True,
    }
    Path(stage_dir, "wg1_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Build and verify WG1 29x29 Red Rocket ground-texture prototype.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b_p = sub.add_parser("build", help="Stage 29x29 Red Rocket ground-texture prototype")
    b_p.add_argument("--fo4", required=True, help="Path to Fallout4.esm")
    b_p.add_argument("--fo4-data", required=True, help="Path to Fallout 4 Data directory")
    b_p.add_argument("--sf-data", required=True, help="Path to Starfield Data directory")
    b_p.add_argument("--content-resources", required=True, help="Path to Starfield Tools/ContentResources.zip")
    b_p.add_argument("--texconv", default="", help="Path to Texconvx64.exe")
    b_p.add_argument("--staged-textures", action="append", default=[], help="Optional read-only converted textures dir")
    b_p.add_argument("--tile", type=int, default=29)
    b_p.add_argument("--top-k", type=int, default=40)
    b_p.add_argument("--out", required=True, help="Output directory outside Git worktrees and game folders")

    c_p = sub.add_parser("check", help="Offline decode and verify staged WG1 prototype")
    c_p.add_argument("--out", required=True)

    args = ap.parse_args(argv)
    if args.cmd == "build":
        rep = build_wg1_prototype(args)
        print(json.dumps(rep, indent=2))
        return 0
    if args.cmd == "check":
        rep = check_wg1_stage(args.out)
        print(json.dumps(rep, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
