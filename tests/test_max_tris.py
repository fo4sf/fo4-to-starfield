"""Tests for --max-tris filtering in convert_batch."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
spec = importlib.util.spec_from_file_location("convert_batch", root / "scripts" / "convert_batch.py")
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


class MaxTrisTests(unittest.TestCase):
    def test_triangle_count_sums_shapes(self):
        # Synthetic NIF-like: mock parse to return shapes with known triangle counts
        mock_src = Mock()
        mock_src.mesh.return_value = b"fake"
        with unittest.mock.patch.object(batch.nif, "parse") as mock_parse, \
             unittest.mock.patch.object(batch.nif, "fo4_trishapes") as mock_shapes:
            shape1 = Mock(triangles=[(0,1,2)] * 100)
            shape2 = Mock(triangles=[(0,1,2)] * 50)
            mock_shapes.return_value = [shape1, shape2]
            mock_parse.return_value = Mock()
            self.assertEqual(batch.triangle_count(mock_src, "test.nif"), 150)

    def test_triangle_count_returns_zero_on_error(self):
        mock_src = Mock()
        mock_src.mesh.side_effect = Exception("bad")
        self.assertEqual(batch.triangle_count(mock_src, "bad.nif"), 0)


if __name__ == "__main__":
    unittest.main()
