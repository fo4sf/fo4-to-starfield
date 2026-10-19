"""Synthetic tests for the triangle limit filter in convert_batch."""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
spec = importlib.util.spec_from_file_location("convert_batch", root / "scripts" / "convert_batch.py")
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


class TriangleCountTests(unittest.TestCase):
    def test_triangle_count_sums_shapes(self):
        class FakeShape:
            def __init__(self, n):
                self.triangles = [()] * n
        class FakeNif:
            pass
        fake_nif = FakeNif()
        # Patch fo4_trishapes to return shapes
        with patch("fo4sf.nif.fo4_trishapes", return_value=[FakeShape(10), FakeShape(5)]):
            with patch("fo4sf.nif.parse", return_value=fake_nif):
                src = Mock()
                src.mesh.return_value = b"fake"
                self.assertEqual(batch.triangle_count(src, "meshes/test.nif"), 15)

    def test_triangle_count_returns_zero_on_error(self):
        src = Mock()
        src.mesh.side_effect = Exception("parse fail")
        self.assertEqual(batch.triangle_count(src, "bad.nif"), 0)


if __name__ == "__main__":
    unittest.main()
