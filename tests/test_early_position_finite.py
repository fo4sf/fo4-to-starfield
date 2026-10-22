"""Offline check that empty or non-finite shape positions are rejected before transform."""
import math
import unittest
from fo4sf import convert_static, nif as nifmod

def make_shape(positions):
    return nifmod.Fo4Shape(
        name=b"test",
        translation=(0.0, 0.0, 0.0),
        rotation=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
        scale=1.0,
        shader_ref=-1,
        alpha_ref=-1,
        skin_ref=-1,
        positions=positions,
        uvs=[],
        normals=[],
        tangents=[],
        colors=[],
        triangles=[],
        skinned=False,
    )

class EarlyPositionFiniteTest(unittest.TestCase):
    def test_rejects_empty_positions(self):
        shape = make_shape([])
        with self.assertRaises(nifmod.NifError) as cm:
            convert_static.shape_to_mesh(shape)
        self.assertIn("empty or non-finite", str(cm.exception))

    def test_rejects_nan_position(self):
        shape = make_shape([(0.0, 0.0, math.nan)])
        with self.assertRaises(nifmod.NifError) as cm:
            convert_static.shape_to_mesh(shape)
        self.assertIn("empty or non-finite", str(cm.exception))

if __name__ == "__main__":
    unittest.main()
