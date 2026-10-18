"""A door whose Open slides its parts is routed to its own rig by that motion, not only by a name NOT_HINGED_RE knows
(Red Rocket's RedRPedDoor.nif slides in FO4; the hinged template swung it about the leaf's centre, owner 2026-10-18)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fo4sf import door_rig  # noqa: E402
from test_door_two_panels import door_nif, sliding_panels, two_leaves  # noqa: E402
import test_sliding_doors  # noqa: E402

PED = "meshes/Interiors/RedRocket/Doors/SyntheticPedDoor.nif"          # no vault / gate / slid in the name


class SlidesTests(unittest.TestCase):
    def test_a_sliding_panel_slides_and_a_hinged_leaf_does_not(self):
        self.assertTrue(door_rig.slides(door_nif(sliding_panels()[:1])))
        self.assertTrue(door_rig.slides(door_nif(sliding_panels())))
        self.assertFalse(door_rig.slides(door_nif(two_leaves()[:1])))
        self.assertFalse(door_rig.slides(door_nif(two_leaves())))

    def test_unreadable_motion_is_not_called_sliding(self):
        bad = door_nif(sliding_panels()[:1])
        bad.block_types.append("NiPathInterpolator")
        for i in range(len(bad.blocks)):
            if bad.type_of(i) == "NiTransformInterpolator":
                bad.block_type_index[i] = len(bad.block_types) - 1
        self.assertFalse(door_rig.slides(bad))


class SlidingRoutingTests(unittest.TestCase):
    convert = test_sliding_doors.NonHingedRoutingTests.convert

    def test_a_sliding_door_with_a_plain_name_gets_its_own_rig(self):
        with tempfile.TemporaryDirectory() as staging:
            result, single, multi, static = self.convert(staging, PED, sliding_panels()[:1], "calumi.dll")
        self.assertTrue(result["ok"], result)
        single.assert_not_called()
        static.assert_not_called()
        self.assertTrue(multi.call_args.kwargs["rest_pose_check"])
        self.assertEqual(result["door"]["rig"], "native")

    def test_without_the_library_it_stays_passable_instead_of_swinging(self):
        with tempfile.TemporaryDirectory() as staging:
            result, single, multi, _ = self.convert(staging, PED, sliding_panels()[:1], None)
        single.assert_not_called()
        multi.assert_not_called()
        self.assertEqual(result["door_not_opening"], "open animation not ported: passable")

    def test_a_hinged_door_with_the_same_name_keeps_the_template(self):
        with tempfile.TemporaryDirectory() as staging:
            _, single, multi, _ = self.convert(staging, PED, two_leaves()[:1], "calumi.dll")
        single.assert_called_once()
        multi.assert_not_called()


if __name__ == "__main__":
    unittest.main()
