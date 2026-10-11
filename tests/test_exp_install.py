"""Experiment deployment failures use synthetic files, never a live game install."""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "game"))
import exp_install as exp  # noqa: E402


class ExperimentRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.staging = self.root / "staging"
        self.data = self.root / "game" / "Data"
        self.local = self.root / "local"
        self.terrain = Path("Terrain") / "nested" / "World.btd"
        self.data.mkdir(parents=True)
        (self.staging / "Data" / self.terrain.parent).mkdir(parents=True)
        (self.staging / "Experiment.esm").write_bytes(b"synthetic plugin")
        (self.staging / "Data" / self.terrain).write_bytes(b"synthetic terrain")
        (self.local / "Starfield").mkdir(parents=True)
        self.plugins = self.local / "Starfield" / "Plugins.txt"
        self.original = b"\xef\xbb\xbf# keep this comment\r\n*FO4Port.esm\r\n"
        self.plugins.write_bytes(self.original)
        environment = patch.dict(os.environ, {"LOCALAPPDATA": str(self.local)})
        environment.start()
        self.addCleanup(environment.stop)
        self.args = SimpleNamespace(starfield=str(self.data.parent), exp_dir=str(self.staging), plugins="")

    def assert_rolled_back(self):
        self.assertEqual(list(self.data.iterdir()), [])
        self.assertEqual(self.plugins.read_bytes(), self.original)

    def test_successful_install_is_idempotent_and_uninstall_preserves_existing_files(self):
        existing = self.data / "Owner.txt"
        existing.write_bytes(b"owner file")
        exp.install(self.args)
        record = self.data / exp.RECORD
        installed = record.read_bytes()
        self.assertTrue(json.loads(installed)["complete"])
        self.assertEqual((self.data / "Experiment.esm").read_bytes(), b"synthetic plugin")
        self.assertEqual((self.data / self.terrain).read_bytes(), b"synthetic terrain")
        self.assertEqual(self.plugins.read_bytes(), self.original + b"*Experiment.esm\r\n")
        exp.install(self.args)
        self.assertEqual(record.read_bytes(), installed)
        exp.uninstall(self.args)
        self.assertEqual(list(self.data.iterdir()), [existing])
        self.assertEqual(existing.read_bytes(), b"owner file")
        self.assertEqual(self.plugins.read_bytes(), self.original)

    def test_partial_second_copy_rolls_back_files_and_directories(self):
        real_copy = exp.shutil.copyfile

        def copy(source, target):
            if Path(source).suffix == ".btd":
                Path(target).write_bytes(b"partial copy")
                raise OSError("injected terrain copy failure")
            return real_copy(source, target)

        with patch.object(exp.shutil, "copyfile", side_effect=copy):
            with self.assertRaises((OSError, SystemExit)):
                exp.install(self.args)
        self.assert_rolled_back()

    def test_missing_source_is_rejected_before_any_publication(self):
        self.args.plugins = "Experiment.esm,Missing.esm"
        with self.assertRaises((OSError, SystemExit)):
            exp.install(self.args)
        self.assert_rolled_back()

    def test_failure_after_activation_restores_exact_plugin_bytes(self):
        real_write = exp.write_plugins

        def activate_then_fail(*args, **kwargs):
            real_write(*args, **kwargs)
            raise OSError("injected failure after activation")

        with patch.object(exp, "write_plugins", side_effect=activate_then_fail):
            with self.assertRaises((OSError, SystemExit)):
                exp.install(self.args)
        self.assert_rolled_back()

    def test_final_record_failure_rolls_back_activation_and_files(self):
        real_write = exp.deployment.write_manifest

        def write(path, record):
            if record["complete"]:
                raise OSError("injected final record failure")
            return real_write(path, record)

        with patch.object(exp.deployment, "write_manifest", side_effect=write):
            with self.assertRaisesRegex(SystemExit, "rolled back"):
                exp.install(self.args)
        self.assert_rolled_back()

    def test_rollback_removes_activation_when_no_plugins_file_existed(self):
        self.plugins.unlink()
        self.plugins.parent.rmdir()
        real_write = exp.write_plugins

        def activate_then_fail(*args, **kwargs):
            real_write(*args, **kwargs)
            raise OSError("injected failure after first activation")

        with patch.object(exp, "write_plugins", side_effect=activate_then_fail):
            with self.assertRaisesRegex(SystemExit, "rolled back"):
                exp.install(self.args)
        self.assertEqual(list(self.data.iterdir()), [])
        self.assertFalse(self.plugins.exists())

    def test_interrupted_activation_has_a_durable_uninstall_record(self):
        real_write = exp.write_plugins

        def activate_then_interrupt(*args, **kwargs):
            real_write(*args, **kwargs)
            raise KeyboardInterrupt("injected interruption")

        with patch.object(exp, "write_plugins", side_effect=activate_then_interrupt):
            with self.assertRaises(KeyboardInterrupt):
                exp.install(self.args)
        record = self.data / exp.RECORD
        self.assertTrue(record.exists(), "interruption must not strand untracked files")
        self.assertFalse(json.loads(record.read_text())["complete"])
        with self.assertRaisesRegex(SystemExit, "incomplete"):
            exp.install(self.args)
        exp.uninstall(self.args)
        self.assert_rolled_back()

    def test_failed_cleanup_retains_a_retryable_record(self):
        real_remove = exp.os.remove
        plugin = self.data / "Experiment.esm"

        def remove(path):
            if Path(path) == plugin:
                raise PermissionError("injected locked plugin")
            return real_remove(path)

        with patch.object(exp, "write_plugins", side_effect=OSError("activation failed")), \
                patch.object(exp.os, "remove", side_effect=remove):
            with self.assertRaises((OSError, SystemExit)):
                exp.install(self.args)
        record = self.data / exp.RECORD
        self.assertTrue(record.exists(), "failed rollback must retain cleanup ownership")
        self.assertEqual(list(json.loads(record.read_text())["files"]), ["Experiment.esm"])
        exp.uninstall(self.args)
        self.assert_rolled_back()

    def test_plugin_edit_during_copy_is_preserved(self):
        real_copy = exp.shutil.copyfile
        edited = self.original + b"*OwnerAdded.esm\r\n"

        def copy(source, target):
            result = real_copy(source, target)
            self.plugins.write_bytes(edited)
            return result

        with patch.object(exp.shutil, "copyfile", side_effect=copy):
            with self.assertRaisesRegex(SystemExit, "changed"):
                exp.install(self.args)
        self.assertEqual(list(self.data.iterdir()), [])
        self.assertEqual(self.plugins.read_bytes(), edited)

    def test_destination_race_never_claims_or_deletes_the_other_file(self):
        real_copy = exp.shutil.copyfile
        target = self.data / self.terrain
        # Identical bytes do not establish that this installer published a file.
        foreign = (self.staging / "Data" / self.terrain).read_bytes()

        def copy(source, destination):
            if Path(source).suffix == ".btd":
                target.write_bytes(foreign)
            return real_copy(source, destination)

        with patch.object(exp.shutil, "copyfile", side_effect=copy):
            with self.assertRaises(SystemExit):
                exp.install(self.args)
        self.assertEqual(target.read_bytes(), foreign)
        self.assertEqual(self.plugins.read_bytes(), self.original)
        with self.assertRaisesRegex(SystemExit, "not confirmed"):
            exp.uninstall(self.args)
        self.assertEqual(target.read_bytes(), foreign)

    def test_recovery_record_cannot_delete_outside_data(self):
        outside = self.data.parent / "Owner.txt"
        outside.write_bytes(b"owner file")
        record = self.data / exp.RECORD
        record.write_text(json.dumps({"files": {"../Owner.txt": exp.digest(outside)},
                                     "dirs": [], "plugins_added": []}))
        with self.assertRaisesRegex(SystemExit, "outside Data"):
            exp.uninstall(self.args)
        self.assertEqual(outside.read_bytes(), b"owner file")
        self.assertTrue(record.exists())


if __name__ == "__main__":
    unittest.main()
