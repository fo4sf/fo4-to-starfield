"""Opt-in synthetic writer failures: persist IDs before any plugin publication."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.environ.get("FO4SF_PLUGIN_WRITER"), "set FO4SF_PLUGIN_WRITER to built PluginSpike.dll")
class PluginIdentityPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fo4sf-formid-publication-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / "empty-data"
        self.data.mkdir()
        self.manifest = self.root / "manifest.json"
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("FO4PORT_")}
        self.env["STARFIELD_DATA"] = str(self.data)
        if os.name == "nt":
            import ctypes
            # Child writer failures must not open the Windows crash dialog.
            previous = ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002)
            self.addCleanup(ctypes.windll.kernel32.SetErrorMode, previous)

    def write(self, stage, names):
        self.manifest.write_text(json.dumps({"items": [
            {"editor_id": "Synthetic_" + name, "model": "synthetic/" + name + ".nif",
             "source": "meshes/synthetic/" + name + ".nif"} for name in names]}))
        return subprocess.run(["dotnet", os.environ["FO4SF_PLUGIN_WRITER"], str(stage), str(self.manifest)],
                              env=self.env, capture_output=True, text=True, timeout=45)

    def test_map_failure_cannot_create_or_replace_a_plugin(self):
        for existing in (False, True):
            with self.subTest(existing_plugin=existing):
                stage = self.root / str(existing)
                stage.mkdir()
                (stage / "formids.json").mkdir()  # An unavailable destination, not a deletable file.
                plugin = stage / "FO4Port.esm"
                previous = b"previous synthetic plugin must remain untouched"
                if existing:
                    plugin.write_bytes(previous)
                result = self.write(stage, ["a"])
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                if existing:
                    self.assertEqual(plugin.read_bytes(), previous)
                else:
                    self.assertFalse(plugin.exists())
                self.assertTrue((stage / "formids.json").is_dir())
                self.assertEqual(list(stage.glob(".formids-*.pending")), [])

    def test_plugin_failure_keeps_reserved_ids_for_reordered_retry(self):
        stage = self.root / "stage"
        stage.mkdir()
        plugin = stage / "FO4Port.esm"
        plugin.mkdir()  # Fail the plugin writer after IDs have been reserved.
        result = self.write(stage, ["a", "b"])
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        mapping = stage / "formids.json"
        self.assertTrue(mapping.is_file(), "failed plugin output lost allocated ID reservations")
        reserved = json.loads(mapping.read_text())
        self.assertEqual(len(reserved), 2)
        plugin.rmdir()  # Empty fixture directory in this test's private temporary root.
        retry = self.write(stage, ["c", "b", "a"])
        self.assertEqual(retry.returncode, 0, retry.stdout + retry.stderr)
        restored = json.loads(mapping.read_text())
        for key, value in reserved.items():
            self.assertEqual(restored[key], value)
        self.assertEqual(len(set(restored.values())), 3)
        self.assertTrue(plugin.is_file())


if __name__ == "__main__":
    unittest.main()
