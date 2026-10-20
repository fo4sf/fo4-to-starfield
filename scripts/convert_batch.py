"""Convert many Fallout 4 statics straight from the game's archives into a Starfield staging folder.

usage: python convert_batch.py --fo4-data <Fallout 4 Data dir> --staging <out dir> --content-resources <ContentResources.zip>
                               --texconv <Texconvx64.exe> --collision-template <vanilla box-collision Starfield .nif>
                               [--pattern "setdressing/(chair|stool)"] [--limit 40] [--manifest manifest.json]
Writes <staging>/manifest.json: converted items (EditorID + model path for the plugin writer), failures with reasons, stats.
After conversion, prints the top failure reasons by count (with percentages) and writes failure-summary.json.
Needs numpy. Deterministic: names are processed in sorted order.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import ba2, checkpoints, convert_static, meshcollision, pipeline, sfcollision, sfnif, textures  # noqa: E402


def checkpoint_signature(a):
    import importlib.metadata
    from pathlib import Path
    archives = sorted(p for p in Path(a.fo4_data).iterdir()
                      if p.name.lower().startswith("fallout4 - ") and p.suffix.lower() == ".ba2")
    if a.starfield_data:
        archives.append(Path(a.starfield_data) / "Starfield - Meshes01.ba2")
    code = sorted(Path(__file__).resolve().parents[1].joinpath("src", "fo4sf").glob("*.py")) + [Path(__file__)]
    packages = {}
    for name in ("numpy", "Pillow"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    def safe_resolve(p):
        try:
            return str(p.resolve())
        except (OSError, ValueError):
            return str(p)

    sig = {"version": 1, "python": sys.version, "packages": packages,
           "archives": [checkpoints.archive_identity(p) for p in archives],
           "content": {safe_resolve(p): checkpoints.digest(p) for p in
                       [*code, Path(a.texconv), Path(a.content_resources), Path(a.collision_template)]},
           "rig_doors": bool(a.starfield_data), "movable_items": bool(a.starfield_data) and not a.static_items}
    if getattr(a, "prefix", "fo4port") != "fo4port":   # output paths differ; the default keeps existing checkpoints valid
        sig["prefix"] = a.prefix
    if getattr(a, "door_anim_dll", "") and a.starfield_data:   # multi-part doors get their own rig and clips
        sig["door_anim_dll"] = checkpoints.digest(Path(a.door_anim_dll))
    caps = textures.parse_texture_caps(getattr(a, "max_texture", ""))
    if caps:                                            # capped outputs differ; no cap keeps existing checkpoints valid
        sig["max_texture"] = caps
    return sig


def merge_texture_log(staging, log):
    """Add this run's texture log (pipeline.Converter.texture_log) to <staging>/texture_log.json, which keeps the entries
    of earlier runs (a resumed run reuses their textures without converting them again). Returns the merged log."""
    path = os.path.join(staging, "texture_log.json")
    merged = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            merged = json.load(f)
    merged.update(log)
    write_json_atomic(path, merged)
    return merged


def texture_totals(log):
    full = sum(v.get("bytes", 0) for v in log.values())
    written = sum(v.get("out_bytes", 0) for v in log.values())
    return {"textures": len(log), "capped": sum(1 for v in log.values() if v.get("capped")),
            "full_bytes": full, "written_bytes": written}


def source_identity(source):
    return source.replace("\\", "/").lower()


def load_editor_ids(staging):
    path = os.path.join(staging, "editorids.json")
    ids = {}
    def adopt(source, value):
        if not isinstance(source, str) or not source or not isinstance(value, str) or not value:
            raise ValueError("source and editor ID must be nonempty strings")
        key = source_identity(source)
        if key in ids and ids[key] != value:
            raise ValueError(f"conflicting editor ID for {key}")
        ids[key] = value

    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            mapping = json.load(f)
        if not isinstance(mapping, dict):
            raise ValueError("persistent source mapping must be an object")
        for source, value in mapping.items():
            adopt(source, value)
    # Adopt existing plugin names rather than renaming deployed records on upgrade.
    manifest = os.path.join(staging, "manifest.json")
    if os.path.exists(manifest):
        with open(manifest, encoding="utf-8") as f:
            for item in json.load(f)["items"]:
                adopt(item["source"], item["editor_id"])
    if len({v.lower() for v in ids.values()}) != len(ids):
        raise ValueError("duplicate editor IDs in persistent source mapping")
    return ids


def editor_id(source, ids):
    key = source_identity(source)
    if key not in ids:
        basename = key.rsplit("/", 1)[-1]
        stem = re.sub(r"[^A-Za-z0-9_]", "_", os.path.splitext(basename)[0])
        name = "FO4Port_" + stem
        reserved = {v.lower() for v in ids.values()}
        if name.lower() in reserved:
            name += "_" + hashlib.sha256(key.encode()).hexdigest()[:16]
        if name.lower() in reserved:
            raise ValueError(f"editor ID collision for {key}")
        ids[key] = name
    return ids[key]


def write_json_atomic(path, value):
    fd, temporary = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".fo4port-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fo4-data", required=True)
    ap.add_argument("--staging", required=True)
    ap.add_argument("--content-resources", required=True)
    ap.add_argument("--texconv", required=True)
    ap.add_argument("--collision-template", required=True)
    ap.add_argument("--starfield-data", default="",
                    help="Starfield Data folder: enables opening doors (needs the vanilla door body as a keyframed donor)")
    ap.add_argument("--static-items", action="store_true",
                    help="keep FO4 loose items fixed (default with --starfield-data: movable, as in FO4)")
    ap.add_argument("--door-anim-dll", default="",
                    help="external CALUMI.Animation.dll (not distributed): with --starfield-data, doors that move more "
                         "than one part (double doors, shutters, sliding panel sets) get their own rig and Open/Close "
                         "clips; without it they keep the single-hinge template and list the parts that stay closed")
    ap.add_argument("--resume", action="store_true", help="reuse content-verified per-model checkpoints")
    ap.add_argument("--pattern", default=r"^meshes[\\/]setdressing[\\/]")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--max-tris", type=int, default=20000, help="skip meshes with more triangles than this")
    ap.add_argument("--cell-json", default="", help="convert the models placed in a cell exported by dotnet/Fo4Export")
    ap.add_argument("--types", default="Static,StaticCollection,MovableStatic,Furniture,Door,Activator,Container,MiscItem,Terminal",
                    help="base record types to take from --cell-json")
    ap.add_argument("--prefix", default="fo4port",
                    help="folder under meshes/, materials/ and textures/ for the converted files (another plugin's own "
                         "archive needs its own prefix, so two archives never hold different files at the same path)")
    ap.add_argument("--max-texture", default="",
                    help="cap converted textures by dropping top mip levels: one size for every kind ('1024') or per "
                         "kind ('color=1024,normal=512,rough=256,opacity=512'); default: full resolution. The full and "
                         "written size of every texture go to <staging>/texture_log.json")
    a = ap.parse_args()
    if not re.fullmatch(r"[a-z0-9_]+", a.prefix):
        ap.error("--prefix: lower-case letters, digits and _ only")
    try:
        textures.parse_texture_caps(a.max_texture)
    except ValueError as e:
        ap.error(f"--max-texture: {e}")
    if a.door_anim_dll and not os.path.isfile(a.door_anim_dll):
        ap.error("--door-anim-dll: file not found")
    if a.door_anim_dll and not a.starfield_data:
        ap.error("--door-anim-dll needs --starfield-data (doors are rigged only with the vanilla donor body)")

    ids = load_editor_ids(a.staging)

    t0 = time.time()
    src = pipeline.Fo4Archives(a.fo4_data)
    with open(a.collision_template, "rb") as f:
        template = convert_static.collision_template_from_nif(f.read())
    donor = None
    if a.starfield_data:                          # opening doors: leaf body copied from a vanilla animated door
        donor = sfcollision.physics_blob_from_nif(ba2.Ba2(os.path.join(a.starfield_data, "Starfield - Meshes01.ba2")).read(
            sfnif.DOOR_TEMPLATE["nif"]))
    mesh_template = None
    if a.starfield_data:                          # FO4's own collision meshes, transplanted into a vanilla container
        mesh_template = meshcollision.template_from_nif(ba2.Ba2(os.path.join(a.starfield_data, "Starfield - Meshes01.ba2")).read(
            meshcollision.UNIVERSAL_TEMPLATE_NIF))
    dynamic_template = None
    if a.starfield_data and not a.static_items:   # FO4 loose items movable: built on a vanilla dynamic item's body
        dynamic_template = meshcollision.check_dynamic_template(meshcollision.template_from_nif(
            ba2.Ba2(os.path.join(a.starfield_data, "Starfield - Meshes01.ba2")).read(meshcollision.DYNAMIC_TEMPLATE_NIF)))
    cache =checkpoints.Checkpoints(a.staging, checkpoint_signature(a)) if a.resume else None
    conv = None
    if a.cell_json:
        with open(a.cell_json, encoding="utf-8-sig") as f:
            cell = json.load(f)
        wanted = set(a.types.split(","))
        names = sorted({"meshes\\" + r["model"].lstrip("\\") for r in cell["refs"] if r["model"] and r["type"] in wanted
                        and not re.search(r"marker|^\\?effects[\\/]", r["model"], re.I)},   # editor markers, fog/light volumes
                       key=str.lower)
    else:
        names = src.mesh_names(a.pattern)
    print(f"{len(names)} candidate meshes; converting up to {a.limit}")
    os.makedirs(a.staging, exist_ok=True)
    state_path = os.path.join(a.staging, "build-state.json")
    write_json_atomic(state_path, {"complete": False, "status": "converting"})
    items, failures, reused = [], [], 0
    attempted_so_far = 0
    skipped = 0
    progress_every = 10  # live status every N attempts; % of limit and success-rate ETA when --limit is set
    lod_skip = re.compile(r"(lod|_dmg|damaged|destr)", re.I)
    remaining_candidates = (sum(1 for name in names if a.cell_json or not lod_skip.search(name))
                            if a.limit > 0 else 0)
    for name in names:
        if len(items) >= a.limit:
            break
        if not a.cell_json and lod_skip.search(name):
            skipped += 1
            continue
        remaining_candidates -= 1
        r = cache.load(name) if cache else None
        if r is not None:
            reused += 1
        else:
            if conv is None:
                conv = pipeline.Converter(src, a.staging, a.texconv, a.content_resources, template,
                                          rig_doors=donor is not None, door_physics_donor=donor,
                                          sf_mesh_template=mesh_template, dynamic_template=dynamic_template,
                                          prefix=a.prefix, max_texture=a.max_texture,
                                          door_anim_dll=a.door_anim_dll or None)
            r = conv.convert_nif(name)
            if cache:
                try:
                    cache.save(name, r)
                except (OSError, ValueError) as e:
                    print(f"  checkpoint unavailable for {name}: {e}")
        attempted_so_far += 1
        if not r["ok"]:
            failures.append({"nif": name, "reason": r["reason"]})
        else:
            eid = editor_id(name, ids)
            if cache:
                os.makedirs(a.staging, exist_ok=True)
                write_json_atomic(os.path.join(a.staging, "editorids.json"), ids)
            items.append({"editor_id": eid, "model": r["out_name"].replace("/", "\\") + ".nif", "source": name,
                          "shapes": r["shapes"], "fallback_materials": r["fallback_materials"], "form_index": len(items),
                          "collision_report": r.get("collision_report") or {}, **({"door": r["door"]} if "door" in r else {}),
                          **({"load_door": r["load_door"]} if "load_door" in r else {}),
                          **({"movable": r["movable"]} if "movable" in r else {}),
                          **({"door_not_opening": r["door_not_opening"]} if "door_not_opening" in r else {}),
                          **({"door_frozen_parts": r["door_frozen_parts"]} if "door_frozen_parts" in r else {}),
                          **({"door_error": r["door_error"]} if "door_error" in r else {})})
            print(f"  ok  {name} -> {eid} (shapes {r['shapes']}, fallback materials {r['fallback_materials']})")
        if attempted_so_far % progress_every == 0:
            elapsed_now = time.time() - t0
            rate = attempted_so_far / elapsed_now if elapsed_now > 0 else 0
            pct = ""
            eta = ""
            if a.limit and a.limit > 0:
                pct = f" ({100.0 * len(items) / a.limit:.0f}% of limit)"
                success_rate = len(items) / elapsed_now if elapsed_now > 0 else 0
                remaining_successes = a.limit - len(items)
                # Success-target ETA uses successful throughput, not attempt rate. Skip it with no
                # measured successes or when remaining candidates cannot reach the limit (exhausted input).
                if success_rate > 0 and remaining_successes > 0 and remaining_candidates >= remaining_successes:
                    eta_s = remaining_successes / success_rate
                    if eta_s > 60:
                        eta = f", ~{eta_s/60:.0f}m left"
                    elif eta_s > 5:
                        eta = f", ~{eta_s:.0f}s left"
            print(f"  progress: {attempted_so_far} attempted ({len(items)} ok, {len(failures)} fail, {skipped} skipped) "
                  f"in {elapsed_now:.0f}s ({rate:.1f}/s){pct}{eta}")
    for f in failures[:15]:
        print("  FAIL", f["nif"], "-", f["reason"][:110])
    from collections import Counter, defaultdict
    reason_counts = Counter(f["reason"].split(":")[0].strip() for f in failures)
    examples = defaultdict(list)
    for f in failures:
        top = f["reason"].split(":")[0].strip()
        if len(examples[top]) < 3:
            examples[top].append(f["nif"])
    total = len(failures)
    unique = len(reason_counts)
    attempted = len(items) + total
    success_pct = 100.0 * len(items) / attempted if attempted else 100.0
    print(f"  Batch result: {len(items)}/{attempted} succeeded ({success_pct:.1f}%)")
    elapsed = round(time.time() - t0, 1)
    print(f"  reused={reused}  seconds={elapsed}")
    doors = sum(1 for it in items if "door" in it)
    load_doors = sum(1 for it in items if "load_door" in it)
    movables = sum(1 for it in items if "movable" in it)
    total_shapes = sum(it.get("shapes", 0) for it in items)
    avg_shapes = round(total_shapes / len(items), 1) if items else 0.0
    if total:
        print(f"  Failure summary: {total} failures across {unique} unique top-level reasons")
        print("  Top failure reasons:")
        for reason, count in reason_counts.most_common(5):
            pct = 100.0 * count / total
            print(f"    {count:4d} ({pct:5.1f}%)  {reason[:80]}")
    else:
        print("  Failure summary: 0 failures")
    if items:
        print(f"  Asset mix: doors={doors} load_doors={load_doors} movables={movables} avg_shapes={avg_shapes}")
    # Always persist a compact summary (including the zero case) so tooling sees the latest run
    summary = {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "attempted": attempted,
        "successes": len(items),
        "success_percent": round(success_pct, 1),
        "total_failures": total,
        "unique_reasons": unique,
        "reused": reused,
        "skipped": skipped,
        "seconds": elapsed,
        "limit": a.limit,
        "pattern": a.pattern,
        "doors": doors,
        "load_doors": load_doors,
        "movables": movables,
        "total_shapes": total_shapes,
        "avg_shapes": avg_shapes,
        "top": [{"reason": r, "count": c, "percent": round(100.0 * c / total, 1) if total else 0.0}
                for r, c in reason_counts.most_common(10)],
        "reasons": {r: c for r, c in reason_counts.most_common()},
        "examples": {r: examples[r] for r in reason_counts},
    }
    write_json_atomic(os.path.join(a.staging, "failure-summary.json"), summary)

    tex_totals = None
    if textures.parse_texture_caps(a.max_texture):
        tex_totals = texture_totals(merge_texture_log(a.staging, conv.texture_log if conv else {}))
        print(f"textures (all runs): {tex_totals}")
    if cache:
        inconsistent = cache.verify_batch()
        if inconsistent:
            write_json_atomic(state_path, {"complete": False, "status": "dependency_conflict", "errors": inconsistent})
            raise RuntimeError(f"{len(inconsistent)} generated dependencies changed after model conversion; build not deployable")
    stats = dict(conv.stats) if conv else {"materials_ok": 0, "materials_fallback": 0}
    stats.update(assets=len(items), failed=len(failures), reused=reused)
    if tex_totals is not None:
        stats["textures"] = dict(tex_totals, caps=textures.parse_texture_caps(a.max_texture))
    manifest = {"items": items, "failures": failures, "material_fallbacks": conv.material_errors if conv else {}, "stats": stats,
                "seconds": round(time.time() - t0, 1)}
    os.makedirs(a.staging, exist_ok=True)
    write_json_atomic(os.path.join(a.staging, "editorids.json"), ids)
    write_json_atomic(os.path.join(a.staging, "manifest.json"), manifest)
    write_json_atomic(state_path, {"complete": True, "status": "finished", "assets": len(items), "failed": len(failures)})
    print(json.dumps({"converted": len(items), **stats, "seconds": manifest["seconds"]}))


if __name__ == "__main__":
    main()
