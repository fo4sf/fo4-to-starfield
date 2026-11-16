"""Actual ascent and in-vault platform/door branches with substituted natives."""
import copy
import json
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.test_newgame import PSC, CS, read, ng, namespace, fake_zip
import tests.test_newgame as newgame_tests
from tests.test_exit_arrival import Reference, translated_functions
import make_anim_console as mac
import make_cog_door as mcd


GLOBALS = ('ridingLift, ridingCell, rideStartedAt, riderX, riderY, riderZ, '
           'rideActive, rideDone, rideTransferred, exitFailed, asked')


class Lift(Reference):
    def GetBaseObject(self): return self.base
    def PlayAnimation(self, name):
        self.plays.append(name)
        return self.accepted


class DoorRef(Reference):
    def __init__(self, open_state=3):
        super().__init__(None, (-59.4, -3.9, 0.0))
        self.open_state = open_state
        self.set_open_calls = []

    def GetOpenState(self): return self.open_state
    def SetOpen(self, val):
        self.set_open_calls.append(val)
        self.open_state = 1 if val else 3


class InVaultPromptAndDoorTests(unittest.TestCase):
    """Prompt appears ONLY on the platform floor (0001B29E, radius 2.0 m) after the cog door opens (stage >= 30)."""

    def setUp(self):
        self.player = Reference(None, (-53.7, -3.7, 0.53))
        self.player.interior = True
        self.door = DoorRef(open_state=3)
        self.prompts = 0
        self.button = 0
        self.stages = []
        self.ascents = []
        self.surfaces = []
        def show():
            self.prompts += 1
            return self.button
        self.ns = dict(
            asked=False, CogDoorId=0x126D, VaultPlugin='FO4Port.esm',
            ConsoleX=-53.7, ConsoleY=-3.7, ConsoleZ=0.53, ConsoleRadius=2.5,
            PlatformX=-77.742, PlatformY=-3.958, PlatformZ=-1.751, PlatformRadius=2.0,
            LiftId=0x1618,
            Game=SimpleNamespace(GetFormFromFile=lambda i, _: self.door if i == 0x126D else None),
            ExitMessage=SimpleNamespace(Show=show),
            AdvanceTo=self.stages.append,
            StartAscent=self.ascents.append,
            Surface=self.surfaces.append,
        )
        exec(compile(translated_functions(read(PSC), ('InVault', 'Near'), 'asked'), PSC, 'exec'), self.ns)

    def test_platform_marker_and_radius_constants(self):
        self.assertIn('Fo4PlatformMarker = 0x01B29E', read(CS))
        self.assertIn('float Property PlatformRadius = 2.0 Auto Const', read(PSC))

    def test_never_prompts_at_console_or_catwalk_or_before_door_opens(self):
        # At the console (-53.7, -3.7, 0.53): opens door -> stage 30, ZERO elevator prompts!
        self.ns['InVault'](self.player, 20)
        self.assertEqual(self.door.set_open_calls, [True])
        self.assertEqual(self.stages, [30])
        self.assertEqual(self.prompts, 0)
        # On the catwalk at 000244EB's NIF root (-70.392, -2.742, -0.114): 7.45 m from platform -> ZERO prompts!
        self.player.pos = (-70.392, -2.742, -0.114)
        self.ns['InVault'](self.player, 30)
        self.assertEqual(self.prompts, 0)
        # Even at platform coordinates, if stage is still 20 and door is closed -> ZERO prompts!
        self.door.open_state = 3
        self.player.pos = (-77.742, -3.958, -1.751)
        self.ns['InVault'](self.player, 20)
        self.assertEqual(self.prompts, 0)

    def test_direct_gear_door_e_activation_advances_stage_30_and_platform_starts_ascent(self):
        # Pressing E directly on FO4SFVaultGearDoor.esm sets open_state to 2 (opening) or 1 (open) without visiting console.
        self.door.open_state = 2
        self.player.pos = (-60.0, -3.9, 0.0)
        self.ns['InVault'](self.player, 20)
        self.assertEqual(self.door.set_open_calls, [])
        self.assertEqual(self.stages, [30])
        self.assertEqual(self.prompts, 0)
        # Stepping onto the platform floor (-77.742, -3.958, -1.751) prompts once and starts ascent.
        self.player.pos = (-77.742, -3.958, -1.751)
        self.ns['InVault'](self.player, 30)
        self.ns['InVault'](self.player, 30)
        self.assertEqual(self.prompts, 1)
        self.assertEqual(self.ascents, [self.player])


class AscentExecutionTests(unittest.TestCase):
    def setUp(self):
        self.now = 10.0
        self.cell = object()
        self.player = Reference(None, (-77.742, -3.958, -1.72))
        self.player.interior, self.player.cell = True, self.cell
        self.lift = Lift(None, (-70.392, -2.742, -0.114))
        self.base = object()
        self.lift.base, self.lift.plays, self.lift.accepted = self.base, [], True
        self.lift.cell = self.cell
        self.failures, self.transfers, self.registrations, self.unregistrations = [], [], [], []
        self.ns = dict(ridingLift=None, ridingCell=None, rideStartedAt=0.0, riderX=0.0, riderY=0.0, riderZ=0.0,
                       rideActive=False, rideDone=False, rideTransferred=False, exitFailed=False, asked=False,
                       PlatformX=-77.742, PlatformY=-3.958, PlatformZ=-1.751, PlatformRadius=2.0,
                       LiftId=0x1618, LiftBaseId=0x1619, LiftRise=21.6, LiftSeconds=9.8667, LiftDoneMargin=0.25, VaultPlugin='FO4Port.esm',
                       Game=SimpleNamespace(GetFormFromFile=lambda i, _: self.lift if i == 0x1618 else self.base,
                                            GetPlayer=lambda: self.player),
                       Utility=SimpleNamespace(GetCurrentRealTime=lambda: self.now),
                       StandsInVault=lambda _: True, Surface=self.transfers.append,
                       RegisterForAnimationEvent=lambda *args: self.registrations.append(args),
                       UnregisterForAnimationEvent=lambda *args: self.unregistrations.append(args))
        text = read(PSC)
        event = re.search(r'Event OnAnimationEvent\((.*?)\)\n(.*?)EndEvent', text, re.S)
        text += '\nFunction AscentEvent(' + event[1] + ')\n' + event[2] + 'EndFunction\n'
        exec(compile(translated_functions(text, ('StartAscent', 'AscentEvent', 'AtLiftTop', 'CheckAscent', 'Near', 'FailExit'), GLOBALS), PSC, 'exec'), self.ns)
        actual_fail = self.ns['FailExit']
        def fail(reason):
            self.failures.append(reason)
            actual_fail(reason)
        self.ns['FailExit'] = fail

    def run_branch(self, name): self.ns[name](self.player)
    def done(self, source=None): self.ns['AscentEvent'](source or self.lift, 'Done')
    def top(self): self.player.pos = (-77.742, -3.958, 19.88)

    def test_carries_before_exactly_one_arrival_and_never_moves_player_on_start(self):
        self.run_branch('StartAscent')
        self.assertEqual(self.lift.plays, ['Play01'])
        self.assertEqual(self.player.moves, [])
        self.assertEqual(self.transfers, [])
        self.now += 9.8
        self.done()
        self.assertTrue(self.ns['rideDone'])
        self.run_branch('CheckAscent')
        self.assertEqual(self.transfers, [])
        self.top()
        self.run_branch('CheckAscent')
        self.run_branch('CheckAscent')
        self.run_branch('StartAscent')
        self.assertEqual(self.transfers, [self.player])
        self.assertEqual(self.lift.plays, ['Play01'])
        self.assertEqual(self.unregistrations, [(self.lift, 'Done')])

    def test_early_done_is_not_reused_after_player_rises(self):
        self.run_branch('StartAscent')
        self.now += 0.068
        self.done()
        self.now += 10
        self.top()
        self.run_branch('CheckAscent')
        self.assertFalse(self.ns['rideDone'])
        self.assertEqual(self.transfers, [])
        self.done()
        self.run_branch('CheckAscent')
        self.assertEqual(self.transfers, [self.player])

    def test_wrong_source_or_event_cannot_complete(self):
        self.run_branch('StartAscent')
        self.now += 10
        self.top()
        self.done(object())
        self.ns['AscentEvent'](self.lift, 'Trans01')
        self.run_branch('CheckAscent')
        self.assertFalse(self.ns['rideDone'])
        self.assertEqual(self.transfers, [])

    def test_refused_play_and_missing_wrong_base_cell_or_unloaded_lift_fail(self):
        for fault in ('refused', 'missing', 'base', 'cell', 'unloaded', 'exterior', 'other_vault'):
            with self.subTest(fault=fault):
                self.setUp()
                if fault == 'refused': self.lift.accepted = False
                if fault == 'missing': self.ns['Game'].GetFormFromFile = lambda *_: None
                if fault == 'base': self.lift.base = object()
                if fault == 'cell': self.lift.cell = object()
                if fault == 'unloaded': self.lift.loaded = False
                if fault == 'exterior': self.player.interior = False
                if fault == 'other_vault': self.ns['StandsInVault'] = lambda _: False
                self.run_branch('StartAscent')
                self.now += 10
                self.top()
                self.done()
                self.run_branch('CheckAscent')
                self.assertEqual(len(self.failures), 1)
                self.assertEqual(self.transfers, [])
                self.assertFalse(self.ns['rideActive'])

    def test_done_without_height_or_outside_footprint_waits_then_times_out(self):
        for pos in ((-77.742, -3.958, -1.72), (-77.742, -3.958, 20.64),
                    (-77.742, -3.958, 19.12), (-74.742, -3.958, 19.88)):
            with self.subTest(pos=pos):
                self.setUp()
                self.run_branch('StartAscent')
                self.now += 10
                self.player.pos = pos
                self.done()
                self.run_branch('CheckAscent')
                self.assertEqual(self.transfers, [])
                self.now += 31
                self.run_branch('CheckAscent')
                self.assertEqual(self.failures, ['lift_timeout'])

    def test_cell_change_or_unloaded_timeout_cannot_transfer(self):
        for fault in ('player_cell', 'lift_cell', 'exterior', 'unloaded'):
            with self.subTest(fault=fault):
                self.setUp()
                self.run_branch('StartAscent')
                self.now += 10
                self.top()
                self.done()
                if fault == 'player_cell': self.player.cell = object()
                if fault == 'lift_cell': self.lift.cell = object()
                if fault == 'exterior': self.player.interior = False
                if fault == 'unloaded': self.player.loaded = False
                self.run_branch('CheckAscent')
                self.assertEqual(self.transfers, [])
                self.now += 31
                if not self.failures: self.run_branch('CheckAscent')
                self.assertEqual(len(self.failures), 1)

    def test_rider_leaves_during_registration_or_before_arrival(self):
        def leave(*_): self.player.cell = object()
        self.ns['RegisterForAnimationEvent'] = leave
        self.run_branch('StartAscent')
        self.assertEqual(self.failures, ['lift_rider_left_before_play'])
        self.assertEqual(self.lift.plays, [])
        self.setUp()
        self.run_branch('StartAscent')
        self.now += 10
        self.top()
        self.done()
        self.ns['UnregisterForAnimationEvent'] = leave
        self.run_branch('CheckAscent')
        self.assertEqual(self.failures, ['lift_rider_left_before_arrival'])
        self.assertEqual(self.transfers, [])


def lift_animation():
    carried = [dict(bone=bone, node=i) for i, (bone, n) in enumerate(mac.LIFT_CARRIED_BY_BONE.items()) for _ in range(n)]
    return dict(
        idles='toggle',
        rest_after='stage2',
        moving_bodies=mac.LIFT_MOVING_BODIES,
        fo4_collision=dict(carried=True, box_fallback_bones=[], carried_bodies=carried),
        clips=[
            dict(name='StateA_Play', seconds=9.8667, motion=[dict(bone='b_Platform', travel_m=[0, 0, 21.6], rotation_deg=0)]),
            dict(name='StateB_Play', seconds=23.8333, motion=[dict(bone='b_Platform', travel_m=[0, 0, -21.6], rotation_deg=0)]),
            dict(name='StateA_Idle', hold_of='StateB_Play', hold_frame='last'),
            dict(name='StateB_Idle', hold_of='StateA_Play', hold_frame='last'),
        ],
    )


class ProductionRecipeTests(unittest.TestCase):
    def test_known_recipe_and_rejected_drift(self):
        self.assertEqual(mac.LIFT_MOVING_BODIES, 37)
        a = lift_animation()
        mac.validate_lift_animation(a)
        for mutate in (lambda a: a.update(rest_after='stage3'),
                       lambda a: a.update(moving_bodies=0),
                       lambda a: a.update(moving_bodies=12),
                       lambda a: a.update(moving_bodies=45),
                       lambda a: a['fo4_collision'].update(box_fallback_bones=['b_Platform']),
                       lambda a: a['fo4_collision']['carried_bodies'].pop(),
                       lambda a: a['clips'][0].update(seconds=20), lambda a: a['clips'][0].update(slowed=True),
                       lambda a: a['clips'][0]['motion'][0].update(travel_m=[0, 0, -21.6]),
                       lambda a: a['clips'][0]['motion'][0].update(rotation_deg=2),
                       lambda a: a['clips'][2].update(hold_frame='first'),
                       lambda a: a['clips'][3].update(hold_of='StateB_Play'),
                       lambda a: a['clips'].append(copy.deepcopy(a['clips'][0]))):
            bad = copy.deepcopy(a)
            mutate(bad)
            with self.assertRaises(SystemExit): mac.validate_lift_animation(bad)

    def test_production_refuses_old_slot_map_before_output(self):
        with tempfile.TemporaryDirectory() as d:
            args = SimpleNamespace(states='stage2=StateA_Play,stage3=StateB_Play', production_lift=True,
                                   edid=mac.LIFT_EDID, out=str(Path(d) / 'out'))
            with self.assertRaisesRegex(SystemExit, 'production-lift'): mac.stage(args)
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_production_manifests_reject_probe_bytes_drift_and_changed_master(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            port, sf = root / 'port.input', root / 'sf.input'
            port.write_bytes(b'port'); sf.write_bytes(b'sf')
            # Lift component
            lift_dir = root / 'lift'
            (lift_dir / 'Data/meshes').mkdir(parents=True)
            (lift_dir / 'Data/meshes/lift.nif').write_bytes(b'model')
            (lift_dir / mac.LIFT_PLUGIN).write_bytes(b'plugin')
            plan = dict(kind=mac.LIFT_KIND, plugins=[mac.LIFT_PLUGIN], states=mac.LIFT_STATES, rise_m=21.6,
                        seconds=9.8667, event='Play01', outputs=mac.probe_a.stage_files(str(lift_dir)),
                        inputs={'FO4Port.esm': {'sha256': ng.sha256(port)}, 'Starfield.esm': {'sha256': ng.sha256(sf)}})
            (lift_dir / 'plan.json').write_text(json.dumps(plan))
            ng.exit_lift_component(str(lift_dir), port, sf)
            plan['kind'] = 'anim-console'; (lift_dir / 'plan.json').write_text(json.dumps(plan))
            with self.assertRaises(SystemExit): ng.exit_lift_component(str(lift_dir), port, sf)
            # Cog door component
            cog_dir = root / 'cog'
            (cog_dir / 'Data/meshes').mkdir(parents=True)
            (cog_dir / 'Data/meshes/cog.nif').write_bytes(b'cog')
            (cog_dir / mcd.COG_PLUGIN).write_bytes(b'cogplugin')
            cplan = dict(kind=mcd.COG_KIND, plugins=[mcd.COG_PLUGIN], ref='00126D',
                         outputs=mac.probe_a.stage_files(str(cog_dir)),
                         inputs={'FO4Port.esm': {'sha256': ng.sha256(port)}, 'Starfield.esm': {'sha256': ng.sha256(sf)}})
            (cog_dir / 'plan.json').write_text(json.dumps(cplan))
            ng.cog_door_component(str(cog_dir), port, sf)
            cplan['kind'] = mcd.KIND; (cog_dir / 'plan.json').write_text(json.dumps(cplan))
            with self.assertRaises(SystemExit): ng.cog_door_component(str(cog_dir), port, sf)

    def test_asset_stage_has_no_probe_compile_or_script(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out, final = root / 'partial', root / 'final'
            work = out / 'work'
            work.mkdir(parents=True)
            (out / 'Data/meshes').mkdir(parents=True)
            (out / 'Data/meshes/lift.nif').write_bytes(b'model')
            port, sf = root / 'port.input', root / 'sf.input'
            port.write_bytes(b'port'); sf.write_bytes(b'sf')
            calls = []
            def run(args):
                calls.append(args)
                if 'build' in args: (out / mac.LIFT_PLUGIN).write_bytes(b'plugin')
                return SimpleNamespace(stdout='all checks pass')
            res = dict(anim=lift_animation(), out_name='lift')
            res['anim'].update(skeleton='lift/skeleton.rig', animations='lift/animations')
            before = {'Starfield.esm': ng.sha256(sf), 'FO4Port.esm': ng.sha256(port)}
            with patch.object(mac, 'run', run), patch.object(mac, 'compile_text', side_effect=AssertionError('probe compile forbidden')):
                mac.finish_production_lift(SimpleNamespace(edid=mac.LIFT_EDID), str(out), str(final), str(work), ['dotnet'],
                                           str(port), str(sf), before, 'original.nif', {'base_id': '001234'}, res, ['Data/meshes/lift.nif'], [])
            self.assertTrue(all('--production-lift' in c for c in calls))
            self.assertFalse((final / 'Data/Scripts').exists())
            self.assertFalse((final / mac.PLUGIN).exists())
            self.assertEqual(ng.exit_lift_component(str(final), port, sf)['plugins'], [mac.LIFT_PLUGIN])

    def test_animation_precheck_refuses_missing_event_declarations(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'base.zip'
            fake_zip(path, animation=False)
            self.assertEqual(ng.precheck_zip(path)['missing_core'], [
                'ScriptObject.RegisterForAnimationEvent', 'ScriptObject.UnregisterForAnimationEvent', 'ScriptObject.OnAnimationEvent'])

    def test_fold_copies_and_hash_verifies_cog_and_lift_assets_without_overwriting_core(self):
        fixture = newgame_tests.VerifyFoldTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        stage = Path(fixture.stage)
        lift_asset = stage / 'Data/meshes/lift.nif'
        cog_asset = stage / 'Data/meshes/cog.nif'
        shared_mat = stage / 'Data/materials/fo4port/v111trim01.mat'
        lift_asset.parent.mkdir(parents=True)
        shared_mat.parent.mkdir(parents=True)
        lift_asset.write_bytes(b'liftmodel')
        cog_asset.write_bytes(b'cogmodel')
        shared_mat.write_bytes(b'sharedmat')
        (stage / mac.LIFT_PLUGIN).write_bytes(b'liftplugin')
        (stage / mcd.COG_PLUGIN).write_bytes(b'cogplugin')
        plan_path = stage / 'plan.json'
        plan = json.loads(plan_path.read_text())
        plan['cog_door'] = {'plugins': [mcd.COG_PLUGIN], 'outputs': {
            mcd.COG_PLUGIN: ng.sha256(stage / mcd.COG_PLUGIN),
            'Data/meshes/cog.nif': ng.sha256(cog_asset),
            'Data/materials/fo4port/v111trim01.mat': ng.sha256(shared_mat)}}
        plan['exit_lift'] = {'plugins': [mac.LIFT_PLUGIN], 'outputs': {
            mac.LIFT_PLUGIN: ng.sha256(stage / mac.LIFT_PLUGIN),
            'Data/meshes/lift.nif': ng.sha256(lift_asset),
            'Data/materials/fo4port/v111trim01.mat': ng.sha256(shared_mat)}}
        plan_path.write_text(json.dumps(plan))
        out = Path(fixture.tmp) / 'folded'
        self.assertEqual(fixture.fold(str(out), port=fixture.port), 0)
        self.assertEqual((out / 'Data/meshes/lift.nif').read_bytes(), b'liftmodel')
        self.assertEqual((out / 'Data/meshes/cog.nif').read_bytes(), b'cogmodel')
        self.assertEqual((out / 'Data/materials/fo4port/v111trim01.mat').read_bytes(), b'sharedmat')
        self.assertIn('FO4TerrainCore.esm,Mars.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm',
                      (out / 'README.txt').read_text())
        # Conflicting shared material hash between cog and lift must refuse fold
        bad_plan = copy.deepcopy(plan)
        bad_plan['exit_lift']['outputs']['Data/materials/fo4port/v111trim01.mat'] = '0' * 64
        plan_path.write_text(json.dumps(bad_plan))
        with self.assertRaises(SystemExit): fixture.fold(str(Path(fixture.tmp) / 'bad_shared'), port=fixture.port)
        plan_path.write_text(json.dumps(plan))
        (out / 'Data/meshes/lift.nif').write_bytes(b'changed')
        self.assertTrue(any('exit lift' in x for x in ng.verify_dir(str(out), plan, fixture.port)))
        # Identical Data/ asset already in core_dir (e.g. Data/materials/fo4port/_neutral.mat) is accepted without copying
        stage_neutral = stage / 'Data/materials/fo4port/_neutral.mat'
        core_neutral = Path(fixture.core_dir) / 'Data/materials/fo4port/_neutral.mat'
        stage_neutral.write_bytes(b'neutralmat')
        core_neutral.parent.mkdir(parents=True, exist_ok=True)
        core_neutral.write_bytes(b'neutralmat')
        neutral_sha = ng.sha256(stage_neutral)
        plan['cog_door']['outputs']['Data/materials/fo4port/_neutral.mat'] = neutral_sha
        plan['exit_lift']['outputs']['Data/materials/fo4port/_neutral.mat'] = neutral_sha
        plan_path.write_text(json.dumps(plan))
        stage_copies = []
        real_copy2 = ng.shutil.copy2
        def spy_copy2(src, dst, *a, **kw):
            p = Path(src).resolve()
            if p.is_relative_to(stage.resolve()):
                stage_copies.append(p)
            return real_copy2(src, dst, *a, **kw)
        out_same = Path(fixture.tmp) / 'folded_same_core_asset'
        with patch.object(ng.shutil, 'copy2', side_effect=spy_copy2):
            self.assertEqual(fixture.fold(str(out_same), port=fixture.port), 0)
        self.assertNotIn(stage_neutral.resolve(), stage_copies)
        self.assertEqual((out_same / 'Data/materials/fo4port/_neutral.mat').read_bytes(), b'neutralmat')
        self.assertEqual(ng.verify_dir(str(out_same), plan, fixture.port), [])
        # Differing Data/ asset in core_dir is still refused
        collision = Path(fixture.core_dir) / 'Data/meshes/lift.nif'
        collision.parent.mkdir(parents=True, exist_ok=True)
        collision.write_bytes(b'preserve')
        with self.assertRaisesRegex(SystemExit, r'core set already has lift asset Data/meshes/lift\.nif'):
            fixture.fold(str(Path(fixture.tmp) / 'refused'), port=fixture.port)
        self.assertEqual(collision.read_bytes(), b'preserve')

    def test_writer_switch_is_opt_in_and_precheck_covers_animation(self):
        self.assertNotIn('--animated-exit-lift', ng.tool_options(namespace()))
        self.assertIn('--animated-exit-lift', ng.tool_options(namespace(exit_lift='production')))
        cs = read(CS)
        self.assertIn('if (animatedExitLift)', cs)
        self.assertIn('IsRefKey(e.Name, Fo4Platform)', cs)
        self.assertIn('Owned(refs[0], port.ModKey, "the exit lift")', cs)
        self.assertIn('("LiftId", (int)p.Lift)', cs)
        self.assertIn('"PlayAnimation"', read(ng.__file__))
        self.assertIn('OnAnimationEvent', ng.NATIVES[ng.SCRIPT]['ScriptObject'])


if __name__ == '__main__':
    unittest.main()
