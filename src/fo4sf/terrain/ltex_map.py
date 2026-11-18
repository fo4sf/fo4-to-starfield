"""Fallout 4 `LAND` (`BTXT` / `ATXT` / `VTXT`) -> Starfield `BTD` `LTEX` layer mapper and `.mat` builder (`WG1`).

Pure library module (no machine-specific paths; synthetic-testable without game installs):
  - Parses FO4 `LAND` per-quadrant `BTXT` base + `ATXT` / `VTXT` (`17 x 17`) alpha layers into exact per-vertex
    fractional coverages summing to `1.0`.
  - Ranks a worldspace's top-`K` (`40`) `LTEX` records by quadrant appearance (`BTXT` + `ATXT`) and resolves each
    `LTEX -> TXST -> BGSM` texture set (`diffuse`, `normal`, `smooth_spec`).
  - Clones Starfield's `Terrain1Layer.mat` single-layer terrain material template with deterministic remapped `res:`
    component IDs.
  - Encodes and decodes `BTD` `ltex` tables, `quad_map` (`[ncy*2, ncx*2, 8]`), and 15-bit sequential 3-bit `weights`
    (`[ncy*128, ncx*128]`), verifying dominant `LTEX` fidelity per quadrant.
"""
from __future__ import annotations

from collections import Counter
import json
import math
import os
import re
import struct
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import zipfile
import zlib

import numpy as np

from fo4sf import btd, convert_material as cm, fo4land, terrain_grid as tg

FO4_QUAD_VERTS = 17
FO4_QUAD_UNITS = 2048.0
FO4_VERT_STEP_UNITS = 128.0
BTD_QUAD_SAMPLES = 64
PLAIN_GROUND_SF_FID = 0x001235C2  # LDirtFootprints01 in Starfield.esm (fallback for unmapped rare LTEX)
TERRAIN_TEMPLATE_PATH = "Materials/Terrain/DirtFootprints01.mat"
DEFAULT_FO4_DIRT_TEXTURES = (
    "Landscape\\Ground\\CommonwealthDefault01_d.dds",
    "Landscape\\Ground\\CommonwealthDefault01_n.dds",
    "Landscape\\Ground\\CommonwealthDefault01_s.dds",
)


def canonical_ltex_key(raw_fid: int, masters: Sequence[str], own_plugin: str) -> str:
    if (int(raw_fid) & 0xFFFFFF) == 0:
        owner = masters[0] if masters else own_plugin
        return f"{owner}:000000"
    idx = (int(raw_fid) >> 24) & 0xFF
    local = int(raw_fid) & 0xFFFFFF
    owner = masters[idx] if idx < len(masters) else own_plugin
    return f"{owner}:{local:06X}"


def parse_fo4_land_layers(
    subrecords: Iterable[Tuple[bytes, bytes]],
    masters: Sequence[str],
    own_plugin: str,
) -> Dict[int, Dict[str, np.ndarray]]:
    """Parse one FO4 `LAND` record's `BTXT` / `ATXT` / `VTXT` into `{q (0..3): {ltex_key: float32[17, 17]}}`."""
    default_key = canonical_ltex_key(0, masters, own_plugin)
    btxt: Dict[int, str] = {0: default_key, 1: default_key, 2: default_key, 3: default_key}
    # q -> list of (layer_int, ltex_key, alpha_grid_17x17)
    atxt_layers: Dict[int, List[Tuple[int, str, np.ndarray]]] = {0: [], 1: [], 2: [], 3: []}

    pending_atxt: Optional[Tuple[int, int, str]] = None
    for sig, data in subrecords:
        if sig == b"BTXT" and len(data) >= 8:
            pending_atxt = None
            lfid, q, _pad, _layer = struct.unpack_from("<IBBh", data)
            if q < 4:
                btxt[q] = canonical_ltex_key(lfid, masters, own_plugin)
        elif sig == b"ATXT" and len(data) >= 8:
            lfid, q, _pad, layer = struct.unpack_from("<IBBh", data)
            if q < 4:
                pending_atxt = (int(q), int(layer), canonical_ltex_key(lfid, masters, own_plugin))
            else:
                pending_atxt = None
        elif sig == b"VTXT" and pending_atxt is not None:
            q, layer, lkey = pending_atxt
            pending_atxt = None
            alpha = np.zeros((FO4_QUAD_VERTS, FO4_QUAD_VERTS), dtype=np.float32)
            count = len(data) // 8
            for i in range(count):
                pos, _p0, _p1, val = struct.unpack_from("<HBBf", data, i * 8)
                if pos < FO4_QUAD_VERTS * FO4_QUAD_VERTS and math.isfinite(val):
                    r, c = divmod(int(pos), FO4_QUAD_VERTS)
                    alpha[r, c] = max(0.0, min(1.0, float(val)))
            atxt_layers[q].append((layer, lkey, alpha))
        else:
            pending_atxt = None

    out: Dict[int, Dict[str, np.ndarray]] = {}
    for q in range(4):
        cov: Dict[str, np.ndarray] = {
            btxt[q]: np.ones((FO4_QUAD_VERTS, FO4_QUAD_VERTS), dtype=np.float32)
        }
        for _layer, lkey, alpha in sorted(atxt_layers[q], key=lambda x: x[0]):
            inv = 1.0 - alpha
            for k in list(cov.keys()):
                cov[k] = cov[k] * inv
            if lkey in cov:
                cov[lkey] = cov[lkey] + alpha
            else:
                cov[lkey] = alpha.copy()
        out[q] = {k: v for k, v in cov.items() if float(v.max()) > 1e-6}
    return out


def read_fo4_world_land_layers(
    plugin_path: str,
    world_edid: str = "Commonwealth",
    cells: Optional[Set[Tuple[int, int]]] = None,
) -> Tuple[Dict[Tuple[int, int], Dict[str, np.ndarray]], Counter]:
    """Read FO4 `LAND` texture layers for `cells` (or all cells when `None`), returning
    `(fo4_quad_layers[(fqx, fqy)], quadrant_use_counter)`."""
    own_plugin = os.path.basename(plugin_path)
    quad_layers: Dict[Tuple[int, int], Dict[str, np.ndarray]] = {}
    use_counts: Counter = Counter()

    with fo4land.Plugin(plugin_path) as p:
        masters = p.masters()
        wrld_hit = p.find_world(world_edid)
        if wrld_hit is None:
            raise ValueError(f"Worldspace {world_edid!r} not found in {plugin_path}")
        _wfid, g_start, g_end, _wsubs = wrld_hit
        default_key = canonical_ltex_key(0, masters, own_plugin)

        def walk_cell_children(c_start: int, c_end: int, cx: int, cy: int) -> None:
            q = c_start
            while q < c_end:
                sig = bytes(p.buf[q : q + 4])
                sz = struct.unpack_from("<I", p.buf, q + 4)[0]
                if sig == b"GRUP":
                    walk_cell_children(q + 24, q + sz, cx, cy)
                    q += sz
                elif sig == b"LAND":
                    subs = list(fo4land.iter_subrecords(fo4land.record_data(p.buf, q)))
                    # Count raw BTXT + ATXT appearances for world-wide ranking
                    btxt_seen: Dict[int, str] = {0: default_key, 1: default_key, 2: default_key, 3: default_key}
                    for s, d in subs:
                        if s == b"BTXT" and len(d) >= 5:
                            lfid, qidx = struct.unpack_from("<IB", d)
                            if qidx < 4:
                                btxt_seen[qidx] = canonical_ltex_key(lfid, masters, own_plugin)
                        elif s == b"ATXT" and len(d) >= 5:
                            lfid, qidx = struct.unpack_from("<IB", d)
                            if qidx < 4:
                                use_counts[canonical_ltex_key(lfid, masters, own_plugin)] += 1
                    for qidx in range(4):
                        use_counts[btxt_seen[qidx]] += 1

                    if cells is not None:
                        parsed = parse_fo4_land_layers(subs, masters, own_plugin)
                        for qidx, cov in parsed.items():
                            fqx = cx * 2 + (qidx & 1)
                            fqy = cy * 2 + ((qidx >> 1) & 1)
                            quad_layers[(fqx, fqy)] = cov
                    return
                else:
                    q += 24 + sz

        def walk_wrld(start: int, end: int) -> None:
            q = start
            while q < end:
                sig = bytes(p.buf[q : q + 4])
                sz = struct.unpack_from("<I", p.buf, q + 4)[0]
                if sig == b"GRUP":
                    gtype = struct.unpack_from("<I", p.buf, q + 12)[0]
                    if gtype in (4, 5):
                        walk_wrld(q + 24, q + sz)
                    q += sz
                elif sig == b"CELL":
                    fl, cfid = struct.unpack_from("<II", p.buf, q + 8)
                    nxt = q + 24 + sz
                    if not (fl & 0x400):
                        subs = list(fo4land.iter_subrecords(fo4land.record_data(p.buf, q)))
                        cxy = next((struct.unpack_from("<2i", d) for s, d in subs if s == b"XCLC"), None)
                        if cxy is not None and (cells is None or cxy in cells):
                            if nxt < end and bytes(p.buf[nxt : nxt + 4]) == b"GRUP":
                                gsz, glbl, gtype = struct.unpack_from("<I4sI", p.buf, nxt + 4)
                                if gtype == 6 and struct.unpack("<I", glbl)[0] == cfid:
                                    walk_cell_children(nxt + 24, nxt + gsz, cxy[0], cxy[1])
                                    q = nxt + gsz
                                    continue
                        elif cxy is not None and cells is not None and cxy not in cells:
                            # Skip cell children group without reading
                            if nxt < end and bytes(p.buf[nxt : nxt + 4]) == b"GRUP":
                                gsz, glbl, gtype = struct.unpack_from("<I4sI", p.buf, nxt + 4)
                                if gtype == 6 and struct.unpack("<I", glbl)[0] == cfid:
                                    q = nxt + gsz
                                    continue
                    q = nxt
                else:
                    q += 24 + sz

        walk_wrld(g_start, g_end)
    return quad_layers, use_counts


def rank_world_ltex_top_k(plugin_path: str, world_edid: str = "Commonwealth", top_k: int = 40) -> List[Tuple[str, int]]:
    """Return deterministic `[(ltex_key, quadrant_count), ...]` top `K` `LTEX` entries across `world_edid`."""
    _layers, counts = read_fo4_world_land_layers(plugin_path, world_edid=world_edid, cells=None)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked[: int(top_k)]


def resolve_fo4_ltex_textures(
    plugin_path: str,
    ltex_keys: Sequence[str],
    material_archives: Sequence[Any] = (),
) -> Dict[str, Dict[str, Any]]:
    """Resolve each FO4 `ltex_key` (`Plugin.esm:XXXXXX`) to `{'edid', 'diffuse', 'normal', 'spec', 'smoothness', 'spec_mult'}`."""
    own_plugin = os.path.basename(plugin_path)
    ltex_recs: Dict[str, Dict[str, Any]] = {}
    txst_recs: Dict[int, Dict[str, str]] = {}

    with fo4land.Plugin(plugin_path) as p:
        masters = p.masters()
        lg = p.top_group(b"LTEX")
        if lg is not None:
            for it in fo4land.iter_items(p.buf, lg[0], lg[1]):
                if it[0] == b"LTEX":
                    subs = dict(fo4land.iter_subrecords(fo4land.record_data(p.buf, it[1])))
                    key = canonical_ltex_key(it[3], masters, own_plugin)
                    ltex_recs[key.lower()] = {
                        "key": key,
                        "edid": fo4land.zstring(subs.get(b"EDID", b"")),
                        "tnam": struct.unpack_from("<I", subs[b"TNAM"])[0] & 0xFFFFFF if b"TNAM" in subs else None,
                    }
        tg_grp = p.top_group(b"TXST")
        if tg_grp is not None:
            for it in fo4land.iter_items(p.buf, tg_grp[0], tg_grp[1]):
                if it[0] == b"TXST":
                    subs = dict(fo4land.iter_subrecords(fo4land.record_data(p.buf, it[1])))
                    txst_recs[it[3] & 0xFFFFFF] = {
                        "edid": fo4land.zstring(subs.get(b"EDID", b"")),
                        "tx00": fo4land.zstring(subs[b"TX00"]) if b"TX00" in subs else "",
                        "tx01": fo4land.zstring(subs[b"TX01"]) if b"TX01" in subs else "",
                        "tx07": fo4land.zstring(subs[b"TX07"]) if b"TX07" in subs else "",
                        "mnam": fo4land.zstring(subs[b"MNAM"]) if b"MNAM" in subs else "",
                    }

    out: Dict[str, Dict[str, Any]] = {}
    for k in ltex_keys:
        if k.endswith(":000000"):
            out[k] = {
                "edid": "LDefaultDirt000000",
                "diffuse": DEFAULT_FO4_DIRT_TEXTURES[0],
                "normal": DEFAULT_FO4_DIRT_TEXTURES[1],
                "spec": DEFAULT_FO4_DIRT_TEXTURES[2],
                "smoothness": 1.0,
                "spec_mult": 1.0,
            }
            continue
        rec = ltex_recs.get(k.lower())
        if rec is None:
            raise KeyError(f"LTEX {k} not found in {plugin_path}")
        tx = txst_recs.get(rec["tnam"], {}) if rec["tnam"] is not None else {}
        diff, norm, spec = tx.get("tx00", ""), tx.get("tx01", ""), tx.get("tx07", "")
        smoothness, spec_mult = 1.0, 1.0
        if not diff and tx.get("mnam"):
            rel = tx["mnam"].replace("\\", "/").lstrip("/")
            if not rel.lower().startswith("materials/"):
                rel = "materials/" + rel
            for arc in material_archives:
                idx = arc.find(rel)
                if idx is not None:
                    bg = cm.parse_bgsm(arc.read(idx))
                    diff, norm, spec = bg.diffuse, bg.normal, bg.smooth_spec
                    smoothness, spec_mult = float(bg.smoothness), float(bg.spec_mult)
                    break
        if not diff:
            diff, norm, spec = DEFAULT_FO4_DIRT_TEXTURES
        out[k] = {
            "edid": rec["edid"] or f"LTEX_{k.split(':')[-1]}",
            "diffuse": diff,
            "normal": norm,
            "spec": spec,
            "smoothness": smoothness,
            "spec_mult": spec_mult,
        }
    return out


def _remapped_res_id(old_id: str, name: str) -> str:
    parts = old_id.split(":")
    tag = f"{zlib.crc32((name + '|' + old_id).encode('utf-8')) & 0xFFFFFFFF:08X}"
    if len(parts) == 4 and parts[0] == "res":
        return f"res:{tag}:{parts[2]}:{parts[3]}"
    return f"res:{tag}:0005E661:A06346EA"


def load_terrain_mat_template(content_resources_zip: str) -> Dict[str, Any]:
    with zipfile.ZipFile(content_resources_zip) as zf:
        return json.loads(zf.read(TERRAIN_TEMPLATE_PATH).decode("utf-8"))


def build_terrain_mat(
    template: Mapping[str, Any],
    name: str,
    color_tex: str,
    normal_tex: str,
    rough_tex: str,
) -> Dict[str, Any]:
    """Clone `DirtFootprints01.mat` (`Terrain1Layer.mat`) for `name` with converted PBR texture paths."""
    mat = json.loads(json.dumps(template))
    defined_ids = {obj["ID"] for obj in mat.get("Objects", []) if "ID" in obj}
    remap = {oid: _remapped_res_id(oid, name) for oid in defined_ids}

    c_norm = color_tex.replace("/", "\\")
    n_norm = normal_tex.replace("/", "\\")
    r_norm = rough_tex.replace("/", "\\")
    if not c_norm.lower().startswith("textures\\"):
        c_norm = "textures\\" + c_norm.lstrip("\\")
    if not n_norm.lower().startswith("textures\\"):
        n_norm = "textures\\" + n_norm.lstrip("\\")
    if not r_norm.lower().startswith("textures\\"):
        r_norm = "textures\\" + r_norm.lstrip("\\")

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            for k, v in list(node.items()):
                if k == "Parent":
                    continue
                node[k] = walk(v)
            if node.get("Type") == "BSComponentDB::CTName" and "Name" in node.get("Data", {}):
                node["Data"]["Name"] = str(node["Data"]["Name"]).replace("DirtFootprints01", name)
            return node
        if isinstance(node, list):
            return [walk(x) for x in node]
        if isinstance(node, str):
            return remap.get(node, node)
        return node

    mat = walk(mat)
    for obj in mat.get("Objects", []):
        comps = obj.get("Components", [])
        if any(c.get("Type") == "BSMaterial::MRTextureFile" for c in comps):
            kept = []
            for c in comps:
                if c.get("Type") != "BSMaterial::MRTextureFile":
                    kept.append(c)
                    continue
                idx = c.get("Index")
                if idx == 0:
                    c["Data"]["FileName"] = c_norm
                    kept.append(c)
                elif idx == 1:
                    c["Data"]["FileName"] = n_norm
                    kept.append(c)
                elif idx == 3:
                    c["Data"]["FileName"] = r_norm
                    kept.append(c)
                # Drop template-specific Index 5 (_ao) and Index 6 (_height)
            obj["Components"] = kept

    layer1 = mat.get("Summary", {}).get("Layer1", {})
    tex_summary = layer1.get("Textures", {})
    if "Albedo" in tex_summary:
        tex_summary["Albedo"]["File"] = c_norm
        tex_summary["Albedo"]["UseReplacement"] = False
    if "Normal" in tex_summary:
        tex_summary["Normal"]["File"] = n_norm
        tex_summary["Normal"]["UseReplacement"] = False
    if "Roughness" in tex_summary:
        tex_summary["Roughness"]["File"] = r_norm
        tex_summary["Roughness"]["UseReplacement"] = False
    if "AmbientOcclusion" in tex_summary:
        tex_summary["AmbientOcclusion"] = {
            "Replacement": {"w": 1, "x": 1, "y": 1, "z": 1},
            "TextureResolutionHint": "Tiling",
            "UseReplacement": True,
        }
    if "Height" in tex_summary:
        tex_summary["Height"] = {
            "Replacement": {"w": 1, "x": 0.5, "y": 0.5, "z": 0.5},
            "TextureResolutionHint": "Tiling",
            "UseReplacement": True,
        }
    return mat


def _sample_fo4_quadrant_coverages(
    fo4_quad_layers: Mapping[Tuple[int, int], Mapping[str, np.ndarray]],
    xu_grid: np.ndarray,
    yu_grid: np.ndarray,
    default_key: str,
) -> Dict[str, np.ndarray]:
    """Bilinearly sample FO4 `LAND` fractional coverages onto a `[64, 64]` coordinate grid in FO4 units."""
    fqx = np.floor(xu_grid / FO4_QUAD_UNITS).astype(np.int32)
    fqy = np.floor(yu_grid / FO4_QUAD_UNITS).astype(np.int32)
    u = np.clip((xu_grid - fqx * FO4_QUAD_UNITS) / FO4_VERT_STEP_UNITS, 0.0, 16.0)
    v = np.clip((yu_grid - fqy * FO4_QUAD_UNITS) / FO4_VERT_STEP_UNITS, 0.0, 16.0)
    c0 = np.minimum(np.floor(u).astype(np.int32), 15)
    r0 = np.minimum(np.floor(v).astype(np.int32), 15)
    fc = (u - c0).astype(np.float32)
    fr = (v - r0).astype(np.float32)

    distinct_fqs = {(int(qx), int(qy)) for qx, qy in zip(fqx.ravel(), fqy.ravel())}
    out: Dict[str, np.ndarray] = {}
    for qx_i, qy_i in distinct_fqs:
        mask = (fqx == qx_i) & (fqy == qy_i)
        layers = fo4_quad_layers.get((qx_i, qy_i))
        if not layers:
            arr = out.setdefault(default_key, np.zeros(xu_grid.shape, dtype=np.float32))
            arr[mask] += 1.0
            continue
        rr = r0[mask]
        cc = c0[mask]
        frc = fr[mask]
        fcc = fc[mask]
        for lkey, grid17 in layers.items():
            v00 = grid17[rr, cc]
            v01 = grid17[rr, cc + 1]
            v10 = grid17[rr + 1, cc]
            v11 = grid17[rr + 1, cc + 1]
            interp = (1.0 - frc) * ((1.0 - fcc) * v00 + fcc * v01) + frc * ((1.0 - fcc) * v10 + fcc * v11)
            arr = out.setdefault(lkey, np.zeros(xu_grid.shape, dtype=np.float32))
            arr[mask] += interp
    return out


def encode_btd_ltex_window(
    fo4_quad_layers: Mapping[Tuple[int, int], Mapping[str, np.ndarray]],
    *,
    n_sf_cells: int,
    origin_cw_m: Tuple[float, float] = (0.0, 0.0),
    ltex_mapping: Mapping[str, int],
    default_fo4_key: str = "Fallout4.esm:000000",
    fallback_sf_fid: int = PLAIN_GROUND_SF_FID,
) -> Tuple[List[int], np.ndarray, np.ndarray, Dict[str, Any]]:
    """Encode `(ltex_table, quad_map, weights, stats)` for an `n_sf_cells x n_sf_cells` BTD tile."""
    # Build deterministic LTEX table: all mapped FormIDs in ltex_mapping order + fallback_sf_fid
    ordered_fids: List[int] = []
    seen_fids = set()
    for fid in list(ltex_mapping.values()) + [int(fallback_sf_fid)]:
        if int(fid) not in seen_fids:
            ordered_fids.append(int(fid))
            seen_fids.add(int(fid))
    n_table = len(ordered_fids)
    if n_table > 255:
        raise ValueError(f"BTD quad_map uint8 supports at most 255 LTEX entries, got {n_table}")
    byte_of_fid = {fid: n_table - idx for idx, fid in enumerate(ordered_fids)}
    map_ci = {k.lower(): int(v) for k, v in ltex_mapping.items()}

    nq = n_sf_cells * 2
    ns = n_sf_cells * 128
    quad_map = np.zeros((nq, nq, 8), dtype=np.uint8)
    weights = np.zeros((ns, ns), dtype=np.uint16)

    g_origin_m = tg.grid_origin(n_sf_cells)
    step_m = tg.SF_CELL_M / 128.0
    xs_local_m = g_origin_m + np.arange(ns, dtype=np.float64) * step_m
    ys_local_m = g_origin_m + np.arange(ns, dtype=np.float64) * step_m
    xs_u = (xs_local_m + float(origin_cw_m[0])) * tg.UNITS_PER_METRE
    ys_u = (ys_local_m + float(origin_cw_m[1])) * tg.UNITS_PER_METRE

    quad_gt_dominant: List[List[str]] = [["" for _ in range(nq)] for _ in range(nq)]
    mapped_dom_hits = 0

    for qy in range(nq):
        sy0, sy1 = qy * 64, (qy + 1) * 64
        yy_u = ys_u[sy0:sy1, None]
        for qx in range(nq):
            sx0, sx1 = qx * 64, (qx + 1) * 64
            xx_u = xs_u[None, sx0:sx1]
            xu_grid, yu_grid = np.broadcast_arrays(xx_u, yy_u)
            cov_by_fo4 = _sample_fo4_quadrant_coverages(fo4_quad_layers, xu_grid, yu_grid, default_fo4_key)

            # Ground-truth FO4 dominant LTEX across all FO4 LTEXs (unmapped included!)
            gt_key = max(cov_by_fo4.items(), key=lambda kv: (float(kv[1].mean()), kv[0]))[0]
            quad_gt_dominant[qy][qx] = gt_key
            if gt_key.lower() in map_ci:
                mapped_dom_hits += 1

            # Project coverages onto Starfield LTEX FormIDs
            cov_by_sf: Dict[int, np.ndarray] = {}
            for fkey, carr in cov_by_fo4.items():
                sf_fid = map_ci.get(fkey.lower(), int(fallback_sf_fid))
                if sf_fid in cov_by_sf:
                    cov_by_sf[sf_fid] = cov_by_sf[sf_fid] + carr
                else:
                    cov_by_sf[sf_fid] = carr.copy()

            # Select up to 6 layers ranked by quadrant mean coverage descending:
            # selected[0] = base layer t[0], selected[1..5] = overlay layers t[1]..t[5]
            ranked = sorted(cov_by_sf.items(), key=lambda kv: (-float(kv[1].mean()), kv[0]))[:6]
            sel_fids = [fid for fid, _ in ranked]
            sel_covs = np.stack([arr for _, arr in ranked], axis=0)  # [K, 64, 64]
            total_cov = np.maximum(sel_covs.sum(axis=0, keepdims=True), 1e-6)
            sel_covs = sel_covs / total_cov

            # Encode quad_map[qy, qx, 0..7]:
            # i = 0..4 sets t[5 - i]; last valid non-zero byte at i = 5 sets base t[0]!
            qbytes = np.zeros(8, dtype=np.uint8)
            qbytes[5] = byte_of_fid[sel_fids[0]]
            for k in range(1, len(sel_fids)):
                # overlay t[k] lives at slot i = 5 - k
                qbytes[5 - k] = byte_of_fid[sel_fids[k]]
            quad_map[qy, qx, :] = qbytes

            # Sequential 3-bit inverse lerp from k = K-1 down to 1:
            k_count = len(sel_fids)
            if k_count > 1:
                w_u16 = np.zeros((64, 64), dtype=np.uint16)
                rem = np.ones((64, 64), dtype=np.float32)
                for k in range(k_count - 1, 0, -1):
                    target = sel_covs[k]
                    ratio = np.where(rem > 1e-5, target / np.maximum(rem, 1e-5), 0.0)
                    a_k = np.clip(np.rint(ratio * 7.0), 0.0, 7.0).astype(np.uint16)
                    w_u16 |= a_k << np.uint16((k - 1) * 3)
                    rem = rem * (1.0 - a_k.astype(np.float32) / 7.0)
                weights[sy0:sy1, sx0:sx1] = w_u16

    stats = {
        "quadrants_total": nq * nq,
        "gt_dominant_in_mapped_set": mapped_dom_hits,
        "gt_dominant_mapped_ratio": round(mapped_dom_hits / float(nq * nq), 5),
        "quad_gt_dominant": quad_gt_dominant,
    }
    return ordered_fids, quad_map, weights, stats


def decode_btd_quadrant_layers(btd_obj: btd.Btd, qy: int, qx: int) -> Dict[str, Any]:
    """Decode one `64 x 64` BTD quadrant using `fo76utils` `getCellTextureSet` + sequential 3-bit alpha blending."""
    nlt = len(btd_obj.ltex)
    qrow = btd_obj.quad_map[qy, qx]
    t_slots: List[Optional[int]] = [None] * 6
    default_fid: Optional[int] = None
    for i in range(8):
        bval = int(qrow[i])
        if 0 < bval <= nlt:
            fid = int(btd_obj.ltex[nlt - bval])
            default_fid = fid
            if i < 5:
                t_slots[5 - i] = fid
    t_slots[0] = default_fid
    if t_slots[0] is None:
        raise ValueError(f"Quadrant ({qy}, {qx}) has no valid base LTEX byte in {list(qrow)}")

    sy0, sy1 = qy * 64, (qy + 1) * 64
    sx0, sx1 = qx * 64, (qx + 1) * 64
    w_block = btd_obj.weights[sy0:sy1, sx0:sx1]

    # Sequential blend from t[0] through t[5]
    blended: Dict[int, np.ndarray] = {t_slots[0]: np.ones((64, 64), dtype=np.float32)}
    for k in range(1, 6):
        fid_k = t_slots[k]
        if fid_k is None:
            continue
        alpha = ((w_block >> np.uint16((k - 1) * 3)) & np.uint16(7)).astype(np.float32) / 7.0
        inv = 1.0 - alpha
        for prev_fid in list(blended.keys()):
            blended[prev_fid] = blended[prev_fid] * inv
        if fid_k in blended:
            blended[fid_k] = blended[fid_k] + alpha
        else:
            blended[fid_k] = alpha

    mean_cov = {fid: float(arr.mean()) for fid, arr in blended.items()}
    dom_fid = max(mean_cov.items(), key=lambda kv: (kv[1], kv[0]))[0]
    return {
        "base_fid": t_slots[0],
        "slots": t_slots,
        "dominant_fid": dom_fid,
        "mean_coverage": mean_cov,
    }


def verify_btd_against_fo4_dominants(
    btd_obj: btd.Btd,
    quad_gt_dominant: Sequence[Sequence[str]],
    ltex_mapping: Mapping[str, int],
) -> Dict[str, Any]:
    """Compare decoded `BTD` dominant `LTEX` per quadrant against FO4's ground-truth dominant `LTEX`."""
    inv_map: Dict[int, str] = {}
    for fkey, sf_fid in ltex_mapping.items():
        if int(sf_fid) in inv_map:
            raise ValueError(f"Non-bijective ltex_mapping on Starfield FormID 0x{int(sf_fid):08X}")
        inv_map[int(sf_fid)] = fkey.lower()

    nq_y = btd_obj.ncy * 2
    nq_x = btd_obj.ncx * 2
    matches = 0
    base_matches = 0
    used_fids = set()
    for qy in range(nq_y):
        for qx in range(nq_x):
            dec = decode_btd_quadrant_layers(btd_obj, qy, qx)
            for s in dec["slots"]:
                if s is not None:
                    used_fids.add(int(s))
            gt_low = str(quad_gt_dominant[qy][qx]).lower()
            if inv_map.get(int(dec["dominant_fid"])) == gt_low:
                matches += 1
            if inv_map.get(int(dec["base_fid"])) == gt_low:
                base_matches += 1

    total = nq_y * nq_x
    return {
        "ltex_table_size": len(btd_obj.ltex),
        "distinct_ltex_referenced_in_quads": len(used_fids),
        "quadrants_total": total,
        "dominant_blended_matches": matches,
        "dominant_blended_match_ratio": round(matches / float(total), 5),
        "base_slot_matches": base_matches,
        "base_slot_match_ratio": round(base_matches / float(total), 5),
    }
