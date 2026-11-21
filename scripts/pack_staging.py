"""Pack a Starfield asset staging folder into plugin-named BA2 archives (<PluginStem> - Main.ba2 and
<PluginStem> - Textures.ba2), splitting texture archives strictly below the 4 GiB BA2 limit with 42-byte full-master
companion plugins (<PluginStem>TexturesN.esm + <PluginStem>TexturesN - Textures.ba2, N = 2, 3, ...).

Refuses any output folder inside a Git worktree or inside a game installation directory (Rule R4).

Usage:
  python scripts/pack_staging.py --staging <dir> --plugin <Name>[.esm] --out <dir> --starfield <Starfield game dir>
                                 [--prev <prev port or batch stage>] [--pack-ratio <float>] [--log <pack.log>]
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import time
from typing import Callable, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (os.path.join(ROOT, "src"), HERE, os.path.join(HERE, "terrain")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fo4sf import pipeline  # noqa: E402
import deploy_starfield  # noqa: E402
import vmad_patch  # noqa: E402

UINT32_MAX = 4_294_967_295          # 4 GiB - 1 B: hard 32-bit BA2 ceiling
ARCHIVE_LIMIT = 4095 * 2 ** 20      # 4,293,918,720 B (< UINT32_MAX), matching interior_batch's proven ceiling
ARCHIVE_WARN = 0.9
PARTS = "textures_parts.json"
PACK_ATTEMPTS = 3
ANIMATED_PEX = "FO4SF_AnimatedLoadDoor.pex"
DEFAULT_PLUGIN = "FO4Port.esm"


def normalize_plugin_name(plugin: str = DEFAULT_PLUGIN) -> Tuple[str, str]:
    """Return (plugin_esm, stem), e.g. 'FO4DLC' or 'FO4DLC.esm' -> ('FO4DLC.esm', 'FO4DLC')."""
    raw = (plugin or DEFAULT_PLUGIN).strip()
    if raw.lower().endswith((".esp", ".esl")):
        raise ValueError(f"plugin must be a full-master .esm (got {plugin!r})")
    stem = raw[:-4] if raw.lower().endswith(".esm") else raw
    if not re.fullmatch(r"[A-Za-z0-9_-]+", stem):
        raise ValueError(f"invalid plugin name: {plugin!r}")
    return f"{stem}.esm", stem


def main_archive_name(plugin: str = DEFAULT_PLUGIN) -> str:
    _, stem = normalize_plugin_name(plugin)
    return f"{stem} - Main.ba2"


def textures_archive_name(plugin: str = DEFAULT_PLUGIN) -> str:
    _, stem = normalize_plugin_name(plugin)
    return f"{stem} - Textures.ba2"


def companion_rx_for(plugin: str = DEFAULT_PLUGIN) -> re.Pattern:
    _, stem = normalize_plugin_name(plugin)
    return re.compile(rf"^{re.escape(stem)}Textures(\d+)( - Textures\.ba2|\.esm)$")


def part_names(k: int, plugin: str = DEFAULT_PLUGIN) -> Tuple[str, Optional[str]]:
    """(archive, companion plugin or None) of texture part k (0 = the plugin's own textures archive)."""
    _, stem = normalize_plugin_name(plugin)
    if k == 0:
        return f"{stem} - Textures.ba2", None
    n = k + 1
    return f"{stem}Textures{n} - Textures.ba2", f"{stem}Textures{n}.esm"


def companion_plugin_bytes() -> bytes:
    """Empty 42-byte full-master Starfield .esm (TES4 flags 0x1, form version 576, HEDR 0.96 / 0 / 0, no MAST)."""
    return vmad_patch.record_bytes(b"TES4", 0, 1, [(b"HEDR", struct.pack("<fII", 0.96, 0, 0))]).serialize()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _save_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


def _load_json(path: str):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def texture_sizes(work: str) -> Dict[str, int]:
    """{relative path under <work>/textures (forward slashes): bytes} sorted case-insensitively."""
    root = os.path.join(work, "textures")
    out: Dict[str, int] = {}
    if not os.path.isdir(root):
        return out
    for d, _dirs, files in os.walk(root):
        for f in files:
            p = os.path.join(d, f)
            out[os.path.relpath(p, root).replace("\\", "/")] = os.path.getsize(p)
    return dict(sorted(out.items(), key=lambda kv: kv[0].casefold()))


def plan_parts(sizes: Dict[str, int], cap: int, previous: Optional[Dict[str, int]] = None) -> List[List[str]]:
    """Split {path: bytes} into parts of at most cap loose bytes each (a file is never split): deterministic, greedy,
    preserving `previous` ({path: part index}) assignments while they fit, and dropping emptied parts."""
    previous = previous or {}
    parts: List[List[str]] = []
    used: List[int] = []
    paths = sorted(sizes, key=str.casefold)
    big = [p for p in paths if sizes[p] > cap]
    if big:
        raise ValueError(f"{len(big)} texture(s) larger than one archive part ({cap:,} bytes): {big[:3]}")
    rest = []
    for p in paths:
        k = previous.get(p)
        if isinstance(k, int) and k >= 0:
            while len(parts) <= k:
                parts.append([])
                used.append(0)
            if used[k] + sizes[p] <= cap:
                parts[k].append(p)
                used[k] += sizes[p]
                continue
        rest.append(p)
    for p in rest:
        k = next((i for i, u in enumerate(used) if u + sizes[p] <= cap), None)
        if k is None:
            parts.append([])
            used.append(0)
            k = len(parts) - 1
        parts[k].append(p)
        used[k] += sizes[p]
    return [sorted(p, key=str.casefold) for p in parts if p]


def pack_ratio(prev_result: Optional[dict], loose_total: Optional[int] = None, plugin: str = DEFAULT_PLUGIN) -> float:
    """Packed bytes per loose byte of the previous stage's texture archives (largest over parts), or 1.0."""
    parts = ((prev_result or {}).get("steps") or {}).get("pack", {}).get("parts") or (prev_result or {}).get("parts") or []
    ratios = [p["bytes"] / p["loose_bytes"] for p in parts if p.get("loose_bytes") and p.get("bytes")]
    if ratios:
        return max(ratios)
    tex_name = textures_archive_name(plugin)
    pack_step = ((prev_result or {}).get("steps") or {}).get("pack") or (prev_result or {})
    legacy = (pack_step.get("bytes") or {}).get(tex_name)
    if legacy and loose_total:
        return min(1.0, legacy / loose_total)
    return 1.0


def measured_ratio(recorded: List[dict]) -> Optional[float]:
    ratios = [p["bytes"] / p["loose_bytes"] for p in recorded if p["loose_bytes"]]
    return max(ratios) if ratios else None


def link_tree(work: str, rels: List[str], dst: str) -> int:
    """Hard-link (or copy on cross-volume fallback) <work>/textures/<rel> into <dst>/textures/<rel>. Returns copies."""
    copies = 0
    for rel in rels:
        src = os.path.join(work, "textures", *rel.split("/"))
        to = os.path.join(dst, "textures", *rel.split("/"))
        os.makedirs(os.path.dirname(to), exist_ok=True)
        try:
            os.link(src, to)
        except OSError:
            shutil.copyfile(src, to)
            copies += 1
    return copies


def archive_check(sizes: Dict[str, int], limit: int = ARCHIVE_LIMIT, warn: float = ARCHIVE_WARN) -> dict:
    eff_limit = min(limit, UINT32_MAX)
    over = sorted(n for n, s in sizes.items() if s >= eff_limit)
    near = sorted(n for n, s in sizes.items() if warn * eff_limit <= s < eff_limit)
    out = {"bytes": sizes, "limit": eff_limit, "pass": not over, "near_limit": near}
    if over:
        out["problem"] = (
            f"over {eff_limit:,} bytes: {', '.join(over)} (a texture part packed worse than planned "
            f"even after replanning: see steps.pack.attempts, or plan tighter with --pack-ratio)"
        )
    return out


def install_set(port: str, plugin: str = DEFAULT_PLUGIN) -> dict:
    """{"files": [...], "plugins_txt": [...]} for a packed port directory."""
    if not os.path.isdir(port):
        return {"files": [], "plugins_txt": []}
    plugin_esm, stem = normalize_plugin_name(plugin)
    main_ba2 = main_archive_name(plugin_esm)
    tex_ba2 = textures_archive_name(plugin_esm)
    rx = companion_rx_for(plugin_esm)
    have = set(os.listdir(port))
    files = [n for n in (plugin_esm, main_ba2, tex_ba2) if n in have]
    plugins = [plugin_esm] if plugin_esm in have else []
    nums = sorted({int(m.group(1)) for n in have for m in [rx.match(n)] if m})
    for n in nums:
        comp_esm = f"{stem}Textures{n}.esm"
        comp_ba2 = f"{stem}Textures{n} - Textures.ba2"
        files += [x for x in (comp_esm, comp_ba2) if x in have]
        if comp_esm in have:
            plugins.append(comp_esm)
    return {"files": files, "plugins_txt": plugins}


def is_superseded(rel: str, plugin: str = DEFAULT_PLUGIN) -> bool:
    plugin_esm, _ = normalize_plugin_name(plugin)
    superseded = (f"port/{plugin_esm}", f"port/{main_archive_name(plugin_esm)}", f"port/{textures_archive_name(plugin_esm)}")
    rx = companion_rx_for(plugin_esm)
    return rel in superseded or (rel.startswith("port/") and rel.count("/") == 1 and bool(rx.match(rel[5:])))


def superseded_files(stage: str, plugin: str = DEFAULT_PLUGIN) -> List[str]:
    port = os.path.join(stage, "port")
    have = os.listdir(port) if os.path.isdir(port) else []
    return sorted("port/" + n for n in have if is_superseded("port/" + n, plugin=plugin))


def pack_staging(
    staging: str,
    out_dir: str,
    starfield: str,
    plugin: str = DEFAULT_PLUGIN,
    prev_port: Optional[str] = None,
    prev_result: Optional[dict] = None,
    pack_ratio_override: Optional[float] = None,
    animated_pex: str = "",
    animated_pex_sha256: str = "",
    log_path: str = "",
    scratch_parent: str = "",
    limit: int = ARCHIVE_LIMIT,
    warn: float = ARCHIVE_WARN,
    build_archive_fn: Optional[Callable] = None,
) -> dict:
    """Pack `staging` into `out_dir` named after `plugin`, splitting textures under `warn * limit` (< 4 GiB)."""
    pipeline.refuse_unsafe_output_dir(out_dir, "--out")
    if scratch_parent:
        pipeline.refuse_unsafe_output_dir(scratch_parent, "--out")
    plugin_esm, _stem = normalize_plugin_name(plugin)
    main_ba2 = main_archive_name(plugin_esm)
    run_archive = build_archive_fn or deploy_starfield.build_archive
    os.makedirs(out_dir, exist_ok=True)

    t = time.time()
    packer = argparse.Namespace(starfield=starfield, staging=staging)
    main_dirs = [d for d in deploy_starfield.MAIN_DIRS if os.path.isdir(os.path.join(staging, d))]
    scripts_dir = os.path.join(staging, "scripts")
    if animated_pex:
        if os.path.exists(scripts_dir):
            raise ValueError(f"{scripts_dir} exists: the work staging must not hold scripts of its own")
        os.makedirs(scripts_dir)
        staged_pex = os.path.join(scripts_dir, ANIMATED_PEX)
        shutil.copyfile(animated_pex, staged_pex)
        if animated_pex_sha256 and sha256_file(staged_pex) != animated_pex_sha256:
            shutil.rmtree(scripts_dir, ignore_errors=True)
            raise ValueError(
                f"{animated_pex} changed since it was pinned (sha256 {animated_pex_sha256[:12]}): refusing to pack it"
            )
        main_dirs.append("scripts")
    try:
        run_archive(packer, os.path.join(out_dir, main_ba2), main_dirs, "General")
    finally:
        if animated_pex:
            shutil.rmtree(scripts_dir, ignore_errors=True)

    sizes = texture_sizes(staging)
    previous: Dict[str, int] = {}
    if prev_port and os.path.isfile(os.path.join(prev_port, PARTS)):
        previous = _load_json(os.path.join(prev_port, PARTS)).get("assignment") or {}
    ratio = pack_ratio_override or pack_ratio(prev_result, sum(sizes.values()), plugin=plugin_esm)
    ratio_source = "--pack-ratio" if pack_ratio_override else ("prev" if prev_result else "default")
    eff_limit = min(limit, UINT32_MAX)
    parts_scratch_base = os.path.join(scratch_parent or out_dir, "pack_parts")
    copies, attempts, packed = 0, [], {}
    while True:
        cap = int(warn * eff_limit / ratio)
        try:
            parts = plan_parts(sizes, cap, previous) or [[]]
        except ValueError as e:
            if not attempts:
                raise
            raise ValueError(f"{e} after replanning at ratio {ratio:.3f} (attempts: {attempts})")
        recorded = []
        for k, rels in enumerate(parts):
            archive, comp_plugin = part_names(k, plugin_esm)
            if packed.get(k) != tuple(rels):
                if len(parts) == 1:
                    run_archive(packer, os.path.join(out_dir, archive), ["textures"], "DDS")
                else:
                    tree_root = os.path.join(parts_scratch_base, str(k))
                    shutil.rmtree(tree_root, ignore_errors=True)
                    copies += link_tree(staging, rels, tree_root)
                    run_archive(
                        argparse.Namespace(starfield=starfield, staging=tree_root),
                        os.path.join(out_dir, archive),
                        ["textures"],
                        "DDS",
                    )
                    shutil.rmtree(tree_root, ignore_errors=True)
                packed[k] = tuple(rels)
            if comp_plugin:
                with open(os.path.join(out_dir, comp_plugin), "wb") as f:
                    f.write(companion_plugin_bytes())
            recorded.append({
                "archive": archive,
                "plugin": comp_plugin,
                "files": len(rels),
                "loose_bytes": sum(sizes[r] for r in rels),
                "bytes": os.path.getsize(os.path.join(out_dir, archive)),
            })
        over = [p["archive"] for p in recorded if p["bytes"] >= eff_limit]
        attempts.append({"ratio": ratio, "cap_loose_bytes": cap, "parts": len(parts), "over": over})
        if not over or len(attempts) >= PACK_ATTEMPTS:
            break
        m_ratio = measured_ratio(recorded)
        ratio = max(m_ratio, ratio) if m_ratio is not None else ratio
        if log_path:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"pack: {', '.join(over)} over the limit at ratio {attempts[-1]['ratio']:.3f}; "
                        f"replanning at {ratio:.3f}\n")

    for k in sorted(packed):
        if k >= len(parts):
            for n in part_names(k, plugin_esm):
                if n and os.path.isfile(os.path.join(out_dir, n)):
                    os.remove(os.path.join(out_dir, n))
    shutil.rmtree(parts_scratch_base, ignore_errors=True)

    files = [main_ba2] + [n for p in recorded for n in (p["archive"], p["plugin"]) if n]
    assignment = {r: k for k, rels in enumerate(parts) for r in rels}
    _save_json(os.path.join(out_dir, PARTS), {
        "schema_version": 1,
        "cap_loose_bytes": cap,
        "ratio": ratio,
        "parts": [p["archive"] for p in recorded],
        "assignment": assignment,
    })
    out = archive_check({n: os.path.getsize(os.path.join(out_dir, n)) for n in files}, limit=eff_limit, warn=warn)
    out["sha256"] = {n: sha256_file(os.path.join(out_dir, n)) for n in files}
    out.update({
        "parts": recorded,
        "ratio": ratio,
        "ratio_source": ratio_source,
        "cap_loose_bytes": cap,
        "attempts": attempts,
        "copies": copies,
        "moved": sum(1 for r, k in assignment.items() if r in previous and previous[r] != k),
        "seconds": round(time.time() - t, 1),
    })
    if log_path:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(
                f"pack: {len(parts)} texture part(s), cap {cap:,} loose bytes (ratio {ratio:.3f} from {ratio_source}, "
                f"{len(attempts)} attempt(s)), {out['moved']} file(s) moved from the previous batch's part, "
                f"{copies} copied where a hard link failed\n"
            )
    return out


def _resolve_prev(prev: str) -> Tuple[Optional[str], Optional[dict]]:
    if not prev:
        return None, None
    port_dir = os.path.join(prev, "port") if os.path.isdir(os.path.join(prev, "port")) else prev
    res = None
    for candidate in (os.path.join(prev, "result.json"), os.path.join(prev, "pack_result.json"),
                      os.path.join(os.path.dirname(os.path.abspath(prev)), "result.json")):
        if os.path.isfile(candidate):
            res = _load_json(candidate)
            break
    return port_dir, res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--staging", required=True, help="conversion staging folder containing meshes/materials/textures")
    ap.add_argument("--plugin", default=DEFAULT_PLUGIN, help="plugin name or stem (e.g. FO4DLC.esm, default FO4Port.esm)")
    ap.add_argument("--out", required=True, help="output directory outside Git worktrees and game folders")
    ap.add_argument("--starfield", required=True, help="Starfield game root containing Tools/Archive2/Archive2.exe")
    ap.add_argument("--prev", default="", help="optional previous pack/batch directory to preserve part assignments")
    ap.add_argument("--pack-ratio", type=float, default=None, help="optional packed/loose ratio override (> 0)")
    ap.add_argument("--log", default="", help="optional pack log file")
    a = ap.parse_args(argv)
    if a.pack_ratio is not None and a.pack_ratio <= 0:
        ap.error("--pack-ratio must be > 0")
    try:
        plugin_esm, _ = normalize_plugin_name(a.plugin)
        pipeline.refuse_unsafe_output_dir(a.out, "--out")
        prev_port, prev_res = _resolve_prev(a.prev)
        res = pack_staging(
            staging=a.staging,
            out_dir=a.out,
            starfield=a.starfield,
            plugin=plugin_esm,
            prev_port=prev_port,
            prev_result=prev_res,
            pack_ratio_override=a.pack_ratio,
            log_path=a.log,
        )
    except ValueError as e:
        sys.exit(f"pack_staging: {e}")
    _save_json(os.path.join(a.out, "pack_result.json"), {"plugin": plugin_esm, **res, "install": install_set(a.out, plugin_esm)})
    print(json.dumps({"plugin": plugin_esm, "pass": res["pass"], "parts": len(res["parts"]), "bytes": res["bytes"]}))
    return 0 if res["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
