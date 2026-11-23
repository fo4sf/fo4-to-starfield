"""Convert a Fallout 4 creature (skeleton.hkx + its skinned mesh) onto its OWN skeleton in Starfield form: the generic
version of convert_handy.convert_parts (Mr. Handy), used by scripts/probes/stage_ra5_creatures.py.

    python scripts/actors/convert_creature.py radroach [--out D:\\FO4SF-Owner-Tests\\robot-anim\\RA5\\work\\mesh-radroach]

Rig rules (as the Handy rig that ran in game, docs/actors/robot-animation.md section 7, plus what creatures need):
  * the Fallout 4 skeleton.hkx reference pose is the bind; Root is held at the identity (root motion is its track);
  * a COM bone (Starfield rig map key 9; vanilla actor meshes hang every bone below COM_Twin, a stand-in for COM) is
    inserted under Root at the rest position of Root's body child, identity rotation, when the skeleton has none
    (radroach, bloatfly, mole rat); every former child of Root hangs under it with the same world pose;
  * bones whose clips move them (translation keys) get an identity rest rotation (actor_skin rest-rotation rebase;
    world positions unchanged), so no translation key depends on the unverified engine rule for a turned bone;
  * DirectAt (map key 137) is added on COM, identity, as on the Mini Bot;
  * names: a creature prefix is stripped (Dogmeat_Root -> Root), the root is 'Root', COM is 'COM', other characters
    than letters, digits and '_' become '_' (actor_skin.starfield_bone_names).
Mesh rules: every lit, skinned shape of the creature NIF except the dismemberment caps is posed on the bind with its
own Fallout 4 weights (convert_handy.pose_part: up to 4 per vertex) and written as one BSGeometry per shape with its
own material (scripts/probes stage passes the converted .mat; a vanilla stand-in otherwise).
"""
import argparse
import json
import math
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(HERE, "..", "..", "src"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from fo4sf import actor_skin, convert_static, fo4skin, nif as nifmod  # noqa: E402
import convert_handy  # noqa: E402

UNIT = convert_static.UNIT_SCALE
IDENT = actor_skin.IDENT_R
DIRECT_AT = ("DirectAt", "COM", ((0.0, 0.0, 0.0), IDENT, 1.0))
TRANSLATION_KEY_M = 1e-4          # a bone whose clip translation leaves its bind by more than this is rebased
MESH_EXCLUDE = ("DirectAt",)


# ---- skeleton --------------------------------------------------------------------------------------------------------
def rig_name_map(names: Sequence[str], parents: Sequence[int], strip_prefix: str = "") -> Dict[str, str]:
    """{Fallout 4 name: rig name}: prefix stripped, the root bone 'Root', a bone named COM (any case) 'COM', then
    actor_skin.starfield_bone_names (letters, digits, '_'; collisions raise)."""
    pre = {}
    for i, n in enumerate(names):
        m = n[len(strip_prefix):] if strip_prefix and n.startswith(strip_prefix) else n
        if parents[i] < 0:
            m = "Root"
        elif m.lower() == "com":
            m = "COM"
        pre[n] = m
    safe = actor_skin.starfield_bone_names(list(pre.values()))
    return {n: safe[m] for n, m in pre.items()}


def force_root_identity(skel: actor_skin.Skeleton) -> Tuple[actor_skin.Skeleton, float]:
    """The skeleton with its root bone's local bind set to the identity, and how far (units) the root stood off it."""
    roots = [i for i, p in enumerate(skel.parents) if p < 0]
    if roots != [0]:
        raise ValueError(f"skeleton has roots {roots}; one root at index 0 is required")
    t, r, s = skel.local[0]
    off = max(math.dist(t, (0, 0, 0)), max(abs(a - b) for a, b in zip(r, IDENT)))
    local = list(skel.local)
    local[0] = ((0.0, 0.0, 0.0), IDENT, 1.0)
    return actor_skin.Skeleton(list(skel.names), list(skel.parents), local, list(skel.lock_translation), skel.name), off


@dataclass
class ComInsert:
    """How insert_com changed the bone list: new index of every old bone, COM's index and its local bind (t, R)."""
    new_index: List[int]
    com: int
    com_local: tuple
    reparented: List[int] = field(default_factory=list)     # old indices whose parent became COM


def insert_com(skel: actor_skin.Skeleton, name: str = "COM",
               strip_prefix: str = "") -> Tuple[actor_skin.Skeleton, Optional[ComInsert]]:
    """(skeleton, ComInsert or None). With no bone called `name` (any case, after strip_prefix: Dogmeat_COM counts):
    a new bone at index 1 under the root, at the rest position of the root's child with the most descendants,
    identity rotation; every former child of the root hangs under it, its local bind turned into COM's frame (world
    pose unchanged)."""
    def bare(n):
        return n[len(strip_prefix):] if strip_prefix and n.startswith(strip_prefix) else n
    if any(bare(n).lower() == name.lower() for n in skel.names):
        return skel, None
    kids = skel.children(0)
    if not kids:
        raise ValueError("the root has no child to stand COM on")
    body = max(kids, key=lambda k: (len(skel.descendants(k)), -k))
    t_root, r_root, _ = skel.local[0]
    w_body = skel.world()[body][0]
    w_root = skel.world()[0]
    rel = actor_skin._mat_vec(actor_skin._mat_t(w_root[1]), tuple(a - b for a, b in zip(w_body, w_root[0])))
    com_local = (rel, IDENT, 1.0)
    new_index = [0] + [i + 1 for i in range(1, len(skel.names))]
    names = [skel.names[0], name] + list(skel.names[1:])
    parents = [-1, 0]
    local = [skel.local[0], com_local]
    for i in range(1, len(skel.names)):
        p = skel.parents[i]
        if p == 0:
            t, r, s = skel.local[i]
            parents.append(1)
            local.append((tuple(a - b for a, b in zip(t, rel)), r, s))
        else:
            parents.append(new_index[p])
            local.append(skel.local[i])
    locks = list(skel.lock_translation)
    locks = (locks[:1] + [False] + locks[1:]) if locks else []
    out = actor_skin.Skeleton(names, parents, local, locks, skel.name)
    return out, ComInsert(new_index, 1, (rel, IDENT), [i for i in range(1, len(skel.names)) if skel.parents[i] == 0])


def insert_com_frames(frames, ins: Optional[ComInsert], quat=True):
    """Source poses [[(t, q)] per bone] -> poses on the skeleton insert_com built (COM held at its bind; the
    reparented bones' local poses moved into COM's frame). quat: rotations are quaternions (x, y, z, w)."""
    if ins is None:
        return [list(fr) for fr in frames]
    rel = ins.com_local[0]
    com = (tuple(rel), (0.0, 0.0, 0.0, 1.0) if quat else IDENT)
    rep = set(ins.reparented)
    out = []
    for fr in frames:
        row = [fr[0], com]
        for i in range(1, len(fr)):
            t, q = fr[i]
            row.append((tuple(a - b for a, b in zip(t, rel)), q) if i in rep else (t, q))
        out.append(row)
    return out


@dataclass
class CreatureRig:
    """The finished rig: skeleton in metres with final names (actor_skin.Skeleton), the source skeleton (hkx names,
    metres, root at identity), the COM insert, the rebase corrections (per bone of the skeleton after insert_com,
    row-major 3x3), {hkx name: final name}, and the report."""
    skel: actor_skin.Skeleton
    source: actor_skin.Skeleton
    com: Optional[ComInsert]
    corrections: List[tuple]
    names: Dict[str, str]
    report: dict


def build_rig(skel_fo4: actor_skin.Skeleton, rebase: Sequence[str] = (), strip_prefix: str = "",
              unit: float = UNIT, extra_bones=(DIRECT_AT,)) -> CreatureRig:
    """skeleton.hkx (FO4 units) -> the rig: root at identity, metres, COM inserted when missing, `rebase` bones (hkx
    names, or 'COM') given an identity rest rotation, extra bones appended (parent by final-or-hkx name), renamed."""
    src, root_off = force_root_identity(skel_fo4.scaled(unit))
    s1, ins = insert_com(src, strip_prefix=strip_prefix)
    corr = actor_skin.rest_rotation_corrections(s1, rebase)
    s2 = actor_skin.rebase_skeleton(s1, corr)
    names = rig_name_map(s1.names, s1.parents, strip_prefix)
    s3 = actor_skin.rename_skeleton(s2, names)
    for name, parent, local in extra_bones:
        s3 = actor_skin.add_bone(s3, name, names.get(parent, parent), local)
    rep = {"bones_fo4": len(skel_fo4.names), "bones_rig": len(s3.names), "com_inserted": ins is not None,
           "com_under": names[s1.names[s1.parents[ins.com]]] if ins else None,
           "com_rest_position_m": [round(c, 6) for c in s3.world()[s3.index("COM")][0]],
           "reparented_under_com": [names[s1.names[ins.new_index[i]]] for i in ins.reparented] if ins else [],
           "root_bind_offset_removed": round(root_off, 6), "rebased": list(rebase),
           "rest_rotation_deg_before": {n: round(actor_skin.rotation_angle_deg(s1.local[s1.index(n)][1], IDENT), 4)
                                        for n in rebase},
           "rest_rotation_deg_after": {n: round(actor_skin.rotation_angle_deg(s3.local[s3.index(names[n])][1], IDENT), 6)
                                       for n in rebase},
           "renamed": {a: b for a, b in names.items() if a != b}, "extra_bones": [e[0] for e in extra_bones],
           "names_safe": all(actor_skin.SAFE_BONE_NAME.match(n) for n in s3.names)}
    return CreatureRig(s3, src, ins, corr, names, rep)


def bones_to_rebase(source_names: Sequence[str], frames_by_clip: Dict[str, list], bind: Sequence[tuple],
                    ins: Optional[ComInsert], tol: float = TRANSLATION_KEY_M) -> List[str]:
    """hkx names (plus 'COM' when inserted) of the bones whose translation leaves its bind in any frame of any clip
    (source poses, metres). The root is never rebased (its bind is the identity)."""
    moved = set()
    for frames in frames_by_clip.values():
        for fr in frames:
            for i in range(1, len(fr)):
                if i not in moved and math.dist(fr[i][0], bind[i][0]) > tol:
                    moved.add(i)
    names = [source_names[i] for i in sorted(moved)]
    return (["COM"] if ins is not None else []) + names


# ---- mesh ------------------------------------------------------------------------------------------------------------
def texture_paths(n, shape) -> List[str]:
    """The BSShaderTextureSet paths of a Fallout 4 shape's lighting shader (empty when it has none)."""
    if shape.shader_ref < 0 or n.type_of(shape.shader_ref) != "BSLightingShaderProperty":
        return []
    import struct
    blk = n.blocks[shape.shader_ref]
    for o in range(0, min(len(blk), 256) - 3, 4):
        v, = struct.unpack_from("<i", blk, o)
        if 0 <= v < len(n.blocks) and n.type_of(v) == "BSShaderTextureSet":
            t = n.blocks[v]
            cnt, = struct.unpack_from("<I", t, 0)
            p, out = 4, []
            for _ in range(cnt):
                ln, = struct.unpack_from("<I", t, p)
                out.append(t[p + 4:p + 4 + ln].decode("latin-1"))
                p += 4 + ln
            return out
    return []


def creature_parts(nif_bytes: bytes, rig: CreatureRig, materials: Dict[str, str], exclude: str = r"cap",
                   default_material: str = convert_static.PLACEHOLDER_MATERIAL, unit: float = UNIT):
    """(SkinParts, expected positions m, expected influences, report) of a Fallout 4 creature NIF on the rig bind.
    Every BSTriShape with a lighting shader and a skin whose name does not match `exclude` (case-insensitive) is
    posed with convert_handy.pose_part on the source skeleton's rest pose (FO4 units, root at identity) and keeps up
    to four of its own weights; materials: {shape name: .mat path} (missing -> default_material)."""
    src_fo4 = rig.source.scaled(1.0 / unit)
    world = src_fo4.world()
    low = {n.lower(): n for n in src_fo4.names}
    n = nifmod.parse(nif_bytes)
    parts, exp_pos, exp_inf, placed, skipped = [], {}, {}, [], []
    used_names = set()
    for s in nifmod.fo4_trishapes(n, placed=True):
        sname = s.name.decode("latin-1")
        kind = n.type_of(s.shader_ref) if s.shader_ref >= 0 else None
        skin = fo4skin.read_skin(n, s.block)
        why = None
        if exclude and re.search(exclude, sname, re.I):
            why = f"name matches {exclude!r} (dismemberment cap: drawn only on a severed limb)"
        elif kind != "BSLightingShaderProperty":
            why = f"shader {kind}: no Starfield material for it"
        elif skin is None:
            why = "not skinned"
        elif not (s.uvs and s.normals and s.tangents):
            why = "uvs / normals / tangents missing"
        if why:
            skipped.append({"shape": sname, "verts": len(s.positions), "why": why})
            continue
        missing = sorted({b.decode("latin-1") for b in skin.bone_names if b.decode("latin-1").lower() not in low})
        if missing:
            raise ValueError(f"{sname}: skin bones not in skeleton.hkx: {missing}")
        pos, nrm, tan, inf, spread = convert_handy.pose_part(
            n, s, skin, lambda b: world[src_fo4.index(b)], None, lambda b: low[b.lower()])
        out_name = re.sub(r"[^A-Za-z0-9_]", "_", sname)
        while out_name in used_names:
            out_name += "_"
        used_names.add(out_name)
        shape = nifmod.Fo4Shape(out_name.encode("latin-1"), (0.0, 0.0, 0.0), IDENT, 1.0, -1, -1, -1,
                                pos, list(s.uvs), nrm, tan, [], list(s.triangles), True)
        infl = [[(rig.names[b], w) for b, w in row] for row in inf]
        mat = materials.get(sname, default_material)
        parts.append(actor_skin.SkinPart(out_name, shape, infl, mat))
        exp_pos[out_name] = [tuple(c * unit for c in p) for p in pos]
        exp_inf[out_name] = infl
        placed.append({"shape": sname, "as": out_name, "verts": len(pos), "tris": len(s.triangles),
                       "bones": len({b for r in inf for b, _ in r}), "max_influences": max(len(r) for r in inf),
                       "bind_spread_fo4_units": round(spread, 6), "material": mat,
                       "textures": [t for t in texture_paths(n, s) if t][:3]})
    if not parts:
        raise ValueError("no shape left to convert")
    return parts, exp_pos, exp_inf, {"placed": placed, "skipped": skipped,
                                     "bind_spread_max_fo4_units": max(p["bind_spread_fo4_units"] for p in placed)}


def build_files(rig: CreatureRig, parts, exp_pos, exp_inf, mesh_rel: str, skeleton_rel: str, skeleton_ref_rel: str,
                root_name: bytes, sf_mesh_template: bytes, sf_skeleton_template: bytes, mesh_exclude=MESH_EXCLUDE,
                unit: float = UNIT):
    """({Data-relative path: bytes}, report): the mesh NIF and its .mesh files, skeleton.nif and skeleton_ref.nif
    (convert_handy._build_files with the creature's own paths), each verified offline."""
    skel = rig.skel
    res = actor_skin.build_actor_mesh_nif(skel, parts, unit, template_nif=sf_mesh_template, root_name=root_name,
                                          exclude=mesh_exclude)
    bound = actor_skin.bound_from_points([p for ps in exp_pos.values() for p in ps])
    rig_root = root_name + b"_mrRigRoot"
    skeleton_nif = actor_skin.build_skeleton_nif(skel, sf_skeleton_template, rig_root, bound)
    skeleton_ref = actor_skin.build_skeleton_nif(skel, sf_skeleton_template, rig_root, bound, full_tree=True)
    verify = actor_skin.verify_actor_mesh_nif(res.nif, res.meshes, skel, exp_pos, exp_inf, exclude=mesh_exclude)
    verify_skel = actor_skin.verify_skeleton_nif(skeleton_nif, skel, full_tree=False)
    verify_ref = actor_skin.verify_skeleton_nif(skeleton_ref, skel, full_tree=True)
    files = {mesh_rel: res.nif, skeleton_rel: skeleton_nif, skeleton_ref_rel: skeleton_ref}
    for (d, f), data in res.meshes.items():
        files[f"geometries/{d}/{f}.mesh"] = data
    weighted = {b for p in parts for row in p.influences for b, w in row if w > 0}
    return files, {"bones": len(skel.names), "bones_in_mesh_nif": res.report["bones_in_nif"],
                   "weighted_bones": len(weighted), "unweighted_bones": [x for x in skel.names if x not in weighted],
                   "parts": res.report["parts"], "bound": bound, "verify_mesh": verify, "verify_skeleton": verify_skel,
                   "verify_skeleton_ref": verify_ref,
                   "ok": verify["ok"] and verify_skel["ok"] and verify_ref["ok"]}


def main(argv=None) -> int:
    """Offline preview of one creature's rig and mesh (no clips, stand-in material) into --out."""
    sys.path.insert(0, os.path.join(HERE, "..", "probes"))
    from fo4sf import creature_race as cr
    from fo4sf.ba2 import Ba2
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("creature", choices=sorted(cr.CREATURES))
    ap.add_argument("--fo4-data", default=convert_handy.FO4_DATA)
    ap.add_argument("--sf-data", default=convert_handy.SF_DATA)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if os.path.abspath(a.out).lower().startswith(os.path.abspath(r"D:\SteamLibrary").lower()):
        raise SystemExit("refusing to write under the game library")
    spec = cr.CREATURES[a.creature]
    anim = Ba2(os.path.join(a.fo4_data, "Fallout4 - Animations.ba2"))
    mesh = Ba2(os.path.join(a.fo4_data, "Fallout4 - Meshes.ba2"))
    base = f"Meshes\\Actors\\{spec.fo4_folder}\\CharacterAssets\\"
    skel = actor_skin.read_hka_skeleton(anim.read(anim.find(base + "skeleton.hkx")))
    rig = build_rig(skel, strip_prefix=spec.strip_prefix)
    parts, ep, ei, prep = creature_parts(mesh.read(mesh.find("Meshes\\Actors\\" + spec.mesh)), rig, {},
                                         spec.exclude_shapes)
    sf = os.path.join(a.sf_data, "Starfield - Meshes*.ba2")
    paths = cr.CreaturePaths(spec.name)
    files, rep = build_files(rig, parts, ep, ei, paths.data_rel(paths.mesh), paths.data_rel(paths.skeleton_nif),
                             paths.data_rel(paths.skeleton_ref), spec.name.encode() + b"FO4",
                             convert_handy._read_ba2(sf, convert_handy.SF_MESH_TEMPLATE),
                             convert_handy._read_ba2(sf, convert_handy.SF_SKELETON_TEMPLATES["minibota"]))
    for rel, data in files.items():
        p = os.path.join(a.out, "Data", *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(data)
    print(json.dumps({"ok": rep["ok"], "rig": rig.report, "mesh": prep,
                      "errors": rep["verify_mesh"]["errors"]}, indent=1, default=str)[:4000])
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
