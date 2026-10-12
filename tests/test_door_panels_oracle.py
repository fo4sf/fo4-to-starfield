"""Offline door oracles on multi-part doors: per-part tracks and bodies (door_panels.py) and per-bone moving bodies
(door_bodies.py, native rig). Synthetic NIFs only."""
import importlib.util
import struct
import unittest
from pathlib import Path

from test_collision import fake_template
from test_door_two_panels import donor, door_nif, fake_clip_files, two_leaves
from fo4sf import convert_static, nif, sfnif


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / f"scripts/oracles/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


panels = load("door_panels")
bodies_oracle = load("door_bodies")


def native_model(material_paths=None):
    source = nif.serialize(door_nif(two_leaves()))
    files, door = convert_static.convert_multipart_door(source, "fo4port/d", material_paths or ["a", "b", "c"],
                                                        fake_clip_files, collision_template=fake_template(),
                                                        leaf_physics_donor=donor())
    return source, files["meshes/fo4port/d.nif"], door


class DoorPanelsOracleTests(unittest.TestCase):
    def test_source_parts_mark_the_part_outside_the_template_hinge(self):
        self.assertEqual(panels.source_parts(nif.serialize(door_nif(two_leaves()))), [("LeafA", True), ("LeafB", False)])

    def test_template_door_freezes_the_second_leaf(self):
        rows = panels.assess([("LeafA", True), ("LeafB", False)], "template", {}, {}, template_body=True)
        self.assertEqual([(r["part"], r["status"]) for r in rows], [("LeafA", "moves"), ("LeafB", "frozen")])

    def test_native_door_moves_both_leaves_and_each_has_a_body(self):
        source, model, door = native_model()
        bodies = panels.model_bodies(model)
        self.assertTrue(bodies["LeafA"] and bodies["LeafB"])
        self.assertFalse(bodies["GeometryAttachment_5"])          # the static frame shape's wrapper: no body
        tracks = {"Open": {"LeafA", "LeafB"}, "Close": {"LeafA", "LeafB"}}
        rows = panels.assess(panels.source_parts(source), "native", tracks, bodies)
        self.assertEqual([r["status"] for r in rows], ["moves", "moves"])
        rows = panels.assess(panels.source_parts(source), "native", {"Open": {"LeafA", "LeafB"}, "Close": {"LeafA"}}, bodies)
        self.assertEqual([r["status"] for r in rows], ["moves", "missing a clip"])
        rows = panels.assess(panels.source_parts(source), "native", tracks, {"LeafA": True})
        self.assertEqual([r["status"] for r in rows], ["moves", "no body"])


class DoorBodiesNativeTests(unittest.TestCase):
    def test_each_animated_leaf_needs_its_own_moving_body(self):
        _, model, door = native_model()
        report = bodies_oracle.audit(model, door["animated_bones"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["moving_bodies"], 2)
        f = nif.parse(model)
        last = max(i for i in range(len(f.blocks)) if f.type_of(i) == "bhkNPCollisionObject")   # LeafB's body
        data = bytearray(f.blocks[last])
        struct.pack_into("<i", data, 0, 0)                    # moved onto the model root: LeafB has none left
        f.blocks[last] = bytes(data)
        report = bodies_oracle.audit(nif.serialize(f), door["animated_bones"])
        self.assertIn("animated part LeafB has geometry but no moving body", report["errors"])
        self.assertTrue(bodies_oracle.audit(model, ["Missing"])["errors"])

    def test_template_doors_are_audited_as_before(self):
        data = nif.serialize(sfnif.build_door_nif(b"Door", [], [], leaf_collision=fake_template()))
        self.assertEqual(bodies_oracle.audit(data)["moving_bodies"], 1)


if __name__ == "__main__":
    unittest.main()
