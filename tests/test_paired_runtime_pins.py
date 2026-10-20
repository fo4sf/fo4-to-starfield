"""Runtime launcher aliases must hash their resolved binaries; source guards stay strict."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts/terrain"), str(ROOT / "src")]
import paired_stage as paired


class RuntimePinTests(unittest.TestCase):
    def test_regular_runtime_pins_bind_the_actual_path_and_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            python, dotnet = root / "python-real", root / "dotnet-real"
            python.write_bytes(b"synthetic python")
            dotnet.write_bytes(b"synthetic dotnet")
            with mock.patch.object(paired.sys, "executable", str(python)), \
                    mock.patch.object(paired.shutil, "which", return_value=str(dotnet)), \
                    mock.patch.object(paired.subprocess, "check_output", side_effect=[b"", b"synthetic info"]):
                pins = paired.writer_pins()
            for name, path in (("python", python), ("dotnet", dotnet)):
                self.assertEqual(pins[f"runtime:{name}"], {
                    "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})

    def test_symlink_runtime_retargeting_changes_both_identity_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            binaries = [root / name for name in ("python-a", "python-b", "dotnet-real")]
            for path in binaries:
                path.write_bytes(path.name.encode())
            python, dotnet = root / "python", root / "dotnet"
            try:
                python.symlink_to(binaries[0])
                dotnet.symlink_to(binaries[2])
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"file symlinks unavailable without changing system permissions: {error}")
            def pins():
                with mock.patch.object(paired.sys, "executable", str(python)), \
                        mock.patch.object(paired.shutil, "which", return_value=str(dotnet)), \
                        mock.patch.object(paired.subprocess, "check_output", side_effect=[b"", b"synthetic info"]):
                    return paired.writer_pins()
            first = pins()
            self.assertEqual(first["runtime:python"]["path"], str(binaries[0]))
            self.assertEqual(first["runtime:python"]["sha256"], paired.sha(binaries[0].read_bytes()))
            self.assertEqual(first["runtime:dotnet"]["path"], str(binaries[2]))
            # Ordinary source/state readers must STILL refuse aliases.
            with self.assertRaisesRegex(ValueError, "non-reparse"):
                paired.read(python)
            python.unlink()
            python.symlink_to(binaries[1])
            second = pins()
            self.assertEqual(second["runtime:python"]["path"], str(binaries[1]))
            self.assertEqual(second["runtime:python"]["sha256"], paired.sha(binaries[1].read_bytes()))
            self.assertNotEqual(first["runtime:python"], second["runtime:python"])


if __name__ == "__main__":
    unittest.main()
