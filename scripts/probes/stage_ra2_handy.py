"""stage_ra2_handy.py: probe bundle "RA2 Handy" (robot-anim task E). It integrates the decoder (A, fo4sf.hkanim), the
actor rig/clip writer (B, fo4sf.actor_anim), the skinned mesh (C, scripts/actors/convert_handy.py) and the race and clip
mapping (D, fo4sf.handy_race) into one bundle for an in-game test that the lead runs.

    python scripts/probes/stage_ra2_handy.py build     [--out D:\\FO4SF-Owner-Tests\\robot-anim\\E] [--mesh parts|mrhandy]
                                                       [--compare-with <earlier bundle>]   (writes <out>\\CHANGES.md)
    python scripts/probes/stage_ra2_handy.py verify    [--stage-dir ...]
    python scripts/probes/stage_ra2_handy.py deform    [--stage-dir ...]     edge stretch, every clip and frame
    python scripts/probes/stage_ra2_handy.py compare   --old <bundle> --new <bundle>   model-space bone positions
    python scripts/probes/stage_ra2_handy.py install   --starfield <game dir> [--stage-dir ...] [--plugins-txt ...]
    python scripts/probes/stage_ra2_handy.py uninstall --starfield <game dir> [--plugins-txt ...]
    python scripts/probes/stage_ra2_handy.py status    --starfield <game dir>

Robot-anim fix (23 Nov 2026, bundle E2): the rig rebases COM, Pelvis and C-ModSlotB|0..2 to an identity rest rotation
(convert_handy.REBASE; clips are decoded in skeleton.hkx's frames and mapped once, rebase_frames), renames every bone
to letters, digits and '_' (Arm1|0 -> Arm1_0), adds DirectAt (map key 137) on COM, and the mesh is built from
Codsworth's own Fallout 4 robot parts (convert_handy.convert_parts) instead of mrhandy.nif.

build writes, under <out>:
  Data\\                         the loose files, in the folder layout the records point at (Data-relative)
    meshes\\fo4sf\\actors\\handy\\handy.nif, characterassets\\skeleton.nif, skeleton_ref.nif, geometries\\*.mesh  (C)
    Meshes\\FO4SF\\Actors\\Handy\\CharacterAssets\\skeleton.rig                     Handy rig (112 bones, from skeleton.hkx)
    Meshes\\Actors\\FO4SF\\Handy\\Animations\\<clip>.af + .afx                       every mapped clip of D's HANDY_CLIP_MAP
    Meshes\\AnimTextData\\...                                                     D's Handy manifests + the own-folder ones
    Meshes\\FO4SF\\Actors\\RA2MiniBot\\CharacterAssets\\skeleton.rig                byte copy of the vanilla Mini Bot rig
    Meshes\\Actors\\FO4SF\\RA2MiniBot\\Animations\\...                              byte copies of the 55 vanilla .af/.afx
  FO4SF_RA2Handy.esm             master Starfield.esm only (records: FORMS below)
  FO4SF_RA2Handy - Main.ba2      every file under Data (GNRL, uncompressed; Archive2.exe when present)
  bat\\ra2a.txt ra2b.txt ra2c.txt  console batch files with an XX load-order placeholder (install stamps real copies)
  report.json, manifest.json     measurements; SHA-256 and size of every staged file
  work\\                          vanilla Mini Bot clips read for their root speeds, mesh conversion report

Conversion rules (measured: see report.json "conventions"): Fallout 4 and Starfield are both Z up, +Y forward, so no
axis change; FO4 units x 1/70 = metres; 30 fps in and out; root motion comes from the clip's
hkaDefaultAnimatedReferenceFrame (x, y, z, yaw in radians about +Z, cumulative) and is written as the Root bone's track
(rest identity) plus the header copy (actor_anim.write_clip). The rig bind is skeleton.hkx's reference pose except
Pelvis = (0, 0, 0) on COM (every clip holds it there; so does mrhandy.nif) and Root = identity; the mesh is rebuilt with
the same bind (convert_handy.convert(bind_overrides=...)).

install / uninstall never run as part of build; Starfield must not be running (fo4sf.launcher.crashwatch.System.pids).
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
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
for _p in (str(REPO / "src"), str(REPO / "scripts" / "actors")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fo4sf import actor_anim as aa  # noqa: E402
from fo4sf import handy_race as hr  # noqa: E402
from fo4sf import hkanim  # noqa: E402
from fo4sf.ba2 import Ba2  # noqa: E402
from fo4sf.planet import esm  # noqa: E402

STARFIELD_DIR = Path(r"D:\SteamLibrary\steamapps\common\Starfield")
FO4_DATA = Path(r"D:\SteamLibrary\steamapps\common\Fallout 4\Data")
OUT = Path(r"D:\FO4SF-Owner-Tests\robot-anim\E")
GAME_LIBRARY = Path(r"D:\SteamLibrary")

PROBE = "ra2-handy"
PLUGIN = "FO4SF_RA2Handy.esm"
MAIN_BA2 = "FO4SF_RA2Handy - Main.ba2"
RECEIPT = "FO4SF_RA2Handy.install.json"
MATERIALS_PLUGIN = "FO4ActorRaider.esm"      # its Main.ba2 holds the Handy .mat and textures (current Codsworth's)
UNIT = 1.0 / 70.0
FPS = 30.0
DEFAULT_MIN_FREE_GB = 20.0

# ---- form ids (local; the plugin's own index is 01 with one master; in game XX = load-order slot)
F_RACE_HANDY, F_BPTD_HANDY, F_ARMA_HANDY, F_ARMO_HANDY, F_NPC_HANDY = 0x800, 0x801, 0x802, 0x803, 0x804
F_RACE_REN, F_ARMA_REN, F_ARMO_REN, F_NPC_REN = 0x805, 0x806, 0x807, 0x808
F_RACE_OWN, F_ARMA_OWN, F_ARMO_OWN, F_NPC_OWN = 0x809, 0x80A, 0x80B, 0x80C
EDIDS = {
    F_RACE_HANDY: hr.HANDY_EDID, F_BPTD_HANDY: hr.HANDY_BPTD_EDID, F_ARMA_HANDY: "FO4SF_RA2Handy_AA",
    F_ARMO_HANDY: "FO4SF_RA2Handy_Skin", F_NPC_HANDY: "FO4SF_RA2HandyTest",
    F_RACE_REN: "FO4SF_RA2MiniBotRenamedRace", F_ARMA_REN: "FO4SF_RA2MiniBotRenamed_AA",
    F_ARMO_REN: "FO4SF_RA2MiniBotRenamed_Skin", F_NPC_REN: "FO4SF_RA2MiniBotRenamed",
    F_RACE_OWN: "FO4SF_RA2MiniBotOwnFolderRace", F_ARMA_OWN: "FO4SF_RA2MiniBotOwnFolder_AA",
    F_ARMO_OWN: "FO4SF_RA2MiniBotOwnFolder_Skin", F_NPC_OWN: "FO4SF_RA2MiniBotOwnFolder",
}
NPC_NAMES = {F_NPC_HANDY: "Mr. Handy (test)", F_NPC_REN: "Mini Bot (renamed race test)",
             F_NPC_OWN: "Mini Bot (own folder test)"}
BATS = {"ra2a.txt": (F_NPC_HANDY, "Mr. Handy (test): own Fallout 4 rig, mesh and clips"),
        "ra2b.txt": (F_NPC_REN, "garden Mini Bot on a renamed copy of its race (Codsworth's case)"),
        "ra2c.txt": (F_NPC_OWN, "garden Mini Bot on a race copy whose rig and clips sit in a plugin folder")}

# ---- Starfield sources
SF_NPC_GARDEN = 0x0004297C        # OutpostRobotMiniBotA_Garden
SF_ARMA_GARDEN = 0x00081886       # AA_MiniBotA_Gardening (dotnet/Mission/Program.cs MiniBotArmaId)
SF_ARMO_GARDEN = 0x003FFD3A       # Skin_MiniBotA_Gardening (MiniBotSkinId)
ACBS_ESSENTIAL = 0x2              # set on the garden bot, absent on every killable EncMiniBotA0x (measured)
AGGRESSION_VERY_AGGRESSIVE = 2    # AIDT byte 0: attacks enemies and neutrals on sight
CONFIDENCE_FOOLHARDY = 4          # AIDT byte 1
HANDY_OBND = (-0.65, -0.65, 0.0, 0.65, 0.65, 1.80)   # as the current Codsworth record (Program.cs)

# ---- paths written into records (relative to Data\Meshes, as Starfield's own)
HANDY = hr.HandyPaths()
HANDY_MODEL = "FO4SF\\Actors\\Handy\\handy.nif"                      # convert_handy.OUT_MESH below meshes\
VAN_CLIPS = "Actors\\MiniBotA\\Animations"
OWN_RIG = "FO4SF\\Actors\\RA2MiniBot\\CharacterAssets\\skeleton.rig"
OWN_CLIPS = "Actors\\FO4SF\\RA2MiniBot\\Animations"
VAN_PREFIX = "meshes/actors/minibota/"
FO4_ROBOT = "meshes\\actors\\robot\\"

# ---- clip conversion choices
BIND_OVERRIDES_FO4 = {"Root": (0.0, 0.0, 0.0), "Pelvis": (0.0, 0.0, 0.0)}
# vanilla Mini Bot rig map keys; DirectAt (137, look-at / aim; 26 of 29 vanilla actor rigs) is the bone
# convert_handy.EXTRA_BONES adds where the Mini Bot has it (on COM, unturned)
RIG_KEYS = {"Root": 0, "COM": 9, "DirectAt": 137}
MESH_SOURCES = ("parts", "mrhandy")             # parts: Codsworth's Fallout 4 robot parts (default); mrhandy: the old mesh
LOCOMOTION_FROM_MINIBOT = {"WalkForward": "walkforward", "JogForward": "jogforward", "RunForward": "runforward",
                           "WalkBackward": "walkbackward", "WalkLeft": "walkleft", "WalkRight": "walkright"}
TURN_CROP_DEG = {"TurnInPlace_Left90": 90.0, "TurnInPlace_Left30": 30.0,
                 "TurnInPlace_Right90": 90.0, "TurnInPlace_Right30": 30.0}
REQUIRED_TAGS = ("Idle", "WalkForward", "RunForward", "TurnInPlace_Left90", "TurnInPlace_Right90", "MeleeAttack01",
                 "StaggerBackwardMedium", "Death_Backward01")

P3_FORBIDDEN_RE = re.compile(r"[mnvMNV]")
STRIPPED_EDID_RE = re.compile(r"\bFO4SF_[A-Za-z0-9_]+", re.I)


class Ra2Error(ValueError):
    pass


# =============================================================================================== small helpers
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_out_dir(out: Path) -> Path:
    out = Path(out).resolve()
    for forbidden, what in ((REPO.resolve(), "the repository"), (GAME_LIBRARY, "the game library")):
        f = os.path.normcase(str(forbidden))
        o = os.path.normcase(str(out))
        if o == f or o.startswith(f + os.sep):
            raise Ra2Error(f"refusing to write the bundle inside {what}: {out}")
    if "candidate-" in os.path.normcase(str(out)):
        raise Ra2Error(f"refusing to write into a candidate-* folder: {out}")
    return out


def check_starfield_not_running() -> None:
    from fo4sf.launcher.crashwatch import GAME_EXE, System
    pids = System.pids(GAME_EXE)
    if pids:
        raise Ra2Error(f"refused while {GAME_EXE} is running (pids={pids})")


def check_free_space_gb(path: Path, min_free_gb: float) -> float:
    probe = Path(path)
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    free = round(shutil.disk_usage(probe).free / 1024 ** 3, 2)
    if free < min_free_gb:
        raise Ra2Error(f"free space {free} GiB < {min_free_gb} GiB on {probe}")
    return free


def yaw_quat(yaw: float) -> tuple:
    return (0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _mvec(v):
    """Reflection through the YZ plane (x -> -x): left <-> right."""
    return (-v[0], v[1], v[2])


def _mquat(q):
    """The rotation M R M of a reflection M = diag(-1, 1, 1): axis (x, y, z) -> (x, -y, -z), same angle."""
    return (q[0], -q[1], -q[2], q[3])


def world_of(parents: Sequence[int], local: Sequence[tuple]) -> List[tuple]:
    out = []
    for i, (t, q) in enumerate(local):
        p = parents[i]
        if p < 0:
            out.append((tuple(t), aa.q_norm(q)))
        else:
            pt, pq = out[p]
            out.append((_add(pt, aa.q_rotate(pq, t)), aa.q_norm(aa.q_mul(pq, q))))
    return out


def local_of(parents: Sequence[int], world: Sequence[tuple]) -> List[tuple]:
    out = []
    for i, (t, q) in enumerate(world):
        p = parents[i]
        if p < 0:
            out.append((tuple(t), aa.q_norm(q)))
        else:
            pt, pq = world[p]
            inv = aa.q_conj(pq)
            out.append((aa.q_rotate(inv, _sub(t, pt)), aa.q_norm(aa.q_mul(inv, q))))
    return out


# =============================================================================================== left / right
def pair_name(name: str) -> str:
    """The mirror partner of a Handy bone: |1 <-> |2 (right / left arm and eye chains; |0 is the front one, its own
    partner), L<Upper> <-> R<Upper>, ...Left... <-> ...Right...; every other bone is its own partner."""
    if name.endswith("|1"):
        return name[:-1] + "2"
    if name.endswith("|2"):
        return name[:-1] + "1"
    m = re.match(r"^([LR])([A-Z].*)$", name)
    if m:
        return ("R" if m.group(1) == "L" else "L") + m.group(2)
    if "Left" in name:
        return name.replace("Left", "Right")
    if "Right" in name:
        return name.replace("Right", "Left")
    return name


def pair_indices(names: Sequence[str], parents: Sequence[int]) -> List[int]:
    idx = {n: i for i, n in enumerate(names)}
    out = []
    for i, n in enumerate(names):
        p = pair_name(n)
        if p not in idx:
            raise Ra2Error(f"bone {n}: mirror partner {p} is not in the skeleton")
        out.append(idx[p])
    for j, i in enumerate(out):
        pj, pi = parents[j], parents[i]
        if (pj < 0) != (pi < 0) or (pj >= 0 and out[pj] != pi):
            raise Ra2Error(f"bone {names[j]}: its partner {names[i]} hangs under a bone that is not its parent's partner")
    return out


def mirror_frames(frames: Sequence[Sequence[tuple]], bind_local: Sequence[tuple], parents: Sequence[int],
                  pairs: Sequence[int]) -> List[List[tuple]]:
    """Left/right mirror of parent-local poses. Rotations: the world rotation of bone j is the reflected world delta of
    its partner i (R_i Rb_i^-1) applied to j's own bind; translations: j keeps its bind-local translation plus the
    reflected world offset its partner has from its own bind-local translation. At the bind this returns the bind
    exactly (the Handy skeleton is not perfectly symmetric: palm bones up to 2.5 FO4 units), and applying it twice
    returns the input (an involution; tested)."""
    bind_world = world_of(parents, bind_local)
    out = []
    for fr in frames:
        w = world_of(parents, fr)
        newq = [aa.q_norm(aa.q_mul(_mquat(aa.q_mul(w[pairs[j]][1], aa.q_conj(bind_world[pairs[j]][1]))),
                                   bind_world[j][1])) for j in range(len(fr))]
        loc = []
        for j in range(len(fr)):
            i, p = pairs[j], parents[j]
            pi = parents[i]
            src_par_q = w[pi][1] if pi >= 0 else (0.0, 0.0, 0.0, 1.0)
            delta_world = aa.q_rotate(src_par_q, _sub(fr[i][0], bind_local[i][0]))
            tgt_par_q = newq[p] if p >= 0 else (0.0, 0.0, 0.0, 1.0)
            t = _add(bind_local[j][0], aa.q_rotate(aa.q_conj(tgt_par_q), _mvec(delta_world)))
            q = aa.q_norm(aa.q_mul(aa.q_conj(newq[p]), newq[j])) if p >= 0 else newq[j]
            loc.append((t, q))
        out.append(loc)
    return out


# =============================================================================================== clips
class Clip:
    """A clip in Starfield units: frames[f][bone] = parent-local (t m, q xyzw); root[f] = (x, y, z m, yaw rad).
    frames[f][0] (Root) is rebuilt from root by finish()."""

    def __init__(self, frames, root, annotations, source, notes=None):
        self.frames = [list(fr) for fr in frames]
        self.root = list(root)
        self.annotations = list(annotations)          # [(time s, text)]
        self.source = source
        self.notes = list(notes or [])

    @property
    def n(self):
        return len(self.frames)

    def finish(self):
        for f, (x, y, z, yaw) in enumerate(self.root):
            self.frames[f][0] = ((x, y, z), yaw_quat(yaw))
        return self


def rig_bones_from_skeleton(skel_m, keys: Optional[Dict[str, int]] = None) -> List[dict]:
    """actor_anim bone dicts from convert_handy's skeleton in metres (actor_skin.Skeleton); keys default RIG_KEYS."""
    from fo4sf import actor_skin
    keys = RIG_KEYS if keys is None else keys
    bones = []
    for i, n in enumerate(skel_m.names):
        t, r, _s = skel_m.local[i]
        q = actor_skin.matrix_to_quat(r)
        if n == "Root":
            t, q = (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)
        bones.append({"name": n, "parent": skel_m.parents[i], "translation": tuple(t), "rotation": tuple(q),
                      "key": keys.get(n)})
    return aa.validate_bones(bones)


# =============================================================================================== rest-rotation rebase
# convert_handy.finish_skeleton turns bone j's frame by a constant C_j (actor_skin.rest_rotation_corrections): COM and
# the other REBASE bones get an identity rest rotation. A pose maps the same way: t' = C_p^-1 t, q' = C_p^-1 q C_j, so
# every bone keeps its world position in every frame and its world rotation becomes W_j C_j. The clips are decoded,
# cropped, mirrored and given root motion in skeleton.hkx's own frames (source), then mapped once before writing.
def corrections_as_quats(corr_mats: Sequence[tuple]) -> List[tuple]:
    from fo4sf import actor_skin
    return [aa.q_norm(actor_skin.matrix_to_quat(m)) for m in corr_mats]


def rebase_frames(frames, parents: Sequence[int], corr_q: Sequence[tuple]) -> List[list]:
    out = []
    for fr in frames:
        row = []
        for j, (t, q) in enumerate(fr):
            p = parents[j]
            cpi = aa.q_conj(corr_q[p]) if p >= 0 else aa.IDENTITY
            row.append((aa.q_rotate(cpi, t), aa.q_norm(aa.q_mul(aa.q_mul(cpi, q), corr_q[j]))))
        out.append(row)
    return out


def unrebase_frames(frames, parents: Sequence[int], corr_q: Sequence[tuple]) -> List[list]:
    """Inverse of rebase_frames (t = C_p t', q = C_p q' C_j^-1); frames may carry extra bones after len(parents): dropped."""
    out = []
    for fr in frames:
        row = []
        for j in range(len(parents)):
            t, q = fr[j]
            p = parents[j]
            cp = corr_q[p] if p >= 0 else aa.IDENTITY
            row.append((aa.q_rotate(cp, t), aa.q_norm(aa.q_mul(aa.q_mul(cp, q), aa.q_conj(corr_q[j])))))
        out.append(row)
    return out


def to_rig_frames(frames, parents_src: Sequence[int], corr_q: Sequence[tuple], extra_binds: Sequence[tuple]) -> List[list]:
    """Source-frame poses -> poses on the written rig: rebased, then the extra bones (DirectAt) held at their bind."""
    return [row + [tuple(x) for x in extra_binds] for row in rebase_frames(frames, parents_src, corr_q)]


def world_position_difference(parents_a, frames_a, parents_b, frames_b, count: int) -> Tuple[float, int, int]:
    """(largest distance m, frame, bone) between the world positions of the first `count` bones of two pose sets."""
    worst = (0.0, -1, -1)
    for f, (fa, fb) in enumerate(zip(frames_a, frames_b)):
        wa, wb = world_of(parents_a, fa), world_of(parents_b, fb)
        for j in range(count):
            d = math.dist(wa[j][0], wb[j][0])
            if d > worst[0]:
                worst = (d, f, j)
    return worst


def translation_rule_exposure(bones: Sequence[dict], frames) -> Tuple[float, Optional[str]]:
    """Largest difference (m) between the two candidate engine rules for a translation offset on a bone, over every
    bone and frame: local t = t_b + q_b t_o (the writer's, actor_anim.offset_to_local) against t = t_b + t_o, with
    t_o = q_b^-1 (t - t_b). Zero for a bone whose rest rotation is the identity."""
    worst, bone = 0.0, None
    for j, b in enumerate(bones):
        bq, bt = b["rotation"], b["translation"]
        if aa.q_angle(bq, aa.IDENTITY) < 1e-9:
            continue
        inv = aa.q_conj(bq)
        for fr in frames:
            d = _sub(fr[j][0], bt)
            e = math.dist(d, aa.q_rotate(inv, d))
            if e > worst:
                worst, bone = e, b["name"]
    return worst, bone


def decode_fo4_clip(hkx: bytes, bones: Sequence[dict], names_hk: Sequence[str], base: Optional[Clip] = None) -> Tuple[Clip, dict]:
    """A Fallout 4 robot clip (decoded by hkanim) as a Clip on the rig `bones` (metres). Untracked bones hold the rig
    bind. An ADDITIVE clip is composed onto `base` (frame f mod base.n): t = t_base + t_add, q = q_base q_add."""
    h = hkanim.load(hkx)
    an, bd = h.animations[0], h.bindings[0]
    names = [b["name"] for b in bones]
    if list(names_hk) != names:
        raise Ra2Error("hkx skeleton and rig bone order differ")
    track_of = {bone: t for t, bone in enumerate(bd.transform_track_to_bone)}
    additive = bd.blend_hint == 2
    if additive and base is None:
        raise Ra2Error("an additive clip needs a base clip")
    stats = {"frames": an.num_frames, "fps": round(an.fps, 4), "blend": bd.blend_hint_name, "tracks": an.num_transform_tracks,
             "max_scale_dev": 0.0, "additive_max_t_m": 0.0, "additive_max_r_deg": 0.0}
    if abs(an.fps - FPS) > 1e-3:
        raise Ra2Error(f"clip at {an.fps} fps; only {FPS} is handled")
    frames = []
    for f in range(an.num_frames):
        fr = []
        for i, b in enumerate(bones):
            if i in track_of:
                t, q, s = an.tracks[track_of[i]][f]
                stats["max_scale_dev"] = max(stats["max_scale_dev"], max(abs(c - 1.0) for c in s))
                t = tuple(c * UNIT for c in t)
                if additive:
                    stats["additive_max_t_m"] = max(stats["additive_max_t_m"], max(abs(c) for c in t))
                    stats["additive_max_r_deg"] = max(stats["additive_max_r_deg"], math.degrees(aa.q_angle(q, aa.IDENTITY)))
                    bt, bq = base.frames[f % base.n][i]
                    t, q = _add(bt, t), aa.q_norm(aa.q_mul(bq, q))
                fr.append((t, aa.q_norm(q)))
            elif additive:
                fr.append(base.frames[f % base.n][i])
            else:
                fr.append((b["translation"], b["rotation"]))
        frames.append(fr)
    rf = an.reference_frame
    if rf is not None and len(rf.samples) == an.num_frames:
        root = [(x * UNIT, y * UNIT, z * UNIT, w) for x, y, z, w in rf.samples]
    else:
        root = [(0.0, 0.0, 0.0, 0.0)] * an.num_frames
    notes = [(t, txt) for _track, lst in an.annotations for t, txt in lst]
    return Clip(frames, root, notes, None).finish(), stats


def crop_turn(clip: Clip, degrees: float) -> Clip:
    """Cut a turning clip at the first frame whose |yaw| reaches `degrees`, then scale the yaw so it ends exactly there."""
    target = math.radians(degrees)
    end = next((f for f, r in enumerate(clip.root) if abs(r[3]) >= target - 1e-9), None)
    if end is None or end == 0:
        raise Ra2Error(f"clip never turns {degrees} deg")
    k = target / abs(clip.root[end][3])
    root = [(x, y, z, w * k) for x, y, z, w in clip.root[:end + 1]]
    last_t = end / FPS
    out = Clip(clip.frames[:end + 1], root, [(t, s) for t, s in clip.annotations if t <= last_t + 1e-6], clip.source,
               clip.notes + [f"cropped at frame {end} of {clip.n} (yaw {math.degrees(clip.root[end][3]):.2f} deg), "
                             f"yaw scaled x{k:.5f} to end at {degrees:g} deg"])
    return out.finish()


def mirror_clip(clip: Clip, bones: Sequence[dict], pairs: Sequence[int]) -> Clip:
    parents = [b["parent"] for b in bones]
    bind = [(b["translation"], b["rotation"]) for b in bones]
    frames = mirror_frames(clip.finish().frames, bind, parents, pairs)
    root = [(-x, y, z, -w) for x, y, z, w in clip.root]
    out = Clip(frames, root, clip.annotations, clip.source, clip.notes + ["mirrored left <-> right"])
    return out.finish()


def with_root_velocity(clip: Clip, velocity: Sequence[float], what: str) -> Clip:
    root = [(velocity[0] * f / FPS, velocity[1] * f / FPS, velocity[2] * f / FPS, 0.0) for f in range(clip.n)]
    out = Clip(clip.frames, root, clip.annotations, clip.source,
               clip.notes + [f"root motion replaced: {what} {tuple(round(v, 4) for v in velocity)} m/s"])
    return out.finish()


def clip_events(cm: hr.ClipMap, clip: Clip) -> List[Tuple[int, str, str]]:
    last = clip.n - 1
    evs = set()
    for t, text in clip.annotations:
        name = hr.sf_event(text)
        if name:
            evs.add((min(last, max(0, int(round(t * FPS)))), name))
    for where, name in cm.add_events:
        evs.add((last if where == "end" else 0, name))
    return [(f, n, "") for f, n in sorted(evs)]


def poses_of(clip: Clip, bones: Sequence[dict]) -> Dict[str, list]:
    return poses_of_frames(clip.frames, bones)


def poses_of_frames(frames, bones: Sequence[dict]) -> Dict[str, list]:
    return {b["name"]: [fr[i] for fr in frames] for i, b in enumerate(bones)}


# =============================================================================================== .afx in the vanilla shape
# Measured on all 19,303 vanilla .afx: CRLF line ends (19,300), tab indents, <payload></payload>, the melee events spelt
# PreHitFrame / WeaponSwing (420 / 422 uses, never the Fallout 4 spelling), while the baked animationoffsets manifests
# spell them preHitFrame / weaponSwing (2,436 each, never capitalised): handy_race.sf_event keeps the manifest spelling.
AFX_EVENT_SPELLING = {"preHitFrame": "PreHitFrame", "weaponSwing": "WeaponSwing"}
_AFX_TOP = re.compile(r"\t<([a-z_]+)>(?:[^\r\n]*?</\1>|\r\n.*?\r\n\t</\1>)\r\n", re.S)


def afx_elements(raw: bytes) -> Tuple[List[Tuple[str, str]], str]:
    """([(element name, its text incl. indent and CRLF)], file ending) of a vanilla-shaped .afx; raises on anything else."""
    text = raw.decode("utf-8")
    if not text.startswith("<root>\r\n"):
        raise Ra2Error("not a vanilla-shaped .afx (no '<root>' CRLF head)")
    end = text.rindex("</root>")
    body, ending = text[len("<root>\r\n"):end], text[end:]
    out, pos = [], 0
    while pos < len(body):
        m = _AFX_TOP.match(body, pos)
        if not m:
            raise Ra2Error(f"unparsed .afx text at {pos}: {body[pos:pos + 40]!r}")
        out.append((m.group(1), m.group(0)))
        pos = m.end()
    return out, ending


_AFX_VAR = re.compile(r"\t\t<variable><name>([^<]*)</name><start>(\d+)</start><end>(\d+)</end></variable>\r\n")


def _clamp_variables(text: str, frame_count: int) -> str:
    """A <variables> block with every frame range clamped to 0..frame_count-1 (a range starting after the clip is
    dropped; the block is dropped when none is left)."""
    last = frame_count - 1

    def fix(m):
        s, e = int(m.group(2)), int(m.group(3))
        if s > last:
            return ""
        return f"\t\t<variable><name>{m.group(1)}</name><start>{s}</start><end>{min(e, last)}</end></variable>\r\n"
    out = _AFX_VAR.sub(fix, text)
    return "" if "<variable>" not in out else out


def afx_vanilla(tag: str, filename: str, is_state: int, events=(), audio=(), template: Optional[bytes] = None,
                frame_count: Optional[int] = None) -> bytes:
    """An .afx as Starfield ships them. template: a vanilla .afx whose other elements (rampout, prefix, suffix,
    compression, flags such as 'Turn Animation', variables) are kept verbatim and in place; its events and audios are
    replaced by `events` [(frame, name, payload)] and `audio` [(frame, foley)]; with frame_count the template's variable
    frame ranges are clamped to the clip. Reproduces every vanilla Mini Bot .afx byte for byte from its own parsed
    fields (tested)."""
    els, ending = afx_elements(template) if template else ([], "</root>")
    if frame_count is not None:
        els = [(n, _clamp_variables(t, frame_count) if n == "variables" else t) for n, t in els]
        els = [(n, t) for n, t in els if t]
    head = (f"\t<is_state>{int(is_state)}</is_state>\r\n\t<tag>{tag}</tag>\r\n\t<filename>{filename}</filename>\r\n")
    ev = ("\t<events>\r\n" + "".join(f"\t\t<event><frame>{int(f)}</frame><name>{n}</name><payload>{p or ''}</payload></event>\r\n"
                                     for f, n, p in events) + "\t</events>\r\n") if events else ""
    au = ("\t<audios>\r\n" + "".join(f"\t\t<audio><frame>{int(f)}</frame><foley>{n}</foley></audio>\r\n" for f, n in audio)
          + "\t</audios>\r\n") if audio else ""
    kept = [(n, t) for n, t in els if n not in ("is_state", "tag", "filename", "events", "audios")]
    before = [t for n, t in kept if n != "variables"]
    after = [t for n, t in kept if n == "variables"]
    return ("<root>\r\n" + head + "".join(before) + ev + au + "".join(after) + ending).encode("utf-8")


def strafing_afx_templates(sfa: Ba2, races: Sequence[esm.Record], prefer: str = VAN_CLIPS) -> Dict[str, Tuple[str, bytes]]:
    """{tag lower: (archive path, .afx bytes)} over the clip folders of every race that plays Creature_Strafing, the
    `prefer` folder first, then the races in Starfield.esm order (a tag's first vanilla .afx wins)."""
    folders = [prefer]
    for r in races:
        for g, fs in hr.race_subgraph_sets(r):
            if g.lower() == hr.STRAFING_GRAPH.lower():
                folders += [f for f in fs if f not in folders]
    by_folder: Dict[str, List[str]] = {}
    for n in sfa.names:
        low = n.lower().replace("\\", "/")
        if low.endswith(".afx"):
            by_folder.setdefault(os.path.dirname(low), []).append(n)
    out: Dict[str, Tuple[str, bytes]] = {}
    for f in folders:
        for n in sorted(by_folder.get(("meshes/" + f).lower().replace("\\", "/"), [])):
            raw = sfa.read(sfa.find(n))
            t = aa.parse_afx(raw)["tag"]
            if t and t.lower() not in out:
                out[t.lower()] = (n, raw)
    return out


# =============================================================================================== read-back check
def _sampler(block):
    rot, trans = block.get("rot", []), block.get("trans", [])
    rd, td = dict(rot), dict(trans)

    def at(f):
        if (f in rd or not rot) and (f in td or not trans):
            return (td.get(f, (0.0, 0.0, 0.0)), rd.get(f, aa.IDENTITY))
        return aa.sample_block(block, f)
    return at


def readback_local(cal, rig_path: Path, af_path: Path):
    rc = cal.read_clip(str(rig_path), str(af_path))
    rb = rc["rig"]["bones"]
    by = {b["bone"]: _sampler(b) for b in rc["blocks"]}
    frames = []
    for f in range(rc["frame_count"]):
        fr = []
        for b in rb:
            if b["name"] in by:
                fr.append(aa.offset_to_local(b["translation"], b["rotation"], *by[b["name"]](f)))
            else:
                fr.append((tuple(b["translation"]), aa.q_norm(b["rotation"])))
        frames.append(fr)
    return rc, frames


def pose_errors(parents, names, a_frames, b_frames, skip=()) -> dict:
    """Largest parent-local translation (m) and rotation (deg) difference and largest model-space position difference
    (mm) between two pose sequences of one rig. skip: bone names left out (e.g. a Root that was rewritten)."""
    worst = {"t_m": 0.0, "r_deg": 0.0, "model_mm": 0.0, "t_bone": None, "r_bone": None, "model_bone": None}
    keep = [i for i, n in enumerate(names) if n not in skip]
    for fa, fb in zip(a_frames, b_frames):
        if skip:
            fa = [fa[i] if names[i] not in skip else fb[i] for i in range(len(fa))]
        wa, wb = world_of(parents, fa), world_of(parents, fb)
        for i in keep:
            dt = max(abs(x - y) for x, y in zip(fa[i][0], fb[i][0]))
            dr = math.degrees(aa.q_angle(fa[i][1], fb[i][1]))
            dm = math.dist(wa[i][0], wb[i][0]) * 1000.0
            if dt > worst["t_m"]:
                worst["t_m"], worst["t_bone"] = dt, names[i]
            if dr > worst["r_deg"]:
                worst["r_deg"], worst["r_bone"] = dr, names[i]
            if dm > worst["model_mm"]:
                worst["model_mm"], worst["model_bone"] = dm, names[i]
    return {k: (round(v, 7) if isinstance(v, float) else v) for k, v in worst.items()}


# =============================================================================================== deformation check
# The review's check 4 (robot-anim F), for every clip and every frame: skin the staged mesh with linear blend skinning
# on the poses read back through the DLL (the rig's bind times each clip's offsets), and measure every mesh edge
# against its bind length. A ratio far above 1 is a tear (a triangle whose corners follow two bones that move apart).
HANDY_NIF_REL = "meshes/fo4sf/actors/handy/handy.nif"           # convert_handy.OUT_MESH
STRETCH_MIN_EDGE_M = 1e-4                                         # shorter bind edges are left out (as the review)
STRETCH_LIMIT = 1.6


def load_skinned_shapes(data_dir: Path, nif_rel: str = HANDY_NIF_REL) -> List[dict]:
    """Every skinned BSGeometry of a staged actor mesh NIF with its .mesh (numpy arrays): bind positions (Root space,
    m), per vertex weights and slots, skin bone names, BoneData (skin -> bone, 3x4), unique triangle edges and their
    bind lengths, and each vertex's heaviest bone."""
    import numpy as np
    from fo4sf import fo4skin, nif as nifmod, sfmesh, sfnif
    data_dir = Path(data_dir)
    n = nifmod.parse((data_dir / Path(*nif_rel.split("/"))).read_bytes())
    out = []
    for g in range(len(n.blocks)):
        if n.type_of(g) != "BSGeometry":
            continue
        geo = sfnif.parse_bsgeometry(n.blocks[g])
        root_i, data_i, nb = struct.unpack_from("<iiI", n.blocks[geo.skin], 0)
        bones = list(struct.unpack_from(f"<{nb}i", n.blocks[geo.skin], 12))
        names = [fo4skin._block_name(n, b).decode("latin-1") for b in bones]
        _bounds, s2b = fo4skin.read_bone_data(n.blocks[data_i])
        rel = geo.meshes[0].path.decode("latin-1").replace("\\", "/")
        m = sfmesh.parse((data_dir / "geometries" / Path(*(rel + ".mesh").split("/"))).read_bytes())
        pts = np.array([sfmesh.decode_position(p, m.scale) for p in m.positions], dtype=float)
        wpv = m.weights_per_vertex
        ws = np.array([[w for _s, w in m.weights[v * wpv:(v + 1) * wpv]] for v in range(len(pts))], dtype=float) / 65535.0
        sl = np.array([[s for s, _w in m.weights[v * wpv:(v + 1) * wpv]] for v in range(len(pts))], dtype=int)
        bd = np.zeros((nb, 3, 4))
        for k, (t, r, s) in enumerate(s2b):
            bd[k, :, :3] = np.array(r, dtype=float).reshape(3, 3) * s
            bd[k, :, 3] = t
        edges = set()
        for a, b, c in m.triangles:
            for u, v in ((a, b), (b, c), (c, a)):
                edges.add((min(u, v), max(u, v)))
        edges = np.array(sorted(edges), dtype=int).reshape(-1, 2)
        l0 = np.linalg.norm(pts[edges[:, 0]] - pts[edges[:, 1]], axis=1)
        keep = l0 > STRETCH_MIN_EDGE_M
        heavy = sl[np.arange(len(pts)), ws.argmax(axis=1)]
        single = ws.max(axis=1) > 0.99999            # one bone carries the whole vertex
        e = edges[keep]
        rigid = single[e[:, 0]] & single[e[:, 1]] & (heavy[e[:, 0]] == heavy[e[:, 1]])
        seams: Dict[str, int] = {}                   # triangles whose corners follow different heaviest bones
        for tri in m.triangles:
            hs = sorted({names[heavy[i]] for i in tri})
            if len(hs) > 1:
                seams["/".join(hs)] = seams.get("/".join(hs), 0) + 1
        out.append({"name": n.strings[geo.name_idx].decode("latin-1"), "bones": names, "bone_data": bd, "pts": pts,
                    "w": ws, "slots": sl, "edges": e, "l0": l0[keep], "heavy": heavy, "rigid": rigid,
                    "seams": dict(sorted(seams.items(), key=lambda kv: -kv[1])),
                    "tris": len(m.triangles), "verts": len(pts)})
    return out


def _world_matrices(parents, local):
    """(B, 3, 4) world matrices of one parent-local pose [(t, q)]."""
    import numpy as np
    w = world_of(parents, local)
    out = np.zeros((len(w), 3, 4))
    for i, (t, q) in enumerate(w):
        x, y, z, s = q
        out[i, :, :3] = ((1 - 2 * (y * y + z * z), 2 * (x * y - z * s), 2 * (x * z + y * s)),
                         (2 * (x * y + z * s), 1 - 2 * (x * x + z * z), 2 * (y * z - x * s)),
                         (2 * (x * z - y * s), 2 * (y * z + x * s), 1 - 2 * (x * x + y * y)))
        out[i, :, 3] = t
    return out


def skin_pose(shape: dict, world, index: Dict[str, int]):
    """Linear blend skinning of one loaded shape on (B, 3, 4) world matrices (rig bone order; `index` name -> row)."""
    import numpy as np
    wm = world[[index[b] for b in shape["bones"]]]
    rot = np.einsum("kij,kjl->kil", wm[:, :, :3], shape["bone_data"][:, :, :3])
    tr = np.einsum("kij,kj->ki", wm[:, :, :3], shape["bone_data"][:, :, 3]) + wm[:, :, 3]
    out = np.zeros_like(shape["pts"])
    for j in range(shape["slots"].shape[1]):
        s = shape["slots"][:, j]
        out += shape["w"][:, j, None] * (np.einsum("vij,vj->vi", rot[s], shape["pts"]) + tr[s])
    return out


def edge_stretch(shapes: Sequence[dict], parents: Sequence[int], names: Sequence[str], frames) -> Dict[str, dict]:
    """{shape: {ratio, frame, bones (heaviest bone of each end), bind_m, posed_m, rigid_dev}} worst edge stretch over
    `frames` (parent-local poses of the rig `names` / `parents`). rigid_dev: the largest |length ratio - 1| of the
    edges whose two ends follow one and the same bone with full weight (a rigid piece: anything but ~0 is a conversion
    error, not a seam)."""
    import numpy as np
    index = {n: i for i, n in enumerate(names)}
    worst = {s["name"]: {"ratio": 0.0, "frame": -1, "rigid_dev": 0.0} for s in shapes}
    for f, fr in enumerate(frames):
        wm = _world_matrices(parents, fr)
        for s in shapes:
            if not len(s["edges"]):
                continue
            p = skin_pose(s, wm, index)
            d = np.linalg.norm(p[s["edges"][:, 0]] - p[s["edges"][:, 1]], axis=1)
            r = d / s["l0"]
            k = int(r.argmax())
            w = worst[s["name"]]
            rig = s.get("rigid")
            if rig is not None and rig.any():
                w["rigid_dev"] = max(w["rigid_dev"], round(float(np.abs(r[rig] - 1.0).max()), 6))
            if r[k] > w["ratio"]:
                a, b = s["edges"][k]
                w.update({"ratio": round(float(r[k]), 4), "frame": f,
                          "bones": [s["bones"][s["heavy"][a]], s["bones"][s["heavy"][b]]],
                          "bind_m": round(float(s["l0"][k]), 5), "posed_m": round(float(d[k]), 5)})
    return worst


def deformation_check(stage: Path, cal=None, dll: Optional[str] = None, limit: float = STRETCH_LIMIT) -> dict:
    """edge_stretch of every clip of a staged bundle (E or E2), every frame, on poses read back through the DLL."""
    stage = Path(stage)
    cal = cal or aa.Calumi(dll)
    data = stage / "Data"
    rig = data / "Meshes" / Path(*HANDY.skeleton_rig.split("\\"))
    shapes = load_skinned_shapes(data)
    rr = cal.read_rig(str(rig))["bones"]
    names, parents = [b["name"] for b in rr], [b["parent"] for b in rr]
    clips = {}
    for af in sorted((data / "Meshes" / Path(*HANDY.clips.split("\\"))).glob("*.af")):
        _rc, rb = readback_local(cal, rig, af)
        clips[af.stem] = edge_stretch(shapes, parents, names, rb)
    return summarize_stretch(clips, shapes, limit)


def summarize_stretch(clips: Dict[str, Dict[str, dict]], shapes: Sequence[dict], limit: float = STRETCH_LIMIT) -> dict:
    per_clip = {c: max(v.values(), key=lambda x: x["ratio"]) | {"shape": max(v, key=lambda k: v[k]["ratio"]),
                                                                   "rigid_dev": max(x.get("rigid_dev", 0.0) for x in v.values())}
                for c, v in clips.items()}
    worst = max(per_clip.items(), key=lambda kv: kv[1]["ratio"]) if per_clip else (None, {"ratio": 0.0})
    return {"limit": limit, "clips": len(clips), "frames": "every frame", "min_edge_m": STRETCH_MIN_EDGE_M,
            "shapes": {s["name"]: {"verts": s["verts"], "tris": s["tris"], "edges": int(len(s["edges"])),
                                   "rigid_edges": int(s["rigid"].sum()) if "rigid" in s else None,
                                   "seam_triangles": s.get("seams"), "bones": len(s["bones"])} for s in shapes},
            "worst": {"clip": worst[0], **worst[1]},
            "rigid_edges_worst_dev": max((v["rigid_dev"] for v in per_clip.values()), default=0.0),
            "over_limit": sorted(c for c, v in per_clip.items() if v["ratio"] >= limit),
            "per_clip": per_clip, "per_clip_shape": clips}


# Fallout 4's own skinning of the same parts on the same decoded frames, against the staged mesh on the read-back clip:
# the evidence that a remaining seam is in Fallout 4's part and clip, not in the conversion. Cases: the worst seam of
# each kind (TorsoHandy chest / ring junction in the turns, ArmsTypeA1 Arm4 / Arm5 hinge, PincherHand finger hinge),
# clips that are neither cropped nor mirrored.
NATIVE_CASES = (("TorsoHandy.nif", None, "turninplace_left180"), ("TorsoHandy.nif", None, "walkdeparture_left180"),
                ("TorsoHandy.nif", None, "firesingle_mouth1"), ("ArmsTypeA1.nif", 0, "meleeattackpower01"),
                ("ArmsTypeA1.nif", 2, "death_backward01"), ("PincherHand.nif", 0, "meleeattack01"))


def fo4_part_shapes(nif_bytes: bytes, instance, hk_names: Sequence[str], unit: float = UNIT) -> List[dict]:
    """The lit shapes of one Fallout 4 part as Fallout 4 skins them (stored skin-space positions, its own
    skin-to-bone transforms and normalised f16 weights), in metres, with bone indices into hk_names."""
    import numpy as np
    import convert_handy
    from fo4sf import fo4skin, nif as nifmod
    low = {n.lower(): i for i, n in enumerate(hk_names)}
    n = nifmod.parse(nif_bytes)
    out = []
    for s in nifmod.fo4_trishapes(n, placed=True):
        if convert_handy._diffuse_stem(n, s) not in convert_handy.TEXTURE_GROUPS:
            continue
        skin = fo4skin.read_skin(n, s.block)
        bones = [low[convert_handy.instance_bone(b.decode("latin-1"), instance).lower()] for b in skin.bone_names]
        bd = np.zeros((len(bones), 3, 4))
        for k, (t, r, sc) in enumerate(skin.skin_to_bone):
            bd[k, :, :3] = np.array(r, dtype=float).reshape(3, 3) * sc
            bd[k, :, 3] = tuple(c * unit for c in t)
        w = np.array([[float(x) for x in ws] for ws in skin.weights])
        w = w / w.sum(axis=1, keepdims=True)
        pts = np.array(s.positions, dtype=float) * unit
        edges = np.array(sorted({(min(u, v), max(u, v)) for a, b, c in s.triangles for u, v in ((a, b), (b, c), (c, a))}))
        l0 = np.linalg.norm(pts[edges[:, 0]] - pts[edges[:, 1]], axis=1)
        keep = l0 > STRETCH_MIN_EDGE_M
        out.append({"name": s.name.decode("latin-1"), "group": convert_handy.TEXTURE_GROUPS[
                        convert_handy._diffuse_stem(n, s)], "bones": [hk_names[b] for b in bones], "bone_data": bd,
                    "pts": pts, "w": w, "slots": np.array([list(k) for k in skin.indices]), "edges": edges[keep],
                    "l0": l0[keep], "heavy": np.zeros(len(pts), dtype=int)})
    return out


def worst_per_frame(shapes: Sequence[dict], parents, names, frames) -> List[float]:
    import numpy as np
    index = {n: i for i, n in enumerate(names)}
    res = []
    for fr in frames:
        wm = _world_matrices(parents, fr)
        m = 0.0
        for s in shapes:
            p = skin_pose(s, wm, index)
            d = np.linalg.norm(p[s["edges"][:, 0]] - p[s["edges"][:, 1]], axis=1)
            m = max(m, float((d / s["l0"]).max()))
        res.append(m)
    return res


def fo4_native_cases(placed, part_nifs, shapes, clips_rep, kept_rb, source, names_src, parents_src, names, parents) -> dict:
    """For each NATIVE_CASES entry: the worst edge stretch per frame of the Fallout 4 part skinned as Fallout 4 skins it
    on the decoded source clip, against the same vertices of the staged mesh on the read-back clip."""
    offsets, cursor = {}, {}
    for p in placed:
        first = cursor.get(p["group"], 0)
        offsets.setdefault((p["part"], p["instance"]), []).append((p["group"], first, p["verts"]))
        cursor[p["group"]] = first + p["verts"]
    by_shape = {s["name"]: s for s in shapes}
    by_file = {c["file"][:-3]: c for c in clips_rep}
    out = {}
    for part, inst, stem in NATIVE_CASES:
        c = by_file[stem]
        if c["how"] == "mirror" or c["frames"] != source(c["fo4"]).n:
            raise Ra2Error(f"native case {stem} is mirrored or cropped")
        nat = worst_per_frame(fo4_part_shapes(part_nifs[part], inst, names_src), parents_src, names_src,
                              source(c["fo4"]).frames)
        our = worst_per_frame([vertex_range(by_shape[g], f, k) for g, f, k in offsets[(part, inst)]], parents, names,
                              kept_rb[stem])
        out[f"{part}{'' if inst is None else '|' + str(inst)} {stem}"] = {
            "fo4_clip": c["fo4"], "fo4_native_worst": round(max(nat), 4), "fo4_native_frame": nat.index(max(nat)),
            "staged_worst": round(max(our), 4), "staged_frame": our.index(max(our)),
            "per_frame_max_abs_diff": round(max(abs(a - b) for a, b in zip(nat, our)), 4)}
    return out


def native_vs_staged(native_shapes: Dict[str, list], src_frames, names_src, parents_src, staged_shapes, rb, names,
                     parents) -> dict:
    """One clip: per shape group, Fallout 4's own skinning of its parts on the poses that were written (source frames,
    skeleton.hkx names) against the staged mesh on the clip read back through CALUMI, worst edge ratio per frame.
    Returns the worst native ratio and the largest per-frame difference (absolute and relative)."""
    by = {s["name"]: s for s in staged_shapes}
    worst, d_abs, d_rel = 0.0, 0.0, 0.0
    for g, nat_shapes in native_shapes.items():
        nat = worst_per_frame(nat_shapes, parents_src, names_src, src_frames)
        stg = worst_per_frame([by[g]], parents, names, rb)
        worst = max(worst, max(nat))
        for a, b in zip(nat, stg):
            d_abs = max(d_abs, abs(a - b))
            d_rel = max(d_rel, abs(a - b) / a)
    return {"worst": round(worst, 4), "max_abs_diff": round(d_abs, 4), "max_rel_diff": round(d_rel, 5)}


def vertex_range(shape: dict, first: int, count: int) -> dict:
    """A loaded staged shape restricted to the edges among vertices [first, first + count) (one placed part)."""
    import numpy as np
    keep = np.all((shape["edges"] >= first) & (shape["edges"] < first + count), axis=1)
    return dict(shape, edges=shape["edges"][keep], l0=shape["l0"][keep])


def compare_bundles(old: Path, new: Path, cal=None, dll: Optional[str] = None) -> dict:
    """Model-space comparison of two staged Handy bundles (robot-anim fix 1 proof): for every clip both hold, every
    frame and every bone of the old rig (matched by actor_skin.starfield_bone_name), the distance between the bone's
    world positions read back through the DLL, and the angle between its new world rotation and its old one times the
    constant rest correction C_j = W_old,bind^-1 W_new,bind (identity for bones that were not rebased)."""
    from fo4sf import actor_skin
    cal = cal or aa.Calumi(dll)
    out = {"clips": {}, "max_position_mm": 0.0, "max_rotation_deg": 0.0, "where": None}
    rigs = {}
    for tag, stage in (("old", Path(old)), ("new", Path(new))):
        rp = stage / "Data" / "Meshes" / Path(*HANDY.skeleton_rig.split("\\"))
        rb = cal.read_rig(str(rp))["bones"]
        rigs[tag] = (rp, [b["name"] for b in rb], [b["parent"] for b in rb],
                     world_of([b["parent"] for b in rb], [(b["translation"], b["rotation"]) for b in rb]))
    _p, on, op, obind = rigs["old"]
    _p, nn, np_, nbind = rigs["new"]
    nidx = {n: i for i, n in enumerate(nn)}
    match = [(i, nidx[actor_skin.starfield_bone_name(n)]) for i, n in enumerate(on)]
    corr = {i: aa.q_mul(aa.q_conj(obind[i][1]), nbind[j][1]) for i, j in match}
    out["rebased_bones"] = sorted(nn[j] for i, j in match if aa.q_angle(corr[i], aa.IDENTITY) > 1e-4)
    out["bones_compared"], out["bones_only_new"] = len(match), sorted(set(nn) - {nn[j] for _i, j in match})
    clip_dir = lambda s: Path(s) / "Data" / "Meshes" / Path(*HANDY.clips.split("\\"))  # noqa: E731
    for af in sorted(clip_dir(new).glob("*.af")):
        oaf = clip_dir(old) / af.name
        if not oaf.is_file():
            continue
        _r, ofr = readback_local(cal, rigs["old"][0], oaf)
        _r, nfr = readback_local(cal, rigs["new"][0], af)
        if len(ofr) != len(nfr):
            raise Ra2Error(f"{af.name}: {len(ofr)} frames before, {len(nfr)} after")
        wp = wr = 0.0
        at = None
        for f, (a, b) in enumerate(zip(ofr, nfr)):
            wa, wb = world_of(op, a), world_of(np_, b)
            for i, j in match:
                d = math.dist(wa[i][0], wb[j][0]) * 1000.0
                r = math.degrees(aa.q_angle(aa.q_mul(wa[i][1], corr[i]), wb[j][1]))
                if d > wp:
                    wp, at = d, (f, nn[j])
                wr = max(wr, r)
        out["clips"][af.stem] = {"frames": len(nfr), "max_position_mm": round(wp, 4), "max_rotation_deg": round(wr, 4),
                                 "at": at}
        if wp > out["max_position_mm"]:
            out["max_position_mm"], out["where"] = round(wp, 4), {"clip": af.stem, "frame": at[0], "bone": at[1]}
        out["max_rotation_deg"] = max(out["max_rotation_deg"], round(wr, 4))
    return out


# =============================================================================================== manifests
def rewrite_folder(text: str, old: str, new: str) -> str:
    return re.sub(re.escape(old), lambda _m: new, text, flags=re.I)


def own_folder_manifests(vanilla: Dict[str, bytes], race: esm.Record, gsd: bytes, new_edid: str,
                         old_folder: str = VAN_CLIPS, new_folder: str = OWN_CLIPS) -> Tuple[Dict[str, bytes], dict]:
    """The Mini Bot's manifests re-keyed and re-pathed for a race whose clip folder is `new_folder`.
    vanilla: {'animationfiledata/<key>.txt': bytes, ...} (lower-case archive paths below meshes/animtextdata/).
    Returns ({Data-relative path: bytes}, report)."""
    out, rep = {}, {"keys": {}}
    sets = [(g, f) for g, f in hr.race_subgraph_sets(race) if f]
    rows = [ln.split("\t") for ln in gsd.decode("cp1252").splitlines()[1:] if ln.strip()]
    for r in rows:
        sets.append((r[4], [x.strip() for x in r[5].split(",")]))
    new_rows = []
    for g, folders in sets:
        old_key = hr.manifest_key(g, folders)
        nf = [rewrite_folder(x, old_folder, new_folder) for x in folders]
        new_key = hr.manifest_key(g, nf)
        rep["keys"][str(old_key)] = {"graph": g, "folders": nf, "new_key": str(new_key)}
        afd = vanilla.get(f"animationfiledata/{old_key}.txt")
        if afd is None:
            raise Ra2Error(f"no vanilla animationfiledata for {old_key} ({g} {folders})")
        lines = afd.decode("cp1252").split("\n")
        if lines[2] != str(old_key):
            raise Ra2Error(f"animationfiledata {old_key}: header names {lines[2]}")
        clips = [rewrite_folder(c, old_folder, new_folder) for c in lines[4:] if c]
        out[f"Meshes\\AnimTextData\\AnimationFileData\\{new_key}.txt"] = hr.animation_file_data(new_key, clips)
        off = vanilla.get(f"animationoffsets/{old_key}.txt")
        if off is not None:
            graph, tags, recs = hr.parse_animation_offsets(off)
            if hr.animation_offsets(graph, tags, recs) != off:
                raise Ra2Error(f"animationoffsets {old_key} does not rebuild byte for byte")
            tags = [(t, rewrite_folder(c, old_folder, new_folder)) for t, c in tags]
            recs = [hr.OffsetClip(rewrite_folder(c.path, old_folder, new_folder), c.duration, c.events, c.keys, c.flags)
                    for c in recs]
            out[f"Meshes\\AnimTextData\\AnimationOffsets\\{new_key}.txt"] = hr.animation_offsets(graph, tags, recs)
        st = vanilla.get(f"animationstancedata/{old_key}.txt")
        if st is not None:
            if b"minibota" in st.lower():
                raise Ra2Error(f"stance data {old_key} names the vanilla folder")
            out[f"Meshes\\AnimTextData\\AnimationStanceData\\{new_key}.txt"] = st
        dyn = vanilla.get(f"dynamicidledata/{old_key}.txt")
        if dyn is not None:
            out[f"Meshes\\AnimTextData\\DynamicIdleData\\{new_key}.txt"] = rewrite_folder(
                dyn.decode("cp1252"), old_folder, new_folder).encode("cp1252")
    for r in rows:
        nr = list(r)
        nr[5] = rewrite_folder(r[5], old_folder, new_folder)
        new_rows.append(tuple(nr[:5]) + ([x.strip() for x in nr[5].split(",")],))
    out[f"Meshes\\AnimTextData\\GeneratedSubgraphData\\{new_edid.lower()}.txt"] = hr.generated_subgraph_data(new_rows)
    return out, rep


# =============================================================================================== records
def _plain_strings(subs, name):
    """FULL / SNAM / DESC hold string-table ids in Starfield.esm (localized); this plugin is not localized."""
    out = []
    for s, d in subs:
        if s in (b"FULL", b"SNAM") and len(d) == 4:
            d = esm.zbytes(name)
        elif s == b"DESC" and len(d) == 4:
            d = esm.zbytes("")
        out.append((s, d))
    return out


def _rec(src: esm.Record, sig: bytes, formid: int, subs) -> esm.Record:
    return esm.Record(sig, formid, subs, src.flags & ~esm.COMPRESSED, src.vc, src.version, src.unknown)


def copy_race(src: esm.Record, formid: int, edid: str, name: str, rig: Optional[str] = None,
              clips: Optional[str] = None, old_clips: str = VAN_CLIPS) -> esm.Record:
    """A RACE copy: new EDID, plain-string name fields; with rig/clips also NAM5, DNAM and every SAPT re-pathed."""
    subs = []
    for s, d in _plain_strings(src.subs, name):
        if s == b"EDID":
            d = esm.zbytes(edid)
        elif rig and s == b"NAM5":
            d = esm.zbytes(rig)
        elif clips and s in (b"DNAM", b"SAPT") and hr._is_text(d):
            d = esm.zbytes(rewrite_folder(esm.zstring(d), old_clips, clips))
        subs.append((s, d))
    return _rec(src, b"RACE", formid, subs)


def copy_arma(src: esm.Record, formid: int, edid: str, race: int, model: Optional[str] = None) -> esm.Record:
    subs = []
    for s, d in src.subs:
        if s == b"EDID":
            d = esm.zbytes(edid)
        elif s == b"RNAM":
            d = struct.pack("<I", race)
        elif model and s == b"MOD2":
            d = esm.zbytes(model)
        subs.append((s, d))
    if model and not any(s == b"MOD2" for s, _ in subs):
        raise Ra2Error(f"{src.edid} has no MOD2 world model to replace")
    return _rec(src, b"ARMA", formid, subs)


def copy_armo(src: esm.Record, formid: int, edid: str, race: int, arma: int) -> esm.Record:
    subs = []
    for s, d in src.subs:
        if s == b"EDID":
            d = esm.zbytes(edid)
        elif s == b"RNAM":
            d = struct.pack("<I", race)
        elif s == b"MODL":
            d = struct.pack("<I", arma)
        subs.append((s, d))
    if sum(1 for s, _ in subs if s == b"MODL") != 1:
        raise Ra2Error(f"{src.edid}: expected one armature (MODL)")
    return _rec(src, b"ARMO", formid, subs)


def copy_npc(src: esm.Record, formid: int, edid: str, name: str, race: int, skin: int,
             obnd: Optional[Sequence[float]] = None) -> Tuple[esm.Record, dict]:
    """The garden Mini Bot NPC_ as a combat test actor: own EDID / name / race / skin, no factions (SNAM), no outpost
    script (VMAD), Essential cleared, AIDT aggression Very Aggressive + confidence Foolhardy. Its template (TPLT/TPTA:
    stats, inventory, attack data; NOT traits, so race and skin are its own) is kept."""
    subs, rep = [], {"dropped": []}
    for s, d in src.subs:
        if s == b"VMAD" or (s == b"SNAM" and len(d) == 5):
            rep["dropped"].append(s.decode())
            continue
        if s == b"EDID":
            d = esm.zbytes(edid)
        elif s == b"FULL":
            d = esm.zbytes(name)
        elif s == b"RNAM":
            d = struct.pack("<I", race)
        elif s == b"WNAM":
            d = struct.pack("<I", skin)
        elif s == b"OBND" and obnd is not None:
            d = struct.pack("<6f", *obnd)
        elif s == b"ACBS":
            flags, = struct.unpack_from("<I", d)
            rep["acbs_flags"] = [hex(flags), hex(flags & ~ACBS_ESSENTIAL)]
            rep["template_flags"] = hex(struct.unpack_from("<H", d, 14)[0])
            if struct.unpack_from("<H", d, 14)[0] & 0x1:
                raise Ra2Error(f"{src.edid}: template supplies traits (race/skin); the copy would ignore its own race")
            d = struct.pack("<I", flags & ~ACBS_ESSENTIAL) + d[4:]
        elif s == b"AIDT":
            rep["aidt"] = [d.hex(), bytes([AGGRESSION_VERY_AGGRESSIVE, CONFIDENCE_FOOLHARDY]).hex() + d[2:].hex()]
            d = bytes([AGGRESSION_VERY_AGGRESSIVE, CONFIDENCE_FOOLHARDY]) + d[2:]
        subs.append((s, d))
    for need in (b"RNAM", b"WNAM", b"AIDT", b"ACBS"):
        if not any(s == need for s, _ in subs):
            raise Ra2Error(f"{src.edid}: no {need.decode()}")
    return _rec(src, b"NPC_", formid, subs), rep


def plugin_bytes(records: Sequence[esm.Record], masters: Sequence[str], group_order: Sequence[str],
                 author="FO4SF", description="RA2 Handy probe (robot-anim E)") -> bytes:
    """esm.PluginWriter's layout, with the top groups in Starfield.esm's own order (its GROUP_ORDER lacks RACE, ARMO,
    ARMA, BPTD and would sort them alphabetically)."""
    by = {}
    for r in records:
        by.setdefault(r.sig.decode("ascii"), []).append(r)
    order = [g for g in group_order if g in by] + sorted(g for g in by if g not in group_order)
    body = b"".join(esm.group_bytes(g, b"".join(r.to_bytes(False) for r in by[g])) for g in order)
    own = [r.formid & 0xFFFFFF for r in records if r.formid >> 24 == len(masters)]
    hsubs = [(b"HEDR", struct.pack("<fII", esm.HEDR_VERSION, len(records) + len(order), max(own) + 1 if own else 0x800))]
    hsubs += [(b"CNAM", esm.zbytes(author)), (b"SNAM", esm.zbytes(description))]
    hsubs += [(b"MAST", esm.zbytes(m)) for m in masters]
    head = esm.Record(b"TES4", 0, hsubs, esm.ESM, 0, esm.HEADER_FORM_VERSION, 0)
    return head.to_bytes(compress=False) + body


# =============================================================================================== BA2 (from stage_r11_p4_10mm.py)
BA2_ALIGN = 0xBAADF00D


def _ba2_keys(rel: str):
    norm = rel.replace("/", "\\").lstrip("\\")
    stem = Path(norm).stem.lower().encode("ascii")
    ext = Path(norm).suffix.lstrip(".").lower().encode("ascii")[:4].ljust(4, b"\0")
    return hr.bs_crc32(stem), ext, hr.bs_crc32(os.path.dirname(norm).lower().encode("ascii"))


def verify_ba2_entry_hashes(path: Path) -> int:
    """Every GNRL entry's name/extension/folder hash against Bethesda's CRC-32 of its name; entries uncompressed."""
    raw = Path(path).read_bytes()
    magic, version, kind, count, name_off = struct.unpack_from("<4sI4sIQ", raw, 0)
    extra = {1: 0, 2: 8, 3: 12, 7: 8, 8: 12}.get(version)
    if magic != b"BTDX" or kind != b"GNRL" or extra is None:
        raise Ra2Error(f"{path}: not a BTDX GNRL archive ({magic!r} v{version} {kind!r})")
    p, names = name_off, []
    for _ in range(count):
        n, = struct.unpack_from("<H", raw, p)
        names.append(raw[p + 2:p + 2 + n].decode("utf-8"))
        p += 2 + n
    e = 24 + extra
    for i, rel in enumerate(names):
        h, ext, d, _fl, _off, packed, _size, _al = struct.unpack_from("<I4sIIQIII", raw, e)
        e += 36
        if packed != 0:
            raise Ra2Error(f"{path}: {rel} is compressed")
        if (h, ext, d) != _ba2_keys(rel):
            raise Ra2Error(f"{path}: entry {i} {rel} hash mismatch")
    return count


def _pack_python(ordered, out_path: Path) -> None:
    cur = 32 + 36 * len(ordered)
    entries = []
    for rel, raw in ordered:
        h, ext, d = _ba2_keys(rel)
        entries.append((h, ext, d, 0x00100100, cur, 0, len(raw), BA2_ALIGN))
        cur += len(raw)
    with out_path.open("wb") as fh:
        fh.write(struct.pack("<4sI4sIQII", b"BTDX", 2, b"GNRL", len(ordered), cur, 1, 0))
        for e in entries:
            fh.write(struct.pack("<I4sIIQIII", *e))
        for _rel, raw in ordered:
            fh.write(raw)
        for rel, _raw in ordered:
            nb = rel.replace("/", "\\").lstrip("\\").encode("utf-8")
            fh.write(struct.pack("<H", len(nb)) + nb)


def pack_gnrl_ba2_v2(files: Sequence[Tuple[str, bytes]], out_path: Path, starfield_dir: Optional[Path] = None) -> dict:
    """Uncompressed Starfield BTDX General archive (Archive2.exe when present, else the Python writer); checked by
    entry hash and by reading every payload back. Copied from scripts/probes/stage_r11_p4_10mm.py (pc-853 worktree)."""
    if not files:
        raise Ra2Error("cannot pack an empty archive")
    ordered = sorted(files, key=lambda kv: kv[0].replace("/", "\\").lower())
    archive2 = starfield_dir / "Tools" / "Archive2" / "Archive2.exe" if starfield_dir is not None else None
    used = False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if archive2 is not None and archive2.is_file():
        with tempfile.TemporaryDirectory(prefix=".ra2-gnrl-", dir=str(out_path.parent)) as tdir:
            root = Path(tdir) / "root"
            tops = []
            for rel, raw in ordered:
                norm = rel.replace("/", "\\").lstrip("\\")
                top = norm.split("\\", 1)[0]
                if top not in tops:
                    tops.append(top)
                dst = root / Path(*norm.split("\\"))
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(raw)
            fresh = Path(tdir) / out_path.name
            r = subprocess.run([str(archive2), ",".join(tops), f"-create={fresh}", f"-root={root}", "-format=General",
                                "-compression=None"], cwd=str(root), capture_output=True, text=True, check=False)
            if r.returncode == 0 and fresh.is_file() and fresh.read_bytes()[:4] == b"BTDX":
                os.replace(fresh, out_path)
                used = True
    if not used:
        _pack_python(ordered, out_path)
    verify_ba2_entry_hashes(out_path)
    checked = Ba2(str(out_path))
    if len(checked.entries) != len(ordered):
        raise Ra2Error(f"{out_path.name}: {len(checked.entries)} entries for {len(ordered)} files")
    for rel, raw in ordered:
        if checked.read(rel) != raw:
            raise Ra2Error(f"{out_path.name}: {rel} does not read back")
    return {"file": out_path.name, "entries": len(ordered), "used_archive2": used, "size_bytes": out_path.stat().st_size,
            "sha256": sha256_file(out_path)}


# =============================================================================================== batch files
def build_bats(slot: Optional[int] = None) -> Dict[str, str]:
    """{file: text}: one console batch per test actor. slot None writes the XX placeholder (the staged copies)."""
    pre = "XX" if slot is None else f"{slot & 0xFF:02X}"
    out = {}
    for fname, (fid, what) in BATS.items():
        out[fname] = (f"; RA2 Handy probe: {what}\n"
                      f"; spawns beside the player (measured 1.3-1.7 m); Very Aggressive + Foolhardy: attacks on sight\n"
                      f"player.placeatme {pre}{fid:06X} 1\n")
    validate_bats(out)
    return out


def validate_bats(bats: Dict[str, str]) -> dict:
    """P3 rule of the probe stagers: no m/n/v in a batch file name or in the typed 'bat <stem>' command, and no
    FO4SF_ editor id inside a batch file."""
    bad = [f for f in bats if P3_FORBIDDEN_RE.search(f) or P3_FORBIDDEN_RE.search("bat " + Path(f).stem)]
    if bad:
        raise Ra2Error(f"m/n/v in batch file names or commands: {bad}")
    edids = {f: STRIPPED_EDID_RE.findall(t) for f, t in bats.items() if STRIPPED_EDID_RE.search(t)}
    if edids:
        raise Ra2Error(f"editor ids inside batch files: {edids}")
    return {"files": sorted(bats), "typed": [f"bat {Path(f).stem}" for f in sorted(bats)]}


# =============================================================================================== build
def _read_archive(pattern_dir: Path, glob_pat: str, rel: str) -> bytes:
    for p in sorted(pattern_dir.glob(glob_pat)):
        a = Ba2(str(p))
        i = a.find(rel)
        if i is not None:
            return a.read(i)
    raise Ra2Error(f"{rel} not found in {pattern_dir}\\{glob_pat}")


def build(out: Path = OUT, starfield_dir: Path = STARFIELD_DIR, fo4_data: Path = FO4_DATA, dll: Optional[str] = None,
          mesh: str = "parts", compare_with: Optional[Path] = None) -> dict:
    """Build the bundle into `out`. mesh: 'parts' (Codsworth's Fallout 4 robot parts, default) or 'mrhandy' (the old
    merged mesh, on the same fixed rig). compare_with: an earlier bundle (read only) to measure against: its clips'
    model-space bone positions (compare_bundles) and its own deformation check; with it, CHANGES.md is written."""
    import convert_handy
    from fo4sf import actor_skin
    if mesh not in MESH_SOURCES:
        raise Ra2Error(f"mesh {mesh!r} not one of {MESH_SOURCES}")
    out = check_out_dir(out)
    if compare_with is not None and Path(compare_with).resolve() == out:
        raise Ra2Error("compare_with is the output folder")
    sf_data = starfield_dir / "Data"
    for sub in ("Data", "work", "bat"):
        if (out / sub).exists():
            shutil.rmtree(out / sub)
    data, work = out / "Data", out / "work"
    data.mkdir(parents=True)
    work.mkdir(parents=True)
    report: dict = {"conventions": {
        "units": "FO4 units x 1/70 = metres (convert_static.UNIT_SCALE)",
        "axes": "FO4 and Starfield both Z up, +Y forward, +X right: no axis change (FO4 Death1 root moves -Y = backward, "
                "Stagger -Y; Starfield walkforward +Y, turninplace_left90 +90 deg about +Z; FO4 TurnLeft180 yaw +pi)",
        "fps": FPS, "root_motion": "hkaDefaultAnimatedReferenceFrame samples (x, y, z, yaw rad) -> Root bone track",
        "bind_overrides_fo4_units": {k: list(v) for k, v in BIND_OVERRIDES_FO4.items()},
        "rebased_bones": list(convert_handy.REBASE), "extra_bones": [e[0] for e in convert_handy.EXTRA_BONES],
        "bone_names": "letters, digits and '_' (actor_skin.starfield_bone_names: '|' and '-' -> '_')",
        "mesh_source": mesh, "rig_keys": RIG_KEYS, "precision": "default"}}

    # ---------------------------------------------------------------- the rig's skeleton: source (hkx) and final
    sf_meshes = lambda rel: _read_archive(sf_data, "Starfield - Meshes*.ba2", rel)  # noqa: E731
    fo4_anim = Ba2(str(fo4_data / "Fallout4 - Animations.ba2"))
    fo4_mesh = Ba2(str(fo4_data / "Fallout4 - Meshes.ba2"))
    skel_hkx = fo4_anim.read(fo4_anim.find(convert_handy.SRC_SKELETON))
    skel_src_fo4 = convert_handy.source_skeleton(skel_hkx, BIND_OVERRIDES_FO4)
    skel_final, corr_m, final_names = convert_handy.finish_skeleton(
        skel_src_fo4, UNIT, convert_handy.REBASE, convert_handy.EXTRA_BONES, rename=True)
    bones_src = rig_bones_from_skeleton(skel_src_fo4.scaled(UNIT), keys={})
    names_src = [b["name"] for b in bones_src]
    parents_src = [b["parent"] for b in bones_src]
    corr_q = corrections_as_quats(corr_m)

    # ---------------------------------------------------------------- C: mesh on the rig's bind
    materials = dict(convert_handy.HANDY_MATERIALS)
    sf_tmpl = (sf_meshes(convert_handy.SF_MESH_TEMPLATE), sf_meshes(convert_handy.SF_SKELETON_TEMPLATES["minibota"]))
    if mesh == "parts":
        files, mrep, skel_m, _names = convert_handy.convert_parts(
            convert_handy.read_codsworth_parts(fo4_mesh), skel_hkx, *sf_tmpl, materials, bind_overrides=BIND_OVERRIDES_FO4)
    else:
        files, mrep, skel_m, _mapping = convert_handy.convert(
            fo4_mesh.read(fo4_mesh.find(convert_handy.SRC_MESH)), skel_hkx, *sf_tmpl, materials,
            bind_overrides=BIND_OVERRIDES_FO4, rebase=convert_handy.REBASE, extra_bones=convert_handy.EXTRA_BONES,
            rename=True, mesh_exclude=convert_handy.MESH_EXCLUDE)
    if not (mrep["verify_mesh"]["ok"] and mrep["verify_skeleton"]["ok"] and mrep["verify_skeleton_ref"]["ok"]):
        raise Ra2Error(f"mesh conversion failed its own checks: {mrep['verify_mesh']['errors']}")
    if skel_m.names != skel_final.names or skel_m.parents != skel_final.parents or max(
            max(math.dist(a[0], b[0]), max(abs(x - y) for x, y in zip(a[1], b[1])))
            for a, b in zip(skel_m.local, skel_final.local)) > 1e-12:
        raise Ra2Error("the mesh skeleton and the rig skeleton differ")
    for rel, raw in files.items():
        p = data / Path(*rel.split("/"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
    (work / "convert_handy_report.json").write_text(json.dumps(mrep, indent=1, default=str), encoding="utf-8")
    (work / "bone_names.json").write_text(json.dumps({"hkx_to_rig": final_names}, indent=1), encoding="utf-8")
    report["mesh"] = {"source": mrep["source"], "files": sorted(files),
                      "bones_in_mesh_nif": mrep["skeleton"]["bones_in_mesh_nif"],
                      "weighted_bones": mrep["skeleton"]["weighted_bones"],
                      "shapes": {k: {x: v[x] for x in ("verts", "weights_per_vertex", "bones", "bind_pose_max_error_mm",
                                                       "influence_histogram")}
                                 for k, v in mrep["verify_mesh"]["shapes"].items()}}
    if mesh == "parts":
        report["mesh"].update({"groups": mrep["groups"], "skipped": mrep["skipped"],
                               "bind_spread_max_fo4_units": mrep["bind_spread_max_fo4_units"],
                               "placed": [{k: p[k] for k in ("part", "instance", "shape", "group", "verts", "tris")}
                                          for p in mrep["placed"]]})

    # ---------------------------------------------------------------- rig
    cal = aa.Calumi(dll)
    bones = rig_bones_from_skeleton(skel_m)
    names = [b["name"] for b in bones]
    parents = [b["parent"] for b in bones]
    extra_binds = [(b["translation"], b["rotation"]) for b in bones[len(bones_src):]]
    check = to_rig_frames([[(b["translation"], b["rotation"]) for b in bones_src]], parents_src, corr_q, extra_binds)[0]
    bind_err = max(max(math.dist(t, b["translation"]), aa.q_angle(q, b["rotation"])) for (t, q), b in zip(check, bones))
    if bind_err > 1e-6:          # the quaternion path (clips) and the matrix path (mesh, rig) agree to float32 round-off
        raise Ra2Error(f"rebased source bind and rig bind differ by {bind_err}")
    report["rig_bind_paths_agree"] = bind_err
    rig_path = data / "Meshes" / Path(*HANDY.skeleton_rig.split("\\"))
    cal.write_rig(bones, rig_path, name="FO4SF_HandyRig", precision="default")
    rig_rb = cal.read_rig(str(rig_path))
    cmp_rig = aa.compare_rigs(bones, rig_rb["bones"])
    sk_a = hkanim.load(skel_hkx).skeletons[0]
    hk_world = world_of(list(sk_a.parents), [
        (tuple(c * UNIT for c in (BIND_OVERRIDES_FO4.get(n) or sk_a.reference_pose[i][0])), aa.q_norm(sk_a.reference_pose[i][1]))
        for i, n in enumerate(sk_a.bones)])
    rig_world = world_of(parents, [(b["translation"], b["rotation"]) for b in rig_rb["bones"]])
    rest = {n: round(math.degrees(aa.q_angle(rig_rb["bones"][names.index(final_names[n])]["rotation"], aa.IDENTITY)), 6)
            for n in convert_handy.REBASE}
    report["rig"] = {"path": str(rig_path), "bones": len(rig_rb["bones"]), "precision": rig_rb["precision"],
                     "keys": {b["name"]: b["key"] for b in rig_rb["bones"] if b["key"] is not None},
                     "readback_max_translation_m": cmp_rig["max_translation"],
                     "readback_max_rotation_deg": math.degrees(cmp_rig["max_rotation"]),
                     "bind_world_position_vs_hkx_reference_max_m": max(
                         math.dist(hk_world[i][0], rig_world[i][0]) for i in range(len(sk_a.bones))),
                     "rest_rotation_deg_of_rebased_bones": rest,
                     "rest_rotation_deg_before": mrep["skeleton"]["rest_rotation_deg_before"],
                     "largest_rest_rotation_deg_com_pelvis": max(rest["COM"], rest["Pelvis"]),
                     "names_renamed": sum(1 for a, b in final_names.items() if a != b),
                     "names_unsafe": [n for n in names if not actor_skin.SAFE_BONE_NAME.match(n)],
                     "direct_at": {"parent": names[parents[names.index("DirectAt")]],
                                   "key": next(b["key"] for b in rig_rb["bones"] if b["name"] == "DirectAt"),
                                   "model_position_m": [round(c, 6) for c in rig_world[names.index("DirectAt")][0]],
                                   "com_model_position_m": [round(c, 6) for c in rig_world[names.index("COM")][0]],
                                   "model_rotation_deg": round(math.degrees(aa.q_angle(
                                       rig_world[names.index("DirectAt")][1], aa.IDENTITY)), 6)},
                     "names_equal_mesh_skeleton": names == list(skel_m.names)}
    pairs = pair_indices(names_src, parents_src)
    shapes = load_skinned_shapes(data)
    stretch_clips, kept_rb = {}, {}
    native_shapes: Dict[str, list] = {}          # group -> Fallout 4 part shapes as Fallout 4 skins them
    if mesh == "parts":
        raw_parts = convert_handy.read_codsworth_parts(fo4_mesh)
        for fname, inst in convert_handy.CODSWORTH_PARTS:
            for s in fo4_part_shapes(raw_parts[fname], inst, names_src):
                native_shapes.setdefault(s["group"], []).append(s)

    # ---------------------------------------------------------------- vanilla Mini Bot: root speeds, own-folder copies
    sfa = Ba2(str(sf_data / "Starfield - Animations.ba2"))
    van_rig = work / "minibota" / "skeleton.rig"
    van_rig.parent.mkdir(parents=True, exist_ok=True)
    van_rig.write_bytes(sfa.read(sfa.find(VAN_PREFIX + "characterassets/skeleton.rig")))
    speeds = {}
    for tag, stem in LOCOMOTION_FROM_MINIBOT.items():
        afp = work / "minibota" / (stem + ".af")
        afp.write_bytes(sfa.read(sfa.find(VAN_PREFIX + f"animations/{stem}.af")))
        rc = cal.read_clip(str(van_rig), str(afp))
        root = [b for b in rc["blocks"] if b["index"] == 0]
        t, q = aa.sample_block(root[0], rc["frame_count"] - 1)
        secs = (rc["frame_count"] - 1) / FPS
        speeds[tag] = [round(v / secs, 6) for v in t]
        if math.degrees(aa.q_angle(q, aa.IDENTITY)) > 0.01:
            raise Ra2Error(f"Mini Bot {stem} turns; not a straight locomotion clip")
    report["minibot_root_speed_m_s"] = speeds

    # ---------------------------------------------------------------- clips
    clip_dir = data / "Meshes" / Path(*HANDY.clips.split("\\"))
    clip_dir.mkdir(parents=True, exist_ok=True)
    cache: Dict[str, Tuple[Clip, dict]] = {}

    def source(rel: str) -> Clip:
        """A Fallout 4 clip on the SOURCE rig (skeleton.hkx frames and names); rebased only when written."""
        if rel not in cache:
            raw = fo4_anim.read(fo4_anim.find(FO4_ROBOT + "animations\\" + rel))
            base = source("Idle.hkx") if rel != "Idle.hkx" else None
            clip, st = decode_fo4_clip(raw, bones_src, sk_a.bones, base=base)
            clip.source = rel
            cache[rel] = (clip, st)
        return cache[rel][0]

    with esm.Plugin(str(sf_data / "Starfield.esm")) as p:
        templates = strafing_afx_templates(sfa, list(p.records("RACE")))
    fo4_info = {}
    clips_rep = []
    for cm in hr.HANDY_CLIP_MAP:
        if cm.how == "none":
            continue
        src = source(cm.fo4)
        if cm.fo4 not in fo4_info:
            fo4_info[cm.fo4] = hr.fo4_clip_info(fo4_anim.read(fo4_anim.find(FO4_ROBOT + "animations\\" + cm.fo4)))
        clip = Clip(src.frames, src.root, src.annotations, src.source)
        if cm.tag in TURN_CROP_DEG:
            clip = crop_turn(clip, TURN_CROP_DEG[cm.tag])
        if cm.how == "mirror":
            clip = mirror_clip(clip, bones_src, pairs)
        if cm.tag in LOCOMOTION_FROM_MINIBOT:
            clip = with_root_velocity(clip, speeds[cm.tag], f"vanilla Mini Bot {LOCOMOTION_FROM_MINIBOT[cm.tag]}.af speed")
        clip.finish()
        events = clip_events(cm, clip)
        rig_frames = to_rig_frames(clip.frames, parents_src, corr_q, extra_binds)
        res = aa.write_clip_files(cal, bones, poses_of_frames(rig_frames, bones), clip.n, clip_dir, cm.tag,
                                  keys_are="local", is_state=cm.is_state, events=events, stem=cm.filename)
        tpl = templates.get(cm.tag.lower())
        Path(res["afx"]).write_bytes(afx_vanilla(cm.tag, cm.filename + ".af", cm.is_state,
                                                 [(f, AFX_EVENT_SPELLING.get(n, n), pl) for f, n, pl in events], (),
                                                 tpl[1] if tpl else None, frame_count=clip.n))
        rc, rb = readback_local(cal, rig_path, Path(res["af"]))
        hdr = aa.read_af_header(Path(res["af"]).read_bytes())
        err = pose_errors(parents, names, rig_frames, rb)
        # the rebase moves nothing: world positions of the source poses and of the rig poses (exact, before writing)
        rebase_dist, rebase_f, rebase_b = world_position_difference(parents_src, clip.frames, parents, rig_frames,
                                                                    len(bones_src))
        rule_m, rule_bone = translation_rule_exposure(bones, rig_frames)
        # against A's decoded data (the source before any derivation; read-back mapped back to the source frames,
        # mirrored clips mirrored back first)
        rb_src = unrebase_frames(rb, parents_src, corr_q)
        rb_a = mirror_frames(rb_src, [(b["translation"], b["rotation"]) for b in bones_src], parents_src, pairs) \
            if cm.how == "mirror" else rb_src
        skip = ("Root",) if (cm.tag in LOCOMOTION_FROM_MINIBOT or cm.tag in TURN_CROP_DEG) else ()
        err_a = pose_errors(parents_src, names_src, src.frames[:clip.n], rb_a, skip=skip)
        stretch_clips[Path(res["af"]).stem] = edge_stretch(shapes, parents, names, rb)
        if Path(res["af"]).stem in {c[2] for c in NATIVE_CASES}:
            kept_rb[Path(res["af"]).stem] = rb
        native = native_vs_staged(native_shapes, clip.frames, names_src, parents_src, shapes, rb, names, parents) \
            if native_shapes else None
        side = aa.parse_afx(Path(res["afx"]).read_bytes())
        last_root = clip.root[-1]
        clips_rep.append({
            "rebase_world_max_m": rebase_dist, "translation_rule_difference_max_m": round(rule_m, 9),
            "translation_rule_bone": rule_bone,
            "stretch_max": max(v["ratio"] for v in stretch_clips[Path(res["af"]).stem].values()),
            "fo4_native": native,
            "tag": cm.tag, "file": Path(res["af"]).name, "fo4": cm.fo4, "how": cm.how, "notes": clip.notes,
            "frames": clip.n, "readback_frames": rc["frame_count"], "header": {k: hdr[k] for k in ("version", "bones", "frames", "kind")},
            "readback_rig_bones": len(rc["rig"]["bones"]), "blocks": res["blocks"],
            "root_end": {"xyz_m": [round(v, 4) for v in last_root[:3]], "yaw_deg": round(math.degrees(last_root[3]), 3)},
            "header_root_translation": [round(v, 4) for v in hdr["root_translation"]],
            "events": side["events"], "is_state": side["is_state"],
            "afx_template": tpl[0] if tpl else None,
            "afx_kept_elements": [n for n, _t in afx_elements(Path(res["afx"]).read_bytes())[0]
                                  if n not in ("is_state", "tag", "filename", "events")],
            "err_vs_written_poses": err, "err_vs_A_decoded": err_a,
            "err_vs_A_compares": ("mirror of the read-back against the unmirrored source" if cm.how == "mirror" else
                                  "read-back against the decoded source") + (", Root left out (rewritten)" if skip else "")
                                 + (", source = Idle composed with the additive clip" if cache[cm.fo4][1]["blend"] == "ADDITIVE" else ""),
            "source_stats": cache[cm.fo4][1]})
        if rc["frame_count"] != clip.n or hdr["frames"] != clip.n or hdr["bones"] != len(bones) or len(rc["rig"]["bones"]) != len(bones):
            raise Ra2Error(f"{cm.tag}: read-back frame or bone count differs")
    report["clips"] = clips_rep
    tags = {c["tag"] for c in clips_rep}
    missing = [t for t in REQUIRED_TAGS if t not in tags]
    if missing:
        raise Ra2Error(f"required tags not written: {missing}")
    report["clip_summary"] = {
        "written": len(clips_rep),
        "worst_vs_written": {k: max(c["err_vs_written_poses"][k] for c in clips_rep) for k in ("t_m", "r_deg", "model_mm")},
        "worst_vs_A": {k: max(c["err_vs_A_decoded"][k] for c in clips_rep) for k in ("t_m", "r_deg", "model_mm")},
        "rebase_world_max_m": max(c["rebase_world_max_m"] for c in clips_rep),
        "translation_rule_difference_max_m": max(c["translation_rule_difference_max_m"] for c in clips_rep),
        "translation_rule_bone": max(clips_rep, key=lambda c: c["translation_rule_difference_max_m"])["translation_rule_bone"],
        "required_tags": list(REQUIRED_TAGS)}
    report["deformation"] = summarize_stretch(stretch_clips, shapes)
    if native_shapes:
        nat = [c["fo4_native"] for c in clips_rep]
        report["deformation"]["fo4_native_all_clips"] = {
            "what": "Fallout 4's own skinning of every placed part on the poses written, against the staged mesh read "
                    "back, every clip / frame / shape group (worst edge ratio per frame)",
            "max_abs_diff": max(x["max_abs_diff"] for x in nat), "max_rel_diff": max(x["max_rel_diff"] for x in nat),
            "clips_native_over_limit": sorted(c["file"][:-3] for c in clips_rep if c["fo4_native"]["worst"] >= STRETCH_LIMIT)}
    if mesh == "parts":
        report["deformation"]["fo4_native"] = fo4_native_cases(
            mrep["placed"], convert_handy.read_codsworth_parts(fo4_mesh), shapes, clips_rep, kept_rb, source,
            names_src, parents_src, names, parents)

    # ---------------------------------------------------------------- manifests
    handy_manifests = hr.race_manifests(hr.HANDY_EDID, HANDY, fo4_info=fo4_info)
    written = hr.write_files(handy_manifests, str(data))
    race_v, bptd_v = hr.load_minibot(str(sf_data / "Starfield.esm"))
    vanilla = {}
    for n in sfa.names:
        low = n.lower().replace("\\", "/")
        if low.startswith("meshes/animtextdata/") and any(str(hr.manifest_key(g, f)) in low for g, f in hr.race_subgraph_sets(race_v) if f):
            vanilla[low[len("meshes/animtextdata/"):]] = sfa.read(sfa.find(n))
    gsd = sfa.read(sfa.find("meshes/animtextdata/generatedsubgraphdata/minibotarace.txt"))
    rows = [ln.split("\t") for ln in gsd.decode("cp1252").splitlines()[1:] if ln.strip()]
    for r in rows:      # the generated (ambush) row's key files
        k = hr.manifest_key(r[4], [x.strip() for x in r[5].split(",")])
        for n in sfa.names:
            low = n.lower().replace("\\", "/")
            if low.startswith("meshes/animtextdata/") and f"/{k}.txt" in low:
                vanilla[low[len("meshes/animtextdata/"):]] = sfa.read(sfa.find(n))
    own_files, own_rep = own_folder_manifests(vanilla, race_v, gsd, EDIDS[F_RACE_OWN])
    written += hr.write_files(own_files, str(data))
    report["manifests"] = {"handy_keys": {g: str(hr.manifest_key(g, f)) for g, f in HANDY.subgraphs()},
                           "handy_files": sorted(handy_manifests), "own_folder": own_rep, "own_files": sorted(own_files),
                           "stance_data_for_handy": "not written (pose unknown, D)"}

    # ---------------------------------------------------------------- own-folder Mini Bot: byte copies
    copied = 0
    for n in sfa.names:
        low = n.lower().replace("\\", "/")
        if not low.startswith(VAN_PREFIX):
            continue
        rest = low[len(VAN_PREFIX):]
        if rest == "characterassets/skeleton.rig":
            dst = data / "Meshes" / Path(*OWN_RIG.split("\\"))
        elif rest.startswith("animations/"):
            dst = data / "Meshes" / Path(*OWN_CLIPS.split("\\")) / Path(*rest[len("animations/"):].split("/"))
        else:
            raise Ra2Error(f"unexpected vanilla Mini Bot file {n}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        raw = sfa.read(sfa.find(n))
        dst.write_bytes(raw)
        if hashlib.sha256(dst.read_bytes()).digest() != hashlib.sha256(raw).digest():
            raise Ra2Error(f"{dst} is not byte-identical")
        copied += 1
    report["own_folder_copies"] = {"files": copied, "rig": OWN_RIG, "clips": OWN_CLIPS}

    # ---------------------------------------------------------------- plugin
    own = lambda local: (1 << 24) | local  # noqa: E731
    with esm.Plugin(str(sf_data / "Starfield.esm")) as p:
        group_order = list(p.groups)
        src = {}
        for g, fid in (("NPC_", SF_NPC_GARDEN), ("ARMA", SF_ARMA_GARDEN), ("ARMO", SF_ARMO_GARDEN)):
            src[g] = next(r for r in p.records(g) if r.formid == fid)
    recs, npc_rep = [], {}
    bone_map, extra_parts = renamed_body_parts(final_names)
    race_h = hr.build_race(race_v, own(F_RACE_HANDY), own(F_BPTD_HANDY), HANDY, name="Mr. Handy", bone_map=bone_map)
    race_h.subs = [(s, struct.pack("<I", own(F_ARMO_HANDY)) if s == b"WNAM" else d) for s, d in race_h.subs]
    recs += [race_h, hr.build_bptd(bptd_v, own(F_BPTD_HANDY), HANDY, bone_map=bone_map, extra_parts=extra_parts),
             copy_arma(src["ARMA"], own(F_ARMA_HANDY), EDIDS[F_ARMA_HANDY], own(F_RACE_HANDY), HANDY_MODEL),
             copy_armo(src["ARMO"], own(F_ARMO_HANDY), EDIDS[F_ARMO_HANDY], own(F_RACE_HANDY), own(F_ARMA_HANDY))]
    for fid_race, fid_arma, fid_armo, fid_npc, kw in (
            (F_RACE_REN, F_ARMA_REN, F_ARMO_REN, F_NPC_REN, {}),
            (F_RACE_OWN, F_ARMA_OWN, F_ARMO_OWN, F_NPC_OWN, {"rig": OWN_RIG, "clips": OWN_CLIPS})):
        recs += [copy_race(race_v, own(fid_race), EDIDS[fid_race], "Mini Bot", **kw),
                 copy_arma(src["ARMA"], own(fid_arma), EDIDS[fid_arma], own(fid_race)),
                 copy_armo(src["ARMO"], own(fid_armo), EDIDS[fid_armo], own(fid_race), own(fid_arma))]
    for fid_npc, fid_race, fid_armo, obnd in ((F_NPC_HANDY, F_RACE_HANDY, F_ARMO_HANDY, HANDY_OBND),
                                              (F_NPC_REN, F_RACE_REN, F_ARMO_REN, None),
                                              (F_NPC_OWN, F_RACE_OWN, F_ARMO_OWN, None)):
        r, rep = copy_npc(src["NPC_"], own(fid_npc), EDIDS[fid_npc], NPC_NAMES[fid_npc], own(fid_race), own(fid_armo), obnd)
        recs.append(r)
        npc_rep[EDIDS[fid_npc]] = rep
    (out / PLUGIN).write_bytes(plugin_bytes(recs, ["Starfield.esm"], group_order))
    report["plugin"] = {"file": PLUGIN, "records": {f"{r.formid:08X}": f"{r.sig.decode()} {r.edid}" for r in recs},
                        "npc_edits": npc_rep, "race_handy_changes": "D build_race + WNAM -> FO4SF_RA2Handy_Skin",
                        "body_part_bones": bone_map, "body_part_extra": [b for _t, b in extra_parts]}

    # ---------------------------------------------------------------- archive, batch files, manifest
    loose = sorted(p for p in data.rglob("*") if p.is_file())
    pairs_files = [(str(p.relative_to(data)).replace("/", "\\"), p.read_bytes()) for p in loose]
    report["ba2"] = pack_gnrl_ba2_v2(pairs_files, out / MAIN_BA2, starfield_dir)
    bat_dir = out / "bat"
    bat_dir.mkdir(exist_ok=True)
    for f, text in build_bats().items():
        (bat_dir / f).write_text(text, encoding="utf-8")
    manifest = {"probe": PROBE, "plugin": PLUGIN, "ba2": MAIN_BA2, "form_ids_local": {EDIDS[k]: f"{k:06X}" for k in EDIDS},
                "files": {}, "data_files": {}}
    for p in [out / PLUGIN, out / MAIN_BA2] + sorted(bat_dir.glob("*.txt")):
        manifest["files"][str(p.relative_to(out)).replace("/", "\\")] = {"sha256": sha256_file(p), "size_bytes": p.stat().st_size}
    for p in loose:
        manifest["data_files"][str(p.relative_to(data)).replace("/", "\\")] = {"sha256": sha256_file(p), "size_bytes": p.stat().st_size}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    report["verify"] = verify(out, dll=dll)
    if compare_with is not None:
        report["before"] = {"stage": str(compare_with), "deformation": deformation_check(compare_with, cal),
                            "rig": rig_summary(compare_with, cal)}
        report["compare_with_before"] = compare_bundles(compare_with, out, cal)
    (out / "report.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    if compare_with is not None:
        (out / "CHANGES.md").write_text(changes_md(out, report, manifest), encoding="utf-8")
    return report


def renamed_body_parts(final_names: Dict[str, str]):
    """handy_race's BONE_MAP and EXTRA_PARTS (Fallout 4 MrHandyBodyPartData bones) in the rig's final names."""
    return ({k: final_names.get(v, v) for k, v in hr.BONE_MAP.items()},
            tuple((t, final_names.get(b, b)) for t, b in hr.EXTRA_PARTS))


def rig_summary(stage: Path, cal=None, dll: Optional[str] = None) -> dict:
    """Bone count, names with characters other than letters / digits / '_', map keys and the COM / Pelvis rest
    rotations of a staged Handy rig (for before / after)."""
    cal = cal or aa.Calumi(dll)
    rb = cal.read_rig(str(Path(stage) / "Data" / "Meshes" / Path(*HANDY.skeleton_rig.split("\\"))))["bones"]
    rest = {b["name"]: round(math.degrees(aa.q_angle(b["rotation"], aa.IDENTITY)), 4) for b in rb
            if b["name"] in ("COM", "Pelvis")}
    return {"bones": len(rb), "names_with_other_characters": sum(1 for b in rb if not re.match(r"^[A-Za-z0-9_]+$", b["name"])),
            "keys": {b["name"]: b["key"] for b in rb if b["key"] is not None}, "rest_rotation_deg": rest}


def changes_md(out: Path, rep: dict, manifest: dict) -> str:
    """E2\\CHANGES.md: what changed against the earlier bundle, the measurements, and the SHA-256 of every output."""
    before, cmp_ = rep["before"], rep["compare_with_before"]
    dn, db = rep["deformation"], before["deformation"]
    rig = rep["rig"]
    L = [f"# RA2 Handy bundle: changes against {before['stage']}", "",
         "Built by `scripts/probes/stage_ra2_handy.py build --out <this folder> --compare-with <earlier bundle>` "
         "(worktree D:\\FO4SF-Worktrees\\claude-robot-anim, branch claude/robot-anim, uncommitted). Same plugin and "
         "archive names, same three NPCs and form ids (01000800-0100080C); only the Handy rig, clips, mesh and body-part "
         "names changed. The two Mini Bot actors (ra2b, ra2c) are unchanged.", "",
         "## 1. COM rest rotation rebased", "",
         f"- Rebased bones (identity parent-local rest; the turn folded into their children, every clip and the mesh "
         f"bind): {', '.join(rep['conventions']['rebased_bones'])}.",
         f"- Rest rotation before: {rig['rest_rotation_deg_before']} deg; after (read back from the .rig): "
         f"{rig['rest_rotation_deg_of_rebased_bones']} deg. Before bundle: {before['rig']['rest_rotation_deg']} deg.",
         f"- Exact check before writing (all {rep['clip_summary']['written']} clips, every frame, every bone): world "
         f"positions of the source poses and the rebased poses differ by at most {rep['clip_summary']['rebase_world_max_m']:.3g} m.",
         f"- Read-back proof (both bundles read through CALUMI, {len(cmp_['clips'])} clips, every frame, "
         f"{cmp_['bones_compared']} bones): model-space positions agree within {cmp_['max_position_mm']} mm "
         f"(worst {cmp_['where']}); world rotations agree within {cmp_['max_rotation_deg']} deg once the constant rest "
         f"correction of the rebased bones ({', '.join(cmp_['rebased_bones'])}) is applied.",
         f"- Largest difference between the two candidate translation-offset rules (t_b + q_b t_o against t_b + t_o) "
         f"over every bone and frame: {rep['clip_summary']['translation_rule_difference_max_m']:.3g} m "
         f"({rep['clip_summary']['translation_rule_bone']}); before: up to 1.271 m on COM (review F).", "",
         "## 2. Bone names", "",
         f"- {rig['names_renamed']} of 112 Fallout 4 names renamed ('|' and '-' -> '_'); names with other characters: "
         f"before {before['rig']['names_with_other_characters']}, after {len(rig['names_unsafe'])}. The same names are "
         "in the .rig, every clip block, the mesh skin bone lists and nodes, skeleton.nif, skeleton_ref.nif and the "
         "BPTD; the full map is in docs/actors/robot-animation.md and work/bone_names.json.",
         f"- BPTD / RACE bones: {rep['plugin']['body_part_bones']}, added parts {rep['plugin']['body_part_extra']}.", "",
         "## 3. DirectAt", "",
         f"- Map keys before {before['rig']['keys']}, after {rig['keys']}. DirectAt parent {rig['direct_at']['parent']}, "
         f"model position {rig['direct_at']['model_position_m']} m (COM {rig['direct_at']['com_model_position_m']}), "
         f"world rotation {rig['direct_at']['model_rotation_deg']} deg: as the Mini Bot's (child of C_Body on COM, "
         "identity). No clip animates it; it is in skeleton_ref.nif, not in the mesh NIF (as vanilla minibota_mesh.nif).",
         "", "## 4. Mesh: Codsworth's own Fallout 4 parts", "",
         f"- Source: {rep['mesh']['source']}. Shapes (merged by texture set, the five Codsworth .mat files unchanged): "
         + "; ".join(f"{k} {v['verts']} verts, wpv {v['weights_per_vertex']}, {v['bones']} bones, bind error "
                     f"{v['bind_pose_max_error_mm']} mm" for k, v in rep["mesh"]["shapes"].items()) + ".",
         f"- Parts placed: " + ", ".join(f"{p['part']}{'' if p['instance'] is None else '|' + str(p['instance'])}"
                                         f":{p['shape']}" for p in rep["mesh"].get("placed", [])) + ".",
         f"- Left out: " + (", ".join(f"{s['part']}|{s['instance']} {s['shape']} ({s['verts']} verts, {s['shader']})"
                                       for s in rep["mesh"].get("skipped", [])) or "nothing") + ".",
         f"- Bind consistency of every part on the rig bind: {rep['mesh'].get('bind_spread_max_fo4_units')} FO4 units.",
         f"- Deformation check (linear blend skinning with the read-back poses, every clip, every frame, edges over "
         f"{dn['min_edge_m']} m): worst before {db['worst']['ratio']}x ({db['worst']['clip']} frame {db['worst']['frame']}, "
         f"{db['worst']['shape']} {db['worst'].get('bones')}); after {dn['worst']['ratio']}x ({dn['worst']['clip']} "
         f"frame {dn['worst']['frame']}, {dn['worst']['shape']} {dn['worst'].get('bones')}). Clips at or over "
         f"{dn['limit']}x: before {len(db['over_limit'])}, after {len(dn['over_limit'])} (under {dn['limit']}x: "
         f"{dn['clips'] - len(dn['over_limit'])} of {dn['clips']}).",
         f"- Rigid pieces (edges whose two ends follow one bone with full weight; any change is a conversion error): "
         f"largest |length ratio - 1| over every clip and frame: after {dn['rigid_edges_worst_dev']}, before "
         f"{db.get('rigid_edges_worst_dev')}. The palm / Arm7 tear of the old mesh (25x) is gone.", "",
         "### Remaining stretch: Fallout 4's own seams", "",
         "Every edge above 1.6x now lies on a seam that Fallout 4's own part has: triangles whose corners follow "
         "different bones. Seam triangles per shape (heaviest bone of each corner):", ""]
    for k, v in dn["shapes"].items():
        L.append(f"- {k}: {v['tris']} triangles, seams {v.get('seam_triangles') or 'none'}")
    na = dn.get("fo4_native_all_clips")
    if na:
        L += ["", f"Every clip, every frame, every shape: Fallout 4's own skinning of the placed parts (their stored "
                  f"positions, skin-to-bone transforms and weights) on the poses written, against handy.nif on the clip "
                  f"read back through CALUMI: worst-edge ratios agree within {na['max_abs_diff']} "
                  f"({100 * na['max_rel_diff']:.3f} % relative). Clips whose Fallout 4 skinning is itself at or over "
                  f"{dn['limit']}x: {len(na['clips_native_over_limit'])}, the same set as the staged mesh: "
                  f"{na['clips_native_over_limit'] == dn['over_limit']}."]
    L += ["", "Fallout 4's own skinning of the same part (its stored positions, skin-to-bone transforms and weights) on the "
          "decoded Fallout 4 clip, against the same vertices of handy.nif on the clip read back through CALUMI "
          "(worst edge ratio per frame):", "", "| part, clip | Fallout 4 clip | Fallout 4 native worst (frame) | "
          "staged worst (frame) | per-frame max difference |", "|---|---|---|---|---|"]
    esc = lambda s: str(s).replace("|", "\\|")  # noqa: E731  (old bone names carry '|')
    for k, v in dn.get("fo4_native", {}).items():
        L.append(f"| {esc(k)} | {v['fo4_clip']} | {v['fo4_native_worst']} ({v['fo4_native_frame']}) | {v['staged_worst']} "
                 f"({v['staged_frame']}) | {v['per_frame_max_abs_diff']} |")
    L += ["", "So the staged Handy deforms as Fallout 4 deforms these parts on these frames. TorsoHandy blends 107 "
          "vertices between Chest, Ring and RingMesh (the junction of the ring band and the dome, 2.55 % of the torso "
          "area); FO4's turn clips spin Ring up to 125 deg (TurnLeft180) and 30 deg (TurnLeft, additive) about the body, "
          "so that band wrings. ArmsTypeA1 joins Arm4 and Arm5 with 13 rigidly weighted triangles per arm (Arm5 bends up "
          "to 143 deg in Death1, 132 deg in Claw\\Attack_3); PincherHand joins the palm and a finger with 12 (the finger "
          "closes 35 deg). Whether Fallout 4's behaviour graph masks Ring in the turns, and how visible these slivers are "
          "on screen, only the game can show.", "",
          "| clip | before (old mesh) | after | Fallout 4 skinning of the same poses | after, rigid pieces |",
          "|---|---|---|---|---|"]
    native = {c["file"][:-3]: c.get("fo4_native") or {} for c in rep["clips"]}
    for c in sorted(dn["per_clip"]):
        b = db["per_clip"].get(c, {})
        a = dn["per_clip"][c]
        L.append(f"| {c} | {b.get('ratio', '-')} {b.get('shape', '')} {esc('/'.join(b.get('bones') or []))} | {a['ratio']} "
                 f"{a['shape']} {'/'.join(a.get('bones') or [])} | {native.get(c, {}).get('worst', '-')} | {a['rigid_dev']} |")
    v = rep["verify"]
    L += ["", "## 5. Checks", "",
          f"- verify: {v['staged_files']} staged files, {v['ba2_entries']} archive entries ({v['data_files_in_ba2']} "
          f"data files byte-equal), {len(v['records'])} records, rig {v['rig_bones']} bones, names safe "
          f"{v.get('names_safe')}, keys {v.get('rig_keys')}.",
          f"- Clips: {rep['clip_summary']['written']} written and read back; worst against the written poses "
          f"{rep['clip_summary']['worst_vs_written']}; against the decoded Fallout 4 data {rep['clip_summary']['worst_vs_A']}.",
          "", "## SHA-256 of every output", "", "| file | bytes | sha256 |", "|---|---|---|"]
    for rel, meta in manifest["files"].items():
        L.append(f"| {rel} | {meta['size_bytes']} | {meta['sha256']} |")
    for rel, meta in manifest["data_files"].items():
        L.append(f"| Data\\{rel} | {meta['size_bytes']} | {meta['sha256']} |")
    for extra in ("manifest.json", "report.json"):
        p = out / extra
        L.append(f"| {extra} | {p.stat().st_size} | {sha256_file(p)} |")
    return "\n".join(L) + "\n"


# =============================================================================================== verify
def verify(stage: Path = OUT, dll: Optional[str] = None) -> dict:
    """Read-only: SHA-256 of every staged file, the plugin's masters / records / references, every loose Data file
    byte-equal inside the BA2 with correct entry hashes, the rig and every clip readable by the DLL, the batch rule."""
    stage = Path(stage)
    man = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
    for rel, meta in man["files"].items():
        p = stage / rel
        if not p.is_file() or sha256_file(p) != meta["sha256"]:
            raise Ra2Error(f"staged file missing or changed: {rel}")
    entries = verify_ba2_entry_hashes(stage / MAIN_BA2)
    arc = Ba2(str(stage / MAIN_BA2))
    for rel, meta in man["data_files"].items():
        raw = arc.read(rel)
        if hashlib.sha256(raw).hexdigest() != meta["sha256"]:
            raise Ra2Error(f"{MAIN_BA2}: {rel} differs from the staged loose file")
    with esm.Plugin(str(stage / PLUGIN)) as p:
        if p.masters != ["Starfield.esm"]:
            raise Ra2Error(f"masters {p.masters}")
        recs = {}
        for g, spans in p.groups.items():
            for start, end in spans:
                for item in p.walk(start, end):
                    if item[0] == "REC":
                        r = p.record_at(item[1])
                        recs[r.formid] = r
    want = {(1 << 24) | k: v for k, v in EDIDS.items()}
    got = {fid: r.edid for fid, r in recs.items()}
    if got != want:
        raise Ra2Error(f"plugin records {got} != {want}")
    refs = {}
    for fid, r in recs.items():
        for s in (b"RNAM", b"WNAM", b"GNAM", b"MODL"):
            for d in r.all(s):
                if len(d) == 4:
                    v, = struct.unpack("<I", d)
                    if v >> 24 == 1 and v not in recs:
                        raise Ra2Error(f"{r.edid} {s.decode()} -> {v:08X}, not in the plugin")
                    refs.setdefault(r.edid, {})[s.decode()] = f"{v:08X}"
    paths_ok = {}
    for fid in ((1 << 24) | F_RACE_HANDY, (1 << 24) | F_RACE_OWN):
        r = recs[fid]
        for s in (b"NAM5", b"DNAM", b"SAPT"):
            for d in r.all(s):
                if hr._is_text(d):
                    rel = "Meshes\\" + esm.zstring(d)
                    if s == b"NAM5":
                        paths_ok[f"{r.edid} {s.decode()} {rel}"] = arc.find(rel) is not None
                    else:
                        paths_ok[f"{r.edid} {s.decode()} {rel}"] = any(
                            n.lower().replace("/", "\\").startswith(rel.lower() + "\\") for n in arc.names)
    model = recs[(1 << 24) | F_ARMA_HANDY].get(b"MOD2")
    paths_ok["ARMA MOD2 Meshes\\" + esm.zstring(model)] = arc.find("Meshes\\" + esm.zstring(model)) is not None
    empty_ok = {k: v for k, v in paths_ok.items() if not v}
    # the Handy Furniture SAPT folder has no clip of its own (D's manifest plays them from the main folder): allowed
    empty_ok.pop(f"{EDIDS[F_RACE_HANDY]} SAPT Meshes\\{HANDY.furniture_clips}", None)
    if empty_ok:
        raise Ra2Error(f"record paths with nothing in the archive: {sorted(empty_ok)}")
    bats = {p.name: p.read_text(encoding="utf-8") for p in sorted((stage / "bat").glob("*.txt"))}
    p3 = validate_bats(bats)
    if sorted(bats) != sorted(BATS):
        raise Ra2Error(f"batch files {sorted(bats)}")
    # bone names: letters, digits and '_' only, in the BPTD and in every Handy NIF (no vanilla actor rig uses others)
    safe = re.compile(r"^[A-Za-z0-9_]+$")
    bptd = recs[(1 << 24) | F_BPTD_HANDY]
    bad = [f"BPTD {s.decode()} {esm.zstring(d)}" for s, d in bptd.subs
           if s in (b"BPTN", b"BPNN", b"BPNT", b"ENAM", b"FNAM") and hr._is_text(d)
           and not esm.zstring(d).lower().endswith(".nif") and not safe.match(esm.zstring(d))]
    from fo4sf import fo4skin, nif as nifmod
    for rel in (HANDY_NIF_REL, "meshes/fo4sf/actors/handy/characterassets/skeleton.nif",
                "meshes/fo4sf/actors/handy/characterassets/skeleton_ref.nif"):
        n = nifmod.parse((stage / "Data" / Path(*rel.split("/"))).read_bytes())
        bad += [f"{rel} {fo4skin._block_name(n, i).decode('latin-1')}" for i in range(len(n.blocks))
                if n.type_of(i) == "NiNode" and not safe.match(fo4skin._block_name(n, i).decode("latin-1"))]
    rig = stage / "Data" / "Meshes" / Path(*HANDY.skeleton_rig.split("\\"))
    rig_n, keys = None, None
    if aa.find_dll(dll):
        cal = aa.Calumi(dll)
        rb = cal.read_rig(str(rig))["bones"]
        rig_n = len(rb)
        keys = {b["name"]: b["key"] for b in rb if b["key"] is not None}
        if keys != RIG_KEYS:
            raise Ra2Error(f"rig map keys {keys} != {RIG_KEYS}")
        bad += [f"rig {b['name']}" for b in rb if not safe.match(b["name"])]
        for b in rb:
            if b["name"] in ("COM", "Pelvis") and math.degrees(aa.q_angle(b["rotation"], aa.IDENTITY)) > 0.01:
                raise Ra2Error(f"rig {b['name']} rest is turned {math.degrees(aa.q_angle(b['rotation'], aa.IDENTITY)):.3f} deg")
        for af in sorted((stage / "Data" / "Meshes" / Path(*HANDY.clips.split("\\"))).glob("*.af")):
            h = aa.read_af_header(af.read_bytes())
            if h["bones"] != rig_n or h["version"] != aa.AF_VERSION or h["kind"] != aa.AF_KIND_FULL:
                raise Ra2Error(f"{af.name}: header {h}")
            side = af.with_suffix(".afx").read_bytes()
            afx_elements(side)
            if aa.parse_afx(side)["filename"].lower() != af.name.lower():
                raise Ra2Error(f"{af.name}: its .afx names another file")
    if bad:
        raise Ra2Error(f"bone names with characters other than letters, digits and '_': {bad[:10]} ({len(bad)})")
    return {"staged_files": len(man["files"]), "ba2_entries": entries, "data_files_in_ba2": len(man["data_files"]),
            "records": {f"{k:08X}": v for k, v in sorted(got.items())}, "references": refs, "record_paths": paths_ok,
            "rig_bones": rig_n, "rig_keys": keys, "names_safe": not bad, "bats": p3}


# =============================================================================================== install / uninstall
def _default_plugins_txt() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / "Starfield" / "Plugins.txt"


def _tes4_flags(path: Path) -> Optional[int]:
    try:
        with path.open("rb") as fh:
            h = fh.read(24)
        return struct.unpack_from("<I", h, 8)[0] if h[:4] == b"TES4" else None
    except OSError:
        return None


IMPLICIT_FULL_MASTERS = ("Starfield.esm", "Constellation.esm", "OldMars.esm", "BlueprintShips-Starfield.esm",
                         "ShatteredSpace.esm")


def full_master_slot(data_dir: Path, lines: Sequence[str], target: str = PLUGIN) -> int:
    """Load-order index of `target` among full (not light / medium) plugins: implicit masters, then active lines."""
    seen, slot = set(), 0
    for name in IMPLICIT_FULL_MASTERS:
        fl = _tes4_flags(data_dir / name)
        if fl is not None and fl & 0x300 == 0:
            seen.add(name.casefold())
            slot += 1
    for raw in lines:
        ln = raw.strip()
        if not ln.startswith("*"):
            continue
        name = ln[1:].strip()
        if name.casefold() == target.casefold():
            return slot
        if name.casefold() in seen:
            continue
        fl = _tes4_flags(data_dir / name)
        if fl is not None and fl & 0x300 == 0:
            seen.add(name.casefold())
            slot += 1
    raise Ra2Error(f"{target} is not an active line of Plugins.txt")


def install(stage: Path, starfield_dir: Path, plugins_txt: Optional[Path] = None,
            min_free_gb: float = DEFAULT_MIN_FREE_GB, check_running=True) -> dict:
    """Copy the plugin and its BA2 into Data, append *FO4SF_RA2Handy.esm to Plugins.txt (original kept in
    <stage>\\backup_pre_ra2), write the batch files stamped with the real load-order slot into the game folder, and a
    receipt. Refuses to overwrite anything."""
    if check_running:
        check_starfield_not_running()
    verify(stage)
    check_free_space_gb(starfield_dir, min_free_gb)
    data = starfield_dir / "Data"
    if not data.is_dir():
        raise Ra2Error(f"no Data folder in {starfield_dir}")
    receipt_path = data / RECEIPT
    if receipt_path.exists():
        raise Ra2Error(f"already installed ({receipt_path}); uninstall first")
    ptxt = plugins_txt or _default_plugins_txt()
    orig = ptxt.read_bytes() if ptxt.is_file() else None
    lines = orig.decode("utf-8-sig").splitlines() if orig is not None else []
    backup = stage / "backup_pre_ra2"
    if backup.exists() and any(backup.iterdir()):
        raise Ra2Error(f"non-empty backup folder {backup}; inspect or uninstall first")
    backup.mkdir(parents=True, exist_ok=True)
    if orig is not None:
        (backup / "Plugins.txt").write_bytes(orig)
    added, bats = [], []
    try:
        for name in (PLUGIN, MAIN_BA2):
            dst = data / name
            if dst.exists():
                raise Ra2Error(f"refusing to overwrite {dst}")
            shutil.copy2(stage / name, dst)
            added.append({"name": name, "sha256": sha256_file(dst)})
        low = {ln.strip().lstrip("*").casefold() for ln in lines if ln.strip()}
        appended = []
        if PLUGIN.casefold() not in low:
            appended.append(f"*{PLUGIN}")
        new_lines = lines + appended
        slot = full_master_slot(data, new_lines)
        for f, text in build_bats(slot).items():
            dst = starfield_dir / f
            if dst.exists():
                raise Ra2Error(f"refusing to overwrite {dst}")
            dst.write_text(text, encoding="utf-8")
            bats.append({"name": f, "sha256": sha256_file(dst)})
        ptxt.parent.mkdir(parents=True, exist_ok=True)
        ptxt.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        materials_active = MATERIALS_PLUGIN.casefold() in {ln.strip()[1:].casefold() for ln in new_lines if ln.strip().startswith("*")}
        receipt = {"probe": PROBE, "stage_dir": str(stage), "backup_dir": str(backup), "plugins_txt": str(ptxt),
                   "plugins_txt_had_file": orig is not None, "plugins_txt_sha256_after": sha256_file(ptxt),
                   "appended_plugins_lines": appended, "slot_hex": f"{slot:02X}",
                   "form_ids": {EDIDS[k]: f"{slot:02X}{k:06X}" for k in EDIDS}, "added_data_files": added,
                   "added_root_bats": bats, "materials_plugin_active": materials_active,
                   "warning": None if materials_active else
                   f"{MATERIALS_PLUGIN} is not active: the Handy .mat and textures (its Main.ba2) will not load"}
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
    changed it since; otherwise drop only the appended line."""
    if check_running:
        check_starfield_not_running()
    data = starfield_dir / "Data"
    receipt_path = data / RECEIPT
    if not receipt_path.is_file():
        raise Ra2Error(f"not installed ({receipt_path} missing)")
    rc = json.loads(receipt_path.read_text(encoding="utf-8"))
    for b in rc["added_root_bats"]:
        p = starfield_dir / b["name"]
        if p.is_file():
            if sha256_file(p) != b["sha256"]:
                raise Ra2Error(f"refusing to delete changed {p}")
            p.unlink()
    for a in rc["added_data_files"]:
        p = data / a["name"]
        if p.is_file():
            if sha256_file(p) != a["sha256"]:
                raise Ra2Error(f"refusing to delete changed {p}")
            p.unlink()
    ptxt = plugins_txt or Path(rc["plugins_txt"])
    backup = Path(rc["backup_dir"])
    how = "unchanged"
    if ptxt.is_file() and sha256_file(ptxt) == rc["plugins_txt_sha256_after"]:
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
    b.add_argument("--starfield", type=Path, default=STARFIELD_DIR)
    b.add_argument("--fo4-data", type=Path, default=FO4_DATA)
    b.add_argument("--dll", default=None)
    b.add_argument("--mesh", choices=MESH_SOURCES, default="parts")
    b.add_argument("--compare-with", type=Path, default=None,
                   help="an earlier bundle (read only): measure against it and write CHANGES.md")
    v = sub.add_parser("verify")
    v.add_argument("--stage-dir", type=Path, default=OUT)
    d = sub.add_parser("deform", help="edge-stretch check of a staged bundle (every clip, every frame)")
    d.add_argument("--stage-dir", type=Path, default=OUT)
    c = sub.add_parser("compare", help="model-space bone positions of two staged bundles, every clip and frame")
    c.add_argument("--old", type=Path, required=True)
    c.add_argument("--new", type=Path, required=True)
    i = sub.add_parser("install")
    i.add_argument("--stage-dir", type=Path, default=OUT)
    i.add_argument("--starfield", type=Path, required=True)
    i.add_argument("--plugins-txt", type=Path, default=None)
    i.add_argument("--min-free-gb", type=float, default=DEFAULT_MIN_FREE_GB)
    u = sub.add_parser("uninstall")
    u.add_argument("--starfield", type=Path, required=True)
    u.add_argument("--plugins-txt", type=Path, default=None)
    s = sub.add_parser("status")
    s.add_argument("--starfield", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "build":
        rep = build(a.out, a.starfield, a.fo4_data, a.dll, mesh=a.mesh, compare_with=a.compare_with)
        print(json.dumps({"out": str(a.out), "rig": rep["rig"], "clip_summary": rep["clip_summary"], "ba2": rep["ba2"],
                          "plugin": rep["plugin"]["records"], "verify": rep["verify"]["rig_bones"],
                          "deformation_worst": rep["deformation"]["worst"],
                          "over_limit": rep["deformation"]["over_limit"],
                          "compare_with_before": {k: v for k, v in rep.get("compare_with_before", {}).items()
                                                  if k != "clips"}}, indent=1, default=str))
    elif a.cmd == "verify":
        print(json.dumps(verify(a.stage_dir), indent=1))
    elif a.cmd == "deform":
        rep = deformation_check(a.stage_dir)
        print(json.dumps({k: v for k, v in rep.items() if k != "per_clip_shape"}, indent=1, default=str))
    elif a.cmd == "compare":
        print(json.dumps(compare_bundles(a.old, a.new), indent=1, default=str))
    elif a.cmd == "install":
        print(json.dumps(install(a.stage_dir, a.starfield, a.plugins_txt, a.min_free_gb), indent=1))
    elif a.cmd == "uninstall":
        print(json.dumps(uninstall(a.starfield, a.plugins_txt), indent=1))
    else:
        print(json.dumps(status(a.starfield), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
