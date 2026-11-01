"""Recorded port restores use pinned prebuilt outputs, never a late rebuild after uninstall."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf.launcher import restore  # noqa: E402

spec = importlib.util.spec_from_file_location("restore_test_deploy", ROOT / "scripts/deploy_starfield.py")
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


def tes4(seed=0):
    body = b"HEDR" + struct.pack("<HfII", 12, 0.96, 0, 0x800 + seed)
    return b"TES4" + struct.pack("<IIIIHH", len(body), 1, 0, 0, 0, 0) + body


class RecordedPortRestoreTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.game = self.root / "synthetic-game"
        self.data = self.game / "Data"
        self.data.mkdir(parents=True)
        self.local = self.root / "local"
        self.pt = self.local / "Starfield" / "Plugins.txt"
        self.pt.parent.mkdir(parents=True)
        self.pt.write_bytes(b"# synthetic owner comment\r\n")
        (self.data / "Starfield.esm").write_bytes(tes4())
        self.calls = []
        self.env = dict(os.environ, LOCALAPPDATA=str(self.local))

    def stage(self, name, seed=0, companions=False):
        stage = self.root / name
        stage.mkdir()
        (stage / deploy.PLUGIN).write_bytes(tes4(seed))
        (stage / deploy.ARCHIVE).write_bytes(b"BTDX" + bytes([seed]) * 28)
        if companions:
            (stage / "FO4PortTextures2.esm").write_bytes(tes4(seed + 2))
            (stage / "FO4PortTextures2 - Textures.ba2").write_bytes(b"BTDX" + b"T" * 28)
        return stage

    def publish(self, stage, companions=False):
        names = [deploy.PLUGIN, deploy.ARCHIVE]
        cohort = ["FO4PortTextures2.esm"] if companions else []
        for name in cohort:
            names += [name, name[:-4] + " - Textures.ba2"]
        built = [stage / name for name in names]
        with patch.dict(os.environ, self.env), contextlib.redirect_stdout(io.StringIO()):
            deploy.publish(str(self.data), str(self.data / deploy.MANIFEST), [str(p) for p in built],
                           [str(self.data / p.name) for p in built],
                           {p.name: deploy.artifact_identity(p) for p in built}, cohort)

    def uninstall(self):
        with patch.dict(os.environ, self.env), contextlib.redirect_stdout(io.StringIO()):
            deploy.uninstall(type("Args", (), {"starfield": str(self.game), "dry_run": False})())

    def snap(self):
        return restore.take(str(self.game), str(self.pt))

    def pair(self, companions=False):
        a, b = self.stage("a", companions=companions), self.stage("b", seed=1)
        self.publish(a, companions)
        target = self.snap()
        self.uninstall()
        self.publish(b)
        return target, a

    def run_installer(self, argv, **kwargs):
        self.calls.append(argv)
        self.assertIn(str(self.game), argv)
        self.assertEqual(kwargs["env"]["LOCALAPPDATA"], str(self.local))
        result = subprocess.run(argv, capture_output=True, **kwargs)
        self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
        return result

    def apply(self, target, stage, run=None):
        return restore.apply(target, str(ROOT), port_staging=str(stage), running=lambda: False,
                             run=run or self.run_installer, echo=lambda *_: None)

    def bytes_now(self):
        return ({str(p.relative_to(self.data)): p.read_bytes() for p in self.data.rglob("*") if p.is_file()},
                self.pt.read_bytes())

    def refused(self, target, stage, text):
        plan = restore.plan(target, self.snap(), str(ROOT), port_staging=str(stage))
        self.assertTrue(any("port:" in p and text in p for p in plan["conflicts"]), plan)
        before = self.bytes_now()
        def forbidden(*args, **kwargs):
            self.fail("a refused port restore must not run even its first uninstall")
        with self.assertRaises(restore.RestoreRefused):
            self.apply(target, stage, run=forbidden)
        self.assertEqual(self.bytes_now(), before)

    def test_different_plugin_refuses_before_uninstall(self):
        target, stage = self.pair()
        (stage / deploy.PLUGIN).write_bytes(tes4(7))
        self.refused(target, stage, deploy.PLUGIN)

    def test_different_archive_refuses_before_uninstall(self):
        target, stage = self.pair()
        (stage / deploy.ARCHIVE).write_bytes(b"BTDX" + b"X" * 28)
        self.refused(target, stage, deploy.ARCHIVE)

    def test_missing_archive_refuses_before_uninstall(self):
        target, stage = self.pair()
        (stage / deploy.ARCHIVE).unlink()
        self.refused(target, stage, deploy.ARCHIVE)

    def test_interrupted_stage_refuses_before_uninstall(self):
        target, stage = self.pair()
        (stage / "build-state.json").write_text(json.dumps({"complete": False}), encoding="utf8")
        self.refused(target, stage, "build-state.json")

    def test_matching_prebuilt_port_restores_without_archive2(self):
        target, stage = self.pair()
        # No Archive2 executable or loose mesh inputs exist anywhere in this synthetic game/stage.
        self.assertEqual(self.apply(target, stage), [])
        self.assertIn("--restore-stdin", self.calls[-1])

    def test_companion_cohort_is_replayed_and_enabled(self):
        target, stage = self.pair(companions=True)
        self.assertEqual(self.apply(target, stage), [])
        self.assertTrue((self.data / "FO4PortTextures2.esm").is_file())
        self.assertTrue((self.data / "FO4PortTextures2 - Textures.ba2").is_file())
        self.assertEqual(restore.record_identity("port", self.snap()["records"]["port"]),
                         restore.record_identity("port", target["records"]["port"]))
        self.assertIn(b"*FO4PortTextures2.esm", self.pt.read_bytes())

    def replay_batch(self, use_subfolder):
        batch = self.root / "batch"
        batch.mkdir()
        target, stage = self.pair(companions=True)
        port = batch / "port"
        stage.rename(port)
        (batch / "result.json").write_text('{"pass":true}', encoding="utf8")
        self.assertEqual(self.apply(target, port if use_subfolder else batch), [])

    def test_batch_root_is_supported(self):
        self.replay_batch(False)

    def test_batch_port_subfolder_is_supported(self):
        self.replay_batch(True)

    def test_failed_batch_result_refuses_before_uninstall(self):
        target, stage = self.pair(companions=True)
        (stage / "result.json").write_text('{"pass":false}', encoding="utf8")
        self.refused(target, stage, "result.json")

    def test_legacy_unpinned_record_is_refused(self):
        target, stage = self.pair()
        target = copy.deepcopy(target)
        del target["records"]["port"]["artifacts"][deploy.ARCHIVE]["sha256"]
        self.refused(target, stage, "identity")

    def test_unsupported_artifact_identity_is_refused_before_uninstall(self):
        target, stage = self.pair()
        target = copy.deepcopy(target)
        target["records"]["port"]["artifacts"][deploy.ARCHIVE]["future_field"] = "not-replayable"
        self.refused(target, stage, "identity")

    def test_target_cannot_name_paths_outside_the_port_set(self):
        target, stage = self.pair()
        target = copy.deepcopy(target)
        target["records"]["port"]["files"].append("../owner.esm")
        self.refused(target, stage, "complete port set")

    def test_missing_companion_pair_is_refused(self):
        target, stage = self.pair(companions=True)
        target = copy.deepcopy(target)
        name = "FO4PortTextures2 - Textures.ba2"
        target["records"]["port"]["files"].remove(name)
        del target["records"]["port"]["artifacts"][name]
        self.refused(target, stage, "cohort")

    def test_bad_stdin_is_refused_by_actual_cli_without_writing(self):
        stage = self.stage("bad-input")
        before = self.bytes_now()
        for content in ("null", "not-json", '{"schema":1}'):
            with self.subTest(content=content):
                result = subprocess.run([sys.executable, str(ROOT / "scripts/deploy_starfield.py"), "install",
                    "--restore-stdin", "--staging", str(stage), "--starfield", str(self.game)],
                    input=content, text=True, capture_output=True, env=self.env)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.bytes_now(), before)

    def test_recorded_install_refuses_an_unexpected_core_without_writing(self):
        target, stage = self.pair()
        self.uninstall()
        (self.data / "FO4TerrainCore.esm").write_bytes(tes4(15))
        before = self.bytes_now()
        payload = {"schema": 1, "files": target["records"]["port"]["files"],
                   "artifacts": target["records"]["port"]["artifacts"], "core_sha256": None}
        result = subprocess.run([sys.executable, str(ROOT / "scripts/deploy_starfield.py"), "install",
            "--restore-stdin", "--staging", str(stage), "--starfield", str(self.game)],
            input=json.dumps(payload), text=True, capture_output=True, env=self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("core differs", result.stderr)
        self.assertEqual(self.bytes_now(), before)

    def test_target_core_is_restored_before_the_port(self):
        def experiment(action, stage=None):
            argv = [sys.executable, str(ROOT / "scripts/game/exp_install.py"), action,
                    "--starfield", str(self.game)]
            if stage:
                argv += ["--exp-dir", str(stage), "--plugins", "FO4TerrainCore.esm"]
            result = subprocess.run(argv, env=self.env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        a, b = self.stage("a"), self.stage("b", seed=1)
        ca, cb = self.root / "core-a", self.root / "core-b"
        for stage, seed in ((ca, 8), (cb, 9)):
            stage.mkdir()
            (stage / "FO4TerrainCore.esm").write_bytes(tes4(seed))
        experiment("install", ca)
        self.publish(a, False)
        target = self.snap()
        self.uninstall()
        experiment("uninstall")
        experiment("install", cb)
        self.publish(b, False)
        plan = restore.plan(target, self.snap(), str(ROOT), port_staging=str(a))
        self.assertEqual(plan["conflicts"], [])
        steps = [s["what"] for s in plan["steps"]]
        self.assertLess(steps.index("install experiment"), steps.index("install port"))
        self.assertEqual(self.apply(target, a), [])

    def test_copy_is_pinned_even_if_source_changes_after_preflight(self):
        target, stage = self.pair()
        self.uninstall()
        spec = {"schema": 1, "files": target["records"]["port"]["files"],
                "artifacts": target["records"]["port"]["artifacts"], "core_sha256": None}
        before = self.bytes_now()
        real_copy = deploy.copy_new_artifact
        def changed_source(src, dst, expected_sha256=None):
            self.assertEqual(expected_sha256, spec["artifacts"][Path(src).name]["sha256"])
            Path(src).write_bytes(tes4(19))
            return real_copy(src, dst, expected_sha256=expected_sha256)
        args = type("Args", (), {"starfield": str(self.game), "staging": str(stage),
                                  "restore_stdin": True, "dry_run": False})()
        with patch.dict(os.environ, self.env), patch.object(sys, "stdin", io.StringIO(json.dumps(spec))), \
                patch.object(deploy, "copy_new_artifact", side_effect=changed_source), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(SystemExit, "source changed since preflight"):
                deploy.install(args)
        self.assertEqual(self.bytes_now(), before)


if __name__ == "__main__":
    unittest.main()
