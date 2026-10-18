"""Synthetic experiment receipt retention, without a live installation."""
import base64
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_exp_install as fixtures
import experiment_receipts as history

exp = fixtures.exp


class ExperimentReceiptTests(unittest.TestCase):
    archive_builder = fixtures.ExperimentRecoveryTests.archive_builder

    def setUp(self):
        fixtures.ExperimentRecoveryTests.setUp(self)
        self.history = self.root / "private-receipts"
        env = patch.dict("os.environ", {"FO4SF_EXPERIMENT_RECEIPTS": str(self.history)})
        env.start()
        self.addCleanup(env.stop)

    def receipts(self):
        return [json.loads(gzip.decompress(p.read_bytes()))
                for p in self.history.glob("*.json.gz")]

    def test_isolated_runner_commands_import_with_empty_game(self):
        for command in ("active", "order"):
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, "-I", "-B", exp.__file__, command,
                     "--starfield", self.args.starfield],
                    cwd=self.root, capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("nothing installed", result.stdout)
        self.assertFalse(self.history.exists())
        self.assertEqual(self.plugins.read_bytes(), self.original)

    def test_uninstall_retains_install_identities_outside_game_and_stage(self):
        exp.install(self.args)
        rec = json.loads((self.data / exp.RECORD).read_bytes())
        exp.uninstall(self.args)
        kept = self.receipts()
        self.assertEqual(len(kept), 1)
        for key in ("files", "source_inputs", "plugins", "plugins_activated", "exp_dir"):
            self.assertEqual(kept[0][key], rec[key])
        self.assertTrue(kept[0]["complete"])
        self.assertTrue(kept[0]["cleanup_pending"])
        self.assertEqual(list(self.data.iterdir()), [])
        self.assertEqual(self.plugins.read_bytes(), self.original)

    def test_packed_archive_identity_survives_pack_temp_and_uninstall(self):
        with patch.object(exp.subprocess, "run", side_effect=self.archive_builder()):
            exp.install(self.args)
        name = "Experiment - Main.ba2"
        expected = hashlib.sha256((self.data / name).read_bytes()).hexdigest()
        exp.uninstall(self.args)
        kept = self.receipts()
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["files"][name], expected)
        self.assertIn(name, kept[0]["published_files"])
        self.assertFalse((self.staging / name).exists())
        self.assertFalse((self.data / name).exists())

    def test_preservation_failure_leaves_files_configuration_and_recovery(self):
        exp.install(self.args)
        files = {p: p.read_bytes() for p in self.data.rglob('*') if p.is_file() and p.name != exp.RECORD}
        plugins = self.plugins.read_bytes()
        with patch.object(exp, "preserve_receipt", side_effect=OSError("private volume unavailable")):
            with self.assertRaisesRegex(SystemExit, "private volume unavailable"):
                exp.uninstall(self.args)
        self.assertEqual({p: p.read_bytes() for p in files}, files)
        self.assertEqual(self.plugins.read_bytes(), plugins)
        self.assertTrue(json.loads((self.data / exp.RECORD).read_bytes())["cleanup_pending"])
        exp.uninstall(self.args)
        self.assertEqual(len(self.receipts()), 1)

    def fail_final_install_write(self, mutation=None):
        """Fail after publication/activation, retaining the last durable journal."""
        write = exp.deployment.write_manifest
        def fail(path, record):
            if record.get("complete"):
                self.before_rollback = Path(path).read_bytes()
                if mutation:
                    mutation()
                raise OSError("final record write failed")
            return write(path, record)
        return patch.object(exp.deployment, "write_manifest", side_effect=fail)

    def assert_original_checkpoint(self):
        rec = json.loads((self.data / exp.RECORD).read_bytes())
        proof = rec.pop("rollback_completed")
        raw = base64.b64decode(proof["original_receipt_b64"], validate=True)
        self.assertEqual(raw, self.before_rollback)
        self.assertEqual(proof["original_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(rec, json.loads(self.before_rollback))

    def rollback_with_history_outage(self):
        with self.fail_final_install_write(), patch.object(
                exp, "preserve_receipt", side_effect=OSError("history volume full")):
            with self.assertRaisesRegex(SystemExit, "was rolled back.*run uninstall.*runner remains blocked"):
                exp.install(self.args)
        self.assert_original_checkpoint()

    def test_failed_install_rolls_back_when_history_full_and_retains_full_receipt(self):
        with self.fail_final_install_write(), patch.object(
                exp, "preserve_receipt", side_effect=OSError("history volume full")):
            with self.assertRaisesRegex(SystemExit, "was rolled back.*preservation pending"):
                exp.install(self.args)
        record = self.data / exp.RECORD
        self.assert_original_checkpoint()
        self.assertEqual(set(json.loads(record.read_bytes())["files"]),
                         {"Experiment.esm", str(self.terrain)})
        self.assertFalse(json.loads(record.read_bytes())["complete"])
        self.assertEqual(self.plugins.read_bytes(), self.original)
        self.assertEqual(list(self.data.rglob("*")), [record])
        self.assertEqual(self.receipts(), [])
        exp.uninstall(self.args)
        self.assertEqual(set(self.receipts()[0]["files"]),
                         {"Experiment.esm", str(self.terrain)})
        self.assertEqual(list(self.data.iterdir()), [])

    def test_failed_install_with_history_failure_preserves_changed_file(self):
        plugin = self.data / "Experiment.esm"
        def edit():
            plugin.write_bytes(b"owner changed plugin")
        with self.fail_final_install_write(edit), patch.object(
                exp, "preserve_receipt", side_effect=OSError("history volume full")):
            with self.assertRaisesRegex(SystemExit, "rollback incomplete.*file changed"):
                exp.install(self.args)
        self.assertEqual(plugin.read_bytes(), b"owner changed plugin")
        self.assertEqual(self.plugins.read_bytes(), self.original)
        self.assertFalse((self.data / self.terrain).exists())
        self.assertEqual((self.data / exp.RECORD).read_bytes(), self.before_rollback)
        plugin.write_bytes((self.staging / "Experiment.esm").read_bytes())
        exp.uninstall(self.args)
        self.assertEqual(len(self.receipts()), 1)
        self.assertEqual(list(self.data.iterdir()), [])

    def test_completed_rollback_retry_preserves_later_configuration_edits(self):
        self.rollback_with_history_outage()
        edited = self.original + b"*OwnerAddedLater.esm\r\n"
        self.plugins.write_bytes(edited)
        exp.uninstall(self.args)
        self.assertEqual(self.plugins.read_bytes(), edited)
        self.assertEqual(list(self.data.iterdir()), [])
        raw = base64.b64decode(self.receipts()[0]["rollback_completed"]["original_receipt_b64"], validate=True)
        self.assertEqual(raw, self.before_rollback)
        # Finishing the receipt no longer traps the next installation.
        exp.install(self.args)
        exp.uninstall(self.args)
        self.assertEqual(self.plugins.read_bytes(), edited)

    def test_completed_rollback_retry_preserves_recreated_files_even_if_identical(self):
        plugin = self.data / "Experiment.esm"
        for payload in (b"owner's replacement", (self.staging / "Experiment.esm").read_bytes()):
            with self.subTest(payload=payload):
                self.rollback_with_history_outage()
                plugin.write_bytes(payload)
                exp.uninstall(self.args)
                self.assertEqual(plugin.read_bytes(), payload)
                self.assertFalse((self.data / exp.RECORD).exists())
                plugin.unlink()  # This fixture's recreated file only.

    def test_completed_rollback_waits_for_history_without_rewriting_checkpoint(self):
        self.rollback_with_history_outage()
        record = self.data / exp.RECORD
        before = record.read_bytes()
        edited = self.original + b"# edited after rollback\r\n"
        self.plugins.write_bytes(edited)
        with patch.object(exp, "preserve_receipt", side_effect=OSError("still unavailable")):
            with self.assertRaisesRegex(SystemExit, "still unavailable"):
                exp.uninstall(self.args)
        self.assertEqual(record.read_bytes(), before)
        self.assertEqual(self.plugins.read_bytes(), edited)
        exp.uninstall(self.args)
        self.assertEqual(self.plugins.read_bytes(), edited)

    def test_completed_checkpoint_still_blocks_runner_until_retired(self):
        self.rollback_with_history_outage()
        # A later owner action may reactivate the same plugin. That does not
        # complete recovery or make this old experiment safe to launch.
        self.plugins.write_bytes(self.original + b"*Experiment.esm\r\n")
        for command, expected in (("active", 8), ("order", 6)):
            with self.subTest(command=command):
                result = subprocess.run([sys.executable, "-I", "-B", exp.__file__, command,
                                         "--starfield", self.args.starfield], cwd=self.root,
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                self.assertIn("incomplete", result.stdout + result.stderr)

    def test_failed_checkpoint_removal_can_retry_without_replaying_cleanup(self):
        self.rollback_with_history_outage()
        record = self.data / exp.RECORD
        before = record.read_bytes()
        with patch.object(exp.os, "remove", side_effect=OSError("receipt in use")):
            with self.assertRaisesRegex(SystemExit, "receipt in use"):
                exp.uninstall(self.args)
        self.assertEqual(record.read_bytes(), before)
        plugin = self.data / "Experiment.esm"
        plugin.write_bytes(b"later owner file")
        exp.uninstall(self.args)
        self.assertEqual(plugin.read_bytes(), b"later owner file")
        self.assertFalse(record.exists())

    def test_completion_checkpoint_corruption_blocks_retirement(self):
        self.rollback_with_history_outage()
        record = self.data / exp.RECORD
        good = json.loads(record.read_bytes())
        mutations = [
            lambda r: r.update(files={}),
            lambda r: r.update(complete=True),
            lambda r: r.update(rollback_completed=None),
            lambda r: r["rollback_completed"].update(schema=True),
            lambda r: r["rollback_completed"].update(original_sha256="0" * 64),
            lambda r: r["rollback_completed"].update(original_receipt_b64="not base64!"),
        ]
        for i, mutation in enumerate(mutations):
            with self.subTest(case=i):
                changed = copy.deepcopy(good)
                mutation(changed)
                raw = json.dumps(changed).encode()
                record.write_bytes(raw)
                with self.assertRaisesRegex(SystemExit, "invalid rollback completion checkpoint"):
                    exp.uninstall(self.args)
                self.assertEqual(record.read_bytes(), raw)
                self.assertEqual(self.plugins.read_bytes(), self.original)
                self.assertEqual(self.receipts(), [])

    def test_checkpoint_write_failure_keeps_original_receipt_and_recovery_instructions(self):
        real = exp.deployment.atomic_write_bytes
        def fail(path, content, prefix, **kwargs):
            if prefix == ".fo4sfexp-rollback-":
                raise OSError("completion volume full")
            return real(path, content, prefix, **kwargs)
        with self.fail_final_install_write(), patch.object(exp.deployment, "atomic_write_bytes", side_effect=fail), \
                patch.object(exp, "preserve_receipt", side_effect=OSError("history volume full")):
            with self.assertRaisesRegex(SystemExit, "was rolled back.*checkpoint unavailable.*leave Plugins.txt"):
                exp.install(self.args)
        self.assertEqual((self.data / exp.RECORD).read_bytes(), self.before_rollback)
        self.assertEqual(self.plugins.read_bytes(), self.original)
        self.assertFalse((self.data / "Experiment.esm").exists())
        exp.uninstall(self.args)
        self.assertEqual(list(self.data.iterdir()), [])

    def test_checkpoint_publication_preserves_a_concurrent_receipt_edit(self):
        real = exp.deployment.atomic_write_bytes
        changed = b'{"concurrent": "receipt edit"}'
        def edit(path, content, prefix, **kwargs):
            if prefix == ".fo4sfexp-rollback-":
                Path(path).write_bytes(changed)
            return real(path, content, prefix, **kwargs)
        with self.fail_final_install_write(), patch.object(exp.deployment, "atomic_write_bytes", side_effect=edit), \
                patch.object(exp, "preserve_receipt", side_effect=OSError("history volume full")):
            with self.assertRaisesRegex(SystemExit, "was rolled back.*checkpoint unavailable"):
                exp.install(self.args)
        self.assertEqual((self.data / exp.RECORD).read_bytes(), changed)
        self.assertEqual(self.plugins.read_bytes(), self.original)

    def test_checkpoint_retirement_preserves_a_concurrent_receipt_edit(self):
        self.rollback_with_history_outage()
        record = self.data / exp.RECORD
        original = exp.preserve_receipt
        changed = b'{"concurrent": "receipt edit"}'
        def edit(path):
            result = original(path)
            record.write_bytes(changed)
            return result
        with patch.object(exp, "preserve_receipt", side_effect=edit):
            with self.assertRaisesRegex(SystemExit, "completion retirement refused"):
                exp.uninstall(self.args)
        self.assertEqual(record.read_bytes(), changed)
        self.assertEqual(self.plugins.read_bytes(), self.original)

    def test_failed_install_with_history_failure_preserves_concurrent_config(self):
        edited = b"# owner edit\r\n*Other.esm\r\n"
        with self.fail_final_install_write(lambda: self.plugins.write_bytes(edited)), patch.object(
                exp, "preserve_receipt", side_effect=OSError("history volume full")):
            with self.assertRaisesRegex(SystemExit, "rollback incomplete"):
                exp.install(self.args)
        self.assertEqual(self.plugins.read_bytes(), edited)
        record = self.data / exp.RECORD
        self.assertEqual(record.read_bytes(), self.before_rollback)
        self.assertEqual(list(self.data.rglob("*")), [record])

    def test_failed_install_will_not_rollback_after_receipt_changes(self):
        replacement = b'{"concurrent":"receipt edit"}'
        def fail_history(path):
            Path(path).write_bytes(replacement)
            raise OSError("history volume full")
        with self.fail_final_install_write(), patch.object(exp, "preserve_receipt", side_effect=fail_history):
            with self.assertRaisesRegex(SystemExit, "rollback incomplete.*receipt changed"):
                exp.install(self.args)
        self.assertEqual((self.data / exp.RECORD).read_bytes(), replacement)
        self.assertTrue((self.data / "Experiment.esm").exists())
        self.assertTrue((self.data / self.terrain).exists())
        self.assertIn(b"*Experiment.esm", self.plugins.read_bytes())

    def test_failed_publication_journal_write_keeps_evidence_while_undoing_known_copies(self):
        record = self.data / exp.RECORD
        write = exp.deployment.write_manifest
        def fail(path, state):
            if len(state.get("published_files", [])) == 2:
                self.before_rollback = Path(path).read_bytes()
                raise OSError("publication journal write failed")
            return write(path, state)
        with patch.object(exp.deployment, "write_manifest", side_effect=fail), patch.object(
                exp, "preserve_receipt", side_effect=OSError("history volume full")):
            with self.assertRaisesRegex(SystemExit, "was rolled back.*preservation pending"):
                exp.install(self.args)
        self.assert_original_checkpoint()
        self.assertEqual(len(json.loads(record.read_bytes())["files"]), 2)
        self.assertEqual(len(json.loads(record.read_bytes())["published_files"]), 1)
        self.assertEqual(list(self.data.rglob("*")), [record])
        self.assertEqual(self.plugins.read_bytes(), self.original)
        exp.uninstall(self.args)
        self.assertEqual(len(self.receipts()[0]["files"]), 2)
        self.assertEqual(list(self.data.iterdir()), [])

    def test_existing_corrupt_history_refuses_cleanup_without_overwrite(self):
        exp.install(self.args)
        record = self.data / exp.RECORD
        data = json.loads(record.read_bytes())
        data["cleanup_pending"] = True
        exp.deployment.write_manifest(str(record), data)
        kept = history.preserve_receipt(record)
        kept.write_bytes(b"damaged snapshot")
        plugins = self.plugins.read_bytes()
        with self.assertRaises(SystemExit):
            exp.uninstall(self.args)
        self.assertEqual(kept.read_bytes(), b"damaged snapshot")
        self.assertTrue((self.data / "Experiment.esm").exists())
        self.assertEqual(self.plugins.read_bytes(), plugins)

    def test_partial_cleanup_preserves_full_then_reduced_inventory(self):
        exp.install(self.args)
        changed = self.data / "Experiment.esm"
        original = changed.read_bytes()
        changed.write_bytes(b"owner edit")
        with self.assertRaisesRegex(SystemExit, "file changed"):
            exp.uninstall(self.args)
        self.assertEqual(set(self.receipts()[0]["files"]), {"Experiment.esm", str(self.terrain)})
        changed.write_bytes(original)
        exp.uninstall(self.args)
        self.assertEqual(sorted(len(r["files"]) for r in self.receipts()), [1, 2])
        self.assertFalse((self.data / exp.RECORD).exists())

    def test_truncated_snapshot_reports_incomplete_without_cleanup(self):
        exp.install(self.args)
        record = self.data / exp.RECORD
        data = json.loads(record.read_bytes())
        data["cleanup_pending"] = True
        exp.deployment.write_manifest(str(record), data)
        kept = history.preserve_receipt(record)
        damaged = kept.read_bytes()[:-5]
        kept.write_bytes(damaged)
        with self.assertRaisesRegex(SystemExit, "incomplete or corrupt"):
            exp.uninstall(self.args)
        self.assertEqual(kept.read_bytes(), damaged)
        self.assertTrue((self.data / "Experiment.esm").exists())

    def test_repeated_snapshot_is_verified_not_overwritten(self):
        exp.install(self.args)
        record = self.data / exp.RECORD
        raw = record.read_bytes()
        first = history.preserve_receipt(record)
        first_bytes, first_mtime = first.read_bytes(), first.stat().st_mtime_ns
        again = history.preserve_receipt(record)
        self.assertEqual(first, again)
        self.assertEqual(first.read_bytes(), first_bytes)
        self.assertEqual(first.stat().st_mtime_ns, first_mtime)
        self.assertEqual(first.name, hashlib.sha256(raw).hexdigest() + ".json.gz")
        self.assertEqual(gzip.decompress(first_bytes), raw)

    def test_failed_atomic_publication_keeps_game_and_no_partial_snapshot(self):
        exp.install(self.args)
        plugins = self.plugins.read_bytes()
        with patch.object(history.os, "link", side_effect=OSError("publication failed")):
            with self.assertRaisesRegex(SystemExit, "publication failed"):
                exp.uninstall(self.args)
        self.assertEqual(list(self.history.iterdir()), [])
        self.assertEqual(self.plugins.read_bytes(), plugins)
        self.assertTrue((self.data / "Experiment.esm").exists())

    def test_publication_race_reopens_matching_winner_without_replacement(self):
        exp.install(self.args)
        record = self.data / exp.RECORD
        raw = record.read_bytes()
        winner = gzip.compress(raw, compresslevel=1, mtime=0)
        def race(src, dst):
            Path(dst).write_bytes(winner)
            raise FileExistsError("another writer published first")
        with patch.object(history.os, "link", side_effect=race):
            kept = history.preserve_receipt(record)
        self.assertEqual(kept.read_bytes(), winner)
        self.assertEqual(list(self.history.iterdir()), [kept])

    def test_publication_race_with_wrong_winner_blocks_cleanup(self):
        exp.install(self.args)
        def race(src, dst):
            Path(dst).write_bytes(gzip.compress(b'wrong record', mtime=0))
            raise FileExistsError("another writer published first")
        plugins = self.plugins.read_bytes()
        with patch.object(history.os, "link", side_effect=race):
            with self.assertRaisesRegex(SystemExit, "differs from its source"):
                exp.uninstall(self.args)
        self.assertEqual(self.plugins.read_bytes(), plugins)
        self.assertTrue((self.data / "Experiment.esm").exists())
        self.assertEqual(len(list(self.history.iterdir())), 1)

    def test_receipt_change_during_preservation_blocks_cleanup(self):
        exp.install(self.args)
        record = self.data / exp.RECORD
        real = history.verify_copy
        def changed(path, raw):
            real(path, raw)
            record.write_bytes(b'{"concurrent":"edit"}')
        with patch.object(history, "verify_copy", side_effect=changed):
            with self.assertRaisesRegex(SystemExit, "changed while preserving"):
                exp.uninstall(self.args)
        self.assertEqual(record.read_bytes(), b'{"concurrent":"edit"}')
        self.assertTrue((self.data / "Experiment.esm").exists())
        self.assertEqual(len(self.receipts()), 1)

    def test_history_must_be_outside_game_and_staging(self):
        exp.install(self.args)
        for root in (self.data.parent / "receipts", self.staging / "receipts"):
            with self.subTest(root=root), patch.dict("os.environ", {"FO4SF_EXPERIMENT_RECEIPTS": str(root)}):
                with self.assertRaisesRegex(SystemExit, "outside"):
                    exp.uninstall(self.args)
            self.assertFalse(root.exists())
        self.assertTrue((self.data / "Experiment.esm").exists())

    @unittest.skipUnless(os.name == "nt", "Windows extended path syntax")
    def test_history_refuses_extended_path_alias_of_game_data(self):
        exp.install(self.args)
        root = "\\\\?\\" + str(self.data / "receipts")
        with patch.dict("os.environ", {"FO4SF_EXPERIMENT_RECEIPTS": root}):
            with self.assertRaisesRegex(SystemExit, "outside"):
                exp.uninstall(self.args)
        self.assertFalse((self.data / "receipts").exists())
        self.assertTrue((self.data / "Experiment.esm").exists())

    @unittest.skipUnless(os.name == "nt", "Windows local administrative share alias")
    def test_history_refuses_unc_alias_of_game_data_when_available(self):
        drive = self.data.drive.rstrip(":")
        alias = Path("\\\\localhost\\" + drive + "$\\" + str(self.data)[3:])
        try:
            reachable = alias.is_dir() and alias.samefile(self.data)
        except OSError:
            reachable = False
        if not reachable:
            self.skipTest("local share unavailable; no credentials or settings changed")
        exp.install(self.args)
        with patch.dict("os.environ", {"FO4SF_EXPERIMENT_RECEIPTS": str(alias / "receipts")}):
            with self.assertRaisesRegex(SystemExit, "outside"):
                exp.uninstall(self.args)
        self.assertFalse((self.data / "receipts").exists())
        self.assertTrue((self.data / "Experiment.esm").exists())

    def test_history_refuses_physical_data_directory_behind_a_link(self):
        external = self.root / "physical-data"
        external.mkdir()
        self.data.rmdir()  # Fixture's empty directory only; no recursive delete.
        if os.name == "nt":
            made = subprocess.run(["cmd", "/c", "mklink", "/J", str(self.data), str(external)],
                                  capture_output=True)
            if made.returncode:
                self.data.mkdir()
                self.skipTest("native junction creation unavailable")
            self.addCleanup(os.rmdir, self.data)  # Remove junction, never its target.
        else:
            self.data.symlink_to(external, target_is_directory=True)
            self.addCleanup(self.data.unlink)
        self.assertEqual(self.data.resolve(), external)
        exp.install(self.args)
        plugins = self.plugins.read_bytes()
        destination = external / "receipts"
        with patch.dict("os.environ", {"FO4SF_EXPERIMENT_RECEIPTS": str(destination)}):
            with self.assertRaisesRegex(SystemExit, "outside"):
                exp.uninstall(self.args)
        self.assertFalse(destination.exists())
        self.assertTrue((self.data / "Experiment.esm").exists())
        self.assertEqual(self.plugins.read_bytes(), plugins)


if __name__ == "__main__":
    unittest.main()
