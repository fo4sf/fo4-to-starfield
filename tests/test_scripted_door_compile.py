"""Compiler boundary regressions: stale/failed products never become ready stages."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "scripts/door_bridge/compile_load_door.py"
spec = importlib.util.spec_from_file_location("scripted_door_compile", path)
compile_door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compile_door)


class ScriptedDoorCompileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.compiler = self.root / "compiler.exe"
        self.resources = self.root / "sources.zip"
        self.compiler.write_bytes(b"synthetic compiler")
        self.resources.write_bytes(b"synthetic sources")
        self.out = self.root / "candidate"

    def extract(self, resources, work):
        sources = work / "Source"
        sources.mkdir(parents=True)
        (sources / "Game.psc").write_text("synthetic", encoding="utf-8")
        return sources

    def run_compile(self, *, code=0, message="Compilation succeeded", output=b"synthetic pex", mutate=False):
        def run(cmd, **kwargs):
            if output is not None:
                (self.out / "Data/Scripts/FO4SF_LoadDoor.pex").write_bytes(output)
            if mutate:
                self.resources.write_bytes(b"changed")
            return subprocess.CompletedProcess(cmd, code, message, "diagnostic")
        with patch.object(compile_door, "extract", self.extract), patch.object(compile_door.subprocess, "run", run):
            return compile_door.compile_candidate(self.compiler, self.resources, self.out)

    def receipt(self):
        return json.loads((self.out / "compile.json").read_text())

    def test_compiled_artifact_has_pins_but_no_install_or_runtime_acceptance(self):
        result = self.run_compile()
        self.assertEqual(result["status"], "compiled")
        self.assertEqual(result["output_bytes"], len(b"synthetic pex"))
        self.assertEqual(len(result["inputs"]), 4)
        self.assertFalse(result["installable"])
        self.assertFalse(result["runtime_accepted"])

    def test_existing_output_refused_without_touching_old_evidence(self):
        self.out.mkdir()
        old = self.out / "compile.json"
        old.write_bytes(b"old receipt")
        with self.assertRaises(FileExistsError):
            self.run_compile()
        self.assertEqual(old.read_bytes(), b"old receipt")

    def test_nonzero_exit_with_pex_is_failure(self):
        with self.assertRaises(ValueError):
            self.run_compile(code=1)
        self.assertEqual(self.receipt()["status"], "failed")
        self.assertTrue((self.out / "Data/Scripts/FO4SF_LoadDoor.pex").exists())

    def test_zero_exit_without_success_message_is_failure(self):
        with self.assertRaises(ValueError):
            self.run_compile(message="Compilation failed")
        self.assertEqual(self.receipt()["status"], "failed")

    def test_missing_pex_is_failure(self):
        with self.assertRaises(ValueError):
            self.run_compile(output=None)
        self.assertEqual(self.receipt()["status"], "failed")

    def test_empty_pex_is_failure(self):
        with self.assertRaises(ValueError):
            self.run_compile(output=b"")
        self.assertEqual(self.receipt()["status"], "failed")

    def test_changed_input_is_failure(self):
        with self.assertRaisesRegex(ValueError, "input changed"):
            self.run_compile(mutate=True)
        self.assertEqual(self.receipt()["status"], "failed")

    def test_missing_compiler_does_not_create_output(self):
        self.compiler.unlink()
        with self.assertRaisesRegex(ValueError, "missing input"):
            self.run_compile()
        self.assertFalse(self.out.exists())

    def test_archive_changed_during_extraction_never_invokes_compiler(self):
        def changed(resources, work):
            imports = self.extract(resources, work)
            self.resources.write_bytes(b"replaced during extraction")
            return imports
        with patch.object(compile_door, "extract", changed), patch.object(compile_door.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "source extraction"):
                compile_door.compile_candidate(self.compiler, self.resources, self.out)
            run.assert_not_called()
        self.assertEqual(self.receipt()["status"], "failed")


if __name__ == "__main__":
    unittest.main()
