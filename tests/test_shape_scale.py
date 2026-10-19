"""Reject non-finite or non-positive shape scales early."""
import unittest
from types import SimpleNamespace

from fo4sf import convert_static, nif as nifmod


def _shape(scale=1.0):
    return SimpleNamespace(
        positions=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
        triangles=[(0, 1, 2)],
        rotation=(1, 0, 0, 0, 1, 0, 0, 0, 1),
        translation=(0, 0, 0),
        scale=scale,
        uvs=[],
        normals=[],
        tangents=[],
        colors=[],
        skinned=False,
    )


class ShapeScaleTests(unittest.TestCase):
    def test_rejects_zero_negative_nan(self):
        for bad in (0.0, -1.0, float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(nifmod.NifError):
                convert_static.shape_to_mesh(_shape(bad))

    def test_accepts_positive_finite(self):
        m = convert_static.shape_to_mesh(_shape(2.5))
        self.assertEqual(len(m.positions), 3)


if __name__ == "__main__":
    unittest.main()
