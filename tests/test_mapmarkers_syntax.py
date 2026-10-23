"""Regression: map markers staging script must parse on Python 3.10 (CI)."""
import ast
import pathlib
import unittest


class MapMarkersSyntaxTest(unittest.TestCase):
    def test_make_map_markers_parses(self):
        path = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "mapmarkers" / "make_map_markers.py"
        source = path.read_text(encoding="utf-8")
        # Must not raise SyntaxError on 3.10 (f-string backslash was illegal)
        ast.parse(source)
        self.assertIn("lift_desc", source)


if __name__ == "__main__":
    unittest.main()
