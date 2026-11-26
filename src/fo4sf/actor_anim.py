"""Starfield actor rigs (skeleton.rig) and clips (.af + .afx) written through the external CALUMI animation library.

Conventions, measured on the vanilla Garden Mini Bot (MiniBotARace 00227705; docs/actors/starfield-actor-anim-format.md):
- units are metres, axes right-handed Z up, +Y forward, +X right (walkforward.af moves Root +1.09 m on +Y, walkright +X,
  turninplace_left90 turns +90 degrees about +Z);
- a rig bone holds its PARENT-LOCAL bind: translation (m), rotation quaternion, scale 1; bones are stored parent first;
- a clip block (track) holds OFFSETS FROM THE BIND, not local transforms: every vanilla track of a bone with a rotated bind
  starts at identity (C_Arm2, bind 172 degrees, lookdirections.af), COM (bind z 0.5057 m) keys z -0.00075 m. This module
  composes local = bind * offset (offset applied in the bone's own rest frame: t = t_b + R_b t_o, R = R_b R_o), the rule the
  library's own Blender add-on uses (matrix_basis = POSE->LOCAL). For bones with an identity bind rotation the order is moot;
  for a rotated bind it is that add-on's rule, NOT verified in game;
- tracks exist only for bones that move; a constant offset is one key at frame 0; keys are integer frames at 30 fps;
- root motion is the Root bone's own translation / rotation track (Root bind is the identity), AND the .af header repeats
  the Root offset at the last frame (f32 w, x, y, z at 0x08; f32 x, y, z at 0x18): verified on 1,111 of 1,112 sampled vanilla
  clips (the one miss is a ship clip within its 2 mm precision). CALUMI writes identity / zero there, so write_clip patches
  the two fields (patch_root_motion) after the library saved the file.

Pure-Python parts (quaternions, validation, bind/offset conversion, track building, sampling, resampling, .afx) need nothing
external. Calumi wraps the DLL (path given by the caller or FO4SF_CALUMI_DLL; never shipped in the repository) for
write_rig / write_clip / read_rig / read_clip. Written files must stay outside the repository.
"""
import ctypes as c
import math
import os
import pathlib
import struct
import xml.etree.ElementTree as ET

from . import anim_object

FPS = 30
DEFAULT_DLL = r"D:\Modding\research\sf_animation_io\CALUMI.Animation.dll"
DLL_SHA256 = "8C138844D17126324068513E18D49B249B0E0CFB7DA998EC821C4359A1BF4D89"
IDENTITY = (0.0, 0.0, 0.0, 1.0)
PRECISIONS = ("default", "first_person", "ship")       # SFBGSRigPackage precision types 0, 1, 2 (vanilla Mini Bot: 0)
ROT_TOL = 1e-6          # quaternion component: below this a rotation offset counts as identity / unchanged
TRANS_TOL = 1e-6        # metres: below this a translation offset counts as zero / unchanged


class ActorAnimError(ValueError):
    pass


# ----------------------------------------------------------------------------------------------- quaternions (x, y, z, w)
def q_norm(q):
    x, y, z, w = (float(v) for v in q)
    n = math.sqrt(x * x + y * y + z * z + w * w)
    if not math.isfinite(n) or n < 1e-12:
        raise ActorAnimError(f"quaternion {q} has no direction")
    return (x / n, y / n, z / n, w / n)


def q_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def q_conj(q):
    return (-q[0], -q[1], -q[2], q[3])


def q_rotate(q, v):
    x, y, z, _w = q_mul(q_mul(q, (v[0], v[1], v[2], 0.0)), q_conj(q))
    return (x, y, z)


def q_dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def q_angle(a, b):
    """Angle in radians between two rotations (sign of the quaternion ignored)."""
    return 2 * math.acos(min(1.0, abs(q_dot(q_norm(a), q_norm(b)))))


def q_slerp(a, b, t):
    if q_dot(a, b) < 0:
        b = tuple(-v for v in b)
    d = min(1.0, q_dot(a, b))
    if d > 0.9995:
        return q_norm(tuple(x + (y - x) * t for x, y in zip(a, b)))
    th = math.acos(d)
    s = math.sin(th)
    wa, wb = math.sin((1 - t) * th) / s, math.sin(t * th) / s
    return q_norm(tuple(wa * x + wb * y for x, y in zip(a, b)))


def q_from_axis_angle(axis, radians):
    ax = math.sqrt(sum(v * v for v in axis))
    s = math.sin(radians / 2) / ax
    return (axis[0] * s, axis[1] * s, axis[2] * s, math.cos(radians / 2))


# ----------------------------------------------------------------------------------------------- bones
def validate_bones(bones):
    """Normalised copy of a bone list [{name, parent, translation, rotation(xyzw), scale=1, mirror=-1, key=None}].
    Rules (as the vanilla rigs): unique names, exactly one root (index 0, parent -1), every parent before its child,
    unit scale, finite values. Raises ActorAnimError."""
    if not bones:
        raise ActorAnimError("a rig needs at least one bone")
    out, seen = [], set()
    for i, b in enumerate(bones):
        name = b["name"]
        if not isinstance(name, str) or not name or name in seen:
            raise ActorAnimError(f"bone {i}: name {name!r} is empty or repeated")
        try:
            name.encode("ascii")
        except UnicodeEncodeError:
            raise ActorAnimError(f"bone {i}: name {name!r} is not ASCII") from None
        seen.add(name)
        parent = int(b["parent"])
        if (i == 0) != (parent == -1) or parent >= i or parent < -1:
            raise ActorAnimError(f"bone {i} {name}: parent {parent} (root must be index 0, parents before children)")
        t = tuple(float(v) for v in b.get("translation", (0.0, 0.0, 0.0)))
        scale = float(b.get("scale", 1.0))
        if len(t) != 3 or not all(math.isfinite(v) for v in t):
            raise ActorAnimError(f"bone {name}: translation {t}")
        if abs(scale - 1.0) > 1e-5:
            raise ActorAnimError(f"bone {name}: bind scale {scale} (rigs carry unit scale)")
        key = b.get("key")
        if key is not None and not 0 <= int(key) <= 255:
            raise ActorAnimError(f"bone {name}: map key {key} outside 0..255")
        out.append({"name": name, "parent": parent, "translation": t, "rotation": q_norm(b.get("rotation", IDENTITY)),
                    "scale": 1.0, "mirror": int(b.get("mirror", -1)), "key": None if key is None else int(key)})
    keys = [b["key"] for b in out if b["key"] is not None]
    if len(keys) != len(set(keys)):
        raise ActorAnimError("a map key names two bones")
    return out


def model_space(bones):
    """[(translation, rotation)] of every bone in model space (rest pose), for checks and previews."""
    out = []
    for b in bones:
        if b["parent"] < 0:
            out.append((tuple(b["translation"]), tuple(b["rotation"])))
        else:
            pt, pq = out[b["parent"]]
            r = q_rotate(pq, b["translation"])
            out.append((tuple(p + v for p, v in zip(pt, r)), q_norm(q_mul(pq, b["rotation"]))))
    return out


# ----------------------------------------------------------------------------------------------- bind <-> offset
def local_to_offset(bind_t, bind_q, t, q):
    """The .af offset of a parent-local pose (t, q) against the bind: q_o = q_b^-1 q, t_o = q_b^-1 (t - t_b)."""
    inv = q_conj(q_norm(bind_q))
    return q_rotate(inv, tuple(a - b for a, b in zip(t, bind_t))), q_norm(q_mul(inv, q_norm(q)))


def offset_to_local(bind_t, bind_q, t_o, q_o):
    """The parent-local pose of an .af offset: q = q_b q_o, t = t_b + q_b t_o (inverse of local_to_offset)."""
    bq = q_norm(bind_q)
    r = q_rotate(bq, t_o)
    return tuple(a + b for a, b in zip(bind_t, r)), q_norm(q_mul(bq, q_norm(q_o)))


# ----------------------------------------------------------------------------------------------- tracks
def _hemisphere(qs):
    out, prev = [], None
    for q in qs:
        q = q_norm(q)
        if prev is not None and q_dot(q, prev) < 0:
            q = tuple(-v for v in q)
        out.append(q)
        prev = q
    return out


def _canonical_identity(q):
    return q if q[3] >= 0 else tuple(-v for v in q)


def build_blocks(bones, poses, frame_count, keys_are="local", keep=(), rot_tol=ROT_TOL, trans_tol=TRANS_TOL):
    """Clip blocks from per-frame poses.

    poses: {bone name: [(translation, rotation_xyzw) for each frame 0..frame_count-1]}; a bone left out holds its bind.
    keys_are: 'local' (parent-local transforms, e.g. decoded from a FO4 .hkx; converted to offsets against the rig's bind)
    or 'offset' (already offsets from the bind, as an .af stores them).
    keep: bone names that get a block even when they never leave the bind (one identity rotation key at frame 0).
    Per channel, as vanilla: no channel when the offset is the identity / zero on every frame, one key at frame 0 when it is
    constant, else one key per frame. Returns [{bone, index, rot: [(frame, xyzw)], trans: [(frame, xyz)]}] in rig order."""
    if keys_are not in ("local", "offset"):
        raise ActorAnimError("keys_are is 'local' or 'offset'")
    frame_count = int(frame_count)
    if not 1 <= frame_count <= 65536:
        raise ActorAnimError(f"frame count {frame_count} outside 1..65536")
    index = {b["name"]: i for i, b in enumerate(bones)}
    unknown = sorted(set(poses) - set(index)) + sorted(set(keep) - set(index))
    if unknown:
        raise ActorAnimError(f"poses name bones the rig lacks: {unknown}")
    blocks = []
    for i, bone in enumerate(bones):
        name = bone["name"]
        if name not in poses:
            if name in keep:
                blocks.append({"bone": name, "index": i, "rot": [(0, IDENTITY)], "trans": []})
            continue
        frames = poses[name]
        if len(frames) != frame_count:
            raise ActorAnimError(f"{name}: {len(frames)} poses for {frame_count} frames")
        ts, qs = [], []
        for t, q in frames:
            t = tuple(float(v) for v in t)
            if len(t) != 3 or not all(math.isfinite(v) for v in t):
                raise ActorAnimError(f"{name}: translation {t}")
            if keys_are == "local":
                t, q = local_to_offset(bone["translation"], bone["rotation"], t, q)
            ts.append(t)
            qs.append(q_norm(q))
        qs = _hemisphere(qs)
        rot = []
        if any(q_angle(q, IDENTITY) > rot_tol for q in qs) or name in keep:
            if all(max(abs(a - b) for a, b in zip(q, qs[0])) <= rot_tol for q in qs):
                rot = [(0, _canonical_identity(qs[0]) if q_angle(qs[0], IDENTITY) <= rot_tol else qs[0])]
            else:
                rot = list(enumerate(qs))
        trans = []
        if any(max(abs(v) for v in t) > trans_tol for t in ts):
            if all(max(abs(a - b) for a, b in zip(t, ts[0])) <= trans_tol for t in ts):
                trans = [(0, ts[0])]
            else:
                trans = list(enumerate(ts))
        if rot or trans:
            blocks.append({"bone": name, "index": i, "rot": rot, "trans": trans})
    return blocks


def _interp(keys, frame, lerp, default):
    if not keys:
        return default
    if frame <= keys[0][0]:
        return keys[0][1]
    for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
        if f0 <= frame <= f1:
            return v0 if f1 == f0 else lerp(v0, v1, (frame - f0) / (f1 - f0))
    return keys[-1][1]


def _lerp3(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def sample_block(block, frame):
    """(offset translation, offset rotation) of a block at a frame: linear translation, slerp rotation between keys, the
    first / last key held outside them, identity / zero for an absent channel. The engine's own interpolation is not read
    (only key frames are compared exactly)."""
    return (_interp(block.get("trans", []), frame, _lerp3, (0.0, 0.0, 0.0)),
            _interp(_hemi_keys(block.get("rot", [])), frame, q_slerp, IDENTITY))


def _hemi_keys(keys):
    if not keys:
        return keys
    qs = _hemisphere([q for _f, q in keys])
    return [(f, q) for (f, _q), q in zip(keys, qs)]


def blocks_to_local_poses(bones, blocks, frame_count):
    """{bone: [(t, q) per frame]} parent-local poses of every bone that has a block (bind * offset)."""
    index = {b["name"]: b for b in bones}
    out = {}
    for blk in blocks:
        bone = index[blk["bone"]]
        out[blk["bone"]] = [offset_to_local(bone["translation"], bone["rotation"], *sample_block(blk, f))
                            for f in range(frame_count)]
    return out


def resample(frames, src_fps, dst_fps=FPS):
    """Per-frame [(t, q)] poses resampled from src_fps to dst_fps (linear / slerp). The clip keeps its length in seconds:
    (n - 1) / src_fps; the new frame count is round(that * dst_fps) + 1."""
    if src_fps <= 0 or dst_fps <= 0 or not frames:
        raise ActorAnimError("resample needs positive rates and at least one frame")
    if len(frames) == 1:
        return list(frames)
    seconds = (len(frames) - 1) / src_fps
    n = int(round(seconds * dst_fps)) + 1
    out = []
    for k in range(n):
        x = min(len(frames) - 1, k * src_fps / dst_fps)
        i = min(int(math.floor(x)), len(frames) - 2)
        u = x - i
        (t0, q0), (t1, q1) = frames[i], frames[i + 1]
        if q_dot(q0, q1) < 0:
            q1 = tuple(-v for v in q1)
        out.append((_lerp3(t0, t1, u), q_slerp(q_norm(q0), q_norm(q1), u)))
    return out


# ----------------------------------------------------------------------------------------------- .af header
# Offsets measured on vanilla clips (docs/actors/starfield-actor-anim-format.md). Only the two root-motion fields are written.
HDR_ROOT_ROTATION = 0x08     # 4 x f32: w, x, y, z of the Root offset at the last frame
HDR_ROOT_TRANSLATION = 0x18  # 3 x f32: x, y, z (m) of the Root offset at the last frame
HDR_VERSION = 0x28           # u16, 5 in every vanilla clip
HDR_BONES = 0x2a             # u16, rig bone count for a full clip (CALUMI: the count given to CreateAnimationC)
HDR_FRAMES = 0x2c            # u16, frame count
HDR_KIND = 0x2e              # u16, 2 = full clip (75 % of vanilla; the only kind CALUMI writes); 4..16 other layouts
AF_VERSION, AF_KIND_FULL = 5, 2


def read_af_header(raw):
    if len(raw) < 0x30:
        raise ActorAnimError("not an .af: shorter than its header")
    w, x, y, z = struct.unpack_from("<4f", raw, HDR_ROOT_ROTATION)
    version, bones, frames, kind = struct.unpack_from("<4H", raw, HDR_VERSION)
    return {"version": version, "bones": bones, "frames": frames, "kind": kind,
            "root_rotation": (x, y, z, w), "root_translation": struct.unpack_from("<3f", raw, HDR_ROOT_TRANSLATION)}


def root_motion(blocks, frame_count):
    """(translation, rotation_xyzw) of the Root block (rig index 0) at the last frame: what vanilla headers carry."""
    root = [b for b in blocks if b["index"] == 0]
    if not root:
        return (0.0, 0.0, 0.0), IDENTITY
    t, q = sample_block(root[0], frame_count - 1)
    return t, _canonical_identity(q_norm(q))


def patch_root_motion(raw, translation, rotation):
    """The .af bytes with the header's root-motion fields set. Refuses a file that is not a version 5 full clip."""
    h = read_af_header(raw)
    if h["version"] != AF_VERSION or h["kind"] != AF_KIND_FULL:
        raise ActorAnimError(f"header version {h['version']} kind {h['kind']}: only version 5 full clips are patched")
    x, y, z, w = q_norm(rotation)
    out = bytearray(raw)
    struct.pack_into("<4f", out, HDR_ROOT_ROTATION, w, x, y, z)
    struct.pack_into("<3f", out, HDR_ROOT_TRANSLATION, *(float(v) for v in translation))
    return bytes(out)


# ----------------------------------------------------------------------------------------------- .afx
def afx(tag, filename=None, is_state=1, events=(), audio=()):
    """The .afx sidecar in the vanilla element order (Mini Bot walkforward.afx: is_state, tag, filename, events, audios).
    events: [(frame, name, payload)] e.g. (15, 'SyncLeftFoot', ''); audio: [(frame, foley)]. Built on
    anim_object.descriptor, which writes is_state / tag / filename / audios; the events element is inserted before audios."""
    root = ET.fromstring(anim_object.descriptor(tag, filename, is_state, audio))
    if events:
        ev = ET.Element("events")
        for frame, name, *payload in events:
            e = ET.SubElement(ev, "event")
            ET.SubElement(e, "frame").text = str(int(frame))
            ET.SubElement(e, "name").text = str(name)
            ET.SubElement(e, "payload").text = str(payload[0]) if payload and payload[0] else ""
        at = [i for i, child in enumerate(root) if child.tag == "audios"]
        root.insert(at[0] if at else len(root), ev)
    for p in root.iter("payload"):
        if p.text is None:
            p.text = ""
    return ET.tostring(root, encoding="utf-8")


def parse_afx(raw):
    """{tag, filename, is_state, events: [(frame, name, payload)], audio: [(frame, foley)]} of an .afx."""
    root = ET.fromstring(raw)
    return {"tag": root.findtext("tag"), "filename": root.findtext("filename"), "is_state": int(root.findtext("is_state") or 0),
            "events": [(int(e.findtext("frame")), e.findtext("name"), e.findtext("payload") or "") for e in root.iter("event")],
            "audio": [(int(a.findtext("frame")), a.findtext("foley")) for a in root.iter("audio")]}


# ----------------------------------------------------------------------------------------------- the library
def find_dll(path=None):
    """The CALUMI library path: the argument, else FO4SF_CALUMI_DLL, else the research copy; None when absent."""
    for p in (path, os.environ.get("FO4SF_CALUMI_DLL"), DEFAULT_DLL):
        if p and os.path.isfile(p):
            return str(pathlib.Path(p).resolve())
    return None


def _outside_repo(path):
    path = pathlib.Path(path).resolve()
    repo = pathlib.Path(__file__).resolve().parents[2]
    if path == repo or repo in path.parents:
        raise ActorAnimError(f"{path}: converted animation files stay outside the repository")
    return path


class Calumi:
    """ctypes bindings to CALUMI.Animation.dll (the calls native_door.export and make_anim_console.CalumiReader use)."""

    def __init__(self, dll=None):
        path = find_dll(dll)
        if path is None:
            raise ActorAnimError("CALUMI.Animation.dll not found (pass its path or set FO4SF_CALUMI_DLL)")
        self.path = path
        self.lib = c.CDLL(path)
        self._fns = {}

    def f(self, name, args, res):
        fn = self._fns.get(name)
        if fn is None:
            fn = getattr(self.lib, name)
            fn.argtypes, fn.restype = args, res
            self._fns[name] = fn
        return fn

    def _err(self):
        return self.f("CreateStringContainerC", [], c.c_void_p)()

    def _free_err(self, err):
        self.f("DeleteStringContainerC", [c.c_void_p], None)(err)

    def _require(self, ok, err, what):
        if not ok:
            m = self.f("GetStringFromContainerC", [c.c_void_p], c.c_char_p)(err)
            raise RuntimeError(f"CALUMI {what} failed: {(m or b'').decode(errors='replace')}")
        return ok

    # ---- rig
    def _make_rig(self, bones, name, precision, err):
        p, b = c.c_void_p, c.c_bool
        rig = self.f("CreateSkeletonRigC", [c.c_char_p], p)(name.encode("ascii"))
        self._require(rig, err, "CreateSkeletonRigC")
        try:
            self._require(self.f("SFBGSRigPackage_AddPackageToSkeletonRigC", [p, p, b], b)(rig, err, True), err, "rig package")
            setp = {"default": "SFBGSRigPackage_SetPrecisionToDefaultC", "first_person": "SFBGSRigPackage_SetPrecisionToFirstPersonC",
                    "ship": "SFBGSRigPackage_SetPrecisionToShipValuesC"}[precision]
            self.f(setp, [p], None)(rig)
            add = self.f("AddBoneToSkeletonRigC", [p] + [c.c_float] * 7 + [c.c_char_p, c.c_int, b, p], b)
            for bone in bones:
                x, y, z, w = bone["rotation"]
                self._require(add(rig, x, y, z, w, *bone["translation"], bone["name"].encode("ascii"), bone["parent"], True, err),
                              err, f"AddBoneToSkeletonRigC {bone['name']}")
            get = self.f("GetSkeletonBoneC", [p, c.c_int, p], p)
            for i, bone in enumerate(bones):
                if bone["mirror"] >= 0:
                    self.f("SetMirrorIndexC", [p, c.c_int], c.c_int)(get(rig, i, err), bone["mirror"])
                if bone["key"] is not None:
                    self._require(self.f("SFBGSRigPackage_AddBoneNameToMapC", [p, c.c_uint8, c.c_char_p, p, b], b)(
                        rig, bone["key"], bone["name"].encode("ascii"), err, True), err, f"map key {bone['key']} {bone['name']}")
            return rig
        except BaseException:
            self.f("DeleteSkeletonRigC", [p], b)(rig)
            raise

    def write_rig(self, bones, path, name="FO4Port_ActorRig", precision="default"):
        if precision not in PRECISIONS:
            raise ActorAnimError(f"precision {precision!r} not one of {PRECISIONS}")
        bones = validate_bones(bones)
        path = _outside_repo(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        err = self._err()
        try:
            rig = self._make_rig(bones, name, precision, err)
            try:
                self._require(self.f("SaveSkeletonRigToSFBGSFormatDirectC", [c.c_void_p, c.c_wchar_p, c.c_void_p], c.c_bool)(
                    rig, str(path), err), err, "SaveSkeletonRigToSFBGSFormatDirectC")
            finally:
                self.f("DeleteSkeletonRigC", [c.c_void_p], c.c_bool)(rig)
        finally:
            self._free_err(err)
        return path

    def _rig_info(self, rig, err):
        p = c.c_void_p
        bones = []
        for i in range(self.f("GetSkeletonRigBoneCountC", [p], c.c_size_t)(rig)):
            bone = self.f("GetSkeletonBoneC", [p, c.c_int, p], p)(rig, i, err)
            name = self.f("GetSkeletonBoneNameC", [p], c.c_char_p)(bone).decode("latin-1")
            q = self.f("GetSkeletonBoneRotationC", [p, c.c_bool], p)(bone, False)
            t = self.f("GetSkeletonBonePositionC", [p, c.c_bool], p)(bone, False)
            mapped = self.f("SFBGSRigPackage_BoneIsMappedC", [p, c.c_char_p], c.c_bool)(rig, name.encode("latin-1"))
            bones.append({"name": name, "parent": self.f("GetSkeletonBoneParentIndexC", [p], c.c_int)(bone),
                          "translation": tuple(self.f("GetVector3" + a, [p], c.c_float)(t) for a in "XYZ"),
                          "rotation": tuple(self.f("GetQuaternion" + a, [p], c.c_float)(q) for a in "XYZW"),
                          "scale": 1.0, "mirror": self.f("GetMirrorIndexC", [p], c.c_int)(bone),
                          "type": self.f("GetBoneTypeC", [p], c.c_uint32)(bone),
                          "key": self.f("SFBGSRigPackage_GetBoneKeyC", [p, c.c_char_p], c.c_uint8)(rig, name.encode("latin-1")) if mapped else None})
        return {"bones": bones, "precision": PRECISIONS[self.f("SFBGSRigPackage_GetPrecisionTypeC", [p], c.c_uint8)(rig)]
                if self.f("SFBGSRigPackage_GetPrecisionTypeC", [p], c.c_uint8)(rig) < len(PRECISIONS) else "custom",
                "high_precision": self.f("SFBGSRigPackage_GetHighPrecisionValueC", [p], c.c_float)(rig),
                "low_precision": self.f("SFBGSRigPackage_GetLowPrecisionValueC", [p], c.c_float)(rig)}

    def read_rig(self, path):
        err = self._err()
        try:
            rig = self.f("LoadSFBGSSkeletonRigFromFileC", [c.c_wchar_p, c.c_void_p], c.c_void_p)(str(path), err)
            self._require(rig, err, f"LoadSFBGSSkeletonRigFromFileC {path}")
            try:
                return self._rig_info(rig, err)
            finally:
                self.f("DeleteSkeletonRigC", [c.c_void_p], c.c_bool)(rig)
        finally:
            self._free_err(err)

    # ---- clips
    def write_clip(self, bones, blocks, frame_count, path, name=None, precision="default", rig_name="FO4Port_ActorRig",
                   header_root_motion=True):
        """Write one .af for the rig `bones` (the list write_rig wrote; the file is quantised against that rig's precision).
        blocks: build_blocks output (offsets from the bind). frame_count: the clip's length in frames at 30 fps; the
        file's frame count is the last key + 1, so a hold key (the last value repeated at frame_count - 1) is added to
        the first block whose keys end earlier, and a clip with no block at all gets an identity Root rotation pair
        (frames 0 and frame_count - 1). header_root_motion: put the Root offset at the last frame into the header as
        vanilla clips have it (patch_root_motion). Returns the path."""
        bones = validate_bones(bones)
        if precision not in PRECISIONS:
            raise ActorAnimError(f"precision {precision!r} not one of {PRECISIONS}")
        path = _outside_repo(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        motion = root_motion(blocks, frame_count)
        blocks = pad_to_length(blocks, frame_count, bones)
        p, b = c.c_void_p, c.c_bool
        err = self._err()
        try:
            rig = self._make_rig(bones, rig_name, precision, err)
            try:
                anim = self.f("CreateAnimationC", [c.c_char_p, c.c_uint], p)((name or path.stem).encode("ascii"), len(bones))
                self._require(anim, err, "CreateAnimationC")
                try:
                    for blk in blocks:
                        if bones[blk["index"]]["name"] != blk["bone"]:
                            raise ActorAnimError(f"block {blk['bone']} filed under rig index {blk['index']}")
                        h = self.f("CreateAnimBlockC", [c.c_char_p, c.c_int, p], p)(blk["bone"].encode("ascii"), blk["index"], err)
                        self._require(h, err, f"CreateAnimBlockC {blk['bone']}")
                        try:
                            for frame, (x, y, z, w) in blk.get("rot", []):
                                e = self.f("CreateRotationEntryC", [c.c_uint16] + [c.c_float] * 4, p)(frame, x, y, z, w)
                                try:
                                    self._require(self.f("AddRotationSqToAnimBlockC", [p, p, c.c_uint, b], b)(h, e, 1, True), err, "rotation key")
                                finally:
                                    self.f("DeleteRotationEntryC", [p], b)(e)
                            for frame, (x, y, z) in blk.get("trans", []):
                                e = self.f("CreateTranslationEntryC", [c.c_uint16] + [c.c_double] * 3, p)(frame, x, y, z)
                                try:
                                    self._require(self.f("AddTranslationSqToAnimBlockC", [p, p, c.c_uint, b], b)(h, e, 1, True), err, "translation key")
                                finally:
                                    self.f("DeleteTranslationEntryC", [p], b)(e)
                            self._require(self.f("AddAnimBlockToAnimationC", [p, p, b, p], b)(anim, h, True, err), err, "AddAnimBlockToAnimationC")
                            h = None
                        finally:
                            if h:
                                self.f("DeleteAnimationBlockC", [p], b)(h)
                    self._require(self.f("SaveAnimationToSFBGSFormatDirectC", [p, c.c_wchar_p, p, p], b)(anim, str(path), rig, err),
                                  err, "SaveAnimationToSFBGSFormatDirectC")
                finally:
                    self.f("DeleteAnimationC", [p], b)(anim)
            finally:
                self.f("DeleteSkeletonRigC", [p], b)(rig)
        finally:
            self._free_err(err)
        raw = path.read_bytes()
        h = read_af_header(raw)
        if h["frames"] != frame_count:
            raise ActorAnimError(f"{path}: the library wrote {h['frames']} frames for {frame_count}")
        if header_root_motion:
            path.write_bytes(patch_root_motion(raw, *motion))
        return path

    def read_clip(self, rig_path, af_path):
        """{name, frame_count, rig, blocks: [{bone, index, rot: [(frame, xyzw)], trans: [(frame, xyz)], scale: [(frame, s)]}]}."""
        p = c.c_void_p
        err = self._err()
        try:
            scene = self.f("LoadAnimationSceneFromSFBGSFormatC", [c.POINTER(c.c_wchar_p), c.c_int, p], p)(
                (c.c_wchar_p * 2)(str(rig_path), str(af_path)), 2, err)
            self._require(scene, err, f"LoadAnimationSceneFromSFBGSFormatC {af_path}")
            try:
                rig = self._rig_info(self.f("GetSkeletonRigC", [p], p)(scene), err)
                anim = self.f("GetAnimationC", [p, c.c_int, p], p)(scene, 0, err)
                self._require(anim, err, "GetAnimationC")
                blocks = []
                for k in range(self.f("GetAnimationBlockCountC", [p], c.c_size_t)(anim)):
                    h = self.f("GetAnimationBlockC", [p, c.c_int, p], p)(anim, k, err)
                    rot, trans, scale = [], [], []
                    for j in range(self.f("GetRotationSqSizeC", [p], c.c_size_t)(h)):
                        e = self.f("GetRotationFromSqC", [p, c.c_int, p], p)(h, j, err)
                        q = self.f("GetValueFromRotationEntryC", [p], p)(e)
                        rot.append((self.f("GetFrameFromRotationEntryC", [p], c.c_uint16)(e),
                                    tuple(self.f("GetQuaternion" + a, [p], c.c_float)(q) for a in "XYZW")))
                    for j in range(self.f("GetTranslationSqSizeC", [p], c.c_size_t)(h)):
                        e = self.f("GetTranslationFromSqC", [p, c.c_int, p], p)(h, j, err)
                        v = self.f("GetValueFromTranslationEntryC", [p], p)(e)
                        trans.append((self.f("GetFrameFromTranslationEntryC", [p], c.c_uint16)(e),
                                      tuple(self.f("GetVector3D" + a, [p], c.c_double)(v) for a in "XYZ")))
                    for j in range(self.f("GetScalarSqSizeC", [p], c.c_size_t)(h)):
                        e = self.f("GetScalarFromSqC", [p, c.c_int, p], p)(h, j, err)
                        scale.append((self.f("GetFrameFromScalarEntryC", [p], c.c_uint16)(e),
                                      self.f("GetValueFromScalarEntryC", [p], c.c_float)(e)))
                    blocks.append({"bone": self.f("GetAnimBlockBoneNameC", [p], c.c_char_p)(h).decode("latin-1"),
                                   "index": self.f("GetAnimBlockBoneIndexC", [p], c.c_int)(h),
                                   "rot": rot, "trans": trans, "scale": scale})
                return {"name": self.f("GetAnimationTitleC", [p], c.c_char_p)(anim).decode("latin-1"),
                        "frame_count": self.f("GetFrameCountC", [p], c.c_size_t)(anim), "rig": rig, "blocks": blocks}
            finally:
                self.f("DeleteAnimationSceneC", [p], c.c_bool)(scene)
        finally:
            self._free_err(err)


def write_clip_files(cal, bones, poses, frame_count, folder, tag, keys_are="local", is_state=1, events=(), audio=(),
                     precision="default", keep=(), stem=None):
    """One clip as vanilla lays it out: <folder>/<stem lower case>.af and .afx, the .afx naming <stem>.af (the Mini Bot's
    walkforward.afx names WalkForward.af). stem defaults to the tag; vanilla shares one tag between variants
    (knockdown_backward.afx and knockdown_forward.afx both carry tag Knockdown). poses as build_blocks takes them.
    Returns {'af': path, 'afx': path, 'blocks': n}."""
    stem = stem or tag
    for name in (tag, stem):
        if not name or any(ch in name for ch in '\\/:*?"<>|.') or not name.isascii():
            raise ActorAnimError(f"clip name {name!r} is not a bare ASCII name")
    for frame, *_rest in list(events) + list(audio):
        if not 0 <= int(frame) < frame_count:
            raise ActorAnimError(f"{tag}: event frame {frame} outside 0..{frame_count - 1}")
    blocks = build_blocks(bones, poses, frame_count, keys_are=keys_are, keep=keep)
    folder = _outside_repo(folder)
    af = cal.write_clip(bones, blocks, frame_count, folder / (stem.lower() + ".af"), name=stem.lower(), precision=precision)
    sidecar = folder / (stem.lower() + ".afx")
    sidecar.write_bytes(afx(tag, stem + ".af", is_state, events, audio))
    return {"af": af, "afx": sidecar, "blocks": len(blocks)}


def pad_to_length(blocks, frame_count, bones):
    """blocks with a hold key so that the last key falls on frame_count - 1 (CALUMI derives the file's frame count from
    the last key; vanilla idle.af stores 41 frames with no block at all, which CALUMI cannot express)."""
    last = frame_count - 1
    if any(blk.get("rot") and blk["rot"][-1][0] > last or blk.get("trans") and blk["trans"][-1][0] > last for blk in blocks):
        raise ActorAnimError(f"a key lies after frame {last}")
    if last <= 0:
        return [dict(blk) for blk in blocks]
    ends = [max([f for f, _ in blk.get("rot", [])] + [f for f, _ in blk.get("trans", [])] + [-1]) for blk in blocks]
    out = [dict(blk) for blk in blocks]
    if ends and max(ends) >= last:
        return out
    if out:
        blk = out[0]
        ch = "rot" if blk.get("rot") else "trans"
        blk[ch] = list(blk[ch]) + [(last, blk[ch][-1][1])]
        return out
    return [{"bone": bones[0]["name"], "index": 0, "rot": [(0, IDENTITY), (last, IDENTITY)], "trans": []}]


# ----------------------------------------------------------------------------------------------- comparison
def compare_rigs(a, b):
    """Largest differences between two bone lists (same names in the same order): translation (m), rotation (rad)."""
    if [x["name"] for x in a] != [x["name"] for x in b] or [x["parent"] for x in a] != [x["parent"] for x in b]:
        raise ActorAnimError("rigs differ in bone names or parents")
    rows = [{"bone": x["name"], "translation": max(abs(u - v) for u, v in zip(x["translation"], y["translation"])),
             "rotation": q_angle(x["rotation"], y["rotation"])} for x, y in zip(a, b)]
    return {"bones": rows, "max_translation": max(r["translation"] for r in rows), "max_rotation": max(r["rotation"] for r in rows)}


def compare_clips(bones, a_blocks, b_blocks, frame_count):
    """Per bone and per frame, the largest difference of the parent-local pose between two clips of one rig (a bone
    without a block holds its bind). Returns {per_bone: {bone: {translation, rotation, frame}}, per_frame: [{translation,
    rotation, bone}], max_translation (m), max_rotation (rad), max_quat_component}."""
    a_idx = {blk["bone"]: blk for blk in a_blocks}
    b_idx = {blk["bone"]: blk for blk in b_blocks}
    per_bone, per_frame = {}, [{"translation": 0.0, "rotation": 0.0, "quat": 0.0, "bone": None} for _ in range(frame_count)]
    empty = {"rot": [], "trans": []}
    for bone in bones:
        n = bone["name"]
        if n not in a_idx and n not in b_idx:
            continue
        worst = {"translation": 0.0, "rotation": 0.0, "quat": 0.0, "frame": 0}
        for f in range(frame_count):
            ta, qa = offset_to_local(bone["translation"], bone["rotation"], *sample_block(a_idx.get(n, empty), f))
            tb, qb = offset_to_local(bone["translation"], bone["rotation"], *sample_block(b_idx.get(n, empty), f))
            dt = max(abs(u - v) for u, v in zip(ta, tb))
            dr = q_angle(qa, qb)
            dq = min(max(abs(u - v) for u, v in zip(qa, qb)), max(abs(u + v) for u, v in zip(qa, qb)))
            if dt > worst["translation"] or dr > worst["rotation"]:
                worst["frame"] = f
            worst["translation"], worst["rotation"], worst["quat"] = max(worst["translation"], dt), max(worst["rotation"], dr), max(worst["quat"], dq)
            pf = per_frame[f]
            if dt > pf["translation"] or dr > pf["rotation"]:
                pf["bone"] = n
            pf["translation"], pf["rotation"], pf["quat"] = max(pf["translation"], dt), max(pf["rotation"], dr), max(pf["quat"], dq)
        per_bone[n] = worst
    return {"per_bone": per_bone, "per_frame": per_frame,
            "max_translation": max([v["translation"] for v in per_bone.values()] + [0.0]),
            "max_rotation": max([v["rotation"] for v in per_bone.values()] + [0.0]),
            "max_quat_component": max([v["quat"] for v in per_bone.values()] + [0.0])}
