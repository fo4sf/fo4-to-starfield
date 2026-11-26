"""fo4sf.actor_anim: Starfield actor rigs and clips. Pure-Python parts always run; the CALUMI parts are skipped when the
external library is absent, and the vanilla round trip when the Starfield archive is absent."""
import math
import os
import pathlib
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET

from fo4sf import actor_anim as aa

DLL = aa.find_dll()
STARFIELD_ANIMS = r"D:\SteamLibrary\steamapps\common\Starfield\Data\Starfield - Animations.ba2"
MINIBOT = "meshes/actors/minibota/"


def close(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def rig():
    """A small Mini Bot-like rig: an arm with a rotated bind, as C_Arm1 (bind about 174 degrees)."""
    return aa.validate_bones([
        {"name": "Root", "parent": -1},
        {"name": "COM", "parent": 0, "translation": (0, 0, 0.5057)},
        {"name": "Arm", "parent": 1, "translation": (0, 0.145, -0.143), "rotation": (0.7082, 0.0457, 0.7025, 0.0531)},
        {"name": "Hand", "parent": 2, "translation": (0.336, 0, 0)},
    ])


def header(version=5, kind=2, frames=31):
    raw = bytearray(0x48)
    struct.pack_into("<4f", raw, 0x08, 1.0, 0.0, 0.0, 0.0)
    struct.pack_into("<4H", raw, 0x28, version, 12, frames, kind)
    return bytes(raw)


class QuaternionTests(unittest.TestCase):
    def test_left_turn_maps_forward_to_left(self):
        # Starfield: +Y forward, +X right, Z up; turninplace_left90 stores +90 degrees about +Z
        q = aa.q_from_axis_angle((0, 0, 1), math.pi / 2)
        self.assertTrue(close(aa.q_rotate(q, (0, 1, 0)), (-1, 0, 0), 1e-12))

    def test_inverse_and_slerp_endpoints(self):
        q = aa.q_norm((0.3, -0.2, 0.5, 0.7))
        self.assertTrue(close(aa.q_mul(q, aa.q_conj(q)), aa.IDENTITY, 1e-12))
        self.assertTrue(close(aa.q_slerp(aa.IDENTITY, q, 1.0), q, 1e-9))
        self.assertAlmostEqual(aa.q_angle(aa.q_slerp(aa.IDENTITY, q, 0.5), aa.IDENTITY), aa.q_angle(q, aa.IDENTITY) / 2, places=9)

    def test_zero_quaternion_refused(self):
        with self.assertRaises(aa.ActorAnimError):
            aa.q_norm((0, 0, 0, 0))


class BoneTests(unittest.TestCase):
    def test_parent_before_child_single_root_unit_scale(self):
        good = [{"name": "Root", "parent": -1}, {"name": "A", "parent": 0}]
        self.assertEqual(aa.validate_bones(good)[1]["rotation"], aa.IDENTITY)
        for bad in ([{"name": "A", "parent": 1}, {"name": "Root", "parent": -1}],
                    [{"name": "Root", "parent": -1}, {"name": "Root", "parent": 0}],
                    [{"name": "Root", "parent": -1}, {"name": "B", "parent": -1}],
                    [{"name": "Root", "parent": -1}, {"name": "A", "parent": 0, "scale": 2.0}],
                    [{"name": "Root", "parent": -1, "key": 0}, {"name": "A", "parent": 0, "key": 0}],
                    []):
            with self.assertRaises(aa.ActorAnimError):
                aa.validate_bones(bad)

    def test_model_space_composes_parent_local_binds(self):
        ms = aa.model_space(rig())
        self.assertTrue(close(ms[1][0], (0, 0, 0.5057)))
        self.assertTrue(close(ms[2][0], (0, 0.145, 0.5057 - 0.143)))
        hand = aa.q_rotate(rig()[2]["rotation"], (0.336, 0, 0))
        self.assertTrue(close(ms[3][0], tuple(a + b for a, b in zip(ms[2][0], hand)), 1e-9))


class OffsetTests(unittest.TestCase):
    def test_offset_and_local_are_inverse_with_a_rotated_bind(self):
        arm = rig()[2]
        t, q = (0.01, 0.2, -0.1), aa.q_norm((0.1, 0.6, 0.2, 0.7))
        to, qo = aa.local_to_offset(arm["translation"], arm["rotation"], t, q)
        t2, q2 = aa.offset_to_local(arm["translation"], arm["rotation"], to, qo)
        self.assertTrue(close(t, t2, 1e-12))
        self.assertLess(aa.q_angle(q, q2), 1e-9)

    def test_bind_pose_is_a_zero_offset(self):
        arm = rig()[2]
        to, qo = aa.local_to_offset(arm["translation"], arm["rotation"], arm["translation"], arm["rotation"])
        self.assertTrue(close(to, (0, 0, 0), 1e-12))
        self.assertLess(aa.q_angle(qo, aa.IDENTITY), 1e-9)

    def test_offset_is_applied_in_the_bone_rest_frame(self):
        # local = bind * offset: an offset along +X of a bone turned 90 degrees about Z moves it along +Y of the parent
        bq = aa.q_from_axis_angle((0, 0, 1), math.pi / 2)
        t, _q = aa.offset_to_local((1, 0, 0), bq, (0.5, 0, 0), aa.IDENTITY)
        self.assertTrue(close(t, (1, 0.5, 0), 1e-12))


class BlockTests(unittest.TestCase):
    def test_vanilla_channel_layout(self):
        bones = rig()
        n = 5
        poses = {
            "Root": [((0, 0.1 * f, 0), aa.IDENTITY) for f in range(n)],                      # root motion: translation only
            "COM": [((0, 0.028, 0.5057 - 0.00075), aa.q_from_axis_angle((1, 0, 0), -0.07)) for _ in range(n)],  # constant
            "Arm": [(bones[2]["translation"], bones[2]["rotation"]) for _ in range(n)],       # at its bind: no block
        }
        blocks = aa.build_blocks(bones, poses, n, keys_are="local")
        by = {b["bone"]: b for b in blocks}
        self.assertEqual([b["bone"] for b in blocks], ["Root", "COM"])
        self.assertEqual(by["Root"]["rot"], [])
        self.assertEqual([f for f, _ in by["Root"]["trans"]], list(range(n)))
        self.assertEqual(len(by["COM"]["rot"]), 1)
        self.assertEqual(len(by["COM"]["trans"]), 1)
        self.assertTrue(close(by["COM"]["trans"][0][1], (0, 0.028, -0.00075), 1e-12))   # an offset, not the bind again

    def test_keep_unknown_and_length(self):
        bones = rig()
        blocks = aa.build_blocks(bones, {}, 3, keep=("Hand",))
        self.assertEqual(blocks, [{"bone": "Hand", "index": 3, "rot": [(0, aa.IDENTITY)], "trans": []}])
        with self.assertRaises(aa.ActorAnimError):
            aa.build_blocks(bones, {"Nope": [((0, 0, 0), aa.IDENTITY)]}, 1)
        with self.assertRaises(aa.ActorAnimError):
            aa.build_blocks(bones, {"COM": [((0, 0, 0), aa.IDENTITY)]}, 2)

    def test_hemisphere_kept_between_frames(self):
        q = aa.q_from_axis_angle((0, 0, 1), 0.5)
        blocks = aa.build_blocks(rig(), {"Hand": [((0.336, 0, 0), q), ((0.336, 0, 0), tuple(-v for v in q)), ((0.336, 0, 0), aa.IDENTITY)]},
                                 3, keys_are="local")
        rots = [r for _f, r in blocks[0]["rot"]]
        self.assertGreater(aa.q_dot(rots[0], rots[1]), 0)

    def test_pad_to_length(self):
        bones = rig()
        self.assertEqual(aa.pad_to_length([], 41, bones),
                         [{"bone": "Root", "index": 0, "rot": [(0, aa.IDENTITY), (40, aa.IDENTITY)], "trans": []}])
        blk = [{"bone": "COM", "index": 1, "rot": [(0, aa.IDENTITY)], "trans": [(0, (0, 0.028, 0))]}]
        out = aa.pad_to_length(blk, 31, bones)
        self.assertEqual(out[0]["rot"][-1], (30, aa.IDENTITY))
        self.assertEqual(len(blk[0]["rot"]), 1)                                   # input untouched
        with self.assertRaises(aa.ActorAnimError):
            aa.pad_to_length([{"bone": "COM", "index": 1, "rot": [(40, aa.IDENTITY)], "trans": []}], 31, bones)

    def test_sample_and_poses_and_compare(self):
        bones = rig()
        blk = {"bone": "Root", "index": 0, "rot": [], "trans": [(0, (0, 0, 0)), (30, (0, 1.08975, 0))]}
        t, q = aa.sample_block(blk, 15)
        self.assertTrue(close(t, (0, 1.08975 / 2, 0), 1e-12))
        poses = aa.blocks_to_local_poses(bones, [blk], 31)
        self.assertEqual(len(poses["Root"]), 31)
        same = aa.compare_clips(bones, [blk], [blk], 31)
        self.assertEqual((same["max_translation"], same["max_rotation"]), (0.0, 0.0))
        moved = aa.compare_clips(bones, [blk], [], 31)
        self.assertAlmostEqual(moved["max_translation"], 1.08975)
        self.assertEqual(moved["per_bone"]["Root"]["frame"], 30)

    def test_resample_keeps_seconds(self):
        frames = [((f / 60.0, 0, 0), aa.q_from_axis_angle((0, 0, 1), f / 60.0)) for f in range(61)]
        out = aa.resample(frames, 60, 30)
        self.assertEqual(len(out), 31)
        self.assertTrue(close(out[-1][0], (1.0, 0, 0), 1e-12))
        self.assertAlmostEqual(aa.q_angle(out[15][1], aa.q_from_axis_angle((0, 0, 1), 0.5)), 0.0, places=9)


class HeaderTests(unittest.TestCase):
    def test_root_motion_fields(self):
        blocks = [{"bone": "Root", "index": 0, "rot": [(0, aa.IDENTITY), (40, aa.q_from_axis_angle((0, 0, 1), math.pi / 2))],
                   "trans": [(0, (0, 0, 0)), (40, (0, 1.09, 0))]}]
        t, q = aa.root_motion(blocks, 41)
        raw = aa.patch_root_motion(header(frames=41), t, q)
        h = aa.read_af_header(raw)
        self.assertEqual((h["version"], h["frames"], h["kind"]), (5, 41, 2))
        self.assertTrue(close(h["root_translation"], (0, 1.09, 0), 1e-6))
        # stored w, x, y, z as the vanilla turninplace_left90.af: 0.7071 at 0x08 and at 0x14
        self.assertTrue(close(struct.unpack_from("<4f", raw, 0x08), (math.sqrt(0.5), 0, 0, math.sqrt(0.5)), 1e-6))
        self.assertEqual(aa.root_motion([], 10), ((0.0, 0.0, 0.0), aa.IDENTITY))

    def test_other_layouts_refused(self):
        with self.assertRaises(aa.ActorAnimError):
            aa.patch_root_motion(header(kind=4), (0, 0, 0), aa.IDENTITY)
        with self.assertRaises(aa.ActorAnimError):
            aa.read_af_header(b"\0" * 8)


class AfxTests(unittest.TestCase):
    def test_vanilla_walkforward_shape(self):
        raw = aa.afx("WalkForward", "WalkForward.af", 1, events=[(15, "SyncLeftFoot", ""), (30, "SyncRightFoot")],
                     audio=[(0, "NPC_MiniBotA_Walk_Start")])
        root = ET.fromstring(raw)
        self.assertEqual([c.tag for c in root], ["is_state", "tag", "filename", "events", "audios"])
        self.assertEqual([c.tag for c in root.find("events/event")], ["frame", "name", "payload"])
        self.assertEqual(aa.parse_afx(raw), {"tag": "WalkForward", "filename": "WalkForward.af", "is_state": 1,
                                             "events": [(15, "SyncLeftFoot", ""), (30, "SyncRightFoot", "")],
                                             "audio": [(0, "NPC_MiniBotA_Walk_Start")]})

    def test_no_events_matches_anim_object_descriptor(self):
        from fo4sf import anim_object
        self.assertEqual(aa.afx("Idle", is_state=1), anim_object.descriptor("Idle", is_state=1))


class GuardTests(unittest.TestCase):
    def test_outputs_refused_inside_repository(self):
        repo = pathlib.Path(aa.__file__).resolve().parents[2]
        with self.assertRaises(aa.ActorAnimError):
            aa._outside_repo(repo / "tests" / "x.af")


@unittest.skipUnless(DLL, "CALUMI.Animation.dll not present")
class CalumiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cal = aa.Calumi(DLL)
        cls.tmp = tempfile.TemporaryDirectory(prefix="fo4sf-actor-anim-")
        cls.dir = pathlib.Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_rig_round_trip(self):
        bones = [dict(b) for b in rig()]
        bones[0]["key"], bones[1]["key"] = 0, 9
        path = self.cal.write_rig(bones, self.dir / "rt" / "skeleton.rig")
        back = self.cal.read_rig(path)
        cmp = aa.compare_rigs(aa.validate_bones(bones), back["bones"])
        self.assertLess(cmp["max_translation"], 1e-6)
        self.assertLess(cmp["max_rotation"], 1e-6)
        self.assertEqual([b["key"] for b in back["bones"]], [0, 9, None, None])
        self.assertEqual(back["precision"], "default")

    def test_clip_round_trip_and_header(self):
        bones = rig()
        n = 31
        poses = {"Root": [((0, 1.09 * f / 30, 0), aa.IDENTITY) for f in range(n)],
                 "Arm": [(bones[2]["translation"], aa.q_mul(bones[2]["rotation"], aa.q_from_axis_angle((0, 1, 0), 0.4 * math.sin(f / 5))))
                         for f in range(n)]}
        rig_path = self.cal.write_rig(bones, self.dir / "clip" / "skeleton.rig")
        out = aa.write_clip_files(self.cal, bones, poses, n, self.dir / "clip" / "animations", "WalkForward",
                                  events=[(15, "SyncLeftFoot"), (30, "SyncRightFoot")])
        self.assertEqual(out["af"].name, "walkforward.af")
        back = self.cal.read_clip(rig_path, out["af"])
        self.assertEqual(back["frame_count"], n)
        written = aa.build_blocks(bones, poses, n)
        cmp = aa.compare_clips(bones, written, back["blocks"], n)
        self.assertLess(cmp["max_translation"], 2e-4)        # format quantisation: 2/3 of the 0.25 mm step at most
        self.assertLess(cmp["max_rotation"], 5e-4)
        h = aa.read_af_header(out["af"].read_bytes())
        self.assertEqual((h["frames"], h["kind"]), (n, 2))
        self.assertTrue(close(h["root_translation"], (0, 1.09, 0), 1e-6))
        self.assertEqual(aa.parse_afx(out["afx"].read_bytes())["events"][0], (15, "SyncLeftFoot", ""))

    def test_shared_tag_with_own_file_stem(self):
        bones = rig()
        out = aa.write_clip_files(self.cal, bones, {}, 31, self.dir / "kd", "Knockdown", stem="Knockdown_Forward", is_state=0)
        self.assertEqual(out["af"].name, "knockdown_forward.af")
        self.assertEqual(aa.parse_afx(out["afx"].read_bytes())["filename"], "Knockdown_Forward.af")
        with self.assertRaises(aa.ActorAnimError):
            aa.write_clip_files(self.cal, bones, {}, 31, self.dir / "kd", "../Up")
        with self.assertRaises(aa.ActorAnimError):
            aa.write_clip_files(self.cal, bones, {}, 31, self.dir / "kd", "Up", events=[(31, "Late")])

    def test_empty_clip_keeps_its_length(self):
        bones = rig()
        rig_path = self.cal.write_rig(bones, self.dir / "idle" / "skeleton.rig")
        path = self.cal.write_clip(bones, [], 41, self.dir / "idle" / "idle.af")
        self.assertEqual(aa.read_af_header(path.read_bytes())["frames"], 41)
        self.assertEqual(self.cal.read_clip(rig_path, path)["frame_count"], 41)

    @unittest.skipUnless(os.path.isfile(STARFIELD_ANIMS), "Starfield - Animations.ba2 not present")
    def test_vanilla_minibot_round_trip(self):
        from fo4sf import ba2
        arc = ba2.Ba2(STARFIELD_ANIMS)
        src = self.dir / "vanilla"
        src.mkdir(exist_ok=True)
        (src / "skeleton.rig").write_bytes(arc.read(MINIBOT + "characterassets/skeleton.rig"))
        vanilla = self.cal.read_rig(src / "skeleton.rig")
        bones = [{k: b[k] for k in ("name", "parent", "translation", "rotation", "mirror", "key")} for b in vanilla["bones"]]
        rig_out = self.cal.write_rig(bones, self.dir / "vanilla_out" / "skeleton.rig")
        self.assertEqual(aa.compare_rigs(vanilla["bones"], self.cal.read_rig(rig_out)["bones"])["max_translation"], 0.0)
        for clip in ("walkforward.af", "turninplace_left90.af", "idle.af"):
            raw = arc.read(MINIBOT + "animations/" + clip)
            (src / clip).write_bytes(raw)
            frames = aa.read_af_header(raw)["frames"]
            orig = self.cal.read_clip(src / "skeleton.rig", src / clip)
            path = self.cal.write_clip(bones, orig["blocks"], frames, self.dir / "vanilla_out" / clip)
            back = self.cal.read_clip(rig_out, path)
            cmp = aa.compare_clips(bones, orig["blocks"], back["blocks"], frames)
            self.assertLess(cmp["max_translation"], 1e-4, clip)
            self.assertLess(cmp["max_rotation"], 1e-4, clip)
            ours, theirs = aa.read_af_header(path.read_bytes()), aa.read_af_header(raw)
            self.assertEqual(ours["frames"], theirs["frames"])
            self.assertTrue(close(ours["root_translation"], theirs["root_translation"], 3e-4), clip)


if __name__ == "__main__":
    unittest.main()
