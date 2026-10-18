"""Source/native pose agreement under the supported bind-offset convention.

Synthetic NIFs and independent matrix composition; no DLL or engine execution.
"""
import math
import unittest

import numpy as np
import test_door_two_panels as fixtures
from fo4sf import door_rig, native_door, nif

UNIT = 1 / 70


def quaternion(degrees, axis):
    half = math.radians(degrees) / 2
    value = [math.cos(half), 0.0, 0.0, 0.0]
    value[axis + 1] = math.sin(half)
    return value


def rotation(q):
    w, x, y, z = q
    return np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w)],
        [2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w)],
        [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y)]])


def source_plan(degrees, axis=2):
    position = (14, 35, 70)
    part = ("Leaf", position, tuple(rotation(quaternion(degrees, axis)).flat),
            [(0, quaternion(degrees, axis)), (1, quaternion(degrees + 90, axis))],
            [(0, position), (1, (84, 0, 105))])
    source = fixtures.door_nif([part], static_shape=False)
    return door_rig.plan(source, placed=True)


def world_poses(bones, poses):
    worlds = []
    for i, bone in enumerate(bones):
        orientation, translation = poses[i]
        local = np.eye(4)
        local[:3, :3] = orientation
        local[:3, 3] = translation
        parent = bone["parent"]
        worlds.append(local if parent == -1 else worlds[parent] @ local)
    return worlds


def source_world(plan, clip, frame):
    samples = {track["node"]: track["samples"][frame] for track in clip["tracks"]}
    poses = []
    for bone in plan["bones"]:
        pose = samples.get(bone["node"], bone["bind"])
        poses.append((rotation(pose["quaternion_wxyz"]),
                      np.array(pose["translation_source_units"]) * UNIT))
    return world_poses(plan["bones"], poses)


def native_world(prepared, clip, frame, offset_first):
    keys = {track["bone"]: track["keys"][frame] for track in clip["tracks"]}
    poses = []
    for i, bone in enumerate(prepared["bones"]):
        orientation = rotation(bone["bind"]["quaternion_wxyz"])
        translation = np.array(bone["bind"]["translation_source_units"]) * UNIT
        if i in keys:
            delta = rotation(keys[i]["quaternion_wxyz"])
            orientation = delta @ orientation if offset_first else orientation @ delta
            translation += keys[i]["translation"]
        poses.append((orientation, translation))
    return world_poses(prepared["bones"], poses)


class SmallDoorBindTests(unittest.TestCase):
    def test_small_authored_rotations_are_not_identity(self):
        for axis in range(3):
            for angle in (-0.15, -0.1, 0.1, 0.15):
                for sign in (-1, 1):
                    with self.subTest(axis=axis, angle=angle, sign=sign):
                        q = [sign * value for value in quaternion(angle, axis)]
                        self.assertFalse(door_rig.is_identity_rotation(q))

    def test_unrebased_small_rotation_is_rejected_by_native_writer(self):
        with self.assertRaisesRegex(nif.NifError, "identity bind rotation"):
            native_door.prepare(source_plan(0.1), UNIT)

    def test_closed_pose_equals_bind_and_exports_zero_rotation_offset(self):
        rebased = door_rig.animated_identity_binds(source_plan(0.1))
        self.assertTrue(any(bone.get("bind_for") == "Leaf" for bone in rebased["bones"]))
        prepared = native_door.prepare(rebased, UNIT)
        for clip in prepared["clips"]:
            frame = 0 if clip["name"] == "Open" else -1
            q = clip["tracks"][0]["keys"][frame]["quaternion_wxyz"]
            self.assertLess(math.hypot(*q[1:]), 1e-8)
            self.assertAlmostEqual(abs(q[0]), 1)

    def test_world_poses_match_source_for_both_composition_orders(self):
        for axis in range(3):
            for angle in (-0.15, 0.1, 90):
                original = source_plan(angle, axis)
                rebased = door_rig.animated_identity_binds(original)
                prepared = native_door.prepare(rebased, UNIT)
                source_leaf = next(i for i, bone in enumerate(original["bones"]) if bone["name"] == "Leaf")
                native_leaf = next(i for i, bone in enumerate(prepared["bones"]) if bone["name"] == "Leaf")
                for source_clip, native_clip in zip(original["clips"], prepared["clips"]):
                    for frame in range(31):
                        expected = source_world(original, source_clip, frame)[source_leaf]
                        for offset_first in (False, True):
                            with self.subTest(axis=axis, angle=angle, clip=source_clip["name"],
                                              frame=frame, offset_first=offset_first):
                                actual = native_world(prepared, native_clip, frame, offset_first)[native_leaf]
                                np.testing.assert_allclose(actual, expected, atol=2e-8, rtol=0)

    def test_sign_equivalent_identity_and_tiny_noise_are_preserved(self):
        for sign in (-1, 1):
            self.assertTrue(door_rig.is_identity_rotation([sign, 0, 0, 0]))
        self.assertTrue(door_rig.is_identity_rotation(quaternion(0.0000001, 2)))
        rebased = door_rig.animated_identity_binds(source_plan(0.0000001))
        self.assertFalse(any(bone.get("bind_for") for bone in rebased["bones"]))


if __name__ == "__main__":
    unittest.main()
