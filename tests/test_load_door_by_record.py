"""FO4 teleport doors are load doors by their record (a Door reference with an XTEL), not only by a "...DoorLoad..."
file name: the Museum of Witchcraft roof hatch (RoofHatch01) stayed a STAT and could not be used from inside (owner
2026-10-18). Synthetic fixtures only."""
import importlib.util
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_sliding_doors  # noqa: E402
from test_door_two_panels import two_leaves  # noqa: E402

spec = importlib.util.spec_from_file_location("convert_batch", os.path.join(ROOT, "scripts", "convert_batch.py"))
convert_batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(convert_batch)

HATCH = "meshes\\SetDressing\\Synthetic\\RoofHatch01.nif"


class TeleportModelsTests(unittest.TestCase):
    def test_only_door_references_with_an_xtel_count(self):
        cell = {"refs": [
            {"type": "Door", "model": "SetDressing\\Synthetic\\RoofHatch01.nif", "teleport_destination": {"door": "x"}},
            {"type": "Door", "model": "SetDressing\\Doors\\PlainDoor01.nif", "teleport_destination": None},
            {"type": "Static", "model": "Architecture\\Wall01.nif", "teleport_destination": {"door": "y"}},
            {"type": "Door", "model": "", "teleport_destination": {"door": "z"}}]}
        self.assertEqual(convert_batch.teleport_models(cell), [HATCH])


class ConverterTests(unittest.TestCase):
    convert = test_sliding_doors.NonHingedRoutingTests.convert

    def test_a_teleporting_hatch_becomes_a_load_door_and_is_not_rigged(self):
        with tempfile.TemporaryDirectory() as staging:
            result, single, multi, static = self.convert(staging, HATCH, two_leaves()[:1], "calumi.dll",
                                                         load_door_models={HATCH.lower()})
        self.assertIn("load_door", result)
        single.assert_not_called()
        multi.assert_not_called()
        static.assert_called_once()

    def test_without_the_record_the_same_model_is_no_load_door(self):
        with tempfile.TemporaryDirectory() as staging:
            result, *_ = self.convert(staging, HATCH, two_leaves()[:1], "calumi.dll")
        self.assertNotIn("load_door", result)


if __name__ == "__main__":
    unittest.main()
