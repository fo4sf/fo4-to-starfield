"""Actual ascent and in-vault platform/door branches with substituted natives."""
import copy
import json
import os
from pathlib import Path
import re
import struct
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
           'rideActive, rideDone, rideTransferred, exitFailures, exitUsedFallback, '
           'surfaceMovedAt, surfaceMoves, surfaceSets, asked')


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
        self.spec_calls = 0
        self.need_attr_modals = 0
        self.notifications = []
        def show():
            self.prompts += 1
            return self.button
        def show_need_attr():
            self.need_attr_modals += 1
            return 0
        self.ns = dict(
            asked=False, liftSpecConfirmed=False, exitFailures=0, TestModeGlobal=None,
            rideActive=False, rideTransferred=False,
            CogDoorId=0x126D, VaultPlugin='FO4Port.esm',
            ConsoleX=-53.7, ConsoleY=-3.7, ConsoleZ=0.53, ConsoleRadius=2.5,
            PlatformX=-77.742, PlatformY=-3.958, PlatformZ=-1.751, PlatformRadius=2.0,
            LiftId=0x1618,
            Game=SimpleNamespace(GetFormFromFile=lambda i, _: self.door if i == 0x126D else None),
            Debug=SimpleNamespace(Notification=self.notifications.append),
            ExitMessage=SimpleNamespace(Show=show),
            ExitNeedAttrMsg=SimpleNamespace(Show=show_need_attr),
            ExitFallbackMessage=SimpleNamespace(Show=lambda: 0),
            EnsureVaultInteractivesRegistered=lambda: None,
            ReadH00SuspectsOnce=lambda: None,
            StartTimer=lambda *_: None,
            OpenLiftAttributeAllocation=lambda: setattr(self, 'spec_calls', self.spec_calls + 1),
            RunSharedMapSetup=lambda: 4,
            AdvanceTo=self.stages.append,
            StartAscent=self.ascents.append,
            FallbackExitToSurface=lambda p: None,
            Surface=self.surfaces.append,
        )
        exec(compile(translated_functions(read(PSC), ('InVault', 'PromptVaultExitLift', 'Near'), 'asked, liftSpecConfirmed, exitFailures'), PSC, 'exec'), self.ns)

    def test_platform_marker_and_radius_constants(self):
        self.assertIn('Fo4PlatformMarker = 0x01B29E', read(CS))
        self.assertIn('float Property PlatformRadius = 2.0 Auto Const', read(PSC))

    def test_console_stand_and_direct_door_open_do_nothing_when_test_mode_is_off(self):
        # X1: With TestModeGlobal off, standing near the console does NOT open the door or advance to stage 30!
        self.ns['InVault'](self.player, 20)
        self.assertEqual(self.door.set_open_calls, [])
        self.assertEqual(self.stages, [])
        self.assertEqual(self.prompts, 0)
        # Even if door open_state changes to 2 while TestModeGlobal is off, InVault does not advance stage 30 without console E!
        self.door.open_state = 2
        self.player.pos = (-60.0, -3.9, 0.0)
        self.ns['InVault'](self.player, 20)
        self.assertEqual(self.stages, [])
        # On the catwalk at 000244EB's NIF root (-70.392, -2.742, -0.114): 7.45 m from platform -> ZERO prompts!
        self.player.pos = (-70.392, -2.742, -0.114)
        self.ns['InVault'](self.player, 30)
        self.assertEqual(self.prompts, 0)

    def test_lift_prompt_blocks_continue_until_special_is_confirmed_then_starts_ascent(self):
        # X3 / H00(b)-(c): Stepping onto platform at stage 30 shows 3-button ExitMessage; button 0 (Continue) shows ExitNeedAttrMsg until S.P.E.C.I.A.L. confirmed!
        self.player.pos = (-77.742, -3.958, -1.751)
        self.button = 0
        self.ns['InVault'](self.player, 30)
        self.assertEqual(self.prompts, 1)
        self.assertEqual(self.ascents, [])
        self.assertEqual(self.need_attr_modals, 1)
        self.assertEqual(self.notifications, [])
        # Button 1 routes to OpenLiftAttributeAllocation; Button 2 stays in Vault 111 (no Starfield Enhance creator on the lift!)
        self.button = 1
        self.ns['InVault'](self.player, 30)
        self.assertEqual(self.spec_calls, 1)
        self.ns['asked'] = False
        self.button = 2
        self.ns['InVault'](self.player, 30)
        self.assertEqual(self.ascents, [])
        # Once liftSpecConfirmed is True, button 0 (Continue) starts ascent once!
        self.ns['asked'] = False
        self.ns['liftSpecConfirmed'] = True
        self.button = 0
        self.ns['InVault'](self.player, 30)
        self.ns['InVault'](self.player, 30)
        self.assertEqual(self.ascents, [self.player])

    def test_test_mode_global_enables_legacy_console_stand_and_continue_shortcut(self):
        self.ns['TestModeGlobal'] = SimpleNamespace(GetValue=lambda: 1.0)
        self.ns['InVault'](self.player, 20)
        self.assertEqual(self.door.set_open_calls, [True])
        self.assertEqual(self.stages, [30])
        self.player.pos = (-77.742, -3.958, -1.751)
        self.ns['InVault'](self.player, 30)
        self.assertEqual(self.ascents, [self.player])


class AscentExecutionTests(unittest.TestCase):
    def setUp(self):
        self.now = 10.0
        self.cell = object()
        self.player = Reference(None, (-77.742, -3.958, -1.72))
        self.player.interior, self.player.cell = True, self.cell
        self.vault_anchor = Reference(None, (-60.0, 0.0, -1.0))
        self.vault_anchor.interior, self.vault_anchor.cell = True, self.cell
        self.lift = Lift(None, (-70.392, -2.742, -0.114))
        self.base = object()
        self.lift.base, self.lift.plays, self.lift.accepted = self.base, [], True
        self.lift.cell = self.cell
        self.failures, self.transfers, self.registrations, self.unregistrations = [], [], [], []
        self.map_setup_calls = 0
        def run_map_setup():
            self.map_setup_calls += 1
            return 4
        self.ns = dict(ridingLift=None, ridingCell=None, rideStartedAt=0.0, riderX=0.0, riderY=0.0, riderZ=0.0,
                       rideActive=False, rideDone=False, rideTransferred=False, exitFailures=0, exitUsedFallback=False,
                       surfaceMovedAt=0.0, surfaceMoves=0, surfaceSets=0, asked=False,
                       VaultAnchorId=0x805, AnchorX=-60.0, AnchorY=0.0, AnchorZ=-1.0,
                       PlatformX=-77.742, PlatformY=-3.958, PlatformZ=-1.751, PlatformRadius=2.0,
                       LiftId=0x1618, LiftBaseId=0x1619, LiftRise=21.6, LiftSeconds=9.8667, LiftDoneMargin=0.25, VaultPlugin='FO4Port.esm',
                       Game=SimpleNamespace(
                           GetFormFromFile=lambda i, _: self.lift if i == 0x1618 else (self.vault_anchor if i == 0x805 else self.base),
                           GetPlayer=lambda: self.player,
                       ),
                       Utility=SimpleNamespace(GetCurrentRealTime=lambda: self.now),
                       GetStage=lambda: 30,
                       StandsInVault=lambda _: True, Surface=self.transfers.append,
                       RunSharedMapSetup=run_map_setup,
                       RegisterForAnimationEvent=lambda *args: self.registrations.append(args),
                       UnregisterForAnimationEvent=lambda *args: self.unregistrations.append(args))
        text = read(PSC)
        event = re.search(r'Event OnAnimationEvent\((.*?)\)\n(.*?)EndEvent', text, re.S)
        text += '\nFunction AscentEvent(' + event[1] + ')\n' + event[2] + 'EndFunction\n'
        exec(compile(translated_functions(text, ('StartAscent', 'AscentEvent', 'AtLiftTop', 'CheckAscent', 'Near', 'FailExit', 'ReturnPlayerToVaultPlatform'), GLOBALS), PSC, 'exec'), self.ns)
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
        self.assertEqual(self.map_setup_calls, 1)
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


class VaultConsoleAndPistolFilterExecutionTests(unittest.TestCase):
    """B4 & B5: Translated-execution tests for GearDoorConsoleRef 2s open-state check/retry and VaultPistolBase filter."""

    FUNCS = (
        'EnsureVaultInteractivesRegistered',
        'ObjectReference.OnItemAdded',
        'ObjectReference.OnActivate',
        'ActivateGearDoorConsole',
    )
    VARS = (
        'itemWatchRegistered, pipboyRegistered, cogDoorRegistered, cogDoorWatchedRef, '
        'consoleRegistered, consoleWatchedRef, portConsoleRegistered, portConsoleWatchedRef, '
        'consoleOpening, pistolPickedLogged'
    )

    def setUp(self):
        self.player = Reference(None, (-53.7, -3.7, 0.53), form_id=0x00000014)
        self.player.interior = True
        self.equipped = set()
        self.player.IsEquipped = lambda item: item in self.equipped
        self.player.EquipItem = lambda item, *args: self.equipped.add(item)
        self.console_ref = Reference(None, (-53.7, -3.7, 0.53), form_id=0x04000819)
        self.pipboy_ref = Reference(None, (-53.79, -2.15, -0.52), form_id=0x0400080F)
        self.port_console = Lift(None, (-53.7, -3.7, 0.53))
        self.port_console.plays = []
        self.port_console.accepted = True
        self.door = DoorRef(open_state=3)
        self.door.blocks = []
        self.door.BlockActivation = lambda *args: self.door.blocks.append(args)
        self.vault_pistol = object()
        self.other_weapon = object()
        self.stage = 20
        self.stages = []
        self.traces = []
        self.waits = []
        self.call_order = []

        def get_form(fid, plg):
            if plg == 'FO4Port.esm':
                if fid == 0x126D:
                    return self.door
                if fid == 0x126E:
                    return self.port_console
            return None

        self.ns = dict(
            Trace=self.traces.append,
            itemWatchRegistered=False,
            pipboyRegistered=False,
            cogDoorRegistered=False,
            cogDoorWatchedRef=None,
            consoleRegistered=False,
            consoleWatchedRef=None,
            portConsoleRegistered=False,
            portConsoleWatchedRef=None,
            consoleOpening=False,
            pistolPickedLogged=False,
            VaultPistolBase=self.vault_pistol,
            VaultPistolId=0x24561C,
            PipboyCorpseRef=self.pipboy_ref,
            GearDoorConsoleRef=self.console_ref,
            CogDoorId=0x126D,
            ConsoleRefId=0x126E,
            LiftId=0,
            VaultPlugin='FO4Port.esm',
            TestModeGlobal=None,
            PipboyAcquiredGlobal=SimpleNamespace(GetValue=lambda: 1.0),
            NoPipboyMsg=SimpleNamespace(Show=lambda: 0),
            Game=SimpleNamespace(GetPlayer=lambda: self.player, GetFormFromFile=get_form),
            Utility=SimpleNamespace(Wait=self.waits.append),
            AddInventoryEventFilter=lambda f: self.call_order.append(('filter', f)),
            RegisterForRemoteEvent=lambda target, ev: self.call_order.append(('register', target, ev)),
            HandlePipboyPickup=lambda p: None,
            GetStage=lambda: self.stage,
            AdvanceTo=lambda n, by='trigger': (setattr(self, 'stage', n), self.stages.append((n, by))),
        )
        exec(compile(translated_functions(read(PSC), self.FUNCS, self.VARS), PSC, 'exec'), self.ns)

    def test_b5_inventory_filter_precedes_registration_and_accepts_only_vault_pistol_base(self):
        self.ns['EnsureVaultInteractivesRegistered']()
        self.assertEqual(self.call_order[0], ('filter', self.vault_pistol))
        self.assertEqual(self.call_order[1], ('register', self.player, 'OnItemAdded'))
        self.assertTrue(any('pistol filter added base=' in t and 'id=2381340' in t for t in self.traces), self.traces)

        # Arbitrary other weapon must NOT log pistol picked
        self.ns['OnItemAdded'](self.player, self.other_weapon, 1, None, None, 0)
        self.assertFalse(self.ns['pistolPickedLogged'])
        self.assertFalse(any(t.startswith('pistol picked ') for t in self.traces))

        # Exact VaultPistolBase logs pistol picked once
        self.ns['OnItemAdded'](self.player, self.vault_pistol, 1, None, None, 0)
        self.assertTrue(self.ns['pistolPickedLogged'])
        self.assertTrue(any(t.startswith('pistol picked ') for t in self.traces))

    def test_b4_gear_door_console_registers_own_activator_waits_2s_and_retries_if_still_closed(self):
        self.ns['EnsureVaultInteractivesRegistered']()
        self.assertIn(('register', self.console_ref, 'OnActivate'), self.call_order)
        self.assertTrue(any('console activator registered ref=' in t for t in self.traces), self.traces)

        # First press: door refuses to open (SetOpen ignored -> open_state stays 3 after 2.0 s wait)
        self.door.SetOpen = lambda val: self.door.set_open_calls.append(val)  # stays 3!
        self.ns['OnActivate'](self.console_ref, self.player)
        self.assertEqual(self.waits, [2.0])
        self.assertIn('cog door open failed state=3', self.traces)
        self.assertEqual(self.stages, [])
        self.assertEqual(self.stage, 20)

        # Second press: console remains active, door opens (open_state=2 opening) -> advances to stage 30 by=vault_console!
        self.door.SetOpen = lambda val: (self.door.set_open_calls.append(val), setattr(self.door, 'open_state', 2))
        self.ns['OnActivate'](self.console_ref, self.player)
        self.assertEqual(self.waits, [2.0, 2.0])
        self.assertEqual(self.stages, [(30, 'vault_console')])
        self.assertEqual(self.stage, 30)


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


def _sec(tag, payload, leaf=True):
    flags = 0x40000000 if leaf else 0
    return struct.pack('>I', flags | (8 + len(payload))) + tag.encode('latin-1') + payload


def _synthetic_tag0(layer, motion_type=1, shape_type='hknpConvexShape'):
    tst1 = f'\0hknpBodyCinfo\0{shape_type}'.encode('latin-1')
    fst1 = b'\0collisionFilterInfo\0motionType'
    tna1 = bytes([3, 1, 0, 2, 0])
    # Type 1 (hknpBodyCinfo): parent=0, opt=0x28 (size+align, fields), size=8, align=4, 2 fields:
    #   field 1 ('collisionFilterInfo') flags=0 offset=0 type=0, field 2 ('motionType') flags=0 offset=4 type=0
    tbdy = bytes([1, 0, 0x28, 8, 4, 2, 1, 0, 0, 0, 2, 0, 4, 0, 0])
    type_sec = _sec('TYPE', _sec('TST1', tst1) + _sec('TNA1', tna1) + _sec('FST1', fst1) + _sec('TBDY', tbdy), leaf=False)
    data = struct.pack('<IB3x', layer, motion_type)
    items = struct.pack('<III', 1, 0, 1) + struct.pack('<III', 2, 8, 1)
    indx_sec = _sec('INDX', _sec('ITEM', items) + _sec('PTCH', b''), leaf=False)
    return _sec('TAG0', _sec('SDKV', b'20190200') + _sec('DATA', data) + type_sec + indx_sec, leaf=False)


class BundleCollisionLayerTests(unittest.TestCase):
    """X5 offline collision audit: lists each body with its Havok collision layer on synthetic and local bundle NIFs."""

    def test_inspect_nif_collision_layers_lists_each_body_and_layer(self):
        from fo4sf import nif
        f = nif.NifFile(endian=1, user_version=12, bs_version=173, author=b'\0', unknown_int=0, export_script=b'\0', sf_data=b'\x7a\0')
        identity = (1, 0, 0, 0, 1, 0, 0, 0, 1)
        pending = {}

        def add_node(name, blob=None):
            idx = f.add_block('NiNode', b'')
            col = -1
            if blob is not None:
                col = f.add_block('bhkNPCollisionObject', struct.pack('<iHiI', idx, 0x80, len(f.blocks) + 1, 0))
                f.add_block('bhkPhysicsSystem', struct.pack('<I', len(blob)) + blob)
            pending[idx] = [f.string_index(name.encode('utf-8')), [], (0, 0, 0), identity, 1.0, col, []]
            return idx

        root = add_node('TestRoot')
        gate = add_node('V111GearRoomGate01', _synthetic_tag0(1, motion_type=2))
        lift_gate = add_node('b_Gate01')
        lift_col = add_node('b_Gate01_col_1', _synthetic_tag0(2, motion_type=1))
        cog = add_node('GearDoor', _synthetic_tag0(2, motion_type=1))
        pending[lift_gate][-1].append(lift_col)
        pending[root][-1].extend([gate, lift_gate, cog])
        for idx, (nm, ex, t, r, sc, col, ch) in pending.items():
            f.blocks[idx] = (struct.pack('<iI', nm, len(ex))
                             + struct.pack('<iI3f9ffiI', -1, 0xE, *t, *r, sc, col, len(ch))
                             + struct.pack(f'<{len(ch)}i', *ch))
        f.footer = struct.pack('<II', 1, root)
        rows = mac.inspect_nif_collision_layers(nif.serialize(f))
        self.assertEqual([(r['bone'], r['layer'], r['layer_name']) for r in rows], [
            ('V111GearRoomGate01', 1, 'L_STATIC'),
            ('b_Gate01', 2, 'L_ANIMSTATIC'),
            ('GearDoor', 2, 'L_ANIMSTATIC'),
        ])

    def _check_local_collision_bodies(self, starfield_dir, env_map):
        checked = 0
        port_ba2 = Path(starfield_dir) / 'Data' / 'FO4Port - Main.ba2'
        if port_ba2.is_file():
            from fo4sf import ba2
            archive = ba2.Ba2(str(port_ba2))
            hit = next((n for n in archive.names if n.lower().endswith('v111gearroomgate01.nif')), None)
            self.assertIsNotNone(hit)
            gate_rows = mac.inspect_nif_collision_layers(archive.read(hit))
            static_rows = [r for r in gate_rows if r['layer_name'] == 'L_STATIC']
            self.assertEqual(len(static_rows), 4)
            self.assertTrue(all('hknpConvexShape' in r['shapes'] for r in static_rows))
            checked += 1
        for env_var, want_count in (('FO4SF_EXIT_LIFT_NIF', 37), ('FO4SF_COG_DOOR_NIF', 26)):
            nif_path = env_map.get(env_var)
            if nif_path and Path(nif_path).is_file():
                rows = mac.inspect_nif_collision_layers(Path(nif_path).read_bytes())
                self.assertEqual(len(rows), want_count)
                self.assertTrue(all(r['layer_name'] == 'L_ANIMSTATIC' for r in rows))
                checked += 1
        if checked == 0:
            self.skipTest(
                'FO4Port - Main.ba2 and FO4SF_EXIT_LIFT_NIF / FO4SF_COG_DOOR_NIF are not present in this environment'
            )

    def test_local_port_and_bundle_collision_bodies_when_present(self):
        self._check_local_collision_bodies(mac.STARFIELD, os.environ)

    def test_b14_r12_collision_check_skips_visibly_when_game_and_stage_files_absent(self):
        with self.assertRaises(unittest.SkipTest) as ctx:
            self._check_local_collision_bodies('__nonexistent_starfield_dir__', {})
        self.assertIn('FO4Port - Main.ba2', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
