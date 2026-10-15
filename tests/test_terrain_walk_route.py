"""scripts/terrain/walk_route.py (docs/terrain/walk-redrocket-sanctuary.md): the navmesh graph and its edge links, A*,
the funnel, the walkability raster (blocking, rises, clearance), line of sight, waypoints and cell crossings. Synthetic
data only."""
import importlib.util
import math
import os
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("terrain_walk_route",
                                              os.path.join(ROOT, "scripts", "terrain", "walk_route.py"))
wr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wr)
nm = wr.nm


def squares_mesh(cells, z=0.0):
    """A TriMesh of unit squares (two triangles each) joined over their shared edges."""
    verts, keys = [], []
    for cx, cy in cells:
        a, b, c, d = (cx, cy, z), (cx + 1, cy, z), (cx + 1, cy + 1, z), (cx, cy + 1, z)
        verts += [(a, b, c), (a, c, d)]
        keys += [(0, len(keys)), (0, len(keys) + 1)]
    edges = {}
    for i, t in enumerate(verts):
        for k in range(3):
            e = frozenset((t[k][:2], t[(k + 1) % 3][:2]))
            edges.setdefault(e, []).append((i, k))
    nbrs = [[] for _ in verts]
    for pair in edges.values():
        if len(pair) == 2:
            (i, ki), (j, kj) = pair
            nbrs[i].append((j, ki))
            nbrs[j].append((i, kj))
    return wr.TriMesh(np.array(verts, float), keys, nbrs)


def nvnm(verts, tris, links=()):
    """A Fallout 4 NVNM (file units) with triangles [(v0, v1, v2, e01, e12, e20, flags)] and edge links
    [(navmesh, tri, edge)]."""
    t = np.zeros(len(tris), nm.TRI_DTYPE)
    for k, (a, b, c, e0, e1, e2, fl) in enumerate(tris):
        t[k]["v"], t[k]["e"], t[k]["flags"] = (a, b, c), (e0, e1, e2), fl
    L = np.zeros(len(links), nm.LINK_DTYPE)
    for k, (navm, tri, edge) in enumerate(links):
        L[k]["navmesh"], L[k]["tri"], L[k]["edge"] = navm, tri, edge
    return nm.Nvnm(15, nm.MAGIC, 0x3C, (0, 0), None, np.array(verts, float), None, t, L,
                   np.zeros(0, nm.DOOR_DTYPE), [], np.zeros(0, nm.COVERMAP_DTYPE), np.zeros(0, nm.WAYPOINT_DTYPE),
                   0, (0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), [])


class NavmeshTests(unittest.TestCase):
    def test_edges_and_edge_links_join_triangles_across_navmeshes(self):
        u = wr.UNITS
        # navmesh 1: the square x 0..1 m (two triangles, edge 1-2 of triangle 0 links to navmesh 2 at x = 1 m);
        # navmesh 2: the square x 1..2 m; a deleted triangle is left out
        a = nvnm([(0, 0, 0), (u, 0, 0), (u, u, 0), (0, u, 0)],
                 [(0, 1, 2, -1, 0, 1, nm.EDGE_LINK_BITS[1]), (0, 2, 3, 0, -1, -1, 0)], [(2, 0, 2)])
        b = nvnm([(u, 0, 0), (2 * u, 0, 0), (2 * u, u, 0), (u, u, 0)],
                 [(0, 1, 3, -1, 1, 0, nm.EDGE_LINK_BITS[2]), (1, 2, 3, -1, -1, 0, 0), (1, 2, 3, -1, -1, -1, nm.F_DELETED)],
                 [(1, 0, 1)])
        mesh = wr.TriMesh.from_navs({1: a, 2: b})
        self.assertEqual(len(mesh.keys), 4)                                 # the deleted triangle is not there
        i, j = mesh.keys.index((1, 0)), mesh.keys.index((2, 0))
        self.assertIn(j, [n for n, _k in mesh.nbrs[i]])
        self.assertIn(i, [n for n, _k in mesh.nbrs[j]])
        self.assertAlmostEqual(mesh.v[j][1][0], 2.0)                         # metres = units / 70
        path = wr.astar(mesh, mesh.keys.index((1, 1)), mesh.keys.index((2, 1)))
        self.assertEqual(path[0], mesh.keys.index((1, 1)))
        self.assertEqual(len(path), 4)
        self.assertEqual(mesh.locate(1.5, 0.2)[0], j)

    def test_the_funnel_bends_only_at_the_inner_corner(self):
        mesh = squares_mesh([(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)])
        s = mesh.locate(0.5, 0.5)[0]
        g = mesh.locate(2.5, 2.5)[0]
        corridor = wr.astar(mesh, s, g)
        pts = wr.funnel((0.5, 0.5, 0.0), (2.5, 2.5, 0.0), wr.portals(mesh, corridor))
        self.assertEqual(len(pts), 3, pts)
        self.assertAlmostEqual(pts[1][0], 2.0)
        self.assertAlmostEqual(pts[1][1], 1.0)
        straight = wr.funnel((0.5, 0.5, 0.0), (2.5, 0.5, 0.0), wr.portals(mesh, wr.astar(mesh, s, mesh.locate(2.5, 0.5)[0])))
        self.assertEqual(len(straight), 2)

    def test_a_short_portal_is_narrowed_to_its_middle(self):
        a, b = wr.narrow((0, 0, 0), (0.5, 0, 0), 0.45)
        self.assertEqual(a, b)
        self.assertAlmostEqual(a[0], 0.25)
        a, b = wr.narrow((0, 0, 0), (4, 0, 0), 0.5)
        self.assertAlmostEqual(a[0], 0.5)
        self.assertAlmostEqual(b[0], 3.5)

    def test_the_layer_nearest_the_corridor_is_taken(self):
        low = squares_mesh([(0, 0)], z=100.0)
        high = squares_mesh([(0, 0)], z=106.0)
        mesh = wr.TriMesh(np.concatenate([low.v, high.v]), low.keys + [(1, k) for k in range(2)], [[], [], [], []])
        self.assertEqual(mesh.layer(0.5, 0.5, 97, 112), 106.0)                       # highest
        self.assertEqual(mesh.layer(0.5, 0.5, 97, 112, near=100.3), 100.0)           # the ground under a canopy
        self.assertEqual(mesh.layer(0.5, 0.5, 97, 112, near=105.0), 106.0)           # a bridge deck over a river bed
        self.assertIsNone(mesh.layer(0.5, 0.5, 107, 112))


def open_grid(nx=40, ny=40, z=0.0):
    g = wr.Grid(0.0, 0.0, nx, ny, 0.5)
    g.nav[:] = z
    g.sup[:] = z
    return g


class GridTests(unittest.TestCase):
    def test_a_wall_triangle_blocks_only_inside_the_capsule(self):
        g = open_grid()
        wall = [[(5.0, 2.0, -1.0), (5.0, 18.0, -1.0), (5.0, 18.0, 3.0)], [(5.0, 2.0, -1.0), (5.0, 18.0, 3.0), (5.0, 2.0, 3.0)]]
        floor = [[(0.0, 0.0, 0.1), (20.0, 0.0, 0.1), (20.0, 20.0, 0.1)]]       # a kerb-high slab: walked over
        wr.mark_blocked(g, np.array(wall + floor))
        g.finish()
        self.assertTrue(g.blocked[g.cell(5.1, 10.0)])
        self.assertTrue(g.blocked[g.cell(4.8, 10.0)])
        self.assertFalse(g.blocked[g.cell(5.6, 10.0)])                         # 0.35 m capsule + a cell
        self.assertFalse(g.blocked[g.cell(5.1, 1.0)])                          # past the wall's end
        self.assertFalse(g.blocked[g.cell(10.0, 10.0)])
        self.assertEqual(g.clear[g.cell(10.25, 10.25)], 4.0)                   # capped
        self.assertLessEqual(g.clear[g.cell(5.75, 10.25)], 1.0)

    def test_the_path_goes_round_a_wall_and_never_up_a_cliff(self):
        g = open_grid()
        g.blocked[g.cell(10.0, 0.0)[0], :30] = True                            # a wall x = 10, y 0..15
        g.sup[:, 34:] = 2.0                                                    # a 2 m cliff at y = 17
        g.finish()
        s, e = g.cell(5.25, 5.25), g.cell(15.25, 5.25)
        cells = wr.grid_astar(g, s, e)
        self.assertIsNotNone(cells)
        ys = [g.centre(*c)[1] for c in cells]
        self.assertGreater(max(ys), 15.0)                                      # round the wall's end
        self.assertLess(max(ys), 17.0)                                         # not over the cliff
        self.assertIsNone(wr.grid_astar(g, s, g.cell(5.25, 18.25)))             # the top of the cliff: unreachable
        pts = [g.centre(*c) for c in cells]
        pulled = wr.prune(wr.smooth(pts, lambda p, q: wr.line_ok(g, p, q)), lambda p, q: wr.line_ok(g, p, q))
        self.assertLessEqual(len(pulled), 5)
        for p, q in zip(pulled, pulled[1:]):
            self.assertTrue(wr.line_ok(g, p, q))
        self.assertFalse(wr.line_ok(g, pulled[0], pulled[-1]))                  # straight through the wall

    def test_line_of_sight_keeps_its_clearance(self):
        g = open_grid()
        g.blocked[g.cell(10, 0)[0], :] = True
        g.finish()
        self.assertTrue(wr.line_ok(g, (2.25, 5.25), (2.25, 15.25)))
        self.assertFalse(wr.line_ok(g, (9.75, 5.25), (9.75, 15.25)))           # 0.5 m from the wall all along
        self.assertFalse(wr.line_ok(g, (5.25, 5.25), (15.25, 5.25)))


class PolylineTests(unittest.TestCase):
    def test_waypoints_close_at_corners_and_on_the_bridge(self):
        pts = [(0.0, 0.0, 0.0), (40.0, 0.0, 0.0), (40.0, 30.0, 0.0)]
        wps = wr.place_waypoints(pts, span=(5.0, 25.0))
        s = [w["s"] for w in wps]
        self.assertEqual((wps[0]["kind"], wps[-1]["kind"]), ("start", "goal"))
        self.assertTrue(all(b - a <= wr.LEG_MAX + 1e-6 for a, b in zip(s, s[1:])))
        on = [b - a for a, b in zip(s, s[1:]) if a >= 5.0 and b <= 25.0]
        self.assertTrue(on and all(g <= wr.LEG_BRIDGE + 1e-6 for g in on))
        corner = next(w for w in wps if w["kind"] == "corner")
        self.assertEqual((corner["x"], corner["y"], corner["turn"]), (40.0, 0.0, 90.0))
        self.assertEqual(wr.reach_of(corner), wr.REACH_CORNER)
        self.assertIn(36.0, s)                                                 # 4 m before the corner
        self.assertIn(44.0, s)                                                 # and after it
        self.assertEqual(wr.reach_of(wps[-1]), wr.GOAL_RADIUS)

    def test_close_corners_merge(self):
        pts = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.4, 0.4, 0.0), (10.4, 10.0, 0.0)]
        wps = wr.place_waypoints(pts)
        self.assertTrue(all(b["s"] - a["s"] >= 1.0 for a, b in zip(wps, wps[1:])), wps)

    def test_the_cell_borders_a_path_crosses(self):
        smp = wr.samples([(-995.0, 1150.0, 0.0), (-1005.0, 1150.0, 0.0), (-1005.0, 1210.0, 0.0)])
        cells, cross = wr.crossings(smp)
        self.assertEqual(cells, [[-10, 11], [-11, 11], [-11, 12]])
        self.assertEqual([(c["axis"], c["at"]) for c in cross], [("x", -1000.0), ("y", 1200.0)])
        self.assertAlmostEqual(cross[0]["s"], 5.0, delta=0.5)

    def test_distance_to_a_polyline(self):
        d, s = wr.polyline_distance([(0, 0), (10, 0), (10, 10)], 12.0, 5.0)
        self.assertAlmostEqual(d, 2.0)
        self.assertAlmostEqual(s, 15.0)
        got = wr.segment_distance(np.array([12.0, 5.0]), np.array([5.0, 3.0]), [(0, 0), (10, 0), (10, 10)])
        self.assertTrue(np.allclose(got, [2.0, 3.0]))
        self.assertTrue(math.isclose(wr.turn_deg((0, 0), (1, 0), (1, 1)), 90.0))


if __name__ == "__main__":
    unittest.main()
