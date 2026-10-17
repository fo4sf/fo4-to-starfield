"""Sliding, lifting and trapdoor FO4 doors (vault doors, elevator doors, hatches): own rig and FO4's keys instead of a
passable static (docs/spikes/sliding-doors.md). Synthetic fixtures only; no game data, no CALUMI library."""
import os
import struct
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fo4sf import convert_static, door_motion, door_rig, nif, pipeline, sfcollision  # noqa: E402
from test_collision import fake_template  # noqa: E402
from test_door_two_panels import (IDENTITY, ROT_Z90, collision_targets, door_nif, donor, fake_clip_files,  # noqa: E402
                                  node_names, quat_z, sequences, sliding_panels, two_leaves)

ROT_X90 = (1, 0, 0, 0, 0, -1, 0, 1, 0)            # row-major, +90 degrees about x


def vault_door():
    """FO4 vault-door shape (V111Door01 / VltDoorRes01*): an upper panel that rises 148 units (2.114 m) and a lower
    panel that drops 68 units (0.971 m); the upper node's name has a space, as FO4's "Door Upper"."""
    return [("Door Upper", (0, 0, -148), IDENTITY, None, [(0, (0, 0, -148)), (1, (0, 0, 0))]),
            ("Lower", (0, 0, 53), IDENTITY, None, [(0, (0, 0, 53)), (1, (0, 0, -15))])]


def trapdoor():
    """A single hatch leaf that flips 90 degrees about the horizontal y axis (UtilMetalElevatorHatch01's kind)."""
    h = 0.7071067811865476
    return [("MetalTrapdoor01", (0, 0, 200), IDENTITY, [(0, (1, 0, 0, 0)), (1, (h, 0, -h, 0))], None)]


def add_track(f, sequence, target, controller_type=None, interpolator_type="NiFloatInterpolator"):
    """Append one controlled block to a sequence: interpolator of the given type, controller-type string (None = absent)."""
    interp = f.add_block(interpolator_type, struct.pack("<f", 0.0))
    block = bytearray(f.blocks[sequence])
    count = struct.unpack_from("<I", block, 4)[0]
    ctype = f.string_index(controller_type.encode()) if controller_type else -1
    entry = struct.pack("<iiBiiiii", interp, -1, 0, f.string_index(target.encode()), -1, ctype, -1, -1)
    at = 12 + 29 * count
    block[at:at] = entry
    struct.pack_into("<I", block, 4, count + 1)
    f.blocks[sequence] = bytes(block)


def retype_track(f, sequence, k, interpolator_type, controller_type):
    """Point controlled block k of a sequence at a new interpolator block of the given type (the old block's payload) and
    name a controller type: a transform track this code cannot sample (B-spline, an unknown interpolator)."""
    block = bytearray(f.blocks[sequence])
    at = 12 + 29 * k
    old = struct.unpack_from("<i", block, at)[0]
    struct.pack_into("<i", block, at, f.add_block(interpolator_type, f.blocks[old]))
    struct.pack_into("<i", block, at + 17, f.string_index(controller_type.encode()))
    f.blocks[sequence] = bytes(block)


def with_shader_tracks(parts):
    """A door whose Open / Close also drive a shader float on a shape (VltDoorRes01A's override-box lights)."""
    f = door_nif(parts)
    for name in (b"Open", b"Close"):
        add_track(f, sequences(f)[name], "OverrideBox:0", "BSLightingShaderPropertyFloatController")
    return f


class IgnoredTrackTests(unittest.TestCase):
    def test_shader_tracks_are_listed_not_binding_issues(self):
        report = door_motion.inspect(with_shader_tracks(sliding_panels()))
        self.assertEqual(report["issues"], [])
        self.assertEqual([(t["target"], t["reason"]) for t in report["ignored_targets"]],
                         [("OverrideBox:0", "controller BSLightingShaderPropertyFloatController")] * 2)
        self.assertEqual([[t["name"] for t in s["targets"]] for s in report["sequences"]], [["PanelA", "PanelB"]] * 2)

    def test_a_visibility_interpolator_without_a_controller_type_is_not_motion(self):
        f = door_nif(sliding_panels())
        add_track(f, sequences(f)[b"Open"], "PanelA", None, "NiBoolInterpolator")      # binds a real node: still not motion
        report = door_motion.inspect(f)
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["ignored_targets"][0]["reason"], "interpolator NiBoolInterpolator")
        self.assertEqual(len(report["sequences"][0]["targets"]), 2)

    def test_a_transform_track_on_a_missing_node_is_still_an_issue(self):
        f = door_nif(sliding_panels())
        add_track(f, sequences(f)[b"Open"], "Missing", "NiTransformController", "NiTransformInterpolator")
        self.assertEqual([i["target"] for i in door_motion.inspect(f)["issues"]], ["Missing"])
        with self.assertRaisesRegex(nif.NifError, "bindings"):
            door_rig.plan(f, placed=True)

    def test_a_transform_track_this_code_cannot_sample_is_refused_not_dropped(self):
        # Codex review of #242, P2: an unknown interpolator on a NiTransformController block is not evidence of
        # non-motion; dropping it would rig the door with PanelA frozen. It stays a track, and the rig plan refuses it.
        for kind in ("NiBSplineCompTransformInterpolator", "UnknownTransformInterpolator"):
            f = door_nif(sliding_panels())
            retype_track(f, sequences(f)[b"Open"], 0, kind, "NiTransformController")
            report = door_motion.inspect(f)
            self.assertEqual(report["ignored_targets"], [], kind)
            self.assertEqual([t["name"] for t in report["sequences"][0]["targets"]], ["PanelA", "PanelB"], kind)
            self.assertEqual(report["sequences"][0]["targets"][0]["transform_track"]["status"], "unsupported_interpolator")
            with self.assertRaisesRegex(nif.NifError, "unsupported sampled door interpolator"):
                door_rig.plan(f, placed=True)

    def test_only_known_non_motion_controllers_are_ignored(self):
        f = door_nif(sliding_panels())                   # a float track under a controller type nobody has checked
        add_track(f, sequences(f)[b"Open"], "OverrideBox:0", "SomeFutureController")
        report = door_motion.inspect(f)
        self.assertEqual(report["ignored_targets"], [])
        self.assertEqual([i["target"] for i in report["issues"]], ["OverrideBox:0"])

    def test_rig_plan_and_native_door_keep_the_moving_parts_and_say_what_was_left_out(self):
        f = with_shader_tracks(sliding_panels())
        plan = door_rig.plan(f, placed=True)
        self.assertEqual([[t["name"] for t in c["tracks"]] for c in plan["clips"]], [["PanelA", "PanelB"]] * 2)
        self.assertEqual(len(plan["ignored_tracks"]), 2)
        count = len([s for s in nif.fo4_trishapes(f) if s.positions and s.triangles])
        _, door = convert_static.convert_multipart_door(nif.serialize(f), "fo4port/vault/d", ["x.mat"] * count, fake_clip_files,
                                                        collision_template=fake_template(), leaf_physics_donor=donor())
        self.assertEqual(door["ignored_tracks"], ["OverrideBox:0 (controller BSLightingShaderPropertyFloatController)"])
        self.assertEqual(door["animated_bones"], ["PanelA", "PanelB"])

    def test_doors_without_ignored_tracks_get_no_ignored_entry(self):
        count = len([s for s in nif.fo4_trishapes(door_nif(two_leaves())) if s.positions and s.triangles])
        _, door = convert_static.convert_multipart_door(nif.serialize(door_nif(two_leaves())), "fo4port/d", ["x.mat"] * count,
                                                        fake_clip_files, collision_template=fake_template(),
                                                        leaf_physics_donor=donor())
        self.assertNotIn("ignored_tracks", door)


class OpenMotionTests(unittest.TestCase):
    def motion(self, parts, unit_scale=1 / 70):
        plan = door_rig.animated_identity_binds(door_rig.plan(door_nif(parts), placed=True))
        return {row["bone"]: row for row in door_rig.open_motion(plan, unit_scale)}

    def test_sliding_panels_travel_apart_in_metres(self):
        rows = self.motion(sliding_panels())
        self.assertEqual(rows["PanelA"]["travel_m"], [0.0, -1.0, 0.0])
        self.assertEqual(rows["PanelB"]["travel_m"], [0.0, 1.0, 0.0])
        self.assertEqual((rows["PanelA"]["rotation_deg"], rows["PanelA"]["axis"]), (0.0, None))

    def test_vault_door_upper_rises_and_lower_drops(self):
        rows = self.motion(vault_door())
        self.assertEqual(rows["Door Upper"]["travel_m"], [0.0, 0.0, round(148 / 70, 4)])
        self.assertEqual(rows["Lower"]["travel_m"], [0.0, 0.0, round(-68 / 70, 4)])

    def test_hinge_and_trapdoor_rotations_and_axes(self):
        leaf = self.motion(two_leaves())["LeafA"]
        self.assertEqual((leaf["rotation_deg"], leaf["axis"], leaf["travel_m"]), (90.0, [0.0, 0.0, -1.0], [0.0, 0.0, 0.0]))
        hatch = self.motion(trapdoor())["MetalTrapdoor01"]
        self.assertEqual((hatch["rotation_deg"], hatch["axis"]), (90.0, [0.0, -1.0, 0.0]))

    def test_travel_of_a_rotated_bind_is_reported_in_the_parent_frame(self):
        # FO4 keys a node's translation in its parent's frame; the identity-bind rewrite moves it into "<name>_Bind"'s
        # rotated frame, so the summary has to rotate it back: the panel still slides +1 m along the door's y axis.
        parts = [("Panel", (0, 35, 0), ROT_Z90, [(0, quat_z(90)), (1, quat_z(90))], [(0, (0, 35, 0)), (1, (0, 105, 0))])]
        row = self.motion(parts)["Panel"]
        self.assertEqual(row["travel_m"], [0.0, 1.0, 0.0])
        self.assertEqual(row["rotation_deg"], 0.0)

    def test_travel_carries_the_parents_bind_scale(self):
        # Codex review of #242, P2: a node's keys are in its parent's frame, scale included, so a parent bound at scale 3
        # makes 70 units of local travel 3 m in model space.
        def bone(node, name, parent, scale, q=(1.0, 0.0, 0.0, 0.0)):
            return {"node": node, "name": name, "parent": parent,
                    "bind": {"translation_source_units": [0.0, 0.0, 0.0], "quaternion_wxyz": list(q), "scale": scale}}

        def sample(x):
            return {"translation_source_units": [x, 0.0, 0.0], "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0], "scale": 1.0}
        plan = {"bones": [bone(0, "Root", -1, 3.0), bone(1, "Panel", 0, 1.0)],
                "clips": [{"name": "Open", "tracks": [{"node": 1, "samples": [sample(0.0), sample(70.0)]}]}]}
        self.assertEqual(door_rig.open_motion(plan, 1 / 70)[0]["travel_m"], [3.0, 0.0, 0.0])
        # nested and turned: 2 x 1.5 under a +90 degree z bind, so the panel's +x is the model's +y
        plan["bones"] = [bone(0, "Root", -1, 2.0), bone(2, "Frame", 0, 1.5, quat_z(90)), bone(1, "Panel", 1, 1.0)]
        self.assertEqual(door_rig.open_motion(plan, 1 / 70)[0]["travel_m"], [0.0, 3.0, 0.0])

    def test_other_clips_are_not_summarised(self):
        plan = door_rig.plan(door_nif(sliding_panels()), placed=True)
        self.assertEqual(len(door_rig.open_motion(plan, 1 / 70, "Close")), 2)
        self.assertEqual(door_rig.open_motion(plan, 1 / 70, "Idle"), [])


class VaultDoorConversionTests(unittest.TestCase):
    def test_both_vault_panels_get_a_bone_a_track_and_a_keyframed_body(self):
        f = door_nif(vault_door())
        count = len([s for s in nif.fo4_trishapes(f) if s.positions and s.triangles])
        files, door = convert_static.convert_multipart_door(nif.serialize(f), "fo4port/interiors/vault/doors/vd",
                                                            ["x.mat"] * count, fake_clip_files,
                                                            collision_template=fake_template(), leaf_physics_donor=donor())
        model = nif.parse(files["meshes/fo4port/interiors/vault/doors/vd.nif"])
        nodes, bodies = node_names(model), collision_targets(model)
        self.assertEqual(set(bodies), {nodes["Door Upper"], nodes["Lower"]})
        for blob in bodies.values():
            for offset, size in sfcollision.KEYFRAMED_FIELDS:
                self.assertEqual(blob[offset:offset + size], donor()[offset:offset + size])
        self.assertEqual(files["meshes/fo4port/interiors/vault/doors/vd/animations/Open.af"], b"Door Upper,Lower")
        self.assertEqual(door["rig"], "native")
        self.assertEqual(door["origin_offset"], [0.0, 0.0, 0.0])
        self.assertEqual([r["bone"] for r in door["open_motion"]], ["Door Upper", "Lower"])
        self.assertEqual(door["open_motion"][0]["travel_m"][2], round(148 / 70, 4))

    def test_opening_closing_sequences_alias_to_open_close(self):
        """FO4 Default2StateActivator ACTI (RedRGarageDoor) names clips Opening/Closing; the graph plays Open/Close
        (docs/terrain/garage-button.md)."""
        f = door_nif(sliding_panels(), open_name=b"Opening", close_name=b"Closing")
        names = [c["name"] for c in door_rig.plan(f, placed=True)["clips"]]
        self.assertEqual(sorted(names), ["Close", "Open"])
        count = len([s for s in nif.fo4_trishapes(f) if s.positions and s.triangles])
        files, door = convert_static.convert_multipart_door(nif.serialize(f), "fo4core/garage", ["x.mat"] * count,
                                                            fake_clip_files, collision_template=fake_template(),
                                                            leaf_physics_donor=donor())
        self.assertIn("meshes/fo4core/garage/animations/Open.af", files)
        self.assertIn("meshes/fo4core/garage/animations/Close.af", files)
        self.assertEqual(door["rig"], "native")

    def test_a_trapdoor_has_one_part_and_still_gets_its_own_rig(self):
        f = door_nif(trapdoor())
        self.assertEqual(convert_static.frozen_door_parts(f), [])            # nothing outside the first node ...
        count = len([s for s in nif.fo4_trishapes(f) if s.positions and s.triangles])
        _, door = convert_static.convert_multipart_door(nif.serialize(f), "fo4port/hatch", ["x.mat"] * count, fake_clip_files,
                                                        collision_template=fake_template(), leaf_physics_donor=donor())
        self.assertEqual((door["animated_bones"], door["moving_bodies"]), (["MetalTrapdoor01"], 1))   # ... yet it moves


class RestPoseTests(unittest.TestCase):
    """Review of #242, P3: the graph shows the bind pose while the door is shut, so on the own-rig route a door whose Open
    does not start, or whose Close does not end, at its bind pose (BHMarketGateDoor01: bind is Open's end pose;
    DExtMainGateDoor01: Close ends open) is refused and stays passable instead of sitting open or never closing."""

    def convert(self, parts, **kw):
        f = door_nif(parts)
        count = len([s for s in nif.fo4_trishapes(f) if s.positions and s.triangles])
        return convert_static.convert_multipart_door(nif.serialize(f), "fo4port/gate", ["x.mat"] * count, fake_clip_files,
                                                     collision_template=fake_template(), leaf_physics_donor=donor(), **kw)

    def test_open_that_starts_away_from_the_bind_pose_is_refused(self):
        slid = [("Gate", (0, 35, 0), IDENTITY, None, [(0, (0, 105, 0)), (1, (0, 35, 0))])]          # bind = Open's end
        turned = [("DoorL01", (0, 0, 0), IDENTITY, [(0, quat_z(170)), (1, quat_z(0))], None)]      # 170 degrees off
        for parts, bone in ((slid, "Gate"), (turned, "DoorL01")):
            with self.assertRaisesRegex(nif.NifError, f"Open of {bone} does not start at the bind pose"):
                self.convert(parts, rest_pose_check=True)
            self.assertEqual(self.convert(parts)[1]["rig"], "native")       # the #79 multi-part route is unchanged

    def test_close_that_ends_away_from_the_bind_pose_is_named(self):
        def track(name, x):
            return {"node": 1, "name": name, "samples": [{"translation_source_units": [x, 0.0, 0.0],
                                                          "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0], "scale": 1.0}]}
        plan = {"bones": [{"node": 1, "name": "Arm", "parent": -1,
                           "bind": {"translation_source_units": [0.0, 0.0, 0.0], "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0],
                                    "scale": 1.0}}],
                "clips": [{"name": "Open", "tracks": [track("Arm", 0.0)]}, {"name": "Close", "tracks": [track("Arm", 52.0)]}]}
        self.assertEqual(door_rig.rest_pose_issue(plan), "Close of Arm does not end at the bind pose")
        plan["clips"][1]["tracks"][0]["samples"][0]["translation_source_units"][0] = 0.1           # within tolerance
        self.assertIsNone(door_rig.rest_pose_issue(plan))

    def test_the_audited_kinds_pass(self):
        for parts in (vault_door(), sliding_panels(), trapdoor(), two_leaves()):
            self.assertEqual(self.convert(parts, rest_pose_check=True)[1]["rig"], "native")


class NonHingedRoutingTests(unittest.TestCase):
    """pipeline.Converter.convert_nif: which path a door-named model takes (stubbed converters)."""

    def convert(self, staging, name, parts, dll, multipart=None):
        converter = pipeline.Converter.__new__(pipeline.Converter)
        converter.src = SimpleNamespace(mesh=lambda _: nif.serialize(door_nif(parts)))
        converter.staging = staging
        converter.prefix = "fo4port"
        converter.no_collision = None
        converter.collision_template = b"synthetic collision"
        converter.sf_mesh_template = None
        converter.rig_doors = True
        converter.door_physics_donor = b"synthetic donor"
        converter.dynamic_template = None
        converter.door_anim_dll = dll
        converter.neutral = "placeholder.mat"
        converter._shape_material = Mock(return_value="synthetic.mat")
        converter.stats = {"assets": 0, "failed": 0}
        entry = {"origin_offset": [0.0, 0.0, 0.0], "rig": "native"}
        with patch.object(pipeline.convert_static, "convert_door",
                          return_value=({}, (0, 0, 0), ((0, 0, 0), (1, 1, 1)))) as single, \
                patch.object(pipeline.convert_static, "convert_multipart_door",
                             side_effect=multipart or (lambda *a, **k: ({}, entry))) as multi, \
                patch.object(pipeline.convert_static, "convert_static", return_value={}) as static:
            return converter.convert_nif(name), single, multi, static

    VAULT = "meshes/Interiors/Vault/Doors/SyntheticVaultDoor01.nif"

    def test_with_the_library_a_vault_door_gets_its_own_rig(self):
        with tempfile.TemporaryDirectory() as staging:
            result, single, multi, static = self.convert(staging, self.VAULT, vault_door(), "calumi.dll")
        self.assertTrue(result["ok"], result)
        single.assert_not_called()
        static.assert_not_called()
        self.assertEqual(multi.call_args.kwargs["leaf_physics_donor"], b"synthetic donor")
        self.assertEqual(multi.call_args.kwargs["collision_template"], b"synthetic collision")
        self.assertTrue(multi.call_args.kwargs["rest_pose_check"])
        self.assertEqual(result["door"]["rig"], "native")
        self.assertNotIn("door_not_opening", result)

    def test_a_single_part_hatch_and_an_elevator_door_are_routed_the_same_way(self):
        for name, parts in (("meshes/Interiors/Utility/Doors/SyntheticElevatorHatch01.nif", trapdoor()),
                            ("meshes/Interiors/Vault/Elevator/SyntheticElevatorDoor02.nif", sliding_panels()),
                            ("meshes/Architecture/Synthetic/SyntheticMainGateDoor01.nif", sliding_panels()),
                            ("meshes/Architecture/Buildings/Doors/SyntheticGarageDoor01.nif", vault_door()),
                            ("meshes/SetDressing/Doors/SyntheticSlidingDoor01.nif", sliding_panels())):
            with tempfile.TemporaryDirectory() as staging:
                result, single, multi, _ = self.convert(staging, name, parts, "calumi.dll")
            self.assertEqual(result["door"]["rig"], "native", name)
            single.assert_not_called()
            multi.assert_called_once()

    def test_without_the_library_it_stays_passable_as_before(self):
        with tempfile.TemporaryDirectory() as staging:
            result, single, multi, static = self.convert(staging, self.VAULT, vault_door(), None)
        self.assertTrue(result["ok"], result)
        single.assert_not_called()
        multi.assert_not_called()
        self.assertEqual(result["door_not_opening"], "open animation not ported: passable")
        self.assertIsNone(static.call_args.kwargs["collision_template"])          # passable: no guessed box
        self.assertNotIn("door", result)

    def test_a_failed_rig_falls_back_to_passable_and_says_why(self):
        def fail(*a, **k):
            raise nif.NifError("synthetic failure")
        with tempfile.TemporaryDirectory() as staging:
            result, _, _, static = self.convert(staging, self.VAULT, vault_door(), "calumi.dll", multipart=fail)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["door_error"], "own rig: NifError: synthetic failure")
        self.assertEqual(result["door_not_opening"], "open animation not ported: passable")
        self.assertNotIn("door", result)
        static.assert_called_once()

    def test_load_doors_and_hinged_doors_keep_their_paths(self):
        with tempfile.TemporaryDirectory() as staging:
            result, single, multi, static = self.convert(staging, "meshes/Interiors/Vault/Doors/SyntheticVaultDoorLoad01.nif",
                                                         vault_door(), "calumi.dll")
        multi.assert_not_called()
        single.assert_not_called()
        self.assertIn("load_door", result)
        self.assertNotIn("door_not_opening", result)
        with tempfile.TemporaryDirectory() as staging:                      # one hinged leaf: the verified template
            result, single, multi, _ = self.convert(staging, "meshes/SetDressing/Doors/SyntheticDoor01.nif",
                                                    two_leaves()[:1], "calumi.dll")
        single.assert_called_once()
        multi.assert_not_called()


if __name__ == "__main__":
    unittest.main()
