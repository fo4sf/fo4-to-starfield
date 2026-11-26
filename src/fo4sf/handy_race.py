"""FO4SF_HandyRace: a Starfield race for Fallout 4's Mr. Handy, cloned from Starfield's Mini Bot race, plus the animation
manifests Starfield keeps beside its graphs, and the proposed Fallout 4 clip -> Starfield graph tag mapping.

Everything below was measured on the installed games (Starfield 1.16.244 data, Fallout 4 1.10.x data, 23 Nov 2026);
docs/actors/robot-animation.md holds the tables and the evidence. What is PROVEN by measurement and what is NOT:

PROVEN
  * MiniBotARace 00227705 / MiniBotABodyPartData 00227704 subrecords (dump_record()).
  * The manifest key (the <u64>.txt names under meshes\\animtextdata\\{animationfiledata, animationoffsets,
    animationstancedata, dynamicidledata}) is
        key = (BSCRC32(lower("|".join(animation folders))) << 32) | BSCRC32(lower(graph path))
    with BSCRC32 = the reflected CRC-32 table (poly 0xEDB88320) run with init 0 and no final xor, the graph path as the
    RACE's SGNM / NAM6 string ("AnimTextData\\Tables\\Graphs\\X.agx") and the folders as the SAPT strings of that
    sub-graph, in record order. Reproduces all 1,889 animationfiledata keys of Starfield - Animations.ba2 from the RACE
    records of Starfield.esm and the generatedsubgraphdata tables (the folder list of a generated row is its last column
    split at ", "). The 11 keys with no clip list (root graphs: Creature_Root, Human_Root, ...) have high word 0.
  * animationfiledata/<key>.txt = "3\\n1\\n<key>\\n<count>\\n" + one clip path per line ("<SAPT folder>\\<afx filename>",
    plain ASCII sort), LF line ends; it lists only the clips whose .afx tag the graph can play (Mini Bot: Diversion01 is
    left out of the Creature_Strafing list).
  * dynamicidledata/<key>.txt = "Version 1\\n" (+ clip paths without extension for graphs with dynamic idles).
  * animationoffsets/<key>.txt layout for the records we write (re-parses every shipped file whose clip records carry
    flags 0x0, 0x20, 0x400000 or 0x400020; flags 0x8/0x10/0x80 add blocks that are NOT decoded):
        "V5\\n", lstr graph, u32 N, N x (lstr tag, lstr clip path without extension),
        u32 M, M x (lstr clip path, f32 duration s, u32 flags, u32 0, u32 0, u32 nkeys, nkeys x 5 f32 (time + 4 floats,
        root-motion keys, meaning of the 4 floats not proven), u32 nevents, nevents x (f32 time s, lstr name))
    lstr = u8 length counting the NUL, the text, a NUL. Flag 0x400000 is set on every record with events.
  * Fallout 4 robot .hkx clip headers (duration, frame count, tracks, annotations) via fo4_clip_info().

NOT PROVEN (needs an in-game test)
  * that Starfield needs the manifests at all for a new race (it may build them itself); that a minimal animationoffsets
    file (no records) is enough when clips carry events; the meaning of animationstancedata (stance_data() writes the
    measured layout, but the pose it should hold is not known: see the doc). persistantsubgraphinfoandoffsetdata.txt
    lists 1,078 of the 1,901 keys and is not extended here.
  * which bone names the converted Handy rig will use. The BPTD uses Fallout 4's own MrHandyBodyPartData bones (hkx /
    skeletonref names: Chest, Pelvis, Spine2, Arm1|0..2, EyeArm3|0..2, COM, Root); they must exist in the new .rig.
"""
import json
import os
import struct
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .planet import esm

MINIBOT_RACE = 0x00227705
MINIBOT_BPTD = 0x00227704
HANDY_EDID = "FO4SF_HandyRace"
HANDY_BPTD_EDID = "FO4SF_HandyBodyPartData"
GRAPH_DIR = "AnimTextData\\Tables\\Graphs\\"
STRAFING_GRAPH = GRAPH_DIR + "Creature_Strafing.agx"
FURNITURE_GRAPH = GRAPH_DIR + "Furniture.agx"
ROOT_GRAPH = GRAPH_DIR + "Creature_Root.agx"


# ------------------------------------------------------------------------------------------------ hashes and keys
def _crc_table():
    t = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ 0xEDB88320 if c & 1 else c >> 1
        t.append(c)
    return t


_T = _crc_table()


def bs_crc32(data: bytes, crc: int = 0) -> int:
    """CRC-32 (reflected, poly 0xEDB88320) with init 0 and no final xor: Bethesda's string hash."""
    for x in data:
        crc = _T[(crc ^ x) & 0xFF] ^ (crc >> 8)
    return crc


def _norm(path: str) -> bytes:
    return path.replace("/", "\\").lower().encode("cp1252")


def graph_hash(graph_path: str) -> int:
    return bs_crc32(_norm(graph_path))


def folders_hash(folders: Sequence[str]) -> int:
    if not folders:
        return 0
    return bs_crc32(_norm("|".join(folders)))


def manifest_key(graph_path: str, folders: Sequence[str]) -> int:
    """The u64 file name of the four per-subgraph manifests (proven on 1,889 + 11 keys)."""
    return (folders_hash(folders) << 32) | graph_hash(graph_path)


# ------------------------------------------------------------------------------------------------ manifest files
def _lstr(text: str) -> bytes:
    b = text.encode("cp1252") + b"\0"
    if len(b) > 255:
        raise ValueError(f"string too long for a u8 length: {text!r}")
    return bytes([len(b)]) + b


def _read_lstr(b: bytes, p: int) -> Tuple[str, int]:
    n = b[p]
    s = b[p + 1:p + 1 + n]
    if n == 0 or s[-1:] != b"\0":
        raise ValueError(f"bad length-prefixed string at {p}")
    return s[:-1].decode("cp1252"), p + 1 + n


def clip_path(folder: str, afx_filename: str) -> str:
    return folder.rstrip("\\") + "\\" + afx_filename


def animation_file_data(key: int, clips: Iterable[str]) -> bytes:
    """animationfiledata/<key>.txt: header 3, 1, key, count, then the clip paths in plain (case-sensitive) ASCII order."""
    clips = sorted(set(clips))
    return ("3\n1\n%d\n%d\n" % (key, len(clips)) + "".join(c + "\n" for c in clips)).encode("cp1252")


def dynamic_idle_data(paths: Iterable[str] = ()) -> bytes:
    return ("Version 1\n" + "".join(p + "\n" for p in paths)).encode("cp1252")


GSD_HEADER = "Role\tPerspective\tActor Keyword(s)\tTarget Keyword(s)\tBehavior Path\tAnimation Path(s)\n"


def generated_subgraph_data(rows: Iterable[Tuple[str, str, str, str, str, Sequence[str]]] = ()) -> bytes:
    """generatedsubgraphdata/<race editor id lower>.txt: a tab table; rows (role, perspective, actor keywords, target
    keywords, graph path, folders). The Mini Bot's holds one keyword-conditioned Furniture row."""
    out = GSD_HEADER
    for role, persp, akw, tkw, graph, folders in rows:
        out += "\t".join((role, persp, akw, tkw, graph, ", ".join(folders))) + "\n"
    return out.encode("cp1252")


@dataclass
class OffsetClip:
    """One clip record of animationoffsets: path without extension, duration, flags, root-motion keys and events."""
    path: str
    duration: float
    events: List[Tuple[float, str]] = field(default_factory=list)
    keys: List[Tuple[float, float, float, float, float]] = field(default_factory=list)
    flags: Optional[int] = None          # None: 0x400000 if events else 0

    def to_bytes(self) -> bytes:
        flags = self.flags if self.flags is not None else (0x400000 if self.events else 0)
        out = _lstr(self.path) + struct.pack("<fIIII", self.duration, flags, 0, 0, len(self.keys))
        out += b"".join(struct.pack("<5f", *k) for k in self.keys)
        out += struct.pack("<I", len(self.events))
        out += b"".join(struct.pack("<f", t) + _lstr(n) for t, n in self.events)
        return out


def animation_offsets(graph_path: str, tags: Sequence[Tuple[str, str]] = (), clips: Sequence[OffsetClip] = ()) -> bytes:
    """animationoffsets/<key>.txt. tags: (tag, clip path without extension). With no tags and no clips this is the
    shipped minimal form (Mini Bot Furniture/Idle set, 53 bytes)."""
    out = b"V5\n" + _lstr(graph_path) + struct.pack("<I", len(tags))
    out += b"".join(_lstr(t) + _lstr(c) for t, c in tags)
    out += struct.pack("<I", len(clips)) + b"".join(c.to_bytes() for c in clips)
    return out


def parse_animation_offsets(b: bytes):
    """(graph, [(tag, clip)], [OffsetClip]) for files whose records use only the decoded flags; raises ValueError on
    the undecoded blocks (flags 0x8 / 0x10 / 0x80) or when the parse does not end at the end of the file."""
    if b[:3] != b"V5\n":
        raise ValueError("not a V5 animationoffsets file")
    graph, p = _read_lstr(b, 3)
    n, = struct.unpack_from("<I", b, p)
    p += 4
    tags = []
    for _ in range(n):
        t, p = _read_lstr(b, p)
        c, p = _read_lstr(b, p)
        tags.append((t, c))
    m, = struct.unpack_from("<I", b, p)
    p += 4
    clips = []
    for _ in range(m):
        path, p = _read_lstr(b, p)
        dur, flags, a, z, nk = struct.unpack_from("<fIIII", b, p)
        if flags & 0x98 or a or z:
            raise ValueError(f"undecoded clip record (flags 0x{flags:x}) for {path}")
        p += 20
        keys = [struct.unpack_from("<5f", b, p + 20 * i) for i in range(nk)]
        p += 20 * nk
        ne, = struct.unpack_from("<I", b, p)
        p += 4
        evs = []
        for _ in range(ne):
            t, = struct.unpack_from("<f", b, p)
            name, p = _read_lstr(b, p + 4)
            evs.append((t, name))
        clips.append(OffsetClip(path, dur, evs, keys, flags))
    if p != len(b):
        raise ValueError(f"parse ended at {p} of {len(b)}")
    return graph, tags, clips


STANCE_TYPE = "AnimationTransformedBoneArray_AnimationBoneTransform"


def parse_stance_data(b: bytes):
    """(header words, [(bone index, 7 floats)], trailer bytes) of an animationstancedata file of the minimal shape (one
    bone array then a 16-byte trailer; 214- and 342-byte shipped files). Bigger files hold more blocks (not decoded)."""
    t, p = _read_lstr(b, 0)
    if t != STANCE_TYPE:
        raise ValueError(f"unexpected stance type {t!r}")
    h = struct.unpack_from("<4I", b, p)
    p += 16
    bones = []
    for _ in range(h[3]):
        vals = struct.unpack_from("<7f", b, p)
        idx, pad = struct.unpack_from("<HH", b, p + 28)
        if pad != 0xFFFF:
            raise ValueError(f"unexpected bone padding 0x{pad:x}")
        bones.append((idx, vals))
        p += 32
    return h[:3], bones, b[p:]


def stance_data(bones: Sequence[Tuple[int, Sequence[float]]], header=(2, 1, 0), trailer_word: int = 2) -> bytes:
    """animationstancedata in the measured minimal layout: bones = (rig bone index, 7 floats: a unit quaternion (order not
    proven) then a translation). The pose the engine expects there is NOT known (the Mini Bot's differ per sub-graph);
    the trailer is u32 trailer_word, u32 0, i32 -1, u32 0 as in the 342-byte Mini Bot Furniture file."""
    out = _lstr(STANCE_TYPE) + struct.pack("<4I", header[0], header[1], header[2], len(bones))
    for idx, vals in bones:
        out += struct.pack("<7f", *vals) + struct.pack("<HH", idx, 0xFFFF)
    return out + struct.pack("<IIiI", trailer_word, 0, -1, 0)


def afx_bytes(tag: str, filename: str, is_state: int = 1, events: Sequence[Tuple[int, str]] = (),
              audio: Sequence[Tuple[int, str]] = ()) -> bytes:
    """A clip's .afx sidecar in the vanilla Mini Bot shape (tab indents, events and audios by frame at 30 fps)."""
    s = "<root>\n\t<is_state>%d</is_state>\n\t<tag>%s</tag>\n\t<filename>%s</filename>\n" % (int(is_state), tag, filename)
    if events:
        s += "\t<events>\n" + "".join("\t\t<event><frame>%d</frame><name>%s</name><payload></payload></event>\n"
                                      % (f, n) for f, n in events) + "\t</events>\n"
    if audio:
        s += "\t<audios>\n" + "".join("\t\t<audio><frame>%d</frame><foley>%s</foley></audio>\n" % (f, n)
                                      for f, n in audio) + "\t</audios>\n"
    return (s + "</root>\n").encode("utf-8")


# ------------------------------------------------------------------------------------------------ Fallout 4 clip headers
def fo4_clip_info(hkx: bytes) -> dict:
    """Header of a Fallout 4 animation .hkx (hk_2014.1.0-r1, 64-bit): duration, frames, frame duration, track counts,
    root motion present, annotations [(time s, text)]. Offsets of hkaAnimation / hkaSplineCompressedAnimation fields
    measured on the 84 robot clips ((frames - 1) * frame duration == duration on all of them)."""
    from .hkpackfile import Packfile
    pf = Packfile(hkx)
    anims = [o for o, c in pf.objects() if c.startswith("hka") and c.endswith("Animation")]
    if not anims:
        raise ValueError("no hkaAnimation object")
    o = anims[0]
    cls = dict(pf.objects())[o]
    typ, dur, ntt, nft = pf.unpack("<ifii", o + 16)

    def cstr(off):
        if off is None:
            return None
        s = pf.data_section.start + off
        return pf.data[s:pf.data.index(b"\0", s)].decode("latin-1")
    notes = []
    ap, ac = pf.array(o + 40)
    for i in range(ac or 0):
        np_, nc = pf.array(ap + 24 * i + 8)
        for j in range(nc or 0):
            tm, = pf.unpack("<f", np_ + 16 * j)
            text = cstr(pf.pointer(np_ + 16 * j + 8))
            if text:
                notes.append((round(tm, 4), text))
    info = {"class": cls, "duration": dur, "transform_tracks": ntt, "float_tracks": nft,
            "root_motion": pf.pointer(o + 32) is not None, "annotations": sorted(notes)}
    if cls == "hkaSplineCompressedAnimation":
        nfr, nbl, _mf, _mq, _bd, _bi, fdur = pf.unpack("<iiiifff", o + 56)
        info.update(frames=nfr, blocks=nbl, frame_duration=fdur)
    return info


# ------------------------------------------------------------------------------------------------ clip mapping
@dataclass(frozen=True)
class ClipMap:
    tag: str                 # Starfield graph tag (the .afx <tag>)
    filename: str            # .af / .afx stem in the Handy clip folder
    fo4: Optional[str]       # Fallout 4 clip under meshes\actors\robot\animations\ (None: no source)
    graph: str = "strafing"  # strafing | furniture
    how: str = "direct"      # direct | reuse | mirror | none
    is_state: int = 0
    add_events: Tuple[Tuple[str, str], ...] = ()   # (where: "start"|"end"|"hit", Starfield event name)
    note: str = ""


_DEATH_EVENTS = (("end", "AddRagdollToWorld"), ("end", "RemoveCharacterControllerFromWorld"))
_KNOCK_EVENTS = (("end", "AddRagdollToWorld"), ("end", "RemoveCharacterControllerFromWorld"))
_TURN_EVENTS = (("end", "SetOrientEnd"),)

# The proposal (doc: docs/actors/robot-animation.md). is_state copies the Mini Bot's .afx for the same tag.
HANDY_CLIP_MAP: Tuple[ClipMap, ...] = (
    # idle
    ClipMap("Idle", "Idle", "Idle.hkx", is_state=1),
    ClipMap("Idle_Flavor01", "Relaxed_Idle_Flavor01", "IdleSearch.hkx", note="14 s look-around"),
    ClipMap("Idle_Flavor02", "Relaxed_Idle_Flavor02", "Idle_ScanHigh.hkx"),
    ClipMap("Idle_Flavor03", "Relaxed_Idle_Flavor03", "Idle_ScanLow.hkx"),
    ClipMap("LookDirections", "LookDirections", None, how="none", is_state=1,
            note="Starfield samples a pose grid; Fallout 4 aimed the eye stalks by head tracking. Needs a built pose clip"),
    # locomotion: Mr. Handy hovers; Fallout 4 has one RunForward and scales it with speed
    ClipMap("WalkForward", "WalkForward", "RunForward.hkx", how="reuse", is_state=1, note="sync foot events not needed"),
    ClipMap("JogForward", "JogForward", "RunForward.hkx", how="reuse", is_state=1),
    ClipMap("RunForward", "RunForward", "RunForward.hkx", is_state=1),
    ClipMap("WalkBackward", "WalkBackward", "RunForward.hkx", how="reuse", is_state=1,
            note="hover body pose is the same; root motion must be rewritten backwards"),
    ClipMap("WalkLeft", "WalkLeft", "RunForward.hkx", how="reuse", is_state=1, note="root motion rewritten sideways"),
    ClipMap("WalkRight", "WalkRight", "RunForward.hkx", how="reuse", is_state=1, note="root motion rewritten sideways"),
    ClipMap("WalkForward_Start", "WalkForward_Start", None, how="none", note="no start clip; graph falls to WalkForward?"),
    ClipMap("WalkForward_Stop", "WalkForward_Stop", None, how="none"),
    ClipMap("RunForward_Start", "RunForward_Start", None, how="none"),
    ClipMap("RunForward_Stop", "RunForward_Stop", None, how="none"),
    ClipMap("TurnInPlace_Left90", "TurnInPlace_Left90", "TurnLeft.hkx", add_events=_TURN_EVENTS),
    ClipMap("TurnInPlace_Left180", "TurnInPlace_Left180", "TurnLeft180.hkx", add_events=_TURN_EVENTS),
    ClipMap("TurnInPlace_Left30", "TurnInPlace_Left30", "TurnLeft.hkx", how="reuse", add_events=_TURN_EVENTS,
            note="crop to the first third or keep 90 deg"),
    ClipMap("TurnInPlace_Right90", "TurnInPlace_Right90", "TurnLeft.hkx", how="mirror", add_events=_TURN_EVENTS),
    ClipMap("TurnInPlace_Right180", "TurnInPlace_Right180", "TurnLeft180.hkx", how="mirror", add_events=_TURN_EVENTS),
    ClipMap("TurnInPlace_Right30", "TurnInPlace_Right30", "TurnLeft.hkx", how="mirror", add_events=_TURN_EVENTS),
    ClipMap("WalkDeparture_Left180", "WalkDeparture_Left180", "TurnLeft180ToMove.hkx", is_state=1),
    ClipMap("RunDeparture_Left180", "RunDeparture_Left180", "TurnLeft180ToMove.hkx", how="reuse", is_state=1),
    ClipMap("WalkDeparture_Right180", "WalkDeparture_Right180", "TurnLeft180ToMove.hkx", how="mirror", is_state=1),
    ClipMap("RunDeparture_Right180", "RunDeparture_Right180", "TurnLeft180ToMove.hkx", how="mirror", is_state=1),
    ClipMap("WalkDeparture_Left90", "WalkDeparture_Left90", None, how="none", is_state=1),
    ClipMap("WalkDeparture_Right90", "WalkDeparture_Right90", None, how="none", is_state=1),
    ClipMap("RunDeparture_Left90", "RunDeparture_Left90", None, how="none", is_state=1),
    ClipMap("RunDeparture_Right90", "RunDeparture_Right90", None, how="none", is_state=1),
    ClipMap("JumpRunForwardFall", "JumpRunForwardFall", "Idle.hkx", how="reuse", note="hovers: no fall pose"),
    ClipMap("JumpRunForwardFallLoop", "JumpRunForwardFallLoop", "Idle.hkx", how="reuse", is_state=1),
    # combat
    ClipMap("MeleeAttack01", "MeleeAttack01", "Claw\\Attack_1.hkx", note="Fallout 4 picks Claw or SawBlade by weapon"),
    ClipMap("MeleeAttack02", "MeleeAttack02", "Claw\\Attack_2.hkx"),
    ClipMap("MeleeAttackPower01", "MeleeAttackPower01", "Claw\\Attack_3.hkx"),
    ClipMap("MeleeAttack_Claw01", "MeleeAttack_Claw01", "SawBlade\\Attack_1.hkx"),
    ClipMap("MeleeAttack_Claw02", "MeleeAttack_Claw02", "SawBlade\\Attack_2.hkx"),
    ClipMap("MeleeAttackPower_Claw01", "MeleeAttackPower_Claw01", "SawBlade\\Attack_3.hkx"),
    ClipMap("FireSingle_Mouth1", "FireSingle_Mouth1", "RightArmSingleFire.hkx",
            note="weaponFire.0 -> WeaponFire; FO4 fires from 5 mounts, Starfield has 3 FireSingle tags"),
    ClipMap("FireSingle_Mouth2", "FireSingle_Mouth2", "LeftArmSingleFire.hkx"),
    ClipMap("FireSingle_Tail", "FireSingle_Tail", "RightShoulderSingleFire.hkx"),
    ClipMap("DodgeLeft", "DodgeLeft", "DodgeLeft.hkx"),
    ClipMap("DodgeRight", "DodgeRight", "DodgeRight.hkx"),
    ClipMap("EvadeLeft", "EvadeLeft", "DodgeLeft.hkx", how="reuse"),
    ClipMap("EvadeRight", "EvadeRight", "DodgeRight.hkx", how="reuse"),
    # hit reactions
    ClipMap("StaggerForward", "StaggerForward", "StaggerForwardMedium.hkx"),
    ClipMap("StaggerBackwardSmall", "StaggerBackwardSmall", "StaggerSmall.hkx"),
    ClipMap("StaggerBackwardMedium", "StaggerBackwardMedium", "StaggerMedium.hkx"),
    ClipMap("StaggerBackwardLarge", "StaggerBackwardLarge", "StaggerLarge.hkx"),
    ClipMap("StaggerLeft", "StaggerLeft", "StaggerMedium.hkx", how="reuse", note="no side stagger in Fallout 4"),
    ClipMap("StaggerRight", "StaggerRight", "StaggerMedium.hkx", how="reuse"),
    ClipMap("Flinch_Head01", "Flinch_Head01", "HitReactionMidEye.hkx"),
    ClipMap("Flinch_Head02", "Flinch_Head02", "HitReactionLeftEye.hkx"),
    ClipMap("Flinch_Torso01", "Flinch_Torso01", "HitReactionThruster.hkx"),
    ClipMap("Flinch_Torso02", "Flinch_Torso02", "HitReactionRightEye.hkx"),
    ClipMap("Flinch_LeftArm", "Flinch_LeftArm", "HitReactionLeftArm.hkx"),
    ClipMap("Flinch_RightArm", "Flinch_RightArm", "HitReactionRightArm.hkx"),
    ClipMap("Flinch_LeftArm2", "Flinch_LeftArm2", "HitReactionMidArm.hkx"),
    # death, knockdown, getup
    ClipMap("Death_Backward01", "Death_Backward01", "Death1.hkx", is_state=1, add_events=_DEATH_EVENTS),
    ClipMap("Death_Forward01", "Death_Forward01", "Death2.hkx", is_state=1, add_events=_DEATH_EVENTS),
    ClipMap("Death_Left01", "Death_Left01", "Death3.hkx", is_state=1, add_events=_DEATH_EVENTS),
    ClipMap("Death_Right01", "Death_Right01", "Death3.hkx", how="mirror", is_state=1, add_events=_DEATH_EVENTS),
    ClipMap("Death_Moving_Forward01", "Death_Moving_Forward01", "Death2.hkx", how="reuse", is_state=1,
            add_events=_DEATH_EVENTS),
    ClipMap("Knockdown", "Knockdown_Backward", "ToUnconscious.hkx", add_events=_KNOCK_EVENTS),
    ClipMap("GetUp_Back", "GetUp_Back", "UnconsciousToConscious.hkx"),
    ClipMap("GetUp_Front", "GetUp_Front", "UnconsciousToConscious.hkx", how="reuse"),
    ClipMap("GetUp_Right", "GetUp_Right", "GetUpRight.hkx"),
    ClipMap("GetUp_Left", "GetUp_Left", "GetUpRight.hkx", how="mirror"),
    ClipMap("TunnelStart", "TunnelStart", None, how="none", note="burrowing; never used by a Handy"),
    ClipMap("TunnelStop", "TunnelStop", None, how="none"),
)

# Fallout 4 clips the generic Starfield creature graphs cannot express (kept for later graph or script work).
FO4_NOT_EXPRESSIBLE = {
    "RightArmAutoFire.hkx": "automatic fire per mount (weaponFire.0..5 picks the arm/shoulder/head); Creature_Actions "
                            "only has FireSingle_Mouth1/Mouth2/Tail",
    "LeftArmAutoFire.hkx": "as above", "RightShoulderAutoFire.hkx": "as above",
    "LeftShoulderAutoFire.hkx": "as above", "HeadAutoFire.hkx": "as above",
    "LeftShoulderSingleFire.hkx": "fifth fire mount; no free FireSingle tag",
    "FlameThrower\\RangedAttack_1.hkx": "5.6 s held flamethrower stream: no hold/loop fire state in Creature_Actions",
    "FlameThrower\\RangedAttackSingleFire_1.hkx": "flamethrower burst; would need FireSingle_* and a flame weapon",
    "Claw\\Recoil_1.hkx": "melee recoil (blocked hit): Creature_Melee has no recoil tag",
    "SawBlade\\Recoil_1.hkx": "as above",
    "RotateRingCW_Add.hkx": "additive ring spin layered by HandyBehavior; Starfield graph has no additive layer for it",
    "RotateRingCCW_Add.hkx": "as above",
    "Idle_EyeFocus.hkx": "7-track partial (eye stalks only) layered on idle",
    "StaggerForwardSmall.hkx": "spare: only one StaggerForward tag",
    "Injured\\Idle.hkx": "crippled-thruster set: needs Creature_LimbCripple tags and an Injured SAPT",
    "Injured\\RunForward.hkx": "as above", "InjuredArmIdle.hkx": "as above",
    "DialogueIdle_Short1.hkx": "talking idles: Starfield dialogue on a creature graph not checked",
    "DialogueIdle_Short2.hkx": "as above", "DialogueIdle_Medium1.hkx": "as above", "DialogueIdle_Medium2.hkx": "as above",
    "DialogueIdle_Long1.hkx": "as above", "DialogueIdle_Long2.hkx": "as above",
    "GiveFood.hkx": "scene idles with props (AnimObjLoad/Draw); need IDLE records + Starfield anim objects",
    "GetFood.hkx": "as above", "GiveHolotape.hkx": "as above", "GivePurifiedWater.hkx": "as above",
    "GiveStimpak.hkx": "as above", "Idle_BabyRattle.hkx": "as above", "Idle_CoffePot.hkx": "as above",
    "Idle_Dusting.hkx": "as above", "Idle_GardeningTablePlot_1.hkx": "as above",
    "Idle_GardeningTablePlot_2.hkx": "as above", "Idle_Maintenance.hkx": "as above", "Idle_Welding.hkx": "as above",
    "SawingIdle.hkx": "as above", "PickUp_Low.hkx": "as above", "PickUp_Medium.hkx": "as above",
    "FurnitureBar\\EnterFromStand.hkx": "furniture: needs FURN records + Furniture.agx keyword rows",
    "FurnitureBar\\ExitToStand.hkx": "as above", "FurnitureBar\\PoseA_Idle1.hkx": "as above",
    "FurnitureBar\\PoseA_IdleFlavor1.hkx": "as above",
    "FurnitureWashingDishes\\EnterFromStand.hkx": "as above", "FurnitureWashingDishes\\LeftExitToStand.hkx": "as above",
    "FurnitureWashingDishes\\PoseA_Idle1.hkx": "as above",
    "OnVertibird\\EnterFromStand.hkx": "vertibird riding: no vertibirds", "OnVertibird\\ExitToStand.hkx": "as above",
    "OnVertibird\\PoseA_Idle1.hkx": "as above",
}

FO4_EVENT_MAP = {"preHitFrame": "preHitFrame", "weaponSwing": "weaponSwing", "HitFrame": "HitFrame"}


def sf_event(fo4_name: str) -> Optional[str]:
    """Starfield gameplay event for a Fallout 4 annotation (None: drop; SoundPlay.* becomes foley work, not an event)."""
    if fo4_name in FO4_EVENT_MAP:
        return FO4_EVENT_MAP[fo4_name]
    if fo4_name.lower().startswith("weaponfire"):
        return "WeaponFire"
    return None


# ------------------------------------------------------------------------------------------------ paths of the new race
@dataclass
class HandyPaths:
    """Paths written into the records (relative to Data\\Meshes, as Starfield's own). Change them here only."""
    skeleton_nif: str = "FO4SF\\Actors\\Handy\\CharacterAssets\\skeleton.nif"           # ANAM
    skeleton_rig: str = "FO4SF\\Actors\\Handy\\CharacterAssets\\skeleton.rig"           # NAM5
    skeleton_ref: str = "FO4SF\\Actors\\Handy\\CharacterAssets\\skeleton_ref.nif"       # BPTD MODL / NAM4 / ENAM / FNAM
    clips: str = "Actors\\FO4SF\\Handy\\Animations"                                     # DNAM + SAPT

    @property
    def furniture_clips(self):
        return self.clips + "\\Furniture"

    def subgraphs(self) -> List[Tuple[str, List[str]]]:
        """(graph, folders) of every SGNM of the Handy race, in record order (mirrors the Mini Bot's two)."""
        return [(STRAFING_GRAPH, [self.clips]), (FURNITURE_GRAPH, [self.furniture_clips, self.clips])]


# Mini Bot part -> Handy bone, from Fallout 4's own MrHandyBodyPartData (0004B368): its parts target Chest, Pelvis,
# SPINE2, Arm1|0..2, EyeArm3|0..2 and Root.
BONE_MAP = {"C_Chassis": "Chest", "C_Base": "Pelvis", "C_Axle": "Pelvis", "C_Arm1": "Arm1|0", "C_Body": "Spine2",
            "COM": "COM", "Root": "Root"}
EXTRA_PARTS = (("C_Arm1", "Arm1|1"), ("C_Arm1", "Arm1|2"),
               ("C_Arm1", "EyeArm3|0"), ("C_Arm1", "EyeArm3|1"), ("C_Arm1", "EyeArm3|2"))


# ------------------------------------------------------------------------------------------------ records
def load_minibot(esm_path: str) -> Tuple[esm.Record, esm.Record]:
    race = bptd = None
    with esm.Plugin(esm_path) as p:
        for r in p.records("RACE"):
            if r.formid == MINIBOT_RACE:
                race = r
                break
        for r in p.records("BPTD"):
            if r.formid == MINIBOT_BPTD:
                bptd = r
                break
    if race is None or bptd is None:
        raise esm.EsmError("MiniBotARace / MiniBotABodyPartData not found")
    return race, bptd


def _is_text(d: bytes) -> bool:
    return len(d) > 1 and d[-1:] == b"\0" and all(32 <= x < 127 for x in d[:-1])


def dump_record(rec: esm.Record) -> List[str]:
    out = [f"{rec.sig.decode()} {rec.formid:08X} {rec.edid} flags=0x{rec.flags:x} version={rec.version}"]
    for i, (s, d) in enumerate(rec.subs):
        out.append(f"{i:3d} {s.decode()} {len(d):5d} {esm.zstring(d) if _is_text(d) else d[:64].hex()}")
    return out


def _part_blocks(subs):
    """Split BPTD subrecords into (head, [part blocks]); a part starts at BPTN."""
    head, parts = [], []
    for s, d in subs:
        if s == b"BPTN":
            parts.append([(s, d)])
        elif parts:
            parts[-1].append((s, d))
        else:
            head.append((s, d))
    return head, parts


def build_bptd(src: esm.Record, formid: int, paths: HandyPaths, bone_map: Dict[str, str] = None,
               extra_parts=EXTRA_PARTS, edid: str = HANDY_BPTD_EDID) -> esm.Record:
    """MiniBotABodyPartData with the Handy skeleton_ref and bones. BPTN (part names) are localized string ids in
    Starfield.esm; our plugin is not localized, so they become plain names (the Handy bone)."""
    bone_map = dict(BONE_MAP if bone_map is None else bone_map)
    head, parts = _part_blocks(src.subs)
    new_head = []
    for s, d in head:
        if s == b"EDID":
            d = esm.zbytes(edid)
        elif s == b"MODL":
            d = esm.zbytes(paths.skeleton_ref)
        new_head.append((s, d))

    def convert(block, override=None):
        out = []
        part = esm.zstring(dict(block).get(b"BPNN", b"\0"))
        bone = override or bone_map.get(part, part)
        for s, d in block:
            if s == b"BPTN":
                d = esm.zbytes(bone)
            elif s in (b"BPNN", b"BPNT"):
                d = esm.zbytes(override or bone_map.get(esm.zstring(d), esm.zstring(d)))
            elif s in (b"NAM4", b"ENAM", b"FNAM") and _is_text(d):
                t = esm.zstring(d)
                if t.lower().endswith("skeleton_ref.nif"):
                    prefix = t.split(" ", 1)[0] + " " if " " in t else ""
                    d = esm.zbytes(prefix + "Meshes\\" + paths.skeleton_ref)
                else:
                    d = esm.zbytes(bone_map.get(t, t))
            out.append((s, d))
        return out
    new_parts = [convert(b) for b in parts]
    by_name = {esm.zstring(dict(b).get(b"BPNN", b"\0")): b for b in parts}
    for template, bone in extra_parts or ():
        new_parts.append(convert(by_name[template], override=bone))
    subs = new_head + [x for b in new_parts for x in b]
    return esm.Record(b"BPTD", formid, subs, src.flags & ~esm.COMPRESSED, src.vc, src.version, src.unknown)


def build_race(src: esm.Record, formid: int, bptd_formid: int, paths: HandyPaths, name: str = "Mr. Handy",
               edid: str = HANDY_EDID, bone_map: Dict[str, str] = None) -> esm.Record:
    """MiniBotARace with: EDID, the three localized name fields as plain strings (FULL, DESC, SNAM: consecutive string
    ids 0x1ED1/0x1ECF/0x1ED0 in Starfield.esm), GNAM -> our BPTD, ANAM/NAM5/DNAM/every SAPT -> the Handy folders, and
    ZNAM bone names (C_Chassis) -> the Handy bone. Every other subrecord is kept byte for byte."""
    bone_map = dict(BONE_MAP if bone_map is None else bone_map)
    graphs = paths.subgraphs()
    subs, sg_i, sapt_i = [], -1, 0
    for s, d in src.subs:
        if s == b"EDID":
            d = esm.zbytes(edid)
        elif s == b"FULL" or s == b"SNAM":
            d = esm.zbytes(name)
        elif s == b"DESC":
            d = esm.zbytes("")
        elif s == b"GNAM":
            d = struct.pack("<I", bptd_formid)
        elif s == b"ANAM" and _is_text(d):
            d = esm.zbytes(paths.skeleton_nif)
        elif s == b"NAM5":
            d = esm.zbytes(paths.skeleton_rig)
        elif s == b"DNAM" and _is_text(d):
            d = esm.zbytes(paths.clips)
        elif s == b"ZNAM" and _is_text(d):
            d = esm.zbytes(bone_map.get(esm.zstring(d), esm.zstring(d)))
        elif s == b"SGNM":
            sg_i += 1
            sapt_i = 0
            if sg_i >= len(graphs) or graphs[sg_i][0].lower() != esm.zstring(d).lower():
                raise esm.EsmError(f"unexpected sub-graph {esm.zstring(d)!r} (template changed?)")
        elif s == b"SAPT":
            folders = graphs[sg_i][1]
            if sapt_i >= len(folders):
                raise esm.EsmError("more SAPT than expected")
            d = esm.zbytes(folders[sapt_i])
            sapt_i += 1
        subs.append((s, d))
    return esm.Record(b"RACE", formid, subs, src.flags & ~esm.COMPRESSED, src.vc, src.version, src.unknown)


def race_subgraph_sets(race: esm.Record) -> List[Tuple[str, List[str]]]:
    """(graph, folders) for the root (NAM6 with no folders: key high word 0) and every SGNM of a RACE record."""
    out = []
    root = race.get(b"NAM6")
    if root is not None:
        out.append((esm.zstring(root), []))
    cur = None
    for s, d in race.subs:
        if s == b"SGNM":
            cur = (esm.zstring(d), [])
            out.append(cur)
        elif s == b"SAPT" and cur is not None:
            cur[1].append(esm.zstring(d))
    return out


# ------------------------------------------------------------------------------------------------ manifests for a race
def race_manifests(race_edid: str, paths: HandyPaths, clip_map: Sequence[ClipMap] = HANDY_CLIP_MAP,
                   fo4_info: Optional[Dict[str, dict]] = None, generated_rows=()) -> Dict[str, bytes]:
    """{archive path under Data: bytes} for the Handy race: per sub-graph animationfiledata, animationoffsets,
    dynamicidledata, plus generatedsubgraphdata/<edid>.txt. Clips with how == "none" are left out. animationoffsets
    carries tag/clip records only for clips with gameplay events (melee hit frames, WeaponFire), as the Mini Bot's; it
    needs fo4_info (fo4_clip_info per Fallout 4 clip name) for durations and event times, else it is the minimal form.
    animationstancedata is NOT written (pose unknown; stance_data() writes the layout once the pose is known)."""
    out = {}
    base = "Meshes\\AnimTextData\\"
    usable = [c for c in clip_map if c.how != "none"]
    for graph, folders in paths.subgraphs():
        key = manifest_key(graph, folders)
        which = "furniture" if graph == FURNITURE_GRAPH else "strafing"
        if which == "furniture":
            chosen = [c for c in usable if c.tag == "Idle" or c.tag.startswith("Idle_Flavor")]
        else:
            chosen = [c for c in usable if c.graph == "strafing"]
        clips = [clip_path(paths.clips, c.filename + ".af") for c in chosen]
        out[base + f"AnimationFileData\\{key}.txt"] = animation_file_data(key, clips)
        out[base + f"DynamicIdleData\\{key}.txt"] = dynamic_idle_data()
        tags, recs = [], []
        if fo4_info and which == "strafing":
            for c in chosen:
                info = fo4_info.get(c.fo4)
                if not info:
                    continue
                evs = [(t, sf_event(n)) for t, n in info["annotations"] if sf_event(n)]
                if not evs:
                    continue
                p = clip_path(paths.clips, c.filename)
                tags.append((c.tag, p))
                recs.append(OffsetClip(p, info["duration"], sorted(set(evs))))
        out[base + f"AnimationOffsets\\{key}.txt"] = animation_offsets(graph, tags, recs)
    out[base + f"GeneratedSubgraphData\\{race_edid.lower()}.txt"] = generated_subgraph_data(generated_rows)
    return out


def write_files(files: Dict[str, bytes], root: str) -> List[str]:
    written = []
    for rel, data in files.items():
        p = os.path.join(root, *rel.split("\\"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
        written.append(p)
    return written


def afx_specs(clip_map: Sequence[ClipMap], fo4_info: Dict[str, dict], fps: float = 30.0) -> Dict[str, dict]:
    """Per Handy clip: tag, is_state, events by frame (Fallout 4 gameplay annotations mapped, plus add_events) and the
    Fallout 4 sound annotations to turn into foley. For the clip builder."""
    out = {}
    for c in clip_map:
        if c.how == "none":
            continue
        info = fo4_info.get(c.fo4, {})
        dur = info.get("duration", 0.0)
        last = int(round(dur * fps))
        evs = [(int(round(t * fps)), sf_event(n)) for t, n in info.get("annotations", []) if sf_event(n)]
        for where, name in c.add_events:
            evs.append((last if where == "end" else 0, name))
        sounds = [(int(round(t * fps)), n.split(".", 1)[1]) for t, n in info.get("annotations", [])
                  if n.startswith("SoundPlay.")]
        out[c.filename] = {"tag": c.tag, "is_state": c.is_state, "fo4": c.fo4, "how": c.how, "duration": dur,
                           "frames": last + 1 if info else None, "events": sorted(set(evs)), "fo4_sounds": sounds,
                           "note": c.note}
    return out


# ------------------------------------------------------------------------------------------------ command line
def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Build FO4SF_HandyRace + BPTD and the animation manifests.")
    ap.add_argument("--starfield", default=r"D:\SteamLibrary\steamapps\common\Starfield\Data")
    ap.add_argument("--fallout4", default=r"D:\SteamLibrary\steamapps\common\Fallout 4\Data")
    ap.add_argument("--out", default=r"D:\FO4SF-Owner-Tests\robot-anim\D")
    a = ap.parse_args(argv)
    from .ba2 import Ba2
    os.makedirs(a.out, exist_ok=True)
    race, bptd = load_minibot(os.path.join(a.starfield, "Starfield.esm"))
    with open(os.path.join(a.out, "minibot_records.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(dump_record(race) + [""] + dump_record(bptd)) + "\n")
    fo4 = Ba2(os.path.join(a.fallout4, "Fallout4 - Animations.ba2"))
    info = {}
    for n in fo4.names:
        nn = n.replace("/", "\\")
        low = nn.lower()
        if low.startswith("meshes\\actors\\robot\\animations\\") and low.endswith(".hkx"):
            rel = nn[len("meshes\\actors\\robot\\animations\\"):]
            info[rel] = fo4_clip_info(fo4.read(n))
            info[rel]["path"] = nn
    # match the map's spelling (case-insensitive)
    by_low = {k.lower(): v for k, v in info.items()}
    info_map = {c.fo4: by_low[c.fo4.lower()] for c in HANDY_CLIP_MAP if c.fo4}
    with open(os.path.join(a.out, "fo4_handy_clips.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, indent=1)
    paths = HandyPaths()
    w = esm.PluginWriter(["Starfield.esm"], author="FO4SF", description="FO4SF Mr. Handy race test (robot-anim D)")
    bptd_new = w.add(build_bptd(bptd, w.own(0x801), paths))
    race_new = w.add(build_race(race, w.own(0x800), bptd_new.formid, paths))
    w.write(os.path.join(a.out, "FO4SF_HandyRace.esm"))
    with open(os.path.join(a.out, "handy_records.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(dump_record(race_new) + [""] + dump_record(bptd_new)) + "\n")
    files = race_manifests(HANDY_EDID, paths, fo4_info=info_map)
    written = write_files(files, os.path.join(a.out, "Data"))
    specs = afx_specs(HANDY_CLIP_MAP, info_map)
    with open(os.path.join(a.out, "handy_afx_specs.json"), "w", encoding="utf-8") as f:
        json.dump(specs, f, indent=1)
    keys = {g: manifest_key(g, fs) for g, fs in paths.subgraphs()}
    print(json.dumps({"race": f"{race_new.formid:08X}", "bptd": f"{bptd_new.formid:08X}",
                      "keys": {g: str(k) for g, k in keys.items()}, "manifests": written,
                      "unmapped_fo4": sorted({k.lower() for k in info} - {c.fo4.lower() for c in HANDY_CLIP_MAP if c.fo4}
                                             - {k.lower() for k in FO4_NOT_EXPRESSIBLE})}, indent=1))


if __name__ == "__main__":
    main()
