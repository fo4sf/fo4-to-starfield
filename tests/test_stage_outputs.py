"""Incomplete source publication must stop consumers before packing or game access."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

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
                with self.assertRaisesRegex(ValueError, 'publication is pending'):
                    stages.require_ready_stage(directory)
                path.unlink()
                path.mkdir()
                with self.assertRaisesRegex(ValueError, 'publication is pending'):
                    stages.require_ready_stage(directory)
                path.rmdir()

    def test_pending_refuses_install_inventory_and_core_reads_before_side_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / stages.PENDING).write_bytes(b'torn journal')
            with patch.object(deploy, 'build_archive', side_effect=AssertionError('must not pack')):
                with self.assertRaisesRegex(ValueError, 'publication is pending'):
                    deploy.install(SimpleNamespace(staging=directory))
            with self.assertRaisesRegex(ValueError, 'publication is pending'):
                exp.install(SimpleNamespace(exp_dir=directory))
            with patch.object(exp, 'digest', side_effect=AssertionError('must not hash')):
                with self.assertRaisesRegex(ValueError, 'publication is pending'):
                    exp.source_inventory(directory, ['missing.esm'])
            with self.assertRaisesRegex(ValueError, 'publication is pending'):
                core.core_params(directory)
            with self.assertRaisesRegex(ValueError, 'publication is pending'):
                cave.cmd_stage(SimpleNamespace(core=directory))
            with self.assertRaisesRegex(ValueError, 'publication is pending'):
                cave.cmd_check(SimpleNamespace(core=directory))

    def test_deployer_isolated_cli_loads_the_guard(self):
        proc = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'scripts/deploy_starfield.py'), '--help'],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
