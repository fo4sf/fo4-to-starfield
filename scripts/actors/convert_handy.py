"""Convert Fallout 4 Mr. Handy (meshes\\actors\\robot\\characterassets\\mrhandy.nif) onto his OWN skeleton for Starfield.

    python scripts/actors/convert_handy.py [--fo4-data <FO4 Data>] [--sf-data <Starfield Data>]
        [--out D:\\FO4SF-Owner-Tests\\robot-anim\\C] [--skeleton-template minibota|modela]

Unlike convert_codsworth.py (one weight per vertex, welded to the Garden Mini Bot's chassis bone) this keeps up to four
of every vertex's Fallout 4 weights and binds them to a NEW skeleton built from Fallout 4's Handy skeleton.hkx
(112 bones, reference pose, FO4 units / 70 = metres). The mesh's bone names (LArm_1, MEyeArm2, ...) are renamed to the
hkx names (Arm1|2, EyeArm2|0, ...) by actor_skin.handy_mesh_bone_to_hkx; the report lists the pose evidence per bone.

Writes, under <out>\\Data (the layout the game reads):
  meshes\\fo4sf\\actors\\handy\\handy.nif                         mesh NIF: COM_Twin + 109 bone nodes + 5 skinned shapes
  meshes\\fo4sf\\actors\\handy\\characterassets\\skeleton.nif       Root, COM, AnimObjectA, CharacterController
  meshes\\fo4sf\\actors\\handy\\characterassets\\skeleton_ref.nif   every bone
  geometries\\<sha1[:20]>\\<sha1[20:40]>.mesh                      one per shape
and next to Data: convert_handy_report.json, handy_skeleton.json (bones, parents, local/world bind in metres for the
.rig builder), handy_bone_map.json (mesh bone -> hkx bone).
The bind pose is the hkx reference pose; vertices stay where Fallout 4 draws mrhandy.nif (posed on its own nodes), so
each part rotates about the hkx joint, which stands up to a few cm from mrhandy.nif's own node (see mapping_evidence).
Physics (character controller, COM body) is copied from the template race's skeleton.nif. Never touches codsworth.nif.

convert_parts() (what the RA2 stager uses since the robot-anim fix) builds the same files from the Fallout 4 robot
parts Codsworth's object template attaches (CODSWORTH_PARTS: TorsoHandy, LegsHandyThruster, the eyes, arms, hands and
armour), each with its own weights, on the finished rig: COM (and the other REBASE bones) rebased to an identity rest,
an extra DirectAt bone, every bone renamed to letters, digits and '_' (finish_skeleton). mrhandy.nif is an older rig
(its nodes stand up to 6.6 FO4 units / 7 deg off skeleton.hkx), and its arm and palm seams tore up to 25x in the death
clips; the parts bind on skeleton.hkx exactly.
"""
import argparse
import glob
import json
import math
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from fo4sf import actor_skin, ba2, convert_static, fo4skin, nif as nifmod  # noqa: E402

FO4_DATA = r"D:\SteamLibrary\steamapps\common\Fallout 4\Data"
SF_DATA = r"D:\SteamLibrary\steamapps\common\Starfield\Data"
OUT = r"D:\FO4SF-Owner-Tests\robot-anim\C"
CODSWORTH_REPORT = r"D:\Modding\staging\codsworth_plainshader\codsworth_report.json"
BONE_MAP_A = r"D:\FO4SF-Owner-Tests\robot-anim\A\handy_bone_map.json"

SRC_MESH = r"Meshes\Actors\Robot\CharacterAssets\MrHandy.nif"
SRC_SKELETON = r"Meshes\Actors\Robot\CharacterAssets\skeleton.hkx"
SF_MESH_TEMPLATE = "meshes/actors/minibota/mesh/minibota_base/minibota_mesh.nif"
SF_SKELETON_TEMPLATES = {"minibota": "meshes/actors/minibota/characterassets/skeleton.nif",
                         "modela": "meshes/actors/modela/characterassets/skeleton.nif"}

OUT_DIR = "meshes/fo4sf/actors/handy"
OUT_MESH = OUT_DIR + "/handy.nif"
OUT_SKELETON = OUT_DIR + "/characterassets/skeleton.nif"
OUT_SKELETON_REF = OUT_DIR + "/characterassets/skeleton_ref.nif"

# The materials the current Codsworth conversion uses (codsworth_report.json "materials"); read from that file when
# it exists, this copy otherwise.
HANDY_MATERIALS = {
    "Torso": "materials\\fo4port\\texsets\\actors\\handy\\handytorso_d_ac34d7ca.mat",
    "Legs": "materials\\fo4port\\texsets\\actors\\handy\\handylegs_d_08f96bcb.mat",
    "HandyShell": "materials\\fo4port\\texsets\\actors\\handy\\handyarmor_d_8e98a175.mat",
    "Arms:0": "materials\\fo4port\\texsets\\actors\\handy\\handyarms_d_4af8b96c.mat",
    "Arms:1": "materials\\fo4port\\texsets\\actors\\handy\\handyhands_d_764488d0.mat",
}


def _read_ba2(pattern: str, rel: str) -> bytes:
    for path in sorted(glob.glob(pattern)):
        a = ba2.Ba2(path)
        i = a.find(rel)
        if i is not None:
            return a.read(i)
    raise FileNotFoundError(f"{rel} not in {pattern}")


# ---- the rig the mesh, skeleton NIFs, .rig and clips share (robot-anim fix, 23 Nov 2026) -----------------------------
# REBASE: bones given an identity parent-local rest rotation (the turn folded into their children, every clip and the
# mesh bind; world positions unchanged). COM is turned -90 deg about Y in skeleton.hkx and every clip moves it (up to
# 3.25 m); Pelvis would otherwise inherit the turn; C-ModSlotB|0..2 are the only other bones with a turned rest and
# real translation keys (eye-stalk bases, up to 0.146 m between the two candidate offset rules). Afterwards no clip key
# depends on how the engine applies a translation offset to a turned bone.
REBASE = ("COM", "Pelvis", "C-ModSlotB|0", "C-ModSlotB|1", "C-ModSlotB|2")
# EXTRA_BONES: (name, parent, local transform in metres). Vanilla Mini Bot rig: DirectAt (map key 137, look-at / aim) is
# a child of C_Body at C_Body's origin with identity rotation, and C_Body sits on COM with identity rotation, so DirectAt
# stands exactly on COM, unturned. The Handy has no C_Body: DirectAt goes directly under (rebased) COM, same place.
EXTRA_BONES = (("DirectAt", "COM", ((0.0, 0.0, 0.0), actor_skin.IDENT_R, 1.0)),)
MESH_EXCLUDE = ("DirectAt",)          # vanilla minibota_mesh.nif carries no DirectAt node (skeleton_ref.nif does)


def source_skeleton(fo4_skeleton_hkx: bytes, bind_overrides: dict = None) -> actor_skin.Skeleton:
    """Fallout 4's Handy skeleton.hkx (FO4 units, hkx names) with bind_overrides applied: {bone: (tx, ty, tz)}
    parent-local translation in FO4 units replacing the reference pose."""
    skel_fo4 = actor_skin.read_hka_skeleton(fo4_skeleton_hkx)
    for bone, t in (bind_overrides or {}).items():
        i = skel_fo4.index(bone)
        _t, r, s = skel_fo4.local[i]
        skel_fo4.local[i] = (tuple(float(v) for v in t), r, s)
    return skel_fo4


def finish_skeleton(skel_fo4: actor_skin.Skeleton, unit_scale: float = convert_static.UNIT_SCALE, rebase=(),
                    extra_bones=(), rename: bool = False):
    """(skeleton in metres with final names, corrections per source bone (row-major 3x3, see
    actor_skin.rest_rotation_corrections), {hkx name: final name}). Order: rebase `rebase` bones to an identity rest,
    scale, append `extra_bones` (metres; parent named by its hkx name), then (rename=True) rename every bone to letters,
    digits and '_' (actor_skin.starfield_bone_names)."""
    corr = actor_skin.rest_rotation_corrections(skel_fo4, rebase)
    skel = actor_skin.rebase_skeleton(skel_fo4, corr).scaled(unit_scale)
    for name, parent, local in extra_bones:
        skel = actor_skin.add_bone(skel, name, parent, local)
    names = actor_skin.starfield_bone_names(skel.names) if rename else {n: n for n in skel.names}
    return actor_skin.rename_skeleton(skel, names), corr, names


def _skeleton_report(skel, skel_fo4, corr, names, rebase, extra_bones):
    turned = {n: round(actor_skin.rotation_angle_deg(skel_fo4.local[skel_fo4.index(n)][1], actor_skin.IDENT_R), 4)
              for n in rebase}
    return {"rebased_bones": list(rebase), "rest_rotation_deg_before": turned,
            "rest_rotation_deg_after": {n: round(actor_skin.rotation_angle_deg(skel.local[skel.index(names[n])][1],
                                                                               actor_skin.IDENT_R), 6) for n in rebase},
            "extra_bones": [e[0] for e in extra_bones],
            "renamed": sum(1 for a, b in names.items() if a != b), "names_safe": all(
                actor_skin.SAFE_BONE_NAME.match(n) for n in skel.names)}


def convert(fo4_mesh: bytes, fo4_skeleton_hkx: bytes, sf_mesh_template: bytes, sf_skeleton_template: bytes,
            materials: dict, unit_scale: float = convert_static.UNIT_SCALE, snap_to_skeleton: bool = False,
            bind_overrides: dict = None, rebase=(), extra_bones=(), rename: bool = False, mesh_exclude=()):
    """(files {Data-relative path: bytes}, report dict, skeleton in metres, mesh bone -> rig bone). Pure: no file access.

    snap_to_skeleton=False (default): vertices stay where Fallout 4 draws mrhandy.nif (posed on its own nodes); the
    bind pose then matches the Fallout 4 mesh, and each part turns about the hkx joint, a few cm from its own node.
    snap_to_skeleton=True: every part keeps its placement relative to its own bone (FO4 skin-to-bone) and is posed
    on the hkx reference pose instead, so joints line up with the skeleton exactly but the parts move (report:
    snap_displacement_max_m).
    bind_overrides: {bone name: (tx, ty, tz) parent-local translation in FO4 units} replacing the hkx reference pose
    before anything is built (integration, robot-anim E: every Handy clip and mrhandy.nif's own node hold Pelvis on COM,
    (0, 0, 0), where skeleton.hkx's reference pose puts it 5.81 units away; the .rig bind must equal this bind).
    rebase / extra_bones / rename / mesh_exclude: see finish_skeleton and REBASE; the defaults keep skeleton.hkx as it
    is (the mesh path robot-anim E staged). The stager uses convert_parts (Codsworth's own parts) instead."""
    skel_fo4 = source_skeleton(fo4_skeleton_hkx, bind_overrides)
    skel, corr, final_names = finish_skeleton(skel_fo4, unit_scale, rebase, extra_bones, rename)
    hk_world = skel_fo4.world()
    src_names = set(skel_fo4.names)
    src = nifmod.parse(fo4_mesh)
    shapes = nifmod.fo4_trishapes(src, placed=True)
    world = nifmod.world_transforms(src, placed=True)

    mapping, mesh_world, unmapped, skins, bone_block = {}, {}, {}, [], {}
    for raw in shapes:
        name = raw.name.decode("latin-1")
        skin = fo4skin.read_skin(src, raw.block)
        if skin is None:
            raise ValueError(f"{name}: not skinned")
        skins.append(skin)
        for blk, b in zip(skin.bones, skin.bone_names):
            bn = b.decode("latin-1")
            mapping[bn] = actor_skin.handy_mesh_bone_to_hkx(bn)
            mesh_world[bn] = world(blk)
            if mapping[bn] is None or mapping[bn] not in src_names:
                unmapped.setdefault(bn, []).append(name)
            else:
                bone_block[blk] = mapping[bn]
    if unmapped:
        raise ValueError(f"mesh bones with no skeleton partner: {unmapped}")

    def snapped(i):
        return hk_world[skel_fo4.index(bone_block[i])] if i in bone_block else world(i)

    pose_rep: dict = {}
    drawn = convert_static.pose_skinned_shapes(src, shapes, pose_rep)
    posed = convert_static.pose_skinned_shapes(src, shapes, {}, world=snapped) if snap_to_skeleton else drawn
    parts, expected_pos, expected_inf, snap_disp = [], {}, {}, {}
    for raw, skin, ps, dr in zip(shapes, skins, posed, drawn):
        name = raw.name.decode("latin-1")
        names = [b.decode("latin-1") for b in skin.bone_names]
        fin = {n: final_names[mapping[n]] for n in names}
        inf = [[(fin[names[k]], float(w)) for w, k in zip(ws, ks) if w > 0.0] or [(fin[names[ks[0]]], 1.0)]
               for ws, ks in zip(skin.weights, skin.indices)]
        parts.append(actor_skin.SkinPart(name, ps, inf, materials.get(name, convert_static.PLACEHOLDER_MATERIAL)))
        expected_pos[name] = [tuple(c * unit_scale for c in p) for p in ps.positions]
        expected_inf[name] = inf
        snap_disp[name] = round(max(math.dist(a, b) for a, b in zip(ps.positions, dr.positions)) * unit_scale, 5)

    files, built = _build_files(skel, parts, expected_pos, expected_inf, unit_scale, sf_mesh_template,
                                sf_skeleton_template, mesh_exclude)
    report = {
        "source": SRC_MESH, "skeleton_source": SRC_SKELETON, "unit_scale": unit_scale,
        "bind_overrides_fo4_units": {k: list(v) for k, v in (bind_overrides or {}).items()},
        "snap_to_skeleton": snap_to_skeleton, "snap_displacement_max_m": snap_disp,
        "skeleton": dict(built["skeleton"], **_skeleton_report(skel, skel_fo4, corr, final_names, rebase, extra_bones)),
        "mesh_bones": len(mapping),
        "mesh_bones_without_skeleton_partner": sorted(unmapped),
        "mapping": dict(sorted(mapping.items())),
        "mapping_final_names": {k: final_names[v] for k, v in sorted(mapping.items())},
        "mapping_evidence_fo4_units": actor_skin.pose_evidence(mapping, mesh_world, skel_fo4),
        "pose": pose_rep, **{k: v for k, v in built.items() if k != "skeleton"},
        "files": sorted(files),
    }
    return files, report, skel, {k: final_names[v] for k, v in mapping.items()}


def _build_files(skel, parts, expected_pos, expected_inf, unit_scale, sf_mesh_template, sf_skeleton_template,
                 mesh_exclude):
    """The mesh NIF, its .mesh files, skeleton.nif and skeleton_ref.nif for `parts` on `skel` (metres), each verified."""
    res = actor_skin.build_actor_mesh_nif(skel, parts, unit_scale, template_nif=sf_mesh_template, root_name=b"HandyFO4",
                                          exclude=mesh_exclude)
    pts = [p for ps in expected_pos.values() for p in ps]
    bound = actor_skin.bound_from_points(pts)
    skeleton_nif = actor_skin.build_skeleton_nif(skel, sf_skeleton_template, b"HandyFO4_mrRigRoot", bound)
    skeleton_ref = actor_skin.build_skeleton_nif(skel, sf_skeleton_template, b"HandyFO4_mrRigRoot", bound, full_tree=True)
    verify = actor_skin.verify_actor_mesh_nif(res.nif, res.meshes, skel, expected_pos, expected_inf, exclude=mesh_exclude)
    verify_skel = actor_skin.verify_skeleton_nif(skeleton_nif, skel, full_tree=False)
    verify_ref = actor_skin.verify_skeleton_nif(skeleton_ref, skel, full_tree=True)
    weighted = {b for p in parts for row in p.influences for b, w in row if w > 0}
    files = {OUT_MESH: res.nif, OUT_SKELETON: skeleton_nif, OUT_SKELETON_REF: skeleton_ref}
    for (d, f), data in res.meshes.items():
        files[f"geometries/{d}/{f}.mesh"] = data
    return files, {
        "skeleton": {"name": skel.name, "bones": len(skel.names), "bones_in_mesh_nif": res.report["bones_in_nif"],
                     "weighted_bones": len(weighted), "unweighted_bones": [n for n in skel.names if n not in weighted],
                     "not_in_mesh_nif": list(mesh_exclude)},
        "parts": res.report["parts"], "bound": bound,
        "verify_mesh": verify, "verify_skeleton": verify_skel, "verify_skeleton_ref": verify_ref}


# ---- Codsworth as Fallout 4 draws him: his object template's robot parts ----------------------------------------------
# Fallout4.esm NPC_ 000179FF "Codsworth" has no skin (WNAM) and no outfit: like every Fallout 4 robot his body is
# assembled from object mods. His OBTS (one template, 15 includes, no properties) attaches, with attach-point index:
#   00047E19 Bot_TorsoHandy                   actors\robot\parts\torsohandy.nif
#   00047E23 Bot_LegsHandyThruster            actors\robot\parts\legshandythruster.nif
#   00047E35 Bot_ModHandyTopArmor             Actors\Robot\Parts\ModTorsoFloatType1AR1A.nif
#   00047E29 Bot_ModTorsoHandyEye1B  x3       actors\robot\parts\ModTorsoHandyEye.nif        index 2, 0, 1
#   00047E2E Bot_ModLegsHandyThruster1AR1A    actors\robot\parts\legshandythrusterar1a.nif
#   00072B4E Bot_ModLegsHandyThruster1AR1B    actors\robot\parts\legshandythrusterar1b.nif
#   000CAC71 Bot_HandyFrontArmor              actors\robot\parts\HandyFrontArmor.nif
#   000CAC72 Bot_HandyRearArmor               actors\robot\parts\HandyRearArmor.nif
#   00157C9B Bot_MrHandy_Arm_Left_Saw         Actors\Robot\Parts\ArmsTypeA1.nif              index 2
#   001A8B1B Bot_MrHandy_Arm_Middle_Pincer    Actors\Robot\Parts\ArmsTypeA1.nif              index 0
#   002491A9 Bot_CompCodsworth_Arm_Right_Flamer Actors\Robot\Parts\ArmsTypeA1.nif            index 1
#   00047E36 Bot_ModArmsHandyAR1A    x2       Actors\Robot\Parts\ModArmsTypeA1AR1A.nif       index 0, 1
# Each arm mod forces a hand weapon (property 1, Forced Inventory) whose embedded weapon mod (WEAP NNAM) is the hand:
#   HandySawLeft 00092A61 -> Bot_SawHand 00047E30 SawHand.nif; HandyPincherMiddle 00092A60 -> Bot_PincherHand 00047E32
#   PincherHand.nif; CompCodsworthFlamethrowerRight 002491A8 -> Bot_FlameThrowerHand 00047E31 FlameThrowerHand.nif.
# The parts that repeat (eyes, arms, hands, arm armour) skin to the |0 bones; instance N uses the |N bones (the hkx has
# the three copies, |0 front, |1 right, |2 left, and mrhandy.nif's M/R/L names agree: actor_skin.HANDY_SIDE). Index N
# is read as instance |N (left saw index 2 = |2, the bot_HasHandLeft arm). Every part's skin binds on skeleton.hkx's
# reference pose up to one rigid offset per shape (W_ref(bone) * skin_to_bone spread <= 0.0001 FO4 units, 0.03 deg).
PARTS_DIR = "Meshes\\Actors\\Robot\\Parts\\"
CODSWORTH_PARTS = (
    ("TorsoHandy.nif", None), ("LegsHandyThruster.nif", None), ("ModTorsoFloatType1AR1A.nif", None),
    ("ModTorsoHandyEye.nif", 0), ("ModTorsoHandyEye.nif", 1), ("ModTorsoHandyEye.nif", 2),
    ("LegsHandyThrusterAR1A.nif", None), ("LegsHandyThrusterAR1B.nif", None),
    ("HandyFrontArmor.nif", None), ("HandyRearArmor.nif", None),
    ("ArmsTypeA1.nif", 0), ("ArmsTypeA1.nif", 1), ("ArmsTypeA1.nif", 2),
    ("ModArmsTypeA1AR1A.nif", 0), ("ModArmsTypeA1AR1A.nif", 1),
    ("PincherHand.nif", 0), ("FlameThrowerHand.nif", 1), ("SawHand.nif", 2),
)
# The parts use the same five Fallout 4 texture sets as mrhandy.nif; each becomes one shape named as in the current
# Codsworth conversion so HANDY_MATERIALS / codsworth_report.json "materials" apply unchanged.
TEXTURE_GROUPS = {"handytorso_d": "Torso", "handylegs_d": "Legs", "handyarmor_d": "HandyShell",
                  "handyarms_d": "Arms:0", "handyhands_d": "Arms:1"}


def instance_bone(name: str, instance) -> str:
    """A part bone name for attach instance N: '...|0' -> '...|N'; other names unchanged. A part placed as an instance
    must only use |0 names (raises otherwise)."""
    if instance is None:
        return name
    if not name.endswith("|0"):
        raise ValueError(f"bone {name} of an instanced part does not end in |0")
    return f"{name[:-2]}|{int(instance)}"


def _diffuse_stem(n, shape) -> str:
    """Lower-case stem of the diffuse texture of an FO4 shape's BSLightingShaderProperty ('' if none)."""
    if shape.shader_ref < 0 or n.type_of(shape.shader_ref) != "BSLightingShaderProperty":
        return ""
    blk = n.blocks[shape.shader_ref]
    for o in range(0, min(len(blk), 256) - 3, 4):
        v, = struct.unpack_from("<i", blk, o)
        if 0 <= v < len(n.blocks) and n.type_of(v) == "BSShaderTextureSet":
            t = n.blocks[v]
            if struct.unpack_from("<I", t, 0)[0] == 0:
                return ""
            ln, = struct.unpack_from("<I", t, 4)
            return os.path.splitext(os.path.basename(t[8:8 + ln].decode("latin-1").replace("\\", "/")))[0].lower()
    return ""


def _rot_of(xf):
    return xf[1]


def pose_part(n, shape, skin, bone_world, instance, lookup):
    """One FO4 part shape posed on `bone_world` (FO4 units, hkx bone name -> world transform). Returns (positions,
    normals, tangents, influences [(hkx bone, weight)], spread): every vertex at the weighted blend of
    bone_world(bone_k) * skin_to_bone_k (normalised weights); spread = largest distance between one slot's
    transform of a vertex and the blend (0 when the part binds rigidly on this pose)."""
    bones = [lookup(instance_bone(b.decode("latin-1"), instance)) for b in skin.bone_names]
    mats = [nifmod._compose(bone_world(b), sb) for b, sb in zip(bones, skin.skin_to_bone)]
    pos, inf, spread = [], [], 0.0
    heavy = []
    for p, ws, ks in zip(shape.positions, skin.weights, skin.indices):
        pairs = [(float(w), k) for w, k in zip(ws, ks) if w > 0.0] or [(1.0, ks[0])]
        tot = sum(w for w, _ in pairs)
        each = [(w, fo4skin.apply(mats[k], p)) for w, k in pairs]
        v = tuple(sum(w * q[a] for w, q in each) / tot for a in range(3))
        spread = max(spread, max(math.dist(q, v) for _, q in each))
        pos.append(v)
        inf.append([(bones[k], w / tot) for w, k in pairs])
        heavy.append(max(pairs)[1])

    def turn(vecs):
        out = []
        for d, k in zip(vecs, heavy):
            r = _rot_of(mats[k])
            x = actor_skin._mat_vec(r, d)
            ln = math.sqrt(sum(c * c for c in x)) or 1.0
            out.append(tuple(c / ln for c in x))
        return out
    return pos, turn(shape.normals) if shape.normals else [], turn(shape.tangents) if shape.tangents else [], inf, spread


def convert_parts(part_nifs: dict, fo4_skeleton_hkx: bytes, sf_mesh_template: bytes, sf_skeleton_template: bytes,
                  materials: dict, placements=CODSWORTH_PARTS, unit_scale: float = convert_static.UNIT_SCALE,
                  bind_overrides: dict = None, rebase=REBASE, extra_bones=EXTRA_BONES, rename: bool = True,
                  mesh_exclude=MESH_EXCLUDE):
    """Codsworth's own Fallout 4 robot parts (CODSWORTH_PARTS; part_nifs {file name: NIF bytes}) skinned with their own
    weights onto the Handy rig. Every shape is posed on the rig's bind (skeleton.hkx reference pose + bind_overrides:
    the legs follow Pelvis onto COM exactly as Fallout 4 draws them while every clip holds Pelvis there); shapes
    with a BSEffectShaderProperty (the eye lens, HandyLens.BGEM) have no Starfield material yet and are left out;
    the rest merge by texture set into TEXTURE_GROUPS shapes. Returns (files, report, skeleton in metres (final),
    {hkx name: final name})."""
    skel_fo4 = source_skeleton(fo4_skeleton_hkx, bind_overrides)
    skel, corr, final_names = finish_skeleton(skel_fo4, unit_scale, rebase, extra_bones, rename)
    world = skel_fo4.world()

    def lookup(name):
        return skel_fo4.names[skel_fo4.index(name)]         # case-insensitive (TorsoHandy says SPINE1 / SPINE2)

    def bone_world(name):
        return world[skel_fo4.index(name)]

    groups: dict = {}
    placed, skipped = [], []
    for fname, inst in placements:
        n = nifmod.parse(part_nifs[fname])
        for s in nifmod.fo4_trishapes(n, placed=True):
            sname = s.name.decode("latin-1")
            stem = _diffuse_stem(n, s)
            if stem not in TEXTURE_GROUPS:
                skipped.append({"part": fname, "instance": inst, "shape": sname, "verts": len(s.positions),
                                "shader": n.type_of(s.shader_ref) if s.shader_ref >= 0 else None,
                                "why": "no Starfield material for this shader (effect shader / unknown texture set)"})
                continue
            skin = fo4skin.read_skin(n, s.block)
            if skin is None:
                raise ValueError(f"{fname} {sname}: not skinned")
            pos, nrm, tan, inf, spread = pose_part(n, s, skin, bone_world, inst, lookup)
            g = groups.setdefault(TEXTURE_GROUPS[stem], {"positions": [], "uvs": [], "normals": [], "tangents": [],
                                                         "triangles": [], "influences": [], "sources": []})
            base = len(g["positions"])
            if (bool(s.uvs), bool(nrm), bool(tan)) != (True, True, True):
                raise ValueError(f"{fname} {sname}: uvs / normals / tangents missing")
            g["positions"] += pos
            g["uvs"] += list(s.uvs)
            g["normals"] += nrm
            g["tangents"] += tan
            g["triangles"] += [(a + base, b + base, c + base) for a, b, c in s.triangles]
            g["influences"] += [[(final_names[b], w) for b, w in row] for row in inf]
            g["sources"].append(f"{fname}:{sname}" + ("" if inst is None else f"|{inst}"))
            placed.append({"part": fname, "instance": inst, "shape": sname, "group": TEXTURE_GROUPS[stem],
                           "verts": len(pos), "tris": len(s.triangles), "bones": sorted({b for r in inf for b, _ in r}),
                           "bind_spread_fo4_units": round(spread, 6)})
    parts, expected_pos, expected_inf = [], {}, {}
    for gname in [g for g in TEXTURE_GROUPS.values() if g in groups]:
        g = groups[gname]
        shape = nifmod.Fo4Shape(gname.encode("latin-1"), (0.0, 0.0, 0.0), actor_skin.IDENT_R, 1.0, -1, -1, -1,
                                g["positions"], g["uvs"], g["normals"], g["tangents"], [], g["triangles"], True)
        parts.append(actor_skin.SkinPart(gname, shape, g["influences"],
                                         materials.get(gname, convert_static.PLACEHOLDER_MATERIAL)))
        expected_pos[gname] = [tuple(c * unit_scale for c in p) for p in g["positions"]]
        expected_inf[gname] = g["influences"]
    files, built = _build_files(skel, parts, expected_pos, expected_inf, unit_scale, sf_mesh_template,
                                sf_skeleton_template, mesh_exclude)
    report = {
        "source": "Codsworth's object-template parts (Fallout4.esm NPC_ 000179FF)", "skeleton_source": SRC_SKELETON,
        "unit_scale": unit_scale, "bind_overrides_fo4_units": {k: list(v) for k, v in (bind_overrides or {}).items()},
        "placed": placed, "skipped": skipped,
        "bind_spread_max_fo4_units": max(p["bind_spread_fo4_units"] for p in placed),
        "groups": {k: {"sources": v["sources"], "verts": len(v["positions"]), "tris": len(v["triangles"])}
                   for k, v in groups.items()},
        "skeleton": dict(built["skeleton"], **_skeleton_report(skel, skel_fo4, corr, final_names, rebase, extra_bones)),
        "mapping_final_names": dict(final_names),
        **{k: v for k, v in built.items() if k != "skeleton"},
        "files": sorted(files),
    }
    return files, report, skel, final_names


def read_codsworth_parts(fo4_meshes_ba2: ba2.Ba2, placements=CODSWORTH_PARTS) -> dict:
    """{file name: NIF bytes} of every part in `placements`, from Fallout4 - Meshes.ba2."""
    out = {}
    for fname, _inst in placements:
        if fname not in out:
            i = fo4_meshes_ba2.find(PARTS_DIR + fname)
            if i is None:
                raise FileNotFoundError(PARTS_DIR + fname)
            out[fname] = fo4_meshes_ba2.read(i)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fo4-data", default=FO4_DATA)
    ap.add_argument("--sf-data", default=SF_DATA)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--codsworth-report", default=CODSWORTH_REPORT)
    ap.add_argument("--skeleton-template", choices=sorted(SF_SKELETON_TEMPLATES), default="minibota")
    ap.add_argument("--bone-map-a", default=BONE_MAP_A, help="builder A's map to cross-check (optional)")
    ap.add_argument("--snap-to-skeleton", action="store_true",
                    help="pose each part on the hkx reference pose (joints exact, parts move a few cm); see convert()")
    a = ap.parse_args(argv)
    if os.path.abspath(a.out).lower().startswith(os.path.abspath(r"D:\SteamLibrary").lower()):
        raise SystemExit("refusing to write under the game library")
    materials = dict(HANDY_MATERIALS)
    if os.path.exists(a.codsworth_report):
        with open(a.codsworth_report, encoding="utf-8") as fh:
            materials.update(json.load(fh).get("materials", {}))
    sf = os.path.join(a.sf_data, "Starfield - Meshes*.ba2")
    files, report, skel, mapping = convert(
        _read_ba2(os.path.join(a.fo4_data, "Fallout4 - Meshes.ba2"), SRC_MESH),
        _read_ba2(os.path.join(a.fo4_data, "Fallout4 - Animations.ba2"), SRC_SKELETON),
        _read_ba2(sf, SF_MESH_TEMPLATE), _read_ba2(sf, SF_SKELETON_TEMPLATES[a.skeleton_template]), materials,
        snap_to_skeleton=a.snap_to_skeleton)
    report["skeleton_template"] = SF_SKELETON_TEMPLATES[a.skeleton_template]
    report["materials"] = materials
    if os.path.exists(a.bone_map_a):
        with open(a.bone_map_a, encoding="utf-8") as fh:
            other = json.load(fh)
        other = other.get("map", other.get("mapping", other)) if isinstance(other, dict) else {}
        flat = {k: (v if isinstance(v, str) else (v or {}).get("hkx") if isinstance(v, dict) else None)
                for k, v in other.items()} if isinstance(other, dict) else {}
        report["builder_a_map_check"] = {
            "path": a.bone_map_a,
            "agree": sorted(k for k in mapping if flat.get(k) == mapping[k]),
            "disagree": {k: {"C": mapping[k], "A": flat.get(k)} for k in mapping if k in flat and flat[k] != mapping[k]},
            "missing_in_A": sorted(k for k in mapping if k not in flat)}
    else:
        report["builder_a_map_check"] = f"not present at {a.bone_map_a} when this ran"
    data_root = os.path.join(a.out, "Data")
    for rel, data in files.items():
        path = os.path.join(data_root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
    with open(os.path.join(a.out, "handy_skeleton.json"), "w", encoding="utf-8") as fh:
        json.dump(skel.to_json(), fh, indent=1)
    with open(os.path.join(a.out, "handy_bone_map.json"), "w", encoding="utf-8") as fh:
        json.dump({"mesh_to_hkx": report["mapping"], "evidence_fo4_units": report["mapping_evidence_fo4_units"]}, fh,
                  indent=1)
    with open(os.path.join(a.out, "convert_handy_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, default=str)
    ok = report["verify_mesh"]["ok"] and report["verify_skeleton"]["ok"] and report["verify_skeleton_ref"]["ok"]
    print(json.dumps({"ok": ok, "out": data_root, "files": report["files"],
                      "errors": report["verify_mesh"]["errors"] + report["verify_skeleton"]["errors"]
                      + report["verify_skeleton_ref"]["errors"],
                      "shapes": {k: {x: v[x] for x in ("verts", "weights_per_vertex", "bones", "bind_pose_max_error_mm",
                                                       "weight_max_error", "influence_histogram")}
                                 for k, v in report["verify_mesh"]["shapes"].items()},
                      "mesh_bones_without_skeleton_partner": report["mesh_bones_without_skeleton_partner"],
                      "builder_a_map_check": report["builder_a_map_check"] if isinstance(report["builder_a_map_check"], str)
                      else {k: (len(v) if k != "path" else v) for k, v in report["builder_a_map_check"].items()}},
                     indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
