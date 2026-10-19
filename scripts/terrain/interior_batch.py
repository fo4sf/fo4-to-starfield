"""interior_batch.py: build one staged batch of the interior plan, compare it with the port it grows, plan its door
rounds, prune superseded batches (docs/terrain/interior-batches.md). Nothing here installs anything.

  python scripts/terrain/interior_batch.py build --plan <batches.json> --batch N --base <installed port doors staging>
         --base-exports <the base port's staging with its <Cell>.json exports> --core <the core build the base's doors
         name> --work <work staging> --out <NEW folder> --fo4-data <FO4 Data> --starfield <Starfield game dir>
         --content-resources <ContentResources.zip> --texconv <Texconvx64.exe> --collision-template <template.nif>
         --fo4export <Fo4Export.dll> --pluginspike <PluginSpike.dll> [--spec-mask-roughness] [--promote-arg ARG ...]
         [--convert-arg ARG ...] [--prev <the previous batch's --out>] [--dlc-data <a DLC's Data folder> ...] [--min-free-gb 40] [--no-pack] [--jobs 2]
  python scripts/terrain/interior_batch.py compare --old <port folder> --new <port folder> [--json <out>]
  python scripts/terrain/interior_batch.py doors --plan <batches.json> --census <census.json> --batch N --out <door_rounds.json>
  python scripts/terrain/interior_batch.py prune --staging-root <dir> --keep N [--delete]

build (batch 0 = the base port's own cells only: proves the pipeline reproduces the installed port before it grows it;
batch N = the base cells + every cell of batches 1..N; the port is cumulative, one FO4Port.esm, as it always grew):
  1. preflight: --out is new; the drive of --out and --work keeps --min-free-gb free after what this batch adds
     (disk_need: its packed folder plus the work staging's growth, from the plan's estimates); the base has FO4Port.esm, formids.json and doors.json (a vmad_patch.py port report).
  2. exports: the base cells' <Cell>.json are copied from --base-exports (pinned: the installed port was built from
     them); every other cell is exported with --fo4export into <work>/exports (kept: an existing non-empty export is
     reused, so a re-run only exports what is missing).
  3. convert: one merged cell json, then scripts/convert_batch.py --resume into --work (the work staging grows; the
     checkpoints make a later batch convert only its new models) with --starfield-data (rigged doors and movables, as
     the integ builds) and --spec-mask-roughness when given.
  4. plugin: --out/plugin gets the base's formids.json, or with --prev the previous batch's port\formids.json (every
     earlier record, the previous batch's new ones included, keeps its FormID; PluginSpike reuses the map) and lighting.json, scripts/terrain/port_promote.py writes promote.json, PluginSpike writes FO4Port.esm.
  5. doors: scripts/terrain/vmad_patch.py port --keep-markers <base>/doors.json into --out/port: the base's scripted
     load doors re-applied with the SAME marker ids the installed core's exterior doors name, then vmad_patch check.
     The new cells' doors into the Commonwealth stay unwired (they need a core build with their doors: the doors gate,
     docs/terrain/interior-batches.md); their interior-to-interior doors are linked by PluginSpike (XTEL).
  6. compare (below) against the base, written to --out/port/compare.json; a renumbered or missing base id, or a
     removed base record, fails the batch. With --prev, the same compare against the previous batch's port
     (--out/port/compare_prev.json) must pass too: a save made on that staged batch carries over.
  7. pack (unless --no-pack): "FO4Port - Main.ba2" and "FO4Port - Textures.ba2" from the work staging into --out/port
     with Starfield's Archive2 (scripts/deploy_starfield.py's packer; the install step itself is not run). An archive
     of 4,095 MiB or more fails the batch (archive_check); one over 90% of that is listed as near_limit.
  8. --out/result.json: the batch's cells with converted / checked / failed per cell, the pins (git commit, input
     sha256s of the plugins and maps), timings, sizes, free space; README.txt says NOT installed.
compare: every key of the old formids.json has the same FormID in the new one; every old record is still there with the
same signature; counts of byte-identical / changed records by signature, added records by signature, the cells added.
doors: the batch's door-round selection for scripts/bridge/door_rounds.py stage --only (FO4Port_<Cell> editor ids),
the Commonwealth doors into each cell and the interior pairs, and what must be installed first.
prune: lists the interiors_bNN folders under --staging-root that this tool made (result.json written by build), keeps the
newest --keep, and with --delete removes the older ones (nothing else is ever deleted).
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import vmad_patch  # noqa: E402

PLUGIN = "FO4Port.esm"
MARKER = "result.json"
BATCH_DIR = re.compile(r"^interiors_b(\d{2})$")


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def save(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def free_gb(path):
    return shutil.disk_usage(path).free / 1e9


# ----------------------------------------------------------------------------------------------------------- compare
def compare(old_dir, new_dir):
    """The new port against the old one: ids, records, cells. {"pass", "problems", ...}."""
    old_ids, new_ids = load(os.path.join(old_dir, "formids.json")), load(os.path.join(new_dir, "formids.json"))
    problems = []
    missing = sorted(k for k in old_ids if k not in new_ids)
    moved = sorted(k for k in old_ids if k in new_ids and new_ids[k] != old_ids[k])
    if missing:
        problems.append(f"{len(missing)} base id key(s) missing from the new formids.json (first: {missing[:5]})")
    if moved:
        problems.append(f"{len(moved)} base id key(s) renumbered (first: {moved[:5]})")
    old_p, new_p = vmad_patch.Plugin.read(os.path.join(old_dir, PLUGIN)), vmad_patch.Plugin.read(os.path.join(new_dir, PLUGIN))
    if old_p.masters() != new_p.masters():
        problems.append(f"masters {old_p.masters()} -> {new_p.masters()}")
    old_r, new_r = old_p.records(), new_p.records()
    same, changed, removed, resig = Counter(), Counter(), [], []
    changed_ids = []
    for fid, (sig, flags, data, path) in old_r.items():
        n = new_r.get(fid)
        if n is None:
            removed.append(f"{sig.decode()} {fid:08X}")
        elif n[0] != sig:
            resig.append(f"{fid:08X} {sig.decode()} -> {n[0].decode()}")
        elif (n[1], n[2]) == (flags, data):
            same[sig.decode()] += 1
        else:
            changed[sig.decode()] += 1
            if len(changed_ids) < 50:
                changed_ids.append(f"{sig.decode()} {fid:08X}")
    added = Counter(new_r[f][0].decode() for f in set(new_r) - set(old_r))
    why = removed_causes(old_ids, new_ids, removed, new_r)
    if removed:
        problems.append(f"{len(removed)} base record(s) removed (first: {removed[:5]}; by cause: {why['counts']})")
    if resig:
        problems.append(f"{len(resig)} base record(s) changed signature (first: {resig[:5]})")
    old_cells = {k[5:] for k in old_ids if k.startswith("CELL:")}
    new_cells = {k[5:] for k in new_ids if k.startswith("CELL:")}
    return {"old": os.path.abspath(old_dir), "new": os.path.abspath(new_dir), "pass": not problems, "problems": problems,
            "ids": {"old": len(old_ids), "new": len(new_ids), "missing": len(missing), "renumbered": len(moved)},
            "records": {"old": len(old_r), "new": len(new_r), "identical": dict(sorted(same.items())),
                        "changed": dict(sorted(changed.items())), "changed_first": changed_ids,
                        "removed": len(removed), "removed_causes": why, "added": dict(sorted(added.items()))},
            "hedr": {"old": list(old_p.hedr()[1:]), "new": list(new_p.hedr()[1:])},
            "cells_added": sorted(new_cells - old_cells), "cells_removed": sorted(old_cells - new_cells)}


def removed_causes(old_ids, new_ids, removed, new_records):
    """Why base records went: {"counts": {cause: n}, "first": {cause: [keys]}}. Per removed record its old key
    ("SIG:editor id"); the new build wrote a record under a key with the same editor id in another case ("renamed_case":
    a converter that names models differently, e.g. a work staging without the base's editorids.json), under another
    signature ("retyped": e.g. a DOOR that is a STAT now, a door rig the build did not make), or not at all ("gone": a
    promotion or a model the build left out)."""
    inv = {v: k for k, v in old_ids.items()}
    live = {}
    for k, v in new_ids.items():
        if (v | 0x01000000) in new_records and ":" in k:
            sig, rest = k.split(":", 1)
            live.setdefault(rest.casefold(), set()).add((sig, rest))
    counts, first = Counter(), {}
    for entry in removed:
        sig, fid = entry.split(" ")
        key = inv.get(int(fid, 16) & 0xFFFFFF, f"{sig}:?")
        ksig, rest = key.split(":", 1) if ":" in key else (sig, key)
        alts = live.get(rest.casefold(), set()) - {(ksig, rest)}
        cause = ("renamed_case" if any(a[0] == ksig for a in alts) else "retyped" if alts else "gone")
        counts[cause] += 1
        first.setdefault(cause, [])
        if len(first[cause]) < 10:
            first[cause].append(key + (" -> " + ",".join(sorted(f"{a}:{b}" for a, b in alts)) if alts else ""))
    return {"counts": dict(sorted(counts.items())), "first": first}


# ------------------------------------------------------------------------------------------------------------- build
def disk_need(plan, n, work_started):
    """GB this batch adds on the drive (supported estimate from the plan): its packed port folder, plus the work
    staging's growth (all of it when the work staging is new). The peak estimate in the plan counts the work staging
    and two batches from nothing, which over-counts once the work staging and the previous batch exist."""
    if not n:
        return 0.0
    b = plan["batches"][n - 1]
    prev_work = plan["batches"][n - 2]["work_staging_gb_est"] if n > 1 else 0.0
    grow = b["work_staging_gb_est"] - (prev_work if work_started else 0.0)
    return round(b["archives_gb_est"] + max(0.0, grow), 2)


def check_prev(a, n):
    """The previous batch this one grows: a passing build of an earlier batch over the same base port."""
    r = load(os.path.join(a.prev, MARKER))
    port = os.path.join(a.prev, "port")
    if not (r.get("pass") and isinstance(r.get("batch"), int) and r["batch"] < n):
        sys.exit(f"--prev {a.prev}: not a passing earlier batch (batch {r.get('batch')}, pass {r.get('pass')})")
    if r.get("pins", {}).get("base_plugin") != sha256(os.path.join(a.base, PLUGIN)):
        sys.exit(f"--prev {a.prev} was built over another base port")
    for need in (PLUGIN, "formids.json"):
        if not os.path.isfile(os.path.join(port, need)):
            sys.exit(f"--prev {a.prev} lacks port\\{need}")
    return port


def cell_plugins(plan, n):
    """{editor id: plugin file} for the cells of batches 1..n whose formkey names a plugin other than Fallout4.esm
    (the DLC batch); every other cell is exported from Fallout4.esm."""
    out = {}
    for b in plan["batches"][:n]:
        for c in b["cells"]:
            plugin = (c.get("formkey") or "").partition(":")[2]
            if plugin and plugin.lower() != "fallout4.esm":
                out[c["editor_id"]] = plugin
    return out


def find_plugin(dirs, name):
    for d in dirs:
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    return None


def batch_cells(plan, n):
    """The cells of batches 1..n, in plan order."""
    if n < 0 or n > len(plan["batches"]):
        raise ValueError(f"batch {n} not in the plan (1..{len(plan['batches'])}, or 0 for the base cells only)")
    return [c["editor_id"] for b in plan["batches"][:n] for c in b["cells"]]


def base_cells(base_exports):
    helpers = {"editorids", "formids", "lighting", "merged", "manifest", "promote", "teleports", "doors", "doors_check",
               "failure-summary", "build-state", "activation", "texture_log", "compare", "result"}
    return sorted(n[:-5] for n in os.listdir(base_exports) if n.lower().endswith(".json") and n[:-5] not in helpers
                  and not n.startswith(("routes", "probe")))


def run(cmd, log, env=None, cwd=None):
    t = time.time()
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"\n$ {' '.join(cmd)}\n")
        f.flush()
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=env, cwd=cwd)
    return r.returncode, round(time.time() - t, 1)


def export_cell(a, cell, exports, log, plugin=None):
    """Fo4Export one cell from Fallout4.esm, or (plugin: a DLC's own cell) from that plugin found in --dlc-data with
    Fallout4.esm loaded as its master, so the base records and the Commonwealth doors resolve."""
    dst = os.path.join(exports, cell + ".json")
    if os.path.isfile(dst) and os.path.getsize(dst) > 0:
        return cell, 0, 0.0
    tmp = dst + ".tmp"
    fo4 = os.path.join(a.fo4_data, "Fallout4.esm")
    src = [fo4]
    if plugin:
        path = find_plugin(a.dlc_data, plugin)
        if path is None:
            with open(log + f".{cell}", "w", encoding="utf-8") as f:
                f.write(f"{plugin} not found in --dlc-data {a.dlc_data}\n")
            return cell, 2, 0.0
        src = [path, "--master", fo4]
    rc, s = run(["dotnet", a.fo4export] + src + ["export", cell, tmp], log + f".{cell}")
    if rc == 0 and os.path.isfile(tmp) and os.path.getsize(tmp) > 0:
        os.replace(tmp, dst)
    return cell, rc, s


def build(a):
    plan = load(a.plan)
    t0 = time.time()
    if os.path.exists(a.out):
        sys.exit(f"{a.out} exists: every batch is a new folder")
    for need in (PLUGIN, "formids.json", "doors.json"):
        if not os.path.isfile(os.path.join(a.base, need)):
            sys.exit(f"--base {a.base} lacks {need} (the installed port's doors staging)")
    new_cells = batch_cells(plan, a.batch)
    old_cells = base_cells(a.base_exports)
    clash = sorted(set(c.casefold() for c in new_cells) & set(c.casefold() for c in old_cells))
    if clash:
        sys.exit(f"cells already in the base port: {clash}")
    prev_port = check_prev(a, a.batch) if a.prev else None
    need = disk_need(plan, a.batch, os.path.isfile(os.path.join(a.work, "manifest.json")))
    os.makedirs(a.work, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    free = min(free_gb(a.work), free_gb(os.path.dirname(os.path.abspath(a.out))))
    if free - need < a.min_free_gb:
        sys.exit(f"free {free:.1f} GB - this batch's estimated {need} GB < {a.min_free_gb} GB: refusing")
    os.makedirs(a.out)
    log = os.path.join(a.out, "build.log")
    steps, cells = {}, {}

    # 2. exports
    exports = os.path.join(a.work, "exports")
    os.makedirs(exports, exist_ok=True)
    pinned = os.path.join(a.out, "base_exports")
    os.makedirs(pinned)
    for c in old_cells:
        shutil.copyfile(os.path.join(a.base_exports, c + ".json"), os.path.join(pinned, c + ".json"))
    with ThreadPoolExecutor(max_workers=max(1, a.jobs)) as pool:
        dlc = cell_plugins(plan, a.batch)
        got = list(pool.map(lambda c: export_cell(a, c, exports, os.path.join(a.out, "export.log"), dlc.get(c)), new_cells))
    for c, rc, s in got:
        cells[c] = {"exported": rc == 0, "export_s": s}
    failed_exports = [c for c, rc, _s in got if rc != 0]
    steps["export"] = {"cells": len(new_cells), "failed": failed_exports}
    export_paths = [os.path.join(pinned, c + ".json") for c in old_cells] + \
                   [os.path.join(exports, c + ".json") for c in new_cells if c not in failed_exports]

    # 3. convert: the base's model -> editor id map first, so every base model keeps its record name (and FormID key);
    # convert_batch names new models itself. A work staging that already names a base model differently is refused.
    seed = os.path.join(a.base_exports, "editorids.json")
    if os.path.isfile(seed):
        base_names = load(seed)
        work_names_path = os.path.join(a.work, "editorids.json")
        work_names = load(work_names_path) if os.path.isfile(work_names_path) else {}
        norm = lambda m: {k.replace("\\", "/").lower(): v for k, v in m.items()}  # noqa: E731
        bn, wn = norm(base_names), norm(work_names)
        differ = sorted(k for k in bn if k in wn and wn[k] != bn[k])
        if differ:
            return finish(a, plan, steps, cells, t0, f"--work names {len(differ)} base model(s) differently from the base's "
                                                      f"editorids.json (first {differ[:3]}): use a new --work")
        merged_names = dict(work_names)
        merged_names.update({k: v for k, v in base_names.items() if k.replace("\\", "/").lower() not in wn})
        save(work_names_path, merged_names)
        steps["editorids"] = {"seeded_from": seed, "base": len(base_names), "work_before": len(work_names)}
    else:
        steps["editorids"] = {"seeded_from": None, "warning": f"{seed} missing: base models may be renamed"}
    refs = []
    for p in export_paths:
        refs.extend(load(p)["refs"])
    merged = os.path.join(a.out, "merged.json")
    save(merged, {"cell": "merged", "refs": refs})
    sf_data = os.path.join(a.starfield, "Data")
    cmd = [sys.executable, os.path.join(ROOT, "scripts", "convert_batch.py"), "--fo4-data", a.fo4_data, "--staging", a.work,
           "--content-resources", a.content_resources, "--texconv", a.texconv, "--collision-template", a.collision_template,
           "--starfield-data", sf_data, "--cell-json", merged, "--limit", "100000", "--resume"]
    if a.spec_mask_roughness:
        cmd.append("--spec-mask-roughness")
    for d in a.dlc_data:
        cmd += ["--extra-data", d]
    cmd += a.convert_arg
    rc, s = run(cmd, log, cwd=ROOT)
    os.remove(merged)                                         # the exports are kept; the merge is rebuilt each time
    steps["convert"] = {"exit": rc, "seconds": s}
    if rc != 0:
        return finish(a, plan, steps, cells, t0, "convert failed")
    manifest = load(os.path.join(a.work, "manifest.json"))
    failed_models = {f["nif"].replace("/", "\\").lower(): f.get("reason", "") for f in manifest.get("failures", [])}

    # 4. plugin
    raw = os.path.join(a.out, "plugin")
    os.makedirs(raw)
    shutil.copyfile(os.path.join(prev_port or a.base, "formids.json"), os.path.join(raw, "formids.json"))
    steps["formids_seed"] = os.path.abspath(os.path.join(prev_port or a.base, "formids.json"))
    if os.path.isfile(os.path.join(a.base, "lighting.json")):
        shutil.copyfile(os.path.join(a.base, "lighting.json"), os.path.join(raw, "lighting.json"))
    tables = os.path.join(ROOT, "scripts", "terrain", "clusters")
    rc, s = run([sys.executable, os.path.join(HERE, "port_promote.py"), "--out", os.path.join(raw, "promote.json"),
                 "--containers-table", os.path.join(tables, "container_table.json"),
                 "--items-table", os.path.join(tables, "item_table.json"), "--starfield-data", sf_data]
                + a.promote_arg + export_paths, log, cwd=ROOT)
    steps["promote"] = {"exit": rc, "seconds": s}
    if rc != 0:
        return finish(a, plan, steps, cells, t0, "port_promote failed")
    env = dict(os.environ, STARFIELD_DATA=sf_data)
    rc, s = run(["dotnet", a.pluginspike, raw, os.path.join(a.work, "manifest.json")] + export_paths, log, env=env)
    steps["pluginspike"] = {"exit": rc, "seconds": s}
    if rc != 0:
        return finish(a, plan, steps, cells, t0, "PluginSpike failed")
    placed = placed_counts(log)
    for c in new_cells:
        if c in cells and c in placed:
            cells[c].update(placed[c])

    # 5. doors
    port = os.path.join(a.out, "port")
    rc, s = run([sys.executable, os.path.join(HERE, "vmad_patch.py"), "port", "--port", raw, "--core", a.core, "--out", port,
                 "--keep-markers", os.path.join(a.base, "doors.json")], log, cwd=ROOT)
    steps["doors"] = {"exit": rc, "seconds": s}
    if rc != 0:
        return finish(a, plan, steps, cells, t0, "vmad_patch port failed")
    rc, s = run([sys.executable, os.path.join(HERE, "vmad_patch.py"), "check", "--port", raw, "--out", port, "--core", a.core],
                log, cwd=ROOT)
    steps["doors_check"] = {"exit": rc, "seconds": s}

    # 6. compare
    cmp_ = compare(a.base, port)
    save(os.path.join(port, "compare.json"), cmp_)
    steps["compare"] = {"pass": cmp_["pass"], "problems": cmp_["problems"], "records": cmp_["records"],
                        "cells_added": len(cmp_["cells_added"])}
    prev_ok = True
    if prev_port:
        cmp_prev = compare(prev_port, port)
        save(os.path.join(port, "compare_prev.json"), cmp_prev)
        steps["compare_prev"] = {"prev": os.path.abspath(a.prev), "pass": cmp_prev["pass"], "problems": cmp_prev["problems"],
                                 "records": cmp_prev["records"], "cells_added": len(cmp_prev["cells_added"])}
        prev_ok = cmp_prev["pass"]
    teleports = load(os.path.join(raw, "teleports.json")) if os.path.isfile(os.path.join(raw, "teleports.json")) else {}
    steps["teleports"] = {k: v for k, v in teleports.items() if not isinstance(v, list)}
    added = {c.casefold() for c in cmp_["cells_added"]}
    for c in new_cells:
        e = cells.setdefault(c, {})
        e["in_plugin"] = f"fo4port_{c}".casefold() in added
        try:
            mods = {r.get("model", "").replace("/", "\\").lower() for r in load(os.path.join(exports, c + ".json"))["refs"]}
        except (OSError, ValueError, KeyError):
            mods = set()
        e["failed_models"] = sorted(m for m in mods if ("meshes\\" + m if not m.startswith("meshes\\") else m) in failed_models)
        e["result"] = ("converted" if e["in_plugin"] and e.get("exported") else "failed")
        e["checked"] = bool(e["in_plugin"] and cmp_["pass"] and prev_ok and steps["doors_check"]["exit"] == 0)
        if e["result"] == "failed":
            e["reason"] = "export failed" if not e.get("exported") else "cell not written by PluginSpike"

    # 7. pack
    if not a.no_pack and cmp_["pass"] and prev_ok:
        import deploy_starfield
        packer = argparse.Namespace(starfield=a.starfield, staging=a.work)
        t = time.time()
        main_dirs = [d for d in deploy_starfield.MAIN_DIRS if os.path.isdir(os.path.join(a.work, d))]
        deploy_starfield.build_archive(packer, os.path.join(port, deploy_starfield.ARCHIVE), main_dirs, "General")
        deploy_starfield.build_archive(packer, os.path.join(port, deploy_starfield.TEX_ARCHIVE), ["textures"], "DDS")
        steps["pack"] = archive_check({n: os.path.getsize(os.path.join(port, n))
                                       for n in (deploy_starfield.ARCHIVE, deploy_starfield.TEX_ARCHIVE)})
        steps["pack"]["seconds"] = round(time.time() - t, 1)
    ok = (cmp_["pass"] and prev_ok and steps["doors_check"]["exit"] == 0 and not failed_exports
          and steps.get("pack", {}).get("pass", True))
    return finish(a, plan, steps, cells, t0, None if ok else "checks failed (see steps)")


# Every vanilla Starfield archive stays under 4 GiB and no source shows the engine reading a larger one
# (research/framework/interiors.md X3), so a batch whose archive reaches this fails its check.
ARCHIVE_LIMIT = 4095 * 2 ** 20
ARCHIVE_WARN = 0.9


def archive_check(sizes):
    """{"bytes", "pass", "near_limit"} for the packed archives' sizes."""
    over = sorted(n for n, s in sizes.items() if s >= ARCHIVE_LIMIT)
    near = sorted(n for n, s in sizes.items() if ARCHIVE_WARN * ARCHIVE_LIMIT <= s < ARCHIVE_LIMIT)
    out = {"bytes": sizes, "limit": ARCHIVE_LIMIT, "pass": not over, "near_limit": near}
    if over:
        out["problem"] = f"over {ARCHIVE_LIMIT:,} bytes: {', '.join(over)} (split the archive before installing)"
    return out


def placed_counts(log):
    """{cell: {"placed", "lights", "skipped"}} from PluginSpike's per-cell lines."""
    out = {}
    rx = re.compile(r"cell FO4Port_(\S+) \S+: placed (\d+) references \+ (\d+) lights .*skipped (\d+)")
    with open(log, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = rx.search(line)
            if m:
                out[m.group(1)] = {"placed": int(m.group(2)), "lights": int(m.group(3)), "skipped": int(m.group(4))}
    return out


def finish(a, plan, steps, cells, t0, error):
    port = os.path.join(a.out, "port")
    pins = {"commit": git_head(), "plan": sha256(a.plan), "base_plugin": sha256(os.path.join(a.base, PLUGIN)),
            "base_formids": sha256(os.path.join(a.base, "formids.json"))}
    if os.path.isfile(os.path.join(port, PLUGIN)):
        pins["plugin"] = sha256(os.path.join(port, PLUGIN))
        pins["plugin_bytes"] = os.path.getsize(os.path.join(port, PLUGIN))
    result = {"batch": a.batch, "name": os.path.basename(os.path.abspath(a.out)), "pass": error is None, "error": error,
              "installed": False, "base": os.path.abspath(a.base), "core": os.path.abspath(a.core),
              "work": os.path.abspath(a.work), "pins": pins, "steps": steps, "cells": cells,
              "totals": dict(Counter(c.get("result", "pending") for c in cells.values())),
              "seconds": round(time.time() - t0, 1), "free_gb_after": round(free_gb(a.out), 1)}
    save(os.path.join(a.out, MARKER), result)
    with open(os.path.join(a.out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"Interior batch {a.batch} (scripts/terrain/interior_batch.py build; docs/terrain/interior-batches.md).\n"
                f"{'PASS' if error is None else 'FAIL: ' + error}. NOT installed, NOT queued. The port to install is port\\ "
                f"(FO4Port.esm + archives); plugin\\ is PluginSpike's output before the door patch.\n")
    print(json.dumps({k: result[k] for k in ("batch", "pass", "error", "totals", "seconds", "free_gb_after")}, indent=1))
    return 0 if error is None else 1


def git_head():
    try:
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    except OSError:
        return None


# ------------------------------------------------------------------------------------------------------------- doors
def doors(plan, census, n):
    """The door-round selection of batch n: door_rounds.py stage --only, and the doors it covers."""
    rows = {r["editor_id"]: r for r in census["cells"]}
    batch = plan["batches"][n - 1]
    cells, only = [], []
    for c in batch["cells"]:
        r = rows.get(c["editor_id"], {})
        ins = r.get("load_doors_in", [])
        cw = [d for d in ins if d.get("from") == "Commonwealth"]
        other_worlds = sorted({d["from"] for d in ins if d.get("from") in census.get("worlds", {}).values()} - {"Commonwealth"})
        interiors = sorted({d["from"] for d in ins if d.get("from") and d["from"] not in census.get("worlds", {}).values()})
        cells.append({"cell": c["editor_id"], "coc": f"FO4Port_{c['editor_id']}", "commonwealth_doors": [d["door"] for d in cw],
                      "other_worldspace_doors": other_worlds, "interior_doors_from": interiors})
        if cw:
            only.append(f"FO4Port_{c['editor_id']}")
    return {"batch": n, "name": batch["name"], "only": ",".join(only), "cells": cells,
            "commonwealth_door_count": sum(len(c["commonwealth_doors"]) for c in cells),
            "needs": ("this batch's port installed together with a core build whose doors cluster was made against it "
                      "(make_cluster.py doors --port <this batch's port>, make_core64c.py stage --cluster, then "
                      "vmad_patch.py port): the installed core v6c/v6e only wires the 16 base cells' doors"),
            "then": ["python scripts/bridge/door_rounds.py order --plugins-txt <Plugins.txt>",
                     "python scripts/bridge/door_rounds.py stage --core <that core build> --port <this batch's port> "
                     f"--core-index HH --port-index HH --out <NEW folder> --only {','.join(only) or '<none>'}",
                     "python scripts/game/testqueue.py plan-terrain --staging <port> --exp-dir <out> --out <queue> --bridge <bridge staging>",
                     "python scripts/game/testqueue.py run --queue <queue> --max-attempts 1",
                     "python scripts/bridge/door_rounds.py judge --queue <queue>"],
            "coc_only": [c["coc"] for c in cells if not c["commonwealth_doors"]]}


# ------------------------------------------------------------------------------------------------------------- prune
def prune(root, keep, delete):
    found = []
    for n in sorted(os.listdir(root)):
        m = BATCH_DIR.match(n)
        p = os.path.join(root, n)
        if m and os.path.isdir(p) and os.path.isfile(os.path.join(p, MARKER)):
            try:
                made = load(os.path.join(p, MARKER))
            except (OSError, ValueError):
                continue
            if made.get("name") == n and made.get("installed") is False:
                found.append((int(m.group(1)), p))
    found.sort()
    drop = found[:-keep] if keep > 0 else found
    for _n, p in drop:
        print(("delete " if delete else "would delete ") + p)
        if delete:
            shutil.rmtree(p)
    for _n, p in found[len(drop):]:
        print("keep " + p)
    return [p for _n, p in drop]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    for k in ("plan", "base", "base-exports", "core", "work", "out", "fo4-data", "starfield", "content-resources", "texconv",
              "collision-template", "fo4export", "pluginspike"):
        b.add_argument("--" + k, required=True)
    b.add_argument("--batch", type=int, required=True)
    b.add_argument("--spec-mask-roughness", action="store_true")
    b.add_argument("--promote-arg", action="append", default=[])
    b.add_argument("--convert-arg", action="append", default=[])
    b.add_argument("--prev", default="")
    b.add_argument("--dlc-data", action="append", default=[],
                   help="a DLC's Data folder (repeatable): its plugin for that batch's cells, its DLC*.ba2 for the models")
    b.add_argument("--min-free-gb", type=float, default=40.0)
    b.add_argument("--no-pack", action="store_true")
    b.add_argument("--jobs", type=int, default=2)
    c = sub.add_parser("compare")
    c.add_argument("--old", required=True)
    c.add_argument("--new", required=True)
    c.add_argument("--json", default="")
    d = sub.add_parser("doors")
    d.add_argument("--plan", required=True)
    d.add_argument("--census", required=True)
    d.add_argument("--batch", type=int, required=True)
    d.add_argument("--out", required=True)
    p = sub.add_parser("prune")
    p.add_argument("--staging-root", required=True)
    p.add_argument("--keep", type=int, default=2)
    p.add_argument("--delete", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        return build(a)
    if a.cmd == "compare":
        r = compare(a.old, a.new)
        if a.json:
            save(a.json, r)
        print(json.dumps({k: r[k] for k in ("pass", "problems", "ids", "records", "hedr")}, indent=1))
        print(f"cells added: {len(r['cells_added'])}, removed: {r['cells_removed']}")
        return 0 if r["pass"] else 1
    if a.cmd == "doors":
        save(a.out, doors(load(a.plan), load(a.census), a.batch))
        return 0
    if a.keep < 1:
        sys.exit("--keep must be at least 1 (the latest batch is never pruned)")
    prune(a.staging_root, a.keep, a.delete)
    return 0


if __name__ == "__main__":
    sys.exit(main())
