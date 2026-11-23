"""Fallout 4 creatures in Starfield: race, body part data, clip -> graph tag maps and animation manifests, generalised
from the Mr. Handy path (handy_race.py, docs/actors/robot-animation.md; method and per-creature choices in
docs/actors/creature-animation.md).

What this module does (pure: no file access except where a reader is passed in):
  * CreaturePaths: where a converted creature's skeleton, rig, mesh and clips live (Data\\Meshes-relative, as the
    RACE / ARMA records store them).
  * build_creature_race: a copy of a Starfield template RACE with our EDID / name / body part data / skin, the
    skeleton and rig paths, every clip folder (DNAM, SAPT) re-pointed at ours, the attack-hit bone names (ZNAM)
    mapped to our bones, and the attacks we have no clip for dropped (ATKD + ATKE + ATKW groups). Every other
    subrecord stays byte for byte (handy_race.build_race does the same for the Mini Bot template).
  * build_creature_bptd: the template's body part data with its bones mapped to ours (handy_race.build_bptd), checked
    against the rig's bone names.
  * CreatureClip / CreatureSpec / CREATURES: the Fallout 4 clip -> Starfield graph tag proposal per creature.
  * creature_events: Fallout 4 annotations -> Starfield .afx events (FootLeft / FootRight keep their names: Starfield's
    own Hexapod clips use exactly these; preHitFrame / weaponSwing / HitFrame / WeaponFire via handy_race.sf_event;
    Ragdoll -> AddRagdollToWorld + RemoveCharacterControllerFromWorld at that frame).
  * mirror_pairs: left / right partner of every bone (name swap L <-> R, Left <-> Right, checked by the mirrored rest
    position), for building right-hand clips from Fallout 4's left-only ones.
  * graph_tag_sets / creature_manifests / key collisions: the four per-sub-graph manifest files for our race's own
    (graph, folders) keys (handy_race.manifest_key, proven on 1,889 keys), listing only clips whose tag the graph plays
    (measured from the vanilla clip lists of every creature race that uses that graph).

NOT PROVEN until run in game: that a Starfield template race's graph plays a Fallout 4 creature's clips on its own rig
(proven for the Mini Bot graph with the Handy, robot-animation.md section 8, not for Hexapod / Flyer / NonStrafing
races); that dropping attack entries without a clip keeps the race's combat working; the character controller size
copied from the physics template's skeleton.nif.
"""
import math
import re
import struct
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from . import handy_race as hr
from .planet import esm

GRAPH_DIR = hr.GRAPH_DIR
STRAFING_GRAPH = hr.STRAFING_GRAPH
NONSTRAFING_GRAPH = GRAPH_DIR + "Creature_NonStrafing.agx"
FLYING_GRAPH = GRAPH_DIR + "Creature_Flying.agx"
FURNITURE_GRAPH = hr.FURNITURE_GRAPH
MANIFEST_DIRS = ("animationfiledata", "animationoffsets", "animationstancedata", "dynamicidledata")
GAMEPLAY_EVENTS = ("HitFrame", "preHitFrame", "weaponSwing", "WeaponFire")   # baked into animationoffsets (Mini Bot)


class CreatureError(ValueError):
    pass


# ------------------------------------------------------------------------------------------------ paths
@dataclass
class CreaturePaths:
    """Data\\Meshes-relative paths of one converted creature (the forms the records store). `name` is a folder name
    (letters and digits)."""
    name: str

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", self.name):
            raise CreatureError(f"creature folder name {self.name!r} must be letters and digits")

    @property
    def skeleton_nif(self) -> str:
        return f"FO4SF\\Actors\\{self.name}\\CharacterAssets\\skeleton.nif"

    @property
    def skeleton_rig(self) -> str:
        return f"FO4SF\\Actors\\{self.name}\\CharacterAssets\\skeleton.rig"

    @property
    def skeleton_ref(self) -> str:
        return f"FO4SF\\Actors\\{self.name}\\CharacterAssets\\skeleton_ref.nif"

    @property
    def mesh(self) -> str:
        return f"FO4SF\\Actors\\{self.name}\\{self.name.lower()}.nif"

    @property
    def clips(self) -> str:
        return f"Actors\\FO4SF\\{self.name}\\Animations"

    def data_rel(self, meshes_rel: str) -> str:
        """The Data-relative path (with the Meshes\\ prefix) of a Meshes-relative record path, '/' separated."""
        return ("Meshes\\" + meshes_rel).replace("\\", "/")


def rewrite_folder(text: str, old: str, new: str) -> str:
    """`text` with every case-insensitive occurrence of folder `old` replaced by `new` (the Mini Bot own-folder probe's
    rule, stage_ra2_handy.rewrite_folder)."""
    return re.sub(re.escape(old), lambda _m: new, text, flags=re.I)


# ------------------------------------------------------------------------------------------------ records
def _text(d: bytes) -> Optional[str]:
    return esm.zstring(d) if hr._is_text(d) else None


def attack_groups(subs) -> List[Tuple[int, int, Optional[str]]]:
    """[(first index, end index, ATKE tag)] of every attack in a RACE's subrecords: an ATKD and the ATK* subrecords
    right after it (Starfield.esm: ATKD, ATKE, ATKW per attack)."""
    out = []
    i = 0
    while i < len(subs):
        if subs[i][0] == b"ATKD":
            j = i + 1
            while j < len(subs) and subs[j][0].startswith(b"ATK") and subs[j][0] != b"ATKD":
                j += 1
            tag = next((esm.zstring(d) for s, d in subs[i:j] if s == b"ATKE"), None)
            out.append((i, j, tag))
            i = j
        else:
            i += 1
    return out


def race_clip_folder(race: esm.Record) -> str:
    d = race.get(b"DNAM")
    if d is None or _text(d) is None:
        raise CreatureError(f"{race.edid}: no DNAM clip folder")
    return esm.zstring(d)


def build_creature_race(template: esm.Record, formid: int, bptd_formid: int, skin_formid: int, paths: CreaturePaths,
                        name: str, edid: str, bone_map: Dict[str, str], attack_tags: Optional[Iterable[str]] = None,
                        main_folder_for_empty_sets: Iterable[str] = ()) -> Tuple[esm.Record, dict]:
    """A copy of `template` (a Starfield creature RACE) for a converted creature. Changes: EDID; FULL / SNAM plain
    `name` and DESC empty (our plugin is not localized); GNAM -> bptd_formid; WNAM -> skin_formid; ANAM / NAM5 -> our
    skeleton.nif / .rig; DNAM and every SAPT re-pointed from the template's clip folder to paths.clips (sub-folders
    keep their tail); ZNAM bone names through bone_map (a name missing from bone_map raises); with attack_tags, the
    attack groups whose ATKE tag is not in it are dropped. main_folder_for_empty_sets: (lower-case) folders that hold
    none of our clips; a sub-graph whose folder list is only such folders gets paths.clips appended as one more SAPT
    (the Mini Bot / Handy Furniture set lists its furniture folder and the main folder). Returns (record, report)."""
    old = race_clip_folder(template)
    keep = None if attack_tags is None else set(attack_tags)
    empty = {f.lower() for f in main_folder_for_empty_sets}
    subs = list(template.subs)
    rep = {"template": f"{template.formid:08X} {template.edid}", "dropped_attacks": [], "kept_attacks": [], "znam": {},
           "sapt": [], "appended_main_folder": []}
    if keep is not None:
        drop = set()
        for a, b, tag in attack_groups(subs):
            if tag in keep:
                rep["kept_attacks"].append(tag)
            else:
                rep["dropped_attacks"].append(tag)
                drop.update(range(a, b))
        if not rep["kept_attacks"]:
            raise CreatureError(f"{edid}: no attack of {template.edid} has a clip")
        subs = [x for i, x in enumerate(subs) if i not in drop]
    out = []
    pending: List[Tuple[int, List[str]]] = []          # (index in out of the last SAPT of the current set, its folders)
    cur_last, cur_folders = None, []

    def close_set():
        if cur_last is not None:
            pending.append((cur_last, list(cur_folders)))

    for s, d in subs:
        if s == b"EDID":
            d = esm.zbytes(edid)
        elif s in (b"FULL", b"SNAM") and len(d) == 4:
            d = esm.zbytes(name)
        elif s == b"DESC" and len(d) == 4:
            d = esm.zbytes("")
        elif s == b"GNAM":
            d = struct.pack("<I", bptd_formid)
        elif s == b"WNAM":
            d = struct.pack("<I", skin_formid)
        elif s == b"ANAM" and _text(d) is not None:
            d = esm.zbytes(paths.skeleton_nif)
        elif s == b"NAM5":
            d = esm.zbytes(paths.skeleton_rig)
        elif s == b"DNAM" and _text(d) is not None:
            d = esm.zbytes(rewrite_folder(esm.zstring(d), old, paths.clips))
        elif s == b"ZNAM" and _text(d) is not None:
            bone = esm.zstring(d)
            if bone not in bone_map:
                raise CreatureError(f"{edid}: template attack bone {bone!r} has no partner in bone_map")
            rep["znam"][bone] = bone_map[bone]
            d = esm.zbytes(bone_map[bone])
        elif s == b"SGNM":
            close_set()
            cur_last, cur_folders = None, []
        elif s == b"SAPT":
            new = rewrite_folder(esm.zstring(d), old, paths.clips)
            if new.lower() == esm.zstring(d).lower() and not new.lower().startswith(paths.clips.lower()):
                raise CreatureError(f"{edid}: SAPT {esm.zstring(d)!r} is not below the template folder {old!r}")
            rep["sapt"].append(new)
            d = esm.zbytes(new)
            cur_folders.append(new)
            cur_last = len(out)
        out.append((s, d))
    close_set()
    for at, folders in reversed(pending):
        if folders and all(f.lower() in empty for f in folders) and paths.clips.lower() not in {f.lower() for f in folders}:
            out.insert(at + 1, (b"SAPT", esm.zbytes(paths.clips)))
            rep["appended_main_folder"].append(folders)
    rec = esm.Record(b"RACE", formid, out, template.flags & ~esm.COMPRESSED, template.vc, template.version,
                     template.unknown)
    return rec, rep


def build_creature_bptd(template: esm.Record, formid: int, edid: str, paths: CreaturePaths, bone_map: Dict[str, str],
                        rig_bones: Sequence[str]) -> esm.Record:
    """The template's body part data with its parts on our bones (handy_race.build_bptd with no extra parts). Every
    bone the template names must be in bone_map and every mapped bone in rig_bones (raises otherwise)."""
    used = bptd_bones(template)
    missing = sorted(b for b in used if b not in bone_map)
    if missing:
        raise CreatureError(f"{edid}: template body part bones without a partner: {missing}")
    rec = hr.build_bptd(template, formid, paths, bone_map=bone_map, extra_parts=(), edid=edid)
    bad = sorted(b for b in bptd_bones(rec) if b not in set(rig_bones))
    if bad:
        raise CreatureError(f"{edid}: body part bones not in the rig: {bad}")
    return rec


def bptd_bones(rec: esm.Record) -> List[str]:
    """Every bone name a BPTD's parts name (BPNN, BPNT; NAM4 / ENAM / FNAM texts that are not .nif paths)."""
    out = []
    for s, d in rec.subs:
        t = _text(d)
        if t is None:
            continue
        if s in (b"BPNN", b"BPNT") or (s in (b"NAM4", b"ENAM", b"FNAM") and not t.lower().endswith(".nif")):
            if t not in out:
                out.append(t)
    return out


def race_bone_names(rec: esm.Record) -> List[str]:
    return [esm.zstring(d) for s, d in rec.subs if s == b"ZNAM" and _text(d) is not None]


# ------------------------------------------------------------------------------------------------ clip maps
@dataclass(frozen=True)
class CreatureClip:
    """One Starfield clip of a creature: graph tag, file stem, Fallout 4 source (path below the creature's
    animations folder; None = no clip) and how it is built (direct / reuse / mirror). crop_deg: a turn clip cut at
    that yaw (stage_ra2_handy.crop_turn). sync: add SyncLeftFoot / SyncRightFoot at the first FootLeft / FootRight
    (Starfield locomotion loops carry both). add_events: (where, name), where = start | end | ragdoll | fire (the
    first Fallout 4 weaponFire frame). frames: keep only the first N frames (a death built from a pose).
    drop_events: Starfield event names left out of this clip."""
    tag: str
    filename: str
    fo4: Optional[str]
    how: str = "direct"
    is_state: int = 0
    crop_deg: Optional[float] = None
    sync: bool = False
    add_events: Tuple[Tuple[str, str], ...] = ()
    note: str = ""
    frames: Optional[int] = None
    drop_events: Tuple[str, ...] = ()


TURN = (("start", "SetOrientBegin"), ("end", "SetOrientEnd"))
DEATH = (("ragdoll", "AddRagdollToWorld"), ("ragdoll", "RemoveCharacterControllerFromWorld"))
DEATH_AT_ONCE = (("start", "AddRagdollToWorld"), ("start", "RemoveCharacterControllerFromWorld"))
GETUP = (("end", "GetUpEnd"),)
FLINCH = (("end", "FlinchEnd"),)
FIRE_AS_MELEE = (("fire", "weaponSwing"), ("fire", "preHitFrame"), ("fire", "HitFrame"))


def loop(tag, fo4, how="direct", filename=None, note=""):
    return CreatureClip(tag, filename or tag, fo4, how, 1, sync=True, note=note)


def clip(tag, fo4, how="direct", **kw):
    return CreatureClip(tag, kw.pop("filename", tag), fo4, how, **kw)


@dataclass(frozen=True)
class CreatureSpec:
    """Everything that differs between creatures. fo4_folder: the folder under meshes\\actors\\ of Fallout4 -
    Animations.ba2 / Fallout4 - Meshes.ba2; mesh: NIF below its CharacterAssets; template_race: the Starfield race
    whose graph, attack data and body part layout are copied; physics_race: the race whose skeleton.nif lends its
    character controller and COM body; bone_map: template bone (ZNAM, BPTD parts) -> ours (final rig names);
    mesh: NIF path below Meshes\\Actors\\; anim_folders: folders below Meshes\\Actors\\ searched in order for a
    clip (default <fo4_folder>\\Animations); event_map: Fallout 4 annotation -> the name creature_events reads."""
    key: str
    name: str
    fo4_folder: str
    fo4_race: str
    mesh: str
    template_race: str
    physics_race: str
    clips: Tuple[CreatureClip, ...]
    bone_map: Dict[str, str]
    exclude_shapes: str = r"cap"                 # dismemberment caps: Fallout 4 draws them only on a severed limb
    strip_prefix: str = ""                       # Dogmeat_Root -> Root
    template_reason: str = ""
    bat: str = ""
    anim_folders: Tuple[str, ...] = ()
    event_map: Tuple[Tuple[str, str], ...] = ()

    @property
    def clip_folders(self) -> Tuple[str, ...]:
        return self.anim_folders or (self.fo4_folder + "\\Animations",)


RADROACH_CLIPS = (
    CreatureClip("Idle", "Idle", "Idle.hkx", is_state=1),
    CreatureClip("Idle_Flavor01", "Relaxed_Idle_Flavor01", "Idle_CleanAntennas.hkx"),
    CreatureClip("Idle_Flavor02", "Relaxed_Idle_Flavor02", "Idle_Look.hkx"),
    CreatureClip("Idle_Flavor03", "Relaxed_Idle_Flavor03", "Idle_CleanBLegs.hkx"),
    CreatureClip("Idle_Flavor04", "Relaxed_Idle_Flavor04", "Idle_Feed.hkx"),
    CreatureClip("Threat_Intimidate01", "Threat_Intimidate01", "Aggro_Warning.hkx", is_state=1),
    CreatureClip("Threat_Assess01", "Threat_Assess01", "Aggro_WarnAttack.hkx", is_state=1),
    loop("WalkForward", "WalkForward.hkx"),
    loop("WalkBackward", "WalkBackward.hkx"),
    loop("WalkLeft", "Left.hkx", note="Fallout 4's only side step (1.28 m/s)"),
    loop("WalkRight", "Left.hkx", how="mirror"),
    loop("RunForward", "RunForward.hkx"),
    loop("JogForward", "RunForward.hkx", how="reuse"),
    loop("RunBackward", "RunBackward.hkx"),
    loop("JogBackward", "RunBackward.hkx", how="reuse"),
    CreatureClip("TurnInPlace_Left90", "TurnInPlace_Left90", "TurnLeft90.hkx", add_events=TURN),
    CreatureClip("TurnInPlace_Left180", "TurnInPlace_Left180", "TurnLeft180.hkx", add_events=TURN),
    CreatureClip("TurnInPlace_Left30", "TurnInPlace_Left30", "TurnLeft90.hkx", how="reuse", crop_deg=30.0,
                 add_events=TURN),
    CreatureClip("TurnInPlace_Right90", "TurnInPlace_Right90", "TurnLeft90.hkx", how="mirror", add_events=TURN),
    CreatureClip("TurnInPlace_Right180", "TurnInPlace_Right180", "TurnLeft180.hkx", how="mirror", add_events=TURN),
    CreatureClip("TurnInPlace_Right30", "TurnInPlace_Right30", "TurnLeft90.hkx", how="mirror", crop_deg=30.0,
                 add_events=TURN),
    CreatureClip("MeleeAttack01", "MeleeAttack01", "Attack1.hkx"),
    CreatureClip("MeleeAttack02", "MeleeAttack02", "Attack2.hkx"),
    CreatureClip("MeleeAttackPower01", "MeleeAttackPower01", "Attack3.hkx", note="leaping bite, 5.2 m forward"),
    CreatureClip("MeleeAttack_Bite01", "MeleeAttack_Bite01", "Attack4.hkx", note="standing bite"),
    CreatureClip("MeleeAttack_Bite02", "MeleeAttack_Bite02", "Attack2.hkx", how="reuse"),
    CreatureClip("MeleeAttackPower_Bite01", "MeleeAttackPower_Bite01", "Attack3.hkx", how="reuse"),
    CreatureClip("DodgeBack", "DodgeBack", "DodgeBack.hkx"),
    CreatureClip("EvadeLeft", "EvadeLeft", "EvadeLeft.hkx"),
    CreatureClip("EvadeRight", "EvadeRight", "EvadeLeft.hkx", how="mirror"),
    CreatureClip("DodgeLeft", "DodgeLeft", "EvadeLeft.hkx", how="reuse"),
    CreatureClip("DodgeRight", "DodgeRight", "EvadeLeft.hkx", how="mirror"),
    CreatureClip("StaggerForward", "StaggerForward", "StaggerForward.hkx"),
    CreatureClip("StaggerBackwardSmall", "StaggerBackwardSmall", "StaggerSmall.hkx"),
    CreatureClip("StaggerBackwardMedium", "StaggerBackwardMedium", "StaggerMedium.hkx"),
    CreatureClip("StaggerBackwardLarge", "StaggerBackwardLarge", "StaggerLarge.hkx"),
    CreatureClip("StaggerLeft", "StaggerLeft", "StaggerLeft.hkx"),
    CreatureClip("StaggerRight", "StaggerRight", "StaggerLeft.hkx", how="mirror"),
    CreatureClip("Flinch_Torso01", "Flinch_Torso01", "HitReaction_Left.hkx", is_state=1, add_events=FLINCH),
    CreatureClip("Flinch_Torso02", "Flinch_Torso02", "HitReaction_Left.hkx", how="mirror", is_state=1,
                 add_events=FLINCH),
    CreatureClip("Death_Backward01", "Death_Backward01", "Death1.hkx", is_state=1, add_events=DEATH),
    CreatureClip("Death_Forward01", "Death_Forward01", "Death2.hkx", is_state=1, add_events=DEATH),
    CreatureClip("Death_Left01", "Death_Left01", "Death3.hkx", is_state=1, add_events=DEATH),
    CreatureClip("Death_Right01", "Death_Right01", "Death3.hkx", how="mirror", is_state=1, add_events=DEATH),
    CreatureClip("Death_Moving_Forward01", "Death_Moving_Forward01", "Death2.hkx", how="reuse", is_state=1,
                 add_events=DEATH),
    CreatureClip("GetUp_Left", "GetUp_Left", "GetUp_Left.hkx", add_events=GETUP),
    CreatureClip("GetUp_Right", "GetUp_Right", "GetUp_Left.hkx", how="mirror", add_events=GETUP),
    CreatureClip("GetUp_Back", "GetUp_Back", "GetUp_Back.hkx", add_events=GETUP),
    CreatureClip("GetUp_Front", "GetUp_Front", "GetUp_Back.hkx", how="reuse", add_events=GETUP),
    CreatureClip("JumpRunForwardFall", "JumpRunForwardFall", "JunpFall.hkx", note="Fallout 4's own file name"),
    CreatureClip("JumpRunForwardFallLoop", "JumpRunForwardFallLoop", "JunpFall.hkx", how="reuse", is_state=1),
)

RADROACH_BONES = {
    # HexapodABodyPartData parts and HexapodARace attack bones -> the radroach rig (FO4 names; '0' front arm pair,
    # '1' middle legs, '2' back legs, by rest position: 0* y +12.5, 1* y +5.4, 2* y -3.8 FO4 units)
    "Root": "Root", "COM": "COM", "C_Spine": "Spine1", "C_Spine2": "Spine2", "C_Head": "Head", "C_Head2": "Head",
    "L_LegFrontBase": "0LArm1", "L_LegFront2": "0LArm2", "L_LegFront3": "0LArm3",
    "R_LegFrontBase": "0RArm1", "R_LegFront2": "0RArm2", "R_LegFront3": "0RArm3",
    "L_LegMidBase": "1LLeg1", "L_LegMid3": "1LLeg3", "R_LegMidBase": "1RLeg1", "R_LegMid3": "1RLeg3",
    "L_LegBackBase": "2LLeg1", "L_LegBack2": "2LLeg2", "R_LegBackBase": "2RLeg1", "R_LegBack3": "2RLeg3",
    "C_spine4": "Head", "C_Tail": "RadRoachTail1",
}

BLOATFLY_CLIPS = (
    clip("Idle", "Idle.hkx", is_state=1, sync=True),
    clip("Idle_Flavor01", "Idle_1.hkx"), clip("Idle_Flavor02", "Idle_2.hkx"),
    clip("Idle_Flavor03", "Idle_3.hkx"), clip("Idle_Flavor04", "Idle_4.hkx"),
    loop("RunForward", "RunForward.hkx"),
    loop("WalkForward", "RunForward2.hkx", note="Fallout 4 flies at one speed (5.7 m/s); its second forward loop"),
    loop("JogForward", "RunForward3.hkx"),
    loop("SoarForward", "RunForward.hkx", how="reuse"),
    loop("RunBackward", "RunBackward.hkx"), loop("WalkBackward", "RunBackward.hkx", how="reuse"),
    loop("RunLeft", "RunLeft.hkx"), loop("RunRight", "RunLeft.hkx", how="mirror"),
    loop("WalkLeft", "RunLeft.hkx", how="reuse"), loop("WalkRight", "RunLeft.hkx", how="mirror"),
    clip("TurnInPlace_Left90", "TurnLeft.hkx", add_events=TURN),
    clip("TurnInPlace_Left180", "TurnLeft180.hkx", add_events=TURN),
    clip("TurnInPlace_Left30", "TurnLeft.hkx", "reuse", crop_deg=30.0, add_events=TURN),
    clip("TurnInPlace_Right90", "TurnLeft.hkx", "mirror", add_events=TURN),
    clip("TurnInPlace_Right180", "TurnLeft180.hkx", "mirror", add_events=TURN),
    clip("TurnInPlace_Right30", "TurnLeft.hkx", "mirror", crop_deg=30.0, add_events=TURN),
    clip("TurnLeft", "TurnLeft.hkx", "reuse"), clip("TurnRight", "TurnLeft.hkx", "mirror"),
    clip("FireSingle_Mouth1", "RangedAttack.hkx", note="larva spit: weaponFire -> WeaponFire"),
    clip("MeleeAttack01", "RangedAttack.hkx", "reuse", add_events=FIRE_AS_MELEE, drop_events=("WeaponFire",),
         note="Fallout 4's bloatfly has no melee clip: its spit, the hit at the fire frame (race attack data)"),
    clip("StaggerForward", "StaggerForward.hkx"), clip("StaggerBackwardSmall", "StaggerSmall.hkx"),
    clip("StaggerBackwardMedium", "StaggerSmall.hkx", "reuse"), clip("StaggerBackwardLarge", "StaggerSmall.hkx", "reuse"),
    clip("StaggerLeft", "StaggerLeft.hkx"), clip("StaggerRight", "StaggerLeft.hkx", "mirror"),
    clip("Death_Backward01", "Idle.hkx", "reuse", is_state=1, frames=2, add_events=DEATH_AT_ONCE,
         note="Fallout 4 has no bloatfly death clip (it ragdolls): two idle frames, ragdoll at frame 0"),
    clip("Death_Forward01", "Idle.hkx", "reuse", is_state=1, frames=2, add_events=DEATH_AT_ONCE),
    clip("Death_Left01", "Idle.hkx", "reuse", is_state=1, frames=2, add_events=DEATH_AT_ONCE),
    clip("Death_Right01", "Idle.hkx", "reuse", is_state=1, frames=2, add_events=DEATH_AT_ONCE),
    clip("Death_Moving_Forward01", "Idle.hkx", "reuse", is_state=1, frames=2, add_events=DEATH_AT_ONCE),
)

BLOATFLY_BONES = {
    # MantaABodyPartData parts and MantaARace attack bones -> the bloatfly rig
    "Root": "Root", "COM": "COM", "C_Spine": "Spine", "C_Spine2": "Rib", "C_Spine3": "Neck",
    "R_wingA": "RWing", "L_wingA": "LWing", "C_spine4": "Head", "C_Tail": "Tail1",
}

MOLERAT_FEET = (("FootFront", "FootLeft"), ("FootBack", "FootRight"))
MOLERAT_CLIPS = (
    clip("Idle", "Idle.hkx", is_state=1),
    clip("Idle_Flavor01", "Idle_Sniff.hkx"), clip("Idle_Flavor02", "Idle_Yawn.hkx"),
    clip("Idle_Flavor03", "Idle_Stand.hkx"), clip("Idle_Flavor04", "Idle_Dig.hkx"),
    clip("Threat_Intimidate01", "Warning1.hkx", is_state=1), clip("Threat_Assess01", "Warning2.hkx", is_state=1),
    loop("WalkForward", "WalkForward.hkx"), loop("WalkBackward", "WalkBackward.hkx"),
    loop("RunForward", "RunForward.hkx"), loop("JogForward", "RunForward.hkx", how="reuse"),
    clip("TurnInPlace_Left90", "TurnL90_InPlace.hkx", add_events=TURN),
    clip("TurnInPlace_Right90", "TurnR90_InPlace.hkx", add_events=TURN),
    clip("TurnInPlace_Left180", "TurnL180_InPlace.hkx", add_events=TURN),
    clip("TurnInPlace_Right180", "TurnR180_InPlace.hkx", add_events=TURN),
    clip("TurnInPlace_Left30", "TurnL30_InPlace.hkx", add_events=TURN),
    clip("TurnInPlace_Right30", "TurnR30_InPlace.hkx", add_events=TURN),
    clip("MeleeAttack01", "Attack1.hkx"), clip("MeleeAttack02", "Attack4.hkx"),
    clip("MeleeAttack_Bite01", "Attack8.hkx", note="standing ankle bite"),
    clip("MeleeAttack_Bite02", "Attack4.hkx", "reuse"),
    clip("MeleeAttackPower01", "Attack5.hkx", note="running attack, 9.4 m"),
    clip("MeleeAttackPower_Bite01", "Attack9.hkx", note="jump up and forward"),
    clip("MeleeAttack_Head01", "Attack2.hkx", note="jump attack, 30 deg left"),
    clip("MeleeAttack_Head02", "Attack3.hkx", note="jump attack, 30 deg right"),
    clip("MeleeAttack_Left90", "Attack6.hkx", add_events=TURN),
    clip("MeleeAttack_Right90", "Attack6.hkx", "mirror", add_events=TURN),
    clip("MeleeAttack_Left180", "Attack7.hkx", add_events=TURN),
    clip("MeleeAttack_Right180", "Attack7.hkx", "mirror", add_events=TURN),
    clip("EvadeLeft", "EvadeLeft.hkx"), clip("EvadeRight", "EvadeLeft.hkx", "mirror"),
    clip("DodgeLeft", "EvadeLeft.hkx", "reuse"), clip("DodgeRight", "EvadeLeft.hkx", "mirror"),
    clip("StaggerForward", "StaggerForwardSmall.hkx"),
    clip("StaggerBackwardSmall", "StaggerMedium.hkx", "reuse"), clip("StaggerBackwardMedium", "StaggerMedium.hkx"),
    clip("StaggerBackwardLarge", "StaggerLarge.hkx"),
    clip("StaggerLeft", "StaggerLeft.hkx"), clip("StaggerRight", "StaggerLeft.hkx", "mirror"),
    clip("CriticalHit", "CriticalHit_Torso.hkx", "reuse", is_state=1),
    clip("CriticalHit_Head01", "CriticalHit_Head.hkx", is_state=1),
    clip("CriticalHit_Head02", "CriticalHit_Head02.hkx", is_state=1),
    clip("CriticalHit_Torso01", "CriticalHit_Torso.hkx", is_state=1),
    clip("CriticalHit_Torso02", "CriticalHit_Torso02.hkx", is_state=1),
    clip("CriticalHit_LeftLeg", "CriticalHit_LLeg.hkx", is_state=1),
    clip("CriticalHit_RightLeg", "CriticalHit_RLeg.hkx", is_state=1),
    clip("Death_Backward01", "Death.hkx", is_state=1, add_events=DEATH),
    clip("Death_Backward02", "Death2.hkx", is_state=1, add_events=DEATH),
    clip("Death_Backward03", "Death3.hkx", is_state=1, add_events=DEATH),
    clip("Death_Forward01", "DeathForward.hkx", is_state=1, add_events=DEATH),
    clip("Death_Left01", "DeathLeft1.hkx", is_state=1, add_events=DEATH),
    clip("Death_Right01", "DeathRight1.hkx", is_state=1, add_events=DEATH),
    clip("Death_Moving_Forward01", "DeathForwardRun1.hkx", is_state=1, add_events=DEATH),
    clip("Death_Moving_Forward02", "DeathForwardRun2.hkx", is_state=1, add_events=DEATH),
    clip("GetUp_Left", "GetUp_Left.hkx", add_events=GETUP), clip("GetUp_Right", "GetUp_Right.hkx", add_events=GETUP),
    clip("TunnelStart", "TunnelEnter.hkx", note="burrows in"), clip("TunnelStop", "TunnelExit.hkx", note="digs out"),
)

MOLERAT_BONES = {
    # HexapodABodyPartData parts (front and middle leg parts both on the mole rat's front legs) and attack bones
    "Root": "Root", "COM": "COM", "C_Spine": "Spine2", "C_Spine2": "Spine4", "C_Head": "Head", "C_Head2": "Jaw",
    "L_LegFrontBase": "Front_LLegCollarbone", "L_LegFront2": "Front_LLeg1", "L_LegFront3": "Front_LLeg2",
    "R_LegFrontBase": "Front_RLegCollarbone", "R_LegFront2": "Front_RLeg1", "R_LegFront3": "Front_RLeg2",
    "L_LegMidBase": "Front_LLeg1", "L_LegMid3": "Front_LLegAnkle", "R_LegMidBase": "Front_RLeg1",
    "R_LegMid3": "Front_RLegAnkle", "L_LegBackBase": "Back_LLeg1", "L_LegBack2": "Back_LLeg2",
    "R_LegBackBase": "Back_RLeg1", "R_LegBack3": "Back_RLegAnkle", "C_spine4": "Head", "C_Tail": "Tail1",
}

DOG_FOLDERS = ("ViciousDog\\Animations", "Dogmeat\\Animations\\Default\\Neutral", "Dogmeat\\Animations")
DOG_CLIPS = (
    clip("Idle", "Idle.hkx", is_state=1),
    clip("Idle_Flavor01", "HeadTilt_Left.hkx"), clip("Idle_Flavor02", "Inspect.hkx"),
    clip("Idle_Taunt01", "AttackIdle.hkx", is_state=1, note="Fallout 4's growling combat idle"),
    loop("WalkForward", "WalkForward.hkx"), loop("WalkBackward", "WalkBackwards.hkx"),
    loop("JogForward", "TrotForward.hkx"), loop("RunForward", "Locomotion\\RunForward.hkx"),
    loop("Sprint", "Locomotion\\TrotFast.hkx"),
    clip("TurnInPlace_Left90", "Turns\\TurnL90_InPlace.hkx", add_events=TURN),
    clip("TurnInPlace_Right90", "Turns\\TurnR90_InPlace.hkx", add_events=TURN),
    clip("TurnInPlace_Left180", "Turns\\TurnL180_InPlace.hkx", add_events=TURN),
    clip("TurnInPlace_Right180", "Turns\\TurnR180_InPlace.hkx", add_events=TURN),
    clip("TurnInPlace_Left30", "Turns\\TurnL30_InPlace.hkx", add_events=TURN),
    clip("TurnInPlace_Right30", "Turns\\TurnR30_InPlace.hkx", add_events=TURN),
    clip("MeleeAttack01", "Attack1.hkx"), clip("MeleeAttack02", "Attack2.hkx"),
    clip("MeleeAttack_Bite01", "Attack1.hkx", "reuse"), clip("MeleeAttack_Bite02", "Attack2.hkx", "reuse"),
    clip("MeleeAttackPower01", "AttackPowerStanding.hkx", note="jumping bite"),
    clip("MeleeAttackPower_Bite01", "AttackPowerForward.hkx", note="running, jumping bite (9.8 m)"),
    clip("StaggerForward", "Stagger_Small_Forward.hkx"), clip("StaggerBackwardSmall", "Stagger_Small.hkx"),
    clip("StaggerBackwardMedium", "Stagger_Medium.hkx"), clip("StaggerBackwardLarge", "Stagger_Large.hkx"),
    clip("StaggerLeft", "Stagger_Medium.hkx", "reuse"), clip("StaggerRight", "Stagger_Medium.hkx", "reuse"),
    clip("CriticalHit", "CritFront_Head.hkx", is_state=1), clip("CriticalHit_Torso", "CritFront_Chest.hkx", is_state=1),
    clip("CriticalHit_Legs", "CritFront_LegL.hkx", is_state=1),
    clip("Death_Backward01", "DeathStanding1.hkx", is_state=1, add_events=DEATH),
    clip("Death_Backward02", "DeathStanding2.hkx", is_state=1, add_events=DEATH),
    clip("Death_Backward03", "DeathStanding3.hkx", is_state=1, add_events=DEATH),
    clip("Death_Forward01", "DeathForward1.hkx", is_state=1, add_events=DEATH),
    clip("Death_Left01", "DeathLeft1.hkx", is_state=1, add_events=DEATH),
    clip("Death_Right01", "DeathRight1.hkx", is_state=1, add_events=DEATH),
    clip("Death_Moving_Forward01", "DeathMoving1.hkx", is_state=1, add_events=DEATH),
    clip("GetUp_Left", "GetUp_Left.hkx", add_events=GETUP),
    clip("GetUp_Right", "GetUp_Left.hkx", "mirror", add_events=GETUP),
    clip("JumpRunForwardFall", "Fall.hkx"), clip("JumpRunForwardFallLoop", "Fall.hkx", "reuse", is_state=1),
    clip("JumpRunLand", "Fall_Land.hkx"),
)

DOG_BONES = {
    # QuadrupedCBodyPartData parts and QuadrupedCRace attack bones -> the dog rig (Dogmeat_ prefix stripped)
    "Root": "Root", "COM": "COM", "C_Spine": "Spine1", "C_Spine3": "Spine3", "C_Spine5": "Ribcage",
    "C_Neck1": "Neck1", "C_Head1": "Head", "C_Tail1": "Tail1",
    "L_Hip": "Rear_LLeg1", "L_BackFemur": "Rear_LLeg2", "L_Foot": "Rear_LLegAnkle",
    "R_Hip": "Rear_RLeg1", "R_BackTibia": "Rear_RLeg2", "R_Ankle": "Rear_RLegAnkle",
    "L_FrontHip": "Front_LLegCollarbone", "L_Thigh": "Front_LLeg1",
    "R_FrontHip": "Front_RLegCollarbone", "R_Thigh": "Front_RLeg1",
}

DEATHCLAW_CLIPS = (
    clip("Idle", "Deathclaw_Idle.hkx", is_state=1),
    clip("Idle_Flavor01", "Deathclaw_SpecialIdleScratchGround.hkx"),
    clip("Idle_Flavor02", "Deathclaw_SpecialIdleTongueDetect.hkx"), clip("Idle_Flavor03", "Deathclaw_SpecialIdleA.hkx"),
    clip("Idle_Taunt01", "Deathclaw_IdleTauntRoar.hkx", is_state=1),
    clip("Threat_Intimidate01", "Deathclaw_IdleTauntStomp.hkx", is_state=1),
    clip("Threat_Assess01", "Deathclaw_IdleTaunt.hkx", is_state=1),
    loop("WalkForward", "Deathclaw_WalkForward.hkx"), loop("WalkBackward", "Deathclaw_WalkBack.hkx"),
    loop("WalkLeft", "Deathclaw_WalkLeft.hkx"), loop("WalkRight", "Deathclaw_WalkRight.hkx"),
    loop("RunForward", "Deathclaw_RunForward.hkx"), loop("JogForward", "Deathclaw_RunForward.hkx", how="reuse"),
    loop("Sprint", "Deathclaw_SprintForward.hkx"),
    clip("RunForward_Start", "Deathclaw_RunForward_Start.hkx"),
    clip("TurnInPlace_Left90", "Deathclaw_TurnLeft90.hkx", add_events=TURN),
    clip("TurnInPlace_Right90", "Deathclaw_TurnRight90.hkx", add_events=TURN),
    clip("TurnInPlace_Left30", "Deathclaw_TurnLeft90.hkx", "reuse", crop_deg=30.0, add_events=TURN),
    clip("TurnInPlace_Right30", "Deathclaw_TurnRight90.hkx", "reuse", crop_deg=30.0, add_events=TURN),
    clip("MeleeAttack01", "Deathclaw_AttackLeft.hkx"), clip("MeleeAttack02", "Deathclaw_AttackRight.hkx"),
    clip("MeleeAttackPower01", "Deathclaw_AttackPowerForward.hkx"),
    clip("MeleeAttack_Bite01", "Deathclaw_AttackLeftSideSwipe.hkx", note="running swipe"),
    clip("MeleeAttack_Bite02", "Deathclaw_AttackRightSideSwipe.hkx", note="running swipe"),
    clip("MeleeAttack_Head01", "Deathclaw_AttackPowerHornRam.hkx"),
    clip("MeleeAttackPower_Head01", "Deathclaw_AttackPowerJumpSlash.hkx", note="15.7 m leap"),
    clip("MeleeAttack_Tail01", "Deathclaw_AttackPowerComboTail.hkx"),
    clip("MeleeAttackPower_Tail01", "Deathclaw_AttackPowerSpinSlashAOE.hkx"),
    clip("EvadeLeft", "Deathclaw_EvadeForwardLeft.hkx"), clip("EvadeRight", "Deathclaw_EvadeForwardRight.hkx"),
    clip("StaggerForward", "Deathclaw_StaggerForwardSmall.hkx"),
    clip("StaggerBackwardSmall", "Deathclaw_StaggerSmall.hkx"),
    clip("StaggerBackwardMedium", "Deathclaw_StaggerSmall.hkx", "reuse"),
    clip("StaggerBackwardLarge", "Deathclaw_StaggerLarge.hkx"),
    clip("CriticalHit", "Deathclaw_CritHitFace.hkx", is_state=1),
    clip("CriticalHit_Torso", "Deathclaw_CritHitChest.hkx", is_state=1),
    clip("CriticalHit_Arms", "Deathclaw_CritHitLeftArm.hkx", is_state=1),
    clip("CriticalHit_Legs", "Deathclaw_CritHitLeftLeg.hkx", is_state=1),
    clip("Death_Backward01", "Deathclaw_DeathAnimationA.hkx", is_state=1, add_events=DEATH),
    clip("Death_Forward01", "Deathclaw_DeathAnimationB.hkx", is_state=1, add_events=DEATH),
    clip("GetUp_Left", "Deathclaw_GetUpFromFaceDown.hkx", add_events=GETUP),
    clip("GetUp_Right", "Deathclaw_GetUpFromFaceUp.hkx", add_events=GETUP),
    clip("JumpRunForwardFall", "Deathclaw_JumpFall.hkx"),
    clip("JumpRunForwardFallLoop", "Deathclaw_JumpFallLoop.hkx", is_state=1),
    clip("JumpRunLand", "Deathclaw_JumpLand.hkx"),
)

DEATHCLAW_BONES = {
    # BipedABodyPartData parts and BipedARace attack bones -> the deathclaw rig
    "Root": "Root", "COM": "COM", "R_Thigh": "RThigh", "L_Thigh": "LThigh", "R_Foot": "RFoot", "L_Foot": "LFoot",
    "L_BicepsFront": "LArmUpperArm", "L_ForearmFront": "LArmForeArm",
    "R_BicepsFront": "RArmUpperArm", "R_ForearmFront": "RArmForeArm",
    "C_Neck1": "NeckRoot", "C_Neck2": "Neck01", "C_Spine": "SpineRoot", "C_Chest": "SpineControl",
    "C_Spine2": "Spine02", "C_Head": "Head", "C_Jaw": "Jaw", "C_Tail1": "Tail1",
    "AnimObjectA": "Weapon",                     # BipedA's prop bone -> the deathclaw's right-hand Weapon node
}

CREATURES: Dict[str, CreatureSpec] = {
    "radroach": CreatureSpec(
        key="radroach", name="Radroach", fo4_folder="RadRoach", fo4_race="RadRoachRace",
        mesh="RadRoach\\CharacterAssets\\RadRoach.nif",
        template_race="HexapodARace", physics_race="MiniBotARace", clips=RADROACH_CLIPS, bone_map=RADROACH_BONES,
        template_reason="six-legged melee biter: HexapodARace plays Creature_Strafing (the graph the Mini Bot and the "
                        "Handy proved in game) and its attack data are bites / claws / head / tail on a six-legged body; "
                        "its clips carry FootLeft / FootRight like Fallout 4's",
        bat="ra5roach.txt"),
    "bloatfly": CreatureSpec(
        key="bloatfly", name="Bloatfly", fo4_folder="Bloatfly", fo4_race="BloatflyRace",
        mesh="Bloatfly\\CharacterAssets\\Bloatfly.nif", template_race="MantaARace", physics_race="MantaARace",
        clips=BLOATFLY_CLIPS, bone_map=BLOATFLY_BONES,
        template_reason="flying ranged pest: MantaARace plays Creature_Flying (flight movement, its skeleton.nif "
                        "controller) and is the only Creature_Flying race whose clips include FireSingle_Mouth1 "
                        "(a spit / shot), FlyerARace has none",
        bat="ra5fly.txt"),
    "molerat": CreatureSpec(
        key="molerat", name="Molerat", fo4_folder="Molerat", fo4_race="MoleratRace",
        mesh="Molerat\\CharacterAssets\\Molerat.nif", template_race="HexapodARace", physics_race="MiniBotARace",
        clips=MOLERAT_CLIPS, bone_map=MOLERAT_BONES, exclude_shapes=r"cap|dirtydirt",
        event_map=MOLERAT_FEET,
        template_reason="burrowing biter: Creature_Strafing (proven in game) plays TunnelStart / TunnelStop, which "
                        "Fallout 4's TunnelEnter / TunnelExit fill, and HexapodARace's bites, head attacks and "
                        "90 / 180 degree turn attacks match the mole rat's ten attacks; physics from the Mini Bot "
                        "(the small controller the Handy ran with)",
        bat="ra5rat.txt"),
    "dog": CreatureSpec(
        key="dog", name="Dog", fo4_folder="Dogmeat", fo4_race="ViciousDogRace",
        mesh="ViciousDog\\ViciousDog.nif", template_race="QuadrupedCRace", physics_race="QuadrupedCRace",
        clips=DOG_CLIPS, bone_map=DOG_BONES, strip_prefix="Dogmeat_", anim_folders=DOG_FOLDERS,
        event_map=MOLERAT_FEET,
        template_reason="dog-sized quadruped biter: QuadrupedCRace (COM 0.66 m, the size of Fallout 4's dog) plays "
                        "Creature_NonStrafing with bites and power bites; NOT proven in game for a converted rig",
        bat="ra5dog.txt"),
    "deathclaw": CreatureSpec(
        key="deathclaw", name="Deathclaw", fo4_folder="Deathclaw", fo4_race="DeathclawRace",
        mesh="Deathclaw\\Deathclaw.nif", template_race="BipedARace", physics_race="BipedARace",
        clips=DEATHCLAW_CLIPS, bone_map=DEATHCLAW_BONES, exclude_shapes=r"cap|hots",
        template_reason="large biped clawer: BipedARace (COM 2.0 m against the deathclaw's 1.93 m) plays "
                        "Creature_NonStrafing with claw / head / tail attacks; NOT proven in game for a converted rig",
        bat="ra5claw.txt"),
}


# ------------------------------------------------------------------------------------------------ events
def creature_events(clip: CreatureClip, annotations: Sequence[Tuple[float, str]], frame_count: int,
                    fps: float = 30.0, event_map: Optional[Dict[str, str]] = None) -> List[Tuple[int, str, str]]:
    """[(frame, name, payload)] of one clip, sorted: Fallout 4 annotations renamed through event_map first
    (FootFront -> FootLeft ...), FootLeft / FootRight kept, the melee / fire events of handy_race.sf_event, Ragdoll ->
    the DEATH events (else at the last frame), clip.add_events (fire = the first weaponFire frame), with clip.sync the
    Sync events at the first FootLeft / FootRight frame (frame 0 / the middle when the clip has none), and
    clip.drop_events removed."""
    last = frame_count - 1
    event_map = event_map or {}

    def fr(t):
        return min(last, max(0, int(round(t * fps))))
    evs, ragdoll, fire, feet = set(), None, None, {"FootLeft": [], "FootRight": []}
    for t, text in annotations:
        text = event_map.get(text, text)
        if text in feet:
            evs.add((fr(t), text))
            feet[text].append(fr(t))
        elif text.lower() == "ragdoll":
            ragdoll = fr(t) if ragdoll is None else min(ragdoll, fr(t))
        else:
            name = hr.sf_event(text)
            if name:
                evs.add((fr(t), name))
                if name == "WeaponFire":
                    fire = fr(t) if fire is None else min(fire, fr(t))
    at = {"start": 0, "end": last, "ragdoll": last if ragdoll is None else ragdoll,
          "fire": last if fire is None else fire}
    for where, name in clip.add_events:
        if where not in at:
            raise CreatureError(f"{clip.tag}: event place {where!r} unknown")
        evs.add((at[where], name))
    if clip.sync:
        evs.add((min(feet["FootLeft"]) if feet["FootLeft"] else 0, "SyncLeftFoot"))
        evs.add((min(feet["FootRight"]) if feet["FootRight"] else last // 2, "SyncRightFoot"))
    return [(f, n, "") for f, n in sorted(evs) if n not in clip.drop_events]


def mirror_event_name(name: str) -> str:
    """A mirrored clip's foot events swap sides."""
    swap = {"FootLeft": "FootRight", "FootRight": "FootLeft", "SyncLeftFoot": "SyncRightFoot",
            "SyncRightFoot": "SyncLeftFoot"}
    return swap.get(name, name)


# ------------------------------------------------------------------------------------------------ left / right
def _swap_candidates(name: str) -> List[str]:
    out = []
    for i, ch in enumerate(name):
        if ch in "LR":
            out.append(name[:i] + ("R" if ch == "L" else "L") + name[i + 1:])
    for a, b in (("Left", "Right"), ("Right", "Left"), ("left", "right"), ("right", "left")):
        if a in name:
            out.append(name.replace(a, b))
    return out


def mirror_pairs(names: Sequence[str], parents: Sequence[int], world: Sequence[Sequence[float]],
                 tol: float) -> Tuple[List[int], dict]:
    """Partner index of every bone: a name with one L <-> R (or Left <-> Right) swapped that exists and whose rest
    position is closest to this bone's mirrored (x -> -x) rest position, accepted within `tol` (skeleton units); a bone
    with no such name under a paired parent takes the unpaired child of the parent's partner nearest its mirrored
    position (Weapon under RArmHand <-> WeaponLeft under LArmHand); otherwise the bone is its own partner. Raises when
    the pairing is not symmetric or a partner hangs under a bone that is not its parent's partner (the condition
    stage_ra2_handy.mirror_frames needs). Returns (pairs, report with the largest rest asymmetry, the bones paired by
    position only and the off-centre bones left on their own)."""
    idx = {n: i for i, n in enumerate(names)}
    pairs: List[Optional[int]] = [None] * len(names)
    asym, alone, by_position = 0.0, [], []

    def mirrored(i):
        return (-world[i][0], world[i][1], world[i][2])
    for i, n in enumerate(names):
        if pairs[i] is not None:
            continue
        best, bd = None, None
        for c in _swap_candidates(n):
            j = idx.get(c)
            if j is None or j == i:
                continue
            d = math.dist(mirrored(i), world[j])
            if bd is None or d < bd:
                best, bd = j, d
        if best is None or bd > tol:
            best, bd = None, None
            p = parents[i]
            if p >= 0 and pairs[p] is not None and pairs[p] != p:
                for j in range(len(names)):
                    if j != i and parents[j] == pairs[p] and pairs[j] is None:
                        d = math.dist(mirrored(i), world[j])
                        if d <= tol and (bd is None or d < bd):
                            best, bd = j, d
                if best is not None:
                    by_position.append(f"{n}<->{names[best]}")
        if best is not None:
            pairs[i] = best
            if pairs[best] is None:
                pairs[best] = i
            asym = max(asym, bd)
        else:
            pairs[i] = i
            if abs(world[i][0]) > tol:
                alone.append(n)
    for i, j in enumerate(pairs):
        if pairs[j] != i:
            raise CreatureError(f"bone {names[i]} pairs with {names[j]}, which pairs with {names[pairs[j]]}")
        pi, pj = parents[i], parents[j]
        if (pi < 0) != (pj < 0) or (pi >= 0 and pairs[pi] != pj):
            raise CreatureError(f"bone {names[i]}: partner {names[j]} hangs under a bone that is not its parent's partner")
    return pairs, {"pairs": sum(1 for i, j in enumerate(pairs) if j > i), "largest_rest_asymmetry": round(asym, 6),
                   "paired_by_position": by_position, "off_centre_without_partner": alone}


# ------------------------------------------------------------------------------------------------ manifests
def key_of_path(path: str) -> Optional[int]:
    """The u64 of an animtextdata manifest path (.../<digits>.txt), else None."""
    m = re.search(r"[\\/](\d+)\.txt$", path)
    return int(m.group(1)) if m else None


def vanilla_manifest_keys(names: Iterable[str]) -> Dict[str, set]:
    """{folder: {keys}} of every manifest file of the four per-sub-graph folders in an archive name list."""
    out = {d: set() for d in MANIFEST_DIRS}
    for n in names:
        low = n.lower().replace("\\", "/")
        if not low.startswith("meshes/animtextdata/"):
            continue
        parts = low.split("/")
        if len(parts) == 4 and parts[2] in out:
            k = key_of_path(low)
            if k is not None:
                out[parts[2]].add(k)
    return out


def key_collisions(our_keys: Iterable[int], vanilla: Dict[str, set]) -> Dict[str, List[int]]:
    """{folder: [our keys that a vanilla manifest file already uses]}; empty lists when there is no collision."""
    ours = set(our_keys)
    return {d: sorted(ours & ks) for d, ks in vanilla.items()}


def parse_file_data(raw: bytes) -> Tuple[int, List[str]]:
    """(key, clip paths) of an animationfiledata file."""
    lines = raw.decode("cp1252").split("\n")
    if lines[0] != "3" or lines[1] != "1":
        raise CreatureError("not an animationfiledata file")
    key, count = int(lines[2]), int(lines[3])
    clips = [c for c in lines[4:] if c]
    if len(clips) != count:
        raise CreatureError(f"animationfiledata {key}: {len(clips)} clips for count {count}")
    return key, clips


def graph_tag_sets(races: Sequence[esm.Record], read_manifest, read_afx_tag, graphs: Iterable[str]) -> Dict[str, set]:
    """{graph lower: tags} played by each graph, measured: for every (graph, folders) set of `races` (RACE records)
    whose graph is in `graphs`, the vanilla animationfiledata/<key>.txt (read_manifest(key) -> bytes or None) lists
    clip paths; read_afx_tag(clip path) gives each one's tag."""
    want = {g.lower() for g in graphs}
    out: Dict[str, set] = {g: set() for g in want}
    seen = set()
    for r in races:
        for g, folders in hr.race_subgraph_sets(r):
            if g.lower() not in want or not folders:
                continue
            k = hr.manifest_key(g, folders)
            if k in seen:
                continue
            seen.add(k)
            raw = read_manifest(k)
            if raw is None:
                continue
            for c in parse_file_data(raw)[1]:
                t = read_afx_tag(c)
                if t:
                    out[g.lower()].add(t)
    return out


@dataclass
class WrittenClip:
    """A clip in our folder for the manifests: folder (as the SAPT names it), .af file name, tag, duration (s),
    events [(frame, name)]."""
    folder: str
    filename: str
    tag: str
    duration: float
    events: List[Tuple[int, str]] = field(default_factory=list)


def creature_manifests(race: esm.Record, clips: Sequence[WrittenClip], graph_tags: Dict[str, set],
                       fps: float = 30.0) -> Tuple[Dict[str, bytes], dict]:
    """({Data-relative path: bytes}, report) for every (graph, folders) set of our race: animationfiledata (clips in
    those folders whose tag the graph plays), dynamicidledata ('Version 1'), animationoffsets (tag / record for every
    listed clip with a gameplay event, times = frame / fps, as the Mini Bot's) and the empty generatedsubgraphdata
    table. A graph with no measured tag set is refused."""
    out, rep = {}, {"keys": {}}
    base = "Meshes\\AnimTextData\\"
    for g, folders in hr.race_subgraph_sets(race):
        if not folders:
            continue
        tags = graph_tags.get(g.lower())
        if tags is None:
            raise CreatureError(f"no measured tag set for graph {g}")
        k = hr.manifest_key(g, folders)
        fl = {f.lower() for f in folders}
        chosen = sorted((c for c in clips if c.folder.lower() in fl and c.tag in tags), key=lambda c: c.filename)
        paths = [hr.clip_path(c.folder, c.filename) for c in chosen]
        recs, tag_rows = [], []
        for c in chosen:
            ev = sorted({(f / fps, n) for f, n in c.events if n in GAMEPLAY_EVENTS})
            if ev:
                p = hr.clip_path(c.folder, c.filename.rsplit(".", 1)[0])
                tag_rows.append((c.tag, p))
                recs.append(hr.OffsetClip(p, c.duration, ev))
        prev = rep["keys"].get(str(k))
        if prev is not None:
            continue
        out[base + f"AnimationFileData\\{k}.txt"] = hr.animation_file_data(k, paths)
        out[base + f"DynamicIdleData\\{k}.txt"] = hr.dynamic_idle_data()
        out[base + f"AnimationOffsets\\{k}.txt"] = hr.animation_offsets(g, tag_rows, recs)
        rep["keys"][str(k)] = {"graph": g, "folders": list(folders), "clips": len(paths), "offset_records": len(recs),
                               "tags_not_played": sorted({c.tag for c in clips if c.folder.lower() in fl} - set(tags))}
    out[base + f"GeneratedSubgraphData\\{race.edid.lower()}.txt"] = hr.generated_subgraph_data(())
    return out, rep
