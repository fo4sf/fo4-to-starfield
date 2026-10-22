"""Multi-part FO4 doors (double doors, shutters, sliding panel sets): every part FO4 moves gets a rig bone, a clip track
and its own keyframed body (synthetic fixtures only; no game data, no CALUMI library)."""
import math
import os
import pathlib
import struct
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fo4sf import checkpoints, convert_static, door_rig, native_door, nif, pipeline, sfcollision  # noqa: E402
from test_collision import fake_template  # noqa: E402
from test_review_fixes import av_fields, trishape_block  # noqa: E402

IDENTITY = (1, 0, 0, 0, 1, 0, 0, 0, 1)
ROT_Z90 = (0, -1, 0, 1, 0, 0, 0, 0, 1)            # row-major, +90 degrees about z


def quat_z(degrees):
    h = math.radians(degrees) / 2
    return (math.cos(h), 0.0, 0.0, math.sin(h))


def transform_data(rotation=None, translation=None):
    """NiTransformData: linear quaternion keys [(time, wxyz)] and linear translation keys [(time, xyz)]."""
    out = b""
    if rotation:
        out += struct.pack("<II", len(rotation), 1) + b"".join(struct.pack("<5f", t, *q) for t, q in rotation)
    else:
        out += struct.pack("<I", 0)
    if translation:
        out += struct.pack("<II", len(translation), 1) + b"".join(struct.pack("<4f", t, *v) for t, v in translation)
    else:
        out += struct.pack("<I", 0)
    return out + struct.pack("<I", 0)              # no scale keys


def reverse(keys):
    return [(1 - t, v) for t, v in reversed(keys)] if keys else keys


def sequence_block(f, name, timing_root, parts, names, extra):
    """NiControllerSequence over parts (each with its own NiTransformInterpolator + data) and extra (unkeyed) targets."""
    interps = []
    for _, position, rotation, rot_keys, trans_keys in parts:
        data = f.add_block("NiTransformData", transform_data(rot_keys, trans_keys))
        q = door_rig.quaternion_from_matrix(rotation)
        interps.append(f.add_block("NiTransformInterpolator", struct.pack("<8fi", *position, *q, 1, data)))
    interps += [-1] * len(extra)
    targets = b"".join(struct.pack("<iiBiiiii", interp, -1, 0, n, -1, -1, -1, -1) for interp, n in zip(interps, names + extra))
    timing = struct.pack("<fiIfffiiH", 1, -1, 2, 1, 0, 1, -1, timing_root, 0)
    return f.add_block("NiControllerSequence", struct.pack("<iII", f.string_index(name), len(interps), 0) + targets + timing)


def sequences(f):
    return {f.strings[struct.unpack_from("<i", f.blocks[i])[0]]: i for i in range(len(f.blocks))
            if f.type_of(i) == "NiControllerSequence"}


def door_nif(parts, root_rotation=IDENTITY, static_shape=True, extra_targets=()):
    """FO4-style door: root -> one node per part (name, position, bind rotation, rotation keys, translation keys), each with
    a 70 x 140 unit leaf shape; plus an optional static frame shape on the root. "Open" (1 s) animates every part (and
    extra_targets, names of nodes without geometry); "Close" plays the same keys backwards."""
    f = nif.NifFile(bs_version=130)
    root_name = f.string_index(b"Root")
    names = [f.string_index(p[0].encode()) for p in parts]
    extra = [f.string_index(n.encode()) for n in extra_targets]
    count = len(parts) + len(extra)
    first_part = 1
    first_shape = first_part + count
    children = list(range(first_part, first_part + count)) + ([first_shape + len(parts)] if static_shape else [])
    f.add_block("NiNode", av_fields(root_name, (70, 0, 0), root_rotation, 1) + struct.pack("<I", len(children))
                + struct.pack(f"<{len(children)}i", *children))
    for k, (name, position, rotation, *_rest) in enumerate(parts):
        f.add_block("NiNode", av_fields(names[k], position, rotation, 1) + struct.pack("<Ii", 1, first_shape + k))
    for k, name in enumerate(extra):
        f.add_block("NiNode", av_fields(name, (0, 0, 0), IDENTITY, 1) + struct.pack("<I", 0))
    for _ in parts:
        f.add_block("BSTriShape", trishape_block([(0, 0, 0), (0, 70, 0), (0, 70, 140), (2, 0, 140)], [(0, 1, 2), (0, 2, 3)]))
    if static_shape:
        f.add_block("BSTriShape", trishape_block([(-5, -80, 0), (-5, 80, 0), (-5, 80, 150)], [(0, 1, 2)]))
    sequence_block(f, b"Open", root_name, parts, names, extra)
    sequence_block(f, b"Close", root_name, [(n, p, r, reverse(rk), reverse(tk)) for n, p, r, rk, tk in parts], names, extra)
    f.footer = struct.pack("<II", 1, 0)
    return f


def two_leaves(right_bind=IDENTITY):
    return [("LeafA", (0, -70, 0), IDENTITY, [(0, quat_z(0)), (1, quat_z(-90))], None),
            ("LeafB", (0, 70, 0), right_bind, [(0, door_rig.quaternion_from_matrix(right_bind)),
                                               (1, quat_z(180 if right_bind != IDENTITY else 90))], None)]


def sliding_panels():
    return [("PanelA", (0, -35, 0), IDENTITY, None, [(0, (0, -35, 0)), (1, (0, -105, 0))]),
            ("PanelB", (0, 35, 0), IDENTITY, None, [(0, (0, 35, 0)), (1, (0, 105, 0))])]


def donor():
    """Fabricated keyframed leaf body: marker bytes in the keyframed fields, layer 2 (ANIMSTATIC) as a vanilla leaf."""
    data = bytearray(fake_template())
    for offset, size in sfcollision.KEYFRAMED_FIELDS:
        data[offset:offset + size] = b"\x07" * size
    struct.pack_into("<I", data, 240, 2)
    return bytes(data)


def fake_clip_files(plan, unit_scale):
    prepared = native_door.prepare(plan, unit_scale)
    out = {native_door.RIG_FILE: b"rig:" + ",".join(b["name"] for b in prepared["bones"]).encode()}
    for clip in prepared["clips"]:
        out[f"{native_door.CLIP_DIR}/{clip['name']}.af"] = ",".join(t["name"] for t in clip["tracks"]).encode()
        out[f"{native_door.CLIP_DIR}/{clip['name']}.afx"] = native_door.clip_descriptor(clip["name"])
    return out


def node_names(f):
    out = {}
    for i in range(len(f.blocks)):
        if f.type_of(i) == "NiNode":
            out[f.strings[struct.unpack_from("<i", f.blocks[i])[0]].decode()] = i
    return out


def collision_targets(f):
    out = {}
    for i in range(len(f.blocks)):
        if f.type_of(i) == "bhkNPCollisionObject":
            target, _, system = struct.unpack_from("<iHi", f.blocks[i])
            out[target] = f.blocks[system][4:]
    return out


class FrozenPartsTests(unittest.TestCase):
    def test_second_leaf_is_listed_and_a_knob_inside_the_leaf_is_not(self):
        self.assertEqual(convert_static.frozen_door_parts(door_nif(two_leaves())), ["LeafB"])
        single = door_nif(two_leaves()[:1], extra_targets=("REF_ATTACH_NODE",))
        self.assertEqual(convert_static.frozen_door_parts(single), [])

    def test_unreadable_motion_keeps_the_template_door(self):
        f = door_nif(two_leaves())
        opening = sequences(f)[b"Open"]
        f.blocks[opening] = f.blocks[opening][:20]
        self.assertEqual(convert_static.frozen_door_parts(f), [])


class PlacedRigTests(unittest.TestCase):
    def test_placed_root_bind_is_identity_and_file_composition_is_kept_by_default(self):
        f = door_nif(two_leaves(), root_rotation=ROT_Z90)
        self.assertEqual(door_rig.plan(f)["bones"][0]["bind"]["translation_source_units"], [70, 0, 0])
        placed = door_rig.plan(f, placed=True)["bones"][0]["bind"]
        self.assertEqual(placed["translation_source_units"], [0.0, 0.0, 0.0])
        self.assertEqual([round(x, 6) for x in placed["quaternion_wxyz"]], [1, 0, 0, 0])

    def test_animated_scene_root_refused_when_placed(self):
        f = door_nif(two_leaves())
        for name in (b"Open", b"Close"):
            data = bytearray(f.blocks[sequences(f)[name]])
            struct.pack_into("<i", data, 12 + 9, struct.unpack_from("<i", f.blocks[0])[0])   # first target -> "Root"
            f.blocks[sequences(f)[name]] = bytes(data)
        self.assertEqual(len(door_rig.plan(f)["clips"][0]["tracks"]), 2)                 # file composition: allowed
        with self.assertRaisesRegex(nif.NifError, "scene root"):
            door_rig.plan(f, placed=True)


class IdentityBindTests(unittest.TestCase):
    def pose(self, plan, clip, node, frame):
        """Model-space (t, R) of a node's track sample, composed through its rig parents' binds."""
        bones = plan["bones"]
        index = next(i for i, b in enumerate(bones) if b["node"] == node)
        track = next(t for t in plan["clips"][clip]["tracks"] if t["node"] == node)
        s = track["samples"][frame]
        def matrix(q):
            w, x, y, z = q
            return (1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y), 2 * (x * y + w * z),
                    1 - 2 * (x * x + z * z), 2 * (y * z - w * x), 2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y))
        local = (tuple(s["translation_source_units"]), matrix(s["quaternion_wxyz"]), 1.0)
        parent = bones[index]["parent"]
        while parent != -1:
            b = bones[parent]["bind"]
            local = nif._compose((tuple(b["translation_source_units"]), matrix(b["quaternion_wxyz"]), 1.0), local)
            parent = bones[parent]["parent"]
        return local

    def test_rotated_animated_bind_gets_a_static_parent_and_the_same_world_pose(self):
        plan = door_rig.plan(door_nif(two_leaves(right_bind=ROT_Z90)), placed=True)
        rebound = door_rig.animated_identity_binds(plan)
        names = [(b["name"], b["parent"]) for b in rebound["bones"]]
        self.assertEqual(names, [("Root", -1), ("LeafA", 0), ("LeafB_Bind", 0), ("LeafB", 2)])
        leaf_b = rebound["bones"][3]
        self.assertEqual(leaf_b["bind"]["quaternion_wxyz"], [1.0, 0.0, 0.0, 0.0])
        self.assertEqual(leaf_b["bind"]["translation_source_units"], [0.0, 0.0, 0.0])
        self.assertEqual(rebound["attachments"][1]["bone"], 3)          # LeafB's shape stays on LeafB
        for frame in (0, 15, 30):
            before, after = self.pose(plan, 0, leaf_b["node"], frame), self.pose(rebound, 0, leaf_b["node"], frame)
            for a, b in zip(before[0] + before[1], after[0] + after[1]):
                self.assertAlmostEqual(a, b, places=5)
        self.assertEqual(door_rig.animated_identity_binds(door_rig.plan(door_nif(two_leaves()), placed=True))["bones"],
                         door_rig.plan(door_nif(two_leaves()), placed=True)["bones"])   # identity binds: unchanged


class NativeClipConventionTests(unittest.TestCase):
    def test_tracks_only_for_animated_bones_keyed_from_the_bind(self):
        plan = door_rig.animated_identity_binds(door_rig.plan(door_nif(two_leaves()), placed=True))
        clip = native_door.prepare(plan, 1 / 70)["clips"][0]
        self.assertEqual([(t["name"], t["bone"]) for t in clip["tracks"]], [("LeafA", 1), ("LeafB", 2)])
        for track, angle in zip(clip["tracks"], (-90, 90)):
            self.assertEqual(track["channels"], ["rotation"])            # a hinge does not translate
            self.assertEqual(track["keys"][0]["translation"], [0.0, 0.0, 0.0])
            self.assertEqual([round(x, 6) for x in track["keys"][0]["quaternion_wxyz"]], [1, 0, 0, 0])
            w, _, _, z = track["keys"][-1]["quaternion_wxyz"]
            self.assertAlmostEqual(math.degrees(2 * math.atan2(z, w)), angle, places=3)
            self.assertEqual([k["frame"] for k in track["keys"]], list(range(31)))

    def test_sliding_panels_key_translation_offsets_in_metres(self):
        plan = door_rig.plan(door_nif(sliding_panels()), placed=True)
        clip = native_door.prepare(plan, 1 / 70)["clips"][0]
        self.assertEqual([t["channels"] for t in clip["tracks"]], [["rotation", "translation"]] * 2)
        self.assertEqual([round(x, 6) for x in clip["tracks"][0]["keys"][-1]["translation"]], [0, -1, 0])
        self.assertEqual([round(x, 6) for x in clip["tracks"][1]["keys"][-1]["translation"]], [0, 1, 0])
        self.assertEqual(clip["tracks"][0]["keys"][0]["translation"], [0.0, 0.0, 0.0])

    def test_rotated_animated_bind_and_animated_scale_refused(self):
        plan = door_rig.plan(door_nif(two_leaves(right_bind=ROT_Z90)), placed=True)
        with self.assertRaisesRegex(nif.NifError, "identity bind"):
            native_door.prepare(plan, 1 / 70)
        plan = door_rig.plan(door_nif(two_leaves()), placed=True)
        plan["clips"][0]["tracks"][0]["samples"][3]["scale"] = 2
        with self.assertRaisesRegex(nif.NifError, "scale"):
            native_door.prepare(plan, 1 / 70)

    def test_quaternion_keys_stay_in_one_hemisphere(self):
        plan = door_rig.plan(door_nif(two_leaves()), placed=True)
        samples = plan["clips"][0]["tracks"][0]["samples"]
        for s in samples[16:]:
            s["quaternion_wxyz"] = [-x for x in s["quaternion_wxyz"]]
        keys = native_door.prepare(plan, 1 / 70)["clips"][0]["tracks"][0]["keys"]
        for a, b in zip(keys, keys[1:]):
            self.assertGreater(sum(x * y for x, y in zip(a["quaternion_wxyz"], b["quaternion_wxyz"])), 0)

    def test_export_files_maps_the_rig_and_clips_next_to_the_model(self):
        def exporter(plan, dll, output, unit_scale):
            prepared = native_door.prepare(plan, unit_scale)
            (pathlib.Path(output) / "door.rig").write_bytes(b"rig")
            for clip in prepared["clips"]:
                (pathlib.Path(output) / (clip["name"] + ".af")).write_bytes(clip["name"].encode())
                (pathlib.Path(output) / (clip["name"] + ".afx")).write_bytes(native_door.clip_descriptor(clip["name"]))
            (pathlib.Path(output) / "events.json").write_text("{}")
            return prepared
        files = native_door.export_files(door_rig.plan(door_nif(two_leaves()), placed=True), "unused.dll", 1 / 70, exporter)
        self.assertEqual(sorted(files), ["animations/Close.af", "animations/Close.afx", "animations/Open.af",
                                         "animations/Open.afx", "characterassets/skeleton.rig"])
        self.assertEqual(files["animations/Open.af"], b"Open")


class LeafBoxFloorTests(unittest.TestCase):
    def test_a_flat_single_leaf_gets_the_leaf_floor_not_the_crash_value(self):
        # the leaf is 2 units (0.029 m) deep: its box is clamped. 0.02 was the value every Red Rocket crash read as an index
        f = door_nif([("Leaf", (0, 0, 0), IDENTITY, [(0, quat_z(0)), (1, quat_z(-90))], None)])
        count = len([s for s in nif.fo4_trishapes(f) if s.positions and s.triangles])
        files, _offset, _bounds = convert_static.convert_door(nif.serialize(f), "fo4port/doors/testsingle",
                                                              ["Materials\\x.mat"] * count, collision_template=fake_template())
        (blob,) = collision_targets(nif.parse(files["meshes/fo4port/doors/testsingle.nif"])).values()
        _centre, half = sfcollision.read_box(blob)
        self.assertAlmostEqual(half[0], 0.05, places=6)
        self.assertEqual(sfcollision.MIN_LEAF_HALF, 0.05)


class MultipartDoorTests(unittest.TestCase):
    def convert(self, parts, **kw):
        f = door_nif(parts, **kw)
        count = len([s for s in nif.fo4_trishapes(f) if s.positions and s.triangles])
        return f, convert_static.convert_multipart_door(nif.serialize(f), "fo4port/doors/testdouble", ["Materials\\x.mat"] * count,
                                                        fake_clip_files, collision_template=fake_template(),
                                                        leaf_physics_donor=donor())

    def test_both_leaves_get_a_bone_a_track_and_their_own_keyframed_body(self):
        _, (files, door) = self.convert(two_leaves(), root_rotation=ROT_Z90)
        model = nif.parse(files["meshes/fo4port/doors/testdouble.nif"])
        nodes, bodies = node_names(model), collision_targets(model)
        self.assertEqual(set(bodies), {nodes["LeafA"], nodes["LeafB"]})       # the static frame keeps no body
        for leaf in ("LeafA", "LeafB"):
            blob = bodies[nodes[leaf]]
            for offset, size in sfcollision.KEYFRAMED_FIELDS:
                self.assertEqual(blob[offset:offset + size], donor()[offset:offset + size])   # keyframed like the vanilla leaf
            centre, half = sfcollision.read_box(blob)                         # leaf-local: 1 m wide, 2 m tall
            for got, want in zip(centre + half, (1 / 70, 0.5, 1.0, sfcollision.MIN_LEAF_HALF, 0.5, 1.0)):
                self.assertAlmostEqual(got, want, places=3)
        self.assertEqual(nif._av_transform(model.blocks[nodes["Root"]])[0], (0.0, 0.0, 0.0))   # placed: no root shift
        self.assertEqual(nif._av_transform(model.blocks[nodes["LeafB"]])[0], (0.0, 1.0, 0.0))
        self.assertEqual(files["meshes/fo4port/doors/testdouble/animations/Open.af"], b"LeafA,LeafB")
        self.assertEqual(files["meshes/fo4port/doors/testdouble/characterassets/skeleton.rig"], b"rig:Root,LeafA,LeafB")
        self.assertEqual(door["origin_offset"], [0.0, 0.0, 0.0])
        self.assertEqual(door["animated_bones"], ["LeafA", "LeafB"])
        self.assertEqual(door["moving_bodies"], 2)
        self.assertEqual(door["skeleton"], "fo4port\\doors\\testdouble\\characterassets\\skeleton.rig")
        self.assertEqual(door["animations"], "fo4port\\doors\\testdouble\\animations")
        self.assertEqual(door["anim_graph"], "AnimTextData\\Tables\\Graphs\\SimpleOpenClose01.agx")
        self.assertEqual(sorted(door["files"]), sorted(k for k in files if k.startswith("meshes/fo4port/doors/testdouble/")))
        lo, hi = door["bounds"]
        self.assertEqual([round(x, 3) for x in lo + hi], [-0.071, -1.143, 0.0, 0.029, 2.0, 2.143])

    def test_rotated_leaf_bind_and_sliding_panels_convert(self):
        _, (files, door) = self.convert(two_leaves(right_bind=ROT_Z90))
        nodes = node_names(nif.parse(files["meshes/fo4port/doors/testdouble.nif"]))
        self.assertIn("LeafB_Bind", nodes)
        self.assertEqual(files["meshes/fo4port/doors/testdouble/characterassets/skeleton.rig"], b"rig:Root,LeafA,LeafB_Bind,LeafB")
        _, (files, door) = self.convert(sliding_panels())
        self.assertEqual(door["animated_bones"], ["PanelA", "PanelB"])
        self.assertEqual(door["moving_bodies"], 2)

    def test_effect_shapes_are_left_out_and_inputs_are_checked(self):
        f = door_nif(two_leaves())
        raw = nif.serialize(f)
        files, door = convert_static.convert_multipart_door(raw, "fo4port/d", ["a.mat", "b.mat", None], fake_clip_files,
                                                            collision_template=fake_template(), leaf_physics_donor=donor())
        self.assertEqual(sum(nif.parse(files["meshes/fo4port/d.nif"]).type_of(i) == "BSGeometry"
                             for i in range(len(nif.parse(files["meshes/fo4port/d.nif"]).blocks))), 2)
        for kwargs in ({"collision_template": None, "leaf_physics_donor": donor()},
                       {"collision_template": fake_template(), "leaf_physics_donor": None}):
            with self.assertRaises(ValueError):
                convert_static.convert_multipart_door(raw, "fo4port/d", ["a", "b", "c"], fake_clip_files, **kwargs)
        with self.assertRaises(ValueError):
            convert_static.convert_multipart_door(raw, "fo4port/d", ["a"], fake_clip_files,
                                                  collision_template=fake_template(), leaf_physics_donor=donor())
        with self.assertRaises(ValueError):
            convert_static.convert_multipart_door(raw, "fo4port/d", ["a", "b", "c"], lambda plan, scale: {},
                                                  collision_template=fake_template(), leaf_physics_donor=donor())

    def test_missing_close_sequence_and_case_only_name_differences_are_refused(self):
        f = door_nif(two_leaves())
        data = bytearray(f.blocks[sequences(f)[b"Close"]])
        struct.pack_into("<i", data, 0, f.string_index(b"Idle"))
        f.blocks[sequences(f)[b"Close"]] = bytes(data)
        clashing = [("Leaf", *two_leaves()[0][1:]), ("LEAF", *two_leaves()[1][1:])]
        for source, message in ((f, "Close"), (door_nif(clashing), "case")):
            with self.assertRaisesRegex(nif.NifError, message):
                convert_static.convert_multipart_door(nif.serialize(source), "fo4port/d", ["a", "b", "c"], fake_clip_files,
                                                      collision_template=fake_template(), leaf_physics_donor=donor())


class PipelineRoutingTests(unittest.TestCase):
    def convert(self, staging, dll, multipart=None):
        converter = pipeline.Converter.__new__(pipeline.Converter)
        converter.src = SimpleNamespace(mesh=lambda _: nif.serialize(door_nif(two_leaves())))
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
        with patch.object(pipeline.convert_static, "convert_door", return_value=({}, (0, 0, 0), ((0, 0, 0), (1, 1, 1)))) as single, \
                patch.object(pipeline.convert_static, "convert_multipart_door",
                             side_effect=multipart or (lambda *a, **k: ({}, entry))) as multi:
            return converter.convert_nif("meshes/doors/SyntheticDoubleDoor01.nif"), single, multi

    def test_library_present_routes_the_double_door_to_its_own_rig(self):
        with tempfile.TemporaryDirectory() as staging:
            result, single, multi = self.convert(staging, "calumi.dll")
        self.assertTrue(result["ok"], result)
        single.assert_not_called()
        self.assertEqual(multi.call_args.kwargs["leaf_physics_donor"], b"synthetic donor")
        self.assertEqual(result["door"]["rig"], "native")
        self.assertNotIn("door_frozen_parts", result)

    def test_without_the_library_the_template_door_lists_the_parts_left_closed(self):
        with tempfile.TemporaryDirectory() as staging:
            result, single, multi = self.convert(staging, None)
        self.assertTrue(result["ok"], result)
        multi.assert_not_called()
        single.assert_called_once()
        self.assertEqual(result["door_frozen_parts"], ["LeafB"])

    def test_a_failed_multipart_build_falls_back_and_says_why(self):
        def fail(*a, **k):
            raise nif.NifError("synthetic failure")
        with tempfile.TemporaryDirectory() as staging:
            result, single, _ = self.convert(staging, "calumi.dll", multipart=fail)
        self.assertTrue(result["ok"], result)
        single.assert_called_once()
        self.assertIn("multi-part: NifError: synthetic failure", result["door_error"])
        self.assertEqual(result["door_frozen_parts"], ["LeafB"])


class CheckpointInventoryTests(unittest.TestCase):
    def test_a_doors_rig_and_clips_are_checkpoint_outputs(self):
        _, (files, door) = MultipartDoorTests().convert(two_leaves())
        with tempfile.TemporaryDirectory() as staging:
            for relative, data in files.items():
                path = pathlib.Path(staging, relative)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            inventory = checkpoints.output_inventory(staging, {"out_name": "fo4port/doors/testdouble", "door": door})
        for relative in door["files"]:
            self.assertIn(relative, inventory)
        with self.assertRaises(ValueError):
            checkpoints.output_inventory("unused", {"out_name": "x", "door": {"files": ["../escape"]}})


if __name__ == "__main__":
    unittest.main()


class LeafClampHelperTests(unittest.TestCase):
    def test_clamped_leaf_halves_raises_thin_axes(self):
        from fo4sf import sfcollision
        # SafeDoor01 measured raw ~0.021, 0.011, 0.093
        raw = (0.021, 0.011, 0.093)
        clamped, raised = sfcollision.clamped_leaf_halves(raw)
        self.assertEqual(clamped, (0.05, 0.05, 0.093))
        self.assertEqual(raised, 2)
        # already thick
        clamped2, raised2 = sfcollision.clamped_leaf_halves((0.1, 0.2, 0.3))
        self.assertEqual(clamped2, (0.1, 0.2, 0.3))
        self.assertEqual(raised2, 0)
