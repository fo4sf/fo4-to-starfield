"""No-key identity scene roots may retain child animation; no sampling-based exemption."""
import math
import struct
import unittest

from fo4sf import convert_static, door_rig, native_door, nif
from test_door_motion import fixture
from test_door_motion_nested import rotation_track, sequence
import test_door_two_panels as panels

ABSENT = -3.4028234663852886e38


def source(values=None, *, data=-1, close_values=None):
    f = fixture()  # Stored scene-root translation is 70; placed roots must ignore it.
    values = values if values is not None else [ABSENT]*7 + [1]
    def track(v):
        return f.add_block('NiTransformInterpolator', struct.pack('<8fi', *v, data))
    f.blocks[5] = sequence(f, b'Open', [(0, track(values)), (1, rotation_track(f, 90)), (2, rotation_track(f, -90))])
    f.add_block('NiControllerSequence', sequence(f, b'Close', [(0, track(close_values or values))]))
    return f


class DoorRootIdentityTests(unittest.TestCase):
    def test_identity_root_does_not_make_a_static_frame_a_moving_box(self):
        f = panels.door_nif(panels.two_leaves())
        def convert():
            count = len([s for s in nif.fo4_trishapes(f) if s.positions and s.triangles])
            return convert_static.convert_multipart_door(
                nif.serialize(f), 'fo4port/doors/testdouble', ['Materials\\x.mat']*count,
                panels.fake_clip_files, collision_template=panels.fake_template(), leaf_physics_donor=panels.donor())
        baseline_files, baseline_report = convert()
        track = f.add_block('NiTransformInterpolator', struct.pack('<8fi', *([ABSENT]*7+[1]), -1))
        root_name = struct.unpack_from('<i', f.blocks[0])[0]
        target = struct.pack('<iiBiiiii', track, -1, 0, root_name, -1, -1, -1, -1)
        for index in panels.sequences(f).values():
            raw = f.blocks[index]
            name, count, grow = struct.unpack_from('<iII', raw)
            f.blocks[index] = struct.pack('<iII', name, count+1, grow) + target + raw[12:]
        files, report = convert()
        self.assertEqual(report['moving_bodies'], 2)
        self.assertEqual(report['animated_bones'], ['LeafA', 'LeafB'])
        self.assertEqual(report, baseline_report)
        self.assertEqual(files, baseline_files)

    def test_absent_channels_use_placed_identity_and_keep_child_motion(self):
        plan = door_rig.plan(source(), placed=True)
        self.assertEqual(plan['bones'][0]['bind'], {
            'translation_source_units': [0, 0, 0], 'quaternion_wxyz': [1, 0, 0, 0], 'scale': 1})
        self.assertTrue(all(t['node'] != 0 for c in plan['clips'] for t in c['tracks']))
        child = plan['clips'][0]['tracks'][0]['samples'][-1]
        self.assertAlmostEqual(child['quaternion_wxyz'][3], math.sqrt(.5), places=6)
        native = native_door.prepare(plan, 1/70)
        self.assertTrue(native)  # Pure in-memory preparation; no DLL or generated assets.

    def test_explicit_identity_and_quaternion_sign_are_constant(self):
        for w in (1, -1):
            with self.subTest(w=w):
                door_rig.plan(source([0, 0, 0, w, 0, 0, 0, 1]), placed=True)

    def test_null_root_track_keeps_identity_bind(self):
        f = source()
        f.blocks[5] = sequence(f, b'Open', [(0, -1), (1, rotation_track(f, 90))])
        door_rig.plan(f, placed=True)

    def test_any_nonidentity_channel_in_either_clip_is_refused(self):
        for index, value in ((0, .001), (1, 1), (2, -1), (4, .001), (5, 1), (6, -1), (7, 1.01)):
            for close in (False, True):
                with self.subTest(index=index, close=close):
                    values = [0, 0, 0, 1, 0, 0, 0, 1]
                    values[index] = value
                    f = source(close_values=values) if close else source(values)
                    with self.assertRaisesRegex(nif.NifError, 'scene root'):
                        door_rig.plan(f, placed=True)

    def test_nonfinite_defaults_are_not_mistaken_for_absent_channels(self):
        for index in range(8):
            for value in (math.nan, math.inf, -math.inf):
                with self.subTest(index=index, value=value):
                    values = [ABSENT]*7 + [1]
                    values[index] = value
                    with self.assertRaisesRegex(nif.NifError, 'scene root'):
                        door_rig.plan(source(values), placed=True)

    def test_keyed_roots_stay_refused_even_if_samples_look_constant(self):
        for constant in (True, False):
            f = source()
            f.blocks[5] = sequence(f, b'Open', [(0, rotation_track(f, 0 if constant else 90))])
            with self.assertRaisesRegex(nif.NifError, 'scene root'):
                door_rig.plan(f, placed=True)

    def test_malformed_channels_do_not_gain_the_absent_default(self):
        for values in ([ABSENT, 1, 0, 1, 0, 0, 0, 1],
                       [1e31, 0, 0, 1, 0, 0, 0, 1],
                       [0, 0, 0, 0, 0, 0, 0, 1],
                       [0, 0, 0, 1, 0, 0, 0, 1e31]):
            with self.subTest(values=values):
                with self.assertRaisesRegex(nif.NifError, 'scene root'):
                    door_rig.plan(source(values), placed=True)

    def test_unknown_interpolator_stays_refused(self):
        f = source()
        unknown = f.add_block('NiFloatInterpolator', b'')
        f.blocks[5] = sequence(f, b'Open', [(0, unknown)])
        with self.assertRaisesRegex(nif.NifError, 'scene root'):
            door_rig.plan(f, placed=True)

    def test_duplicate_identity_root_bindings_stay_refused(self):
        f = source()
        f.blocks[5] = sequence(f, b'Open', [(0, -1), (0, -1), (1, rotation_track(f, 90))])
        with self.assertRaisesRegex(nif.NifError, 'duplicate door target'):
            door_rig.plan(f, placed=True)

    def test_nonplaced_root_bind_remains_unchanged(self):
        plan = door_rig.plan(source())
        self.assertEqual(plan['bones'][0]['bind']['translation_source_units'], [70, 0, 0])


if __name__ == '__main__':
    unittest.main()
