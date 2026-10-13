"""The game places a reference by replacing its model's scene-root transform, so a rotation stored on the FO4 NIF root
is not applied in game (checked against FO4's precombined physics, docs/ai/research-log.md 2026-10-10). Conversion must
place geometry, collision nodes and door pivots the same way. Synthetic NIFs only."""
import os
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fo4sf import convert_static, meshcollision, nif, sfmesh  # noqa: E402
from test_review_fixes import av_fields, trishape_block  # noqa: E402

IDENTITY = (1, 0, 0, 0, 1, 0, 0, 0, 1)
ROT_Z180 = (-1, 0, 0, 0, -1, 0, 0, 0, 1)
ROT_X60 = (1, 0, 0, 0, 0.5, -0.8660254, 0, 0.8660254, 0.5)       # a stair helper node's tilt


def rooted_nif(root_rot=ROT_Z180, child_t=(0, 70, 0), child_rot=IDENTITY, collision=False):
    """root NiNode (rotated) -> child NiNode (translated) -> BSTriShape [-> bhkNPCollisionObject on the child]."""
    f = nif.NifFile(bs_version=130, author=b"t\x00", process_script=b"\x00", export_script=b"\x00", max_filepath=b"\x00")
    f.string_index(b"Shape")
    f.add_block("NiNode", av_fields(0, (0, 0, 0), root_rot, 1.0) + struct.pack("<Ii", 1, 1))
    f.add_block("NiNode", av_fields(0, child_t, child_rot, 1.0) + struct.pack("<Ii", 1, 2))
    f.add_block("BSTriShape", trishape_block([(0, 0, 0), (70, 0, 0), (0, 70, 0)], [(0, 1, 2)]))
    if collision:
        f.add_block("bhkNPCollisionObject", struct.pack("<iHiI", 1, 0x80, 4, 0))
        f.add_block("bhkPhysicsSystem", struct.pack("<I", 4) + b"test")
    f.footer = struct.pack("<II", 1, 0)
    return nif.serialize(f)


def close(test, actual, expected, places=4):
    test.assertEqual(len(actual), len(expected))
    for a, e in zip(actual, expected):
        test.assertAlmostEqual(a, e, places=places)


class PlacedWorldTransformTests(unittest.TestCase):
    def test_placed_transform_leaves_out_the_scene_root(self):
        f = nif.parse(rooted_nif())
        default = nif.world_transforms(f)(1)
        placed = nif.world_transforms(f, placed=True)(1)
        close(self, default[0], (0, -70, 0))                  # the file's own composition: root turns the child
        close(self, default[1], ROT_Z180)
        close(self, placed[0], (0, 70, 0))                    # as placed in game: the child's own transform only
        close(self, placed[1], IDENTITY)
        close(self, nif.world_transforms(f, placed=True)(0)[1], IDENTITY)

    def test_shapes_and_converted_geometry_are_placed_without_the_root(self):
        raw = rooted_nif()
        s = nif.fo4_trishapes(nif.parse(raw), placed=True)[0]
        close(self, s.translation, (0, 70, 0))
        close(self, s.rotation, IDENTITY)
        files = convert_static.convert_static(raw, "test/rooted")
        mesh = sfmesh.parse(next(v for k, v in files.items() if k.endswith(".mesh")))
        pts = sorted(tuple(round(c, 3) for c in sfmesh.decode_position(p, mesh.scale)) for p in mesh.positions)
        # vertices (0,0,0), (1 m,0,0), (0,1 m,0) moved 1 m along +y; with the root applied they would be at y <= -1
        self.assertEqual(pts, [(0.0, 1.0, 0.0), (0.0, 2.0, 0.0), (1.0, 1.0, 0.0)])

    def test_native_collision_node_is_placed_without_the_root(self):
        src = nif.parse(rooted_nif(child_t=(0, 121.65, -0.6), child_rot=ROT_X60, collision=True))
        report = {}
        with patch.object(meshcollision, "convert_bodies", return_value=[b"body"]) as convert:
            blobs = convert_static.fo4_native_collision(src, b"template", report)
        self.assertEqual(len(blobs), 1)
        blob, translation, rotation = blobs[0]
        self.assertEqual(blob, b"body")
        close(self, translation, (0, 121.65 / 70, -0.6 / 70))      # the helper stays on its own side of the model
        close(self, rotation, ROT_X60)
        close(self, convert.call_args.kwargs["node_rot"], ROT_X60)  # helper slope measured in the placed orientation
        self.assertEqual(report["source"], "fo4-native")

    def test_door_pivot_is_placed_without_the_root(self):
        from test_door_motion import fixture                     # root translated 70 units, LeafA animated first
        f = fixture()
        node, pivot = nif.door_hinge(f, placed=True)
        self.assertEqual(node, nif.door_hinge(f)[0])
        close(self, pivot, (0, 0, 0))
        close(self, nif.door_hinge(f)[1], (70, 0, 0))             # default: the file's own composition, unchanged


if __name__ == "__main__":
    unittest.main()
