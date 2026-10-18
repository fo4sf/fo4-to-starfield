"""src/fo4sf/navmesh.py on synthetic navmeshes: both NVNM layouts, the search grid, NVMI, the conversion of Fallout 4
navmeshes into Starfield's 100 m cells (cell lines, corners, portals, ledges, doors, waypoints) and the validator.
No game data."""
import math
import os
import struct
import sys
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
from fo4sf import navmesh as nm  # noqa: E402

FOUND = nm.F_FOUND


def fo4_bytes(world, grid, verts, tris, links=(), doors=(), cover=(), wps=(), lists=None, version=15):
    """A Fallout 4 (v15) NVNM: 12 B vertices in game units, 8 B cover entries, no trailer."""
    out = [struct.pack("<III", version, nm.MAGIC, world), struct.pack("<hh", grid[1], grid[0])]
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
    w = np.zeros(len(wps), nm.WAYPOINT_DTYPE)
    for i, x in enumerate(wps):
        w[i] = x
    out.append(struct.pack("<I", len(w)) + w.tobytes())
    lists = lists if lists is not None else [list(range(len(tris)))]
    v = np.asarray(verts, np.float64).reshape(-1, 3)
    out.append(struct.pack("<I8f", 1, 1.0, 1.0, *v.min(0), *v.max(0)))
    for lst in lists:
        out.append(struct.pack(f"<I{len(lst)}h", len(lst), *lst))
    return b"".join(out)


def square(x0, y0, x1, y1, z=0.0):
    """Two triangles over a rectangle (game units), counter-clockwise, sharing the diagonal 0-2."""
    verts = [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]
    tris = [((0, 1, 2), (-1, -1, 1), 3.4028235e38, FOUND), ((0, 2, 3), (0, -1, -1), 3.4028235e38, FOUND)]
    return verts, tris


def area(pc):
    return sum(nm._tri_area(pc, i) for i in range(len(pc.tris)))


def sf_set(pieces, base=0x01000800, world=0x01000802):
    fids = [base + i for i in range(len(pieces))]
    navs = {fids[i]: nm.parse(nm.write_sf(nm.piece_nvnm(p, world, fids))) for i, p in enumerate(pieces)}
    infos = {fids[i]: nm.parse_nvmi(nm.write_nvmi(nm.piece_nvmi(p, fids[i], world, fids))) for i, p in enumerate(pieces)}
    return fids, navs, infos


class LayoutTests(unittest.TestCase):
    def test_fo4_layout_and_exact_end(self):
        verts, tris = square(0, 0, 700, 700, 70)
        b = fo4_bytes(0x3C, (-17, 19), verts, tris, cover=[b"\1" * 8, b"\2" * 8],
                      wps=[((350, 350, 70), 0, 0)])
        m = nm.parse(b)
        self.assertEqual((m.version, m.world, m.grid, m.cell), (15, 0x3C, (-17, 19), None))
        self.assertEqual(m.vertices.shape, (4, 3))
        self.assertEqual(len(m.cover[0]), 8)
        self.assertEqual(m.trailer, b"")
        self.assertFalse(m.starfield)
        with self.assertRaises(nm.NavmeshError):            # one byte too many: the layout is wrong
            nm.parse(b + b"\0")
        with self.assertRaises(nm.NavmeshError):            # a vertex index past the vertex list
            bad = list(tris)
            bad[0] = ((0, 1, 9), (-1, -1, 1), 1.0, FOUND)
            nm.parse(fo4_bytes(0x3C, (0, 0), verts, bad))

    def test_flags_follow_the_extra_byte(self):
        # triangle: 3 i16 vertices, 3 i16 edges, f32 height, u8 extra, u16 flags, u16 cover (the order whose edge-link
        # bits agree with the edge values in every FO4 and Starfield record checked)
        t = np.zeros(1, nm.TRI_DTYPE)
        t[0] = ((0, 1, 2), (0, -1, -1), 2.5, 7, 0x0801, 0x4002)
        raw = t.tobytes()
        self.assertEqual(raw[16], 7)
        self.assertEqual(struct.unpack_from("<HH", raw, 17), (0x0801, 0x4002))

    def test_starfield_round_trip(self):
        v = np.array([[0, 0, 1], [2, 0, 1], [2, 2, 1], [0, 2, 1]], np.float64)
        t = np.zeros(2, nm.TRI_DTYPE)
        t[0] = ((0, 1, 2), (0, -1, 1), 1.8, 0, nm.EDGE_LINK_BITS[0] | FOUND, 0)
        t[1] = ((0, 2, 3), (0, -1, -1), nm.FLT_MAX, 0, FOUND | nm.F_DOOR, 0)
        links = np.zeros(1, nm.LINK_DTYPE)
        links[0] = (0, 0x01000801, 5, 2)
        doors = np.zeros(1, nm.DOOR_DTYPE)
        doors[0] = (1, nm.DOOR_EXTRA, 0x01001234)
        wps = np.zeros(1, nm.WAYPOINT_DTYPE)
        wps[0] = ((1, 1.5, 1), 1, 0)
        d, size, gmin, gmax, lists = nm.build_grid(v, t)
        m = nm.Nvnm(17, nm.MAGIC, 0x01000802, (-10, 11), None, v, np.array([1, 1, 0, 1], np.int32), t, links, doors,
                    [b"\0" * 12], np.zeros(0, nm.COVERMAP_DTYPE), wps, d, size, gmin, gmax, lists, nm.SF_TRAILER)
        b = nm.write_sf(m)
        back = nm.parse(b)
        self.assertEqual(nm.write_sf(back), b)
        self.assertEqual((back.grid, back.world, back.trailer), ((-10, 11), 0x01000802, nm.SF_TRAILER))
        self.assertEqual(struct.unpack_from("<hh", b, 12), (11, -10))      # grid y first, then x
        self.assertEqual(back.vertex_extra.tolist(), [1, 1, 0, 1])
        self.assertEqual(int(back.links[0]["navmesh"]), 0x01000801)
        with self.assertRaises(nm.NavmeshError):
            nm.write_sf(nm.Nvnm(**dict(m.__dict__, cover=[b"\0" * 8])))  # FO4-size cover in a Starfield record


class GridTests(unittest.TestCase):
    def test_divisor_rule(self):
        self.assertEqual([nm.grid_divisor(n) for n in (1, 16, 17, 49, 50, 99, 100, 499, 500, 5000)],
                         [1, 1, 2, 2, 3, 3, 4, 11, 12, 12])

    def test_grid_bounds_lists_and_raw(self):
        v = np.array([[0, 0, 0], [10, 0, 0], [10, 10, 2], [0, 10, 2]], np.float64)
        t = np.zeros(2, nm.TRI_DTYPE)
        t[0] = ((0, 1, 2), (-1, -1, 1), 1.8, 0, 0, 0)
        t[1] = ((0, 2, 3), (0, -1, -1), 1.8, 0, 0, 0)
        d, size, gmin, gmax, lists = nm.build_grid(v, t)
        self.assertEqual((d, size, gmin), (1, (10.0, 10.0), (0.0, 0.0, 0.0)))
        self.assertAlmostEqual(gmax[2], 3.8, places=5)                     # highest vertex + the triangle's height
        self.assertEqual(lists, [[0, 1]])
        t["height"] = nm.FLT_MAX                                           # no ceiling: FLT_MAX stays FLT_MAX
        self.assertEqual(nm.build_grid(v, t)[3][2], nm.FLT_MAX)
        # 17 triangles: 2 x 2 grid, y-major, each triangle in the cells its shape touches
        rng = np.random.default_rng(1)
        pts = rng.uniform(0, 20, (30, 2))
        vv = np.c_[pts, np.zeros(30)]
        tt = np.zeros(17, nm.TRI_DTYPE)
        for i in range(17):
            tt[i]["v"] = (i, i + 1, i + 2)
        d, size, gmin, gmax, lists = nm.build_grid(vv, tt)
        self.assertEqual(d, 2)
        for r in range(2):
            for c in range(2):
                x0, y0 = gmin[0] + c * size[0], gmin[1] + r * size[1]
                for i in range(17):
                    p = vv[tt["v"][i]][:, :2]
                    cen = p.mean(0)
                    if x0 < cen[0] < x0 + size[0] and y0 < cen[1] < y0 + size[1]:
                        self.assertIn(i, lists[r * 2 + c])
        self.assertEqual(nm.grid_raw([[5, 6], []]), [2, 0, 5, 6, 0, 0])
        self.assertEqual(nm.grid_raw([[1]], nm.SF_TRAILER), [1, 0, 1, 12, 8])


class NvmiTests(unittest.TestCase):
    def test_round_trip_and_parts(self):
        e = nm.Nvmi(0x01000900, 0, (1.0, 2.0, 3.0), 0.0, [0x01000901, 0x01000902], [], [(nm.DOOR_EXTRA, 0x01001234)],
                    [], None, 0x01000802, (-10, 11), None, nm.BORDER_W | nm.BORDER_N)
        b = nm.write_nvmi(e)
        back = nm.parse_nvmi(b)
        self.assertEqual((back.merged, back.doors, back.grid, back.border, back.outline), (e.merged, e.doors, (-10, 11), 12, None))
        # what TerrainExp2 hands Mutagen: Data (20 B) and Unknown (22 B) around the typed lists
        self.assertEqual(b[4:24], nm.nvmi_data((1.0, 2.0, 3.0)))
        self.assertEqual(b[-22:], nm.nvmi_unknown(0x01000802, (-10, 11), 12))
        with self.assertRaises(nm.NavmeshError):
            nm.parse_nvmi(b + b"\0")
        broken = bytearray(b)
        broken[-17] ^= 0xFF                                  # inside the CRC field
        with self.assertRaises(nm.NavmeshError):
            nm.parse_nvmi(bytes(broken))

    def test_outline_and_traversals_parse(self):
        it = np.array([[0, 1, 2]], np.int16)
        iv = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], np.float32)
        e = nm.Nvmi(5, nm.NVMI_OUTLINE, (0, 0, 0), 0.0, [], [6], [], [b"\x07" * 60], ((0, 0, 0, 1, 1, 0), it, iv),
                    0, None, 0x1234, 0)
        back = nm.parse_nvmi(nm.write_nvmi(e))
        self.assertEqual((back.cell, back.preferred, len(back.traversals)), (0x1234, [6], 1))
        self.assertEqual(back.outline[1].tolist(), [[0, 1, 2]])

    def test_border_bits(self):
        self.assertEqual(nm.border_bits((-1000, 1100, 0), (-900, 1200, 0), (-10, 11)), 15)
        self.assertEqual(nm.border_bits((-1000, 1150, 0), (-950, 1160, 0), (-10, 11)), nm.BORDER_W)
        self.assertEqual(nm.border_bits((-950, 1100, 0), (-900, 1120, 0), (-10, 11)), nm.BORDER_S | nm.BORDER_E)


class ConvertTests(unittest.TestCase):
    def fo4(self, fid, verts, tris, **kw):
        return fid, nm.parse(fo4_bytes(0x3C, (0, 0), verts, tris, **kw))

    def test_cell_line_cut_keeps_area_and_links_exactly(self):
        # 20 x 10 m (1400 x 700 units) across x = 0: two pieces, linked edge for edge
        nav = self.fo4(0x100, *square(-700, 100, 700, 800, 70.0))
        pieces, rep = nm.convert([nav])
        self.assertEqual(sorted(p.cell for p in pieces), [(-1, 0), (0, 0)])
        self.assertAlmostEqual(sum(area(p) for p in pieces), 200.0, places=6)
        self.assertEqual(rep["links"]["cell_line"], 2)                # both triangles cross the line
        for p in pieces:
            xs = [q[0] for q in p.pos]
            self.assertTrue(all(-100 - 1e-9 <= x <= 0 + 1e-9 for x in xs) if p.cell == (-1, 0)
                            else all(0 - 1e-9 <= x <= 100 for x in xs))
            self.assertTrue(all(abs(q[2] - 1.0) < 1e-12 for q in p.pos))   # 70 units = 1 m
        fids, navs, infos = sf_set(pieces)
        st = nm.validate(navs, infos, 0x01000802)
        self.assertEqual(st["errors"], [])
        self.assertEqual(st["links"], st["links_symmetric"])
        self.assertEqual(st["link_gap_max_m"], 0.0)
        for f in fids:                                              # NVMI merged-to: the other piece
            self.assertEqual(infos[f].merged, [g for g in fids if g != f])
        self.assertEqual(infos[fids[0]].border | infos[fids[1]].border, nm.BORDER_E | nm.BORDER_W)

    def test_corner_four_pieces_share_the_corner(self):
        # one triangle over the cell corner (0, 0): four pieces, links across both lines, the corner point identical
        verts = [(-1400, -1400, 0), (1400, -1400, 0), (0, 1400, 0)]
        tris = [((0, 1, 2), (-1, -1, -1), 3.4e38, FOUND)]
        pieces, rep = nm.convert([self.fo4(0x200, verts, tris)])
        self.assertEqual(sorted(p.cell for p in pieces), [(-1, -1), (-1, 0), (0, -1), (0, 0)])
        corners = [k for p in pieces for k in p.keys if k[0] == "c"]
        self.assertEqual(len(corners), 4)
        self.assertEqual(len(set(corners)), 1)
        self.assertAlmostEqual(sum(area(p) for p in pieces), 0.5 * 40 * 40, places=6)
        _fids, navs, infos = sf_set(pieces)
        st = nm.validate(navs, infos)
        self.assertEqual(st["errors"], [])
        self.assertEqual(st["link_gap_max_m"], 0.0)

    def test_shared_edge_cut_points_are_identical(self):
        # two triangles sharing an edge that crosses the line: the cut point is one key in both, so the triangles stay
        # neighbours inside each piece (no T-junction, no gap)
        verts = [(-700, 0, 0), (700, 70, 0), (700, 700, 140), (-700, 630, 0)]
        tris = [((0, 1, 2), (-1, -1, 1), 3.4e38, FOUND), ((0, 2, 3), (0, -1, -1), 3.4e38, FOUND)]
        pieces, _ = nm.convert([self.fo4(0x300, verts, tris)])
        for p in pieces:
            inner = sum(1 for t in p.neighbours for e in t if isinstance(e, int) and e >= 0)
            self.assertGreaterEqual(inner, 2)
        _fids, navs, _ = sf_set(pieces)
        self.assertEqual(nm.validate(navs)["errors"], [])

    def test_vertex_on_the_line_makes_no_sliver(self):
        verts = [(0, 0, 0), (700, 0, 0), (0, 700, 0), (-700, 0, 0)]
        tris = [((0, 1, 2), (-1, -1, 1), 3.4e38, FOUND), ((0, 2, 3), (0, -1, -1), 3.4e38, FOUND)]
        pieces, rep = nm.convert([self.fo4(0x400, verts, tris)])
        self.assertEqual(rep["sliver_triangles_dropped"], 0)
        self.assertEqual(sorted(len(p.tris) for p in pieces), [1, 1])
        _fids, navs, _ = sf_set(pieces)
        st = nm.validate(navs)
        self.assertEqual(st["errors"], [])
        self.assertEqual(st["links"], 2)                            # the diagonal on x = 0 links the two pieces

    def test_portals_ledges_outside_links_doors_waypoints(self):
        # navmesh A (x 700..1400) and B (x 1400..2100), one cell; A's edge on x = 1400 is a type-0 portal to B,
        # plus a type-1 ledge link to itself and a link to a navmesh that is not converted
        av, at = square(700, 700, 1400, 1400)
        bv, bt = square(1400, 700, 2100, 1400)
        at = [((0, 1, 2), (-1, 0, 1), 170.0, FOUND | nm.EDGE_LINK_BITS[1]),
              ((0, 2, 3), (0, 1, 2), 3.4e38, FOUND | nm.EDGE_LINK_BITS[1] | nm.EDGE_LINK_BITS[2] | nm.F_WATER)]
        a_links = [(0, 0xB, 1, 2), (1, 0xA, 0, 0), (0, 0xDEAD, 0, 0)]
        # B: edge 2-0 of B's triangle 1 (vertex 3 -> 0: x = 1400) links back to A's triangle 0, edge 1
        bt = [((0, 1, 2), (-1, -1, 1), 3.4e38, FOUND), ((0, 2, 3), (0, -1, 0), 3.4e38, FOUND | nm.EDGE_LINK_BITS[2])]
        b_links = [(0, 0xA, 0, 1)]
        A = self.fo4(0xA, av, at, links=a_links, doors=[(0, nm.DOOR_EXTRA, 0x77), (1, nm.DOOR_EXTRA, 0x99)],
                     wps=[((900, 1000, 0), 0, 0), ((5000, 5000, 0), 0, 0)])
        B = self.fo4(0xB, bv, bt, links=b_links)
        pieces, rep = nm.convert([A, B], door_refs={0x77: "000077:Fallout4.esm"})
        self.assertEqual(rep["links"], {"cell_line": 0, "fo4_portal": 1})
        self.assertEqual(rep["dropped"]["fo4_links_ledge_type1_2"], 1)
        self.assertEqual(rep["dropped"]["fo4_links_outside"], 1)
        self.assertEqual(rep["dropped"]["water_flag_triangles"], 1)
        self.assertEqual(rep["dropped"]["doors_not_converted"], 1)
        self.assertEqual((rep["kept"]["doors"], rep["kept"]["waypoints"], rep["dropped"]["waypoints_not_found"]), (1, 1, 1))
        pa = next(p for p in pieces if p.src == 0xA)
        self.assertEqual(pa.doors, [(0, nm.DOOR_EXTRA, "000077:Fallout4.esm")])
        self.assertTrue(pa.flags[0] & nm.F_DOOR and not pa.flags[1] & nm.F_DOOR)
        self.assertFalse(any(f & nm.F_WATER for f in pa.flags))
        self.assertAlmostEqual(pa.heights[0], 170.0 / 70.0)
        self.assertEqual(pa.heights[1], nm.FLT_MAX)
        fids, navs, infos = sf_set(pieces)
        st = nm.validate(navs, infos)
        self.assertEqual(st["errors"], [])
        self.assertEqual((st["links"], st["links_symmetric"]), (2, 2))
        ext = navs[fids[pieces.index(pa)]].vertex_extra
        self.assertEqual(int(ext.sum()), 4)                         # every vertex is on an open edge somewhere
        fa, fb = fids[pieces.index(pa)], fids[1 - pieces.index(pa)]
        path = nm.triangle_path(navs, (fa, 1), (fb, 0))
        self.assertIsNotNone(path)
        self.assertEqual({f for f, _ in path}, {fa, fb})
        hit = nm.locate(navs, 25.0, 15.0, z=0.0)
        self.assertEqual(hit[0][1], fb)

    def portal(self, xa, xb):
        """Navmesh A ending at x = xa and B starting at x = xb (units; 7000 = 100 m, a cell line), joined by one FO4
        type-0 portal: (fo4_portal links, subedge drops, validate errors, a path from A to B)."""
        av, _ = square(xa - 700, 700, xa, 1400)
        bv, _ = square(xb, 700, xb + 700, 1400)
        at = [((0, 1, 2), (-1, 0, 1), 3.4e38, FOUND | nm.EDGE_LINK_BITS[1]), ((0, 2, 3), (0, -1, -1), 3.4e38, FOUND)]
        bt = [((0, 1, 2), (-1, -1, 1), 3.4e38, FOUND), ((0, 2, 3), (0, -1, 0), 3.4e38, FOUND | nm.EDGE_LINK_BITS[2])]
        pieces, rep = nm.convert([self.fo4(0xA, av, at, links=[(0, 0xB, 1, 2)]),
                                  self.fo4(0xB, bv, bt, links=[(0, 0xA, 0, 1)])])
        fids, navs, infos = sf_set(pieces)
        ends = [fids[next(i for i, p in enumerate(pieces) if p.src == src)] for src in (0xA, 0xB)]
        return (rep["links"]["fo4_portal"], rep["dropped"]["fo4_portal_subedge_missing"],
                nm.validate(navs, infos)["errors"], nm.triangle_path(navs, (ends[0], 0), (ends[1], 0)) is not None)

    def test_a_portal_on_or_straddling_a_cell_line_is_linked(self):
        # #210: the portal's two sides were only joined inside one cell; on the 100 m line (or straddling it by less
        # than FO4's own 0.343 m portal gap) A's sub-edge is in cell 0 and B's in cell 1, so it was dropped
        for xa, xb in ((1400, 1400), (7007, 7007), (7000, 7000), (6986, 7014)):
            self.assertEqual(self.portal(xa, xb), (1, 0, [], True), (xa, xb))
        # sides 30 m apart are not joined across cells: dropped, one count per one-sided cell as before
        self.assertEqual(self.portal(7000, 7000 + 700 * 3)[:2], (0, 2))

    def test_deleted_triangles_are_skipped(self):
        v, t = square(0, 0, 700, 700)
        t = [t[0], (t[1][0], (-1, -1, -1), t[1][2], FOUND | nm.F_DELETED)]
        t[0] = (t[0][0], (-1, -1, -1), t[0][2], FOUND)
        pieces, rep = nm.convert([self.fo4(0x500, v, t)])
        self.assertEqual((rep["dropped"]["deleted_triangles"], sum(len(p.tris) for p in pieces)), (1, 1))


class ValidateTests(unittest.TestCase):
    def setUp(self):
        verts, tris = square(-700, 100, 700, 800)
        pieces, _ = nm.convert([(0x100, nm.parse(fo4_bytes(0x3C, (0, 0), verts, tris)))])
        self.fids, self.navs, self.infos = sf_set(pieces)

    def test_clean_set_passes(self):
        self.assertEqual(nm.validate(self.navs, self.infos)["errors"], [])

    def test_one_sided_link_is_reported(self):
        f = self.fids[0]
        m = self.navs[f]
        m.links["tri"][0] = (int(m.links["tri"][0]) + 1) % len(self.navs[self.fids[1]].triangles)
        errs = nm.validate(self.navs)["errors"]
        self.assertTrue(any("does not link back" in e for e in errs), errs)

    def test_dangling_link_and_missing_target(self):
        f = self.fids[0]
        m = self.navs[f]
        m.links = np.concatenate([m.links, m.links[:1]])            # an extra link no triangle uses
        errs = nm.validate(self.navs)["errors"]
        self.assertTrue(any("used by 0" in e for e in errs), errs)
        del self.navs[self.fids[1]]
        errs = nm.validate(self.navs)["errors"]
        self.assertTrue(any("missing navmesh" in e for e in errs), errs)

    def test_internal_neighbour_and_cell_and_nvmi(self):
        f = self.fids[0]
        m = self.navs[f]
        t = m.triangles
        k = next(k for k in range(3) if int(t["e"][0][k]) >= 0 and not int(t["flags"][0]) & nm.EDGE_LINK_BITS[k])
        t["e"][0][k] = 0                                           # points at itself, not at its neighbour
        m.vertices[0, 0] += 300.0                                  # leaves its cell
        self.infos[f].merged = []
        errs = nm.validate(self.navs, self.infos)["errors"]
        self.assertTrue(any("does not share" in e or "does not point back" in e for e in errs), errs)
        self.assertTrue(any("leave cell" in e for e in errs), errs)
        self.assertTrue(any("merged-to" in e for e in errs), errs)


class ExportTests(unittest.TestCase):
    def test_export_matches_the_reference_writer(self):
        # navmesh.json -> make_exp2d.reference_nvnm -> write_sf must give what piece_nvnm gives (the byte check that
        # compares TerrainExp2's output with Python rests on it)
        import make_exp2d
        verts = [(-1400, -1400, 70), (1400, -1400, 70), (0, 1400, 140)]
        tris = [((0, 1, 2), (-1, -1, -1), 3.4e38, FOUND)]
        pieces, _ = nm.convert([(0x200, nm.parse(fo4_bytes(0x3C, (0, 0), verts, tris)))])
        doc = nm.export(pieces)
        fids = [0x01000900 + i for i in range(len(pieces))]
        for i, e in enumerate(doc["navmeshes"]):
            ref = make_exp2d.reference_nvnm(e, 0x01000802, fids, {})
            want = nm.piece_nvnm(pieces[i], 0x01000802, fids)
            want.vertices = want.vertices.astype(np.float32).astype(np.float64)
            d, size, gmin, gmax, lists = nm.build_grid(want.vertices, want.triangles)
            want.grid_divisor, want.grid_size, want.grid_min, want.grid_max, want.grid_lists = d, size, gmin, gmax, lists
            self.assertEqual(nm.write_sf(ref), nm.write_sf(want))
            raw = e["grid"]["raw"]
            self.assertEqual(raw, nm.grid_raw(e["grid"]["lists"]))
            self.assertAlmostEqual(sum(e["nvmi"]["location"]), sum(np.array(want.vertices, np.float32).mean(0)), places=4)


class N1PlanTests(unittest.TestCase):
    def test_n1_entries_pass_the_runner_validation(self):
        # every N1 entry make_exp2d stages must be a valid npc_nav test (everything typed into the console validated)
        sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
        import make_exp2d
        import testqueue as tq
        req = {"queue": "q", "test": "0000_terrain_FO4CW_RedRocketSpawn", "verdict": "PASS"}
        for pre in (None, ["gnm"]):
            w = make_exp2d.n1_test("N1b_ptr_player", "ptr_player", [-985.0, 1139.0, 105.03], [-972.0, 1153.0, 105.03],
                                   [-989.0286, 1147.2, 105.2609], req, "PASS", "synthetic", pre)
            t = tq.npc_test(0, w)
            self.assertIs(t["fresh"], True)
            self.assertEqual(t["pre"], pre or [])
            self.assertEqual((t["npc"], t["travel"], t["anchor"]["ref"]), ("002B211C", "coc FO4CW_RedRocketSpawn", "02000800"))
            self.assertFalse(t["control"] or t["baseline"])
            self.assertEqual(t["reads_s"], [0.0, 5.0, 15.0, 30.0, 60.0])


if __name__ == "__main__":
    unittest.main()
