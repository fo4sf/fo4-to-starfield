"""Starfield `.af` animation reader (per-bone keyframes of a `.rig` skeleton) and a minimal `.rig` reader.

    rig = parse_rig(rig_bytes)                     # bone names, parents, bind pose, translation precision
    anim = parse(af_bytes, precision=rig.precision)
    anim.header.frame_count, anim.bones[i].rotation.frames, anim.bones[i].rotation.values
    deltas = sample(anim, frame)                   # per-bone (translation, quaternion_wxyz) deltas at one frame
    pose = pose_at(anim, frame, rig)               # per-bone local transforms = bind pose composed with the deltas
    frames = expand(anim, rig)                     # frames[frame][bone] = (translation, quaternion_wxyz)

Our own implementation. The structure was taken from the field names published by the CALUMI.Animation project
(https://github.com/Calaverah/CALUMI.Animation, LGPL-3.0; no code copied) and every rule below was checked against
the owner's own `Starfield - Animations.ba2`: all 19,358 `.af` files in it parse to exactly their byte length
(docs/ai/research-log.md "Starfield .af channel layout", 2026-10-11, with status labels; `scripts/af_inspect.py`
reproduces the checks). Status labels in this docstring: [v] verified on vanilla files, [h] supported hypothesis,
[u] unresolved.

Header, 64 bytes (all offsets little-endian)
    0x00 u64   magic, 0 in all 19,358 files [v]
    0x08 f32x4 header rotation, stored w x y z (identity in the door files and in 15,221 files; meaning [u])
    0x18 f32x3 header translation (zero in the door files; meaning [u])
    0x24 u8    flags: bit0 unused in vanilla, bit1 key counters are u16, bit2 key frame indices are u16,
               bit3 a scalar channel is present (CALUMI names); bits 1-3 [v] (observed 0, 4, 6, 8, 12, 14)
    0x25 u8x3  zero
    0x28 u16   version, 5 in all files [v]
    0x2A u16   bone count = the rig's *animated* bone count (u16 at rig offset 58): equals the rig's bone count for
               the door rigs (6, 21, 24, 49), 82 of 97 for the human rig [v]
    0x2C u16   frame count [v]; the frame rate is not in the file (30 fps gives 1 s / 2 s / 3 s / 10 s for the common
               counts 31 / 61 / 91 / 301 [h])
    0x2E u16   index atlas length in bytes [v]
    0x30 u16   suffix block count (0 in the door files) [v]
    0x32 u16   preamble size in bytes, a multiple of 4 (0 in the door files) [v]
    0x34 f32x3 three floats, zero in 11,918 files (meaning [u])
Sections after the header, in this order [v by exact consumption]:
    preamble: `preamble size` opaque bytes. Inside [h]: u32 count, then entries (u16 n, f32 x 2n, f32 x frame count,
      i16 x n, i8 x n), padded to 4 bytes; parsed best-effort into Animation.preamble.
    suffix ids: `suffix block count` x u32; not floats (values such as 0xFFF1BB1A repeat across the files that
      animate the same prop), 32-bit identifiers of the extra tracks [h]. Order relative to the preamble [u]
      (both are skipped, so it does not change the decode).
    index atlas: u8 run lengths over the bones in rig order, alternating "bones without a block" and "bones with a
      block", starting with the empty run (Akila door: 00 06 = all six bones have a block; turret death: 03 03) [v]
    one block per bone with data, in bone order [v]:
      6 counters (u8, or u16 with flag bit1): rotation keys, rotation prefixes, translation keys, translation
        prefixes, scalar keys, priority keys
      frame indices (u8, or u16 with flag bit2): rotation, translation, scalar, priority keys
      rotation entries    3 x i8 per key
      rotation prefixes   4 bytes: three 7-bit signed coarse values each with a 1-bit x8 flag in the top bit, then a
                          byte with the run length (low 6 bits, covers run+1 keys) and the dropped quaternion
                          component (high 2 bits: 0 x, 1 y, 2 z, 3 w)
      translation entries 3 x i8 per key
      translation prefixes (2-aligned) 8 bytes: i16 x, y, z coarse values and a u16 run length (covers run keys)
      scalar entries (2-aligned) i16 per key; priority entries u8 per key
    suffix blocks: `suffix block count` more blocks of the same layout (extra tracks; none in the door files) [v]

Rotation [v]: component = coarse * sqrt(1/2)/64 + fine * sqrt(1/2)/16384 * (8 if the x8 flag is set) for the three
stored components; the dropped component is sqrt(1 - sum of squares), always non-negative. The coarse step is fixed
by the 90.0 deg door swings (|z| = w needs 64 steps = sqrt(1/2)); the fine step gives the clean 60.0 / 25.0 deg
handle swings of the ship door [h for the fine step]. The dropped component is the largest one (180 deg about y drops
y) [v].
Translation [v for the coarse step]: component = coarse * low + fine * high, with (low, high) from the rig header
(0.03125 / 0.00025 for the building and actor rigs, 0.25 / 0.002 for the ship door rigs; always 125 fine steps per
coarse step). The elevator door panels slide by exactly their bind offset (1.000 m and 1.500 m), which fixes the coarse
step; the fine step gives clean 0.088 / 0.606 / 0.097 values [h].
Values are deltas from the rig's bind pose, not absolute local transforms [v]: in 9 door families (57 channels, 37 of
them on bones whose bind pose is not identity / zero) every `open.af` channel starts at identity / zero and every
`close.af` channel ends there, and open's last key equals close's first key. How the delta composes with the bind
pose is [h]: translation delta added in the parent frame (the generic door's mirrored latch bones, bind-twisted by
180 deg, carry opposite-sign deltas, which retracts both latches only in the parent frame); rotation delta applied in
the parent frame, local = delta * bind (the ship door's `Arm01`, bind 105.5 deg about an oblique axis, rotates about
the root y axis that every other hinge of that door uses). `pose_at` uses this composition; the order matters only
for bones with a non-identity bind rotation (none of the door hinge / panel bones).
Keys are sparse; `sample` interpolates linearly between them (our choice, the engine's interpolation is [u]) and
holds the first / last key outside the keyed range. Units are the rig's units (metres for the door rigs).
"""
import math
import struct
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

Quat = Tuple[float, float, float, float]      # w, x, y, z
Vec3 = Tuple[float, float, float]

ROTATION_COARSE = math.sqrt(0.5) / 64.0
ROTATION_FINE = math.sqrt(0.5) / 16384.0
DEFAULT_PRECISION = (0.03125, 0.00025)        # (coarse, fine) translation steps when no rig is given
SHIP_PRECISION = (0.25, 0.002)
HEADER_SIZE = 64
RIG_HEADER_SIZE = 80
RIG_BONE_SIZE = 96
IDENTITY: Quat = (1.0, 0.0, 0.0, 0.0)
ZERO: Vec3 = (0.0, 0.0, 0.0)


class AfError(ValueError):
    pass


@dataclass
class Header:
    magic: int
    rotation: Quat
    translation: Vec3
    flags: int
    version: int
    bone_count: int
    frame_count: int
    atlas_length: int
    suffix_count: int
    preamble_size: int
    tail_floats: Vec3

    @property
    def wide_counters(self) -> bool:
        return bool(self.flags & 0x2)

    @property
    def wide_frames(self) -> bool:
        return bool(self.flags & 0x4)

    @property
    def has_scalar(self) -> bool:
        return bool(self.flags & 0x8)


@dataclass
class Channel:
    frames: List[int] = field(default_factory=list)
    values: list = field(default_factory=list)

    def __len__(self):
        return len(self.frames)


@dataclass
class BoneTrack:
    bone: int
    rotation: Channel = field(default_factory=Channel)       # values: quaternion (w, x, y, z) deltas from bind
    translation: Channel = field(default_factory=Channel)    # values: (x, y, z) deltas from bind, rig units
    scalar: Channel = field(default_factory=Channel)         # values: raw i16 (meaning unresolved)
    priority: Channel = field(default_factory=Channel)       # values: raw u8 (meaning unresolved)
    raw: dict = field(default_factory=dict)                  # undecoded prefixes/entries for inspection

    @property
    def animated(self) -> bool:
        return bool(self.rotation or self.translation or self.scalar or self.priority)


@dataclass
class Preamble:
    count: int
    pre: List[float]
    main: List[float]
    footer1: List[int]
    footer2: List[int]


@dataclass
class Animation:
    header: Header
    atlas: List[int]
    bones: List[BoneTrack]
    preamble_raw: bytes
    preamble: List[Preamble]          # best-effort decode of preamble_raw; empty when it did not fit
    preamble_parsed: bool
    suffix_ids: List[int]
    suffix_blocks: List[BoneTrack]
    precision: Tuple[float, float]
    consumed: int

    @property
    def animated_bones(self) -> List[int]:
        return [b.bone for b in self.bones if b.animated]


@dataclass
class RigBone:
    index: int
    name: str
    parent: int
    rotation: Quat          # local bind rotation (w, x, y, z)
    global_rotation: Quat
    translation: Vec3       # local bind translation, rig units


@dataclass
class Rig:
    version: int
    precision: Tuple[float, float]   # (coarse, fine) translation steps for this rig's .af files
    bones: List[RigBone]
    animated_count: int              # u16 at 58: the bone count .af files of this rig carry
    bone_map: List[int]              # u16 slots between the bone table and the names (0xFFFF = unmapped)

    def index(self, name: str) -> int:
        for b in self.bones:
            if b.name == name:
                return b.index
        raise KeyError(name)


class _Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def align(self, n: int):
        if n > 1 and self.pos % n:
            self.pos += n - self.pos % n

    def take(self, size: int, align: int = 1) -> bytes:
        self.align(align)
        if self.pos + size > len(self.data):
            raise AfError('truncated .af: need %d bytes at 0x%X, have %d' % (size, self.pos, len(self.data)))
        out = self.data[self.pos:self.pos + size]
        self.pos += size
        return out

    def u(self, size: int, align: int = None, signed: bool = False) -> int:
        return int.from_bytes(self.take(size, size if align is None else align), 'little', signed=signed)

    def f32(self) -> float:
        return struct.unpack('<f', self.take(4, 4))[0]


def _signed7(byte: int) -> int:
    v = byte & 0x7F
    return v - 128 if v & 0x40 else v


def decode_rotation(prefix: bytes, entry: bytes) -> Quat:
    """One 4-byte rotation prefix + one 3-byte entry -> unit quaternion (w, x, y, z)."""
    if len(prefix) != 4 or len(entry) != 3:
        raise AfError('rotation prefix is 4 bytes and entry 3 bytes')
    fine = struct.unpack('<3b', entry)
    stored = []
    for i in range(3):
        scale = 8.0 if prefix[i] & 0x80 else 1.0
        stored.append(ROTATION_COARSE * _signed7(prefix[i]) + ROTATION_FINE * fine[i] * scale)
    missing = prefix[3] >> 6
    rest = 1.0 - sum(c * c for c in stored)
    dropped = math.sqrt(rest) if rest > 0 else 0.0
    xyzw = stored[:missing] + [dropped] + stored[missing:]
    x, y, z, w = xyzw
    n = math.sqrt(w * w + x * x + y * y + z * z)
    return (w / n, x / n, y / n, z / n)


def rotation_run_length(prefix: bytes) -> int:
    """Number of rotation keys one prefix covers (stored run + 1)."""
    return (prefix[3] & 0x3F) + 1


def decode_translation(prefix: bytes, entry: bytes, precision: Tuple[float, float] = DEFAULT_PRECISION) -> Vec3:
    """One 8-byte translation prefix + one 3-byte entry -> (x, y, z) in rig units."""
    if len(prefix) != 8 or len(entry) != 3:
        raise AfError('translation prefix is 8 bytes and entry 3 bytes')
    coarse = struct.unpack('<3h', prefix[:6])
    fine = struct.unpack('<3b', entry)
    low, high = precision
    return tuple(coarse[i] * low + fine[i] * high for i in range(3))


def translation_run_length(prefix: bytes) -> int:
    return struct.unpack_from('<H', prefix, 6)[0]


def _expand_runs(prefixes: Sequence[bytes], lengths: Sequence[int], needed: int, what: str) -> List[bytes]:
    out = []
    for p, n in zip(prefixes, lengths):
        out.extend([p] * n)
    if len(out) != needed:
        raise AfError('%s prefixes cover %d keys, block has %d' % (what, len(out), needed))
    return out


def _parse_header(data: bytes) -> Header:
    if len(data) < HEADER_SIZE:
        raise AfError('.af shorter than its 64-byte header')
    magic, = struct.unpack_from('<Q', data, 0)
    w, x, y, z = struct.unpack_from('<4f', data, 8)
    tx, ty, tz = struct.unpack_from('<3f', data, 0x18)
    flags = data[0x24]
    version, bones, frames, atlas, suffix, preamble = struct.unpack_from('<6H', data, 0x28)
    tail = struct.unpack_from('<3f', data, 0x34)
    return Header(magic, (w, x, y, z), (tx, ty, tz), flags, version, bones, frames, atlas, suffix, preamble, tail)


def _parse_block(r: _Reader, h: Header, bone: int, precision) -> BoneTrack:
    csize = 2 if h.wide_counters else 1
    ksize = 2 if h.wide_frames else 1
    counts = [r.u(csize) for _ in range(6)]
    n_rot, n_rot_prefix, n_trans, n_trans_prefix, n_scalar, n_priority = counts
    rot_frames = [r.u(ksize) for _ in range(n_rot)]
    trans_frames = [r.u(ksize) for _ in range(n_trans)]
    scalar_frames = [r.u(ksize) for _ in range(n_scalar)]
    priority_frames = [r.u(ksize) for _ in range(n_priority)]
    rot_entries = [r.take(3) for _ in range(n_rot)]
    rot_prefixes = [r.take(4) for _ in range(n_rot_prefix)]
    trans_entries = [r.take(3) for _ in range(n_trans)]
    trans_prefixes = [r.take(8, 2) for _ in range(n_trans_prefix)]
    scalars = [r.u(2, signed=True) for _ in range(n_scalar)]
    priorities = [r.u(1) for _ in range(n_priority)]
    track = BoneTrack(bone)
    for frames in (rot_frames, trans_frames, scalar_frames, priority_frames):
        if any(b > a for a, b in zip(frames[1:], frames)) or any(f >= h.frame_count for f in frames):
            raise AfError('bone %d: key frames are not ascending within 0..%d' % (bone, h.frame_count - 1))
    if n_rot:
        prefixes = _expand_runs(rot_prefixes, [rotation_run_length(p) for p in rot_prefixes], n_rot, 'rotation')
        track.rotation = Channel(rot_frames, [decode_rotation(p, e) for p, e in zip(prefixes, rot_entries)])
    elif n_rot_prefix:
        raise AfError('bone %d: rotation prefixes without rotation keys' % bone)
    if n_trans:
        prefixes = _expand_runs(trans_prefixes, [translation_run_length(p) for p in trans_prefixes], n_trans,
                                'translation')
        track.translation = Channel(trans_frames,
                                    [decode_translation(p, e, precision) for p, e in zip(prefixes, trans_entries)])
    elif n_trans_prefix:
        raise AfError('bone %d: translation prefixes without translation keys' % bone)
    track.scalar = Channel(scalar_frames, scalars)
    track.priority = Channel(priority_frames, priorities)
    track.raw = {'rotation_prefixes': rot_prefixes, 'rotation_entries': rot_entries,
                 'translation_prefixes': trans_prefixes, 'translation_entries': trans_entries}
    return track


def _parse_preamble(blob: bytes, frame_count: int) -> Tuple[List[Preamble], bool]:
    """Best-effort decode of the preamble (supported hypothesis). Returns ([], False) when it does not fit."""
    r = _Reader(blob)
    out = []
    try:
        count = r.u(4)
        for _ in range(count):
            n = r.u(2)
            pre = [r.f32() for _ in range(2 * n)]
            main = [r.f32() for _ in range(frame_count)]
            f1 = [r.u(2, signed=True) for _ in range(n)]
            f2 = [r.u(1, signed=True) for _ in range(n)]
            out.append(Preamble(n, pre, main, f1, f2))
    except AfError:
        return [], False
    # the header's size is padded to 4 bytes
    if not (r.pos <= len(blob) <= r.pos + 3):
        return [], False
    return out, True


def parse(data: bytes, precision: Tuple[float, float] = DEFAULT_PRECISION, strict: bool = True) -> Animation:
    """Parse a whole .af file. `precision` is the rig's (coarse, fine) translation step (see parse_rig).

    With strict=True the file must be consumed exactly and the atlas must cover the header's bone count."""
    h = _parse_header(data)
    r = _Reader(data)
    r.pos = HEADER_SIZE
    preamble_raw = r.take(h.preamble_size)
    preamble, preamble_parsed = _parse_preamble(preamble_raw, h.frame_count) if h.preamble_size else ([], True)
    suffix_ids = [r.u(4) for _ in range(h.suffix_count)]
    atlas = list(r.take(h.atlas_length))
    if strict and sum(atlas) != h.bone_count:
        raise AfError('index atlas covers %d bones, header says %d' % (sum(atlas), h.bone_count))
    bones: List[BoneTrack] = []
    for run, length in enumerate(atlas):
        for _ in range(length):
            bone = len(bones)
            bones.append(_parse_block(r, h, bone, precision) if run % 2 else BoneTrack(bone))
    suffix_blocks = [_parse_block(r, h, -1 - i, precision) for i in range(h.suffix_count)]
    if strict and r.pos != len(data):
        raise AfError('parsed %d of %d bytes' % (r.pos, len(data)))
    return Animation(h, atlas, bones, preamble_raw, preamble, preamble_parsed, suffix_ids, suffix_blocks, precision,
                     r.pos)


def parse_rig(data: bytes) -> Rig:
    """Minimal Starfield .rig reader: header precision, 96-byte bone records, bone map, name table.

    Layout (7 vanilla rigs checked: 3 doors, human, terrormorph, turret, bipedA): u32 version 5, file size,
    header size 80, 0, bone-map offset (= 80 + 96 * bones), 0; 3 x u64; f32 coarse step, f32 fine step; u16 bone
    count; u16 animated bone count. Bone record: f32x4 local rotation wxyz, f32x4 global rotation, f32x3 position,
    u32 type, u64 absolute offset of the bone's name, i32 parent, 36 bytes of twist / mirror fields (not decoded).
    The bone map (157 u16 slots in all 7 rigs) sits at the bone-map offset; the null-terminated names follow it."""
    if len(data) < RIG_HEADER_SIZE:
        raise AfError('.rig shorter than its 80-byte header')
    version, file_size, header_size, _, map_offset, _ = struct.unpack_from('<6I', data, 0)
    low, high, bone_count, animated = struct.unpack_from('<ffHH', data, 48)
    if header_size != RIG_HEADER_SIZE or file_size != len(data):
        raise AfError('.rig header size %d / file size %d do not match' % (header_size, file_size))
    if not (0 < high < low):
        raise AfError('.rig precision %r is not (coarse > fine > 0)' % ((low, high),))
    table_end = RIG_HEADER_SIZE + RIG_BONE_SIZE * bone_count
    if table_end > len(data) or map_offset < table_end:
        raise AfError('.rig bone table overruns the file')
    records = []
    for i in range(bone_count):
        off = RIG_HEADER_SIZE + RIG_BONE_SIZE * i
        lw, lx, ly, lz, gw, gx, gy, gz = struct.unpack_from('<8f', data, off)
        tx, ty, tz = struct.unpack_from('<3f', data, off + 32)
        name_off, = struct.unpack_from('<Q', data, off + 48)
        parent, = struct.unpack_from('<i', data, off + 56)
        if parent >= i or parent < -1:
            raise AfError('.rig bone %d has parent %d (parents must come first)' % (i, parent))
        if not (map_offset <= name_off < len(data)):
            raise AfError('.rig bone %d name offset %d outside the name table' % (i, name_off))
        records.append((name_off, parent, (lw, lx, ly, lz), (gw, gx, gy, gz), (tx, ty, tz)))
    names_start = min((rec[0] for rec in records), default=len(data))
    bone_map = list(struct.unpack_from('<%dH' % ((names_start - map_offset) // 2), data, map_offset))
    bones = []
    for i, (name_off, parent, lrot, grot, pos) in enumerate(records):
        end = data.find(b'\0', name_off)
        name = data[name_off:end if end >= 0 else len(data)].decode('latin-1')
        bones.append(RigBone(i, name, parent, lrot, grot, pos))
    return Rig(version, (low, high), bones, animated, bone_map)


def qmul(a: Quat, b: Quat) -> Quat:
    """Hamilton product a * b (w, x, y, z): the rotation that applies b first, then a."""
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return (w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2)


def _slerp(a: Quat, b: Quat, t: float) -> Quat:
    dot = sum(p * q for p, q in zip(a, b))
    if dot < 0:
        b = tuple(-c for c in b)
        dot = -dot
    if dot > 0.9995:
        out = tuple(p + (q - p) * t for p, q in zip(a, b))
    else:
        theta = math.acos(max(-1.0, min(1.0, dot)))
        sa, sb = math.sin((1 - t) * theta), math.sin(t * theta)
        out = tuple((p * sa + q * sb) / math.sin(theta) for p, q in zip(a, b))
    n = math.sqrt(sum(c * c for c in out))
    return tuple(c / n for c in out)


def _lerp3(a: Vec3, b: Vec3, t: float) -> Vec3:
    return tuple(p + (q - p) * t for p, q in zip(a, b))


def channel_at(channel: Channel, frame: float, mix):
    """Value of a sparse channel at `frame`: linear between the neighbouring keys, held outside them."""
    frames, values = channel.frames, channel.values
    if not frames:
        return None
    if frame <= frames[0]:
        return values[0]
    if frame >= frames[-1]:
        return values[-1]
    hi = next(i for i, f in enumerate(frames) if f >= frame)
    lo = hi - 1
    if frames[hi] == frame:
        return values[hi]
    t = (frame - frames[lo]) / (frames[hi] - frames[lo])
    return mix(values[lo], values[hi], t)


def sample(anim: Animation, frame: float) -> List[Tuple[Vec3, Quat]]:
    """Per-bone (translation delta, rotation delta wxyz) at `frame`; bones without a channel give zero / identity."""
    out = []
    for track in anim.bones:
        t = channel_at(track.translation, frame, _lerp3)
        q = channel_at(track.rotation, frame, _slerp)
        out.append((ZERO if t is None else t, IDENTITY if q is None else q))
    return out


def compose(bind: RigBone, delta_t: Vec3, delta_q: Quat, parent_frame: bool = True) -> Tuple[Vec3, Quat]:
    """Local transform of a bone from its bind pose and an .af delta.

    parent_frame=True (default, supported hypothesis, see the module docstring): translation = bind + delta,
    rotation = delta * bind. parent_frame=False applies the delta in the bone's own frame: rotation = bind * delta,
    translation = bind + bind_rotation(delta)."""
    bt, bq = bind.translation, bind.rotation
    if parent_frame:
        return tuple(p + d for p, d in zip(bt, delta_t)), qmul(delta_q, bq)
    rotated = qmul(qmul(bq, (0.0,) + tuple(delta_t)), (bq[0], -bq[1], -bq[2], -bq[3]))[1:]
    return tuple(p + d for p, d in zip(bt, rotated)), qmul(bq, delta_q)


def pose_at(anim: Animation, frame: float, rig: Rig, parent_frame: bool = True) -> List[Tuple[Vec3, Quat]]:
    """Per-bone local (translation, quaternion_wxyz) at `frame`: the rig's bind pose composed with the deltas."""
    if len(rig.bones) < len(anim.bones):
        raise AfError('rig has %d bones, animation needs %d' % (len(rig.bones), len(anim.bones)))
    return [compose(rig.bones[track.bone], t, q, parent_frame)
            for track, (t, q) in zip(anim.bones, sample(anim, frame))]


def expand(anim: Animation, rig: Optional[Rig] = None) -> List[List[Tuple[Vec3, Quat]]]:
    """frames[frame][bone] = (translation, quaternion_wxyz) for every frame: local transforms with a rig, deltas without."""
    if rig is None:
        return [sample(anim, f) for f in range(anim.header.frame_count)]
    return [pose_at(anim, f, rig) for f in range(anim.header.frame_count)]


def axis_angle(q: Quat) -> Tuple[Vec3, float]:
    """Rotation axis and angle in degrees of a unit quaternion (w, x, y, z); axis is zero for the identity."""
    w, x, y, z = q
    s = math.sqrt(x * x + y * y + z * z)
    if s < 1e-9:
        return (0.0, 0.0, 0.0), 0.0
    angle = 2.0 * math.atan2(s, w)
    if angle > math.pi:
        angle -= 2 * math.pi
    return (x / s, y / s, z / s), math.degrees(angle)
