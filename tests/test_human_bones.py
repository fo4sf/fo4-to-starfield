from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fo4sf import human_bones  # noqa: E402

# Fallout 4's skeleton.nif NiNode names (PC job AT, 2026-10-19), less the scene root, camera and bumper nodes.
FO4_NODES = (
    "Root COM Pelvis LLeg_Thigh LLeg_Calf LLeg_Foot LLeg_Toe1 LLeg_Calf_skin LLeg_Calf_Low_skin LLeg_Thigh_skin "
    "LLeg_Thigh_Low_skin LLeg_Thigh_Fat_skin RLeg_Thigh RLeg_Calf RLeg_Foot RLeg_Toe1 RLeg_Calf_skin RLeg_Calf_Low_skin "
    "RLeg_Thigh_skin RLeg_Thigh_Low_skin RLeg_Thigh_Fat_skin Pelvis_skin RButtFat_skin LButtFat_skin Pelvis_Rear_skin "
    "SPINE1 SPINE2 Chest LArm_Collarbone LArm_UpperArm LArm_ForeArm1 LArm_ForeArm2 LArm_ForeArm3 LArm_Hand "
    "LArm_Finger11 LArm_Finger12 LArm_Finger13 LArm_Finger21 LArm_Finger22 LArm_Finger23 LArm_Finger31 LArm_Finger32 "
    "LArm_Finger33 LArm_Finger41 LArm_Finger42 LArm_Finger43 LArm_Finger51 LArm_Finger52 LArm_Finger53 WeaponLeft "
    "AnimObjectL1 AnimObjectL3 AnimObjectL2 LArm_ForeArm3_skin LArm_ForeArm2_skin LArm_ForeArm1_skin "
    "LArm_UpperTwist1 LArm_UpperTwist2 LArm_UpperTwist2_skin LArm_UpperFat_skin LArm_UpperTwist1_skin "
    "LArm_UpperArm_skin LArm_Collarbone_skin LArm_ShoulderFat_skin Neck HEAD Head_skin Face_skin Neck_skin Neck1_skin "
    "RArm_Collarbone RArm_UpperArm RArm_ForeArm1 RArm_ForeArm2 RArm_ForeArm3 RArm_Hand RArm_Finger11 RArm_Finger12 "
    "RArm_Finger13 RArm_Finger21 RArm_Finger22 RArm_Finger23 RArm_Finger31 RArm_Finger32 RArm_Finger33 RArm_Finger41 "
    "RArm_Finger42 RArm_Finger43 RArm_Finger51 RArm_Finger52 RArm_Finger53 WEAPON AnimObjectR1 AnimObjectR2 "
    "AnimObjectR3 RArm_ForeArm3_skin RArm_ForeArm2_skin RArm_ForeArm1_skin RArm_UpperTwist1 RArm_UpperTwist2 "
    "RArm_UpperTwist2_skin RArm_UpperFat_skin RArm_UpperTwist1_skin RArm_UpperArm_skin RArm_Collarbone_skin "
    "RArm_ShoulderFat_skin L_RibHelper R_RibHelper Chest_skin LBreast_skin RBreast_skin Chest_Rear_Skin "
    "Chest_Upper_skin Neck_Low_skin Spine2_skin UpperBelly_skin Spine2_Rear_skin Spine1_skin Belly_skin "
    "Spine1_Rear_skin AnimObjectA AnimObjectB"
).split()


class HumanBonesTest(unittest.TestCase):
    def test_every_fo4_body_bone_lands_on_a_starfield_bone(self):
        rig = set(human_bones.STARFIELD_HUMAN)
        for name in FO4_NODES:
            self.assertIn(human_bones.bone_for(name), rig, name)

    def test_rig_list_matches_the_name_table(self):
        self.assertEqual(len(human_bones.STARFIELD_HUMAN), 97)
        self.assertEqual(len(set(human_bones.STARFIELD_HUMAN)), 97)
        self.assertIn("Camera Control FP", human_bones.STARFIELD_HUMAN)

    def test_known_pairs(self):
        b = human_bones.bone_for
        self.assertEqual(b("Pelvis"), "C_Hips")
        self.assertEqual(b("LArm_UpperArm"), "L_Biceps")
        self.assertEqual(b("RArm_Hand"), "R_Wrist")
        self.assertEqual(b("LArm_Finger11"), "L_Thumb")
        self.assertEqual(b("RArm_Finger53"), "R_Pinky2")
        self.assertEqual(b("LLeg_Thigh_Fat_skin"), "L_Thigh")
        self.assertEqual(b("Face_skin"), "C_Head")

    def test_unweighted_goes_to_hips_and_unknown_is_refused(self):
        self.assertEqual(human_bones.bone_for(None), "C_Hips")
        with self.assertRaises(KeyError):
            human_bones.bone_for("PipboyBone")


if __name__ == "__main__":
    unittest.main()
