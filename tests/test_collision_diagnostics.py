"""Offline unit tests for collision_diagnostics. No game data."""
import unittest

from fo4sf.collision_diagnostics import report_clamped_halves, has_non_finite


class TestCollisionDiagnostics(unittest.TestCase):
    def test_report_clamped_leaf(self):
        # 0.02 is below MIN_LEAF_HALF 0.05
        clamped = report_clamped_halves([(0.02, 0.5, 0.5)], leaf=True)
        self.assertEqual(len(clamped), 1)
        orig, after = clamped[0]
        self.assertEqual(orig, (0.02, 0.5, 0.5))
        self.assertEqual(after, (0.05, 0.5, 0.5))

    def test_no_clamp_when_above_floor(self):
        clamped = report_clamped_halves([(0.1, 0.1, 0.1)], leaf=True)
        self.assertEqual(clamped, [])

    def test_non_finite(self):
        self.assertTrue(has_non_finite([1.0, float("nan")]))
        self.assertTrue(has_non_finite([float("inf")]))
        self.assertFalse(has_non_finite([0.0, 1.0, -0.5]))


if __name__ == "__main__":
    unittest.main()
