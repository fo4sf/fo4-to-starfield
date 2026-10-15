"""Each fixture is one FO4 NAVM class. The converter is absent, so output is None."""
import unittest

try:
    from fo4sf import navmesh as converter
except ImportError:
    converter = None


def convert(record):
    if converter is None:
        return None
    fn = getattr(converter, "convert", None)
    return None if fn is None else fn(record)


class NavmeshLossTests(unittest.TestCase):
    def test_converter_module_is_absent(self):
        self.assertIsNone(converter)

    def test_one_triangle_mesh_is_dropped(self):
        navm = {
            "vertices": [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
            "triangles": [(0, 1, 2)],
            "edges": [(0, 1), (1, 2), (2, 0)],
        }
        self.assertIsNone(convert(navm))

    def test_one_cover_edge_is_dropped(self):
        navm = {"cover": [{"edge": (0, 1), "left": 1.2, "right": 0.0, "flags": 1}]}
        self.assertIsNone(convert(navm))

    def test_one_ledge_link_is_dropped(self):
        navm = {"ledge_links": [{"from_tri": 0, "to_tri": 1, "kind": "drop"}]}
        self.assertIsNone(convert(navm))

    def test_one_door_link_is_dropped(self):
        navm = {"door_links": [{"tri": 0, "door": 0x00012ABC}]}
        self.assertIsNone(convert(navm))

    def test_one_nvmi_traversal_row_is_dropped(self):
        navm = {"nvmi": [{"from_mesh": 1, "to_mesh": 2, "tri": 0}]}
        self.assertIsNone(convert(navm))

    def test_one_cell_cut_portal_is_dropped(self):
        navm = {"cell_cuts": [{"edge": (0, 1)}], "portals": [{"to_cell": 0x0000ABCD, "edge": (0, 1)}]}
        self.assertIsNone(convert(navm))
