"""Plugins.txt binding refusal; installer effects are injected inside synthetic folders only."""
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

import test_launcher_restore as fixture
from fo4sf.launcher import restore

ROOT = fixture.ROOT

class PluginsNamespaceTests(unittest.TestCase):
    snap = fixture.RestoreTests.snap
    read_pt = fixture.RestoreTests.read_pt

    def setUp(self):
        fixture.RestoreTests.setUp(self)
        local = mock.patch.dict(os.environ, {"LOCALAPPDATA": self.local})
        local.start()
        self.addCleanup(local.stop)

    def bad_paths(self):
        return [Path(self.local) / "Starfield" / "Other.txt",
                Path(self.local) / "Other" / "Plugins.txt",
                Path(self.root) / "elsewhere.txt"]

    def test_snapshot_refuses_unsupported_locations_before_reading(self):
        for path in self.bad_paths():
            with self.subTest(path=str(path)), mock.patch.object(restore, "_read", return_value=None) as reader:
                with self.assertRaisesRegex(restore.RestoreRefused, "Plugins.txt"):
                    restore.take(self.game, str(path))
                reader.assert_not_called()

    def test_legacy_snapshot_refuses_before_running_or_installing(self):
        valid = self.snap()
        for path in [*map(str, self.bad_paths()), None, "", 17]:
            with self.subTest(path=path):
                target = dict(valid, plugins_txt=path)
                running = mock.Mock(return_value=False)
                runner = mock.Mock(return_value=SimpleNamespace(returncode=0))
                with self.assertRaisesRegex(restore.RestoreRefused, "Plugins.txt"):
                    restore.apply(target, ROOT, running=running, run=runner)
                running.assert_not_called()
                runner.assert_not_called()

    def test_wrong_recorded_file_cannot_hide_installer_changes_to_canonical_file(self):
        original = self.read_pt()
        wrong = Path(self.local) / "Starfield" / "Other.txt"
        wrong.write_bytes(original)
        target = dict(self.snap(), plugins_txt=str(wrong))  # Legacy snapshot accepted this path.
        record = Path(self.data) / "FO4SFExp.install.json"
        record.write_text(json.dumps({"files": {}, "plugins": [], "complete": True}), encoding="utf-8")

        def synthetic_installer(argv, *, cwd, env):
            actual = Path(env["LOCALAPPDATA"]) / "Starfield" / "Plugins.txt"
            self.assertEqual(actual, Path(self.pt))
            actual.write_bytes(b"changed by injected synthetic installer")
            record.unlink()
            return SimpleNamespace(returncode=0)

        runner = mock.Mock(side_effect=synthetic_installer)
        with self.assertRaisesRegex(restore.RestoreRefused, "Plugins.txt"):
            restore.apply(target, ROOT, running=lambda: False, run=runner, echo=lambda *_: None)
        runner.assert_not_called()
        self.assertEqual(self.read_pt(), original)
        self.assertEqual(wrong.read_bytes(), original)
        self.assertTrue(record.exists())  # Recovery/ownership record was not cleared.

    def test_plan_and_verify_do_not_approve_invalid_or_different_bindings(self):
        valid = self.snap()
        paths = [*map(str, self.bad_paths()), str(Path(self.root) / "another-local/Starfield/Plugins.txt")]
        for path in paths:
            with self.subTest(path=path):
                other = dict(valid, plugins_txt=path)
                plan = restore.plan(other, valid, ROOT)
                self.assertEqual(plan["steps"], [])
                self.assertTrue(plan["conflicts"])
                self.assertTrue(restore.verify(other, valid))
                self.assertTrue(restore.plan(valid, other, ROOT)["conflicts"])
                self.assertTrue(restore.verify(valid, other))

    def test_direct_writer_refuses_bad_namespace_without_changing_bytes(self):
        wrong = self.bad_paths()[0]
        wrong.write_bytes(b"owner bytes")
        digest = hashlib.sha256(wrong.read_bytes()).hexdigest()
        with self.assertRaisesRegex(restore.RestoreRefused, "Plugins.txt"):
            restore.write_plugins_txt(str(wrong), None, digest)
        self.assertEqual(wrong.read_bytes(), b"owner bytes")

    def test_valid_custom_root_default_and_noop_restore_are_preserved(self):
        original = self.read_pt()
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": self.local}):
            target = restore.take(self.game)
        self.assertEqual(target["plugins_txt"], os.path.abspath(self.pt))
        runner = mock.Mock()
        with self.assertRaisesRegex(restore.RestoreRefused, "running"):
            restore.apply(target, ROOT, running=lambda: True, run=runner)
        runner.assert_not_called()
        self.assertEqual(restore.apply(target, ROOT, running=lambda: False, run=runner), [])
        runner.assert_not_called()
        self.assertEqual(self.read_pt(), original)

    def test_missing_valid_plugins_file_is_recorded_without_creating_directories(self):
        path = Path(self.root) / "missing-local/Starfield/Plugins.txt"
        target = restore.take(self.game, str(path))
        self.assertIsNone(target["plugins_txt_b64"])
        self.assertFalse(path.parent.exists())
        runner = mock.Mock()
        self.assertEqual(restore.apply(target, ROOT, running=lambda: False, run=runner), [])
        runner.assert_not_called()
        self.assertFalse(path.parent.exists())

    def test_case_alias_only_accepts_same_existing_installer_namespace(self):
        alias = Path(self.local) / "sTaRfIeLd/pLuGiNs.TxT"
        if alias.exists():  # Normal Windows case-insensitive alias.
            snap = restore.take(self.game, str(alias))
            self.assertEqual(snap["plugins_txt"], os.path.abspath(self.pt))
            self.assertEqual(snap["plugins_txt_sha256"], self.snap()["plugins_txt_sha256"])
        else:  # A distinct/missing namespace on a case-sensitive filesystem.
            alias.parent.mkdir(exist_ok=True)
            alias.write_bytes(self.read_pt())  # Equal bytes still do not make it the installer address.
            with self.assertRaisesRegex(restore.RestoreRefused, "Plugins.txt"):
                restore.take(self.game, str(alias))


if __name__ == "__main__":
    unittest.main()
