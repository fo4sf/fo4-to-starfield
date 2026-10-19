"""Fallout 4 human bone names -> Starfield human rig bone names (spike E, docs/spikes/E-own-ecosystem.md).

    from fo4sf import human_bones
    actor_rebind.rebind(template_nif, fo4_nif, human_bones.bone_for, ...)   # an FO4 human body on Starfield's rig

Sources (verified, PC jobs AT and AU, 2026-10-19): the 129 NiNode names of Fallout 4's
meshes\\actors\\character\\characterassets\\skeleton.nif, and the 97 bone names in the name table of Starfield's
meshes\\actors\\human\\characterassets\\skeleton.rig (first name at the u32 offset stored at 0x80). Only the names come
from those files; which FO4 bone matches which Starfield bone is our reading of the names (supported hypothesis) until a
converted body is posed in game. FO4's _skin and fat helpers fold onto the deform bone they sit on. A name with no
mapping raises KeyError instead of being bound to a guessed bone (ACTOR-MILESTONE step 2).
"""
from typing import Optional

# The Starfield human rig's 97 bone names, in name-table order.
STARFIELD_HUMAN = (
    'Root', 'AnimObjectA', 'AnimObjectB', 'AnimObjectC', 'AnimObjectD', 'COM', 'C_Hips', 'R_Thigh', 'R_Calf',
    'L_Thigh', 'L_Calf', 'C_Spine', 'C_Spine1', 'C_Spine2', 'C_Chest', 'C_Neck', 'L_Clavicle', 'L_Biceps',
    'L_Forearm', 'L_Wrist', 'L_AnimObject1', 'L_AnimObject2', 'L_AnimObject3', 'R_Clavicle', 'R_Biceps', 'R_Forearm',
    'R_Wrist', 'R_AnimObject1', 'R_AnimObject2', 'R_AnimObject3', 'Weapon', 'WeaponLeft', 'C_Neck1', 'C_Head',
    'Eye_Target', 'R_HandIk', 'L_HandIk', 'DirectAt', 'R_Foot', 'L_Foot', 'R_Toe', 'L_Toe', 'L_Thumb', 'L_Thumb1',
    'L_Thumb2', 'L_Cup', 'L_Pinky', 'L_Pinky1', 'L_Pinky2', 'L_Ring', 'L_Ring1', 'L_Ring2', 'L_Middle', 'L_Middle1',
    'L_Middle2', 'L_Index', 'L_Index1', 'L_Index2', 'R_Thumb', 'R_Thumb1', 'R_Cup', 'R_Pinky', 'R_Pinky1', 'R_Ring',
    'R_Ring1', 'R_Ring2', 'R_Middle', 'R_Middle1', 'R_Index', 'R_Index1', 'R_Index2', 'Camera Control',
    'CamTargetParent', 'CameraTarget', 'Camera', 'L_Arm', 'R_Thumb2', 'R_Pinky2', 'R_Middle2', 'R_Arm', 'C_Waist',
    'Camera Control FP', 'R_Thigh_Twist', 'R_Thigh_Twist1', 'L_Thigh_Twist', 'L_Thigh_Twist1', 'C_Neck_Twist',
    'L_Wrist_Twist', 'L_Wrist_Twist1', 'L_Wrist_Twist2', 'L_Biceps_Twist', 'L_Biceps_Twist1', 'R_Wrist_Twist',
    'R_Wrist_Twist1', 'R_Wrist_Twist2', 'R_Biceps_Twist', 'R_Biceps_Twist1',
)

_FINGERS = {"1": "Thumb", "2": "Index", "3": "Middle", "4": "Ring", "5": "Pinky"}
_SEGMENT = {"1": "", "2": "1", "3": "2"}


def _direct() -> dict:
    m = {"Root": "Root", "COM": "COM", "Pelvis": "C_Hips", "SPINE1": "C_Spine", "SPINE2": "C_Spine2",
         "Chest": "C_Chest", "Neck": "C_Neck", "HEAD": "C_Head", "WEAPON": "Weapon", "WeaponLeft": "WeaponLeft",
         "AnimObjectA": "AnimObjectA", "AnimObjectB": "AnimObjectB", "Camera": "Camera",
         "Camera Control": "Camera Control", "CamTargetParent": "CamTargetParent", "CamTarget": "CameraTarget"}
    for fo4, sf in (("L", "L"), ("R", "R")):
        m.update({f"{fo4}Leg_Thigh": f"{sf}_Thigh", f"{fo4}Leg_Calf": f"{sf}_Calf", f"{fo4}Leg_Foot": f"{sf}_Foot",
                  f"{fo4}Leg_Toe1": f"{sf}_Toe", f"{fo4}Arm_Collarbone": f"{sf}_Clavicle",
                  f"{fo4}Arm_UpperArm": f"{sf}_Biceps", f"{fo4}Arm_UpperTwist1": f"{sf}_Biceps_Twist",
                  f"{fo4}Arm_UpperTwist2": f"{sf}_Biceps_Twist1", f"{fo4}Arm_ForeArm1": f"{sf}_Forearm",
                  f"{fo4}Arm_ForeArm2": f"{sf}_Wrist_Twist", f"{fo4}Arm_ForeArm3": f"{sf}_Wrist_Twist1",
                  f"{fo4}Arm_Hand": f"{sf}_Wrist"})
        for i in "123":
            m[f"AnimObject{fo4}{i}"] = f"{sf}_AnimObject{i}"
        for f, finger in _FINGERS.items():
            for s, seg in _SEGMENT.items():
                m[f"{fo4}Arm_Finger{f}{s}"] = f"{sf}_{finger}{seg}"
    return m


# FO4 helper and skin nodes -> the FO4 deform bone whose mapping they take.
_HELPERS = {
    "Pelvis_skin": "Pelvis", "RButtFat_skin": "Pelvis", "LButtFat_skin": "Pelvis", "Pelvis_Rear_skin": "Pelvis",
    "Spine1_skin": "SPINE1", "Belly_skin": "SPINE1", "Spine1_Rear_skin": "SPINE1",
    "Spine2_skin": "SPINE2", "UpperBelly_skin": "SPINE2", "Spine2_Rear_skin": "SPINE2",
    "Chest_skin": "Chest", "LBreast_skin": "Chest", "RBreast_skin": "Chest", "Chest_Rear_Skin": "Chest",
    "Chest_Upper_skin": "Chest", "L_RibHelper": "Chest", "R_RibHelper": "Chest",
    "Neck_skin": "Neck", "Neck1_skin": "Neck", "Neck_Low_skin": "Neck", "Head_skin": "HEAD", "Face_skin": "HEAD",
}
for _s in "LR":
    _HELPERS.update({
        f"{_s}Leg_Calf_skin": f"{_s}Leg_Calf", f"{_s}Leg_Calf_Low_skin": f"{_s}Leg_Calf",
        f"{_s}Leg_Thigh_skin": f"{_s}Leg_Thigh", f"{_s}Leg_Thigh_Low_skin": f"{_s}Leg_Thigh",
        f"{_s}Leg_Thigh_Fat_skin": f"{_s}Leg_Thigh",
        f"{_s}Arm_ForeArm1_skin": f"{_s}Arm_ForeArm1", f"{_s}Arm_ForeArm2_skin": f"{_s}Arm_ForeArm2",
        f"{_s}Arm_ForeArm3_skin": f"{_s}Arm_ForeArm3", f"{_s}Arm_UpperTwist1_skin": f"{_s}Arm_UpperTwist1",
        f"{_s}Arm_UpperTwist2_skin": f"{_s}Arm_UpperTwist2", f"{_s}Arm_UpperFat_skin": f"{_s}Arm_UpperArm",
        f"{_s}Arm_UpperArm_skin": f"{_s}Arm_UpperArm", f"{_s}Arm_Collarbone_skin": f"{_s}Arm_Collarbone",
        f"{_s}Arm_ShoulderFat_skin": f"{_s}Arm_Collarbone",
    })

BONES = _direct()
BONES.update({helper: BONES[deform] for helper, deform in _HELPERS.items()})


def bone_for(fo4_bone: Optional[str]) -> str:
    """actor_rebind's bone_for: the Starfield human bone for an FO4 bone; unweighted vertices (None) go to the hips."""
    if fo4_bone is None:
        return "C_Hips"
    return BONES[fo4_bone]
