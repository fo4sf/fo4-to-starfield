"""One tiny FO4 NAVM per class. convert() keeps geometry; cover/ledges/traversals drop."""
import os
import struct
import sys
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf import navmesh as nm  # noqa: E402

FOUND = nm.F_FOUND


def fo4(fid, verts, tris, links=(), doors=(), cover=()):
    out = [struct.pack("<III", 15, nm.MAGIC, 0x3C), struct.pack("<hh", 0, 0)]
    out.append(struct.pack("<I", len(verts)) + np.asarray(verts, "<f4").reshape(-1, 3).tobytes())
    t = np.zeros(len(tris), nm.TRI_DTYPE)
    for i, (v, e, h, fl) in enumerate(tris):
        t[i] = (v, e, h, 0, fl, 0)
    out.append(struct.pack("<I", len(t)) + t.tobytes())
    li = np.zeros(len(links), nm.LINK_DTYPE)
    for i, x in enumerate(links):
        li[i] = x
    out.append(struct.pack("<I", len(li)) + li.tobytes())
    d = np.zeros(len(doors), nm.DOOR_DTYPE)
    for i, x in enumerate(doors):
        d[i] = x
    out.append(struct.pack("<I", len(d)) + d.tobytes())
    out.append(struct.pack("<I", len(cover)) + b"".join(cover))
    out.append(struct.pack("<I", 0))
    out.append(struct.pack("<I", 0))
    v = np.asarray(verts, np.float64).reshape(-1, 3)
    out.append(struct.pack("<I8f", 1, 1.0, 1.0, *v.min(0), *v.max(0)))
    out.append(struct.pack(f"<I{len(tris)}h", len(tris), *range(len(tris))))
    return fid, nm.parse(b"".join(out))


def tri():
    return [(0.0, 0.0, 0.0), (70.0, 0.0, 0.0), (0.0, 70.0, 0.0)], [
        ((0, 1, 2), (-1, -1, -1), 3.4e38, FOUND)
    ]


class NavmeshLossTests(unittest.TestCase):
    def test_converter_module_is_present(self):
        self.assertIsNotNone(nm.convert)

    def test_one_triangle_mesh_is_retained(self):
        # in: vertices + one triangle + three edges
        pieces, rep = nm.convert([fo4(0xA, *tri())])
        self.assertEqual((rep["fo4_triangles"], rep["triangles"], len(pieces)), (1, 1, 1))
        self.assertEqual(len(pieces[0].tris), 1)

    def test_one_cover_edge_is_dropped(self):
        # in: {"cover": [{"edge": (0, 1), "left": 1.2, "right": 0.0, "flags": 1}]}
        fid, m = fo4(0xA, *tri(), cover=[b"\x01" * 8])
        m.triangles["cover"][0] = 1
        pieces, rep = nm.convert([(fid, m)])
        self.assertEqual(rep["dropped"]["cover_entries"], 1)
        self.assertEqual(rep["dropped"]["cover_flag_triangles"], 1)
        out = nm.piece_nvnm(pieces[0], 0x3C, [0x100])
        self.assertEqual(out.cover, [])
        self.assertEqual(int(out.triangles["cover"][0]), 0)

    def test_one_ledge_link_is_dropped(self):
        # in: {"ledge_links": [{"from_tri": 0, "to_tri": 1, "kind": "drop"}]}
        verts, _ = tri()
        verts = verts + [(70.0, 70.0, 0.0)]
        tris = [
            ((0, 1, 2), (0, -1, 1), 3.4e38, FOUND | nm.EDGE_LINK_BITS[0]),
            ((0, 2, 3), (0, -1, -1), 3.4e38, FOUND),
        ]
        pieces, rep = nm.convert([fo4(0xA, verts, tris, links=[(2, 0xA, 1, 0)])])
        self.assertEqual(rep["dropped"]["fo4_links_ledge_type1_2"], 1)
        self.assertEqual(rep["links"], {"cell_line": 0, "fo4_portal": 0})
        self.assertEqual(nm.piece_nvnm(pieces[0], 0x3C, [0x100]).links.shape[0], 0)

    def test_one_door_link_is_dropped(self):
        # in: {"door_links": [{"tri": 0, "door": 0x00012ABC}]}
        pieces, rep = nm.convert([fo4(0xA, *tri(), doors=[(0, nm.DOOR_EXTRA, 0x12ABC)])])
        self.assertEqual(rep["dropped"]["doors_not_converted"], 1)
        self.assertEqual(rep["kept"]["doors"], 0)
        self.assertEqual(pieces[0].doors, [])

    def test_one_nvmi_traversal_row_is_dropped(self):
        # in: {"nvmi": [{"from_mesh": 1, "to_mesh": 2, "tri": 0}]} — convert() never reads FO4 NVMI
        pieces, _ = nm.convert([fo4(0xA, *tri())])
        info = nm.piece_nvmi(pieces[0], 0x100, 0x3C, [0x100])
        self.assertEqual(info.traversals, [])
        self.assertIsNone(info.outline)

    def test_one_cell_cut_portal_is_retained(self):
        # in: {"cell_cuts": [{"edge": (0, 1)}], "portals": [{"to_cell": 0xABCD, "edge": (0, 1)}]}
        verts = [(-70.0, 0.0, 0.0), (70.0, 0.0, 0.0), (70.0, 70.0, 0.0), (-70.0, 70.0, 0.0)]
        tris = [
            ((0, 1, 2), (-1, -1, 1), 3.4e38, FOUND),
            ((0, 2, 3), (0, -1, -1), 3.4e38, FOUND),
        ]
        pieces, rep = nm.convert([fo4(0xA, verts, tris)])
        self.assertGreaterEqual(rep["links"]["cell_line"], 1)
        self.assertEqual(len(pieces), 2)
