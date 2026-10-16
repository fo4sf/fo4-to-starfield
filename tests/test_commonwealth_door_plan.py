"""Synthetic planning joins; no game files or live input."""
import copy
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("door_plan", Path(__file__).parents[1] / "scripts/slice/plan_commonwealth_doors.py")
plan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plan)


class DoorPlanTests(unittest.TestCase):
    def setUp(self):
        self.outer = "000111:Fallout4.esm"
        self.inner = "000222:Fallout4.esm"
        self.cell = "000333:Fallout4.esm"
        self.band = {"worldspace": {"editor_id": "Commonwealth"}, "refs": [
            {"formkey": self.outer, "type": "Door", "teleport_destination": {"door": self.inner}}],
            "teleport_dependencies": [{"source": self.outer, "door": self.inner,
                "destination_cell": {"formkey": self.cell, "editor_id": "Room", "worldspace": None}}]}
        self.objects = {"refs": [{"src": self.outer, "base": 0}], "bases": [{"edid": "base"}]}
        self.core = {"plugin": "Core.esm", "refs": {self.outer: "000900"}}
        self.port = {"CELL:FO4Port_Room": 2048, "REFR:FO4Port_Room:" + self.inner: 2049}
        self.interiors = [{"formkey": self.cell, "cell": "Room", "refs": [
            {"formkey": self.inner, "teleport_destination": {"door": self.outer}}]}]

    def run_plan(self, bands=None):
        return plan.inventory(bands or [self.band], self.objects, self.core, self.port, self.interiors)

    def test_mapping_is_not_functional_door_acceptance(self):
        report = self.run_plan()
        row = report["doors"][0]
        self.assertEqual(report["counts"]["placed_load_doors_to_mapped_interiors"], 1)
        self.assertTrue(row["source_return_is_reciprocal"])
        self.assertFalse(row["core_base_has_door_metadata"])
        self.assertFalse(report["native_acceptance"])

    def test_same_local_id_other_plugin_does_not_match(self):
        self.band["teleport_dependencies"][0]["destination_cell"]["formkey"] = "000333:Other.esm"
        self.assertFalse(self.run_plan()["doors"][0]["interior_cell_mapped"])

    def test_casefolded_source_identity_matches(self):
        self.port["REFR:fo4port_room:" + self.inner.lower()] = self.port.pop("REFR:FO4Port_Room:" + self.inner)
        self.assertEqual(self.run_plan()["doors"][0]["port_door_id"], 2049)

    def test_duplicate_normalized_map_key_refused(self):
        self.core["refs"][self.outer.lower()] = "000901"
        with self.assertRaisesRegex(ValueError, "duplicate normalized"):
            self.run_plan()

    def test_malformed_local_id_refused(self):
        self.core["refs"][self.outer] = "runtime-id"
        with self.assertRaisesRegex(ValueError, "invalid core local ID"):
            self.run_plan()

    def test_auxiliary_floor_is_not_a_source_reference(self):
        self.port["REFR:FO4Port_DoorTest:floor"] = 3000
        report = self.run_plan()
        self.assertEqual(report["auxiliary_port_reference_keys"], ["REFR:FO4Port_DoorTest:floor"])
        self.assertEqual(report["doors"][0]["port_door_id"], 2049)

    def test_missing_destination_stays_unknown(self):
        self.band["teleport_dependencies"].clear()
        report = self.run_plan()
        self.assertEqual(report["counts"]["unresolved_load_destinations"], 1)
        self.assertIn("missing_destination_dependency", report["doors"][0]["warnings"])

    def test_core_map_without_object_is_not_placed_count(self):
        self.objects["refs"].clear()
        report = self.run_plan()
        self.assertEqual(report["counts"]["placed_load_doors_to_mapped_interiors"], 0)
        self.assertIn("core_objects_map_disagree", report["doors"][0]["warnings"])

    def test_cell_mapping_does_not_invent_endpoint(self):
        del self.port["REFR:FO4Port_Room:" + self.inner]
        row = self.run_plan()["doors"][0]
        self.assertTrue(row["interior_cell_mapped"])
        self.assertIsNone(row["port_door_id"])

    def test_duplicate_bands_deduplicate_but_conflicts_refused(self):
        self.assertEqual(self.run_plan([self.band, copy.deepcopy(self.band)])["counts"]["doors"], 1)
        other = copy.deepcopy(self.band)
        other["refs"][0]["disabled"] = True
        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            self.run_plan([self.band, other])

    def test_wrong_dependency_refused(self):
        self.band["teleport_dependencies"][0]["door"] = "000444:Fallout4.esm"
        with self.assertRaisesRegex(ValueError, "mismatch"):
            self.run_plan()

    def test_nonteleport_door_in_inventory_not_load_count(self):
        self.band["refs"][0]["teleport_destination"] = None
        self.band["teleport_dependencies"].clear()
        report = self.run_plan()
        self.assertEqual(report["counts"]["doors"], 1)
        self.assertEqual(report["counts"]["load_doors"], 0)


if __name__ == "__main__":
    unittest.main()
