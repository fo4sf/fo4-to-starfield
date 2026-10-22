"""Tests for finite position validation in convert_static.shape_to_mesh."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import convert_static, nif as nifmod


class FinitePositionTests(unittest.TestCase):
    def test_nonfinite_positions_raise(self):
        class FakeShape:
            positions = [(float("nan"), 0.0, 0.0)]
            rotation = (1, 0, 0, 0, 1, 0, 0, 0, 1)
            scale = 1.0
            translation = (0.0, 0.0, 0.0)
            triangles = []
            uvs = []
            normals = []
            tangents = []
            colors = []

        with self.assertRaises(nifmod.NifError) as ctx:
            convert_static.shape_to_mesh(FakeShape())
        self.assertIn("non-finite value after transform", str(ctx.exception))
        self.assertIn("nan", str(ctx.exception).lower())

    def test_empty_positions_raise(self):
        class FakeShape:
            positions = []
            rotation = (1, 0, 0, 0, 1, 0, 0, 0, 1)
            scale = 1.0
            translation = (0.0, 0.0, 0.0)
            triangles = []
            uvs = []
            normals = []
            tangents = []
            colors = []

        with self.assertRaises(nifmod.NifError):
            convert_static.shape_to_mesh(FakeShape())


if __name__ == "__main__":
    unittest.main()
