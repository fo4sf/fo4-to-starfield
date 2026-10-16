"""Incomplete source publication must stop consumers before packing or game access."""
import os
from pathlib import Path
import json
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'scripts/game'), str(ROOT / 'scripts/terrain'), str(ROOT / 'src')]
sys.path.insert(0, str(ROOT / 'scripts/slice'))
import stage_outputs as stages
import deploy_starfield as deploy
import exp_install as exp
import make_core64c as core
import make_cave_core64c as cave


class StageOutputTests(unittest.TestCase):
    def test_legacy_stage_without_marker_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            stages.require_ready_stage(directory)

    def test_pending_or_lease_path_refuses_even_malformed_or_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in (stages.PENDING, stages.LEASE):
                path = Path(directory) / name
                path.write_bytes(b'incomplete JSON is not readiness')
                with self.assertRaisesRegex(stages.PendingPublication, 'publication is pending'):
                    stages.require_ready_stage(directory)
                path.unlink()
                path.mkdir()
                with self.assertRaisesRegex(stages.PendingPublication, 'publication is pending'):
                    stages.require_ready_stage(directory)
                path.rmdir()

    def test_pending_refuses_install_inventory_and_core_reads_before_side_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / stages.PENDING).write_bytes(b'torn journal')
            with patch.object(deploy, 'build_archive', side_effect=AssertionError('must not pack')):
                with self.assertRaisesRegex(stages.PendingPublication, 'publication is pending'):
                    deploy.install(SimpleNamespace(staging=directory))
            with self.assertRaisesRegex(stages.PendingPublication, 'publication is pending'):
                exp.install(SimpleNamespace(exp_dir=directory))
            with patch.object(exp, 'digest', side_effect=AssertionError('must not hash')):
                with self.assertRaisesRegex(stages.PendingPublication, 'publication is pending'):
                    exp.source_inventory(directory, ['missing.esm'])
            with self.assertRaisesRegex(stages.PendingPublication, 'publication is pending'):
                core.core_params(directory)
            with self.assertRaisesRegex(stages.PendingPublication, 'publication is pending'):
                cave.cmd_stage(SimpleNamespace(core=directory))
            with self.assertRaisesRegex(stages.PendingPublication, 'publication is pending'):
                cave.cmd_check(SimpleNamespace(core=directory))

    def test_deployer_isolated_cli_loads_the_guard(self):
        proc = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'scripts/deploy_starfield.py'), '--help'],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_pending_publication_checkpoints_runner_stop_before_any_game_action(self):
        from test_testqueue import FakeControls, args, make_queue, tq
        for marker in (stages.PENDING, stages.LEASE):
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as directory:
                stage, queue = (Path(directory) / name for name in ('stage', 'queue'))
                stage.mkdir()
                queue.mkdir()
                pending = stage / marker
                pending.write_bytes(b'preserve this unresolved publication')
                make_queue(str(queue), n=1)
                control = FakeControls()
                control.pid = None
                step = Mock(side_effect=AssertionError('must not run a game step'))
                runner = tq.Runner(str(queue), args(), ctl=control, step=step)
                runner.q['experiment_identity'] = {'exp_dir': str(stage), 'plugins': ['Synthetic.esm'], 'inputs': {}}
                runner.pinned_ok = Mock(return_value=True)
                runner._ps = Mock(side_effect=AssertionError('must not launch or send input'))
                with patch.object(tq, 'planned_on_other_code', return_value=None), \
                     patch.object(exp, 'digest', side_effect=AssertionError('must not hash an incomplete stage')):
                    try:
                        result = runner.run()
                    except ValueError as error:
                        state = json.loads((queue / 'state.json').read_text(encoding='utf-8'))
                        self.fail(f'publication error escaped: {error}; checkpoint={state["status"]}')
                state = json.loads((queue / 'state.json').read_text(encoding='utf-8'))
                self.assertEqual(result, 3)
                self.assertTrue(state['status'].startswith('stopped:'), state)
                self.assertEqual(state['done'], {})
                self.assertIn('publication is pending', (queue / 'run.log').read_text(encoding='utf-8'))
                self.assertEqual(pending.read_bytes(), b'preserve this unresolved publication')
                runner._ps.assert_not_called()
                step.assert_not_called()
