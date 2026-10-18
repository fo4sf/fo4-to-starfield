"""pipeline.Converter marks a converted model `movable` when its collision report says the body is dynamic (synthetic)."""
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from test_review_fixes import nested_nif
from fo4sf import pipeline


class MovablePipelineTests(unittest.TestCase):
    def convert(self, staging, report_patch):
        converter = pipeline.Converter.__new__(pipeline.Converter)
        converter.src = SimpleNamespace(mesh=lambda _: nested_nif())
        converter.staging = staging
        converter.prefix = "fo4port"
        converter.no_collision = None
        converter.collision_template = b"synthetic collision"
        converter.sf_mesh_template = b"synthetic native template"
        converter.rig_doors = False
        converter.door_physics_donor = None
        converter.dynamic_template = b"synthetic dynamic template"
        converter.neutral = "placeholder.mat"
        converter._shape_material = Mock(return_value="synthetic.mat")
        converter.stats = {"assets": 0, "failed": 0}
        seen = {}

        def fake_convert_static(raw, out_name, **kw):
            seen["dynamic_template"] = kw.get("dynamic_template")
            seen["mass_scale"] = kw.get("mass_scale")
            kw["report"].update(report_patch)
            return {}
        with patch.object(pipeline.convert_static, "convert_static", side_effect=fake_convert_static):
            res = converter.convert_nif("meshes/setdressing/rubble/tincan01.nif")
        return res, seen

    def test_dynamic_report_marks_the_item_movable_with_its_mass(self):
        with tempfile.TemporaryDirectory() as staging:
            res, seen = self.convert(staging, {"source": "fo4-native", "motion": "dynamic", "mass_kg": 5.0})
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["movable"], {"mass_kg": 5.0})
        self.assertEqual(seen["dynamic_template"], b"synthetic dynamic template")   # handed to the converter
        self.assertEqual(seen["mass_scale"], 1.0)

    def test_rigid_merge_note_travels_with_the_movable_flag(self):
        with tempfile.TemporaryDirectory() as staging:
            res, _ = self.convert(staging, {"source": "fo4-native", "motion": "dynamic", "mass_kg": 115.0,
                                            "motion_note": "17 FO4 bodies merged into one rigid movable body"})
        self.assertEqual(res["movable"], {"mass_kg": 115.0, "note": "17 FO4 bodies merged into one rigid movable body"})

    def test_static_report_leaves_the_item_fixed(self):
        with tempfile.TemporaryDirectory() as staging:
            res, _ = self.convert(staging, {"source": "fo4-native", "bodies": 2})
        self.assertTrue(res["ok"], res)
        self.assertNotIn("movable", res)


if __name__ == "__main__":
    unittest.main()
