"""Opt-in binary writer controls for invalid or exhausted persistent reservations."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.environ.get("FO4SF_PLUGIN_WRITER"), "set FO4SF_PLUGIN_WRITER to built PluginSpike.dll")
class PluginIdentityValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fo4sf-formid-validation-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / "empty-data"
        self.data.mkdir()
        self.manifest = self.root / "manifest.json"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("FO4PORT_")}
        self.env["STARFIELD_DATA"] = str(self.data)
        if os.name == "nt":
            import ctypes
            previous = ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002)
            self.addCleanup(ctypes.windll.kernel32.SetErrorMode, previous)

    def write(self, stage, names):
        self.manifest.write_text(json.dumps({"items": [
            {"editor_id": "Synthetic_" + name, "model": "synthetic/" + name + ".nif",
             "source": "synthetic/" + name + ".nif"} for name in names]}), encoding="utf-8")
        return subprocess.run(["dotnet", os.environ["FO4SF_PLUGIN_WRITER"], str(stage), str(self.manifest)],
                              env=self.env, capture_output=True, text=True, timeout=45)

    def test_invalid_reservations_cannot_replace_map_or_plugin(self):
        cases = {
            "zero": {"STAT:Synthetic_a": 0},
            "reserved_low": {"STAT:Synthetic_a": 0x7FF},
            "aliased_high_byte": {"STAT:Synthetic_a": 0x01000800},
            "overflow_tombstone": {"STAT:Synthetic_a": 0x800, "STAT:removed": 0xFFFFFFFF},
            "duplicate_tombstone": {"STAT:Synthetic_a": 0x800, "STAT:removed": 0x800},
        }
        for name, mapping in cases.items():
            with self.subTest(name=name):
                stage = self.root / name
                stage.mkdir()
                path = stage / "formids.json"
                before = json.dumps(mapping).encode("utf-8")
                path.write_bytes(before)
                plugin = stage / "FO4Port.esm"
                prior = b"keep the previous synthetic plugin"
                plugin.write_bytes(prior)
                result = self.write(stage, ["a"])
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(plugin.read_bytes(), prior)
                self.assertEqual(list(stage.glob(".formids-*.pending")), [])

    def test_duplicate_json_keys_and_non_maps_cannot_create_a_plugin(self):
        cases = ['{"STAT:Synthetic_a":2048,"STAT:Synthetic_a":2304}', "null", "[]"]
        for index, text in enumerate(cases):
            with self.subTest(text=text):
                stage = self.root / str(index)
                stage.mkdir()
                path = stage / "formids.json"
                path.write_text(text, encoding="utf-8")
                before = path.read_bytes()
                result = self.write(stage, ["a"])
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse((stage / "FO4Port.esm").exists())
                self.assertEqual(path.read_bytes(), before)

    def test_last_id_can_be_reused_but_no_new_identity_can_alias_it(self):
        stage = self.root / "limit"
        stage.mkdir()
        path = stage / "formids.json"
        path.write_text(json.dumps({"STAT:Synthetic_a": 0xFFFFFE}), encoding="utf-8")
        result = self.write(stage, ["b", "a"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        mapping = json.loads(path.read_text())
        self.assertEqual(mapping, {"STAT:Synthetic_a": 0xFFFFFE, "STAT:Synthetic_b": 0xFFFFFF})
        result = self.write(stage, ["a", "b"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(path.read_text()), mapping)
        plugin = stage / "FO4Port.esm"
        prior = plugin.read_bytes()
        before = path.read_bytes()
        result = self.write(stage, ["c", "b", "a"])
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(plugin.read_bytes(), prior)

    def test_sparse_ids_and_unused_reservations_stay_unchanged(self):
        stage = self.root / "sparse"
        stage.mkdir()
        path = stage / "formids.json"
        original = {"STAT:Synthetic_a": 0x900, "STAT:removed": 0x123456}
        path.write_text(json.dumps(original), encoding="utf-8")
        result = self.write(stage, ["b", "a"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        mapping = json.loads(path.read_text())
        self.assertEqual(mapping, dict(original, **{"STAT:Synthetic_b": 0x123457}))


if __name__ == "__main__":
    unittest.main()
