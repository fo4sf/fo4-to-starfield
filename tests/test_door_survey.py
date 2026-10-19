"""scripts/terrain/door_survey.py: FO4's door set-up per reference, on a synthetic cell export."""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
import door_survey  # noqa: E402

CELL = {"cell": "SyntheticCell", "door_bases": {
    "000A01:Fallout4.esm": {"record": {"Flags": "Automatic, MinimalUse"}, "scripts": [{"name": "ElevatorDoorScript"}]}},
    "refs": [
        {"formkey": "000B01:Fallout4.esm", "type": "Door", "base_formkey": "000A01:Fallout4.esm", "base_editor_id": "Lift",
         "model": "SetDressing\\Elevator\\Lift.nif", "teleport_destination": {"door": "000B09:Fallout4.esm"},
         "lock_data": None, "open_by_default": False, "disabled": 0},
        {"formkey": "000B02:Fallout4.esm", "type": "Door", "base_formkey": "000A02:Fallout4.esm", "base_editor_id": "Plain",
         "model": "SetDressing\\Doors\\Plain.nif", "lock_data": {"level": 50, "key": "000C01:Fallout4.esm"},
         "open_by_default": True, "disabled": 2048, "scripts": [{"name": "DefaultLockScript"}],
         "activate_parents": {"parents": [{"reference": "000B05:Fallout4.esm"}]}},
        {"formkey": "000B03:Fallout4.esm", "type": "Static", "model": "Wall.nif"}]}


class SurveyTests(unittest.TestCase):
    def test_each_door_gets_its_fo4_behaviour_and_build_result(self):
        with tempfile.TemporaryDirectory() as d:
            cell, manifest = os.path.join(d, "c.json"), os.path.join(d, "m.json")
            with open(cell, "w") as f:
                json.dump(CELL, f)
            with open(manifest, "w") as f:
                json.dump({"items": [{"source": "meshes\\SetDressing\\Doors\\Plain.nif", "model": "fo4port\\plain.nif",
                                      "door": {"rig": "native"}, "collision_report": {"source": "fo4-mesh"}}]}, f)
            rows = door_survey.survey([cell], [manifest])
        self.assertEqual(len(rows), 2)
        lift, plain = rows
        self.assertEqual(lift["classes"], ["load door", "scripted", "flag Automatic", "flag MinimalUse"])
        self.assertEqual(lift["build"], "not converted")
        self.assertEqual(plain["classes"], ["locked (key)", "open by default", "enabled by something else",
                                            "opened by another reference", "scripted"])
        self.assertFalse(plain["base_exported"])
        self.assertEqual(plain["build"], {"door_rig": "native", "collision": "fo4-mesh"})
        s = door_survey.summary(rows)
        self.assertEqual((s["doors"], s["classes"]["scripted"], s["bases_without_export"]), (2, 2, 1))


if __name__ == "__main__":
    unittest.main()
