"""Synthetic source topology regressions for #216; no native game claims."""
import math
import struct
import unittest

from fo4sf import convert_static, door_motion
from test_door_motion import fixture


def rotation_track(source, degrees=0, *, keys=True):
    radians = math.radians(degrees) / 2
    data = -1
    if keys:
        data = source.add_block("NiTransformData", struct.pack(
            "<II10fII", 2, 1, 0, 1, 0, 0, 0,
            1, math.cos(radians), 0, 0, math.sin(radians), 0, 0))
    return source.add_block("NiTransformInterpolator", struct.pack(
        "<8fi", 0, 0, 0, 1, 0, 0, 0, 1, data))


def sequence(source, name, targets):
    controlled = b"".join(struct.pack(
        "<iiBiiiii", track, -1, 0,
        struct.unpack_from("<i", source.blocks[node])[0], -1, -1, -1, -1)
        for node, track in targets)
    timing = struct.pack("<fiIfffiiH", 1, -1, 2, 1, 0, 1, -1, 0, 0)
    return struct.pack("<iII", source.string_index(name), len(targets), 0) + controlled + timing


class NestedDoorMotionTests(unittest.TestCase):
    def nested(self, degrees=(-90, 90)):
        source = fixture()
        parent = rotation_track(source)
        children = [rotation_track(source, value) for value in degrees]
        source.blocks[5] = sequence(source, b"Open", [(0, parent), *enumerate(children, 1)])
        return source

    def test_opposite_nested_leaves_require_own_rig(self):
        source = self.nested()
        report = door_motion.inspect(source)
        self.assertTrue(report["requires_additional_motion_support"])
        self.assertEqual(report["animated_shapes_outside_single_hinge"], [3, 4])
        self.assertEqual(report["nested_controlled_shape_blocks"], [3, 4])
        self.assertTrue(convert_static.frozen_door_parts(source))

    def test_identical_child_curves_are_still_independent_local_tracks(self):
        self.assertTrue(door_motion.inspect(self.nested((90, 90)))["requires_additional_motion_support"])

    def test_single_hinge_with_uncontrolled_geometry_stays_single(self):
        source = self.nested()
        source.blocks[5] = sequence(source, b"Open", [(0, rotation_track(source, 90))])
        self.assertFalse(door_motion.inspect(source)["requires_additional_motion_support"])
        self.assertEqual(convert_static.frozen_door_parts(source), [])

    def test_null_child_interpolator_does_not_add_local_motion(self):
        source = self.nested()
        source.blocks[5] = sequence(source, b"Open", [(0, rotation_track(source, 90)), (1, -1)])
        self.assertFalse(door_motion.inspect(source)["requires_additional_motion_support"])

    def test_close_only_child_track_is_not_hidden_by_open_parent(self):
        source = self.nested()
        source.blocks[5] = sequence(source, b"Open", [(0, rotation_track(source, 90))])
        source.add_block("NiControllerSequence", sequence(source, b"Close", [(1, rotation_track(source, -90))]))
        self.assertEqual(door_motion.inspect(source)["animated_shapes_outside_single_hinge"], [3])
        self.assertTrue(convert_static.frozen_door_parts(source))

    def test_constant_or_unsupported_child_track_is_not_assumed_bind_equivalent(self):
        for kind in ("constant", "unsupported"):
            with self.subTest(kind=kind):
                source = self.nested()
                track = (rotation_track(source, keys=False) if kind == "constant" else
                         source.add_block("NiFloatInterpolator", b""))
                source.blocks[5] = sequence(source, b"Open", [(0, -1), (1, track)])
                self.assertEqual(door_motion.inspect(source)["animated_shapes_outside_single_hinge"], [3])
                self.assertTrue(convert_static.frozen_door_parts(source))

    def test_track_without_geometry_does_not_change_hinge_routing(self):
        source = self.nested()
        source.blocks[1] = source.blocks[1][:-8] + struct.pack("<I", 0)
        source.blocks[5] = sequence(source, b"Open", [(0, -1), (1, rotation_track(source, 90))])
        self.assertFalse(door_motion.inspect(source)["requires_additional_motion_support"])


if __name__ == "__main__":
    unittest.main()
