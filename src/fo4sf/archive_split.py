"""Plan, build, and verify multi-archive BA2 splits for bundles approaching or exceeding Starfield's 4 GiB limit.

Starfield BA2 archives use unsigned 32-bit offsets/sizes in several engine paths and top out just below 4 GiB
(4,294,967,295 B; vanilla Starfield's own largest archives top out at 4,294,946,755 B and split into numbered parts
listed in Starfield.ini). Non-base plugins are NOT listed in Starfield.ini: instead, the engine automatically mounts
`<PluginStem> - Main.ba2` (GNRL) and `<PluginStem> - Textures.ba2` (DX10) for each active `.esm` in `Plugins.txt`.

Because a multi-plugin bundle (such as the 19/21-plugin Core Candidate) already activates multiple real `.esm` masters,
any `Data/` tree can be split deterministically across `<plugins[k]> - Main.ba2` (either by size budget or by owning
plugin/component) with zero `Starfield.ini` edits and full per-archive SHA-256 verification, install, and rollback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

MAX_BA2_BYTES = (4 * (1024 ** 3)) - 1  # 4,294,967,295 B (32-bit unsigned ceiling)
DEFAULT_MAX_ARCHIVE_BYTES = 3 * (1024 ** 3)  # 3,221,225,472 B (3.000 GiB default target per split archive)
BA2_V2_HEADER_BYTES = 32  # 24-byte BTDX prefix + 8-byte v2 extended header
BA2_GNRL_RECORD_BYTES = 36


@dataclass(frozen=True)
class DataResource:
    rel_posix: str          # relative to Data/, e.g. "meshes/fo4port/x.nif"
    size_bytes: int
    sha256: str = ""

    @property
    def data_key(self) -> str:
        return f"Data/{self.rel_posix}"

    @property
    def entry_overhead_bytes(self) -> int:
        win_rel = self.rel_posix.replace("/", "\\")
        return BA2_GNRL_RECORD_BYTES + 2 + len(win_rel.encode("utf-8"))

    @property
    def total_ba2_contribution(self) -> int:
        return self.entry_overhead_bytes + self.size_bytes

    @property
    def top_folder(self) -> str:
        return self.rel_posix.split("/", 1)[0].casefold()


@dataclass(frozen=True)
class ArchiveBucket:
    plugin: str
    archive_name: str
    resources: Tuple[DataResource, ...]

    @property
    def file_count(self) -> int:
        return len(self.resources)

    @property
    def raw_bytes(self) -> int:
        return sum(r.size_bytes for r in self.resources)

    @property
    def estimated_ba2_bytes(self) -> int:
        if not self.resources:
            return 0
        return BA2_V2_HEADER_BYTES + sum(r.total_ba2_contribution for r in self.resources)

    def input_digests(self) -> Dict[str, str]:
        return {r.data_key: r.sha256 for r in self.resources}


def plugin_main_archive_name(plugin_filename: str) -> str:
    stem, ext = os.path.splitext(plugin_filename.strip())
    if ext.lower() not in (".esm", ".esp", ".esl") or not stem:
        raise ValueError(f"invalid plugin filename for archive naming: {plugin_filename!r}")
    return f"{stem} - Main.ba2"


def read_held_off_plugins(starfield_dir: Optional[str]) -> set[str]:
    """Return casefolded plugin names listed under `"off"` in `<starfield_dir>/Data/FO4SF.toggle.json`."""
    if not starfield_dir:
        return set()
    cand_data = os.path.join(starfield_dir, "Data")
    toggle_path = (
        os.path.join(cand_data, "FO4SF.toggle.json")
        if os.path.isdir(cand_data)
        else os.path.join(starfield_dir, "FO4SF.toggle.json")
    )
    if not os.path.exists(toggle_path):
        return set()
    with open(toggle_path, encoding="utf-8") as fp:
        rec = json.load(fp)
    off = rec.get("off") if isinstance(rec, Mapping) else None
    if not isinstance(off, list) or not all(isinstance(x, str) and x.strip() for x in off):
        raise ValueError(f"{toggle_path}: 'off' must be a list of non-empty plugin names")
    return {x.strip().casefold() for x in off}


def refuse_held_carrier_buckets(
    buckets: Sequence[ArchiveBucket],
    held_off: Iterable[str] = (),
    starfield_dir: Optional[str] = None,
) -> None:
    """Refuse any split plan whose carrier plugin is held off in `Data/FO4SF.toggle.json` (`"off"` list)."""
    held_set = {str(p).strip().casefold() for p in (held_off or ()) if str(p).strip()}
    if starfield_dir:
        held_set |= read_held_off_plugins(starfield_dir)
    if not held_set:
        return
    held_stems = {os.path.splitext(p)[0].casefold() for p in held_set}
    bad: List[str] = []
    for b in buckets:
        p_cf = b.plugin.strip().casefold()
        arc_stem = b.archive_name[:-len(" - Main.ba2")].casefold() if b.archive_name.lower().endswith(" - main.ba2") else ""
        if p_cf in held_set or (arc_stem and arc_stem in held_stems):
            if b.plugin not in bad:
                bad.append(b.plugin)
    if bad:
        raise ValueError(
            f"split archive carrier plugin(s) held off in FO4SF.toggle.json: {', '.join(bad)}; "
            f"run plugin_toggle.py on before using split archives"
        )


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_data_resources(exp_dir: str, precomputed_inputs: Optional[Mapping[str, str]] = None) -> List[DataResource]:
    """Scan `<exp_dir>/Data` into sorted `DataResource` records (reusing SHA-256s from `precomputed_inputs` when given)."""
    data_root = os.path.join(exp_dir, "Data")
    if not os.path.isdir(data_root):
        return []
    out: List[DataResource] = []
    for root, dirs, files in os.walk(data_root):
        dirs.sort()
        rel_dir = os.path.relpath(root, data_root).replace("\\", "/")
        if rel_dir == ".":
            rel_dir = ""
        if not rel_dir and files:
            raise ValueError(f"cannot pack root-level Data files: {sorted(files)}")
        for fn in sorted(files):
            full = os.path.join(root, fn)
            rel_posix = f"{rel_dir}/{fn}" if rel_dir else fn
            key = f"Data/{rel_posix}"
            digest = precomputed_inputs[key] if (precomputed_inputs and key in precomputed_inputs) else sha256_file(full)
            out.append(DataResource(rel_posix=rel_posix, size_bytes=os.path.getsize(full), sha256=digest))
    return out


def _validate_plugins_and_budget(plugins: Sequence[str], max_archive_bytes: int) -> List[str]:
    cleaned = [p.strip() for p in plugins if p and p.strip()]
    if not cleaned:
        raise ValueError("at least one active plugin is required to name BA2 archives")
    if len({p.casefold() for p in cleaned}) != len(cleaned):
        raise ValueError(f"duplicate plugins in archive carrier list: {cleaned}")
    if max_archive_bytes <= BA2_V2_HEADER_BYTES or max_archive_bytes > MAX_BA2_BYTES:
        raise ValueError(f"max_archive_bytes must be in (32, {MAX_BA2_BYTES}], got {max_archive_bytes}")
    return cleaned


def _pack_group_into_chunks(items: Sequence[DataResource], max_archive_bytes: int) -> List[List[DataResource]]:
    chunks: List[List[DataResource]] = []
    cur: List[DataResource] = []
    cur_bytes = BA2_V2_HEADER_BYTES
    for r in items:
        single = BA2_V2_HEADER_BYTES + r.total_ba2_contribution
        if single > max_archive_bytes:
            raise ValueError(
                f"single resource {r.data_key} requires {single} B, exceeding max_archive_bytes={max_archive_bytes}"
            )
        if cur and (cur_bytes + r.total_ba2_contribution > max_archive_bytes):
            chunks.append(cur)
            cur = [r]
            cur_bytes = single
        else:
            cur.append(r)
            cur_bytes += r.total_ba2_contribution
    if cur:
        chunks.append(cur)
    return chunks


def plan_split_by_size(
    resources: Sequence[DataResource],
    plugins: Sequence[str],
    max_archive_bytes: int = DEFAULT_MAX_ARCHIVE_BYTES,
    *,
    held_off: Iterable[str] = (),
    starfield_dir: Optional[str] = None,
) -> List[ArchiveBucket]:
    """Deterministically split `resources` across `<plugins[k]> - Main.ba2` archives so each is <= `max_archive_bytes`.

    Keeps non-texture directories (`meshes`, `geometries`, `Terrain`, `materials`, `Interface`, `Scripts`, `sound`)
    grouped ahead of `textures` so a 3.74 GiB bundle splits cleanly at the non-texture / texture boundary first,
    and automatically spills into additional plugin-named archives if either group exceeds `max_archive_bytes`.
    """
    carriers = _validate_plugins_and_budget(plugins, max_archive_bytes)
    if not resources:
        return []

    non_tex = sorted([r for r in resources if r.top_folder != "textures"], key=lambda x: x.rel_posix.lower())
    tex = sorted([r for r in resources if r.top_folder == "textures"], key=lambda x: x.rel_posix.lower())

    total_single = BA2_V2_HEADER_BYTES + sum(r.total_ba2_contribution for r in resources)
    if total_single <= max_archive_bytes:
        ordered = sorted(resources, key=lambda x: x.rel_posix.lower())
        raw_buckets = [ordered]
    else:
        non_tex_chunks = _pack_group_into_chunks(non_tex, max_archive_bytes) if non_tex else []
        tex_chunks = _pack_group_into_chunks(tex, max_archive_bytes) if tex else []
        raw_buckets = non_tex_chunks + tex_chunks
        # If one side was empty and all items fell into a single chunk <= max_archive_bytes, raw_buckets has len 1;
        # otherwise non_tex and tex naturally stay in separate clean archives when total_single > max_archive_bytes.

    if len(raw_buckets) > len(carriers):
        raise ValueError(
            f"split requires {len(raw_buckets)} archives at max_archive_bytes={max_archive_bytes}, "
            f"but only {len(carriers)} active plugins were supplied ({carriers})"
        )

    buckets: List[ArchiveBucket] = []
    for plugin_name, group in zip(carriers, raw_buckets):
        ordered_group = tuple(sorted(group, key=lambda x: x.rel_posix.lower()))
        bucket = ArchiveBucket(
            plugin=plugin_name,
            archive_name=plugin_main_archive_name(plugin_name),
            resources=ordered_group,
        )
        if bucket.estimated_ba2_bytes > max_archive_bytes:
            raise ValueError(
                f"planned archive {bucket.archive_name} is {bucket.estimated_ba2_bytes} B > {max_archive_bytes} B"
            )
        buckets.append(bucket)
    refuse_held_carrier_buckets(buckets, held_off=held_off, starfield_dir=starfield_dir)
    return buckets


def plan_split_by_plugin(
    resources: Sequence[DataResource],
    plugins: Sequence[str],
    bundle_plan: Optional[Mapping[str, object]] = None,
    max_archive_bytes: int = MAX_BA2_BYTES,
    *,
    held_off: Iterable[str] = (),
    starfield_dir: Optional[str] = None,
) -> List[ArchiveBucket]:
    """Assign each `Data/*` resource to its owning plugin's `<PluginStem> - Main.ba2` (with overflow spill if > budget).

    - Component outputs recorded in `bundle_plan["components"]` map to that component's first plugin.
    - Remaining base core `Data/*` files map to `FO4TerrainCore.esm` if active in `plugins`, else `plugins[0]`.
    - If any single plugin's assigned bucket exceeds `max_archive_bytes`, excess chunks spill onto unused carrier
      plugins in `plugins` so no generated BA2 ever exceeds `max_archive_bytes`.
    """
    carriers = _validate_plugins_and_budget(plugins, max_archive_bytes)
    if not resources:
        return []

    carrier_lookup = {p.casefold(): p for p in carriers}
    default_base_plugin = carrier_lookup.get("fo4terraincore.esm", carriers[0])

    owner_by_key: Dict[str, str] = {}
    if isinstance(bundle_plan, Mapping):
        comps = bundle_plan.get("components")
        if isinstance(comps, Mapping):
            for _ckey, cinfo in comps.items():
                if not isinstance(cinfo, Mapping):
                    continue
                cplugins = [p for p in (cinfo.get("plugins") or []) if isinstance(p, str) and p.casefold() in carrier_lookup]
                if not cplugins:
                    continue
                target_plugin = carrier_lookup[cplugins[0].casefold()]
                outputs = cinfo.get("outputs")
                if isinstance(outputs, Mapping):
                    for rel_out in outputs:
                        rel_norm = str(rel_out).replace("\\", "/")
                        if rel_norm.startswith("Data/"):
                            # Keep earliest plugin owner when two components share an identical asset (e.g. _neutral.mat)
                            owner_by_key.setdefault(rel_norm.lower(), target_plugin)

    by_plugin: Dict[str, List[DataResource]] = {p: [] for p in carriers}
    for r in sorted(resources, key=lambda x: x.rel_posix.lower()):
        owner = owner_by_key.get(r.data_key.lower(), default_base_plugin)
        by_plugin[owner].append(r)

    unused = [p for p in carriers if not by_plugin[p]]
    final_pairs: List[Tuple[str, List[DataResource]]] = []

    for p in carriers:
        items = by_plugin[p]
        if not items:
            continue
        chunks = _pack_group_into_chunks(items, max_archive_bytes)
        final_pairs.append((p, chunks[0]))
        for extra_chunk in chunks[1:]:
            if not unused:
                raise ValueError(
                    f"plugin {p} overflowed max_archive_bytes={max_archive_bytes} into {len(chunks)} chunks "
                    f"with no unused carrier plugins left in {carriers}"
                )
            spill_plugin = unused.pop(0)
            final_pairs.append((spill_plugin, extra_chunk))

    carrier_order = {p.casefold(): idx for idx, p in enumerate(carriers)}
    final_pairs.sort(key=lambda pair: carrier_order[pair[0].casefold()])
    buckets = [
        ArchiveBucket(
            plugin=p,
            archive_name=plugin_main_archive_name(p),
            resources=tuple(sorted(grp, key=lambda x: x.rel_posix.lower())),
        )
        for p, grp in final_pairs
    ]
    refuse_held_carrier_buckets(buckets, held_off=held_off, starfield_dir=starfield_dir)
    return buckets


def stage_bucket_tree(exp_data_dir: str, bucket: ArchiveBucket, dst_data_dir: str, hardlink: bool = True) -> List[str]:
    """Populate `dst_data_dir` with only `bucket.resources` and return sorted top-level folder names."""
    os.makedirs(dst_data_dir, exist_ok=True)
    top_folders = set()
    for r in bucket.resources:
        parts = r.rel_posix.split("/")
        top_folders.add(parts[0])
        src = os.path.join(exp_data_dir, *parts)
        dst = os.path.join(dst_data_dir, *parts)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if hardlink:
            try:
                os.link(src, dst)
                continue
            except OSError:
                pass
        shutil.copy2(src, dst)
    return sorted(top_folders)


def verify_split_archives(
    archive_paths_by_name: Mapping[str, str],
    buckets: Sequence[ArchiveBucket],
    all_data_inputs: Mapping[str, str],
    verify_archive_fn,
    max_archive_bytes: int = MAX_BA2_BYTES,
) -> Dict[str, Dict[str, object]]:
    """Verify every built BA2 archive individually and prove their disjoint union equals `all_data_inputs`."""
    expected_all = {k: v for k, v in all_data_inputs.items() if k.startswith("Data/")}
    seen_keys: Dict[str, str] = {}
    summary: Dict[str, Dict[str, object]] = {}

    if set(archive_paths_by_name.keys()) != {b.archive_name for b in buckets}:
        raise ValueError(
            f"built archive set {sorted(archive_paths_by_name)} != planned {[b.archive_name for b in buckets]}"
        )

    for b in buckets:
        ba2_path = archive_paths_by_name[b.archive_name]
        if not os.path.isfile(ba2_path):
            raise ValueError(f"missing split archive: {ba2_path}")
        actual_size = os.path.getsize(ba2_path)
        if actual_size > max_archive_bytes or actual_size > MAX_BA2_BYTES:
            raise ValueError(
                f"split archive {b.archive_name} is {actual_size} B, exceeding limit {min(max_archive_bytes, MAX_BA2_BYTES)} B"
            )
        subset = b.input_digests()
        for k, digest in subset.items():
            if k in seen_keys:
                raise ValueError(f"resource {k} duplicated across split archives")
            seen_keys[k] = digest
        verify_archive_fn(ba2_path, subset)
        summary[b.archive_name] = {
            "plugin": b.plugin,
            "entries": b.file_count,
            "raw_bytes": b.raw_bytes,
            "ba2_bytes": actual_size,
            "sha256": sha256_file(ba2_path),
            "inputs": subset,
        }

    if seen_keys != expected_all:
        missing = sorted(set(expected_all) - set(seen_keys))[:5]
        extra = sorted(set(seen_keys) - set(expected_all))[:5]
        raise ValueError(f"split archives do not match Data inventory (missing={missing}, extra={extra})")

    return summary


def build_split_archives_offline(
    exp_dir: str,
    starfield_dir: str,
    out_dir: str,
    plugins: Sequence[str],
    split_by: str = "plugin",
    max_archive_bytes: int = DEFAULT_MAX_ARCHIVE_BYTES,
    hardlink: bool = True,
    held_off: Iterable[str] = (),
) -> Dict[str, object]:
    """Build and verify split `<plugin> - Main.ba2` archives from `<exp_dir>/Data` into `<out_dir>`."""
    scripts_dir = str(Path(__file__).resolve().parents[2] / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import deploy_starfield as deployment  # noqa: E402
    from verify_packed_experiment import verify_archive  # noqa: E402

    exp_abs = os.path.abspath(exp_dir)
    out_abs = os.path.abspath(out_dir)
    os.makedirs(out_abs, exist_ok=True)

    resources = scan_data_resources(exp_abs)
    all_inputs = {r.data_key: r.sha256 for r in resources}

    bundle_plan = None
    bplan_path = os.path.join(exp_abs, "bundle_plan.json")
    if os.path.isfile(bplan_path):
        with open(bplan_path, encoding="utf-8") as fp:
            bundle_plan = json.load(fp)

    if split_by == "size":
        buckets = plan_split_by_size(
            resources,
            plugins,
            max_archive_bytes=max_archive_bytes,
            held_off=held_off,
            starfield_dir=starfield_dir,
        )
    elif split_by == "plugin":
        buckets = plan_split_by_plugin(
            resources,
            plugins,
            bundle_plan=bundle_plan,
            max_archive_bytes=max_archive_bytes,
            held_off=held_off,
            starfield_dir=starfield_dir,
        )
    else:
        raise ValueError(f"unsupported split_by mode: {split_by!r}")

    built_paths: Dict[str, str] = {}
    exp_data = os.path.join(exp_abs, "Data")
    with tempfile.TemporaryDirectory(prefix="fo4sf-split-pack-", dir=out_abs) as tmp_work:
        for idx, b in enumerate(buckets):
            stage_data = os.path.join(tmp_work, f"bucket_{idx:02d}", "Data")
            folders = stage_bucket_tree(exp_data, b, stage_data, hardlink=hardlink)
            out_ba2 = os.path.join(out_abs, b.archive_name)
            deployment.build_archive(
                argparse.Namespace(starfield=starfield_dir, staging=stage_data),
                out_ba2,
                folders,
                "General",
                compression="None",
            )
            built_paths[b.archive_name] = out_ba2

    verified = verify_split_archives(
        built_paths,
        buckets,
        all_inputs,
        verify_archive_fn=verify_archive,
        max_archive_bytes=max_archive_bytes,
    )
    manifest = {
        "kind": "archive-split-plan",
        "version": 1,
        "split_by": split_by,
        "max_archive_bytes": max_archive_bytes,
        "plugins": list(plugins),
        "total_entries": len(resources),
        "total_raw_bytes": sum(r.size_bytes for r in resources),
        "archives": [
            {
                "archive": b.archive_name,
                "plugin": b.plugin,
                "entries": verified[b.archive_name]["entries"],
                "raw_bytes": verified[b.archive_name]["raw_bytes"],
                "ba2_bytes": verified[b.archive_name]["ba2_bytes"],
                "sha256": verified[b.archive_name]["sha256"],
                "inputs": verified[b.archive_name]["inputs"],
            }
            for b in buckets
        ],
    }
    with open(os.path.join(out_abs, "archive_split_plan.json"), "w", encoding="utf-8") as fp:
        json.dump(manifest, fp, indent=1)
    return manifest


def _resolve_plugins_arg(exp_dir: str, plugins_csv: str) -> List[str]:
    if plugins_csv.strip():
        return [p.strip() for p in plugins_csv.split(",") if p.strip()]
    bplan_path = os.path.join(exp_dir, "bundle_plan.json")
    if os.path.isfile(bplan_path):
        with open(bplan_path, encoding="utf-8") as fp:
            bp = json.load(fp)
        if isinstance(bp.get("plugins"), list) and bp["plugins"]:
            return list(bp["plugins"])
    return sorted(f for f in os.listdir(exp_dir) if f.lower().endswith(".esm"))


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan", help="Preview split archives and sizes without building BA2s.")
    p_plan.add_argument("--exp-dir", required=True)
    p_plan.add_argument("--starfield", default="", help="Optional Starfield root to check Data/FO4SF.toggle.json")
    p_plan.add_argument("--plugins", default="")
    p_plan.add_argument("--split-by", choices=("size", "plugin"), default="plugin")
    p_plan.add_argument("--max-archive-bytes", type=int, default=DEFAULT_MAX_ARCHIVE_BYTES)

    p_build = sub.add_parser("build", help="Build and verify split BA2 archives into --out.")
    p_build.add_argument("--exp-dir", required=True)
    p_build.add_argument("--starfield", required=True)
    p_build.add_argument("--out", required=True)
    p_build.add_argument("--plugins", default="")
    p_build.add_argument("--split-by", choices=("size", "plugin"), default="plugin")
    p_build.add_argument("--max-archive-bytes", type=int, default=DEFAULT_MAX_ARCHIVE_BYTES)
    p_build.add_argument("--no-hardlink", action="store_true")

    p_ver = sub.add_parser("verify", help="Verify an existing split archive directory against --exp-dir.")
    p_ver.add_argument("--split-dir", required=True)
    p_ver.add_argument("--exp-dir", required=True)
    p_ver.add_argument("--starfield", default="", help="Optional Starfield root to check Data/FO4SF.toggle.json")

    a = ap.parse_args(argv)
    if a.cmd == "plan":
        plugins = _resolve_plugins_arg(a.exp_dir, a.plugins)
        resources = scan_data_resources(a.exp_dir)
        bplan = None
        bp_file = os.path.join(a.exp_dir, "bundle_plan.json")
        if os.path.isfile(bp_file):
            with open(bp_file, encoding="utf-8") as fp:
                bplan = json.load(fp)
        buckets = (
            plan_split_by_size(resources, plugins, a.max_archive_bytes, starfield_dir=a.starfield or None)
            if a.split_by == "size"
            else plan_split_by_plugin(
                resources,
                plugins,
                bundle_plan=bplan,
                max_archive_bytes=a.max_archive_bytes,
                starfield_dir=a.starfield or None,
            )
        )
        for b in buckets:
            gib = b.estimated_ba2_bytes / (1024 ** 3)
            print(f"{b.archive_name}: plugin={b.plugin} entries={b.file_count:,} est_ba2={b.estimated_ba2_bytes:,} B ({gib:.3f} GiB)")
        print(f"planned {len(buckets)} archive(s) across {len(resources):,} Data/ files")
        return 0

    if a.cmd == "build":
        plugins = _resolve_plugins_arg(a.exp_dir, a.plugins)
        manifest = build_split_archives_offline(
            exp_dir=a.exp_dir,
            starfield_dir=a.starfield,
            out_dir=a.out,
            plugins=plugins,
            split_by=a.split_by,
            max_archive_bytes=a.max_archive_bytes,
            hardlink=not a.no_hardlink,
        )
        for item in manifest["archives"]:
            gib = item["ba2_bytes"] / (1024 ** 3)
            print(
                f"built & verified {item['archive']}: entries={item['entries']:,} "
                f"bytes={item['ba2_bytes']:,} ({gib:.3f} GiB) sha256={item['sha256'][:16]}..."
            )
        print(f"split verify: ok ({len(manifest['archives'])} archives, {manifest['total_entries']:,} entries)")
        return 0

    if a.cmd == "verify":
        scripts_dir = str(Path(__file__).resolve().parents[2] / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from verify_packed_experiment import verify_archive  # noqa: E402

        plan_file = os.path.join(a.split_dir, "archive_split_plan.json")
        with open(plan_file, encoding="utf-8") as fp:
            manifest = json.load(fp)
        resources = scan_data_resources(a.exp_dir)
        by_key = {r.data_key: r for r in resources}
        buckets = []
        paths = {}
        for item in manifest["archives"]:
            res_tuple = tuple(by_key[k] for k in sorted(item["inputs"]) if k in by_key)
            if len(res_tuple) != len(item["inputs"]):
                raise ValueError(f"{item['archive']} references Data resources missing from {a.exp_dir}")
            buckets.append(ArchiveBucket(plugin=item["plugin"], archive_name=item["archive"], resources=res_tuple))
            paths[item["archive"]] = os.path.join(a.split_dir, item["archive"])
        refuse_held_carrier_buckets(buckets, starfield_dir=a.starfield or None)
        verify_split_archives(
            paths,
            buckets,
            {r.data_key: r.sha256 for r in resources},
            verify_archive_fn=verify_archive,
            max_archive_bytes=int(manifest.get("max_archive_bytes", MAX_BA2_BYTES)),
        )
        print(f"split verify: ok ({len(buckets)} archives, {len(resources):,} entries)")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
