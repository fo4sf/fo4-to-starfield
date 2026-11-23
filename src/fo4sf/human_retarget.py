"""Fallout 4 human clips on Starfield's human rig (human-animation lane, 23 Nov 2026).

Converted humans stay on Starfield's HumanRace (faces, outfits, dialogue, AI), so a Fallout 4 clip is retargeted onto
Starfield's own human rig (`meshes/actors/human/characterassets/skeleton.rig`, 97 bones) instead of shipping Fallout 4's
skeleton. Doc: docs/actors/human-animation.md. Everything here was measured offline; nothing was run in the game.

Measured facts this module relies on (docs/actors/human-animation.md has the numbers):
- Fallout 4 `skeleton.hkx` (95 bones, Havok units, x 1/70 = metres) and the Starfield rig share only 8 bone names
  (Root, COM, Weapon, WeaponLeft, Camera, Camera Control, AnimObjectA/B); the body map is by anatomy (`BODY_MAP`).
- Both are Z up, +Y forward (FO4 walkforward root motion +Y, Starfield relaxed_walkforward +Y).
- Bone-local axis conventions differ (FO4 COM is turned -90 deg about Y, Starfield's is not; Starfield's C_Hips is turned
  180 deg; limb bones differ by up to 180 deg about their own axis), and the rest poses differ (arm and leg angles), so
  local rotations cannot be copied. The retarget matches ANATOMICAL frames in model space: each mapped bone gets a frame
  built from joint landmarks of its own skeleton at rest (bone direction to the next joint plus a second direction:
  the elbow plane, the palm, world forward / up), held rigidly by the bone. Per frame the Starfield bone takes the world
  rotation that puts its anatomical frame where the Fallout 4 bone's anatomical frame is:
      W_sf(f) = W_fo4(f) * C_fo4 * C_sf^-1,   C = W_rest^-1 * F_rest   (constant per bone).
  At the rest-aligned pose the Starfield rig is exactly at its bind; for world-aligned frames (`WORLD`) this is the
  plain transfer of the world rotation delta from rest.
- Starfield has more spine and neck joints (C_Spine..C_Chest, C_Neck, C_Neck1) than Fallout 4 (Spine1, Spine2, Chest,
  Neck): C_Spine1 and C_Neck1 take the slerp of their two neighbours' frames.
- Translation: only COM and Root move. The hip-joint centre (mid point of the thighs' joints) follows Fallout 4's,
  scaled by the hip height ratio k (Starfield rest hip height / Fallout 4 rest hip height); COM is solved so that the
  hips land there. Root motion (FO4 hkaDefaultAnimatedReferenceFrame x, y, z, yaw) is scaled by k as well.
- Starfield .af offsets of the human rig compose as  q_local = q_bind * q_offset  and  t_local = t_bind + t_offset
  (translation NOT rotated by the bind rotation): with that rule the vanilla R_HandIk / L_HandIk bones sit on the
  wrists within 0.4 mm in three vanilla clips, with actor_anim's rotated rule they are 0.6 to 0.86 m away
  (`offsets_from_local` / `local_from_offsets`; actor_anim is left as it is).
- Vanilla human clips store 82 bones in the header: the 15 twist bones (keys 142 to 156) are the last 15 rig bones and
  are never in a clip ("twist bones cannot be animated"); `clip_bones` returns that prefix.

Pure Python except where a Calumi object (actor_anim) is passed in.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from . import actor_anim as aa

FO4_UNIT = 1.0 / 70.0
FPS = 30.0
IDENTITY = (0.0, 0.0, 0.0, 1.0)
SF_HUMAN_RIG = "meshes/actors/human/characterassets/skeleton.rig"
SF_HUMAN_RIG_FEMALE = "meshes/actors/human/characterassets/female/skeleton.rig"
SF_FIRST_PERSON_RIG = "meshes/actors/human/_1stperson/characterassets/skeleton.rig"
FO4_HUMAN_SKELETON = "meshes/actors/character/characterassets/skeleton.hkx"
FO4_FIRST_PERSON_SKELETON = "meshes/actors/character/_1stperson/characterassets/skeleton.hkx"
TWIST_KEYS = range(142, 157)          # rig map keys of the 15 twist bones (never in a vanilla clip)


class RetargetError(ValueError):
    pass


# ============================================================================================ quaternion / vector helpers
def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _scale(v, s):
    return tuple(x * s for x in v)


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(v):
    n = math.sqrt(_dot(v, v))
    if n < 1e-12:
        raise RetargetError(f"zero-length direction {v}")
    return tuple(x / n for x in v)


def quat_from_basis(x_axis, y_axis):
    """Rotation whose local +X is `x_axis` and whose local +Y is the part of `y_axis` orthogonal to it."""
    x = _unit(x_axis)
    y = _sub(y_axis, _scale(x, _dot(y_axis, x)))
    y = _unit(y)
    z = _cross(x, y)
    m = (x[0], y[0], z[0], x[1], y[1], z[1], x[2], y[2], z[2])      # columns x, y, z (row-major storage)
    tr = m[0] + m[4] + m[8]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        q = ((m[7] - m[5]) / s, (m[2] - m[6]) / s, (m[3] - m[1]) / s, 0.25 * s)
    elif m[0] > m[4] and m[0] > m[8]:
        s = math.sqrt(1.0 + m[0] - m[4] - m[8]) * 2
        q = (0.25 * s, (m[1] + m[3]) / s, (m[2] + m[6]) / s, (m[7] - m[5]) / s)
    elif m[4] > m[8]:
        s = math.sqrt(1.0 + m[4] - m[0] - m[8]) * 2
        q = ((m[1] + m[3]) / s, 0.25 * s, (m[5] + m[7]) / s, (m[2] - m[6]) / s)
    else:
        s = math.sqrt(1.0 + m[8] - m[0] - m[4]) * 2
        q = ((m[2] + m[6]) / s, (m[5] + m[7]) / s, 0.25 * s, (m[3] - m[1]) / s)
    return aa.q_norm(q)


def quat_between(a, b) -> tuple:
    """Smallest rotation taking direction a to direction b."""
    a, b = _unit(a), _unit(b)
    c = _dot(a, b)
    if c < -1.0 + 1e-9:
        axis = _cross(a, (1.0, 0.0, 0.0))
        if _dot(axis, axis) < 1e-12:
            axis = _cross(a, (0.0, 1.0, 0.0))
        return aa.q_from_axis_angle(_unit(axis), math.pi)
    x, y, z = _cross(a, b)
    return aa.q_norm((x, y, z, 1.0 + c))


def two_bone_ik(hip, knee, ankle, target, pole_fallback=(0.0, 1.0, 0.0)):
    """Knee position that puts a two-bone chain (lengths |knee-hip|, |ankle-knee|) on `target`, keeping the bend
    plane of the given knee. Returns (new knee, reached ankle, distance to target that could not be reached)."""
    a = math.dist(hip, knee)
    b = math.dist(knee, ankle)
    to = _sub(target, hip)
    d_want = math.sqrt(_dot(to, to))
    if d_want < 1e-9:
        return knee, ankle, 0.0
    lo, hi = abs(a - b) + 1e-6, a + b - 1e-6
    d = min(max(d_want, lo), hi)
    u = _scale(to, 1.0 / d_want)
    kv = _sub(knee, hip)
    pole = _sub(kv, _scale(u, _dot(kv, u)))
    if _dot(pole, pole) < 1e-12:
        pole = _sub(pole_fallback, _scale(u, _dot(pole_fallback, u)))
    pole = _unit(pole)
    cos_a = max(-1.0, min(1.0, (a * a + d * d - b * b) / (2 * a * d)))
    sin_a = math.sqrt(max(0.0, 1.0 - cos_a * cos_a))
    new_knee = _add(hip, _add(_scale(u, a * cos_a), _scale(pole, a * sin_a)))
    reached = _add(hip, _scale(u, d))
    return new_knee, reached, abs(d_want - d)


def world_of(parents: Sequence[int], local: Sequence[tuple]) -> List[tuple]:
    """Model-space (t, q) of every bone from parent-local (t, q) (parents before children)."""
    out = []
    for i, (t, q) in enumerate(local):
        p = parents[i]
        if p < 0:
            out.append((tuple(t), aa.q_norm(q)))
        else:
            pt, pq = out[p]
            out.append((_add(pt, aa.q_rotate(pq, t)), aa.q_norm(aa.q_mul(pq, q))))
    return out


def yaw_quat(yaw: float) -> tuple:
    return (0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))


# ============================================================================================ skeletons
@dataclass
class Skel:
    """A skeleton in metres: names, parents, parent-local rest (t, q)."""
    names: List[str]
    parents: List[int]
    rest: List[tuple]

    def index(self) -> Dict[str, int]:
        return {n: i for i, n in enumerate(self.names)}

    def rest_world(self) -> List[tuple]:
        return world_of(self.parents, self.rest)


def fo4_skeleton(hkx: bytes, unit: float = FO4_UNIT) -> Skel:
    """Fallout 4 skeleton.hkx (first hkaSkeleton) in metres."""
    from . import hkanim
    sk = hkanim.load(hkx).skeletons[0]
    return Skel(list(sk.bones), list(sk.parents),
                [(_scale(t, unit), aa.q_norm(q)) for t, q, _s in sk.reference_pose])


def sf_skeleton(bones: Sequence[dict]) -> Skel:
    """A Starfield rig read by actor_anim.Calumi.read_rig (bone dicts)."""
    return Skel([b["name"] for b in bones], [b["parent"] for b in bones],
                [(tuple(b["translation"]), aa.q_norm(b["rotation"])) for b in bones])


def clip_bones(bones: Sequence[dict]) -> List[dict]:
    """The rig prefix a vanilla human clip addresses (header bone count 82 of 97): every bone before the first twist
    bone. Refuses a rig whose twist bones (map keys 142..156) are not exactly its tail."""
    twist = [i for i, b in enumerate(bones) if b.get("key") is not None and b["key"] in TWIST_KEYS]
    if not twist:
        return list(bones)
    first = min(twist)
    if twist != list(range(first, len(bones))):
        raise RetargetError("the twist bones are not the tail of the rig")
    return list(bones[:first])


# ============================================================================================ the bone map
# A landmark frame spec: (primary, secondary), each a vector spec evaluated at REST in model space:
#   ("to", bone)          from the bone's own joint to that joint
#   ("from_to", a, b)     from joint a to joint b
#   ("dir", (x, y, z))    a fixed model-space direction
#   ("cross", s1, s2)     cross product of two vector specs
WORLD = (("dir", (0.0, 1.0, 0.0)), ("dir", (0.0, 0.0, 1.0)))


@dataclass(frozen=True)
class Pair:
    sf: str                      # Starfield bone
    fo4: Tuple[str, ...]         # (bone,) or (bone_a, bone_b) blended by `blend`
    sf_frame: tuple = WORLD
    fo4_frame: tuple = WORLD
    chain: str = ""
    blend: float = 0.0           # weight of fo4[1] when two bones are given
    fo4_frame_b: tuple = WORLD   # landmark frame of fo4[1]


def _side_pairs(s: str) -> List[Pair]:
    """Arm, hand, finger and leg pairs of one side (s = 'L' or 'R')."""
    S = s
    arm, leg = f"{S}Arm_", f"{S}Leg_"
    p = [
        Pair(f"{s}_Thigh", (leg + "Thigh",), (("to", f"{s}_Calf"), ("dir", (0, 1, 0))),
             (("to", leg + "Calf"), ("dir", (0, 1, 0))), f"{s}_leg"),
        Pair(f"{s}_Calf", (leg + "Calf",), (("to", f"{s}_Foot"), ("dir", (0, 1, 0))),
             (("to", leg + "Foot"), ("dir", (0, 1, 0))), f"{s}_leg"),
        Pair(f"{s}_Foot", (leg + "Foot",), (("to", f"{s}_Toe"), ("dir", (0, 0, 1))),
             (("to", leg + "Toe1"), ("dir", (0, 0, 1))), f"{s}_leg"),
        Pair(f"{s}_Toe", (leg + "Toe1",), WORLD, WORLD, f"{s}_leg"),
        Pair(f"{s}_Clavicle", (arm + "Collarbone",), (("to", f"{s}_Biceps"), ("dir", (0, 1, 0))),
             (("to", arm + "UpperArm"), ("dir", (0, 1, 0))), f"{s}_arm"),
        Pair(f"{s}_Biceps", (arm + "UpperArm",), (("to", f"{s}_Forearm"), ("from_to", f"{s}_Forearm", f"{s}_Wrist")),
             (("to", arm + "ForeArm1"), ("from_to", arm + "ForeArm1", arm + "Hand")), f"{s}_arm"),
        Pair(f"{s}_Forearm", (arm + "ForeArm1",), (("to", f"{s}_Wrist"), ("to", f"{s}_Biceps")),
             (("to", arm + "Hand"), ("to", arm + "UpperArm")), f"{s}_arm"),
        Pair(f"{s}_Wrist", (arm + "Hand",), (("to", f"{s}_Middle"), ("from_to", f"{s}_Index", f"{s}_Pinky")),
             (("to", arm + "Finger31"), ("from_to", arm + "Finger21", arm + "Finger51")), f"{s}_arm"),
    ]
    lateral_sf = ("from_to", f"{s}_Index", f"{s}_Pinky")
    lateral_fo4 = ("from_to", arm + "Finger21", arm + "Finger51")
    palm_sf = ("cross", ("to", f"{s}_Middle"), lateral_sf)
    palm_fo4 = ("cross", ("from_to", arm + "Hand", arm + "Finger31"), lateral_fo4)
    for name, n in (("Thumb", 1), ("Index", 2), ("Middle", 3), ("Ring", 4), ("Pinky", 5)):
        sf_j = [f"{s}_{name}", f"{s}_{name}1", f"{s}_{name}2"]
        fo_j = [f"{arm}Finger{n}{k}" for k in (1, 2, 3)]
        sec_sf, sec_fo = (palm_sf, palm_fo4) if name == "Thumb" else (lateral_sf, lateral_fo4)
        for k in range(3):
            if k < 2:
                prim_sf, prim_fo = ("to", sf_j[k + 1]), ("to", fo_j[k + 1])
            else:
                prim_sf, prim_fo = ("from_to", sf_j[k - 1], sf_j[k]), ("from_to", fo_j[k - 1], fo_j[k])
            p.append(Pair(sf_j[k], (fo_j[k],), (prim_sf, sec_sf), (prim_fo, sec_fo), f"{s}_fingers"))
    return p


BODY_MAP: Tuple[Pair, ...] = tuple([
    Pair("COM", ("COM",), chain="spine"),
    Pair("C_Hips", ("Pelvis",), chain="spine"),
    Pair("C_Spine", ("Spine1",), chain="spine"),
    Pair("C_Spine1", ("Spine1", "Spine2"), chain="spine", blend=0.5),
    Pair("C_Spine2", ("Spine2",), chain="spine"),
    Pair("C_Chest", ("Chest",), chain="spine"),
    Pair("C_Neck", ("Neck",), chain="head"),
    Pair("C_Neck1", ("Neck", "Head"), chain="head", blend=0.5),
    Pair("C_Head", ("Head",), chain="head"),
] + _side_pairs("L") + _side_pairs("R"))

# Joint positions compared by the FK check (Starfield joint, Fallout 4 joint, chain). "HIPS" is the mid point of the
# thigh joints in either skeleton.
JOINTS: Tuple[Tuple[str, str, str], ...] = tuple(
    [("HIPS", "HIPS", "spine"), ("C_Chest", "Chest", "spine"), ("C_Neck", "Neck", "head"), ("C_Head", "Head", "head")]
    + [x for s in "LR" for x in (
        (f"{s}_Calf", f"{s}Leg_Calf", f"{s}_leg"), (f"{s}_Foot", f"{s}Leg_Foot", f"{s}_leg"),
        (f"{s}_Toe", f"{s}Leg_Toe1", f"{s}_leg"),
        (f"{s}_Biceps", f"{s}Arm_UpperArm", f"{s}_arm"), (f"{s}_Forearm", f"{s}Arm_ForeArm1", f"{s}_arm"),
        (f"{s}_Wrist", f"{s}Arm_Hand", f"{s}_arm"),
        (f"{s}_Index2", f"{s}Arm_Finger23", f"{s}_fingers"), (f"{s}_Thumb2", f"{s}Arm_Finger13", f"{s}_fingers"),
        (f"{s}_Pinky2", f"{s}Arm_Finger53", f"{s}_fingers"))])

# Bone segments whose direction is compared (Starfield from, to; Fallout 4 from, to; chain).
SEGMENTS: Tuple[Tuple[str, str, str, str, str], ...] = tuple(
    [("HIPS", "C_Neck", "HIPS", "Neck", "spine"), ("C_Neck", "C_Head", "Neck", "Head", "head")]
    + [x for s in "LR" for x in (
        (f"{s}_Thigh", f"{s}_Calf", f"{s}Leg_Thigh", f"{s}Leg_Calf", f"{s}_leg"),
        (f"{s}_Calf", f"{s}_Foot", f"{s}Leg_Calf", f"{s}Leg_Foot", f"{s}_leg"),
        (f"{s}_Foot", f"{s}_Toe", f"{s}Leg_Foot", f"{s}Leg_Toe1", f"{s}_leg"),
        (f"{s}_Clavicle", f"{s}_Biceps", f"{s}Arm_Collarbone", f"{s}Arm_UpperArm", f"{s}_arm"),
        (f"{s}_Biceps", f"{s}_Forearm", f"{s}Arm_UpperArm", f"{s}Arm_ForeArm1", f"{s}_arm"),
        (f"{s}_Forearm", f"{s}_Wrist", f"{s}Arm_ForeArm1", f"{s}Arm_Hand", f"{s}_arm"),
        (f"{s}_Wrist", f"{s}_Middle", f"{s}Arm_Hand", f"{s}Arm_Finger31", f"{s}_arm"),
        (f"{s}_Index", f"{s}_Index1", f"{s}Arm_Finger21", f"{s}Arm_Finger22", f"{s}_fingers"),
        (f"{s}_Thumb", f"{s}_Thumb1", f"{s}Arm_Finger11", f"{s}Arm_Finger12", f"{s}_fingers"))])


# ============================================================================================ landmark frames
def _vec(spec, me: str, pos: Dict[str, tuple]) -> tuple:
    kind = spec[0]
    if kind == "to":
        return _sub(pos[spec[1]], pos[me])
    if kind == "from_to":
        return _sub(pos[spec[2]], pos[spec[1]])
    if kind == "dir":
        return tuple(float(v) for v in spec[1])
    if kind == "cross":
        return _cross(_vec(spec[1], me, pos), _vec(spec[2], me, pos))
    raise RetargetError(f"unknown vector spec {spec!r}")


def landmark_frame(bone: str, spec: tuple, pos: Dict[str, tuple]) -> tuple:
    """Model-space rotation of a landmark frame (local X = primary, local Y = secondary made orthogonal)."""
    a, b = _unit(_vec(spec[0], bone, pos)), _unit(_vec(spec[1], bone, pos))
    if abs(_dot(a, b)) > math.cos(math.radians(15.0)):
        raise RetargetError(f"{bone}: landmark directions within 15 deg of each other ({spec!r})")
    return quat_from_basis(a, b)


def _positions(skel: Skel, world) -> Dict[str, tuple]:
    pos = {n: world[i][0] for i, n in enumerate(skel.names)}
    return pos


def hip_centre(skel: Skel, world, left: str, right: str) -> tuple:
    ix = skel.index()
    return _scale(_add(world[ix[left]][0], world[ix[right]][0]), 0.5)


# ============================================================================================ the retargeter
@dataclass
class Retargeter:
    fo4: Skel
    sf: Skel
    pairs: Tuple[Pair, ...] = BODY_MAP
    # filled by prepare()
    c_fo4: Dict[str, tuple] = field(default_factory=dict)      # per FO4 bone used: C = W_rest^-1 F_rest (per pair key)
    c_sf: Dict[str, tuple] = field(default_factory=dict)
    k: float = 1.0
    fo4_hips_rest: tuple = (0.0, 0.0, 0.0)
    sf_hips_rest: tuple = (0.0, 0.0, 0.0)
    report: dict = field(default_factory=dict)
    leg_ik: bool = True          # ankles on k * the Fallout 4 ankles (two-bone IK, bend plane kept)
    ik_miss: List[float] = field(default_factory=list)          # per solved leg: target distance not reachable (m)
    fo4_ankle_rest_z: float = 0.0
    sf_ankle_rest_z: float = 0.0

    FO4_THIGHS = ("LLeg_Thigh", "RLeg_Thigh")
    SF_THIGHS = ("L_Thigh", "R_Thigh")
    IK_FULL_BELOW_M = 0.03       # Fallout 4 ankle height above its rest height: full IK below, none above IK_NONE_ABOVE_M
    IK_NONE_ABOVE_M = 0.10
    LEGS = (("L_Thigh", "L_Calf", "L_Foot", "LLeg_Foot"), ("R_Thigh", "R_Calf", "R_Foot", "RLeg_Foot"))

    def prepare(self) -> "Retargeter":
        fw, sw = self.fo4.rest_world(), self.sf.rest_world()
        fpos, spos = _positions(self.fo4, fw), _positions(self.sf, sw)
        fix, six = self.fo4.index(), self.sf.index()
        missing = [p.sf for p in self.pairs if p.sf not in six] + [b for p in self.pairs for b in p.fo4 if b not in fix]
        if missing:
            raise RetargetError(f"bones missing from the skeletons: {missing}")
        for p in self.pairs:
            self.c_sf[p.sf] = aa.q_norm(aa.q_mul(aa.q_conj(sw[six[p.sf]][1]), landmark_frame(p.sf, p.sf_frame, spos)))
            frames = (p.fo4_frame,) if len(p.fo4) == 1 else (p.fo4_frame, p.fo4_frame_b)
            for b, spec in zip(p.fo4, frames):
                key = f"{p.sf}<{b}"
                self.c_fo4[key] = aa.q_norm(aa.q_mul(aa.q_conj(fw[fix[b]][1]), landmark_frame(b, spec, fpos)))
        self.fo4_hips_rest = hip_centre(self.fo4, fw, *self.FO4_THIGHS)
        self.sf_hips_rest = hip_centre(self.sf, sw, *self.SF_THIGHS)
        if self.fo4_hips_rest[2] <= 0 or self.sf_hips_rest[2] <= 0:
            raise RetargetError("hip joints are not above the ground at rest")
        self.k = self.sf_hips_rest[2] / self.fo4_hips_rest[2]
        self.fo4_ankle_rest_z = sum(fw[fix[lg[3]]][0][2] for lg in self.LEGS) / 2.0
        self.sf_ankle_rest_z = sum(sw[six[lg[2]]][0][2] for lg in self.LEGS) / 2.0
        self.report = {"k_hip_height_ratio": self.k, "fo4_hip_height_m": self.fo4_hips_rest[2],
                       "sf_hip_height_m": self.sf_hips_rest[2], "fo4_ankle_height_m": self.fo4_ankle_rest_z,
                       "sf_ankle_height_m": self.sf_ankle_rest_z,
                       "leg_length_m": {"fo4": self._leg_length(self.fo4, ("LLeg_Thigh", "LLeg_Calf", "LLeg_Foot")),
                                        "sf": self._leg_length(self.sf, ("L_Thigh", "L_Calf", "L_Foot"))},
                       "rest_anatomical_offsets_deg": self.rest_offsets_deg(fw, sw)}
        return self

    @staticmethod
    def _leg_length(skel: Skel, chain) -> float:
        ix = skel.index()
        return sum(math.sqrt(_dot(skel.rest[ix[b]][0], skel.rest[ix[b]][0])) for b in chain[1:])

    def rest_offsets_deg(self, fw, sw) -> Dict[str, float]:
        """Per pair: angle between the two skeletons' rest world rotations once their anatomical frames are matched
        (how far the plain world-rotation copy would be off): angle(W_sf_rest, W_fo4_rest C_fo4 C_sf^-1)."""
        fix, six = self.fo4.index(), self.sf.index()
        out = {}
        for p in self.pairs:
            b = p.fo4[0]
            want = aa.q_mul(aa.q_mul(fw[fix[b]][1], self.c_fo4[f"{p.sf}<{b}"]), aa.q_conj(self.c_sf[p.sf]))
            out[p.sf] = round(math.degrees(aa.q_angle(want, fw[fix[b]][1])), 3)
        return out

    # ------------------------------------------------------------------------------------------------ one frame
    def target_world_rotations(self, fo4_world) -> Dict[str, tuple]:
        """{Starfield bone: model-space rotation} for every mapped bone at one Fallout 4 pose (model space)."""
        fix = self.fo4.index()
        out = {}
        for p in self.pairs:
            frames = []
            for b in p.fo4:
                frames.append(aa.q_mul(fo4_world[fix[b]][1], self.c_fo4[f"{p.sf}<{b}"]))
            f = frames[0] if len(frames) == 1 else aa.q_slerp(aa.q_norm(frames[0]), aa.q_norm(frames[1]), p.blend)
            out[p.sf] = aa.q_norm(aa.q_mul(f, aa.q_conj(self.c_sf[p.sf])))
        return out

    def pose(self, fo4_local, root=(0.0, 0.0, 0.0, 0.0), extras: Optional[Dict[str, tuple]] = None,
             world_rot: Optional[Dict[str, tuple]] = None) -> List[tuple]:
        """Starfield parent-local (t, q) of every rig bone for one Fallout 4 frame.

        fo4_local: Fallout 4 parent-local (t m, q) of every skeleton bone, with its Root at the identity (the clip is
        in place; root motion comes as `root` = (x, y, z, yaw) in Fallout 4 metres). extras: {bone: (t, q)} parent-local
        values held for unmapped bones (vanilla constants: weapon bones, cameras...). world_rot: {bone: model-space
        rotation relative to Root} for unmapped bones that must hold a world orientation (DirectAt). Unmapped bones
        otherwise keep their bind."""
        fw = world_of(self.fo4.parents, fo4_local)
        target = self.target_world_rotations(fw)
        extras = extras or {}
        world_rot = world_rot or {}
        sf = self.sf
        six = sf.index()
        x, y, z, yaw = root
        root_t, root_q = (x * self.k, y * self.k, z * self.k), yaw_quat(yaw)
        local: List[Optional[tuple]] = [None] * len(sf.names)
        world: List[Optional[tuple]] = [None] * len(sf.names)
        for i, name in enumerate(sf.names):
            p = sf.parents[i]
            bt, bq = sf.rest[i]
            if name in extras:
                t, q = extras[name]
            else:
                t, q = bt, bq
            if p < 0:
                t, q = root_t, root_q
                local[i] = (t, q)
                world[i] = (t, q)
                continue
            pt, pq = world[p]
            leg = next((lg for lg in self.LEGS if lg[0] == name), None) if self.leg_ik else None
            if leg is not None:
                self._solve_leg(leg, _add(pt, aa.q_rotate(pq, t)), fw, target, root_t, root_q)
            if name in target or name in world_rot:
                wq = target[name] if name in target else aa.q_mul(root_q, world_rot[name])
                q = aa.q_norm(aa.q_mul(aa.q_conj(pq), wq))
            local[i] = (tuple(t), aa.q_norm(q))
            world[i] = (_add(pt, aa.q_rotate(pq, t)), aa.q_norm(aa.q_mul(pq, q)))
            if name == "COM":
                # place COM so that the hip centre lands on k * the Fallout 4 hip centre (in the root's frame)
                fo4_h = hip_centre(self.fo4, fw, *self.FO4_THIGHS)
                want = _add(root_t, aa.q_rotate(root_q, _scale(fo4_h, self.k)))
                have = self._hips_from_com(world[i], target)
                shift = aa.q_rotate(aa.q_conj(pq), _sub(want, have))
                t = _add(t, shift)
                local[i] = (t, local[i][1])
                world[i] = (_add(pt, aa.q_rotate(pq, t)), world[i][1])
        return local

    def _solve_leg(self, leg, hip, fw, target, root_t, root_q) -> None:
        """Turn the thigh and calf targets so that the ankle reaches k * the Fallout 4 ankle (root frame); the foot keeps
        its own target rotation."""
        thigh, calf, foot, fo4_foot = leg
        six, fix = self.sf.index(), self.fo4.index()
        wt, wc = target[thigh], target[calf]
        knee = _add(hip, aa.q_rotate(wt, self.sf.rest[six[calf]][0]))
        ankle = _add(knee, aa.q_rotate(wc, self.sf.rest[six[foot]][0]))
        fo4_thigh = self.fo4.parents[fix[fo4_foot]]
        fo4_thigh = self.fo4.parents[fo4_thigh]                     # foot <- calf <- thigh
        fx, fy, fz = _scale(fw[fix[fo4_foot]][0], self.k)
        # the ankle height above the ground is the rig's own (Starfield's ankle joint sits 3 cm higher in its foot):
        # height = Starfield rest ankle height + k * (Fallout 4 ankle height - its rest ankle height)
        fz += self.sf_ankle_rest_z - self.k * self.fo4_ankle_rest_z
        want = _add(root_t, aa.q_rotate(root_q, (fx, fy, fz)))
        # keep Fallout 4's leg spacing relative to the hips: shift the target sideways (horizontally) by the difference
        # between the Starfield hip joint and the scaled Fallout 4 one (Starfield's hips are wider)
        fo4_hip = _add(root_t, aa.q_rotate(root_q, _scale(fw[fo4_thigh][0], self.k)))
        d = _sub(hip, fo4_hip)
        want = _add(want, (d[0], d[1], 0.0))
        new_knee, reached, miss = two_bone_ik(hip, knee, ankle, want, aa.q_rotate(root_q, (0.0, 1.0, 0.0)))
        r1 = quat_between(_sub(knee, hip), _sub(new_knee, hip))
        wt2 = aa.q_norm(aa.q_mul(r1, wt))
        wc1 = aa.q_mul(r1, wc)
        ankle1 = _add(new_knee, aa.q_rotate(wc1, self.sf.rest[six[foot]][0]))
        r2 = quat_between(_sub(ankle1, new_knee), _sub(reached, new_knee))
        wc2 = aa.q_norm(aa.q_mul(r2, wc1))
        # IK while the foot is on or near the ground, Fallout 4's own leg motion (FK) while it swings
        h = fw[fix[fo4_foot]][0][2] - self.fo4_ankle_rest_z
        lo, hi = self.IK_FULL_BELOW_M, self.IK_NONE_ABOVE_M
        w = 1.0 if h <= lo else 0.0 if h >= hi else (hi - h) / (hi - lo)
        target[thigh] = aa.q_slerp(aa.q_norm(wt), wt2, w) if w < 1.0 else wt2
        target[calf] = aa.q_slerp(aa.q_norm(wc), wc2, w) if w < 1.0 else wc2
        self.ik_miss.append(miss * w)

    def _hips_from_com(self, com_world, target) -> tuple:
        """Hip centre in model space for a COM world transform, with C_Hips at its target rotation (or bind)."""
        sf = self.sf
        six = sf.index()
        ct, cq = com_world
        hi = six["C_Hips"]
        ht, hq_local = sf.rest[hi]
        hq = target.get("C_Hips", aa.q_mul(cq, hq_local))
        hw = _add(ct, aa.q_rotate(cq, ht))
        pts = [_add(hw, aa.q_rotate(hq, sf.rest[six[t]][0])) for t in self.SF_THIGHS]
        return _scale(_add(pts[0], pts[1]), 0.5)


# ============================================================================================ clips
@dataclass
class Fo4Clip:
    """A decoded Fallout 4 clip on its skeleton: frames[f] = parent-local (t m, q) per skeleton bone (Root at the
    identity), root[f] = (x, y, z m, yaw rad) extracted motion, events [(time s, text)]."""
    frames: List[List[tuple]]
    root: List[tuple]
    events: List[Tuple[float, str]]
    fps: float
    blend: str
    stats: dict = field(default_factory=dict)

    @property
    def n(self) -> int:
        return len(self.frames)


def decode_fo4_clip(hkx: bytes, skel: Skel, unit: float = FO4_UNIT) -> Fo4Clip:
    """A Fallout 4 human clip (hkanim) on `skel`. Untracked bones hold the rest; the Root bone is forced to the
    identity and its motion is taken from the extracted reference frame (the measured Root track is reported)."""
    from . import hkanim
    h = hkanim.load(hkx)
    an, bd = h.animations[0], h.bindings[0]
    if bd.blend_hint != 0:
        raise RetargetError(f"{bd.blend_hint_name} clip: only NORMAL clips are retargeted")
    if abs(an.fps - FPS) > 1e-3:
        raise RetargetError(f"clip at {an.fps} fps; only {FPS} is handled")
    mapping = bd.transform_track_to_bone or list(range(an.num_transform_tracks))
    track_of = {b: t for t, b in enumerate(mapping)}
    root_track_max = 0.0
    frames = []
    for f in range(an.num_frames):
        fr = []
        for i in range(len(skel.names)):
            if i in track_of:
                t, q, _s = an.tracks[track_of[i]][f]
                t = _scale(t, unit)
                if i == 0:
                    root_track_max = max(root_track_max, max(abs(c) for c in t), math.degrees(aa.q_angle(q, IDENTITY)))
                    t, q = (0.0, 0.0, 0.0), IDENTITY
                fr.append((t, aa.q_norm(q)))
            else:
                fr.append(skel.rest[i] if i else ((0.0, 0.0, 0.0), IDENTITY))
        frames.append(fr)
    rf = an.reference_frame
    if rf is not None and len(rf.samples) == an.num_frames:
        root = [(x * unit, y * unit, z * unit, w) for x, y, z, w in rf.samples]
    else:
        root = [(0.0, 0.0, 0.0, 0.0)] * an.num_frames
    events = sorted((t, txt) for _n, lst in an.annotations for t, txt in lst)
    return Fo4Clip(frames, root, events, an.fps, bd.blend_hint_name,
                   {"frames": an.num_frames, "tracks": an.num_transform_tracks, "root_track_max": root_track_max})


def retarget_clip(rt: Retargeter, clip: Fo4Clip, extras=None, world_rot=None, root_motion=True) -> List[List[tuple]]:
    """Starfield parent-local poses (every rig bone) for every frame of a Fallout 4 clip."""
    return [rt.pose(fr, clip.root[f] if root_motion else (0.0, 0.0, 0.0, 0.0), extras, world_rot)
            for f, fr in enumerate(clip.frames)]


def attach_to(frames, skel: Skel, child: str, target: str, offset=((0.0, 0.0, 0.0), IDENTITY)) -> List[List[tuple]]:
    """Frames where bone `child` sits, in model space, at bone `target`'s transform times `offset` (t, q in the
    target's frame): used to put the hand IK targets on the wrists and a weapon in the hand. `child` must come after
    `target` in the rig or be independent of it."""
    ix = skel.index()
    ci, ti = ix[child], ix[target]
    out = []
    for fr in frames:
        w = world_of(skel.parents, fr)
        tt, tq = w[ti]
        want_t = _add(tt, aa.q_rotate(tq, offset[0]))
        want_q = aa.q_mul(tq, offset[1])
        pt, pq = w[skel.parents[ci]]
        inv = aa.q_conj(pq)
        row = list(fr)
        row[ci] = (aa.q_rotate(inv, _sub(want_t, pt)), aa.q_norm(aa.q_mul(inv, want_q)))
        out.append(row)
    return out


def set_world_rotations(skel: Skel, frame, rotations: Dict[str, tuple]) -> List[tuple]:
    """A copy of one frame (parent-local) where the named bones take the given model-space rotations (their children
    follow); translations are unchanged."""
    ix = skel.index()
    out = list(frame)
    world: List[Optional[tuple]] = [None] * len(out)
    for i, (t, q) in enumerate(out):
        p = skel.parents[i]
        name = skel.names[i]
        if p < 0:
            world[i] = (tuple(t), aa.q_norm(q))
            continue
        pt, pq = world[p]
        if name in rotations:
            q = aa.q_norm(aa.q_mul(aa.q_conj(pq), rotations[name]))
            out[i] = (t, q)
        world[i] = (_add(pt, aa.q_rotate(pq, t)), aa.q_norm(aa.q_mul(pq, q)))
    return out


ARMS = (("R", "R_Biceps", "R_Forearm", "R_Wrist", "RArm_Hand"), ("L", "L_Biceps", "L_Forearm", "L_Wrist", "LArm_Hand"))


def hold_weapon(rt: Retargeter, clip: Fo4Clip, frames, hand_weapon: tuple, root_motion=True) -> Tuple[list, dict]:
    """Gun clips: the Fallout 4 gun pose carried over in the gun's own space instead of through the arms.
      gun      model-space rotation = Fallout 4's Weapon rotation (both games: barrel +Y, up +Z, right +X; measured on
               the FO4 pistol ready idle and Starfield's grippistol ready_idle); position = Starfield chest +
               k * (Fallout 4 gun - Fallout 4 chest).
      right    wrist on the grip with Starfield's own hand-to-gun transform `hand_weapon` (from a vanilla gun clip).
      left     wrist where Fallout 4 holds its left hand relative to the gun (unscaled: the gun keeps its size), in the
               Starfield hand's anatomical frame.
    Both arms reach their wrist targets by two-bone IK from the shoulder (bend plane kept). Returns (frames, stats)."""
    six, fix = rt.sf.index(), rt.fo4.index()
    out, unreached, worst_l = [], 0.0, 0.0
    ht, hq = hand_weapon
    for f, (fr_fo, fr) in enumerate(zip(clip.frames, frames)):
        fw = world_of(rt.fo4.parents, fr_fo)
        root = clip.root[f] if root_motion else (0.0, 0.0, 0.0, 0.0)
        rq, rtv = yaw_quat(root[3]), _scale(root[:3], rt.k)
        to_world = lambda p: _add(rtv, aa.q_rotate(rq, p))  # noqa: E731
        sw = world_of(rt.sf.parents, fr)
        gun_q = aa.q_mul(rq, fw[fix["Weapon"]][1])
        gun_t = _add(sw[six["C_Chest"]][0], aa.q_rotate(rq, _scale(_sub(fw[fix["Weapon"]][0], fw[fix["Chest"]][0]), rt.k)))
        wrist = {}
        wrist["R"] = (_sub(gun_t, aa.q_rotate(aa.q_mul(gun_q, aa.q_conj(hq)), ht)), aa.q_norm(aa.q_mul(gun_q, aa.q_conj(hq))))
        inv_gun_fo4 = aa.q_conj(fw[fix["Weapon"]][1])
        l_rel_t = aa.q_rotate(inv_gun_fo4, _sub(fw[fix["LArm_Hand"]][0], fw[fix["Weapon"]][0]))
        l_rel_q = aa.q_mul(aa.q_mul(inv_gun_fo4, fw[fix["LArm_Hand"]][1]), rt.c_fo4["L_Wrist<LArm_Hand"])
        wrist["L"] = (_add(gun_t, aa.q_rotate(gun_q, l_rel_t)),
                      aa.q_norm(aa.q_mul(aa.q_mul(gun_q, l_rel_q), aa.q_conj(rt.c_sf["L_Wrist"]))))
        rots = {}
        for side, bic, fore, wri, _fo in ARMS:
            sh, el, wr = sw[six[bic]][0], sw[six[fore]][0], sw[six[wri]][0]
            new_el, reached, miss = two_bone_ik(sh, el, wr, wrist[side][0], aa.q_rotate(rq, (0.0, 0.0, -1.0)))
            unreached = max(unreached, miss)
            r1 = quat_between(_sub(el, sh), _sub(new_el, sh))
            wb = aa.q_mul(r1, sw[six[bic]][1])
            wf1 = aa.q_mul(r1, sw[six[fore]][1])
            wr1 = _add(new_el, aa.q_rotate(wf1, rt.sf.rest[six[wri]][0]))
            r2 = quat_between(_sub(wr1, new_el), _sub(reached, new_el))
            rots[bic], rots[fore], rots[wri] = aa.q_norm(wb), aa.q_norm(aa.q_mul(r2, wf1)), wrist[side][1]
        new = set_world_rotations(rt.sf, fr, rots)
        nw = world_of(rt.sf.parents, new)
        worst_l = max(worst_l, math.dist(nw[six["L_Wrist"]][0], wrist["L"][0]))
        out.append(new)
    out = attach_to(out, rt.sf, "Weapon", "R_Wrist", hand_weapon)
    return out, {"arm_ik_unreached_max_m": round(unreached, 5), "left_wrist_off_target_max_m": round(worst_l, 5)}


def relative_transform(world, a: int, b: int) -> tuple:
    """(t, q) of bone b in bone a's frame."""
    at, aq = world[a]
    bt, bq = world[b]
    inv = aa.q_conj(aq)
    return aa.q_rotate(inv, _sub(bt, at)), aa.q_norm(aa.q_mul(inv, bq))


# ============================================================================================ .af offsets (measured rule)
def offsets_from_local(bones: Sequence[dict], frames) -> Dict[str, list]:
    """{bone: [(t_offset, q_offset) per frame]} with the measured human-rig rule: q_o = q_b^-1 q, t_o = t - t_b.
    For actor_anim.build_blocks(keys_are='offset')."""
    out = {}
    for i, b in enumerate(bones):
        bt, bq = b["translation"], aa.q_norm(b["rotation"])
        inv = aa.q_conj(bq)
        out[b["name"]] = [(_sub(fr[i][0], bt), aa.q_norm(aa.q_mul(inv, fr[i][1]))) for fr in frames]
    return out


def local_from_offsets(bones: Sequence[dict], blocks, frame_count: int) -> List[List[tuple]]:
    """Parent-local poses of every rig bone from clip blocks (the inverse of offsets_from_local; a bone without a block
    holds its bind). Linear / slerp between keys (actor_anim.sample_block)."""
    by = {blk["bone"]: blk for blk in blocks}
    out = []
    for f in range(frame_count):
        fr = []
        for b in bones:
            bt, bq = tuple(b["translation"]), aa.q_norm(b["rotation"])
            blk = by.get(b["name"])
            if blk is None:
                fr.append((bt, bq))
                continue
            to, qo = aa.sample_block(blk, f)
            fr.append((_add(bt, to), aa.q_norm(aa.q_mul(bq, qo))))
        out.append(fr)
    return out


def blocks_for(bones: Sequence[dict], frames, frame_count: int, keep=()) -> list:
    """Clip blocks (actor_anim.build_blocks) for the clip bones (clip_bones prefix) from parent-local frames."""
    cb = clip_bones(bones)
    poses = offsets_from_local(cb, [fr[:len(cb)] for fr in frames])
    return aa.build_blocks(cb, poses, frame_count, keys_are="offset", keep=keep)


# ============================================================================================ FK comparison
def _named_points(skel: Skel, world, thighs) -> Dict[str, tuple]:
    pos = _positions(skel, world)
    pos["HIPS"] = hip_centre(skel, world, *thighs)
    return pos


def compare(rt: Retargeter, clip: Fo4Clip, sf_frames, root_motion=True, joints=JOINTS, segments=SEGMENTS) -> dict:
    """Per frame, Starfield FK (sf_frames, every rig bone) against Fallout 4 FK of the clip:
      position_m      |P_sf(j) - k * P_fo4(j)| in the root's frame (includes the proportion difference of the rigs)
      motion_m        |(P_sf(j, f) - P_sf(j, 0)) - k (P_fo4(j, f) - P_fo4(j, 0))|: the joint's own movement
      direction_deg   angle between the bone segments' directions (proportion-free)
      frame_deg       anatomical frame of every mapped bone (W C) against the Fallout 4 bone's (blends excluded)
    reduced to max / mean per chain."""
    six, fix = rt.sf.index(), rt.fo4.index()
    stats: Dict[str, Dict[str, list]] = {}

    def add(chain, metric, v):
        stats.setdefault(chain, {}).setdefault(metric, []).append(v)
    first_sf = first_fo = None
    prev = {}
    for f, (fr_fo, fr_sf) in enumerate(zip(clip.frames, sf_frames)):
        fw = world_of(rt.fo4.parents, fr_fo)
        sw = world_of(rt.sf.parents, fr_sf)
        root = clip.root[f] if root_motion else (0.0, 0.0, 0.0, 0.0)
        rq = yaw_quat(root[3])
        rtv = _scale(root[:3], rt.k)
        sw_rel = [(aa.q_rotate(aa.q_conj(rq), _sub(t, rtv)), aa.q_mul(aa.q_conj(rq), q)) for t, q in sw]
        # foot slide: while the Fallout 4 ankle is within 2 cm of its rest height in two frames running, the Starfield
        # ankle's horizontal world movement against k * the Fallout 4 ankle's (both with root motion)
        for thigh, calf, foot, fo4_foot in rt.LEGS:
            fa = _add(rtv, aa.q_rotate(rq, _scale(fw[fix[fo4_foot]][0], rt.k)))
            sa = sw[six[foot]][0]
            low = fw[fix[fo4_foot]][0][2] - rt.fo4_ankle_rest_z <= 0.02
            if foot in prev and prev[foot][2] and low:
                dsf = _sub(sa, prev[foot][0])
                dfo = _sub(fa, prev[foot][1])
                add(f"{foot[0]}_leg", "stance_slide_m", math.hypot(dsf[0] - dfo[0], dsf[1] - dfo[1]))
            prev[foot] = (sa, fa, low)
        ps = _named_points(rt.sf, sw_rel, rt.SF_THIGHS)
        pf = _named_points(rt.fo4, fw, rt.FO4_THIGHS)
        if first_sf is None:
            first_sf, first_fo = ps, pf
        for s_j, f_j, chain in joints:
            add(chain, "position_m", math.dist(ps[s_j], _scale(pf[f_j], rt.k)))
            ms = _sub(ps[s_j], first_sf[s_j])
            mf = _scale(_sub(pf[f_j], first_fo[f_j]), rt.k)
            add(chain, "motion_m", math.dist(ms, mf))
        for sa, sb, fa, fb, chain in segments:
            ds = _sub(ps[sb], ps[sa])
            df = _sub(pf[fb], pf[fa])
            c = max(-1.0, min(1.0, _dot(_unit(ds), _unit(df))))
            add(chain, "direction_deg", math.degrees(math.acos(c)))
        for p in rt.pairs:
            if len(p.fo4) != 1:
                continue
            a = aa.q_mul(sw_rel[six[p.sf]][1], rt.c_sf[p.sf])
            b = aa.q_mul(fw[fix[p.fo4[0]]][1], rt.c_fo4[f"{p.sf}<{p.fo4[0]}"])
            add(p.chain or "other", "frame_deg", math.degrees(aa.q_angle(a, b)))
    out = {}
    for chain, metrics in sorted(stats.items()):
        out[chain] = {m: {"max": round(max(v), 5), "mean": round(sum(v) / len(v), 5)} for m, v in sorted(metrics.items())}
    return out


def readback_error(bones: Sequence[dict], want_frames, got_frames) -> dict:
    """Largest parent-local and model-space differences between the frames written and the frames read back."""
    parents = [b["parent"] for b in bones]
    n = min(len(bones), len(want_frames[0]), len(got_frames[0]))
    worst = {"t_m": 0.0, "r_deg": 0.0, "model_mm": 0.0}
    for fa, fb in zip(want_frames, got_frames):
        wa, wb = world_of(parents[:n], fa[:n]), world_of(parents[:n], fb[:n])
        for i in range(n):
            worst["t_m"] = max(worst["t_m"], math.dist(fa[i][0], fb[i][0]))
            worst["r_deg"] = max(worst["r_deg"], math.degrees(aa.q_angle(fa[i][1], fb[i][1])))
            worst["model_mm"] = max(worst["model_mm"], math.dist(wa[i][0], wb[i][0]) * 1000.0)
    return {k: round(v, 6) for k, v in worst.items()}


# ============================================================================================ events
FO4_EVENT_MAP = {"SyncLeft": "SyncLeftFoot", "SyncRight": "SyncRightFoot", "FootLeft": "FootLeft", "FootRight": "FootRight"}


def foot_contacts(skel: Skel, frames, foot: str, toe: str) -> List[int]:
    """Frames where the foot is lowest within the cycle (local minima of the foot joint's height, ties to the first).
    Used to place foot events on clips whose events were not authored for Starfield."""
    ix = skel.index()
    zs = [world_of(skel.parents, fr)[ix[foot]][0][2] for fr in frames]
    n = len(zs)
    if n < 3:
        return [0]
    mins = [f for f in range(n) if zs[f] <= zs[(f - 1) % n] and zs[f] < zs[(f + 1) % n]]
    return mins or [min(range(n), key=lambda f: zs[f])]


def passes_under_hips(skel: Skel, frames, foot: str, thighs: Sequence[str]) -> List[int]:
    """Frames where the foot joint passes from in front of the hip centre to behind it (forward axis +Y, frames in
    place): the middle of that foot's stance. Starfield's SyncLeftFoot / SyncRightFoot sit there in its own walk, jog
    and run (docs/actors/human-animation.md), while Fallout 4 puts its Sync annotations on the landing frame."""
    ix = skel.index()
    rel = []
    for fr in frames:
        w = world_of(skel.parents, fr)
        rel.append(w[ix[foot]][0][1] - hip_centre(skel, w, *thighs)[1])
    out = []
    for f in range(len(rel) - 1):
        if rel[f] > 0 >= rel[f + 1]:
            out.append(f if abs(rel[f]) < abs(rel[f + 1]) else f + 1)
    return out


def fo4_events(clip: Fo4Clip, frame_count: int, mapping=FO4_EVENT_MAP) -> List[Tuple[int, str, str]]:
    """Fallout 4 annotations mapped to Starfield event names at the nearest frame (unmapped ones dropped)."""
    out = set()
    for t, text in clip.events:
        name = mapping.get(text)
        if name:
            out.add((min(frame_count - 1, max(0, int(round(t * FPS)))), name, ""))
    return sorted(out)


# ============================================================================================ manifests for an add-on race
def override_file_list(vanilla: Sequence[str], ours: Sequence[str]) -> List[str]:
    """animationfiledata clip list of a row whose first folder is ours: every vanilla entry whose file name (case
    ignored) one of ours shadows is replaced, in place, by ours; ours that shadow nothing are appended. The rule is the
    one vanilla AnimArchetypeAngry shows (its five files replace exactly the five same-named default entries)."""
    by_name = {}
    for p in ours:
        name = p.replace("/", "\\").rsplit("\\", 1)[-1].lower()
        if name in by_name:
            raise RetargetError(f"two clips named {name}")
        by_name[name] = p
    used, out = set(), []
    for v in vanilla:
        name = v.replace("/", "\\").rsplit("\\", 1)[-1].lower()
        if name in by_name and name.endswith(".af"):
            if name not in used:
                out.append(by_name[name])
                used.add(name)
            continue
        out.append(v)
    out += [p for n, p in by_name.items() if n not in used]
    return out


def animation_file_data_in_order(key: int, clips: Sequence[str]) -> bytes:
    """animationfiledata/<key>.txt with the clips in the given order (vanilla human lists are in graph order, not
    sorted, so handy_race.animation_file_data's sorted form does not reproduce them)."""
    return ("3\n1\n%d\n%d\n" % (key, len(clips)) + "".join(c + "\n" for c in clips)).encode("cp1252")


def parse_animation_file_data(raw: bytes) -> Tuple[int, List[str]]:
    lines = raw.decode("cp1252").split("\n")
    if lines[:2] != ["3", "1"] or int(lines[3]) != len(lines) - 5 or lines[-1] != "":
        raise RetargetError("not an animationfiledata file")
    return int(lines[2]), lines[4:-1]
