"""stage_ra5_creatures.py: probe bundle "RA5 creatures": Fallout 4 creatures on their own Fallout 4 rigs, clips and
meshes in Starfield, the generic version of the Mr. Handy probe (stage_ra2_handy.py, bundle E2, which ran in game).

    python scripts/probes/stage_ra5_creatures.py build     [--out D:\\FO4SF-Owner-Tests\\robot-anim\\RA5]
                                                           [--creatures radroach,bloatfly,...] [--no-materials]
    python scripts/probes/stage_ra5_creatures.py verify    [--stage-dir ...]
    python scripts/probes/stage_ra5_creatures.py deform    [--stage-dir ...]       edge stretch, every clip and frame
    python scripts/probes/stage_ra5_creatures.py install   --starfield <game dir> [--stage-dir ...] [--plugins-txt ...]
    python scripts/probes/stage_ra5_creatures.py uninstall --starfield <game dir> [--plugins-txt ...]
    python scripts/probes/stage_ra5_creatures.py status    --starfield <game dir>

build writes, under <out>:
  Data\\                          loose files in the layout the records point at:
    Meshes\\FO4SF\\Actors\\<Name>\\<name>.nif, CharacterAssets\\skeleton.nif / skeleton_ref.nif / skeleton.rig
    Meshes\\Actors\\FO4SF\\<Name>\\Animations\\<clip>.af + .afx
    Meshes\\AnimTextData\\...      the race's own sub-graph manifests (fo4sf.creature_race.creature_manifests)
    geometries\\*.mesh, materials\\fo4sfcreatures\\..., textures\\fo4sfcreatures\\...  (converted Fallout 4 look)
  FO4SF_RA5Creatures.esm          master Starfield.esm only: per creature RACE, BPTD, ARMA, ARMO and a hostile NPC_
  FO4SF_RA5Creatures - Main.ba2   every file under Data (GNRL, uncompressed)
  bat\\ra5*.txt                    console batch files with an XX load-order placeholder (install stamps real copies)
  report.json, manifest.json      measurements; SHA-256 and size of every staged file
  work\\                           graph tag sets, per-creature mesh reports

The conversion rules are stage_ra2_handy's (FO4 units / 70 = metres, both games Z up / +Y forward, 30 fps, root motion
from hkaDefaultAnimatedReferenceFrame as the Root track plus the .af header copy) and convert_creature's rig rules
(COM inserted when missing, bones with translation keys rebased to an identity rest, DirectAt on COM, safe names).
install / uninstall never run as part of build; Starfield must not be running.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import struct
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
for _p in (str(REPO / "src"), str(REPO / "scripts" / "actors"), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fo4sf import actor_anim as aa  # noqa: E402
from fo4sf import creature_race as cr  # noqa: E402
from fo4sf import handy_race as hr  # noqa: E402
from fo4sf.ba2 import Ba2  # noqa: E402
from fo4sf.planet import esm  # noqa: E402
import stage_ra2_handy as ra2  # noqa: E402

STARFIELD_DIR = ra2.STARFIELD_DIR
FO4_DATA = ra2.FO4_DATA
OWNER_TESTS = Path(r"D:\FO4SF-Owner-Tests")
OUT = OWNER_TESTS / "robot-anim" / "RA5"
TEXCONV = Path(r"C:\Modding\tools\xedit\Edit Scripts\texconv.exe")
PROBE = "ra5-creatures"
PLUGIN = "FO4SF_RA5Creatures.esm"
MAIN_BA2 = "FO4SF_RA5Creatures - Main.ba2"
RECEIPT = "FO4SF_RA5Creatures.install.json"
BACKUP = "backup_pre_ra5"
MATERIAL_PREFIX = "fo4sfcreatures"
UNIT = ra2.UNIT
FPS = ra2.FPS
RIG_KEYS = {"Root": 0, "COM": 9, "DirectAt": 137}        # the keys the Handy rig ran with (vanilla Mini Bot's)
ORDER = ("radroach", "bloatfly", "molerat", "dog", "deathclaw")   # fixed: form id block k = 0x800 + 5 k
REQUIRED_TAGS = ("Idle", "WalkForward", "TurnInPlace_Left90", "TurnInPlace_Right90", "Death_Backward01")
SF_NPC_TEMPLATE = 0x000C1F50      # EncMiniBotA01Template: killable, no template, aggressive (copy_npc: Very Aggressive)
PAIR_TOL_M = 0.03                 # left / right partner: mirrored rest position within this or 5 % of the size
ROOT_GRAPHS = ("creature_root.agx", "critter_root.agx")


class Ra5Error(ValueError):
    pass


def form_ids(key: str) -> Dict[str, int]:
    k = ORDER.index(key)
    base = 0x800 + 5 * k
    return {"RACE": base, "BPTD": base + 1, "ARMA": base + 2, "ARMO": base + 3, "NPC_": base + 4}


def edids(spec: cr.CreatureSpec) -> Dict[str, str]:
    n = spec.name
    return {"RACE": f"FO4SF_{n}Race", "BPTD": f"FO4SF_{n}BodyPartData", "ARMA": f"FO4SF_RA5{n}_AA",
            "ARMO": f"FO4SF_RA5{n}_Skin", "NPC_": f"FO4SF_RA5{n}Test"}


def check_out_dir(out: Path) -> Path:
    out = ra2.check_out_dir(out)
    o, ot = os.path.normcase(str(out)), os.path.normcase(str(OWNER_TESTS))
    if (o == ot or o.startswith(ot + os.sep)) and not (o == os.path.normcase(str(OUT))
                                                       or o.startswith(os.path.normcase(str(OUT)) + os.sep)):
        raise Ra5Error(f"under {OWNER_TESTS} only {OUT} may be written: {out}")
    return out


# =============================================================================================== frames on the rig
def remove_com_frames(frames, ins):
    """Inverse of convert_creature.insert_com_frames: poses on the insert_com skeleton -> source order (the COM pose of
    each frame composed back into the reparented bones)."""
    if ins is None:
        return [list(fr) for fr in frames]
    rep = set(ins.reparented)
    out = []
    for fr in frames:
        tc, qc = fr[ins.com]
        row = [fr[0]]
        for i in range(1, len(ins.new_index)):
            t, q = fr[ins.new_index[i]]
            row.append((ra2._add(tc, aa.q_rotate(qc, t)), aa.q_norm(aa.q_mul(qc, q))) if i in rep else (t, q))
        out.append(row)
    return out


class RigMap:
    """Source poses (skeleton.hkx order and names, metres) <-> poses on the written rig."""

    def __init__(self, rig, bones):
        import convert_creature as cc
        self.cc = cc
        self.rig = rig
        self.ins = rig.com
        self.corr_q = ra2.corrections_as_quats(rig.corrections)
        self.n_s1 = len(rig.corrections)
        self.parents_s1 = [b["parent"] for b in bones[:self.n_s1]]
        self.extra = [(b["translation"], b["rotation"]) for b in bones[self.n_s1:]]

    def to_rig(self, frames):
        s1 = self.cc.insert_com_frames(frames, self.ins)
        return [row + [tuple(x) for x in self.extra] for row in ra2.rebase_frames(s1, self.parents_s1, self.corr_q)]

    def to_source(self, frames):
        return remove_com_frames(ra2.unrebase_frames(frames, self.parents_s1, self.corr_q), self.ins)

    def source_index(self, i_src: int) -> int:
        return i_src if self.ins is None else self.ins.new_index[i_src]


def world_difference(parents_a, frames_a, parents_b, frames_b, index_b) -> float:
    """Largest world-position distance (m) between source bone i and rig bone index_b(i) over every frame."""
    worst = 0.0
    for fa, fb in zip(frames_a, frames_b):
        wa, wb = ra2.world_of(parents_a, fa), ra2.world_of(parents_b, fb)
        for i in range(len(fa)):
            worst = max(worst, math.dist(wa[i][0], wb[index_b(i)][0]))
    return worst


# =============================================================================================== shared sources
class Sources:
    """Everything read once: the archives, Starfield.esm records, vanilla manifest keys, measured graph tag sets,
    vanilla .afx by tag (templates for the clip sidecars)."""

    def __init__(self, starfield_dir: Path, fo4_data: Path, work: Path):
        sf = starfield_dir / "Data"
        self.sf_data = sf
        self.sfa = Ba2(str(sf / "Starfield - Animations.ba2"))
        self.fo4_anim = Ba2(str(fo4_data / "Fallout4 - Animations.ba2"))
        self.fo4_mesh = Ba2(str(fo4_data / "Fallout4 - Meshes.ba2"))
        self.races, self.bptd, self.src = {}, {}, {}
        with esm.Plugin(str(sf / "Starfield.esm")) as p:
            self.group_order = list(p.groups)
            for r in p.records("RACE"):
                self.races[r.edid] = r
            for r in p.records("BPTD"):
                self.bptd[r.formid] = r
            for g, fid in (("NPC_", SF_NPC_TEMPLATE), ("ARMA", ra2.SF_ARMA_GARDEN), ("ARMO", ra2.SF_ARMO_GARDEN)):
                self.src[g] = next(r for r in p.records(g) if r.formid == fid)
        self.vanilla_keys = cr.vanilla_manifest_keys(self.sfa.names)
        self._afx_cache: Dict[str, Optional[bytes]] = {}
        self.creature_races = [r for r in self.races.values()
                               if r.get(b"NAM6") and esm.zstring(r.get(b"NAM6")).split("\\")[-1].lower() in ROOT_GRAPHS]
        cache = work / "graph_tags.json"
        graphs = {g for r in self.creature_races for g, f in hr.race_subgraph_sets(r) if f}
        self.graph_tags = cr.graph_tag_sets(self.creature_races, self.read_manifest, self.afx_tag, graphs)
        cache.write_text(json.dumps({g: sorted(t) for g, t in sorted(self.graph_tags.items())}, indent=1), encoding="utf-8")

    def read_manifest(self, key: int) -> Optional[bytes]:
        i = self.sfa.find(f"meshes/animtextdata/animationfiledata/{key}.txt")
        return self.sfa.read(i) if i is not None else None

    def afx_raw(self, clip_path: str) -> Optional[bytes]:
        rel = "meshes/" + clip_path.replace("\\", "/").lower()
        rel = rel[:-3] + ".afx" if rel.endswith(".af") else rel + ".afx"
        if rel not in self._afx_cache:
            i = self.sfa.find(rel)
            self._afx_cache[rel] = self.sfa.read(i) if i is not None else None
        return self._afx_cache[rel]

    def afx_tag(self, clip_path: str) -> Optional[str]:
        raw = self.afx_raw(clip_path)
        return aa.parse_afx(raw)["tag"] if raw else None

    def afx_templates(self, template: esm.Record) -> Dict[str, Tuple[str, bytes]]:
        """{tag lower: (archive path, .afx)}: the template race's own folders first, then every creature race that
        plays one of the template's graphs (ra2.strafing_afx_templates for any graph)."""
        graphs = {g.lower() for g, f in hr.race_subgraph_sets(template) if f}
        folders = [f for g, fs in hr.race_subgraph_sets(template) for f in fs]
        for r in self.creature_races:
            for g, fs in hr.race_subgraph_sets(r):
                if g.lower() in graphs:
                    folders += [f for f in fs if f not in folders]
        by_folder: Dict[str, List[str]] = {}
        for n in self.sfa.names:
            low = n.lower().replace("\\", "/")
            if low.endswith(".afx"):
                by_folder.setdefault(os.path.dirname(low), []).append(n)
        out: Dict[str, Tuple[str, bytes]] = {}
        for f in folders:
            for n in sorted(by_folder.get(("meshes/" + f).lower().replace("\\", "/"), [])):
                raw = self.sfa.read(self.sfa.find(n))
                t = aa.parse_afx(raw)["tag"]
                if t and t.lower() not in out:
                    out[t.lower()] = (n, raw)
        return out

    def sf_mesh(self, rel: str) -> bytes:
        return ra2._read_archive(self.sf_data, "Starfield - Meshes*.ba2", rel)


# =============================================================================================== one creature
def build_creature(spec: cr.CreatureSpec, S: Sources, cal, data: Path, work: Path, materials_conv=None) -> dict:
    """Rig, mesh, clips, manifests and records of one creature. Returns {'records': [...], 'report': {...},
    'written': [WrittenClip]}."""
    import convert_creature as cc
    import convert_handy
    from fo4sf import actor_skin, nif as nifmod
    paths = cr.CreaturePaths(spec.name)
    fid = form_ids(spec.key)
    own = lambda local: (1 << 24) | local  # noqa: E731
    E = edids(spec)
    base = f"Meshes\\Actors\\{spec.fo4_folder}\\"
    rep: dict = {"name": spec.name, "fo4_race": spec.fo4_race, "template_race": spec.template_race,
                 "template_reason": spec.template_reason, "physics_race": spec.physics_race,
                 "form_ids_local": {k: f"{v:06X}" for k, v in fid.items()}, "edids": E}
    template = S.races[spec.template_race]
    physics = S.races[spec.physics_race]

    # ------------------------------------------------------------ source skeleton and the clips it plays
    skel_hkx = S.fo4_anim.read(S.fo4_anim.find(base + "CharacterAssets\\skeleton.hkx"))
    skel_fo4 = actor_skin.read_hka_skeleton(skel_hkx)
    pre = cc.build_rig(skel_fo4, strip_prefix=spec.strip_prefix)
    src = pre.source
    bones_src = ra2.rig_bones_from_skeleton(src, keys={})
    names_src = [b["name"] for b in bones_src]
    parents_src = [b["parent"] for b in bones_src]
    bind_src = [(b["translation"], b["rotation"]) for b in bones_src]
    cache: Dict[str, Tuple[ra2.Clip, dict]] = {}

    def source(rel: str) -> ra2.Clip:
        if rel not in cache:
            i = next((j for j in (S.fo4_anim.find("Meshes\\Actors\\" + f + "\\" + rel) for f in spec.clip_folders)
                      if j is not None), None)
            if i is None:
                raise Ra5Error(f"{spec.name}: no Fallout 4 clip {rel} in {spec.clip_folders}")
            raw = S.fo4_anim.read(i)
            info = hr.fo4_clip_info(raw)
            b = source("Idle.hkx") if rel.lower() != "idle.hkx" and _is_additive(raw) else None
            clip, st = ra2.decode_fo4_clip(raw, bones_src, names_src, base=b)
            root = resampled_root(raw, clip.n)
            if root is not None:            # ra2.decode_fo4_clip keeps root motion only when samples == frames
                clip.root = root
                clip.finish()
                st["root_motion_samples_resampled"] = True
            clip.source = rel
            st["fo4_info"] = {k: info[k] for k in ("duration", "frames", "transform_tracks", "root_motion")}
            cache[rel] = (clip, st)
        return cache[rel][0]

    usable = [c for c in spec.clips if c.how != "none" and c.fo4]
    for c in usable:
        source(c.fo4)
    world_src = ra2.world_of(parents_src, bind_src)
    size = max(max(p[0][a] for p in world_src) - min(p[0][a] for p in world_src) for a in range(3))
    pairs, pair_rep = cr.mirror_pairs(names_src, parents_src, [w[0] for w in world_src], max(PAIR_TOL_M, 0.05 * size))
    rep["mirror_pairs"] = pair_rep

    # ------------------------------------------------------------ the rig
    rebase = cc.bones_to_rebase(names_src, {k: v[0].frames for k, v in cache.items()}, bind_src, pre.com)
    rig = cc.build_rig(skel_fo4, rebase=rebase, strip_prefix=spec.strip_prefix)
    rep["rig"] = dict(rig.report)
    bones = ra2.rig_bones_from_skeleton(rig.skel, keys=RIG_KEYS)
    names = [b["name"] for b in bones]
    parents = [b["parent"] for b in bones]
    rm = RigMap(rig, bones)
    check = rm.to_rig([bind_src])[0]
    bind_err = max(max(math.dist(t, b["translation"]), aa.q_angle(q, b["rotation"])) for (t, q), b in zip(check, bones))
    if bind_err > 1e-5:
        raise Ra5Error(f"{spec.name}: rig bind and mapped source bind differ by {bind_err}")
    rig_path = data / "Meshes" / Path(*paths.skeleton_rig.split("\\"))
    cal.write_rig(bones, rig_path, name=f"FO4SF_{spec.name}Rig", precision="default")
    rr = cal.read_rig(str(rig_path))
    cmp_rig = aa.compare_rigs(bones, rr["bones"])
    rep["rig"].update({"path": paths.skeleton_rig, "bones": len(rr["bones"]), "precision": rr["precision"],
                       "keys": {b["name"]: b["key"] for b in rr["bones"] if b["key"] is not None},
                       "readback_max_translation_m": cmp_rig["max_translation"],
                       "readback_max_rotation_deg": math.degrees(cmp_rig["max_rotation"]),
                       "bind_paths_agree": bind_err, "names": names})

    # ------------------------------------------------------------ mesh and materials
    nif_raw = S.fo4_mesh.read(S.fo4_mesh.find("Meshes\\Actors\\" + spec.mesh))
    mats, mat_rep = {}, {"converted": {}, "stand_in": convert_handy.convert_static.PLACEHOLDER_MATERIAL, "errors": {}}
    if materials_conv is not None:
        n = nifmod.parse(nif_raw)
        for s in nifmod.fo4_trishapes(n, placed=True):
            sname = s.name.decode("latin-1")
            if spec.exclude_shapes and re.search(spec.exclude_shapes, sname, re.I):
                continue
            try:
                m = materials_conv._shape_material(n, s)
            except Exception as e:                        # noqa: BLE001 - recorded, stand-in used
                m, mat_rep["errors"][sname] = None, f"{type(e).__name__}: {e}"
            if m and m != materials_conv.neutral:
                mats[sname] = m
                mat_rep["converted"][sname] = m
    parts, exp_pos, exp_inf, part_rep = cc.creature_parts(nif_raw, rig, mats, spec.exclude_shapes)
    files, mesh_rep = cc.build_files(rig, parts, exp_pos, exp_inf, paths.data_rel(paths.mesh),
                                     paths.data_rel(paths.skeleton_nif), paths.data_rel(paths.skeleton_ref),
                                     spec.name.encode("ascii") + b"FO4", S.sf_mesh(convert_handy.SF_MESH_TEMPLATE),
                                     S.sf_mesh("meshes/" + esm.zstring(physics.get(b"ANAM")).replace("\\", "/").lower()))
    if not mesh_rep["ok"]:
        raise Ra5Error(f"{spec.name}: mesh conversion failed its checks: {mesh_rep['verify_mesh']['errors']}")
    for rel, raw in files.items():
        p = data / Path(*rel.split("/"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
    (work / f"mesh_{spec.key}.json").write_text(json.dumps({"parts": part_rep, "build": mesh_rep}, indent=1, default=str),
                                                encoding="utf-8")
    rep["mesh"] = {"files": sorted(files), "placed": part_rep["placed"], "skipped": part_rep["skipped"],
                   "bind_spread_max_fo4_units": part_rep["bind_spread_max_fo4_units"], "bound_m": mesh_rep["bound"],
                   "shapes": {k: {x: v[x] for x in ("verts", "weights_per_vertex", "bones", "bind_pose_max_error_mm",
                                                    "influence_histogram")}
                              for k, v in mesh_rep["verify_mesh"]["shapes"].items()},
                   "weighted_bones": mesh_rep["weighted_bones"], "unweighted_bones": mesh_rep["unweighted_bones"],
                   "physics_skeleton": esm.zstring(physics.get(b"ANAM")), "materials": mat_rep}
    shapes = ra2.load_skinned_shapes(data, paths.data_rel(paths.mesh))
    native = fo4_native_shapes(nif_raw, names_src, spec.exclude_shapes)

    # ------------------------------------------------------------ clips
    templates = S.afx_templates(template)
    clip_dir = data / "Meshes" / Path(*paths.clips.split("\\"))
    clip_dir.mkdir(parents=True, exist_ok=True)
    clips_rep, written, stretch = [], [], {}
    for cm in usable:
        src_clip = source(cm.fo4)
        notes = [(t, cr.mirror_event_name(x) if cm.how == "mirror" else x) for t, x in src_clip.annotations]
        clip = ra2.Clip(src_clip.frames, src_clip.root, notes, src_clip.source)
        if cm.frames is not None:
            clip = ra2.Clip(clip.frames[:cm.frames], clip.root[:cm.frames],
                            [(t, x) for t, x in clip.annotations if t <= (cm.frames - 1) / FPS + 1e-6], clip.source,
                            clip.notes + [f"first {cm.frames} frames"])
        if cm.crop_deg is not None:
            clip = ra2.crop_turn(clip, cm.crop_deg)
        if cm.how == "mirror":
            clip = ra2.mirror_clip(clip, bones_src, pairs)
        clip.finish()
        events = cr.creature_events(cm, clip.annotations, clip.n, event_map=dict(spec.event_map))
        rig_frames = rm.to_rig(clip.frames)
        res = aa.write_clip_files(cal, bones, ra2.poses_of_frames(rig_frames, bones), clip.n, clip_dir, cm.tag,
                                  keys_are="local", is_state=cm.is_state, events=events, stem=cm.filename)
        tpl = templates.get(cm.tag.lower())
        Path(res["afx"]).write_bytes(ra2.afx_vanilla(cm.tag, cm.filename + ".af", cm.is_state,
                                                     [(f, ra2.AFX_EVENT_SPELLING.get(nm, nm), pl) for f, nm, pl in events],
                                                     (), tpl[1] if tpl else None, frame_count=clip.n))
        rc, rb = ra2.readback_local(cal, rig_path, Path(res["af"]))
        hdr = aa.read_af_header(Path(res["af"]).read_bytes())
        if rc["frame_count"] != clip.n or hdr["frames"] != clip.n or hdr["bones"] != len(bones):
            raise Ra5Error(f"{spec.name} {cm.tag}: read-back frame or bone count differs")
        err = ra2.pose_errors(parents, names, rig_frames, rb)
        world_m = world_difference(parents_src, clip.frames, parents, rig_frames, rm.source_index)
        rule_m, rule_bone = ra2.translation_rule_exposure(bones, rig_frames)
        rb_src = rm.to_source(rb)
        rb_a = ra2.mirror_frames(rb_src, bind_src, parents_src, pairs) if cm.how == "mirror" else rb_src
        skip = ("Root",) if cm.crop_deg is not None else ()
        err_a = ra2.pose_errors(parents_src, names_src, src_clip.frames[:clip.n], rb_a, skip=skip)
        stem = Path(res["af"]).stem
        stretch[stem] = ra2.edge_stretch(shapes, parents, names, rb)
        nat = native_vs_staged(native, clip.frames, names_src, parents_src, shapes, rb, names, parents)
        side = aa.parse_afx(Path(res["afx"]).read_bytes())
        last = clip.root[-1]
        clips_rep.append({
            "tag": cm.tag, "file": Path(res["af"]).name, "fo4": cm.fo4, "how": cm.how, "crop_deg": cm.crop_deg,
            "notes": clip.notes + ([cm.note] if cm.note else []), "frames": clip.n, "blocks": res["blocks"],
            "header": {k: hdr[k] for k in ("version", "bones", "frames", "kind")},
            "root_end": {"xyz_m": [round(v, 4) for v in last[:3]], "yaw_deg": round(math.degrees(last[3]), 3)},
            "header_root_translation": [round(v, 4) for v in hdr["root_translation"]],
            "events": side["events"], "is_state": side["is_state"], "afx_template": tpl[0] if tpl else None,
            "err_vs_written_poses": err, "err_vs_fo4_decoded": err_a, "rig_vs_source_world_max_m": world_m,
            "translation_rule_difference_max_m": round(rule_m, 9), "translation_rule_bone": rule_bone,
            "stretch_max": max(v["ratio"] for v in stretch[stem].values()), "fo4_native": nat, "source_stats": {
                k: v for k, v in cache[cm.fo4][1].items() if k != "max_scale_dev"}})
        written.append(cr.WrittenClip(paths.clips, cm.filename + ".af", cm.tag, (clip.n - 1) / FPS,
                                      [(f, nm) for f, nm, _p in events]))
    tags = {c["tag"] for c in clips_rep}
    missing = [t for t in REQUIRED_TAGS if t not in tags]
    if missing:
        raise Ra5Error(f"{spec.name}: required tags not written: {missing}")
    rep["clips"] = clips_rep
    rep["clip_summary"] = {
        "written": len(clips_rep), "fo4_clips_used": sorted({c.fo4 for c in usable}),
        "fo4_clips_unused": sorted(_fo4_clip_names(S, spec) - {c.fo4.lower() for c in usable}),
        "worst_vs_written": {k: max(c["err_vs_written_poses"][k] for c in clips_rep) for k in ("t_m", "r_deg", "model_mm")},
        "worst_vs_fo4_decoded": {k: max(c["err_vs_fo4_decoded"][k] for c in clips_rep) for k in ("t_m", "r_deg", "model_mm")},
        "rig_vs_source_world_max_m": max(c["rig_vs_source_world_max_m"] for c in clips_rep),
        "translation_rule_difference_max_m": max(c["translation_rule_difference_max_m"] for c in clips_rep)}
    rep["deformation"] = ra2.summarize_stretch(stretch, shapes)
    rep["deformation"].pop("per_clip_shape", None)
    nats = [c["fo4_native"] for c in clips_rep]
    rep["deformation"]["fo4_native_all_clips"] = {
        "what": "Fallout 4's own skinning of the same shapes on the poses written (source frames) against the staged "
                "mesh on the clip read back, every clip / frame (worst edge ratio per frame)",
        "max_abs_diff": max(x["max_abs_diff"] for x in nats), "max_rel_diff": max(x["max_rel_diff"] for x in nats),
        "clips_native_over_limit": sorted(c["file"][:-3] for c in clips_rep if c["fo4_native"]["worst"] >= ra2.STRETCH_LIMIT),
        "same_set_as_staged": sorted(c["file"][:-3] for c in clips_rep if c["fo4_native"]["worst"] >= ra2.STRETCH_LIMIT)
        == rep["deformation"]["over_limit"]}

    # ------------------------------------------------------------ records and manifests
    tags_written = sorted(tags)
    race, race_rep = cr.build_creature_race(
        template, own(fid["RACE"]), own(fid["BPTD"]), own(fid["ARMO"]), paths, spec.name, E["RACE"], spec.bone_map,
        attack_tags=tags_written, main_folder_for_empty_sets=_empty_folders(template, paths, written))
    bptd_src = S.bptd[struct.unpack("<I", template.get(b"GNAM"))[0]]
    bptd = cr.build_creature_bptd(bptd_src, own(fid["BPTD"]), E["BPTD"], paths, spec.bone_map, names)
    bad = [b for b in cr.race_bone_names(race) if b not in names]
    if bad:
        raise Ra5Error(f"{spec.name}: race attack bones not in the rig: {bad}")
    files_m, man_rep = cr.creature_manifests(race, written, S.graph_tags)
    hr.write_files(files_m, str(data))
    keys = [int(k) for k in man_rep["keys"]]
    coll = cr.key_collisions(keys, S.vanilla_keys)
    if any(coll.values()):
        raise Ra5Error(f"{spec.name}: manifest keys used by vanilla files: {coll}")
    bound = mesh_rep["bound"]
    obnd = tuple(round(v, 4) for v in (bound[0][0] - bound[1][0], bound[0][1] - bound[1][1], 0.0,
                                       bound[0][0] + bound[1][0], bound[0][1] + bound[1][1], bound[0][2] + bound[1][2]))
    arma = ra2.copy_arma(S.src["ARMA"], own(fid["ARMA"]), E["ARMA"], own(fid["RACE"]), paths.mesh)
    armo = ra2.copy_armo(S.src["ARMO"], own(fid["ARMO"]), E["ARMO"], own(fid["RACE"]), own(fid["ARMA"]))
    npc, npc_rep = ra2.copy_npc(S.src["NPC_"], own(fid["NPC_"]), E["NPC_"], f"{spec.name} (FO4 test)", own(fid["RACE"]),
                                own(fid["ARMO"]), obnd)
    rep["records"] = {"race": race_rep, "bptd_bones": cr.bptd_bones(bptd), "npc": npc_rep, "obnd": obnd,
                      "attack_bones": cr.race_bone_names(race)}
    rep["manifests"] = {"files": sorted(files_m), **man_rep, "vanilla_key_collisions": coll}
    return {"records": [race, bptd, arma, armo, npc], "report": rep, "written": written}


def fo4_native_shapes(nif_bytes: bytes, names_src: Sequence[str], exclude: str, unit: float = UNIT) -> List[dict]:
    """The shapes creature_parts converts, as Fallout 4 skins them (stored skin-space positions, its own skin-to-bone
    transforms and normalised weights), in metres, bones as source (skeleton.hkx) names: ra2.fo4_part_shapes for any
    creature NIF."""
    import numpy as np
    from fo4sf import fo4skin, nif as nifmod
    low = {x.lower(): i for i, x in enumerate(names_src)}
    n = nifmod.parse(nif_bytes)
    out = []
    for s in nifmod.fo4_trishapes(n, placed=True):
        sname = s.name.decode("latin-1")
        if (exclude and re.search(exclude, sname, re.I)) or s.shader_ref < 0 \
                or n.type_of(s.shader_ref) != "BSLightingShaderProperty":
            continue
        skin = fo4skin.read_skin(n, s.block)
        if skin is None:
            continue
        bones = [low[b.decode("latin-1").lower()] for b in skin.bone_names]
        bd = np.zeros((len(bones), 3, 4))
        for k, (t, r, sc) in enumerate(skin.skin_to_bone):
            bd[k, :, :3] = np.array(r, dtype=float).reshape(3, 3) * sc
            bd[k, :, 3] = tuple(c * unit for c in t)
        w = np.array([[float(x) for x in ws] for ws in skin.weights])
        w = w / np.maximum(w.sum(axis=1, keepdims=True), 1e-12)
        pts = np.array(s.positions, dtype=float) * unit
        edges = np.array(sorted({(min(u, v), max(u, v)) for a, b, c in s.triangles for u, v in ((a, b), (b, c), (c, a))}))
        l0 = np.linalg.norm(pts[edges[:, 0]] - pts[edges[:, 1]], axis=1)
        keep = l0 > ra2.STRETCH_MIN_EDGE_M
        out.append({"name": re.sub(r"[^A-Za-z0-9_]", "_", sname), "bones": [names_src[b] for b in bones],
                    "bone_data": bd, "pts": pts, "w": w, "slots": np.array([list(k) for k in skin.indices]),
                    "edges": edges[keep], "l0": l0[keep], "heavy": np.zeros(len(pts), dtype=int)})
    return out


def native_vs_staged(native: Sequence[dict], src_frames, names_src, parents_src, staged: Sequence[dict], rb, names,
                     parents) -> dict:
    """Worst edge ratio per frame of Fallout 4's own skinning on the source poses against the staged mesh on the
    clip read back through the DLL (shapes matched by name)."""
    by = {s["name"]: s for s in staged}
    nat = ra2.worst_per_frame(native, parents_src, names_src, src_frames)
    stg = ra2.worst_per_frame([by[s["name"]] for s in native], parents, names, rb)
    return {"worst": round(max(nat), 4), "frame": nat.index(max(nat)), "staged_worst": round(max(stg), 4),
            "max_abs_diff": round(max(abs(a - b) for a, b in zip(nat, stg)), 4),
            "max_rel_diff": round(max(abs(a - b) / a for a, b in zip(nat, stg)), 5)}


def resample_root(samples: Sequence[Sequence[float]], n: int, unit: float = UNIT) -> List[tuple]:
    """Root motion (x, y, z m, yaw rad) per frame from hkaDefaultAnimatedReferenceFrame samples spread evenly over
    the clip (the deathclaw stores 2: start and end), linearly interpolated."""
    if len(samples) < 2 or n < 1:
        raise Ra5Error("root motion needs at least two samples and one frame")
    out = []
    for f in range(n):
        x = f * (len(samples) - 1) / max(1, n - 1)
        i = min(int(math.floor(x)), len(samples) - 2)
        u = x - i
        a, b = samples[i], samples[i + 1]
        v = [a[k] + (b[k] - a[k]) * u for k in range(4)]
        out.append((v[0] * unit, v[1] * unit, v[2] * unit, v[3]))
    return out


def resampled_root(hkx: bytes, n: int) -> Optional[List[tuple]]:
    """The clip's root motion resampled to n frames when its reference frame holds a different number of samples
    (None when it has none or exactly n)."""
    from fo4sf import hkanim
    from fo4sf.hkpackfile import Packfile
    p = Packfile(hkx)
    rfs = [hkanim.read_reference_frame(p, o) for o, c in p.objects() if c == "hkaDefaultAnimatedReferenceFrame"]
    if not rfs or len(rfs[0].samples) == n or len(rfs[0].samples) < 2:
        return None
    return resample_root(rfs[0].samples, n)


def _is_additive(hkx: bytes) -> bool:
    """hkaAnimationBinding blend hint ADDITIVE (2), read without decoding the clip (hkanim.read_binding's offset)."""
    from fo4sf import hkanim
    from fo4sf.hkpackfile import Packfile
    p = Packfile(hkx)
    return any(hkanim.read_binding(p, o).blend_hint == 2 for o, c in p.objects() if c == "hkaAnimationBinding")


def _fo4_clip_names(S: Sources, spec: cr.CreatureSpec) -> set:
    out = set()
    for f in spec.clip_folders:
        pre = f"meshes\\actors\\{f.lower()}\\"
        out |= {n.replace("/", "\\").lower()[len(pre):] for n in S.fo4_anim.names
                if n.replace("/", "\\").lower().startswith(pre) and n.lower().endswith(".hkx")}
    return out


def _empty_folders(template: esm.Record, paths: cr.CreaturePaths, written) -> List[str]:
    """Our rewritten folders (lower case) that hold none of our clips."""
    old = cr.race_clip_folder(template)
    have = {w.folder.lower() for w in written}
    return sorted({cr.rewrite_folder(esm.zstring(d), old, paths.clips).lower() for s, d in template.subs
                   if s == b"SAPT"} - have)


# =============================================================================================== batch files
def build_bats(keys: Sequence[str], slot: Optional[int] = None) -> Dict[str, str]:
    pre = "XX" if slot is None else f"{slot & 0xFF:02X}"
    out = {}
    for k in keys:
        spec = cr.CREATURES[k]
        out[spec.bat] = (f"; RA5 creature probe: {spec.name} on its own Fallout 4 rig, clips and mesh\n"
                         f"; spawns beside the player; Very Aggressive + Foolhardy: attacks on sight; killable\n"
                         f"player.placeatme {pre}{form_ids(k)['NPC_']:06X} 1\n")
    ra2.validate_bats(out)
    return out


# =============================================================================================== build
def build(out: Path = OUT, creatures: Sequence[str] = ORDER, starfield_dir: Path = STARFIELD_DIR,
          fo4_data: Path = FO4_DATA, dll: Optional[str] = None, texconv: Optional[Path] = TEXCONV,
          materials: bool = True) -> dict:
    out = check_out_dir(out)
    unknown = [c for c in creatures if c not in cr.CREATURES]
    if unknown:
        raise Ra5Error(f"unknown creatures {unknown}; known: {sorted(cr.CREATURES)}")
    creatures = [c for c in ORDER if c in creatures]
    for sub in ("Data", "work", "bat"):
        if (out / sub).exists():
            shutil.rmtree(out / sub)
    for f in (PLUGIN, MAIN_BA2, "report.json", "manifest.json"):
        (out / f).unlink(missing_ok=True)
    data, work = out / "Data", out / "work"
    data.mkdir(parents=True)
    work.mkdir(parents=True)
    ra2.check_free_space_gb(out, 60.0)
    S = Sources(starfield_dir, fo4_data, work)
    cal = aa.Calumi(dll)
    conv = None
    report: dict = {"probe": PROBE, "conventions": {
        "units": "FO4 units x 1/70 = metres", "axes": "both games Z up, +Y forward, +X right: no axis change",
        "fps": FPS, "root_motion": "hkaDefaultAnimatedReferenceFrame samples -> Root track + .af header",
        "rig_keys": RIG_KEYS, "precision": "default",
        "rig_rules": "COM inserted when missing; bones with translation keys rebased to an identity rest; DirectAt on "
                     "COM; letters / digits / '_' names (scripts/actors/convert_creature.py)"},
        "creatures": {}, "not_built": {}}
    if materials:
        cres = starfield_dir / "Tools" / "ContentResources.zip"
        if texconv and Path(texconv).is_file() and cres.is_file():
            from fo4sf import pipeline
            conv = pipeline.Converter(pipeline.Fo4Archives(str(fo4_data)), str(data), str(texconv), str(cres),
                                      prefix=MATERIAL_PREFIX)
            report["materials"] = {"how": "pipeline.Converter._shape_material (the converter Codsworth's look came from)",
                                   "texconv": str(texconv), "prefix": MATERIAL_PREFIX}
        else:
            report["materials"] = {"how": "stand-in", "why": "texconv or ContentResources.zip missing"}
    else:
        report["materials"] = {"how": "stand-in", "why": "--no-materials"}
    records, built = [], []
    for key in creatures:
        try:
            res = build_creature(cr.CREATURES[key], S, cal, data, work, conv)
        except (Ra5Error, cr.CreatureError, ra2.Ra2Error, ValueError, KeyError) as e:
            report["not_built"][key] = f"{type(e).__name__}: {e}"
            if key == "radroach":
                raise
            continue
        records += res["records"]
        report["creatures"][key] = res["report"]
        built.append(key)
    (out / PLUGIN).write_bytes(ra2.plugin_bytes(records, ["Starfield.esm"], S.group_order,
                                                description="RA5 creature probe (Fallout 4 creatures, own rigs)"))
    report["plugin"] = {"file": PLUGIN, "records": {f"{r.formid:08X}": f"{r.sig.decode()} {r.edid}" for r in records}}
    loose = sorted(p for p in data.rglob("*") if p.is_file())
    report["ba2"] = ra2.pack_gnrl_ba2_v2([(str(p.relative_to(data)).replace("/", "\\"), p.read_bytes()) for p in loose],
                                         out / MAIN_BA2, starfield_dir)
    bat_dir = out / "bat"
    bat_dir.mkdir(exist_ok=True)
    for f, text in build_bats(built).items():
        (bat_dir / f).write_text(text, encoding="utf-8")
    manifest = {"probe": PROBE, "plugin": PLUGIN, "ba2": MAIN_BA2, "creatures": built,
                "form_ids_local": {edids(cr.CREATURES[k])[g]: f"{v:06X}" for k in built for g, v in form_ids(k).items()},
                "files": {}, "data_files": {}}
    for p in [out / PLUGIN, out / MAIN_BA2] + sorted(bat_dir.glob("*.txt")):
        manifest["files"][str(p.relative_to(out)).replace("/", "\\")] = {"sha256": ra2.sha256_file(p),
                                                                          "size_bytes": p.stat().st_size}
    for p in loose:
        manifest["data_files"][str(p.relative_to(data)).replace("/", "\\")] = {"sha256": ra2.sha256_file(p),
                                                                                "size_bytes": p.stat().st_size}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    report["verify"] = verify(out, dll=dll)
    report["sizes_bytes"] = {"data": sum(p.stat().st_size for p in loose), "ba2": (out / MAIN_BA2).stat().st_size}
    (out / "report.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    return report


# =============================================================================================== verify
def _plugin_records(path: Path) -> Dict[int, esm.Record]:
    recs = {}
    with esm.Plugin(str(path)) as p:
        if p.masters != ["Starfield.esm"]:
            raise Ra5Error(f"masters {p.masters}")
        for g, spans in p.groups.items():
            for start, end in spans:
                for item in p.walk(start, end):
                    if item[0] == "REC":
                        r = p.record_at(item[1])
                        recs[r.formid] = r
    return recs


def verify(stage: Path = OUT, dll: Optional[str] = None) -> dict:
    """Read-only: SHA-256 of every staged file; every loose Data file byte-equal inside the BA2 (entry hashes too);
    the plugin's masters, records and references; every record path present in the archive; batch rule; safe bone
    names; rig keys; every clip readable through the DLL with the rig's bone count."""
    stage = Path(stage)
    man = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
    for rel, meta in man["files"].items():
        p = stage / rel
        if not p.is_file() or ra2.sha256_file(p) != meta["sha256"]:
            raise Ra5Error(f"staged file missing or changed: {rel}")
    entries = ra2.verify_ba2_entry_hashes(stage / MAIN_BA2)
    arc = Ba2(str(stage / MAIN_BA2))
    for rel, meta in man["data_files"].items():
        if hashlib.sha256(arc.read(rel)).hexdigest() != meta["sha256"]:
            raise Ra5Error(f"{MAIN_BA2}: {rel} differs from the staged loose file")
    if len(arc.entries) != len(man["data_files"]):
        raise Ra5Error(f"{MAIN_BA2}: {len(arc.entries)} entries for {len(man['data_files'])} data files")
    recs = _plugin_records(stage / PLUGIN)
    want = {(1 << 24) | v: edids(cr.CREATURES[k])[g] for k in man["creatures"] for g, v in form_ids(k).items()}
    got = {fid: r.edid for fid, r in recs.items()}
    if got != want:
        raise Ra5Error(f"plugin records {got} != {want}")
    refs = {}
    for fid, r in recs.items():
        for s in (b"RNAM", b"WNAM", b"GNAM", b"MODL"):
            for d in r.all(s):
                if len(d) == 4:
                    v, = struct.unpack("<I", d)
                    if v >> 24 == 1 and v not in recs:
                        raise Ra5Error(f"{r.edid} {s.decode()} -> {v:08X}, not in the plugin")
                    refs.setdefault(r.edid, {})[s.decode()] = f"{v:08X}"
    safe = re.compile(r"^[A-Za-z0-9_]+$")
    names_low = {n.lower().replace("/", "\\") for n in arc.names}
    per = {}
    cal = aa.Calumi(dll) if aa.find_dll(dll) else None
    for k in man["creatures"]:
        spec, fid = cr.CREATURES[k], form_ids(k)
        paths = cr.CreaturePaths(spec.name)
        race, bptd, arma = (recs[(1 << 24) | fid[g]] for g in ("RACE", "BPTD", "ARMA"))
        missing = []
        for s in (b"ANAM", b"NAM5"):
            rel = "meshes\\" + esm.zstring(race.get(s)).lower()
            if rel not in names_low:
                missing.append(f"RACE {s.decode()} {rel}")
        rel = "meshes\\" + esm.zstring(arma.get(b"MOD2")).lower()
        if rel not in names_low:
            missing.append(f"ARMA MOD2 {rel}")
        dn = "meshes\\" + esm.zstring(race.get(b"DNAM")).lower() + "\\"
        if not any(n.startswith(dn) for n in names_low):
            missing.append(f"RACE DNAM {dn}")
        if missing:
            raise Ra5Error(f"{spec.name}: record paths with nothing in the archive: {missing}")
        rig = stage / "Data" / "Meshes" / Path(*paths.skeleton_rig.split("\\"))
        info = {"clips": 0}
        rig_names = None
        if cal is not None:
            rb = cal.read_rig(str(rig))["bones"]
            rig_names = [b["name"] for b in rb]
            keys = {b["name"]: b["key"] for b in rb if b["key"] is not None}
            if keys != RIG_KEYS:
                raise Ra5Error(f"{spec.name}: rig keys {keys}")
            for af in sorted((stage / "Data" / "Meshes" / Path(*paths.clips.split("\\"))).glob("*.af")):
                h = aa.read_af_header(af.read_bytes())
                rc = cal.read_clip(str(rig), str(af))
                if h["bones"] != len(rb) or h["kind"] != aa.AF_KIND_FULL or rc["frame_count"] != h["frames"]:
                    raise Ra5Error(f"{spec.name} {af.name}: header {h}, read back {rc['frame_count']} frames")
                side = af.with_suffix(".afx").read_bytes()
                ra2.afx_elements(side)
                if aa.parse_afx(side)["filename"].lower() != af.name.lower():
                    raise Ra5Error(f"{af.name}: its .afx names another file")
                info["clips"] += 1
            info["rig_bones"] = len(rb)
        bad = [b for b in cr.bptd_bones(bptd) + cr.race_bone_names(race)
               if not safe.match(b) or (rig_names is not None and b not in rig_names)]
        from fo4sf import fo4skin, nif as nifmod
        for p in (paths.mesh, paths.skeleton_nif, paths.skeleton_ref):
            n = nifmod.parse((stage / "Data" / "Meshes" / Path(*p.split("\\"))).read_bytes())
            bad += [f"{p} {fo4skin._block_name(n, i).decode('latin-1')}" for i in range(len(n.blocks))
                    if n.type_of(i) == "NiNode" and not safe.match(fo4skin._block_name(n, i).decode("latin-1"))]
        if rig_names is not None:
            bad += [f"rig {b}" for b in rig_names if not safe.match(b)]
        if bad:
            raise Ra5Error(f"{spec.name}: unsafe or unknown bone names {bad[:10]}")
        per[k] = info
    bats = {p.name: p.read_text(encoding="utf-8") for p in sorted((stage / "bat").glob("*.txt"))}
    p3 = ra2.validate_bats(bats)
    if sorted(bats) != sorted(build_bats(man["creatures"])):
        raise Ra5Error(f"batch files {sorted(bats)}")
    return {"staged_files": len(man["files"]), "ba2_entries": entries, "data_files_in_ba2": len(man["data_files"]),
            "records": {f"{k:08X}": v for k, v in sorted(got.items())}, "references": refs, "creatures": per,
            "bats": p3}


def deformation_check(stage: Path = OUT, dll: Optional[str] = None) -> dict:
    """Edge stretch of every staged creature's mesh on every clip and frame read back through the DLL."""
    stage = Path(stage)
    man = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
    cal = aa.Calumi(dll)
    data = stage / "Data"
    out = {}
    for k in man["creatures"]:
        paths = cr.CreaturePaths(cr.CREATURES[k].name)
        rig = data / "Meshes" / Path(*paths.skeleton_rig.split("\\"))
        shapes = ra2.load_skinned_shapes(data, paths.data_rel(paths.mesh))
        rr = cal.read_rig(str(rig))["bones"]
        nm, par = [b["name"] for b in rr], [b["parent"] for b in rr]
        clips = {}
        for af in sorted((data / "Meshes" / Path(*paths.clips.split("\\"))).glob("*.af")):
            _rc, rb = ra2.readback_local(cal, rig, af)
            clips[af.stem] = ra2.edge_stretch(shapes, par, nm, rb)
        s = ra2.summarize_stretch(clips, shapes)
        s.pop("per_clip_shape", None)
        out[k] = s
    return out


# =============================================================================================== install / uninstall
def install(stage: Path, starfield_dir: Path, plugins_txt: Optional[Path] = None,
            min_free_gb: float = ra2.DEFAULT_MIN_FREE_GB, check_running=True) -> dict:
    """Copy the plugin and its BA2 into Data, append *FO4SF_RA5Creatures.esm to Plugins.txt (original kept in
    <stage>\\backup_pre_ra5), write the batch files stamped with the real load-order slot into the game folder and a
    receipt. Refuses to overwrite anything (stage_ra2_handy.install's rules)."""
    if check_running:
        ra2.check_starfield_not_running()
    man = json.loads((Path(stage) / "manifest.json").read_text(encoding="utf-8"))
    verify(stage)
    ra2.check_free_space_gb(starfield_dir, min_free_gb)
    data = starfield_dir / "Data"
    if not data.is_dir():
        raise Ra5Error(f"no Data folder in {starfield_dir}")
    receipt_path = data / RECEIPT
    if receipt_path.exists():
        raise Ra5Error(f"already installed ({receipt_path}); uninstall first")
    ptxt = plugins_txt or ra2._default_plugins_txt()
    orig = ptxt.read_bytes() if ptxt.is_file() else None
    lines = orig.decode("utf-8-sig").splitlines() if orig is not None else []
    backup = Path(stage) / BACKUP
    if backup.exists() and any(backup.iterdir()):
        raise Ra5Error(f"non-empty backup folder {backup}; inspect or uninstall first")
    backup.mkdir(parents=True, exist_ok=True)
    if orig is not None:
        (backup / "Plugins.txt").write_bytes(orig)
    added, bats = [], []
    try:
        for name in (PLUGIN, MAIN_BA2):
            dst = data / name
            if dst.exists():
                raise Ra5Error(f"refusing to overwrite {dst}")
            shutil.copy2(Path(stage) / name, dst)
            added.append({"name": name, "sha256": ra2.sha256_file(dst)})
        low = {ln.strip().lstrip("*").casefold() for ln in lines if ln.strip()}
        appended = [] if PLUGIN.casefold() in low else [f"*{PLUGIN}"]
        new_lines = lines + appended
        slot = ra2.full_master_slot(data, new_lines, target=PLUGIN)
        for f, text in build_bats(man["creatures"], slot).items():
            dst = starfield_dir / f
            if dst.exists():
                raise Ra5Error(f"refusing to overwrite {dst}")
            dst.write_text(text, encoding="utf-8")
            bats.append({"name": f, "sha256": ra2.sha256_file(dst)})
        ptxt.parent.mkdir(parents=True, exist_ok=True)
        ptxt.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        receipt = {"probe": PROBE, "stage_dir": str(stage), "backup_dir": str(backup), "plugins_txt": str(ptxt),
                   "plugins_txt_had_file": orig is not None, "plugins_txt_sha256_after": ra2.sha256_file(ptxt),
                   "appended_plugins_lines": appended, "slot_hex": f"{slot:02X}",
                   "form_ids": {edids(cr.CREATURES[k])[g]: f"{slot:02X}{v:06X}" for k in man["creatures"]
                                for g, v in form_ids(k).items()},
                   "added_data_files": added, "added_root_bats": bats}
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        return receipt
    except Exception:
        for b in bats:
            (starfield_dir / b["name"]).unlink(missing_ok=True)
        for a in added:
            (data / a["name"]).unlink(missing_ok=True)
        if orig is not None:
            ptxt.write_bytes(orig)
        shutil.rmtree(backup, ignore_errors=True)
        raise


def uninstall(starfield_dir: Path, plugins_txt: Optional[Path] = None, check_running=True) -> dict:
    """Remove what install added (each file only if unchanged) and restore Plugins.txt byte for byte when nobody
    changed it since; otherwise drop only the appended line (stage_ra2_handy.uninstall's rules)."""
    if check_running:
        ra2.check_starfield_not_running()
    data = starfield_dir / "Data"
    receipt_path = data / RECEIPT
    if not receipt_path.is_file():
        raise Ra5Error(f"not installed ({receipt_path} missing)")
    rc = json.loads(receipt_path.read_text(encoding="utf-8"))
    for group, root in (("added_root_bats", starfield_dir), ("added_data_files", data)):
        for b in rc[group]:
            p = root / b["name"]
            if p.is_file():
                if ra2.sha256_file(p) != b["sha256"]:
                    raise Ra5Error(f"refusing to delete changed {p}")
                p.unlink()
    ptxt = plugins_txt or Path(rc["plugins_txt"])
    backup = Path(rc["backup_dir"])
    how = "unchanged"
    if ptxt.is_file() and ra2.sha256_file(ptxt) == rc["plugins_txt_sha256_after"]:
        if rc["plugins_txt_had_file"]:
            ptxt.write_bytes((backup / "Plugins.txt").read_bytes())
            how = "restored byte for byte"
        else:
            ptxt.unlink()
            how = "removed (there was none before)"
    elif ptxt.is_file() and rc["appended_plugins_lines"]:
        drop = {ln.casefold() for ln in rc["appended_plugins_lines"]}
        kept = [ln for ln in ptxt.read_text(encoding="utf-8-sig").splitlines() if ln.strip().casefold() not in drop]
        ptxt.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
        how = "changed since install: only the appended line was removed"
    (backup / "Plugins.txt").unlink(missing_ok=True)
    if backup.is_dir() and not any(backup.iterdir()):
        backup.rmdir()
    receipt_path.unlink()
    return {"uninstalled": PROBE, "plugins_txt": how}


def status(starfield_dir: Path) -> dict:
    p = starfield_dir / "Data" / RECEIPT
    return {"installed": p.is_file(), "receipt": json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None}


# =============================================================================================== command line
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", type=Path, default=OUT)
    b.add_argument("--creatures", default=",".join(ORDER))
    b.add_argument("--starfield", type=Path, default=STARFIELD_DIR)
    b.add_argument("--fo4-data", type=Path, default=FO4_DATA)
    b.add_argument("--dll", default=None)
    b.add_argument("--texconv", type=Path, default=TEXCONV)
    b.add_argument("--no-materials", action="store_true", help="vanilla stand-in material instead of the converted look")
    v = sub.add_parser("verify")
    v.add_argument("--stage-dir", type=Path, default=OUT)
    d = sub.add_parser("deform")
    d.add_argument("--stage-dir", type=Path, default=OUT)
    i = sub.add_parser("install")
    i.add_argument("--stage-dir", type=Path, default=OUT)
    i.add_argument("--starfield", type=Path, required=True)
    i.add_argument("--plugins-txt", type=Path, default=None)
    i.add_argument("--min-free-gb", type=float, default=ra2.DEFAULT_MIN_FREE_GB)
    u = sub.add_parser("uninstall")
    u.add_argument("--starfield", type=Path, required=True)
    u.add_argument("--plugins-txt", type=Path, default=None)
    s = sub.add_parser("status")
    s.add_argument("--starfield", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "build":
        rep = build(a.out, [c.strip() for c in a.creatures.split(",") if c.strip()], a.starfield, a.fo4_data, a.dll,
                    a.texconv, materials=not a.no_materials)
        print(json.dumps({"out": str(a.out), "built": sorted(rep["creatures"]), "not_built": rep["not_built"],
                          "ba2": rep["ba2"], "plugin": rep["plugin"]["records"],
                          "summary": {k: {"clips": v["clip_summary"]["written"],
                                          "worst_vs_fo4_decoded": v["clip_summary"]["worst_vs_fo4_decoded"],
                                          "deformation_worst": v["deformation"]["worst"].get("ratio"),
                                          "over_limit": v["deformation"]["over_limit"]}
                                      for k, v in rep["creatures"].items()}}, indent=1, default=str))
    elif a.cmd == "verify":
        print(json.dumps(verify(a.stage_dir), indent=1))
    elif a.cmd == "deform":
        rep = deformation_check(a.stage_dir)
        print(json.dumps({k: {x: v[x] for x in ("worst", "over_limit", "rigid_edges_worst_dev")} for k, v in rep.items()},
                         indent=1, default=str))
    elif a.cmd == "install":
        print(json.dumps(install(a.stage_dir, a.starfield, a.plugins_txt, a.min_free_gb), indent=1))
    elif a.cmd == "uninstall":
        print(json.dumps(uninstall(a.starfield, a.plugins_txt), indent=1))
    else:
        print(json.dumps(status(a.starfield), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
