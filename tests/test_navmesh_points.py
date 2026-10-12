"""scripts/actors/navmesh_points.py on synthetic navmeshes and a synthetic plugin: the triangle graph and its
components, the corridor path (funnel), the placed-object classes, free space and clearance, the pair rules, and the
whole `analyze` run on a tiny hand-built Starfield-layout plugin. No game data."""
import json
import math
import os
import struct
import sys
import tempfile
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "actors"))
import navmesh_points as npt  # noqa: E402
from fo4sf import navmesh as nm  # noqa: E402


def mesh(verts, faces, cell=0x00ABC001, links=(), link_edges=()):
    """A Starfield interior Nvnm from vertices (x, y, z) and counter-clockwise faces; shared edges are joined.
    link_edges: [(face, edge k, link index)] edges that are edge links instead."""
    tris = np.zeros(len(faces), nm.TRI_DTYPE)
    owner = {}
    for fi, f in enumerate(faces):
        for k in range(3):
            owner.setdefault(frozenset((f[k], f[(k + 1) % 3])), []).append((fi, k))
    for fi, f in enumerate(faces):
        e = []
        for k in range(3):
            other = [x for x in owner[frozenset((f[k], f[(k + 1) % 3]))] if x[0] != fi]
            e.append(other[0][0] if other else -1)
        tris[fi] = (f, e, 6.0, 0, nm.F_FOUND, 0)
    for fi, k, li in link_edges:
        tris[fi]["e"][k] = li
        tris[fi]["flags"] |= nm.EDGE_LINK_BITS[k]
    lk = np.zeros(len(links), nm.LINK_DTYPE)
    for i, x in enumerate(links):
        lk[i] = x
    v = np.asarray(verts, np.float64)
    d, size, gmin, gmax, lists = nm.build_grid(v, tris)
    return nm.Nvnm(nm.SF_VERSION, nm.MAGIC, 0, None, cell, v, np.zeros(len(v), np.int32), tris, lk,
                   np.zeros(0, nm.DOOR_DTYPE), [], np.zeros(0, nm.COVERMAP_DTYPE), np.zeros(0, nm.WAYPOINT_DTYPE),
                   d, size, gmin, gmax, lists, nm.SF_TRAILER)


def grid_mesh(cells, size=1.0, cell=0x00ABC001):
    """Unit squares at the given (i, j) grid cells, two triangles each, joined where they touch."""
    idx, verts, faces = {}, [], []

    def v(i, j):
        if (i, j) not in idx:
            idx[(i, j)] = len(verts)
            verts.append((i * size, j * size, 0.0))
        return idx[(i, j)]
    for i, j in cells:
        a, b, c, d = v(i, j), v(i + 1, j), v(i + 1, j + 1), v(i, j + 1)
        faces += [(a, b, c), (a, c, d)]
    return mesh(verts, faces, cell)


def room(w=24.0, h=24.0):
    """A w x h rectangle, two triangles, origin at the south-west corner."""
    return mesh([(0, 0, 0), (w, 0, 0), (w, h, 0), (0, h, 0)], [(0, 1, 2), (0, 2, 3)])


class GraphTests(unittest.TestCase):
    def test_components_area_bounds_and_links(self):
        a = grid_mesh([(0, 0), (1, 0)])
        b = grid_mesh([(5, 0)], cell=0x00ABC001)
        navs = {0x100: a, 0x200: b}
        comps = npt.components(navs)
        self.assertEqual(len(comps), 2)
        self.assertAlmostEqual(comps[0]["area_m2"], 2.0)
        self.assertEqual(comps[0]["bounds"][0][:2], [0.0, 0.0])
        self.assertEqual(comps[0]["bounds"][1][:2], [2.0, 1.0])
        # an edge link from the east square of a to b (and back) joins them; a link to a navmesh outside the cell is
        # an exit, not a neighbour
        f = a.triangles
        east = next(i for i in range(len(f)) if any(int(e) < 0 for e in f["e"][i])
                    and a.vertices[f["v"][i]][:, 0].max() == 2.0)
        k = next(k for k in range(3) if int(f["e"][east][k]) < 0
                 and a.vertices[f["v"][east][k]][0] == 2.0 and a.vertices[f["v"][east][(k + 1) % 3]][0] == 2.0)
        a2 = mesh(a.vertices, [tuple(x) for x in f["v"]], links=[(0, 0x200, 0, 2), (0, 0x999, 0, 0)],
                  link_edges=[(east, k, 0)])
        navs = {0x100: a2, 0x200: b}
        comps = npt.components(navs)
        self.assertEqual(len(comps), 1)
        self.assertAlmostEqual(comps[0]["area_m2"], 3.0)
        lonely = mesh(a.vertices, [tuple(x) for x in f["v"]], links=[(0, 0x999, 0, 0)], link_edges=[(east, k, 0)])
        comps = npt.components({0x100: lonely})
        self.assertEqual((len(comps), comps[0]["exits"]), (1, 1))

    def test_boundary_edges_of_a_rectangle(self):
        self.assertEqual(len(npt.boundary_edges({1: room()})), 4)
        self.assertEqual(len(npt.boundary_edges({1: grid_mesh([(0, 0), (1, 0), (2, 0)])})), 8)

    def test_funnel_hugs_the_inner_corner_of_an_l(self):
        navs = {1: grid_mesh([(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)])}
        length, pts = npt.navmesh_path(navs, (0.5, 0.5, 0), (2.5, 2.5, 0))
        self.assertAlmostEqual(length, 2 * math.hypot(1.5, 0.5), places=6)     # via the inner corner (2, 1)
        self.assertIn((2.0, 1.0), [tuple(round(c, 6) for c in p) for p in pts])
        # and the mirror image (turning the other way)
        navs = {1: grid_mesh([(0, 2), (1, 2), (2, 2), (2, 1), (2, 0)])}
        length, _ = npt.navmesh_path(navs, (0.5, 2.5, 0), (2.5, 0.5, 0))
        self.assertAlmostEqual(length, 2 * math.hypot(1.5, 0.5), places=6)
        # inside one convex room the corridor path is the straight line
        length, pts = npt.navmesh_path({1: room()}, (2, 3, 0), (20, 19, 0))
        self.assertAlmostEqual(length, math.hypot(18, 16), places=6)
        self.assertEqual(len(pts), 2)

    def test_disconnected_points_have_no_path(self):
        navs = {1: grid_mesh([(0, 0)]), 2: grid_mesh([(3, 0)])}
        self.assertIsNone(npt.navmesh_path(navs, (0.5, 0.5, 0), (3.5, 0.5, 0)))
        self.assertIsNone(npt.navmesh_path(navs, (0.5, 0.5, 0), (9.5, 0.5, 0)))   # off the navmesh


class ObjectTests(unittest.TestCase):
    WALL = {"type": "STAT", "edid": "Wall6x6", "flags": 0, "obnd": [-3, 0, 0, 3, 0.13, 6]}

    def test_rotation_is_clockwise_x_then_y_then_z(self):
        c = npt.box_corners(self.WALL["obnd"], (10, 10, 0), (0, 0, math.pi / 2))
        self.assertAlmostEqual(c[:, 1].min(), 7.0)                # a quarter turn: the 6 m wall now runs along y
        self.assertAlmostEqual(c[:, 1].max(), 13.0)
        self.assertAlmostEqual(c[:, 0].min(), 10.0, places=6)     # clockwise: local +y goes to world +x
        self.assertAlmostEqual(c[:, 0].max(), 10.13, places=6)

    def test_classes(self):
        floor = {"type": "STAT", "edid": "Gravel6x6", "flags": 0, "obnd": [-3, -3, 0, 3, 3, 0]}
        cases = [
            (self.WALL, (0, 0, 0), (0, 0, 0), "obstacle"),
            (floor, (0, 0, 0), (0, 0, 0), "floor"),
            (self.WALL, (0, 0, 6), (0, math.pi / 2, 0), "overhead"),       # the wall laid flat at z 6: a ceiling
            ({"type": "STAT", "edid": "COCMarkerHeading", "flags": npt.MARKER_FLAG | 4,
              "obnd": [-0.4, -0.4, 0, 0.4, 0.9, 1.9]}, (0, 0, 0), (0, 0, 0), "marker"),
            ({"type": "LIGH", "edid": "defaultLight01", "flags": 0, "obnd": [-0.1] * 3 + [0.1] * 3}, (0, 0, 1),
             (0, 0, 0), "light"),
            ({"type": "FURN", "edid": "Chair", "flags": 0, "obnd": [-0.3, -0.3, 0, 0.3, 0.3, 1]}, (0, 0, 0), (0, 0, 0),
             "sandbox"),
        ]
        for base, pos, rot, want in cases:
            c = npt.box_corners(base["obnd"], pos, rot)
            self.assertEqual(npt.classify(base, c, 0.0), want, base["edid"])

    def test_convex_hull(self):
        hull = npt.convex_hull([(0, 0), (2, 0), (2, 1), (0, 1), (1, 0.5), (1, 0)])
        self.assertEqual(len(hull), 4)
        self.assertAlmostEqual(npt.polygon_area(hull), 2.0)


class FreeSpaceTests(unittest.TestCase):
    def setUp(self):
        self.navs = {1: room(24, 24)}
        # a 6 m wall standing across the middle, x 9..15 at y 12
        self.wall = {"footprint": [[9, 12], [15, 12], [15, 12.13], [9, 12.13]]}
        self.fs = npt.FreeSpace(self.navs, [self.wall])

    def test_clearance_and_the_open_border(self):
        self.assertAlmostEqual(self.fs.clearance((12, 6)), 6.0, delta=0.1)           # 6 m south of the wall
        self.assertAlmostEqual(self.fs.clearance((1, 6)), 1.0, delta=0.1)            # 1 m from the west border
        self.assertEqual(self.fs.clearance((12, 12.05)), 0.0)                          # inside the wall
        self.assertEqual(self.fs.clearance((30, 6)), 0.0)                              # off the navmesh

    def test_a_blocked_segment_detours_and_a_clear_one_is_straight(self):
        a, b = (12, 6, 0), (12, 18, 0)
        self.assertEqual(self.fs.segment_clearance(a, b), 0.0)
        p = self.fs.path(a, b)
        self.assertGreater(p, 12.0 * 1.05)                                          # around the wall end
        self.assertLess(p, 12.0 * 1.25)
        self.assertEqual(self.fs.path((3, 6, 0), (3, 18, 0)), 12.0)
        m = npt.measure(self.navs, npt.components(self.navs), self.fs, a, b, arrival=(12, 3, 0), trace=[(12, 4, 0)])
        self.assertTrue(m["same_component"])
        self.assertEqual(m["navmesh_path"], 12.0)                                    # the navmesh has no hole for it
        self.assertGreater(m["free_path_ratio"], 1.05)
        self.assertEqual(m["attractor_progress"], 12.0 - 15.0)
        self.assertEqual(m["b_from_trace"], 14.0)

    def test_free_space_components_split_by_a_full_wall(self):
        wall = {"footprint": [[0, 12], [24, 12], [24, 12.2], [0, 12.2]]}
        fs = npt.FreeSpace(self.navs, [wall])
        _lab, sizes = fs.labels()
        self.assertEqual(len(sizes), 2)
        self.assertIsNone(fs.path((12, 6, 0), (12, 18, 0)))


class PairTests(unittest.TestCase):
    def test_pairs_follow_every_rule(self):
        navs = {1: room(24, 24)}
        fs = npt.FreeSpace(navs, [{"footprint": [[9, 12], [15, 12], [15, 12.13], [9, 12.13]]}])
        comps = npt.components(navs)
        arrival = (12, 2, 0)
        trace = [(10, 3, 0), (14, 4, 0)]
        pairs, counts = npt.pick_pairs(navs, comps, fs, arrival, trace, lattice=1.0, top=5)
        self.assertTrue(pairs)
        self.assertEqual(counts["pairs_ranked"], len(pairs))
        for m in pairs:
            self.assertTrue(npt.PAIR_MIN <= m["distance"] <= npt.PAIR_MAX)
            self.assertGreaterEqual(min(m["a_clearance"], m["b_clearance"]), npt.END_CLEAR)
            self.assertGreaterEqual(m["segment_clearance"], npt.SEG_CLEAR)
            self.assertLessEqual(m["free_path_ratio"], npt.DETOUR_MAX)
            self.assertGreaterEqual(m["b_from_arrival"], npt.B_FROM_ARRIVAL)
            self.assertGreaterEqual(m["a_from_arrival"], npt.A_FROM_ARRIVAL)
            self.assertGreaterEqual(m["b_from_trace"], npt.B_FROM_TRACE)
            self.assertLessEqual(m["drift_progress"], npt.DRIFT_MAX)
            # the drift covers the arrival, the navmesh centre (12, 12) and every traced read
            for x in [arrival, (12, 12, 0)] + trace:
                self.assertLessEqual(m["distance"] - math.dist(m["b"][:2], x[:2]), m["drift_progress"] + 1e-3)
        self.assertEqual([m["score"] for m in pairs], sorted(m["score"] for m in pairs))
        again, _ = npt.pick_pairs(navs, comps, fs, arrival, trace, lattice=1.0, top=5)
        self.assertEqual(json.dumps(pairs), json.dumps(again))                        # deterministic

    def test_drift_names_the_worst_attractor(self):
        dp, k = npt.drift((0, 0), (20, 0), [(30, 0), (12, 0), (0, 5)])
        self.assertEqual((dp, k), (12.0, 1))                                          # 20 m, but 8 m from (12, 0)
        self.assertEqual(npt.drift((0, 0), (20, 0), []), (None, None))
        self.assertEqual(npt.centroid({1: room(24, 12)}, npt.components({1: room(24, 12)})[0])[:2], (12.0, 6.0))


# ------------------------------------------------------------------------------------------------ a synthetic plugin
def rec(typ, fid, fields, flags=0):
    data = b"".join(sig + struct.pack("<H", len(d)) + d for sig, d in fields)
    return struct.pack("<4sIII", typ, len(data), flags, fid) + b"\0" * 8 + data


def grup(label, gtype, body):
    lab = label if isinstance(label, bytes) else struct.pack("<I", label)
    return struct.pack("<4sI4si", b"GRUP", 24 + len(body), lab, gtype) + b"\0" * 8 + body


def refr(fid, base, pos, rot=(0, 0, 0)):
    return rec(b"REFR", fid, [(b"NAME", struct.pack("<I", base)), (b"DATA", struct.pack("<6f", *pos, *rot))])


def plugin_bytes():
    """TES4, a STAT group (wall, floor tile, COC marker), and one interior cell 'TestRoom' with a 24 x 24 m navmesh,
    a wall across its middle, a floor tile and the COC marker."""
    nav = room(24, 24)
    nvnm = nm.write_sf(nav)
    stat = (rec(b"STAT", 0x10, [(b"EDID", b"Wall6x6\0"), (b"OBND", struct.pack("<6f", -3, 0, 0, 3, 0.13, 6))])
            + rec(b"STAT", 0x11, [(b"EDID", b"Gravel6x6\0"), (b"OBND", struct.pack("<6f", -3, -3, 0, 3, 3, 0))])
            + rec(b"STAT", 0x32, [(b"EDID", b"COCMarkerHeading\0"),
                                  (b"OBND", struct.pack("<6f", -0.4, -0.4, 0, 0.4, 0.9, 1.9))], flags=0x00800004))
    temp = (rec(b"NAVM", 0x2001, [(b"NVNM", nvnm), (b"MNAM", b"")])
            + refr(0x2002, 0x10, (12, 12, 0)) + refr(0x2003, 0x11, (3, 3, 0)))
    pers = refr(0x2004, 0x32, (12, 3, 0))
    children = grup(0x2000, 6, grup(0x2000, 8, pers) + grup(0x2000, 9, temp))
    other = rec(b"CELL", 0x1000, [(b"EDID", b"OtherRoom\0"), (b"DATA", b"\1\0")])
    cell = rec(b"CELL", 0x2000, [(b"EDID", b"TestRoom\0"), (b"DATA", b"\1\0")])
    cells = grup(b"CELL", 0, grup(0, 2, grup(0, 3, other + grup(0x1000, 6, b"") + cell + children)))
    return rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 0.96, 3, 0x800))]) + grup(b"STAT", 0, stat) + cells


class AnalyzeTests(unittest.TestCase):
    def test_analyze_a_synthetic_plugin(self):
        d = tempfile.mkdtemp()
        esm = os.path.join(d, "Synthetic.esm")
        with open(esm, "wb") as f:
            f.write(plugin_bytes())
        res, navs, fs, objs = npt.analyze(esm, "TestRoom", (6, 6, 0), (18, 18, 0))
        self.assertEqual(res["cell"]["form_id"], "00002000")
        self.assertEqual([n["form_id"] for n in res["navmeshes"]], ["00002001"])
        self.assertEqual(res["components"][0]["area_m2"], 576.0)
        self.assertEqual(res["objects"]["classes"], {"floor": 1, "marker": 1, "obstacle": 1})
        self.assertEqual(res["arrival"]["pos"], [12.0, 3.0, 0.0])
        old = res["old_pair"]
        self.assertTrue(old["same_component"])
        self.assertEqual(old["segment_clearance"], 0.0)                 # the diagonal crosses the wall at (12, 12)
        ch = res["chosen"]
        self.assertIsNotNone(ch)
        self.assertGreaterEqual(ch["segment_clearance"], npt.SEG_CLEAR)
        self.assertEqual(res["chosen_reversed"]["a"], ch["b"])
        self.assertIn("TestRoom 00002000", npt.summary(res))
        res2 = npt.analyze(esm, "TestRoom", (6, 6, 0), (18, 18, 0))[0]
        self.assertEqual(json.dumps(res, sort_keys=True), json.dumps(res2, sort_keys=True))
        with self.assertRaises(KeyError):
            npt.analyze(esm, "NoSuchRoom")
        try:
            from PIL import Image  # noqa: F401  (render needs Pillow; the test env may lack it)
        except ImportError:
            return
        png = os.path.join(d, "top.png")
        npt.render(res, navs, fs, objs, png)
        self.assertGreater(os.path.getsize(png), 1000)


if __name__ == "__main__":
    unittest.main()
