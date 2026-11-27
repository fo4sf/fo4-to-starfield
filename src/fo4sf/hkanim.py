"""Fallout 4 Havok animation reader (hk_2014.1.0-r1, 64-bit little-endian packfiles).

Reads, from a standalone .hkx packfile (or any blob `hkpackfile.Packfile` accepts):
  hkaSkeleton                     bone names, parent indices, lock-translation flags, reference pose (t, q, s)
  hkaAnimationBinding             transformTrackToBoneIndices, floatTrackToFloatSlotIndices, blend hint
  hkaSplineCompressedAnimation    decoded to per-frame local transforms per track
  hkaDefaultAnimatedReferenceFrame  extracted (root) motion samples
  hkaAnnotationTrack              per-track annotation events (time, text)

Object layouts (64-bit, hk 2014) are measured from the Fallout 4 files, not reflected from class data:
  hkReferencedObject  16 bytes (vtable 8, size/flags 2, refcount 2, pad 4)
  hkaSkeleton         +16 name*  +24 parentIndices[]  +40 bones[]  +56 referencePose[]  +72 referenceFloats[]
                      +88 floatSlots[]  +104 localFrames[]  +120 partitions[]
  hkaBone             16 bytes: name*, lockTranslation(u8)
  hkQsTransform       48 bytes: translation xyzw, rotation xyzw, scale xyzw
  hkaAnimation        +16 type(i32) +20 duration(f32) +24 numTransformTracks +28 numFloatTracks
                      +32 extractedMotion*  +40 annotationTracks[]
  hkaSplineCompressedAnimation (after hkaAnimation)
                      +56 numFrames +60 numBlocks +64 maxFramesPerBlock +68 maskAndQuantizationSize
                      +72 blockDuration +76 blockInverseDuration +80 frameDuration
                      +88 blockOffsets[u32] +104 floatBlockOffsets[u32] +120 transformOffsets[f32]
                      +136 floatOffsets[f32] +152 data[u8] +168 endian(i32)
  hkaAnimationBinding +16 originalSkeletonName* +24 animation* +32 transformTrackToBoneIndices[i16]
                      +48 floatTrackToFloatSlotIndices[i16] +64 partitionIndices[i16] +80 blendHint(i8)
  hkaDefaultAnimatedReferenceFrame  +16 frameType(i8) +32 up xyzw +48 forward xyzw +64 duration
                      +72 referenceFrameSamples[vec4]
  hkaAnnotationTrack  24 bytes: trackName*, annotations[] ; hkaAnnotation 16 bytes: time(f32), pad, text*

Spline block stream (public format knowledge, checked here by measurement: every block must end exactly at the next
block's float-section offset, every dequantized quaternion must be unit length):
  per block: one 4-byte mask per transform track (quantization byte, position flags, rotation flags, scale flags),
  then per track: position, rotation, scale, each 4-byte aligned at its end.
    quantization byte: bits 0-1 position (0 = 8-bit, 1 = 16-bit), bits 2-5 rotation format, bits 6-7 scale
    vector flags: bit i (i = x, y, z) static component, bit 4 + i spline component
    rotation flags: any of 0xF0 spline, else any of 0x0F static, else identity
  vector spline: numItems u16, degree u8, knots u8[numItems + degree + 2], align 4, per axis: spline -> min, max f32;
    static -> value f32; then numItems + 1 control points of the spline axes (8/16-bit fractions of min..max), align 4
  vector without spline: static axes as f32, other axes default (0 for translation, 1 for scale)
  rotation spline: numItems u16, degree u8, knots, align to the format, numItems + 1 packed quaternions
  rotation static: align to the format, one packed quaternion
  knots and evaluation parameter are local frame indices; blocks share their boundary frame (maxFramesPerBlock - 1
  intervals per block). Quaternion splines blend components linearly and are then normalized.
"""
import math
import struct
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .hkpackfile import Packfile, PackfileError

Transform = Tuple[Tuple[float, float, float], Tuple[float, float, float, float], Tuple[float, float, float]]

ROTATION_FORMATS = {0: "POLAR32", 1: "THREECOMP40", 2: "THREECOMP48", 3: "THREECOMP24", 4: "STRAIGHT16",
                    5: "UNCOMPRESSED"}
ROTATION_SIZE = {0: 4, 1: 5, 2: 6, 3: 3, 4: 2, 5: 16}
ROTATION_ALIGN = {0: 4, 1: 1, 2: 2, 3: 1, 4: 2, 5: 4}
VECTOR_FORMATS = {0: "BITS8", 1: "BITS16"}
BLEND_HINTS = {0: "NORMAL", 1: "ADDITIVE_DEPRECATED", 2: "ADDITIVE"}
ANIMATION_TYPES = {0: "UNKNOWN", 1: "INTERLEAVED", 2: "MIRRORED", 3: "SPLINE_COMPRESSED", 4: "QUANTIZED",
                   5: "PREDICTIVE", 6: "REFERENCE_POSE"}


class HkAnimError(PackfileError):
    pass


# --------------------------------------------------------------------------------------------------------------------
# packfile helpers
# --------------------------------------------------------------------------------------------------------------------
def _string(p: Packfile, ptr_off: int) -> Optional[str]:
    tgt = p.pointer(ptr_off)
    if tgt is None:
        return None
    d = p.data
    a = p.data_section.start + tgt
    return d[a:d.index(b"\0", a)].decode("latin-1")


def _array(p: Packfile, off: int, fmt: str, size: int) -> list:
    at, n = p.array(off)
    if n == 0:
        return []
    if at is None:
        raise HkAnimError(f"array at 0x{off:x} has {n} items and no data pointer")
    return [p.unpack(fmt, at + i * size) for i in range(n)]


def _bytes(p: Packfile, off: int) -> bytes:
    at, n = p.array(off)
    return b"" if n == 0 else p.raw(at, n)


# --------------------------------------------------------------------------------------------------------------------
# data classes
# --------------------------------------------------------------------------------------------------------------------
@dataclass
class Skeleton:
    name: str
    bones: List[str]
    parents: List[int]
    lock_translation: List[bool]
    reference_pose: List[Transform]
    float_slots: List[str] = field(default_factory=list)
    reference_floats: List[float] = field(default_factory=list)

    def index(self, name: str) -> int:
        return self.bones.index(name)


@dataclass
class Binding:
    original_skeleton_name: Optional[str]
    transform_track_to_bone: List[int]
    float_track_to_slot: List[int]
    partition_indices: List[int]
    blend_hint: int

    @property
    def blend_hint_name(self) -> str:
        return BLEND_HINTS.get(self.blend_hint, str(self.blend_hint))


@dataclass
class ReferenceFrame:
    frame_type: int
    up: Tuple[float, float, float, float]
    forward: Tuple[float, float, float, float]
    duration: float
    samples: List[Tuple[float, float, float, float]]


@dataclass
class Animation:
    type: int
    duration: float
    num_frames: int
    frame_duration: float
    num_transform_tracks: int
    num_float_tracks: int
    # tracks[t][f] = ((tx, ty, tz), (qx, qy, qz, qw), (sx, sy, sz)) local transform of track t at frame f
    tracks: List[List[Transform]]
    float_tracks: List[List[float]] = field(default_factory=list)
    annotations: List[Tuple[str, List[Tuple[float, str]]]] = field(default_factory=list)
    reference_frame: Optional[ReferenceFrame] = None
    # measurement record: forms seen, raw quaternion norms, structure checks
    stats: Dict = field(default_factory=dict)

    @property
    def fps(self) -> float:
        return 1.0 / self.frame_duration if self.frame_duration else 0.0

    def frame(self, f: int) -> List[Transform]:
        return [tr[f] for tr in self.tracks]


@dataclass
class HkxFile:
    skeletons: List[Skeleton]
    animations: List[Animation]
    bindings: List[Binding]
    classes: Counter


# --------------------------------------------------------------------------------------------------------------------
# object readers
# --------------------------------------------------------------------------------------------------------------------
def read_skeleton(p: Packfile, o: int) -> Skeleton:
    name = _string(p, o + 16) or ""
    parents = [v[0] for v in _array(p, o + 24, "<h", 2)]
    at, n = p.array(o + 40)
    bones, lock = [], []
    for i in range(n):
        bones.append(_string(p, at + 16 * i) or "")
        lock.append(bool(p.unpack("<B", at + 16 * i + 8)[0]))
    pose = []
    for v in _array(p, o + 56, "<12f", 48):
        pose.append((tuple(v[0:3]), tuple(v[4:8]), tuple(v[8:11])))
    floats = [v[0] for v in _array(p, o + 72, "<f", 4)]
    at, nf = p.array(o + 88)
    slots = [_string(p, at + 8 * i) or "" for i in range(nf)]
    if not (len(parents) == len(bones) == len(pose)):
        raise HkAnimError(f"skeleton {name}: {len(bones)} bones, {len(parents)} parents, {len(pose)} poses")
    for i, par in enumerate(parents):
        if par >= i or par < -1:
            raise HkAnimError(f"skeleton {name}: bone {i} parent {par} not before it")
    return Skeleton(name, bones, parents, lock, pose, slots, floats)


def read_binding(p: Packfile, o: int) -> Binding:
    return Binding(_string(p, o + 16),
                   [v[0] for v in _array(p, o + 32, "<h", 2)],
                   [v[0] for v in _array(p, o + 48, "<h", 2)],
                   [v[0] for v in _array(p, o + 64, "<h", 2)],
                   p.unpack("<b", o + 80)[0])


def read_reference_frame(p: Packfile, o: int) -> ReferenceFrame:
    return ReferenceFrame(p.unpack("<b", o + 16)[0], p.unpack("<4f", o + 32), p.unpack("<4f", o + 48),
                          p.unpack("<f", o + 64)[0], [tuple(v) for v in _array(p, o + 72, "<4f", 16)])


def read_annotations(p: Packfile, o: int) -> List[Tuple[str, List[Tuple[float, str]]]]:
    at, n = p.array(o + 40)
    out = []
    for i in range(n):
        t = at + 24 * i
        aat, an = p.array(t + 8)
        out.append((_string(p, t) or "", [(p.unpack("<f", aat + 16 * k)[0], _string(p, aat + 16 * k + 8) or "")
                                          for k in range(an)]))
    return out


# --------------------------------------------------------------------------------------------------------------------
# quantized values
# --------------------------------------------------------------------------------------------------------------------
_SQRT_HALF = math.sqrt(0.5)


# Dequantization checks for the "smallest three" formats: the dropped component is by construction the largest in
# magnitude, and the kept three must not exceed unit length. Counted per decode, reported in Animation.stats.
QUAT_CHECKS = Counter()


def _insert_w(three: Sequence[float], shift: int, negative: bool) -> Tuple[float, float, float, float]:
    s = 1.0 - (three[0] * three[0] + three[1] * three[1] + three[2] * three[2])
    if s < -1e-6:
        QUAT_CHECKS["kept_three_over_unit"] += 1
    w = math.sqrt(s) if s > 0.0 else 0.0
    if abs(w) + 1e-3 < max(abs(c) for c in three):
        QUAT_CHECKS["dropped_not_largest"] += 1
    if negative:
        w = -w
    q = list(three)
    q.insert(shift, w)
    return tuple(q)


def unpack_quaternion(fmt: int, b: bytes) -> Tuple[float, float, float, float]:
    """Dequantize one packed quaternion (xyzw). Only the formats measured in Fallout 4 files are decoded; others
    raise (their sizes are still known, so a stream containing them can be walked)."""
    if fmt == 1:                                       # THREECOMP40: 3 x 12 bits, 2-bit dropped index, 1 sign bit
        v = int.from_bytes(b[:5], "little")
        f = _SQRT_HALF / 2047.0
        three = [(((v >> (12 * i)) & 0xFFF) - 2047) * f for i in range(3)]
        return _insert_w(three, (v >> 36) & 3, bool((v >> 38) & 1))
    if fmt == 2:                                       # THREECOMP48: 3 x 15 bits; index bits and sign in the tops
        x, y, z = struct.unpack_from("<3H", b)
        f = _SQRT_HALF / 16383.0
        three = [((c & 0x7FFF) - 16383) * f for c in (x, y, z)]
        shift = ((y >> 14) & 2) | ((x >> 15) & 1)
        return _insert_w(three, shift, bool(z >> 15))
    if fmt == 5:                                       # UNCOMPRESSED
        return struct.unpack_from("<4f", b)
    raise HkAnimError(f"rotation format {ROTATION_FORMATS.get(fmt, fmt)} is not decoded (not measured in FO4 data)")


# --------------------------------------------------------------------------------------------------------------------
# B-spline
# --------------------------------------------------------------------------------------------------------------------
def find_span(n: int, p: int, u: float, knots: Sequence[int]) -> int:
    """Knot span index (NURBS-book convention): knots[span] <= u < knots[span + 1], span in [p, n]; n = last CP."""
    if u >= knots[n + 1]:
        return n
    if u <= knots[p]:
        return p
    lo, hi = p, n + 1
    mid = (lo + hi) // 2
    while u < knots[mid] or u >= knots[mid + 1]:
        if u < knots[mid]:
            hi = mid
        else:
            lo = mid
        mid = (lo + hi) // 2
    return mid


def basis(span: int, u: float, p: int, knots: Sequence[int]) -> List[float]:
    """Non-zero B-spline basis functions N[span-p .. span] at u (Cox-de Boor triangle)."""
    N = [1.0] + [0.0] * p
    left = [0.0] * (p + 1)
    right = [0.0] * (p + 1)
    for j in range(1, p + 1):
        left[j] = u - knots[span + 1 - j]
        right[j] = knots[span + j] - u
        saved = 0.0
        for r in range(j):
            den = right[r + 1] + left[j - r]
            tmp = N[r] / den if den else 0.0
            N[r] = saved + right[r + 1] * tmp
            saved = left[j - r] * tmp
        N[j] = saved
    return N


def evaluate(u: float, degree: int, knots: Sequence[int], cps: Sequence[Sequence[float]]) -> List[float]:
    n = len(cps) - 1
    if n == 0:
        return list(cps[0])
    span = find_span(n, degree, u, knots)
    N = basis(span, u, degree, knots)
    dim = len(cps[0])
    out = [0.0] * dim
    for k in range(degree + 1):
        c = cps[span - degree + k]
        w = N[k]
        for d in range(dim):
            out[d] += w * c[d]
    return out


# --------------------------------------------------------------------------------------------------------------------
# spline-compressed stream
# --------------------------------------------------------------------------------------------------------------------
class _Reader:
    def __init__(self, data: bytes, pos: int):
        self.d = data
        self.pos = pos

    def align(self, a: int):
        if a > 1:
            self.pos = (self.pos + a - 1) // a * a

    def take(self, n: int) -> bytes:
        if self.pos + n > len(self.d):
            raise HkAnimError(f"spline stream overrun at {self.pos} (+{n}) of {len(self.d)}")
        b = self.d[self.pos:self.pos + n]
        self.pos += n
        return b

    def u8(self) -> int:
        return self.take(1)[0]

    def u16(self) -> int:
        return struct.unpack("<H", self.take(2))[0]

    def f32(self) -> float:
        return struct.unpack("<f", self.take(4))[0]


@dataclass
class _Curve:
    """One decoded component group: either constant values or a B-spline over local frames."""
    const: Optional[Tuple[float, ...]] = None
    degree: int = 0
    knots: Tuple[int, ...] = ()
    cps: Optional[List[Tuple[float, ...]]] = None

    def at(self, u: float) -> List[float]:
        if self.cps is None:
            return list(self.const)
        return evaluate(u, self.degree, self.knots, self.cps)


def _spline_header(r: _Reader, stats: Counter, what: str):
    n_items = r.u16()
    degree = r.u8()
    knots = tuple(r.take(n_items + degree + 2))
    stats[f"{what}_spline_degree_{degree}"] += 1
    return n_items, degree, knots


def _read_vector(r: _Reader, qfmt: int, flags: int, default: float, stats: Counter, what: str) -> _Curve:
    spline_axes = [i for i in range(3) if flags & (0x10 << i)]
    if spline_axes:
        stats[f"{what}_{VECTOR_FORMATS.get(qfmt, qfmt)}_spline"] += 1
        if qfmt not in VECTOR_FORMATS:
            raise HkAnimError(f"{what} quantization {qfmt} unknown")
        n_items, degree, knots = _spline_header(r, stats, what)
        r.align(4)
        lo, hi, const = {}, {}, [default] * 3
        for i in range(3):
            if flags & (0x10 << i):
                lo[i], hi[i] = r.f32(), r.f32()
            elif flags & (1 << i):
                const[i] = r.f32()
        size, scale = (1, 255.0) if qfmt == 0 else (2, 65535.0)
        cps = []
        for _ in range(n_items + 1):
            cp = list(const)
            for i in spline_axes:
                b = r.take(size)
                q = b[0] if size == 1 else struct.unpack("<H", b)[0]
                cp[i] = lo[i] + (hi[i] - lo[i]) * (q / scale)
            cps.append(tuple(cp))
        r.align(4)
        return _Curve(degree=degree, knots=knots, cps=cps)
    const = [default] * 3
    if flags & 0x07:
        stats[f"{what}_static"] += 1
    else:
        stats[f"{what}_identity"] += 1
    for i in range(3):
        if flags & (1 << i):
            const[i] = r.f32()
    r.align(4)
    return _Curve(const=tuple(const))


def _read_rotation(r: _Reader, qfmt: int, flags: int, stats: Counter, norms: List[float]) -> _Curve:
    name = ROTATION_FORMATS.get(qfmt)
    if name is None:
        raise HkAnimError(f"rotation quantization {qfmt} unknown")
    size, al = ROTATION_SIZE[qfmt], ROTATION_ALIGN[qfmt]
    if flags & 0xF0:
        stats[f"rotation_{name}_spline"] += 1
        n_items, degree, knots = _spline_header(r, stats, "rotation")
        r.align(al)
        cps = [unpack_quaternion(qfmt, r.take(size)) for _ in range(n_items + 1)]
        r.align(4)
        for i, q in enumerate(cps):
            norms.append(math.sqrt(sum(c * c for c in q)))
            if i and sum(a * b for a, b in zip(q, cps[i - 1])) < 0.0:
                stats["rotation_cp_sign_flips"] += 1
        return _Curve(degree=degree, knots=knots, cps=cps)
    if flags & 0x0F:
        stats[f"rotation_{name}_static"] += 1
        r.align(al)
        q = unpack_quaternion(qfmt, r.take(size))
        r.align(4)
        norms.append(math.sqrt(sum(c * c for c in q)))
        return _Curve(const=q)
    stats["rotation_identity"] += 1
    r.align(4)
    return _Curve(const=(0.0, 0.0, 0.0, 1.0))


def _normalize(q: Sequence[float]) -> Tuple[float, float, float, float]:
    n = math.sqrt(sum(c * c for c in q))
    if not n or not math.isfinite(n):
        raise HkAnimError(f"degenerate quaternion {tuple(q)}")
    return tuple(c / n for c in q)


def decode_spline(p: Packfile, o: int) -> Animation:
    atype, duration, ntt, nft = p.unpack("<ifii", o + 16)
    num_frames, num_blocks, max_fpb, mq_size = p.unpack("<iiii", o + 56)
    block_dur, block_inv, frame_dur = p.unpack("<fff", o + 72)
    block_offsets = [v[0] for v in _array(p, o + 88, "<I", 4)]
    float_block_offsets = [v[0] for v in _array(p, o + 104, "<I", 4)]
    transform_offsets = _array(p, o + 120, "<f", 4)
    float_offsets = _array(p, o + 136, "<f", 4)
    data = _bytes(p, o + 152)
    endian, = p.unpack("<i", o + 168)
    if atype != 3:
        raise HkAnimError(f"animation type {atype} is not spline-compressed")
    if endian != 0:
        raise HkAnimError("big-endian spline data")
    if nft:
        raise HkAnimError(f"{nft} float tracks: float-track decoding not implemented (none measured in robot clips)")
    if transform_offsets or float_offsets:
        raise HkAnimError("non-empty transform/float offset tables are not handled")
    if mq_size != 4 * (ntt + nft):
        raise HkAnimError(f"mask size {mq_size} != 4 * tracks {ntt + nft}")
    if len(block_offsets) != num_blocks or len(float_block_offsets) != num_blocks:
        raise HkAnimError("block offset table size mismatch")
    stats: Counter = Counter()
    norms: List[float] = []
    QUAT_CHECKS.clear()
    step = max_fpb - 1
    tracks: List[List[Transform]] = [[None] * num_frames for _ in range(ntt)]
    block_checks = []
    boundary_t = boundary_r = 0.0
    for b in range(num_blocks):
        start = block_offsets[b]
        r = _Reader(data, start)
        masks = [tuple(r.take(4)) for _ in range(ntt)]
        first = b * step
        last = min(num_frames - 1, first + step)
        for t, (qb, pf, rf, sf) in enumerate(masks):
            pos = _read_vector(r, qb & 3, pf, 0.0, stats, "translation")
            rot = _read_rotation(r, (qb >> 2) & 0xF, rf, stats, norms)
            scl = _read_vector(r, (qb >> 6) & 3, sf, 1.0, stats, "scale")
            for f in range(first, last + 1):
                u = float(f - first)
                tq = rot.at(u)
                if rot.cps is not None:
                    raw_n = math.sqrt(sum(c * c for c in tq))
                    stats["max_blend_norm_dev_x1e6"] = max(stats["max_blend_norm_dev_x1e6"],
                                                           int(abs(raw_n - 1.0) * 1e6))
                x = (tuple(pos.at(u)), _normalize(tq), tuple(scl.at(u)))
                prev = tracks[t][f]
                if prev is not None:        # shared boundary frame: the previous block's end must agree
                    boundary_t = max(boundary_t, _tdist(prev[0], x[0]))
                    boundary_r = max(boundary_r, quat_angle(prev[1], x[1]))
                tracks[t][f] = x
        end_rel = r.pos - start
        block_checks.append({"block": b, "read_end": end_rel, "float_block_offset": float_block_offsets[b],
                             "next_block": (block_offsets[b + 1] - start) if b + 1 < num_blocks else len(data) - start})
        # Measured invariant: the transform stream of a block ends exactly where its float section starts.
        if end_rel != float_block_offsets[b]:
            raise HkAnimError(f"block {b}: transform stream ends at {end_rel}, float section at "
                              f"{float_block_offsets[b]} (stream misparsed)")
    if any(tr[f] is None for tr in tracks for f in range(num_frames)):
        raise HkAnimError("frames left undecoded")
    anim = Animation(atype, duration, num_frames, frame_dur, ntt, nft, tracks)
    anim.stats = {
        "forms": dict(sorted((k, v) for k, v in stats.items() if not k.startswith(("max_", "rotation_cp_sign")))),
        "rotation_cp_sign_flips": stats["rotation_cp_sign_flips"],
        "max_blend_norm_dev": stats["max_blend_norm_dev_x1e6"] / 1e6,
        "packed_quaternions": len(norms),
        "max_packed_quat_norm_dev": max((abs(n - 1.0) for n in norms), default=0.0),
        "packed_quat_dropped_not_largest": QUAT_CHECKS["dropped_not_largest"],
        "packed_quat_kept_three_over_unit": QUAT_CHECKS["kept_three_over_unit"],
        "block_boundary_max_translation_diff": boundary_t,
        "block_boundary_max_rotation_diff_deg": math.degrees(boundary_r),
        "num_blocks": num_blocks, "max_frames_per_block": max_fpb, "block_duration": block_dur,
        "block_inverse_duration": block_inv, "data_bytes": len(data), "blocks": block_checks,
    }
    return anim


# --------------------------------------------------------------------------------------------------------------------
# file-level entry points
# --------------------------------------------------------------------------------------------------------------------
def load(data: bytes) -> HkxFile:
    p = Packfile(data)
    objs = p.objects()
    classes = Counter(c for _, c in objs)
    skeletons = [read_skeleton(p, o) for o, c in objs if c == "hkaSkeleton"]
    bindings = [read_binding(p, o) for o, c in objs if c == "hkaAnimationBinding"]
    frames = {o: read_reference_frame(p, o) for o, c in objs if c == "hkaDefaultAnimatedReferenceFrame"}
    anims = []
    for o, c in objs:
        if c == "hkaSplineCompressedAnimation":
            a = decode_spline(p, o)
            a.annotations = read_annotations(p, o)
            em = p.pointer(o + 32)
            if em is not None:
                a.reference_frame = frames.get(em)
            anims.append(a)
        elif c in ("hkaInterleavedUncompressedAnimation", "hkaQuantizedAnimation", "hkaPredictiveCompressedAnimation"):
            raise HkAnimError(f"{c} is not decoded (not measured in the Fallout 4 robot/deathclaw clips)")
    return HkxFile(skeletons, anims, bindings, classes)


def load_file(path: str) -> HkxFile:
    with open(path, "rb") as f:
        return load(f.read())


# --------------------------------------------------------------------------------------------------------------------
# pose helpers (for checks and later retargeting)
# --------------------------------------------------------------------------------------------------------------------
def quat_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def quat_rotate(q, v):
    x, y, z, w = q
    vx, vy, vz = v
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty), vy + w * ty + (z * tx - x * tz), vz + w * tz + (x * ty - y * tx))


def quat_angle(a, b) -> float:
    """Angle in radians between two rotations (sign-independent)."""
    d = abs(sum(x * y for x, y in zip(a, b)))
    return 2.0 * math.acos(min(1.0, d))


def model_space(parents: Sequence[int], local: Sequence[Transform]) -> List[Transform]:
    """Compose local (t, q, s) transforms down the hierarchy into model space (uniform-scale assumption)."""
    out: List[Transform] = []
    for i, (t, q, s) in enumerate(local):
        par = parents[i]
        if par < 0:
            out.append((tuple(t), tuple(q), tuple(s)))
            continue
        pt, pq, ps = out[par]
        st = (t[0] * ps[0], t[1] * ps[1], t[2] * ps[2])
        rt = quat_rotate(pq, st)
        out.append(((pt[0] + rt[0], pt[1] + rt[1], pt[2] + rt[2]), _normalize(quat_mul(pq, q)),
                    (ps[0] * s[0], ps[1] * s[1], ps[2] * s[2])))
    return out


def bone_pose(anim: Animation, binding: Optional[Binding], skeleton: Skeleton, f: int) -> List[Transform]:
    """Local pose of every skeleton bone at frame f: reference pose, overridden by the bound tracks (additive
    bindings are not composed here; the caller must handle BLEND_HINT additive clips)."""
    pose = list(skeleton.reference_pose)
    mapping = binding.transform_track_to_bone if binding and binding.transform_track_to_bone else \
        list(range(anim.num_transform_tracks))
    for t, bone in enumerate(mapping):
        if 0 <= bone < len(pose):
            pose[bone] = anim.tracks[t][f]
    return pose


# --------------------------------------------------------------------------------------------------------------------
# measurement report and JSON form
# --------------------------------------------------------------------------------------------------------------------
def _tdist(a, b) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def clip_report(anim: Animation, binding: Optional[Binding], skeleton: Optional[Skeleton],
                still_eps_t: float = 1e-3, still_eps_r: float = 1e-3) -> Dict:
    """Measurements on one decoded clip (no judgement by eye):
      frames_match     numFrames == round(duration / frameDuration) + 1
      finite           no NaN / inf in any decoded value
      quaternions      max |norm - 1| of packed quaternions and of spline blends before normalization
      still tracks     tracks whose translation and rotation never move in the clip; their largest difference from
                       the bound bone's reference pose (meaningful for NORMAL blend clips only)
      frame0_vs_ref    per bound bone, frame 0 against the reference pose (largest translation and rotation)"""
    rep: Dict = {
        "duration": anim.duration, "num_frames": anim.num_frames, "frame_duration": anim.frame_duration,
        "fps": round(anim.fps, 4), "transform_tracks": anim.num_transform_tracks, "float_tracks": anim.num_float_tracks,
        "frames_expected": int(round(anim.duration / anim.frame_duration)) + 1 if anim.frame_duration else None,
    }
    rep["frames_match"] = rep["frames_expected"] == anim.num_frames
    finite = True
    max_out_norm_dev = 0.0
    for tr in anim.tracks:
        for t, q, s in tr:
            if not all(math.isfinite(v) for v in (*t, *q, *s)):
                finite = False
            max_out_norm_dev = max(max_out_norm_dev, abs(math.sqrt(sum(c * c for c in q)) - 1.0))
    rep["finite"] = finite
    rep["max_output_quat_norm_dev"] = max_out_norm_dev
    for k in ("max_packed_quat_norm_dev", "max_blend_norm_dev", "packed_quaternions", "rotation_cp_sign_flips",
              "packed_quat_dropped_not_largest", "packed_quat_kept_three_over_unit", "num_blocks", "forms",
              "block_boundary_max_translation_diff", "block_boundary_max_rotation_diff_deg"):
        rep[k] = anim.stats.get(k)
    jump_t = jump_r = 0.0
    for tr in anim.tracks:
        for a, b in zip(tr, tr[1:]):
            jump_t = max(jump_t, _tdist(a[0], b[0]))
            jump_r = max(jump_r, quat_angle(a[1], b[1]))
    rep["max_frame_step_translation"] = jump_t
    rep["max_frame_step_rotation_deg"] = math.degrees(jump_r)
    rep["blend_hint"] = binding.blend_hint_name if binding else None
    mapping = binding.transform_track_to_bone if binding and binding.transform_track_to_bone else \
        list(range(anim.num_transform_tracks))
    moving, still = [], []
    for t, tr in enumerate(anim.tracks):
        t0, q0, s0 = tr[0]
        dt = max(_tdist(x[0], t0) for x in tr)
        dr = max(quat_angle(x[1], q0) for x in tr)
        (still if dt <= still_eps_t and dr <= still_eps_r else moving).append((t, dt, dr))
    rep["moving_tracks"] = len(moving)
    rep["still_tracks"] = len(still)
    if skeleton is not None:
        names = skeleton.bones
        rep["moving_bones"] = [names[mapping[t]] for t, _, _ in moving if 0 <= mapping[t] < len(names)]
        worst_t = (0.0, None)
        worst_r = (0.0, None)
        additive = bool(binding) and binding.blend_hint in (1, 2)
        ident = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0))
        within, off = 0, []
        for t, _, _ in still:
            b = mapping[t]
            if not 0 <= b < len(names):
                continue
            # a still track of a normal clip should hold the bind pose; of an additive clip, the identity delta
            rt, rq, _rs = ident if additive else skeleton.reference_pose[b]
            ct, cq, _cs = anim.tracks[t][0]
            d_t, d_r = _tdist(ct, rt), quat_angle(cq, rq)
            if d_t > worst_t[0]:
                worst_t = (d_t, names[b])
            if d_r > worst_r[0]:
                worst_r = (d_r, names[b])
            if d_t <= 0.01 and math.degrees(d_r) <= 0.1:
                within += 1
            else:
                off.append({"bone": names[b], "translation": round(d_t, 4), "rotation_deg": round(math.degrees(d_r), 3)})
        rep["still_compared_with"] = "identity (additive clip)" if additive else "skeleton reference pose"
        rep["still_within_0.01u_0.1deg"] = within
        rep["still_off_reference"] = off
        rep["still_vs_ref_max_translation"] = {"value": worst_t[0], "bone": worst_t[1]}
        rep["still_vs_ref_max_rotation_deg"] = {"value": math.degrees(worst_r[0]), "bone": worst_r[1]}
        diffs = []
        for t, b in enumerate(mapping):
            if 0 <= b < len(names):
                rt, rq, _rs = skeleton.reference_pose[b]
                ct, cq, _cs = anim.tracks[t][0]
                diffs.append((names[b], _tdist(ct, rt), math.degrees(quat_angle(cq, rq))))
        rep["frame0_vs_ref_max_translation"] = max(((d, n) for n, d, _ in diffs), default=(0.0, None))
        rep["frame0_vs_ref_max_rotation_deg"] = max(((r, n) for n, _, r in diffs), default=(0.0, None))
        rep["frame0_vs_ref_top5"] = [{"bone": n, "translation": d, "rotation_deg": r}
                                     for n, d, r in sorted(diffs, key=lambda x: -(x[1] + x[2]))[:5]]
    if anim.reference_frame is not None:
        rf = anim.reference_frame
        s0, s1 = rf.samples[0] if rf.samples else None, rf.samples[-1] if rf.samples else None
        rep["root_motion"] = {"up": rf.up, "forward": rf.forward, "samples": len(rf.samples), "first": s0,
                              "last": s1}
    rep["annotations"] = [(n, a) for n, a in anim.annotations if a]
    return rep


def to_json(anim: Animation, binding: Optional[Binding] = None, skeleton: Optional[Skeleton] = None,
            digits: int = 6) -> Dict:
    """Full decoded data: per track the bound bone and per-frame [tx, ty, tz, qx, qy, qz, qw, sx, sy, sz]."""
    mapping = binding.transform_track_to_bone if binding and binding.transform_track_to_bone else \
        list(range(anim.num_transform_tracks))
    out = {"duration": anim.duration, "num_frames": anim.num_frames, "frame_duration": anim.frame_duration,
           "blend_hint": binding.blend_hint_name if binding else None,
           "layout": "per frame [tx, ty, tz, qx, qy, qz, qw, sx, sy, sz], local to the parent bone, Havok units",
           "tracks": []}
    for t, tr in enumerate(anim.tracks):
        b = mapping[t] if t < len(mapping) else -1
        out["tracks"].append({
            "track": t, "bone_index": b,
            "bone": skeleton.bones[b] if skeleton is not None and 0 <= b < len(skeleton.bones) else None,
            "frames": [[round(v, digits) for v in (*x[0], *x[1], *x[2])] for x in tr]})
    if anim.reference_frame is not None:
        rf = anim.reference_frame
        out["root_motion"] = {"up": rf.up, "forward": rf.forward, "duration": rf.duration,
                              "samples": [[round(v, digits) for v in s] for s in rf.samples]}
    out["annotations"] = [{"track": n, "events": a} for n, a in anim.annotations if a]
    return out
