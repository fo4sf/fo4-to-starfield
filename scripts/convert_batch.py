"""Convert many Fallout 4 statics straight from the game's archives into a Starfield staging folder.

usage: python convert_batch.py --fo4-data <Fallout 4 Data dir> --staging <out dir> --content-resources <ContentResources.zip>
                               --texconv <Texconvx64.exe> --collision-template <vanilla box-collision Starfield .nif>
                               [--pattern "setdressing/(chair|stool)"] [--limit 40] [--manifest manifest.json]
Writes <staging>/manifest.json: converted items (EditorID + model path for the plugin writer), failures with reasons, stats.
With --cell-json, references whose FO4 ragdoll data (XRGD) poses their model away from its node pose get a posed model of
their own (src/fo4sf/placed_pose.py): extra items with "pose": {"kind": "xrgd", "refs": [FO4 FormKeys]}, which the plugin
writer places for those references only; manifest "poses" counts every reference with ragdoll data. --no-ref-poses: off.
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
from fo4sf import ba2, checkpoints, convert_static, exterior, meshcollision, nif, pipeline, placed_pose, sfcollision, sfnif, textures  # noqa: E402


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
    sig = {"version": 1, "python": sys.version, "packages": packages,
           "archives": [checkpoints.archive_identity(p) for p in archives],
           "content": {str(p.resolve()): checkpoints.digest(p) for p in
                       [*code, Path(a.texconv), Path(a.content_resources), Path(a.collision_template)]},
           "rig_doors": bool(a.starfield_data), "movable_items": bool(a.starfield_data) and not a.static_items}
    if getattr(a, "prefix", "fo4port") != "fo4port":   # output paths differ; the default keeps existing checkpoints valid
        sig["prefix"] = a.prefix
    if getattr(a, "door_anim_dll", "") and a.starfield_data:   # multi-part doors get their own rig and clips
        sig["door_anim_dll"] = checkpoints.digest(Path(a.door_anim_dll))
    if getattr(a, "rig_load_doors", False) and a.starfield_data:   # load doors rigged; off keeps checkpoints valid
        sig["rig_load_doors"] = True
    extra = [Path(d) for d in getattr(a, "extra_data", None) or []]
    if extra:                                           # DLC archives, in lookup order; none keeps existing checkpoints valid
        sig["extra_archives"] = [[str(d.resolve()), [checkpoints.archive_identity(p) for p in sorted(
            (p for p in d.iterdir() if p.name.lower().startswith("dlc") and p.suffix.lower() == ".ba2"),
            key=lambda p: p.name.lower())]] for d in extra]
    if getattr(a, "spec_mask_roughness", False):        # rougher outputs differ; off keeps existing checkpoints valid
        sig["spec_mask_roughness"] = True
    if getattr(a, "mass_scale", 1.0) != 1.0:            # scaled masses differ; default 1.0 keeps existing checkpoints valid
        sig["mass_scale"] = a.mass_scale
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
                if "pose" not in item:          # posed variants share their base's source; their names derive from it
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


DEFAULT_CELL_TYPES = "Static,StaticCollection,MovableStatic,Furniture,Door,Activator,Container,MiscItem,Terminal"


def cell_candidates(cell, wanted):
    """The meshes --cell-json converts for one cell export: 'meshes\\' + model of every reference whose base type is in
    wanted, without editor markers, effect meshes (fog / light volumes) and placed water planes, sorted
    case-insensitively, each once. A water plane (Water\\*.nif: a BSWaterShaderProperty quad plus an L_WATER body) is out
    for the reason the exterior path already leaves it out (exterior.WATER_RE): as a static it is an opaque flat grey sheet
    (the neutral fallback material) AND a solid floor, because the converted L_WATER body supports the player (Vault 111
    gear pit: the player stood on the sheet 0.44 m above the real floor; docs/JOURNAL.md 2026-10-17)."""
    return sorted({"meshes\\" + r["model"].lstrip("\\") for r in cell["refs"] if r["model"] and r["type"] in wanted
                   and not re.search(r"marker|^\\?effects[\\/]", r["model"], re.I)   # editor markers, fog/light volumes
                   and not exterior.WATER_RE.search(r["model"])},                    # water planes (see the docstring)
                  key=str.lower)


def teleport_models(cell):
    """The meshes FO4 places in this cell as a teleporting door ('meshes\\' + model of every Door reference with an XTEL):
    load doors for the converter whatever their file name (pipeline.Converter load_door_models)."""
    return sorted({"meshes\\" + r["model"].lstrip("\\") for r in cell["refs"] if r.get("model") and r.get("type") == "Door"
                   and r.get("teleport_destination")}, key=str.lower)


def static_body_models(cell):
    """The meshes a cell export marks "static_body" (make_core64c convert_list: placed outdoors as STAT only, never as an
    item): they keep a static body though movable items get dynamic ones (pipeline.Converter static_body_models)."""
    return sorted({"meshes\\" + r["model"].lstrip("\\") for r in cell["refs"] if r.get("model") and r.get("static_body")},
                  key=str.lower)


def static_pattern_models(pattern, names):
    """--static-pattern: the candidate names matching a regex, or, for "@file", the names listed in that file (one mesh
    name per line, as a manifest prints them; case and slashes ignored)."""
    if pattern.startswith("@"):
        with open(pattern[1:], encoding="utf-8-sig") as f:
            wanted = {line.strip().replace("/", "\\").lower() for line in f if line.strip()}
        return {n for n in names if n.replace("/", "\\").lower() in wanted}
    return {n for n in names if re.search(pattern, n, re.I)}


def triangle_count(src_archives, name):
    """Rough triangle count from a FO4 NIF (sum of decoded BSTriShape triangles). Used by --max-tris."""
    try:
        raw = src_archives.mesh(name)
        parsed = nif.parse(raw)
        shapes = nif.fo4_trishapes(parsed)
        return sum(len(s.triangles) for s in shapes if s.triangles)
    except Exception:  # noqa: BLE001
        return 0  # let the real converter report the failure


def checkpoint_key(key, name, load_models, static_models, no_rig_models=()):
    """The checkpoint identity of one conversion: the mesh (or posed-variant) key plus the record-driven classes that
    change its output (load door, static body), so a cell export that reclassifies a mesh is a cache miss (Codex review
    of #354: a RoofHatch01 primed without an XTEL was reused, without load_door, after its XTEL appeared). A mesh in
    neither class keeps its plain key, so existing checkpoints stay valid. no_rig_models (--no-rig-pattern) tags the
    same way."""
    low = name.replace("/", "\\").lower()
    tags = [t for t, models in (("load_door", load_models), ("static_body", static_models), ("no_rig", no_rig_models))
            if low in {m.replace("/", "\\").lower() for m in models}]
    return "|".join([key] + tags)


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


def retry_failed_nifs(summary):
    """Exact previous-failure identities, or None if the summary cannot drive a retry."""
    names = summary.get("failed_nifs") if isinstance(summary, dict) else None
    if not isinstance(names, list) or any(not isinstance(n, str) or not n for n in names):
        return None
    seen, ordered = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            ordered.append(n)
    return ordered


def item_identity(it):
    """Base vs posed-variant identity. XRGD rows share source with the base and must stay distinct."""
    src = it.get("source") if isinstance(it, dict) else None
    if not isinstance(src, str) or not src:
        return None
    key = source_identity(src)
    pose = it.get("pose") if isinstance(it.get("pose"), dict) else None
    if pose:
        kind = pose.get("kind")
        pk = pose.get("key")
        if isinstance(kind, str) and kind and pk not in (None, ""):
            return (key, kind, str(pk))
    return (key, "", "")


def retry_nif_identity(nif):
    """Canonical identity for a failed_nifs / failure nif string. Pose rows are source|kind:key."""
    if not isinstance(nif, str) or not nif:
        return None
    if "|" in nif:
        src, rest = nif.split("|", 1)
        if ":" in rest:
            kind, pk = rest.split(":", 1)
            if src and kind and pk != "":
                return (source_identity(src), kind, str(pk))
    return (source_identity(nif), "", "")


def retry_pending_idents(pending):
    return {ident for ident in (retry_nif_identity(n) for n in pending) if ident}


def retry_pending_sources(pending):
    """Base NIF sources a retry must convert, including parents of pose-only pending keys."""
    return {ident[0] for ident in retry_pending_idents(pending)}


def _failure_by_identity(rows):
    out = {}
    for f in rows:
        if isinstance(f, dict) and f.get("nif"):
            ident = retry_nif_identity(f["nif"])
            if ident:
                out[ident] = f
    return out


def extend_pending_from_manifest(pending, prior):
    """Until summary and manifest agree, keep unresolved identities from both."""
    extra = []
    if isinstance(prior, dict):
        for f in prior.get("failures") or []:
            if isinstance(f, dict) and isinstance(f.get("nif"), str) and f["nif"]:
                extra.append(f["nif"])
    seen = set(pending)
    out = list(pending)
    for n in extra:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def merge_retry_stage(prior, new_items, new_failures, pending_nifs):
    """Keep prior successes; fold this retry in by base/pose identity; drop only proven successful retries."""
    prior = prior if isinstance(prior, dict) else {}
    items = [dict(it) for it in (prior.get("items") or []) if isinstance(it, dict) and item_identity(it)]
    by_id = {item_identity(it): i for i, it in enumerate(items)}
    next_index = max((it.get("form_index", -1) for it in items), default=-1) + 1
    for it in new_items:
        row = dict(it)
        ident = item_identity(row)
        if not ident:
            continue
        if ident in by_id:
            old = items[by_id[ident]]
            row["form_index"] = old.get("form_index", by_id[ident])
            if old.get("editor_id"):
                row["editor_id"] = old["editor_id"]
            items[by_id[ident]] = row
        else:
            row["form_index"] = next_index
            next_index += 1
            by_id[ident] = len(items)
            items.append(row)
    succeeded = {item_identity(it) for it in new_items if item_identity(it)}
    now_fail = _failure_by_identity(new_failures)
    prior_fail = _failure_by_identity(prior.get("failures") or [])
    failures = []
    seen = set()
    ordered = list(pending_nifs)
    for f in new_failures:
        if isinstance(f, dict) and f.get("nif"):
            ordered.append(f["nif"])
    for n in ordered:
        ident = retry_nif_identity(n)
        if not ident or ident in seen:
            continue
        seen.add(ident)
        if ident in succeeded:
            continue
        if ident in now_fail:
            failures.append(now_fail[ident])
        elif ident in prior_fail:
            failures.append(prior_fail[ident])
        else:
            failures.append({"nif": n, "reason": "unattempted retry"})
    return items, failures


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
                         "than one part (double doors, shutters, sliding panel sets) and sliding / lifting / trapdoor "
                         "doors (vault, elevator, hatch) get their own rig and Open/Close clips; without it the first "
                         "keep the single-hinge template and list the parts that stay closed, the second stay passable")
    ap.add_argument("--extra-data", action="append", default=[],
                    help="another Data folder whose DLC*.ba2 archives are read after the base game's (a DLC's depot "
                         "Data); base-game models keep converting from Fallout4 - *.ba2 first. The folders and their "
                         "DLC*.ba2 identities, in order, join the checkpoint signature (none: existing checkpoints stay valid)")
    ap.add_argument("--rig-load-doors", action="store_true",
                    help="with --starfield-data: FO4 load doors whose model animates are rigged like other doors and "
                         "open before the trip (manifest load_door.anim; docs/spikes/load-door-animations.md). Off by "
                         "default: load doors stay graph-less static doors")
    ap.add_argument("--no-rig-pattern", default="",
                    help="regex over mesh names: these doors skip their own rig (as without --door-anim-dll), only they "
                         "reconvert on --resume once the checkpoints match this code (the signature digests src/fo4sf and this "
                         "script, so the first run after a code change reconverts everything; crash bisects: v6 Red "
                         "Rocket, 2026-10-19)")
    ap.add_argument("--static-pattern", default="",
                    help="regex over mesh names, or @file listing mesh names: these keep a static body though items "
                         "are movable; only they reconvert on --resume once the checkpoints match this code (as --no-rig-pattern)")
    ap.add_argument("--resume", action="store_true", help="reuse content-verified per-model checkpoints")
    ap.add_argument("--pattern", default=r"^meshes[\\/]setdressing[\\/]")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--max-tris", type=int, default=0,
                    help="skip meshes with more triangles than this (0, the default: skip none). Off by default: "
                         "the option was inert until 5f2a065, and a skipped model drops its base record, so a build "
                         "that turned it on would renumber or lose records an earlier build kept")
    ap.add_argument("--retry-failures", action="store_true",
                    help="only process NIFs that failed in the previous run (from failure-summary.json)")
    ap.add_argument("--cell-json", default="", help="convert the models placed in a cell exported by dotnet/Fo4Export")
    ap.add_argument("--no-ref-poses", action="store_true",
                    help="with --cell-json: place every reference with its base's shared model, ignoring FO4 ragdoll "
                         "poses (XRGD); default: references the pose moves get a posed model of their own")
    ap.add_argument("--types", default=DEFAULT_CELL_TYPES, help="base record types to take from --cell-json")
    ap.add_argument("--prefix", default="fo4port",
                    help="folder under meshes/, materials/ and textures/ for the converted files (another plugin's own "
                         "archive needs its own prefix, so two archives never hold different files at the same path)")
    ap.add_argument("--max-texture", default="",
                    help="cap converted textures by dropping top mip levels: one size for every kind ('1024') or per "
                         "kind ('color=1024,normal=512,rough=256,opacity=512'); default: full resolution. The full and "
                         "written size of every texture go to <staging>/texture_log.json")
    ap.add_argument("--spec-mask-roughness", action="store_true",
                    help="roughness also follows FO4's specular mask (smooth-spec R), so dull surfaces with high gloss "
                         "stay rough; default off (the gloss alone, as every build so far)")
    ap.add_argument("--mass-scale", type=float, default=1.0,
                    help="scale FO4 dynamic body masses (playtest row 26: FO4 small items 2-10x Starfield; try 0.2-0.5 so grab works)")
    a = ap.parse_args()
    if not re.fullmatch(r"[a-z0-9_]+", a.prefix):
        ap.error("--prefix: lower-case letters, digits and _ only")
    try:
        a.mass_scale = convert_static.require_mass_scale(a.mass_scale)
    except ValueError as e:
        ap.error(f"--mass-scale: {e}")
    try:
        textures.parse_texture_caps(a.max_texture)
    except ValueError as e:
        ap.error(f"--max-texture: {e}")
    if a.door_anim_dll and not os.path.isfile(a.door_anim_dll):
        ap.error("--door-anim-dll: file not found")
    if a.door_anim_dll and not a.starfield_data:
        ap.error("--door-anim-dll needs --starfield-data (doors are rigged only with the vanilla donor body)")
    if a.rig_load_doors and not a.starfield_data:
        ap.error("--rig-load-doors needs --starfield-data (doors are rigged only with the vanilla donor body)")

    ids = load_editor_ids(a.staging)

    t0 = time.time()
    src = pipeline.Fo4Archives(a.fo4_data, a.extra_data)
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
        names = cell_candidates(cell, set(a.types.split(",")))
        load_models = teleport_models(cell)
        static_models = static_body_models(cell)
    else:
        names = src.mesh_names(a.pattern)
        load_models = static_models = []
    no_rig_models = [n for n in names if a.no_rig_pattern and re.search(a.no_rig_pattern, n, re.I)]
    if a.static_pattern:
        static_models = sorted(set(static_models) | static_pattern_models(a.static_pattern, names), key=str.lower)
    pending_retry = None
    prior_manifest = None
    if a.retry_failures:
        summary_path = os.path.join(a.staging, "failure-summary.json")
        if not os.path.exists(summary_path):
            sys.exit(f"--retry-failures: missing {summary_path}; stage not changed")
        with open(summary_path, encoding="utf-8") as f:
            prev_summary_raw = f.read()
        try:
            prev_summary = json.loads(prev_summary_raw)
        except json.JSONDecodeError:
            sys.exit("--retry-failures: failure-summary.json is not JSON; stage not changed")
        pending_retry = retry_failed_nifs(prev_summary)
        if pending_retry is None:
            sys.exit("--retry-failures: failure-summary.json has no failed_nifs list; stage not changed")
        man_path = os.path.join(a.staging, "manifest.json")
        if os.path.exists(man_path):
            with open(man_path, encoding="utf-8") as f:
                prior_manifest = json.load(f)
        pending_retry = extend_pending_from_manifest(pending_retry, prior_manifest or {})
        pending_sources = retry_pending_sources(pending_retry)
        names = [n for n in names if source_identity(n) in pending_sources]
        print(f"  retry-failures: narrowed to {len(names)} previous failures")
    print(f"{len(names)} candidate meshes; converting up to {a.limit}")
    os.makedirs(a.staging, exist_ok=True)
    state_path = os.path.join(a.staging, "build-state.json")
    write_json_atomic(state_path, {"complete": False, "status": "converting"})
    items, failures, reused = [], [], 0
    attempted_so_far = 0
    skipped = 0
    progress_every = 10
    for name in names:
        if len(items) >= a.limit:
            break
        if not a.cell_json and re.search(r"(lod|_dmg|damaged|destr)", name, re.I):
            skipped += 1
        else:
            ckey = checkpoint_key(name, name, load_models, static_models, no_rig_models)
            # Apply --max-tris: skip heavy meshes before the expensive conversion
            if a.max_tris and triangle_count(src, name) > a.max_tris:
                skipped += 1
                print(f"  skip {name}: > {a.max_tris} triangles")
                continue
            r = cache.load(ckey) if cache else None
            if r is not None:
                reused += 1
            else:
                if conv is None:
                    conv = pipeline.Converter(src, a.staging, a.texconv, a.content_resources, template,
                                              rig_doors=donor is not None, door_physics_donor=donor,
                                              sf_mesh_template=mesh_template, dynamic_template=dynamic_template,
                                              prefix=a.prefix, max_texture=a.max_texture,
                                              door_anim_dll=a.door_anim_dll or None,
                                              spec_mask_roughness=a.spec_mask_roughness,
                                              mass_scale=a.mass_scale, load_door_models=load_models,
                                              static_body_models=static_models,
                                              no_rig_models=no_rig_models, rig_load_doors=a.rig_load_doors)
                r = conv.convert_nif(name)
                if cache:
                    try:
                        cache.save(ckey, r)
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
        if (attempted_so_far + skipped) % progress_every == 0:
            elapsed_now = time.time() - t0
            rate = attempted_so_far / elapsed_now if elapsed_now > 0 else 0
            print(f"  progress: {attempted_so_far} attempted ({len(items)} ok, {len(failures)} fail, {skipped} skipped) "
                  f"in {elapsed_now:.0f}s ({rate:.1f}/s)")
    pose_stats = None
    if a.cell_json and not a.no_ref_poses:
        # FO4 ragdoll poses (XRGD): one posed model per distinct pose that moves its model (skeletons lying down)
        by_source = {source_identity(it["source"]).replace("/", "\\"): it for it in items}
        variants, pose_stats = placed_pose.plan(cell["refs"], by_source, lambda name: src.mesh(name))
        pending_idents = retry_pending_idents(pending_retry) if pending_retry is not None else None
        for v in variants:
            pose_ident = (source_identity(v.source), "xrgd", str(v.key))
            base_ident = (source_identity(v.source), "", "")
            if pending_idents is not None and pose_ident not in pending_idents and base_ident not in pending_idents:
                continue
            base = by_source[source_identity(v.source).replace("/", "\\")]
            key = checkpoint_key(f"{v.source}|xrgd:{v.key}", v.source, load_models, static_models, no_rig_models)
            r = cache.load(key) if cache else None
            if r is not None:
                reused += 1
            else:
                if conv is None:
                    conv = pipeline.Converter(src, a.staging, a.texconv, a.content_resources, template,
                                              rig_doors=donor is not None, door_physics_donor=donor,
                                              sf_mesh_template=mesh_template, dynamic_template=dynamic_template,
                                              prefix=a.prefix, max_texture=a.max_texture,
                                              door_anim_dll=a.door_anim_dll or None,
                                              spec_mask_roughness=a.spec_mask_roughness,
                                              mass_scale=a.mass_scale, load_door_models=load_models,
                                              static_body_models=static_models,
                                              no_rig_models=no_rig_models, rig_load_doors=a.rig_load_doors)
                r = conv.convert_nif(v.source, pose=v.overrides, out_suffix=v.suffix)
                if cache:
                    try:
                        cache.save(key, r)
                    except (OSError, ValueError) as e:
                        print(f"  checkpoint unavailable for {key}: {e}")
            if not r["ok"]:
                failures.append({"nif": key, "reason": r["reason"]})
                pose_stats["posed_refs"] -= len(v.refs)
                pose_stats["failed_refs"] = pose_stats.get("failed_refs", 0) + len(v.refs)
                continue
            items.append({"editor_id": base["editor_id"] + v.suffix, "model": r["out_name"].replace("/", "\\") + ".nif",
                          "source": v.source, "shapes": r["shapes"], "fallback_materials": r["fallback_materials"],
                          "form_index": len(items), "collision_report": r.get("collision_report") or {},
                          **({"movable": r["movable"]} if "movable" in r else {}),
                          "pose": {"kind": "xrgd", "key": v.key, "refs": sorted(v.refs), "nodes": len(v.overrides),
                                   "shift_units": round(v.shift, 2)}})
        print(f"  ragdoll poses: {json.dumps(pose_stats)}")
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
            if examples[reason]:
                print(f"      examples: {', '.join(examples[reason][:3])}")
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
        "failed_nifs": [f["nif"] for f in failures],
    }
    if pending_retry is not None:
        items, failures = merge_retry_stage(prior_manifest or {}, items, failures, pending_retry)
        total = len(failures)
        unique = len(Counter(f["reason"].split(":")[0].strip() for f in failures))
        attempted = len(items) + total
        success_pct = 100.0 * len(items) / attempted if attempted else 100.0
        summary["attempted"] = attempted
        summary["successes"] = len(items)
        summary["success_percent"] = round(success_pct, 1)
        summary["total_failures"] = total
        summary["unique_reasons"] = unique
        summary["failed_nifs"] = [f["nif"] for f in failures]
        summary["top"] = [{"reason": r, "count": c, "percent": round(100.0 * c / total, 1) if total else 0.0}
                          for r, c in Counter(f["reason"].split(":")[0].strip() for f in failures).most_common(10)]
        summary["reasons"] = {r: c for r, c in Counter(f["reason"].split(":")[0].strip() for f in failures).most_common()}

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
                "seconds": round(time.time() - t0, 1), **({"poses": pose_stats} if pose_stats is not None else {})}
    os.makedirs(a.staging, exist_ok=True)
    write_json_atomic(os.path.join(a.staging, "editorids.json"), ids)
    write_json_atomic(os.path.join(a.staging, "manifest.json"), manifest)
    write_json_atomic(os.path.join(a.staging, "failure-summary.json"), summary)
    finished = not (pending_retry is not None and failures)
    write_json_atomic(state_path, {"complete": finished, "status": "finished" if finished else "retry_pending",
                                   "assets": len(items), "failed": len(failures)})
    print(json.dumps({"converted": len(items), **stats, "seconds": manifest["seconds"]}))


if __name__ == "__main__":
    main()
