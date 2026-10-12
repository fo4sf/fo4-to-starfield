"""Native door resume checks use the production converter's synthetic fixture."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import test_door_two_panels as fixtures
from test_checkpoints import generated
from fo4sf import checkpoints


class NativeDoorCheckpointTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.staging = Path(temporary.name)
        _, (self.files, door) = fixtures.MultipartDoorTests().convert(fixtures.two_leaves())
        self.result = {"ok": True, "out_name": "fo4port/doors/testdouble",
                       "fallback_materials": 0, "shapes": 3, "door": door}
        self.dependencies = set(door["files"])
        self.signature = {"synthetic": "native-door"}
        self.write_outputs()

    def write_outputs(self):
        for relative, data in self.files.items():
            path = self.staging / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def cache(self):
        return checkpoints.Checkpoints(self.staging, self.signature)

    def test_unchanged_native_door_reuses_every_rig_and_clip_dependency(self):
        cache = self.cache()
        self.assertTrue(cache.save("double.nif", self.result))
        loaded = self.cache()
        self.assertEqual(loaded.load("double.nif"), self.result)
        self.assertTrue(self.dependencies.issubset(loaded.expected["double.nif"]))

    def test_omitted_inventory_entry_cannot_hide_missing_referenced_file(self):
        cache = self.cache()
        self.assertTrue(cache.save("double.nif", self.result))
        original = json.loads(cache.path("double.nif").read_text())
        for relative in sorted(self.dependencies):
            with self.subTest(dependency=relative):
                self.write_outputs()
                saved = copy.deepcopy(original)
                saved["result"]["door"]["files"].remove(relative)
                del saved["outputs"][relative]
                cache.path("double.nif").write_text(json.dumps(saved))
                (self.staging / relative).unlink()
                loaded = self.cache()
                self.assertIsNone(loaded.load("double.nif"))
                self.assertEqual(loaded.expected, {})

    def test_door_references_are_followed_when_files_list_is_absent(self):
        result = copy.deepcopy(self.result)
        del result["door"]["files"]
        inventory = checkpoints.output_inventory(self.staging, result)
        self.assertTrue(self.dependencies.issubset(inventory))
        for relative in sorted(self.dependencies):
            with self.subTest(dependency=relative):
                self.write_outputs()
                (self.staging / relative).unlink()
                cache = self.cache()
                with self.assertRaises(OSError):
                    cache.save("double.nif", result)
                self.assertEqual(cache.verify_batch(), [
                    {"source": "double.nif", "output": "<dependency inventory unavailable>"}])

    def test_changed_rig_or_clip_invalidates_native_door_reuse(self):
        for relative in sorted(self.dependencies):
            with self.subTest(dependency=relative):
                self.write_outputs()
                cache = self.cache()
                self.assertTrue(cache.save("double.nif", self.result))
                (self.staging / relative).write_bytes(b"changed synthetic animation")
                self.assertIsNone(self.cache().load("double.nif"))
                self.assertIn({"source": "double.nif", "output": relative}, cache.verify_batch())

    def test_omitted_rig_tag_cannot_hide_generated_dependencies(self):
        result = copy.deepcopy(self.result)
        del result["door"]["rig"]
        del result["door"]["files"]
        cache = self.cache()
        self.assertTrue(cache.save("double.nif", result))
        original = json.loads(cache.path("double.nif").read_text())
        self.assertTrue(self.dependencies.issubset(original["outputs"]))
        for relative in sorted(self.dependencies):
            with self.subTest(dependency=relative):
                self.write_outputs()
                saved = copy.deepcopy(original)
                del saved["outputs"][relative]
                cache.path("double.nif").write_text(json.dumps(saved))
                (self.staging / relative).unlink()
                self.assertIsNone(self.cache().load("double.nif"))

    def test_vanilla_template_references_do_not_require_staged_copies(self):
        result, _ = generated(self.staging, "template")
        result["door"] = {"skeleton": "architecture\\vanilla\\characterassets\\skeleton.rig",
                          "animations": "architecture\\vanilla\\animations"}
        for rig in (None, "template"):
            with self.subTest(rig=rig):
                result["door"]["rig"] = rig
                cache = self.cache()
                self.assertTrue(cache.save("template.nif", result))
                self.assertEqual(self.cache().load("template.nif"), result)

    def test_missing_or_invalid_native_reference_metadata_cannot_resume(self):
        for key in ("skeleton", "animations"):
            for value in (None, "", 123, "../outside", "/absolute", "C:/absolute", "safe//invalid"):
                with self.subTest(field=key, value=value):
                    result = copy.deepcopy(self.result)
                    result["door"][key] = value
                    with self.assertRaises(ValueError):
                        checkpoints.output_inventory(self.staging, result)


if __name__ == "__main__":
    unittest.main()
