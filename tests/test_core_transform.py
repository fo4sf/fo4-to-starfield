"""The Transform adapter (docs/ai/leader-core.md section 9): the core's one ref_matrix in the Z-first order of PR
#102, its parity with the two Python copies (routes.py: equal everywhere; exterior.py: equal on heading-only
rotations, different on tilted ones), and the matrix properties. Pure arithmetic; no game, no files."""
import itertools
import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))

from fo4sf.core.adapters import transform as tf  # noqa: E402
from fo4sf import exterior  # noqa: E402  (the X-first copy, numpy-backed module; the adapter itself needs no numpy)
import routes  # noqa: E402  (the Z-first copy)

ROCK = (0.0312, -0.2123, 3.1979)      # RockCliff05 18BCCC, the northeast probe of PR #102 (a 12 degree tilt)
ANGLES = (-2.5, -1.0, -0.3, 0.0, 0.0312, 0.7, math.pi / 2, 3.1979)
GRID = list(itertools.product(ANGLES, repeat=3))


def close(a, b, tol=1e-12):
    return max(abs(x - y) for x, y in zip(a, b)) <= tol


class ParityTests(unittest.TestCase):
    def test_equals_routes_ref_matrix_on_every_rotation(self):
        for rot in GRID + [ROCK]:
            self.assertTrue(close(tf.ref_matrix(rot), routes.ref_matrix(rot)), rot)

    def test_equals_exterior_ref_matrix_on_heading_only_rotations(self):
        for z in ANGLES:
            self.assertTrue(close(tf.ref_matrix((0.0, 0.0, z)), exterior.ref_matrix((0.0, 0.0, z))), z)
        # and exterior.to_world agrees there too (same unit, metres)
        self.assertTrue(close(tf.to_world((1.0, 2.0, 3.0), (10.0, 20.0, 30.0), (0.0, 0.0, 1.2), 2.0),
                              exterior.to_world((1.0, 2.0, 3.0), (10.0, 20.0, 30.0), (0.0, 0.0, 1.2), 2.0)))

    def test_differs_from_exterior_on_tilted_rotations_by_the_documented_amount(self):
        a, e = tf.ref_matrix(ROCK), exterior.ref_matrix(ROCK)
        self.assertGreater(max(abs(x - y) for x, y in zip(a, e)), 0.4)
        top = (0.0, 0.0, 24.0)                                        # the rock's top under each order
        self.assertGreater(math.dist(tf.apply(a, top), tf.apply(e, top)), 10.0)
        # the orders only differ when x or y is set: every single-axis rotation agrees (the familiar heading case)
        for ang in ANGLES:
            for rot in ((ang, 0.0, 0.0), (0.0, ang, 0.0), (0.0, 0.0, ang)):
                self.assertTrue(close(tf.ref_matrix(rot), exterior.ref_matrix(rot), 1e-12), rot)
        tilted = [rot for rot in GRID if (rot[0] or rot[1]) and rot[2] and not close(tf.ref_matrix(rot), exterior.ref_matrix(rot), 1e-9)]
        self.assertGreater(len(tilted), 300)                           # most two- and three-axis rotations differ

    def test_the_order_is_z_first(self):
        # R = Rx(-x) Ry(-y) Rz(-z): with only z set the matrix is a plain clockwise heading, and composing the three
        # single-axis matrices in that order reproduces the full one
        x, y, z = ROCK
        rx, ry, rz = tf.ref_matrix((x, 0, 0)), tf.ref_matrix((0, y, 0)), tf.ref_matrix((0, 0, z))
        self.assertTrue(close(tf.ref_matrix(ROCK), tf.matmul(rx, tf.matmul(ry, rz))))
        self.assertFalse(close(tf.ref_matrix(ROCK), tf.matmul(rz, tf.matmul(ry, rx)), 1e-6))   # the X-first order
        self.assertEqual(tf.ROTATION_ORDER, "Z-first")
        heading = tf.ref_matrix((0.0, 0.0, math.pi / 2))               # 90 degrees clockwise seen from +Z
        self.assertTrue(close(tf.apply(heading, (0.0, 1.0, 0.0)), (1.0, 0.0, 0.0), 1e-12))


class MatrixTests(unittest.TestCase):
    def test_orthonormal_with_determinant_one(self):
        for rot in GRID[::7] + [ROCK]:
            m = tf.ref_matrix(rot)
            self.assertTrue(close(tf.matmul(m, tf.transpose(m)), tf.IDENTITY), rot)
            det = (m[0] * (m[4] * m[8] - m[5] * m[7]) - m[1] * (m[3] * m[8] - m[5] * m[6]) + m[2] * (m[3] * m[7] - m[4] * m[6]))
            self.assertAlmostEqual(det, 1.0, places=12, msg=rot)

    def test_local_undoes_world_with_scale_and_offset(self):
        t = tf.Transform((-2189.26, -1553.49, 105.26), ROCK, 2.5)
        for v in ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.3, -4.0, 24.0), (-7.5, 2.25, -1.0)):
            self.assertTrue(close(t.local(t.world(v)), v, 1e-9), v)
        self.assertTrue(close(t.matrix, tf.ref_matrix(ROCK)))
        self.assertTrue(close(t.world((0.0, 0.0, 0.0)), t.pos))
        self.assertTrue(close(tf.to_local(tf.to_world((1.0, 2.0, 3.0), (4.0, 5.0, 6.0), ROCK), (4.0, 5.0, 6.0), ROCK), (1.0, 2.0, 3.0), 1e-9))

    def test_units_and_the_record(self):
        self.assertEqual(tf.metres((70.0, -140.0, 35.0)), (1.0, -2.0, 0.5))
        self.assertEqual(tf.units((1.0, -2.0, 0.5)), (70.0, -140.0, 35.0))
        self.assertEqual(tf.UNITS_PER_METRE, exterior.UNITS_PER_METRE)
        t = tf.Transform.from_units((-153248.2, -108744.3, 7368.2), (0, 0, 1.5), 1)
        self.assertTrue(close(t.pos, exterior.metres((-153248.2, -108744.3, 7368.2))))
        self.assertEqual((t.rot, t.scale), ((0.0, 0.0, 1.5), 1.0))
        with self.assertRaises(ValueError):
            tf.Transform((0, 0), (0, 0, 0))
        for bad in (0, -1, float("nan"), float("inf"), -float("inf"), "big", None):
            with self.assertRaises(ValueError, msg=bad):
                tf.Transform((0, 0, 0), (0, 0, 0), bad)

    def test_the_record_is_frozen_and_hashes_by_value(self):
        t = tf.Transform((1, 2, 3), (0, 0, 1), 2)
        with self.assertRaises(AttributeError):
            t.scale = 3
        with self.assertRaises(AttributeError):
            t.pos = (0, 0, 0)
        same = tf.Transform((1.0, 2.0, 3.0), (0.0, 0.0, 1.0), 2.0)
        self.assertEqual(t, same)
        self.assertEqual(hash(t), hash(same))
        self.assertEqual(len({t, same}), 1)
        self.assertEqual((type(t.pos), type(t.scale)), (tuple, float))

    def test_the_csharp_rotate_offset_is_x_first_as_documented(self):
        # dotnet/PluginSpike/Program.cs RotateOffset, transliterated line by line (the C# copy is not changed here,
        # section 9 documents its cost): it equals exterior.ref_matrix (X first) and differs from the adapter
        def rotate_offset(v, r, scale):
            cx, sx, cy, sy, cz, sz = (math.cos(-r[0]), math.sin(-r[0]), math.cos(-r[1]), math.sin(-r[1]),
                                      math.cos(-r[2]), math.sin(-r[2]))
            x, y, z = (c * scale for c in v)
            y1, z1 = y * cx - z * sx, y * sx + z * cx            # about X
            x2, z2 = x * cy + z1 * sy, -x * sy + z1 * cy          # about Y
            x3, y3 = x2 * cz - y1 * sz, x2 * sz + y1 * cz         # about Z
            return (x3, y3, z2)
        v = (120.0, -35.0, 70.0)
        for rot in GRID + [ROCK]:
            cs = rotate_offset(v, rot, 1.0)
            ext = tuple(float(c) for c in exterior.to_world(v, (0.0, 0.0, 0.0), rot, 1.0))
            self.assertTrue(close(cs, ext, 1e-9), rot)
        tilted = [rot for rot in GRID if rot[0] or rot[1]]
        differs = sum(1 for rot in tilted if not close(rotate_offset(v, rot, 1.0), tf.to_world(v, (0, 0, 0), rot, 1.0), 1e-6))
        self.assertGreater(differs, len(tilted) // 2)
        for rot in [(0, 0, a) for a in ANGLES]:                   # heading-only: all three agree
            self.assertTrue(close(rotate_offset(v, rot, 1.0), tf.to_world(v, (0, 0, 0), rot, 1.0), 1e-9), rot)

    def test_the_adapter_imports_no_numpy(self):
        with open(os.path.join(ROOT, "src", "fo4sf", "core", "adapters", "transform.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("import numpy", src)
        self.assertNotIn("from numpy", src)


if __name__ == "__main__":
    unittest.main()
