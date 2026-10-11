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

    def archive_builder(self, payload=b"BTDX" + bytes(12) + b"synthetic archive"):
        tool = self.data.parent / "Tools" / "Archive2" / "Archive2.exe"
        tool.parent.mkdir(parents=True)
        tool.write_bytes(b"synthetic tool; never executed")
        self.args.pack = True

        def build(command, **kwargs):
            self.assertEqual(Path(kwargs["cwd"]), self.staging / "Data")
            self.assertIn("-format=General", command)
            output = next(arg[len("-create="):] for arg in command if arg.startswith("-create="))
            Path(output).write_bytes(payload)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        return build

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

    def test_packed_install_publishes_plugins_and_archive_only(self):
        build = self.archive_builder()
        self.args.plugins = "Experiment.esm,Experiment_Mars.esm"
        (self.staging / "Experiment_Mars.esm").write_bytes(b"synthetic registration plugin")
        with patch.object(exp.subprocess, "run", side_effect=build) as process:
            exp.install(self.args)
            process.assert_called_once()
            exp.install(self.args)
            process.assert_called_once()
        self.assertFalse((self.data / "Terrain").exists())
        self.assertEqual((self.data / "Experiment - Main.ba2").read_bytes(),
                         (self.staging / "Experiment - Main.ba2").read_bytes())
        self.assertEqual((self.data / "Experiment_Mars.esm").read_bytes(), b"synthetic registration plugin")
        exp.uninstall(self.args)
        self.assert_rolled_back()

    def test_packed_archive_copy_failure_rolls_back_published_plugin(self):
        build = self.archive_builder()
        real_copy = exp.shutil.copyfile

        def copy(source, target):
            if Path(source).suffix == ".ba2":
                Path(target).write_bytes(b"partial archive")
                raise OSError("injected archive copy failure")
            return real_copy(source, target)

        with patch.object(exp.subprocess, "run", side_effect=build), \
                patch.object(exp.shutil, "copyfile", side_effect=copy):
            with self.assertRaisesRegex(SystemExit, "rolled back"):
                exp.install(self.args)
        self.assert_rolled_back()

    def test_packed_build_failure_preserves_previous_archive_and_game(self):
        build = self.archive_builder()
        archive = self.staging / "Experiment - Main.ba2"
        previous = b"previous staging archive"
        archive.write_bytes(previous)

        def fail(command, **kwargs):
            result = build(command, **kwargs)
            result.returncode = 1
            return result

        with patch.object(exp.subprocess, "run", side_effect=fail):
            with self.assertRaises(SystemExit):
                exp.install(self.args)
        self.assertEqual(archive.read_bytes(), previous)
        self.assert_rolled_back()

    def test_truncated_packed_archive_is_rejected_before_installation(self):
        build = self.archive_builder(b"BTDX")
        archive = self.staging / "Experiment - Main.ba2"
        previous = b"previous staging archive"
        archive.write_bytes(previous)
        with patch.object(exp.subprocess, "run", side_effect=build):
            with self.assertRaises(SystemExit):
                exp.install(self.args)
        self.assertEqual(archive.read_bytes(), previous)
        self.assert_rolled_back()

    def test_missing_plugin_is_rejected_before_packing(self):
        build = self.archive_builder()
        self.args.plugins = "Experiment.esm,Missing.esm"
        archive = self.staging / "Experiment - Main.ba2"
        previous = b"previous staging archive"
        archive.write_bytes(previous)
        with patch.object(exp.subprocess, "run", side_effect=build) as process:
            with self.assertRaises((OSError, SystemExit)):
                exp.install(self.args)
            process.assert_not_called()
        self.assertEqual(archive.read_bytes(), previous)
        self.assert_rolled_back()

    def test_packing_mode_change_is_not_reported_as_already_installed(self):
        exp.install(self.args)
        installed = (self.data / exp.RECORD).read_bytes()
        build = self.archive_builder()
        with patch.object(exp.subprocess, "run", side_effect=build) as process:
            with self.assertRaisesRegex(SystemExit, "mode"):
                exp.install(self.args)
            process.assert_not_called()
        self.assertEqual((self.data / exp.RECORD).read_bytes(), installed)
        exp.uninstall(self.args)
        self.assert_rolled_back()

    def changed_plugin_blocks_relaunch_after_partial_cleanup(self):
        exp.install(self.args)
        plugin = self.data / "Experiment.esm"
        plugin.write_bytes(b"owner changed plugin")
        with self.assertRaisesRegex(SystemExit, "changed since install"):
            exp.uninstall(self.args)
        self.assertEqual({path.name for path in self.data.iterdir()}, {"Experiment.esm", exp.RECORD})
        with self.assertRaisesRegex(SystemExit, "incomplete"):
            exp.install(self.args)
        self.assertEqual(plugin.read_bytes(), b"owner changed plugin")
        # Once the owner restores the recorded content, cleanup is retryable.
        plugin.write_bytes((self.staging / "Experiment.esm").read_bytes())
        exp.uninstall(self.args)
        self.assert_rolled_back()

    def test_partial_loose_uninstall_cannot_masquerade_as_installed(self):
        self.changed_plugin_blocks_relaunch_after_partial_cleanup()

    def test_partial_packed_uninstall_cannot_masquerade_as_installed(self):
        build = self.archive_builder()
        with patch.object(exp.subprocess, "run", side_effect=build) as process:
            self.changed_plugin_blocks_relaunch_after_partial_cleanup()
            process.assert_called_once()

    def test_interrupted_uninstall_is_journaled_before_plugin_changes(self):
        exp.install(self.args)
        real_write = exp.write_plugins

        def remove_activation_then_interrupt(*args, **kwargs):
            real_write(*args, **kwargs)
            raise KeyboardInterrupt("injected interrupted uninstall")

        with patch.object(exp, "write_plugins", side_effect=remove_activation_then_interrupt):
            with self.assertRaises(KeyboardInterrupt):
                exp.uninstall(self.args)
        self.assertEqual(self.plugins.read_bytes(), self.original)
        with self.assertRaisesRegex(SystemExit, "incomplete"):
            exp.install(self.args)
        exp.uninstall(self.args)
        self.assert_rolled_back()

    def test_inactive_existing_plugin_is_activated_and_restored(self):
        self.original += b"  Experiment.esm  \r\n"
        self.plugins.write_bytes(self.original)
        exp.install(self.args)
        lines = self.plugins.read_text(encoding="utf-8-sig").splitlines()
        self.assertEqual(lines.count("*Experiment.esm"), 1)
        self.assertNotIn("  Experiment.esm  ", lines)
        exp.install(self.args)
        exp.uninstall(self.args)
        self.assert_rolled_back()

    def test_activation_restoration_preserves_cr_and_missing_trailing_newline(self):
        for original in (b"# owner\r*FO4Port.esm\rExperiment.esm\r",
                         b"\xef\xbb\xbf# owner\n*FO4Port.esm\nExperiment.esm"):
            with self.subTest(original=original):
                self.original = original
                self.plugins.write_bytes(original)
                exp.install(self.args)
                expected = original.replace(b"Experiment.esm", b"*Experiment.esm")
                self.assertEqual(self.plugins.read_bytes(), expected)
                exp.uninstall(self.args)
                self.assert_rolled_back()

    def test_relaunch_rejects_an_externally_deactivated_plugin(self):
        exp.install(self.args)
        inactive = self.original + b"Experiment.esm\r\n"
        self.plugins.write_bytes(inactive)
        with self.assertRaisesRegex(SystemExit, "inactive"):
            exp.install(self.args)
        self.assertEqual(self.plugins.read_bytes(), inactive)

    def test_relaunch_rejects_a_missing_packed_archive(self):
        build = self.archive_builder()
        with patch.object(exp.subprocess, "run", side_effect=build) as process:
            exp.install(self.args)
            (self.data / "Experiment - Main.ba2").unlink()
            with self.assertRaisesRegex(SystemExit, "missing or changed"):
                exp.install(self.args)
            process.assert_called_once()

    def test_relaunch_rejects_rebuilt_staged_plugin(self):
        exp.install(self.args)
        (self.staging / "Experiment.esm").write_bytes(b"rebuilt plugin")
        with self.assertRaisesRegex(SystemExit, "source inputs changed"):
            exp.install(self.args)
        self.assertEqual((self.data / "Experiment.esm").read_bytes(), b"synthetic plugin")

    def test_relaunch_rejects_changed_packed_terrain_inputs(self):
        build = self.archive_builder()
        with patch.object(exp.subprocess, "run", side_effect=build) as process:
            exp.install(self.args)
            (self.staging / "Data" / self.terrain).write_bytes(b"changed terrain")
            with self.assertRaisesRegex(SystemExit, "source inputs changed"):
                exp.install(self.args)
            process.assert_called_once()

    def test_changed_terrain_during_packing_is_rejected_before_installation(self):
        build = self.archive_builder()

        def change_inputs(command, **kwargs):
            result = build(command, **kwargs)
            (self.staging / "Data" / self.terrain).write_bytes(b"changed while packing")
            return result

        with patch.object(exp.subprocess, "run", side_effect=change_inputs):
            with self.assertRaisesRegex(SystemExit, "changed during preparation"):
                exp.install(self.args)
        self.assert_rolled_back()

    def test_packing_refuses_omitted_root_data_files_before_building(self):
        build = self.archive_builder()
        (self.staging / "Data" / "extra.txt").write_bytes(b"synthetic root resource")
        with patch.object(exp.subprocess, "run", side_effect=build) as process:
            with self.assertRaisesRegex(SystemExit, "root"):
                exp.install(self.args)
            process.assert_not_called()
        self.assert_rolled_back()

    def test_missing_local_appdata_cannot_activate_a_relative_profile(self):
        previous = os.getcwd()
        os.chdir(self.root)
        try:
            with patch.dict(os.environ, {"LOCALAPPDATA": ""}):
                with self.assertRaisesRegex(SystemExit, "LOCALAPPDATA"):
                    exp.install(self.args)
        finally:
            os.chdir(previous)
        self.assert_rolled_back()

    def test_pre_replacement_config_conflict_finishes_rollback(self):
        real_write = exp.write_plugins
        edited = self.original + b"*OwnerAdded.esm\r\n"

        def edit_before_write(*args, **kwargs):
            self.plugins.write_bytes(edited)
            return real_write(*args, **kwargs)

        with patch.object(exp, "write_plugins", side_effect=edit_before_write):
            with self.assertRaisesRegex(SystemExit, "rolled back"):
                exp.install(self.args)
        self.assertEqual(list(self.data.iterdir()), [])
        self.assertEqual(self.plugins.read_bytes(), edited)

    def test_changed_source_during_copy_is_never_published(self):
        real_copy = exp.shutil.copyfile

        def copy(source, target):
            if Path(source).suffix == ".esm":
                Path(source).write_bytes(b"changed source while copying")
            return real_copy(source, target)

        with patch.object(exp.shutil, "copyfile", side_effect=copy):
            with self.assertRaisesRegex(SystemExit, "rolled back"):
                exp.install(self.args)
        self.assert_rolled_back()

    def test_duplicate_destinations_are_rejected_before_publication(self):
        (self.staging / "Data" / "Experiment.esm").write_bytes(b"conflicting synthetic plugin")
        with self.assertRaisesRegex(SystemExit, "duplicate"):
            exp.install(self.args)
        self.assert_rolled_back()

    def test_publication_is_recorded_before_full_installed_archive_hash(self):
        build = self.archive_builder()
        real_digest = exp.digest

        def interrupt(path):
            if Path(path) == self.data / "Experiment - Main.ba2":
                raise KeyboardInterrupt("injected interruption during installed archive hash")
            return real_digest(path)

        with patch.object(exp.subprocess, "run", side_effect=build), \
                patch.object(exp, "digest", side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                exp.install(self.args)
        record = json.loads((self.data / exp.RECORD).read_text())
        self.assertIn("Experiment - Main.ba2", record["published_files"])
        exp.uninstall(self.args)
        self.assert_rolled_back()

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
        self.assertFalse((self.data / exp.RECORD).exists(), "proven foreign publication must not trap recovery")
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
